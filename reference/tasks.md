# Task Index - developer task -> reading path

Find the task, read the path in order (compact reference first, findings only when you need
the mechanism), check the rules, verify with the recipe. Paths are relative to the KB root;
"(Section)" names a heading inside the file. Rules live in `reference/rules/`; recipes in
`reference/verify.md`.

## T01: Build, sign and broadcast a transaction (TypeScript or Python)

- Read: `wax/README.md` (Quick Lookup) -> `wax/api.md` (Entry points; Options; Calling the
  API) -> `wax/operations.md` (Building & pushing; High-level builders) ->
  `wax/transactions.md` (End-to-end; Stages; Gotchas) -> `wax/signing.md` (Provider
  abstraction; Signer packages; Keys)
- Protocol facts: the operation's entry in `operations.md` (Authority, Fields, Validation)
- Rules: WAX-003, WAX-004, WAX-005, WAX-006 (`rules/wax.md`); HC-001, HC-004, HC-007 (`rules/hive-core.md`)
- Verify: `verify.md` section 1 (the ladder), section 3 (serialization)

## T02: Display or compute asset amounts (HIVE, HBD, VESTS)

- Read: `wax/assets.md` (NaiAsset; Building; Conversions / economics helpers; waxify
  formatter) -> `constants.md` (Assets) -> `README.md` (Important Non-Obvious Facts: legacy
  wire names)
- Deeper: `research/wax/findings/04-assets-formatters.md`
- Rules: WAX-001, WAX-002 (`rules/wax.md`); HC-006 (legacy symbol names, `rules/hive-core.md`)
- Verify: `verify.md` section 3

## T03: Pick the authority level and the signing key for an operation

- Read: `operations.md` (Index Table: the Authority column; then the operation's entry) ->
  `wax/signing.md` (Authorities) -> `state-objects.md` (account_object: owner / active /
  posting / memo keys)
- Deeper: `research/hive-core/findings/03-operation-validation.md` (required authorities),
  `hardforks.md` (Key Hardfork Details: HF28 strict / mixed authorities)
- Rules: HC-001, HC-008 (`rules/hive-core.md`); WAX-003 (role key resolution, `rules/wax.md`)
- Verify: `verify.md` section 2

## T04: Send an app custom_json (ids, authority, limits, who interprets it)

- Read: `operations.md` (custom_json_operation) -> `README.md` (Important Non-Obvious Facts:
  only `"rc"` is chain-interpreted) -> `wax/operations.md` (hive_apps_operations/ for the
  follow / community / reblog builders) -> `hivemind/operations.md` (The op filter; Follow
  custom_json; Reblog custom_json; Community custom_json) -> `hivemind/README.md` (L1
  consistency: active-authority custom_jsons are invisible to hivemind)
- Limits: `constants.md` (Block / Transaction Limits)
- Rules: HC-004 (RC payer is the first operation's authority), HC-007 (size limits) (`rules/hive-core.md`); HM-006 (`rules/hivemind.md`)
- Verify: `verify.md` section 1 and 7

## T05: Vote, and estimate vote cost and value (HF28 stable votes)

- Read: `operations.md` (vote_operation: Evaluator and Notes, including votes on paid-out
  posts) -> `economics.md` (Curation; Votes to rshares (HF28+ stable vote)) ->
  `constants.md` (Rewards) -> `state-objects.md` (account_object manabars)
- Deeper: `research/hive-core/findings/04-chain-evaluators.md` (vote_evaluator),
  `research/hive-core/findings/07-economic-model.md`,
  `research/hive-core/findings/14-delayed-voting.md` (what counts as effective stake)
- Rules: HC-002, HC-003 (`rules/hive-core.md`)
- Verify: `verify.md` section 4 (hf28_tests.cpp as the executable spec)

## T06: Transfers, savings, conversions, recurrent transfers

- Read: `operations.md` (transfer_operation; transfer_to_savings_operation;
  transfer_from_savings_operation; convert_operation; collateralized_convert_operation;
  recurrent_transfer_operation) -> `economics.md` (Conversions; HBD Interest) ->
  `wax/operations.md` (complex_operations/)
- Deeper: `research/hive-core/findings/04-chain-evaluators.md` (5.1 Transfer Evaluators),
  `research/hive-core/findings/12-recurrent-transfers.md`
- Rules: HC-001, HC-012 (`rules/hive-core.md`); WAX-001 (`rules/wax.md`)
- Verify: `verify.md` section 1

## T07: Power up, power down, delegations (HP and RC)

- Read: `operations.md` (transfer_to_vesting_operation; withdraw_vesting_operation;
  set_withdraw_vesting_route_operation; delegate_vesting_shares_operation) ->
  `economics.md` (Vesting / Power Down) -> `constants.md` (Vesting / Power Down) -> `rc.md`
  (RC Delegation)
- Deeper: `research/hive-core/findings/14-delayed-voting.md`,
  `research/hive-core/findings/04-chain-evaluators.md` (2.8 Vesting Withdrawal Helpers; 2.10
  Delegation Helpers)
- Rules: HC-011, HC-004 (`rules/hive-core.md`)
- Verify: `verify.md` section 4

## T08: Check RC cost and whether an account can afford a transaction

- Read: `rc.md` (Overview; Cost Calculation; Mana Regeneration; Special Cases; API
  Endpoints) -> `api.md` (rc_api)
- Deeper: `research/hive-core/findings/08-resource-credits.md`,
  `research/hive-core/findings/15-rc-consensus.md` (why RC is mempool-only)
- Rules: HC-004 (`rules/hive-core.md`)
- Verify: `verify.md` section 1 step 3

## T09: Debug a rejected transaction (error text -> check -> fix)

- Read: `verify.md` section 1 step 5 first -> `operations.md` (the operation's Validation
  and Evaluator lines) -> `research/hive-core/findings/03-operation-validation.md` ->
  `research/hive-core/findings/04-chain-evaluators.md` (section 5, the evaluator) ->
  `research/hive-core/findings/11-validate-evaluate-gaps.md`
- If the error came from a social API call: `hivemind/serving.md` (Error contract)
- If the client raised it: `wax/README.md` (typed Wax* exceptions)
- Rules: HC-001, HC-002, HC-003, HC-010 (`rules/hive-core.md`); WAX-006, WAX-007 (`rules/wax.md`); HM-007 (`rules/hivemind.md`)

## T10: Read chain state through the API and pick the right endpoint

- Read: `api.md` (Calling Convention; Plugin Overview; database_api; condenser_api mapping;
  Key Notes) -> `wax/api.md` (Calling the API; Extending for REST / HAF endpoints) ->
  `state-objects.md` (the object you are reading)
- Deeper: `research/hive-core/findings/10-api-layer.md`
- Rules: WAX-007 (`rules/wax.md`); HC-006, HC-012 (`rules/hive-core.md`)
- Verify: call it; `verify.md` table row "Did my transaction land"

## T11: Confirm a transaction is final (deposits, withdrawals, exchanges)

- Read: `consensus.md` (Irreversibility; Block Application Sequence) -> `api.md`
  (get_dynamic_global_properties: last_irreversible_block_num; condenser_api
  get_transaction / is_known_transaction) -> `haf/README.md` (Important Non-Obvious Facts:
  reversible vs irreversible) if you index
- Deeper: `research/hive-core/findings/06-consensus-mechanisms.md`
- Rules: HC-012 (`rules/hive-core.md`); HAF-001, HAF-006 (`rules/haf.md`)
- Verify: compare the transaction's block with `last_irreversible_block_num`

## T12: Create an account (claim_account, create_claimed_account, fees)

- Read: `operations.md` (claim_account_operation; create_claimed_account_operation;
  account_create_operation) -> `constants.md` (Account Creation) -> `rc.md` (Special Cases:
  New Account RC Adjustment; Cost Calculation for resource_new_accounts) ->
  `wax/operations.md` (complex_operations/)
- Deeper: `research/hive-core/findings/04-chain-evaluators.md` (5.2 Account Evaluators),
  `research/hive-core/findings/17-witness-subsidy.md`
- Rules: HC-001, HC-004 (`rules/hive-core.md`)
- Verify: `verify.md` section 1

## T13: Build a HAF app (context, loop, views, forks, filtering)

- Read: `haf/README.md` (Quick Lookup; Important Non-Obvious Facts) -> `haf/apps.md` (The
  pattern; App API; Stages; Key behaviors) -> `haf/schema.md` (Schemas; Core tables; The
  per-context views; Events & forks; Derived data) -> `haf/forks.md` -> `haf/filtering.md`
  (Three filter axes; Use cases)
- Protocol facts for what you index: `operations.md`, `hardforks.md`
- Deeper: `research/haf/findings/03-*` (app development), `05-*` (forks), `04-*` (data model)
- Rules: HAF-001 to HAF-006 (`rules/haf.md`)
- Verify: `verify.md` section 7

## T14: Index app custom_json in HAF (custom_json type index)

- Read: `haf/schema.md` (Core tables: operations columns) -> `haf/filtering.md` ->
  `contrib/haf/2026-07-23-expand-custom-json-type-index.md` (pending addition:
  `hafd.custom_json_types`, `custom_json_type_id`, `hive.create_custom_json_type_index`) ->
  `hivemind/operations.md` (The op filter: how hivemind uses it)
- Rules: HAF-001, HAF-004 (`rules/haf.md`); HM-006 (`rules/hivemind.md`)
- Verify: `verify.md` section 7

## T15: Query social data: posts, feeds, follows, communities, notifications

- Read: `hivemind/README.md` (Quick Lookup; Important Non-Obvious Facts: API behavior) ->
  `hivemind/api.md` (bridge; condenser_api; follow_api; Response objects) ->
  `hivemind/serving.md` (Request flow; The validator; Error contract) ->
  `hivemind/schema.md` (Views; Encodings) if you query the tables
- Deeper: `research/hivemind/findings/05-bridge-api.md`, `06-legacy-apis.md`,
  `07-serving-internals.md`
- Rules: HM-001, HM-002, HM-004, HM-005, HM-007 (`rules/hivemind.md`)
- Verify: `verify.md` section 7

## T16: Interpret payout and reward numbers shown in UIs

- Read: `economics.md` (Reward Distribution; Post Payout Calculation; Author Payout Split;
  Curation) -> `hivemind/README.md` (L1 consistency: author_payout_value includes the
  beneficiary cut, is_declined is never wired) -> `hivemind/api.md` (Response objects) ->
  `state-objects.md` (comment_cashout_object)
- Deeper: `research/hivemind/findings/08-l1-consistency.md` (discoveries 4, 5, 10, 11),
  `research/hive-core/findings/07-economic-model.md`
- Rules: HM-003, HM-005 (`rules/hivemind.md`); HC-009 (`rules/hive-core.md`)
- Verify: `verify.md` section 4 and 7

## T17: Replay history correctly in an indexer (hardfork eras)

- Read: `hardforks.md` (the activation table; Key Hardfork Details) -> `hivemind/README.md`
  (L1 consistency: pre-905693 rshares scaling, HF17 cashout block, cumulative pre-HF19
  reward vops) -> `haf/README.md` (Important Non-Obvious Facts: per-block DGPO in
  hafd.blocks) -> `operations.md` (Disabled Operations)
- Deeper: `research/hive-core/findings/09-hardfork-history.md`,
  `research/hivemind/findings/08-l1-consistency.md`, `research/hivemind/findings/04-operation-semantics.md`
- Rules: HC-009, HC-002 (`rules/hive-core.md`); HAF-004 (`rules/haf.md`); HM-004 (`rules/hivemind.md`)
- Verify: `verify.md` section 5

## T18: Set up a chain you can experiment on

- Read: `verify.md` section 6 -> `constants.md` (Testnet Overrides) -> `api.md`
  (debug_node_api)
- Deeper: `research/hive-core/findings/06-consensus-mechanisms.md`,
  `research/hive-core/findings/10-api-layer.md`
- Verify: that is the point of this task
