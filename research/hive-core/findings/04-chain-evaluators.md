# Part 4: Chain Evaluators — Dispatch and Database Helpers

Source-verified analysis of how evaluators are dispatched and what database helper
methods they call to mutate chain state.

---

## 1. Evaluator Dispatch Architecture

### 1.1 Class Hierarchy

```
evaluator<OperationType>                     (abstract base)
  └─ evaluator_impl<EvaluatorType>           (template CRTP bridge)
       └─ transfer_evaluator                 (concrete, via HIVE_DEFINE_EVALUATOR macro)
       └─ vote_evaluator
       └─ ... (one per operation type)
```

**Key files:**
- `libraries/chain/include/hive/chain/evaluator.hpp` — base class + `HIVE_DEFINE_EVALUATOR` macro
- `libraries/chain/include/hive/chain/evaluator_registry.hpp` — dispatch table
- `libraries/chain/include/hive/chain/hive_evaluator.hpp` — registration function declarations

The `HIVE_DEFINE_EVALUATOR(X)` macro generates a class `X_evaluator` with:
- `typedef X_operation operation_type;`
- Constructor taking `database& db`
- Pure virtual `do_apply(const X_operation& o)` that subclasses implement

The `evaluator_impl::apply()` method casts the variant `operation` to the concrete
operation type and calls `do_apply()`.

### 1.2 Registration

`database::initialize_evaluators()` (in `database_init.cpp`) calls five registration
functions, each populating the same `evaluator_registry<operation>`:

```cpp
void database::initialize_evaluators()
{
  register_social_evaluators( _my->_evaluator_registry );   // hive_evaluator_social.cpp
  register_transfer_evaluators( _my->_evaluator_registry ); // hive_evaluator_transfer.cpp
  register_account_evaluators( _my->_evaluator_registry );  // hive_evaluator_account.cpp
  register_witness_evaluators( _my->_evaluator_registry );  // hive_evaluator.cpp
  register_dhf_evaluators( _my->_evaluator_registry );      // dhf_evaluator.cpp

  rc().initialize_evaluators();
}
```

The `evaluator_registry` holds a `vector<unique_ptr<evaluator<operation>>>` indexed
by the operation's `which()` tag (its position in the `operation` variant).
`register_evaluator<EvaluatorType>()` inserts at slot
`operation::tag<EvaluatorType::operation_type>::value`.

### 1.3 Complete Evaluator Registration Map

#### Social Evaluators (hive_evaluator_social.cpp)
| Evaluator | Operation |
|-----------|-----------|
| `vote_evaluator` | `vote_operation` |
| `comment_evaluator` | `comment_operation` |
| `comment_options_evaluator` | `comment_options_operation` |
| `delete_comment_evaluator` | `delete_comment_operation` |

#### Transfer Evaluators (hive_evaluator_transfer.cpp)
| Evaluator | Operation |
|-----------|-----------|
| `transfer_evaluator` | `transfer_operation` |
| `transfer_to_vesting_evaluator` | `transfer_to_vesting_operation` |
| `withdraw_vesting_evaluator` | `withdraw_vesting_operation` |
| `set_withdraw_vesting_route_evaluator` | `set_withdraw_vesting_route_operation` |
| `convert_evaluator` | `convert_operation` |
| `collateralized_convert_evaluator` | `collateralized_convert_operation` |
| `limit_order_create_evaluator` | `limit_order_create_operation` |
| `limit_order_create2_evaluator` | `limit_order_create2_operation` |
| `limit_order_cancel_evaluator` | `limit_order_cancel_operation` |
| `escrow_transfer_evaluator` | `escrow_transfer_operation` |
| `escrow_approve_evaluator` | `escrow_approve_operation` |
| `escrow_dispute_evaluator` | `escrow_dispute_operation` |
| `escrow_release_evaluator` | `escrow_release_operation` |
| `transfer_to_savings_evaluator` | `transfer_to_savings_operation` |
| `transfer_from_savings_evaluator` | `transfer_from_savings_operation` |
| `cancel_transfer_from_savings_evaluator` | `cancel_transfer_from_savings_operation` |
| `claim_reward_balance_evaluator` | `claim_reward_balance_operation` |
| `delegate_vesting_shares_evaluator` | `delegate_vesting_shares_operation` |
| `recurrent_transfer_evaluator` | `recurrent_transfer_operation` |

#### Account Evaluators (hive_evaluator_account.cpp)
| Evaluator | Operation |
|-----------|-----------|
| `account_create_evaluator` | `account_create_operation` |
| `account_create_with_delegation_evaluator` | `account_create_with_delegation_operation` |
| `account_update_evaluator` | `account_update_operation` |
| `account_update2_evaluator` | `account_update2_operation` |
| `claim_account_evaluator` | `claim_account_operation` |
| `create_claimed_account_evaluator` | `create_claimed_account_operation` |
| `request_account_recovery_evaluator` | `request_account_recovery_operation` |
| `recover_account_evaluator` | `recover_account_operation` |
| `change_recovery_account_evaluator` | `change_recovery_account_operation` |
| `decline_voting_rights_evaluator` | `decline_voting_rights_operation` |
| `reset_account_evaluator` | `reset_account_operation` |
| `set_reset_account_evaluator` | `set_reset_account_operation` |

#### Witness Evaluators (hive_evaluator.cpp)
| Evaluator | Operation |
|-----------|-----------|
| `witness_update_evaluator` | `witness_update_operation` |
| `witness_set_properties_evaluator` | `witness_set_properties_operation` |
| `account_witness_proxy_evaluator` | `account_witness_proxy_operation` |
| `account_witness_vote_evaluator` | `account_witness_vote_operation` |
| `custom_evaluator` | `custom_operation` |
| `custom_json_evaluator` | `custom_json_operation` |
| `custom_binary_evaluator` | `custom_binary_operation` |
| `pow_evaluator` | `pow_operation` |
| `pow2_evaluator` | `pow2_operation` |
| `feed_publish_evaluator` | `feed_publish_operation` |
| `witness_block_approve_evaluator` | `witness_block_approve_operation` |

#### DHF (Proposal) Evaluators (dhf_evaluator.cpp)
| Evaluator | Operation |
|-----------|-----------|
| `create_proposal_evaluator` | `create_proposal_operation` |
| `update_proposal_evaluator` | `update_proposal_operation` |
| `update_proposal_votes_evaluator` | `update_proposal_votes_operation` |
| `remove_proposal_evaluator` | `remove_proposal_operation` |

### 1.4 Dispatch Flow

The full call chain from block application to evaluator execution:

```
database::apply_block(full_block, skip, block_ctrl)
  └─ database::_apply_block(full_block, block_ctrl)
       ├─ notify_pre_apply_block(note)
       ├─ FOR EACH transaction in block:
       │    └─ database::apply_transaction(trx, skip)
       │         └─ database::_apply_transaction(trx)
       │              ├─ validate_transaction(trx, skip)
       │              ├─ create<transaction_object>  (dupe check)
       │              ├─ notify_pre_apply_transaction(note)
       │              ├─ rc().reset_tx_info(trx)
       │              ├─ FOR EACH operation in transaction:
       │              │    └─ database_impl::apply_operation(op)
       │              │         ├─ notify_pre_apply_operation(note)
       │              │         ├─ rc().handle_operation_discount(op)  [HF20+]
       │              │         ├─ _evaluator_registry.get_evaluator(op).apply(op)
       │              │         │    └─ evaluator_impl::apply(op)
       │              │         │         └─ ConcreteEvaluator::do_apply(typed_op)
       │              │         └─ notify_post_apply_operation(note)
       │              ├─ rc().finalize_transaction(trx)
       │              └─ notify_post_apply_transaction(note)
       │
       ├─ [End-of-block processing — see Section 3]
       ├─ notify_post_apply_block(note)
       └─ migrate_irreversible_state(old_lib)
```

### 1.5 Signal/Plugin Integration

The `notify_*` calls fire boost signals that plugins subscribe to. Plugins connect
via `add_pre_apply_operation_handler()`, `add_post_apply_operation_handler()`, etc.
Each handler gets an `operation_notification` containing:
- The operation itself
- Block number, transaction-in-block index, operation-in-transaction index

Virtual operations follow the same signal path. They are pushed via:
- `push_virtual_operation(db, op)` — fires both pre and post notifications
- `pre_push_virtual_operation(db, op)` — fires only pre-notification (allows the
  callback to read state before modifications that will be described by the vop)
- `post_push_virtual_operation(db, op)` — fires only post-notification

### 1.6 Custom Operation Dispatch

`custom_json_operation` has a secondary dispatch mechanism. When `custom_json_evaluator`
runs, it looks up a `custom_operation_interpreter` by `id` field and delegates to it.
Plugins register interpreters via `database::register_custom_operation_interpreter()`.

---

## 2. Database Helper Methods

These are the methods evaluators call to mutate state. Organized by domain.

### 2.1 Balance Helpers (database.cpp)

#### `adjust_balance(const account_object& a, const asset& delta)`
- **Dispatches** to the HIVE or HBD overload based on `delta.symbol`.

#### `adjust_balance(const account_object& a, const HIVE_asset& delta)`
- **Modifies**: `account_object.balance` (liquid HIVE)
- **Checks**: Balance cannot go negative.
- **Virtual ops**: None.

#### `adjust_balance(const account_object& a, const HBD_asset& delta)`
- **Modifies**: `account_object.hbd_balance`, `account_object.hbd_seconds`,
  `account_object.hbd_seconds_last_update`, `account_object.hbd_last_interest_payment`
- **Side effect (pre-HF25)**: Calculates and pays accrued HBD interest on the account's
  liquid HBD balance. Interest is compounded at `HIVE_HBD_INTEREST_COMPOUND_INTERVAL_SEC`
  intervals.
- **Modifies (if interest paid)**: `dynamic_global_property_object.current_hbd_supply`,
  `dynamic_global_property_object.virtual_supply`
- **Virtual ops**: `interest_operation(account, interest_paid, true)` if interest > 0
  (the `true` flag indicates liquid balance, not savings).

#### `adjust_savings_balance(const account_object& a, const asset& delta)`
- **Dispatches** to the HIVE or HBD overload.

#### `adjust_savings_balance(const account_object& a, const HIVE_asset& delta)`
- **Modifies**: `account_object.savings_balance`
- **Checks**: Savings HIVE cannot go negative.
- **Virtual ops**: None.

#### `adjust_savings_balance(const account_object& a, const HBD_asset& delta)`
- **Modifies**: `account_object.savings_hbd_balance`, `account_object.savings_hbd_seconds`,
  `account_object.savings_hbd_seconds_last_update`, `account_object.savings_hbd_last_interest_payment`
- **Side effect**: Calculates and pays accrued HBD interest on the savings HBD balance
  (same compound interval as liquid HBD).
- **Modifies (if interest paid)**: `dynamic_global_property_object.current_hbd_supply`,
  `dynamic_global_property_object.virtual_supply`
- **Virtual ops**: `interest_operation(account, interest_paid, false)` if interest > 0
  (`false` flag = savings balance).

#### `adjust_reward_balance(const account_object& a, const asset& value_delta, const asset& share_delta)`
- **Dispatches** to typed overloads based on symbol. Routes to one of three:

#### `adjust_reward_balance(const account_object& a, const HIVE_asset& value_delta)`
- **Modifies**: `account_object.reward_hive_balance`
- **Checks**: Cannot go negative.

#### `adjust_reward_balance(const account_object& a, const HIVE_asset& value_delta, const VEST_asset& share_delta)`
- **Modifies**: `account_object.reward_vesting_hive`, `account_object.reward_vesting_balance`
- **Checks**: reward VESTS cannot go negative.

#### `adjust_reward_balance(const account_object& a, const HBD_asset& value_delta)`
- **Modifies**: `account_object.reward_hbd_balance`
- **Checks**: Cannot go negative.

#### `adjust_supply(const asset& delta, bool adjust_vesting = false)`
- **Dispatches** to HIVE or HBD overload.

#### `adjust_supply(const HIVE_asset& delta, bool adjust_vesting = false)`
- **Modifies**: `dynamic_global_property_object.current_supply`, `.virtual_supply`,
  `.total_vesting_fund_hive`
- **Special**: If `adjust_vesting` is true AND `delta > 0` AND block > 7 days,
  adds `delta * 9` as new vesting (early inflation mechanism, pre-HF16).
- **Checks**: `current_supply` cannot go negative.

#### `adjust_supply(const HBD_asset& delta)`
- **Modifies**: `dynamic_global_property_object.current_hbd_supply`, `.virtual_supply`
- **Recalculates**: `virtual_supply = hbd_supply * median_price + current_supply`
- **Checks**: `current_hbd_supply` cannot go negative.

#### `get_balance(const account_object& a, asset_symbol_type symbol) const`
- **Read-only**: Returns liquid HIVE or HBD balance.

#### `get_savings_balance(const account_object& a, asset_symbol_type symbol) const`
- **Read-only**: Returns savings HIVE or HBD balance.

### 2.2 Vesting Helpers (database.cpp + database_vesting_helpers.hpp)

#### `create_vesting(const account_object& to, const HIVE_asset& liquid, bool to_reward_balance = false)`
- **Convenience wrapper**: Calls `create_vesting2()` with an empty callback.

#### `create_vesting2(database& db, const account_object& to, const HIVE_asset& liquid, bool to_reward_balance, Before&& callback)`
- **Template function** (in `database_vesting_helpers.hpp`).
- Calls `adjust_account_vesting_balance()` which:
  1. Calculates new VESTS: `liquid * vesting_share_price` (reward or regular price)
  2. Invokes `callback(new_vesting)` (used for pre-notification of virtual ops)
  3. If `to_reward_balance`: calls `adjust_reward_balance(to, liquid, new_vesting)`
  4. If regular balance:
     - Updates manabar (`util::update_manabar`) [HF20+]
     - Regenerates RC mana [HF20+]
     - `account_object.vesting_shares += new_vesting`
     - Updates RC after vest change [HF20+]
  5. Updates `dynamic_global_property_object`:
     - Reward: `pending_rewarded_vesting_shares += new_vesting`, `pending_rewarded_vesting_hive += liquid`
     - Regular: `total_vesting_fund_hive += liquid`, `total_vesting_shares += new_vesting`
- If not reward balance: calls `adjust_proxied_witness_votes(to, new_vesting.amount)`
- **Returns**: `VEST_asset` — the amount of new vesting shares created.

#### `calculate_vesting(database& db, const HIVE_asset& liquid, bool to_reward_balance)`
- **Pure calculation** (inline in header): `liquid * price` using reward or regular vesting share price.

### 2.3 HBD Creation Helper (database.cpp)

#### `create_hbd(const account_object& to, const HIVE_asset& hive, bool to_reward_balance = false)`
- **Purpose**: Converts HIVE into HBD at the current median price, respecting the
  `hbd_print_rate` (which throttles HBD creation when HBD is near its market cap limit).
- **Logic**:
  1. `to_hbd = (hbd_print_rate * hive) / 100%` — portion that becomes HBD
  2. `to_hive = hive - to_hbd` — remainder stays as HIVE
  3. `hbd = to_hbd * median_price` — actual HBD amount
  4. Credits both `hbd` and `to_hive` to the account (via `adjust_balance` or `adjust_reward_balance`)
  5. `adjust_supply(-to_hbd)` — removes the converted HIVE from supply
  6. `adjust_supply(hbd)` — adds the new HBD to supply
- **Returns**: `pair<HBD_asset, HIVE_asset>` — (HBD paid, HIVE paid)
- **Fallback**: If median price is null, credits all as HIVE.

### 2.4 Witness Vote Helpers (database.cpp)

#### `adjust_proxied_witness_votes(const account_object& a, const array<share_type, DEPTH+1>& delta, int depth = 0)`
- **Purpose**: Propagates vote weight changes through the proxy chain.
- If account has proxy: propagates delta to proxy's `proxied_vsf_votes[]`, recurses.
- If no proxy (leaf): calls `adjust_witness_votes(a, total_delta)`.
- **Modifies**: `account_object.proxied_vsf_votes[]` on each proxy in the chain.

#### `adjust_proxied_witness_votes(const account_object& a, share_type delta, int depth = 0)`
- **Simplified overload**: Same logic but for a single delta value at the given depth.

#### `nullify_proxied_witness_votes(const account_object& a)`
- **Purpose**: Removes all of account `a`'s vote influence from the proxy chain.
- Constructs a delta array with negated values of `a`'s direct vote power and all
  `proxied_vsf_votes[i]`, then calls the array overload.

### 2.5 Account Management Helpers (database.cpp + hive_evaluator_account.cpp)

#### `create_account(database& db, name, key, creation_time, block_time, mined, fee_for_rc, recovery_account, initial_delegation)` (free function)
- **Purpose**: Creates a new account with proper recovery account handling.
- Pre-HF11: forces recovery account to "steem".
- HF20+: calculates RC adjustment from creation fee.
- **Creates**: `account_object` via `db.create<account_object>(...)`.
- **Asserts**: Account does not already exist.

#### `update_owner_authority(const account_object& account, const authority& owner_authority)`
- **Creates**: `owner_authority_history_object` (if block >= tracking start).
- **Modifies**: `account_authority_object.owner`, `.previous_owner_update`, `.last_owner_update`.

#### `lock_account(const account_object& account)`
- **Purpose**: Locks an account by clearing all authority keys and setting thresholds.
- **Modifies**: `account_authority_object` — clears owner/active/posting keys, sets thresholds to 1.
- **Modifies**: `account_object` — sets recovery account to self, clears memo key.
- **Removes**: Any `account_recovery_request_object` and `change_recovery_account_request_object`.

#### `clear_account(const account_object& account)`
- **Purpose**: HF23 "redistribution" — moves all of an account's balances to treasury.
- **Modifies**: The target `account_object` (zeroes all balances), the treasury `account_object`
  (receives balances), `dynamic_global_property_object` (adjusts vesting totals).
- **Virtual ops**: `hardfork_hive_operation`.

#### `restore_accounts(const set<string>& restored_accounts)`
- **Purpose**: HF23 balance restoration — returns previously cleared balances from treasury.
- **Modifies**: Treasury and restored account balances.
- **Virtual ops**: `hardfork_hive_restore_operation`.

### 2.6 Comment/Reward Helpers (database_comment.cpp)

#### `find_comment(comment_id_type id) const`
- **Read-only**: Returns `comment_object*` or nullptr.

#### `find_comment_cashout(comment_id_type id) const`
- **Read-only**: Returns `comment_cashout_object*` or nullptr.

#### `find_comment_cashout_ex(comment_id_type id) const`
- **Read-only**: Returns `comment_cashout_ex_object*` (pre-HF19 only).

#### `pay_curators(const comment_object& comment, const comment_cashout_object& cashout, HIVE_asset& max_rewards)`
- **Purpose**: Distributes curation rewards to voters proportional to their vote weight.
- **For each voter** with positive weight:
  - Calculates claim: `(max_rewards * weight) / total_weight`
  - Calls `create_vesting2()` to convert HIVE claim to VESTS for the voter.
  - **Modifies**: Voter's `account_object.curation_rewards += claim`
  - **Virtual ops**: `curation_reward_operation` for each curator.
- **Returns**: Unclaimed rewards (rounding dust).

#### `cashout_comment_helper(ctx, comment, cashout, cashout_ex, forward_curation_remainder)`
- **Purpose**: Master comment payout function. Orchestrates the full payout.
- **Calls**: `pay_curators()`, `create_vesting2()`, `create_hbd()`.
- **Processes beneficiaries**: For each beneficiary, splits their share into HBD/VESTS.
  Special handling for treasury beneficiary (converts to HBD directly).
- **Modifies**: Author's `account_object.posting_rewards`.
- **Virtual ops**: `author_reward_operation`, `comment_benefactor_reward_operation`,
  `comment_reward_operation`, `comment_payout_update_operation`.
- Post-HF19: Removes the `comment_cashout_object` after payout.
- Removes all `comment_vote_object` entries for the comment.

#### `process_comment_cashout()`
- **Called by**: `_apply_block()` end-of-block processing.
- **Purpose**: Processes all comments whose cashout time has arrived.
- Decays `recent_claims` on each `reward_fund_object`.
- Pre-calculates total rshares being cashed out (HF17+).
- For each eligible comment: calls `cashout_comment_helper()`.
- Updates `reward_fund_object.reward_balance` and `.recent_claims`.

#### `perform_vesting_share_split(uint32_t magnitude)`
- **Purpose**: Historical vesting share split (hardfork operation).
- **Modifies**: Every `account_object` (multiplies vesting shares, withdrawn, to_withdraw, etc.),
  every `comment_cashout_object` (multiplies rshares), `dynamic_global_property_object`.
- **Virtual ops**: `vesting_shares_split_operation` for each account with changed vests.

### 2.7 Market/DEX Helpers (database_market.cpp)

#### `get_escrow(name, escrow_id) const` / `find_escrow(name, escrow_id) const`
- **Read-only**: Lookups for `escrow_object`.

#### `expire_escrow_ratification()`
- **Called by**: `_apply_block()` end-of-block processing.
- **Purpose**: Returns funds from unapproved escrows past their deadline.
- **Modifies**: Restores HIVE, HBD, and fee to `escrow.from` via `adjust_balance()`.
  Decrements `account_object.pending_escrow_transfers`. Removes `escrow_object`.
- **Virtual ops**: `escrow_rejected_operation`.

#### `remove_pending_escrows(const account_object& account, name)`
- **Purpose**: Used during HF23 account clearing — returns all escrow balances.
- Same pattern as `expire_escrow_ratification()` but for a specific account.

#### `find_savings_withdraw(owner, request_id) const` / `get_savings_withdraw(owner, request_id) const`
- **Read-only**: Lookups for `savings_withdraw_object`.

#### `process_savings_withdraws()`
- **Called by**: `_apply_block()` end-of-block processing.
- **Purpose**: Completes savings withdrawals whose completion time has arrived.
- **Modifies**: Credits `to` account via `adjust_balance()`. Decrements `from`
  account's `savings_withdraw_requests`. Removes `savings_withdraw_object`.
- **Virtual ops**: `fill_transfer_from_savings_operation`.

#### `remove_pending_savings_withdraws(const account_object& account, name)`
- **Purpose**: HF23 account clearing — returns all pending savings withdrawals.

#### `find_limit_order(name, orderid) const` / `get_limit_order(name, orderid) const`
- **Read-only**: Lookups for `limit_order_object`. Pre-HF6 masks orderid to 16 bits.

#### `apply_order(const limit_order_object& new_order)`
- **Purpose**: Attempts to match a new limit order against existing orders on the book.
- Iterates the `by_price` index, calling `match()` for each compatible order.
- **Returns**: `true` if the new order was fully filled (i.e., removed).

#### `match(const limit_order_object& new_order, const limit_order_object& old_order, const price& match_price)`
- **Purpose**: Executes a trade between two matching orders.
- Calculates fill amounts based on the match price.
- Pre-HF12: calls `adjust_liquidity_reward()` for liquidity mining.
- **Virtual ops**: `fill_order_operation`.
- Calls `fill_order()` for both sides.
- **Returns**: Bitmask (bit 0 = new order filled, bit 1 = old order filled).

#### `fill_order(const limit_order_object& order, const asset& pays, const asset& receives)`
- **Modifies**: Credits `receives` to `order.seller` via `adjust_balance()`.
- If fully filled: removes the `limit_order_object`.
- If partially filled: reduces `for_sale`. If remaining `amount_to_receive` is zero
  (rounding to dust), calls `cancel_order()`.

#### `cancel_order(const limit_order_object& order, bool suppress_vop = false)`
- **Modifies**: Returns `amount_for_sale` to seller via `adjust_balance()`.
  Removes the `limit_order_object`.
- **Virtual ops**: `limit_order_cancelled_operation` (unless suppressed).

#### `clear_expired_orders()`
- **Called by**: `_apply_block()` end-of-block processing.
- Iterates orders past their expiration, calls `cancel_order()` for each.

### 2.8 Vesting Withdrawal Helpers (database_vesting.cpp)

#### `pay_liquidity_reward()`
- **Called by**: `_apply_block()` every `HIVE_LIQUIDITY_REWARD_BLOCKS` blocks.
- **Purpose**: Pays liquidity reward to the top volume-weighted market maker.
- **Modifies**: Adjusts supply (`adjust_supply(reward, true)`), credits reward to
  winner via `adjust_balance()`, resets winner's `liquidity_reward_balance_object`.
- **Virtual ops**: `liquidity_reward_operation`.

#### `adjust_liquidity_reward(const account_object& owner, const asset& volume, bool is_hbd)`
- **Purpose**: Updates liquidity tracking for market participants.
- **Modifies**: `liquidity_reward_balance_object` — updates `hbd_volume` or `hive_volume`,
  recalculates weight, resets if timed out.

#### `process_vesting_withdrawals()`
- **Called by**: `_apply_block()` end-of-block processing.
- **Purpose**: Processes weekly power-down installments.
- For each account past its `next_vesting_withdrawal` time:
  1. Calculates withdrawal amount (min of weekly rate and remaining).
  2. Processes withdraw routes: for each route, either deposits VESTS (auto-vest)
     or converts to HIVE (non-auto-vest).
  3. Remainder goes to the withdrawing account as HIVE.
  4. Updates `account_object`: decreases `vesting_shares`, increases `balance`,
     updates `withdrawn`, resets schedule if complete.
  5. Updates `dynamic_global_property_object`: decreases `total_vesting_fund_hive`
     and `total_vesting_shares` for HIVE conversions.
  6. Handles delayed voting (HF24+) or adjusts proxied witness votes.
- **Virtual ops**: `fill_vesting_withdraw_operation` for each route and the remainder.

### 2.9 Conversion Helpers (database_conversion.cpp)

#### `process_conversions()`
- **Called by**: `_apply_block()` end-of-block processing.
- **Purpose**: Processes matured conversion requests (both regular and collateralized).
- **Regular conversions** (HBD -> HIVE):
  - `amount_to_issue = hbd_amount * current_median_history`
  - Credits HIVE to owner via `adjust_balance()`.
  - Removes `convert_request_object`.
  - **Virtual ops**: `fill_convert_request_operation`.
- **Collateralized conversions** (HIVE collateral -> HBD already issued):
  - Calculates required HIVE at market median price + fee.
  - Returns excess collateral to owner via `adjust_balance()`.
  - If collateral insufficient: emits `system_warning_operation`, uses all collateral.
  - Removes `collateralized_convert_request_object`.
  - **Virtual ops**: `fill_collateralized_convert_request_operation`.
- **Corrects global supply**: Adjusts `current_supply` and `current_hbd_supply` for
  net changes.

#### `remove_pending_conversion_requests(const account_object& account)`
- **Purpose**: HF23 cleanup — returns pending conversion balances.
- Regular: returns HBD via `adjust_balance()`.
- Collateralized: asserts none exist (not handled by clear_account).

### 2.10 Delegation Helpers (database_delegation.cpp + database.cpp)

The `database_delegation.cpp` file only contains index initialization for
`reward_fund_index`, `vesting_delegation_index`, and `vesting_delegation_expiration_index`.

#### `clear_expired_delegations()` (in database.cpp)
- **Called by**: `_apply_block()` end-of-block processing.
- **Purpose**: Returns vesting from expired delegation expirations.
- For each expired `vesting_delegation_expiration_object`:
  - Updates manabar and regenerates RC [HF20+].
  - Decreases delegator's `delegated_vesting_shares`.
  - Updates RC after vest change [HF20+].
  - Removes the expiration object.
- **Virtual ops**: `return_vesting_delegation_operation`.

### 2.11 Recurrent Transfer Helpers (database_dhf.cpp)

#### `process_recurrent_transfers()`
- **Called by**: `_apply_block()` end-of-block processing. HF25+ only.
- **Purpose**: Executes scheduled recurrent transfers.
- Per-block limit: `HIVE_MAX_RECURRENT_TRANSFERS_PER_BLOCK`.
- **If sufficient balance**: Transfers via `adjust_balance()` on both accounts.
  Updates next trigger date, decrements remaining executions.
  **Virtual ops**: `fill_recurrent_transfer_operation`.
- **If insufficient balance**: Increments `consecutive_failures`. After
  `HIVE_MAX_CONSECUTIVE_RECURRENT_TRANSFER_FAILURES`, removes the transfer.
  **Virtual ops**: `failed_recurrent_transfer_operation`.
- On completion (remaining_executions == 0 or max failures): removes
  `recurrent_transfer_object`, decrements `account_object.open_recurrent_transfers`.

### 2.12 Governance Helpers (database_dhf.cpp + database.cpp)

#### `process_decline_voting_rights()`
- **Called by**: `_apply_block()` end-of-block processing.
- **Purpose**: Processes accounts that requested to decline voting rights.
- For each matured `decline_voting_rights_request_object`:
  - Removes DHF proposal votes [HF28+: with threshold guard].
  - Calls `nullify_proxied_witness_votes()` and `clear_witness_votes()`.
  - Sets `account_object.can_vote = false`, clears proxy.
  - Removes the request object.
- **Virtual ops**: `proxy_cleared_operation` (if had proxy), `declined_voting_rights_operation`.

#### `remove_expired_governance_votes()` (in database.cpp)
- **Called by**: `_apply_block()` end-of-block processing.
- **Purpose**: Removes witness and proposal votes that have expired based on governance
  vote expiration time.

### 2.13 Other End-of-Block Processing Methods

#### `clear_null_account_balance()`
- **Purpose**: Burns any funds sent to `@null` by zeroing its balances and reducing global supply.
- **Modifies**: `account_object` (null account — zeroes all balances), `dynamic_global_property_object`
  (reduces supply).
- **Virtual ops**: `clear_null_account_balance_operation`.

#### `consolidate_treasury_balance()`
- **Purpose**: HF24+ — merges old treasury (`steem.dao`) into new treasury (`hive.fund`).

#### `process_funds()`
- **Purpose**: Per-block inflation distribution.
- Calculates: `new_hive = virtual_supply * inflation_rate / (100% * blocks_per_year)`
- Splits into: `content_reward`, `vesting_reward`, `dhf_new_funds`, `witness_reward`.
- Witness reward scaled by schedule type (elected/timeshare/miner) and weight.
- DHF funds: converted to HBD via `create_hbd`-like logic, credited to treasury.
- Witness reward: converted to VESTS via `create_vesting2()`.
- **Modifies**: `dynamic_global_property_object` (supply, vesting, reward fund, dhf ledger).
- **Virtual ops**: `producer_reward_operation`.

#### `process_subsidized_accounts()`
- **Purpose**: Updates the global subsidized account creation pool using resource dynamics.
- **Modifies**: `dynamic_global_property_object.available_account_subsidies`.

#### `account_recovery_processing()`
- **Purpose**: Clears expired account recovery requests.

#### `update_median_feed()`
- **Called every**: `HIVE_FEED_INTERVAL_BLOCKS` blocks.
- **Purpose**: Calculates median price feed from witness-published feeds.
- **Modifies**: `feed_history_object` — updates `price_history` deque,
  `current_median_history`, `market_median_history`, `current_min_history`, `current_max_history`.
- Applies HBD hard cap correction if HBD exceeds configured limit.
- **Virtual ops**: `system_warning_operation` if price was corrected.

#### `update_virtual_supply()`
- **Purpose**: Recalculates `virtual_supply` and `hbd_print_rate`.
- `virtual_supply = current_supply + current_hbd_supply * median_price`
- `hbd_print_rate` scales between 0% and 100% based on HBD percentage of market cap
  relative to `hbd_start_percent` and `hbd_stop_percent`.
- **Modifies**: `dynamic_global_property_object.virtual_supply`, `.hbd_print_rate`.

---

## 3. End-of-Block Processing Order

After all transactions in a block are applied, `_apply_block()` executes these
in strict order:

```
update_global_dynamic_data(block)         // head_block_number, time, etc.
update_signing_witness(signing_witness)   // witness stats
update_last_irreversible_block()          // LIB calculation
create_block_summary(block)               // block summary for TaPoS
clear_expired_transactions()              // transaction dedup cleanup
clear_expired_orders()                    // limit order expiry
clear_expired_delegations()               // vesting delegation returns

update_witness_schedule()                 // witness scheduling
update_median_feed()                      // price feed
update_virtual_supply()                   // recalculate virtual supply

clear_null_account_balance()              // burn @null funds
consolidate_treasury_balance()            // merge old/new treasury
process_funds()                           // inflation distribution
process_conversions()                     // HBD<->HIVE conversions
process_comment_cashout()                 // author/curator rewards
process_vesting_withdrawals()             // power-down installments
process_savings_withdraws()               // savings withdrawal completion
process_subsidized_accounts()             // account subsidy pool
pay_liquidity_reward()                    // market maker rewards
update_virtual_supply()                   // re-update after changes

account_recovery_processing()             // expired recovery requests
expire_escrow_ratification()              // unapproved escrow cleanup
process_decline_voting_rights()           // voting rights declination
process_proposals(note)                   // DHF proposal payouts
process_delayed_voting(note)              // delayed vote processing
remove_expired_governance_votes()         // expired governance votes

process_recurrent_transfers()             // scheduled recurring transfers

rc().handle_expired_delegations()         // RC delegation cleanup
rc().finalize_block()                     // RC finalization

process_hardforks()                       // hardfork activation
```

---

## 4. Summary of Virtual Operations Generated by Helpers

| Helper Method | Virtual Operation |
|---------------|-------------------|
| `adjust_balance` (HBD overload, pre-HF25) | `interest_operation` |
| `adjust_savings_balance` (HBD overload) | `interest_operation` |
| `pay_curators` | `curation_reward_operation` |
| `cashout_comment_helper` | `author_reward_operation`, `comment_benefactor_reward_operation`, `comment_reward_operation`, `comment_payout_update_operation` |
| `process_vesting_withdrawals` | `fill_vesting_withdraw_operation` |
| `process_conversions` (regular) | `fill_convert_request_operation` |
| `process_conversions` (collateralized) | `fill_collateralized_convert_request_operation`, `system_warning_operation` |
| `clear_expired_delegations` | `return_vesting_delegation_operation` |
| `expire_escrow_ratification` | `escrow_rejected_operation` |
| `process_savings_withdraws` | `fill_transfer_from_savings_operation` |
| `cancel_order` | `limit_order_cancelled_operation` |
| `match` (order matching) | `fill_order_operation` |
| `pay_liquidity_reward` | `liquidity_reward_operation` |
| `process_funds` | `producer_reward_operation`, `system_warning_operation` |
| `clear_null_account_balance` | `clear_null_account_balance_operation` |
| `restore_accounts` | `hardfork_hive_restore_operation` |
| `clear_account` | `hardfork_hive_operation` |
| `process_recurrent_transfers` | `fill_recurrent_transfer_operation`, `failed_recurrent_transfer_operation` |
| `process_decline_voting_rights` | `proxy_cleared_operation`, `declined_voting_rights_operation` |
| `update_median_feed` | `system_warning_operation` (price correction) |
| `perform_vesting_share_split` | `vesting_shares_split_operation` |

---

## 5. Per-Evaluator Reference

All 50 registered evaluators, organized by source file. For each: state objects
read/modified/created/removed, chain-state assertions, virtual operations generated,
hardfork-conditional behavior, and key business logic.

### 5.1 Transfer Evaluators (hive_evaluator_transfer.cpp)

---

#### transfer_evaluator
- **Source**: `hive_evaluator_transfer.cpp:260-290`
- **Reads**: `feed_history` (HIVE-to-treasury path), `is_treasury(o.to)`
- **Modifies**: sender balance (`adjust_balance -amount`), recipient balance (`adjust_balance +amount`)
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: `dhf_conversion_operation` (when HIVE sent to treasury, HF24+)
- **Chain-State Checks**:
  - HF21-HF24: only HBD can be sent to treasury
  - HF24+: HIVE to treasury requires non-null price feed
- **Business Logic**: Three paths: (1) HF24+ HIVE to treasury: converts HIVE to HBD at median price, burns HIVE supply, credits HBD to treasury. (2) HF21+ to treasury: HBD only. (3) Normal: simple balance transfer.
- **Hardfork Notes**: HF21 (treasury restrictions), HF24 (HIVE-to-treasury auto-conversion)

---

#### transfer_to_vesting_evaluator
- **Source**: `hive_evaluator_transfer.cpp:292-325`
- **Reads**: `from` account, `to` account, `is_treasury(o.to)`
- **Modifies**: sender HIVE balance (deducted), recipient VESTS (increased), `dynamic_global_property_object` (vesting totals). HF24+: creates delayed voting record (30-day governance delay).
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: `transfer_to_vesting_completed_operation` (always)
- **Chain-State Checks**: Cannot vest to treasury (HF21+)
- **Business Logic**: Converts HIVE to VESTS (Hive Power). Post-HF24, governance power is delayed 30 days to prevent takeover attacks.
- **Hardfork Notes**: HF21 (treasury restriction), HF24 (delayed voting)

---

#### withdraw_vesting_evaluator
- **Source**: `hive_evaluator_transfer.cpp:327-389`
- **Reads**: account object
- **Modifies**: `account_object` (vesting_withdraw_rate, next_vesting_withdrawal, to_withdraw, withdrawn). RC mana regenerated (HF20+).
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**:
  - Negative VESTS withdrawal blocked (HF20+ hard assert; pre-HF20 silent return — historical exploit at block 23847548)
  - Sufficient vesting (net of delegations)
  - HF28: prevents no-op cancellation and redundant power-down set
- **Business Logic**: `amount == 0` cancels active power-down. `amount > 0` sets weekly withdrawal rate = `amount / intervals`. Pre-HF16: 104 intervals. Post-HF16: 13 intervals. HF21: fixes rounding by incrementing rate if `rate * intervals < total`.
- **Hardfork Notes**: HF16 (interval change 104→13), HF20 (negative VESTS rejection, RC), HF21 (rounding fix), HF28 (no-op prevention)

---

#### set_withdraw_vesting_route_evaluator
- **Source**: `hive_evaluator_transfer.cpp:391-455`
- **Reads**: from/to accounts, existing route
- **Modifies**: `withdraw_vesting_route_object` (create/modify/remove), `account_object.withdraw_routes` counter
- **Creates**: `withdraw_vesting_route_object` (new route with percent > 0)
- **Removes**: `withdraw_vesting_route_object` (when percent == 0)
- **Virtual Ops**: —
- **Chain-State Checks**:
  - Cannot route to treasury (HF21+)
  - Max `HIVE_MAX_WITHDRAW_ROUTES` per account
  - Total percent across all routes ≤ 100%
- **Business Logic**: Three cases: create (percent > 0, no existing), delete (percent == 0, existing), update (percent > 0, existing).
- **Hardfork Notes**: HF21 (treasury restriction)

---

#### convert_evaluator
- **Source**: `hive_evaluator_transfer.cpp:457-471`
- **Reads**: account, `feed_history`
- **Modifies**: account HBD balance (deducted immediately)
- **Creates**: `convert_request_object` (time-delayed)
- **Removes**: —
- **Virtual Ops**: — (actual conversion emits `fill_convert_request_operation` later)
- **Chain-State Checks**: Requires non-null price feed
- **Business Logic**: HBD→HIVE. Deducts HBD now, creates delayed request. HIVE paid out after `HIVE_CONVERSION_DELAY` (3.5 days post-HF16) at median price at completion time.
- **Hardfork Notes**: HF16 (delay change)

---

#### collateralized_convert_evaluator
- **Source**: `hive_evaluator_transfer.cpp:473-520`
- **Reads**: account, `feed_history` (median + min), `dynamic_global_property_object` (hbd_print_rate, hbd_stop_percent)
- **Modifies**: account HIVE balance (deducted), account HBD balance (credited immediately), `dynamic_global_property_object` (current_hbd_supply, virtual_supply)
- **Creates**: `collateralized_convert_request_object`
- **Removes**: —
- **Virtual Ops**: `collateralized_convert_immediate_conversion_operation` (always)
- **Chain-State Checks**:
  - HF25+ only
  - Non-null price feed
  - `hbd_print_rate > 0` (HBD creation not blocked)
  - Converted amount > 0
  - New HBD doesn't violate global `hbd_stop_percent` cap
- **Business Logic**: HIVE→HBD with 2x overcollateralization. Immediate HBD payout at `current_min_history` price minus fee. Excess collateral returned after `HIVE_COLLATERALIZED_CONVERSION_DELAY` at median price.
- **Hardfork Notes**: HF25 (introduced)

---

#### limit_order_create_evaluator
- **Source**: `hive_evaluator_transfer.cpp:522-547`
- **Reads**: `head_block_time()`, `head_block_id()` (pre-HF20)
- **Modifies**: seller balance (deducted), potentially other orders and balances via `apply_order()`
- **Creates**: `limit_order_object`
- **Removes**: — (but `apply_order()` may remove matched orders)
- **Virtual Ops**: — (but `apply_order()` → `match()` emits `fill_order_operation`)
- **Chain-State Checks**:
  - Expiration must be in future
  - HF20+: max 28-day expiration
  - Fill-or-kill: must be fully filled or transaction reverts
- **Business Logic**: Creates DEX limit order. Deducts sell amount, calls `apply_order()` to match against book. Pre-HF20: expiration clamped with pseudorandom offset from `head_block_id`.
- **Hardfork Notes**: HF20 (28-day max expiration)

---

#### limit_order_create2_evaluator
- **Source**: `hive_evaluator_transfer.cpp:549-571`
- **Reads**: `head_block_time()`
- **Modifies**: Same as limit_order_create
- **Creates**: `limit_order_object`
- **Removes**: — (via `apply_order()`)
- **Virtual Ops**: — (via `apply_order()`)
- **Chain-State Checks**: Same as limit_order_create
- **Business Logic**: Same as `limit_order_create` but takes explicit `exchange_rate` instead of deriving from `min_to_receive / amount_to_sell`.
- **Hardfork Notes**: HF20 (28-day max expiration)

---

#### limit_order_cancel_evaluator
- **Source**: `hive_evaluator_transfer.cpp:573-576`
- **Reads**: `limit_order_object` by owner+orderid
- **Modifies**: seller balance (returned via `cancel_order()`)
- **Creates**: —
- **Removes**: `limit_order_object`
- **Virtual Ops**: `limit_order_cancelled_operation` (via `cancel_order()`)
- **Chain-State Checks**: Order must exist (implicit from `get_limit_order`)
- **Business Logic**: Delegates to `db.cancel_order()`.

---

#### escrow_transfer_evaluator
- **Source**: `hive_evaluator_transfer.cpp:75-106`
- **Reads**: from/to/agent accounts
- **Modifies**: sender balance (HIVE + HBD deducted including fee), `account_object.pending_escrow_transfers++`
- **Creates**: `escrow_object`
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**:
  - Ratification deadline and escrow expiration must be in future
  - `pending_escrow_transfers < HIVE_MAX_PENDING_TRANSFERS`
- **Business Logic**: Creates escrow holding HIVE/HBD + fee. Requires ratification by `to` and `agent` before deadline.

---

#### escrow_approve_evaluator
- **Source**: `hive_evaluator_transfer.cpp:108-175`
- **Reads**: `escrow_object`, from account (on rejection)
- **Modifies**: `escrow_object` (to_approved/agent_approved flags, pending_fee). On rejection: restores all funds to sender. On full approval: pays fee to agent.
- **Creates**: —
- **Removes**: `escrow_object` (on rejection)
- **Virtual Ops**: `escrow_rejected_operation` (on rejection), `escrow_approved_operation` (when both approve)
- **Chain-State Checks**:
  - to/agent must match escrow
  - Ratification deadline not passed
  - Cannot approve if already approved
- **Business Logic**: Approve or reject. Rejection returns all funds. Full approval (both to and agent) pays fee to agent.

---

#### escrow_dispute_evaluator
- **Source**: `hive_evaluator_transfer.cpp:177-196`
- **Reads**: from account, `escrow_object`
- **Modifies**: `escrow_object` (disputed = true)
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**: Not expired, fully approved, not already disputed, to/agent match
- **Business Logic**: Marks escrow as disputed. Once disputed, only agent can release funds.

---

#### escrow_release_evaluator
- **Source**: `hive_evaluator_transfer.cpp:198-258`
- **Reads**: from account, `escrow_object`
- **Modifies**: receiver balance (credited), `escrow_object` (balances reduced). If emptied: `pending_escrow_transfers--`
- **Creates**: —
- **Removes**: `escrow_object` (when both balances reach zero)
- **Virtual Ops**: —
- **Chain-State Checks**:
  - Sufficient escrow balance
  - Receiver must be `from` or `to`
  - Fully approved
  - Disputed: only agent can release
  - Not disputed, not expired: `from` can only release to `to` and vice versa
  - Expired: either party can release to either
- **Business Logic**: Complex permission model based on dispute/expiration state.

---

#### transfer_to_savings_evaluator
- **Source**: `hive_evaluator_transfer.cpp:578-587`
- **Reads**: from/to accounts, `is_treasury(to)`
- **Modifies**: sender liquid balance (deducted), recipient savings balance (credited)
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**: Cannot transfer to treasury savings
- **Business Logic**: Moves liquid HIVE/HBD to savings.

---

#### transfer_from_savings_evaluator
- **Source**: `hive_evaluator_transfer.cpp:589-606`
- **Reads**: from/to accounts, savings balance, `is_treasury(to)`
- **Modifies**: savings balance (deducted), `account_object.savings_withdraw_requests++`
- **Creates**: `savings_withdraw_object` (3-day delay)
- **Removes**: —
- **Virtual Ops**: — (completion emits `fill_transfer_from_savings_operation` later)
- **Chain-State Checks**:
  - `savings_withdraw_requests < HIVE_SAVINGS_WITHDRAW_REQUEST_LIMIT`
  - Only HBD can be withdrawn to treasury
  - Sufficient savings balance
- **Business Logic**: Time-delayed savings withdrawal (3 days). Deducts immediately, creates pending object.

---

#### cancel_transfer_from_savings_evaluator
- **Source**: `hive_evaluator_transfer.cpp:608-619`
- **Reads**: `savings_withdraw_object`, from account
- **Modifies**: savings balance (restored), `account_object.savings_withdraw_requests--`
- **Creates**: —
- **Removes**: `savings_withdraw_object`
- **Virtual Ops**: —
- **Chain-State Checks**: Pending withdrawal must exist (implicit from get)
- **Business Logic**: Returns funds to savings and removes pending withdrawal.

---

#### claim_reward_balance_evaluator
- **Source**: `hive_evaluator_transfer.cpp:621-675`
- **Reads**: account, `dynamic_global_property_object`
- **Modifies**: account reward balances (deducted), account liquid/vesting balances (credited), `dynamic_global_property_object` (moves VESTS from pending-reward to active pool), governance vote weight (via `adjust_proxied_witness_votes`)
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**: Cannot claim more than earned (HIVE, HBD, VESTS each checked)
- **Business Logic**: Moves earned rewards from reward balances to active balances. VESTS become active Hive Power. Updates global vesting totals and governance vote weight.
- **Hardfork Notes**: HF20 (manabar update, RC update on VESTS claim)

---

#### delegate_vesting_shares_evaluator
- **Source**: `hive_evaluator_transfer.cpp:677-903`
- **Reads**: delegator/delegatee accounts, existing `vesting_delegation_object`, `dynamic_global_property_object`, `witness_schedule_object`
- **Modifies**: delegator (delegated_vesting_shares, voting/downvote manabars), delegatee (received_vesting_shares, voting/downvote manabars), RC mana (HF20+)
- **Creates**: `vesting_delegation_object` (new delegation), `vesting_delegation_expiration_object` (on decrease — delayed return)
- **Removes**: `vesting_delegation_object` (when decreasing to zero)
- **Virtual Ops**: —
- **Chain-State Checks**:
  - Sufficient available shares (mana-based check, HF20+)
  - Sufficient available downvote shares (HF21+)
  - Minimum delegation threshold (derived from account_creation_fee * vesting price)
  - Minimum update threshold (prevent dust changes)
  - Cannot remove a delegation that is already zero
- **Business Logic**: Three cases: new delegation, increase (delta applied), decrease (creates expiration object for delayed return, max of `delegation_return_period` and `min_delegation_time`). Available shares = current mana - received shares - active power-down. Post-HF20: 30x reduction in min thresholds.
- **Hardfork Notes**: HF20 (mana-based, 30x threshold reduction, RC), HF21 (downvote manabar tracking), HF22 (uint128 overflow fix)

---

#### recurrent_transfer_evaluator
- **Source**: `hive_evaluator_transfer.cpp:906-957`
- **Reads**: from/to accounts, balance, existing `recurrent_transfer_object`
- **Modifies**: `account_object.open_recurrent_transfers` (increment/decrement)
- **Creates**: `recurrent_transfer_object` (new)
- **Removes**: `recurrent_transfer_object` (when amount == 0)
- **Virtual Ops**: — (periodic execution emits `fill_recurrent_transfer_operation` / `failed_recurrent_transfer_operation` later)
- **Chain-State Checks**:
  - HF25+ only
  - Sufficient balance for first execution
  - `open_recurrent_transfers < HIVE_MAX_OPEN_RECURRENT_TRANSFERS`
  - Total duration ≤ `HIVE_MAX_RECURRENT_TRANSFER_END_DATE` days
- **Business Logic**: Three cases: create (amount > 0, no existing), delete (amount == 0, existing), update (amount > 0, existing). `pair_id` allows multiple recurrent transfers between same accounts.
- **Hardfork Notes**: HF25 (introduced)

---

### 5.2 Account Evaluators (hive_evaluator_account.cpp)

---

#### account_create_evaluator
- **Source**: `hive_evaluator_account.cpp:156-208`
- **Reads**: creator account, `dynamic_global_property_object`, `witness_schedule_object` (median fee), null account (HF20+)
- **Modifies**: creator balance (deducted). Pre-HF20: fee converted to VESTS for new account. HF20+: fee sent to null (burned).
- **Creates**: `account_object` (via `create_account()` helper), `account_authority_object`
- **Removes**: —
- **Virtual Ops**: `account_created_operation` (always)
- **Chain-State Checks**:
  - HF20+: fee must equal exactly the median account_creation_fee
  - HF19-HF20: fee >= median * `HIVE_CREATE_ACCOUNT_WITH_HIVE_MODIFIER`
  - HF1+: fee >= median
  - Referenced accounts in authorities must exist
- **Business Logic**: Three fee eras. Post-HF20: exact fee, burned. Pre-HF20: minimum fee, converted to VESTS for new account.
- **Hardfork Notes**: HF1 (min fee), HF11 (recovery account), HF19 (higher fee), HF20 (exact fee, burn to null, RC adjustment, voting mana init)

---

#### account_create_with_delegation_evaluator
- **Source**: `hive_evaluator_account.cpp:210-283`
- **Reads**: creator account, `dynamic_global_property_object`, `witness_schedule_object`, null account (HF20+)
- **Modifies**: creator balance (deducted), creator delegated_vesting_shares (increased)
- **Creates**: `account_object`, `account_authority_object`, `vesting_delegation_object` (if delegation > 0 or pre-HF19)
- **Removes**: —
- **Virtual Ops**: `account_created_operation` (always, includes delegation amount)
- **Chain-State Checks**:
  - **DISABLED after HF20** — asserts `!has_hardfork(HF20)`
  - Sufficient HIVE balance and available vesting for delegation
  - Combined fee+delegation meets minimum threshold
- **Business Logic**: Deprecated at HF20. Created accounts with HIVE fee + VESTS delegation combination. Delegation has `HIVE_CREATE_ACCOUNT_DELEGATION_TIME` (30-day) minimum lifetime.
- **Hardfork Notes**: HF20 (disabled)

---

#### account_update_evaluator
- **Source**: `hive_evaluator_account.cpp:286-358`
- **Reads**: account, `account_authority_object`
- **Modifies**: `account_object` (memo_key, last_account_update), `account_authority_object` (active, posting). Owner via `update_owner_authority()` (creates `owner_authority_history_object`).
- **Creates**: `owner_authority_history_object` (if owner changed, via helper)
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**:
  - Cannot update temp account
  - HF20+: `validate_auth_size()` for each provided authority
  - HF11+: owner authority rate limited — once per hour (HF26+: twice per hour)
  - Referenced accounts in authorities must exist
- **Business Logic**: Pre-HF15: posting authority references to non-existing accounts silently removed. HF26 doubles owner update rate to 2/hour via two-timestamp check.
- **Hardfork Notes**: HF11 (owner rate limit), HF15 (strict posting auth), HF20 (auth size check), HF26 (2x/hour owner update)

---

#### account_update2_evaluator
- **Source**: `hive_evaluator_account.cpp:360-400`
- **Reads**: account, `account_authority_object`
- **Modifies**: Same as account_update
- **Creates**: `owner_authority_history_object` (if owner changed)
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**: HF21+ only. Same as account_update (minus pre-HF15 leniency).
- **Business Logic**: Nearly identical to `account_update` but `memo_key` is optional (can omit entirely). Introduced HF21.
- **Hardfork Notes**: HF21 (introduced), HF26 (2x/hour owner update)

---

#### claim_account_evaluator
- **Source**: `hive_evaluator_account.cpp:402-462`
- **Reads**: creator account, `witness_schedule_object`, `dynamic_global_property_object`, current block witness (fee=0 path), null account
- **Modifies**: creator balance (deducted if fee > 0), null account (receives fee), `account_object.pending_claimed_accounts++`, witness subsidies (if fee=0), global subsidies (if fee=0)
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**:
  - HF20+ only
  - Sufficient HIVE balance
  - Fee > 0: must equal exactly median account_creation_fee
  - Fee == 0: elected witness only, sufficient per-witness and global subsidies
- **Business Logic**: Two paths: (A) paid — exact fee, burned to null. (B) subsidized — uses RC system pools. Per-witness subsidy check only runs during block processing (not mempool validation). Increments `pending_claimed_accounts` for later use by `create_claimed_account`.
- **Hardfork Notes**: HF20 (introduced)

---

#### create_claimed_account_evaluator
- **Source**: `hive_evaluator_account.cpp:464-497`
- **Reads**: creator account, `dynamic_global_property_object`, `witness_schedule_object`
- **Modifies**: `account_object.pending_claimed_accounts--`
- **Creates**: `account_object`, `account_authority_object`
- **Removes**: —
- **Virtual Ops**: `account_created_operation` (always, with zero vesting/delegation)
- **Chain-State Checks**: HF20+ only. Creator must have `pending_claimed_accounts > 0`. Referenced accounts must exist.
- **Business Logic**: Second half of claim+create flow. Consumes one pending token. Fee passed to `create_account()` is for RC calculation only — no HIVE deducted.
- **Hardfork Notes**: HF20 (introduced)

---

#### request_account_recovery_evaluator
- **Source**: `hive_evaluator_account.cpp:499-552`
- **Reads**: target account, recovery agent account, top-voted witness (fallback), existing recovery requests
- **Modifies**: existing `account_recovery_request_object` (update authority + reset timer)
- **Creates**: `account_recovery_request_object` (new request, expires in `HIVE_ACCOUNT_RECOVERY_REQUEST_EXPIRATION_PERIOD`)
- **Removes**: `account_recovery_request_object` (when weight_threshold == 0 — cancel)
- **Virtual Ops**: —
- **Chain-State Checks**:
  - Recovery account must match the target's configured recovery partner
  - If no recovery partner set: top-voted witness is the default
  - Authority must not be impossible or open (zero threshold)
- **Business Logic**: Three branches: create, cancel (weight_threshold == 0), update (existing request). **Known bug**: `validate_auth_size` only called on new requests, not modifications — marked for HF29 fix.

---

#### recover_account_evaluator
- **Source**: `hive_evaluator_account.cpp:554-587`
- **Reads**: target account, active recovery request, `owner_authority_history_index`
- **Modifies**: owner authority (via `update_owner_authority()`), `account_object` (last_account_recovery_time, block_last_account_recovery_time)
- **Creates**: `owner_authority_history_object` (via helper)
- **Removes**: `account_recovery_request_object`
- **Virtual Ops**: —
- **Chain-State Checks**:
  - HF12+: recovery cooldown (1 hour) — note: uses simple single-check even after HF26
  - Active recovery request must exist
  - `new_owner_authority` must match request
  - `recent_owner_authority` must be found in authority history (proves knowledge of prior key)
- **Business Logic**: Core recovery algorithm. Requires dual proof: (1) recovery agent created a request with matching new authority, (2) account holder proves knowledge of a previous owner key. Request removed before authority update to avoid iterator invalidation.

---

#### change_recovery_account_evaluator
- **Source**: `hive_evaluator_account.cpp:589-615`
- **Reads**: new recovery account, target account, existing change requests
- **Modifies**: existing `change_recovery_account_request_object` (update target + reset timer)
- **Creates**: `change_recovery_account_request_object` (effective after `HIVE_OWNER_AUTH_RECOVERY_PERIOD` = 30 days)
- **Removes**: `change_recovery_account_request_object` (when requesting change back to current — cancel)
- **Virtual Ops**: —
- **Chain-State Checks**: New recovery account must exist (implicit from `get_account`)
- **Business Logic**: Three branches: create (30-day delay), update (reset timer), cancel (change back to current). The change is deferred, not immediate.

---

#### decline_voting_rights_evaluator
- **Source**: `hive_evaluator_account.cpp:617-643`
- **Reads**: account, existing decline request
- **Modifies**: —
- **Creates**: `decline_voting_rights_request_object` (when declining, effective after `HIVE_OWNER_AUTH_RECOVERY_PERIOD` = 30 days)
- **Removes**: `decline_voting_rights_request_object` (when cancelling)
- **Virtual Ops**: —
- **Chain-State Checks**:
  - HF14+ only
  - Account must still have `can_vote` (cannot decline twice)
  - Decline: no existing request. Cancel: existing request must exist.
- **Business Logic**: Two-step with delay. Once effective (processed by maintenance), `can_vote` is permanently false.
- **Hardfork Notes**: HF14 (introduced)

---

#### reset_account_evaluator
- **Source**: `hive_evaluator_account.cpp:645-651`
- **PERMANENTLY DISABLED**: Always asserts `false` — "Reset Account Operation is currently disabled."
- **Business Logic**: Never used. Related to abandoned feature (steem issue #240).

---

#### set_reset_account_evaluator
- **Source**: `hive_evaluator_account.cpp:653-657`
- **PERMANENTLY DISABLED**: Always asserts `false` — "Set Reset Account Operation is currently disabled."
- **Business Logic**: Same abandoned feature as reset_account.

---

### 5.3 Social Evaluators (hive_evaluator_social.cpp)

---

#### comment_evaluator
- **Source**: `hive_evaluator_social.cpp:174-312`
- **Reads**: author account, existing comment (for edits), parent comment (for replies), parent cashout (for reply count)
- **Modifies**: `account_object` — new: `last_root_post`, `post_bandwidth`, `last_post`, `last_post_edit`, `post_count++`. Edit: only `last_post_edit`. Parent's `comment_cashout_object` — `on_reply()` increments reply count (new replies only).
- **Creates**: `comment_object`, `comment_cashout_object`, `comment_cashout_ex_object` (pre-HF19 only)
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**:
  - **New comment**: depth limit (255 soft cap, 64K hard cap after HF17; strict `HIVE_MAX_COMMENT_DEPTH_PRE_HF17` before), UTF-8 json_metadata, frozen discussion check (HF12-HF17), posting frequency (pre-HF6: 1/min; HF6+: root every 5 min, reply every 3 sec), valid permlink (HF1+)
  - **Edit**: HF21+ edit interval (one per block), cannot change parent, era-dependent restrictions on editing after payout/archival
- **Business Logic**: Two paths: new comment vs edit. HF12-HF17: `reward_weight` penalizes frequent posting via post-bandwidth formula. Cashout time: HF17+ always `now + 7 days`; pre-HF17: replies had infinite cashout, roots had separate window.
- **Hardfork Notes**: HF1 (permlink validation), HF6 (posting intervals), HF10 (24h edit limit), HF12 (reward bandwidth), HF14 (archived check), HF17 (depth limit change, cashout unification), HF19 (cashout_ex removed), HF21 (edit interval, stricter parent change)

---

#### comment_options_evaluator
- **Source**: `hive_evaluator_social.cpp:108-172`
- **Reads**: comment, `comment_cashout_object`, beneficiary accounts
- **Modifies**: `comment_cashout_object` — `configure_options()` for percent_hbd/max_payout/allow_votes/allow_curation. `add_beneficiary()` for each beneficiary.
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**:
  - HF24+: setting options on paid-out comment is hard error (pre-HF24: silent return)
  - Options can only be made **more restrictive** (curation rewards, voting, max payout, HBD percent can only decrease)
  - Reducing rewards requires no existing votes
  - Beneficiaries: set once only, before any votes, each account must exist, max 8
- **Business Logic**: One-way ratchet on all option values. Beneficiaries max 8 (soft-fork check in control mode only).
- **Hardfork Notes**: HF24 (strict paid-out check)

---

#### delete_comment_evaluator
- **Source**: `hive_evaluator_social.cpp:55-106`
- **Reads**: `comment_object`, `comment_cashout_object`, all `comment_vote_object` for comment, parent cashout
- **Modifies**: parent's `comment_cashout_object` (`on_reply(true)` — decrements reply count)
- **Creates**: —
- **Removes**: All `comment_vote_object` entries, `comment_cashout_ex_object` (pre-HF19), `comment_cashout_object`, `comment_object`
- **Virtual Ops**: `ineffective_delete_comment_operation` (pre-HF19 only, when net_rshares > 0 — soft failure)
- **Chain-State Checks**:
  - No replies (cannot delete comment with replies)
  - Cashout object must exist (cannot delete after payout)
  - HF19+: net_rshares must be ≤ 0 (hard error). Pre-HF19: positive rshares → silent no-op with virtual op.
- **Business Logic**: Removes comment and all its votes. Pre-HF19: positive votes caused soft failure. HF19+: hard rejection.
- **Hardfork Notes**: HF19 (hard rejection of voted-on delete)

---

#### vote_evaluator
- **Source**: `hive_evaluator_social.cpp:854-864` (dispatcher), `pre_hf20_vote_evaluator:314-603`, `hf20_vote_evaluator:605-852`
- **Reads**: comment, `comment_cashout_object`, voter account, `dynamic_global_property_object`, existing `comment_vote_object`, `reward_fund_object` (HF17+), curation rewards percent
- **Modifies**: `account_object` (voting mana deducted, last_vote_time). `comment_cashout_object` (net_rshares, vote_weight, total_vote_weight). `comment_vote_object` (on edit). Pre-HF17: root `comment_cashout_object` and `comment_cashout_ex_object` (cashout time recalculation, abs_rshares), `dynamic_global_property_object` (rshares2).
- **Creates**: `comment_vote_object` (new vote)
- **Removes**: —
- **Virtual Ops**: `effective_comment_vote_operation` (always, on every successful vote)
- **Chain-State Checks**:
  - Voter has not declined voting rights
  - (positive vote) Comment allows votes
  - Sufficient voting mana/power
  - HF14+: rshares above `HIVE_VOTE_DUST_THRESHOLD` (or zero weight)
  - Upvote lockout: HF7 (1 min before payout), HF17+ (12 hours before payout, linear attenuation in HF20+)
  - New vote: weight != 0, rshares > 0
  - Vote edit: weight must differ from previous
  - HF20+ downvotes: `voting_mana + downvote_mana > used_mana`
- **Business Logic — Vote Power (Pre-HF20)**: Mana regeneration over `HIVE_VOTING_MANA_REGENERATION_SECONDS`. `used_power = current_power * |weight| * 86400 / (100% * vote_power_reserve_rate * regen_seconds)`. `rshares = effective_vesting_shares * used_power / 100%`.
- **Business Logic — Mana (HF20+)**: Three mana eras: (1) HF28+: `used_mana = effective_vesting_shares * |weight| * 86400 / 100%` (stake-based, not current-mana-based). (2) Pre-HF28 downvotes: mana scaled by downvote_pool_percent. (3) Pre-HF28 upvotes: `used_mana = voting_mana * |weight| * 86400 / 100%`. Dust threshold subtracted directly: `rshares = used_mana - HIVE_VOTE_DUST_THRESHOLD`.
- **Business Logic — Curation Weight**: Pre-HF17: `W(R) = MAX_UINT64 * R / (2S + R)`. HF17+: configurable reward curve via `evaluate_reward_curve()`. Reverse auction discount: early voting gives reduced curation weight. HF25+: three voting phases — early (full weight), mid (÷2), late (÷8). HF26+: vote edits receive curation rewards (previously: `vote_weight = 0` on edits).
- **Hardfork Notes**: HF1 (scaling), HF6 (duplicate vote check), HF7 (lockout), HF13 (dust threshold), HF14 (dust rounding), HF17 (lockout 12h, reward fund curve, cashout unification), HF19 (sqrt curve override), HF20 (mana system, downvote pool, lockout attenuation), HF22 (uint128 downvote fix), HF25 (early/mid/late phases), HF26 (vote edit curation), HF28 (stake-based vote)

---

### 5.4 Witness Evaluators (hive_evaluator.cpp)

---

#### witness_update_evaluator
- **Source**: `hive_evaluator.cpp:62-99`
- **Reads**: owner account, existing witness (if any)
- **Modifies**: `witness_object` (url, signing_key, props)
- **Creates**: `witness_object` (if none exists)
- **Removes**: —
- **Virtual Ops**: `system_warning_operation` (pre-HF14, non-canonical fee symbol — 8 known mainnet instances)
- **Chain-State Checks**: HF14+: fee symbol must be canonical
- **Business Logic**: Create-or-update pattern. Copies legacy chain properties (account_creation_fee, maximum_block_size, hbd_interest_rate).
- **Hardfork Notes**: HF14 (canonical fee symbol enforcement)

---

#### witness_set_properties_evaluator
- **Source**: `hive_evaluator.cpp:113-208`
- **Reads**: `witness_object` by name
- **Modifies**: `witness_object` (any/all of: props, signing_key, hbd_exchange_rate, last_hbd_exchange_update, url)
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**:
  - HF20+ only
  - `key` property must match current `signing_key` (authentication)
- **Business Logic**: Uses bitfield to track which properties were provided, applies only those in a single `modify()`. The `key` field authenticates (must match current key); `new_signing_key` rotates the key. HF24: accepts renamed property keys (`hbd_interest_rate` in addition to legacy `sbd_interest_rate`).
- **Hardfork Notes**: HF20 (introduced), HF24 (renamed HBD property keys)

---

#### account_witness_proxy_evaluator
- **Source**: `hive_evaluator.cpp:210-261`
- **Reads**: account, proxy account, proxy chain (walked iteratively)
- **Modifies**: `account_object` (governance_vote_expiration_ts, proxy). Nullifies/adjusts proxied witness votes through chain. Clears individual witness votes when setting proxy.
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: `proxy_cleared_operation` (when switching proxies or clearing)
- **Chain-State Checks**:
  - Account can vote
  - Proxy must change (not a no-op)
  - No proxy loops (checked by walking chain)
  - Proxy chain depth ≤ `HIVE_MAX_PROXY_RECURSION_DEPTH` (4)
- **Business Logic**: Setting proxy: nullifies existing votes, checks for loops (max depth 4), clears individual witness votes, sets new proxy, propagates vote power. Clearing: nullifies and clears.

---

#### account_witness_vote_evaluator
- **Source**: `hive_evaluator.cpp:264-326`
- **Reads**: voter account, `witness_object`, existing `witness_vote_object`
- **Modifies**: `account_object` (governance_vote_expiration_ts, witnesses_voted_for). `witness_object` (votes, via `adjust_witness_vote` post-HF3).
- **Creates**: `witness_vote_object` (on approve)
- **Removes**: `witness_vote_object` (on unapprove)
- **Virtual Ops**: —
- **Chain-State Checks**:
  - No proxy set
  - Can vote (not declined)
  - HF2+: max 30 witness votes
  - Cannot approve if already approved / reject if no vote
- **Business Logic**: Three vote-counting eras: pre-HF2 (direct modify), HF2-HF3 (proxied adjustment), post-HF3 (direct witness vote adjustment). Vote weight from `get_governance_vote_power()`.
- **Hardfork Notes**: HF2 (30-vote limit, proxied adjustment), HF3 (direct witness vote adjustment)

---

#### custom_evaluator
- **Source**: `hive_evaluator.cpp:328-335`
- **Reads**: —
- **Modifies**: —
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**: HF26+: data size ≤ `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` (8192 bytes)
- **Business Logic**: Minimal. Only enforces data size limit. No custom interpreter invoked (unlike custom_json).
- **Hardfork Notes**: HF26 (data size limit solidified from softfork)

---

#### custom_json_evaluator
- **Source**: `hive_evaluator.cpp:337-373`
- **Reads**: registered `custom_operation_interpreter` by `o.id`
- **Modifies**: Indirectly via interpreter's `apply(o)`
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: Depends on interpreter
- **Chain-State Checks**: HF26+: JSON size ≤ `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` (8192 bytes)
- **Business Logic**: Looks up interpreter by `id` string. If none registered, silently returns. In control mode (producing/validating): interpreter exceptions propagate. During replay: fc::exceptions swallowed, non-fc logged. Evaluator's responsibility to undo changes on exception.
- **Hardfork Notes**: HF26 (JSON size limit solidified)

---

#### custom_binary_evaluator
- **Source**: `hive_evaluator.cpp:376-399`
- **PERMANENTLY DISABLED**: Always asserts `false` — "Operation disallowed."
- **Business Logic**: Dead code. Waits for potential redesign.

---

#### pow_evaluator
- **Source**: `hive_evaluator.cpp:402-505`
- **DISABLED after HF13**: Asserts `!has_hardfork(HF13)` — "pow is deprecated. Use pow2 instead"
- **Reads**: `dynamic_global_property_object`, existing witness, worker account, PoW difficulty target
- **Modifies**: `dynamic_global_property_object` (total_pow, num_pow_witnesses), witness (pow_worker, last_work), supply (reward)
- **Creates**: `account_object` (mined account if new), `account_authority_object`, `witness_object` (if new)
- **Removes**: —
- **Virtual Ops**: `account_created_operation` (new account), `pow_reward_operation` (block producer reward)
- **Chain-State Checks**: HF5+: no duplicate work. Active/signing key checks. Block ID must match head. Difficulty check. Existing witness not already scheduled.
- **Business Logic**: Mined account creation. Reward before `HIVE_START_MINER_VOTING_BLOCK`: `pow_reward * HIVE_MAX_WITNESSES` as liquid HIVE. After: `pow_reward` as VESTS. Reward goes to block producer, not miner.
- **Hardfork Notes**: HF5 (duplicate work detection), HF13 (disabled)

---

#### pow2_evaluator
- **Source**: `hive_evaluator.cpp:508-603`
- **DISABLED after HF17**: Asserts `!has_hardfork(HF17)` — "mining is now disabled"
- **Reads**: `dynamic_global_property_object`, PoW difficulty target, worker account, existing witness
- **Modifies**: Same pattern as pow. `dynamic_global_property_object` (total_pow, num_pow_witnesses). Block producer reward (VESTS, only pre-HF16).
- **Creates**: `account_object` (if new), `account_authority_object`, `witness_object` (for new accounts)
- **Removes**: —
- **Virtual Ops**: `account_created_operation` (new account), `pow_reward_operation` (pre-HF16 only)
- **Chain-State Checks**: `new_owner_key` required for new accounts, forbidden for existing. Existing accounts must have witness. Difficulty check. Min block size.
- **Business Logic**: Two eras: pre-HF16 (pow2 work type), HF16+ (equihash). Block producer reward only pre-HF16. Existing accounts must already have a witness before mining.
- **Hardfork Notes**: HF16 (equihash, reward removed), HF17 (fully disabled)

---

#### feed_publish_evaluator
- **Source**: `hive_evaluator.cpp:605-621`
- **Reads**: `witness_object` by publisher name
- **Modifies**: `witness_object` (hbd_exchange_rate, last_hbd_exchange_update)
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**: HF20+: feed must be HBD base / HIVE quote
- **Business Logic**: Writes exchange rate and timestamp to witness object. Median price computation happens elsewhere (`update_median_feed()`).
- **Hardfork Notes**: HF20 (HBD/HIVE direction enforcement)

---

#### witness_block_approve_evaluator
- **Source**: `hive_evaluator.cpp:623-628`
- **PERMANENTLY DISABLED**: Always asserts `false` — "Operation excluded from blocks."
- **Business Logic**: Handled in `database::process_fast_confirm_transaction`, never reaches evaluator.

---

### 5.5 DHF (Proposal) Evaluators (dhf_evaluator.cpp)

---

#### create_proposal_evaluator
- **Source**: `dhf_evaluator.cpp:32-101`
- **Reads**: treasury account, creator account, receiver account, comment by creator or receiver
- **Modifies**: creator balance (deducted), treasury balance (credited)
- **Creates**: `proposal_object`
- **Removes**: —
- **Virtual Ops**: `proposal_fee_operation` (always)
- **Chain-State Checks**:
  - HF21+ only
  - End date must be in future (start date can be in the past)
  - Receiver account must exist
  - Permlink must point to a post by creator or receiver
- **Business Logic**: Base fee `HIVE_TREASURY_FEE` (10 HBD). HF24+: graduated fee — adds 1 HBD per day beyond 60-day duration. Fee paid to treasury.
- **Hardfork Notes**: HF21 (introduced), HF24 (graduated fee)

---

#### update_proposal_evaluator
- **Source**: `dhf_evaluator.cpp:103-153`
- **Reads**: `proposal_object`, comment by creator or receiver
- **Modifies**: `proposal_object` (daily_pay, subject, permlink, end_date)
- **Creates**: —
- **Removes**: —
- **Virtual Ops**: —
- **Chain-State Checks**:
  - HF24+ only
  - Only creator can update (not receiver)
  - Daily pay can only decrease or stay same
  - HF25+: end date can only shorten, must remain after start_date
  - At most one extension
- **Business Logic**: One-way ratchet on pay and duration. Subject and permlink freely changeable.
- **Hardfork Notes**: HF24 (introduced), HF25 (end_date shortening via extension)

---

#### update_proposal_votes_evaluator
- **Source**: `dhf_evaluator.cpp:155-211`
- **Reads**: proposal index, proposal vote index, voter account
- **Modifies**: `account_object` (governance_vote_expiration_ts)
- **Creates**: `proposal_vote_object` (on approve, if not already existing)
- **Removes**: `proposal_vote_object` (on unapprove, if existing)
- **Virtual Ops**: —
- **Chain-State Checks**:
  - HF21+ only
  - Voter has not declined voting rights
  - HF28+: voting on nonexistent/removed proposal is hard error (pre-HF28: silently skipped)
  - HF25+: voting on expired proposals forbidden
- **Business Logic**: Batch operation — processes set of proposal IDs. Idempotent: approve+existing = no-op, unapprove+absent = no-op. Removed proposals treated as nonexistent. Governance expiration updated on every call.
- **Hardfork Notes**: HF21 (introduced), HF25 (expired vote restriction), HF28 (strict nonexistent proposal check)

---

#### remove_proposal_evaluator
- **Source**: `dhf_evaluator.cpp:213-252`
- **Reads**: proposal index
- **Modifies**: `proposal_object` (removed=true, end_date backdated)
- **Creates**: —
- **Removes**: `proposal_vote_object` (all votes for each proposal), `proposal_object` (via helper, throttled)
- **Virtual Ops**: —
- **Chain-State Checks**:
  - HF21+ only
  - Only creator can remove own proposals
  - HF28+: removing nonexistent proposal is hard error
- **Business Logic**: Two-phase removal. Phase 1: physical removal of proposals + votes via `dhf_helper::remove_proposals()` with per-block threshold. Phase 2: marks remaining with `removed=true` and backdated `end_date` (1 day in past) for maintenance cleanup.
- **Hardfork Notes**: HF21 (introduced), HF28 (strict nonexistent proposal check)

---

## 6. Virtual Operation Generation Map (Evaluator-Direct)

| Evaluator | Virtual Operation | Condition |
|-----------|-------------------|-----------|
| transfer | `dhf_conversion_operation` | HIVE sent to treasury (HF24+) |
| transfer_to_vesting | `transfer_to_vesting_completed_operation` | Always |
| collateralized_convert | `collateralized_convert_immediate_conversion_operation` | Always |
| account_create | `account_created_operation` | Always |
| account_create_with_delegation | `account_created_operation` | Always |
| create_claimed_account | `account_created_operation` | Always |
| pow | `account_created_operation` | New account created |
| pow | `pow_reward_operation` | Block producer reward |
| pow2 | `account_created_operation` | New account created |
| pow2 | `pow_reward_operation` | Pre-HF16 only |
| delete_comment | `ineffective_delete_comment_operation` | Pre-HF19, net_rshares > 0 |
| vote | `effective_comment_vote_operation` | Always |
| witness_update | `system_warning_operation` | Pre-HF14, non-canonical fee |
| account_witness_proxy | `proxy_cleared_operation` | When switching or clearing proxy |
| escrow_approve | `escrow_rejected_operation` | On rejection |
| escrow_approve | `escrow_approved_operation` | When both parties approve |
| create_proposal | `proposal_fee_operation` | Always |

---

## 7. State Object Modification Map

| Object | Created By | Modified By | Removed By |
|--------|-----------|-------------|------------|
| `account_object` | account_create, create_with_delegation, create_claimed_account, pow, pow2 | transfer, transfer_to_vesting, withdraw_vesting, claim_account, create_claimed_account, account_update, account_update2, recover_account, claim_reward_balance, delegate_vesting_shares, vote, comment, escrow_transfer/approve/release, transfer_to/from_savings, cancel_transfer_from_savings, recurrent_transfer, set_withdraw_vesting_route, decline_voting_rights, account_witness_vote, account_witness_proxy, update_proposal_votes | — |
| `account_authority_object` | account_create, create_with_delegation, create_claimed_account, pow, pow2 | account_update, account_update2 | — |
| `owner_authority_history_object` | account_update (via helper), account_update2, recover_account | — | — |
| `witness_object` | witness_update, pow, pow2 | witness_update, witness_set_properties, feed_publish, account_witness_vote, claim_account (subsidies), pow, pow2 | — |
| `witness_vote_object` | account_witness_vote (approve) | — | account_witness_vote (unapprove) |
| `comment_object` | comment | — | delete_comment |
| `comment_cashout_object` | comment | comment, comment_options, vote | delete_comment |
| `comment_cashout_ex_object` | comment (pre-HF19) | vote (pre-HF17) | delete_comment (pre-HF19) |
| `comment_vote_object` | vote | vote (edit) | delete_comment (all) |
| `convert_request_object` | convert | — | — (removed by process_conversions) |
| `collateralized_convert_request_object` | collateralized_convert | — | — (removed by process_conversions) |
| `limit_order_object` | limit_order_create, limit_order_create2 | apply_order/fill_order (partial fill) | limit_order_cancel, apply_order (full fill), clear_expired_orders |
| `escrow_object` | escrow_transfer | escrow_approve, escrow_dispute, escrow_release | escrow_approve (rejection), escrow_release (emptied), expire_escrow_ratification |
| `savings_withdraw_object` | transfer_from_savings | — | cancel_transfer_from_savings, process_savings_withdraws |
| `vesting_delegation_object` | delegate_vesting_shares, account_create_with_delegation | delegate_vesting_shares (increase) | delegate_vesting_shares (zero) |
| `vesting_delegation_expiration_object` | delegate_vesting_shares (decrease) | — | clear_expired_delegations |
| `withdraw_vesting_route_object` | set_withdraw_vesting_route | set_withdraw_vesting_route (update) | set_withdraw_vesting_route (percent=0) |
| `account_recovery_request_object` | request_account_recovery | request_account_recovery (update) | request_account_recovery (cancel), recover_account |
| `change_recovery_account_request_object` | change_recovery_account | change_recovery_account (update) | change_recovery_account (cancel) |
| `decline_voting_rights_request_object` | decline_voting_rights | — | decline_voting_rights (cancel), process_decline_voting_rights |
| `proposal_object` | create_proposal | update_proposal, remove_proposal (marks removed) | remove_proposal (via helper) |
| `proposal_vote_object` | update_proposal_votes | — | update_proposal_votes, remove_proposal (via helper) |
| `recurrent_transfer_object` | recurrent_transfer | recurrent_transfer (update) | recurrent_transfer (amount=0), process_recurrent_transfers |
| `dynamic_global_property_object` | — | collateralized_convert, claim_reward_balance, claim_account, pow, pow2, vote (pre-HF17 rshares2) | — |
| `reward_fund_object` | — | — (read by vote evaluator; modified by process_comment_cashout) | — |
| `feed_history_object` | — | — (modified by update_median_feed) | — |

---

## 8. Key Discoveries

1. **Evaluators split across 5 files** (not one monolithic file): `hive_evaluator.cpp` (witness/custom/pow/feed), `hive_evaluator_account.cpp`, `hive_evaluator_social.cpp`, `hive_evaluator_transfer.cpp`, `dhf_evaluator.cpp`.

2. **50 evaluators registered** matching the 50 regular operations. 4 are permanently disabled (custom_binary, witness_block_approve, reset_account, set_reset_account). 3 more are hardfork-disabled (pow at HF13, pow2 at HF17, account_create_with_delegation at HF20).

3. **HF28 introduces stake-based voting** (`HIVE_HARDFORK_1_28_STABLE_VOTE`): vote mana consumption becomes proportional to `effective_vesting_shares` directly, rather than current mana. This makes vote weight deterministic regardless of current mana level.

4. **HF25 introduces three-phase curation** (early/mid/late): early voting gets full weight, mid-window gets ÷2, late gets ÷8. This replaced the reverse auction mechanism.

5. **HF26 removes vote-edit curation penalty**: before HF26, editing a vote set `vote_weight = 0` (no curation reward for edited votes). After HF26, edits receive proper curation weight.

6. **Collateralized conversion** (HF25) enforces two separate HBD supply caps: `hbd_print_rate > 0` AND `percent_hbd <= hbd_stop_percent`.

7. **Known bug in request_account_recovery**: `validate_auth_size` is only called on new requests, not modifications. Editing an existing request can introduce an oversized authority. Code comment marks this for HF29 fix.

8. **Recovery account rate limit asymmetry**: `recover_account` uses the simple 1-hour check (two-argument `owner_update_limit_mgr::check`) even after HF26, unlike `account_update`/`account_update2` which use the three-argument version (2x/hour).

9. **HIVE-to-treasury auto-conversion** (HF24): when HIVE is sent to the treasury via transfer, it is automatically converted to HBD at median price and the HIVE is burned. This makes the treasury HBD-only.

10. **Proposal removal is two-phase**: first physically removes up to a threshold (votes + proposals), then marks remaining with `removed=true` and backdated end_date for maintenance cleanup.

11. **30-step end-of-block processing order** is critical: the sequence matters because each step may depend on state changes from prior steps (e.g., `update_median_feed()` before `process_conversions()`; `update_virtual_supply()` runs twice — before and after major state changes).

12. **HBD interest accrual hidden in adjust_balance**: calling `adjust_balance()` with an HBD delta triggers interest calculation as a side effect, generating `interest_operation` virtual ops. This non-obvious behavior means any HBD balance modification may alter the account's balance beyond the stated delta.

13. **custom_json exception handling differs by mode**: during block production/validation, interpreter exceptions propagate (transaction rejected). During replay, exceptions are swallowed to avoid chain divergence from non-deterministic interpreter bugs.

---

## 9. Discrepancies and Potential Issues

1. **validate_auth_size gap in request_account_recovery**: Existing request modification skips authority size validation. Marked in code as FC_TODO for HF29.

2. **Recovery rate limit inconsistency**: `recover_account` uses simpler rate limit check than `account_update`/`account_update2` after HF26. May be intentional (recovery is more sensitive) or oversight.

3. **custom_json exception swallowing during replay**: Non-fc exceptions are logged via `elog` but not propagated. If a custom operation interpreter has a non-fc exception, state changes from the interpreter may have been applied but the exception was swallowed — the code comment notes evaluators must undo their own changes on exception (references issue #256).

4. **Pre-HF19 delete_comment soft failure**: Before HF19, deleting a comment with positive votes silently does nothing (emits `ineffective_delete_comment_operation`). Users may not realize their delete was ineffective without watching virtual ops.

5. **Escrow `pending_escrow_transfers` counter**: The counter is modified in multiple evaluators (transfer, approve, release) and maintenance code (expire_escrow_ratification). Any bug in counter management could lead to permanent lockout (counter stuck above 0 preventing account clearing).

---

## 10. Open Questions

1. How does the RC (Resource Credit) system interact with evaluator execution? `rc().handle_operation_discount()` is called before each evaluator — what discounts apply?

2. The `delayed_voting` mechanism (HF24+): how exactly are the delayed governance votes processed? What happens during the 30-day window?

3. What is the exact `evaluate_reward_curve()` implementation? The vote evaluator uses it but the curve type is configurable per reward fund.

4. How does `process_proposals()` (DHF payout) work? The evaluators only create/modify/remove proposals and votes — the actual payment to proposal recipients is in the end-of-block processing.

5. How does `process_fast_confirm_transaction()` handle the `witness_block_approve_operation` that bypasses the evaluator?

---

## Code References

| File | Purpose |
|------|---------|
| `libraries/chain/include/hive/chain/evaluator.hpp` | Base evaluator class, HIVE_DEFINE_EVALUATOR macro |
| `libraries/chain/include/hive/chain/evaluator_registry.hpp` | Evaluator dispatch table |
| `libraries/chain/include/hive/chain/hive_evaluator.hpp` | Registration function declarations |
| `libraries/chain/hive_evaluator.cpp` | Witness, custom, pow, feed evaluators |
| `libraries/chain/hive_evaluator_account.cpp` | Account create/update/recovery evaluators |
| `libraries/chain/hive_evaluator_social.cpp` | Comment, vote, delete evaluators |
| `libraries/chain/hive_evaluator_transfer.cpp` | Transfer, vesting, conversion, escrow, savings, delegation, DEX evaluators |
| `libraries/chain/dhf_evaluator.cpp` | DHF proposal evaluators |
| `libraries/chain/database.cpp` | Evaluator dispatch, balance/supply helpers, end-of-block processing |
| `libraries/chain/database_init.cpp` | Evaluator registration |
| `libraries/chain/database_account.cpp` | Account management helpers |
| `libraries/chain/database_comment.cpp` | Comment cashout, curation reward helpers |
| `libraries/chain/database_market.cpp` | DEX order matching, escrow, savings helpers |
| `libraries/chain/database_vesting.cpp` | Vesting withdrawal processing |
| `libraries/chain/database_conversion.cpp` | Conversion processing helpers |
| `libraries/chain/database_delegation.cpp` | Delegation index initialization |
| `libraries/chain/database_dhf.cpp` | Recurrent transfer processing, governance helpers |
