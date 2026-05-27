# Hive Resource Credits (RC) Reference

Source: hive-core release 1.28.6. RC is non-consensus (enforced at mempool only, not during block processing).

---

## Overview

Every Hive account has a regenerating RC mana bar. Transactions consume RC proportional to their resource usage. No fees are burned -- RC regenerates over 5 days.

- **Max RC** = effective VESTS - delegated_rc + rc_adjustment + received_rc
- **Effective VESTS** = own VESTS + received VEST delegations - delegated VESTS
- **RC payer** = account providing the first required authority in the transaction
- Non-consensus: blocks containing RC-violating transactions are accepted during replay; enforcement is only at mempool/block-production time

---

## Resource Types

| Name | What It Measures | Budget Period | Half-Life | Budget Size |
|------|-----------------|---------------|-----------|-------------|
| `resource_history_bytes` | Serialized tx size (bytes) | 30 days | 15 days | 37,500,000,000 |
| `resource_new_accounts` | Subsidized account creation | ~30,000s | 5 days | 797 (witness-set) |
| `resource_market_bytes` | Tx size for market ops | 30 days | 16 hours | 6,250,000,000 |
| `resource_state_bytes` | RAM usage (hour-bytes) | 30 days | 15 days | 37,623,913,512,960 |
| `resource_execution_time` | CPU time (nanoseconds) | 1 hour | 1 hour | 48,000,000,000 |

**Market operations** (charged market_bytes): transfer, transfer_to_vesting, limit_order_create/create2, recurrent_transfer.

**`resource_new_accounts` is special**: its weight always equals the sum of all other weights, making subsidized account creation perpetually expensive. Its dynamics are witness-controlled.

---

## State Byte Tiers

State bytes are measured in **hour-bytes** (object size x expected lifetime in hours).

| Tier | Multiplier (hours) | Meaning | Example |
|------|-------------------|---------|---------|
| Temporary | 1 | Known expiration, charged per actual hour | Vote (7-day cashout = 168h) |
| Lasting | 21,900 | ~2.5 year average lifetime | Long-lived objects |
| Persistent | 43,800 | ~5 year assumed lifetime | Accounts, comments (base) |

Example: A 100-byte persistent object costs `100 * 43,800 = 4,380,000` hour-bytes in resource units.

---

## Cost Calculation

```
For each resource type i:

  1. Count raw usage:
     usage[i] = resource-specific measurement (bytes, count, hour-bytes, ns)

  2. Scale by resource_unit:
     usage[i] *= resource_unit[i]      # 10 for most, 100000 for new_accounts, 100 for market

  3. Compute global RC regen rate:
     rc_regen = total_vests / 144000   # per block (total_vests / (432000s / 3s))

  4. Compute per-resource share of RC regen:
     pool_regen_share[i] = rc_regen * weight[i] / sum_of_weights

  5. Price from rational curve:
     cost[i] = (pool_regen_share * coeff_a >> shift) * usage[i] / (coeff_b + current_pool[i]) + 1

  6. Total:
     total_cost = sum(cost[i]) + flood_surcharge (if applicable)
```

Key behavior: as a resource pool drains (high demand), price increases. The `+1` ensures no operation is ever free.

**Differential discount**: Operations modifying existing state (e.g. key rotation via account_update) subtract existing object size, so only the net change is charged.

---

## Mana Regeneration

```
dt = now - last_update_time
regen_amount = max_mana * dt / 432000    # 432000s = 5 days
new_mana = min(current_mana + regen_amount, max_mana)
```

- **Full regen**: 0 to max in exactly 5 days (432,000 seconds)
- **Lazy evaluation**: mana is only recalculated when needed
- **Mana can go negative**: use_mana allows saturating subtraction
- **No cap on catch-up**: inactive accounts get full regen on first use regardless of how long they were idle

---

## RC Delegation

Broadcast as `custom_json` with id `"rc"`, requires **posting authority**.

```json
{
  "from": "delegator",
  "delegatees": ["user1", "user2"],
  "max_rc": 5000000000
}
```

| Rule | Detail |
|------|--------|
| Max delegatees per op | 100 |
| Minimum delegation | `(account_creation_fee / 3)` converted to VESTS equivalent |
| Remove delegation | Set `max_rc = 0` |
| Re-delegation of received RC | Not allowed -- can only delegate from own effective VESTS |
| Effect on delegator mana | Creating/increasing immediately deducts from current_mana |
| Removing delegation | Does **not** return mana to delegator (prevents pump-and-spend attack) |
| Receiver effect | Mana immediately adjusted by the delta |
| Delegation overflow | If delegator loses VESTS below delegated_rc, delegations are auto-removed in order; may be deferred across blocks |

---

## Special Cases

### Subsidized Operations
- `recover_account_operation` with single key/account authority and <= 2 signatures: **zero RC cost**. Ensures stolen accounts can always be recovered.

### Flood Surcharge
When mempool exceeds 20 blocks of queued transactions:
```
surcharge = (blocks_in_mempool - 20) * flood_surcharge * rc_cost / HIVE_100_PERCENT
```
**Exempt**: Top elected witnesses' `feed_publish`, `witness_update`, and `witness_set_properties` operations.

### Witness Exemption
Elected witnesses' operational transactions (feed publishing, witness updates) bypass the flood surcharge during congestion.

### New Account RC Adjustment
New accounts receive a permanent `rc_adjustment` equal to the creation fee converted to VESTS, giving them immediate RC capacity. Pre-HF20 accounts received a fixed adjustment of ~2020.75 VESTS.

### Metadata Not Charged
`json_metadata` on accounts is not charged for state bytes (plugin-dependent, would cause RC divergence between nodes).

---

## API Endpoints

| Endpoint | Returns |
|----------|---------|
| `rc_api.find_rc_accounts` | RC mana, max_rc, delegated/received RC for specific accounts |
| `rc_api.list_rc_accounts` | Paginated RC account list (limit 1000) |
| `rc_api.list_rc_direct_delegations` | RC delegations from an account |
| `rc_api.get_resource_params` | Resource names, dynamics params, size info |
| `rc_api.get_resource_pool` | Current pool levels and fill percentages |
| `rc_api.get_rc_stats` | Daily RC statistics |
| `rc_api.get_rc_operation_stats` | Per-operation cost breakdown |

**Checking if a user can afford an operation**: Call `rc_api.find_rc_accounts` for the payer, compare `rc_manabar.current_mana` (after regeneration) against the estimated cost.
