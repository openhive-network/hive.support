# wax KB gaps found while drafting rules and evals (2026-10-14)

- **Topic**: wax
- **Type**: addition
- **Affects**: research/wax/findings/01-architecture.md, 03-transaction-lifecycle.md, 05-signing-signers.md; reference/wax/api.md, signing.md, transactions.md
- **Source**: wax worktree `workspace/wax/c9c4918a84/` (2.0.2); line references below were read there by the drafting agent and need the maintainer's confirmation before incorporation

## Description

Found by the rules/evals drafting pass. Two related items were verified by the maintainer and
applied the same day (examples now `await` `BeekeeperProvider.for(..., role)`;
`reference/wax/api.md` now says a recognized hived error is rethrown with `WaxChainApiError`
as its `cause`). The following remain pending:

1. **Role-based provider picks the first key auth only.** `BeekeeperProvider.for(..., role)`
   resolves `account[role].key_auths[0][0]` (and `memo` -> `memo_key`)
   (`ts/packages/signers-beekeeper/src/index.ts:36-48`). findings/05 says only "resolves the
   key for that role"; multisig / multi-key accounts silently get the first listed key. Worth a
   sentence in findings/05 section 2 and in `reference/wax/signing.md` (Signer packages).
2. **`WasmManager.module` getter is imprecisely described.** `wasm_errors.ts:85-99`: the
   cached branch calls `resolve(this.mainModule)` but has no `return`, so `wasmFn` runs again
   and overwrites `mainModule` on every access. findings/01 says it "resolves once and
   caches". No practical impact at 2.0.2 (the getter is read once per
   `createWaxFoundation` / `createHiveChain`, `base.ts:16`, `chain.ts:23`), but the text
   should say so and the code is a latent upstream bug.
3. **TS/Python divergence not recorded.** Python `validate()` calls `_flush_transaction()`
   first (`python/wax/wax/_private/transaction.py:109-111`), which locks the expiration;
   TS `validate()` (`transaction.ts:335-337`) does not flush. Belongs in findings/03 section
   10 (divergences) and the transactions reference.
4. **Expiration input formats undocumented** (findings/03 lists it as an open question).
   `util/expiration_parser.ts:21-50` accepts a `Date`, a unix-time number, an absolute date
   string, or a relative `"+N"` (seconds) / `"+Nm"` / `"+Nh"`; an invalid offset throws
   `WaxError("Invalid expiration time offset")`. Add to `reference/wax/transactions.md`
   (Stages: Expiration) and `reference/wax/api.md` (`createTransaction(expiration?)`).
5. **Upstream doc bug worth a wax issue** (not a KB error): the JSDoc example at
   `ts/packages/signers-beekeeper/src/index.ts:12-25` uses the stale argument order
   `BeekeeperProvider.for(myWallet, "myaccount", "active", chain)`; the real signature is
   `for(chainOrBase, wallet, publicKeyOrAccount, role?)`.

## Evidence

Line references above, all in the pinned 2.0.2 worktree; items 1 and 2 were additionally
read by the maintainer at `signers-beekeeper/src/index.ts:36-48` and `chain_api.ts:85-96`.
