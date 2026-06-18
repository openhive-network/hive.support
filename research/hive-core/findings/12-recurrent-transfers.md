# Findings: recurrent-transfers

> Zoom deep-dive. Source pinned at hive-core `10ac0ce94f7591b6ad80db1a23d046c9d57b6559`
> (release `1.28.6`). Every `file:line` below refers to that worktree. Where a claim
> depends on git history, the commit hash and its ancestry relative to the pinned SHA
> are stated explicitly.

## Summary

Recurrent transfers (introduced in HF25) let an account schedule a fixed-asset transfer to
another account that fires every `recurrence` hours for `executions` iterations. State lives
in a single `recurrent_transfer_object` per `(from, to, pair_id)` triple; the operation
evaluator does create/update/delete CRUD, while block-processing
(`process_recurrent_transfers()`, run once per block) walks a trigger-date-ordered index and
executes due transfers, emitting `fill_recurrent_transfer_operation` or
`failed_recurrent_transfer_operation` virtual ops. The most consequential discoveries at this
SHA: (1) the **only active hardfork gate is HF25** — the HF28 `pair_id` guard and a pre-HF28
"faulty" end-date check were both *removed* as replay-safe cleanup (commit `b155eb62e`); (2)
scheduling is **grid-anchored, not drifting** — late execution never shifts the schedule
(empirically asserted by a unit test); and (3) `executions >= 2` is enforced in `validate()`
on **every** path including deletion, a restriction that a *future* HF29 (absent here) relaxes.

## Key Discoveries

### 1. Only HF25 is an active hardfork gate at this SHA; the HF28 `pair_id` guard was removed
- **What**: The evaluator and the block processor each gate the *entire* feature on
  `HIVE_HARDFORK_1_25` and nothing else. The `pair_id` extension (documented as "Since HF28")
  has **no** HF28 assertion anywhere in the worktree. The guard
  `FC_ASSERT( !was_pair_id || has_hardfork(HIVE_HARDFORK_1_28), ... )` existed in an ancestor
  commit (`8ab354b9c`) but was deleted by ancestor commit `b155eb62e` ("clean transfer
  operations and their handling code") together with a pre-HF28 "Legacy faulty validation
  (issue #456)" duration check.
- **Where**: `libraries/chain/hive_evaluator_transfer.cpp:908` (HF25, the only gate);
  `:916` (`op.get_pair_id()` called with no version check);
  `libraries/chain/database_dhf.cpp:39` (HF25 gate in processing). Removal verified via
  `git show b155eb62e -- libraries/chain/hive_evaluator_transfer.cpp`.
- **Impact**: At this SHA the code carries **no explicit version gate** for the `pair_id`
  extension or for the post-HF28 end-date formula. Correctness now rests on the historical
  invariant that no pre-HF28 mainnet block can contain a `pair_id` op or an over-long transfer
  (the guards were active when those blocks were produced, so such ops were rejected at the
  time and cannot appear in canonical history). The removal is **replay-safe for mainnet** but
  is a deliberate simplification, not a still-present assertion. See *Discrepancies* §1.

### 2. Scheduling is grid-anchored (no drift), even when execution is deferred
- **What**: `update_next_trigger_date()` does `trigger_date += fc::hours(recurrence)` — it
  advances from the object's **previous** trigger date, not from `now`. A transfer deferred to
  a later block (because the per-block cap was hit) therefore keeps its place on the original
  time grid; its next fire is `original + N × recurrence`, regardless of when it actually ran.
- **Where**: `libraries/chain/include/hive/chain/detail/state/recurrent_transfer_object.hpp:26-29`.
  Empirically asserted in `tests/unit/tests/operation_tests.cpp:9930, 9943, 9959, 9970`
  (a transfer deferred by one block still has `trigger_date == creation + days(1)`, identical
  to the on-time transfers).
- **Impact**: Predictable cadence; backlog does not cause schedule slippage. (Contrast
  `set_recurrence_trigger_date()` at `:42-48`, used by the *update* path, which re-anchors to
  `head_block_time + recurrence` **only if** `recurrence` changed.)

### 3. `executions >= 2` is enforced in `validate()` on every path, including delete
- **What**: `validate()` unconditionally requires `executions >= 2` and
  `recurrence >= HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` (24h on mainnet) — with **no**
  branch on `amount`. Because deletion is expressed as `amount == 0`, a *delete* operation
  must still carry `executions >= 2` and `recurrence >= 24` to pass protocol validation.
- **Where**: `libraries/protocol/hive_operations.cpp:807-825` (executions check at `:819-823`,
  recurrence at `:815`).
- **Impact**: You cannot reduce a transfer to a single final execution, nor cancel one while
  setting `executions = 1`. A *future* commit (`8d435f016`, **not** an ancestor of this SHA)
  moves these checks to the evaluator and lets `executions == 1` on modify/delete once
  `HIVE_HARDFORK_1_29_ALLOW_MODIFY_LAST_RECURRENT_TRANSFER` activates — that constant does not
  exist at this SHA. See *Discoveries* §9 and *Open Questions*.

### 4. RC state cost scales with the transfer's whole lifetime (`recurrence × executions`)
- **What**: The RC state-byte charge is
  `(recurrent_transfer_base_size + memo_char_size × memo.size()) × lifetime`, where
  `lifetime = op.recurrence × op.executions` (in hours). It is charged **only** when
  `op.amount.amount > 0` (so a pure delete pays no state cost). Execution-time cost adds a base
  plus `processing_time × op.executions`. The op is counted as a market operation.
- **Where**: `libraries/chain/rc/resource_count.cpp:517-527` (lifetime at `:521`); sizes at
  `libraries/chain/rc/resource_sizes.cpp:156-160` (base = `SIZE(node,200) × TEMPORARY_STATE_BYTE`,
  per-char = `TEMPORARY_STATE_BYTE`) and `:225-226` (times).
- **Impact**: Longer/denser schedules cost proportionally more RC up front; the `TEMPORARY`
  byte class reflects that state is reclaimed when the transfer completes or is removed.

### 5. The `dynamic_global_property_object` "limit" fields are informational mirrors, not consensus inputs
- **What**: `dgpo` exposes `max_consecutive_recurrent_transfer_failures`,
  `max_recurrent_transfer_end_date`, `min_recurrent_transfers_recurrence`,
  `max_open_recurrent_transfers`, each initialised to its `HIVE_*` constant. Consensus code
  **never reads them** — the evaluator and processor use the compile-time `HIVE_*` macros
  directly. The dgpo fields are only copied into `condenser_api`/`database_api` responses.
- **Where**: fields at
  `libraries/chain/include/hive/chain/detail/state/global_property_object.hpp:166-169`;
  all readers are API constructors only (`database_api_objects_constructors.cpp:184-187`,
  `condenser_api.hpp:317-320`) — no consensus reader exists (verified by exhaustive grep).
- **Impact**: These fields are a client-facing convenience; they are not (and cannot be) tuned
  at runtime to change behavior. The source of truth is the constants.

### 6. `consecutive_failures` resets only on a *successful* execution — never on user update
- **What**: A successful fire sets `consecutive_failures = 0`; a failed fire increments it. The
  evaluator's *update* path rewrites `amount`, `memo`, `recurrence`, `remaining_executions`
  but leaves `consecutive_failures` untouched.
- **Where**: reset on success `database_dhf.cpp:90`; increment on failure `:113`; update path
  `hive_evaluator_transfer.cpp:947-953` (no failure-counter write).
- **Impact**: Editing a transfer that has been failing does not clear its strike count; only a
  funded execution does. After `HIVE_MAX_CONSECUTIVE_RECURRENT_TRANSFER_FAILURES` (10) in a
  row, the object is deleted.

### 7. A failed execution still consumes one of the remaining executions
- **What**: `remaining_executions` is decremented once per processing attempt
  (`const auto remaining_executions = current.remaining_executions - 1;`) and written back in
  **both** the success and the keep-after-failure branches. A failed fire is not retried; it
  burns a scheduled slot and reschedules to the next grid point.
- **Where**: `database_dhf.cpp:66` (decrement), `:92` (success writeback), `:115` (failure
  writeback). Comment confirms: "failed transfers are not automatically repeated"
  (`hive_virtual_operations.hpp:646`).
- **Impact**: Insufficient funds shorten the effective number of *successful* payments; the
  transfer still ends after the original number of scheduled iterations (or earlier, via the
  10-failure cap).

### 8. Per-block cap (1000) bounds work; overflow defers to later blocks
- **What**: `process_recurrent_transfers()` stops after
  `HIVE_MAX_RECURRENT_TRANSFERS_PER_BLOCK` (1000) executions in a block; remaining due
  transfers (earliest `trigger_date`, then lowest `id`) are processed in subsequent blocks.
- **Where**: `database_dhf.cpp:53-57`; ordering via the `by_trigger_date` index `:43`.
  Empirically: `operation_tests.cpp:9876-9975` creates 1004 due transfers and asserts exactly
  1000 fire in the first block and 4 in the second.
- **Impact**: A single block's transfer-processing cost is capped regardless of how many are
  due; combined with grid-anchoring (§2), short deferrals do not perturb the schedule.

### 9. API can only enumerate transfers by sender; the `<=`-bounded loop can return 1001 rows
- **What**: `database_api.find_recurrent_transfers({from})` queries the `by_from_id` index and
  returns transfers **sent** by an account. There is no by-recipient index, so a recipient
  cannot enumerate incoming recurrent transfers from chain state (only via account-history
  `fill_*` vops). The loop guard `result.size() <= DATABASE_API_SINGLE_QUERY_LIMIT` (1000) is
  inclusive, so up to **1001** objects can be returned.
- **Where**: `libraries/plugins/apis/database_api/database_api_financial.cpp:736-754`
  (`by_from_id` at `:743`, `<=` guard at `:746`); limit macro
  `database_api_args.hpp:11` (`DATABASE_API_SINGLE_QUERY_LIMIT 1000`).
- **Impact**: Off-by-one over-return (minor, non-consensus); and a real coverage gap for
  recipient-side discovery. See *Discrepancies* §3.

## Data Structures

### Operation: `recurrent_transfer_operation` (regular op #49)
`libraries/protocol/include/hive/protocol/hive_operations.hpp:1013-1039`,
reflected at `:1219`.

| Field | Type | Notes |
|-------|------|-------|
| `from` | `account_name_type` | source; requires active authority (`:1034`) |
| `to` | `account_name_type` | recipient |
| `amount` | `asset` | liquid (HIVE/HBD), non-vesting, non-negative; `amount == 0` ⇒ delete |
| `memo` | `string` | ≤ `HIVE_MAX_MEMO_SIZE - 1` (2047), UTF-8 |
| `recurrence` | `uint16_t` (hrs) | ≥ 24 (mainnet) |
| `executions` | `uint16_t` | ≥ 2 (this SHA, all paths) |
| `extensions` | `flat_set<recurrent_transfer_extension>` | only `recurrent_transfer_pair_id` supported |

`get_pair_id()` walks the extensions via `recurrent_transfer_extension_visitor`, returning the
`pair_id` (default 0) and optionally whether it was explicitly set (`was_pair_id`); the
evaluator call site passes `explicitValue = nullptr` so `was_pair_id` is discarded.
`hive_operations.cpp:832-864`.

### Extension: `recurrent_transfer_pair_id`
`libraries/protocol/include/hive/protocol/types.hpp:151-161` (a `static_variant<void_t,
recurrent_transfer_pair_id>`, with `uint8_t pair_id = 0`), reflected at `:187`.

### State object: `recurrent_transfer_object`
`libraries/chain/include/hive/chain/detail/state/recurrent_transfer_object.hpp:11-78`.

| Member | Type | Notes |
|--------|------|-------|
| `trigger_date` | `time_point_sec` (**private**) | next fire time; accessed via `get_trigger_date()` |
| `from_id` / `to_id` | `account_id_type` | stored as ids, not names |
| `amount` | `asset` | |
| `memo` | `shared_string` | dynamically allocated |
| `recurrence` | `uint16_t` | hours |
| `remaining_executions` | `uint16_t` | object removed when this would reach 0 |
| `consecutive_failures` | `uint8_t` | deleted at 10 in a row |
| `pair_id` | `uint8_t` | distinguishes multiple transfers to same `to` |

Behavioral methods: `update_next_trigger_date()` (`+= recurrence`, `:26-29`),
`get_final_trigger_date()` (`trigger_date + recurrence × (remaining_executions − 1)`, `:36-39`),
`set_recurrence_trigger_date()` (re-anchor to now iff recurrence changed, `:42-48`).

### Indices: `recurrent_transfer_index`
`libraries/chain/include/hive/chain/detail/state/recurrent_transfer_object_multiindex.hpp:9-36`.

| Tag | Key(s) | Used by |
|-----|--------|---------|
| `by_id` | `id` | generic |
| `by_trigger_date` | `(trigger_date, id)` | block processing (due order) `:14-19` |
| `by_from_id` | `(from_id, id)` | `find_recurrent_transfers` `:20-25` |
| `by_from_to_id` | `(from_id, to_id, pair_id)` **unique** | evaluator CRUD lookup `:26-33` |

There is **no** by-`to` index.

### Account counter
`account_object.open_recurrent_transfers` (`uint16_t`, max 255) tracks the number of live
objects an account sends; incremented on create, decremented on delete/removal.
`libraries/chain/include/hive/chain/detail/state/account_object.hpp:248`.

### Virtual operations
- `fill_recurrent_transfer_operation` — emitted on each successful fire; carries
  `from, to, amount, memo, remaining_executions, extensions`.
  `hive_virtual_operations.hpp:627-641`.
- `failed_recurrent_transfer_operation` — emitted when funds are insufficient; adds
  `consecutive_failures` and `deleted` (true iff the object was removed this attempt).
  `:650-666`.

Both are virtual ops (`operations.hpp:113-114`, `last_regular + 34 / + 35`), consistent with
the KB's 50-regular + 43-virtual count.

## Preconditions / Side Effects / Postconditions (evaluator)

`recurrent_transfer_evaluator::do_apply` — `hive_evaluator_transfer.cpp:906-957`.

**Preconditions (all paths):**
- `has_hardfork(HIVE_HARDFORK_1_25)` (`:908`).
- `from` and `to` accounts exist (`:910-911`).
- Sender's liquid balance in `amount.symbol` ≥ `amount` — the "first transfer" affordability
  check (`:913-914`). NB this checks affordability of *one* installment at submission time, not
  the whole schedule.

**Branch by `(existing object?, amount)`:**

| Case | Condition | Effect |
|------|-----------|--------|
| **Create** | no object for `(from,to,pair_id)` | assert `open_recurrent_transfers < 255` (`:923`); assert `amount != 0` (`:925`); create object with `trigger_date = head_block_time` (`:926`); assert `get_final_trigger_date() ≤ head_block_time + 730 days` (`:927-928`); `open_recurrent_transfers++` (`:930-933`) |
| **Delete** | object exists, `amount == 0` | remove object (`:937`); assert counter `> 0` then `--` (`:938-942`) |
| **Update** | object exists, `amount != 0` | overwrite `amount`, `memo`, `set_recurrence_trigger_date()`, `remaining_executions = op.executions` (`:947-953`); re-assert end-date ≤ 730 days (`:954-955`) |

**Postconditions of note:** create sets the first `trigger_date` to *now*, so the first
installment fires on the next block that runs processing (the transfer "executes immediately").
Update resets `remaining_executions` to the new `op.executions` (so editing can extend life),
and only moves `trigger_date` if `recurrence` changed.

## Block processing state machine

`database::process_recurrent_transfers()` — `database_dhf.cpp:37-144`, called from
`apply_block` (`database.cpp:2351`) after most other periodic processes.

```
if !has_hardfork(HF25): return
now = head_block_time()
itr = index<by_trigger_date>.begin()
while itr != end() && itr->trigger_date <= now:
    if processed >= 1000: break                      # per-block cap (:53)
    cur = *itr;  ++itr                               # advance BEFORE mutating (:59-60)
    assert cur.remaining_executions > 0              # (:65)
    rem = cur.remaining_executions - 1               # decrement once (:66)
    if balance(from, amount.symbol) >= cur.amount:   # success (:76)
        adjust_balance(from, -amount); adjust_balance(to, +amount)   # (:78-79)
        if rem == 0: remove_flag = true
        else: modify{ consecutive_failures = 0; trigger_date += recurrence; remaining = rem }
        emit fill_recurrent_transfer(... rem ...)     # (:96)
    else:                                            # insufficient funds (:98)
        cf = cur.consecutive_failures + 1
        if cf < 10:
            if rem == 0: remove_flag = true
            else: modify{ ++consecutive_failures; trigger_date += recurrence; remaining = rem }
            emit failed_recurrent_transfer(... cf, rem, deleted=remove_flag ...)   # (:119)
        else:                                        # 10th failure → kill (:121-127)
            remove_flag = true
            emit failed_recurrent_transfer(... cf, rem, deleted=true ...)
    if remove_flag: remove(cur); from.open_recurrent_transfers-- (assert >0)       # (:130-138)
    processed++
```

Key invariants enforced here: `remaining_executions > 0` for any persisted object (`:65`); the
sender counter never underflows (`FC_ASSERT(open_recurrent_transfers > 0)` at `:135`). The
`++itr` before mutation (`:60`) avoids iterator invalidation when `modify` relocates the object
in the `by_trigger_date` ordering.

## Hardfork-conditional behavior (verified evolution)

At the pinned SHA the **only** runtime hardfork condition in the entire flow is HF25. The
following version-gated branches existed earlier and were removed as post-HF28 cleanup. All
three commits below were confirmed ancestors of `10ac0ce94f` via `git merge-base --is-ancestor`.

| Behavior | History | At this SHA |
|----------|---------|-------------|
| Feature enablement | added HF25 | **active** (`hive_evaluator_transfer.cpp:908`, `database_dhf.cpp:39`) |
| `pair_id` extension | gated by `has_hardfork(HF28)` inside the visitor (`ae10dd10f`, 2023), moved to evaluator (`8ab354b9c`), then **removed** (`b155eb62e`) | **no gate** — accepted whenever HF25 active |
| End-date limit (pre-HF28) | "Legacy faulty validation, issue #456": `recurrence × executions hours < 730 days`, gated `!has_hardfork(HF28)`; **removed** by `b155eb62e` | gone — only the post-HF28 absolute check remains |
| End-date limit (post-HF28) | `get_final_trigger_date() ≤ head_block_time + 730 days` | **active** (`:927-928`, `:954-955`) |
| `failed_*` vop `deleted` flag | issue #769 (`19a89e7a9`): once hard-coded `false`, fixed to report real removal | **fixed** (`database_dhf.cpp:119`) |

The two pre-HF28 formulas differed: the old check used `recurrence × executions` strictly `<`
730 days; the new one uses `recurrence × (executions − 1)` (the span to the final fire) `≤`
730 days — the new form is slightly more permissive, which is exactly why relaxing it required
a hardfork. Removing the old branch is replay-safe because any op that would differ between the
two was rejected pre-HF28 and so cannot appear in a pre-HF28 block.

**Not present at this SHA (future work):** `HIVE_HARDFORK_1_29_ALLOW_MODIFY_LAST_RECURRENT_TRANSFER`
and the commits that introduce it (`8d435f016`, `2b42e9f48`) — verified **not** ancestors.
That future work moves the `executions` minimum into the evaluator and permits `executions == 1`
when modifying/deleting an existing transfer (issue #786), so a user can edit the last remaining
installment. Today that is impossible (see *Discoveries* §3).

## Constants

All from `libraries/protocol/include/hive/protocol/config.hpp`. The end-date / per-block /
min-recurrence trio is defined twice — once in the testnet branch (`:123-125`, where
`HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` is runtime-configurable via
`configuration_data.get_hive_min_recurrent_transfers_recurrence()`) and once in the live branch
(`:204-206`, hard-coded `24`). The two account/failure caps sit after the `#endif` and are
common to both networks.

| Constant | Value (mainnet) | Where |
|----------|-----------------|-------|
| `HIVE_MAX_RECURRENT_TRANSFER_END_DATE` | 730 (days) | `config.hpp:204` |
| `HIVE_MAX_RECURRENT_TRANSFERS_PER_BLOCK` | 1000 | `config.hpp:205` |
| `HIVE_MIN_RECURRENT_TRANSFERS_RECURRENCE` | 24 (hours) | `config.hpp:206` |
| `HIVE_MAX_OPEN_RECURRENT_TRANSFERS` | 255 | `config.hpp:241` |
| `HIVE_MAX_CONSECUTIVE_RECURRENT_TRANSFER_FAILURES` | 10 | `config.hpp:242` |

Testnet default for min-recurrence is also 24h, adjustable via
`set_min_recurrent_transfers_recurrence()` (`testnet_blockchain_configuration.hpp:51,200-202`).

## API surface

- **`database_api.find_recurrent_transfers`** — args `{ from }`, returns
  `vector<api_recurrent_transfer_object>` for transfers **sent** by `from`
  (`database_api_financial.cpp:736-754`; args `database_api_args.hpp:502-510`).
- **`condenser_api.find_recurrent_transfers`** — thin wrapper taking the account as
  `args[0]`, delegating to the database_api method (`condenser_api.cpp:1074-1078`).
- **`api_recurrent_transfer_object`** fields: `id, trigger_date, from, to, amount, memo,
  recurrence, consecutive_failures, remaining_executions, pair_id`
  (`database_api_objects.hpp:589-603`, reflected `:874`; constructor maps `from_id/to_id` →
  names and `get_trigger_date()` → `trigger_date`, `database_api_objects_constructors.cpp:444-455`).
- The `cli_wallet` exposes a `recurrent_transfer` helper (`libraries/wallet/wallet.cpp`,
  declared in `wallet.hpp`) — convenience only, no consensus role.

## Account history / impacted accounts

For the operation and both virtual ops, account-history impact records **both** `from` and
`to`, with `from` as the owner — so a recurrent transfer appears in both parties' histories
(`forward_impacted.cpp:281-287` op, `:578-584` fill, `:586-592` failed). The balance-tracking
visitor records the fund movement only for the **fill** vop (`to += amount`, `from -= amount`,
`:857-861`); `failed_*` is intentionally absent there because a failed attempt moves no funds.

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Operation struct | `libraries/protocol/include/hive/protocol/hive_operations.hpp` | 1013-1039 | field definitions, `get_pair_id` decls |
| Operation reflection | `…/hive_operations.hpp` | 1219 | FC_REFLECT |
| Extension type | `libraries/protocol/include/hive/protocol/types.hpp` | 151-161 | `recurrent_transfer_pair_id`, variant |
| `validate()` | `libraries/protocol/hive_operations.cpp` | 807-825 | protocol checks (incl. executions≥2 all-paths) |
| `get_pair_id` / visitor | `…/hive_operations.cpp` | 832-864 | extension parsing |
| State object | `…/detail/state/recurrent_transfer_object.hpp` | 11-78 | fields + trigger-date methods |
| `update_next_trigger_date` | `…/recurrent_transfer_object.hpp` | 26-29 | grid-anchored `+= recurrence` |
| `get_final_trigger_date` | `…/recurrent_transfer_object.hpp` | 36-39 | end-date computation |
| `set_recurrence_trigger_date` | `…/recurrent_transfer_object.hpp` | 42-48 | re-anchor on recurrence change |
| Indices | `…/recurrent_transfer_object_multiindex.hpp` | 9-36 | by_id / by_trigger_date / by_from_id / by_from_to_id |
| Account counter | `…/detail/state/account_object.hpp` | 248 | `open_recurrent_transfers` |
| Evaluator | `libraries/chain/hive_evaluator_transfer.cpp` | 906-957 | create/delete/update CRUD |
| Block processing | `libraries/chain/database_dhf.cpp` | 37-144 | due-transfer execution loop |
| Processing call site | `libraries/chain/database.cpp` | 2351 | invoked per block in `apply_block` |
| Virtual ops | `libraries/protocol/include/hive/protocol/hive_virtual_operations.hpp` | 627-666 | fill / failed |
| Op registration | `libraries/protocol/include/hive/protocol/operations.hpp` | 74,113-114 | regular #49, virtual +34/+35 |
| RC cost | `libraries/chain/rc/resource_count.cpp` | 517-527 | lifetime-scaled state + exec time |
| RC sizes | `libraries/chain/rc/resource_sizes.cpp` | 156-160, 225-226 | byte/time coefficients |
| dgpo mirror fields | `…/detail/state/global_property_object.hpp` | 166-169 | informational only |
| Impacted accounts | `libraries/protocol/forward_impacted.cpp` | 281-287, 578-592, 857-861 | account-history + balance impact |
| database_api impl | `…/database_api/database_api_financial.cpp` | 736-754 | `find_recurrent_transfers` |
| api object | `…/database_api/include/.../database_api_objects.hpp` | 589-603 | response struct |
| Constants | `libraries/protocol/include/hive/protocol/config.hpp` | 204-206, 241-242 | mainnet limits |
| Unit test (per-block + no-drift) | `tests/unit/tests/operation_tests.cpp` | 9876-9975 | cap + grid-anchoring proof |
| Unit tests (suite) | `tests/unit/tests/operation_tests.cpp` | 9562-10443 | validate/apply/hbd/max-open/pair_id/edit |
| Unit test (expiration) | `tests/unit/tests/operation_time_tests.cpp` | 3112 | lifecycle end |

## Cross-references to existing parts

- **Part 02 (operations-catalog)** — *complements*: lists `recurrent_transfer_operation` (#49)
  and the two vops; this zoom adds the full field semantics and the `pair_id` extension parsing.
- **Part 03 (operation-validation)** — *deepens / refines*: Part 03 (`:603-616`) states
  recurrence≥24, executions≥2, and that chain limits are enforced at the evaluator. This zoom
  adds (a) that executions≥2 applies even to deletes, (b) that the end-date check is the
  post-HF28 absolute form and the pre-HF28 duration form was removed, and (c) that the `pair_id`
  extension has no evaluator HF gate at this SHA. No contradiction — Part 03's line cites
  (`hive_evaluator_transfer.cpp:923-928, 954-955`) still hold.
- **Part 04 (chain-evaluators)** — *deepens*: Part 04 (`§2.11`, `:1205-1217`) summarizes the
  evaluator and `process_recurrent_transfers`. This zoom supplies the full state machine,
  grid-anchoring, failure accounting, and the iterator-safety detail.
- **Part 05 (state-objects)** — *deepens*: confirms `recurrent_transfer_object` lifecycle
  (`:1754`); adds index roles and the private-`trigger_date` accessor pattern.
- **Part 07 / Part 08 (economics / RC)** — *confirms*: Part 08 (`:139`) already gives
  `(200 + memo) × TEMPORARY × recurrence × executions`; this zoom verifies the exact code and
  the `amount > 0` gating and market-op flag.
- **Part 09 (hardfork-history)** — *deepens*: Part 09 (`:332-335,415`) attributes recurrent
  transfers to HF25. This zoom documents the HF28 `pair_id` era and its *removal* at this SHA,
  plus the (future, absent) HF29 single-execution relaxation — material not in Part 09.
- **Part 10 (api-layer)** — *deepens*: Part 10 (`:237,351`) lists `find_recurrent_transfers`;
  this zoom adds the by-sender-only limitation, the absent by-`to` index, and the `<=` off-by-one.

## Discrepancies and Potential Issues

1. **`pair_id` HF28 guard removed — relies on a historical invariant, not an assertion.**
   At this SHA nothing rejects a `recurrent_transfer` carrying a `pair_id` extension before
   HF28; the gate was deleted in `b155eb62e`. This is **replay-safe for canonical mainnet**
   (no pre-HF28 block can contain such an op, because the guard was active when those blocks
   were produced) and matches Hive's documented practice of dropping obsolete hardfork
   conditions after a successful replay experiment. It is *not* a live fork risk (post-HF28 all
   nodes accept the extension and agree). The caveat worth recording: a fresh replay of a
   **non-mainnet / alternative** history that *did* contain a pre-HF28 `pair_id` op would
   diverge from a pre-`b155eb62e` node. Flagged for awareness, not as a mainnet bug.

2. **`executions >= 2` blocks editing/cancelling the last installment.** Once
   `remaining_executions` reaches 1, the holder cannot change the amount/memo of that final
   payment without resetting `executions ≥ 2` (which extends the schedule), and cannot delete
   with `executions = 1`. The future HF29 (`8d435f016`, not present here) treats this as a bug
   (issue #786) and relaxes it. At this SHA it is a real, if minor, UX limitation; the
   `recurrence ≥ 24` and `executions ≥ 2` requirements also apply to delete operations, which is
   surprising for an `amount == 0` "cancel".

3. **No recipient-side state query.** `find_recurrent_transfers` and the indices only support
   lookup by sender. A recipient cannot enumerate incoming recurrent transfers from chain state
   (only reconstruct them from account-history `fill_*` vops). Combined with the inclusive
   `<=` limit guard (returns up to 1001 objects), the read API is a candidate for a future
   improvement (a `by_to` index / `find_recurrent_transfers_by_to`). Non-consensus.

4. **Affordability is checked for one installment, at submission only.** The evaluator verifies
   the sender can afford a single `amount` at create/update time (`:913-914`); there is no check
   that the sender can fund the whole schedule. Subsequent shortfalls are handled at execution
   time via the failure/`consecutive_failures` machinery. This is by design but easy to
   misread as a full-schedule guarantee.

## Open Questions

- **Multi-fire catch-up under extreme backlog.** Grid-anchoring (`trigger_date += recurrence`)
  means that if a transfer were ever delayed by *more than one full `recurrence` period*, its
  re-inserted `trigger_date` could still be `≤ now`, letting it fire multiple times in one block
  to catch up (bounded by the 1000/block cap). The per-block test only exercises a one-block
  (3-second) deferral, where no catch-up occurs because `recurrence ≥ 24h`. Whether sustained
  backlog beyond a full period is reachable in practice (it needs >1000 transfers due per block
  for ~28800 consecutive blocks) — and whether catch-up there is intended — would need a
  dedicated test/replay to confirm. Reasoned from code + `boost::multi_index` re-insertion
  semantics, not yet observed empirically.
- **`pair_id` value space vs. account cap.** `pair_id` is `uint8_t` (0-255), so up to 256
  transfers are addressable per `(from, to)` pair, but `HIVE_MAX_OPEN_RECURRENT_TRANSFERS` caps
  an account at 255 live transfers across *all* recipients. The interaction (e.g., can a single
  pair exhaust the account budget?) is consistent but untested here — a possible edge case for a
  future zoom on account limits.
- **HAF / Hivemind exposure.** How recurrent-transfer state and the `fill_*`/`failed_*` vops are
  surfaced by the HAF SQL layer and Hivemind is out of scope for this hive-core zoom and remains
  uncovered by the KB (Part 10 covers only hived APIs).

```results
PART: 12
AREA: recurrent-transfers
STATUS: COMPLETE
OUTPUT_FILES:
- research/hive-core/findings/12-recurrent-transfers.md
KEY_FINDINGS:
- Only HF25 is an active gate at 1.28.6: the HF28 pair_id guard and a pre-HF28 "faulty" end-date check were both removed as replay-safe cleanup (commit b155eb62e, an ancestor); HF29 single-execution relaxation is NOT present (verified non-ancestor).
- Scheduling is grid-anchored, not drifting — update_next_trigger_date() does `trigger_date += recurrence` from the prior value, so per-block-cap deferrals never shift the schedule (empirically asserted by operation_tests.cpp:9876-9975).
- validate() enforces executions>=2 (and recurrence>=24) on EVERY path including delete (amount==0); failed fires consume a remaining_execution and are never retried; consecutive_failures resets only on a funded fire, not on user update.
- RC state cost scales with lifetime = recurrence × executions (charged only when amount>0); the dgpo "limit" fields are informational mirrors never read by consensus.
- API enumerates by sender only (no by_to index) and the loop guard is an inclusive `<=` (returns up to 1001).
CROSS_REFS:
- Deepens Part 03 (validation), Part 04 (evaluators), Part 09 (hardforks), Part 10 (API); confirms Part 08 (RC) formula; complements Part 02 (ops) and Part 05 (state objects). No contradictions.
BLOCKERS:
- None
```
