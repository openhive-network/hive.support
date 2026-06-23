# HAF Part 06 - sql_serializer Indexing Internals

**Anchor:** HAF `1.28.6` (`222c848355`).
**Scope:** the C++ internals of the `sql_serializer` plugin - the in-memory cache, the
per-type processor threads, the two dumpers, the write-ahead log, and index/constraint
management for bulk load. Builds on the part-01 dataflow (signals, sync modes); the SQL
target tables are part 02/04.

Paths relative to `src/sql_serializer/`; headers under
`include/hive/plugins/sql_serializer/`.

---

## 1. The pipeline

```
hived signals ──> cache (cached_data_t) ──> flush trigger (mode) ──> dumper
                                                                       │
                       WAL (durability)                    per-type data_processor threads
                                                                       │
                                                                  Postgres (hafd.*)
```

The plugin (`sql_serializer_plugin_impl`, part 01) gathers each block's data into an
in-memory cache; a mode-specific flush trigger decides when to dump; a dumper converts the
cache to SQL using a pool of worker threads; and a write-ahead log guarantees no block is
lost between hived and Postgres.

---

## 2. The cache (`cached_data.h`)

`cached_data_t` (`cached_data.h:6`) is the per-batch accumulator - parallel vectors, one per
entity:

`transactions` (`:9`), `operations` (`:11`), `accounts` (`:12`), `account_operations`
(`:13`), `applied_hardforks` (`:14`) (plus blocks). It pre-reserves space
(`cached_data_t(reservation_size)`, `:30`) and tracks `total_size` for flush sizing. The
cache is owned as `cached_containter_t = std::unique_ptr<cached_data_t>` (`:77`), so a full
cache is handed off to the dumper by moving the pointer.

---

## 3. The processor model (`data_processor.hpp`)

`data_processor` (`data_processor.hpp:21`) is a **single dedicated worker thread** fed
chunks of one data kind:

- Constructed with a `data_processing_fn`
  (`std::function<data_processing_status(data_chunk_ptr)>`, `:36`) - the convert+write step -
  and a `block_num_rendezvous_trigger` (`:38`).
- `trigger(data_chunk_ptr, last_blocknum)` (`:46`) hands a chunk to the thread (async);
  `complete_data_processing()` (`:50`) blocks the caller until the thread has consumed it;
  `join()` (`:52`) shuts it down.

The concurrency model: **one processor per data type**, so blocks, transactions, operations,
and account_operations are converted to SQL and written **in parallel**, and the dumper
`trigger`s them all then waits on the rendezvous.

---

## 4. The two dumpers

Both implement `data_dumper` (`data_dumper.h`); the mode picks which (part 01).

### `reindex_data_dumper` (MASSIVE / replay) - `reindex_data_dumper.h:17`

Converts the cache to **direct table `INSERT`s** with the heaviest types split across
threads:

- blocks: a single `table_data_writer<hive_blocks>` (`:41`),
- transactions / operations / account_operations: a
  `chunks_for_sql_writers_splitter<table_data_writer<...>>` (`:42`) - the splitter slices the
  container and runs multiple `table_data_writer`s concurrently (each `container_view` gets a
  chunk). Bulk insert, maximum parallelism.

### `livesync_data_dumper` (LIVE) - `livesync_data_dumper.h`

Converts to a form compatible with the **`hive.push_block` procedure** and writes it in **one
transaction** (so the fork-manager sees a coherent block), with multithreaded string
building (part 01, `dataflow.txt`). So live sync goes through the fork-aware SQL path; replay
bypasses it with raw inserts.

---

## 5. The write-ahead log (`write_ahead_log.hpp`)

The WAL exists because there is a window between hived finishing a block and Postgres
committing its data (`write_ahead_log.hpp:13-26`): if power fails in that window, hived
restarts at block `x+1` and block `x`'s data is never written - silent desync. The WAL
persists the collected data first, so on restart `replay_wal_if_necessary`
(`sql_serializer.cpp:514`) re-applies anything not yet committed. The comment notes this is
**far worse in massive/p2p sync** (many blocks at once - a crash would otherwise force a full
replay). So the WAL is the crash-consistency guarantee for hived<->Postgres.

---

## 6. Index & constraint management (`indexes_controler.h`)

Bulk inserting into indexed tables is slow, so for big batches HAF drops and rebuilds
(`indexes_controler.h:15`):

- `disable_indexes_depends_on_blocks(n_blocks)` (`:18`) / `enable_indexes()` (`:19`) - drop
  indexes before a large insert, recreate after,
- `disable_constraints(n_blocks)` (`:20`) / `enable_constrains()` (`:21`) - same for FK
  constraints,
- gated by `_psql_index_threshold` (`:31`) - only worth it above N blocks,
- `poll_and_create_indexes()` (`:22`) rebuilds indexes (pollable / interruptible via
  `indexes_interruptor`).

This is the classic fast-bulk-load pattern, applied automatically during massive sync and
skipped for small live batches.

---

## 7. Supporting machinery

- `accounts_collector` / `all_accounts_dumper` - collect/dump the account set (feeds the
  accounts state provider, part 04).
- `vacuum_cleaner.h` - vacuums the shadow/undo tables (the `last_shadow_vacuum_block` in the
  loop state, part 03).
- `blockchain_data_filter` / `filter_collector` - operation/account filtering of what gets
  indexed (part 07).
- `end_massive_sync_processor` - the transition out of MASSIVE mode (move-to-irreversible,
  re-enable indexes).
- `block_num_rendezvous_trigger` - the barrier the processors sync on per flush.

---

## 8. Notable findings

1. **One worker thread per data type** (`data_processor`) - blocks/transactions/operations/
   account_operations convert and write concurrently; the dumper fans out and joins on a
   rendezvous.
2. **Two write paths by mode**: replay uses raw multithreaded `INSERT`s
   (`reindex_data_dumper`, splitter), live uses the fork-aware `hive.push_block` in one
   transaction (`livesync_data_dumper`).
3. **The WAL is a real crash-consistency layer**, not a perf feature - it closes the
   hived-committed-but-Postgres-didn't window (`write_ahead_log.hpp:13-26`).
4. **Index/constraint drop-and-rebuild is automatic and threshold-gated**
   (`_psql_index_threshold`) - the reason massive sync is fast.
5. **The splitter (`chunks_for_sql_writers_splitter`)** parallelizes only the high-volume
   tables; blocks (one per block) use a single writer.

---

## 9. Code References

| Topic | File:line |
|-------|-----------|
| cache structure | `include/.../cached_data.h:6-14`,`:30`,`:77` |
| processor (worker thread) | `include/.../data_processor.hpp:21`,`:36`,`:46-52` |
| reindex dumper (splitter) | `include/.../reindex_data_dumper.h:17`,`:41-42` |
| livesync dumper | `include/.../livesync_data_dumper.h`; `dataflow.txt` |
| write-ahead log + rationale | `include/.../write_ahead_log.hpp:13-26`; WAL replay `sql_serializer.cpp:514` |
| index/constraint controller | `include/.../indexes_controler.h:15-22`,`:31` |
| sync-mode flush triggers | `indexation_state.cpp:75`,`:91`,`:103`,`:135` (part 01) |
| supporting (vacuum, collectors, filter) | `include/.../{vacuum_cleaner,accounts_collector,blockchain_data_filter}.h` |

---

## 10. Open Questions (for later parts / zoom)

- **`data_2_sql_tuple_base` / `pqxx_conversions`** - the exact cache-row -> SQL-literal
  conversion and escaping.
- **The splitter's chunking math** - how `chunks_for_sql_writers_splitter` decides thread
  count and chunk boundaries.
- **WAL format** - what exactly is persisted and the replay protocol on restart.
- **`end_massive_sync_processor`** - the precise MASSIVE -> P2P/LIVE transition steps.
- **Filtering** (`blockchain_data_filter`, `filter_collector`) - part 07.
