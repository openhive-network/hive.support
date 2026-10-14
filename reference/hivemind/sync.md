# Hivemind: Sync Internals (cheat sheet)

Anchor `1.28.6`. Depth: findings part 03. Python: `hive/indexer/sync.py`,
`hive/indexer/blocks.py`, `hive/db/db_state.py`; SQL: `massive_sync.sql`.

## The two counters

| Counter | Source | Advanced |
|---------|--------|----------|
| last **imported** | HAF context head (`hive.app_get_current_block_num`) | by `app_next_iteration` |
| last **completed** | `hive_state.last_completed_block_num` | `update_last_completed_block` - per live range (in-tx) / at massive finalization |

Gap => finalization pending; gap > 201600 => `is_initial_massive`; gap + seed
account id=0 missing => UNLOGGED data loss (full reset + resync from 0).

## Massive batch pipeline (`Blocks.process_multi_sql`, phase-per-tx)

| # | Phase | SQL |
|---|-------|-----|
| 1 | load | `load_ops_staging(first,last)` - one `operations_view` scan (filter: see operations.md) |
| 2 | accounts + community state | `process_accounts_from_staging`, `process_community_from_staging(cs, 1)` |
| 3 | posts (waves) | `process_posts_from_staging` -> rows for Python body merge |
| 3a | community post-ops | `process_community_from_staging(cs, 2)` (skipped pre-community; muted-parent propagation deferred to fills) |
| 3.5 | votes | `process_votes_from_staging(safe_cashout)` |
| 3.6 | incremental rshares | only when indexes enabled (MASSIVE_WITH_INDEXES catch-up) |
| 4 | parallel (3 conns) | reblogs, follows, payouts - deadlock retry 3x; overlapped with Python DMP body merging |
| 4b | serialized | account_updates, lastread (all hive_accounts writers serialized) |
| 5 | flush | `PostDataCache.flush()` -> hive_post_data |
| 6 | notifications (3 conns) | post/follow/reblog flushes - only within 90-day window; VOTE notifications deferred to fills |

`safe_cashout` = LIB - 201600 once past HF17 block 10629455 (else 0).

## Live pipeline (`Blocks.process_live_block_sql`)

Same functions, sequential, **ONE transaction per range** (crash = rollback =
HAF re-serves the range). Adds: immediate `update_posts_rshares`, all 4
notification flushes, then `on_live_blocks_processed`: children count, root_id,
feed cache, `update_last_completed_block`, `prune_notification_cache`.
Periodic: every 1200 blocks (1 h) payout_stats refresh + mentions cleanup;
every 200 blocks (10 min) community rank update. The ONLY Python left in block
processing: diff-match-patch body reconstruction for comment edits.

## Crash-safety matrix

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Death mid-massive-batch | `_batch_queue` row (LOGGED) | replay batch; idempotency guards (vote num_changes, last_payout_block) |
| Death mid-live-range | - | whole-range tx rolled back; same range re-served |
| PG crash w/ UNLOGGED tables | context ahead + seed id=0 missing | truncate all, recreate context, reseed, resync from 0 |
| SIGINT/SIGTERM in massive | signal counters | rollback, skip index/FK rebuild (batch queue covers), restore WAL settings |
| Phase-4 / flush deadlock | PG 40P01 | retry parallel set 3x |
| Cross-app DDL deadlock | 40P01 during FK/index drop-restore | `_retry_ddl` 5x (other HAF apps hold read locks) |
| Stale connections | `pg_stat_activity` name `hivemind_%` | terminated at startup; leak-asserted per live range |

## Massive-mode switches

- Session: `synchronous_commit = OFF`.
- Cluster (superuser, via admin conn): `ALTER SYSTEM SET fsync=off,
  full_page_writes=off` + `pg_reload_conf()` - restored on EVERY shutdown
  path (persists in postgresql.auto.conf!). Graceful skip without superuser.
- Indexes: `hive.app_save_and_drop_indexes('hivemind_app')` (all 41); restore
  per-table in threads + `reptracker_app.account_reputations`. BM25 dropped
  manually before UNLOGGED conversion.
- Tables LOGGED<->UNLOGGED in two FK-aware phases (parallel); LOGGED-first on
  restore (BM25 can't index UNLOGGED).
- Fill queries run with `SET LOCAL work_mem = total_mem/64`.

## Finalization ("fills", `_finish_all_tables`)

1. `recalculate_all_posts_rshares` FIRST + immediate hive_posts vacuum (~54M
   dead tuples).
2. **Part 0** (parallel): feed cache, children count (full `__post_children`
   recount if initial), root_id fix (+ hard sanity check -> RuntimeError),
   last-completed catch-up; if initial: payout matview, community rank,
   `propagate_all_muted_parents`; + the **BM25 build** (~31 min hidden inside
   ~48 min Part 0).
3. **Part 1** (initial only): `clear_muted_notifications` +
   `flush_vote_notifications_for_blocks(1, head)`.
4. Reputation-score rewrite for notification types 12-15 from reptracker's
   final values (`(GREATEST(log10|rep|-9,0)*sign*7.5+25)`).
Vacuum: all tables before fills (initial), 7 hot tables after; FULL for
hive_posts/hive_post_data (note: `vacuum_table` runs VACUUM twice - looks
unintentional).

## Dead code (verified no callers)

`Reputations.flush` (inline reptracker driving), `hafapp_api.sql` legacy block
providers (`get_ops_for_hivemind`, `_v2`, `get_blocks_and_ops_for_hivemind_v2`,
`get_block_dates_for_hivemind`) - only `process_follows_for_blocks` is live
in that file.

## Mocks (test-only)

`mocker` CLI appends mock blocks/vops after an existing replayed HAF head
(requires non-empty `hafd.blocks`); env `MOCK_BLOCK_DATA_PATH`/
`MOCK_VOPS_DATA_PATH`; container path `setup --add-mocks="true"`.
