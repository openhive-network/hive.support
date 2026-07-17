# Findings: Hardfork History — Evolution of Consensus Rules

## Summary

The Hive blockchain defines **28 hardforks** from genesis to the current code version. Hardforks 1–22 are pre-fork (inherited from Steem, major version 0); hardfork 23 is the chain-split that created Hive (still version 0.23 — the major version bump to 1.x came at HF24); hardforks 24–28 are Hive-native (major version 1). Activation is **time-based**: hardforks 1–4 activate purely when wall-clock time passes a fixed timestamp, while hardforks 5+ additionally require a **17-of-21 witness supermajority** signalling the same version+time (`HIVE_HARDFORK_REQUIRED_WITNESSES`, `config.hpp:231`). Each hardfork is defined in a `.hf` file under `libraries/protocol/hardfork.d/`, applied via `database::apply_hardfork()` (`database_hardfork.cpp:178`) with optional one-time state migrations, and gated throughout the codebase via `has_hardfork()` checks.

Two facts are central to understanding this part, and resolve most of the original open questions:

1. **The live consensus engine never consults block numbers.** `process_hardforks()` (`database_hardfork.cpp:114`) activates a hardfork when `next_hardfork_time <= head_block_time()` and the voted `next_hardfork` version exceeds the current one. The `HIVE_HARDFORK_*_BLOCK` constants in `hardfork_block.hpp` are **not referenced anywhere in `libraries/chain`** — they are consumed only by the offline `blockchain_converter` tool, which replays an existing block_log (for mirrornet/testnet generation) and therefore decides hardfork state by block height rather than by wall-clock/votes.

2. **HF28's activation time is a runtime value, not a compile-time constant.** `HIVE_HARDFORK_1_28_TIME` expands to `next_hf_time()` (`database.cpp:61`), which returns `1763557200` (2025-11-19 13:00:00 UTC) on mainnet but can be overridden by the `HIVE_HF28_TIME` environment variable.

The most consequential hardforks: **HF23** (the Steem→Hive fork) cleared Steemit/Tron-affiliated accounts and is the only hardfork **force-activated without a witness majority**; **HF20** introduced the Resource Credits system (largest feature addition and biggest one-time migration); **HF24** established Hive's identity (chain ID, treasury rename, account restoration); **HF28** is the most recent hardfork defined in the code.

**Software version vs. hardfork (1.28.7).** The mainnet `HIVE_BLOCKCHAIN_VERSION` is a *software* release identifier, distinct from the consensus hardfork version. It moved 1.28.6 -> 1.28.7 (`config.hpp:140`, mainnet branch; the testnet and mirrornet branches stay 1.28.6 at `:66`/`:135`) with **no new hardfork**: 1.28.7 is a network-robustness maintenance release (fork-tolerance + RocksDB info-LOG bounding). The latest consensus hardfork remains HF28. Because activation is time+vote gated and `libraries/chain` never consults the software version, bumping it cannot by itself activate a hardfork.

## Hardfork System Architecture

### How Hardforks Are Defined

Each hardfork lives in a `.hf` file in `libraries/protocol/hardfork.d/`:
- **Naming convention**: `{major}_{minor}.hf` (e.g., `0_17.hf`, `1_24.hf`)
- **Preamble**: `0-preamble.hf` defines `HIVE_NUM_HARDFORKS` — currently `28` for both mainnet and `USE_ALTERNATE_CHAIN_ID` (testnet) builds (`0-preamble.hf:15-20`)
- Files are concatenated into the generated `hardfork.hpp` at build time (the generated file carries an "automatically generated … modify the .hf files in hardfork.d instead" banner)

Each `.hf` file defines (e.g. `1_28.hf`):
```cpp
#define HIVE_HARDFORK_X_Y  <sequential_id>          // e.g., 28
#define HIVE_HARDFORK_X_Y_TIME  <unix_timestamp or fn>  // activation time
#define HIVE_HARDFORK_X_Y_VERSION hardfork_version(X, Y)
// Optional: sub-feature aliases (two styles, see below)
```

**Sub-feature aliases come in two styles**, both expanding to the parent hardfork number so that `has_hardfork()` can document *which specific fix* a code path implements:
- **Numbered (pre-fork, HF1–22)**: `HIVE_HARDFORK_0_X__NNN`, where `NNN` is the original GitHub issue number — e.g. `HIVE_HARDFORK_0_20__1449` (`0_20.hf:31`). Note the **double underscore**. HF23 (the chain-split) has no sub-feature aliases.
- **Named (Hive-native, HF24–28)**: `HIVE_HARDFORK_1_X_FEATURE_NAME` with a descriptive name — e.g. `HIVE_HARDFORK_1_27_FIX_TIMESHARE_WITNESS_SCHEDULING` (`1_27.hf:13`), `HIVE_HARDFORK_1_28_STABLE_VOTE` (`1_28.hf:19`). Note the **single underscore** before the name. A naive grep for `__` misses these.

**Testnet support**: Times are wrapped in `USE_ALTERNATE_CHAIN_ID` guards so a testnet can override the activation timestamp via `testnet_blockchain_configuration::configuration_data.get_hf_time(...)`.

### How Hardforks Activate (live consensus)

**Source**: `database::process_hardforks()` (`database_hardfork.cpp:114-144`); witness voting in `witness_schedule.cpp:262-350`.

The switch from time-only to vote-based activation is itself gated on the `HIVE_HARDFORK_0_5__54` sub-feature:

**Pre-HF5 (time only)** — `database_hardfork.cpp:133-141`:
```
while last_hardfork < HIVE_NUM_HARDFORKS
  AND _hardfork_versions.times[last_hardfork + 1] <= head_block_time()
  AND last_hardfork < HIVE_HARDFORK_0_5__54
  -> apply_hardfork(last_hardfork + 1)
```

**Post-HF5 (witness vote + time)** — `database_hardfork.cpp:121-132`:
```
while _hardfork_versions.versions[last_hardfork] < next_hardfork
  AND next_hardfork_time <= head_block_time()
  -> apply_hardfork(last_hardfork + 1)
```
Here `next_hardfork`/`next_hardfork_time` are set by the witness-vote tally, not by `process_hardforks` itself. Note the loop compares **versions** and gates on **time** — no block height is involved.

The voting tally runs during witness-schedule updates (`witness_schedule.cpp:264-350`):
1. For each scheduled witness, count its `running_version` and its `(hardfork_version_vote, hardfork_time_vote)` tuple (`:269-282`).
2. The highest version reached by ≥ `hardfork_required_witnesses` becomes `majority_version` (`:305-317`).
3. If any `(version, time)` tuple has ≥ `hardfork_required_witnesses` votes, set `next_hardfork`/`next_hardfork_time` to it (`:319-339`).
4. If no tuple still holds a supermajority, **reset** `next_hardfork = current_hardfork_version` (`:342-347`) — a pending hardfork is cancelled if witnesses drop below threshold.

`HIVE_HARDFORK_REQUIRED_WITNESSES = 17` (`config.hpp:231`), commented as "17 of the 21 dpos witnesses (20 elected and 1 virtual time) … guarantees 75% participation on all subsequent rounds."

**Special case — HF23 forced activation** (`witness_schedule.cpp:289-301`):
```cpp
if( hpo.current_hardfork_version == HIVE_HARDFORK_0_22_VERSION )
{
  if( hpo.next_hardfork != HIVE_HARDFORK_0_23_VERSION )
  {
    ilog("Forcing HF23 without need to have witness majority version");
    _hpo.next_hardfork = HIVE_HARDFORK_0_23_VERSION;
    _hpo.next_hardfork_time = fc::time_point_sec(HIVE_HARDFORK_0_23_TIME);
  }
}
else { /* normal vote tally */ }
```
This `if`/`else` is **exclusive**: once a node's current version is exactly `0.22`, the entire normal vote-tally branch is skipped and HF23 is the unconditional next hardfork. After HF23 applies (current becomes `0.23`), the `else` branch resumes and normal witness voting governs all subsequent hardforks. This is the only place witness consent is bypassed.

### How the blockchain_converter determines hardforks (offline tool)

**Source**: `programs/blockchain_converter/converter.cpp:283-312` and `:589-602`.

This is where `HIVE_HARDFORK_*_BLOCK` is actually used. The converter rewrites an existing block_log into mirrornet/testnet form; it cannot use wall-clock time or live witness votes, so it maps **block height → hardfork state**. It builds a compile-time array from the block constants via Boost preprocessor expansion (`:297-312`):
```cpp
const std::array< uint32_t, HIVE_NUM_HARDFORKS + 1 > blockchain_converter::hardfork_blocks = {
  /* HIVE_HARDFORK_0_1_BLOCK, … , HIVE_HARDFORK_1_28_BLOCK, */
  static_cast< uint32_t >(-1) // default for hardforks beyond those defined
};
```
and decides hardfork state by height (`:597-602`):
```cpp
bool blockchain_converter::has_hardfork( uint32_t hf, uint32_t block_num ) {
  if( hf > HIVE_NUM_HARDFORKS ) hf = HIVE_NUM_HARDFORKS + 1;
  return block_num > hardfork_blocks.at(hf - 1);
}
```
The trailing `2^32 - 1` default means any hardfork index beyond those defined "never activates" during conversion. The constants are split into two "chains" — major-0 hardforks 1–23 and major-1 hardforks 24–`HIVE_NUM_HARDFORKS` (`:286-294`).

**Implication**: the value `HIVE_HARDFORK_1_28_BLOCK = 100000000` (`hardfork_block.hpp:30`) is the converter's threshold for treating HF28 as active during a replay/conversion. For hardforks 1–27 the `_BLOCK` constants record the actual mainnet block at which each historically activated; for HF28 the value is a pre-chosen round number, since (unlike past hardforks) it was set before the fact. None of these constants affect live activation.

### The HF28 activation time and `next_hf_time()`

**Source**: `database.cpp:61-80`, `1_28.hf:4-10`.

`1_28.hf` declares `long next_hf_time();` and defines `HIVE_HARDFORK_1_28_TIME` as `next_hf_time()` on mainnet (or the testnet-config override under `USE_ALTERNATE_CHAIN_ID`). The function:
```cpp
long next_hf_time() {
  long hfTime =
#ifdef IS_TEST_NET
    1675818000; // Wednesday, February 8, 2023 1:00:00 AM
#else
    1763557200; // Wed Nov 19 2025 13:00:00 GMT+0000
#endif
  const char* value = getenv("HIVE_HF28_TIME");
  if (value) { hfTime = atol(value); /* logged */ }
  return hfTime;
}
```
`init_hardforks()` reads this into `_hardfork_versions.times[HIVE_HARDFORK_1_28]` (`database_hardfork.cpp:110`). This is why HF28 uses a *function* rather than a literal: it lets operators/tests override the activation time at runtime via the `HIVE_HF28_TIME` environment variable without recompiling. (The inline comment "Saturday, February 8, 2025…" at `1_28.hf:10` is stale; the actual values are in `next_hf_time()`.)

### Hardfork State Tracking

**Source**: `libraries/chain/include/hive/chain/detail/state/hardfork_property_object.hpp` (the top-level `hardfork_property_object.hpp` is just a one-line include of this `detail/state/` file).

The `hardfork_property_object` (singleton) stores:

| Field | Type | Purpose |
|-------|------|---------|
| `processed_hardforks` | `t_vector<time_point_sec>` | Timestamp of each applied hardfork (index = HF number); seeded with `genesis_time` at construction (`:23`) |
| `last_hardfork` | `uint32_t` | Current hardfork number |
| `current_hardfork_version` | `hardfork_version` | Current version (major.minor) |
| `next_hardfork` | `hardfork_version` | Next scheduled hardfork version |
| `next_hardfork_time` | `time_point_sec` | When the next hardfork activates |
| `h23_balances` | `t_flat_map<account_name_type, hf23_item>` | Balances cleared at HF23, kept for HF24 restoration (`:36`) |

- **`has_hardfork(n)`** = `processed_hardforks.size() > n` (`database_hardfork.cpp:146-149`).
- **`get_hardfork()`** = `processed_hardforks.size() - 1` (`:151-154`).
- **`apply_hardfork()`** appends to `processed_hardforks`, bumps `last_hardfork`, and asserts strict in-order application (`:519-527`).
- **`set_hardfork()`** (`:156-176`) is the testnet/debug path: for pre-HF5 it backdates `_hardfork_versions.times[i]`, for HF5+ it forces `next_hardfork`/`next_hardfork_time`, optionally applying immediately.

The object is `FC_REFLECT`-ed including `h23_balances` (`:53-55`), so it is serialized into shared memory / state snapshots.

### Version System and the major-0/1 equivalence

**Source**: `libraries/protocol/include/hive/protocol/version.hpp`.

`version` packs major.hardfork.release into a `uint32_t`: bits 31–24 major, 23–16 hardfork, 15–0 release (`:30-34`). `hardfork_version` zeroes the release (`v_num & 0xFFFF0000`, `:83`).

The comparison operators funnel through `version::_operator<op>(val, val_call)` (`:48-75`), which contains a special rule for the HF24 major-version bump so that nodes near the cutover don't reject each other (`:52-61`):
```cpp
auto _val = ( val & 0xFF000000 ) >> 24;          // operand's major
if( major_v() == 0 && _val == 1 )  val &= 0x00FFFFFF;   // branch A
else if( major_v() == 1 && _val == 0 ) val &= 0x01FFFFFF; // branch B
```

**This equivalence is non-commutative**, and the exact bit math matters:
- **Branch A** (`this` major 0, operand major 1): `val &= 0x00FFFFFF` clears the operand's major byte to `0x00`. Both sides are now major-0 → `version(0,N) == version(1,N)` is **true**.
- **Branch B** (`this` major 1, operand major 0): `val &= 0x01FFFFFF`. The operand's major byte is already `0x00`, and `0x00 & 0x01 == 0x00`, so the mask is **inert** — the operand stays major-0 while `this` stays major-1. Hence `version(1,N) == version(0,N)` is **false**, and a major-1 version always compares **strictly greater** than the same-numbered major-0 version. (To make them equal, branch B would have needed `val |= 0x01000000`, not `&=`.)

**Consumer**: the only consensus path that can see a cross-major comparison is the per-block assertion `witness.running_version >= current_hardfork_version` at `database.cpp:2286-2293` (active after HF5). There `this` is the witness's reported `running_version`:
- A witness reporting a major-0 `running_version` against a post-HF24 major-1 `current_hardfork_version` hits branch A → the major byte is neutralized and the comparison is decided on the hardfork number alone (the intended "don't reject during cutover" behavior).
- The symmetric case (major-1 running version vs a still-major-0 current version) hits branch B → `1.x` compares strictly greater than `0.y` → the `>=` assertion passes anyway.

Both directions yield "do not reject," so the inert branch B does not cause spurious block rejection at the HF24 boundary; the non-commutativity is a latent implementation quirk rather than an observable fault here.

### TIME vs ACTUAL_TIME

Three hardforks define an `ACTUAL_TIME` in addition to the scheduled `TIME`. The shared comment (`0_20.hf:4-18`, `1_24.hf:4-15`) explains: `TIME` is the *earliest* a hardfork was allowed (set in advance), while `ACTUAL_TIME` is the timestamp of the block where it *actually* took effect (knowable only after the fact, valid for mainnet only).

| HF | TIME | ACTUAL_TIME | Used? |
|----|------|-------------|-------|
| 19 | `1497970800` (2017-06-20 15:00:00) | `1497970809` (2017-06-20 15:00:**09**) | Yes — `HIVE_HF_19_SQRT_PRE_CALC = ACTUAL_TIME - HIVE_CASHOUT_WINDOW_SECONDS` (`0_19.hf:23-24`), consumed in the curation curve selection at `hive_evaluator_social.cpp:522` |
| 20 | `1537887600` (2018-09-25 15:00:00) | `1537887600` (identical) | **No** — `HIVE_HARDFORK_0_20_ACTUAL_TIME` is defined (`0_20.hf:25-28`) but is **not referenced in any `.cpp`/`.hpp`**; vestigial |
| 24 | `1601992800` (2020-10-06 14:00:00) | `1602703884` (2020-10-14 19:31:24) | Yes — selects the transaction signature-validation epoch at `full_transaction.cpp:479` |

Why `ACTUAL_TIME` is needed for HF24 (and was for HF20): transaction signature-validation rules are chosen by wall-clock timestamp **before** block application, where `has_hardfork()` state isn't available. `get_transaction_signature_validation_rules_at_time()` (`full_transaction.cpp:469-483`) returns `post_hf_1_24_rules` when `time > HIVE_HARDFORK_1_24_ACTUAL_TIME`, else `pre_hf_1_24_rules`. Using the scheduled `TIME` (Oct 6) instead of the real `ACTUAL_TIME` (Oct 14) would misvalidate every transaction in the 8-day gap during replay. All pre-1.24 signature behavior (including HF20's) is now folded into the single `pre_hf_1_24_rules` object, which is why HF20's own `ACTUAL_TIME` is no longer wired in.

## Current State

- **Highest hardfork defined**: HF28 (`HIVE_NUM_HARDFORKS = 28`, `0-preamble.hf:16-20`).
- **Current blockchain version**: 1.28.x.
- **HF28 activation time (code-defined)**: `next_hf_time()` = `1763557200` (2025-11-19 13:00:00 UTC) on mainnet, `1675818000` on testnet, overridable via `HIVE_HF28_TIME` (`database.cpp:61-80`). Activation additionally requires the HF5+ witness supermajority (`process_hardforks`, `database_hardfork.cpp:114`).
- **HF28 block constant**: `HIVE_HARDFORK_1_28_BLOCK = 100000000` (`hardfork_block.hpp:30`). Unlike the HF1–27 constants (which record actual historical activation blocks), this is a pre-chosen round number, and it is consumed **only by the `blockchain_converter`** (`converter.cpp:309`), never by live consensus.

## Hardfork Reference

### HF1 — Vesting Share Split
- **Block**: 905,693 — **Time**: 2016-04-25 17:30:00 UTC — **Version**: 0.1
- **One-time migration**: `perform_vesting_share_split(1000000)` (`database_hardfork.cpp:189-191`) — multiplied all VESTS amounts by 1,000,000
- **Conditional behavior**: permlink validation introduced (`validate_permlink_0_1`); curation weight calculation changed
- **Note**: introduced a rounding issue in power downs that persisted until HF28 fixed it (see HF28)

### HF2 — Witness Vote Retally
- **Block**: 934,585 — **Time**: 2016-04-26 18:00:00 UTC — **Version**: 0.2
- **One-time migration**: `retally_witness_votes()` (`database_hardfork.cpp:192-194`)
- **Conditional behavior**: max witness votes enforced; proxied witness vote adjustments; virtual schedule lap length change

### HF3 — Witness Vote Adjustment
- **Block**: 953,363 — **Time**: 2016-04-27 13:00:00 UTC — **Version**: 0.3
- **One-time migration**: `retally_witness_votes()` (`:195-197`)
- **Conditional behavior**: direct witness vote adjustment (vs proxied in HF2)

### HF4 — Virtual Schedule Fix
- **Block**: 1,041,497 — **Time**: 2016-05-01 — **Version**: 0.4
- **One-time migration**: `reset_virtual_schedule_time(*this)` (`:198-200`)
- **Conditional behavior**: virtual scheduled time overflow protection (clamped to `fc::uint128_max_value()`)

### HF5 — Witness Hardfork Voting
- **Block**: 1,934,236 — **Time**: 2016-05-31 17:00:00 UTC (`1464714000`) — **Version**: 0.5
- **One-time migration**: None (`:201-202`)
- **Key change**: **Introduced witness-based hardfork activation.** The `HIVE_HARDFORK_0_5__54` sub-feature is the literal gate that flips both `process_hardforks` (`database_hardfork.cpp:121` vs `:137`) and the witness-schedule tally (`witness_schedule.cpp:264`) from time-only to vote+time.
- **Sub-features (6)**: `__22, __54, __55, __56, __59, __62` (`0_5.hf:3-8`)

### HF6 — Reverse Auction & Rate Limiting
- **Block**: 2,790,882 — **Time**: 2016-06-30 14:00:00 UTC — **Version**: 0.6
- **One-time migration**: `retally_witness_vote_counts()` (`:203-205`)
- **Key changes**: reverse auction mechanism; 60-second post rate limit; self-vote detection (`__112`); order ID full 32-bit range
- **Sub-features (9)**: `#74, #78, #80, #101, #104, #112, #113, #114, #127`

### HF7 — Cashout Time & Upvote Lockout
- **Block**: 2,889,019 — **Time**: 2016-07-04 00:00:00 UTC — **Version**: 0.7
- **One-time migration**: None (`:206-207`)
- **Conditional behavior**: upvote lockout timer before payout (1 minute pre-HF17), gated via the HF7 sub-feature

### HF8 — Vote Count Retally
- **Block**: 2,889,959 — **Time**: 2016-07-04 01:00:00 UTC (1 hour after HF7) — **Version**: 0.8
- **One-time migration**: `retally_witness_vote_counts(true)` — with reset flag (`:208-210`)

### HF9 — Compromised Account Recovery
- **Block**: 3,202,773 — **Time**: 2016-07-14 00:00:00 UTC — **Version**: 0.9
- **One-time migration** (`database_hardfork.cpp:211-230`): iterate `hardfork9::get_compromised_accounts()` and reset each existing account's owner/active/posting authorities to `HIVE_HF_9_COMPROMISED_ACCOUNTS_PUBLIC_KEY_STR` (170+ accounts from a security breach, including prominent names)
- **Sub-feature**: `HIVE_HARDFORK_0_9__141` — liquidity weight calculation change

### HF10 — Liquidity Reward Period
- **Block**: 3,239,649 — **Time**: 2016-07-15 12:00:00 UTC — **Version**: 0.10
- **One-time migration**: `retally_liquidity_weight()` (`:231-233`)
- **Key change**: minimum liquidity reward period → 30 minutes (`HIVE_MIN_LIQUIDITY_REWARD_PERIOD_SEC_HF10`)

### HF11 — Recovery Account Restriction
- **Block**: 3,276,913 — **Time**: 2016-07-17 15:00:00 UTC — **Version**: 0.11
- **One-time migration**: None (`:234-235`)
- **Key change**: `HIVE_TEMP_ACCOUNT` rejected as recovery account for new accounts

### HF12 — Liquidity Rewards Removed
- **Block**: 3,533,567 — **Time**: 2016-07-26 15:00:00 UTC — **Version**: 0.12
- **One-time migration** (`database_hardfork.cpp:236-244`): `apply_hardfork_12_comment_cashout_fix()` then **clear the liquidity reward index** (`liquidity_reward_balance_idx.clear()`) — mechanism discontinued permanently
- **Sub-features (4)**: `#176, #177, #178, #179`
- **Conditional behavior**: post bandwidth limiting, frozen-discussion detection, comment editing restrictions, cashout time calculations

### HF13 — PoW Deprecation
- **Block**: 4,105,155 — **Time**: 2016-08-15 14:00:00 UTC — **Version**: 0.13
- **One-time migration**: None (`:245-246`)
- **Key change**: `pow` operation deprecated ("Use pow2 instead")
- **Sub-features (3)**: `#248, #256, #257`. (The bare `HIVE_HARDFORK_0_13` appears only in `init`/`case`; all runtime behavior is gated via these numbered sub-features.)

### HF14 — Witness Scheduling & Custom JSON
- **Block**: 5,137,542 — **Time**: 2016-09-20 15:00:00 UTC — **Version**: 0.14
- **One-time migration**: None (`:247-248`)
- **Key changes**: disabled witnesses skipped in schedule (#278); `custom_json` enabled (#317); `change_recovery_account` enabled (#324); account-creation-fee symbol canonicalization (#410); vote dust threshold (#259); witness shutdown threshold for missed blocks (#278)
- **Sub-features (11)**: `#143, #230, #239, #259, #278, #306, #307, #317, #324, #327, #410`

### HF15 — Posting Authority Verification
- **Block**: 6,547,932 — **Time**: 2016-11-08 16:00:00 UTC — **Version**: 0.15
- **One-time migration**: None (`:249-250`)
- **Key change**: authority account existence verification for posting authority updates (#465)

### HF16 — Power Down Reduction & Inflation Model
- **Block**: 7,353,249 — **Time**: 2016-12-06 16:00:00 UTC — **Version**: 0.16
- **One-time migration** (`database_hardfork.cpp:251-259`): trim feed history window to `HIVE_FEED_HISTORY_WINDOW`
- **Key changes**: **power down 104 weeks → 13 weeks** (`HIVE_VESTING_WITHDRAW_INTERVALS`); conversion delay → `HIVE_CONVERSION_DELAY`; Equihash PoW enabled (#551); **new inflation model** (9.5% start, −0.01% every 250k blocks, floor 0.95%); PoW difficulty adjusted
- **Sub-features (2)**: `#551, #562`

### HF17 — Reward Fund System & Mining End
- **Block**: 10,629,455 — **Time**: 2017-03-30 15:00:00 UTC (`1490886000`) — **Version**: 0.17
- **One-time migration** (`database_hardfork.cpp:260-296`): witness schedule → **20 voted + 0 miner + 1 runner** (was 19+1+1); create `reward_fund_object` ("post") with `HIVE_HF_17_RECENT_CLAIMS`; zero `total_reward_fund_hive` and `total_reward_shares2`; `apply_hardfork_17_comment_cashout_fix()`
- **Key changes**: comment depth limit 6 → 65,535; reward fund system; `pow2` mining **disabled** permanently (#770); upvote lockout → 12 hours
- **Sub-features (14)**: `#659, #733, #766, #767, #769, #770, #771, #772, #773, #774, #818, #869, #926, #900` (`0_17.hf:3-16`)
- **Hardcoded migration data**: `HIVE_HF_17_NUM_POSTS` (49,357), `HIVE_HF_17_NUM_REPLIES` (242,051), `HIVE_HF_17_RECENT_CLAIMS` (`0_17.hf:26-28`)

### HF18 — Empty Version Marker
- **Block**: 10,629,486 (31 blocks after HF17) — **Time**: 2017-03-30 15:00:00 UTC (`1490886000`, **identical to HF17**) — **Version**: 0.18
- **One-time migration**: None — `case HIVE_HARDFORK_0_18: break;` (`database_hardfork.cpp:297-298`)
- **Verified empty**: `HIVE_HARDFORK_0_18` appears in only four places, all in `database_hardfork.cpp` (the three `init_hardforks` lines `:79-81` and the empty `case` `:297`), plus the converter-only block constant. `0_18.hf` defines **no** sub-feature aliases and there is **no** `has_hardfork(HIVE_HARDFORK_0_18)` anywhere in the codebase. It is the **only** hardfork with neither a migration nor any behavioral consumer — a pure version-number bump.
- **Why a 31-block gap despite identical TIME**: because `process_hardforks` (post-HF5) gates on the voted `next_hardfork` *version*, not time. Both HF17 and HF18 satisfy the time check immediately, so HF18 applied only once witnesses re-signalled `0.18` after `0.17` — the gap reflects witness re-signalling latency, not a time delay.

### HF19 — Linear Rewards & Vote Cleanup
- **Block**: 12,988,978 — **Time**: 2017-06-20 15:00:00 UTC (`1497970800`); **ACTUAL_TIME** 2017-06-20 15:00:**09** (`1497970809`) — **Version**: 0.19
- **One-time migration** (`database_hardfork.cpp:299-335`): `vote_power_reserve_rate = HIVE_REDUCED_VOTE_POWER_RATE`; reward fund `recent_claims = HIVE_HF_19_RECENT_CLAIMS`, author curve → linear, curation curve → square_root; remove all zero-amount delegation objects; `remove_old_cashouts()`
- **Sub-features (9)**: `#822, #876, #971, #977, #987, #997, #1051, #1052, #1053` (`0_19.hf:10-18`)
- **ACTUAL_TIME use**: `HIVE_HF_19_SQRT_PRE_CALC = ACTUAL_TIME − HIVE_CASHOUT_WINDOW_SECONDS` (`0_19.hf:24`), the cutoff used to pick the curation curve at `hive_evaluator_social.cpp:522`

### HF20 — Resource Credits System
- **Block**: 26,256,743 — **Time**: 2018-09-25 15:00:00 UTC (`1537887600`); **ACTUAL_TIME** identical (`1537887600`) — **Version**: 0.20
- **One-time migration** (`database_hardfork.cpp:336-417`): set `delegation_return_period`, `reverse_auction_seconds` (HF20), `hbd_stop_percent`/`hbd_start_percent` (9%/10%), zero `available_account_subsidies`; multiply witness `account_creation_fee` by `HIVE_CREATE_ACCOUNT_WITH_HIVE_MODIFIER`; **initialize the entire RC system** — load `resource_parameters.json`, create `rc_resource_param_object`, `set_pool_params`, create `HIVE_RC_WINDOW_BUCKET_COUNT` usage buckets, `rc_pool_object`, two `rc_stats_object`s; set every account's `rc_adjustment = HIVE_RC_HISTORICAL_ACCOUNT_CREATION_ADJUSTMENT` and fill its RC manabar to max
- **Key changes**: RC system; `claim_account`/`create_claimed_account` (#1771); `account_create_with_delegation` deprecated (#1760); negative vesting withdrawal rejected; limit-order expiration capped at 28 days (#1449); mana-based delegation voting; authority size validation; exact account-creation fee
- **Sub-features (22)**: `__409, __1449, __1620, __1760, __1761, __1762, __1764, __1765, __1771, __1782, __1811, __1815, __1860, __1877, __1944, __2019, __2022, __2428, __2539, __2642, __2651, __SP190` (`0_20.hf:30-51`)
- Defines `ACTUAL_TIME` (= TIME) but it is unused in current C++ (see TIME vs ACTUAL_TIME)

### HF21 — Economic Improvement Proposal (EIP)
- **Block**: 35,921,786 — **Time**: 2019-08-27 15:00:00 UTC — **Version**: 0.21
- **One-time migration** (`database_hardfork.cpp:418-451`): `proposal_fund_percent = 10%`, `content_reward_percent = 65%`, `downvote_pool_percent = 25%`, `reverse_auction_seconds` (HF21); create treasury account if missing and `lock_account(get_treasury())`; reward fund → 50% curation, `convergent_linear` author curve, `convergent_square_root` curation curve, `HIVE_CONTENT_CONSTANT_HF21`, `HIVE_HF21_CONVERGENT_LINEAR_RECENT_CLAIMS`
- **Key changes**: convergent linear rewards; DHF / proposal system; separate downvote pool; treasury cannot receive vesting; `account_update2` (#3274); comment-edit throttle 1/block (#3313); power-down rounding fix
- **Sub-features (6)**: `#2203, #3004, #3274, #3313, #3336, #3343`
- **Stall block**: `HIVE_HF_21_STALL_BLOCK = 35,922,615` — downvote mana initialization workaround

### HF22 — Downvote Mana Fix
- **Block**: 35,974,326 — **Time**: 2019-08-29 15:00:00 UTC (`1567090800`) — **Version**: 0.22
- **One-time migration**: None (`:452-453`)
- **Key changes**: downvote mana proportional calculation fix (sub-feature `HIVE_HARDFORK_0_22__3485`, `0_22.hf:10`); delegation mana adjustments corrected
- **Carries the HF23 clear list**: `hardforkprotect::get_steemit_accounts()` is *defined* in `0_22.hf:19+` (**332 account-name entries**) but only *called* at HF23 — the exclusion list was prepared one hardfork in advance

### HF23 — The Steem→Hive Fork ⚡
- **Block**: 41,818,752 — **Time**: 2020-03-20 14:00:00 UTC (`1584712800`) — **Version**: 0.23
- **One-time migration** (`database_hardfork.cpp:454-470`): `clear_accounts(hardforkprotect::get_steemit_accounts())` — sweeps the 332 listed accounts' balances to the treasury (see "The HF23 Clear / HF24 Restore Mechanism")
- **FORCED without witness majority** — the unique override at `witness_schedule.cpp:289-301`
- **TAPOS reset present but commented out** (`database_hardfork.cpp:458-468`): the loop that would zero the `block_summary_index` block IDs (replay-attack mitigation) is disabled. The verbatim rationale: *"Reset TAPOS buffer to avoid replay attack - do it only for mainnet, since is far away from such blocks. … Skip it now since it is ineffective, but i.e. breaks live 5M mirrornet instance having applied all HFs."* So HF23 did **not** clear TAPOS; replay separation from Steem rests on the chain-ID change at HF24.
- **Significance**: the community fork away from Steemit Inc / Tron control

### HF24 — First Hive-Native Hardfork
- **Block**: 47,797,680 — **Time (scheduled)**: 2020-10-06 14:00:00 UTC (`1601992800`); **ACTUAL_TIME**: 2020-10-14 19:31:24 UTC (`1602703884`) — **Version**: 1.24 (first major version 1)
- **One-time migration** (`database_hardfork.cpp:471-552`):
  - `restore_accounts(hardforkprotect::get_restored_accounts())` — restores liquid balances for **51 accounts** (see below)
  - On mainnet, `set_chain_id(HIVE_CHAIN_ID)` = `beeab0de…` (skipped on testnet, `:474-478`)
  - **Treasury rename** `steem.dao` → `hive.fund`: keyed by `HIVE_HARDFORK_1_24_TREASURY_RENAME` (= 24, `1_24.hf:34`) and run **after** the hardfork is marked applied (`:529-544`), because `consolidate_treasury_balance()` depends on the HF already being recorded
  - `set_blockchain_config(...)` updated with the new treasury/chain-id (`:546-552`)
- **Key changes**: major version 0→1; signature-validation epoch switch keyed on `ACTUAL_TIME` (`full_transaction.cpp:479`); HIVE transfers to treasury auto-convert to HBD; delayed voting introduced; updating paid-out comment parameters forbidden; `update_proposal` enabled; HBD interest "touched" when clearing accounts

### HF25 — Recurrent Transfers & Linear Rewards
- **Block**: 55,235,767 — **Time**: 2021-06-30 14:00:00 UTC — **Version**: 1.25
- **One-time migration** (`database_hardfork.cpp:481-495`): reward fund both curves → **linear**; `reverse_auction_seconds = HF25` (0 / disabled); `early_voting_seconds = HF25` (24h); `mid_voting_seconds = HF25` (48h)
- **Key changes**: recurrent transfers; `collateralized_convert` (HIVE→HBD, 2× collateral); governance vote expiration 365 days; HBD hard cap no longer counts treasury balance (#140); proposal end-date extension; expired-proposal vote protection

### HF26 — Governance & Vote Improvements
- **Block**: 68,676,505 — **Time**: 2022-10-11 12:00:00 UTC — **Version**: 1.26
- **One-time migration** (`database_hardfork.cpp:496-509`): HBD cap → 20%/20%; **create a second `witness_schedule_object` (id=1)** as the "future" schedule (`copy_values_from` current; asserts id==1)
- **Key changes**: dust votes count as votes; no vote-edit penalty; authorization update twice/hour; old soft forks solidified (custom_binary disabled, `HIVE_CUSTOM_OP_DATA_MAX_LENGTH` enforced); future witness schedule always computed (gated by `HIVE_HARDFORK_1_26_FUTURE_WITNESS_SCHEDULE`, `witness_schedule.cpp:410`); fast-confirmation operation enabled

### HF27 — Timeshare Witness Scheduling Fix
- **Block**: 69,050,084 — **Time**: 2022-10-24 12:00:00 UTC (`1666612800`, 13 days after HF26) — **Version**: 1.27
- **One-time migration**: None (no explicit `case`; falls to `default: break`)
- **Key change**: fix timeshare-witness scheduling to restore pre-HF26 behavior. Gated by the **named** sub-feature `HIVE_HARDFORK_1_27_FIX_TIMESHARE_WITNESS_SCHEDULING` (`1_27.hf:13`), consumed at `witness_schedule.cpp:23` and `database_witness.cpp:71`, where it selects which `witness_schedule_object` (current id=0 vs future id=1) drives scheduling. (HF27 has no `__NNN` aliases — its single gate is the named flag, which is why it is *not* an empty hardfork despite the bare `HIVE_HARDFORK_1_27` appearing only in `init`.)

### HF28 — Power Down Fix, Stable Votes, Authority Improvements
- **Block constant**: `HIVE_HARDFORK_1_28_BLOCK = 100000000` (converter-only; see Current State) — **Time**: `next_hf_time()` = `1763557200` (2025-11-19 13:00:00 UTC) mainnet / `1675818000` testnet, overridable via `HIVE_HF28_TIME` — **Version**: 1.28
- **One-time migration**: `remove_proposal_votes_for_accounts_without_voting_rights()` only (`database_hardfork.cpp:510-514`). Every other HF28 feature below is **runtime-gated** via its named sub-feature, not a one-time migration.
- **Sub-features (10 named flags, `1_28.hf:14-33`)**:
  - `FIX_POWER_DOWN` — fixes the prolonged power-down rounding bug introduced by HF1's vesting split ("yes, that long ago")
  - `FIX_CANCEL_POWER_DOWN` — better "no-op" detection for cancel-power-down
  - `STABLE_VOTE` — use **max mana** (not current mana) for vote strength (issue #609)
  - `GLOBAL_WITNESS_PROPS` — max block size and HBD APR applied at schedule *activation* rather than creation (consumed at `witness_schedule.cpp:147,428`)
  - `EXPIRATION_TIME` — longer signature expiration (up to 24h) and transaction runtime (up to 1h)
  - `ALLOW_STRICT_AND_MIXED_AUTHORITIES` — accept only the required authority level; owner/active may be combined with posting in one transaction (consumed across 3 files)
  - `ALLOW_REDUNDANT_SIGNATURES` — redundant signatures permitted
  - `NO_DHF_HBD_IN_INFLATION` — exclude treasury HBD from virtual-supply inflation calc
  - `DONT_TRY_VOTE_FOR_NONEXISTENT_PROPOSAL` — reject voting on a nonexistent proposal
  - `DONT_TRY_REMOVE_NONEXISTENT_PROPOSAL` — reject removing a nonexistent proposal

## Hardfork-Conditional Code Map

> Line numbers below are at pinned commit `1584099c30`. Note the two alias styles: `__NNN` (numbered, HF1–22) and `_FEATURE_NAME` (named, HF24–28).

| Feature/Rule | Added/Changed At | Code Location |
|--------------|-----------------|---------------|
| Permlink validation | HF1 | `hive_evaluator_social.cpp` |
| Vesting share split (1M multiplier) | HF1 | `database_comment.cpp:612` |
| Max witness votes limit | HF2 | `hive_evaluator.cpp:280` |
| Virtual schedule lap length | HF2 | `database_witness.cpp:82` |
| Virtual schedule overflow fix | HF4 | `database_witness.cpp:88` |
| Witness hardfork voting (time→vote switch) | HF5 (`__54`) | `database_hardfork.cpp:121,137`; `witness_schedule.cpp:264` |
| Reverse auction mechanism | HF6 | `0_6.hf` |
| Post rate limiting (60s) | HF6 | `hive_evaluator_social.cpp:202` |
| Self-vote detection | HF6 | `hive_evaluator_social.cpp:571` |
| Order ID full range | HF6 | `database_market.cpp:52` |
| Upvote lockout (1min/12hr) | HF7/HF17 | `hive_evaluator_social.cpp:385` |
| Compromised account recovery | HF9 | `database_hardfork.cpp:211` |
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
| Curation curve sqrt pre-calc cutoff | HF19 (`__1052`) | `hive_evaluator_social.cpp:522` |
| Vote power reserve rate | HF19 | `database_hardfork.cpp:303` |
| Linear author, sqrt curation | HF19 | `database_hardfork.cpp:311` |
| RC system initialized | HF20 | `database_hardfork.cpp:366` |
| Account claim/create | HF20 | `hive_evaluator_account.cpp:404` |
| Delegation with creation deprecated | HF20 | `hive_evaluator_account.cpp:212` |
| Authority size validation | HF20 | `hive_evaluator_account.cpp:293` |
| Mana-based voting | HF20 | `hive_evaluator_transfer.cpp:696` |
| Convergent linear rewards | HF21 | `database_hardfork.cpp:440` |
| DHF / proposals | HF21 | `dhf_evaluator.cpp:36` |
| Downvote pool (25%) | HF21 | `database_hardfork.cpp:424` |
| Treasury locked | HF21 | `database_hardfork.cpp:438` |
| account_update2 enabled | HF21 | `hive_evaluator_account.cpp:362` |
| Downvote mana proportional calc | HF22 (`__3485`) | `hive_evaluator_social.cpp:665` |
| Steemit accounts cleared | HF23 | `database_hardfork.cpp:456` |
| HF23 forced (no witness vote) | HF23 | `witness_schedule.cpp:289` |
| Per-block running_version assert | HF5 (`__54`) | `database.cpp:2290` |
| Chain ID set to Hive | HF24 | `database_hardfork.cpp:477` |
| Accounts restored from HF23 | HF24 | `database_hardfork.cpp:473` |
| Treasury renamed (hive.fund) | HF24 (`_TREASURY_RENAME`) | `database_hardfork.cpp:529` |
| Sig-validation epoch switch | HF24 (`_ACTUAL_TIME`) | `full_transaction.cpp:479` |
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
| Future witness schedule (create) | HF26 | `database_hardfork.cpp:503` |
| Future witness schedule (use) | HF26 (`_FUTURE_WITNESS_SCHEDULE`) | `witness_schedule.cpp:410` |
| Timeshare witness fix | HF27 (`_FIX_TIMESHARE_WITNESS_SCHEDULING`) | `witness_schedule.cpp:23`; `database_witness.cpp:71` |
| Power down fix (HF1 bug) | HF28 (`_FIX_POWER_DOWN`) | `database_vesting.cpp:128` |
| Cancel power down fix | HF28 (`_FIX_CANCEL_POWER_DOWN`) | `hive_evaluator_transfer.cpp:349` |
| Stable vote (max mana) | HF28 (`_STABLE_VOTE`) | `hive_evaluator_social.cpp:659` |
| Global witness props timing | HF28 (`_GLOBAL_WITNESS_PROPS`) | `witness_schedule.cpp:147,428` |
| Extended tx expiration | HF28 (`_EXPIRATION_TIME`) | `database.cpp:2536` |
| Strict/mixed authorities | HF28 (`_ALLOW_STRICT_AND_MIXED_AUTHORITIES`) | `database.cpp:2612` |
| Redundant signatures | HF28 (`_ALLOW_REDUNDANT_SIGNATURES`) | `database.cpp:2613` |
| DHF HBD excluded from inflation | HF28 (`_NO_DHF_HBD_IN_INFLATION`) | `database.cpp:1724` |
| Proposal vote/remove validation | HF28 (2 flags) | `dhf_evaluator.cpp:177` |

## One-Time Migrations Summary

`apply_hardfork()` (`database_hardfork.cpp:178-555`) is a `switch` on the hardfork number. Most cases that change behavior do so via `has_hardfork()` elsewhere; the migrations below are the *one-time* state changes that run exactly once at activation:

| HF | Migration | Description |
|----|-----------|-------------|
| 1 | `perform_vesting_share_split(1000000)` | Multiply all VESTS by 1M |
| 2, 3 | `retally_witness_votes()` | Recount witness votes |
| 4 | `reset_virtual_schedule_time()` | Reset witness scheduling |
| 6 | `retally_witness_vote_counts()` | Recount vote counts |
| 8 | `retally_witness_vote_counts(true)` | Recount with reset |
| 9 | Reset compromised accounts | Set authorities to recovery key (170+ accounts) |
| 10 | `retally_liquidity_weight()` | Recount liquidity weights |
| 12 | Comment cashout fix + clear liquidity reward index | Permanently remove mechanism |
| 16 | Trim feed history window | Resize to new constant |
| 17 | Create reward fund, change witness schedule | Major structural change |
| 19 | Reset vote rate, reward curves, remove zero delegations, remove old cashouts | Economic reset |
| 20 | **Initialize entire RC system** + set every account's RC | Biggest one-time migration |
| 21 | Set EIP parameters, create+lock treasury, update reward fund | Economic overhaul |
| 23 | **Clear 332 Steemit/Tron accounts** | The Hive fork action |
| 24 | Restore 51 accounts, set chain ID, rename+consolidate treasury, update config | Hive identity established |
| 25 | Set linear reward curves, disable reverse auction, set voting windows | Reward simplification |
| 26 | Raise HBD cap, create future witness schedule (id=1) | Governance improvements |
| 28 | `remove_proposal_votes_for_accounts_without_voting_rights()` | Cleanup |

Hardforks **5, 7, 11, 13, 14, 15, 18, 22, 27** have no one-time migration (`break`/`default`). Of these, only **HF18** has no behavioral consumer at all; the rest gate runtime behavior through sub-feature aliases.

## The HF23 Clear / HF24 Restore Mechanism

This pair is the heart of the Steem→Hive transition, and the `h23_balances` lifecycle answers a long-standing open question.

**Clear (HF23)** — `clear_accounts()` → `clear_account()` (`database.cpp:1461-1643`):
- For each of the 332 listed accounts that exists, `clear_account()` removes delegations (in and out), pending escrows, limit orders, conversion/savings withdrawals; converts the account's VESTS to HIVE and sends that to the treasury; touches HBD to settle interest; and sweeps all liquid HIVE/HBD (balance + savings + rewards) to the treasury.
- Crucially, it records **only the liquid totals** via `gather_balance(account_name, vop.hive_transferred, vop.hbd_transferred)` (`:1640`). `hf23_item` holds just `{ hive_balance, hbd_balance }` (`hf23_helper.hpp:12-16`) — the HIVE that came from converting the account's VESTS (`total_hive_from_vests`) is **not** recorded per-account.

**Restore (HF24)** — `restore_accounts()` (`database.cpp:1422-1459`):
- For each of the **51** accounts in `get_restored_accounts()` (`0_23.hf:18-81`), look up its saved `hf23_item` and move those HIVE/HBD amounts back from the treasury, emitting a `hardfork_hive_restore_operation`.
- It **reads** `found->second` but **never erases** the entry from `h23_balances`.

**Consequences:**
- Restoration returns only the **liquid** balances that were swept; powered-up stake (VESTS, already converted to HIVE and pooled into the treasury at clear time) was not tracked per account and is not returned by this mechanism.
- `h23_balances` permanently retains entries for **all 332 cleared accounts** — both the 51 restored and the ~281 never restored — living in shared-memory state indefinitely (it is `FC_REFLECT`-ed into the `hardfork_property_object`). Because the data persists and `restore_accounts()` takes an arbitrary set, a future hardfork could in principle restore additional accounts by calling it with a new list.

**The 51 restored accounts** (`0_23.hf:22-77`), by category:
- **30** "errored accounts" (erroneously included in the HF23 clear list)
- **4** that won their airdrop appeal via proposal #104
- **17** that won their airdrop appeal via proposal #111

## Key Discoveries

1. **Live activation never uses block numbers.** `process_hardforks()` (`database_hardfork.cpp:114`) is purely version+time driven. `HIVE_HARDFORK_*_BLOCK` is referenced nowhere in `libraries/chain` — only in the offline `blockchain_converter` (`converter.cpp:309,597-602`), which must decide hardfork state by block height because it replays existing logs. This is the key to the "block 100M" confusion: that constant gates the converter, not the chain.

2. **HF28's activation time is overridable at runtime.** `HIVE_HARDFORK_1_28_TIME` = `next_hf_time()` (`database.cpp:61`), which returns `1763557200` on mainnet but honors the `HIVE_HF28_TIME` env var — the reason HF28 uses a function instead of a compile-time literal.

3. **HF23 forced activation is exclusive, not just additive.** When `current_hardfork_version == 0.22`, the witness-vote tally is entirely skipped and HF23 is forced (`witness_schedule.cpp:289-301`). Normal voting resumes only after HF23 is applied.

4. **HF18 is the single truly-empty hardfork.** Verified: zero sub-feature aliases, zero `has_hardfork()` consumers, empty `case` (`database_hardfork.cpp:297`). It shares HF17's exact timestamp; the 31-block gap is witness re-signalling latency, since post-HF5 activation keys on the voted version, not time.

5. **`h23_balances` is never erased and only ever held liquid balances.** HF24 restoration reads but does not delete entries (`database.cpp:1422-1459`), and only liquid HIVE/HBD was ever recorded (`gather_balance`, `:1640`). The map retains all 332 cleared accounts permanently.

6. **Corrected counts**: HF23 cleared **332** accounts (`get_steemit_accounts`, `0_22.hf:19+`); HF24 restored **51** = 30 errored + 4 (proposal #104) + 17 (proposal #111) (`0_23.hf:18-81`). (Earlier estimates of "~360" and "~47/29+4+14" were imprecise.)

7. **Three hardforks carry an `ACTUAL_TIME`, for two different reasons.** HF19's drives the curation-curve cutoff (`HIVE_HF_19_SQRT_PRE_CALC`, used at `hive_evaluator_social.cpp:522`); HF24's drives the signature-validation epoch (`full_transaction.cpp:479`); HF20's is defined but unused. `ACTUAL_TIME` is needed wherever behavior is selected by wall-clock timestamp before `has_hardfork()` state is available.

8. **The major-0/1 version equivalence is non-commutative.** Branch A (`version.hpp:58-59`) correctly neutralizes a major-1 operand when compared against a major-0 `this`; branch B (`:60-61`) uses `&= 0x01FFFFFF`, which is inert against an already-major-0 operand, so `version(1,N) == version(0,N)` is false while `version(0,N) == version(1,N)` is true. The lone consensus consumer (`database.cpp:2290`) is unaffected: both comparison directions resolve to "do not reject" at the HF24 cutover.

9. **Two distinct sub-feature alias conventions.** Pre-fork hardforks (HF1-22) use numbered `__NNN` (GitHub issue) aliases; Hive-native hardforks (HF24+) use named `_FEATURE_NAME` flags. HF27 (`_FIX_TIMESHARE_WITNESS_SCHEDULING`) and the ten HF28 flags are named — a grep that only matches `__` will under-count modern hardforks.

10. **HF1's rounding bug lasted to HF28.** `HIVE_HARDFORK_1_28_FIX_POWER_DOWN` (`1_28.hf:14`) explicitly fixes "prolonged power down caused by disturbance introduced during HF1 (yes, that long ago)."

11. **Treasury rename is deliberately ordered after the HF mark.** The `steem.dao → hive.fund` rename runs in a second block at `database_hardfork.cpp:529-544`, after `processed_hardforks` is updated, because `consolidate_treasury_balance()` assumes the hardfork is already recorded.

12. **HF23 did not reset TAPOS.** The replay-buffer reset is commented out (`database_hardfork.cpp:458-468`) as "ineffective" and because it "breaks live 5M mirrornet"; replay separation relied on the HF24 chain-ID change instead.

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
| Witness composition (voted/miner/runner) | 19/1/1 | — | — | — | — | — |
| (from HF17) | 20/0/1 | — | — | — | — | — |

## Witness Schedule Composition History

| Period | Voted | Miner | Runner | Total |
|--------|-------|-------|--------|-------|
| Genesis–HF17 | 19 | 1 | 1 | 21 |
| HF17+ | 20 | 0 | 1 | 21 |

Mining was deprecated at HF13 (`pow`) and disabled at HF17 (`pow2`), removing the miner slot (`database_hardfork.cpp:269-274`). Separately, the *scheduling* of the timeshare/runner witness changed twice in the Hive era: HF26 introduced a "future" `witness_schedule_object` (id=1, `:503-507`), and HF27 fixed timeshare scheduling by selecting between the current and future schedule objects (`witness_schedule.cpp:23`, `database_witness.cpp:71`).

## Code References

| File | Purpose |
|------|---------|
| `libraries/protocol/hardfork.d/*.hf` | Hardfork definitions (28 files + `0-preamble.hf`) |
| `libraries/chain/database_hardfork.cpp` | `init_hardforks()` (:24), `process_hardforks()` (:114), `has_hardfork()` (:146), `get_hardfork()` (:151), `set_hardfork()` (:156), `apply_hardfork()` (:178), `gather_balance()` (:562) |
| `libraries/chain/include/hive/chain/detail/state/hardfork_property_object.hpp` | State-tracking object (incl. `h23_balances`) |
| `libraries/chain/include/hive/chain/util/hf23_helper.hpp` | `hf23_item { hive_balance, hbd_balance }` |
| `libraries/protocol/include/hive/protocol/hardfork_block.hpp` | Block constants (converter-only) |
| `libraries/protocol/include/hive/protocol/version.hpp` | `version` / `hardfork_version`; major-0/1 equivalence (:48-75) |
| `libraries/chain/witness_schedule.cpp:262-350` | Witness-vote tally + HF23 force |
| `libraries/chain/database.cpp:61-80` | `next_hf_time()` (HF28 time + env override) |
| `libraries/chain/database.cpp:1422-1459` | `restore_accounts()` (HF24) |
| `libraries/chain/database.cpp:1461-1643` | `clear_accounts()` / `clear_account()` (HF23) |
| `libraries/chain/database.cpp:2286-2293` | Per-block `running_version >= current_hardfork_version` assert |
| `libraries/chain/full_transaction.cpp:469-483` | Signature-validation epoch keyed on `HIVE_HARDFORK_1_24_ACTUAL_TIME` |
| `programs/blockchain_converter/converter.cpp:283-312, 589-602` | Block-height-based `has_hardfork()` for offline conversion |
| `libraries/chain/database_dhf.cpp` | `remove_proposal_votes_for_accounts_without_voting_rights()` (HF28) |
| `libraries/protocol/include/hive/protocol/config.hpp:231` | `HIVE_HARDFORK_REQUIRED_WITNESSES = 17` |

## Activation Block Reference

For HF1–27, the block below is the actual mainnet block at which the hardfork activated, as recorded in `hardfork_block.hpp` (a historical record, not an activation threshold — activation is time/vote-based). For HF28 the listed value is the converter constant, *not* an activation block.

| Hardfork | Block (`hardfork_block.hpp`) | Date (UTC) | Era |
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
| HF24 | 47,797,680 | 2020-10-14 (ACTUAL_TIME) | Hive |
| HF25 | 55,235,767 | 2021-06-30 | Hive |
| HF26 | 68,676,505 | 2022-10-11 | Hive |
| HF27 | 69,050,084 | 2022-10-24 | Hive |
| HF28 | 100,000,000 (converter constant) | TIME = 2025-11-19 (`next_hf_time()`) | Hive |

## Discrepancies and Potential Issues

1. **HF28 block number (100,000,000) is converter-only, not an activation parameter.** Unlike HF1–27, whose `_BLOCK` constants record the actual mainnet activation block, HF28's is a pre-chosen round number consumed solely by `blockchain_converter` (`converter.cpp:309`). Live activation is governed entirely by `next_hf_time()` + witness supermajority. There is no coordination mechanism tying live activation to block 100,000,000 — the two are independent.

2. **HF18 is effectively empty (verified).** No migration, no sub-feature aliases, no `has_hardfork(HIVE_HARDFORK_0_18)` anywhere — only `init_hardforks` registration and an empty `case`. Same timestamp as HF17; purely a version-number bump.

3. **`h23_balances` persists permanently.** HF24 restoration reads without erasing (`database.cpp:1422-1459`), so the `hardfork_property_object` carries all 332 cleared-account balance records in shared memory indefinitely — dead weight after HF24, but it also leaves the door open for a future restore.

4. **HF23 TAPOS reset is commented out.** The block-summary reset (`database_hardfork.cpp:458-468`) is disabled because it was "ineffective" and "breaks live 5M mirrornet." So the Steem→Hive fork did not clear TAPOS; replay separation relied on the HF24 chain-ID change.

5. **Version comparison is non-commutative across the major-0/1 boundary.** `version.hpp:60-61`'s `val &= 0x01FFFFFF` is inert (it cannot set a major bit via AND), so the equivalence only fully works when the major-0 operand is on the left. `version(0,N) == version(1,N)` is true but `version(1,N) == version(0,N)` is false. The lone consensus consumer (`database.cpp:2290`, witness `running_version` check) is unaffected because both directions resolve to "do not reject" at the HF24 cutover; the quirk is latent, not an observed fault. (Out of scope for this part: a full audit of every `version` comparison across plugins/p2p to confirm none depends on the broken branch — a candidate for a dedicated zoom.)

6. **HF20 defines an unused `ACTUAL_TIME`.** `HIVE_HARDFORK_0_20_ACTUAL_TIME` (`0_20.hf:25-28`) has no `.cpp`/`.hpp` consumer; the pre-1.24 signature behavior it once keyed is now bundled in `pre_hf_1_24_rules`. Harmless but vestigial.

## Open Questions

All four prior open questions are now resolved:

1. **~~What prevents HF28 from activating before block 100,000,000? How are the block number and time coordinated?~~** *Resolved.* Nothing about block 100M participates in live activation. Live activation is purely `next_hardfork_time <= head_block_time()` plus the voted `next_hardfork` version (`database_hardfork.cpp:114-132`). The `HIVE_HARDFORK_1_28_BLOCK` constant is consumed only by the offline `blockchain_converter` (`converter.cpp:309,597-602`); it and the time are not coordinated because they serve different tools (offline replay vs. live chain).

2. **~~Will HF28 activate at block 100M? Is the block number used for activation?~~** *Resolved.* The block number is never used for live activation (no `libraries/chain` reference). Per task constraints, no claim is made here about whether any block has been reached or whether HF28 is active — only that the code ties activation to `next_hf_time()` + witness vote, not to a block height.

3. **~~Are there other "empty" hardfork slots besides HF18?~~** *Resolved.* No. HF18 is the unique hardfork with neither a one-time migration nor any sub-feature/`has_hardfork()` consumer. The other migration-less hardforks (5, 7, 11, 13, 14, 15, 22, 27) all gate runtime behavior through aliases — including HF27, whose single gate is the *named* flag `_FIX_TIMESHARE_WITNESS_SCHEDULING`.

4. **~~What happens to `h23_balances` after HF24? Could a future hardfork restore more?~~** *Resolved.* `restore_accounts()` reads but never erases (`database.cpp:1431-1457`), so the map permanently retains all 332 cleared accounts (only the 51 in `get_restored_accounts()` were credited back, and only their liquid HIVE/HBD — vesting-derived HIVE was never recorded per account). The data persistence means a future hardfork could call `restore_accounts()` with a new set to restore additional accounts.

**Remaining (minor / out of scope):** A complete audit of every `version`/`hardfork_version` comparison outside `libraries/chain` (plugins, p2p handshake, wallet) to confirm none relies on the non-commutative branch-B path (Discrepancy #5) would belong in a dedicated zoom rather than this part.
