# HAF Part 01 - Architecture & Dataflow

**Anchor:** HAF `1.28.6` (`222c848355efbdf0e4970c5f384b6da7cbfb582e`).
**Protocol alignment:** HAF 1.28.6 bundles the `hive` submodule at
`10ac0ce94f7591b6ad80db1a23d046c9d57b6559` - the **exact commit** the hive-core KB is
pinned to. So HAF's protocol layer matches that KB precisely; this part cross-references
it rather than re-deriving operations/consensus.

**Scope:** the overall shape of HAF - what it is, its components, how blockchain data
flows from `hived` into Postgres (`sql_serializer`), and how apps consume it (the
`hive_fork_manager` events-source model). Deep detail on the SQL framework, app API,
data model, forks, indexing internals, and filtering is parts 02-07.

Paths are HAF-repo-relative, against the pinned worktree `workspace/haf/222c848355/`.

---

## 1. What HAF is

HAF (Hive Application Framework) is a **PostgreSQL indexing layer** for Hive. It is not a
node and not a client library - it runs *alongside* `hived` and turns the blockchain into
queryable SQL, with built-in fork/reversibility handling so apps don't have to reimplement
it.

It is an **"events-source" architecture** (`src/hive_fork_manager/Readme.md`): during live
sync `hived` only *schedules events* by writing block data into the database; HAF apps then
process those events at their own pace via the fork-manager API. Multiple apps share one
block database and process **independently** - no app needs to lock the shared blockchain
tables.

Two cooperating halves:

```
   hived  ──(C++ plugin)──>  Postgres  ──(SQL framework)──>  HAF apps
   sql_serializer            hafd/hive schemas               contexts + app tables
   (writes block data)       (reversible + irreversible)     (read views, at own pace)
```

---

## 2. Components (`src/`)

| Component | Lang | Role |
|-----------|------|------|
| `sql_serializer/` | C++ | a **hived plugin** that consumes block/operation data and writes it into Postgres (section 3) |
| `hive_fork_manager/` | PL/pgSQL | the **SQL framework**: the `hive`/`hafd` schemas, app contexts, reversible/irreversible tables, fork handling (section 4) |
| `applications/` | C++/SQL | the HAF app framework / base app machinery (part 03) |
| `query_supervisor/` | C++ | guards app queries (limits/monitoring) |
| `transaction_controllers/` | C++ | DB transaction helpers (retry/commit) |
| `filter_utils/` | C++ | operation/account filtering of indexed data (part 07) |
| `pq_utils/`, `psql_utils/` | C++ | libpq / Postgres C++ utilities |

The `hive` submodule (uninitialized in the worktree) supplies the protocol/`hived`
side; it is the 1.28.6 commit the hive-core KB documents.

---

## 3. Dataflow: `sql_serializer` (hived -> Postgres)

`sql_serializer_plugin_impl` (`src/sql_serializer/sql_serializer.cpp:290`) is the hived
plugin that drives indexing. It hooks `hived`'s chain signals in `connect_signals`
(`sql_serializer.cpp:580-587`):

| hived signal -> handler | Purpose |
|-------------------------|---------|
| `pre_apply_operation` / `post_apply_operation` | gather each operation + its impacted accounts into an in-memory cache; PRE handles all ops except the hardfork virtual op, POST handles that one (ordering compat with account-history) |
| `pre_apply_block` (`:366`) | first call establishes the DB connection; then disconnects |
| `post_apply_block` (`:367`) | push block + transaction data into the cache; may trigger a flush |
| `pre_reindex` / `post_reindex` (`:587`) | switch processing mode (replay vs sync) |
| `end_of_syncing` | switch into LIVE-SYNC mode |

Some virtual operations are **supplemented** here (`hive::util::supplement_operation`) -
extra data not produced during normal state evaluation, needed by downstream services
(e.g. Hivemind) - mirroring the old account-history RocksDB plugin. (Detail: `dataflow.txt`.)

### Sync modes and flush triggers

`indexation_state` flushes the cache to SQL differently per mode (`INDEXATION` enum;
`src/sql_serializer/indexation_state.cpp`):

| Mode | Flush trigger | Behavior |
|------|---------------|----------|
| MASSIVE / reindex (replay) | `reindex_flush_trigger` (`:75`) | flush every `BLOCKS_PER_FLUSH`; incoming data is **implicitly irreversible** |
| P2P-SYNC | `p2p_flush_trigger` (`:103`) | flush once per `MINIMUM_BLOCKS_PER_FLUSH`; sets irreversible-block handler |
| LIVE-SYNC | `live_flush_trigger` (`:91`) | flush every block; irreversible immediately follows the chain's irreversible |
| LIVE (lite) | `lite_live_flush_trigger` (`:135`) | LIVE variant that flushes only irreversible blocks (`:560-584`) |

Two dumpers materialize the cache (`dataflow.txt`): `livesync_data_dumper` converts to a
form compatible with the `hive.push_block` procedure (one transaction; multithreaded string
build), while `reindex_data_dumper` produces direct table `INSERT`s (multithreaded per data
kind). So replay uses fast bulk inserts; live sync routes through the fork-aware
`push_block`.

---

## 4. The fork manager (Postgres -> apps)

`hive_fork_manager` is a Postgres **extension** (`CREATE EXTENSION hive_fork_manager
CASCADE;`) organized into schemas (`src/hive_fork_manager/Readme.md`):

| Schema | Holds | Update behavior |
|--------|-------|-----------------|
| `hafd` | data types + **collected blockchain data** | critical; **never modified/dropped** on update |
| `hive` | runtime code (functions, procedures, views) | **dropped and recreated** at the start of every HAF update |
| `hive_update` | update-time functions | - |

Block data is stored in **two parallel table sets**: **reversible** and **irreversible**.
When a block becomes irreversible, `hived` (via the fork-manager API) signals that the data
should be moved from the reversible to the irreversible tables. Operates at
`READ COMMITTED` isolation.

### The context model

A HAF app groups its tables into a named **context** (alphanumerics + underscores). The
context tracks the app's processed events, last block, and the fork currently being
processed - enough for HAF to **auto-construct views** that seamlessly merge reversible +
irreversible data:
`{context_schema}.{blocks|transactions|multi_signatures|operations}_view`.
A context is owned by, and accessible only to, the role that created it; only roles
inheriting from **`hive_applications_group`** may use the App API.

---

## 5. The app loop (consume side)

The app-facing API lives in `src/hive_fork_manager/app_api.sql`. The canonical loop:

```
hive.app_create_context(...)        -- create the context (:22 / :57)
hive.app_register_table(...)        -- register app tables for fork rewind (:475)
LOOP:
  hive.app_next_block(context)      -- next block range to process (:198 / :228)
  -- read context views (blocks_view, operations_view, ...); write to app tables
```

Other key calls: `app_context_attach` / `app_context_detach` (`:240` / `:331`) pause/resume
a context; `app_context_set_forking` / `app_context_set_non_forking` (`:419` / `:367`)
choose whether the context rewinds on forks; `app_get_irreversible_block` (`:518`);
`app_create_views_for_contexts` (`:1`); `app_reset_data` / `app_remove_context`.

Because apps only ever read through their context's views and write to their own
fork-managed tables, the fork manager can **rewind** an app's data automatically when
`hived` switches forks - the app does not implement fork handling itself (detail: part 05).

---

## 6. Notable findings

1. **Events-source, pull-based.** hived/sql_serializer only *write* events; apps *pull*
   via `app_next_block` at their own pace. Multiple apps share one DB with no cross-app
   locking (`Readme.md`).
2. **`hive` schema is disposable, `hafd` is sacred.** Updates drop and recreate all of
   `hive` (code) but never touch `hafd` (data) - the upgrade-safety boundary.
3. **Reversible vs irreversible is first-class**, exposed through auto-generated per-context
   `*_view`s that merge both - apps query one view and get fork-correct data.
4. **Replay and live sync use different write paths** - bulk `INSERT` (`reindex_data_dumper`)
   vs the fork-aware `hive.push_block` (`livesync_data_dumper`) - selected by the indexation
   mode.
5. **Protocol layer is the hive-core KB's exact 1.28.6** (`10ac0ce94`), so HAF facts about
   operations/blocks defer cleanly to that KB.
6. **Virtual-op supplementation happens at index time** (`supplement_operation`) - HAF
   stores richer virtual-op data than bare consensus, for downstream apps.

---

## 7. Code References

| Topic | File:line |
|-------|-----------|
| HAF components | `src/` (sql_serializer, hive_fork_manager, applications, ...) |
| sql_serializer plugin impl | `src/sql_serializer/sql_serializer.cpp:290` |
| hived signal handlers / connect | `src/sql_serializer/sql_serializer.cpp:366-367`,`:580-587` |
| Sync-mode flush triggers | `src/sql_serializer/indexation_state.cpp:75`,`:91`,`:103`,`:135` |
| Dumpers | `src/sql_serializer/{livesync_data_dumper,reindex_data_dumper}.cpp` |
| Full dataflow narrative | `dataflow.txt` |
| Fork-manager architecture + schemas | `src/hive_fork_manager/Readme.md` |
| App API (contexts, next_block, views) | `src/hive_fork_manager/app_api.sql:22`,`:198`,`:240`,`:475`,`:518` |

---

## 8. Open Questions (for later parts / zoom)

- **The `hafd`/`hive` schema in detail** (tables, the block/transaction/operation storage,
  the `hive.contexts` registry) - part 02.
- **App lifecycle & the application loop** (`applications/`, `app_next_block` internals,
  the events queue) - part 03.
- **Exact data model** of blocks/transactions/operations + impacted accounts/balances and
  account-operations - part 04.
- **Fork rewind mechanics** (`context_rewind`, how registered tables are reverted on a fork
  switch) - part 05.
- **sql_serializer internals** (the cache, `write_ahead_log`, `data_processor`, the WAL
  replay at `sql_serializer.cpp:514`) - part 06.
- **Filtering** (operation/account filters, `get_impacted_accounts`) - part 07.
