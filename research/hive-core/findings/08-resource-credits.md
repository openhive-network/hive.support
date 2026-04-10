# Findings: Resource Credits (RC) System

## Summary

Resource Credits (RC) are Hive's rate-limiting mechanism, introduced at HF20 to replace the legacy bandwidth system. RC determines whether an account can broadcast a transaction based on its stake (VESTS). Instead of transaction fees, Hive uses a regenerating mana system: each transaction consumes RC proportional to its resource usage across 5 resource types, and RC regenerates over 5 days. The system is **non-consensus** — nodes enforce it in the mempool and during block production, but blocks containing transactions from RC-depleted accounts are still accepted during replay.

Key characteristics:
- **No transaction fees**: RC is consumed but not destroyed; it regenerates
- **5 resource types**: history bytes, new accounts, market bytes, state bytes, execution time
- **Demand-responsive pricing**: cost adapts to usage via pool dynamics
- **RC = function of stake**: max RC equals effective VESTS (adjusted for delegations)
- **5-day regeneration**: same as voting mana (`HIVE_VOTING_MANA_REGENERATION_SECONDS = 432000`)

**Code references**: Core logic in `libraries/chain/rc/`, headers in `libraries/chain/include/hive/chain/rc/`, API in `libraries/plugins/apis/rc_api/`.

---

## RC Overview

### Conceptual Model

1. Every account has an **RC mana bar** that tracks current RC and last update time
2. Maximum RC is derived from the account's effective VESTS (plus adjustments and delegations)
3. When a transaction is broadcast, the system:
   a. Identifies the **RC payer** (first operation's required authority)
   b. **Counts resources** consumed by each resource type
   c. **Computes the RC cost** using per-resource price curves and pool states
   d. **Deducts RC** from the payer's mana bar (rejects if insufficient)
4. RC regenerates linearly from current level to max over 5 days

### Non-Consensus Status

RC is explicitly non-consensus. The code contains:
```cpp
FC_TODO( "Add || db.has_hardfork( X ) to make RC part of consensus since X" );
```

This means:
- **`is_in_control()` (producing/validating new tx)**: RC is strictly enforced; insufficient RC → transaction rejected
- **`is_processing_block()`**: Insufficient RC is logged but the transaction is accepted
- **Replay**: RC is calculated but not enforced
- The `last_max_rc` field is described as "for bug catching with RC code, can be removed once RC becomes part of consensus"

**Source**: `rc_utility.cpp:547-581`

---

## Resource Types

Five resource types defined in `resource_count.hpp`:

```cpp
enum rc_resource_types {
  resource_history_bytes,    // 0
  resource_new_accounts,     // 1
  resource_market_bytes,     // 2
  resource_state_bytes,      // 3
  resource_execution_time    // 4
};
```

| Resource | What It Measures | Budget Period | Budget | Half-Life | Resource Unit |
|----------|-----------------|---------------|--------|-----------|---------------|
| `resource_history_bytes` | Transaction size (network/storage) | 30 days | 37,500,000,000 | 15 days | 10 |
| `resource_new_accounts` | Subsidized account creation tokens | ~30,000s | 797 (witness-controlled) | 5 days | 100,000 |
| `resource_market_bytes` | Tx size for market operations | 30 days | 6,250,000,000 | 16 hours | 100 |
| `resource_state_bytes` | RAM state usage (hour-bytes) | 30 days | 37,623,913,512,960 | 15 days | 10 |
| `resource_execution_time` | CPU time (nanoseconds) | 1 hour | 48,000,000,000 | 1 hour | 10 |

**Source**: `libraries/jsonball/data/resource_parameters.json`

### Resource Measurement Details

#### history_bytes
Simply the serialized transaction size in bytes. Added for all transactions.

#### new_accounts
Incremented by 1 for `claim_account_operation` with `fee == 0` (subsidized account claims). Not charged for paid claims.

#### market_bytes
Transaction size is counted for transactions containing "market" operations:
- `transfer_operation`
- `transfer_to_vesting_operation`
- `limit_order_create_operation`
- `limit_order_create2_operation`
- `recurrent_transfer_operation`

#### state_bytes
Measured in **hour-bytes** — the product of:
- Object size in bytes (from `resource_sizes.cpp`)
- Expected lifetime in hours

Three durability tiers:
- `TEMPORARY_STATE_BYTE = 1` — objects with known expiration
- `LASTING_STATE_BYTE = 5 * 365 * 12 = 21,900` — long-lived objects (2.5 year average)
- `PERSISTENT_STATE_BYTE = 5 * 365 * 24 = 43,800` — permanent objects (5 year assumption)

Examples:
- Account creation: `(616+144) bytes * PERSISTENT + 312 bytes * PERSISTENT` = very expensive
- Comment: `96 bytes * PERSISTENT + 192 bytes * TEMPORARY * 7 * 24` (7-day cashout)
- Vote: `144 bytes * TEMPORARY * 7 * 24` (7-day cashout)

**Source**: `resource_sizes.cpp:45-165`

#### execution_time
Pre-measured execution times (in nanoseconds) from benchmark results. Composed of:
`validate_time + exec_time + pre_rc_time + post_rc_time [+ automatic_processing_time]`

Plus per-transaction overhead:
- `transaction_time = 6622 ns` (dupe check + tapos + post-rc)
- `verify_authority_time = 94165 ns` per signature

Examples:
| Operation | Execution Time (ns) |
|-----------|---------------------|
| `transfer` | 5,999 |
| `vote` | 18,312 |
| `comment` | 66,178 |
| `account_create` | 38,710 |
| `custom_json` | 1,509 |
| `delegate_rc` | 75,000 (over custom_json) |

**Source**: `resource_sizes.cpp:167-242`

---

## RC Cost Calculation

### Step-by-Step Formula

For a transaction, the RC cost is computed as follows:

#### Step 1: Count Resources

For each resource type, count how much the transaction uses (`resource_count.cpp`):

```
usage[history_bytes] = tx_serialized_size
usage[new_accounts] = count of subsidized claim_account_operations
usage[market_bytes] = tx_size if any market op, else 0
usage[state_bytes] = sum(object_size * lifetime_hours) + tx_base_size * expiration_hours
usage[execution_time] = sum(op_times) + transaction_time + verify_authority_time * num_signatures
```

Additionally, a **discount system** subtracts existing state usage for operations that modify (rather than create) state objects. For example, `account_update` that swaps a key doesn't allocate new state, so the existing authority's size is subtracted first.

**Source**: `resource_count.cpp:136-164` (discount), `resource_count.cpp:572-631` (counting)

#### Step 2: Apply Resource Units

Each raw usage count is multiplied by the resource's `resource_unit`:

```cpp
usage_info->usage[i] *= int64_t( params.resource_dynamics_params.resource_unit );
```

**Source**: `rc_utility.cpp:305`

#### Step 3: Calculate Per-Resource RC Share

The global RC regeneration rate is split among resources based on their popularity (usage weight):

```cpp
int64_t total_vests = dgpo.get_total_vesting_shares().amount.value;
int64_t rc_regen = total_vests / (HIVE_RC_REGEN_TIME / HIVE_BLOCK_INTERVAL);
// rc_regen = total_vests / (432000 / 3) = total_vests / 144000
// This is RC regenerated per block globally

int64_t pool_regen_share = (rc_regen * pool_weight) / sum_of_weights;
```

**Source**: `rc_utility.cpp:292-306`

#### Step 4: Compute Individual Resource Cost

For each resource, the cost is calculated using the price curve:

```cpp
int64_t cost = compute_cost(curve_params, current_pool, resource_count, pool_regen_share);
```

The price curve formula (from `rc_utility.cpp:243-284`):

```
cost = (pool_regen_share * coeff_a >> shift) * resource_count / (coeff_b + current_pool) + 1
```

Where:
- `coeff_a` and `shift`: Derived from curve generation, encode `tau/k` (characteristic time / price sensitivity)
- `coeff_b`: `inelasticity_threshold * pool_eq` — below this pool level, price rises rapidly
- `current_pool`: Current pool level (higher pool → lower price)
- `+1`: Ensures minimum cost of 1 RC per resource used

**Key behavior**: As the pool drains (more demand), price increases. When pool is at equilibrium, prices are moderate. When pool goes negative/zero, price is at maximum (`coeff_b` prevents division by zero).

**Source**: `rc_utility.cpp:243-284`, `rc_curve.cpp:32-98`

#### Step 5: Sum All Resource Costs

```cpp
total_cost = sum(cost[i] for i in resources)
```

#### Step 6: Deduct from Payer

```cpp
account.rc_manabar.use_mana(total_cost + surcharge);
```

**Source**: `rc_utility.cpp:799-831` (finalize_transaction)

### Subsidized Operations

`recover_account_operation` with a single key/account authority and ≤ 2 signatures is fully subsidized (free). This is to ensure stolen accounts can always be recovered.

**Source**: `resource_count.cpp:534-546`, `resource_count.cpp:606-611`

### Flood Surcharge

When the mempool has more blocks-worth of transactions than `flood_level` (default 20), a surcharge is applied:

```cpp
surcharge = (blocks_in_mempool - flood_level) * flood_surcharge * rc_cost / HIVE_100_PERCENT;
```

Top elected witnesses' feed_publish, witness_update, and witness_set_properties operations are exempt from the surcharge (privileged).

**Source**: `rc_utility.cpp:505-537`

---

## Mana Bar / Regeneration

### Structure

```cpp
struct manabar {
  int64_t    current_mana     = 0;
  uint32_t   last_update_time = 0;
};

struct manabar_params {
  int64_t    max_mana    = 0;
  uint32_t   regen_time  = 0;  // HIVE_RC_REGEN_TIME = 432000 seconds (5 days)
};
```

### Regeneration Formula

Regeneration is **linear**. When `regenerate_mana()` is called:

```
dt = now - last_update_time
regen_amount = (max_mana * dt) / regen_time
new_mana = min(current_mana + regen_amount, max_mana)
last_update_time = now
```

Using 128-bit arithmetic to prevent overflow:

```cpp
uint128_t max_mana_dt = uint64_t(max_mana) * dt;
uint64_t u_regen = max_mana_dt / regen_time;
new_current_mana = min(current_mana + u_regen, max_mana);
```

**Source**: `manabar.hpp:42-68`

### Key Properties

- **Full regeneration**: 0 → max takes exactly 5 days (432,000 seconds)
- **Lazy evaluation**: Mana is only regenerated on-demand (before operations that read/modify it)
- **RC uses `skip_cap_regen = true`**: The dt cap (`dt > regen_time → dt = regen_time`) is skipped for RC, meaning very old accounts that haven't transacted in months get full regeneration on first use
- **Mana can go negative**: `use_mana()` uses saturating subtraction and allows negative values (capped at `int64_t::min()`)

### Maximum RC Calculation

```cpp
share_type get_maximum_rc(bool only_delegable = false) const {
  share_type total = get_effective_vesting_shares().amount - delegated_rc;
  if (only_delegable == false)
    total += rc_adjustment + received_rc;
  return total;
}
```

Where:
- `get_effective_vesting_shares()` = own VESTS + received VEST delegations - delegated VESTS
- `delegated_rc` = RC delegated to others
- `rc_adjustment` = compensation for account creation fee (VESTS equivalent)
- `received_rc` = RC delegated from others

**Source**: `account_object.hpp:115-121`

### Relation to Voting Mana

Both RC and voting mana use the same `manabar` struct and same regeneration time (`HIVE_VOTING_MANA_REGENERATION_SECONDS = 5 days`). However:
- Voting mana's `max_mana` = effective vesting shares
- RC mana's `max_mana` = effective vesting shares - delegated_rc + rc_adjustment + received_rc
- Voting mana also has a separate downvote manabar with `max_mana` scaled by `downvote_pool_percent`

**Source**: `manabar.hpp:104-141`

---

## RC Delegation

### Operation

RC delegation uses a custom operation framework via `delegate_rc_operation`:

```cpp
struct delegate_rc_operation : public base_operation {
  account_name_type             from;
  flat_set<account_name_type>   delegatees;  // up to HIVE_RC_MAX_ACCOUNTS_PER_DELEGATION_OP (100)
  int64_t                       max_rc = 0;  // 0 = remove delegation
  extensions_type               extensions;
};
```

This is packed inside `custom_json_operation` with id `"rc"`.

**Source**: `hive_custom_operations.hpp:8-17`

### How It Works (HF26+)

1. Requires **posting authority** of `from`
2. Minimum delegation: `(account_creation_fee / 3) * vesting_share_price` (in VESTS equivalent)
3. `max_rc = 0` removes an existing delegation
4. Can delegate to multiple accounts in one operation
5. **Cannot re-delegate received RC**: Only `min(max_delegable_rc, current_mana)` can be delegated, where `max_delegable_rc = effective_vesting_shares - delegated_rc` (excludes received_rc and rc_adjustment)
6. Creating a new delegation **immediately deducts** from delegator's current_mana
7. Removing/reducing a delegation does **not** return mana to the delegator (prevents pumping)
8. Receiver's mana is **immediately adjusted** by the delta (positive or negative)

**Source**: `rc_utility.cpp:26-110`

### Delegation Overflow

When an account loses VESTS (power down, delegation removed) and their `delegated_rc > effective_vesting_shares`:

1. System detects "delegation overflow" during `update_account_after_vest_change()`
2. Delegations are removed in order (by ID) to reduce overflow
3. If removal limit is hit, remaining removals are deferred via `rc_expired_delegation_object`
4. Deferred removals are processed in subsequent blocks via `handle_expired_delegations()`
5. While expired delegations exist, the account **cannot create new RC delegations**

**Source**: `rc_utility.cpp:401-443`, `rc_utility.cpp:598-677`

### State Objects

```cpp
class rc_direct_delegation_object {
  account_id_type from;
  account_id_type to;
  uint64_t        delegated_rc = 0;
};
```

Indexed by `(from, to)` for efficient lookups.

**Source**: `rc_objects.hpp:179-192`

---

## Resource Dynamics

### Pool System

Each resource type has an independent pool that tracks available capacity. The pool dynamics follow a differential equation model:

```
new_pool = pool - decay + budget - usage
```

Per block:
- **Budget**: Fixed amount of new resources added per block (`budget_per_time_unit`)
- **Decay**: Proportional to current pool level (pulls toward equilibrium)
- **Usage**: Resources consumed by transactions in this block

**Source**: `rc_utility.cpp:734-797`

### Decay Formula

```cpp
int64_t decay = (decay_per_time_unit * current_pool) >> decay_per_time_unit_denom_shift;
```

With `HIVE_RD_DECAY_DENOM_SHIFT = 36`, the decay is a fraction of the pool per block.

**Source**: `rd.cpp:23-41`

### Pool Equilibrium

At equilibrium (where budget = decay):

```
pool_eq = ceil((budget << decay_denom_shift) / decay_per_time_unit)
```

The pool oscillates around this equilibrium. When usage exceeds the budget, the pool drops below equilibrium, making the resource more expensive.

**Source**: `rd.cpp:80-118`

### Price Curve Parameters

Generated from resource dynamics and curve generation params:

```
coeff_b = inelasticity_threshold * pool_eq
```

Default `inelasticity_threshold = 1/128`, so `coeff_b ≈ pool_eq/128`.

```
coeff_a = (a * (1-u)) / (decay_rate * u)
```

Where `a = 37/1000` (default for new_accounts) or `150/10000 = 15/1000` (default for others), and `u = 1/2`.

**Source**: `rc_curve.cpp:32-98`, `rc_curve.hpp:11-21`

### Resource Weights (Popularity)

Each block, resource weights are recalculated based on usage in the last 24-hour window:

```cpp
resource_weights[i] = usage_in_window[i] * HIVE_100_PERCENT / budget_per_time_unit;
```

The `resource_new_accounts` weight is always set to `sum_of_resource_weights` (100% share), making it always as expensive as the sum of all other resources.

The weight determines each resource's share of the global RC regeneration, which affects pricing:
```
pool_regen_share[i] = global_rc_regen * weight[i] / sum_of_weights
```

More popular resources get a larger share, which dilutes their price increase. Less popular resources get a smaller share, making even small usage relatively expensive.

**Source**: `rc_objects.hpp:80-95`

### Usage Buckets

Usage is tracked in a sliding window of 24 hourly buckets (`HIVE_RC_BUCKET_TIME_LENGTH = 3600s`, `HIVE_RC_WINDOW_BUCKET_COUNT = 24`). When the current bucket expires, the oldest bucket's usage is subtracted and the bucket is reused.

**Source**: `rc_objects.hpp:216-256`, `rc_utility.cpp:746-796`

---

## Account Creation RC

### Two Paths for Account Creation

1. **Paid creation** (`claim_account` with fee):
   - Fee = `wso.median_props.account_creation_fee` (witness-set)
   - Increments `pending_claimed_accounts` on creator
   - Fee goes to null account (burned)
   - The fee is converted to VESTS equivalent and stored as `rc_adjustment` on the new account

2. **Subsidized creation** (`claim_account` with fee = 0):
   - Consumes from the `resource_new_accounts` pool
   - Requires subsidy available globally and from the producing witness
   - Only elected witnesses can include subsidized claims in blocks

**Source**: `hive_evaluator_account.cpp:402-462`

### RC Adjustment

When a new account is created (post-HF20), the creation fee paid is converted to its VESTS equivalent and stored as `rc_adjustment`:

```cpp
rc_adjustment_from_fee = (fee_for_rc_adjustment * vesting_share_price).amount.value;
```

This gives the new account RC capacity as if it had that many VESTS, ensuring new accounts can immediately transact. The adjustment is permanent and cannot be reclaimed by the creator.

For accounts existing before HF20, all received:
```cpp
account.rc_adjustment = HIVE_RC_HISTORICAL_ACCOUNT_CREATION_ADJUSTMENT; // 2020748973
// = 2020.748973 VESTS ≈ 1.000 HIVE at HF20 activation
```

**Source**: `hive_evaluator_account.cpp:130-153`, `database_hardfork.cpp:406-414`

### New Accounts Pool

The `resource_new_accounts` pool is special:
- Its dynamics parameters come from the **witness schedule** (`account_subsidy_rd`), not the JSON parameters file
- The RC pool value is synchronized with `dgpo.available_account_subsidies` (consensus value) each block
- Precision: `HIVE_ACCOUNT_SUBSIDY_PRECISION = 10000` (HIVE_100_PERCENT)
- Budget and decay are witness-configurable

**Source**: `rc_utility.cpp:770-779`, `rc_utility.cpp:833-851`

---

## RC State Objects

### Per-Account (in `account_object`)

| Field | Type | Description |
|-------|------|-------------|
| `rc_manabar` | `manabar` | Current RC mana and last update timestamp |
| `rc_adjustment` | `share_type` | Permanent RC bonus from account creation fee |
| `delegated_rc` | `share_type` | Total RC delegated out to others |
| `received_rc` | `share_type` | Total RC delegated in from others |
| `last_max_rc` | `share_type` | Last computed max RC (debug/bug-catching) |

**Source**: `account_object.hpp:192, 215-218`

### Global Singletons

| Object | Description |
|--------|-------------|
| `rc_resource_param_object` | Per-resource dynamics params and price curve params |
| `rc_pool_object` | Current pool levels, usage windows, weights, budgets |
| `rc_stats_object` (×2) | Pending and archive daily statistics |

### Per-Delegation

| Object | Fields |
|--------|--------|
| `rc_direct_delegation_object` | `from`, `to`, `delegated_rc` |
| `rc_expired_delegation_object` | `from`, `expired_delegation` (overflow amount) |

### Usage Tracking

| Object | Description |
|--------|-------------|
| `rc_usage_bucket_object` (×24) | Hourly buckets of per-resource usage |

**Source**: `rc_objects.hpp`

---

## RC API Endpoints

The `rc_api` plugin exposes:

| Endpoint | Description |
|----------|-------------|
| `rc_api.get_resource_params` | Returns resource names, dynamics params, size info |
| `rc_api.get_resource_pool` | Returns current pool levels and fill percentages |
| `rc_api.find_rc_accounts` | Returns RC info for specific accounts |
| `rc_api.list_rc_accounts` | Lists RC accounts (paginated, limit 1000) |
| `rc_api.list_rc_direct_delegations` | Lists RC delegations from an account |
| `rc_api.get_rc_stats` | Returns daily RC statistics |
| `rc_api.get_rc_operation_stats` | Returns per-operation cost breakdown |

The `rc_account_api_object` returned by `find_rc_accounts` contains:
- `account`, `rc_manabar`, `max_rc_creation_adjustment` (VESTS), `max_rc`, `delegated_rc`, `received_delegated_rc`

**Source**: `rc_api.hpp`, `rc_api.cpp`

---

## RC Statistics System

### Daily Reports

The system generates periodic reports (default: once per day, `HIVE_BLOCKS_PER_DAY`):

- **Per-operation stats**: Count, usage, cost for each operation type (plus multi-op transactions)
- **Per-payer-rank stats**: 8 ranks based on account size, tracking:
  - Total usage and cost
  - How many payers had < 5%, < 10%, < 20% of max RC
  - How many payers couldn't afford average vote/comment/transfer

Report types: NONE, MINIMAL (basic), REGULAR (with ops), FULL (with detailed usage)

**Source**: `rc_stats.hpp`, `rc_utility.cpp:142-230`

### Rolling Hash Stamp

Statistics include a rolling SHA-256 hash of payer RC mana values, providing a fingerprint for comparing RC state across nodes.

**Source**: `rc_objects.hpp:147`

---

## Key Discoveries

1. **RC is non-consensus**: This is a deliberate design with a TODO to make it consensus in a future hardfork. Currently, a block producer can include transactions that violate RC limits.

2. **Differential usage discount**: Operations that modify existing state (like `account_update` swapping a key) get a discount for the state already in use, so only the _net change_ in state bytes is charged. This prevents excessive charging for routine key rotations.

3. **`resource_new_accounts` is special**: Its weight is always 100% of sum_of_resource_weights, making it perpetually as expensive as all other resources combined. Its dynamics are also witness-controlled rather than hardcoded.

4. **Recover account is subsidized**: Single-key recovery operations with ≤ 2 signatures are completely free (zero RC cost), ensuring stolen accounts can always be recovered regardless of RC state.

5. **RC delegation doesn't return mana on removal**: When you stop delegating RC, the delegator does NOT get the mana back. Only the max_rc changes. This prevents a "pumping" attack where you delegate, the receiver spends, then you un-delegate to recover your mana.

6. **Flood prevention surcharge**: During mempool congestion (>20 blocks queued), RC costs are multiplied, but elected witnesses' operational transactions are exempt.

7. **State bytes use hour-byte accounting**: A 100-byte object lasting 1 year costs 876,000 resource units (100 * 365 * 24). Persistent objects assume 5-year lifetime, making account creation very expensive in state bytes.

8. **The price curve is a rational function**: `cost = A * usage / (B + pool)`. As pool depletes toward 0, cost rises toward `A * usage / B` (the maximum price). As pool grows, cost decreases. The `+1` rounding ensures no operation is ever truly free.

---

## Code References

| File | Purpose |
|------|---------|
| `include/hive/chain/rc/rc_objects.hpp` | All RC state objects (pool, params, stats, delegations, buckets) |
| `include/hive/chain/rc/rc_utility.hpp` | `resource_credits` class — main RC logic interface |
| `include/hive/chain/rc/resource_count.hpp` | Resource type enum, count_resources declarations |
| `include/hive/chain/rc/resource_sizes.hpp` | State object sizes and execution times |
| `include/hive/chain/rc/rc_curve.hpp` | Price curve generation params |
| `include/hive/chain/rc/rc_export_objects.hpp` | Per-tx and per-block RC info structs |
| `include/hive/chain/rc/rc_stats.hpp` | Per-operation and per-payer statistics |
| `include/hive/chain/util/manabar.hpp` | Mana bar regeneration (shared by RC and voting) |
| `include/hive/chain/util/rd_dynamics.hpp` | Resource dynamics params and pool decay |
| `include/hive/chain/util/rd_setup.hpp` | User/system param conversion |
| `rc/rc_utility.cpp` | Core implementation: cost computation, mana management, delegation, block finalization |
| `rc/resource_count.cpp` | Resource counting per-operation, differential discount |
| `rc/resource_sizes.cpp` | Concrete size/time values for all operations |
| `rc/rc_curve.cpp` | Price curve parameter generation |
| `rc/resource_user.cpp` | RC payer determination |
| `util/rd.cpp` | `rd_apply()`, `rd_compute_pool_decay()`, `rd_setup_dynamics_params()` |
| `database_hardfork.cpp:336-416` | HF20 RC initialization |
| `libraries/jsonball/data/resource_parameters.json` | Initial resource pool parameters |
| `plugins/apis/rc_api/rc_api.cpp` | RC API implementation |
| `protocol/include/.../hive_custom_operations.hpp` | `delegate_rc_operation` definition |

---

## Discrepancies and Potential Issues

1. **Non-consensus RC acceptance**: The comment at `rc_utility.cpp:547` shows awareness that accepting RC-violating transactions during block processing is a gap. A rogue witness could include spam transactions.

2. **`last_max_rc` drift detection**: The code at `rc_utility.cpp:331-343` detects when `max_rc` changes without a proper operation (indicating a bug). On testnet this asserts; on mainnet it only logs a warning.

3. **Custom operation timing estimate**: The `delegate_rc_time = 75000` is noted as a rough estimate: "once we have real uses of RC delegation we can correct actual average time consumption" (`resource_sizes.cpp:227-228`).

4. **Metadata not charged**: Account metadata (json_metadata) is explicitly NOT charged for state bytes because it's plugin-dependent and could cause RC differences between nodes (`resource_count.cpp:205-207`).

5. **Fixed vs dynamic sizes**: `resource_sizes.cpp` uses `#define USE_FIXED_SIZE` which hardcodes object sizes. There's machinery to compare with actual runtime sizes, but it's disabled for production.

---

## Open Questions

1. **When will RC become consensus?** The TODO has been present since HF20. Making it consensus requires resolving edge cases where nodes could disagree on RC state.

2. **Execution time measurements**: The times in `resource_sizes.cpp` are from specific benchmark runs. How often are they re-measured? Changes in hived's internal implementation could make them inaccurate.

3. **Resource dynamics parameter tuning**: The initial parameters (from `resource_parameters.json`) were set at HF20. Only `resource_new_accounts` is witness-adjustable. Are the other resource parameters still optimal?

4. **Pool weight asymmetry for `resource_new_accounts`**: Setting its weight to always equal the sum of all other weights means account creation is always disproportionately expensive relative to other resources. This is intentional but creates a permanent 2x multiplier on the total global RC allocation to account creation.
