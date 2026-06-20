# Wax Reference - Entry Points & Chain/API Client

Quick reference for constructing wax and talking to a node. Deep detail:
`findings/01-architecture.md`, `findings/06-chain-api-client.md`.

## Entry points

| | TypeScript (`@hiveio/wax`) | Python (`hiveio-wax`) |
|--|----------------------------|------------------------|
| Offline (build/sign/validate) | `await createWaxFoundation(opts?)` -> `IWaxBaseInterface` | `create_wax_foundation(opts?)` -> `IWaxBaseInterface` |
| Online (above + API/broadcast) | `await createHiveChain(opts?)` -> `IHiveChainInterface` | `create_hive_chain(opts?)` -> `IHiveChainInterface` |

- TS construction is **async** (WASM load); Python is **sync** (Cython `.so`).
- `HiveChainApi` **extends** `WaxBaseApi` - the chain is a superset of the foundation.

### Options (defaults)

| Option | Default | Notes |
|--------|---------|-------|
| `chainId` | `beeab0de00..00` (mainnet) | binds the sig digest; set for testnet/mirrornet |
| `apiEndpoint` (TS) | `https://api.hive.blog` | JSON-RPC endpoint (`chain.api`) |
| `restApiEndpoint` (TS) | `https://api.syncad.com` | REST endpoint (`chain.restApi`) |
| `apiTimeout` (TS) | `2000` ms | per-request timeout |
| `endpoint_url` (Python) | - | single endpoint (Python has no separate REST caller) |
| `waxApiCaller` | undefined | pluggable transport hook |

## Calling the API (TypeScript)

`chain.api` (JSON-RPC) and `chain.restApi` (REST) are typed Proxies - property access
builds the method path, the call issues the request:

```ts
const dgpo = await chain.api.database_api.get_dynamic_global_properties({});
const acc  = await chain.api.database_api.find_accounts({ accounts: ["alice"] });
```

| Surface | Transport | Default predefined |
|---------|-----------|--------------------|
| `chain.api.*` | JSON-RPC (POST, `{jsonrpc,method,params,id}`) | curated subset: `account_by_key_api`, `database_api`, `network_broadcast_api`, `block_api`, `rc_api` |
| `chain.restApi.*` | REST (GET, path+query) | **none** - `HiveRestApiTypes = {}`; add via `extendRest` |

- **Not all ~175 hived methods are predefined** - reach for `extend` (or condenser_api
  via extension) for the rest.
- hived **error responses become typed `Wax*` exceptions** via the core; a thrown
  `WaxChainApiError` carries request/response data.

## Extending

| Call | Effect |
|------|--------|
| `chain.extend<T>(defs?)` | add typed JSON-RPC methods -> `HiveChainApi & TWaxExtended<T>` |
| `chain.extendRest<T>(defs?)` | add typed REST methods (the primary way to call HAF) |
| `chain.withProxy(reqI, respI)` | new instance with request/response interceptors (mock/log/proxy) |
| `chain.endpointUrl = url` | change JSON-RPC endpoint (propagates to originator) |

Python: `chain.extends(ApiCollection)` merges class-based API collections (no Proxy).

## Broadcast

```ts
await chain.broadcast(tx);   // ApiTransaction | ITransaction | IOnlineTransaction
```
Internally: `toApiJson()` (proto->api shape) -> for an `OnlineTransaction`,
`performOnChainVerification()` (recursive authority check) -> `network_broadcast_api.
broadcast_transaction({ max_block_age: -1, ... })`.

## Health checker

`healthchecker/` is a standalone endpoint-selection utility (probe/score/fail-over);
not auto-wired. Feed a chosen endpoint back via `endpointUrl` / per-path overrides.

## Misc base methods

`isValidAccountName(name)`, `config` (cached protocol constants for the chain),
`getVersion()`, `addressPrefix` ("STM").
