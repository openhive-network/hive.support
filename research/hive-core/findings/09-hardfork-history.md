# Findings: Hardfork History — Evolution of Consensus Rules

## Summary

The Hive blockchain has undergone **28 hardforks** from genesis to the current version. Hardforks 1–23 occurred during the Steem era (major version 0), while hardforks 24–28 are Hive-native (major version 1). The hardfork system uses a witness supermajority voting mechanism (17/21) introduced at HF5; prior hardforks activated purely by time. Each hardfork is defined in a `.hf` file under `libraries/protocol/hardfork.d/`, applied via `database::apply_hardfork()` with one-time state migrations, and gated throughout the codebase via `has_hardfork()` checks (225+ occurrences across 19 chain-layer source files).

The most critical hardfork is **HF23** (the Steem→Hive fork), which cleared Steemit/Tron-affiliated accounts and was **forced without witness majority** — a unique override in the code. **HF20** introduced the Resource Credits system, the single largest feature addition. **HF28** (block 100,000,000) is the most recent, with an expected activation in November 2025.

## Hardfork System Architecture

### How Hardforks Are Defined

Each hardfork lives in a `.hf` file in `libraries/protocol/hardfork.d/`:
- **Naming convention**: `{major}_{minor}.hf` (e.g., `0_17.hf`, `1_24.hf`)
- **Preamble**: `0-preamble.hf` defines `HIVE_NUM_HARDFORKS` (currently 28)
- Files are concatenated into `hardfork.hpp` at build time

Each `.hf` file defines:
```cpp
#define HIVE_HARDFORK_X_Y  <sequential_id>          // e.g., 20
#define HIVE_HARDFORK_X_Y_TIME  <unix_timestamp>     // activation time
#define HIVE_HARDFORK_X_Y_VERSION hardfork_version(X, Y)
// Optional: sub-feature aliases like HIVE_HARDFORK_0_20__1760
// Optional: feature flags like HIVE_HARDFORK_1_26_DUST_VOTE_FIX
```

**Sub-feature aliases**: Many hardforks define aliases like `HIVE_HARDFORK_0_14__259` that map to the parent hardfork number. These correspond to original GitHub issue numbers from Steem development and allow fine-grained `has_hardfork()` checks that document *which specific fix* a code path implements.

**Testnet support**: All times use `USE_ALTERNATE_CHAIN_ID` guards to allow testnet overrides via `testnet_blockchain_configuration`.

### How Hardforks Activate

**Source**: `libraries/chain/witness_schedule.cpp` (lines 264–333), `libraries/chain/database_hardfork.cpp`

**Pre-HF5 (time-based)**:
```
while last_hardfork < HIVE_NUM_HARDFORKS
  AND hardfork_times[last_hardfork + 1] <= head_block_time()
  → apply_hardfork(last_hardfork + 1)
```

**Post-HF5 (witness vote + time)**:
1. Each witness signals `hardfork_version_vote` and `hardfork_time_vote`
2. During witness schedule updates, the system counts votes per version
3. When `HIVE_HARDFORK_REQUIRED_WITNESSES` (17 of 21) signal the same version+time AND time has passed:
   - `hardfork_property_object.next_hardfork` and `next_hardfork_time` are set
4. `process_hardforks()` checks: if `next_hardfork > current_version` AND `next_hardfork_time <= head_block_time()`:
   - Calls `apply_hardfork(last_hardfork + 1)`

**Special case — HF23 forced activation**:
```cpp
if( hpo.current_hardfork_version == HIVE_HARDFORK_0_22_VERSION )
{
  // Force HF23 even no witness majority.
  _hpo.next_hardfork = HIVE_HARDFORK_0_23_VERSION;
  _hpo.next_hardfork_time = fc::time_point_sec(HIVE_HARDFORK_0_23_TIME);
}
```
This is the only hardfork that bypasses the witness voting requirement — it was the Hive community's fork away from Steem.

### Hardfork State Tracking

**Source**: `libraries/chain/include/hive/chain/detail/state/hardfork_property_object.hpp`

The `hardfork_property_object` (singleton) stores:

| Field | Type | Purpose |
|-------|------|---------|
| `processed_hardforks` | `vector<time_point_sec>` | Timestamp of each applied hardfork (index = HF number) |
| `last_hardfork` | `uint32_t` | Current hardfork number |
| `current_hardfork_version` | `hardfork_version` | Current version (major.minor) |
| `next_hardfork` | `hardfork_version` | Next scheduled hardfork version |
| `next_hardfork_time` | `time_point_sec` | When next hardfork activates |
| `h23_balances` | `flat_map<name, hf23_item>` | Balances cleared at HF23 (for HF24 restoration) |

**`has_hardfork(n)`**: Returns `processed_hardforks.size() > n` — simply checks if hardfork N has been applied.

**`get_hardfork()`**: Returns `processed_hardforks.size() - 1` — current hardfork number.

### Version System

**Source**: `libraries/protocol/include/hive/protocol/version.hpp`

The `version` struct packs major.hardfork.release into a `uint32_t`:
- Bits 31–24: major version (0 or 1)
- Bits 23–16: hardfork number
- Bits 15–0: release number

**Critical compatibility rule**: Version comparison treats major 0 and 1 as equivalent. This was needed for the HF24 transition where some witnesses were still running version 0.x nodes:
```cpp
if( major_v() == 0 && _val == 1 )  // 0.HF == 1.HF
  val &= 0x00FFFFFF;
```

`hardfork_version` extends `version` with the release number zeroed out — only major and hardfork number matter for hardfork comparisons.

## Current State

- **Current hardfork**: HF28
- **Current blockchain version**: 1.28.x
- **HF28 activation block**: 100,000,000 (defined, not yet reached as of code review)
- **HF28 activation time**: November 19, 2025, 13:00:00 UTC (via `next_hf_time()` returning `1763557200`)
- **Total hardfork definitions**: 28 (HIVE_NUM_HARDFORKS = 28)

## Hardfork Reference

### HF1 — Vesting Share Split
- **Block**: 905,693
- **Time**: 2016-04-25 17:30:00 UTC
- **Version**: 0.1
- **One-time migration**: `perform_vesting_share_split(1000000)` — multiplied all VESTS amounts by 1,000,000
- **Conditional behavior**:
  - Permlink validation introduced (`validate_permlink_0_1`)
  - Curation weight calculation changed (removed 1M multiplier)
- **Note**: This split introduced a rounding issue in power downs that persisted until HF28 fixed it

### HF2 — Witness Vote Retally
- **Block**: 934,585
- **Time**: 2016-04-26 18:00:00 UTC
- **Version**: 0.2
- **One-time migration**: `retally_witness_votes()`
- **Conditional behavior**:
  - Max witness votes enforced (`HIVE_MAX_ACCOUNT_WITNESS_VOTES`)
  - Proxied witness vote adjustments
  - Virtual schedule lap length changed (`HIVE_VIRTUAL_SCHEDULE_LAP_LENGTH2`)

### HF3 — Witness Vote Adjustment
- **Block**: 953,363
- **Time**: 2016-04-27 13:00:00 UTC
- **Version**: 0.3
- **One-time migration**: `retally_witness_votes()`
- **Conditional behavior**: Direct witness vote adjustment (vs proxied in HF2)

### HF4 — Virtual Schedule Fix
- **Block**: 1,041,497
- **Time**: 2016-05-01
- **Version**: 0.4
- **One-time migration**: `reset_virtual_schedule_time()`
- **Conditional behavior**: Virtual scheduled time overflow protection (clamped to `fc::uint128_max_value()`)

### HF5 — Witness Hardfork Voting
- **Block**: 1,934,236
- **Time**: 2016-05-31 17:00:00 UTC
- **Version**: 0.5
- **One-time migration**: None
- **Key change**: **Introduced witness-based hardfork activation** — prior hardforks were time-only
- **Sub-features**: 6 aliases (#22, #54, #55, #56, #59, #62)
- **Conditional behavior**: PoW witness work uniqueness check

### HF6 — Reverse Auction & Rate Limiting
- **Block**: 2,790,882
- **Time**: 2016-06-30 14:00:00 UTC
- **Version**: 0.6
- **One-time migration**: `retally_witness_vote_counts()`
- **Key changes**:
  - Reverse auction mechanism introduced (6 days before hardfork)
  - Post rate limiting: minimum 60 seconds between posts
  - Self-vote detection (`HIVE_HARDFORK_0_6__112`)
  - Order ID full 32-bit range enabled
- **Sub-features**: 9 aliases (#74, #78, #80, #101, #104, #112, #113, #114, #127)

### HF7 — Cashout Time & Upvote Lockout
- **Block**: 2,889,019
- **Time**: 2016-07-04 00:00:00 UTC
- **Version**: 0.7
- **One-time migration**: None
- **Conditional behavior**: Upvote lockout timer before payout (1 minute pre-HF17)

### HF8 — Vote Count Retally
- **Block**: 2,889,959
- **Time**: 2016-07-04 01:00:00 UTC (1 hour after HF7)
- **Version**: 0.8
- **One-time migration**: `retally_witness_vote_counts(true)` (with reset flag)

### HF9 — Compromised Account Recovery
- **Block**: 3,202,773
- **Time**: 2016-07-14 00:00:00 UTC
- **Version**: 0.9
- **One-time migration**: **Reset 170+ compromised accounts** — set owner/active/posting authorities to a recovery public key (`HIVE_HF_9_COMPROMISED_ACCOUNTS_PUBLIC_KEY_STR`)
- **Key detail**: Hardcoded list of compromised account names and "bad memos" from a security breach. Included accounts like `dan`, `dantheman`, `ned`, `steemit`, `steemitblog`, `gtg`
- **Sub-feature**: `HIVE_HARDFORK_0_9__141` — liquidity weight calculation change

### HF10 — Liquidity Reward Period
- **Block**: 3,239,649
- **Time**: 2016-07-15 12:00:00 UTC
- **Version**: 0.10
- **One-time migration**: `retally_liquidity_weight()`
- **Key change**: Minimum liquidity reward period changed to 30 minutes (`HIVE_MIN_LIQUIDITY_REWARD_PERIOD_SEC_HF10`)

### HF11 — Recovery Account Restriction
- **Block**: 3,276,913
- **Time**: 2016-07-17 15:00:00 UTC
- **Version**: 0.11
- **One-time migration**: None
- **Key change**: `HIVE_TEMP_ACCOUNT` rejected as recovery account for new accounts

### HF12 — Liquidity Rewards Removed
- **Block**: 3,533,567
- **Time**: 2016-07-26 15:00:00 UTC
- **Version**: 0.12
- **One-time migration**:
  - Comment cashout fix applied
  - **Liquidity reward index cleared** — mechanism discontinued permanently
- **Sub-features**: 4 aliases (#176, #177, #178, #179)
- **Conditional behavior**: Post bandwidth limiting, discussion frozen detection, comment editing restrictions, cashout time calculations

### HF13 — PoW Deprecation
- **Block**: 4,105,155
- **Time**: 2016-08-15 14:00:00 UTC
- **Version**: 0.13
- **One-time migration**: None
- **Key change**: `pow` operation deprecated ("Use pow2 instead")
- **Sub-features**: 3 aliases (#248, #256, #257)
- **Conditional behavior**: Vote dust threshold changes, cashout window calculation adjustments

### HF14 — Witness Scheduling & Custom JSON
- **Block**: 5,137,542
- **Time**: 2016-09-20 15:00:00 UTC
- **Version**: 0.14
- **One-time migration**: None
- **Key changes**:
  - Disabled witnesses skipped in schedule (#278)
  - `custom_json` operation enabled (#317)
  - `change_recovery_account` operation enabled (#324)
  - Account creation fee symbol canonicalization (#410)
  - Vote dust threshold with `HIVE_VOTE_DUST_THRESHOLD` (#259)
  - Witness shutdown threshold for missed blocks (#278)
- **Sub-features**: 11 aliases (#143, #230, #239, #259, #278, #306, #307, #317, #324, #327, #410)

### HF15 — Posting Authority Verification
- **Block**: 6,547,932
- **Time**: 2016-11-08 16:00:00 UTC
- **Version**: 0.15
- **One-time migration**: None
- **Key change**: Authority account existence verification for posting authority updates (#465)

### HF16 — Power Down Reduction & Inflation Model
- **Block**: 7,353,249
- **Time**: 2016-12-06 16:00:00 UTC
- **Version**: 0.16
- **One-time migration**: Feed history window trimmed to `HIVE_FEED_HISTORY_WINDOW`
- **Key changes**:
  - **Power down changed from 104 weeks to 13 weeks** (`HIVE_VESTING_WITHDRAW_INTERVALS`: 104 → 13)
  - Conversion delay changed to `HIVE_CONVERSION_DELAY`
  - Equihash PoW enabled (#551)
  - **New inflation model**: 9.5% starting rate, decreasing 0.01% every 250k blocks toward 0.95% floor
  - PoW difficulty calculation adjusted
- **Sub-features**: 2 aliases (#551, #562)

### HF17 — Reward Fund System & Mining End
- **Block**: 10,629,455
- **Time**: 2017-03-30 15:00:00 UTC
- **Version**: 0.17
- **One-time migration**:
  - Witness schedule composition changed: **20 voted + 0 miner + 1 runner** (was 19 + 1 + 1)
  - `reward_fund_object` ("post") created with initial recent_claims
  - Global `total_reward_fund_hive` and `total_reward_shares2` zeroed
  - Comment cashout fix applied
- **Key changes**:
  - Comment depth limit increased (6 → 65,535)
  - Reward fund system created (per-pool rewards)
  - `pow2` (mining) **disabled** permanently (#770)
  - Various comment payout timing changes
  - Upvote lockout increased to 12 hours before payout (#900)
- **Sub-features**: 14 aliases (#659, #733, #766–774, #818, #869, #926, #900)
- **Hardcoded migration data**: `HIVE_HF_17_NUM_POSTS` (49,357), `HIVE_HF_17_NUM_REPLIES` (242,051), `HIVE_HF_17_RECENT_CLAIMS`

### HF18 ��� Simultaneous with HF17
- **Block**: 10,629,486 (31 blocks after HF17)
- **Time**: 2017-03-30 15:00:00 UTC (same timestamp)
- **Version**: 0.18
- **One-time migration**: None
- **Note**: Activated simultaneously with HF17 — effectively a no-op hardfork used as a version marker

### HF19 — Linear Rewards & Vote Cleanup
- **Block**: 12,988,978
- **Time**: 2017-06-20 15:00:00 UTC
- **Version**: 0.19
- **One-time migration**:
  - Vote power reserve rate set to `HIVE_REDUCED_VOTE_POWER_RATE` (10 full votes/day)
  - Reward fund: recent_claims reset, author curve → linear, curation curve → square_root
  - All zero-amount delegation objects removed
  - Old cashouts removed
- **Key changes**:
  - Comment cashout extra objects discontinued
  - Account creation fee threshold changes (#987, #997)
  - Various voting refinements
- **Sub-features**: 9 aliases (#822, #876, #971, #977, #987, #997, #1051, #1052, #1053)
- **Hardcoded**: `HIVE_HF_19_RECENT_CLAIMS`, actual activation time for curation curve computation

### HF20 — Resource Credits System
- **Block**: 26,256,743
- **Time**: 2018-09-25 15:00:00 UTC
- **Version**: 0.20
- **One-time migration**:
  - **RC system fully initialized**: parameter objects, usage buckets, pool, stats objects
  - All existing accounts: RC mana set to maximum, `rc_adjustment` set to `HIVE_RC_HISTORICAL_ACCOUNT_CREATION_ADJUSTMENT`
  - Delegation return period → `HIVE_DELEGATION_RETURN_PERIOD_HF20` (5 days)
  - Reverse auction → 15 minutes
  - HBD limits: start 9%, stop 10%
  - Available account subsidies → 0
  - Witness account creation fees multiplied by `HIVE_CREATE_ACCOUNT_WITH_HIVE_MODIFIER`
- **Key changes**:
  - **Resource Credits (RC) system** — the single largest feature addition in blockchain history
  - `claim_account` and `create_claimed_account` operations enabled (#1771)
  - `account_create_with_delegation` deprecated (#1760)
  - Negative vesting withdrawal rejected
  - Limit order expiration capped at 28 days (#1449)
  - Mana-based voting system for delegations
  - Transaction signature validation changes
  - Authority size validation enforced
  - Account creation fee must be exact
- **Sub-features**: 21 aliases (#409, #1449, #1620, #1760–1782, #1811–1877, #1944, #2019–2651, SP190)
- **Has ACTUAL_TIME**: Separate from TIME (actual activation determined after witness voting)

### HF21 — Economic Improvement Proposal (EIP)
- **Block**: 35,921,786
- **Time**: 2019-08-27 15:00:00 UTC
- **Version**: 0.21
- **One-time migration**:
  - Proposal fund percent → 10%
  - Content reward percent → 65%
  - Downvote pool percent → 25%
  - Reverse auction → 5 minutes
  - Treasury account created and locked
  - Reward fund: 50% curation, convergent_linear author curve, convergent_square_root curation curve, `HIVE_CONTENT_CONSTANT_HF21`
- **Key changes**:
  - **Convergent linear rewards** (replacing pure linear)
  - **DHF (Decentralized Hive Fund) / proposal system** enabled
  - Separate downvote pool (25% of upvote mana)
  - Treasury cannot receive vesting or vesting withdrawals
  - `account_update2` operation enabled (#3274)
  - Comment edit throttle: 1 edit per block (#3313)
  - Power down rounding fix (add 1 if needed)
- **Sub-features**: 6 aliases (#2203, #3004, #3274, #3313, #3336, #3343)
- **Stall block**: `HIVE_HF_21_STALL_BLOCK` = 35,922,615 — downvote mana initialization workaround

### HF22 — Downvote Mana Fix
- **Block**: 35,974,326
- **Time**: 2019-08-29 15:00:00 UTC (2 days after HF21)
- **Version**: 0.22
- **One-time migration**: None
- **Key changes**:
  - Downvote mana calculation fix (#3485) — proper proportional calculation
  - Delegation mana adjustments corrected
  - Contains `hardforkprotect::get_steemit_accounts()` — the list of ~360 accounts to be cleared at HF23
- **Note**: Rapid follow-up to HF21, mainly fixing downvote pool integration issues

### HF23 — The Steem→Hive Fork ⚡
- **Block**: 41,818,752
- **Time**: 2020-03-20 14:00:00 UTC
- **Version**: 0.23
- **One-time migration**:
  - **`clear_accounts()`** called on ~360 Steemit Inc, Tron puppet, and supporter accounts
  - Balances (HIVE + HBD) transferred to treasury, recorded in `h23_balances` for potential restoration
  - All vesting, delegations, pending withdrawals cleared
  - Accounts left with zero balances but still existing
  - ~~TAPOS buffer reset~~ (commented out in final code)
- **Key changes**:
  - **The Hive blockchain fork from Steem**
  - **FORCED without witness majority** — unique override in `witness_schedule.cpp`
  - Steemit Inc accounts (steemit, steemit2, steem, misterdelegation, etc.)
  - Tron puppet accounts (goodguy24, aheadofslow, night11pm, etc.)
  - Community members who voted for Tron sockpuppets with >1k SP
  - `get_steemit_accounts()` returns the full exclusion list
- **Significance**: This is the defining hardfork — the community forking away from Steemit Inc/Tron control

### HF24 — First Hive-Native Hardfork
- **Block**: 47,797,680
- **Time**: 2020-10-06 (scheduled) / 2020-10-14 19:31:24 UTC (actual)
- **Version**: 1.24 (first major version 1)
- **One-time migration**:
  - **`restore_accounts()`** — restored HIVE/HBD balances for ~47 accounts:
    - 29 accounts erroneously included in HF23 exclusion list
    - 4 accounts won airdrop appeal (proposal #104)
    - 14 accounts won airdrop appeal (proposal #111)
  - **Chain ID set** to Hive mainnet: `beeab0de00000000000000000000000000000000000000000000000000000000`
  - **Treasury renamed**: `steem.dao` → `hive.fund` (new account created, balance consolidated)
  - Blockchain configuration updated
- **Key changes**:
  - Major version changed from 0 to 1
  - Signature validation changes (has `ACTUAL_TIME` separate from `TIME`)
  - HIVE transfers to treasury auto-convert to HBD at median price
  - Delayed voting system introduced
  - Updating paid-out comment parameters forbidden
  - `update_proposal` operation enabled
  - Clear account improvements (delayed votes cleared, HBD interest touched)

### HF25 — Recurrent Transfers & Linear Rewards
- **Block**: 55,235,767
- **Time**: 2021-06-30 14:00:00 UTC
- **Version**: 1.25
- **One-time migration**:
  - Reward fund: both curation and author curves set to **linear** (removing convergent)
  - Reverse auction **disabled** (0 seconds)
  - Early voting window: 24 hours
  - Mid voting window: 48 hours
- **Key changes**:
  - **Recurrent transfers** enabled (`recurrent_transfer_operation`)
  - **`collateralized_convert` operation** enabled (HIVE→HBD with 2x collateral)
  - **Governance vote expiration**: 365 days (`HIVE_GOVERNANCE_VOTE_EXPIRATION_PERIOD`)
  - HBD hard cap no longer counts treasury balance (#140)
  - Proposal end date update extension allowed
  - Expired proposal vote protection

### HF26 — Governance & Vote Improvements
- **Block**: 68,676,505
- **Time**: 2022-10-11 12:00:00 UTC
- **Version**: 1.26
- **One-time migration**:
  - HBD cap raised: start 20%, stop 20% (was 9%/10%)
  - **Future witness schedule object** created (second `witness_schedule_object` with id=1)
- **Key changes**:
  - **Dust votes are votes**: dust-level votes now count as actual votes
  - **No vote edit penalty**: editing a vote treated as new vote (no penalty)
  - HBD hard cap increased to 20%
  - **Authorization update twice per hour** (was once per hour)
  - **Old soft forks solidified**: custom_binary disabled, `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` enforced
  - Future witness schedule always computed
  - **Fast confirmation operation** enabled

### HF27 — Timeshare Witness Fix
- **Block**: 69,050,084
- **Time**: 2022-10-24 12:00:00 UTC (13 days after HF26)
- **Version**: 1.27
- **One-time migration**: None (falls to `default: break`)
- **Key change**: **Fix timeshare witness scheduling** to restore pre-HF26 behavior
- **Note**: Rapid hotfix for HF26 regression in witness scheduling

### HF28 — Power Down Fix, Stable Votes, Authority Improvements
- **Block**: 100,000,000
- **Time**: 2025-11-19 13:00:00 UTC (via `next_hf_time()` returning `1763557200`)
- **Version**: 1.28
- **One-time migration**: `remove_proposal_votes_for_accounts_without_voting_rights()` — cleans up votes from accounts that shouldn't have voting rights
- **Key changes**:
  - **Fix prolonged power down** (`HIVE_HARDFORK_1_28_FIX_POWER_DOWN`): Fixes bug from HF1 vesting share split where rounding caused prolonged power downs
  - **Fix cancel power down** (`HIVE_HARDFORK_1_28_FIX_CANCEL_POWER_DOWN`): Better no-op detection for cancel operations
  - **Stable vote** (`HIVE_HARDFORK_1_28_STABLE_VOTE`): Uses **max mana** instead of current mana for vote strength calculation
  - **Global witness properties** (`HIVE_HARDFORK_1_28_GLOBAL_WITNESS_PROPS`): Max block size and HBD APR activated with schedule activation instead of creation
  - **Extended expiration** (`HIVE_HARDFORK_1_28_EXPIRATION_TIME`): Signature expiration up to 24 hours (`HIVE_MAX_TIME_UNTIL_SIGNATURE_EXPIRATION`), transaction runtime up to 1 hour (`HIVE_MAX_TIME_UNTIL_EXPIRATION`)
  - **Strict and mixed authorities** (`HIVE_HARDFORK_1_28_ALLOW_STRICT_AND_MIXED_AUTHORITIES`): Accept only required authority level; owner/active can be combined with posting in one transaction
  - **Redundant signatures allowed** (`HIVE_HARDFORK_1_28_ALLOW_REDUNDANT_SIGNATURES`)
  - **DHF HBD excluded from inflation** (`HIVE_HARDFORK_1_28_NO_DHF_HBD_IN_INFLATION`): Inflation calculation excludes treasury HBD balance from virtual supply
  - **Proposal vote/remove validation**: Reject voting on or removing nonexistent proposals

## Hardfork-Conditional Code Map

### By Feature Area

| Feature/Rule | Added/Changed At | Code Location |
|--------------|-----------------|---------------|
| Permlink validation | HF1 | `hive_evaluator_social.cpp` |
| Vesting share split (1M multiplier) | HF1 | `database_comment.cpp:612` |
| Max witness votes limit | HF2 | `hive_evaluator.cpp:280` |
| Virtual schedule lap length | HF2 | `database_witness.cpp:82` |
| Virtual schedule overflow fix | HF4 | `database_witness.cpp:88` |
| Witness hardfork voting | HF5 | `witness_schedule.cpp:264` |
| Reverse auction mechanism | HF6 | `0_6.hf` |
| Post rate limiting (60s) | HF6 | `hive_evaluator_social.cpp:202` |
| Self-vote detection | HF6 | `hive_evaluator_social.cpp:571` |
| Order ID full range | HF6 | `database_market.cpp:52` |
| Upvote lockout (1min/12hr) | HF7/HF17 | `hive_evaluator_social.cpp:385` |
| Compromised account recovery | HF9 | `database_hardfork.cpp:212` |
| Liquidity rewards removed | HF12 | `database_hardfork.cpp:238` |
| PoW deprecated | HF13 | `hive_evaluator.cpp:503` |
| Disabled witnesses skipped | HF14 | `witness_schedule.cpp:166` |
| Custom JSON enabled | HF14 | `hive_evaluator.cpp:380` |
| Posting authority verification | HF15 | `hive_evaluator_account.cpp:329` |
| Power down 104→13 weeks | HF16 | `hive_evaluator_transfer.cpp:362` |
| Inflation model (9.5%→0.95%) | HF16 | `database.cpp:1710` |
| Witness schedule 20/0/1 | HF17 | `database_hardfork.cpp:269` |
| Comment depth 65535 | HF17 | `hive_evaluator_social.cpp:185` |
| Reward fund system | HF17 | `database_hardfork.cpp:278` |
| Mining disabled | HF17 | `hive_evaluator.cpp:511` |
| Vote power reserve rate | HF19 | `database_hardfork.cpp:301` |
| Linear author, sqrt curation | HF19 | `database_hardfork.cpp:310` |
| RC system initialized | HF20 | `database_hardfork.cpp:337` |
| Account claim/create | HF20 | `hive_evaluator_account.cpp:404` |
| Delegation with creation deprecated | HF20 | `hive_evaluator_account.cpp:212` |
| Authority size validation | HF20 | `hive_evaluator_account.cpp:293` |
| Mana-based voting | HF20 | `hive_evaluator_transfer.cpp:696` |
| Convergent linear rewards | HF21 | `database_hardfork.cpp:440` |
| DHF / proposals | HF21 | `dhf_evaluator.cpp:36` |
| Downvote pool (25%) | HF21 | `database_hardfork.cpp:424` |
| Treasury locked | HF21 | `database_hardfork.cpp:438` |
| account_update2 enabled | HF21 | `hive_evaluator_account.cpp:362` |
| Downvote mana proportional calc | HF22 | `hive_evaluator_social.cpp:665` |
| Steemit accounts cleared | HF23 | `database_hardfork.cpp:456` |
| HF23 forced (no witness vote) | HF23 | `witness_schedule.cpp:289` |
| Chain ID set to Hive | HF24 | `database_hardfork.cpp:477` |
| Accounts restored from HF23 | HF24 | `database_hardfork.cpp:473` |
| Treasury renamed (hive.fund) | HF24 | `database_hardfork.cpp:529` |
| Delayed voting | HF24 | `database.cpp:1656` |
| HIVE→treasury auto-converts to HBD | HF24 | `hive_evaluator_transfer.cpp:262` |
| update_proposal enabled | HF24 | `dhf_evaluator.cpp:107` |
| Recurrent transfers | HF25 | `hive_evaluator_transfer.cpp:908` |
| Collateralized convert | HF25 | `hive_evaluator_transfer.cpp:475` |
| Governance vote expiration | HF25 | `1_25.hf` |
| Linear rewards (both curves) | HF25 | `database_hardfork.cpp:483` |
| Dust votes count | HF26 | `hive_evaluator_social.cpp:751` |
| No vote edit penalty | HF26 | `hive_evaluator_social.cpp:755` |
| HBD cap 20% | HF26 | `database_hardfork.cpp:498` |
| Auth update twice/hour | HF26 | `hive_evaluator_account.cpp:313` |
| Soft forks solidified | HF26 | `hive_evaluator.cpp:330` |
| Future witness schedule | HF26 | `database_hardfork.cpp:503` |
| Timeshare witness fix | HF27 | `witness_schedule.cpp` |
| Power down fix (HF1 bug) | HF28 | `database_vesting.cpp:128` |
| Cancel power down fix | HF28 | `hive_evaluator_transfer.cpp:349` |
| Stable vote (max mana) | HF28 | `hive_evaluator_social.cpp:659` |
| Global witness props timing | HF28 | `witness_schedule.cpp:147` |
| Extended tx expiration | HF28 | `database.cpp:2533` |
| Strict/mixed authorities | HF28 | `database.cpp:2609` |
| Redundant signatures | HF28 | `database.cpp:2610` |
| DHF HBD excluded from inflation | HF28 | `database.cpp:1724` |
| Proposal vote validation | HF28 | `dhf_evaluator.cpp:177` |

### has_hardfork() Distribution

| Source File | Count |
|-------------|-------|
| `hive_evaluator_social.cpp` | 40 |
| `hive_evaluator_transfer.cpp` | 37 |
| `database.cpp` | 35 |
| `database_comment.cpp` | 25 |
| `hive_evaluator_account.cpp` | 23 |
| `hive_evaluator.cpp` | 16 |
| `database_vesting.cpp` | 11 |
| `witness_schedule.cpp` | 8 |
| `dhf_evaluator.cpp` | 7 |
| `database_market.cpp` | 5 |
| `rc_utility.cpp` | 5 |
| Other files | 13 |
| **Total** | **225** |

## One-Time Migrations Summary

| HF | Migration | Description |
|----|-----------|-------------|
| 1 | `perform_vesting_share_split(1000000)` | Multiply all VESTS by 1M |
| 2, 3 | `retally_witness_votes()` | Recount witness votes |
| 4 | `reset_virtual_schedule_time()` | Reset witness scheduling |
| 6 | `retally_witness_vote_counts()` | Recount vote counts |
| 8 | `retally_witness_vote_counts(true)` | Recount with reset |
| 9 | Reset 170+ compromised accounts | Set authorities to recovery key |
| 10 | `retally_liquidity_weight()` | Recount liquidity weights |
| 12 | Clear liquidity reward index | Permanently remove mechanism |
| 16 | Trim feed history window | Resize to new constant |
| 17 | Create reward fund, change witness schedule | Major structural change |
| 19 | Reset vote rate, reward curves, remove zero delegations | Economic parameter reset |
| 20 | **Initialize entire RC system** | Biggest one-time migration |
| 21 | Set EIP parameters, create treasury, update reward fund | Economic overhaul |
| 23 | **Clear ~360 Steemit/Tron accounts** | The Hive fork action |
| 24 | Restore ~47 accounts, set chain ID, rename treasury | Hive identity established |
| 25 | Set linear rewards, disable reverse auction | Reward simplification |
| 26 | Raise HBD cap, create future witness schedule | Governance improvements |
| 28 | Remove invalid proposal votes | Cleanup |

## Key Discoveries

1. **HF23 forced activation is unique**: The only hardfork that bypasses witness majority voting. This was hardcoded specifically for the Steem→Hive fork — once current version is HF22, HF23 is forced regardless of witness votes.

2. **HF17 and HF18 activated simultaneously**: Same timestamp (2017-03-30 15:00 UTC), only 31 blocks apart. HF18 has no one-time migration and no conditional code — it's purely a version marker.

3. **HF1 vesting split bug lasted until HF28**: The `perform_vesting_share_split(1000000)` at HF1 introduced a rounding issue in power downs. The comment in HF28's `FIX_POWER_DOWN` explicitly states: "fix prolonged power down caused by disturbance introduced during HF1 (yes, that long ago)."

4. **HF28 uses a function for activation time**: Unlike all other hardforks which use compile-time constants, HF28's time comes from `next_hf_time()` — a regular function returning `1763557200` (Nov 19 2025). This may indicate the time was set after the code was written.

5. **HF28 block number is a round number**: Block 100,000,000 — the only hardfork with a "designed" block number (all others are determined by when witnesses actually activated them).

6. **HF9 contains a full account list**: 170+ compromised account names hardcoded in the source, including prominent accounts (`dan`, `ned`, `gtg`, `steemitblog`). This was a response to a security breach.

7. **HF22 contains the HF23 exclusion list**: The `get_steemit_accounts()` function was defined in `0_22.hf` but only called at HF23. This means the list was prepared one hardfork in advance.

8. **HF24 has dual time semantics**: Both `TIME` (earliest allowed) and `ACTUAL_TIME` (when it really happened). The gap is 8 days (Oct 6 → Oct 14), showing how long it took witnesses to approve.

9. **Version comparison ignores major version**: Comparing `0.20` and `1.20` would be equal. This was specifically designed for the HF24 transition where some witnesses hadn't upgraded from version 0.x.

10. **225 has_hardfork checks**: The conditional code is spread across 19 source files, with the heaviest concentration in social evaluators (40) and transfer evaluators (37), reflecting that comment/vote and transfer logic has changed the most over time.

## Economic Parameter Evolution

| Parameter | Pre-HF16 | HF16 | HF20 | HF21 | HF25 | HF26 |
|-----------|----------|------|------|------|------|------|
| Inflation | Fixed formula | 9.5%→0.95% | — | — | — | — |
| Power down | 104 weeks | 13 weeks | — | — | — | — |
| Reverse auction | — | — | 15 min | 5 min | **0 (disabled)** | — |
| HBD cap start | — | — | 9% | — | — | **20%** |
| HBD cap stop | — | — | 10% | — | — | **20%** |
| Content reward % | — | — | — | 65% | — | — |
| Curation % | — | — | — | 50% | — | — |
| Proposal fund % | — | — | — | 10% | — | — |
| Downvote pool % | — | — | — | 25% | — | — |
| Author reward curve | — | — | — | convergent_linear | **linear** | — |
| Curation reward curve | — | — | square_root | convergent_sqrt | **linear** | — |
| Witness composition | 19/1/1 | — | — | — | — | — |
| (from HF17) | 20/0/1 | — | — | — | — | — |

## Witness Schedule Composition History

| Period | Voted | Miner | Runner | Total |
|--------|-------|-------|--------|-------|
| Genesis–HF17 | 19 | 1 | 1 | 21 |
| HF17+ | 20 | 0 | 1 | 21 |

Mining was deprecated at HF13 (pow) and disabled at HF17 (pow2), so the miner slot was removed.

## Code References

| File | Purpose |
|------|---------|
| `libraries/protocol/hardfork.d/*.hf` | Hardfork definitions (28 files + preamble) |
| `libraries/chain/database_hardfork.cpp` | `init_hardforks()`, `process_hardforks()`, `apply_hardfork()`, `has_hardfork()` |
| `libraries/chain/include/hive/chain/detail/state/hardfork_property_object.hpp` | State tracking object |
| `libraries/protocol/include/hive/protocol/hardfork_block.hpp` | Mainnet activation block numbers |
| `libraries/protocol/include/hive/protocol/version.hpp` | Version and hardfork_version structs |
| `libraries/chain/witness_schedule.cpp:264-333` | Hardfork voting mechanism |
| `libraries/chain/database.cpp:61-71` | `next_hf_time()` for HF28 |
| `libraries/chain/database.cpp:1461-1540` | `clear_account()` / `clear_accounts()` for HF23 |
| `libraries/chain/database.cpp:1422-1458` | `restore_accounts()` for HF24 |
| `libraries/chain/database_dhf.cpp:146` | `remove_proposal_votes_for_accounts_without_voting_rights()` for HF28 |

## Activation Block Reference

| Hardfork | Block | Date (UTC) | Era |
|----------|-------|------------|-----|
| HF1 | 905,693 | 2016-04-25 | Steem |
| HF2 | 934,585 | 2016-04-26 | Steem |
| HF3 | 953,363 | 2016-04-27 | Steem |
| HF4 | 1,041,497 | 2016-05-01 | Steem |
| HF5 | 1,934,236 | 2016-05-31 | Steem |
| HF6 | 2,790,882 | 2016-06-30 | Steem |
| HF7 | 2,889,019 | 2016-07-04 | Steem |
| HF8 | 2,889,959 | 2016-07-04 | Steem |
| HF9 | 3,202,773 | 2016-07-14 | Steem |
| HF10 | 3,239,649 | 2016-07-15 | Steem |
| HF11 | 3,276,913 | 2016-07-17 | Steem |
| HF12 | 3,533,567 | 2016-07-26 | Steem |
| HF13 | 4,105,155 | 2016-08-15 | Steem |
| HF14 | 5,137,542 | 2016-09-20 | Steem |
| HF15 | 6,547,932 | 2016-11-08 | Steem |
| HF16 | 7,353,249 | 2016-12-06 | Steem |
| HF17 | 10,629,455 | 2017-03-30 | Steem |
| HF18 | 10,629,486 | 2017-03-30 | Steem |
| HF19 | 12,988,978 | 2017-06-20 | Steem |
| HF20 | 26,256,743 | 2018-09-25 | Steem |
| HF21 | 35,921,786 | 2019-08-27 | Steem |
| HF22 | 35,974,326 | 2019-08-29 | Steem |
| HF23 | 41,818,752 | 2020-03-20 | **Hive Fork** |
| HF24 | 47,797,680 | 2020-10-14 | Hive |
| HF25 | 55,235,767 | 2021-06-30 | Hive |
| HF26 | 68,676,505 | 2022-10-11 | Hive |
| HF27 | 69,050,084 | 2022-10-24 | Hive |
| HF28 | 100,000,000 | ~2025-11-19 | Hive |

## Discrepancies and Potential Issues

1. **HF28 block number (100,000,000) is symbolic**: Unlike all prior hardforks whose blocks were determined by when witnesses activated them, HF28 targets a round number. Since the code uses `next_hf_time()` for the time rather than a compile-time constant, there may be a coordination mechanism to ensure witnesses activate near this block.

2. **HF18 is effectively empty**: Same activation time as HF17, no one-time migration, no conditional code found. Its only purpose is advancing the version number. This may have been a planned hardfork whose features were merged into HF17.

3. **h23_balances persists permanently**: The `hardfork_property_object` stores HF23 cleared balances forever in shared memory, even though restoration happened at HF24. This is dead weight after HF24 but remains in the state.

4. **HF23 TAPOS reset was commented out**: The code to clear the TAPOS buffer (preventing replay attacks after the fork) is present but commented out with a note that it "breaks live 5M mirrornet instance." This means the Steem→Hive fork did NOT clear TAPOS — replay protection relied on the chain ID change at HF24 instead.

5. **Version comparison quirk**: The major version 0↔1 equivalence means `version(0, 28, 0)` would compare equal to `version(1, 28, 0)`. This could theoretically cause issues if a version 0.x node attempted to connect to the Hive network, but in practice such old nodes wouldn't be running HF28 code.

## Open Questions

1. **What prevents HF28 from activating before block 100,000,000?** The `next_hf_time()` function returns a fixed timestamp, but the block number is defined in `hardfork_block.hpp`. How are these two coordinated? Does the block number override the time for replay?

2. **Will HF28 actually activate at block 100M?** The code defines `HIVE_HARDFORK_1_28_BLOCK 100000000` in `hardfork_block.hpp`, but the activation depends on witness voting. The block number is only used for hardfork block lookups, not for activation.

3. **Are there any hardfork features that were planned but not shipped?** HF18 suggests this happens. Are there other "empty" hardfork slots?

4. **What happens to `h23_balances` storage?** Since restoration at HF24 only restored a subset, does the map still contain entries for unreStored accounts? Could a future hardfork restore more?
