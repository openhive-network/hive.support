# Hive Resource Credits (RC) Reference

Source: hive-core release 1.28.8. RC is non-consensus until HF29 (defined in 1.28.8 code, inactive on mainnet): a node enforces it for new transactions, for its re-applied pending transactions and while it produces a block, not when it applies or replays a block (Part 08, section Non-Consensus Status).

---

## Overview

Every Hive account has a regenerating RC mana bar. Transactions consume RC proportional to their resource usage. No fees are burned -- RC regenerates over 5 days.

- **Max RC** = effective VESTS - delegated_rc + rc_adjustment + received_rc
- **Effective VESTS** = own VESTS + received VEST delegations - delegated VESTS, minus the next power-down installment while a power-down is active
- **RC payer** = decided by the first operation that yields a payer (operations yielding none are skipped, `resource_user.cpp:54-65`): `witness_set_properties` -> its `owner`, `recover_account` -> `account_to_recover`, `witness_block_approve` -> its `witness`, any other operation -> the first account of its required active, else owner, else posting authorities (`resource_user.cpp:17-46`)
- Non-consensus until HF29: when the payer lacks RC, a new transaction (API or P2P) is rejected, a re-applied pending transaction is dropped and a transaction the node tries to put into a block it produces is skipped; a block being applied (from P2P or sync, or the node's own produced block) or replayed is accepted, the shortfall logged from HF26. HF29 (defined in 1.28.8 code, inactive on mainnet): the RC payer and balance checks assert in every mode, which makes RC part of consensus (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet); Part 08, section Non-Consensus Status)

---

## Resource Types

| Name | What It Measures | Budget Period | Half-Life | Budget Size |
|------|-----------------|---------------|-----------|-------------|
| `resource_history_bytes` | Serialized tx size (bytes) | 30 days | 15 days | 37,500,000,000 |
| `resource_new_accounts` | Subsidized account creation | 30,000 s | ~4.76 days at the default witness decay 347321 (the JSON and a code comment say 5 days; Part 17, The rd math) | 797 (witness-set) |
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
     usage[i] *= resource_unit[i]      # 1 for most, 10000 for new_accounts, 10 for market_bytes

  3. Compute global RC regen rate:
     rc_regen = total_vests / 144000   # per block (total_vests / (432000s / 3s))

  4. Compute per-resource share of RC regen:
     pool_regen_share[i] = rc_regen * weight[i] / sum_of_weights

  5. Price from rational curve:
     cost[i] = (((pool_regen_share * coeff_a) >> shift) + 1) * usage[i] / (coeff_b + max(current_pool[i], 0)) + 1
     # only when pool_regen_share > 0; zero usage costs 0 (rc_utility.cpp:272-276, :319-321; Part 08)

  6. Total:
     total_cost = sum(cost[i])   # recorded as the transaction's rc_cost; the flood surcharge (below) is taken from mana on top (rc_utility.cpp:844-845, :563)
```

Key behavior: as a resource pool drains (high demand), price increases.

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
- **Mana floors at 0**: `use_mana` default `min_mana` is `std::numeric_limits<uint64_t>::min()` = 0; accounts force-charged in a block end at 0, never negative
- **No cap on catch-up**: inactive accounts get full regen on first use regardless of how long they were idle

---

## RC Delegation

Broadcast as `custom_json` with id `"rc"`, requires **posting authority**: `required_posting_auths` = [`from`] and `required_auths` empty, since the inner operation's authorities must equal the outer ones (`generic_custom_operation_interpreter.hpp:207-211`). Its `json` field is the operation's name and body (the object form `{"type": "delegate_rc_operation", "value": {...}}` is accepted too):

```json
["delegate_rc", {
  "from": "delegator",
  "delegatees": ["user1", "user2"],
  "max_rc": 5000000000
}]
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
| Delegation overflow | If the delegator's effective VESTS fall below its `delegated_rc`, its delegations are reduced or removed in delegatee account id order; removals past the per-change limit continue in later blocks (Part 08, section Delegation Overflow) |

---

## Special Cases

### Subsidized Operations
- `recover_account_operation` as the transaction's only operation, with a new owner authority of a single key or account and <= 2 signatures: **zero RC cost**. A multisig owner authority is not subsidized (Part 08, Key Discovery 6).

### Flood Surcharge
When the mempool holds more than `flood_level` blocks of pending transactions (pending size / `maximum_block_size`; node option `rc-flood-level`, default 20), a new or re-applied pending transaction pays (never one in a block being produced or applied):
```
surcharge = (blocks_in_mempool - flood_level) * flood_surcharge * rc_cost / HIVE_100_PERCENT   # flood_surcharge: node option rc-flood-surcharge, default 10000
```
**Exempt**: a single-operation transaction with `feed_publish`, `witness_update` or `witness_set_properties` whose payer's witness object is marked `elected` (`schedule == witness_object::elected`); the check runs only while the mempool is over the flood level (Part 08, section RC Cost Calculation, Step 7; Part 15, Key Discovery 8).

### Witness Exemption
Only the single-operation transactions above are exempt: a witness operation bundled with any other operation pays the surcharge. A node that accepts such an exempt transaction as new puts it at the front of its popped-transaction list (`database.cpp:647-653`), which is re-applied before the other pending transactions when the pending list is rebuilt (`db_with.hpp:199-210`; Part 15, Key Discovery 8).

### New Account RC Adjustment
Accounts created since HF20 receive a permanent `rc_adjustment`: the account creation fee in force when the account is created, converted to VESTS at that moment (for a claimed account the fee at `create_claimed_account`, not the fee paid for the claim), giving them immediate RC capacity. Accounts that existed at HF20 received a fixed adjustment of ~2020.75 VESTS.

### Metadata Not Charged
`json_metadata` and `posting_json_metadata` of accounts are not charged for state bytes: whether they are stored depends on the optional `metadata` plugin, so a differential charge could differ between nodes, and a full charge on every update would overcharge (code comments; Part 08, Key Discovery 5). The transaction size still counts as history bytes.

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
