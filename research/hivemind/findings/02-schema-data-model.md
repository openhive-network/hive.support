# Hivemind Part 02 - Schema & Data Model

**Anchor:** hivemind `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`).
**Scope:** everything that lives in the database - the `hivemind_app` tables (core,
bookkeeping, staging), views and the canonical post record, the index strategy
(incl. HAF-managed drop/restore registration), foreign keys, id/enum encodings, and
the upgrade machinery. How rows get *written* is part 03 (sync flow) / part 04
(operation semantics); how they are *read* is parts 05-07 (API).

Paths are hivemind-repo-relative, against the pinned worktree
`workspace/hivemind/cab9e328bf/`. Table DDL cites
`hive/db/sql_scripts/schema/create_tables.sql` (below: `create_tables.sql`).

---

## Summary

`hivemind_app` holds 21 core tables (`create_tables.sql`) plus bookkeeping and
staging tables created elsewhere. The model is aggressively denormalized for read
speed: dictionary tables (permlink/category/tag) shrink hot rows, `hive_posts` is
split from its bulky text (`hive_post_data`), counters (followers, children,
subscribers, rank) are materialized into columns, and 47 secondary indexes - many
partial or on expressions - serve the ranking queries directly. 41 of those
indexes are registered with HAF for drop/restore around massive sync; FKs exist
only on 6 tables and are `DEFERRABLE NOT VALID`. Reputation is deliberately NOT
stored: it joins in from reputation_tracker at view level via a `search_path`
trick at code-deploy time.

---

## Key Discoveries

### 1. The whole SQL API is redeployed on every indexer start, binding the reptracker schema via search_path
- **What**: `DbState.initialize` always ends with `SET SEARCH_PATH TO
  {REPTRACKER_SCHEMA_NAME}` + `SET custom.swagger_url = ...` and then re-runs
  `setup_runtime_code` (the ~120-script list) - so all views/functions are
  dropped/recreated at each `hive sync`/`build_schema` start, and the unqualified
  `account_reputations` reference in `hive_accounts_view` binds to the configured
  reptracker schema *at CREATE VIEW time*.
- **Where**: `hive/db/db_state.py:136-138`; `hive/db/sql_scripts/hive_accounts_view.sql:17`
  (comment "schema needs to be removed to support custom schema"); option plumbed
  from `--reptracker-schema-name` (`hive/conf.py:206-207`).
- **Impact**: schema objects are versionless runtime artifacts - only *tables* are
  migration-managed. Anyone inspecting a live DB sees view/function definitions of
  whatever binary last started, and the reptracker schema name is frozen into view
  definitions, not looked up per query.

### 2. Reputation and account identity: two id spaces bridged by `haf_id`
- **What**: `hive_accounts.id` is hivemind's own SERIAL; `haf_id` stores HAF's
  account id. `hive_accounts_view` LEFT JOINs reptracker's `account_reputations`
  ON `ar.account_id = ha.haf_id`, exposing `reputation`, `is_implicit`, and
  `is_grayed` (`reputation <= -464800000000`, "biggest number where rep_log10
  gives < 1.0").
- **Where**: `create_tables.sql:5-18`; `hive/db/sql_scripts/hive_accounts_view.sql:4-17`.
- **Impact**: every reputation-aware query pays a cross-app join keyed on haf_id;
  hivemind never writes or advances reputation state (a leftover
  `Reputations.flush` that would call `reptracker_process_blocks` inline exists
  at `hive/indexer/reputations.py:17-22` but has no callers - part 03, Key
  Discovery 8).

### 3. Post identity allows permlink reuse: `counter_deleted` is part of the unique key
- **What**: `hive_posts` uniqueness is `(author_id, permlink_id, counter_deleted)`;
  deleted posts keep their row (counter bumped), and the "live" subset is always
  `counter_deleted = 0` - encoded in the `live_posts_comments_view` family and in
  nearly every partial index predicate.
- **Where**: `create_tables.sql:70`; `hive/db/sql_scripts/hive_posts_view.sql:1-5`.
- **Impact**: joins that forget the `counter_deleted = 0` filter silently include
  deleted revisions; the sentinel row `id = 0` (part 01, seed data) must also be
  excluded (`hp.id <> 0` appears in views/matviews).

### 4. 41 indexes are HAF-managed (dropped during massive sync); the exceptions are deliberate
- **What**: `register_indexes.sql` registers 41 index-creation statements via
  `hive.app_register_index_dependency` (SECURITY DEFINER). NOT registered - hence
  always present: all PKs/unique constraints, both `hive_reblogs` indexes, both
  `hive_post_tags` indexes, `hive_communities_ix1 (rank, id)`, `hive_roles_ix1`,
  the `hive_notification_cache` unique index, and the communities GIN FT index.
  The BM25 index is explicitly excluded because pg_search leaves a MetaPage that
  blocks UNLOGGED conversion - it is created directly in the massive-sync
  finalize ("fills") phase instead.
- **Where**: `hive/db/sql_scripts/schema/register_indexes.sql:1-64` (BM25 note at
  59-61); deferred BM25 creation `hive/db/db_state.py:245-270`.
- **Impact**: during `MASSIVE_WITHOUT_INDEXES` the surviving indexes are exactly
  the constraint set + the unregistered ones; a schema reader can tell which
  indexes exist mid-sync from this list alone (cross-ref HAF KB part 03 for the
  stage machinery).

### 5. Notification ids are snowflakes; the cache is capped by score and time
- **What**: `hive_notification_cache.id` = `(seconds_since_hive_genesis << 6 |
  type_id) << 22 | counter` (type_id <= 63, counter <= 4194303 = 2^22-1), built by
  `hivemind_app.notification_id()` with an `extract_from_notification_id` inverse.
  17 active notification types are defined in Python (`NotifyType`, values 1-17).
- **Where**: `hive/db/sql_scripts/utility_functions.sql:120-133` (genesis fn at
  101); `hive/indexer/notify_type.py:4-25`; example producer
  `hive/db/sql_scripts/massive_sync.sql:1602-1611`.
- **Impact**: ids sort chronologically and are collision-free per (second, type)
  up to 4.19M events; the `community_op_counter` sequence
  (`massive_sync.sql:9`) feeds the counter for community ops.

### 6. The NAI map hardcodes VESTS precision 3 (protocol says 6) - currently dormant
- **What**: `hivemind_postgrest_utilities.nai_currency_map` seeds
  `('VESTS','@@000000037', 3)`; protocol VESTS precision is 6 (hive-core KB,
  `reference/operations.md` assets). The only `to_nai` call sites format post
  payout fields (`curator_payout_value`, `total_payout_value`,
  `max_accepted_payout`), which are HBD-denominated strings - so the VESTS row is
  never exercised today.
- **Where**: `hive/db/sql_scripts/postgrest/utilities/assets_operations.sql:11`
  (map), `:15` (`to_nai`), `:41` (`parse_asset`); call sites
  `postgrest/utilities/create_database_post_object.sql:49-53`.
- **Impact**: latent bug if any future endpoint converts VESTS through this map;
  worth an upstream note but harmless at the anchor.

### 7. Fresh installs register NO tables with HAF; one legacy migration branch does
- **What**: no `INHERITS (hive.hivemind_app)` anywhere in `create_tables.sql` -
  consistent with the non-forking (irreversible-only) context, which needs no undo
  log. The only `INHERIT` is inside the legacy `tags_ids` migration
  (`ALTER TABLE hivemind_app.hive_post_tags INHERIT hive.hivemind_app`,
  executed only if the pre-1.28 `hive_posts.tags_ids` column exists; also uses
  `TABLESPACE haf_tablespace`).
- **Where**: `hive/db/sql_scripts/upgrade/upgrade_runtime_migration.sql:9-36`
  (INHERIT at 31, tablespace at 28).
- **Impact**: on databases upgraded from the old schema, `hive_post_tags` is a
  HAF-registered table (gains `hive_rowid`,
  `upgrade/upgrade_table_schema.sql:33-41`) while everything else is not - a
  real fresh-vs-upgraded divergence to expect when inspecting deployments.

---

## 1. Core tables (`create_tables.sql`)

21 tables. Sizes below are the production magnitudes recorded in code comments
(`hive/db/schema.py:436-449`).

### 1.1 Posts cluster

| Table | Lines | Keys | Notes |
|-------|-------|------|-------|
| `hive_posts` (~83 GB) | 21-88 | PK `id` SERIAL; UNIQUE `(author_id, permlink_id, counter_deleted)` | The hot row: tree links (`root_id`, `parent_id`, `depth`), dictionary FKs, community/moderation state, payout mirror, ranking scores |
| `hive_post_data` (~127 GB) | 91-96 | PK `id` (= `hive_posts.id`, 1:1, **no FK**) | `title VARCHAR(512)`, `body TEXT`, `json TEXT` - the bulk split out of `hive_posts`; BM25 target |
| `hive_permlink_data` (~27 GB) | 100-104 | PK; UNIQUE `permlink` (VARCHAR(255) COLLATE "C") | Dictionary |
| `hive_category_data` | 107-111 | PK; UNIQUE `category` | Dictionary |
| `hive_tag_data` (~12 GB with post_tags) | 142-146 | PK; UNIQUE `tag` (VARCHAR(64)) | Dictionary; id 0 = '' sentinel |
| `hive_post_tags` | 135-139 | none (heap) + 2 indexes | `(post_id, tag_id)` pairs; btree `(post_id, tag_id)` here + UNIQUE `(tag_id, post_id DESC)` added in Python (`hive/db/schema.py:177-181`) |

`hive_posts` column semantics worth knowing (lines 21-70): `counter_deleted`
(see Key Discovery 3); `muted_reasons INTEGER` bitmask (section 6);
`is_muted/is_valid/is_pinned/is_hidden/is_nsfw/is_declined/is_full_power`
moderation & payout flags; payout mirror columns - `payout`/`pending_payout
DECIMAL(10,3)`, `payout_at/last_payout_at/cashout_time`, `is_paidout`,
`author_rewards{,_hive,_hbd,_vests} BIGINT`, legacy formatted strings
`total_payout_value`/`curator_payout_value`/`max_accepted_payout VARCHAR(30)`
(defaults `'0.000 HBD'`, `'1000000.000 HBD'`), `percent_hbd` default 10000;
vote aggregates `abs_rshares`/`vote_rshares NUMERIC`, `total_vote_weight`,
`total_votes`/`net_votes BIGINT`; ranking `sc_trend`/`sc_hot REAL`;
`beneficiaries JSON` default `[]`; provenance `block_num` vs `block_num_created`;
`last_payout_block` (payout idempotency high-water mark for crash replay, also
retrofitted by `upgrade/upgrade_table_schema.sql:52`).

### 1.2 Votes

`hive_votes` (~319 GB; lines 114-132): PK BIGSERIAL; **UNIQUE `(voter_id,
author_id, permlink_id)`** - protocol vote identity, not `(voter, post)`;
`post_id` is resolved. `weight NUMERIC`, `rshares BIGINT`, `vote_percent`,
`num_changes` (edit counter; used as an idempotency guard during batch replay,
`hive/indexer/sync.py:236-238`), `is_effective`, `last_update`, `block_num`.

### 1.3 Accounts

`hive_accounts` (~748 MB; lines 5-18): PK SERIAL, UNIQUE `name` (VARCHAR(16)
COLLATE "C"), `haf_id` (+ index, line 18), denormalized `followers`/`following`
counters, `rank`, `lastread_at` (notification read marker),
`posting_json_metadata`/`json_metadata TEXT`. **No reputation column** (Key
Discovery 2). Seed rows: id 0 sentinel + `miners`/`null`/`temp`/`initminer`
(part 01).

### 1.4 Follows family (5 identical tables)

`follows`, `muted`, `blacklisted`, `follow_muted`, `follow_blacklisted` (lines
260-307): each `(follower, following, block_num)` with PK `(follower,
following)` + `following` index + `block_num` index. This replaced the old
single `hive_follows` state-int table; each relation kind is its own table.
`muted_accounts_by_id_view`
(`hive/db/sql_scripts/hive_muted_accounts_by_id_view.sql:2-12`) computes
effective mutes = direct `muted` UNION transitive (accounts muted by lists you
follow: `follow_muted JOIN muted`).

### 1.5 Communities cluster

| Table | Lines | Keys | Notes |
|-------|-------|------|-------|
| `hive_communities` | 192-215 | **PK `id` = the community account's `hive_accounts.id`** (assigned, not serial - `hive/db/sql_scripts/community.sql:167-168`); UNIQUE `name` | `type_id SMALLINT` (1/2/3 - part 04), `lang CHAR(2)` default 'en', profile fields, `settings JSONB`, denormalized `sum_pending`/`num_pending`/`num_authors`/`rank`/`subscribers` |
| `hive_roles` | 218-226 | PK `(account_id, community_id)` | `role_id SMALLINT` (8 = owner set at creation, `community.sql:170-171`; full enum part 04), `title VARCHAR(140)` |
| `hive_subscriptions` | 229-238 | PK SERIAL; UNIQUE `(account_id, community_id)` | + community and block_num indexes |

Plus the GIN full-text index on `title || ' ' || about`
(`hive_communities_ft1`, created in Python, `hive/db/schema.py:163-164`).

### 1.6 Feeds, reblogs, mentions, notifications

| Table | Lines | Keys | Notes |
|-------|-------|------|-------|
| `hive_feed_cache` | 161-171 | PK `(account_id, post_id)` | Materialized blog feed: own posts + reblogs per account; `(account_id, created_at DESC, post_id DESC)` covering index |
| `hive_reblogs` | 149-158 | PK SERIAL; UNIQUE `(blogger_id, post_id)` | Indexes NOT HAF-registered (stay during massive sync) |
| `hive_mentions` | 183-189 | PK SERIAL; UNIQUE `(post_id, account_id, block_num)` | Rebuilt around edits via `delete_hive_posts_mentions` (part 04) |
| `hive_notification_cache` | 241-257 | PK `id` BIGINT snowflake (Key Discovery 5); UNIQUE `(src, dst, type_id, post_id, block_num)` | `dst`/`src`/`post_id`/`dst_post_id` nullable; `score INT`; `community`/`community_title`; `payload VARCHAR`; partial index `(dst, score) WHERE dst IS NOT NULL` |

### 1.7 Bookkeeping

- `hive_state` (lines 174-180): single row **by convention - no PK/unique**;
  `last_completed_block_num` (read at `hive/indexer/blocks.py:118`),
  `db_version`, and the stamped `hivemind_version`/`git_rev`/`git_date`
  (write sites: part 01 section 2). NOTE: fresh DDL declares `hivemind_git_date
  TIMESTAMP`; the upgrade path adds it as `TIMESTAMP WITH TIME ZONE`
  (`upgrade/upgrade_table_schema.sql:48`) - a fresh-vs-upgraded type drift.
- `hive_db_patch_level` (Python-created, `hive/db/schema.py:166-174`): SERIAL
  `level`, `patch_date`, `patched_to_revision`; read at startup for the version
  banner (`hive/indexer/sync.py:484-487`).
- Upgrade-only: `hive_db_data_migration`, `hive_db_vacuum_needed`
  (`upgrade/upgrade_table_schema.sql:15-25`; vacuum flag consumed by
  `hive/db/schema.py:374-382`).
- `deps_saved_ddl` + sequence (`hive/db/sql_scripts/postgres_handle_view_changes.sql:15-36`):
  the Pretius save-and-drop-dependencies helper used by upgrades to tear down /
  restore dependent views; note it is created with an **unqualified** name (falls
  wherever the admin's `search_path` points) while the paired DROP targets
  `hivemind_app.` explicitly (`postgres_handle_view_changes.sql:8-9`).

---

## 2. Staging & auxiliary tables (created by runtime SQL, not schema DDL)

Defined in `hive/db/sql_scripts/massive_sync.sql` (flow in part 03):

| Table | Lines | Logged? | Purpose |
|-------|-------|---------|---------|
| `_batch_queue` | 15-18 | **LOGGED** (comment 11-14: must survive crash recovery) | In-flight batch range marker for replay |
| `_ops_staging` | 20-33 | UNLOGGED | Batch's operations: HAF op id, block_num/date, `op_type_id`, pre-extracted JSONB payload; 2 indexes |
| `_comment_staging` | 36-48 | UNLOGGED | Comment ops of the batch (delete-create cycle detection via `staging_id`) |
| `_post_results` | 50-69 | UNLOGGED | Post-processing wave output (post_id, muted state, community...) |
| `_vote_batch` | 76-90 | UNLOGGED | Vote batch (persistent to avoid per-call temp-table overhead) |
| `_reblog_ops` / `_reblog_final` | 93-113 | UNLOGGED | Reblog pipeline stages |
| `_follow_notification_events` | 115-123 | UNLOGGED | Individual follow events incl. re-follows (final-state `follows` can't represent them) |

Others: `__post_children` UNLOGGED helper for the depth-descending children
recount (`hive/db/sql_scripts/update_hive_posts_children_count.sql:74-81`);
`community_op_counter` SEQUENCE (`massive_sync.sql:9`); session TEMP tables in
live processing (`hive/db/sql_scripts/hafapp_api.sql:74-82,278,309,366,404`).
In the utilities schema: `nai_currency_map` (Key Discovery 6). All UNLOGGED
staging + data tables are truncated by the UNLOGGED-loss recovery path
(`hive/indexer/sync.py:294-324` - the authoritative all-tables list).

---

## 3. Views & the canonical post record

All recreated at every start (Key Discovery 1); files under `hive/db/sql_scripts/`.

| View | File:lines | Shape |
|------|-----------|-------|
| `live_posts_comments_view` | hive_posts_view.sql:1 | `hive_posts WHERE counter_deleted = 0` |
| `live_posts_view` / `live_comments_view` | :3 / :5 | ... `AND depth = 0` / `depth != 0` |
| `hive_posts_base_view` | hive_posts_base_view.sql:2-14 | Minimal payout projection (block_num, ids, payout, rshares) |
| `hive_posts_parent_view` | :18-66 | Post + parent join; `parent_permlink_or_category` (parent permlink for replies, category for top-level, lines 43-46); hardcoded `0 AS votes/active_votes`, `true AS allow_replies` |
| `hive_accounts_view` | hive_accounts_view.sql:2-18 | Accounts + reptracker reputation join (`haf_id`), `is_implicit`, `is_grayed` |
| `hive_accounts_info_view_lite` | hive_accounts_info_view.sql:2-22 | + LATERAL live post_count |
| `hive_accounts_info_view` | :25-55 | + `active_at` = GREATEST(created, latest post, latest vote) (LATERAL max scans, index hints in comments) |
| `hive_votes_view` | hive_votes_view.sql:3-25 | Votes + voter (with reputation) + author + permlink names |
| `muted_accounts_by_id_view` | hive_muted_accounts_by_id_view.sql:2-12 | Direct UNION transitive mutes |
| `payout_stats_view` **MATERIALIZED** | payout_stats_view.sql:3-30 | Pending payouts per (community, author) UNION per-community rollup (`author IS NULL`, distinct authors); UNIQUE `(community_id, author)` enables CONCURRENTLY |

`payout_stats_view` refresh: `REFRESH MATERIALIZED VIEW CONCURRENTLY` via
`PayoutStats.generate` (`hive/utils/payout_stats.py:12-23`); call sites: live
block loop (`hive/indexer/blocks.py:515`), massive finalize
(`hive/db/db_state.py:535`), and sync shutdown (`hive/indexer/sync.py:79`).

**Canonical post record**: `hivemind_app.get_post_view_by_id(_id)` returns
`get_post_view_by_id_return_t` - the ~40-field composite (author/permlink/body/
img_url/payout/community/role fields...) that API post objects are built from
(`hive/db/sql_scripts/get_post_view_by_id.sql:3` type, `:151` function). It
carries function-local planner tuning `SET join_collapse_limit = 6` (`:246`),
overriding the database-wide 16 (part 01 section 7.2). Helpers in the same file:
`extract_img_url_from_json_metadata` (`:68`), `get_blacklisted_by_observer`
(`:251`). Detailed field mapping: parts 05-07.

**HAF-view helpers**: `head_block_time()` reads the context's
`hivemind_app.blocks_view` at `hive.app_get_current_block_num('hivemind_app')`
(`hive/db/sql_scripts/head_block_time.sql:2-10`); `block_before_head(interval)` /
`block_before_irreversible(interval)` compute block cutoffs at 3 s/block
(`:13-19`, `:22-28`). These are hivemind's only structural touchpoints on HAF's
per-context views (HAF KB part 04).

---

## 4. Index strategy

47 secondary indexes in `create_tables.sql` + 2 Python-created (GIN FT,
post_tags unique) + optional BM25. Patterns:

- **Live-subset partials**: most `hive_posts` indexes carry `WHERE
  counter_deleted = 0` and often `AND NOT is_paidout AND depth = 0` - matching
  ranked-post queries exactly (e.g. `hive_posts_sc_trend_id_idx`,
  `create_tables.sql:80-81`).
- **Expression indexes** on `(payout + pending_payout)`
  (`create_tables.sql:87-88`) for payout-ordered listings.
- **Covering** (`INCLUDE`) indexes: `hive_posts_parent_id_id_idx INCLUDE
  (author_id)` (`:74`), pinned/paidout community partials `INCLUDE (id)`
  (`:76-78`).
- **Feed path**: `hive_feed_cache (account_id, created_at DESC, post_id DESC)`
  (`:171`).
- **Notifications**: partial `(dst, score) WHERE dst IS NOT NULL` (`:257`).
- **Extended statistics** (dependencies) on 6 tables + per-table autovacuum
  thresholds + fillfactor 90 for `hive_posts`/`hive_votes`
  (`hive/db/schema.py:21-34,385-415`).

HAF registration split: Key Discovery 4. Full registered list:
`register_indexes.sql:6-64` (feed_cache 4, posts 17, votes 4, subscriptions 2,
communities 1, notification_cache 2, follows family 10, accounts 1 = 41).

---

## 5. Foreign keys

13 FKs, all `DEFERRABLE NOT VALID` ("skip validation on creation for speed",
`create_foreign_keys.sql:2`): `hive_posts` -> accounts/posts(root)/posts(parent)
(`:5-10`); `hive_votes` -> posts/accounts(voter)/accounts(author)/permlink
(`:13-20`); `hive_post_tags` -> posts/tag_data (`:23-26`); `hive_reblogs` ->
accounts/posts (`:29-32`); `hive_mentions` -> posts/accounts (`:35-38`).

**No FKs at all** on: `hive_post_data` (1:1 with posts by id!), `hive_feed_cache`,
the 5 follows tables, communities/roles/subscriptions, `hive_notification_cache`,
dictionaries, bookkeeping. Referential integrity there is maintained by the
indexer only. FK enable/disable during massive sync is HAF-managed (part 03);
the FK-aware two-phase UNLOGGED conversion order lives in
`hive/db/schema.py:418-458`.

---

## 6. Encodings & enums

- **Notification snowflake id** + `NotifyType` 1-17: Key Discovery 5. Score
  computation for vote notifications: `calculate_notify_vote_score`
  (`hive/db/sql_scripts/notifications_view.sql:3-15` - despite the filename, this
  file now defines only functions, no view).
- **`muted_reasons` bitmask** (on `hive_posts`): bit positions 0-4 =
  `MUTED_COMMUNITY_MODERATION`, `MUTED_COMMUNITY_TYPE`, `MUTED_PARENT`,
  `MUTED_REPUTATION`, `MUTED_ROLE_COMMUNITY`
  (`postgrest/utilities/muted_reasons_operations.sql:10-14`), with
  encode/decode helpers (`:21-46`).
- **Currency ENUM + NAI map**: `currency` ENUM ('HBD','HIVE','VESTS'), map rows
  `@@000000013`/`@@000000021`/`@@000000037` all precision 3 (VESTS wrong but
  dormant - Key Discovery 6).
- **Community `type_id`** (1/2/3) and **`role_id`** (8 = owner at creation;
  negative roles exist) - enumerated fully in part 04 with the community.sql
  logic.

---

## 7. Upgrade machinery

`hive upgrade_schema` (part 01 section 7.4) executes, as admin:

1. `postgres_handle_view_changes.sql` - installs `deps_saved_ddl` +
   `deps_save_and_drop_dependencies`/restore (view-dependency save/restore,
   `postgres_handle_view_changes.sql:1-45,137-144`).
2. `upgrade/upgrade_table_schema.sql` - **asserts** the install-time optimizer
   settings (`join_collapse_limit`/`from_collapse_limit` = 16, `jit` = off,
   source='database') and aborts with "use install_app.sh" otherwise (`:1-6`);
   `SET ROLE hivemind` (`:13`); then idempotent DDL: `hive_db_data_migration`,
   `hive_db_vacuum_needed` (`:15-25`), legacy index drops (`:29-31`), the
   HAF-shaped `hive_post_tags` re-creation with explicit `hive_rowid` column
   (`:33-41`), the critical unique tag index (`:43-45`), `hive_state` column
   retrofits (`:47-49`), `hive_posts.last_payout_block` (`:52`).
3. `upgrade/upgrade_runtime_migration.sql` - data migrations; at the anchor only
   the `tags_ids` array -> `hive_post_tags` migration (with INHERIT +
   `haf_tablespace`, Key Discovery 7), ending with `TRUNCATE
   hive_db_data_migration` (`:42`).

Then `VACUUM FULL VERBOSE ANALYZE` if `hive_db_vacuum_needed` says so
(`hive/db/schema.py:374-382`). Post-massive-sync, a targeted parallel vacuum runs
over 7 tables (`hive/db/db_state.py:785-795`).

---

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Core DDL (21 tables + 47 indexes) | hive/db/sql_scripts/schema/create_tables.sql | 1-307 | Fresh-install table shapes |
| HAF index registration (41) | hive/db/sql_scripts/schema/register_indexes.sql | 6-64 | Drop/restore around massive sync; BM25 exclusion note 59-61 |
| FK set (13, deferrable not valid) | hive/db/sql_scripts/schema/create_foreign_keys.sql | 5-38 | Posts/votes/tags/reblogs/mentions only |
| Staging tables | hive/db/sql_scripts/massive_sync.sql | 9-123 | `_batch_queue` LOGGED + 7 UNLOGGED staging |
| Runtime redeploy + search_path bind | hive/db/db_state.py | 136-138 | Reptracker schema frozen into views; swagger GUC |
| Reputation join | hive/db/sql_scripts/hive_accounts_view.sql | 4-17 | `haf_id` bridge, `is_grayed` threshold |
| Live-post views | hive/db/sql_scripts/hive_posts_view.sql | 1-5 | `counter_deleted = 0` family |
| Parent view | hive/db/sql_scripts/hive_posts_base_view.sql | 18-66 | `parent_permlink_or_category` |
| Account info views | hive/db/sql_scripts/hive_accounts_info_view.sql | 2-55 | post_count, `active_at` |
| Votes view | hive/db/sql_scripts/hive_votes_view.sql | 3-25 | Vote + names + reputation |
| Effective mutes | hive/db/sql_scripts/hive_muted_accounts_by_id_view.sql | 2-12 | Direct UNION transitive |
| Payout matview | hive/db/sql_scripts/payout_stats_view.sql | 3-30 | + unique idx for CONCURRENTLY |
| Matview refresh | hive/utils/payout_stats.py | 12-23 | Callers: blocks.py:515, db_state.py:535, sync.py:79 |
| Canonical post record | hive/db/sql_scripts/get_post_view_by_id.sql | 3,151,246 | Return type, function, local join_collapse_limit=6 |
| HAF view helpers | hive/db/sql_scripts/head_block_time.sql | 2-28 | blocks_view, block_before_* |
| Notification snowflake | hive/db/sql_scripts/utility_functions.sql | 101-153 | genesis time, pack, unpack |
| Notify types | hive/indexer/notify_type.py | 4-25 | 17 active type_ids |
| Muted-reasons bitmask | hive/db/sql_scripts/postgrest/utilities/muted_reasons_operations.sql | 10-77 | 5 reasons, encode/decode |
| NAI map | hive/db/sql_scripts/postgrest/utilities/assets_operations.sql | 2-41 | ENUM, map (VESTS=3!), to_nai, parse_asset |
| Community id = account id | hive/db/sql_scripts/community.sql | 167-171 | + owner role 8 |
| Children recount helper | hive/db/sql_scripts/update_hive_posts_children_count.sql | 74-81 | UNLOGGED `__post_children` |
| Upgrade guards + DDL | hive/db/sql_scripts/upgrade/upgrade_table_schema.sql | 1-52 | Optimizer asserts, bookkeeping tables, retrofits |
| tags_ids migration | hive/db/sql_scripts/upgrade/upgrade_runtime_migration.sql | 9-36 | INHERIT + haf_tablespace |
| View-deps helper | hive/db/sql_scripts/postgres_handle_view_changes.sql | 8-36 | deps_saved_ddl (unqualified create quirk) |
| UNLOGGED conversion | hive/db/schema.py | 418-492 | Two-phase FK-aware, real table sizes |
| Extended stats/autovac/fillfactor | hive/db/schema.py | 21-34,385-415 | Planner & vacuum tuning |
| UNLOGGED-loss table list | hive/indexer/sync.py | 294-324 | Authoritative data-table enumeration |

---

## Cross-references to existing parts

- **Part 01** (architecture): schema creation flow (section 7.3), seed data,
  extensions (plpython3u, pg_search), the three app schemas, install-time DB
  settings that upgrade asserts.
- **HAF KB part 03/04**: `app_register_index_dependency`, per-context
  `blocks_view`/`operations_view`, `app_get_current_block_num`,
  `app_get_irreversible_block`, stages.
- **hive-core KB** `reference/economics.md` / `operations.md`: asset NAIs and
  precisions (VESTS = 6 - contrast Key Discovery 6), vote identity
  (voter, author, permlink), payout fields mirrored in `hive_posts`.

## Open Questions (for later parts)

- Part 03: who writes `hive_state.last_completed_block_num` and when relative to
  the HAF context block (the two-counter consistency model); `_ops_staging` load
  path (`load_ops_staging`) and the wave algorithm behind
  `_comment_staging`/`_post_results`.
- Part 04: full `role_id` and community `type_id` enums; muted_reasons bit
  producers; mentions rebuild policy; notification score formulas beyond votes;
  `update_posts_rshares`, `hot_and_trends` (sc_trend/sc_hot math),
  `update_communities_rank`, feed-cache maintenance
  (`update_feed_cache`, `delete_reblog_feed_cache`).
- Part 07: which endpoints read `payout_stats_view`, the notification score
  cutoff (`prune_notification_cache`), and `custom.swagger_url` consumption in
  `endpoint_schema.sql`.
- Upstream-worthy: the VESTS precision row (Key Discovery 6); the
  `deps_saved_ddl` unqualified-creation quirk; `hive_state.hivemind_git_date`
  type drift (fresh TIMESTAMP vs upgraded TIMESTAMPTZ).
