# Findings: Protocol Foundation — Types, Assets, and Configuration Constants

## Summary

This document captures the complete protocol foundation of the Hive blockchain as defined in the C++ source code under `libraries/protocol/`, with chain-layer extensions (`libraries/chain/`) where the protocol layer delegates behavior (block IDs, signature validation rules, genesis state). Hive operates on a 3-second block interval with 21 witnesses, using three native assets (HIVE, HBD, VESTS) encoded via a Numeric Asset Identifier (NAI) system. The protocol layer defines ~190 consensus constants covering timing, economics, authority, and resource limits, all verified directly from `config.hpp` and related headers at release 1.28.7 (`1584099c3`).

## Key Discoveries

### 1. NAI Encoding Uses Reserved Space for Native Assets
- **What**: Native assets map to NAI data values 1 (HBD), 2 (HIVE), 3 (VESTS) — deep inside the reserved band below `SMT_MIN_NON_RESERVED_NAI = 10,000,000`, so SMT NAI generation can never produce them. Internally they are stored as `SMT_MAX_NAI + HIVE_NAI_X` (asset_num space), keeping them disjoint from every SMT `asset_num`. The ones-place digit of the string form doubles as a Damm checksum digit; per the header comment, string NAIs 0–9 all decode to NAI data 0, which is invalid — making the low space safe.
- **Where**: `asset_symbol.hpp:9-32` (esp. `SMT_MIN_NON_RESERVED_NAI` at `asset_symbol.hpp:14`, reserved-space comment at `asset_symbol.hpp:24-25`), `asset.cpp:128-165`
- **Impact**: Clever design that avoids collisions between native and SMT asset identifiers while keeping a compact `uint32_t` representation.

### 2. Legacy Steem Symbol Names Persist in Binary Protocol
- **What**: On mainnet, HIVE serializes as `STEEM` (`OBSOLETE_SYMBOL_SER`) and HBD serializes as `SBD` (`OBD_SYMBOL_SER`) in legacy wire format. On testnet, they become `TESTS` and `TBD`. Crucially, **legacy is the default binary pack mode** (`serialization_mode_controller::default_pack = pack_type::legacy`, `misc_utilities.hpp:32`), so blocks and the block_log are serialized with the old Steem symbol bytes to this day. The HF26 pack type (NAI-based) exists alongside it; the default *transaction* serialization for API-facing code is `hf26` (`misc_utilities.hpp:31`).
- **Where**: `asset_symbol.hpp:36-53`, `misc_utilities.hpp:23-32`
- **Impact**: Any tool parsing consensus binary serialization must handle the old STEEM/SBD symbol bytes. Transactions may arrive in either serialization (see Discovery 15).

### 3. HIVE_MAX_SATOSHIS is 2^62 - 1
- **What**: `HIVE_MAX_SATOSHIS = 4611686018427387903` which is exactly `(2^62 - 1)`. This is the maximum amount any single asset field can hold. Meanwhile `HIVE_MAX_SHARE_SUPPLY` is `1,000,000,000,000,000` (10^15) — the maximum total supply of HIVE tokens. The `share_type` is `safe<int64_t>`, providing overflow checking.
- **Where**: `config.hpp:355-356`, `types.hpp:76`
- **Impact**: The satoshis cap at 2^62-1 ensures that multiplication in `uint128_t` during price calculations never overflows.

### 4. Chain ID is "beeab0de", and Signature Validation Switches Chain ID at HF24's *Actual* Time
- **What**: `HIVE_CHAIN_ID = fc::sha256("beeab0de0000...")` (vanity hex), `OLD_CHAIN_ID` = empty sha256 (the Steem chain ID), mirrornet uses `"42000..."`, testnet uses `sha256::hash("testnet")`. Signature validation is time-dependent: transactions in blocks with timestamp ≤ `HIVE_HARDFORK_1_24_ACTUAL_TIME = 1602703884` (2020-10-14 — the *actual* delayed activation moment, not the scheduled `HIVE_HARDFORK_1_24_TIME = 1601992800` / 2020-10-06) validate against `OLD_CHAIN_ID`; later ones against `HIVE_CHAIN_ID`. New (mempool) transactions always use `HIVE_CHAIN_ID`. A comment also records that ECDSA canonicality checking was unified to a single mode (`bip_0062`) between HF27 and HF28.
- **Where**: `config.hpp:136-143`, `full_transaction.cpp:450-493`, `hardfork.d/1_24.hf:17-27`
- **Impact**: Chain ID is mixed into transaction signature digests, preventing cross-chain replay. Replaying pre-fork Steem history requires the old (empty) chain ID — hived handles this automatically by block timestamp.

### 5. Version Comparison Has Major-Version Compatibility Hack
- **What**: The `version` comparison template treats major versions 0 and 1 as equivalent (`0.HARDFORK == 1.HARDFORK`). This was added for HF24 (the Steem→Hive fork) where the major version changed from 0 to 1, but some witnesses still ran nodes reporting 0.x.
- **Where**: `version.hpp:48-75` (masking logic at `version.hpp:56-61`)
- **Impact**: `version(0, 23, 0) == version(1, 23, 0)` returns true. This is a permanent backward-compatibility quirk.

### 6. HBD Hard Limit Changed Significantly Across Hardforks
- **What**: The HBD-to-market-cap ratio at which printing stops changed dramatically: HF14 (2%→5%), HF20 (9%→10%), HF26 (20%→20% start/stop, identical). An artificial price floor kicks in at 10% pre-HF26 and 30% post-HF26.
- **Where**: `config.hpp:339-346`
- **Impact**: HF26 effectively doubled the "start reducing" threshold from 10% to 20% and raised the hard limit from 10% to 30%.

### 7. `HIVE_HARDFORK_1_28_BLOCK` Does Not Match Actual Activation Block
- **What**: `HIVE_HARDFORK_1_28_BLOCK = 100000000` (`hardfork_block.hpp:30`). All other `HIVE_HARDFORK_*_BLOCK` constants record the actual mainnet block at which each hardfork activated — these constants are NOT used in the activation mechanism (which is time-based via `process_hardforks()` at `database_hardfork.cpp:114`; requires `next_hardfork_time <= head_block_time()` plus witness supermajority for HF5+). The HF28 constant was set before activation and never updated. HF28 actually activated at block 101,319,928 (2025-11-19). HF28 carries real behavior changes behind hardfork guards — notably `HIVE_HARDFORK_1_28_ALLOW_STRICT_AND_MIXED_AUTHORITIES` and `HIVE_HARDFORK_1_28_ALLOW_REDUNDANT_SIGNATURES` (see Discovery 14).
- **Where**: `hardfork_block.hpp:30`, `database_hardfork.cpp:114-145`, `config.hpp:66/135/140`
- **Impact**: Minor code inconsistency. The constant could be updated to 101319928 to match all other entries in `hardfork_block.hpp`.

### 8. Transaction Expiration Hard Limit is 1 Hour
- **What**: `HIVE_MAX_TIME_UNTIL_EXPIRATION = 3600` seconds (1 hour). For signatures specifically, the limit is 1 day (`HIVE_MAX_TIME_UNTIL_SIGNATURE_EXPIRATION = 86400`).
- **Where**: `config.hpp:232-233`
- **Impact**: Transactions must be broadcast within 1 hour of creation. The separate signature expiration allows pre-signed transactions with a longer validity window.

### 9. Block ID is SHA-224 of the *Signed* Header with Block Number Spliced In; Block Digest is SHA-256 of the *Unsigned* Header
- **What**: The real block ID computation lives in the chain layer, not protocol. `full_block_type::construct_block_id()`: (1) `sha224` over the serialized `signed_block_header` bytes (header **including** `witness_signature`), (2) overwrite the first 4 bytes of that hash with `endian_reverse_u32(block_num)`, (3) truncate to 20 bytes (`block_id_type` is ripemd160-sized but holds no RIPEMD hash). The **digest that the witness signs** is different: `sha256` over the serialized **unsigned** `block_header` only. The witness signature is `signer->sign_compact(digest)`. Notably, **no chain ID is mixed into the block digest** (unlike transaction signatures) — cross-chain replay of blocks is instead prevented by the `previous` block-ID chain. The protocol-layer `block_header::legacy_digest()` (`block.cpp:7-11`) and `signed_block::legacy_calculate_merkle_root()` exist "just for unit tests; actual function is in full_block" (`block.cpp:18`).
- **Where**: `full_block.cpp:305-316` (construct_block_id), `full_block.cpp:144-153` (digest + signing during production), `full_block.cpp:356-364` (layout comment), `full_block.cpp:336-339` (signee recovery), `block_header.hpp:17-19`
- **Impact**: Block IDs sort by height (first 4 bytes = big-endian block number), enabling `num_from_id()` (`block.cpp:13-16`) and the TaPoS scheme. Any reimplementation must hash the *signed* header for the ID but the *unsigned* header for signature verification.

### 10. Genesis VESTS Price is 1:1 (in Display Units); HF1 Multiplied All VESTS by 1,000,000
- **What**: `dynamic_global_property_object::get_vesting_share_price()` returns `VEST_price(1000000, 1000)` — 1,000,000 VESTS-satoshis (= 1.000000 VESTS) per 1,000 HIVE-satoshis (= 1.000 HIVE) — whenever the vesting pools are empty, i.e. at genesis. At HF1 (block 905,693), `perform_vesting_share_split(1000000)` multiplied `total_vesting_shares`, every account's `vesting_shares`, `withdrawn`, `to_withdraw`, and proxied votes by 10^6 (the "vesting share split"). Testnet's configurable initial price defaults to `VEST_price(1800, 1000)` *pre-split*, with an explicit warning that HF1 will multiply the VEST side by 1,000,000.
- **Where**: `libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:87-92`, `database_hardfork.cpp:189-191`, `database_comment.cpp:612-667`, `testnet_blockchain_configuration.hpp:260-270`
- **Impact**: Resolves the genesis-ratio question: 1 HIVE = 1 VESTS at genesis, ×10^6 at HF1; ever since, the effective ratio floats as `total_vesting_shares / total_vesting_fund_hive` in the dgpo.

### 11. `hf_21_stall_block` Replays a Real HF21 Overflow Bug; "iceberg" is the Blockchain Converter Plugin
- **What**: At HF21 the downvote manabar was introduced. Its original `max_mana` computation, `effective_vests * downvote_pool_percent / HIVE_100_PERCENT`, was done in plain `int64_t` and **overflowed for very large vesting balances — and that overflow made it into the mainnet chain**. `update_manabar()` therefore keeps the buggy arithmetic for blocks ≤ `HIVE_HF_21_STALL_BLOCK = 35,922,615` (mainnet constant; 829 blocks ≈ 41 minutes after HF21 activation at 35,921,786) and logs "NOTIFYALERT! max mana overflow made it in to the chain" if it triggers; after that block the corrected `uint128_t` math applies. Testnet and iceberg-enabled converter builds always use the fixed math (`#if defined(IS_TEST_NET) || defined(HIVE_CONVERTER_ICEBERG_PLUGIN_ENABLED)`). "iceberg" is the `iceberg_generate` plugin of `programs/blockchain_converter/` — it fabricates a valid chain from only a *range* of mainnet blocks (e.g. last 5M), creating missing accounts/comments on the fly; chains generated that way never contain the historic overflow, so the testnet-side knob (`configuration_data.hf_21_stall_block`, settable via the `alternate-chain-spec` JSON) can be removed once mirrornet block logs come from iceberg.
- **Where**: `manabar.hpp:120-135`, `hardfork.d/0_21.hf:18-22`, `testnet_blockchain_configuration.hpp:284`, `chain_plugin.cpp:1760-1761`, `programs/blockchain_converter/README.md:308-324`
- **Impact**: A consensus-relevant replay quirk: any reimplementation of mana regeneration must reproduce the int64 overflow for mainnet blocks 35,921,786–35,922,615 or it will fork on replay.

### 12. HF9 Hardcodes 151 Compromised Accounts and a Recovery Key
- **What**: `hardfork.d/0_9.hf:15-172` contains a hardcoded `std::set` of 151 account names (`get_compromised_accounts()`). At HF9 application, each account's owner, active, and posting authorities are forcibly replaced with the single key `STM7sw22HqsXbz7D2CmJfmMwt9rimtk518dRzsR1f8Cgw52dQR1pR` (`HIVE_DEFAULT_HF_9_COMPROMISED_ACCOUNTS_PUBLIC_KEY_STR`, `config.hpp:18`). This was the consensus response to the July 2016 account-compromise incident on Steem. On testnet the key is configurable (`testnet_blockchain_configuration.hpp:73,133`).
- **Where**: `config.hpp:18`, `hardfork.d/0_9.hf:15-172`, `database_hardfork.cpp:213-226`
- **Impact**: Precedent for protocol-level account intervention; the account list and key are consensus data that all replaying nodes apply identically.

### 13. Mainnet Genesis-Time Comments in config.hpp are Wrong
- **What**: `HIVE_GENESIS_TIME = 1458835200` (`config.hpp:152`) carries the comment "Friday, January 1, 2016 12:00:00 AM UTC", but 1458835200 is actually **Thursday, March 24, 2016 16:00:00 UTC** (the comment was copy-pasted from the testnet branch at `config.hpp:71-72`, where 1451606400 *is* Jan 1, 2016). Next line, `HIVE_MINING_TIME = 1458838800` (`config.hpp:154`) says "Thursday, March 24, 2016 4:00:00 PM UTC", but 1458838800 is **17:00 UTC** — that comment describes the genesis value one line above. Both values are correct; both comments are wrong/shifted.
- **Where**: `config.hpp:150-154` (mainnet), `config.hpp:71-72` (testnet)
- **Impact**: Documentation hazard only — but anyone citing genesis time from the comments gets the wrong date. Steem/Hive mainnet genesis: 2016-03-24T16:00:00Z; mining (PoW acceptance) began one hour later.

### 14. Authority Verification: Posting Isolation, Role Upgrade, and the HF28 "Strict and Mixed" Switch
- **What**: The full verification algorithm lives in protocol `verify_authority_impl()`. Pre-HF28 behavior (`allow_strict_and_mixed_authorities = false`): (a) a transaction with any posting-required operation **may not** also require active/owner/witness/other authorities (`transaction_util.cpp:59-74`); (b) **role upgrade** — a posting requirement is satisfied by posting *or* active *or* owner authority (`transaction_util.cpp:101-104`), an active requirement by active *or* owner (`transaction_util.cpp:146-158`); (c) signatures not consumed by verification cause rejection via `tx_irrelevant_sig` ("Unnecessary signature(s) detected", `transaction_util.cpp:184-188, 250-252`). After HF28 both flags flip (`database.cpp:2612-2613`): mixing posting with active/owner in one transaction becomes legal, role checks become **strict** (an owner key no longer auto-satisfies active/posting requirements), and redundant signatures are tolerated. Also: `HIVE_MAX_AUTHORITY_MEMBERSHIP` (40) and `HIVE_MAX_SIG_CHECK_ACCOUNTS` (125) are passed as 0 (unlimited) for blocks before HF20 (`database.cpp:2621-2622`).
- **Where**: `transaction_util.cpp:18-192`, `database.cpp:2598-2626`, `sign_state.hpp:167+` (weight accumulation/recursion)
- **Impact**: Critical for wallet/signing implementations: today an owner key signs anything, but post-HF28 a transaction must carry signatures for the exact roles required, and posting+active mixing becomes possible.

### 15. Transactions Validate Against Their Actual Wire Bytes; Either Serialization is Accepted
- **What**: `full_transaction_type::compute_sig_digest()` hashes `chain_id || <the exact serialized bytes the transaction arrived in>` (`full_transaction.cpp:110-116`) — not a re-serialization. A transaction may be packed in legacy or HF26 format; `is_legacy_pack()` detects which by re-packing under a legacy guard and comparing bytes (`full_transaction.cpp:263-284`). Duplicate signatures are rejected during key recovery (`tx_duplicate_sig`, `full_transaction.cpp:145-148`). Transaction IDs are likewise the first 20 bytes of SHA-256 over the actual serialized transaction (`full_transaction.cpp:93-108`; protocol equivalent `transaction.cpp:58-64`).
- **Where**: `full_transaction.cpp:93-160, 263-284`, `misc_utilities.hpp:23-32`
- **Impact**: Signers choose a serialization; the chain honors whichever they signed. Tools recomputing tx IDs must serialize exactly as the transaction was packed on the wire.

### 16. Every config.hpp Constant is Exported via the API
- **What**: `config.hpp:12-14` warns: "Every symbol defined here needs to be handled appropriately in get_config.cpp. This is checked by get_config_check.sh called from Dockerfile." The generated `get_config.d/get_config.cpp.in` materializes the full constant table served by `database_api.get_config`.
- **Where**: `config.hpp:12-14`, `libraries/protocol/get_config.d/get_config.cpp.in`
- **Impact**: The authoritative runtime view of all constants (including testnet overrides) is one API call away — useful for verifying a live node's compiled configuration.

---

## Configuration Constants Reference

All constants from `config.hpp` and related headers, organized by domain. Values shown are for **mainnet** unless otherwise noted.

### Genesis & Chain Identity

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_CHAIN_ID` | sha256 `beeab0de00...00` | Vanity chain ID since HF24 (`config.hpp:142`) |
| `OLD_CHAIN_ID` | empty sha256 | Steem chain ID, used for sig validation of pre-HF24 blocks (`config.hpp:141`) |
| Mirrornet chain ID | sha256 `42000...00` | `config.hpp:137` |
| `HIVE_GENESIS_TIME` | 1458835200 | 2016-03-24T16:00:00Z (comment in source is wrong — see Discrepancy 6) |
| `HIVE_MINING_TIME` | 1458838800 | 2016-03-24T17:00:00Z |
| `HIVE_INIT_PUBLIC_KEY_STR` | `STM8GC13u...` | initminer key (`config.hpp:42`) |
| `HIVE_INIT_MINER_NAME` | `"initminer"` | Genesis witness account |
| `HIVE_NUM_INIT_MINERS` | 1 | `config.hpp:220` |
| `HIVE_INIT_SUPPLY` / `HIVE_HBD_INIT_SUPPLY` | 0 / 0 | Mainnet starts empty; supply mined (`config.hpp:49-50`) |
| HF9 compromised-accounts key | `STM7sw22H...` | `config.hpp:18`, applied at HF9 to 151 accounts |
| `HIVE_BLOCKCHAIN_VERSION` | 1.28.7 | `config.hpp:140` |
| `HIVE_NUM_HARDFORKS` | 28 | `hardfork.d/0-preamble.hf:16-19` |

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
| `HIVE_SECOND_CASHOUT_WINDOW` | 2,592,000 | seconds | 30 days (testnet: 3 days, `config.hpp:76`) |
| `HIVE_MAX_CASHOUT_WINDOW_SECONDS` | 1,209,600 | seconds | 14 days (testnet: 1 day) |
| `HIVE_UPVOTE_LOCKOUT_HF7` | 60 | seconds | 1 minute (`config.hpp:160`) |
| `HIVE_UPVOTE_LOCKOUT_SECONDS` | 43,200 | seconds | 12 hours before cashout |
| `HIVE_UPVOTE_LOCKOUT_HF17` | 12 hours | fc::hours | Same as above, typed (testnet: 5 minutes) |
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
| `HIVE_POST_WEIGHT_CONSTANT` | (4×10000)² | — | Targets ~2 posts/day average (`config.hpp:251`) |

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
| `HIVE_VIRTUAL_SCHEDULE_LAP_LENGTH` | 2^64 − 1 | uint128(0, uint64_max) — pre-HF26 virtual-time lap (`config.hpp:383`) |
| `HIVE_VIRTUAL_SCHEDULE_LAP_LENGTH2` | 2^128 − 1 | uint128 max — post-HF26 lap (`config.hpp:384`); algorithm in `witness_schedule.cpp` (Part 06) |
| `HIVE_IRREVERSIBLE_THRESHOLD` | 7,500 (75%) | Witness participation for LIB advance |

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
| `HIVE_MIN_PAYOUT_HBD` | 0.020 HBD | Minimum payout threshold (`HBD_asset(20)`) |
| `HIVE_VOTE_DUST_THRESHOLD` | 50,000,000 | Vote rshares below this are treated as dust |
| `HIVE_DOWNVOTE_POOL_PERCENT_HF21` | 2,500 | 25% of upvote mana available as free downvotes |
| `HIVE_HF21_CONVERGENT_LINEAR_RECENT_CLAIMS` | 503,600,561,838,938,636 | uint128 seed for HF21 convergent-linear curve (`config.hpp:267`) |
| `HIVE_CONTENT_CONSTANT_HF0` | 2,000,000,000,000 | Reward curve constant (`config.hpp:299`) |
| `HIVE_CONTENT_CONSTANT_HF21` | 2,000,000,000,000 | Same value, uint128 form (`config.hpp:268`) |
| `HIVE_RECENT_RSHARES_DECAY_TIME_HF17` | 30 days | Reward fund recent-claims decay (`config.hpp:297`) |
| `HIVE_RECENT_RSHARES_DECAY_TIME_HF19` | 15 days | `config.hpp:298` |
| `HIVE_INITIAL_VOTE_POWER_RATE` | 40 | Votes per day at full power |
| `HIVE_REDUCED_VOTE_POWER_RATE` | 10 | Reduced rate |
| `HIVE_MAX_RATION_DECAY_RATE` | 1,000,000 | `config.hpp:271` |

### Legacy PoW Mining & Pre-HF16 APR Constants

These governed early-Steem economics; retained for replay correctness.

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MINING_REWARD` | 1.000 HIVE | `HIVE_asset(1000)` per PoW (`config.hpp:282`) |
| `HIVE_EQUIHASH_N` / `HIVE_EQUIHASH_K` | 140 / 6 | Equihash params for later PoW (`config.hpp:283-284`) |
| `HIVE_MIN_CONTENT_REWARD` / `HIVE_MIN_CURATE_REWARD` / `HIVE_MIN_PRODUCER_REWARD` / `HIVE_MIN_POW_REWARD` | 1.000 HIVE | All alias `HIVE_MINING_REWARD` (`config.hpp:291-294`) |
| `HIVE_APR_PERCENT_MULTIPLY_PER_BLOCK` | 0x5ccce802de5f | Fixed-point per-block APR multiplier (`config.hpp:305-308`) |
| `HIVE_APR_PERCENT_SHIFT_PER_BLOCK` | 87 | `config.hpp:310` |
| `HIVE_APR_PERCENT_MULTIPLY_PER_ROUND` | 0x79ccf5c73480 | `config.hpp:312-315` |
| `HIVE_APR_PERCENT_SHIFT_PER_ROUND` | 83 | `config.hpp:317` |
| `HIVE_APR_PERCENT_MULTIPLY_PER_HOUR` | 0x6cc139a15cbd | `config.hpp:321-324` |
| `HIVE_APR_PERCENT_SHIFT_PER_HOUR` | 77 | `config.hpp:327` |
| `HIVE_CURATE_APR_PERCENT` | 3,875 | Sums with below to 100% (`config.hpp:331-335`) |
| `HIVE_CONTENT_APR_PERCENT` | 3,875 | |
| `HIVE_LIQUIDITY_APR_PERCENT` | 750 | |
| `HIVE_PRODUCER_APR_PERCENT` | 750 | |
| `HIVE_POW_APR_PERCENT` | 750 | |

### Legacy Liquidity Rewards (disabled since HF12/HF14 era)

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_LIQUIDITY_TIMEOUT_SEC` | 7 days | Volume resets after a week (`config.hpp:286`) |
| `HIVE_MIN_LIQUIDITY_REWARD_PERIOD_SEC` | 60 s | Min time on books (`config.hpp:287`) |
| `HIVE_LIQUIDITY_REWARD_PERIOD_SEC` | 3,600 s | `config.hpp:288` |
| `HIVE_LIQUIDITY_REWARD_BLOCKS` | 1,200 | period/block interval (`config.hpp:289`) |
| `HIVE_MIN_LIQUIDITY_REWARD` | 1,200.000 HIVE | `1000*blocks` satoshis (`config.hpp:290`) |

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

### Vesting (Power Up/Down) & Delegation

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_VESTING_WITHDRAW_INTERVALS_PRE_HF_16` | 104 | 2 years of weekly withdrawals |
| `HIVE_VESTING_WITHDRAW_INTERVALS` | 13 | 13 weeks (current) |
| `HIVE_VESTING_WITHDRAW_INTERVAL_SECONDS` | 604,800 | = `CASHOUT_WINDOW_SECONDS` (1 week) |
| `HIVE_VOTING_MANA_REGENERATION_SECONDS` | 432,000 | 5 days |
| `HIVE_MAX_WITHDRAW_ROUTES` | 10 | Max withdrawal destinations |
| `HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS` | 2,592,000 | 30 days — delay before new vests vote |
| `HIVE_DELAYED_VOTING_INTERVAL_SECONDS` | 86,400 | 1 day granularity for delayed voting |
| `HIVE_DELEGATION_RETURN_PERIOD_HF0` | 604,800 | = cashout window (`config.hpp:390`) |
| `HIVE_DELEGATION_RETURN_PERIOD_HF20` | 432,000 | = mana regen, 5 days (`config.hpp:391`) |

### Account/Authority Limits

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MIN_ACCOUNT_NAME_LENGTH` | 3 | Characters |
| `HIVE_MAX_ACCOUNT_NAME_LENGTH` | 16 | Characters |
| `HIVE_MIN_ACCOUNT_CREATION_FEE` | 1 | 0.001 HIVE (mainnet); 0 on testnet |
| `HIVE_MAX_ACCOUNT_CREATION_FEE` | 1,000,000,000 | 1,000,000 HIVE |
| `HIVE_MAX_AUTHORITY_MEMBERSHIP` | 40 | Max keys+accounts in an authority; **41 on mirrornet converter builds** ("40 + second auth", `config.hpp:374-378`); enforced only post-HF20 (`database.cpp:2621`) |
| `HIVE_MAX_SIG_CHECK_DEPTH` | 2 | Max authority recursion depth |
| `HIVE_MAX_SIG_CHECK_ACCOUNTS` | 125 | Max accounts checked during sig verification; enforced post-HF20 (`database.cpp:2622`) |
| `HIVE_MAX_PROXY_RECURSION_DEPTH` | 4 | Max witness vote proxy chain |
| `HIVE_CREATE_ACCOUNT_WITH_HIVE_MODIFIER` | 30 | Multiplier for creation-with-HIVE fee |
| `HIVE_CREATE_ACCOUNT_DELEGATION_RATIO` | 5 | Delegation-to-fee ratio |
| `HIVE_CREATE_ACCOUNT_DELEGATION_TIME` | 30 days | Delegation lock period |

### Account Subsidies (HF20+)

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_ACCOUNT_SUBSIDY_PRECISION` | 10,000 | = `HIVE_100_PERCENT` (`config.hpp:405`) |
| `HIVE_WITNESS_SUBSIDY_BUDGET_PERCENT` | 12,500 (125%) | Per-witness pool budget boost (`config.hpp:409`) |
| `HIVE_WITNESS_SUBSIDY_DECAY_PERCENT` | 210,000 (21×100%) | Witness pool decays once per round (`config.hpp:414`) |
| `HIVE_DEFAULT_ACCOUNT_SUBSIDY_DECAY` | 347,321 | ≈ 5-day halflife (`config.hpp:417`) |
| `HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET` | 797 | ≈ 0.5 accounts/block (`config.hpp:419`) |
| `HIVE_DECAY_BACKSTOP_PERCENT` | 9,000 (90%) | `config.hpp:420` |

### Resource Dynamics (RD) Parameter Bounds

Used to validate witness-settable resource-pool dynamics (account subsidies; also RC pool shapes).

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_RD_MIN_DECAY_BITS` / `HIVE_RD_MAX_DECAY_BITS` | 6 / 32 | `config.hpp:393-394` |
| `HIVE_RD_DECAY_DENOM_SHIFT` | 36 | `config.hpp:395` |
| `HIVE_RD_MAX_POOL_BITS` | 64 | `config.hpp:396` |
| `HIVE_RD_MAX_BUDGET` | min(2^34−1, 2^28−1, INT32_MAX) = 2^28−1 | Composite of `HIVE_RD_MAX_BUDGET_1/2/3` (`config.hpp:397-400`) |
| `HIVE_RD_MIN_DECAY` | 64 | `1 << 6` (`config.hpp:401`) |
| `HIVE_RD_MIN_BUDGET` | 1 | `config.hpp:402` |
| `HIVE_RD_MAX_DECAY` | 0xFFFFFFFF | `config.hpp:403` |

### Size Limits

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MAX_TRANSACTION_SIZE` | 65,536 | 64 KB |
| `HIVE_MIN_TRANSACTION_SIZE_LIMIT` | 1,024 | 1 KB |
| `HIVE_MAX_BLOCK_SIZE` | 2,097,152 | 2 MB hard maximum |
| `HIVE_MIN_BLOCK_SIZE_LIMIT` | 65,536 | = `MAX_TRANSACTION_SIZE` |
| `HIVE_MIN_BLOCK_SIZE` | 115 | Bytes — minimum valid block |
| `HIVE_MAX_MEMO_SIZE` | 2,048 | Characters |
| `HIVE_MIN_PERMLINK_LENGTH` | 0 | `config.hpp:351` |
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
| `HIVE_OWNER_UPDATE_LIMIT` | 60 minutes | 6 seconds (default; configurable) |
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
| `HIVE_CUSTOM_OP_BLOCK_LIMIT` | 5 | Max custom ops per account per block |

### Comment Limits

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_MAX_COMMENT_DEPTH_PRE_HF17` | 6 | Very shallow comment threads |
| `HIVE_MAX_COMMENT_DEPTH` | 65,535 | 0xFFFF — effectively unlimited |
| `HIVE_SOFT_MAX_COMMENT_DEPTH` | 255 | Soft limit enforced differently |
| `HIVE_MAX_COMMENT_BENEFICIARIES` | 8 | Max beneficiary routes per post |
| `HIVE_BENEFICIARY_LIMIT` | 128 | Extended beneficiary limit |
| `HIVE_COMMENT_TITLE_LIMIT` | 256 | Characters |
| `HIVE_POST_REWARD_FUND_NAME` | `"post"` | Reward fund object name (`config.hpp:296`) |

### Resource Credits (RC System)

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_RC_REGEN_TIME` | 432,000 | 5 days (= `VOTING_MANA_REGENERATION_SECONDS`) |
| `HIVE_RC_BUCKET_TIME_LENGTH` | 3,600 | 1 hour |
| `HIVE_RC_WINDOW_BUCKET_COUNT` | 24 | 24 hours of buckets |
| `HIVE_RC_STATS_REPORT_FREQUENCY` | 28,800 | 1 report per day |
| `HIVE_RC_HISTORICAL_ACCOUNT_CREATION_ADJUSTMENT` | 2,020,748,973 | 2020.748973 VESTS = 1.000 HIVE at HF20 |
| `HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP` | 100 | Max accounts per RC delegation |

The actual per-resource cost parameters (state bytes, execution time, bandwidth shares, pool budgets/decay) are **not** in the protocol layer — they live in `libraries/chain/rc/`: per-operation resource counting in `resource_count.cpp`, state-byte size tables in `resource_sizes.hpp/.cpp`, price curve in `rc_curve.cpp`/`rc_utility.cpp`, persisted in the `rc_resource_param_object` state object (`rc_objects.hpp`). Covered in Part 08.

### Percentage/Basis System

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_100_PERCENT` | 10,000 | Basis of all percentage calculations |
| `HIVE_1_PERCENT` | 100 | = `100_PERCENT/100` |
| `HIVE_1_BASIS_POINT` | 1 | = `100_PERCENT/10000` |

### Special Accounts

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_INIT_MINER_NAME` | `"initminer"` | Genesis block producer |
| `HIVE_MINER_ACCOUNT` | `"miners"` | Represents current witnesses |
| `HIVE_NULL_ACCOUNT` | `"null"` | Black hole — no authority |
| `HIVE_TEMP_ACCOUNT` | `"temp"` | Wildcard authority (anyone); weight_threshold 0 at genesis |
| `OBSOLETE_TREASURY_ACCOUNT` | `"steem.dao"` | Old treasury |
| `NEW_HIVE_TREASURY_ACCOUNT` | `"hive.fund"` | Current treasury (since HF24) |
| `HIVE_PROXY_TO_SELF_ACCOUNT` | `""` | Empty string = vote directly |
| `HIVE_ROOT_POST_PARENT` | `account_name_type()` | Canonical root-post parent (`config.hpp:451`) |
| `"steem"` | — | Created at genesis as a system account with hardcoded key `STM65wH1...` (`database_init.cpp:270-291`, `misc_utilities.hpp:11`); historically mined, now official |

### Node Behavior Margins (consensus-adjacent)

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_UP_TO_DATE_MARGIN__FAST_CONFIRM` | 60 s | Head-block recency for fast-confirm txs (`config.hpp:434`) |
| `HIVE_UP_TO_DATE_MARGIN__BLOCK_STATS` | 20 s | `config.hpp:435` |
| `HIVE_UP_TO_DATE_MARGIN__PENDING_TXS` | 20 s | `config.hpp:436` |

### Miscellaneous

| Constant | Value | Notes |
|----------|-------|-------|
| `HIVE_ADDRESS_PREFIX` | `"STM"` | Public key prefix (kept from Steem) |
| `HIVE_MAX_UNDO_HISTORY` | 10,000 | Undo stack depth |
| `HIVE_MAX_LIMIT_ORDER_EXPIRATION` | 2,419,200 | 28 days |
| `HIVE_BLOCK_GENERATION_POSTPONED_TX_LIMIT` | 5 | Max postponed transactions per block |
| `HIVE_PENDING_TRANSACTION_EXECUTION_LIMIT` | 200ms | Time budget for pending txs |
| `HIVE_GLOBAL_REMOVE_THRESHOLD` | 200 | **20 on testnet** (`config.hpp:97/178`) |
| `HIVE_BLOCKCHAIN_PRECISION` | 1,000 | 10^3 — matches HBD precision |

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
Bits [0..3]:   precision (decimals, 0-12; HIVE_ASSET_MAX_DECIMALS = 12)
Bit  [4]:      control bit (1 for SMT tokens, 0 for legacy)
Bit  [5]:      vesting flag (1 = vesting variant of SMT)
Bits [6..31]:  NAI data digits
```

**For native assets:** The NAI data digits are `SMT_MAX_NAI + HIVE_NAI_X` where `SMT_MAX_NAI = 99999999` and `HIVE_NAI_X` is 1 (HBD), 2 (HIVE), or 3 (VESTS). The control bit is 0 for native assets.

**For SMT tokens:** NAI data ranges from `SMT_MIN_NAI (1)` to `SMT_MAX_NAI (99999999)`, with the control bit set to 1; generated NAIs are restricted to the non-reserved range starting at `SMT_MIN_NON_RESERVED_NAI = 10,000,000` (`asset_symbol.hpp:14`), keeping low values (including the native 1-3) reserved. A Damm checksum digit is appended for the string representation (`@@NNNNNNNNNC`). NAI pool: `SMT_MAX_NAI_POOL_COUNT = 10` candidates, `SMT_MAX_NAI_GENERATION_TRIES = 100` (`asset_symbol.hpp:17-18`).

**Spaces:**
- `legacy_space` (1): HIVE, HBD, VESTS — the three hardcoded native assets
- `smt_nai_space` (2): All other assets (SMT tokens)

### Serialization

Two serialization modes exist (`serialization_type: legacy, hf26`, `misc_utilities.hpp:23`):
- **Legacy format**: 8 bytes — a `uint64_t` whose low byte is the precision and remaining bytes are the ASCII symbol (`XXX_SYMBOL_SER = uint64_t(precision) | (SYMBOL_U64 << 8)`, `asset_symbol.hpp:51-53`). HIVE serializes as `STEEM`, HBD as `SBD` (testnet: `TESTS`/`TBD`).
- **NAI format (hf26)**: 4 bytes — the raw `asset_num` uint32.

The `pack`/`unpack` functions detect the format during deserialization by matching against known legacy byte patterns (`asset_symbol.hpp:157-216`). **Defaults:** binary pack (blocks, block_log) = `legacy` (`misc_utilities.hpp:32`); API-facing transaction serialization = `hf26` (`misc_utilities.hpp:31`). The thread-local `serialization_mode_controller` with RAII `pack_guard`/`mode_guard` switches modes per-context.

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
| `account_name_type` | `fixed_string<16>` | Account name — max 16 chars, stored inline (`types.hpp:70`) |
| `share_type` | `safe<int64_t>` | Asset amounts with overflow checking (`types.hpp:76`) |
| `ushare_type` | `safe<uint64_t>` | Unsigned variant |
| `weight_type` | `uint16_t` | Authority weights |
| `chain_id_type` | `fc::sha256` | 256-bit chain identifier |
| `block_id_type` | `fc::ripemd160` | 160-bit container — holds truncated SHA-224, *not* a RIPEMD hash (see Block Structure) |
| `transaction_id_type` | `fc::ripemd160` | 160-bit container — holds truncated SHA-256 |
| `checksum_type` | `fc::ripemd160` | Generic 160-bit checksum |
| `digest_type` | `fc::sha256` | 256-bit digest (for signing) |
| `signature_type` | `fc::ecc::compact_signature` | ECDSA compact signature (65 bytes) |
| `private_key_type` | `fc::ecc::private_key` | ECDSA private key |
| `public_key_type` | custom struct wrapping `fc::ecc::public_key_data` | With base58 encoding (`types.hpp:83-103`) |
| `custom_id_type` | `fixed_string<32>` | Custom operation ID string |
| `contribution_id_type` | `uint32_t` | For DHF/proposal contributions |

### fixed_string

`fixed_string<N>` is a stack-allocated, endian-reversible string with a maximum of `N` bytes. Used for `account_name_type` (16 bytes) and `custom_id_type` (32 bytes). Internally uses `fc::uint128` (for 16) or `erpair<uint64_t, uint64_t>` for storage.

### public_key_type

Custom struct wrapping `fc::ecc::public_key_data` (33 bytes — compressed EC point). Serializes to/from base58 strings with the `STM` prefix and a 4-byte RIPEMD-160 checksum. Also supports extended key types (`extended_public_key_type`, `extended_private_key_type`) for HD wallet derivation.

### Password-Based Key Derivation

`collect_potential_keys()` (`transaction_util.cpp:379-408`) documents the canonical Hive key derivation: for a candidate password string, role keys are derived as `private_key = regenerate(sha256(account_name + role + password))` for roles `owner`, `active`, `posting`, `memo`. The same helper also accepts raw WIF and extended private keys.

### Extensions Types

- `future_extensions` = `static_variant<void_t>` — placeholder for future fields (`base.hpp:31-35`)
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

Additionally, `witness` authority (the witness signing key) is tracked separately for block signing and witness-key-required operations.

### Weight/Threshold System

- Each key or account in an authority has a `weight_type` (`uint16_t`) weight
- The authority has a `weight_threshold` (`uint32_t`)
- To satisfy an authority, the sum of weights of provided keys/accounts must be ≥ threshold
- Example: threshold=2, key_A weight=1, key_B weight=1 -> both keys needed (2-of-2)
- Example: threshold=1, key_A weight=1, key_B weight=1 -> either key works (1-of-2)
- `is_impossible()` returns true when total available weights < threshold

### Verification Algorithm (`transaction_util.cpp`, `sign_state.hpp`)

Collection: `transaction::get_required_authorities()` (`transaction.cpp:90-98`) folds every operation's `get_required_{active,owner,posting,witness}_authorities()` / `get_required_authorities()` (declared per-operation; no-op defaults in `base_operation`, `base.hpp:13-23`) into a `required_authorities_type`.

Verification: `verify_authority()` (`transaction_util.cpp:18-192`) walks the requirements against a `sign_state` seeded with the public keys recovered from the transaction's signatures. `sign_state::check_authority_impl()` (`sign_state.hpp:167+`) accumulates key weights, recursing into `account_auths` up to `max_recursion_depth` and counting membership/account limits.

Semantics (pre-HF28, i.e., current mainnet):
- **Posting isolation**: operations requiring posting authority cannot share a transaction with operations requiring active/owner/witness/other authority (`transaction_util.cpp:59-74`).
- **Role upgrade**: posting requirement satisfied by posting, active, or owner authority (`transaction_util.cpp:101-104`); active requirement satisfied by active or owner (`transaction_util.cpp:146-158`); owner requirement only by owner (`transaction_util.cpp:162-166`).
- **Witness requirement**: satisfied iff the transaction is signed with the witness's current signing key (`transaction_util.cpp:168-182`).
- **No redundant signatures**: leftover signatures not needed by any requirement throw `tx_irrelevant_sig` (`transaction_util.cpp:184-188`).

At HF28 (`database.cpp:2612-2613`): `HIVE_HARDFORK_1_28_ALLOW_STRICT_AND_MIXED_AUTHORITIES` removes the posting-isolation rule **and** the role-upgrade paths (strict per-role matching), and `HIVE_HARDFORK_1_28_ALLOW_REDUNDANT_SIGNATURES` stops rejecting unused signatures.

Limits passed by the chain: `HIVE_MAX_SIG_CHECK_DEPTH = 2`, and — only for blocks after HF20 — `HIVE_MAX_AUTHORITY_MEMBERSHIP = 40` and `HIVE_MAX_SIG_CHECK_ACCOUNTS = 125` (passed as 0/unlimited pre-HF20, `database.cpp:2620-2622`).

### Multi-sig

Multi-signature is built into the authority model:
- An authority can have up to **40 members** (`HIVE_MAX_AUTHORITY_MEMBERSHIP`) — combination of keys and accounts
- Account auths allow delegation: account B's authority can be part of account A's authority
- Max recursion depth for account authority resolution: **2** (`HIVE_MAX_SIG_CHECK_DEPTH`)
- Max accounts checked during signature verification: **125** (`HIVE_MAX_SIG_CHECK_ACCOUNTS`)
- The wallet-side helper `signing_keys_collector` (`transaction_util.cpp:410-553`) walks account_auths breadth-first per role (switching to the active role below the first level for owner/active chains) to gather all candidate signing keys

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

The per-operation mapping (which of the 50 regular operations requires which level) is cataloged in Part 02.

---

## Block Structure

### Block Header (`block_header.hpp`)

```cpp
struct block_header {
  block_id_type                previous;              // ID of previous block (encodes height)
  fc::time_point_sec           timestamp;             // Block production time
  string                       witness;               // Witness account name
  checksum_type                transaction_merkle_root; // Merkle root of transaction digests
  block_header_extensions_type extensions;             // Version reporting, HF votes
};
// block_num() == num_from_id(previous) + 1     (block_header.hpp:19)
```

### Signed Block Header / Full Signed Block

```cpp
struct signed_block_header : public block_header {
  signature_type witness_signature;  // ECDSA compact signature (65 bytes)
};
struct signed_block : public signed_block_header {
  vector<signed_transaction> transactions;
};
```

### Block ID Computation (chain layer — `full_block.cpp:305-316`)

```cpp
// 1. SHA-224 over the serialized signed_block_header (header INCLUDING witness_signature)
fc::sha224 block_hash = fc::sha224::hash(signed_block_header_begin, signed_block_header_size);
// 2. overwrite first 4 bytes with big-endian block number
block_hash._hash[0] = fc::endian_reverse_u32(block_num);
// 3. truncate to 20 bytes (discard last 8 of the 28-byte SHA-224)
memcpy(block_id._hash, block_hash._hash, 20);
```

Properties:
- The first 4 bytes of every block ID are the big-endian block number — `num_from_id()` (`block.cpp:13-16`) just reads them back. IDs are therefore chronologically sortable.
- The hash covers the **signed** header, so the same header signed twice (different signature nonce) yields different block IDs.
- Serialization uses the ambient pack mode (legacy by default).
- The protocol-layer `legacy_digest()` and `legacy_calculate_merkle_root()` are unit-test conveniences; production paths are `full_block_type::get_digest()` / `compute_merkle_root()` (`block.cpp:18`, `block_header.hpp:17`).

### Witness Signature Scheme

During block production (`full_block.cpp:102-156`):
1. The header (without signature) is serialized; `digest = sha256(serialized block_header bytes)` (`full_block.cpp:144`; layout comment at `full_block.cpp:356-364`).
2. The witness signs: `witness_signature = signer->sign_compact(digest)` (`full_block.cpp:149`) using its current signing key (the one registered in its `witness_object`).
3. Verification recovers the public key from the compact signature: `signee() = fc::ecc::public_key(witness_signature, digest)` (`full_block.cpp:336-339`) and the chain checks it equals the scheduled witness's signing key.

**No chain ID enters the block digest** — block replay protection across chains comes from the `previous` ID chain, not the signature domain.

### Block Header Extensions

The `block_header_extensions` is a `static_variant` (`block_header.hpp:7-11`) supporting:
1. `void_t` — empty/no extension
2. `version` — witness reports its software version
3. `hardfork_version_vote` — witness votes for next hardfork (includes HF version + activation time)

These are stored in a `flat_set` so they're unique and ordered.

### Merkle Root

Computed via pairwise hashing of transaction `merkle_digest()`s (legacy pack), iteratively halving until one root remains; an odd element is carried up unchanged each round; empty block ⇒ zero checksum (`block.cpp:19-46`; production version `full_block.cpp` `compute_merkle_root`).

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
struct signed_transaction : public transaction {
  vector<signature_type> signatures;  // ECDSA compact signatures
};
```

### TaPoS (Transaction as Proof of Stake)

TaPoS prevents transaction replay and proves the signer had visibility of recent chain state (`transaction.cpp:84-88`):

```cpp
void transaction::set_reference_block(const block_id_type& reference_block) {
  ref_block_num = fc::endian_reverse_u32(reference_block._hash[0]);    // block number (16-bit truncation)
  ref_block_prefix = reference_block._hash[1];                          // next 4 bytes of block ID
}
```

- `ref_block_num`: Lower 16 bits of a recent block number (note: works because block IDs embed the block number in `_hash[0]` — see Block ID Computation)
- `ref_block_prefix`: Bytes 4-7 of that block's ID
- The chain verifies these match a block within the recent undo history

### Expiration

- Transactions must include an expiration timestamp
- Maximum expiration: `HIVE_MAX_TIME_UNTIL_EXPIRATION` = **3,600 seconds** (1 hour) from head block time
- Expired transactions are rejected; not-yet-valid transactions are also rejected

### Transaction ID Computation

Transaction ID = first 20 bytes of SHA-256 over the serialized transaction (without signatures). Protocol form `transaction.cpp:58-64`; production form hashes the actual wire bytes (`full_transaction.cpp:93-108`).

### Signature Digest and Chain ID Selection

Protocol form (`transaction.cpp:29-38`): `sig_digest = sha256(chain_id || pack(transaction))` under an explicit pack guard. Production form (`full_transaction.cpp:110-116`) hashes `chain_id ||` **the exact bytes the transaction arrived in** — no re-serialization, so a transaction signed under either legacy or HF26 serialization validates as long as its signatures match its own wire bytes (`is_legacy_pack()` detection at `full_transaction.cpp:263-284`).

Chain ID selection is time-dependent (`full_transaction.cpp:453-493`): blocks with timestamp ≤ `HIVE_HARDFORK_1_24_ACTUAL_TIME = 1602703884` validate with `OLD_CHAIN_ID` (empty sha256 — Steem); later blocks and all new transactions use `HIVE_CHAIN_ID` ("beeab0de..."). Duplicate signatures throw `tx_duplicate_sig` during key recovery (`full_transaction.cpp:145-148`).

### Transaction Validation

Basic validation ensures (`transaction.cpp:40-56`):
- At least one operation exists
- Each operation passes its own `validate()` method

Authority verification is separate (see Authority Model) and checks that recovered signature keys satisfy all required authorities for all operations.

---

## Version and Hardfork System

### Version (`version.hpp`)

Triple encoding: `major.hardfork.release` packed in `uint32_t`:
- Bits [24-31]: major version
- Bits [16-23]: hardfork version (minor)
- Bits [0-15]: release version

Current: `version(1, 28, 7)` -> `0x011C0007`. Major versions 0 and 1 compare equal (`version.hpp:48-75`, see Discovery 5).

### Hardfork Version

Inherits from `version` but masks off the release bits:
```cpp
hardfork_version(version v) { v_num = v.v_num & 0xFFFF0000; }
```

### Hardfork History (Block Numbers, `hardfork_block.hpp`)

| Hardfork | Block | Notes |
|----------|-------|-------|
| HF 0.1 | 905,693 | Vesting share split ×1,000,000 |
| HF 0.2 | 934,585 | |
| HF 0.3 | 953,363 | |
| HF 0.4 | 1,041,497 | |
| HF 0.5 | 1,934,236 | |
| HF 0.6 | 2,790,882 | |
| HF 0.7 | 2,889,019 | |
| HF 0.8 | 2,889,959 | |
| HF 0.9 | 3,202,773 | 151 compromised accounts locked to recovery key |
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
| HF 0.21 | 35,921,786 | Downvote mana overflow until block 35,922,615 (`HIVE_HF_21_STALL_BLOCK`) |
| HF 0.22 | 35,974,326 | |
| HF 0.23 | 41,818,752 | (Hive fork from Steem) |
| HF 1.24 | 47,797,680 | First "1.x"; scheduled 2020-10-06, actually activated 1602703884 = 2020-10-14 (`hardfork.d/1_24.hf:22-27`) |
| HF 1.25 | 55,235,767 | |
| HF 1.26 | 68,676,505 | |
| HF 1.27 | 69,050,084 | |
| HF 1.28 | 100,000,000 (code; actual activation: 101,319,928) | 2025-11-19. Strict/mixed authority + redundant signature changes |

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

### Genesis State (chain layer — `database_init.cpp:177-307`)

`init_genesis()` creates: `miners`, `null`, `temp` (threshold 0 = wildcard), `initminer` (with witness object, schedule `miner`), and the `steem` system account (officially created at genesis since it had been used as a system account before being mined; key `STM65wH1...`, `database_init.cpp:270-291`). Testnet/iceberg builds additionally create both treasury accounts at genesis (`database_init.cpp:213-230`). The dgpo starts with `current_witness = initminer` and all supplies zero on mainnet.

---

## Answers to Research Questions

### Configuration Constants

**Q: What is the block interval?**
A: 3 seconds (`HIVE_BLOCK_INTERVAL = 3`). Source: `config.hpp:56`

**Q: What is the maximum transaction size?**
A: 65,536 bytes / 64 KB (`HIVE_MAX_TRANSACTION_SIZE = 1024*64`). Source: `config.hpp:364`

**Q: What is the maximum block size?**
A: 2,097,152 bytes / 2 MB (`HIVE_MAX_BLOCK_SIZE = 2*1024*1024`). Source: `config.hpp:366`. Witness-voted `maximum_block_size` in dgpo cannot exceed it.

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
A: Default 10% APR. Witnesses set the rate (median of witness properties). Compounds monthly (every 30 days). Source: `config.hpp:255, 363`

**Q: What are the DHF constants?**
A: 10 HBD creation fee, 80-char subject, maintenance every hour, 1 HBD fee increase every 60 days. Source: `config.hpp:462-469`

**Q: What constants differ between mainnet and testnet?**
A: Key differences (testnet defaults from `config.hpp:64-126` and `testnet_blockchain_configuration.hpp:27-88`):

| Constant | Mainnet | Testnet default |
|----------|---------|-----------------|
| Cashout window | 7 days | 1 hour (configurable) |
| Second cashout window | 30 days | 3 days |
| Max cashout window | 14 days | 1 day |
| Upvote lockout | 12 hours | 5 minutes |
| Early/mid voting | 24 h / 48 h | 10 min / 20 min |
| Owner recovery period | 30 days | 60 seconds |
| Recovery request expiration | 1 day | 12 seconds |
| Owner update limit | 60 min | 6 seconds |
| Delayed voting | 30 days / 1 day steps | 1 day / total÷30 steps |
| Governance vote expiration | 365 days | 5 days |
| Feed interval | 1,200 blocks | 20 blocks |
| Max feed age | 7 days | 10,080 s (60·24·7) |
| Account creation fee min | 1 (0.001 HIVE) | 0 |
| `HIVE_GLOBAL_REMOVE_THRESHOLD` | 200 | 20 |
| Start miner voting block | 864,000 | 30 |
| Initial supply | 0 HIVE / 0 HBD | 243M HIVE / 7M HBD |
| Initial vesting price | n/a (1:1 via dgpo default) | `VEST_price(1800, 1000)` pre-HF1-split |
| Chain ID | beeab0de... | sha256("testnet") (CLI-overridable) |
| HF times / initminer key / HF9 key | fixed | all configurable via `alternate-chain-spec` |

**Q: Any suspicious constants?**
A: See Discrepancies — misleading `HIVE_BLOCKCHAIN_PRECISION` comment, misleading `HIVE_ADDRESS_PREFIX` name, *wrong* mainnet genesis-time comments, HF26 start==stop, and the converter-only 41-member authority limit.

### Asset System

**Q: Internal representations?**
A: All three use `asset_num` (uint32_t) with NAI encoding. HIVE and HBD have precision 3 (3 decimal places), VESTS has precision 6.

**Q: NAI system?**
A: Covered in detail above. Key: `@@NNNNNNNNNC` string format, Damm checksum, 32-bit internal encoding, reserved band below 10,000,000.

**Q: Asset validation?**
A: Symbol type validated in `asset_symbol_type::validate()` (NAI range + control bit, `asset.cpp:261-283`). Amount uses `safe<int64_t>` for overflow protection. No explicit negative amount prevention at the protocol type level — that's enforced per-operation in validation.

### Type System

**Q: `account_name_type` constraints?**
A: `fixed_string<16>` — max 16 characters. RFC 1035 DNS-like rules: lowercase, dot-separated labels, each ≥ 3 chars, starts with letter, ends with letter/digit. Min length 3.

**Q: `share_type` and large numbers?**
A: `safe<int64_t>` — wraps `int64_t` with overflow checking. Throws on overflow/underflow. Max value: `INT64_MAX`. For calculations requiring larger numbers, `uint128_t` and `uint256_t` are available.

**Q: How are public keys represented?**
A: 33-byte compressed secp256k1 points (`fc::ecc::public_key_data`) wrapped in `public_key_type`; base58 with `STM` prefix + 4-byte RIPEMD-160 checksum (`types.hpp:83-103`).

### Authority Model

**Q: What operations can each authority level perform?**
A: Declared per-operation via `get_required_*_authorities()`; full catalog in Part 02. The protocol-layer *enforcement* (role upgrade, posting isolation, HF28 strict/mixed switch) is documented in the Authority Model section above.

**Q: How does multi-sig work at the protocol level?**
A: Weighted threshold over up to 40 keys/accounts, recursive account authorities to depth 2, ≤125 accounts touched per verification; weight accumulation in `sign_state::check_authority_impl` (`sign_state.hpp:167+`).

### Block Structure

**Q: How are block IDs computed?**
A: **Answered** (was an open question): SHA-224 of the serialized signed block header, first 4 bytes overwritten with the big-endian block number, truncated to 20 bytes — `full_block_type::construct_block_id()` (`full_block.cpp:305-316`). The protocol library only carries the unit-test helper `legacy_digest()` and `num_from_id()`.

**Q: What is the witness signature scheme?**
A: ECDSA compact signature (`sign_compact`) over the SHA-256 digest of the serialized *unsigned* block header; verification by public-key recovery (`signee`, `full_block.cpp:336-339`) against the scheduled witness's signing key. No chain ID in the digest.

### Transaction Structure

All sub-questions answered in the Transaction Structure section above (fields, TaPoS, expiration, IDs, extensions; plus the dual-serialization and chain-id-switching behavior of signature validation).

---

## Code References

| Component | File | Line(s) | Purpose |
|-----------|------|---------|---------|
| Block interval constant | `config.hpp` | 56 | `HIVE_BLOCK_INTERVAL = 3` |
| All timing constants | `config.hpp` | 56-207 | Block, cashout, recovery, feed timings |
| Genesis & mining times | `config.hpp` | 150-154 | Values correct, comments wrong (see Discrepancy 6) |
| All economic constants | `config.hpp` | 215-346 | Inflation, rewards, HBD limits |
| Legacy APR/PoW/liquidity constants | `config.hpp` | 282-335 | Pre-HF16 economics, Equihash 140/6 |
| All size limits | `config.hpp` | 348-399 | Transaction, block, name, URL sizes and miscellaneous limits |
| Authority membership (converter quirk) | `config.hpp` | 374-378 | 40 mainnet, 41 mirrornet converter |
| Witness virtual schedule laps | `config.hpp` | 383-384 | 2^64−1 / 2^128−1; algorithm in `witness_schedule.cpp` |
| Resource dynamics bounds | `config.hpp` | 393-403 | `HIVE_RD_*` budget/decay bounds |
| Account subsidy constants | `config.hpp` | 405-420 | HF20 subsidy budget/decay |
| Special accounts | `config.hpp` | 441-458 | null, temp, miners, proxy-to-self, root-post-parent, treasury pair (resolved via `database::get_treasury_name()`) |
| DHF constants | `config.hpp` | 460-469 | Proposal system |
| RC constants | `config.hpp` | 479-494 | Resource credits (timing only; costs in `libraries/chain/rc/`) |
| get_config export warning | `config.hpp` | 12-14 | Every constant exposed via `database_api.get_config` |
| HF9 recovery key | `config.hpp` | 18 | + account list `hardfork.d/0_9.hf:15-172`, applied `database_hardfork.cpp:213-226` |
| NAI bit layout | `asset_symbol.hpp` | 9-32 | Precision bits, shift, NAI encoding, reserved space |
| Asset precisions | `asset_symbol.hpp` | 20-22 | HBD=3, HIVE=3, VESTS=6 |
| Legacy symbol bytes | `asset_symbol.hpp` | 36-53 | STEEM/SBD/TESTS/TBD/HIVE/HBD/VESTS |
| Serialization modes | `asset_symbol.hpp` | 157-216 | Legacy vs NAI pack/unpack |
| Pack mode controller | `misc_utilities.hpp` | 23-68 | legacy/hf26 enum, defaults, pack_guard |
| `asset` struct | `asset.hpp` | 21-96 | Amount + symbol with operator overloads |
| `price` struct | `asset.hpp` | 139-186 | Base/quote pair |
| `tiny_asset` / `tiny_price` | `asset.hpp` | 218-322 | Typed thin wrappers |
| NAI Damm checksum | `asset.cpp` | 80-126 | 8-digit Damm algorithm |
| Asset symbol validation | `asset.cpp` | 261-283 | NAI range + control bit checks |
| Price multiplication | `asset.cpp` | 310-325 | uint128 cross-multiplication |
| Core type aliases | `types.hpp` | 66-81 | All fundamental typedefs |
| `public_key_type` | `types.hpp` | 83-103 | Key data + base58 encoding |
| Authority struct | `authority.hpp` | 7-55 | Threshold + key/account maps |
| Account name validation | `authority.cpp` | 58-122 | RFC 1035 with Hive rules |
| Authority verification | `transaction_util.cpp` | 18-192 | Posting isolation, role upgrade, HF28 flags |
| Chain verify_authority call | `database.cpp` | 2598-2626 | HF28 flags, HF20 limits |
| sign_state recursion | `sign_state.hpp` | 167+ | Weight accumulation, depth/membership limits |
| Password key derivation | `transaction_util.cpp` | 379-408 | sha256(account+role+password) |
| Signing key collector | `transaction_util.cpp` | 410-553 | Wallet-side authority walk |
| Block header | `block_header.hpp` | 15-31 | previous, timestamp, witness, merkle root, block_num() |
| Block number extraction | `block.cpp` | 13-16 | `endian_reverse_u32(id._hash[0])` |
| Protocol merkle root (test-only) | `block.cpp` | 18-46 | Pairwise hashing; production in full_block |
| **Block ID construction** | `full_block.cpp` | 305-316 | SHA-224(signed header) + block-num splice, 20 bytes |
| Block digest & signing | `full_block.cpp` | 102-156 | SHA-256(unsigned header), sign_compact |
| Block digest layout comment | `full_block.cpp` | 352-367 | Authoritative description of digest vs ID |
| Witness sig recovery | `full_block.cpp` | 336-339 | `signee()` public-key recovery |
| Transaction struct | `transaction.hpp` | 12-53 | ref_block, expiration, operations |
| TaPoS encoding | `transaction.cpp` | 84-88 | Block number + prefix extraction |
| Tx ID computation | `transaction.cpp` | 58-64 | SHA-256 truncated to 20 bytes |
| Signature digest (protocol) | `transaction.cpp` | 29-38 | chain_id + transaction -> SHA-256 |
| Signature digest (production) | `full_transaction.cpp` | 110-116 | chain_id + actual wire bytes |
| Chain-ID validation rules | `full_transaction.cpp` | 450-493 | OLD_CHAIN_ID pre-HF24-actual-time, bip_0062 note |
| Legacy pack detection | `full_transaction.cpp` | 263-284 | Byte-compare against re-pack |
| Duplicate signature check | `full_transaction.cpp` | 145-148 | `tx_duplicate_sig` |
| Transaction validation | `transaction.cpp` | 40-56 | operations.size() > 0, per-op validate |
| Required authorities fold | `transaction.cpp` | 90-98 | Per-op authority collection |
| `base_operation` | `base.hpp` | 13-29 | Required authorities interface |
| Version struct | `version.hpp` | 15-77 | Major.HF.release in uint32; 0≡1 hack at 48-75 |
| Hardfork version | `version.hpp` | 79-102 | Masks release bits |
| HF version vote | `version.hpp` | 104-111 | HF version + activation time |
| Hardfork blocks | `hardfork_block.hpp` | 3-30 | All 28 HF activation blocks |
| HF count | `hardfork.d/0-preamble.hf` | 16-19 | `HIVE_NUM_HARDFORKS = 28` |
| HF21 stall block | `hardfork.d/0_21.hf` | 18-22 | 35,922,615 mainnet; testnet-configurable |
| HF21 overflow replay | `manabar.hpp` | 120-135 | int64 overflow reproduced ≤ stall block |
| HF24 times | `hardfork.d/1_24.hf` | 17-27 | Scheduled vs ACTUAL (1602703884) |
| Chain IDs | `config.hpp` | 136-143 | Mainnet "beeab0de...", mirrornet "4200...", testnet |
| HBD interest calc | `hbd_interest.hpp` | 8-23 | Balance-seconds / year * rate |
| Collateral estimation | `hive_collateral.hpp` | 8-26 | `estimate_hive_collateral()` formula |
| Genesis init | `database_init.cpp` | 177-307 | System accounts, initminer, "steem", dgpo |
| Genesis vesting price | `chain/.../detail/state/global_property_object.hpp` | 87-92 | `VEST_price(1000000,1000)` on empty pools |
| HF1 vesting split | `database_hardfork.cpp` / `database_comment.cpp` | 189-191 / 612-667 | ×1,000,000 across all VESTS state |
| Testnet overrides | `testnet_blockchain_configuration.hpp` | 27-285 | All configurable defaults |
| Alternate chain spec loader | `chain_plugin.cpp` | ~1704-1764 | JSON overrides incl. `hf_21_stall_block` |
| RC cost parameters (pointer) | `libraries/chain/rc/` | — | `resource_count.cpp`, `resource_sizes.*`, `rc_curve.cpp`, `rc_objects.hpp` (Part 08) |
| Witness scheduling (pointer) | `libraries/chain/witness_schedule.cpp` | — | Virtual-time algorithm (Part 06) |

---

## Discrepancies and Potential Issues

### 1. `HIVE_BLOCKCHAIN_PRECISION` Naming
- **File**: `config.hpp:371`
- **Issue**: Comment says "actually HBD precision" but the value (1000) is the same 10^3 precision used for both HIVE and HBD. The comment is misleading — it should say "HBD/HIVE precision" or better yet, use `HIVE_PRECISION_HIVE` directly.

### 2. HF 0.17 and 0.18 Activation Gap
- **File**: `hardfork_block.hpp:19-20`
- **Issue**: HF17 at block 10,629,455 and HF18 at block 10,629,486 — only 31 blocks apart (~93 seconds). This is effectively simultaneous and suggests HF18 was a hotfix or companion change to HF17. (Historical reason not derivable from this code; would need Steem-era release notes.)

### 3. Public Key Prefix Still "STM" (Steem)
- **File**: `config.hpp:212`
- **Issue**: `HIVE_ADDRESS_PREFIX = "STM"` — the old Steem prefix is retained for backward compatibility. This is intentional (changing it would break all existing keys) but worth noting for documentation. Note: the constant name is misleading — "STM" prefixes public keys (e.g., `STM7abc...`), not addresses. On Hive, an address is an account name (username).

### 4. `HIVE_INIT_SUPPLY` is 0 on Mainnet
- **File**: `config.hpp:49-50`
- **Issue**: Mainnet initial HIVE and HBD supply are both 0, while testnet defaults to 243M HIVE and 7M HBD. The mainnet genesis block relied on the mining mechanism to create initial supply. This is correct behavior but often surprising to newcomers.

### 5. `HF26 START == STOP` for HBD Printing
- **File**: `config.hpp:343-344`
- **Issue**: `HIVE_HBD_START_PERCENT_HF26 = HIVE_HBD_STOP_PERCENT_HF26 = 2000` (20%). When start equals stop, there is no gradual reduction — it's a binary on/off at exactly 20% market cap. This is likely intentional but contrasts with all previous hardforks which had a gradual reduction range.

### 6. Mainnet Genesis/Mining Time Comments Are Wrong
- **File**: `config.hpp:152, 154`
- **Issue**: `HIVE_GENESIS_TIME = 1458835200` is commented "Friday, January 1, 2016 12:00:00 AM UTC" but the value is **Thursday, 2016-03-24 16:00:00 UTC** (the comment belongs to the *testnet* genesis 1451606400 at `config.hpp:71-72`). `HIVE_MINING_TIME = 1458838800` is commented "March 24, 2016 4:00:00 PM UTC" but the value is **17:00 UTC**. Values are consensus-correct; only the comments mislead.

### 7. Converter Builds Quietly Change a Consensus Limit
- **File**: `config.hpp:374-378`
- **Issue**: `HIVE_MAX_AUTHORITY_MEMBERSHIP` is 41 ("40 + second auth") when `HIVE_CONVERTER_BUILD` is defined. Intentional for mirrornet (the converter appends an extra authority member so it can re-sign history), but it means mirrornet consensus differs from mainnet in this limit.

---

## Open Questions

1. ~~How exactly are block IDs computed?~~ **Resolved** — see Key Discovery 9 (`full_block.cpp:305-316`).

2. ~~What is the exact VEST/HIVE conversion ratio at genesis?~~ **Resolved** — see Key Discovery 10 (1.000000 VESTS per 1.000 HIVE on empty pools; ×10^6 at HF1).

3. ~~What is `hf_21_stall_block` / "iceberg"?~~ **Resolved** — see Key Discovery 11 (HF21 downvote-mana int64 overflow replay window; iceberg = `blockchain_converter` plugin).

4. **Per-operation authority catalog** — the *mechanism* (declaration + verification + HF28 changes) is now documented here; the table of which of the 50 operations requires which level is Part 02 (Operations Catalog).

5. **Exact RC cost parameter values** — protocol layer defines only timing; the cost model (per-op resource counts, size tables, curve parameters, pool budgets) lives in `libraries/chain/rc/` and is covered in Part 08.

6. **Witness scheduling algorithm details** — `HIVE_VIRTUAL_SCHEDULE_LAP_LENGTH(2)` constants are protocol-side (`config.hpp:383-384`); the virtual-time algorithm in `witness_schedule.cpp` is covered in Part 06.

7. **Why was HF18 only 31 blocks after HF17?** Not derivable from this codebase (needs Steem-era release history). Kept as historical curiosity; no consensus impact today.
