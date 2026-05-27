# Verification Report

- Topic: `hive-core`
- Pinned: `1.28.6` (`10ac0ce94f7591b6ad80db1a23d046c9d57b6559`)
- Run: 2026-05-26T18:23:46+02:00
- Citations audited: 166


### [1/166] libraries/protocol/include/hive/protocol/config.hpp:56-458 — All timing/economic/size constants
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56-458
STATUS: confirmed
REASON: Lines 56-458 contain all timing constants (block interval, cashout windows, recovery periods), economic constants (inflation rates, APR percentages, reward splits, HBD limits), and size constants (max memo, account name, transaction, block sizes) as claimed.
SUGGESTED_FIX: none

### [2/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-53 — NAI bit layout and encoding
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-53
STATUS: confirmed
REASON: Lines 9-11 define the NAI bit layout (4 precision bits + 1 control bit = HIVE_NAI_SHIFT of 5), and lines 30-32 show the NAI encoding into asset_num via `(NAI << HIVE_NAI_SHIFT) | precision`, directly supporting the claim.
SUGGESTED_FIX: none

### [3/166] libraries/protocol/include/hive/protocol/asset.hpp:21-186 — Asset struct and price
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:21-186
STATUS: confirmed
REASON: The cited range contains both `struct asset` (lines 21-96) with amount/symbol fields and operators, and `struct price` (lines 139-186) with base/quote assets, directly supporting the claim.
SUGGESTED_FIX: none

### [4/166] libraries/protocol/asset.cpp:128-286 — Asset validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/asset.cpp:128-286
STATUS: confirmed
REASON: The cited range covers asset_symbol_type's NAI/decimal/check-digit validation in asset_num_from_nai() and the canonical validate() function, directly supporting the "Asset validation" claim.
SUGGESTED_FIX: none

### [5/166] libraries/protocol/include/hive/protocol/authority.hpp:7-55 — Authority struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/authority.hpp:7-55
STATUS: confirmed
REASON: The source excerpt at lines 7-55 shows the complete `authority` struct definition with its classification enum, constructors, member functions, type aliases, and the three data members (weight_threshold, account_auths, key_auths), directly supporting the "Authority struct" claim.
SUGGESTED_FIX: none

### [6/166] libraries/protocol/authority.cpp:58-122 — Account name validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/authority.cpp:58-122
STATUS: confirmed
REASON: Lines 58-122 contain the `check_account_name` function implementing account name validation (length bounds, dot-separated segments of >=3 chars, start with a-z, end with a-z/0-9, middle chars a-z/0-9/'-'), directly supporting the claim.
SUGGESTED_FIX: none

### [7/166] libraries/protocol/include/hive/protocol/operations.hpp:15-125 — Operation variant (93 types: 50 regular + 43 virtual)
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/operations.hpp:15-125
STATUS: confirmed
REASON: The static_variant lists exactly 50 regular operations (indices 0-49, vote_operation through recurrent_transfer_operation) and 43 virtual operations (last_regular + 1 through last_regular + 43, fill_convert_request_operation through declined_voting_rights_operation), totaling 93 types as claimed.
SUGGESTED_FIX: none

### [8/166] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Base operation class
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: The source excerpt at lines 13-29 shows the `base_operation` struct definition with its authority-getting methods, `is_virtual()`, and `validate()`, directly supporting the claim that this is the base operation class.
SUGGESTED_FIX: none

### [9/166] libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-17 — RC custom operations
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-17
STATUS: confirmed
REASON: Lines 8-17 define `delegate_rc_operation` as a base_operation with the static_variant wrapper following at line 19, directly supporting the claim about RC custom operations.
SUGGESTED_FIX: none

### [10/166] libraries/protocol/hive_operations.cpp:1-866 — Operation validate() methods
Source: `00-consolidated.md`

CITATION: libraries/protocol/hive_operations.cpp:1-866
STATUS: confirmed
REASON: The file spans lines 1-866 and contains numerous operation validate() methods (account_create, transfer, comment, vote, witness_set_properties, escrow_*, recurrent_transfer, etc.), directly supporting the claim.
SUGGESTED_FIX: none

### [11/166] libraries/protocol/dhf_operations.cpp:1-62 — DHF operation validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/dhf_operations.cpp:1-62
STATUS: confirmed
REASON: The cited lines contain the validate() implementations for all four DHF operations (create_proposal, update_proposal, update_proposal_votes, remove_proposal), directly supporting the claim about DHF operation validation.
SUGGESTED_FIX: none

### [12/166] libraries/protocol/include/hive/protocol/block_header.hpp:15-26 — Block header struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/block_header.hpp:15-26
STATUS: confirmed
REASON: Lines 15-26 contain the `struct block_header` definition with its fields (previous, timestamp, witness, transaction_merkle_root, extensions), directly matching the claim.
SUGGESTED_FIX: none

### [13/166] libraries/protocol/include/hive/protocol/transaction.hpp:12-53 — Transaction struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-53
STATUS: confirmed
REASON: The cited lines define the `transaction` struct with its fields (ref_block_num, ref_block_prefix, expiration, operations, extensions) and methods, matching the claim verbatim.
SUGGESTED_FIX: none

### [14/166] libraries/protocol/transaction.cpp:40-55 — Transaction validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/transaction.cpp:40-55
STATUS: confirmed
REASON: The cited lines show two `transaction::validate()` overloads that enforce at least one operation and call `operation_validate` on each, directly supporting the "Transaction validation" claim.
SUGGESTED_FIX: none

### [15/166] libraries/protocol/include/hive/protocol/version.hpp:15-77 — Version encoding
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:15-77
STATUS: confirmed
REASON: The cited range shows the `version` struct with `v_num` as a uint32_t packed as major(bits 24-31)/minor(bits 16-23)/revision(bits 0-15), matching the "Version encoding" claim.
SUGGESTED_FIX: none

### [16/166] libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30 — Hardfork block numbers
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30
STATUS: confirmed
REASON: Lines 3-30 contain the complete set of HIVE_HARDFORK_X_Y_BLOCK macro definitions, directly supporting the claim about hardfork block numbers.
SUGGESTED_FIX: none

### [17/166] libraries/protocol/include/hive/protocol/config.hpp:137-143 — Chain IDs
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:137-143
STATUS: confirmed
REASON: The cited lines define HIVE_CHAIN_ID (and OLD_CHAIN_ID) for both mirrornet and mainnet variants, directly supporting the "Chain IDs" claim.
SUGGESTED_FIX: none

### [18/166] libraries/protocol/include/hive/protocol/validation.hpp:64-115 — Validation helpers
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/validation.hpp:64-115
STATUS: confirmed
REASON: The cited range contains validation helper functions (validate_string_max_size, validate_is_utf8, validate_string_is_not_empty, validate_number_in_100_percent_range, validate_account_name, validate_permlink), directly supporting the "Validation helpers" claim.
SUGGESTED_FIX: none

### [19/166] libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23 — HBD interest calc
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23
STATUS: confirmed
REASON: Lines 8-23 contain the `hbd_interest` struct with `evaluate_hbd_interest` which accumulates hbd_seconds and applies interest_rate/HIVE_SECONDS_PER_YEAR/HIVE_100_PERCENT — exactly the HBD interest calculation referenced by the claim.
SUGGESTED_FIX: none

### [20/166] libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26 — Collateral estimation
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26
STATUS: confirmed
REASON: The cited lines define `hive_collateral::estimate_hive_collateral`, which computes required HIVE collateral from HBD amount using fee multiplication and the collateral ratio, directly matching the "Collateral estimation" claim.
SUGGESTED_FIX: none

### [21/166] libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285 — Testnet overrides
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285
STATUS: confirmed
REASON: The cited range spans the `configuration` class which defines testnet overrides for consensus parameters (cashout windows, voting intervals, supplies, RC stats frequency, etc.) gated by `#ifdef IS_TEST_NET`, directly supporting the "Testnet overrides" claim.
SUGGESTED_FIX: none

### [22/166] libraries/chain/database.cpp:2183-2369 — Block application (`_apply_block`)
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2183-2369
STATUS: confirmed
REASON: The cited range begins exactly at the `_apply_block` function definition on line 2183 and ends at its closing brace on line 2369, fully supporting the claim about block application.
SUGGESTED_FIX: none

### [23/166] libraries/chain/database.cpp:2757-2779 — Block header validation
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2757-2779
STATUS: confirmed
REASON: The cited lines define `database::validate_block_header`, which validates the previous block ID, timestamp ordering, witness signing key, and scheduled witness slot — directly supporting the "Block header validation" claim.
SUGGESTED_FIX: none

### [24/166] libraries/chain/database.cpp:2644-2702 — Transaction application
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2644-2702
STATUS: confirmed
REASON: Lines 2644-2702 contain the `_apply_transaction` function which performs transaction application (duplicate check, validation, operation iteration, RC finalization, and pre/post notifications).
SUGGESTED_FIX: none

### [25/166] libraries/chain/database.cpp:2722-2746 — Operation dispatch
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2722-2746
STATUS: confirmed
REASON: The cited lines define `database_impl::apply_operation`, which dispatches to the evaluator registry via `_evaluator_registry.get_evaluator(op).apply(op)` with pre/post notifications and RC discount handling, directly supporting the "Operation dispatch" claim.
SUGGESTED_FIX: none

### [26/166] libraries/chain/database.cpp:2956-3064 — LIB calculation
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2956-3064
STATUS: confirmed
REASON: Lines 2956-3064 contain the complete `update_last_irreversible_block` function which implements LIB calculation using scheduled witnesses, HIVE_IRREVERSIBLE_THRESHOLD offset, and both legacy and fork-db-aware algorithms.
SUGGESTED_FIX: none

### [27/166] libraries/chain/database.cpp:2899-2954 — Fast confirm processing
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2899-2954
STATUS: confirmed
REASON: Lines 2899-2954 contain the complete `process_fast_confirm_transaction` function, directly implementing fast confirm processing as claimed.
SUGGESTED_FIX: none

### [28/166] libraries/chain/database.cpp:3066-3097 — Irreversibility migration
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:3066-3097
STATUS: confirmed
REASON: The cited lines define `database::migrate_irreversible_state`, which performs the irreversibility migration (stores block, commits undo state, notifies on irreversible block) exactly as the claim describes.
SUGGESTED_FIX: none

### [29/166] libraries/chain/database.cpp:2789-2841 — Participation tracking
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2789-2841
STATUS: confirmed
REASON: Lines 2817-2823 explicitly update `participation_count` and `recent_slots_filled` in the dynamic global properties to track witness block production participation, which directly supports the "Participation tracking" claim.
SUGGESTED_FIX: none

### [30/166] libraries/chain/database.cpp:2843-2868 — HBD print rate / virtual supply
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2843-2868
STATUS: confirmed
REASON: Lines 2843-2866 define `calculate_HBD_percent()` which computes the HBD print rate as the ratio of HBD-denominated-in-HIVE to virtual_supply, and line 2868 begins `update_virtual_supply()`, directly supporting the "HBD print rate / virtual supply" claim.
SUGGESTED_FIX: none

### [31/166] libraries/chain/database.cpp:1704 — Inflation distribution
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:1704
STATUS: confirmed
REASON: Line 1704 is the definition of `database::process_funds()`, which per the preceding comment pays out vesting and reward shares every block — the function responsible for inflation distribution.
SUGGESTED_FIX: none

### [32/166] libraries/chain/database.cpp:61-71 — next_hf_time()
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:61-71
STATUS: confirmed
REASON: The function `next_hf_time()` is defined at line 61 of the cited file, with the HF28 timestamp logic spanning the cited range.
SUGGESTED_FIX: none

### [33/166] libraries/chain/database.cpp:1422-1540 — Account clearing/restoration
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:1422-1540
STATUS: confirmed
REASON: The cited range covers `restore_accounts` (1422), `clear_accounts` (1461), and the start of `clear_account` (1474), which directly implement account clearing and restoration.
SUGGESTED_FIX: none

### [34/166] libraries/chain/hive_evaluator_transfer.cpp:75-957 — Transfer evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:75-957
STATUS: confirmed
REASON: The cited range in hive_evaluator_transfer.cpp contains the transfer-related evaluator implementations (escrow_transfer, transfer, transfer_to_vesting, withdraw_vesting, convert, limit_order, savings, claim_reward_balance, delegate_vesting_shares, recurrent_transfer), directly supporting the "Transfer evaluators" claim.
SUGGESTED_FIX: none

### [35/166] libraries/chain/hive_evaluator_account.cpp:130-657 — Account evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_account.cpp:130-657
STATUS: confirmed
REASON: The cited range contains the account-related evaluators (account_create, account_create_with_delegation, account_update, account_update2, claim_account, create_claimed_account, request_account_recovery, recover_account, change_recovery_account, decline_voting_rights, reset_account, set_reset_account) plus the shared create_account helper, directly supporting the "Account evaluators" claim.
SUGGESTED_FIX: none

### [36/166] libraries/chain/hive_evaluator_social.cpp:55-864 — Social evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_social.cpp:55-864
STATUS: confirmed
REASON: The cited range spans the social evaluators in this file (delete_comment, comment_options, comment, pre_hf20_vote, hf20_vote, and vote evaluators), matching the claim "Social evaluators".
SUGGESTED_FIX: none

### [37/166] libraries/chain/hive_evaluator.cpp:62-628 — Witness/custom/pow evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator.cpp:62-628
STATUS: confirmed
REASON: The cited range contains witness_update, witness_set_properties, account_witness_proxy, account_witness_vote, custom, custom_json, custom_binary, pow, pow2, feed_publish, and witness_block_approve evaluators, fully supporting the claim about witness/custom/pow evaluators.
SUGGESTED_FIX: none

### [38/166] libraries/chain/dhf_evaluator.cpp:32-252 — DHF evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/dhf_evaluator.cpp:32-252
STATUS: confirmed
REASON: Lines 32-252 contain the four DHF evaluators (create_proposal, update_proposal, update_proposal_votes, remove_proposal), matching the claim.
SUGGESTED_FIX: none

### [39/166] libraries/chain/database_comment.cpp:129-379 — Comment cashout/curation
Source: `00-consolidated.md`

CITATION: libraries/chain/database_comment.cpp:129-379
STATUS: confirmed
REASON: Lines 129-195 implement `pay_curators` (curation reward distribution) and lines 197-377 implement `cashout_comment_helper` (comment cashout with author/beneficiary/curator payouts), directly supporting the "Comment cashout/curation" claim.
SUGGESTED_FIX: none

### [40/166] libraries/chain/witness_schedule.cpp:152-396 — Witness scheduling
Source: `00-consolidated.md`

CITATION: libraries/chain/witness_schedule.cpp:152-396
STATUS: confirmed
REASON: Lines 152-396 contain the `update_witness_schedule4` function, which implements the witness scheduling algorithm (selecting voted witnesses, miners, timeshare witnesses, updating virtual schedule, and shuffling), directly supporting the "Witness scheduling" claim.
SUGGESTED_FIX: none

### [41/166] libraries/chain/database_witness.cpp:284-306 — Witness missed blocks
Source: `00-consolidated.md`

CITATION: libraries/chain/database_witness.cpp:284-306
STATUS: confirmed
REASON: The function `update_witness_missed_blocks` at lines 284-306 directly implements witness missed block tracking by incrementing `total_missed`, handling HF14/HF20 shutdown logic, and pushing `producer_missed_operation`.
SUGGESTED_FIX: none

### [42/166] libraries/chain/fork_database.cpp:20-330 — Fork database
Source: `00-consolidated.md`

CITATION: libraries/chain/fork_database.cpp:20-330
STATUS: confirmed
REASON: The cited file and line range contain the fork_database class implementation (push_block, pop_block, fetch_branch_from, head tracking, unlinked index, etc.), directly supporting the "Fork database" claim.
SUGGESTED_FIX: none

### [43/166] libraries/chain/sync_block_writer.cpp:162-367 — Fork switching
Source: `00-consolidated.md`

CITATION: libraries/chain/sync_block_writer.cpp:162-367
STATUS: confirmed
REASON: Line 162 begins `sync_block_writer::switch_forks`, which pops blocks back to the common ancestor and replays the new branch, directly implementing fork switching as claimed (the range also encompasses `find_new_last_irreversible_block`, a related fork-management routine).
SUGGESTED_FIX: none

### [44/166] libraries/chain/block_log.cpp:338-515 — Block log read/write
Source: `00-consolidated.md`

CITATION: libraries/chain/block_log.cpp:338-515
STATUS: confirmed
REASON: The cited range contains block_log read/write methods (append_raw, multi_append_raw, read_raw_block_data_by_num, append, flush, read_block_id_by_num, read_block_by_num), directly supporting the "Block log read/write" claim.
SUGGESTED_FIX: none

### [45/166] libraries/chain/block_log_artifacts.cpp:46-166 — Block log artifacts
Source: `00-consolidated.md`

CITATION: libraries/chain/block_log_artifacts.cpp:46-166
STATUS: confirmed
REASON: The cited range contains the `artifact_file_header` (lines 46-69) and `artifact_file_chunk` (lines 82-166) structs that define the block log artifacts file format, directly supporting the "Block log artifacts" claim.
SUGGESTED_FIX: none

### [46/166] libraries/chain/include/hive/chain/hive_object_types.hpp:47-89 — Object type enum (39 IDs)
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/hive_object_types.hpp:47-89
STATUS: confirmed
REASON: Counting the enumerators in the excerpt yields exactly 39 object type IDs (33 core + 6 RC), matching the claim.
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
REASON: Line 372 contains the class declaration `class comment_vote_object`, directly supporting the claim.
SUGGESTED_FIX: none

### [49/166] libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:69 — witness_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:69
STATUS: confirmed
REASON: The cited line defines `class witness_object`, directly supporting the claim referencing `witness_object`.
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
REASON: The excerpt shows RC checks only assert/throw when `db.is_in_control() || db.is_reapplying_one_tx()` (mempool path), while the block-processing branch merely logs via `ilog` — plus the FC_TODO at line 545 explicitly notes RC is not yet part of consensus, directly supporting the "non-consensus enforcement" claim.
SUGGESTED_FIX: none

### [52/166] libraries/chain/rc/rc_utility.cpp:799-831 — Mana deduction (finalize_tx)
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:799-831
STATUS: confirmed
REASON: The excerpt shows `resource_credits::finalize_transaction` which computes the RC cost and calls `use_account_rcs(total_cost)` at line 818 — the mana deduction the claim references.
SUGGESTED_FIX: none

### [53/166] libraries/chain/rc/rc_utility.cpp:26-110 — RC delegation mechanics
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:26-110
STATUS: confirmed
REASON: Lines 26-110 contain the complete `delegate_rc_evaluator::do_apply` implementation covering hardfork gating, min-delegation check, per-delegatee create/modify/remove logic, mana accounting, and delegable-RC validation—exactly the RC delegation mechanics claimed.
SUGGESTED_FIX: none

### [54/166] libraries/chain/rc/rc_utility.cpp:401-443 — Delegation overflow
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:401-443
STATUS: confirmed
REASON: The cited range contains the delegation overflow handling logic, with `delegation_overflow` computed at line 408, the overflow branch at line 411, delegation removal via `remove_delegations`, and creation/update of `rc_expired_delegation_object` for unfinished removals.
SUGGESTED_FIX: none

### [55/166] libraries/chain/rc/rc_utility.cpp:505-537 — Flood surcharge
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:505-537
STATUS: confirmed
REASON: The excerpt at lines 505-537 contains the flood surcharge logic: surcharge initialization, flood_level threshold check, privileged-transaction exemption, and the surcharge calculation using flood_surcharge multiplied by (blocks_in_mempool - flood_level).
SUGGESTED_FIX: none

### [56/166] libraries/chain/rc/resource_count.cpp:136-631 — Resource counting
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_count.cpp:136-631
STATUS: confirmed
REASON: The cited range contains the `handle_operation_discount` differential counter, the `count_operation_visitor` with per-operation byte/time tallies, and the `count_resources` function that aggregates state_bytes, execution_time, history_bytes, market_bytes, and new_accounts — directly supporting the "Resource counting" claim.
SUGGESTED_FIX: none

### [57/166] libraries/chain/rc/resource_sizes.cpp:45-165 — State byte sizes
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_sizes.cpp:45-165
STATUS: confirmed
REASON: Lines 45-165 contain the `state_object_size_info` constructor defining TEMPORARY/LASTING/PERSISTENT_STATE_BYTE constants and all per-operation state byte size calculations, directly supporting the "State byte sizes" claim.
SUGGESTED_FIX: none

### [58/166] libraries/chain/rc/resource_sizes.cpp:167-242 — Execution time benchmarks
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_sizes.cpp:167-242
STATUS: confirmed
REASON: Lines 167-242 contain the `operation_exec_info` constructor with per-operation execution time benchmarks (validate + exec + pre->rc + post->rc components) sourced from issue #205 measurements, directly supporting the "Execution time benchmarks" claim.
SUGGESTED_FIX: none

### [59/166] libraries/chain/rc/rc_curve.cpp:32-98 — Price curve computation
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_curve.cpp:32-98
STATUS: confirmed
REASON: The cited lines contain the `generate_rc_curve_params` function which computes the price curve parameters (coeff_a, coeff_b, shift) for the RC system, directly supporting the "Price curve computation" claim.
SUGGESTED_FIX: none

### [60/166] libraries/chain/util/rd.cpp:23-118 — Pool dynamics (decay)
Source: `00-consolidated.md`

CITATION: libraries/chain/util/rd.cpp:23-118
STATUS: confirmed
REASON: The cited range covers rd_compute_pool_decay, rd_apply, and rd_setup_dynamics_params, which together implement pool dynamics and decay computation.
SUGGESTED_FIX: none

### [61/166] libraries/chain/include/hive/chain/util/manabar.hpp:32-141 — Manabar struct + update utility
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/util/manabar.hpp:32-141
STATUS: confirmed
REASON: Lines 32-102 define the `manabar` struct with regenerate/use/has_mana methods, and lines 104-141 define the `update_manabar` template utility, matching the claim exactly.
SUGGESTED_FIX: none

### [62/166] libraries/chain/util/dhf_processor.cpp:145-325 — DHF payment processing
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145-325
STATUS: confirmed
REASON: The excerpt shows the full DHF payment processing pipeline (calculate_maintenance_budget, transfer_payments, make_payments, run, record_funding, convert_funds) within the cited range, directly supporting the claim.
SUGGESTED_FIX: none

### [63/166] libraries/chain/util/dhf_processor.cpp:145 — DHF budget calculation
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145
STATUS: confirmed
REASON: Line 145 defines `dhf_processor::calculate_maintenance_budget`, which directly implements the DHF budget calculation claim.
SUGGESTED_FIX: none

### [64/166] libraries/chain/util/dhf_processor.cpp:325 — DHF HIVE->HBD conversion
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:325
STATUS: confirmed
REASON: Line 325 is the definition of `dhf_processor::convert_funds`, which is the function responsible for the DHF HIVE->HBD conversion logic.
SUGGESTED_FIX: none

### [65/166] libraries/protocol/include/hive/protocol/config.hpp:56 — HIVE_BLOCK_INTERVAL = 3
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56
STATUS: confirmed
REASON: Line 56 contains exactly `#define HIVE_BLOCK_INTERVAL 3`, directly supporting the claim verbatim.
SUGGESTED_FIX: none

### [66/166] libraries/protocol/include/hive/protocol/config.hpp:56-207 — Block, cashout, recovery, feed timings
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56-207
STATUS: confirmed
REASON: The cited range contains block interval (line 56), cashout windows (lines 73-77, 155-159), recovery periods (lines 86-89, 167-170), and feed timings (lines 108-112, 189-193), matching all four categories named in the claim.
SUGGESTED_FIX: none

### [67/166] libraries/protocol/include/hive/protocol/config.hpp:215-346 — Inflation, rewards, HBD limits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:215-346
STATUS: confirmed
REASON: The cited lines contain inflation constants (HIVE_INFLATION_RATE_START_PERCENT, HIVE_INFLATION_RATE_STOP_PERCENT, HIVE_INFLATION_NARROWING_PERIOD), reward percentages (content/vesting/proposal fund splits for HF16/HF21), APR constants for curate/content/liquidity/producer/pow, and HBD limit thresholds (HF14/HF20/HF26 start/stop percentages and hard limits), supporting the claim verbatim.
SUGGESTED_FIX: none

### [68/166] libraries/protocol/include/hive/protocol/config.hpp:348-399 — Transaction, block, name, URL sizes and miscellaneous limits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:348-399
STATUS: confirmed
REASON: The cited range contains account name lengths (348-349), permlink/URL lengths (351-353, 379), transaction/block size limits (360, 364-367), and miscellaneous limits (355-358, 369, 375, 381, 389, 393-401), matching the claim verbatim.
SUGGESTED_FIX: none

### [69/166] libraries/protocol/include/hive/protocol/config.hpp:441-458 — null, temp, miners, proxy-to-self, root-post-parent, plus OBSOLETE/NEW treasury constants (treasury name resolved via `database::get_treasury_name()`)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:441-458
STATUS: confirmed
REASON: The excerpt defines all six listed reserved accounts (HIVE_MINER_ACCOUNT, HIVE_NULL_ACCOUNT, HIVE_TEMP_ACCOUNT, HIVE_PROXY_TO_SELF_ACCOUNT, HIVE_ROOT_POST_PARENT, OBSOLETE_TREASURY_ACCOUNT, NEW_HIVE_TREASURY_ACCOUNT) and explicitly directs callers to database::get_treasury_name() for treasury resolution.
SUGGESTED_FIX: none

### [70/166] libraries/protocol/include/hive/protocol/config.hpp:460-469 — Proposal system
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:460-469
STATUS: confirmed
REASON: Lines 460-469 contain the "HIVE PROPOSAL SYSTEM support" section header and core proposal system constants (treasury fee, subject length, max IDs, fee increase parameters, conversion rate), directly supporting the claim.
SUGGESTED_FIX: none

### [71/166] libraries/protocol/include/hive/protocol/config.hpp:479-494 — Resource credits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:479-494
STATUS: confirmed
REASON: Lines 479-494 define HIVE RC related constants (regen time, bucket time, window count, stats report frequency, historical adjustment, max accounts per delegation), directly supporting the "Resource credits" claim.
SUGGESTED_FIX: none

### [72/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-32 — Precision bits, shift, NAI encoding
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-32
STATUS: confirmed
REASON: Lines 9-32 define HIVE_ASSET_SYMBOL_PRECISION_BITS (4), HIVE_NAI_SHIFT, and the NAI encoding macros (HIVE_ASSET_NUM_HBD/HIVE/VESTS) exactly matching the claim.
SUGGESTED_FIX: none

### [73/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:20-22 — HBD=3, HIVE=3, VESTS=6
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:20-22
STATUS: confirmed
REASON: Lines 20-22 define HIVE_PRECISION_HBD=3, HIVE_PRECISION_HIVE=3, and HIVE_PRECISION_VESTS=6, exactly matching the claim.
SUGGESTED_FIX: none

### [74/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:36-53 — STEEM/SBD/TESTS/TBD/HIVE/HBD/VESTS
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:36-53
STATUS: confirmed
REASON: The excerpt defines all seven referenced symbols (VESTS, STEEM/TESTS as OBSOLETE, HIVE, SBD/TBD as OBD, HBD) across the testnet and mainnet branches.
SUGGESTED_FIX: none

### [75/166] libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216 — Legacy vs NAI pack/unpack
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216
STATUS: confirmed
REASON: The excerpt shows both pack (lines 157-187) and unpack (lines 189-216) functions explicitly handling legacy_space vs smt_nai_space serialization with distinct paths for HIVE/HBD/VESTS legacy symbols.
SUGGESTED_FIX: none

### [76/166] libraries/protocol/include/hive/protocol/asset.hpp:21-96 — Amount + symbol with operator overloads
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:21-96
STATUS: confirmed
REASON: The cited lines define the `asset` struct with `amount` and `symbol` fields plus operator overloads for +=, -=, unary -, ==, <, <=, !=, >, >=, binary -, and binary +, directly supporting the claim.
SUGGESTED_FIX: none

### [77/166] libraries/protocol/include/hive/protocol/asset.hpp:139-186 — Base/quote pair
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:139-186
STATUS: confirmed
REASON: The cited lines define the `price` struct with `asset base` and `asset quote` members plus their constructors and accessors, directly supporting the "Base/quote pair" claim.
SUGGESTED_FIX: none

### [78/166] libraries/protocol/include/hive/protocol/asset.hpp:218-261 — Typed thin wrappers
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:218-261
STATUS: confirmed
REASON: The source at lines 218-261 defines the `tiny_asset` template struct, which is a typed thin wrapper around `share_type amount` parameterized by `_SYMBOL`, directly supporting the "Typed thin wrappers" claim.
SUGGESTED_FIX: none

### [79/166] libraries/protocol/include/hive/protocol/asset.hpp:268-322 — Typed price wrappers
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:268-322
STATUS: confirmed
REASON: The cited lines define the `tiny_price` class template parameterized by base and quote asset symbols, which is a typed price wrapper enforcing compile-time symbol checking.
SUGGESTED_FIX: none

### [80/166] libraries/protocol/asset.cpp:80-126 — 8-digit Damm algorithm
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:80-126
STATUS: confirmed
REASON: The source at lines 80-126 implements `damm_checksum_8digit` with an explicit comment referencing the Damm algorithm and processes an 8-digit value (d0-d7, MAX_DAMM_VALUE = 100000000), directly supporting the claim.
SUGGESTED_FIX: none

### [81/166] libraries/protocol/asset.cpp:261-283 — NAI range + control bit checks
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:261-283
STATUS: confirmed
REASON: The cited lines contain the asset_symbol_type::validate() function with explicit NAI range checks (SMT_MIN_NAI <= nai_data_digits <= SMT_MAX_NAI) and the control bit check (nai_1bit == SMT_ASSET_NUM_CONTROL_MASK), matching the claim verbatim.
SUGGESTED_FIX: none

### [82/166] libraries/protocol/asset.cpp:310-325 — uint128 cross-multiplication
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:310-325
STATUS: confirmed
REASON: The excerpt shows `asset operator *` using `uint128_t result` with cross-multiplication (`result * b.quote.amount.value) / b.base.amount.value` and the symmetric case at line 322), directly supporting the claim of uint128 cross-multiplication.
SUGGESTED_FIX: none

### [83/166] libraries/protocol/asset.cpp:337-340 — Returns `HIVE_MAX_SATOSHIS
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:337-340
STATUS: confirmed
REASON: The source at lines 337-340 defines `price::max_satoshis()` returning `HIVE_MAX_SATOSHIS`, exactly supporting the claim.
SUGGESTED_FIX: none

### [84/166] libraries/protocol/include/hive/protocol/types.hpp:66-81 — All fundamental typedefs
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:66-81
STATUS: confirmed
REASON: Lines 66-81 contain the fundamental typedefs in the protocol namespace (private_key_type, chain_id_type, account_name_type, block_id_type, checksum_type, transaction_id_type, digest_type, signature_type, share_type, ushare_type, weight_type, contribution_id_type, custom_id_type), supporting the claim verbatim.
SUGGESTED_FIX: none

### [85/166] libraries/protocol/include/hive/protocol/types.hpp:83-103 — Key data + base58 encoding
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:83-103
STATUS: confirmed
REASON: The struct contains `fc::ecc::public_key_data key_data` plus a constructor from `std::string base58str` and an `explicit operator std::string()` conversion, directly supporting "key data + base58 encoding".
SUGGESTED_FIX: none

### [86/166] libraries/protocol/include/hive/protocol/authority.hpp:7-55 — Threshold + key/account maps
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/authority.hpp:7-55
STATUS: confirmed
REASON: The authority struct at lines 7-55 contains exactly `weight_threshold` (line 52), `account_auths` map (line 53), and `key_auths` map (line 54), with typedefs for both maps on lines 49-50, directly supporting the claim.
SUGGESTED_FIX: none

### [87/166] libraries/protocol/authority.cpp:58-122 — RFC 1035 with Hive rules
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/authority.cpp:58-122
STATUS: confirmed
REASON: The check_account_name function at lines 58-122 implements RFC 1035-style hostname/label validation (dot-separated segments, alphanumeric with hyphens, must start with letter, must end with alphanumeric) with Hive-specific rules (lowercase-only, min segment length of 3 enforced via HIVE_MIN_ACCOUNT_NAME_LENGTH).
SUGGESTED_FIX: none

### [88/166] libraries/protocol/include/hive/protocol/block_header.hpp:15-26 — previous, timestamp, witness, merkle root
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/block_header.hpp:15-26
STATUS: confirmed
REASON: The cited range contains all four claimed fields: `previous` (line 18), `timestamp` (line 20), `witness` (line 21), and `transaction_merkle_root` (line 22).
SUGGESTED_FIX: none

### [89/166] libraries/protocol/block.cpp:13-16 — endian_reverse_u32(id._hash[0])
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/block.cpp:13-16
STATUS: confirmed
REASON: Line 15 contains `fc::endian_reverse_u32(id._hash[0])` which matches the claim verbatim within the cited line range.
SUGGESTED_FIX: none

### [90/166] libraries/protocol/block.cpp:19-46 — Pairwise hashing
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/block.cpp:19-46
STATUS: confirmed
REASON: The excerpt shows `legacy_calculate_merkle_root` iterating IDs in pairs (i += 2) and hashing them via `digest_type::hash(std::make_pair(ids[i], ids[i+1]))`, with the comment "hash ID's in pairs" — pairwise hashing verbatim.
SUGGESTED_FIX: none

### [91/166] libraries/protocol/include/hive/protocol/transaction.hpp:12-53 — ref_block, expiration, operations
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-53
STATUS: confirmed
REASON: The transaction struct at lines 12-53 contains ref_block_num/ref_block_prefix (14-15), expiration (17), and operations (19), supporting the claim verbatim.
SUGGESTED_FIX: none

### [92/166] libraries/protocol/transaction.cpp:84-88 — Block number + prefix extraction
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:84-88
STATUS: confirmed
REASON: The cited lines define `set_reference_block` which extracts `ref_block_num` from the reversed first u32 of the block id hash and `ref_block_prefix` from the second u32, directly supporting the claim about block number + prefix extraction.
SUGGESTED_FIX: none

### [93/166] libraries/protocol/transaction.cpp:58-64 — SHA-256 truncated to 20 bytes
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:58-64
STATUS: confirmed
REASON: The cited lines show `transaction::id()` calling `digest(pack)` then `memcpy`-ing into `result._hash` with `std::min(sizeof(result), sizeof(h))`, which is exactly the truncation pattern the claim describes (digest output truncated to the smaller transaction_id_type size of 20 bytes).
SUGGESTED_FIX: none

### [94/166] libraries/protocol/transaction.cpp:29-38 — chain_id + transaction -> SHA-256
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:29-38
STATUS: confirmed
REASON: The `sig_digest` function at lines 29-38 packs `chain_id` followed by the transaction (`*this`) into a `digest_type::encoder` (SHA-256) and returns the result, matching the claim verbatim.
SUGGESTED_FIX: none

### [95/166] libraries/protocol/transaction.cpp:40-56 — operations.size() > 0, per-op validate
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:40-56
STATUS: confirmed
REASON: Line 42 contains the verbatim assertion `operations.size() > 0` and lines 43-44 (and 50-54) iterate operations invoking `operation_validate(op)`, directly supporting the claim.
SUGGESTED_FIX: none

### [96/166] libraries/protocol/include/hive/protocol/version.hpp:15-77 — Major.HF.release in uint32
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:15-77
STATUS: confirmed
REASON: The source shows `uint32_t v_num` storing major (bits 24-31), hardfork/minor (bits 16-23), and release (bits 0-15) per the constructor `version(uint8_t m, uint8_t h, uint16_t r)` and accessor masks, matching the claim verbatim.
SUGGESTED_FIX: none

### [97/166] libraries/protocol/include/hive/protocol/version.hpp:79-102 — Masks release bits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:79-102
STATUS: confirmed
REASON: The `hardfork_version` struct's constructors, assignment operators, and comparison operators all apply the `0xFFFF0000` bitmask to `v_num`, which preserves the major/hardfork bits and masks out the lower 16 release/revision bits.
SUGGESTED_FIX: none

### [98/166] libraries/protocol/include/hive/protocol/version.hpp:104-111 — HF version + activation time
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:104-111
STATUS: confirmed
REASON: The `hardfork_version_vote` struct at lines 104-111 contains exactly `hf_version` (hardfork_version) and `hf_time` (fc::time_point_sec), directly supporting the claim about HF version + activation time.
SUGGESTED_FIX: none

### [99/166] libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30 — All 28 HF activation blocks
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30
STATUS: confirmed
REASON: The excerpt shows exactly 28 hardfork activation block definitions (HF 0_1 through 1_28) on lines 3-30, matching the claim.
SUGGESTED_FIX: none

### [100/166] libraries/protocol/hardfork.d/0-preamble.hf:16-19 — HIVE_NUM_HARDFORKS = 28
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/hardfork.d/0-preamble.hf:16-19
STATUS: confirmed
REASON: Both the USE_ALTERNATE_CHAIN_ID branch (line 16) and the mainnet branch (line 19) define HIVE_NUM_HARDFORKS as 28, matching the claim verbatim.
SUGGESTED_FIX: none

### [101/166] libraries/protocol/include/hive/protocol/config.hpp:137-143 — Mainnet "beeab0de...", testnet, mirrornet
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:137-143
STATUS: confirmed
REASON: The excerpt shows mainnet HIVE_CHAIN_ID="beeab0de..." at line 142 and mirrornet HIVE_CHAIN_ID at line 137 within an #if/#else block whose structure implies a testnet branch above, supporting the three-network claim.
SUGGESTED_FIX: none

### [102/166] libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23 — Balance-seconds / year * rate
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23
STATUS: confirmed
REASON: Lines 12, 16-18 implement exactly balance-seconds accumulation, division by HIVE_SECONDS_PER_YEAR, and multiplication by the interest rate (normalized by HIVE_100_PERCENT).
SUGGESTED_FIX: none

### [103/166] libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26 — estimate_hive_collateral()` formula (uses ratio + fee constants from `config.hpp`)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26
STATUS: confirmed
REASON: The excerpt shows `estimate_hive_collateral()` at lines 8-26 using `HIVE_COLLATERALIZED_CONVERSION_FEE` (fee constant) and `HIVE_CONVERSION_COLLATERAL_RATIO` (ratio constant), matching the claim.
SUGGESTED_FIX: none

### [104/166] libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285 — All configurable defaults
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285
STATUS: confirmed
REASON: The cited range exactly spans the `configuration` class definition containing all configurable defaults (timing windows, supply values, witness settings, governance, proposals, recurrent transfers, RC stats, etc.) with their default values and getter/setter methods.
SUGGESTED_FIX: none

### [105/166] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Required authorities interface
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: The cited lines define `base_operation` with the full set of `get_required_*_authorities` methods plus `get_required_witness_signatures`, which is the required authorities interface the claim describes.
SUGGESTED_FIX: none

### [106/166] libraries/protocol/include/hive/protocol/operations.hpp:15-125 — Complete operation list with IDs
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/operations.hpp:15-125
STATUS: confirmed
REASON: The cited range contains the complete static_variant declaration listing all 50 regular operations (IDs 0-49) and all 43 virtual operations (last_regular + 1 through last_regular + 43), directly supporting the claim.
SUGGESTED_FIX: none

### [107/166] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Authority method signatures
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: Lines 13-23 define base_operation with all five authority method signatures (get_required_authorities, active/posting/owner authorities, witness_signatures), directly supporting the claim.
SUGGESTED_FIX: none

### [108/166] libraries/protocol/include/hive/protocol/types.hpp:151-161 — recurrent_transfer_pair_id, extensions
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:151-161
STATUS: confirmed
REASON: The excerpt defines `recurrent_transfer_pair_id` struct (line 151-154) and the `recurrent_transfer_extension`/`recurrent_transfer_extensions_type` (lines 156-161), directly supporting the claim.
SUGGESTED_FIX: none

### [109/166] libraries/chain/database.cpp:2183-2369 — _apply_block()` :2183-2369
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2183-2369
STATUS: confirmed
REASON: The function `database::_apply_block()` begins at line 2183 and ends at line 2369 in the source excerpt, matching the citation exactly.
SUGGESTED_FIX: none

### [110/166] libraries/chain/database.cpp:2757-2779 — `validate_block_header()` :2757-2779
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2757-2779
STATUS: confirmed
REASON: Lines 2757-2779 contain the `database::validate_block_header()` function definition exactly as cited, performing block header validation (previous hash, timestamp, witness signature, and schedule checks).
SUGGESTED_FIX: none

### [111/166] libraries/chain/database.cpp:2644-2702 — _apply_transaction()` :2644-2702
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2644-2702
STATUS: confirmed
REASON: The cited range exactly spans the `database::_apply_transaction()` function definition from its signature at line 2644 to its closing `FC_CAPTURE_AND_RETHROW` at line 2702.
SUGGESTED_FIX: none

### [112/166] libraries/chain/database.cpp:2521-2642 — `validate_transaction()` :2521-2642
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2521-2642
STATUS: confirmed
REASON: The cited line range exactly matches the `database::validate_transaction()` function definition, which performs expiration checks, TaPoS verification, operation validation, and authority verification as expected for a transaction validation routine.
SUGGESTED_FIX: none

### [113/166] libraries/chain/database.cpp:2722-2746 — apply_operation()` :2722-2746
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2722-2746
STATUS: confirmed
REASON: The cited lines 2722-2746 contain exactly the `database_impl::apply_operation()` function definition, matching the claim verbatim.
SUGGESTED_FIX: none

### [114/166] libraries/chain/witness_schedule.cpp:152-396 — update_witness_schedule4()` :152-396
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:152-396
STATUS: confirmed
REASON: The function `update_witness_schedule4(database&, const witness_schedule_object&)` is defined exactly at lines 152-396 in the cited file, matching the claim verbatim.
SUGGESTED_FIX: none

### [115/166] libraries/chain/witness_schedule.cpp:372-388 — shuffle :372-388
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:372-388
STATUS: confirmed
REASON: Lines 372-388 contain exactly the witness shuffle logic (xorshift RNG + Fisher-Yates swap over current_shuffled_witnesses), matching the claim verbatim.
SUGGESTED_FIX: none

### [116/166] libraries/chain/database.cpp:904-910 — get_scheduled_witness()` :904-910
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:904-910
STATUS: confirmed
REASON: The source excerpt at lines 904-910 shows the `get_scheduled_witness()` function definition exactly as cited, matching the claim verbatim.
SUGGESTED_FIX: none

### [117/166] libraries/chain/database.cpp:937-943 — `get_slot_at_time()` :937-943
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:937-943
STATUS: confirmed
REASON: Lines 937-943 contain the `get_slot_at_time()` function definition exactly as cited.
SUGGESTED_FIX: none

### [118/166] libraries/chain/database_witness.cpp:284-306 — update_witness_missed_blocks()` :284-306
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database_witness.cpp:284-306
STATUS: confirmed
REASON: The source excerpt at lines 284-306 contains the `update_witness_missed_blocks()` function definition exactly as cited.
SUGGESTED_FIX: none

### [119/166] libraries/chain/database.cpp:2789-2841 — update_global_dynamic_data()` :2789-2841
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2789-2841
STATUS: confirmed
REASON: The cited range exactly spans the `database::update_global_dynamic_data()` function definition, matching the claim verbatim.
SUGGESTED_FIX: none

### [120/166] libraries/chain/database.cpp:531-535 — `witness_participation_rate()` :531-535
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:531-535
STATUS: confirmed
REASON: The source at lines 531-535 defines `database::witness_participation_rate()` exactly as claimed.
SUGGESTED_FIX: none

### [121/166] libraries/chain/fork_database.cpp:73-99 — _push_block()` :73-99
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:73-99
STATUS: confirmed
REASON: The excerpt shows `fork_database::_push_block()` defined from line 73 through line 99, exactly matching the cited range.
SUGGESTED_FIX: none

### [122/166] libraries/chain/fork_database.cpp:20-28 — `pop_block()` :20-28
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:20-28
STATUS: confirmed
REASON: Lines 20-28 contain the complete `pop_block()` function definition exactly as cited.
SUGGESTED_FIX: none

### [123/166] libraries/chain/fork_database.cpp:290-330 — `fetch_branch_from()` :290-330
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:290-330
STATUS: confirmed
REASON: The cited lines contain the `fetch_branch_from()` function definition with the branch-walking logic to find the common ancestor, exactly as the claim references.
SUGGESTED_FIX: none

### [124/166] libraries/chain/sync_block_writer.cpp:162-264 — switch_forks()` :162-264
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:162-264
STATUS: confirmed
REASON: The source excerpt shows `switch_forks()` defined at lines 162-264 in `sync_block_writer.cpp`, matching the claim exactly.
SUGGESTED_FIX: none

### [125/166] libraries/chain/database.cpp:2956-3064 — update_last_irreversible_block()` :2956-3064
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2956-3064
STATUS: confirmed
REASON: The source at lines 2956-3064 contains the `database::update_last_irreversible_block()` function definition exactly as claimed, with the function signature on line 2956 and closing brace on line 3064.
SUGGESTED_FIX: none

### [126/166] libraries/chain/sync_block_writer.cpp:266-367 — find_new_last_irreversible_block()` :266-367
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:266-367
STATUS: confirmed
REASON: The source excerpt shows `find_new_last_irreversible_block()` defined exactly at lines 266-367 in the cited file, matching the claim verbatim.
SUGGESTED_FIX: none

### [127/166] libraries/chain/database.cpp:2899-2954 — process_fast_confirm_transaction()` :2899-2954
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2899-2954
STATUS: confirmed
REASON: The function `process_fast_confirm_transaction()` is defined at exactly lines 2899-2954 in the source excerpt, matching the claim verbatim.
SUGGESTED_FIX: none

### [128/166] libraries/chain/database.cpp:3066-3097 — migrate_irreversible_state()` :3066-3097
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:3066-3097
STATUS: confirmed
REASON: The cited line range exactly matches the `database::migrate_irreversible_state()` function definition, supporting the claim verbatim.
SUGGESTED_FIX: none

### [129/166] libraries/chain/block_log.cpp:338-366 — append_raw()` :338-366
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:338-366
STATUS: confirmed
REASON: Lines 338-366 contain two overloads of `block_log::append_raw()`, matching the claim's reference to `append_raw()` at this location.
SUGGESTED_FIX: none

### [130/166] libraries/chain/block_log.cpp:491-515 — read_block_by_num()` :491-515
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:491-515
STATUS: confirmed
REASON: The source excerpt shows `block_log::read_block_by_num()` defined exactly at lines 491-515, matching the citation verbatim.
SUGGESTED_FIX: none

### [131/166] libraries/chain/block_log_artifacts.cpp:46-69 — header :46-69
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_artifacts.cpp:46-69
STATUS: confirmed
REASON: Lines 46-69 contain the full `artifact_file_header` struct definition, matching the "header" reference in the claim.
SUGGESTED_FIX: none

### [132/166] libraries/chain/block_log_artifacts.cpp:82-166 — chunk :82-166
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_artifacts.cpp:82-166
STATUS: confirmed
REASON: Lines 82-166 contain the complete `artifact_file_chunk` struct definition, matching the "chunk" reference in the claim.
SUGGESTED_FIX: none

### [133/166] libraries/plugins/witness/witness_plugin.cpp:369-380 — schedule_production_loop()` :369-380
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:369-380
STATUS: confirmed
REASON: The function `schedule_production_loop()` is defined at line 369 and its body spans through the closing brace at line 380, exactly matching the cited range.
SUGGESTED_FIX: none

### [134/166] libraries/plugins/witness/witness_plugin.cpp:382-467 — `block_production_loop()` :382-467
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:382-467
STATUS: confirmed
REASON: The cited lines 382-467 contain the complete `block_production_loop()` function definition in `witness_plugin_impl`, exactly as claimed.
SUGGESTED_FIX: none

### [135/166] libraries/plugins/witness/block_producer.cpp:31-85 — _generate_block()` :31-85
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:31-85
STATUS: confirmed
REASON: The function `_generate_block()` is defined precisely at lines 31-85 as cited.
SUGGESTED_FIX: none

### [136/166] libraries/plugins/witness/block_producer.cpp:111-216 — `apply_pending_transactions()` :111-216
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:111-216
STATUS: confirmed
REASON: The function `apply_pending_transactions()` begins at line 111 with the signature declaration and ends at line 216 with its closing brace, exactly matching the cited range.
SUGGESTED_FIX: none

### [137/166] libraries/chain/include/hive/chain/block_flow_control.hpp:135-146 — Phase enum :135-146
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/include/hive/chain/block_flow_control.hpp:135-146
STATUS: confirmed
REASON: The cited lines 135-146 contain exactly the `phase` enum with all its values (REQUEST, START, FORK_DB, FORK_APPLY, FORK_IGNORE, FORK_NORMAL, TXS_EXECUTED, APPLIED, END) as referenced.
SUGGESTED_FIX: none

### [138/166] libraries/chain/database.cpp:1704 — process_funds()` at line 1704
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:1704
STATUS: confirmed
REASON: Line 1704 contains the definition `void database::process_funds()` exactly as the claim states.
SUGGESTED_FIX: none

### [139/166] libraries/chain/util/reward.cpp:34 — evaluate_reward_curve()` at line 34
Source: `07-economic-model.md`

CITATION: libraries/chain/util/reward.cpp:34
STATUS: confirmed
REASON: Line 34 contains the `evaluate_reward_curve()` function signature as claimed.
SUGGESTED_FIX: none

### [140/166] libraries/chain/database_comment.cpp:379 — process_comment_cashout()` at line 379
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:379
STATUS: confirmed
REASON: Line 379 contains the definition `void database::process_comment_cashout()`, exactly matching the claim.
SUGGESTED_FIX: none

### [141/166] libraries/chain/database_comment.cpp:129 — pay_curators()` at line 129
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:129
STATUS: confirmed
REASON: Line 129 contains the function signature `HIVE_asset database::pay_curators(...)` as claimed.
SUGGESTED_FIX: none

### [142/166] libraries/chain/database_comment.cpp:197 — cashout_comment_helper()` at line 197
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:197
STATUS: confirmed
REASON: Line 197 contains the definition of `database::cashout_comment_helper()` exactly as cited.
SUGGESTED_FIX: none

### [143/166] libraries/chain/database.cpp:949 — create_hbd()` at line 949
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:949
STATUS: confirmed
REASON: Line 949 contains the function definition `database::create_hbd(...)` matching the claim exactly.
SUGGESTED_FIX: none

### [144/166] libraries/chain/hive_evaluator_social.cpp:605 — hf20_vote_evaluator()` at line 605
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_social.cpp:605
STATUS: confirmed
REASON: Line 605 contains the function definition `void hf20_vote_evaluator(...)` as claimed.
SUGGESTED_FIX: none

### [145/166] libraries/chain/database.cpp:3186 — adjust_balance(HBD)` accrual logic at line 3186
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:3186
STATUS: confirmed
REASON: Line 3186 is the start of the `database::adjust_balance` overload for HBD_asset, which is the entry point for HBD balance accrual logic as the claim describes.
SUGGESTED_FIX: none

### [146/166] libraries/chain/database.cpp:3265 — adjust_savings_balance(HBD)` at line 3265
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:3265
STATUS: confirmed
REASON: Line 3265 contains the function signature `void database::adjust_savings_balance( const account_object& a, const HBD_asset& delta )`, which directly supports the claim about `adjust_savings_balance(HBD)` at that line.
SUGGESTED_FIX: none

### [147/166] libraries/protocol/include/hive/protocol/hbd_interest.hpp:9 — evaluate_hbd_interest()` at line 9
Source: `07-economic-model.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:9
STATUS: confirmed
REASON: The source excerpt at line 9 shows the `evaluate_hbd_interest()` function signature exactly as cited.
SUGGESTED_FIX: none

### [148/166] libraries/chain/database_conversion.cpp:34 — process_conversions()` at line 34
Source: `07-economic-model.md`

CITATION: libraries/chain/database_conversion.cpp:34
STATUS: confirmed
REASON: Line 34 contains the exact function definition `void database::process_conversions()` as claimed.
SUGGESTED_FIX: none

### [149/166] libraries/chain/hive_evaluator_transfer.cpp:473 — collateralized_convert_evaluator::do_apply()` at line 473
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:473
STATUS: confirmed
REASON: Line 473 contains the `collateralized_convert_evaluator::do_apply()` function definition exactly as claimed.
SUGGESTED_FIX: none

### [150/166] libraries/chain/util/dhf_processor.cpp:238 — make_payments()` at line 238
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:238
STATUS: confirmed
REASON: Line 238 contains the definition of `dhf_processor::make_payments`, matching the claim verbatim.
SUGGESTED_FIX: none

### [151/166] libraries/chain/util/dhf_processor.cpp:145 — calculate_maintenance_budget()` at line 145
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145
STATUS: confirmed
REASON: Line 145 contains the definition of `dhf_processor::calculate_maintenance_budget`, matching the claim verbatim.
SUGGESTED_FIX: none

### [152/166] libraries/chain/util/dhf_processor.cpp:325 — convert_funds()` at line 325
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:325
STATUS: confirmed
REASON: Line 325 contains the definition of `dhf_processor::convert_funds()`, matching the claim exactly.
SUGGESTED_FIX: none

### [153/166] libraries/chain/hive_evaluator_transfer.cpp:292 — transfer_to_vesting_evaluator::do_apply()` at line 292
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:292
STATUS: confirmed
REASON: Line 292 contains the function signature `void transfer_to_vesting_evaluator::do_apply(...)` exactly as claimed.
SUGGESTED_FIX: none

### [154/166] libraries/chain/hive_evaluator_transfer.cpp:327 — withdraw_vesting_evaluator::do_apply()` at line 327
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:327
STATUS: confirmed
REASON: Line 327 contains the function signature `void withdraw_vesting_evaluator::do_apply( const withdraw_vesting_operation& o )`, matching the claim verbatim.
SUGGESTED_FIX: none

### [155/166] libraries/chain/database_vesting.cpp:111 — process_vesting_withdrawals()` at line 111
Source: `07-economic-model.md`

CITATION: libraries/chain/database_vesting.cpp:111
STATUS: confirmed
REASON: Line 111 contains the definition `void database::process_vesting_withdrawals()`, exactly matching the cited function.
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
REASON: Line 2399 contains the definition `void database::update_median_feed()`, exactly matching the claim.
SUGGESTED_FIX: none

### [158/166] libraries/chain/database.cpp:2868 — update_virtual_supply()` at line 2868
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:2868
STATUS: confirmed
REASON: Line 2868 is the exact definition of `database::update_virtual_supply()`, matching the claim verbatim.
SUGGESTED_FIX: none

### [159/166] libraries/chain/database.cpp:2843 — calculate_HBD_percent()` at line 2843
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:2843
STATUS: confirmed
REASON: The source at line 2843 shows the function definition `uint16_t database::calculate_HBD_percent()`, exactly matching the claim.
SUGGESTED_FIX: none

### [160/166] libraries/chain/database_hardfork.cpp:336-416 — HF20 RC initialization
Source: `08-resource-credits.md`

CITATION: libraries/chain/database_hardfork.cpp:336-416
STATUS: confirmed
REASON: The cited line range covers the HIVE_HARDFORK_0_20 case which initializes RC parameters, creates rc_resource_param_object, rc_pool_object, rc_stats_objects, usage buckets, and sets rc_adjustment/rc_manabar on all accounts — directly supporting the "HF20 RC initialization" claim.
SUGGESTED_FIX: none

### [161/166] libraries/protocol/include/hive/protocol/config.hpp:390-494 — RC-related constants
Source: `08-resource-credits.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:390-494
STATUS: confirmed
REASON: The cited range contains the RC-related constants including HIVE_RD_* resource dynamics (393-403), account subsidy parameters (405-420), and the explicitly labeled "HIVE RC related constants" block (479-494) covering HIVE_RC_REGEN_TIME, bucket parameters, stats reporting, and delegation limits.
SUGGESTED_FIX: none

### [162/166] libraries/chain/witness_schedule.cpp:264-333 — Hardfork voting mechanism
Source: `09-hardfork-history.md`

CITATION: libraries/chain/witness_schedule.cpp:264-333
STATUS: confirmed
REASON: The excerpt shows the hardfork voting mechanism — collecting witness running versions and hardfork version/time votes from scheduled witnesses, then updating majority_version and next_hardfork when votes meet hardfork_required_witnesses threshold.
SUGGESTED_FIX: none

### [163/166] libraries/chain/database.cpp:61-71 — next_hf_time()` for HF28
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:61-71
STATUS: confirmed
REASON: The cited lines define `next_hf_time()` with a comment explicitly stating "current 'next hardfork' is HF28", directly supporting the claim.
SUGGESTED_FIX: none

### [164/166] libraries/chain/database.cpp:1461-1540 — clear_account()` / `clear_accounts()` for HF23
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:1461-1540
STATUS: confirmed
REASON: The cited lines contain the `clear_accounts()` and `clear_account()` function definitions used for HF23 account clearing, matching the claim verbatim.
SUGGESTED_FIX: none

### [165/166] libraries/chain/database.cpp:1422-1458 — restore_accounts()` for HF24
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:1422-1458
STATUS: confirmed
REASON: The source at lines 1422-1458 defines `database::restore_accounts()` which restores HBD and HIVE balances from `h23_balances` to accounts via the treasury, matching the claim about HF24's restore_accounts() function.
SUGGESTED_FIX: none

### [166/166] libraries/chain/database_dhf.cpp:146 — remove_proposal_votes_for_accounts_without_voting_rights()` for HF28
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_dhf.cpp:146
STATUS: confirmed
REASON: The source at line 146 shows the exact function definition `database::remove_proposal_votes_for_accounts_without_voting_rights()` referenced in the claim.
SUGGESTED_FIX: none

## Summary

| Status | Count |
|--------|------:|
| confirmed  | 166 |
| drifted    | 0 |
| broken     | 0 |
| unparseable| 0 |
