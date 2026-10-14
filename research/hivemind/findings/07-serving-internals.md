# Hivemind Part 07 - Serving Internals (errors, utilities, REST, search, hive.*)

**Anchor:** hivemind `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`).
**Scope:** the layers under and beside the JSON-RPC namespaces - the
exception/error contract, the parse/validate utility belt, profiles,
notification rendering, the `hive.*` introspection methods, `search-api`
(BM25/ParadeDB + the plpython preprocessor), and the native REST surface with
its OpenAPI self-description. Completes the findings series (parts 05-06 cover
the namespaces themselves).

Paths are hivemind-repo-relative against `workspace/hivemind/cab9e328bf/`;
`utilities/` = `hive/db/sql_scripts/postgrest/utilities/`,
`endpoints/` = `hive/db/sql_scripts/endpoints/`.

---

## Summary

Errors are raised as JSON-encoded strings that `home()` re-parses into JSON-RPC
error objects, and the important ones carry a fabricated hived-style
`assert_exception` payload so wax-family clients parse hivemind failures exactly
like node failures. A small utility belt (parse_*, valid_*, json_date,
rep_log10) gives every endpoint identical coercion rules. Besides JSON-RPC,
hivemind serves real REST: two GET endpoints with PostgREST-native signatures,
HTTP cache headers chosen by irreversibility, and an OpenAPI document served
from a dynamically (re)generated no-argument `home()` overload with the
deploy-time `custom.swagger_url` GUC baked in. `search-api.find_text` requires
ParadeDB and translates user queries to BM25 syntax in plpython.

---

## Key Discoveries

### 1. The error contract: JSON-in-SQLERRM, wax-compatible hived masquerade
- **What**: `raise_exception(code, message, data, id)` RAISEs
  `{"code":..,"message":..,"data":..}` as TEXT (with a `' :' -> ':'` spacing
  normalization); `home()` catches and re-parses it (part 01). 24 wrappers
  cover the error taxonomy; the prominent ones (method-not-found,
  account/permlink validation, deleted post, etc.) attach
  `build_hived_error_data` - a fake `assert_exception` structure (code 10,
  stack frame, `assertion_expression`, per-error hardcoded `assert_hash`)
  labeled "WAX-compatible" in-source. Unknown methods return JSON-RPC code
  **-32602** (the invalid-params code, not -32601) with message
  `Assert Exception:unknown method: ...`. The one exception is an unknown API
  namespace: `dispatch.sql:30` -> `raise_api_not_found_exception` -> plain
  **-32601** `Api not found <api>` with no fabricated data (`exceptions.sql:114-125`).
- **Where**: `utilities/exceptions.sql:3-36` (hived masquerade), `:39-62`
  (raise base + spacing hack), `:90-112` (method-not-found);
  parser side `postgrest/home.sql:63-76`.
- **Impact**: clients cannot distinguish hivemind-origin from hived-origin
  assert errors by shape - deliberate, for wax/beem error handling; the
  -32602-for-unknown-methods convention is a faithful port, not a bug.

### 2. GET / serves OpenAPI: a second, zero-argument home() overload
- **What**: `endpoints/endpoint_schema.sql` holds the OpenAPI 3.1.0 document
  (title Hivemind, version stamped at image build - part 01) and, at deploy
  time, EXECUTEs a dynamically-built
  `CREATE OR REPLACE FUNCTION hivemind_endpoints.home() RETURNS json` whose
  body embeds that document with `current_setting('custom.swagger_url')`
  substituted (the GUC set in `DbState.initialize`, part 02). With
  `PGRST_DB_ROOT_SPEC=home` (image ENV, part 01), PostgREST serves GET / from
  the no-arg overload (the spec) while POST / dispatches JSON-RPC through
  `home(JSON)` - one name, two overloads, two protocols.
- **Where**: `endpoints/endpoint_schema.sql:1-453` (spec + dynamic create
  at 27-39); `Dockerfile:142`; `hive/db/db_state.py:137`.
- **Impact**: the API is self-describing per deployment (correct public URL in
  the spec); any tooling that resolves PostgREST root specs gets a valid
  swagger for the REST subset.

### 3. REST responses set HTTP cache headers by irreversibility
- **What**: `hivemind_endpoints.get_ops_by_account` (the `/accounts/{a}/
  operations` REST endpoint) sets PostgREST response headers via
  `set_config('response.headers', ...)`: `Cache-Control: public,
  max-age=31536000` (1 year) when the requested page's last block is at or
  below HAF's irreversible block, else `max-age=2`. It then delegates to
  `hafah_backend.get_ops_by_account` passing the observer's muted list with
  mode `'exclude'`; page numbering is REVERSED (external page N maps to
  internal `total - N + 1`; first call passes NULL to get the newest page) -
  explained in a long in-file comment.
- **Where**: `endpoints/accounts/get_ops_by_account.sql:181-200` (headers
  181-185, hafah call 189-199), paging comment 201-213; sibling
  `endpoints/blog/get_reblogs.sql:89-96` shows the PostgREST-native signature
  style (hyphenated named args `"start-author"`, `RETURNS SETOF
  hivemind_endpoints.reblog_status`).
- **Impact**: immutable history pages are CDN-cacheable for a year straight
  from the database function - the only place hivemind manipulates HTTP
  semantics; also the concrete consumer of the HAfAH coupling (parts 01/04).

### 4. search-api is ParadeDB-only, with a plpython query compiler
- **What**: `search_api.find_text(pattern, sort, author?, start_*, limit,
  observer, truncate_body)` - sorts `relevance` (via `paradedb.score`) or
  `created`; raises "Full-text search is not available (pg_search extension
  not installed)" when the extension is absent; the BM25 query must match the
  partial-index predicate (`is_top_level_post`). User patterns are compiled by
  `preprocess_search_query` - a **plpython3u SECURITY DEFINER** function
  (installed by the admin, part 02) that tokenizes quoted phrases, `+`/`-`
  must/must-not prefixes, `title:`/`body:` field prefixes, repairs unclosed
  quotes, and defaults to searching both fields.
- **Where**: `postgrest/search-api/find_text.sql:20-95` (availability check
  56-59, score 86-95); `utilities/preprocess_search_query.sql:1-40+`.
- **Impact**: the one endpoint whose availability depends on an optional
  extension (deployments without ParadeDB have a working API minus search);
  also the only user-input path into plpython.

### 5. hive.* is deployment introspection straight from bookkeeping tables
- **What**: `hive.get_info` returns hivemind_version/git rev/git date (from
  `hive_state`), `database_head_block` (context head via `get_head_state`),
  and patch level (date/revision/`database_schema_version` = level);
  `hive.db_head_state` returns `db_head_block`, `db_head_time`, `db_head_age`
  (now minus head-block epoch). Both parameterless (the home() whitelist,
  part 01).
- **Where**: `postgrest/hive_api/hive_api_get_info.sql:2-36`;
  `hive_api/hive_api_db_head_state.sql:1-19`.
- **Impact**: the standard health/monitoring surface (haf_api_node health
  checks and the README curl example use `hive.get_info`); ties the version
  stamping chain (part 01 section 2) to a queryable endpoint.

---

## The utility belt (used by every namespace)

- **Parsing** (`utilities/parse_argument_from_json.sql:4-185`):
  `parse_argument_from_json` (text; optional-vs-required),
  `parse_integer_/parse_bigint_argument_from_json` (accept JSON numbers OR
  numeric strings, floor floats, NULL passthrough),
  `parse_integer_array_argument_from_json`.
- **Validation** (`utilities/valid_*.sql`): `valid_account`, `valid_permlink`,
  `valid_tag`, `valid_community`, `valid_date`, `valid_offset`, `valid_limit`,
  `valid_number`/`valid_bigint` (default + [min,max] + parameter name in the
  error), `valid_accounts` (arrays). Resolution: `find_account_id`,
  `find_comment_id` (live posts only), `find_category_id`, `find_tag_id`,
  `find_community_id`, `find_subscription_id`.
- **Rendering**: `json_date` - NULL / `infinity` / `9999-12-31...` all render
  as the sentinel **`1969-12-31T23:59:59`** (`utilities/json_date.sql:9-13`);
  `rep_log10` - the classic condenser formula (first-4-digits log trick,
  `(GREATEST(log10-9,0) * sign * 9) + 25`, 0 -> 25, ROUND 2)
  (`utilities/rep_log10.sql:1-35`) - note the *9 here vs the *7.5 variant
  used for notification scores (part 04); `json_stringify_numeric` for
  bigint-as-string fields.
- **Profiles**: `get_profiles(accounts, observer)` returns id/name/created/
  active/post_count/`rep_log10` reputation/stats{rank, following, followers}/
  `metadata.profile` (via `extract_profile_metadata`, merging
  posting_json_metadata-over-json_metadata profile objects); nonexistent
  accounts yield `{"<name>": "account does not exist"}` entries
  (`utilities/get_profiles.sql:29-67`;
  `utilities/extract_profile_metadata.sql:1-126`).
- **Notifications rendering**: `get_notify_type_from_id` (ids 1-17 -> names,
  matching the Python `NotifyType`, part 02) and `get_notify_message` -
  template strings with `<src>`/`<dst>`/`<payload>` substitution (e.g.
  `'<src> set your role to <payload>'`)
  (`utilities/notifications.sql:11-27,52-117`).
- **Misc**: `get_muted_accounts_list(observer)` (direct + transitive, feeds
  both list filtering and the REST ops exclusion), `get_number_of_mentions_in_post`,
  `check_community`/`valid_community`, `is_superuser`
  (`hive/db/sql_scripts/is_superuser.sql`, used by the `--log_explain_queries`
  guard, part 01).

## REST surface recap (with parts 01/04)

| Route (rewriter) | Function | Notes |
|------------------|----------|-------|
| GET `/accounts/{account}/operations` | `hivemind_endpoints.get_ops_by_account` | hafah delegation; muted-exclusion; reversed paging; irreversibility cache headers (Discovery 3) |
| GET `/blog/reblogs` | `hivemind_endpoints.get_reblogs` | native named args; `reblog_status` rows (type in `utilities/get_reblogged_posts.sql`) |
| GET `/` (root spec) | `hivemind_endpoints.home()` (no-arg) | the OpenAPI document (Discovery 2) |
| POST `/` -> `/rpc/home` | `hivemind_endpoints.home(JSON)` | the JSON-RPC dispatcher (part 01) |

`endpoints/types/operation.sql` defines the operation row type used by the ops
endpoint's OpenAPI schema.

---

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Hived-error masquerade | hive/db/sql_scripts/postgrest/utilities/exceptions.sql | 3-36 | assert_exception fabrication, assert_hash |
| Raise base + spacing hack | hive/db/sql_scripts/postgrest/utilities/exceptions.sql | 39-62 | JSON-in-SQLERRM contract |
| Method-not-found (-32602) | hive/db/sql_scripts/postgrest/utilities/exceptions.sql | 90-112 | Code choice + message shape |
| OpenAPI dynamic home() | hive/db/sql_scripts/endpoints/endpoint_schema.sql | 1-453 | swagger_url GUC substitution |
| REST ops endpoint | hive/db/sql_scripts/endpoints/accounts/get_ops_by_account.sql | 149-215 | Cache headers, hafah call, reversed paging |
| REST reblogs endpoint | hive/db/sql_scripts/endpoints/blog/get_reblogs.sql | 89-161 | Native PostgREST signature |
| Search endpoint | hive/db/sql_scripts/postgrest/search-api/find_text.sql | 20-95 | pg_search gate, paradedb.score |
| Query preprocessor | hive/db/sql_scripts/postgrest/utilities/preprocess_search_query.sql | 1-173 | plpython3u SECURITY DEFINER compiler |
| hive.get_info / db_head_state | hive/db/sql_scripts/postgrest/hive_api/*.sql | 2-36 / 1-19 | Version + head introspection |
| Parse helpers | hive/db/sql_scripts/postgrest/utilities/parse_argument_from_json.sql | 4-185 | Lenient coercion rules |
| json_date sentinel | hive/db/sql_scripts/postgrest/utilities/json_date.sql | 9-13 | 1969-12-31T23:59:59 |
| rep_log10 | hive/db/sql_scripts/postgrest/utilities/rep_log10.sql | 1-35 | Display reputation formula (*9+25) |
| Profiles | hive/db/sql_scripts/postgrest/utilities/get_profiles.sql | 29-67 | Field set; missing-account entries |
| Profile metadata merge | hive/db/sql_scripts/postgrest/utilities/extract_profile_metadata.sql | 1-126 | posting-over-json precedence |
| Notification rendering | hive/db/sql_scripts/postgrest/utilities/notifications.sql | 11-27,52-117 | Type names + message templates |

## Cross-references to existing parts

- **Part 01**: home(JSON) dispatcher + error re-parsing; PGRST_DB_ROOT_SPEC
  and the rewriter routes; the OpenAPI version stamping at image build.
- **Part 02**: `custom.swagger_url` GUC set in `DbState.initialize`; the
  bookkeeping tables `hive.get_info` reads; plpython3u/pg_search extensions.
- **Part 04**: notification score formula (*7.5) vs display `rep_log10` (*9);
  the muted-list semantics behind `get_muted_accounts_list`.
- **Parts 05/06**: every endpoint's use of the parse/valid belt; the vote and
  post objects that consume `json_date`/`rep_log10`/`json_stringify_numeric`.
- **wax KB**: the hived-error masquerade exists precisely so wax-family error
  parsing works unchanged against hivemind (`reference/wax/api.md` error
  handling).

## Open Questions

- `extract_profile_metadata` field-by-field sanitization (images, about
  length caps) was skimmed, not exhaustively mapped - relevant if the KB ever
  documents profile rendering guarantees.
- `get_reblogged_posts.sql` (blog-entry shaping, 208 lines) - skimmed;
  field-level verification pending if consumers need it.
- The per-error `assert_hash` constants are hardcoded and distinct per raise
  site - whether any client keys on them is unknown (source-only research).
- Whether `response.headers` caching also applies to `/blog/reblogs` (it does
  not set headers at the anchor - only the ops endpoint does).
