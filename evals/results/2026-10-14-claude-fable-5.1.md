# Eval run 2026-10-14 - Claude Fable 5.1, with vs without the KB

- **Date**: 2026-10-14
- **Model**: Claude Fable 5.1 (`claude-fable-5-1`), effort max, same model for answering both conditions and for grading
- **KB state**: branch `add/rules-evals-mcp` at `dc15d350c` (hive-core 1.28.7, wax 2.0.2, HAF 1.28.6, hivemind 1.28.6; rules, tasks and verify layers present)
- **Items**: 53 (hive-core 25, wax 10, haf 8, hivemind 10); answer batches of 8-10 items per subagent; graders blinded (A/B order randomized per item, seed 20261014)
- **Conditions**: *baseline* = closed book, no tools, own knowledge, told to say when unsure; *KB* = read-only access to `CLAUDE.md`, `README.md`, `reference/`, `research/`, `contrib/` of this checkout (no source worktrees, no web), asked to cite the files used

## Headline

| Topic | Items | Baseline pass / fail / abstain | KB pass / fail / abstain |
|---|---|---|---|
| hive-core | 25 | 18 / 7 / 0 | 25 / 0 / 0 |
| wax | 10 | 5 / 5 / 0 | 10 / 0 / 0 |
| haf | 8 | 5 / 3 / 0 | 8 / 0 / 0 |
| hivemind | 10 | 5 / 5 / 0 | 10 / 0 / 0 |
| **all** | 53 | **33** / 20 / 0 (62%) | **53** / 0 / 0 (100%) |
| all, excluding the 1 `leak_risk` item | 52 | 33 (63%) | 52 (100%) |

| Kind | Items | Baseline pass | KB pass |
|---|---|---|---|
| lookup | 21 | 14 (67%) | 21 (100%) |
| reasoning | 11 | 4 (36%) | 11 (100%) |
| trap | 21 | 15 (71%) | 21 (100%) |

- KB-condition failures: **none**. Baseline-pass-but-KB-fail regressions: **none**. KB answers citing files that do not exist: **none** (every cited path checked on disk).
- Abstains: **0 in both conditions**. The closed-book model never said "I don't know"; every one of its 20 misses is a confidently stated wrong claim (see the list below). That is the failure mode the KB exists for.

## What the model gets wrong about Hive without the KB

Grader's one-line reason per closed-book failure (the forbidden or contradicted claim is what a developer's agent would have told them).

| Item | Topic | Kind | What the closed-book answer got wrong |
|---|---|---|---|
| HC-E003 | hive-core | trap | Although it correctly says the block is valid, it commits (with a hedge) to the forbidden claim that the debit is not floored at zero and current_mana can go negative until it regenerates. |
| HC-E004 | hive-core | trap | Answers Yes, claiming active/owner signatures satisfy posting requirements with no hardfork change and only mixing is forbidden, which are both forbidden claims and contradict the HF28 strict-authority rule (missing_posting). |
| HC-E013 | hive-core | lookup | Answers yes and asserts the maximum expiration is the 1-hour HIVE_MAX_TIME_UNTIL_EXPIRATION cap, which is the forbidden claim and contradicts the HF28 24-hour limit. |
| HC-E021 | hive-core | reasoning | Names HIVE_MAX_UNDO_HISTORY = 10000 as the hard upper bound and theoretical cap on reorg depth, contradicting the expected MAX_BLOCK_REORDERING = 1024 fork-database cap (10000 is only the head - LIB halt threshold), which it omits entirely. |
| HC-E023 | hive-core | reasoning | Asserts the forbidden proportional band (20%-30% thresholds giving hbd_print_rate = 80%) and claims collateralized_convert works normally at 22%, contradicting the expected print rate of 0 and the hbd_print_rate > 0 gate. |
| HC-E024 | hive-core | reasoning | Asserts the forbidden claim that both the upvote and the downvote fail for zero rshares ('Voting weight is too small'), and its hedge still commits to that wrong claim. |
| HC-E025 | hive-core | reasoning | Asserts the forbidden claim that the transaction is invalid because posting and active operations cannot share a transaction, contradicting the expected HF28 validity. |
| WAX-E003 | wax | lookup | Commits to apiTimeout = 5000 ms (hedged but asserted), contradicting the expected default of 2000 ms. |
| WAX-E004 | wax | trap | Correct on REST (nothing predefined, use the instance returned by extendRest) but asserts account_history_api is among the shipped chain.api APIs (with an open-ended list), contradicting the expected closed curated set of five. |
| WAX-E005 | wax | trap | Answers Yes and asserts the expiration is fixed at createTransaction() from the node's head block time, which are two forbidden claims. |
| WAX-E007 | wax | lookup | Counts are right but it commits (hedged) to pow/pow2/report_over_production as the missing ops and explicitly claims custom_binary and reset_account/set_reset_account have protos and builders, contradicting expected. |
| WAX-E008 | wax | lookup | Commits to four signer packages, omitting @hiveio/wax-signers-external, and gives for() signatures that differ from the expected Provider.for(chainOrBase, backend, pubKeyOrAccount, role?) pattern. |
| HAF-E003 | haf | trap | Commits to the wrong claim that HAF 1.28.6 has no custom_json_type_id column at all, omits the hive.create_custom_json_type_index opt-in entirely, and recommends parsing body->>'id' with an expression index in the app schema, which is the forbidden workaround. |
| HAF-E006 | haf | lookup | Asserts the forbidden claim that the low 8 bits of id hold op_type_id (id = block_num << 32 / pos << 8 / op_type_id, operation_id_to_type_id = id & 0xFF) and that the table has no op_type_id column, contradicting the /32-bit block_num/32-bit sequence/ encoding with the type in op_type_id. |
| HAF-E007 | haf | reasoning | The core recommendation and consequences (irreversible-only, never rewound, no triggers or shadow tables) are right, but it commits to the wrong claim that the mode is fixed at context creation and the context must be recreated to change it, contradicting expected's hive.app_context_set_non_forking switch. |
| HM-E002 | hivemind | trap | Gets the 1000 cap and the counters right but gives the list_votes start cursor as [voter, author, permlink], contradicting the expected [author, permlink, last_voter] order. |
| HM-E006 | hivemind | lookup | Asserts the forbidden -32601 'Method not found' for an unknown method inside a known namespace and claims unknown namespaces yield the same code. |
| HM-E008 | hivemind | lookup | Asserts the forbidden claim that the maximum is 100 and that a [1:20] error means a non-stock node, never mentioning the hivemind_app.max_posts_per_call GUC with default 20. |
| HM-E009 | hivemind | reasoning | Never states that hivemind stamps real ops with the previous block's timestamp; it attributes the lag to hived head_block_time semantics and says it believes created_at is the block's own timestamp with the join wrong for another reason (the forbidden reading), so only the block_num_created join advice matches. |
| HM-E010 | hivemind | reasoning | Gets the read-time mechanism and the role -2 condition right but says bit 3 is set when reputation is negative, contradicting the expected grayed threshold (is_grayed, reputation <= -464800000000). |

## Reading the result

- The KB condition scoring 100% says the agent can **find and use** verified knowledge for questions of this shape; it does not say the KB is complete. Every item was written from KB content (contribs, triaged open questions, hub facts, findings), so this run measures retrieval and routing, not coverage of questions the KB has never seen. The next items should come from real developer questions and reviewer misses (the 2026-09-05 vote contrib is the one such source in this set: HC-E001, HC-E010, HC-E018, HC-E024).
- The baseline is the interesting number: a frontier model with no Hive context answers 62% of realistic Hive questions correctly and is wrong, with confidence, on the rest. Traps and lookups split roughly evenly; reasoning items (two facts combined) are where it fails most (4 of 11 pass).
- The same model family wrote the items, answered and graded. Grader reasons were spot-checked against the cited source lines for the hive-core failures (HC-E004, HC-E013, HC-E021, HC-E023, HC-E025) and hold. A different grader model would strengthen the claim.
- One item (HC-E003, RC non-consensus and the mana floor) carries `leak_risk` because `CLAUDE.md` states "RC is non-consensus"; the baseline still failed it (on the mana floor), so the leak did not help.
- Cost: 12 answer subagents and 6 grader subagents; closed-book batches took 4 to 35 minutes each, open-book batches 3 to 6 minutes, graders about 2 minutes.

## Triage and next steps

- No KB-condition failure to triage this run.
- Add items from outside the KB's own text: questions asked in support channels, reviewer findings on real MRs, the contrib notes filed on 2026-10-14 (`contrib/wax`, `contrib/haf`, `contrib/hivemind`) once digested.
- Re-run after every KB-changing MR (`/forge-eval`); a KB-condition pass rate below 100%% on existing items is a regression to investigate before merging.
- Consider a second grader model and a human spot-check sample in the next run.

## Per-item verdicts

| Item | Topic | Kind | Baseline | KB | KB files cited |
|---|---|---|---|---|---|
| HC-E001 | hive-core | trap | pass | pass | 4 |
| HC-E002 | hive-core | trap | pass | pass | 6 |
| HC-E003 | hive-core | trap | fail | pass | 4 |
| HC-E004 | hive-core | trap | fail | pass | 6 |
| HC-E005 | hive-core | trap | pass | pass | 5 |
| HC-E006 | hive-core | trap | pass | pass | 7 |
| HC-E007 | hive-core | trap | pass | pass | 6 |
| HC-E008 | hive-core | trap | pass | pass | 3 |
| HC-E009 | hive-core | trap | pass | pass | 8 |
| HC-E010 | hive-core | trap | pass | pass | 9 |
| HC-E011 | hive-core | lookup | pass | pass | 7 |
| HC-E012 | hive-core | lookup | pass | pass | 5 |
| HC-E013 | hive-core | lookup | fail | pass | 5 |
| HC-E014 | hive-core | lookup | pass | pass | 4 |
| HC-E015 | hive-core | lookup | pass | pass | 8 |
| HC-E016 | hive-core | lookup | pass | pass | 5 |
| HC-E017 | hive-core | lookup | pass | pass | 4 |
| HC-E018 | hive-core | lookup | pass | pass | 7 |
| HC-E019 | hive-core | lookup | pass | pass | 4 |
| HC-E020 | hive-core | lookup | pass | pass | 4 |
| HC-E021 | hive-core | reasoning | fail | pass | 5 |
| HC-E022 | hive-core | reasoning | pass | pass | 6 |
| HC-E023 | hive-core | reasoning | fail | pass | 5 |
| HC-E024 | hive-core | reasoning | fail | pass | 7 |
| HC-E025 | hive-core | reasoning | fail | pass | 6 |
| WAX-E001 | wax | trap | pass | pass | 6 |
| WAX-E002 | wax | lookup | pass | pass | 4 |
| WAX-E003 | wax | lookup | fail | pass | 6 |
| WAX-E004 | wax | trap | fail | pass | 6 |
| WAX-E005 | wax | trap | fail | pass | 7 |
| WAX-E006 | wax | trap | pass | pass | 9 |
| WAX-E007 | wax | lookup | fail | pass | 4 |
| WAX-E008 | wax | lookup | fail | pass | 8 |
| WAX-E009 | wax | reasoning | pass | pass | 9 |
| WAX-E010 | wax | reasoning | pass | pass | 5 |
| HAF-E001 | haf | trap | pass | pass | 5 |
| HAF-E002 | haf | trap | pass | pass | 5 |
| HAF-E003 | haf | trap | fail | pass | 7 |
| HAF-E004 | haf | lookup | pass | pass | 6 |
| HAF-E005 | haf | lookup | pass | pass | 3 |
| HAF-E006 | haf | lookup | fail | pass | 5 |
| HAF-E007 | haf | reasoning | fail | pass | 7 |
| HAF-E008 | haf | reasoning | pass | pass | 5 |
| HM-E001 | hivemind | trap | pass | pass | 8 |
| HM-E002 | hivemind | trap | fail | pass | 6 |
| HM-E003 | hivemind | trap | pass | pass | 7 |
| HM-E004 | hivemind | trap | pass | pass | 7 |
| HM-E005 | hivemind | lookup | pass | pass | 9 |
| HM-E006 | hivemind | lookup | fail | pass | 6 |
| HM-E007 | hivemind | lookup | pass | pass | 6 |
| HM-E008 | hivemind | lookup | fail | pass | 6 |
| HM-E009 | hivemind | reasoning | fail | pass | 8 |
| HM-E010 | hivemind | reasoning | fail | pass | 6 |
