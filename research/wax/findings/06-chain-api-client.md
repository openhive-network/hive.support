# Wax Part 06 - Chain / API Client

**Anchor:** wax `2.0.2` (`c9c4918a`).
**Scope:** the online side - `HiveChainApi`: how `chain.api.*` / `chain.restApi.*` calls
work, the predefined API surface and how to `extend` it, `broadcast`, endpoints /
interceptors / `waxApiCaller`, and the standalone health checker. Builds on part 01
(`createHiveChain`, options/endpoints), part 03 (`createTransaction`, TaPoS cache,
`broadcast` endpoint) and part 05 (on-chain authority verification).

---

## 1. Two callers: JSON-RPC and REST

`HiveChainApi extends WaxBaseApi` (`chain_api.ts:36`) adds two independent
`ApiCaller`s (part 01 established these are distinct endpoints):

| Accessor | Caller | Endpoint (default) | HTTP | Envelope |
|----------|--------|--------------------|------|----------|
| `chain.api` (`chain_api.ts:41-43`) | `jsonRpcApiCaller` (`:45`) | `apiEndpoint` = `api.hive.blog` | POST | JSON-RPC `{jsonrpc, method, params, id}` |
| `chain.restApi` (`chain_api.ts:37-39`) | `restApiCaller` (`:46`) | `restApiEndpoint` = `api.syncad.com` | GET | REST path + query/body |

Both are built in the constructor (`chain_api.ts:63`,`:102`) with their type registry,
default method, an endpoint-propagation callback, and `config.waxApiCaller`. The
JSON-RPC caller additionally gets static request/response rewriters (section 3).

---

## 2. The call mechanism (`ApiCaller` + Proxy)

`chain.api` / `chain.restApi` return a `Proxy` from `ApiCaller.createApiCaller()`
(`util/api_caller.ts:102`). The pattern `chain.api.database_api.get_dynamic_global_properties({...})`
works like this:

1. **Property access builds the path.** Each `.database_api`, `.get_dynamic_global_properties`
   hits the Proxy `get` trap (`api_caller.ts:162-191`), which looks the name up in the
   type registry (`getRestTypeFromPath`), pushes it onto `callFn.paths` / `realPaths`,
   and records any per-method `method`/`urlPath` override (`:178-191`).
2. **Calling issues the request** via `callFn` (`api_caller.ts:104-154`):
   - REST path = `/` + paths joined, with `{braced}` URL params substituted from the
     request object (`:105-118`); GET/DELETE put remaining fields in a query string,
     others in the body (`:120-127`).
   - Builds `requestData { method, endpoint, timeout, url, data, waxApiCaller, paths,
     apiCallerId }` (`:133-143`) and runs the request through the **4-layer interceptor
     chain** (`:145`): `staticRequestInterceptor -> requestInterceptor -> request() ->
     responseInterceptor -> staticResponseInterceptor`.
   - Returns `data.response`; missing-but-required result throws `WaxChainApiError`
     (`:148-151`).

So the API surface is a typed Proxy tree, not a hand-written client - the request shape
is derived from the accessed path plus the registry entry.

---

## 3. JSON-RPC envelope and typed API errors

The JSON-RPC caller's **static** interceptors (`chain_api.ts:68-100`) do the
RPC-specific work:

- **Request rewrite** (`:68-77`): replace the body with
  `{ jsonrpc: "2.0", method: paths.join('.'), params: <data>, id: 1 }` and clear the URL
  (POST to the endpoint root). So `database_api.get_dynamic_global_properties` becomes the
  dotted RPC method.
- **Response rewrite** (`:78-100`): if the response has `result`, unwrap to it; if it has
  an `error`, call `cpp_transform_api_error_response_into_exception(error.data)`
  (`foundation.hpp:120`) to turn the hived error into a **typed Wax exception**, wrapping
  the cause in `WaxChainApiError` for request/response forensics; otherwise throw
  `WaxChainApiError("Invalid response")`.

So chain-API errors get the same typed-exception treatment as WASM assertion errors
(part 01) - a hived error response is repackaged into a recognizable `Wax*` error.

---

## 4. Predefined API surface and extending it

`chain_api_data.ts` defines the registries:

- `HiveApiTypes` (`:16-73`) - a **curated JSON-RPC subset**, strongly typed
  (Request/Response per method): `account_by_key_api` (get_key_references),
  `database_api` (find_accounts, find_witnesses, get_dynamic_global_properties,
  get_witness_schedule, verify_authority, ...), `network_broadcast_api`
  (broadcast_transaction), `block_api` (get_block / _header / _range), `rc_api`
  (find_rc_accounts). This is **not** the full hived API (~175 methods; see
  `reference/api.md`) - just what wax needs plus common calls.
- `HiveRestApiTypes` (`:12-14`) is **`{}`** - REST has **no** predefined methods. The
  REST surface (HAF apps: block explorer, balance tracker, ...) is entirely
  app-supplied via `extendRest`.

Extending (both return a new, type-extended chain instance):

- `extend<YourApi>(data?)` (`chain_api.ts:155`) merges custom JSON-RPC method
  definitions into `jsonRpcApiCaller.localTypes`; type is `HiveChainApi & TWaxExtended<...>`.
- `extendRest<YourRestApi>(data?)` (`chain_api.ts:170`) does the same for REST - this is
  the **primary** way to call HAF REST endpoints.
- `withProxy(requestInterceptor, responseInterceptor)` (`chain_api.ts:122-130`) returns an
  extended instance whose callers run your interceptors - used for mocking (the test
  proxy-mock-server), logging, or request rewriting.
- **Originator propagation**: an extended instance keeps a link to its `originator`
  (`chain_api.ts:57`); endpoint changes propagate back through
  `setEndpointUrlForPath` (`:63-66`,`:102-104`) so base and extensions stay consistent.

---

## 5. Broadcast

`broadcast(tx)` (`chain_api.ts:110-117`):

1. `const toBroadcast = "toApiJson" in tx ? tx.toApiJson() : tx` - convert the transaction
   to **API-JSON shape** (the proto->api conversion from part 03).
2. `if ("performOnChainVerification" in tx) await tx.performOnChainVerification()` - for an
   `OnlineTransaction`, run the recursive **authority verification** (part 05) before
   sending.
3. `await this.api.network_broadcast_api.broadcast_transaction({ max_block_age: -1, ... })`
   - the actual JSON-RPC broadcast.

So broadcasting is shape-conversion + optional authority pre-check + the RPC call.

---

## 6. Endpoints, timeout, and `waxApiCaller`

- `endpointUrl` get/set (`chain_api.ts:132-141`) controls the JSON-RPC endpoint (and
  propagates to the originator). `apiTimeout` defaults to 2000 ms (part 01).
- **Per-path endpoint overrides**: `ApiCaller.setEndpointUrlForPath(path, url)`
  (`api_caller.ts:63`) lets individual methods target a different node than the default.
- `waxApiCaller` (`config.waxApiCaller`, threaded into every `requestData` as
  `waxApiCaller`) is a pluggable transport hook - a named caller the host environment can
  intercept (e.g. routing requests through a custom fetch/transport).
- TaPoS reference data is cached ~3 s (`acquireChainReferenceData`, part 03) to back
  `createTransaction`.

---

## 7. Health checker (endpoint selection)

`ts/wasm/lib/detailed/healthchecker/` is a **standalone** utility (not auto-wired into a
chain) for picking/monitoring endpoints. `HealthChecker` + `Endpoint`
(`healthchecker/healthchecker.ts`, `endpoint.ts`) probe candidate nodes and classify
failures - `WaxRequestTimeoutError`, `WaxNon_2XX_3XX_ResponseCodeError`,
`WaxRequestAbortedByUser`, `WaxHealthCheckerValidatorFailedError`
(`healthchecker/errors.ts`) - emitting events so an app can fail over to a healthy node
and feed the result back via `endpointUrl` / `setEndpointUrlForPath`. A custom
**validator** can reject a syntactically-OK-but-stale node.

---

## 8. Python parallel

Python models the API as **collections**, not a Proxy tree:

- `HiveChainApi(..., api_collection)` (`_private/chain_api.py:28-61`) wraps a
  `WaxApiCollection` (`:56-57`) in a `WaxApiCaller(collection, endpoint_url)` (`:61`).
- `extends(new_api)` (`:70-81`) combines API collection classes and returns a new
  chain typed over the merged collection (the analogue of TS `extend`).
- **Single `endpoint_url`** (`:85`) - no separate predefined REST caller (consistent
  with part 01); REST/HAF access is via the supplied collection.
- Broadcast / API calls go through the same C++ core for serialization and the typed
  Python API models.

So both languages: a typed, extensible API client over the same core; TS uses a
Proxy + dual JSON-RPC/REST callers, Python uses class-based collections + a single
endpoint.

---

## 9. API-shape vs proto-shape

Two JSON shapes coexist (part 02/03): the internal **proto** shape and the **API**
shape the nodes speak. The chain client always exchanges the API shape; conversion
happens at the edges via the core - `cpp_tx_api_to_proto` on `Transaction.fromApi`
(inbound) and `cpp_tx_proto_to_api` on `toApiJson` / `broadcast` (outbound). Callers
generally hand wax API-shaped objects and get API-shaped responses; the proto form is an
implementation detail of the C++ handle.

---

## 10. Notable findings

1. **REST is empty by default** (`HiveRestApiTypes = {}`, `chain_api_data.ts:12-14`).
   wax predefines only a JSON-RPC subset; HAF/REST endpoints are app-defined via
   `extendRest`. Expect to extend before calling REST.
2. **hived API errors become typed `Wax*` exceptions** through the C++ core
   (`cpp_transform_api_error_response_into_exception`, `chain_api.ts:88`) - not raw HTTP
   errors.
3. **The API client is a typed Proxy, not a hand-written client** - methods are derived
   from the registry, and `extend`/`extendRest` add type-safe methods at runtime.
4. **`broadcast` runs on-chain authority verification first** for `OnlineTransaction`
   (`chain_api.ts:113-114`).
5. **Curated, not complete.** Only a subset of hived's ~175 methods is predefined;
   reach for `extend` (or `condenser_api` via extension) for the rest.
6. **Pluggable transport** via `waxApiCaller` and the interceptor chain (`withProxy`)
   - enabling mocking, proxying, and custom fetch transports.

---

## 11. Code References

| Topic | File:line |
|-------|-----------|
| HiveChainApi + .api / .restApi | `ts/wasm/lib/detailed/chain_api.ts:36-46` |
| Caller construction | `chain_api.ts:63`,`:102` |
| JSON-RPC request/response rewriters | `chain_api.ts:68-100`; `core/foundation.hpp:120` |
| broadcast | `chain_api.ts:110-117` |
| withProxy / endpointUrl | `chain_api.ts:122-141` |
| extend / extendRest | `chain_api.ts:155`,`:170` |
| ApiCaller class | `ts/wasm/lib/detailed/util/api_caller.ts:29` |
| createApiCaller + Proxy + callFn | `api_caller.ts:102-191` |
| Interceptor chain | `api_caller.ts:145` |
| Per-path endpoint override | `api_caller.ts:63` |
| API registries (JSON-RPC / REST) | `ts/wasm/lib/detailed/chain_api_data.ts:16-73`,`:12-14` |
| Health checker | `ts/wasm/lib/detailed/healthchecker/{healthchecker,endpoint,errors}.ts` |
| Python chain API + collections + extends | `python/wax/wax/_private/chain_api.py:28-61`,`:70-85` |

---

## 12. Open Questions (for later parts / zoom)

- **`RequestHelper.request` transport.** The actual fetch/timeout/abort implementation
  (`ApiCaller extends RequestHelper`) and how `waxApiCaller` swaps it was not read.
- **`extend` type machinery.** `TWaxExtended` / `TWaxRestExtended` /
  `TDeepWaxApiRequestPartial` (the compile-time API typing) is unexplored.
- **HealthChecker scoring/failover policy** - how it ranks endpoints and integrates with
  a running chain is a zoom candidate.
- **condenser_api access.** Whether the legacy `condenser_api` is reachable out of the
  box or needs `extend` (it is not in the predefined `HiveApiTypes`).
- **REST endpoint examples.** Concrete `extendRest` usage against a HAF app (balance
  tracker / block explorer) would make this part actionable.
