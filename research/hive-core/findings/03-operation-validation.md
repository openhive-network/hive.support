# Findings: Operation Validation Rules

## Summary

Hive protocol-level validation is implemented in `validate()` methods on each operation struct, called before any chain-state checks. These methods enforce structural correctness: field sizes, asset types, amount ranges, account name format, and cross-field consistency. Critically, **no hardfork-conditional logic exists in protocol-level validate() methods** — all hardfork-dependent validation happens in chain-layer evaluators. Virtual operations have a validate() that always asserts false (they cannot be broadcast).

## General Validation Rules

### Transaction-Level Validation
**File:** `transaction.cpp:40-55`

- Transaction must have at least one operation (`operations.size() > 0`)
- Each operation's `validate()` method is called sequentially
- Transaction expiration: max `HIVE_MAX_TIME_UNTIL_EXPIRATION` = 3600 seconds (1 hour) — enforced at chain level, not in validate()
- Max transaction size: `HIVE_MAX_TRANSACTION_SIZE` = 65,536 bytes (64KB) — enforced at serialization/chain level
- Pre-HF28: posting authority cannot be mixed with active/owner authority in same transaction

### Account Name Validation
**File:** `authority.cpp:58-122`

Account names follow RFC 1035-inspired rules, validated by `check_account_name()`:

| Rule | Constraint |
|------|-----------|
| **Length** | Min 3 (`HIVE_MIN_ACCOUNT_NAME_LENGTH`), Max 16 (`HIVE_MAX_ACCOUNT_NAME_LENGTH`) characters |
| **Format** | Dot-separated labels, each label ≥ 3 characters |
| **Label start** | Must start with lowercase letter `[a-z]` |
| **Label end** | Must end with lowercase letter or digit `[a-z0-9]` |
| **Label middle** | Lowercase letters, digits, or hyphens `[a-z0-9-]` |
| **Separator** | Dots `.` separate labels (e.g., `my.account`) |

**No uppercase letters are ever allowed.** No underscores. No consecutive dots. Each label between dots must independently satisfy the 3+ character rule with proper start/end characters.

### Asset Validation
**File:** `asset.cpp:261-286`, `validation.hpp`

**Asset symbol validation (`asset_symbol_type::validate()`):**
- Three legacy assets validated by asset_num: HIVE, HBD, VESTS
- Non-legacy assets (SMT NAI space): NAI data digits must be in range `[SMT_MIN_NAI=1, SMT_MAX_NAI=99999999]`, control bit set, decimal places ≤ `HIVE_ASSET_MAX_DECIMALS` (12)
- Damm checksum algorithm validates NAI integrity

**Native asset precision is fixed:**
| Asset | Precision | NAI |
|-------|-----------|-----|
| HIVE | 3 decimal places | @@000000021 |
| HBD | 3 decimal places | @@000000013 |
| VESTS | 6 decimal places | @@000000037 |

**Price validation (`price::validate()`):**
- Both base and quote must be > 0
- Base and quote symbols must differ

**Helper functions used across operations:**
| Helper | Check |
|--------|-------|
| `validate_asset_type(asset, symbol)` | Asset symbol matches expected |
| `validate_asset_type_one_of(asset, symbols)` | Asset symbol in allowed set |
| `validate_asset_greater_than_zero(asset)` | `amount > 0` |
| `validate_asset_not_negative(asset)` | `amount >= 0` |
| `validate_asset_is_not_vesting(asset)` | Symbol is not VESTS |

### String Validation Helpers
**File:** `validation.hpp:64-85`

| Helper | Check |
|--------|-------|
| `validate_string_max_size(str, max)` | `str.size() <= max` |
| `validate_is_utf8(str)` | Valid UTF-8 encoding |
| `validate_string_is_not_empty(str)` | `str.size() > 0` |

### Permlink Validation
**File:** `validation.hpp:111-115`

- Length: `< HIVE_MAX_PERMLINK_LENGTH` (256 characters) — note: strict less-than
- Encoding: Must be valid UTF-8

### JSON Validation
**File:** `hive_operations.cpp:22-33`

The `validate_json_with_fallback()` function:
1. First tries `fc::json::fast_is_valid()` (validates UTF-8 and JSON)
2. On failure, falls back to UTF-8 check + relaxed JSON validation (`fc::json::is_valid` with `relaxed` mode)

This fallback exists for replay compatibility — the old parser allowed some invalid JSON through.

### Authority Validation
**File:** `hive_operations.cpp:36-43`, `authority.cpp:47-55`

- `validate_auth_size()`: Total keys + accounts ≤ `HIVE_MAX_AUTHORITY_MEMBERSHIP` (40, or 41 in some builds)
- `authority::validate()`: Each account name in `account_auths` must be a valid account name

### Percent Validation
**File:** `validation.hpp:87-93`

- `validate_number_in_100_percent_range(n)`: `n <= HIVE_100_PERCENT` (10000)

---

## Per-Operation Validation

### account_create_operation (ID 9)
**File:** `hive_operations.cpp:45-66`

| Field | Constraint |
|-------|-----------|
| `new_account_name` | Valid account name |
| `fee` | Asset type HIVE, ≥ 0, ≤ `HIVE_MAX_ACCOUNT_CREATION_FEE` (1,000,000,000 = 1M HIVE) |
| `owner` | Authority validated (account names valid) |
| `active` | Authority validated |
| `posting` | Authority validated |
| `owner/active/posting` | Auth size ≤ 40 members each |
| `json_metadata` | If non-empty, valid JSON (with fallback) |

**Note:** The `creator` field is not validated here (only used for authority requirements).

### account_create_with_delegation_operation (ID 41)
**File:** `hive_operations.cpp:68-93`

Same as `account_create_operation` plus:

| Field | Constraint |
|-------|-----------|
| `creator` | Valid account name |
| `delegation` | Asset type VESTS, ≥ 0 |

**Note:** This operation is disabled since HF20 at the evaluator level.

### account_update_operation (ID 10)
**File:** `hive_operations.cpp:95-103`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `json_metadata` | If non-empty, valid JSON |

**Notable:** Does NOT validate auth sizes (comment in code: "unfortunately can't have validate_auth_size here").

### account_update2_operation (ID 43)
**File:** `hive_operations.cpp:105-121`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `owner` | If present, auth size validated |
| `active` | If present, auth size validated |
| `posting` | If present, auth size validated |
| `json_metadata` | If non-empty, valid JSON |
| `posting_json_metadata` | If non-empty, valid JSON |

### comment_operation (ID 1)
**File:** `hive_operations.cpp:123-138`

| Field | Constraint |
|-------|-----------|
| `title` | Size ≤ `HIVE_COMMENT_TITLE_LIMIT - 1` (255 chars), valid UTF-8 |
| `body` | Not empty, valid UTF-8 |
| `parent_author` | If non-empty, valid account name |
| `author` | Valid account name |
| `parent_permlink` | Valid permlink (< 256, UTF-8) |
| `permlink` | Valid permlink (< 256, UTF-8) |
| `json_metadata` | If non-empty, valid JSON |

**Note:** No max body size enforced at protocol level. Body size is effectively bounded by max transaction size (64KB). Comment depth is validated at chain level, not here.

### comment_payout_beneficiaries (extension struct)
**File:** `hive_operations.cpp:150-175`

| Field | Constraint |
|-------|-----------|
| `beneficiaries` | At least 1, less than `HIVE_BENEFICIARY_LIMIT` (128) |
| Each `beneficiary.account` | Valid account name |
| Each `beneficiary.weight` | ≤ 10000 (100%) |
| Cumulative weight | ≤ 10000 (100%) |
| **Order** | Beneficiaries must be sorted ascending by account name |

### comment_options_operation (ID 19)
**File:** `hive_operations.cpp:177-186`

| Field | Constraint |
|-------|-----------|
| `author` | Valid account name |
| `percent_hbd` | ≤ 10000 (100%) |
| `max_accepted_payout` | Asset type HBD, ≥ 0 |
| `permlink` | Valid permlink |
| `extensions` | Each extension validated (triggers beneficiaries validation) |

### delete_comment_operation (ID 17)
**File:** `hive_operations.cpp:188-192`

| Field | Constraint |
|-------|-----------|
| `permlink` | Valid permlink |
| `author` | Valid account name |

### claim_account_operation (ID 22)
**File:** `hive_operations.cpp:194-210`

| Field | Constraint |
|-------|-----------|
| `creator` | Valid account name |
| `fee` | Asset type HIVE, ≥ 0, ≤ `HIVE_MAX_ACCOUNT_CREATION_FEE` |
| `extensions` | Must be empty (size == 0) |

### create_claimed_account_operation (ID 23)
**File:** `hive_operations.cpp:212-231`

| Field | Constraint |
|-------|-----------|
| `creator` | Valid account name |
| `new_account_name` | Valid account name |
| `owner/active/posting` | Authority validated + auth size checked |
| `json_metadata` | If non-empty, valid JSON |
| `extensions` | Must be empty (size == 0) |

### vote_operation (ID 0)
**File:** `hive_operations.cpp:233-239`

| Field | Constraint |
|-------|-----------|
| `voter` | Valid account name |
| `author` | Valid account name |
| `weight` | `abs(weight) <= 10000` (±100%) |
| `permlink` | Valid permlink |

### transfer_operation (ID 2)
**File:** `hive_operations.cpp:241-249`

| Field | Constraint |
|-------|-----------|
| `from` | Valid account name |
| `to` | Valid account name |
| `amount` | Not VESTS, > 0 |
| `memo` | Size ≤ `HIVE_MAX_MEMO_SIZE - 1` (2047 chars), valid UTF-8 |

**Note:** `from != to` is NOT checked at protocol level (allowed to transfer to self).

### transfer_to_vesting_operation (ID 3)
**File:** `hive_operations.cpp:251-257`

| Field | Constraint |
|-------|-----------|
| `from` | Valid account name |
| `amount` | Asset type HIVE, > 0 |
| `to` | If not empty, valid account name (can be empty = power up to self) |

### withdraw_vesting_operation (ID 4)
**File:** `hive_operations.cpp:259-263`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `vesting_shares` | Asset type VESTS (no amount check — 0 is valid to cancel) |

### set_withdraw_vesting_route_operation (ID 20)
**File:** `hive_operations.cpp:265-274`

| Field | Constraint |
|-------|-----------|
| `from_account` | Valid account name |
| `to_account` | Valid account name |
| `percent` | `0 <= percent <= HIVE_100_PERCENT` (0–10000) |

### witness_update_operation (ID 11)
**File:** `hive_operations.cpp:276-285`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `url` | Size ≤ `HIVE_MAX_WITNESS_URL_LENGTH` (2048), not empty, valid UTF-8 |
| `fee` | ≥ 0 (any asset type!) |
| `props` | Legacy chain properties validated with `force_canon = false` |

**Legacy chain properties validation (non-canonical):**
- `account_creation_fee.amount` ≥ `HIVE_MIN_ACCOUNT_CREATION_FEE` (1 on mainnet, 0 on testnet)
- `account_creation_fee.amount` ≤ `HIVE_MAX_ACCOUNT_CREATION_FEE` (1,000,000,000)
- `maximum_block_size` ≥ `HIVE_MIN_BLOCK_SIZE_LIMIT` (65,536) and ≤ `HIVE_MAX_BLOCK_SIZE` (2,097,152 = 2MB)
- `hbd_interest_rate` ≥ 0 and ≤ 10000 (100%)

### witness_set_properties_operation (ID 42)
**File:** `hive_operations.cpp:287-396`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `props["key"]` | Must be present (current signing key) |
| `props["account_creation_fee"]` | If present: HIVE symbol, ≥ `HIVE_MIN_ACCOUNT_CREATION_FEE`, ≤ `HIVE_MAX_ACCOUNT_CREATION_FEE` |
| `props["maximum_block_size"]` | If present: ≥ `HIVE_MIN_BLOCK_SIZE_LIMIT` (65,536), ≤ `HIVE_MAX_BLOCK_SIZE` (2MB) |
| `props["sbd_interest_rate"]` or `props["hbd_interest_rate"]` | If present: ≥ 0, ≤ 10000 (100%) |
| `props["new_signing_key"]` | If present: must deserialize as valid public key |
| `props["sbd_exchange_rate"]` or `props["hbd_exchange_rate"]` | If present: base = HBD, quote = HIVE, price validated (both > 0) |
| `props["url"]` | If present: ≤ 2048 chars, not empty, valid UTF-8 |
| `props["account_subsidy_budget"]` | If present: ≥ `HIVE_RD_MIN_BUDGET` (1), ≤ `HIVE_RD_MAX_BUDGET` |
| `props["account_subsidy_decay"]` | If present: ≥ `HIVE_RD_MIN_DECAY` (64), ≤ `HIVE_RD_MAX_DECAY` (0xFFFFFFFF) |

**Note:** Property keys accept both legacy "sbd_" and current "hbd_" prefixes.

### account_witness_vote_operation (ID 12)
**File:** `hive_operations.cpp:398-402`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `witness` | Valid account name |

### account_witness_proxy_operation (ID 13)
**File:** `hive_operations.cpp:404-410`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `proxy` | If not clearing (not empty string), valid account name |
| **Cross-field** | `proxy != account` (cannot proxy to self) |

### custom_operation (ID 15)
**File:** `hive_operations.cpp:412-419`

| Field | Constraint |
|-------|-----------|
| `required_auths` | Size > 0, size ≤ `HIVE_MAX_AUTHORITY_MEMBERSHIP` (40) |

**Note:** No validation of data content or ID at protocol level. Data size limit enforced at chain level since HF26.

### custom_json_operation (ID 18)
**File:** `hive_operations.cpp:421-434`

| Field | Constraint |
|-------|-----------|
| Total auths | `required_auths.size() + required_posting_auths.size()` > 0 and ≤ 40 |
| `id` | Length ≤ `HIVE_CUSTOM_OP_ID_MAX_LENGTH` (32) |
| `json` | Valid JSON (with fallback) |

**Note:** No explicit max json size check in validate(), but bounded by max transaction size (64KB).

### custom_binary_operation (ID 35)
**File:** `hive_operations.cpp:436-455`

| Field | Constraint |
|-------|-----------|
| Total named auths | `required_owner_auths + required_active_auths + required_posting_auths` > 0 |
| Total all auths | Above + all key/account auths from `required_auths` vector ≤ 40 |
| `required_auths` | Each authority validated |
| `id` | Length ≤ `HIVE_CUSTOM_OP_ID_MAX_LENGTH` (32) |
| `data` | Size ≤ `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` (8192 bytes) |

**Note:** Disabled before HF14 at evaluator level.

### pow_operation (ID 14)
**File:** `hive_operations.cpp:465-476`

| Field | Constraint |
|-------|-----------|
| `props` | Legacy chain properties validated with `force_canon = true` |
| `worker_account` | Valid account name |
| `work.input` | Must match deterministic calculation from `block_id` and `nonce` |
| `work` | Validated (work hash ≠ all zeros) |

**Note:** Disabled since HF13. Work validation code partially eliminated (bip0062 mode).

### pow2_operation (ID 30)
**File:** `hive_operations.cpp:489-495`

| Field | Constraint |
|-------|-----------|
| `props` | Legacy chain properties validated with `force_canon = true` |
| `work` | Visitor validates the specific pow2 type |

**Note:** Disabled since HF17.

### feed_publish_operation (ID 7)
**File:** `hive_operations.cpp:592-598`

| Field | Constraint |
|-------|-----------|
| `publisher` | Valid account name |
| `exchange_rate` | Must be HIVE/HBD pair (either direction), price validated (both > 0, different symbols) |

### limit_order_create_operation (ID 5)
**File:** `hive_operations.cpp:601-618`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `amount_to_sell` / `min_to_receive` | Must be HIVE:HBD pair (either direction), OR one side can be SMT NAI paired with HIVE |
| Implied price | Validated as price (both > 0, different symbols) |

### limit_order_create2_operation (ID 21)
**File:** `hive_operations.cpp:620-640`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `amount_to_sell` | Must match `exchange_rate.base` symbol |
| `exchange_rate` | Price validated (both > 0, different symbols) |
| Market pair | HIVE:HBD (either direction) or SMT:HIVE |
| `amount_to_sell * exchange_rate` | Result > 0 (cannot round to zero) |

### limit_order_cancel_operation (ID 6)
**File:** `hive_operations.cpp:642-645`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |

### convert_operation (ID 8)
**File:** `hive_operations.cpp:647-654`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `amount` | Asset type HBD only, > 0 |

### collateralized_convert_operation (ID 48)
**File:** `hive_operations.cpp:656-662`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `amount` | Asset type HIVE only, > 0 |

### escrow_transfer_operation (ID 27)
**File:** `hive_operations.cpp:664-684`

| Field | Constraint |
|-------|-----------|
| `from`, `to`, `agent` | Valid account names |
| `fee` | ≥ 0, must be HIVE or HBD |
| `hbd_amount` | ≥ 0, asset type HBD |
| `hive_amount` | ≥ 0, asset type HIVE |
| **Cross-field** | At least one of hbd/hive amount > 0 |
| **Cross-field** | `from != agent` AND `to != agent` (agent is third party) |
| **Cross-field** | `ratification_deadline < escrow_expiration` |
| `json_meta` | If non-empty, valid JSON |

### escrow_approve_operation (ID 31)
**File:** `hive_operations.cpp:686-693`

| Field | Constraint |
|-------|-----------|
| `from`, `to`, `agent`, `who` | Valid account names |
| **Cross-field** | `who == to` OR `who == agent` |

### escrow_dispute_operation (ID 28)
**File:** `hive_operations.cpp:695-702`

| Field | Constraint |
|-------|-----------|
| `from`, `to`, `agent`, `who` | Valid account names |
| **Cross-field** | `who == from` OR `who == to` |

### escrow_release_operation (ID 29)
**File:** `hive_operations.cpp:704-718`

| Field | Constraint |
|-------|-----------|
| `from`, `to`, `agent`, `who`, `receiver` | Valid account names |
| **Cross-field** | `who` must be one of `from`, `to`, or `agent` |
| **Cross-field** | `receiver` must be `from` or `to` |
| `hbd_amount` | ≥ 0, asset type HBD |
| `hive_amount` | ≥ 0, asset type HIVE |
| **Cross-field** | At least one of hbd/hive amount > 0 |

### request_account_recovery_operation (ID 24)
**File:** `hive_operations.cpp:720-725`

| Field | Constraint |
|-------|-----------|
| `recovery_account` | Valid account name |
| `account_to_recover` | Valid account name |
| `new_owner_authority` | Authority validated (account names checked) |

### recover_account_operation (ID 25)
**File:** `hive_operations.cpp:727-736`

| Field | Constraint |
|-------|-----------|
| `account_to_recover` | Valid account name |
| `new_owner_authority` | Not impossible, weight_threshold > 0, validated |
| `recent_owner_authority` | Not impossible, validated |
| **Cross-field** | `new_owner_authority != recent_owner_authority` |

### change_recovery_account_operation (ID 26)
**File:** `hive_operations.cpp:738-742`

| Field | Constraint |
|-------|-----------|
| `account_to_recover` | Valid account name |
| `new_recovery_account` | Valid account name |

### transfer_to_savings_operation (ID 32)
**File:** `hive_operations.cpp:744-752`

| Field | Constraint |
|-------|-----------|
| `from`, `to` | Valid account names |
| `amount` | > 0, must be HIVE or HBD |
| `memo` | Size ≤ 2047, valid UTF-8 |

### transfer_from_savings_operation (ID 33)
**File:** `hive_operations.cpp:754-762`

| Field | Constraint |
|-------|-----------|
| `from`, `to` | Valid account names |
| `amount` | > 0, must be HIVE or HBD |
| `memo` | Size ≤ 2047, valid UTF-8 |

### cancel_transfer_from_savings_operation (ID 34)
**File:** `hive_operations.cpp:764-767`

| Field | Constraint |
|-------|-----------|
| `from` | Valid account name |

### decline_voting_rights_operation (ID 36)
**File:** `hive_operations.cpp:769-772`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |

### reset_account_operation (ID 37)
**File:** `hive_operations.cpp:774-777`

**Always fails** — `FC_ASSERT(false)` — placeholder, never used.

### set_reset_account_operation (ID 38)
**File:** `hive_operations.cpp:779-782`

**Always fails** — `FC_ASSERT(false)` — placeholder, never used.

### claim_reward_balance_operation (ID 39)
**File:** `hive_operations.cpp:784-796`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `reward_hive` | Asset type HIVE, ≥ 0 |
| `reward_hbd` | Asset type HBD, ≥ 0 |
| `reward_vests` | Asset type VESTS, ≥ 0 |
| **Cross-field** | At least one reward amount > 0 |

### delegate_vesting_shares_operation (ID 40)
**File:** `hive_operations.cpp:798-805`

| Field | Constraint |
|-------|-----------|
| `delegator` | Valid account name |
| `delegatee` | Valid account name |
| **Cross-field** | `delegator != delegatee` |
| `vesting_shares` | Asset type VESTS, ≥ 0 (0 = remove delegation) |

### recurrent_transfer_operation (ID 49)
**File:** `hive_operations.cpp:807-825`

| Field | Constraint |
|-------|-----------|
| `from`, `to` | Valid account names |
| `amount` | Not VESTS, ≥ 0 (0 = cancel recurrent transfer) |
| `recurrence` | ≥ `HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` (24 hours) |
| `memo` | Size ≤ 2047, valid UTF-8 |
| **Cross-field** | `from != to` |
| `executions` | ≥ 2 |
| `extensions` | May contain `recurrent_transfer_pair_id` (uint8_t) |

### witness_block_approve_operation (ID 16)
**File:** `hive_operations.cpp:827-830`

| Field | Constraint |
|-------|-----------|
| `witness` | Valid account name |

---

## DHF (Decentralized Hive Fund) Operations

### create_proposal_operation (ID 44)
**File:** `dhf_operations.cpp:7-23`

| Field | Constraint |
|-------|-----------|
| `creator` | Valid account name |
| `receiver` | Valid account name |
| `end_date` | Must be > `start_date` |
| `daily_pay` | ≥ 0, asset type HBD |
| `subject` | Not empty, ≤ `HIVE_PROPOSAL_SUBJECT_MAX_LENGTH` (80 chars), valid UTF-8 |
| `permlink` | Not empty, valid permlink |

### update_proposal_operation (ID 47)
**File:** `dhf_operations.cpp:25-38`

| Field | Constraint |
|-------|-----------|
| `creator` | Valid account name |
| `proposal_id` | ≥ 0 |
| `daily_pay` | ≥ 0, asset type HBD |
| `subject` | Not empty, ≤ 80 chars, valid UTF-8 |
| `permlink` | Not empty, valid permlink |

### update_proposal_votes_operation (ID 45)
**File:** `dhf_operations.cpp:40-49`

| Field | Constraint |
|-------|-----------|
| `voter` | Valid account name |
| `proposal_ids` | Not empty, size ≤ `HIVE_PROPOSAL_MAX_IDS_NUMBER` (5) |

### remove_proposal_operation (ID 46)
**File:** `dhf_operations.cpp:51-60`

| Field | Constraint |
|-------|-----------|
| `proposal_owner` | Valid account name |
| `proposal_ids` | Not empty, size ≤ `HIVE_PROPOSAL_MAX_IDS_NUMBER` (5) |

---

## Custom Operation (RC Delegation)

### delegate_rc_operation (custom_json sub-operation)
**File:** `hive_custom_operations.cpp:12-32`

| Field | Constraint |
|-------|-----------|
| `from` | Valid account name |
| `delegatees` | Size > 0, size ≤ `HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP` (100) |
| Each delegatee | Valid account name, not equal to `from` |
| `max_rc` | ≥ 0 |

---

## Operations With NO Protocol-Level validate()

These operations are virtual (generated by the chain, never broadcast) and their `validate()` always asserts false:
- All 43 virtual operations (IDs 50–92)

---

## Validation Constants Reference

| Constant | Value | Used By |
|----------|-------|---------|
| `HIVE_MIN_ACCOUNT_NAME_LENGTH` | 3 | Account name validation |
| `HIVE_MAX_ACCOUNT_NAME_LENGTH` | 16 | Account name validation |
| `HIVE_MAX_MEMO_SIZE` | 2048 (check is ≤ 2047) | transfer, savings, recurrent_transfer |
| `HIVE_MAX_PERMLINK_LENGTH` | 256 (check is < 256) | comment, comment_options, proposals |
| `HIVE_COMMENT_TITLE_LIMIT` | 256 (check is ≤ 255) | comment |
| `HIVE_MAX_WITNESS_URL_LENGTH` | 2048 | witness_update, witness_set_properties |
| `HIVE_MAX_AUTHORITY_MEMBERSHIP` | 40 | Authority size validation, custom ops |
| `HIVE_100_PERCENT` | 10000 | vote weight, HBD percent, interest rate |
| `HIVE_MAX_ACCOUNT_CREATION_FEE` | 1,000,000,000 | account_create, witness props |
| `HIVE_MIN_ACCOUNT_CREATION_FEE` | 1 (mainnet), 0 (testnet) | witness props |
| `HIVE_MAX_TRANSACTION_SIZE` | 65,536 (64KB) | Chain-level enforcement |
| `HIVE_MAX_TIME_UNTIL_EXPIRATION` | 3600 (1 hour) | Chain-level enforcement |
| `HIVE_MIN_BLOCK_SIZE_LIMIT` | 65,536 | witness props (= max tx size) |
| `HIVE_MAX_BLOCK_SIZE` | 2,097,152 (2MB) | witness props |
| `HIVE_BENEFICIARY_LIMIT` | 128 | comment_payout_beneficiaries |
| `HIVE_PROPOSAL_SUBJECT_MAX_LENGTH` | 80 | create/update proposal |
| `HIVE_PROPOSAL_MAX_IDS_NUMBER` | 5 | vote/remove proposal |
| `HIVE_CUSTOM_OP_ID_MAX_LENGTH` | 32 | custom_json, custom_binary |
| `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` | 8192 | custom_binary |
| `HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP` | 100 | delegate_rc |
| `HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` | 24 (hours) | recurrent_transfer |
| `HIVE_MAX_SATOSHIS` | 2^62 - 1 | Asset amount ceiling |
| `HIVE_ASSET_MAX_DECIMALS` | 12 | SMT/NAI assets |
| `HIVE_RD_MIN_BUDGET` | 1 | witness subsidy budget |
| `HIVE_RD_MAX_BUDGET` | ~2.1B (int32 max) | witness subsidy budget |
| `HIVE_RD_MIN_DECAY` | 64 | witness subsidy decay |
| `HIVE_RD_MAX_DECAY` | 0xFFFFFFFF | witness subsidy decay |
| `HIVE_EQUIHASH_N` | 140 | pow2 (equihash) |
| `HIVE_EQUIHASH_K` | 6 | pow2 (equihash) |
| `HIVE_PRECISION_HIVE` | 3 | Asset symbol validation |
| `HIVE_PRECISION_HBD` | 3 | Asset symbol validation |
| `HIVE_PRECISION_VESTS` | 6 | Asset symbol validation |

---

## Hardfork-Dependent Validation Changes

**Critical finding:** No hardfork-conditional logic exists in protocol-level `validate()` methods. ALL hardfork-dependent validation happens in chain-layer evaluators. This means the protocol validation is stable and deterministic regardless of hardfork state.

The chain-level evaluator changes supplement protocol validation with state-dependent checks:

### Operation Availability by Hardfork

| Hardfork | Operation | Change |
|----------|-----------|--------|
| HF13 | `pow_operation` | Deprecated — evaluator rejects |
| HF14 | `custom_binary_operation` | Enabled (was disabled) |
| HF17 | `pow2_operation` | Mining disabled — evaluator rejects |
| HF20 | `account_create_with_delegation` | Deprecated — evaluator rejects |
| HF20 | `claim_account_operation` | Enabled |
| HF20 | `create_claimed_account_operation` | Enabled |
| HF20 | `witness_set_properties_operation` | Enabled |
| HF21 | `account_update2_operation` | Enabled |
| HF21 | Proposal operations (44–46) | Enabled |
| HF24 | `update_proposal_operation` (47) | Enabled |
| HF25 | `recurrent_transfer_operation` (49) | Enabled |
| HF25 | `collateralized_convert_operation` (48) | Enabled |

### Evaluator-Level Validation Changes by Hardfork

| Hardfork | Area | Change |
|----------|------|--------|
| HF14 | Witness | Fee symbol canonicalization enforced |
| HF17 | Comments | Depth limit changed to 0xffff (soft limit 255) |
| HF19 | Comments | Delete forbidden if comment has positive votes |
| HF20 | Account creation | Exact fee requirement enforced (was minimum) |
| HF20 | Vesting withdrawal | Negative VESTS withdrawal blocked |
| HF20 | Delegation | Minimum delegation and update amounts introduced |
| HF21 | Comments | Edit frequency limit enforced |
| HF21 | Transfers | Treasury transfer validation tightened |
| HF24 | Comments | comment_options on already-paid comments forbidden |
| HF24 | Transfers | Treasury HIVE transfers require feed history |
| HF26 | Custom ops | Data size limits solidified from soft-fork to hard-fork |
| HF26 | Voting | Vote edit penalty removed |
| HF26 | Voting | Dust vote handling fixed |
| HF28 | Authority | Posting authority can be mixed with active in same tx |
| HF28 | Power down | Cancel power down fix |
| HF28 | Voting | Stable vote mechanism introduced |

---

## Key Discoveries

1. **No hardfork logic in validate():** Protocol-level validation is entirely hardfork-independent. This is a clean architectural separation — protocol defines structural rules, chain defines contextual rules.

2. **account_update_operation skips auth size validation:** Unlike all other account operations, `account_update_operation` does NOT validate authority membership sizes. The code has an explicit comment about this. This means an `account_update` can potentially set an authority with > 40 members, which would then need chain-level enforcement.

3. **transfer allows self-transfers:** `transfer_operation::validate()` does not check `from != to`. Self-transfers are structurally valid at the protocol level (though may be handled by evaluator).

4. **withdraw_vesting accepts zero amount:** No `amount > 0` check — zero VESTS is valid (used to cancel power-down).

5. **recurrent_transfer allows zero amount:** Amount ≥ 0 (not > 0). Zero amount is used to cancel a recurrent transfer.

6. **witness_update fee has no symbol check:** The `fee` in `witness_update_operation` is validated as `≥ 0` but has no asset type constraint at protocol level. It accepts any asset symbol.

7. **JSON validation has a fallback path:** For blockchain replay compatibility, the JSON validator falls back to a relaxed parser if the fast parser rejects the input. This means some malformed JSON that was historically accepted will continue to be accepted.

8. **comment body has no max size in validate():** Body size is only bounded by max transaction size (64KB). No explicit body size limit in the comment operation's validate().

9. **Proposal IDs batch limit is small:** Only 5 proposal IDs per vote/remove operation (`HIVE_PROPOSAL_MAX_IDS_NUMBER`), meaning batch operations on proposals are limited.

10. **reset_account and set_reset_account always fail:** These operations exist in the protocol but their validate() unconditionally asserts false. They are placeholders that were never implemented.

11. **Legacy "sbd_" property names still accepted:** `witness_set_properties` accepts both `sbd_interest_rate`/`sbd_exchange_rate` and `hbd_interest_rate`/`hbd_exchange_rate`.

---

## Code References

| File | Role |
|------|------|
| `libraries/protocol/hive_operations.cpp` | Main validate() implementations (866 lines) |
| `libraries/protocol/dhf_operations.cpp` | DHF operation validation (62 lines) |
| `libraries/protocol/hive_custom_operations.cpp` | RC delegation validation (34 lines) |
| `libraries/protocol/authority.cpp` | Account name validation + authority validation |
| `libraries/protocol/asset.cpp` | Asset symbol/price validation |
| `libraries/protocol/transaction.cpp` | Transaction-level validation |
| `libraries/protocol/include/hive/protocol/validation.hpp` | Validation helper functions |
| `libraries/protocol/include/hive/protocol/config.hpp` | All validation constants |
| `libraries/protocol/include/hive/protocol/hive_operations.hpp` | `legacy_chain_properties::validate()` template |
| `libraries/protocol/include/hive/protocol/asset_symbol.hpp` | NAI/asset constants |
| `libraries/protocol/include/hive/protocol/base.hpp` | `virtual_operation::validate()` (always fails) |

---

## Discrepancies and Potential Issues

1. **Inconsistent "off by one" patterns:** Some size checks use `<` (permlink: `size < 256`), others use `<= max - 1` (memo: `size <= 2047` where max is 2048), and others use `<= max` directly (title: `size <= 255` where limit is 256). The effective limits are the same but the patterns are inconsistent.

2. **witness_update_operation fee lacks symbol validation:** Unlike `account_create_operation` which requires HIVE, `witness_update_operation` allows any asset type for the fee. The evaluator may enforce this, but the protocol doesn't.

3. **account_update auth size gap:** `account_update_operation` doesn't validate authority membership sizes while `account_update2_operation` does. This creates an inconsistency where the older operation is less strict.

4. **Relaxed JSON fallback:** The `validate_json_with_fallback()` function accepts some malformed JSON for replay compatibility. This is documented behavior but could surprise application developers expecting strict JSON validation.

---

## Open Questions

1. **Custom operation JSON size limit:** `custom_json_operation` has no explicit json size limit in validate() — is there a chain-level enforcement beyond the 64KB transaction limit? (The HF26 solidification only mentions `custom_operation` data size.)

2. **SMT asset validation in limit orders:** The limit order operations allow SMT NAI assets paired with HIVE. Are there any chain-level checks that further restrict which NAI values are valid for market orders?

3. **Authority recursion depth:** While `HIVE_MAX_SIG_CHECK_DEPTH` (2) and `HIVE_MAX_SIG_CHECK_ACCOUNTS` (125) limit authority traversal, are these enforced only at signature verification time or also during validate()?

4. **Comment depth:** The protocol validate() for comments does not check depth. Is the soft max of 255 (`HIVE_SOFT_MAX_COMMENT_DEPTH`) enforced only in the evaluator?
