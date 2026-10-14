# Verification Recipes - claim type -> the tool that settles it

The KB tells you what should happen and where in the source it is decided. A tool shows what
does happen. When a question can be settled by running something, run it and report the
observed result; cite the KB for the mechanism. When no tool applies, say the claim is
source-derived and cite the section and `file:line`.

Anchors: hived `1.28.7`, wax `2.0.2`, HAF `1.28.6`, hivemind `1.28.6`. Method names below are
the ones listed in `api.md`; source citations are into the pinned hived tree.

| Claim type | Authoritative check | KB background |
|------------|---------------------|---------------|
| Transaction is well-formed (fields, limits, sizes) | wax `tx.validate()` (offline protocol `validate()`) | `wax/transactions.md` (Stages); `operations.md` (Validation lines); findings hive-core 03 |
| Signatures / authority satisfied | `database_api.verify_authority`, `verify_account_authority`, `get_required_signatures`, `get_potential_signatures` | `api.md` (Authority / Validation); `wax/signing.md` (Authorities) |
| Account can afford the RC | `rc_api.find_rc_accounts`, `get_resource_pool`, `get_resource_params` | `rc.md` (Cost Calculation; Overview: RC is mempool-only) |
| Chain accepts it (stateful evaluator rules) | apply it: a test chain, or mainnet `condenser_api.broadcast_transaction_synchronous` | findings hive-core 04 (section 5, per evaluator), 11 (validate vs evaluate gaps) |
| Why a transaction was rejected | grep the quoted assert text in the pinned `libraries/chain` and `libraries/protocol` | findings 03/04/11; `hivemind/serving.md` (Error contract: hivemind fabricates the same error shape) |
| Did my transaction land, what happened | `condenser_api.get_transaction`, `is_known_transaction`, `get_ops_in_block`, `get_account_history` | `api.md` (condenser_api, account_history_api) |
| Serialization matches hived | `database_api.get_transaction_hex` vs the client's binary form | `wax/transactions.md` (Serialization forms); `README.md` (legacy wire names) |
| Numbers: vote rshares, payouts, RC cost | live: `get_dynamic_global_properties`, `get_reward_fund`, `get_current_median_history_price`, `rc_api.*`; spec: unit tests | `economics.md`; `rc.md`; `tests/unit/tests/hf28_tests.cpp` |
| Which hardfork rules apply now / at block N | `database_api.get_hardfork_properties`, `condenser_api.get_hardfork_version`; replay to N | `hardforks.md`; findings hive-core 09 |
| Which accounts / balances an op touches (indexers) | `hive.get_impacted_accounts(operation)`, `hive.get_impacted_balances(operation, ...)` | `haf/schema.md` (Derived data) |
| Social API behavior | call `bridge.*` / `condenser_api.*` on a hivemind node; `hive.get_info` for the deployed version | `hivemind/api.md`; `hivemind/serving.md` |

## 1. Will this transaction be accepted? (the ladder)

Climb until the answer is observed, not inferred.

1. **Structure.** wax `tx.validate()` runs the protocol-level `validate()` of every operation
   offline (`wax/transactions.md` > Stages; `api.md` is not needed). It catches what the
   `Validation` line of each `operations.md` entry describes (lengths, ranges, asset symbols,
   UTF-8, JSON validity) and nothing stateful. `OnlineTransaction.validate()` adds API-backed
   checks such as account existence.
2. **Authority.** `database_api.verify_authority(trx)` for a signed transaction;
   `verify_account_authority(account, signers, level)` answers "would these keys satisfy
   owner / active / posting"; `get_required_signatures(trx, available_keys)` and
   `get_potential_signatures(trx)` show which keys are needed (`api.md` > database_api >
   Authority / Validation). The required level per operation is the `Authority` line in
   `operations.md`; `custom_json` has its own model (its entry).
3. **RC.** RC is enforced only at the mempool (`rc.md` > Overview): a transaction already in a
   block was accepted regardless of RC. Before broadcasting, compare the account's
   `rc_manabar` from `rc_api.find_rc_accounts` with the cost model in `rc.md` > Cost
   Calculation; `broadcast_transaction_synchronous` reports the charged `rc_cost`.
4. **Evaluator rules** (balances, existing objects, hardfork gates, rate limits) are checked
   only when the transaction is applied. Use a test chain (section 6) when mainnet must not be
   touched. On mainnet `condenser_api.broadcast_transaction_synchronous` blocks until the
   transaction is included or expired and returns `{id, block_num, trx_num, rc_cost, expired}`;
   `broadcast_transaction` returns after mempool acceptance (`api.md` > Broadcast).
5. **Reading a rejection.** Every `HIVE_CHAIN_*_ASSERT` / `HIVE_PROTOCOL_*_ASSERT` throws an
   `fc::assert_exception` whose message is the quoted text in the source; grep the pinned
   tree for that text to land on the exact check, then use findings 03/04/11 for the
   semantics. Example: "Account does not have enough mana to downvote" is the strict downvote
   gate at `libraries/chain/hive_evaluator_social.cpp:692-694`. Hivemind's API returns errors
   shaped like hived's `assert_exception` too (`hivemind/serving.md` > Error contract), so
   first establish which service answered.

## 2. Is this the right authority level?

`verify_account_authority(account, signers, level)` with `level` in owner / active / posting
is the executable answer. The expected level is the `Authority` line of the operation's entry
in `operations.md`; mixed authorities in one transaction are allowed since HF28
(`hardforks.md` > Key Hardfork Details). On the client side `wax/signing.md` > Authorities
describes how wax resolves them.

## 3. Does my serializer match hived?

`database_api.get_transaction_hex(trx)` returns hived's binary serialization; compare it with
the client's binary form. wax has four serialization forms (HF26 JSON, HF26 binary,
API-shape JSON, legacy JSON; `wax/transactions.md` > Serialization forms). Legacy JSON uses
the wire names `STEEM` / `SBD` and the `STM` public-key prefix (`README.md` > Important
Non-Obvious Facts). The signature digest binds the chain id (`wax/README.md`); mainnet's id is
the literal `beeab0de00..00`, testnet's is `sha256("testnet")` (`constants.md`).

## 4. What are the numbers?

- **Vote cost and rshares (HF28+)**: formula in `economics.md` > Votes to rshares (HF28+
  stable vote); inputs are the account's effective vesting shares (`state-objects.md` >
  account_object) and `dynamic_global_property_object` fields. The executable spec is
  `tests/unit/tests/hf28_tests.cpp`: 49 full votes from a full bar before the round-up bites
  (`:1810-1819`), 12 full downvotes then spill into upvote mana (`:1841-1848`), a zero-stake
  account can upvote but not downvote (`:1893-1907`).
- **RC cost**: `rc.md` > Cost Calculation with live `rc_api.get_resource_params` /
  `get_resource_pool`; the account side from `find_rc_accounts`. Spec:
  `tests/unit/tests/rc_tests.cpp`, `direct_rc_delegation.cpp`.
- **Payouts**: `economics.md` > Reward Distribution and Curation with live `get_reward_fund`
  and `get_current_median_history_price`. Spec: `curation_reward_tests.cpp`,
  `operation_time_tests.cpp`.
- Other executable specs in `tests/unit/tests/`: `operation_tests.cpp` (validation and
  evaluators), `proposal_tests.cpp` (DHF), `delayed_voting_tests.cpp`, `hf23_tests.cpp`,
  `hf24_tests.cpp`, `hf26_tests.cpp`, `serialization_tests.cpp`, `undo_tests.cpp`,
  `block_tests.cpp`.

## 5. Which hardfork applies?

Now: `database_api.get_hardfork_properties` or `condenser_api.get_hardfork_version`
(`api.md`). At a historical block: the activation table in `hardforks.md`; indexers must apply
the era of the block they are processing (worked examples in hivemind findings part 08: vote
rshares scaled by 1e6 before block 905693, the HF17 cashout change at 10629455). To observe
historical behavior directly, replay (section 6) with `--stop-at-block N`.

## 6. A chain you can experiment on

- **Unit tests**: configure hived with `-DBUILD_HIVE_TESTNET=ON`, build the `chain_test`
  target, run `./tests/chain_test --run_test=<suite>/<case>` (`--list_content` lists them;
  `tests/unit/CMakeLists.txt:59-62`).
- **Functional tests**: `tests/python/functional` under pytest with the markers `testnet`,
  `mirrornet`, `mainnet_5m` (`tests/python/pytest.ini`); the node harness is the
  `hiveio-test-tools` package (`tests/python/hive-local-tools/pyproject.toml:34`).
- **Network types**: a testnet build (`BUILD_HIVE_TESTNET`) or a mirrornet build
  (`HIVE_CONVERTER_BUILD`, a mainnet clone for testing; `CMakeLists.txt:241-243`).
- **`debug_node_api`** (testing only, never on a production node; `api.md` > Plugin
  Overview): `debug_generate_blocks`, `debug_generate_blocks_until`, `debug_set_hardfork`,
  `debug_has_hardfork`, `debug_get_hardfork_property_object`, `debug_set_vest_price`,
  `debug_fail_transaction`, `debug_throw_exception`, `debug_get_head_block`,
  `debug_get_witness_schedule`, `debug_get_future_witness_schedule`, `debug_get_json_schema`
  (`libraries/plugins/apis/debug_node_api/include/hive/plugins/debug_node_api/debug_node_api.hpp:162-183`).
- **Replay** for consensus questions: `hived --replay-blockchain [--validate-during-replay]
  [--stop-at-block N | --exit-at-block N]`; `--force-replay` cleans old state first
  (`libraries/plugins/chain/chain_plugin.cpp:1519-1525`). `--validate-during-replay` turns
  the validations normally skipped during replay back on.
- Builds are heavy; run them on a dedicated build host, never on a workstation that holds
  credentials.

## 7. HAF and hivemind claims

- Which accounts or balances an operation affects: `hive.get_impacted_accounts(operation)`
  and `hive.get_impacted_balances(operation, ...)` in SQL (`haf/schema.md` > Derived data).
  This is what HAF account-tracking filters use (`haf/filtering.md`).
- Fork-correct reads: query the per-context views, never the raw `_reversible` tables
  (`haf/schema.md` > The per-context views); in `events_queue`, `block_num` is a fork id for
  `BACK_FROM_FORK` (`haf/schema.md` > Events & forks).
- Hivemind deployed version: `hive.get_info` (`hivemind/architecture.md` > Gotchas). Payout
  decline: do not read `hive_posts.is_declined` (never wired, always FALSE); infer from
  `max_accepted_payout = '0.000 HBD'` (`hivemind/README.md` > L1 consistency). Bridge vs
  condenser objects differ (`hivemind/api.md` > Response objects).

## 8. When no tool exists

Say so. Quote the KB section and its source `file:line`, name the pinned version, and label
the claim as source-derived rather than observed. If the source itself is ambiguous, write a
`contrib/` note instead of guessing.
