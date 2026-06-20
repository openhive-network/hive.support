# Wax Part 03 - Transaction Lifecycle

**Anchor:** wax `2.0.2` (`c9c4918a`).
**Scope:** the full life of a transaction in wax - create -> set TaPoS -> set
expiration -> add operations -> serialize -> sign -> get id -> broadcast. Operation
building is part 02; the signer providers are part 05; the chain/API plumbing and
`broadcast` internals are part 06. The cross-language picture is TS-first with the
Python parallel in section 10.

Central file: `ts/wasm/lib/detailed/transaction.ts` (the `Transaction` class).

---

## 1. Lifecycle at a glance

```
create ── TaPoS ── (default expiration "+1m") ── pushOperation* ──┐
                                                                  │ build (lazy)
   broadcast ◄── sign ◄── sigDigest ◄── serialize ◄── flush ◄─────┘
   (part 06)    addSig    (per chainId)  (4 forms)   applyExpiration (once)
```

Throughout, wax holds the transaction in **two synchronized representations** (as with
operations in part 02): the JS-side proto `transaction` (`this.target`) and the C++
`hive_transaction_handle` (`this.txHandle`). Every mutation updates both; serialization,
digest, id, and signing all run on the C++ handle.

---

## 2. Creating a transaction

### Offline

`new Transaction(api, transactionOptions)` (`transaction.ts:62`). Options either carry a
ready proto transaction (`protoTransaction`, used by `fromApi`) or a TaPoS block id:

- With `protoTransaction` (`transaction.ts:72-77`): clone it and build the C++ handle
  via `cpp_create_transaction_handle(target, true)`.
- Otherwise (`transaction.ts:79-89`): compute TaPoS from `taposBlockId`, then build
  `target = { ref_block_num, ref_block_prefix, expiration:'', extensions:[],
  operations:[], signatures:[] }` and the C++ handle.

`Transaction.fromApi(api, data)` (`transaction.ts:137-143`) parses an API/JSON
transaction, runs `cpp_tx_api_to_proto(obj)` to convert API-shape -> proto, and wraps
it as a `protoTransaction`.

### Online

`HiveChainApi.createTransaction(expirationTime?)` (`chain_api.ts:185-188`):

```ts
const { headBlockTime, headBlockId } = await this.acquireChainReferenceData(3000);
return new OnlineTransaction(this, { headBlockTime, taposBlockId: headBlockId, expirationTime });
```

`acquireChainReferenceData` reads `database_api.get_dynamic_global_properties()` for
`head_block_id` + `time` and caches them in `taposCache` (`chain_api.ts:48`,`:194-195`)
for the liveness window (3000 ms; cf. Python `TAPOS_LIVENESS = 3000`,
`_private/chain_api.py:29`). So a burst of `createTransaction` calls reuses one head
block rather than refetching. The returned `OnlineTransaction` adds API-backed
validation (section 9).

---

## 3. TaPoS

`taposRefer(hex)` (`transaction.ts:56-58`) calls `cpp_get_tapos_data(blockId)`
(`foundation.hpp:141`), returning `{ ref_block_num, ref_block_prefix }` derived from a
block id - the standard Hive Transaction-as-Proof-of-Stake reference (low 16 bits of the
block number + a 4-byte prefix of the block id; see the hive-core consensus KB). The
block id used is the chain head at create time (online) or a caller-supplied id
(offline). TaPoS plus expiration is what bounds a transaction to a recent fork and a
short validity window.

---

## 4. Expiration (lazy, locked once)

The expiration is **not** fixed at construction. The field defaults to the relative
string `"+1m"` (`transaction.ts:63`); the absolute value is computed the first time the
transaction is flushed:

- `flushTransaction()` (`transaction.ts:168-172`) applies expiration only if
  `target.expiration` is still empty - "Sign can be called before build, so ensure that
  we are applying the expiration time only once". Every serialize/sign/id getter calls
  it first.
- `applyExpiration()` (`transaction.ts:339-344`): `calculateExpiration(this.expirationTime,
  this.chainHeadBlockTime)` -> ISO string trimmed to Hive's format
  (`toISOString().slice(0, -5)`, dropping `.000Z`) -> `cpp_tx_set_expiration(txHandle, ...)`
  (`foundation.hpp:270`).

**Reference-time subtlety** (`transaction.ts:66-70`): for **mainnet** (`chainId ===`
the default), `chainHeadBlockTime` is left undefined so `calculateExpiration` uses
real/local time - the source comment notes this "eliminate[s] potential API node time
[skew]". For **non-mainnet** chains it uses the supplied `headBlockTime`, easing
testnet/mirrornet prototyping. Net effect: on mainnet, `"+1m"` means one minute from
when you first serialize/sign, by local clock.

---

## 5. Build operations

`pushOperation(op | OperationBase)` appends to both representations
(`cpp_create_operation_handle` + `cpp_tx_add_operation`) - fully covered in part 02. The
JS `target.operations[]` and the C++ handle stay in lockstep.

---

## 6. Serialization (four forms + HF26/legacy)

All flush first (locking expiration). The `use_hf26_serialization` boolean from part 01
selects HF26 vs legacy wire format per call:

| Method | Core call | Output |
|--------|-----------|--------|
| `toString()` / `toApi()` (`:145`,`:174-178`) | `cpp_tx_to_json` | HF26 JSON string |
| `toBinaryForm(strip?)` (`:156-160`) | `cpp_tx_to_binary(h, true, strip)` | HF26 binary, hex |
| `toApiJson()` (`:149-154`) | `cpp_tx_proto_to_api(tx)` | API-shaped JSON object (`ApiTransaction`) |
| `toLegacyApi()` (`:162-166`) | `cpp_tx_to_legacy_json` | legacy `["op_name", {...}]` JSON |
| `binaryViewMetadata` / `legacy_binaryViewMetadata` (`:110-127`) | `cpp_tx_binary(h, isHf26, strip)` | binary + parsed offset tree (part 04) |

So there are two parallel format families (HF26 and legacy), and within JSON two shapes
(proto-shape via `to_json`, API-shape via `proto_to_api`). `toApi()` is just
`toString()` (HF26 JSON).

---

## 7. Signing

### The digest

`sigDigest` (`transaction.ts:258-262`) = `cpp_tx_sig_digest(txHandle, this.chainId, true)`
(`foundation.hpp:279`); `legacy_sigDigest` (`:264-268`) passes `false`. The digest binds
the **chain id** (replay protection across mainnet / testnet / mirrornet) and the
serialization mode. You sign this digest, not the transaction bytes directly.

### Preferred flow: digest -> external sign -> addSignature

1. read `tx.sigDigest`,
2. sign it with a key (a signer/wallet provider, part 05),
3. `tx.addSignature(sig)` (`transaction.ts:399-405`): `validate()` then `signWithHandle`.

`signWithHandle(sig)` (`:378-381`) pushes to `target.signatures[]` **and**
`cpp_tx_add_signature(txHandle, sig)` (`foundation.hpp:269`) - dual representation again.

### Deprecated all-in-one

`sign(provider, publicKey)` (`transaction.ts:386-397`, marked `@deprecated`):
`validate -> flush -> encryptOperations -> provider.signDigest(publicKey, sigDigest) ->
signWithHandle`. Superseded by the digest+addSignature split and the signer abstraction
(part 05).

### Inspecting signatures

- `signatureKeys` / `legacy_signatureKeys` (`:129-135`) -> `cpp_tx_signature_keys(h,
  chainId, isHf26)` recovers the public keys that produced the current signatures.
- `isSigned()` (`:407-409`) = `target.signatures.length > 0`.

---

## 8. Id and inspection

- `id` / `legacy_id` (`:270-280`) -> `cpp_tx_id(txHandle, true|false)` (`foundation.hpp:274`).
- `impactedAccounts` (`:92-99`) -> `cpp_tx_impacted_accounts`.
- `requiredAuthorities` (`:282-334`) -> the active/posting/owner sets needed to sign
  (detailed in part 05).
- `transaction` getter (`:411-415`) -> the finalized proto `target`.

---

## 9. Validation and broadcast

- `validate()` (`transaction.ts:335`) -> `cpp_tx_validate` (`foundation.hpp:283`):
  offline structural/protocol validation. Called inside `addSignature`/`sign`.
- `OnlineTransaction` (`online_transaction.ts`) overrides per-operation hooks
  (`transfer_operation`, `account_create_operation`, ...) and an async
  `validate(operations)` (`online_transaction.ts:36`) that performs **API-backed**
  checks (e.g. resolving accounts) the offline validator cannot.
- **Broadcast** (lifecycle endpoint, part 06): `HiveChainApi.broadcast(tx)`
  (`chain_api.ts:110`) accepts `ApiTransaction | ITransaction | IOnlineTransaction` and
  calls `network_broadcast_api.broadcast_transaction(...)` (`chain_api.ts:116`).

---

## 10. Python parallel

`python/wax/wax/_private/transaction.py` mirrors the TS class over the same C++ core:

| Stage | TypeScript | Python |
|-------|------------|--------|
| sig digest | `get sigDigest` -> `cpp_tx_sig_digest(h, chainId, true)` (`:258`) | `sig_digest` -> `tx_sig_digest(h, chain_id, use_hf26_serialization=True)` (`transaction.py:87-89`) |
| sign | `sign()` (deprecated) | `async sign(wallet, public_key)` -> `wallet.sign_digest(sig_digest, key)` (`transaction.py:113-115`) |
| add signature | `addSignature(sig)` (`:399`) | `add_signature(sig)` (`transaction.py:118`) |
| serialize | `toBinaryForm` / `toApi` / `toApiJson` (`:145-166`) | `to_binary_form` / `to_api` / `to_api_json` (`transaction.py:127-154`) |
| expiration | lazy `applyExpiration` -> `cpp_tx_set_expiration` (`:339`) | lazy `_apply_expiration` -> `tx_set_expiration(h, target.expiration)` (`transaction.py:177-184`) |
| signer recovery | `signatureKeys` | `get_public_key_from_signature(sig_digest, sig)` (`transaction.py:189`) |

Both default expiration to a relative window, lock it once, and keep proto + C++ handle
in sync. (Python `sign` takes an unlocked beekeeper wallet directly; TS routes signing
through a provider/signer - part 05.)

---

## 11. Notable findings

1. **Expiration is locked at first flush, not construction** (`transaction.ts:168-172`).
   The relative default `"+1m"` is resolved when you first serialize/sign, so holding a
   built-but-unsent transaction does not consume its validity window early.
2. **Mainnet vs non-mainnet expiration reference** (`transaction.ts:66-70`): mainnet uses
   local realtime (avoids API-node clock skew); test chains use the head block time.
   A subtle correctness/UX distinction baked into the constructor.
3. **Dual representation, re-created on op mutation.** The C++ handle is rebuilt from
   `target` when operations change out-of-band (e.g. `decrypt`, `transaction.ts:358`).
4. **`sigDigest` binds `chainId`** - the same operations sign to different digests on
   mainnet/testnet/mirrornet, which is the cross-chain replay guard.
5. **`sign()` is deprecated** in favor of `sigDigest` + `addSignature`, reflecting the
   move to pluggable signers (part 05) and digest-only signing.
6. **TaPoS head block is cached ~3s** (`chain_api.ts:48`,`:194-195`), so rapid
   transaction creation reuses one reference block.

---

## 12. Code References

| Topic | File:line |
|-------|-----------|
| Transaction class | `ts/wasm/lib/detailed/transaction.ts:48` |
| Constructor (TaPoS, expiration, handle) | `transaction.ts:62-90` |
| TaPoS (`cpp_get_tapos_data`) | `transaction.ts:56-58`; `core/foundation.hpp:141` |
| Online createTransaction + TaPoS cache | `ts/wasm/lib/detailed/chain_api.ts:185-188`,`:48`,`:194-195` |
| fromApi | `transaction.ts:137-143` |
| flushTransaction / applyExpiration | `transaction.ts:168-172`,`:339-344`; `foundation.hpp:270` |
| Serialization (4 forms) | `transaction.ts:145-166`,`:110-127` |
| sigDigest / legacy_sigDigest | `transaction.ts:258-268`; `foundation.hpp:279` |
| sign (deprecated) / addSignature / signWithHandle | `transaction.ts:386-397`,`:399-405`,`:378-381`; `foundation.hpp:269` |
| signatureKeys / isSigned | `transaction.ts:129-135`,`:407-409` |
| id / legacy_id | `transaction.ts:270-280`; `foundation.hpp:274` |
| validate | `transaction.ts:335`; `foundation.hpp:283` |
| broadcast (endpoint) | `chain_api.ts:110-116` |
| Python transaction | `python/wax/wax/_private/transaction.py:87-189` |

---

## 13. Open Questions (for later parts / zoom)

- **`calculateExpiration` parsing grammar.** The relative-string syntax (`"+1m"`,
  absolute ISO, etc.) lives in `util/expiration_parser` (`dateFromString` is imported by
  `chain_api`); the exact accepted formats are untraced here.
- **`encryptOperations` / `startEncrypt` / `decrypt`.** Memo encryption woven into the
  sign path (`transaction.ts:180-221`,`:346-377`) belongs to part 05.
- **`requiredAuthorities` computation** (`transaction.ts:282-334`) and the
  collect-signing-keys / minimize-signatures flow - part 05.
- **HF26 vs legacy digest difference.** Why two digests exist and when a caller needs
  the legacy one (pre-HF26 nodes/tools) - a part-05/06 detail.
- **`broadcast` response handling / retries** and the `OnlineTransaction` API-backed
  validation set - part 06.
