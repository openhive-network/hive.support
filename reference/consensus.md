# Hive Consensus Mechanisms Reference

Source: hive-core release 1.28.8.

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
3. Update the virtual times of the witnesses step 2 went through (the chosen one included); on overflow reset all virtual times
4. Shuffle the 21 witnesses using a deterministic Fisher-Yates shuffle with XORshift PRNG seeded by `head_block_time << 32`
5. Compute median witness properties (account creation fee, max block size, HBD interest rate, account subsidy budget/decay)
6. After HF26: two schedules are maintained (current + future); the future schedule is pre-computed so the next round is known one round in advance

**Slot-to-witness mapping:** `current_shuffled_witnesses[current_aslot % num_scheduled_witnesses]` (21 on mainnet, `database.cpp:913-919`) where `current_aslot` is the absolute slot number since genesis (includes missed slots).

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
9. **Blockchain processing** (order is consensus-critical): null account clearing, treasury consolidation, inflation distribution, HBD conversions, comment cashout, power-down payments, savings withdrawals, subsidized accounts, liquidity reward (no-op since HF12), virtual supply update, account recovery processing, escrow ratification expiry, declined voting rights, DHF proposal payments, delayed voting, expired governance votes, recurrent transfers, RC expired delegations, RC finalization, hardfork activation check
10. **Finalization** -- notify plugins, migrate irreversible state to block log

---

## Fork Resolution

The fork database is an in-memory structure tracking competing chain tips. Its window is the member `_max_size`: **1024 blocks** at start, then set to head - LIB + 1 after every applied block and every accepted fast confirm, so it has no fixed 1024 cap (in normal validation head - LIB stays below `HIVE_MAX_UNDO_HISTORY`, `database.cpp:2870-2877`; Part 06, section Undo History and Reorg Depth Limits); `MAX_BLOCK_REORDERING` (1024) is declared but used by no code (Part 06, sections Fork Database Structure and Undo History and Reorg Depth Limits).

**Longest chain rule:** The fork DB head always points to the block with the highest block number. When a new block extends a different fork than the current head:

1. Find common ancestor by walking both branches backward
2. Pop the old fork (reverse state changes via undo stack, recover transactions into `_popped_tx`)
3. Apply new fork blocks from oldest to newest
4. If applying the new fork fails: the failed block and the rest of the new branch are removed from the fork DB; the node reverts to the old branch only when an irreversibility test against the common ancestor passes and the chain is shorter than where it started (`sync_block_writer.cpp:236-237`); the exception is rethrown in every case (Part 06, section Fork Switch, step 5, and its Discrepancies item 3)

**Key behaviors:**
- Unlinked (orphan) blocks are stored separately until their parent arrives
- A block below the fork-DB window (too old) is rejected as *unlinkable*, not invalid (since 1.28.7): the peer keeps its connection and the block is reconciled through normal sync, instead of being disconnected as if it had relayed a bad block (at 1.28.7 for blocks delivered live; since 1.28.8 also for sync blocks, and the net layer's disconnect rules for rejected blocks changed; node policy, Part 06, section Fork Resolution: Longest Chain Rule)
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
1. Blocks from old LIB+1 to new LIB are appended to the block log, and the fork DB is trimmed to `head - new_LIB + 1` blocks (this trim runs after every applied block and every accepted fast confirm)
2. Undo data for those blocks is deleted (state becomes permanent)
3. Plugins are notified for each newly irreversible block

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
| Compression time (code comment) | ~3.5 ms at level 15, from tests around block 63M; the comment does not say per what |
| Decompression time (code comment) | ~65 us, same comment |
| Split file size | 1,000,000 blocks per part file (400 in `IS_TEST_NET` builds, `block_log.hpp:8-16`) |
| Split file naming | `block_log_part.0001` through `block_log_part.9999` |
| Batch I/O size | 10,000 blocks (400 in `IS_TEST_NET` builds) |

**Participation tracking:** A 128-bit shift register (`recent_slots_filled`) tracks produced vs. missed blocks over the last 128 slots (~6.4 minutes). Witnesses stop producing if the participation rate drops below the configured threshold (witness plugin default 33%).
