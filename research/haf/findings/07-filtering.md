# HAF Part 07 - Filtering (Indexing a Subset)

**Anchor:** HAF `1.28.6` (`222c848355`).
**Scope:** how a HAF node can be configured to index only a **subset** of the chain -
filtering by account, operation type, or operation body - so an app-specific node stays
small and syncs fast. Builds on impacted-accounts (part 04) and the indexing pipeline
(part 06).

Paths relative to `src/`.

---

## 1. Why filter

A full HAF node indexes every operation of the whole chain - large and slow to sync. Most
apps need only a slice: one community's accounts, a few operation types, or `custom_json`s
matching a pattern. HAF lets the operator restrict what `sql_serializer` writes to Postgres,
so a node can be a fraction of the size while still serving its app. Filtering is applied at
**index time** (in the plugin), not at query time.

---

## 2. The three filter dimensions

Configured via `sql_serializer` plugin options (`sql_serializer.cpp:969-972`):

| Option | Filters by | Notes |
|--------|-----------|-------|
| `psql-track-account-range` | **accounts** in a range `["from","to"]` | repeatable; an op is kept if it impacts a tracked account |
| `psql-track-operations` | **operation types** | repeatable; keep only these op types |
| `psql-track-body-operations` | **operation body** (per-type regex) | repeatable; a regex on the op body decides exclusion - "complex regex can cause slowdown or [be] abandoned" |
| `psql-enable-filter` (default `true`) | master switch | with no track-* options the filter accepts everything (full index); tracks narrow it |

So the default node indexes the whole chain; you **opt into** a subset by adding track
options. Account-range filtering hooks into impacted-accounts (part 04,
`get_impacted_accounts`) - an operation is account-tracked when any account it impacts falls
in a tracked range.

---

## 3. The filter classes

`blockchain_data_filter` (`sql_serializer/include/.../blockchain_data_filter.hpp:11`) is the
interface:

- `is_enabled()` (`:13`/`:45`)
- `is_tracked_account(account_name)` (`:14`/`:48`)
- `is_tracked_operation(operation)` (`:15`/`:49`)

`blockchain_filter` (`:18`) is the implementation, holding three pluggable trackers
(`:35-37`): an `account_filter`, an `operation_filter` (by type), and an
`operation_body_filter` (regex). `fill(options, tracked_accounts, tracked_operations,
tracked_operation_body_filters)` (`:52`) builds them from the plugin options
(wired at `sql_serializer.cpp:1023`); `is_trx_accepted` / `remember_trx_id` (`:46`,`:51`)
track which transactions had any accepted operation.

---

## 4. Application during indexing

`filter_collector` (`.../filter_collector.hpp:7`) applies the filter as the plugin walks a
block:

- `is_operation_tracked(...)` / `collect_tracked_operation(op)` (`:30-31`) - keep an
  operation if its type/body passes,
- `is_account_tracked(account)` / `collect_tracked_account(account)` (`:27-28`) - accumulate
  the impacted accounts that fall in a tracked range (into `_accounts_accepted`, a
  `flat_set`).

Only operations/accounts the collector accepts are converted and dumped to Postgres (part
06) - everything else is dropped before it reaches the database. So the filter shrinks the
cache, the writes, and the stored data together.

---

## 5. The `op_body_filter` tool

Body regexes are fiddly, so HAF ships a standalone helper, `op_body_filter`
(`filter_utils/op_body_filter.cpp`, `filter_utils/README.md`): feed it the output of
`block_api.get_block` and iterate on a regex until it matches the operations you want, then
use it as a `psql-track-body-operations` value. Examples live in `filter_utils/examples.info`.

---

## 6. Notable findings

1. **Index-time, three-axis filtering** (account range / op type / op body) lets a HAF node
   be app-sized, not chain-sized - the main operational lever for HAF deployments.
2. **Account filtering = impacted-account membership** - it reuses `get_impacted_accounts`
   (part 04), so "track account X" means "keep every op that touches X", which is exactly
   account-history semantics.
3. **Body filtering is regex on the op body** and explicitly warned to be a performance
   footgun (`sql_serializer.cpp:971`) - powerful but use sparingly.
4. **Default is full index** - filtering is opt-in via track options even though
   `psql-enable-filter` defaults true.
5. **Filtering is upstream of everything** - dropped data never enters the cache/WAL/tables,
   so a filtered node is smaller end to end, not just in queries.

---

## 7. Code References

| Topic | File:line |
|-------|-----------|
| Filter interface | `sql_serializer/include/.../blockchain_data_filter.hpp:11-15` |
| blockchain_filter (trackers, fill) | `.../blockchain_data_filter.hpp:18-37`,`:45-56` |
| filter_collector | `.../filter_collector.hpp:7`,`:27-31` |
| Plugin options | `sql_serializer/sql_serializer.cpp:969-972` (filter `fill` at `:1023`) |
| Account-tracking <-> impacted accounts | `hive_fork_manager/get_impacted_accounts.sql:1` (part 04) |
| op_body_filter tool | `filter_utils/op_body_filter.cpp`; `filter_utils/README.md` |

---

## 8. Open Questions (for later parts / zoom)

- **Range semantics** - whether `psql-track-account-range` is lexicographic on account name
  and how multiple ranges compose.
- **Filtering + state providers** - whether accounts/keyauth/metadata (part 04) respect the
  account filter or always cover all accounts.
- **Re-filtering an existing node** - whether widening a filter requires a replay (likely)
  and any tooling for it.
- **Interaction with lite/pruning mode** and the exact `is_tracked_operation` evaluation
  order (type before body, short-circuiting).
