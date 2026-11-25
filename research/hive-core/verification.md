# Verification Report

- Topic: `hive-core`
- Pinned: `1.28.8` (`274384a8adddf54b69965a7fd43d8eb0ddda7701`)
- Previous anchor: `1.28.7` (`1584099c3054a97f02abfb4788b23f02eea98728`)
- Run: 2026-10-15 to 2026-11-24
- Method:
  1. Line shift by script: every citation into code that is byte-identical between the two
     tags was renumbered mechanically (2085 numbers in 1390 ranges, 24 files) and checked: the
     cited lines at 1.28.7 are identical to the computed lines at 1.28.8.
  2. Rework per part, on Opus, from a worklist: ranges into changed code re-derived in the 1.28.8
     source, citations without an attributable file resolved, broken ranges fixed, and the text
     brought in line with 1.28.8 (each change logged with old text, new text and evidence).
  3. Independent audit per part, on Opus, with isolated inputs: citation slices that each carry
     planted wrong rows, and content audits of the part's claims that each carry one planted
     false claim. Every finding was checked by hand in the 1.28.8 source before an edit.
  4. The same rework and audit for the reference layer, the hive-core rules, the evals and the
     metadata.
  5. A final scan of every citation in the KB that resolves to hive-core.
- HF29 is defined in the 1.28.8 code and inactive on mainnet (mainnet builds support HF28 only);
  the KB describes its switches once, in Part 01, and refers to that text elsewhere.

## What changed 1.28.7 -> 1.28.8

219 commits, 647 files (+16786/-41837); non-test source 218 files (+7868/-4970); submodules
`libraries/fc`, `compression_dictionaries` and `tests_api` moved. The operation set (50 + 43) and
the API method set (198 methods) are unchanged. The areas that changed KB text:

| Area | What the KB now says | Parts |
|------|----------------------|-------|
| Versions and HF29 | mainnet version 1.28.8, testnet and mirrornet 1.29.0; `HIVE_NUM_HARDFORKS` 28 on mainnet, 29 with `USE_ALTERNATE_CHAIN_ID`; `hardfork.d/1_29.hf` and its five switches | 01, 09, 00 and cross-references |
| Hardfork block constants | `HIVE_HARDFORK_1_28_BLOCK` is the actual activation block; `HIVE_HARDFORK_1_29_BLOCK` added | 01, 09 |
| Chain objects | object headers under `detail/state/`; typed balances; private fields behind getters; two reward-fund fields removed from the global properties and the APIs; reward fund created at genesis | 01, 04, 05, 07, 09, 10, 14, 16, 17 |
| Payouts | `author_reward_operation.curators_vesting_payout` is the curation actually paid | 02, 04, 07 |
| Account creation fee | minimum and maximum defined once for all networks | 01 |
| Resource Credits | JSONL statistics, RC index headers, the testnet RC bypass removed | 08, 15 |
| Block acceptance and P2P | a block more than 1 s early is held (node policy); the net layer's handling of rejected blocks (node policy) | 06 |
| External storage | flush paths, `flush-state-interval-live`, descriptor budget | 13, 06 |
| Recurrent transfers | executions minimum checked in the evaluator, per path | 02, 03, 11, 12 |
| Escrow | escrow bodies moved into `database_market.cpp` helpers | 04, 05, 16 |
| Debug plugin | debug-plugin blocks can skip transaction reapplication, like queen blocks (test tools) | 06 |

## Per-part results

"Ranges" is the number of cited line ranges in the part that the final scan resolves to
hive-core, all unchanged at 1.28.8. "Rework" counts re-derived / resolved / fixed citation rows.
"Planted" counts the planted wrong rows and planted false claims the audit caught. "Fixed after
audit" counts the points checked by hand and corrected after the audit.

| Part | Ranges | Rework | Content changes | Planted (rows, claims) | Fixed after audit | KB commit |
|------|--------|--------|-----------------|------------------------|-------------------|-----------|
| 00 consolidated | 209 | 41 / 7 / 1 | 96 | 4/4, 3/3 | 19 | `c3ed0dffa` |
| 01 protocol-foundation | 383 | 28 / 9 / 3 | 12 | 5/5, 1/1 | 8 | `5da26b3dd` |
| 02 operations-catalog | 226 | 9 / 0 / 1 | 18 | 4/4, 1/1 | 13 | `ac1d7fb42` |
| 03 operation-validation | 194 | 8 / 3 / 1 | 39 | 4/4, 1/1 | 10 | `b29797d16` |
| 04 chain-evaluators | 305 | 50 / 12 / 6 | 74 | 6/6, 2/2 | 20 | `3b0e56702` |
| 05 state-objects | 350 | 70 / 1 / 8 | 72 | 6/6, 2/2 | 17 | `247933c1f` |
| 06 consensus-mechanisms | 462 | 43 / 77 / 24 | 57 | 8/8, 2/2 | 20 | `f48c67b83` |
| 07 economic-model | 559 | 153 / 31 / 47 | 59 | 10/10, 2/2 | 17 | `9750b5cfe` |
| 08 resource-credits | 290 | 46 / 3 / 5 | 74 | 6/6, 2/2 | 18 | `11d524c2b` |
| 09 hardfork-history | 345 | 35 / 15 / 4 | 46 | 6/6, 2/2 | 10 | `faf076f85` |
| 10 api-layer | 232 | 1 / 44 / 7 | 30 | 4/4, 1/1 | 9 | `80bbf0c24` |
| 11 validate-evaluate-gaps | 172 | 25 / 4 / 10 | 24 | 4/4, 1/1 | 8 | `40a8b1054` |
| 12 recurrent-transfers | 166 | 20 / 41 / 1 | 18 | 4/4, 1/1 | 5 | `50e746848`, `bb62eaded` |
| 13 external-storage | 279 | 37 / 3 / 11 | 19 | 6/6, 1/1 | 4 | `f382f6ad4` |
| 14 delayed-voting | 305 | 63 / 21 / 3 | 23 | 6/6, 1/1 | 12 | `335386f39` |
| 15 rc-consensus | 292 | 64 / 15 / 20 | 47 | 6/6, 2/2 | 11 | `063a892dc` |
| 16 escrow-recover-gaps | 161 | 58 / 19 / 6 | 35 | 4/4, 1/1 | 6 | `95f3543cb` |
| 17 witness-subsidy | 167 | 49 / 13 / 2 | 25 | 4/4, 1/1 | 3 | `0bf25255f` |
| Reference layer, rules, evals, metadata (17 files) | 270 | - | 281 | all, all | about 50 | `f27e63111` |

The "fixed" column of Rework includes confirm rows found already wrong at 1.28.7. Follow-up
commits corrected text in other parts that a later part's rework or audit showed to be wrong
(`af105063a`, `7a1b8e7be`, `36d09e2d0`, `38d41cb36`, `0977ce185`, `5e59e341c`, `0da29e56a`,
`ada1e332f`). Per-change logs, audit rows and audit outputs are kept with the producer's notes.

## Errors older than 1.28.8

Many corrections were not caused by the release: the reworks and audits found text that was already
wrong at 1.28.7, among them hardfork details (HF6, HF7, HF9, HF14, HF16, HF19, HF23), API parameter names,
return wrappers and error codes, transport defaults, the testnet chain id (the hash of the
fc-packed string), transaction size and signature limits, RC payer selection, HBD interest timing,
conversion and DHF details, and many line ranges that pointed a few lines off.
The six minor imprecisions that the 1.28.7 report left open (Parts 08, 10 and 16) are corrected.

## Final scan

- 35 KB files carry 5399 line ranges that resolve to hive-core. At 1.28.8: 5398 unchanged and
  attributed to one file; 0 broken; 0 unparseable or unattributed in the hive-core files.
- The one remaining range is a wax research citation (`config.hpp:69`, the testnet chain id),
  which names two files of that basename. The wax KB stays anchored at wax 2.0.2 and its citations
  into hive-core stay at their 1.28.7 lines until the wax pass; the same holds for the 13 ranges
  in hivemind part 08, which the hivemind pass re-checks.
- Read by hand at 1.28.8 (config, Dockerfile, template and build files, which the scanner parses
  only in part):
  `contrib/config-for-docker.ini:6-26`, `:57-58`; `doc/example_config.ini:3-21`, `:50-51`;
  `docker/exchange/config.ini:10-18`; `Dockerfile:184`;
  `libraries/plugins/apis/documentation/Dockerfile:5-12`, `:23-24`;
  `libraries/manifest/templates/plugins/mf_plugins.cpp.j2:14-16`;
  `libraries/utilities/git_revision.cpp.in:31-38`; `tests/python/hive-local-tools/pyproject.toml:34`.

## Limits

- The scan proves that each citation points at the same code it pointed at, or at re-derived
  code, not that the sentence around it is true. Content rests on the per-part reworks and audits;
  the content audits read the claims of each part, but an audit is a check, not a proof.
- Nothing in this pass was run on a node except where a part says so; behaviour claims come from
  reading the 1.28.8 source and its unit tests.

## Bottom line

The hive-core KB is re-anchored to `1.28.8` (`274384a8a`). Every citation into hive-core resolves
at 1.28.8, every part and the reference layer were reworked and independently audited on Opus,
and every planted error was caught.
