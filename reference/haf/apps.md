# HAF Reference - Building an App

Deep detail: `findings/03-app-development.md`. An app = a context + its own (fork-managed)
tables + a pull loop. The fork manager handles reversibility; the app processes blocks
forward.

## The pattern

```sql
-- setup (once)
SELECT hive.app_create_context('my_app', _schema=>'my_app', _is_forking=>TRUE,
         _stages=>ARRAY[ hive.stage('MASSIVE',2,100), hafd.live_stage() ]);
-- create app tables, then:
SELECT hive.app_register_table('my_app','my_table','my_app');   -- fork-managed

-- loop (forever)
LOOP
  CALL hive.app_next_iteration('my_app', blocks_range);  -- or hive.app_next_block(ctx)
  -- blocks_range = (first,last) or (NULL,NULL) => no new blocks, retry
  -- read my_app.blocks_view / operations_view for [first..last]; write my_app tables
END LOOP;
```

## App API (`hive_fork_manager/app_api.sql`)

| Call | Purpose | Line |
|------|---------|------|
| `app_create_context(name, schema, [stages], is_forking, is_attached)` | create the context (starts pre-genesis) | `:22`,`:57` |
| `app_register_table(schema, table, context)` | register an app table for fork rewind | `:475` |
| `app_next_block(context)` -> `blocks_range` | next block range (function); stamps `last_active_at`; routes forking/non-forking | `:198` |
| `app_next_iteration(context, range OUT)` | next block range (procedure form, used in examples) | `application_loop/loop.sql` |
| `app_context_attach` / `app_context_detach` | resume / pause the context | `:240`,`:331` |
| `app_context_set_forking` / `_non_forking` | toggle fork rewind | `:419`,`:367` |
| `app_get_irreversible_block(context)` | the context's irreversible block | `:518` |
| `app_reset_data` / `app_remove_context` | wipe / delete | `:116`,`:92` |

## Stages (auto-scaling batches)

`hafd.application_stage = (name, min_head_block_distance, blocks_limit_in_group,
processing_alarm_threshold)` (`application_loop/stages.sql:8`). An app supplies an array;
`app_next_iteration` picks the stage by distance-to-head, so batch size scales automatically:

- far behind -> a big-batch stage (e.g. `hive.stage('MASSIVE',2,100)` = 100 blocks),
- at head -> `hafd.live_stage()` = `('live',0,1,'3s')` (one block).

`loop.sql` re-analyzes (`is_stages_analyze_required`) if the app falls behind, dropping back
to MASSIVE. Loop state in `hafd.application_loop_state` (`stages.sql:44`).

## Key behaviors

- **`(NULL,NULL)` = no new blocks** - just retry; a live app idles here between blocks.
- **`last_active_at` heartbeat** - stop calling `app_next_block` and the app is auto-detached
  (dead-app detection).
- **Massive-sync bootstrap**: detach -> bulk-load with direct inserts -> re-attach at the
  synced block (why contexts start pre-genesis).
- **Forking vs non-forking**: forking contexts get automatic fork rewind ([forks.md](forks.md));
  non-forking/lite skip the rewind machinery (cheaper, process irreversible-only).
- **Access**: only roles inheriting `hive_applications_group` may use the App API; a context
  is owned by its creating role.
