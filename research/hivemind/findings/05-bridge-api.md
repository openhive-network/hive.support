# Hivemind Part 05 - The bridge API (25 methods)

**Anchor:** hivemind `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`).
**Scope:** the `bridge.*` namespace - the modern frontend API (denser, condenser
"bridge" mode). Router branch -> SQL function mapping, the shared parameter
pipeline, the bridge post object, per-method parameters/defaults/behavior.
Legacy namespaces are part 06; the dispatcher/error/utility layer in full depth
(list_votes, get_profiles internals, exceptions) is part 07.

Paths are hivemind-repo-relative against `workspace/hivemind/cab9e328bf/`;
`bridge_api/` = `hive/db/sql_scripts/postgrest/bridge_api/`,
`utilities/` = `hive/db/sql_scripts/postgrest/utilities/`.

---

## Summary

`get_bridge_method` routes 25 method names (`utilities/get_api_method.sql:100-169`);
23 map 1:1 to `hivemind_endpoints.bridge_api_*` functions, `normalize_post` is an
inline alias of `get_post`, and `list_muted_reasons_enum` returns a static map.
Every endpoint follows the same shape: `validate_json_arguments` (typed,
order-aware) -> `parse_*_argument_from_json` + `valid_*` normalizers ->
`find_account_id`/`find_comment_id` resolution -> a SQL body that assembles JSONB,
usually through `create_bridge_post_object`. Post-list methods share a 20-post
default limit governed by a database GUC, and observer-aware mute filtering plus
`muted_reasons_filter` masks thread through the big list methods.

---

## Key Discoveries

### 1. One validator for every method - ordered-JSON positional mapping
- **What**: `validate_json_arguments(_given_args, _expected_args JSON,
  _min_args_number, _special_errors)` accepts an object OR a positional array;
  arrays are mapped to names using the KEY ORDER of `_expected_args` (deliberately
  `JSON`, not `JSONB` - "because it preserve ordering"); a 1-element array holding
  an object is unwrapped; the legacy `call` envelope (part 01 dispatcher) enforces
  `_min_args_number` as minimum positional arity; too many positionals always
  fail. Type checks are lenient for `number` (accepts number/string/null/array -
  downstream `valid_number` finishes the job) and exact-or-null otherwise, with
  per-parameter custom error messages. "Unexpected keyword" is raised only when
  at least `_min_args_number` known args were supplied - explicitly mimicking the
  old Python error ordering (comment in-file).
- **Where**: `utilities/validate_json_arguments.sql:2-110` (ordering comment 2,
  call-arity 57-60, mapping loop 69-75, python-mimicry comment 86-88).
- **Impact**: JSON-RPC positional calls only work because of the declared key
  order in each endpoint - reordering keys in an `_expected_args` literal is a
  breaking API change that no schema diff would show.

### 2. Post-list limits are operator-tunable via a GUC
- **What**: `get_max_posts_per_call_limit()` reads
  `current_setting('hivemind_app.max_posts_per_call')`, default 20. Ranked and
  account-post endpoints validate `limit` against `[1, max]` with default
  `least(20, max)`; `valid_number` raises `<name> = N outside valid range
  [lo:hi]` on an out-of-range value, it never clamps (`utilities/valid_number.sql`).
- **Where**: `utilities/api_limits.sql:1-8`; usage e.g.
  `bridge_api/bridge_api_get_ranked_posts.sql:27-30`.
- **Impact**: a node operator can raise/lower page sizes per deployment
  (`ALTER DATABASE ... SET hivemind_app.max_posts_per_call`) without code
  changes - not documented anywhere else in the repo.

### 3. get_ranked_posts is a 6x4 matrix of specialized functions
- **What**: sorts `trending | hot | created | payout | payout_comments | muted`
  x scopes: no tag/`all` -> `get_all_*`; tag=`my` -> `*_for_observer_communities`
  (observer REQUIRED only in this case); tag is a community name ->
  `get_ranked_posts_for_communities` (sort passed as enum); otherwise ->
  `*_for_tag`. 24 concrete functions + the community dispatcher live in a
  2383-line utility file. `muted_reasons_filter` (array of enum ints) becomes a
  bitmask filter.
- **Where**: dispatch `bridge_api/bridge_api_get_ranked_posts.sql:15-86`
  (observer requirement 40-44, sort list 52-60); functions
  `utilities/get_ranked_posts.sql:5-2383`.
- **Impact**: behavior differences between scopes (pinned handling, mute rules,
  community-role gating) are per-function, not parametric - part 07/ future
  zooms should treat each cell independently when verifying subtle behavior.

### 4. The bridge post object - shared response shape with computed moderation
- **What**: `create_bridge_post_object(observer, row, truncate, reblogged_by,
  set_is_pinned, update_reblogs, replies)` builds every post payload:
  `stats.hide = is_hidden`, `stats.total_votes` (the per-post counter to use
  instead of `active_votes.length`), `stats.gray = is_grayed OR is_muted OR role_id = -2`; `stats.flag_weight` is a
  "cheap log10, stake-based flag weight" from downvote rshares (in-code: "1 =
  approx $400 of downvoting stake; 2 = $4,000"); `blacklists` gains synthetic
  `reputation-0`/`reputation-1` markers below rep thresholds; paid-out posts
  split `curator_payout_value` (parsed with `ASSERT currency = 'HBD'`) from
  author value, pending posts put the whole sum in `pending_payout_value`;
  replies get `parent_author`/`parent_permlink` and a `'RE: ' || root_title`
  title; `stats.muted_reasons` decodes the stored bitmask PLUS runtime bits 3
  (`MUTED_REPUTATION` when grayed) and 4 (`MUTED_ROLE_COMMUNITY` when role -2);
  `active_votes` always fetches via `list_votes` with a hardcoded 1000 cap
  ("in python code it was hardcoded"); `community`/`author_role`/`author_title`
  appear only when the post is in a community (role defaults to `guest`).
- **Where**: `utilities/create_bridge_post_object.sql:2-148` (gray 55-60,
  flag_weight 62-65, rep blacklists 76-81, payout split 104-115, RE: title
  117-121, muted_reasons 123-136, votes 69-70).
- **Impact**: this is the contract every bridge post method shares; the
  runtime-computed reason bits mean `stats.muted_reasons` is NOT simply the
  stored `hive_posts.muted_reasons` column (part 02).

### 5. Notification reads trust the write-time filtering; unread goes to raw HAF blocks
- **What**: `account_notifications`: `min_score` default 25 (0-100), `limit`
  1-100 default 100, `last_id` exclusive descending pagination, 90-day floor;
  message text via `get_notify_message`, url preference
  post -> community -> src -> dst; mention counts computed lazily only for
  type 16. `unread_notifications` resolves `lastread_at` to a block by scanning
  **`hive.blocks_view`** directly - the comment says "very important for
  performance (originally it was a hivemind_app_blocks_view)" - then counts
  cache rows above that block and `min_score` (default 25).
- **Where**: `bridge_api/bridge_api_account_notifications.sql:15-104`;
  `bridge_api/bridge_api_unread_notifications.sql:15-51` (blocks_view comment
  33); `post_notifications` is the same pattern keyed by post.
- **Impact**: all threshold/mute semantics were already applied at write time
  (part 04, Discovery 6) - the API layer only filters by score/window/pagination.
  The raw-`hive.blocks_view` shortcut is one of only two places the API bypasses
  the app's own context views (cross-check when HAF changes view shapes).

### 6. Two router-level quirks: normalize_post and does_user_follow_any_lists
- **What**: `normalize_post` never validates its input - the router extracts
  `params.post.author/permlink` and calls `get_post` ("according to python code,
  there are no checks"). `does_user_follow_any_lists` - despite the name -
  checks ONLY `follow_blacklisted` (an EXISTS on blacklist-follows; muted-list
  follows are not consulted).
- **Where**: `utilities/get_api_method.sql:144-146`;
  `bridge_api/bridge_api_does_user_follow_any_lists.sql:14-21`.
- **Impact**: faithful ports of old Python behavior, but both are traps for
  API consumers assuming the names describe the semantics.

---

## Method catalog

Defaults/ranges from each endpoint's `valid_number` calls (out-of-range raises, no clamping); "min" = the
validator's `_min_args_number` (legacy-`call` arity + unexpected-arg threshold,
Discovery 1). MPC = `max_posts_per_call` GUC (default 20).

| Method | Params (required bold) | Limits/defaults | Notes |
|--------|------------------------|-----------------|-------|
| get_ranked_posts | **sort**, start_author, start_permlink, limit, tag, observer, muted_reasons_filter | limit d=min(20,MPC), max MPC | Discovery 3; observer required iff tag='my' |
| get_account_posts | **sort**, **account**, start_author, start_permlink, limit, observer | same | sorts: blog, comments, feed, posts, replies, payout (`bridge_api_get_account_posts.sql:47-55`); `replies` alters start-resolution when start_permlink given |
| get_account_posts_by_tag | account, tag, ... (min 2) | same | separate method + single utility fn (`utilities/get_account_posts_by_tag.sql:2`) |
| get_post | **author**, **permlink**, observer | - | canonical single post via `get_post_view_by_id` (part 02) |
| normalize_post | post{author,permlink} | - | unvalidated alias (Discovery 6) |
| get_discussion | **author**, **permlink**, observer, muted_reasons_filter | - | returns an OBJECT keyed `author/permlink`, each with `replies` id arrays (`bridge_api_get_discussion.sql:36-40`) |
| get_post_header | **author**, **permlink** | - | minimal header (author/permlink/category/depth) |
| get_profile / get_profiles | **account** / **accounts[]**, observer | - | get_profile = get_profiles([a])[0] (`bridge_api_get_profile.sql:16-21`) |
| get_relationship_between_accounts | **account1**, **account2**, observer, debug (min 4) | - | 5 EXISTS booleans over the 5 follow tables (`:38-44`) |
| get_follow_list | **observer**, follow_type | - | follow_type: blacklisted (default) / follow_blacklist / muted / follow_muted (`bridge_api_get_follow_list.sql:24-40`); profile-decorated entries |
| does_user_follow_any_lists | **observer** | - | follow_blacklisted only (Discovery 6) |
| account_notifications | **account**, min_score, last_id, limit | score d=25 [0,100]; limit d=100 [1,100] | Discovery 5 |
| post_notifications | **author**, **permlink**, min_score, last_id, limit | same | per-post variant |
| unread_notifications | **account**, min_score | score d=25 | lastread -> block via raw hive.blocks_view |
| get_community | **name**, observer | - | community + team (roles >= mod, ORDER role DESC) |
| get_community_context | **name**, **account** | - | subscription/role/title for one account |
| list_communities | last, limit, query, sort, observer (min 0) | limit d=100 [1,100] | paged community list with text query |
| list_subscribers | **community**, last, limit | limit d=100 [1,100] | ORDER BY subscriber name ASC (`bridge_api_list_subscribers.sql:46`) |
| list_all_subscriptions | **account** | - | account's communities + own role/title |
| list_community_roles | **community**, last, limit | - | paged role list |
| list_pop_communities | limit (min 0) | d=25 [1,25] | rank by new subscriptions (`bridge_api_list_pop_communities.sql:21-38`) |
| get_trending_topics | limit, observer (min 2) | d=10 [1,25] | community ranks + fallback tag list (`bridge_api_get_trending_topics.sql:36-47`) |
| get_payout_stats | limit (min 0) | d=250 [1,250] | reads `payout_stats_view` matview (part 02) joined to communities |
| list_muted_reasons_enum | (none) | - | static `get_muted_reason_map()` (part 02 bitmask) |

(25 total: the 23 table rows above with get_profile/get_profiles counted
separately, + normalize_post + list_muted_reasons_enum.)

## Shared utility layer (as used here; full depth part 07)

- **Resolution**: `find_account_id(name, must_exist)` /
  `find_comment_id(author, permlink, must_exist)` - post ids resolved with
  `counter_deleted = 0`; `valid_account`, `valid_permlink`, `valid_tag`,
  `valid_number`/`valid_bigint` (default + range + name in error),
  `check_community` (name shape test) gate every input.
- **Observer semantics**: optional almost everywhere (`allow_empty => True`);
  when present, list methods add mute filtering and relationship decoration;
  `tag='my'` (ranked) and the follow-list/notification methods require it.
- **muted_reasons_filter**: array -> bitmask via `create_muted_reasons_bitmask`
  (part 02) threaded through ranked posts and get_discussion.
- **Profiles**: `get_profiles` + `extract_profile_metadata` merge
  `json_metadata`/`posting_json_metadata` profile objects (used by get_profile/s
  and get_follow_list entries).

---

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Bridge router (25 branches) | hive/db/sql_scripts/postgrest/utilities/get_api_method.sql | 100-169 | Method -> function map; normalize_post alias |
| Argument validator | hive/db/sql_scripts/postgrest/utilities/validate_json_arguments.sql | 2-110 | Ordered positional mapping; call arity; lenient number |
| Posts-per-call GUC | hive/db/sql_scripts/postgrest/utilities/api_limits.sql | 1-8 | hivemind_app.max_posts_per_call, default 20 |
| Bridge post object | hive/db/sql_scripts/postgrest/utilities/create_bridge_post_object.sql | 2-148 | Shared shape; gray/flag_weight/muted_reasons |
| Ranked dispatch | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_get_ranked_posts.sql | 15-86 | 6 sorts x 4 scopes |
| Ranked sort fns (24+1) | hive/db/sql_scripts/postgrest/utilities/get_ranked_posts.sql | 5-2383 | Per-scope implementations |
| Account posts dispatch | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_get_account_posts.sql | 17-56 | 6 sorts |
| Account posts fns | hive/db/sql_scripts/postgrest/utilities/get_account_posts.sql | 2-569 | blog/comments/feed/posts/replies/payout |
| Account notifications | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_account_notifications.sql | 15-104 | Pagination, msg/url building |
| Unread notifications | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_unread_notifications.sql | 15-51 | lastread -> raw hive.blocks_view |
| Single post | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_get_post.sql | 15-74 | get_post_view_by_id -> post object |
| Discussion tree | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_get_discussion.sql | 13-133 | Object keyed author/permlink + replies |
| Relationship | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_get_relationship_between_accounts.sql | 14-45 | 5 booleans over 5 tables |
| Follow list | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_get_follow_list.sql | 14-99 | 4 follow_type modes |
| does_user_follow_any_lists | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_does_user_follow_any_lists.sql | 14-21 | follow_blacklisted-only EXISTS |
| Community group | hive/db/sql_scripts/postgrest/bridge_api/ (7 files) | - | get_community(_context), list_* , trending topics |
| Payout stats endpoint | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_get_payout_stats.sql | 14-37 | matview read, limit 250 |
| Profiles | hive/db/sql_scripts/postgrest/bridge_api/bridge_api_get_profile.sql, bridge_api_get_profiles.sql | 12-21, 12-16 | get_profiles delegation |

## Cross-references to existing parts

- **Part 02**: `get_post_view_by_id_return_t` (the row every post method
  selects), `payout_stats_view`, muted-reasons bitmask + `get_muted_reason_map`,
  notification snowflake ids (`last_id` pagination works because ids sort by
  time), `rep_log10`/`is_grayed` threshold.
- **Part 04**: write-time notification thresholds and mute filtering these
  endpoints rely on; community types/roles behind `author_role`; the follow
  tables behind relationship/follow-list methods.
- **Part 01**: the dispatcher whitelist of parameterless methods includes
  `bridge.list_pop_communities`, `bridge.get_payout_stats`,
  `bridge.get_trending_topics`, `bridge.list_muted_reasons_enum` (home.sql:36-43).

## Open Questions (parts 06/07 or future zooms)

- `list_votes` internals (presentation modes, the 1000 cap) and
  `get_profiles`/`extract_profile_metadata` field mapping - part 07.
- Per-cell verification of the 24 ranked-sort functions (pinned-post injection,
  observer mute application differences) - future zoom if needed.
- `get_trending_topics` fallback tag list contents and community-rank window;
  `list_pop_communities` "newsubs" window definition.
- `get_relationship_between_accounts` `debug` parameter is parsed but its
  effect not traced here.
