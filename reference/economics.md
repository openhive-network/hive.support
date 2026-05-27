# Hive Economic Model Reference

Source: hive-core release 1.28.6. All formulas verified against source code.

---

## Inflation

Current rate: ~9.78%, decreasing 0.01% every 250,000 blocks (~8.68 days). Floor: 0.95% at block 220,750,000 (~March 2037).

```
inflation_rate = max(978 - floor(head_block_num / 250000), 95)   // basis points
new_hive = virtual_supply * inflation_rate / (10000 * 10512000)  // per block
```

HF28+: `virtual_supply` excludes treasury HBD to prevent feedback loop.

**Distribution (post-HF21):**

| Recipient | Share | Paid As |
|-----------|-------|---------|
| Content rewards | 65% | Added to reward pool |
| Vesting fund | 15% | HP (increases VESTS/HIVE ratio) |
| DHF (treasury) | 10% | Converted to HBD at median price |
| Witnesses | 10% (remainder) | HP, weighted by schedule type |

---

## Reward Distribution

Single reward fund ("post") since HF17. Reward pool tracks `reward_balance` (HIVE) and `recent_claims` (uint128, 15-day half-life decay).

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
| Claims decay | 15-day half-life (HF19+) |

### Author Payout Split

Author's 50% is split between HBD and HP based on `percent_hbd` setting and `hbd_print_rate`:

```
hbd_hive = author_tokens * percent_hbd / (2 * 10000)
vesting_hive = author_tokens - hbd_hive
actual_hbd = hbd_hive * hbd_print_rate / 10000   // rest paid as liquid HIVE
```

---

## Curation

Curators split 50% of post rewards proportional to their `vote_weight / total_vote_weight`. Paid as HP.

### Vote Timing Weight (HF25+)

| Window | Weight |
|--------|--------|
| 0-24 hours | Full (1x) |
| 24-72 hours | Half (1/2x) |
| 72+ hours | One-eighth (1/8x) |

Last 12 hours before cashout: rshares linearly scaled to 0 (lockout).

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
// Evaluated lazily when balance is accessed; resets every 30 days
```

| Parameter | Value |
|-----------|-------|
| Compound interval | 30 days |
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
| Blocked when | `hbd_print_rate == 0` (HBD over 20% of market cap) |

If price drops >50% during delay, all collateral is burned (insufficient collateral edge case -- HBD already in circulation).

---

## HBD Supply Management

### Print Rate (Soft Throttle)

```
hbd_percent = hbd_as_hive / virtual_supply
HF26+: start == stop == 20%  --> binary switch (100% or 0% HBD printing)
```

No gradual throttle since HF26. HBD payouts switch entirely to HIVE when HBD exceeds 20% of market cap.

### Hard Cap (Haircut Rule)

At 30% of market cap (HF26+), `current_median_history` is artificially inflated to make HBD-to-HIVE conversions less favorable. `market_median_history` (true median) is unaffected.

Treasury HBD is excluded from HBD% calculation (HF24+).

---

## DHF Funding

### Funding Sources
1. 10% of inflation (converted to HBD)
2. Daily 0.05% of treasury HIVE converted to HBD
3. Beneficiary rewards directed to treasury
4. Direct transfers

### Proposal Payments

```
daily_budget = treasury_hbd / 100            // 1% of treasury per day
hourly_budget = daily_budget * 3600 / 86400  // paid every hour
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

Initial ratio: 1000 VESTS per HIVE. Ratio increases over time as vesting rewards add HIVE without creating VESTS.

30-day delayed voting after power-up (HF24+) -- affects governance weight only.

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
| `current_max_history` | Rolling maximum |

---

## Block Processing Order (Economic Operations)

```
1. clear_expired_orders
2. update_witness_schedule
3. update_median_feed         -- price update
4. update_virtual_supply      -- recalculate virtual supply
5. process_funds              -- INFLATION (create new HIVE)
6. process_conversions        -- HBD/HIVE conversion settlements
7. process_comment_cashout    -- REWARD PAYOUTS
8. process_vesting_withdrawals -- POWER DOWN installments
9. process_savings_withdraws
10. update_virtual_supply     -- cover HBD changes
11. process_proposals         -- DHF PAYMENTS
12. process_recurrent_transfers
```

---

## Notable Design Details

- **HF26 print rate cliff**: `start == stop == 20%` creates binary on/off, no gradual throttle
- **Collateralized conversion uses different prices**: immediate = `current_min_history` (conservative), settlement = `market_median_history` (true median, not hard-cap-corrected)
- **Interest is discrete compound**: simple within each 30-day period, compound across periods
- **Dust threshold is per-vote**: 50M rshares subtracted from each vote individually; small accounts can have zero-impact votes
- **Witness pay is unequal**: weighted by schedule type (elected/timeshare/miner) and normalization factor
