# Findings: Resource Credits (RC) System

## Summary

Resource Credits (RC) are Hive's rate-limiting mechanism, introduced at HF20 to replace the legacy bandwidth system. RC determines whether an account can broadcast a transaction based on its stake (VESTS). Instead of transaction fees, Hive uses a regenerating mana system: each transaction consumes RC proportional to its resource usage across 5 resource types, and RC regenerates linearly over 5 days. The system is **non-consensus** — nodes enforce it only when accepting new transactions (mempool and block production); blocks containing transactions from RC-depleted accounts are still accepted during block processing and replay.

Key characteristics:
- **No transaction fees**: RC is consumed but not destroyed; it regenerates
- **5 resource types**: history bytes, new accounts, market bytes, state bytes, execution time
- **Demand-responsive pricing**: cost adapts to usage via pool dynamics (a rational price curve with a characteristic time derived from a 15-day / 16-hour / 1-hour half-life depending on resource)
- **RC = function of stake**: max RC equals effective VESTS adjusted for delegations and the permanent creation-fee bonus
- **5-day regeneration** (`HIVE_RC_REGEN_TIME = HIVE_VOTING_MANA_REGENERATION_SECONDS = 432000`)
- **RC payer = first operation's required authority**: deterministically the first account whose active/owner/posting authority is required by the first operation (two special-case overrides)

**Code references**: Core logic in `libraries/chain/rc/`, headers in `libraries/chain/include/hive/chain/rc/`, API in `libraries/plugins/apis/rc_api/`, initial parameters at `libraries/jsonball/data/resource_parameters.json` (transformed at build time by `programs/build_helpers/hive_build_helpers/rc_generate_resource_parameters.py`).

---

## RC Overview

### Conceptual Model

1. Every account has an **RC mana bar** (`account_object.rc_manabar`) tracking current RC and last update time.
2. Maximum RC is derived from effective VESTS (plus `rc_adjustment` and `received_rc`, minus `delegated_rc`).
3. When a transaction enters the system, the core flow in `resource_credits::finalize_transaction` (`rc_utility.cpp:799-831`) is:
   a. **Identify the payer** — first operation's required authority (`resource_user.cpp:49-65`)
   b. **Count resources** consumed by each of 5 resource types (`resource_count.cpp:582-631`)
   c. **Compute RC cost** using per-resource price curves and current pool levels (`rc_utility.cpp:286-316`)
   d. **Deduct RC** from the payer's mana bar; reject transaction if insufficient and in enforcement context (`rc_utility.cpp:478-590`)
4. RC regenerates linearly from current level toward max over 5 days, via a shared `manabar` implementation with voting mana.

### Non-Consensus Status — Three Enforcement Paths

RC is explicitly non-consensus. Enforcement differs by context, per `rc_utility.cpp:541-583`:

| Context | `db.is_in_control()` or `db.is_reapplying_one_tx()` | `db.is_processing_block()` |
|---------|-----------------------------------------------------|------------------------------|
| Meaning | New tx being accepted locally (mempool / reapply after block) | Tx is inside a block currently being processed |
| Enforcement | **Strict**: `HIVE_ASSERT(has_mana, not_enough_rc_exception, ...)` throws `not_enough_rc_exception` | **Permissive**: Logs `ilog("Accepting transaction by ${account}, has ${rc_current} RC, needs ${rc_needed} RC, block ${b}, witness ${w}.")` and continues |
| When added | HF20 | HF26 (before HF26 the permissive log path didn't exist) |
| Surcharge | Computed if `blocks_in_mempool > flood_level` | Never applied (no mempool notion) |

The surcharge-aware assertion is a separate message showing both `rc` and `surcharge` so users understand why they're rejected during flood (`rc_utility.cpp:549-556`).

The code contains an explicit TODO pointing at the missing consensus migration:
```cpp
FC_TODO( "Add || db.has_hardfork( X ) to make RC part of consensus since X" );
  //we should also replace all NOTIFYALERT warnings in RC with assertions, since they can't ever happen
```
at `rc_utility.cpp:545-546`.

The `last_max_rc` account field is described in code as "for bug catching with RC code, can be removed once RC becomes part of consensus" — it detects drift between computed and stored max RC.

### Testnet-Only Strict Assertions (`USE_ALTERNATE_CHAIN_ID`)

Several invariants are asserted on testnet and only warned on mainnet:
- Drift of `max_rc` vs `last_max_rc` between RC-affecting operations (`rc_utility.cpp:331-343`)
- Missing pre-op regeneration before RC delegation change (`rc_utility.cpp:365-376`)
- Missing pre-op regeneration before vest change (`rc_utility.cpp:390-400`)
- Missing payer on a transaction (`rc_utility.cpp:483-484`)
- Testnet also supports `configuration_data.allow_not_enough_rc` to bypass enforcement entirely (`rc_utility.cpp:541-542`)

**Source**: `rc_utility.cpp:478-590`

---

## Resource Types

Five resource types defined in `resource_count.hpp:17-24`:

```cpp
enum rc_resource_types {
  resource_history_bytes,    // 0
  resource_new_accounts,     // 1
  resource_market_bytes,     // 2
  resource_state_bytes,      // 3
  resource_execution_time    // 4
};
```

### Raw JSON Source vs Runtime Values

The source file `libraries/jsonball/data/resource_parameters.json` contains **human-readable parameters** (budget, half-life, base/exponent for resource_unit). A build-time Python script (`rc_generate_resource_parameters.py`) transforms these into the runtime `rd_dynamics_params` that hived loads at HF20 activation (`database_hardfork.cpp:369-384`).

Source parameters (as written in the JSON):

| Resource | Budget | Budget Period | Half-Life | Unit Base | Unit Exponent | Resource Unit |
|----------|--------|---------------|-----------|-----------|---------------|---------------|
| `resource_history_bytes`  | 37,500,000,000 | 30 days    | 15 days  | 10 | 0 | **1** |
| `resource_new_accounts`   | 797            | 30,000 s   | 5 days   | 10 | 4 | **10,000** |
| `resource_market_bytes`   | 6,250,000,000  | 30 days    | 16 hours | 10 | 1 | **10** |
| `resource_state_bytes`    | 37,623,913,512,960 | 30 days | 15 days | 10 | 0 | **1** |
| `resource_execution_time` | 48,000,000,000 | 1 hour     | 1 hour   | 10 | 0 | **1** |

**Correction from prior findings**: resource_units are `[1, 10000, 10, 1, 1]`, NOT `[10, 100000, 100, 10, 10]`. Confirmed at `rc_api.cpp:269` comment ("it only works when resource units are [1,10000,10,1,1] respectively") and line 272 dividing `usage[resource_new_accounts]/10000` to produce a human-readable claim count. The raw base-10 exponents in the JSON give 10^0/10^4/10^1/10^0/10^0.

### Derived Runtime Values

The Python transform computes (all per block, since `time_unit = "blocks"` and `block_interval = 3`):
- `budget_per_time_unit = (budget / budget_time_sec) * resource_unit * 3`
- `pool_eq = ceil((budget << 36) / decay_per_time_unit)` (`rd.cpp:94-99`; equilibrium where decay equals budget)
- `max_pool_size = pool_eq` (at HF20 the code overrides the JSON-derived `max_pool_size = 2*pool_eq` with `pool_eq`; `rd.cpp:99`)
- `decay_per_time_unit = decay_per_sec * 2^36`, where `decay_per_sec = -expm1(-ln(2)/tau)` and `tau = half_life_sec / ln(2)`
- Curve parameters (`coeff_a`, `coeff_b`, `shift`) computed via `generate_rc_curve_params` (`rc_curve.cpp:32-98`)

### Resource Measurement Details

All counting is done by `count_operation_visitor` (`resource_count.cpp:170-570`), which dispatches on each operation type.

#### history_bytes
Set to `tx_size` (serialized transaction size) for every transaction (`resource_count.cpp:614`). Applies to all operations uniformly.

#### new_accounts
Incremented by 1 only when `claim_account_operation` has `fee.amount == 0` (i.e. subsidized claim); paid claims cost no `new_accounts` (`resource_count.cpp:425-430`, `resource_count.cpp:616`). The `resource_new_accounts` pool is the only resource whose pool dynamics are **witness-controlled** (via `account_subsidy_rd` in the witness schedule, pushed into the RC params each witness rotation by `resource_credits::set_pool_params`, `rc_utility.cpp:833-851`).

#### market_bytes
If `market_op_count > 0` in a transaction, the full `tx_size` is charged as `market_bytes` (`resource_count.cpp:618-619`). Market operations are:
- `transfer_operation`
- `transfer_to_vesting_operation`
- `limit_order_create_operation` / `limit_order_create2_operation`
- `recurrent_transfer_operation`

Because the size is counted **once per transaction** regardless of how many market ops it contains, multiple market ops in one tx is cheaper than one per tx. A `// TODO:` comment at `resource_count.cpp:564-569` lists operations (withdraw_vesting, convert, escrow_*, savings_*, etc.) that "should [they] be market ops?" — currently they are not.

#### state_bytes
Measured in **hour-bytes**: `object_size × expected_lifetime_in_hours`. From `resource_sizes.cpp:45-165`, three durability tiers:
- `TEMPORARY_STATE_BYTE = 1` — lifetime is known and explicit (e.g. cashout window, delegation return period)
- `LASTING_STATE_BYTE = 5 × 365 × 12 = 21,900` — assumes 2.5-year average
- `PERSISTENT_STATE_BYTE = 5 × 365 × 24 = 43,800` — assumes 5-year lifetime. Rationale (comment at `resource_sizes.cpp:52-53`): "cost of persistent objects is calculated with assumption that average node doubles its memory every 5 years."

Representative costs (after applying tiers, from `resource_sizes.cpp`):
| Operation | State Bytes Formula |
|-----------|---------------------|
| `account_create` | `(616+144) × PERSISTENT + 312 × PERSISTENT` ≈ 47M per account |
| `comment` (base) | `96 × PERSISTENT + 192 × TEMPORARY × 168` (7-day cashout) |
| `vote` | `144 × TEMPORARY × 168` (7-day cashout) |
| `witness_vote` | `136 × TEMPORARY × 365 × 24` (1-year expiration) |
| `create_proposal` | `(336 + char × chars) × TEMPORARY × lifetime_hours` (variable) |
| `recurrent_transfer` | `(200 + memo) × TEMPORARY × recurrence × executions` |

The transaction itself is charged `transaction_base_size × expiration_hours` (128 × 1 × ceil(expiration_sec/3600)) (`resource_count.cpp:621-623`, `resource_sizes.cpp:121-122`).

**Metadata exclusion** (`resource_count.cpp:200-205`, `:270-275`, `:403-405`): `json_metadata` and `posting_json_metadata` are explicitly NOT charged for state bytes. Reason (from code comments): metadata storage depends on whether the optional `metadata` plugin is enabled, so charging for it would cause RC cost divergence across nodes. "API nodes should use it... which means it is not possible to handle it with differential usage counter, which finally leads to massive overcharge." This is a deliberate loophole: users can stuff unlimited json_metadata without paying state bytes for it.

#### execution_time
Pre-measured benchmark times (in nanoseconds) hardcoded in `resource_sizes.cpp:167-242`, composed as:
```
validate_time + exec_time + pre_rc_time + post_rc_time [+ automatic_processing_time]
```

Plus per-transaction overhead (`resource_count.cpp:627-628`):
- `transaction_time = 2821 + 386 + 3415 = 6622 ns` (dupe check + tapos + post-rc per-tx overhead)
- `verify_authority_time = 94165 ns` — multiplied by `tx.signatures.size()`

Representative times (from `resource_sizes.cpp:181-241`):
| Operation | Components (ns) | Total (ns) |
|-----------|-----------------|------------|
| `vote` | 479 + 17568 + 187 + 78 | 18,312 |
| `transfer` | 638 + 5023 + 204 + 134 | 5,999 |
| `comment` | 2419 + 20408 + 221 + 166 + 42964 (cashout) | 66,178 |
| `account_create` | 498 + 31575 + 236 + 6401 | 38,710 |
| `custom_json` | 859 + 162 + 321 + 167 | 1,509 |
| `custom_binary` | 0 + 0 + 0 + 0 + 100000 (artificial) | 100,000 |
| `delegate_rc` | 75000 (over custom_json) | +75,000 |
| `withdraw_vesting` | 376 + 6524 + 2068 + 567 + 16307 × HIVE_VESTING_WITHDRAW_INTERVALS | variable |
| `recurrent_transfer` | 914 + 12426 + 330 + 238 + 14347 × executions | variable |

Source of these numbers: a specific benchmark run documented at `https://gitlab.syncad.com/hive/hive/-/issues/205` (`resource_sizes.cpp:168`). The times use "clean run" values, not plugin-run values, because plugin runs have broken measurements for ops that produce vops. **There is no automated re-measurement cadence** — the values are baked in at build time via `#define USE_FIXED_SIZE` (`resource_sizes.cpp:26`).

The toggle mechanism for validating size constants (`resource_sizes.cpp:28-43`) shows a `SIZE(type, fixed_value)` macro that, when `USE_FIXED_SIZE` is undefined, uses a `validate_size` template to `static_assert` that `sizeof(type) == fixed_value` — i.e. dynamic-check that runtime object sizes match hardcoded values. In production builds this is disabled; it's only enabled during hardfork preparation "when we plan to update state RC costs for new hardfork after some significant changes in chain objects" (`resource_sizes.cpp:22-26`). Otherwise RC costs would change nondeterministically between compiler/platform combinations, breaking determinism.

---

## RC Cost Calculation

### Step-by-Step Formula

For a transaction, the RC cost is computed as follows (`rc_utility.cpp:286-316`, `:243-284`):

#### Step 1: Count Resources Per Type

The `count_operation_visitor` dispatches over all operations in the transaction, accumulating:
- `state_bytes_count`, `execution_time_count`, `market_op_count`, `new_account_op_count`
- Also sets `subsidized_op` / `subsidized_signatures` for `recover_account_operation`

Result folded into the 5-element `usage` array (`resource_count.cpp:582-631`):
```
usage[history_bytes] = tx_serialized_size
usage[new_accounts]  = count of subsidized claim_account_operations
usage[market_bytes]  = tx_size if any market op, else 0
usage[state_bytes]   = sum(object_size × lifetime_hours) + tx_base_size × expiration_hours
usage[execution_time]= sum(op_times) + transaction_time + verify_authority_time × num_signatures
```

After counting, `prevent_negative(result)` clamps any resource that went negative (due to differential discount) to 0 (`resource_count.cpp:599-603`, `:630`). Negative usage for one resource cannot subsidize positive usage for another; they are clamped independently.

**Subsidized transactions short-circuit all counting**: If the visitor flagged `subsidized_op` AND there is exactly one operation AND signature count ≤ `subsidized_signatures`, the function returns before charging anything (`resource_count.cpp:606-612`). Currently only `recover_account_operation` with a single owner-authority entry (key or account) and ≤ 2 signatures qualifies.

#### Step 2: Apply Differential Discount (Pre-Op)

Certain operations that modify rather than create state get a discount for the already-present state. Called **before** each operation applies, via `resource_credits::handle_operation_discount` (`resource_count.cpp:134-168`), which uses `count_differential_operation_visitor` (`resource_count.cpp:17-132`).

Operations with differential discount:
| Operation | Discount applied to |
|-----------|---------------------|
| `witness_update_operation` | Existing witness's `witness_update_base_size + url × char_size` |
| `account_update_operation` | Existing authority sizes for each authority being modified |
| `account_update2_operation` | Same as account_update |
| `recover_account_operation` | Existing owner authority size |
| `delegate_rc_operation` (non-zero) | Existing delegation base size per delegatee who already has a delegation |

The discount is stored as **negative initial usage** in `tx_info.usage[resource_state_bytes]`. When the post-op count runs, the positive new size partially cancels the discount. Key properties:
- Differential usage is **per-transaction** (not per-block) and reset in pre-apply transaction
- Discount must run in pre-apply-operation (not pre-apply-transaction) because some transactions create accounts then update them in the same tx — the differential visitor needs the to-be-updated state to exist
- A negative result from one op can "subsidize" a positive result from another op in the same tx (e.g. account_update reducing state below 0 makes a same-tx vesting delegation free)
- `json_metadata` is excluded from differential usage for the same reason it's excluded from counting — plugin-dependent
- `delegate_rc_operation` with `max_rc == 0` skips differential (the removal itself doesn't use new state)

#### Step 3: Apply Resource Units

Each raw usage is multiplied by the resource's `resource_unit` (`rc_utility.cpp:305`):
```cpp
usage_info->usage[i] *= int64_t( params.resource_dynamics_params.resource_unit );
```

This converts raw counts (bytes, hour-bytes, nanoseconds, account claims) into internal "resource units" that the price curve operates on. Units: `[1, 10000, 10, 1, 1]`.

#### Step 4: Compute Global RC Regeneration Rate

```cpp
int64_t total_vests = dgpo.get_total_vesting_shares().amount.value;
int64_t rc_regen = total_vests / (HIVE_RC_REGEN_TIME / HIVE_BLOCK_INTERVAL);
// = total_vests / (432000 / 3)
// = total_vests / 144000  (RC regenerated per block globally)
```

This is the total RC the network gains each block (`rc_utility.cpp:293`). It equals `total_vesting_shares / 144000` because in 5 days (144,000 blocks) every VEST-equivalent regenerates exactly once.

**Edge case**: If `rc_regen == 0` (only possible pre-genesis or in degenerate testnet), the entire transaction is free (`rc_utility.cpp:298`). Checked via `FC_ASSERT(rc_regen > 0)` in the per-resource `compute_cost` (`rc_utility.cpp:257`).

#### Step 5: Per-Resource Regen Share

```cpp
int64_t pool_regen_share = (rc_regen * pool_obj.get_weight(i)) / pool_obj.get_weight_divisor();
```
(`rc_utility.cpp:306`)

The weight divisor is `sum_of_resource_weights`. Weights are recalculated each block (see "Resource Weights" below).

#### Step 6: Price Curve

The per-resource RC cost is computed via `resource_credits::compute_cost(curve_params, current_pool, resource_count, rc_regen)` (`rc_utility.cpp:243-284`):

```cpp
uint128_t num = uint128_t(rc_regen) * curve_params.coeff_a;
num >>= curve_params.shift;   // shift first to avoid overflow
num += 1;                      // err on rounding AGAINST user
num *= uint64_t(resource_count);

uint128_t denom = uint128_t(curve_params.coeff_b);
denom += (current_pool > 0) ? uint64_t(current_pool) : 0;  // negative pool treated as 0

return uint128_to_uint64(num / denom) + 1;  // minimum cost of 1
```

Where:
- `coeff_a ≈ tau / k`, where tau is characteristic time (inversely related to half-life) and `k = u / (a × (1-u))`. For default parameters (a=37/1000 for new_accounts, 150/10000 for others; u=1/2): `k = 0.5 / (0.037 × 0.5) = 27.03` for new_accounts, `k = 0.5 / (0.015 × 0.5) = 66.67` for others.
- `coeff_b = inelasticity_threshold × pool_eq = pool_eq / 128` (`rc_curve.cpp:94-97`)
- `shift` is set so that `coeff_a / 2^shift` gives the proper A value while keeping it 64-bit

**Economic interpretation**:
- When `current_pool >> coeff_b`, price is low: `cost ≈ (rc_regen × coeff_a × count) / (2^shift × current_pool)`
- When `current_pool → 0`, price approaches maximum: `cost → (rc_regen × coeff_a × count) / (coeff_b × 2^shift)`
- When `current_pool < 0` (already in deficit), the code clamps `coeff_b + current_pool` to `coeff_b`, so the price saturates at p_max (no further increase)
- The `+1` at the end ensures `cost ≥ 1` — no resource is ever truly free

**Numerical robustness**: `compute_cost` uses `uint128_t` throughout. The comment at `:267-269` notes "rc_regen * coeff_a is already risking overflowing 128 bits, so shift it immediately before multiplying by resource_count."

**Negative usage handled**: `if (resource_count < 0) return -compute_cost(...,-resource_count,...)`. Cost is symmetric under sign flip (`rc_utility.cpp:259-263`).

#### Step 7: Sum All Resource Costs and Apply Flood Surcharge

```cpp
total_cost = sum(cost[i] for i in resources)
```

Then in `use_account_rcs` (`rc_utility.cpp:505-537`), a **flood surcharge** may be added:

```cpp
blocks_in_mempool = db._pending_tx_size / dgpo.maximum_block_size;
if (blocks_in_mempool > flood_level) {
  if (!is_privileged) {
    surcharge = (blocks_in_mempool - flood_level) × flood_surcharge × rc / HIVE_100_PERCENT;
  }
}
acc.rc_manabar.use_mana(rc + surcharge);
```

Where:
- `flood_level` defaults to 20 (20 blocks of pending tx = ~60 seconds of backlog)
- `flood_surcharge` defaults to `HIVE_100_PERCENT = 10000` (one blocks-over-threshold multiplies cost by 100%)
- Surcharge is ONLY applied when `is_validating_one_tx() || is_reapplying_one_tx()` — never during block processing
- **Privileged operations bypass surcharge**: `feed_publish_operation`, `witness_update_operation`, `witness_set_properties_operation` are privileged IF the payer is in the `witness_object::elected` schedule (top-21). These are essential for chain operation during congestion.
- Surcharge config is controlled via `resource_credits::set_flood_limiters()` — configurable per-node (not consensus) via command-line flags

The assertion `FC_ASSERT(sc <= max - rc)` prevents surcharge overflow (`rc_utility.cpp:534`). If a transaction has `rc` RC cost and enough mana for `rc` but not `rc + surcharge`, a specific message explains the flood situation (`rc_utility.cpp:549-556`).

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
  uint32_t   regen_time  = 0;
};
```

Shared by RC, voting mana, and downvote mana (`manabar.hpp`).

### Regeneration Formula

```cpp
template<bool skip_cap_regen = false>
void regenerate_mana(const manabar_params& params, uint32_t now) {
  FC_ASSERT(now >= last_update_time);
  uint32_t dt = now - last_update_time;

  // Early-out: if already at or above max, snap down to max and return
  if (current_mana >= params.max_mana) {
    current_mana = params.max_mana;
    last_update_time = now;
    return;
  }
  if (dt == 0) return;

  if (!skip_cap_regen)
    dt = min(dt, params.regen_time);

  uint128_t max_mana_dt = max_mana × dt;
  uint64_t u_regen = max_mana_dt / regen_time;
  int64_t new_current_mana = signed_sat_add(current_mana, u_regen);
  current_mana = min(new_current_mana, max_mana);
  last_update_time = now;
}
```

**Source**: `manabar.hpp:41-68`

### Key Properties

- **Regeneration is linear**, proportional to max. Full regen (0 → max) takes exactly 5 days for RC (432,000 seconds).
- **Lazy evaluation**: regeneration runs on-demand via `regenerate_rc_mana()` before any operation that reads or modifies mana (`rc_utility.cpp:318-350`).
- **Early-out clamp has a side-effect**: If `current_mana > max_mana` (e.g. because `max_mana` just dropped due to delegation change), the early-out **reduces** `current_mana` to `max_mana`. This is the "apparent mana loss" after a max reduction that's not a true regeneration.
- **`skip_cap_regen = true` for RC** (`rc_utility.cpp:347`, `:361`, `:503`): skips `dt = min(dt, regen_time)`. In practice, post-cap the result is identical — `signed_sat_add` saturates at int64_max and then the final `min(new, max_mana)` clamps it. The skip is essentially a micro-optimization avoiding a comparison + branch.
- **Voting mana uses `skip_cap_regen = false`** — the default. See `manabar.hpp:109-138`.
- **Mana can go negative via `use_mana`**: `use_mana` uses `signed_sat_sub`. Optional `min_mana` floor (default `uint64_t::min()` = 0 treated as signed) can clamp to any value. RC normally calls with no floor, allowing negative mana after over-consumption. `has_mana(needed)` returns true iff `mana_needed ≤ 0 || current_mana ≥ mana_needed`.

### Maximum RC Calculation

```cpp
share_type get_maximum_rc(bool only_delegable = false) const {
  share_type total = get_effective_vesting_shares().amount - delegated_rc;
  if (only_delegable == false)
    total += rc_adjustment + received_rc;
  return total;
}
```
(`account_object.hpp:115-121`)

Where:
- `get_effective_vesting_shares()` = own VESTS + received VEST delegations - delegated VESTS
- `delegated_rc` = total RC currently delegated out to others (in VESTS-equivalent units)
- `rc_adjustment` = permanent bonus awarded at account creation (fee converted to VESTS, or historical flat adjustment for pre-HF20 accounts)
- `received_rc` = total RC currently delegated in from others
- `only_delegable=true` variant excludes `rc_adjustment` and `received_rc` — only own stake can be delegated onward, preventing re-delegation of received RC

### Relation to Voting Mana

Both use the same `manabar` struct and `HIVE_VOTING_MANA_REGENERATION_SECONDS = 5 days`. Key differences:

| Property | RC mana | Voting mana | Downvote mana |
|----------|---------|-------------|---------------|
| `max_mana` | `get_maximum_rc()` | `get_effective_vesting_shares()` | `effective_vests × downvote_pool_percent / 100%` |
| Regen cap | skip_cap_regen=true | skip_cap_regen=false | skip_cap_regen=false |
| Consensus? | Non-consensus | **Consensus** | **Consensus** |
| Reduced on vote delegation change | Receiver's mana "immediately adjusted" per `update_account_after_rc_delegation` | Uses different accounting (`update_manabar`) | |

The code comment at `rc_utility.cpp:320-323` explicitly notes the consensus dependency:
```cpp
// Since RC tracking is non-consensus, we must rely on consensus to forbid
// transferring / delegating VESTS that haven't regenerated voting power.
static_assert( HIVE_RC_REGEN_TIME <= HIVE_VOTING_MANA_REGENERATION_SECONDS,
  "RC regen time must be smaller than vote regen time" );
```
Because voting mana is consensus and has the same or longer regen time than RC, any voting-mana-based consensus rule effectively polices VEST mobility with at least the granularity RC needs.

---

## RC Delegation

### Operation

Broadcast as `custom_json_operation` with id `"rc"` (`hive_custom_operations.hpp:23`):

```cpp
struct delegate_rc_operation : public base_operation {
  account_name_type             from;
  flat_set<account_name_type>   delegatees;  // up to 100 per op
  int64_t                       max_rc = 0;  // 0 = remove delegation
  extensions_type               extensions;
  void get_required_posting_authorities(...) { a.insert(from); }
};
```

Dispatched through the `generic_custom_operation_interpreter<rc_custom_operation>` registered by `resource_credits::initialize_evaluators` (`rc_utility.cpp:717-732`).

### Semantics (HF26+)

Implemented in `delegate_rc_evaluator::do_apply` (`rc_utility.cpp:27-111`):

1. **Hardfork gate**: Pre-HF26, the operation is accepted but ineffective — a `dlog` records "Ineffective RC delegation" and the function returns (`rc_utility.cpp:29-33`)
2. **Requires posting authority** of `from`
3. **Minimum delegation** (only enforced for new tx, not in blocks): `(account_creation_fee / 3) × vesting_share_price` → converts account_creation_fee/3 HIVE into VESTS-equivalent. Applied per individual delegation, not per op (`rc_utility.cpp:40-44`)
4. **`max_rc = 0` removes the delegation** (only valid if delegation already exists; new-creation with 0 throws)
5. **Already-same-value is rejected**: `FC_ASSERT(delegation->delegated_rc != uint64_t(op.max_rc), ...)` prevents no-op tx from consuming RC
6. **Expired-delegation block**: Cannot create new RC delegations while the delegator has a `rc_expired_delegation_object` (`rc_utility.cpp:49-52`). The comment explains: "we want to discourage users from using the scheme to temporarily 'pump' amount of RC, also if it is not intentional they might be confused about fresh delegations disappearing right after being formed (which might happen if we allow fresh delegations while previous were not yet cleared)."
7. **Delta can be negative** (reducing delegation): in a single operation with multiple delegatees, reductions can appear before the final check; the final assertion happens once at the end (`rc_utility.cpp:93-96`).
8. **Delegator's current_mana is deducted IMMEDIATELY for increases**, unchanged for decreases (`rc_utility.cpp:98-108`):
   ```cpp
   if (delta_total > 0)
     acc.rc_manabar.current_mana -= delta_total;
   acc.delegated_rc += delta_total;
   acc.last_max_rc = acc.get_maximum_rc();
   ```
   The mana reduction on increase is capped by `from_delegable_rc = min(get_maximum_rc(only_delegable=true), current_mana)`, so it can't drive current_mana negative.
9. **Receiver's mana is adjusted by the full delta** (both increase and decrease): `update_account_after_rc_delegation(to_account, now, delta, regenerate=true)` (`rc_utility.cpp:352-385`):
   ```cpp
   acc.rc_manabar.current_mana = max(acc.rc_manabar.current_mana + delta, 0);
   acc.last_max_rc = max_rc + delta;
   acc.received_rc += delta;
   ```
   Receiver's current_mana clamps to 0 (cannot go negative from decrease).
10. **Pump-prevention asymmetry explained**: increases deduct from delegator, but decreases do NOT restore mana to delegator. If they did, delegator could give, receiver spends, delegator takes back → both have spent same pool once. Comment at `rc_utility.cpp:100-101`: "Do not give mana back when deleting/reducing rc delegation (note that regular delegations behave differently)." The asymmetry is load-bearing.

### Delegation Overflow

When a VESTS change makes `delegated_rc > effective_vesting_shares`, the system handles overflow in `update_account_after_vest_change` (`rc_utility.cpp:387-467`):

1. Compute `delegation_overflow = -get_maximum_rc(only_delegable=true).value` (negative of delegable RC)
2. If overflow > 0, iterate direct delegations (by ID, smallest-first) and reduce/remove them until overflow is cleared
3. Limited by `db.get_remove_threshold()` per block (prevents one account's VEST change from spawning an unbounded work blob)
4. If overflow remains after the limit, create or augment a `rc_expired_delegation_object` holding the leftover amount
5. In subsequent blocks, `handle_expired_delegations()` (`rc_utility.cpp:598-637`) continues removing delegations until the expired object is exhausted, then deletes it
6. While expired object exists, **the delegator cannot create new RC delegations** — enforced at evaluator level (`rc_utility.cpp:49`)

The reduction per delegation uses `update_account_after_rc_delegation(to, now, -delta_rc, regenerate=true)` which does regenerate the receiver's mana first (pre-delta), then applies the delta (`rc_utility.cpp:673`).

**Current iteration order is FIFO by delegation ID, not by size** — comment at `rc_utility.cpp:643-644`: "Maybe add a new index to sort by from / amount delegated so it's always the bigger delegations that is modified first instead of the id order?" This is a noted TODO: iteration order may cause many small delegations to be reduced before one large one.

### State Objects

```cpp
class rc_direct_delegation_object {
  account_id_type from;
  account_id_type to;
  uint64_t        delegated_rc = 0;
};

class rc_expired_delegation_object {
  account_id_type from;
  uint64_t        expired_delegation = 0;
};
```

Indices: `by_from_to` composite on `rc_direct_delegation_object`; `by_account` on `rc_expired_delegation_object` (by_from). (`rc_objects.hpp:179-213`, `:287-311`)

---

## Resource Dynamics

### Pool System

Each resource has an independent pool (`rc_pool_object.pool_array[5]`). Pool is mutated once per block in `resource_credits::finalize_block` (`rc_utility.cpp:734-797`):

```
new_pool = pool - decay + budget - usage
```

Per-block components (exact order in code, `rc_utility.cpp:758-783`):
1. `int64_t pool = pool_obj.get_pool(i);`
2. `pool_obj.set_budget(i, params.budget_per_time_unit);` — records the budget for stats
3. `int64_t decay = rd_compute_pool_decay(params.decay_params, pool - block_info.usage[i], 1);` — decay is computed on **pool minus usage** (usage is virtually deducted before decay is computed)
4. Update 24h window: if bucket rotating, subtract oldest bucket's usage from `usage_in_window`; add current-block usage
5. `int64_t new_pool = pool - decay + params.budget_per_time_unit - block_info.usage[i];`
6. For `resource_new_accounts`: force-sync to `dgpo.available_account_subsidies` (see above)
7. Clamp: `if (new_pool < 0) new_pool = 0;`

Key decay math:
- **Decay formula** (`rd.cpp:23-41`): `decay = (decay_per_time_unit × pool × dt) >> decay_per_time_unit_denom_shift`
- `decay_per_time_unit_denom_shift` is always `HIVE_RD_DECAY_DENOM_SHIFT = 36` (hard-asserted at setup; `rd.cpp:78`)
- The Python build-time transform computes `decay_per_time_unit = 2^36 × (-expm1(-block_interval × ln(2) / half_life_sec))` — this gives exactly the fractional per-block decay rate for the specified half-life
- If result > current_pool, decay is clamped to current_pool (cannot decay more than is there)
- **No upper clamp on pool growth**: unlike `rd_apply` (`rd.cpp:43-54`), `finalize_block` doesn't apply `max_pool_size`. The pool's upper bound is implicit — at equilibrium decay equals budget, so pool naturally settles around `pool_eq`.

### Pool Equilibrium

At equilibrium, decay equals budget:
```
pool_eq = ceil((budget << 36) / decay_per_time_unit)
```
(`rd.cpp:94-98`)

Production parameters:
- `resource_new_accounts` at witness-default: budget=797/block, decay=347321, shift=36 → `pool_eq = 797 × 2^36 / 347321 ≈ 157.8M units` (~15,782 accounts at 10000 units each)
- Other resources: budget & decay come from the JSON-derived runtime values

The `rd_setup_dynamics_params` function asserts its own correctness (`rd.cpp:109-118`): `check_pool_eq(pool_eq) = true && check_pool_eq(pool_eq-1) = false`, verifying `pool_eq` is minimal.

### `resource_new_accounts` Special Handling

The only resource whose dynamics are NOT from the JSON file at runtime. Two special paths:

1. **Witness override** at hardfork or on witness schedule change: `resource_credits::set_pool_params(wso)` (`rc_utility.cpp:833-851`). If `wso.account_subsidy_rd` differs from the current params, it overwrites `resource_param_array[resource_new_accounts].resource_dynamics_params` and regenerates the curve params.

2. **Consensus-value sync each block**: In `finalize_block` (`rc_utility.cpp:770-779`):
   ```cpp
   if (i == resource_new_accounts) {
     int64_t new_consensus_pool = dgpo.available_account_subsidies;
     if (new_consensus_pool != new_pool) {
       ilog("resource_new_accounts adjustment on block ${b}: ${a}", ...);
       new_pool = new_consensus_pool;
     }
   }
   ```
   The pool value is forced to match the consensus-tracked `available_account_subsidies`. Because account creation is consensus (you can't include a subsidized claim in a block if subsidies aren't available), the RC pool follows along passively rather than being computed independently. Any non-zero delta is logged as an `ilog` for operator visibility.

This is the bridge between the non-consensus RC pool (which could diverge between nodes) and the consensus subsidy pool (which cannot).

### Resource Weights (Popularity-Based Regen Share)

Each block, `rc_pool_object::recalculate_resource_weights(params)` (`rc_objects.hpp:80-95`):

```cpp
sum_of_resource_weights = 0;
for (int i = 0; i < HIVE_RC_NUM_RESOURCE_TYPES; ++i) {
  if (i == resource_new_accounts) continue;
  resource_weights[i] = usage_in_window[i] * HIVE_100_PERCENT / params.budget_per_time_unit;
  if (resource_weights[i] == 0) resource_weights[i] = 1;  // minimum weight
  sum_of_resource_weights += resource_weights[i];
}
resource_weights[resource_new_accounts] = sum_of_resource_weights;  // always 100%
```

Then the regen share of each resource is `weight[i] / sum_of_weights`. Because `weight[new_accounts] = sum_of_others`, the effective division is:
- new_accounts: `sum / (2 × sum) = 50%`
- Everything else: `own_weight / (2 × sum) = usage_share / 2`

So **50% of global RC regen is always allocated to new_accounts, the other 50% is split among other resources proportional to their popularity in the last 24h.**

This is intentional design per comment at `rc_objects.hpp:40-42`: "resource_new_accounts is treated as luxury item — its share is always 100% and it is excluded from share calculation of other resources." The symmetry `weight_ka = sum_others` (not `weight_ka = sum_others × k`) creates exactly the 50/50 split.

**Consequence**: Subsidized account creation is persistently expensive — the effective per-resource price scales inversely with the share. With 50% of regen going to new_accounts, if only a few accounts are being created (low usage_in_window), the pool stays near equilibrium, but the **pool_regen_share** is still half of the global regen. This keeps pressure on subsidized creation even when paid creation is cheap.

### Usage Buckets (24h Sliding Window)

Usage is tracked in 24 hourly buckets (`HIVE_RC_BUCKET_TIME_LENGTH = 3600`, `HIVE_RC_WINDOW_BUCKET_COUNT = 24`) (`rc_objects.hpp:216-256`).

In `finalize_block` (`rc_utility.cpp:746-796`):
1. `active_bucket` = last (newest) bucket in `by_timestamp` index
2. If `active_bucket.timestamp + 3600 <= now`, the oldest bucket is selected for reset (`reset_bucket = true`)
3. Before adding current-block usage, subtract the to-be-reset bucket's usage from `rc_pool_object.usage_in_window` (a running sum)
4. Add current-block usage to `usage_in_window`
5. Add to the bucket (either the active bucket or the now-reset bucket)
6. Reset the expired bucket's timestamp to `now`

So `rc_pool_object.usage_in_window` is a rolling 24-hour total. This is what the weight calculation uses.

**Smallest-id discovery**: The index `by_timestamp` — bucket with smallest timestamp is the oldest. The code uses `bucket_idx.begin()` for oldest and `bucket_idx.rbegin()` for newest.

### Relationship to Voting Mana

The `static_assert` noted earlier says `HIVE_RC_REGEN_TIME <= HIVE_VOTING_MANA_REGENERATION_SECONDS`. Currently they're equal. If voting mana regen were faster than RC regen, attackers could power down → vote-with-newly-arrived-voting-mana → but RC hasn't caught up so the operation would be free. Because RC is non-consensus, preventing this kind of drift requires the voting mana regen to be the slower bound.

---

## Account Creation RC

### Two Paths

1. **Paid creation** (`claim_account` with `fee.amount > 0`, `hive_evaluator_account.cpp:402-462`):
   - Fee = `wso.median_props.account_creation_fee` (witness-set, 3 HIVE default)
   - Increments `pending_claimed_accounts` on creator (consumed later by `create_claimed_account_operation`)
   - Fee goes to null account (burned)
   - Fee is converted to VESTS equivalent and stored as `rc_adjustment` on the new account
   - No RC cost on the `resource_new_accounts` resource

2. **Subsidized creation** (`claim_account` with `fee.amount == 0`):
   - Consumes from `resource_new_accounts` pool (via RC cost) AND from `dgpo.available_account_subsidies` (consensus)
   - Witness-subsidy tracking: requires subsidy available globally (consensus) and on the block-producing witness (consensus)
   - Elected witnesses can include subsidized claims in blocks; backup witnesses can too when their own per-witness pool has sufficient subsidy
   - The RC pool and the consensus pool are synced by the forced-assignment at `rc_utility.cpp:770-779`

### `rc_adjustment`

When a new account is created post-HF20 via paid or create_claimed path, the creation fee is converted to VESTS equivalent and stored permanently as `rc_adjustment` on the new account (`hive_evaluator_account.cpp:130-153`). This gives new accounts RC capacity equivalent to having that VESTS stake — but only for RC purposes; it doesn't contribute to governance weight, voting power, or HIVE conversion.

For accounts existing before HF20:
```cpp
account.rc_adjustment = HIVE_RC_HISTORICAL_ACCOUNT_CREATION_ADJUSTMENT;  // 2020748973
// = 2020.748973 VESTS ≈ 1.000 HIVE at HF20 activation
```
(`database_hardfork.cpp:406-414`, `config.hpp:492`)

The historical value was chosen so every pre-HF20 account received roughly 1 HIVE worth of RC adjustment at HF20. Their full `current_mana` was set to `get_maximum_rc().value` at HF20 (`database_hardfork.cpp:408-413`).

### `resource_new_accounts` Pool Integration

Budget and decay for `resource_new_accounts` come from `wso.account_subsidy_rd`, which witnesses vote on (via `witness_set_properties_operation` or legacy chain props). Defaults (`config.hpp:417-419`):
- `HIVE_DEFAULT_ACCOUNT_SUBSIDY_DECAY = 347321` (5-day half-life)
- `HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET = 797` (intended "0.5 accounts per block" at equilibrium, per code comment)

Precision: `HIVE_ACCOUNT_SUBSIDY_PRECISION = HIVE_100_PERCENT = 10000` — the account_subsidy params are in basis points. With the Python transform producing `resource_unit = 10^4 = 10000`, one claim = 10000 resource units.

---

## RC State Objects

### Per-Account (in `account_object`)

| Field | Type | Description |
|-------|------|-------------|
| `rc_manabar` | `manabar` | Current RC mana and last update timestamp (lazy) |
| `rc_adjustment` | `share_type` | Permanent VESTS-equivalent bonus from account creation |
| `delegated_rc` | `share_type` | Total RC delegated out to others |
| `received_rc` | `share_type` | Total RC delegated in from others |
| `last_max_rc` | `share_type` | Last computed max RC; used for bug-catching drift detection |

**Source**: `account_object.hpp:192, 215-218`. Accessors `get_maximum_rc()`, `get_delegated_rc()`, `get_received_rc()` at `account_object.hpp:115-124`.

### Global Singletons

| Object | Count | Description |
|--------|-------|-------------|
| `rc_resource_param_object` | 1 | Per-resource dynamics params and price curve params |
| `rc_pool_object` | 1 | Current pool levels, 24h usage window, weights, last budgets |
| `rc_stats_object` | 2 | Pending (`RC_PENDING_STATS_ID = 0`) and archive (`RC_ARCHIVE_STATS_ID = 1`) daily statistics |
| `rc_usage_bucket_object` | 24 | Hourly sliding-window usage buckets |

### Per-Delegation

| Object | Fields |
|--------|--------|
| `rc_direct_delegation_object` | `from`, `to`, `delegated_rc` |
| `rc_expired_delegation_object` | `from`, `expired_delegation` (overflow amount) |

**Source**: `rc_objects.hpp`

---

## RC API Endpoints

The `rc_api` plugin (`libraries/plugins/apis/rc_api/`) exposes read-only queries:

| Endpoint | Returns |
|----------|---------|
| `rc_api.get_resource_params` | Per-resource `rd_dynamics_params` + curve params, plus the `state_object_size_info` and `operation_exec_info` constants from `resource_sizes.cpp` |
| `rc_api.get_resource_pool` | Per-resource `{pool: int64, fill_level: uint16_bp}` where `fill_level = pool * 10000 / pool_eq` |
| `rc_api.find_rc_accounts` | For each requested account: `{account, rc_manabar, max_rc_creation_adjustment (asset VESTS), max_rc, delegated_rc, received_delegated_rc}` |
| `rc_api.list_rc_accounts` | Paginated by account name, limit 1000 |
| `rc_api.list_rc_direct_delegations` | Paginated by `(from, to)` tuple, limit 1000 |
| `rc_api.get_rc_stats` | Returns the archive (previous-day) `rc_stats_object` as variant, REGULAR detail level |
| `rc_api.get_rc_operation_stats` | Per-operation: count, avg_cost, breakdown by resource (cost, cost_share bp, usage in native unit) |

**Key detail**: `get_rc_operation_stats.resource_usage.tokens` is a STRING with 4 decimal places (`std::stringstream << std::fixed << std::setprecision(4) << double(usage[resource_new_accounts]) / 10000.0`) to force fixed precision. This is the only API field that translates from resource units back to a human-readable count. Comment at `rc_api.cpp:269`: "somehow I can't be bothered to code it in generic way; it only works when resource units are [1,10000,10,1,1] respectively" — confirming the resource unit values.

**Implementation constraint**: `find_rc_accounts` and `list_rc_accounts` only return data post-HF20 (`rc_api.cpp:115`, `:139`) — before HF20 activation they return empty results silently rather than error.

**Source**: `rc_api.hpp`, `rc_api.cpp`

---

## RC Statistics System

### Structure

Two stats objects:
- `RC_PENDING_STATS_ID = 0` — accumulates stats for current reporting window
- `RC_ARCHIVE_STATS_ID = 1` — holds previous window's finalized stats (what the API returns)

Each stats object tracks (`rc_stats.hpp`, `rc_objects.hpp:130-175`):

```cpp
struct rc_stats_object {
  uint32_t                 block_num;    // starting block of this window
  int64_t                  regen;        // global RC regen rate at starting block
  restartable_sha256       stamp;        // rolling SHA-256 hash of payer RC mana values
  resource_count_type      budget;       // budgets at starting block
  resource_count_type      pool;         // pool values at starting block
  resource_share_type      share;        // per-resource share in bp
  rc_op_stats[HIVE_RC_NUM_OPERATIONS+1]  op_stats;       // per-op cost/usage/count; last slot = multiop tx
  rc_payer_stats[8]        payer_stats;  // per-rank payer stats (see below)
  int64_t[3]               average_cost; // avg cost of vote, comment, transfer (for affordability filter)
};
```

### Per-Op Stats

```cpp
struct rc_op_stats {
  resource_count_type usage;
  resource_cost_type  cost;
  uint32_t            count;
  int64_t average_cost() const { return sum(cost) / count; }
};
```

Updated per-tx in `rc_stats_object::add_stats(tx_info)` (`rc_objects.cpp:32-78`). The multiop slot (`HIVE_RC_NUM_OPERATIONS`) captures multi-operation transactions; single-op transactions go to the operation-specific slot.

### Per-Payer-Rank Stats

8 ranks based on payer's max_rc magnitude:
```cpp
int rank = log10(tx_info.max) - 9;
if (rank < 0) rank = 0;
if (rank >= 8) rank = 7;
```
(`rc_objects.cpp:50-54`)

- Rank 0: max_rc < 10^10 (~10B; very small accounts)
- Rank 1: max_rc < 10^11
- ...
- Rank 7: max_rc >= 10^16

Per-rank stats:
- `count`, `cost`, `usage`
- `less_than_5_percent`, `less_than_10_percent`, `less_than_20_percent` — counters of how often payer was observed with those mana levels (out of `count` total observations)
- `cant_afford[3]` — counters for vote/comment/transfer affordability failures (see below)
- `was_dry()` = any `cant_afford[i] > 0`

### "Can't Afford" Affordability Flag

`add_stats` checks `tx_info.rc < average_cost[i]` for `i ∈ {0=vote, 1=comment, 2=transfer}` (`rc_objects.cpp:74-76`). The `average_cost` values are carried over from the PREVIOUS reporting window (updated in `archive_and_reset_stats`, `rc_objects.cpp:22-26`). The first window has no affordability data (all 0), so the check is always false until one full cycle has elapsed.

### Rolling Hash (Stamp)

`stamp.update(&tx_info.rc, sizeof(tx_info.rc))` after every transaction. This is a `restartable_sha256` over payer's post-tx RC mana. On archival, `stamp.finish()` returns a hex digest. Purpose: fingerprint for comparing RC state across nodes — two nodes running independent replays should produce identical stamps for each block window. **This is how non-consensus divergence can be detected out-of-band** without making RC a hard consensus rule.

### Reports

Auto-report frequency: `HIVE_RC_STATS_REPORT_FREQUENCY = HIVE_BLOCKS_PER_DAY` on mainnet (configurable per-session on testnet via `configuration_data.rc_stats_report_frequency`). Report types:

| Type | Includes |
|------|----------|
| `NONE` | (suppressed) |
| `MINIMAL` | block, stamp, regen, budget, pool, share, avg vote/comment/transfer cost |
| `REGULAR` | `MINIMAL` + per-op average cost, per-rank counters |
| `FULL` | `REGULAR` but per-op and per-rank show full cost/usage arrays instead of just averages |

Output: `DLOG`, `ILOG`, `NOTIFY` (app notification `"rc_stats"`), or `BOTH` (NOTIFY + ILOG). Configurable via `set_auto_report`.

**Source**: `rc_utility.cpp:143-230, 679-715`

---

## Key Discoveries

1. **Non-consensus with three distinct enforcement paths**: `is_in_control()` (new tx) and `is_reapplying_one_tx()` are strict; `is_processing_block()` is permissive post-HF26. Pre-HF26, the permissive path logged nothing. The `last_max_rc` field is explicitly designed to detect drift pending the consensus migration.

2. **Resource units are `[1, 10000, 10, 1, 1]`**, not `[10, 100000, 100, 10, 10]`. Only `resource_new_accounts` (10000) and `resource_market_bytes` (10) have scaling factors; the others are raw. The RC API at `rc_api.cpp:269` has a hardcoded assertion/comment documenting this exact sequence.

3. **Resource weights create a persistent 50/50 split between new_accounts and everything-else**: Because `weight[new_accounts] = sum_of_other_weights`, the global RC regen is divided 50% new_accounts / 50% rest. This makes subsidized account creation perpetually expensive regardless of demand for other resources.

4. **Differential discount is per-transaction and per-operation, not per-block**: Operations that modify existing state (authority rotation via account_update, witness URL changes, existing-delegation modifications) get a discount for the state they're overwriting. Stored as negative initial state_bytes usage; subsequent ops in the same tx can benefit. `prevent_negative` clamps each resource to ≥ 0 after summing — one resource cannot subsidize another.

5. **Metadata is deliberately unchargeable**: `json_metadata` is a consensus loophole — because `metadata` plugin is optional, charging for it would cause RC cost divergence between full nodes and API nodes. This is intentional and documented in comments at `resource_count.cpp:200-275`.

6. **Recovery ops are fully subsidized only for simple cases**: `recover_account_operation` is free only if (a) it has a single-entry new_owner_authority (one account OR one key, not multisig) AND (b) signature count ≤ 2. Multisig stolen accounts are NOT subsidized — users must still pay RC to recover them. Comment at `resource_count.cpp:538-540`: "circumventing cost of setting up new multisig is also not allowed."

7. **Delegation asymmetry is load-bearing anti-pump**: Increasing a delegation deducts current_mana from delegator immediately. Decreasing/removing does NOT restore mana. Otherwise, an attacker could delegate → receiver spends → delegator un-delegates → both have spent same pool. Receiver always gets immediate delta (both ways), because receiver hasn't had time to "pump" anything.

8. **Flood surcharge has a top-21 privileged override**: When mempool exceeds 20 blocks of backlog, tx cost is surcharged. But `feed_publish`, `witness_update`, `witness_set_properties` from top-21 `elected` witnesses bypass it. Justification: these ops are essential for chain operation (unblocking congestion, setting block sizes), so they must go through even when users are being throttled.

9. **`resource_new_accounts` pool is force-synced to consensus each block**: `dgpo.available_account_subsidies` is consensus-tracked; the RC pool passively adopts it each block via `finalize_block`. Any divergence is logged as `ilog` for operator visibility. This is the only pool where an explicit consensus-to-non-consensus bridge exists.

10. **Build-time parameter generation via Python**: The human-readable JSON at `libraries/jsonball/data/resource_parameters.json` is transformed at CMake time by `rc_generate_resource_parameters.py` into runtime-loadable JSON (with `budget_per_time_unit`, `pool_eq`, `decay_per_time_unit`, `coeff_a/b`, `shift` computed). The raw JSON values in the data file are NOT what ends up in state.

11. **Payer-rank statistics use log10(max_rc)**: 8 ranks span max_rc from <10B (rank 0) to ≥10^16 (rank 7). This groups payers by order-of-magnitude stake.

12. **Rolling SHA-256 stamp over payer mana fingerprints RC state across nodes**: Stored per reporting window. Two nodes replaying independently should produce the same stamp — a divergence indicator without requiring consensus on RC itself.

13. **Testnet-only strict assertions**: Under `USE_ALTERNATE_CHAIN_ID`, warnings about max_rc drift, missing regeneration before RC/VEST changes, and missing payer become hard asserts. Mainnet only logs. This allows thorough correctness testing without forking mainnet.

14. **`skip_cap_regen = true` is essentially cosmetic for RC**: The template flag bypasses `dt = min(dt, regen_time)`, but the final `min(new_mana, max_mana)` clamp plus `signed_sat_add` saturation produce identical results. The distinction matters only for edge cases in micro-benchmark scenarios.

15. **Early-out in `regenerate_mana` can reduce current_mana**: If `current_mana > max_mana` (e.g. after a delegation loss shrinks max), the early-out path clamps down to `max_mana`. Users observe this as "mana dropped on its own" after losing incoming delegations.

---

## Code References

| File | Purpose |
|------|---------|
| `include/hive/chain/rc/rc_objects.hpp` | All RC state objects (pool, params, stats, delegations, buckets); weight recalculation |
| `include/hive/chain/rc/rc_utility.hpp` | `resource_credits` class interface |
| `include/hive/chain/rc/resource_count.hpp` | Resource type enum, counting declarations |
| `include/hive/chain/rc/resource_sizes.hpp` | State object size and operation execution time constants |
| `include/hive/chain/rc/rc_curve.hpp` | Price curve generation params |
| `include/hive/chain/rc/rc_export_objects.hpp` | Per-tx and per-block RC info structs |
| `include/hive/chain/rc/rc_stats.hpp` | Per-operation and per-payer statistics |
| `include/hive/chain/util/manabar.hpp` | Mana bar regeneration template (shared by RC and voting) |
| `include/hive/chain/util/rd_dynamics.hpp` | Resource dynamics params and pool decay |
| `include/hive/chain/util/rd_setup.hpp` | User/system param conversion and `rd_setup_dynamics_params` |
| `rc/rc_utility.cpp` | Core implementation: cost computation, mana management, delegation, block finalization, stats |
| `rc/resource_count.cpp` | Resource counting per-operation, differential discount, subsidy handling |
| `rc/resource_sizes.cpp` | Concrete size/time values for all operations (hardcoded via `USE_FIXED_SIZE`) |
| `rc/rc_curve.cpp` | Price curve parameter generation |
| `rc/resource_user.cpp` | RC payer determination (first-authority rule with special cases) |
| `rc/rc_objects.cpp` | Stats aggregation and archive rotation |
| `util/rd.cpp` | `rd_apply()`, `rd_compute_pool_decay()`, `rd_setup_dynamics_params()` |
| `database_hardfork.cpp:336-416` | HF20 RC initialization |
| `libraries/jsonball/data/resource_parameters.json` | Source parameters (human-readable) |
| `programs/build_helpers/hive_build_helpers/rc_generate_resource_parameters.py` | Build-time transform to runtime params |
| `libraries/jsonball/CMakeLists.txt` | Build-time pipeline for resource parameter generation |
| `plugins/apis/rc_api/rc_api.cpp` | RC API implementation |
| `protocol/include/hive/protocol/hive_custom_operations.hpp` | `delegate_rc_operation`; `HIVE_RC_CUSTOM_OPERATION_ID = "rc"` |
| `protocol/include/hive/protocol/config.hpp:390-494` | RC-related constants |

---

## Discrepancies and Potential Issues

1. **Non-consensus enforcement gap**: A rogue witness could include RC-violating transactions in their block. With HF26, such txs are logged (not asserted) on non-producing nodes. In-flight TODO at `rc_utility.cpp:545-546`: "Add || db.has_hardfork( X ) to make RC part of consensus since X / we should also replace all NOTIFYALERT warnings in RC with assertions, since they can't ever happen."

2. **`last_max_rc` drift detection is after-the-fact**: On testnet it asserts; on mainnet it only `wlog` NOTIFYALERT (`rc_utility.cpp:336-342`). Multiple other drift-related warnings exist at `:369-376`, `:394-400`. None are consensus-rejections on mainnet.

3. **`delegate_rc_time = 75000` ns is a one-shot estimate**: Comment at `resource_sizes.cpp:227-229`: "this is cost over custom json processing (difference between RC delegation and dummy custom json of the same size); while it depends on number of delegatees, the differences should be neglegible so it was collected for 10 delegatees / once we have real uses of RC delegation we can correct actual average time consumption." The value was measured for 10 delegatees and applied uniformly.

4. **Metadata not charged is a consensus loophole**: Because `json_metadata` storage is plugin-dependent (optional `metadata` plugin), charging it would cause RC divergence. Result: users can stuff unlimited metadata without RC cost. Mitigation would require HAF migration or making metadata consensus-storable.

5. **Fixed vs dynamic object sizes**: `#define USE_FIXED_SIZE` (`resource_sizes.cpp:26`) hardcodes all state object sizes. The disabled dynamic path uses `sizeof(type)` with a static_assert that fixed matches dynamic; this is only enabled during hardfork development to flag when chain object layout changes. In production, adding a field to a state object silently leaves the RC cost computed using the old size.

6. **Execution time benchmarks are stale by design**: Times from `https://gitlab.syncad.com/hive/hive/-/issues/205` are baked into `resource_sizes.cpp:167-242`. Improvements in hived's internal implementation over time could make these values inaccurate (overestimates vs actual CPU cost). No automated re-measurement cadence exists. The cost changes would also need a hardfork if they alter `is_in_control` enforcement outcomes.

7. **`max_pool_size` is unused for the RC pool update**: The RC pool update in `finalize_block` (`rc_utility.cpp:768`) is manual: `new_pool = pool - decay + budget - usage`, clamped only to `>= 0`. It does NOT apply `rd_apply()` which would clamp to `max_pool_size`. So the JSON-provided `max_pool_size = 2 * pool_eq` is effectively a dead field for RC resources. `rd_apply` is only used in the consensus subsidy paths (`database.cpp:1827` for global, `database_witness.cpp:214` for per-witness). For `resource_new_accounts`, witness-driven `rd_setup_dynamics_params` (`database_init.cpp:360-361`, `witness_schedule.cpp:138-139`) sets `max_pool_size = pool_eq`, but again this only matters for the witness-subsidy `rd_apply` path, not for the RC pool itself which syncs from `dgpo.available_account_subsidies`.

8. **Delegation overflow iteration is FIFO not by-size**: `remove_delegations` iterates `by_from` (ID order, smallest-first). A TODO comment at `rc_utility.cpp:643-644` notes this may cause many small delegations to be reduced before one large one.

9. **`market_op_count` is once-per-tx, not once-per-op**: If a tx contains 5 market ops, it's charged full `tx_size` as market bytes ONCE (not 5x). Possibly intentional batching discount; not documented as such.

10. **`decay_per_time_unit_denom_shift` is not actually user-settable**: The `rd_setup_dynamics_params` asserts `system_params.decay_per_time_unit_denom_shift == HIVE_RD_DECAY_DENOM_SHIFT` (`rd.cpp:78`). The struct `rd_system_params` suggests it's configurable, but the implementation rejects anything other than 36. Comment at `rd.cpp:73-77`: "TLDR, if you trigger this FC_ASSERT(), you've created a bug."

---

## Open Questions

1. **How to migrate RC to consensus**: The TODO has persisted since HF20. Making RC consensus requires:
   - Fully deterministic state evolution across all nodes (currently non-deterministic corner cases exist, e.g., metadata exclusion, fixed-vs-dynamic sizes)
   - Handling the historical non-consensus blocks during replay (would need to skip enforcement pre-activation)
   - Agreement on what happens to pre-activation accounts whose current_mana may differ between independent replays of the same history
   - Possibly deprecating some non-determinism sources (e.g., making metadata mandatory in state)

2. **Execution time measurement refresh**: No automated CI job re-measures the benchmarks from GitLab issue #205. When hived is optimized or new operations are added, the benchmarks grow stale. Would require a reproducible benchmark harness and a policy for when to update them (with hardfork implications).

3. **Can RC pool grow arbitrarily large when underused?** In `finalize_block`, there's no upper-bound clamp on the RC pool — only `new_pool = max(new_pool, 0)`. Over long periods of low usage, the pool will grow toward (and past?) `pool_eq` based on `pool - decay + budget - usage`. At equilibrium, decay == budget, so pool stabilizes. But during sustained underuse, the pool grows until decay catches up with budget (always at `pool_eq`). So in practice the pool can only settle at `pool_eq` — but nothing in the update code enforces a hard upper bound. Is this safe under all witness-settable decay values? The JSON has `max_pool_size = 2 * pool_eq` but it's unused for the RC pool update.

---

## Out-of-Scope / Zoom Candidates

The following topics could deepen via a dedicated investigation:

1. **Witness account subsidy pool dynamics**: The full witness-side `account_subsidy_rd` tracking — per-witness pools, global subsidy pool, interactions between `HIVE_WITNESS_SUBSIDY_BUDGET_PERCENT` and `HIVE_WITNESS_SUBSIDY_DECAY_PERCENT`, and how witness rotation affects subsidy availability.
2. **RC delegation discovery in full context**: How `rc_direct_delegation_index` interacts with HAF backfills and API consumers; possible regression vectors on the `by_from` iteration ordering.
3. **Pool-curve calibration**: Monte-carlo analysis of cost variance for typical operations at various pool levels, cross-referenced against the 8 payer ranks to understand real-world affordability.
4. **Interaction of RC stats with mirrornet/testnet configs**: Config-driven differences in `rc_stats_report_frequency`, `allow_not_enough_rc`, and how they affect testing vs mainnet behavior.
