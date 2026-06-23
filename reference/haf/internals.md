# HAF Reference - Architecture & Indexing Internals

How HAF works end to end. Deep detail: `findings/01-architecture-dataflow.md`,
`findings/06-indexing-internals.md`.

## The two halves

```
hived ──(sql_serializer C++ plugin)──> Postgres ──(hive_fork_manager extension)──> apps
        writes block/op data               hafd + hive schemas      contexts + views
```

- **`sql_serializer/`** (C++): a hived plugin that consumes block/operation data via chain
  signals and writes it to Postgres.
- **`hive_fork_manager/`** (PL/pgSQL): the SQL framework that stores it (reversible +
  irreversible) and serves apps via contexts/views.
- Events-source, pull model: hived only *schedules* events; apps process at their own pace.

## Components (`src/`)

| Dir | Role |
|-----|------|
| `sql_serializer/` | hived plugin: cache -> dump -> Postgres |
| `hive_fork_manager/` | SQL framework (schemas, contexts, tables, views, rewind) |
| `applications/`, `query_supervisor/`, `transaction_controllers/` | app base, query limits, DB tx helpers |
| `filter_utils/`, `pq_utils/`, `psql_utils/` | filtering, libpq/Postgres C++ utils |

## Dataflow (sql_serializer)

hived signals -> `sql_serializer_plugin_impl` (`sql_serializer.cpp:290`) handlers
(`connect_signals` `:580-587`): `pre/post_apply_operation` (cache each op + impacted
accounts), `pre/post_apply_block`, `pre/post_reindex`, `end_of_syncing`. Data accumulates in
`cached_data_t` (parallel vectors), then a mode-specific trigger flushes via a dumper.

## Sync modes & dumpers

| Mode | Flush trigger (`indexation_state.cpp`) | Dumper | Write path |
|------|----------------------------------------|--------|-----------|
| MASSIVE / reindex (replay) | `reindex_flush_trigger` (`:75`) | `reindex_data_dumper` | raw `INSERT`s, high-volume tables split across writer threads |
| P2P | `p2p_flush_trigger` (`:103`) | - | flush per `MINIMUM_BLOCKS_PER_FLUSH` |
| LIVE | `live_flush_trigger` (`:91`) | `livesync_data_dumper` | fork-aware `hive.push_block`, one transaction |
| LIVE (lite) | `lite_live_flush_trigger` (`:135`) | - | flush irreversible only |

## Indexing internals (`include/hive/plugins/sql_serializer/`)

- **Cache**: `cached_data_t` (`cached_data.h:6`) - per-batch vectors (blocks, transactions,
  operations, accounts, account_operations, applied_hardforks), pre-reserved.
- **Processors**: `data_processor` (`data_processor.hpp:21`) - **one worker thread per data
  type**; `trigger(chunk)` async, `complete_data_processing()` to sync. Types convert+write
  in parallel; the splitter (`chunks_for_sql_writers_splitter`) parallelizes high-volume
  tables further.
- **WAL**: `write_ahead_log.hpp:13-26` - crash consistency between hived and Postgres;
  replayed on startup (`replay_wal_if_necessary`, `sql_serializer.cpp:514`).
- **Index/constraint management**: `indexes_controler.h:15` - drop indexes+constraints above
  `_psql_index_threshold` (default 20M blocks), bulk-insert, recreate.
- **Support**: `vacuum_cleaner` (shadow tables), `accounts_collector` (account set),
  `blockchain_data_filter` (filtering -> [filtering.md](filtering.md)).
