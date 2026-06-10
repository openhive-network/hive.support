# Findings: API Layer — Available Endpoints and Data Access

## Summary

The Hive blockchain node (hived) exposes its functionality through a modular plugin system built on the **AppBase** framework. API plugins register methods with a central **JSON-RPC 2.0** router, accessible via HTTP, HTTPS, WebSocket, and Unix socket transports.

**Key numbers verified from source (commit `10ac0ce94f`):**
- **18 API plugins** in `libraries/plugins/apis/` register JSON-RPC methods (excluding `test_api`, a test-only plugin), **plus the `jsonrpc` introspection API** built into the `json_rpc` plugin → **19 method namespaces**.
- **198 registered `(api, method)` endpoints** total: 196 declared via `DECLARE_API` across the 18 plugins + 2 from `jsonrpc`. (condenser_api duplicates much functionality semantically, but every method is a distinct registered endpoint string.)
- **7+ non-API infrastructure plugins** (chain, p2p, witness, market_history, reputation, transaction_status, state_snapshot, …) plus testnet-only tooling (colony, queen).
- **4 transport types** (HTTP, HTTPS, WebSocket, Unix socket).
- JSON-RPC 2.0 compliant with custom error codes (-32000 to -32003 + the standard set).
- Two-phase API registration (proxy during init, finalized at startup) + an "early" registration path for status APIs.
- **No per-client rate limiting** anywhere in the webserver/JSON-RPC layer — the only concurrency control is a fixed thread pool (default 16).

> **Count corrections vs. earlier revisions of this doc and `reference/api.md`:** condenser_api has **62** methods (not 57 — the prior tables also omitted `get_open_orders`); debug_node_api has **12** (not 11); total registered endpoints are **~198** (not ~175). See *Discrepancies* and *Reference Impacts*.

Per-plugin method counts (robust parenthesis-aware count of each `DECLARE_API` block, comments stripped):

| Plugin | Methods | | Plugin | Methods |
|--------|---------|---|--------|---------|
| condenser_api | 62 | | reputation_api | 1 |
| database_api | 51 | | rewards_api | 1 |
| wallet_bridge_api | 35 | | transaction_status_api | 1 |
| debug_node_api | 12 | | network_broadcast_api | 1 |
| rc_api | 7 | | account_by_key_api | 1 |
| market_history_api | 7 | | node_status_api | 1 |
| account_history_api | 4 | | app_status_api | 1 |
| network_node_api | 4 | | chain_api | 1 |
| block_api | 3 | | jsonrpc (built-in) | 2 |
| witness_api | 3 | | **TOTAL** | **198** |

---

## Plugin Architecture

### AppBase Framework

**Source:** `libraries/appbase/` (a git submodule pinned at `bc76409c50975449528180ae86f53c51d9d21f96`; not checked out in the worktree — read from the pinned object store).

All plugins inherit from `appbase::plugin<Impl>` (CRTP pattern). The framework manages:

- **Plugin registration** via `APPBASE_PLUGIN_REQUIRES((dep1)(dep2))` (`appbase/include/appbase/plugin.hpp:10-16`) — each listed dependency is registered through `get_app().register_plugin<elem>()`.
- **Dependency resolution** — initializing a plugin recursively initializes its dependencies *first* (`appbase/include/appbase/application.hpp:274-286`, `plugin::initialize` calls `plugin_for_each_dependency(...)` before `plugin_initialize`). Dependencies flow **API plugin → core**, never the reverse: enabling `chain` does not pull in `database_api`, but enabling `condenser_api` pulls in `database_api → json_rpc → chain → webserver`.
- **Lifecycle management** — states: `registered` → `initialized` → `started` → `stopped`.

**Plugin lifecycle hooks:**
1. `plugin_initialize(options)` — Setup resources, register APIs (into `proxy_data`)
2. `plugin_startup()` — Begin active processing
3. `plugin_finalize_startup()` — Post-startup actions (json_rpc moves `proxy_data` → `data` here; API plugins resolve their soft dependencies here via `api_startup()`)
4. `plugin_pre_shutdown()` — Ordered cleanup (webserver closes first, then p2p, then others)
5. `plugin_shutdown()` — Final cleanup

**Registration is build-time discovery, not a curated list.** `hive::plugins::register_plugins(theApp)` (called at `programs/hived/main.cpp:108`) is generated at build time from a Jinja2 template (`libraries/manifest/templates/plugins/mf_plugins.cpp.j2:14-16`) that emits one `app.register_plugin<...>()` per plugin discovered under `libraries/plugins/` (every directory shipping a `plugin.json`; discovery in `libraries/manifest/CMakeLists.txt:17-39` via `programs/build_helpers/hive_build_helpers/list_plugins.py:8-13`). Registration only makes a plugin *available* (exposes its config options); it does **not** start it.

### Default Plugin Configuration (three tiers)

A common misconception is that hived "enables the API by default." It does not. With **no `--plugin` flags and no/empty config**, only a minimal set runs (`programs/hived/main.cpp`):

1. **Always loaded** (hardcoded, config-independent): `chain`, `p2p`, `webserver` — passed to `theApp.initialize<...>()` at `main.cpp:126-131` (the unconditional `autostart_plugins`, `appbase/application.cpp:329-331`). `json_rpc` is pulled in transitively (`chain_plugin` requires `webserver`+`json_rpc`, `chain_plugin.hpp:43`; `webserver_plugin` requires `json_rpc`, `webserver_plugin.hpp:36`).
2. **Default-enabled but config-overridable**: `witness`, `account_by_key`, `account_by_key_api`, `state_snapshot` — `theApp.set_default_plugins<...>()` at `main.cpp:117-122`. This stores plugin name strings (`application.hpp:174-175`) that become the **default value of the `--plugin` option** (`application.cpp:183-184`). The only `set_default_plugins` caller in the production binary.
3. **Registered-but-off**: every other built plugin — all the read APIs (`database_api`, `condenser_api`, `block_api`, `account_history*`, `network_broadcast_api`, `rc_api`, `wallet_bridge_api`, `market_history*`, …). They start only if named in `--plugin`/config or pulled in as a dependency.

So a bare hived is **not a useful API node** — it has `witness` and `account_by_key_api` but none of `database_api`/`condenser_api`/`account_history_api`/`block_api`/`network_broadcast_api`. A fresh auto-generated `config.ini` is written **commented-out** (`application.cpp:483-530`), so it does not override the built-in default.

**Deployment-level defaults differ from the binary's defaults.** The useful API plugin set comes from shipped sample configs, not the C++ defaults:
- `contrib/config-for-docker.ini:6-26` enables `webserver p2p json_rpc`, `database_api condenser_api`, `witness`, `account_by_key(_api)`, `account_history_rocksdb` + `account_history_api`, `transaction_status(_api)`, `block_api network_broadcast_api rc_api`, `state_snapshot`, `wallet_bridge_api`, `node_status_api`.
- `contrib/config-for-ahnode.ini` adds `market_history(_api)` and `reputation(_api)`.
- `doc/example_config.ini:3-21` is similar (no `wallet_bridge`/market in some variants).
- The official Docker image copies `doc/example_config.ini` to `/home/hived/datadir/example_config.ini` (**not** `config.ini`) — `Dockerfile:161`; the entrypoint (`docker/docker_entrypoint.sh:79-81`) does not pass `--plugin`, so operators must supply their own `config.ini` or fall back to the bare 8-plugin default.

### JSON-RPC Framework

**Source:** `libraries/plugins/json_rpc/`

The `json_rpc_plugin` is the central API registry. It maintains a map `api_name -> {method_name -> handler}` (`data._registered_apis`), the flat list of `"api.method"` strings (`data._methods`), and the per-method signatures (`data._method_sigs`).

**Two-phase registration (race-condition guard):**
1. During `plugin_initialize()`: `JSON_RPC_REGISTER_API` inserts methods into `proxy_data` (temporary).
2. During `plugin_finalize_startup()`: `proxy_data._registered_apis/_methods/_method_sigs` move into the live `data` (`json_rpc_plugin.cpp:~298-310`). Methods become callable only here, after all dependencies are ready.
3. **Early path:** `JSON_RPC_REGISTER_EARLY_API` registers directly to `data`, making the API callable during init/sync. Used by `app_status_api` (`app_status_api.cpp:58`) and `node_status_api` (`node_status_api.cpp:36`) — health/sync probes that must answer before finalize. The `jsonrpc` API itself registers in `json_rpc_plugin_impl::initialize()` (`json_rpc_plugin.cpp:316`).

**Request routing (`json_rpc_plugin::call` → `rpc` → `rpc_jsonrpc`):**
```
HTTP/WS body (JSON string)
  -> json_rpc_plugin::call(message)          [json_rpc_plugin.cpp:647-699]
     - fc::json::from_string(..., full validation)   [:652]
     - if array -> batch: iterate, rpc(element) each [:656-666]
     - else single rpc(element)                      [:678]
  -> rpc(variant)                            [:526-587]  (outer id/error isolation)
  -> rpc_jsonrpc(request, response)          [:416-524]
     - validate jsonrpc=="2.0"                        [:421]
     - process_params(method,...) -> find_api_method  [:438, :353-393, :341-351]
     - (*call)(func_args)  (handler executes)         [:455]
  -> json_rpc_response {jsonrpc, result|error, id}
```

**Batch requests are supported:** a top-level JSON array is processed element-by-element and the results returned as an array (`json_rpc_plugin.cpp:656-666`). Each element is an independent JSON-RPC call.

**Two calling conventions** (`process_params`, `json_rpc_plugin.cpp:353-393`):

Convention 1 — dotted method name (`method` split on `.`, must be exactly `api.method`):
```json
{"jsonrpc":"2.0","method":"database_api.get_dynamic_global_properties","params":{},"id":1}
```
Convention 2 — generic `"call"` with positional array `["api","method", args?]` (size 2 or 3):
```json
{"jsonrpc":"2.0","method":"call","params":["database_api","get_dynamic_global_properties",{}],"id":1}
```
If `params` is omitted it defaults to `{}` (`:376`, `:389`).

**JSON-RPC error codes and where they are actually produced** — the constants live in `json_rpc_plugin.hpp`; the table below also records the precise emission site, because the runtime mapping has subtleties:

| Code | Constant | Emitted when (file:line) |
|------|----------|--------------------------|
| -32700 | JSON_RPC_PARSE_ERROR | Top-level JSON parse / bad_cast of the message (`:567`, `:571`) |
| -32600 | JSON_RPC_INVALID_REQUEST | `jsonrpc` ≠ "2.0" (`:518`), missing `method` member (`:513`), or bad `id` type (`:411`) |
| -32601 | JSON_RPC_METHOD_NOT_FOUND | Outer assert handler (`:508`) |
| -32602 | JSON_RPC_INVALID_PARAMS | (defined; param validation) |
| -32603 | JSON_RPC_INTERNAL_ERROR | (defined) |
| -32000 | JSON_RPC_SERVER_ERROR | Uncaught `fc::exception`/`std::exception` in `rpc` (`:554/558/575`) |
| -32001 | JSON_RPC_NO_PARAMS | `"call"` without a `params` member (`:503`) |
| -32002 | JSON_RPC_PARSE_PARAMS_ERROR | Failure inside `process_params`/`find_api_method` (`:443`) |
| -32003 | JSON_RPC_ERROR_DURING_CALL | Exception thrown by the handler, incl. `FC_ASSERT` and `chainbase::lock_exception` (`:494`, `:498`) |

> **Subtlety worth knowing:** `find_api_method` throws an `FC_ASSERT` ("Could not find API/method", `:345/:348`) which is invoked from `process_params` inside the inner `try` whose `catch` maps to **-32002 (PARSE_PARAMS_ERROR)** at `:443` — so an unknown api/method is reported through the params-error path, while the nominal -32601 handler at `:508` sits on the outer `try`. Treat both -32002 and -32601 as "method/params resolution failed." Any handler-level `FC_ASSERT` (e.g. `"market_history_api_plugin not enabled."`) surfaces as **-32003**.

**Method-specific legacy-serialization fallback (NOT a blanket dual-format):** the handler is normally called once. If it throws `fc::bad_cast_exception` **and** the method is exactly `network_broadcast_api.broadcast_transaction` or `database_api.verify_authority`, the call is retried under a `mode_guard(transaction_serialization_type::legacy)` (`json_rpc_plugin.cpp:457-489`). All other methods do not get this retry at the JSON-RPC layer. (condenser_api's own broadcast methods are lockless and handle their dual serialization internally.)

### API Method Declaration Pattern & Locking

**Source:** `libraries/plugins/json_rpc/include/hive/plugins/json_rpc/utility.hpp`

Each API class uses `DECLARE_API((method_a)(method_b))` (`utility.hpp:27-34`), which generates `method_a_return method_a(const method_a_args&, bool lock=false)` plus a `for_each_api()` visitor used for registration. Implementations bind each method through one of three locking macros (`utility.hpp:45-85`):

- `DEFINE_READ_APIS` — when `lock==true`, runs under `db.with_read_lock([...], fc::seconds(1))` — a **1-second read-lock timeout** (`utility.hpp:50`).
- `DEFINE_WRITE_APIS` — `db.with_write_lock([...])`, **no timeout** (`utility.hpp:63`).
- `DEFINE_LOCKLESS_APIS` — no locking; for stateless or self-locking methods (`utility.hpp:74-75`).

The `lock` flag is `true` when a method is invoked through the JSON-RPC router (top-level call) and `false` when one API calls another internally (e.g. condenser delegating to database_api), so the lock is taken exactly once. Example: condenser's `DEFINE_LOCKLESS_APIS` set (`condenser_api.cpp:1272-1282`) covers `get_version`, `get_config`, `get_account_references`, both `broadcast_transaction*`, `get_market_history_buckets`, `get_ops_in_block`, `get_account_history`, `get_transaction` — these either delegate to a self-locking API or hit RocksDB/p2p, so the condenser layer adds no lock; everything else is a read API.

### WebServer Plugin — Transports, Concurrency, No Rate Limiting

**Source:** `libraries/plugins/webserver/webserver_plugin.cpp`

Config options (`set_program_options`, `:737-748`):

| Flag | Default | Notes |
|------|---------|-------|
| `--webserver-http-endpoint` | (unset) | No default port; bound only if supplied |
| `--webserver-https-endpoint` | (unset) | Requires cert + key flags (asserted `:763-764`) |
| `--webserver-ws-endpoint` | (unset) | WebSocket |
| `--webserver-unix-endpoint` | (unset) | Unix-socket HTTP; **always permessage-deflate-enabled** server type (`:156`) |
| `--webserver-ws-deflate` | **false** | RFC-7692 permessage-deflate for WS, only if client requests it (`:743`) |
| `--webserver-thread-pool-size` | **16** | "Number of threads used to handle queries"; asserted `>0` (`:744-745, :755`) |
| `--webserver-https-certificate-file-name` | (unset) | HTTPS only |
| `--webserver-https-key-file-name` | (unset) | HTTPS only |

**Concurrency model — fixed thread pool draining one shared queue.** `prepare_threads()` (`:322-329`) spins up `thread_pool_size` worker threads (named `"api"`), all running the same `thread_pool_ios` io_context, kept alive by a `work_guard`. Acceptor threads (one per endpoint: ws/http/unix, `:284-294`) read the request, then hand work to the pool via `boost::asio::post(thread_pool_ios, ...)` (HTTP `:626`, WS `:574`, unix `:686`). Each worker invokes `api->call(body)` (`:634`, `:584`).

**No rate limiting exists.** An exhaustive search (`rate|throttle|max_connection|max_message|max_body|connection_limit`) across `webserver/` and `json_rpc/` finds nothing; the only `fc::rate_limiting_group` in the tree is in the **P2P** layer (`libraries/net/node.cpp:564`), which throttles inter-node bandwidth, not API clients. `boost::asio::post` enqueues unconditionally — when all N workers are busy, requests **queue indefinitely** with no rejection or backpressure. The only effect of saturation is **diagnostic logging** via `LOG_DELAY`/`LOG_DELAY_EX` (`utility.hpp:87-99`): warnings at 2 s ("begin processing"), 4 s ("get request_body"), 10 s ("process API call") — `webserver_plugin.cpp:627/630/676`. hived sets no max-body-size or max-message-size; any such cap comes from the bundled websocketpp defaults (not overridden) or an upstream reverse proxy.

**Pre-shutdown ordering** (appbase `pre_shutdown_order` enum, pinned `bc76409c`): `basic_order=0`, `p2p_order=1`, `webserver_order=2`, `colony_order=3`. The pre-shutdown multiset iterates **highest-first**, so the order is colony(3) → webserver(2) → p2p(1) → basic(0). The webserver (`set_pre_shutdown_order(webserver_order)`, `webserver_plugin.cpp:730`) drains in-flight API calls **before** p2p is torn down — necessary because `network_broadcast_api` calls into p2p. `stop_webserver()` stops the worker pool then joins acceptor threads (`:540-566`).

---

## API Reference

### condenser_api (Legacy API) — 62 methods

**Plugin name:** `"condenser_api"` · **Source:** `libraries/plugins/apis/condenser_api/`
**Purpose:** Legacy API compatible with Steem-era clients. Aggregates data from underlying APIs and converts to legacy format (`legacy_asset` string symbols like `"1.000 HIVE"`, `legacy_price`, etc.).

**Hard dependencies (only):** `json_rpc`, `database_api` (`condenser_api_plugin.hpp:17`). **Soft dependencies** are resolved at `api_startup()` via `find_plugin<>()` and may be absent: `block_api`, `account_history_api`, `account_by_key_api`, `network_broadcast_api`, `p2p`, `reputation_api`, `market_history_api`, `rc_api`, `metadata` (`condenser_api.cpp:1213-1270`). A method needing an absent soft dependency throws a **clear** `FC_ASSERT("X_plugin not enabled.")` → JSON-RPC -32003 (see *Discrepancies #3*).

**All methods accept `vector<variant>` (positional arguments).**

#### Version & Configuration (3)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_version` | (none) | `{blockchain_version, hive_revision, fc_revision, chain_id}` | lockless |
| `get_config` | (none) | variant_object | Legacy symbol substitutions applied; lockless |
| `get_hardfork_version` | (none) | hardfork_version string | e.g. "1.27.0" |

#### Global State (5)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_dynamic_global_properties` | (none) | extended_dynamic_global_properties | Head block, supplies, rates, timing |
| `get_chain_properties` | (none) | api_chain_properties | Median witness props |
| `get_current_median_history_price` | (none) | legacy_price | HBD/HIVE price feed |
| `get_feed_history` | (none) | api_feed_history_object | min/max/median price history |
| `get_next_scheduled_hardfork` | (none) | scheduled_hardfork | Next HF version and time |

#### Witness Data (9)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_active_witnesses` | (include_future?: bool) | vector\<account_name\> | |
| `get_witness_schedule` | (include_future?: bool) | api_witness_schedule_object | Shuffle list, virtual times, weights |
| `get_witnesses` | (ids: vector\<witness_id\>) | vector\<optional\<api_witness_object\>\> | By numeric ID |
| `get_witness_by_account` | (account: string) | optional\<api_witness_object\> | |
| `get_witnesses_by_vote` | (start: string, limit: uint32) | vector\<api_witness_object\> | Descending vote order |
| `lookup_witness_accounts` | (lower_bound: string, limit: uint32) | vector\<string\> | Name pagination |
| `get_witness_count` | (none) | uint64 | |
| `get_reward_fund` | (name: string) | api_reward_fund_object | e.g. "post" |
| `list_rc_direct_delegations` | (start: variant, limit: uint32) | vector\<rc_direct_delegation_api_object\> | Needs rc_api |

#### Account Data (11)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_accounts` | (names: vector\<string\>, delayed_votes?: bool) | vector\<extended_account\> | Reputation field populated only if reputation_api enabled (`:379`) |
| `lookup_account_names` | (names: vector\<string\>, delayed_votes?: bool) | vector\<optional\<api_account_object\>\> | Nulls for missing |
| `lookup_accounts` | (lower_bound: string, limit: uint32) | set\<string\> | `FC_ASSERT(limit <= 1000)` (`:435`) |
| `get_account_count` | (none) | uint64 | |
| `get_account_references` | (account) | — | **PERMANENTLY BROKEN** — `FC_ASSERT(false, "...Needs to be refactored for Hive.")` (`condenser_api.cpp:397`) |
| `get_account_reputations` | (name: string, limit?: uint32=1000) | vector\<account_reputation\> | Needs reputation_api (asserts if absent) |
| `get_key_references` | (keys: vector\<public_key\>) | vector\<vector\<string\>\> | Needs account_by_key_api |
| `get_owner_history` | (account: string) | vector\<owner_authority_history\> | |
| `get_recovery_request` | (account: string) | optional\<recovery_request\> | |
| `find_rc_accounts` | (accounts: vector\<string\>) | vector\<rc_account_api_object\> | Needs rc_api |
| `list_rc_accounts` | (start: string, limit: uint32) | vector\<rc_account_api_object\> | Needs rc_api |

#### Vesting & Delegation (5)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_vesting_delegations` | (delegator, start, limit?) | vector\<vesting_delegation\> | **default limit 100** (`:561`) |
| `get_expiring_vesting_delegations` | (delegator, start, limit?) | vector\<vesting_delegation_expiration\> | **default limit 100** (`:582`) |
| `get_withdraw_routes` | (account, type?) | vector\<withdraw_vesting_route\> | outgoing/incoming/all |
| `get_savings_withdraw_from` | (account) | vector\<savings_withdraw\> | |
| `get_savings_withdraw_to` | (account) | vector\<savings_withdraw\> | |

#### Escrow & Conversions (4)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_escrow` | (from, escrow_id) | optional\<escrow_object\> | |
| `get_conversion_requests` | (account) | vector\<convert_request\> | HBD→HIVE |
| `get_collateralized_conversion_requests` | (account) | vector\<collateralized_convert_request\> | HIVE→HBD |
| `find_recurrent_transfers` | (account) | vector\<recurrent_transfer\> | |

#### Blockchain Data (5)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_block_header` | (block_num) | optional\<block_header\> | Needs block_api (asserts, `:231`) |
| `get_block` | (block_num) | optional\<legacy_signed_block\> | Needs block_api (asserts, `:244`) |
| `get_ops_in_block` | (block_num, only_virtual?) | vector\<api_operation_object\> | Needs account_history_api (asserts, `:257`); lockless |
| `get_account_history` | (account, from: int64, limit, op_filter_low?, op_filter_high?) | map\<uint32, api_operation_object\> | Bitmask filtering; needs account_history_api; lockless |
| `is_known_transaction` | (txid) | bool | |

#### Transaction Operations (6)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_transaction` | (txid: hex) | annotated_signed_transaction | Needs account_history_api (`:760`); lockless |
| `get_transaction_hex` | (trx) | hex_string | |
| `get_required_signatures` | (trx, available_keys) | set\<pubkey\> | |
| `get_potential_signatures` | (trx) | set\<pubkey\> | |
| `verify_authority` | (trx) | bool | |
| `verify_account_authority` | (account, signers, level?) | bool | owner/active/posting |

#### Voting & Content (4)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_active_votes` | (author, permlink) | vector\<vote_state\> | Voter, weight, rshares, percent, time |
| `list_proposals` | (start, limit, order, direction?, status?, last_id?) | vector\<api_proposal_object\> | DHF proposals; `args.size() 3–6` |
| `find_proposals` | (ids: vector\<int64\>) | vector\<api_proposal_object\> | |
| `list_proposal_votes` | (start, limit, order, direction?, status?) | vector\<proposal_vote_object\> | `args.size() 3–5` |

#### Market & Orders (8)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_open_orders` | (account) | vector\<api_limit_order_object\> | **Was missing from earlier tables.** Reads `limit_order_index, by_account` directly (`:733`) |
| `get_ticker` | (none) | ticker | Needs market_history_api (asserts) |
| `get_volume` | (none) | volume | Needs market_history_api |
| `get_order_book` | (depth?: uint32) | order_book | **default depth 500** (`:962`); needs market_history_api |
| `get_trade_history` | (start, end, limit?) | vector\<market_trade\> | **default limit 1000** (`:970`) |
| `get_recent_trades` | (limit?) | vector\<market_trade\> | **default 1000** (`:985`) |
| `get_market_history` | (bucket_secs, start, end) | vector\<bucket_object\> | OHLCV; needs market_history_api |
| `get_market_history_buckets` | (none) | flat_set\<uint32\> | lockless |

#### Transaction Broadcast (2)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `broadcast_transaction` | (trx) | void | Needs network_broadcast_api (`:854`); async; lockless |
| `broadcast_transaction_synchronous` | (trx) | {id, block_num, trx_num, rc_cost, expired} | Needs network_broadcast_api + p2p (`:863-864`); blocks until confirmed/expired; lockless |

---

### database_api (Direct State Access) — 51 methods

**Plugin name:** `"database_api"` · **Source:** `libraries/plugins/apis/database_api/`
**Purpose:** Comprehensive direct access to chain state objects. Find/list pattern: `find_*` = direct lookup by key, `list_*` = ordered pagination over an index.

**Pagination:** `{start: variant, limit: uint32, order: sort_order_type}`. **`DATABASE_API_SINGLE_QUERY_LIMIT = 1000`**, enforced via `FC_ASSERT(0 < limit && limit <= 1000, "limit not set or too big")` (e.g. `database_api_financial.cpp:24,92,182,266,328`).

#### Global Properties (6)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_config` | void | variant_object | All consensus config constants |
| `get_version` | void | variant_object | Version + chain_id |
| `get_dynamic_global_properties` | void | api_dynamic_global_property_object | 70+ fields |
| `get_witness_schedule` | include_future?: bool | api_witness_schedule_object | |
| `get_hardfork_properties` | void | api_hardfork_property_object | HF history/versions |
| `get_reward_funds` | void | vector\<api_reward_fund_object\> | All reward funds |

#### Witnesses (4)
| Method | Parameters | Returns | Order options |
|--------|-----------|---------|---------------|
| `list_witnesses` | start, limit, order | vector\<api_witness_object\> | by_name, by_vote_name, by_schedule_time |
| `find_witnesses` | owners: vector\<string\> | vector\<api_witness_object\> | — |
| `list_witness_votes` | start, limit, order | vector\<api_witness_vote_object\> | by_account_witness, by_witness_account |
| `get_active_witnesses` | include_future?: bool | witnesses + optional future_witnesses | — |

#### Accounts (24 — 12 find/list pairs)
| Pair | find_ Parameters | list_ Order Options | Object |
|------|-----------------|-------------------|--------|
| accounts | names: vector\<string\> | by_name, by_proxy, by_next_vesting_withdrawal | api_account_object |
| owner_histories | owner: string | by_account | api_owner_authority_history_object |
| account_recovery_requests | accounts | by_account, by_expiration | api_account_recovery_request_object |
| change_recovery_account_requests | accounts | by_account, by_effective_date | api_change_recovery_account_request_object |
| escrows | from: string | by_from_id, by_ratification_deadline | api_escrow_object |
| withdraw_vesting_routes | account + order | by_withdraw_route, by_destination | api_withdraw_vesting_route_object |
| savings_withdrawals | account | by_from_id, by_complete_from_id, by_to_complete | api_savings_withdraw_object |
| vesting_delegations | account | by_delegation | api_vesting_delegation_object |
| vesting_delegation_expirations | account | by_expiration, by_account_expiration | api_vesting_delegation_expiration_object |
| hbd_conversion_requests | account | by_account, by_conversion_date | api_convert_request_object |
| collateralized_conversion_requests | account | by_account, by_conversion_date | api_collateralized_convert_request_object |
| decline_voting_rights_requests | accounts | by_account, by_effective_date | api_decline_voting_rights_request_object |

#### Content (1)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_comment_pending_payouts` | vector\<{author, permlink}\> | vector\<comment_pending_payout_info\> | Cashout: rshares, votes, payout timing |

#### Market / Orders (3)
| Method | Parameters | Returns | Order options |
|--------|-----------|---------|---------------|
| `list_limit_orders` | start, limit, order | vector\<api_limit_order_object\> | by_price, by_account |
| `find_limit_orders` | account: string | vector\<api_limit_order_object\> | — |
| `get_order_book` | limit: uint32 | order_book {asks, bids} | — |

#### DHF / Proposals (3)
| Method | Parameters | Returns | Order options |
|--------|-----------|---------|---------------|
| `list_proposals` | start, limit, order, direction, status, last_id? | vector\<api_proposal_object\> | by_creator, by_start_date, by_end_date, by_total_votes |
| `find_proposals` | ids: vector\<int64\> | vector\<api_proposal_object\> | — |
| `list_proposal_votes` | start, limit, order, direction, status | vector\<api_proposal_vote_object\> | by_voter_proposal, by_proposal_voter |

**Proposal status filter enum:** `all`, `inactive`, `active`, `expired`, `votable`

#### Recurrent Transfers (1)
| Method | Parameters | Returns |
|--------|-----------|---------|
| `find_recurrent_transfers` | from: string | vector\<api_recurrent_transfer_object\> |

#### Authority / Validation (7)
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_transaction_hex` | trx | hex_string | |
| `get_required_signatures` | trx + available_keys | set\<pubkey\> | |
| `get_potential_signatures` | trx | set\<pubkey\> | |
| `verify_authority` | trx + pack_type? | bool | legacy-serialization retry path (`json_rpc_plugin.cpp:457-489`) |
| `verify_account_authority` | account + signers + level? | bool | owner/active/posting |
| `verify_signatures` | hash + signatures + required_auths | bool | Low-level check |
| `is_known_transaction` | txid | bool | |

---

### block_api — 3 methods
**Source:** `libraries/plugins/apis/block_api/`
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_block_header` | block_num: uint32 | optional\<block_header\> | Header only |
| `get_block` | block_num: uint32 | optional\<api_signed_block_object\> | Full block with transaction IDs |
| `get_block_range` | starting_block_num, count | vector\<api_signed_block_object\> | Batch retrieval |

### account_history_api — 4 methods
**Source:** `libraries/plugins/apis/account_history_api/` · Backend: `account_history_rocksdb` plugin.
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_ops_in_block` | block_num, only_virtual?, include_reversible? | multiset\<api_operation_object\> | |
| `get_transaction` | id: string, include_reversible? | annotated_signed_transaction | By tx ID hex |
| `get_account_history` | account, start: uint64=-1, limit: uint32=1000, include_reversible?, op_filter_low?, op_filter_high? | map\<uint32, api_operation_object\> | `FC_ASSERT(limit <= 1000)` and `start >= limit-1` (`account_history_api.cpp:125-126`) |
| `enum_virtual_ops` | block_range_begin, block_range_end, include_reversible?, group_by_block?, operation_begin?, limit?, filter? | ops + ops_by_block + next cursors | **`max_limit = 150,000`**, default 150,000 (`:259-267`) |

**Operation filter bitmasks** (`operation_filter_low`/`_high`): each operation type maps to a bit position by its operation ID; set bit = include that type. **`enum_virtual_ops` pagination** returns `next_block_range_begin` + `next_operation_begin` for cursor-based iteration.

### account_by_key_api — 1 method
**Source:** `libraries/plugins/apis/account_by_key_api/` · Requires `account_by_key` plugin.
| Method | Parameters | Returns |
|--------|-----------|---------|
| `get_key_references` | keys: vector\<public_key\> | vector\<vector\<account_name\>\> (accounts using each key) |

### network_broadcast_api — 1 method
**Source:** `libraries/plugins/apis/network_broadcast_api/`
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `broadcast_transaction` | trx, max_block_age?: int32 | void | Validates, accepts to mempool, broadcasts to peers. Legacy-serialization retry path (`json_rpc_plugin.cpp:457-489`) |

### rc_api (Resource Credits) — 7 methods
**Source:** `libraries/plugins/apis/rc_api/`
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_resource_params` | void | resource_names + resource_params + size_info | RC config |
| `get_resource_pool` | void | resource_pool | Current pool levels/fill states |
| `find_rc_accounts` | accounts: vector\<string\> | vector\<rc_account_api_object\> | RC mana, max_rc, delegated/received |
| `list_rc_accounts` | start: variant, limit | vector\<rc_account_api_object\> | |
| `list_rc_direct_delegations` | start: variant, limit | vector\<rc_direct_delegation_api_object\> | |
| `get_rc_stats` | void | variant_object | Aggregate RC statistics |
| `get_rc_operation_stats` | operation: string | {count, avg_cost_rc, resource_cost, resource_cost_share, resource_usage} | Per-op RC cost breakdown |

**rc_account_api_object:** account, rc_manabar (current_mana + last_update_time), max_rc_creation_adjustment, max_rc, delegated_rc, received_delegated_rc.
**RC resource types:** history (bytes), tokens, market (bytes), state (hbytes), execution (nanoseconds).

### market_history_api — 7 methods
**Source:** `libraries/plugins/apis/market_history_api/` · Requires `market_history` plugin.
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_ticker` | void | {latest, lowest_ask, highest_bid, percent_change, hive_volume, hbd_volume} | |
| `get_volume` | void | {hive_volume, hbd_volume} | 24h |
| `get_order_book` | limit: uint32=500 | {bids, asks} | |
| `get_trade_history` | start, end, limit=1000 | vector\<market_trade\> | |
| `get_recent_trades` | limit=1000 | vector\<market_trade\> | |
| `get_market_history` | bucket_seconds, start, end | vector\<bucket_object\> | OHLCV candles |
| `get_market_history_buckets` | void | flat_set\<uint32\> | Available bucket durations |

### wallet_bridge_api — 35 methods
**Source:** `libraries/plugins/apis/wallet_bridge_api/`
**Purpose:** Convenience wrapper aggregating read-only operations + broadcast from database_api, block_api, account_history_api, market_history_api, account_by_key_api, network_broadcast_api, rc_api into one API for wallets. **All methods accept `variant` (positional).** It omits market ticker/volume/trade methods, `get_block_header`, several vote/content methods, and some signature methods that condenser_api has — hence 35 vs 62.

| Method | Delegates To | | Method | Delegates To |
|--------|-------------|---|--------|-------------|
| get_version | database_api | | get_account | chain DB + metadata |
| get_witness_schedule | database_api | | get_accounts | chain DB + metadata |
| get_current_median_history_price | database_api | | get_transaction | account_history_api |
| get_hardfork_version | database_api | | list_witnesses | database_api |
| get_block | block_api | | get_witness | database_api |
| get_chain_properties | database_api | | get_conversion_requests | database_api |
| get_ops_in_block | account_history_api | | get_collateralized_conversion_requests | database_api |
| get_feed_history | database_api | | get_order_book | market_history_api |
| get_active_witnesses | database_api | | get_open_orders | chain DB |
| get_withdraw_routes | database_api | | get_owner_history | database_api |
| list_my_accounts | account_by_key_api + db | | get_account_history | account_history_api |
| list_accounts | chain DB | | list_proposals | database_api |
| get_dynamic_global_properties | database_api | | find_proposals | database_api |
| is_known_transaction | database_api | | list_proposal_votes | database_api |
| get_reward_fund | chain DB | | find_recurrent_transfers | database_api |
| broadcast_transaction_synchronous | chain_plugin + p2p | | find_rc_accounts | rc_api |
| broadcast_transaction | network_broadcast_api | | list_rc_accounts | rc_api |
| list_rc_direct_delegations | rc_api | | | |

**Key differences from database_api:** simplified return types; some methods (`get_account(s)`, `list_accounts`, `get_open_orders`, `get_reward_fund`) hit the chain DB directly; includes broadcasting; enriches accounts with metadata; dual serialization (legacy + HF26) for broadcast.

### witness_api — 3 methods
**Source:** `libraries/plugins/apis/witness_api/` · Witness nodes only. Controls fast-confirm mode. **Not** for querying witness data (that's database_api/condenser_api).
| Method | Returns |
|--------|---------|
| `enable_fast_confirm` | void |
| `disable_fast_confirm` | void |
| `is_fast_confirm_enabled` | bool |

### reputation_api — 1 method
**Source:** `libraries/plugins/apis/reputation_api/` · Requires `reputation` plugin.
| Method | Parameters | Returns |
|--------|-----------|---------|
| `get_account_reputations` | account_lower_bound: string, limit: uint32=1000 | vector\<{account, reputation}\> |

### rewards_api — 1 method
**Source:** `libraries/plugins/apis/rewards_api/`
| Method | Parameters | Returns |
|--------|-----------|---------|
| `simulate_curve_payouts` | curve: curve_id, var1: string | {recent_claims, payouts: vector\<{author, permlink, payout}\>} |

### transaction_status_api — 1 method
**Source:** `libraries/plugins/apis/transaction_status_api/` · Requires `transaction_status` plugin.
| Method | Parameters | Returns |
|--------|-----------|---------|
| `find_transaction` | transaction_id, expiration?: time | {status, block_num?, rc_cost?} |

**Status enum:** `unknown`, `within_mempool`, `within_reversible_block`, `within_irreversible_block`, `expired_reversible`, `expired_irreversible`, `too_old`.

### chain_api — 1 method
**Source:** `libraries/plugins/apis/chain_api/`
| Method | Parameters | Returns |
|--------|-----------|---------|
| `push_transaction` | trx | {success, error?} |

### node_status_api — 1 method (EARLY)
**Source:** `libraries/plugins/apis/node_status_api/` · Registered via `JSON_RPC_REGISTER_EARLY_API` (`node_status_api.cpp:36`) — answers during sync.
| Method | Returns |
|--------|---------|
| `get_node_status` | {last_processed_block_num, last_processed_block_time} |

### app_status_api — 1 method (EARLY)
**Source:** `libraries/plugins/apis/app_status_api/` · `JSON_RPC_REGISTER_EARLY_API` (`app_status_api.cpp:58`).
| Method | Returns |
|--------|---------|
| `get_app_status` | statuses (application-level health) |

### network_node_api — 4 methods
**Source:** `libraries/plugins/apis/network_node_api/` · Explicit-enable; P2P management.
| Method | Parameters | Returns |
|--------|-----------|---------|
| `get_info` | void | variant_object |
| `add_node` | endpoint | void |
| `set_allowed_peers` | allowed_peers: vector\<node_id\> | void |
| `get_connected_peers` | void | vector\<api_peer_status\> |

### debug_node_api — 12 methods (testing/debugging)
**Source:** `libraries/plugins/apis/debug_node_api/` · Requires the `debug_node` plugin. Compiles into mainnet binaries but is **absent from all shipped production configs** — enabled only on dev/testnet nodes. **Not for production use.**
| Method | Parameters | Returns |
|--------|-----------|---------|
| `debug_generate_blocks` | debug_key, count, skip?, miss_blocks? | {blocks} |
| `debug_generate_blocks_until` | debug_key, head_block_time, generate_sparsely? | {blocks} |
| `debug_get_head_block` | void | optional\<signed_block\> |
| `debug_get_witness_schedule` | void | api_witness_schedule_object |
| `debug_get_future_witness_schedule` | void | api_witness_schedule_object |
| `debug_get_hardfork_property_object` | void | api_hardfork_property_object |
| `debug_set_hardfork` | hardfork_id, hook_to_tx? | void |
| `debug_has_hardfork` | hardfork_id | {has_hardfork: bool} |
| `debug_get_json_schema` | void | {schema: string} | **dead** — returns empty (see *Open Questions #1*) |
| `debug_throw_exception` | throw_exception?: bool | void |
| `debug_set_vest_price` | vest_price, hook_to_tx? | void |
| `debug_fail_transaction` | tx_id | void |

> The 12th method (`debug_fail_transaction`) was missing from earlier "11 methods" counts. `debug_get_json_schema` is annotated in source as "the whole schema thing is (and pretty much always was) dead" (`debug_node_api.cpp:170`).

### jsonrpc (built-in) — 2 methods
**Source:** `libraries/plugins/json_rpc/` · Introspection.
| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_methods` | void | vector\<string\> | All registered `"api.method"` strings (`data._methods`, `json_rpc_plugin.cpp:319-322`) |
| `get_signature` | method: string | api_method_signature {args, ret} | Splits on `.`, returns the **default-constructed** arg/return structs reflected to variant — a field skeleton, not a JSON Schema (`:325-339`) |

### test_api (test-only)
**Source:** `libraries/plugins/apis/test_api/` — registers via `JSON_RPC_REGISTER_API(name())` (`test_api_plugin.cpp:10`) but is a unit-test fixture, not part of production nodes. Excluded from the 18-plugin / 198-endpoint counts above as a production API; listed here for completeness.

---

## Non-API Plugins

### chain_plugin (Core)
**Source:** `libraries/plugins/chain/` — the foundational plugin all others depend on. Maintains the chainbase database and consensus state; processes/validates blocks and transactions; registers block generators; provides `chain::database&` to other plugins; detects legacy vs HF26 transaction encoding. **Requires** webserver + json_rpc (`chain_plugin.hpp:43`).

### witness_plugin (Block Production)
**Source:** `libraries/plugins/witness/` — manages signing keys, schedules production by witness slot, tracks production conditions (not_synced, not_my_turn, no_private_key, low_participation, lag, …), and supports fast-confirm. `enable_queen_mode()` (`witness_plugin.cpp:570-577`) lets a single node represent every scheduled witness (testnet only — bypasses the identity check at `:335`). Requires chain + p2p.

### p2p_plugin (Network)
**Source:** `libraries/plugins/p2p/` — peer connections/discovery; broadcasts blocks and transactions; provides network info and peer status. Contains the only rate limiting in hived (`fc::rate_limiting_group`, `libraries/net/node.cpp:564`) — inter-node bandwidth, unrelated to API clients. Pre-shutdown order 1 (closes after webserver). Requires chain.

### market_history_plugin
**Source:** `libraries/plugins/market_history/` — tracks internal HIVE/HBD market: OHLCV buckets (configurable intervals) and fill-order history; hooks `fill_order` virtual ops. Backs market_history_api. Requires chain.

### reputation_plugin
**Source:** `libraries/plugins/reputation/` — computes account reputation from vote operations via `generic_custom_operation_interpreter`. Backs reputation_api. Requires chain.

### transaction_status_plugin
**Source:** `libraries/plugins/transaction_status/` — tracks tx lifecycle mempool→irreversible; hooks post_apply_transaction / pre/post_apply_block; prunes per `--transaction-status-block-depth`. Backs transaction_status_api. Requires chain.

### state_snapshot_plugin
**Source:** `libraries/plugins/state_snapshot/` — point-in-time state snapshots for fast sync; registers as a snapshot provider with chain. In the binary's default plugin set. Requires chain.

### colony (TESTNET-ONLY load generator) — corrected
**Source:** `libraries/plugins/colony/` — **NOT "parallel chain processing."** A **transaction load/stress generator**: worker threads fabricate and broadcast synthetic ARTICLE/REPLY/VOTE/TRANSFER/CUSTOM_JSON operations to fill max-sized blocks (`colony_plugin.cpp:42-50`, `:286-288`). **Exposes no API** (no `DECLARE_API`/`JSON_RPC_REGISTER_API` anywhere in the dir). **Mainnet-blocked:** `plugin_initialize` opens with `#ifndef USE_ALTERNATE_CHAIN_ID … FC_ASSERT(false, "Are you sure you want to use colony plugin on mainnet?")` (`:887-889`) — only runs on testnet/mirrornet builds. Requires chain (optionally uses p2p at runtime). Config: `colony-threads`, `colony-max-concurrency`, `colony-transactions-per-block`, per-op-type params, etc. (`:858-880`). The `colony_order` pre-shutdown constant (appbase enum value 3) is purely a **shutdown-sequencing hint** for its worker threads — *not* consensus significance.

### queen (TESTNET-ONLY instant block producer) — corrected
**Source:** `libraries/plugins/queen/` — **NOT "consensus leadership management."** A **single-node instant block producer** for benchmarking/CI: it produces a block as soon as the pending tx budget (block size / tx count) is exhausted rather than on the 3-second schedule (`queen_plugin.cpp:98-127`), using `skip_validate | skip_validate_invariants | skip_undo_block`. **Exposes no API.** **Mainnet-blocked:** `FC_ASSERT(false, "Queen plugin cannot be used with mainnet, since it has to turn off p2p")` (`:273-275`); it then disables p2p and calls `witness.enable_queen_mode()`. Requires chain + witness; reuses the witness plugin's witness/key config. Config: `queen-block-size`, `queen-tx-count` (`:256-266`).

### Other Notable Plugins
| Plugin | Purpose |
|--------|---------|
| `account_by_key` | Indexes accounts by public key (backs account_by_key_api) |
| `account_history_rocksdb` | RocksDB store for account history (backs account_history_api) |
| `debug_node` | Local block generation / hardfork manipulation (backs debug_node_api; dev/testnet) |
| `metadata` | Account metadata storage/enrichment (used by condenser/wallet_bridge) |
| `block_log_info` | Block log metadata and inspection |
| `block_data_export` / `stats_export` | Block/statistics export |
| `statsd` | StatsD metrics over UDP (the `STATSD_START_TIMER` macros throughout json_rpc) |
| `pacemaker` | Block-production timing control (testing) |
| `comment_cashout_logging` | Logs comment cashout events |

---

## Documentation & API Spec Generation

**Source:** `libraries/plugins/apis/documentation/` and `libraries/plugins/apis/api_generation/`

| File | Size | Content |
|------|------|---------|
| `documentation/openapi.json` | 1.35 MB | OpenAPI 3.1.0 spec — **215 paths, 507 component schemas**, `x-envelope: "jsonrpc-2.0"` |
| `documentation/walletapi.json` | 171 KB | OpenAPI 3.1.0 spec — 87 paths (cli_wallet API) |
| `documentation/Dockerfile` | — | Minifies + version-stamps the spec and serves it via busybox httpd |

**Both specs are hand-maintained, committed source artifacts — NOT auto-generated.** No build step, CMake target, or CI job *produces* them; every tool only *consumes* them:
- The `Dockerfile` (`:5-12,23-24`) only `jq`-minifies `openapi.json` and injects `info.version` (placeholder `"0.0.0-dev"`); it does not generate content.
- `api_generation/` is a downstream **client-package generator** (OpenAPI → Python `hiveio-api` via `datamodel-code-generator`); it *reads* `openapi.json` (`api_generation/.../generate_description.py:21`).
- CI jobs (`.gitlab-ci.yaml`): `generate-wax-spec` (`:207`) feeds `openapi.json` into the `@hiveio/wax-api-jsonrpc` npm generator; `generate_hived_flattened_openapi_definition` (`:1462-1474`) flattens it. All treat the spec as fixed input.

**The live-introspection path that *could* generate schemas is dead:**
- `debug_get_json_schema` (`debug_node_api.cpp:170`) is annotated "the whole schema thing is (and pretty much always was) dead"; it returns `_db.get_json_schema()` whose populating function `init_schema()` has its **entire body commented out** (`libraries/chain/database_init.cpp:118-174`), so it always returns empty.
- `jsonrpc.get_signature` returns *default-constructed* arg/return structs reflected to a variant (`json_rpc_plugin.cpp:325-339`) — a field skeleton, not a JSON Schema, and nothing converts it into the OpenAPI document.

**Drift risk: HIGH and unguarded.** The C++ arg/return structs are FC-reflected (so schemas *could* be derived) but nothing does so. No CI job regenerates or validates the spec against the node's actual responses or struct definitions. `openapi.json` has ~59 commits of granular hand-fixes ("Fix get_rc_stats…", "Rename block to header…"), and its 927 example blocks contain frozen real mainnet snapshots — direct evidence of manual maintenance. (Note: `libraries/wallet/api_documentation.cpp`, the cli_wallet interactive `help`, *is* genuinely auto-generated from Doxygen via Perl (`libraries/wallet/CMakeLists.txt:13-22`) — do not confuse it with the hand-written `walletapi.json`.)

---

## Key Discoveries

1. **condenser_api has 62 methods, not 57** — the prior count was wrong and the tables omitted `get_open_orders` (`condenser_api.hpp:993`). It remains a thick legacy adapter: it delegates to specialized APIs but applies `legacy_asset` serialization ("1.000 HIVE" vs NAI `{amount, precision, nai}`).

2. **Only `database_api` + `json_rpc` are hard dependencies of condenser_api** (`condenser_api_plugin.hpp:17`). Everything else (block, account_history, account_by_key, network_broadcast, reputation, market_history, rc, metadata, p2p) is resolved softly in `api_startup()` via `find_plugin<>()` (`condenser_api.cpp:1213-1270`) and may be null.

3. **Missing optional plugins produce CLEAR errors, not silent empties** — methods needing an absent soft dependency throw `FC_ASSERT("X_plugin not enabled.")` (e.g. `condenser_api.cpp:231,257,854,936,944`), surfaced as JSON-RPC -32003. The *only* silent degradation is reputation enrichment inside `get_accounts` (`if(_reputation_api)`, `:379`). This reverses the prior doc's claim.

4. **hived does not enable the API by default.** A bare node runs only chain/p2p/webserver/json_rpc + witness/account_by_key(_api)/state_snapshot (`main.cpp:117-131`). The useful API set comes from deployment `config.ini` files (`contrib/config-for-docker.ini`), not the binary.

5. **No per-client rate limiting exists** anywhere in the webserver/JSON-RPC layer; the sole concurrency control is the fixed thread pool (default 16, `webserver_plugin.cpp:744`). Under saturation, requests queue indefinitely via `boost::asio::post` — no rejection, only `LOG_DELAY` warnings at 2/4/10 s. (Reverse proxies must provide any throttling.)

6. **Two-phase + early registration.** Most APIs register into `proxy_data` during init and go live at finalize; `app_status_api` and `node_status_api` use `JSON_RPC_REGISTER_EARLY_API` so health/sync probes answer during replay.

7. **Three locking strategies, taken once.** Read APIs use a 1-second read-lock timeout (`utility.hpp:50`); write APIs an untimed write lock; lockless skip locking. The `lock` flag is true only for top-level JSON-RPC calls, so nested API delegation never double-locks.

8. **Legacy-serialization fallback is method-specific, not universal** — only `network_broadcast_api.broadcast_transaction` and `database_api.verify_authority` retry under a legacy `mode_guard` on `bad_cast` (`json_rpc_plugin.cpp:457-489`).

9. **`get_account_references` is permanently broken** — `FC_ASSERT(false, "...Needs to be refactored for Hive.")` (`condenser_api.cpp:397`), disabled since the Steem→Hive fork.

10. **OpenAPI/wallet specs are hand-maintained** with high, unguarded drift risk; the schema-introspection path (`debug_get_json_schema`) is dead code.

11. **`colony` and `queen` are testnet-only tools with no API** (load generator / instant block producer), both hard-blocked on mainnet via `FC_ASSERT`. Prior "parallel chain processing" / "consensus leadership" descriptions were wrong; `colony_order` is only a shutdown-ordering hint.

12. **Pagination limits are inconsistent and span two orders of magnitude** — defaults/caps range from 100 (condenser vesting-delegation defaults) to 500 (order book default) to 1000 (`DATABASE_API_SINGLE_QUERY_LIMIT`, most list methods) to **150,000** (`enum_virtual_ops` max). No unified standard.

13. **Batch JSON-RPC is supported** — a top-level array is processed element-by-element into a response array (`json_rpc_plugin.cpp:656-666`).

---

## Code References

| Topic | File | Key Lines |
|-------|------|-----------|
| Plugin base / requires macro | `libraries/appbase/include/appbase/plugin.hpp` | 10-16 (`APPBASE_PLUGIN_REQUIRES`), 35-42 (`pre_shutdown_order`) |
| App init / default plugins | `libraries/appbase/include/appbase/application.hpp` | 174-175 (`set_default_plugins`), 223 |
| App init / option default | `libraries/appbase/src/application.cpp` | 183-184, 329-343, 483-530 |
| hived startup | `programs/hived/main.cpp` | 108, 117-122, 126-131 |
| Plugin manifest generation | `libraries/manifest/templates/plugins/mf_plugins.cpp.j2` | 12-17; `libraries/manifest/CMakeLists.txt:17-39` |
| API declaration / locking macros | `libraries/plugins/json_rpc/include/hive/plugins/json_rpc/utility.hpp` | 27-34 (DECLARE_API), 45-85 (locking), 87-99 (LOG_DELAY) |
| JSON-RPC routing | `libraries/plugins/json_rpc/json_rpc_plugin.cpp` | 341-393 (find/process_params), 416-524 (rpc_jsonrpc), 526-587 (rpc), 647-699 (call/batch) |
| JSON-RPC registration & introspection | `libraries/plugins/json_rpc/json_rpc_plugin.cpp` | 274-316 (register/finalize), 319-339 (get_methods/get_signature) |
| Legacy-serialization retry | `libraries/plugins/json_rpc/json_rpc_plugin.cpp` | 457-489 |
| WebServer transports/pool | `libraries/plugins/webserver/webserver_plugin.cpp` | 322-329 (pool), 574/626/686 (post), 730 (shutdown order), 737-748 (options) |
| condenser methods (62) | `libraries/plugins/apis/condenser_api/include/.../condenser_api.hpp` | 957-1020 (DECLARE_API) |
| condenser soft-dep wiring | `libraries/plugins/apis/condenser_api/condenser_api.cpp` | 1213-1270 (api_startup), 1272-1282 (lockless set), 397 (broken method) |
| database_api methods (51) | `libraries/plugins/apis/database_api/include/.../database_api.hpp` | DECLARE_API block |
| database_api query limit | `libraries/plugins/apis/database_api/database_api_financial.cpp` | 24,92,182,266,328 (`DATABASE_API_SINGLE_QUERY_LIMIT`) |
| wallet_bridge_api (35) | `libraries/plugins/apis/wallet_bridge_api/include/.../wallet_bridge_api.hpp` | DECLARE_API block |
| account_history limits | `libraries/plugins/apis/account_history_api/account_history_api.cpp` | 125-126 (1000), 259-267 (150,000) |
| debug_node_api (12) | `libraries/plugins/apis/debug_node_api/include/.../debug_node_api.hpp` | 162-184; dead schema `debug_node_api.cpp:170` |
| EARLY-registered status APIs | `…/app_status_api/app_status_api.cpp:58`, `…/node_status_api/node_status_api.cpp:36` | |
| colony (testnet tool) | `libraries/plugins/colony/colony_plugin.cpp` | 42-50, 286-288, 858-880, 887-889 |
| queen (testnet tool) | `libraries/plugins/queen/queen_plugin.cpp` | 98-127, 256-266, 273-275 |
| OpenAPI spec (hand-maintained) | `libraries/plugins/apis/documentation/openapi.json`, `.../Dockerfile:5-12` | client gen: `api_generation/.../generate_description.py:21` |

---

## Discrepancies and Potential Issues

1. **condenser_api method count was wrong (57 → 62).** The `DECLARE_API` block (`condenser_api.hpp:957-1020`) declares 62 methods; earlier tables summed to 61 and omitted `get_open_orders`, while the headline said 57. `reference/api.md` must be corrected.

2. **debug_node_api count was wrong (11 → 12).** `debug_fail_transaction` was missing.

3. **"Optional plugins silently return empty / no clear error" was wrong (now corrected).** condenser_api methods for optional plugins throw a descriptive `FC_ASSERT("X_plugin not enabled.")` → JSON-RPC -32003. Clients *can* distinguish "plugin not enabled" (this assert message) from "no data found" (empty result). Only the reputation field inside `get_accounts` degrades silently.

4. **Inconsistent pagination limits (confirmed, quantified).** Caps/defaults: condenser `get_vesting_delegations`/`get_expiring_vesting_delegations` default **100**; `get_order_book` default **500**; most list methods and `DATABASE_API_SINGLE_QUERY_LIMIT` cap at **1000**; `account_history_api.enum_virtual_ops` caps at **150,000**. No unified pagination standard.

5. **`witness_api` name collision (still valid caution).** The `witness_api` *plugin* has only 3 fast-confirm methods; witness *data* queries live in database_api (`find_witnesses`, `list_witnesses`, `list_witness_votes`, `get_active_witnesses`) and condenser_api (`get_witnesses`, `get_witness_by_account`, `get_witnesses_by_vote`, …).

6. **`wallet_bridge_api` (35) vs condenser_api (62).** wallet_bridge omits market ticker/volume/trade, `get_block_header`, several vote/content methods, and some signature methods — confirmed by header comparison.

7. **Total endpoint count was understated (~175 → ~198).** 196 `DECLARE_API` methods across 18 production API plugins + 2 jsonrpc. The "17 API plugins" headline should be "18 + jsonrpc" (plus the test-only `test_api`).

8. **Error-code nuance.** An unknown api/method returns **-32002** (PARSE_PARAMS_ERROR, via `find_api_method`'s assert in `process_params`), not the nominal -32601; handler asserts (incl. "plugin not enabled") return **-32003**. Documenting only the nominal constants can mislead client error-handling.

---

## Open Questions

*All five original open questions are now resolved (see the corresponding sections).*

1. **How is the OpenAPI spec generated?** → **RESOLVED.** `openapi.json`/`walletapi.json` are hand-maintained committed artifacts; no generator produces them; the introspection path (`debug_get_json_schema`) is dead. Drift risk is high and unguarded by CI. (See *Documentation & API Spec Generation*.)

2. **What determines which plugins are enabled by default?** → **RESOLVED.** A three-tier model in `programs/hived/main.cpp` (always-on chain/p2p/webserver; default witness/account_by_key(_api)/state_snapshot; everything else off). The full API set comes from deployment `config.ini` files, not the binary. (See *Default Plugin Configuration*.)

3. **Is there rate limiting?** → **RESOLVED.** No per-client rate limiting anywhere in the API layer; only the fixed thread pool (default 16). Saturation queues indefinitely with diagnostic logging. P2P bandwidth limiting is unrelated. (See *WebServer Plugin*.)

4. **How does `colony` relate to the API layer?** → **RESOLVED.** It doesn't — `colony` is a testnet-only transaction load generator with no API, mainnet-blocked; `colony_order` is only a shutdown-ordering hint.

5. **What's the `queen` plugin?** → **RESOLVED.** A testnet-only single-node instant block producer for benchmarking/CI, no API, mainnet-blocked, disables P2P.

**Remaining / out of scope (zoom candidates):**
- **Exact websocketpp default body/message-size limits.** hived sets none; the effective cap is whatever the bundled websocketpp (nested under the `fc` submodule, not checked out) compiles in. Verifying the numeric default requires the populated submodule.
- **HAF/hivemind API surface.** The richest production "Hive API" (account history, social, block explorer) is served by HAF-based apps in front of hived, not by these node plugins. That layer is out of scope for hive-core and belongs in a separate HAF research part.
