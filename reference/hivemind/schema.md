# Hivemind: Schema & Data Model (cheat sheet)

Anchor `1.28.6`. Depth: findings part 02. All tables in `hivemind_app` unless
noted. DDL: `hive/db/sql_scripts/schema/create_tables.sql`.

## Core tables (21)

| Table | Key(s) | Holds | Notes |
|-------|--------|-------|-------|
| hive_posts (~83 GB) | PK id SERIAL; UQ (author_id, permlink_id, **counter_deleted**) | tree (root/parent/depth), moderation flags, payout mirror, sc_trend/sc_hot, muted_reasons bitmask | sentinel id=0; `block_num` moves on edit, `block_num_created` doesn't; `last_payout_block` = payout replay guard |
| hive_post_data (~127 GB) | PK id = posts.id (1:1, NO FK) | title/body/json TEXT | BM25 target |
| hive_permlink_data (~27 GB) / hive_category_data / hive_tag_data | UQ text dicts (COLLATE "C") | dictionaries | id 0 = '' sentinels |
| hive_post_tags | 2 indexes, no PK | (post_id, tag_id) | UQ (tag_id, post_id DESC) added in Python |
| hive_votes (~319 GB) | PK BIGSERIAL; UQ (voter_id, author_id, **permlink_id**) | weight/rshares/vote_percent/num_changes/is_effective | vote identity = protocol triple, not (voter, post) |
| hive_accounts (~748 MB) | PK SERIAL; UQ name | haf_id (HAF bridge), follower counters, rank, lastread_at, metadata | NO reputation column |
| follows / muted / blacklisted / follow_muted / follow_blacklisted | PK (follower, following) | the 5 relationship kinds | + following & block_num indexes |
| hive_communities | PK id = community account's hive_accounts.id; UQ name | type_id 1/2/3, settings JSONB, denormalized counters | GIN FT index on title+about |
| hive_roles | PK (account_id, community_id) | role_id, title | roles: -2 muted, 0 guest, 2 member, 4 mod, 6 admin, 8 owner |
| hive_subscriptions | UQ (account_id, community_id) | membership | |
| hive_feed_cache | PK (account_id, post_id) | blog feed (own posts + reblogs) | covering (account, created DESC, post DESC) |
| hive_reblogs | UQ (blogger_id, post_id) | reblogs | its indexes NOT HAF-registered |
| hive_mentions | UQ (post_id, account_id, block_num) | @mentions | regex-extracted from bodies |
| hive_notification_cache | PK snowflake BIGINT; UQ (src,dst,type_id,post_id,block_num) | 90-day notification stream | partial (dst, score) index |
| hive_state | single row, NO PK | last_completed_block_num, db_version, version stamps | git_date type drifts fresh(TS) vs upgraded(TSTZ) |

Bookkeeping: `hive_db_patch_level` (SERIAL level + revision),
`hive_db_vacuum_needed`, `hive_db_data_migration` (upgrade-time),
`deps_saved_ddl` (view-dependency save/restore; created unqualified).

## Staging tables (massive_sync.sql)

`_batch_queue` (**LOGGED** - crash-replay marker) + UNLOGGED: `_ops_staging`
(op id/block/date/type/JSONB payload), `_comment_staging`, `_post_results`,
`_vote_batch`, `_reblog_ops`, `_reblog_final`, `_follow_notification_events`
(re-follow events the final-state tables can't express). Helper UNLOGGED
`__post_children`. Sequence `community_op_counter`. In utilities schema:
`nai_currency_map` (VESTS row says precision 3 - wrong but dormant).

## Views (all recreated at every indexer start)

| View | Shape |
|------|-------|
| live_posts_comments_view / live_posts_view / live_comments_view | posts with counter_deleted=0 / +depth=0 / +depth!=0 |
| hive_posts_base_view | minimal payout projection |
| hive_posts_parent_view | post+parent join; `parent_permlink_or_category` |
| hive_accounts_view | accounts + reptracker reputation (JOIN on haf_id; `is_grayed` = rep <= -464800000000; `account_reputations` bound via search_path) |
| hive_accounts_info_view(_lite) | + post_count (+ active_at = GREATEST(created, last post, last vote)) |
| hive_votes_view | votes + voter (with rep) + author + permlink names |
| muted_accounts_by_id_view | direct UNION transitive mutes (follow_muted -> muted) |
| payout_stats_view (MATERIALIZED) | pending payouts per (community, author) + rollups; UQ enables REFRESH CONCURRENTLY (hourly in live, at fills, on shutdown) |

**Canonical post record**: `hivemind_app.get_post_view_by_id(id)` returns the
~40-field `get_post_view_by_id_return_t` every API post object is built from
(function-local `SET join_collapse_limit = 6`). HAF-view helpers:
`head_block_time()`, `block_before_head(interval)`,
`block_before_irreversible(interval)` (3 s/block).

## Indexes & FKs

- 47 secondary indexes; heavy use of partials (`counter_deleted = 0`,
  `NOT is_paidout AND depth = 0`), expression indexes on
  `(payout + pending_payout)`, INCLUDE covering indexes.
- **41 HAF-registered** (dropped in MASSIVE_WITHOUT_INDEXES): all of
  posts/votes/feed_cache/subscriptions/follows-family/accounts.haf_id + 1
  communities + 2 notification_cache. NOT registered (always present): PKs/UQs,
  both reblogs indexes, both post_tags indexes, communities (rank,id),
  roles_ix1, the GIN FT, notification UQ. BM25 handled manually (fills phase).
- 13 FKs, all `DEFERRABLE NOT VALID`: posts(3), votes(4), post_tags(2),
  reblogs(2), mentions(2). Everything else FK-free (incl. post_data 1:1!).
- Extended statistics on 6 tables; fillfactor 90 (posts, votes); per-table
  autovacuum thresholds.

## Encodings

| Encoding | Definition |
|----------|-----------|
| Notification id | `(seconds_since_genesis << 6 \| type_id) << 22 \| counter` (type <= 63, counter <= 2^22-1); inverse `extract_from_notification_id` |
| NotifyType | 1 new_community ... 11 subscribe, 12 reply, 13 reply_comment, 14 reblog, 15 follow, 16 mention, 17 vote |
| muted_reasons bits | 0 COMMUNITY_MODERATION, 1 COMMUNITY_TYPE, 2 PARENT, 3 REPUTATION*, 4 ROLE_COMMUNITY* (*computed at read time) |
| Community type_id | 1 topic, 2 journal, 3 council |
| role_id | -2 muted, 0 guest, 2 member, 4 mod, 6 admin, 8 owner |
| NAI map | HBD @@000000013, HIVE @@000000021, VESTS @@000000037 (precision 3 - VESTS wrong, dormant) |

## Upgrade machinery

`upgrade_schema`: asserts install-time optimizer settings -> idempotent DDL
retrofits (incl. the legacy `tags_ids` -> hive_post_tags migration, which
INHERITs the table into `hive.hivemind_app` + `haf_tablespace` on upgraded DBs
only) -> optional `VACUUM FULL` when `hive_db_vacuum_needed` says so. Fresh
installs register NO tables with HAF.
