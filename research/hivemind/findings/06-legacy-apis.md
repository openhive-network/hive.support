# Hivemind Part 06 - Legacy API namespaces (condenser, follow, tags, database)

**Anchor:** hivemind `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`).
**Scope:** the four legacy namespaces - `condenser_api` (23 branches),
`follow_api` (7), `tags_api` (11), `database_api` (3): router maps, delegation
structure, the condenser post object vs the bridge object, vote presentation
modes, per-method parameters and quirks. The `hive.*` and `search-api`
namespaces + shared utility internals are part 07.

Paths are hivemind-repo-relative against `workspace/hivemind/cab9e328bf/`;
`condenser_api/` = `hive/db/sql_scripts/postgrest/condenser_api/`,
`utilities/` = `hive/db/sql_scripts/postgrest/utilities/`.

---

## Summary

44 router branches, of which 41 are live and 3 are deliberate deprecation stubs
(`condenser_api.get_state`, `condenser_api.get_account_votes`,
`tags_api.get_account_votes`). `follow_api` and `tags_api` own ZERO
implementations - every branch calls a `condenser_api_*` function with behavior
flags; `condenser_api`'s ranked listings in turn reuse the same
`get_ranked_posts`/`get_account_posts` utilities as the bridge API (part 05),
called with `_called_from_bridge_api => False` and a caller-supplied
`truncate_body`. The legacy-vs-bridge differences live in two places: the
response objects (`create_condenser_post_object` vs the bridge object) and small
dispatch differences (community detection, no `muted_reasons_filter`).

---

## Key Discoveries

### 1. Two namespaces are pure delegation; four flags encode all legacy variants
- **What**: `follow_api` routes all 7 methods to `condenser_api_*` functions;
  `tags_api` routes all 10 live methods likewise. The variant behavior is
  carried by boolean flags at the router: `_fat_node_style` (condenser True /
  follow False - response format of get_account_reputations),
  `_get_entries` (get_blog vs get_blog_entries), `_get_replies` +
  `_content_additions` (get_content family; tags_api passes additions=False),
  `_called_from_condenser_api` (followers/following parameter naming).
  Notably `tags_api.get_discussion` is condenser `get_content` WITHOUT
  additions - NOT bridge `get_discussion`.
- **Where**: routers `utilities/get_api_method.sql:2-64` (condenser),
  `:67-97` (follow), `:170-208` (tags).
- **Impact**: fixing/auditing one condenser function covers up to three
  namespaces; the flags are the complete legacy-variant matrix.

### 2. The condenser post object is materially different from the bridge object
- **What**: `create_condenser_post_object`: `author_reputation` is the RAW
  reputation value (`_row.author_rep`) - the bridge object applies `rep_log10`;
  empty category renders as `'undefined'`; adds `last_update`, `body_length`,
  `root_title`, always parent fields. With `_content_additions` (only
  `condenser_api.get_content/_replies`): adds `author_rewards`,
  `root_author`/`root_permlink`, `allow_*`, `net_votes`,
  `total_pending_payout_value`, and rshares fields that are ZEROED once paid
  out, with `vote_rshares = FLOOR((rshares + abs_rshares)/2)` when pending;
  without additions (tags_api + list methods): only `net_rshares` and a
  simplified payout block. Payout-string logic mirrors the old Python
  ("afaik in all cases when currency is not HBD, assert is thrown in python
  code").
- **Where**: `utilities/create_condenser_post_object.sql:2-113` (raw rep 35,
  'undefined' 18-21, additions 67-98, vote_rshares 96-97, paidout zeroing
  87-91).
- **Impact**: the same post serialized via bridge and condenser differs in
  a dozen fields including the reputation SCALE - consumers must not mix
  namespaces when comparing values.

### 3. One vote engine, four presentation modes, 1000 caps everywhere
- **What**: `list_votes(observer, post, limit, case, presentation[, voter])`
  serves every vote listing: presentations `condenser_api` (percent as TEXT,
  reputation, rshares, voter), `database_api` (full row incl. weight,
  num_changes, last_update), `bridge_api` (rshares + voter only),
  `active_votes` (condenser + time + weight); cases `get_votes_for_posts`,
  `database_list_by_comment_voter`, `database_list_by_voter_comment`. Both
  post objects and `database_api.find_votes` hardcode limit 1000; the
  interactive `database_api.list_votes` validates `limit` within [1,1000]
  (out-of-range raises; `valid_number` never clamps).
- **Where**: `utilities/list_votes.sql:1-106` (presentations 5-50, cases
  53-55); `database_api/database_api_find_votes.sql:32`;
  `database_api/database_api_list_votes.sql:42,64-66`.
- **Impact**: 1000 is the effective ceiling on votes visible through ANY
  hivemind endpoint - posts with more voters are silently truncated (a
  faithful port of the Python cap, comment in both post-object builders).

### 4. Condenser's ranked dispatch is NOT the bridge dispatch
- **What**: `condenser_api_get_discussions_by` (serving
  by_created/hot/trending + post/comment_discussions_by_payout for BOTH
  condenser and tags namespaces): detects communities by `left(_tag, 5) =
  'hive-'` (bridge uses `check_community`), has NO `tag='my'` scope, no
  `muted_reasons_filter`, explicitly rejects `filter_tags` ("not supported"),
  accepts `truncate_body` - and for the two payout sorts there is NO community
  branch at all: `tag='hive-xxx'` + payout falls through to the generic
  per-tag function.
- **Where**: `condenser_api/condenser_api_get_discussion_by.sql:16-88`
  (community checks 55,63,71; payout cases 76-88).
- **Impact**: payout-sorted community listings behave differently between
  bridge (`get_ranked_posts_for_communities`) and condenser/tags
  (`*_for_tag`) - a real behavioral divergence to know when comparing outputs.

### 5. follow_api speaks `type`, condenser_api speaks `follow_type`
- **What**: the shared parameter extractor for followers/following picks the
  parameter NAME by caller: `follow_type` (condenser) vs `type` (follow_api),
  default `'blog'`, allowed values only `'blog'` (follows table) and
  `'ignore'` (muted table); limit validated [1,1000] (raises outside), default 1000.
  `get_account_reputations` differs in shape: condenser returns a bare array
  of `{account, reputation}`, follow_api wraps `{"reputations": [{name,
  reputation}]}` (raw values, limit 1000).
- **Where**:
  `condenser_api/extract_parameters_for_get_following_and_followers.sql:18-34,22-25`;
  `condenser_api/condenser_api_get_account_reputations.sql:2-49` (comment at 2).
- **Impact**: same data, three wire dialects (bridge relationship methods are
  a fourth) - the KB's reference layer must document per-namespace shapes, not
  just semantics.

---

## Method catalogs

### condenser_api (23 branches; router `get_api_method.sql:2-64`)

| Method | Implementation | Notes |
|--------|----------------|-------|
| get_follow_count | own fn | followers/following counters from `hive_accounts` (`condenser_api_get_follow_count.sql:12-20`) |
| get_reblogged_by | own fn | accounts who reblogged (author, permlink) (`condenser_api_get_reblogged_by.sql:14-35`) |
| get_trending_tags | own fn | per-category stats; limit d=250 max 250 (`condenser_api_get_trending_tags.sql:15-45`) |
| get_account_reputations | shared, `_fat_node_style=True` | Discovery 5 |
| get_blog / get_blog_entries | `condenser_api_get_blog` flag | blog feed incl. reblogs; entries variant returns stubs (ids), not full posts |
| get_content / get_content_replies | `condenser_api_get_content` flags | additions=True; replies capped at 5000 children (`condenser_api_get_content.sql:33-40`) |
| get_followers / get_following | shared + extractor | `follow_type` in {blog, ignore}; limit 1000 |
| get_active_votes | own fn | `list_votes` in `active_votes` presentation |
| get_discussions_by_blog / by_feed | `..._by_blog_or_feed` flag | delegates to `get_account_posts_by_blog/feed` (part 05 utilities) (`condenser_api_get_discussions_by_blog_or_feed.sql:56-58`) |
| get_discussions_by_comments | delegation | -> `get_account_posts_by_comments` (`:53`) |
| get_replies_by_last_update | delegation | -> `get_account_posts_by_replies` (`condenser_api_get_replies_by_last_update.sql:49`) |
| get_discussions_by_author_before_date | own query | over `live_posts_view` by author (`condenser_api_get_discussion_by_author_before_date.sql:59-108`) |
| get_discussions_by_{created,hot,trending}, get_post/comment_discussions_by_payout | `condenser_api_get_discussions_by` + sort enum | Discovery 4 |
| get_state | **stub** | "condenser_api get state is not supported" (`get_api_method.sql:19-20`) |
| get_account_votes | **stub** | steemitdev deprecation link (`:60-61`) |

Common to the list methods: limit d=`least(20, MPC)` max MPC (the part-05 GUC),
`truncate_body` (default 0 = no truncation), optional observer.

### follow_api (7; router `get_api_method.sql:67-97`)

All delegations: get_account_reputations (`_fat_node_style=False`), get_blog,
get_blog_entries, get_follow_count, get_reblogged_by, get_followers,
get_following (`_called_from_condenser_api=False` -> `type` parameter).

### tags_api (11; router `get_api_method.sql:170-208`)

get_content_replies + get_discussion (both -> `get_content`,
`_content_additions=False`), get_discussions_by_blog, by_comments,
by_author_before_date, by_created, by_hot, by_trending,
get_post_discussions_by_payout, get_comment_discussions_by_payout (all the
same condenser fns), get_account_votes (**stub**).

### database_api (3; router `get_api_method.sql:211-233`)

| Method | Behavior |
|--------|----------|
| find_votes | **author** + **permlink** -> `{"votes": [...]}`, database presentation, hardcoded 1000 (`database_api_find_votes.sql:13-32`) |
| list_votes | **start** (3-element array), **limit** [1,1000], **order** `by_comment_voter` / `by_voter_comment` (the two list cases); observer optional (`database_api_list_votes.sql:23-66`) |
| find_comments | **comments** = array of [author, permlink] pairs; malformed pairs silently skipped (`CONTINUE WHEN ... <> 'array' OR length <> 2`); returns database-style post objects (`database_api_find_comments.sql:18-104`, skip at 32) |

---

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Condenser router (23) | hive/db/sql_scripts/postgrest/utilities/get_api_method.sql | 2-64 | Map + 2 stubs + flags |
| Follow router (7) | hive/db/sql_scripts/postgrest/utilities/get_api_method.sql | 67-97 | Pure delegation |
| Tags router (11) | hive/db/sql_scripts/postgrest/utilities/get_api_method.sql | 170-208 | Pure delegation + stub |
| Database router (3) | hive/db/sql_scripts/postgrest/utilities/get_api_method.sql | 211-233 | find/list votes, find_comments |
| Condenser post object | hive/db/sql_scripts/postgrest/utilities/create_condenser_post_object.sql | 2-113 | Raw rep; additions matrix |
| Vote engine | hive/db/sql_scripts/postgrest/utilities/list_votes.sql | 1-106 | 4 presentations, 3 cases |
| Ranked dispatch (legacy) | hive/db/sql_scripts/postgrest/condenser_api/condenser_api_get_discussion_by.sql | 16-88 | hive- prefix; payout gap |
| Content family | hive/db/sql_scripts/postgrest/condenser_api/condenser_api_get_content.sql | 15-137 | additions flag; 5000-reply cap |
| Blog family | hive/db/sql_scripts/postgrest/condenser_api/condenser_api_get_blog.sql | 1-173 | get_blog vs entries |
| Followers extractor | hive/db/sql_scripts/postgrest/condenser_api/extract_parameters_for_get_following_and_followers.sql | 18-57 | follow_type vs type; 1000 |
| Reputations dual format | hive/db/sql_scripts/postgrest/condenser_api/condenser_api_get_account_reputations.sql | 2-49 | fat-node flag |
| Author-before-date | hive/db/sql_scripts/postgrest/condenser_api/condenser_api_get_discussion_by_author_before_date.sql | 19-112 | Own live_posts_view query |
| database_api fns | hive/db/sql_scripts/postgrest/database_api/*.sql | - | 3 methods (table above) |

## Cross-references to existing parts

- **Part 05**: the shared utilities every legacy list method reuses
  (`get_ranked_posts.sql` matrix, `get_account_posts.sql` sorts,
  `validate_json_arguments`, the `max_posts_per_call` GUC), and the bridge
  post object to contrast with Discovery 2.
- **Part 02**: `hive_accounts_view` (raw reputation source), `live_posts_view`,
  `hive_votes_view` fields surfaced by the database presentation
  (`num_changes`, `weight`).
- **Part 04**: vote-merge semantics behind `num_changes`/`is_effective`; the
  follows/muted tables behind followers/following; reblog rows behind
  get_reblogged_by/get_blog.
- **Part 01**: home.sql's parameterless whitelist includes
  `condenser.get_trending_tags` (called without params).

## Open Questions (part 07 / future zooms)

- `get_blog` vs `get_blog_entries` exact entry shape and the
  `get_reblogged_posts.sql` utility (208 lines) - worth a skim in part 07 if
  the reference layer needs blog-entry field lists.
- `json_date()` default epoch rendering (used for cashout/last_payout
  sentinels) - part 07 (utilities).
- `database_api.find_comments` result cap semantics (`LIMIT
  _comments_amount`) - whether duplicate pairs dedupe.
- Whether any production consumer still calls the tags_api namespace (drone
  metrics would tell; out of scope for source-only research).
