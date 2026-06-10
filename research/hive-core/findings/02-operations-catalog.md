# Findings: Operations Catalog

## Summary

The Hive blockchain protocol defines **50 regular (broadcastable) operations** (IDs 0–49) and **43 virtual operations** (IDs 50–92, i.e. `last_regular+1` … `last_regular+43`). Operations are encoded as an `fc::static_variant` where the index position is the numeric operation ID; positional stability is consensus-critical. The protocol also defines a custom-operation framework (`custom_operation`, `custom_json_operation`, `custom_binary_operation`) for higher-level protocols to embed structured data. All structs verified directly from `libraries/protocol/` at commit `10ac0ce94f`.

Three facts that span the protocol *and* chain layers are worth stating up front, because the protocol-layer structs alone are misleading without them:

1. **Of the three custom-operation types, only `custom_json_operation` with `id == "rc"` is acted upon by consensus.** `custom_operation` (15) is inert except for a size cap; `custom_binary_operation` (35) is **hard-disabled** — its evaluator unconditionally throws.
2. **There is no central pre-hardfork gate for new operations.** Each evaluator self-guards. Twelve operations carry an explicit blocking `has_hardfork(...)` guard; the rest became usable when their defining release shipped (any historical guard has since been removed, per standard practice).
3. **There is no per-transaction operation-count limit** — only "≥ 1 operation" and the 64 KiB transaction-size cap.

> Scope note: this part catalogs the *protocol-layer* definition of every operation (fields, types, declared authority, `validate()`), plus the *minimal* chain-layer facts needed to state whether/when an operation is usable. Full evaluator state-change semantics are Part 04; RC cost pricing is Part 08; hardfork block heights are Part 09.

## Operation Variant Definition

From `operations.hpp:12-125`, the complete operation variant (numeric ID = variant index):

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

#ifndef HIVE_PROTOCOL_SKIP_VOPS
    // --- Virtual Operations (50-92) ---
    fill_convert_request_operation,             // 50  (last_regular + 1)
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
    declined_voting_rights_operation            // 92  (last_regular + 43)
#endif // HIVE_PROTOCOL_SKIP_VOPS
> operation;
```

**Note:** Virtual operations can be compiled out via the `HIVE_PROTOCOL_SKIP_VOPS` preprocessor flag (`operations.hpp:76,124`) for lighter protocol-only builds. The comment at `operations.hpp:12-14` warns: *"do not change the order of any operations prior to the virtual operations or it will trigger a hardfork."*

## Base Operation Architecture

From `base.hpp:13-29`:

```cpp
struct base_operation {
    void get_required_authorities( vector<authority>& )const {}
    void get_required_active_authorities( flat_set<account_name_type>& )const {}
    void get_required_posting_authorities( flat_set<account_name_type>& )const {}
    void get_required_owner_authorities( flat_set<account_name_type>& )const {}
    void get_required_witness_signatures( flat_set<account_name_type>& )const {}
    bool is_virtual()const { return false; }
    void validate()const {}
};

struct virtual_operation : public base_operation {
    bool is_virtual()const { return true; }
    void validate()const { HIVE_PROTOCOL_UNREACHABLE_CODE_ASSERT( false, ... ); } // always asserts
};
```

Operations override `get_required_*_authorities()` to declare which authority level(s) are needed. The five declarable levels are **owner**, **active**, **posting**, **witness signatures**, and custom **authority** objects (`get_required_authorities`, used for inline keys/authorities that aren't tied to an account's stored authority).

`base.hpp:31-35` also defines the empty extension type used pervasively: `future_extensions` is `static_variant<void_t>` and `extensions_type` is `flat_set<future_extensions>` — i.e. "no extensions defined yet," serialized as an empty array.

---

## Transaction-Level Constraints

These bound how operations may be combined and answer two recurring questions (max ops per tx; authority mixing).

**Maximum operations per transaction — there is no explicit count limit.** `transaction::validate()` (`transaction.cpp:40-45`) asserts only:

```cpp
HIVE_PROTOCOL_NUMBER_ASSERT( operations.size() > 0, "A transaction must have at least one operation", ... );
for( const auto& op : operations ) operation_validate(op);
```

The only upper bound is the serialized transaction size, `HIVE_MAX_TRANSACTION_SIZE = 1024*64` = **64 KiB** (`config.hpp:364`). A block's `maximum_block_size` floor equals this same constant (`config.hpp:365`). So the practical op-per-tx ceiling is "as many as fit in 64 KiB once serialized," not a fixed integer.

**Posting authority cannot be mixed with active/owner in one transaction (before HF28).** In `transaction.cpp:150-176`, signature gathering enforces:

```cpp
/** Up to HF28 posting authority cannot be mixed with active authority in same transaction */
if( required_posting.size() ) {
  if( !allow_strict_and_mixed_authorities ) {
    HIVE_PROTOCOL_AUTHORITY_ASSERT( !required_owner.size(),  "No owner authorities are allowed if posting authority is required before HF28", ... );
    HIVE_PROTOCOL_AUTHORITY_ASSERT( !required_active.size(), "No active authorities are allowed if posting authority is required before HF28", ... );
  }
  ...
}
```

`allow_strict_and_mixed_authorities` is the HF28 switch. **Before HF28**, a transaction that requires any posting authority may *not* also require active or owner authority — so e.g. a `vote` (posting) and a `transfer` (active) could not be batched in one transaction. **From HF28**, mixed/strict authority sets are permitted. This is purely a signature-gathering rule; it does not change individual operation validation.

---

## Regular Operations (Broadcastable)

Field lists below follow `FC_REFLECT` serialization order (bottom of `hive_operations.hpp` / `dhf_operations.hpp`). "Required Authority" is the declared level from `get_required_*_authorities()`.

### Social/Content Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 0 | `vote_operation` | `voter`: account_name, `author`: account_name, `permlink`: string, `weight`: int16_t | **posting** (voter) | Weight range −10000…10000 (HIVE percent). `validate()` checks `abs(weight)` in 0–100% range. |
| 1 | `comment_operation` | `parent_author`: account_name, `parent_permlink`: string, `author`: account_name, `permlink`: string, `title`: string, `body`: string, `json_metadata`: json_string | **posting** (author) | Post (empty parent_author) or comment. Body must be non-empty UTF-8; title ≤ `HIVE_COMMENT_TITLE_LIMIT−1` (255). |
| 17 | `delete_comment_operation` | `author`: account_name, `permlink`: string | **posting** (author) | No blocking HF guard. Evaluator: from HF19 cannot delete a comment with net positive rshares (`hive_evaluator_social.cpp:68-69`). |
| 19 | `comment_options_operation` | `author`: account_name, `permlink`: string, `max_accepted_payout`: asset (HBD, default 1,000,000,000), `percent_hbd`: uint16_t (default 100%), `allow_votes`: bool, `allow_curation_rewards`: bool, `extensions`: comment_options_extensions_type | **posting** (author) | Extensions can carry `comment_payout_beneficiaries`: ≥1 entry, **< `HIVE_BENEFICIARY_LIMIT` (128) ⇒ max 127**, sorted strictly ascending by account, cumulative weight ≤ 100% (`hive_operations.cpp:150-175`). (Evaluator imposes a stricter soft-fork runtime cap — see reference/operations.md — Part 04.) |

### Transfer/Financial Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 2 | `transfer_operation` | `from`, `to`: account_name, `amount`: asset, `memo`: string | **active** (from) | HIVE or HBD only (not vesting). `amount > 0`. Memo ≤ `HIVE_MAX_MEMO_SIZE−1` (2047) UTF-8. `from==to` allowed at protocol level. |
| 3 | `transfer_to_vesting_operation` | `from`, `to`: account_name, `amount`: asset | **active** (from) | Power up. Amount must be HIVE, `> 0`. `to` empty ⇒ self. |
| 4 | `withdraw_vesting_operation` | `account`: account_name, `vesting_shares`: asset | **active** (account) | Power down. Amount must be VESTS. (No `>0` check in validate — 0 cancels.) |
| 20 | `set_withdraw_vesting_route_operation` | `from_account`, `to_account`: account_name, `percent`: uint16_t, `auto_vest`: bool | **active** (from_account) | Percent 0–10000. No blocking HF guard; HF21 evaluator forbids routing to treasury (`hive_evaluator_transfer.cpp:400`). |
| 32 | `transfer_to_savings_operation` | `from`, `to`: account_name, `amount`: asset, `memo`: string | **active** (from) | HIVE or HBD. `amount > 0`. |
| 33 | `transfer_from_savings_operation` | `from`: account_name, `request_id`: uint32_t, `to`: account_name, `amount`: asset, `memo`: string | **active** (from) | 3-day delay. HIVE or HBD. `amount > 0`. |
| 34 | `cancel_transfer_from_savings_operation` | `from`: account_name, `request_id`: uint32_t | **active** (from) | Cancels pending savings withdrawal. |
| 39 | `claim_reward_balance_operation` | `account`: account_name, `reward_hive`: asset, `reward_hbd`: asset, `reward_vests`: asset | **posting** (account) | Each amount ≥ 0 with correct symbol; at least one > 0. |
| 49 | `recurrent_transfer_operation` | `from`, `to`: account_name, `amount`: asset, `memo`: string, `recurrence`: uint16_t, `executions`: uint16_t, `extensions`: recurrent_transfer_extensions_type | **active** (from) | **Blocked before HF25** (`hive_evaluator_transfer.cpp:908`). `from != to`; HIVE or HBD; `amount ≥ 0` (0 deletes); `recurrence ≥ HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` (24h); `executions ≥ 2`. Extension: `recurrent_transfer_pair_id` (uint8_t). |

### Market Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 5 | `limit_order_create_operation` | `owner`: account_name, `orderid`: uint32_t, `amount_to_sell`: asset, `min_to_receive`: asset, `fill_or_kill`: bool, `expiration`: time_point_sec (default `maximum()`) | **active** (owner) | Internal HIVE↔HBD market. `validate()` also accepts HIVE↔SMT-NAI pairs (residual SMT code — see "SMT residue" below). |
| 6 | `limit_order_cancel_operation` | `owner`: account_name, `orderid`: uint32_t | **active** (owner) | |
| 21 | `limit_order_create2_operation` | `owner`: account_name, `orderid`: uint32_t, `amount_to_sell`: asset, `exchange_rate`: price, `fill_or_kill`: bool, `expiration`: time_point_sec | **active** (owner) | Serializes price directly. Same SMT-NAI residue in `validate()`. `amount_to_sell` must match `exchange_rate.base` symbol; price·amount must not round to 0. |

### Conversion Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 8 | `convert_operation` | `owner`: account_name, `requestid`: uint32_t, `amount`: asset | **active** (owner) | HBD→HIVE only. `amount > 0`. Settles after `HIVE_CONVERSION_DELAY` (3.5 days). |
| 48 | `collateralized_convert_operation` | `owner`: account_name, `requestid`: uint32_t, `amount`: asset | **active** (owner) | **Blocked before HF25** (`hive_evaluator_transfer.cpp:475`). HIVE→HBD; HBD delivered immediately; excess collateral returned after `HIVE_COLLATERALIZED_CONVERSION_DELAY`. |

### Account Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 9 | `account_create_operation` | `fee`: asset, `creator`: account_name, `new_account_name`: account_name, `owner`/`active`/`posting`: authority, `memo_key`: public_key, `json_metadata`: json_string | **active** (creator) | Fee must be HIVE, ≥0, ≤ `HIVE_MAX_ACCOUNT_CREATION_FEE`. Each authority `validate_auth_size()` ≤ `HIVE_MAX_AUTHORITY_MEMBERSHIP` (40). |
| 10 | `account_update_operation` | `account`: account_name, `owner`/`active`/`posting`: optional\<authority\>, `memo_key`: public_key, `json_metadata`: json_string | **owner** if `owner` set; else **active** | `validate()` deliberately cannot check auth size (comment at `hive_operations.cpp:99`). |
| 22 | `claim_account_operation` | `creator`: account_name, `fee`: asset, `extensions`: extensions_type | **active** (creator) | **Blocked before HF20** (`hive_evaluator_account.cpp:404`). Fee HIVE (0 ⇒ use RC). `extensions` must be empty. Claims a creation ticket. |
| 23 | `create_claimed_account_operation` | `creator`: account_name, `new_account_name`: account_name, `owner`/`active`/`posting`: authority, `memo_key`: public_key, `json_metadata`: json_string, `extensions`: extensions_type | **active** (creator) | **Blocked before HF20** (`hive_evaluator_account.cpp:466`). Consumes a claimed creation ticket. `extensions` must be empty. |
| 41 | `account_create_with_delegation_operation` | `fee`: asset, `delegation`: asset, `creator`: account_name, `new_account_name`: account_name, `owner`/`active`/`posting`: authority, `memo_key`: public_key, `json_metadata`: json_string, `extensions`: extensions_type | **active** (creator) | **Deprecated at HF20** (evaluator rejects). Fee HIVE, delegation VESTS. |
| 43 | `account_update2_operation` | `account`: account_name, `owner`/`active`/`posting`: optional\<authority\>, `memo_key`: optional\<public_key\>, `json_metadata`: json_string, `posting_json_metadata`: json_string, `extensions`: extensions_type | **owner** if `owner` set; **active** if `active`/`posting`/`memo_key`/`json_metadata` set (no owner); **posting** if only `posting_json_metadata` set | **Blocked before HF21** (`hive_evaluator_account.cpp:362`). Three-tier authority depending on populated fields (`hive_operations.hpp:88-95`). |

### Account Recovery Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 24 | `request_account_recovery_operation` | `recovery_account`: account_name, `account_to_recover`: account_name, `new_owner_authority`: authority, `extensions`: extensions_type | **active** (recovery_account) | Recovery request valid ~24h. Setting `new_owner_authority` weight threshold to 0 cancels. |
| 25 | `recover_account_operation` | `account_to_recover`: account_name, `new_owner_authority`: authority, `recent_owner_authority`: authority, `extensions`: extensions_type | **custom**: must satisfy BOTH `new_owner_authority` AND `recent_owner_authority` (`hive_operations.hpp:851-855`) | `validate()` requires new≠recent, neither impossible, new non-trivial. Recent authority valid 30 days. |
| 26 | `change_recovery_account_operation` | `account_to_recover`: account_name, `new_recovery_account`: account_name, `extensions`: extensions_type | **owner** (account_to_recover) | 30-day delay before effective. |

### Escrow Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 27 | `escrow_transfer_operation` | `from`, `to`, `agent`: account_name, `hbd_amount`: asset, `hive_amount`: asset, `escrow_id`: uint32_t (**default 30**), `agent`/`fee`: asset, `json_meta`: json_string, `ratification_deadline`, `escrow_expiration`: time_point_sec | **active** (from) | Serialization order: `(from)(to)(hbd_amount)(hive_amount)(escrow_id)(agent)(fee)(json_meta)(ratification_deadline)(escrow_expiration)`. Agent must be a third party; ≥1 amount >0; fee HIVE or HBD; deadline < expiration. |
| 28 | `escrow_dispute_operation` | `from`, `to`, `agent`, `who`: account_name, `escrow_id`: uint32_t (default 30) | **active** (who) | `who` must be `from` or `to`. |
| 29 | `escrow_release_operation` | `from`, `to`, `agent`, `who`, `receiver`: account_name, `escrow_id`: uint32_t (default 30), `hbd_amount`, `hive_amount`: asset | **active** (who) | `who` ∈ {from,to,agent}; `receiver` ∈ {from,to}; ≥1 amount >0. Permission depends on dispute/expiration state (Part 04). |
| 31 | `escrow_approve_operation` | `from`, `to`, `agent`, `who`: account_name, `escrow_id`: uint32_t (default 30), `approve`: bool (default true) | **active** (who) | `who` must be `to` or `agent`. |

### Witness Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 7 | `feed_publish_operation` | `publisher`: account_name, `exchange_rate`: price | **active** (publisher) | Price must be a HIVE/HBD pair (either ordering). |
| 11 | `witness_update_operation` | `owner`: account_name, `url`: string, `block_signing_key`: public_key, `props`: legacy_chain_properties, `fee`: asset | **active** (owner) | Null signing key removes witness. URL 1…`HIVE_MAX_WITNESS_URL_LENGTH` (2048) UTF-8. `props.validate<false>()` (non-canonical fee allowed). |
| 12 | `account_witness_vote_operation` | `account`, `witness`: account_name, `approve`: bool (default true) | **active** (account) | |
| 13 | `account_witness_proxy_operation` | `account`: account_name, `proxy`: account_name (default `HIVE_PROXY_TO_SELF_ACCOUNT` = "") | **active** (account) | Empty proxy clears. Cannot proxy to self. |
| 16 | `witness_block_approve_operation` | `witness`: account_name, `block_id`: block_id_type | **witness signature** (witness) | Internal; only operation declaring a witness signature. |
| 42 | `witness_set_properties_operation` | `owner`: account_name, `props`: flat_map\<string, vector\<char\>\>, `extensions`: extensions_type | **custom**: `authority(1, signing_key, 1)` built from `props["key"]` (`hive_operations.hpp:475-487`) | **Blocked before HF20** (`hive_evaluator.cpp:115`). `validate()` requires `props["key"]`. Recognized props below. |

**`legacy_chain_properties`** (`hive_operations.hpp:400-437`; used in `witness_update`/`pow`/`pow2`):
- `account_creation_fee`: legacy_hive_asset (≥ `HIVE_MIN_ACCOUNT_CREATION_FEE`, ≤ `HIVE_MAX_ACCOUNT_CREATION_FEE`)
- `maximum_block_size`: uint32_t (`HIVE_MIN_BLOCK_SIZE_LIMIT` … `HIVE_MAX_BLOCK_SIZE`)
- `hbd_interest_rate`: uint16_t (0–10000)

**`witness_set_properties` recognized `props` keys** (`hive_operations.cpp:287-396`), each deserialized & validated only if present: `key` (**required**), `new_signing_key`, `account_creation_fee`, `maximum_block_size`, `hbd_interest_rate` (or legacy `sbd_interest_rate`), `hbd_exchange_rate` (or legacy `sbd_exchange_rate`), `url`, `account_subsidy_budget`, `account_subsidy_decay`. Unknown keys are ignored by `validate()`.

### Proof-of-Work Operations (Historical/Disabled)

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 14 | `pow_operation` | `worker_account`: account_name, `block_id`: block_id_type, `nonce`: uint64_t, `work`: pow, `props`: legacy_chain_properties | None (PoW itself is the authority; `get_required_active_authorities` empty) | Deprecated at HF13. `pow::validate()` real work-check is eliminated — "Creation of new ops is disallowed" (`hive_operations.cpp:562-570`). |
| 30 | `pow2_operation` | `work`: pow2_work (variant: pow2 \| equihash_pow), `new_owner_key`: optional\<public_key\>, `props`: legacy_chain_properties | **active** (worker) if `new_owner_key` unset; else custom `authority(1, new_owner_key, 1)` | Mining disabled at HF17. `pow2::validate()` work-check likewise eliminated. |

### Custom Operations

| ID | Operation | Fields (serialization order) | Declared Authority | Chain reality |
|----|-----------|-----|-------------------|-------|
| 15 | `custom_operation` | `required_auths`: flat_set\<account_name\>, `id`: uint16_t, `data`: vector\<char\> | **active** (all required_auths) | Evaluator does nothing except enforce `data ≤ 8192` bytes from HF26 (`hive_evaluator.cpp:328-335`). No interpreter dispatch. ≥1 auth, ≤40. |
| 18 | `custom_json_operation` | `required_auths`: flat_set\<account_name\>, `required_posting_auths`: flat_set\<account_name\>, `id`: custom_id_type (≤32), `json`: json_string | **active** (required_auths) + **posting** (required_posting_auths) | Dispatched by `id` to a registered interpreter (only `"rc"` exists in consensus); unknown id ⇒ silent no-op (`hive_evaluator.cpp:337-373`). |
| 35 | `custom_binary_operation` | `required_owner_auths`, `required_active_auths`, `required_posting_auths`: flat_set\<account_name\>, `required_auths`: vector\<authority\>, `id`: custom_id_type, `data`: vector\<char\> | **owner**+**active**+**posting**+custom authorities (declared) | **HARD-DISABLED**: evaluator unconditionally throws (`hive_evaluator.cpp:378`). `validate()` succeeds at protocol layer, but no transaction containing it can be applied. |

### Governance / Proposal Operations (DHF)

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 44 | `create_proposal_operation` | `creator`, `receiver`: account_name, `start_date`, `end_date`: time_point_sec, `daily_pay`: asset, `subject`: string, `permlink`: string, `extensions`: extensions_type | **active** (creator) | **Blocked before HF21** (`dhf_evaluator.cpp:36`). daily_pay HBD. |
| 45 | `update_proposal_votes_operation` | `voter`: account_name, `proposal_ids`: flat_set_ex\<int64_t\>, `approve`: bool, `extensions`: extensions_type | **active** (voter) | **Blocked before HF21** (`dhf_evaluator.cpp:159`). |
| 46 | `remove_proposal_operation` | `proposal_owner`: account_name, `proposal_ids`: flat_set_ex\<int64_t\>, `extensions`: extensions_type | **active** (proposal_owner) | **Blocked before HF21** (`dhf_evaluator.cpp:217`). |
| 47 | `update_proposal_operation` | `proposal_id`: int64_t, `creator`: account_name, `daily_pay`: asset, `subject`: string, `permlink`: string, `extensions`: update_proposal_extensions_type | **active** (creator) | **Blocked before HF24** (`dhf_evaluator.cpp:107`). daily_pay can only be lowered. Extension: `update_proposal_end_date`. |

### Vesting Delegation Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 40 | `delegate_vesting_shares_operation` | `delegator`, `delegatee`: account_name, `vesting_shares`: asset | **active** (delegator) | VESTS only, ≥0. Cannot delegate to self. 0 removes (with return period). |

### Voting Rights Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 36 | `decline_voting_rights_operation` | `account`: account_name, `decline`: bool (default true) | **owner** (account) | **Blocked before HF14** (`hive_evaluator_account.cpp:619`). 30-day delay (`HIVE_OWNER_AUTH_RECOVERY_PERIOD`). |

### Placeholder/Disabled Operations

| ID | Operation | Fields (serialization order) | Required Authority | Notes |
|----|-----------|-----|-------------------|-------|
| 37 | `reset_account_operation` | `reset_account`, `account_to_reset`: account_name, `new_owner_authority`: authority | **active** (reset_account) | **DISABLED.** `validate()` always asserts `false && "placeholder1"` (`hive_operations.cpp:774-777`). |
| 38 | `set_reset_account_operation` | `account`, `current_reset_account`, `reset_account`: account_name | **owner** if `current_reset_account` set; else **posting** | **DISABLED.** `validate()` always asserts `false && "placeholder2"` (`hive_operations.cpp:779-782`). |

---

## Virtual Operations

Virtual operations are **never broadcast**. They are generated internally during block processing to record side effects, and all inherit from `virtual_operation` (`is_virtual()==true`; `validate()` always asserts). Field types come directly from `hive_virtual_operations.hpp`.

### Reward/Payout Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 51 | `author_reward_operation` | `author`, `permlink`, `hbd_payout` (HBD), `hive_payout` (HIVE), `vesting_payout` (VESTS), `curators_vesting_payout` (VESTS), `payout_must_be_claimed` (bool) | Comment cashout with nonzero author reward |
| 52 | `curation_reward_operation` | `curator`, `reward` (VESTS), `author`, `permlink`, `payout_must_be_claimed` (bool) | Comment cashout — per curator with nonzero reward |
| 53 | `comment_reward_operation` | `author`, `permlink`, `payout` (HBD), `author_rewards` (**share_type** — HIVE satoshi, see Discrepancies), `total_payout_value` (HBD), `curator_payout_value` (HBD), `beneficiary_payout_value` (HBD) | Comment cashout — informational summary, no transfers |
| 63 | `comment_benefactor_reward_operation` | `benefactor`, `author`, `permlink`, `hbd_payout` (HBD), `hive_payout` (HIVE), `vesting_payout` (VESTS), `payout_must_be_claimed` (bool) | Comment cashout — per beneficiary from comment_options |
| 61 | `comment_payout_update_operation` | `author`, `permlink` | Comment cashout time passes (even with zero rewards) |
| 54 | `liquidity_reward_operation` | `owner`, `payout` (HIVE) | Market-maker reward. **No longer active after HF12.** |
| 64 | `producer_reward_operation` | `producer`, `vesting_shares` (**asset** — VESTS, or HIVE in first 30 days post-genesis) | Every block — block-production reward |
| 78 | `pow_reward_operation` | `worker`, `reward` (**asset** — VESTS, or HIVE early) | pow/pow2 execution. **Mining rewards stopped after HF16.** |

### Conversion Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 50 | `fill_convert_request_operation` | `owner`, `requestid` (uint32_t), `amount_in` (HBD), `amount_out` (HIVE) | `convert_operation` completes after delay |
| 81 | `fill_collateralized_convert_request_operation` | `owner`, `requestid` (uint32_t), `amount_in` (HIVE), `amount_out` (HBD), `excess_collateral` (HIVE) | `collateralized_convert` completes after delay |
| 88 | `collateralized_convert_immediate_conversion_operation` | `owner`, `requestid` (uint32_t), `hbd_out` (HBD) | `collateralized_convert_operation` execution — immediate HBD |
| 74 | `dhf_conversion_operation` | `treasury`, `hive_amount_in` (HIVE), `hbd_amount_out` (HBD) | HIVE→treasury transfer, or daily treasury maintenance |

### Transfer/Withdrawal Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 55 | `interest_operation` | `owner`, `interest` (HBD), `is_saved_into_hbd_balance` (bool) | HBD balance modification accrues interest. After HF25: savings only. |
| 56 | `fill_vesting_withdraw_operation` | `from_account`, `to_account`, `withdrawn` (VESTS), `deposited` (**asset** — HIVE or VESTS per route `auto_vest`) | Power-down batch — each active withdraw route per period (`is_empty_implied_route()` ⇒ skipped, see issue #337) |
| 59 | `fill_transfer_from_savings_operation` | `from`, `to`, `amount` (**asset** — HIVE or HBD), `request_id` (uint32_t), `memo` | Savings withdrawal delay passes |
| 77 | `transfer_to_vesting_completed_operation` | `from_account`, `to_account`, `hive_vested` (HIVE), `vesting_shares_received` (VESTS) | Every `transfer_to_vesting` — supplements with VESTS received |
| 83 | `fill_recurrent_transfer_operation` | `from`, `to`, `amount` (**asset** — HIVE or HBD), `memo`, `remaining_executions` (uint16_t), `extensions` | Recurrent transfer executes successfully |
| 84 | `failed_recurrent_transfer_operation` | `from`, `to`, `amount` (asset), `memo`, `consecutive_failures` (uint8_t), `remaining_executions` (uint16_t), `deleted` (bool), `extensions` | Recurrent transfer fails (insufficient funds). `deleted=true` if discontinued. |

### Market Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 57 | `fill_order_operation` | `current_owner`, `current_orderid` (uint32_t), `current_pays` (asset), `open_owner`, `open_orderid` (uint32_t), `open_pays` (asset) | Order matching on internal market |
| 85 | `limit_order_cancelled_operation` | `seller`, `orderid` (uint32_t), `amount_back` (asset — HIVE or HBD) | Order cancelled (explicit, remainder too small, or expired) |

### Governance Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 66 | `proposal_pay_operation` | `proposal_id` (uint32_t), `receiver`, `payer` (treasury), `payment` (HBD) | Proposal maintenance — funded proposal receives payment |
| 67 | `dhf_funding_operation` | `treasury`, `additional_funds` (HBD) | Proposal maintenance — inflation directed to treasury |
| 87 | `proposal_fee_operation` | `creator`, `treasury`, `proposal_id` (uint32_t), `fee` (HBD) | `create_proposal_operation` execution — fee paid |
| 70 | `delayed_voting_operation` | `voter`, `votes` (ushare_type) | Grace period ends for fresh VESTS governance-vote activation |
| 75 | `expired_account_notification_operation` | `account` | User's governance votes nullified due to inactivity |
| 91 | `proxy_cleared_operation` | `account`, `proxy` | Proxy removed (explicit, declined voting, or governance-vote expiration) |
| 92 | `declined_voting_rights_operation` | `account` | `decline_voting_rights_operation` takes effect after 30-day wait |

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
| 72 | `effective_comment_vote_operation` | `voter`, `author`, `permlink`, `weight` (uint64_t), `rshares` (int64_t), `total_vote_weight` (uint64_t), `pending_payout` (HBD) | Each effective vote (before cashout); `pending_payout` supplemented by AH RocksDB plugin |
| 73 | `ineffective_delete_comment_operation` | `author`, `permlink` | delete_comment ignored (pre-HF19, had net positive votes) |

### Account Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 80 | `account_created_operation` | `new_account_name`, `creator`, `initial_vesting_shares` (VESTS), `initial_delegation` (VESTS) | All account creation methods (genesis, operations, PoW). Constructor asserts creator is non-empty. |
| 76 | `changed_recovery_account_operation` | `account`, `old_recovery_account`, `new_recovery_account` | change_recovery_account wait period passes |

### Escrow Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 89 | `escrow_approved_operation` | `from`, `to`, `agent`, `escrow_id` (uint32_t), `fee` (asset — HIVE or HBD) | Both agent and to approved — agent receives fee |
| 90 | `escrow_rejected_operation` | `from`, `to`, `agent`, `escrow_id` (uint32_t), `hbd_amount` (HBD), `hive_amount` (HIVE), `fee` (asset) | Escrow rejected or ratification deadline passed — all funds returned to from |

### System/Hardfork Virtual Operations

| ID | Operation | Fields | Generated By |
|----|-----------|--------|-------------|
| 60 | `hardfork_operation` | `hardfork_id` (uint32_t) | Each hardfork activation |
| 65 | `clear_null_account_balance_operation` | `total_cleared`: vector\<asset\> | Nonzero assets burned from 'null' account |
| 71 | `consolidate_treasury_balance_operation` | `total_moved`: vector\<asset\> | Assets moved from old treasury ('steem.dao') to new ('hive.fund') |
| 68 | `hardfork_hive_operation` | `account`, `treasury`, `other_affected_accounts`: vector\<account_name\>, `hbd_transferred` (HBD), `hive_transferred` (HIVE), `vests_converted` (VESTS), `total_hive_from_vests` (HIVE) | HF23 — per account excluded from HIVE airdrop |
| 69 | `hardfork_hive_restore_operation` | `account`, `treasury`, `hbd_transferred` (HBD), `hive_transferred` (HIVE) | HF24 — late airdrop for accounts that won appeal (see Discrepancies) |
| 79 | `vesting_shares_split_operation` | `owner`, `vesting_shares_before_split` (VESTS), `vesting_shares_after_split` (VESTS) | HF1 — VESTS precision increase (×1,000,000) |
| 82 | `system_warning_operation` | `message` (string) | Node-operator-level anomalies surfaced on 'initminer' account history: unknown witness type, collateral shortfall, HBD hard-cap price correction, noncanonical witness fee symbol, witness block-size change (`hive_virtual_operations.hpp:595-608`) |

---

## Custom Operations Framework

This section answers "how does the custom operation interpreter work, and which ids does the chain itself interpret?" — verified across the protocol *and* chain layers.

### The three custom-op types and their actual chain behavior

| Type | ID | Payload | What the chain does |
|------|----|---------|---------------------|
| `custom_operation` | 15 | binary (`data`) | **Inert.** Evaluator only enforces `data.size() ≤ HIVE_CUSTOM_OP_DATA_MAX_LENGTH` (8192) from HF26; never dispatched to any interpreter (`hive_evaluator.cpp:328-335`). |
| `custom_json_operation` | 18 | JSON (`json`) | **Dispatched by `id`.** Looks up a registered interpreter; if none, silently returns (`hive_evaluator.cpp:347-349`). From HF26, `json.length() ≤ 8192`. |
| `custom_binary_operation` | 35 | binary (`data`) | **Disabled.** Evaluator unconditionally throws `"custom_binary_operation is disallowed"` (`hive_evaluator.cpp:378`). The HF14 guard immediately below it (`:380`) is now dead code. |

### Dispatch and exception handling for `custom_json` (`hive_evaluator.cpp:337-373`)

```cpp
std::shared_ptr<custom_operation_interpreter> eval = _db.get_custom_json_evaluator( o.id );
if( !eval ) return;            // unknown id ⇒ no-op (the op is still stored in the block / account history)
...
if( !_db.is_in_control() ) truncation_controller::set_verify( false );
eval->apply( o );              // wrapped in try/catch:
// - if in_control (producing block / accepting to mempool): exceptions propagate (tx rejected)
// - if NOT in_control (replay / applying a block from the network): exceptions are swallowed
//   (issue #256 — the interpreter is responsible for undoing partial state itself)
```

This asymmetry means a malformed `custom_json` for a *registered* id will be rejected when first broadcast, but is tolerated (no-op) during replay so historical blocks always apply.

### Built-in custom operation: RC delegation — the only consensus-interpreted id

The single protocol-defined custom operation is **RC delegation** (`hive_custom_operations.hpp:8-23`):

```cpp
struct delegate_rc_operation : public base_operation {
    account_name_type             from;
    flat_set<account_name_type>   delegatees;   // ≥1, ≤ HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP (100)
    int64_t                       max_rc = 0;   // ≥ 0
    extensions_type               extensions;
    void get_required_posting_authorities( flat_set<account_name_type>& a )const { a.insert( from ); } // posting auth
};
typedef fc::static_variant<delegate_rc_operation> rc_custom_operation;
#define HIVE_RC_CUSTOM_OPERATION_ID "rc"
```

`validate()` (`hive_custom_operations.cpp:12-32`): valid `from`; 1…100 distinct delegatees, none equal to `from`; `max_rc ≥ 0`.

**This is the only `custom_json` id with a consensus-registered interpreter.** The RC subsystem lives *inside the chain library* (`libraries/chain/rc/`), not an optional plugin, and is wired up during core database init (`database_init.cpp:37` → `rc().initialize_evaluators()`). Registration (`rc/rc_utility.cpp:717-732`):

```cpp
_custom_operation_interpreter = std::make_shared<
  generic_custom_operation_interpreter< hive::protocol::rc_custom_operation > >( db, HIVE_RC_CUSTOM_OPERATION_ID );
_custom_operation_interpreter->register_evaluator< delegate_rc_evaluator >( nullptr );
db.register_custom_operation_interpreter( _custom_operation_interpreter );   // keyed by "rc"
```

A broad search of the chain library found **no other `custom_json` id special-cased in consensus code** (no `== "follow"`, `== "reblog"`, etc.). All other ids — `"follow"`, `"reblog"`, `"community"`, `"notify"`, `"ssc-mainnet-hive"`, `"sm_*"`, … — are off-chain conventions interpreted by Hivemind / sidechains, and are pure no-ops to hived (stored in the block, never acted on by consensus).

**Consensus nuance on RC:** RC *delegation processing* (the `"rc"` custom_json) is deterministic and consensus-applied by every node. RC *cost enforcement* (whether a broadcaster has enough mana) is non-consensus / mempool-only — see comment at `rc/rc_utility.cpp:320` and the KB's "RC is non-consensus" headline. Detailed pricing is Part 08.

### Authority model for custom operations

| Operation | Authority levels declared | Payload | ≥1 auth? | Max auth |
|-----------|--------------------------|---------|----------|----------|
| `custom_operation` | active only | binary | yes | `HIVE_MAX_AUTHORITY_MEMBERSHIP` (40) |
| `custom_json_operation` | active + posting | JSON (validated) | yes (active+posting combined) | 40 combined |
| `custom_binary_operation` | owner + active + posting + inline authorities | binary | yes | 40 (counting inline auth members) |

`custom_id_type` is `fixed_string<32>` (`types.hpp:80`); `validate()` additionally caps id length at `HIVE_CUSTOM_OP_ID_MAX_LENGTH` (32) for the JSON/binary variants.

---

## Operation Availability — Hardfork Gating

This resolves "when were operations introduced, and how is that enforced?" The mechanism, verified across all chain evaluators, is:

> **There is no central/generic gate that blocks unknown or new operations before a hardfork.** The evaluator registry (`evaluator_registry.hpp`) is pure dispatch with no hardfork logic. Each operation that needs to be blocked before a hardfork carries its *own* `HIVE_CHAIN_HARDFORK_ASSERT( _db.has_hardfork(...) )` at the top of its `do_apply()`. Operations without such a guard became usable the moment their defining release shipped to a majority of the network; any historical blocking guard is removed once activation is safely in the past (standard practice — see the repo's own CLAUDE.md on consensus-critical changes).

**Operations with an explicit *blocking* hardfork guard** (cannot be applied before the named HF; HF↔version source-confirmed in `database_hardfork.cpp:82,97,100`):

| ID | Operation | Blocking HF | Hardfork constant | Guard location |
|----|-----------|------------|-------------------|----------------|
| 35 | `custom_binary_operation` | — | (HF14 guard now **dead** under unconditional disable) | `hive_evaluator.cpp:378,380` |
| 36 | `decline_voting_rights_operation` | HF14 | `HIVE_HARDFORK_0_14__324` | `hive_evaluator_account.cpp:619` |
| 22 | `claim_account_operation` | HF20 | `HIVE_HARDFORK_0_20__1771` | `hive_evaluator_account.cpp:404` |
| 23 | `create_claimed_account_operation` | HF20 | `HIVE_HARDFORK_0_20__1771` | `hive_evaluator_account.cpp:466` |
| 42 | `witness_set_properties_operation` | HF20 | `HIVE_HARDFORK_0_20__1620` | `hive_evaluator.cpp:115` |
| 43 | `account_update2_operation` | HF21 | `HIVE_HARDFORK_0_21__3274` | `hive_evaluator_account.cpp:362` |
| 44 | `create_proposal_operation` | HF21 | `HIVE_HARDFORK_0_21_PROPOSALS` | `dhf_evaluator.cpp:36` |
| 45 | `update_proposal_votes_operation` | HF21 | `HIVE_HARDFORK_0_21_PROPOSALS` | `dhf_evaluator.cpp:159` |
| 46 | `remove_proposal_operation` | HF21 | `HIVE_HARDFORK_0_21_PROPOSALS` | `dhf_evaluator.cpp:217` |
| 47 | `update_proposal_operation` | HF24 | `HIVE_HARDFORK_1_24` | `dhf_evaluator.cpp:107` |
| 48 | `collateralized_convert_operation` | HF25 | `HIVE_HARDFORK_1_25` | `hive_evaluator_transfer.cpp:475` |
| 49 | `recurrent_transfer_operation` | HF25 | `HIVE_HARDFORK_1_25` | `hive_evaluator_transfer.cpp:908` |

**Operations 17–21 specifically** (`delete_comment`, `custom_json`, `comment_options`, `set_withdraw_vesting_route`, `limit_order_create2`) carry **no blocking guard** at this commit. They have only *behavior-modifying* guards added at later hardforks:

| ID | Operation | Behavior-modifying guard (not blocking) | HF |
|----|-----------|-----------------------------------------|----|
| 17 | `delete_comment` | from HF19, cannot delete a comment with net positive rshares (`hive_evaluator_social.cpp:68-69`) | HF19 |
| 19 | `comment_options` | from HF24, cannot update options on an already-paid-out comment (`hive_evaluator_social.cpp:149`) | HF24 |
| 20 | `set_withdraw_vesting_route` | from HF21, cannot route to treasury (`hive_evaluator_transfer.cpp:400`) | HF21 |
| 21 | `limit_order_create2` | from HF20, expiration capped to ≤28 days ahead (`hive_evaluator_transfer.cpp:~556`) | HF20 |

So the answer to "exactly when were 17–21 introduced" is: **not gated by an in-code hardfork at this commit.** Their historical introduction heights (and the genesis set 0–16) are a Part 09 / `reference/hardforks.md` matter; the *consensus mechanism* for their availability is the social/release process plus variant-order stability, not a per-op gate. (`custom_binary` (35) is the cautionary counter-example: technically enabled at HF14, never used, and later hard-disabled.)

---

## Operation Classification

From `operations.cpp:7-47`:

- **Market operations** (`is_market_operation`, `operations.cpp:7-16`) — `limit_order_create_operation`, `limit_order_cancel_operation`, `transfer_operation`, `transfer_to_vesting_operation`. (Used for market-history bucketing, not rate limiting — hived has no per-client API rate limiting.)
- **Virtual operations** (`is_virtual_operation`, `operations.cpp:22-33`) — dispatches to each op's `is_virtual()`; true for IDs 50–92.
- **Effective operations** (`is_effective_operation`, `operations.cpp:35-47`) — all operations except `fill_vesting_withdraw_operation` when it represents an empty implied route (`withdrawn.amount == 0`, see issue #337).

### SMT residue in limit-order validation (resolves open question)

`limit_order_create_operation::validate()` (`hive_operations.cpp:601-618`) and `limit_order_create2_operation::validate()` (`:620-640`) accept **four** symbol pairings: the two HIVE/HBD orderings, **plus** two orderings where one side is `HIVE_SYMBOL` and the other has `symbol.space() == asset_symbol_type::smt_nai_space`. `smt_nai_space` is the SMT (Smart Media Token) symbol space (`asset_symbol.hpp:69-73`). This is **leftover code from the never-activated SMT effort** (SMTs were designed on Steem but never shipped to consensus on Hive). Consequences:
- There is no operation to *create* an SMT, so no SMT balances exist on chain.
- The limit-order evaluator has **no SMT branch** (verified: zero `smt`/`nai_space` references in `hive_evaluator_transfer.cpp`). A HIVE/SMT order would pass `validate()` but cannot reference a real balance, so it cannot be funded/filled.
- Tightening `validate()` to reject SMT pairs would change which transactions are legal and therefore requires a hardfork — which is why the dead branch persists (the repo CLAUDE.md uses this exact case as its canonical "unsafe change" example).

---

## Key Discoveries

1. **Numeric IDs are strictly positional.** Operation ID = variant index. Reordering anything before the virtual ops triggers a hardfork (`operations.hpp:12-14`). 50 regular (0–49) + 43 virtual (50–92) = 93 total.

2. **Only `custom_json` with `id=="rc"` is interpreted by consensus.** `custom_operation` (15) is inert beyond a size cap, `custom_binary_operation` (35) is hard-disabled, and `custom_json` (18) with any non-`"rc"` id is a silent no-op. The RC interpreter is registered inside the chain library, not a plugin (`rc/rc_utility.cpp:717-732`).

3. **`custom_binary_operation` is dead at the chain layer.** Its evaluator unconditionally throws (`hive_evaluator.cpp:378`), despite a valid protocol-layer `validate()` and a declared all-levels authority model. No transaction containing it can be applied. (Correction to prior framing that listed it as a usable multi-level-auth op.)

4. **No central pre-hardfork gate; evaluators self-guard.** Twelve operations carry explicit blocking `has_hardfork` guards (table above); 17–21 carry only behavior-modifying guards. The registry itself does no hardfork checking.

5. **No per-transaction operation-count limit.** `transaction::validate()` requires only ≥1 operation (`transaction.cpp:42`); the real bound is the 64 KiB `HIVE_MAX_TRANSACTION_SIZE` (`config.hpp:364`).

6. **Posting authority can't mix with active/owner before HF28.** Signature gathering rejects a transaction needing posting auth alongside active/owner auth until the `allow_strict_and_mixed_authorities` (HF28) switch (`transaction.cpp:150-176`).

7. **Three-tier authority in `account_update2`.** Owner / active / posting depending on which fields are populated (`hive_operations.hpp:88-95`) — the only op with three distinct authority paths.

8. **`recover_account_operation` has a unique dual-authority requirement.** Must satisfy BOTH `new_owner_authority` AND `recent_owner_authority` simultaneously (`hive_operations.hpp:851-855`) — the only op requiring two separate authority objects.

9. **`witness_set_properties` authenticates via the signing key, not owner/active/posting.** It builds `authority(1, props["key"], 1)`; a missing `"key"` yields the impossible null-account authority (`hive_operations.hpp:475-487`). It also accepts legacy Steem prop names (`sbd_interest_rate`, `sbd_exchange_rate`).

10. **`reset_account`/`set_reset_account` are dead placeholders.** Both `validate()`s always assert false (`hive_operations.cpp:774-782`); they exist only to hold variant slots 37–38.

11. **`flat_set_ex` enforces sorted-unique on deserialize.** DHF proposal-id sets reject out-of-order/duplicate items during `from_variant` (`dhf_operations.hpp:115-143`).

12. **Several reward vops carry untyped `asset` fields.** `producer_reward.vesting_shares`, `pow_reward.reward`, `fill_vesting_withdraw.deposited`, `fill_transfer_from_savings.amount`, `fill_order.*pays`, escrow vop `fee`/amounts — these intentionally hold whichever of HIVE/HBD/VESTS applies at runtime, unlike the strongly-typed (`HIVE_asset`/`HBD_asset`/`VEST_asset`) fields elsewhere.

13. **`payout_must_be_claimed` flag** on `author_reward`, `curation_reward`, `comment_benefactor_reward` indicates the recipient must use `claim_reward_balance_operation`.

14. **`pow`/`pow2` real work verification is removed.** The cryptographic checks are commented out with "Creation of new ops is disallowed" after the BIP-0062 hard switch (`hive_operations.cpp:562-578`); existing blocks remain valid, new PoW ops cannot be created.

15. **Post-HF26 size caps on custom payloads.** `custom_operation.data` and `custom_json.json` are each capped at `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` (8192) from HF26 onward (`hive_evaluator.cpp:330-345`).

---

## Code References

| Component | File:line | Key Content |
|-----------|-----------|-------------|
| Operation variant typedef | `libraries/protocol/include/hive/protocol/operations.hpp:12-125` | All 93 operations with IDs; SKIP_VOPS flag |
| Op classification | `libraries/protocol/operations.cpp:7-47` | is_market / is_virtual / is_effective |
| Base operation class | `libraries/protocol/include/hive/protocol/base.hpp:13-35` | Authority method signatures; extensions_type |
| Regular operation structs | `libraries/protocol/include/hive/protocol/hive_operations.hpp` | All 46 regular op definitions + FC_REFLECT order |
| DHF operation structs | `libraries/protocol/include/hive/protocol/dhf_operations.hpp` | 4 proposal ops; flat_set_ex |
| Virtual operation structs | `libraries/protocol/include/hive/protocol/hive_virtual_operations.hpp` | All 43 virtual op definitions |
| RC custom op | `libraries/protocol/include/hive/protocol/hive_custom_operations.hpp:8-23` | delegate_rc_operation; "rc" id |
| RC custom op validate | `libraries/protocol/hive_custom_operations.cpp:12-32` | delegatee limits |
| Validate implementations | `libraries/protocol/hive_operations.cpp` | All `validate()` logic (e.g. limit_order SMT `:601-640`, witness props `:287-396`, reset placeholders `:774-782`) |
| Transaction structure & constraints | `libraries/protocol/transaction.cpp:40-56` (op count); `:150-176` (posting/active mixing) | transaction::validate; signature gathering |
| Transaction struct | `libraries/protocol/include/hive/protocol/transaction.hpp:12-20` | operations vector; extensions |
| Custom id / recurrent ext types | `libraries/protocol/include/hive/protocol/types.hpp:80,151-161` | custom_id_type; recurrent_transfer_pair_id |
| SMT symbol space | `libraries/protocol/include/hive/protocol/asset_symbol.hpp:69-73` | legacy_space / smt_nai_space enum |
| Assert macro semantics | `libraries/protocol/include/hive/protocol/hive_specialised_exceptions.hpp:8-24,59-60` | HIVE_CHAIN_*_ASSERT throw on `!(expr)` |
| Constants | `libraries/protocol/include/hive/protocol/config.hpp:206,234,353,364,375-377,425-428,449,494` | tx size, memo, url, auth membership, custom-op caps, beneficiary limit, RC delegatee max |
| custom_json / custom / custom_binary evaluators | `libraries/chain/hive_evaluator.cpp:328-394` | dispatch; size caps; custom_binary disabled |
| witness_set_properties guard | `libraries/chain/hive_evaluator.cpp:115` | HF20 block |
| Account-op hardfork guards | `libraries/chain/hive_evaluator_account.cpp:362,404,466,619` | account_update2 / claim_account / create_claimed_account / decline_voting_rights |
| Transfer-op hardfork guards | `libraries/chain/hive_evaluator_transfer.cpp:400,475,556,908` | route-to-treasury / collateralized_convert / lo_create2 expiry / recurrent_transfer |
| Social-op guards | `libraries/chain/hive_evaluator_social.cpp:68-69,149` | delete_comment HF19; comment_options HF24 |
| DHF guards | `libraries/chain/dhf_evaluator.cpp:36,107,159,217` | create / update / update_votes / remove proposal |
| RC interpreter registration | `libraries/chain/rc/rc_utility.cpp:717-732`; `libraries/chain/database_init.cpp:29-38` | "rc" interpreter wired into core init |
| HF↔version sanity | `libraries/chain/database_hardfork.cpp:82,97,100` | HF19==19, HF24==24, HF25==25 |

---

## Discrepancies and Potential Issues

1. **`comment_reward_operation.author_rewards` is `share_type`, not a typed asset.** The constructor takes `const HIVE_asset& ar` but stores `ar.amount` (raw HIVE satoshi), with source comment `[is it needed?] TODO: turn into HIVE_asset` (`hive_virtual_operations.hpp:84,91`). The op is informational-only (no transfers), so this never affected balances, but the field loses symbol typing.

2. **`hardfork_hive_restore_operation` documents an unresolved airdrop bug.** Source comment (`hive_virtual_operations.hpp:364-366`): *"the late airdrop did not apply properly since HIVE that the accounts should receive did not account for HIVE from converted VESTS. [how was it resolved?]"*. This is a chain-author annotation about HF24 historical behavior; the protocol struct itself carries only `hbd_transferred`/`hive_transferred` and the resolution is not encoded in the protocol layer (out of scope here — a chain-state/Part 06/09 matter; do not speculate).

3. **Escrow default `escrow_id = 30` is an undocumented magic default.** Consistent across all four escrow ops (`hive_operations.hpp:247,278,298,323`); no source comment explains the choice of 30 over 0. It is purely a sender-chosen identifier with a non-zero default sentinel.

4. **`witness_set_properties` accepts both legacy and current property names, legacy first.** It probes `"sbd_interest_rate"` then falls back to `"hbd_interest_rate"`, and `"sbd_exchange_rate"` then `"hbd_exchange_rate"` (`hive_operations.cpp:327-329,351-353`). If a witness sends the legacy Steem name, it takes precedence; both are valid.

5. **`fill_vesting_withdraw_operation.deposited` is an untyped `asset`** (`hive_virtual_operations.hpp:150`) — HIVE or VESTS depending on the route's `auto_vest` flag.

6. **`producer_reward_operation.vesting_shares` is an untyped `asset`** (`hive_virtual_operations.hpp:291`) — VESTS normally, HIVE only during the first 30 days post-genesis. (`pow_reward_operation.reward` shares the same dual-asset pattern.)

7. **`custom_binary_operation` (35) is usable at the protocol layer but rejected by consensus.** `validate()` passes and authorities are declared, yet the evaluator unconditionally throws (`hive_evaluator.cpp:378`). Anything that inspects only the protocol structs (wallets, SDKs) may present it as a usable op; it is not. Prior versions of this catalog described it without the chain-layer disable — corrected here.

8. **`custom_operation` (15) declares an `id` and binary `data` but is never interpreted.** Unlike `custom_json`, the evaluator never looks up an interpreter (`hive_evaluator.cpp:328-335`); the `id` field is effectively inert at consensus.

---

## Open Questions

1. ~~When exactly were operations 17–21 introduced?~~ **Resolved.** None of 17–21 carries a blocking hardfork guard at this commit; only behavior-modifying guards exist (table in "Operation Availability"). There is no central pre-hardfork gate — evaluators self-guard, and twelve ops carry explicit blocking guards. Historical introduction heights are Part 09's domain.

2. ~~What is the maximum number of operations per transaction?~~ **Resolved.** No explicit count limit; `transaction::validate()` requires only ≥1 op, bounded by `HIVE_MAX_TRANSACTION_SIZE` = 64 KiB (`transaction.cpp:42`, `config.hpp:364`).

3. **How does the RC system price each operation?** **Still deferred to Part 08.** Confirmed only that RC delegation processing (`"rc"` custom_json) is in the chain library and consensus-applied, while RC *cost* enforcement is non-consensus/mempool-only (`rc/rc_utility.cpp:320`). The per-op cost model (`rc/resource_sizes.cpp`, state/exec/byte sizing) is Part 08.

4. ~~What custom_json IDs does the chain itself interpret?~~ **Resolved.** Only `"rc"`. It is the sole id with a consensus-registered interpreter (`rc/rc_utility.cpp:723-730`); every other id is a silent no-op to hived, handled off-chain (Hivemind, sidechains). `custom_operation`(15) dispatches to nothing; `custom_binary`(35) is disabled.

5. ~~What is the `smt_nai_space` check in `limit_order_create` validate()?~~ **Resolved.** Residual never-activated SMT support: `validate()` permits HIVE↔SMT-NAI pairs (`hive_operations.cpp:601-640`), but no SMT assets exist and the evaluator has no SMT branch, so such orders can't be funded/filled. Removing the branch would require a hardfork (changes transaction legality).

**Residual (minor, for future zoom):**
- The exact hardfork at which `custom_binary_operation` was hard-disabled (the unconditional assert) is not pinpointed here — the now-dead guard references HF14, but the disable itself is unconditional. A git-archaeology zoom (which release added the `false &&` disable) would settle it; not derivable from this single pinned commit.
- `system_warning_operation`'s trigger set is enumerated from a struct comment (`hive_virtual_operations.hpp:595-608`); confirming each trigger's call-site is a Part 04/06 evaluator-level task.
