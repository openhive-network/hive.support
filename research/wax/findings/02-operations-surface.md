# Wax Part 02 - Operations Surface (Protobuf)

**Anchor:** wax `2.0.2` (`c9c4918a`), bundling hive submodule `f4e0a4b7`.
**Scope:** how wax represents the Hive operations - the protobuf `operation` oneof,
which operations wax actually exposes, the proto-generation pipeline, and how you
build/push an operation in TypeScript and Python. This part does **not** re-document
each operation's fields/semantics - that is the hive-core KB's job
(`reference/operations.md`, `research/hive-core/findings/02-operations-catalog.md`);
here we cross-reference it.

Paths are wax-repo-relative unless prefixed `hive:` (the bundled hive submodule at
`f4e0a4b7`, read from the pinned source).

---

## 1. Operations are protobuf - one canonical oneof

Wax does not hand-define operations. They come from the **`operation` protobuf oneof**
in the hive source: `hive:libraries/protocol/proto/operation.proto`. It is `proto2`
(`operation.proto:1`), `package hive.protocol.buffers`, and its `oneof value`
(`operation.proto:102-195`) enumerates every operation as a numbered field:

```proto
oneof value {
    vote     vote_operation     = 1  [json_name = "vote_operation"];
    comment  comment_operation  = 2  [json_name = "comment_operation"];
    transfer transfer_operation = 3  [json_name = "transfer_operation"];
    ...
}
```

This oneof is a **direct mirror of hive-core's `operation` `static_variant`**
(`hive:libraries/protocol/include/hive/protocol/operations.hpp`). The proto field
number equals the C++ static_variant index **+ 1** (proto is 1-based, C++ is 0-based:
`vote` is C++ index 0 / proto field 1). A header comment makes the ordering
consensus-critical:

> `operation.proto:98-99`: "NOTE: do not change the order of any operations prior to
> the virtual operations or it will trigger a hardfork."

Each field also carries `[json_name = "<name>_operation"]`. That json_name is the
HF26 wire/API key, so a vote serializes as `{"vote_operation": {...}}` - the bridge to
the JSON/API transport (serialization detail in part 03, API in part 06).

---

## 2. The proto operation surface: 47 broadcastable + 43 virtual = 90

The oneof splits at field 100:

- **Broadcastable (regular) operations**: fields **1-50**, but with **three gaps at
  36, 38, 39** (`operation.proto:103-149`). So **47** regular operations are actually
  present (1-35 contiguous, then 37, then 40-50).
- **Virtual operations**: fields **100-142**, contiguous = **43**
  (`operation.proto:151-194`). Matches hive-core's 43 virtual exactly.

Total proto operations: **90**, versus hive-core's **93** (50 regular + 43 virtual;
see `reference/operations.md`). The 3-operation difference is entirely in the regular
band, and is fully explained.

### The 3 missing broadcastable operations

The proto field number = C++ index + 1, so the gaps map exactly onto hive-core
static_variant slots (`operations.hpp`, index comments):

| Proto gap | hive-core index | Operation | Why wax omits it |
|-----------|-----------------|-----------|------------------|
| 36 | 35 | `custom_binary` | Deliberately disabled - the proto exists only as `hive:.../proto/custom_binary.proto.disabled` (the `.disabled` suffix excludes it from generation). |
| 38 | 37 | `reset_account` | Defunct Steem-era op (account-reset feature never operative on Hive). No `.proto` at all. |
| 39 | 38 | `set_reset_account` | Defunct Steem-era op (pairs with `reset_account`). No `.proto` at all. |

These three still occupy slots in hive-core's `static_variant` (so they count toward
the canonical 50) - the index must be preserved for serialization stability - but wax
gives them no protobuf, so they are not part of wax's buildable/parseable surface.
Verified: `ls .../proto | grep -iE "reset_account|custom_binary"` returns only
`custom_binary.proto.disabled`.

### SMT operations are compiled out

hive-core's `static_variant` has a block of SMT ops (`claim_reward_balance2`,
`smt_setup`, `smt_setup_emissions`, `smt_set_setup_parameters`,
`smt_set_runtime_parameters`, `smt_create`, `smt_contribute`) guarded by
`#ifdef HIVE_ENABLE_SMT` (`operations.hpp`, after index 49). SMT is not enabled on
mainnet, so these are absent from both the consensus operation set and wax's proto.

### Virtual operations are present but not broadcastable

All 43 virtual ops (fields 100-142: `fill_convert_request`, `author_reward`,
`curation_reward`, `producer_reward`, `account_created`, `fill_recurrent_transfer`,
...) have full proto. They cannot be pushed into a transaction (the chain emits them),
but wax needs them to **deserialize blocks and account history** and to type API
responses. So the proto surface is broadcast-superset: 47 you can build, plus 43 you
can only receive.

---

## 3. Proto-generation pipeline

The `.proto` source lives in the hive submodule (`hive:libraries/protocol/proto/`,
99 active `.proto` files at `f4e0a4b7`: the 90 operations plus supporting types -
`asset`, `authority`, `transaction`, `block`, `future_extensions`, `price`,
`legacy_chain_properties`, ...). It is compiled per language (per the repo's own
`CLAUDE.md`):

| Target | Generator | Output | Committed? |
|--------|-----------|--------|-----------|
| TypeScript | `ts-proto` | `ts/wasm/lib/proto/*.js` + `*.d.ts` | No - generated at build (empty in a clean checkout) |
| TypeScript (drift guard) | - | `ts/protobuf_patterns/proto/*.js` + `*.d.ts` | **Yes** - pattern copies tracking expected output |
| Python | `grpcio-tools` | `python/wax/wax/_private/proto/*_pb2.py` + `*.pyi` (+ `*_pb2_grpc.py`) | **Yes** - committed (98 `*_pb2.py` modules, one per type) |

So the actual shipped surface is inspectable without a build: read the committed
Python `_pb2` modules, or the TS pattern files in `ts/protobuf_patterns/proto/`. The
pattern files exist to detect drift between the checked-in expectation and freshly
generated output (CI compares them).

---

## 4. Building and pushing an operation - TypeScript

### The operation types

`ts/wasm/lib/detailed/protocol.ts` is the single re-export point for "only the
protobuf definitions" (`protocol.ts:1`): the `operation` oneof itself
(`protocol.ts:5`), `transaction`, supporting types (`asset`, `authority`,
`future_extensions`, `price`, `legacy_chain_properties`), and **every** operation type
- regular and virtual (`account_create`, `comment_options`, `author_reward`,
`curation_reward`, ...). A proto `operation` value is a oneof: an object with exactly
one `*_operation` field set.

### Two ways to push

`Transaction.pushOperation(op: operation | OperationBase): this`
(`transaction.ts:249`) accepts either form and is chainable:

1. **Raw proto operation** - an object with one oneof field:
   ```ts
   tx.pushOperation({ vote_operation: { voter, author, permlink, weight } });
   ```
   Goes straight to `pushOperationWithHandle` (`transaction.ts:252-253`).

2. **High-level builder** - an `OperationBase` (`operation_base.ts:8`), whose
   `finalize(sink): Iterable<operation>` (`operation_base.ts:9`) emits one or more raw
   proto operations. `pushOperation` detects it by `"finalize" in op`
   (`transaction.ts:250`) and routes to `produceOperations`, which calls
   `finalize(this)` and pushes each produced op (`transaction.ts:240-247`). These
   builders live in `complex_operations/` and `hive_apps_operations/` (part 07).

### What pushOperationWithHandle does (the dual representation)

`pushOperationWithHandle(op)` (`transaction.ts:234-238`) keeps **two** synchronized
representations of the transaction:

```ts
this.target.operations.push(op);                                   // JS-side proto array
const opHandle = ...cpp_create_operation_handle(op, true);         // proto -> C++ handle
...cpp_tx_add_operation(this.txHandle, opHandle);                  // append to C++ tx handle
```

- `this.target` is the JS-side proto `transaction` (its `operations[]` array).
- `cpp_create_operation_handle(op, true)` crosses into the WASM core: it converts the
  proto operation object into a `hive_operation_handle` (the C++ `operation` from part
  01). This is the proto-aware entry on the exposed `protocol_foundation`
  (`this.api.protocol`, established in part 01), distinct from the transport-agnostic
  base `foundation`.
- `cpp_tx_add_operation(txHandle, opHandle)` appends it to the C++ transaction handle
  (`foundation.hpp:268`).

Every WASM call is wrapped in `wasmManager.safeWasmCall(...)` (part 01) so C++
assertion failures surface as typed `Wax*` errors. From here, signing/serialization
operate on the C++ `txHandle` (part 03).

---

## 5. Building and pushing an operation - Python

Python mirrors the TS model closely (the shared C++ core is the same; only the binding
differs):

- Operation types are the committed `_pb2` modules under
  `python/wax/wax/_private/proto/` (re-exported via `wax.proto`), one per operation.
- `Transaction` (`python/wax/wax/_private/transaction.py:52`, `class Transaction(ITransaction)`)
  builds an operation from a oneof **dict** and creates the C++ handle:
  ```python
  op_handle = create_wax_operation({operation_name + "_operation": dict_default_op}, is_protobuf=True)  # transaction.py:158
  ```
  i.e. the same `{"<name>_operation": {...}}` oneof shape as TS, via
  `create_wax_operation(..., is_protobuf=True)` (from `cpp_python_bridge`, part 01).
- `push_operation(operation) -> Self` (`transaction.py:162`) is the chainable public
  API; `OnlineTransaction(Transaction, IOnlineTransaction)`
  (`online_transaction.py:123`) adds broadcasting (part 06).

So both languages converge on: build a proto oneof (object in TS, dict in Python) ->
create a C++ op handle -> append to the C++ transaction handle.

---

## 6. TS vs Python (operations surface)

| Aspect | TypeScript | Python |
|--------|------------|--------|
| Operation type source | `ts/wasm/lib/proto/` (generated by ts-proto; re-exported via `protocol.ts`) | `_private/proto/*_pb2` (grpcio-tools; re-exported via `wax.proto`) |
| Operation value shape | proto object `{ vote_operation: {...} }` | dict `{"vote_operation": {...}}` |
| Push API | `tx.pushOperation(op | OperationBase)` -> `this` (`transaction.ts:249`) | `tx.push_operation(op)` -> `Self` (`transaction.py:162`) |
| proto -> C++ handle | `cpp_create_operation_handle(op, true)` (`transaction.ts:236`) | `create_wax_operation(dict, is_protobuf=True)` (`transaction.py:158`) |
| High-level builders | `OperationBase.finalize()` (`operation_base.ts`) | `complex_operations/` (part 07) |

---

## 7. Notable findings

1. **wax's broadcastable surface is 47, not 50** - it omits `custom_binary` (proto
   disabled), `reset_account`, and `set_reset_account` (defunct). Code that enumerates
   "all operations" off wax's proto will be 3 short of hive-core's regular count by
   design. (Verified, section 2.)
2. **The proto oneof is consensus-ordered.** Field numbers are pinned to the C++
   `static_variant` index (+1) and must not be reordered before the virtual band
   (`operation.proto:98-99`). The gaps at 36/38/39 are reserved, not reusable.
3. **Virtual ops are first-class in proto** (fields 100-142) but receive-only - present
   for block/history deserialization and API typing, not for `pushOperation`.
4. **Two synchronized transaction representations.** wax maintains both a JS/Python
   proto `operations[]` array and a C++ transaction handle, updated together on every
   push (`transaction.ts:234-238`). Serialization/signing use the C++ handle.
5. **json_name = HF26 key.** Each oneof field's `json_name` (`<name>_operation`) is the
   HF26 JSON/API operation key; the legacy array form (`["vote", {...}]`) is produced
   separately (part 03 serialization).

---

## 8. Code References

| Topic | File:line |
|-------|-----------|
| Canonical operation oneof | `hive:libraries/protocol/proto/operation.proto:102-195` |
| Consensus-order warning | `hive:.../proto/operation.proto:98-99` |
| Regular ops 1-50 (gaps 36/38/39) | `hive:.../proto/operation.proto:103-149` |
| Virtual ops 100-142 | `hive:.../proto/operation.proto:151-194` |
| C++ static_variant (index comments) | `hive:libraries/protocol/include/hive/protocol/operations.hpp` |
| custom_binary disabled | `hive:.../proto/custom_binary.proto.disabled` |
| TS proto re-exports | `ts/wasm/lib/detailed/protocol.ts:1-` |
| TS pushOperation | `ts/wasm/lib/detailed/transaction.ts:249-256` |
| TS push internals (dual rep) | `ts/wasm/lib/detailed/transaction.ts:234-238` |
| TS OperationBase | `ts/wasm/lib/detailed/operation_base.ts:8-10` |
| TS committed proto patterns | `ts/protobuf_patterns/proto/` |
| Python proto modules | `python/wax/wax/_private/proto/*_pb2.py` (98) |
| Python Transaction + build | `python/wax/wax/_private/transaction.py:52`, `:158`, `:162` |
| Python OnlineTransaction | `python/wax/wax/_private/online_transaction.py:123` |

---

## 9. Open Questions (for later parts / zoom)

- **proto -> C++ conversion internals.** `cpp_create_operation_handle` and the
  `proto_converter` / `api_converter` (part 01) do the proto<->C++ marshalling; the
  exact fc-reflection path (and how `void_t` / `future_extensions` map) is untraced.
- **HF26 vs legacy serialization selection.** How a built operation becomes binary or
  legacy-array JSON (`use_hf26_serialization` boolean from part 01) is part 03.
- **api_to_proto / proto_to_api.** The Python `__init__` exposes `api_to_proto`,
  `proto_to_api`, `proto_to_legacy_api`; the API-shape vs proto-shape distinction (and
  why both exist) belongs to part 06.
- **Operand validation timing.** `cpp_op_validate` exists (part 01); whether
  `pushOperation` validates eagerly or defers to sign/broadcast is a part-03 question.
