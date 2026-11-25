# Findings: validate-evaluate-gaps

## Summary

Hive checks an operation in two completely separate layers: the stateless protocol-level
`validate()` method on the operation struct (`libraries/protocol/`) and the stateful evaluator
`do_apply()` method in the chain layer (`libraries/chain/hive_evaluator*.cpp`). The decisive
discovery of this zoom is that **`validate()` is skipped on two of the most important code paths —
default replay and checkpoint sync — while the evaluator's `do_apply()` always runs on every
operation in every block.** That makes the evaluator the *sole* consensus authority for historical
blocks: any rule enforced only in `validate()` is a non-consensus "first-line filter" for new
transactions and live blocks, not a hard rule. Combined with the fact that `validate()` is also
**hardfork-agnostic** (it has no `has_hardfork` access), this structurally forces every
state-dependent or version-dependent rule into the evaluator and explains code comments such as
"the check can't be in validate()" (`hive_evaluator.cpp:72`).

## Key Discoveries

### 1. `validate()` is conditionally skipped; evaluators are not
- **What**: `database_impl::apply_operation` dispatches to the evaluator unconditionally:
  `_evaluator_registry.get_evaluator( op ).apply( op )` with no skip flag
  (`database.cpp:2757`). By contrast `validate()` is invoked inside
  `database::validate_transaction` only when `!(skip & skip_validate)` (`database.cpp:2588`).
- **Where**: `database.cpp:2757` (evaluator), `database.cpp:2588` (validate gate),
  `chain_plugin.cpp:1266` and `chain_plugin.cpp:1082` (where `skip_validate` is set).
- **Impact**: During default replay (`chain_plugin.cpp:1252-1267`, "no need to validate
  operations") and while syncing blocks at/before the last checkpoint
  (`chain_plugin.cpp:1070-1085`), `validate()` does not run at all. Only `do_apply()` runs.
  The evaluator — not `validate()` — defines what is actually accepted into chain state on
  those paths.

### 2. `validate()` is hardfork-agnostic, which forces version logic into evaluators
- **What**: `validate()` has no database handle and therefore cannot call `has_hardfork()`.
  Part 03 states this explicitly ("No hardfork-conditional logic exists in protocol-level
  validate() methods"). Every "allowed before HF X, forbidden after" rule must therefore live
  in the evaluator, guarded by `has_hardfork()` and/or `is_in_control()`.
- **Where**: e.g. `hive_evaluator.cpp:66-75` (witness_update canonical-symbol check, post-HF14),
  `hive_evaluator_account.cpp:283-291` (account_update auth-size check, post-HF20).
- **Impact**: The split is not arbitrary; it is structural. `validate()` may only hold rules that
  are *universally true across all of chain history*. Anything else is evaluator territory.

### 3. Three enforcement tiers, not two
- **What**: There is an intermediate tier between `validate()` and hard consensus checks: the
  `is_in_control()` "softfork" check. `is_in_control() = is_validating_one_tx() ||
  is_producing_block()` (`database.hpp:176`) — true for new transactions and block production,
  **false during replay and when applying another node's block.**
- **Where**: `hive_evaluator_social.cpp:123` (max-beneficiaries softfork),
  `hive_evaluator_social.cpp:187` (soft comment-depth limit).
- **Impact**: A check `if( _db.is_in_control() || _db.has_hardfork(X) )` is enforced immediately
  for new traffic, but for blocks from other producers and on replay only from HF X on. Distinct
  from `is_processing_block()` (`database.hpp:164`), which is **true** during replay.

### 4. Several `validate()` rules are strictly looser than the evaluator
- **What**: For some operations `validate()` accepts inputs the evaluator later rejects. The
  evaluator is the binding rule; `validate()` just fails to pre-filter.
- **Where**: `feed_publish` (validate accepts either price ordering, evaluator requires
  HBD/HIVE post-HF20 — `hive_evaluator.cpp:599-605`); `withdraw_vesting` (validate omits the
  non-negative check, evaluator handles negative VESTS — `hive_evaluator_transfer.cpp:345-351`);
  `transfer` (validate allows any non-vesting symbol, evaluator's `adjust_balance` rejects
  non-HIVE/HBD).
- **Impact**: These are the clearest "gaps" — a transaction that passes `validate()` can still
  be rejected at apply time, and on replay paths the `validate()` step that would have caught
  a malformed input never runs anyway.

### 5. Recovery-request authority size: checked on every path when in control or under HF29
- **What**: `request_account_recovery`'s `validate()` does not check authority *membership size*:
  besides the two account names it calls only `new_owner_authority.validate()`, which checks the
  account names in the authority, not membership count (`hive_operations.cpp:720-725`); the size
  check is the evaluator's. HF29 switch
  `HIVE_HARDFORK_1_29_FIX_ENFORCEMENT_OF_AUTHORITY_SIZE_ON_RECOVERY_REQUEST` (defined in 1.28.8,
  inactive on mainnet): `request_account_recovery` checks the size of the new owner authority on
  every request path (`hive_evaluator_account.cpp:500-506`). A 1.28.8 node already applies this
  check to new transactions submitted to it (API or P2P) and to blocks it produces
  (`is_in_control()`, `database.hpp:176`; Part 01, section HF29 (Defined in 1.28.8, Inactive on
  Mainnet)).
- **Where**: `hive_evaluator_account.cpp:500-506` (the check before the branch on new / cancel /
  change request, with the comment "after activation of HF29 check if the check can be moved to
  operation validate").
- **Impact**: The size rule for this operation is an evaluator rule, not a `validate()` rule.

---

## The Execution Model — when each layer runs

### `validate()` invocation path (stateless, protocol layer)
- `transaction::validate()` iterates operations and calls `operation_validate(op)` for each
  (`transaction.cpp:40-45`; two-arg notify variant `transaction.cpp:47-56`).
- `full_transaction_type::validate()` caches the result (`full_transaction.cpp:215-231`), backed
  by `precompute_validation()` (`full_transaction.cpp:186-213`) which may run in parallel worker
  threads as an optimization.
- The chain layer calls it from `database::validate_transaction`
  (`database.cpp:2538`, gate at `database.cpp:2588`), reached two ways:
  1. `_apply_transaction` → `validate_transaction(full_transaction, skip)` with
     `skip = get_node_skip_flags()` (`database.cpp:2687`).
  2. Fast-confirm path → `validate_transaction(full_transaction, skip_tapos_check)`
     (`database.cpp:2952`).

### `skip_validate` — where validation is turned OFF
`skip_validate` is documented as "used prior to checkpoint, skips validate() call on transaction"
(`database.hpp:215`). It is set in four places:

| Context | Location | Rationale (from code) |
|---------|----------|----------------------|
| **Default replay** | `chain_plugin.cpp:1266` | "no need to validate operations" (unless `--validate-during-replay`, `chain_plugin.cpp:1255`) |
| **Checkpoint sync** | `chain_plugin.cpp:1082` | Blocks `block_num <= checkpoints.rbegin()->first` skip validate/sig/authority/invariants; normal validation resumes after the last checkpoint (`chain_plugin.cpp:1087-1092`) |
| **Re-push of pending txs** | `db_with.hpp:176` | "operations once validated cannot become invalid" — these txs were validated when first received |
| **Queen-mode block production** | `queen_plugin.cpp:118` | "transactions were validated when added to pending"; the queen plugin refuses to initialize without `USE_ALTERNATE_CHAIN_ID`, i.e. on mainnet builds (`queen_plugin.cpp:273-275`) |

The gate at `database.cpp:2588` carries the comment *"issue #505 explains why this skip_flag is
disabled"* — i.e. in normal live block application `skip_validate` is intentionally **not** set,
so `validate()` does run for live blocks past the last checkpoint and for newly submitted
transactions. Checkpoints are loaded from config into `chain_plugin_impl::checkpoints`
(`chain_plugin.cpp:1683`); this document makes **no claim** about which checkpoints are configured
on any running node.

### Evaluator invocation path (stateful, chain layer) — always runs
- `database_impl::apply_operation` (`database.cpp:2739-2763`): emits pre-apply notification,
  applies the RC discount hook post-HF20 (`database.cpp:2754-2755`), then calls
  `_evaluator_registry.get_evaluator( op ).apply( op )` (`database.cpp:2757`), then the post-apply
  notification. **No skip flag gates the evaluator call.**
- `apply()` (`evaluator.hpp:33-38`) downcasts and calls `do_apply()` on the typed operation.

### Net consequence
```
                       new tx / block production   live block (post-checkpoint)   replay (default) / pre-checkpoint sync
validate()  (static)          RUN                          RUN                              SKIPPED
is_in_control() softcheck     RUN                          (false → off)*                   (false → off until HF)
do_apply()  (evaluator)       RUN                          RUN                              RUN
```
\*`is_in_control()` is true only while validating a single new tx or producing a block; it is
false when applying a block someone else produced. The evaluator is the only layer guaranteed to
run on all three columns.

---

## Division of Labor — what each layer owns

### What `validate()` can and does check (universal, stateless)
From `validation.hpp` helpers and the per-op `validate()` bodies in `hive_operations.cpp`:
- **Account-name format** — `validate_account_name` → `check_account_name` (RFC-1035 labels;
  `validation.hpp:95-109`). Deterministic across all hardforks.
- **Asset symbol / sign / range** — `validate_asset_type`, `validate_asset_type_one_of`,
  `validate_asset_greater_than_zero`, `validate_asset_not_negative`, `validate_asset_is_not_vesting`
  (`validation.hpp:18-61`).
- **String size / UTF-8 / JSON validity** — `validate_string_max_size`, `validate_is_utf8`,
  `validate_json_with_fallback` (`validation.hpp:63-77`, `hive_operations.cpp:22-33`).
- **Percent ranges** — `validate_number_in_100_percent_range` (`validation.hpp:87-93`).
- **Permlink length + UTF-8** — `validate_permlink` (`validation.hpp:111-115`) — note: **not**
  charset; charset is evaluator-only (see gap table).
- **Authority structure** - `authority::validate()` (valid account names, `authority.cpp:47-55`) and, where
  present, `validate_auth_size` (membership ≤ `HIVE_MAX_AUTHORITY_MEMBERSHIP`,
  `hive_operations.cpp:36-43`).
- **Cross-field invariants with no state** — e.g. escrow `ratification_deadline <
  escrow_expiration` and "agent must be third party" (`hive_operations.cpp:681,675`); recurrent
  transfer `from != to` (`hive_operations.cpp:816`); since 1.28.8 its `validate()` rejects only
  `executions == 0` (`hive_operations.cpp:820-824`); the `executions` minimum is the evaluator's
  (gap catalog).

### What only the evaluator can check (state and/or hardfork)
- **Existence** — `get_account`, `get_comment`, `get_escrow`, `get_witness`, etc. throw if absent.
- **Balances / mana** — `adjust_balance`, manabar math, reward balances.
- **Counts held in state** — pending escrow transfers, withdraw routes, witness votes, open
  recurrent transfers, savings withdraw requests.
- **Hardfork gating** — every `has_hardfork()` branch.
- **Time-vs-now** — `o.expiration > head_block_time()`, escrow deadlines.
- **Authority-referenced account existence** — `verify_authority_accounts_exist`
  (`hive_evaluator_account.cpp:51-87`).

---

## Gap Catalog — per-operation divergences

Each row is a place where `validate()` and `do_apply()` diverge in a way that matters. "validate
looser" means a value passes `validate()` but is rejected (or reinterpreted) by the evaluator.

| Operation | `validate()` (stateless) | Evaluator divergence / addition | Direction |
|-----------|--------------------------|----------------------------------|-----------|
| `withdraw_vesting` | name + VESTS type only; **no sign check** (`hive_operations.cpp:259-263`) | negative VESTS: pre-HF20 silent `return`, post-HF20 hardfork-assert fails (`hive_evaluator_transfer.cpp:345-351`) | validate looser |
| `feed_publish` | base/quote in **either** order (`hive_operations.cpp:592-599`) | post-HF20 requires base=HBD, quote=HIVE (`hive_evaluator.cpp:599-605`) | validate looser |
| `witness_update` | `props.validate<false>()` — non-canonical fee symbol allowed (`hive_operations.cpp:276-285`) | post-HF14 asserts symbol `is_canon()`; "8 instances of non-canon fee symbol in mainnet, so the check can't be in validate()" (`hive_evaluator.cpp:66-75`) | validate looser |
| `transfer` | non-vesting + amount>0 (any non-vesting symbol) (`hive_operations.cpp:241-249`) | non-HIVE/HBD symbol rejected by `adjust_balance`; treasury conversion HF24 / treasury restriction HF21 (`hive_evaluator_transfer.cpp:268-300`) | validate looser |
| `custom_json` | id length + JSON validity; **no JSON byte cap** (`hive_operations.cpp:421-434`) | `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` cap only post-HF26 (`hive_evaluator.cpp:341-345`) | validate looser |
| `custom` (`custom_operation`) | auth count only; **no data cap** (`hive_operations.cpp:412-419`) | data cap post-HF26 (`hive_evaluator.cpp:330-334`). Asymmetry: `custom_binary` *does* cap data in validate (`hive_operations.cpp:453-454`) | validate looser |
| `recurrent_transfer` | `validate_asset_not_negative` - **amount 0 allowed**; since 1.28.8 only `executions >= 1` (`hive_operations.cpp:807-826`) | HF25 gate; amount 0 = delete semantics; create with 0 rejected; balance + open-transfer limit + max-end-date (`hive_evaluator_transfer.cpp:952-1028`); since 1.28.8 also the `executions` minimum (in `validate()` at 1.28.7). HF29 switch `HIVE_HARDFORK_1_29_ALLOW_MODIFY_LAST_RECURRENT_TRANSFER` (defined in 1.28.8, inactive on mainnet): a recurrent transfer may be modified or deleted with `executions == 1`; before HF29 the evaluator requires at least 2 on every path, and creation always does (`hive_evaluator_transfer.cpp:976-978`, `:991-996`, `:1011-1016`; Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet); Part 12, section Hardfork-conditional behavior (verified evolution)) | reinterpreted; validate looser for `executions` since 1.28.8 |
| `collateralized_convert` | symbol + amount>0 (`hive_operations.cpp:656-662`) | HF25 gate, feed availability, `hbd_print_rate>0`, global HBD limit (`hive_evaluator_transfer.cpp:486-533`) | evaluator stricter |
| `convert` | HBD + amount>0 (`hive_operations.cpp:647-654`) | feed availability, conversion-delay by HF (`hive_evaluator_transfer.cpp:468-484`) | evaluator stricter |
| comment beneficiaries | count `< HIVE_BENEFICIARY_LIMIT` = 128, hard (`hive_operations.cpp:156`) | count `<= HIVE_MAX_COMMENT_BENEFICIARIES` = 8, **soft** via `is_in_control` (`hive_evaluator_social.cpp:123`) | two different limits |
| comment depth | not checkable (needs parent state) | hard `HIVE_MAX_COMMENT_DEPTH` 0xffff, soft 0xff via `is_in_control`, pre-HF17 limit 6 (`hive_evaluator_social.cpp:186-190`) | evaluator-only |
| comment permlink charset | `validate_permlink` checks length+UTF-8 only (`validation.hpp:111-115`) | `validate_permlink_0_1` enforces `[a-z0-9-]` charset on **new** posts post-HF1 (`hive_evaluator_social.cpp:37-51,240-244`) | evaluator stricter |
| `limit_order_create` / `2` | HIVE:HBD **or** SMT NAI space paired with HIVE accepted (`hive_operations.cpp:601-640`) | HF29 switch `HIVE_HARDFORK_1_29_FIX_LIMIT_ORDER_ASSETS` (defined in 1.28.8, inactive on mainnet): `limit_order_create` and `limit_order_create2` accept only the HIVE:HBD market (`hive_evaluator_transfer.cpp:540-546`, `:578-584`). A 1.28.8 node already rejects other markets in new transactions submitted to it and in blocks it produces (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)). When that check does not run, `adjust_balance` rejects only an order that sells an SMT symbol (`database.cpp:3179-3198`; Part 03, section limit_order_create_operation (ID 5)); at 1.28.7 an `FC_TODO` "Limit to HIVE/HBD after next hardfork (HF29)" stood where the check is | validate looser |
| `account_update` | "unfortunately can't have validate_auth_size here" (`hive_operations.cpp:99`) | auth-size enforced post-HF20 only (`hive_evaluator_account.cpp:283-291`) | evaluator-only (HF-gated) |
| `account_update2` | `validate_auth_size` **is** called (`hive_operations.cpp:110-114`) | evaluator does **not** re-check size — relies on validate → not enforced on replay paths | validate-only |
| `request_account_recovery` | `new_owner_authority.validate()` (account names, not size) (`hive_operations.cpp:720-725`) | size checked by the evaluator, on every request path when in control or under HF29 (Key Discovery 5; `hive_evaluator_account.cpp:500-506`) | evaluator-only |
| `claim_account` | fee symbol/range, zero extensions (`hive_operations.cpp:194-210`) | per-witness subsidy limit gated by `is_processing_block()` (`hive_evaluator_account.cpp:417`) | evaluator-only |
| `vote` | names, `abs(weight) <= 100%`, permlink (`hive_operations.cpp:233-239`) | existence, `can_vote`, mana/dust/cashout-window - all state (`hive_evaluator_social.cpp:607-854`) | evaluator-only |
| `account_witness_proxy` | names, `proxy != account` (`hive_operations.cpp:404-410`) | existence, `can_vote`, proxy-loop + recursion-depth (`hive_evaluator.cpp:210-261`) | evaluator-only |
| `delegate_vesting_shares` | names, delegator!=delegatee, VESTS, non-neg (`hive_operations.cpp:798-805`) | mana availability, `min_delegation`, `min_update` - all state/HF (`hive_evaluator_transfer.cpp:723-950`) | evaluator-only |
| `escrow_transfer` | deadline<expiration, fee one-of, amounts (`hive_operations.cpp:664-684`) | deadline/expiration `> head_block_time`, pending-transfer limit, balance (`hive_evaluator_transfer.cpp:75-124`) | evaluator-only |

### Disabled / placeholder operations
| Operation | `validate()` | Evaluator |
|-----------|-------------|-----------|
| `reset_account` / `set_reset_account` | always `FC_ASSERT(false)` "placeholder" (`hive_operations.cpp:774-782`) | `HIVE_CHAIN_UNREACHABLE_CODE_ASSERT(false)` "currently disabled" (`hive_evaluator_account.cpp:631-643`) |
| `custom_binary` | real checks (auth, id, data cap) (`hive_operations.cpp:436-455`) | `UNREACHABLE_CODE_ASSERT(false)` + HF14 gate — "disallowed" (`hive_evaluator.cpp:376-399`) |
| `witness_block_approve` | checks witness name (`hive_operations.cpp:828-831`) | `UNREACHABLE_CODE_ASSERT(false)` "may not be included in a block" — handled out-of-band in `process_fast_confirm_transaction` (`hive_evaluator.cpp:615-620`) |
| `pow` | work/input checks (`hive_operations.cpp:465-476`) | `HARDFORK_ASSERT(!HF13)` "pow is deprecated" (`hive_evaluator.cpp:498-502`) |
| `pow2` | `props.validate<true>()` and the work's own check: names for `pow2` work, the full proof check for equihash work (`hive_operations.cpp:489-495`, `:572-590`) | `HARDFORK_ASSERT(!HF17)` "mining is now disabled" (`hive_evaluator.cpp:508`) |

For `reset_account`/`set_reset_account`, `custom_binary` and `witness_block_approve` the evaluator
asserts unconditionally (`hive_evaluator_account.cpp:633`, `:641`; `hive_evaluator.cpp:378`, `:619`),
so it rejects them on every path, including replay and checkpoint sync where `validate()` is skipped;
`validate()` of `reset_account`/`set_reset_account` also always fails wherever it runs. For `pow` and
`pow2` the evaluator's hardfork assert is the binding rule because historical blocks contain valid
instances of these ops that must replay successfully before their respective disabling hardforks.

---

## Soft-fork checks (`is_in_control` / `is_processing_block`)

These are the middle tier: rules applied according to the node's context rather than by a hardfork
(none of the checks below has a hardfork term for its soft part):

| Check | Guard | Hard limit (always) | Soft limit (`is_in_control`) | Where |
|-------|-------|---------------------|------------------------------|-------|
| Comment max depth | `is_in_control && depth_limit > SOFT` | `HIVE_MAX_COMMENT_DEPTH` 0xffff (HF17+) | `HIVE_SOFT_MAX_COMMENT_DEPTH` 0xff | `hive_evaluator_social.cpp:186-190` |
| Comment beneficiaries | `!is_in_control \|\| size <= MAX` | serialization fits one byte (validate, 128) | `HIVE_MAX_COMMENT_BENEFICIARIES` 8 | `hive_evaluator_social.cpp:123` |
| `claim_account` subsidy | `is_processing_block()` | global subsidy pool always checked | per-witness subsidy only in-block | `hive_evaluator_account.cpp:417` |

The HF29 switches (HF29 is defined in 1.28.8, inactive on mainnet) are described in Part 01,
section HF29 (Defined in 1.28.8, Inactive on Mainnet); this part gives each one where it discusses
that check (Key Discovery 5, the gap catalog).

Note the distinction: comment checks use `is_in_control()` (**false** on replay), whereas
`claim_account` uses `is_processing_block()` (**true** on replay): the per-witness subsidy check
runs for every transaction in a block, replay included, but not for transactions outside a block.
The code comment gives the reason: the check is made only when the transaction can be attributed to
a concrete witness, that is, when it is part of a block, existing or in production
(`hive_evaluator_account.cpp:411-417`).

---

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Evaluator dispatch (unconditional) | `libraries/chain/database.cpp` | 2739-2763 | `database_impl::apply_operation` -> `get_evaluator(op).apply(op)`; no skip flag |
| `validate()` gate | `libraries/chain/database.cpp` | 2588 | `if (!(skip & skip_validate))`: "issue #505 ... skip_flag is disabled" |
| `validate_transaction` | `libraries/chain/database.cpp` | 2538-2659 | expiration and TaPoS checks, the gated `validate()` call, authority verification |
| `_apply_transaction` caller | `libraries/chain/database.cpp` | 2678, 2687 | `skip = get_node_skip_flags()`, then `validate_transaction(full_transaction, skip)` |
| `skip_validate` flag def | `libraries/chain/include/hive/chain/database.hpp` | 215 | "used prior to checkpoint, skips validate() call" |
| `is_in_control` / `is_processing_block` | `libraries/chain/include/hive/chain/database.hpp` | 164,176 | softfork lever semantics |
| Replay skip flags | `libraries/plugins/chain/chain_plugin.cpp` | 1252-1267 | `skip_validate` set unless `--validate-during-replay` |
| Checkpoint skip flags | `libraries/plugins/chain/chain_plugin.cpp` | 1070-1092 | `skip_validate` for blocks <= last checkpoint |
| Pending-tx re-push skips | `libraries/chain/include/hive/chain/db_with.hpp` | 175-192 | `skip_validate` for already-validated pending txs |
| Queen-mode production skips | `libraries/plugins/queen/queen_plugin.cpp` | 118-120 | `skip_validate` for blocks the queen plugin produces (not available on mainnet builds) |
| `transaction::validate` | `libraries/protocol/transaction.cpp` | 40-56 | per-op `operation_validate` loop |
| `full_transaction::validate` | `libraries/chain/full_transaction.cpp` | 186-231 | cached validation; parallel precompute |
| `--validate-during-replay` arg | `libraries/plugins/chain/chain_plugin.cpp` | 1255-1267 | the option that actually gates whether `skip_validate` is set during replay (default off -> validation skipped); declared at `chain_plugin.cpp:1550` |
| worker-pool `validate_during_replay` | `libraries/chain/blockchain_worker_thread_pool.cpp` | 236-245 | same-named member that gates only the *parallel precompute* enqueue (the per-transaction check at `:321-334` is redundant, per its comment); the apply-path gate above is what governs enforcement |
| Validation helpers | `libraries/protocol/include/hive/protocol/validation.hpp` | 18-115 | asset/string/name/permlink/percent checks |
| All `validate()` bodies | `libraries/protocol/hive_operations.cpp` | 45-831 | 46 of the 50 regular-op `validate()` methods (the four proposal operations' are in `dhf_operations.cpp`) |
| Social evaluators | `libraries/chain/hive_evaluator_social.cpp` | 56-866 | comment / comment_options / delete_comment / vote |
| Transfer evaluators | `libraries/chain/hive_evaluator_transfer.cpp` | 75-1028 | transfer / vesting / escrow / savings / convert / limit orders / claim reward balance / delegate / recurrent |
| Account evaluators | `libraries/chain/hive_evaluator_account.cpp` | 156-643 | account create/update / claim account / create claimed account / recovery / decline-voting / reset |
| Witness/custom evaluators | `libraries/chain/hive_evaluator.cpp` | 62-620 | witness / proxy / custom / pow / feed / block-approve |
| `verify_authority_accounts_exist` | `libraries/chain/hive_evaluator_account.cpp` | 51-128 | state check for authority-referenced accounts |
| Recovery auth-size check | `libraries/chain/hive_evaluator_account.cpp` | 500-506 | size check on every request path when in control or under HF29 (Key Discovery 5) |

---

## Cross-references to existing parts

- **Part 03 (operation-validation)** — *deepens.* Part 03 catalogs each `validate()` method and
  correctly states validation is stateless with "no hardfork-conditional logic." This zoom adds the
  missing runtime dimension Part 03 does not cover: **`validate()` is skipped during default replay
  and checkpoint sync**, so the stateless checks Part 03 documents are non-consensus on those paths.
  Part 03's note that `asset_symbol_type::validate()` is not reached for SMT NAIs in
  `limit_order_create/2` (the evaluator decides; see the gap catalog row for `limit_order_create` / `2`)
  is the same class of gap catalogued here.
- **Part 04 (chain-evaluators)** — *complements.* Part 04 documents evaluator dispatch and a
  per-evaluator reference; it confirms the base `evaluator` class has no `validate()`
  (`evaluator.hpp:10-19`) and that protocol validation "lives on the operation itself." This zoom
  pairs each evaluator with its `validate()` counterpart and isolates the divergences, rather than
  describing either layer in isolation.
- **Part 01 (protocol-foundation)** — *complements.* Constant values used here
  (`HIVE_MAX_COMMENT_BENEFICIARIES`=8, `HIVE_BENEFICIARY_LIMIT`=128, `HIVE_SOFT_MAX_COMMENT_DEPTH`
  =0xff, `HIVE_MAX_COMMENT_DEPTH`=0xffff) are in `protocol/config.hpp:270-272` and
  `protocol/config.hpp:426`.
- **Part 09 (hardfork-history)** - *complements.* Many evaluator-only checks here are HF-gated; the
  "historical exception" comments (8 non-canon witness fees, `hellosteem` oversized authority,
  reversed feed) are the empirical reasons checks were placed in the evaluator rather than
  `validate()`. Its section HF29 (Defined in 1.28.8, Inactive on Mainnet) lists the HF29 switches,
  three of which change checks catalogued here (Key Discovery 5, gap catalog).

---

## Discrepancies and Potential Issues

1. **Recovery-request authority size is an evaluator rule.** `validate()` never checks membership
   size for this op; the evaluator does (Key Discovery 5).

2. **`account_update2` auth-size is validate-only.** Unlike `account_update` (size checked in the
   evaluator post-HF20, `hive_evaluator_account.cpp:283-291`), `account_update2` checks
   `validate_auth_size` only in `validate()` (`hive_operations.cpp:110-114`); its evaluator does
   not (`hive_evaluator_account.cpp:352-392`). Because `validate()` is skipped on replay/checkpoint
   paths, the size limit for `account_update2` is not a consensus check there — it relies on the
   fact that every such op in a historical block passed `validate()` at production time. Functional
   today, but an inconsistency a future contributor could trip over.

3. **`feed_publish` / `withdraw_vesting` / `transfer` accept inputs the evaluator rejects.** Listed
   in the gap table. Harmless for consensus (the evaluator binds), but means a successful
   `validate()` is not a guarantee of acceptance, and tooling that only runs `validate()` will
   mis-predict acceptance.

4. **Two permlink validators with different strictness.** `validate_permlink` (length+UTF-8) vs
   the evaluator's `validate_permlink_0_1` (charset `[a-z0-9-]`, new posts, post-HF1). A permlink
   with out-of-charset bytes passes `validate()` but fails the evaluator on a new post — and is not
   re-checked on edits (`hive_evaluator_social.cpp:278-311` edit branch never calls it).

5. **Same-block edit-then-reply inconsistency (code-acknowledged).** `FC_TODO` "Fix bug when you
   can edit post and then post new reply in the same block" (`hive_evaluator_social.cpp:214`),
   noted as requiring HF29; none of the five HF29 switches defined in 1.28.8 is for it (Part 01,
   section HF29 (Defined in 1.28.8, Inactive on Mainnet)). Not a validate/evaluate gap per se but a
   known evaluator-level inconsistency in the social path covered by an entry file.

None of the above are crash/halt vulnerabilities; they are correctness/consistency notes. They do
not contradict the consolidated security posture in the project audit memory.

---

## Open Questions

1. **Are checkpoints configured in shipped node defaults?** The skip-on-checkpoint path
   (`chain_plugin.cpp:1070`) only matters if `checkpoints` is non-empty. The source loads them from
   config (`chain_plugin.cpp:1683`) but the default set, if any, was not traced here. A future zoom
   on the chain plugin / node configuration could establish whether mainnet ships hardcoded
   checkpoints (and thus how large the "validate-skipped" historical range is in practice). This
   document deliberately makes no claim about live node state.

2. **Custom-operation interpreter validation.** `custom_json` dispatches to a registered
   `custom_operation_interpreter` (`hive_evaluator.cpp:347-372`; the same dispatch in the
   `custom_binary` evaluator, `hive_evaluator.cpp:382-398`, is never reached because of its
   unconditional assert), which has its own apply/validate semantics (notably the
   `truncation_controller` verify toggle and the exception handling: an `fc::exception` from the
   interpreter propagates only when the node is in control, any other exception is logged and
   swallowed in every mode, `hive_evaluator.cpp:361-372`, and the generic interpreter's undo session
   leaves no partial state, `generic_custom_operation_interpreter.hpp:184-225`; Part 04, section
   custom_json_evaluator and its Discrepancy 3). The interpreter layer (e.g. RC custom ops) is a
   separate validate/evaluate surface not covered by the three entry files - a candidate for its
   own zoom.

3. **`witness_set_properties` deserialization-as-validation.** Its `validate()`
   (`hive_operations.cpp:287-396`) validates by *unpacking* each property blob, while the evaluator
   re-unpacks and applies (`hive_evaluator.cpp:113-208`). The two unpack the same `flat_map` twice
   with subtly different key handling (e.g. `sbd_`/`hbd_` aliasing gated on HF24 in the evaluator at
   `hive_evaluator.cpp:150`, `:172` but unconditional in validate at
   `hive_operations.cpp:327-329`, `:351-353`). Whether any property key ordering/aliasing edge case
   diverges between the two unpack passes deserves a dedicated check.

```results
PART: 11
AREA: validate-evaluate-gaps
STATUS: COMPLETE
OUTPUT_FILES:
- research/hive-core/findings/11-validate-evaluate-gaps.md
KEY_FINDINGS:
- validate() (stateless, protocol layer) is SKIPPED on default replay (chain_plugin.cpp:1266) and checkpoint sync (chain_plugin.cpp:1082), while the evaluator do_apply() always runs (database.cpp:2757, no skip flag) — making the evaluator the sole consensus authority for historical blocks; validate() is a non-consensus first-line filter.
- validate() is also hardfork-agnostic (no has_hardfork access), so every state-dependent OR version-dependent rule is structurally forced into the evaluator; a third "softfork" tier exists via is_in_control() (false on replay) vs is_processing_block() (true on replay).
- Catalogued ~20 concrete validate<->evaluate divergences (feed_publish price ordering, withdraw_vesting missing sign check, witness_update non-canon symbol, custom/custom_json missing byte caps, recurrent_transfer amount==0 semantics and, since 1.28.8, its executions minimum, permlink charset, etc.) plus request_account_recovery's authority-size check, an evaluator rule tied to the HF29 switch (defined in 1.28.8, inactive on mainnet; Key Discovery 5, hive_evaluator_account.cpp:500-506).
CROSS_REFS:
- Part 03 (operation-validation): deepens — adds the replay/checkpoint skip dimension Part 03 omits, and generalizes its SMT-NAI gap observation.
- Part 04 (chain-evaluators): complements — pairs each evaluator with its validate() counterpart to isolate divergences.
- Part 01 (constants) and Part 09 (hardfork-history): complements — constant values and the historical exceptions that explain evaluator placement.
BLOCKERS:
- None
```
