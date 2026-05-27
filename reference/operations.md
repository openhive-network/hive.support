# Hive Operations Reference

Source: hive-core release 1.28.6. 50 regular operations (IDs 0-49) + 43 virtual operations (IDs 50-92).

---

## Index Table

| ID | Name | Category | Authority | Status |
|----|------|----------|-----------|--------|
| 0 | vote | Social | posting | active |
| 1 | comment | Social | posting | active |
| 2 | transfer | Transfer | active | active |
| 3 | transfer_to_vesting | Vesting | active | active |
| 4 | withdraw_vesting | Vesting | active | active |
| 5 | limit_order_create | Market | active | active |
| 6 | limit_order_cancel | Market | active | active |
| 7 | feed_publish | Witness | active | active |
| 8 | convert | Transfer | active | active |
| 9 | account_create | Account | active | active |
| 10 | account_update | Account | owner/active | active |
| 11 | witness_update | Witness | active | active |
| 12 | account_witness_vote | Governance | active | active |
| 13 | account_witness_proxy | Governance | active | active |
| 14 | pow | -- | -- | disabled (HF13) |
| 15 | custom | Custom | active | active |
| 16 | witness_block_approve | Witness | witness | disabled |
| 17 | delete_comment | Social | posting | active |
| 18 | custom_json | Custom | active+posting | active |
| 19 | comment_options | Social | posting | active |
| 20 | set_withdraw_vesting_route | Vesting | active | active |
| 21 | limit_order_create2 | Market | active | active |
| 22 | claim_account | Account | active | active (HF20+) |
| 23 | create_claimed_account | Account | active | active (HF20+) |
| 24 | request_account_recovery | Account | active | active |
| 25 | recover_account | Account | dual custom | active |
| 26 | change_recovery_account | Account | owner | active |
| 27 | escrow_transfer | Escrow | active | active |
| 28 | escrow_dispute | Escrow | active | active |
| 29 | escrow_release | Escrow | active | active |
| 30 | pow2 | -- | -- | disabled (HF17) |
| 31 | escrow_approve | Escrow | active | active |
| 32 | transfer_to_savings | Transfer | active | active |
| 33 | transfer_from_savings | Transfer | active | active |
| 34 | cancel_transfer_from_savings | Transfer | active | active |
| 35 | custom_binary | Custom | multi-level | disabled |
| 36 | decline_voting_rights | Governance | owner | active |
| 37 | reset_account | -- | -- | disabled (never implemented) |
| 38 | set_reset_account | -- | -- | disabled (never implemented) |
| 39 | claim_reward_balance | Transfer | posting | active |
| 40 | delegate_vesting_shares | Vesting | active | active |
| 41 | account_create_with_delegation | Account | active | disabled (HF20) |
| 42 | witness_set_properties | Witness | signing key | active (HF20+) |
| 43 | account_update2 | Account | owner/active/posting | active (HF21+) |
| 44 | create_proposal | DHF | active | active (HF21+) |
| 45 | update_proposal_votes | DHF | active | active (HF21+) |
| 46 | remove_proposal | DHF | active | active (HF21+) |
| 47 | update_proposal | DHF | active | active (HF24+) |
| 48 | collateralized_convert | Transfer | active | active (HF25+) |
| 49 | recurrent_transfer | Transfer | active | active (HF25+) |

---

## Disabled Operations

- **pow_operation (14)**: Deprecated at HF13. Use pow2 (also disabled).
- **pow2_operation (30)**: Mining disabled at HF17.
- **witness_block_approve_operation (16)**: Handled internally, evaluator always rejects.
- **custom_binary_operation (35)**: Evaluator always rejects. Dead code.
- **reset_account_operation (37)**: validate() always fails. Never implemented placeholder.
- **set_reset_account_operation (38)**: validate() always fails. Never implemented placeholder.
- **account_create_with_delegation_operation (41)**: Deprecated at HF20. Evaluator rejects.

---

## Social/Content Operations

### vote_operation (ID: 0)
**Authority**: posting (voter)
**Fields**: voter (account), author (account), permlink (string), weight (int16)
**Validation**: |weight| <= 10000; permlink < 256 chars UTF-8
**Evaluator**: Deducts voting mana from voter proportional to |weight|. Computes rshares and applies to comment. HF20+: separate downvote mana pool. HF28+: stake-based (not mana-based) vote power calculation. Creates/updates comment_vote_object.
**Virtual ops**: effective_comment_vote_operation (always)
**Notes**: Upvote lockout 12h before payout (HF17+). Vote edits get curation rewards since HF26. Three-phase curation weighting since HF25 (early=full, mid=/2, late=/8).

### comment_operation (ID: 1)
**Authority**: posting (author)
**Fields**: parent_author (account), parent_permlink (string), author (account), permlink (string), title (string), body (string), json_metadata (json)
**Validation**: title <= 255 chars; body non-empty; permlink < 256 chars; all UTF-8; json_metadata valid JSON if non-empty
**Evaluator**: Creates or edits post/comment. New: sets cashout time (now + 7 days HF17+), increments parent reply count. Edit: updates content only. Posting frequency limits: root posts every 5 min, replies every 3 sec (HF6+). Max depth 255 (HF17+).
**Virtual ops**: None directly. Payouts happen via process_comment_cashout at end-of-block.

### delete_comment_operation (ID: 17)
**Authority**: posting (author)
**Fields**: author (account), permlink (string)
**Validation**: Valid account and permlink
**Evaluator**: Removes comment, all votes, and cashout objects. Fails if comment has replies or net_rshares > 0 (HF19+; pre-HF19 was silent no-op for voted comments). Cannot delete after payout.
**Virtual ops**: ineffective_delete_comment_operation (pre-HF19 only, on soft failure)

### comment_options_operation (ID: 19)
**Authority**: posting (author)
**Fields**: author (account), permlink (string), max_accepted_payout (HBD asset), percent_hbd (uint16), allow_votes (bool), allow_curation_rewards (bool), extensions (beneficiaries)
**Validation**: percent_hbd <= 10000; max_accepted_payout HBD >= 0; beneficiaries sorted by account, total weight <= 100%, max 127 entries
**Evaluator**: Options can only be made MORE restrictive (one-way ratchet). Beneficiaries: set once, before any votes, max 8 (soft-fork), each account must exist.
**Notes**: Extensions contain comment_payout_beneficiaries with (account, weight) pairs.

---

## Transfer/Financial Operations

### transfer_operation (ID: 2)
**Authority**: active (from)
**Fields**: from (account), to (account), amount (asset), memo (string)
**Validation**: amount > 0; HIVE or HBD only (no VESTS); memo <= 2047 chars UTF-8. Note: from==to is allowed at protocol level.
**Evaluator**: Deducts from sender, credits receiver. Triggers HBD interest calculation on both accounts (pre-HF25 on liquid, post-HF25 savings only). HIVE sent to treasury is auto-converted to HBD (HF24+).
**Virtual ops**: dhf_conversion_operation (HIVE to treasury, HF24+)

### transfer_to_savings_operation (ID: 32)
**Authority**: active (from)
**Fields**: from (account), to (account), amount (asset), memo (string)
**Validation**: amount > 0; HIVE or HBD; memo <= 2047 chars UTF-8
**Evaluator**: Moves liquid balance to savings. Cannot send to treasury savings. Triggers HBD interest on savings balance.

### transfer_from_savings_operation (ID: 33)
**Authority**: active (from)
**Fields**: from (account), request_id (uint32), to (account), amount (asset), memo (string)
**Validation**: amount > 0; HIVE or HBD; memo <= 2047 chars UTF-8
**Evaluator**: Creates 3-day pending withdrawal. Deducts savings immediately. Max pending requests: HIVE_SAVINGS_WITHDRAW_REQUEST_LIMIT. Only HBD can be withdrawn to treasury.
**Virtual ops**: fill_transfer_from_savings_operation (on completion, 3 days later)

### cancel_transfer_from_savings_operation (ID: 34)
**Authority**: active (from)
**Fields**: from (account), request_id (uint32)
**Evaluator**: Returns funds to savings, removes pending withdrawal.

### convert_operation (ID: 8)
**Authority**: active (owner)
**Fields**: owner (account), requestid (uint32), amount (asset)
**Validation**: amount > 0; HBD only
**Evaluator**: HBD->HIVE conversion. Deducts HBD immediately; HIVE paid after 3.5-day delay (HIVE_CONVERSION_DELAY) at median price at completion time.
**Virtual ops**: fill_convert_request_operation (on completion)

### collateralized_convert_operation (ID: 48)
**Authority**: active (owner)
**Fields**: owner (account), requestid (uint32), amount (asset)
**Validation**: amount > 0; HIVE only
**Evaluator**: HIVE->HBD with 2x overcollateralization. HBD delivered immediately at current_min_history price. Excess HIVE collateral returned after HIVE_COLLATERALIZED_CONVERSION_DELAY at median price. Requires hbd_print_rate > 0.
**Virtual ops**: collateralized_convert_immediate_conversion_operation (always); fill_collateralized_convert_request_operation (on completion)
**Notes**: HF25+. Fails if new HBD would violate global hbd_stop_percent cap.

### claim_reward_balance_operation (ID: 39)
**Authority**: posting (account)
**Fields**: account (account), reward_hive (HIVE asset), reward_hbd (HBD asset), reward_vests (VESTS asset)
**Validation**: Each >= 0; at least one > 0; correct asset types
**Evaluator**: Moves earned rewards from reward balances to active balances. VESTS become active HP. Updates governance vote weight. Cannot claim more than earned.

### recurrent_transfer_operation (ID: 49)
**Authority**: active (from)
**Fields**: from (account), to (account), amount (asset), memo (string), recurrence (uint16 hours), executions (uint16), extensions (pair_id)
**Validation**: from != to; HIVE or HBD; amount >= 0 (0 = cancel); recurrence >= 24 hours; executions >= 2; memo <= 2047 chars
**Evaluator**: Creates/updates/deletes scheduled recurring transfer. Sufficient balance required for first execution. Max open transfers per account limited. pair_id extension allows multiple recurrent transfers between same accounts.
**Virtual ops**: fill_recurrent_transfer_operation (each execution); failed_recurrent_transfer_operation (insufficient funds)
**Notes**: HF25+. Auto-deleted after HIVE_MAX_CONSECUTIVE_RECURRENT_TRANSFER_FAILURES consecutive failures.

---

## Account Operations

### account_create_operation (ID: 9)
**Authority**: active (creator)
**Fields**: fee (HIVE asset), creator (account), new_account_name (account), owner (authority), active (authority), posting (authority), memo_key (public_key), json_metadata (json)
**Validation**: fee HIVE >= 0, <= 1B HIVE; auth sizes <= 40; valid JSON if non-empty
**Evaluator**: HF20+: fee must exactly equal median account_creation_fee, fee burned to null. Pre-HF20: fee >= median, converted to VESTS for new account.
**Virtual ops**: account_created_operation

### account_update_operation (ID: 10)
**Authority**: owner if owner field set; otherwise active
**Fields**: account (account), owner (optional authority), active (optional authority), posting (optional authority), memo_key (public_key), json_metadata (json)
**Evaluator**: Updates account authorities and metadata. Owner changes rate-limited: once per hour (HF26+: twice per hour). Creates owner_authority_history_object on owner change.

### account_update2_operation (ID: 43)
**Authority**: owner if owner set; active if active/posting/memo_key/json_metadata set; posting if only posting_json_metadata set
**Fields**: account (account), owner/active/posting (optional authorities), memo_key (optional public_key), json_metadata (json), posting_json_metadata (json), extensions
**Evaluator**: Same as account_update but memo_key is optional and adds posting_json_metadata field. Three-tier authority model.
**Notes**: HF21+. The only operation allowing profile metadata updates with just posting authority.

### claim_account_operation (ID: 22)
**Authority**: active (creator)
**Fields**: creator (account), fee (HIVE asset), extensions
**Validation**: fee HIVE >= 0
**Evaluator**: Two paths: (A) fee > 0: must equal exact median fee, burned to null. (B) fee == 0: subsidized via RC system, elected witnesses only. Increments pending_claimed_accounts.
**Notes**: HF20+. First half of claim+create account flow.

### create_claimed_account_operation (ID: 23)
**Authority**: active (creator)
**Fields**: creator (account), new_account_name (account), owner/active/posting (authorities), memo_key (public_key), json_metadata (json), extensions
**Evaluator**: Consumes one pending_claimed_accounts token. No HIVE deducted. Creates account.
**Virtual ops**: account_created_operation
**Notes**: HF20+. Second half of claim+create flow.

### request_account_recovery_operation (ID: 24)
**Authority**: active (recovery_account)
**Fields**: recovery_account (account), account_to_recover (account), new_owner_authority (authority), extensions
**Evaluator**: Creates recovery request valid for HIVE_ACCOUNT_RECOVERY_REQUEST_EXPIRATION_PERIOD (24h). Recovery account must be the target's configured recovery partner (default: top-voted witness). weight_threshold == 0 cancels.

### recover_account_operation (ID: 25)
**Authority**: must satisfy BOTH new_owner_authority AND recent_owner_authority
**Fields**: account_to_recover (account), new_owner_authority (authority), recent_owner_authority (authority)
**Validation**: new != recent; both non-impossible
**Evaluator**: Requires dual proof: matching recovery request + knowledge of previous owner key (found in authority history, valid 30 days). Recovery cooldown: 1 hour.
**Notes**: The only operation requiring two separate authority objects simultaneously.

### change_recovery_account_operation (ID: 26)
**Authority**: owner (account_to_recover)
**Fields**: account_to_recover (account), new_recovery_account (account), extensions
**Evaluator**: 30-day delay before taking effect. Can be updated/cancelled before effective.
**Virtual ops**: changed_recovery_account_operation (when change takes effect)

---

## Witness Operations

### feed_publish_operation (ID: 7)
**Authority**: active (publisher)
**Fields**: publisher (account), exchange_rate (price)
**Validation**: Must be HIVE/HBD pair; both sides > 0
**Evaluator**: Updates witness's published price feed. HF20+: must be HBD base / HIVE quote. Median computation happens in update_median_feed() at end-of-block.

### witness_update_operation (ID: 11)
**Authority**: active (owner)
**Fields**: owner (account), url (string), block_signing_key (public_key), props (legacy_chain_properties), fee (asset)
**Validation**: url 1-2048 chars UTF-8; fee >= 0; props validated (creation_fee, block_size, interest_rate)
**Evaluator**: Creates or updates witness. Setting block_signing_key to null key disables witness.

### witness_set_properties_operation (ID: 42)
**Authority**: custom -- signed by witness signing key (from props["key"])
**Fields**: owner (account), props (flat_map<string, bytes>), extensions
**Validation**: props["key"] required; individual property values validated if present
**Evaluator**: Selective property update. Properties: key, new_signing_key, account_creation_fee, maximum_block_size, hbd_interest_rate, hbd_exchange_rate, url, account_subsidy_budget, account_subsidy_decay. Accepts legacy "sbd_" prefixed names.
**Notes**: HF20+. Does not use owner/active/posting authority at all.

### account_witness_vote_operation (ID: 12)
**Authority**: active (account)
**Fields**: account (account), witness (account), approve (bool)
**Evaluator**: Vote/unvote for a witness. Max 30 witness votes per account (HF2+). Cannot vote if proxy is set or voting rights declined.

### account_witness_proxy_operation (ID: 13)
**Authority**: active (account)
**Fields**: account (account), proxy (account)
**Validation**: proxy != account; proxy valid name if not clearing (empty string clears)
**Evaluator**: Delegates governance vote weight to proxy. Max proxy chain depth 4. Checks for loops. Setting proxy clears individual witness votes. Clearing proxy restores direct voting.
**Virtual ops**: proxy_cleared_operation (on clear/switch)

---

## Market Operations

### limit_order_create_operation (ID: 5)
**Authority**: active (owner)
**Fields**: owner (account), orderid (uint32), amount_to_sell (asset), min_to_receive (asset), fill_or_kill (bool), expiration (time)
**Validation**: HIVE:HBD pair; implied price valid (both > 0)
**Evaluator**: Creates limit order on internal HIVE/HBD DEX. Deducts sell amount. Immediately attempts matching. fill_or_kill reverts if not fully filled. Max 28-day expiration (HF20+).
**Virtual ops**: fill_order_operation (on match); limit_order_cancelled_operation (on cancel/expiry)

### limit_order_create2_operation (ID: 21)
**Authority**: active (owner)
**Fields**: owner (account), orderid (uint32), amount_to_sell (asset), exchange_rate (price), fill_or_kill (bool), expiration (time)
**Validation**: amount_to_sell matches exchange_rate.base symbol; result > 0
**Evaluator**: Same as limit_order_create but takes explicit exchange_rate instead of min_to_receive.

### limit_order_cancel_operation (ID: 6)
**Authority**: active (owner)
**Fields**: owner (account), orderid (uint32)
**Evaluator**: Returns unsold amount to seller. Removes order.
**Virtual ops**: limit_order_cancelled_operation

---

## Governance/DHF Operations

### create_proposal_operation (ID: 44)
**Authority**: active (creator)
**Fields**: creator (account), receiver (account), start_date (time), end_date (time), daily_pay (HBD asset), subject (string), permlink (string), extensions
**Validation**: end_date > start_date; daily_pay HBD >= 0; subject 1-80 chars UTF-8; permlink non-empty
**Evaluator**: Creates DHF proposal. Fee: 10 HBD base + 1 HBD/day beyond 60 days (HF24+). Permlink must point to a post by creator or receiver. End date must be in future (start can be past).
**Virtual ops**: proposal_fee_operation
**Notes**: HF21+.

### update_proposal_votes_operation (ID: 45)
**Authority**: active (voter)
**Fields**: voter (account), proposal_ids (flat_set<int64>), approve (bool), extensions
**Validation**: proposal_ids non-empty, max 5 IDs
**Evaluator**: Batch vote/unvote on proposals. Idempotent. HF28+: voting on nonexistent proposal is hard error. Cannot vote if voting rights declined.
**Notes**: HF21+.

### remove_proposal_operation (ID: 46)
**Authority**: active (proposal_owner)
**Fields**: proposal_owner (account), proposal_ids (flat_set<int64>), extensions
**Validation**: proposal_ids non-empty, max 5 IDs
**Evaluator**: Two-phase removal: immediate physical removal (throttled) then marks remaining as removed. Only creator can remove own proposals.
**Notes**: HF21+.

### update_proposal_operation (ID: 47)
**Authority**: active (creator)
**Fields**: proposal_id (int64), creator (account), daily_pay (HBD asset), subject (string), permlink (string), extensions (may include update_proposal_end_date)
**Validation**: daily_pay HBD >= 0; subject 1-80 chars; proposal_id >= 0
**Evaluator**: Only creator can update. daily_pay can only decrease. End date can only shorten (HF25+ via extension). Subject and permlink freely changeable.
**Notes**: HF24+.

### decline_voting_rights_operation (ID: 36)
**Authority**: owner (account)
**Fields**: account (account), decline (bool)
**Evaluator**: 30-day delay before taking effect. Once effective, can_vote is permanently false -- removes all witness votes, proposal votes, and proxy. decline=false cancels pending request.
**Virtual ops**: declined_voting_rights_operation (when takes effect); proxy_cleared_operation (if had proxy)

---

## Vesting Operations

### transfer_to_vesting_operation (ID: 3)
**Authority**: active (from)
**Fields**: from (account), to (account), amount (HIVE asset)
**Validation**: amount > 0; HIVE only; to can be empty (= self)
**Evaluator**: Power up. Converts HIVE to VESTS at current vesting share price. Cannot vest to treasury (HF21+). Governance power delayed 30 days (HF24+).
**Virtual ops**: transfer_to_vesting_completed_operation (always, includes VESTS received)

### withdraw_vesting_operation (ID: 4)
**Authority**: active (account)
**Fields**: account (account), vesting_shares (VESTS asset)
**Validation**: VESTS type; amount >= 0 (0 = cancel power-down)
**Evaluator**: Sets weekly power-down rate = amount / 13 installments (HF16+; was 104 pre-HF16). Amount 0 cancels. Must have sufficient non-delegated VESTS.
**Virtual ops**: fill_vesting_withdraw_operation (each weekly installment)

### set_withdraw_vesting_route_operation (ID: 20)
**Authority**: active (from_account)
**Fields**: from_account (account), to_account (account), percent (uint16), auto_vest (bool)
**Validation**: percent 0-10000
**Evaluator**: Routes power-down proceeds. auto_vest=true re-vests instead of converting to HIVE. percent=0 removes route. Total across all routes <= 100%. Max HIVE_MAX_WITHDRAW_ROUTES per account. Cannot route to treasury.

### delegate_vesting_shares_operation (ID: 40)
**Authority**: active (delegator)
**Fields**: delegator (account), delegatee (account), vesting_shares (VESTS asset)
**Validation**: delegator != delegatee; VESTS >= 0 (0 = remove delegation)
**Evaluator**: Delegates HP to another account. Decrease/removal creates expiration object for delayed return. Minimum delegation threshold derived from account_creation_fee. Affects voting mana and downvote mana of both parties.
**Notes**: Delegation return period: max(delegation_return_period, min_delegation_time).

---

## Escrow Operations

### escrow_transfer_operation (ID: 27)
**Authority**: active (from)
**Fields**: from (account), to (account), hbd_amount (HBD), hive_amount (HIVE), escrow_id (uint32, default 30), agent (account), fee (HIVE or HBD), json_meta (json), ratification_deadline (time), escrow_expiration (time)
**Validation**: agent != from and agent != to; at least one amount > 0; ratification_deadline < escrow_expiration; fee >= 0
**Evaluator**: Creates escrow. Deducts HIVE + HBD + fee from sender. Requires ratification by both `to` and `agent` before deadline.

### escrow_approve_operation (ID: 31)
**Authority**: active (who)
**Fields**: from (account), to (account), agent (account), who (account), escrow_id (uint32), approve (bool)
**Validation**: who == to or who == agent
**Evaluator**: Approve or reject. Rejection returns all funds to sender. When both approve, agent receives fee.
**Virtual ops**: escrow_approved_operation (both approve); escrow_rejected_operation (rejection)

### escrow_dispute_operation (ID: 28)
**Authority**: active (who)
**Fields**: from (account), to (account), agent (account), who (account), escrow_id (uint32)
**Validation**: who == from or who == to
**Evaluator**: Marks escrow as disputed. Once disputed, only agent can release funds. Must be approved and not expired.

### escrow_release_operation (ID: 29)
**Authority**: active (who)
**Fields**: from (account), to (account), agent (account), who (account), receiver (account), escrow_id (uint32), hbd_amount (HBD), hive_amount (HIVE)
**Validation**: who in {from, to, agent}; receiver in {from, to}; at least one amount > 0
**Evaluator**: Complex permission model: disputed -- only agent releases. Not disputed, not expired -- from releases to to and vice versa. Expired -- either party releases to either. Escrow removed when both balances reach zero.

---

## Custom Operations

### custom_operation (ID: 15)
**Authority**: active (all required_auths)
**Fields**: required_auths (set<account>), id (uint16), data (bytes)
**Validation**: At least 1 auth, max 40
**Evaluator**: Minimal -- only enforces data size limit (8192 bytes, HF26+). No interpreter invoked. Binary payload.

### custom_json_operation (ID: 18)
**Authority**: active (required_auths) + posting (required_posting_auths)
**Fields**: required_auths (set<account>), required_posting_auths (set<account>), id (string max 32), json (json string)
**Validation**: Total auths 1-40; valid JSON
**Evaluator**: Looks up custom_operation_interpreter by id. If registered, delegates. If none, silently succeeds. JSON size <= 8192 bytes (HF26+). Most commonly used custom op.
**Notes**: Well-known IDs: "rc" (RC delegation, protocol-level), "follow", "reblog", "community" (Hivemind), "ssc-mainnet-hive" (Hive Engine).

---

## Virtual Operations

Virtual operations are never broadcast. They are generated internally during block processing to record side effects.

| ID | Name | Generated By | Key Fields |
|----|------|-------------|------------|
| 50 | fill_convert_request | HBD->HIVE conversion completes | owner, requestid, amount_in (HBD), amount_out (HIVE) |
| 51 | author_reward | Comment cashout | author, permlink, hbd/hive/vesting payouts, payout_must_be_claimed |
| 52 | curation_reward | Comment cashout (per curator) | curator, reward (VESTS), author, permlink, payout_must_be_claimed |
| 53 | comment_reward | Comment cashout (summary) | author, permlink, payout (HBD), total/curator/beneficiary payout values |
| 54 | liquidity_reward | Market maker reward | owner, payout (HIVE). **Inactive since HF12.** |
| 55 | interest | HBD balance interest | owner, interest (HBD), is_saved_into_hbd_balance. HF25+: savings only. |
| 56 | fill_vesting_withdraw | Weekly power-down installment | from_account, to_account, withdrawn (VESTS), deposited (HIVE or VESTS) |
| 57 | fill_order | DEX order match | current_owner/orderid/pays, open_owner/orderid/pays |
| 58 | shutdown_witness | Witness removed for missing blocks | owner. **Inactive since HF20.** |
| 59 | fill_transfer_from_savings | Savings withdrawal completes (3-day) | from, to, amount, request_id, memo |
| 60 | hardfork | Hardfork activation | hardfork_id |
| 61 | comment_payout_update | Comment cashout time passes | author, permlink |
| 62 | return_vesting_delegation | Delegation return period expires | account, vesting_shares (VESTS) |
| 63 | comment_benefactor_reward | Comment cashout (per beneficiary) | benefactor, author, permlink, hbd/hive/vesting payouts |
| 64 | producer_reward | Every block (witness reward) | producer, vesting_shares (VESTS or HIVE) |
| 65 | clear_null_account_balance | Funds burned from @null | total_cleared (vector<asset>) |
| 66 | proposal_pay | DHF proposal funded | proposal_id, receiver, payer (treasury), payment (HBD) |
| 67 | dhf_funding | Inflation to treasury | treasury, additional_funds (HBD) |
| 68 | hardfork_hive | HF23 account exclusion | account, treasury, hbd/hive/vests transferred |
| 69 | hardfork_hive_restore | HF24 late airdrop | account, treasury, hbd/hive transferred |
| 70 | delayed_voting | Fresh VESTS governance activation | voter, votes |
| 71 | consolidate_treasury_balance | Old->new treasury merge | total_moved (vector<asset>) |
| 72 | effective_comment_vote | Each vote cast | voter, author, permlink, weight, rshares, pending_payout |
| 73 | ineffective_delete_comment | Pre-HF19 delete with votes | author, permlink |
| 74 | dhf_conversion | HIVE->HBD for treasury | treasury, hive_amount_in, hbd_amount_out |
| 75 | expired_account_notification | Governance votes nullified (inactivity) | account |
| 76 | changed_recovery_account | Recovery account change takes effect | account, old/new_recovery_account |
| 77 | transfer_to_vesting_completed | Every power-up | from_account, to_account, hive_vested, vesting_shares_received |
| 78 | pow_reward | Mining reward (historical) | worker, reward. **Stopped after HF16.** |
| 79 | vesting_shares_split | HF1 VESTS precision increase | owner, before/after split amounts |
| 80 | account_created | All account creation methods | new_account_name, creator, initial_vesting/delegation |
| 81 | fill_collateralized_convert_request | Collateralized conversion completes | owner, requestid, amount_in (HIVE), amount_out (HBD), excess_collateral |
| 82 | system_warning | Various anomalies | message (string) |
| 83 | fill_recurrent_transfer | Recurrent transfer executes | from, to, amount, memo, remaining_executions |
| 84 | failed_recurrent_transfer | Recurrent transfer fails | from, to, amount, consecutive_failures, deleted |
| 85 | limit_order_cancelled | Order cancelled/expired | seller, orderid, amount_back |
| 86 | producer_missed | Witness missed block | producer |
| 87 | proposal_fee | Proposal creation fee | creator, treasury, proposal_id, fee (HBD) |
| 88 | collateralized_convert_immediate_conversion | Immediate HBD from collateralized convert | owner, requestid, hbd_out |
| 89 | escrow_approved | Escrow fully ratified | from, to, agent, escrow_id, fee |
| 90 | escrow_rejected | Escrow rejected/expired ratification | from, to, agent, escrow_id, amounts returned |
| 91 | proxy_cleared | Proxy removed | account, proxy |
| 92 | declined_voting_rights | Voting rights decline takes effect | account |
