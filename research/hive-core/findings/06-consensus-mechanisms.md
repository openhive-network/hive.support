# Findings: Consensus Mechanisms — Block Production, Witness Schedule, Fork Resolution

## Summary

Hive uses Delegated Proof of Stake (DPoS) with 21 active witnesses producing blocks every 3 seconds. The consensus layer is built on four interacting subsystems: (1) witness scheduling via a virtual-time fair queuing algorithm, (2) a 200ms polling production loop in the witness plugin, (3) an in-memory fork database tracking competing chains with longest-chain selection, and (4) a 75%-of-witnesses irreversibility threshold with HF26 "fast confirm" acceleration.

All code verified directly from `libraries/chain/` and `libraries/plugins/witness/` in the hive-core repository.

---

## Block Production Flow

### Overview: From "Witness's Turn" to "Block in Chain"

1. **Witness plugin polls** every 200ms (`schedule_production_loop()` in `witness_plugin.cpp:369-380`)
2. **Slot check**: converts current time to slot number, looks up scheduled witness for that slot
3. **If it's our turn**: verify private key available, check network participation rate
4. **Generate block**: assemble pending transactions, create signed block header
5. **Push to fork DB**: insert into fork database (may trigger fork switch)
6. **Broadcast**: P2P layer distributes block to network
7. **Apply block**: other nodes receive, validate, apply through the full `_apply_block()` pipeline

### Witness Plugin Production Loop

The witness plugin uses a **timer-based polling loop** with a 200ms cycle:

```
BLOCK_PRODUCTION_LOOP_SLEEP_TIME = 200,000 microseconds (200ms)
BLOCK_PRODUCING_LAG_TIME = 750ms (max acceptable production delay)
```

**`schedule_production_loop()`** (`witness_plugin.cpp:369-380`):
- Sets async timer for next 200ms interval (minimum 50ms)
- On expiry, calls `block_production_loop()`

**`block_production_loop()`** (`witness_plugin.cpp:382-467`):
- Checks if past genesis time
- Calls `maybe_produce_block()` which delegates to `update_produce_block_data()`
- Reschedules itself for next 200ms

**`update_produce_block_data()`** (`witness_plugin.cpp:310-367`):
1. Get current slot: `slot = _db.get_slot_at_time(time)`
2. Get scheduled witness: `scheduled_witness = _db.get_scheduled_witness(slot)`
3. Check if it's one of our configured witnesses (or queen mode)
4. Verify private key for the witness's signing key exists
5. Check participation rate: `_db.witness_participation_rate() >= _required_witness_participation`
6. Store decision in `produce_block_data` struct

**Time adjustment**: Current time adds 500ms buffer to catch the slot window:
```cpp
fc::time_point_sec now = fc::time_point::now() + fc::microseconds(500000);
```

### Block Assembly

**`block_producer::_generate_block()`** (`block_producer.cpp:31-85`):

1. Start undo session for block
2. Set pending block header (witness, timestamp, previous block ID)
3. Call `apply_pending_transactions()` to select and validate transactions
4. Create `full_block_type` from header + transactions + signer
5. Assert block size ≤ `HIVE_MAX_BLOCK_SIZE`
6. Push block to chain via `generate_block_ctrl->store_produced_block()`

**Transaction selection** (`block_producer.cpp:111-216`):
- Iterate `_db._pending_tx` in order
- Skip expired transactions (`runtime_expiration < when`)
- Skip already-known transactions
- Check block size: `total_block_size + tx_size < maximum_block_size`
- Re-apply each transaction in undo session to verify still valid
- On failure: undo and skip (will retry after block reapply)
- On success: squash session, include in block

**Block size calculation**:
```cpp
total_block_size = fc::raw::pack_size(pending_block_header) + 4; // header + tx count varint
// Then add each tx_size
```

### Block Signing

- Block is signed via `fc::ecc::private_key` passed as `signer` to `full_block_type::create_from_block_header_and_transactions()`
- The signing key must match `witness_object.signing_key` on the witness's chain record
- Signing is skipped if `skip_witness_signature` flag is set (testing only)

### Post-Generation

After successful block generation:
1. **Push to chain**: `_chain.push_block(*generate_block_ctrl, skip)` — enters the fork DB and `apply_block` pipeline
2. **Broadcast to P2P**: `witness_generate_block_flow_control::on_fork_db_insert()` calls `p2p.broadcast_block(full_block)`
3. **Fast confirm** (HF26+): if other witnesses are configured locally, create and broadcast `witness_block_approve_operation` transactions

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
// witness_schedule.cpp:403-405
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

5. **Shuffle** (lines 372-388) — see Shuffle Algorithm below

6. **Calculate median witness properties** (lines 58-150):
   - Sort all scheduled witnesses' proposed values
   - Take median for: `account_creation_fee`, `maximum_block_size`, `hbd_interest_rate`, `account_subsidy_budget`, `account_subsidy_decay`

### Future Witness Schedule (HF26+)

After `HIVE_HARDFORK_1_26_FUTURE_WITNESS_SCHEDULE`, two schedules are maintained:

```cpp
// witness_schedule.cpp:410-432
// Promote future schedule to current
db.modify(wso, [&](witness_schedule_object& ws) { ws.copy_values_from(future_wso); });
// Compute new future schedule
update_witness_schedule4(db, future_wso);
```

This pre-computes the next round's schedule, reducing production uncertainty.

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

### Missed Blocks

When a witness misses their slot (`database_witness.cpp:284-306`):

1. For each missed slot, the scheduled witness gets:
   - `total_missed++` counter increment
   - `producer_missed_operation` virtual operation emitted
   - Between HF14 and HF20: if `head_block_num - last_confirmed_block_num > HIVE_WITNESS_SHUTDOWN_THRESHOLD` (28,800 blocks = 1 day on mainnet), witness is **disabled** by clearing signing key, and `shutdown_witness_operation` is emitted

2. Participation tracking updates via `update_global_dynamic_data()` — see Participation Tracking below

### Witness Voting

- **Type**: Approval voting — each account votes for up to 30 witnesses
- **Weight**: Voter's governance_vote_power (derived from vesting shares/VEST)
- **Storage**: `witness_vote_object` pairs (account, witness)
- **Validation**: `FC_ASSERT(w.votes <= total_vesting_shares.amount)` — votes can never exceed total vesting

---

## Block Application Sequence

### Entry Points

There are multiple entry points depending on block source:

| Source | Entry Point | Skip Flags |
|--------|------------|------------|
| P2P block | `apply_block_extended()` | Minimal skips |
| Sync mode | `apply_block_extended()` with `skip_undo_block` | More skips |
| Self-produced | `push_block()` via `generate_block_flow_control` | `skip_block_size_check` |
| Replay | `apply_block_extended()` | Many validation skips |

### `apply_block_extended()` (`database.cpp:2123-2142`)

Outer wrapper that manages undo sessions:
- If `skip_undo_block`: apply directly (sync mode, no rollback needed)
- Otherwise: wrap in undo session, then push session on success

### `apply_block()` (`database.cpp:2073-2121`)

Applies skip flags via `detail::with_skip_flags()`, then delegates to `_apply_block()`.

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
- `block_ctrl->on_end_of_transactions()` — flow control callback

#### Phase 9: Global State Updates (lines 2314-2331)
```
1. update_global_dynamic_data(block)    — head block, participation, aslot
2. update_signing_witness(witness, block) — witness stats
3. update_last_irreversible_block()     — LIB advancement
4. create_block_summary(full_block)     — TaPoS reference data
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

### Transaction Application Chain

**`apply_transaction()`** → sets skip flags → **`_apply_transaction()`** (`database.cpp:2644-2702`):

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

### Operation Application

**`database_impl::apply_operation()`** (`database.cpp:2722-2746`):
1. Create operation notification
2. `notify_pre_apply_operation()`
3. If HF20+: `rc().handle_operation_discount(op)` — RC discounts
4. **`_evaluator_registry.get_evaluator(op).apply(op)`** — dispatch to specific evaluator
5. `notify_post_apply_operation()`

### Skip Flags

Defined in `database.hpp`:

| Flag | Bit | Purpose |
|------|-----|---------|
| `skip_nothing` | 0 | Full validation |
| `skip_witness_signature` | 1<<0 | Reindexing |
| `skip_transaction_signatures` | 1<<1 | Non-witness nodes |
| `skip_transaction_dupe_check` | 1<<2 | Reindexing |
| `skip_fork_db` | 1<<3 | Reindexing |
| `skip_block_size_check` | 1<<4 | Self-produced blocks |
| `skip_tapos_check` | 1<<5 | Reindexing |
| `skip_authority_check` | 1<<6 | Reindexing |
| `skip_merkle_check` | 1<<7 | Reindexing |
| `skip_undo_history_check` | 1<<8 | Reindexing |
| `skip_witness_schedule_check` | 1<<9 | Reindexing |
| `skip_validate` | 1<<10 | Pre-checkpoint |
| `skip_validate_invariants` | 1<<11 | Skip invariant checks |
| `skip_undo_block` | 1<<12 | Sync mode |
| `skip_block_log` | 1<<13 | Reindex only |

### Pending Transaction Reapplication

After a block is applied, previously pending transactions are re-tested (`db_with.hpp:59-242`):
- `pending_transactions_restorer` clears pending pool before block, restores after
- Reapplication uses relaxed skip flags: `skip_validate | skip_transaction_signatures | skip_transaction_dupe_check`
- Transactions that fail (e.g., RC exhausted by block transactions) are silently dropped

---

## Fork Database and Resolution

### Fork Database Structure

**`fork_item`** (`fork_database.hpp:20-41`):
```cpp
struct fork_item {
    weak_ptr<fork_item>   prev;         // Link to parent block
    bool                  invalid;       // Flagged if block found to be bad
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

**Maximum size**: Default 1024 blocks. Trimmed when LIB advances.

### Fork Resolution: Longest Chain Rule

**`fork_database::_push_block()`** (`fork_database.cpp:73-99`):

```cpp
// Link to parent
auto itr = _index.get<block_id>().find(item->previous_id());
HIVE_ASSERT(itr != index.end(), unlinkable_block_exception, "block does not link to known chain");
FC_ASSERT(!(*itr)->invalid);
item->prev = *itr;

_index.insert(item);

// Longest chain rule: higher block_num wins
if (!_head || item->get_block_num() > _head->get_block_num())
    _head = item;
```

The rule is simple: **highest block number wins**. Fork DB's `_head` pointer always tracks the tallest chain.

### Fork Switch

When a new block arrives that extends a different fork than the current state head:

**`sync_block_writer::switch_forks()`** (`sync_block_writer.cpp:162-264`):

1. **Find common ancestor**: `_fork_db.fetch_branch_from(new_head_id, current_head_id)`
   - Walks both branches backward until they share a parent
   - Returns two vectors: blocks unique to each fork

2. **Pop old fork**: `pop_block_extended(old_branch.back()->previous_id())`
   - Reverses blocks one-by-one using undo stack
   - Recovers transactions from popped blocks into `_popped_tx` pool

3. **Notify**: `_db.notify_switch_fork(current_head_block_num)`

4. **Apply new fork**: Iterate new_branch from oldest to newest:
   ```cpp
   for (auto ritr = new_branch.crbegin(); ritr != new_branch.crend(); ++ritr)
       apply_block_extended((*ritr)->full_block, skip, ...);
   ```

5. **Error recovery**: If applying new fork fails:
   - Mark failed blocks as invalid in fork DB
   - If old fork was shorter: log error, propagate exception (can't switch back safely)
   - If old fork was longer or equal: pop bad fork, re-apply old fork

### Pop Block

**`database::pop_block()`** (`database.cpp:669-709`):
```cpp
void database::pop_block()
{
    _pending_tx_session.reset();
    auto full_head_block = _block_writer->get_block_reader().fetch_block_by_id(head_id);
    _block_writer->pop_block();   // Move fork DB head pointer back
    undo();                        // Reverse all state changes via undo stack
    // Recover popped transactions into _popped_tx for later re-evaluation
    _popped_tx.insert(_popped_tx.begin(), full_head_block->get_full_transactions()...);
}
```

**`fork_database::pop_block()`** (`fork_database.cpp:20-28`):
```cpp
FC_ASSERT(_head, "cannot pop an empty fork database");
auto prev = _head->prev.lock();
FC_ASSERT(prev, "popping head block would leave fork DB empty");
_head = prev;  // Simply move head pointer back
```

### `fetch_branch_from()` — Finding Common Ancestor (`fork_database.cpp:290-330`)

```
1. Walk the taller branch down to match the shorter branch's height
2. Walk both branches back in parallel until they share a parent (previous_id match)
3. Include the divergence point in both branches
```

---

## Irreversibility

### Last Irreversible Block (LIB) Calculation

**Threshold**: `HIVE_IRREVERSIBLE_THRESHOLD = 75 * HIVE_1_PERCENT = 7500` (75%)

This means 75% of scheduled witnesses must "approve" a block for it to become irreversible. With 21 witnesses: `ceil(21 * 0.75)` = 16 witnesses required.

**Calculation** (`database.cpp:2956-3064` — `update_last_irreversible_block()`):

**Early phase** (before `HIVE_START_MINER_VOTING_BLOCK` = 864,000 blocks on mainnet):
```cpp
// Simple rule: LIB = head - 21
if (head_block_num() > HIVE_MAX_WITNESSES)
    set_last_irreversible_block_num(head_block_num() - HIVE_MAX_WITNESSES);
```

**Normal operation** (after voting enabled):

1. Get the scheduled witnesses from `witness_schedule_object_for_irreversibility`
2. Calculate required approvals:
   ```cpp
   offset = (HIVE_100_PERCENT - HIVE_IRREVERSIBLE_THRESHOLD) * num_witnesses / HIVE_100_PERCENT;
   witnesses_required = num_witnesses - offset;  // ≈75% of 21 = 16
   ```
3. Delegate to `find_new_last_irreversible_block()` — see below

### Witness Approval Sources

A witness "approves" a block in two ways:
1. **Block generation** (implicit): producing a block implicitly approves all ancestor blocks
2. **Fast confirm** (explicit, HF26+): `witness_block_approve_operation` explicitly votes for a specific block

The LIB calculation considers whichever is higher (most recent) for each witness:
```cpp
best_block = max(fast_approved_block_num, last_generated_block_num)
```

### `find_new_last_irreversible_block()` (`sync_block_writer.cpp:266-367`)

1. Collect each scheduled witness's best approved block (max of fast-confirm vs generation)
2. For each fork tip (blocks with no children):
   - Walk backwards counting witness approvals
   - A witness's approval of block N counts as approval of all ancestors
   - If ≥ required witnesses approve a block → candidate for new LIB
3. Select the highest such block across all fork tips
4. Check if the candidate LIB is on the main branch or a different fork
5. If on another fork: may trigger a fork switch (only if that fork is at least as long)

### Fast Confirm Mechanism (HF26+)

**`process_fast_confirm_transaction()`** (`database.cpp:2899-2954`):

Fast confirms are special transactions containing a single `witness_block_approve_operation`:
```cpp
struct witness_block_approve_operation {
    account_name_type witness;
    block_id_type     block_id;
};
```

Processing flow:
1. Assert HF26 is active
2. Verify it's a single-operation transaction with `witness_block_approve_operation`
3. Validate transaction (skip TaPoS — witness may be on different fork)
4. Verify witness is in the current schedule
5. Check the approval is for a higher block than any previous approval from this witness
6. Store in `_last_fast_approved_block_by_witness` map
7. Immediately re-run `update_last_irreversible_block()` — LIB may advance
8. `migrate_irreversible_state()` — process any newly irreversible blocks

**Key design decisions**:
- Fast confirms are **not included in blocks** — they are processed out-of-band via P2P
- The evaluator always asserts false: `HIVE_CHAIN_UNREACHABLE_CODE_ASSERT(false)` (`hive_evaluator.cpp:623-628`)
- TaPoS is skipped because the approving witness may be on a different fork
- This allows LIB to advance between blocks, not just when blocks are applied

### Irreversibility Propagation

**`migrate_irreversible_state()`** (`database.cpp:3066-3097`):

When LIB advances from `old_lib` to `new_lib`:

1. **Move blocks to block log**: `_block_writer->store_block(new_lib, head_block_num)`
   - Walks fork DB from old_lib+1 to new_lib on the main branch
   - Appends each block to the block log file
   - Flushes head storage

2. **Commit state**: `commit(new_lib)`
   - Deletes undo data for all blocks ≤ new_lib
   - State changes become permanent and irreversible

3. **Trim fork DB**: `_fork_db.set_max_size(head - new_lib + 1)`
   - Removes blocks older than new_lib from both linked and unlinked indices

4. **Notifications**:
   - `get_comments_handler().on_irreversible_block(new_lib)` — comment system marks posts permanent
   - `notify_irreversible_block(i)` for each block from old_lib+1 to new_lib — plugin notifications

5. **Clean fast-confirm map**: Remove entries for blocks ≤ new_lib

---

## Participation Tracking

### Mechanism

The `dynamic_global_property_object` tracks participation via:
- `recent_slots_filled` — 128-bit circular buffer (1 = block produced, 0 = missed)
- `participation_count` — running count of 1-bits (0-128)
- `current_aslot` — absolute slot number since genesis

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

The witness plugin checks this against `_required_witness_participation` before producing a block. If participation drops too low, witnesses stop producing (safety mechanism).

---

## Block Log

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
- Files: `block_log` (monolithic) or `block_log_part.XXXX` (split)

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

Total per-block entry size: 8 + 16 = 24 bytes. Artifacts can be regenerated from the block log if missing or corrupted.

### Compression

- **Algorithm**: ZSTD (Zstandard) — `block_log_compression.cpp`
- **Default level**: 15
- **Custom dictionaries**: Pre-trained for Hive block patterns, stored in `block_compression_dictionaries.cpp`
- **Optimization**: Magicless format, no content size flag, no checksum (all save space)
- **Performance**: ~3.5ms compression, ~65μs decompression per block

### Split Block Log

Large block logs are split into part files for filesystem manageability:

- **Naming**: `block_log_part.0001` through `block_log_part.9999`
- **Size**: `BLOCKS_IN_SPLIT_BLOCK_LOG_FILE` — 1,000,000 blocks per file (mainnet)
- **Implementation**: `split_block_log.cpp` reads monolithic log in batches (`BLOCKS_IN_BATCH_IO_MODE` = 10,000) and distributes to part files
- **First block of part N**: `(N-1) * 1,000,000 + 1`

### Read Operations

**By block number** (`block_log.cpp:491-515`):
1. Check if block_num is in range and not the cached head
2. Look up position and attributes in artifacts file
3. Read raw bytes from block log at that offset
4. Decompress if needed (check `is_compressed` flag)
5. Return `full_block_type`

**Batch read** for efficiency:
- `multi_read_raw_block_data()` reads a range of blocks in a single I/O operation
- Queries artifacts for all blocks in range
- Single `pread()` from first block to end of last block

---

## Key Discoveries

1. **Fast confirms never enter blocks**: The `witness_block_approve_evaluator::do_apply()` always asserts false. These transactions are processed entirely out-of-band via `process_fast_confirm_transaction()`, which updates an in-memory map and immediately re-checks LIB.

2. **LIB can trigger fork switches**: If 75% of witnesses approve blocks on a fork different from the current main chain, and that fork is at least as long, the node will switch forks to follow the irreversible chain. This is a safety mechanism — irreversibility overrides the longest-chain rule.

3. **Block application is fully atomic**: No per-transaction undo sessions during block application. The comment in code explicitly states: "We do not need to push the undo state for each transaction because they either all apply and are valid or the entire block fails to apply."

4. **Known bad merkle roots are tolerated**: `shared_db_merkle` map contains block numbers with known incorrect merkle roots from historical chain data. These are accepted to maintain replay compatibility.

5. **The future witness schedule (HF26+) fixes a subtle bug**: Before HF26, the irreversibility check used the current schedule. After HF26, it uses the future schedule via `get_witness_schedule_object_for_irreversibility()`, fixing timing edge cases in timeshare witness scheduling (referenced as HF27 fix).

6. **Participation safety**: If participation rate drops below a configurable threshold, witnesses stop producing blocks entirely. The `recent_slots_filled` 128-bit register provides a 6.4-minute rolling window.

7. **Post-HF17: No more PoW miners**: `HIVE_MAX_MINER_WITNESSES_HF17 = 0`. The timeshare slot is now the sole entry point for non-top-20 witnesses, selected via virtual time fair queuing.

8. **XORshift shuffle is deterministic but non-trivially manipulable**: Seeded by `head_block_time << 32`, the shuffle changes every 21 blocks. A witness can't choose their position in the next round because the seed depends on the previous round's timing.

9. **Fork DB default capacity is 1024 blocks**: This limits the maximum reorg depth. Combined with 3-second blocks, this is ~51 minutes of potential reorg (though in practice LIB advances every few minutes).

10. **Block production has a 750ms lag tolerance**: If a witness is more than 750ms late for their slot, they skip production for that slot to avoid causing chain confusion.

---

## Code References

| Component | File | Key Methods/Lines |
|-----------|------|-------------------|
| Block application | `database.cpp` | `_apply_block()` :2183-2369, `validate_block_header()` :2757-2779 |
| Transaction application | `database.cpp` | `_apply_transaction()` :2644-2702, `validate_transaction()` :2521-2642 |
| Operation dispatch | `database.cpp` | `apply_operation()` :2722-2746 |
| Witness scheduling | `witness_schedule.cpp` | `update_witness_schedule4()` :152-396, shuffle :372-388 |
| Slot mapping | `database.cpp` | `get_scheduled_witness()` :904-910, `get_slot_at_time()` :937-943 |
| Missed blocks | `database_witness.cpp` | `update_witness_missed_blocks()` :284-306 |
| Participation | `database.cpp` | `update_global_dynamic_data()` :2789-2841, `witness_participation_rate()` :531-535 |
| Fork DB | `fork_database.cpp` | `_push_block()` :73-99, `pop_block()` :20-28, `fetch_branch_from()` :290-330 |
| Fork switch | `sync_block_writer.cpp` | `switch_forks()` :162-264 |
| LIB calculation | `database.cpp` | `update_last_irreversible_block()` :2956-3064 |
| LIB determination | `sync_block_writer.cpp` | `find_new_last_irreversible_block()` :266-367 |
| Fast confirm | `database.cpp` | `process_fast_confirm_transaction()` :2899-2954 |
| Irreversibility | `database.cpp` | `migrate_irreversible_state()` :3066-3097 |
| Block log append | `block_log.cpp` | `append_raw()` :338-366 |
| Block log read | `block_log.cpp` | `read_block_by_num()` :491-515 |
| Block log artifacts | `block_log_artifacts.cpp` | header :46-69, chunk :82-166 |
| Witness plugin | `witness_plugin.cpp` | `schedule_production_loop()` :369-380, `block_production_loop()` :382-467 |
| Block producer | `block_producer.cpp` | `_generate_block()` :31-85, `apply_pending_transactions()` :111-216 |
| Global properties | `global_property_object.hpp` | Full struct definition |
| Flow control | `block_flow_control.hpp` | Phase enum :135-146 |

---

## Discrepancies and Potential Issues

1. **`update_signing_witness` aslot calculation seems redundant**: It calculates `new_block_aslot = dpo.current_aslot + get_slot_at_time(new_block.timestamp)`, but `current_aslot` was already updated in `update_global_dynamic_data()` to include the block's slot. This may double-count, though it's used only for `last_aslot` tracking on the witness object, not for consensus-critical decisions.

2. **Known bad merkle map is a consensus escape hatch**: `shared_db_merkle` allows blocks with incorrect merkle roots to be accepted. This is necessary for replay but means historical data integrity has known exceptions.

3. **Fork switch error recovery is asymmetric**: If applying the new fork fails and the old fork was shorter, the code does NOT attempt to revert (would be going to a shorter chain). This means the node gets stuck — the exception propagates and the node likely needs manual intervention.

4. **Fast confirm TaPoS skip**: Fast confirms intentionally skip TaPoS validation because the approving witness may reference a block on a different fork. This is by design but means fast confirms have weaker structural validation than normal transactions.

---

## Open Questions

1. **What exactly is `queen_mode`?** The witness plugin references `_queen_mode` which bypasses the witness identity check. Appears to be a testing/special mode but needs more investigation.

2. **How does the P2P layer prioritize fast-confirm transactions?** They appear to be processed outside the normal transaction pipeline, but the P2P propagation path wasn't fully traced.

3. **What is the exact split block log migration path?** When transitioning from monolithic to split format on a running node, what's the procedure?

4. **Block flow control phases**: The `generate_block_flow_control` and `p2p_block_flow_control` have different phase progressions. The exact interaction between these and the chain plugin thread model needs further investigation.

5. **Undo stack depth limits**: `HIVE_MAX_UNDO_HISTORY` is checked but the actual limit value and behavior when exceeded (besides assertion failure) needs verification.
