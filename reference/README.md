# Hive Blockchain Reference — Navigation Guide

Source-code-verified reference for Hive blockchain (hived). All data from hive-core release `1.28.8`.

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
- 39 object type IDs in the core enum: 37 defined in the core chain library, 1 in the metadata plugin, 1 never defined
- 28 hardforks (HF1-23 Steem-era, HF24-28 Hive-era); HF29 is defined in 1.28.8 code, inactive on mainnet ([hardforks.md](hardforks.md))
- 198 API methods: 196 in 18 API plugins plus 2 in the built-in jsonrpc namespace
- 3 native assets: HIVE (3 decimals), HBD (3 decimals), VESTS (6 decimals)

## Important Non-Obvious Facts

- **RC is non-consensus** until HF29 (defined in 1.28.8 code, inactive on mainnet): enforced for new and re-applied pending transactions and while a node produces a block, not when it applies or replays a block (Part 08, section Non-Consensus Status)
- **HIVE serializes as "STEEM"** in legacy wire format, HBD as "SBD", public key prefix is "STM"
- **No per-client API rate limiting** — must be done externally
- **Only `"rc"` custom_json ID** is chain-interpreted; all others are app-layer conventions
- **No max operations per transaction**: bounded by the transaction size, on the push path the witness-voted `maximum_block_size` minus 256 bytes (the 64KB `HIVE_MAX_TRANSACTION_SIZE` is not checked against transactions); the push path also caps `custom` / `custom_json` / `custom_binary` operations at 5 per account (mainnet) across a node's pending transactions (Part 02, section Transaction-Level Constraints)
- **Comment permlinks lost after cashout** — stored in comment_cashout_object which is deleted

## Detailed Findings

For deeper analysis with source file:line citations, see `../research/hive-core/findings/`.

## Found an error?

This KB is maintained by a pipeline that reads source code directly, but mistakes happen. If something here contradicts the code, write a contribution file in `contrib/hive-core/` — see [CONTRIBUTING.md](../CONTRIBUTING.md) for the format.
