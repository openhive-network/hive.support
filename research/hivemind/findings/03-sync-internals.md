# Hivemind Part 03 - Sync Internals (Loop, Stages, Crash Safety)

**Anchor:** hivemind `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`).
**Scope:** how blocks become rows - the consume loop and stage transitions, the
massive-batch and live processing pipelines (`process_multi_sql` /
`process_live_block_sql` and the SQL functions behind them), connection topology,
crash-safety machinery (batch replay, UNLOGGED-loss recovery, WAL toggling),
massive-sync finalization ("fills"), signals/shutdown, and the mock-data tooling.
*What* each operation does to the tables (follow semantics, community ops, payout
math) is part 04; this part covers the *pipeline*.

Paths are hivemind-repo-relative, against the pinned worktree
`workspace/hivemind/cab9e328bf/`.

---

## Summary

The sync loop asks HAF for the next block range (`hive.app_next_iteration`), then
runs a staged, mostly-SQL pipeline: one scan of `operations_view` loads a filtered
staging table, then domain functions (accounts, communities, posts, votes,
reblogs, follows, payouts, notifications) consume it. Massive sync runs phases in
separate transactions with bounded parallelism and a crash-replay marker; live
sync runs the identical phases sequentially inside ONE transaction per range, so a
crash simply re-serves the range. Massive throughput comes from dropped
indexes/FKs, UNLOGGED tables, `synchronous_commit=off`, and - with superuser -
`fsync`/`full_page_writes` off via ALTER SYSTEM. A finalization pass ("fills")
recomputes everything that was deferred: rshares, children counts, root ids, feed
cache, vote notifications, reputation-corrected scores, and the BM25 index.

---

## Key Discoveries

### 1. One staging scan, 17 op types, and the HAF custom_json type filter
- **What**: `load_ops_staging(first, last)` truncates `_ops_staging` +
  `_follow_notification_events`, then INSERTs from `operations_view` filtered to
  `op_type_id IN (0,1,9,10,14,17,18,19,23,30,41,43,51,53,61,72,73)`, and for
  custom_json (18) only rows whose `custom_json_type_id` maps to
  `'follow','reblog','community','notify'` in `hafd.custom_json_types` - the HAF
  1.28.6 typed-custom_json feature (see the 2026-07-23 contrib note; index created
  at sync start, part 01 section 8). Ends with a partial `ANALYZE` that skips the
  JSONB column.
- **Where**: `hive/db/sql_scripts/massive_sync.sql:168-208`.
- **Impact**: everything downstream reads `_ops_staging`, not HAF views - the
  filter list IS hivemind's op surface (mapped op-by-op in part 04). Date
  semantics are preserved from the old Python: virtual ops (`op_type_id >= 50`)
  get the *current* block's timestamp, regular ops the *previous* block's
  (`lag()` window; `massive_sync.sql:177-193`).

### 2. Two-counter consistency: HAF context vs `hive_state.last_completed_block_num`
- **What**: "imported" = HAF context head (`hive.app_get_current_block_num`,
  `hive/indexer/blocks.py:103-110`); "completed" = hivemind's own
  `hive_state.last_completed_block_num` (`blocks.py:112-119`), advanced by
  `update_last_completed_block`
  (`hive/db/sql_scripts/update_hive_blocks_consistency_flag.sql:2-14`). Live sync
  advances it inside the same transaction as the block work
  (`blocks.py:530-536`); massive sync leaves it behind and catches it up only at
  finalization (`hive/db/db_state.py:561-566,699-702`).
- **Where**: as cited; gap check `Blocks.is_consistency` (`blocks.py:543-554`);
  finalize trigger `imported > completed` (`db_state.py:772-773`).
- **Impact**: the gap *is* the state machine: `ensure_finalize_massive_sync` fires
  on any gap; `is_initial_massive` = gap > 201600 blocks (`db_state.py:777`); and
  the UNLOGGED-loss detector uses `context ahead AND seed row missing` as its
  signature (part 01 section 9, `hive/indexer/sync.py:256-350`).

### 3. Live block ranges are single atomic transactions; massive phases are not
- **What**: `process_live_block_sql` wraps load + all processing + notifications +
  post-processing + `update_last_completed_block` in one
  `START TRANSACTION`/`COMMIT` pair on the shared connection - "if the process
  crashes, the entire block's work rolls back and app_next_iteration() returns
  the same range on restart". Massive (`process_multi_sql`) commits per phase and
  relies on the LOGGED `_batch_queue` marker (inserted atomically with the
  context advance, part 01) + idempotent SQL (vote `num_changes`,
  `last_payout_block` guards) for replay.
- **Where**: `hive/indexer/blocks.py:350-426` (live; atomicity comment 352-358);
  `blocks.py:145-348` (massive); replay `hive/indexer/sync.py:231-254`.
- **Impact**: live crash-recovery needs no marker at all; massive recovery
  replays exactly one batch. The differing transaction granularity explains why
  massive phases can deadlock (Discovery 5) and live cannot.

### 4. With superuser, massive sync turns off fsync AND full_page_writes cluster-wide
- **What**: `disable_wal_safety_for_massive_sync` saves current values, then
  `ALTER SYSTEM SET fsync='off'` + `full_page_writes='off'` + `pg_reload_conf()`
  on a dedicated admin connection (autocommit - ALTER SYSTEM can't run in a tx);
  gracefully skipped without superuser. Restored in `run()`'s live transition,
  on any stop, and the attempted-flag reset (`restore_wal_safety_after_massive_sync`).
  Justification in-code: an interrupted massive sync leaves an inconsistent DB
  that must be rebuilt anyway.
- **Where**: `hive/db/db_state.py:336-396`; call sites `hive/indexer/sync.py:191,216,447`.
- **Impact**: these persist in `postgresql.auto.conf` across PG restarts - hence
  the always-restore-on-shutdown discipline (`sync.py:443-448`). Operationally:
  a hivemind massive sync with superuser affects EVERY database in the cluster's
  crash durability, not just hivemind's tables.

### 5. Two deadlock regimes, two remedies
- **What**: (a) *Cross-app DDL*: dropping/restoring FKs and indexes needs
  AccessExclusiveLock while other HAF apps (proxy-whitelist, block explorer) hold
  read locks - `_retry_ddl` retries 5x with backoff, safe because HAF's
  save/drop/restore functions are idempotent. (b) *Intra-batch*: phase-4 tasks
  (`reblogs`, `follows`, `payouts`) run on separate connections; the three
  functions that UPDATE `hive_accounts` (follows, account_updates, lastread) are
  deliberately serialized - account_updates + lastread moved to the main thread
  AFTER the parallel set - and the whole parallel set retries up to 3x on
  PostgreSQL 40P01.
- **Where**: `hive/db/db_state.py:69-100` (a);
  `hive/indexer/blocks.py:230-306` (b), retry helper `blocks.py:464-506`.
- **Impact**: batch replay after a phase-4 retry works because "the retried batch
  will skip via idempotency guards" (`blocks.py:247-252`) - the same idempotency
  that crash replay depends on.

### 6. Finalization hides the BM25 build and ends with a reputation-score rewrite
- **What**: `_finish_all_tables` order: (1) `recalculate_all_posts_rshares` FIRST
  + immediate `hive_posts` vacuum ("creates ~54M dead tuples"); (2) "Part 0" in
  parallel - feed cache fill, children count (full recount via `__post_children`
  on initial sync, range-based otherwise), `root_id` fix with a hard sanity check
  (any `root_id = 0 AND depth = 0` post -> RuntimeError), last-completed catch-up,
  and on initial sync payout matview + community rank + accumulated muted-parent
  propagation - plus the BM25 index build ("takes ~31min but is hidden inside
  Part 0 which takes ~48min"); (3) "Part 1" (initial only) -
  `clear_muted_notifications` + `flush_vote_notifications_for_blocks(1, head)`;
  (4) a sequential UPDATE of `hive_notification_cache.score` for type_ids
  12-15 (reply/reply_comment/reblog/follow) from reptracker's final reputations
  using `score = (GREATEST(log10(|rep|) - 9, 0) * sign * 7.5 + 25)::INT`.
- **Where**: `hive/db/db_state.py:673-737` (order + comments), rshares-first
  rationale `679-689`, BM25 comment `710-713`, root_id check `515-521`,
  reputation rewrite `605-642`.
- **Impact**: the fills are where every "deferred during massive" promise is
  kept; each deferral (rshares, children, root_id, muted parents, vote
  notifications) exists because the needed index or data (payouts, final
  reputation) was missing mid-sync.

### 7. Notification flush policy differs by kind and mode
- **What**: massive batches flush post/follow/reblog notifications in parallel,
  but only for blocks inside a 90-day window
  (`block_before_irreversible('90 days')`, cached once); vote notifications are
  never flushed per-batch - their score needs payout data that arrives up to 7
  days later - so they run once at finalization. Live sync flushes all four kinds
  inline per range, then `prune_notification_cache` keeps the table bounded.
- **Where**: `hive/indexer/blocks.py:313-337` (massive; window at 319-321),
  `blocks.py:407-411` (live), pruning `blocks.py:535`, deferral rationale
  `hive/db/db_state.py:586-592`; flush functions
  `hive/db/sql_scripts/massive_sync.sql:2338-2584`.
- **Impact**: explains the README/CLAUDE.md operational rule that
  reputation_tracker must be synced *before* hivemind finishes massive sync (the
  notification cache is built at that moment, scores read reptracker state);
  final correctness is restored by the Discovery-6 score rewrite.

### 8. `Reputations.flush` is dead code at the anchor
- **What**: `hive/indexer/reputations.py:17-22` still contains a `flush()` that
  would call `reptracker_process_blocks` inline, but nothing imports or calls
  `Reputations` anywhere in the tree - reputation processing is fully delegated
  to the separately-running reputation_tracker app.
- **Where**: `hive/indexer/reputations.py` (no callers; verified by grep over
  `hive/`).
- **Impact**: hivemind only *reads* reptracker tables (views, notification
  scores) and *restores its index* after massive sync
  (`hive/db/db_state.py:294-301`); it never advances reptracker's state. (The
  wording in part 02, Key Discovery 2, has been corrected accordingly.)

---

## 1. The consume loop and stages (recap + specifics)

Part 01 section 9 has the skeleton (`hive/indexer/sync.py:94-229`). Additional
specifics:

- `run()` preamble order matters: custom_json index -> head date -> terminate
  stale `hivemind_%` backends -> `_replay_crashed_batch` -> UNLOGGED-loss check
  (`sync.py:94-110`); replay must run before per-domain connections open.
- `hive.app_next_iteration` is called with `_limit` = `--test-max-block` and
  `_override_max_batch` = `--max-batch` (`sync.py:386-412`); the psycopg2 result
  is parsed with `ast.literal_eval` and an empty range keeps looping (the
  `wait_for_haf` stage only logs a transition, `sync.py:161-164`).
- Stage names come from `hive.get_current_stage_name('hivemind_app')`
  (`sync.py:156`); unknown names abort with AssertionError after a controlled
  stop (`sync.py:227-229`).
- `--test-max-block` termination goes through the FULL finalize path: indexes
  restored, `ensure_finalize_massive_sync`, then stop (`sync.py:375-382`) - which
  is why CI test DBs are query-ready at exit (part 01 section 6.3 test flow).
- Live-transition housekeeping: when entering `live` the loop waits for the
  massive thread, re-enables synchronous_commit/indexes/WAL/FKs, closes the admin
  connection, and reopens domain connections in shared mode with a
  connection-stability wait (issue #207 workaround) (`sync.py:209-226,414-428,624-644`).

## 2. Connection topology

- Base connection + per-purpose clones, all named `hivemind_<name>`
  (`application_name`, `hive/db/adapter.py:105`) - which is what the stale-backend
  terminator and the leak assertions match on (`sync.py:580-622`).
- **Massive mode**: `Blocks.setup_own_db_access` opens a `massive_instance` clone
  (the "common block processing db") plus 13 per-domain clones (PostDataCache,
  Votes, Follow, Posts, Reblog, Notify, Accounts, Mentions, NotificationCache +
  4 notification-kind holders) (`hive/indexer/blocks.py:60-77`;
  `hive/indexer/db_adapter_holder.py:26-31,58-73`).
- **Live mode**: `DbLiveContextHolder.is_live_context()` makes every domain class
  share the MAIN connection, and `beginTx`/`commitTx` become no-ops
  (`db_adapter_holder.py:43-52`) - that is how `PostDataCache.flush()` lands
  inside the live block's wrapping transaction (`blocks.py:403-405`).
- `DbState.admin_db()` is a lazily-created clone for ALTER SYSTEM, closed when
  entering live (`db_state.py:157-171`; `sync.py:217`).
- `Db.set_max_connections` requires >= 15 available connections
  (`hive/db/adapter.py:63-89`).

## 3. The massive batch pipeline (`Blocks.process_multi_sql`)

`hive/indexer/blocks.py:145-348`; each phase logs into a `[PHASE-SUMMARY]` line.

| Phase | Tx | SQL / work | Notes |
|-------|----|-----------|-------|
| 1 load | own | `load_ops_staging(first,last)` | Discovery 1 |
| 2 accounts+community-state | own | `process_accounts_from_staging(cs)`; `process_community_from_staging(cs, 1)` | `cs` = `--community-start-block` |
| 3 posts | own | `process_posts_from_staging(cs)` returns `post_staging_result` rows | wave algorithm, section 5 |
| 3a community post-ops | own | `process_community_from_staging(cs, 2)` | skipped before community start; muted-parent propagation deferred to finalization (recursive CTE would seq-scan without the parent_id index; comment `blocks.py:188-194`) |
| 3.5 votes | own (Votes conn) | `process_votes_from_staging(last_safe_cashout)` | rshares deferred on initial sync |
| 3.6 incremental rshares | - | `update_posts_rshares(post_ids)` for the batch's voted posts | ONLY when indexes enabled, i.e. `MASSIVE_WITH_INDEXES` catch-up (`blocks.py:210-228`) |
| 4 parallel | 3 conns | reblogs, follows, payouts | deadlock retry 3x; overlapped with Python 3b |
| 3b body merge | main thread | `_process_post_results_for_cache` | section 5 |
| 4b serialized | own | `process_account_updates_from_staging`; `process_lastread_from_staging` | after follows - all three UPDATE `hive_accounts` (`blocks.py:234-239`) |
| 5 flush | PostDataCache conn | `PostDataCache.flush()` | batched INSERT into `hive_post_data` |
| 6 notifications | 3 conns | `flush_{post,follow,reblog}_notifications_for_blocks` | 90-day window; votes deferred (Discovery 7) |

`_last_safe_cashout_block` (used by votes/payouts phases) = LIB - 201600 once LIB
is past HF17's block 10629455, else 0 - pre-HF17 posts "could stay unpaid
forever" (`blocks.py:132-143`; HF17 cashout unification: hive-core KB
`reference/hardforks.md`).

## 4. The live pipeline (`Blocks.process_live_block_sql`)

Same functions, sequential, one transaction (`blocks.py:350-426`): load ->
accounts -> community(1) -> posts -> body merge -> votes -> immediate
`update_posts_rshares` (API needs current values) -> reblogs -> follows ->
account_updates -> lastread -> payouts -> community(2) -> PostDataCache flush ->
all four notification flushes -> `on_live_blocks_processed` -> periodic actions ->
COMMIT.

`on_live_blocks_processed` (`blocks.py:522-541`): `update_hive_posts_children_count`,
`update_hive_posts_root_id`, `update_feed_cache`, `update_last_completed_block`,
`prune_notification_cache` - per range, every iteration. Periodic extras
(`blocks.py:508-520`): every 1200 blocks (1 h) refresh `payout_stats_view` +
`Mentions.refresh()`; every 200 blocks (10 min) `update_communities_posts_and_rank`.

## 5. The posts wave algorithm and the Python remnant

`process_posts_from_staging` (`hive/db/sql_scripts/massive_sync.sql:972-1650`)
returns `post_staging_result` (type at `:954-970`) and works in steps: collect
"ineffective delete" keys (op 73); stage comment ops with an `is_first` flag per
(author, permlink); then **wave-based resolution** - "each wave resolves one
level of parent-child dependency" (`:1067-1068`), so replies created in the same
batch as their parents insert in dependency order; delete/re-create cycles are
tracked via the original staging id (`_comment_staging.staging_id`,
`massive_sync.sql:39`).

The ONLY Python left in block processing is body reconstruction
(`blocks.py:147-150` "Only PostDataCache body merging remains in Python"):
`_process_post_results_for_cache` stores full title/body/json for new posts and
for edits applies **diff-match-patch** patches to the previous body
(`blocks.py:428-462`; `hive/indexer/posts.py:20-29` `patch_apply`) - comment
edits on Hive may carry DMP patches instead of full bodies (part 04). The cache
then bulk-INSERTs into `hive_post_data` (`hive/indexer/post_data_cache.py:52-130`).

## 6. Crash-safety matrix

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Process dies mid-massive-batch | `_batch_queue` row exists at startup | Replay the range via `process_multi_sql`; idempotency guards absorb double-processing (`sync.py:231-254`) |
| Process dies mid-live-range | nothing persisted | The whole range's tx rolled back; `app_next_iteration` re-serves it (`blocks.py:352-358`) |
| PostgreSQL crash while tables UNLOGGED | context ahead of completed AND seed account id=0 missing | Truncate all data+staging tables, remove/recreate context, reseed, resync from 0 (`sync.py:256-350`) |
| SIGINT/SIGTERM during massive | `FINISH_SIGNAL_DURING_SYNC` counter | Rollback, wait for the massive thread, skip index/FK rebuild (batch queue covers replay), restore WAL settings (`sync.py:364-373,443-465`) |
| Exception in the massive thread | future re-raises in `_wait_for_massive_consume` | Cleared future so shutdown path runs with `sigint_during_massive=True` (`sync.py:132-144`) |
| Phase-4 / parallel-flush deadlock | psycopg2 `TransactionRollbackError` (40P01) | Retry whole parallel set up to 3x (`blocks.py:253-298,464-506`) |
| DDL deadlock with other HAF apps | same error class | `_retry_ddl` 5x with 1s*attempt backoff (`db_state.py:69-100`) |
| Stale connections from a crashed run | `pg_stat_activity` names `hivemind_%` | `pg_terminate_backend` at startup + post-range leak assertions (`sync.py:580-622`) |

Signals: SIGINT/SIGTERM increment an `AtomicCounter`; `can_continue_thread()`
gates every loop iteration; handlers print "PLEASE WAIT... PROCESSING DATA IN
QUEUES" and default handlers are restored before shutdown
(`hive/signals.py:33-76`; `sync.py:59,364-373`).

## 7. Stage-support machinery (indexes, FKs, memory)

- Index drop: single `hive.app_save_and_drop_indexes('hivemind_app')`
  (`db_state.py:220-228`); restore: per-table `hive.app_restore_indexes` across
  the 12 registered tables in threads, **plus
  `reptracker_app.account_reputations`** (`db_state.py:230-243,281-303` - list
  of tables at `:45-58`).
- BM25 handled outside HAF registration: dropped explicitly before UNLOGGED
  conversion, created in the fills (Discovery 6; `db_state.py:399-416,245-270`).
- LOGGED->UNLOGGED and back via `set_logged_table_attribute` (part 02;
  LOGGED-first before index restore because BM25 can't index UNLOGGED tables,
  `db_state.py:448-453`).
- FKs: `hive.app_save_and_drop_foreign_keys` / `app_restore_foreign_keys` over
  the 5 FK tables (`db_state.py:419-484`).
- Heavy fill queries run with `SET LOCAL work_mem = total_mem/64 MB` and assert
  the setting took effect and reverted (`db_state.py:192-217`).
- Vacuum policy: initial massive vacuums ALL `hivemind_app` base tables, then
  after fills vacuums 7 hot tables again; `hive_posts`/`hive_post_data` get
  `VACUUM FULL` - and note each table is actually vacuumed twice in
  `vacuum_table` (FULL-or-plain, then plain again; `db_state.py:739-769,779-795`).

## 8. Mock-data tooling (test-only)

`mocker` (console script, part 01) is a separate CLI: it requires an existing
replayed HAF DB (aborts if `hafd.blocks` is empty -
`hive/indexer/mocking/populate_haf_with_mocked_data.py:96-103`), loads JSON mock
files (`MOCK_BLOCK_DATA_PATH` / `MOCK_VOPS_DATA_PATH`, same env vars the sync
loop also accepts, `hive/conf.py:107-119`) and appends mock blocks/vops
continuing after the DB head (`mock_block.py` `BlockMock`/`BlockMockAfterDb`,
providers in `mock_block_provider.py`/`mock_vops_provider.py`). The container
path is `setup --add-mocks="true"` -> `ci/add-mocks-to-db.sh` (part 01 section 6.1).
Mock content itself (what ops the files inject for tests) is out of scope here.

---

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Massive batch pipeline | hive/indexer/blocks.py | 145-348 | Phases, parallelism, deadlock retry, 90-day window |
| Live pipeline (atomic) | hive/indexer/blocks.py | 350-426 | One tx per range; inline rshares + notifications |
| Live post-processing | hive/indexer/blocks.py | 508-541 | children/root_id/feed/completed/prune + periodic 1200/200 |
| Body merge (Python remnant) | hive/indexer/blocks.py | 428-462 | New vs DMP-patched edits |
| DMP patch apply | hive/indexer/posts.py | 20-29 | diff-match-patch body reconstruction |
| PostDataCache flush | hive/indexer/post_data_cache.py | 52-130 | Batched INSERT into hive_post_data |
| Counters (imported/completed) | hive/indexer/blocks.py | 97-119 | HAF context vs hive_state |
| Safe-cashout threshold | hive/indexer/blocks.py | 132-143 | LIB - 201600 after HF17 block 10629455 |
| Staging load + op filter | hive/db/sql_scripts/massive_sync.sql | 168-208 | 17 op types; custom_json_type_id filter; date semantics |
| Posts wave algorithm | hive/db/sql_scripts/massive_sync.sql | 949-1650 | post_staging_result; waves; delete-create cycles |
| Notification flush fns | hive/db/sql_scripts/massive_sync.sql | 2338-2584 | vote/post/follow/reblog + reputation_score |
| Muted-parent propagation | hive/db/sql_scripts/massive_sync.sql | 2240-2332 | Batch fn (deferred) + propagate_all_muted_parents |
| update_last_completed_block | hive/db/sql_scripts/update_hive_blocks_consistency_flag.sql | 2-14 | Advances hive_state |
| get_head_state | hive/db/sql_scripts/utility_functions.sql | 74-99 | context_data_view + blocks_view |
| Consume loop | hive/indexer/sync.py | 94-229 | Stages, batch queue, transitions (part 01 recap) |
| Crash replay | hive/indexer/sync.py | 231-254 | _batch_queue replay |
| UNLOGGED-loss recovery | hive/indexer/sync.py | 256-350 | Detect + full reset |
| Connection hygiene | hive/indexer/sync.py | 580-644 | Terminate stale; leak assertions; stability wait |
| DDL deadlock retry | hive/db/db_state.py | 69-100 | Cross-app AccessExclusive contention |
| Index drop/restore | hive/db/db_state.py | 220-243,281-312 | HAF-managed + reptracker index restore |
| WAL toggling | hive/db/db_state.py | 336-396 | ALTER SYSTEM fsync/full_page_writes |
| Index/FK ensure fns | hive/db/db_state.py | 399-484 | UNLOGGED ordering, FK save/restore |
| Fills orchestration | hive/db/db_state.py | 673-737 | rshares-first, Part 0/1, BM25 overlap |
| Finish helpers | hive/db/db_state.py | 486-642 | posts/feed/payout/communities/muted/vote-notifs/rep scores |
| Finalize trigger + vacuum | hive/db/db_state.py | 739-800 | is_initial_massive; vacuum policy |
| Signals | hive/signals.py | 33-76 | AtomicCounters, graceful handlers |
| Adapter holder / live sharing | hive/indexer/db_adapter_holder.py | 8-73 | Shared-conn live mode; massive_instance |
| Dead code: inline reptracker | hive/indexer/reputations.py | 13-22 | flush() has no callers |
| Mocker entry | hive/indexer/mocking/populate_haf_with_mocked_data.py | 96-103 | Requires replayed HAF; appends mocks |

## Cross-references to existing parts

- **Part 01** sections 8-9: context/stages creation, the loop skeleton, batch
  queue atomicity comment, healthcheck marker.
- **Part 02**: staging DDL (section 2), `_batch_queue` LOGGED rationale,
  registered-index list, UNLOGGED conversion, `__post_children`,
  `payout_stats_view`, notification snowflake + `NotifyType` (12-15 = the
  reputation-corrected kinds). Part 02's Key Discovery 2 wording on
  `Reputations.flush` is corrected by Discovery 8 here.
- **HAF KB part 03**: `app_next_iteration`, stages, `app_save_and_drop_indexes`,
  `app_save_and_drop_foreign_keys`, context views.
- **hive-core KB**: HF17 (block 10629455) cashout unification
  (`reference/hardforks.md`); op type ids for the staging filter (part 04 will
  map all 17); payout virtual ops (`reference/operations.md`).

## Open Questions (for later parts)

- Part 04: map the 17 staged op_type_ids to protocol operations and their
  handlers (`process_accounts_from_staging`, `process_community_op`,
  vote/payout SQL, follow ops incl. `_follow_notification_events` consumers);
  `legacy_amount`/`sbd_amount` JSONB asset parsing
  (`massive_sync.sql:890-948`); the ineffective-delete (op 73) semantics;
  community op validation helpers (`_validate_json_keys` etc.,
  `massive_sync.sql:1658-1727`).
- Part 04/07: `prune_notification_cache` retention math and
  `clear_muted_notifications` semantics.
- Upstream-worthy observations: `Reputations.flush` dead code; the double
  `VACUUM` in `vacuum_table` (`db_state.py:744-748`) looks unintentional;
  `hafapp_api.sql`'s legacy block-provider functions (`get_ops_for_hivemind`,
  `get_ops_for_hivemind_v2`, `get_blocks_and_ops_for_hivemind_v2`,
  `get_block_dates_for_hivemind`; `hafapp_api.sql:10-52,509-650`) are superseded
  by `load_ops_staging` and have no callers in either the Python tree or the SQL
  scripts (verified by grep) - only `process_follows_for_blocks` (`:54`) is live
  in that file.
