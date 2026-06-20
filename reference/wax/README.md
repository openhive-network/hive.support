# Wax Reference - Navigation Guide

Compact, source-verified quick-lookup for **wax**, the Hive client library. Anchored to
wax `2.0.2` (`c9c4918a`, npm `latest`), **TypeScript-first** (Python noted where it
diverges). For deep analysis with `file:line` citations, see `../../research/wax/findings/`.

Wax documents the **client** surface (build / sign / broadcast / API). For the protocol
itself (operations semantics, consensus, economics) use the hive-core reference
(`../operations.md`, `../economics.md`, ...).

## Quick Lookup

| I need to know... | Read |
|-------------------|------|
| Entry points, options, the chain client, API calls, `extend` | [api.md](api.md) |
| How operations are modeled & built (`pushOperation`, builders) | [operations.md](operations.md) |
| The transaction lifecycle (TaPoS, expiration, serialize, sign) | [transactions.md](transactions.md) |
| Assets (HIVE/HBD/VESTS), conversions, the `waxify` formatter | [assets.md](assets.md) |
| Signing, signer packages, authorities, keys, memo encryption | [signing.md](signing.md) |

## Key Numbers

- **2 entry points per language**: `createWaxFoundation` (offline) / `createHiveChain`
  (online); Python `create_wax_foundation` / `create_hive_chain`.
- **90 operations** in wax's proto = **47 broadcastable + 43 virtual** (hive-core has 93;
  wax omits `custom_binary`, `reset_account`, `set_reset_account`).
- **3 native assets**: HIVE (`@@000000021`, prec 3), HBD (`@@000000013`, prec 3),
  VESTS (`@@000000037`, prec 6).
- **Default chain id**: Hive mainnet `beeab0de00..00` (literal). Default endpoints:
  `api.hive.blog` (JSON-RPC) + `api.syncad.com` (REST), 2000 ms timeout.
- **5 signer packages**: beekeeper, keychain, metamask, peakvault, external.
- **4 serialization forms**: HF26 JSON, HF26 binary, API-shape JSON, legacy JSON.

## Important Non-Obvious Facts

- **`NaiAsset.amount` is a string**, not a number (BigInt-backed) - precision-safe;
  treating it as a JS number is a bug risk.
- **`waxify` is TypeScript-only** - Python has assets/conversions but no formatter.
- **REST API surface is empty by default** (`HiveRestApiTypes = {}`); HAF/REST endpoints
  are app-supplied via `extendRest`. Only a curated JSON-RPC subset is predefined.
- **`Transaction.sign()` is deprecated** - use a signer's `signTransaction(tx)`, or
  `sigDigest` + `addSignature`.
- **Expiration is locked lazily, once** - the default `"+1m"` resolves at first
  serialize/sign, not at construction. Mainnet uses local realtime; test chains use head
  block time.
- **`sigDigest` binds the chain id** - the cross-chain (mainnet/testnet/mirrornet) replay
  guard.
- **No WASM heap-corruption recovery in wax core** - `WasmManager` caches the instance and
  never resets it; long-lived embedders (e.g. denser) must reset on corruption themselves.
- **hived API errors become typed `Wax*` exceptions** (via the C++ core), not raw HTTP
  errors.
- **Only `"rc"` among the app `custom_json` ids is chain-interpreted**; `follow` /
  `community` are hivemind/social-layer conventions the chain stores verbatim.
- **Version is git-tag-driven** - the manifest version is a build placeholder; CI injects
  it from the tag. The public line is `2.0.x` (npm 2.0.2 / PyPI 2.0.1); `1.28.6-rcXX` tags
  are internal RC builds, not the public release.

## Architecture in one line

One shared C++ `core/foundation` compiled twice - to WASM (TypeScript `@hiveio/wax`) and
to a native `.so` (Python `hiveio-wax`) - under an identical `WaxBaseApi -> HiveChainApi`
class hierarchy. See [api.md](api.md) and `findings/01-architecture.md`.

## Found an error?

Write a contribution file in `contrib/` (any topic dir) - see `../../CONTRIBUTING.md`.
