# HAF Reference - Forks & Reversibility

How HAF reverts an app's derived data on a fork switch, with no app-side fork code. Deep
detail: `findings/05-forks-reversibility.md`. Paths relative to
`src/hive_fork_manager/context_rewind/`.

Applies only to **forking** contexts; non-forking/lite contexts skip all of this.

## The undo log (set up at `app_register_table`)

Per registered table, HAF creates:

| Thing | What | File |
|-------|------|------|
| **Shadow table** | `CREATE TABLE hafd.<shadow> AS TABLE <origin>` + `hive_block_num` + `hive_operation_type` + `hive_operation_id` (bigserial) | `register_table.sql:118-122` (`create_shadow_table`, `:105`) |
| **Capture triggers** | statement-level `AFTER INSERT/UPDATE/DELETE` + `BEFORE TRUNCATE`, using transition tables (`NEW/OLD TABLE`) | `triggers.sql:23`,`:34`,`:45`,`:56` |
| **Revert functions** | `<schema>_<table>_revert_insert/_delete/_update` | `register_table.sql` (`create_revert_functions`) |

As the app modifies its tables, the triggers batch-record each change (block + op type +
old/new data) into the shadow table.

## The rewind (`back_from_fork.sql`)

1. hived switches forks -> records `hafd.fork` row + enqueues a `BACK_FROM_FORK` event
   (with `block_num_before_fork`).
2. The forking context consumes that event -> `context_back_from_fork(ctx, block_num_before_fork)`
   (`rewind_api.sql`) -> `back_from_fork_one_table(...)` per registered table.
3. Replay the shadow **in reverse**:
   ```sql
   FOR st IN (shadow WHERE hive_block_num > block_num_before_fork
                     ORDER BY hive_operation_id DESC)
     CASE st.hive_operation_type
       WHEN 'INSERT' THEN ..._revert_insert(st.hive_rowid)      -- delete it
       WHEN 'DELETE' THEN ..._revert_delete(st.hive_operation_id) -- re-insert from shadow
       WHEN 'UPDATE' THEN ..._revert_update(...)                  -- restore old values
   DELETE FROM shadow WHERE hive_block_num > block_num_before_fork;
   ```
   The app's tables are restored to the pre-fork state; processing resumes on the new branch.

## Bounding the log

You can never fork below an irreversible block, so when a block becomes irreversible:
- its reversible rows move to the irreversible tables, and
- `remove_obsolete_operations(shadow, irreversible_block)` (`irreversible.sql`) drops the
  shadow undo records at/below it.

So the undo log stays bounded to the reversible window (~last-irreversible distance).

## Why it matters

- **Generic** - any app table becomes fork-safe by registration; zero app fork code.
- **Cheap capture** - statement-level triggers + transition tables record once per statement,
  not per row (matters during massive sync).
- **Event-driven** - each forking context rewinds independently when it reaches the
  `BACK_FROM_FORK` event.
