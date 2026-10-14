# Wax Reference - Signing, Signers, Authorities, Keys, Memo

Deep detail: `findings/05-signing-signers.md`.

## Provider abstraction

| Interface | Key method | Level |
|-----------|-----------|-------|
| `ISignatureProvider` | `signDigest(pubKey, digest)`, `encryptData`, `decryptData` | low-level, key-specific |
| `IOnlineSignatureProvider` | `signTransaction(tx)` | high-level, signer picks keys |
| `IOnlineEncryptionProvider` | async `encryptData(buf, recipient)` / `decryptData` | encryption |

Base classes (`extension_helpers.ts`): `ASignatureProvider.signTransaction` =
`generateSignatures(tx)` then `addSignature` each; `AEncryptionProvider` runs
`performOperationEncryption` (memos) **before** signing. Concrete signers implement
`generateSignatures` (+ encrypt/decrypt).

## Signer packages (npm, pluggable)

`@hiveio/wax-signers-{beekeeper, keychain, metamask, peakvault, external}`. Each:
`Provider.for(chainOrBase, backend, pubKeyOrAccount, role?)` then `signTransaction(tx)`.

```ts
const provider = await BeekeeperProvider.for(chain, wallet, "alice", "active");  // with a role it resolves the key via find_accounts and returns a Promise
await provider.signTransaction(tx);
```

- `role` (`owner`/`active`/`posting`/`memo`) -> wax resolves the key via `find_accounts`.
- **Key custody stays in the backend** - wax only ever sees the returned signature.
- Browser signers (keychain/metamask/peakvault) are TS-only; Python signs via a beekeepy
  unlocked wallet (`await tx.sign(wallet, key)`).

## Authorities

| | Call | Returns |
|--|------|---------|
| Offline: who must sign | `tx.requiredAuthorities` | `{ posting, active, owner: Set, other: authority[] }` |
| Online: do signatures satisfy? | `OnlineTransaction.performOnChainVerification()` | recursive `cpp_trace_authority_verification` via the `IAccountAuthorityProvider` API callback |

Core also has `cpp_collect_signing_keys` / `cpp_minimize_required_signatures`.

## Keys

| Method | Purpose |
|--------|---------|
| `calculatePublicKey(wif)` | WIF private -> public |
| `getPrivateKeyFromPassword(account, role, password)` | derive a role key from a master password |
| `suggestBrainKey()` | generate a brain key + keys |
| `getPublicKeyFromSignature(sigDigest, sig)` | recover the signer's public key |
| `convertRawPrivateKeyToWif(hex)` / `convertRawPublicKeyToWif(hex)` | raw <-> WIF |

## Memo encryption

- `wax.encrypt(wallet, content, mainKey, otherKey?, nonce?)` -> ciphertext wrapped in the
  `#`-prefixed crypto-memo envelope (`cpp_crypto_memo_dump_string`).
- `wax.decrypt(wallet, encrypted)` -> plaintext.
- Transaction-level: `tx.startEncrypt(mainKey, otherKey?)` / `stopEncrypt` mark memo
  ranges; `performOperationEncryption` (during sign) encrypts them; `tx.decrypt(wallet)`
  decrypts `#`-memos.
- **Private-key-leak guard**: `scanForMatchingPrivateKeys(...)` throws
  `WaxPrivateKeyLeakDetectedException` if text contains the account's keys/password.
