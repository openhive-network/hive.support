# HAF KB gaps found while drafting rules and evals (2026-10-14)

- **Topic**: haf
- **Type**: addition
- **Affects**: reference/haf/apps.md, forks.md, schema.md; research/haf/findings/02-fork-manager-schema.md, 03-app-development.md, 04-data-model.md, 05-forks-reversibility.md; contrib/haf/2026-07-23-expand-custom-json-type-index.md
- **Source**: HAF worktree `workspace/haf/222c848355/` (1.28.6); line references were read there by the drafting agent; the maintainer confirmed items 2 (`hived_api.sql:727/:737/:757`, `docker/cron_jobs.sql`) and 5 (`types/operation/operation_id.sql`) and applied item 6

## Description

1. **The 2026-07-23 contrib overstates its gap.** `hafd.custom_json_types` is already in
   `reference/haf/schema.md:35`, `findings/02:81`, `findings/04:46-47`, and the
   `custom_json_type_id` column in `findings/04:40` (only `reference/haf/schema.md:33` omits
   it). The real gap is `hive.create_custom_json_type_index()` plus the opt-in rationale. The
   same file also defines `hive.create_op_type_partial_index(_op_type_ids SMALLINT[])`
   (`custom_json_type_schema_update.sql:90-136`, a partial index on
   `hafd.operation_id_to_block_num(id)` WHERE `op_type_id IN (...)`) and a migration adding
   `op_type_id` to `hafd.account_operations(_reversible)` (`:138-161`) whose comment confirms
   the operation-id encoding change (the type is no longer in the low 8 bits). None of that
   is in the KB.
2. **Dead-app auto-detach is misattributed.** `findings/02` section 7 and `findings/03`
   section 5 credit "the CI job `dead_app_auto_detach`"; that is a test job
   (`.gitlab-ci.yml:1619`). The mechanism is
   `hive.proc_perform_dead_app_contexts_auto_detach(_app_timeout INTERVAL DEFAULT '4 hours')`
   (`hived_api.sql:727`; condition `last_active_at < now - timeout` at `:757`; only when
   `hive.is_instance_ready()`, `:737`; granted to `haf_maintainer`), scheduled by pg_cron
   every 30 minutes in the Docker image (`docker/cron_jobs.sql:2`, installed by
   `docker/docker_entrypoint.sh:112`). The KB also credits only `app_next_block` with the
   stamp: `app_next_iteration` stamps it too (`application_loop/loop.sql:236`),
   `hive.app_update_last_active_at()` exists as an explicit heartbeat (`app_api.sql:590`,
   `:614`), and `app_next_iteration` manages attachment itself (`loop.sql:118-135`
   `update_attachment`, `:271-278`). Rule HAF-005 already states the corrected mechanism.
3. **Non-forking contexts and triggers.** `findings/05` section 5 says "a non-forking (or
   lite) context registers no triggers/shadow tables". At the anchor `hive.register_table`
   creates the shadow table unconditionally in the full schema (`register_table.sql:262`;
   only the lite schema skips it, `:210-213`) and installs capture triggers for any attached
   context regardless of `is_forking` (`:430-432`; `create_triggers` has no gate,
   `triggers.sql:1-22`). Only the attach path skips them (`detach_table.sql:98-101`), which is
   what `app_context_set_non_forking` relies on (`app_api.sql:367-404`). So the claim holds
   only after a detach/attach cycle (possibly an upstream HAF question). Separately,
   `findings/05` hedges ("tolerate forks itself or process only irreversible data") while
   `apps.md` says irreversible-only; source confirms irreversible-only
   (`blocks_views_for_contexts.sql:200-201` `hb.num <= c.min_block`; `app_api_impl.sql:495`).
   Rule HAF-006 carries the caveat.
4. **`reference/haf/forks.md` hides the registration mechanism.** `app_register_table`
   (`app_api.sql:475-508`) adds `hive_rowid` and `ALTER TABLE ... INHERIT <ctx schema>.<ctx>`;
   the shadow table, triggers and revert functions come from `hive.register_table` fired by
   the DDL event trigger (`event_triggers.sql:77-115`, `:188-202`), and
   `CREATE TABLE ... INHERITS (ctx)` registers a table without any `app_register_table` call
   (`register_table.sql:221-223`). Reviewers grepping only for `app_register_table` miss it.
5. **Operation-id helpers are never named.** `hafd.operation_id_to_block_num()`,
   `operation_id_to_pos()`, `hafd.operation_id(block, pos)`
   (`types/operation/operation_id.sql:3,:8,:14`), and the fact that the views' `block_num` is
   computed from the id (`blocks_views_for_contexts.sql:540`) are the practical companions of
   the "id encodes block|seq" fact. Rule HAF-004 names them.
6. (applied) `reference/haf/apps.md` cited `app_get_irreversible_block(context)` as `:518`,
   which is the zero-argument overload; the context overload is at `app_api.sql:532`.

## Evidence

Line references above, in the pinned 1.28.6 worktree.
