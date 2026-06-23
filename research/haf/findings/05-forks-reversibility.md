# HAF Part 05 - Forks & Reversibility

**Anchor:** HAF `1.28.6` (`222c848355`).
**Scope:** the mechanism that makes HAF apps fork-safe - the shadow-table undo log, the
triggers that fill it, and the `back_from_fork` rewind that reverts an app's derived data
when `hived` switches forks. The registry rows (`registered_tables`, `triggers`) are part
02; the forking-vs-non-forking app choice is part 03; the reversible/irreversible block
tables and views are part 02/04.

Paths relative to `src/hive_fork_manager/context_rewind/`.

---

## 1. The problem and the approach

A HAF app derives its own tables from block data. When `hived` switches forks, the blocks
the app already processed on the losing branch are gone - and so must be the app's derived
rows for them. HAF solves this generically with a **per-table undo log**: every change an
app makes is recorded, and on a fork the changes since the fork point are **replayed in
reverse**. The app writes no fork logic - it just processes blocks forward and HAF rewinds
when needed.

This applies only to **forking** contexts (part 03); non-forking / lite contexts skip the
whole apparatus.

---

## 2. Registration: shadow table + triggers + revert functions

`app_register_table` (part 03) wires three things per app table (`register_table.sql`,
`triggers.sql`):

### Shadow table (the undo log) - `create_shadow_table`

`CREATE TABLE hafd.<shadow> AS TABLE <origin>` (same columns), emptied, then augmented
(`register_table.sql:118-122`) with:

| Added column | Meaning |
|--------------|---------|
| `hive_block_num INTEGER` | block at which the change happened |
| `hive_operation_type hafd.trigger_operation` | `INSERT` / `DELETE` / `UPDATE` |
| `hive_operation_id BIGSERIAL PRIMARY KEY` | monotonic change sequence (the undo order) |
| (`hive_rowid`) | identifies the affected origin row |

So each shadow row is "to undo change N at block B on this table, do the inverse using
these old/new column values".

### Triggers - `create_triggers`

**Statement-level `AFTER` triggers with transition tables** (`triggers.sql:23`,`:34`,`:45`,`:56`):

- `AFTER INSERT ... REFERENCING NEW TABLE AS NEW_TABLE FOR EACH STATEMENT`
- `AFTER DELETE ... REFERENCING OLD TABLE AS OLD_TABLE FOR EACH STATEMENT`
- `AFTER UPDATE ... REFERENCING OLD TABLE AS OLD_TABLE FOR EACH STATEMENT`
- `BEFORE TRUNCATE ... FOR EACH STATEMENT`

Statement-level + transition tables means HAF records **all rows changed by a statement in
one shot** (not per-row), recording the data needed to undo it (the inserted rows for an
INSERT, the OLD rows for DELETE/UPDATE) into the shadow with the current block + op type.

### Revert functions - `create_revert_functions`

Three per table (`register_table.sql`): `hafd.<schema>_<table>_revert_insert(row_id)`
(delete the inserted row), `_revert_delete(operation_id)` (re-insert the deleted row from
the shadow), `_revert_update(operation_id, row_id)` (restore old values from the shadow).

---

## 3. The fork switch: `back_from_fork`

When `hived` switches forks it notifies HAF, which records a `hafd.fork` row
(`block_num` = head after reverting the fork's blocks; part 02) and enqueues a
`BACK_FROM_FORK` event (`hafd.events_queue`, part 02). When a forking app's context
consumes that event (the forking path of `app_next_block`, part 03),
`context_back_from_fork(context, block_num_before_fork)` (`rewind_api.sql`) runs
`hive.back_from_fork_one_table(...)` for each registered table.

The replay (`back_from_fork.sql`, `back_from_fork_one_table`):

```sql
FOR st IN (... shadow ... WHERE hive_block_num > <block_num_before_fork>
                          ORDER BY hive_operation_id DESC)   -- newest change first
  CASE st.hive_operation_type
    WHEN 'INSERT' THEN ..._revert_insert(st.hive_rowid)
    WHEN 'DELETE' THEN ..._revert_delete(st.hive_operation_id)
    WHEN 'UPDATE' THEN ..._revert_update(st.hive_operation_id, st.hive_rowid)
  END;
DELETE FROM hafd.<shadow> WHERE hive_block_num > <block_num_before_fork>;
```

So: undo every change after the fork point **in reverse order** (`ORDER BY
hive_operation_id DESC`), then clear those undo records. The app's tables are byte-for-byte
back to the pre-fork state, and processing resumes on the new branch.

---

## 4. Irreversibility: promotion + shadow GC

The undo log only needs to cover the **reversible** range - you can never fork below an
irreversible block. So:

- When a block becomes irreversible, its reversible rows are moved into the irreversible
  tables (part 02), and
- `hive.remove_obsolete_operations(shadow_table_name, irreversible_block)` (`irreversible.sql`)
  **drops the shadow undo records** at/below the irreversible block.

This bounds the undo log to the reversible window (~the last-irreversible distance), keeping
it small.

---

## 5. Forking vs non-forking

A **non-forking** (or lite) context registers no triggers/shadow tables and is never
rewound (part 03) - cheaper, but the app must either tolerate forks itself or process only
irreversible data. `app_next_block` picks the forking path only when the context is forking,
not lite, and live-or-not-pruning (part 03, `app_api.sql:218`); otherwise the non-forking
path. So an app opts into automatic rewind by being a forking context.

---

## 6. Notable findings

1. **Generic per-table undo log.** Any app table becomes fork-safe by registration - the
   shadow table + statement triggers record an undo log; no app-specific fork code.
2. **Statement-level triggers + transition tables** make capture cheap (one record op per
   statement, not per row) - important for massive-sync batches.
3. **Reverse replay by `hive_operation_id DESC`** is the whole rewind; correctness comes from
   undoing changes newest-first down to the fork point.
4. **The undo log is self-trimming** - `remove_obsolete_operations` drops irreversible
   entries, so the shadow tables stay bounded to the reversible window.
5. **Rewind is event-driven** - a `BACK_FROM_FORK` event in the queue is what triggers a
   context's rewind, so each app rewinds when it reaches that event, independently.
6. **Opt-in cost** - only forking contexts pay for triggers/shadows; analytics apps over
   irreversible data can skip it entirely.

---

## 7. Code References

| Topic | File:line |
|-------|-----------|
| Shadow table DDL | `context_rewind/register_table.sql:118-122` (`create_shadow_table`) |
| Revert functions | `context_rewind/register_table.sql` (`create_revert_functions`, `*_revert_insert/delete/update`) |
| Capture triggers (statement-level) | `context_rewind/triggers.sql:23`,`:34`,`:45`,`:56` (`create_triggers`) |
| Rewind replay | `context_rewind/back_from_fork.sql` (`back_from_fork_one_table`; revert dispatch + `ORDER BY hive_operation_id DESC` + shadow cleanup) |
| Per-row revert ops | `context_rewind/back_from_fork.sql` (`revert_insert`/`revert_delete`/`revert_update`) |
| Shadow GC at irreversible | `context_rewind/irreversible.sql` (`remove_obsolete_operations`) |
| Context rewind API | `context_rewind/rewind_api.sql` (`context_back_from_fork`, `context_detach`, ...) |
| fork table / BACK_FROM_FORK event | `forks.sql:1`; `events_queue.sql` (part 02) |

---

## 8. Open Questions (for later parts / zoom)

- **`hafd.trigger_operation`** and the exact trigger procedure bodies (how OLD/NEW transition
  rows are written into the shadow) - a zoom candidate.
- **State-provider rewind** - whether `accounts`/`keyauth`/`metadata` (part 04) use the same
  shadow mechanism or a dedicated path.
- **Multi-table ordering** - whether cross-table referential consistency during rewind needs
  a global order (vs per-table `hive_operation_id`).
- **`detach_table` / `event_triggers.sql`** - the DDL-event handling that keeps the registry
  consistent when apps alter tables.
- **Interaction with massive-sync** - how the undo log behaves when reindex flushes mark data
  implicitly irreversible (part 06).
