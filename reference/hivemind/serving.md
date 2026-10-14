# Hivemind: Serving Internals (cheat sheet)

Anchor `1.28.6`. Depth: findings part 07 (+ 05 for the validator). SQL under
`postgrest/` (`home.sql`, `utilities/`) and `endpoints/`.

## Request flow

```
POST any-path -> rewriter -> /rpc/home -> home(JSON)
  -> validate jsonrpc/id/method (params required unless whitelisted)
  -> legacy 'call' envelope unwrap (["api","method",[params]])
  -> dispatch(api, method, params) -> per-namespace router -> endpoint fn
GET  /            -> home()          (no-arg overload = OpenAPI document)
GET  /blog/reblogs, /accounts/{a}/operations -> native REST functions
```

Parameterless-methods whitelist (home.sql): `call`, `hive.db_head_state`,
`condenser.get_trending_tags`, `bridge.list_pop_communities`,
`bridge.get_payout_stats`, `bridge.get_trending_topics`,
`bridge.list_muted_reasons_enum`.

## The validator (`validate_json_arguments`)

- Accepts object OR positional array; positional args map to names via the
  **key order** of the expected-args literal (JSON, not JSONB - order is the
  contract). A 1-element array holding an object unwraps.
- `_min_args_number`: minimum arity for legacy-`call` arrays + the threshold
  for raising "unexpected keyword" (mimics old Python error ordering).
- Types: `number` leniently accepts number/string/null/array (finished by
  `valid_number`); others exact-or-null; per-param custom error messages.

## Error contract

- Functions RAISE a JSON string `{"code","message"[,"data"]}`; `home()`
  re-parses SQLERRM into the JSON-RPC error object.
- Prominent errors attach `build_hived_error_data`: a fabricated hived
  `assert_exception` (code 10, fake stack frame, per-site hardcoded
  `assert_hash`) - "WAX-compatible" so client libs parse hivemind errors like
  node errors.
- Unknown method in a known api => JSON-RPC code **-32602** with
  `Assert Exception:unknown method: ...` (deliberately not -32601). Unknown api
  namespace => plain **-32601** `Api not found <api>` with no fabricated data
  (`utilities/dispatch.sql:30`, `exceptions.sql:114-125`).
- 24 `raise_*` wrappers in `utilities/exceptions.sql` (validation, deleted
  post, nonexistent account/category/tag, array-length, unexpected-keyword...).

## Utility belt

| Helper | Behavior |
|--------|----------|
| parse_argument_from_json / parse_integer_ / parse_bigint_ / parse_integer_array_ | optional-vs-required; numeric strings accepted; floats floored |
| valid_account/permlink/tag/community/date/offset/limit; valid_number/bigint | normalization + range + parameter name in the error |
| find_account_id / find_comment_id / find_category_id / find_tag_id / find_community_id | resolution (comments: live posts only) |
| json_date | NULL / 'infinity' / 9999-12-31 -> sentinel **1969-12-31T23:59:59** |
| rep_log10 | display reputation `(log10-9)*9+25` (0 -> 25, ROUND 2) - contrast notification scores `*7.5+25` |
| json_stringify_numeric | bigints as strings |
| get_notify_type_from_id / get_notify_message | type names 1-17; `<src>/<dst>/<payload>` templates |
| get_muted_accounts_list | direct + transitive mutes (feeds list filters + REST exclusion) |
| get_profiles / extract_profile_metadata | profile objects (posting_json_metadata over json_metadata) |

## GUCs (operator/deploy knobs)

| GUC | Purpose |
|-----|---------|
| hivemind_app.max_posts_per_call | post-list page cap, default 20 (ALTER DATABASE ... SET) |
| custom.swagger_url | public URL baked into the OpenAPI at deploy |
| response.headers | set by the REST ops fn: Cache-Control max-age=31536000 (irreversible page) vs 2 |

## OpenAPI self-description

`endpoints/endpoint_schema.sql` EXECUTEs a dynamic
`CREATE OR REPLACE FUNCTION hivemind_endpoints.home() RETURNS json` embedding
the OpenAPI 3.1.0 document with `custom.swagger_url` substituted; with
`PGRST_DB_ROOT_SPEC=home`, GET / serves it while POST / hits `home(JSON)` -
one name, two overloads, two protocols. Spec version stamped at image build.

## search pipeline

`find_text` -> gate on `pg_search` extension (raises if absent) ->
`preprocess_search_query` (plpython3u SECURITY DEFINER: quoted phrases, +/-,
title:/body: fields, unclosed-quote repair) -> BM25 query on the partial
top-level-posts index; sort `relevance` = `paradedb.score`.

## Cross-app touchpoints at serve time

- Reputation: reptracker tables via `haf_id` join (views) - two hardcoded
  `reptracker_app.` refs in scoring paths (see hub README gotcha).
- Account history: `hafah_backend.get_ops_by_account` behind the REST ops
  endpoint (muted-exclusion, reversed paging).
- HAF: `hivemind_app.blocks_view`/`context_data_view` for head state;
  `unread_notifications` reads RAW `hive.blocks_view` for the lastread block
  (documented perf choice).
