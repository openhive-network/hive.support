# Wax Reference - Operations & Builders

How wax models and builds operations. Deep detail: `findings/02-operations-surface.md`,
`findings/07-complex-operations.md`. For each operation's fields/semantics, use the
hive-core reference (`../operations.md`).

## The operation model

- Operations are the **`proto2` `operation` oneof** (`hive:libraries/protocol/proto/
  operation.proto`), a mirror of hive-core's `operation` static_variant.
- proto field number = C++ static_variant index **+ 1**; order before the virtual band is
  **consensus-critical** (do not reorder).
- An operation value is a oneof: an object with exactly one `*_operation` field, e.g.
  `{ vote_operation: { voter, author, permlink, weight } }`.
- `json_name` per field (`<name>_operation`) is the HF26 JSON/API key.

## The surface: 90 operations

| Band | proto fields | Count | Broadcastable? |
|------|--------------|-------|----------------|
| Regular | 1-50 (gaps at 36/38/39) | **47** | yes |
| Virtual | 100-142 | **43** | no (chain-emitted; present for deserialization/API) |

**Omitted vs hive-core's 50 regular**: `custom_binary` (proto `.disabled`),
`reset_account`, `set_reset_account` (defunct). SMT ops are compiled out on mainnet.

## Building & pushing

| | TypeScript | Python |
|--|------------|--------|
| Value shape | object `{ vote_operation: {...} }` | dict `{"vote_operation": {...}}` |
| Push | `tx.pushOperation(op | OperationBase)` -> `this` | `tx.push_operation(op)` -> `Self` |
| proto -> C++ | `cpp_create_operation_handle(op, true)` | `create_wax_operation(dict, is_protobuf=True)` |

`pushOperation` keeps a JS/Python proto `operations[]` array **and** the C++ transaction
handle in sync. Operation types are re-exported from `protocol.ts` (TS) / `wax.proto`
(Python).

## High-level builders

Both extend `OperationBase` (`finalize(sink): Iterable<operation>`); pushed via
`pushOperation`. One builder may emit several operations.

### complex_operations/ (compose protocol ops)

| Builder | Emits |
|---------|-------|
| `CommentOperation` / `BlogPostOperation` / `ReplyOperation` | `comment` (+ optional `comment_options`: metadata, beneficiaries) |
| `AccountAuthorityUpdateOperation` | `account_update` / `account_update2` (via role classes: owner/active/posting/memo) |
| `DefineRecurrentTransferOperation` / `RecurrentTransferRemovalOperation` | `recurrent_transfer` (removal = amount 0) |
| `WitnessSetPropertiesOperation` | `witness_set_properties` (binary props encoding) |
| `LegacyVoteOperation`, `UpdateProposalOperation` | `vote` / `update_proposal` |

### hive_apps_operations/ (custom_json apps)

Pattern: **stage** (builder methods append to `body`) -> **`authorize(postingAuths,
auths?)`** (wraps each into `custom_json_operation { id, json, required_auths,
required_posting_auths }`) -> **`finalize`** returns the ops.

| Builder | `id` | Methods (examples) |
|---------|------|--------------------|
| `FollowOperation` | `follow` | `followBlog`, `unfollowBlog`, `muteBlog`, `blacklistBlog`, `reblog` (following list <= 100) |
| community builder | community ids | community management |
| rc builder | `rc` | RC delegation |

**Only `rc` is chain-interpreted**; `follow`/`community` are hivemind-layer. JSON uses a
bigint->string replacer (fc `as_int64`).

Both families are pure client-side ergonomics - identical bytes to hand-built operations.
Python ships parallel `complex_operations/` + `hive_apps_operations/`.
