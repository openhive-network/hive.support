# HAF Part 03 - App Development & the Application Loop

**Anchor:** HAF `1.28.6` (`222c848355`).
**Scope:** how you build a HAF app - the context lifecycle (create / attach / detach),
the block-consume loop (`app_next_block` / `app_next_iteration`), and the **stages** state
machine that auto-scales batch size by distance to head. Builds on the schema (part 02);
the views an app reads are part 04, the fork rewind it relies on is part 05.

Paths relative to `src/hive_fork_manager/`.

---

## 1. The app model

A HAF app is: **a context + its own tables + a process loop**. The app pulls block ranges
from HAF at its own pace, reads the context's auto-generated views, and writes derived
data into its own (fork-managed) tables. HAF handles reversibility and fork rewind; the
app just processes blocks forward.

Canonical shape (from `doc/examples/hive_fork_app.py`):

```python
# setup (once)
if not app_context_exists(CTX):
    app_create_context(CTX, _schema=>'applications', _is_forking=>TRUE,
                       _stages=>ARRAY[ hive.stage('MASSIVE',2,100), hafd.live_stage() ])
    create + app_register_table(...)            # app tables, fork-managed
    create app processing functions

# loop (forever)
while True:
    with transaction:
        CALL hive.app_next_iteration(CTX, blocks_range)   # -> (first, last) or (NULL,NULL)
        if blocks_range is (None,None): continue
        process blocks [first..last]  via context views -> app tables
```

---

## 2. Creating a context

`hive.app_create_context` (`app_api.sql:22`):

```sql
app_create_context(_name, _schema, _is_forking BOOLEAN = TRUE, _is_attached BOOLEAN = TRUE)
-- overload (app_api.sql:57) adds: _stages hafd.application_stages
```

- It starts the context at **block before genesis** (the app processes from block 1), with
  the current `fork_id` and the head irreversible block (`app_api.sql:39-49`).
- Then it builds the context's views (`app_create_views_for_contexts`, `:51`) and logs
  `CREATED`.
- `_is_forking` chooses whether the context rewinds on forks (forced FALSE in lite mode,
  `:34-37`); `_is_attached` whether it starts live.

After creating the context, an app `app_register_table`s its tables (part 02) so they get
shadow tables + rewind triggers.

---

## 3. The consume loop

Two equivalent entry points return a `hive.blocks_range`:

| API | Form | `app_api.sql` / `loop.sql` |
|-----|------|----------------------------|
| `hive.app_next_block(context)` | FUNCTION -> `blocks_range` | `app_api.sql:198`,`:228` |
| `hive.app_next_iteration(context, blocks_range OUT, ...)` | PROCEDURE (used in the example) | `application_loop/loop.sql` |

`app_next_block` (`app_api.sql:198-224`):
1. `app_check_contexts_synchronized` - all contexts must be at the same position.
2. **`UPDATE hafd.contexts SET last_active_at = NOW()`** (`:210-212`) - marks the app alive
   so the dead-app detector won't auto-detach it.
3. Reads the sync state, then routes to **`app_next_block_forking_app`** vs
   **`app_next_block_non_forking_app`** (`:218-223`): the forking path runs only when the
   context is forking, not in lite mode, and either sync is `LIVE` or pruning is off -
   otherwise the cheaper non-forking path.

Each call returns the next `(first_block, last_block)` to process, or `(NULL, NULL)` when
no new blocks are available yet (the loop just retries). The app reads that range from its
context views and writes to its tables, all in one transaction.

---

## 4. The stages state machine

Stages let one app process **fast when behind, carefully when live**.

`hafd.application_stage` (`application_loop/stages.sql:8`):

| Field | Meaning |
|-------|---------|
| `name` | stage name |
| `min_head_block_distance` | minimum distance-to-head at which this stage applies |
| `blocks_limit_in_group` | max blocks returned per iteration in this stage |
| `processing_alarm_threshold` | warn if an iteration runs longer than this |

Built-ins: `hafd.live_stage()` = `('live', 0, 1, '3 seconds')` (`:15`) - at head, **one block
at a time**; `hafd.wait_for_haf_stage()` = distance `INT_MAX` (`:26`) - park until HAF has
data. An app supplies an **array** of stages (`hafd.application_stages`, `:42`); the example
uses `ARRAY[ hive.stage('MASSIVE',2,100), hafd.live_stage() ]` - i.e. when >= 2 blocks
behind, batch up to 100 blocks; once at head, 1 block per iteration.

The chosen stage and batch live in `hafd.application_loop_state` (`:44`): `current_stage`,
`end_block_range`, `size_of_blocks_batch`, `current_batch_end`,
`last_analyze_distance_to_head_block`, `last_shadow_vacuum_block`. `loop.sql` drives it -
`analyze_stages` picks the stage for the current distance, `is_stages_analyze_required`
re-analyzes when the app falls behind (so a stalled app drops back to MASSIVE), and
`app_next_iteration` returns the next batch.

> So batch sizing is automatic: the same loop bulk-syncs history and then settles into
> per-block live processing, switching purely on distance to head.

---

## 5. Context lifecycle

| Operation | API | Effect |
|-----------|-----|--------|
| Attach / detach | `app_context_attach` / `app_context_detach` (`app_api.sql:240`,`:331`) | pause/resume advancing the context |
| Set forking mode | `app_context_set_forking` / `app_context_set_non_forking` (`:419`,`:367`) | whether it rewinds on forks |
| Irreversible head | `app_get_irreversible_block` (`:518`) | the context's irreversible block |
| Reset / remove | `app_reset_data` / `app_remove_context` (`:116`,`:92`) | wipe / delete |

**Massive-sync pattern** (`app_api.sql:39-40`): an app may **detach** its context, bulk-load
history with direct inserts (no per-block fork overhead), then **re-attach** at the last
synced block and continue live. This is why a context starts pre-genesis and tracks its own
block cursor.

**Dead-app auto-detach**: because `app_next_block` stamps `last_active_at`, an app that
stops calling it is detected and auto-detached (the CI job `dead_app_auto_detach`), so a
dead app's reversible data and triggers don't pin the whole database.

---

## 6. Reading block data

Within a returned range, the app queries its context's **auto-views**
(`{context_schema}.{blocks|transactions|operations|...}_view`, part 02) - which transparently
merge reversible + irreversible rows for that context's fork position - and writes results
to its registered tables. The example reads `applications.blocks_view` (`hive_fork_app.py:29`).
View internals and the per-operation data are part 04.

---

## 7. Notable findings

1. **One loop, auto-scaling batches.** Stages turn distance-to-head into batch size; the
   same code path does massive history sync and live per-block processing
   (`stages.sql`, `loop.sql`).
2. **`app_next_block` is the heartbeat.** It both returns work and stamps `last_active_at`;
   not calling it is how HAF knows an app died.
3. **Forking vs non-forking is chosen per call** (`app_api.sql:218`) - a non-forking or
   lite-mode context skips the fork machinery entirely (cheaper, no rewind).
4. **Detach-massive-sync-reattach** is the supported fast-bootstrap path for a new app, and
   the reason contexts start pre-genesis.
5. **`(NULL, NULL)` means "no blocks yet"**, not an error - the loop simply retries; live
   apps spend most time here between 3-second blocks.

---

## 8. Code References

| Topic | File:line |
|-------|-----------|
| app_create_context (+ stages overload) | `app_api.sql:22-55`,`:57` |
| app_next_block (forking/non-forking routing) | `app_api.sql:198-224`,`:218-223` |
| last_active_at stamp | `app_api.sql:210-212` |
| app_next_iteration + loop logic | `application_loop/loop.sql` (`analyze_stages`, `app_next_iteration`, `get_current_stage_name`) |
| application_stage + built-in stages | `application_loop/stages.sql:8`,`:15`,`:26` |
| application_stages / application_loop_state | `application_loop/stages.sql:42`,`:44` |
| attach / detach / forking mode | `app_api.sql:240`,`:331`,`:419`,`:367` |
| Example app (setup + loop) | `doc/examples/hive_fork_app.py:53-93` (stages at `:59`) |

---

## 9. Open Questions (for later parts / zoom)

- **`app_next_iteration` internals** - the exact stage-analysis / batch-end arithmetic in
  `loop.sql` (`analyze_stages`, `app_next_iteration`) is a zoom candidate.
- **The context views** (`blocks_view`/`operations_view`/...) and the per-operation/column
  data they expose - part 04.
- **What "forking path" does on a fork** (`app_next_block_forking_app` -> rewind) - part 05.
- **`wait_for_haf` / sync-state coupling** - how an app blocks until HAF has data.
- **Non-SQL app tooling** - the Python/`test_tools` helpers that wrap this loop (the
  examples are raw SQL); whether a supported app SDK exists.
