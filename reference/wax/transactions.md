# Wax Reference - Transaction Lifecycle

Build -> sign -> broadcast, at a glance. Deep detail:
`findings/03-transaction-lifecycle.md`.

## End-to-end (TypeScript)

```ts
const chain = await createHiveChain();
const tx = await chain.createTransaction();            // head block -> TaPoS; expiration "+1m"
tx.pushOperation({ transfer_operation: { from, to, amount, memo } });
const provider = BeekeeperProvider.for(chain, wallet, "alice", "active");
await provider.signTransaction(tx);                     // encrypt-then-sign, appends signature
await chain.broadcast(tx);
```

Python: `create_hive_chain()` -> `tx = chain.create_transaction()` -> `tx.push_operation(...)`
-> `await tx.sign(wallet, key)` -> broadcast.

## Stages

| Stage | TS surface | Core call |
|-------|-----------|-----------|
| Create (online) | `chain.createTransaction(expiration?)` | head block cached ~3 s for TaPoS |
| Create (offline) | `new Transaction(api, { taposBlockId, ... })` / `Transaction.fromApi(...)` | `cpp_create_transaction_handle` |
| TaPoS | from a block id | `cpp_get_tapos_data` -> `{ ref_block_num, ref_block_prefix }` |
| Expiration | default `"+1m"`; applied **once** at first flush | `cpp_tx_set_expiration` |
| Build | `tx.pushOperation(...)` | `cpp_create_operation_handle` + `cpp_tx_add_operation` |
| Sig digest | `tx.sigDigest` (binds chainId) / `tx.legacy_sigDigest` | `cpp_tx_sig_digest(h, chainId, hf26)` |
| Sign | `provider.signTransaction(tx)` (preferred) / `tx.addSignature(sig)` | `cpp_tx_add_signature` |
| Validate | `tx.validate()` (offline); online async on `OnlineTransaction` | `cpp_tx_validate` |
| Id | `tx.id` / `tx.legacy_id` | `cpp_tx_id(h, hf26)` |
| Broadcast | `chain.broadcast(tx)` | `network_broadcast_api.broadcast_transaction` |

## Serialization forms

| Method | Output |
|--------|--------|
| `tx.toApi()` / `tx.toString()` | HF26 JSON |
| `tx.toBinaryForm(strip?)` | HF26 binary (hex) |
| `tx.toApiJson()` | API-shaped JSON object |
| `tx.toLegacyApi()` | legacy `["op_name", {...}]` JSON |

`use_hf26_serialization` is a per-call boolean, not a global mode.

## Gotchas

- **Expiration locks at first serialize/sign**, not construction - holding a built tx does
  not burn its window early.
- **`Transaction.sign(provider, pubKey)` is deprecated** - use the signer's
  `signTransaction`, or `sigDigest` + `addSignature`.
- **Mainnet expiration uses local realtime** (avoids API-node clock skew); test chains use
  the head block time.
- The JS/Python proto array and the C++ handle are kept in sync; the handle is rebuilt
  when ops mutate (e.g. `decrypt`).

## Inspection

`tx.impactedAccounts`, `tx.requiredAuthorities` (-> [signing.md](signing.md)),
`tx.signatureKeys` (recover signers), `tx.isSigned()`, `tx.transaction` (proto value).
