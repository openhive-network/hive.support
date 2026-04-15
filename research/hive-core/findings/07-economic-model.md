# Findings: Economic Model — Rewards, Inflation, Interest, Conversions

## Summary

The Hive economic model is a complex system of interrelated mechanisms governing inflation, reward distribution, asset conversion, interest, and governance funding. All economic activity is driven by a per-block inflation schedule that creates new HIVE, which is then split among content creators, curators, witnesses (block producers), vesting holders, and the Decentralized Hive Fund (DHF/treasury). This document captures the **exact code behavior** verified from the C++ source.

Key characteristics:
- Inflation starts at 9.78% and decreases 0.01% every 250,000 blocks until it reaches 0.95% (at block ~220,750,000)
- Rewards are split: 65% content rewards, 15% vesting fund, 10% DHF, 10% witness pay (post-HF21)
- Content rewards use a convergent linear author curve and linear curation curve (post-HF25)
- 50% of content rewards go to curators, 50% to authors (post-HF21)
- HBD earns interest on savings balances only (post-HF25), compounded monthly, rate set by witness median
- Two conversion mechanisms exist: HBD->HIVE (3.5-day delay, no fee) and HIVE->HBD collateralized (3.5-day delay, 5% fee, 200% collateral)
- HBD supply is managed through print rate throttling and a hard price cap at 30% of market cap

---

## Inflation Schedule

### Formula
Defined in `database::process_funds()` at `database.cpp:1704`.

```
inflation_rate = max(HIVE_INFLATION_RATE_START_PERCENT - floor(head_block_num / HIVE_INFLATION_NARROWING_PERIOD),
                     HIVE_INFLATION_RATE_STOP_PERCENT)

new_hive_per_block = virtual_supply * inflation_rate / (HIVE_100_PERCENT * HIVE_BLOCKS_PER_YEAR)
```

### Constants
| Constant | Value | Meaning |
|----------|-------|---------|
| `HIVE_INFLATION_RATE_START_PERCENT` | 978 (9.78%) | Starting inflation rate |
| `HIVE_INFLATION_RATE_STOP_PERCENT` | 95 (0.95%) | Floor inflation rate |
| `HIVE_INFLATION_NARROWING_PERIOD` | 250,000 blocks | Blocks per 0.01% reduction |
| `HIVE_BLOCKS_PER_YEAR` | 10,512,000 (365×24×60×60/3) | Blocks per year at 3s intervals |

### Timeline
- **Start**: 978 (9.78%) — anchored at block 7,000,000 to 9.5% (note: the constant is 978, the comment says 9.5% at block 7M)
- **End**: 95 (0.95%) — reached at block ~220,750,000
- **Duration**: ~20.5 years of narrowing
- **Reduction**: 0.01 percentage points every 250,000 blocks (~8.68 days)

### Virtual Supply Basis (HF28 change)
Post-HF28 (`HIVE_HARDFORK_1_28_NO_DHF_HBD_IN_INFLATION`), the inflation base **excludes treasury HBD** from the virtual supply calculation:

```cpp
// HF28+:
HBD_asset hbd_supply_without_treasury = current_hbd_supply - treasury.hbd_balance;
virtual_supply_without_treasury = hbd_supply_without_treasury * median_price + current_supply;
new_hive = virtual_supply_without_treasury * current_inflation_rate / (100% * blocks_per_year);

// Pre-HF28:
new_hive = virtual_supply * current_inflation_rate / (100% * blocks_per_year);
```

This prevents treasury accumulation from inflating the inflation base.

### Distribution Splits
The newly created HIVE is split according to percentages stored in `dynamic_global_property_object`:

```cpp
content_reward  = new_hive * content_reward_percent  / 100%
vesting_reward  = new_hive * vesting_reward_percent  / 100%
dhf_new_funds   = new_hive * proposal_fund_percent   / 100%
witness_reward  = new_hive - content_reward - vesting_reward - dhf_new_funds  // remainder
```

| Era | Content | Vesting | DHF | Witness (remainder) |
|-----|---------|---------|-----|---------------------|
| Pre-HF21 (HF16+) | 75% | 15% | 0% | 10% |
| HF21+ | 65% | 15% | 10% | 10% |

**DHF funds are converted to HBD** at the current median price and deposited to the treasury account:
```cpp
new_hbd = dhf_new_funds * feed.current_median_history;
adjust_balance(treasury, new_hbd);
```

### Witness Reward Distribution
Witness pay is NOT evenly split. Each block's witness receives a weighted share:

```cpp
witness_reward *= HIVE_MAX_WITNESSES;  // 21
if (timeshare) witness_reward *= wso.timeshare_weight;
else if (miner) witness_reward *= wso.miner_weight;
else if (elected) witness_reward *= wso.elected_weight;
witness_reward /= wso.witness_pay_normalization_factor;
```

Witness reward is paid as **vesting (HP)** via `create_vesting2()`, emitting a `producer_reward_operation` virtual op.

### Pre-HF16 Inflation (Legacy)
Before HF16, inflation used a different system based on per-block APR calculations:
- `HIVE_CONTENT_APR_PERCENT` = 3875 (38.75%)
- `HIVE_CURATE_APR_PERCENT` = 3875 (38.75%)
- `HIVE_PRODUCER_APR_PERCENT` = 750 (7.5%)

These used the `calc_percent_reward_per_block<>()` template from `compound.hpp` with high-precision fixed-point arithmetic.

---

## Reward System

### Reward Pool

The reward pool is tracked in `reward_fund_object` (`reward_fund_object.hpp`). There is a single reward fund ("post") since HF17.

**Fields:**
- `reward_balance` — HIVE available to pay out
- `recent_claims` — uint128_t tracking total rshares claims (decays over time)
- `content_constant` — curve parameter (2,000,000,000,000 since HF21)
- `percent_curation_rewards` — curation share (50% since HF21)
- `percent_content_rewards` — always 100% (of what's allocated to content)
- `author_reward_curve` — `linear` since HF25 (was `convergent_linear` in HF21)
- `curation_reward_curve` — `linear` since HF25 (was `convergent_square_root` in HF21)

**Funding**: Each block, `pay_reward_funds()` adds content_reward to `reward_balance`:
```cpp
r = reward * itr->percent_content_rewards / HIVE_100_PERCENT;
rfo.reward_balance += r;
```

**Claims Decay**: Recent claims decay with a half-life:
```cpp
// HF19+: 15 day decay; HF17-HF19: 30 day decay
rfo.recent_claims -= (rfo.recent_claims * elapsed_seconds) / decay_time_seconds;
```

| Constant | Value |
|----------|-------|
| `HIVE_RECENT_RSHARES_DECAY_TIME_HF19` | 15 days |
| `HIVE_RECENT_RSHARES_DECAY_TIME_HF17` | 30 days |

### Reward Curves

Six curves are defined in `curve_id` enum (`misc_utilities.hpp`), implemented in `reward.cpp`:

| Curve | Formula | Used Since |
|-------|---------|------------|
| `quadratic` | `(rshares + s)² - s²` | Genesis |
| `bounded_curation` | `rshares × 2^64 / (2s + rshares)` | Genesis (curation) |
| `linear` | `rshares` | HF25 (both author and curation) |
| `square_root` | `√rshares` | HF19 (curation, briefly) |
| `convergent_linear` | `((rshares + s)² - s²) / (rshares + 4s)` | HF21 (author) |
| `convergent_square_root` | `rshares / √(rshares + 2s)` | HF21 (curation) |

Where `s` = `content_constant` (2×10¹² since HF21).

**Evolution of curves:**

| Hardfork | Author Curve | Curation Curve |
|----------|-------------|----------------|
| Pre-HF17 | quadratic | bounded_curation |
| HF17 | linear | square_root |
| HF21 | convergent_linear | convergent_square_root |
| HF25 | **linear** | **linear** |

### Individual Comment Reward Calculation

From `get_rshare_reward()` in `reward.cpp`:

```
claim = evaluate_reward_curve(comment.net_rshares, author_curve, content_constant)
claim = claim * reward_weight / 100%
payout = reward_fund_balance * claim / total_recent_claims
payout = min(payout, max_accepted_payout_in_hive)
if payout_in_hbd < HIVE_MIN_PAYOUT_HBD (0.020 HBD): payout = 0  // dust threshold
```

### Author vs Curator Split

```cpp
uint16_t curation_percent = get_curation_rewards_percent();
curation_tokens = reward_tokens * curation_percent / 100%;
author_tokens = reward - curation_tokens;
```

| Era | Curation % | Author % |
|-----|-----------|----------|
| Pre-HF8 | 50% | 50% |
| HF8–HF20 | 25% | 75% |
| HF21+ | **50%** | **50%** |

Source: `database.cpp:1918` — `get_curation_rewards_percent()`.

### Curation Reward Distribution

Curators receive rewards proportional to their `vote_weight` in the comment's `total_vote_weight`. From `pay_curators()` in `database_comment.cpp:129`:

```cpp
for each vote (sorted by weight descending):
    claim = max_rewards * vote.weight / total_vote_weight
    if claim > 0:
        create_vesting(voter, claim)  // paid as HP
        unclaimed_rewards -= claim
```

**Vote weight calculation** (post-HF25, from `hive_evaluator_social.cpp`):

The curation reward curve evaluates: `W(R_N) - W(R_{N-1})` where `W(R)` is the reward curve applied to cumulative positive rshares up to that vote.

With **linear** curation curve (HF25+): `vote_weight = new_rshares - old_rshares` (i.e., each vote's rshares directly).

**Early voting penalty** (HF25+, replaces reverse auction):
- Votes in first `early_voting_seconds` (24 hours): **full weight**
- Votes from 24–72 hours: weight **÷ 2**
- Votes after 72 hours: weight **÷ 8**

```cpp
if (seconds >= early_voting_seconds && early_voting_seconds) {
    if (seconds < early_voting_seconds + mid_voting_seconds)
        vote_weight /= 2;   // phase 1
    else
        vote_weight /= 8;   // phase 2
}
```

| Constant | Value |
|----------|-------|
| `HIVE_EARLY_VOTING_SECONDS_HF25` | 24 hours (86,400s) |
| `HIVE_MID_VOTING_SECONDS_HF25` | 48 hours (172,800s) |

**Pre-HF25 reverse auction** (disabled at HF25 by setting to 0):
Votes cast within `reverse_auction_seconds` of post creation had their curation weight linearly reduced to 0 at creation time.

| Hardfork | Reverse Auction Window |
|----------|----------------------|
| HF6 | 30 minutes |
| HF20 | 15 minutes |
| HF21 | 5 minutes |
| HF25 | **0 (disabled)** |

**Unclaimed curation remainder**: Pre-HF20, forwarded to author. Post-HF20, returned to reward pool (not forwarded).

### How Votes Map to rshares (HF20+)

From `hf20_vote_evaluator()` in `hive_evaluator_social.cpp`:

```
// HF28+ (stable vote):
used_mana = effective_vesting_shares * abs_weight * 86400 / HIVE_100_PERCENT

// Pre-HF28 upvote:
used_mana = voting_manabar.current_mana * abs_weight * 86400 / HIVE_100_PERCENT

max_vote_denom = vote_power_reserve_rate * HIVE_VOTING_MANA_REGENERATION_SECONDS
used_mana = ceil(used_mana / max_vote_denom)

abs_rshares = used_mana
abs_rshares -= HIVE_VOTE_DUST_THRESHOLD  // 50,000,000
abs_rshares = max(0, abs_rshares)
```

| Constant | Value |
|----------|-------|
| `HIVE_VOTING_MANA_REGENERATION_SECONDS` | 432,000 (5 days) |
| `HIVE_VOTE_DUST_THRESHOLD` | 50,000,000 |
| `HIVE_INITIAL_VOTE_POWER_RATE` | 40 |
| `HIVE_UPVOTE_LOCKOUT_SECONDS` | 43,200 (12 hours) |

**Downvote mana pool** (HF21+): Downvotes draw from a separate mana pool at 25% of upvote mana (`HIVE_DOWNVOTE_POOL_PERCENT_HF21 = 25%`). If downvote mana is exhausted, remainder comes from upvote mana.

**Lockout**: In the last 12 hours before cashout, rshares are linearly scaled down to 0:
```cpp
if (cashout_delta < HIVE_UPVOTE_LOCKOUT_SECONDS)
    abs_rshares = abs_rshares * cashout_delta / HIVE_UPVOTE_LOCKOUT_SECONDS;
```

### Cashout Process

**Cashout window**: 7 days after post creation (`HIVE_CASHOUT_WINDOW_SECONDS = 60*60*24*7`).

**Minimum payout**: `HIVE_MIN_PAYOUT_HBD = 0.020 HBD`. Posts below this threshold receive nothing.

**Step-by-step cashout** (from `process_comment_cashout()` and `cashout_comment_helper()` in `database_comment.cpp`):

1. **Decay recent claims** on the reward fund
2. **Snapshot**: Add all comments being cashed out this block to `recent_claims`
3. For each comment reaching cashout time:
   a. Calculate total HIVE reward from reward pool
   b. Split into curation tokens (50%) and author tokens (50%)
   c. **Pay curators**: each curator's share = `max_curation * vote_weight / total_vote_weight`, paid as HP
   d. **Pay beneficiaries**: deducted from author's share at specified weights
      - If beneficiary is treasury: paid as HBD (HIVE burned, HBD minted)
      - Otherwise: split between HBD and HP based on `percent_hbd`
   e. **Pay author**: remaining author tokens split between HBD and HP
      - `hbd_hive = author_tokens * percent_hbd / (2 * 100%)` — note the factor of 2
      - `vesting_hive = author_tokens - hbd_hive`
      - HBD portion is created via `create_hbd()` which respects `hbd_print_rate`
   f. Emit virtual operations: `curation_reward_operation`, `comment_benefactor_reward_operation`, `author_reward_operation`, `comment_reward_operation`
4. **Deduct** awarded HIVE from reward fund balance
5. **Remove** cashout object (post-HF19) or reset for second cashout (pre-HF17)

### HBD Print Rate and Author Payout

`create_hbd()` at `database.cpp:949` controls what fraction of "HBD portion" is actually paid as HBD vs HIVE:

```cpp
to_hbd_amount = hbd_print_rate * hive_for_hbd / 100%
to_hive_amount = hive_for_hbd - to_hbd_amount
hbd = to_hbd_amount * median_price  // convert HIVE to HBD
// to_hive_amount stays as liquid HIVE
```

The `hbd_print_rate` is updated every block in `update_virtual_supply()`:
- If HBD% ≥ `hbd_stop_percent`: print_rate = 0 (no HBD printed)
- If HBD% ≤ `hbd_start_percent`: print_rate = 100% (full HBD)
- Between: linearly interpolated

| Era | Start % | Stop % |
|-----|---------|--------|
| HF14 | 2% | 5% |
| HF20 | 9% | 10% |
| HF26 | **20%** | **20%** |

Note HF26: start == stop (20%), creating a cliff — either full HBD printing or zero.

### Beneficiaries

Beneficiaries are set via `comment_options_operation` and stored in the `comment_cashout_object`. Each beneficiary has a `weight` (basis points out of 10,000). Total beneficiary weight is deducted from the author's share proportionally.

---

## HBD Interest

### Mechanism

HBD interest is calculated using a **dollar-seconds** accumulator pattern (`hbd_interest.hpp`):

```cpp
hbd_seconds += hbd_balance * elapsed_seconds
interest = hbd_seconds / HIVE_SECONDS_PER_YEAR * hbd_interest_rate / 100%
```

**This is NOT compound interest** — it accumulates linearly within each compound interval, then resets. However, the interest is added to the balance, and subsequent intervals earn interest on the new (higher) balance, creating a form of discrete compounding.

### Compound Interval

```
HIVE_HBD_INTEREST_COMPOUND_INTERVAL_SEC = 60*60*24*30  // 30 days
```

Interest is only evaluated and paid when `(now - last_interest_payment) > 30 days`. This check happens **lazily** — triggered whenever the HBD balance is accessed (via `adjust_balance` or `adjust_savings_balance`).

### Interest Rate

- Set by **witness median**: each witness publishes `hbd_interest_rate` in their properties
- Top 21 witnesses' rates are sorted, median is taken (`witness_schedule.cpp:86`)
- Default: `HIVE_DEFAULT_HBD_INTEREST_RATE = 1000` (10% APR)
- Stored in `dynamic_global_property_object::hbd_interest_rate`
- Rate is in basis points (0-10000), representing APR

### Which Balances Earn Interest

| Balance Type | Pre-HF25 | HF25+ |
|-------------|----------|-------|
| Liquid HBD (`hbd_balance`) | **Yes** | **No** |
| Savings HBD (`savings_hbd_balance`) | **Yes** | **Yes** |

Post-HF25, only savings HBD earns interest. This was a deliberate change to encourage locking HBD in savings (3-day withdrawal delay).

### Interest Payment Flow

1. Interest accumulates as `hbd_seconds` (balance × time)
2. Every 30+ days, when balance is touched:
   - `interest = hbd_seconds / seconds_per_year * rate / 10000`
   - `hbd_balance += interest` (new HBD minted)
   - `hbd_seconds = 0` (reset accumulator)
   - `current_hbd_supply += interest` (global supply updated)
   - `interest_operation` virtual op emitted

---

## Conversions

### HBD -> HIVE (Regular Conversion)

**Operation**: `convert_operation`
**Evaluator**: `convert_evaluator::do_apply()` at `hive_evaluator_transfer.cpp:457`

**Process**:
1. User submits HBD amount
2. HBD is deducted from user's balance immediately
3. A `convert_request_object` is created with completion date = now + `HIVE_CONVERSION_DELAY`
4. After delay, `process_conversions()` executes:
   ```cpp
   amount_to_issue = convert_amount * current_median_history  // HBD -> HIVE at median price
   adjust_balance(owner, amount_to_issue)
   ```

**Key properties**:
- **No fee** — conversion at exact median price
- **Delay**: 3.5 days (`HIVE_CONVERSION_DELAY = HIVE_FEED_HISTORY_WINDOW * HIVE_FEED_INTERVAL_BLOCKS * HIVE_BLOCK_INTERVAL`)
- **Price used**: median price at **completion time** (not submission time)
- Supply adjustment: HBD burned, HIVE created

### HIVE -> HBD (Collateralized Conversion)

**Operation**: `collateralized_convert_operation` (HF25+)
**Evaluator**: `collateralized_convert_evaluator::do_apply()` at `hive_evaluator_transfer.cpp:473`

**Process**:
1. User submits HIVE as collateral
2. **Immediate HBD creation**:
   ```cpp
   for_immediate = collateral * 100% / HIVE_CONVERSION_COLLATERAL_RATIO  // 50% of collateral
   converted_hbd = multiply_with_fee(for_immediate, current_min_history, 5%)
   ```
   - Uses `current_min_history` (rolling minimum, not median) for immediate conversion
   - 5% fee applied
   - HBD immediately credited to user
3. `collateralized_convert_request_object` created with full collateral locked
4. After 3.5 days, `process_conversions()` executes:
   ```cpp
   required_hive = multiply_with_fee(converted_amount, market_median_history, 5%)
   excess_collateral = collateral - required_hive
   // Return excess collateral to user
   // Burn required_hive from supply
   ```

**Key properties**:
- **Collateral ratio**: 200% (`HIVE_CONVERSION_COLLATERAL_RATIO = 2 * HIVE_100_PERCENT`)
- **Fee**: 5% (`HIVE_COLLATERALIZED_CONVERSION_FEE = 5 * HIVE_1_PERCENT`)
- **Immediate price**: uses `current_min_history` (protective against manipulation)
- **Settlement price**: uses `market_median_history` (not the potentially corrected `current_median_history`)
- **Delay**: 3.5 days (same as regular conversion)
- **Blocked when**: `hbd_print_rate == 0` (HBD over stop percent)
- **Blocked when**: would push HBD% over `hbd_stop_percent`
- Supply adjustment: user gets HBD immediately; at settlement, HIVE is burned, excess returned

### Insufficient Collateral Edge Case

If at settlement time the required HIVE exceeds the locked collateral (extreme price move):
```cpp
if (excess_collateral < 0) {
    // system_warning_operation emitted
    required_hive = collateral;  // burn all collateral
    excess_collateral = 0;       // nothing returned
}
```

---

## DHF (Decentralized Hive Fund) Funding

### Overview

The DHF is a decentralized treasury that funds proposals voted on by stakeholders. It is managed by `dhf_processor` (`dhf_processor.cpp`).

### Funding Sources

1. **Inflation allocation**: 10% of new HIVE (post-HF21), converted to HBD and deposited to treasury (see Inflation section)
2. **Daily HIVE->HBD conversion**: Treasury's liquid HIVE is converted to HBD at 0.05% per day
3. **Beneficiary rewards**: Posts with treasury as beneficiary send rewards as HBD to treasury
4. **Direct transfers**: Anyone can transfer HBD/HIVE to the treasury account

### Daily Treasury Conversion

From `dhf_processor::convert_funds()`:
```cpp
to_convert = HIVE_PROPOSAL_CONVERSION_RATE * treasury.hive_balance / HIVE_100_PERCENT
// HIVE_PROPOSAL_CONVERSION_RATE = 5 * HIVE_1_BASIS_POINT = 0.05%
converted_hbd = to_convert * current_median_history
if (converted_hbd >= HIVE_MIN_PAYOUT_HBD):  // dust check
    treasury.hive -= to_convert
    treasury.hbd += converted_hbd
    adjust_supply(-to_convert)   // burn HIVE
    adjust_supply(+converted_hbd) // mint HBD
```

Runs every `HIVE_DAILY_PROPOSAL_MAINTENANCE_PERIOD` (24 hours on mainnet, 1 hour on testnet).

### Proposal Payment

From `dhf_processor::make_payments()`, runs every `HIVE_PROPOSAL_MAINTENANCE_PERIOD` (1 hour on mainnet):

1. **Find active proposals** (start_date ≤ now ≤ end_date)
2. **Calculate votes** for each proposal:
   - Sum of `governance_vote_power` (vesting shares) of all voters who haven't set a proxy
3. **Sort by total_votes** descending (ties broken by proposal_id ascending)
4. **Calculate maintenance budget**:
   ```cpp
   daily_budget_limit = treasury_hbd / 100  // 1% of treasury per day
   budget = daily_budget_limit * elapsed_seconds / seconds_per_day
   ```
5. **Pay proposals** in order until budget exhausted:
   ```cpp
   period_pay = elapsed_seconds * proposal.daily_pay / seconds_per_day
   if (period_pay >= remaining_budget):
       pay remaining_budget, stop
   else:
       pay period_pay, continue
   ```

### Return Proposal

There is no explicit "return proposal" in the code. Instead, proposals with `total_votes == 0` are skipped:
```cpp
if (_item.total_votes == 0) break;  // in transfer_payments()
```

The "return proposal" is a community convention — a proposal that acts as a funding threshold. All proposals below it in votes receive no funding because the budget is exhausted by proposals ranked above (including the return proposal which returns funds to treasury).

### Key Constants

| Constant | Value |
|----------|-------|
| `total_amount_divider` | 100 (1% of treasury per day) |
| `HIVE_PROPOSAL_MAINTENANCE_PERIOD` | 3600s (1 hour) on mainnet |
| `HIVE_DAILY_PROPOSAL_MAINTENANCE_PERIOD` | 86400s (24 hours) on mainnet |
| `HIVE_PROPOSAL_CONVERSION_RATE` | 0.05% (5 basis points) |

---

## Vesting Mechanics (Power Up / Power Down)

### Power Up (HIVE -> VESTS)

**Operation**: `transfer_to_vesting_operation`
**Evaluator**: `transfer_to_vesting_evaluator::do_apply()` at `hive_evaluator_transfer.cpp:292`

**Conversion rate**:
```cpp
vesting_share_price = total_vesting_shares / total_vesting_fund_hive
new_vests = hive_amount * vesting_share_price
```

From `get_vesting_share_price()` in `global_property_object.hpp`:
```cpp
if (total_vesting_fund_hive == 0 || total_vesting_shares == 0)
    return price(1000000 VESTS, 1000 HIVE)  // initial ratio: 1000 VESTS per HIVE
else
    return price(total_vesting_shares, total_vesting_fund_hive)
```

**Note**: The VESTS/HIVE ratio increases over time as vesting rewards are added to the pool without creating new VESTS. This means each VEST becomes worth more HIVE over time.

**Delayed voting** (HF24+): After power-up, the new vesting shares are subject to a 30-day voting delay to prevent instant influence purchases.

### Power Down (VESTS -> HIVE)

**Operation**: `withdraw_vesting_operation`
**Evaluator**: `withdraw_vesting_evaluator::do_apply()` at `hive_evaluator_transfer.cpp:327`

**Setup**:
```cpp
vesting_withdraw_rate = requested_vests / HIVE_VESTING_WITHDRAW_INTERVALS  // 13 installments
if (vesting_withdraw_rate == 0) vesting_withdraw_rate = 1;  // minimum 1 satoshi
// HF21+: round up to ensure full amount is paid
if (rate * intervals < requested) rate += 1;
next_vesting_withdrawal = now + HIVE_VESTING_WITHDRAW_INTERVAL_SECONDS  // 7 days
```

**Processing** (weekly, from `process_vesting_withdrawals()` in `database_vesting.cpp:111`):

Each week:
1. Calculate `to_withdraw` = min(vesting_withdraw_rate, remaining)
2. Process withdraw routes (up to `HIVE_MAX_WITHDRAW_ROUTES = 10`):
   - `auto_vest` routes: VESTS transferred directly (no conversion)
   - Regular routes: VESTS converted to HIVE at `vesting_share_price`
3. Remainder (not routed): converted to HIVE, credited to account
4. Global pools updated: `total_vesting_fund_hive -= converted_hive`, `total_vesting_shares -= converted_vests`
5. Emit `fill_vesting_withdraw_operation` virtual ops

**Cancel power down**: Set `vesting_shares = 0` in the operation.

| Constant | Value |
|----------|-------|
| `HIVE_VESTING_WITHDRAW_INTERVALS` | 13 (HF16+) |
| `HIVE_VESTING_WITHDRAW_INTERVALS_PRE_HF_16` | 104 |
| `HIVE_VESTING_WITHDRAW_INTERVAL_SECONDS` | 604,800 (7 days, = `HIVE_CASHOUT_WINDOW_SECONDS`) |
| `HIVE_MAX_WITHDRAW_ROUTES` | 10 |

### Reward Vesting Price

For reward balance operations (claiming rewards), a different price is used that accounts for pending rewards:
```cpp
reward_vesting_price = (total_vesting_shares + pending_rewarded_vesting_shares) /
                       (total_vesting_fund_hive + pending_rewarded_vesting_hive)
```

---

## Price Feed

### Feed Collection

Updated every `HIVE_FEED_INTERVAL_BLOCKS` (1200 blocks = 1 hour on mainnet), from `update_median_feed()` at `database.cpp:2399`:

1. Collect feeds from all scheduled witnesses whose feed is less than `HIVE_MAX_FEED_AGE_SECONDS` (7 days) old
2. Require minimum `HIVE_MIN_FEEDS = HIVE_MAX_WITNESSES/3 = 7` valid feeds
3. Sort feeds, take median

### Feed History

The `feed_history_object` maintains:
- `price_history` — deque of hourly median feeds
  - Window: `HIVE_FEED_HISTORY_WINDOW = 84` entries (12×7 = 3.5 days)
  - Pre-HF16: `HIVE_FEED_HISTORY_WINDOW_PRE_HF_16 = 168` entries (24×7 = 7 days)
- `current_median_history` — median of the price history (may be artificially adjusted upward by hard cap)
- `market_median_history` — true median without hard cap adjustment
- `current_min_history` — minimum of history (used for collateralized conversion)
- `current_max_history` — maximum of history

### HBD Hard Cap (Haircut Rule)

When HBD as a percentage of combined market cap exceeds the hard limit, `current_median_history` is artificially increased to make HBD "worth less" in conversion terms:

```
min_price = (100% - limit%) × hbd_supply HBD per (limit% × hive_supply) HIVE
if min_price > current_median_history:
    current_median_history = min_price  // OVERRIDE
    // market_median_history is NOT changed
```

| Era | Hard Limit |
|-----|-----------|
| Pre-HF26 | 10% |
| HF26+ | **30%** |

**Effect**: When the cap is hit, the artificial price makes conversions from HBD->HIVE less favorable, discouraging conversion attacks.

**HF24 change**: Treasury HBD is excluded from `calculate_HBD_percent()` calculations:
```cpp
hbd_supply -= treasury.hbd_balance;
if (hbd_supply < 0) hbd_supply = 0;
```

### HBD Print Rate (Soft Throttle)

Separate from the hard cap, the `hbd_print_rate` (0–10000) controls what fraction of "HBD" in payouts is actually printed as HBD vs paid as HIVE:

```
percent_hbd = hbd_as_hive / virtual_supply  (as percentage of market cap)

if percent_hbd >= hbd_stop_percent:  print_rate = 0  (no HBD printed)
if percent_hbd <= hbd_start_percent: print_rate = 100%  (full HBD)
between: linearly interpolated
```

---

## Block Processing Order

From `_apply_block()` at `database.cpp:2325`:

```
1. clear_expired_orders()
2. clear_expired_delegations()
3. update_witness_schedule()
4. update_median_feed()
5. update_virtual_supply()           // price may have changed
6. clear_null_account_balance()
7. consolidate_treasury_balance()
8. process_funds()                   // INFLATION
9. process_conversions()             // HBD↔HIVE completions
10. process_comment_cashout()        // REWARD PAYOUTS
11. process_vesting_withdrawals()    // POWER DOWN installments
12. process_savings_withdraws()
13. process_subsidized_accounts()
14. pay_liquidity_reward()           // (deprecated since HF12)
15. update_virtual_supply()          // cover HBD changes
16. account_recovery_processing()
17. expire_escrow_ratification()
18. process_decline_voting_rights()
19. process_proposals()              // DHF PAYMENTS
20. process_delayed_voting()
21. remove_expired_governance_votes()
22. process_recurrent_transfers()
23. RC finalization
24. process_hardforks()
```

---

## Economic Constants Reference

| Constant | Value | Purpose |
|----------|-------|---------|
| `HIVE_INFLATION_RATE_START_PERCENT` | 978 (9.78%) | Starting annual inflation |
| `HIVE_INFLATION_RATE_STOP_PERCENT` | 95 (0.95%) | Minimum annual inflation |
| `HIVE_INFLATION_NARROWING_PERIOD` | 250,000 blocks | Blocks per 0.01% reduction |
| `HIVE_BLOCKS_PER_YEAR` | 10,512,000 | At 3s block interval |
| `HIVE_CONTENT_REWARD_PERCENT_HF21` | 6500 (65%) | Content's share of inflation |
| `HIVE_VESTING_FUND_PERCENT_HF16` | 1500 (15%) | Vesting fund's share |
| `HIVE_PROPOSAL_FUND_PERCENT_HF21` | 1000 (10%) | DHF's share |
| `HIVE_100_PERCENT` | 10,000 | Basis for percentage math |
| `HIVE_1_PERCENT` | 100 | 1% in BPS |
| `HIVE_CASHOUT_WINDOW_SECONDS` | 604,800 (7 days) | Post payout window |
| `HIVE_MIN_PAYOUT_HBD` | 0.020 HBD | Dust threshold |
| `HIVE_VESTING_WITHDRAW_INTERVALS` | 13 | Weekly installments (13 weeks) |
| `HIVE_VESTING_WITHDRAW_INTERVAL_SECONDS` | 604,800 (7 days) | Between installments |
| `HIVE_VOTING_MANA_REGENERATION_SECONDS` | 432,000 (5 days) | Full mana regen time |
| `HIVE_VOTE_DUST_THRESHOLD` | 50,000,000 | Minimum rshares for non-dust vote |
| `HIVE_DOWNVOTE_POOL_PERCENT_HF21` | 2500 (25%) | Downvote mana pool |
| `HIVE_INITIAL_VOTE_POWER_RATE` | 40 | Vote power reserve rate |
| `HIVE_DEFAULT_HBD_INTEREST_RATE` | 1000 (10%) | Default HBD APR |
| `HIVE_HBD_INTEREST_COMPOUND_INTERVAL_SEC` | 2,592,000 (30 days) | Interest compound interval |
| `HIVE_SECONDS_PER_YEAR` | 31,536,000 | Seconds in 365 days |
| `HIVE_CONVERSION_DELAY` | 302,400s (3.5 days) | HBD->HIVE delay |
| `HIVE_COLLATERALIZED_CONVERSION_DELAY` | 302,400s (3.5 days) | HIVE->HBD delay |
| `HIVE_CONVERSION_COLLATERAL_RATIO` | 20,000 (200%) | Required collateral |
| `HIVE_COLLATERALIZED_CONVERSION_FEE` | 500 (5%) | Conversion fee |
| `HIVE_FEED_INTERVAL_BLOCKS` | 1,200 (1 hour) | Feed update frequency |
| `HIVE_FEED_HISTORY_WINDOW` | 84 (3.5 days) | Price history entries |
| `HIVE_MIN_FEEDS` | 7 (21/3) | Minimum valid feeds |
| `HIVE_MAX_FEED_AGE_SECONDS` | 604,800 (7 days) | Maximum feed age |
| `HIVE_HBD_HARD_LIMIT` | 3000 (30%) | Hard cap on HBD% |
| `HIVE_HBD_START_PERCENT_HF26` | 2000 (20%) | Start throttling HBD |
| `HIVE_HBD_STOP_PERCENT_HF26` | 2000 (20%) | Stop printing HBD |
| `HIVE_EARLY_VOTING_SECONDS_HF25` | 86,400 (24 hours) | Full curation window |
| `HIVE_MID_VOTING_SECONDS_HF25` | 172,800 (48 hours) | Half curation window |
| `HIVE_RECENT_RSHARES_DECAY_TIME_HF19` | 15 days | Reward claims decay |
| `HIVE_CONTENT_CONSTANT_HF21` | 2,000,000,000,000 | Curve parameter |
| `HIVE_PROPOSAL_MAINTENANCE_PERIOD` | 3,600 (1 hour) | DHF payment interval |
| `HIVE_DAILY_PROPOSAL_MAINTENANCE_PERIOD` | 86,400 (24 hours) | Treasury conversion interval |
| `HIVE_PROPOSAL_CONVERSION_RATE` | 5 basis points (0.05%) | Daily HIVE->HBD rate for treasury |
| `HIVE_MAX_WITHDRAW_ROUTES` | 10 | Max power-down destinations |
| `HIVE_UPVOTE_LOCKOUT_SECONDS` | 43,200 (12 hours) | Pre-cashout lockout |

---

## Key Discoveries

1. **HF26 HBD print rate cliff**: `hbd_start_percent == hbd_stop_percent == 20%`. This means there's no gradual throttle — HBD printing is either 100% or 0%, creating a binary switch at exactly 20% market cap.

2. **HF28 inflation base change**: Treasury HBD is excluded from virtual supply for inflation calculation, preventing a feedback loop where treasury accumulation increases inflation.

3. **Collateralized conversion uses different prices at different stages**: Immediate conversion uses `current_min_history` (most conservative), while settlement uses `market_median_history` (true median, not the potentially hard-cap-corrected one). This is deliberate to prevent gaming.

4. **Interest is NOT truly compound**: The formula `hbd_seconds / seconds_per_year * rate` calculates simple interest within each 30-day period. Compounding only occurs because the interest is added to the principal for the next period.

5. **Curation weight phase system (HF25)**: The early voting bonus (24h full, 24-72h half, 72h+ one-eighth) replaced the reverse auction mechanism. This incentivizes voting within the first 24 hours.

6. **DHF budget is 1% of treasury per day**: The `total_amount_divider = 100` constant means only 1% of treasury HBD can be distributed daily, regardless of proposal requests. This is a conservative safety limit.

7. **Witness pay is NOT equal**: Despite being "10% of inflation", each witness's actual pay depends on their schedule type (elected/timeshare/miner) and the normalization factor. Elected witnesses get the most consistent pay.

8. **HBD interest moved to savings-only at HF25**: Before HF25, liquid HBD earned interest. Post-HF25, only savings HBD earns interest. This was a major economic policy change to encourage HBD locking.

9. **Dust vote threshold is per-vote, not per-account**: `HIVE_VOTE_DUST_THRESHOLD = 50,000,000` is subtracted from each vote's rshares individually. Small accounts can effectively have zero-impact votes.

10. **Unclaimed curation rewards behavior changed at HF20**: Pre-HF20, unclaimed curation rewards were forwarded to the author. Post-HF20, they are NOT forwarded (effectively returned to the reward pool).

---

## Code References

| Topic | File | Key Lines |
|-------|------|-----------|
| Inflation/distribution | `database.cpp` | `process_funds()` at line 1704 |
| Reward curves | `util/reward.cpp` | `evaluate_reward_curve()` at line 34 |
| Comment cashout | `database_comment.cpp` | `process_comment_cashout()` at line 379 |
| Curation payment | `database_comment.cpp` | `pay_curators()` at line 129 |
| Author payment | `database_comment.cpp` | `cashout_comment_helper()` at line 197 |
| HBD creation | `database.cpp` | `create_hbd()` at line 949 |
| Vote -> rshares | `hive_evaluator_social.cpp` | `hf20_vote_evaluator()` at line 605 |
| Curation weight | `hive_evaluator_social.cpp` | Lines 779–829 |
| HBD interest | `database.cpp` | `adjust_balance(HBD)` accrual logic at line 3186 |
| Savings interest | `database.cpp` | `adjust_savings_balance(HBD)` at line 3265 |
| Interest formula | `hbd_interest.hpp` | `evaluate_hbd_interest()` at line 9 |
| Conversions | `database_conversion.cpp` | `process_conversions()` at line 34 |
| Collateralized convert | `hive_evaluator_transfer.cpp` | `collateralized_convert_evaluator::do_apply()` at line 473 |
| DHF payments | `util/dhf_processor.cpp` | `make_payments()` at line 238 |
| DHF budget | `util/dhf_processor.cpp` | `calculate_maintenance_budget()` at line 145 |
| DHF conversion | `util/dhf_processor.cpp` | `convert_funds()` at line 325 |
| Power up | `hive_evaluator_transfer.cpp` | `transfer_to_vesting_evaluator::do_apply()` at line 292 |
| Power down setup | `hive_evaluator_transfer.cpp` | `withdraw_vesting_evaluator::do_apply()` at line 327 |
| Power down processing | `database_vesting.cpp` | `process_vesting_withdrawals()` at line 111 |
| Vesting price | `global_property_object.hpp` | `get_vesting_share_price()` at line 87 |
| Price feed | `database.cpp` | `update_median_feed()` at line 2399 |
| HBD hard cap | `database.cpp` | Lines 2461–2509 in `update_median_feed()` |
| HBD print rate | `database.cpp` | `update_virtual_supply()` at line 2868 |
| HBD % calculation | `database.cpp` | `calculate_HBD_percent()` at line 2843 |
| Compound math | `compound.hpp` | `calc_percent_reward<>()` template |
| Reward fund object | `reward_fund_object.hpp` | Full struct definition |
| Feed history object | `feed_history_object.hpp` | Full struct definition |
| HF parameter changes | `database_hardfork.cpp` | Lines 311-492 |

---

## Discrepancies and Potential Issues

1. **Content constant name mismatch**: `HIVE_CONTENT_CONSTANT_HF0` is used as the default in `reward_fund_object`, but the actual value used since HF21 is `HIVE_CONTENT_CONSTANT_HF21 = 2,000,000,000,000`. They are actually the same value, but the naming is confusing.

2. **Savings withdraw has no interest payment**: When a savings withdrawal completes, the HBD is simply transferred. Interest is calculated lazily when the savings balance is next adjusted, not at withdrawal time. This means a withdrawal that drains the entire savings balance will trigger interest calculation on the `adjust_savings_balance(-amount)` call.

3. **DHF maintenance drift**: The code comments note (`dhf_processor.cpp:219`): "shifting from current time instead of proper maintenance time causes drift when maintenance block was missed." This is a known issue documented inline.

4. **Collateralized conversion and insufficient collateral**: If HIVE price drops >50% between submission and settlement, the collateral is insufficient. The system burns all collateral but the created HBD is already in circulation — this is a form of uncovered HBD creation (acknowledged by design, protected by the 200% collateral requirement).

5. **HBD print rate cliff at HF26**: With start == stop == 20%, there's no gradual throttling. This is either intentional (simplification) or a potential issue if fine-grained control is needed.

---

## Open Questions

1. **Unclaimed curation rewards post-HF20**: Verified — they stay in the reward pool. `pay_curators()` reduces `curation_tokens` (by reference) by the unclaimed amount. `claimed_reward = author_tokens + curation_tokens` thus excludes unclaimed curation. Since `funds[fund_id].hive_awarded += claimed_reward`, only actually paid rewards are deducted from the fund. The unclaimed portion remains in `reward_balance` for future payouts.

2. **Is the 30-day delayed voting for power-up the same as the HBD savings 3-day withdrawal?** No — these are completely different mechanisms. The 30-day delayed voting only affects governance vote weight, not the ability to power down.

3. **Exact block where inflation reaches 0.95%**: Solving `978 - floor(block/250000) = 95` gives `floor(block/250000) = 883`, so the first block at 0.95% is block `883 × 250000 = 220,750,000`.
