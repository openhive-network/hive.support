# Findings: Operations Catalog

## Summary

The Hive blockchain protocol defines **50 regular (broadcastable) operations** (IDs 0–49) and **43 virtual operations** (IDs 50–92, i.e. last_regular+1 through last_regular+43). Operations are encoded as a `fc::static_variant` where the index position determines the numeric operation ID. The protocol also defines a custom operation framework allowing higher-level protocols to embed structured data using `custom_json_operation`. All structs verified directly from source in `libraries/protocol/`.

## Operation Variant Definition

From `operations.hpp`, the complete operation variant:

```cpp
typedef fc::static_variant<
    // --- Regular Operations (0-49) ---
    vote_operation,                             // 0
    comment_operation,                          // 1
    transfer_operation,                         // 2
    transfer_to_vesting_operation,              // 3
    withdraw_vesting_operation,                 // 4
    limit_order_create_operation,               // 5
    limit_order_cancel_operation,               // 6
    feed_publish_operation,                     // 7
    convert_operation,                          // 8
    account_create_operation,                   // 9
    account_update_operation,                   // 10
    witness_update_operation,                   // 11
    account_witness_vote_operation,             // 12
    account_witness_proxy_operation,            // 13
    pow_operation,                              // 14
    custom_operation,                           // 15
    witness_block_approve_operation,            // 16
    delete_comment_operation,                   // 17
    custom_json_operation,                      // 18
    comment_options_operation,                  // 19
    set_withdraw_vesting_route_operation,       // 20
    limit_order_create2_operation,              // 21
    claim_account_operation,                    // 22
    create_claimed_account_operation,           // 23
    request_account_recovery_operation,         // 24
    recover_account_operation,                  // 25
    change_recovery_account_operation,          // 26
    escrow_transfer_operation,                  // 27
    escrow_dispute_operation,                   // 28
    escrow_release_operation,                   // 29
    pow2_operation,                             // 30
    escrow_approve_operation,                   // 31
    transfer_to_savings_operation,              // 32
    transfer_from_savings_operation,            // 33
    cancel_transfer_from_savings_operation,     // 34
    custom_binary_operation,                    // 35
    decline_voting_rights_operation,            // 36
    reset_account_operation,                    // 37
    set_reset_account_operation,                // 38
    claim_reward_balance_operation,             // 39
    delegate_vesting_shares_operation,          // 40
    account_create_with_delegation_operation,   // 41
    witness_set_properties_operation,           // 42
    account_update2_operation,                  // 43
    create_proposal_operation,                  // 44
    update_proposal_votes_operation,            // 45
    remove_proposal_operation,                  // 46
    update_proposal_operation,                  // 47
    collateralized_convert_operation,           // 48
    recurrent_transfer_operation,               // 49

    // --- Virtual Operations (50-93) ---
    fill_convert_request_operation,             // 50
    author_reward_operation,                    // 51
    curation_reward_operation,                  // 52
    comment_reward_operation,                   // 53
    liquidity_reward_operation,                 // 54
    interest_operation,                         // 55
    fill_vesting_withdraw_operation,            // 56
    fill_order_operation,                       // 57
    shutdown_witness_operation,                 // 58
    fill_transfer_from_savings_operation,       // 59
    hardfork_operation,                         // 60
    comment_payout_update_operation,            // 61
    return_vesting_delegation_operation,        // 62
    comment_benefactor_reward_operation,        // 63
    producer_reward_operation,                  // 64
    clear_null_account_balance_operation,       // 65
    proposal_pay_operation,                     // 66
    dhf_funding_operation,                      // 67
    hardfork_hive_operation,                    // 68
    hardfork_hive_restore_operation,            // 69
    delayed_voting_operation,                   // 70
    consolidate_treasury_balance_operation,     // 71
    effective_comment_vote_operation,           // 72
    ineffective_delete_comment_operation,       // 73
    dhf_conversion_operation,                   // 74
    expired_account_notification_operation,     // 75
    changed_recovery_account_operation,         // 76
    transfer_to_vesting_completed_operation,    // 77
    pow_reward_operation,                       // 78
    vesting_shares_split_operation,             // 79
    account_created_operation,                  // 80
    fill_collateralized_convert_request_operation, // 81
    system_warning_operation,                   // 82
    fill_recurrent_transfer_operation,          // 83
    failed_recurrent_transfer_operation,        // 84
    limit_order_cancelled_operation,            // 85
    producer_missed_operation,                  // 86
    proposal_fee_operation,                     // 87
    collateralized_convert_immediate_conversion_operation, // 88
    escrow_approved_operation,                  // 89
    escrow_rejected_operation,                  // 90
    proxy_cleared_operation,                    // 91
    declined_voting_rights_operation            // 92
> operation;
```

**Note:** Virtual operations can be compiled out via `HIVE_PROTOCOL_SKIP_VOPS` preprocessor flag for lighter protocol-only builds.

## Base Operation Architecture

From `base.hpp`:

```cpp
struct base_operation {
    void get_required_authorities(vector<authority>&) const {}
    void get_required_active_authorities(flat_set<account_name_type>&) const {}
    void get_required_posting_authorities(flat_set<account_name_type>&) const {}
    void get_required_owner_authorities(flat_set<account_name_type>&) const {}
    void get_required_witness_signatures(flat_set<account_name_type>&) const {}
    bool is_virtual() const { return false; }
    void validate() const {}
};

struct virtual_operation : public base_operation {
    bool is_virtual() const { return true; }
    void validate() const { /* always asserts — virtual ops are never validated */ }
};
```

Operations override `get_required_*_authorities()` to declare which authority level(s) are needed. The authority system supports five levels: **owner**, **active**, **posting**, **witness**, and custom **authority** objects.

---

## Regular Operations (Broadcastable)

### Social/Content Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 0 | `vote_operation` | `voter`: account_name, `author`: account_name, `permlink`: string, `weight`: int16_t | **posting** (voter) | Weight range: -10000 to 10000 (HIVE percent) |
| 1 | `comment_operation` | `parent_author`: account_name, `parent_permlink`: string, `author`: account_name, `permlink`: string, `title`: string, `body`: string, `json_metadata`: json_string | **posting** (author) | Used for both posts (empty parent_author) and comments |
| 17 | `delete_comment_operation` | `author`: account_name, `permlink`: string | **posting** (author) | Prior to HF19, ignored on comments with net positive votes |
| 19 | `comment_options_operation` | `author`: account_name, `permlink`: string, `max_accepted_payout`: asset (HBD, default 1B), `percent_hbd`: uint16_t (default 100%), `allow_votes`: bool, `allow_curation_rewards`: bool, `extensions`: comment_options_extensions_type | **posting** (author) | Extensions can include `comment_payout_beneficiaries` (max HIVE_BENEFICIARY_LIMIT-1 entries, sorted by account name, total weight <= 100%) |

### Transfer/Financial Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 2 | `transfer_operation` | `from`: account_name, `to`: account_name, `amount`: asset, `memo`: string | **active** (from) | HIVE or HBD only (no VESTS). Memo max HIVE_MAX_MEMO_SIZE. |
| 3 | `transfer_to_vesting_operation` | `from`: account_name, `to`: account_name, `amount`: asset | **active** (from) | Power up. Amount must be HIVE. `to` can be empty (self). |
| 4 | `withdraw_vesting_operation` | `account`: account_name, `vesting_shares`: asset | **active** (account) | Power down. Amount must be VESTS. Set to 0 to cancel. |
| 20 | `set_withdraw_vesting_route_operation` | `from_account`: account_name, `to_account`: account_name, `percent`: uint16_t, `auto_vest`: bool | **active** (from_account) | Percent 0–10000. auto_vest re-vests instead of converting to HIVE. |
| 32 | `transfer_to_savings_operation` | `from`: account_name, `to`: account_name, `amount`: asset, `memo`: string | **active** (from) | HIVE or HBD. |
| 33 | `transfer_from_savings_operation` | `from`: account_name, `request_id`: uint32_t, `to`: account_name, `amount`: asset, `memo`: string | **active** (from) | 3-day waiting period. HIVE or HBD. |
| 34 | `cancel_transfer_from_savings_operation` | `from`: account_name, `request_id`: uint32_t | **active** (from) | Cancels pending savings withdrawal. |
| 39 | `claim_reward_balance_operation` | `account`: account_name, `reward_hive`: asset, `reward_hbd`: asset, `reward_vests`: asset | **posting** (account) | Claims pending author/curation rewards. At least one amount must be > 0. |
| 49 | `recurrent_transfer_operation` | `from`: account_name, `to`: account_name, `amount`: asset, `memo`: string, `recurrence`: uint16_t, `executions`: uint16_t, `extensions`: recurrent_transfer_extensions_type | **active** (from) | Since HF25. Recurrence in hours (min HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE). Executions >= 2. Amount 0 deletes. Extensions: `recurrent_transfer_pair_id` (uint8_t). |

### Market Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 5 | `limit_order_create_operation` | `owner`: account_name, `orderid`: uint32_t, `amount_to_sell`: asset, `min_to_receive`: asset, `fill_or_kill`: bool, `expiration`: time_point_sec | **active** (owner) | Internal HIVE<->HBD market only. |
| 6 | `limit_order_cancel_operation` | `owner`: account_name, `orderid`: uint32_t | **active** (owner) | |
| 21 | `limit_order_create2_operation` | `owner`: account_name, `orderid`: uint32_t, `amount_to_sell`: asset, `exchange_rate`: price, `fill_or_kill`: bool, `expiration`: time_point_sec | **active** (owner) | Same as limit_order_create but serializes price directly. |

### Conversion Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 8 | `convert_operation` | `owner`: account_name, `requestid`: uint32_t, `amount`: asset | **active** (owner) | HBD->HIVE only. Converts after HIVE_CONVERSION_DELAY (3.5 days). |
| 48 | `collateralized_convert_operation` | `owner`: account_name, `requestid`: uint32_t, `amount`: asset | **active** (owner) | Since HF25. HIVE->HBD. HBD delivered immediately; excess HIVE collateral returned after HIVE_COLLATERALIZED_CONVERSION_DELAY. |

### Account Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 9 | `account_create_operation` | `fee`: asset, `creator`: account_name, `new_account_name`: account_name, `owner`: authority, `active`: authority, `posting`: authority, `memo_key`: public_key, `json_metadata`: json_string | **active** (creator) | Fee must be HIVE, <= HIVE_MAX_ACCOUNT_CREATION_FEE. |
| 10 | `account_update_operation` | `account`: account_name, `owner`: optional\<authority\>, `active`: optional\<authority\>, `posting`: optional\<authority\>, `memo_key`: public_key, `json_metadata`: json_string | **owner** if owner field is set; otherwise **active** (account) | |
| 22 | `claim_account_operation` | `creator`: account_name, `fee`: asset, `extensions`: extensions_type | **active** (creator) | Since HF20. Fee in HIVE (or 0 to use RC). Claims a "creation ticket". |
| 23 | `create_claimed_account_operation` | `creator`: account_name, `new_account_name`: account_name, `owner`: authority, `active`: authority, `posting`: authority, `memo_key`: public_key, `json_metadata`: json_string, `extensions`: extensions_type | **active** (creator) | Since HF20. Uses a previously claimed creation ticket. |
| 41 | `account_create_with_delegation_operation` | `fee`: asset, `delegation`: asset, `creator`: account_name, `new_account_name`: account_name, `owner`: authority, `active`: authority, `posting`: authority, `memo_key`: public_key, `json_metadata`: json_string, `extensions`: extensions_type | **active** (creator) | **Deprecated at HF20.** Fee HIVE, delegation VESTS. |
| 43 | `account_update2_operation` | `account`: account_name, `owner`: optional\<authority\>, `active`: optional\<authority\>, `posting`: optional\<authority\>, `memo_key`: optional\<public_key\>, `json_metadata`: json_string, `posting_json_metadata`: json_string, `extensions`: extensions_type | **owner** if owner set; **active** if active/posting/memo_key/json_metadata set (without owner); **posting** if only posting_json_metadata set | Since HF21. Adds `posting_json_metadata` and makes `memo_key` optional. Three-tier authority depending on which fields are populated. |

### Account Recovery Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 24 | `request_account_recovery_operation` | `recovery_account`: account_name, `account_to_recover`: account_name, `new_owner_authority`: authority, `extensions`: extensions_type | **active** (recovery_account) | Since HF14. Creates recovery request valid for 24 hours. |
| 25 | `recover_account_operation` | `account_to_recover`: account_name, `new_owner_authority`: authority, `recent_owner_authority`: authority, `extensions`: extensions_type | **custom**: must satisfy both `new_owner_authority` AND `recent_owner_authority` | Must match a pending recovery request. Recent authority valid for 30 days. |
| 26 | `change_recovery_account_operation` | `account_to_recover`: account_name, `new_recovery_account`: account_name, `extensions`: extensions_type | **owner** (account_to_recover) | 30-day delay before taking effect. |

### Escrow Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 27 | `escrow_transfer_operation` | `from`: account_name, `to`: account_name, `hbd_amount`: asset, `hive_amount`: asset, `escrow_id`: uint32_t (default 30), `agent`: account_name, `fee`: asset, `json_meta`: json_string, `ratification_deadline`: time_point_sec, `escrow_expiration`: time_point_sec | **active** (from) | Agent must be a third party. Fee is HIVE or HBD. At least one of hbd/hive amount must be > 0. |
| 28 | `escrow_dispute_operation` | `from`: account_name, `to`: account_name, `agent`: account_name, `who`: account_name, `escrow_id`: uint32_t | **active** (who) | `who` must be `from` or `to`. |
| 29 | `escrow_release_operation` | `from`: account_name, `to`: account_name, `agent`: account_name, `who`: account_name, `receiver`: account_name, `escrow_id`: uint32_t, `hbd_amount`: asset, `hive_amount`: asset | **active** (who) | `who` must be from/to/agent. `receiver` must be from or to. Complex permission scheme depending on dispute/expiration state. |
| 31 | `escrow_approve_operation` | `from`: account_name, `to`: account_name, `agent`: account_name, `who`: account_name, `escrow_id`: uint32_t, `approve`: bool | **active** (who) | `who` must be `to` or `agent`. |

### Witness Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 7 | `feed_publish_operation` | `publisher`: account_name, `exchange_rate`: price | **active** (publisher) | Price feed: HIVE/HBD or HBD/HIVE pair. Only top N witnesses' feeds used. |
| 11 | `witness_update_operation` | `owner`: account_name, `url`: string, `block_signing_key`: public_key, `props`: legacy_chain_properties, `fee`: asset | **active** (owner) | Setting block_signing_key to null key disables/removes witness. URL max HIVE_MAX_WITNESS_URL_LENGTH. |
| 12 | `account_witness_vote_operation` | `account`: account_name, `witness`: account_name, `approve`: bool | **active** (account) | |
| 13 | `account_witness_proxy_operation` | `account`: account_name, `proxy`: account_name | **active** (account) | Setting proxy to HIVE_PROXY_TO_SELF_ACCOUNT ("") clears proxy. Cannot proxy to self. |
| 16 | `witness_block_approve_operation` | `witness`: account_name, `block_id`: block_id_type | **witness** signature (witness) | Used internally for block signing validation. |
| 42 | `witness_set_properties_operation` | `owner`: account_name, `props`: flat_map\<string, vector\<char\>\>, `extensions`: extensions_type | **custom**: authority(1, signing_key, 1) — signed by the witness signing key found in `props["key"]` | Since HF20. Properties include: key, new_signing_key, account_creation_fee, maximum_block_size, hbd_interest_rate, hbd_exchange_rate, url, account_subsidy_budget, account_subsidy_decay. |

**`legacy_chain_properties`** (used in witness_update_operation):
- `account_creation_fee`: legacy_hive_asset (min HIVE_MIN_ACCOUNT_CREATION_FEE)
- `maximum_block_size`: uint32_t (min HIVE_MIN_BLOCK_SIZE_LIMIT, max HIVE_MAX_BLOCK_SIZE)
- `hbd_interest_rate`: uint16_t (0–10000)

### Proof of Work Operations (Historical/Deprecated)

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 14 | `pow_operation` | `worker_account`: account_name, `block_id`: block_id_type, `nonce`: uint64_t, `work`: pow, `props`: legacy_chain_properties | None (proof of work IS the authority) | **Deprecated at HF13.** |
| 30 | `pow2_operation` | `work`: pow2_work (variant: pow2 \| equihash_pow), `new_owner_key`: optional\<public_key\>, `props`: legacy_chain_properties | **active** (worker) if `new_owner_key` is NOT set; custom authority(1, new_owner_key, 1) if set | **Disabled at HF17** (mining disabled). |

### Custom Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 15 | `custom_operation` | `required_auths`: flat_set\<account_name\>, `id`: uint16_t, `data`: vector\<char\> | **active** (all required_auths) | Binary payload. At least 1 required auth. |
| 18 | `custom_json_operation` | `required_auths`: flat_set\<account_name\>, `required_posting_auths`: flat_set\<account_name\>, `id`: custom_id_type (max 32 chars), `json`: json_string | **active** (required_auths) + **posting** (required_posting_auths) | Human-readable JSON. At least 1 auth total. Most commonly used custom op. |
| 35 | `custom_binary_operation` | `required_owner_auths`: flat_set\<account_name\>, `required_active_auths`: flat_set\<account_name\>, `required_posting_auths`: flat_set\<account_name\>, `required_auths`: vector\<authority\>, `id`: custom_id_type, `data`: vector\<char\> | **owner** + **active** + **posting** + custom **authorities** (as specified) | Binary payload. Supports all authority levels. Data max HIVE_CUSTOM_OP_DATA_MAX_LENGTH. |

### Governance/Proposal Operations (DHF)

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 44 | `create_proposal_operation` | `creator`: account_name, `receiver`: account_name, `start_date`: time_point_sec, `end_date`: time_point_sec, `daily_pay`: asset, `subject`: string, `permlink`: string, `extensions`: extensions_type | **active** (creator) | Since HF21. Daily pay in HBD. Permlink must exist (posted by creator or receiver). |
| 45 | `update_proposal_votes_operation` | `voter`: account_name, `proposal_ids`: flat_set_ex\<int64_t\>, `approve`: bool, `extensions`: extensions_type | **active** (voter) | Since HF21. Vote for/against multiple proposals. Nonexisting IDs trigger error. |
| 46 | `remove_proposal_operation` | `proposal_owner`: account_name, `proposal_ids`: flat_set_ex\<int64_t\>, `extensions`: extensions_type | **active** (proposal_owner) | Since HF21. Only owner can remove. Nonexisting IDs trigger error. |
| 47 | `update_proposal_operation` | `proposal_id`: int64_t, `creator`: account_name, `daily_pay`: asset, `subject`: string, `permlink`: string, `extensions`: update_proposal_extensions_type | **active** (creator) | Since HF24. daily_pay can only be lowered. Extensions can include `update_proposal_end_date`. |

### Vesting Delegation Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 40 | `delegate_vesting_shares_operation` | `delegator`: account_name, `delegatee`: account_name, `vesting_shares`: asset | **active** (delegator) | VESTS only. Cannot delegate to self. 0 removes delegation (with return period). |

### Voting Rights Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 36 | `decline_voting_rights_operation` | `account`: account_name, `decline`: bool | **owner** (account) | 30-day waiting period (HIVE_OWNER_AUTH_RECOVERY_PERIOD). |

### Placeholder/Disabled Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 37 | `reset_account_operation` | `reset_account`: account_name, `account_to_reset`: account_name, `new_owner_authority`: authority | **active** (reset_account) | **DISABLED.** validate() always asserts. "Placeholder for potential new operation." |
| 38 | `set_reset_account_operation` | `account`: account_name, `current_reset_account`: account_name, `reset_account`: account_name | **owner** if current_reset_account is set; **posting** otherwise | **DISABLED.** validate() always asserts. "Placeholder for potential new operation." |

---

## Virtual Operations

Virtual operations are **never broadcast** by users. They are generated internally by the chain during block processing to record side effects. All inherit from `virtual_operation` (which always returns `is_virtual() == true` and asserts on `validate()`).

### Reward/Payout Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 51 | `author_reward_operation` | `author`, `permlink`, `hbd_payout` (HBD), `hive_payout` (HIVE), `vesting_payout` (VESTS), `curators_vesting_payout` (VESTS), `payout_must_be_claimed` (bool) | Comment cashout when comment has nonzero reward |
| 52 | `curation_reward_operation` | `curator`, `reward` (VESTS), `author`, `permlink`, `payout_must_be_claimed` (bool) | Comment cashout — one per curator with nonzero reward |
| 53 | `comment_reward_operation` | `author`, `permlink`, `payout` (HBD), `author_rewards` (share_type), `total_payout_value` (HBD), `curator_payout_value` (HBD), `beneficiary_payout_value` (HBD) | Comment cashout — informational summary, no transfers |
| 63 | `comment_benefactor_reward_operation` | `benefactor`, `author`, `permlink`, `hbd_payout` (HBD), `hive_payout` (HIVE), `vesting_payout` (VESTS), `payout_must_be_claimed` (bool) | Comment cashout — per beneficiary defined in comment_options |
| 61 | `comment_payout_update_operation` | `author`, `permlink` | Comment cashout time passes (even with zero rewards) |
| 54 | `liquidity_reward_operation` | `owner`, `payout` (HIVE) | Market maker reward. **No longer active after HF12.** |
| 64 | `producer_reward_operation` | `producer`, `vesting_shares` (VESTS or HIVE) | Every block — witness receives block production reward |
| 78 | `pow_reward_operation` | `worker`, `reward` (VESTS or HIVE) | pow/pow2 execution — mining reward. **Stopped after HF16.** |

### Conversion Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 50 | `fill_convert_request_operation` | `owner`, `requestid` (uint32_t), `amount_in` (HBD), `amount_out` (HIVE) | convert_operation completes after delay |
| 81 | `fill_collateralized_convert_request_operation` | `owner`, `requestid` (uint32_t), `amount_in` (HIVE), `amount_out` (HBD), `excess_collateral` (HIVE) | collateralized_convert completes after delay |
| 88 | `collateralized_convert_immediate_conversion_operation` | `owner`, `requestid` (uint32_t), `hbd_out` (HBD) | collateralized_convert_operation execution — immediate HBD |
| 74 | `dhf_conversion_operation` | `treasury`, `hive_amount_in` (HIVE), `hbd_amount_out` (HBD) | HIVE transferred to treasury or daily treasury maintenance |

### Transfer/Withdrawal Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 55 | `interest_operation` | `owner`, `interest` (HBD), `is_saved_into_hbd_balance` (bool) | HBD balance modification triggers interest. After HF25: savings only. |
| 56 | `fill_vesting_withdraw_operation` | `from_account`, `to_account`, `withdrawn` (VESTS), `deposited` (HIVE or VESTS) | Power down batch — each active withdraw route per period |
| 59 | `fill_transfer_from_savings_operation` | `from`, `to`, `amount` (HIVE or HBD), `request_id` (uint32_t), `memo` | Savings withdrawal delay passes |
| 77 | `transfer_to_vesting_completed_operation` | `from_account`, `to_account`, `hive_vested` (HIVE), `vesting_shares_received` (VESTS) | Every transfer_to_vesting_operation — supplements with VESTS received |
| 83 | `fill_recurrent_transfer_operation` | `from`, `to`, `amount` (HIVE or HBD), `memo`, `remaining_executions` (uint16_t), `extensions` | Recurrent transfer executes successfully |
| 84 | `failed_recurrent_transfer_operation` | `from`, `to`, `amount`, `memo`, `consecutive_failures` (uint8_t), `remaining_executions` (uint16_t), `deleted` (bool), `extensions` | Recurrent transfer fails (insufficient funds). `deleted=true` if discontinued. |

### Market Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 57 | `fill_order_operation` | `current_owner`, `current_orderid`, `current_pays` (HIVE or HBD), `open_owner`, `open_orderid`, `open_pays` (HBD or HIVE) | Order matching on internal market |
| 85 | `limit_order_cancelled_operation` | `seller`, `orderid` (uint32_t), `amount_back` (HIVE or HBD) | Order cancelled (explicit, remainder too small, or expired) |

### Governance Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 66 | `proposal_pay_operation` | `proposal_id` (uint32_t), `receiver`, `payer` (treasury), `payment` (HBD) | Proposal maintenance — funded proposals receive payment |
| 67 | `dhf_funding_operation` | `treasury`, `additional_funds` (HBD) | Proposal maintenance period — inflation directed to treasury |
| 87 | `proposal_fee_operation` | `creator`, `treasury`, `proposal_id` (uint32_t), `fee` (HBD) | create_proposal_operation execution — fee paid |
| 70 | `delayed_voting_operation` | `voter`, `votes` (ushare_type) | Grace period ends for fresh VESTS governance vote activation |
| 75 | `expired_account_notification_operation` | `account` | User's governance votes nullified due to inactivity |
| 91 | `proxy_cleared_operation` | `account`, `proxy` | Proxy removed (explicit, declined voting, or governance vote expiration) |
| 92 | `declined_voting_rights_operation` | `account` | decline_voting_rights_operation takes effect after 30-day wait |

### Witness Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 58 | `shutdown_witness_operation` | `owner` | Witness removed for missing all blocks for a day. **No longer active after HF20.** |
| 86 | `producer_missed_operation` | `producer` | Witness failed to produce scheduled block |

### Delegation Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 62 | `return_vesting_delegation_operation` | `account`, `vesting_shares` (VESTS) | Delegation return period passes — VESTS returned to delegator |

### Voting Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 72 | `effective_comment_vote_operation` | `voter`, `author`, `permlink`, `weight` (uint64_t), `rshares` (int64_t), `total_vote_weight` (uint64_t), `pending_payout` (HBD) | Each effective vote cast (before cashout) |
| 73 | `ineffective_delete_comment_operation` | `author`, `permlink` | delete_comment ignored (pre-HF19, had net positive votes) |

### Account Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 80 | `account_created_operation` | `new_account_name`, `creator`, `initial_vesting_shares` (VESTS), `initial_delegation` (VESTS) | All account creation methods (genesis, operations, PoW) |
| 76 | `changed_recovery_account_operation` | `account`, `old_recovery_account`, `new_recovery_account` | change_recovery_account wait period passes |

### Escrow Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 89 | `escrow_approved_operation` | `from`, `to`, `agent`, `escrow_id` (uint32_t), `fee` (HIVE or HBD) | Both agent and to approved escrow — agent receives fee |
| 90 | `escrow_rejected_operation` | `from`, `to`, `agent`, `escrow_id`, `hbd_amount` (HBD), `hive_amount` (HIVE), `fee` | Escrow rejected or ratification deadline passed — all funds returned to from |

### System/Hardfork Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 60 | `hardfork_operation` | `hardfork_id` (uint32_t) | Each hardfork activation |
| 65 | `clear_null_account_balance_operation` | `total_cleared`: vector\<asset\> | Nonzero assets burned from 'null' account |
| 71 | `consolidate_treasury_balance_operation` | `total_moved`: vector\<asset\> | Assets moved from old treasury ('steem.dao') to new ('hive.fund') |
| 68 | `hardfork_hive_operation` | `account`, `treasury`, `other_affected_accounts`: vector\<account_name\>, `hbd_transferred` (HBD), `hive_transferred` (HIVE), `vests_converted` (VESTS), `total_hive_from_vests` (HIVE) | HF23 — per account excluded from HIVE airdrop |
| 69 | `hardfork_hive_restore_operation` | `account`, `treasury`, `hbd_transferred` (HBD), `hive_transferred` (HIVE) | HF24 — late airdrop for accounts that won appeal |
| 79 | `vesting_shares_split_operation` | `owner`, `vesting_shares_before_split` (VESTS), `vesting_shares_after_split` (VESTS) | HF1 — VESTS precision increase (×1,000,000) |
| 82 | `system_warning_operation` | `message` (string) | Various: unknown witness type, collateral shortfall, HBD hard cap price correction, witness block size change |

---

## Custom Operations Framework

### Architecture

Custom operations provide an extensibility mechanism for building higher-level protocols on Hive. The key custom operation is `custom_json_operation` (ID 18), which carries:
- `id`: A string identifier (max 32 characters) naming the protocol
- `json`: The JSON payload

### Built-in Custom Operation: RC Delegation

The only protocol-level custom operation defined in the Hive core protocol is **RC (Resource Credits) delegation**, defined in `hive_custom_operations.hpp`:

```cpp
struct delegate_rc_operation : public base_operation {
    account_name_type             from;
    flat_set<account_name_type>   delegatees;
    int64_t                       max_rc = 0;
    extensions_type               extensions;
    // Authority: posting (from)
};

typedef fc::static_variant<delegate_rc_operation> rc_custom_operation;
#define HIVE_RC_CUSTOM_OPERATION_ID "rc"
```

This is broadcast as a `custom_json_operation` with `id = "rc"` and the operation serialized as JSON in the `json` field.

### Well-Known Custom JSON IDs (Application Layer)

While not defined in the protocol code, these are widely used in the ecosystem:
- `"rc"` — RC delegation (the only protocol-defined one)
- `"follow"` — Follow/mute operations (Hivemind)
- `"reblog"` — Reblog/resteem operations (Hivemind)
- `"community"` — Community operations (Hivemind)
- `"notify"` — Notification settings
- `"ssc-mainnet-hive"` — Hive Engine sidechain
- `"sm_*"` — Splinterlands game operations

### Authority Model for Custom Operations

The three custom operation types offer different authority flexibility:

| Operation | Authority Levels | Payload |
|-----------|-----------------|---------|
| `custom_operation` | active only | binary |
| `custom_json_operation` | active + posting | JSON (validated) |
| `custom_binary_operation` | owner + active + posting + custom authorities | binary (max HIVE_CUSTOM_OP_DATA_MAX_LENGTH) |

---

## Operation Lifecycle and Hardfork History

### Genesis Operations (Available Since Block 1)
IDs 0–16: vote, comment, transfer, transfer_to_vesting, withdraw_vesting, limit_order_create, limit_order_cancel, feed_publish, convert, account_create, account_update, witness_update, account_witness_vote, account_witness_proxy, pow, custom, witness_block_approve

### Added in Early Hardforks
- **HF14** (block 5,137,542): request_account_recovery, recover_account, change_recovery_account, escrow operations (transfer/dispute/release/approve), custom_binary, delete_comment (behavior change)
- **HF16** (block 7,353,249): Mining rewards stopped (pow_reward_operation ceases)
- **HF17** (block 10,629,455): pow2 disabled, comment_options, set_withdraw_vesting_route, limit_order_create2, decline_voting_rights, claim_reward_balance, delegate_vesting_shares, savings operations, custom_json added earlier but significantly modified

### Added in Later Hardforks
- **HF20** (block 26,256,743): claim_account, create_claimed_account, witness_set_properties. account_create_with_delegation **deprecated**.
- **HF21** (block 35,921,786): account_update2, create_proposal, update_proposal_votes, remove_proposal (DHF system)
- **HF24** (block 47,797,680): update_proposal
- **HF25** (block 55,235,767): collateralized_convert, recurrent_transfer

### Currently Disabled/Deprecated
- `pow_operation` (ID 14): Deprecated at HF13
- `pow2_operation` (ID 30): Disabled at HF17
- `reset_account_operation` (ID 37): Never used, validate() always fails
- `set_reset_account_operation` (ID 38): Never used, validate() always fails
- `account_create_with_delegation_operation` (ID 41): Deprecated at HF20

---

## Market Operation Classification

From `operations.cpp`, only these operations are classified as "market operations" for purposes like rate limiting:
- `limit_order_create_operation`
- `limit_order_cancel_operation`
- `transfer_operation`
- `transfer_to_vesting_operation`

## Effective Operation Classification

All operations are considered "effective" except `fill_vesting_withdraw_operation` when it represents an empty implied route (withdrawn amount is 0).

---

## Key Discoveries

1. **Numeric IDs are strictly positional**: The operation ID is simply the index in the variant. Adding or reordering operations would break consensus (comment at top of operations.hpp: "do not change the order of any operations prior to the virtual operations or it will trigger a hardfork").

2. **Three-tier authority in account_update2**: This is the only operation with three distinct authority level paths — owner, active, or posting — depending on which fields are populated. This allows profile metadata updates with just posting authority.

3. **`recover_account_operation` has unique dual-authority requirement**: Must satisfy BOTH `new_owner_authority` AND `recent_owner_authority`. This is the only operation requiring two separate authority objects simultaneously.

4. **`witness_set_properties_operation` uses signing key authority**: Does not use owner/active/posting at all. Instead constructs a custom `authority(1, signing_key, 1)` from the key in `props["key"]`. If the key is missing, it requires the impossible null account authority.

5. **Escrow default ID is 30**: Not 0 as might be expected. `escrow_id` defaults to 30 in all escrow operations.

6. **reset_account and set_reset_account are dead code**: Both operations exist in the variant (IDs 37-38) to preserve ID numbering, but their validate() functions always assert. They were reserved as "placeholder for potential new operation" and never implemented.

7. **Virtual operation IDs are contiguous but can be compiled out**: The `HIVE_PROTOCOL_SKIP_VOPS` flag removes virtual operations from the variant entirely, used in protocol-only builds.

8. **`payout_must_be_claimed` flag**: Several reward virtual operations include this boolean, indicating whether the recipient must manually claim rewards via `claim_reward_balance_operation`.

9. **pow_operation has no authority requirement**: The proof of work itself serves as authentication — `get_required_active_authorities()` is overridden to be empty.

10. **`flat_set_ex` for proposal IDs**: DHF operations use a custom `flat_set_ex<int64_t>` that enforces sorted-unique ordering during deserialization (items must be strictly increasing).

---

## Code References

| Component | File | Key Content |
|-----------|------|-------------|
| Operation variant typedef | `include/hive/protocol/operations.hpp:15-125` | Complete operation list with IDs |
| Base operation class | `include/hive/protocol/base.hpp:13-29` | Authority method signatures |
| Regular operation structs | `include/hive/protocol/hive_operations.hpp` | All 46 regular op definitions |
| DHF operation structs | `include/hive/protocol/dhf_operations.hpp` | 4 proposal operations |
| Virtual operation structs | `include/hive/protocol/hive_virtual_operations.hpp` | All 43 virtual op definitions |
| Custom operation framework | `include/hive/protocol/hive_custom_operations.hpp` | RC delegation custom op |
| Validate implementations | `hive_operations.cpp` | All validate() logic |
| Market/virtual classification | `operations.cpp` | is_market_operation, is_virtual_operation |
| Comment types | `include/hive/protocol/comment_types.hpp` | beneficiary_route_type |
| Recurrent transfer types | `include/hive/protocol/types.hpp:151-161` | recurrent_transfer_pair_id, extensions |
| Hardfork blocks | `include/hive/protocol/hardfork_block.hpp` | All hardfork activation blocks |
| FC_REFLECT serialization | Bottom of hive_operations.hpp, hive_virtual_operations.hpp, dhf_operations.hpp | Field serialization order |

---

## Discrepancies and Potential Issues

1. **`comment_reward_operation` has TODO comment**: Field `author_rewards` is `share_type` (raw satoshi) with comment "TODO: turn into HIVE_asset". This inconsistency means it's not a proper typed asset.

2. **`hardfork_hive_restore_operation` known bug**: Comment in source notes the late airdrop "did not apply properly since HIVE that the accounts should receive did not account for HIVE from converted VESTS" with question "[how was it resolved?]".

3. **Escrow default ID inconsistency**: The default `escrow_id = 30` seems arbitrary and is not documented as to why 30 was chosen rather than 0.

4. **`witness_set_properties_operation` accepts both old and new property names**: Code checks for both `"sbd_interest_rate"` and `"hbd_interest_rate"`, and both `"sbd_exchange_rate"` and `"hbd_exchange_rate"` — legacy Steem naming backward compatibility.

5. **`fill_vesting_withdraw_operation.deposited` is untyped `asset`**: Can be HIVE or VESTS depending on the route's `auto_vest` setting, unlike most virtual ops which use typed assets.

6. **`producer_reward_operation.vesting_shares` is untyped `asset`**: Can be VESTS or HIVE (HIVE only during first 30 days after genesis).

---

## Open Questions

1. **When exactly were operations 17-21 introduced?** The variant ordering suggests they were added after the genesis set (0-16), but the exact hardfork for each is not always gated in the evaluator (some rely on implicit consensus changes).

2. **What is the maximum number of operations per transaction?** The protocol defines `HIVE_MAX_TRANSACTION_SIZE` (64KB) but not an explicit operation count limit.

3. **How does the RC system price each operation?** Resource sizing is in `rc/resource_sizes.cpp` but the per-operation RC cost model needs chain-layer analysis (Part 08).

4. **What custom_json IDs does the chain itself interpret?** Beyond "rc", does the core chain process any other custom_json IDs, or are all others purely application layer?

5. **What is the `smt_nai_space` check in limit_order_create validate()?** The limit order validation allows SMT (Smart Media Token) NAI space assets paired with HIVE, suggesting SMT market support was partially coded but never activated.
