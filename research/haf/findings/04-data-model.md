# HAF Part 04 - Data Model: Tables, Views, Derived Data

**Anchor:** HAF `1.28.6` (`222c848355`).
**Scope:** the per-column data model - what `hafd.blocks` / `transactions` / `operations`
actually hold, how the per-context views merge reversible + irreversible rows, and the
derived data HAF computes (impacted accounts, account-operations, impacted balances, the
state providers). The schema *inventory* and reversibility *concept* are part 02; the fork
*rewind mechanics* are part 05. Operation field semantics defer to the hive-core KB.

Paths relative to `src/hive_fork_manager/`.

---

## 1. Core tables (columns)

### `hafd.blocks` (`irreversible_blocks.sql:7-34`)

Block header **plus a per-block DGPO snapshot**:

- Header: `num` (PK), `hash`, `prev`, `created_at`, `producer_account_id`,
  `transaction_merkle_root`, `extensions` (jsonb), `witness_signature`, `signing_key`.
- DGPO at that block (`:18-31`): `hbd_interest_rate`, `total_vesting_fund_hive`,
  `total_vesting_shares`, `total_reward_fund_hive`, `virtual_supply`, `current_supply`,
  `current_hbd_supply`, `dhf_interval_ledger`.

So economics queries (HP price, supply, interest) can read the chain state *as of any
block* without replaying - a notable HAF convenience.

### `hafd.transactions` (`:61`) / `hafd.transactions_multisig` (`:76`)

`transactions`: `block_num`, `trx_in_block`, `trx_hash` (PK), `ref_block_num`,
`ref_block_prefix`, `expiration`, `signature`. `transactions_multisig`: `(trx_hash,
signature)` - the extra signatures for multi-sig transactions.

### `hafd.operations` (`:100-109`)

- `id BIGINT` - **encoded `|| 32b block_num | 32b seq ||`** (`:101`), so operation id sorts
  by block then position and embeds the block number.
- `trx_in_block`, `op_type_id` (-> `operation_types`), `op_pos`, `body_value JSONB`
  (`:106` - the operation body as JSON), `custom_json_type_id`.

### Catalog + status tables

- `hafd.operation_types` (`:84`): `id`, `name`, `is_virtual` - the catalog of every
  operation type (the hive-core KB's 50 regular + 43 virtual = 93; `is_virtual` flags them).
- `hafd.custom_json_types` (`:93`): `id`, `custom_json_id` - the catalog of seen
  `custom_json` ids (follow/rc/community/...).
- `hafd.applied_hardforks` (`:113`): `hardfork_num`, `block_num`, `hardfork_vop_id`.
- `hafd.hive_state` (`:44-53`): the single-row HAF status - `consistent_block`, `is_dirty`,
  `state` (`hafd.sync_state` enum: `START`/`WAIT`/`REINDEX_WAIT`/`REINDEX`/`P2P`/`LIVE`,
  `:39`), `pruning`, `lite_mode`, `lite_schema`.

---

## 2. The per-context views (the reversible/irreversible merge)

Each context gets auto-generated views; an app queries these and never the raw `hafd`
tables. `blocks_views_for_contexts.sql`:

- `create_context_data_view(ctx)` (`:1`) -> `{schema}.context_data_view`, exposing the
  context's `irreversible_block`, `fork_id`, and a **`reversible_range`** flag =
  `current_block_num > irreversible_block AND is_forking` (`:29`).
- `create_blocks_view(ctx)` (`:76`) -> `{schema}.blocks_view`, a `UNION ALL` of:
  - **irreversible** rows from `hafd.blocks` (`num <= irreversible_block`), and
  - **reversible** rows from `hafd.blocks_reversible` selected for *this context's fork*: for
    each `num`, the row with `MAX(fork_id) <= context.fork_id` and `num <= current_block_num`
    (`:149-156`).

The same shape produces `operations_view`, `transactions_view`, etc. So the view yields
exactly the blocks visible at the context's fork+position; a non-forking/lite context uses a
simpler variant (`:163`) with no reversible union.

> This is the payoff of the whole design: apps write ordinary SQL against one `*_view` and
> get fork-correct, reversibility-correct data for their own cursor.

---

## 3. Impacted accounts & account-operations

`hive.get_impacted_accounts(hafd.operation)` (`get_impacted_accounts.sql:1`) returns the set
of accounts an operation touches - the basis for **account-operations** indexing (the
`account_operations` table, with reversible/irreversible forms from part 02). This is HAF's
equivalent of the old account-history plugin: "give me every operation that impacted account
X", in SQL. The encoded operation `id` (block+seq) gives the ordering.

---

## 4. Impacted balances

`hive.get_impacted_balances(operation, ...)` (`get_impacted_balances.sql:10`,`:28`) returns
the balance deltas an operation causes (account / asset / amount), and
`hive.get_balance_impacting_operations()` (`:52`) is the set of operation types that move
balances. There is an `_is_hf01` / block-number variant because some balance effects are
hardfork-conditional (cross-ref the hive-core economics KB). This feeds balance-tracking
apps (e.g. balance_tracker) without re-deriving consensus math.

---

## 5. State providers (opt-in derived state)

Beyond raw block data, a context can enable **state providers** (the
`hafd.state_providers` enum, part 02) that maintain extra fork-consistent tables:

| Provider | File | Maintains |
|----------|------|-----------|
| `ACCOUNTS` | `state_providers/accounts.sql` | the account list (id <-> name), built by scanning `account_create*` ops |
| `KEYAUTH` | `state_providers/keyauth.sql` | account key authorities |
| `METADATA` | `state_providers/metadata.sql` | account (JSON) metadata |

Each provider has `start_provider_*` (create its table, e.g. `accounts.sql:4`),
`update_state_provider_*` (advance it over a block range, e.g. `accounts.sql:51`), and
`drop_state_provider_*` (`:87`). They are advanced in lockstep with the context and rewound
on forks like any registered table.

---

## 6. Notable findings

1. **Per-block DGPO is stored** (`blocks:18-31`) - point-in-time supply/price/interest is a
   column read, not a replay. Big for economics/analytics apps.
2. **Operation `id` encodes block+seq** (`operations:101`) - global ordering and block
   membership in one bigint; no join needed to sort or locate an op.
3. **Operation bodies are JSONB** (`body_value`) typed by `op_type_id` - so SQL can filter by
   type cheaply and dig into the body with JSON operators.
4. **The views are the API.** Reversibility + fork correctness are entirely inside the
   auto-generated `*_view`s (`blocks_views_for_contexts.sql`); apps never touch `_reversible`
   tables directly.
5. **Account-history and balance-tracking are first-class** via `get_impacted_accounts` /
   `get_impacted_balances` - HAF re-implements the old AH/balance plugins as SQL.
6. **State providers are opt-in** - an app only pays for the accounts/keyauth/metadata it
   asks for.

---

## 7. Code References

| Topic | File:line |
|-------|-----------|
| blocks (+ per-block DGPO) | `irreversible_blocks.sql:7-34` |
| hive_state (+ sync_state enum) | `irreversible_blocks.sql:39`,`:44-53` |
| transactions / multisig | `irreversible_blocks.sql:61`,`:76` |
| operations (id encoding, JSONB body) | `irreversible_blocks.sql:100-109` |
| operation_types / custom_json_types | `irreversible_blocks.sql:84`,`:93` |
| applied_hardforks | `irreversible_blocks.sql:113` |
| context_data_view / blocks_view (merge) | `blocks_views_for_contexts.sql:1`,`:76`,`:149-156` |
| get_impacted_accounts | `get_impacted_accounts.sql:1` |
| get_impacted_balances / balance-impacting ops | `get_impacted_balances.sql:10`,`:28`,`:52` |
| State providers | `state_providers/{accounts,keyauth,metadata}.sql` |

---

## 8. Open Questions (for later parts / zoom)

- **The view-generation SQL in full** (operations_view / transactions_view variants, the
  non-forking path) and how `op_type_id` joins to `operation_types` in queries.
- **`account_operations` exact columns** and how it is populated/indexed for AH-style
  queries.
- **State-provider rewind** - how `accounts`/`keyauth`/`metadata` tables are reverted on a
  fork (part 05).
- **`body_value` shape** - whether it is HF26 JSON or a HAF-specific form, and the
  `get_legacy_style_operation` path.
- **Pruning** (`hafd.hive_state.pruning`) - how pruned/lite mode changes the data model.
