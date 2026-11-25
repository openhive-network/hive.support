# Findings: Economic Model — Rewards, Inflation, Interest, Conversions

## Summary

The Hive economic model is a complex system of interrelated mechanisms governing inflation, reward distribution, asset conversion, interest, and governance funding. All economic activity is driven by a per-block inflation schedule that creates new HIVE, which is then split among content creators, curators, witnesses (block producers), vesting holders, and the Decentralized Hive Fund (DHF/treasury). This document captures the **exact code behavior** verified from the C++ source at release 1.28.8 (`274384a8a`).

Key characteristics:
- Inflation starts at 9.78% and decreases 0.01% every 250,000 blocks until it reaches the 0.95% floor at block 220,750,000 (~year 2037); inflation never fully stops
- Rewards are split: 65% content rewards, 15% vesting fund, 10% DHF, 10% witness pay (post-HF21)
- Content rewards use linear author and curation curves since HF25 (convergent curves HF21–HF25, linear/square-root HF19–HF21, quadratic/bounded before HF19)
- 50% of content rewards go to curators, 50% to authors (post-HF21)
- HBD earns interest on savings balances only (post-HF25); interest is simple within each accrual period and compounds only when the balance is touched more than 30 days after the last payment; rate set by witness median (bounded 0-100% APR)
- Two conversion mechanisms exist: HBD->HIVE (3.5-day delay, no fee) and HIVE->HBD collateralized (3.5-day delay, 5% fee, 200% collateral)
- HBD supply is managed through print rate throttling (cliff at 20% since HF26) and a hard price cap at 30% of market cap
- Author/curation/beneficiary rewards are paid into **pending reward balances** that must be claimed via `claim_reward_balance_operation`; claimed reward VESTS get immediate governance power (no 30-day delay)

---

## Inflation Schedule

### Formula
Defined in `database::process_funds()` at `database.cpp:1725` (active branch gated on HF16, `database.cpp:1731`).

```
inflation_rate = max(HIVE_INFLATION_RATE_START_PERCENT - floor(head_block_num / HIVE_INFLATION_NARROWING_PERIOD),
                     HIVE_INFLATION_RATE_STOP_PERCENT)

new_hive_per_block = virtual_supply * inflation_rate / (HIVE_100_PERCENT * HIVE_BLOCKS_PER_YEAR)
```

Exact code (`database.cpp:1737-1742`): `current_inflation_rate = std::max(978 - head_block_num/250000, 95)` in basis points. The code comment (`database.cpp:1733-1735`) states: "At block 7,000,000 have a 9.5% instantaneous inflation rate, decreasing to 0.95% at a rate of 0.01% every 250k blocks. This narrowing will take approximately 20.5 years and will complete on block 220,750,000."

### Constants
| Constant | Value | Meaning |
|----------|-------|---------|
| `HIVE_INFLATION_RATE_START_PERCENT` | 978 (9.78%) | Starting inflation rate (calibrated so block 7,000,000 = 9.50%) |
| `HIVE_INFLATION_RATE_STOP_PERCENT` | 95 (0.95%) | Floor inflation rate |
| `HIVE_INFLATION_NARROWING_PERIOD` | 250,000 blocks | Blocks per 0.01% reduction |
| `HIVE_BLOCKS_PER_YEAR` | 10,512,000 (365×24×60×60/3) | Blocks per year at 3s intervals (`config.hpp:60`) |

(`config.hpp:253-255`)

### Timeline
- **Effective start**: rate formula yields 9.78% at block 0; the constant was chosen to anchor 9.50% at block 7,000,000
- **Floor**: solving `978 - floor(block/250000) = 95` gives `floor(block/250000) = 883`, so the first block at 0.95% is block **883 × 250,000 = 220,750,000** (≈ 21 years of 3s blocks from genesis 2016-03-24, i.e. ~2037)
- **Inflation does not stop** — it continues at 0.95% of virtual supply indefinitely after the floor
- **Reduction**: 0.01 percentage points every 250,000 blocks (~8.68 days)

### Virtual Supply Basis (HF28 change)
Post-HF28 (`HIVE_HARDFORK_1_28_NO_DHF_HBD_IN_INFLATION`, `database.cpp:1745-1759`), the inflation base **excludes treasury HBD** from the virtual supply calculation:

```cpp
// HF28+ (database.cpp:1747-1754):
FC_ASSERT( exchange_rate.is_null() == false );   // exchange_rate = get_hbd_price(), the current median price (database.cpp:1729)
HBD_asset hbd_supply_without_treasury = current_hbd_supply - treasury.hbd_balance;
virtual_supply_without_treasury = hbd_supply_without_treasury * exchange_rate + current_supply;
new_hive = virtual_supply_without_treasury * current_inflation_rate / (100% * blocks_per_year);

// Pre-HF28 (database.cpp:1758):
new_hive = props.virtual_supply * current_inflation_rate / (100% * blocks_per_year);
```

This prevents treasury accumulation from inflating the inflation base.

### Distribution Splits
The newly created HIVE is split according to percentages stored in `dynamic_global_property_object` (`database.cpp:1761-1764`):

```cpp
content_reward  = new_hive * content_reward_percent  / 100%   // moved into the reward fund by pay_reward_funds(); since 1.28.8 also before HF17
vesting_reward  = new_hive * vesting_reward_percent  / 100%
dhf_new_funds   = new_hive * proposal_fund_percent   / 100%
witness_reward  = new_hive - content_reward - vesting_reward - dhf_new_funds  // remainder
```

| Era | Content | Vesting | DHF | Witness (remainder) |
|-----|---------|---------|-----|---------------------|
| Pre-HF21 (HF16+) | 75% | 15% | 0% | 10% |
| HF21+ | 65% | 15% | 10% | 10% |

Defaults in `dynamic_global_property_object` are the HF16 values (`detail/state/global_property_object.hpp:275-277`); HF21 changed them (`database_hardfork.cpp:417-418`). Constants: `HIVE_CONTENT_REWARD_PERCENT_HF16/HF21`, `HIVE_VESTING_FUND_PERCENT_HF16`, `HIVE_PROPOSAL_FUND_PERCENT_HF0/HF21` (`config.hpp:256-261`).

**DHF funds are converted to HBD** at the current median price and deposited to the treasury account (`database.cpp:1794`, `:1800-1802`); the HBD amount is also accumulated in `dgpo.dhf_interval_ledger` (`database.cpp:1795`) for hourly reporting (see DHF section). Since 1.28.8 the supply bookkeeping goes through the dgpo's own methods (`database.cpp:1785-1796`; Part 05, section dynamic_global_property_object (Singleton)): `issue_HIVE(new_hive + dhf_new_funds)` adds that amount to `current_supply` and `virtual_supply`, the vesting reward moves into `total_vesting_fund_hive`, and `convert_HIVE_to_HBD`, called so that it leaves `virtual_supply` unchanged, takes the DHF slice off `current_supply` and adds its HBD to `current_hbd_supply` (`global_property_object.hpp:295-302`, `:335-348`). Net effect: `current_supply += content + vesting + witness` (the DHF slice is *not* added to HIVE supply, it becomes HBD), `current_hbd_supply += hbd_issued` (the DHF slice converted, named `new_hbd` at 1.28.7), `virtual_supply += content + vesting + witness + dhf_new_funds`; the `new_hive` passed to `issue_HIVE` is that sum, reassigned at `database.cpp:1783`, so with the weighted witness reward it can differ from the inflation amount computed at `:1754` / `:1758`.

### Witness Reward Distribution
Witness pay is NOT evenly split. Each block's witness receives a weighted share (`database.cpp:1766-1781`):

```cpp
witness_reward *= HIVE_MAX_WITNESSES;  // 21
if (timeshare) witness_reward *= wso.timeshare_weight;   // 5
else if (miner) witness_reward *= wso.miner_weight;      // 1
else if (elected) witness_reward *= wso.elected_weight;  // 1
witness_reward /= wso.witness_pay_normalization_factor;  // 25 on mainnet
```

Weights (`detail/state/witness_objects.hpp:191-194`): `elected_weight = 1`, `timeshare_weight = 5`, `miner_weight = 1`, `witness_pay_normalization_factor = 25`. The normalization factor is recomputed during schedule updates as `elected_weight*num_elected + miner_weight*num_miners + timeshare_weight*num_timeshare` (`witness_schedule.cpp:367-370`). Since HF17 the schedule is 20 elected + 0 miners + 1 timeshare (`config.hpp:223-225`; pre-HF17: 19 + 1 + 1, `config.hpp:219-221`), so the factor is 20*1 + 1*5 = 25:
- An **elected** witness block pays `21×1/25 = 0.84×` the nominal per-block witness slice
- A **timeshare** (backup) witness block pays `21×5/25 = 4.2×` nominal — compensating for being scheduled far less often

Witness reward is paid as **vesting (HP)** via `create_vesting2()`, emitting a `producer_reward_operation` virtual op (`database.cpp:1805-1814`).

### Pre-HF16 Inflation (Legacy)
Before HF16, there was no single inflation rate; each reward category was computed from its own APR against virtual supply (`database.cpp:1816-1866`):
- `HIVE_CONTENT_APR_PERCENT` = 3875 (38.75%), `HIVE_CURATE_APR_PERCENT` = 3875, `HIVE_PRODUCER_APR_PERCENT` = 750 (7.5%), `HIVE_POW_APR_PERCENT` = 750, `HIVE_LIQUIDITY_APR_PERCENT` = 750 (`config.hpp:330-334`)
- Per-block amounts via `calc_percent_reward_per_block<>()` from `compound.hpp`, using precomputed fixed-point multipliers (`HIVE_APR_PERCENT_MULTIPLY_PER_BLOCK` / `..._SHIFT_PER_BLOCK = 87`, `config.hpp:304-316`) that approximate continuous compounding of the annual rate
- **Vesting multiplier**: `vesting_reward = (content + curation + witness_pay) × 9` (`database.cpp:1828`) — i.e. 9 HIVE went to the vesting fund for every 1 HIVE paid out, the source of Steem's early hyperinflationary vesting
- No vesting rewards at all before `HIVE_START_VESTING_BLOCK` = 7 days of blocks = 201,600 (`database.cpp:1825`, `protocol/config.hpp:63`)
- Liquidity rewards (7.5% APR, hourly, minimum `HIVE_MIN_LIQUIDITY_REWARD` = 1,200.000 HIVE per hour) were paid to the top internal-market liquidity provider; **disabled at HF12** — `get_liquidity_reward()` returns 0 (`database.cpp:1888-1889`) and the index was cleared at HF12 (`database_hardfork.cpp:245-248`)

---

## Reward System

### Reward Pool

The reward pool is tracked in `reward_fund_object` (`detail/state/reward_fund_object.hpp`). There is a single reward fund (`HIVE_POST_REWARD_FUND_NAME` = "post"). Since 1.28.8 it exists from genesis: `init_genesis()` creates it with an empty balance and asserts that it gets id 0 (`database_init.cpp:258-262`); its `reward_balance` receives the content reward from the first block on (see Funding below), and before HF17 its `recent_claims` holds the undecayed running total of rshares2 (`database.cpp:1687-1699`). HF17 sets `last_update` and, outside testnet (`IS_TEST_NET`) builds, seeds `recent_claims` with `HIVE_HF_17_RECENT_CLAIMS`; the balance carries over (`database_hardfork.cpp:281-287`). At 1.28.7 HF17 created the fund, moving the dgpo's `total_reward_fund_hive` into it and zeroing that field and `total_reward_shares2`, which held these values before HF17; 1.28.8 removed both fields from the dgpo (Part 05, sections reward_fund_object (Singleton) and dynamic_global_property_object (Singleton)).

**Fields and their defaults at creation** (`reward_fund_object.hpp:66-70`):
- `reward_balance` — HIVE available to pay out
- `recent_claims` - uint128_t; before HF17 the undecayed rshares2 total (since 1.28.8, see above), from HF17 the recent rshare claims, which decay over time; seeded with `HIVE_HF_17_RECENT_CLAIMS` at HF17 and re-seeded at HF19 and HF21 to match curve changes, outside testnet builds (see Reward Curves)
- `content_constant` — default `HIVE_CONTENT_CONSTANT_HF0` = 2,000,000,000,000 (`config.hpp:298`); HF21 set it to `HIVE_CONTENT_CONSTANT_HF21` — the **same numeric value** (`config.hpp:264`)
- `percent_curation_rewards` - default 25%; **50% since HF21** (`database_hardfork.cpp:437`)
- `percent_content_rewards` — 100% (the fund takes the whole content slice)
- `author_reward_curve` — default `quadratic`; see curve evolution below
- `curation_reward_curve` — default `bounded_curation`

**Funding**: Each block, `pay_reward_funds()` (`database.cpp:1953-1975`) moves the per-block content reward out of the HIVE that `process_funds()` has just issued into `reward_balance`, and asserts that the fund took all of it. Since 1.28.8 both inflation branches call it (`database.cpp:1799`, `:1836`), so the fund is fed from the first block; at 1.28.7 it was called from HF17 on, and before that the content reward went to the dgpo's `total_reward_fund_hive`:
```cpp
r = content_reward * itr->get_percent_content_rewards() / HIVE_100_PERCENT;
rfo.access_reward_balance().transfer_from( reward_balance, r );   // reward_balance: the issued HIVE; then FC_ASSERT( used_rewards == content_reward )
```

**Claims decay** (`database_comment.cpp:397-413`): performed at the start of every `process_comment_cashout()` since HF17:
```cpp
// HF19+: 15-day decay; HF17–HF19: 30-day decay
if (now - last_update <= decay_time)
    rfo.recent_claims -= (rfo.recent_claims * elapsed_seconds) / decay_time_seconds;
else
    rfo.recent_claims = 0;   // only possible if chain were inactive longer than the decay window
rfo.last_update = now;
```

| Constant | Value |
|----------|-------|
| `HIVE_RECENT_RSHARES_DECAY_TIME_HF19` | 15 days (`config.hpp:297`) |
| `HIVE_RECENT_RSHARES_DECAY_TIME_HF17` | 30 days (`config.hpp:296`) |

**Claims snapshot** (HF17+): before paying anything, all comments cashing out this block have their curve-evaluated claims added to `recent_claims` (`database_comment.cpp:433-444`); the code comment explains: "This ensures equal satoshi per rshare payment". Payouts in the block are then computed against this snapshot and the fund balance taken at the start (`database_comment.cpp:463-464`). Since 1.28.8, before and after HF17, the fund's whole balance is moved into a temporary balance at the start (`database_comment.cpp:415`, `:425`; balance classes: Part 01, section tiny_asset and tiny_price), each payout takes exactly what it pays out of it (curator claims `database_comment.cpp:169-170`, beneficiaries `:246-247`, the author share `:282-283`), and at the end the rest goes back into `reward_balance` and, from HF17, `recent_claims` is written back (`database_comment.cpp:503-509`); at 1.28.7 the fund was reduced by the summed `claimed_reward` of the payouts (`reward_balance -= hive_awarded`). Either way only actually-claimed rewards leave the fund.

### Reward Curves

Six curves are defined in the `curve_id` enum (`protocol/misc_utilities.hpp`), implemented in `util/reward.cpp:34-75`:

| Curve | Formula (s = content_constant) | Code |
|-------|-------------------------------|------|
| `quadratic` | `(rshares + s)² - s²` | `reward.cpp:40-46` |
| `bounded_curation` | `(rshares << 64) / (2s + rshares)` | `reward.cpp:47-53` |
| `linear` | `rshares` | `reward.cpp:54-55` |
| `square_root` | `√rshares` (approx) | `reward.cpp:57-58` |
| `convergent_linear` | `((rshares + s)² - s²) / (rshares + 4s)` | `reward.cpp:60-65` |
| `convergent_square_root` | `rshares / √(rshares + 2s)` | `reward.cpp:66-71` |

**Evolution of curves (corrected)**: the curve changes happened at HF19, not HF17. The reward fund keeps its *default* curves until HF19 (since 1.28.8 it exists from genesis with them; at 1.28.7 HF17 created it with them), and they match pre-HF17 behavior (`comment_reward_context` defaults to `quadratic` + `HIVE_CONTENT_CONSTANT_HF0`, `util/reward.hpp:31-32`):

| Era | Author Curve | Curation Curve | Source |
|-----|-------------|----------------|--------|
| Genesis-HF19 | quadratic | bounded_curation | fund defaults `reward_fund_object.hpp:69-70`; votes read the fund's curation curve only from HF17 (before that the vote evaluator used hardcoded formulas), and from HF17 votes on comments created in the 7 days before HF19 already used `square_root` (`hive_evaluator_social.cpp:519-541`, `hardfork.d/0_19.hf:24`) |
| HF19 | **linear** | **square_root** | `database_hardfork.cpp:306-307` |
| HF21 | convergent_linear | convergent_square_root | `database_hardfork.cpp:438-439` |
| HF25 | **linear** | **linear** | `database_hardfork.cpp:480-481` |

HF19 ("linear rewards") also reduced `vote_power_reserve_rate` from 40 to 10 (`database_hardfork.cpp:298`, `HIVE_INITIAL_VOTE_POWER_RATE = 40`, `HIVE_REDUCED_VOTE_POWER_RATE = 10`, `config.hpp:385-386`). **The mainnet value of `dgpo.vote_power_reserve_rate` has been 10 ever since**: no later hardfork changes it.

`recent_claims` was seeded when the decaying model started at HF17 (`HIVE_HF_17_RECENT_CLAIMS`) and re-seeded at the HF19 and HF21 curve changes (`HIVE_HF_19_RECENT_CLAIMS`, `HIVE_HF21_CONVERGENT_LINEAR_RECENT_CLAIMS`), each time only outside testnet builds (`database_hardfork.cpp:284-286`, `:303-305`, `:441-443`), so existing posts wouldn't be over/under-paid relative to the new curve; the HF25 switch to linear curves did not re-seed it (`database_hardfork.cpp:476-490`).

### Individual Comment Reward Calculation

From `get_rshare_reward()` in `util/reward.cpp:7-32`, computed in 256-bit arithmetic:

```
claim  = evaluate_reward_curve(comment.net_rshares, author_curve, content_constant)
claim  = claim * reward_weight / HIVE_100_PERCENT          // reward.cpp:18
payout = reward_fund_balance * claim / total_recent_claims  // u256 math, reward.cpp:20-22
if to_hbd(payout) < HIVE_MIN_PAYOUT_HBD (0.020 HBD): payout = 0   // dust, reward.cpp:24-25, reward.hpp:44-47
payout = min(payout, to_hive(max_accepted_payout))          // reward.cpp:27-29
```

- `reward_weight` comes from the comment's `comment_cashout_ex_object` when it has one (comments created before HF19) and is 100% otherwise (`database_comment.cpp:205-208`); it is below 100% only for root posts created between HF12 and HF17, where it implemented the 4-posts-per-day frequency penalty (`hive_evaluator_social.cpp:220-226`, `HIVE_POST_AVERAGE_WINDOW`/`HIVE_POST_WEIGHT_CONSTANT`, `protocol/config.hpp:246-247`)
- **Maximum payout**: `max_accepted_payout` defaults to `asset(1000000000, HBD_SYMBOL)` = **1,000,000.000 HBD** (`protocol/hive_operations.hpp:139`). It is an HBD-denominated cap converted to HIVE at the current median and applied to the **total** (pre-split) reward. It can be lowered (never raised) via `comment_options_operation`. Setting it to 0 declines payout entirely.
- Comments with `net_rshares <= 0` at cashout receive nothing (`database_comment.cpp:201`)

### Author vs Curator Split

```cpp
// database_comment.cpp:224-225
curation_tokens = reward_tokens * get_curation_rewards_percent() / HIVE_100_PERCENT;
author_tokens = reward - curation_tokens;
```

`get_curation_rewards_percent()` (`database.cpp:1943-1951`): post-HF17 reads `reward_fund.percent_curation_rewards`; HF8-HF17 hardcoded 25%; pre-HF8 50%.

| Era | Curation % | Author % |
|-----|-----------|----------|
| Pre-HF8 | 50% | 50% |
| HF8–HF21 | 25% | 75% |
| HF21+ | **50%** | **50%** |

### Curation Reward Distribution

Curators receive rewards proportional to their `vote_weight` share of the comment's `total_vote_weight`. From `pay_curators()` in `database_comment.cpp:121-191`:

```cpp
// iteration sorted by weight descending, ties by voter id ascending (cmp struct, database_comment.cpp:124-133)
for each vote:
    claim = max_rewards * vote.weight / total_vote_weight   // uint128 math, line 162
    if claim > 0:                                            // truncated-to-zero claims stay unclaimed
        unclaimed_rewards -= claim
        create_vesting2(voter, claim, is_reward=HF17+)       // claim moved out of the fund's temp balance (since 1.28.8); paid as HP into pending rewards
        voter.curation_rewards += claim                      // lifetime counter (HIVE-equivalent)
        emit curation_reward_operation                       // since 1.28.8 its VESTS are also summed into the caller's curators_vesting_payout
max_rewards -= unclaimed_rewards    // by-reference: caller's curation_tokens shrinks to what was actually paid
return unclaimed_rewards
```

**If the author disabled curation rewards** (`allow_curation_rewards = false`): `pay_curators()` zeroes both `unclaimed_rewards` and `max_rewards` (`database_comment.cpp:139-143`). The curation share is then **neither paid to curators nor forwarded to the author** (even pre-HF20, since the returned remainder is 0) — it simply never leaves the reward fund.

**Unclaimed curation remainder**: `cashout_comment_helper` adds the remainder to `author_tokens` only when `forward_curation_remainder` is true, which is `!has_hardfork(HF20__1877)` (`database_comment.cpp:232-235`, `database_comment.cpp:446`). Post-HF20 the remainder is excluded from `claimed_reward = author_tokens + curation_tokens` (`database_comment.cpp:238`), and since only `claimed_reward` leaves the fund (since 1.28.8 the curator claims, beneficiary shares and author share are moved out of the temporary balance holding the fund's HIVE, `database_comment.cpp:169-170`, `:246-247`, `:282-283`, and the rest returns to the fund, `:508`; at 1.28.7 the fund was reduced by the summed `claimed_reward`), **unclaimed curation stays in the reward pool for future payouts**.

**Vote weight calculation** (`hf20_vote_evaluator`, `hive_evaluator_social.cpp:751-839`):

The curation weight of a vote is the increment it causes in the curve-evaluated cumulative positive rshares: `W(R_N) - W(R_{N-1})` where `R` is `vote_rshares` (sum of positive rshares so far) and `W` is the **curation** curve (`hive_evaluator_social.cpp:788-797`). With the linear curve (HF25+) this is simply the vote's own positive rshares. Weight is only granted when `rshares > 0 && allows_curation_rewards() && curation_percent > 0` (`hive_evaluator_social.cpp:782-783`); downvotes get weight 0 and earn nothing.

**Early voting penalty** (HF25+, replaces reverse auction; `hive_evaluator_social.cpp:812-824`):
- Votes in the first `early_voting_seconds` (24h): full weight
- Votes from 24–72h (`early + mid_voting_seconds`): weight ÷ 2 (`phase_1_factor`, "chosen empirically")
- Votes after 72h: weight ÷ 8 (`phase_2_factor`)

| Constant | Value |
|----------|-------|
| `HIVE_EARLY_VOTING_SECONDS_HF25` | 24 hours (`config.hpp:182`) |
| `HIVE_MID_VOTING_SECONDS_HF25` | 48 hours (`config.hpp:183`) |

**Penalty semantics differ fundamentally from the reverse auction** (key discovery):
- **Reverse auction era** (pre-HF25, `hive_evaluator_social.cpp:800-811`): `max_vote_weight` (added to `total_vote_weight`) was set to the **full** weight, while the vote's stored weight was discounted by `elapsed/auction_window`. The gap between the two became *unclaimed* curation: burned back to the pool post-HF20, forwarded to the author pre-HF20.
- **HF25+ phases** (`hive_evaluator_social.cpp:818-823`): the division by 2/8 is applied **before** `max_vote_weight` is set, so the discounted weight is what enters `total_vote_weight`. The penalty **redistributes proportionally to all other curators** instead of being burned. Post-HF25, unclaimed curation arises only from truncation dust and disabled-curation posts.

**Pre-HF25 reverse auction windows** (`dgpo.reverse_auction_seconds`, set per hardfork):

| Hardfork | Window | Source |
|----------|--------|--------|
| HF6 | 30 minutes | `config.hpp:240`, dgpo default |
| HF20 | 15 minutes | `database_hardfork.cpp:337` |
| HF21 | 5 minutes | `database_hardfork.cpp:420` |
| HF25 | **0 (disabled)** | `protocol/config.hpp:181`, `database_hardfork.cpp:485` |

**Vote edits and curation**: before HF26, editing an existing vote put it through the `else` branch that accumulates rshares but grants `max_vote_weight = 0` — **edited votes forfeited all curation weight** (`hive_evaluator_social.cpp:833-836`). `HIVE_HARDFORK_1_26_NO_VOTE_EDIT_PENALTY` routes edits through the normal weight path (`hive_evaluator_social.cpp:757-761`). Related historical limits noted in code comments: one vote per block per user existed HF11–HF26 (`hive_evaluator_social.cpp:629`); a 5-edit-per-vote limit existed until HF28 (`hive_evaluator_social.cpp:644`).

Curation rewards are paid as HP into the **pending reward balance** (`create_vesting2(..., is_reward = HF17+)`) and must be claimed (see Claiming Rewards).

### How Votes Map to rshares (HF20+)

From `hf20_vote_evaluator()` in `hive_evaluator_social.cpp:607-854`:

```
// HF28+ "stable votes" (hive_evaluator_social.cpp:661-664):
used_mana = effective_vesting_shares * abs_weight * 86400 / HIVE_100_PERCENT

// Pre-HF28 upvote (hive_evaluator_social.cpp:682):
used_mana = voting_manabar.current_mana * abs_weight * 86400 / HIVE_100_PERCENT

// Pre-HF28 downvote with downvote pool (hive_evaluator_social.cpp:665-679):
used_mana = max(downvote_mana * 100% / downvote_pool_percent, voting_mana) * abs_weight * 86400 / 100%
            // i.e. downvote mana is scaled up to "full pool" terms before comparison;
            // HF22__3485 fixed an overflow in this formula (cast placement)

max_vote_denom = vote_power_reserve_rate * HIVE_VOTING_MANA_REGENERATION_SECONDS   // 10 * 432,000 = 4,320,000
used_mana = ceil(used_mana / max_vote_denom)            // ceiling division, line 688

abs_rshares = used_mana - HIVE_VOTE_DUST_THRESHOLD      // 50,000,000; floor at 0 (lines 708-709)
```

With `vote_power_reserve_rate = 10` (since HF19) and 86400/4,320,000 = 1/50: **a 100% vote consumes 2% of current mana**, hence the code comment "it is not possible to burn all mana in one 50 vote transaction due to round up" (`hive_evaluator_social.cpp:700`). At 20%/day regeneration, ten 100% votes per day are sustainable. Under HF28 stable votes, rshares derive from `effective_vesting_shares` (own + received - delegated, minus the next power-down installment while a power-down is active, `detail/state/account_object.hpp:111-117`), so vote strength no longer sags as mana depletes, but the same `used_mana` is still checked against and deducted from the manabar (`hive_evaluator_social.cpp:701-703`, `:718-745`).

| Constant | Value |
|----------|-------|
| `HIVE_VOTING_MANA_REGENERATION_SECONDS` | 432,000 (5 days) (`config.hpp:239`) |
| `HIVE_VOTE_DUST_THRESHOLD` | 50,000,000 (`config.hpp:243`) |
| `HIVE_INITIAL_VOTE_POWER_RATE` / `HIVE_REDUCED_VOTE_POWER_RATE` | 40 / **10 (current since HF19)** (`config.hpp:385-386`) |
| `HIVE_UPVOTE_LOCKOUT_SECONDS` | 43,200 (12 hours) (`config.hpp:160`) |

**Downvote mana pool** (HF21+): `dgpo.downvote_pool_percent = 25%` (`HIVE_DOWNVOTE_POOL_PERCENT_HF21`, set at `database_hardfork.cpp:419`). Downvotes consume downvote mana first; any excess spills into upvote mana (`hive_evaluator_social.cpp:720-742`). The downvote mana requirement is slightly higher than necessary, which prevents zero-stake accounts from downvoting; per the code comment the effect might be unintentional but is kept on purpose (`hive_evaluator_social.cpp:691-693`).

**Lockout**: since HF20 there is no lockout; in the last 12 hours before cashout the rshares of every vote, downvotes included, scale linearly to 0 (`hive_evaluator_social.cpp:711-716`). Historical: before HF20 a vote that raised the voter's rshares on the comment was rejected in the last minute before payout from HF7 (`protocol/config.hpp:159`) and in the last 12 hours from HF17 (`hive_evaluator_social.cpp:384-390`).

**Dust vote bookkeeping**: in this evaluator, until `HIVE_HARDFORK_1_26_DUST_VOTE_FIX`, a vote whose rshares truncate to 0 did not mark the comment as voted on (`hive_evaluator_social.cpp:753`; the pre-HF20 evaluator marks every vote, `:465`, `:578`); a voted-on comment can no longer get beneficiaries, and its `comment_options` can no longer set `allow_votes` or `allow_curation_rewards` to false or lower `max_accepted_payout` (`hive_evaluator_social.cpp:121`, `:156-157`). `net_votes` counts every vote regardless of its rshares (`detail/state/comment_object.hpp:181-193`). Other vote preconditions: voter must not have declined voting rights (`hive_evaluator_social.cpp:615`), comment must allow votes for upvotes (`:619`), vote weight != 0 for new votes (`:640`), re-vote with identical weight rejected (`:645`).

### Cashout Process

**Cashout window**: 7 days after post creation (`HIVE_CASHOUT_WINDOW_SECONDS`, `config.hpp:156`). Historical windows (`config.hpp:154-157`): before HF17 the cashout time was not fixed at creation: from HF12 a new root post started 12 hours ahead (`HIVE_CASHOUT_WINDOW_SECONDS_PRE_HF17`; earlier posts and all replies started with none, `hive_evaluator_social.cpp:249-254`), and votes re-averaged it toward now + 24 hours (`HIVE_CASHOUT_WINDOW_SECONDS_PRE_HF12`), toward now + 12 hours only between HF12 and HF13 (`hive_evaluator_social.cpp:435-439`); HF12-HF17 also had a **second cashout** 30 days after the first ( `HIVE_SECOND_CASHOUT_WINDOW`, `config.hpp:157`, applied at `database_comment.cpp:348-349`); HF17+ = single 7-day cashout. No payouts at all before HF7 (`HIVE_HARDFORK_0_7_FIRST_CASHOUT_TIME` gate, `database_comment.cpp:383-384`).

**Step-by-step cashout** (from `process_comment_cashout()` `database_comment.cpp:378-510` and `cashout_comment_helper()` `database_comment.cpp:193-376`):

1. **Decay recent claims** on the reward fund (HF17+; linear decay over `HIVE_RECENT_RSHARES_DECAY_TIME_HF17` = 30 days, 15 days since HF19, `database_comment.cpp:404-410`, see Reward Pool); since 1.28.8 the fund's whole balance is also moved, before and after HF17, into the temporary balance the payouts draw from (`database_comment.cpp:397-427`)
2. **Snapshot**: add curve-evaluated claims of all comments cashing out this block to `recent_claims` (HF17+)
3. For each comment with `cashout_time <= now`: post-HF17 against the snapshotted fund state; pre-HF17 whole discussions, root and all replies, are paid together against the current pool state (since 1.28.8: the fund's undecayed `recent_claims` and the balance not yet paid out in the block, `database_comment.cpp:477-496`; at 1.28.7: the dgpo's `total_reward_shares2` and `total_reward_fund_hive`):
   a. Compute total HIVE reward via `get_rshare_reward()` (dust check, `max_accepted_payout` cap)
   b. Split into curation tokens (50%) and author tokens (50%)
   c. **Pay curators** (see above); unclaimed remainder stays in fund (HF20+)
   d. **Pay beneficiaries** (`database_comment.cpp:242-279`): each gets `author_tokens * weight / 100%` (computed *before* deduction, on the post-curation author share)
      - Treasury beneficiary (HF21+, `database_comment.cpp:252-262`): paid **entirely in HBD** at median price (the dgpo's `convert_HIVE_to_HBD`: HIVE burned, HBD minted), directly to balance: `payout_must_be_claimed = false`
      - Regular beneficiary (HF20+, `database_comment.cpp:263-270`): same HBD/HP split as the author (`benefactor_balance * percent_hbd / (2*100%)` through `award_hbd(..., is_reward=true)`, named `create_hbd` at 1.28.7); pre-HF20: all HP
      - Emits `comment_benefactor_reward_operation` per beneficiary
   e. **Pay author** (`database_comment.cpp:281-300`): `author_tokens -= total_beneficiary`, then
      - `hbd_hive = author_tokens * percent_hbd / (2 * 100%)` — with default `percent_hbd = 10000`, **half** the author share is the "HBD portion", half is vested
      - HBD portion goes through `award_hbd()` (`create_hbd()` at 1.28.7; print-rate split, below); HP portion through `create_vesting2()`
      - `author.posting_rewards += author_tokens` lifetime counter (`database_comment.cpp:318-321`)
   f. Virtual ops: `curation_reward_operation` (per curator), `comment_benefactor_reward_operation` (per beneficiary), `author_reward_operation` (includes the `curators_vesting_payout` total for the convenience of downstream apps like hivemind, code comment `database_comment.cpp:227-230`; since 1.28.8 that total is the sum of the `reward` of the same payout's `curation_reward_operation`s, `database_comment.cpp:171-177`, `:231-232`; for how 1.28.7 differed see Part 02, section Reward/Payout Virtual Operations, the `author_reward_operation` row (ID 51)), `comment_reward_operation` (totals in HBD terms), `comment_payout_update_operation`
4. **All `comment_vote_object`s are removed** after payout (`database_comment.cpp:365-372`)
5. **Remove** the `comment_cashout_object` (HF19+, `database_comment.cpp:471-475`); pre-HF19 it was kept with updated bookkeeping (pre-HF17 second cashout scheduling, `database_comment.cpp:330-358`)
6. **Write back** fund state: `recent_claims` (HF17+) and, since 1.28.8, the unspent rest of the temporary balance back into `reward_balance` (`database_comment.cpp:503-509`); at 1.28.7 `reward_balance -= hive_awarded`

All author/curator/regular-beneficiary payouts since HF17 (`HIVE_HARDFORK_0_17__659`) land in **pending reward balances**, not liquid/vesting balances.

### Claiming Rewards (`claim_reward_balance_operation`)

`claim_reward_balance_evaluator` (`hive_evaluator_transfer.cpp:667-721`):
- Claims any portion of `reward_hive_balance`, `reward_hbd_balance`, `reward_vesting_balance` (bounds-checked, `hive_evaluator_transfer.cpp:677-682`)
- HIVE/HBD move to liquid balances; VESTS move to `vesting_shares` and the matching HIVE from the account's `reward_vesting_hive` into `total_vesting_fund_hive`, while `total_vesting_shares` grows and `pending_rewarded_vesting_{shares,hive}` shrink by the same amounts, written directly rather than through the dgpo's supply methods (`hive_evaluator_transfer.cpp:701-718`); partial VESTS claims move HIVE proportionally (`hive_evaluator_transfer.cpp:684-689`)
- Because pending rewarded vesting sits outside the main pools, the **reward vesting price** `(total_vesting_shares + pending_rewarded_vesting_shares) / (total_vesting_fund_hive + pending_rewarded_vesting_hive)` (`get_reward_vesting_share_price()`, `detail/state/global_property_object.hpp:109-113`) is used when granting vested rewards (`:371-375`), and granting does not move the regular vesting price; claiming adds the VESTS and their HIVE to the main pools together, so the regular price moves only as far as the account's reward VESTS-to-HIVE ratio differs from it
- **Claimed reward VESTS receive governance power immediately**: `adjust_proxied_witness_votes(acnt, op_reward_vests)` is called directly (`hive_evaluator_transfer.cpp:720`); the 30-day delayed-voting mechanism does **not** apply to claimed rewards (it covers only `transfer_to_vesting` and the VESTS that a power-down auto-vest route moves to another account, `database_vesting.cpp:213-217`; see Key Discovery 12)

### HBD Print Rate and Author Payout

`award_hbd()` (named `create_hbd()` at 1.28.7) at `database.cpp:957-1005` controls what fraction of an "HBD portion" is actually paid as HBD vs HIVE:

```cpp
to_hbd  = hbd_print_rate * hive_for_hbd / 100%   // database.cpp:973
to_hive = hive_for_hbd - to_hbd
hbd     = to_hbd * exchange_rate                  // get_hbd_price() = current median; the dgpo's convert_HIVE_to_HBD burns the HIVE, mints the HBD (database.cpp:977-980)
// is_reward (author and beneficiary payouts): HBD and to_hive go to the reward balances, else to the liquid balances (database.cpp:985-994)
```

**If the median price feed is null** (never published; only true before block ~933,600 historically, per the code comment at `database.cpp:2910`), the entire amount is paid as HIVE (`database.cpp:996-1000`).

The `hbd_print_rate` is recomputed in `update_virtual_supply()` (`database.cpp:2905-2926`):
- If HBD% ≥ `hbd_stop_percent`: print_rate = 0 (no HBD printed)
- If HBD% ≤ `hbd_start_percent`: print_rate = 100%
- Between: `print_rate = (stop - percent_hbd) * 100% / (stop - start)` (`database.cpp:2923`)

| Era | Start % | Stop % | Source |
|-----|---------|--------|--------|
| HF14 | 2% | 5% | `config.hpp:338-339`, dgpo defaults |
| HF20 | 9% | 10% | `config.hpp:340-341`, `database_hardfork.cpp:338-339` |
| HF26 | **20%** | **20%** | `config.hpp:342-343`, `database_hardfork.cpp:495-496` |

Since HF26 start == stop, the interpolation branch is dead code: printing is binary — 100% below 20% HBD market-cap share, 0% at or above it.

### Beneficiaries

Set via the `comment_payout_beneficiaries` extension of `comment_options_operation`; stored in the `comment_cashout_object`.

**Protocol validation** (`comment_payout_beneficiaries::validate()`, `protocol/hive_operations.cpp:150-175`):
- At least 1, fewer than `HIVE_BENEFICIARY_LIMIT = 128` (`config.hpp:426`) — the limit exists so the count serializes in one byte
- Accounts in strictly ascending order (no duplicates), each weight ≤ 100%, running sum ≤ 100% (10,000 bps)

**Evaluator rules** (`comment_options_extension_visitor`, `hive_evaluator_social.cpp:118-135`):
- Beneficiaries can be set **only once** per comment (`hive_evaluator_social.cpp:120`) and **only before the comment is marked as voted on** (`has_votes()`, `:121`; see Dust vote bookkeeping)
- Each beneficiary account must exist (`hive_evaluator_social.cpp:131`)
- **Soft-fork limit of `HIVE_MAX_COMMENT_BENEFICIARIES = 8`** (`config.hpp:272`): enforced only when `_db.is_in_control()` (`hive_evaluator_social.cpp:123-124`), i.e. when the node validates a new transaction or produces a block (`database.hpp:176`); a node accepts blocks from other producers containing up to 127 (comment: "check below moved from witness plugin, it remains softfork check")

**Other `comment_options_operation` rules** (`comment_options_evaluator`, `hive_evaluator_social.cpp:138-173`): all options are one-way ratchets (`allow_curation_rewards` and `allow_votes` can only be disabled, `max_accepted_payout` and `percent_hbd` can only be lowered, `:159-162`); an operation that sets `allow_curation_rewards` or `allow_votes` to false or lowers `max_accepted_payout` requires the comment not to be marked as voted on yet (`has_votes()`, `:156-157`), while lowering `percent_hbd` alone does not; since HF24 the operation is rejected entirely on paid-out comments (`:150`).

At payout, each beneficiary receives `author_tokens * weight / HIVE_100_PERCENT` deducted from the author share (see Cashout step d).

---

## HBD Interest

### Mechanism

HBD interest uses a **dollar-seconds accumulator** (`protocol/hbd_interest.hpp:9-23`):

```cpp
hbd_seconds += hbd_balance * elapsed_seconds_since_last_update;
if (hbd_seconds != 0 && do_evaluation) {
    interest  = hbd_seconds / HIVE_SECONDS_PER_YEAR;   // integer division FIRST
    interest *= hbd_interest_rate;                      // then rate (bps)
    interest /= HIVE_100_PERCENT;
}
```

**This is NOT continuous compound interest.** Within an accrual period the formula is simple interest on the time-weighted balance. Compounding happens only when an interest payment is added to the balance and the accumulator resets, and that happens **lazily**, only when the balance is next modified (`adjust_balance`/`adjust_savings_balance`) more than 30 days after the previous payment. Consequences:
- An account that touches its savings monthly gets ~monthly compounding
- An account that never touches its savings accrues *simple* interest indefinitely (the accumulator keeps growing) and receives it as one lump on the next touch — the interim interest never compounds
- Interest paid is added after the accumulator is evaluated, so a payment doesn't earn interest within its own period

### Accrual sites

| Balance | Code | Active when |
|---------|------|-------------|
| Liquid HBD (`hbd_balance`) | `adjust_balance(HBD)` `database.cpp:3242-3267` | **pre-HF25 only** (`has_hardfork(HIVE_HARDFORK_1_25) == false`, `database.cpp:3242`) |
| Savings HBD (`savings_hbd_balance`) | `adjust_savings_balance(HBD)` `database.cpp:3312-3345` | always |
| Savings HIVE | `adjust_savings_balance(HIVE)` `database.cpp:3304-3310` | **never earns interest** (no accrual logic) |

Payment condition: `(now - last_interest_payment) > HIVE_HBD_INTEREST_COMPOUND_INTERVAL_SEC` (strictly greater; 30 days, `config.hpp:362`). On payment: balance += interest, `hbd_seconds = 0`, `last_interest_payment = now`, `current_hbd_supply += interest`, `virtual_supply += interest * median_price` (since 1.28.8 through the dgpo's `issue_HBD`, `global_property_object.hpp:312-322`), and an `interest_operation` vop is emitted with a boolean flag distinguishing liquid (`true`) vs savings (`false`) payout (`database.cpp:3251-3266`, `:3326-3341`).

**Truncation/dust hazard**: `hbd_seconds` is divided by `HIVE_SECONDS_PER_YEAR` (31,536,000) *before* the rate is applied, and the accumulator is zeroed **even when the computed interest truncates to 0** (`database.cpp:3251-3262`, savings `:3326-3337`: the reset is unconditional inside `if (hbd_seconds > 0 && update_balance)`; the vop is suppressed only when interest == 0). At 10% APR, a 30-day period needs >= ~0.122 HBD for interest >= 1 satoshi (0.001 HBD); smaller savings balances repeatedly lose their accrued dollar-seconds whenever touched after 30+ days.

### Interest Rate

- Each witness publishes `hbd_interest_rate` in its chain properties; the **median of the scheduled witnesses' values** (the 21 of a round: 20 elected and, since HF17, 1 timeshare witness, which is picked by virtual schedule time from outside the top 20 rather than by the 21st-highest vote, `witness_schedule.cpp:209-231`; see Witness Reward Distribution) is taken during witness schedule update; each property is sorted and medianed independently of the others (`witness_schedule.cpp:82-86`)
- Default: `HIVE_DEFAULT_HBD_INTEREST_RATE` = 1000 bps = 10% APR (`config.hpp:251`)
- Stored in `dynamic_global_property_object::hbd_interest_rate`; rate is APR in basis points
- **Bounds: 0 ≤ rate ≤ 10,000 bps (0–100% APR)**, enforced in both witness property paths:
  - `legacy_chain_properties::validate()` (used by `witness_update_operation`): non-negative + `validate_number_in_100_percent_range` (`protocol/hive_operations.hpp:432-434`)
  - `witness_set_properties_operation::validate()`: same checks on the serialized property (`protocol/hive_operations.cpp:329-340`)

### Which Balances Earn Interest

| Balance Type | Pre-HF25 | HF25+ |
|-------------|----------|-------|
| Liquid HBD (`hbd_balance`) | **Yes** | **No** |
| Savings HBD (`savings_hbd_balance`) | **Yes** | **Yes** |
| Savings HIVE | No | No |

Post-HF25, only savings HBD earns interest, so earning interest means accepting the 3-day savings withdrawal delay. (The 3-day savings withdrawal is unrelated to the 30-day delayed-voting on power-ups; see Vesting.)

---

## Conversions

### HBD -> HIVE (Regular Conversion)

**Operation**: `convert_operation`
**Evaluator**: `convert_evaluator::do_apply()` at `hive_evaluator_transfer.cpp:468-484`

**Process**:
1. HBD is deducted from the user's balance **immediately** (`hive_evaluator_transfer.cpp:473`); a price feed must exist (`:476`)
2. A `convert_request_object` holding the deducted HBD (Part 05, section convert_request_object) is created with completion at now + `HIVE_CONVERSION_DELAY` (3.5 days; pre-HF16 it was `HIVE_CONVERSION_DELAY_PRE_HF_16` = 7 days, `config.hpp:191-192`, `hive_evaluator_transfer.cpp:478-483`)
3. At completion, `process_conversions()` (`database_conversion.cpp:35-196`) executes:
   ```cpp
   amount_to_issue = convert_amount * current_median_history;   // line 67
   ```
   emitting `fill_convert_request_operation`. Since 1.28.8 the run works in three steps: all due regular and collateralized requests are collected first (amounts and vops computed, request balances drained, objects removed, `database_conversion.cpp:55-135`); the supply is then corrected once, the collected HBD burned with the dgpo's `burn_HBD` and the net HIVE issued or burned with `issue_HIVE` / `burn_HIVE` (`current_hbd_supply`, `current_supply`, `virtual_supply`; `:137-159`); only then are the owners credited and the vops emitted, regular requests first (`:161-195`). At 1.28.7 each request was credited and its vop emitted as it was processed, and the supply was corrected at the end of the run.

**Key properties**:
- **No fee** — conversion at the exact median price **at completion time** (not submission)
- Because it uses `current_median_history`, the conversion **is** affected by the hard-cap artificial price (see Price Feed): when the haircut is active, HBD converts at the corrected (worse) rate — this is precisely the cap's defense mechanism
- `process_conversions()` returns early while the feed is null — historically the case until block 933,600 (`database_conversion.cpp:39-40`)

### HIVE -> HBD (Collateralized Conversion)

**Operation**: `collateralized_convert_operation` (HF25+, asserted at `hive_evaluator_transfer.cpp:488`)
**Evaluator**: `collateralized_convert_evaluator::do_apply()` at `hive_evaluator_transfer.cpp:486-533`

**Process**:
1. User submits HIVE; the **full amount is taken as collateral** immediately (`hive_evaluator_transfer.cpp:493`) and held by the request until settlement (Part 05, section collateralized_convert_request_object)
2. **Immediate HBD creation** (`hive_evaluator_transfer.cpp:506-512`):
   ```cpp
   for_immediate = collateral * 100% / HIVE_CONVERSION_COLLATERAL_RATIO;  // = collateral / 2
   converted_hbd = multiply_with_fee(for_immediate, current_min_history, 5%);
   FC_ASSERT(converted_hbd > 0, "Amount of collateral too low - conversion gives no HBD");
   ```
   - Uses `current_min_history` (3.5-day rolling **minimum**, most conservative) plus the 5% fee
   - HBD credited instantly; `current_hbd_supply` (and `virtual_supply`) raised immediately, since 1.28.8 through the dgpo's `issue_HBD`, the HIVE side corrected only at settlement (`hive_evaluator_transfer.cpp:514-524`, with a design comment describing the alternative of burning all collateral upfront and printing back the excess, `:520-523`)
3. Guards: rejected when `hbd_print_rate == 0` (`hive_evaluator_transfer.cpp:498`, with comment explaining the feed updates hourly so the artificial-price state may lag), and when the new HBD would push `calculate_HBD_percent()` over `hbd_stop_percent` (`:526-527`)
4. `collateralized_convert_immediate_conversion_operation` vop emitted (line 532)
5. After 3.5 days, `process_conversions()` settles (`database_conversion.cpp:99-132`, `:177-195`):
   ```cpp
   required_hive = multiply_with_fee(converted_amount, market_median_history, 5%);
   excess_collateral = collateral - required_hive;   // returned to user
   // required_hive burned from supply
   ```
   The inline comment (`database_conversion.cpp:103-108`) explains the price choice: median (not minimum) is proper for settlement — the minimum at the immediate step was anti-gaming; and `market_median_history` (not `current_median_history`) is used for the rare case where the hard cap has corrupted the official median away from market conditions.

**Key properties**:
- **Collateral ratio**: 200% (`HIVE_CONVERSION_COLLATERAL_RATIO = 2 * HIVE_100_PERCENT`, `config.hpp:194`)
- **Fee**: 5% (`HIVE_COLLATERALIZED_CONVERSION_FEE = 5 * HIVE_1_PERCENT`, `config.hpp:195`), applied at **both** the immediate quote and the settlement computation
- **Delay**: same 3.5 days (`HIVE_COLLATERALIZED_CONVERSION_DELAY = HIVE_CONVERSION_DELAY`, `config.hpp:193`)
- The user effectively receives HBD priced off `min_history × 1.05` upfront and is later charged `market_median × 1.05` worth of HIVE; everything else comes back

### Insufficient Collateral Edge Case

If at settlement the required HIVE exceeds the locked collateral (HIVE price dropped more than ~50% net of fee during the delay), `database_conversion.cpp:114-117`, `:182-188`:
```cpp
if (excess_collateral < 0)        // while collecting the request
    required_hive = collateral;   // burn everything; to_return stays 0, user gets nothing back
// supply corrected once for the whole run, then while crediting:
if (excess_collateral < 0)        // pushed right before this request's fill vop
    push system_warning_operation ("Insufficient collateral on conversion ... shortfall of ...");
```
The already-issued HBD remains in circulation — a bounded form of under-collateralized HBD creation, accepted by design and mitigated by the 200% requirement.

---

## DHF (Decentralized Hive Fund)

### Overview

The DHF is the on-chain treasury funding proposals voted on by stakeholders, managed by `dhf_processor` (`util/dhf_processor.cpp`). The treasury account is `steem.dao` before HF24 and `hive.fund` after (`OBSOLETE_TREASURY_ACCOUNT` `config.hpp:455`, `NEW_HIVE_TREASURY_ACCOUNT` `config.hpp:456`); the rename at `HIVE_HARDFORK_1_24_TREASURY_RENAME` creates/locks the new account and `consolidate_treasury_balance()` moves all old-treasury balances over (`database_hardfork.cpp:524-539`). The treasury account is locked (no keys) and protected: it cannot receive vesting or be a power-down target (`hive_evaluator_transfer.cpp:307-308`, `:411-414`), and from HF21 plain transfers to it may carry only HBD (`hive_evaluator_transfer.cpp:294`, although the error message says "HBD or HIVE"); since HF24 HIVE sent to it is converted to HBD at the median price on arrival (`:270-291`).

Per-block hook order (`dhf_processor::run()`, `dhf_processor.cpp:298-304`): `remove_old_proposals` → `record_funding` → `convert_funds` → `make_payments`.

### Funding Sources

1. **Inflation allocation**: 10% of new HIVE (post-HF21), converted to HBD at median price and credited to treasury **every block** in `process_funds()` (`database.cpp:1794`, `:1800-1802`). The amounts also accumulate in `dgpo.dhf_interval_ledger`; once per maintenance hour `record_funding()` emits a single summarizing `dhf_funding_operation` vop and resets the ledger (`dhf_processor.cpp:306-323`); the ledger is reporting-only, the balance was already credited.
2. **Daily HIVE->HBD conversion** of treasury-held HIVE (below).
3. **Proposal creation fees**: `create_proposal_operation` costs `HIVE_TREASURY_FEE` = 10.000 HBD plus, since HF24, 1.000 HBD per day of runtime beyond 60 days (`HIVE_PROPOSAL_FEE_INCREASE_*`, `config.hpp:461-467`); the fee is paid **to the treasury** and reported via `proposal_fee_operation` (`dhf_evaluator.cpp:44-55`, `:93-98`).
4. **Beneficiary rewards**: posts naming the treasury as beneficiary pay it directly in HBD (`database_comment.cpp:252-262`).
5. **HF23 seizure**: balances of the Steemit-related accounts cleared at HF23 went to the treasury (`clear_accounts(...)`, `database_hardfork.cpp:451`); `hardfork_property_object::h23_balances` records each account's `hive_transferred` and `hbd_transferred` (`database.cpp:1664`, `database_hardfork.cpp:557-563`), not the HIVE from its converted VESTS (`total_hive_from_vests` of the same vop, `database.cpp:1662`).
6. **Direct transfers**: anyone can send HBD to the treasury, and since HF24 also HIVE, which is converted to HBD at the median price on arrival (`hive_evaluator_transfer.cpp:270-295`). Each block, right before `process_funds`, `consolidate_treasury_balance()` moves any balance left on the old treasury account into the new one (its VESTS and reward VESTS converted to HIVE first, `database.cpp:1355-1392`), while `clear_null_account_balance()` (HF14+) burns the balances of `null` instead of passing them to the treasury (`database.cpp:2350-2352`, `:1296-1398`, `:1277-1291`).

### Daily Treasury Conversion

From `dhf_processor::convert_funds()` (`dhf_processor.cpp:325-364`), gated on the **daily** maintenance time and on HF24 (`is_daily_maintenance_period`, `dhf_processor.cpp:34-41`: "No DHF conversion until HF24"):
```cpp
to_convert = HIVE_PROPOSAL_CONVERSION_RATE * treasury.hive_balance / HIVE_100_PERCENT;
             // 5 basis points = 0.05% of treasury HIVE per day (config.hpp:468)
converted_hbd = to_convert * current_median_history;
if (converted_hbd < HIVE_MIN_PAYOUT_HBD) return;   // dust guard, dhf_processor.cpp:350-351
// balance swap through the dgpo's convert_HIVE_to_HBD: HIVE burned, HBD minted (dhf_processor.cpp:353-360)
// dhf_conversion_operation vop (dhf_processor.cpp:362-363)
```

### Proposal Payment

From `dhf_processor::make_payments()` (`dhf_processor.cpp:238-286`), every `HIVE_PROPOSAL_MAINTENANCE_PERIOD` (3600s on mainnet, `protocol/config.hpp:168`):

1. **Find proposals** active now (`start_date <= now <= end_date`, `dhf_processor.cpp:71-86`)
2. **Recalculate votes** for each active proposal — and also for not-yet-active ones, "only for presentation/statistics" (`dhf_processor.cpp:266-270`):
   - A proposal's `total_votes` = sum of `get_governance_vote_power()` over its voters **who have no proxy set** (`dhf_processor.cpp:95-104`)
   - `get_governance_vote_power()` = own `vesting_shares` **minus `sum_delayed_votes`** (the 30-day-maturing power-up vests) **plus all proxied votes** (`detail/state/account_object.hpp:326-342`)
3. **Sort by `total_votes` descending**, ties broken by lower `proposal_id` first (`dhf_processor.cpp:126-136`)
4. **Maintenance budget** (`calculate_maintenance_budget()`, `dhf_processor.cpp:145-159`):
   ```cpp
   daily_budget_limit = treasury_hbd / 100;            // total_amount_divider = 100 → 1%/day
   budget = daily_budget_limit * passed_seconds / 86400;
   ```
5. **Pay in vote order** until the budget runs out (`transfer_payments()`, `dhf_processor.cpp:161-213`):
   - `period_pay = passed_seconds * daily_pay / 86400` (HF25+ simplified math, lines 192-200)
   - A proposal with `total_votes == 0` terminates the loop (lines 188-189 — sorted order makes `break` safe)
   - Payments are **direct liquid HBD transfers** from treasury to receiver with a `proposal_pay_operation` vop (`dhf_processor.cpp:170-181`); no claiming involved
6. `update_settings()` advances `next_maintenance_time = head_time + 3600` and `last_budget_time = head_time` (`dhf_processor.cpp:215-223`, through the dgpo setter at `global_property_object.hpp:122-126`)

`process_proposals()` runs late in `_apply_block` with the comment "new HBD converted here does not count towards limit" (`database.cpp:2364`): it comes after the block's last `update_virtual_supply()`, which sets `hbd_print_rate` (`:2359`), and since HF24 `calculate_HBD_percent()` leaves the treasury's HBD out of the HBD share anyway (`:2889-2896`). Treasury conversions do count towards the proposal payment budget: `run()` calls `convert_funds` before `make_payments`, which computes the budget from the treasury's HBD balance at that point (`dhf_processor.cpp:298-304`, `:138-159`).

### Proposal Lifecycle Constraints

- `create_proposal`: HF21+ (`HIVE_HARDFORK_0_21_PROPOSALS`); `end_date > now`; permlink must reference an existing comment by creator or receiver; fee as above (`dhf_evaluator.cpp:31-101`)
- `update_proposal` (HF24+): creator only; **`daily_pay` can only decrease**; since HF25 the `end_date` can be moved **earlier** only (`dhf_evaluator.cpp:103-154`)
- `update_proposal_votes`: requires voting rights; **refreshes the voter's governance vote expiration** (`dhf_evaluator.cpp:169`)
- **Governance vote expiration**: all governance votes (witness + proposal) expire after `HIVE_GOVERNANCE_VOTE_EXPIRATION_PERIOD` = 365 days (`protocol/config.hpp:171`) of governance inactivity; `remove_expired_governance_votes()` runs per block from HF25 on (`database.cpp:3502-3545`), so inactive accounts drop off proposals without acting; each expiry is reported by an `expired_account_notification_operation` vop (`:3536`)
- Expired proposals are **not** auto-removed (kept queryable); removal happens only via explicit `remove_proposal_operation`, processed in batches with a removal threshold (`dhf_processor.cpp:53-68`)

### Return Proposal

There is no "return proposal" in the code. The convention: the community keeps a proposal whose receiver is the treasury itself (refund proposal) heavily voted; every proposal ranked below it effectively gets nothing once the budget is consumed above it, and the refund proposal's own `period_pay` simply transfers treasury money back to the treasury. The only code-level cutoff is `total_votes == 0` (`dhf_processor.cpp:188-189`).

### Key Constants

| Constant | Value |
|----------|-------|
| `total_amount_divider` | 100 (1% of treasury HBD per day) (`dhf_processor.hpp`) |
| `HIVE_PROPOSAL_MAINTENANCE_PERIOD` | 3,600s (1 hour) (`protocol/config.hpp:168`) |
| `HIVE_DAILY_PROPOSAL_MAINTENANCE_PERIOD` | 86,400s (24 hours) (`protocol/config.hpp:170`) |
| `HIVE_PROPOSAL_CONVERSION_RATE` | 5 bps (0.05%/day) (`config.hpp:468`) |
| `HIVE_TREASURY_FEE` | 10.000 HBD (`config.hpp:461`) |
| `HIVE_PROPOSAL_FEE_INCREASE_AMOUNT` / `_DAYS` | 1.000 HBD/day beyond 60 days (`config.hpp:465-467`) |
| `HIVE_PROPOSAL_SUBJECT_MAX_LENGTH` | 80 (`config.hpp:462`) |
| `HIVE_GOVERNANCE_VOTE_EXPIRATION_PERIOD` | 365 days (`protocol/config.hpp:171`) |

---

## Vesting Mechanics (Power Up / Power Down)

### Power Up (HIVE -> VESTS)

**Operation**: `transfer_to_vesting_operation`
**Evaluator**: `transfer_to_vesting_evaluator::do_apply()` at `hive_evaluator_transfer.cpp:302-336`

**Conversion rate** (`get_vesting_share_price()`, `detail/state/global_property_object.hpp:94-99`):
```cpp
if (total_vesting_fund_hive == 0 || total_vesting_shares == 0)
    return VEST_price(1000000, 1000);   // empty pools: 1.000000 VESTS per 1.000 HIVE (satoshi amounts), i.e. 1:1 at genesis
return VEST_price(total_vesting_shares, total_vesting_fund_hive);
```
The VESTS-per-HIVE ratio falls over time (15% of inflation enters `total_vesting_fund_hive` each block without minting VESTS), so each VEST appreciates in HIVE terms. It is not strictly monotonic: the HF1 split multiplied all VESTS by 1,000,000 (Part 01, section Key Discoveries, item 10), and claimed reward VESTS enter the pools at the account's own ratio (see Claiming Rewards).

**Delayed voting** (HF24+, `hive_evaluator_transfer.cpp:322-328`): newly vested shares are recorded via `delayed_voting::add_delayed_value()` and excluded from governance power for `HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS` = **30 days** (`protocol/config.hpp:178`). Mechanics (`util/delayed_voting_processor.hpp:35`, `:65`; `util/delayed_voting.cpp:88-105`): per-account bucket list with `HIVE_DELAYED_VOTING_INTERVAL_SECONDS` = 1-day granularity (`protocol/config.hpp:179`), max 30 entries; `process_delayed_voting()` (called per block, `database.cpp:2365`) matures buckets older than 30 days into witness/proposal voting power. The code comment explains the rationale: instant voting after power-up would let attackers buy stake and immediately take over governance (`hive_evaluator_transfer.cpp:316-321`). **This is unrelated to the 3-day HBD savings withdrawal delay**: delayed voting only suppresses governance weight; the vests themselves are usable (and can even be powered down) immediately.

Vesting to the treasury is forbidden (HF21+, `hive_evaluator_transfer.cpp:307-308`). A `transfer_to_vesting_completed_operation` vop reports the VESTS created (line 335).

### Power Down (VESTS -> HIVE)

**Operation**: `withdraw_vesting_operation`
**Evaluator**: `withdraw_vesting_evaluator::do_apply()` at `hive_evaluator_transfer.cpp:338-400`

**Setup**:
```cpp
vesting_withdraw_rate = requested_vests / 13;            // HIVE_VESTING_WITHDRAW_INTERVALS (HF16+)
if (rate == 0) rate = 1;                                  // minimum 1 satoshi-VEST
if (HF21+ && rate * 13 < requested) rate += 1;            // round UP so the full amount completes in 13 weeks
next_vesting_withdrawal = now + 604800;                   // 7 days
```
- Delegated VESTS cannot be withdrawn: requires `vesting - delegated_vesting >= amount` (`hive_evaluator_transfer.cpp:354`)
- **Cancel**: `vesting_shares = 0` resets the schedule; since `HIVE_HARDFORK_1_28_FIX_CANCEL_POWER_DOWN` cancelling with no active power-down, or "changing" to the identical rate, is rejected as a no-op (`hive_evaluator_transfer.cpp:360-361`, `:389-390`)
- Pre-HF20 a negative-amount withdraw was silently ignored rather than rejected; the code links the infamous block 23,847,548 incident (`hive_evaluator_transfer.cpp:345-351`)

**Processing** (weekly per account, `process_vesting_withdrawals()` at `database_vesting.cpp:111-307`):

1. `to_withdraw = min(vesting_withdraw_rate, remaining)`; a pre-HF28 quirk computed the final installment as `to_withdraw % rate`: the long comment (`database_vesting.cpp:130-135`, on the code at `:128-129`) documents the 'gil' account case where HF1's fractional rate change made the modulo wrong; `HIVE_HARDFORK_1_28_FIX_POWER_DOWN` removed the modulo path. A safety clamp logs `NOTIFYALERT!` and caps at the actual balance if the schedule somehow exceeds it (lines 136-146)
2. **Withdraw routes** (up to `HIVE_MAX_WITHDRAW_ROUTES = 10` destinations, percent sum ≤ 100%, set via `set_withdraw_vesting_route_operation`, `hive_evaluator_transfer.cpp:402-466`): processed in **two passes** — first all `auto_vest` routes (VESTS transferred as VESTS), then all conversion routes (VESTS → HIVE at current price); comment: "Try to maintain as much accuracy for VESTS as possible" (lines 230-232). Each transfer emits `fill_vesting_withdraw_operation`
3. Remainder (not routed): converted to HIVE at `get_vesting_share_price()` and credited to the account; the vop is emitted even for a zero remainder (issue #337 referenced in comment, `database_vesting.cpp:248-249`)
4. Global pools shrink only for converted amounts: since 1.28.8 the dgpo's `convert_VESTS_to_HIVE` pays their HIVE out of `total_vesting_fund_hive` and burns their VESTS from `total_vesting_shares` at the regular price (`database_vesting.cpp:186-189`, `:240-243`), while the installment is issued with `issue_VESTS(to_withdraw, true)` and the account's `to_withdraw` VESTS are burned with `burn_VESTS(..., true)`, both on `pending_rewarded_vesting_shares` (`:160-164`, `:282-286`); auto-vest routed VESTS just move between accounts
5. Account bookkeeping: `withdrawn += to_withdraw` (this step's amount); when the account's remaining withdrawal `get_total_vesting_withdrawal()` (`to_withdraw - withdrawn`, `detail/state/account_object.hpp:99`) is <= 0 or vesting hits 0, the schedule resets; otherwise `next_vesting_withdrawal += 7 days` (`database_vesting.cpp:260-277`)
6. Governance power: HF24+ reduces the withdrawer's **delayed votes first**, only the leftover reduces actual (proxied) witness votes (`database_vesting.cpp:288-296`); pre-HF24, votes reduced directly

| Constant | Value |
|----------|-------|
| `HIVE_VESTING_WITHDRAW_INTERVALS` | 13 (HF16+) (`config.hpp:233`) |
| `HIVE_VESTING_WITHDRAW_INTERVALS_PRE_HF_16` | 104 (2 years) (`config.hpp:232`) |
| `HIVE_VESTING_WITHDRAW_INTERVAL_SECONDS` | 604,800 (7 days; defined as = cashout window) (`config.hpp:234`) |
| `HIVE_MAX_WITHDRAW_ROUTES` | 10 (`config.hpp:235`) |

### Reward Vesting Price

Reward-balance VESTS use `get_reward_vesting_share_price()` which includes the pending pools (`detail/state/global_property_object.hpp:109-113`):
```cpp
reward_vesting_price = (total_vesting_shares + pending_rewarded_vesting_shares) /
                       (total_vesting_fund_hive + pending_rewarded_vesting_hive)
```

---

## Price Feed

### Feed Collection

Updated every `HIVE_FEED_INTERVAL_BLOCKS` (1200 blocks = 1 hour, `config.hpp:185`; gate at `database.cpp:2419`), from `update_median_feed()` at `database.cpp:2416-2531`:

1. Collect `hbd_exchange_rate` from the **currently scheduled (shuffled) witnesses** of this round — not from all witnesses (`database.cpp:2424-2441`)
2. Discard null feeds and feeds older than `HIVE_MAX_FEED_AGE_SECONDS` (7 days). **Pre-HF19 the age check was inverted/broken**: the condition `last_update < now + max_age` is always true, so stale feeds were never filtered; `HIVE_HARDFORK_0_19__822` fixed it to `now < last_update + max_age` (`database.cpp:2428-2440`)
3. Require at least `HIVE_MIN_FEEDS = HIVE_MAX_WITNESSES/3 = 7` valid feeds, otherwise no update this hour (comment: "protects the network from conversions before price has been established", `config.hpp:189`)
4. Take the **upper median** (`feeds[size/2]` after sort, `database.cpp:2445-2446`) and push it into `price_history`

A long code comment (`database.cpp:2447-2454`) documents that feeds must be sorted as raw `price` (pre-HF20 some witnesses published non-normalized HIVE-base prices, and symbol-first comparison made sorting order differ in exactly 21 historical cases between blocks 13,335,600–13,362,000), but storing history normalized as `HBD_price` was verified safe — final medians match either way.

### Feed History

The `feed_history_object` maintains (`database.cpp:2465-2472`):
- `price_history` — deque of hourly medians-of-witness-feeds
  - Window: `HIVE_FEED_HISTORY_WINDOW = 84` entries = 3.5 days (`config.hpp:187`); pre-HF16: 168 entries = 7 days (trimmed at HF16, `database_hardfork.cpp:258-262`)
- `current_median_history` - median of the window (the "official" price; may be artificially raised by the hard cap). Used by: regular conversions, DHF conversions/funding, `award_hbd` (`create_hbd` at 1.28.7), virtual supply, `calculate_HBD_percent`
- `market_median_history` — same median **without** hard-cap correction. Used by: collateralized conversion settlement
- `current_min_history` / `current_max_history` — window extremes; the minimum is used by collateralized immediate conversion; the maximum gets dragged up by a hard-cap correction but the minimum deliberately does not (an open question in the code itself: "should we also correct current_min_history?", `database.cpp:2523`)

### HBD Hard Cap (Haircut Rule)

Introduced at HF14 (`HIVE_HARDFORK_0_14__230`); when HBD (excluding treasury since `HIVE_HARDFORK_1_25_HBD_HARD_CAP`, `database.cpp:2502-2503`) would exceed the hard limit as a fraction of combined market cap, `current_median_history` is overridden upward (`database.cpp:2478-2526`):

```
limit L (full percentage points): 10% pre-HF26, 30% since HF26 (config.hpp:344-345)
min_price = (100% − L)·hbd_supply HBD  per  L·hive_supply HIVE     // database.cpp:2512-2513
if (min_price > current_median_history) {
    push system_warning_operation("HIVE price corrected upward due to ...% HBD cutoff rule ...");
    current_median_history = min_price;        // override official price
}
if (min_price > current_max_history) current_max_history = min_price;
// market_median_history is NEVER touched
```

The derivation and a worked example live in the comment block (`database.cpp:2480-2498`), including why the price is expressed as `(100%-L)·X per L·Y` rather than `(100%/L − 1)·X per Y` — integer precision (with the naive form, L=30% and L=33% would produce identical prices).

**Effect**: with the artificial price, HBD→HIVE conversions yield less HIVE per HBD, capping how much of the HIVE supply can be extracted via conversions — the stated threat being a large HBD holder exploiting a sharp HIVE price decline to take over the chain (`database.cpp:2480-2484`).

**Debt ratio measurement** (`calculate_HBD_percent()`, `database.cpp:2880-2903`): returns 0 while the feed is null; since HF24 excludes treasury HBD from the numerator **and** recomputes the denominator (virtual supply) without it (`database.cpp:2889-2896`); HF21 added half-denominator rounding (`database.cpp:2900-2901`).

### HBD Print Rate (Soft Throttle)

Recomputed in `update_virtual_supply()` (`database.cpp:2905-2926`), which runs twice per block (`database.cpp:2348`, `:2359`), from HF14 on and only while the median price is set (`:2914`) - see "HBD Print Rate and Author Payout" for the formula and the HF14/HF20/HF26 parameter table. Note the two distinct mechanisms and thresholds since HF26: print throttling flips at 20% debt ratio; the price haircut engages at 30%.

---

## Block Processing Order

From `_apply_block()` (`database.cpp:2342-2373`), the per-block economic pipeline:

```
 1. clear_expired_orders()
 2. clear_expired_delegations()
 3. update_witness_schedule()
 4. update_median_feed()              // hourly; may apply haircut
 5. update_virtual_supply()           // "accommodate potentially new price"
 6. clear_null_account_balance()      // burns null's balances (HF14+)
 7. consolidate_treasury_balance()    // old treasury -> current treasury
 8. process_funds()                   // INFLATION
 9. process_conversions()             // HBD<->HIVE completions
10. process_comment_cashout()         // REWARD PAYOUTS
11. process_vesting_withdrawals()     // POWER-DOWN installments
12. process_savings_withdraws()
13. process_subsidized_accounts()
14. pay_liquidity_reward()            // no-op since HF12
15. update_virtual_supply()           // "cover changes in HBD supply from above"
16. account_recovery_processing()
17. expire_escrow_ratification()
18. process_decline_voting_rights()
19. process_proposals()               // DHF; "new HBD converted here does not count towards limit"
20. process_delayed_voting()          // mature 30-day buckets
21. remove_expired_governance_votes() // 365-day expiry
22. process_recurrent_transfers()
23. rc().handle_expired_delegations(); rc().finalize_block()
24. process_hardforks()
```

---

## Economic Constants Reference

| Constant | Value | Purpose |
|----------|-------|---------|
| `HIVE_INFLATION_RATE_START_PERCENT` | 978 (9.78%) | Starting annual inflation (`config.hpp:253`) |
| `HIVE_INFLATION_RATE_STOP_PERCENT` | 95 (0.95%) | Floor annual inflation (`config.hpp:254`) |
| `HIVE_INFLATION_NARROWING_PERIOD` | 250,000 blocks | Blocks per 0.01% reduction (`config.hpp:255`) |
| `HIVE_BLOCKS_PER_YEAR` | 10,512,000 | At 3s block interval (`protocol/config.hpp:60`) |
| `HIVE_CONTENT_REWARD_PERCENT_HF16` / `_HF21` | 7500 / 6500 | Content share of inflation (`config.hpp:256,260`) |
| `HIVE_VESTING_FUND_PERCENT_HF16` | 1500 (15%) | Vesting fund share (`config.hpp:257`) |
| `HIVE_PROPOSAL_FUND_PERCENT_HF0` / `_HF21` | 0 / 1000 | DHF share (`config.hpp:258,261`) |
| `HIVE_100_PERCENT` / `HIVE_1_PERCENT` / `HIVE_1_BASIS_POINT` | 10,000 / 100 / 1 | Percent math (`config.hpp:211-213`) |
| `HIVE_CASHOUT_WINDOW_SECONDS` | 604,800 (7 days) | Payout window since HF17 (`protocol/config.hpp:156`) |
| `HIVE_CASHOUT_WINDOW_SECONDS_PRE_HF12` / `_PRE_HF17` | 1 day / 12 hours | Historical windows (`protocol/config.hpp:154-155`) |
| `HIVE_SECOND_CASHOUT_WINDOW` | 30 days | Second payout, HF12-HF17 (`protocol/config.hpp:157`) |
| `HIVE_MIN_PAYOUT_HBD` | 0.020 HBD | Dust threshold (payouts & DHF conversion) (`config.hpp:336`) |
| `HIVE_MAX_COMMENT_BENEFICIARIES` | 8 | Soft-fork beneficiary limit (`config.hpp:272`) |
| `HIVE_BENEFICIARY_LIMIT` | 128 | Protocol limit (exclusive) (`config.hpp:426`) |
| default `max_accepted_payout` | 1,000,000.000 HBD | Per-comment payout cap (`hive_operations.hpp:139`) |
| `HIVE_VESTING_WITHDRAW_INTERVALS` (`_PRE_HF_16`) | 13 (104) | Weekly power-down installments (`config.hpp:232-233`) |
| `HIVE_VESTING_WITHDRAW_INTERVAL_SECONDS` | 604,800 (7 days) | Between installments (`config.hpp:234`) |
| `HIVE_MAX_WITHDRAW_ROUTES` | 10 | Power-down destinations (`config.hpp:235`) |
| `HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS` | 30 days | Power-up governance delay (`protocol/config.hpp:178`) |
| `HIVE_DELAYED_VOTING_INTERVAL_SECONDS` | 1 day | Delay bucket granularity (`protocol/config.hpp:179`) |
| `HIVE_VOTING_MANA_REGENERATION_SECONDS` | 432,000 (5 days) | Full mana regen (`config.hpp:239`) |
| `HIVE_VOTE_DUST_THRESHOLD` | 50,000,000 | Subtracted from every vote's rshares (`config.hpp:243`) |
| `HIVE_DOWNVOTE_POOL_PERCENT_HF21` | 2500 (25%) | Downvote mana pool (`config.hpp:244`) |
| `HIVE_INITIAL_VOTE_POWER_RATE` / `HIVE_REDUCED_VOTE_POWER_RATE` | 40 / **10 (current)** | `vote_power_reserve_rate`; reduced at HF19 (`config.hpp:385-386`) |
| `HIVE_REVERSE_AUCTION_WINDOW_SECONDS_HF6/HF20/HF21/HF25` | 30m / 15m / 5m / 0 | Reverse auction (`protocol/config.hpp:240-242,181`) |
| `HIVE_EARLY_VOTING_SECONDS_HF25` | 86,400 (24h) | Full-curation window (`protocol/config.hpp:182`) |
| `HIVE_MID_VOTING_SECONDS_HF25` | 172,800 (48h) | Half-curation window (`protocol/config.hpp:183`) |
| `HIVE_UPVOTE_LOCKOUT_SECONDS` | 43,200 (12h) | Pre-cashout vote scaling (`protocol/config.hpp:160`) |
| `HIVE_RECENT_RSHARES_DECAY_TIME_HF17` / `_HF19` | 30 / 15 days | Claims decay (`config.hpp:296-297`) |
| `HIVE_CONTENT_CONSTANT_HF0` = `_HF21` | 2,000,000,000,000 | Curve parameter (`config.hpp:298,264`) |
| `HIVE_DEFAULT_HBD_INTEREST_RATE` | 1000 (10% APR) | Default interest (`config.hpp:251`); witness-set range 0–10000 |
| `HIVE_HBD_INTEREST_COMPOUND_INTERVAL_SEC` | 2,592,000 (30 days) | Min time between interest payments (`config.hpp:362`) |
| `HIVE_SECONDS_PER_YEAR` | 31,536,000 | Interest denominator (`config.hpp:360`) |
| `HIVE_CONVERSION_DELAY` (`_PRE_HF_16`) | 3.5 days (7 days) | HBD->HIVE delay (`config.hpp:191-192`) |
| `HIVE_COLLATERALIZED_CONVERSION_DELAY` | 3.5 days | HIVE->HBD delay (`config.hpp:193`) |
| `HIVE_CONVERSION_COLLATERAL_RATIO` | 20,000 (200%) | Collateral requirement (`config.hpp:194`) |
| `HIVE_COLLATERALIZED_CONVERSION_FEE` | 500 (5%) | Applied at quote and settlement (`config.hpp:195`) |
| `HIVE_FEED_INTERVAL_BLOCKS` | 1,200 (1 hour) | Feed cadence (`config.hpp:185`) |
| `HIVE_FEED_HISTORY_WINDOW` (`_PRE_HF_16`) | 84 (168) entries | 3.5 (7) days (`config.hpp:186-187`) |
| `HIVE_MAX_FEED_AGE_SECONDS` | 604,800 (7 days) | Feed staleness cutoff (`config.hpp:188`) |
| `HIVE_MIN_FEEDS` | 7 (21/3) | Minimum feeds for median update (`config.hpp:189`) |
| `HIVE_HBD_HARD_LIMIT` (`_PRE_HF26`) | 3000 (1000) | Haircut threshold 30% (10%) (`config.hpp:344-345`) |
| `HIVE_HBD_START/STOP_PERCENT_HF14` | 200 / 500 | Print throttle 2–5% (`config.hpp:338-339`) |
| `HIVE_HBD_START/STOP_PERCENT_HF20` | 900 / 1000 | Print throttle 9–10% (`config.hpp:340-341`) |
| `HIVE_HBD_START/STOP_PERCENT_HF26` | 2000 / 2000 | Print cliff at 20% (`config.hpp:342-343`) |
| `HIVE_PROPOSAL_MAINTENANCE_PERIOD` | 3,600s | DHF payment interval (`protocol/config.hpp:168`) |
| `HIVE_DAILY_PROPOSAL_MAINTENANCE_PERIOD` | 86,400s | Treasury conversion interval (`protocol/config.hpp:170`) |
| `HIVE_PROPOSAL_CONVERSION_RATE` | 5 bps (0.05%/day) | Treasury HIVE->HBD rate (`config.hpp:468`) |
| `HIVE_TREASURY_FEE` | 10.000 HBD | Proposal creation fee (`config.hpp:461`) |
| `HIVE_PROPOSAL_FEE_INCREASE_AMOUNT`/`_DAYS` | 1 HBD/day past 60 days | HF24+ extra fee (`config.hpp:465-467`) |
| `HIVE_GOVERNANCE_VOTE_EXPIRATION_PERIOD` | 365 days | Governance vote expiry (`protocol/config.hpp:171`) |
| `HIVE_CONTENT/CURATE/PRODUCER/POW/LIQUIDITY_APR_PERCENT` | 3875/3875/750/750/750 | Pre-HF16 APRs (`config.hpp:330-334`) |
| `HIVE_START_VESTING_BLOCK` | 201,600 (7 days) | First vesting rewards (`protocol/config.hpp:63`) |

---

## Key Discoveries

1. **HF26 HBD print rate cliff**: `hbd_start_percent == hbd_stop_percent == 20%`, so the interpolation branch in `update_virtual_supply()` is dead code - HBD printing is binary at exactly 20% debt ratio (`database.cpp:2918-2923`).

2. **HF28 inflation base change**: treasury HBD is excluded from virtual supply for inflation, preventing a feedback loop where treasury accumulation raises inflation (`database.cpp:1745-1754`).

3. **Collateralized conversion uses three different prices**: immediate quote at `current_min_history` (anti-manipulation), settlement at `market_median_history` (immune to haircut corruption of the official median), while regular conversions use `current_median_history` (deliberately exposed to the haircut). Rationale documented inline (`database_conversion.cpp:103-108`).

4. **HBD interest compounding is touch-driven, not scheduled**: interest is evaluated only when a balance is modified more than 30 days after the last payment. Untouched savings accrue *simple* interest indefinitely and receive a lump payment on the next touch; only accounts that touch their balance periodically experience compounding (`database.cpp:3242-3267`, `:3312-3345`; `protocol/hbd_interest.hpp:9-23`).

5. **HF25 curation penalty redistributes; the reverse auction burned**: the reverse auction added *full* weight to `total_vote_weight` but discounted the voter's stored weight (gap -> unclaimed -> pool/author), while the HF25 phase penalties (weight divided by 2 or 8) discount **before** accumulating into `total_vote_weight`, so the penalty flows to the other curators of the same post (`hive_evaluator_social.cpp:800-828`).

6. **DHF budget is 1% of treasury per day** (`total_amount_divider = 100`), independent of how much proposals request (`dhf_processor.cpp:154`).

7. **Witness pay is not equal**: per-block witness pay is `slice * 21 * weight / factor` with weights elected=1, timeshare=5, miner=1, where the factor is the sum of the scheduled witnesses' weights, recomputed every round (`witness_schedule.cpp:367-370`); with the usual 20 elected + 1 timeshare witnesses it is 25, so an elected witness block pays 0.84x nominal, a timeshare block 4.2x (`database.cpp:1766-1781`, `witness_objects.hpp:191-194`).

8. **HBD interest moved to savings-only at HF25**; savings HIVE never earned interest at all (`database.cpp:3242`, `:3304-3310`).

9. **Dust vote threshold is per-vote**: 50,000,000 rshares subtracted from every vote (`hive_evaluator_social.cpp:708-709`); with `vote_power_reserve_rate = 10` a full vote consumes exactly 2% of mana (1/50), matching the in-code "50 vote transaction" remark.

10. **Unclaimed curation rewards stay in the reward pool post-HF20**: `pay_curators()` shrinks `curation_tokens` by-reference to the actually-paid amount (`database_comment.cpp:187`); only `author_tokens + curation_tokens` (`claimed_reward`, `:238`) is deducted from the fund: since 1.28.8 the curator claims, beneficiary shares and author share are moved out of the temporary balance holding the fund's HIVE (`:169-170`, `:246-247`, `:282-283`) and the rest returns to the fund (`:508`); at 1.28.7 the fund was reduced by the summed `claimed_reward`. Pre-HF20 the remainder was added to the author's share instead (`database_comment.cpp:234-235`, `:446`).

11. **The famous "linear rewards" change was HF19, not HF17**: the reward fund keeps the legacy quadratic/bounded_curation defaults until HF19 (since 1.28.8 it exists from genesis with them, `database_init.cpp:258-262`; at 1.28.7 HF17 created it with them; HF17 touches no curve, `database_hardfork.cpp:265-290`); HF19 set linear/square_root **and** cut `vote_power_reserve_rate` 40->10, which is still the live value (`database_hardfork.cpp:294-308`, `reward_fund_object.hpp:66-70`).

12. **Claimed reward VESTS bypass delayed voting**: `claim_reward_balance` grants governance power immediately via `adjust_proxied_witness_votes` - the 30-day delay only covers `transfer_to_vesting` and VESTS that a power-down auto-vest route moves to another account (`hive_evaluator_transfer.cpp:720` vs `:322-328`; `database_vesting.cpp:213-217`; Part 14, section Key Discoveries, item 1).

13. **Disabling curation rewards burns the curation share into the pool**: with `allow_curation_rewards = false` the 50% curation slice is neither paid nor given to the author — it never leaves the reward fund (`database_comment.cpp:139-143`).

14. **The 8-beneficiary limit is a soft fork**: protocol accepts up to 127; the evaluator enforces 8 only while the node is in control (`is_in_control()`: when it validates a new transaction from the API or P2P and when it produces a block, `database.hpp:176`), so blocks from other producers containing 9-127 beneficiaries are accepted (`hive_evaluator_social.cpp:123-124`).

15. **Pre-HF19 the feed age filter was broken** (condition trivially true), so arbitrarily stale witness feeds entered the hourly median until `HIVE_HARDFORK_0_19__822` fixed the comparison (`database.cpp:2428-2440`).

16. **Governance votes expire after 365 days** of inactivity: from HF25 `remove_expired_governance_votes()`, run every block, clears them and reports each expiry with an `expired_account_notification_operation` vop, so DHF proposal rankings can change without any new votes being cast (`protocol/config.hpp:171`, `database.cpp:2366`, `:3502-3545`).

---

## Code References

| Topic | File | Key Lines |
|-------|------|-----------|
| Inflation/distribution | `database.cpp` | `process_funds()` 1725-1867 (HF28 base 1745-1759; witness weights 1766-1781; legacy 1816-1866); `pay_reward_funds()` 1953-1975 |
| Reward curves | `util/reward.cpp` | `get_rshare_reward()` 7-32; `evaluate_reward_curve()` 34-75 |
| Reward context defaults | `util/reward.hpp` | 23-33 (quadratic default); dust check 44-47 |
| Comment cashout | `database_comment.cpp` | `process_comment_cashout()` 378-510 (decay 397-413; snapshot 433-444; write-back 503-509) |
| Curation payment | `database_comment.cpp` | `pay_curators()` 121-191 |
| Author/beneficiary payment | `database_comment.cpp` | `cashout_comment_helper()` 193-376 (beneficiaries 242-279; author 281-321) |
| Curation % | `database.cpp` | `get_curation_rewards_percent()` 1943-1951 |
| HBD creation/print split | `database.cpp` | `award_hbd()` 957-1005 (`create_hbd()` at 1.28.7) |
| Vote -> rshares | `hive_evaluator_social.cpp` | `hf20_vote_evaluator()` 607-854 (mana 658-709; lockout 711-716; curation weight 751-839) |
| Comment options/beneficiaries | `hive_evaluator_social.cpp` | 109-173 |
| Beneficiary validation | `protocol/hive_operations.cpp` | `comment_payout_beneficiaries::validate()` 150-175 |
| Interest rate bounds | `protocol/hive_operations.hpp` | `legacy_chain_properties::validate()` 417-434 |
| Interest rate bounds | `protocol/hive_operations.cpp` | `witness_set_properties_operation::validate()`, interest rate 329-340 |
| HBD interest (liquid, pre-HF25) | `database.cpp` | `adjust_balance(HBD)` 3227-3281 |
| HBD interest (savings) | `database.cpp` | `adjust_savings_balance(HBD)` 3312-3345 |
| Interest formula | `protocol/hbd_interest.hpp` | `evaluate_hbd_interest()` 9-23 |
| Interest median | `witness_schedule.cpp` | 82-86 |
| Claim rewards | `hive_evaluator_transfer.cpp` | `claim_reward_balance_evaluator` 667-721 |
| Conversions processing | `database_conversion.cpp` | `process_conversions()` 35-196 |
| Convert evaluators | `hive_evaluator_transfer.cpp` | `convert` 468-484; `collateralized_convert` 486-533 |
| DHF processor | `util/dhf_processor.cpp` | `run()` 298-304; votes 88-124; budget 145-159; payments 161-213; funding vop 306-323; conversion 325-364 |
| Proposal evaluators | `dhf_evaluator.cpp` | create 31-101 (fee 44-55); update 103-154; votes 156+ |
| Governance vote power | `detail/state/account_object.hpp` | 326-342 |
| Power up | `hive_evaluator_transfer.cpp` | `transfer_to_vesting_evaluator` 302-336 |
| Power down setup | `hive_evaluator_transfer.cpp` | `withdraw_vesting_evaluator` 338-400; routes 402-466 |
| Power down processing | `database_vesting.cpp` | `process_vesting_withdrawals()` 111-307 |
| Delayed voting | `util/delayed_voting.cpp` | add 7-13; maturation 87-117 |
| Delayed voting | `util/delayed_voting_processor.hpp` | bucket 65 |
| Vesting prices | `detail/state/global_property_object.hpp` | `get_vesting_share_price()` 94-99; `get_reward_vesting_share_price()` 109-113 |
| Price feed + haircut | `database.cpp` | `update_median_feed()` 2416-2531 (cap 2478-2526) |
| HBD % / print rate | `database.cpp` | `calculate_HBD_percent()` 2880-2903; `update_virtual_supply()` 2905-2926 |
| Block order | `database.cpp` | `_apply_block` economic sequence 2342-2373 |
| Legacy compound template | `compound.hpp` | `calc_percent_reward<>()` 12-29 |
| Compound constants | `protocol/config.hpp` | 304-316 |
| Reward fund object | `detail/state/reward_fund_object.hpp` | defaults 66-70 |
| Reward fund creation (since 1.28.8) | `database_init.cpp` | `init_genesis()` 258-262 |
| HF parameter changes | `database_hardfork.cpp` | HF12 245-248; HF16 256-263; HF17 265-290; HF19 294-329; HF20 331-341; HF21 413-445; HF23 449-465; HF25 476-490; HF26 491-504; treasury rename 524-539 |

---

## Discrepancies and Potential Issues

1. **Content constant naming**: `HIVE_CONTENT_CONSTANT_HF0` (fund default) and `HIVE_CONTENT_CONSTANT_HF21` (set at HF21) are the same value (2*10^12); the HF21 re-assignment is a no-op for the constant itself: only the curves and the curation share (50%) changed. Confusing but harmless (`config.hpp:298` vs `:264`).

2. **Savings withdrawal pays no interest at completion**: interest is computed lazily on the `adjust_savings_balance(-amount)` at *request* time (if more than 30 days have passed since the last payment), not when the 3-day withdrawal completes (`hive_evaluator_transfer.cpp:636`; `database.cpp:3321`). A withdrawal draining the balance still triggers accrual on the way out, but timing is counter-intuitive.

3. **DHF maintenance drift**: `next_maintenance_time = head_time + period` shifts from the processing block's time rather than the scheduled time, drifting when maintenance blocks are missed; acknowledged inline with "the fix is problematic - see MR!168" (`dhf_processor.cpp:219-221`, same note for the daily conversion at `:334-336`; since 1.28.8 both times are set by the dgpo's setters, `global_property_object.hpp:122-130`).

4. **Collateralized conversion can leave uncovered HBD**: if HIVE drops >~50% during the 3.5-day delay, all collateral is burned but the issued HBD stays in circulation; signaled only by a `system_warning_operation` (`database_conversion.cpp:114-117`, `:182-188`). Accepted by design, bounded by the 200% requirement.

5. **HBD print rate cliff at HF26** (start == stop == 20%): no gradual throttle band remains; either intentional simplification or loss of fine-grained control (`config.hpp:342-343`).

6. **Interest dust wipe**: the dollar-seconds accumulator is zeroed even when the computed interest truncates to zero, so balances below ~0.122 HBD (at 10% APR) can permanently lose accrued interest each time they're touched after a 30-day gap (`database.cpp:3251-3262`, `:3326-3337`).

7. **Beneficiary limit is node policy, not consensus**: the 8-beneficiary cap uses `is_in_control()`, true only while the node validates a new transaction or produces a block (`database.hpp:176`), so blocks from other producers and replayed blocks with up to 127 beneficiaries are accepted (Part 03, section comment_payout_beneficiaries (extension struct)); downstream apps assuming <=8 could misbehave (`hive_evaluator_social.cpp:123-124`).

8. **`current_min_history` is not corrected by the hard cap** while `current_max_history` is; the code itself carries the unresolved question ("should we also correct current_min_history?", `database.cpp:2523`). Practical impact: during a haircut, collateralized conversions still quote off the uncorrected market minimum — consistent with using `market_median_history` at settlement, so arguably intentional.

---

## Open Questions

All previous open questions are resolved and folded into the body:
1. *Unclaimed curation post-HF20* → stays in the reward pool (see Curation Reward Distribution and Key Discovery 10).
2. *30-day delayed voting vs 3-day savings withdrawal* → unrelated mechanisms (see Power Up; delayed voting affects only governance weight).
3. *Exact block where inflation reaches 0.95%* → block 220,750,000, matching the code comment (see Inflation Timeline).

No open questions remain for this part. Candidate zoom deep-dives noted: (a) delayed-voting bucket edge cases (`util/delayed_voting*.{hpp,cpp}`): covered by Part 14 (delayed voting), section The Bucket Collection Algebra; (b) witness schedule/pay normalization interplay (overlaps part 06); (c) recurrent transfers economics (`process_recurrent_transfers`): covered by Part 12 (recurrent transfers), section Block processing state machine.
