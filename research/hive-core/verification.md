# Verification Report

- Topic: `hive-core`
- Pinned: `1.28.7` (`1584099c3054a97f02abfb4788b23f02eea98728`)
- Previous anchor: `1.28.6` (`10ac0ce94f7591b6ad80db1a23d046c9d57b6559`)
- Run: 2026-07-17
- Method: 18 parallel subagents, one per findings part, each re-verifying that part's
  citations against the pinned `1.28.7` worktree. This is the first full pass to cover the
  zoom parts (11-17) and the two prior corrections (RC `resource_new_accounts` regen share;
  chain-id literal). Line drift from the six files changed between 1.28.6 and 1.28.7 was fixed
  mechanically and re-verified against the worktree (function-boundary spot-checks all matched).

## What changed 1.28.6 -> 1.28.7 (6 files, +50/-8)

Every other source file is byte-identical, so citations into them remain valid unchanged.

| File | Insertion | Citation shift |
|------|-----------|----------------|
| `libraries/chain/database.cpp` | +3 @ old 2121 (apply_block rethrow) | old line >= 2121 -> +3 |
| `libraries/plugins/chain/chain_plugin.cpp` | +1 @ old 1046, +3 @ old 1086 (push_block rethrow, block_id local) | 1046-1085 -> +1; >= 1086 -> +4 |
| `libraries/chain/fork_database.cpp` | +8 @ old 74 (`_push_block` unlinkable_block_exception) | old line >= 74 -> +8 (the `:77-79` assert restructured to `:84-87`) |
| `libraries/chain/external_storage/rocksdb_storage_provider.cpp` | +5 @ old 49 (openDb LOG), +5 @ old 124 (createDbSchema LOG) | 49-123 -> +5; >= 124 -> +10 |
| `libraries/net/node.cpp` | ~+19 @ ~2052 (closing_connection_message) | KB cites `:564` only -> **unaffected** |
| `libraries/protocol/include/hive/protocol/config.hpp` | version value only (mainnet 1,28,6 -> 1,28,7) | **no line-count change**, all cites valid |

## Per-part results

| Part | Confirmed | Drift (fixed) | Broken/corrected (fixed) | Pre-existing (noted) |
|------|-----------|---------------|--------------------------|----------------------|
| 00 consolidated | 102 | 12 table + 6 prose | - | - |
| 01 protocol-foundation | 69 | 2 table + 6 prose | 1 (version comma-form `01:759`) | - |
| 02 operations-catalog | 23 | 0 | - | - |
| 03 operation-validation | 128 | 7 | - | - |
| 04 chain-evaluators | 128 | 8 | - | - |
| 05 state-objects | 18 | 1 | - | - |
| 06 consensus-mechanisms | 23 | 12 table + several prose | - | - |
| 07 economic-model | 29 | 5 (+ bare table/continuations) | - | - |
| 08 resource-credits | 146 | 0 | - | 3 (adjacent-line/range) |
| 09 hardfork-history | 17 | 7 | - | - |
| 10 api-layer | 20 | 0 (node.cpp unaffected) | - | 1 (appbase `src/` path) |
| 11 validate-evaluate-gaps | 14 | 7 | - | - |
| 12 recurrent-transfers | 25 | 1 | - | - |
| 13 external-storage | 23 | 4 + detached | - | - |
| 14 delayed-voting | 31 | 2 | 1 (`27`->`24` test cases) | - |
| 15 rc-consensus | 26 | 4 | 1 (`set_remove_threshold` claim) | - |
| 16 escrow-recover-gaps | 28 | 1 | - | 2 (over-broad ranges) |
| 17 witness-subsidy | 28 | 1 | - | - |

All drift was the deterministic line shift from the six files above (verified against the
worktree: `_apply_block`->2186, `apply_operation`->2725, `process_fast_confirm_transaction`->2902,
`migrate_irreversible_state`->3069, `_push_block`->73, `set_max_size`->154, `fetch_branch_from`->298,
`reindex_internal`->1226, comment-archive option->1515, RocksDB LOG->49-53 - all exact).

## Corrections applied beyond line drift

- **`01:759`** (metadata): `version(1, 28, 6)` -> `0x011C0006` corrected to `version(1, 28, 7)` ->
  `0x011C0007` (comma-spaced form the version bump had missed).
- **`14`** (pre-existing content error, surfaced by the first zoom audit): the `delayed_voting_tests.cpp`
  row claimed "27 cases"; the file defines exactly **24** `BOOST_AUTO_TEST_CASE` (2 in
  `delayed_voting_proposal_tests` + 22 in `delayed_voting_tests`, worktree-verified). Corrected to 24.
- **`15`** (pre-existing content error): a row claimed both `rc_tests.cpp` and `direct_rc_delegation.cpp`
  use `set_remove_threshold`; only `direct_rc_delegation.cpp` does. Reworded.
- **`reference/api.md`** (folded-in prior correction): `17 plugins, ~175 methods` -> `18 plugins +
  jsonrpc = 19 namespaces, 198 endpoints`; condenser_api 57->62, debug_node_api 11->12 (table now sums to 198).

## Pre-existing minor imprecisions (NOT re-anchor drift; left as-is, noted for a future pass)

Unrelated to the 1.28.6->1.28.7 bump (the files are unchanged); flagged incidentally by this pass:

- **`08`**: `resource_sizes.cpp:52-53` (comment starts at 51); `rc_objects.hpp:86` (`continue;` at 87);
  `account_object.hpp:115-124` (range should reach `get_received_rc` at 127).
- **`10`**: `appbase/src/application.cpp:...` - the appbase submodule has no `src/` subdirectory
  (root-level `application.cpp`); line numbers correct once the path is fixed.
- **`16`**: `hive_operations.hpp:787-940` overshoots `change_recovery_account_operation`'s close (923);
  `account_object_multiindex.hpp:50-163` sweeps in unrelated indices (recovery indices are 50-65, 125-163).

## Bottom line

The hive-core KB is re-anchored to `1.28.7` (`1584099c3`). All citation drift from the six changed
files has been fixed and worktree-verified; the zoom parts (11-17) and the two prior corrections are
now covered by a full pass; three genuine content errors were corrected. Only six minor pre-existing
citation imprecisions (in unchanged files) remain, itemized above for a future cleanup.
