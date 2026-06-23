# HAF Part 02 - The hive_fork_manager Schema

**Anchor:** HAF `1.28.6` (`222c848355`).
**Scope:** the SQL framework's schema - the `hive`/`hafd` schemas, the context registry,
the irreversible/reversible core tables, the events queue, and the type system. This is
the structural map; the per-column data model of blocks/transactions/operations is part 04,
and the fork-rewind mechanics (shadow tables, triggers in action) are part 05.

Paths are relative to `src/hive_fork_manager/` in the pinned worktree.

---

## 1. The schemas

| Schema | Holds | Lifecycle |
|--------|-------|-----------|
| `hafd` | persistent **data** + the domains/types that data uses | never dropped; survives HAF updates (`pg_extension_config_dump` marks each table for `pg_dump`) |
| `hive` | runtime **code**: functions, procedures, **views**, composite types | dropped and recreated on every HAF update |
| `hive_update` | update-time helper functions | - |

Apps interact with the `hive` schema (e.g. `SELECT * FROM hive.contexts;`,
`hive.blocks`), which exposes the `hafd` data through views and functions - so the data is
upgrade-stable while the access code is freely replaceable (part 01).

---

## 2. The context registry (`context_rewind/data_schema.sql`)

A **context** is the unit of app state. Core tables:

### `hafd.contexts` (`data_schema.sql:9-27`)

The per-app processing state:

| Column | Meaning |
|--------|---------|
| `name`, `schema` | context name (`hafd.context_name` domain, `:3`) and its SQL schema |
| `current_block_num` | last block the app has processed |
| `irreversible_block` | the context's view of irreversibility |
| `events_id` | cursor into `hafd.events_queue` (the last consumed event; `0` = none) |
| `fork_id` | the fork the context is on |
| `back_from_fork` | the context is recovering from a fork |
| `is_forking` | whether this context rewinds on forks (default TRUE) |
| `owner` | the role that owns the context |
| `last_active_at` | updated by `app_next_block` - basis for dead-app detection |
| `baseclass_id` | `REGCLASS` of the context base table |
| `stages`, `loop` | application-stage / loop state (part 03) |

### Supporting tables

- `hafd.contexts_attachment` (`:33`) - is a context **attached** (live, advancing) or
  detached (paused).
- `hafd.registered_tables` (`:43`) - each app table the context manages, mapped to a
  **shadow table** (`shadow_table_name`) plus its `origin_table_columns`. The shadow table
  stores undo data for rewind (part 05).
- `hafd.triggers` (`:63`) - the rewind triggers installed on each registered table
  (`trigger_name`, `function_name`).
- `hafd.contexts_log` (`application_loop/contexts_log.sql:12`) + `hafd.context_event`
  enum (`:3`) - a log of context lifecycle events.

Two enums live here too: `hafd.state_providers` (`ACCOUNTS`/`KEYAUTH`/`METADATA`, `:5`) and
`hafd.event_type` (`:7`, section 4).

---

## 3. Core data tables: the irreversible / reversible split

Every block-derived table exists in **two forms** - a final irreversible table and a
fork-tagged reversible table. The per-context views (part 01) merge them.

### Irreversible (`irreversible_blocks.sql`)

| Table | Line |
|-------|------|
| `hafd.blocks` | `:7` |
| `hafd.transactions` | `:61` |
| `hafd.transactions_multisig` | `:76` |
| `hafd.operations` | `:100` |
| `hafd.applied_hardforks` | `:113` |
| `hafd.operation_types` (catalog) | `:84` |
| `hafd.custom_json_types` (catalog) | `:93` |
| `hafd.hive_state` (+ `hafd.sync_state` enum) | `:39-44` |

### Reversible (`reversible_blocks.sql`) - mirror tables, fork-tagged

`hafd.blocks_reversible` (`:1`), `transactions_reversible` (`:14`),
`transactions_multisig_reversible` (`:28`), `operations_reversible` (`:42`),
`accounts_reversible` (`:58`), `account_operations_reversible` (`:74`),
`applied_hardforks_reversible` (`:90`).

So: blocks, transactions, transactions_multisig, operations, and applied_hardforks have
both forms; **accounts** and **account_operations** appear as reversible here and are
otherwise produced by the state providers (section 6). Reversible rows carry a `fork_id`
so a fork switch can discard the losing fork's rows. Column-level detail is part 04.

---

## 4. The events queue and forks

### `hafd.events_queue` (`events_queue.sql:6`)

The single signal channel from hived to apps - `(id BIGSERIAL, event hafd.event_type,
block_num BIGINT)`. `block_num` is **overloaded by event type** (`events_queue.sql:1-5`):

| `event` | `block_num` means |
|---------|-------------------|
| `NEW_BLOCK` | the new block number |
| `NEW_IRREVERSIBLE` | the new irreversible block |
| `BACK_FROM_FORK` | the **fork id** (not a block) |
| `MASSIVE_SYNC` | head irreversible block after a hived massive push |

An app's `hafd.contexts.events_id` is its cursor; `app_next_block` advances it and returns
the implied work (part 03). This is the "events-source" mechanism from part 01.

### `hafd.fork` (`forks.sql:1`)

`(id BIGSERIAL, block_num INT, time_of_fork TIMESTAMP)` - one row per fork switch
(`block_num` = head after reverting the fork's blocks; written when hived sends the
`back_from_fork` notification). Referenced by `contexts.fork_id` and `BACK_FROM_FORK`
events.

---

## 5. The type system

Two layers, by schema:

- **`hafd` domains** (`types/domains.sql`) - the physical column types: `account_name_type`
  `VARCHAR(16)` (`:4`), `permlink` `VARCHAR(255)` (`:7`), `memo` `VARCHAR(2048)`,
  `public_key_type`, `weight_type` `int4`, `share_type` `int8`, `signature_type`/
  `block_id_type`/`transaction_id_type`/`digest_type` `bytea`, `asset_symbol` `int8`,
  plus asset domains (`vest_amount`/`hive_amount`/`hbd_amount` `NUMERIC`,
  `irreversible_blocks.sql:1-5`).
- **`hive` composite types** (`types/types.sql`) - the structured value/operation
  representation used by views and functions: `hive.asset` (`:4`), `hive.price` (`:11`),
  `hive.legacy_hive_asset` (`:22`), `hive.beneficiary_route_type` (`:37`),
  `hive.comment_operation` (`:76`), and the operation/extension composite types. These mirror
  the protocol types (cross-ref the hive-core KB `reference/operations.md`).

---

## 6. State providers

Optional **derived state** an app can request per context (the `hafd.state_providers` enum):
`ACCOUNTS` (`state_providers/accounts.sql`), `KEYAUTH` (`keyauth.sql`), `METADATA`
(`metadata.sql`). These maintain extra tables (e.g. the account list, key authorities)
beyond the raw block data, kept fork-consistent like everything else. Detailed in part 04.

---

## 7. Notable findings

1. **`hafd` = data, `hive` = code** is the schema-level expression of the upgrade-safety
   boundary (part 01); every `hafd` table is registered with
   `pg_extension_config_dump` so it survives dump/restore and updates.
2. **Two tables per block-derived entity** (X / X_reversible) is the storage shape of
   reversibility; the merge is hidden behind per-context views, so apps see one logical
   table.
3. **The context row is the whole cursor** - block, event, and fork position live in
   `hafd.contexts`, which is why apps are stateless between `app_next_block` calls.
4. **`events_queue.block_num` is polymorphic** - reading it without the `event` type is a
   bug (a `BACK_FROM_FORK` "block_num" is a fork id).
5. **Registered table -> shadow table + trigger** is the rewind substrate set up here and
   exercised in part 05.
6. **`last_active_at`** on the context underpins dead-app auto-detach (the CI job
   `dead_app_auto_detach`).

---

## 8. Code References

| Topic | File:line |
|-------|-----------|
| context_name / state_providers / event_type | `context_rewind/data_schema.sql:3`,`:5`,`:7` |
| `hafd.contexts` | `context_rewind/data_schema.sql:9-27` |
| contexts_attachment / registered_tables / triggers | `context_rewind/data_schema.sql:33`,`:43`,`:63` |
| contexts_log | `application_loop/contexts_log.sql:3`,`:12` |
| Irreversible tables | `irreversible_blocks.sql:7`,`:61`,`:76`,`:84`,`:93`,`:100`,`:113` |
| Reversible tables | `reversible_blocks.sql:1`,`:14`,`:28`,`:42`,`:58`,`:74`,`:90` |
| events_queue (+ block_num semantics) | `events_queue.sql:1-13` |
| fork | `forks.sql:1` |
| hafd domains | `types/domains.sql`; `irreversible_blocks.sql:1-5` |
| hive composite types | `types/types.sql:4`,`:11`,`:76` |
| State providers | `state_providers/{accounts,keyauth,metadata}.sql` |

---

## 9. Open Questions (for later parts / zoom)

- **Per-column data model** of blocks/transactions/operations and the catalog tables
  (`operation_types`, `custom_json_types`), plus `account_operations` - part 04.
- **The auto-view SQL** (`blocks_views_for_contexts.sql`) that merges reversible +
  irreversible per context - part 04.
- **State-provider internals** (how `accounts`/`keyauth`/`metadata` are maintained and
  rewound) - part 04/05.
- **Shadow-table + trigger mechanics** for rewind (`context_rewind/`) - part 05.
- **`application_stages` / `application_loop_state`** on the context - part 03.
