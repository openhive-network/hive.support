# hive.support — Hive Blockchain Knowledge Base for Claude Code

## Purpose

Source-code-verified knowledge base about the Hive blockchain ecosystem, designed for Claude Code instances (and any other LLM agent) to use as authoritative reference when working on Hive projects.

**Ground truth is always the source code.** If documentation conflicts with code, the code wins.

## Quick Reference (start here)

Need to look something up? Go to `reference/`:

| I need to know... | File |
|-------------------|------|
| Operations: fields, authority, validation, behavior | `reference/operations.md` |
| State objects: fields, indices, what modifies them | `reference/state-objects.md` |
| Config constants: all consensus parameters | `reference/constants.md` |
| Economics: inflation, rewards, interest, conversions | `reference/economics.md` |
| Consensus: block production, witnesses, forks, LIB | `reference/consensus.md` |
| API endpoints: methods, parameters, returns | `reference/api.md` |
| Resource Credits: cost calculation, mana, delegation | `reference/rc.md` |
| Hardfork history: what changed when | `reference/hardforks.md` |

The table above is the **protocol** layer (hive-core release `1.28.8`).

**Doing a task** ("build and broadcast a transfer", "display an asset", "build a HAF app",
"debug a rejected transaction")? Start at `reference/tasks.md`: it gives the ordered reading
path across topics, the rules to check and how to verify.

**Reviewing or writing code**? Read `reference/rules/` first (verified best practices and
traps with evidence; ids `HC-`, `WAX-`, `HAF-`, `HM-`), then the topic reference.

**Need to prove a claim instead of asserting it**? `reference/verify.md` maps claim types to
the tool that observes the behavior (wax offline validation, `verify_authority`, `rc_api`, a
test chain, replay, unit tests, HAF SQL).

**Using the wax client library** (build / sign / broadcast / API)? Start at
`reference/wax/README.md` (anchored to wax `2.0.2`): entry points & API
(`reference/wax/api.md`), operations & builders (`reference/wax/operations.md`),
transaction lifecycle (`reference/wax/transactions.md`), assets & `waxify`
(`reference/wax/assets.md`), signing & signers (`reference/wax/signing.md`).

**Using HAF** (the SQL indexing layer / building a HAF app)? Start at
`reference/haf/README.md` (anchored to HAF `1.28.6`): architecture & indexing
(`reference/haf/internals.md`), schema & data model (`reference/haf/schema.md`), building an
app (`reference/haf/apps.md`), forks & reversibility (`reference/haf/forks.md`), filtering
(`reference/haf/filtering.md`).

**Using Hivemind** (the social API: posts, follows, communities, notifications)?
Start at `reference/hivemind/README.md` (anchored to hivemind `1.28.6`):
architecture & deployment (`reference/hivemind/architecture.md`), schema
(`reference/hivemind/schema.md`), sync internals (`reference/hivemind/sync.md`),
operation semantics (`reference/hivemind/operations.md`), API methods
(`reference/hivemind/api.md`), serving internals (`reference/hivemind/serving.md`).

## Key Facts

- 3-second blocks, 21 witnesses, DPoS consensus
- 50 regular + 43 virtual = 93 operations
- 3 native assets: HIVE (3 dec), HBD (3 dec), VESTS (6 dec)
- 28 hardforks active on mainnet, HF28 the latest; HF29 is defined in 1.28.8 code, inactive on mainnet (`reference/hardforks.md`)
- RC is non-consensus until HF29: enforced for new and re-applied pending transactions and while producing a block, not when applying or replaying blocks (`research/hive-core/findings/08-resource-credits.md`, section Non-Consensus Status)
- Legacy wire format: HIVE="STEEM", HBD="SBD", prefix="STM"
- No per-client API rate limiting in hived
- Only `"rc"` custom_json ID is chain-interpreted

## Structure

```
hive.support/
|-- CLAUDE.md              <- You are here
|-- reference/             <- COMPACT LOOKUP DOCS (start here)
|   |-- README.md          <- Navigation guide (protocol layer)
|   |-- tasks.md           <- Developer task -> reading path across topics
|   |-- verify.md          <- Claim type -> the tool that checks it
|   |-- rules/             <- Verified best-practice rules and traps (per topic)
|   |-- operations.md      <- All 93 operations
|   |-- state-objects.md   <- All state objects
|   |-- constants.md       <- All config constants
|   |-- economics.md       <- Economic model
|   |-- consensus.md       <- Consensus mechanisms
|   |-- api.md             <- API endpoints
|   |-- rc.md              <- Resource Credits
|   |-- hardforks.md       <- Hardfork history
|   |-- wax/               <- wax client library (README + 5 area docs)
|   |-- haf/               <- HAF framework (README + 5 area docs)
|   +-- hivemind/          <- Hivemind social API (README + 6 area docs)
|-- research/
|   |-- hive-core/findings/  <- DETAILED ANALYSIS (source file:line citations)
|   |-- wax/findings/
|   |-- haf/findings/
|   +-- hivemind/findings/
|-- evals/                 <- Benchmark items + run reports (does the KB help an agent?)
|-- mcp/                   <- Dependency-free MCP server serving this KB to any agent
|-- contrib/               <- FEEDBACK -- write here to improve the KB
+-- .claude/
    |-- settings.json      <- Agent and skill configuration
    |-- agents/            <- Hive-specialized agents
    +-- skills/            <- Hive slash commands
```

**reference/** = compact lookup tables for quick answers
**research/<topic>/findings/** = detailed analysis with source code citations for deep investigation

## When to Use What

- **Quick lookup** (what fields does transfer_operation have?) -> `reference/operations.md`
- **A task** (how do I broadcast a transfer with wax?) -> `reference/tasks.md`
- **Code review / "should I"** -> `reference/rules/<topic>.md`
- **Prove it** (will this transaction pass?) -> `reference/verify.md`
- **Deep investigation** (how exactly does the vote evaluator handle HF25 curation penalties?) -> `research/hive-core/findings/04-chain-evaluators.md`
- **Verify a claim** (is X really true?) -> Read the source code at the file:line cited in findings
- **Found an error?** -> Write a contribution file in `contrib/<topic>/` (see `CONTRIBUTING.md`)

## Agents and Skills

### Agents

- **hive-researcher** — Investigate Hive questions deeply using the KB (routes "how do I" questions through `reference/tasks.md`). Writes contrib notes when it discovers gaps.
- **hive-reviewer** — Code review specialized for Hive projects. Reads `reference/rules/` first, then checks operations, state, RC, economics, indexing and social-API semantics. Writes contrib notes when it finds KB inconsistencies.

### Skills (slash commands)

- `/hive-lookup <query>` — Quick lookup against reference docs (all topics)
- `/hive-verify <claim>` — Verify a claim about Hive behavior against the KB
- `/hive-op <operation_name>` — Complete documentation for a specific operation

Producer-side skills (`/forge-*`: `expand`, `zoom`, `improve`, `distill`, `audit`, `contrib`, `eval`, `publish`) maintain the KB; `/forge-eval` runs the `evals/` benchmark.

## Any agent, not only Claude Code

`mcp/hive_support_mcp.py` is a read-only MCP server (Python standard library only) that
serves this KB to any MCP client: `hive_tasks`, `hive_operation`, `hive_rules`,
`hive_search`, `hive_read`, `hive_index`. See `mcp/README.md`.

## Measuring it

`evals/` holds benchmark questions with verified expected answers and forbidden answers,
derived from contrib corrections, triaged open questions and the non-obvious facts of each
topic. `/forge-eval` answers each item with and without the KB using the same model and
grades both; reports live in `evals/results/`. A KB-condition miss is a KB gap to fix.

## Contributing to the Knowledge Base

Found something wrong or missing? Write a contribution file to `contrib/<topic>/`:

```
contrib/<topic>/YYYY-MM-DD-<source>-<slug>.md
```

See `contrib/README.md` for the format. Contributions are reviewed and incorporated into future KB revisions. Do not edit `reference/` or `research/` files directly.

## Research Coverage

### hive-core (Complete)
10-part source-level analysis of hived, completed 2026-04-04, plus 7 zoom parts. Anchored to hived `1.28.8` (`274384a8a`).

| Part | Focus |
|------|-------|
| 00 | Consolidated summary and triaged findings |
| 01 | Protocol Foundation — Types, Assets, Config Constants |
| 02 | Operations Catalog — All 93 Operations |
| 03 | Operation Validation Rules |
| 04 | Chain Evaluators — How Operations Modify State |
| 05 | State Objects — Blockchain Database Schema |
| 06 | Consensus — Blocks, Witnesses, Forks |
| 07 | Economic Model — Rewards, Inflation, Conversions |
| 08 | Resource Credits System |
| 09 | Hardfork History |
| 10 | API Layer — Endpoints and Data Access |
| 11-17 | Zooms: validate/evaluate gaps, recurrent transfers, external storage, delayed voting, RC consensus, escrow/recovery gaps, witness subsidy |

### wax (Complete)
7-part source-level analysis of the wax client library, completed 2026-06-20.
Anchored to wax `2.0.2` (`c9c4918a`, npm `latest`), TypeScript-first. Documents wax's
own surface (build/sign/broadcast/API) and cross-references the hive-core KB for
protocol semantics rather than re-deriving them.

| Part | Focus |
|------|-------|
| 01 | Architecture & entry points (WASM/Cython; WaxBaseApi -> HiveChainApi) |
| 02 | Operations surface (proto oneof; 90 ops = 47 broadcastable + 43 virtual) |
| 03 | Transaction lifecycle (TaPoS, expiration, serialize, sign, broadcast) |
| 04 | Assets & formatters (NaiAsset, economics helpers, waxify) |
| 05 | Signing & signers (provider abstraction; beekeeper/keychain/metamask/peakvault) |
| 06 | Chain/API client (JSON-RPC + REST callers, extend/extendRest, broadcast) |
| 07 | Complex operations (complex_operations/ + hive_apps_operations/) |

### HAF (Complete)
7-part source-level analysis of the Hive Application Framework, completed 2026-06-24.
Anchored to HAF `1.28.6` (`222c848355`), whose embedded protocol layer is hive-core `1.28.6`
(`10ac0ce94`), an earlier hive-core KB anchor; the hive-core KB moved to `1.28.7` (a maintenance release
that left HAF's embedded protocol unchanged) and then to `1.28.8`, which changes the protocol layer (for example, it
defines HF29). Documents HAF's own surface (SQL indexing + the app framework).

| Part | Focus |
|------|-------|
| 01 | Architecture & dataflow (sql_serializer plugin -> Postgres -> fork manager; sync modes) |
| 02 | Fork-manager schema (hive/hafd schemas, context registry, irreversible/reversible tables) |
| 03 | App development (context lifecycle, the consume loop, the stages state machine) |
| 04 | Data model (table columns, the per-context views, impacted accounts/balances) |
| 05 | Forks & reversibility (shadow-table undo log, back_from_fork rewind) |
| 06 | Indexing internals (cache, per-type processor threads, dumpers, WAL, index management) |
| 07 | Filtering (index a subset by account / operation / body) |

### Hivemind (Complete)
8-part source-level analysis of the Hivemind social API layer, completed 2026-08-02.
Anchored to hivemind `1.28.6` (`cab9e328bf`, tag == master == release/1.28.6), which pairs
with the HAF KB's anchor (HAF `1.28.6`). Documents hivemind's own surface (the Python
indexer, the `hivemind_app` schema, and the PL/pgSQL + PostgREST API); protocol and HAF
mechanics are cross-referenced, not re-derived.

| Part | Focus |
|------|-------|
| 01 | Architecture & deployment (indexer + PostgREST/rewriter serving; images; roles; HAF context) |
| 02 | Schema & data model (21 core + staging tables, views, canonical post record, 41 HAF-managed indexes) |
| 03 | Sync internals (massive/live pipelines, two-counter model, crash-safety matrix, fills) |
| 04 | Operation semantics (17-op map, follow machine, community gating, payout mirroring, notifications) |
| 05 | Bridge API (25 methods; validator; the bridge post object; ranked-posts matrix) |
| 06 | Legacy namespaces (condenser/follow/tags/database - delegations, stubs, object differences) |
| 07 | Serving internals (error contract, utility belt, REST + dynamic OpenAPI, search/BM25, hive.*) |
| 08 | L1 consistency cross-check vs hive-core (re-derived protocol assumptions verified; treasury-accounts gap, legacy deviations) |

### Not Yet Covered
- P2P Protocol — Network layer details

## Source

- **Repository:** [hive/hive](https://gitlab.syncad.com/hive/hive) on GitLab
- **Version:** release `1.28.8` (`274384a8a`)
