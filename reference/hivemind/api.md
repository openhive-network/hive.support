# Hivemind: API Methods (cheat sheet)

Anchor `1.28.6`. Depth: findings parts 05 (bridge), 06 (legacy), 07 (hive/
search/REST). Routers: `postgrest/utilities/get_api_method.sql`.

**Common rules**: params validated by `validate_json_arguments` (positional
arrays map via expected-args KEY ORDER; lenient number typing); post-list
`limit` default `least(20, max_posts_per_call)`, validated against the
`hivemind_app.max_posts_per_call` GUC (default 20): an out-of-range value raises
`<name> = N outside valid range [lo:hi]`, it is never clamped (`valid_number`);
observer optional unless stated; votes in any response capped at 1000.

## bridge (25)

| Method | Required | Notes |
|--------|----------|-------|
| get_ranked_posts | sort | sorts trending/hot/created/payout/payout_comments/muted x scopes all/`my`/community/tag (24 fns); observer REQUIRED iff tag='my'; muted_reasons_filter mask |
| get_account_posts | sort, account | sorts blog/comments/feed/posts/replies/payout |
| get_account_posts_by_tag | account, tag | separate utility fn |
| get_post / get_post_header | author, permlink | canonical post object / minimal header |
| normalize_post | post{author,permlink} | UNVALIDATED alias of get_post |
| get_discussion | author, permlink | OBJECT keyed `author/permlink` + replies arrays; muted_reasons_filter |
| get_profile / get_profiles | account / accounts[] | name/created/active/post_count/rep_log10/stats/profile-metadata; missing -> "account does not exist" |
| get_relationship_between_accounts | account1, account2 | 5 EXISTS booleans over the 5 follow tables |
| get_follow_list | observer | follow_type: blacklisted(d)/follow_blacklist/muted/follow_muted |
| does_user_follow_any_lists | observer | checks ONLY follow_blacklisted |
| account_notifications / post_notifications | account / author+permlink | min_score d=25 [0,100]; limit d=100 [1,100]; last_id exclusive desc pagination; 90-day floor |
| unread_notifications | account | lastread -> block via raw hive.blocks_view; count above min_score |
| get_community / get_community_context | name / name+account | + team roles / own role+subscription |
| list_communities | - | last/limit(d=100)/query/sort/observer |
| list_subscribers | community | ORDER BY name ASC, limit d=100 |
| list_all_subscriptions | account | account's communities + role |
| list_community_roles | community | paged |
| list_pop_communities | - | by new subscriptions, limit d=25 max 25 |
| get_trending_topics | - | community ranks + fallback tags, limit d=10 max 25 |
| get_payout_stats | - | payout_stats_view matview, limit d=250 |
| list_muted_reasons_enum | - | static bitmask map |

## condenser_api (23 = 21 live + 2 stubs)

| Method | Notes |
|--------|-------|
| get_content / get_content_replies | full condenser object (`_content_additions=True`); replies capped 5000 |
| get_discussions_by_{created,hot,trending}, get_post/comment_discussions_by_payout | shared ranked fns; community = `hive-` prefix; **payout sorts have NO community branch**; filter_tags rejected; truncate_body param |
| get_discussions_by_blog / by_feed / by_comments; get_replies_by_last_update | delegate to account-posts fns |
| get_discussions_by_author_before_date | own live_posts_view query |
| get_blog / get_blog_entries | full posts vs entry stubs |
| get_followers / get_following | param `follow_type` in {blog, ignore}; limit d=1000 |
| get_follow_count | follower/following counters |
| get_reblogged_by | rebloggers of a post |
| get_active_votes | list_votes `active_votes` presentation |
| get_account_reputations | bare array {account, reputation RAW}; limit d=1000 |
| get_trending_tags | per-category stats; limit d=250 |
| get_state / get_account_votes | **STUBS** - raise deprecation errors |

## follow_api (7 - all delegations)

get_account_reputations (wrapped `{"reputations":[{name, reputation}]}`),
get_blog, get_blog_entries, get_follow_count, get_reblogged_by, get_followers,
get_following (param named `type`, not `follow_type`).

## tags_api (11 = 10 delegations + 1 stub)

get_content_replies + get_discussion (condenser get_content WITHOUT additions -
NOT bridge get_discussion), get_discussions_by_blog/comments/
author_before_date/created/hot/trending, get_post/comment_discussions_by_payout,
get_account_votes (**stub**).

## database_api (3)

| Method | Notes |
|--------|-------|
| find_votes | author+permlink -> {"votes": [...]} database presentation, cap 1000 |
| list_votes | start = 3-element array; order by_comment_voter / by_voter_comment; limit [1,1000] |
| find_comments | array of [author, permlink] pairs; malformed pairs silently skipped |

## hive (2) - parameterless introspection

`hive.get_info` (hivemind version/git rev+date, database_head_block, patch
level), `hive.db_head_state` (db_head_block/time/age).

## search-api (1; alias `search_api`)

`find_text(pattern, sort relevance|created, author?, start_*, limit, observer,
truncate_body)` - REQUIRES pg_search (raises otherwise); ParadeDB BM25 over
top-level posts; plpython query compiler (quotes, +/-, title:/body:).

## REST (GET, via the rewriter)

| Route | Notes |
|-------|-------|
| /accounts/{account}/operations | delegates to hafah_backend; observer's muted list excluded; REVERSED page numbering (first call NULL = newest); Cache-Control 1 yr when page irreversible else 2 s |
| /blog/reblogs | native PostgREST signature (`"start-author"` style args) |
| / (GET) | the OpenAPI 3.1.0 document (dynamic no-arg `home()` overload) |

## Response objects (bridge vs condenser)

| Aspect | bridge object | condenser object |
|--------|---------------|------------------|
| author_reputation | `rep_log10` (25-ish scale) | RAW bigint |
| empty category | '' | 'undefined' |
| moderation | stats{hide, gray, total_votes, flag_weight, muted_reasons incl. runtime bits 3/4, is_pinned}; blacklists + reputation-0/1 markers | none |
| community | community/community_title/author_role/author_title | none |
| replies title | 'RE: ' + root_title | own title |
| paidout rshares | kept | zeroed (additions mode) |
| extra (additions mode) | - | author_rewards, root_author/permlink, allow_*, net_votes, vote_rshares=(rshares+abs)/2 |

Vote presentations: condenser (percent TEXT), database_api (full),
bridge (rshares+voter), active_votes (+time, weight).
