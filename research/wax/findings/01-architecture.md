# Wax Part 01 - Architecture & Entry Points

**Anchor:** wax `2.0.2` (`c9c4918a845f59ebd97fff1316d00c91827df623`), npm `latest`.
**Scope:** the overall shape of the library - how the shared C++ protocol core is
bound into TypeScript (WASM) and Python (Cython), the public entry points, and the
`base` (offline) vs `chain` (online) split. Deeper method-by-method behavior is left
to parts 02-07.

All paths are relative to the wax repo root. Citations are `file:line` against the
pinned worktree `workspace/wax/c9c4918a84/`.

---

## 1. Three-layer architecture

Wax is one C++ protocol core exposed through two language bindings. The same C++
class (`cpp::foundation`) is compiled twice: to WebAssembly via Emscripten for the
TypeScript package, and to a native `.so` via Cython for the Python package.

```
                 hive submodule (libraries/protocol, libraries/fc)
                                     |
                          core/  (shared C++)
                       cpp::foundation  +  proto/api converters
                       /                                    \
         Emscripten / WASM                              Cython / .so
                 |                                            |
   ts/  @hiveio/wax                              python/  hiveio-wax
   WaxBaseApi -> HiveChainApi                    WaxBaseApi -> HiveChainApi
                 |                                            |
   createWaxFoundation()/createHiveChain()   create_wax_foundation()/create_hive_chain()
```

- The C++ layer is "tightly integrated to the hive submodule and mostly uses
  `libraries/protocol` and `libraries/fc`" (per the repo's own `CLAUDE.md`). It holds
  the real protocol logic: serialization, signing math, asset/economics math,
  authority verification.
- Each language layer is a thin object-oriented wrapper that marshals
  JSON/proto across the binding boundary and presents an idiomatic API.
- The two language APIs are deliberately **structurally identical** at the top
  (`WaxBaseApi` -> `HiveChainApi`), but diverge in transport and packaging details
  (section 6).

Note the TS package's overriding design constraint, stated in the repo `CLAUDE.md`:
"One important principle of the TS version is minimal size of the finally produced
NPM package." This drives the WASM-loading complexity in `index.ts` (section 4).

---

## 2. Shared C++ core (`core/foundation`)

`class foundation` (`core/foundation.hpp:76`) is "common base providing functionality
independent of the JSON format being used for parameter transport" (`foundation.hpp:75`).
It is the single surface both bindings call into.

### Handle objects

The core does not pass raw C++ `signed_transaction`/`operation` objects across the
language boundary. Instead it hands back opaque **handles**:

- `hive_transaction_handle` (`foundation.hpp:45-61`) - owns a
  `std::unique_ptr<hive_tx, wax_tx_ptr_deleter>` where `hive_tx =
  hive::protocol::signed_transaction` (`foundation.hpp:33`).
- `hive_operation_handle` (`foundation.hpp:63-67`) - owns a `hive_op =
  hive::protocol::operation` (`foundation.hpp:34`).

`hive_transaction_handle` carries `static unsigned int instance_count` /
`max_instance_count` (`foundation.hpp:59-60`), surfaced via
`cpp_report_transaction_handle_stats()` (`foundation.hpp:119`) - i.e. the core tracks
live transaction handles, a leak/lifetime diagnostic that matters for the long-lived
WASM instances on the TS side (section 4).

### The authority-provider callback bridge

`IAccountAuthorityProvider` (`foundation.hpp:21-31`) is a pure-virtual interface the
binding layer **implements in TS/Python** and passes back into C++ so the C++
authority-verification algorithm can pull account authorities and witness keys on
demand:

- `getAuthority(account_name, authorityRole)` -> `wax_authority` (`foundation.hpp:26`)
- `getWitnessPublicKey(witness_name)` -> public key (`foundation.hpp:28`)

It is consumed by `cpp_trace_authority_verification(...)` (`foundation.hpp:249-252`).
This inversion (C++ calling back up into JS/Python) is the key integration mechanism
and recurs in signing-key collection (part 05).

### Method surface (categories)

The `foundation` public methods (`foundation.hpp:81-283`), grouped - each group maps
to a later part:

| Category | Representative methods | Part |
|----------|------------------------|------|
| Keys / crypto | `cpp_calculate_public_key`, `cpp_generate_private_key`, `cpp_suggest_brain_key`, `cpp_get_public_key_from_signature`, WIF conversions | 05 |
| Protocol config | `cpp_get_hive_protocol_config(chain_id)` -> map of constants | 01/02 |
| Assets | `cpp_general_asset`, `cpp_hive`, `cpp_hbd`, `cpp_vests`, `cpp_asset_value`, `cpp_asset_symbol` | 04 |
| Economics math | `cpp_calculate_hp_apr`, `cpp_hbd_to_hive`, `cpp_hive_to_hbd`, `cpp_vests_to_hp`, `cpp_hp_to_vests`, `cpp_calculate_inflation_rate_for_block`, `cpp_estimate_hive_collateral`, `cpp_evaluate_hbd_interest` | 04 |
| Manabar | `cpp_calculate_manabar_full_regeneration_time`, `cpp_calculate_current_manabar_value` | 04 |
| TaPoS | `cpp_get_tapos_data(block_id)` -> `ref_block_data` | 03 |
| Operation handle | `cpp_op_validate`, `cpp_op_to_binary`, `cpp_op_to_json`, `cpp_op_required_authorities`, `cpp_op_impacted_accounts` | 02/03 |
| Transaction handle | `cpp_tx_add_operation`, `cpp_tx_set_expiration`, `cpp_tx_add_signature`, `cpp_tx_sig_digest`, `cpp_tx_id`, `cpp_tx_to_binary`, `cpp_tx_validate`, `cpp_tx_signature_keys` | 03 |
| Signing helpers | `cpp_collect_signing_keys`, `cpp_minimize_required_signatures`, `cpp_trace_authority_verification` | 05 |
| Memo crypto | `cpp_crypto_memo_from_string`, `cpp_crypto_memo_dump_string`, `cpp_check_memo_for_private_keys` | 05 |
| Witness props | `cpp_serialize_witness_set_properties`, `cpp_deserialize_witness_set_properties` | 07 |
| Validation | `cpp_is_valid_account_name` | 03 |

A notable design point: `cpp_op_to_binary` / `cpp_op_binary` / `cpp_tx_to_binary` /
`cpp_tx_id` all take a `bool use_hf26_serialization` (`foundation.hpp:262-275`), so the
core can emit either legacy or HF26 wire formats on demand - relevant to part 03.

### Transport converters

`foundation` is transport-agnostic; the proto<->C++ and api<->C++ marshalling lives
beside it in `core/proto_converter.hpp` (`to_proto_converter` / `to_proto_visitor`,
`proto_converter.hpp:14-21`) and `core/api_converter.hpp`. These convert between
fc-reflected C++ protocol structs and the protobuf/JSON forms the bindings exchange.
Detailed in part 02.

---

## 3. Public entry points (both languages)

Wax has exactly two construction entry points per language, mirroring the
offline/online split:

| Concept | TypeScript | Python |
|---------|------------|--------|
| Offline foundation (build/sign/validate, no network) | `createWaxFoundation(options?)` -> `IWaxBaseInterface` | `create_wax_foundation(options?)` -> `IWaxBaseInterface` |
| Online chain (the above + API calls/broadcast) | `createHiveChain(options?)` -> `IHiveChainInterface` | `create_hive_chain(options?)` -> `IHiveChainInterface` |

- TS: `ts/wasm/lib/index.ts:82` (`createWaxFoundation`), `index.ts:67` (`createHiveChain`).
- Python: `python/wax/wax/wax_factory.py:10` (`create_wax_foundation`),
  `wax_factory.py:20` (`create_hive_chain`).

`HiveChainApi` **is a** `WaxBaseApi` in both languages (TS `chain_api.ts:36`
`extends WaxBaseApi`; Python `chain_api.py:28` inherits `WaxBaseApi`), so everything
the offline foundation can do, the online chain can do too - the chain object just
adds endpoints and network methods.

---

## 4. TypeScript binding (Emscripten / WASM)

### Entry module and WASM loading

`ts/wasm/lib/index.ts` is the package entry. It re-exports the implementation
(`export * from "./detailed/index.js"`, `index.ts:3`) and owns the
environment-specific WASM loading via `getModuleExt()` (`index.ts:10-56`). That
function is the price of the "minimal NPM package" + "run everywhere" goals - it has
distinct branches for:

- Vite client (`import.meta.client`) with a string-concatenation hack to defeat
  bundler rewriting (`index.ts:11-22`),
- Node / non-browser (`index.ts:25-30`),
- webpack/parcel with `new URL(..., import.meta.url)` and a base64 `data:` inline
  fallback that decodes the WASM to a `Uint8Array` (`index.ts:34-55`).

The public `createHiveChain` / `createWaxFoundation` here just resolve the WASM
location, then delegate to the `detailed/` constructors (`index.ts:67-86`).

### WasmManager: lifecycle and error translation

`WasmManager` (`ts/wasm/lib/detailed/util/wasm_errors.ts:17`) owns the module instance:

- Lazy, cached load: the `module` getter resolves the Emscripten module once and
  caches it in `this.mainModule` (`wasm_errors.ts:85-99`).
- `safeWasmCall<T>(fn)` (`wasm_errors.ts:75-81`) wraps every call into WASM; on throw
  it routes to `handleWasmStdException`.
- `handleWasmStdException` (`wasm_errors.ts:27-73`) uses Emscripten's
  `getExceptionMessage(e)` (`wasm_errors.ts:39`) to recover `[exceptionName, body]`
  and maps C++ exception types to typed JS errors:
  - `cpp::wax_chain_assertion` -> `WaxChainAssertionError`
  - `cpp::wax_protocol_assertion` -> `WaxProtocolAssertionError`
  - `cpp::wax_api_assertion` / `wax_unknown_assertion` / `wax_assertion` -> `WaxAssertionError`
  - `cpp::wax_private_key_leak` -> `WaxPrivateKeyLeakDetectedException` (carries
    `public_key`, `account`, `authority_role`; `wax_errors.ts:55-59`) - the runtime
    guard behind `cpp_check_memo_for_private_keys` (part 05)
  - anything else -> generic `WaxError` (`wax_errors.ts:72`).

> **Finding (verified, low severity):** As of 2.0.2 `WasmManager` translates
> exceptions but has **no WASM heap-corruption recovery path**. It caches
> `mainModule` (`wasm_errors.ts:91`) and never resets it; a module that has hit
> `memory access out of bounds` / `unreachable` / `RuntimeError` stays poisoned for
> the process lifetime. Recovery (detect WASM error -> drop cached instance -> rebuild
> on next call) is implemented by *consumers* such as denser, not by wax itself. Any
> long-lived service embedding `@hiveio/wax` must own that reset. (See the documented
> denser WASM-memory-corruption fix.)

### API classes and defaults

`createWaxFoundation` (`detailed/base.ts:14`) builds a `WasmManager`, awaits the
module, merges options over `DEFAULT_WAX_OPTIONS` (`base.ts:9-11`, only
`chainId: "beeab0de...0000"`), and returns `new WaxBaseApi(...)`
(`base.ts:20`; class at `base_api.ts:40`, `implements IWaxBaseInterface`).
`WaxBaseApi` holds the live C++ core as `this.protocol = new wax.protocol_foundation()`
(`base_api.ts:51`) - the WASM-bound `protocol_foundation` class **is** the
`cpp::foundation` surface from section 2, and every `cpp_*` call routes through it.

`createHiveChain` (`detailed/chain.ts:21`) does the same over
`DEFAULT_WAX_OPTIONS_CHAIN` (`chain.ts:12-18`), which extends the base defaults with
`apiEndpoint: "https://api.hive.blog"`, `restApiEndpoint: "https://api.syncad.com"`,
`apiTimeout: 2000` ms, and an optional `waxApiCaller`. It returns
`new HiveChainApi(...)` (`chain.ts:27`; class at `chain_api.ts:36`,
`extends WaxBaseApi implements IHiveChainInterface`).

The default `chainId` `beeab0de00000000000000000000000000000000000000000000000000000000`
(`base.ts:10`) is the **Hive mainnet chain id**, and it is the **literal** 32-byte
value - not a hash. hive-core defines `HIVE_CHAIN_ID =
fc::sha256("beeab0de00...00")` (hive-core
`libraries/protocol/include/hive/protocol/config.hpp:142`) using the fc::sha256 **hex
constructor**, which fills the 32-byte digest buffer directly from the hex string. So
the id is exactly `beeab0de00..00`. Testnet, by contrast, is a genuine digest:
`fc::sha256::hash("testnet")` (`config.hpp:69`). Pass a non-default `chainId` for
testnet/mirrornet.

> **KB note (verified during review):** `reference/constants.md:248` currently lists
> the mainnet chain id as `sha256("beeab0de...")`, conflating the hex constructor with
> the `::hash()` method - the id is the literal value, not a hash of it. Filed as
> `contrib/hive-core/2026-06-16-reviewer-chain-id-constructor-not-hash.md`.

### Pluggable signers (extension packages)

The TS core is signer-agnostic. Signing providers ship as separate sub-packages under
`ts/packages/`: `signers-beekeeper`, `signers-keychain`, `signers-metamask`,
`signers-peakvault`, and `signers-external`. They plug into the transaction-signing
flow rather than being bundled into core (keeps the core package small). Detailed in
part 05.

---

## 5. Python binding (Cython / single `.so`)

### One shared object, many Cython sub-modules

The Python package compiles multiple Cython sources
(`python/wax/cython_modules_*.pyx`) into a **single `.so`**. `wax/__init__.py` does two
load-time fixups before the public API is importable:

1. **Symlink restoration** (`__init__.py:12-51`): wheels drop symlinks to the main
   `.so`, so `_restore_symlinks()` recreates them from a `_symlinks.json` manifest at
   first import (falling back to file copy on platforms without symlink permission,
   `__init__.py:38-45`).
2. **Cython sub-module aliasing** (`__init__.py:53-89`): because the sub-modules
   `cimport` each other by short name, they are imported and registered in
   `sys.modules` under bare names **in dependency order** -
   `cython_modules_common` -> `cython_modules_handles` -> `cython_modules_validation`
   -> `cython_modules_transactions` -> then the `cpp_python_bridge` facade. The
   comment stresses this interleaving "is required and cannot be reorganized"
   (`__init__.py:71-73`).

### Two import paths for the bridge functions

Public functions come from two places (`__init__.py:91-183`):

- `_private.cython_wrappers` (`__init__.py:96-138`) - wrappers for functions that take
  `str` parameters, needed for "Cython 3.1.3 compatibility" with subclasses of builtin
  types (`__init__.py:95`). E.g. `serialize_transaction`, `calculate_sig_digest`,
  `validate_operation`, `collect_signing_keys`.
- `cpp_python_bridge` directly (`__init__.py:141-183`) - functions without `str`
  params, imported raw. E.g. `hive`/`hbd`/`vests`, the economics calculators,
  `create_wax_operation`, `create_wax_transaction`, `op_*`, `tx_*`.

### Factories and API classes

`wax_factory.py` builds the same two objects as TS, lazily importing the
implementation from `wax._private`:

- `create_wax_foundation(options?)` -> `WaxBaseApi(chain_id, _private=True)`
  (`wax_factory.py:10-17`; class `_private/base_api.py:75`, `WaxBaseApi(IWaxBaseInterface)`).
- `create_hive_chain(options?)` -> `HiveChainApi(chain_id, endpoint_url, _private=True)`
  (`wax_factory.py:20-29`; class `_private/chain_api.py:28`,
  `HiveChainApi(IHiveChainInterface, WaxBaseApi, Generic[ApiCollectionT])`).

The `_private=True` keyword is a guard steering callers to the factory functions
rather than constructing the API classes directly.

---

## 6. TS vs Python divergences (entry-point level)

| Aspect | TypeScript (`@hiveio/wax`) | Python (`hiveio-wax`) |
|--------|----------------------------|-----------------------|
| Binding | Emscripten WASM, loaded async (`createX` returns a `Promise`) | Cython native `.so`, imported synchronously (`create_x` returns directly) |
| Construction | async (`await createHiveChain()`) | sync (`create_hive_chain()`) |
| Online endpoints | **two**: `apiEndpoint` (JSON-RPC, default `api.hive.blog`) + `restApiEndpoint` (default `api.syncad.com`) (`chain.ts:14-15`; routed to separate `JSON_RPC`/`REST` callers at `chain_api.ts:29-46`,`:63`) | **one**: `endpoint_url` (`wax_factory.py:26`, `chain_api.py:34`) |
| Chain generic | `HiveChainApi` non-generic | `HiveChainApi` is `Generic[ApiCollectionT]` (`chain_api.py:28`) |
| Error model | typed `Wax*` errors via `WasmManager` (`wax_errors.ts`) | exception mapping in the Cython layer (`exceptions/`, part 03) |
| Packaging quirk | env-specific WASM locating in `index.ts` | single-`.so` symlink restore + Cython sub-module aliasing (`__init__.py`) |
| PyPI/npm tip | npm `latest` = 2.0.2 (this anchor) | PyPI `latest` = 2.0.1 (one patch behind, API-identical) |

Published `version` is a build-time placeholder in both (`ts/package.json`
`0.0.1-LastGitTagPlaceholder...`; `__init__.py:211` `__version__ = "0.0.0"`); CI injects
the real version from the git tag (see README versioning note).

---

## 7. Entry-point cheat-sheet

```ts
// TypeScript (@hiveio/wax) - async
import { createWaxFoundation, createHiveChain } from "@hiveio/wax";
const wax   = await createWaxFoundation();                 // offline
const chain = await createHiveChain({ apiEndpoint, restApiEndpoint, chainId });
```

```python
# Python (hiveio-wax) - sync
from wax import create_wax_foundation, create_hive_chain
wax   = create_wax_foundation()                            # offline
chain = create_hive_chain(WaxChainOptions(endpoint_url=...))
```

- Use `*WaxFoundation` for pure offline work (build/serialize/sign/validate); no
  network is touched.
- Use `*HiveChain` when you also need API reads or to broadcast; it is a superset.

---

## 8. Notable findings

1. **No WASM corruption recovery in wax core (verified).** `WasmManager` caches the
   module and never resets it; heap-corruption recovery is the embedder's job
   (section 4). Worth a KB cross-link from the denser WASM-corruption note.
2. **C++-calls-up-into-JS/Python is the central bridge mechanism.**
   `IAccountAuthorityProvider` (`foundation.hpp:21`) and the `retrieve_authorities_cb`
   in `cpp_collect_signing_keys` (`foundation.hpp:280`) invert control so authority
   data is fetched lazily from the host language. Signing is not a pure C++ black box.
3. **Transaction-handle instance counting** (`foundation.hpp:59-60`,119) is a built-in
   lifetime diagnostic - useful when hunting leaks in long-lived WASM instances.
4. **`use_hf26_serialization` is a per-call boolean**, not a global mode
   (`foundation.hpp:262-275`) - wax can produce legacy and HF26 wire forms side by
   side (part 03).

---

## 9. Code References

| Topic | File:line |
|-------|-----------|
| Shared C++ foundation class | `core/foundation.hpp:76` |
| Transaction/operation handles | `core/foundation.hpp:45-67` |
| Handle instance counting | `core/foundation.hpp:59-60`, `:119` |
| IAccountAuthorityProvider bridge | `core/foundation.hpp:21-31`, `:249-252` |
| Proto converter | `core/proto_converter.hpp:14-21` |
| TS package entry / WASM loading | `ts/wasm/lib/index.ts:3`, `:10-56` |
| TS createWaxFoundation (public) | `ts/wasm/lib/index.ts:82` |
| TS createHiveChain (public) | `ts/wasm/lib/index.ts:67` |
| TS createWaxFoundation (impl) + defaults | `ts/wasm/lib/detailed/base.ts:9-23` |
| TS createHiveChain (impl) + defaults | `ts/wasm/lib/detailed/chain.ts:12-36` |
| TS WaxBaseApi class | `ts/wasm/lib/detailed/base_api.ts:40` |
| C++ foundation exposed to TS | `ts/wasm/lib/detailed/base_api.ts:51` (`new wax.protocol_foundation()`) |
| TS HiveChainApi class + JSON-RPC/REST callers | `ts/wasm/lib/detailed/chain_api.ts:36`, `:29-46`, `:63` |
| Mainnet chain id (ground truth) | hive-core `libraries/protocol/include/hive/protocol/config.hpp:142` (literal), `:69` (testnet hash) |
| TS WasmManager + error translation | `ts/wasm/lib/detailed/util/wasm_errors.ts:17`, `:27-99` |
| TS signer packages | `ts/packages/signers-{beekeeper,external,keychain,metamask,peakvault}` |
| Python public API + load fixups | `python/wax/wax/__init__.py:12-209` |
| Python Cython sub-module aliasing | `python/wax/wax/__init__.py:53-89` |
| Python factories | `python/wax/wax/wax_factory.py:10-29` |
| Python WaxBaseApi class | `python/wax/wax/_private/base_api.py:75` |
| Python HiveChainApi class | `python/wax/wax/_private/chain_api.py:28` |

---

## 10. Open Questions (for later parts / zoom)

- **How exactly is `cpp::foundation` exposed to each binding?** Partly answered: TS
  binds it as the WASM class `protocol_foundation`, instantiated per API object at
  `base_api.ts:51`; Python wraps it through `cpp_python_bridge.pyx`. The Emscripten
  embind glue and the Cython `cdef` layer themselves were not traced here - belong to
  part 02/03.
- **Proto vs legacy JSON transport selection.** `proto_converter.hpp` and
  `api_converter.hpp` exist side by side; which path each public call uses (and the
  role of `*_proto_*` vs plain functions in the Python `__init__`) is a part-02 item.
- **Python single-endpoint vs TS dual-endpoint.** Does Python lack a separate REST
  client, or route REST through the same `endpoint_url`? Resolve in part 06.
- **`waxApiCaller` injection** (`chain.ts:17`) - the pluggable API-caller hook is
  unexplored; part 06.
