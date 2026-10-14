# Hive Blockchain Reference — Navigation Guide

Source-code-verified reference for Hive blockchain (hived). All data from hive-core release `1.28.7`.

## Quick Lookup

| I need to know... | Read |
|-------------------|------|
| What operations exist, their fields/authority/validation | [operations.md](operations.md) |
| What state objects exist and their fields | [state-objects.md](state-objects.md) |
| All consensus constants and config values | [constants.md](constants.md) |
| How inflation, rewards, interest, conversions work | [economics.md](economics.md) |
| How blocks are produced, validated, finalized | [consensus.md](consensus.md) |
| What API endpoints exist and how to call them | [api.md](api.md) |
| How Resource Credits work and cost calculation | [rc.md](rc.md) |
| What changed at each hardfork | [hardforks.md](hardforks.md) |

## Key Numbers

- 3-second blocks, 21 witnesses (20 elected + 1 timeshare)
- 50 regular operations + 43 virtual = 93 total
- 37 state object types in chainbase
- 28 hardforks (HF1-23 Steem-era, HF24-28 Hive-era)
- 198 API methods across 18 plugins (plus the built-in jsonrpc namespace)
- 3 native assets: HIVE (3 decimals), HBD (3 decimals), VESTS (6 decimals)

## Important Non-Obvious Facts

- **RC is non-consensus** — enforced at mempool only, not during block replay
- **HIVE serializes as "STEEM"** in legacy wire format, HBD as "SBD", public key prefix is "STM"
- **No per-client API rate limiting** — must be done externally
- **Only `"rc"` custom_json ID** is chain-interpreted; all others are app-layer conventions
- **No max operations per transaction** — bounded only by 64KB tx size limit
- **Comment permlinks lost after cashout** — stored in comment_cashout_object which is deleted

## Detailed Findings

For deeper analysis with source file:line citations, see `../research/hive-core/findings/`.

## Found an error?

This KB is maintained by a pipeline that reads source code directly, but mistakes happen. If something here contradicts the code, write a contribution file in `contrib/hive-core/` — see [CONTRIBUTING.md](../CONTRIBUTING.md) for the format.
