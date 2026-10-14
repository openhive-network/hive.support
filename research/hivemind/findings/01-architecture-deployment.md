# Hivemind Part 01 - Architecture & Deployment

**Anchor:** hivemind `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`, tag `1.28.6`
== `master` == `release/1.28.6`, 2026-05-04).
**HAF alignment:** CI pins HAF upstream ref `1.28.6` (`.gitlab-ci.yml:425-427`,
`UPSTREAM_BRANCH: 1.28.6`) - the HAF release the HAF KB is anchored to (`222c848355`).
Protocol semantics (operations, payouts, ...) are the hive-core KB's job; HAF context
mechanics (stages, views, `app_next_iteration`) are the HAF KB's job - this part
cross-references both.

**Scope:** the overall shape of hivemind - components, entry points, Docker images,
database installation (roles/schemas/settings), the HAF context, the sync loop's
skeleton, the serving path (PostgREST + nginx rewriter), and build/CI. Deep detail on
schema, sync internals, operation semantics, and the API namespaces is parts 02-07.

Paths are hivemind-repo-relative, against the pinned worktree
`workspace/hivemind/cab9e328bf/`.

---

## 1. What hivemind is

Hivemind is a **HAF application** that maintains Hive's *social* state - posts,
votes, follows, reblogs, communities, notifications, account profiles - and serves
the social APIs used by frontends (denser, condenser, wallets). It explicitly does
NOT cover wallets/orders/keys/account-history (`README.md:32-34` points those at
hived; account-history REST is delegated to HAfAH, section 10.4).

Two halves (`README.md:45-79`):

1. **Indexer** - Python package `hive/` (`setup.cfg:47-50` console script `hive`).
   Runs the HAF consume loop against an existing HAF database and fills the
   `hivemind_app` schema. Only **irreversible** blocks: the HAF context is created
   non-forking (`hive/indexer/hive_db/haf_functions.py:24-25`).
2. **Server** - pure **PL/pgSQL**. PostgREST exposes the `hivemind_endpoints`
   schema; an nginx/openresty "rewriter" in front converts the legacy JSON-RPC
   surface to PostgREST `/rpc/*` calls (section 10). The old Python API server is
   gone: `hive server` raises `"server mode is not longer supported - postgrest
   server is used instead"` (`hive/conf.py:212-215`).

The repo's own architecture claim "transitioning from Python to PL/pgSQL"
(`README.md:83-89`) is visible in the numbers: 142 `.sql` files vs 79 `.py` files at
the anchor, and even massive-sync block processing is SQL - the Python side just
orchestrates (section 9).

```
  hived -> HAF (haf_block_log DB)                       [HAF KB]
              |
              |  hive.app_next_iteration('hivemind_app')      Python indexer
              v                                               (hive sync)
          hivemind_app schema  (tables: posts/votes/follows/...)
              |
              |  SQL functions (hivemind_endpoints.*)         PL/pgSQL server
              v
          PostgREST :8080  <-  openresty rewriter :80  <-  JSON-RPC clients
```

---

## 2. Version anchor & versioning machinery

- Build backend: setuptools + **versioningit** (`pyproject.toml:1-7`). The version is
  derived from git tags matching `v*` or `[0-9]*` (`pyproject.toml:10-13`,
  `[tool.versioningit.vcs]`), so the manifest holds no version string.
- At build, versioningit writes `hive/_version.py` with `__version__`,
  `__git_revision__`, `__git_revision_date__` (`pyproject.toml:18-27`,
  `[tool.versioningit.write]`). `hive/version.py:1-8` re-exports these as `VERSION`,
  `GIT_REVISION`, `GIT_DATE`. Consequence: a plain source checkout has no
  `hive/_version.py` - the package is importable only after `pip install` /
  the Docker build generates it.
- The running instance stamps its version into the DB: `hive_state` gets
  `hivemind_git_rev/git_date/version` at schema creation
  (`hive/db/schema.py:56-59`) and refreshed on every `setup_runtime_code`
  (`hive/db/schema.py:335-356`).

**Lineages** (repo forensics, not code): final tags (`1.28.4`, `1.28.5`, `1.28.6`)
live on the curated `master`/`release/1.28.6` lineage; alpha/rc tags live on
`develop`, whose history diverged in the HAF-era rebase. The anchor `1.28.6` is the
`master` HEAD. GitLab release *objects* stop at `1.27.10`.

---

## 3. Repository layout (verified)

| Path | Content |
|------|---------|
| `hive/` | The Python package: `cli.py` (mode router), `conf.py` (configargparse), `db/` (adapter, schema builder, `sql_scripts/`), `indexer/` (sync loop + per-domain processors), `utils/` |
| `hive/db/sql_scripts/` | All SQL: indexer-side functions at top level (`massive_sync.sql`, `follow_ops.sql`, `hive_post_operations.sql`, views, ...), `schema/` (DDL), `postgrest/` (the server: `home.sql`, `utilities/`, `bridge_api/`, `condenser_api/`, `database_api/`, `hive_api/`, `search-api/`), `endpoints/` (REST + OpenAPI), `upgrade/` |
| `docker/` | `docker_entrypoint.sh` (instance image), `rewriter_entrypoint.sh` + `hivemind_nginx.conf.template` (rewriter image), `block-processing-healthcheck.sh`, compose files for sync/test |
| `scripts/` | `setup_postgres.sh`, `install_app.sh`(+`.sql`), `uninstall_app.sh`, `start_postgrest.sh`, `ci/` (incl. `build.sh`), `ci-helpers/`, mock helpers |
| `rewrite_rules.conf` | The 3 nginx rewrite rules (repo root; copied into the rewriter image) |
| `hafah/`, `reputation_tracker/`, `tests/tests_api/` | Git submodules (section 4) |
| `mock_data/` | Mock blocks/vops injected into a 5M-block HAF for tests |
| `tests/` | Tavern (YAML) API tests + Python unit tests |
| `alembic.ini` | **Vestigial** - no `alembic/` directory is tracked at the anchor; upgrades use raw SQL (`hive/db/sql_scripts/upgrade/`, section 7.4) |
| `Dockerfile`, `Dockerfile.rewriter` | The two images (section 6) |

---

## 4. Components & submodules

`.gitmodules` at the anchor defines exactly three submodules: `tests/tests_api`,
`reputation_tracker`, `hafah` (`.gitmodules:1-9`). Gitlink pointers at the anchor:
`hafah` = `19c53e29c5` (HAfAH `release/1.28.6`), `reputation_tracker` = `5103d71a98`
(`release/1.28.6`).

**There is NO `haf` submodule at 1.28.6** (there was at 1.28.4 - its tag commit
still lists one). Instead:

- CI detects the matching HAF *image* dynamically: "Upstream Image Detection (No
  Submodules Required)" via the `find_haf_image` job (`.gitlab-ci.yml:88-98`), with
  `UPSTREAM_BRANCH: 1.28.6` (`.gitlab-ci.yml:425-427`).
- The few HAF helper *scripts* hivemind needs (`create_haf_app_role.sh`,
  `common.sh`, `run_with_reconnect.sh`) are fetched at image build from
  `hive/common-ci-configuration` (`Dockerfile:157-160`); `setup_postgres.sh:14-29`
  looks for the role script in the image path, then a dev `../haf` submodule path
  (backwards compat), then falls back to `curl` from common-ci-configuration
  `develop`.

Why the other two apps are bundled:

- **reputation_tracker** - hard dependency of the server (reputation data).
  `install_app.sql:2-14` *asserts* the reptracker schema exists before hivemind
  installs; `install_app.sh:76-78` grants `reptracker_owner`/`reptracker_user` to
  `hivemind`. Default schema `reptracker_app`, overridable via
  `--reptracker-schema-name` (`hive/conf.py:149-155`, `install_app.sh:31,45-47`).
- **HAfAH** - backs hivemind's REST account-operations endpoint:
  `hivemind_endpoints.get_ops_by_account` calls `hafah_backend.*`
  (`hive/db/sql_scripts/endpoints/accounts/get_ops_by_account.sql:170-178`).
  `install_app.sh:80-82` grants `hafah_owner` to `hivemind` and `hafah_user` to
  `hivemind_user` **unconditionally** (with `ON_ERROR_STOP=on`) - i.e. hivemind
  1.28.6 cannot be installed into a HAF database that lacks HAfAH's roles.
- The instance image ships both apps under `/home/hivemind/app/`
  (`Dockerfile:164-165`) so `setup --with-apps` can install them
  (`docker/docker_entrypoint.sh:137-148`) - used by CI/test setups; production
  (haf_api_node) installs them as separate services.

---

## 5. Entry points & run modes

Console scripts (`setup.cfg:47-50`):

| Command | Target | Purpose |
|---------|--------|---------|
| `hive` | `hive.cli:run` | Mode router (below) |
| `mocker` | `hive.indexer.mocking.populate_haf_with_mocked_data:main` | Inject mock blocks/vops into HAF (testing) |

`hive` modes (`hive/cli.py:69-115`; default mode is `sync`, `hive/conf.py:44`):

| Mode | What it does |
|------|--------------|
| `build_schema` | `SyncHiveDb(enter_sync=False, upgrade_schema=False).build_database_schema()` - creates schema + runtime SQL, no sync (`hive/cli.py:71-82`) |
| `upgrade_schema` | Same but runs the upgrade scripts first (`hive/cli.py:84-95`; section 7.4) |
| `sync` | The consume loop (`hive/cli.py:97-107`; section 9) |
| `status` | Prints `DbState.status()` (`hive/cli.py:109-112`) |
| `completion` | Generates a bash-completion file (`hive/cli.py:46-48`, `hive/conf.py:259-275`) |
| `server` | **Removed** - raises in `Conf.init_argparse` (`hive/conf.py:212-215`) |

Key options (`hive/conf.py:36-163`): `--database-url` (env `DATABASE_URL`),
`--test-max-block` (stop sync at block N, then finalize indexes),
`--community-start-block` (default **37500000**, `hive/conf.py:120`),
`--reptracker-schema-name` (default `reptracker_app`), `--max-workers` (default 6) /
`--max-batch` (default None -> HAF stage decides), `--prometheus-port` (optional
Prometheus daemon, `hive/cli.py:42`), mock data paths for tests
(`hive/conf.py:107-119`).

Config precedence: CLI arg > ENV var > `./hive.conf` (configargparse,
`hive/conf.py:36-40`). DB access is psycopg2 (`hive/db/adapter.py:1-13`) - the
SQLAlchemy mentions in `README.md:92` and stray comments (`hive/indexer/sync.py:148`,
`hive/db/schema.py:176`) are leftovers; `adapter.py` converts SA-style `:param`
bindings to psycopg2 format itself (`hive/db/adapter.py:19-25`).

---

## 6. Docker images & container commands

Two images are released (registry `registry.gitlab.syncad.com/hive/hivemind` /
mirrored at `registry.hive.blog/hivemind` for haf_api_node):

### 6.1 `instance` (Dockerfile)

Multi-stage (`Dockerfile:5-103`): `pure_postgrest` (PostgREST binary from
`common-ci-configuration/postgrest` at pinned commit `4091089666...`, which is
upstream `postgrest/postgrest:v12.0.2` - verified in that repo's
`Dockerfile.postgrest`) -> `runtime` (base `python:3.14-slim-bookworm`,
`Dockerfile:9`; user `hivemind` uid 1000, `Dockerfile:50`) -> `ci-base-image` ->
`builder` (runs `scripts/ci/build.sh`, section 11) -> `instance`.

The instance stage ships: the venv + wheel (`Dockerfile:151-152`),
`docker_entrypoint.sh` + healthcheck (`Dockerfile:153-154`), `scripts/` as
`/home/hivemind/app` (`Dockerfile:155`), fetched HAF helper scripts
(`Dockerfile:157-160`), mock data (`Dockerfile:161-162`), and the two bundled apps
(`Dockerfile:164-165`). `STOPSIGNAL SIGINT` (`Dockerfile:170`) - sync shuts down
via the custom signal handlers. `ENV USE_POSTGREST=1` (`Dockerfile:137-138`) is
vestigial - nothing references it.

Entrypoint commands (`docker/docker_entrypoint.sh:181-213`):

| Command | Effect |
|---------|--------|
| `setup` / `install_app` | `setup_postgres.sh` -> (if `--with-apps`: install reptracker + hafah) -> `install_app.sh` -> (if `--add-mocks`: `ci/add-mocks-to-db.sh`) -> `hive build_schema` (or `upgrade_schema` if `--upgrade-schema`) (`docker_entrypoint.sh:127-167`) |
| `sync` | Optionally run setup first (`--install-app`), record startup time for the healthcheck, then `exec hive sync ...` (`docker_entrypoint.sh:191-204`) |
| `server` | `exec app/start_postgrest.sh` (`docker_entrypoint.sh:112-124,205-208`) |
| `uninstall_app` | `uninstall_app.sh` (+ bundled apps if `--with-apps`) (`docker_entrypoint.sh:169-178`) |

Healthcheck (`docker/block-processing-healthcheck.sh:12-27`): healthy if a block was
processed in the last 60s (after container start), OR hivemind's head == HAF's
irreversible head (so a stalled HAF doesn't mark hivemind unhealthy).

### 6.2 `postgrest-rewriter` (Dockerfile.rewriter)

Base `openresty:1.27.1.1-1-alpine` (mirrored), copies
`docker/hivemind_nginx.conf.template` + `rewrite_rules.conf`, entrypoint substitutes
`${REWRITE_LOG}` and execs openresty (`Dockerfile.rewriter:1-7`,
`docker/rewriter_entrypoint.sh:4-14`). Listens on **:80** (default_server,
`docker/hivemind_nginx.conf.template:11`), proxies to
`http://hivemind-postgrest-server:8080` (`hivemind_nginx.conf.template:21` - the
upstream hostname is hardcoded to the compose/network service name), and serves a
bare `204` health endpoint on **:81** `/health`
(`hivemind_nginx.conf.template:32-38`).

### 6.3 Deployment pairing

Recommended path is haf_api_node (`README.md:198-235`): `HIVE_API_NODE_VERSION`
selects hivemind + rewriter images (haf_api_node `hivemind.yaml` uses
`${HIVEMIND_IMAGE:-registry.hive.blog/hivemind}:${HIVEMIND_VERSION:-$HIVE_API_NODE_VERSION}`).
Install order is strict: **HAF -> reputation_tracker -> hivemind indexer**, server
last (`README.md:160-166`). Manual container sequence: `setup` (admin URL) -> `sync`
(app URL) -> `server` + rewriter (`README.md:291-310`).

---

## 7. Database installation: roles, schemas, settings

### 7.1 Roles (`scripts/setup_postgres.sh`)

- `hivemind` - the HAF app role, created via HAF's `create_haf_app_role.sh`
  (`setup_postgres.sh:100`). Owns the schemas; runs sync; is PostgREST's anon role.
- `hivemind_user` - query role, created with `--base-group=hive_applications_group`
  (`setup_postgres.sh:101`).
- Grants: `GRANT hivemind TO haf_admin`; `GRANT hivemind_user TO hivemind`
  (`setup_postgres.sh:48-53`).
- Optional `--statement-timeout` sets `statement_timeout` on `hivemind_user`
  (`setup_postgres.sh:107-110`); always resets
  `query_supervisor.limits_enabled` for `hivemind_user` (`setup_postgres.sh:111`;
  query supervisor is a HAF-side mechanism - HAF KB).

### 7.2 Database-level settings (`scripts/install_app.sql`)

Run by `install_app.sh:74` as admin, after asserting reputation_tracker is
installed (`install_app.sql:2-14`):

- `join_collapse_limit = 16`, `from_collapse_limit = 16` (database-wide,
  `install_app.sql:22-23`),
- `GRANT CREATE ON DATABASE ... TO hivemind` (`install_app.sql:24`),
- **JIT disabled** database-wide (`jit TO False`, `install_app.sql:26-29`).

Then cross-app grants (section 4): reptracker (`install_app.sh:76-78`) and hafah
(`install_app.sh:80-82`).

### 7.3 Schema creation (`hive build_schema` -> `hive/db/schema.py`)

`setup()` (`hive/db/schema.py:82-188`), admin + app connections:

- Creates the 3 schemas owned by `hivemind`: `hivemind_app`,
  `hivemind_endpoints`, `hivemind_postgrest_utilities`
  (`hive/db/schema.py:86-88`; names fixed in `hive/conf.py:14-17`).
- Extensions: **`plpython3u` required** (superuser-created,
  `hive/db/schema.py:97-99`) - used by the search-query preprocessor executed as
  admin (`hive/db/schema.py:183-188`,
  `postgrest/utilities/preprocess_search_query.sql`). **`pg_search` (ParadeDB)
  optional** (`hive/db/schema.py:90-95`): if present, a **BM25 index** is created
  on `hive_post_data(title, body)` restricted to top-level posts
  (`hive/db/schema.py:121-129`), with an `is_top_level_post()` helper created as a
  dummy before DDL and replaced with the real implementation after
  (`hive/db/schema.py:103-115,131-145`). If absent, BM25 full-text search is
  disabled with a warning.
- Creates the HAF context (section 8), then DDL from
  `sql_scripts/schema/create_tables.sql` (`hive/db/schema.py:117-119`), registers
  indexes with HAF for managed drop/restore during massive sync
  (`register_indexes.sql` via `hive.app_register_index_dependency`,
  `hive/db/schema.py:147-149` - HAF KB), FKs (`create_foreign_keys.sql`,
  `hive/db/schema.py:152`), extended statistics (`hive/db/schema.py:21-34`),
  autovacuum thresholds and fillfactors (`hive/db/schema.py:385-415`), seed data
  (`hive/db/schema.py:47-79`: sentinel id=0 rows, system accounts `miners`,
  `null`, `temp`, `initminer`, sentinel post 0), a patch-level table
  (`hive/db/schema.py:166-174`).
- `setup_runtime_code()` (`hive/db/schema.py:191-318`) then executes the ordered
  list of ~120 SQL scripts - all indexer SQL functions, views, and the entire
  PostgREST API surface. This list is the definitive map of the server code; parts
  05-07 follow it.

### 7.4 Upgrade & uninstall

- `hive upgrade_schema` runs `postgres_handle_view_changes.sql`,
  `upgrade/upgrade_table_schema.sql`, `upgrade/upgrade_runtime_migration.sql` as
  admin (`hive/db/schema.py:359-372`), then `VACUUM FULL VERBOSE ANALYZE` only if a
  `hive_db_vacuum_needed` row requests it (`hive/db/schema.py:374-382`). Container
  flow: `--upgrade-schema` (`docker_entrypoint.sh:67-70,160-166`;
  `README.md:316-329`).
- `uninstall_app.sh:61-66`: `hive.app_remove_context('hivemind_app')`, `DROP
  SCHEMA hivemind_app CASCADE`, `DROP OWNED BY hivemind CASCADE`, `DROP ROLE
  hivemind`.

---

## 8. HAF integration: context & stages

`prepare_app_context` (`hive/indexer/hive_db/haf_functions.py:12-33`):

- Context name = schema = `hivemind_app`, created **non-forking**
  (`_is_forking => FALSE`) - hivemind consumes only irreversible blocks; on an
  existing context it force-sets non-forking
  (`haf_functions.py:29-31`).
- Custom stage array (`haf_functions.py:16-21`):

| Stage | Enter when behind by | Batch size |
|-------|----------------------|-----------|
| `MASSIVE_WITHOUT_INDEXES` | > `ONE_WEEK_IN_BLOCKS` = 201600 blocks (`hive/conf.py:18`) | 1000 |
| `MASSIVE_WITH_INDEXES` | > 101 blocks | 1000 |
| `live` (`hive.live_stage()`) | otherwise | 1 |

  (Stage mechanics - thresholds, `'20 seconds'` window parameter, `wait_for_haf` -
  are HAF KB part 03 territory.)

- **Custom-JSON partial index**: at sync start (not install - deliberate, comment at
  `haf_functions.py:35-36`) hivemind calls
  `hive.create_custom_json_type_index(ARRAY['follow','reblog','community','notify'])`
  (`haf_functions.py:9,39-48`, invoked from `hive/indexer/sync.py:95-98`). This is a
  HAF 1.28.6 feature (SECURITY DEFINER; builds a partial index on
  `hafd.operations.custom_json_type_id`) that the HAF KB does not yet document - a
  contrib note was filed. The 4 ids listed are exactly the custom_json op ids
  hivemind interprets (part 04).

---

## 9. Sync architecture (skeleton; detail in part 03)

The loop (`hive/indexer/sync.py:94-229`):

1. Every iteration calls `CALL hive.app_next_iteration(ARRAY['hivemind_app'], ...)`
   passing `--test-max-block` as `_limit` and `--max-batch` as
   `_override_max_batch` (`sync.py:386-412`), then asks
   `hive.get_current_stage_name('hivemind_app')` (`sync.py:156`).
2. `MASSIVE_WITHOUT_INDEXES`: synchronous_commit off, **WAL safety off** (`fsync`,
   `full_page_writes` via ALTER SYSTEM - restored on any shutdown path,
   `sync.py:190-191,443-448`), FKs and indexes dropped (HAF-managed), then the
   batch is processed **in a single background thread**
   (`_massive_consume_blocks_thread_pool`, max_workers=1, `sync.py:52,430-441`).
3. `MASSIVE_WITH_INDEXES`: same, but indexes restored first (`sync.py:196-208`).
4. `live`: waits for pending massive work, restores synchronous_commit/WAL/FKs,
   finalizes massive sync, then per-block `Blocks.process_live_block_sql`
   (`sync.py:209-226,414-428`).
5. Block processing itself is **pure SQL**: massive batches run
   `Blocks.process_multi_sql` reading directly from the context's
   `operations_view` - "no Python dispatch loop" (`sync.py:533-578`, docstring at
   534, `operations_view` comment at 438; the SQL lives in
   `hive/db/sql_scripts/massive_sync.sql`, 2619 lines).

Crash-safety machinery (part 03 will detail):

- `_batch_queue` marker table committed atomically with the context advance;
  replayed on restart if a batch died mid-flight (`sync.py:180-185,231-254`);
  processing SQL is idempotent for replay (comment `sync.py:236-238`).
- **UNLOGGED-table data-loss detection**: during massive sync big tables are
  UNLOGGED (two-phase FK-aware parallel conversion with real-world sizes in
  comments - `hive_votes` ~319GB, `hive/db/schema.py:418-492`); a Postgres crash
  truncates them while the LOGGED HAF context survives. Detection = seed account
  id=0 missing while context is ahead; recovery = truncate everything, reset the
  context, reseed, resync from 0 (`sync.py:256-350`).
- Connection hygiene: stale `hivemind_%` backends from crashed instances are
  terminated at startup (`sync.py:584-611`), and live sync asserts its connection
  set is unchanged after each range (`sync.py:427-428,613-622`).
- Prometheus metrics broadcast per batch when `--prometheus-port` is set
  (`sync.py:572`, `hive/cli.py:42`).

---

## 10. Serving path

### 10.1 Request flow

```
client --POST JSON-RPC--> openresty:80 --rewrite--> PostgREST:8080 --SELECT--> SQL
```

`rewrite_rules.conf:1-8` (included by `hivemind_nginx.conf.template:14-15`):

| Incoming | Rewritten to |
|----------|--------------|
| `^/blog/reblogs` | `/rpc/get_reblogs` |
| `^/accounts/([^/]+)/operations` | `/rpc/get_ops_by_account?account-name=$1` |
| everything else (`^/(.*)$`) | `/rpc/home` (the JSON-RPC dispatcher) |

### 10.2 PostgREST configuration

`scripts/start_postgrest.sh:52-63` (what `server` runs): schema
`hivemind_endpoints`, anon role `hivemind`, pool 20, acquisition timeout 10s,
admin port 3001 (default; webserver 8080). `PGRST_DB_ROOT_SPEC="home"` is set as
image ENV (`Dockerfile:140-142`) but commented out in the script itself
(`start_postgrest.sh:61`) - in-container the inherited ENV makes `POST /` hit
`home` directly; on bare-host runs only the nginx rewrite provides that mapping.
Note the script's default connection user is `hivemind_user`
(`start_postgrest.sh:8`) but the documented/production invocations pass
`--postgres-url` with the `hivemind` role (`README.md:304`,
`docker_entrypoint.sh:112-124`).

### 10.3 The JSON-RPC dispatcher

`hivemind_endpoints.home(JSON)` (`hive/db/sql_scripts/postgrest/home.sql:1-79`):
validates `jsonrpc == '2.0'` / `id` / `method`, rejects missing `params` except for
a whitelist of parameterless methods (`home.sql:34-43`), supports the legacy
`call` envelope (`["api", "method", [params]]`, `home.sql:46-58`), splits
`api.method`, and delegates to `hivemind_postgrest_utilities.dispatch`
(`home.sql:61`). Errors: functions raise exceptions whose message is a JSON blob;
`home` converts that into the JSON-RPC `error` object (`home.sql:63-76`).

`dispatch` (`postgrest/utilities/dispatch.sql:11-31`) routes 7 namespaces to
per-API routers in `postgrest/utilities/get_api_method.sql`; counting
`WHEN __method_type` branches gives the surface size at the anchor:

| Namespace | Router (`get_api_method.sql`) | Methods |
|-----------|------------------------------|---------|
| `bridge` | `get_bridge_method` (line 100) | 25 |
| `condenser_api` | `get_condenser_api_method` (line 2) | 23 |
| `tags_api` | `get_tags_api_method` (line 170) | 11 |
| `follow_api` | `get_follow_api_method` (line 67) | 7 |
| `database_api` | `get_database_api_method` (line 211) | 3 |
| `hive` | `get_hive_api_method` (line 236) | 2 |
| `search-api` (alias `search_api`) | `get_search_api_method` (line 259) | 1 |

72 branches total (some may be alias/deprecation stubs - per-method verification is
parts 05-07). The `search_api` underscore alias exists because the drone caching
proxy folds it onto `search-api` upstream (comment `dispatch.sql:22-25`).

### 10.4 REST surface + OpenAPI

`hive/db/sql_scripts/endpoints/`: `endpoint_schema.sql` (OpenAPI 3.1.0 spec, line 2;
`version: 0.0.0-dev` at line 11 is stamped with the real version at image build,
`Dockerfile:94-99`), `types/operation.sql`, and two GET endpoints:
`hivemind_endpoints.get_ops_by_account`
(`endpoints/accounts/get_ops_by_account.sql:149`, delegating to `hafah_backend.*`,
lines 170-178) and `hivemind_endpoints.get_reblogs`
(`endpoints/blog/get_reblogs.sql:89`). These correspond 1:1 to the two non-home
rewrite rules (10.1).

Reputation data comes from the reputation_tracker schema (default
`reptracker_app`); the schema name is baked into SQL at install time via
`--reptracker-schema-name` (section 4).

---

## 11. Build & CI

- In-image build: `scripts/ci/build.sh` creates `/home/hivemind/.hivemind-venv`,
  generates version SQL for the bundled reputation_tracker and hafah (their
  `generate_version_sql` scripts, handling both submodule and standalone-clone git
  layouts), `pip install .`, sanity-imports `hive.signals`, and builds a wheel
  (`scripts/ci/build.sh:8-45`).
- OpenAPI version stamping: the builder rewrites `"version"` fields in
  `endpoint_schema.sql` / `hafah_openapi.sql` with `ARG API_VERSION`
  (`Dockerfile:94-99`).
- PostgREST provenance: pinned `common-ci-configuration` image commit
  (`Dockerfile:5-7`), which wraps upstream `postgrest/postgrest:v12.0.2` - matches
  `README.md:397`'s "requires PostgREST version 12.0.2".
- Note (supply-chain shape, not a bug): the instance image `ADD`s three HAF helper
  scripts from `common-ci-configuration` at **`COMMON_CI_REF=develop`** by default
  (`Dockerfile:13,111,157-160`), and `setup_postgres.sh:23-28` has a runtime `curl`
  fallback for the role script, also defaulting to `develop`. Released images are
  built by CI with pinned refs, but a manual `docker build` without
  `--build-arg COMMON_CI_REF=...` pulls moving-target scripts.
- CI (`.gitlab-ci.yml`): HAF image detection (section 4), `HAF_CI_MODE: "1"`, app
  sync against a cached 5M-block HAF + injected mocks, Tavern smoketests
  (bridge/condenser/follow/tags/database/negative patterns), benchmarking. The
  repo's `haf_data_preparation` / `haf_app_testing` templates come from
  common-ci-configuration (`.gitlab-ci.yml:20-25`).

---

## 12. Repo docs vs code at the anchor (trust the code)

The in-repo `README.md` and `CLAUDE.md` lag the code; verified discrepancies:

| Doc claim | Reality at 1.28.6 |
|-----------|-------------------|
| "haf/ - HAF project - Git submodule" (`README.md:108`), build steps `cd haf` (`README.md:176-181`) | No `haf` submodule/dir; HAF image found by CI, helper scripts fetched from common-ci-configuration (section 4) |
| "Python 3.10" / "Python 3.10+ required" (`README.md:92,367`; `CLAUDE.md`) | `python_requires = >=3.12` (`setup.cfg:10`); image ships Python 3.14 (`Dockerfile:9`) |
| "SqlAlchemy 1.4.49 is used" (`README.md:92`) | psycopg2 only (`hive/db/adapter.py:1-13`; no SQLAlchemy in `setup.cfg:11-22`) |
| `hive server --http-server-port=8080 ...` (`README.md:656-658`) | `server` mode raises - PostgREST replaced it (`hive/conf.py:212-215`); use the container `server` command / `start_postgrest.sh` |
| CLAUDE.md: "cli.py routes (sync, build_schema, status)" | Also `upgrade_schema` and `completion` (`hive/cli.py:84,46`) |

(The repo CLAUDE.md is otherwise a decent orientation doc; its test-setup block
numbers - reptracker to 4,999,979 before hivemind massive-sync end at 5,000,024 -
match `README.md:618-649`.)

---

## 13. Cross-references & open threads for later parts

- **HAF KB**: `app_next_iteration`/stages (part 03 there), managed index
  registration, non-forking contexts, `operations_view`, query supervisor.
  Newly-found gap: `hive.create_custom_json_type_index` (contrib note filed
  2026-07-23).
- **hive-core KB**: operation semantics for everything part 04 will map
  (comment/vote/custom_json/delete_comment/... and the payout virtual ops).
- Open threads: exact table set + views (part 02); `massive_sync.sql` internals +
  mocking (part 03); the 4 custom_json domains incl. community start block
  37500000 rationale (part 04); per-method API verification incl. which of the 72
  branches are real vs deprecation stubs (parts 05-07); notification cache +
  `prune_notification_cache` (parts 02/04); the `hive.*` namespace (`get_info`,
  `db_head_state`) and api_limits (part 07).
