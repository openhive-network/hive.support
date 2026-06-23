# HAF Reference - Navigation Guide

Compact, source-verified quick-lookup for **HAF** (Hive Application Framework) - the
PostgreSQL indexing layer for Hive. Anchored to HAF `1.28.6` (`222c848355`). For deep
analysis with `file:line` citations, see `../../research/haf/findings/`.

HAF documents **infrastructure** (indexing + the SQL app framework). For the protocol it
indexes (operations, consensus, economics) use the hive-core reference (`../operations.md`,
...) - HAF 1.28.6's protocol layer is the hive-core KB's exact `1.28.6` (`10ac0ce94`).

## Quick Lookup

| I need to know... | Read |
|-------------------|------|
| How HAF works end to end (plugin -> Postgres -> apps), sync modes, the indexing pipeline | [internals.md](internals.md) |
| The schemas, tables, data model, views, types | [schema.md](schema.md) |
| How to build a HAF app (context, the loop, stages) | [apps.md](apps.md) |
| Fork handling & reversibility (the rewind machinery) | [forks.md](forks.md) |
| Indexing only a subset (account/operation/body filters) | [filtering.md](filtering.md) |

## Key Numbers

- **2 cooperating halves**: the `sql_serializer` hived plugin (C++, writes) + the
  `hive_fork_manager` Postgres extension (PL/pgSQL, serves apps).
- **3 schemas**: `hafd` (persistent data, survives updates), `hive` (runtime code/views,
  dropped+recreated on update), `hive_update`.
- **3 sync modes**: MASSIVE/reindex, P2P, LIVE (+ lite), with mode-specific flush triggers
  and dumpers.
- **4 event types**: `NEW_BLOCK`, `NEW_IRREVERSIBLE`, `BACK_FROM_FORK`, `MASSIVE_SYNC`.
- **3 filter axes**: account range, operation type, operation-body regex.

## Important Non-Obvious Facts

- **`hive` schema is disposable, `hafd` is sacred** - updates drop & recreate all of `hive`
  (code/views) but never touch `hafd` (data). The upgrade-safety boundary.
- **The per-context `*_view`s are the API** - apps query `blocks_view`/`operations_view`/...
  and never the raw `_reversible` tables; the view merges reversible + irreversible for the
  context's fork.
- **`events_queue.block_num` is polymorphic** - for `BACK_FROM_FORK` it's a **fork id**, not
  a block number. Reading it without the `event` type is a bug.
- **Operation `id` encodes `|32b block_num | 32b seq|`** - sorts and locates an op in one
  bigint; `body_value` is JSONB typed by `op_type_id`.
- **Per-block DGPO is stored** in `hafd.blocks` - point-in-time supply/price/interest is a
  column read, not a replay.
- **`app_next_block` is the heartbeat** - it stamps `last_active_at`; an app that stops
  calling it is auto-detached (dead-app detection).
- **Stages auto-scale batch size** by distance-to-head (bulk when behind, 1 block when live).
- **Rewind = reverse-replay of a shadow undo log** - only **forking** contexts pay for it
  (triggers + shadow tables); non-forking/lite contexts skip it.
- **The WAL is crash-consistency, not performance** - it closes the window where hived
  processed a block but Postgres hadn't committed.
- **Default is a full index** - filtering (account/op/body) is opt-in; account-tracking =
  impacted-account membership (`get_impacted_accounts`), i.e. account-history semantics.
- **Account-history & balance-tracking are first-class SQL** (`get_impacted_accounts`,
  `get_impacted_balances`) - HAF re-implements the old AH/balance plugins.

## In one line

`hived` + the `sql_serializer` plugin write block data into Postgres; the
`hive_fork_manager` extension serves it to apps via fork-managed contexts and views, so apps
write ordinary SQL and get fork-correct data. See [internals.md](internals.md).

## Found an error?

Write a contribution file in `contrib/` - see `../../CONTRIBUTING.md`.
