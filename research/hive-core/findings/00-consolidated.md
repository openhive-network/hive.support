# Consolidated Research Findings: Hive Core Blockchain (hived)

## Executive Summary

The Hive blockchain is a Delegated Proof of Stake system producing blocks every 3 seconds with 21 witnesses, operating three native assets (HIVE, HBD, VESTS) across 50 broadcastable operations and ~43 virtual operations. Its architecture cleanly separates stateless protocol-level validation from hardfork-conditional chain-layer evaluators, with state stored across 37 defined object types in shared memory via chainbase. The economic model combines decreasing inflation (9.78% narrowing to 0.95% over ~20.5 years), stake-weighted content rewards, demand-responsive Resource Credits (replacing transaction fees), and a Decentralized Hive Fund — all evolved through 28 hardforks from the Steem genesis to the current Hive-native chain. The codebase carries significant legacy burden (Steem-era serialization names, dead operations, phantom object types) alongside several known bugs slated for future hardfork fixes, and the RC rate-limiting system remains explicitly non-consensus with a longstanding TODO to change this.

---

## Notable Findings

*Classified after source-code verification and deep analysis (2026-04-04). Original research labeled all 8 as "critical" — reclassified below by actual severity and nature.*

### Known Architectural Debt

#### 1. Resource Credits Are Non-Consensus (Part 08) — Known, No Timeline

**Category**: Known architectural debt, acknowledged by developers in source comments.

**What it is**: RC enforcement is mempool/block-production only. During block processing and replay, insufficient RC is logged (`ilog`) but accepted. `rc_utility.cpp:547-581` — explicit branching on `is_processing_block()`. The `FC_TODO` at line 545 reads: `"Add || db.has_hardfork( X ) to make RC part of consensus since X"` — no hardfork assigned.

**Why it exists**: RC state is time-dependent (continuous mana regeneration) making deterministic cross-node consensus hard. Code comment at `rc_utility.cpp:320`: "Since RC tracking is non-consensus, we must rely on consensus to forbid transferring/delegated VESTS that haven't regenerated voting power."

**Practical risk**: Mitigated by DPoS — a rogue witness filling blocks with RC-violating transactions would be voted out. Impact limited to a single block slot (~3 seconds). Still the largest architectural gap in the consensus layer.

**Status**: No assigned hardfork, no active development indicated. `account_object.hpp:218` field `last_max_rc` annotated "can be removed once RC becomes part of consensus."

### Confirmed Bugs (Known to Developers)

#### 2. request_account_recovery Skips Authority Size Validation (Part 04) — Tracked for HF29

**Category**: Confirmed bug, already known to developers, tracked for fix.

**What it is**: When modifying an existing recovery request (not creating new), `validate_auth_size()` is not called. `hive_evaluator_account.cpp:518-521` — ABW comment: "now there is a bug - editing existing request can introduce authority wider than max...HF29 is needed to fix this, after that the check should be moved to validate." Line 528 calls `validate_auth_size()` for new requests; lines 540-550 (modification path) do not.

**Practical risk**: Low. Exploitation requires the recovery account holder to cooperate, recovery requests are rare, and the oversized authority would only affect recovery scenarios. The fix is straightforward (add `validate_auth_size()` to the modification branch).

**Status**: Explicitly marked `FC_TODO` for HF29.

#### 3. HF1 Vesting Split Rounding Bug (Part 09) — Fixed in HF28

**Category**: Historical bug, already fixed.

**What it is**: HF1's 1M vesting multiplier recalculated `vesting_withdraw_rate` via integer division instead of multiplying, introducing truncation. Affected accounts (e.g., 'gil') could never complete power-down — remainder required 368+ years. `database_comment.cpp:1463-1476` (buggy recalculation), `database_vesting.cpp:128-129` (HF28 fix using modulo for final installment).

**Status**: Fixed in HF28 (block 100,000,000). No action needed.

### Architecture Documentation (Not Bugs)

#### 4. HF23 Forced Activation Without Witness Majority (Part 09) — Historical Fact

**Category**: Historical governance event, not a code defect.

**What it is**: The Steem-to-Hive fork (HF23, March 2020) bypassed witness supermajority voting, using time-based activation. Cleared 357 accounts (Steemit/Tron-affiliated) prepared in `hardfork.d/0_22.hf:19-360`. Balances transferred to treasury via `database.cpp:1461-1642`.

**Why this is not a finding**: ALL hardforks activate automatically when the compiled code reaches the scheduled time. Nodes choose which code to run. HF23 was an extraordinary chain-split event — the community that became Hive deliberately chose these parameters. The "forced" nature is inherent to how all DPoS hardforks work: code is law, operators choose which code to run.

#### 5. Block Application Is Fully Atomic (Part 06) — Design Choice

**Category**: Intentional design, explicitly documented in source.

**What it is**: No per-transaction undo during block processing. If any transaction fails, the entire block is rejected. `database.cpp:2292-2302` — explicit comment: "We do not need to push the undo state for each transaction because they either all apply and are valid or the entire block fails to apply."

**Why this is correct**: Blocks are pre-validated by the producing witness. Pending transactions DO get per-transaction undo (`_pending_tx_session` at database.cpp:626). During block replay, atomicity is correct because blocks were valid when produced. A malicious witness can't exploit this — a block with an invalid transaction is simply rejected by the network.

#### 6. Known Bad Merkle Roots in Historical Data (Part 06) — Historical Errata

**Category**: Historical data artifact, not actionable.

**What it is**: 8 blocks from early Steem-era chain (blocks 3,705,111 through 5,435,426, all from 2016) have incorrect merkle roots whitelisted in `shared_db_merkle.hpp:5-20`. These are hardcoded exceptions — new entries cannot be added without a code change.

**Why this is not a finding**: Long irreversible, immutable historical data. Common in long-running blockchains. The whitelist is a pragmatic compatibility measure for replay.

### Economic Policy Observations (Not Bugs)

#### 7. HBD Print Rate Cliff at HF26 (Part 07) — Intentional Governance Decision

**Category**: Deliberate economic policy change, not a code defect.

**What it is**: `config.hpp:343-344` sets `hbd_start_percent = hbd_stop_percent = 2000 (20%)`, eliminating the gradual throttling band. `database.cpp:2881-2886` — when `start == stop`, the middle branch (gradual scaling) is unreachable, creating binary 100%->0% switching.

**History**: Pre-HF14: no throttling. HF14-HF19: gradual 2%->5% band. HF20-HF25: gradual 9%->10% band. HF26+: cliff at 20%. Each step was a governance decision. These constants are hardcoded, not witness-adjustable — they require a hardfork to change.

**Whether this is optimal**: Legitimate economic policy question, but the code does exactly what it was configured to do. The community/witnesses approved HF26 with these parameters.

#### 8. Fork Switch Recovery Handles Three Cases (Part 06) — Correct by Design

**Category**: Correctly handled edge case, originally mischaracterized as asymmetric bug.

**What it is**: `sync_block_writer.cpp:228-260` handles three cases when a fork switch fails partway through. The code explicitly documents all three in comments at lines 228-232:

1. **New fork still longer** (bad block was late) -> stay on partial new fork. Correct.
2. **New fork now shorter, common ancestor not irreversible** -> revert to old fork. Correct.
3. **New fork shorter, but blocks became irreversible** -> cannot revert. Correct.

**Why case 3 is not a bug**: If LIB advanced past the common ancestor during the fork switch (via `update_last_irreversible_block()` called in `_apply_block()` at `database.cpp:2321`), the undo data for those blocks has been discarded and the block log is written. Reverting is physically impossible. The exception propagates, which is the only correct behavior. For LIB to advance, 16/21 witnesses must have confirmed blocks on the new fork — an extremely unlikely scenario to then have a later block fail.

**Possible improvement**: Better logging when recovery is skipped (currently silent at the decision point). Not a correctness issue.

---

## Cross-Cutting Themes

### Theme 1: Layered Validation Architecture

The codebase maintains a clean separation between protocol-level validation (stateless, no hardfork logic) and chain-level evaluation (stateful, hardfork-conditional). Protocol `validate()` methods enforce structural correctness (field sizes, asset types, ranges). Chain evaluators enforce business rules, state transitions, and hardfork-dependent behavior. This separation is documented across Parts 03, 04, and 09.

### Theme 2: Legacy Compatibility Burden

Steem-era artifacts persist throughout the codebase:
- **Serialization**: HIVE serializes as "STEEM", HBD as "SBD" in legacy wire format (Part 01)
- **Public key prefix**: Still "STM" (Steem) for backward compatibility — note: `HIVE_ADDRESS_PREFIX` is a misleading constant name; on Hive, addresses are account names, not keys (Part 01)
- **Dead operations**: `reset_account`, `set_reset_account` (always assert), `pow`, `pow2`, `custom_binary` (disabled by hardfork), `account_create_with_delegation` (disabled HF20) — 7 total (Part 02, 04)
- **Phantom objects**: `block_stats_object` type ID 24 reserved but never defined (Part 05)
- **Legacy objects**: `liquidity_reward_balance_object` unused since HF12, `comment_cashout_ex_object` empty since HF19 (Part 05)
- **Broken API**: `get_account_references` permanently throws "Needs to be refactored for Hive" (Part 10)
- **condenser_api**: 57-method thick adapter layer preserving Steem-era API format (Part 10)

### Theme 3: Hardfork-Driven Evolution

28 hardforks have reshaped every aspect of the system. 225+ `has_hardfork()` checks across 19 source files create significant code complexity. The heaviest files: `hive_evaluator_social.cpp` (40 checks), `hive_evaluator_transfer.cpp` (37), `database.cpp` (35). Key economic parameters have changed multiple times:

| Parameter | Genesis | Current (HF28) |
|-----------|---------|-----------------|
| Power down | 104 weeks | 13 weeks (HF16) |
| Reward curves | Quadratic | Linear (HF25) |
| Curation split | 50% | 50% (HF21, was 25% HF8-20) |
| HBD cap | 2% (HF14) | 20% (HF26) |
| Inflation split | 100% content | 65% content, 15% vesting, 10% DHF, 10% witness (HF21) |
| Witness schedule | 19/1/1 | 20/0/1 (HF17, miners eliminated) |

### Theme 4: Complex Economic Interdependencies

The economic model involves tightly coupled mechanisms:
- Inflation creates new HIVE, split four ways
- Content rewards use stake-weighted voting with mana regeneration
- HBD stability depends on price feeds, print rate throttling, and conversion mechanisms
- DHF funding comes from both inflation (10%) and daily treasury HIVE-to-HBD conversion (0.05%/day)
- Vesting (power-up) affects voting weight, RC capacity, witness voting, and DHF proposal voting
- 30-day delayed voting on power-up (HF24) affects governance timing

### Theme 5: State Object Architecture

37 object types in chainbase shared memory with Boost.MultiIndex containers. Key architectural decisions:
- RC mana embedded directly in `account_object` (not separate) — tight coupling
- `comment_object` stores only RIPEMD-160 hash, not raw strings — `comment_cashout_object` holds permlink but is deleted after cashout
- Inconsistent use of `account_id_type` vs `account_name_type` across objects (with TODO comments noting planned migration)
- Singletons (6), doubletons (2), fixed-size multitons (2), dynamic multitons (27)

### Theme 6: API Layer Complexity

175 methods across 17 API plugins, with significant overlap between `condenser_api` (legacy), `database_api` (direct state), and `wallet_bridge_api` (convenience). Three different locking strategies (read/write/lockless). Two calling conventions (dotted and generic). Dual serialization support (legacy + HF26).

---

## Detailed Findings by Part

### Part 01: Protocol Foundation

**Core constants**: 3-second blocks, 21 witnesses, 64KB max transaction, 7-day cashout, 13-week power-down, 1-hour max transaction expiration, 1-day signature expiration.

**Asset system**: Three native assets (HIVE 3 decimals, HBD 3 decimals, VESTS 6 decimals) encoded via NAI with Damm checksum. `HIVE_MAX_SATOSHIS = 2^62-1` prevents overflow in uint128_t price calculations. Legacy Steem names persist in binary serialization.

**Authority model**: Threshold-weight system with max 40 members, 2-level recursion. Four levels: owner (highest), active (transfers), posting (social), witness (signing key). Multi-sig supported.

**Block/transaction structure**: Block IDs from RIPEMD-160 of header digest. TaPoS (Transaction as Proof of Stake) references recent blocks for chain-following. Merkle root from transaction IDs.

**Chain ID**: `beeab0de00000000000000000000000000000000000000000000000000000000` (SHA-256).

**Version compatibility hack**: Major versions 0 and 1 treated as equivalent for the HF24 transition (`version.hpp:50-61`).

**HF28**: Defined at block 100,000,000 (expected November 2025). Uses `next_hf_time()` function rather than compile-time constant.

**Discrepancies found**: `HIVE_BLOCKCHAIN_PRECISION` comment says "actually HBD precision" but value (1000) applies to both HIVE and HBD. Public key prefix still "STM" (Steem-era name; constant is misleadingly called `HIVE_ADDRESS_PREFIX`).

### Part 02: Operations Catalog

**50 regular operations** (IDs 0-49) organized into 14 categories: social (4), transfer/financial (9), market (3), conversion (2), account management (5), account recovery (3), escrow (4), witness (6), proof-of-work (2, deprecated), custom (3), governance/DHF (4), vesting delegation (1), voting rights (1), placeholders (2, disabled).

**Virtual operations** (IDs 50-92/93): Generated internally for rewards, conversions, transfers, market fills, governance events, system/hardfork events. Never broadcast. `validate()` always asserts false.

**Note on count**: The original Part 02 summary incorrectly stated "44 virtual operations (IDs 50-93)." Verified against `operations.hpp`: there are exactly **43 virtual operations** (last_regular+1 through last_regular+43, ending at `declined_voting_rights_operation`). Corrected in findings file.

**Key findings**:
- Operation IDs are strictly positional in `fc::static_variant` — reordering breaks consensus
- `account_update2` is the only operation with 3-tier authority paths (owner/active/posting)
- `recover_account` requires dual-authority satisfaction (new + recent owner)
- `witness_set_properties` uses signing key directly (bypasses owner/active/posting)
- Escrow default ID is 30 (not 0) — undocumented design choice
- `comment_reward_operation` has TODO: field `author_rewards` should be `HIVE_asset` type
- SMT market support partially coded in `limit_order_create` validate but never activated

### Part 03: Operation Validation

**38 operations** have substantive `validate()` methods. 2 always fail (reset_account, set_reset_account). All 43 virtual operations unconditionally reject.

**No hardfork logic in validate()** — clean architectural separation confirmed. All hardfork-dependent validation lives in chain-layer evaluators.

**Account name rules**: RFC 1035-inspired, 3-16 chars, dot-separated labels each >= 3 chars, lowercase+digits+hyphens, must start with letter, end with letter/digit.

**JSON validation**: Uses fast parser with UTF-8 validation, fallback to relaxed mode for blockchain replay compatibility — some technically malformed JSON is accepted.

**Key size limits**: memo 2047 chars, permlink 255 chars, title 255 chars, witness URL 2048 chars, custom_json ID 32 chars, custom_json/custom body 8192 bytes (HF26+), proposal subject 80 chars, beneficiaries max 127, proposal batch operations max 5.

**Notable gaps**: `account_update_operation` skips authority size validation (unlike `account_update2`). `witness_update_operation` fee has no asset symbol check at protocol level. Comment body has no max size in validate() — bounded only by 64KB transaction limit.

**Evaluator-level hardfork changes**: 12 operation availability gates and 16+ validation rule changes cataloged across HF13-HF28.

### Part 04: Chain Evaluators

**50 evaluators** registered across 5 source files. 4 permanently disabled, 3 hardfork-disabled (7 inactive total).

**Dispatch architecture**: `evaluator<T>` base (abstract) -> `evaluator_impl<T>` (CRTP) -> concrete evaluators via `HIVE_DEFINE_EVALUATOR` macro. Registry indexed by `operation::which()` tag.

**Block processing pipeline**: `_apply_block()` -> per-transaction `apply_transaction()` -> per-operation `apply_operation()` -> evaluator dispatch. Entire block is atomic (no per-tx undo).

**End-of-block processing**: 30+ steps in strict deterministic order covering: expired order/delegation cleanup, witness scheduling, price feeds, supply updates, null account clearing, treasury consolidation, inflation distribution, conversions, comment cashout, vesting withdrawals, savings, account recovery, escrow expiry, governance, DHF proposals, delayed voting, recurrent transfers, RC finalization, hardfork checks.

**Key HF28 changes**: Stake-based voting (`effective_vesting_shares * weight * 86400 / 100%`) makes vote weight deterministic regardless of current mana state.

**Key HF25 changes**: Three-phase curation penalty (0-24h full, 24-72h half, 72h+ one-eighth) replaced reverse auction. Vote edits receive proper curation starting HF26.

**HBD interest side effect**: `adjust_balance(HBD)` triggers interest calculation — any HBD modification may generate `interest_operation` virtual ops.

**Custom operation exception handling**: Differs by mode — propagates in production/validation, swallowed during replay. Evaluators must self-undo on exception.

**State modification map**: Complete dependency matrix documented covering 25+ object types and which evaluators create/modify/remove them.

### Part 05: State Objects

**39 type IDs** (0-38) in the `object_type` enum. **37 have actual definitions** (block_stats reserved but never defined; account_metadata is plugin-level).

**Singletons** (6): `dynamic_global_property_object`, `feed_history_object`, `hardfork_property_object`, `reward_fund_object`, `rc_resource_param_object`, `rc_pool_object`.

**Doubletons** (2): `witness_schedule_object` (current + future), `rc_stats_object` (pending + archive).

**Fixed multitons** (2): `block_summary_object` (65,536 for TaPoS ring buffer), `rc_usage_bucket_object` (24 hourly buckets).

**`account_object`** is the largest/most complex: 50+ fields covering balances (8 fields), vesting (8), manabars (3), RC (4), HBD interest (6), governance (4), social (6), delayed voting (2).

**`dynamic_global_property_object`** is the most important singleton: 45 fields tracking all global chain state (supply, rewards, HBD parameters, distribution rates, governance windows, recurrent transfer limits).

**`comment_object`** stores only RIPEMD-160 hash of `permlink@author_id`, not raw strings. Actual permlink lives in `comment_cashout_object` which is deleted after cashout — cashed-out comments lose their permlink from core state.

**Inconsistencies**: Mixed use of `account_id_type` vs `account_name_type` across objects (code TODOs note planned migration). Several `account_object` fields marked "REMOVE" (not used by consensus, only API).

### Part 06: Consensus Mechanisms

**Block production**: 200ms polling loop in witness plugin. Witnesses check slot via `get_scheduled_witness(current_aslot % 21)`. XORshift Fisher-Yates shuffle every 21 blocks (~63s). 750ms production lag tolerance.

**Witness schedule**: Post-HF17: 20 elected (top-voted) + 1 timeshare (virtual-time fair queuing). Miners eliminated. Schedule recalculated every 21 blocks. HF26 adds future schedule pre-computation.

**Irreversibility (LIB)**: 75% of scheduled witnesses (16/21) must approve. Approval via block generation (implicit) or fast-confirm transactions (explicit, HF26+). Fast confirms processed out-of-band, never included in blocks, can trigger LIB advancement between blocks.

**Fork resolution**: Longest-chain rule (highest block_num). Fork DB holds up to 1024 reversible blocks (~51 minutes). Fork switch pops old chain via undo stack, re-applies new chain from common ancestor.

**Participation tracking**: 128-bit circular buffer (`recent_slots_filled`) with ~6.4 minute rolling window. Witnesses stop producing if rate drops below threshold.

**Block log**: ZSTD compression with custom dictionaries. Split into 1M-block part files. 24-byte-per-block artifacts index for O(1) random access. ~3.5ms compression, ~65us decompression per block.

**Key finding**: LIB can trigger fork switches — irreversibility overrides longest-chain rule when 75% of witnesses approve blocks on a different fork.

### Part 07: Economic Model

**Inflation**: Starts 9.78%, decreases 0.01% every 250,000 blocks (~8.68 days), floor 0.95% at block ~220,750,000. HF28 excludes treasury HBD from inflation base. Post-HF21 split: 65% content, 15% vesting, 10% DHF, 10% witness.

**Reward curves evolution**: quadratic (genesis) -> linear + square_root (HF17) -> convergent_linear + convergent_square_root (HF21) -> linear + linear (HF25). Single reward fund ("post") since HF17. Minimum payout: 0.020 HBD.

**Curation**: 50% of content rewards since HF21. Vote weight proportional to stake. Early voting penalty (HF25): 0-24h full, 24-72h half, 72h+ one-eighth. Downvote pool: 25% of upvote mana (HF21).

**HBD interest**: Savings-only since HF25. 30-day compound interval. Rate set by witness median (stored as basis points APR). Dollar-seconds accumulator pattern (not truly compound — discrete steps).

**Two conversion paths**:
- HBD -> HIVE: 3.5-day delay, no fee, at market median price
- HIVE -> HBD (collateralized, HF25+): 200% collateral, 5% fee, immediate HBD at min price, settlement at market median

**HBD stability**: 30% hard cap (HF26) with price haircut. Print rate cliff at 20% (binary on/off since HF26). Feed history: 84 hourly medians (3.5 days), minimum 7 valid feeds required.

**DHF**: Funded by 10% of inflation + 0.05%/day treasury HIVE->HBD conversion. Budget: 1% of treasury per day. Proposals ranked by stake-weighted votes, paid hourly. Graduated creation fee: 10 HBD base + 1 HBD/day beyond 60 days (HF24+).

**Power down**: 13 weekly installments. Up to 10 routing destinations. 30-day delayed voting on power-up (HF24). VESTS/HIVE ratio increases over time.

### Part 08: Resource Credits

**5 resource types**: history_bytes (tx size), new_accounts (subsidized creation), market_bytes (market tx size), state_bytes (RAM hour-bytes), execution_time (nanoseconds).

**Pricing**: Demand-responsive via pool dynamics. Rational function curve: `cost = A * usage / (B + pool) + 1`. As pool depletes, cost rises. `resource_new_accounts` always weighted at 100% of sum, making account creation perpetually expensive.

**Mana**: Max RC = effective_vests - delegated_rc + rc_adjustment + received_rc. Regenerates linearly over 5 days (432,000 seconds). Same regeneration rate as voting mana.

**State bytes**: Three durability tiers — temporary (1x), lasting (21,900x = 2.5yr), persistent (43,800x = 5yr). Account creation is very expensive due to persistent tier.

**RC delegation** (HF26+): Custom operation via `custom_json` with id "rc". Requires posting authority. Delegating immediately deducts from delegator's mana. Removing does NOT return mana (prevents pumping attack). Maximum 100 delegatees per operation.

**Subsidized operations**: `recover_account_operation` with single key authority and <= 2 signatures is fully free (zero RC), ensuring stolen accounts can always be recovered.

**Flood surcharge**: When mempool > 20 blocks worth, RC costs multiplied. Elected witnesses' operations exempt.

### Part 09: Hardfork History

**28 hardforks**: HF1-23 Steem-era (major v0), HF24-28 Hive-era (major v1).

**Activation mechanism**: Time-only before HF5. Witness supermajority (17/21) after HF5. Exception: HF23 forced without vote.

**Most impactful hardforks**:
- HF1: Vesting share 1M multiplier (introduced 9-year rounding bug)
- HF9: Reset 170+ compromised accounts
- HF12: Liquidity rewards permanently removed
- HF16: Power down 104->13 weeks, new inflation model
- HF17: Mining eliminated, reward fund system created
- HF20: Resource Credits system (largest feature addition)
- HF21: DHF/proposals, convergent linear rewards, downvote pool
- HF23: Steem->Hive fork, account clearing
- HF24: First Hive-native, chain ID change, delayed voting
- HF25: Recurrent transfers, pure linear rewards, collateralized conversions
- HF26: Fast confirms, future witness schedule, HBD cap raised to 20%
- HF28: Stable votes, strict authorities, power-down fix, DHF HBD excluded from inflation

**HF17/HF18 anomaly**: Activated simultaneously (same timestamp, 31 blocks apart). HF18 is effectively empty — purely a version marker.

**HF22->HF23 preparation**: The exclusion list for the Steem->Hive fork was embedded one hardfork in advance.

### Part 10: API Layer

**17 API plugins** exposing ~175 methods via JSON-RPC 2.0. **4 transport types**: HTTP, HTTPS, WebSocket, Unix socket.

**Major APIs**:
- `condenser_api`: 57 methods (legacy Steem-compatible, thick adapter)
- `database_api`: 51 methods (direct state access, find/list pattern)
- `wallet_bridge_api`: 35 methods (convenience wrapper, simplified returns)
- `rc_api`: 7 methods (Resource Credits)
- `market_history_api`: 7 methods (HIVE/HBD market)
- `account_history_api`: 4 methods (with bitmask operation filtering)

**7 non-API plugins**: chain (core), witness (block production), p2p (networking), market_history, reputation, transaction_status, state_snapshot.

**Key issues**: `get_account_references` permanently broken. Inconsistent pagination limits across APIs. Optional plugin dependencies silently fail. `wallet_bridge_api` bypasses `database_api` for some methods, accessing chain DB directly.

**Documentation**: 1.3MB OpenAPI/Swagger spec in `libraries/plugins/apis/documentation/openapi.json`.

---

## Known Bugs and Issues

| # | Issue | Category | Severity | Part | Location | Status |
|---|-------|----------|----------|------|----------|--------|
| 1 | RC is non-consensus | Arch debt | Known | 08 | `rc_utility.cpp:545-581` | TODO, no HF assigned |
| 2 | `request_account_recovery` skips `validate_auth_size` on modifications | Bug | Low | 04 | `hive_evaluator_account.cpp:518-550` | FC_TODO for HF29 |
| 3 | HF1 vesting split rounding bug in power-down | Bug | Fixed | 09 | `database_vesting.cpp:128-129` | Fixed in HF28 |
| 4 | `hardfork_hive_restore_operation` late airdrop VESTS accounting | Bug | Low | 02 | `hive_virtual_operations.hpp` | Unknown |
| 5 | `get_account_references` API permanently broken | Tech debt | Low | 10 | `condenser_api.cpp:397` | No fix planned |
| 6 | Bad merkle roots in 8 historical blocks | Errata | N/A | 06 | `shared_db_merkle.hpp:5-20` | Permanent (historical) |
| 7 | HBD print rate cliff (binary on/off at 20%) | Policy | N/A | 07 | `config.hpp:343-344` | Intentional (HF26) |
| 8 | Recovery rate limit inconsistency vs `account_update` | Bug | Low | 04 | `hive_evaluator_account.cpp` | Unresolved |
| 9 | `comment_reward_operation.author_rewards` typed as `share_type` not `HIVE_asset` | Tech debt | Low | 02 | `hive_virtual_operations.hpp` | TODO in code |

*Note: Original items #7 (fork switch) and #8 (HBD cliff) from the research were reclassified after source-code verification — #7 is correct-by-design edge case handling, #8 is intentional governance decision. See Notable Findings section above for details.*

---

## Prioritized Recommendations

*Recommendations reflect post-verification classification. Items previously listed as "high priority" that turned out to be design choices or historical facts have been removed or reclassified.*

### Existing Tracked Items (no action needed from us)

1. **RC non-consensus** — Developers are aware (`FC_TODO` in code). The challenge is making RC state deterministic across nodes. No hardfork assigned. This is the core team's decision to prioritize.

2. **`request_account_recovery` auth validation** — Already marked `FC_TODO` for HF29. Fix is straightforward (one-line addition of `validate_auth_size()` to the modification branch).

3. **HF1 vesting rounding bug** — Already fixed in HF28.

### Code Quality Improvements

4. **Clean up dead operations**: 7 disabled/dead operations (`reset_account`, `set_reset_account`, `pow`, `pow2`, `custom_binary`, `account_create_with_delegation`, `witness_block_approve`) add code complexity. Consider explicit "disabled" evaluator type.

5. **Resolve ID-vs-name inconsistency in state objects**: Mixed use of `account_id_type` and `account_name_type` across objects. TODO comments in code acknowledge this.

6. **Remove legacy phantom objects**: `block_stats_object` (type ID 24, never defined), `liquidity_reward_balance_object` (unused since HF12), and `comment_cashout_ex_object` (empty since HF19).

### Low Priority

7. **Fix or remove `get_account_references` API**: Permanently broken method throwing on every call (`condenser_api.cpp:397`). Either implement or remove.

8. **Standardize JSON validation**: Relaxed fallback parser for replay compatibility could surprise developers.

9. **Document escrow default ID=30 convention**: Undocumented, could confuse client library implementers.

10. **Add logging to fork switch case 3**: `sync_block_writer.cpp:236` — when recovery is skipped because LIB advanced past the common ancestor, there's no log message. Operators would benefit from explicit "cannot revert: blocks became irreversible" logging.

---

## Open Questions — Triaged (2026-04-04)

*Each question investigated against source code. Status: RESOLVED (answered from code), KNOWN (developers aware, no public resolution), or ASK TEAM (requires insider knowledge).*

### Architecture

**1. When will RC become consensus?** — KNOWN, no timeline
No hardfork assigned. `FC_TODO` at `rc_utility.cpp:545` has no version number. Challenge is making RC state deterministic across nodes — time-dependent mana regeneration, transaction ordering effects. See Notable Finding #1.

**2. What is `queen_mode` in the witness plugin?** — RESOLVED
Testnet-only feature. When enabled (via colony/queen plugin), the witness plugin skips the identity check (`witnesses.find(scheduled_witness)`) and produces blocks for ANY scheduled witness as long as it has the signing key. Protected by `#ifndef USE_ALTERNATE_CHAIN_ID` — cannot activate on mainnet. Used for single-node testing/benchmarking. Source: `witness_plugin.cpp:335`, `queen_plugin.cpp:273-280`.

**3. What is `hf_21_stall_block`?** — RESOLVED
Constant block number `35922615` in `hardfork.d/0_21.hf`. Marks a specific point for the **iceberg** feature — a blockchain converter plugin that generates valid blockchain slices from a range of mainnet blocks for mirrornet/testing. Iceberg creates condensed histories with all necessary account/comment context. Comment says "remove when iceberg is implemented." Iceberg implementation exists in the converter tool but the stall_block reference persists.

**4. Plans to migrate `account_name_type` -> `account_id_type`?** — RESOLVED: no active plan
Investigated GitLab issues, MRs, branches, and commit history — no active work, no filed issues, no branches. The TODOs are informal ABW annotations in 5 state object files (`global_property_object.hpp:63`, `escrow_object.hpp:40-42`, `limit_order_object.hpp:46`, `savings_withdraw_object.hpp:27-28`) noting it "can be replaced" with caveats like "would make looking for escrow object harder." These are aspirational comments, not tracked work.

**5. Plans to refactor `account_object`?** — ASK TEAM
50+ fields, some marked "REMOVE" (not used by consensus, only API). No refactoring plan visible in source.

### Consensus

**6. How is HF28 activation controlled?** — RESOLVED
Dual-trigger: block number AND time. `hardfork_block.hpp:30` sets `HIVE_HARDFORK_1_28_BLOCK = 100000000`. `hardfork.d/1_28.hf` sets time via `next_hf_time()` -> mainnet `1763557200` (2025-11-19 13:00 UTC). Overridable via `HIVE_HF28_TIME` env var. `process_hardforks()` in `database_hardfork.cpp:114-144` requires BOTH conditions (time reached AND block number reached naturally through consensus). Neither condition alone triggers activation.

**7. Fork DB capacity and undo stack interaction?** — RESOLVED
Fork DB has `max_size = 1024` blocks (`fork_database.hpp:207`). Blocks older than `head - 1024` are rejected (`fork_database.cpp:77-79`). Oldest block in fork DB = last irreversible block (`fork_database.cpp:440-441`). When blocks fall off the fork DB, their undo data is committed — they become irreversible. This enforces a hard **1024-block reorg limit** (~51 minutes at 3s blocks).

**8. Fast-confirm P2P propagation?** — RESOLVED
Fast confirms are regular P2P transactions (not a separate message type). Witness plugin calls `p2p_plugin.broadcast_transaction()` (`witness_plugin.cpp:290`). Peers receive via standard gossip, then `chain_plugin.push_transaction()` routes them to `process_fast_confirm_transaction()` — a separate code path from normal transactions. Fast confirms are **never included in blocks** — the evaluator asserts this (`hive_evaluator.cpp:623-628`). They update a per-witness tracking map (`_last_fast_approved_block_by_witness`), which feeds into `update_last_irreversible_block()`. When 67%+ of witnesses approve a block, it becomes irreversible.

**9. Split block log migration procedure?** — ASK TEAM
No migration documentation found in source. The split block log (1M-block part files) is implemented in `block_log.cpp` but the procedure for migrating a running node from monolithic to split format is not documented in the codebase.

### Economics

**10. When does inflation reach 0.95% floor?** — RESOLVED
Block ~220,750,000. At 3s/block from genesis (2016-03-24), this is ~21 years ≈ **March 2037**. Calculation: (9.78% - 0.95%) / 0.01% = 883 decreases × 250,000 blocks = 220,750,000.

**11. How are RC execution time benchmarks maintained?** — RESOLVED
Hardcoded constants in `resource_sizes.cpp:167-240`. Each operation's time is a sum of measured components (validate + exec + pre_rc + post_rc). Values come from benchmark measurements documented in GitLab issue #205. They are NOT measured at runtime. When implementation changes, engineers must re-run benchmarks and manually update the constants. A `USE_FIXED_SIZE` macro controls fixed vs dynamic validation during development.

**12. Are RC resource dynamics parameters still tuned?** — RESOLVED: last rebalanced 2022, no changes since
Parameters were NOT set once at HF20 and forgotten. Full history: initial 2018 implementation with several tuning rounds (#2547, #2628, #2974, #3061). **Major rebalance in 2022 (MR !390 by ABW)**: state budget recalculated to reflect actual byte-hours (5yr persistent / 2.5yr lasting tiers), execution budget shortened to 1hr half-life based on benchmarks (issue #205), new pool popularity mechanism auto-balances cost across resource types, all non-account-token costs 3x multiplied. `resource_parameters.json` last substantively modified 2022-04-28. No changes since. Only `resource_new_accounts` is witness-adjustable; the other 4 pools require a hardfork. The popularity mechanism (MR !390) was designed to reduce need for manual rebalancing.

**13. DHF maintenance drift issue?** — RESOLVED
`dhf_processor.cpp:218-219`: "shifting from current time instead of proper maintenance time causes drift when maintenance block was missed, but the fix is problematic - see MR!168 for details." When a maintenance block is missed, using `head_time` instead of scheduled `next_maintenance_time` causes cumulative drift. MR!168 documents why a complete fix is problematic (consensus/hardfork implications). Low practical impact — maintenance blocks are rarely missed on a healthy network.

### API

**14. OpenAPI spec — auto-generated or manual?** — RESOLVED
**Manually maintained.** The 24,873-line `openapi.json` in `libraries/plugins/apis/documentation/` is version-controlled with 95+ commits. Not auto-generated from C++ code. Python tools exist to consume/flatten the spec but they don't generate it. Drift risk is real — spec must be manually updated when API methods change.

**15. Default plugin enablement?** — RESOLVED
From `programs/hived/main.cpp`: **Always loaded** (regardless of config): `chain_plugin`, `p2p_plugin`, `webserver_plugin`. **Default config** (included unless removed): `witness_plugin`, `account_by_key_plugin`, `account_by_key_api_plugin`, `state_snapshot_plugin`. All API plugins (database_api, condenser_api, etc.) require explicit configuration.

**16. Per-client rate limiting?** — RESOLVED
**None.** No per-IP, per-client, or per-request rate limiting exists in the webserver or json_rpc plugins. Only global connection limits (`p2p-max-connections`) and per-query result pagination (`limit` parameters). Node operators must implement rate limiting externally (reverse proxy, firewall).

**17. What is the `colony` plugin?** — RESOLVED
Stress-testing/load-generation plugin. Automatically generates synthetic transactions (articles, replies, votes, transfers, custom_json) using multiple worker threads to flood the network with configurable loads. Used for performance testing. Referenced in shutdown order because it must stop generating transactions before other plugins shut down. Not an API plugin — no endpoints exposed.

### Operations

**18. Max operations per transaction?** — RESOLVED
**No explicit limit.** `transaction.cpp:40-56` only checks `operations.size() > 0`. The effective limit is the 64KB transaction size (`HIVE_MAX_TRANSACTION_SIZE = 1024*64` in `config.hpp:364`). As many operations as fit within serialized 64KB.

**19. Chain-interpreted custom_json IDs?** — RESOLVED
Only **`"rc"`** is interpreted by the chain layer (`hive_custom_operations.hpp:23`, `HIVE_RC_CUSTOM_OPERATION_ID`). Contains `delegate_rc_operation`. All other custom_json IDs ("follow", "community", etc.) are application-layer conventions passed to generic custom operation interpreters — not validated or interpreted by core consensus.

**20. Authority recursion depth enforcement?** — RESOLVED
`HIVE_MAX_SIG_CHECK_DEPTH = 2` (`config.hpp:357`). Enforced in **signature verification**, not validate(). `sign_state.hpp:216-223` in `check_authority_impl()` stops recursion when `depth == limits.recursion`. Nested account authorities beyond depth 2 are silently skipped.

**21. Comment depth 255 — where enforced?** — RESOLVED
`HIVE_SOFT_MAX_COMMENT_DEPTH = 0xff (255)` (`config.hpp:275`). Enforced in the **comment evaluator** (`hive_evaluator_social.cpp:185-189`), not validate(). Checked only when `_db.is_in_control()` (new mempool transactions). Post-HF17 hard limit is 64K (`HIVE_MAX_COMMENT_DEPTH = 0xffff`), but witness plugin enforces the soft 255 limit for new transactions.

### Historical

**22. hardfork_hive_restore_operation VESTS bug resolution?** — KNOWN, unresolved
The bug is **acknowledged but unfixed**. `hardfork_hive_restore.proto:9-10` contains the question: "the late airdrop did not apply properly since HIVE that the accounts should receive did not account for HIVE from converted VESTS. [how was it resolved?]" The question mark remains unanswered in the codebase. No corrective mechanism was implemented.

**23. h23_balances — future recovery possible?** — RESOLVED
**Yes, technically.** `hardfork_property_object.hpp` maintains `h23_balances` as a persistent `flat_map` in chainbase. The `gather_balance()` function in `database_hardfork.cpp` stores cleared HIVE/HBD balances. They are NOT deleted post-hardfork. A future hardfork could read these values and issue restoration operations.

**24. Planned but unshipped hardfork features?** — ASK TEAM
No evidence in source code of planned-but-unshipped features beyond what's already in HF28. HF29 is referenced only in the `FC_TODO` for the recovery auth size fix. Whether there's a feature roadmap is a governance/team question.

**25. block_stats_object — defined anywhere?** — RESOLVED
**No.** Only a reserved type ID (`hive_object_types.hpp:73`) and a forward declaration (line 114). No struct definition anywhere in the codebase. The unrelated `block_stats` class in `block_flow_control.hpp` is a runtime statistics tracker, not a persistent object. The type ID appears permanently unused/abandoned.

---

## Conflicts and Inconsistencies Between Parts

### 1. Virtual Operation Count

**Part 02 summary** originally stated "44 virtual operations (IDs 50-93)" but the actual `operations.hpp` variant lists `last_regular+1` through `last_regular+43`, ending at `declined_voting_rights_operation` (last_regular+43). **Resolution**: **43 virtual operations** is correct. Part 02 findings file corrected.

### 2. Object Type Counts

**Part 05 summary** says "35 object types" but detail sections enumerate "39 type IDs (0-38), 37 with actual definitions." The 35 number likely excludes plugin-level and reserved types, while 37 includes everything with a definition, and 39 is the raw enum range. **Resolution**: The precise count depends on counting methodology. 37 defined types is the most accurate.

### 3. End-of-Block Processing Descriptions

Parts 04, 06, and 07 all describe the end-of-block sequence. Part 06 provides the most granular code-level walkthrough. Part 04 has a 30-step summary. Part 07 focuses on economic steps. All three are consistent in ordering but differ in granularity. **Resolution**: Part 06's description at `database.cpp:2183-2369` is authoritative.

### 4. HBD Interest Description

Part 04 says HBD interest is "hidden as side effect of adjust_balance(HBD)" while Part 07 describes it as "dollar-seconds accumulator pattern, evaluated lazily when balance accessed." These are complementary descriptions of the same mechanism (not conflicting). Part 04 notes it applies "pre-HF25" for liquid balances; Part 07 confirms "savings-only since HF25." **Resolution**: Consistent.

---

## Code Reference Table

### Protocol Layer (`libraries/protocol/`)

| Component | File | Key Lines |
|-----------|------|-----------|
| All timing/economic/size constants | `include/hive/protocol/config.hpp` | 56-458 |
| NAI bit layout and encoding | `include/hive/protocol/asset_symbol.hpp` | 9-53 |
| Asset struct and price | `include/hive/protocol/asset.hpp` | 21-186 |
| Asset validation | `asset.cpp` | 128-286 |
| Authority struct | `include/hive/protocol/authority.hpp` | 7-55 |
| Account name validation | `authority.cpp` | 58-122 |
| Operation variant (93 types: 50 regular + 43 virtual) | `include/hive/protocol/operations.hpp` | 15-125 |
| Base operation class | `include/hive/protocol/base.hpp` | 13-29 |
| Regular operation structs | `include/hive/protocol/hive_operations.hpp` | — |
| DHF operation structs | `include/hive/protocol/dhf_operations.hpp` | — |
| Virtual operation structs | `include/hive/protocol/hive_virtual_operations.hpp` | — |
| RC custom operations | `include/hive/protocol/hive_custom_operations.hpp` | 8-17 |
| Operation validate() methods | `hive_operations.cpp` | 1-866 |
| DHF operation validation | `dhf_operations.cpp` | 1-62 |
| Block header struct | `include/hive/protocol/block_header.hpp` | 15-26 |
| Transaction struct | `include/hive/protocol/transaction.hpp` | 12-53 |
| Transaction validation | `transaction.cpp` | 40-55 |
| Version encoding | `include/hive/protocol/version.hpp` | 15-77 |
| Hardfork definitions | `hardfork.d/*.hf` | — |
| Hardfork block numbers | `include/hive/protocol/hardfork_block.hpp` | 3-30 |
| Chain IDs | `config.hpp` | 137-143 |
| Validation helpers | `include/hive/protocol/validation.hpp` | 64-115 |
| HBD interest calc | `include/hive/protocol/hbd_interest.hpp` | 8-23 |
| Collateral estimation | `include/hive/protocol/hive_collateral.hpp` | 8-26 |
| Testnet overrides | `include/hive/protocol/testnet_blockchain_configuration.hpp` | 27-285 |

### Chain Layer (`libraries/chain/`)

| Component | File | Key Lines |
|-----------|------|-----------|
| Block application (`_apply_block`) | `database.cpp` | 2183-2369 |
| Block header validation | `database.cpp` | 2757-2779 |
| Transaction application | `database.cpp` | 2644-2702 |
| Operation dispatch | `database.cpp` | 2722-2746 |
| Balance/supply helpers | `database.cpp` | 3206+ |
| LIB calculation | `database.cpp` | 2956-3064 |
| Fast confirm processing | `database.cpp` | 2899-2954 |
| Irreversibility migration | `database.cpp` | 3066-3097 |
| Participation tracking | `database.cpp` | 2789-2841 |
| Median feed update | `database.cpp` | 2399+ |
| HBD print rate / virtual supply | `database.cpp` | 2843-2868 |
| Inflation distribution | `database.cpp` | 1704 |
| HBD creation helper | `database.cpp` | 949+ |
| next_hf_time() | `database.cpp` | 61-71 |
| Account clearing/restoration | `database.cpp` | 1422-1540 |
| Evaluator base class | `include/hive/chain/evaluator.hpp` | — |
| Evaluator registry | `include/hive/chain/evaluator_registry.hpp` | — |
| Evaluator registration | `database_init.cpp` | — |
| Transfer evaluators | `hive_evaluator_transfer.cpp` | 75-957 |
| Account evaluators | `hive_evaluator_account.cpp` | 130-657 |
| Social evaluators | `hive_evaluator_social.cpp` | 55-864 |
| Witness/custom/pow evaluators | `hive_evaluator.cpp` | 62-628 |
| DHF evaluators | `dhf_evaluator.cpp` | 32-252 |
| Comment cashout/curation | `database_comment.cpp` | 129-379 |
| Market/order matching | `database_market.cpp` | — |
| Vesting withdrawals | `database_vesting.cpp` | 111+ |
| Conversion processing | `database_conversion.cpp` | 34+ |
| DHF/recurrent transfers | `database_dhf.cpp` | — |
| Hardfork application | `database_hardfork.cpp` | — |
| Witness scheduling | `witness_schedule.cpp` | 152-396 |
| Witness missed blocks | `database_witness.cpp` | 284-306 |
| Fork database | `fork_database.cpp` | 20-330 |
| Fork switching | `sync_block_writer.cpp` | 162-367 |
| Block log read/write | `block_log.cpp` | 338-515 |
| Block log artifacts | `block_log_artifacts.cpp` | 46-166 |

### State Objects (`libraries/chain/include/hive/chain/`)

| Object | File |
|--------|------|
| Object type enum (39 IDs) | `hive_object_types.hpp:47-89` |
| dynamic_global_property_object | `detail/state/global_property_object.hpp` |
| account_object (50+ fields) | `detail/state/account_object.hpp` |
| account_authority_object | `detail/state/account_object.hpp:339` |
| comment_object / comment_cashout | `detail/state/comment_object.hpp` |
| comment_vote_object | `detail/state/comment_object.hpp:372` |
| witness_object | `detail/state/witness_objects.hpp:69` |
| witness_schedule_object | `detail/state/witness_objects.hpp:183` |
| feed_history_object | `detail/state/feed_history_object.hpp` |
| limit_order_object | `detail/state/limit_order_object.hpp` |
| convert_request_object | `detail/state/convert_request_object.hpp` |
| collateralized_convert_request | `detail/state/collateralized_convert_request_object.hpp` |
| escrow_object | `detail/state/escrow_object.hpp` |
| proposal_object / proposal_vote | `detail/state/dhf_objects.hpp` |
| recurrent_transfer_object | `detail/state/recurrent_transfer_object.hpp` |
| reward_fund_object | `detail/state/reward_fund_object.hpp` |
| hardfork_property_object | `detail/state/hardfork_property_object.hpp` |
| block_summary_object | `detail/state/block_summary_object.hpp` |
| transaction_object | `detail/state/transaction_object.hpp` |

### RC System (`libraries/chain/rc/`)

| Component | File | Key Lines |
|-----------|------|-----------|
| RC core logic | `rc_utility.cpp` | — |
| Non-consensus enforcement | `rc_utility.cpp` | 547-581 |
| Mana deduction (finalize_tx) | `rc_utility.cpp` | 799-831 |
| RC delegation mechanics | `rc_utility.cpp` | 26-110 |
| Delegation overflow | `rc_utility.cpp` | 401-443 |
| Flood surcharge | `rc_utility.cpp` | 505-537 |
| Resource counting | `resource_count.cpp` | 136-631 |
| State byte sizes | `resource_sizes.cpp` | 45-165 |
| Execution time benchmarks | `resource_sizes.cpp` | 167-242 |
| Price curve computation | `rc_curve.cpp` | 32-98 |
| Pool dynamics (decay) | `rd.cpp` | 23-118 |
| Resource parameters | `libraries/jsonball/data/resource_parameters.json` | — |
| Manabar struct | `include/hive/chain/rc/manabar.hpp` | 42-141 |
| RC state objects | `include/hive/chain/rc/rc_objects.hpp` | — |
| RC API | `libraries/plugins/apis/rc_api/` | — |

### Plugins (`libraries/plugins/`)

| Component | File |
|--------|------|
| AppBase plugin framework | `libraries/appbase/include/appbase/plugin.hpp` |
| JSON-RPC routing/registration | `json_rpc/json_rpc_plugin.cpp` |
| API declaration macros | `json_rpc/include/.../utility.hpp` |
| WebServer transports | `webserver/webserver_plugin.cpp` |
| condenser_api (57 methods) | `apis/condenser_api/` |
| database_api (51 methods) | `apis/database_api/` |
| wallet_bridge_api (35 methods) | `apis/wallet_bridge_api/` |
| rc_api (7 methods) | `apis/rc_api/` |
| account_history_api (4 methods) | `apis/account_history_api/` |
| market_history_api (7 methods) | `apis/market_history_api/` |
| block_api (3 methods) | `apis/block_api/` |
| witness_api (3 methods) | `apis/witness_api/` |
| Witness plugin (block production) | `witness/witness_plugin.cpp` |
| Block producer | `witness/block_producer.cpp` |
| OpenAPI documentation | `apis/documentation/openapi.json` |

### Reward Calculations (`libraries/chain/util/`)

| Component | File | Key Lines |
|-----------|------|-----------|
| Reward curve evaluation | `reward.cpp` | 34+ |
| DHF payment processing | `dhf_processor.cpp` | 145-325 |
| DHF budget calculation | `dhf_processor.cpp` | 145 |
| DHF HIVE->HBD conversion | `dhf_processor.cpp` | 325 |
| Compound interest template | `compound.hpp` | — |

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total research parts | 10 |
| Parts completed | 10 |
| Regular operations | 50 (IDs 0-49) |
| Virtual operations | 43 (IDs 50-92) |
| Active evaluators | 43 (50 registered, 7 disabled) |
| State object type IDs | 39 (37 defined) |
| Consensus constants cataloged | 150+ |
| Hardforks documented | 28 |
| API plugins | 17 |
| API methods | ~175 |
| `has_hardfork()` checks | 225+ across 19 files |
| Tracked bugs/issues | 9 (1 arch debt, 3 bugs [1 fixed], 2 tech debt, 2 errata/policy, 1 low) |
| Open questions | 25 -> 21 resolved, 2 known/unresolved, 2 ask-team |
| Notable findings | 8 (reclassified from "critical" after verification) |
| Recommendations | 10 |
| Recommendations | 11 |
