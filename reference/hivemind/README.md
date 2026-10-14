# Hivemind Reference (social API layer)

Compact lookup layer for **hivemind** - the HAF app that maintains Hive's social
state (posts, votes, follows, communities, notifications) and serves the social
APIs (`bridge`, `condenser_api`, ...). Depth lives in
`../../research/hivemind/findings/` (8 parts, fully `file:line`-cited).

**Anchor:** hivemind `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`, tag
`1.28.6` == `master` == `release/1.28.6`, 2026-05-04). Pairs with **HAF 1.28.6**
(the HAF KB anchor). Version is git-tag-driven (versioningit); rc/alpha tags
live on the diverged `develop` lineage - final tags on `master`.

## Quick Lookup

| I need to know... | Doc |
|-------------------|-----|
| Components, CLI, Docker images, install/roles, HAF context, config | [architecture.md](architecture.md) |
| Tables, views, indexes, FKs, id encodings, enums | [schema.md](schema.md) |
| Sync loop, massive/live pipelines, crash safety, finalization | [sync.md](sync.md) |
| Which op does what to which table (op map + domain semantics) | [operations.md](operations.md) |
| API methods: all namespaces, params, limits, response objects | [api.md](api.md) |
| Dispatcher, errors, validator, utilities, REST/OpenAPI, search | [serving.md](serving.md) |

## Key Numbers

- **2 halves**: Python indexer (fills `hivemind_app`) + pure PL/pgSQL server
  (PostgREST serves `hivemind_endpoints`; openresty rewriter in front).
- **Irreversible-only**: non-forking HAF context `hivemind_app`.
- **3 sync stages**: `MASSIVE_WITHOUT_INDEXES` (> 201600 blocks behind),
  `MASSIVE_WITH_INDEXES` (> 101), `live`; 1000-block batches.
- **21 core tables** + 1 LOGGED + 7 UNLOGGED staging; **47 secondary indexes**
  (41 HAF-registered for massive-sync drop/restore); **13 FKs** (all
  DEFERRABLE NOT VALID).
- **72 JSON-RPC method branches** in 7 namespaces: bridge 25, condenser_api 23
  (2 stubs), tags_api 11 (1 stub), follow_api 7, database_api 3, hive 2,
  search-api 1 - plus **2 REST GET endpoints** and a GET-/ OpenAPI document.
- **3 schemas** (`hivemind_app`, `hivemind_endpoints`,
  `hivemind_postgrest_utilities`), **2 roles** (`hivemind` owner/sync/anon,
  `hivemind_user` query).
- Python **>= 3.12** (image ships 3.14); **PostgREST v12.0.2**; `plpython3u`
  REQUIRED; ParadeDB `pg_search` optional (BM25 search).
- Community support starts at block **37,500,000** (default
  `--community-start-block`).
- Notifications: **90-day** retention/window; vote notifications need
  rshares >= 10e9 AND value >= 0.02 HBD; scores 0-100, default min_score 25.
- Page sizes: `hivemind_app.max_posts_per_call` GUC, default **20**; votes are
  capped at **1000** per post in every API response.

## Important Non-Obvious Facts

**Deployment / installation**
- `hive server` is REMOVED (raises; PostgREST replaced it). The container
  `server` command runs `start_postgrest.sh`.
- `install_app.sh` hard-requires **HAfAH roles** (unconditional grants) and
  asserts the **reputation_tracker schema** exists. Install order: HAF ->
  reptracker -> hivemind indexer -> server.
- Install sets database-wide `join_collapse_limit`/`from_collapse_limit` = 16
  and **disables JIT**; the upgrade script ASSERTS these and aborts otherwise.
- During massive sync (with superuser) hivemind runs `ALTER SYSTEM SET
  fsync=off, full_page_writes=off` - **cluster-wide**, persisted in
  postgresql.auto.conf, restored on every shutdown path.
- A Postgres crash while tables are UNLOGGED truncates them; hivemind detects
  this (HAF context ahead + seed account id=0 missing) and resyncs from 0.
- The repo's own README/CLAUDE.md are stale at the anchor: no `haf` submodule
  exists, no SQLAlchemy (psycopg2 only), Python is >= 3.12 not 3.10.
- Manual `docker build` without `--build-arg COMMON_CI_REF=...` fetches HAF
  helper scripts from common-ci-configuration `develop` (moving target).

**Data model / indexer**
- The whole SQL API (views + functions) is **redeployed on every indexer
  start**; the reptracker schema binds via `search_path` at CREATE time - but
  TWO references hardcode `reptracker_app.` (`reputation_score`, mention
  scoring), so a custom `--reptracker-schema-name` breaks notification/mention
  scores (upstream-worthy).
- Reputation is never stored in hivemind - it joins from reputation_tracker
  via `hive_accounts.haf_id`. (`Reputations.flush` exists but has NO callers.)
- Post identity includes `counter_deleted` (permlink reuse after delete);
  always filter `counter_deleted = 0` (the `live_*` views do).
- `effective_comment_vote` rshares are scaled **x1,000,000 before block
  905693** (early-chain denomination).
- The BM25 index is NOT HAF-registered (pg_search MetaPage blocks UNLOGGED
  conversion) - dropped manually, rebuilt in the finalization "fills".
- `nai_currency_map` seeds VESTS with precision **3** (protocol says 6) -
  dormant (only HBD paths call `to_nai`), but a latent bug.
- `hive_state.hivemind_git_date` is TIMESTAMP on fresh installs but
  TIMESTAMPTZ on upgraded DBs (type drift).

**API behavior**
- JSON-RPC positional params map to names via the **key order** of each
  endpoint's expected-args literal (deliberately JSON, not JSONB) - key order
  IS the API contract.
- Errors masquerade as hived `assert_exception` payloads ("WAX-compatible");
  unknown methods return code **-32602** (not -32601); only an unknown API
  namespace returns -32601 `Api not found <api>`.
- `stats.muted_reasons` in responses = stored bitmask (bits 0-2) PLUS
  runtime-computed bits 3 (`MUTED_REPUTATION`) and 4 (`MUTED_ROLE_COMMUNITY`).
- Two reputation formulas: display `rep_log10` = `(log10-9)*9+25`;
  notification scores use `*7.5+25`. Condenser post objects return RAW
  reputation; bridge objects return `rep_log10`.
- Condenser's ranked dispatch detects communities by the `hive-` name prefix
  and has **no community branch for payout sorts** (falls through to per-tag) -
  a real bridge-vs-condenser divergence.
- `bridge.does_user_follow_any_lists` checks ONLY `follow_blacklisted`;
  `bridge.normalize_post` does zero validation (both faithful Python ports).
- `json_date` renders NULL/infinity as sentinel `1969-12-31T23:59:59`.
- GET / serves the **OpenAPI document** from a dynamically-recreated no-arg
  `home()` overload (with the `custom.swagger_url` GUC baked in);
  POST / is JSON-RPC via `home(JSON)`.
- The REST ops endpoint sets `Cache-Control: max-age=31536000` when the page
  is fully irreversible (else `max-age=2`) - CDN-cacheable history.
- `search-api.find_text` requires `pg_search`; queries are compiled to
  ParadeDB syntax by a plpython3u SECURITY DEFINER function.
- Only the `follow`, `reblog`, `community`, `notify` custom_json ids are
  interpreted (staged via HAF's `custom_json_type_id` partial index).

**L1 consistency (findings part 08 - hivemind vs hive-core)**
- **vop 80 (`account_created`) is not staged** - a LATENT gap: accounts
  created purely by hardfork code would be missing from `hive_accounts`.
  Harmless on mainnet today (both treasury names, `steem.dao` and
  `hive.fund`, were pre-registered as ordinary accounts months before their
  hardforks - verified empirically, production profiles/follows work), but
  it bites on fresh chains (testnet/mirrornet) and for any future
  hardfork-created account.
- Social custom_jsons signed with ACTIVE authority are valid on L1 but
  invisible to hivemind (all processors require exactly one posting auth).
- bridge's `author_payout_value` (condenser writes the same difference into
  `total_payout_value`; it has no `author_payout_value`) = payout - curator,
  which INCLUDES the beneficiary cut (the vop's misnamed `total_payout_value`
  is actually author-only; hivemind's `payout` reconstruction is correct).
- `hive_posts.is_declined` has NEVER been wired (definition-only since the
  2018 draft schema; verified across 0.25.4-1.28.6): always FALSE - anyone
  querying the column directly gets silently wrong data. Infer payout-decline
  from `max_accepted_payout = '0.000 HBD'`; note declined posts still rank
  in trending/payout sorts via their never-to-be-paid pending payouts.
- All real-op timestamps (created_at/updated_at/last_update) lag their block
  by 3 s (deliberate old-Python compat); vop-derived times are exact.
- Verified-exact L1 constants: pre-905693 rshares x1e6 = the HF1 vesting
  split; safe-cashout block 10629455 = HF17; comment_payout_update's
  final-only emission; cumulative pre-HF19 reward vops (last-writer is
  correct); ECV fires for unvotes too.

## Findings map (depth)

| Part | File |
|------|------|
| 01 Architecture & deployment | `../../research/hivemind/findings/01-architecture-deployment.md` |
| 02 Schema & data model | `.../02-schema-data-model.md` |
| 03 Sync internals | `.../03-sync-internals.md` |
| 04 Operation semantics | `.../04-operation-semantics.md` |
| 05 Bridge API | `.../05-bridge-api.md` |
| 06 Legacy namespaces | `.../06-legacy-apis.md` |
| 07 Serving internals | `.../07-serving-internals.md` |
| 08 L1 consistency cross-check | `.../08-l1-consistency.md` |
