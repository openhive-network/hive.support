# Hive Economic Model Reference

Source: hive-core release 1.28.8. All formulas verified against source code.

---

## Inflation

Started at 9.78% (HF16 model), decreasing 0.01% every 250,000 blocks (~8.68 days): at block B the rate is `max(978 - floor(B / 250000), 95)` basis points, so about 5.73% around block 101.3M (HF28, November 2025) and about 5.4% at 110M blocks. Floor: 0.95% at block 220,750,000 (~March 2037). Read the live value from the formula and the current head block, never from a cached "current rate".

```
inflation_rate = max(978 - floor(head_block_num / 250000), 95)   // basis points
new_hive = virtual_supply * inflation_rate / (10000 * 10512000)  // per block
```

HF28+: `virtual_supply` excludes treasury HBD to prevent feedback loop.

**Distribution (post-HF21):**

| Recipient | Share | Paid As |
|-----------|-------|---------|
| Content rewards | 65% | Added to reward pool |
| Vesting fund | 15% | Added to the vesting fund without new VESTS (each VEST gains HIVE value) |
| DHF (treasury) | 10% | Converted to HBD at median price |
| Witnesses | 10% (remainder) | HP, weighted by schedule type |

---

## Reward Distribution

Single reward fund ("post"): since 1.28.8 it exists from genesis (at 1.28.7 HF17 created it), and the decaying `recent_claims` payout model applies since HF17. Reward pool tracks `reward_balance` (HIVE) and `recent_claims` (uint128; each block subtracts `recent_claims * elapsed / 15 days`, HF19+).

### Post Payout Calculation

```
claim = rshares                          // linear curve (HF25+)
payout = reward_balance * claim / recent_claims
if payout < 0.020 HBD equivalent: payout = 0   // dust threshold
```

| Parameter | Value |
|-----------|-------|
| Cashout window | 7 days |
| Dust threshold | 0.020 HBD |
| Author/curator split | 50% / 50% (HF21+) |
| Reward curve | Linear (both author and curation, HF25+) |
| Claims decay | `recent_claims * elapsed / 15 days` subtracted each block (HF19+; 30 days HF17-HF19) |

### Author Payout Split

Author's 50% is split between HBD and HP based on `percent_hbd` setting and `hbd_print_rate`:

```
hbd_hive = author_tokens * percent_hbd / (2 * 10000)
vesting_hive = author_tokens - hbd_hive
to_hbd = hbd_hive * hbd_print_rate / 10000   // converted to HBD at the median price; the rest of hbd_hive is paid as HIVE
```

Since HF17 the HBD, the HIVE and the VESTS go to the author's reward balances and must be claimed (`claim_reward_balance_operation`).

---

## Curation

Curators split 50% of post rewards proportional to their `vote_weight / total_vote_weight`. Paid as HP.

### Vote Timing Weight (HF25+)

| Window | Weight |
|--------|--------|
| 0-24 hours | Full (1x) |
| 24-72 hours | Half (1/2x) |
| 72+ hours | One-eighth (1/8x) |

Last 12 hours before cashout (HF20+): the rshares of every vote, downvotes included, scale linearly to 0; no vote is rejected. Before HF20 a vote that raised the voter's rshares on the comment was rejected in that window (from HF17; in the last minute from HF7).

### Votes to rshares (HF28+ stable vote)

```
used_mana = effective_vesting_shares * abs_weight * 86400 / 10000
used_mana = ceil(used_mana / (vote_power_reserve_rate * 432000))
rshares = max(0, used_mana - 50000000)   // dust threshold per vote
```

| Parameter | Value |
|-----------|-------|
| Mana regeneration | 5 days (432,000s) |
| Vote dust threshold | 50,000,000 rshares |
| Downvote pool | 25% of upvote mana (separate pool, HF21+) |
| Unclaimed curation | Stays in reward pool (HF20+) |

---

## HBD Interest

Paid on **savings HBD only** (HF25+). Rate set by witness median (basis points APR).

```
hbd_seconds += balance * elapsed_seconds
interest = hbd_seconds / 31536000 * rate / 10000    // simple within interval
// paid (and hbd_seconds reset) at the first savings-HBD adjustment, even a zero one, more than 30 days after the last payment; an account never paid has no 30-day wait (database.cpp:3317-3337)
```

| Parameter | Value |
|-----------|-------|
| Compound interval | Over 30 days: interest is paid at the first savings-HBD adjustment more than 30 days after the last payment (`database.cpp:3321`) |
| Eligible balance | Savings only (HF25+) |
| Default rate | 10% APR (1000 bps) |
| Type | Simple within interval, discrete compound across intervals |

---

## Conversions

### HBD to HIVE (convert_operation)

| Property | Value |
|----------|-------|
| Fee | None |
| Delay | 3.5 days |
| Price used | Median at completion time |
| Effect | HBD burned, HIVE created |

### HIVE to HBD (collateralized_convert_operation, HF25+)

| Property | Value |
|----------|-------|
| Fee | 5% |
| Collateral | 200% (user locks 2x HIVE) |
| Immediate payout | 50% of collateral converted to HBD at rolling minimum price minus fee |
| Settlement | 3.5 days later; excess collateral returned, required HIVE burned |
| Blocked when | `hbd_print_rate == 0` (HBD share at or above 20% since HF26), or the new HBD would push the HBD share over `hbd_stop_percent` |

If at settlement the required HIVE exceeds the collateral (the market median HIVE price at settlement is below half the minimum price used at the request; the 5% fee applies at both steps and cancels, `hive_evaluator_transfer.cpp:510-511`, `database_conversion.cpp:108-109`), all collateral is burned (insufficient collateral edge case -- HBD already in circulation).

---

## HBD Supply Management

### Print Rate (Soft Throttle)

```
hbd_percent = hbd_as_hive / virtual_supply
HF26+: start == stop == 20%  --> binary switch (100% or 0% HBD printing)
```

No gradual throttle since HF26. HBD payouts switch entirely to HIVE when the HBD share reaches 20% (`hbd_percent >= hbd_stop_percent`).

### Hard Cap (Haircut Rule)

At 30% of market cap (HF26+), `current_median_history` is artificially inflated to make HBD-to-HIVE conversions less favorable. `market_median_history` (true median) is unaffected.

Treasury HBD is excluded from the HBD share that sets the print rate since HF24 (`calculate_HBD_percent`) and from the hard-cap computation since HF25.

---

## DHF Funding

### Funding Sources
1. 10% of inflation (converted to HBD)
2. Daily 0.05% of treasury HIVE converted to HBD (HF24+)
3. Beneficiary rewards directed to treasury
4. Direct transfers (HBD; since HF24 also HIVE, converted to HBD at the median price on arrival)
5. Proposal creation fees (10 HBD, plus 1 HBD per day of runtime beyond 60 days since HF24)

### Proposal Payments

```
daily_budget = treasury_hbd / 100                 // 1% of treasury per day
budget = daily_budget * passed_seconds / 86400    // passed_seconds since the last hourly maintenance run (last_budget_time, reset by every run, global_property_object.hpp:121-125), normally 3600
```

Proposals sorted by total stake-weighted votes (descending). Paid in order until budget exhausted. Proposals with 0 votes are skipped. "Return proposal" is a convention (not code) that acts as a funding threshold.

| Parameter | Value |
|-----------|-------|
| Payment interval | 1 hour |
| Daily budget | 1% of treasury HBD |
| Treasury HIVE conversion | 0.05%/day to HBD |

---

## Vesting / Power Down

### Power Up (HIVE to HP)

```
vesting_share_price = total_vesting_shares / total_vesting_fund_hive
new_vests = hive_amount * vesting_share_price
```

With empty pools the price is 1 VESTS per HIVE (`VEST_price(1000000, 1000)` in satoshis, the genesis price); HF1 multiplied all VESTS by 1,000,000 (Part 01, Key Discovery 10). Since then the VESTS-per-HIVE ratio falls over time as vesting rewards add HIVE without creating VESTS, though not strictly: claimed reward VESTS enter the pools at the account's own ratio (Part 07, section Power Up).

30-day delayed voting after power-up (HF24+), effectively just over 29 to 30 days since new VESTS are kept in daily buckets (Part 14, Key Discovery 6) -- affects governance weight only.

### Power Down (HP to HIVE)

```
weekly_installment = requested_vests / 13    // rounded up (HF21+)
hive_per_installment = installment_vests / vesting_share_price
```

| Parameter | Value |
|-----------|-------|
| Installments | 13 weekly (HF16+) |
| Interval | 7 days |
| Max withdraw routes | 10 |
| Cancel | Set vesting_shares = 0 |

---

## Price Feed

Witnesses publish HIVE/HBD price feeds. Updated hourly (every 1,200 blocks).

```
Collect feeds from scheduled witnesses (max age: 7 days)
Require >= 7 valid feeds
Median of hourly medians over 3.5-day window (84 entries)
```

| Field | Description |
|-------|-------------|
| `current_median_history` | Median price (may be adjusted by hard cap) |
| `market_median_history` | True median (no hard cap adjustment) |
| `current_min_history` | Rolling minimum (used for collateralized conversion) |
| `current_max_history` | Rolling maximum; the hard-cap correction can raise it (`database.cpp:2524-2525`) |

---

## Block Processing Order (Economic Operations)

```
1. clear_expired_orders
2. clear_expired_delegations  -- return VESTS of reduced or removed delegations after their return period
3. update_witness_schedule
4. update_median_feed         -- price update
5. update_virtual_supply      -- recalculate virtual supply
6. clear_null_account_balance -- burn what `null` holds (HF14+)
7. consolidate_treasury_balance -- old treasury balances to the current treasury (HF24+)
8. process_funds              -- INFLATION (create new HIVE)
9. process_conversions        -- HBD/HIVE conversion settlements
10. process_comment_cashout   -- REWARD PAYOUTS
11. process_vesting_withdrawals -- POWER DOWN installments
12. process_savings_withdraws
13. update_virtual_supply     -- cover HBD changes
14. process_proposals         -- DHF PAYMENTS
15. process_recurrent_transfers
```

Economic steps only; the full per-block order is in Part 07, section Block Processing Order.

---

## Notable Design Details

- **HF26 print rate cliff**: `start == stop == 20%` creates binary on/off, no gradual throttle
- **Collateralized conversion uses different prices**: immediate = `current_min_history` (conservative), settlement = `market_median_history` (true median, not hard-cap-corrected)
- **Interest is discrete compound**: simple within each accrual period, which ends at the first savings-HBD adjustment more than 30 days after the last payment; it compounds only at those payments
- **Dust threshold is per-vote**: 50M rshares subtracted from each vote individually; small accounts can have zero-impact votes
- **Witness pay is unequal**: weighted by schedule type (elected/timeshare/miner) and normalization factor
