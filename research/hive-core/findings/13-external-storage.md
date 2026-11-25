# Findings: external-storage

**Area:** `libraries/chain/external_storage/` (+ headers in `libraries/chain/include/hive/chain/external_storage/`)
**Pinned SHA:** `274384a8adddf54b69965a7fd43d8eb0ddda7701` (release 1.28.8)
**All `file:line` references are relative to the worktree at that SHA.**

## Summary

The `external_storage` subsystem is the 1.28 mechanism that moves consensus data out of chainbase shared memory into RocksDB. Its primary client is the **comment archive**: once a comment's cashout becomes irreversible, the `comment_object` is deleted from the SHM `comment_index` and (in the default ROCKSDB mode) persisted as a hash-keyed RocksDB record, with all consensus lookups transparently falling through to the archive. The same directory also hosts the **shared RocksDB provider infrastructure** (base storage provider, comparators, write-batch types, snapshot backup/restore, fd-limit management) that the `account_history_rocksdb` plugin builds on — so this area is the common foundation for *all* RocksDB use in hived.

## Key Discoveries

### 1. Mainnet builds have no archive choice — ROCKSDB is compiled in as the only mode
- **What**: The `comment-archive` config option (NONE/MEMORY/ROCKSDB) is registered only under `#ifdef USE_ALTERNATE_CHAIN_ID` (`chain_plugin.cpp:1539-1541`), which is defined only for `BUILD_HIVE_TESTNET` or `HIVE_CONVERTER_BUILD` (mirrornet) builds (`cmake/hive_options.cmake:31-36`). On a mainnet build the option does not exist; the parse falls through to the default string `"ROCKSDB"` (`chain_plugin.cpp:1604-1612`) and the default enum value (`chain_plugin.cpp:176`).
- **Where**: `libraries/plugins/chain/chain_plugin.cpp:1539-1541`, `cmake/hive_options.cmake:31-36`
- **Impact**: NONE and MEMORY are test-infrastructure modes. Every mainnet 1.28.8 node runs the RocksDB comment archive; there is no supported way to opt out. Part 05, section "Comment Archive and External Storage (RocksDB)", describes the same compile gate.

### 2. The two-phase migration protocol: volatile object under undo → RocksDB at LIB
- **What**: On cashout, the ROCKSDB archive does **not** write to RocksDB. It creates a `volatile_comment_object` in chainbase (under undo) recording `{comment_id, parent_comment, depth, hash, block_number}` (`rocksdb_comment_archive.cpp:51-59`). Only when the cashout block is irreversible does `on_irreversible_block` serialize each volatile entry with `block_number <= LIB` into RocksDB and remove *both* the volatile object and the original `comment_object` from chainbase (`rocksdb_comment_archive.cpp:100-141`). Fork switches before irreversibility simply roll the volatile object back with normal undo.
- **Where**: `libraries/chain/external_storage/rocksdb_comment_archive.cpp:35-141`
- **Impact**: RocksDB only ever receives irreversible data; reversible state stays entirely inside chainbase. This is the core invariant that makes an external non-undoable store safe to use for consensus data.

### 3. Deliberate undo asymmetry: ROCKSDB migration is undoable, MEMORY migration is not
- **What**: When migrating at LIB, `rocksdb_comment_archive` removes the comment with plain `db.remove()` (`rocksdb_comment_archive.cpp:131-132`) — the removal is recorded in the head block's undo session — while `memory_comment_archive` uses `db.remove_no_undo()` (`memory_comment_archive.cpp:44`), the **only** caller of that chainbase facility in the entire codebase. The ROCKSDB variant must stay undoable: if a pop restores the (undo-tracked) `volatile_comment_object`, the `comment_object` must come back too, or re-archival would hit `FC_ASSERT( _comment )` (`rocksdb_comment_archive.cpp:128-129`). The MEMORY variant tolerates the asymmetry because its lookup falls through to the SHM archive copy and its LIB processing skips already-missing comments (`memory_comment_archive.cpp:40-41`).
- **Where**: `rocksdb_comment_archive.cpp:126-132` vs `memory_comment_archive.cpp:43-44`; chainbase warning comment `libraries/chainbase/include/chainbase/util/object.hpp:26-35`
- **Impact**: A pop of the block whose application advanced LIB temporarily restores already-archived comments into `comment_index` (ROCKSDB mode); lookups still resolve correctly because the live index is checked first, and re-archival is an idempotent overwrite of the same RocksDB key. The unit test `fork_reverts_cashout` encodes exactly this contract: `migrate=true, undoable_migration=true` for ROCKSDB, `migrate=true, undoable_migration=false` for MEMORY (`tests/unit/tests/comments_in_external_storage.cpp:413-418`, scenario at `:239-411`).

### 4. SHM↔RocksDB consistency is enforced by a LIB cross-check at every open
- **What**: The provider caches the last irreversible block both in memory and as a RocksDB record (key `LIB_ID` = uint32 `0`). `openDb(expected_lib)` is passed `db.get_last_irreversible_block_num()` from shared memory (`rocksdb_comment_archive.cpp:187`), and `load_lib()` asserts the stored value matches: fresh DB requires SHM LIB == 0 (`rocksdb_storage_provider.cpp:335-342`), existing DB requires exact equality (`rocksdb_storage_provider.cpp:348-353`). The failure message explicitly mentions stale Linux page cache after ZFS/LVM snapshot rollback and recommends `echo 3 > /proc/sys/vm/drop_caches`.
- **Where**: `libraries/chain/external_storage/rocksdb_storage_provider.cpp:330-356`
- **Impact**: Mixing a shared_memory.bin with a comment archive from a different point in time is detected at startup and refuses to run (forcing replay), instead of silently producing divergent consensus lookups. Both assert conditions (`lib == _cached_irreversible_block`, `0 == _cached_irreversible_block`) are pinned by the `inconsistent_comment_archive` unit test, which compares them with `fc::last_assert_expression`, not the message texts (`tests/unit/tests/comments_in_external_storage.cpp:420-483`, `tests/unit/db_fixture/database_fixture.hpp:65-69`).

### 5. Comment puts and the LIB record ride the same atomic WriteBatch
- **What**: `update_lib()` does not write to the DB directly - it Puts the new LIB into the same `WriteBatch` that accumulates archived-comment Puts (`rocksdb_storage_provider.cpp:358-363`). The batch is committed atomically by `flushWriteBuffer()` (`rocksdb_storage_provider.cpp:259-266`), called at the end of each LIB migration round (`rocksdb_comment_archive.cpp:137`), directly by the periodic state flush (`flush(false)`, `rocksdb_comment_archive.cpp:211-212`), and through `flushDb()` (`rocksdb_storage_provider.cpp:280-286`) on the forced flushes at close and end of syncing (`flush(true)`, `rocksdb_comment_archive.cpp:209-210`), on snapshot dump (`rocksdb_snapshot.cpp:55`) and in `shutdownDb()` (`rocksdb_storage_provider.cpp:98`). At 1.28.7 the periodic state flush also went through `flushDb()`.
- **Where**: `rocksdb_storage_provider.cpp:259-266, 358-372`
- **Impact**: After a crash, RocksDB's stored LIB always corresponds exactly to the comment set it contains (single atomic batch). Any divergence from SHM is caught by discovery #4. `update_lib` additionally asserts `_initialized` so a LIB update can never precede `openDb` (`rocksdb_storage_provider.cpp:365-372`).

### 6. Column-family layout is semantically inverted relative to its names
- **What**: The comment DB declares CFs `["default", "account_permlink_hash"]` (`rocksdb_comment_storage_provider.cpp:13-25`). But `save()`/`read()` use `_columnHandles[CommentsColumns::COMMENT]` where `COMMENT = 0` → comment records (20-byte ripemd160 keys) actually live in the **default** CF (`rocksdb_storage_provider.cpp:316-328`, enum `types.hpp:31-34`), while the base class hardcodes the LIB record into `_columnHandles[Columns::CURRENT_LIB]` where `CURRENT_LIB = 1` → the CF *named* `account_permlink_hash` (`rocksdb_storage_provider.cpp:333, 361`; enum `types.hpp:36-44`). The `by_Hash_Comparator` assigned to that CF (`rocksdb_comment_storage_provider.cpp:20-22`) therefore only ever compares the single 4-byte LIB key (harmless — it falls back to bytewise compare).
- **Where**: `types.hpp:31-44`, `rocksdb_storage_provider.cpp:316-328`, `rocksdb_comment_storage_provider.cpp:13-25`
- **Impact**: Functionally correct but confusing: anyone inspecting the SST files will find comments under `default` and the LIB under `account_permlink_hash`. The `Columns` enum (values 1-6) is really the **account-history** CF layout (matching `rocksdb_ah_storage_provider::prepareColumnDefinitions`, `libraries/plugins/account_history_rocksdb/rocksdb_ah_storage_provider.cpp:61-90`), reused by the shared base class for its LIB logic; it only lines up with the comment DB by coincidence of index 1 existing.

### 7. RocksDB read errors are indistinguishable from "comment does not exist"
- **What**: `rocksdb_storage_provider::read()` returns `s.ok()` (`rocksdb_storage_provider.cpp:322-328`); `get_comment_impl` maps `false` to a null result (`rocksdb_comment_archive.cpp:82-98`), and `get_comment` then either returns empty or throws "Comment ... not found" (`rocksdb_comment_archive.cpp:164-169`). Unlike the AH-side `CachableWriteBatch::getAHInfo`, which asserts `s.IsNotFound()` on the non-OK path (`types.cpp:65`), an I/O error or corruption status here is silently treated as not-found.
- **Where**: `rocksdb_storage_provider.cpp:322-328` vs `types.cpp:47-67`
- **Impact**: A disk-level read failure during block application would make an existing archived comment invisible to consensus (e.g. a reply to it would be rejected), i.e. a local I/O fault converts into consensus divergence instead of a crash. Low probability, but the asymmetry with the AH code path looks unintentional. Flagged under Discrepancies.

### 8. Sync batching: 10,000-object threshold, dropped to 0 when live
- **What**: During sync/replay, LIB migration only runs once ≥ 10,000 volatile objects accumulate (`volatile_objects_limit`, `rocksdb_comment_archive.hpp:16`, check at `rocksdb_comment_archive.cpp:109-110`). When the node reaches live sync, `notify_end_of_syncing` → `on_end_of_syncing` sets the limit to 0 (`database.cpp:873`, `rocksdb_comment_archive.cpp:215-219`), so every subsequent LIB advance migrates immediately.
- **Where**: `rocksdb_comment_archive.cpp:100-141, 215-219`; `database.cpp:861-876`
- **Impact**: Avoids per-block RocksDB write+flush overhead during replay (where LIB advances every block) while keeping the SHM footprint of pending volatile objects bounded; in live mode comments leave SHM as soon as their cashout is irreversible.

### 9. Archived comments are point-lookup-only, by hash — never by id, never enumerable
- **What**: The only retrieval path is `get_comment(author_id, permlink, required)` which computes `ripemd160(permlink + "@" + author_id)` (`comment_object.hpp:92-96` in `detail/state/`) and checks the live `by_permlink` index first, then the archive (`rocksdb_comment_archive.cpp:143-172`). The RocksDB value stores only `{comment_id, parent_comment, depth}` (`comment_rocksdb_objects.hpp:43-58`); the key is the hash. There is no id->hash mapping and no iteration API in `comments_handler` (`comments_handler.hpp:15-34`).
- **Where**: `rocksdb_comment_archive.cpp:82-98, 143-172`; `comment_rocksdb_objects.hpp:43-58`
- **Impact**: Any code holding only a `comment_id` cannot resolve an archived comment. Consensus never needs to (votes on paid comments are no-ops, cashout precedes archival), and APIs that resolve author+permlink (`database_api.get_comment_pending_payouts` → `database_api_content.cpp:25`; `condenser_api.get_active_votes` → `condenser_api.cpp:802`) keep working transparently. Replies to archived parents work because `depth`/`comment_id` survive in the archive (`hive_evaluator_social.cpp:185-191`).

### 10. The whole area is shared infrastructure with account_history_rocksdb
- **What**: `rocksdb_ah_storage_provider` derives from this area's `rocksdb_storage_provider` (`libraries/plugins/account_history_rocksdb/include/.../rocksdb_ah_storage_provider.hpp:13`), and the AH plugin instantiates this area's `rocksdb_snapshot` as `("Account History RocksDB", "account_history_rocksdb_data", ...)` (`account_history_rocksdb_plugin.cpp:120-121`). `types.hpp`/`types.cpp` carry the AH-specific machinery: the `Columns` CF enum, all comparators + their RocksDB ObjectRegistry registration (`types.cpp:84-149`), `operation_id_vop_pair` (63-bit op id + 1-bit virtual flag, `types.hpp:191-219`), `account_history_info` (`types.hpp:262-275`), and `CachableWriteBatch` (`types.hpp:283-298`, impl `types.cpp:47-82`). Chainbase even provides a generic `generic_index::move_to_external_storage` helper used by the AH plugin (`chainbase.hpp:459-488`; `account_history_rocksdb_plugin.cpp:1265`) — the comment archive implements its own equivalent loop instead.
- **Where**: `types.hpp`/`types.cpp` throughout; AH provider files cited above
- **Impact**: "external_storage" is not just the comment archive — it is hived's RocksDB platform layer. Future zooms on `account_history_rocksdb` should treat this area as their foundation. Store version constants `STORE_MAJOR_VERSION=1, STORE_MINOR_VERSION=1` (`types.hpp:21-22`) are shared by both databases (written/verified at `rocksdb_storage_provider.cpp:288-314`).

### 11. fd_budget raises the process FD soft limit before any RocksDB open
- **What**: `raise_fd_limit()` lifts `RLIMIT_NOFILE` soft -> `min(hard, 65536)`, warns below 8192, and is idempotent via `std::call_once` (`fd_budget.cpp:19-20, 40-83, 112-115`). Called from `openDb` and `createDbSchema` (`rocksdb_storage_provider.cpp:54, 145`) and three times by the state_snapshot plugin (`state_snapshot_plugin.cpp:296, 1025, 1177`). Since 1.28.8 `openDb` and `createDbSchema` then set a finite `max_open_files = max_open_files_budget()` (`rocksdb_storage_provider.cpp:62, 153`): (soft limit - 8192 headroom) / 4 expected stores when the soft limit exceeds 8192 + 4 x 256, else the floor 256 (also 256 when the limit cannot be read), capped at `INT_MAX` and logged at each open (`fd_budget.cpp:22-30, 117-147`); at a 65536 soft limit that is 14336 per store. At 1.28.7 `max_open_files` was left at RocksDB's default -1 (every table file kept open). Also since 1.28.8 every `flush_to_all_storages` call runs `report_fd_usage_if_needed()` (`database.cpp:2793`): once every 1200 calls (counted in calls, not time: roughly hourly at one flush per block, `fd_budget.cpp:34-36`) it counts the open descriptors in `/proc/self/fd` and warns when usage is at or above 70% of the soft limit, after the first warning only at a higher percentage than the last one (re-armed when usage falls below 70%) (`fd_budget.cpp:32-36, 149-188`).
- **Where**: `libraries/chain/external_storage/fd_budget.cpp`
- **Impact**: Operational: nodes with a low hard limit get a warning, not a failure; nothing else in the chain library manages FD limits.

## Architecture

### Class hierarchy

```
comments_handler (abstract; comments_handler.hpp:15-34)
 |- extends external_storage_snapshot (save/load_snapshot; external_storage_snapshot.hpp:10-18)
 |- placeholder_comment_archive   - comment-archive=NONE   (placeholder_comment_archive.hpp:9-32)
 |- memory_comment_archive        - comment-archive=MEMORY (memory_comment_archive.hpp:19-98)
 `- rocksdb_comment_archive       - comment-archive=ROCKSDB, default (rocksdb_comment_archive.hpp:12-45)
      |- owns rocksdb_comment_storage_provider (rocksdb_comment_storage_provider.hpp:19-38)
      |    |- extends rocksdb_storage_provider (rocksdb_storage_provider.hpp:33-106)
      |    |    `- implements external_basic_provider (openDb/shutdownDb/flushDb/flushWriteBuffer/flushStorage/wipeDb/LIB; external_basic_provider.hpp:11-34)
      |    `- implements external_comment_storage_provider (save/read; external_comment_storage_provider.hpp:12-20)
      `- owns rocksdb_snapshot ("Comments RocksDB", "comments_rocksdb_data"; rocksdb_comment_archive.cpp:27)
```

The `database` holds a `comments_handler_ptr` injected by the chain plugin before open (`database.hpp:860-880`, `chain_plugin.cpp:817-837`); `database::get_comments_handler()` asserts it was set (`database.hpp:877-880`). The `comment` value-type wrapper (`comment.hpp:8-24`) carries either a raw pointer into SHM or a `shared_ptr<comment_object>` heap reconstruction from RocksDB - callers use one type for both.

### Database integration points (lifecycle)

| Event | Call | Where |
|-------|------|-------|
| DB open (after SHM mapped, before genesis check) | `get_comments_handler().open()` | `database.cpp:186` (in `initialize_state_independent_data`) |
| Comment paid out (HF19+) | `on_cashout(block_num, comment, cashout)` | `database_comment.cpp:473` (`process_comment_cashout`) |
| HF19 activation (bulk) | `on_cashout` for every already-paid comment | `database_comment.cpp:94-113` (`remove_old_cashouts`, called from `database_hardfork.cpp:328`) |
| LIB advance (every applied block / fast-confirm) | `on_irreversible_block(new_lib)` | `database.cpp:3121` (in `migrate_irreversible_state`, called from `_apply_block` `database.cpp:2382` and fast-confirm `database.cpp:2990`) |
| Periodic state flush | `flush(false)` via `flush_to_all_storages(false)`; ROCKSDB: `flushWriteBuffer()` only (the write batch reaches the memtable and WAL, no column-family `Flush()`); the AH plugin's flush handler does the same | `database.cpp:2783-2794`, `rocksdb_comment_archive.cpp:202-213`, `account_history_rocksdb_plugin.cpp:1290-1300`; scheduled per `_flush_blocks` in `database::apply_block` (`database.cpp:2119-2133`): since 1.28.8 the next flush block is picked when a flush fires, in the last tenth of the interval (`schedule_next_flush_block`, `database.cpp:2765-2781`), so an interval of N gives gaps of at most N blocks (every block for N = 1); at 1.28.7 the block after a flush only rescheduled, so gaps were up to N+1 blocks (every second block for N = 1); interval `flush-state-interval` while syncing, `flush-state-interval-live` after the end of syncing (see Configuration) |
| End of syncing | `flush(true)` via `flush_to_all_storages(true)` (ROCKSDB: `flushDb()`), outside testnet builds the switch to the `flush-state-interval-live` interval, then `on_end_of_syncing()` | `database.cpp:861-876` (calls at `:863`, `:871`, `:873`); when it runs: Part 06, section "Chain Plugin Thread Model and Write Queues" |
| DB close (chain plugin shutdown, `chain_plugin.cpp:1972`) | `flush(true)` via `flush_to_all_storages(true)`, then `close()` (ROCKSDB: `shutdownDb()`, which runs `flushDb()` again and closes the DB) | `database.cpp:304-305`; `rocksdb_storage_provider.cpp:91-109` |
| Wipe (replay/resync/snapshot-load) | `wipe()` | `database.cpp:283`; triggered by `chain_plugin.cpp:955-956` |
| Snapshot dump/load | `save_snapshot`/`load_snapshot` | `state_snapshot_plugin.cpp:1535, 1409` |

All author+permlink lookups funnel through eight `database::get_comment`/`find_comment` overloads (`database.cpp:402-451`; the by-id accessors read chainbase only, `database_comment.cpp:46-49, 84-92`) - `get_*` passes `comment_is_required=true` (throws if missing), `find_*` passes `false` (returns empty wrapper).

## The Three Archive Implementations

### placeholder_comment_archive (NONE)
Pre-1.28 behavior: `on_cashout` only bumps a counter (`placeholder_comment_archive.cpp:10-14`); comments stay in `comment_index` forever; `get_comment` searches only the live index and throws/returns-empty otherwise (`placeholder_comment_archive.cpp:21-40`). All storage hooks are no-ops. Also hosts the definition of the shared static `comments_handler::stats` (`placeholder_comment_archive.cpp:8`).

### memory_comment_archive (MEMORY)
- Cashout bookkeeping is a **process-memory** map `block_num → [comment_ids]` (`memory_comment_archive.hpp:78`); a long comment explains why it need not be persisted or undo-tracked: it self-empties on restart, and duplicate/dead entries are harmless because LIB processing skips missing comments (`memory_comment_archive.hpp:71-77`, `memory_comment_archive.cpp:13-14, 40-41`).
- At LIB, each comment is **copied** (`copy_chain_object`) into an `archived_comment_index` — a `hashed_unique` boost multi-index over `comment_object` keyed by hash, living in SHM as a *named segment object* (`find_or_construct<archive_object_type>("memory_comment_archive")`, `memory_comment_archive.cpp:95-102`), **not** a chainbase index — then removed from `comment_index` with `remove_no_undo` (`memory_comment_archive.cpp:43-44`).
- ABW source comments record the design trade-offs: hashed index is fastest but rehash takes minutes (unusable for the live index on witness nodes), and the pool allocator can't be used with hashed indices (`memory_comment_archive.hpp:49-54`).
- `open()` asserts `archive->last_irreversible_block_num == db LIB` — the MEMORY-mode equivalent of discovery #4, with the hint "did you change comment-archive config option? if so, you need to replay" (`memory_comment_archive.cpp:100-101`).
- **Snapshot save/load are unimplemented** — both `FC_ASSERT(false)` (`memory_comment_archive.cpp:83-93`), so MEMORY mode cannot dump or load snapshots at all.

### rocksdb_comment_archive (ROCKSDB, default)
- Constructor registers `volatile_comment_index` as a chainbase plugin index (`HIVE_ADD_PLUGIN_INDEX`, `rocksdb_comment_archive.cpp:25` → `index.hpp:64-65`) and builds the provider + snapshot helper (`rocksdb_comment_archive.cpp:26-27`). The index therefore exists only on nodes running this mode, in SHM space ID 21, type value `21<<8 = 5376` (`comment_rocksdb_objects.hpp:8-17`).
- `on_cashout` asserts the hash is not already in the volatile index — "Incorrect duplicate archiving of the same comment", with an ABW note that undo coverage of the index makes this impossible (`rocksdb_comment_archive.cpp:39-41`) — then creates the volatile object (`:51-59`).
- `on_irreversible_block`: updates LIB (always, even pre-HF19 and below the batching threshold — the Put lands in the write buffer), early-outs before HF19, early-outs below `volatile_objects_limit`, then walks `by_block` order: serialize → `db.remove` comment → `db.remove` volatile → final `flushWriteBuffer()` (`rocksdb_comment_archive.cpp:100-141`).
- Serialization is `fc::raw::pack` of `rocksdb_comment_object {comment_id, parent_comment, depth}` via the `dump`/`load` helpers (`utilities.hpp:12-34`); key = 20-byte hash slice (`rocksdb_comment_archive.cpp:65-80`).
- Lookup reconstructs a heap `comment_object` through a dedicated public constructor `comment_object(id, parent, hash, depth)` (`rocksdb_comment_archive.cpp:97`; ctor at `detail/state/comment_object.hpp:35-36, 86-90`).
- `open()` passes the SHM LIB as the expected value (`rocksdb_comment_archive.cpp:184-188`); `close()` is also invoked from the destructor (`rocksdb_comment_archive.cpp:30-33`).

### Mode-switch protection matrix

Switching modes between runs without replay is detected in 3 of 4 directions (fresh-store/stale-store LIB asserts, discoveries #4 and the MEMORY open assert). The undetected direction: switching **to NONE** — the placeholder has no persistent state and no open-time check (`placeholder_comment_archive.cpp:52-70`), so previously archived comments would silently become invisible to consensus. Only reachable on testnet/mirrornet builds (discovery #1).

## RocksDB Provider Internals

### Open / schema-creation protocol (`rocksdb_storage_provider.cpp:25-243`)
1. Constructor: registers comparators with the RocksDB ObjectRegistry (needed so `BackupEngine`/options-file loading can resolve comparator names; `types.cpp:84-149`), creates the storage directory (`rocksdb_storage_provider.cpp:13-23`).
2. `openDb(expected_lib)`: caches expected LIB → `createDbSchema`:
   - Try `DB::OpenForReadOnly` with the full CF list - success means schema exists (`rocksdb_storage_provider.cpp:159-183`).
   - Otherwise create the DB, `CreateColumnFamilies` (without `default`, which always exists), write `STORE_MAJOR_VERSION`/`STORE_MINOR_VERSION` into the default CF, flush, close (`rocksdb_storage_provider.cpp:185-233`). A `db_wrapper` RAII guard guarantees `finalizeStorage()` on every path (`rocksdb_storage_provider.cpp:120-132`).
3. Reopen read-write with `Options().IncreaseParallelism()` + `OptimizeLevelStyleCompaction()`, bound the RocksDB info LOG, then `raise_fd_limit()` (`rocksdb_storage_provider.cpp:45-54`) and, since 1.28.8, `max_open_files = max_open_files_budget()` (`:62`, discovery #11; `createDbSchema` sets the same options, `:136-153`), verify store version (`rocksdb_storage_provider.cpp:297-314`), `loadSeqIdentifiers()` (no-op for comments; loads `AH_SEQ_ID` for AH - `rocksdb_ah_storage_provider.cpp:21-36`), `load_lib()` (discovery #4), set `_initialized` (`rocksdb_storage_provider.cpp:88`).

   > **RocksDB info LOG bounding (new in 1.28.7, `2f7b76b98`):** `openDb` (`rocksdb_storage_provider.cpp:49-53`) and `createDbSchema` now set `info_log_level = WARN`, `max_log_file_size = 8 MiB`, `keep_log_file_num = 1`. RocksDB's defaults (`max_log_file_size = 0`, `keep_log_file_num = 1000`, INFO level) never rotate the LOG, so it grew unbounded and could fill a small tmpfs — shipped as hive!2048.

`shutdownDb` = `flushDb` + destroy CF handles + close (`rocksdb_storage_provider.cpp:91-109`); `wipeDb` = `rocksdb::DestroyDB` (`:111-116`); `flushDb` = commit write buffer + `Flush()` every CF, since 1.28.8 composed of `flushWriteBuffer()` (the batch reaches the memtable and WAL) and `flushStorage()` (memtables written out to SST files) (`:259-286`); at 1.28.7 `flushDb` called `flushWriteBuffer()` and then flushed each column family inline; there was no `flushStorage()`.

### Write buffering
Each concrete provider owns its `WriteBatch` (`rocksdb_comment_storage_provider.hpp:23`; the AH provider uses the cache-augmented `CachableWriteBatch`, `types.hpp:283-298`). All mutations (comments, LIB, store version) accumulate there; reads (`DB::Get`) do **not** see the uncommitted batch, which is safe because `on_irreversible_block` commits the batch whenever it archives comments (`rocksdb_comment_archive.cpp:137`) and no lookup can interleave within block application; on its early returns (before HF19, or below the batch limit, `:104-110`) only the LIB record stays pending, with no comment data.

## Consensus Surface of Archived Comments

What each evaluator does when `get_comment` returns an archived comment (i.e. `find_comment_cashout` returns null):

| Operation | Behavior | Where |
|-----------|----------|-------|
| `comment_operation` (reply to archived parent) | Works; depth check uses archived `depth`, new comment's `parent_comment` = archived `comment_id` | `hive_evaluator_social.cpp:185-191` |
| `comment_operation` (edit of archived comment) | Allowed post-HF17; consensus only updates `account.last_post_edit` — the archived object is never modified | `hive_evaluator_social.cpp:278-311` |
| `comment_operation` (permlink reuse) | Prevented: `find_comment` sees the archived comment, so the op is an edit, not a create | `hive_evaluator_social.cpp:179, 195` |
| `vote_operation` | Silent no-op ("comment already paid") | `hive_evaluator_social.cpp:327-333` (pre-HF20), `:619-625` (HF20+) |
| `delete_comment_operation` | Rejected: "Cannot delete comment after payout" | `hive_evaluator_social.cpp:67` |
| `comment_options_operation` | No-op pre-HF24; rejected at/after HF24 | `hive_evaluator_social.cpp:150` |
| `create_proposal` / `update_proposal` (DHF) | Permlink-existence check resolves archived comments | `dhf_evaluator.cpp:67-70, 113-116` |
| API: `database_api.get_comment_pending_payouts`, `condenser_api.get_active_votes` | Point lookups resolve archived comments | `database_api_content.cpp:25`, `condenser_api.cpp:802` |

Because a comment can only be deleted *before* payout (`hive_evaluator_social.cpp:67`) and archival happens only *after* payout is irreversible, no fork can produce "archived on fork A, deleted on fork B" divergence — the `fork_reverts_cashout` test exercises the pre-payout delete-after-pop edge (`tests/unit/tests/comments_in_external_storage.cpp:339-370`) including author/permlink reuse by a replacement comment (`:371-411`).

## Snapshot Integration (`rocksdb_snapshot`)

- Generic over any `external_basic_provider`; parametrized by display name + storage subdir. Comments: `("Comments RocksDB", "comments_rocksdb_data")` (`rocksdb_comment_archive.cpp:27`); AH plugin: `("Account History RocksDB", "account_history_rocksdb_data")` (`account_history_rocksdb_plugin.cpp:120-121`).
- **Dump**: creates `<snapshot>/ext_data/comments_rocksdb_data`, asserts provider LIB == SHM LIB ("Inconsistency between state and Rocksdb data"), `flushDb`, `BackupEngine::CreateNewBackupWithMetadata(..., flush=true)` with head-block metadata, asserts **exactly one** backup exists in the dir, registers the path in the snapshot manifest under the display name (`rocksdb_snapshot.cpp:26-65`). The exactly-one assert means dumping into a directory that already contains a previous backup fails.
- **Load**: if the manifest lacks the key, logs "No external data present" and returns **without error** (`rocksdb_snapshot.cpp:70-74`) — loading a snapshot produced without comment data leaves the just-opened (typically fresh) archive in place; subsequent LIB mismatch is *not* checked again at this point. Otherwise: `shutdownDb` → `wipeDb` → `RestoreDBFromLatestBackup` (WAL into `<storage>/WAL`) → `openDb(SHM LIB)` re-running the consistency check (`rocksdb_snapshot.cpp:80-106`).
- Wiring: the chain plugin wipes everything when `--load-snapshot` is requested (`chain_plugin.cpp:955-956`), opens the DB normally, then the state_snapshot plugin (registered via the `state_snapshot_provider` interface from this area, `state_snapshot_provider.hpp:25-35`, registration `chain_plugin.cpp:98-100, 1980-1983`) loads SHM indexes and calls `get_comments_handler().load_snapshot(...)` plus the generic supplement signal for plugins (`state_snapshot_plugin.cpp:1403-1411`); dump path mirrors this (`state_snapshot_plugin.cpp:1525-1540`). Startup order: load processed at `chain_plugin.cpp:1894`, dump at `:1926`.
- The notification structs live in `database.hpp:912-926`; the dump/load helper interfaces (`snapshot_dump_helper`/`snapshot_load_helper`) in this area's `state_snapshot_provider.hpp:37-65`.

## Configuration

| Option | Kind | Default | Notes |
|--------|------|---------|-------|
| `comment-archive` | cfg, **testnet/mirrornet builds only** | `ROCKSDB` | `chain_plugin.cpp:1539-1541`; unknown values → `fc::parse_error_exception` (`:1613-1614`) |
| `comments-rocksdb-path` | **CLI only** (not config file) | `comments-rocksdb-storage` | `chain_plugin.cpp:1556`; relative paths resolve under `shared_memory_dir` (`:1593-1601`) |
| `flush-state-interval` | cfg | `10000` when unset | periodic state flush interval in blocks while syncing; 0 disables the periodic flush (`chain_plugin.cpp:1520-1521, 1659-1662`; `database.cpp:2119`) |
| `flush-state-interval-live` | cfg, since 1.28.8 | `1` | interval switched to at the end of syncing, not in testnet builds; 0 disables the periodic flush in live mode (`chain_plugin.cpp:1522-1523, 1664`; `database.cpp:864-872`); at 1.28.7 the live interval was fixed at 1 |

Default location is therefore `<shared-file-dir>/comments-rocksdb-storage` — i.e. **next to shared_memory.bin** (`chain_plugin.cpp:1593`). Operational consequences: (a) a node operator who puts `shared-file-dir` on tmpfs (`/dev/shm`) silently gets the comment archive on tmpfs too — consensus data lost on reboot (forces replay via discovery #4) and RAM consumed by RocksDB files; (b) because the override is CLI-only, it cannot be set in `config.ini`. The path is exposed to tests via `chain_plugin::comment_storage_dir()` (`chain_plugin.cpp:1498-1501`). The archive directory is created in the provider constructor (`rocksdb_storage_provider.cpp:21-22`); `openDb` also creates the *blockchain* storage path, a quirk inherited from AH usage where the data dir may not exist yet on fresh sync (`rocksdb_storage_provider.cpp:30-31` — the comment there still talks about the "AH plugin").

Stats: all implementations maintain `comments_handler::stats` (nanosecond counters for index-hit / archive-hit / not-found / cashout / LIB processing, `benchmark_dumper.hpp:28-35`), surfaced through the chain plugin's stat lambda for `--dump-memory-details` (`chain_plugin.cpp:858-869`).

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| `comments_handler` interface | `libraries/chain/include/hive/chain/external_storage/comments_handler.hpp` | 15-34 | Abstract archive API; `flush( bool force_storage_flush )` since 1.28.8 |
| `comment` wrapper | `libraries/chain/include/hive/chain/external_storage/comment.hpp` | 8-24 | SHM-pointer-or-heap handle |
| Handler injection / lookup funnel | `libraries/chain/include/hive/chain/database.hpp` | 860-880 | `set_/get_comments_handler` |
| Lookup overloads | `libraries/chain/database.cpp` | 402-451 | `get_comment`/`find_comment` × 8 |
| Cashout hook (HF19+) | `libraries/chain/database_comment.cpp` | 470-475 | `on_cashout` + cashout removal |
| HF19 bulk archiving | `libraries/chain/database_comment.cpp` | 94-113 | `remove_old_cashouts` |
| LIB hook | `libraries/chain/database.cpp` | 3121 | inside `migrate_irreversible_state` |
| Mode selection | `libraries/plugins/chain/chain_plugin.cpp` | 817-837 | builds chosen archive |
| Option compile gate | `libraries/plugins/chain/chain_plugin.cpp` | 1539-1541 | `USE_ALTERNATE_CHAIN_ID` |
| Placeholder impl | `libraries/chain/external_storage/placeholder_comment_archive.cpp` | 10-70 | NONE mode |
| Memory impl | `libraries/chain/external_storage/memory_comment_archive.cpp` | 8-117 | MEMORY mode |
| Memory archive SHM object | `libraries/chain/include/hive/chain/external_storage/memory_comment_archive.hpp` | 45-78 | hashed index + bookkeeping |
| RocksDB archive | `libraries/chain/external_storage/rocksdb_comment_archive.cpp` | 22-219 | ROCKSDB mode |
| `volatile_comment_object` | `libraries/chain/include/hive/chain/external_storage/comment_rocksdb_objects.hpp` | 19-39 | space 21 staging object |
| `volatile_comment_index` | `libraries/chain/include/hive/chain/external_storage/comment_rocksdb_objects_multiindex.hpp` | 9-28 | `by_id`, `by_block`, `by_permlink`; own header since 1.28.8 |
| `rocksdb_comment_object` | `libraries/chain/include/hive/chain/external_storage/comment_rocksdb_objects.hpp` | 43-58 | persisted record |
| Provider base | `libraries/chain/external_storage/rocksdb_storage_provider.cpp` | 13-381 | open/schema/flush/LIB/version |
| LIB load + ZFS hint | `libraries/chain/external_storage/rocksdb_storage_provider.cpp` | 330-356 | consistency guard |
| Comment CF defs | `libraries/chain/external_storage/rocksdb_comment_storage_provider.cpp` | 13-25 | default + account_permlink_hash |
| Shared types/comparators | `libraries/chain/include/hive/chain/external_storage/types.hpp` | 21-298 | CF enums, slices, comparators, AH types |
| Comparator registry | `libraries/chain/external_storage/types.cpp` | 84-149 | RocksDB ObjectLibrary registration |
| Snapshot backup/restore | `libraries/chain/external_storage/rocksdb_snapshot.cpp` | 26-106 | BackupEngine dump/load |
| Snapshot provider iface | `libraries/chain/include/hive/chain/external_storage/state_snapshot_provider.hpp` | 25-65 | chain↔snapshot-plugin contract |
| FD limit | `libraries/chain/external_storage/fd_budget.cpp` | 19-188 | raise to min(hard, 65536); since 1.28.8 also the per-store `max_open_files` budget and the FD usage report |
| Serialization helpers | `libraries/chain/include/hive/chain/external_storage/utilities.hpp` | 12-34 | `dump`/`load` via fc::raw |
| `EnableNoUndo` contract | `libraries/chainbase/include/chainbase/util/object.hpp` | 26-35 | why MEMORY removal is safe |
| `remove_no_undo` | `libraries/chainbase/include/chainbase/chainbase.hpp` | 446-457 | removal outside undo, only for `enable_no_undo_t` objects |
| AH reuse | `libraries/plugins/account_history_rocksdb/rocksdb_ah_storage_provider.cpp` | 5-90 | derives from provider base |
| Unit tests | `tests/unit/tests/comments_in_external_storage.cpp` | 65-483 | lifecycle, fork, inconsistency |
| FD budget test | `tests/unit/tests/fd_budget_tests.cpp` | 15-40 | `max_open_files` budget derivation (since 1.28.8) |

## Cross-references to existing parts

- **Part 05 (state-objects)** - *deepens*. Part 05's section "Comment Archive and External Storage (RocksDB)" describes the three modes, the `USE_ALTERNATE_CHAIN_ID` compile gate on the option, `volatile_comment_object` with its index, and the lookup funnel. This zoom adds: the provider/snapshot class hierarchy and its reuse by `account_history_rocksdb`; the LIB cross-check + atomic write-batch consistency model and the flush paths; CF layout details; the reason for the undo asymmetry (Part 05, section "State Objects Reference" (conventions) and Key Discoveries item 15, states that only the MEMORY archive calls `remove_no_undo` while the ROCKSDB archive uses undoable `remove`; discovery #3 here explains why, as pinned by the `fork_reverts_cashout` test); and the evaluator behavior matrix.
- **Part 04 (chain-evaluators)** — *complements*. Part 04's comment/vote/delete evaluator analysis describes paid-comment behavior via `comment_cashout` absence; this zoom explains where the comment object itself physically lives at that point and why lookups still succeed.
- **Part 09 (hardfork-history)** — *complements*. HF19 is the archival watershed: `on_cashout` fires only when HF19 is active (`database_comment.cpp:471-475`), LIB migration is HF19-gated in both archives (`rocksdb_comment_archive.cpp:104-105`, `memory_comment_archive.cpp:24-25`), and HF19 application bulk-archives all previously-paid comments (`database_hardfork.cpp:328`).
- **Part 10 (api-layer)** — *complements*. API methods that resolve comments by author+permlink transparently read RocksDB; there is no API that can enumerate archived comments from hived (consistent with Part 10's observation that content APIs largely live in hivemind).
- **Part 06 (consensus-mechanisms)** - *complements*. `migrate_irreversible_state` (Part 06, section "Irreversibility Propagation") is the single driver of archive migration; the archive write happens inside the same irreversibility transition as block-log storage and undo `commit`. Part 06, section "Chain Plugin Thread Model and Write Queues", describes when `notify_end_of_syncing` runs; its effects on the archive (forced flush, batching threshold dropped to 0) are in the lifecycle table and discovery #8 here.

## Discrepancies and Potential Issues

1. **I/O errors conflated with not-found in consensus reads** (`rocksdb_storage_provider.cpp:322-328`): `read()` returns `s.ok()` with no `IsNotFound()` discrimination, unlike the AH-side pattern (`types.cpp:65`). A RocksDB read error during evaluation would be interpreted as "comment does not exist", turning a local fault into consensus divergence rather than a halt. Suggested hardening: assert `s.IsNotFound()` when not OK.
2. **Dead/vestigial code in `createDbSchema`**: the `<needs-import, opened-ok>` tuple (documented at `rocksdb_storage_provider.hpp:48-51`) is effectively constant — every failure path throws, so `openDb`'s `if(!std::get<1>(_result))` branch (`rocksdb_storage_provider.cpp:33-38`) is unreachable, and `std::get<0>` is never read. The trailing comment at `:242` ("DB does not need data import, an application is closed") contradicts the actual returned value `{true, true}`. Leftovers from the AH plugin's original import flow.
3. **Misleading CF naming** (discovery #6): comment records live in the `default` CF; the `account_permlink_hash` CF holds only the LIB record. Anyone writing external tooling against the comment archive will be misled by the names.
4. **Mode switch to NONE is undetected** (testnet-only surface): placeholder mode performs no open-time consistency check, so switching ROCKSDB→NONE silently hides archived comments from consensus.
5. **`unpackSlice` uses C `assert`** (`types.hpp:61, 67`): size validation of slices read back from RocksDB disappears in release builds (NDEBUG); a corrupted/truncated value would be reinterpret-cast without checks. Mitigated in practice by fc unpack errors for the comment payload path, but the LIB read (`lib_slice_t::unpackSlice`, `rocksdb_storage_provider.cpp:346`) relies on it.
6. **`comments-rocksdb-path` is CLI-only and defaults under `shared-file-dir`**: cannot be set via config.ini, and tmpfs SHM placement drags consensus data onto tmpfs (see Configuration). Worth an operator-facing doc note; `haf_api_node` deployments should be checked for this (out of scope here).
7. Minor: the "Very rare case" comment in `openDb` (`rocksdb_storage_provider.cpp:30`) still describes the AH plugin even though the code is now shared base-class logic; the shared static `comments_handler::stats` is defined in `placeholder_comment_archive.cpp:8`, an unintuitive location.

## Open Questions

1. **AH plugin specifics** (different area): how `account_history_rocksdb` drives `CachableWriteBatch`, pruning via `account_history_info`, the `Columns` CFs, and reindex interplay (`account_history_rocksdb_plugin.cpp:1092-1125`) deserve their own zoom; this area only defines their building blocks.
2. **State snapshot plugin internals** (different area): manifest format, `ext_data` layout, and the ordering guarantees between index load and `load_snapshot_external_data` were only spot-checked (`state_snapshot_plugin.cpp:1403-1411, 1525-1540`).
3. **Why HF19 (not HF17) as the archival boundary**: code-visible facts are that cashout-object removal and archiving are HF19-gated and `comment_cashout_ex_object` dies at HF19; the deeper rationale (vote/payout semantics that still mutated paid comments between HF17 and HF19) lives in reward-code history — Part 07/09 territory.
4. **`comments_in_blocks` id-wrap comment** (`memory_comment_archive.hpp:75-76`): the claim that comment ids can "wrap once in many years" (echoed by the test's `BOOST_CHECK_LT(old_id, comment_id)` caveat, `comments_in_external_storage.cpp:401`) is asserted but not explained — chainbase oid allocation would need its own verification to substantiate when/whether wrap is possible.
5. **Replay memory spike at HF19**: `remove_old_cashouts` creates one volatile object per already-paid comment in a single block's processing (millions on mainnet history). They migrate out at the next LIB round, but the transient SHM cost during replay was not measured here.
6. **BackupEngine accumulation**: whether the snapshot plugin guarantees a fresh `ext_data` directory per dump (so the `backupInfos.size() == 1` assert in `rocksdb_snapshot.cpp:62` can't fire on re-dump) was not traced.
