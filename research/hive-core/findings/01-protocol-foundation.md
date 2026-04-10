# Findings: Protocol Foundation — Types, Assets, and Configuration Constants

## Summary

This document captures the complete protocol foundation of the Hive blockchain as defined in the C++ source code under `libraries/protocol/`. Hive operates on a 3-second block interval with 21 witnesses, using three native assets (HIVE, HBD, VESTS) encoded via a Numeric Asset Identifier (NAI) system. The protocol layer defines ~150+ consensus constants covering timing, economics, authority, and resource limits, all verified directly from `config.hpp` and related headers.

## Key Discoveries

### 1. NAI Encoding Uses Reserved Space for Native Assets
- **What**: Native assets (HIVE/HBD/VESTS) use NAI data digits 1-3, which are below the minimum valid NAI range (`SMT_MIN_NAI = 1`). The ones-place digit doubles as a Damm checksum, so NAI data 0-9 would always fail checksum validation for SMT tokens — making this space safe for the three built-in assets.
- **Where**: `asset_symbol.hpp:24-32`, `asset.cpp:128-165`
- **Impact**: Clever design that avoids collisions between native and SMT asset identifiers while keeping a compact `uint32_t` representation.

### 2. Legacy Steem Symbol Names Persist in Binary Protocol
- **What**: On mainnet, HIVE serializes as `STEEM` (`OBSOLETE_SYMBOL_SER`) and HBD serializes as `SBD` (`OBD_SYMBOL_SER`) in legacy wire format. The old symbol names are preserved for backward-compatible deserialization only. On testnet, they become `TESTS` and `TBD`.
- **Where**: `asset_symbol.hpp:36-53`
- **Impact**: Any tool parsing legacy binary serialization must handle the old STEEM/SBD symbol bytes. The NAI format (`smt_nai_space`) uses the new naming.

### 3. HIVE_MAX_SATOSHIS is 2^62 - 1
- **What**: `HIVE_MAX_SATOSHIS = 4611686018427387903` which is exactly `(2^62 - 1)`. This is the maximum amount any single asset field can hold. Meanwhile `HIVE_MAX_SHARE_SUPPLY` is `1,000,000,000,000,000` (10^15) — the maximum total supply of HIVE tokens. The `share_type` is `safe<int64_t>`, providing overflow checking.
- **Where**: `config.hpp:355-356`, `types.hpp:76`
- **Impact**: The satoshis cap at 2^62-1 ensures that multiplication in `uint128_t` during price calculations never overflows.

### 4. Mainnet Chain ID is "beeab0de" Hex Pattern
- **What**: `HIVE_CHAIN_ID = fc::sha256("beeab0de00000000000000000000000000000000000000000000000000000000")`. This is a vanity-style chain ID chosen at the Hive hard fork from Steem. The old Steem chain ID (`OLD_CHAIN_ID`) is an empty sha256. Testnet uses `sha256::hash("testnet")`.
- **Where**: `config.hpp:142-143`, `config.hpp:68-69`
- **Impact**: Chain ID is mixed into transaction signature digests, preventing cross-chain replay attacks.

### 5. Version Comparison Has Major-Version Compatibility Hack
- **What**: The `version` struct comparison operators treat major versions 0 and 1 as equivalent. This was added for HF24 (the Steem→Hive fork) where the major version changed from 0 to 1, but some witnesses still ran old nodes reporting version 0.x.
- **Where**: `version.hpp:50-61`
- **Impact**: `version(0, 23, 0) == version(1, 23, 0)` returns true. This is a permanent backward-compatibility quirk.

### 6. HBD Hard Limit Changed Significantly Across Hardforks
- **What**: The HBD-to-market-cap ratio at which printing stops changed dramatically: HF14 (2%→5%), HF20 (9%→10%), HF26 (20%→20% start/stop, identical). An artificial price floor kicks in at 10% pre-HF26 and 30% post-HF26.
- **Where**: `config.hpp:339-346`
- **Impact**: HF26 effectively doubled the "start reducing" threshold from 10% to 20% and raised the hard limit from 10% to 30%.

### 7. Hardfork 28 Block is Set to 100,000,000 (Unreached Placeholder)
- **What**: `HIVE_HARDFORK_1_28_BLOCK = 100000000`. For context, HF27 activated at block 69,050,084. Block 100M has not been reached yet (approximately late 2026-2027 at current rates). The blockchain version is already set to `1.28.6`.
- **Where**: `hardfork_block.hpp:30`, `config.hpp:66/135`
- **Impact**: HF28 is defined in code but its activation block is a future placeholder.

### 8. Transaction Expiration Hard Limit is 1 Hour
- **What**: `HIVE_MAX_TIME_UNTIL_EXPIRATION = 3600` seconds (1 hour). For signatures specifically, the limit is 1 day (`HIVE_MAX_TIME_UNTIL_SIGNATURE_EXPIRATION = 86400`).
- **Where**: `config.hpp:232-233`
- **Impact**: Transactions must be broadcast within 1 hour of creation. The separate signature expiration allows pre-signed transactions with a longer validity window.

---

## Configuration Constants Reference

All constants from `config.hpp` and related headers, organized by domain. Values shown are for **mainnet** unless otherwise noted.

### Timing Constants

| Constant | Value | Unit | Notes |
|----------|-------|------|-------|
| `HIVE_BLOCK_INTERVAL` | 3 | seconds | Fundamental block production interval |
| `HIVE_BLOCKS_PER_YEAR` | 10,512,000 | blocks | `365*24*60*60/3` |
| `HIVE_BLOCKS_PER_DAY` | 28,800 | blocks | `24*60*60/3` |
| `HIVE_BLOCKS_PER_HOUR` | 1,200 | blocks | `60*60/3` |
| `HIVE_MAX_TIME_UNTIL_EXPIRATION` | 3,600 | seconds | 1 hour — max transaction expiration window |
| `HIVE_MAX_TIME_UNTIL_SIGNATURE_EXPIRATION` | 86,400 | seconds | 1 day — max signature validity |
| `HIVE_ONE_DAY_SECONDS` | 86,400 | seconds | Convenience constant |
| `HIVE_SECONDS_PER_YEAR` | 31,536,000 | seconds | `60*60*24*365` |

### Post/Comment Timing

| Constant | Value | Unit | Notes |
|----------|-------|------|-------|
| `HIVE_CASHOUT_WINDOW_SECONDS` | 604,800 | seconds | 7 days (mainnet) |
| `HIVE_CASHOUT_WINDOW_SECONDS_PRE_HF12` | 86,400 | seconds | 1 day |
| `HIVE_CASHOUT_WINDOW_SECONDS_PRE_HF17` | 43,200 | seconds | 12 hours |
| `HIVE_SECOND_CASHOUT_WINDOW` | 2,592,000 | seconds | 30 days |
| `HIVE_MAX_CASHOUT_WINDOW_SECONDS` | 1,209,600 | seconds | 14 days (2 weeks) |
| `HIVE_UPVOTE_LOCKOUT_SECONDS` | 43,200 | seconds | 12 hours before cashout |
| `HIVE_UPVOTE_LOCKOUT_HF17` | 12 hours | fc::hours | Same as above, typed |
| `HIVE_MIN_ROOT_COMMENT_INTERVAL` | 300 | seconds | 5 minutes between root posts |
| `HIVE_MIN_REPLY_INTERVAL` | 3 | seconds | Between replies |
| `HIVE_MIN_COMMENT_EDIT_INTERVAL` | 3 | seconds | Between comment edits |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF6` | 1,800 | seconds | 30 minutes |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF20` | 900 | seconds | 15 minutes |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF21` | 300 | seconds | 5 minutes |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF25` | 0 | seconds | Disabled on mainnet |
| `HIVE_EARLY_VOTING_SECONDS_HF25` | 86,400 | seconds | 24 hours |
| `HIVE_MID_VOTING_SECONDS_HF25` | 172,800 | seconds | 48 hours |
| `HIVE_POST_AVERAGE_WINDOW` | 86,400 | seconds | 1 day |

### Witness Constants

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MAX_WITNESSES` | 21 | Total witnesses per round |
| `HIVE_MAX_VOTED_WITNESSES_HF0` | 19 | Pre-HF17 elected witnesses |
| `HIVE_MAX_MINER_WITNESSES_HF0` | 1 | Pre-HF17 miner witness slots |
| `HIVE_MAX_RUNNER_WITNESSES_HF0` | 1 | Pre-HF17 runner-up slots |
| `HIVE_MAX_VOTED_WITNESSES_HF17` | 20 | Post-HF17 elected witnesses |
| `HIVE_MAX_MINER_WITNESSES_HF17` | 0 | Mining disabled post-HF17 |
| `HIVE_MAX_RUNNER_WITNESSES_HF17` | 1 | One backup/runner-up witness |
| `HIVE_HARDFORK_REQUIRED_WITNESSES` | 17 | 17/21 required for hardfork (guarantees 75%+) |
| `HIVE_MAX_ACCOUNT_WITNESS_VOTES` | 30 | Max witnesses a user can vote for |
| `HIVE_WITNESS_SHUTDOWN_THRESHOLD` | 28,800 | Blocks (1 day) before shutdown for missed blocks |
| `HIVE_START_MINER_VOTING_BLOCK` | 864,000 | 30 days of blocks before miner voting starts |
| `HIVE_START_VESTING_BLOCK` | 201,600 | 7 days of blocks |

### Inflation & Rewards

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_INFLATION_RATE_START_PERCENT` | 978 | 9.78% — fixes block 7,000,000 to ~9.5% |
| `HIVE_INFLATION_RATE_STOP_PERCENT` | 95 | 0.95% — long-term floor |
| `HIVE_INFLATION_NARROWING_PERIOD` | 250,000 | Narrow 0.01% every 250k blocks |
| `HIVE_CONTENT_REWARD_PERCENT_HF16` | 7,500 | 75% of inflation to content |
| `HIVE_VESTING_FUND_PERCENT_HF16` | 1,500 | 15% of inflation to vesting fund |
| `HIVE_CONTENT_REWARD_PERCENT_HF21` | 6,500 | 65% of inflation to content |
| `HIVE_PROPOSAL_FUND_PERCENT_HF0` | 0 | No DHF before HF21 |
| `HIVE_PROPOSAL_FUND_PERCENT_HF21` | 1,000 | 10% of inflation to DHF |
| `HIVE_MINER_PAY_PERCENT` | 100 | 1% |
| `HIVE_MIN_PAYOUT_HBD` | 0.020 HBD | Minimum payout threshold |
| `HIVE_VOTE_DUST_THRESHOLD` | 50,000,000 | Vote rshares below this are treated as dust |
| `HIVE_DOWNVOTE_POOL_PERCENT_HF21` | 2,500 | 25% of upvote mana available as free downvotes |

### HBD (Hive Backed Dollars)

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_DEFAULT_HBD_INTEREST_RATE` | 1,000 | 10% APR default |
| `HIVE_HBD_INTEREST_COMPOUND_INTERVAL_SEC` | 2,592,000 | 30 days — interest compounds monthly |
| `HIVE_HBD_START_PERCENT_HF14` | 200 | Start reducing HBD printing at 2% market cap |
| `HIVE_HBD_STOP_PERCENT_HF14` | 500 | Stop printing at 5% |
| `HIVE_HBD_START_PERCENT_HF20` | 900 | 9% |
| `HIVE_HBD_STOP_PERCENT_HF20` | 1,000 | 10% |
| `HIVE_HBD_START_PERCENT_HF26` | 2,000 | 20% |
| `HIVE_HBD_STOP_PERCENT_HF26` | 2,000 | 20% (start = stop, binary cutoff) |
| `HIVE_HBD_HARD_LIMIT_PRE_HF26` | 1,000 | Artificial HBD price at 10% cap |
| `HIVE_HBD_HARD_LIMIT` | 3,000 | Artificial HBD price at 30% cap |

### Conversions

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_CONVERSION_DELAY` | ~3.5 days | `FEED_HISTORY_WINDOW * FEED_INTERVAL_BLOCKS * BLOCK_INTERVAL` |
| `HIVE_CONVERSION_DELAY_PRE_HF_16` | ~7 days | Double the current delay |
| `HIVE_COLLATERALIZED_CONVERSION_DELAY` | same as `CONVERSION_DELAY` | ~3.5 days |
| `HIVE_CONVERSION_COLLATERAL_RATIO` | 20,000 | 200% (2× `HIVE_100_PERCENT`) |
| `HIVE_COLLATERALIZED_CONVERSION_FEE` | 500 | 5% fee |

### Feed System

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_FEED_INTERVAL_BLOCKS` | 1,200 | = `BLOCKS_PER_HOUR` (every hour) |
| `HIVE_FEED_HISTORY_WINDOW_PRE_HF_16` | 168 | 24×7 intervals = 7 days |
| `HIVE_FEED_HISTORY_WINDOW` | 84 | 12×7 intervals = 3.5 days |
| `HIVE_MAX_FEED_AGE_SECONDS` | 604,800 | 7 days before feed expires |
| `HIVE_MIN_FEEDS` | 7 | `MAX_WITNESSES/3` = 21/3 |

### Vesting (Power Up/Down)

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_VESTING_WITHDRAW_INTERVALS_PRE_HF_16` | 104 | 2 years of weekly withdrawals |
| `HIVE_VESTING_WITHDRAW_INTERVALS` | 13 | 13 weeks (current) |
| `HIVE_VESTING_WITHDRAW_INTERVAL_SECONDS` | 604,800 | = `CASHOUT_WINDOW_SECONDS` (1 week) |
| `HIVE_VOTING_MANA_REGENERATION_SECONDS` | 432,000 | 5 days |
| `HIVE_MAX_WITHDRAW_ROUTES` | 10 | Max withdrawal destinations |
| `HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS` | 2,592,000 | 30 days — delay before new vests vote |
| `HIVE_DELAYED_VOTING_INTERVAL_SECONDS` | 86,400 | 1 day granularity for delayed voting |

### Account/Authority Limits

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MIN_ACCOUNT_NAME_LENGTH` | 3 | Characters |
| `HIVE_MAX_ACCOUNT_NAME_LENGTH` | 16 | Characters |
| `HIVE_MIN_ACCOUNT_CREATION_FEE` | 1 | 0.001 HIVE (mainnet); 0 on testnet |
| `HIVE_MAX_ACCOUNT_CREATION_FEE` | 1,000,000,000 | 1,000,000 HIVE |
| `HIVE_MAX_AUTHORITY_MEMBERSHIP` | 40 | Max keys+accounts in an authority |
| `HIVE_MAX_SIG_CHECK_DEPTH` | 2 | Max authority recursion depth |
| `HIVE_MAX_SIG_CHECK_ACCOUNTS` | 125 | Max accounts checked during sig verification |
| `HIVE_MAX_PROXY_RECURSION_DEPTH` | 4 | Max witness vote proxy chain |
| `HIVE_CREATE_ACCOUNT_WITH_HIVE_MODIFIER` | 30 | Multiplier for creation-with-HIVE fee |
| `HIVE_CREATE_ACCOUNT_DELEGATION_RATIO` | 5 | Delegation-to-fee ratio |
| `HIVE_CREATE_ACCOUNT_DELEGATION_TIME` | 30 days | Delegation lock period |

### Size Limits

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MAX_TRANSACTION_SIZE` | 65,536 | 64 KB |
| `HIVE_MIN_TRANSACTION_SIZE_LIMIT` | 1,024 | 1 KB |
| `HIVE_MAX_BLOCK_SIZE` | 2,097,152 | 2 MB hard maximum |
| `HIVE_MIN_BLOCK_SIZE_LIMIT` | 65,536 | = `MAX_TRANSACTION_SIZE` |
| `HIVE_MIN_BLOCK_SIZE` | 115 | Bytes — minimum valid block |
| `HIVE_MAX_MEMO_SIZE` | 2,048 | Characters |
| `HIVE_MAX_PERMLINK_LENGTH` | 256 | Characters |
| `HIVE_MAX_WITNESS_URL_LENGTH` | 2,048 | Characters |
| `HIVE_MAX_URL_LENGTH` | 127 | For witness URL in operations |
| `HIVE_MAX_SHARE_SUPPLY` | 10^15 | 1,000,000,000,000,000 |
| `HIVE_MAX_SATOSHIS` | 2^62 - 1 | 4,611,686,018,427,387,903 |

### Owner Key Recovery

| Constant | Value (Mainnet) | Value (Testnet) |
|----------|-----------------|-----------------|
| `HIVE_OWNER_AUTH_RECOVERY_PERIOD` | 30 days | 60 seconds |
| `HIVE_ACCOUNT_RECOVERY_REQUEST_EXPIRATION_PERIOD` | 1 day | 12 seconds |
| `HIVE_OWNER_UPDATE_LIMIT` | 60 minutes | 6 seconds |
| `HIVE_OWNER_AUTH_HISTORY_TRACKING_START_BLOCK_NUM` | 3,186,477 | 1 |

### Savings

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_SAVINGS_WITHDRAW_TIME` | 3 days | Mandatory withdrawal delay |
| `HIVE_SAVINGS_WITHDRAW_REQUEST_LIMIT` | 100 | Max pending savings withdrawals |

### Recurrent Transfers

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MAX_RECURRENT_TRANSFER_END_DATE` | 730 | 2 years in days |
| `HIVE_MAX_RECURRENT_TRANSFERS_PER_BLOCK` | 1,000 | Processing limit per block |
| `HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` | 24 | Hours — minimum interval |
| `HIVE_MAX_OPEN_RECURRENT_TRANSFERS` | 255 | Per account |
| `HIVE_MAX_CONSECUTIVE_RECURRENT_TRANSFER_FAILURES` | 10 | Before cancellation |
| `HIVE_MAX_PENDING_TRANSFERS` | 255 | Max pending transfers |

### DHF (Decentralized Hive Fund) / Proposals

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_TREASURY_FEE` | 10,000 | 10 HBD (10 × `BLOCKCHAIN_PRECISION`) |
| `HIVE_PROPOSAL_SUBJECT_MAX_LENGTH` | 80 | Characters |
| `HIVE_PROPOSAL_MAX_IDS_NUMBER` | 5 | Max IDs per update/remove operation |
| `HIVE_PROPOSAL_FEE_INCREASE_DAYS` | 60 | Days after which fee increases |
| `HIVE_PROPOSAL_FEE_INCREASE_AMOUNT` | 1,000 | 1 HBD per 60 days |
| `HIVE_PROPOSAL_CONVERSION_RATE` | 5 | 0.05% (5 basis points) |
| `HIVE_PROPOSAL_MAINTENANCE_PERIOD` | 3,600 | 1 hour — how often proposals are processed |
| `HIVE_PROPOSAL_MAINTENANCE_CLEANUP` | 86,400 | 1 day |
| `HIVE_DAILY_PROPOSAL_MAINTENANCE_PERIOD` | 86,400 | 1 day |
| `HIVE_GOVERNANCE_VOTE_EXPIRATION_PERIOD` | 365 days | Governance votes expire yearly |

### Custom Operations

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_CUSTOM_OP_ID_MAX_LENGTH` | 32 | Characters |
| `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` | 8,192 | Bytes |
| `HIVE_CUSTOM_OP_BLOCK_LIMIT` | 5 | Max custom ops per block |

### Comment Limits

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MAX_COMMENT_DEPTH_PRE_HF17` | 6 | Very shallow comment threads |
| `HIVE_MAX_COMMENT_DEPTH` | 65,535 | 0xFFFF — effectively unlimited |
| `HIVE_SOFT_MAX_COMMENT_DEPTH` | 255 | Soft limit enforced differently |
| `HIVE_MAX_COMMENT_BENEFICIARIES` | 8 | Max beneficiary routes per post |
| `HIVE_BENEFICIARY_LIMIT` | 128 | Extended beneficiary limit |
| `HIVE_COMMENT_TITLE_LIMIT` | 256 | Characters |

### Resource Credits (RC System)

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_RC_REGEN_TIME` | 432,000 | 5 days (= `VOTING_MANA_REGENERATION_SECONDS`) |
| `HIVE_RC_BUCKET_TIME_LENGTH` | 3,600 | 1 hour |
| `HIVE_RC_WINDOW_BUCKET_COUNT` | 24 | 24 hours of buckets |
| `HIVE_RC_STATS_REPORT_FREQUENCY` | 28,800 | 1 report per day |
| `HIVE_RC_HISTORICAL_ACCOUNT_CREATION_ADJUSTMENT` | 2,020,748,973 | ~2020.748973 VESTS = 1 HIVE at HF20 |
| `HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP` | 100 | Max accounts per RC delegation |

### Percentage/Basis System

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_100_PERCENT` | 10,000 | Basis of all percentage calculations |
| `HIVE_1_PERCENT` | 100 | = `100_PERCENT/100` |
| `HIVE_1_BASIS_POINT` | 1 | = `100_PERCENT/10000` |
| `HIVE_IRREVERSIBLE_THRESHOLD` | 7,500 | 75% for irreversibility |

### Special Accounts

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_INIT_MINER_NAME` | `"initminer"` | Genesis block producer |
| `HIVE_MINER_ACCOUNT` | `"miners"` | Represents current witnesses |
| `HIVE_NULL_ACCOUNT` | `"null"` | Black hole — no authority |
| `HIVE_TEMP_ACCOUNT` | `"temp"` | Wildcard authority (anyone) |
| `OBSOLETE_TREASURY_ACCOUNT` | `"steem.dao"` | Old treasury |
| `NEW_HIVE_TREASURY_ACCOUNT` | `"hive.fund"` | Current treasury (since HF24) |
| `HIVE_PROXY_TO_SELF_ACCOUNT` | `""` | Empty string = vote directly |

### Miscellaneous

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_ADDRESS_PREFIX` | `"STM"` | Public key prefix (kept from Steem) |
| `HIVE_MAX_UNDO_HISTORY` | 10,000 | Undo stack depth |
| `HIVE_INITIAL_VOTE_POWER_RATE` | 40 | Votes per day at full power |
| `HIVE_REDUCED_VOTE_POWER_RATE` | 10 | Reduced rate |
| `HIVE_MAX_LIMIT_ORDER_EXPIRATION` | 2,419,200 | 28 days |
| `HIVE_BLOCK_GENERATION_POSTPONED_TX_LIMIT` | 5 | Max postponed transactions per block |
| `HIVE_PENDING_TRANSACTION_EXECUTION_LIMIT` | 200ms | Time budget for pending txs |
| `HIVE_GLOBAL_REMOVE_THRESHOLD` | 200 | (100 on testnet) |
| `HIVE_BLOCKCHAIN_PRECISION` | 1,000 | 10^3 — matches HBD precision |
| `HIVE_NUM_HARDFORKS` | 28 | Total hardforks defined |

---

## Asset System

### Three Native Assets

| Asset | Symbol (Mainnet) | Legacy Symbol | Precision | NAI Data Digit | NAI String | `asset_num` (decimal) |
|-------|-----------------|---------------|-----------|----------------|------------|----------------------|
| HIVE | `HIVE` | `STEEM` | 3 (0.001) | 2 | `@@000000021` | 3,200,000,035 |
| HBD | `HBD` | `SBD` | 3 (0.001) | 1 | `@@000000013` | 3,200,000,003 |
| VESTS | `VESTS` | `VESTS` | 6 (0.000001) | 3 | `@@000000037` | 3,200,000,070 |

### NAI (Numeric Asset Identifier) Encoding

The `asset_symbol_type` is a single `uint32_t` (`asset_num`) that packs:

```
Bits [0..3]:   precision (decimals, 0-12)
Bit  [4]:      control bit (1 for SMT tokens, 0 for legacy)
Bit  [5]:      vesting flag (1 = vesting variant of SMT)
Bits [6..31]:  NAI data digits
```

**For native assets:** The NAI data digits are `SMT_MAX_NAI + HIVE_NAI_X` where `SMT_MAX_NAI = 99999999` and `HIVE_NAI_X` is 1 (HBD), 2 (HIVE), or 3 (VESTS). The control bit is 0 for native assets.

**For SMT tokens:** NAI data ranges from `SMT_MIN_NAI (1)` to `SMT_MAX_NAI (99999999)`, with the control bit set to 1. A Damm checksum digit is appended for the string representation (`@@NNNNNNNNNC`).

**Spaces:**
- `legacy_space` (1): HIVE, HBD, VESTS — the three hardcoded native assets
- `smt_nai_space` (2): All other assets (SMT tokens)

### Serialization

Two serialization modes exist:
- **Legacy format**: 8 bytes — `pppp AAAA BBBB CCCC DDDD EEEE FFFF 0000` where `p` = precision and `A-F` = ASCII symbol chars. HIVE serializes as `STEEM`, HBD as `SBD`.
- **NAI format**: 4 bytes — the raw `asset_num` uint32.

The `pack`/`unpack` functions automatically detect the format during deserialization by matching against known legacy byte patterns.

### Asset Validation
- Assets enforce same-symbol checks on all arithmetic operations (`+=`, `-=`, comparisons, etc.) via `HIVE_PROTOCOL_ASSET_ASSERT`
- No overflow protection at the `asset` level — that's handled by `share_type = safe<int64_t>` which throws on overflow
- The `price` struct requires `base.symbol != quote.symbol` and both amounts > 0
- Price comparisons use cross-multiplication in `uint128_t` to avoid floating-point

### tiny_asset and tiny_price

Template-parameterized thin wrappers used in chain objects:
- `HBD_asset = tiny_asset<HIVE_ASSET_NUM_HBD>` — stores only `share_type amount`
- `HIVE_asset = tiny_asset<HIVE_ASSET_NUM_HIVE>`
- `VEST_asset = tiny_asset<HIVE_ASSET_NUM_VESTS>`
- `HBD_price = tiny_price<HIVE_ASSET_NUM_HBD, HIVE_ASSET_NUM_HIVE>`
- `VEST_price = tiny_price<HIVE_ASSET_NUM_VESTS, HIVE_ASSET_NUM_HIVE>`

These are **not** used in operations (where the full `asset` type with explicit symbol is required for clarity) but are used in internal chain state for efficiency and type safety.

---

## Type System

### Core Type Definitions (`types.hpp`)

| Type | Definition | Purpose |
|------|-----------|---------|
| `account_name_type` | `fixed_string<16>` | Account name — max 16 chars, stored inline |
| `share_type` | `safe<int64_t>` | Asset amounts with overflow checking |
| `ushare_type` | `safe<uint64_t>` | Unsigned variant |
| `weight_type` | `uint16_t` | Authority weights |
| `chain_id_type` | `fc::sha256` | 256-bit chain identifier |
| `block_id_type` | `fc::ripemd160` | 160-bit block hash |
| `transaction_id_type` | `fc::ripemd160` | 160-bit transaction hash |
| `checksum_type` | `fc::ripemd160` | Generic 160-bit checksum |
| `digest_type` | `fc::sha256` | 256-bit digest (for signing) |
| `signature_type` | `fc::ecc::compact_signature` | ECDSA compact signature (65 bytes) |
| `private_key_type` | `fc::ecc::private_key` | ECDSA private key |
| `public_key_type` | custom struct wrapping `fc::ecc::public_key_data` | With base58 encoding |
| `custom_id_type` | `fixed_string<32>` | Custom operation ID string |
| `contribution_id_type` | `uint32_t` | For DHF/proposal contributions |

### fixed_string

`fixed_string<N>` is a stack-allocated, endian-reversible string with a maximum of `N` bytes. Used for `account_name_type` (16 bytes) and `custom_id_type` (32 bytes). Internally uses `fc::uint128` (for 16) or `erpair<uint64_t, uint64_t>` for storage.

### public_key_type

Custom struct wrapping `fc::ecc::public_key_data` (33 bytes — compressed EC point). Serializes to/from base58 strings with the `STM` prefix and a 4-byte RIPEMD-160 checksum. Also supports extended key types (`extended_public_key_type`, `extended_private_key_type`) for HD wallet derivation.

### Extensions Types

- `future_extensions` = `static_variant<void_t>` — placeholder for future fields
- `extensions_type` = `flat_set<future_extensions>` — standard extensions on most operations
- `block_header_extensions` = `static_variant<void_t, version, hardfork_version_vote>` — block-level extensions for witness version reporting and HF voting

---

## Authority Model

### Structure (`authority.hpp`)

```cpp
struct authority {
  uint32_t              weight_threshold;
  account_authority_map account_auths;   // flat_map<account_name_type, weight_type>
  key_authority_map     key_auths;       // flat_map<public_key_type, weight_type>
};
```

### Authority Levels

Three classification levels defined as an enum:
1. **owner** (0) — Highest privilege. Can change all keys. Recovery period: 30 days.
2. **active** (1) — Standard operational authority. Financial transfers, voting.
3. **posting** (2) — Lowest privilege. Social actions: posting, voting on content, custom_json for social ops.

Additionally, `witness` authority is tracked separately for block signing.

### Weight/Threshold System

- Each key or account in an authority has a `weight_type` (`uint16_t`) weight
- The authority has a `weight_threshold` (`uint32_t`)
- To satisfy an authority, the sum of weights of provided keys/accounts must be ≥ threshold
- Example: threshold=2, key_A weight=1, key_B weight=1 → both keys needed (2-of-2)
- Example: threshold=1, key_A weight=1, key_B weight=1 → either key works (1-of-2)

### Multi-sig

Multi-signature is built into the authority model:
- An authority can have up to **40 members** (`HIVE_MAX_AUTHORITY_MEMBERSHIP`) — combination of keys and accounts
- Account auths allow delegation: account B's authority can be part of account A's authority
- Max recursion depth for account authority resolution: **2** (`HIVE_MAX_SIG_CHECK_DEPTH`)
- Max accounts checked during signature verification: **125** (`HIVE_MAX_SIG_CHECK_ACCOUNTS`)
- `is_impossible()` returns true when total available weights < threshold

### Account Name Validation

Names follow RFC 1035 DNS label rules with additional Hive constraints:
- Length: 3-16 characters
- Dot-separated labels, each label ≥ 3 characters
- Each label: starts with lowercase letter, ends with letter or digit, middle chars are letters/digits/hyphens
- Only lowercase letters allowed (no uppercase)
- Implementation: `authority.cpp:58-122`

### Required Authorities per Operation

Each operation declares which authority levels it requires via:
- `get_required_active_authorities()` — needs active key
- `get_required_posting_authorities()` — needs posting key
- `get_required_owner_authorities()` — needs owner key
- `get_required_witness_signatures()` — needs witness signing key
- `get_required_authorities()` — custom authority (e.g., multi-party operations)

---

## Block Structure

### Block Header (`block_header.hpp`)

```cpp
struct block_header {
  block_id_type                previous;              // RIPEMD-160 hash of previous block
  fc::time_point_sec           timestamp;             // Block production time
  string                       witness;               // Witness account name
  checksum_type                transaction_merkle_root; // Merkle root of transaction hashes
  block_header_extensions_type extensions;             // Version reporting, HF votes
};
```

### Signed Block Header

```cpp
struct signed_block_header : public block_header {
  signature_type witness_signature;  // ECDSA compact signature (65 bytes)
};
```

### Full Signed Block

```cpp
struct signed_block : public signed_block_header {
  vector<signed_transaction> transactions;
};
```

### Block ID Computation

Block IDs are `block_id_type` (RIPEMD-160, 20 bytes). The block number is encoded in the first 4 bytes (big-endian reversed):

```cpp
uint32_t block_header::num_from_id(const block_id_type& id) {
  return fc::endian_reverse_u32(id._hash[0]);
}
```

The block number for the current block is `num_from_id(previous) + 1`.

### Block Header Extensions

The `block_header_extensions` is a `static_variant` supporting:
1. `void_t` — empty/no extension
2. `version` — witness reports its software version
3. `hardfork_version_vote` — witness votes for next hardfork (includes HF version + activation time)

These are stored in a `flat_set` so they're unique and ordered.

### Merkle Root

Computed via `legacy_calculate_merkle_root()` — pairs transaction digests, hashing them together iteratively until one root remains. Uses legacy serialization mode. An empty block has a zero checksum.

---

## Transaction Structure

### Transaction (`transaction.hpp`)

```cpp
struct transaction {
  uint16_t           ref_block_num;    // TaPoS: lower 16 bits of reference block number
  uint32_t           ref_block_prefix; // TaPoS: first 32 bits of reference block ID  
  fc::time_point_sec expiration;       // When this transaction expires
  vector<operation>  operations;       // List of operations
  extensions_type    extensions;       // Future extensions (currently void_t only)
};
```

### Signed Transaction

```cpp
struct signed_transaction : public transaction {
  vector<signature_type> signatures;  // ECDSA compact signatures
};
```

### TaPoS (Transaction as Proof of Stake)

TaPoS prevents transaction replay and proves the signer had visibility of recent chain state:

```cpp
void transaction::set_reference_block(const block_id_type& reference_block) {
  ref_block_num = fc::endian_reverse_u32(reference_block._hash[0]);    // block number (16-bit)
  ref_block_prefix = reference_block._hash[1];                          // 32-bit block ID prefix
}
```

- `ref_block_num`: Lower 16 bits of a recent block number
- `ref_block_prefix`: First 4 bytes (after block number) of that block's ID
- The chain verifies these match a block within the recent undo history

### Expiration

- Transactions must include an expiration timestamp
- Maximum expiration: `HIVE_MAX_TIME_UNTIL_EXPIRATION` = **3,600 seconds** (1 hour) from head block time
- Expired transactions are rejected; not-yet-valid transactions are also rejected

### Transaction ID Computation

```cpp
transaction_id_type transaction::id(pack_type pack) const {
  auto h = digest(pack);  // SHA-256 of serialized transaction
  transaction_id_type result;
  memcpy(result._hash, h._hash, std::min(sizeof(result), sizeof(h)));
  return result;  // Truncated to RIPEMD-160 size (20 bytes)
}
```

Transaction ID = first 20 bytes of SHA-256 hash of serialized transaction data.

### Signature Digest

For signing, the chain ID is prepended to the transaction data before hashing:

```cpp
digest_type transaction::sig_digest(const chain_id_type& chain_id, pack_type pack) const {
  digest_type::encoder enc;
  fc::raw::pack(enc, chain_id);  // Chain ID first
  fc::raw::pack(enc, *this);     // Then full transaction
  return enc.result();           // SHA-256
}
```

### Transaction Validation

Basic validation ensures:
- At least one operation exists
- Each operation passes its own `validate()` method

Authority verification is separate and checks that provided signatures satisfy all required authorities for all operations.

---

## Version and Hardfork System

### Version (`version.hpp`)

Triple encoding: `major.hardfork.release` packed in `uint32_t`:
- Bits [24-31]: major version
- Bits [16-23]: hardfork version (minor)
- Bits [0-15]: release version

Current: `version(1, 28, 6)` → `0x011C0006`

### Hardfork Version

Inherits from `version` but masks off the release bits:
```cpp
hardfork_version(version v) { v_num = v.v_num & 0xFFFF0000; }
```

### Hardfork History (Block Numbers)

| Hardfork | Block | Approx Date |
|----------|-------|-------------|
| HF 0.1 | 905,693 | |
| HF 0.2 | 934,585 | |
| HF 0.3 | 953,363 | |
| HF 0.4 | 1,041,497 | |
| HF 0.5 | 1,934,236 | |
| HF 0.6 | 2,790,882 | |
| HF 0.7 | 2,889,019 | |
| HF 0.8 | 2,889,959 | |
| HF 0.9 | 3,202,773 | |
| HF 0.10 | 3,239,649 | |
| HF 0.11 | 3,276,913 | |
| HF 0.12 | 3,533,567 | |
| HF 0.13 | 4,105,155 | |
| HF 0.14 | 5,137,542 | |
| HF 0.15 | 6,547,932 | |
| HF 0.16 | 7,353,249 | |
| HF 0.17 | 10,629,455 | |
| HF 0.18 | 10,629,486 | (~31 blocks after HF17) |
| HF 0.19 | 12,988,978 | |
| HF 0.20 | 26,256,743 | |
| HF 0.21 | 35,921,786 | |
| HF 0.22 | 35,974,326 | |
| HF 0.23 | 41,818,752 | (Hive fork from Steem) |
| HF 1.24 | 47,797,680 | (First "1.x" version) |
| HF 1.25 | 55,235,767 | |
| HF 1.26 | 68,676,505 | |
| HF 1.27 | 69,050,084 | |
| HF 1.28 | 100,000,000 | (Future — not yet reached) |

Note: HF 0.17 and 0.18 were only ~31 blocks apart — practically simultaneous. The major version changed from 0 to 1 at HF24 (the Hive chain split).

### HBD Interest Calculation

From `hbd_interest.hpp`:
```
interest = (hbd_balance * seconds_elapsed) / SECONDS_PER_YEAR * hbd_interest_rate / 10000
```

Compounds every `HIVE_HBD_INTEREST_COMPOUND_INTERVAL_SEC` (30 days). The `hbd_seconds` accumulator tracks balance-weighted time.

### Collateralized Conversion

From `hive_collateral.hpp`:
```
needed_hive = hbd_amount * min_price * (1 + 5% fee)
required_collateral = needed_hive * 200% / 100%
```

The 200% collateral ratio (`HIVE_CONVERSION_COLLATERAL_RATIO = 2 * HIVE_100_PERCENT`) and 5% fee (`HIVE_COLLATERALIZED_CONVERSION_FEE = 5 * HIVE_1_PERCENT`) are consensus constants.

---

## Answers to Research Questions

### Configuration Constants

**Q: What is the block interval?**
A: 3 seconds (`HIVE_BLOCK_INTERVAL = 3`). Source: `config.hpp:56`

**Q: What is the maximum transaction size?**
A: 65,536 bytes / 64 KB (`HIVE_MAX_TRANSACTION_SIZE = 1024*64`). Source: `config.hpp:364`

**Q: What is the maximum block size?**
A: 2,097,152 bytes / 2 MB (`HIVE_MAX_BLOCK_SIZE = 2*1024*1024`). Source: `config.hpp:366`

**Q: What is the transaction expiration window?**
A: Maximum 3,600 seconds / 1 hour (`HIVE_MAX_TIME_UNTIL_EXPIRATION`). Source: `config.hpp:232`

**Q: What are the cashout windows?**
A: Currently 7 days (604,800s). Was 1 day pre-HF12, 12 hours pre-HF17. Source: `config.hpp:155-159`

**Q: What are the inflation rate parameters?**
A: Starts at 9.78% (`978`), decreases by 0.01% every 250,000 blocks, stops at 0.95% (`95`). 65% to content, 10% to proposals (DHF), remaining to witnesses/vesting. Source: `config.hpp:257-265`

**Q: What are the witness-related constants?**
A: 21 total, 20 elected + 1 runner-up (post-HF17). 17/21 required for hardfork activation. 30 max votes per account. Source: `config.hpp:62, 223-231`

**Q: What are the vesting withdrawal parameters?**
A: 13 weekly intervals (was 104 pre-HF16). Each interval = 7 days (same as cashout window). Max 10 withdrawal routes. Source: `config.hpp:236-239`

**Q: What are the HBD interest rate bounds?**
A: Default 10% APR. Witnesses set the rate. Compounds monthly (every 30 days). Source: `config.hpp:255, 363`

**Q: What are the DHF constants?**
A: 10 HBD creation fee, 80-char subject, maintenance every hour, 1 HBD fee increase every 60 days. Source: `config.hpp:462-469`

**Q: What constants differ between mainnet and testnet?**
A: Testnet overrides are extensive — see `testnet_blockchain_configuration.hpp`. Key differences: cashout window (1 hour vs 7 days), owner recovery (60s vs 30 days), delayed voting (1 day vs 30 days), governance vote expiration (5 days vs 365 days), feed interval (20 blocks vs 1200), initial supply (243M HIVE + 7M HBD vs 0).

**Q: Any suspicious constants?**
A: `HIVE_BLOCKCHAIN_PRECISION = uint64_t(1000)` has a comment saying "actually HBD precision" — this is somewhat misleading since it's the same precision for all 3-decimal assets (HIVE and HBD). The naming suggests it's a general precision but it's really just 10^3. Not a bug, but the comment could be clearer.

### Asset System

**Q: Internal representations?**
A: All three use `asset_num` (uint32_t) with NAI encoding. HIVE and HBD have precision 3 (3 decimal places), VESTS has precision 6.

**Q: NAI system?**
A: Covered in detail above. Key: `@@NNNNNNNNNC` string format, Damm checksum, 32-bit internal encoding.

**Q: Asset validation?**
A: Symbol type validated in `asset_symbol_type::validate()`. Amount uses `safe<int64_t>` for overflow protection. No explicit negative amount prevention at the protocol type level — that's enforced per-operation in validation.

### Type System

**Q: `account_name_type` constraints?**
A: `fixed_string<16>` — max 16 characters. RFC 1035 DNS-like rules: lowercase, dot-separated labels, each ≥ 3 chars, starts with letter, ends with letter/digit. Min length 3.

**Q: `share_type` and large numbers?**
A: `safe<int64_t>` — wraps `int64_t` with overflow checking. Throws on overflow/underflow. Max value: `INT64_MAX`. For calculations requiring larger numbers, `uint128_t` and `uint256_t` are available.

### Block/Transaction Structure

Fully documented in the sections above.

---

## Code References

| Component | File | Line(s) | Purpose |
|-----------|------|---------|---------|
| Block interval constant | `config.hpp` | 56 | `HIVE_BLOCK_INTERVAL = 3` |
| All timing constants | `config.hpp` | 56-207 | Block, cashout, recovery, feed timings |
| All economic constants | `config.hpp` | 215-346 | Inflation, rewards, HBD limits |
| All size limits | `config.hpp` | 348-399 | Transaction, block, memo, name sizes |
| Special accounts | `config.hpp` | 441-458 | null, temp, miners, treasury |
| DHF constants | `config.hpp` | 460-469 | Proposal system |
| RC constants | `config.hpp` | 479-494 | Resource credits |
| NAI bit layout | `asset_symbol.hpp` | 9-32 | Precision bits, shift, NAI encoding |
| Asset precisions | `asset_symbol.hpp` | 20-22 | HBD=3, HIVE=3, VESTS=6 |
| Legacy symbol bytes | `asset_symbol.hpp` | 36-53 | STEEM/SBD/TESTS/TBD/HIVE/HBD/VESTS |
| Serialization modes | `asset_symbol.hpp` | 157-216 | Legacy vs NAI pack/unpack |
| `asset` struct | `asset.hpp` | 21-96 | Amount + symbol with operator overloads |
| `price` struct | `asset.hpp` | 139-186 | Base/quote pair |
| `tiny_asset` template | `asset.hpp` | 218-261 | Typed thin wrappers |
| `tiny_price` template | `asset.hpp` | 268-322 | Typed price wrappers |
| NAI Damm checksum | `asset.cpp` | 80-126 | 8-digit Damm algorithm |
| Asset symbol validation | `asset.cpp` | 261-283 | NAI range + control bit checks |
| Price multiplication | `asset.cpp` | 310-325 | uint128 cross-multiplication |
| Max satoshis | `asset.cpp` | 337-340 | Returns `HIVE_MAX_SATOSHIS` |
| Core type aliases | `types.hpp` | 66-81 | All fundamental typedefs |
| `public_key_type` | `types.hpp` | 83-103 | Key data + base58 encoding |
| Authority struct | `authority.hpp` | 7-55 | Threshold + key/account maps |
| Account name validation | `authority.cpp` | 58-122 | RFC 1035 with Hive rules |
| Block header | `block_header.hpp` | 15-26 | previous, timestamp, witness, merkle root |
| Block number extraction | `block.cpp` | 13-16 | `endian_reverse_u32(id._hash[0])` |
| Merkle root calc | `block.cpp` | 19-46 | Pairwise hashing |
| Transaction struct | `transaction.hpp` | 12-53 | ref_block, expiration, operations |
| TaPoS encoding | `transaction.cpp` | 84-88 | Block number + prefix extraction |
| Tx ID computation | `transaction.cpp` | 58-64 | SHA-256 truncated to 20 bytes |
| Signature digest | `transaction.cpp` | 29-38 | chain_id + transaction → SHA-256 |
| Transaction validation | `transaction.cpp` | 40-56 | operations.size() > 0, per-op validate |
| Version struct | `version.hpp` | 15-77 | Major.HF.release in uint32 |
| Hardfork version | `version.hpp` | 79-102 | Masks release bits |
| HF version vote | `version.hpp` | 104-111 | HF version + activation time |
| Hardfork blocks | `hardfork_block.hpp` | 3-30 | All 28 HF activation blocks |
| HF count | `hardfork.d/0-preamble.hf` | 16-19 | `HIVE_NUM_HARDFORKS = 28` |
| Chain IDs | `config.hpp` | 137-143 | Mainnet "beeab0de...", testnet, mirrornet |
| HBD interest calc | `hbd_interest.hpp` | 8-23 | Balance-seconds / year * rate |
| Collateral estimation | `hive_collateral.hpp` | 8-26 | 200% ratio with 5% fee |
| Testnet overrides | `testnet_blockchain_configuration.hpp` | 27-285 | All configurable defaults |
| `base_operation` | `base.hpp` | 13-29 | Required authorities interface |

---

## Discrepancies and Potential Issues

### 1. `HIVE_BLOCKCHAIN_PRECISION` Naming
- **File**: `config.hpp:371`
- **Issue**: Comment says "actually HBD precision" but the value (1000) is the same 10^3 precision used for both HIVE and HBD. The comment is misleading — it should say "HBD/HIVE precision" or better yet, use `HIVE_PRECISION_HIVE` directly.

### 2. HF 0.17 and 0.18 Activation Gap
- **File**: `hardfork_block.hpp:19-20`
- **Issue**: HF17 at block 10,629,455 and HF18 at block 10,629,486 — only 31 blocks apart (~93 seconds). This is effectively simultaneous and suggests HF18 was a hotfix or companion change to HF17.

### 3. Address Prefix Still "STM" (Steem)
- **File**: `config.hpp:212`
- **Issue**: `HIVE_ADDRESS_PREFIX = "STM"` — the old Steem prefix is retained for backward compatibility. This is intentional (changing it would break all existing keys) but worth noting for documentation.

### 4. `HIVE_INIT_SUPPLY` is 0 on Mainnet
- **File**: `config.hpp:49-50`
- **Issue**: Mainnet initial HIVE and HBD supply are both 0, while testnet defaults to 243M HIVE and 7M HBD. The mainnet genesis block relied on the mining mechanism to create initial supply. This is correct behavior but often surprising to newcomers.

### 5. `HF26 START == STOP` for HBD Printing
- **File**: `config.hpp:343-344`
- **Issue**: `HIVE_HBD_START_PERCENT_HF26 = HIVE_HBD_STOP_PERCENT_HF26 = 2000` (20%). When start equals stop, there is no gradual reduction — it's a binary on/off at exactly 20% market cap. This is likely intentional but contrasts with all previous hardforks which had a gradual reduction range.

---

## Open Questions

1. **How exactly are block IDs computed?** The `block_header::legacy_digest()` method hashes the header, but the actual block ID construction (mixing in block number) likely happens in the chain database layer (`full_block_type`), not in the protocol library. Need to examine chain-level code.

2. **What is the exact VEST/HIVE conversion ratio at genesis?** The testnet configuration defaults to 1800:1000, but this was modified by the HF1 "vesting share split" that multiplied VESTS by 1,000,000. The current effective ratio is set by the dynamic global properties.

3. **How are operation authority requirements enforced?** Each operation type declares its required authorities via virtual methods, but the mapping of "which operations are posting-level vs active-level" is defined per-operation in the `hive_operations.cpp` and related files — covered in Part 02 (Operations Catalog).

4. **What are the exact RC cost parameters?** The RC system constants (`HIVE_RC_*`) define timing but the actual resource costs (state bytes, execution time, bandwidth) are defined elsewhere in the chain layer.

5. **How does the witness scheduling algorithm work?** The `HIVE_VIRTUAL_SCHEDULE_LAP_LENGTH` constants hint at a virtual-time-based scheduling system, but the actual algorithm is in the chain database layer — covered in Part 06 (Consensus).

6. **What is `hf_21_stall_block`?** In `testnet_blockchain_configuration.hpp:284`, there's a `hf_21_stall_block = 35922615` with comment "remove when `iceberg` is implemented". This appears to be a testnet-specific workaround for some HF21 issue. The "iceberg" reference is unexplained.
