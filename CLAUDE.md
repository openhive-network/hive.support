# hive.support — Hive Blockchain Knowledge Base for Claude Code

## Purpose

Source-code-verified knowledge base about the Hive blockchain ecosystem, designed for Claude Code instances to use as authoritative reference when working on Hive projects.

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

All data verified against hive-core release `1.28.6`.

## Key Facts

- 3-second blocks, 21 witnesses, DPoS consensus
- 50 regular + 43 virtual = 93 operations
- 3 native assets: HIVE (3 dec), HBD (3 dec), VESTS (6 dec)
- RC is non-consensus (mempool enforcement only)
- Legacy wire format: HIVE="STEEM", HBD="SBD", prefix="STM"
- No per-client API rate limiting in hived
- Only `"rc"` custom_json ID is chain-interpreted

## Structure

```
hive.support/
|-- CLAUDE.md              <- You are here
|-- reference/             <- COMPACT LOOKUP DOCS (start here)
|   |-- README.md          <- Navigation guide
|   |-- operations.md      <- All 93 operations
|   |-- state-objects.md   <- All state objects
|   |-- constants.md       <- All config constants
|   |-- economics.md       <- Economic model
|   |-- consensus.md       <- Consensus mechanisms
|   |-- api.md             <- API endpoints
|   |-- rc.md              <- Resource Credits
|   +-- hardforks.md       <- Hardfork history
|-- research/
|   +-- hive-core/
|       +-- findings/      <- DETAILED ANALYSIS (with source file:line citations)
|-- contrib/               <- FEEDBACK -- write here to improve the KB
+-- .claude/
    |-- settings.json      <- Agent and skill configuration
    |-- agents/            <- Hive-specialized agents
    +-- skills/            <- Hive slash commands
```

**reference/** = compact lookup tables for quick answers
**research/hive-core/findings/** = detailed analysis with source code citations for deep investigation

## When to Use What

- **Quick lookup** (what fields does transfer_operation have?) -> `reference/operations.md`
- **Deep investigation** (how exactly does the vote evaluator handle HF25 curation penalties?) -> `research/hive-core/findings/04-chain-evaluators.md`
- **Verify a claim** (is X really true?) -> Read the source code at the file:line cited in findings
- **Found an error?** -> Write a contribution file in `contrib/hive-core/` (see `CONTRIBUTING.md`)

## Agents and Skills

### Agents

- **hive-researcher** — Investigate Hive questions deeply using the KB. Writes contrib notes when it discovers gaps.
- **hive-reviewer** — Code review specialized for Hive projects. Checks operations, state, RC, economics. Writes contrib notes when it finds KB inconsistencies.

### Skills (slash commands)

- `/hive-lookup <query>` — Quick lookup against reference docs
- `/hive-verify <claim>` — Verify a claim about Hive behavior against the KB
- `/hive-op <operation_name>` — Complete documentation for a specific operation

## Contributing to the Knowledge Base

Found something wrong or missing? Write a contribution file to `contrib/hive-core/`:

```
contrib/hive-core/YYYY-MM-DD-<source>-<slug>.md
```

See `contrib/README.md` for the format. Contributions are reviewed and incorporated into future KB revisions. Do not edit `reference/` or `research/` files directly.

## Research Coverage

### hive-core (Complete)
10-part source-level analysis of hived, completed 2026-04-04.

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

### Not Yet Covered
- HAF (Hive Application Framework) — SQL layer between hived and apps
- Hivemind — Social API layer
- P2P Protocol — Network layer details

## Source

- **Repository:** [hive/hive](https://gitlab.syncad.com/hive/hive) on GitLab
- **Version:** release `1.28.6` (`10ac0ce94`)
