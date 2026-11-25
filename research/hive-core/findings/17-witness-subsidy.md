# Findings: witness-subsidy

> Source: hive-core, pinned SHA `274384a8adddf54b69965a7fd43d8eb0ddda7701` (release `1.28.8`).
> Entry files: `libraries/chain/rc/rc_utility.cpp`, `libraries/chain/database_witness.cpp`.
> Every `file:line` below is from the worktree at that SHA.

## Summary

"Witness subsidy" is the consensus mechanism for **free (fee-less) account creation**: witnesses
vote on a per-block `account_subsidy_budget` and `account_subsidy_decay`; the medians feed a
**resource-dynamics (rd)** model that runs **two parallel stockpile pools** every block — one
network-wide consensus pool (`dynamic_global_property_object::available_account_subsidies`) and one
**per-witness** pool (`witness_object::available_witness_account_subsidies`). A subsidized
`claim_account_operation` (fee == 0) draws `HIVE_ACCOUNT_SUBSIDY_PRECISION` (10000) units from the
network pool and, while the transaction is applied as part of a block, also from the per-witness
pool of the block's producing witness, whose `schedule` must be `elected`: the network pool limits
subsidized claims chain-wide, the per-witness pool limits those in one witness's blocks to that
witness's own share. The same witness-voted rd params are also pushed into the RC subsystem
(`resource_new_accounts`), the single point where the RC pool, non-consensus until HF29 (Part 01,
section HF29 (Defined in 1.28.8, Inactive on Mainnet)), is force-slaved to a consensus value - this part documents the **witness side** of that bridge, which Parts 08 and 15
explicitly deferred.

## Key Discoveries

### 1. Two-tier pool architecture: global consensus pool + per-witness pool
- **What**: Subsidized account creation is gated by **two** independently-decaying pools that are
  *both* checked and *both* decremented on every fee-less claim applied in a block (outside a block
  only the global pool, Key Discovery 5):
  - Global: `dynamic_global_property_object::available_account_subsidies` (`int64_t`,
    `global_property_object.hpp:264`).
  - Per-witness: `witness_object::available_witness_account_subsidies` (`int64_t`,
    `witness_objects.hpp:161`).
- **Where**: Consumption at `hive_evaluator_account.cpp:423-437`; per-block replenishment at
  `database.cpp:1869-1883` (`process_subsidized_accounts`).
- **Impact**: The global pool limits subsidized claims chain-wide; the per-witness pool limits the
  subsidized claims in the blocks a witness produces to that witness's own accumulated share. The
  inline comment at `hive_evaluator_account.cpp:411-416` gives the rationale: RC is not consensus
  (until HF29, Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)), so subsidized claims
  are limited to the producing witness's own share of subsidies, and the check runs only when the
  transaction can be attributed to a block producer.

### 2. Parameter pipeline: vote → median → rd params → (consensus pools + RC pool)
- **What**: Witnesses set `account_subsidy_budget`/`account_subsidy_decay` only via
  `witness_set_properties_operation` (the legacy `witness_update_operation` copies only the account
  creation fee, the maximum block size and the HBD interest rate, `hive_evaluator.cpp:55-60`); these
  are stored on the witness's `props` (`chain_properties`). Each witness-schedule rotation,
  `update_median_witness_props`
  takes the **median over the scheduled witnesses** and converts it — through
  `rd_setup_dynamics_params` — into two cached `rd_dynamics_params` on the witness schedule object:
  `account_subsidy_rd` (network) and `account_subsidy_witness_rd` (per-witness). The network rd is
  *also* copied into the RC `resource_new_accounts` params via `set_pool_params`.
- **Where**: vote storage `hive_evaluator.cpp:156-164,194-197`; median + rd setup
  `witness_schedule.cpp:88-145`; RC push `witness_schedule.cpp:437-438` → `rc_utility.cpp:864-882`.
- **Impact**: All four downstream artifacts (global pool growth, per-witness pool growth, RC pool
  level, RC price curve for fee-less claims, the only claims charged on `resource_new_accounts`,
  `rc/resource_count.cpp:425-430`) trace back to the same two median-voted numbers.

### 3. The resource-dynamics (rd) math is a decaying budgeted pool with an equilibrium cap
- **What**: `rd_apply(rd, pool)` = `clamp(pool + budget − max(decay, min_decay), 0, max_pool_size)`,
  where `decay = (decay_per_time_unit · pool) >> 36` capped at `pool`, and `max_pool_size = pool_eq =
  ceil((budget << 36) / decay)` is the smallest pool where decay ≥ budget (so an unconsumed pool
  rises to `pool_eq` and stops).
- **Where**: `util/rd.cpp:43-54` (`rd_apply`), `:23-41` (`rd_compute_pool_decay`), `:56-119`
  (`rd_setup_dynamics_params` — computes `pool_eq`).
- **Impact**: With default params the network pool tops out at `pool_eq ≈ 157.7M` units
  (`≈ 15,769` accounts) and the max *sustained* creation rate is `budget/precision = 797/10000 ≈
  0.0797 accounts/block` (`~ 2,295/day` at 3 s blocks). Decay gives a half-life of ~4.76 days; the
  code comment on the default decay says 5 days (see The rd math).

### 4. Per-witness scaling: 125% budget, 21× decay, replenished once per round — so the GLOBAL pool runs out first
- **What**: The per-witness rd is derived from the same medians but scaled:
  `w_budget = median_budget · 125%`, `w_decay = median_decay · 2100%` (i.e. ×21 = ×`HIVE_MAX_WITNESSES`),
  each clamped to `int32`/`uint32` (`witness_schedule.cpp:116-125`). The per-witness pool is advanced
  by `rd_apply` **only on the block the witness itself produces, and only if it is `elected`**
  (`database_witness.cpp:207-217`, called for `gpo.get_current_witness()` at `database.cpp:1881-1882`).
- **Where**: scaling constants `protocol/config.hpp:406-413`; once-per-round application
  `database_witness.cpp:210-216`.
- **Impact**: ×21 decay compensates for the pool decaying only ~once per 21-block round, giving the
  same *real-time* decay as the network pool (comment `protocol/config.hpp:410-412`). The +25% budget boost
  makes the summed per-witness print capacity (~20 × 996/round ≈ 19,920) exceed the global budget
  (797/block × 21 ≈ 16,737/round), so under normal load the **global** pool is the binding
  constraint and empties first - exactly the design intent stated at `protocol/config.hpp:406-407`.

### 5. Consumption is `elected`-only and block-attributed (the p2p propagation nuance)
- **What**: A fee-less `claim_account` requires the producing witness to be `elected` and to have
  per-witness subsidies — **but only when `is_processing_block()`**. When merely validating a loose
  transaction (not yet in a block), only the *global* pool is checked; the per-witness/elected checks
  are skipped.
- **Where**: `hive_evaluator_account.cpp:417-437`; rationale comment `:411-416`.
- **Impact**: This prevents nodes from dropping (and refusing to propagate) otherwise-valid
  subsidized claims just because the *current head* witness happens to have an exhausted pool. The
  per-witness rule binds only once the tx is attributed to a concrete block producer.

### 6. The RC `resource_new_accounts` pool is force-slaved to the consensus pool every block
- **What**: In `finalize_block`, the RC pool for `resource_new_accounts` is computed like any other
  resource and then **discarded** in favor of `dgpo.available_account_subsidies`, logging any delta.
- **Where**: `rc_utility.cpp:801-810`.
- **Impact**: This is the only hard coupling between the RC system, non-consensus until HF29 (Part 08,
  section Non-Consensus Status), and consensus. The witness-voted subsidy params therefore control
  *both* the consensus free-account allowance *and*
  (via the same `account_subsidy_rd` and the regenerated price curve) the **RC price a normal user
  pays** to claim an account with RC. Complements Part 15 Discovery 5 / Part 08 §"`resource_new_accounts`
  Special Handling".

### 7. `witness_schedule_object::min_witness_account_subsidy_decay` is a dead field (always 0)
- **What**: This field is declared, default-0, copied in `copy_values_from`, FC-reflected, and
  surfaced by **three** APIs (database_api, condenser_api, debug_node_api) — but **never assigned a
  computed value anywhere in chain code**. The real per-witness decay backstop is written to
  `account_subsidy_witness_rd.min_decay` instead (`witness_schedule.cpp:144`).
- **Where**: declaration `witness_objects.hpp:206`; the only writes are the default-init and the
  `copy_values_from` propagation (`witness_objects.hpp:230`); never set in
  `witness_schedule.cpp`/`database_init.cpp`.
- **Impact**: Any consumer reading `min_witness_account_subsidy_decay` from the APIs gets a constant
  `0`, which is **not** the actual minimum decay (that lives inside the nested
  `account_subsidy_witness_rd.min_decay`). Misleading-but-harmless API surface. See Discrepancies D1.

### 8. The "0.5 accounts per block" config comment does not match the default budget
- **What**: `protocol/config.hpp:417-418` comments `HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET (797)` as "Default
  rate is 0.5 accounts per block." With `HIVE_ACCOUNT_SUBSIDY_PRECISION = 10000` units per account,
  797 units/block = **~0.0797 accounts/block**, off by ~6.3×. `0.5` instead matches the RC price
  curve's `u_point = 1/2` (`rc_curve.hpp:17-18`), a dimensionless curve anchor — likely the source
  of the confusion. See Discrepancies D2.

## Data Structures

### `chain_properties` (witness-voted) — `witness_objects.hpp:34-62`
| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `account_subsidy_budget` | `int32_t` | `797` (`HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET`) | Pool units added per block; `HIVE_ACCOUNT_SUBSIDY_PRECISION (10000)` = one account (`witness_objects.hpp:50-54`). |
| `account_subsidy_decay` | `uint32_t` | `347321` (`HIVE_DEFAULT_ACCOUNT_SUBSIDY_DECAY`) | Fraction-per-block of pool that expires; `1 << 36` = 100%/block (`witness_objects.hpp:56-61`). 347321 gives a ~4.76-day half-life at one decay per block (the code comment says 5 days; see The rd math). |

(Validation ranges: budget ∈ `[HIVE_RD_MIN_BUDGET=1, HIVE_RD_MAX_BUDGET=268435455]`, decay ∈
`[HIVE_RD_MIN_DECAY=64, HIVE_RD_MAX_DECAY=4294967295]` — `hive_operations.cpp:375-395`.)

### `rd_dynamics_params` — `util/rd_dynamics.hpp:26-59`
`resource_unit`, `budget_per_time_unit (int32)`, `pool_eq`, `max_pool_size`, `decay_params`,
`min_decay`. `decay_params` = `{decay_per_time_unit (uint32), decay_per_time_unit_denom_shift (uint8)}`
(`rd_dynamics.hpp:11-24`). The witness schedule caches two of these: `account_subsidy_rd`,
`account_subsidy_witness_rd` (`witness_objects.hpp:204-205`).

### `rd_user_params` / `rd_system_params` — `util/rd_setup.hpp:18-29`
User-settable: `{budget_per_time_unit, decay_per_time_unit}`. System-fixed: `{resource_unit,
decay_per_time_unit_denom_shift = HIVE_RD_DECAY_DENOM_SHIFT (36)}`.

### Consensus state fields
- `dynamic_global_property_object::available_account_subsidies` - `int64_t`, `global_property_object.hpp:264`;
  private since 1.28.8, read and written through `get_available_account_subsidies()` /
  `set_available_account_subsidies()` (`global_property_object.hpp:167`, `:185`).
- `witness_object::available_witness_account_subsidies` - `int64_t`, `witness_objects.hpp:161`.
- `account_object::pending_claimed_accounts` — incremented on claim, decremented on
  `create_claimed_account` (`hive_evaluator_account.cpp:450,470`).

## Constants (all from `protocol/config.hpp`)

| Constant | Value | Line | Role |
|----------|-------|------|------|
| `HIVE_ACCOUNT_SUBSIDY_PRECISION` | `HIVE_100_PERCENT` = 10000 | 404 | Pool units per one account (claim cost; rd `resource_unit`). |
| `HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET` | 797 | 418 | Default per-block budget. |
| `HIVE_DEFAULT_ACCOUNT_SUBSIDY_DECAY` | 347321 | 416 | Default decay (the code comment, `protocol/config.hpp:415`, says a 5-day half-life; ~4.76 days per The rd math). |
| `HIVE_WITNESS_SUBSIDY_BUDGET_PERCENT` | 125*`HIVE_1_PERCENT` = 12500 | 408 | Per-witness budget = 125% of network. |
| `HIVE_WITNESS_SUBSIDY_DECAY_PERCENT` | `HIVE_MAX_WITNESSES`*`HIVE_100_PERCENT` = 210000 | 413 | Per-witness decay = x21. |
| `HIVE_DECAY_BACKSTOP_PERCENT` | 90*`HIVE_1_PERCENT` = 9000 | 419 | Per-witness `min_decay` = 90% of median observed decay. |
| `HIVE_RD_DECAY_DENOM_SHIFT` | 36 | 394 | Decay/`pool_eq` denominator shift. |
| `HIVE_RD_MIN_DECAY` | `1<<6` = 64 | 400 | Min votable decay (guarantees rd setup never divides by 0). |
| `HIVE_RD_MAX_DECAY` | `0xFFFFFFFF` | 402 | Max votable decay. |
| `HIVE_RD_MIN_BUDGET` / `HIVE_RD_MAX_BUDGET` | 1 / 268435455 (`=2^28-1`) | 401,399 | Votable budget range. |
| `HIVE_MAX_WITNESSES` | 21 | 65 | Round length / decay multiplier. |

## The rd math (verified `util/rd.cpp`)

```
rd_compute_pool_decay(dp, pool, dt):                 # :23-41  (odd: decay(-p) = -decay(p))
    decay = (dp.decay_per_time_unit · dt · pool) >> dp.denom_shift
    return min(decay, pool)                           # never decay below 0

rd_apply(rd, pool):                                   # :43-54  (dt hard-coded = 1)
    decay   = max(rd_compute_pool_decay(rd.decay, pool, 1), rd.min_decay)
    new     = pool + rd.budget − decay
    return clamp(new, 0, rd.max_pool_size)

rd_setup_dynamics_params(user, sys, out):             # util/rd.cpp:56-119
    out.budget = user.budget; out.decay = {user.decay, sys.denom_shift}; out.resource_unit = sys.resource_unit
    assert sys.denom_shift == HIVE_RD_DECAY_DENOM_SHIFT          # :78
    out.pool_eq = out.max_pool_size = ceil((user.budget << 36) / user.decay)   # :94-99
    assert  decay(pool_eq)   ≥ budget                           # :117
    assert  decay(pool_eq-1) < budget                           # :118  (pool_eq is minimal)
```

`rd_validate_user_params` (`:14-21`) bounds-checks budget/decay — **but it is called only for the
network params** (`witness_schedule.cpp:128`), not the per-witness params (see D3).

Default-parameter derivations (for orientation; arithmetic, not code):
- Network `pool_eq = ceil((797·2^36)/347321) ≈ 157.7M` units `≈ 15,769` accounts (cap on global stockpile).
- Per-witness: `w_budget = 797·1.25 = 996`, `w_decay = 347321·21 = 7,293,741`,
  `pool_eq ≈ (996·2^36)/7,293,741 ≈ 9.38M` units `≈ 938` accounts (per-witness stockpile cap).
- Half-life: `decay_fraction/block = 347321/2^36 ~ 5.054e-6` -> `ln2/5.054e-6 ~ 137,143` blocks ~ 4.76 days
  at one decay step per 3 s block. This figure follows from the constant; the code comment above it says
  "347321 corresponds to a 5-day halflife" (`protocol/config.hpp:415-416`).

## Lifecycle / message flow

1. **Vote.** `witness_set_properties_evaluator` (HF20+, `hive_evaluator.cpp:113-208`) writes
   `account_subsidy_budget`/`decay` into the witness's `props` only if the corresponding key is
   present (`hive_evaluator.cpp:156-164,194-197`); the legacy `witness_update_evaluator`
   (`hive_evaluator.cpp:62-99`) copies only the account creation fee, the maximum block size and the
   HBD interest rate (`hive_evaluator.cpp:55-60`). `validate()` enforces the
   rd ranges (`hive_operations.cpp:375-395`).
2. **Median + rd setup.** Once per round, inside `update_witness_schedule(4)`
   (`witness_schedule.cpp:152-396`), `update_median_witness_props` (`:58-150`):
   - medians of `account_subsidy_budget` (`:88-93`), `account_subsidy_decay` (`:95-100`), and of the
     witnesses' current `available_witness_account_subsidies` (`:102-107`);
   - builds network user params and per-witness user params (x125% / x21, clamped)
     (`witness_schedule.cpp:109-125`);
   - `rd_validate_user_params(network)` (`:128`); `rd_setup_dynamics_params` for both rds (`:138-139`);
   - per-witness `min_decay` backstop: `min_decay = 90% · rd_compute_pool_decay(witness_rd.decay,
     median_available_witness_subsidies, 1)`, stored on `account_subsidy_witness_rd.min_decay`
     (`witness_schedule.cpp:141-144`).
3. **Push to RC.** Still per round, `set_pool_params(wso)` copies `account_subsidy_rd` into
   `resource_param_array[resource_new_accounts]` and regenerates the price curve **iff** it changed
   (`witness_schedule.cpp:437-438` → `rc_utility.cpp:864-882`; curve gen `rc_curve.cpp:33-99`).
4. **Per-block replenish.** `process_subsidized_accounts` (`database.cpp:1869-1883`, called from
   `_apply_block` at `database.cpp:2357`, **after** `update_witness_schedule` at `database.cpp:2345`):
   - global pool: `available_account_subsidies = rd_apply(account_subsidy_rd, available_account_subsidies)` — **every block**;
   - per-witness pool: `update_witness_schedule_for_elected(current_witness, account_subsidy_witness_rd)`
     applies `rd_apply` **only if `current_witness.schedule == elected`** (`database_witness.cpp:210-216`).
5. **RC reconciliation.** `rc().finalize_block` (`rc_utility.cpp:765-828`) recomputes every RC pool,
   then overwrites `resource_new_accounts` with `dgpo.get_available_account_subsidies()`
   (`rc_utility.cpp:801-810`).
6. **Consume.** `claim_account_operation` with `fee == 0` (`hive_evaluator_account.cpp:394-453`):
   if `is_processing_block()`, require `elected` + per-witness pool ≥ 10000 and subtract 10000
   (`hive_evaluator_account.cpp:417-430`); then unconditionally require global pool >= 10000 and
   subtract 10000 (`hive_evaluator_account.cpp:432-437`); `pending_claimed_accounts++`. Later,
   `create_claimed_account_operation` (`hive_evaluator_account.cpp:455-479`) spends one
   `pending_claimed_accounts` to instantiate the account.

## Hardfork-conditional behavior

- **HF20** introduces the entire subsidy system. `witness_set_properties` (`HIVE_HARDFORK_0_20__1620`,
  `hive_evaluator.cpp:115`), `claim_account`/`create_claimed_account` (`HIVE_HARDFORK_0_20__1771`,
  `hive_evaluator_account.cpp:396,457`). Both markers equal `HIVE_HARDFORK_0_20`
  (`hardfork.d/0_20.hf:32,38`). RC itself is HF20-gated (`rc_utility.cpp:767,832`). See Part 09 for
  activation history.
- **HF20 activation block** (`database_hardfork.cpp:331-412`): resets `available_account_subsidies = 0`
  (`database_hardfork.cpp:340`); loads RC params from the compiled jsonball and **immediately
  overrides** `resource_new_accounts` via `set_pool_params(wso)` (`database_hardfork.cpp:381`). Note: the **per-witness**
  pools are *not* reset here.
- **Genesis** (`database_init.cpp:308-332`): builds both rds from the default `median_props`, but does
  **not** compute `account_subsidy_witness_rd.min_decay` (stays 0 until the first
  `update_median_witness_props`). Benign — see D4.
- **HF26** (`HIVE_HARDFORK_1_26_FUTURE_WITNESS_SCHEDULE`): `update_witness_schedule4`, and with it
  `update_median_witness_props`, runs on the future schedule object; each rotation first promotes the
  future object to the current one with `copy_values_from`, which also copies `median_props`,
  `account_subsidy_rd` and `account_subsidy_witness_rd` (`witness_schedule.cpp:410-431`,
  `witness_objects.hpp:219`, `:228-229`). The subsidy params in force during a round are therefore
  the medians of that round's witnesses, taken one rotation earlier (Part 06, section Future Witness
  Schedule (HF26+)); the subsidy math is unchanged.
- **HF27** (`HIVE_HARDFORK_1_27_FIX_TIMESHARE_WITNESS_SCHEDULING`): not subsidy-specific, but it
  changes which schedule object vote-weight math reads (`database_witness.cpp:71-72`,
  `witness_schedule.cpp:23-24`); relevant only because it touches the same witness scheduling path
  that drives subsidy median computation.
- **HF28** (`HIVE_HARDFORK_1_28_GLOBAL_WITNESS_PROPS`): moves *when* global witness props are copied
  to dgpo (`witness_schedule.cpp:147-148,428-429`); does not change subsidy math.
- **HF29** (defined in 1.28.8, inactive on mainnet): no subsidy code path in this part is HF29-gated
  (`hive_evaluator_account.cpp:394-453`, `database.cpp:1869-1883`, `database_witness.cpp:207-217`,
  `witness_schedule.cpp:58-150`, `rc_utility.cpp:765-828`, `:864-882`); the "until HF29" remarks on
  RC refer to its `RC_IS_CONSENSUS` switch (Part 01, section HF29 (Defined in 1.28.8, Inactive on
  Mainnet)).

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Per-block pool update (both pools) | `chain/database.cpp` | 1869-1883 | `process_subsidized_accounts` |
| Call site (block apply) | `chain/database.cpp` | 2357 | inside `_apply_block` (`:2200`), after schedule update |
| Per-witness pool `rd_apply` (elected only) | `chain/database_witness.cpp` | 207-217 | `update_witness_schedule_for_elected` |
| Median + rd param derivation | `chain/witness_schedule.cpp` | 58-150 | `update_median_witness_props` |
| ↳ median budget / decay | `chain/witness_schedule.cpp` | 88-100 | medians over scheduled witnesses |
| ↳ per-witness ×125% / ×21 scaling | `chain/witness_schedule.cpp` | 116-125 | `w_budget` / `w_decay` |
| ↳ rd setup + `min_decay` backstop | `chain/witness_schedule.cpp` | 138-144 | both rds + 90% decay floor |
| RC param push on schedule change | `chain/witness_schedule.cpp` | 437-438 | `set_pool_params(wso)` |
| RC param/curve update | `chain/rc/rc_utility.cpp` | 864-882 | `set_pool_params` |
| RC pool -> consensus override | `chain/rc/rc_utility.cpp` | 801-810 | new_accounts slaved to `available_account_subsidies` |
| RC regen-share weights | `chain/include/.../rc/rc_objects.hpp` | 81-95,108 | `recalculate_resource_weights` / `get_weight_divisor` |
| RC cost / regen share | `chain/rc/rc_utility.cpp` | 299-329 | `compute_cost`; `pool_regen_share` at `:319` |
| RC price-curve generation | `chain/rc/rc_curve.cpp` | 33-99 | `generate_rc_curve_params` (a=37/1000, u=1/2) |
| Consumption (fee==0 path) | `chain/hive_evaluator_account.cpp` | 394-453 | `claim_account_evaluator` |
| -> block-attribution / elected / per-witness | `chain/hive_evaluator_account.cpp` | 417-430 | `is_processing_block()` gate |
| -> global pool assert/decrement | `chain/hive_evaluator_account.cpp` | 432-437 | unconditional |
| Account instantiation | `chain/hive_evaluator_account.cpp` | 455-479 | `create_claimed_account_evaluator` |
| Vote storage | `chain/hive_evaluator.cpp` | 113-208 | `witness_set_properties_evaluator` |
| Vote validation | `protocol/hive_operations.cpp` | 375-395 | budget/decay ranges |
| rd math | `chain/util/rd.cpp` | 14-119 | apply / decay / setup / validate |
| rd structs | `chain/include/.../util/rd_dynamics.hpp` | 11-59 | `rd_decay_params`, `rd_dynamics_params` |
| `chain_properties` | `chain/include/.../witness_objects.hpp` | 34-62 | voted budget/decay |
| Per-witness pool field | `chain/include/.../witness_objects.hpp` | 161 | `available_witness_account_subsidies` |
| Schedule rd cache + dead field | `chain/include/.../witness_objects.hpp` | 204-206,230 | `account_subsidy_rd`, `min_witness_account_subsidy_decay` |
| Global pool field | `chain/include/.../global_property_object.hpp` | 264 | `available_account_subsidies` |
| Genesis init | `chain/database_init.cpp` | 308-332 | both rds (no `min_decay`) |
| HF20 init | `chain/database_hardfork.cpp` | 331-412 | reset global pool; override RC new_accounts |
| Constants | `protocol/include/.../config.hpp` | 392-419 | rd + subsidy constants |
| jsonball placeholder | `jsonball/data/resource_parameters.json` | new_accounts entry | budget 797, unit 10^4, "recalculated with account subsidy witness params" |

## Cross-references to existing parts

- **Part 15 (rc-consensus): completes a deferred zoom.** Part 15's section Open Questions, item 2,
  flags "Witness-side subsidy print/decay calibration" as "already flagged as a zoom candidate by
  Part 08" and says "this zoom confirms the consensus asserts but not the economics." This part
  supplies that: the two-tier pool model, the ×125%/×21 scaling, once-per-round per-witness decay,
  and why the global pool is the binding constraint. Part 15 Discovery 5 (the new_accounts→consensus
  bridge) is the RC-side mirror of this part's Key Discovery 6 — they agree.
- **Part 08 (resource-credits): complements; agrees.** Part 08 covers the RC-side pool,
  `set_pool_params`, the curve, and, in section Pool Equilibrium, `pool_eq = 157691079` units at the
  witness defaults (this part: ~157.7M, the same value). Part 08's section Resource Weights
  (Popularity-Based Regen Share) gives new_accounts a **100%** regen share and states that there is
  no `2 x sum` divisor; it formerly stated 50%, the error this part recorded as D5. The code's
  `get_weight_divisor()` returns `sum_of_resource_weights` (`rc_objects.hpp:108`), which is the sum
  of the **other** resources' weights only: inside `recalculate_resource_weights` the sum is reset at
  `rc_objects.hpp:83` and accumulated only at `rc_objects.hpp:92`, and the
  `resource_weights[new_accounts] = sum_of_resource_weights` assignment (`rc_objects.hpp:94`) does
  **not** feed back into it. So new_accounts' `pool_regen_share = sum_others / sum_others = 100%` of
  `rc_regen`, matching the code's own `//always 100%` comment (`rc_objects.hpp:94`) and the class
  comment (`rc_objects.hpp:41-42`). See D5.
- **Part 05 (state-objects): deepens.** Adds the read/write story for `available_account_subsidies`,
  `available_witness_account_subsidies`, the two `rd_dynamics_params` on the schedule object, and the
  unused `min_witness_account_subsidy_decay`.
- **Part 06 (consensus): deepens.** Drills into the `account_subsidy_*` slice of
  `update_median_witness_props`, which Part 06 covers at the scheduling level.
- **Part 04 (evaluators) / Part 03 (validation) / Part 02 (operations): deepens.** Full pre/side/post
  conditions for `claim_account`, `create_claimed_account`, `witness_set_properties`.
- **Part 09 (hardforks): complements.** Subsidies = HF20; defer activation block/history to Part 09.

## Discrepancies and Potential Issues

- **D1 — `min_witness_account_subsidy_decay` is dead/misleading (medium-relevance, non-consensus).**
  Declared, copied, reflected, and exposed by database_api/condenser_api/debug_node_api, but never
  assigned a computed value (`witness_objects.hpp:206`; verified no writes outside default-init and
  `copy_values_from`). API consumers always read `0`; the real floor is the nested
  `account_subsidy_witness_rd.min_decay` (`witness_schedule.cpp:144`). Either wire it up or drop it
  from the API surface.

- **D2 - "0.5 accounts per block" comment is ~6.3x off (doc-only).** `protocol/config.hpp:417`. Budget 797 /
  precision 10000 = ~0.0797 accounts/block. `0.5` matches the curve `u_point = 1/2`
  (`rc_curve.hpp:17-18`), a different quantity. The `chain_properties` field comment ("per elected
  witness block", `witness_objects.hpp:50-54`) is also slightly imprecise: the **global** pool budget
  is applied on *every* block in `process_subsidized_accounts`, not only on elected-witness blocks
  (the per-block-per-witness framing is accurate only for the per-witness pool).

- **D3 — Per-witness rd params bypass `rd_validate_user_params` and can exceed `HIVE_RD_MAX_BUDGET`
  (robustness note; not exploitable).** Only the network params are validated
  (`witness_schedule.cpp:128`); the comment there ("median of valid params should always be valid")
  reasons about the network params only. The per-witness budget is `median·1.25`, so at the votable
  max it reaches `268,435,455·1.25 = 335,544,318` > `HIVE_RD_MAX_BUDGET (268,435,455)`. The
  `static_assert` in `rd_setup_dynamics_params` (`rd.cpp:91-92`) proves `budget << 36 < 2^64` *only*
  for `budget ≤ HIVE_RD_MAX_BUDGET`; the per-witness budget violates that premise, and correctness is
  preserved **only** because the intermediate `temp` is `uint128_t` (`rd.cpp:94`). The subsequent
  divide by `w_decay ≥ 64·21 = 1344` keeps `pool_eq` within `uint64`. Division-by-zero is impossible
  because `HIVE_RD_MIN_DECAY = 64 > 0` floors every votable decay. No bug at current constants, but
  the safety margin depends on the uint128 intermediate and on `HIVE_RD_MAX_BUDGET` staying ≤ ~2^28.

- **D4 — Genesis omits the per-witness `min_decay` (benign).** `database_init.cpp:308-332` mirrors
  `update_median_witness_props` but skips the `rd_compute_pool_decay`/90% backstop step, so
  `account_subsidy_witness_rd.min_decay = 0` until the first witness-schedule rotation populates it.
  Harmless (claims are HF20-gated and the global pool is reset at HF20 anyway).

- **D5 - Part 08's former "50% regen share for new_accounts" contradicted the code (KB correction,
  resolved in the KB).** See Cross-references. Code yields 100%; the `2 x sum` divisor Part 08 assumed
  does not exist. Part 08's section Resource Weights (Popularity-Based Regen Share) now states the
  100% share.

- **Observation (not a defect) — pre-HF20 accumulation.** `process_subsidized_accounts` has no
  hardfork guard and runs in `_apply_block` from genesis. Pre-HF20 the global pool would grow toward
  `pool_eq`, but HF20 resets it to 0 (`database_hardfork.cpp:340`). Per-witness pools also grow
  pre-HF20 for elected producers and are **not** reset at HF20, so witnesses could carry a non-zero
  per-witness balance into HF20 — immaterial since claims are HF20-gated, but worth recording.

## Open Questions

1. **Backup-witness reachability of subsidized claims (economics).** Per-witness `pool_eq ≈ 938`
   accounts at defaults and replenishment only on the witness's own blocks - but a subsidized claim in
   a block requires the producing witness's `schedule == elected` (`hive_evaluator_account.cpp:420`).
   Can a `timeshare`/backup witness ever
   accumulate or use a per-witness balance? The pool is advanced only when `schedule == elected`
   (`database_witness.cpp:210`), so backups appear to neither accrue nor spend. Confirming the exact
   accrual/eligibility across schedule transitions (e.g. a witness moving elected→timeshare→elected)
   needs a runtime/test trace — candidate for a future zoom or a `rc_tests.cpp` reading.
2. **Effect of irregular production cadence on the ×21 decay assumption.** The ×21 multiplier assumes
   exactly one decay per 21-block round. A witness that misses rounds or produces out of cadence sees
   a different *effective* real-time decay. Quantifying the drift is out of scope here (needs
   simulation against `update_witness_missed_blocks`).
3. **Is the dead `min_witness_account_subsidy_decay` (D1) a renamed/relocated field?** Worth a quick
   git-history check to see whether it once held the value now in `account_subsidy_witness_rd.min_decay`
   — informs whether to wire it up or remove it.
   **Answered from git history up to 1.28.8: yes, relocated.** Commit `00f227212` ("Factor out
   functionality into rd_apply #2786", 2018-08-23, an ancestor of 1.28.8) replaced the write
   `_wso.min_witness_account_subsidy_decay = min_decay` in `update_median_witness_props` with
   `_wso.account_subsidy_witness_rd.min_decay = min_decay`, and the read
   `decay = std::max( decay, wso.min_witness_account_subsidy_decay )` in `process_subsidized_accounts`
   with the `rd.min_decay` floor of the new `rd_apply`; the old field stayed declared and reflected,
   and since commit `bf3b6202a` (2022-07-24, the HF26 future witness schedule) `copy_values_from`
   also copies it, as at 1.28.8 (D1).

```results
PART: 17
AREA: witness-subsidy
STATUS: COMPLETE
OUTPUT_FILES:
- research/hive-core/findings/17-witness-subsidy.md
KEY_FINDINGS:
- Subsidized (fee==0) account creation runs two parallel rd-decaying pools: a network consensus pool (dgpo.available_account_subsidies) and a per-witness pool (witness_object.available_witness_account_subsidies); a claim in a block draws HIVE_ACCOUNT_SUBSIDY_PRECISION=10000 units from BOTH, outside a block only from the network pool (database.cpp:1869-1883, hive_evaluator_account.cpp:417-437).
- Witness-voted budget/decay are medianed each round (witness_schedule.cpp:58-150) into account_subsidy_rd (network) and account_subsidy_witness_rd (per-witness, scaled +25% budget / x21 decay so the global pool is the binding constraint); the network rd is also pushed into the RC resource_new_accounts params (set_pool_params, rc_utility.cpp:864-882).
- Per-witness pool is advanced by rd_apply only on the producing witness's own block and only if elected (database_witness.cpp:207-217); claim's per-witness/elected checks fire only when is_processing_block() so loose txs still propagate (hive_evaluator_account.cpp:411-430).
- min_witness_account_subsidy_decay (witness_schedule_object) is a dead field: never computed, always 0, yet exposed by 3 APIs; the real floor lives in account_subsidy_witness_rd.min_decay (D1). Config comment "0.5 accounts/block" mismatches budget 797/precision 10000 = ~0.0797/block (D2).
- CORRECTION to Part 08: new_accounts gets 100% of rc_regen as pool_regen_share (get_weight_divisor = sum of OTHER weights only; rc_objects.hpp:83,92,94,108), not the 50% Part 08 formerly stated; Part 08 now states 100% (D5).
CROSS_REFS:
- Part 15 (rc-consensus): completes its explicitly-deferred witness-side subsidy zoom; agrees on the new_accounts->consensus bridge.
- Part 08 (resource-credits): complements RC-side coverage; its former "50% regen share" claim is corrected to 100% in Part 08 itself (D5).
- Part 05 (state-objects), Part 06 (consensus), Part 04/03/02 (evaluators/validation/operations), Part 09 (hardforks): deepened/complemented.
BLOCKERS:
- None
```