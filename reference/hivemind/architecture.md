# Hivemind: Architecture & Deployment (cheat sheet)

Anchor `1.28.6` (`cab9e328bf`). Depth: findings part 01.

## Dataflow

```
hived -> HAF (haf_block_log)                                [HAF KB]
           |  hive.app_next_iteration('hivemind_app')       Python: hive sync
           v
       hivemind_app schema (posts/votes/follows/...)
           |  hivemind_endpoints.* (PL/pgSQL)
           v
       PostgREST :8080  <-  openresty rewriter :80  <-  clients
```

## CLI (`hive`, default mode `sync`; `mocker` = test-data injector)

| Mode | Effect |
|------|--------|
| `build_schema` | Create schemas + tables + runtime SQL, no sync |
| `upgrade_schema` | Run upgrade scripts, then build runtime SQL |
| `sync` | The consume loop |
| `status` | DbState status dump |
| `completion` | Bash completion file |
| `server` | REMOVED - raises (use container `server` -> start_postgrest.sh) |

Key options (CLI > ENV > `./hive.conf`): `--database-url` (`DATABASE_URL`),
`--test-max-block` (stop + finalize indexes), `--community-start-block`
(d=37500000), `--reptracker-schema-name` (d=`reptracker_app`), `--max-batch`
(d=NULL -> stage decides), `--max-workers` (d=6), `--prometheus-port`,
`--log_explain_queries` (superuser only), mock paths
(`MOCK_BLOCK_DATA_PATH`/`MOCK_VOPS_DATA_PATH`). DB layer: psycopg2 (SA-style
`:param` converted internally). Source: `hive/conf.py`, `hive/cli.py`.

## Docker images

| Image | Contents |
|-------|----------|
| `instance` | python:3.14-slim base, uid-1000 `hivemind` user, venv+wheel, PostgREST v12.0.2 binary (via pinned common-ci-configuration image), scripts as `/home/hivemind/app`, mock data, bundled reptracker+hafah apps; `STOPSIGNAL SIGINT` |
| `postgrest-rewriter` | openresty 1.27.1.1-alpine + `hivemind_nginx.conf.template` + `rewrite_rules.conf`; :80 proxy -> `hivemind-postgrest-server:8080` (hardcoded upstream name), :81 `/health` -> 204 |

Entrypoint commands (`docker_entrypoint.sh`): `setup`/`install_app`
(setup_postgres -> [--with-apps: reptracker+hafah] -> install_app ->
[--add-mocks] -> `hive build_schema`|`upgrade_schema`), `sync`
(optional `--install-app` first; writes healthcheck start marker), `server`
(exec start_postgrest.sh), `uninstall_app`. Healthcheck: block processed in
last 60 s OR head == HAF irreversible head.

Deployment: haf_api_node (`HIVE_API_NODE_VERSION` selects both images).
Order: **HAF -> reputation_tracker -> hivemind indexer -> server + rewriter**.

## Roles, schemas, database settings

| Item | Value |
|------|-------|
| Roles | `hivemind` (HAF app role; schema owner; sync; PostgREST anon), `hivemind_user` (query; base group `hive_applications_group`; optional `--statement-timeout`) |
| Schemas | `hivemind_app` (data), `hivemind_endpoints` (API), `hivemind_postgrest_utilities` (helpers) - all owned by `hivemind` |
| DB settings at install | `join_collapse_limit`=16, `from_collapse_limit`=16, `jit`=off (database-wide; upgrade ASSERTS them), `GRANT CREATE ON DATABASE` to hivemind |
| Extensions | `plpython3u` REQUIRED (search preprocessor); `pg_search` optional (BM25) |
| Cross-app grants | reptracker_owner+user -> hivemind; hafah_owner -> hivemind, hafah_user -> hivemind_user (UNCONDITIONAL - HAfAH must exist) |
| Uninstall | `hive.app_remove_context` + DROP SCHEMA hivemind_app CASCADE + DROP OWNED BY/ROLE hivemind |

## HAF integration

- Context `hivemind_app` = schema name; **non-forking** (irreversible only);
  re-set non-forking on every start.
- Stages: `MASSIVE_WITHOUT_INDEXES` (> 201600 behind, batch 1000),
  `MASSIVE_WITH_INDEXES` (> 101, batch 1000), `live` - plus HAF's
  `wait_for_haf`.
- At sync start: `hive.create_custom_json_type_index(ARRAY['follow','reblog',
  'community','notify'])` (HAF 1.28.6 typed-custom_json partial index).
- 41 indexes registered via `hive.app_register_index_dependency`; FKs via
  `hive.app_save_and_drop_foreign_keys`/`app_restore_foreign_keys`.

## Serving path

| Route (rewriter :80) | Target |
|----------------------|--------|
| `^/blog/reblogs` | `/rpc/get_reblogs` |
| `^/accounts/([^/]+)/operations` | `/rpc/get_ops_by_account?account-name=$1` |
| everything else | `/rpc/home` (JSON-RPC) |

PostgREST env (`start_postgrest.sh` / image ENV): schema `hivemind_endpoints`,
anon role `hivemind`, pool 20, admin port 3001, `PGRST_DB_ROOT_SPEC=home`
(image ENV; GET / = OpenAPI). Version stamped into the OpenAPI at image build.

## Gotchas (see hub README for the full list)

- No `haf` submodule at 1.28.6 - CI finds the HAF image; helper scripts are
  fetched from common-ci-configuration (default ref `develop` - pin for
  reproducible manual builds).
- `hive_state` carries version/git-rev stamps; `hive.get_info` exposes them.
- In-repo README/CLAUDE.md lag reality (haf submodule, SQLAlchemy, py3.10,
  `hive server`) - findings part 01 section 12 has the discrepancy table.
