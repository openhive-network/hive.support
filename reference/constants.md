# Hive Configuration Constants Reference

Source: hive-core release 1.28.7. Constants from `libraries/protocol/include/hive/protocol/config.hpp` unless noted.

Percentage values use basis-point encoding: `HIVE_100_PERCENT = 10,000`, `HIVE_1_PERCENT = 100`, `HIVE_1_BASIS_POINT = 1`.

---

## Timing

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_BLOCK_INTERVAL` | 3 s | Block production interval |
| `HIVE_BLOCKS_PER_HOUR` | 1,200 | |
| `HIVE_BLOCKS_PER_DAY` | 28,800 | |
| `HIVE_BLOCKS_PER_YEAR` | 10,512,000 | |
| `HIVE_ONE_DAY_SECONDS` | 86,400 | |
| `HIVE_SECONDS_PER_YEAR` | 31,536,000 | |
| `HIVE_MAX_TIME_UNTIL_EXPIRATION` | 3,600 s | Runtime expiration cap (1 hr); before HF28 also the hard limit on the `expiration` field |
| `HIVE_MAX_TIME_UNTIL_SIGNATURE_EXPIRATION` | 86,400 s | HF28+: max offset of the `expiration` field (1 day); the node still treats the tx as expired 1 hr after first validation (`database.cpp:2536-2548`) |
| `HIVE_CASHOUT_WINDOW_SECONDS` | 604,800 s | Post payout window (7 days) |
| `HIVE_CASHOUT_WINDOW_SECONDS_PRE_HF12` | 86,400 s | 1 day |
| `HIVE_CASHOUT_WINDOW_SECONDS_PRE_HF17` | 43,200 s | 12 hours |
| `HIVE_SECOND_CASHOUT_WINDOW` | 2,592,000 s | 30 days |
| `HIVE_MAX_CASHOUT_WINDOW_SECONDS` | 1,209,600 s | 14 days |
| `HIVE_UPVOTE_LOCKOUT_SECONDS` | 43,200 s | 12 hours before cashout |
| `HIVE_MIN_ROOT_COMMENT_INTERVAL` | 300 s | 5 min between root posts |
| `HIVE_MIN_REPLY_INTERVAL` | 3 s | Between replies |
| `HIVE_MIN_COMMENT_EDIT_INTERVAL` | 3 s | Between edits |
| `HIVE_POST_AVERAGE_WINDOW` | 86,400 s | 1 day |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF6` | 1,800 s | 30 min |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF20` | 900 s | 15 min |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF21` | 300 s | 5 min |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF25` | 0 s | Disabled |
| `HIVE_EARLY_VOTING_SECONDS_HF25` | 86,400 s | 24 hours |
| `HIVE_MID_VOTING_SECONDS_HF25` | 172,800 s | 48 hours |

## Block / Transaction Limits

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_MAX_BLOCK_SIZE` | 2,097,152 B | 2 MB hard maximum |
| `HIVE_MIN_BLOCK_SIZE_LIMIT` | 65,536 B | = MAX_TRANSACTION_SIZE |
| `HIVE_MIN_BLOCK_SIZE` | 115 B | Minimum valid block |
| `HIVE_MAX_TRANSACTION_SIZE` | 65,536 B | 64 KB |
| `HIVE_MIN_TRANSACTION_SIZE_LIMIT` | 1,024 B | 1 KB |
| `HIVE_MAX_MEMO_SIZE` | 2,048 | Characters |
| `HIVE_MAX_PERMLINK_LENGTH` | 256 | Characters |
| `HIVE_MAX_WITNESS_URL_LENGTH` | 2,048 | Characters |
| `HIVE_MAX_URL_LENGTH` | 127 | Witness URL in operations |
| `HIVE_MAX_SHARE_SUPPLY` | 10^15 | Max total HIVE supply |
| `HIVE_MAX_SATOSHIS` | 2^62 - 1 | Max single asset field |
| `HIVE_BLOCKCHAIN_PRECISION` | 1,000 | 10^3 (HIVE/HBD precision) |
| `HIVE_BLOCK_GENERATION_POSTPONED_TX_LIMIT` | 5 | Max postponed txs per block |
| `HIVE_PENDING_TRANSACTION_EXECUTION_LIMIT` | 200 ms | Time budget for pending txs |
| `HIVE_MAX_UNDO_HISTORY` | 10,000 | Undo stack depth |

## Witness / DPoS

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_MAX_WITNESSES` | 21 | Witnesses per round |
| `HIVE_MAX_VOTED_WITNESSES_HF0` | 19 | Elected (pre-HF17) |
| `HIVE_MAX_MINER_WITNESSES_HF0` | 1 | Miner slots (pre-HF17) |
| `HIVE_MAX_RUNNER_WITNESSES_HF0` | 1 | Runner-up (pre-HF17) |
| `HIVE_MAX_VOTED_WITNESSES_HF17` | 20 | Elected (post-HF17) |
| `HIVE_MAX_MINER_WITNESSES_HF17` | 0 | Mining disabled |
| `HIVE_MAX_RUNNER_WITNESSES_HF17` | 1 | Runner-up (post-HF17) |
| `HIVE_HARDFORK_REQUIRED_WITNESSES` | 17 | 17/21 for HF activation |
| `HIVE_MAX_ACCOUNT_WITNESS_VOTES` | 30 | Max votes per account |
| `HIVE_WITNESS_SHUTDOWN_THRESHOLD` | 28,800 blocks | 1 day before shutdown |
| `HIVE_START_MINER_VOTING_BLOCK` | 864,000 | 30 days of blocks |
| `HIVE_START_VESTING_BLOCK` | 201,600 | 7 days of blocks |
| `HIVE_IRREVERSIBLE_THRESHOLD` | 7,500 | 75% for irreversibility |

## Vesting / Power Down

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_VESTING_WITHDRAW_INTERVALS` | 13 | 13 weekly withdrawals (current) |
| `HIVE_VESTING_WITHDRAW_INTERVALS_PRE_HF_16` | 104 | 2 years weekly (pre-HF16) |
| `HIVE_VESTING_WITHDRAW_INTERVAL_SECONDS` | 604,800 s | 1 week per interval |
| `HIVE_MAX_WITHDRAW_ROUTES` | 10 | Max withdrawal destinations |
| `HIVE_VOTING_MANA_REGENERATION_SECONDS` | 432,000 s | 5 days full regen |
| `HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS` | 2,592,000 s | 30-day delay for new vests |
| `HIVE_DELAYED_VOTING_INTERVAL_SECONDS` | 86,400 s | 1-day granularity |
| `HIVE_INITIAL_VOTE_POWER_RATE` | 40 | Votes/day at full power |
| `HIVE_REDUCED_VOTE_POWER_RATE` | 10 | Reduced rate |

## Rewards

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_INFLATION_RATE_START_PERCENT` | 978 | 9.78% initial inflation |
| `HIVE_INFLATION_RATE_STOP_PERCENT` | 95 | 0.95% long-term floor |
| `HIVE_INFLATION_NARROWING_PERIOD` | 250,000 blocks | -0.01% per period |
| `HIVE_CONTENT_REWARD_PERCENT_HF16` | 7,500 | 75% to content |
| `HIVE_CONTENT_REWARD_PERCENT_HF21` | 6,500 | 65% to content |
| `HIVE_VESTING_FUND_PERCENT_HF16` | 1,500 | 15% to vesting |
| `HIVE_MINER_PAY_PERCENT` | 100 | 1% to witnesses |
| `HIVE_MIN_PAYOUT_HBD` | 0.020 HBD | Minimum payout threshold |
| `HIVE_VOTE_DUST_THRESHOLD` | 50,000,000 | Min rshares for non-dust vote |
| `HIVE_DOWNVOTE_POOL_PERCENT_HF21` | 2,500 | 25% free downvote pool |

## HBD / Stablecoin

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_DEFAULT_HBD_INTEREST_RATE` | 1,000 | 10% APR default |
| `HIVE_HBD_INTEREST_COMPOUND_INTERVAL_SEC` | 2,592,000 s | Compounds every 30 days |
| `HIVE_HBD_START_PERCENT_HF14` | 200 | Start reducing at 2% cap |
| `HIVE_HBD_STOP_PERCENT_HF14` | 500 | Stop printing at 5% cap |
| `HIVE_HBD_START_PERCENT_HF20` | 900 | Start reducing at 9% cap |
| `HIVE_HBD_STOP_PERCENT_HF20` | 1,000 | Stop printing at 10% cap |
| `HIVE_HBD_START_PERCENT_HF26` | 2,000 | Binary cutoff at 20% cap |
| `HIVE_HBD_STOP_PERCENT_HF26` | 2,000 | Same as start (no gradual) |
| `HIVE_HBD_HARD_LIMIT_PRE_HF26` | 1,000 | Artificial price floor at 10% |
| `HIVE_HBD_HARD_LIMIT` | 3,000 | Artificial price floor at 30% |
| `HIVE_CONVERSION_DELAY` | ~3.5 days | HBD-to-HIVE conversion delay |
| `HIVE_CONVERSION_DELAY_PRE_HF_16` | ~7 days | Double (pre-HF16) |
| `HIVE_COLLATERALIZED_CONVERSION_DELAY` | ~3.5 days | HIVE-to-HBD conversion delay |
| `HIVE_CONVERSION_COLLATERAL_RATIO` | 20,000 | 200% collateral required |
| `HIVE_COLLATERALIZED_CONVERSION_FEE` | 500 | 5% fee |
| `HIVE_SAVINGS_WITHDRAW_TIME` | 3 days | Mandatory savings delay |
| `HIVE_SAVINGS_WITHDRAW_REQUEST_LIMIT` | 100 | Max pending savings withdrawals |

### Feed System

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_FEED_INTERVAL_BLOCKS` | 1,200 | Every hour |
| `HIVE_FEED_HISTORY_WINDOW` | 84 | 3.5 days of intervals |
| `HIVE_FEED_HISTORY_WINDOW_PRE_HF_16` | 168 | 7 days of intervals |
| `HIVE_MAX_FEED_AGE_SECONDS` | 604,800 s | 7 days before feed expires |
| `HIVE_MIN_FEEDS` | 7 | MAX_WITNESSES/3 required |

## DHF / Proposals

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_PROPOSAL_FUND_PERCENT_HF0` | 0 | No DHF before HF21 |
| `HIVE_PROPOSAL_FUND_PERCENT_HF21` | 1,000 | 10% of inflation to DHF |
| `HIVE_TREASURY_FEE` | 10,000 | 10 HBD proposal creation fee |
| `HIVE_PROPOSAL_SUBJECT_MAX_LENGTH` | 80 | Characters |
| `HIVE_PROPOSAL_MAX_IDS_NUMBER` | 5 | Max IDs per update/remove op |
| `HIVE_PROPOSAL_FEE_INCREASE_DAYS` | 60 | Days before fee increases |
| `HIVE_PROPOSAL_FEE_INCREASE_AMOUNT` | 1,000 | +1 HBD per 60 days |
| `HIVE_PROPOSAL_CONVERSION_RATE` | 5 | 0.05% (5 basis points) |
| `HIVE_PROPOSAL_MAINTENANCE_PERIOD` | 3,600 s | Process proposals hourly |
| `HIVE_PROPOSAL_MAINTENANCE_CLEANUP` | 86,400 s | 1 day |
| `HIVE_DAILY_PROPOSAL_MAINTENANCE_PERIOD` | 86,400 s | 1 day |
| `HIVE_GOVERNANCE_VOTE_EXPIRATION_PERIOD` | 365 days | Governance votes expire yearly |

## Account Creation

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_MIN_ACCOUNT_NAME_LENGTH` | 3 | Characters |
| `HIVE_MAX_ACCOUNT_NAME_LENGTH` | 16 | Characters |
| `HIVE_MIN_ACCOUNT_CREATION_FEE` | 1 | 0.001 HIVE (mainnet) |
| `HIVE_MAX_ACCOUNT_CREATION_FEE` | 1,000,000,000 | 1,000,000 HIVE |
| `HIVE_CREATE_ACCOUNT_WITH_HIVE_MODIFIER` | 30 | Fee multiplier for creation-with-HIVE |
| `HIVE_CREATE_ACCOUNT_DELEGATION_RATIO` | 5 | Delegation-to-fee ratio |
| `HIVE_CREATE_ACCOUNT_DELEGATION_TIME` | 30 days | Delegation lock period |
| `HIVE_MAX_AUTHORITY_MEMBERSHIP` | 40 | Max keys+accounts per authority |
| `HIVE_MAX_SIG_CHECK_DEPTH` | 2 | Authority recursion depth |
| `HIVE_MAX_SIG_CHECK_ACCOUNTS` | 125 | Max accounts in sig verification |
| `HIVE_MAX_PROXY_RECURSION_DEPTH` | 4 | Witness vote proxy chain depth |

### Owner Key Recovery

| Constant | Mainnet | Testnet | Description |
|----------|---------|---------|-------------|
| `HIVE_OWNER_AUTH_RECOVERY_PERIOD` | 30 days | 60 s | Recovery window |
| `HIVE_ACCOUNT_RECOVERY_REQUEST_EXPIRATION_PERIOD` | 1 day | 12 s | Request expiration |
| `HIVE_OWNER_UPDATE_LIMIT` | 60 min | 6 s | Rate limit on owner key changes |
| `HIVE_OWNER_AUTH_HISTORY_TRACKING_START_BLOCK_NUM` | 3,186,477 | 1 | |

## RC (Resource Credits)

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_RC_REGEN_TIME` | 432,000 s | 5 days (= voting mana regen) |
| `HIVE_RC_BUCKET_TIME_LENGTH` | 3,600 s | 1 hour per bucket |
| `HIVE_RC_WINDOW_BUCKET_COUNT` | 24 | 24 hours of buckets |
| `HIVE_RC_STATS_REPORT_FREQUENCY` | 28,800 blocks | 1 report per day |
| `HIVE_RC_HISTORICAL_ACCOUNT_CREATION_ADJUSTMENT` | 2,020,748,973 | ~2020.75 VESTS = 1 HIVE at HF20 |
| `HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP` | 100 | Max accounts per RC delegation |

## Assets

| Asset | Symbol | Legacy Symbol | Precision | NAI String | `asset_num` |
|-------|--------|---------------|-----------|------------|-------------|
| HIVE | `HIVE` | `STEEM` | 3 | `@@000000021` | 3,200,000,035 |
| HBD | `HBD` | `SBD` | 3 | `@@000000013` | 3,200,000,003 |
| VESTS | `VESTS` | `VESTS` | 6 | `@@000000037` | 3,200,000,070 |

## Misc

| Constant | Value | Description |
|----------|-------|-------------|
| `HIVE_ADDRESS_PREFIX` | `"STM"` | Public key prefix (kept from Steem) |
| `HIVE_NUM_HARDFORKS` | 28 | Total hardforks defined |
| `HIVE_MAX_COMMENT_DEPTH` | 65,535 | Effectively unlimited (current) |
| `HIVE_MAX_COMMENT_DEPTH_PRE_HF17` | 6 | Very shallow |
| `HIVE_SOFT_MAX_COMMENT_DEPTH` | 255 | Soft limit |
| `HIVE_MAX_COMMENT_BENEFICIARIES` | 8 | Beneficiary routes per post |
| `HIVE_BENEFICIARY_LIMIT` | 128 | Extended beneficiary limit |
| `HIVE_COMMENT_TITLE_LIMIT` | 256 | Characters |
| `HIVE_CUSTOM_OP_ID_MAX_LENGTH` | 32 | Characters |
| `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` | 8,192 | Bytes |
| `HIVE_CUSTOM_OP_BLOCK_LIMIT` | 5 | Max custom ops per block |
| `HIVE_MAX_RECURRENT_TRANSFER_END_DATE` | 730 days | 2 years |
| `HIVE_MAX_RECURRENT_TRANSFERS_PER_BLOCK` | 1,000 | Processing limit per block |
| `HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` | 24 hr | Minimum interval |
| `HIVE_MAX_OPEN_RECURRENT_TRANSFERS` | 255 | Per account |
| `HIVE_MAX_CONSECUTIVE_RECURRENT_TRANSFER_FAILURES` | 10 | Before cancellation |
| `HIVE_MAX_PENDING_TRANSFERS` | 255 | Max pending transfers |
| `HIVE_MAX_LIMIT_ORDER_EXPIRATION` | 2,419,200 s | 28 days |
| `HIVE_GLOBAL_REMOVE_THRESHOLD` | 200 | 100 on testnet |
| `HIVE_INIT_MINER_NAME` | `"initminer"` | Genesis block producer |
| `HIVE_MINER_ACCOUNT` | `"miners"` | Represents current witnesses |
| `HIVE_NULL_ACCOUNT` | `"null"` | Black hole (no authority) |
| `HIVE_TEMP_ACCOUNT` | `"temp"` | Wildcard authority (anyone) |
| `OBSOLETE_TREASURY_ACCOUNT` | `"steem.dao"` | Old treasury |
| `NEW_HIVE_TREASURY_ACCOUNT` | `"hive.fund"` | Current treasury (since HF24) |
| `HIVE_PROXY_TO_SELF_ACCOUNT` | `""` | Empty = vote directly |

## Testnet Overrides

Source: `testnet_blockchain_configuration.hpp`. Key constants that differ from mainnet defaults.

| Constant | Mainnet | Testnet | Notes |
|----------|---------|---------|-------|
| `HIVE_CASHOUT_WINDOW_SECONDS` | 604,800 s (7 days) | 3,600 s (1 hour) | |
| `HIVE_OWNER_AUTH_RECOVERY_PERIOD` | 30 days | 60 s | |
| `HIVE_ACCOUNT_RECOVERY_REQUEST_EXPIRATION_PERIOD` | 1 day | 12 s | |
| `HIVE_OWNER_UPDATE_LIMIT` | 60 min | 6 s | |
| `HIVE_OWNER_AUTH_HISTORY_TRACKING_START_BLOCK_NUM` | 3,186,477 | 1 | |
| `HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS` | 2,592,000 s (30 days) | 86,400 s (1 day) | |
| `HIVE_GOVERNANCE_VOTE_EXPIRATION_PERIOD` | 365 days | 5 days | |
| `HIVE_FEED_INTERVAL_BLOCKS` | 1,200 (1 hour) | 20 | |
| `HIVE_INIT_SUPPLY` | 0 | 243,000,000,000 | 243M HIVE |
| `HIVE_HBD_INIT_SUPPLY` | 0 | 7,000,000,000 | 7M HBD |
| `HIVE_MIN_ACCOUNT_CREATION_FEE` | 1 (0.001 HIVE) | 0 | |
| `HIVE_GLOBAL_REMOVE_THRESHOLD` | 200 | 100 | |
| Symbol names | HIVE/HBD | TESTS/TBD | |
| Chain ID | `beeab0de00...00` (literal hex) | `sha256("testnet")` | Mainnet id is the literal value via the `fc::sha256` hex ctor (`config.hpp:142`), **not** a hash; testnet is a real `sha256::hash("testnet")` (`config.hpp:69`) |
