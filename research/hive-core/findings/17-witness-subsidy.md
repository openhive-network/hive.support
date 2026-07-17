# Findings: witness-subsidy

> Source: hive-core, pinned SHA `1584099c3054a97f02abfb4788b23f02eea98728` (release `1.28.7`).
> Entry files: `libraries/chain/rc/rc_utility.cpp`, `libraries/chain/database_witness.cpp`.
> Every `file:line` below is from the worktree at that SHA.

## Summary

"Witness subsidy" is the consensus mechanism for **free (fee-less) account creation**: witnesses
vote on a per-block `account_subsidy_budget` and `account_subsidy_decay`; the medians feed a
**resource-dynamics (rd)** model that runs **two parallel stockpile pools** every block — one
network-wide consensus pool (`dynamic_global_property_object::available_account_subsidies`) and one
**per-witness** pool (`witness_object::available_witness_account_subsidies`). A subsidized
`claim_account_operation` (fee == 0) draws `HIVE_ACCOUNT_SUBSIDY_PRECISION` (10000) units from
*both* pools; the per-witness pool exists purely so a rogue/buggy witness can drain at most its own
share of the network pool rather than the whole thing. The same witness-voted rd params are also
pushed into the RC subsystem (`resource_new_accounts`), which is the single point where the
otherwise-non-consensus RC pool is force-slaved to a consensus value — this part documents the
**witness side** of that bridge, which Parts 08 and 15 explicitly deferred.

## Key Discoveries

### 1. Two-tier pool architecture: global consensus pool + per-witness anti-abuse pool
- **What**: Subsidized account creation is gated by **two** independently-decaying pools that are
  *both* checked and *both* decremented on every fee-less claim:
  - Global: `dynamic_global_property_object::available_account_subsidies` (`int64_t`,
    `global_property_object.hpp:143`).
  - Per-witness: `witness_object::available_witness_account_subsidies` (`int64_t`,
    `witness_objects.hpp:162`).
- **Where**: Consumption at `hive_evaluator_account.cpp:431-446`; per-block replenishment at
  `database.cpp:1819-1833` (`process_subsidized_accounts`).
- **Impact**: The per-witness pool is the abuse-limiter. RC is non-consensus (a rogue witness could
  sign transactions that ignore RC), so without it a single witness could drain the *entire* global
  free-account stockpile. With it, a witness can only spend its own accumulated share. The inline
  comment at `hive_evaluator_account.cpp:420-425` states this rationale explicitly.

### 2. Parameter pipeline: vote → median → rd params → (consensus pools + RC pool)
- **What**: Witnesses set `account_subsidy_budget`/`account_subsidy_decay` via
  `witness_set_properties_operation` (or legacy `witness_update_operation`); these are stored on the
  witness's `props` (`chain_properties`). Each witness-schedule rotation, `update_median_witness_props`
  takes the **median over the scheduled witnesses** and converts it — through
  `rd_setup_dynamics_params` — into two cached `rd_dynamics_params` on the witness schedule object:
  `account_subsidy_rd` (network) and `account_subsidy_witness_rd` (per-witness). The network rd is
  *also* copied into the RC `resource_new_accounts` params via `set_pool_params`.
- **Where**: vote storage `hive_evaluator.cpp:156-164,194-197`; median + rd setup
  `witness_schedule.cpp:88-145`; RC push `witness_schedule.cpp:437-438` → `rc_utility.cpp:833-851`.
- **Impact**: All four downstream artifacts (global pool growth, per-witness pool growth, RC pool
  level, RC price curve for paid claims) trace back to the same two median-voted numbers.

### 3. The resource-dynamics (rd) math is a decaying budgeted pool with an equilibrium cap
- **What**: `rd_apply(rd, pool)` = `clamp(pool + budget − max(decay, min_decay), 0, max_pool_size)`,
  where `decay = (decay_per_time_unit · pool) >> 36` capped at `pool`, and `max_pool_size = pool_eq =
  ceil((budget << 36) / decay)` is the smallest pool where decay ≥ budget (so an unconsumed pool
  rises to `pool_eq` and stops).
- **Where**: `util/rd.cpp:43-54` (`rd_apply`), `:23-41` (`rd_compute_pool_decay`), `:56-119`
  (`rd_setup_dynamics_params` — computes `pool_eq`).
- **Impact**: With default params the network pool tops out at `pool_eq ≈ 157.7M` units
  (`≈ 15,769` accounts) and the max *sustained* creation rate is `budget/precision = 797/10000 ≈
  0.0797 accounts/block` (`≈ 2,295/day` at 3 s blocks). Decay gives a ~5-day half-life.

### 4. Per-witness scaling: 125% budget, 21× decay, replenished once per round — so the GLOBAL pool runs out first
- **What**: The per-witness rd is derived from the same medians but scaled:
  `w_budget = median_budget · 125%`, `w_decay = median_decay · 2100%` (i.e. ×21 = ×`HIVE_MAX_WITNESSES`),
  each clamped to `int32`/`uint32` (`witness_schedule.cpp:116-125`). The per-witness pool is advanced
  by `rd_apply` **only on the block the witness itself produces, and only if it is `elected`**
  (`database_witness.cpp:207-217`, called for `gpo.current_witness` at `database.cpp:1831-1832`).
- **Where**: scaling constants `config.hpp:407-414`; once-per-round application
  `database_witness.cpp:210-216`.
- **Impact**: ×21 decay compensates for the pool decaying only ~once per 21-block round, giving the
  same *real-time* decay as the network pool (comment `config.hpp:411-413`). The +25% budget boost
  makes the summed per-witness print capacity (~20 × 996/round ≈ 19,920) exceed the global budget
  (797/block × 21 ≈ 16,737/round), so under normal load the **global** pool is the binding
  constraint and empties first — exactly the design intent stated at `config.hpp:407-408`.

### 5. Consumption is `elected`-only and block-attributed (the p2p propagation nuance)
- **What**: A fee-less `claim_account` requires the producing witness to be `elected` and to have
  per-witness subsidies — **but only when `is_processing_block()`**. When merely validating a loose
  transaction (not yet in a block), only the *global* pool is checked; the per-witness/elected checks
  are skipped.
- **Where**: `hive_evaluator_account.cpp:426-446`; rationale comment `:420-425`.
- **Impact**: This prevents nodes from dropping (and refusing to propagate) otherwise-valid
  subsidized claims just because the *current head* witness happens to have an exhausted pool. The
  per-witness rule binds only once the tx is attributed to a concrete block producer.

### 6. The RC `resource_new_accounts` pool is force-slaved to the consensus pool every block
- **What**: In `finalize_block`, the RC pool for `resource_new_accounts` is computed like any other
  resource and then **discarded** in favor of `dgpo.available_account_subsidies`, logging any delta.
- **Where**: `rc_utility.cpp:770-779`.
- **Impact**: This is the only hard coupling between the non-consensus RC system and consensus. The
  witness-voted subsidy params therefore control *both* the consensus free-account allowance *and*
  (via the same `account_subsidy_rd` and the regenerated price curve) the **RC price a normal user
  pays** to claim an account with RC. Complements Part 15 Discovery 5 / Part 08 §"`resource_new_accounts`
  Special Handling".

### 7. `witness_schedule_object::min_witness_account_subsidy_decay` is a dead field (always 0)
- **What**: This field is declared, default-0, copied in `copy_values_from`, FC-reflected, and
  surfaced by **three** APIs (database_api, condenser_api, debug_node_api) — but **never assigned a
  computed value anywhere in chain code**. The real per-witness decay backstop is written to
  `account_subsidy_witness_rd.min_decay` instead (`witness_schedule.cpp:144`).
- **Where**: declaration `witness_objects.hpp:208`; the only writes are the default-init and the
  `copy_values_from` propagation `:232`; never set in `witness_schedule.cpp`/`database_init.cpp`.
- **Impact**: Any consumer reading `min_witness_account_subsidy_decay` from the APIs gets a constant
  `0`, which is **not** the actual minimum decay (that lives inside the nested
  `account_subsidy_witness_rd.min_decay`). Misleading-but-harmless API surface. See Discrepancies D1.

### 8. The "0.5 accounts per block" config comment does not match the default budget
- **What**: `config.hpp:418-419` comments `HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET (797)` as "Default
  rate is 0.5 accounts per block." With `HIVE_ACCOUNT_SUBSIDY_PRECISION = 10000` units per account,
  797 units/block = **~0.0797 accounts/block**, off by ~6.3×. `0.5` instead matches the RC price
  curve's `u_point = 1/2` (`rc_curve.hpp:17-18`), a dimensionless curve anchor — likely the source
  of the confusion. See Discrepancies D2.

## Data Structures

### `chain_properties` (witness-voted) — `witness_objects.hpp:34-62`
| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `account_subsidy_budget` | `int32_t` | `797` (`HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET`) | Pool units added per block; `HIVE_ACCOUNT_SUBSIDY_PRECISION (10000)` = one account (`:50-54`). |
| `account_subsidy_decay` | `uint32_t` | `347321` (`HIVE_DEFAULT_ACCOUNT_SUBSIDY_DECAY`) | Fraction-per-block of pool that expires; `1 << 36` = 100%/block (`:56-61`). 347321 ≈ 5-day half-life. |

(Validation ranges: budget ∈ `[HIVE_RD_MIN_BUDGET=1, HIVE_RD_MAX_BUDGET=268435455]`, decay ∈
`[HIVE_RD_MIN_DECAY=64, HIVE_RD_MAX_DECAY=4294967295]` — `hive_operations.cpp:375-395`.)

### `rd_dynamics_params` — `util/rd_dynamics.hpp:26-59`
`resource_unit`, `budget_per_time_unit (int32)`, `pool_eq`, `max_pool_size`, `decay_params`,
`min_decay`. `decay_params` = `{decay_per_time_unit (uint32), decay_per_time_unit_denom_shift (uint8)}`
(`:11-24`). The witness schedule caches two of these: `account_subsidy_rd`,
`account_subsidy_witness_rd` (`witness_objects.hpp:206-207`).

### `rd_user_params` / `rd_system_params` — `util/rd_setup.hpp:18-29`
User-settable: `{budget_per_time_unit, decay_per_time_unit}`. System-fixed: `{resource_unit,
decay_per_time_unit_denom_shift = HIVE_RD_DECAY_DENOM_SHIFT (36)}`.

### Consensus state fields
- `dynamic_global_property_object::available_account_subsidies` — `int64_t`, `global_property_object.hpp:143`.
- `witness_object::available_witness_account_subsidies` — `int64_t`, `witness_objects.hpp:162`.
- `account_object::pending_claimed_accounts` — incremented on claim, decremented on
  `create_claimed_account` (`hive_evaluator_account.cpp:460,480`).

## Constants (all from `config.hpp`)

| Constant | Value | Line | Role |
|----------|-------|------|------|
| `HIVE_ACCOUNT_SUBSIDY_PRECISION` | `HIVE_100_PERCENT` = 10000 | 405 | Pool units per one account (claim cost; rd `resource_unit`). |
| `HIVE_DEFAULT_ACCOUNT_SUBSIDY_BUDGET` | 797 | 419 | Default per-block budget. |
| `HIVE_DEFAULT_ACCOUNT_SUBSIDY_DECAY` | 347321 | 417 | Default decay (5-day half-life). |
| `HIVE_WITNESS_SUBSIDY_BUDGET_PERCENT` | 125·`HIVE_1_PERCENT` = 12500 | 409 | Per-witness budget = 125% of network. |
| `HIVE_WITNESS_SUBSIDY_DECAY_PERCENT` | `HIVE_MAX_WITNESSES`·`HIVE_100_PERCENT` = 210000 | 414 | Per-witness decay = ×21. |
| `HIVE_DECAY_BACKSTOP_PERCENT` | 90·`HIVE_1_PERCENT` = 9000 | 420 | Per-witness `min_decay` = 90% of median observed decay. |
| `HIVE_RD_DECAY_DENOM_SHIFT` | 36 | 395 | Decay/`pool_eq` denominator shift. |
| `HIVE_RD_MIN_DECAY` | `1<<6` = 64 | 401 | Min votable decay (guarantees rd setup never divides by 0). |
| `HIVE_RD_MAX_DECAY` | `0xFFFFFFFF` | 403 | Max votable decay. |
| `HIVE_RD_MIN_BUDGET` / `HIVE_RD_MAX_BUDGET` | 1 / 268435455 (`=2^28−1`) | 402,400 | Votable budget range. |
| `HIVE_MAX_WITNESSES` | 21 | 62 | Round length / decay multiplier. |

## The rd math (verified `util/rd.cpp`)

```
rd_compute_pool_decay(dp, pool, dt):                 # :23-41  (odd: decay(-p) = -decay(p))
    decay = (dp.decay_per_time_unit · dt · pool) >> dp.denom_shift
    return min(decay, pool)                           # never decay below 0

rd_apply(rd, pool):                                   # :43-54  (dt hard-coded = 1)
    decay   = max(rd_compute_pool_decay(rd.decay, pool, 1), rd.min_decay)
    new     = pool + rd.budget − decay
    return clamp(new, 0, rd.max_pool_size)

rd_setup_dynamics_params(user, sys, out):             # :56-119
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
- Half-life: `decay_fraction/block = 347321/2^36 ≈ 5.05e-6` → `ln2/5.05e-6 ≈ 137,150` blocks ≈ 4.76 d.

## Lifecycle / message flow

1. **Vote.** `witness_set_properties_evaluator` (HF20+, `hive_evaluator.cpp:113-208`) or legacy
   `witness_update_evaluator` (`:62-99`) writes `account_subsidy_budget`/`decay` into the witness's
   `props` only if the corresponding key is present (`:156-164,194-197`). `validate()` enforces the
   rd ranges (`hive_operations.cpp:375-395`).
2. **Median + rd setup.** Once per round, inside `update_witness_schedule(4)`
   (`witness_schedule.cpp:152-396`), `update_median_witness_props` (`:58-150`):
   - medians of `account_subsidy_budget` (`:88-93`), `account_subsidy_decay` (`:95-100`), and of the
     witnesses' current `available_witness_account_subsidies` (`:102-107`);
   - builds network user params and per-witness user params (×125% / ×21, clamped) (`:109-125`);
   - `rd_validate_user_params(network)` (`:128`); `rd_setup_dynamics_params` for both rds (`:138-139`);
   - per-witness `min_decay` backstop: `min_decay = 90% · rd_compute_pool_decay(witness_rd.decay,
     median_available_witness_subsidies, 1)`, stored on `account_subsidy_witness_rd.min_decay`
     (`:141-144`).
3. **Push to RC.** Still per round, `set_pool_params(wso)` copies `account_subsidy_rd` into
   `resource_param_array[resource_new_accounts]` and regenerates the price curve **iff** it changed
   (`witness_schedule.cpp:437-438` → `rc_utility.cpp:833-851`; curve gen `rc_curve.cpp:32-98`).
4. **Per-block replenish.** `process_subsidized_accounts` (`database.cpp:1819-1833`, called from
   `_apply_block` at `:2340`, **after** `update_witness_schedule` at `:2328`):
   - global pool: `available_account_subsidies = rd_apply(account_subsidy_rd, available_account_subsidies)` — **every block**;
   - per-witness pool: `update_witness_schedule_for_elected(current_witness, account_subsidy_witness_rd)`
     applies `rd_apply` **only if `current_witness.schedule == elected`** (`database_witness.cpp:210-216`).
5. **RC reconciliation.** `rc().finalize_block` (`rc_utility.cpp:734-797`) recomputes every RC pool,
   then overwrites `resource_new_accounts` with `dgpo.available_account_subsidies` (`:770-779`).
6. **Consume.** `claim_account_operation` with `fee == 0` (`hive_evaluator_account.cpp:402-462`):
   if `is_processing_block()`, require `elected` + per-witness pool ≥ 10000 and subtract 10000
   (`:426-439`); then unconditionally require global pool ≥ 10000 and subtract 10000 (`:441-446`);
   `pending_claimed_accounts++`. Later, `create_claimed_account_operation` (`:464-497`) spends one
   `pending_claimed_accounts` to instantiate the account.

## Hardfork-conditional behavior

- **HF20** introduces the entire subsidy system. `witness_set_properties` (`HIVE_HARDFORK_0_20__1620`,
  `hive_evaluator.cpp:115`), `claim_account`/`create_claimed_account` (`HIVE_HARDFORK_0_20__1771`,
  `hive_evaluator_account.cpp:404,466`). All three markers equal `HIVE_HARDFORK_0_20`
  (`hardfork.d/0_20.hf:32,38`). RC itself is HF20-gated (`rc_utility.cpp:736,801`). See Part 09 for
  activation history.
- **HF20 activation block** (`database_hardfork.cpp:336-414`): resets `available_account_subsidies = 0`
  (`:345`); loads RC params from the compiled jsonball and **immediately overrides** `resource_new_accounts`
  via `set_pool_params(wso)` (`:386`). Note: the **per-witness** pools are *not* reset here.
- **Genesis** (`database_init.cpp:338-362`): builds both rds from the default `median_props`, but does
  **not** compute `account_subsidy_witness_rd.min_decay` (stays 0 until the first
  `update_median_witness_props`). Benign — see D4.
- **HF27** (`HIVE_HARDFORK_1_27_FIX_TIMESHARE_WITNESS_SCHEDULING`): not subsidy-specific, but it
  changes which schedule object vote-weight math reads (`database_witness.cpp:71-72`,
  `witness_schedule.cpp:23-24`); relevant only because it touches the same witness scheduling path
  that drives subsidy median computation.
- **HF28** (`HIVE_HARDFORK_1_28_GLOBAL_WITNESS_PROPS`): moves *when* global witness props are copied
  to dgpo (`witness_schedule.cpp:147-148,428-429`); does not change subsidy math.

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Per-block pool update (both pools) | `chain/database.cpp` | 1819-1833 | `process_subsidized_accounts` |
| Call site (block apply) | `chain/database.cpp` | 2340 | inside `_apply_block` (`:2183`), after schedule update |
| Per-witness pool `rd_apply` (elected only) | `chain/database_witness.cpp` | 207-217 | `update_witness_schedule_for_elected` |
| Median + rd param derivation | `chain/witness_schedule.cpp` | 58-150 | `update_median_witness_props` |
| ↳ median budget / decay | `chain/witness_schedule.cpp` | 88-100 | medians over scheduled witnesses |
| ↳ per-witness ×125% / ×21 scaling | `chain/witness_schedule.cpp` | 116-125 | `w_budget` / `w_decay` |
| ↳ rd setup + `min_decay` backstop | `chain/witness_schedule.cpp` | 138-144 | both rds + 90% decay floor |
| RC param push on schedule change | `chain/witness_schedule.cpp` | 437-438 | `set_pool_params(wso)` |
| RC param/curve update | `chain/rc/rc_utility.cpp` | 833-851 | `set_pool_params` |
| RC pool → consensus override | `chain/rc/rc_utility.cpp` | 770-779 | new_accounts slaved to `available_account_subsidies` |
| RC regen-share weights | `chain/include/.../rc/rc_objects.hpp` | 81-95,108 | `recalculate_resource_weights` / `get_weight_divisor` |
| RC cost / regen share | `chain/rc/rc_utility.cpp` | 286-316 | `compute_cost`; `pool_regen_share` at 306 |
| RC price-curve generation | `chain/rc/rc_curve.cpp` | 32-98 | `generate_rc_curve_params` (a=37/1000, u=1/2) |
| Consumption (fee==0 path) | `chain/hive_evaluator_account.cpp` | 402-462 | `claim_account_evaluator` |
| ↳ block-attribution / elected / per-witness | `chain/hive_evaluator_account.cpp` | 426-439 | `is_processing_block()` gate |
| ↳ global pool assert/decrement | `chain/hive_evaluator_account.cpp` | 441-446 | unconditional |
| Account instantiation | `chain/hive_evaluator_account.cpp` | 464-497 | `create_claimed_account_evaluator` |
| Vote storage | `chain/hive_evaluator.cpp` | 113-208 | `witness_set_properties_evaluator` |
| Vote validation | `protocol/hive_operations.cpp` | 375-395 | budget/decay ranges |
| rd math | `chain/util/rd.cpp` | 14-119 | apply / decay / setup / validate |
| rd structs | `chain/include/.../util/rd_dynamics.hpp` | 11-59 | `rd_decay_params`, `rd_dynamics_params` |
| `chain_properties` | `chain/include/.../witness_objects.hpp` | 34-62 | voted budget/decay |
| Per-witness pool field | `chain/include/.../witness_objects.hpp` | 162 | `available_witness_account_subsidies` |
| Schedule rd cache + dead field | `chain/include/.../witness_objects.hpp` | 206-208,232 | `account_subsidy_rd`, `min_witness_account_subsidy_decay` |
| Global pool field | `chain/include/.../global_property_object.hpp` | 143 | `available_account_subsidies` |
| Genesis init | `chain/database_init.cpp` | 338-362 | both rds (no `min_decay`) |
| HF20 init | `chain/database_hardfork.cpp` | 336-414 | reset global pool; override RC new_accounts |
| Constants | `protocol/include/.../config.hpp` | 393-420 | rd + subsidy constants |
| jsonball placeholder | `jsonball/data/resource_parameters.json` | new_accounts entry | budget 797, unit 10^4, "recalculated with account subsidy witness params" |

## Cross-references to existing parts

- **Part 15 (rc-consensus): completes a deferred zoom.** Part 15's Open Question #2 (line ~168)
  explicitly flags "Witness-side subsidy print/decay calibration … already flagged as a zoom
  candidate by Part 08; this zoom confirms the consensus asserts but not the economics." This part
  supplies that: the two-tier pool model, the ×125%/×21 scaling, once-per-round per-witness decay,
  and why the global pool is the binding constraint. Part 15 Discovery 5 (the new_accounts→consensus
  bridge) is the RC-side mirror of this part's Key Discovery 6 — they agree.
- **Part 08 (resource-credits): complements + one correction.** Part 08 covers the RC-side pool,
  `set_pool_params`, the curve, and `pool_eq ≈ 157.8M` (this part: `≈157.7M`, same value modulo
  rounding). **Correction**: Part 08 §"Resource Weights" (lines 562-568) states new_accounts gets a
  **50%** regen share via a `2×sum` divisor. The code's `get_weight_divisor()` returns
  `sum_of_resource_weights`, which is the sum of the **other** resources' weights only — the
  `resource_weights[new_accounts] = sum_of_resource_weights` assignment (`rc_objects.hpp:94`) does
  **not** feed back into the sum (verified: only writes at `:83,92`). So new_accounts'
  `pool_regen_share = sum_others / sum_others = 100%` of `rc_regen`, matching the code's own
  `// always 100%` comment (`:94`) and the class comment (`:41-42`). See D5; merits a contrib note
  to Part 08.
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
  assigned a computed value (`witness_objects.hpp:208`; verified no writes outside default-init and
  `copy_values_from`). API consumers always read `0`; the real floor is the nested
  `account_subsidy_witness_rd.min_decay` (`witness_schedule.cpp:144`). Either wire it up or drop it
  from the API surface.

- **D2 — "0.5 accounts per block" comment is ~6.3× off (doc-only).** `config.hpp:418`. Budget 797 /
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

- **D4 — Genesis omits the per-witness `min_decay` (benign).** `database_init.cpp:338-362` mirrors
  `update_median_witness_props` but skips the `rd_compute_pool_decay`/90% backstop step, so
  `account_subsidy_witness_rd.min_decay = 0` until the first witness-schedule rotation populates it.
  Harmless (claims are HF20-gated and the global pool is reset at HF20 anyway).

- **D5 — Part 08's "50% regen share for new_accounts" contradicts the code (KB correction).** See
  Cross-references. Code yields 100%; the `2×sum` divisor assumed by Part 08 does not exist.

- **Observation (not a defect) — pre-HF20 accumulation.** `process_subsidized_accounts` has no
  hardfork guard and runs in `_apply_block` from genesis. Pre-HF20 the global pool would grow toward
  `pool_eq`, but HF20 resets it to 0 (`database_hardfork.cpp:345`). Per-witness pools also grow
  pre-HF20 for elected producers and are **not** reset at HF20, so witnesses could carry a non-zero
  per-witness balance into HF20 — immaterial since claims are HF20-gated, but worth recording.

## Open Questions

1. **Backup-witness reachability of subsidized claims (economics).** Per-witness `pool_eq ≈ 938`
   accounts at defaults and replenishment only on the witness's own blocks — but only `elected`
   witnesses may claim (`hive_evaluator_account.cpp:429`). Can a `timeshare`/backup witness ever
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

```results
PART: 17
AREA: witness-subsidy
STATUS: COMPLETE
OUTPUT_FILES:
- research/hive-core/findings/17-witness-subsidy.md
KEY_FINDINGS:
- Subsidized (fee==0) account creation runs two parallel rd-decaying pools: a network consensus pool (dgpo.available_account_subsidies) and a per-witness anti-abuse pool (witness_object.available_witness_account_subsidies); a claim draws HIVE_ACCOUNT_SUBSIDY_PRECISION=10000 units from BOTH (database.cpp:1819-1833, hive_evaluator_account.cpp:426-446).
- Witness-voted budget/decay are medianed each round (witness_schedule.cpp:58-150) into account_subsidy_rd (network) and account_subsidy_witness_rd (per-witness, scaled +25% budget / x21 decay so the global pool is the binding constraint); the network rd is also pushed into the RC resource_new_accounts params (set_pool_params, rc_utility.cpp:833-851).
- Per-witness pool is advanced by rd_apply only on the producing witness's own block and only if elected (database_witness.cpp:207-217); claim's per-witness/elected checks fire only when is_processing_block() so loose txs still propagate (hive_evaluator_account.cpp:420-439).
- min_witness_account_subsidy_decay (witness_schedule_object) is a dead field: never computed, always 0, yet exposed by 3 APIs; the real floor lives in account_subsidy_witness_rd.min_decay (D1). Config comment "0.5 accounts/block" mismatches budget 797/precision 10000 = ~0.0797/block (D2).
- CORRECTION to Part 08: new_accounts gets 100% of rc_regen as pool_regen_share (get_weight_divisor = sum of OTHER weights only; rc_objects.hpp:83,92,94,108), not the 50% Part 08 states (D5).
CROSS_REFS:
- Part 15 (rc-consensus): completes its explicitly-deferred witness-side subsidy zoom; agrees on the new_accounts->consensus bridge.
- Part 08 (resource-credits): complements RC-side coverage; CORRECTS its "50% regen share" claim to 100% (needs contrib note).
- Part 05 (state-objects), Part 06 (consensus), Part 04/03/02 (evaluators/validation/operations), Part 09 (hardforks): deepened/complemented.
BLOCKERS:
- None
```