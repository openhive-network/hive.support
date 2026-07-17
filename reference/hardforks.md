# Hive Hardfork History Reference

Source: hive-core release 1.28.7. 28 hardforks: HF1-22 pre-fork (inherited from Steem), HF23 Hive genesis (chain-split), HF24-28 Hive-native.

Versioning: HF1-23 use major version 0 (0.1-0.23). HF24-28 use major version 1 (1.24-1.28). The version bump came at HF24 but the chain split happened at HF23. Version comparison treats major 0 and 1 as equivalent for backward compatibility.

Activation: HF1-4 activated by time only. HF5+ require 17/21 witness supermajority vote plus time. Exception: HF23 was force-activated without witness majority — this is the fork that created Hive.

| HF | Block | Date | Key Changes |
|----|-------|------|-------------|
| 1 | 905,693 | 2016-04-25 | Vesting share split (all VESTS x1,000,000); permlink validation |
| 2 | 934,585 | 2016-04-26 | Witness vote retally; max witness votes enforced |
| 3 | 953,363 | 2016-04-27 | Direct witness vote adjustment |
| 4 | 1,041,497 | 2016-05-01 | Virtual schedule time overflow fix |
| 5 | 1,934,236 | 2016-05-31 | **Witness-based hardfork voting** introduced (replaces time-only activation) |
| 6 | 2,790,882 | 2016-06-30 | Reverse auction mechanism; 60s post rate limit; self-vote detection |
| 7 | 2,889,019 | 2016-07-04 | Cashout time changes; upvote lockout before payout |
| 8 | 2,889,959 | 2016-07-04 | Vote count retally (1 hour after HF7) |
| 9 | 3,202,773 | 2016-07-14 | Reset 170+ compromised accounts after security breach |
| 10 | 3,239,649 | 2016-07-15 | Liquidity reward period changed to 30 min |
| 11 | 3,276,913 | 2016-07-17 | Temp account rejected as recovery account |
| 12 | 3,533,567 | 2016-07-26 | **Liquidity rewards removed** permanently; post bandwidth limiting |
| 13 | 4,105,155 | 2016-08-15 | `pow` deprecated (use `pow2`); vote dust threshold |
| 14 | 5,137,542 | 2016-09-20 | `custom_json` enabled; `change_recovery_account` enabled; witness shutdown on missed blocks |
| 15 | 6,547,932 | 2016-11-08 | Posting authority account existence verification |
| **16** | 7,353,249 | 2016-12-06 | **Power down 104 weeks -> 13 weeks**; new inflation model (9.5% decreasing to 0.95%) |
| 17 | 10,629,455 | 2017-03-30 | Reward fund system; **mining disabled** permanently (20 voted + 1 runner witness schedule) |
| 18 | 10,629,486 | 2017-03-30 | Version marker only (31 blocks after HF17, no-op) |
| 19 | 12,988,978 | 2017-06-20 | **Linear rewards**; 10 full votes/day; square root curation curve |
| **20** | 26,256,743 | 2018-09-25 | **Resource Credits system**; `claim_account` op; `account_create_with_delegation` deprecated |
| **21** | 35,921,786 | 2019-08-27 | **DHF/proposal system**; convergent linear rewards; separate downvote pool (25%); 50% curation |
| 22 | 35,974,326 | 2019-08-29 | Downvote mana fix (2 days after HF21); contains HF23 exclusion account list |
| **23** | 41,818,752 | 2020-03-20 | **Steem-to-Hive fork** (forced). ~360 accounts cleared; balances to treasury |
| **24** | 47,797,680 | 2020-10-14 | First Hive-native HF (v1.x). ~47 accounts restored; chain ID set; treasury renamed to `hive.fund` |
| **25** | 55,235,767 | 2021-06-30 | **Recurrent transfers**; `collateralized_convert`; governance vote expiration (365d); pure linear rewards |
| **26** | 68,676,505 | 2022-10-11 | Dust votes count; no vote-edit penalty; HBD cap raised to 20%; fast confirmation op |
| 27 | 69,050,084 | 2022-10-24 | Timeshare witness scheduling hotfix (13 days after HF26) |
| **28** | 100,000,000 | 2025-11-19 | Power down fix; **stable votes** (max mana); extended expiration (24h); strict/mixed authorities; DHF HBD excluded from inflation |

## Key Hardfork Details

**HF16 — Power Down & Inflation** (2016-12-06): Reduced power down from 104 weekly installments to 13 (2 years to 13 weeks). Introduced declining inflation model starting at 9.5%, decreasing 0.01% every 250k blocks, floor at 0.95%.

**HF20 — Resource Credits** (2018-09-25): The largest single feature addition. Replaced bandwidth-based rate limiting with the RC system. Every account gets RC proportional to their HP, spent on transactions, regenerating over 5 days. Enabled `claim_account` for discounted account creation.

**HF21 — Economic Improvement Proposal** (2019-08-27): Created the DHF (Decentralized Hive Fund) proposal system funded by 10% of inflation. Changed reward split to 50/50 author/curator. Added separate downvote pool at 25% of upvote mana. Switched to convergent linear reward curve.

**HF23 — The Hive Fork** (2020-03-20): The community fork away from Steemit Inc/Tron. Force-activated without witness majority (unique override). Cleared ~360 accounts affiliated with Steemit Inc, Tron puppets, and supporters. Balances moved to treasury and recorded for potential restoration.

**HF24 — Hive Identity** (2020-10-14): First major-version-1 hardfork. Set the Hive chain ID (`beeab0de...`). Restored ~47 accounts erroneously cleared or won via airdrop appeal proposals. Renamed treasury from `steem.dao` to `hive.fund`. Enabled `update_proposal` operation.

**HF25 — Recurrent Transfers** (2021-06-30): Enabled recurring scheduled transfers. Added `collateralized_convert` (HIVE to HBD with 2x collateral). Set governance vote expiration to 365 days. Returned to pure linear reward curves, disabled reverse auction.

**HF26 — Governance Improvements** (2022-10-11): Made dust-level votes count as real votes. Removed penalty for editing votes. Raised HBD hard cap to 20%. Allowed authority updates twice per hour. Solidified old soft forks (custom_binary disabled, custom op size limits enforced).

**HF28 — Stability & Authority** (2025-11-19, block 100,000,000): Fixes a power-down rounding bug originating from HF1's vesting split. Stable votes use max mana instead of current mana for consistent vote strength. Extended signature expiration up to 24 hours. Allows strict and mixed authorities (owner/active combined with posting in one transaction). Excludes DHF treasury HBD from inflation calculation.

**Software releases after HF28 (no new hardfork):** the mainnet `HIVE_BLOCKCHAIN_VERSION` moved 1.28.6 -> 1.28.7 (`config.hpp:140`) as a network-robustness maintenance release — fork-tolerance (a too-old block is treated as *unlinkable* rather than invalid, avoiding peer-disconnect storms) plus RocksDB info-LOG bounding. This is a *software* version bump only: the latest consensus hardfork remains **HF28**, and hardfork activation is time + witness-vote gated, never tied to the software version.
