# Hive Consensus Mechanisms Reference

Source: hive-core at commit 44c3fd880.

---

## Block Production

A witness plugin polls every 200ms to check if it is the scheduled producer for the current slot.

1. Convert current time to slot number (`get_slot_at_time`)
2. Look up scheduled witness for that slot (`get_scheduled_witness`)
3. Verify private signing key is available for that witness
4. Check participation rate meets minimum threshold
5. Assemble pending transactions into a block (iterate `_pending_tx`, skip expired/oversized, re-validate each in an undo session)
6. Sign the block (signing key must match the witness's on-chain `signing_key`)
7. Push block into fork database (may trigger fork switch)
8. Broadcast block via P2P
9. If HF26+ and other local witnesses are configured, broadcast fast-confirm transactions

| Parameter | Value |
|-----------|-------|
| Block interval | 3 seconds (`HIVE_BLOCK_INTERVAL`) |
| Production poll interval | 200ms |
| Max acceptable production lag | 750ms |
| Time buffer added to "now" | 500ms |
| Max block size | Governed by `gprops.maximum_block_size` (median of witness votes) |

---

## Witness Schedule

Each round consists of 21 witnesses. The schedule is recalculated every 21 blocks (~63 seconds).

| Category | Count (post-HF17) | Selection |
|----------|-------------------|-----------|
| Elected (top voted) | 20 | Highest approval votes from `by_vote_name` index |
| Timeshare (runner-up) | 1 | Virtual-time fair queuing from `by_schedule_time` index |
| Miner (PoW) | 0 | Removed at HF17 |

**Schedule recalculation steps:**

1. Select top 20 elected witnesses (skip disabled -- empty signing key)
2. Select 1 timeshare witness via virtual-time scheduling (`virtual_scheduled_time = last_update + (LAP_LENGTH - position) / (votes + 1)`)
3. Update all witnesses' virtual times; reset on overflow
4. Compute median witness properties (account creation fee, max block size, HBD interest rate, account subsidy budget/decay)
5. Shuffle the 21 witnesses using a deterministic Fisher-Yates shuffle with XORshift PRNG seeded by `head_block_time << 32`
6. After HF26: two schedules are maintained (current + future); the future schedule is pre-computed so the next round is known one round in advance

**Slot-to-witness mapping:** `scheduled_witnesses[current_aslot % 21]` where `current_aslot` is the absolute slot number since genesis (includes missed slots).

**Voting:** Approval voting; each account votes for up to 30 witnesses, weighted by governance vote power (vesting shares).

---

## Block Application Sequence

When a node receives a block, `_apply_block()` executes these phases in consensus-critical order:

1. **Pre-block setup** -- notify plugins, reset RC block info, store block metadata
2. **Genesis processing** (block 1 only) -- create genesis accounts, apply all hardforks up to genesis time
3. **Merkle root validation** -- recompute from transactions, assert match (known historical exceptions tolerated)
4. **Block header validation:**
   - Chain continuity: `head_block_id == block.previous`
   - Timestamp monotonicity: `head_block_time < block.timestamp`
   - Witness signature matches on-chain signing key
   - Slot is valid and witness matches schedule
5. **Block size validation** (post-HF12) -- block size must not exceed `gprops.maximum_block_size`
6. **Witness hardfork version check** (post-HF5.54) -- witness must run current hardfork version
7. **Transaction application** -- each transaction applied sequentially; entire block is atomic (no per-tx undo sessions)
8. **Global state updates** -- head block, participation, aslot, signing witness stats, LIB advancement, TaPoS summaries, expired tx/order/delegation cleanup, witness schedule, median feed, virtual supply
9. **Blockchain processing** (order is consensus-critical): null account clearing, treasury consolidation, inflation distribution, HBD conversions, comment cashout, power-down payments, savings withdrawals, subsidized accounts, DHF proposal payments, delayed voting, expired governance votes, recurrent transfers, RC finalization, hardfork activation check
10. **Finalization** -- notify plugins, migrate irreversible state to block log

---

## Fork Resolution

The fork database is an in-memory structure tracking competing chain tips, with a default capacity of **1024 blocks** (~51 minutes at 3s/block).

**Longest chain rule:** The fork DB head always points to the block with the highest block number. When a new block extends a different fork than the current head:

1. Find common ancestor by walking both branches backward
2. Pop the old fork (reverse state changes via undo stack, recover transactions into `_popped_tx`)
3. Apply new fork blocks from oldest to newest
4. If applying the new fork fails: mark failed blocks invalid; re-apply old fork if it was at least as long

**Key behaviors:**
- Unlinked (orphan) blocks are stored separately until their parent arrives
- Fork switch errors on a shorter old fork are fatal (cannot safely revert)
- LIB advancement can force a fork switch if 75% of witnesses approve blocks on a non-main fork

---

## Irreversibility

A block becomes irreversible (Last Irreversible Block / LIB) when 75% of scheduled witnesses have approved it.

| Parameter | Value |
|-----------|-------|
| Irreversibility threshold | 75% of scheduled witnesses |
| Required approvals (21 witnesses) | 16 of 21 |
| Early phase rule (before block 864,000) | LIB = head - 21 |

**Witness approval sources** (higher of the two counts):
- **Implicit:** Producing a block approves all ancestor blocks
- **Explicit (HF26+ fast confirm):** `witness_block_approve_operation` approves a specific block ID

**Fast confirm details:**
- Processed out-of-band via P2P, never included in blocks (the evaluator always asserts false)
- TaPoS is skipped (approving witness may be on a different fork)
- Immediately triggers LIB recalculation -- LIB can advance between blocks
- Stored in an in-memory map (`_last_fast_approved_block_by_witness`)

**When LIB advances:**
1. Blocks from old LIB+1 to new LIB are appended to the block log
2. Undo data for those blocks is deleted (state becomes permanent)
3. Fork DB is trimmed to `head - new_LIB + 1`
4. Plugins are notified for each newly irreversible block

---

## Block Log

The block log is the append-only on-disk archive of irreversible blocks.

**On-disk format:**
- Each block is serialized (optionally ZSTD-compressed at level 15), followed by 8 bytes: 48-bit file offset + compression flags
- Last 8 bytes of the file point to the head block, enabling backward traversal

**Artifacts file** (`.artifacts`) provides O(1) random access by block number:
- 24 bytes per block: 48-bit offset, compression dictionary number, compressed flag, stripped block ID
- Can be regenerated from the block log if corrupted

| Parameter | Value |
|-----------|-------|
| Compression algorithm | ZSTD (magicless, no checksum) |
| Default compression level | 15 |
| Typical compression time | ~3.5ms per block |
| Typical decompression time | ~65us per block |
| Split file size | 1,000,000 blocks per part file |
| Split file naming | `block_log_part.0001` through `block_log_part.9999` |
| Batch I/O size | 10,000 blocks |

**Participation tracking:** A 128-bit circular buffer (`recent_slots_filled`) tracks produced vs. missed blocks over ~6.4 minutes. Witnesses stop producing if the participation rate drops below the configured threshold.
