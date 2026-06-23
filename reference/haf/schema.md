# HAF Reference - Schema & Data Model

The `hive_fork_manager` schema. Deep detail: `findings/02-fork-manager-schema.md`,
`findings/04-data-model.md`. Paths relative to `src/hive_fork_manager/`.

## Schemas

| Schema | Holds | On update |
|--------|-------|-----------|
| `hafd` | persistent data + its domains/types | never dropped (each table `pg_extension_config_dump`'d) |
| `hive` | runtime code: functions, procedures, **views**, composite types | dropped & recreated |
| `hive_update` | update-time helpers | - |

## Context registry (`context_rewind/data_schema.sql`)

- `hafd.contexts` (`:9`): per-app cursor - `name`, `schema`, `current_block_num`,
  `irreversible_block`, `events_id` (queue cursor), `fork_id`, `is_forking`, `owner`,
  `last_active_at`, `stages`, `loop`.
- `hafd.contexts_attachment` (`:33`): attached (live) vs detached.
- `hafd.registered_tables` (`:43`): app table -> shadow table (for rewind).
- `hafd.triggers` (`:63`): rewind triggers.
- enums: `context_name` (`:3`), `state_providers` (`:5`), `event_type` (`:7`).

## Core tables (irreversible / reversible pairs)

Each block-derived table has `hafd.X` (irreversible) + `hafd.X_reversible` (fork-tagged).

| Table | Key columns | File:line |
|-------|-------------|-----------|
| `hafd.blocks` | `num`, `hash`, `prev`, producer, merkle root + **per-block DGPO** (supplies, vesting fund, interest) | `irreversible_blocks.sql:7` |
| `hafd.transactions` | `block_num`, `trx_in_block`, `trx_hash`, `ref_block_*`, `expiration`, `signature` | `:61` |
| `hafd.transactions_multisig` | `(trx_hash, signature)` | `:76` |
| `hafd.operations` | `id` (= `\|32b block\|32b seq\|`), `op_type_id`, `op_pos`, `body_value` JSONB | `:100` |
| `hafd.operation_types` | `id`, `name`, `is_virtual` (the 93-op catalog) | `:84` |
| `hafd.custom_json_types` | `id`, `custom_json_id` | `:93` |
| `hafd.applied_hardforks` | `hardfork_num`, `block_num`, `hardfork_vop_id` | `:113` |
| `hafd.hive_state` | sync status: `consistent_block`, `state` (sync_state enum), `pruning`, `lite_mode` | `:44` |

Reversible mirrors (carry `fork_id`): `reversible_blocks.sql:1`,`:14`,`:28`,`:42`,`:58`
(accounts),`:74` (account_operations),`:90`.

## Events & forks

- `hafd.events_queue` (`events_queue.sql:6`): `(id, event, block_num)`. `block_num` is
  **per-event-type** - `NEW_BLOCK`=block, `NEW_IRREVERSIBLE`=irrev block,
  `BACK_FROM_FORK`=**fork id**, `MASSIVE_SYNC`=head irrev after massive push.
- `hafd.fork` (`forks.sql:1`): `(id, block_num, time_of_fork)`.

## The per-context views (the merge)

`blocks_views_for_contexts.sql` generates `{schema}.blocks_view` (and operations/transactions
views) as a `UNION ALL` of irreversible rows (`num <= irreversible_block`) + the context's-fork
reversible rows (`MAX(fork_id) <= ctx.fork_id AND num <= current_block_num`,
`:149-156`). **Apps query the view, never the raw tables.**

## Derived data

- `hive.get_impacted_accounts(operation)` (`get_impacted_accounts.sql:1`) -> accounts an op
  touches; basis for `account_operations` (AH-style queries).
- `hive.get_impacted_balances(operation, ...)` (`get_impacted_balances.sql:10`) -> balance
  deltas; `get_balance_impacting_operations()` (`:52`).
- **State providers** (opt-in per context): `ACCOUNTS` / `KEYAUTH` / `METADATA`
  (`state_providers/*.sql`) maintain account list / key auths / metadata.

## Types

`hafd` **domains** = column types (`account_name_type VARCHAR(16)`, `permlink VARCHAR(255)`,
`block_id_type bytea`, `asset_symbol int8`, ...; `types/domains.sql`). `hive` **composite
types** = value/operation shapes (`hive.asset`, `hive.price`, `hive.comment_operation`, ...;
`types/types.sql`).
