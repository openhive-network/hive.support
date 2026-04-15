# Verification Report

- Topic: `hive-core`
- Pinned: `develop@2026-04-02` (`44c3fd880`)
- Run: 2026-04-15T07:53:51+02:00
- Citations audited: 165


### [1/165] libraries/protocol/include/hive/protocol/config.hpp:56-458 — All timing/economic/size constants
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56-458
STATUS: confirmed
REASON: The cited range covers all timing constants (BLOCK_INTERVAL, CASHOUT_WINDOW_SECONDS, etc.), economic constants (INFLATION_RATE, CONTENT_REWARD_PERCENT, HBD interest/limits, etc.), and size constants (MAX_BLOCK_SIZE, MAX_MEMO_SIZE, MAX_TRANSACTION_SIZE, etc.) as claimed.
SUGGESTED_FIX: none

### [2/165] libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-53 — NAI bit layout and encoding
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-53
STATUS: confirmed
REASON: Lines 9-53 define the complete NAI bit layout (precision bits, control bits, shift), reserved NAI values for native assets, asset_num encoding formulas, and symbol serialization constants, directly supporting the cited claim.
SUGGESTED_FIX: none

### [3/165] libraries/protocol/include/hive/protocol/asset.hpp:21-186 — Asset struct and price
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:21-186
STATUS: confirmed
REASON: Lines 21-96 define `struct asset` (fields: amount, symbol; arithmetic/comparison operators with symbol-match assertions), lines 98-127 define `struct legacy_asset`, and lines 139-186 define `struct price` (fields: base, quote; validate, max, min), all matching the "Asset struct and price" claim.
SUGGESTED_FIX: none

### [4/165] libraries/protocol/asset.cpp:128-286 — Asset validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/asset.cpp:128-286
STATUS: confirmed
REASON: Lines 128-286 contain asset symbol validation logic including NAI range/checksum validation (`asset_num_from_nai`), decimal-place enforcement for HIVE/HBD/VESTS, space determination, and the `validate()` method that checks all SMT asset_num invariants.
SUGGESTED_FIX: none

### [5/165] libraries/protocol/include/hive/protocol/authority.hpp:7-55 — Authority struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/authority.hpp:7-55
STATUS: confirmed
REASON: The source excerpt shows the complete `authority` struct definition at exactly lines 7-55, matching the claimed location with all fields (weight_threshold, account_auths, key_auths), classification enum, and member functions intact.
SUGGESTED_FIX: none

### [6/165] libraries/protocol/authority.cpp:58-122 — Account name validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/authority.cpp:58-122
STATUS: confirmed
REASON: The source excerpt shows the `check_account_name` function at exactly lines 58-122, implementing account name validation (length, segment, and character checks), which matches the KB citation precisely.
SUGGESTED_FIX: none

### [7/165] libraries/protocol/include/hive/protocol/operations.hpp:15-125 — Operation variant (93 types: 50 regular + 43 virtual)
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/operations.hpp:15-125
STATUS: confirmed
REASON: The source excerpt shows exactly 50 regular operations (indices 0-49, lines 16-74) and 43 virtual operations (last_regular + 1 through last_regular + 43, lines 80-122), totaling 93 types as claimed.
SUGGESTED_FIX: none

### [8/165] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Base operation class
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: The source excerpt shows `base_operation` (lines 13-23) and `virtual_operation` (lines 25-29) exactly at the cited lines, matching the claim of a base operation class with authority, validation, and virtuality methods.
SUGGESTED_FIX: none

### [9/165] libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-17 — RC custom operations
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-17
STATUS: confirmed
REASON: The excerpt shows the `delegate_rc_operation` struct definition (the sole RC custom operation) with its fields, validation, and posting authority requirement, directly supporting the "RC custom operations" claim.
SUGGESTED_FIX: none

### [10/165] libraries/protocol/hive_operations.cpp:1-866 — Operation validate() methods
Source: `00-consolidated.md`

CITATION: libraries/protocol/hive_operations.cpp:1-866
STATUS: confirmed
REASON: The file contains validate() method implementations for numerous operations (account_create, comment, transfer, vote, escrow, etc.) spanning the full cited range, directly supporting the claim about operation validate() methods.
SUGGESTED_FIX: none

### [11/165] libraries/protocol/dhf_operations.cpp:1-62 — DHF operation validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/dhf_operations.cpp:1-62
STATUS: confirmed
REASON: The source excerpt covers the complete file with validation logic for all four DHF operations (create_proposal, update_proposal, update_proposal_votes, remove_proposal), matching the cited claim of DHF operation validation.
SUGGESTED_FIX: none

### [12/165] libraries/protocol/include/hive/protocol/block_header.hpp:15-26 — Block header struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/block_header.hpp:15-26
STATUS: confirmed
REASON: The source excerpt shows the complete `block_header` struct definition at exactly the cited lines with fields `previous`, `timestamp`, `witness`, `transaction_merkle_root`, and `extensions`, matching the claimed block header struct.
SUGGESTED_FIX: none

### [13/165] libraries/protocol/include/hive/protocol/transaction.hpp:12-53 — Transaction struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-53
STATUS: confirmed
REASON: The source excerpt shows the complete `transaction` struct at exactly lines 12-53, matching the cited location and content verbatim.
SUGGESTED_FIX: none

### [14/165] libraries/protocol/transaction.cpp:40-55 — Transaction validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/transaction.cpp:40-55
STATUS: confirmed
REASON: The source excerpt shows `transaction::validate()` at lines 40-45 enforcing non-empty operations and validating each operation, plus the notify-variant overload at lines 47-56, directly supporting the "transaction validation" claim.
SUGGESTED_FIX: none

### [15/165] libraries/protocol/include/hive/protocol/version.hpp:15-77 — Version encoding
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:15-77
STATUS: confirmed
REASON: Lines 15-77 contain the complete `version` struct showing the packed uint32_t encoding with major (bits 24-31), hardfork (bits 16-23), and release (bits 0-15) fields, plus HF24 major-version compatibility logic — directly supporting the "Version encoding" claim.
SUGGESTED_FIX: none

### [16/165] libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30 — Hardfork block numbers
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30
STATUS: confirmed
REASON: The source excerpt at lines 3-30 contains exactly the hardfork block number defines (HF0.1 through HF1.28) as claimed, matching the cited file and line range verbatim.
SUGGESTED_FIX: none

### [17/165] libraries/protocol/include/hive/protocol/config.hpp:137-143 — Chain IDs
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:137-143
STATUS: confirmed
REASON: The excerpt shows the exact chain ID definitions for mirrornet (`4200...`) and mainnet (`beeab0de...`) at the cited lines, directly supporting the "Chain IDs" claim.
SUGGESTED_FIX: none

### [18/165] libraries/protocol/include/hive/protocol/validation.hpp:64-115 — Validation helpers
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/validation.hpp:64-115
STATUS: confirmed
REASON: Lines 64-115 contain exactly the validation helper functions claimed — `validate_string_max_size`, `validate_is_utf8`, `validate_string_is_not_empty`, `validate_number_in_100_percent_range`, `validate_account_name`, and `validate_permlink`.
SUGGESTED_FIX: none

### [19/165] libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23 — HBD interest calc
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23
STATUS: confirmed
REASON: The source excerpt at lines 8-23 contains the complete `evaluate_hbd_interest` static method implementing the dollar-seconds accumulator pattern, matching the code reference table entry "HBD interest calc."
SUGGESTED_FIX: none

### [20/165] libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26 — Collateral estimation
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26
STATUS: confirmed
REASON: The source excerpt shows the `estimate_hive_collateral` static method at exactly lines 8-26, implementing collateral estimation using `multiply_with_fee`, `HIVE_COLLATERALIZED_CONVERSION_FEE`, and `HIVE_CONVERSION_COLLATERAL_RATIO`, which directly supports the "Collateral estimation" claim.
SUGGESTED_FIX: none

### [21/165] libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285 — Testnet overrides
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285
STATUS: confirmed
REASON: Lines 27-285 contain the full `configuration` class defining all testnet-overridable parameters (cashout windows, voting windows, feed intervals, governance voting, initial supply, RC settings, etc.) with shorter defaults than mainnet.
SUGGESTED_FIX: none

### [22/165] libraries/chain/database.cpp:2183-2369 — Block application (`_apply_block`)
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2183-2369
STATUS: confirmed
REASON: The source excerpt shows the complete `_apply_block` method at exactly lines 2183-2369, matching the claimed function name, file, and line range verbatim.
SUGGESTED_FIX: none

### [23/165] libraries/chain/database.cpp:2757-2779 — Block header validation
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2757-2779
STATUS: confirmed
REASON: The source excerpt shows `validate_block_header` at exactly lines 2757-2779, performing previous-block linkage, timestamp ordering, witness signing key, and schedule checks, which directly supports the "block header validation" claim.
SUGGESTED_FIX: none

### [24/165] libraries/chain/database.cpp:2644-2702 — Transaction application
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2644-2702
STATUS: confirmed
REASON: The source excerpt shows the complete `_apply_transaction` method performing duplicate check, validation, transaction object creation, pre-apply notification, RC reset, operation-by-operation application via `apply_operation`, RC finalization, and post-apply notification, which directly supports the "Transaction application" claim.
SUGGESTED_FIX: none

### [25/165] libraries/chain/database.cpp:2722-2746 — Operation dispatch
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2722-2746
STATUS: confirmed
REASON: The excerpt shows `database_impl::apply_operation` which is the canonical operation dispatch path: pre-notify, RC discount, `_evaluator_registry.get_evaluator(op).apply(op)`, post-notify — directly supporting an "operation dispatch" claim.
SUGGESTED_FIX: none

### [26/165] libraries/chain/database.cpp:2956-3064 — LIB calculation
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2956-3064
STATUS: confirmed
REASON: The cited lines contain the complete `update_last_irreversible_block()` function, which implements the LIB calculation including the pre-voting fallback, replay-mode nth_element algorithm, and fork-db-based `find_new_last_irreversible_block` path with fast-confirm cleanup.
SUGGESTED_FIX: none

### [27/165] libraries/chain/database.cpp:2899-2954 — Fast confirm processing
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2899-2954
STATUS: confirmed
REASON: The source excerpt at the cited lines shows the complete `process_fast_confirm_transaction` method, which validates HF26 gating, checks witness scheduling, deduplicates by tracking per-witness approvals, and triggers irreversibility updates — directly supporting the "fast confirm processing" claim.
SUGGESTED_FIX: none

### [28/165] libraries/chain/database.cpp:3066-3097 — Irreversibility migration
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:3066-3097
STATUS: confirmed
REASON: The source excerpt shows the `migrate_irreversible_state` function exactly at lines 3066-3097, matching the claimed location and demonstrating the irreversibility migration logic (store block, commit undo state, notify irreversible blocks) as described.
SUGGESTED_FIX: none

### [29/165] libraries/chain/database.cpp:2789-2841 — Participation tracking
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2789-2841
STATUS: confirmed
REASON: The source excerpt directly shows participation tracking via the `participation_count` and `recent_slots_filled` fields being updated in a sliding-window bitfield loop within `update_global_dynamic_data`, exactly matching the claimed behavior.
SUGGESTED_FIX: none

### [30/165] libraries/chain/database.cpp:2843-2868 — HBD print rate / virtual supply
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2843-2868
STATUS: confirmed
REASON: Lines 2843-2866 implement `calculate_HBD_percent()` which computes the HBD debt ratio against virtual supply (the print rate gate), and line 2868 begins `update_virtual_supply()`, directly supporting the "HBD print rate / virtual supply" claim.
SUGGESTED_FIX: none

### [31/165] libraries/chain/database.cpp:1704 — Inflation distribution
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:1704
STATUS: confirmed
REASON: Line 1704 is `void database::process_funds()`, the function responsible for inflation distribution (vesting/reward shares per block, liquidity shares daily), directly supporting the claim.
SUGGESTED_FIX: none

### [32/165] libraries/chain/database.cpp:61-71 — next_hf_time()
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:61-71
STATUS: confirmed
REASON: The source excerpt shows the `next_hf_time()` function at exactly lines 61-71, matching the cited location and claim.
SUGGESTED_FIX: none

### [33/165] libraries/chain/database.cpp:1422-1540 — Account clearing/restoration
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:1422-1540
STATUS: confirmed
REASON: The excerpt directly contains `restore_accounts()` (line 1422), `clear_accounts()` (line 1461), and `clear_account()` (line 1474), which collectively implement HF23 account clearing and balance restoration via the treasury.
SUGGESTED_FIX: none

### [34/165] libraries/chain/hive_evaluator_transfer.cpp:75-957 — Transfer evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:75-957
STATUS: confirmed
REASON: The source excerpt spans lines 75–957 and contains all transfer-related evaluators (escrow_transfer, escrow_approve, escrow_dispute, escrow_release, transfer, transfer_to_vesting, withdraw_vesting, set_withdraw_vesting_route, convert, collateralized_convert, limit_order_create/create2/cancel, transfer_to/from_savings, cancel_transfer_from_savings, claim_reward_balance, delegate_vesting_shares, recurrent_transfer), confirming the "Transfer evaluators" claim.
SUGGESTED_FIX: none

### [35/165] libraries/chain/hive_evaluator_account.cpp:130-657 — Account evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_account.cpp:130-657
STATUS: confirmed
REASON: Lines 130-657 contain all account evaluators: create_account helper, account_create, account_create_with_delegation, account_update, account_update2, claim_account, create_claimed_account, request_account_recovery, recover_account, change_recovery_account, decline_voting_rights, reset_account, and set_reset_account evaluators, exactly matching the "Account evaluators" claim.
SUGGESTED_FIX: none

### [36/165] libraries/chain/hive_evaluator_social.cpp:55-864 — Social evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_social.cpp:55-864
STATUS: confirmed
REASON: Lines 55–864 contain the complete social evaluator implementations (delete_comment_evaluator, comment_options_evaluator, comment_evaluator, pre_hf20_vote_evaluator, hf20_vote_evaluator, vote_evaluator) exactly as claimed, with the file ending at line 866.
SUGGESTED_FIX: none

### [37/165] libraries/chain/hive_evaluator.cpp:62-628 — Witness/custom/pow evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator.cpp:62-628
STATUS: confirmed
REASON: Lines 62-628 contain exactly the witness evaluators (witness_update, witness_set_properties, account_witness_proxy, account_witness_vote, feed_publish, witness_block_approve), custom evaluators (custom, custom_json, custom_binary), and pow evaluators (pow, pow2) as claimed.
SUGGESTED_FIX: none

### [38/165] libraries/chain/dhf_evaluator.cpp:32-252 — DHF evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/dhf_evaluator.cpp:32-252
STATUS: confirmed
REASON: Lines 32-252 contain all four DHF evaluator implementations (create_proposal, update_proposal, update_proposal_votes, remove_proposal) exactly as cited.
SUGGESTED_FIX: none

### [39/165] libraries/chain/database_comment.cpp:129-379 — Comment cashout/curation
Source: `00-consolidated.md`

CITATION: libraries/chain/database_comment.cpp:129-379
STATUS: confirmed
REASON: Lines 129-195 contain `pay_curators()` and lines 197-377 contain `cashout_comment_helper()`, which together implement the full comment cashout and curation reward distribution logic as claimed.
SUGGESTED_FIX: none

### [40/165] libraries/chain/witness_schedule.cpp:152-396 — Witness scheduling
Source: `00-consolidated.md`

CITATION: libraries/chain/witness_schedule.cpp:152-396
STATUS: confirmed
REASON: The excerpt at lines 152-396 contains the complete `update_witness_schedule4` function covering elected/miner/timeshare witness selection, virtual time scheduling, xorshift shuffle, and hardfork version voting — all core witness scheduling logic.
SUGGESTED_FIX: none

### [41/165] libraries/chain/database_witness.cpp:284-306 — Witness missed blocks
Source: `00-consolidated.md`

CITATION: libraries/chain/database_witness.cpp:284-306
STATUS: confirmed
REASON: The source excerpt at the cited lines directly implements witness missed block tracking — incrementing `total_missed`, emitting `producer_missed_operation`, and conditionally disabling witnesses via `shutdown_witness_operation` — which fully supports the "Witness missed blocks" claim.
SUGGESTED_FIX: none

### [42/165] libraries/chain/fork_database.cpp:20-330 — Fork database
Source: `00-consolidated.md`

CITATION: libraries/chain/fork_database.cpp:20-330
STATUS: confirmed
REASON: The source excerpt at lines 20-330 contains the core fork_database implementation (pop_block, push_block, _push_block, _push_next, set_max_size, fetch_block, fetch_branch_from, etc.), directly supporting the "Fork database" claim.
SUGGESTED_FIX: none

### [43/165] libraries/chain/sync_block_writer.cpp:162-367 — Fork switching
Source: `00-consolidated.md`

CITATION: libraries/chain/sync_block_writer.cpp:162-367
STATUS: confirmed
REASON: Lines 162-264 contain the `switch_forks()` method implementing fork switching (pop old branch, push new branch, handle failures, restore original fork), and lines 266-367 contain the related `find_new_last_irreversible_block()` method — both directly support the "Fork switching" claim.
SUGGESTED_FIX: none

### [44/165] libraries/chain/block_log.cpp:338-515 — Block log read/write
Source: `00-consolidated.md`

CITATION: libraries/chain/block_log.cpp:338-515
STATUS: confirmed
REASON: The cited lines contain the block log's core append (write) and read methods — `append_raw`, `multi_append_raw`, `append`, `read_raw_block_data_by_num`, `read_block_id_by_num`, and `read_block_by_num` — which directly support the "block log read/write" claim.
SUGGESTED_FIX: none

### [45/165] libraries/chain/block_log_artifacts.cpp:46-166 — Block log artifacts
Source: `00-consolidated.md`

CITATION: libraries/chain/block_log_artifacts.cpp:46-166
STATUS: confirmed
REASON: Lines 46-166 define the two core block log artifact structs (`artifact_file_header` and `artifact_file_chunk`) including file format versioning, block position/compression flags bitfield layout, and block ID packing, directly supporting the "Block log artifacts" claim.
SUGGESTED_FIX: none

### [46/165] libraries/chain/include/hive/chain/hive_object_types.hpp:47-89 — Object type enum (39 IDs)
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/hive_object_types.hpp:47-89
STATUS: confirmed
REASON: The enum at lines 47-89 contains exactly 39 enumerator values (dynamic_global_property_object_type through rc_expired_delegation_object_type), matching the claimed count.
SUGGESTED_FIX: none

### [47/165] libraries/chain/include/hive/chain/detail/state/account_object.hpp:339 — account_authority_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/account_object.hpp:339
STATUS: confirmed
REASON: The source at line 339 shows the `account_authority_object` class declaration exactly as cited.
SUGGESTED_FIX: none

### [48/165] libraries/chain/include/hive/chain/detail/state/comment_object.hpp:372 — comment_vote_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/comment_object.hpp:372
STATUS: confirmed
REASON: Line 372 contains the `comment_vote_object` class definition exactly as cited.
SUGGESTED_FIX: none

### [49/165] libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:69 — witness_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:69
STATUS: confirmed
REASON: The source at line 69 shows the `witness_object` class definition exactly as cited.
SUGGESTED_FIX: none

### [50/165] libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:183 — witness_schedule_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:183
STATUS: confirmed
REASON: Line 183 contains the `witness_schedule_object` class definition exactly as cited.
SUGGESTED_FIX: none

### [51/165] libraries/chain/rc/rc_utility.cpp:547-581 — Non-consensus enforcement
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:547-581
STATUS: confirmed
REASON: The code confirms non-consensus RC enforcement: line 547 shows RC is only asserted when `is_in_control()` (mempool validation), while the else branch at line 562-581 merely logs insufficient RC during block processing instead of rejecting, and line 545's FC_TODO explicitly notes RC is not yet part of consensus.
SUGGESTED_FIX: none

### [52/165] libraries/chain/rc/rc_utility.cpp:799-831 — Mana deduction (finalize_tx)
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:799-831
STATUS: confirmed
REASON: The source excerpt shows `finalize_transaction` at lines 799-831 performing exactly the claimed mana deduction flow: counting resources, computing RC cost, and calling `use_account_rcs` to deduct mana.
SUGGESTED_FIX: none

### [53/165] libraries/chain/rc/rc_utility.cpp:26-110 — RC delegation mechanics
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:26-110
STATUS: confirmed
REASON: Lines 26-110 contain the complete `delegate_rc_evaluator::do_apply` implementation covering HF26 gating, minimum delegation threshold, create/update/delete delegation logic, mana regeneration, re-delegation prevention, and delegable RC sufficiency checks — fully supporting the "RC delegation mechanics" claim.
SUGGESTED_FIX: none

### [54/165] libraries/chain/rc/rc_utility.cpp:401-443 — Delegation overflow
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:401-443
STATUS: confirmed
REASON: The cited lines directly implement RC delegation overflow detection (line 408), removal of excess delegations with a per-block object limit (lines 413-435), and adjustment of `delegated_rc` (lines 438-441), exactly matching the "Delegation overflow" claim.
SUGGESTED_FIX: none

### [55/165] libraries/chain/rc/rc_utility.cpp:505-537 — Flood surcharge
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:505-537
STATUS: confirmed
REASON: The excerpt shows the flood surcharge mechanism exactly as described — calculating a surcharge based on mempool fullness relative to flood_level, with privileged witness operations exempted, and the surcharge added to the RC cost check.
SUGGESTED_FIX: none

### [56/165] libraries/chain/rc/resource_count.cpp:136-631 — Resource counting
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_count.cpp:136-631
STATUS: confirmed
REASON: The cited range covers the complete resource counting implementation: the `handle_operation_discount` differential usage mechanism (lines 136-168), the `count_operation_visitor` with per-operation cost handlers for all 5 resource types (lines 170-570), and the `resource_credits::count_resources` aggregation function (lines 572-631).
SUGGESTED_FIX: none

### [57/165] libraries/chain/rc/resource_sizes.cpp:45-165 — State byte sizes
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_sizes.cpp:45-165
STATUS: confirmed
REASON: Lines 45-165 contain the complete `state_object_size_info` constructor defining all RC state byte size costs (TEMPORARY, LASTING, PERSISTENT multipliers and per-operation object sizes), exactly matching the index entry's claim.
SUGGESTED_FIX: none

### [58/165] libraries/chain/rc/resource_sizes.cpp:167-242 — Execution time benchmarks
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_sizes.cpp:167-242
STATUS: confirmed
REASON: The cited lines contain the `operation_exec_info` constructor with detailed execution time benchmarks (in nanoseconds) for all operations, exactly matching the claim of "execution time benchmarks."
SUGGESTED_FIX: none

### [59/165] libraries/chain/rc/rc_curve.cpp:32-98 — Price curve computation
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_curve.cpp:32-98
STATUS: confirmed
REASON: The excerpt contains the `generate_rc_curve_params` function at exactly lines 32-98, implementing the price curve computation with coefficients A (coeff_a, shift) and B (coeff_b) derived from decay, elasticity, and pool equilibrium parameters.
SUGGESTED_FIX: none

### [60/165] libraries/chain/util/rd.cpp:23-118 — Pool dynamics (decay)
Source: `00-consolidated.md`

CITATION: libraries/chain/util/rd.cpp:23-118
STATUS: confirmed
REASON: Lines 23-118 contain `rd_compute_pool_decay()`, `rd_apply()`, and `rd_setup_dynamics_params()` which directly implement pool dynamics and decay mechanics including decay computation, budget-decay balance, and equilibrium calculation.
SUGGESTED_FIX: none

### [61/165] libraries/chain/include/hive/chain/util/manabar.hpp:42-141 — Manabar struct
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/util/manabar.hpp:42-141
STATUS: confirmed
REASON: The source excerpt at lines 42-141 contains the manabar struct's core methods (regenerate_mana, has_mana, use_mana) and the update_manabar helper function, confirming the "Manabar struct" claim; however, note that the KB table in 00-consolidated.md line 617 lists the path as `include/hive/chain/rc/manabar.hpp` (wrong subdirectory — should be `util/`, as the namespace `hive::chain::util` confirms).
SUGGESTED_FIX: none

### [62/165] libraries/chain/util/dhf_processor.cpp:145-325 — DHF payment processing
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145-325
STATUS: confirmed
REASON: Lines 145-325 contain the complete DHF payment processing pipeline: budget calculation, proposal sorting by votes, payment transfers with budget cap, maintenance period scheduling, old proposal removal, funding recording, and the top-level `run()` entry point — all directly supporting the "DHF payment processing" claim.
SUGGESTED_FIX: none

### [63/165] libraries/chain/util/dhf_processor.cpp:145 — DHF budget calculation
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145
STATUS: confirmed
REASON: Line 145 is the signature of `calculate_maintenance_budget`, which is precisely the DHF budget calculation function the claim references.
SUGGESTED_FIX: none

### [64/165] libraries/chain/util/dhf_processor.cpp:325 — DHF HIVE->HBD conversion
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:325
STATUS: confirmed
REASON: Line 325 defines `dhf_processor::convert_funds()` with a daily-maintenance-period gate, directly supporting the claim about DHF HIVE->HBD conversion.
SUGGESTED_FIX: none

### [65/165] libraries/protocol/include/hive/protocol/config.hpp:56 — HIVE_BLOCK_INTERVAL = 3
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56
STATUS: confirmed
REASON: Line 56 defines `HIVE_BLOCK_INTERVAL` as `3`, exactly matching the claim.
SUGGESTED_FIX: none

### [66/165] libraries/protocol/include/hive/protocol/config.hpp:56-207 — Block, cashout, recovery, feed timings
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56-207
STATUS: confirmed
REASON: Lines 56-207 contain all four timing categories: block interval/blocks-per-day (56-60), cashout windows and upvote lockout (155-162), owner auth recovery and account recovery expiration (167-170), and feed interval/history window/max feed age (189-196).
SUGGESTED_FIX: none

### [67/165] libraries/protocol/include/hive/protocol/config.hpp:215-346 — Inflation, rewards, HBD limits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:215-346
STATUS: confirmed
REASON: Lines 257-259 define inflation rate constants (start 978, stop 95, narrowing period 250000), lines 260-265 define reward distribution percentages (content, vesting, proposal for HF16 and HF21), and lines 339-346 define HBD market cap limits (start/stop/hard limit for HF14, HF20, HF26).
SUGGESTED_FIX: none

### [68/165] libraries/protocol/include/hive/protocol/config.hpp:348-399 — Transaction, block, name, URL sizes and miscellaneous limits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:348-399
STATUS: confirmed
REASON: Lines 348-399 contain exactly the claimed transaction, block, name, URL size limits and miscellaneous constants (account name 3-16, permlink 0-256, witness URL 2048, max transaction 64KB, max block 2MB, min block 115, max authority membership 40, max URL 127, etc.).
SUGGESTED_FIX: none

### [69/165] libraries/protocol/include/hive/protocol/config.hpp:441-458 — null, temp, miners, proxy-to-self, root-post-parent, plus OBSOLETE/NEW treasury constants (treasury name resolved via `database::get_treasury_name()`)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:441-458
STATUS: confirmed
REASON: The source excerpt at lines 441-458 defines exactly the reserved accounts listed in the claim (null, temp, miners, proxy-to-self, root-post-parent) plus the OBSOLETE/NEW treasury constants with the comment directing use of `database::get_treasury_name()`.
SUGGESTED_FIX: none

### [70/165] libraries/protocol/include/hive/protocol/config.hpp:460-469 — Proposal system
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:460-469
STATUS: confirmed
REASON: The source excerpt at lines 460-469 defines the Hive Proposal System constants (treasury fee, subject max length, max IDs, fee increase schedule, conversion rate), directly supporting the "Proposal system" claim.
SUGGESTED_FIX: none

### [71/165] libraries/protocol/include/hive/protocol/config.hpp:479-494 — Resource credits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:479-494
STATUS: confirmed
REASON: The source excerpt at lines 479-494 contains the RC-related constants (regen time, bucket time, window bucket count, stats report frequency, historical account creation adjustment, max accounts per delegation op) exactly as cited.
SUGGESTED_FIX: none

### [72/165] libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-32 — Precision bits, shift, NAI encoding
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-32
STATUS: confirmed
REASON: Lines 9-32 define exactly the precision bits (4), control bits (1), NAI shift (5), per-asset precisions (HBD=3, HIVE=3, VESTS=6), reserved NAI values (1,2,3), and the ASSET_NUM encoding formula `(NAI << shift) | precision`, all matching the claim.
SUGGESTED_FIX: none

### [73/165] libraries/protocol/include/hive/protocol/asset_symbol.hpp:20-22 — HBD=3, HIVE=3, VESTS=6
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:20-22
STATUS: confirmed
REASON: Lines 20-22 define HIVE_PRECISION_HBD as 3, HIVE_PRECISION_HIVE as 3, and HIVE_PRECISION_VESTS as 6, exactly matching the claim.
SUGGESTED_FIX: none

### [74/165] libraries/protocol/include/hive/protocol/asset_symbol.hpp:36-53 — STEEM/SBD/TESTS/TBD/HIVE/HBD/VESTS
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:36-53
STATUS: confirmed
REASON: Lines 36-53 define all seven symbol names exactly as claimed: VESTS (lines 36,43), TESTS (line 37 via OBSOLETE on testnet), STEEM (line 44 via OBSOLETE on mainnet), HIVE (lines 38,45), TBD (line 39 via OBD on testnet), SBD (line 46 via OBD on mainnet), and HBD (lines 40,47).
SUGGESTED_FIX: none

### [75/165] libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216 — Legacy vs NAI pack/unpack
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216
STATUS: confirmed
REASON: The source excerpt shows exactly the legacy vs NAI pack/unpack logic at the cited lines — pack() branches on legacy_space to serialize HIVE/HBD/VESTS as their obsolete symbol constants, otherwise serializes the raw asset_num; unpack() switches on the first 4 bytes to detect legacy symbols or falls through to raw NAI deserialization.
SUGGESTED_FIX: none

### [76/165] libraries/protocol/include/hive/protocol/asset.hpp:21-96 — Amount + symbol with operator overloads
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:21-96
STATUS: confirmed
REASON: The `asset` struct at lines 21-96 contains `amount` and `symbol` fields with operator overloads for `+=`, `-=`, unary `-`, `==`, `<`, `<=`, `!=`, `>`, `>=`, binary `-`, and binary `+`, exactly matching the claim.
SUGGESTED_FIX: none

### [77/165] libraries/protocol/include/hive/protocol/asset.hpp:139-186 — Base/quote pair
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:139-186
STATUS: confirmed
REASON: The `price` struct at lines 139-186 clearly contains `asset base` and `asset quote` members (lines 141-142), confirming the "base/quote pair" claim verbatim.
SUGGESTED_FIX: none

### [78/165] libraries/protocol/include/hive/protocol/asset.hpp:218-261 — Typed thin wrappers
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:218-261
STATUS: confirmed
REASON: The source excerpt shows `tiny_asset` as a template struct parameterized on a symbol constant, wrapping only a `share_type amount` with conversions to/from the full `asset` type, which directly supports the "typed thin wrappers" claim.
SUGGESTED_FIX: none

### [79/165] libraries/protocol/include/hive/protocol/asset.hpp:268-322 — Typed price wrappers
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:268-322
STATUS: confirmed
REASON: The source excerpt shows the `tiny_price` template class at exactly lines 268-322, which is a typed price wrapper using template parameters for base and quote symbol types with compile-time type checking, matching the claim verbatim.
SUGGESTED_FIX: none

### [80/165] libraries/protocol/asset.cpp:80-126 — 8-digit Damm algorithm
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:80-126
STATUS: confirmed
REASON: The source at lines 80-126 implements exactly an 8-digit Damm algorithm checksum, with MAX_DAMM_VALUE of 100000000 (10^8) and extraction of 8 digits (d0-d7), matching the claim verbatim.
SUGGESTED_FIX: none

### [81/165] libraries/protocol/asset.cpp:261-283 — NAI range + control bit checks
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:261-283
STATUS: confirmed
REASON: The source excerpt shows `asset_symbol_type::validate()` at lines 261-283 performing exactly the described NAI range checks (SMT_MIN_NAI/SMT_MAX_NAI), control bit check (SMT_ASSET_NUM_CONTROL_MASK), and decimal places check, matching the claim.
SUGGESTED_FIX: none

### [82/165] libraries/protocol/asset.cpp:310-325 — uint128 cross-multiplication
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:310-325
STATUS: confirmed
REASON: The source shows `uint128_t result` used for cross-multiplication of asset amount by price numerator before dividing by denominator (lines 313, 316, 322), exactly matching the claimed uint128 cross-multiplication pattern.
SUGGESTED_FIX: none

### [83/165] libraries/protocol/asset.cpp:337-340 — Returns `HIVE_MAX_SATOSHIS
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:337-340
STATUS: confirmed
REASON: The source excerpt shows `price::max_satoshis()` returning `HIVE_MAX_SATOSHIS` at exactly the cited lines, matching the claim verbatim.
SUGGESTED_FIX: none

### [84/165] libraries/protocol/include/hive/protocol/types.hpp:66-81 — All fundamental typedefs
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:66-81
STATUS: confirmed
REASON: The cited lines contain exactly the fundamental protocol typedefs (private_key_type, chain_id_type, account_name_type, block_id_type, checksum_type, transaction_id_type, digest_type, signature_type, share_type, ushare_type, weight_type, contribution_id_type, custom_id_type) as claimed.
SUGGESTED_FIX: none

### [85/165] libraries/protocol/include/hive/protocol/types.hpp:83-103 — Key data + base58 encoding
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:83-103
STATUS: confirmed
REASON: The source excerpt shows `public_key_type` with `fc::ecc::public_key_data key_data`, a `binary_key` inner struct with a `check` field (for checksum), and an explicit constructor from `std::string base58str`, directly supporting the claim of key data + base58 encoding.
SUGGESTED_FIX: none

### [86/165] libraries/protocol/include/hive/protocol/authority.hpp:7-55 — Threshold + key/account maps
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/authority.hpp:7-55
STATUS: confirmed
REASON: The source excerpt directly shows the `authority` struct with `weight_threshold` (uint32_t), `key_authority_map` (flat_map of public keys to weights), and `account_authority_map` (flat_map of account names to weights), confirming the "threshold + key/account maps" claim.
SUGGESTED_FIX: none

### [87/165] libraries/protocol/authority.cpp:58-122 — RFC 1035 with Hive rules
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/authority.cpp:58-122
STATUS: confirmed
REASON: The code implements DNS-label-style validation (dot-separated segments, must start with letter, end with letter/digit, interior allows letter/digit/hyphen) matching RFC 1035 structure, with Hive-specific restrictions (lowercase-only, minimum 3-char segments, Hive length constants).
SUGGESTED_FIX: none

### [88/165] libraries/protocol/include/hive/protocol/block_header.hpp:15-26 — previous, timestamp, witness, merkle root
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/block_header.hpp:15-26
STATUS: confirmed
REASON: The struct at lines 15-26 contains exactly the fields claimed — `previous` (line 18), `timestamp` (line 20), `witness` (line 21), and `transaction_merkle_root` (line 22) — plus `extensions`, matching the claim with the minor detail that the KB abbreviates `transaction_merkle_root` to "merkle root".
SUGGESTED_FIX: none

### [89/165] libraries/protocol/block.cpp:13-16 — endian_reverse_u32(id._hash[0])
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/block.cpp:13-16
STATUS: confirmed
REASON: The source excerpt at lines 13-16 shows `fc::endian_reverse_u32(id._hash[0])` verbatim, matching the claimed expression.
SUGGESTED_FIX: none

### [90/165] libraries/protocol/block.cpp:19-46 — Pairwise hashing
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/block.cpp:19-46
STATUS: confirmed
REASON: The source clearly implements pairwise hashing in the Merkle root calculation, as shown by the comment "hash ID's in pairs" (line 34) and the loop that hashes adjacent pairs via `digest_type::hash( std::make_pair( ids[i], ids[i+1] ) )` (line 39).
SUGGESTED_FIX: none

### [91/165] libraries/protocol/include/hive/protocol/transaction.hpp:12-53 — ref_block, expiration, operations
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-53
STATUS: confirmed
REASON: The source at lines 12-53 shows the `transaction` struct with fields `ref_block_num`, `ref_block_prefix`, `expiration`, and `operations`, directly confirming the claimed fields.
SUGGESTED_FIX: none

### [92/165] libraries/protocol/transaction.cpp:84-88 — Block number + prefix extraction
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:84-88
STATUS: confirmed
REASON: The source excerpt shows `set_reference_block` extracting `ref_block_num` via `endian_reverse_u32(reference_block._hash[0])` and `ref_block_prefix` via `reference_block._hash[1]`, which is exactly block number + prefix extraction from a block ID.
SUGGESTED_FIX: none

### [93/165] libraries/protocol/transaction.cpp:58-64 — SHA-256 truncated to 20 bytes
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:58-64
STATUS: confirmed
REASON: `digest(pack)` produces a SHA-256 hash (32 bytes), and the `memcpy` with `std::min(sizeof(result), sizeof(h))` truncates it to `sizeof(transaction_id_type)` which is 20 bytes (ripemd160-sized type).
SUGGESTED_FIX: none

### [94/165] libraries/protocol/transaction.cpp:29-38 — chain_id + transaction -> SHA-256
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:29-38
STATUS: confirmed
REASON: The `sig_digest` method packs `chain_id` then `*this` (the transaction) into a `digest_type::encoder` (which is `fc::sha256`), directly supporting the claim.
SUGGESTED_FIX: none

### [95/165] libraries/protocol/transaction.cpp:40-56 — operations.size() > 0, per-op validate
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:40-56
STATUS: confirmed
REASON: Lines 40-56 show two overloads of transaction::validate(), both asserting operations.size() > 0 and iterating per-op to call operation_validate(), exactly matching the claim.
SUGGESTED_FIX: none

### [96/165] libraries/protocol/include/hive/protocol/version.hpp:15-77 — Major.HF.release in uint32
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:15-77
STATUS: confirmed
REASON: The struct stores `uint32_t v_num` (line 34) with major in bits 31-24, hardfork in bits 23-16, and release in bits 15-0, exactly matching the claim that version is Major.HF.release packed in a uint32.
SUGGESTED_FIX: none

### [97/165] libraries/protocol/include/hive/protocol/version.hpp:79-102 — Masks release bits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:79-102
STATUS: confirmed
REASON: The `hardfork_version` struct applies `& 0xFFFF0000` in its constructor, assignment operators, and all comparison operators, which masks out the lower 16 bits (the release component of the version number).
SUGGESTED_FIX: none

### [98/165] libraries/protocol/include/hive/protocol/version.hpp:104-111 — HF version + activation time
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:104-111
STATUS: confirmed
REASON: The source excerpt shows `hardfork_version_vote` at lines 104-111 containing exactly `hf_version` (hardfork version) and `hf_time` (activation time), directly supporting the claim of "HF version + activation time."
SUGGESTED_FIX: none

### [99/165] libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30 — All 28 HF activation blocks
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30
STATUS: confirmed
REASON: Lines 3-30 define exactly 28 hardfork activation block macros (HF 0.1 through 1.28), matching the claim verbatim.
SUGGESTED_FIX: none

### [100/165] libraries/protocol/hardfork.d/0-preamble.hf:16-19 — HIVE_NUM_HARDFORKS = 28
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/hardfork.d/0-preamble.hf:16-19
STATUS: confirmed
REASON: Both the alternate-chain and mainnet branches define HIVE_NUM_HARDFORKS as 28 at exactly the cited lines.
SUGGESTED_FIX: none

### [101/165] libraries/protocol/include/hive/protocol/config.hpp:137-143 — Mainnet "beeab0de...", testnet, mirrornet
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:137-143
STATUS: confirmed
REASON: Line 142 shows mainnet chain ID prefix "beeab0de" and line 137 shows mirrornet chain ID "4200000000...", with testnet defined elsewhere via preprocessor branches, directly supporting the claim.
SUGGESTED_FIX: none

### [102/165] libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23 — Balance-seconds / year * rate
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23
STATUS: confirmed
REASON: Lines 16-18 compute exactly `hbd_seconds / HIVE_SECONDS_PER_YEAR * hbd_interest_rate / HIVE_100_PERCENT`, which is the claimed "balance-seconds / year * rate" formula (the HIVE_100_PERCENT divisor just normalizes the basis-point rate to a fraction).
SUGGESTED_FIX: none

### [103/165] libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26 — estimate_hive_collateral()` formula (uses ratio + fee constants from `config.hpp`)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26
STATUS: confirmed
REASON: The source excerpt shows `estimate_hive_collateral()` at lines 8-26 using `HIVE_COLLATERALIZED_CONVERSION_FEE` and `HIVE_CONVERSION_COLLATERAL_RATIO` constants with `multiply_with_fee()`, directly supporting the claim that the formula uses ratio and fee constants from config.
SUGGESTED_FIX: none

### [104/165] libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285 — All configurable defaults
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285
STATUS: confirmed
REASON: Lines 27-285 span the entire `configuration` class, which holds all configurable default values (voting windows, cashout, feed, savings, governance, proposals, RC, witness shutdown, initial supply, comment intervals, etc.) with their testnet defaults and setter/getter methods.
SUGGESTED_FIX: none

### [105/165] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Required authorities interface
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: The source excerpt at lines 13-29 shows `base_operation` defining the five `get_required_*` authority methods (authorities, active, posting, owner, witness_signatures) plus `is_virtual()` and `validate()`, and `virtual_operation` inheriting from it, which directly supports the "required authorities interface" claim.
SUGGESTED_FIX: none

### [106/165] libraries/protocol/include/hive/protocol/operations.hpp:15-125 — Complete operation list with IDs
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/operations.hpp:15-125
STATUS: confirmed
REASON: The source excerpt at lines 15-125 contains the complete `operation` typedef listing all 50 regular operations (IDs 0-49) and 43 virtual operations (last_regular+1 through last_regular+43), exactly matching the KB claim of a complete operation list with IDs.
SUGGESTED_FIX: none

### [107/165] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Authority method signatures
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: The source excerpt shows exactly the five authority method signatures (get_required_authorities, get_required_active_authorities, get_required_posting_authorities, get_required_owner_authorities, get_required_witness_signatures) plus is_virtual() and validate() on base_operation, and the virtual_operation subclass, matching the claim about authority method signatures at the cited lines.
SUGGESTED_FIX: none

### [108/165] libraries/protocol/include/hive/protocol/types.hpp:151-161 — recurrent_transfer_pair_id, extensions
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:151-161
STATUS: confirmed
REASON: The source excerpt exactly matches the claim — `recurrent_transfer_pair_id` struct (with `uint8_t pair_id`) and `recurrent_transfer_extensions_type` are defined at lines 151-161.
SUGGESTED_FIX: none

### [109/165] libraries/chain/database.cpp:2183-2369 — _apply_block()` :2183-2369
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2183-2369
STATUS: confirmed
REASON: The source excerpt shows `_apply_block()` defined exactly at lines 2183–2369, matching the cited range and containing all the block-processing logic (merkle check, transaction application, global state updates, economic processing, hardfork handling) described in the findings.
SUGGESTED_FIX: none

### [110/165] libraries/chain/database.cpp:2757-2779 — `validate_block_header()` :2757-2779
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2757-2779
STATUS: confirmed
REASON: The source excerpt shows `validate_block_header()` at exactly lines 2757-2779 with the described logic (previous block linkage, timestamp ordering, witness signature check, schedule check), matching the claim.
SUGGESTED_FIX: none

### [111/165] libraries/chain/database.cpp:2644-2702 — _apply_transaction()` :2644-2702
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2644-2702
STATUS: confirmed
REASON: The provided source excerpt shows `_apply_transaction()` at exactly lines 2644-2702, matching the cited range and covering the claimed logic (tx status check, duplicate check, validation, operation application loop, RC finalization, and notifications).
SUGGESTED_FIX: none

### [112/165] libraries/chain/database.cpp:2521-2642 — `validate_transaction()` :2521-2642
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2521-2642
STATUS: confirmed
REASON: The source excerpt shows `validate_transaction()` defined at line 2521 and ending at line 2642, matching the cited range exactly with the expected expiration checking, TaPoS verification, operation validation, and authority verification logic.
SUGGESTED_FIX: none

### [113/165] libraries/chain/database.cpp:2722-2746 — apply_operation()` :2722-2746
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2722-2746
STATUS: confirmed
REASON: The provided source excerpt shows `database_impl::apply_operation()` at exactly lines 2722-2746, matching the cited function and line range.
SUGGESTED_FIX: none

### [114/165] libraries/chain/witness_schedule.cpp:152-396 — update_witness_schedule4()` :152-396
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:152-396
STATUS: confirmed
REASON: The provided source excerpt shows `update_witness_schedule4()` beginning at line 152 with its signature and ending at line 396 with `} FC_CAPTURE_AND_RETHROW() }`, exactly matching the cited range.
SUGGESTED_FIX: none

### [115/165] libraries/chain/witness_schedule.cpp:372-388 — shuffle :372-388
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:372-388
STATUS: confirmed
REASON: The provided source excerpt exactly matches the KB's description of an XORshift PRNG shuffle seeded with head block timestamp, including the constant 2685821657736338717ULL and the Fisher-Yates swap logic.
SUGGESTED_FIX: none

### [116/165] libraries/chain/database.cpp:904-910 — get_scheduled_witness()` :904-910
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:904-910
STATUS: confirmed
REASON: The source excerpt shows `get_scheduled_witness()` at exactly lines 904-910 with the described logic of computing `current_aslot + slot_num` and indexing into `current_shuffled_witnesses`, matching the claim.
SUGGESTED_FIX: none

### [117/165] libraries/chain/database.cpp:937-943 — `get_slot_at_time()` :937-943
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:937-943
STATUS: confirmed
REASON: The source excerpt shows `get_slot_at_time()` at exactly lines 937-943 with the described logic, matching the citation verbatim.
SUGGESTED_FIX: none

### [118/165] libraries/chain/database_witness.cpp:284-306 — update_witness_missed_blocks()` :284-306
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database_witness.cpp:284-306
STATUS: confirmed
REASON: The source excerpt at lines 284-306 exactly matches the cited function `update_witness_missed_blocks()`, showing the missed block iteration, `total_missed++` increment, HF0_14/HF0_20 shutdown logic, and `producer_missed_operation` virtual op.
SUGGESTED_FIX: none

### [119/165] libraries/chain/database.cpp:2789-2841 — update_global_dynamic_data()` :2789-2841
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2789-2841
STATUS: confirmed
REASON: The source excerpt shows `update_global_dynamic_data()` at lines 2789-2841 with the described logic for missed block tracking, participation bitmap updates, DGP field updates (head_block_number, head_block_id, time, current_aslot), and undo history check, matching the cited claim.
SUGGESTED_FIX: none

### [120/165] libraries/chain/database.cpp:531-535 — `witness_participation_rate()` :531-535
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:531-535
STATUS: confirmed
REASON: The source excerpt shows `witness_participation_rate()` at exactly lines 531-535 with the described popcount-based calculation, matching the claim verbatim.
SUGGESTED_FIX: none

### [121/165] libraries/chain/fork_database.cpp:73-99 — _push_block()` :73-99
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:73-99
STATUS: confirmed
REASON: The `_push_block()` function spans exactly lines 73-99 as cited, with the expected logic: cache-range check, linkability check, index insertion, head update, and `_push_next` call.
SUGGESTED_FIX: none

### [122/165] libraries/chain/fork_database.cpp:20-28 — `pop_block()` :20-28
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:20-28
STATUS: confirmed
REASON: The source excerpt at lines 20-28 shows `pop_block()` exactly as described — asserting head exists, asserting prev exists, then setting `_head = prev`.
SUGGESTED_FIX: none

### [123/165] libraries/chain/fork_database.cpp:290-330 — `fetch_branch_from()` :290-330
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:290-330
STATUS: confirmed
REASON: The source excerpt at lines 290-330 shows `fetch_branch_from()` implementing the exact 3-phase common-ancestor algorithm described in the KB claim (equalize heights, walk back to shared parent, optionally include the fork point).
SUGGESTED_FIX: none

### [124/165] libraries/chain/sync_block_writer.cpp:162-264 — switch_forks()` :162-264
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:162-264
STATUS: confirmed
REASON: The `switch_forks()` function spans exactly lines 162–264 as cited, with the expected logic of fetching branches, popping old-branch blocks, applying new-branch blocks, and reverting on failure.
SUGGESTED_FIX: none

### [125/165] libraries/chain/database.cpp:2956-3064 — update_last_irreversible_block()` :2956-3064
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2956-3064
STATUS: confirmed
REASON: The source excerpt shows `update_last_irreversible_block()` defined at exactly lines 2956–3064, matching the cited location and function name verbatim.
SUGGESTED_FIX: none

### [126/165] libraries/chain/sync_block_writer.cpp:266-367 — find_new_last_irreversible_block()` :266-367
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:266-367
STATUS: confirmed
REASON: The source excerpt shows `find_new_last_irreversible_block()` defined exactly at lines 266–367 in `sync_block_writer.cpp`, matching the cited file, function name, and line range.
SUGGESTED_FIX: none

### [127/165] libraries/chain/database.cpp:2899-2954 — process_fast_confirm_transaction()` :2899-2954
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2899-2954
STATUS: confirmed
REASON: The provided source excerpt shows `process_fast_confirm_transaction()` spanning exactly lines 2899–2954, matching the cited location and function name verbatim.
SUGGESTED_FIX: none

### [128/165] libraries/chain/database.cpp:3066-3097 — migrate_irreversible_state()` :3066-3097
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:3066-3097
STATUS: confirmed
REASON: The provided source excerpt shows `migrate_irreversible_state()` at exactly lines 3066-3097, matching the cited location and function signature verbatim.
SUGGESTED_FIX: none

### [129/165] libraries/chain/block_log.cpp:338-366 — append_raw()` :338-366
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:338-366
STATUS: confirmed
REASON: The source excerpt shows two `append_raw` overloads spanning exactly lines 338–366, matching the cited function and line range.
SUGGESTED_FIX: none

### [130/165] libraries/chain/block_log.cpp:491-515 — read_block_by_num()` :491-515
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:491-515
STATUS: confirmed
REASON: The provided source excerpt shows `read_block_by_num()` defined exactly at lines 491-515 with the described logic intact.
SUGGESTED_FIX: none

### [131/165] libraries/chain/block_log_artifacts.cpp:46-69 — header :46-69
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_artifacts.cpp:46-69
STATUS: confirmed
REASON: The source excerpt at lines 46-69 matches the cited struct `artifact_file_header` definition exactly, with all fields and initialization logic intact.
SUGGESTED_FIX: none

### [132/165] libraries/chain/block_log_artifacts.cpp:82-166 — chunk :82-166
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_artifacts.cpp:82-166
STATUS: confirmed
REASON: The struct `artifact_file_chunk` at lines 82-166 matches the claimed bit-field layout (48-bit offset, 8-bit dict, 1-bit custom_dict, 6-bit gap, 1-bit compressed) and `stripped_block_id[2]`; the KB simplification omits the union wrapper and methods but the data layout and line range are accurate.
SUGGESTED_FIX: none

### [133/165] libraries/plugins/witness/witness_plugin.cpp:369-380 — schedule_production_loop()` :369-380
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:369-380
STATUS: confirmed
REASON: The source excerpt shows `schedule_production_loop()` defined at exactly lines 369-380 with the 200ms sleep loop, timer setup, and callback to `block_production_loop`, matching the cited function and line range.
SUGGESTED_FIX: none

### [134/165] libraries/plugins/witness/witness_plugin.cpp:382-467 — `block_production_loop()` :382-467
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:382-467
STATUS: confirmed
REASON: The source excerpt shows `block_production_loop()` defined at exactly lines 382–467, matching the cited range verbatim.
SUGGESTED_FIX: none

### [135/165] libraries/plugins/witness/block_producer.cpp:31-85 — _generate_block()` :31-85
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:31-85
STATUS: confirmed
REASON: The `_generate_block()` method definition spans exactly lines 31–85 in the provided excerpt, matching the citation precisely.
SUGGESTED_FIX: none

### [136/165] libraries/plugins/witness/block_producer.cpp:111-216 — `apply_pending_transactions()` :111-216
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:111-216
STATUS: confirmed
REASON: The source excerpt shows `apply_pending_transactions()` defined exactly at lines 111-216, matching the cited function name, file, and line range.
SUGGESTED_FIX: none

### [137/165] libraries/chain/include/hive/chain/block_flow_control.hpp:135-146 — Phase enum :135-146
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/include/hive/chain/block_flow_control.hpp:135-146
STATUS: confirmed
REASON: The provided source excerpt shows the `phase` enum at exactly lines 135-146 with all nine enumerators and comments matching the claim verbatim.
SUGGESTED_FIX: none

### [138/165] libraries/chain/database.cpp:1704 — process_funds()` at line 1704
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:1704
STATUS: confirmed
REASON: The source excerpt shows `void database::process_funds()` defined at exactly line 1704, matching the claim verbatim.
SUGGESTED_FIX: none

### [139/165] libraries/chain/util/reward.cpp:34 — evaluate_reward_curve()` at line 34
Source: `07-economic-model.md`

CITATION: libraries/chain/util/reward.cpp:34
STATUS: confirmed
REASON: The source excerpt shows `evaluate_reward_curve()` defined at exactly line 34 with the expected signature.
SUGGESTED_FIX: none

### [140/165] libraries/chain/database_comment.cpp:379 — process_comment_cashout()` at line 379
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:379
STATUS: confirmed
REASON: The source excerpt shows `void database::process_comment_cashout()` defined at exactly line 379, matching the claim verbatim.
SUGGESTED_FIX: none

### [141/165] libraries/chain/database_comment.cpp:129 — pay_curators()` at line 129
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:129
STATUS: confirmed
REASON: The source excerpt shows `pay_curators()` defined at exactly line 129 of `libraries/chain/database_comment.cpp`, matching the claim verbatim.
SUGGESTED_FIX: none

### [142/165] libraries/chain/database_comment.cpp:197 — cashout_comment_helper()` at line 197
Source: `07-economic-model.md`

CITATION: libraries/chain/database_comment.cpp:197
STATUS: confirmed
REASON: The source excerpt shows `cashout_comment_helper()` defined beginning at line 197, matching the claim verbatim.
SUGGESTED_FIX: none

### [143/165] libraries/chain/database.cpp:949 — create_hbd()` at line 949
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:949
STATUS: confirmed
REASON: The source excerpt shows `create_hbd()` defined at line 949 of `libraries/chain/database.cpp`, matching the claim exactly.
SUGGESTED_FIX: none

### [144/165] libraries/chain/hive_evaluator_social.cpp:605 — hf20_vote_evaluator()` at line 605
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_social.cpp:605
STATUS: confirmed
REASON: The source excerpt shows `void hf20_vote_evaluator(` beginning exactly at line 605, matching the claim verbatim.
SUGGESTED_FIX: none

### [145/165] libraries/chain/database.cpp:3186 — adjust_balance(HBD)` accrual logic at line 3186
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:3186
STATUS: confirmed
REASON: The source excerpt shows `void database::adjust_balance( const account_object& a, const HBD_asset& delta )` at exactly line 3186, confirming the HBD overload of `adjust_balance` begins there.
SUGGESTED_FIX: none

### [146/165] libraries/chain/database.cpp:3265 — adjust_savings_balance(HBD)` at line 3265
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:3265
STATUS: confirmed
REASON: The source excerpt at line 3265 shows the function signature `void database::adjust_savings_balance( const account_object& a, const HBD_asset& delta )`, which directly confirms the claim that `adjust_savings_balance(HBD)` exists at that line.
SUGGESTED_FIX: none

### [147/165] libraries/protocol/include/hive/protocol/hbd_interest.hpp:9 — evaluate_hbd_interest()` at line 9
Source: `07-economic-model.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:9
STATUS: confirmed
REASON: Line 9 contains the declaration of `static uint128_t evaluate_hbd_interest(...)`, matching the claim verbatim.
SUGGESTED_FIX: none

### [148/165] libraries/chain/database_conversion.cpp:34 — process_conversions()` at line 34
Source: `07-economic-model.md`

CITATION: libraries/chain/database_conversion.cpp:34
STATUS: confirmed
REASON: The source excerpt shows `void database::process_conversions()` defined at exactly line 34, matching the claim verbatim.
SUGGESTED_FIX: none

### [149/165] libraries/chain/hive_evaluator_transfer.cpp:473 — collateralized_convert_evaluator::do_apply()` at line 473
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:473
STATUS: confirmed
REASON: Line 473 contains the definition of `collateralized_convert_evaluator::do_apply()` exactly as claimed.
SUGGESTED_FIX: none

### [150/165] libraries/chain/util/dhf_processor.cpp:238 — make_payments()` at line 238
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:238
STATUS: confirmed
REASON: The source excerpt shows `void dhf_processor::make_payments(` beginning exactly at line 238, matching the claim verbatim.
SUGGESTED_FIX: none

### [151/165] libraries/chain/util/dhf_processor.cpp:145 — calculate_maintenance_budget()` at line 145
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145
STATUS: confirmed
REASON: The source excerpt shows `calculate_maintenance_budget()` defined at exactly line 145, matching the claim verbatim.
SUGGESTED_FIX: none

### [152/165] libraries/chain/util/dhf_processor.cpp:325 — convert_funds()` at line 325
Source: `07-economic-model.md`

CITATION: libraries/chain/util/dhf_processor.cpp:325
STATUS: confirmed
REASON: The source excerpt shows `void dhf_processor::convert_funds(` beginning exactly at line 325, matching the claim.
SUGGESTED_FIX: none

### [153/165] libraries/chain/hive_evaluator_transfer.cpp:292 — transfer_to_vesting_evaluator::do_apply()` at line 292
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:292
STATUS: confirmed
REASON: The source excerpt shows `transfer_to_vesting_evaluator::do_apply()` beginning at exactly line 292, matching the claim verbatim.
SUGGESTED_FIX: none

### [154/165] libraries/chain/hive_evaluator_transfer.cpp:327 — withdraw_vesting_evaluator::do_apply()` at line 327
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:327
STATUS: confirmed
REASON: The source excerpt at line 327 shows `withdraw_vesting_evaluator::do_apply()` exactly as cited, matching the claim verbatim.
SUGGESTED_FIX: none

### [155/165] libraries/chain/database_vesting.cpp:111 — process_vesting_withdrawals()` at line 111
Source: `07-economic-model.md`

CITATION: libraries/chain/database_vesting.cpp:111
STATUS: confirmed
REASON: The source excerpt shows `void database::process_vesting_withdrawals()` defined exactly at line 111, matching the claim verbatim.
SUGGESTED_FIX: none

### [156/165] libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87 — get_vesting_share_price()` at line 87
Source: `07-economic-model.md`

CITATION: libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87
STATUS: confirmed
REASON: The source excerpt shows `get_vesting_share_price()` defined at exactly line 87 with the described signature and fallback logic.
SUGGESTED_FIX: none

### [157/165] libraries/chain/database.cpp:2399 — update_median_feed()` at line 2399
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:2399
STATUS: confirmed
REASON: The source excerpt shows `void database::update_median_feed()` defined at exactly line 2399, matching the claim verbatim.
SUGGESTED_FIX: none

### [158/165] libraries/chain/database.cpp:2868 — update_virtual_supply()` at line 2868
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:2868
STATUS: confirmed
REASON: The source excerpt shows `void database::update_virtual_supply()` defined at exactly line 2868, matching the claim verbatim.
SUGGESTED_FIX: none

### [159/165] libraries/chain/database.cpp:2843 — calculate_HBD_percent()` at line 2843
Source: `07-economic-model.md`

CITATION: libraries/chain/database.cpp:2843
STATUS: confirmed
REASON: The source excerpt shows `uint16_t database::calculate_HBD_percent()` beginning exactly at line 2843, matching the claim verbatim.
SUGGESTED_FIX: none

### [160/165] libraries/chain/database_hardfork.cpp:336-416 — HF20 RC initialization
Source: `08-resource-credits.md`

CITATION: libraries/chain/database_hardfork.cpp:336-416
STATUS: confirmed
REASON: The source excerpt shows the complete HF20 RC initialization sequence at exactly the cited lines: loading resource parameters from JSON, creating rc_resource_param_object, setting pool params, creating usage buckets, creating rc_pool_object, creating rc_stats_objects, and initializing all accounts' RC mana to maximum.
SUGGESTED_FIX: none

### [161/165] libraries/chain/witness_schedule.cpp:264-333 — Hardfork voting mechanism
Source: `09-hardfork-history.md`

CITATION: libraries/chain/witness_schedule.cpp:264-333
STATUS: confirmed
REASON: The cited lines directly implement the hardfork voting mechanism: tallying witness version votes (lines 266-282), determining majority version against `hardfork_required_witnesses` threshold (lines 306-317), and scheduling the next hardfork when vote threshold is met (lines 319-334), plus the special-case HF23 force (lines 289-301).
SUGGESTED_FIX: none

### [162/165] libraries/chain/database.cpp:61-71 — next_hf_time()` for HF28
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:61-71
STATUS: confirmed
REASON: The source excerpt at lines 61-71 defines `next_hf_time()` with the comment "current next hardfork is HF28" and the mainnet timestamp 1763557200, exactly matching the claim.
SUGGESTED_FIX: none

### [163/165] libraries/chain/database.cpp:1461-1540 — clear_account()` / `clear_accounts()` for HF23
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:1461-1540
STATUS: confirmed
REASON: The source excerpt shows `clear_accounts()` at line 1461 and `clear_account()` at line 1474, both implementing HF23 account clearing logic (with `hardfork_hive_operation` vop, treasury transfers, delegation removal), exactly as claimed.
SUGGESTED_FIX: none

### [164/165] libraries/chain/database.cpp:1422-1458 — restore_accounts()` for HF24
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:1422-1458
STATUS: confirmed
REASON: The source excerpt shows `restore_accounts()` at exactly lines 1422-1458, restoring HBD/HIVE balances from `h23_balances` (HF23 seizures) back from treasury to accounts — consistent with the HF24 restoration claim.
SUGGESTED_FIX: none

### [165/165] libraries/chain/database_dhf.cpp:146 — remove_proposal_votes_for_accounts_without_voting_rights()` for HF28
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_dhf.cpp:146
STATUS: confirmed
REASON: The source at line 146 shows the function `remove_proposal_votes_for_accounts_without_voting_rights()` defined exactly as claimed.
SUGGESTED_FIX: none

## Summary

| Status | Count |
|--------|------:|
| confirmed  | 165 |
| drifted    | 0 |
| broken     | 0 |
| unparseable| 0 |
