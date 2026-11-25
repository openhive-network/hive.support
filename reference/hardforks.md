# Hive Hardfork History Reference

Source: hive-core release 1.28.8. 28 hardforks active on mainnet: HF1-22 pre-fork (inherited from Steem), HF23 Hive genesis (chain-split), HF24-28 Hive-native. The 1.28.8 code also defines HF29, inactive on mainnet (see HF29 below).

Versioning: HF1-23 use major version 0 (0.1-0.23). HF24-28 use major version 1 (1.24-1.28), and HF29 is 1.29. The version bump came at HF24 but the chain split happened at HF23. The `version` comparison has a compatibility branch for comparisons between major versions 0 and 1: `version(0, 23, 0) == version(1, 23, 0)` returns true (Part 01, Key Discovery 5).

Activation: HF1-5 activated by time only (the time-only path applies hardforks up to and including HF5). HF6+ require a 17/21 witness supermajority vote plus time (`database_hardfork.cpp:126-146`). The time tested is the head block's timestamp, not the wall clock. Exception: HF23 was force-activated without witness majority - this is the fork that created Hive. Dates below are each hardfork's `TIME` (HF24: its `ACTUAL_TIME`); blocks are the mainnet activation blocks recorded in `hardfork_block.hpp`, which live activation never reads (Part 09, section Activation Block Reference).

| HF | Block | Date | Key Changes |
|----|-------|------|-------------|
| 1 | 905,693 | 2016-04-25 | Vesting share split (all VESTS x1,000,000); permlink validation |
| 2 | 934,585 | 2016-04-26 | Witness vote retally; max witness votes enforced |
| 3 | 953,363 | 2016-04-27 | Direct witness vote adjustment |
| 4 | 1,041,497 | 2016-04-30 | Virtual schedule time overflow fix |
| 5 | 1,934,236 | 2016-05-31 | **Witness-based hardfork voting** introduced (replaces time-only activation) |
| 6 | 2,790,882 | 2016-06-30 | Reverse auction mechanism; posting intervals (one post per 60 s before HF6; from HF6 the 1.28.8 code applies a root post per 5 min and a reply per 3 s); a vote edit that keeps the same weight is rejected |
| 7 | 2,889,019 | 2016-07-04 | First comment payouts (no cashout before HF7); upvote lockout before payout (1 min, 12 h from HF17; since HF20 no lockout, a vote's rshares scale down over the last 12 h) |
| 8 | 2,889,959 | 2016-07-04 | Vote count retally (1 hour after HF7) |
| 9 | 3,202,773 | 2016-07-14 | Reset the authorities of up to 151 listed compromised accounts (names without an account are skipped) after a security breach |
| 10 | 3,239,649 | 2016-07-15 | Minimum time on the order book for liquidity rewards 1 min -> 30 min |
| 11 | 3,276,913 | 2016-07-17 | An account created by `temp` gets no recovery account (before HF11 every new account got `steem`) |
| 12 | 3,533,567 | 2016-07-26 | **Liquidity rewards removed** permanently; post bandwidth limiting |
| 13 | 4,105,155 | 2016-08-15 | `pow` deprecated (use `pow2`); vote dust threshold |
| 14 | 5,137,542 | 2016-09-20 | `custom_binary` enabled (the 1.28.8 evaluator rejects it unconditionally); `decline_voting_rights` enabled; witness shutdown on missed blocks (until HF20) |
| 15 | 6,547,932 | 2016-11-08 | Posting authority account existence verification |
| **16** | 7,353,249 | 2016-12-06 | **Power down 104 weeks -> 13 weeks**; new inflation model (9.5% decreasing to 0.95%) |
| 17 | 10,629,455 | 2017-03-30 | Reward fund system (since 1.28.8 the fund object exists from genesis and HF17 re-seeds it); **mining disabled** permanently (20 voted + 1 runner witness schedule) |
| 18 | 10,629,486 | 2017-03-30 | Version marker only (31 blocks after HF17, no-op) |
| 19 | 12,988,978 | 2017-06-20 | **Linear rewards**; 10 full votes/day; square root curation curve |
| **20** | 26,256,743 | 2018-09-25 | **Resource Credits system**; `claim_account` op; `account_create_with_delegation` deprecated |
| **21** | 35,921,786 | 2019-08-27 | **DHF/proposal system**; convergent linear rewards; separate downvote pool (25%); 50% curation |
| 22 | 35,974,326 | 2019-08-29 | Downvote mana fix (2 days after HF21); contains HF23 exclusion account list |
| **23** | 41,818,752 | 2020-03-20 | **Steem-to-Hive fork** (forced). At most 328 accounts cleared (332 list entries, 4 duplicates); balances to treasury |
| **24** | 47,797,680 | 2020-10-14 | First Hive-native HF (v1.x). 51 accounts restored; chain ID set; treasury renamed to `hive.fund` |
| **25** | 55,235,767 | 2021-06-30 | **Recurrent transfers**; `collateralized_convert`; governance vote expiration (365d); pure linear rewards |
| **26** | 68,676,505 | 2022-10-11 | Dust votes count; no vote-edit penalty; HBD print-rate thresholds raised to 20%, HBD hard limit to 30%; fast confirmation op |
| 27 | 69,050,084 | 2022-10-24 | Timeshare witness scheduling hotfix (13 days after HF26) |
| **28** | 101,319,928 (since 1.28.8 also the value of the code constant `HIVE_HARDFORK_1_28_BLOCK`, 100,000,000 at 1.28.7; block constants are unused for activation) | 2025-11-19 | Power down fix; **stable votes** (max mana); extended expiration (24h); strict/mixed authorities; DHF HBD excluded from inflation |
| 29 | none on mainnet (`HIVE_HARDFORK_1_29_BLOCK` = 150,000,000 is the converter's threshold for converted chains, not an activation block) | none on mainnet | Defined in 1.28.8 code, inactive on mainnet: five switches, no one-time migration (see HF29 below) |

## Key Hardfork Details

**HF16 - Power Down & Inflation** (2016-12-06): Reduced power down from 104 weekly installments to 13 (2 years to 13 weeks). Introduced the declining inflation model: 9.78% at block 0, narrowing 0.01% every 250k blocks (9.5% from block 7,000,000, about when HF16 activated), floor 0.95% (`protocol/config.hpp:253-255`).

**HF20 — Resource Credits** (2018-09-25): The largest single feature addition. Replaced bandwidth-based rate limiting with the RC system. Every account gets RC proportional to their HP, spent on transactions, regenerating over 5 days. Enabled `claim_account` for discounted account creation.

**HF21 — Economic Improvement Proposal** (2019-08-27): Created the DHF (Decentralized Hive Fund) proposal system funded by 10% of inflation. Changed reward split to 50/50 author/curator. Added separate downvote pool at 25% of upvote mana. Switched to convergent linear reward curve.

**HF23 - The Hive Fork** (2020-03-20): The community fork away from Steemit Inc/Tron. Force-activated without witness majority (unique override). Cleared at most 328 accounts (the list has 332 entries with 4 duplicates) affiliated with Steemit Inc, Tron puppets, and supporters. Their balances moved to the treasury (VESTS converted to HIVE); the HIVE/HBD swept from each account (liquid, savings and reward balances, not the HIVE from converted VESTS) was recorded for potential restoration (`database.cpp:1610-1611`, `:1624-1625`, `:1638-1639`, `:1664`) (Part 09, section The HF23 Clear / HF24 Restore Mechanism).

**HF24 - Hive Identity** (2020-10-14): First major-version-1 hardfork. Set the Hive chain ID (`beeab0de...`). Paid the recorded balances back to the liquid balances of up to 51 listed accounts (names without a record or an account are skipped, `database.cpp:1441-1458`): 30 erroneously cleared and 21 that won airdrop appeal proposals (#104, #111). Renamed treasury from `steem.dao` to `hive.fund`. Enabled `update_proposal` operation.

**HF25 — Recurrent Transfers** (2021-06-30): Enabled recurring scheduled transfers. Added `collateralized_convert` (HIVE to HBD with 2x collateral). Set governance vote expiration to 365 days. Returned to pure linear reward curves, disabled reverse auction.

**HF26 - Governance Improvements** (2022-10-11): Made dust-level votes count as real votes. Removed penalty for editing votes. Raised the HBD print-rate thresholds to 20% (start and stop; 9% and 10% before) and the HBD hard limit, where an artificial price floor kicks in, from 10% to 30% (`protocol/config.hpp:340-345`). Allowed authority updates twice per hour. Solidified old soft forks (custom op size limits enforced on `custom` and `custom_json`; the `1_26.hf` comment also names disabling `custom_binary`, which the 1.28.8 evaluator rejects at every hardfork).

**HF28 - Stability & Authority** (2025-11-19 13:00 UTC, activated at block 101,319,928; since 1.28.8 the `HIVE_HARDFORK_1_28_BLOCK` constant also says 101,319,928 (100,000,000 at 1.28.7), but block constants play no part in activation, which is time + witness supermajority via `process_hardforks()`): Fixes a power-down rounding bug originating from HF1's vesting split. Stable votes use max mana instead of current mana for consistent vote strength. Extended signature expiration up to 24 hours. Allows strict and mixed authorities (owner/active combined with posting in one transaction). Excludes DHF treasury HBD from inflation calculation.

**HF29 - Defined in 1.28.8, Inactive on Mainnet**: `hardfork.d/1_29.hf` defines HF29 (version 1.29) with five switches (`ALLOW_MODIFY_LAST_RECURRENT_TRANSFER`, `FIX_ENFORCEMENT_OF_AUTHORITY_SIZE_ON_RECOVERY_REQUEST`, `FIX_LIMIT_ORDER_ASSETS`, `RC_IS_CONSENSUS`, `VALIDATE_ALL_PROPOSAL_IDS`) and no one-time migration. Only testnet and mirrornet builds (`USE_ALTERNATE_CHAIN_ID`) set `HIVE_NUM_HARDFORKS` to 29 and register it (`hardfork.d/0-preamble.hf:15-20`, `database_hardfork.cpp:112-116`); a mainnet build keeps 28, so a 1.28.8 mainnet node cannot activate HF29. What each switch does: Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet). RC stays non-consensus until HF29 (Part 08, section Non-Consensus Status).

**Software releases after HF28 (no new hardfork):** the mainnet `HIVE_BLOCKCHAIN_VERSION` moved 1.28.6 -> 1.28.7 as a network-robustness maintenance release - fork-tolerance (a too-old block is treated as *unlinkable* rather than invalid, avoiding peer-disconnect storms; Part 06, section Fork Resolution: Longest Chain Rule) plus RocksDB info-LOG bounding - and then 1.28.7 -> 1.28.8 (`protocol/config.hpp:139`); testnet and mirrornet builds of 1.28.8 report 1.29.0 (`protocol/config.hpp:69`, `:134`) because they register HF29. These are *software* version bumps only: the latest consensus hardfork active on mainnet remains **HF28**, and hardfork activation is time + witness-vote gated; `process_hardforks()` never consults the software version (Part 09, Summary).
