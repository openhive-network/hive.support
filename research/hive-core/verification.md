# Verification Report

- Topic: `hive-core`
- Pinned: `develop@2026-04-02` (`44c3fd880`)
- Run: 2026-05-26T17:31:54+02:00
- Citations audited: 166


### [1/166] libraries/protocol/include/hive/protocol/config.hpp:56-458 — All timing/economic/size constants
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56-458
STATUS: confirmed
REASON: The cited line range contains all timing constants (block interval, cashout windows, recovery periods), economic constants (inflation rates, APR percentages, reward percentages, HBD limits), and size constants (max memo, max transaction, max block size, name lengths) as claimed.
SUGGESTED_FIX: none

### [2/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-53 — NAI bit layout and encoding
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-53
STATUS: confirmed
REASON: The excerpt defines HIVE_ASSET_SYMBOL_PRECISION_BITS (4), HIVE_ASSET_CONTROL_BITS (1), HIVE_NAI_SHIFT, and the HIVE_ASSET_NUM_* macros that encode NAI via `((SMT_MAX_NAI + NAI) << HIVE_NAI_SHIFT) | PRECISION`, directly documenting the NAI bit layout and encoding.
SUGGESTED_FIX: none

### [3/166] libraries/protocol/include/hive/protocol/asset.hpp:21-186 — Asset struct and price
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:21-186
STATUS: confirmed
REASON: The cited range spans the `asset` struct (line 21-96) and the `price` struct (line 139-186), directly supporting the claim about "Asset struct and price".
SUGGESTED_FIX: none

### [4/166] libraries/protocol/asset.cpp:128-286 — Asset validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/asset.cpp:128-286
STATUS: confirmed
REASON: The cited range contains multiple asset validation routines including `asset_num_from_nai()` (NAI range, check digit, decimal places), `is_vesting()`, `get_paired_symbol()`, `space()`, and the explicit `validate()` method, all of which directly support the "Asset validation" claim.
SUGGESTED_FIX: none

### [5/166] libraries/protocol/include/hive/protocol/authority.hpp:7-55 — Authority struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/authority.hpp:7-55
STATUS: confirmed
REASON: The source excerpt at lines 7-55 defines the `authority` struct with its classification enum, constructors, helper methods, and the three core fields (`weight_threshold`, `account_auths`, `key_auths`), directly supporting the claim.
SUGGESTED_FIX: none

### [6/166] libraries/protocol/authority.cpp:58-122 — Account name validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/authority.cpp:58-122
STATUS: confirmed
REASON: Lines 58-122 contain the complete `check_account_name` function which validates account name length, segment structure, and per-character allowed sets — directly supporting the "Account name validation" claim.
SUGGESTED_FIX: none

### [7/166] libraries/protocol/include/hive/protocol/operations.hpp:15-125 — Operation variant (93 types: 50 regular + 43 virtual)
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/operations.hpp:15-125
STATUS: confirmed
REASON: The static_variant spans regular operations numbered 0-49 (50 total) and virtual operations from last_regular+1 through last_regular+43 (43 total), summing to 93 as claimed.
SUGGESTED_FIX: none

### [8/166] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Base operation class
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: The cited lines define `base_operation` (13-23) and `virtual_operation` (25-29), directly supporting the claim about the base operation class.
SUGGESTED_FIX: none

### [9/166] libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-17 — RC custom operations
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-17
STATUS: confirmed
REASON: The cited lines define `delegate_rc_operation` struct with RC delegation fields, directly supporting the claim about RC custom operations.
SUGGESTED_FIX: none

### [10/166] libraries/protocol/hive_operations.cpp:1-866 — Operation validate() methods
Source: `00-consolidated.md`

CITATION: libraries/protocol/hive_operations.cpp:1-866
STATUS: confirmed
REASON: The cited file spans lines 1-866 and contains numerous operation `validate()` method implementations (account_create, transfer, vote, comment, witness_update, escrow_*, recurrent_transfer, etc.), directly supporting the claim about operation validate() methods.
SUGGESTED_FIX: none

### [11/166] libraries/protocol/dhf_operations.cpp:1-62 — DHF operation validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/dhf_operations.cpp:1-62
STATUS: confirmed
REASON: The cited file contains validate() implementations for all four DHF operations (create_proposal, update_proposal, update_proposal_votes, remove_proposal), directly supporting the "DHF operation validation" claim.
SUGGESTED_FIX: none

### [12/166] libraries/protocol/include/hive/protocol/block_header.hpp:15-26 — Block header struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/block_header.hpp:15-26
STATUS: confirmed
REASON: Lines 15-26 contain the `struct block_header` definition with its fields (previous, timestamp, witness, transaction_merkle_root, extensions), directly supporting the claim.
SUGGESTED_FIX: none

### [13/166] libraries/protocol/include/hive/protocol/transaction.hpp:12-53 — Transaction struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-53
STATUS: confirmed
REASON: The cited lines define the `transaction` struct with its fields (ref_block_num, ref_block_prefix, expiration, operations, extensions) and methods, directly supporting the claim.
SUGGESTED_FIX: none

### [14/166] libraries/protocol/transaction.cpp:40-55 — Transaction validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/transaction.cpp:40-55
STATUS: confirmed
REASON: Lines 40-55 contain the two `transaction::validate()` method definitions that perform transaction-level validation (requiring at least one operation and invoking `operation_validate` on each), directly supporting the claim.
SUGGESTED_FIX: none

### [15/166] libraries/protocol/include/hive/protocol/version.hpp:15-77 — Version encoding
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:15-77
STATUS: confirmed
REASON: The cited range contains the `version` struct definition with its constructor (major/hardfork/release triple) and the bit-extraction accessors `major_v()`, `minor_v()`, `rev_v()` that document the 32-bit `v_num` encoding scheme.
SUGGESTED_FIX: none

### [16/166] libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30 — Hardfork block numbers
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30
STATUS: confirmed
REASON: Lines 3-30 contain exactly the `#define HIVE_HARDFORK_*_BLOCK` constants (HF0_1 through HF1_28), which directly defines the hardfork block numbers as claimed.
SUGGESTED_FIX: none

### [17/166] libraries/protocol/include/hive/protocol/config.hpp:137-143 — Chain IDs
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:137-143
STATUS: confirmed
REASON: Lines 137-143 define HIVE_CHAIN_ID for both Mirrornet (0x42...) and Hive mainnet (beeab0de...), directly supporting the "Chain IDs" claim.
SUGGESTED_FIX: none

### [18/166] libraries/protocol/include/hive/protocol/validation.hpp:64-115 — Validation helpers
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/validation.hpp:64-115
STATUS: confirmed
REASON: The cited range contains multiple inline validation helper functions (validate_string_max_size, validate_is_utf8, validate_string_is_not_empty, validate_number_in_100_percent_range, validate_account_name, validate_permlink), directly supporting the "Validation helpers" claim.
SUGGESTED_FIX: none

### [19/166] libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23 — HBD interest calc
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23
STATUS: confirmed
REASON: Lines 8-23 contain the `hbd_interest` struct with `evaluate_hbd_interest` implementing the standard interest formula (hbd_seconds / HIVE_SECONDS_PER_YEAR * hbd_interest_rate / HIVE_100_PERCENT), directly supporting the "HBD interest calc" claim.
SUGGESTED_FIX: none

### [20/166] libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26 — Collateral estimation
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26
STATUS: confirmed
REASON: The cited lines define the `hive_collateral` struct with the `estimate_hive_collateral` static method that computes required collateral from HBD amount using the min price feed and conversion fee/ratio, directly supporting the "Collateral estimation" claim.
SUGGESTED_FIX: none

### [21/166] libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285 — Testnet overrides
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285
STATUS: confirmed
REASON: The cited range contains the `configuration` class defining testnet-specific overrides (cashout windows, voting periods, supply, hardfork times, RC stats frequency) with `#ifdef IS_TEST_NET` guards, directly supporting the "Testnet overrides" claim.
SUGGESTED_FIX: none

### [22/166] libraries/chain/database.cpp:2183-2369 — Block application (`_apply_block`)
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2183-2369
STATUS: confirmed
REASON: The source at lines 2183-2369 defines `database::_apply_block`, matching the claim about block application exactly.
SUGGESTED_FIX: none

### [23/166] libraries/chain/database.cpp:2757-2779 — Block header validation
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2757-2779
STATUS: confirmed
REASON: Lines 2757-2779 contain `database::validate_block_header` which validates the previous block ID, timestamp ordering, witness signing key, and witness schedule slot — directly supporting the "Block header validation" claim.
SUGGESTED_FIX: none

### [24/166] libraries/chain/database.cpp:2644-2702 — Transaction application
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2644-2702
STATUS: confirmed
REASON: The cited range is exactly the `_apply_transaction` function which handles transaction application including duplicate check, validation, dupe-DB insertion, RC reset, operation iteration, and pre/post notifications.
SUGGESTED_FIX: none

### [25/166] libraries/chain/database.cpp:2722-2746 — Operation dispatch
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2722-2746
STATUS: confirmed
REASON: The cited lines show database_impl::apply_operation which dispatches operations via _evaluator_registry.get_evaluator(op).apply(op) with pre/post notifications and RC handling, directly supporting the "Operation dispatch" claim.
SUGGESTED_FIX: none

### [26/166] libraries/chain/database.cpp:2956-3064 — LIB calculation
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2956-3064
STATUS: confirmed
REASON: Lines 2956-3064 contain the complete `database::update_last_irreversible_block` function implementing LIB calculation, including pre-voting fallback (HIVE_MAX_WITNESSES offset), post-voting witness-schedule-based threshold using HIVE_IRREVERSIBLE_THRESHOLD, and fork-switch handling.
SUGGESTED_FIX: none

### [27/166] libraries/chain/database.cpp:2899-2954 — Fast confirm processing
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2899-2954
STATUS: confirmed
REASON: The cited range contains the `process_fast_confirm_transaction` function, which implements fast-confirm processing including HF26 assertion, witness schedule validation, deduplication by block number, and irreversibility update.
SUGGESTED_FIX: none

### [28/166] libraries/chain/database.cpp:3066-3097 — Irreversibility migration
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:3066-3097
STATUS: confirmed
REASON: The cited lines contain the `migrate_irreversible_state` function which performs the irreversibility migration by storing the block, committing undo state, and notifying irreversible blocks.
SUGGESTED_FIX: none

### [29/166] libraries/chain/database.cpp:2789-2841 — Participation tracking
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2789-2841
STATUS: confirmed
REASON: The cited range contains the participation tracking logic, including updates to dgp.participation_count and dgp.recent_slots_filled at lines 2820-2822.
SUGGESTED_FIX: none

### [30/166] libraries/chain/database.cpp:2843-2868 — HBD print rate / virtual supply
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2843-2868
STATUS: confirmed
REASON: The excerpt shows `calculate_HBD_percent()` (lines 2843-2866) computing HBD's share of virtual_supply as the print rate, with HF24 treasury exclusion and HF21 rounding, and line 2868 begins `update_virtual_supply()`, directly supporting the HBD print rate / virtual supply claim.
SUGGESTED_FIX: none

### [31/166] libraries/chain/database.cpp:1704 — Inflation distribution
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:1704
STATUS: confirmed
REASON: Line 1704 is the definition of `database::process_funds()`, with the preceding comment confirming it pays out vesting and reward shares every block — the inflation distribution entry point.
SUGGESTED_FIX: none

### [32/166] libraries/chain/database.cpp:61-71 — next_hf_time()
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:61-71
STATUS: confirmed
REASON: The source excerpt shows `next_hf_time()` defined exactly at lines 61-71, matching the citation precisely.
SUGGESTED_FIX: none

### [33/166] libraries/chain/database.cpp:1422-1540 — Account clearing/restoration
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:1422-1540
STATUS: confirmed
REASON: The cited range contains `restore_accounts` (1422-1459), `clear_accounts` (1461-1472), and the beginning of `clear_account` (1474-1540+), directly implementing account clearing and restoration.
SUGGESTED_FIX: none

### [34/166] libraries/chain/hive_evaluator_transfer.cpp:75-957 — Transfer evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:75-957
STATUS: confirmed
REASON: The cited range spans the bodies of all transfer-related evaluators (escrow_transfer, transfer, transfer_to_vesting, withdraw_vesting, convert, collateralized_convert, limit_order_*, transfer_to_savings, transfer_from_savings, claim_reward_balance, delegate_vesting_shares, recurrent_transfer), matching the "Transfer evaluators" claim.
SUGGESTED_FIX: none

### [35/166] libraries/chain/hive_evaluator_account.cpp:130-657 — Account evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_account.cpp:130-657
STATUS: confirmed
REASON: The cited range contains the account evaluator implementations (create, update, update2, claim, create_claimed, request_recovery, recover, change_recovery, decline_voting_rights, reset, set_reset), directly matching the "Account evaluators" claim.
SUGGESTED_FIX: none

### [36/166] libraries/chain/hive_evaluator_social.cpp:55-864 — Social evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_social.cpp:55-864
STATUS: confirmed
REASON: The cited range spans delete_comment_evaluator, comment_options_evaluator, comment_evaluator, pre_hf20_vote_evaluator, hf20_vote_evaluator, and vote_evaluator — all social evaluators in the file as the claim asserts.
SUGGESTED_FIX: none

### [37/166] libraries/chain/hive_evaluator.cpp:62-628 — Witness/custom/pow evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator.cpp:62-628
STATUS: confirmed
REASON: Lines 62-628 contain the witness evaluators (witness_update, witness_set_properties, account_witness_proxy, account_witness_vote, feed_publish, witness_block_approve), custom evaluators (custom, custom_json, custom_binary), and pow evaluators (pow, pow2), matching the claim verbatim.
SUGGESTED_FIX: none

### [38/166] libraries/chain/dhf_evaluator.cpp:32-252 — DHF evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/dhf_evaluator.cpp:32-252
STATUS: confirmed
REASON: The cited range spans the four DHF evaluators (create_proposal at line 32, update_proposal at 103, update_proposal_votes at 155, remove_proposal at 213, ending at line 252), directly supporting the "DHF evaluators" claim.
SUGGESTED_FIX: none

### [39/166] libraries/chain/database_comment.cpp:129-379 — Comment cashout/curation
Source: `00-consolidated.md`

CITATION: libraries/chain/database_comment.cpp:129-379
STATUS: confirmed
REASON: The cited range covers `pay_curators` (line 129) and `cashout_comment_helper` (line 197) and ends at the start of `process_comment_cashout` (line 379), directly implementing comment cashout and curation reward distribution.
SUGGESTED_FIX: none

### [40/166] libraries/chain/witness_schedule.cpp:152-396 — Witness scheduling
Source: `00-consolidated.md`

CITATION: libraries/chain/witness_schedule.cpp:152-396
STATUS: confirmed
REASON: Lines 152-396 contain the `update_witness_schedule4` function which implements witness scheduling (selecting voted/miner/timeshare witnesses, updating virtual schedule, shuffling, and writing the schedule object).
SUGGESTED_FIX: none

### [41/166] libraries/chain/database_witness.cpp:284-306 — Witness missed blocks
Source: `00-consolidated.md`

CITATION: libraries/chain/database_witness.cpp:284-306
STATUS: confirmed
REASON: The cited lines define `update_witness_missed_blocks`, which iterates over scheduled witnesses, increments `total_missed`, and pushes `producer_missed_operation` for each missed slot, directly supporting the "witness missed blocks" claim.
SUGGESTED_FIX: none

### [42/166] libraries/chain/fork_database.cpp:20-330 — Fork database
Source: `00-consolidated.md`

CITATION: libraries/chain/fork_database.cpp:20-330
STATUS: confirmed
REASON: The cited file and line range contains the fork_database class implementation (push_block, pop_block, fetch_branch_from, head tracking, unlinked block handling), directly supporting the "Fork database" claim.
SUGGESTED_FIX: none

### [43/166] libraries/chain/sync_block_writer.cpp:162-367 — Fork switching
Source: `00-consolidated.md`

CITATION: libraries/chain/sync_block_writer.cpp:162-367
STATUS: confirmed
REASON: Line 162 begins the `switch_forks` function which implements fork switching (popping old branch, pushing new branch, handling failure rollback), and the range extends through related LIB-determination logic that supports the broader fork-switching topic.
SUGGESTED_FIX: none

### [44/166] libraries/chain/block_log.cpp:338-515 — Block log read/write
Source: `00-consolidated.md`

CITATION: libraries/chain/block_log.cpp:338-515
STATUS: confirmed
REASON: The excerpt shows block_log read/write methods (append_raw, multi_append_raw, read_raw_block_data_by_num, append, flush, read_block_id_by_num, read_block_by_num) spanning the cited line range, directly supporting the "Block log read/write" claim.
SUGGESTED_FIX: none

### [45/166] libraries/chain/block_log_artifacts.cpp:46-166 — Block log artifacts
Source: `00-consolidated.md`

CITATION: libraries/chain/block_log_artifacts.cpp:46-166
STATUS: confirmed
REASON: The cited range contains the `artifact_file_header` and `artifact_file_chunk` struct definitions that constitute the on-disk format of block log artifacts, directly supporting the claim.
SUGGESTED_FIX: none

### [46/166] libraries/chain/include/hive/chain/hive_object_types.hpp:47-89 — Object type enum (39 IDs)
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/hive_object_types.hpp:47-89
STATUS: confirmed
REASON: Counting the enum entries in the cited range yields exactly 39 object type IDs (33 core + 6 RC), matching the claim.
SUGGESTED_FIX: none

### [47/166] libraries/chain/include/hive/chain/detail/state/account_object.hpp:339 — account_authority_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/account_object.hpp:339
STATUS: confirmed
REASON: Line 339 contains the class declaration for `account_authority_object`, directly supporting the claim.
SUGGESTED_FIX: none

### [48/166] libraries/chain/include/hive/chain/detail/state/comment_object.hpp:372 — comment_vote_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/comment_object.hpp:372
STATUS: confirmed
REASON: Line 372 contains the class declaration `class comment_vote_object`, directly supporting the claim referencing this object.
SUGGESTED_FIX: none

### [49/166] libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:69 — witness_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:69
STATUS: confirmed
REASON: Line 69 defines `class witness_object`, directly matching the claim.
SUGGESTED_FIX: none

### [50/166] libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:183 — witness_schedule_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:183
STATUS: confirmed
REASON: Line 183 contains the class declaration for witness_schedule_object, directly supporting the claim.
SUGGESTED_FIX: none

### [51/166] libraries/chain/rc/rc_utility.cpp:547-581 — Non-consensus enforcement
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:547-581
STATUS: confirmed
REASON: The excerpt shows RC exhaustion throws `not_enough_rc_exception` only when `db.is_in_control() || db.is_reapplying_one_tx()` (mempool path), while the `is_processing_block()` branch merely logs and accepts the transaction — directly supporting non-consensus enforcement.
SUGGESTED_FIX: none

### [52/166] libraries/chain/rc/rc_utility.cpp:799-831 — Mana deduction (finalize_tx)
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:799-831
STATUS: confirmed
REASON: The cited range shows `resource_credits::finalize_transaction` computing total RC cost and deducting mana via `use_account_rcs(total_cost)` at line 818, directly supporting the "Mana deduction (finalize_tx)" claim.
SUGGESTED_FIX: none

### [53/166] libraries/chain/rc/rc_utility.cpp:26-110 — RC delegation mechanics
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:26-110
STATUS: confirmed
REASON: Lines 26-110 contain the complete delegate_rc_evaluator::do_apply implementation covering HF26 gating, minimum delegation check, create/update/delete delegation logic, manabar regeneration, and the delegable RC assertion—the core RC delegation mechanics.
SUGGESTED_FIX: none

### [54/166] libraries/chain/rc/rc_utility.cpp:401-443 — Delegation overflow
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:401-443
STATUS: confirmed
REASON: Lines 403-443 implement the RC delegation overflow logic — computing `delegation_overflow`, calling `remove_delegations`, and creating/modifying `rc_expired_delegation_object` to track unfinished removals — directly supporting the "Delegation overflow" claim.
SUGGESTED_FIX: none

### [55/166] libraries/chain/rc/rc_utility.cpp:505-537 — Flood surcharge
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:505-537
STATUS: confirmed
REASON: The excerpt at lines 505-537 directly implements the flood surcharge logic, computing `surcharge` from `(blocks_in_mempool - flood_level) * flood_surcharge` when mempool exceeds the flood level.
SUGGESTED_FIX: none

### [56/166] libraries/chain/rc/resource_count.cpp:136-631 — Resource counting
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_count.cpp:136-631
STATUS: confirmed
REASON: The cited range contains the resource counting machinery — `handle_operation_discount` (differential usage), the `count_operation_visitor` per-op visitor tallying state_bytes/execution_time/market/new_account counts, and the `count_resources` function that aggregates them into the per-resource result — directly supporting the "Resource counting" claim.
SUGGESTED_FIX: none

### [57/166] libraries/chain/rc/resource_sizes.cpp:45-165 — State byte sizes
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_sizes.cpp:45-165
STATUS: confirmed
REASON: Lines 45-165 contain the `state_object_size_info` constructor defining TEMPORARY/LASTING/PERSISTENT state byte units and all per-operation state byte sizes, directly supporting the claim.
SUGGESTED_FIX: none

### [58/166] libraries/chain/rc/resource_sizes.cpp:167-242 — Execution time benchmarks
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_sizes.cpp:167-242
STATUS: confirmed
REASON: Lines 167-242 contain the `operation_exec_info` constructor initializing execution time benchmarks for all operations (e.g., account_create_time, vote_time, transfer_time), directly supporting the claim.
SUGGESTED_FIX: none

### [59/166] libraries/chain/rc/rc_curve.cpp:32-98 — Price curve computation
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_curve.cpp:32-98
STATUS: confirmed
REASON: Lines 32-98 contain the `generate_rc_curve_params` function which computes the RC price curve parameters (coeff_a, coeff_b, shift) from dynamics and curve-gen inputs, matching the claim verbatim.
SUGGESTED_FIX: none

### [60/166] libraries/chain/util/rd.cpp:23-118 — Pool dynamics (decay)
Source: `00-consolidated.md`

CITATION: libraries/chain/util/rd.cpp:23-118
STATUS: confirmed
REASON: The cited range covers `rd_compute_pool_decay`, `rd_apply`, and `rd_setup_dynamics_params`, which together implement the pool decay dynamics (decay formula, budget/decay/max_pool application, and equilibrium pool sizing).
SUGGESTED_FIX: none

### [61/166] libraries/chain/include/hive/chain/util/manabar.hpp:42-141 — Manabar struct
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/util/manabar.hpp:42-141
STATUS: drifted
REASON: The cited range 42-141 starts mid-method (inside regenerate_mana) rather than at the struct definition, and extends past the struct's closing brace at line 102 into the separate update_manabar utility function (lines 104-141).
SUGGESTED_FIX: Narrow the citation to the actual struct bounds — likely something like manabar.hpp:~25-102 (start of struct through its closing `};`); flag for manual review to confirm the struct's opening line.

### [62/166] libraries/chain/util/dhf_processor.cpp:145-325 — DHF payment processing
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145-325
STATUS: confirmed
REASON: The cited range covers the core DHF payment processing functions — calculate_maintenance_budget, transfer_payments, make_payments, record_funding, and run — directly supporting the claim.
SUGGESTED_FIX: none

### [63/166] libraries/chain/util/dhf_processor.cpp:145 — DHF budget calculation
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145
STATUS: confirmed
REASON: Line 145 is the signature of `dhf_processor::calculate_maintenance_budget`, which directly implements DHF budget calculation by drawing from the treasury fund.
SUGGESTED_FIX: none

### [64/166] libraries/chain/util/dhf_processor.cpp:325 — DHF HIVE->HBD conversion
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:325
STATUS: confirmed
REASON: Line 325 is the entry point of `dhf_processor::convert_funds`, the function that handles the DHF's HIVE->HBD conversion during daily maintenance.
SUGGESTED_FIX: none

### [65/166] libraries/protocol/include/hive/protocol/config.hpp:56 — HIVE_BLOCK_INTERVAL = 3
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56
STATUS: confirmed
REASON: Line 56 contains `#define HIVE_BLOCK_INTERVAL                   3`, matching the claim verbatim.
SUGGESTED_FIX: none

### [66/166] libraries/protocol/include/hive/protocol/config.hpp:56-207 — Block, cashout, recovery, feed timings
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56-207
STATUS: confirmed
REASON: The cited range contains block timings (lines 56-60), cashout windows (73-77, 155-159), owner/account recovery periods (86-89, 167-170), and feed interval/history/age constants (108-112, 189-193), matching all four categories in the claim.
SUGGESTED_FIX: none

### [67/166] libraries/protocol/include/hive/protocol/config.hpp:215-346 — Inflation, rewards, HBD limits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:215-346
STATUS: confirmed
REASON: The cited range contains inflation constants (lines 257-259), reward percentages and APR constants (lines 260-265, 282-294, 331-335), and HBD limit constants (lines 337-346), directly supporting the claim.
SUGGESTED_FIX: none

### [68/166] libraries/protocol/include/hive/protocol/config.hpp:348-399 — Transaction, block, name, URL sizes and miscellaneous limits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:348-399
STATUS: confirmed
REASON: The cited range contains account name lengths (348-349), permlink lengths (351-352), witness URL length (353), transaction size limits (360, 364), block size limits (365-367), URL length (379), and other miscellaneous limits as the claim describes.
SUGGESTED_FIX: none

### [69/166] libraries/protocol/include/hive/protocol/config.hpp:441-458 — null, temp, miners, proxy-to-self, root-post-parent, plus OBSOLETE/NEW treasury constants (treasury name resolved via `database::get_treasury_name()`)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:441-458
STATUS: confirmed
REASON: The cited lines define HIVE_MINER_ACCOUNT, HIVE_NULL_ACCOUNT, HIVE_TEMP_ACCOUNT, HIVE_PROXY_TO_SELF_ACCOUNT, HIVE_ROOT_POST_PARENT, OBSOLETE_TREASURY_ACCOUNT, and NEW_HIVE_TREASURY_ACCOUNT, with the comment explicitly directing use of database::get_treasury_name() for treasury resolution.
SUGGESTED_FIX: none

### [70/166] libraries/protocol/include/hive/protocol/config.hpp:460-469 — Proposal system
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:460-469
STATUS: confirmed
REASON: Lines 460-469 contain the "HIVE PROPOSAL SYSTEM support" section with proposal-related constants (treasury fee, subject length, max IDs, fee increase parameters, conversion rate), directly supporting the proposal system claim.
SUGGESTED_FIX: none

### [71/166] libraries/protocol/include/hive/protocol/config.hpp:479-494 — Resource credits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:479-494
STATUS: confirmed
REASON: Lines 479-494 contain the "HIVE RC related constants" block defining RC regen time, bucket time/count, stats report frequency, historical account creation adjustment, and max accounts per delegation op, supporting the "Resource credits" claim.
SUGGESTED_FIX: none

### [72/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-32 — Precision bits, shift, NAI encoding
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-32
STATUS: confirmed
REASON: The cited range defines HIVE_ASSET_SYMBOL_PRECISION_BITS (line 9), HIVE_NAI_SHIFT (line 11), and the NAI-encoded asset numbers for HBD/HIVE/VESTS (lines 30-32), directly supporting the claim.
SUGGESTED_FIX: none

### [73/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:20-22 — HBD=3, HIVE=3, VESTS=6
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:20-22
STATUS: confirmed
REASON: Lines 20-22 define HIVE_PRECISION_HBD=3, HIVE_PRECISION_HIVE=3, HIVE_PRECISION_VESTS=6, exactly matching the claim.
SUGGESTED_FIX: none

### [74/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:36-53 — STEEM/SBD/TESTS/TBD/HIVE/HBD/VESTS
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:36-53
STATUS: confirmed
REASON: All seven symbols (STEEM, SBD, TESTS, TBD, HIVE, HBD, VESTS) are defined verbatim in the cited range via the mainnet/testnet #ifdef branches.
SUGGESTED_FIX: none

### [75/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216 — Legacy vs NAI pack/unpack
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216
STATUS: confirmed
REASON: The excerpt shows both pack() (lines 157-187) branching on legacy_space/pack_type::legacy to emit OBSOLETE/OBD/VESTS legacy symbols vs. raw asset_num, and unpack() (lines 189-216) switching on the legacy 4-byte sentinels vs. NAI asset_num, directly supporting the legacy-vs-NAI pack/unpack claim.
SUGGESTED_FIX: none

### [76/166] libraries/protocol/include/hive/protocol/asset.hpp:21-96 — Amount + symbol with operator overloads
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:21-96
STATUS: confirmed
REASON: The cited range defines the `asset` struct with `amount` and `symbol` fields plus operator overloads for +=, -=, unary -, ==, <, <=, !=, >, >=, binary -, and binary +, directly supporting the claim.
SUGGESTED_FIX: none

### [77/166] libraries/protocol/include/hive/protocol/asset.hpp:139-186 — Base/quote pair
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:139-186
STATUS: confirmed
REASON: The cited lines define `struct price` with `asset base` and `asset quote` members, directly supporting the base/quote pair claim.
SUGGESTED_FIX: none

### [78/166] libraries/protocol/include/hive/protocol/asset.hpp:218-261 — Typed thin wrappers
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:218-261
STATUS: confirmed
REASON: The cited lines define the `tiny_asset` template struct parameterized by `_SYMBOL`, which is a typed thin wrapper around `share_type amount` enforcing a fixed asset symbol via compile-time templating.
SUGGESTED_FIX: none

### [79/166] libraries/protocol/include/hive/protocol/asset.hpp:268-322 — Typed price wrappers
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:268-322
STATUS: confirmed
REASON: The cited lines define the `tiny_price` class template parameterized by base/quote symbols, directly supporting the claim of typed price wrappers.
SUGGESTED_FIX: none

### [80/166] libraries/protocol/asset.cpp:80-126 — 8-digit Damm algorithm
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:80-126
STATUS: confirmed
REASON: The source excerpt at lines 80-126 implements `damm_checksum_8digit(uint32_t value)` with an explicit comment referencing the Damm algorithm and processes 8 decimal digits (d0-d7) via the standard Damm lookup table, directly supporting the claim.
SUGGESTED_FIX: none

### [81/166] libraries/protocol/asset.cpp:261-283 — NAI range + control bit checks
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:261-283
STATUS: confirmed
REASON: Lines 274-276 explicitly validate NAI range (SMT_MIN_NAI <= nai_data_digits <= SMT_MAX_NAI) and the control bit (nai_1bit == SMT_ASSET_NUM_CONTROL_MASK), directly supporting the claim.
SUGGESTED_FIX: none

### [82/166] libraries/protocol/asset.cpp:310-325 — uint128 cross-multiplication
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:310-325
STATUS: confirmed
REASON: The excerpt shows `uint128_t result` being multiplied by one side of the price and divided by the other (lines 316 and 322), which is exactly the uint128 cross-multiplication pattern claimed.
SUGGESTED_FIX: none

### [83/166] libraries/protocol/asset.cpp:337-340 — Returns `HIVE_MAX_SATOSHIS
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:337-340
STATUS: confirmed
REASON: The source excerpt at lines 337-340 shows `price::max_satoshis()` returning `HIVE_MAX_SATOSHIS`, directly supporting the claim verbatim.
SUGGESTED_FIX: none

### [84/166] libraries/protocol/include/hive/protocol/types.hpp:66-81 — All fundamental typedefs
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:66-81
STATUS: confirmed
REASON: Lines 66-81 contain the protocol namespace opening followed by all fundamental typedefs (private_key_type, chain_id_type, account_name_type, block_id_type, checksum_type, transaction_id_type, digest_type, signature_type, share_type, ushare_type, weight_type, contribution_id_type, custom_id_type), directly supporting the claim.
SUGGESTED_FIX: none

### [85/166] libraries/protocol/include/hive/protocol/types.hpp:83-103 — Key data + base58 encoding
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:83-103
STATUS: confirmed
REASON: The public_key_type struct at lines 83-103 contains fc::ecc::public_key_data key_data plus constructor and operator std::string for base58 string conversion, supporting the "Key data + base58 encoding" claim.
SUGGESTED_FIX: none

### [86/166] libraries/protocol/include/hive/protocol/authority.hpp:7-55 — Threshold + key/account maps
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/authority.hpp:7-55
STATUS: confirmed
REASON: The authority struct at lines 7-55 explicitly defines `weight_threshold` (line 52), `account_auths` as `account_authority_map` (line 53), and `key_auths` as `key_authority_map` (line 54), directly matching the "threshold + key/account maps" claim.
SUGGESTED_FIX: none

### [87/166] libraries/protocol/authority.cpp:58-122 — RFC 1035 with Hive rules
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/authority.cpp:58-122
STATUS: confirmed
REASON: The source implements DNS-label-style validation (dot-separated segments, start with letter, end with letter/digit, middle allows letter/digit/hyphen) which matches RFC 1035 with Hive-specific additions (lowercase-only, 3-char minimum per segment, Hive length bounds).
SUGGESTED_FIX: none

### [88/166] libraries/protocol/include/hive/protocol/block_header.hpp:15-26 — previous, timestamp, witness, merkle root
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/block_header.hpp:15-26
STATUS: confirmed
REASON: The block_header struct at lines 15-26 contains exactly the four fields claimed: previous (block_id_type), timestamp (fc::time_point_sec), witness (string), and transaction_merkle_root (checksum_type).
SUGGESTED_FIX: none

### [89/166] libraries/protocol/block.cpp:13-16 — endian_reverse_u32(id._hash[0])
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/block.cpp:13-16
STATUS: confirmed
REASON: The cited lines show `num_from_id` returning `fc::endian_reverse_u32(id._hash[0])`, which matches the claim verbatim.
SUGGESTED_FIX: none

### [90/166] libraries/protocol/block.cpp:19-46 — Pairwise hashing
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/block.cpp:19-46
STATUS: confirmed
REASON: The excerpt shows `legacy_calculate_merkle_root()` explicitly hashing IDs in pairs via `digest_type::hash(std::make_pair(ids[i], ids[i+1]))` with a comment "hash ID's in pairs", directly supporting the pairwise hashing claim.
SUGGESTED_FIX: none

### [91/166] libraries/protocol/include/hive/protocol/transaction.hpp:12-53 — ref_block, expiration, operations
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-53
STATUS: confirmed
REASON: The transaction struct at lines 12-53 contains ref_block_num/ref_block_prefix (line 14-15), expiration (line 17), and operations (line 19), matching the claim.
SUGGESTED_FIX: none

### [92/166] libraries/protocol/transaction.cpp:84-88 — Block number + prefix extraction
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:84-88
STATUS: confirmed
REASON: Lines 84-88 define `set_reference_block` which extracts `ref_block_num` (via endian-reversed first hash word) and `ref_block_prefix` (second hash word) from a block_id, exactly matching the claim about block number + prefix extraction.
SUGGESTED_FIX: none

### [93/166] libraries/protocol/transaction.cpp:58-64 — SHA-256 truncated to 20 bytes
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:58-64
STATUS: confirmed
REASON: The cited lines show `transaction::id()` computing a digest and using `memcpy` with `std::min(sizeof(result), sizeof(h))` to truncate the hash into the smaller `transaction_id_type`, which matches the truncation mechanism described in the claim.
SUGGESTED_FIX: none

### [94/166] libraries/protocol/transaction.cpp:29-38 — chain_id + transaction -> SHA-256
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:29-38
STATUS: confirmed
REASON: The sig_digest function packs chain_id followed by the transaction into a digest_type encoder (FC's SHA-256), exactly matching the claim.
SUGGESTED_FIX: none

### [95/166] libraries/protocol/transaction.cpp:40-56 — operations.size() > 0, per-op validate
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:40-56
STATUS: confirmed
REASON: Lines 40-56 show transaction::validate() asserting operations.size() > 0 and calling operation_validate(op) for each operation, matching the claim verbatim.
SUGGESTED_FIX: none

### [96/166] libraries/protocol/include/hive/protocol/version.hpp:15-77 — Major.HF.release in uint32
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:15-77
STATUS: confirmed
REASON: The struct stores `uint32_t v_num` (line 34) packed as major (bits 24-31), hardfork/minor (bits 16-23), and release/rev (bits 0-15) per the masks at lines 30-32, matching the constructor signature `version(uint8_t m, uint8_t h, uint16_t r)` at line 18.
SUGGESTED_FIX: none

### [97/166] libraries/protocol/include/hive/protocol/version.hpp:79-102 — Masks release bits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:79-102
STATUS: confirmed
REASON: The hardfork_version struct consistently applies the 0xFFFF0000 mask in its constructor, assignment, and comparison operators, which zeros out the lower 16 bits (release/patch component) and retains only the major/hardfork bits, directly supporting the "Masks release bits" claim.
SUGGESTED_FIX: none

### [98/166] libraries/protocol/include/hive/protocol/version.hpp:104-111 — HF version + activation time
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:104-111
STATUS: confirmed
REASON: The cited lines define `hardfork_version_vote` struct with exactly two fields — `hf_version` (hardfork_version) and `hf_time` (time_point_sec) — which directly supports the "HF version + activation time" claim.
SUGGESTED_FIX: none

### [99/166] libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30 — All 28 HF activation blocks
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30
STATUS: confirmed
REASON: Lines 3-30 contain exactly 28 HIVE_HARDFORK_*_BLOCK macros (HF 0_1 through 1_28), matching the claim verbatim.
SUGGESTED_FIX: none

### [100/166] libraries/protocol/hardfork.d/0-preamble.hf:16-19 — HIVE_NUM_HARDFORKS = 28
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/hardfork.d/0-preamble.hf:16-19
STATUS: confirmed
REASON: Both the alternate-chain (line 16) and mainnet (line 19) branches define HIVE_NUM_HARDFORKS as 28, matching the claim verbatim.
SUGGESTED_FIX: none

### [101/166] libraries/protocol/include/hive/protocol/config.hpp:137-143 — Mainnet "beeab0de...", testnet, mirrornet
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:137-143
STATUS: confirmed
REASON: Mainnet chain ID "beeab0de..." appears verbatim at line 142 and mirrornet chain ID is visible at lines 134-137, supporting the claim about distinct chain IDs across mainnet/testnet/mirrornet (testnet would be in the preceding #if branch not shown but implied by the #else structure).
SUGGESTED_FIX: none

### [102/166] libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23 — Balance-seconds / year * rate
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23
STATUS: confirmed
REASON: The source computes `hbd_seconds / HIVE_SECONDS_PER_YEAR * hbd_interest_rate` (then scales by HIVE_100_PERCENT), which is exactly balance-seconds / year * rate.
SUGGESTED_FIX: none

### [103/166] libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26 — estimate_hive_collateral()` formula (uses ratio + fee constants from `config.hpp`)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26
STATUS: confirmed
REASON: The source excerpt shows `estimate_hive_collateral()` defined at lines 8-26 using `HIVE_COLLATERALIZED_CONVERSION_FEE`, `HIVE_CONVERSION_COLLATERAL_RATIO`, and `HIVE_100_PERCENT` constants from config, matching the claim verbatim.
SUGGESTED_FIX: none

### [104/166] libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285 — All configurable defaults
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285
STATUS: confirmed
REASON: Lines 27-285 contain the complete `configuration` class definition with all configurable default values (vote windows, cashout, feed, savings, governance, proposals, witness thresholds, initial supplies, etc.) and their getters/setters, supporting the claim verbatim.
SUGGESTED_FIX: none

### [105/166] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Required authorities interface
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: The excerpt shows base_operation defining the get_required_*_authorities methods (active, posting, owner, witness_signatures) plus the generic get_required_authorities, which directly constitutes the required authorities interface claimed.
SUGGESTED_FIX: none

### [106/166] libraries/protocol/include/hive/protocol/operations.hpp:15-125 — Complete operation list with IDs
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/operations.hpp:15-125
STATUS: confirmed
REASON: The cited range contains the complete `fc::static_variant` operation typedef with all 50 regular operations (IDs 0-49) and 43 virtual operations (last_regular + 1 through last_regular + 43), each annotated with its ID as a comment.
SUGGESTED_FIX: none

### [107/166] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Authority method signatures
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: Lines 15-19 contain the five authority method signatures (get_required_authorities, get_required_active_authorities, get_required_posting_authorities, get_required_owner_authorities, get_required_witness_signatures) on base_operation, exactly matching the cited claim.
SUGGESTED_FIX: none

### [108/166] libraries/protocol/include/hive/protocol/types.hpp:151-161 — recurrent_transfer_pair_id, extensions
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:151-161
STATUS: confirmed
REASON: The cited lines define `recurrent_transfer_pair_id` struct and the `recurrent_transfer_extensions_type` (flat_set of static_variant including `recurrent_transfer_pair_id`), directly supporting the claim about the pair_id and extensions.
SUGGESTED_FIX: none

### [109/166] libraries/chain/database.cpp:2183-2369 — _apply_block()` :2183-2369
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2183-2369
STATUS: confirmed
REASON: The function `database::_apply_block()` begins at line 2183 and ends at line 2369 as cited, matching the claim exactly.
SUGGESTED_FIX: none

### [110/166] libraries/chain/database.cpp:2757-2779 — `validate_block_header()` :2757-2779
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2757-2779
STATUS: confirmed
REASON: The function `database::validate_block_header()` is defined exactly at lines 2757-2779 as cited, performing header validation (previous hash, timestamp, witness signing key, and schedule slot checks).
SUGGESTED_FIX: none

### [111/166] libraries/chain/database.cpp:2644-2702 — _apply_transaction()` :2644-2702
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2644-2702
STATUS: confirmed
REASON: The source excerpt shows `database::_apply_transaction()` defined exactly at lines 2644-2702, matching the cited range verbatim.
SUGGESTED_FIX: none

### [112/166] libraries/chain/database.cpp:2521-2642 — `validate_transaction()` :2521-2642
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2521-2642
STATUS: confirmed
REASON: The function `database::validate_transaction()` begins at line 2521 and its closing brace is at line 2642, exactly as cited.
SUGGESTED_FIX: none

### [113/166] libraries/chain/database.cpp:2722-2746 — apply_operation()` :2722-2746
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2722-2746
STATUS: confirmed
REASON: The source excerpt at lines 2722-2746 shows the complete definition of `database_impl::apply_operation()`, exactly matching the citation.
SUGGESTED_FIX: none

### [114/166] libraries/chain/witness_schedule.cpp:152-396 — update_witness_schedule4()` :152-396
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:152-396
STATUS: confirmed
REASON: The function `update_witness_schedule4()` starts at line 152 and ends at line 396 with the closing `FC_CAPTURE_AND_RETHROW() }` as cited.
SUGGESTED_FIX: none

### [115/166] libraries/chain/witness_schedule.cpp:372-388 — shuffle :372-388
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:372-388
STATUS: confirmed
REASON: Lines 372-388 contain exactly the witness shuffle logic (xorshift PRNG seeded from head_block_time, Fisher-Yates-style std::swap loop over current_shuffled_witnesses), matching the "shuffle" claim verbatim.
SUGGESTED_FIX: none

### [116/166] libraries/chain/database.cpp:904-910 — get_scheduled_witness()` :904-910
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:904-910
STATUS: confirmed
REASON: The source at lines 904-910 defines `database::get_scheduled_witness( uint32_t slot_num )`, exactly matching the cited function and line range.
SUGGESTED_FIX: none

### [117/166] libraries/chain/database.cpp:937-943 — `get_slot_at_time()` :937-943
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:937-943
STATUS: confirmed
REASON: Lines 937-943 contain the definition of `database::get_slot_at_time()`, exactly matching the claim.
SUGGESTED_FIX: none

### [118/166] libraries/chain/database_witness.cpp:284-306 — update_witness_missed_blocks()` :284-306
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database_witness.cpp:284-306
STATUS: confirmed
REASON: The source excerpt at lines 284-306 shows the `update_witness_missed_blocks()` function definition, matching the claim verbatim.
SUGGESTED_FIX: none

### [119/166] libraries/chain/database.cpp:2789-2841 — update_global_dynamic_data()` :2789-2841
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2789-2841
STATUS: confirmed
REASON: The function `database::update_global_dynamic_data()` begins at line 2789 and ends at line 2841 exactly as cited, updating dynamic global properties including head block number, timestamp, missed blocks tracking, and recent_slots_filled.
SUGGESTED_FIX: none

### [120/166] libraries/chain/database.cpp:531-535 — `witness_participation_rate()` :531-535
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:531-535
STATUS: confirmed
REASON: The source excerpt at lines 531-535 defines `database::witness_participation_rate()` exactly as cited, computing the rate from `dpo.recent_slots_filled`.
SUGGESTED_FIX: none

### [121/166] libraries/chain/fork_database.cpp:73-99 — _push_block()` :73-99
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:73-99
STATUS: confirmed
REASON: The source excerpt shows `fork_database::_push_block()` defined exactly at lines 73-99, matching the citation.
SUGGESTED_FIX: none

### [122/166] libraries/chain/fork_database.cpp:20-28 — `pop_block()` :20-28
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:20-28
STATUS: confirmed
REASON: Lines 20-28 contain the `fork_database::pop_block()` function definition as cited.
SUGGESTED_FIX: none

### [123/166] libraries/chain/fork_database.cpp:290-330 — `fetch_branch_from()` :290-330
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:290-330
STATUS: confirmed
REASON: The cited lines contain the `fetch_branch_from()` function definition implementing branch traversal back to a common ancestor, matching the claim.
SUGGESTED_FIX: none

### [124/166] libraries/chain/sync_block_writer.cpp:162-264 — switch_forks()` :162-264
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:162-264
STATUS: confirmed
REASON: Lines 162-264 exactly bound the `switch_forks()` function definition, with line 162 starting the signature and line 264 closing the function body with the `// switch_forks` comment.
SUGGESTED_FIX: none

### [125/166] libraries/chain/database.cpp:2956-3064 — update_last_irreversible_block()` :2956-3064
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2956-3064
STATUS: confirmed
REASON: The function `database::update_last_irreversible_block()` is defined exactly at lines 2956-3064 as cited, matching the claim verbatim.
SUGGESTED_FIX: none

### [126/166] libraries/chain/sync_block_writer.cpp:266-367 — find_new_last_irreversible_block()` :266-367
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:266-367
STATUS: confirmed
REASON: The function `find_new_last_irreversible_block()` is defined exactly at lines 266-367 as cited, with the closing brace and comment marker on line 367.
SUGGESTED_FIX: none

### [127/166] libraries/chain/database.cpp:2899-2954 — process_fast_confirm_transaction()` :2899-2954
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2899-2954
STATUS: confirmed
REASON: The function `database::process_fast_confirm_transaction()` is defined exactly at lines 2899-2954 as cited, matching the claim verbatim.
SUGGESTED_FIX: none

### [128/166] libraries/chain/database.cpp:3066-3097 — migrate_irreversible_state()` :3066-3097
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:3066-3097
STATUS: confirmed
REASON: The source excerpt at lines 3066-3097 contains the `database::migrate_irreversible_state()` function definition exactly as cited.
SUGGESTED_FIX: none

### [129/166] libraries/chain/block_log.cpp:338-366 — append_raw()` :338-366
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:338-366
STATUS: confirmed
REASON: Lines 338-366 contain both `append_raw()` overloads (the 3-arg delegating variant at 338-342 and the main implementation at 344-366), matching the citation exactly.
SUGGESTED_FIX: none

### [130/166] libraries/chain/block_log.cpp:491-515 — read_block_by_num()` :491-515
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:491-515
STATUS: confirmed
REASON: Lines 491-515 contain the `read_block_by_num()` method definition exactly as referenced in the claim.
SUGGESTED_FIX: none

### [131/166] libraries/chain/block_log_artifacts.cpp:46-69 — header :46-69
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_artifacts.cpp:46-69
STATUS: confirmed
REASON: Lines 46-69 contain the `artifact_file_header` struct definition exactly as the claim references.
SUGGESTED_FIX: none

### [132/166] libraries/chain/block_log_artifacts.cpp:82-166 — chunk :82-166
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_artifacts.cpp:82-166
STATUS: confirmed
REASON: The cited range exactly spans the `artifact_file_chunk` struct definition; the documented bitfield layout (block_log_offset:48, dictionary_no:8, custom_dict_used:1, gap:6, is_compressed:1) and `stripped_block_id[2]` match the source, with the doc reasonably omitting the union wrapper and member functions.
SUGGESTED_FIX: none

### [133/166] libraries/plugins/witness/witness_plugin.cpp:369-380 — schedule_production_loop()` :369-380
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:369-380
STATUS: confirmed
REASON: The source excerpt shows `witness_plugin_impl::schedule_production_loop()` defined exactly at lines 369-380, matching the citation verbatim.
SUGGESTED_FIX: none

### [134/166] libraries/plugins/witness/witness_plugin.cpp:382-467 — `block_production_loop()` :382-467
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:382-467
STATUS: confirmed
REASON: The cited range 382-467 contains the complete `block_production_loop()` function definition for `witness_plugin_impl`, matching the claim exactly.
SUGGESTED_FIX: none

### [135/166] libraries/plugins/witness/block_producer.cpp:31-85 — _generate_block()` :31-85
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:31-85
STATUS: confirmed
REASON: The cited lines define the `_generate_block()` function with the expected signature and body covering slot validation, witness verification, transaction application, block assembly, and push.
SUGGESTED_FIX: none

### [136/166] libraries/plugins/witness/block_producer.cpp:111-216 — `apply_pending_transactions()` :111-216
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:111-216
STATUS: confirmed
REASON: The function `block_producer::apply_pending_transactions()` begins at line 111 and ends at line 216 in the cited file, matching the claim exactly.
SUGGESTED_FIX: none

### [137/166] libraries/chain/include/hive/chain/block_flow_control.hpp:135-146 — Phase enum :135-146
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/include/hive/chain/block_flow_control.hpp:135-146
STATUS: confirmed
REASON: The source at lines 135-146 contains the `phase` enum with all expected values (REQUEST, START, FORK_DB, FORK_APPLY, FORK_IGNORE, FORK_NORMAL, TXS_EXECUTED, APPLIED, END), matching the citation exactly.
SUGGESTED_FIX: none

### [138/166] libraries/chain/database.cpp:1704 — process_funds()` at line 1704
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:1704
STATUS: confirmed
REASON: Line 1704 contains the function definition `void database::process_funds()` exactly as cited.
SUGGESTED_FIX: none

### [139/166] libraries/chain/util/reward.cpp:34 — evaluate_reward_curve()` at line 34
Source: `07-economic-model.md`

CITATION: libraries/chain/util/reward.cpp:34
STATUS: confirmed
REASON: Line 34 contains the definition of `evaluate_reward_curve()` exactly as claimed.
SUGGESTED_FIX: none

### [140/166] libraries/chain/database_comment.cpp:379 — process_comment_cashout()` at line 379
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:379
STATUS: confirmed
REASON: Line 379 contains the function definition `void database::process_comment_cashout()`, which directly matches the cited claim.
SUGGESTED_FIX: none

### [141/166] libraries/chain/database_comment.cpp:129 — pay_curators()` at line 129
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:129
STATUS: confirmed
REASON: Line 129 contains the `pay_curators()` function definition exactly as claimed.
SUGGESTED_FIX: none

### [142/166] libraries/chain/database_comment.cpp:197 — cashout_comment_helper()` at line 197
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:197
STATUS: confirmed
REASON: Line 197 is the function signature of `database::cashout_comment_helper(...)`, matching the claim verbatim.
SUGGESTED_FIX: none

### [143/166] libraries/chain/database.cpp:949 — create_hbd()` at line 949
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:949
STATUS: confirmed
REASON: Line 949 is the function signature for `database::create_hbd()`, matching the claim verbatim.
SUGGESTED_FIX: none

### [144/166] libraries/chain/hive_evaluator_social.cpp:605 — hf20_vote_evaluator()` at line 605
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_social.cpp:605
STATUS: confirmed
REASON: Line 605 contains the function definition `void hf20_vote_evaluator( const vote_operation... o, database... _db )`, directly matching the claim.
SUGGESTED_FIX: none

### [145/166] libraries/chain/database.cpp:3186 — adjust_balance(HBD)` accrual logic at line 3186
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:3186
STATUS: confirmed
REASON: Line 3186 is the function signature of `database::adjust_balance` taking an `HBD_asset` delta, which is the HBD-specific overload where accrual logic for HBD balances resides.
SUGGESTED_FIX: none

### [146/166] libraries/chain/database.cpp:3265 — adjust_savings_balance(HBD)` at line 3265
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:3265
STATUS: confirmed
REASON: Line 3265 contains the function signature `database::adjust_savings_balance( const account_object&, const HBD_asset& delta )`, directly matching the claim.
SUGGESTED_FIX: none

### [147/166] libraries/protocol/include/hive/protocol/hbd_interest.hpp:9 — evaluate_hbd_interest()` at line 9
Source: `07-economic-model.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:9
STATUS: confirmed
REASON: Line 9 contains the declaration of `evaluate_hbd_interest()` as claimed.
SUGGESTED_FIX: none

### [148/166] libraries/chain/database_conversion.cpp:34 — process_conversions()` at line 34
Source: `07-economic-model.md`

CITATION: libraries/chain/database_conversion.cpp:34
STATUS: confirmed
REASON: The source excerpt shows `void database::process_conversions()` defined at line 34, exactly matching the cited function and location.
SUGGESTED_FIX: none

### [149/166] libraries/chain/hive_evaluator_transfer.cpp:473 — collateralized_convert_evaluator::do_apply()` at line 473
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:473
STATUS: confirmed
REASON: Line 473 contains the function signature `void collateralized_convert_evaluator::do_apply(...)`, exactly matching the claim.
SUGGESTED_FIX: none

### [150/166] libraries/chain/util/dhf_processor.cpp:238 — make_payments()` at line 238
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:238
STATUS: confirmed
REASON: Line 238 contains the function definition `void dhf_processor::make_payments(...)`, directly supporting the claim that `make_payments()` is at line 238.
SUGGESTED_FIX: none

### [151/166] libraries/chain/util/dhf_processor.cpp:145 — calculate_maintenance_budget()` at line 145
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145
STATUS: confirmed
REASON: Line 145 contains the definition of `dhf_processor::calculate_maintenance_budget()`, matching the claim verbatim.
SUGGESTED_FIX: none

### [152/166] libraries/chain/util/dhf_processor.cpp:325 — convert_funds()` at line 325
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:325
STATUS: confirmed
REASON: Line 325 contains the `convert_funds` function definition as a member of `dhf_processor`, matching the claim verbatim.
SUGGESTED_FIX: none

### [153/166] libraries/chain/hive_evaluator_transfer.cpp:292 — transfer_to_vesting_evaluator::do_apply()` at line 292
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:292
STATUS: confirmed
REASON: Line 292 contains the function signature `void transfer_to_vesting_evaluator::do_apply(...)`, exactly matching the claim.
SUGGESTED_FIX: none

### [154/166] libraries/chain/hive_evaluator_transfer.cpp:327 — withdraw_vesting_evaluator::do_apply()` at line 327
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:327
STATUS: confirmed
REASON: Line 327 contains the exact function definition `void withdraw_vesting_evaluator::do_apply( const withdraw_vesting_operation& o )` as claimed.
SUGGESTED_FIX: none

### [155/166] libraries/chain/database_vesting.cpp:111 — process_vesting_withdrawals()` at line 111
Source: `07-economic-model.md`

CITATION: libraries/chain/database_vesting.cpp:111
STATUS: confirmed
REASON: The cited line 111 contains exactly the function signature `void database::process_vesting_withdrawals()` as referenced in the claim.
SUGGESTED_FIX: none

### [156/166] libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87 — get_vesting_share_price()` at line 87
Source: `07-economic-model.md`

CITATION: libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87
STATUS: confirmed
REASON: Line 87 contains the declaration `VEST_price get_vesting_share_price() const`, exactly matching the claim.
SUGGESTED_FIX: none

### [157/166] libraries/chain/database.cpp:2399 — update_median_feed()` at line 2399
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:2399
STATUS: confirmed
REASON: Line 2399 contains the function definition `void database::update_median_feed()` exactly as the claim states.
SUGGESTED_FIX: none

### [158/166] libraries/chain/database.cpp:2868 — update_virtual_supply()` at line 2868
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:2868
STATUS: confirmed
REASON: The cited line is exactly the start of the `database::update_virtual_supply()` function definition, matching the claim verbatim.
SUGGESTED_FIX: none

### [159/166] libraries/chain/database.cpp:2843 — calculate_HBD_percent()` at line 2843
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:2843
STATUS: confirmed
REASON: Line 2843 contains the definition `uint16_t database::calculate_HBD_percent()`, exactly matching the claim.
SUGGESTED_FIX: none

### [160/166] libraries/chain/database_hardfork.cpp:336-416 — HF20 RC initialization
Source: `08-resource-credits.md`

CITATION: libraries/chain/database_hardfork.cpp:336-416
STATUS: confirmed
REASON: The excerpt spans the HIVE_HARDFORK_0_20 case (line 336) through its closing brace (line 416) and contains explicit "Initialize RC:" logic including rc_resource_param_object, rc_usage_bucket_object, rc_pool_object, rc_stats_object creation, and per-account rc_adjustment/manabar initialization.
SUGGESTED_FIX: none

### [161/166] libraries/protocol/include/hive/protocol/config.hpp:390-494 — RC-related constants
Source: `08-resource-credits.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:390-494
STATUS: confirmed
REASON: The cited range contains RC-related constants including the Resource Dynamics framework (HIVE_RD_*, lines 393-403), account subsidy constants (lines 405-420), and the explicitly labeled "HIVE RC related constants" section (lines 479-494).
SUGGESTED_FIX: none

### [162/166] libraries/chain/witness_schedule.cpp:264-333 — Hardfork voting mechanism
Source: `09-hardfork-history.md`

CITATION: libraries/chain/witness_schedule.cpp:264-333
STATUS: confirmed
REASON: The cited range clearly implements the hardfork voting mechanism — tallying witness running_version and (hardfork_version_vote, hardfork_time_vote) tuples across the scheduled witnesses and updating hardfork_property_object when hardfork_required_witnesses threshold is met.
SUGGESTED_FIX: none

### [163/166] libraries/chain/database.cpp:61-71 — next_hf_time()` for HF28
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:61-71
STATUS: confirmed
REASON: The function `next_hf_time()` is defined at line 61 with an explicit comment at line 63 stating "current 'next hardfork' is HF28", directly supporting the claim.
SUGGESTED_FIX: none

### [164/166] libraries/chain/database.cpp:1461-1540 — clear_account()` / `clear_accounts()` for HF23
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:1461-1540
STATUS: confirmed
REASON: The cited lines contain the `clear_accounts()` function (1461-1472) and the start of `clear_account()` (1474-1540), directly supporting the claim about these functions being used for HF23.
SUGGESTED_FIX: none

### [165/166] libraries/chain/database.cpp:1422-1458 — restore_accounts()` for HF24
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:1422-1458
STATUS: confirmed
REASON: The source excerpt at lines 1422-1458 shows the `database::restore_accounts()` function definition, which directly supports the claim about `restore_accounts()` for HF24.
SUGGESTED_FIX: none

### [166/166] libraries/chain/database_dhf.cpp:146 — remove_proposal_votes_for_accounts_without_voting_rights()` for HF28
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_dhf.cpp:146
STATUS: confirmed
REASON: Line 146 contains the exact function definition `void database::remove_proposal_votes_for_accounts_without_voting_rights()` matching the claim verbatim.
SUGGESTED_FIX: none

## Summary

| Status | Count |
|--------|------:|
| confirmed  | 165 |
| drifted    | 1 |
| broken     | 0 |
| unparseable| 0 |
