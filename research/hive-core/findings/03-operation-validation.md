# Findings: Operation Validation Rules

## Summary

Hive protocol-level validation is implemented in `validate()` methods on each operation struct, driven by `transaction::validate()` (`transaction.cpp:40-45`) which iterates operations and dispatches through `operation_validate_visitor` (`operation_util_impl.hpp:10-15`). These methods enforce *structural* correctness: field sizes, asset types, amount ranges, account name format, and cross-field consistency. `validate()` is **stateless** — it has no access to chain state, so balance, existence, authority-recursion, and hardfork checks are deferred to evaluators or to the signature-verification layer. Virtual operations have a `validate()` that always asserts false (they cannot be broadcast). **No hardfork-conditional logic exists in protocol-level validate() methods** — every version-dependent rule lives in the chain layer.

## General Validation Rules

### Transaction-Level Validation
**File:** `transaction.cpp:40-56`

- Transaction must have at least one operation (`HIVE_PROTOCOL_NUMBER_ASSERT( operations.size() > 0 )`).
- Each operation's `validate()` is invoked via `operation_validate_visitor`; exceptions are wrapped with `FC_CAPTURE_AND_RETHROW( (op) )`.
- The `validate( notify )` variant takes a callback with two arguments (the operation and a before/after flag) and calls it before and after each operation's `validate()` (`transaction.cpp:47-56`); its only caller with a callback is the benchmark dumper, which times each operation's validation (`database.cpp:2590-2603`). The checks are identical.
- Transaction expiration: max `HIVE_MAX_TIME_UNTIL_EXPIRATION` = 3600 seconds (1 hour) of runtime validity; since HF28 the field may be up to `HIVE_MAX_TIME_UNTIL_SIGNATURE_EXPIRATION` = 86400 s ahead (`database.cpp:2550-2562`) — enforced at chain level, **not** in validate().
- Max transaction size: not checked by validate(). The transaction push path (API or P2P) rejects a transaction larger than the witness-voted `maximum_block_size` minus 256 bytes (`database.cpp:566-572`), and a block as a whole must fit in `maximum_block_size` (since HF12, `database.cpp:2284-2286`). `HIVE_MAX_TRANSACTION_SIZE` (64 KiB) is not checked against transactions: in the code it only defines `HIVE_MIN_BLOCK_SIZE_LIMIT` (`config.hpp:363-364`), the floor for the voted `maximum_block_size` (`hive_operations.cpp:317`, `hive_operations.hpp:430`). The `get_config` API still reports it, like every `config.hpp` constant (`generate_get_config.cmake:53-59`).
- HF28 posting/active mixing rule: enforced during **signature verification** (`transaction_util.cpp:60-74`), not validate(). Pre-HF28 a transaction with posting-required operations cannot also have operations requiring active/owner/witness or `other` authorities. Guarded by `HIVE_HARDFORK_1_28_ALLOW_STRICT_AND_MIXED_AUTHORITIES` (`database.cpp:2626`).

### Base Class Contract
**File:** `base.hpp:13-29`

- `base_operation::validate()` is a no-op — any operation that inherits without overriding gets an empty check.
- `virtual_operation::validate()` always throws via `HIVE_PROTOCOL_UNREACHABLE_CODE_ASSERT( false )`. This is what makes virtual operations un-broadcastable.
- `base_operation::is_virtual()` returns `false`; `virtual_operation::is_virtual()` returns `true`. The `operation_validate` dispatcher does not special-case virtuals — an attempt to broadcast one simply hits the assert.

### Account Name Validation
**File:** `authority.cpp:57-122`, `validation.hpp:95-109`

`validate_account_name()` calls `detail::check_account_name()` which returns an enum; `validate_account_name()` then maps `too_short`/`too_long`/`invalid_sequence` to distinct `HIVE_PROTOCOL_ACCOUNT_NAME_ASSERT` failures.

| Rule | Constraint |
|------|-----------|
| **Total length** | `HIVE_MIN_ACCOUNT_NAME_LENGTH` (3) ≤ size ≤ `HIVE_MAX_ACCOUNT_NAME_LENGTH` (16) |
| **Labels** | Dot-separated; each label independently ≥ 3 chars (`if( end - begin < 3 ) return invalid_sequence` @ `authority.cpp:77`) |
| **Label start** | `[a-z]` only (explicit switch @ `authority.cpp:79-88`), not `[a-z0-9-]` |
| **Label end** | `[a-z0-9]` (explicit switch @ `authority.cpp:89-100`), no trailing hyphens |
| **Label middle** | `[a-z0-9-]` (explicit switch @ `authority.cpp:101-116`) |
| **Separator** | Dots `.` only (`name.find_first_of( '.', begin )`) |

**Consequence:** No uppercase, no underscores, no consecutive dots (would create a zero-length label and hit the `< 3` check), no hyphen at label boundaries, no top-level dot or empty trailing segment. The check is deterministic and the same at every hardfork.

`authority::validate()` (`authority.cpp:47-55`) walks `account_auths` and confirms each account name via `is_valid_account_name()`. It does **not** check weight_threshold bounds, `is_impossible()`, recursion depth, or membership size — those are separate concerns handled elsewhere.

### Asset Validation
**File:** `asset.cpp:261-286`, `validation.hpp:18-61`

**Asset symbol validation (`asset_symbol_type::validate()`):**
- Legacy assets (asset_num = HIVE/HBD/VESTS) pass unconditionally.
- Non-legacy (SMT NAI space): `nai_data_digits` in `[SMT_MIN_NAI=1, SMT_MAX_NAI=99999999]`, control bit = `SMT_ASSET_NUM_CONTROL_MASK`, decimal places <= `HIVE_ASSET_MAX_DECIMALS` (12). `asset_num` does not hold the Damm check digit: it is computed from the data digits for the string form (`to_nai()`, `asset.cpp:167-190`) and checked only when a NAI is converted to an `asset_num` (`asset_num_from_nai()`, `asset.cpp:128-140`).

**Important caveat:** `asset_symbol_type::validate()` is **not** called implicitly by `price::validate()` (`asset.cpp:329-335`) nor by the `validate_asset_type*` helpers, so operation validate() methods never check symbol integrity themselves. The gate is deserialization: binary unpacking calls `asset_symbol_type::validate()` on every symbol (`asset_symbol.hpp:189-216`), the JSON NAI form goes through `asset_num_from_nai()`, which checks the range, the Damm check digit and the decimals (`asset.cpp:643-671`, `:128-165`), and the legacy string form accepts only the native symbols (`asset.cpp:424-509`). Every symbol a node deserializes has passed these checks, so a malformed symbol can reach validate() only in an operation built in memory, for example by a client library.

**Native asset precision is fixed:**
| Asset | Precision | NAI (symbolic) |
|-------|-----------|----------------|
| HIVE | 3 | `@@000000021` |
| HBD | 3 | `@@000000013` |
| VESTS | 6 | `@@000000037` |

**Price validation (`price::validate()`):**
- Both base.amount and quote.amount must be > 0.
- base.symbol must ≠ quote.symbol.
- Does not recursively validate the two symbols themselves.

**Helper functions used across operations:**
| Helper | Check |
|--------|-------|
| `validate_asset_type(asset, symbol)` | `asset.symbol == symbol` |
| `validate_asset_type_one_of(asset, symbols)` | `asset.symbol` in allowed set |
| `validate_asset_greater_than_zero(asset)` | `amount > 0` |
| `validate_asset_not_negative(asset)` | `amount >= 0` |
| `validate_asset_is_not_vesting(asset)` | `!symbol.is_vesting()` |

### String Validation Helpers
**File:** `validation.hpp:63-85`

| Helper | Check | Idiom |
|--------|-------|-------|
| `validate_string_max_size(str, max)` | `str.size() <= max` | inclusive `<=` |
| `validate_is_utf8(str)` | `fc::is_utf8( str )` | |
| `validate_string_is_not_empty(str)` | `str.size() > 0` | |

### String-size idioms used in operation validate() methods
These three patterns all coexist in the codebase; they yield the same effective byte count but different apparent limits:

| Idiom | Example call | Constant | Effective max size (bytes) |
|-------|--------------|----------|----------------------------|
| `size() < MAX` | `validate_permlink` @ `validation.hpp:113` | `HIVE_MAX_PERMLINK_LENGTH = 256` | 255 |
| `size() <= MAX - 1` | `transfer_operation` memo @ `hive_operations.cpp:247` | `HIVE_MAX_MEMO_SIZE = 2048` | 2047 |
| `size() <= MAX - 1` | `comment_operation` title @ `hive_operations.cpp:125` | `HIVE_COMMENT_TITLE_LIMIT = 256` | 255 |
| `size() <= MAX` | `witness_update_operation` url @ `hive_operations.cpp:280` | `HIVE_MAX_WITNESS_URL_LENGTH = 2048` | 2048 |

Note the witness URL outlier: because it uses the inclusive `<=` pattern without `-1`, the URL can actually be **one byte longer** (2048) than the memo (2047) even though both constants are nominally 2048. This is not necessarily a bug — the constants weren't defined with a single consistent "max data" or "max data + length byte" convention — but it is an observable inconsistency that surfaces if you try to pack a 2048-byte memo.

### Permlink Validation
**File:** `validation.hpp:111-115`

- `permlink.size() < HIVE_MAX_PERMLINK_LENGTH` (256) -> effective max 255 bytes (`size()` counts bytes).
- Must be valid UTF-8 (`fc::is_utf8`).
- No lowercase/format check — unlike account names, permlinks permit any UTF-8 content under 256 bytes. Empty permlinks pass the protocol check; emptiness is only enforced by specific operations (e.g., DHF subject/permlink require non-empty via `validate_string_is_not_empty`).

### JSON Validation
**File:** `hive_operations.cpp:22-33`

The `validate_json_with_fallback()` function operates in two stages:
1. **Fast path**: `fc::json::fast_is_valid(json)` — validates both UTF-8 encoding and JSON grammar.
2. **Fallback path** (only if fast path rejects): explicit `validate_is_utf8(json)` then `fc::json::is_valid(json, format_validation_mode::relaxed)`.

The inline comment in the source explains why: "the old is_valid() test is slower and let some bad json through. For now, we're falling back to the old parser which will allow us to replay blocks that the old is_valid() allowed but shouldn't have." In practice this means some historically-accepted malformed JSON (e.g., trailing or missing commas; keys must still be quoted strings) remains accepted forever because rejecting it would make historical replays fail. **Application developers should not rely on strict JSON validation for inputs that round-trip through on-chain storage**: use a strict parser themselves if needed.

### Authority Validation
**File:** `hive_operations.cpp:36-43`, `authority.cpp:47-55`

- `validate_auth_size(a)`: `a.account_auths.size() + a.key_auths.size() <= HIVE_MAX_AUTHORITY_MEMBERSHIP` (40; 41 in converter builds via `#ifdef HIVE_CONVERTER_BUILD`).
- `authority::validate()`: Each account name in `account_auths` must satisfy `is_valid_account_name()`. Keys are not further validated here. The text form of a `public_key_type` is checked for the address prefix, its length and its checksum when it is parsed (`types.cpp:31-40`, through fc's `public_key::from_base58_with_prefix`); the binary form is any 33 bytes (`types.hpp:170`). Neither checks that the bytes encode a valid curve point.
- `authority::validate()` does **not**: check weight_threshold > 0, check `is_impossible()`, validate recursion depth, or check the sum of weights against `weight_threshold`. Most of those are instead enforced in signature verification.
- Signature verification (`verify_authority` -> `sign_state::check_authority_impl` in `sign_state.hpp:167-293`) enforces `HIVE_MAX_SIG_CHECK_DEPTH` (2 levels of account-auth recursion), `HIVE_MAX_AUTHORITY_MEMBERSHIP` (40 entries per authority) and `HIVE_MAX_SIG_CHECK_ACCOUNTS` (125 account authorities checked; counted per required authority before HF28 and across the whole transaction since HF28, `sign_state.hpp:88-91, 116-117`). The chain layer passes them in (`database.cpp:2626-2640`): the depth at every hardfork, the other two only from HF20 (before HF20 it passed 0, meaning no limit, `database.cpp:2634-2636`). The depth and account limits are therefore **never** touched by `validate()`; `HIVE_MAX_AUTHORITY_MEMBERSHIP` is also the `validate()` cap of `validate_auth_size` (above) and of the custom operations' authority counts (`hive_operations.cpp:416, 428, 448`).

### Percent Validation
**File:** `validation.hpp:87-93`

- `validate_number_in_100_percent_range(n)`: `n <= HIVE_100_PERCENT` (10000), with no lower bound, so a negative value of a signed type would pass. Its callers pass unsigned fields (beneficiary weights and their sum, `percent_hbd`, `hbd_interest_rate`) or `abs(weight)` (vote) (`hive_operations.cpp:162-172, 180, 237, 340`). `set_withdraw_vesting_route_operation` asserts `0 <= percent && percent <= HIVE_100_PERCENT` itself (`hive_operations.cpp:269-273`), but its `percent` is `uint16_t` (`hive_operations.hpp:387`), so the lower bound cannot fail.

---

## Per-Operation Validation

### account_create_operation (ID 9)
**File:** `hive_operations.cpp:45-66`

| Field | Constraint |
|-------|-----------|
| `new_account_name` | Valid account name |
| `fee` | Asset type HIVE, ≥ 0, ≤ `HIVE_MAX_ACCOUNT_CREATION_FEE` (1,000,000,000 = 1M HIVE on mainnet) |
| `owner` | Authority validated (account names valid) |
| `active` | Authority validated |
| `posting` | Authority validated |
| `owner/active/posting` | Each: `validate_auth_size` ≤ 40 members |
| `json_metadata` | If non-empty, valid JSON (with fallback) |

**Note:** The `creator` field is not validated here — only populated for authority derivation. The protocol doesn't even require it to be a valid account name (the evaluator `get_account( o.creator )` effectively enforces that at state-check time).

### account_create_with_delegation_operation (ID 41)
**File:** `hive_operations.cpp:68-93`

Same as `account_create_operation` plus:

| Field | Constraint |
|-------|-----------|
| `creator` | Valid account name (added here, unlike in `account_create`) |
| `delegation` | Asset type VESTS, ≥ 0 |

**Note:** Disabled at evaluator level since HF20.

### account_update_operation (ID 10)
**File:** `hive_operations.cpp:95-103`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `json_metadata` | If non-empty, valid JSON |

**Critical gap:** The source carries the comment `// unfortunately can't have validate_auth_size here`. The gap is filled in the evaluator (`hive_evaluator_account.cpp:283-291`) which runs `validate_auth_size` on each submitted authority **only when HF20 is active**. The historical reason, from the inline code comment at the evaluator call site: `3920d6b938492a873b36b3b44725154cf4123e95` is cited as an example of an authority exceeding 40 members, and, per the same comment, `hellosteem` has an even bigger authority to this day. Moving the check to validate() would make old blocks unreplayable.

### account_update2_operation (ID 43)
**File:** `hive_operations.cpp:105-121`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `owner` | If present (optional), auth size ≤ 40 |
| `active` | If present (optional), auth size ≤ 40 |
| `posting` | If present (optional), auth size ≤ 40 |
| `json_metadata` | If non-empty, valid JSON |
| `posting_json_metadata` | If non-empty, valid JSON |

Introduced in HF21 — no legacy accounts to protect — so the validate() can enforce size directly.

### comment_operation (ID 1)
**File:** `hive_operations.cpp:123-138`

| Field | Constraint |
|-------|-----------|
| `title` | `size() <= 255`, valid UTF-8 (empty title is allowed; title need not be present) |
| `body` | Not empty, valid UTF-8 |
| `parent_author` | If non-empty, valid account name (empty = root post) |
| `author` | Valid account name |
| `parent_permlink` | Valid permlink (< 256 bytes, UTF-8) |
| `permlink` | Valid permlink (< 256 bytes, UTF-8) |
| `json_metadata` | If non-empty, valid JSON (with fallback) |

**No max body size at protocol level.** The body is only bounded by the size of the containing transaction, which the push path limits to the witness-voted `maximum_block_size` minus 256 bytes (`database.cpp:566-572`); `HIVE_MAX_TRANSACTION_SIZE` (64 KiB) is not checked against transactions.

**No depth check at protocol level.** `HIVE_SOFT_MAX_COMMENT_DEPTH` (255) is enforced only in the chain layer, when the node is in control (`hive_evaluator_social.cpp:186-190`): `uint16_t depth_limit = !has_hardfork(HF17) ? HIVE_MAX_COMMENT_DEPTH_PRE_HF17 (6) : HIVE_MAX_COMMENT_DEPTH (0xffff); if (is_in_control() && depth_limit > HIVE_SOFT_MAX_COMMENT_DEPTH) depth_limit = HIVE_SOFT_MAX_COMMENT_DEPTH;`. `is_in_control()` is true while the node validates a new transaction or produces a block (`database.hpp:176`), so blocks from other producers and replayed blocks can contain deeper chains. Hivemind's own tree-walking logic is the practical floor for what users see.

### comment_payout_beneficiaries (extension struct)
**File:** `hive_operations.cpp:150-175`

| Field | Constraint |
|-------|-----------|
| `beneficiaries` | Size ≥ 1, `size() < HIVE_BENEFICIARY_LIMIT` (< 128, so max 127) |
| Each `beneficiary.account` | Valid account name |
| Each `beneficiary.weight` | ≤ 10000 |
| Running `sum` | ≤ 10000 (asserted at each step, so overflow is caught early) |
| **Order** | `beneficiaries[i-1] < beneficiaries[i]` strictly ascending by account name (comparison operator on the beneficiary struct itself) |

The size-strict-less-than (`< 128`) rather than `<= 128` is deliberate: the error message reads "Cannot specify more than ${max} beneficiaries" with `HIVE_BENEFICIARY_LIMIT - 1 = 127`, and the code comment notes "Require size serialization fits in one byte": the list size is serialized as an unsigned varint with 7 bits per byte, so 127 is the largest size that fits in one byte.

Beyond `validate()`, the evaluator limits the list to `HIVE_MAX_COMMENT_BENEFICIARIES` (8) entries when the node is in control, i.e. for new transactions and for blocks it produces (`hive_evaluator_social.cpp:123-124`, `config.hpp:272`); it is node policy, not a block validity rule.

### comment_options_operation (ID 19)
**File:** `hive_operations.cpp:177-186`

| Field | Constraint |
|-------|-----------|
| `author` | Valid account name |
| `percent_hbd` | ≤ 10000 |
| `max_accepted_payout` | Asset type HBD, ≥ 0 |
| `permlink` | Valid permlink |
| `extensions` | Each extension dispatched through `comment_options_extension_validate_visitor` → triggers `comment_payout_beneficiaries::validate` |

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
| `extensions` | Must be empty (size == 0) — hard zero, not a soft "unknown extension" pass-through |

### create_claimed_account_operation (ID 23)
**File:** `hive_operations.cpp:212-231`

| Field | Constraint |
|-------|-----------|
| `creator` | Valid account name |
| `new_account_name` | Valid account name |
| `owner/active/posting` | Each validated and auth size ≤ 40 |
| `json_metadata` | If non-empty, valid JSON |
| `extensions` | Must be empty |

### vote_operation (ID 0)
**File:** `hive_operations.cpp:233-239`

| Field | Constraint |
|-------|-----------|
| `voter` | Valid account name |
| `author` | Valid account name |
| `weight` | `abs(weight) <= HIVE_100_PERCENT` (±10000) |
| `permlink` | Valid permlink |

Note: `abs(weight)` is used (`int16`), so both `-10000` and `+10000` pass. `weight = 0` is structurally valid at validate() time.

### transfer_operation (ID 2)
**File:** `hive_operations.cpp:241-249`

| Field | Constraint |
|-------|-----------|
| `from` | Valid account name |
| `to` | Valid account name |
| `amount` | Not VESTS, > 0 |
| `memo` | `size() <= 2047`, valid UTF-8 |

**Note:** `from != to` is **not** checked — self-transfers pass protocol validation (and pass the evaluator, adjusting balances by zero net). The whole body is wrapped in `FC_CAPTURE_AND_RETHROW((*this))` so rejection reasons include the full operation.

### transfer_to_vesting_operation (ID 3)
**File:** `hive_operations.cpp:251-257`

| Field | Constraint |
|-------|-----------|
| `from` | Valid account name |
| `amount` | Asset type HIVE, > 0 |
| `to` | If not default (`account_name_type()` = empty string), valid account name (empty = power up to self) |

### withdraw_vesting_operation (ID 4)
**File:** `hive_operations.cpp:259-263`

| Field | Constraint |
|-------|-----------|
| `account` | Valid account name |
| `vesting_shares` | Asset type VESTS (no amount check — 0 is valid to cancel a power-down, and post-HF20 the evaluator rejects negative amounts) |

### set_withdraw_vesting_route_operation (ID 20)
**File:** `hive_operations.cpp:265-274`

| Field | Constraint |
|-------|-----------|
| `from_account` | Valid account name |
| `to_account` | Valid account name |
| `percent` | `0 <= percent <= HIVE_100_PERCENT` (explicit two-sided check, not just the helper) |

### witness_update_operation (ID 11)
**File:** `hive_operations.cpp:276-285`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `url` | `size() <= 2048`, non-empty, valid UTF-8 |
| `fee` | `>= 0` — **no asset symbol check at protocol level** |
| `props` | `legacy_chain_properties::validate<force_canon=false>` |

**The `fee` field is ignored by the evaluator entirely** (`hive_evaluator.cpp:62-99` does not reference `o.fee`). It is a vestigial field from the original design that pays the network to register the witness — the current behaviour is to create or update the witness without consuming the fee. Because `o.fee` is declared as `asset` (not `legacy_hive_asset`), any asset type passes the deserializer. `get_fee()` coerces to `HIVE_asset`, but nothing calls it.

**Legacy chain properties validation (`force_canon = false`):**
- `account_creation_fee.amount` >= `HIVE_MIN_ACCOUNT_CREATION_FEE` (1 on every network since 1.28.8, `config.hpp:274-275`; at 1.28.7 the testnet value was 0), <= `HIVE_MAX_ACCOUNT_CREATION_FEE` (1,000,000,000).
- `maximum_block_size` in `[HIVE_MIN_BLOCK_SIZE_LIMIT = 65,536, HIVE_MAX_BLOCK_SIZE = 2,097,152]`.
- `hbd_interest_rate` in `[0, 10000]`.
- `force_canon = false` means the fee's symbol ser byte can be non-canonical — at the evaluator, `witness_update_evaluator` asserts `o.props.account_creation_fee.symbol.is_canon()` from HF14 onward (`hive_evaluator.cpp:66-75`); pre-HF14 non-canonical serializations produced only a warning virtual op. 8 non-canonical fee symbols exist in mainnet history, which is why the check cannot be lifted into `validate()`.

### witness_set_properties_operation (ID 42)
**File:** `hive_operations.cpp:287-396`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `props["key"]` | Must be present; validate() does not check its value, the evaluator requires it to equal the witness's current signing key (`hive_evaluator.cpp:128-133`) |
| `props["account_creation_fee"]` | If present: HIVE symbol, ≥ `HIVE_MIN_ACCOUNT_CREATION_FEE`, ≤ `HIVE_MAX_ACCOUNT_CREATION_FEE` |
| `props["maximum_block_size"]` | If present: in `[HIVE_MIN_BLOCK_SIZE_LIMIT, HIVE_MAX_BLOCK_SIZE]` |
| `props["sbd_interest_rate"]` / `props["hbd_interest_rate"]` | If present: ≥ 0, ≤ 10000 |
| `props["new_signing_key"]` | If present: must deserialize as a valid `public_key_type` |
| `props["sbd_exchange_rate"]` / `props["hbd_exchange_rate"]` | If present: base = HBD, quote = HIVE, `price::validate` passes |
| `props["url"]` | If present: `size() <= 2048`, non-empty, valid UTF-8 |
| `props["account_subsidy_budget"]` | If present: ≥ `HIVE_RD_MIN_BUDGET` (1), ≤ `HIVE_RD_MAX_BUDGET` |
| `props["account_subsidy_decay"]` | If present: ≥ `HIVE_RD_MIN_DECAY` (64), ≤ `HIVE_RD_MAX_DECAY` (0xFFFFFFFF) |

**Legacy alias note:** The code looks up `sbd_interest_rate` first and falls back to `hbd_interest_rate` (same for exchange_rate, `hive_operations.cpp:327-329, 351-353`). Both may be present; the `sbd_` value is then the one checked and applied. At evaluator level HF24 gates the `hbd_` alias (`hive_evaluator.cpp:149-151, 171-173`).

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
| `proxy` | If not clearing (not default-constructed empty), valid account name |
| **Cross-field** | `proxy != account` (cannot proxy to self) — asserted even when clearing (clearing sets proxy to empty string, which won't equal a valid account name, so the check is effectively a no-op in that branch) |

### custom_operation (ID 15)
**File:** `hive_operations.cpp:412-419`

| Field | Constraint |
|-------|-----------|
| `required_auths` | `size > 0`, `size <= HIVE_MAX_AUTHORITY_MEMBERSHIP` (40) |

**No protocol-level content validation of `data` or `id`.** Chain-level: since HF26 (`HIVE_HARDFORK_1_26_SOLIDIFY_OLD_SOFTFORKS`), `hive_evaluator.cpp:330-334` enforces `o.data.size() <= HIVE_CUSTOM_OP_DATA_MAX_LENGTH` (8192 bytes). Before HF26 the same limit was only node policy: the evaluator applied it to new transactions the node accepted (added in 2018, commit `3fc6604e4`) and, from 2022, whenever the node was in control, which adds the blocks it produces (`53934a96f`), so blocks from other producers could carry larger operations; the HF26 change made it a consensus rule (`2441193ff`). The source comment names transaction `ab28c8e3a10d24f56476653d6a525e712e2e912e` as an example of a historically-large operation.

### custom_json_operation (ID 18)
**File:** `hive_operations.cpp:421-434`

| Field | Constraint |
|-------|-----------|
| Total auths | `required_auths.size() + required_posting_auths.size() > 0` and ≤ 40 |
| `id` | `size() <= HIVE_CUSTOM_OP_ID_MAX_LENGTH` (32) |
| `json` | Valid JSON (with fallback); UTF-8 validated |

**Chain-level size enforcement:** Since HF26, `hive_evaluator.cpp:343-344` asserts `o.json.length() <= HIVE_CUSTOM_OP_DATA_MAX_LENGTH` (8192 bytes) via `HIVE_CHAIN_LIMIT_ASSERT`. The source comment names transaction `803bcc0dae4d242e0a6539948d998a4410b19655` as an example of a historically-large custom_json. Pre-HF26 the same 8192-byte limit was node policy applied by the evaluator (see `custom_operation` above). The transaction size limit of the push path (voted `maximum_block_size` minus 256 bytes, `database.cpp:566-572`) still applies as an upper ceiling.

Only one chain-interpreted `id` exists: `"rc"` → routed to `generic_custom_operation_interpreter` to dispatch `delegate_rc_operation` etc. Other IDs are app-layer (Hivemind, leofinance, etc.) — not touched by hived.

### custom_binary_operation (ID 35)
**File:** `hive_operations.cpp:436-455`

| Field | Constraint |
|-------|-----------|
| Total named auths | `required_owner_auths + required_active_auths + required_posting_auths > 0` |
| Total all auths | Named + sum of each `authority`'s `(key_auths.size() + account_auths.size())` from `required_auths` ≤ 40 |
| Each `required_auths[i]` | `authority::validate()` (account names valid) |
| `id` | `size() <= HIVE_CUSTOM_OP_ID_MAX_LENGTH` (32) |
| `data` | `size() <= HIVE_CUSTOM_OP_DATA_MAX_LENGTH` (8192) — protocol-level, no HF gate |

**Disabled at evaluator level:** `custom_binary_evaluator::do_apply` immediately throws `HIVE_CHAIN_UNREACHABLE_CODE_ASSERT(false, "Operation disallowed.")` (`hive_evaluator.cpp:376-379`). The operation keeps its slot in the operation variant, but no transaction containing it can be applied; the source comment says no one used it in practice and that it waits for a possible redesign.

### pow_operation (ID 14)
**File:** `hive_operations.cpp:465-476`

| Field | Constraint |
|-------|-----------|
| `props` | `legacy_chain_properties::validate<force_canon=true>` — the stricter variant |
| `worker_account` | Valid account name |
| `work.input` | Must equal deterministic hash from `block_id` and `nonce` |
| `work` | `pow::validate()` asserts `work != sha256()` (all-zero proof rejected) |

Wrapped in `#ifndef HIVE_CONVERTER_BUILD` — the blockchain_converter tool skips this validation entirely. Disabled at evaluator level since HF13. Comments in `pow::validate()` mention that the original ECDSA-recovery check was removed after the switch to bip0062-only signatures — historic pow ops remain valid because they are already in blocks.

### pow2_operation (ID 30)
**File:** `hive_operations.cpp:489-495`

| Field | Constraint |
|-------|-----------|
| `props` | `legacy_chain_properties::validate<force_canon=true>` |
| `work` | Visitor dispatches to `pow2::validate()` or `equihash_pow::validate()` |

`pow2::validate()` (`hive_operations.cpp:572-578`): validates `input.worker_account` is a valid account name; historic pow_summary check is commented-out. `equihash_pow::validate()` (`hive_operations.cpp:580-590`): validates worker account, `proof.n == HIVE_EQUIHASH_N (140)`, `proof.k == HIVE_EQUIHASH_K (6)`, `proof.seed` matches computed seed, `proof.is_valid()`, `pow_summary` matches recomputation. Disabled at evaluator level since HF17.

### feed_publish_operation (ID 7)
**File:** `hive_operations.cpp:592-598`

| Field | Constraint |
|-------|-----------|
| `publisher` | Valid account name |
| `exchange_rate` | Base/quote must be HIVE/HBD in either order; `price::validate()` (both > 0, different symbols) |

### limit_order_create_operation (ID 5)
**File:** `hive_operations.cpp:601-618`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| Market pair | `HIVE:HBD` (either direction) OR one side is SMT NAI (space) and the other side is HIVE |
| Implied price | `price(amount_to_sell, min_to_receive).validate()` — both > 0, symbols differ |

**SMT-in-limit-order reality check:** Protocol `validate()` allows SMT NAI paired with HIVE. However:
1. `price::validate()` does **not** call `asset_symbol_type::validate()`, and every symbol other than HIVE, HBD and VESTS counts as smt_nai_space (`asset.cpp:245-259`), so `validate()` itself never checks the NAI; symbol integrity is checked when the operation is deserialized (see the caveat under Asset Validation).
2. Without the market check of item 3, the evaluator debits the seller through `database::adjust_balance()` (`hive_evaluator_transfer.cpp:561-563`), which accepts only HIVE and HBD (`database.cpp:3179-3198`: `FC_ASSERT( ( delta.symbol.asset_num == HIVE_ASSET_NUM_HBD ) && "liquid", "invalid symbol" )`). An order that sells an SMT symbol therefore fails, while an order that sells HIVE for an SMT symbol is funded from the seller's HIVE and created, but can never fill because no SMT balances exist, so it stays open until it expires or is cancelled; a `fill_or_kill` order of that kind fails instead (`hive_evaluator_transfer.cpp:565-570`).
3. Since 1.28.8 both evaluators accept only the HIVE:HBD market under HF29 (`HIVE_HARDFORK_1_29_FIX_LIMIT_ORDER_ASSETS`, defined in 1.28.8, inactive on mainnet), and a 1.28.8 node already rejects other markets in new transactions submitted to it and in blocks it produces (`hive_evaluator_transfer.cpp:540-546`; Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)).

The 1.28.7 inline `FC_TODO( "Limit to HIVE/HBD after next hardfork (HF29)" )` is replaced since 1.28.8 by that check and the comment "once HF29 triggers try trimming the check in validate" (`hive_evaluator_transfer.cpp:540`). Conclusion: SMT limit orders are protocol-allowed; the evaluator's market check (applied when the node is in control since 1.28.8, and in every block under HF29) is what restricts orders to HIVE:HBD.

### limit_order_create2_operation (ID 21)
**File:** `hive_operations.cpp:620-640`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `amount_to_sell` | Symbol must equal `exchange_rate.base.symbol` |
| `exchange_rate` | `price::validate()` (both > 0, symbols differ) |
| Market pair | `HIVE:HBD` (either direction) OR SMT_NAI + HIVE (either direction) |
| `amount_to_sell * exchange_rate` | Must be > 0 (cannot round to zero once traded) |

Same SMT caveat as `limit_order_create` (market check at `hive_evaluator_transfer.cpp:578-584`, seller debit at `:596-598`, `fill_or_kill` at `:605`).

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

Code comment: "only allow conversion from HBD to HIVE, allowing the opposite can enable traders to abuse market fluxuations through converting large quantities without moving the price." This is a protocol-level one-way restriction; `collateralized_convert_operation` is the HIVE→HBD counterpart added in HF25.

### collateralized_convert_operation (ID 48)
**File:** `hive_operations.cpp:656-662`

| Field | Constraint |
|-------|-----------|
| `owner` | Valid account name |
| `amount` | Asset type HIVE only, > 0 |

Code comment: "only allow conversion from HIVE to HBD (at least for now)". Enabled since HF25 (evaluator asserts HF25 at dispatch).

### escrow_transfer_operation (ID 27)
**File:** `hive_operations.cpp:664-684`

| Field | Constraint |
|-------|-----------|
| `from`, `to`, `agent` | Valid account names |
| `fee` | ≥ 0, asset ∈ {HIVE, HBD} |
| `hbd_amount` | ≥ 0, asset type HBD |
| `hive_amount` | ≥ 0, asset type HIVE |
| **Cross-field** | `hbd_amount.amount > 0 || hive_amount.amount > 0` |
| **Cross-field** | `from != agent && to != agent` |
| **Cross-field** | `ratification_deadline < escrow_expiration` |
| `json_meta` | If non-empty, valid JSON |

### escrow_approve_operation (ID 31)
**File:** `hive_operations.cpp:686-693`

| Field | Constraint |
|-------|-----------|
| `from`, `to`, `agent`, `who` | Valid account names |
| **Cross-field** | `who == to || who == agent` |

### escrow_dispute_operation (ID 28)
**File:** `hive_operations.cpp:695-702`

| Field | Constraint |
|-------|-----------|
| `from`, `to`, `agent`, `who` | Valid account names |
| **Cross-field** | `who == from || who == to` |

### escrow_release_operation (ID 29)
**File:** `hive_operations.cpp:704-718`

| Field | Constraint |
|-------|-----------|
| `from`, `to`, `agent`, `who`, `receiver` | Valid account names |
| **Cross-field** | `who ∈ {from, to, agent}` |
| **Cross-field** | `receiver ∈ {from, to}` |
| `hbd_amount` | ≥ 0, asset type HBD |
| `hive_amount` | ≥ 0, asset type HIVE |
| **Cross-field** | `hbd_amount.amount > 0 || hive_amount.amount > 0` |

### request_account_recovery_operation (ID 24)
**File:** `hive_operations.cpp:720-725`

| Field | Constraint |
|-------|-----------|
| `recovery_account` | Valid account name |
| `account_to_recover` | Valid account name |
| `new_owner_authority` | `authority::validate()` (account names checked) |

### recover_account_operation (ID 25)
**File:** `hive_operations.cpp:727-736`

| Field | Constraint |
|-------|-----------|
| `account_to_recover` | Valid account name |
| `new_owner_authority` | `weight_threshold > 0` (trivial rejected), `!is_impossible()`, `validate()` |
| `recent_owner_authority` | `!is_impossible()`, `validate()` |
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
| `amount` | > 0, asset ∈ {HIVE, HBD} |
| `memo` | `size() <= 2047`, valid UTF-8 |

### transfer_from_savings_operation (ID 33)
**File:** `hive_operations.cpp:754-762`

| Field | Constraint |
|-------|-----------|
| `from`, `to` | Valid account names |
| `amount` | > 0, asset ∈ {HIVE, HBD} |
| `memo` | `size() <= 2047`, valid UTF-8 |

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

### reset_account_operation (ID 37) — placeholder
**File:** `hive_operations.cpp:774-777`

Always fails — `FC_ASSERT( false && "placeholder1" )`.

### set_reset_account_operation (ID 38) — placeholder
**File:** `hive_operations.cpp:779-782`

Always fails — `FC_ASSERT( false && "placeholder2" )`.

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
**File:** `hive_operations.cpp:807-826`

| Field | Constraint |
|-------|-----------|
| `from`, `to` | Valid account names |
| `amount` | Not VESTS, ≥ 0 (0 = cancel) |
| `recurrence` | ≥ `HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` (24 hours) |
| `memo` | `size() <= 2047`, valid UTF-8 |
| **Cross-field** | `from != to` |
| `executions` | >= 1 since 1.28.8 (`hive_operations.cpp:820-824`; >= 2 at 1.28.7); the minimum of 2 is enforced by the evaluator (see below) |
| `extensions` | May contain a `recurrent_transfer_pair_id` (`uint8_t`) — not validated at protocol level beyond being a valid extension variant |

**Chain-level limits:** `HIVE_MAX_OPEN_RECURRENT_TRANSFERS` (255 per account) and `HIVE_MAX_RECURRENT_TRANSFER_END_DATE` (730 days) are enforced at evaluator time (`hive_evaluator_transfer.cpp:969, 980-981, 1025-1026`). Since 1.28.8 the evaluator also enforces the minimum of `executions`: at least 2 to create a transfer (`:976-978`), and at least 2 to modify or delete one before HF29 (`:991-996`, `:1011-1016`). Under HF29 (`HIVE_HARDFORK_1_29_ALLOW_MODIFY_LAST_RECURRENT_TRANSFER`, defined in 1.28.8, inactive on mainnet) an existing transfer may be modified or deleted with `executions == 1` (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)).

### witness_block_approve_operation (ID 16)
**File:** `hive_operations.cpp:828-831`

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
| `end_date` | `> start_date` |
| `daily_pay` | ≥ 0, asset type HBD |
| `subject` | Non-empty, `size() <= HIVE_PROPOSAL_SUBJECT_MAX_LENGTH` (80), valid UTF-8 |
| `permlink` | Non-empty, valid permlink (< 256 bytes, UTF-8) |

Note: `start_date < end_date` is enforced but not `start_date >= now` — the evaluator handles past-start-date cases.

### update_proposal_operation (ID 47)
**File:** `dhf_operations.cpp:25-38`

| Field | Constraint |
|-------|-----------|
| `creator` | Valid account name |
| `proposal_id` | ≥ 0 |
| `daily_pay` | ≥ 0, asset type HBD |
| `subject` | Non-empty, <= 80 bytes (`validate_string_max_size`), valid UTF-8 |
| `permlink` | Non-empty, valid permlink |

### update_proposal_votes_operation (ID 45)
**File:** `dhf_operations.cpp:40-49`

| Field | Constraint |
|-------|-----------|
| `voter` | Valid account name |
| `proposal_ids` | Non-empty, `size() <= HIVE_PROPOSAL_MAX_IDS_NUMBER` (5) |

### remove_proposal_operation (ID 46)
**File:** `dhf_operations.cpp:51-60`

| Field | Constraint |
|-------|-----------|
| `proposal_owner` | Valid account name |
| `proposal_ids` | Non-empty, size ≤ 5 |

---

## Custom Operation Sub-Operations (RC delegation)

### delegate_rc_operation (custom_json sub-operation, `id == "rc"`)
**File:** `hive_custom_operations.cpp:12-32`

| Field | Constraint |
|-------|-----------|
| `from` | Valid account name |
| `delegatees` | `size > 0`, size ≤ `HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP` (100) |
| Each delegatee | Valid account name, `delegatee != from` |
| `max_rc` | ≥ 0 |

This operation reaches `validate()` only via the custom_json dispatch path (`generic_custom_operation_interpreter`) after `custom_json_operation::validate()` has already succeeded on the wrapper.

---

## Operations With NO Protocol-Level validate()

All 43 virtual operations (IDs 50–92) inherit `virtual_operation::validate()` which asserts false via `HIVE_PROTOCOL_UNREACHABLE_CODE_ASSERT`. An attempt to include one in a broadcast transaction fails at `transaction::validate()` — specifically inside `operation_validate_visitor::operator()`.

---

## Chain-level Enforcement Complementing validate()

`validate()` does not see chain state, so several limits that look protocol-level are actually enforced only at evaluator time. This table is the map of what `validate()` does *not* enforce but the chain does:

| Concern | validate() enforces? | Chain (evaluator/verify) enforces | Source |
|---------|:---:|---|---|
| Transaction size <= voted `maximum_block_size` minus 256 bytes (`HIVE_MAX_TRANSACTION_SIZE` is not checked) | no | transaction push path (API or P2P), not block validity | `database.cpp:566-572` |
| Transaction expiration ≤ 1h from head (field ≤ 24h since HF28, runtime capped at 1h) | no | chain | `HIVE_MAX_TIME_UNTIL_EXPIRATION`, `HIVE_MAX_TIME_UNTIL_SIGNATURE_EXPIRATION` |
| Posting cannot mix with active, owner, witness or other authorities pre-HF28 (`other`: the explicit authorities that `witness_set_properties`, `custom_binary`, `pow2` and `recover_account` require, `hive_operations.hpp:475, 564, 751, 851`) | no | `verify_authority_impl` | `transaction_util.cpp:62-74` |
| Authority recursion depth ≤ 2 | no | `sign_state::check_authority_impl` | `sign_state.hpp:216-220` |
| Account authorities checked in verification <= 125 (HF20+; per required authority before HF28, per transaction since HF28) | no | `sign_state::check_authority_impl` | `sign_state.hpp:226-233` |
| `account_update` auth size ≤ 40 | **no** | evaluator HF20+ | `hive_evaluator_account.cpp:283-291` |
| `witness_update.props.account_creation_fee` symbol canonical | no | evaluator HF14+ | `hive_evaluator.cpp:66-75` |
| `custom_operation.data.size() ≤ 8192` | no | evaluator HF26+ | `hive_evaluator.cpp:330-334` |
| `custom_json_operation.json.length() ≤ 8192` | no | evaluator HF26+ | `hive_evaluator.cpp:343-344` |
| custom, custom_json and custom_binary operations per account across a node's pending transactions <= 5 (`HIVE_CUSTOM_OP_BLOCK_LIMIT` on mainnet) | no | transaction push path (node policy), not block validity | `database.cpp:598-621` |
| Comment depth <= 0xffff (hard) / 255 (soft, when in control) | no | evaluator HF17+ | `hive_evaluator_social.cpp:186-190` |
| Beneficiaries per comment <= 8 (`HIVE_MAX_COMMENT_BENEFICIARIES`; validate() allows 127) | no | evaluator, when in control (node policy, not block validity) | `hive_evaluator_social.cpp:123-124` |
| `recurrent_transfer` open count ≤ 255 per account | no | evaluator HF25+ | `hive_evaluator_transfer.cpp:969` |
| `recurrent_transfer` end-date ≤ 730 days | no | evaluator HF25+ | `hive_evaluator_transfer.cpp:980` |
| `recurrent_transfer` executions >= 2 (create always; modify and delete before HF29) | no since 1.28.8 (validate() checks >= 1) | evaluator | `hive_evaluator_transfer.cpp:976-978, 991-996, 1011-1016` |
| Limit orders only on the HIVE:HBD market | partial (also admits SMT NAI paired with HIVE) | evaluator market check, when in control since 1.28.8 and in every block under HF29; otherwise `database::adjust_balance` rejects only orders that sell an SMT symbol | `hive_evaluator_transfer.cpp:540-546, 578-584`; `database.cpp:3179-3198` |
| Account existence (from, to, creator, etc.) | no | evaluator (via `get_account`) | many |
| Balance sufficiency | no | evaluator / `adjust_balance` | `database.cpp:3202-3207, 3229-3234` |

---

## Validation Constants Reference

| Constant | Value | Used By |
|----------|-------|---------|
| `HIVE_MIN_ACCOUNT_NAME_LENGTH` | 3 | Account name validation |
| `HIVE_MAX_ACCOUNT_NAME_LENGTH` | 16 | Account name validation |
| `HIVE_MAX_MEMO_SIZE` | 2048 (effective cap 2047 via `- 1`) | transfer, savings, recurrent_transfer |
| `HIVE_MAX_PERMLINK_LENGTH` | 256 (effective cap 255 via `<`) | comment, comment_options, proposals, vote, delete_comment |
| `HIVE_COMMENT_TITLE_LIMIT` | 256 (effective cap 255 via `- 1`) | comment |
| `HIVE_MAX_WITNESS_URL_LENGTH` | 2048 (effective cap 2048 via `<=`) | witness_update, witness_set_properties |
| `HIVE_MAX_AUTHORITY_MEMBERSHIP` | 40 (41 in converter builds) | Authority size validation, custom ops |
| `HIVE_100_PERCENT` | 10000 | vote weight, HBD percent, interest rate |
| `HIVE_MAX_ACCOUNT_CREATION_FEE` | 1,000,000,000 | account_create, claim_account, witness props |
| `HIVE_MIN_ACCOUNT_CREATION_FEE` | 1 (every network since 1.28.8; testnet 0 at 1.28.7) | witness props |
| `HIVE_MAX_TRANSACTION_SIZE` | 65,536 (64 KiB) | In the code only used to define `HIVE_MIN_BLOCK_SIZE_LIMIT`; not checked against transactions; reported by `get_config` |
| `HIVE_MAX_TIME_UNTIL_EXPIRATION` | 3600 (1 hour; HF28+: field limit 86400, runtime cap 3600) | Chain-level |
| `HIVE_MIN_BLOCK_SIZE_LIMIT` | 65,536 | witness props (= `HIVE_MAX_TRANSACTION_SIZE`) |
| `HIVE_MAX_BLOCK_SIZE` | 2,097,152 (2MB) | witness props |
| `HIVE_BENEFICIARY_LIMIT` | 128 (effective cap 127 via `<`) | comment_payout_beneficiaries |
| `HIVE_PROPOSAL_SUBJECT_MAX_LENGTH` | 80 | create/update proposal |
| `HIVE_PROPOSAL_MAX_IDS_NUMBER` | 5 | vote/remove proposal |
| `HIVE_CUSTOM_OP_ID_MAX_LENGTH` | 32 | custom_json, custom_binary |
| `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` | 8192 | custom_binary (validate), custom/custom_json (chain-level, HF26+) |
| `HIVE_CUSTOM_OP_BLOCK_LIMIT` | 5 (mainnet) | Custom operations per account in a node's pending transactions (push path, node policy) |
| `HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP` | 100 | delegate_rc |
| `HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` | 24 (hours) | recurrent_transfer |
| `HIVE_MAX_SATOSHIS` | 2^62 - 1 | Asset amount ceiling (implicit via asset impl) |
| `HIVE_ASSET_MAX_DECIMALS` | 12 | SMT/NAI asset symbols |
| `HIVE_RD_MIN_BUDGET` | 1 | witness subsidy budget |
| `HIVE_RD_MAX_BUDGET` | `min(2^34-1, 2^28-1, INT32_MAX)` = 2^28-1 = 268,435,455 (`config.hpp:394-399`) | witness subsidy budget |
| `HIVE_RD_MIN_DECAY` | 64 (= 2^6) | witness subsidy decay |
| `HIVE_RD_MAX_DECAY` | 0xFFFFFFFF | witness subsidy decay |
| `HIVE_EQUIHASH_N` | 140 | pow2 (equihash) |
| `HIVE_EQUIHASH_K` | 6 | pow2 (equihash) |
| `HIVE_PRECISION_HIVE` / `HIVE_PRECISION_HBD` / `HIVE_PRECISION_VESTS` | 3 / 3 / 6 | Asset symbol validation |
| `SMT_MIN_NAI` / `SMT_MAX_NAI` | 1 / 99999999 | SMT NAI data-digit range |
| `HIVE_MAX_SIG_CHECK_DEPTH` | 2 | Signature verification (chain) — not validate() |
| `HIVE_MAX_SIG_CHECK_ACCOUNTS` | 125 | Signature verification (chain) — not validate() |
| `HIVE_SOFT_MAX_COMMENT_DEPTH` | 255 | Comment depth (chain, `is_in_control()` only) |
| `HIVE_MAX_COMMENT_BENEFICIARIES` | 8 | Beneficiaries per comment (chain, `is_in_control()` only) |
| `HIVE_MAX_COMMENT_DEPTH` | 65535 | Comment depth hard limit (chain, HF17+) |
| `HIVE_MAX_COMMENT_DEPTH_PRE_HF17` | 6 | Comment depth pre-HF17 |
| `HIVE_MAX_OPEN_RECURRENT_TRANSFERS` | 255 | Per-account cap (chain) |
| `HIVE_MAX_RECURRENT_TRANSFER_END_DATE` | 730 (days) | Chain-level |

---

## Hardfork-Dependent Validation Changes

**Critical finding reaffirmed:** No hardfork-conditional logic exists in protocol-level `validate()` methods. A grep for `has_hardfork` across `libraries/protocol/hive_operations.cpp`, `dhf_operations.cpp`, `hive_custom_operations.cpp`, and `validation.hpp` yields zero hits. ALL hardfork-dependent validation happens in chain-layer evaluators or in `verify_authority`. This means protocol validation is stable and deterministic regardless of hardfork state — a valid transaction by `validate()` standards alone may still be rejected by the chain layer depending on when it arrives.

### Operation Availability by Hardfork

| Hardfork | Operation | Change (evaluator-gated) |
|----------|-----------|--------------------------|
| HF13 | `pow_operation` | Rejected at evaluator |
| HF14 | `custom_binary_operation` | Enabled (later disabled again via unreachable assert) |
| HF17 | `pow2_operation` | Rejected at evaluator |
| HF20 | `account_create_with_delegation_operation` | Rejected at evaluator |
| HF20 | `claim_account_operation` | Enabled |
| HF20 | `create_claimed_account_operation` | Enabled |
| HF20 | `witness_set_properties_operation` | Enabled |
| HF21 | `account_update2_operation` | Enabled |
| HF21 | DHF proposal ops (44–46) | Enabled |
| HF24 | `update_proposal_operation` (47) | Enabled |
| HF25 | `recurrent_transfer_operation` (49) | Enabled |
| HF25 | `collateralized_convert_operation` (48) | Enabled |

### Evaluator-Level Validation Changes by Hardfork

| Hardfork | Area | Change |
|----------|------|--------|
| HF14 | Witness | `account_creation_fee.symbol.is_canon()` enforced (`hive_evaluator.cpp:66-75`) |
| HF15 | account_update | posting authority validated via `verify_authority_accounts_exist` |
| HF17 | Comments | Hard depth limit 0xffff (soft limit 255 when in control) |
| HF19 | Comments | Delete forbidden if comment has positive votes |
| HF20 | account_update | `validate_auth_size` added at evaluator (`hive_evaluator_account.cpp:283-291`) |
| HF20 | Authority | `HIVE_MAX_AUTHORITY_MEMBERSHIP` and `HIVE_MAX_SIG_CHECK_ACCOUNTS` caps activated in `verify_authority` (`database.cpp:2635-2636`; the depth limit applies at every hardfork, `:2634`) |
| HF20 | Account creation | Exact fee requirement enforced (was minimum) |
| HF20 | Vesting withdrawal | Negative VESTS withdrawal blocked |
| HF20 | Delegation | Minimum delegation and update amounts introduced |
| HF20 | Limit orders | Max 28-day expiration enforced |
| HF21 | Comments | Edit frequency limit enforced |
| HF21 | Transfers | Treasury transfer validation tightened |
| HF24 | Comments | `comment_options` on already-paid comments forbidden |
| HF24 | Transfers | Treasury HIVE transfers require feed history |
| HF24 | Witness props | `hbd_` aliases accepted in addition to `sbd_` |
| HF26 | Custom ops | `custom.data` and `custom_json.json` size ≤ 8192 solidified at evaluator |
| HF26 | Voting | Vote edit penalty removed |
| HF26 | Voting | Dust vote handling fixed |
| HF26 | Custom ops | RC Delegation operation added via custom_json `"rc"` id |
| HF28 | Authority | `allow_strict_and_mixed_authorities` enables posting-with-active/owner in the same tx |
| HF28 | Authority | `allow_redundant_signatures` relaxes the "every signature must be used" rule |
| HF28 | Power down | Cancel-power-down fix |
| HF28 | Voting | Stable vote mechanism introduced |
| HF28 | DHF | Voting on nonexistent proposal becomes hard error |
| HF28 | Witness | Global witness props copied from active witness schedule object |
| HF29 (defined in 1.28.8, inactive on mainnet) | Recurrent transfers | An existing transfer may be modified or deleted with `executions == 1` (`HIVE_HARDFORK_1_29_ALLOW_MODIFY_LAST_RECURRENT_TRANSFER`, `hive_evaluator_transfer.cpp:991-996, 1011-1016`); creating one still needs 2 |
| HF29 (defined in 1.28.8, inactive on mainnet) | Limit orders | Only the HIVE:HBD market (`HIVE_HARDFORK_1_29_FIX_LIMIT_ORDER_ASSETS`, `hive_evaluator_transfer.cpp:540-546, 578-584`); a 1.28.8 node already applies this check to new transactions submitted to it and to blocks it produces |

For HF29's other switches see Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet).

---

## Key Discoveries

1. **No hardfork logic in validate():** Protocol-level validation is entirely hardfork-independent. This is a clean architectural separation — protocol defines structural rules, chain defines contextual rules. Confirmed by grep-level verification across `libraries/protocol`.

2. **account_update_operation skips auth size validation (with historical cause):** The evaluator fills the gap since HF20 (`hive_evaluator_account.cpp:283-291`). The reason it can't be lifted to `validate()`: the evaluator's source comment cites `3920d6b938492a873b36b3b44725154cf4123e95` as an example of an authority exceeding 40 members, and `hellosteem` still holds such an authority. A validate()-level check would make replay fail.

3. **transfer allows self-transfers:** `transfer_operation::validate()` does not check `from != to`. Self-transfers are structurally valid at the protocol level; the evaluator also accepts them (net-zero balance change).

4. **withdraw_vesting accepts zero amount:** No `amount > 0` check — zero VESTS is valid (used to cancel power-down). Post-HF20 the evaluator rejects *negative* amounts.

5. **recurrent_transfer allows zero amount:** Amount ≥ 0 (not > 0). Zero is how you cancel a recurrent transfer.

6. **witness_update `fee` is effectively dead:** The field has no symbol check at protocol level AND the evaluator (`hive_evaluator.cpp:62-99`) does not reference `o.fee` at all. It is a vestigial field preserved for wire-format compatibility.

7. **JSON validation has a fallback path:** For blockchain replay compatibility, the JSON validator falls back to a relaxed parser. Historically-accepted malformed JSON continues to be accepted forever. Application code should run its own strict parser if strictness matters.

8. **comment body has no max size in validate():** Body size is only bounded by the transaction size limit of the push path (voted `maximum_block_size` minus 256 bytes). No explicit body-size limit in the comment operation's validate(). `title` *is* capped (255); `body` is not.

9. **Proposal IDs batch limit is 5:** Only 5 proposal IDs per vote/remove operation (`HIVE_PROPOSAL_MAX_IDS_NUMBER`), so batch actions on proposals require multiple transactions.

10. **reset_account and set_reset_account always fail:** Placeholder operations that unconditionally assert false at validate() time. They exist in the operation enum/wire format but cannot be broadcast.

11. **Legacy `sbd_` property names still accepted:** `witness_set_properties` looks up `sbd_interest_rate` / `sbd_exchange_rate` first and falls back to the `hbd_` names (HF24+ only for the `hbd_` fallback at evaluator time).

12. **custom ops chain-level size limits (8192 bytes) were HF26 solidifications:** Before HF26, the limit was node policy that the evaluator applied only to new transactions the node accepted (from 2022: whenever it was in control, which adds the blocks it produced); malformed-big operations could land in blocks. The HF26 solidification made both `custom.data` and `custom_json.json` size limits consensus rules. Chain assertions are in `hive_evaluator.cpp:330-334` (custom) and `:343-344` (custom_json).

13. **Signature verification constants (`HIVE_MAX_SIG_CHECK_DEPTH`, `HIVE_MAX_SIG_CHECK_ACCOUNTS`) are not touched by validate():** They are applied in `sign_state::check_authority_impl` at signature-verification time. Protocol `authority::validate()` only checks account-name validity; `validate_auth_size()` is a separate, top-level, 40-member cap.

14. **Comment depth is purely evaluator-enforced:** `HIVE_SOFT_MAX_COMMENT_DEPTH` (255) is enforced only when the node is in control (new transactions and block production). Historical deep chains replay unchanged. Hard limit since HF17 is 0xffff; pre-HF17 it was 6.

15. **SMT NAI orders are allowed by validate() but limited by the evaluator:** `limit_order_create/2::validate()` accepts SMT NAI <-> HIVE pairs (unchanged at 1.28.8). Without the evaluator's market check, an order selling an SMT symbol fails in `database::adjust_balance` (`database.cpp:3179-3198`, HIVE and HBD only), while an order selling HIVE for an SMT symbol is created and never fills. Since 1.28.8 both evaluators accept only the HIVE:HBD market under HF29 (defined in 1.28.8, inactive on mainnet), and a 1.28.8 node already applies that check to new transactions submitted to it and to blocks it produces (`hive_evaluator_transfer.cpp:540-546, 578-584`); the 1.28.7 `FC_TODO` is replaced by the comment "once HF29 triggers try trimming the check in validate". `asset_symbol_type::validate()` is not called from `price::validate()`, but symbols are checked when a node deserializes them (`asset_symbol.hpp:215`, `asset.cpp:128-165`), so a malformed NAI does not reach a node's `validate()`.

16. **String-size idiom inconsistency is observable, not just cosmetic:** Because witness URL uses `<= MAX` while memo/title/permlink use `< MAX` or `<= MAX - 1`, URL (effective 2048) and memo (effective 2047) accept different byte counts despite both constants being 2048. Applications that serialize strings at the boundary might see asymmetric acceptance.

17. **`transaction::validate()` is the only ordered-iteration call-site of operation `validate()`:** Any direct call-site (e.g., wallet pre-flight validation) should mirror `transaction::validate()`'s operation-count check and FC_CAPTURE_AND_RETHROW wrapping to get consistent error semantics.

---

## Code References

| File | Role |
|------|------|
| `libraries/protocol/hive_operations.cpp` | Main `validate()` implementations (867 lines) |
| `libraries/protocol/dhf_operations.cpp` | DHF operation validation (62 lines) |
| `libraries/protocol/hive_custom_operations.cpp` | RC delegation validation (34 lines) |
| `libraries/protocol/authority.cpp` | Account name + authority validation |
| `libraries/protocol/asset.cpp` | Asset symbol / price validation |
| `libraries/protocol/transaction.cpp` | Transaction-level validation |
| `libraries/protocol/transaction_util.cpp` | `verify_authority_impl` — posting/active/owner mixing, depth, account cap |
| `libraries/protocol/include/hive/protocol/validation.hpp` | String/asset/percent helper functions |
| `libraries/protocol/include/hive/protocol/sign_state.hpp` | `check_authority_impl` — depth and account cap |
| `libraries/protocol/include/hive/protocol/operation_util_impl.hpp` | `operation_validate_visitor` + `HIVE_DEFINE_OPERATION_TYPE` |
| `libraries/protocol/include/hive/protocol/config.hpp` | All validation constants |
| `libraries/protocol/include/hive/protocol/hive_operations.hpp` | `legacy_chain_properties::validate<force_canon>` template |
| `libraries/protocol/include/hive/protocol/asset_symbol.hpp` | NAI/asset constants |
| `libraries/protocol/include/hive/protocol/base.hpp` | `base_operation::validate` (no-op), `virtual_operation::validate` (always fails) |
| `libraries/chain/hive_evaluator.cpp` | Chain-level `custom`, `custom_json`, `witness_update` checks |
| `libraries/chain/hive_evaluator_account.cpp` | Chain-level `account_update` auth-size check (HF20+) |
| `libraries/chain/hive_evaluator_social.cpp` | Chain-level comment depth check |
| `libraries/chain/hive_evaluator_transfer.cpp` | Chain-level recurrent_transfer, limit_order checks |
| `libraries/chain/database.cpp` | `verify_authority` dispatch, `adjust_balance` asset-symbol guard |

---

## Discrepancies and Potential Issues

1. **Inconsistent "off by one" patterns in size checks:** Some size checks use `<` (permlink: `size < 256`), others use `<= max - 1` (memo: `size <= 2047`; title: `size <= 255`), and one uses `<= max` directly (witness url: `size <= 2048`). The `witness_update` URL can accept 2048 bytes while the `transfer` memo tops out at 2047 — both nominally tied to 2048-valued constants. Not a correctness bug, but a design footgun if callers assume "max means max bytes of payload".

2. **witness_update_operation fee lacks symbol validation AND is unread by the evaluator:** `validate()` only enforces `fee >= 0` with no symbol check, and `hive_evaluator.cpp:62-99` never references `o.fee`. The field is vestigial. A client can submit `witness_update_operation` with fee in HBD, VESTS, or an SMT NAI and the op will be accepted. This is the most conspicuous "unused field" in the protocol.

3. **account_update auth size gap (historical, now filled by evaluator since HF20):** The original `account_update_operation::validate()` cannot do the size check because of pre-HF20 authorities that already exceed 40 members. The evaluator applies the rule from HF20 onward. Clients broadcasting fresh `account_update` operations today effectively face the same 40-member cap as `account_update2`, but via a different layer.

4. **Relaxed JSON fallback:** `validate_json_with_fallback()` accepts some malformed JSON that a strict parser would reject, for replay compatibility. Application developers expecting strict JSON must re-validate themselves.

5. **SMT NAI orders pass validate() but do not work:** A subtle "it's valid but it won't work" trap. The `validate()` allows the operation; a 1.28.8 node rejects it in new transactions through the evaluator's market check (in every block once HF29 is active), and without that check an order selling an SMT symbol fails in `adjust_balance` while one selling HIVE for an SMT symbol is created but never fills. A client library that pre-flights only `validate()` would report success for a doomed operation. The evaluator comment says to try trimming the `validate()` branch once HF29 triggers (`hive_evaluator_transfer.cpp:540`).

6. **`price::validate()` does not validate symbol integrity:** `asset_symbol_type::validate()` is not called from `price::validate()` nor from the asset-type helper suite, so the invariant "a validated price has validated symbols" does not hold for an operation built in memory. Nodes are not affected: binary deserialization validates every symbol (`asset_symbol.hpp:215`) and the JSON form is checked, including the Damm check digit, when its NAI string is parsed (`asset.cpp:128-165`).

7. **`account_witness_proxy::validate()` has a dead-code check:** When `proxy` is clearing (empty string), `validate_account_name( proxy )` is skipped, but the subsequent `proxy != account` assertion still runs. Since `account` must be a valid account name (3+ chars), the empty-string proxy can never equal it — the check is effectively a no-op in that branch. Harmless, but slightly misleading at first read.

8. **`transaction::validate()` requires >= 1 operation but not a size cap:** The transaction size cap (voted `maximum_block_size` minus 256 bytes) is applied on the transaction push path (`database.cpp:566-572`), not in `validate()`; `HIVE_MAX_TRANSACTION_SIZE` (64 KiB) is not checked against transactions. A `validate()`-only review does not catch oversized transactions.

---

## Open Questions

(Previously open questions have been resolved by the deepening pass above. See "Chain-level Enforcement Complementing validate()" section and the per-operation notes for the answers.)

1. **Are there any other operations where validate() admits values the evaluator always rejects?** Beyond SMT limit orders, witness_update fee, and reset_account placeholders, this would require a systematic evaluator walk to close. Since 1.28.8 `recurrent_transfer_operation` is one more case: `validate()` admits `executions == 1`, which the evaluator always rejects when the operation would create a transfer (`hive_evaluator_transfer.cpp:976-978`). Candidates include rarely-exercised paths in `escrow_*` and `recover_account_operation`, not examined in this pass. *Zoom candidate.*
