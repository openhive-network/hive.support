# Wax Part 05 - Signing & Signers

**Anchor:** wax `2.0.2` (`c9c4918a`).
**Scope:** how a built transaction gets signed - the provider abstraction, the pluggable
signer packages (beekeeper / keychain / metamask / peakvault / external), required-
authority computation and online authority verification, key derivation/recovery, and
memo encryption (including the private-key-leak guard). Picks up the threads parts 03
(`sigDigest` / `addSignature`) and 01 (`IAccountAuthorityProvider`) deferred here.

---

## 1. The provider abstraction (3 interfaces + 2 base classes)

`ts/wasm/lib/detailed/extensions/signatures/index.ts` defines three provider contracts:

| Interface | Methods | Level |
|-----------|---------|-------|
| `ISignatureProvider` (`:4-35`) | `signDigest(pubKey, sigDigest)`, `encryptData(content, key, otherKey?, nonce?)`, `decryptData(content, key, otherKey?)` | low-level, synchronous, **key-specific** |
| `IOnlineSignatureProvider` (`:56-65`) | `signTransaction(tx): Promise<void>` | high-level, async, **signer picks keys** |
| `IOnlineEncryptionProvider` (`:37-54`) | async `encryptData(buffer, recipient)`, `decryptData(buffer)` (recipient by pubkey **or account name**) | high-level encryption |

The signing flow itself lives in two abstract base classes
(`extensions/signatures/extension_helpers.ts`) that concrete signers extend:

- `ASignatureProvider` (`:7-18`) implements `signTransaction`:
  ```ts
  const signatures = await this.generateSignatures(transaction);  // provider-specific
  for (const sig of signatures) transaction.addSignature(sig);     // validate + append (part 03)
  ```
  Subclasses implement only `generateSignatures(tx): Promise<TSignature[]>` (`:17`).
- `AEncryptionProvider extends ASignatureProvider` (`:26-39`) overrides `signTransaction`
  to **encrypt memos first, then sign** (`:28-32`):
  ```ts
  transaction.performOperationEncryption?.(this);  // encrypt marked memo ops (section 6)
  await super.signTransaction(transaction);         // then the base sign flow
  ```
  and adds abstract `encryptData` / `decryptData`.

So the modern signing path is: build tx -> `await provider.signTransaction(tx)` ->
`await chain.broadcast(tx)`. (The `Transaction.sign(provider, pubKey)` method from part 03
is the deprecated manual equivalent.)

---

## 2. Signer packages (pluggable backends)

Signers ship as **separate npm sub-packages** under `ts/packages/` so the core stays
small (part 01): `signers-beekeeper`, `signers-keychain`, `signers-metamask`,
`signers-peakvault`, `signers-external`. Each exports a `*Provider` class extending
`AEncryptionProvider` (or `ASignatureProvider`) with a `static for(...)` factory and a
backend-specific `generateSignatures`.

### BeekeeperProvider (canonical example)

`signers-beekeeper/src/index.ts` (`class BeekeeperProvider extends AEncryptionProvider`,
`:27`):

- `static for(chainOrBase, wallet, publicKeyOrAccount, role?)` (`:36-48`):
  - no `role` -> bind directly to the given public key.
  - with `role` -> `database_api.find_accounts([account])` resolves the **key for that
    role** (`owner`/`active`/`posting`/`memo`; `memo` maps to `memo_key`), returning a
    `Promise`. So you can sign by **account + role** and wax pulls the right key from
    chain state.
- `generateSignatures(tx)` (`:85-89`) = `wallet.signDigest(this.publicKey, tx.sigDigest)`
  - delegates to the beekeeper unlocked wallet.
- `encryptData` / `decryptData` (`:59-77`) forward to `base.encrypt` / `base.decrypt`
  (section 6).

Documented usage (`:12-25`):
```ts
const provider = BeekeeperProvider.for(chain, myWallet, "myaccount", "active");
const tx = await chain.createTransaction();
// ...pushOperation...
await provider.signTransaction(tx);
await chain.broadcast(tx);
```

The other signers follow the same shape over their backends: `keychain` (Hive Keychain
browser extension), `metamask` (MetaMask snap), `peakvault` (PeakVault extension),
`external` (a generic/bring-your-own provider). **Key custody stays in the backend** -
the private key is never handed to wax; wax only ever sees the returned signature.

---

## 3. Required authorities and online verification

### Offline: which authorities are needed

`Transaction.requiredAuthorities` (`transaction.ts:282-333`) calls
`cpp_tx_required_authorities` (`foundation.hpp:276`) and returns
`{ posting, active, owner: Set<account>, other: authority[] }` - the account sets whose
posting/active/owner authority must sign, plus any `other` explicit authorities
(full `{ weight_threshold, account_auths, key_auths }` objects for ops carrying their
own authority).

### Online: do these signatures satisfy the authorities?

`OnlineTransaction` performs real authority verification
(`online_transaction.ts:185-210`). Because account authorities can delegate to other
accounts (`account_auths`), resolution is **recursive and API-backed**:

1. Build the account set from the required active/owner (and posting) accounts.
2. Wrap it in an `AccountAuthorityCachingProvider(chain, accounts)` and expose it to C++
   via `IAccountAuthorityProvider.implement(...)` (`:190-192`) - the part-01 callback
   bridge.
3. Loop: `await authorityCache.acquireData()` (fetch this layer's authorities from the
   API) then `cpp_trace_authority_verification(requiredAuthorities, signatureKeys, impl)`
   (`:199`), **while `authorityCache.canContinue`** - each pass may reveal a deeper
   authority layer to fetch (`:196-201`).
4. The result is an `authority_verification_trace` mapping the present signature keys to
   whether they satisfy each authority.

The core also exposes `cpp_collect_signing_keys` and `cpp_minimize_required_signatures`
(`foundation.hpp:280-281`) for computing/trimming the signing-key set.

---

## 4. Key derivation and recovery

All forward to the shared `foundation` (`foundation.hpp:81-105`), exposed on `WaxBaseApi`:

| Method (TS) | Core | Purpose |
|-------------|------|---------|
| `calculatePublicKey(wif)` (`base_api.ts:480`) | `cpp_calculate_public_key` | WIF private -> public key |
| `getPrivateKeyFromPassword(account, role, password)` (`base_api.ts:471`) | `cpp_generate_private_key(account, role, password)` | derive the role key from a master password |
| `suggestBrainKey()` (`base_api.ts:461`) | `cpp_suggest_brain_key` | generate a brain-key + keys |
| `getPublicKeyFromSignature(sigDigest, signature)` (`base_api.ts:349`) | `cpp_get_public_key_from_signature` | recover the signer's public key |
| `convertRawPrivateKeyToWif(hex)` / `convertRawPublicKeyToWif(hex)` (`base_api.ts:485`,`:490`) | `cpp_convert_raw_*` | raw <-> WIF encoding |

(These overlap the clive key-generation audit material; wax is a thin wrapper over the
same fc crypto.)

---

## 5. Protocol config

`WaxBaseApi.config` (`base_api.ts:367-383`) = `cpp_get_hive_protocol_config(chainId)`
(`foundation.hpp:102`), a cached map of the hive protocol constants for the active chain
(cross-ref `reference/constants.md`). Cached after first access.

---

## 6. Memo encryption and the private-key-leak guard

### Encrypt / decrypt a memo

- `encrypt(wallet, content, mainKey, otherKey?, nonce?)` (`base_api.ts:355-363`):
  `wallet.encryptData(...)` produces the ciphertext, then
  `cpp_crypto_memo_dump_string({ content, from: mainKey, to: otherKey ?? mainKey })`
  (`foundation.hpp:133`) wraps it in the Hive crypto-memo envelope (the `#`-prefixed memo
  form).
- `decrypt(wallet, encrypted)` (`base_api.ts:385-389`):
  `cpp_crypto_memo_from_string(encrypted)` (`foundation.hpp:126`) -> `{ content, from, to }`,
  then `wallet.decryptData(content, from, to)`.

### Transaction-level memo encryption

`Transaction` marks operation ranges for encryption: `startEncrypt(mainKey, otherKey?)`
(`transaction.ts:180`) records a range in `indexKeeper`; `stopEncrypt`
(`transaction.ts:221`) closes it; `performOperationEncryption(provider)`
(`transaction.ts:186`, invoked by `AEncryptionProvider.signTransaction`) encrypts the
marked memo fields before signing; `decrypt(wallet)` (`transaction.ts:346`) walks
operations and decrypts `#`-prefixed memos via an `EncryptionVisitor`.

### Private-key-leak guard

`scanForMatchingPrivateKeys(content, account, accountAuthorities, memoKey, otherKeys?)`
(`base_api.ts:410-418`) -> `cpp_scan_text_for_matching_private_keys` scans text for
references to the account's private keys/password and **throws** on a hit. This is the
source of `WaxPrivateKeyLeakDetectedException` surfaced by `WasmManager` (part 01,
`wasm_errors.ts:55-59`); the related memo-specific guard is `cpp_check_memo_for_private_keys`
(`foundation.hpp:135`). It prevents accidentally publishing a key in a memo/post. (Marked
`@internal` - the `wax_authorities` parameter type is awkward for direct TS use.)

---

## 7. Python parallel

Python shares the C++ crypto/authority core but **not** the TS signer-package ecosystem:

- Signing is via a beekeepy unlocked wallet directly: `await tx.sign(wallet, public_key)`
  -> `wallet.sign_digest(sig_digest, key)` (`transaction.py:113-115`, part 03), plus
  `add_signature`.
- Signer recovery: `get_public_key_from_signature(sig_digest, sig)` (`transaction.py:189`).
- The browser-extension signers (keychain / metamask / peakvault) are inherently
  web/TypeScript and have **no Python equivalent**; beekeeper exists in both worlds (as a
  TS provider package vs a Python beekeepy wallet).
- Key derivation and memo crypto exist in Python via the same `cpp_python_bridge`
  functions (`generate_private_key`, `calculate_public_key`, `decode_encrypted_memo` /
  `encode_encrypted_memo`, `check_memo_for_private_keys`; see part 01 `__init__` exports).

---

## 8. Notable findings

1. **Sign by account + role.** `*.for(chain, wallet, account, role)` resolves the role
   key from chain state (`signers-beekeeper:36-48`), so callers need not know the public
   key up front.
2. **Encrypt-then-sign is enforced by the base class.** `AEncryptionProvider.signTransaction`
   runs `performOperationEncryption` before signing (`extension_helpers.ts:28-32`), so a
   memo is always encrypted against the final signed bytes.
3. **Online authority verification is recursive/multi-layer** and API-backed via the
   `IAccountAuthorityProvider` callback - it keeps fetching deeper `account_auths` layers
   until the authority tree is resolved (`online_transaction.ts:196-201`).
4. **Key custody never enters wax.** Providers return signatures; private keys stay in
   the backend (beekeeper/keychain/...). wax's own key methods operate on WIF/raw inputs
   the caller supplies.
5. **Built-in private-key-leak guard** (`scanForMatchingPrivateKeys`) throws a dedicated
   exception - a safety feature for memo/post content.
6. **Browser signers are TS-only**; Python signs via beekeepy wallets.

---

## 9. Code References

| Topic | File:line |
|-------|-----------|
| Provider interfaces | `ts/wasm/lib/detailed/extensions/signatures/index.ts:4-65` |
| Base provider classes (sign flow) | `extensions/signatures/extension_helpers.ts:7-39` |
| BeekeeperProvider | `ts/packages/signers-beekeeper/src/index.ts:27`,`:36-48`,`:85-89` |
| Signer packages | `ts/packages/signers-{beekeeper,keychain,metamask,peakvault,external}` |
| requiredAuthorities | `ts/wasm/lib/detailed/transaction.ts:282-333`; `core/foundation.hpp:276` |
| Online authority verification | `ts/wasm/lib/detailed/online_transaction.ts:185-210`; `foundation.hpp:249`,`:21` |
| collect / minimize signing keys | `foundation.hpp:280-281` |
| Key derivation/recovery | `base_api.ts:349`,`:461-490`; `foundation.hpp:81-105` |
| Protocol config | `base_api.ts:367-383`; `foundation.hpp:102` |
| Memo encrypt/decrypt | `base_api.ts:355-389`; `foundation.hpp:126`,`:133` |
| Tx-level memo encryption | `transaction.ts:180`,`:186`,`:221`,`:346` |
| Private-key-leak guard | `base_api.ts:410-418`; `foundation.hpp:135`; `wasm_errors.ts:55-59` |
| Python signing | `python/wax/wax/_private/transaction.py:113-115`,`:189` |

---

## 10. Open Questions (for later parts / zoom)

- **`AccountAuthorityCachingProvider` internals.** The exact caching/`canContinue`
  termination logic and how many API round-trips a deep authority tree costs is untraced.
- **Multisig assembly.** How an app collects signatures from multiple
  providers/devices and merges them (beyond a single `generateSignatures`) is not shown
  here.
- **`signers-external` contract.** What the generic external provider expects from a
  bring-your-own backend (vs the named integrations) needs its own read.
- **memo `nonce` semantics** and the binary-vs-string `encryptData` branch in the
  beekeeper provider (`signers-beekeeper:59-66`) - a zoom candidate.
- **`getPrivateKeyFromPassword` exact derivation** (account+role+password -> key) vs the
  hive-core/clive key-generation audit - cross-link rather than re-derive.
