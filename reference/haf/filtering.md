# HAF Reference - Filtering (Index a Subset)

Configure a HAF node to index only part of the chain - smaller DB, faster sync. Deep
detail: `findings/07-filtering.md`. Filtering is applied at **index time** (in the
`sql_serializer` plugin), so dropped data never enters the cache/WAL/tables.

## Three filter axes (plugin options, `sql_serializer.cpp:969-972`)

| Option | Filters by | Notes |
|--------|-----------|-------|
| `psql-track-account-range` | accounts in a range `["from","to"]` | repeatable; keep ops impacting a tracked account |
| `psql-track-operations` | operation types | repeatable |
| `psql-track-body-operations` | operation body (per-type regex) | repeatable; a perf footgun - "complex regex can cause slowdown or [be] abandoned" |
| `psql-enable-filter` (default `true`) | master switch | with **no** track-* options, accepts everything (full index) |

**Default = full index.** You opt into a subset by adding track options.

## How it applies

- `blockchain_filter` (`blockchain_data_filter.hpp:18`): `is_tracked_account` /
  `is_tracked_operation`, built from the options via `fill(...)` (`:52`; wired at
  `sql_serializer.cpp:1023`). Holds an `account_filter` + `operation_filter` +
  `operation_body_filter` (`:35-37`).
- `filter_collector` (`filter_collector.hpp:7`): during indexing, accepts and collects the
  ops/accounts that pass (`is_operation_tracked`/`collect_tracked_operation` `:30-31`;
  `is_account_tracked`/`collect_tracked_account` `:27-28`). Only accepted data is dumped.
- **Account-tracking = impacted-account membership** - reuses `get_impacted_accounts`
  (schema.md), i.e. "track account X" = "keep every op that touches X" = account-history
  semantics.

## Tooling

`op_body_filter` (`filter_utils/op_body_filter.cpp`, `filter_utils/README.md`) builds/tests
body regexes from `block_api.get_block` output; examples in `filter_utils/examples.info`.

## Use cases

App-specific nodes: a node that tracks only one community's accounts, or only `custom_json`
ops with a given id, is a fraction of a full node - end to end (cache, WAL, storage), not
just at query time.
