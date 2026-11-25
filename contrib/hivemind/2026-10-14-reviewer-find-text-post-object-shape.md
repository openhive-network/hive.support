# Which post object does search-api.find_text return (bridge rep_log10 or condenser RAW)?

- **Topic**: hivemind
- **Type**: question
- **Affects**: reference/hivemind/api.md (search-api (1)); reference/rules/hivemind.md (HM-005, the list of namespaces that return rep_log10); research/hivemind/findings/07-serving-internals.md (Key Discovery 4)
- **Source**: hivemind `hive/db/sql_scripts/postgrest/search-api/find_text.sql:20-95` (as cited by the KB); observed behavior: recorded responses in denser's test fixtures

## Description

HM-005 names `bridge` post objects and `bridge.get_profile(s)` as the calibrated
(`rep_log10`) sources and `condenser_api` / `follow_api` / `tags_api` as RAW. `search-api.find_text`
is documented only as "ParadeDB BM25 over top-level posts" with its parameter list
(`pattern, sort, author?, start_*, limit, observer, truncate_body`); the KB never says which
post-object builder it uses, so a reviewer cannot place its `author_reputation` on either
scale from the KB alone. This mattered in a real review (denser MR !1141): denser types
`find_text` as returning bridge `Entry[]` and renders `author_reputation` with the same
"already calibrated" helper as bridge posts; if `find_text` were condenser-shaped the fix
would have turned the search page's badges into 15-digit integers.

Please document the response shape of `find_text` (presumably `create_bridge_post_object`,
given the `observer` parameter and the observed values) and, if confirmed, add `search-api`
to the calibrated side of HM-005. Also worth stating for `truncate_body`, since that name
otherwise appears only on condenser list methods.

## Evidence

- KB: reference/hivemind/api.md lines "search-api (1; alias search_api)" and
  research/hivemind/findings/07-serving-internals.md Key Discovery 4 describe parameters,
  the pg_search gate and the plpython query compiler, not the result object.
- Observed: denser's recorded fixtures `apps/blog/playwright/tests/mock/fixtures/searchClassic/0002-search-api.find_text.json`
  and `.../ssrChecks/0013-search-api.find_text.json` (request `search-api.find_text` with
  `pattern: "hive", sort: "relevance", observer: "hive.blog"`) contain `author_reputation`
  values 38.01, 52.92, 53.59, 59.44, 62.13, 63.41, 64.24, 66.23, 66.74, 67.18, 67.41, 72.39 and
  a `stats` object with `gray/hide/flag_weight/total_votes`, i.e. the bridge post object with
  `rep_log10` applied. This is consistent with the bridge builder but is a recorded sample,
  not a reading of `find_text.sql`.
