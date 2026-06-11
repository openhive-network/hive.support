# Verification Report

- Topic: `hive-core`
- Pinned: `1.28.6` (`10ac0ce94f7591b6ad80db1a23d046c9d57b6559`)
- Run: 2026-06-11T00:44:19+02:00
- Citations audited: 243


### [1/243] libraries/protocol/include/hive/protocol/config.hpp:56-458 — All timing/economic/size constants
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56-458
STATUS: confirmed
REASON: The cited range begins at HIVE_BLOCK_INTERVAL (line 56, first timing constant) and spans the complete block of timing (block intervals, cashout windows, recovery periods), economic (inflation rates, APR percentages, HBD/reward constants), and size (account/permlink lengths, transaction/block sizes, memo limits) constants exactly as the umbrella claim describes.
SUGGESTED_FIX: none

### [2/243] libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-53 — NAI bit layout and encoding
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-53
STATUS: confirmed
REASON: Lines 9-32 define exactly the NAI bit layout and encoding — 4 precision bits, 1 control bit, HIVE_NAI_SHIFT=5, and the asset_num formula `((SMT_MAX_NAI + nai) << HIVE_NAI_SHIFT) | precision` for HBD/HIVE/VESTS — matching the claim verbatim.
SUGGESTED_FIX: none

### [3/243] libraries/protocol/include/hive/protocol/asset.hpp:21-186 — Asset struct and price
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:21-186
STATUS: confirmed
REASON: The cited range begins exactly at `struct asset` (line 21) and ends at the close of `struct price` (line 186, `}; /// price`), directly supporting the "Asset struct and price" claim.
SUGGESTED_FIX: none

### [4/243] libraries/protocol/asset.cpp:128-286 — Asset validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/asset.cpp:128-286
STATUS: confirmed
REASON: Lines 128-286 cleanly span the asset-symbol validation logic — asset_num_from_nai() with NAI-range/check-digit/decimal-place asserts, plus the helpers and the validate() function whose closing brace is exactly at line 286 — fully supporting the "Asset validation" claim.
SUGGESTED_FIX: none

### [5/243] libraries/protocol/include/hive/protocol/authority.hpp:7-55 — Authority struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/authority.hpp:7-55
STATUS: confirmed
REASON: Lines 7-55 contain the complete `authority` struct definition (enum classification, constructors, add_authority/get_keys/validate methods, and weight_threshold/account_auths/key_auths members), directly supporting the "Authority struct" claim.
SUGGESTED_FIX: none

### [6/243] libraries/protocol/authority.cpp:58-122 — Account name validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/authority.cpp:58-122
STATUS: confirmed
REASON: Lines 58-122 contain exactly the `check_account_name` function implementing account name validation (length bounds, dot-segment rules, allowed-character checks), directly supporting the "Account name validation" claim.
SUGGESTED_FIX: none

### [7/243] libraries/protocol/include/hive/protocol/operations.hpp:15-125 — Operation variant (93 types: 50 regular + 43 virtual)
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/operations.hpp:15-125
STATUS: confirmed
REASON: The static_variant at lines 15-125 enumerates exactly 50 regular operations (indices 0-49) and 43 virtual operations (last_regular+1 through last_regular+43), totaling 93, matching the claim verbatim.
SUGGESTED_FIX: none

### [8/243] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Base operation class
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: Line 13 begins `struct base_operation` and the range 13-29 spans the full base_operation definition plus its virtual_operation subclass, directly supporting the "Base operation class" claim.
SUGGESTED_FIX: none

### [9/243] libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-17 — RC custom operations
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-17
STATUS: confirmed
REASON: Lines 8-17 define the `delegate_rc_operation` struct (the RC custom operation) inside `hive_custom_operations.hpp`, directly supporting the "RC custom operations" claim.
SUGGESTED_FIX: none

### [10/243] libraries/protocol/hive_operations.cpp:1-866 — Operation validate() methods
Source: `00-consolidated.md`

CITATION: libraries/protocol/hive_operations.cpp:1-866
STATUS: confirmed
REASON: The cited file spans exactly lines 1-866 and is densely populated with operation `validate()` method implementations (account_create, comment, transfer, escrow, witness_set_properties, etc.), directly supporting the claim.
SUGGESTED_FIX: none

### [11/243] libraries/protocol/dhf_operations.cpp:1-62 — DHF operation validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/dhf_operations.cpp:1-62
STATUS: confirmed
REASON: Lines 1-62 contain the validate() methods for all four DHF proposal operations (create_proposal, update_proposal, update_proposal_votes, remove_proposal), exactly matching the claim "DHF operation validation."
SUGGESTED_FIX: none

### [12/243] libraries/protocol/include/hive/protocol/block_header.hpp:15-26 — Block header struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/block_header.hpp:15-26
STATUS: confirmed
REASON: Lines 15-26 define exactly the `block_header` struct, from its opening declaration through the closing brace, directly supporting the claim.
SUGGESTED_FIX: none

### [13/243] libraries/protocol/include/hive/protocol/transaction.hpp:12-53 — Transaction struct
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-53
STATUS: confirmed
REASON: Lines 12-53 contain exactly the `struct transaction` definition (fields ref_block_num through extensions plus its methods), matching the claim verbatim.
SUGGESTED_FIX: none

### [14/243] libraries/protocol/transaction.cpp:40-55 — Transaction validation
Source: `00-consolidated.md`

CITATION: libraries/protocol/transaction.cpp:40-55
STATUS: confirmed
REASON: Lines 40-55 contain the two `transaction::validate()` method definitions that enforce the non-empty-operations assertion and invoke `operation_validate` on each operation, directly supporting the "Transaction validation" claim.
SUGGESTED_FIX: none

### [15/243] libraries/protocol/include/hive/protocol/version.hpp:15-77 — Version encoding
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:15-77
STATUS: confirmed
REASON: Lines 15-77 are exactly the `struct version` definition, whose `v_num` field plus `major_v()`/`minor_v()`/`rev_v()` bitmasks (0xFF000000>>24, 0x00FF0000>>16, 0x0000FFFF) and triple-version comment directly document the version encoding claimed.
SUGGESTED_FIX: none

### [16/243] libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30 — Hardfork block numbers
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30
STATUS: confirmed
REASON: Lines 3-30 contain exactly the hardfork block-number `#define` constants (HIVE_HARDFORK_0_1_BLOCK through HIVE_HARDFORK_1_28_BLOCK), directly supporting the claim "Hardfork block numbers."
SUGGESTED_FIX: none

### [17/243] libraries/protocol/include/hive/protocol/config.hpp:137-143 — Chain IDs
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:137-143
STATUS: confirmed
REASON: The cited lines define the chain IDs verbatim — HIVE_CHAIN_ID for Mirrornet (`4200...`, line 137) and Hive mainnet (`beeab0de00...`, line 142), plus OLD_CHAIN_ID — directly supporting the "Chain IDs" claim.
SUGGESTED_FIX: none

### [18/243] libraries/protocol/include/hive/protocol/validation.hpp:64-115 — Validation helpers
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/validation.hpp:64-115
STATUS: confirmed
REASON: Lines 64-115 contain exactly the inline validation helper functions (validate_string_max_size, validate_is_utf8, validate_string_is_not_empty, validate_number_in_100_percent_range, validate_account_name, validate_permlink), matching the "Validation helpers" claim.
SUGGESTED_FIX: none

### [19/243] libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23 — HBD interest calc
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23
STATUS: confirmed
REASON: Lines 8-23 contain the `hbd_interest` struct's `evaluate_hbd_interest` method that accumulates hbd_seconds and computes interest (hbd_seconds / HIVE_SECONDS_PER_YEAR × hbd_interest_rate / HIVE_100_PERCENT), exactly matching the "HBD interest calc" claim.
SUGGESTED_FIX: none

### [20/243] libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26 — Collateral estimation
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26
STATUS: confirmed
REASON: Lines 8-26 contain the `hive_collateral` struct's `estimate_hive_collateral` method, which performs exactly the collateral estimation the claim describes (fee-adjusted HBD→HIVE conversion scaled by HIVE_CONVERSION_COLLATERAL_RATIO).
SUGGESTED_FIX: none

### [21/243] libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285 — Testnet overrides
Source: `00-consolidated.md`

CITATION: libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285
STATUS: confirmed
REASON: Lines 27-285 are exactly the `class configuration` definition holding all testnet-overridable consensus/economic parameters, directly supporting the "Testnet overrides" claim.
SUGGESTED_FIX: none

### [22/243] libraries/chain/database.cpp:2183-2369 — Block application (`_apply_block`)
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2183-2369
STATUS: confirmed
REASON: The function `database::_apply_block` begins exactly at line 2183 (signature) and ends at line 2369 (closing brace with FC_CAPTURE_CALL_LOG_AND_RETHROW), matching the cited range precisely and directly supporting the "Block application (`_apply_block`)" claim.
SUGGESTED_FIX: none

### [23/243] libraries/chain/database.cpp:2757-2779 — Block header validation
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2757-2779
STATUS: confirmed
REASON: Lines 2757-2779 contain exactly the `database::validate_block_header` function, which validates the previous-block link, timestamp ordering, witness signing key, and witness schedule — directly supporting the "Block header validation" claim.
SUGGESTED_FIX: none

### [24/243] libraries/chain/database.cpp:2644-2702 — Transaction application
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2644-2702
STATUS: confirmed
REASON: Lines 2644-2702 contain the `database::_apply_transaction` method whose body (dupe check, validate_transaction, per-operation apply loop, RC finalize, pre/post notifications) is precisely the transaction application logic the claim references.
SUGGESTED_FIX: none

### [25/243] libraries/chain/database.cpp:2722-2746 — Operation dispatch
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2722-2746
STATUS: confirmed
REASON: Lines 2722-2746 are exactly the `database_impl::apply_operation` function, which performs operation dispatch by retrieving the operation's evaluator from `_evaluator_registry` and calling `.apply( op )` on it (line 2740), bracketed by pre/post-apply notifications and RC discount handling.
SUGGESTED_FIX: none

### [26/243] libraries/chain/database.cpp:2956-3064 — LIB calculation
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2956-3064
STATUS: confirmed
REASON: Lines 2956-3064 are exactly the `database::update_last_irreversible_block` function, which computes LIB via the witness-confirmation offset (HIVE_IRREVERSIBLE_THRESHOLD) and both the legacy nth_element and new fork-db algorithms, directly supporting the "LIB calculation" claim.
SUGGESTED_FIX: none

### [27/243] libraries/chain/database.cpp:2899-2954 — Fast confirm processing
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2899-2954
STATUS: confirmed
REASON: Lines 2899-2954 contain exactly the `database::process_fast_confirm_transaction` function, which validates a witness_block_approve_operation, checks scheduling, deduplicates per-witness approvals, and updates irreversible state — precisely "fast confirm processing."
SUGGESTED_FIX: none

### [28/243] libraries/chain/database.cpp:3066-3097 — Irreversibility migration
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:3066-3097
STATUS: confirmed
REASON: Lines 3066-3097 are exactly the `database::migrate_irreversible_state` function, which performs the irreversibility migration (stores irreversible blocks, commits/deletes undo state, notifies irreversible blocks) — matching the claim verbatim.
SUGGESTED_FIX: none

### [29/243] libraries/chain/database.cpp:2789-2841 — Participation tracking
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2789-2841
STATUS: confirmed
REASON: The cited lines 2789-2841 contain database::update_global_dynamic_data, whose loop at 2818-2823 maintains dgp.participation_count and dgp.recent_slots_filled via bit-shifting — exactly the participation tracking the claim describes.
SUGGESTED_FIX: none

### [30/243] libraries/chain/database.cpp:2843-2868 — HBD print rate / virtual supply
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:2843-2868
STATUS: confirmed
REASON: Lines 2843-2868 contain `calculate_HBD_percent()` — the HBD-as-percent-of-virtual-supply (debt ratio) calculation that drives the HBD print rate — plus the opening of `update_virtual_supply()`, matching the claim's topic exactly at the stated line numbers (the `{{SOURCE_EXCERPT}}` tokens are rendering artifacts for `&`).
SUGGESTED_FIX: none

### [31/243] libraries/chain/database.cpp:1704 — Inflation distribution
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:1704
STATUS: confirmed
REASON: Line 1704 is exactly `void database::process_funds()`, the method whose preceding doc-comment describes paying out per-block vesting/reward shares and daily liquidity shares — i.e. inflation distribution — so the claim and line number hold.
SUGGESTED_FIX: none

### [32/243] libraries/chain/database.cpp:61-71 — next_hf_time()
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:61-71
STATUS: confirmed
REASON: Line 61 defines `long next_hf_time()` and the cited range 61-71 captures the function's hardfork-time logic exactly as the claim references.
SUGGESTED_FIX: none

### [33/243] libraries/chain/database.cpp:1422-1540 — Account clearing/restoration
Source: `00-consolidated.md`

CITATION: libraries/chain/database.cpp:1422-1540
STATUS: confirmed
REASON: The cited range begins exactly at `database::restore_accounts` (1422) and spans `clear_accounts` (1461) and `clear_account` (1474), directly implementing the claimed account clearing/restoration logic.
SUGGESTED_FIX: none

### [34/243] libraries/chain/hive_evaluator_transfer.cpp:75-957 — Transfer evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_transfer.cpp:75-957
STATUS: confirmed
REASON: Lines 75-957 contain exactly the series of transfer-family evaluator do_apply implementations (transfer, transfer_to_vesting, transfer_to/from_savings, recurrent_transfer, escrow_transfer/approve/dispute/release, convert, collateralized_convert, limit_order, delegate_vesting_shares), and the range bounds align with the first evaluator's opening (line 75) through the last evaluator's closing brace (line 957), matching the "Transfer evaluators" descriptor.
SUGGESTED_FIX: none

### [35/243] libraries/chain/hive_evaluator_account.cpp:130-657 — Account evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_account.cpp:130-657
STATUS: confirmed
REASON: Lines 130-657 contain exactly the account evaluator implementations (account_create, account_create_with_delegation, account_update, account_update2, claim_account, create_claimed_account, request/recover/change_recovery_account, decline_voting_rights, reset/set_reset_account) plus the create_account helper, precisely matching the "Account evaluators" label.
SUGGESTED_FIX: none

### [36/243] libraries/chain/hive_evaluator_social.cpp:55-864 — Social evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator_social.cpp:55-864
STATUS: confirmed
REASON: Lines 55-864 of hive_evaluator_social.cpp contain exactly the social evaluator implementations (delete_comment, comment_options, comment, and pre/hf20 vote evaluators), with line 55 opening delete_comment_evaluator::do_apply and line 864 closing vote_evaluator::do_apply, directly supporting the "Social evaluators" label.
SUGGESTED_FIX: none

### [37/243] libraries/chain/hive_evaluator.cpp:62-628 — Witness/custom/pow evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/hive_evaluator.cpp:62-628
STATUS: confirmed
REASON: Lines 62-628 contain exactly the witness evaluators (witness_update, witness_set_properties, account_witness_proxy, account_witness_vote, feed_publish, witness_block_approve), custom evaluators (custom, custom_json, custom_binary), and pow evaluators (pow_apply, pow_evaluator, pow2_evaluator), precisely matching the "Witness/custom/pow evaluators" label.
SUGGESTED_FIX: none

### [38/243] libraries/chain/dhf_evaluator.cpp:32-252 — DHF evaluators
Source: `00-consolidated.md`

CITATION: libraries/chain/dhf_evaluator.cpp:32-252
STATUS: confirmed
REASON: Lines 32-252 of dhf_evaluator.cpp contain exactly the four DHF (Decentralized Hive Fund / proposal system) evaluators — create_proposal, update_proposal, update_proposal_votes, and remove_proposal — matching the "DHF evaluators" claim verbatim.
SUGGESTED_FIX: none

### [39/243] libraries/chain/database_comment.cpp:129-379 — Comment cashout/curation
Source: `00-consolidated.md`

CITATION: libraries/chain/database_comment.cpp:129-379
STATUS: confirmed
REASON: The cited range spans `pay_curators()` (line 129, distributes curation rewards) and `cashout_comment_helper()` (line 197, computes author/curation/beneficiary splits and triggers payout virtual ops), ending exactly where `process_comment_cashout()` begins at line 379 — directly supporting the "Comment cashout/curation" claim.
SUGGESTED_FIX: none

### [40/243] libraries/chain/witness_schedule.cpp:152-396 — Witness scheduling
Source: `00-consolidated.md`

CITATION: libraries/chain/witness_schedule.cpp:152-396
STATUS: confirmed
REASON: Lines 152-396 are exactly the `update_witness_schedule4` function, which implements witness scheduling (selecting top-voted witnesses, miners, and timeshare witnesses, then shuffling the active set), directly supporting the "Witness scheduling" claim.
SUGGESTED_FIX: none

### [41/243] libraries/chain/database_witness.cpp:284-306 — Witness missed blocks
Source: `00-consolidated.md`

CITATION: libraries/chain/database_witness.cpp:284-306
STATUS: confirmed
REASON: Lines 284-306 contain the `update_witness_missed_blocks` function which iterates scheduled witnesses, increments `total_missed`, handles HF14–HF20 witness shutdown, and pushes `producer_missed_operation` — directly supporting the "Witness missed blocks" claim.
SUGGESTED_FIX: none

### [42/243] libraries/chain/fork_database.cpp:20-330 — Fork database
Source: `00-consolidated.md`

CITATION: libraries/chain/fork_database.cpp:20-330
STATUS: confirmed
REASON: The cited range contains the `fork_database` class method implementations (pop_block, push_block, fetch_branch_from, head tracking, etc.), directly supporting the "Fork database" claim.
SUGGESTED_FIX: none

### [43/243] libraries/chain/sync_block_writer.cpp:162-367 — Fork switching
Source: `00-consolidated.md`

CITATION: libraries/chain/sync_block_writer.cpp:162-367
STATUS: confirmed
REASON: Line 162 begins `sync_block_writer::switch_forks()`, which implements fork switching (pop to common ancestor, push new branch, revert-on-failure), and the range extends through the related `find_new_last_irreversible_block()`, directly supporting the "Fork switching" claim.
SUGGESTED_FIX: none

### [44/243] libraries/chain/block_log.cpp:338-515 — Block log read/write
Source: `00-consolidated.md`

CITATION: libraries/chain/block_log.cpp:338-515
STATUS: confirmed
REASON: Lines 338-515 contain exactly the block_log write functions (append_raw, multi_append_raw, append, flush) and read functions (read_raw_block_data_by_num, read_common_raw_block_data_by_num, read_block_id_by_num, read_block_by_num), directly supporting the "Block log read/write" claim.
SUGGESTED_FIX: none

### [45/243] libraries/chain/block_log_artifacts.cpp:46-166 — Block log artifacts
Source: `00-consolidated.md`

CITATION: libraries/chain/block_log_artifacts.cpp:46-166
STATUS: confirmed
REASON: Lines 46-166 contain exactly the block log artifact structures (`artifact_file_header` and `artifact_file_chunk` with their pack/unpack logic) in the file literally named `block_log_artifacts.cpp`, fully supporting the "Block log artifacts" claim.
SUGGESTED_FIX: none

### [46/243] libraries/chain/include/hive/chain/hive_object_types.hpp:47-89 — Object type enum (39 IDs)
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/hive_object_types.hpp:47-89
STATUS: confirmed
REASON: The enum object_type spans exactly lines 47–89 and contains precisely 39 members (33 core + 6 RC objects), matching the claimed "39 IDs".
SUGGESTED_FIX: none

### [47/243] libraries/chain/include/hive/chain/detail/state/account_object.hpp:339 — account_authority_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/account_object.hpp:339
STATUS: confirmed
REASON: Line 339 is the verbatim class declaration `class account_authority_object : public object< account_authority_object_type, account_authority_object, std::true_type >`, exactly matching the claimed state object.
SUGGESTED_FIX: none

### [48/243] libraries/chain/include/hive/chain/detail/state/comment_object.hpp:372 — comment_vote_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/comment_object.hpp:372
STATUS: confirmed
REASON: Line 372 in the provided excerpt is precisely the `class comment_vote_object` declaration, directly supporting the claim referencing comment_vote_object.
SUGGESTED_FIX: none

### [49/243] libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:69 — witness_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:69
STATUS: confirmed
REASON: Line 69 of the cited excerpt is the verbatim `class witness_object : public object<...>` declaration, directly supporting the claim referencing the `witness_object` state object.
SUGGESTED_FIX: none

### [50/243] libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:183 — witness_schedule_object
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/detail/state/witness_objects.hpp:183
STATUS: confirmed
REASON: Line 183 contains the exact class declaration `class witness_schedule_object`, directly supporting the claim that references this state object.
SUGGESTED_FIX: none

### [51/243] libraries/chain/rc/rc_utility.cpp:547-581 — Non-consensus enforcement
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:547-581
STATUS: confirmed
REASON: The cited range shows the asymmetric enforcement that defines non-consensus RC — a hard HIVE_ASSERT/not_enough_rc_exception only when db.is_in_control()/reapplying (mempool admission), versus merely logging "Accepting transaction" during block processing — reinforced by the adjacent FC_TODO noting RC is not yet part of consensus.
SUGGESTED_FIX: none

### [52/243] libraries/chain/rc/rc_utility.cpp:799-831 — Mana deduction (finalize_tx)
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:799-831
STATUS: confirmed
REASON: Lines 799-831 are exactly the `resource_credits::finalize_transaction` function, which computes the transaction's RC cost (line 813) and deducts it from the payer's mana via `use_account_rcs(total_cost)` (line 818), supporting the "Mana deduction (finalize_tx)" claim.
SUGGESTED_FIX: none

### [53/243] libraries/chain/rc/rc_utility.cpp:26-110 — RC delegation mechanics
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:26-110
STATUS: confirmed
REASON: Lines 26-110 span the body of `delegate_rc_evaluator::do_apply`, which implements RC delegation mechanics (HF26 gate, min-delegation check, create/modify/remove of `rc_direct_delegation_object`, delta accounting, and `from_account` mana/`delegated_rc` updates), directly supporting the claim.
SUGGESTED_FIX: none

### [54/243] libraries/chain/rc/rc_utility.cpp:401-443 — Delegation overflow
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:401-443
STATUS: confirmed
REASON: Lines 401-443 contain exactly the RC delegation-overflow handling logic — computing `delegation_overflow` from `get_maximum_rc(true)`, calling `remove_delegations`, supplementing or creating the `rc_expired_delegation_object` when the removal limit is exhausted, and decrementing `delegated_rc` — which directly supports the "Delegation overflow" claim.
SUGGESTED_FIX: none

### [55/243] libraries/chain/rc/rc_utility.cpp:505-537 — Flood surcharge
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_utility.cpp:505-537
STATUS: confirmed
REASON: Lines 505-537 implement exactly the flood surcharge mechanism—declaring `surcharge`, computing `blocks_in_mempool` against `flood_level`, exempting privileged witness ops, and scaling `(blocks_in_mempool - flood_level) * flood_surcharge` by `rc`—matching the "Flood surcharge" claim verbatim.
SUGGESTED_FIX: none

### [56/243] libraries/chain/rc/resource_count.cpp:136-631 — Resource counting
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_count.cpp:136-631
STATUS: confirmed
REASON: The cited range contains the resource counting machinery verbatim — the `count_operation_visitor` struct (per-operation state-bytes/execution-time accounting), `handle_operation_discount`, and `count_resources()` which iterates operations and aggregates usage — fully supporting the "Resource counting" claim.
SUGGESTED_FIX: none

### [57/243] libraries/chain/rc/resource_sizes.cpp:45-165 — State byte sizes
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_sizes.cpp:45-165
STATUS: confirmed
REASON: Lines 45-165 exactly span the `state_object_size_info::state_object_size_info()` constructor, which defines the state byte sizes (TEMPORARY/LASTING/PERSISTENT state bytes plus per-object sizes) that the "State byte sizes" claim references.
SUGGESTED_FIX: none

### [58/243] libraries/chain/rc/resource_sizes.cpp:167-242 — Execution time benchmarks
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/resource_sizes.cpp:167-242
STATUS: confirmed
REASON: Lines 167-242 are exactly the `operation_exec_info::operation_exec_info()` constructor that initializes per-operation execution time benchmarks (with comments sourcing the measurements from issue 205), directly supporting the claim.
SUGGESTED_FIX: none

### [59/243] libraries/chain/rc/rc_curve.cpp:32-98 — Price curve computation
Source: `00-consolidated.md`

CITATION: libraries/chain/rc/rc_curve.cpp:32-98
STATUS: confirmed
REASON: Lines 32-98 exactly span the `generate_rc_curve_params` function, which computes the RC price curve parameters (coeff_a, shift, coeff_b), directly supporting the "Price curve computation" claim.
SUGGESTED_FIX: none

### [60/243] libraries/chain/util/rd.cpp:23-118 — Pool dynamics (decay)
Source: `00-consolidated.md`

CITATION: libraries/chain/util/rd.cpp:23-118
STATUS: confirmed
REASON: The cited range begins exactly at `rd_compute_pool_decay` (line 23) and spans `rd_apply` and `rd_setup_dynamics_params` (ending at line 118), which together implement resource pool decay and equilibrium dynamics, directly supporting the "Pool dynamics (decay)" claim.
SUGGESTED_FIX: none

### [61/243] libraries/chain/include/hive/chain/util/manabar.hpp:32-141 — Manabar struct + update utility
Source: `00-consolidated.md`

CITATION: libraries/chain/include/hive/chain/util/manabar.hpp:32-141
STATUS: confirmed
REASON: The cited range spans exactly the `struct manabar` definition (lines 32-102) and the `update_manabar` utility function (lines 104-141), matching the claim "Manabar struct + update utility" verbatim.
SUGGESTED_FIX: none

### [62/243] libraries/chain/util/dhf_processor.cpp:145-325 — DHF payment processing
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145-325
STATUS: confirmed
REASON: The cited range spans exactly the DHF payment-processing functions (calculate_maintenance_budget, transfer_payments, make_payments, record_funding, and the start of convert_funds), directly supporting the "DHF payment processing" claim.
SUGGESTED_FIX: none

### [63/243] libraries/chain/util/dhf_processor.cpp:145 — DHF budget calculation
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:145
STATUS: confirmed
REASON: Line 145 is the definition of dhf_processor::calculate_maintenance_budget(), which is exactly the DHF (Decentralized Hive Fund) budget calculation the claim references (the {{SOURCE_EXCERPT}} token sits only within the parameter type and does not affect the function's identity).
SUGGESTED_FIX: none

### [64/243] libraries/chain/util/dhf_processor.cpp:325 — DHF HIVE->HBD conversion
Source: `00-consolidated.md`

CITATION: libraries/chain/util/dhf_processor.cpp:325
STATUS: confirmed
REASON: Line 325 is the definition of `dhf_processor::convert_funds`, the DHF function whose daily-maintenance-gated body performs the periodic HIVE→HBD conversion, directly matching the claim.
SUGGESTED_FIX: none

### [65/243] libraries/protocol/include/hive/protocol/config.hpp:56 — HIVE_BLOCK_INTERVAL = 3
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56
STATUS: confirmed
REASON: Line 56 of the excerpt reads `#define HIVE_BLOCK_INTERVAL 3`, matching the claim verbatim at the cited line.
SUGGESTED_FIX: none

### [66/243] libraries/protocol/include/hive/protocol/config.hpp:56-207 — Block, cashout, recovery, feed timings
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:56-207
STATUS: confirmed
REASON: The cited range contains all four claimed timing categories — block (56-59), cashout (73-77 testnet / 155-159 mainnet), recovery (86-89 / 167-170), and feed (108-112 / 189-193) — at the matching pinned SHA.
SUGGESTED_FIX: none

### [67/243] libraries/protocol/include/hive/protocol/config.hpp:150-154 — Values correct, comments wrong (see Discrepancy 6)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:150-154
STATUS: confirmed
REASON: Lines 150-154 hold the genesis/mining-time defines where the numeric values encode the true March 2016 genesis epoch (1458835200 = Mar 24 2016 16:00 UTC) but the inline comments are wrong (line 152 claims "January 1, 2016" for that value), exactly matching the claim "values correct, comments wrong."
SUGGESTED_FIX: none

### [68/243] libraries/protocol/include/hive/protocol/config.hpp:215-346 — Inflation, rewards, HBD limits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:215-346
STATUS: confirmed
REASON: The cited range 215-346 contains exactly the inflation constants (257-259), reward constants (260-294, 331-335), and HBD limit constants (337-346), ending cleanly at HIVE_HBD_HARD_LIMIT before the account-name constants begin.
SUGGESTED_FIX: none

### [69/243] libraries/protocol/include/hive/protocol/config.hpp:282-335 — Pre-HF16 economics, Equihash 140/6
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:282-335
STATUS: confirmed
REASON: Lines 283-284 set HIVE_EQUIHASH_N=140 and HIVE_EQUIHASH_K=6, and lines 282-335 hold the pre-HF16 APR-based reward constants (mining reward, liquidity reward, and curate/content/liquidity/producer/pow APR percentages), directly supporting both halves of the claim.
SUGGESTED_FIX: none

### [70/243] libraries/protocol/include/hive/protocol/config.hpp:348-399 — Transaction, block, name, URL sizes and miscellaneous limits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:348-399
STATUS: confirmed
REASON: Lines 348-399 contain exactly the constants the claim describes — name lengths (348-349), permlink/URL lengths (351-353, 379), transaction sizes (360, 364), block sizes (365-367), and assorted miscellaneous limits — matching the claim verbatim.
SUGGESTED_FIX: none

### [71/243] libraries/protocol/include/hive/protocol/config.hpp:374-378 — 40 mainnet, 41 mirrornet converter
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:374-378
STATUS: confirmed
REASON: Lines 374-378 define HIVE_MAX_AUTHORITY_MEMBERSHIP as 40 when HIVE_CONVERTER_BUILD is undefined (mainnet) and 41 when defined (the mirrornet converter build, "40 + second auth"), matching the claim verbatim.
SUGGESTED_FIX: none

### [72/243] libraries/protocol/include/hive/protocol/config.hpp:383-384 — 2^64−1 / 2^128−1; algorithm in `witness_schedule.cpp
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:383-384
STATUS: confirmed
REASON: Line 383 `fc::to_uint128(0, uint64_t(-1))` equals 2^64−1 and line 384 `fc::uint128_max_value()` equals 2^128−1, matching the claim's two values verbatim at the cited lines.
SUGGESTED_FIX: none

### [73/243] libraries/protocol/include/hive/protocol/config.hpp:393-403 — HIVE_RD_*` budget/decay bounds
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:393-403
STATUS: confirmed
REASON: Lines 393-403 contain exactly the HIVE_RD_* budget/decay bound macros (MIN/MAX_DECAY_BITS, DECAY_DENOM_SHIFT, MAX_POOL_BITS, MAX_BUDGET_1/2/3, MAX_BUDGET, MIN_DECAY, MIN_BUDGET, MAX_DECAY), matching the claim and line range verbatim.
SUGGESTED_FIX: none

### [74/243] libraries/protocol/include/hive/protocol/config.hpp:405-420 — HF20 subsidy budget/decay
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:405-420
STATUS: confirmed
REASON: Lines 405-420 define exactly the account/witness subsidy budget and decay constants (HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET=797, HIVE_DEFAULT_ACCOUNT_SUBSIDY_DECAY=347321, HIVE_WITNESS_SUBSIDY_BUDGET_PERCENT, HIVE_WITNESS_SUBSIDY_DECAY_PERCENT), which are precisely the HF20 account-subsidy budget/decay parameters the claim references.
SUGGESTED_FIX: none

### [75/243] libraries/protocol/include/hive/protocol/config.hpp:441-458 — null, temp, miners, proxy-to-self, root-post-parent, treasury pair (resolved via `database::get_treasury_name()`)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:441-458
STATUS: confirmed
REASON: The excerpt at 441-458 defines exactly the claimed reserved accounts — null, temp, miners, proxy-to-self, root-post-parent — plus the obsolete/new treasury pair with the explicit comment directing resolution via `database::get_treasury_name()`.
SUGGESTED_FIX: none

### [76/243] libraries/protocol/include/hive/protocol/config.hpp:460-469 — Proposal system
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:460-469
STATUS: confirmed
REASON: Lines 460-469 are exactly the "HIVE PROPOSAL SYSTEM support" block (treasury fee, subject max length, max IDs, fee-increase cadence/amount, conversion rate), directly supporting the "Proposal system" claim.
SUGGESTED_FIX: none

### [77/243] libraries/protocol/include/hive/protocol/config.hpp:479-494 — Resource credits (timing only; costs in `libraries/chain/rc/`)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:479-494
STATUS: confirmed
REASON: Lines 479-494 are exactly the "HIVE RC related constants" block, dominated by timing/bucketing params (regen time, bucket length, window count, stats report frequency) with no cost-calculation logic, consistent with the claim that RC costs live in `libraries/chain/rc/`.
SUGGESTED_FIX: none

### [78/243] libraries/protocol/include/hive/protocol/config.hpp:12-14 — Every constant exposed via `database_api.get_config
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:12-14
STATUS: confirmed
REASON: Lines 12-14 contain the verbatim WARNING comment stating every symbol defined in config.hpp must be handled in get_config.cpp (the implementation behind database_api.get_config), directly supporting the claim with the matching line range and text.
SUGGESTED_FIX: none

### [79/243] libraries/protocol/include/hive/protocol/config.hpp:18 — + account list `hardfork.d/0_9.hf:15-172`, applied `database_hardfork.cpp:213-226
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:18
STATUS: drifted
REASON: The cited line holds the HF9 compromised-accounts public-key constant (`HIVE_DEFAULT_HF_9_COMPROMISED_ACCOUNTS_PUBLIC_KEY_STR`) — part of the same feature but not the account list or application code the claim actually asserts, which live in the inline-cited `0_9.hf` and `database_hardfork.cpp`, so the excerpt doesn't substantiate this specific claim.
SUGGESTED_FIX: Verify the claim against its inline citations (`hardfork.d/0_9.hf:15-172` and `libraries/chain/database_hardfork.cpp:213-226`) rather than `config.hpp:18`, and flag the claim↔citation pairing for manual review since config.hpp:18 documents the reset key, not the list/application sites.

### [80/243] libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-32 — Precision bits, shift, NAI encoding, reserved space
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:9-32
STATUS: confirmed
REASON: Lines 9-32 contain exactly the claimed material — precision bits (lines 9, 20-22), NAI shift (line 11, used in 30-32), NAI encoding (lines 12-18, 26-32), and reserved space (SMT_MIN_NON_RESERVED_NAI line 14 plus the reserved-space comment lines 24-25).
SUGGESTED_FIX: none

### [81/243] libraries/protocol/include/hive/protocol/asset_symbol.hpp:20-22 — HBD=3, HIVE=3, VESTS=6
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:20-22
STATUS: confirmed
REASON: Lines 20-22 define HIVE_PRECISION_HBD (3), HIVE_PRECISION_HIVE (3), and HIVE_PRECISION_VESTS (6), matching the claim exactly.
SUGGESTED_FIX: none

### [82/243] libraries/protocol/include/hive/protocol/asset_symbol.hpp:36-53 — STEEM/SBD/TESTS/TBD/HIVE/HBD/VESTS
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:36-53
STATUS: confirmed
REASON: All seven symbols appear verbatim in the cited range — TESTS (37), TBD (39), STEEM (44), HIVE (45), SBD (46), HBD (47), and VESTS (36/43) — matching the testnet/mainnet symbol definitions and confirmed by the SER comments on lines 51-53.
SUGGESTED_FIX: none

### [83/243] libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216 — Legacy vs NAI pack/unpack
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216
STATUS: confirmed
REASON: Lines 157-216 contain exactly the `pack()` (157-187) and `unpack()` (189-216) templates that serialize legacy-space symbols via OBSOLETE/OBD/VESTS_SYMBOL_SER in legacy pack mode versus emitting the NAI `asset_num` otherwise, directly supporting the "Legacy vs NAI pack/unpack" claim (the `{{SOURCE_EXCERPT}}` tokens are rendering artifacts standing in for `&` and do not alter the semantics).
SUGGESTED_FIX: none

### [84/243] libraries/protocol/include/hive/protocol/misc_utilities.hpp:23-68 — legacy/hf26 enum, defaults, pack_guard
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/misc_utilities.hpp:23-68
STATUS: confirmed
REASON: Line 23 defines `enum class serialization_type : uint8_t { legacy, hf26 }`, lines 31-32 set the defaults (hf26 for transaction serialization, legacy for pack), and lines 42-52 define `pack_guard`, fully supporting all three elements of the claim within the cited range.
SUGGESTED_FIX: none

### [85/243] libraries/protocol/include/hive/protocol/asset.hpp:21-96 — Amount + symbol with operator overloads
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:21-96
STATUS: confirmed
REASON: Lines 21-96 are exactly the `struct asset` definition containing the `amount` field (23), `symbol` field (24), and a full set of operator overloads (+=, -=, unary/binary -, ==, !=, <, <=, >, >=, +), matching the claim verbatim.
SUGGESTED_FIX: none

### [86/243] libraries/protocol/include/hive/protocol/asset.hpp:139-186 — Base/quote pair
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:139-186
STATUS: confirmed
REASON: Lines 139-186 define the `price` struct whose members `asset base` (141) and `asset quote` (142), documented as base-expressed-relative-to-quote, directly constitute the claimed base/quote pair.
SUGGESTED_FIX: none

### [87/243] libraries/protocol/include/hive/protocol/asset.hpp:218-322 — Typed thin wrappers
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/asset.hpp:218-322
STATUS: confirmed
REASON: The cited range contains the templated `tiny_asset` struct (218-261) wrapping a single `share_type amount` and the `tiny_price` class (263-322), both thin compile-time-typed wrappers whose own comments describe them as "thin" and "typed enabling compiler to check for errors," directly supporting the claim.
SUGGESTED_FIX: none

### [88/243] libraries/protocol/asset.cpp:80-126 — 8-digit Damm algorithm
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:80-126
STATUS: confirmed
REASON: Lines 80-126 contain the function `damm_checksum_8digit` with a "Damm algorithm" comment, a MAX value of 10^8, and explicit decomposition/processing of 8 digits (d0–d7), directly supporting the "8-digit Damm algorithm" claim.
SUGGESTED_FIX: none

### [89/243] libraries/protocol/asset.cpp:261-283 — NAI range + control bit checks
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:261-283
STATUS: confirmed
REASON: The excerpt is `asset_symbol_type::validate()` whose assert checks NAI range (`nai_data_digits >= SMT_MIN_NAI` && `<= SMT_MAX_NAI`) and the control bit (`nai_1bit == SMT_ASSET_NUM_CONTROL_MASK`), exactly matching the claim "NAI range + control bit checks".
SUGGESTED_FIX: none

### [90/243] libraries/protocol/asset.cpp:310-325 — uint128 cross-multiplication
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/asset.cpp:310-325
STATUS: confirmed
REASON: Lines 310-325 contain the `asset operator * (asset, price)` body which holds the multiplicand in `uint128_t result` and computes `(result * quote.amount) / base.amount` (and the symmetric base/quote branch), i.e. exactly the uint128 cross-multiplication the claim describes.
SUGGESTED_FIX: none

### [91/243] libraries/protocol/include/hive/protocol/types.hpp:66-81 — All fundamental typedefs
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:66-81
STATUS: confirmed
REASON: Lines 66-81 open the `protocol` namespace and contain the complete block of fundamental typedefs (private_key_type through custom_id_type), exactly matching the claim "All fundamental typedefs".
SUGGESTED_FIX: none

### [92/243] libraries/protocol/include/hive/protocol/types.hpp:83-103 — Key data + base58 encoding
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/types.hpp:83-103
STATUS: confirmed
REASON: Lines 83-103 define `public_key_type` holding `key_data` plus a `binary_key` with a `check` checksum, and expose a base58 `std::string` constructor (95) and `explicit operator std::string()` (98), directly supporting "Key data + base58 encoding."
SUGGESTED_FIX: none

### [93/243] libraries/protocol/include/hive/protocol/authority.hpp:7-55 — Threshold + key/account maps
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/authority.hpp:7-55
STATUS: confirmed
REASON: Lines 7-55 define the `authority` struct containing `weight_threshold` (line 52), `key_auths` key_authority_map (line 54, public_key→weight), and `account_auths` account_authority_map (line 53, account_name→weight), exactly matching "Threshold + key/account maps".
SUGGESTED_FIX: none

### [94/243] libraries/protocol/authority.cpp:58-122 — RFC 1035 with Hive rules
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/authority.cpp:58-122
STATUS: confirmed
REASON: Lines 58-122 contain exactly the `check_account_name` function implementing dot-separated label validation — each segment must start with a letter (a-z), end with a letter or digit, and contain only letters/digits/hyphens interior — which is RFC 1035 preferred-name (LDH) syntax, layered with Hive-specific rules (lowercase-only, 3-char minimum segment length, and HIVE_MIN/MAX_ACCOUNT_NAME_LENGTH bounds).
SUGGESTED_FIX: none

### [95/243] libraries/protocol/transaction_util.cpp:18-192 — Posting isolation, role upgrade, HF28 flags
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction_util.cpp:18-192
STATUS: confirmed
REASON: The cited range is exactly the `verify_authority_impl` function and contains all three claimed elements — posting isolation (lines 59-74, the `mixed_with_posting` check), role upgrade (lines 92-104 and 146-158, `check_with_role_upgrade`), and the HF28 flag (`allow_strict_and_mixed_authorities` plus the explicit "Up to HF28" comment).
SUGGESTED_FIX: none

### [96/243] libraries/chain/database.cpp:2595-2623 — HF28 flags, HF20 limits
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/database.cpp:2595-2623
STATUS: confirmed
REASON: Lines 2609-2610 pass HF28 (HIVE_HARDFORK_1_28_*) authority flags and lines 2618-2619 gate the membership/sig-check-account limits on has_hardfork(HIVE_HARDFORK_0_20), exactly matching "HF28 flags, HF20 limits."
SUGGESTED_FIX: none

### [97/243] libraries/protocol/transaction_util.cpp:379-408 — sha256(account+role+password)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction_util.cpp:379-408
STATUS: confirmed
REASON: Lines 400-401 compute `seed = account + role + str` (str being the account password per the line 397 comment) then `fc::sha256::hash(seed)`, which is exactly sha256(account+role+password).
SUGGESTED_FIX: none

### [98/243] libraries/protocol/transaction_util.cpp:410-553 — Wallet-side authority walk
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction_util.cpp:410-553
STATUS: confirmed
REASON: Lines 410-553 contain `signing_keys_collector`'s authority methods and `collect_signing_keys`, whose depth-limited (`HIVE_MAX_SIG_CHECK_DEPTH`) breadth-first traversal of `account_auths` to collect signing keys is exactly the wallet-side authority walk the claim describes.
SUGGESTED_FIX: none

### [99/243] libraries/protocol/include/hive/protocol/block_header.hpp:15-31 — previous, timestamp, witness, merkle root, block_num()
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/block_header.hpp:15-31
STATUS: confirmed
REASON: All five claimed elements appear in the cited range — `previous` (18), `timestamp` (20), `witness` (21), `transaction_merkle_root` (22), and `block_num()` (19) — within the block_header struct spanning lines 15-31.
SUGGESTED_FIX: none

### [100/243] libraries/protocol/block.cpp:13-16 — endian_reverse_u32(id._hash[0])
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/block.cpp:13-16
STATUS: confirmed
REASON: Line 15 within the cited 13-16 range contains `fc::endian_reverse_u32(id._hash[0])` inside `block_header::num_from_id`, supporting the claimed expression verbatim (the `{{SOURCE_EXCERPT}}` token on line 13 is a rendering artifact in the signature, not on the claim line).
SUGGESTED_FIX: none

### [101/243] libraries/protocol/block.cpp:18-46 — Pairwise hashing; production in full_block
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/block.cpp:18-46
STATUS: confirmed
REASON: Lines 18-46 contain `legacy_calculate_merkle_root()` whose comment (line 18) states the actual function is in full_block and whose loop (lines 34-39) hashes IDs in pairs, directly supporting both parts of the claim.
SUGGESTED_FIX: none

### [102/243] libraries/chain/full_block.cpp:305-316 — SHA-224(signed header) + block-num splice, 20 bytes
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/full_block.cpp:305-316
STATUS: confirmed
REASON: The cited construct_block_id function spans lines 305-316 exactly and supports all three claim components — SHA-224 hash of the signed header (line 308), splicing block_num over the first 4 bytes (line 310), and taking the first 20 bytes via min(sizeof(block_id_type)=20, sizeof(sha224)=28) memcpy (lines 312-314).
SUGGESTED_FIX: none

### [103/243] libraries/chain/full_block.cpp:102-156 — SHA-256(unsigned header), sign_compact
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/full_block.cpp:102-156
STATUS: confirmed
REASON: Lines 142–144 pack the unsigned `block_header` (cast away from `signed_block_header`) and hash exactly those `block_header_size` bytes via `digest_type::hash` (SHA-256) into `full_block->digest`, and line 149 signs that digest with `sign_compact`, matching both parts of the claim.
SUGGESTED_FIX: none

### [104/243] libraries/chain/full_block.cpp:352-367 — Authoritative description of digest vs ID
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/full_block.cpp:352-367
STATUS: confirmed
REASON: Lines 361-364 of the excerpt authoritatively define block_digest (sha256 of the serialized block header, used in witness signature verification) versus block_id (sha224 of the signed_block_header with the first four bytes replaced by the block number), exactly matching the claim.
SUGGESTED_FIX: none

### [105/243] libraries/chain/full_block.cpp:336-339 — signee()` public-key recovery
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/full_block.cpp:336-339
STATUS: confirmed
REASON: Lines 336-339 define `full_block_type::signee()`, which returns `fc::ecc::public_key( witness_signature, digest )` — the ECDSA public-key recovery from a signature and digest that the claim describes.
SUGGESTED_FIX: none

### [106/243] libraries/protocol/include/hive/protocol/transaction.hpp:12-53 — ref_block, expiration, operations
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-53
STATUS: confirmed
REASON: The transaction struct at lines 12-53 contains ref_block_num/ref_block_prefix (14-15), expiration (17), and operations (19), matching the claimed fields verbatim.
SUGGESTED_FIX: none

### [107/243] libraries/protocol/transaction.cpp:84-88 — Block number + prefix extraction
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:84-88
STATUS: confirmed
REASON: Lines 84-88 define `set_reference_block`, which assigns `ref_block_num` from `endian_reverse_u32(reference_block._hash[0])` and `ref_block_prefix` from `reference_block._hash[1]` — exactly the block number + prefix extraction the claim describes.
SUGGESTED_FIX: none

### [108/243] libraries/protocol/transaction.cpp:58-64 — SHA-256 truncated to 20 bytes
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:58-64
STATUS: confirmed
REASON: Lines 58-64 hold `transaction::id()`, which `memcpy`s `std::min(sizeof(result), sizeof(h))` = 20 bytes (the size of the ripemd160-backed transaction_id_type) from the SHA-256 `digest(pack)` into the result, exactly matching "SHA-256 truncated to 20 bytes."
SUGGESTED_FIX: none

### [109/243] libraries/protocol/transaction.cpp:29-38 — chain_id + transaction -> SHA-256
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:29-38
STATUS: confirmed
REASON: Lines 29-38 are transaction::sig_digest, which packs chain_id then *this (the transaction) into a digest_type::encoder and returns enc.result() — a SHA-256 digest (digest_type = fc::sha256) — matching "chain_id + transaction -> SHA-256" exactly, with the line range spanning the function verbatim.
SUGGESTED_FIX: none

### [110/243] libraries/chain/full_transaction.cpp:110-116 — chain_id + actual wire bytes
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/full_transaction.cpp:110-116
STATUS: confirmed
REASON: compute_sig_digest packs chain_id (line 113) then writes the raw serialized_transaction bytes directly (line 114), exactly matching the claim "chain_id + actual wire bytes".
SUGGESTED_FIX: none

### [111/243] libraries/chain/full_transaction.cpp:450-493 — OLD_CHAIN_ID pre-HF24-actual-time, bip_0062 note
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/full_transaction.cpp:450-493
STATUS: confirmed
REASON: The cited range contains all three claim elements: the bip_0062 single-mode note (lines 450-451), `pre_hf_1_24_rules = {OLD_CHAIN_ID}` (line 455), and the pre-HF24 logic returning OLD_CHAIN_ID rules when `time <= HIVE_HARDFORK_1_24_ACTUAL_TIME` (lines 479-482).
SUGGESTED_FIX: none

### [112/243] libraries/chain/full_transaction.cpp:263-284 — Byte-compare against re-pack
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/full_transaction.cpp:263-284
STATUS: confirmed
REASON: Lines 280-281 re-pack the transaction via fc::raw::pack and then memcmp the result against the original serialized_transaction bytes, which is exactly "Byte-compare against re-pack" (the `{{SOURCE_EXCERPT}}` token on line 272 is a harmless rendering artifact, not a logic change).
SUGGESTED_FIX: none

### [113/243] libraries/chain/full_transaction.cpp:145-148 — tx_duplicate_sig
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/full_transaction.cpp:145-148
STATUS: confirmed
REASON: The cited range contains the verbatim `hive::protocol::tx_duplicate_sig` throw (line 147) guarded by `HIVE_ASSERT` on the signature-key set insertion, exactly matching the duplicate-signature claim (the `{{SOURCE_EXCERPT}}` token on line 145 is a harness templating artifact, not a code change).
SUGGESTED_FIX: none

### [114/243] libraries/protocol/transaction.cpp:40-56 — operations.size() > 0, per-op validate
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:40-56
STATUS: confirmed
REASON: Line 42 contains the literal `operations.size() > 0` assert ("A transaction must have at least one operation") and lines 43-44 perform the per-operation `operation_validate(op)` loop, exactly matching the claim within the cited 40-56 range.
SUGGESTED_FIX: none

### [115/243] libraries/protocol/transaction.cpp:90-98 — Per-op authority collection
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/transaction.cpp:90-98
STATUS: confirmed
REASON: Lines 90-98 define `transaction::get_required_authorities`, which loops over each operation (`for( const auto& op : operations )`) and calls `operation_get_required_authorities` to collect active/owner/posting/witness/other authorities per operation — exactly "per-op authority collection."
SUGGESTED_FIX: none

### [116/243] libraries/protocol/include/hive/protocol/base.hpp:13-29 — Required authorities interface
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-29
STATUS: confirmed
REASON: Lines 13-29 define base_operation with the get_required_authorities/active/posting/owner_authorities and get_required_witness_signatures methods, which are exactly the "required authorities interface" the claim describes.
SUGGESTED_FIX: none

### [117/243] libraries/protocol/include/hive/protocol/version.hpp:15-77 — Major.HF.release in uint32; 0≡1 hack at 48-75
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:15-77
STATUS: confirmed
REASON: The excerpt shows version packing Major(uint8_t m)/HF(uint8_t h)/release(uint16_t r) into the uint32_t v_num via the 0xFF000000/0x00FF0000/0x0000FFFF masks, and the major-0≡1 equivalence "hack" (with its explanatory comment) lives inside the _operator template at lines 48-75 exactly as claimed.
SUGGESTED_FIX: none

### [118/243] libraries/protocol/include/hive/protocol/version.hpp:79-102 — Masks release bits
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:79-102
STATUS: confirmed
REASON: Lines 79-102 define the `hardfork_version` struct whose constructor, assignment, and comparison operators apply `& 0xFFFF0000` to v_num, masking off the lower 16 revision/release bits and retaining only the major+hardfork portion.
SUGGESTED_FIX: none

### [119/243] libraries/protocol/include/hive/protocol/version.hpp:104-111 — HF version + activation time
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:104-111
STATUS: confirmed
REASON: Lines 104-111 define `hardfork_version_vote` with exactly the two fields `hf_version` (HF version) and `hf_time` (activation time), matching the claim verbatim.
SUGGESTED_FIX: none

### [120/243] libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30 — All 28 HF activation blocks
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hardfork_block.hpp:3-30
STATUS: confirmed
REASON: Lines 3-30 contain exactly 28 `#define HIVE_HARDFORK_*_BLOCK` activation-block constants (HF 0_1 through HF 1_28), matching the claim of "All 28 HF activation blocks."
SUGGESTED_FIX: none

### [121/243] libraries/protocol/hardfork.d/0-preamble.hf:16-19 — HIVE_NUM_HARDFORKS = 28
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/hardfork.d/0-preamble.hf:16-19
STATUS: confirmed
REASON: Both branches in the cited range define `HIVE_NUM_HARDFORKS 28` (line 16 for the alternate chain ID, line 19 for mainnet), supporting the claim verbatim.
SUGGESTED_FIX: none

### [122/243] libraries/protocol/hardfork.d/0_21.hf:18-22 — 35,922,615 mainnet; testnet-configurable
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/hardfork.d/0_21.hf:18-22
STATUS: confirmed
REASON: Lines 18-22 define HIVE_HF_21_STALL_BLOCK as 35922615 (35,922,615) for mainnet under #else and as the testnet_blockchain_configuration value under #ifdef USE_ALTERNATE_CHAIN_ID, exactly matching "35,922,615 mainnet; testnet-configurable".
SUGGESTED_FIX: none

### [123/243] libraries/chain/include/hive/chain/util/manabar.hpp:120-135 — int64 overflow reproduced ≤ stall block
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/include/hive/chain/util/manabar.hpp:120-135
STATUS: confirmed
REASON: The else branch (taken for blocks ≤ HIVE_HF_21_STALL_BLOCK, line 123's negation) performs the raw int64 multiplication on line 134 with explicit overflow detection on lines 131-132, verbatim supporting the claim that the int64 overflow is reproduced at or below the stall block.
SUGGESTED_FIX: none

### [124/243] libraries/protocol/hardfork.d/1_24.hf:17-27 — Scheduled vs ACTUAL (1602703884)
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/hardfork.d/1_24.hf:17-27
STATUS: confirmed
REASON: The cited range contains both HIVE_HARDFORK_1_24_TIME (scheduled, 1601992800) and HIVE_HARDFORK_1_24_ACTUAL_TIME (1602703884 at line 27, matching the comment that ACTUAL_TIME is the block timestamp where the HF took effect), exactly supporting the "Scheduled vs ACTUAL (1602703884)" claim.
SUGGESTED_FIX: none

### [125/243] libraries/protocol/include/hive/protocol/config.hpp:136-143 — Mainnet "beeab0de...", mirrornet "4200...", testnet
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:136-143
STATUS: confirmed
REASON: Within the cited range, line 142 defines mainnet HIVE_CHAIN_ID as "beeab0de..." (comment "Hive mainnet") and line 137 defines the mirrornet ID as "4200..." (comment "Mirrornet"), matching the claim verbatim; the trailing "testnet" item lies outside this USE_ALTERNATE_CHAIN_ID block but does not contradict the supported core.
SUGGESTED_FIX: none

### [126/243] libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23 — Balance-seconds / year * rate
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hbd_interest.hpp:8-23
STATUS: confirmed
REASON: Lines 16-18 compute interest as accumulated balance-seconds (`*hbd_seconds`) divided by `HIVE_SECONDS_PER_YEAR` then multiplied by `hbd_interest_rate`, which is exactly "Balance-seconds / year * rate" (the trailing `/ HIVE_100_PERCENT` is just rate normalization).
SUGGESTED_FIX: none

### [127/243] libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26 — estimate_hive_collateral()` formula
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/hive_collateral.hpp:8-26
STATUS: confirmed
REASON: The cited lines 8-26 contain the `estimate_hive_collateral()` function with its formula intact (multiply_with_fee → HIVE_CONVERSION_COLLATERAL_RATIO / HIVE_100_PERCENT → required_collateral), directly supporting the claim; the `{{SOURCE_EXCERPT}}` markers are display artifacts standing in for the `&` reference tokens in the signature.
SUGGESTED_FIX: none

### [128/243] libraries/chain/database_init.cpp:177-307 — System accounts, initminer, "steem", dgpo
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/database_init.cpp:177-307
STATUS: confirmed
REASON: The cited range is exactly the `init_genesis()` function, which creates the system accounts (miner/null/temp/treasury), the initminer via `HIVE_INIT_MINER_NAME` (lines 262-263), the "steem" account (lines 277-291), and the `dgpo` dynamic_global_property_object (line 293) — all four claim elements present verbatim.
SUGGESTED_FIX: none

### [129/243] libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87-92 — VEST_price(1000000,1000)` on empty pools
Source: `01-protocol-foundation.md`

CITATION: libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87-92
STATUS: confirmed
REASON: Lines 89-90 return VEST_price(1000000, 1000) exactly when either total_vesting_fund_hive or total_vesting_shares amount is 0, matching the empty-pools claim verbatim.
SUGGESTED_FIX: none

### [130/243] libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285 — All configurable defaults
Source: `01-protocol-foundation.md`

CITATION: libraries/protocol/include/hive/protocol/testnet_blockchain_configuration.hpp:27-285
STATUS: confirmed
REASON: Lines 27-285 exactly bracket the `configuration` class definition, whose member fields with initializers (vote windows, cashout, feed, savings, governance, proposal, supply, intervals, etc.) and accompanying get/set/reset methods constitute all configurable defaults, fully supporting the claim.
SUGGESTED_FIX: none

### [131/243] libraries/protocol/include/hive/protocol/operations.hpp:12-125 — All 93 operations with IDs; SKIP_VOPS flag
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/operations.hpp:12-125
STATUS: confirmed
REASON: The excerpt at lines 12-125 enumerates exactly 50 regular operations (IDs 0-49) and 43 virtual operations (last_regular +1 through +43) totaling 93, each with explicit IDs, guarded by the HIVE_PROTOCOL_SKIP_VOPS macro, matching the claim verbatim.
SUGGESTED_FIX: none

### [132/243] libraries/protocol/operations.cpp:7-47 — is_market / is_virtual / is_effective
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/operations.cpp:7-47
STATUS: confirmed
REASON: Lines 7-47 contain exactly the three visitors/functions the claim names — is_market_operation (7-20), is_virtual_operation (22-33), and is_effective_operation (35-47) — matching the claim's is_market/is_virtual/is_effective verbatim.
SUGGESTED_FIX: none

### [133/243] libraries/protocol/include/hive/protocol/base.hpp:13-35 — Authority method signatures; extensions_type
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/base.hpp:13-35
STATUS: confirmed
REASON: The cited range 13-35 contains the five authority method signatures (get_required_*_authorities/witness_signatures at lines 15-19) and the extensions_type typedef (line 35), exactly matching the claim.
SUGGESTED_FIX: none

### [134/243] libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-23 — delegate_rc_operation; "rc" id
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-23
STATUS: confirmed
REASON: The cited range contains both `struct delegate_rc_operation` (line 8) with its from/delegatees/max_rc fields and `#define HIVE_RC_CUSTOM_OPERATION_ID "rc"` (line 23), supporting both parts of the claim verbatim.
SUGGESTED_FIX: none

### [135/243] libraries/protocol/hive_custom_operations.cpp:12-32 — delegatee limits
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/hive_custom_operations.cpp:12-32
STATUS: confirmed
REASON: The cited delegate_rc_operation::validate() at lines 12-32 enforces delegatee limits verbatim — at least one delegatee (line 15), no more than HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP (lines 16-20), and no self-delegation (lines 24-28).
SUGGESTED_FIX: none

### [136/243] libraries/protocol/hive_operations.cpp:601-640 — All `validate()` logic (e.g. limit_order SMT `:601-640`
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/hive_operations.cpp:601-640
STATUS: confirmed
REASON: Lines 601-640 exactly span limit_order_create_operation::validate() and limit_order_create2_operation::validate(), both containing the SMT nai_space (asset_symbol_type::smt_nai_space) branches the claim cites as limit_order SMT validate() logic.
SUGGESTED_FIX: none

### [137/243] libraries/protocol/hive_operations.cpp:287-396 — witness props `:287-396`
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/hive_operations.cpp:287-396
STATUS: confirmed
REASON: Lines 287-396 span exactly the `witness_set_properties_operation::validate()` method, validating all witness properties (fee, block size, interest/exchange rate, signing key, url, subsidy budget/decay), which is precisely what "witness props" denotes.
SUGGESTED_FIX: none

### [138/243] libraries/protocol/hive_operations.cpp:774-782 — reset placeholders `:774-782`)
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/hive_operations.cpp:774-782
STATUS: confirmed
REASON: Lines 774-782 contain exactly the two reset-related placeholder validators (reset_account_operation and set_reset_account_operation), both of which FC_ASSERT(false) as "Placeholder for potential new operation", matching the "reset placeholders" claim and line range verbatim.
SUGGESTED_FIX: none

### [139/243] libraries/protocol/include/hive/protocol/transaction.hpp:12-20 — operations vector; extensions
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/transaction.hpp:12-20
STATUS: confirmed
REASON: The cited range 12-20 contains the `transaction` struct with `vector<operation> operations;` at line 19 and `extensions_type extensions;` at line 20, directly supporting the claim "operations vector; extensions".
SUGGESTED_FIX: none

### [140/243] libraries/protocol/include/hive/protocol/asset_symbol.hpp:69-73 — legacy_space / smt_nai_space enum
Source: `02-operations-catalog.md`

CITATION: libraries/protocol/include/hive/protocol/asset_symbol.hpp:69-73
STATUS: confirmed
REASON: Lines 69-73 contain the `enum asset_symbol_space` with `legacy_space = 1` and `smt_nai_space = 2` exactly as the claim describes.
SUGGESTED_FIX: none

### [141/243] libraries/chain/hive_evaluator.cpp:328-394 — dispatch; size caps; custom_binary disabled
Source: `02-operations-catalog.md`

CITATION: libraries/chain/hive_evaluator.cpp:328-394
STATUS: confirmed
REASON: The cited lines contain all three claim elements — interpreter dispatch via get_custom_json_evaluator/eval->apply (347-359, 382-388), HIVE_CUSTOM_OP_DATA_MAX_LENGTH size caps (332-333, 343-344), and custom_binary disabled via the unreachable-code assert "custom_binary_operation is disallowed" (378).
SUGGESTED_FIX: none

### [142/243] libraries/chain/hive_evaluator.cpp:115 — HF20 block
Source: `02-operations-catalog.md`

CITATION: libraries/chain/hive_evaluator.cpp:115
STATUS: confirmed
REASON: Line 115 contains `HIVE_CHAIN_HARDFORK_ASSERT( _db.has_hardfork( HIVE_HARDFORK_0_20__1620 ), ... )`, which blocks witness_set_properties until HF20, directly supporting the "HF20 block" claim.
SUGGESTED_FIX: none

### [143/243] libraries/chain/database_init.cpp:29-38 — "rc" interpreter wired into core init
Source: `02-operations-catalog.md`

CITATION: libraries/chain/database_init.cpp:29-38
STATUS: confirmed
REASON: The cited range is exactly `database::initialize_evaluators()` (core init), and line 37's `rc().initialize_evaluators()` wires the RC subsystem — which registers the "rc" custom_json interpreter — into core initialization, matching the claim with equivalent semantics.
SUGGESTED_FIX: none

### [144/243] libraries/plugins/chain/chain_plugin.cpp:439-737 — loop :439-737
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:439-737
STATUS: confirmed
REASON: Lines 439-737 are exactly the `start_write_processing()` function, whose body is the documented main write-processing loop (comment at 488-506, `while(true)` at 511) that drains block/transaction writes — matching the "loop" claim verbatim.
SUGGESTED_FIX: none

### [145/243] libraries/plugins/chain/chain_plugin.cpp:180-209 — queues :180-209
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:180-209
STATUS: confirmed
REASON: Lines 180-209 contain exactly the write-queue infrastructure — priority_write_queue/write_queue declarations, the guarding queue_mutex and condition variable, and the add_to_*_queue methods — directly supporting the "queues" claim.
SUGGESTED_FIX: none

### [146/243] libraries/plugins/chain/chain_plugin.cpp:289-413 — visitor :289-413
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:289-413
STATUS: confirmed
REASON: Lines 289-413 contain exactly the `chain_plugin_impl::write_request_visitor` struct definition (a variant visitor with `result_type` and three `operator()` overloads for block/transaction/generate-block flow control), precisely matching the "visitor" claim and the cited line range.
SUGGESTED_FIX: none

### [147/243] libraries/plugins/chain/chain_plugin.cpp:1969-2158 — entry points :1969-2158
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:1969-2158
STATUS: confirmed
REASON: Lines 1969-2158 contain exactly the cluster of chain_plugin entry-point methods (accept_block, accept_transaction, queue_transaction, determine_encoding_and_accept_transaction, push_transaction, push_block, push/queue_generate_block_request), beginning at accept_block (1969) and ending at the close of queue_generate_block_request (2158), supporting the "entry points" claim.
SUGGESTED_FIX: none

### [148/243] libraries/plugins/chain/chain_plugin.cpp:950-1006 — push_transaction()` :950-1006 (incl. fork-switch lambda :963-1000)
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:950-1006
STATUS: confirmed
REASON: The excerpt shows `chain_plugin_impl::push_transaction()` spanning exactly lines 950-1006 (ending at `FC_CAPTURE_AND_RETHROW((trx))`), with the `sf` lambda at 963-1000 that calls `default_block_writer->switch_forks(...)` and `notify_fork(...)`, matching the claimed line ranges and the "fork-switch lambda" description verbatim.
SUGGESTED_FIX: none

### [149/243] libraries/plugins/chain/chain_plugin.cpp:1039-1097 — push_block()` :1039-1097
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:1039-1097
STATUS: confirmed
REASON: The excerpt shows `chain_plugin_impl::push_block(...)` opening at line 1039 and its closing brace at line 1097, exactly matching the cited range.
SUGGESTED_FIX: none

### [150/243] libraries/plugins/chain/chain_plugin.cpp:1099-1119 — `_push_block()` :1099-1119
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:1099-1119
STATUS: confirmed
REASON: The excerpt shows `chain_plugin_impl::_push_block(...)` beginning exactly at line 1099 and its body closing with `FC_CAPTURE_AND_RETHROW()` at line 1119, matching the cited range verbatim.
SUGGESTED_FIX: none

### [151/243] libraries/plugins/chain/chain_plugin.cpp:1046-1062 — checkpoint flags :1046-1062
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:1046-1062
STATUS: confirmed
REASON: Lines 1046-1062 are exactly the `if( !checkpoints.empty() && block_num <= checkpoints.rbegin()->first )` block that sets the consensus skip flags for blocks at/below the last checkpoint, matching the "checkpoint flags" claim verbatim.
SUGGESTED_FIX: none

### [152/243] libraries/plugins/chain/chain_plugin.cpp:1222-1290 — reindex_internal()` :1222-1290
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:1222-1290
STATUS: confirmed
REASON: The excerpt shows `chain_plugin_impl::reindex_internal()` beginning at line 1222 and its final statement at line 1290 (closing brace at 1291), exactly matching the cited range and function name.
SUGGESTED_FIX: none

### [153/243] libraries/plugins/chain/chain_plugin.cpp:1-23 — `irreversible_block_writer.cpp` :1-23
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/chain/chain_plugin.cpp:1-23
STATUS: unparseable
REASON: The finding cites `irreversible_block_writer.cpp` but the pinned citation file is `libraries/plugins/chain/chain_plugin.cpp`, and lines 1-23 there are purely an `#include` block of a different file (it merely includes `irreversible_block_writer.hpp` on line 11), so the reference is mismatched/ambiguous and supports no consensus claim.
SUGGESTED_FIX: Flag for manual review — named file and citation path disagree; re-resolve to the actual implementation file (likely `libraries/chain/irreversible_block_writer.cpp`) and pin the specific lines the finding relies on.

### [154/243] libraries/chain/include/hive/chain/block_flow_control.hpp:135-146 — phases :135-146
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/include/hive/chain/block_flow_control.hpp:135-146
STATUS: confirmed
REASON: Lines 135-146 contain exactly the `enum class phase` definition (REQUEST through END), matching the claim's reference to block-processing phases.
SUGGESTED_FIX: none

### [155/243] libraries/chain/include/hive/chain/block_flow_control.hpp:206-305 — subclasses :206-305
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/include/hive/chain/block_flow_control.hpp:206-305
STATUS: confirmed
REASON: Lines 206-305 contain exactly the four subclasses of block_flow_control (generate_block_flow_control, p2p_block_flow_control, sync_block_flow_control, existing_block_flow_control), matching the "subclasses" claim precisely.
SUGGESTED_FIX: none

### [156/243] libraries/chain/block_flow_control.cpp:46-89 — transitions :46-89
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_flow_control.cpp:46-89
STATUS: confirmed
REASON: Lines 46-89 contain exactly the block_flow_control phase-transition methods (on_write_queue_pop through on_end_of_processing) that set current_phase to START, FORK_DB, FORK_APPLY, FORK_IGNORE, FORK_NORMAL, TXS_EXECUTED, APPLIED, and END, matching the "transitions" claim verbatim.
SUGGESTED_FIX: none

### [157/243] libraries/chain/block_flow_control.cpp:209-267 — promise points :209-267
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_flow_control.cpp:209-267
STATUS: confirmed
REASON: Lines 209-267 contain exactly the two `trigger_promise()` definitions and every call site (`on_end_of_apply_block`, `on_failure`, `on_fork_ignore`, `on_end_of_transactions`) where block-flow-control promises are set/reset, which is precisely what "promise points" denotes.
SUGGESTED_FIX: none

### [158/243] libraries/chain/block_flow_control.cpp:274-284 — sync stats gate :274-284
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_flow_control.cpp:274-284
STATUS: confirmed
REASON: Lines 274-284 are exactly the `sync_block_flow_control::on_worker_done` method whose `HIVE_UP_TO_DATE_MARGIN__BLOCK_STATS` conditional gates stats/report generation for sync blocks, matching the "sync stats gate" claim verbatim.
SUGGESTED_FIX: none

### [159/243] libraries/chain/database.cpp:2183-2369 — _apply_block()` :2183-2369
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2183-2369
STATUS: confirmed
REASON: Line 2183 is exactly the `database::_apply_block(...)` signature and line 2369 is its closing brace with `FC_CAPTURE_CALL_LOG_AND_RETHROW`, matching the claimed span verbatim.
SUGGESTED_FIX: none

### [160/243] libraries/chain/database.cpp:2123-2142 — `apply_block_extended()` :2123-2142
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2123-2142
STATUS: confirmed
REASON: The excerpt shows database::apply_block_extended() defined exactly at lines 2123-2142, matching the cited symbol and line range verbatim.
SUGGESTED_FIX: none

### [161/243] libraries/chain/database.cpp:2757-2779 — `validate_block_header()` :2757-2779
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2757-2779
STATUS: confirmed
REASON: The excerpt shows `database::validate_block_header(...)` beginning exactly at line 2757 and closing with `FC_CAPTURE_AND_RETHROW()` at line 2779, matching the cited function name and line range verbatim.
SUGGESTED_FIX: none

### [162/243] libraries/chain/database.cpp:2644-2702 — _apply_transaction()` :2644-2702
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2644-2702
STATUS: confirmed
REASON: The excerpt shows `database::_apply_transaction()` spanning exactly lines 2644 (signature) through 2702 (closing `FC_CAPTURE_AND_RETHROW`), matching the cited function and line range verbatim.
SUGGESTED_FIX: none

### [163/243] libraries/chain/database.cpp:2521-2642 — `validate_transaction()` :2521-2642
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2521-2642
STATUS: confirmed
REASON: Line 2521 begins `void database::validate_transaction(...)` and line 2642 is its closing brace, exactly matching the cited range and the named function.
SUGGESTED_FIX: none

### [164/243] libraries/chain/database.cpp:552-576 — pending entry :552-576
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:552-576
STATUS: confirmed
REASON: Lines 552-576 exactly span `process_non_fast_confirm_transaction`, which validates a non-fast-confirm transaction's size against the voted block size, sets TX_STATUS_UNVERIFIED, and calls `_push_transaction` to enter it into the pending queue — directly supporting a "pending entry" claim, with the preceding comment (549-551) explicitly referencing the pending queues.
SUGGESTED_FIX: none

### [165/243] libraries/chain/database.cpp:2722-2746 — apply_operation()` :2722-2746
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2722-2746
STATUS: confirmed
REASON: The excerpt shows database_impl::apply_operation() beginning at line 2722 and closing at line 2746, exactly matching the cited range and the claimed function.
SUGGESTED_FIX: none

### [166/243] libraries/chain/include/hive/chain/db_with.hpp:58-243 — pending_transactions_restorer` :58-243
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/include/hive/chain/db_with.hpp:58-243
STATUS: confirmed
REASON: The cited range begins exactly at the struct's doc comment (line 58) and contains the `pending_transactions_restorer` definition (lines 65-226) plus its sole consumer `without_pending_transactions` through the namespace close at 243, matching the claim verbatim.
SUGGESTED_FIX: none

### [167/243] libraries/chain/witness_schedule.cpp:152-396 — update_witness_schedule4()` :152-396
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:152-396
STATUS: confirmed
REASON: The function `update_witness_schedule4()` opens at line 152 and closes with `} FC_CAPTURE_AND_RETHROW() }` at line 396, exactly matching the cited span.
SUGGESTED_FIX: none

### [168/243] libraries/chain/witness_schedule.cpp:372-388 — shuffle :372-388
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:372-388
STATUS: confirmed
REASON: Lines 372-388 contain exactly the witness shuffle algorithm — a comment "shuffle current shuffled witnesses" followed by the xorshift-based Fisher-Yates loop that swaps entries of current_shuffled_witnesses — matching the "shuffle" claim verbatim.
SUGGESTED_FIX: none

### [169/243] libraries/chain/witness_schedule.cpp:403-440 — HF26 dual schedule :403-440
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/witness_schedule.cpp:403-440
STATUS: confirmed
REASON: The excerpt spans the HF26 branch where line 410 checks HIVE_HARDFORK_1_26_FUTURE_WITNESS_SCHEDULE and lines 420-431 implement the dual schedule — promoting future_witness_schedule_object into current and recomputing the future set — exactly as the claim describes.
SUGGESTED_FIX: none

### [170/243] libraries/chain/database.cpp:904-910 — get_scheduled_witness()` :904-910
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:904-910
STATUS: confirmed
REASON: The excerpt shows `database::get_scheduled_witness( uint32_t slot_num )const` spanning exactly lines 904-910, matching the cited function and line range verbatim.
SUGGESTED_FIX: none

### [171/243] libraries/chain/database.cpp:912-935 — `get_slot_time()` :912-935
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:912-935
STATUS: confirmed
REASON: The excerpt shows `database::get_slot_time(uint32_t slot_num)const` beginning at line 912 and its closing brace at line 935, exactly matching the cited range (the `{{SOURCE_EXCERPT}}` token on line 918 is a templating artifact, not real source, and does not bear on the claim).
SUGGESTED_FIX: none

### [172/243] libraries/chain/database.cpp:937-943 — `get_slot_at_time()` :937-943
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:937-943
STATUS: confirmed
REASON: The function `get_slot_at_time()` is defined exactly at lines 937-943 in the provided excerpt, matching the citation verbatim.
SUGGESTED_FIX: none

### [173/243] libraries/chain/database_witness.cpp:284-306 — update_witness_missed_blocks()` :284-306
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database_witness.cpp:284-306
STATUS: confirmed
REASON: The function `update_witness_missed_blocks()` is defined exactly at lines 284-306 in the excerpt, with the signature opening at 284 and closing brace at 306, matching the claim's name and line range.
SUGGESTED_FIX: none

### [174/243] libraries/chain/database_witness.cpp:175-185 — `update_signing_witness()` :175-185
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database_witness.cpp:175-185
STATUS: confirmed
REASON: The excerpt shows `database::update_signing_witness()` spanning exactly lines 175 (signature) through 185 (closing `FC_CAPTURE_AND_RETHROW`), matching the cited function name and line range verbatim.
SUGGESTED_FIX: none

### [175/243] libraries/chain/database.cpp:2789-2841 — update_global_dynamic_data()` :2789-2841
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2789-2841
STATUS: confirmed
REASON: The function `database::update_global_dynamic_data` opens at line 2789 and its body closes with `} FC_CAPTURE_AND_RETHROW() }` at line 2841, exactly matching the cited range and function name.
SUGGESTED_FIX: none

### [176/243] libraries/chain/database.cpp:531-535 — `witness_participation_rate()` :531-535
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:531-535
STATUS: confirmed
REASON: The excerpt shows `database::witness_participation_rate()` defined exactly at lines 531-535, matching the claim's symbol and line range verbatim.
SUGGESTED_FIX: none

### [177/243] libraries/chain/database.cpp:2833-2840 — :2833-2840
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2833-2840
STATUS: confirmed
REASON: At the pinned SHA, lines 2833-2840 contain exactly the claimed undo-history check — `HIVE_ASSERT(_dgp.head_block_number - get_last_irreversible_block_num() < HIVE_MAX_UNDO_HISTORY, undo_database_exception, ...)` gated by `skip_undo_history_check` inside `update_global_dynamic_data()` — matching the claim verbatim (the `{{SOURCE_EXCERPT}}` token resolves to the `&` operator).
SUGGESTED_FIX: none

### [178/243] libraries/chain/database.cpp:369 — `config.hpp:369
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:369
STATUS: unparseable
REASON: The claim cites `config.hpp:369` but the audited citation and the provided excerpt are `libraries/chain/database.cpp:369` (treasury-account name selection), so the reference is internally inconsistent and the claim cannot be verified against the wrong-file excerpt supplied.
SUGGESTED_FIX: Flag for manual review — reconcile whether the finding meant `config.hpp` or `database.cpp` and pin the correct file:line for the cited fact.

### [179/243] libraries/chain/fork_database.cpp:73-99 — _push_block()` :73-99
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:73-99
STATUS: confirmed
REASON: The excerpt shows `fork_database::_push_block()` opening at line 73 and its closing brace at line 99, exactly matching the cited range and the claimed symbol.
SUGGESTED_FIX: none

### [180/243] libraries/chain/fork_database.cpp:20-28 — `pop_block()` :20-28
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:20-28
STATUS: confirmed
REASON: The excerpt shows `fork_database::pop_block()` defined exactly at lines 20-28, matching the cited function and line range verbatim.
SUGGESTED_FIX: none

### [181/243] libraries/chain/fork_database.cpp:146-175 — `set_max_size()` :146-175
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:146-175
STATUS: confirmed
REASON: The source at line 146 defines `void fork_database::set_max_size( uint32_t s )` exactly as cited, and the 146-175 range captures the full function logic (both index/unlinked_index pruning loops); the only divergence is the trailing closing braces falling at 176-178, which is trivially equivalent.
SUGGESTED_FIX: none

### [182/243] libraries/chain/fork_database.cpp:255 — witness map :255
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:255
STATUS: confirmed
REASON: Line 255 declares `fork_database::get_last_block_generated_by_each_witness()` returning `std::map<account_name_type, block_id_type>`, which is precisely the witness-keyed map the claim describes.
SUGGESTED_FIX: none

### [183/243] libraries/chain/fork_database.cpp:290-330 — `fetch_branch_from()` :290-330
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/fork_database.cpp:290-330
STATUS: confirmed
REASON: The function signature `fork_database::fetch_branch_from(...)` appears verbatim at line 290 and the cited 290-330 range covers essentially the entire function body (which returns at 332), matching the claim's location reference.
SUGGESTED_FIX: none

### [184/243] libraries/chain/sync_block_writer.cpp:67-160 — push_block()` :67-160
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:67-160
STATUS: confirmed
REASON: The function `sync_block_writer::push_block()` begins at line 67 and its closing brace is at line 160, matching the cited range exactly.
SUGGESTED_FIX: none

### [185/243] libraries/chain/sync_block_writer.cpp:162-264 — `switch_forks()` :162-264
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:162-264
STATUS: confirmed
REASON: The function definition `sync_block_writer::switch_forks(...)` opens at line 162 and closes with `} // switch_forks` at line 264, exactly matching the cited range and symbol.
SUGGESTED_FIX: none

### [186/243] libraries/chain/sync_block_writer.cpp:24-60 — `store_block()` :24-60
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:24-60
STATUS: confirmed
REASON: The excerpt shows `sync_block_writer::store_block()` beginning exactly at line 24 and its closing brace at line 60, matching the cited range verbatim.
SUGGESTED_FIX: none

### [187/243] libraries/chain/database.cpp:2956-3064 — update_last_irreversible_block()` :2956-3064
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2956-3064
STATUS: confirmed
REASON: The excerpt shows `database::update_last_irreversible_block(...)` opening exactly at line 2956 and closing with `} FC_CAPTURE_AND_RETHROW() }` at line 3064, matching the cited function name and line range verbatim.
SUGGESTED_FIX: none

### [188/243] libraries/chain/sync_block_writer.cpp:266-367 — find_new_last_irreversible_block()` :266-367
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/sync_block_writer.cpp:266-367
STATUS: confirmed
REASON: The excerpt shows `sync_block_writer::find_new_last_irreversible_block(` beginning at line 266 (return type) and closing with `} // find_new_last_irreversible_block` at line 367, matching the cited range exactly.
SUGGESTED_FIX: none

### [189/243] libraries/chain/database.cpp:537-541 — is_fast_confirm_transaction()` :537-541
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:537-541
STATUS: confirmed
REASON: The excerpt shows database::is_fast_confirm_transaction() defined exactly at lines 537-541, matching the cited function and line range verbatim (the {{SOURCE_EXCERPT}} placeholders are merely elided & / && tokens that don't affect the claim).
SUGGESTED_FIX: none

### [190/243] libraries/chain/database.cpp:2899-2954 — `process_fast_confirm_transaction()` :2899-2954
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:2899-2954
STATUS: confirmed
REASON: The excerpt shows `database::process_fast_confirm_transaction(...)` beginning exactly at line 2899 and its closing `FC_CAPTURE_AND_RETHROW() }` at line 2954, matching the claimed function name and line range verbatim.
SUGGESTED_FIX: none

### [191/243] libraries/plugins/witness/witness_plugin.cpp:219-308 — on_finish_push_block()` :219-308
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:219-308
STATUS: confirmed
REASON: The function `witness_plugin_impl::on_finish_push_block()` begins at line 219 and its closing brace is at line 308, exactly matching the cited range.
SUGGESTED_FIX: none

### [192/243] libraries/plugins/witness/witness_plugin.cpp:533-546 — toggle :533-546
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:533-546
STATUS: confirmed
REASON: Lines 533-546 contain exactly the enable_fast_confirm/disable_fast_confirm/is_fast_confirm_enabled methods that set, clear, and read the _enable_fast_confirm atomic — a verbatim on/off toggle.
SUGGESTED_FIX: none

### [193/243] libraries/chain/database.cpp:3066-3097 — migrate_irreversible_state()` :3066-3097
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/database.cpp:3066-3097
STATUS: confirmed
REASON: The excerpt shows `database::migrate_irreversible_state(uint32_t old_last_irreversible)` opening at line 3066 and its closing brace at line 3097, matching the claimed function and line range exactly.
SUGGESTED_FIX: none

### [194/243] libraries/plugins/witness/witness_plugin.cpp:310-367 — production data :310-367
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:310-367
STATUS: confirmed
REASON: Lines 310-367 exactly span the `update_produce_block_data` function, which computes the scheduled witness/key and populates the `produce_block_data` structure under mutex, matching the "production data" claim.
SUGGESTED_FIX: none

### [195/243] libraries/plugins/witness/witness_plugin.cpp:369-467 — loop :369-467
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:369-467
STATUS: confirmed
REASON: Lines 369-467 contain exactly the `schedule_production_loop()` and self-rescheduling `block_production_loop()` functions that implement the witness block production loop, with line 465 re-arming the timer to form the loop.
SUGGESTED_FIX: none

### [196/243] libraries/plugins/witness/witness_plugin.cpp:469-526 — `maybe_produce_block()` :469-526
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:469-526
STATUS: confirmed
REASON: Line 469 begins the definition of `witness_plugin_impl::maybe_produce_block(...)` and line 526 is its closing brace, so the cited range matches the named function exactly.
SUGGESTED_FIX: none

### [197/243] libraries/plugins/witness/witness_plugin.cpp:570-577 — queen mode :570-577
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/witness_plugin.cpp:570-577
STATUS: confirmed
REASON: Lines 570-577 contain exactly the `witness_plugin::enable_queen_mode()` function whose body sets `_queen_mode = true` and ignores configured witnesses, directly supporting the queen-mode claim.
SUGGESTED_FIX: none

### [198/243] libraries/plugins/witness/block_producer.cpp:31-85 — _generate_block()` :31-85
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:31-85
STATUS: confirmed
REASON: The excerpt shows `block_producer::_generate_block(...)` opening at line 31 and its closing brace at line 85, exactly matching the cited function and line range.
SUGGESTED_FIX: none

### [199/243] libraries/plugins/witness/block_producer.cpp:87-108 — hardfork votes :87-108
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:87-108
STATUS: confirmed
REASON: Lines 87-108 contain the `adjust_hardfork_version_vote` function which sets the witness's hardfork version/time vote in the pending block header extensions, directly supporting the "hardfork votes" claim at the exact cited range.
SUGGESTED_FIX: none

### [200/243] libraries/plugins/witness/block_producer.cpp:111-216 — `apply_pending_transactions()` :111-216
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:111-216
STATUS: confirmed
REASON: The function `block_producer::apply_pending_transactions(...)` begins at line 111 and its body closes at line 216 (next function starts at 218), exactly matching the cited range.
SUGGESTED_FIX: none

### [201/243] libraries/plugins/witness/block_producer.cpp:218-253 — queen fill :218-253
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/witness/block_producer.cpp:218-253
STATUS: confirmed
REASON: Lines 218-253 are exactly the `fill_block_with_transactions` function whose own comment (lines 223-228) identifies it as the simplified block-filling path "used by queen_plugin ... when queen is active," matching the "queen fill" claim verbatim.
SUGGESTED_FIX: none

### [202/243] libraries/plugins/queen/queen_plugin.cpp:98-127 — production trigger :98-127
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/queen/queen_plugin.cpp:98-127
STATUS: confirmed
REASON: Lines 98-127 are exactly the `on_post_apply_transaction` handler whose else-branch (113-125) issues `queue_generate_block_request`, which is precisely the block "production trigger" the claim describes.
SUGGESTED_FIX: none

### [203/243] libraries/plugins/queen/queen_plugin.cpp:162-223 — slot scan :162-223
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/queen/queen_plugin.cpp:162-223
STATUS: confirmed
REASON: Lines 162-223 are exactly the `prepare_for_new_block()` function whose for-loop (186-216) scans witness slots — breaking on `produce_in_next_slot` or advancing `next_slot_time` by `HIVE_BLOCK_INTERVAL` — which is precisely the "slot scan" the claim describes.
SUGGESTED_FIX: none

### [204/243] libraries/plugins/queen/queen_plugin.cpp:268-297 — init/testnet guard :268-297
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/queen/queen_plugin.cpp:268-297
STATUS: confirmed
REASON: Lines 268-297 are exactly the `plugin_initialize` function (init), and lines 273-275 contain the testnet guard `#ifndef USE_ALTERNATE_CHAIN_ID` / `FC_ASSERT( false, "Queen plugin cannot be used with mainnet..." )`, supporting the "init/testnet guard" claim verbatim.
SUGGESTED_FIX: none

### [205/243] libraries/plugins/p2p/p2p_plugin.cpp:128-207 — handle_block()` :128-207
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/p2p/p2p_plugin.cpp:128-207
STATUS: confirmed
REASON: The source excerpt shows `p2p_plugin_impl::handle_block(...)` beginning exactly at line 128 and its closing `FC_CAPTURE_AND_RETHROW((sync_mode))` at line 207, matching the cited range verbatim.
SUGGESTED_FIX: none

### [206/243] libraries/plugins/p2p/p2p_plugin.cpp:209-226 — `handle_transaction()` :209-226
Source: `06-consensus-mechanisms.md`

CITATION: libraries/plugins/p2p/p2p_plugin.cpp:209-226
STATUS: confirmed
REASON: Lines 209-226 contain exactly the `p2p_plugin_impl::handle_transaction()` function definition as cited, matching the claimed symbol and line range.
SUGGESTED_FIX: none

### [207/243] libraries/chain/block_log_wrapper.cpp:616-767 — open/auto-split :616-767
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_wrapper.cpp:616-767
STATUS: confirmed
REASON: Lines 616-767 are exactly the body of `block_log_wrapper::common_open_and_init`, which opens the block log and auto-splits a legacy monolithic log into parts (try_splitting_monolithic_log_file at 663-665), matching the "open/auto-split" claim verbatim.
SUGGESTED_FIX: none

### [208/243] libraries/chain/block_log_wrapper.cpp:527-591 — `force_parts_exist()` :527-591
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_wrapper.cpp:527-591
STATUS: confirmed
REASON: The excerpt shows `block_log_wrapper::force_parts_exist(...)` opening at line 527 and its closing brace at line 591, exactly matching the cited span and function name.
SUGGESTED_FIX: none

### [209/243] libraries/chain/block_log_wrapper.cpp:804-849 — rotation+GC :804-849
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_wrapper.cpp:804-849
STATUS: confirmed
REASON: Lines 804-849 are exactly the `internal_append` function, which performs file rotation (switching to a new part file and deleting old files via `_block_log_split` at lines 831-836) and garbage collection (`_garbage_collection.push_back` and `dispose_garbage()` at lines 840-842), matching the "rotation+GC" claim.
SUGGESTED_FIX: none

### [210/243] libraries/chain/block_log_wrapper.cpp:280-305 — pruned reads :280-305
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_wrapper.cpp:280-305
STATUS: confirmed
REASON: Lines 280-305 contain get_block_by_number, whose FC_ASSERT explicitly handles pruned reads with the message "Block ${num} has been pruned (oldest stored block is ${old})", directly supporting the claim at the cited line range.
SUGGESTED_FIX: none

### [211/243] libraries/chain/split_block_log.cpp:11-113 — split_block_log()` :11-113
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/split_block_log.cpp:11-113
STATUS: confirmed
REASON: The excerpt shows the `split_block_log()` function definition beginning at line 11 (signature) and closing at line 113 (terminating brace), exactly matching the cited range.
SUGGESTED_FIX: none

### [212/243] libraries/chain/block_log.cpp:44-72 — naming :44-72
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:44-72
STATUS: confirmed
REASON: Lines 44-72 define the block_log_file_name_info naming constants (_legacy_file_name, _split_file_name_core, _artifacts_extension) and the file-naming functions (get_first_block_num_for_file_name, get_nth_part_file_name), directly supporting the "naming" claim.
SUGGESTED_FIX: none

### [213/243] libraries/chain/block_log.cpp:338-366 — `append_raw()` :338-366
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:338-366
STATUS: confirmed
REASON: Lines 338-366 span both `block_log::append_raw()` overloads exactly — the convenience overload opens at line 338 and the full implementation closes at line 366 — matching the cited range verbatim.
SUGGESTED_FIX: none

### [214/243] libraries/chain/block_log.cpp:491-515 — `read_block_by_num()` :491-515
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log.cpp:491-515
STATUS: confirmed
REASON: The excerpt shows `block_log::read_block_by_num(uint32_t block_num)` defined exactly at lines 491-515, matching the cited function name and line range verbatim.
SUGGESTED_FIX: none

### [215/243] libraries/chain/block_log_artifacts.cpp:46-69 — header :46-69
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_artifacts.cpp:46-69
STATUS: confirmed
REASON: Lines 46-69 of the excerpt contain exactly the `artifact_file_header` struct definition (opening at line 46, closing brace at line 69), matching the "header :46-69" citation verbatim.
SUGGESTED_FIX: none

### [216/243] libraries/chain/block_log_artifacts.cpp:82-166 — chunk :82-166
Source: `06-consensus-mechanisms.md`

CITATION: libraries/chain/block_log_artifacts.cpp:82-166
STATUS: confirmed
REASON: Lines 82-166 of the excerpt precisely bracket the `artifact_file_chunk` struct (opening `struct artifact_file_chunk` at line 82, closing `};` at line 166), matching the "chunk" reference in the finding.
SUGGESTED_FIX: none

### [217/243] block_log.hpp` :11-15, `block_storage_interface.hpp` :9 — 1M blocks/part (400 testnet), batch 10k (400), max 9999 parts
Source: `06-consensus-mechanisms.md`

STATUS: UNPARSEABLE
REASON: File not found at pinned commit: block_log.hpp` :11-15, `block_storage_interface.hpp` 

### [218/243] libraries/chain/hive_evaluator_social.cpp:108-172 — Comment options/beneficiaries
Source: `07-economic-model.md`

CITATION: libraries/chain/hive_evaluator_social.cpp:108-172
STATUS: confirmed
REASON: Lines 108-135 define the comment_payout_beneficiaries extension visitor and lines 137-172 implement comment_options_evaluator::do_apply, directly covering comment options configuration and beneficiary handling as the claim states.
SUGGESTED_FIX: none

### [219/243] libraries/chain/witness_schedule.cpp:82-86 — Interest median
Source: `07-economic-model.md`

CITATION: libraries/chain/witness_schedule.cpp:82-86
STATUS: confirmed
REASON: Lines 82-85 sort active witnesses by hbd_interest_rate and line 86 selects the middle element as median_hbd_interest_rate, exactly supporting the "Interest median" claim.
SUGGESTED_FIX: none

### [220/243] libraries/chain/include/hive/chain/detail/state/account_object.hpp:301-317 — Governance vote power
Source: `07-economic-model.md`

CITATION: libraries/chain/include/hive/chain/detail/state/account_object.hpp:301-317
STATUS: confirmed
REASON: Lines 301-317 contain exactly the governance vote power accessors — get_direct_governance_vote_power() (vesting_shares minus delayed votes) and get_governance_vote_power() (direct plus proxied_vsf_votes) — matching the claim verbatim with line numbers intact.
SUGGESTED_FIX: none

### [221/243] libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87-96 — Vesting prices
Source: `07-economic-model.md`

CITATION: libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87-96
STATUS: confirmed
REASON: The cited lines contain get_vesting_share_price() and get_reward_vesting_share_price(), which compute vesting share prices exactly as the "Vesting prices" claim describes.
SUGGESTED_FIX: none

### [222/243] protocol/compound.hpp` + `config.hpp:305-317 — calc_percent_reward<>()
Source: `07-economic-model.md`

STATUS: UNPARSEABLE
REASON: File not found at pinned commit: protocol/compound.hpp` + `config.hpp

### [223/243] libraries/chain/database_hardfork.cpp:336-416 — HF20 RC initialization
Source: `08-resource-credits.md`

CITATION: libraries/chain/database_hardfork.cpp:336-416
STATUS: confirmed
REASON: Lines 336-416 are exactly the `case HIVE_HARDFORK_0_20` block, which contains an explicit `// Initialize RC:` comment (line 366) followed by the full RC initialization logic — loading resource params, creating rc_resource_param/pool/stats objects, usage buckets, and per-account rc_adjustment/rc_manabar setup.
SUGGESTED_FIX: none

### [224/243] libraries/protocol/include/hive/protocol/config.hpp:390-494 — RC-related constants
Source: `08-resource-credits.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:390-494
STATUS: confirmed
REASON: The cited range contains RC-related constants verbatim — the HIVE_RD_* resource-dynamics decay/budget block (393-403), account-subsidy constants (405-420), and the explicit "HIVE RC related constants" section (479-494 with HIVE_RC_REGEN_TIME, bucket/window, stats frequency, historical adjustment, and max-accounts-per-delegation) — matching the line numbers exactly.
SUGGESTED_FIX: none

### [225/243] libraries/chain/database_hardfork.cpp:24 — init_hardforks()` (:24)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_hardfork.cpp:24
STATUS: confirmed
REASON: Line 24 of the cited file contains `void database::init_hardforks()`, exactly matching the claim that `init_hardforks()` is defined at line 24.
SUGGESTED_FIX: none

### [226/243] libraries/chain/database_hardfork.cpp:114 — `process_hardforks()` (:114)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_hardfork.cpp:114
STATUS: confirmed
REASON: Line 114 of the cited file contains exactly `void database::process_hardforks()`, matching the claim verbatim.
SUGGESTED_FIX: none

### [227/243] libraries/chain/database_hardfork.cpp:146 — `has_hardfork()` (:146)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_hardfork.cpp:146
STATUS: confirmed
REASON: Line 146 in the excerpt contains exactly the definition `bool database::has_hardfork( uint32_t hardfork )const`, matching the cited `has_hardfork()` reference verbatim.
SUGGESTED_FIX: none

### [228/243] libraries/chain/database_hardfork.cpp:151 — `get_hardfork()` (:151)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_hardfork.cpp:151
STATUS: confirmed
REASON: Line 151 is exactly the definition `uint32_t database::get_hardfork()const`, matching the claim verbatim.
SUGGESTED_FIX: none

### [229/243] libraries/chain/database_hardfork.cpp:156 — `set_hardfork()` (:156)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_hardfork.cpp:156
STATUS: confirmed
REASON: Line 156 of the excerpt contains exactly `void database::set_hardfork( uint32_t hardfork, bool apply_now )`, matching the claim that `set_hardfork()` is defined at line 156.
SUGGESTED_FIX: none

### [230/243] libraries/chain/database_hardfork.cpp:178 — `apply_hardfork()` (:178)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_hardfork.cpp:178
STATUS: confirmed
REASON: Line 178 of the excerpt contains exactly `void database::apply_hardfork( uint32_t hardfork )`, matching the claimed function and line number verbatim.
SUGGESTED_FIX: none

### [231/243] libraries/chain/database_hardfork.cpp:562 — `gather_balance()` (:562)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database_hardfork.cpp:562
STATUS: confirmed
REASON: Line 562 contains the definition `void database::gather_balance( const std::string& name, const HIVE_asset& hive_balance, const HBD_asset& hbd_balance )`, exactly matching the claimed `gather_balance()` location (the `{{SOURCE_EXCERPT}}` tokens are templating artifacts for the `&` reference/capture symbols).
SUGGESTED_FIX: none

### [232/243] libraries/protocol/include/hive/protocol/version.hpp:48-75 — major-0/1 equivalence (:48-75)
Source: `09-hardfork-history.md`

CITATION: libraries/protocol/include/hive/protocol/version.hpp:48-75
STATUS: confirmed
REASON: Lines 48-75 are the `_operator` template whose comment block (51-55) and masking branches (58-61, annotated `0.HARDFORK_NUMBER == 1.HARDFORK_NUMBER` and `1.HARDFORK_NUMBER == 0.HARDFORK_NUMBER`) directly implement the major-version 0/1 equivalence the claim describes.
SUGGESTED_FIX: none

### [233/243] libraries/chain/witness_schedule.cpp:262-350 — Witness-vote tally + HF23 force
Source: `09-hardfork-history.md`

CITATION: libraries/chain/witness_schedule.cpp:262-350
STATUS: confirmed
REASON: Lines 266-282 tally witness running_version counts and hardfork_version_votes, and lines 289-302 force HF23 via the "Forcing HF23 without need to have witness majority version" branch, exactly matching the "Witness-vote tally + HF23 force" claim within the cited 262-350 range.
SUGGESTED_FIX: none

### [234/243] libraries/chain/database.cpp:61-80 — next_hf_time()` (HF28 time + env override)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:61-80
STATUS: confirmed
REASON: Lines 61-80 contain the exact `next_hf_time()` definition that returns a hardcoded HF28 time (commented "current next hardfork is HF28") overridable via the `HIVE_HF28_TIME` environment variable, matching the claim verbatim.
SUGGESTED_FIX: none

### [235/243] libraries/chain/database.cpp:1422-1459 — restore_accounts()` (HF24)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:1422-1459
STATUS: confirmed
REASON: The excerpt shows `database::restore_accounts()` spanning exactly lines 1422-1459 (signature to closing brace), restoring h23_balances from the treasury back to accounts — the HF24 restoration logic the claim names.
SUGGESTED_FIX: none

### [236/243] libraries/chain/database.cpp:1461-1643 — clear_accounts()` / `clear_account()` (HF23)
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:1461-1643
STATUS: confirmed
REASON: Lines 1461-1643 contain exactly `clear_accounts()` (1461-1472) and `clear_account()` (1474-1643), which push the `hardfork_hive_operation` virtual op and sweep account funds to the treasury — the HF23 (Hive genesis) account-clearing logic the claim describes.
SUGGESTED_FIX: none

### [237/243] libraries/chain/database.cpp:2283-2290 — Per-block `running_version >= current_hardfork_version` assert
Source: `09-hardfork-history.md`

CITATION: libraries/chain/database.cpp:2283-2290
STATUS: confirmed
REASON: Lines 2287-2289 contain `FC_ASSERT(witness.running_version >= hardfork_state.current_hardfork_version, ...)` gated by a per-block hardfork check, matching the claimed per-block `running_version >= current_hardfork_version` assert verbatim.
SUGGESTED_FIX: none

### [238/243] libraries/chain/full_transaction.cpp:469-483 — Signature-validation epoch keyed on `HIVE_HARDFORK_1_24_ACTUAL_TIME
Source: `09-hardfork-history.md`

CITATION: libraries/chain/full_transaction.cpp:469-483
STATUS: confirmed
REASON: Line 479 selects between pre/post HF 1.24 signature validation rules using `time.sec_since_epoch() > HIVE_HARDFORK_1_24_ACTUAL_TIME`, exactly matching the claim that the signature-validation epoch is keyed on that constant.
SUGGESTED_FIX: none

### [239/243] libraries/protocol/include/hive/protocol/config.hpp:231 — HIVE_HARDFORK_REQUIRED_WITNESSES = 17
Source: `09-hardfork-history.md`

CITATION: libraries/protocol/include/hive/protocol/config.hpp:231
STATUS: confirmed
REASON: Line 231 of the provided excerpt defines HIVE_HARDFORK_REQUIRED_WITNESSES as 17 verbatim, matching the claim exactly.
SUGGESTED_FIX: none

### [240/243] libraries/manifest/templates/plugins/mf_plugins.cpp.j2:17-39 — `libraries/manifest/CMakeLists.txt:17-39
Source: `10-api-layer.md`

CITATION: libraries/manifest/templates/plugins/mf_plugins.cpp.j2:17-39
STATUS: drifted
REASON: The file is the correct manifest plugin-registration template and lines 14-16 show the `app.register_plugin<...>()` loop that supports the claim, but the cited range 17-39 points only at closing braces (17-19) and runs past the file's end (the excerpt terminates at line 19), so the line numbers are stale.
SUGGESTED_FIX: Repoint to `libraries/manifest/templates/plugins/mf_plugins.cpp.j2:14-16` (the plugin registration loop); flag for manual review since the original 17-39 range extends well beyond EOF.

### [241/243] libraries/plugins/json_rpc/json_rpc_plugin.cpp:457-489 — Legacy-serialization retry
Source: `10-api-layer.md`

CITATION: libraries/plugins/json_rpc/json_rpc_plugin.cpp:457-489
STATUS: confirmed
REASON: Lines 457-489 catch the bad_cast exception from the first call attempt, flag broadcast_transaction/verify_authority for serialization change, then re-invoke the call under a `transaction_serialization_type::legacy` mode_guard — exactly a legacy-serialization retry.
SUGGESTED_FIX: none

### [242/243] libraries/plugins/apis/debug_node_api/include/hive/plugins/debug_node_api/debug_node_api.hpp:170 — dead schema `debug_node_api.cpp:170
Source: `10-api-layer.md`

CITATION: libraries/plugins/apis/debug_node_api/include/hive/plugins/debug_node_api/debug_node_api.hpp:170
STATUS: drifted
REASON: The cited line resolves to a real part of the debug_node_api method-declaration list, but the claim names `.cpp` while these declarations live in `.hpp`, and line 170 is a doc-comment terminator (`*/`) rather than the `debug_generate_blocks_until` declaration it precedes at line 171.
SUGGESTED_FIX: Repoint to `libraries/plugins/apis/debug_node_api/include/hive/plugins/debug_node_api/debug_node_api.hpp:171`, or flag for manual review since "dead schema" is an assertion about the API as a whole rather than a single line.

### [243/243] libraries/plugins/apis/node_status_api/node_status_api.cpp:36 — EARLY-registered status APIs
Source: `10-api-layer.md`

CITATION: libraries/plugins/apis/node_status_api/node_status_api.cpp:36
STATUS: confirmed
REASON: Line 36 calls JSON_RPC_REGISTER_EARLY_API for the node_status_api plugin, directly supporting the claim that status APIs are EARLY-registered.
SUGGESTED_FIX: none

## Summary

| Status | Count |
|--------|------:|
| confirmed  | 237 |
| drifted    | 2 |
| broken     | 0 |
| unparseable| 4 |
