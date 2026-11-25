# Consolidated Research Findings: Hive Core Blockchain (hived)

## Executive Summary

The Hive blockchain is a Delegated Proof of Stake system producing blocks every 3 seconds with 21 witnesses, operating three native assets (HIVE, HBD, VESTS) across 50 broadcastable operations and 43 virtual operations. Its architecture cleanly separates stateless protocol-level validation from hardfork-conditional chain-layer evaluators, with state stored across 37 object types defined in the core chain library, in shared memory via chainbase. The economic model combines decreasing inflation (9.78% narrowing to 0.95% over ~20.5 years), stake-weighted content rewards, demand-responsive Resource Credits (replacing transaction fees), and a Decentralized Hive Fund, all evolved through 28 hardforks from the Steem genesis to the current Hive-native chain (HF29 is defined in 1.28.8 code, inactive on mainnet; Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)). The codebase carries significant legacy burden (Steem-era serialization names, dead operations, phantom object types) alongside several known bugs slated for future hardfork fixes, and the RC rate-limiting system is non-consensus until HF29 (Part 08, section Non-Consensus Status). This summary describes hived release 1.28.8 (`274384a8a`).

---

## Notable Findings

*Classified after source-code verification and deep analysis (2026-04-04). Original research labeled all 8 as "critical" — reclassified below by actual severity and nature.*

### Known Architectural Debt

#### 1. Resource Credits Are Non-Consensus (Part 08) — Known, No Timeline

**Category**: Known architectural debt, acknowledged by developers in source comments.

**What it is**: RC is non-consensus until HF29, which is defined in 1.28.8 and inactive on mainnet (Part 08, section Non-Consensus Status). Before HF29 a payer's RC shortfall rejects the transaction only when the node is in control (a new transaction from API or P2P, or a block it produces) or re-applies its pending transactions; during block application and replay the transaction is accepted and, from HF26, the shortfall is logged (`ilog`) (`rc_utility.cpp:567-602`). HF29 switch `HIVE_HARDFORK_1_29_RC_IS_CONSENSUS` (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)): the RC payer and balance checks assert in every mode, which makes RC part of consensus (`rc_utility.cpp:507-508`, `:567`).

**Why it exists**: Not for lack of determinism: RC state is block-time driven, not wall-clock driven, and evolves identically on every node running the same binary (Part 15, Key Discovery 6, which also discusses what stands in the way of enforcing it in consensus). Code comment at `rc_utility.cpp:333-334`: "Since RC tracking is non-consensus, we must rely on consensus to forbid transferring / delegating VESTS that haven't regenerated voting power."

**Status**: HF29 is defined in 1.28.8 code, inactive on mainnet (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)). `account_object.hpp:243` field `last_max_rc` annotated "for bug catching with RC code, can be removed once RC becomes part of consensus".

### Confirmed Bugs (Known to Developers)

#### 2. request_account_recovery Authority Size Check (Part 04) - HF29 Switch

**Category**: Evaluator check known to developers, with an HF29 switch.

**What it is**: HF29 switch `HIVE_HARDFORK_1_29_FIX_ENFORCEMENT_OF_AUTHORITY_SIZE_ON_RECOVERY_REQUEST` (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)): `request_account_recovery` checks the size of the new owner authority on every request path (`hive_evaluator_account.cpp:500-506`). A 1.28.8 node already applies this check to new transactions submitted to it (API or P2P) and to blocks it produces (`is_in_control()`, `database.hpp:176`). See Part 16, Key Discovery 3, and Part 11, Key Discovery 5.

**Status**: HF29 is defined in 1.28.8 code, inactive on mainnet.

#### 3. HF1 Vesting Split Rounding Bug (Part 09) — Fixed in HF28

**Category**: Historical bug, already fixed.

**What it is**: HF1's 1M vesting multiplier recalculated `vesting_withdraw_rate` by dividing the multiplied `to_withdraw` by 104 instead of multiplying the old rate (`database_comment.cpp:621-623`); for 'gil' the code comment gives 9615.384615 VESTS instead of 9615.000000. Before HF28 the last installment was `to_withdraw % vesting_withdraw_rate` (`database_vesting.cpp:128-129`): for 'gil' 0.000040 VESTS a week against a 0.769270 VESTS remainder (comment at `database_vesting.cpp:130-135`), so its power-down could not complete in practice (368+ years at that rate; the comment says other accounts may have been affected too). `HIVE_HARDFORK_1_28_FIX_POWER_DOWN` turns that path off.

**Status**: Fixed in HF28 (activated 2025-11-19 at block 101,319,928, which `HIVE_HARDFORK_1_28_BLOCK` records since 1.28.8; it was 100,000,000 at 1.28.7; Part 01, Key Discovery 7). No action needed.

### Architecture Documentation (Not Bugs)

#### 4. HF23 Forced Activation Without Witness Majority (Part 09) — Historical Fact

**Category**: Historical governance event, not a code defect.

**What it is**: The Steem-to-Hive fork (HF23, March 2020) bypassed witness supermajority voting, using time-based activation. Cleared at most 328 accounts (Steemit/Tron-affiliated), listed in `hardfork.d/0_22.hf:19-360` (332 entries, 4 of them duplicates). Balances transferred to treasury via `database.cpp:1478-1667`.

**Why this is not a finding**: Hardfork activation uses block time, not the wall clock: HF1-HF5 activate when the head block time reaches their scheduled time, HF6+ also need 17 of the 21 scheduled witnesses to vote for the same version and time (`database_hardfork.cpp:119-149`; Part 09, section How Hardforks Activate (live consensus)). HF23 is the one hardfork the code activates without that vote (`witness_schedule.cpp:289-301`). Nodes choose which code to run. HF23 was an extraordinary chain-split event: the community that became Hive deliberately chose these parameters.

#### 5. Block Application Is Fully Atomic (Part 06) — Design Choice

**Category**: Intentional design, explicitly documented in source.

**What it is**: No per-transaction undo during block processing. If any transaction fails, the entire block is rejected. `database.cpp:2309-2319` — explicit comment: "We do not need to push the undo state for each transaction because they either all apply and are valid or the entire block fails to apply."

**Why this is correct**: Blocks are pre-validated by the producing witness. Pending transactions DO get per-transaction undo (`_pending_tx_session` at `database.cpp:632`). During block replay, atomicity is correct because blocks were valid when produced. The code comment gives the reason: an undo state per transaction is needed only when validating broadcast transactions or building a block (`database.cpp:2311-2316`).

#### 6. Known Bad Merkle Roots in Historical Data (Part 06) — Historical Errata

**Category**: Historical data artifact, not actionable.

**What it is**: 8 blocks from early Steem-era chain (blocks 3,705,111 through 5,435,426, all from 2016) have incorrect merkle roots whitelisted in `shared_db_merkle.hpp:5-20`. These are hardcoded exceptions — new entries cannot be added without a code change.

**Why this is not a finding**: Long irreversible, immutable historical data. Common in long-running blockchains. The whitelist is a pragmatic compatibility measure for replay.

### Economic Policy Observations (Not Bugs)

#### 7. HBD Print Rate Cliff at HF26 (Part 07) — Intentional Governance Decision

**Category**: Deliberate economic policy change, not a code defect.

**What it is**: `protocol/config.hpp:342-343` defines the HF26 start and stop percents both as 2000 (20%), which HF26 writes to `hbd_start_percent` and `hbd_stop_percent` (`database_hardfork.cpp:495-496`), eliminating the gradual throttling band. `database.cpp:2918-2923`: when `start == stop`, the middle branch (gradual scaling) is unreachable, creating binary 100%->0% switching.

**History**: Pre-HF14: no throttling. HF14-HF19: gradual 2%->5% band. HF20-HF25: gradual 9%->10% band. HF26+: cliff at 20%. Each step was a governance decision. These constants are hardcoded, not witness-adjustable — they require a hardfork to change.

**Whether this is optimal**: Legitimate economic policy question, but the code does exactly what it was configured to do. The community/witnesses approved HF26 with these parameters.

#### 8. Fork Switch Recovery Handles Three Cases (Part 06) - Conditional Revert

**Category**: Fork-switch error handling, described in a source comment.

**What it is**: When a fork switch fails partway through, `sync_block_writer.cpp:228-260` reverts to the old branch only when an irreversibility test against the common ancestor passes and the chain is shorter than where it started (`sync_block_writer.cpp:236-237`); the comment at `sync_block_writer.cpp:228-232` spells out the three possibilities. The exception is rethrown in every case (`sync_block_writer.cpp:260`). See Part 06, section Fork Switch, step 5, and its Discrepancies item 3.

**Possible improvement**: No log line records the decision not to revert: the `if` at `sync_block_writer.cpp:236-237` has no `else` (the failure itself is logged at `sync_block_writer.cpp:219`).

---

## Cross-Cutting Themes

### Theme 1: Layered Validation Architecture

The codebase maintains a clean separation between protocol-level validation (stateless, no hardfork logic) and chain-level evaluation (stateful, hardfork-conditional). Protocol `validate()` methods enforce structural correctness (field sizes, asset types, ranges). Chain evaluators enforce business rules, state transitions, and hardfork-dependent behavior. This separation is documented across Parts 03, 04, and 09.

### Theme 2: Legacy Compatibility Burden

Steem-era artifacts persist throughout the codebase:
- **Serialization**: HIVE serializes as "STEEM", HBD as "SBD" in legacy wire format (Part 01)
- **Public key prefix**: Still "STM" (Steem) for backward compatibility — note: `HIVE_ADDRESS_PREFIX` is a misleading constant name; on Hive, addresses are account names, not keys (Part 01)
- **Dead operations**: `reset_account`, `set_reset_account` (always assert), `custom_binary` (its evaluator always rejects), `witness_block_approve` (its evaluator always rejects it, `hive_evaluator.cpp:615-620`; a single-operation transaction carrying it is processed as a fast confirm, `database.cpp:543-547`), plus `pow` (HF13), `pow2` (HF17) and `account_create_with_delegation` (HF20) disabled by hardfork: 7 total (Part 02, 04)
- **Phantom objects**: `block_stats_object` type ID 24 kept in the enum but never defined (Part 05)
- **Legacy objects**: `liquidity_reward_balance_object` unused since HF12, `comment_cashout_ex_object` empty since HF19 (Part 05)
- **Broken API**: `get_account_references` permanently throws "Needs to be refactored for Hive" (Part 10)
- **condenser_api**: 62-method thick adapter layer preserving Steem-era API format (Part 10)

### Theme 3: Hardfork-Driven Evolution

28 hardforks have reshaped every aspect of the system (HF29 is defined in 1.28.8 code, inactive on mainnet; Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)). At 1.28.8, 257 `has_hardfork()` checks across 17 files of `libraries/chain` (calls of `has_hardfork(`, its declaration and definition not counted) create significant code complexity. The heaviest files: `hive_evaluator_social.cpp` (43 checks), `hive_evaluator_transfer.cpp` (42), `database.cpp` (42). Key economic parameters have changed multiple times:

| Parameter | Genesis | Current (HF28) |
|-----------|---------|-----------------|
| Power down | 104 weeks | 13 weeks (HF16) |
| Reward curves | Quadratic | Linear (HF25) |
| Curation split | 50% | 50% (HF21, was 25% HF8-20) |
| HBD print throttle (start/stop) | none (2%/5% from HF14) | 20%/20% (HF26) |
| Inflation split | separate APR per reward category (pre-HF16) | 65% content, 15% vesting, 10% DHF, 10% witness (HF21) |
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
- Inconsistent use of `account_id_type` vs `account_name_type` across objects (since 1.28.8 several objects note why their names must stay, a few TODO comments remain; Part 05, Key Discovery 9)
- Singletons (6), doubletons (2), fixed-size multitons (2), dynamic multitons (27)

### Theme 6: API Layer Complexity

198 methods: 196 across 18 API plugins plus 2 in the built-in jsonrpc namespace, with significant overlap between `condenser_api` (legacy), `database_api` (direct state), and `wallet_bridge_api` (convenience). Three different locking strategies (read/write/lockless). Two calling conventions (dotted and generic). Dual serialization support (legacy + HF26).

---

## Detailed Findings by Part

### Part 01: Protocol Foundation

**Core constants**: 3-second blocks, 21 witnesses, 7-day cashout, 13-week power-down, 1-hour max transaction expiration, 1-day signature expiration. A transaction may be at most the witness-voted `maximum_block_size` minus 256 bytes on the push path (`database.cpp:566-572`); the 64KB `HIVE_MAX_TRANSACTION_SIZE` is not checked against transactions (Part 02, section Transaction-Level Constraints).

**Asset system**: Three native assets (HIVE 3 decimals, HBD 3 decimals, VESTS 6 decimals) encoded via NAI with Damm checksum. `HIVE_MAX_SATOSHIS = 2^62-1` prevents overflow in uint128_t price calculations. Legacy Steem names persist in binary serialization.

**Authority model**: Threshold-weight system with max 40 members, 2-level recursion. Four levels: owner (highest), active (transfers), posting (social), witness (signing key). Multi-sig supported.

**Block/transaction structure**: Block IDs are the first 20 bytes of a SHA-224 over the signed block header, with the block number written into the first 4 bytes (`full_block.cpp:305-316`; Part 01, Key Discovery 9). TaPoS (Transaction as Proof of Stake) references recent blocks for chain-following. Merkle root from the transactions' merkle digests, a SHA-256 of each signed transaction (`full_block.cpp:620-648`, digest at `full_transaction.cpp:65-76`; Part 01, section Merkle Root).

**Chain ID**: `beeab0de00000000000000000000000000000000000000000000000000000000` (an `fc::sha256` built from this literal hex via the constructor - not a hash of anything; `protocol/config.hpp:141`).

**Version compatibility hack**: The `version` comparison has a compatibility branch for comparisons between major versions 0 and 1, added for the HF24 transition: `version(0, 23, 0) == version(1, 23, 0)` returns true (`version.hpp:50-61`; Part 01, Key Discovery 5).

**HF28**: activated 2025-11-19 13:00 UTC at block 101,319,928 (time + witness vote; since 1.28.8 the `HIVE_HARDFORK_1_28_BLOCK` constant records that block, 100,000,000 at 1.28.7, and activation does not use it, see Part 01 Discovery 7). Uses `next_hf_time()` function rather than compile-time constant.

**Discrepancies found**: `HIVE_BLOCKCHAIN_PRECISION` comment says "actually HBD precision" but value (1000) applies to both HIVE and HBD. Public key prefix still "STM" (Steem-era name; constant is misleadingly called `HIVE_ADDRESS_PREFIX`).

### Part 02: Operations Catalog

**50 regular operations** (IDs 0-49) organized into 14 categories: social (4), transfer/financial (9), market (3), conversion (2), account management (6), account recovery (3), escrow (4), witness (6), proof-of-work (2, deprecated), custom (3), governance/DHF (4), vesting delegation (1), voting rights (1), placeholders (2, disabled).

**Virtual operations** (IDs 50-92): Generated internally for rewards, conversions, transfers, market fills, governance events, system/hardfork events. Never broadcast. `validate()` always asserts false.

**Note on count**: The original Part 02 summary incorrectly stated "44 virtual operations (IDs 50-93)." Verified against `operations.hpp`: there are exactly **43 virtual operations** (last_regular+1 through last_regular+43, ending at `declined_voting_rights_operation`). Corrected in findings file.

**Key findings**:
- Operation IDs are strictly positional in `fc::static_variant` — reordering breaks consensus
- `account_update2` is the only operation with 3-tier authority paths (owner/active/posting)
- `recover_account` requires dual-authority satisfaction (new + recent owner): both authorities come from the operation's `get_required_authorities` (`hive_operations.hpp:851-855`)
- `witness_set_properties` uses signing key directly (bypasses owner/active/posting)
- Escrow default ID is 30 (not 0) — undocumented design choice
- `comment_reward_operation` has TODO: field `author_rewards` should be `HIVE_asset` type
- SMT market support partially coded in `limit_order_create` validate but never activated

### Part 03: Operation Validation

**All 50 regular operations** define a `validate()` method. 2 always fail (reset_account, set_reset_account). All 43 virtual operations unconditionally reject.

**No hardfork logic in validate()** — clean architectural separation confirmed. All hardfork-dependent validation lives in chain-layer evaluators.

**Account name rules**: RFC 1035-inspired, 3-16 chars, dot-separated labels each >= 3 chars, lowercase+digits+hyphens, must start with letter, end with letter/digit.

**JSON validation**: Uses fast parser with UTF-8 validation, fallback to relaxed mode for blockchain replay compatibility — some technically malformed JSON is accepted.

**Key size limits**: memo 2047 chars, permlink 255 chars, title 255 chars, witness URL 2048 chars, custom_json ID 32 chars, custom_json/custom body 8192 bytes (HF26+), proposal subject 80 chars, beneficiaries max 127, proposal batch operations max 5.

**Notable gaps**: `account_update_operation` skips authority size validation (unlike `account_update2`). `witness_update_operation` fee has no asset symbol check at protocol level. Comment body has no max size in validate(): on the push path it is bounded by the transaction size limit (voted `maximum_block_size` minus 256 bytes; Part 03, Key Discovery 8), and inside blocks by the block-size check, which applies from HF12 (`database.cpp:2285-2286`).

**Evaluator-level hardfork changes**: 12 operation availability gates and 16+ validation rule changes cataloged across HF13-HF28.

### Part 04: Chain Evaluators

**50 evaluators** registered across 5 source files. 4 permanently disabled, 3 hardfork-disabled (7 inactive total).

**Dispatch architecture**: `evaluator<T>` base (abstract) -> `evaluator_impl<T>` (CRTP) -> concrete evaluators via `HIVE_DEFINE_EVALUATOR` macro. Registry indexed by `operation::which()` tag.

**Block processing pipeline**: `_apply_block()` -> per-transaction `apply_transaction()` -> per-operation `apply_operation()` -> evaluator dispatch. Entire block is atomic (no per-tx undo).

**End-of-block processing**: 30+ steps in strict deterministic order covering: expired order/delegation cleanup, witness scheduling, price feeds, supply updates, null account clearing, treasury consolidation, inflation distribution, conversions, comment cashout, vesting withdrawals, savings, account recovery, escrow expiry, governance, DHF proposals, delayed voting, recurrent transfers, RC finalization, hardfork checks.

**Key HF28 changes**: Stake-based voting (`effective_vesting_shares * weight * 86400 / 100%`) makes vote weight deterministic regardless of current mana state.

**Key HF25 changes**: Three-phase curation penalty (0-24h full, 24-72h half, 72h+ one-eighth) replaced reverse auction. Vote edits receive proper curation starting HF26.

**HBD interest side effect**: `adjust_savings_balance()` with an HBD delta, and before HF25 also `adjust_balance()` with an HBD delta, pays accrued interest as a side effect, so such a balance change may generate `interest_operation` virtual ops: interest is paid on liquid HBD only before HF25 and on savings HBD in every era (`database.cpp:3242`, `:3317`; Part 04, Key Discovery 12).

**Custom operation exception handling**: An `fc::exception` from the interpreter propagates only when the node is in control (producing a block or validating a new transaction); otherwise (replay, blocks from the network, re-applied pending transactions) it is swallowed. Any other exception is logged and swallowed in every mode (`hive_evaluator.cpp:361-372`). The generic interpreter's undo session leaves no partial state (Part 04, Discrepancy 3).

**State modification map**: Complete dependency matrix documented covering 25+ object types and which evaluators create/modify/remove them.

### Part 05: State Objects

**39 type IDs** (0-38) in the `object_type` enum. **37 are defined in the core chain library**; account_metadata (ID 2) is defined in the metadata plugin and block_stats (ID 24) is never defined (`hive_object_types.hpp:48-90`).

**Singletons** (6): `dynamic_global_property_object`, `feed_history_object`, `hardfork_property_object`, `reward_fund_object`, `rc_resource_param_object`, `rc_pool_object`.

**Doubletons** (2): `witness_schedule_object` (current + future), `rc_stats_object` (pending + archive).

**Fixed multitons** (2): `block_summary_object` (65,536 for TaPoS ring buffer), `rc_usage_bucket_object` (24 hourly buckets).

**`account_object`** is the largest/most complex: 50+ fields covering balances (8 fields), vesting (8), manabars (3), RC (4), HBD interest (6), governance (4), social (6), delayed voting (2).

**`dynamic_global_property_object`** is the most important singleton: 41 fields since 1.28.8 (43 at 1.28.7, which also had `total_reward_fund_hive` and `total_reward_shares2`; Part 05) tracking all global chain state (supply, rewards, HBD parameters, distribution rates, governance windows, recurrent transfer limits).

**`comment_object`** stores only RIPEMD-160 hash of `permlink@author_id`, not raw strings. Actual permlink lives in `comment_cashout_object` which is deleted after cashout — cashed-out comments lose their permlink from core state.

**Inconsistencies**: Mixed use of `account_id_type` vs `account_name_type` across objects (since 1.28.8 several objects note why their names must stay, a few TODO comments remain, and no migration plan is visible in the code; Part 05, Key Discovery 9 and Discrepancy 5). Several `account_object` fields marked "REMOVE" (not used by consensus, only API).

### Part 06: Consensus Mechanisms

**Block production**: 200ms polling loop in witness plugin. Witnesses check slot via `get_scheduled_witness(slot)`, which reads `current_shuffled_witnesses[(current_aslot + slot) % num_scheduled_witnesses]` (`database.cpp:913-919`). XORshift Fisher-Yates shuffle every 21 blocks (~63s). 750ms production lag tolerance.

**Witness schedule**: Post-HF17: 20 elected (top-voted) + 1 timeshare (virtual-time fair queuing). Miners eliminated. Schedule recalculated every 21 blocks. HF26 adds future schedule pre-computation.

**Irreversibility (LIB)**: 75% of scheduled witnesses (16/21) must approve. Approval via block generation (implicit) or fast-confirm transactions (explicit, HF26+). Fast confirms processed out-of-band, never included in blocks, can trigger LIB advancement between blocks.

**Fork resolution**: Longest-chain rule (highest block_num). The fork DB window `_max_size` is 1024 at start and is set to head - LIB + 1 after every applied block and every accepted fast confirm, so there is no fixed 1024 cap; `MAX_BLOCK_REORDERING` = 1024 is declared but used by no code (`fork_database.hpp:67`, `:207`, `sync_block_writer.cpp:59`; Part 06, sections Fork Database Structure and Undo History and Reorg Depth Limits). Fork switch pops old chain via undo stack, re-applies new chain from common ancestor.

**Participation tracking**: 128-bit circular buffer (`recent_slots_filled`) with ~6.4 minute rolling window. Witnesses stop producing if rate drops below threshold.

**Block log**: ZSTD compression with custom dictionaries. Split into 1M-block part files. 24-byte-per-block artifacts index for O(1) random access. A code comment gives ~3.5ms compression and ~65us decompression times at the default level 15, without saying per what (`block_log.cpp:118-121`).

**Key finding**: LIB can trigger fork switches: irreversibility overrides longest-chain rule when 75% of witnesses approve blocks on a different fork whose head is not below the current head (`database.cpp:3062-3088`; Part 06, Key Discovery 2).

### Part 07: Economic Model

**Inflation**: Starts 9.78%, decreases 0.01% every 250,000 blocks (~8.68 days), floor 0.95% at block ~220,750,000. HF28 excludes treasury HBD from inflation base. Post-HF21 split: 65% content, 15% vesting, 10% DHF, 10% witness.

**Reward curves evolution**: quadratic + bounded_curation (genesis) -> linear + square_root (HF19) -> convergent_linear + convergent_square_root (HF21) -> linear + linear (HF25) (`database_hardfork.cpp:306-307`, `:438-439`, `:480-481`). Single reward fund ("post"): since 1.28.8 it exists from genesis (`database_init.cpp:258-262`; at 1.28.7 HF17 created it), and from HF17 its `recent_claims` decay (seeded at HF17 outside testnet builds; Part 07, section Reward Pool). Minimum payout: 0.020 HBD.

**Curation**: 50% of content rewards since HF21. Vote weight proportional to stake. Early voting penalty (HF25): 0-24h full, 24-72h half, 72h+ one-eighth. Downvote pool: 25% of upvote mana (HF21).

**HBD interest**: Savings-only since HF25. 30-day compound interval. Rate set by witness median (stored as basis points APR). Dollar-seconds accumulator pattern (not truly compound — discrete steps).

**Two conversion paths**:
- HBD -> HIVE: 3.5-day delay, no fee, at the official median price (`current_median_history`, which the hard cap can raise; `database_conversion.cpp:67`)
- HIVE -> HBD (collateralized, HF25+): 200% collateral, 5% fee, immediate HBD at min price, settlement at market median

**HBD stability**: 30% hard cap (HF26) with price haircut. Print rate cliff at 20% (binary on/off since HF26). Feed history: 84 hourly medians (3.5 days), minimum 7 valid feeds required.

**DHF**: Funded by 10% of inflation + 0.05%/day treasury HIVE->HBD conversion. Budget: 1% of treasury per day. Proposals ranked by stake-weighted votes, paid hourly. Graduated creation fee: 10 HBD base + 1 HBD/day beyond 60 days (HF24+).

**Power down**: 13 weekly installments. Up to 10 routing destinations. 30-day delayed voting on power-up (HF24). The VESTS-per-HIVE ratio falls over time, so each VEST is worth more HIVE: the vesting share of inflation enters `total_vesting_fund_hive` without new VESTS (`database.cpp:1793`; Part 07, section Power Up (HIVE -> VESTS)).

### Part 08: Resource Credits

**5 resource types**: history_bytes (tx size), new_accounts (subsidized creation), market_bytes (market tx size), state_bytes (RAM hour-bytes), execution_time (nanoseconds).

**Pricing**: Demand-responsive via pool dynamics. Rational function curve: `cost = A * usage / (B + pool) + 1`. As pool depletes, cost rises. `resource_new_accounts` always weighted at 100% of sum, making account creation perpetually expensive.

**Mana**: Max RC = effective_vests - delegated_rc + rc_adjustment + received_rc. Regenerates linearly over 5 days (432,000 seconds). Same regeneration rate as voting mana.

**State bytes**: Three durability tiers — temporary (1x), lasting (21,900x = 2.5yr), persistent (43,800x = 5yr). Account creation is very expensive due to persistent tier.

**RC delegation** (HF26+): Custom operation via `custom_json` with id "rc". Requires posting authority. Delegating immediately deducts from delegator's mana. Removing does NOT return mana (prevents pumping attack). Maximum 100 delegatees per operation.

**Subsidized operations**: a transaction whose only operation is `recover_account_operation`, with a new owner authority of a single entry (one key or one account) and <= 2 signatures, is fully free (zero RC); multisig recoveries are not subsidized (`resource_count.cpp:536-537`, `:606`; Part 08, Key Discovery 6).

**Flood surcharge**: When the mempool holds more than `flood_level` blocks worth of transactions (default 20, a node option), RC costs of new and re-applied pending transactions are multiplied. A single-operation transaction with `feed_publish`, `witness_update` or `witness_set_properties` is exempt when its payer's witness object has `schedule == witness_object::elected`; that test runs only while the mempool is over the flood level (`rc_utility.cpp:529-562`, `:888-889`; Part 08, Key Discovery 8; Part 15, Key Discovery 8).

### Part 09: Hardfork History

**28 hardforks**: HF1-23 Steem-era (major v0), HF24-28 Hive-era (major v1). HF29 (version 1.29) is defined in 1.28.8 code, inactive on mainnet: it has no one-time migration and only builds with `USE_ALTERNATE_CHAIN_ID` (testnet, mirrornet) register it (`database_hardfork.cpp:112-116`, `:505-511`; Part 09, section HF29 (Defined in 1.28.8, Inactive on Mainnet)).

**Activation mechanism**: Driven by block time, not the wall clock. Time-only for HF1-HF5. From HF6 also a witness supermajority (17/21) for the same version and time (`database_hardfork.cpp:119-149`). Exception: HF23 forced without vote (`witness_schedule.cpp:289-301`).

**Most impactful hardforks**:
- HF1: Vesting share 1M multiplier (introduced 9-year rounding bug)
- HF9: Reset up to 151 compromised accounts (`hardfork.d/0_9.hf:19-169`; names without an account are skipped, `database_hardfork.cpp:220-222`)
- HF12: Liquidity rewards permanently removed
- HF16: Power down 104->13 weeks, new inflation model
- HF17: Mining eliminated, reward fund system (decaying `recent_claims`; the fund itself exists from genesis since 1.28.8, HF17 created it at 1.28.7)
- HF20: Resource Credits system (largest feature addition)
- HF21: DHF/proposals, convergent linear rewards, downvote pool
- HF23: Steem->Hive fork, account clearing
- HF24: First Hive-native, chain ID change, delayed voting
- HF25: Recurrent transfers, pure linear rewards, collateralized conversions
- HF26: Fast confirms, future witness schedule, HBD cap raised to 20%
- HF28: Stable votes, strict authorities, power-down fix, DHF HBD excluded from inflation

**HF17/HF18 anomaly**: Same scheduled time (`1490886000`), applied 31 blocks apart, because HF18 waited for the witnesses to vote for 0.18 (Part 09, the HF18 section of Hardfork Reference). HF18 is effectively empty - purely a version marker.

**HF22->HF23 preparation**: The exclusion list for the Steem->Hive fork was embedded one hardfork in advance.

### Part 10: API Layer

**18 API plugins** exposing 196 methods, plus 2 in the built-in jsonrpc namespace (198 in all), via JSON-RPC 2.0 (the test-only `test_api` adds 2 more). **4 transport types**: HTTP, HTTPS, WebSocket, Unix socket.

**Major APIs**:
- `condenser_api`: 62 methods (legacy Steem-compatible, thick adapter)
- `database_api`: 51 methods (direct state access, find/list pattern)
- `wallet_bridge_api`: 35 methods (convenience wrapper, simplified returns)
- `rc_api`: 7 methods (Resource Credits)
- `market_history_api`: 7 methods (HIVE/HBD market)
- `account_history_api`: 4 methods (with bitmask operation filtering)

**7 non-API plugins**: chain (core), witness (block production), p2p (networking), market_history, reputation, transaction_status, state_snapshot.

**Key issues**: `get_account_references` permanently broken. Inconsistent pagination limits across APIs. A method whose optional plugin is missing throws a clear `X_plugin not enabled.` assert (JSON-RPC -32003); only account enrichments degrade silently: the reputation field inside `get_accounts` and, without the `metadata` plugin, the account JSON metadata fields (Part 10 Discrepancy 3). `wallet_bridge_api` bypasses `database_api` for some methods, accessing chain DB directly.

**Documentation**: 1.3MB OpenAPI/Swagger spec in `libraries/plugins/apis/documentation/openapi.json`.

---

## Known Bugs and Issues

| # | Issue | Category | Severity | Part | Location | Status |
|---|-------|----------|----------|------|----------|--------|
| 1 | RC is non-consensus until HF29 | Arch debt | Known | 08 | `rc_utility.cpp:567-602` | HF29 switch, defined in 1.28.8 code, inactive on mainnet (Part 08, section Non-Consensus Status) |
| 2 | `request_account_recovery` authority size check: HF29 switch `HIVE_HARDFORK_1_29_FIX_ENFORCEMENT_OF_AUTHORITY_SIZE_ON_RECOVERY_REQUEST` (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)): `request_account_recovery` checks the size of the new owner authority on every request path. A 1.28.8 node already applies this check to new transactions submitted to it (API or P2P) and to blocks it produces (`is_in_control()`, `database.hpp:176`). See Part 16, Key Discovery 3, and Part 11, Key Discovery 5 | Evaluator check | Known | 04 | `hive_evaluator_account.cpp:500-506` | HF29 is defined in 1.28.8 code, inactive on mainnet |
| 3 | HF1 vesting split rounding bug in power-down | Bug | Fixed | 09 | `database_comment.cpp:621-623`, `database_vesting.cpp:128-129` | Fixed in HF28 |
| 4 | `hardfork_hive_restore_operation` late airdrop VESTS accounting | Bug | Low | 02 | `hive_virtual_operations.hpp` | Unknown |
| 5 | `get_account_references` API permanently broken | Tech debt | Low | 10 | `condenser_api.cpp:397` | No fix planned |
| 6 | Bad merkle roots in 8 historical blocks | Errata | N/A | 06 | `shared_db_merkle.hpp:5-20` | Permanent (historical) |
| 7 | HBD print rate cliff (binary on/off at 20%) | Policy | N/A | 07 | `protocol/config.hpp:342-343` | Intentional (HF26) |
| 8 | Recovery rate limit inconsistency vs `account_update` | Bug | Low | 04 | `hive_evaluator_account.cpp` | Unresolved |
| 9 | `comment_reward_operation.author_rewards` typed as `share_type` not `HIVE_asset` | Tech debt | Low | 02 | `hive_virtual_operations.hpp` | TODO in code |

*Note: Original items #7 (fork switch) and #8 (HBD cliff) from the research were reclassified after source-code verification: #7 is described in Notable Finding 8 as Part 06 describes it (section Fork Switch, step 5), #8 is an intentional governance decision. See Notable Findings section above for details.*

---

## Prioritized Recommendations

*Recommendations reflect post-verification classification. Items previously listed as "high priority" that turned out to be design choices or historical facts have been removed or reclassified.*

### Existing Tracked Items (no action needed from us)

1. **RC non-consensus** - Developers are aware: RC is non-consensus until HF29, which is defined in 1.28.8 code, inactive on mainnet (Part 08, section Non-Consensus Status, which describes the switch).

2. **`request_account_recovery` auth validation** - HF29 switch `HIVE_HARDFORK_1_29_FIX_ENFORCEMENT_OF_AUTHORITY_SIZE_ON_RECOVERY_REQUEST` (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)): `request_account_recovery` checks the size of the new owner authority on every request path (`hive_evaluator_account.cpp:500-506`). A 1.28.8 node already applies this check to new transactions submitted to it (API or P2P) and to blocks it produces (`is_in_control()`, `database.hpp:176`). See Part 16, Key Discovery 3, and Part 11, Key Discovery 5.

3. **HF1 vesting rounding bug** — Already fixed in HF28.

### Code Quality Improvements

4. **Clean up dead operations**: 7 disabled/dead operations (`reset_account`, `set_reset_account`, `pow`, `pow2`, `custom_binary`, `account_create_with_delegation`, `witness_block_approve`) add code complexity. Consider explicit "disabled" evaluator type.

5. **Resolve ID-vs-name inconsistency in state objects**: Mixed use of `account_id_type` and `account_name_type` across objects. Since 1.28.8 several objects note why their names must stay; TODO-style comments remain on the escrow parties (`escrow_object.hpp:69-71`), `change_recovery_account_request_object::recovery_account` (`account_object.hpp:591`) and the dgpo's `current_witness` (`global_property_object.hpp:208`) (Part 05, Key Discovery 9 and Open Question 1).

6. **Remove legacy phantom objects**: `block_stats_object` (type ID 24, never defined), `liquidity_reward_balance_object` (unused since HF12), and `comment_cashout_ex_object` (empty since HF19).

### Low Priority

7. **Fix or remove `get_account_references` API**: Permanently broken method throwing on every call (`condenser_api.cpp:397`). Either implement or remove.

8. **Standardize JSON validation**: Relaxed fallback parser for replay compatibility could surprise developers.

9. **Document escrow default ID=30 convention**: Undocumented, could confuse client library implementers.

10. **Add logging to fork switch error recovery**: no log line records the decision not to revert: the `if` at `sync_block_writer.cpp:236-237` has no `else`; the failure itself is logged at `sync_block_writer.cpp:219` (Part 06, section Fork Switch, step 5).

---

## Open Questions — Triaged (2026-04-04)

*Each question investigated against source code. Status: RESOLVED (answered from code), KNOWN (developers aware, no public resolution), or ASK TEAM (requires insider knowledge).*

### Architecture

**1. When will RC become consensus?** — KNOWN, no timeline
Non-consensus until HF29, which is defined in 1.28.8 code, inactive on mainnet (Part 08, section Non-Consensus Status, which describes the switch; the balance check is at `rc_utility.cpp:567`). See Notable Finding #1.

**2. What is `queen_mode` in the witness plugin?** — RESOLVED
Testnet and mirrornet builds only (`USE_ALTERNATE_CHAIN_ID`, set for both, `cmake/hive_options.cmake:31-35`). When enabled (via the queen plugin), the witness plugin skips the identity check (`witnesses.find(scheduled_witness)`) and produces blocks for ANY scheduled witness as long as it has the signing key. Protected by `#ifndef USE_ALTERNATE_CHAIN_ID`: cannot activate on mainnet. Used for single-node testing/benchmarking. Source: `witness_plugin.cpp:335`, `queen_plugin.cpp:273-280`.

**3. What is `hf_21_stall_block`?** — RESOLVED
Constant block number `35922615` in `hardfork.d/0_21.hf:18-22` (alternate-chain builds read the configurable `hf_21_stall_block` instead). `update_manabar()` uses it to choose the downvote-mana computation: blocks up to it keep the HF21-era one, later blocks the current one, and testnet and iceberg-enabled converter builds always use the current one (`manabar.hpp:120-135`; Part 01, Key Discovery 11). The comment "remove when `iceberg` is implemented" sits on the alternate-chain knob (`testnet_blockchain_configuration.hpp:283`). **Iceberg** is the `iceberg_generate` plugin of the blockchain converter, which generates a valid blockchain from a range of mainnet blocks for mirrornet/testing, with all necessary account/comment context. Iceberg implementation exists in the converter tool but the stall_block reference persists.

**4. Plans to migrate `account_name_type` -> `account_id_type`?** — RESOLVED: no active plan
Investigated GitLab issues, MRs, branches, and commit history: no active work, no filed issues, no branches. At 1.28.8 informal ABW annotations are on the escrow parties ("can be replaced with account_id_type (ABW: would make looking for escrow object harder)", `escrow_object.hpp:69-71`) and, since 1.28.8, on the dgpo's `current_witness` ("check if worth replacing with account_id_type (ABW: probably not)", `global_property_object.hpp:208`; at 1.28.7 a plain TODO to replace it), and `change_recovery_account_request_object::recovery_account` is marked "could be changed to id" (`account_object.hpp:591`). The savings-withdraw and limit-order TODOs of 1.28.7 became notes since 1.28.8 that the names cannot be replaced (`savings_withdraw_object.hpp:54-55`, `limit_order_object.hpp:68`; Part 05, Key Discovery 9). These are code notes, not tracked work.

**5. Plans to refactor `account_object`?** — ASK TEAM
50+ fields, some marked "REMOVE" (not used by consensus, only API). No refactoring plan visible in source.

### Consensus

**6. How is HF28 activation controlled?** — RESOLVED
Time plus witness supermajority, no block-number condition. `hardfork.d/1_28.hf` sets the time via `next_hf_time()` -> mainnet `1763557200` (2025-11-19 13:00 UTC), overridable via `HIVE_HF28_TIME` env var. `process_hardforks()` (`database_hardfork.cpp:119-149`) applies the next hardfork when `hardforks.next_hardfork_time <= head_block_time()` and the witness-voted `next_hardfork` version is ahead of the last applied one; the `HIVE_HARDFORK_1_28_BLOCK` constant (`hardfork_block.hpp:30`; 101319928 since 1.28.8, 100000000 at 1.28.7) is never consulted by the chain, only by the mirrornet `blockchain_converter` (Part 01 Discovery 7). Activation happened at block 101,319,928, the first block whose timestamp reached the hardfork time (verified against a public node: block 101,319,927 is 12:59:57, block 101,319,928 is 13:00:00; block 100,000,000 dates from 2025-10-04).

**7. Fork DB capacity and undo stack interaction?** — RESOLVED
The fork DB window is the member `_max_size`, 1024 at start (`fork_database.hpp:207`); `MAX_BLOCK_REORDERING` = 1024 (`fork_database.hpp:67`) is declared but used by no code. After every applied block and every accepted fast confirm, `store_block` sets the window to head - LIB + 1 (`sync_block_writer.cpp:59`), so there is no fixed 1024 cap. Blocks at or below head - `_max_size` are rejected as unlinkable (`fork_database.cpp:84-87`). Oldest block in fork DB = last irreversible block (`fork_database.cpp:448-449`). When LIB advances, `migrate_irreversible_state` writes the newly irreversible blocks to the block log, shrinks the fork DB window and then commits their undo state (`database.cpp:3103-3134`). The practical reorg depth is head - LIB, normally a handful of blocks. Undo history is bounded separately by `HIVE_MAX_UNDO_HISTORY` = 10,000 blocks between head and LIB (`protocol/config.hpp:368`, `database.cpp:2870-2877`): past it each further block fails to apply, so the node stops following the chain; with every slot filled that is about 8.3 hours (Part 06, sections Fork Database Structure and Undo History and Reorg Depth Limits).

**8. Fast-confirm P2P propagation?** — RESOLVED
Fast confirms are regular P2P transactions (not a separate message type). Witness plugin calls `p2p_plugin.broadcast_transaction()` (`witness_plugin.cpp:290`). Peers receive via standard gossip, then `chain_plugin.push_transaction()` routes them to `process_fast_confirm_transaction()`: a separate code path from normal transactions. Fast confirms are **never included in blocks**: the evaluator asserts this (`hive_evaluator.cpp:615-620`). They update a per-witness tracking map (`_last_fast_approved_block_by_witness`), which feeds into `update_last_irreversible_block()`. When 75% of the scheduled witnesses (16 of 21, `HIVE_IRREVERSIBLE_THRESHOLD`, `protocol/config.hpp:380`) have approved a block, it becomes irreversible.

**9. Split block log migration procedure?** - RESOLVED
Part 06 answers it from the code (section Migration: Monolithic -> Split (automatic at startup)): when the node opens block storage, finds no part files and splitting is allowed, it splits an existing monolithic `block_log` into the 1M-block part files (`block_log_wrapper.cpp:639-669`); `block_log_util --split` does the same offline (`block_log_util.cpp:1373`).

### Economics

**10. When does inflation reach 0.95% floor?** — RESOLVED
Block ~220,750,000. At 3s/block from genesis (2016-03-24), this is ~21 years ≈ **March 2037**. Calculation: (9.78% - 0.95%) / 0.01% = 883 decreases × 250,000 blocks = 220,750,000.

**11. How are RC execution time benchmarks maintained?** — RESOLVED
Hardcoded constants in `resource_sizes.cpp:167-240`. Each operation's time is a sum of measured components (validate + exec + pre_rc + post_rc, plus automatic processing for some, `resource_sizes.cpp:179`). Values come from benchmark measurements documented in GitLab issue #205. They are NOT measured at runtime. When implementation changes, engineers must re-run benchmarks and manually update the constants. A `USE_FIXED_SIZE` macro (`resource_sizes.cpp:22-26`) selects fixed or dynamically computed object sizes for the state costs, not the execution times.

**12. Are RC resource dynamics parameters still tuned?** — RESOLVED: last rebalanced 2022, no changes since
The JSON was tuned several times after its first version. Full history: initial 2018 implementation with several tuning rounds (#2547, #2628, #2974, #3061). **Major rebalance in 2022 (MR !390 by ABW)**: state budget recalculated to reflect actual byte-hours (5yr persistent / 2.5yr lasting tiers), execution budget shortened to 1hr half-life based on benchmarks (issue #205), new pool popularity mechanism auto-balances cost across resource types, all non-account-token costs 3x multiplied. `resource_parameters.json` last substantively modified 2022-04-28. No changes since. Only `resource_new_accounts` is witness-adjustable; the other 4 pools take their parameters from `resource_parameters.json`, transformed when CMake configures the build (`libraries/jsonball/CMakeLists.txt:26-32`; Part 08, section Raw JSON Source vs Runtime Values) and written into chain state once, when HF20 is applied (`database_hardfork.cpp:363-379`); afterwards only the `resource_new_accounts` parameters change (`rc_utility.cpp:868-872`), so a changed JSON reaches a node's state only when it replays through HF20. The popularity mechanism (MR !390) was designed to reduce need for manual rebalancing.

**13. DHF maintenance drift issue?** — RESOLVED
`dhf_processor.cpp:219-220`: "shifting from current time instead of proper maintenance time causes drift when maintenance block was missed, but the fix is problematic - see MR!168 for details." When a maintenance block is missed, using `head_time` instead of scheduled `next_maintenance_time` causes cumulative drift. MR!168 documents why a complete fix is problematic (consensus/hardfork implications). Low practical impact — maintenance blocks are rarely missed on a healthy network.

### API

**14. OpenAPI spec — auto-generated or manual?** — RESOLVED
**Manually maintained.** The 24,999-line `openapi.json` (24,873 lines at 1.28.7) in `libraries/plugins/apis/documentation/` is version-controlled: 76 commits touch it up to 1.28.8 (59 up to 1.28.7; Part 10, section Documentation & API Spec Generation). Not auto-generated from C++ code. The Python `api_generation` package consumes it and a Node.js script flattens it (`libraries/plugins/apis/api_generation/flatten_swagger.js`); neither generates it. Drift risk is real: spec must be manually updated when API methods change.

**15. Default plugin enablement?** — RESOLVED
From `programs/hived/main.cpp`: **Always loaded** (regardless of config): `chain_plugin`, `p2p_plugin`, `webserver_plugin`. **Default config** (included unless removed): `witness_plugin`, `account_by_key_plugin`, `account_by_key_api_plugin`, `state_snapshot_plugin`. All API plugins (database_api, condenser_api, etc.) require explicit configuration.

**16. Per-client rate limiting?** — RESOLVED
**None.** No per-IP, per-client, or per-request rate limiting exists in the webserver or json_rpc plugins. Only the P2P connection limit (`p2p-max-connections`, `p2p_plugin.cpp:436`; it counts incoming and outgoing connections together, `libraries/net/node.cpp:2008-2026`) and per-query result pagination (`limit` parameters). Node operators must implement rate limiting externally (reverse proxy, firewall).

**17. What is the `colony` plugin?** — RESOLVED
Stress-testing/load-generation plugin. Automatically generates synthetic transactions (articles, replies, votes, transfers, custom_json) using multiple worker threads to flood the network with configurable loads. Used for performance testing. Referenced in shutdown order because it must stop generating transactions before other plugins shut down. Not an API plugin — no endpoints exposed.

### Operations

**18. Max operations per transaction?** — RESOLVED
**No explicit limit.** `transaction.cpp:40-56` only checks `operations.size() > 0`. The effective limit is the transaction size: on the push path a transaction may be at most the witness-voted `maximum_block_size` minus 256 bytes (`database.cpp:566-572`); the 64KB `HIVE_MAX_TRANSACTION_SIZE` (`protocol/config.hpp:363`) is not checked against transactions (Part 02, section Transaction-Level Constraints). As many operations as fit within that size.

**19. Chain-interpreted custom_json IDs?** — RESOLVED
Only **`"rc"`** is interpreted by the chain layer (`hive_custom_operations.hpp:23`, `HIVE_RC_CUSTOM_OPERATION_ID`). Contains `delegate_rc_operation`. All other custom_json IDs ("follow", "community", etc.) are application-layer conventions passed to generic custom operation interpreters — not validated or interpreted by core consensus.

**20. Authority recursion depth enforcement?** — RESOLVED
`HIVE_MAX_SIG_CHECK_DEPTH = 2` (`protocol/config.hpp:356`). Enforced in **signature verification**, not validate(). `sign_state.hpp:216-223` in `check_authority_impl()` stops recursion when `depth == limits.recursion`. Nested account authorities beyond depth 2 are silently skipped.

**21. Comment depth 255 — where enforced?** — RESOLVED
`HIVE_SOFT_MAX_COMMENT_DEPTH = 0xff (255)` (`protocol/config.hpp:271`). Enforced in the **comment evaluator** (`hive_evaluator_social.cpp:186-190`), not validate(). Checked only when `_db.is_in_control()` (new transactions from API or P2P and blocks the node produces). Post-HF17 hard limit is 64K (`HIVE_MAX_COMMENT_DEPTH = 0xffff`, `protocol/config.hpp:270`); the code comment says the soft check was moved from the witness plugin (`hive_evaluator_social.cpp:188`).

### Historical

**22. hardfork_hive_restore_operation VESTS bug resolution?** — KNOWN, unresolved
The bug is **acknowledged but unfixed**. `hardfork_hive_restore.proto:9-10` contains the question: "the late airdrop did not apply properly since HIVE that the accounts should receive did not account for HIVE from converted VESTS. [how was it resolved?]" The question mark remains unanswered in the codebase. No corrective mechanism was implemented.

**23. h23_balances — future recovery possible?** — RESOLVED
**Yes, technically.** `hardfork_property_object.hpp:36` maintains `h23_balances` as a persistent `flat_map` in chainbase. The `gather_balance()` function (`database_hardfork.cpp:557-563`) stored the HIVE/HBD swept from each cleared account: savings, liquid and reward balances (`database.cpp:1610-1611`, `:1624-1625`, `:1638-1639`, `:1664`); HF23 cleared at most 328 accounts (the list has 332 entries, 4 of them duplicates). HF24's `restore_accounts()` reads the entries of the 51 accounts it restores (`hardfork.d/0_23.hf`) and erases none (`database.cpp:1434-1476`), so they are NOT deleted post-hardfork. A future hardfork could call `restore_accounts()` with a new list (Part 09, section The HF23 Clear / HF24 Restore Mechanism).

**24. Planned but unshipped hardfork features?** — ASK TEAM
At 1.28.8 HF29 is defined in code, inactive on mainnet, with five switches (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)). Whether there's a feature roadmap is a governance/team question.

**25. block_stats_object — defined anywhere?** — RESOLVED
**No.** Only an enum entry (`hive_object_types.hpp:74`), a forward declaration (`hive_object_types.hpp:115`) and an id typedef (`hive_object_types.hpp:155`). No struct definition anywhere in the codebase. The unrelated `block_stats` class in `block_flow_control.hpp` is a runtime statistics tracker, not a persistent object. The type ID appears permanently unused/abandoned.

---

## Conflicts and Inconsistencies Between Parts

### 1. Virtual Operation Count

**Part 02 summary** originally stated "44 virtual operations (IDs 50-93)" but the actual `operations.hpp` variant lists `last_regular+1` through `last_regular+43`, ending at `declined_voting_rights_operation` (last_regular+43). **Resolution**: **43 virtual operations** is correct. Part 02 findings file corrected.

### 2. Object Type Counts

**Part 05 summary** originally said "35 object types" while its detail sections enumerated "39 type IDs (0-38), 37 with actual definitions." **Resolution**: at 1.28.8 Part 05 counts 39 type IDs (0-38): 37 defined in the core chain library, `account_metadata` (ID 2) defined in the metadata plugin, and `block_stats` (ID 24) never defined (`hive_object_types.hpp:48-90`; Part 05, Summary).

### 3. End-of-Block Processing Descriptions

Parts 04, 06, and 07 all describe the end-of-block sequence. Part 06 provides the most granular code-level walkthrough. Part 04 has a 30-step summary. Part 07 focuses on economic steps. All three are consistent in ordering but differ in granularity. **Resolution**: Part 06's description at `database.cpp:2200-2386` is authoritative.

### 4. HBD Interest Description

Part 04 says HBD interest accrual is hidden in the balance helpers: `adjust_savings_balance()` with an HBD delta, before HF25 also `adjust_balance()` with an HBD delta, pays accrued interest as a side effect (Key Discovery 12), while Part 07 describes it as a dollar-seconds accumulator paid lazily when the balance is next modified (section HBD Interest). These are complementary descriptions of the same mechanism (not conflicting). Both say liquid HBD earned interest only before HF25 and savings HBD in every era. **Resolution**: Consistent.

---

## Code Reference Table

### Protocol Layer (`libraries/protocol/`)

| Component | File | Key Lines |
|-----------|------|-----------|
| Timing, economic and size constants | `include/hive/protocol/config.hpp` | 21-493 |
| NAI bit layout and encoding | `include/hive/protocol/asset_symbol.hpp` | 9-53 |
| Asset struct and price | `include/hive/protocol/asset.hpp` | 21-186 |
| Asset validation | `asset.cpp` | 128-286 |
| Authority struct | `include/hive/protocol/authority.hpp` | 7-57 |
| Account name validation | `authority.cpp` | 58-122 |
| Operation variant (93 types: 50 regular + 43 virtual) | `include/hive/protocol/operations.hpp` | 15-125 |
| Base operation class | `include/hive/protocol/base.hpp` | 13-29 |
| Regular operation structs | `include/hive/protocol/hive_operations.hpp` | — |
| DHF operation structs | `include/hive/protocol/dhf_operations.hpp` | — |
| Virtual operation structs | `include/hive/protocol/hive_virtual_operations.hpp` | — |
| RC custom operations | `include/hive/protocol/hive_custom_operations.hpp` | 8-17 |
| Operation validate() methods | `hive_operations.cpp` | 1-867 |
| DHF operation validation | `dhf_operations.cpp` | 1-62 |
| Block header struct | `include/hive/protocol/block_header.hpp` | 15-26 |
| Transaction struct | `include/hive/protocol/transaction.hpp` | 12-53 |
| Transaction validation | `transaction.cpp` | 40-55 |
| Version encoding | `include/hive/protocol/version.hpp` | 15-77 |
| Hardfork definitions | `hardfork.d/*.hf` | — |
| Hardfork block numbers (HF1-HF28 activation blocks; HF29 the converter's threshold for converted chains, Part 09) | `include/hive/protocol/hardfork_block.hpp` | 3-31 |
| Chain IDs | `include/hive/protocol/config.hpp` | 132-142 |
| Validation helpers | `include/hive/protocol/validation.hpp` | 18-115 |
| HBD interest calc | `include/hive/protocol/hbd_interest.hpp` | 8-23 |
| Collateral estimation | `include/hive/protocol/hive_collateral.hpp` | 8-26 |
| Testnet overrides | `include/hive/protocol/testnet_blockchain_configuration.hpp` | 27-284 |

### Chain Layer (`libraries/chain/`)

| Component | File | Key Lines |
|-----------|------|-----------|
| Block application (`_apply_block`) | `database.cpp` | 2200-2386 |
| Block header validation | `database.cpp` | 2796-2818 |
| Transaction application | `database.cpp` | 2661-2719 |
| Operation dispatch | `database.cpp` | 2739-2763 |
| Balance helpers | `database.cpp` | 3179-3361 |
| Supply issue/burn (dgpo methods; `adjust_supply` removed in 1.28.8) | `detail/state/global_property_object.hpp` | 295-396 |
| LIB calculation | `database.cpp` | 2993-3101 |
| Fast confirm processing | `database.cpp` | 2936-2991 |
| Irreversibility migration | `database.cpp` | 3103-3134 |
| Participation tracking | `database.cpp` | 2828-2878 |
| Median feed update | `database.cpp` | 2416+ |
| HBD print rate / virtual supply | `database.cpp` | 2880-2926 |
| Inflation distribution | `database.cpp` | 1725 |
| HBD creation helper (`award_hbd`; `create_hbd` at 1.28.7) | `database.cpp` | 957-1005 |
| next_hf_time() | `database.cpp` | 62-81 |
| Account clearing/restoration | `database.cpp` | 1434-1667 |
| Evaluator base class | `include/hive/chain/evaluator.hpp` | — |
| Evaluator registry | `include/hive/chain/evaluator_registry.hpp` | — |
| Evaluator registration | `database_init.cpp` | — |
| Transfer evaluators | `hive_evaluator_transfer.cpp` | 75-1028 |
| Account evaluators | `hive_evaluator_account.cpp` | 130-643 |
| Social evaluators | `hive_evaluator_social.cpp` | 56-866 |
| Witness/custom/pow evaluators | `hive_evaluator.cpp` | 62-620 |
| DHF evaluators | `dhf_evaluator.cpp` | 31-272 |
| Comment cashout/curation | `database_comment.cpp` | 121-510 |
| Market/order matching | `database_market.cpp` | — |
| Vesting withdrawals | `database_vesting.cpp` | 111+ |
| Conversion processing | `database_conversion.cpp` | 35+ |
| DHF/recurrent transfers | `database_dhf.cpp` | — |
| Hardfork application | `database_hardfork.cpp` | — |
| Witness scheduling | `witness_schedule.cpp` | 152-396 |
| Witness missed blocks | `database_witness.cpp` | 284-306 |
| Fork database | `fork_database.cpp` | 20-554 |
| Fork switching | `sync_block_writer.cpp` | 162-367 |
| Block log read/write | `block_log.cpp` | 339-518 |
| Block log artifacts | `block_log_artifacts.cpp` | 46-166 |

### State Objects (`libraries/chain/include/hive/chain/`)

| Object | File |
|--------|------|
| Object type enum (39 IDs) | `hive_object_types.hpp:48-90` |
| dynamic_global_property_object | `detail/state/global_property_object.hpp` |
| account_object (50+ fields) | `detail/state/account_object.hpp` |
| account_authority_object | `detail/state/account_object.hpp:364` |
| comment_object / comment_cashout | `detail/state/comment_object.hpp` |
| comment_vote_object | `detail/state/comment_object.hpp:372` |
| witness_object | `detail/state/witness_objects.hpp:69` |
| witness_schedule_object | `detail/state/witness_objects.hpp:181` |
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
| Non-consensus enforcement | `rc_utility.cpp` | 567-602 |
| Mana deduction (finalize_tx) | `rc_utility.cpp` | 830-862 |
| RC delegation mechanics | `rc_utility.cpp` | 38-122 |
| Delegation overflow | `rc_utility.cpp` | 424-466 |
| Flood surcharge | `rc_utility.cpp` | 529-562 |
| Resource counting | `resource_count.cpp` | 136-631 |
| State byte sizes | `resource_sizes.cpp` | 45-165 |
| Execution time benchmarks | `resource_sizes.cpp` | 167-242 |
| Price curve computation | `rc_curve.cpp` | 33-99 |
| Pool dynamics (decay) | `libraries/chain/util/rd.cpp` | 23-118 |
| Resource parameters | `libraries/jsonball/data/resource_parameters.json` | — |
| Manabar struct + update utility | `include/hive/chain/util/manabar.hpp` | 32-141 |
| RC state objects | `include/hive/chain/rc/rc_objects.hpp` | — |
| RC API | `libraries/plugins/apis/rc_api/` | — |

### Plugins (`libraries/plugins/`)

| Component | File |
|--------|------|
| AppBase plugin framework | `libraries/appbase/include/appbase/plugin.hpp` |
| JSON-RPC routing/registration | `json_rpc/json_rpc_plugin.cpp` |
| API declaration macros | `json_rpc/include/.../utility.hpp` |
| WebServer transports | `webserver/webserver_plugin.cpp` |
| condenser_api (62 methods) | `apis/condenser_api/` |
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
| Total research parts | 17 (Parts 01-10 summarized here; zoom Parts 11-17 listed below) |
| Parts completed | 17 |
| Regular operations | 50 (IDs 0-49) |
| Virtual operations | 43 (IDs 50-92) |
| Active evaluators | 43 (50 registered, 7 disabled) |
| State object type IDs | 39 (37 defined in the core chain library) |
| Consensus constants cataloged | 150+ |
| Hardforks documented | 28 (HF29 defined in 1.28.8 code, inactive on mainnet; Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)) |
| API plugins | 18 (plus the built-in jsonrpc namespace) |
| API methods | 198 (196 in 18 plugins + 2 in jsonrpc) |
| `has_hardfork()` checks | 257 in 17 files of `libraries/chain` at 1.28.8 (calls of `has_hardfork(`, declaration and definition not counted) |
| Tracked bugs/issues | 9 (1 arch debt, 1 evaluator check with an HF29 switch, 3 bugs [1 fixed], 2 tech debt, 2 errata/policy) |
| Open questions | 25 -> 21 resolved, 2 known/unresolved, 2 ask-team |
| Notable findings | 8 (reclassified from "critical" after verification) |
| Recommendations | 10 |

<!-- zoom-addition: 2026-06-11T10:12:55+02:00 -->
- Part 11 (validate-evaluate-gaps): see `findings/11-validate-evaluate-gaps.md`

<!-- zoom-addition: 2026-06-11T11:46:33+02:00 -->
- Part 12 (recurrent-transfers): see `findings/12-recurrent-transfers.md`

<!-- zoom-addition: 2026-06-11T12:56:00+02:00 -->
- Part 13 (external-storage): see `findings/13-external-storage.md`

<!-- zoom-addition: 2026-06-11T15:49:41+02:00 -->
- Part 14 (delayed-voting): see `findings/14-delayed-voting.md`

<!-- zoom-addition: 2026-06-12T16:27:15+02:00 -->
- Part 15 (rc-consensus): see `findings/15-rc-consensus.md`

<!-- zoom-addition: 2026-06-13T02:32:28+02:00 -->
- Part 16 (escrow-recover-gaps): see `findings/16-escrow-recover-gaps.md`

<!-- zoom-addition: 2026-06-13T17:13:51+02:00 -->
- Part 17 (witness-subsidy): see `findings/17-witness-subsidy.md`
