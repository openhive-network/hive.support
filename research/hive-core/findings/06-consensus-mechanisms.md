# Findings: Consensus Mechanisms — Block Production, Witness Schedule, Fork Resolution

## Summary

Hive uses Delegated Proof of Stake (DPoS) with 21 active witnesses producing blocks every 3 seconds. The consensus layer is built on five interacting subsystems: (1) witness scheduling via a virtual-time fair queuing algorithm, (2) a 200ms polling production loop in the witness plugin, (3) a single dedicated writer thread in the chain plugin that serializes all state mutations through two FIFO queues (blocks have priority over transactions), (4) an in-memory fork database tracking competing chains with longest-chain selection, and (5) a 75%-of-witnesses irreversibility threshold with HF26 "fast confirm" acceleration.

All code verified directly from `libraries/chain/`, `libraries/plugins/chain/`, `libraries/plugins/witness/`, `libraries/plugins/queen/`, and `libraries/plugins/p2p/` in the hive-core repository at the pinned commit (release 1.28.6).

---

## Chain Plugin Thread Model and Write Queues

All blockchain state mutations — P2P blocks, transactions, and block-generation requests — are processed by a **single dedicated writer thread** named `write_queue` (`chain_plugin.cpp:439-737`, thread name set at :466-467). Other threads (P2P, API/webserver, witness timer) never mutate chain state directly; they enqueue requests and (usually) wait on a promise.

### Two queues, strict priority

Two plain FIFO queues guarded by one mutex (`chain_plugin.cpp:180-205`):

| Queue | What goes in | Enqueued by |
|-------|-------------|-------------|
| `priority_write_queue` | P2P/sync blocks, block-generation requests | `accept_block()` :2017, `push_generate_block_request()` :2139, `queue_generate_block_request()` :2155 |
| `write_queue` | Transactions (API and P2P, including fast confirms) | `accept_transaction()` :2046/:2058, `queue_transaction()` :2077/:2083 |

The worker always drains the priority queue first (`chain_plugin.cpp:562-571`, and again inside the batch loop at :664-673). **Blocks therefore always jump ahead of any backlog of pending transactions**, but there is no further prioritization inside either queue.

### Entry points and blocking behavior

| Entry point | Queue | Blocks caller? | Caller |
|-------------|-------|----------------|--------|
| `chain_plugin::accept_block(p2p_block_ctrl, syncing)` | priority | yes — until TXS_EXECUTED / FORK_IGNORE / failure; returns `block_ctrl->forked()` (:2025) | p2p_plugin `handle_block` (`p2p_plugin.cpp:128-162`) |
| `chain_plugin::accept_transaction(full_tx, lock_type)` | normal | yes — until tx applied/failed | p2p_plugin `handle_transaction` (`p2p_plugin.cpp:209-217`, uses `lock_type::fc`), API broadcast |
| `chain_plugin::queue_transaction(trx_ctrl)` | normal | no | fire-and-forget broadcasters |
| `chain_plugin::push_generate_block_request(ctrl)` | priority | yes — until APPLIED phase (`block_flow_control.cpp:225-232`) | witness plugin `maybe_produce_block` (`witness_plugin.cpp:518`) |
| `chain_plugin::queue_generate_block_request(ctrl)` | priority | no (:2148-2158) | queen plugin (called from *within* the writer thread — blocking would deadlock) |
| `determine_encoding_and_accept_transaction` | normal | yes | API JSON path: tries HF26 serialization first, retries with legacy pack on `transaction_auth_exception` (:2087-2113) |

### Sync mode vs live mode

The worker starts in **sync mode** (if P2P is enabled) and drains the queues as fast as possible while holding the write lock. It switches to **live mode** when the head block time comes within 1 minute of system time (`get_time_gap_to_live_sync`, `chain_plugin.cpp:425-430`; `force_live_sync` config skips the wait). On the transition it calls `db.notify_end_of_syncing()` and `default_block_writer->set_is_at_live_sync()` (:681-688).

In live mode the worker voluntarily releases the write lock after `write_lock_hold_time` to let reader (API) threads in (`chain_plugin.cpp:622-651`):

- Default: `HIVE_BLOCK_INTERVAL * 1000 / 6` = **500ms** (`chain_plugin.cpp:209`)
- Witness nodes with configured witnesses+keys raise it to 1/3 of block interval = **1000ms** (`witness_plugin.cpp:646-648` via `set_write_lock_hold_time`)

Note: the loop's design comment (:495-506) mentions a 10ms sleep after yielding the lock; no such sleep exists in the loop body — the thread immediately re-waits on the condition variable. (Stale comment, behavior is harmless.)

If P2P is disabled but work is enabled (e.g. queen mode, or `--stop-at-block` reached with p2p on), the worker runs in "API mode" (:477-485, :599-619). With no new data for 30 seconds (10×block interval) it logs a "No P2P data received" warning (:470-524). The writer also reports a utilization breakdown (waiting for work / locks / processing blocks / transactions) every 30 seconds (:691-715).

### Where blocks are actually processed

A `write_request_visitor` (`chain_plugin.cpp:289-413`) dispatches each dequeued item:

- **P2P block** → `cp.push_block(*p2p_block_ctrl, skip_flags)` (:328)
- **Transaction** → `cp.push_transaction(full_tx, skip_nothing)` (:354); separate catch branches count auth failures and RC failures for block stats (:360-369)
- **Generate request** → `cp.block_generator->generate_block(ctrl)` (:396) — the block generator is the witness plugin's registered `block_producer` (`witness_plugin.cpp:615`); only one plugin may register a generator

The visitor accumulates incoming-transaction counters between blocks and passes them to `on_write_queue_pop` when the next block is popped (:305-312), which is how per-block stats know how many transactions arrived "before" the block.

---

## Block Flow Control

`block_flow_control` (`block_flow_control.hpp:116-204`) wraps a block being processed, tracks its progress through phases, collects timing statistics, and releases the caller's promise at the right moment. Subclasses cover each block source.

### Phases

```
REQUEST      request created (default)
START        picked from worker queue          on_write_queue_pop()
FORK_DB      inserted into fork database       on_fork_db_insert()
FORK_APPLY   fork switch required              on_fork_apply()   (was_fork = true)
FORK_IGNORE  block on shorter fork — ignored   on_fork_ignore()  (was_ignored = true)
FORK_NORMAL  extends active fork               on_fork_normal()
TXS_EXECUTED all block transactions applied    on_end_of_transactions()
APPLIED      block fully applied               on_end_of_apply_block()
END          pending reapplied, all done       on_end_of_processing()
```

(`block_flow_control.hpp:135-146`, transitions in `block_flow_control.cpp:46-89`. END is only entered if no exception occurred and phase reached APPLIED, :87-88.)

### Subclasses and their differences

| Class | Buffer tag | Promise released at | Notes |
|-------|-----------|--------------------|-------|
| `generate_block_flow_control` | `gen` | APPLIED (`on_end_of_apply_block`, `block_flow_control.cpp:225-232`) or failure | Releasing earlier would let the witness loop see stale state and try to produce the same block again (comment :229-232). Work-time stats end at FORK_DB insert (:218-223). |
| `witness_generate_block_flow_control` (witness plugin subclass) | `gen` | same | Overrides `on_fork_db_insert()` to **broadcast the block via P2P as soon as it enters the fork DB**, before it is applied (`witness_plugin.cpp:113-131`) |
| `queen_generate_block_flow_control` (queen plugin subclass) | `queen` | n/a (nobody waits) | `skip_transaction_reapplication() == true`; recalculates stats against block timestamp (`queen_plugin.cpp:72-96`) |
| `p2p_block_flow_control` | `p2p` | TXS_EXECUTED (`block_flow_control.cpp:256-261`), FORK_IGNORE (:249-254), or failure | **The P2P thread resumes before post-block processing and pending reapplication** — those run on the writer thread while P2P fetches the next block. Work-time stats end at the same points. |
| `sync_block_flow_control` | `sync` | same as p2p | Suppresses the per-block stats report unless the block is within `HIVE_UP_TO_DATE_MARGIN__BLOCK_STATS` = 20s of now (`block_flow_control.cpp:274-284`, `config.hpp:435`) — avoids log spam slowing down sync |
| `existing_block_flow_control` | `old` | n/a | For already-known blocks: used when a **fast confirm triggers a fork switch** (`chain_plugin.cpp:966`) and in tests |

In block-stats reports the buffer tag is replaced by `broken` (exception), `forked`, or `ignored` when applicable (`block_flow_control.cpp:135-143`). Reports include offset from block timestamp, wait/work/cleanup times, and before/after transaction counts (:130-207); report type/output configured via `block-stats-report-type/-output` (`chain_plugin.cpp:1816`).

---

## Block Production Flow

### Overview: From "Witness's Turn" to "Block in Chain"

1. **Witness plugin polls** every 200ms (`schedule_production_loop()` in `witness_plugin.cpp:369-380`)
2. **Slot check**: converts current time to slot number, looks up scheduled witness for that slot
3. **If it's our turn**: verify private key available, check network participation rate
4. **Enqueue generation request** to the priority write queue and wait
5. **Writer thread generates block**: re-applies pending transactions, creates signed block
6. **Push through fork DB**: same `push_block` pipeline as P2P blocks
7. **Broadcast**: P2P broadcast fires at fork-DB insert (before apply finishes)
8. **Apply block**: full `_apply_block()` pipeline; witness thread resumes at APPLIED
9. **Fast confirm** (HF26+): on `notify_finish_push_block`, locally-represented scheduled witnesses broadcast approval transactions

### Witness Plugin Production Loop

The witness plugin uses a **timer-based polling loop** with a 200ms cycle:

```
BLOCK_PRODUCTION_LOOP_SLEEP_TIME = 200,000 microseconds (200ms)
BLOCK_PRODUCING_LAG_TIME = 750ms (max acceptable production delay)
```

**`schedule_production_loop()`** (`witness_plugin.cpp:369-380`):
- Sets async timer aligned to the next 200ms boundary (minimum 50ms sleep)
- On expiry, calls `block_production_loop()`

**`block_production_loop()`** (`witness_plugin.cpp:382-467`):
- Checks if past genesis time
- Calls `maybe_produce_block()`, logs the outcome per `block_production_condition`
- On `unknown_hardfork_exception` (node out of date) or cancellation: stops production and interrupts the app (:407-414)
- Reschedules itself unless writer thread finished (:462-465)

**Production decision data** is precomputed and cached in a mutex-guarded `produce_block_data` struct, refreshed by `update_produce_block_data()` (`witness_plugin.cpp:310-367`) after every pushed block (`on_finish_push_block` :307) and when keys/witnesses change. The decision logic:

1. If production not enabled: enable it once `get_slot_time(1) >= now` (i.e. chain caught up), else `not_synced` (:325-331)
2. Get scheduled witness for the slot: `scheduled_witness = _db.get_scheduled_witness(slot)`
3. Check it is one of our configured witnesses — **skipped entirely in queen mode** (`if( not _queen_mode && _witnesses.find(...) == end ) return not_my_turn;` :333-336)
4. Look up the witness's on-chain `signing_key` and find the matching private key (`no_private_key` if absent)
5. Check participation: `witness_participation_rate() >= _required_witness_participation` (`low_participation` if not; default 33%, `witness_plugin.cpp:33`)

The full condition enum: `produced, not_synced, not_my_turn, not_time_yet, no_private_key, low_participation, lag, exception_producing_block, wait_for_genesis`.

**`maybe_produce_block()`** (`witness_plugin.cpp:469-526`):
- Time check adds a 500ms buffer: `now = fc::time_point::now() + 500ms` (:477)
- If the cached slot time is still in the future → `not_time_yet`
- **Lag handling** (:488-507): if `now` is more than 750ms past the cached slot time, recompute production data for the *next future slot* (rounded up by whole block intervals) under a 200ms-bounded read lock; if it was actually our turn, report `lag` and skip producing for that slot
- If it's our turn: create a `witness_generate_block_flow_control` and call `_chain_plugin.push_generate_block_request()` — **synchronous**; the witness thread waits until the block is applied so that the next loop iteration sees the new head (comment :522-525)

### Block Assembly

Generation happens on the writer thread in `block_producer::generate_block` → `_generate_block()` (`block_producer.cpp:18-85`):

1. Re-verify slot and witness: `get_scheduled_witness(slot) == witness_owner` (:36-39)
2. Verify signing key matches witness object (unless `skip_witness_signature`) (:43-44)
3. Build header: `previous = head_block_id()`, timestamp = slot time, witness (:46-50)
4. **`adjust_hardfork_version_vote()`** (:52, :87-108): adds block header extensions — reported `version` if running version differs from witness record, and a `hardfork_version_vote` correcting the witness's on-chain vote to match the binary's next-known hardfork (or to *reject* an unknown future hardfork)
5. Select transactions — normal path `apply_pending_transactions()`, queen path `fill_block_with_transactions()` (:55-58)
6. Create `full_block_type` from header + transactions + signer; size assert `<= HIVE_MAX_BLOCK_SIZE` unless `skip_block_size_check` (:67-72)
7. `generate_block_ctrl->store_produced_block(full_block)` then **`_chain.push_block(*generate_block_ctrl, skip)`** (:73-77) — the produced block goes through the same fork-DB/apply pipeline as a P2P block; a failure here logs `NOTIFYALERT!` (:81-82)

**Transaction selection** (`apply_pending_transactions`, `block_producer.cpp:111-216`):
- Rebuilds the pending session as **two nested undo sessions** (`_pending_tx_session.emplace(start_undo_session(), start_undo_session())` :135-137) — outer for the whole attempt, inner squashed per accepted transaction
- Sets `dgp.current_witness = witness_owner` *before* applying transactions so evaluators know the producer, and squashes that change so a failing first transaction can't undo it (:139-145)
- Tx status: `TX_STATUS_GEN_BLOCK` (:149)
- Duplicate check uses the in-memory `_pending_tx_index` (cleared and rebuilt) with `skip_transaction_dupe_check` set, instead of the consensus `transaction_index` (:151-155, :186-194)
- Per transaction, in pending order: skip if `runtime_expiration < when` (counted failed); skip if it would exceed `maximum_block_size` (counted unused); apply in the inner session — on success squash and include, on exception undo and leave for post-block reapplication (:162-207)
- Stops early after `HIVE_BLOCK_GENERATION_POSTPONED_TX_LIMIT` = 5 oversize skips (`config.hpp:422`, :164-165)
- Block size accounting: `total_block_size = pack_size(header) + 4` then add each tx size (:116-120)

**Queen fast path** (`fill_block_with_transactions`, `block_producer.cpp:218-253`): no reapplication, no undo sessions — pending transactions are appended in order until the size limit, relying on queen-mode invariants (transactions were validated on arrival, no forks, no authority changes in between; comment :223-228).

### Block Signing

- Block is signed via `fc::ecc::private_key` passed as `signer` to `full_block_type::create_from_block_header_and_transactions()`
- The signing key must match `witness_object.signing_key` on the witness's chain record
- Signing is skipped if `skip_witness_signature` flag is set (testing only)

### Post-Generation

1. **Fork DB insert** → `witness_generate_block_flow_control::on_fork_db_insert()` broadcasts via `p2p.broadcast_block(full_block)` (`witness_plugin.cpp:123-127`) — broadcast happens *before* the block is applied to state
2. **Apply** through `_apply_block()`; witness thread's promise releases at APPLIED
3. **Fast confirms** for other locally-represented witnesses are generated from the `notify_finish_push_block` handler (see Irreversibility)

---

## Queen Plugin (`queen_mode`)

The queen plugin (`libraries/plugins/queen/queen_plugin.cpp`) is a **testnet-only benchmark/CI driver** that produces blocks as fast as transactions arrive instead of on the 3-second schedule. It cannot run on mainnet: `plugin_initialize` hard-fails unless built with `USE_ALTERNATE_CHAIN_ID` because "it has to turn off p2p" (:273-275).

Setup (`plugin_initialize`, :268-297):
- `_chain.disable_p2p(false)` — disables P2P but keeps the writer loop working ("API mode"; `chain_plugin.cpp:432-437` — the `false` keeps `is_work_enabled = true`)
- `_witness.enable_queen_mode()` (`witness_plugin.cpp:570-577`) — sets `_production_enabled = true` and `_queen_mode = true`

**What `_queen_mode` does in the witness plugin**: the flag makes the plugin **represent every scheduled witness** rather than only those in its config — the witness-identity check in `update_produce_block_data` is bypassed (`witness_plugin.cpp:335`), and the fast-confirm loop treats all scheduled witnesses as local (:241). The private key for each witness's signing key must still be present in `_private_keys` (practical on testnets where all witnesses use init keys). The normal 200ms production loop is *not* started (P2P disabled → `plugin_startup` returns early, `witness_plugin.cpp:655-660`).

Production trigger (`on_post_apply_transaction`, `queen_plugin.cpp:98-127`): after each new/reapplied pending transaction, queen decrements its remaining block-size/tx-count budget (`queen-block-size`, `queen-tx-count` options; 0 = max/unlimited). When the budget would be exceeded, it creates a `queen_generate_block_flow_control` with skip flags `skip_validate | skip_validate_invariants | skip_undo_block` and calls **`queue_generate_block_request`** (non-blocking — queen runs inside the writer thread via the signal, so the request lands in the priority queue and is processed right after the current transaction batch).

Per-block bookkeeping (`prepare_for_new_block`, :162-223): resets budgets from `dgpo.maximum_block_size - 256`, then scans up to 21 future slots for one it can sign — `no_private_key` slots are skipped by advancing production data one block interval (`_witness.update_production_data(next_slot_time + HIVE_BLOCK_INTERVAL)`), `low_participation` or no signable slot kills the app. `on_fail_apply_block` also kills the app — queen-produced blocks must never fail (:152-160). On shutdown it prints production statistics (:225-248).

---

## Witness Scheduling

### Schedule Structure

- **HIVE_MAX_WITNESSES** = 21 active witnesses per round
- Schedule stored in `witness_schedule_object` with a fixed 21-element array `current_shuffled_witnesses`
- Two schedule objects after HF26: current (ID 0) and future (ID 1)

### Witness Categories

| Category | Pre-HF17 | Post-HF17 | Selection Method |
|----------|----------|-----------|------------------|
| **Elected** (top voted) | 19 | 20 | Highest votes from `by_vote_name` index |
| **Miner** (PoW) | 1 | 0 | Top of `by_pow` index |
| **Timeshare** (runner-up) | 1 | 1 | Virtual time fair queuing from `by_schedule_time` index |
| **Total** | **21** | **21** | |

Constants from `config.hpp`:
```
HIVE_MAX_VOTED_WITNESSES_HF0  = 19     HIVE_MAX_VOTED_WITNESSES_HF17  = 20
HIVE_MAX_MINER_WITNESSES_HF0  = 1      HIVE_MAX_MINER_WITNESSES_HF17  = 0
HIVE_MAX_RUNNER_WITNESSES_HF0 = 1      HIVE_MAX_RUNNER_WITNESSES_HF17 = 1
```

### Schedule Recalculation

**Trigger**: Every `HIVE_MAX_WITNESSES` (21) blocks — approximately every 63 seconds.

```cpp
// witness_schedule.cpp:405
if( (db.head_block_num() % HIVE_MAX_WITNESSES) == 0 )
```

**Algorithm** (`update_witness_schedule4()` in `witness_schedule.cpp:152-396`):

1. **Select elected witnesses** (lines 157-171):
   - Iterate `by_vote_name` index (descending by votes, ascending by name)
   - Skip disabled witnesses (empty signing key) after HF14
   - Take top `max_voted_witnesses`

2. **Select miner witnesses** (lines 176-206):
   - Iterate `by_pow` index
   - Skip if already elected or disabled
   - Remove from PoW queue after processing
   - Take `max_miner_witnesses`

3. **Select timeshare witnesses** (lines 209-231):
   - Iterate `by_schedule_time` index (virtual time ordering)
   - Skip if already elected, miner, or disabled
   - Fill remaining slots to reach 21

4. **Update virtual times** (lines 235-256):
   - Advance all processed witnesses' virtual_last_update to new_virtual_time
   - Recalculate virtual_scheduled_time: `new_virtual_time + LAP_LENGTH / (votes + 1)`
   - If overflow detected: reset all virtual times to 0

5. **Majority version / hardfork vote processing** (lines ~260-350): determine majority `running_version` and next hardfork votes; if a hardfork majority is lost, `hpo.next_hardfork` is reset to current (:342-348)

6. **Shuffle** (lines 372-388) — see Shuffle Algorithm below; also sets `next_shuffle_block_num = head_block_num + num_scheduled_witnesses` (:391) and `witness_pay_normalization_factor` (:367-370)

7. **Calculate median witness properties** (`update_median_witness_props`, lines 58-150, called at :395):
   - Sort all scheduled witnesses' proposed values
   - Take median for: `account_creation_fee`, `maximum_block_size`, `hbd_interest_rate`, `account_subsidy_budget`, `account_subsidy_decay`

### Future Witness Schedule (HF26+)

`update_witness_schedule()` (`witness_schedule.cpp:403-440`) — after `HIVE_HARDFORK_1_26_FUTURE_WITNESS_SCHEDULE`, two schedules are maintained:

```cpp
// witness_schedule.cpp:420-431
const witness_schedule_object& future_wso = db.get_future_witness_schedule_object();
db.modify(wso, [&](witness_schedule_object& ws) { ws.copy_values_from(future_wso); }); // promote
update_witness_schedule4(db, future_wso); // compute next round into future schedule
```

This pre-computes the next round's schedule one round in advance. Additional steps on the same cadence: after HF28, promoted global witness properties are copied to the dgpo (`update_global_witness_properties`, :428-429); after HF20, RC pool parameters are refreshed from the schedule (`db.rc().set_pool_params(wso)`, :437-438).

### Virtual Time Fair Queuing (Timeshare Selection)

The timeshare/runner-up witness slot uses a virtual time scheduling algorithm to give all non-top-20 witnesses proportional block production based on their vote weight:

**Key fields on `witness_object`:**
- `virtual_last_update` — when witness last advanced in virtual time
- `virtual_position` — position in current virtual lap
- `virtual_scheduled_time` — when witness should complete lap (lower = sooner)
- `votes` — total governance votes (sum of all voters' vesting shares)

**Formula:**
```
virtual_scheduled_time = virtual_last_update + (LAP_LENGTH - virtual_position) / (votes + 1)
```

Witnesses with more votes complete the virtual lap faster, getting scheduled sooner. The `HIVE_VIRTUAL_SCHEDULE_LAP_LENGTH2` constant is a `uint128` value ensuring fair distribution.

**When votes change** (`database_witness.cpp:69-94`):
```cpp
delta_pos = votes * (current_virtual_time - virtual_last_update);
virtual_position += delta_pos;
virtual_last_update = current_virtual_time;
votes += delta;
virtual_scheduled_time = virtual_last_update + (LAP_LENGTH - virtual_position) / (votes + 1);
```

### Shuffle Algorithm

After witnesses are selected, their order is randomized using a **XORshift PRNG** seeded with the head block timestamp:

```cpp
// witness_schedule.cpp:372-388
auto now_hi = uint64_t(db.head_block_time().sec_since_epoch()) << 32;
for( uint32_t i = 0; i < num_scheduled_witnesses; ++i )
{
    uint64_t k = now_hi + uint64_t(i)*2685821657736338717ULL;
    k ^= (k >> 12);
    k ^= (k << 25);
    k ^= (k >> 27);
    k *= 2685821657736338717ULL;

    uint32_t jmax = num_scheduled_witnesses - i;
    uint32_t j = i + k%jmax;
    std::swap(current_shuffled_witnesses[i], current_shuffled_witnesses[j]);
}
```

This is a **Fisher-Yates shuffle** with deterministic XORshift random. The seed changes every 21 blocks (new schedule), making the order predictable (necessary for consensus) but non-trivially manipulable.

### Slot System

**Slot-to-witness mapping** (`database.cpp:904-910`):
```cpp
account_name_type database::get_scheduled_witness( uint32_t slot_num ) const
{
    uint64_t current_aslot = dpo.current_aslot + slot_num;
    return wso.current_shuffled_witnesses[ current_aslot % wso.num_scheduled_witnesses ];
}
```

- `current_aslot` = absolute slot number since genesis (includes missed slots)
- Maps to witness: `shuffled_witnesses[aslot % 21]`
- Each slot = 3 seconds (`HIVE_BLOCK_INTERVAL`)

**Time-to-slot conversion** (`database.cpp:937-943`):
```cpp
uint32_t database::get_slot_at_time(fc::time_point_sec when) const
{
    fc::time_point_sec first_slot_time = get_slot_time( 1 );
    if( when < first_slot_time ) return 0;
    return (when - first_slot_time).to_seconds() / HIVE_BLOCK_INTERVAL + 1;
}
```

`get_slot_time(slot_num)` (`database.cpp:912-935`): slot 0 maps to the head block's slot-aligned time; before any block exists, slot times count from genesis time + one interval.

### Missed Blocks

When a block arrives with a timestamp more than one slot past the head block, the intervening slots were missed. `update_global_dynamic_data()` computes `missed_blocks = get_slot_at_time(b.timestamp) - 1` (`database.cpp:2793-2796`) and calls `update_witness_missed_blocks()` (`database_witness.cpp:284-306`):

1. For each missed slot, the witness scheduled at that slot (if different from the current producer) gets:
   - `total_missed++` counter increment
   - `producer_missed_operation` virtual operation emitted
   - Between HF14 (`HIVE_HARDFORK_0_14__278`) and HF20 (`HIVE_HARDFORK_0_20__SP190`): if `head_block_num - last_confirmed_block_num > HIVE_WITNESS_SHUTDOWN_THRESHOLD` (= `HIVE_BLOCKS_PER_DAY` = 28,800 blocks on mainnet), witness is **disabled** by clearing signing key, and `shutdown_witness_operation` is emitted (this auto-shutdown no longer applies after HF20)

2. Participation tracking updates via `update_global_dynamic_data()` — see Participation Tracking below

### Witness Voting

- **Type**: Approval voting — each account votes for up to 30 witnesses
- **Weight**: Voter's governance vote power (derived from vesting shares/VESTS)
- **Storage**: `witness_vote_object` pairs (account, witness)
- **Invariant**: `FC_ASSERT(w.votes <= total_vesting_shares.amount)` (`database_witness.cpp:271-282`) — votes can never exceed total vesting

---

## Block Application Sequence

### Entry Points and Skip Flags by Source

| Source | Path | Notable skip flags |
|--------|------|--------------------|
| P2P block (live) | `accept_block` → writer → `chain_plugin::push_block` → fork DB → `apply_block_extended` | `skip_transaction_signatures` unless the node is a block producer or `p2p-force-validate` (`p2p_plugin.cpp:156`) |
| P2P block (sync) | same, with `sync_block_flow_control` | same as live (sync mode affects stats/lock behavior, not validation flags) |
| Block before last checkpoint | same | large set: witness/tx signatures, dupe, size, TaPoS, authority, undo-history, schedule, validate, invariants + `skip_undo_block` (`chain_plugin.cpp:1046-1062`); merkle and fork DB explicitly NOT skipped (comments :1051, :1055) |
| Self-produced | `push_generate_block_request` → writer → `block_producer` → `chain_plugin::push_block` | `skip_block_size_check` is NOT in the set; production uses node flags + `skip_undo_history_check` when stale production enabled (`witness_plugin.cpp:671`) |
| Replay | `reindex_internal` → `db.apply_block()` directly — **no fork DB, no flow control**, `irreversible_block_writer` (store_block is a no-op, `irreversible_block_writer.cpp:19-21`) | `skip_validate_invariants | skip_block_log | skip_undo_block` ("needed to keep head block == LIB") + unless `--validate-during-replay`: witness/tx signatures, dupe, TaPoS, merkle, schedule, authority, validate (`chain_plugin.cpp:1222-1240`) |

### `push_block` vs `apply_block` — the precise difference

- **`chain_plugin::push_block(block_ctrl, skip)`** (`chain_plugin.cpp:1039-1097`) is the full pipeline for a **new** block: checkpoint skip-flag handling, `without_pending_transactions` (clear pending, restore+reapply after), `_push_block` → `sync_block_writer::push_block` (fork DB insertion, fork resolution, possibly applying several blocks), `notify_finish_push_block`, `on_end_of_apply_block`, free-memory check. It may conclude the block is on a shorter fork and not apply it at all.
- **`database::apply_block_extended(full_block, skip, block_ctrl)`** (`database.cpp:2123-2142`) is the state transition for one block assumed to extend the current state head: sets `TX_STATUS_P2P_BLOCK`, wraps `apply_block()` in an undo session unless `skip_undo_block`.
- **`database::apply_block()`** applies skip flags via `detail::with_skip_flags()` then delegates to `_apply_block()` (consensus-critical body).
- There is no `database::push_block` — fork choice lives in `sync_block_writer`/`fork_database`, state transition in `database`.

### `_apply_block()` — The Consensus-Critical Method (`database.cpp:2183-2369`)

This is the heart of consensus. The exact execution order:

#### Phase 1: Pre-Block Setup (lines 2189-2202)
```
1. notify_pre_apply_block()
2. rc().reset_block_info()
3. Store _currently_processing_block_id
4. Set _current_block_num, _current_timestamp, _current_trx_in_block = 0
```

#### Phase 2: Genesis Hardfork Processing (lines 2204-2235)
Only on block 1:
- `process_genesis_accounts()`
- Apply all hardforks whose activation time ≤ genesis block timestamp
- Update witness hardfork version votes

#### Phase 3: Merkle Root Validation (lines 2237-2262)
- Compute merkle root from block's transactions
- Assert matches `block.transaction_merkle_root`
- Exception: known bad merkle roots in `shared_db_merkle` map are tolerated (historical chain data)

#### Phase 4: Block Header Validation — `validate_block_header()` (lines 2757-2779)
Five critical assertions in order:
1. **Chain continuity**: `head_block_id() == next_block_header.previous`
2. **Timestamp monotonicity**: `head_block_time() < next_block_header.timestamp`
3. **Witness signature**: `witness.signing_key == full_block->get_signing_key()` (unless `skip_witness_signature`)
4. **Valid slot**: `slot_num > 0` (block timestamp maps to a valid slot)
5. **Correct witness**: `witness.owner == get_scheduled_witness(slot_num)` (unless `skip_witness_schedule_check`)

#### Phase 5: Block Size Validation (lines 2267-2272)
- After HF12: `block_size <= gprops.maximum_block_size`
- If block_size < `HIVE_MIN_BLOCK_SIZE`: log warning (not an error)

#### Phase 6: Witness Hardfork Version Check (lines 2283-2290)
- After HF5.54: witness must be running `>= current_hardfork_version`

#### Phase 7: Transaction Application (lines 2292-2302)
```cpp
for( const auto& trx : full_block->get_full_transactions() )
{
    apply_transaction( trx, skip );
    ++_current_trx_in_block;
}
```

No per-transaction undo sessions — entire block is atomic. If any transaction fails, the entire block fails.

#### Phase 8: End of Transactions Notification (lines 2304-2312)
- `block_ctrl->on_end_of_transactions()` — flow control callback; **for P2P blocks this releases the P2P thread's promise** (see Block Flow Control)

#### Phase 9: Global State Updates (lines 2314-2331)
```
1. update_global_dynamic_data(block)    — head block, participation, aslot, missed blocks
2. update_signing_witness(witness, block) — witness last_aslot / last_confirmed_block_num
3. LIB update:
     if skip_undo_block: set_last_irreversible_block_num(head)  — replay/pre-checkpoint mode
     else: update_last_irreversible_block(no fork-switch callback)
4. create_block_summary(full_block)     — TaPoS reference data (ring buffer of 65536 entries)
5. clear_expired_transactions()
6. clear_expired_orders()
7. clear_expired_delegations()
8. update_witness_schedule()            — every 21 blocks
9. update_median_feed()
10. update_virtual_supply()
```

#### Phase 10: Blockchain Processing (lines 2333-2354)
**Order is consensus-critical:**
```
1.  clear_null_account_balance()
2.  consolidate_treasury_balance()
3.  process_funds()                    — inflation distribution
4.  process_conversions()              — HBD↔HIVE conversions
5.  process_comment_cashout()          — author/curation rewards
6.  process_vesting_withdrawals()      — power-down payments
7.  process_savings_withdraws()
8.  process_subsidized_accounts()
9.  pay_liquidity_reward()
10. update_virtual_supply()
11. account_recovery_processing()
12. expire_escrow_ratification()
13. process_decline_voting_rights()
14. process_proposals()                — DHF proposal payments
15. process_delayed_voting()
16. remove_expired_governance_votes()
17. process_recurrent_transfers()
18. rc().handle_expired_delegations()
19. rc().finalize_block()
20. process_hardforks()                — check if hardfork should activate
```

#### Phase 11: Finalization (lines 2358-2369)
```
1. notify_post_apply_block()
2. migrate_irreversible_state()        — move newly irreversible blocks to block log
3. Update _last_pushed_block_number and _last_pushed_block_time atomics
```

After `_apply_block` returns, the surrounding `chain_plugin::push_block` runs `notify_finish_push_block` (where the witness plugin emits fast confirms and refreshes production data) and `on_end_of_apply_block`, then pending transactions are reapplied (see below), and `db.check_free_memory()` may auto-grow the shared memory file (`chain_plugin.cpp:1073-1089`, `database.cpp:2144-2181`).

### Transaction Application Chain

**`apply_transaction()`** -> sets skip flags -> **`_apply_transaction()`** (`database.cpp:2644-2702`):

1. **Status check**: verify TX_STATUS is set
2. **Duplicate check**: `is_known_transaction(trx_id)` (unless `skip_transaction_dupe_check`)
3. **Validate**: calls `validate_transaction()` which checks:
   - Expiration time (HF28: separate max-sig-expiration vs max-execution-expiration)
   - TaPoS: `trx.ref_block_prefix == tapos_block_summary.block_id._hash[1]`
   - Operation structure validation: `full_transaction->validate()`
   - Authority/signature verification via `hive::protocol::verify_authority()`
4. **Create transaction_object**: record in transaction index for duplicate detection
5. **Notify**: `notify_pre_apply_transaction()`
6. **Apply operations**:
   ```cpp
   for (const auto& op : trx.operations)
   {
       _my->apply_operation(op);  // evaluator registry dispatch
       ++_current_op_in_trx;
   }
   ```
7. **Finalize**: `rc().finalize_transaction()`, `notify_post_apply_transaction()`

New transactions enter the pending pool via `process_non_fast_confirm_transaction()` (`database.cpp:552-576`): asserts the tx is NOT a fast confirm, enforces `tx_size <= maximum_block_size - 256` (size limit is tied to the witness-voted block size, not `HIVE_MAX_TRANSACTION_SIZE` — comments :561-563), sets `TX_STATUS_UNVERIFIED`, and `_push_transaction` adds it to `_pending_tx` inside nested undo sessions.

### Operation Application

**`database_impl::apply_operation()`** (`database.cpp:2722-2746`):
1. Create operation notification
2. `notify_pre_apply_operation()`
3. If HF20+: `rc().handle_operation_discount(op)` — RC discounts
4. **`_evaluator_registry.get_evaluator(op).apply(op)`** — dispatch to specific evaluator
5. `notify_post_apply_operation()`

### Skip Flags

Defined in `database.hpp:201-216`:

| Flag | Bit | Purpose |
|------|-----|---------|
| `skip_nothing` | 0 | Full validation |
| `skip_witness_signature` | 1<<0 | Reindexing |
| `skip_transaction_signatures` | 1<<1 | Non-witness nodes (P2P blocks) |
| `skip_transaction_dupe_check` | 1<<2 | Reindexing; also pending-pool path (separate in-memory index) |
| `skip_fork_db` | 1<<3 | Reindexing |
| `skip_block_size_check` | 1<<4 | Locally generated transactions |
| `skip_tapos_check` | 1<<5 | Reindexing; fast confirms |
| `skip_authority_check` | 1<<6 | Reindexing |
| `skip_merkle_check` | 1<<7 | Reindexing (NOT skipped pre-checkpoint) |
| `skip_undo_history_check` | 1<<8 | Reindexing, stale production, pre-checkpoint |
| `skip_witness_schedule_check` | 1<<9 | Reindexing |
| `skip_validate` | 1<<10 | Pre-checkpoint, pending reapplication |
| `skip_validate_invariants` | 1<<11 | Replay |
| `skip_undo_block` | 1<<12 | Replay, pre-checkpoint, queen ("keeps head block == LIB"; also short-circuits LIB calculation to LIB=head, `database.cpp:2318-2319`) |
| `skip_block_log` | 1<<13 | Replay (switches LIB computation to the legacy algorithm, `database.cpp:2995-3005`) |

### Pending Transaction Reapplication

After a block is applied, previously pending transactions are re-tested. `without_pending_transactions` / `pending_transactions_restorer` (`db_with.hpp:58-243`) clears the pending pool before block work and restores it afterwards (in the destructor):

- **Order**: popped transactions (`_popped_tx`, recovered from fork switches) are reapplied first, then prior pending transactions (:199-210)
- **In-sync gate**: reapplication only *executes* transactions when the block being processed is within `HIVE_UP_TO_DATE_MARGIN__PENDING_TXS` = 20s of now (`config.hpp:436`, :92-96); otherwise everything is just postponed (kept without execution)
- **Time budget**: execution stops after `HIVE_PENDING_TRANSACTION_EXECUTION_LIMIT` = 200ms (`config.hpp:423`, :108-110); remaining transactions are **postponed** — kept in the pool unexecuted
- **Mempool cap**: postponed transactions are dropped entirely once `_pending_tx_size >= _max_mempool_size` (`max-mempool-size` option, default 100M; `chain_plugin.cpp:1507`, `db_with.hpp:158-171`)
- **Outcome counters** (fed to block stats): expired / known (already in block) / applied / failed (RC or other exception) / postponed / dropped (:98-103, :215)
- **Skip flags**: `skip_validate | skip_transaction_signatures | skip_transaction_dupe_check` — with documented reasoning: validation can't become invalid, signatures are witness's job to recheck, TaPoS deliberately NOT skipped so fork switches drop cross-fork transactions, duplicates checked against the in-memory pending index (:175-193)
- If the pool is unexpectedly non-empty at restore time, a `NOTIFYALERT!` is logged; testnet builds abort (:76-88)

---

## Fork Database and Resolution

### Fork Database Structure

**`fork_item`** (`fork_database.hpp:20-41`):
```cpp
struct fork_item {
    weak_ptr<fork_item>   prev;         // Link to parent block
    bool                  invalid;       // Flagged if block found to be bad; blocks linking on top of it are rejected
    std::shared_ptr<full_block_type> full_block;
};
```

**Multi-index container** with three indices:
1. `block_id` — hashed unique, fast lookup by block hash
2. `by_previous` — hashed non-unique, find children of a parent
3. `block_num` — ordered non-unique, range queries by height

**Two-level indexing**:
- `_index` — linked blocks (connected to main chain back to LIB)
- `_unlinked_index` — orphaned blocks (parent not yet received)

**Maximum size**: `MAX_BLOCK_REORDERING = 1024` (`fork_database.hpp:67`). Adjusted live as LIB advances. The fork DB also maintains a map of the last block generated by each witness (`get_last_block_generated_by_each_witness`, `fork_database.cpp:255`), used by LIB calculation.

### Fork Resolution: Longest Chain Rule

**`fork_database::_push_block()`** (`fork_database.cpp:73-99`):

```cpp
// must be within max_size of current head
FC_ASSERT(item->get_block_num() > std::max<int64_t>(0, int64_t(_head->get_block_num()) - _max_size));  // :77-79
// Link to parent
auto itr = _index.get<block_id>().find(item->previous_id());
HIVE_ASSERT(itr != index.end(), unlinkable_block_exception, "block does not link to known chain");
FC_ASSERT(!(*itr)->invalid);   // can't build on a block flagged bad
item->prev = *itr;

_index.insert(item);

// Longest chain rule: higher block_num wins
if (!_head || item->get_block_num() > _head->get_block_num())
    _head = item;
```

The rule is simple: **highest block number wins**. Fork DB's `_head` pointer always tracks the tallest chain. The `unlinkable_block_exception` is translated to a graphene::net exception so the P2P layer can fetch missing ancestors (`p2p_plugin.cpp:178-185`).

### `sync_block_writer::push_block()` — Fork Decision (`sync_block_writer.cpp:67-160`)

For every incoming block:

1. Insert into fork DB; `on_fork_db_insert()` fires (:79-80)
2. **Double-production detection**: if the fork DB now holds more than one block at this height, log "block num collision" with the witnesses and timestamps involved (:81-94)
3. If the resulting fork DB head is **not higher** than the state head: `on_fork_ignore()`, return — the block is retained in the fork DB but not applied (:96-102)
4. Collect the chain of blocks from the new head down to the state head's height (:106-113). If the bottom of that chain links to the state head: **no fork switch** — apply the collected blocks oldest-first (`on_fork_normal()`). This handles "linking in previously unlinked blocks": several blocks can be applied from one push when an orphaned subtree just became connected. While applying multiple blocks, `_fork_db.set_head()` keeps the fork DB head in sync per block (:140-141); the flow-control pointer is only passed for the specific block that triggered the push (:139, :148)
5. Otherwise: `on_fork_apply()` then `switch_forks()` (:114-124); returns true (caller's `accept_block` returns "forked")
6. If applying a block fails: the failed block **and all fork-DB blocks after it on that fork** are removed, then the exception propagates (:150-157)

### Fork Switch

**`sync_block_writer::switch_forks()`** (`sync_block_writer.cpp:162-264`):

1. **Find common ancestor**: `_fork_db.fetch_branch_from(new_head_id, current_head_id)` — returns the two diverging branches (`fork_database.cpp:290-330`: equalize heights walking the taller branch down, then walk both in parallel until the parent matches)
2. **Pop old fork**: `pop_block_extended(old_branch.back()->previous_id())` — reverses blocks one-by-one through the undo stack; popped blocks' transactions land in `_popped_tx`
3. **Notify**: `_db.notify_switch_fork(current_head_block_num)`
4. **Apply new fork** oldest-to-newest via `apply_block_extended`; for the block that triggered the switch, its flow control is passed so its promise releases even if a later block fails ("the block was good after all", comment :203-205)
5. **Error recovery** (:213-261): on failure, the failed block and the rest of the new branch are removed from the fork DB. Then revert to the old fork **only if BOTH**:
   - `_fork_db.get_last_irreversible_block_num() < common_block_number` — nothing on the new fork became irreversible, AND
   - `_fork_db.get_head()->get_block_num() < original_head_block_number` — we are now on a shorter chain than where we started
   
   (conditions at :236-237; the in-code comment :228-232 spells out the three possibilities). Revert = pop back to the common ancestor and re-apply the old branch. **The exception is rethrown in every failure case** (:260) — even after a successful revert — so the caller always sees the failure.

### Pop Block

**`database::pop_block()`** (`database.cpp:669-709`):
```cpp
void database::pop_block()
{
    _pending_tx_session.reset();
    auto full_head_block = _block_writer->get_block_reader().fetch_block_by_id(head_id);
    HIVE_ASSERT(full_head_block, pop_empty_chain, "there are no blocks to pop");
    _block_writer->pop_block();   // Move fork DB head pointer back
    undo();                        // Reverse all state changes via undo stack
    // Recover popped transactions into _popped_tx for later re-evaluation
    _popped_tx.insert(_popped_tx.begin(), full_head_block->get_full_transactions()...);
}
```

`pop_block_extended(end_block)` (`database.cpp:711+`) pops repeatedly until the head equals `end_block` and returns the resulting head number.

**`fork_database::pop_block()`** (`fork_database.cpp:20-28`):
```cpp
FC_ASSERT(_head, "cannot pop an empty fork database");
auto prev = _head->prev.lock();
FC_ASSERT(prev, "popping head block would leave fork DB empty");
_head = prev;  // Simply move head pointer back
```

---

## Irreversibility

### Last Irreversible Block (LIB) Calculation

**Threshold**: `HIVE_IRREVERSIBLE_THRESHOLD = 75 * HIVE_1_PERCENT = 7500` (75%, `config.hpp:381`)

```cpp
// database.cpp:2993, :3014
offset = (HIVE_100_PERCENT - HIVE_IRREVERSIBLE_THRESHOLD) * num_witnesses / HIVE_100_PERCENT;  // 21 -> 5
witnesses_required_for_irreversibility = num_witnesses - offset;                               // 21 -> 16
```

With 21 witnesses: 16 must approve.

**`update_last_irreversible_block(optional<switch_forks_t> sf)`** (`database.cpp:2956-3064`) — the `sf` parameter is key:
- Called at the end of `_apply_block` with **no callback** (`std::optional<switch_forks_t>()`, `database.cpp:2321`)
- Called from fast-confirm processing **with** a fork-switch callback (`database.cpp:2951`, callback built in `chain_plugin.cpp:963-1000`)

Algorithm variants, in order:

1. **Early phase** (before `HIVE_START_MINER_VOTING_BLOCK` = `HIVE_BLOCKS_PER_DAY * 30` = 864,000 on mainnet, `config.hpp:180`): `LIB = head - 21` (:2962-2972)
2. **Replay with `skip_block_log`** (no fork DB): legacy algorithm — `nth_element` over the scheduled witnesses' `last_confirmed_block_num`, LIB = the value at the offset position, i.e. the highest block confirmed by ≥16 of them (:2995-3005)
3. **Normal**: collect scheduled witnesses from the *irreversibility* schedule (see below), delegate to `_block_writer->find_new_last_irreversible_block(...)` (:3007-3019)

If the new LIB candidate lies **on another fork** (:3025-3051):
- If that fork's head is *lower* than the current head: **postpone** — "there may be other places in the code that assume the head block number never decreases" (:3028-3036)
- If `sf` provided (fast-confirm path): execute the fork switch through the callback
- If `sf` absent (called from `_apply_block`): **defer** the switch — "we'll just delay the fork switch until the next time we get a new block or a fast-confirm" (:3044-3050)

Finally: `set_last_irreversible_block_num(std::min(new_lib, head_block_num()))` — **LIB never exceeds the head that state has actually processed** (relevant mid-fork-switch, :3053-3054), and fast-confirm map entries at or below the new LIB are erased (:3057-3061). The function returns the *old* LIB value, which the caller feeds to `migrate_irreversible_state`.

### Witness Approval Sources

A witness "approves" a block in two ways (`sync_block_writer.cpp:280-309`):
1. **Block generation** (implicit): the fork DB tracks each witness's most recent generated block (`fork_database.cpp:255`); producing a block implicitly approves all its ancestors
2. **Fast confirm** (explicit, HF26+): `witness_block_approve_operation` votes for a specific block ID

Per witness only the **highest block number** of the two counts (:296-308).

### `find_new_last_irreversible_block()` (`sync_block_writer.cpp:266-367`)

1. Build `number_of_approvals_by_block_id`: each scheduled witness's single best approved block (:289-309)
2. For each fork tip (`_fork_db.fetch_heads()`): walk backwards, accumulating approvals (an approval of block N counts for all its ancestors); stop at `old_last_irreversible` or when the running candidate is already higher (:311-352)
3. The first block on a walk reaching ≥16 approvals becomes the candidate if its tip is the highest such tip (:331-344)
4. `found_on_another_fork` = the candidate is not the same object as the same-numbered block on the main branch (:361-364)

### Fast Confirm Mechanism (HF26+)

Fast confirms are transactions containing exactly one `witness_block_approve_operation`:
```cpp
struct witness_block_approve_operation {
    account_name_type witness;
    block_id_type     block_id;
};
```

**Generation** (witness plugin, `on_finish_push_block` handler, `witness_plugin.cpp:219-308`) — after every successfully pushed block, when ALL of:
- HF26 active
- `note.block_num > _last_fast_confirmation_block_number` (guards against re-confirming during fork-switch reapplication, comment :223-224)
- production enabled AND p2p enabled
- block timestamp within `HIVE_UP_TO_DATE_MARGIN__FAST_CONFIRM` = **60s** of now (`config.hpp:434`) — no fast confirms while syncing

For each witness in the **irreversibility schedule** (= future schedule after HF26) that is locally represented (configured in `witness` list — or *all* of them in queen mode) **except the block's own producer** (the block itself is their approval):
- Build the op; TaPoS references **the LIB block** (not head — maximizes cross-fork validity, :271-276); expiration = head time + `HIVE_MAX_TIME_UNTIL_EXPIRATION/2` = 30 min; HF26 serialization; signed with the witness signing key (:266-283)
- Push locally via `chain_plugin.push_transaction` and broadcast via `p2p_plugin.broadcast_transaction` (:286-290)

Runtime toggle: `enable_fast_confirm()` / `disable_fast_confirm()` (atomic; exposed for testing via witness plugin API, `witness_plugin.cpp:533-546`).

**Network propagation — no special priority.** There is no fast-confirm-specific code in `libraries/net` or the p2p plugin (verified by search). Fast confirms travel as ordinary transaction items (inventory flooding) and arrive via `p2p_plugin::handle_transaction` → `chain_plugin::accept_transaction` → the **normal** (non-priority) write queue. The special treatment begins in `chain_plugin_impl::push_transaction` (`chain_plugin.cpp:950-1006`):

```cpp
if( not db.is_fast_confirm_transaction( full_transaction ) )
    db.process_non_fast_confirm_transaction( ... );   // normal pending-pool path
else
    db.process_fast_confirm_transaction( full_transaction, sf );  // in-memory only
```

`is_fast_confirm_transaction` (`database.cpp:537-541`): exactly one operation and its variant tag is `witness_block_approve_operation`. The `sf` lambda passed in (`chain_plugin.cpp:963-1000`) wraps `sync_block_writer::switch_forks` in `without_pending_transactions` with an `existing_block_flow_control` — **a fast confirm alone can trigger a fork switch** when a supermajority confirms a block on another fork.

**Processing** (`process_fast_confirm_transaction()`, `database.cpp:2899-2954`):
1. Assert HF26 active and shape correct
2. `validate_transaction(full_transaction, skip_tapos_check)` — full validation (expiration, signature against witness authority) except TaPoS, because the approving witness may be on a different fork (comment :2909-2914)
3. Ignore if the witness is not in the irreversibility schedule (:2920-2930)
4. Ignore if the witness already approved an equal-or-higher block (per-witness monotonicity, :2932-2945)
5. Record in the in-memory `_last_fast_approved_block_by_witness` map (:2946)
6. `update_last_irreversible_block(sf)` — may advance LIB **and/or switch forks** immediately
7. `migrate_irreversible_state(old_lib)` — flush any newly irreversible blocks

**Key design decisions**:
- Fast confirms are **never included in blocks** — the evaluator is unreachable: `witness_block_approve_evaluator::do_apply()` contains `HIVE_CHAIN_UNREACHABLE_CODE_ASSERT(false)` (`hive_evaluator.cpp:623-628`)
- They never enter the pending pool or the transaction index, so they cost no RC and don't affect block assembly
- This allows LIB to advance *between* blocks, not just when blocks are applied

### Irreversibility Propagation

**`migrate_irreversible_state(old_last_irreversible)`** (`database.cpp:3066-3097`):

When LIB advanced from `old_lib` to `new_lib`:

1. **Move blocks to block log**: `_block_writer->store_block(new_lib, head_block_num)` (`sync_block_writer.cpp:24-60`):
   - Asserts fork DB head == state head
   - Collects main-branch fork items from blocklog head+1 to new_lib (each must exist — `FC_ASSERT` otherwise), appends them to block storage, records the last one as `last_irreversible_block_data` in state, flushes head storage
   - **Trims fork DB**: `_fork_db.set_max_size(state_head - new_lib + 1)` — removes everything at or below the new LIB from both linked and unlinked indices (`fork_database.cpp:146-175`)
2. **Commit state**: `commit(new_lib)` — deletes undo data for all blocks ≤ new_lib; those state changes become permanent
3. **Notifications** (only if LIB actually advanced): `get_comments_handler().on_irreversible_block(new_lib)`, then `notify_irreversible_block(i)` for each block from old_lib+1 to new_lib (:3079-3089)
4. On any error: log + `theApp.generate_interrupt_request()` — **the node shuts down rather than continue with inconsistent irreversible state** (:3092-3096)

---

## Participation Tracking

### Mechanism

The `dynamic_global_property_object` tracks participation via:
- `recent_slots_filled` — 128-bit shift register (1 = block produced, 0 = missed)
- `participation_count` — running count of 1-bits (0-128)
- `current_aslot` — absolute slot number since genesis (`current_aslot += missed_blocks+1` per block, `database.cpp:2830`)

### Update Logic (`database.cpp:2815-2831`)

```cpp
for (uint32_t i = 0; i < missed_blocks + 1; i++)
{
    // Remove oldest bit (MSB) from count if it was 1
    participation_count -= (uint128_high_bits(recent_slots_filled) & 0x8000000000000000ULL) ? 1 : 0;
    // Shift left (drop oldest), add new bit (1 for actual block, 0 for miss)
    recent_slots_filled = (recent_slots_filled << 1) + (i == 0 ? 1 : 0);
    participation_count += (i == 0 ? 1 : 0);
}
```

### Participation Rate

```cpp
// database.cpp:531-535
uint32_t database::witness_participation_rate() const
{
    return uint64_t(HIVE_100_PERCENT) * fc::uint128_popcount(dpo.recent_slots_filled) / 128;
}
```

Returns a value in basis points (0-10000). Example: 128/128 = 100%, 64/128 = 50%.

The witness plugin checks this against `_required_witness_participation` (default 33%) before producing a block. If participation drops too low, witnesses stop producing (safety against extending a minority fork). Queen mode instead kills the node on low participation (`queen_plugin.cpp:199-202`).

---

## Undo History and Reorg Depth Limits

Two distinct limits bound how far the node can roll back:

1. **`HIVE_MAX_UNDO_HISTORY` = 10,000** (`config.hpp:369`). Enforced in `update_global_dynamic_data()` (`database.cpp:2833-2840`):
   ```cpp
   HIVE_ASSERT( _dgp.head_block_number - get_last_irreversible_block_num() < HIVE_MAX_UNDO_HISTORY,
                undo_database_exception,
                "The database does not have enough undo history to support a blockchain with so many missed blocks. "
                "Please add a checkpoint if you would like to continue applying blocks beyond this point." );
   ```
   Every reversible block keeps an undo session alive in chainbase; this caps that growth. **Behavior when exceeded**: the block being applied fails with `undo_database_exception` — the node stops following the chain. This happens when LIB stalls (e.g. participation below 75% so irreversibility cannot advance) for ~10,000 blocks (~8.3 hours). **Escape hatches**: (a) configure a `checkpoint` — pre-checkpoint blocks carry `skip_undo_history_check` and `skip_undo_block` (`chain_plugin.cpp:1046-1062`); (b) witnesses running `enable-stale-production` get `skip_undo_history_check` in their production skip flags (`witness_plugin.cpp:671`); (c) replay sets it implicitly (LIB pinned to head via `skip_undo_block`).

2. **Fork DB `MAX_BLOCK_REORDERING` = 1024** (`fork_database.hpp:67`): the fork DB refuses blocks more than 1024 below its head (`fork_database.cpp:77-79`) and its effective size is continuously narrowed to `head - LIB + 1` as LIB advances (`sync_block_writer.cpp:59`). This bounds the *practical* reorg depth to head−LIB, normally a handful of blocks; 1024 is only reachable when irreversibility stalls.

---

## Block Log

### Block Storage Modes (`block-log-split` option)

`block-log-split` (`chain_plugin.cpp:1506`, default **9999**) selects the storage backend (`block_storage_i::create_storage`, :1548):

| Value | Meaning |
|-------|---------|
| `-1` | Legacy single monolithic `block_log` file (`LEGACY_SINGLE_FILE_BLOCK_LOG`) |
| `0` | **No block log at all** — memory-only `single_block_storage` keeping the head block (state-only node) |
| `N > 0` | Split log: 1M-block part files, **pruned** to the N most recent parts |
| `9999` (default) | = `MAX_FILES_OF_SPLIT_BLOCK_LOG` (`block_storage_interface.hpp:9`) — split but effectively unpruned (9999 parts ≈ 10B blocks) |

### On-Disk Format

The block log is an append-only binary file:

```
+---------+------------------+---------+------------------+-----+
| Block 1 | Pos+Flags of B1  | Block 2 | Pos+Flags of B2  | ... |
+---------+------------------+---------+------------------+-----+
```

- Each block is serialized (possibly compressed)
- Followed by 8 bytes: 48-bit file offset of block start + compression flags
- Last 8 bytes of file point to head block start — enables backward traversal
- Files: `block_log` (monolithic) or `block_log_part.0001`-style part files (4-digit zero-padded, `block_log.cpp:64-72`)

### Block Log Artifacts (Index File)

The `.artifacts` file provides O(1) random access by block number.

**Header** (`block_log_artifacts.cpp:46-69`):
```cpp
struct artifact_file_header {
    uint32_t head_block_num;
    char git_version[41];
    uint8_t format_major_version;      // Currently 1.1
    uint8_t format_minor_version;
    uint8_t dirty_close;               // Corruption flag
    uint32_t tail_block_num;
    uint32_t generating_interrupted_at_block;  // Resume checkpoint
};
```

**Per-block entry** (`block_log_artifacts.cpp:82-166`):
```cpp
struct artifact_file_chunk {
    uint64_t block_log_offset : 48;     // File position
    uint64_t dictionary_no : 8;         // Compression dictionary number
    uint64_t custom_dict_used : 1;
    uint64_t gap : 6;
    uint64_t is_compressed : 1;         // 0=raw, 1=zstd
    uint64_t stripped_block_id[2];      // Block ID without block_num portion (16 bytes)
};
```

Total per-block entry size: 8 + 16 = 24 bytes. Artifacts can be regenerated from the block log if missing or corrupted (each part file has its own artifacts).

### Compression

- **Algorithm**: ZSTD (Zstandard) — `block_log_compression.cpp`
- **Default level**: 15 (`chain_plugin.cpp:164`)
- **Custom dictionaries**: Pre-trained per million-block range, stored in `block_compression_dictionaries.cpp`
- **Optimization**: Magicless format, no content size flag, no checksum (all save space)
- **Performance**: ~3.5ms compression, ~65μs decompression per block

### Split Block Log Layout

- **Naming**: `block_log_part.0001` through `block_log_part.9999`
- **Size**: `BLOCKS_IN_SPLIT_BLOCK_LOG_FILE` = 1,000,000 blocks per part on mainnet, 400 on testnet (`block_log.hpp:11-15`)
- **Part N contains blocks** `[(N-1)*1M + 1, N*1M]` (`block_log_wrapper.hpp:101-110`)
- Only the head part is ever open for writing; all earlier parts are read-only (`block_log_wrapper.cpp:736-739`)

### Migration: Monolithic → Split (automatic at startup)

When the node opens block storage (`block_log_wrapper::common_open_and_init`, `block_log_wrapper.cpp:616-767`):

1. Scan the blockchain directory for `block_log_part.*` files (:633-638)
2. **No part files found**: if a legacy `block_log` exists, **auto-split it** via `try_splitting_monolithic_log_file` (:640-670, :503-525). How much is split depends on context (:643-661):
   - replay or snapshot load pending → split the *entire* source log
   - otherwise → split only up to the **state head block** so log and state match; if state is empty, derive from source
   - pruned configs split only the newest `N+1` parts' worth
   If there is no monolithic file either, a fresh empty part file is created (:672-682)
3. **Part files found**: determine the required tail part from config/pruning/replay needs (:685-716), then `force_parts_exist` (:527-591) checks continuity (no gaps in part numbering); missing needed parts can be regenerated by splitting the monolithic file *if it is still present* — but never overwriting an existing isolated part ("blocking part", :555-575); otherwise startup throws with the explicit missing-file range
4. **Open** all needed parts; for every adjacent pair, assert that the first block of part N links by `previous` ID to the last block of part N−1 (:727-766) — corrupted/mismatched part sets are rejected with a runtime error

The split routine itself (`split_block_log()`, `split_block_log.cpp:11-113`): opens the monolithic log read-only, computes head/tail part numbers, refuses if conflicting part files exist in the output dir (:51-59), then copies **raw** (compressed) block data in batches of `BLOCKS_IN_BATCH_IO_MODE` = 10,000 blocks (400 testnet) using `multi_read_raw_block_data`/`multi_append_raw` — no decompress/recompress — with the head block handled separately (:93-108). The monolithic file is left in place (it is the operator's to delete).

**Manual tooling**: `block_log_util --split` performs the same conversion offline; `--merge-block-logs` does the reverse (split parts → monolithic), with `--block-number` to cap the merge (`block_log_util.cpp:1372, :1377-1382`).

### Runtime Rotation and Pruning

On append (`block_log_wrapper::internal_append`, `block_log_wrapper.cpp:804-849`): when the just-written block was the last of its part, the next append creates `block_log_part.<N+1>` (flushing the previous head part first). If pruning is configured (`_block_log_split > 0`) and more than N parts now exist, the oldest part is atomically detached and handed to a **garbage collector** (:831-843) which closes and deletes the part file + its artifacts only when no other thread (e.g. an API reader) still holds a reference (`dispose_garbage`, :123-149; final forced attempt at close, with `FC_ASSERT` if an API thread still uses it).

Reads of pruned blocks fail with an explicit message: "Block ${num} has been pruned (oldest stored block is ${old}). Consider disabling pruning or increasing block-log-split value" (:280-305).

### Read Operations

**By block number** (`block_log.cpp:491-515`):
1. Route to the right part: `get_block_log_corresponding_to(block_num)` (`block_log_wrapper.cpp:422-431`) — returns null for pruned/unknown parts
2. Look up position and attributes in that part's artifacts file
3. Read raw bytes from the log at that offset
4. Decompress if needed (check `is_compressed` flag)
5. Return `full_block_type`

**Batch read** for efficiency:
- `multi_read_raw_block_data()` reads a range of blocks in a single I/O operation (used by P2P sync serving and splitting); ranges crossing a part boundary are looped per-part (`block_log_wrapper.cpp:433-460`)
- `process_blocks()` iterates ranges across parts for replay (:244-266)

---

## Key Discoveries

1. **Fast confirms never enter blocks**: The `witness_block_approve_evaluator::do_apply()` always asserts false. These transactions are processed entirely out-of-band via `process_fast_confirm_transaction()`, which updates an in-memory map and immediately re-checks LIB.

2. **Fast confirms get no P2P priority — but they alone can trigger fork switches**: there is no fast-confirm special-casing in the net layer or the write queues (they ride the normal transaction queue behind blocks). Their power is in processing: `update_last_irreversible_block` is only given a fork-switch callback on the fast-confirm path; when LIB lands on another (equal-or-longer) fork, the switch executes immediately. The same situation discovered during `_apply_block` is deferred to the next block or fast confirm (`database.cpp:3038-3050`).

3. **The single-writer architecture is the concurrency model**: one `write_queue` thread performs every state mutation; P2P blocks and generation requests use a priority queue over transactions; in live mode the writer yields the write lock every 500ms (1000ms on witness nodes) for readers. Promise-release points differ by source: P2P threads resume at TXS_EXECUTED (before housekeeping/pending reapplication), the witness thread at APPLIED (so it never sees stale head state).

4. **`queen_mode` is a testnet-only instant-production mode**: the queen plugin (cannot initialize on mainnet builds) disables P2P, makes the witness plugin represent *all* scheduled witnesses (bypassing the configured-witness check), and produces a block from inside the writer thread the moment pending transactions fill the target size/count — a benchmark/CI tool producing blocks as fast as they can be filled rather than every 3s.

5. **Block application is fully atomic**: No per-transaction undo sessions during block application. The comment in code explicitly states: "We do not need to push the undo state for each transaction because they either all apply and are valid or the entire block fails to apply."

6. **Known bad merkle roots are tolerated**: `shared_db_merkle` map contains block numbers with known incorrect merkle roots from historical chain data. These are accepted to maintain replay compatibility.

7. **The future witness schedule (HF26+) drives irreversibility**: `get_witness_schedule_object_for_irreversibility()` returns the *future* schedule after HF26 (`database.cpp:2891-2897`). Both LIB counting and fast-confirm eligibility use it; fast-confirm generation also signs for future-scheduled local witnesses.

8. **Participation safety**: If participation rate drops below a configurable threshold (default 33%), witnesses stop producing blocks entirely. The `recent_slots_filled` 128-bit register provides a 6.4-minute rolling window.

9. **Post-HF17: No more PoW miners**: `HIVE_MAX_MINER_WITNESSES_HF17 = 0`. The timeshare slot is now the sole entry point for non-top-20 witnesses, selected via virtual time fair queuing.

10. **XORshift shuffle is deterministic but non-trivially manipulable**: Seeded by `head_block_time << 32`, the shuffle changes every 21 blocks. A witness can't choose their position in the next round because the seed depends on the previous round's timing.

11. **Two distinct rollback depth limits**: fork DB capacity (`MAX_BLOCK_REORDERING` = 1024, continuously trimmed to head−LIB+1) bounds in-memory reorg depth; `HIVE_MAX_UNDO_HISTORY` = 10,000 bounds head−LIB itself — if irreversibility stalls for ~8.3 hours the node halts with `undo_database_exception` (checkpoint or stale-production flags bypass it).

12. **Block production has a 750ms lag tolerance**: If a witness is more than 750ms late for their slot, it recomputes its production data for the next future slot and skips the missed one to avoid producing stale blocks.

13. **Produced blocks are broadcast before they are applied**: `witness_generate_block_flow_control::on_fork_db_insert()` fires the P2P broadcast at fork-DB insertion, while the producing node is still applying the block to its own state — minimizing propagation latency.

14. **Split block log migration is automatic and incremental**: at startup, a missing/partial set of part files is generated from a still-present monolithic `block_log` (raw copy, no recompression), split only as far as the state head so log and state stay consistent; pruning configs delete the oldest part (file + artifacts) at runtime via a use-count-aware garbage collector.

15. **Pending reapplication is budgeted, not exhaustive**: after each block, reapplication runs only if the block is <20s old, executes at most 200ms of transactions, postpones the rest, and drops postponed transactions beyond the 100MB (default) mempool cap. Popped fork-switch transactions are recovered first. TaPoS is deliberately *not* skipped so cross-fork transactions die on reapplication.

---

## Code References

| Component | File | Key Methods/Lines |
|-----------|------|-------------------|
| Writer thread & queues | `chain_plugin.cpp` | loop :439-737, queues :180-209, visitor :289-413, entry points :1969-2158 |
| Fast confirm routing | `chain_plugin.cpp` | `push_transaction()` :950-1006 (incl. fork-switch lambda :963-1000) |
| push_block pipeline | `chain_plugin.cpp` | `push_block()` :1039-1097, `_push_block()` :1099-1119, checkpoint flags :1046-1062 |
| Replay — reindex | `chain_plugin.cpp` | `reindex_internal()` :1222-1290 |
| Replay — IRB writer | `irreversible_block_writer.cpp` | `store_block()` no-op :19-21 |
| Flow control | `block_flow_control.hpp` | phases :135-146; subclasses :206-305 |
| Flow control impl | `block_flow_control.cpp` | transitions :46-89, promise points :209-267, sync stats gate :274-284 |
| Block application | `database.cpp` | `_apply_block()` :2183-2369, `apply_block_extended()` :2123-2142, `validate_block_header()` :2757-2779 |
| Transaction application | `database.cpp` | `_apply_transaction()` :2644-2702, `validate_transaction()` :2521-2642, pending entry :552-576 |
| Operation dispatch | `database.cpp` | `apply_operation()` :2722-2746 |
| Pending reapplication | `db_with.hpp` | `pending_transactions_restorer` :58-243 |
| Witness scheduling | `witness_schedule.cpp` | `update_witness_schedule4()` :152-396, shuffle :372-388, HF26 dual schedule :403-440 |
| Slot mapping | `database.cpp` | `get_scheduled_witness()` :904-910, `get_slot_time()` :912-935, `get_slot_at_time()` :937-943 |
| Missed blocks / witness stats | `database_witness.cpp` | `update_witness_missed_blocks()` :284-306, `update_signing_witness()` :175-185 |
| Participation | `database.cpp` | `update_global_dynamic_data()` :2789-2841, `witness_participation_rate()` :531-535 |
| Undo history cap — enforcement | `database.cpp` | :2833-2840 |
| Undo history cap — constant | `config.hpp` | 369 |
| Fork DB | `fork_database.cpp` | `_push_block()` :73-99, `pop_block()` :20-28, `set_max_size()` :146-175, witness map :255, `fetch_branch_from()` :290-330 |
| Fork decision & switch | `sync_block_writer.cpp` | `push_block()` :67-160, `switch_forks()` :162-264, `store_block()` :24-60 |
| LIB calculation | `database.cpp` | `update_last_irreversible_block()` :2956-3064 |
| LIB determination | `sync_block_writer.cpp` | `find_new_last_irreversible_block()` :266-367 |
| Fast confirm processing | `database.cpp` | `is_fast_confirm_transaction()` :537-541, `process_fast_confirm_transaction()` :2899-2954 |
| Fast confirm generation | `witness_plugin.cpp` | `on_finish_push_block()` :219-308, toggle :533-546 |
| Irreversibility migration | `database.cpp` | `migrate_irreversible_state()` :3066-3097 |
| Witness plugin | `witness_plugin.cpp` | production data :310-367, loop :369-467, `maybe_produce_block()` :469-526, queen mode :570-577 |
| Block producer | `block_producer.cpp` | `_generate_block()` :31-85, hardfork votes :87-108, `apply_pending_transactions()` :111-216, queen fill :218-253 |
| Queen plugin | `queen_plugin.cpp` | production trigger :98-127, slot scan :162-223, init/testnet guard :268-297 |
| P2P handlers | `p2p_plugin.cpp` | `handle_block()` :128-207, `handle_transaction()` :209-226 |
| Block log wrapper / split | `block_log_wrapper.cpp` | open/auto-split :616-767, `force_parts_exist()` :527-591, rotation+GC :804-849, pruned reads :280-305 |
| Split routine | `split_block_log.cpp` | `split_block_log()` :11-113 |
| Block log core | `block_log.cpp` | naming :44-72, `append_raw()` :338-366, `read_block_by_num()` :491-515 |
| Block log artifacts | `block_log_artifacts.cpp` | header :46-69, chunk :82-166 |
| Storage constants — block log | `block_log.hpp` | 11-15 |
| Storage constants — interface | `block_storage_interface.hpp` | 9 |
| Global properties | `global_property_object.hpp` | Full struct definition |

---

## Discrepancies and Potential Issues

1. **`update_signing_witness` aslot formula — verified correct, but misleading** (resolved): `new_block_aslot = dpo.current_aslot + get_slot_at_time(new_block.timestamp)` (`database_witness.cpp:175-185`) looks like double-counting since `update_global_dynamic_data` already advanced `current_aslot` past this block. It is not: at this point head_block_time equals the new block's timestamp, so `get_slot_at_time(new_block.timestamp)` returns **0** (`when < get_slot_time(1)` → 0, `database.cpp:937-943`) and the addition is a no-op. The formula only behaves nontrivially if call order ever changed — worth a comment upstream, but not a bug.

2. **Known bad merkle map is a consensus escape hatch**: `shared_db_merkle` allows blocks with incorrect merkle roots to be accepted. This is necessary for replay but means historical data integrity has known exceptions.

3. **Fork switch error recovery is conditional, and failure always propagates**: after a failed fork switch, reverting to the old fork happens only when *both* (a) no new-fork block became irreversible past the common ancestor and (b) the chain is now shorter than where it started (`sync_block_writer.cpp:236-237`). If the partially-applied new fork is already at least as long, the node stays on it; if irreversibility crossed the common ancestor, reverting is impossible. In every case the exception is rethrown (:260) — the pushing peer's block is reported failed even when the node recovered to a consistent state.

4. **Fast confirm TaPoS skip**: fast confirms intentionally skip TaPoS validation because the approving witness may reference a block on a different fork (`database.cpp:2909-2915`); generation softens this by referencing the LIB block in TaPoS (`witness_plugin.cpp:271-276`). They still carry full signature validation, a 30-minute expiration, and per-witness block-number monotonicity, but structurally remain weaker-validated than block transactions.

5. **Fast confirms are invisible to transaction dedup infrastructure**: they never enter `transaction_index` (`is_known_transaction` stays false), so the P2P layer's "is item known" check (`p2p_plugin.cpp:120-123`) cannot recognize an already-processed fast confirm by ID; dedup relies on the net-layer inventory cache and the per-witness monotonicity check. Harmless in practice (re-processing is an ignored no-op) but a structural oddity.

6. **Stale comment in the writer loop**: the design comment (`chain_plugin.cpp:495-506`) describes a 10ms sleep after yielding the write lock; no such sleep exists in the loop body (:511-716) — the thread re-waits on the condition variable immediately. Behavior is fine; the comment overstates idle time.

---

## Open Questions

1. **Net-layer propagation details for fast confirms**: the graphene::net inventory/flooding mechanics (item caching, expiry of never-indexed transaction items) were not traced into `libraries/net`. How long a fast confirm circulates and how peers throttle re-requests is unverified (the chain-side handling is fully documented above).

2. **`single_block_storage` (block-log-split=0) operational limits**: with no block log, how the node serves sync requests to peers (presumably it cannot) and what API methods degrade was not traced (`single_block_storage.cpp` unexamined).

3. **`fork_database::get_last_block_generated_by_each_witness()` cost profile**: the map is rebuilt per LIB evaluation (`fork_database.cpp:255`); implementation/caching details not examined.
