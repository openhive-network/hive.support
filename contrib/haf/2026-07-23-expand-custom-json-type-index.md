# HAF 1.28.6 custom_json type indexing is not covered by the HAF KB

- **Topic**: haf
- **Type**: addition
- **Affects**: reference/haf/schema.md, reference/haf/apps.md, research/haf/findings/02-fork-manager-schema.md, research/haf/findings/04-data-model.md
- **Source**: haf worktree `workspace/haf/222c848355/src/hive_fork_manager/custom_json_type_schema_update.sql` (whole file); observed consumer: hivemind 1.28.6

## Description

While bootstrapping the hivemind KB topic (anchored hivemind `1.28.6`, which pairs
with HAF `1.28.6` = the HAF KB anchor `222c848355`), I found a HAF schema/app-API
feature that the HAF KB never mentions:

1. **`hafd.custom_json_types` table** - `id SMALLINT IDENTITY` +
   `custom_json_id VARCHAR(32) UNIQUE` (custom_json_type_schema_update.sql:6-9),
   registered for `pg_extension_config_dump` (line 11).
2. **`custom_json_type_id SMALLINT` column** added to BOTH `hafd.operations` and
   `hafd.operations_reversible` (lines 13-28). This is a data-model change to the
   core operations tables - findings part 04 / reference schema.md list operations
   columns and do not include it.
3. **`hive.create_custom_json_type_index(_custom_json_ids TEXT[])`** - a
   SECURITY DEFINER function (so plain app roles can index `hafd.operations`,
   comment lines 37-38) that creates a deterministic partial index
   `hive_operations_custom_json_types_<ids>_idx ON hafd.operations
   (custom_json_type_id) WHERE custom_json_type_id IN (...)` (lines 39-80). No
   generic index is created by default, deliberately - apps opt in per type to
   avoid indexing high-volume ids like Splinterlands (comment lines 30-33).

There is presumably also serializer-side population of `custom_json_type_id` and
the `hafd.custom_json_types` dictionary during sync (not traced yet - the file
above is the migration/API side; worth verifying where the column gets filled,
likely sql_serializer C++ or the massive-sync dumpers).

## Evidence

- HAF side (at the KB's own anchor `222c848355`):
  `src/hive_fork_manager/custom_json_type_schema_update.sql:6-9` (table),
  `:13-28` (columns), `:39-80` (function).
- Real consumer: hivemind 1.28.6 calls
  `SELECT hive.create_custom_json_type_index(ARRAY['follow','reblog','community','notify'])`
  at sync startup (hivemind `hive/indexer/hive_db/haf_functions.py:9,39-48`,
  invoked from `hive/indexer/sync.py:95-98`).
- KB check: `grep -rn create_custom_json_type_index reference/haf/
  research/haf/findings/` returns nothing; `custom_json_type` likewise absent.

Suggested incorporation: add the table + column to the data-model docs, and the
function to the app-development surface (alongside `app_register_index_dependency`
and friends), noting the SECURITY DEFINER rationale and the opt-in indexing design.
