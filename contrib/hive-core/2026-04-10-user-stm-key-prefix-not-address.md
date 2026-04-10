# STM is a public key prefix, not an address prefix

- **Topic**: hive-core
- **Type**: cascade
- **Affects**: reference/README.md, research/hive-core/findings/00-consolidated.md, research/hive-core/findings/01-protocol-foundation.md
- **Source**: config.hpp:212 (`HIVE_ADDRESS_PREFIX = "STM"`)

## Description

The KB referred to "STM" as an "address prefix" in multiple places. On Hive, an address is an account name (username like `@gandalf`). Public keys (e.g., `STM7abc...`) are just keys attached to an account's authority levels — they are not addresses.

The C++ constant is named `HIVE_ADDRESS_PREFIX` which is misleading — it should be understood as a public key prefix. The constant name itself is a legacy artifact from Steem that could be improved upstream.

## Evidence

- `HIVE_ADDRESS_PREFIX` at `config.hpp:212` is used to prefix serialized public keys, not account names
- Hive accounts are identified by username, not by key — unlike Bitcoin/Ethereum where addresses derive from keys
- The `public_key_type` serialization prepends this prefix: `STM` + base58(key_data + checksum)

## Resolution

This was a cascade correction — the term "address prefix" appeared in multiple reference and findings documents, all traced to the same misleading constant name. Fixed to "public key prefix" with notes about the misleading constant.

Upstream issue filed: hive/hive (suggesting documentation or rename of `HIVE_ADDRESS_PREFIX`).
