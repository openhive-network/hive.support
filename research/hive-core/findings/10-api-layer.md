# Findings: API Layer — Available Endpoints and Data Access

## Summary

The Hive blockchain node (hived) exposes its functionality through a modular plugin system built on the **AppBase** framework. API plugins register methods with a central **JSON-RPC 2.0** router, accessible via HTTP, HTTPS, WebSocket, and Unix socket transports. There are **17 API plugins** exposing a combined **~175 unique methods** across different namespaces, plus **7 non-API plugins** providing core infrastructure (block production, P2P networking, chain state, market tracking, etc.).

**Key numbers verified from source:**
- 17 API plugins (in `libraries/plugins/apis/`)
- ~175 total API methods (some overlap between condenser_api and specialized APIs)
- 7 non-API infrastructure plugins
- 4 transport types (HTTP, HTTPS, WebSocket, Unix socket)
- JSON-RPC 2.0 compliant with custom error codes (-32000 to -32003)
- Two-phase API registration (proxy during init, finalized at startup)

---

## Plugin Architecture

### AppBase Framework

**Source:** `libraries/appbase/`

All plugins inherit from `appbase::plugin<Impl>` (CRTP pattern). The framework manages:

- **Plugin registration** via `APPBASE_PLUGIN_REQUIRES((dep1)(dep2))` macro
- **Dependency resolution** — plugins are initialized in dependency order
- **Lifecycle management** — 4 states: `registered` -> `initialized` -> `started` -> `stopped`

**Plugin lifecycle hooks:**
1. `plugin_initialize(options)` — Setup resources, register APIs
2. `plugin_startup()` — Begin active processing
3. `plugin_finalize_startup()` — Post-startup actions (JSON-RPC finalizes API registration here)
4. `plugin_pre_shutdown()` — Ordered cleanup (webserver closes first, then p2p, then others)
5. `plugin_shutdown()` — Final cleanup

### JSON-RPC Framework

**Source:** `libraries/plugins/json_rpc/`

The `json_rpc_plugin` is the central API registry. It:
- Maintains a map of `api_name -> {method_name -> handler_function}`
- Supports two calling conventions in requests
- Provides introspection via `jsonrpc.get_methods()` and `jsonrpc.get_signature()`

**Two-phase registration:**
1. During `plugin_initialize()`: methods go into `proxy_data` (temporary)
2. During `plugin_finalize_startup()`: `proxy_data` moves to `data` (live)
3. Exception: `JSON_RPC_REGISTER_EARLY_API` registers directly to `data`

**Request routing flow:**
```
HTTP/WS request (JSON string)
    -> json_rpc_plugin::call(body)
    -> Parse JSON, validate JSON-RPC 2.0 format
    -> process_params() — extract api_name + method_name
    -> find_api_method() — lookup in _registered_apis map
    -> Execute handler (with read/write lock as appropriate)
    -> Return json_rpc_response {jsonrpc, result|error, id}
```

**Two calling conventions:**

Convention 1 — Dotted method name:
```json
{"jsonrpc":"2.0", "method":"database_api.get_dynamic_global_properties", "params":{}, "id":1}
```

Convention 2 — Generic "call" with array params:
```json
{"jsonrpc":"2.0", "method":"call", "params":["database_api","get_dynamic_global_properties",{}], "id":1}
```

**JSON-RPC error codes:**
| Code | Constant | Meaning |
|------|----------|---------|
| -32700 | JSON_RPC_PARSE_ERROR | Invalid JSON |
| -32600 | JSON_RPC_INVALID_REQUEST | Malformed JSON-RPC request |
| -32601 | JSON_RPC_METHOD_NOT_FOUND | Method does not exist |
| -32602 | JSON_RPC_INVALID_PARAMS | Parameter validation failed |
| -32603 | JSON_RPC_INTERNAL_ERROR | Internal server error |
| -32000 | JSON_RPC_SERVER_ERROR | General server error |
| -32001 | JSON_RPC_NO_PARAMS | No params provided |
| -32002 | JSON_RPC_PARSE_PARAMS_ERROR | Param parsing error |
| -32003 | JSON_RPC_ERROR_DURING_CALL | Error during method execution |

### API Method Declaration Pattern

**Source:** `libraries/plugins/json_rpc/include/hive/plugins/json_rpc/utility.hpp`

Each API class uses the `DECLARE_API` macro:
```cpp
class some_api {
    DECLARE_API(
        (method_a)
        (method_b)
    )
};
```

This generates for each method:
- Method signature: `method_a_return method_a(const method_a_args& args, bool lock = false)`
- A `for_each_api()` template for visitor-based registration

Implementation uses one of three locking macros:
- `DEFINE_READ_APIS` — acquires database read lock (1-second timeout)
- `DEFINE_WRITE_APIS` — acquires database write lock
- `DEFINE_LOCKLESS_APIS` — no locking (for stateless or self-locking methods)

### WebServer Plugin

**Source:** `libraries/plugins/webserver/`

Provides 4 transport endpoints:
| Transport | Config Option | Default |
|-----------|--------------|---------|
| HTTP | `--webserver-http-endpoint` | `127.0.0.1:8090` |
| HTTPS | `--webserver-https-endpoint` | (disabled) |
| WebSocket | `--webserver-ws-endpoint` | `127.0.0.1:8091` |
| Unix Socket | `--webserver-unix-endpoint` | (disabled) |

- Thread pool size configurable: `--webserver-thread-pool-size` (default: 16)
- WebSocket supports RFC-7692 permessage-deflate compression
- Pre-shutdown order ensures webserver closes connections before other plugins stop

---

## API Reference

### condenser_api (Legacy API)

**Plugin name:** `"condenser_api"`
**Source:** `libraries/plugins/apis/condenser_api/`
**Methods:** 57
**Purpose:** Legacy API compatible with Steem-era clients. Aggregates data from 10+ underlying APIs and converts to legacy format (legacy_asset with string symbols, legacy_price, etc.).

**Dependencies:** database_api, block_api, account_history_api, account_by_key_api, network_broadcast_api, reputation_api (optional), market_history_api (optional), rc_api (optional), metadata_plugin (optional), p2p_plugin

**All methods accept `vector<variant>` (positional arguments).**

#### Version & Configuration (3 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_version` | (none) | `{blockchain_version, hive_revision, fc_revision, chain_id}` | |
| `get_config` | (none) | variant_object | Legacy symbol substitutions applied |
| `get_hardfork_version` | (none) | hardfork_version string | e.g. "1.27.0" |

#### Global State (5 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_dynamic_global_properties` | (none) | extended_dynamic_global_properties | Head block, supplies, rates, timing |
| `get_chain_properties` | (none) | api_chain_properties | Median witness props |
| `get_current_median_history_price` | (none) | legacy_price | HBD/HIVE price feed |
| `get_feed_history` | (none) | api_feed_history_object | Price feed history with min/max/median |
| `get_next_scheduled_hardfork` | (none) | scheduled_hardfork | Next HF version and time |

#### Witness Data (9 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_active_witnesses` | (include_future?: bool) | vector\<account_name\> | Optional future witness schedule |
| `get_witness_schedule` | (include_future?: bool) | api_witness_schedule_object | Shuffle list, virtual times, weights |
| `get_witnesses` | (ids: vector\<witness_id\>) | vector\<optional\<api_witness_object\>\> | By numeric ID |
| `get_witness_by_account` | (account: string) | optional\<api_witness_object\> | By owner account name |
| `get_witnesses_by_vote` | (start: string, limit: uint32) | vector\<api_witness_object\> | Descending vote order |
| `lookup_witness_accounts` | (lower_bound: string, limit: uint32) | vector\<string\> | Name pagination |
| `get_witness_count` | (none) | uint64 | Total witnesses |
| `get_reward_fund` | (name: string) | api_reward_fund_object | e.g. "post" |
| `list_rc_direct_delegations` | (start: variant, limit: uint32) | vector\<rc_direct_delegation_api_object\> | RC delegations |

#### Account Data (11 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_accounts` | (names: vector\<string\>, delayed_votes?: bool) | vector\<extended_account\> | Full account objects |
| `lookup_account_names` | (names: vector\<string\>, delayed_votes?: bool) | vector\<optional\<api_account_object\>\> | Nulls for missing |
| `lookup_accounts` | (lower_bound: string, limit: uint32) | set\<string\> | Max 1000 |
| `get_account_count` | (none) | uint64 | |
| `get_account_references` | (account) | vector\<account_id\> | **DEPRECATED** — throws exception |
| `get_account_reputations` | (name: string, limit?: uint32) | vector\<account_reputation\> | Requires reputation_api |
| `get_key_references` | (keys: vector\<public_key\>) | vector\<vector\<string\>\> | Accounts by key |
| `get_owner_history` | (account: string) | vector\<owner_authority_history\> | |
| `get_recovery_request` | (account: string) | optional\<recovery_request\> | |
| `find_rc_accounts` | (accounts: vector\<string\>) | vector\<rc_account_api_object\> | RC mana pools |
| `list_rc_accounts` | (start: string, limit: uint32) | vector\<rc_account_api_object\> | |

#### Vesting & Delegation (5 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_vesting_delegations` | (delegator: string, start: string, limit: uint32) | vector\<vesting_delegation\> | |
| `get_expiring_vesting_delegations` | (delegator: string, start: time, limit: uint32) | vector\<vesting_delegation_expiration\> | |
| `get_withdraw_routes` | (account: string, type?: string) | vector\<withdraw_vesting_route\> | outgoing/incoming/all |
| `get_savings_withdraw_from` | (account: string) | vector\<savings_withdraw\> | |
| `get_savings_withdraw_to` | (account: string) | vector\<savings_withdraw\> | |

#### Escrow & Conversions (4 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_escrow` | (from: string, escrow_id: uint32) | optional\<escrow_object\> | |
| `get_conversion_requests` | (account: string) | vector\<convert_request\> | HBD->HIVE |
| `get_collateralized_conversion_requests` | (account: string) | vector\<collateralized_convert_request\> | HIVE->HBD |
| `find_recurrent_transfers` | (account: string) | vector\<recurrent_transfer\> | |

#### Blockchain Data (5 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_block_header` | (block_num: uint32) | optional\<block_header\> | Legacy serialization |
| `get_block` | (block_num: uint32) | optional\<legacy_signed_block\> | Legacy format |
| `get_ops_in_block` | (block_num: uint32, only_virtual?: bool) | vector\<api_operation_object\> | |
| `get_account_history` | (account, from: int64, limit: uint32, op_filter_low?, op_filter_high?) | map\<uint32, api_operation_object\> | Bitmask operation filtering |
| `is_known_transaction` | (txid: string) | bool | Chain or mempool |

#### Transaction Operations (6 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_transaction` | (txid: hex_string) | annotated_signed_transaction | Legacy format |
| `get_transaction_hex` | (trx: signed_transaction) | hex_string | |
| `get_required_signatures` | (trx, available_keys: set\<pubkey\>) | set\<pubkey\> | |
| `get_potential_signatures` | (trx) | set\<pubkey\> | All possible signers |
| `verify_authority` | (trx) | bool | Is properly signed? |
| `verify_account_authority` | (account, signers: set\<pubkey\>, level?: string) | bool | owner/active/posting |

#### Voting & Content (4 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_active_votes` | (author: string, permlink: string) | vector\<vote_state\> | Voter, weight, rshares, percent, time |
| `list_proposals` | (start, limit, order, direction?, status?, last_id?) | vector\<api_proposal_object\> | DHF proposals |
| `find_proposals` | (ids: vector\<int64\>) | vector\<api_proposal_object\> | |
| `list_proposal_votes` | (start, limit, order, direction?, status?) | vector\<proposal_vote_object\> | |

#### Market History (7 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_ticker` | (none) | ticker | Price, 24h change%, volume |
| `get_volume` | (none) | volume | 24h HIVE/HBD volume |
| `get_order_book` | (depth?: uint32) | order_book | Default depth 500 |
| `get_trade_history` | (start: time, end: time, limit?: uint32) | vector\<market_trade\> | Max 1000 |
| `get_recent_trades` | (limit?: uint32) | vector\<market_trade\> | Default 1000 |
| `get_market_history` | (bucket_secs: uint32, start: time, end: time) | vector\<bucket_object\> | OHLCV data |
| `get_market_history_buckets` | (none) | flat_set\<uint32\> | Available bucket sizes |

#### Transaction Broadcast (2 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `broadcast_transaction` | (trx: signed_transaction) | void | Async — returns after mempool |
| `broadcast_transaction_synchronous` | (trx: signed_transaction) | {id, block_num, trx_num, rc_cost, expired} | Blocks until confirmed or expired |

---

### database_api (Direct State Access)

**Plugin name:** `"database_api"`
**Source:** `libraries/plugins/apis/database_api/`
**Methods:** 51
**Purpose:** Comprehensive direct access to chain state objects. Uses a find/list pattern: `find_*` methods do direct lookups by key, `list_*` methods do ordered pagination.

**Pagination pattern:**
```
list_object_args_type {
    start: variant       // Cursor position (type depends on sort order)
    limit: uint32        // Max results (default 0 = server default, max 1000)
    order: sort_order_type  // Which index to iterate
}
```

**Constants:** `DATABASE_API_SINGLE_QUERY_LIMIT = 1000`

#### Global Properties (6 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_config` | void | variant_object | All consensus config constants |
| `get_version` | void | variant_object | Version info + chain_id |
| `get_dynamic_global_properties` | void | api_dynamic_global_property_object | 70+ fields: supplies, rates, timing |
| `get_witness_schedule` | include_future?: bool | api_witness_schedule_object | With optional future schedule |
| `get_hardfork_properties` | void | api_hardfork_property_object | HF history and versions |
| `get_reward_funds` | void | vector\<api_reward_fund_object\> | All reward funds |

#### Witness Methods (4 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `list_witnesses` | start, limit, order | vector\<api_witness_object\> | Orders: by_name, by_vote_name, by_schedule_time |
| `find_witnesses` | owners: vector\<string\> | vector\<api_witness_object\> | Direct lookup |
| `list_witness_votes` | start, limit, order | vector\<api_witness_vote_object\> | Orders: by_account_witness, by_witness_account |
| `get_active_witnesses` | include_future?: bool | witnesses + optional future_witnesses | |

#### Account Methods (24 methods — 12 find/list pairs)

| Pair | find_ Parameters | list_ Order Options | Object Type |
|------|-----------------|-------------------|-------------|
| accounts | names: vector\<string\> | by_name, by_proxy, by_next_vesting_withdrawal | api_account_object |
| owner_histories | owner: string | by_account | api_owner_authority_history_object |
| account_recovery_requests | accounts: vector\<string\> | by_account, by_expiration | api_account_recovery_request_object |
| change_recovery_account_requests | accounts: vector\<string\> | by_account, by_effective_date | api_change_recovery_account_request_object |
| escrows | from: string | by_from_id, by_ratification_deadline | api_escrow_object |
| withdraw_vesting_routes | account + order | by_withdraw_route, by_destination | api_withdraw_vesting_route_object |
| savings_withdrawals | account: string | by_from_id, by_complete_from_id, by_to_complete | api_savings_withdraw_object |
| vesting_delegations | account: string | by_delegation | api_vesting_delegation_object |
| vesting_delegation_expirations | account: string | by_expiration, by_account_expiration | api_vesting_delegation_expiration_object |
| hbd_conversion_requests | account: string | by_account, by_conversion_date | api_convert_request_object |
| collateralized_conversion_requests | account: string | by_account, by_conversion_date | api_collateralized_convert_request_object |
| decline_voting_rights_requests | accounts: vector\<string\> | by_account, by_effective_date | api_decline_voting_rights_request_object |

#### Content Methods (1 method)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_comment_pending_payouts` | vector\<{author, permlink}\> | vector\<comment_pending_payout_info\> | Cashout info: rshares, votes, payout timing |

#### Market/Order Methods (3 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `list_limit_orders` | start, limit, order | vector\<api_limit_order_object\> | Orders: by_price, by_account |
| `find_limit_orders` | account: string | vector\<api_limit_order_object\> | |
| `get_order_book` | limit: uint32 | order_book {asks, bids} | |

#### DHF/Proposal Methods (3 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `list_proposals` | start, limit, order, direction, status, last_id? | vector\<api_proposal_object\> | Orders: by_creator, by_start_date, by_end_date, by_total_votes |
| `find_proposals` | ids: vector\<int64\> | vector\<api_proposal_object\> | |
| `list_proposal_votes` | start, limit, order, direction, status | vector\<api_proposal_vote_object\> | Orders: by_voter_proposal, by_proposal_voter |

**Proposal status filter enum:** `all`, `inactive`, `active`, `expired`, `votable`

#### Recurrent Transfers (1 method)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `find_recurrent_transfers` | from: string | vector\<api_recurrent_transfer_object\> | |

#### Authority/Validation Methods (7 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_transaction_hex` | trx: signed_transaction | hex_string | |
| `get_required_signatures` | trx + available_keys | set\<pubkey\> | |
| `get_potential_signatures` | trx | set\<pubkey\> | |
| `verify_authority` | trx + pack_type? | bool | |
| `verify_account_authority` | account + signers + level? | bool | level: owner/active/posting |
| `verify_signatures` | hash + signatures + required_auths | bool | Low-level signature check |
| `is_known_transaction` | txid | bool | |

---

### block_api

**Plugin name:** `"block_api"`
**Source:** `libraries/plugins/apis/block_api/`
**Methods:** 3

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_block_header` | block_num: uint32 | optional\<block_header\> | Header only |
| `get_block` | block_num: uint32 | optional\<api_signed_block_object\> | Full block with transaction IDs |
| `get_block_range` | starting_block_num: uint32, count: uint32 | vector\<api_signed_block_object\> | Batch block retrieval |

---

### account_history_api

**Plugin name:** `"account_history_api"`
**Source:** `libraries/plugins/apis/account_history_api/`
**Methods:** 4

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_ops_in_block` | block_num: uint32, only_virtual?: bool, include_reversible?: bool | multiset\<api_operation_object\> | Operations in a specific block |
| `get_transaction` | id: string, include_reversible?: bool | annotated_signed_transaction | By transaction ID hex |
| `get_account_history` | account, start: uint64=-1, limit: uint32=1000, include_reversible?: bool, operation_filter_low?: uint64, operation_filter_high?: uint64 | map\<uint32, api_operation_object\> | Bitmask operation type filtering |
| `enum_virtual_ops` | block_range_begin, block_range_end, include_reversible?, group_by_block?, operation_begin?, limit?, filter? | ops + ops_by_block + next cursors | Paginated virtual operation enumeration |

**Operation filter bitmasks** (`get_account_history_op_filter_low`/`_high`): Each operation type has a bit position matching its operation ID. Set bit = include that operation type.

**`enum_virtual_ops` pagination:** Returns `next_block_range_begin` and `next_operation_begin` for cursor-based pagination across large ranges.

---

### account_by_key_api

**Plugin name:** `"account_by_key_api"`
**Source:** `libraries/plugins/apis/account_by_key_api/`
**Methods:** 1

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_key_references` | keys: vector\<public_key\> | vector\<vector\<account_name\>\> | Maps public keys to accounts (owner, active, posting, memo) |

---

### network_broadcast_api

**Plugin name:** `"network_broadcast_api"`
**Source:** `libraries/plugins/apis/network_broadcast_api/`
**Methods:** 1

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `broadcast_transaction` | trx: signed_transaction, max_block_age?: int32 | void | Validates, accepts to mempool, broadcasts to peers |

---

### rc_api (Resource Credits)

**Plugin name:** `"rc_api"`
**Source:** `libraries/plugins/apis/rc_api/`
**Methods:** 7

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_resource_params` | void | resource_names + resource_params + size_info | RC system configuration |
| `get_resource_pool` | void | resource_pool (variant_object) | Current pool levels and fill states |
| `find_rc_accounts` | accounts: vector\<string\> | vector\<rc_account_api_object\> | RC mana, max_rc, delegated/received RC |
| `list_rc_accounts` | start: variant, limit: uint32 | vector\<rc_account_api_object\> | Paginated listing |
| `list_rc_direct_delegations` | start: variant, limit: uint32 | vector\<rc_direct_delegation_api_object\> | RC delegation details |
| `get_rc_stats` | void | variant_object | Aggregate RC statistics |
| `get_rc_operation_stats` | operation: string | {count, avg_cost_rc, resource_cost, resource_cost_share, resource_usage} | Per-operation RC cost breakdown |

**rc_account_api_object fields:** account, rc_manabar (current_mana + last_update_time), max_rc_creation_adjustment, max_rc, delegated_rc, received_delegated_rc

**RC resource types:** history (bytes), tokens, market (bytes), state (hbytes), execution (nanoseconds)

---

### market_history_api

**Plugin name:** `"market_history_api"`
**Source:** `libraries/plugins/apis/market_history_api/`
**Methods:** 7

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_ticker` | void | {latest, lowest_ask, highest_bid, percent_change, hive_volume, hbd_volume} | HIVE/HBD market ticker |
| `get_volume` | void | {hive_volume, hbd_volume} | 24h trading volume |
| `get_order_book` | limit: uint32=500 | {bids, asks} | Order book depth |
| `get_trade_history` | start: time, end: time, limit: uint32=1000 | vector\<market_trade\> | Historical trades |
| `get_recent_trades` | limit: uint32=1000 | vector\<market_trade\> | Most recent trades |
| `get_market_history` | bucket_seconds: uint32, start: time, end: time | vector\<bucket_object\> | OHLCV candles |
| `get_market_history_buckets` | void | flat_set\<uint32\> | Available bucket durations (seconds) |

---

### wallet_bridge_api

**Plugin name:** `"wallet_bridge_api"`
**Source:** `libraries/plugins/apis/wallet_bridge_api/`
**Methods:** 35
**Purpose:** Convenience wrapper aggregating read-only operations from database_api, block_api, account_history_api, market_history_api, account_by_key_api, network_broadcast_api, and rc_api into a single unified API for wallet applications.

**All methods accept `variant` (positional arguments).**

| Method | Parameters | Delegates To | Notes |
|--------|-----------|-------------|-------|
| `get_version` | (none) | database_api | |
| `get_witness_schedule` | (include_future?: bool) | database_api | |
| `get_current_median_history_price` | (none) | database_api | Returns price only |
| `get_hardfork_version` | (none) | database_api | Extracts from hardfork_properties |
| `get_block` | (block_num) | block_api | |
| `get_chain_properties` | (none) | database_api | Returns median_props only |
| `get_ops_in_block` | (block_num, only_virtual?) | account_history_api | |
| `get_feed_history` | (none) | database_api | |
| `get_active_witnesses` | (include_future?) | database_api | |
| `get_withdraw_routes` | (account, type?) | database_api | outgoing/incoming/all |
| `list_my_accounts` | (public_keys: vector) | account_by_key_api + database_api | Key->account->details |
| `list_accounts` | (lower_bound, limit) | Direct chain DB | |
| `get_dynamic_global_properties` | (none) | database_api | |
| `get_account` | (name) | Direct chain DB + metadata | Returns optional |
| `get_accounts` | (names: vector) | Direct chain DB + metadata | Multiple accounts |
| `get_transaction` | (txid) | account_history_api | |
| `list_witnesses` | (lower_bound, limit) | database_api | |
| `get_witness` | (name) | database_api | Returns optional |
| `get_conversion_requests` | (account) | database_api | HBD->HIVE |
| `get_collateralized_conversion_requests` | (account) | database_api | HIVE->HBD |
| `get_order_book` | (limit) | market_history_api | |
| `get_open_orders` | (account) | Direct chain DB | |
| `get_owner_history` | (account) | database_api | |
| `get_account_history` | (account, from, limit) | account_history_api | |
| `list_proposals` | (start, limit, order, direction, status) | database_api | |
| `find_proposals` | (ids: vector) | database_api | |
| `is_known_transaction` | (txid) | database_api | |
| `list_proposal_votes` | (start, limit, order, direction, status) | database_api | |
| `get_reward_fund` | (name) | Direct chain DB | |
| `broadcast_transaction_synchronous` | (trx) | chain_plugin + p2p | Custom sync implementation |
| `broadcast_transaction` | (trx) | network_broadcast_api | Async |
| `find_recurrent_transfers` | (account) | database_api | |
| `find_rc_accounts` | (accounts: vector) | rc_api | |
| `list_rc_accounts` | (start, limit) | rc_api | |
| `list_rc_direct_delegations` | (start, limit) | rc_api | |

**Key differences from database_api:**
- Simplified return types (extracts nested fields)
- Some methods access chain DB directly (bypassing database_api for efficiency)
- Includes transaction broadcasting (database_api is read-only)
- Enriches account objects with metadata plugin data when available
- Supports dual serialization (legacy + HF26) for broadcast methods

---

### witness_api

**Plugin name:** `"witness_api"`
**Source:** `libraries/plugins/apis/witness_api/`
**Methods:** 3
**Purpose:** Control fast-confirm mode on witness nodes.

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `enable_fast_confirm` | void | void | Enable fast block confirmation |
| `disable_fast_confirm` | void | void | Disable fast block confirmation |
| `is_fast_confirm_enabled` | void | bool | Check fast-confirm status |

---

### reputation_api

**Plugin name:** `"reputation_api"`
**Source:** `libraries/plugins/apis/reputation_api/`
**Methods:** 1

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_account_reputations` | account_lower_bound: string, limit: uint32=1000 | vector\<{account, reputation}\> | Paginated reputation scores |

---

### rewards_api

**Plugin name:** `"rewards_api"`
**Source:** `libraries/plugins/apis/rewards_api/`
**Methods:** 1

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `simulate_curve_payouts` | curve: curve_id, var1: string | {recent_claims, payouts: vector\<{author, permlink, payout}\>} | Simulates payout under different reward curves |

---

### transaction_status_api

**Plugin name:** `"transaction_status_api"`
**Source:** `libraries/plugins/apis/transaction_status_api/`
**Methods:** 1

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `find_transaction` | transaction_id, expiration?: time | {status, block_num?, rc_cost?} | Transaction lifecycle tracking |

**Transaction status enum values:**
| Value | Meaning |
|-------|---------|
| `unknown` | Expiration in future, not in block or mempool |
| `within_mempool` | In mempool awaiting inclusion |
| `within_reversible_block` | Included in block, not yet irreversible |
| `within_irreversible_block` | Included in irreversible block |
| `expired_reversible` | Expired, not irreversible (could be in fork) |
| `expired_irreversible` | Expired and irreversible (final) |
| `too_old` | Transaction predates tracking window |

---

### chain_api

**Plugin name:** `"chain_api"`
**Source:** `libraries/plugins/apis/chain_api/`
**Methods:** 1

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `push_transaction` | trx: signed_transaction | {success, error?} | Direct transaction push (bypasses broadcast) |

---

### node_status_api

**Plugin name:** `"node_status_api"`
**Source:** `libraries/plugins/apis/node_status_api/`
**Methods:** 1

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_node_status` | void | {last_processed_block_num, last_processed_block_time} | Node sync status |

---

### app_status_api

**Plugin name:** `"app_status_api"`
**Source:** `libraries/plugins/apis/app_status_api/`
**Methods:** 1

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_app_status` | void | statuses (utility type) | Application-level health status |

---

### network_node_api

**Plugin name:** `"network_node_api"`
**Source:** `libraries/plugins/apis/network_node_api/`
**Methods:** 4

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_info` | void | variant_object | P2P network information |
| `add_node` | endpoint: ip::endpoint | void | Connect to a specific peer |
| `set_allowed_peers` | allowed_peers: vector\<node_id\> | void | Restrict peer connections |
| `get_connected_peers` | void | vector\<api_peer_status\> | List connected peers |

---

### debug_node_api (Testing Only)

**Plugin name:** `"debug_node_api"`
**Source:** `libraries/plugins/apis/debug_node_api/`
**Methods:** 11
**Purpose:** Testing and debugging — generates blocks locally, manipulates hardforks, inspects state. **Not for production use.**

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `debug_generate_blocks` | debug_key, count, skip?, miss_blocks? | {blocks} | Generate blocks locally |
| `debug_generate_blocks_until` | debug_key, head_block_time, generate_sparsely? | {blocks} | Generate to target time |
| `debug_get_head_block` | void | optional\<signed_block\> | |
| `debug_get_witness_schedule` | void | api_witness_schedule_object | |
| `debug_get_future_witness_schedule` | void | api_witness_schedule_object | |
| `debug_get_hardfork_property_object` | void | api_hardfork_property_object | |
| `debug_set_hardfork` | hardfork_id, hook_to_tx? | void | Force hardfork activation |
| `debug_has_hardfork` | hardfork_id | {has_hardfork: bool} | |
| `debug_get_json_schema` | void | {schema: string} | Full JSON schema |
| `debug_throw_exception` | throw_exception?: bool | void | Test error handling |
| `debug_set_vest_price` | vest_price, hook_to_tx? | void | Override VESTS price |
| `debug_fail_transaction` | tx_id | void | Force transaction failure |

---

### jsonrpc (Built-in)

**Plugin name:** `"jsonrpc"`
**Source:** `libraries/plugins/json_rpc/`
**Methods:** 2
**Purpose:** Introspection — discover available API methods and their signatures.

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `get_methods` | void | vector\<string\> | All registered "api.method" strings |
| `get_signature` | method: string | {args, ret} as variant | Method argument/return type schema |

---

## Non-API Plugins

### chain_plugin (Core)

**Source:** `libraries/plugins/chain/`
**Purpose:** Core blockchain state management — the foundational plugin all others depend on.

- Maintains blockchain database (chainbase) and consensus state
- Processes and validates blocks and transactions
- Manages block generation registration (`register_block_generator`)
- Provides database access to all other plugins via `chain::database&`
- Thread pool for async operations
- Transaction encoding detection (legacy vs HF26 serialization)
- Dependencies: webserver_plugin, json_rpc_plugin

### witness_plugin (Block Production)

**Source:** `libraries/plugins/witness/`
**Purpose:** Block production for witness nodes.

- Manages witness signing keys (public->private key map)
- Schedules block production based on witness slots
- Tracks production conditions (not_synced, not_my_turn, no_private_key, low_participation, lag, etc.)
- Fast-confirm mode for rapid block confirmation
- Dependencies: chain_plugin, p2p_plugin

### p2p_plugin (Network)

**Source:** `libraries/plugins/p2p/`
**Purpose:** Peer-to-peer network communication.

- Manages peer connections and discovery
- Broadcasts blocks and transactions to peers
- Provides network info and peer status
- Ordered pre-shutdown (closes before other plugins)
- Dependencies: chain_plugin

### market_history_plugin (Market Data)

**Source:** `libraries/plugins/market_history/`
**Purpose:** Tracks HIVE/HBD internal market trading data.

- Maintains OHLCV bucket data (configurable time intervals)
- Stores fill order history with timestamps
- Bucket sizes configurable (commonly: 60s, 300s, 3600s, 86400s)
- Hooks into fill_order virtual operations
- Dependencies: chain_plugin

### reputation_plugin

**Source:** `libraries/plugins/reputation/`
**Purpose:** Computes and maintains account reputation scores.

- Uses `generic_custom_operation_interpreter` for custom operation handling
- Processes vote operations to update reputation
- Dependencies: chain_plugin

### transaction_status_plugin

**Source:** `libraries/plugins/transaction_status/`
**Purpose:** Tracks transaction lifecycle from mempool through irreversibility.

- Hooks into `post_apply_transaction`, `pre_apply_block`, `post_apply_block` notifications
- Maintains transaction_status_object and transaction_status_block_object indexes
- Prunes old entries based on configurable retention (`--transaction-status-block-depth`)
- Dependencies: chain_plugin

### state_snapshot_plugin

**Source:** `libraries/plugins/state_snapshot/`
**Purpose:** Creates and manages blockchain state snapshots for fast sync.

- Generates point-in-time snapshots of chain state
- Enables new nodes to sync from snapshot instead of replaying all blocks
- Registers as state snapshot provider with chain_plugin
- Dependencies: chain_plugin

### Other Notable Plugins

| Plugin | Purpose |
|--------|---------|
| `account_by_key` | Indexes accounts by public key for reverse lookups |
| `account_history_rocksdb` | Stores account history in RocksDB (backend for account_history_api) |
| `block_log_info` | Block log metadata and inspection |
| `block_data_export` | Exports block data in various formats |
| `statsd` | StatsD metrics reporting (UDP) |
| `pacemaker` | Block production timing control |
| `colony` | Parallel chain processing |
| `queen` | Consensus leadership management |
| `metadata` | Account metadata storage and enrichment |
| `comment_cashout_logging` | Logs comment cashout events |
| `stats_export` | Statistics export |

---

## Plugin Dependency Graph

```
webserver_plugin <- json_rpc_plugin <- chain_plugin (CORE)
                                         ^
                    +--------------------+----------------------+
                    |                    |                      |
               p2p_plugin         market_history_plugin    reputation_plugin
                    ^              transaction_status_plugin
                    |              state_snapshot_plugin
              witness_plugin       account_by_key_plugin
                                   account_history_rocksdb_plugin

API plugins (all depend on json_rpc_plugin + their data source plugin):
  condenser_api_plugin -> database_api, block_api, account_history_api, etc.
  database_api_plugin -> chain_plugin (direct DB access)
  wallet_bridge_api_plugin -> database_api, block_api, account_history_api, etc.
  block_api_plugin -> chain_plugin
  account_history_api_plugin -> account_history_rocksdb_plugin
  rc_api_plugin -> chain_plugin (RC subsystem)
  market_history_api_plugin -> market_history_plugin
  reputation_api_plugin -> reputation_plugin
  transaction_status_api_plugin -> transaction_status_plugin
```

---

## Documentation Files

**Source:** `libraries/plugins/apis/documentation/`

| File | Size | Content |
|------|------|---------|
| `openapi.json` | 1.3 MB | Full OpenAPI/Swagger specification for all API endpoints |
| `walletapi.json` | 171 KB | Wallet API specification |
| `Dockerfile` | — | Container for serving documentation |

---

## Key Discoveries

1. **condenser_api is a thick adapter layer** — All 57 methods delegate to specialized APIs but transform data into legacy format. It maps 1:1 to underlying APIs but applies legacy_asset serialization (string-format amounts like "1.000 HIVE" instead of NAI {amount, precision, nai}).

2. **Two-phase API registration prevents startup race conditions** — Methods registered during `plugin_initialize()` go to `proxy_data`; they only become callable after `plugin_finalize_startup()` moves them to `data`. This ensures all dependencies are ready before any API method executes.

3. **Three locking strategies** — API methods use one of: read lock (most queries), write lock (state-modifying), or lockless (stateless or self-managing like broadcast). The 1-second read lock timeout prevents long-running queries from starving writers.

4. **wallet_bridge_api bypasses database_api for some methods** — `get_account`, `get_accounts`, `list_accounts`, `get_open_orders`, and `get_reward_fund` access the chain database directly instead of going through database_api, presumably for efficiency.

5. **broadcast_transaction_synchronous has custom callback tracking** — Both condenser_api and wallet_bridge_api implement their own sync broadcast by registering post_apply_block callbacks that match transaction IDs, with expiration-based cleanup.

6. **get_account_references is permanently broken** — The condenser_api method throws "Needs to be refactored for Hive" and has been disabled since the Steem->Hive fork.

7. **Operation filtering uses bitmask system** — `get_account_history` accepts two uint64 bitmasks (low + high) where each bit corresponds to an operation type ID. This allows querying for specific operation types without server-side configuration.

8. **enum_virtual_ops supports cursor-based pagination** — Returns `next_block_range_begin` and `next_operation_begin` for stateless pagination across arbitrary block ranges, with optional `group_by_block` for block-grouped output.

9. **Dual transaction serialization** — broadcast methods attempt HF26 serialization first, falling back to legacy format. This allows clients using either format to broadcast successfully.

10. **witness_api is minimal** — Only 3 methods for fast-confirm control; witness data queries go through database_api or condenser_api.

---

## Code References

| Topic | File | Key Lines/Sections |
|-------|------|--------------------|
| Plugin base class | `libraries/appbase/include/appbase/plugin.hpp` | APPBASE_PLUGIN_REQUIRES macro, state enum |
| API declaration macros | `libraries/plugins/json_rpc/include/hive/plugins/json_rpc/utility.hpp` | DECLARE_API, DEFINE_READ_APIS |
| JSON-RPC routing | `libraries/plugins/json_rpc/json_rpc_plugin.cpp` | process_params(), find_api_method(), rpc() |
| API registration | `libraries/plugins/json_rpc/include/hive/plugins/json_rpc/json_rpc_plugin.hpp` | JSON_RPC_REGISTER_API macro, visitor template |
| WebServer transports | `libraries/plugins/webserver/webserver_plugin.cpp` | handle_http_message(), handle_ws_message() |
| condenser_api methods | `libraries/plugins/apis/condenser_api/include/hive/plugins/condenser_api/condenser_api.hpp` | DECLARE_API block (57 methods) |
| database_api methods | `libraries/plugins/apis/database_api/include/hive/plugins/database_api/database_api.hpp` | DECLARE_API block (51 methods) |
| database_api args/returns | `libraries/plugins/apis/database_api/include/hive/plugins/database_api/database_api_args.hpp` | All arg/return structs, sort_order_type enum |
| database_api objects | `libraries/plugins/apis/database_api/include/hive/plugins/database_api/database_api_objects.hpp` | All api_* object definitions |
| wallet_bridge_api | `libraries/plugins/apis/wallet_bridge_api/include/hive/plugins/wallet_bridge_api/wallet_bridge_api.hpp` | DECLARE_API block (35 methods) |
| rc_api methods | `libraries/plugins/apis/rc_api/include/hive/plugins/rc_api/rc_api.hpp` | 7 methods + rc_account_api_object |
| Transaction status enum | `libraries/plugins/transaction_status/include/hive/plugins/transaction_status/transaction_status_objects.hpp` | 7-value enum |
| OpenAPI spec | `libraries/plugins/apis/documentation/openapi.json` | Full machine-readable API documentation |

---

## Discrepancies and Potential Issues

1. **condenser_api method count** — The condenser_api declares 57 methods but one (`get_account_references`) is permanently broken. Client libraries may still try to call it.

2. **Inconsistent pagination limits** — database_api uses `DATABASE_API_SINGLE_QUERY_LIMIT = 1000`, condenser_api varies per method (some max 1000, some max 500), wallet_bridge_api inherits from delegated APIs. No unified pagination standard.

3. **Optional plugin dependencies** — condenser_api's market, reputation, and RC methods silently fail or return empty if those plugins aren't enabled. No clear error distinguishes "plugin not enabled" from "no data found."

4. **witness_api name collision** — The `witness_api` plugin (3 methods for fast-confirm) should not be confused with witness-related methods in database_api and condenser_api that provide witness data queries.

5. **wallet_bridge_api has 35 methods** (counted from header) vs condenser_api's 57 — wallet_bridge_api omits market ticker/volume/trade methods, block_header, several vote/content methods, and some signature methods.

---

## Open Questions

1. **How is the OpenAPI spec generated?** — The 1.3MB `openapi.json` in the documentation directory appears comprehensive but it's unclear if it's auto-generated from source or manually maintained. Drift risk is high.

2. **What determines which plugins are enabled by default?** — The `haf_api_node` deployment likely has a default plugin list, but the core node can run with any subset. Need to check deployment configs.

3. **Is there rate limiting?** — The webserver thread pool (default 16) limits concurrency, but there's no per-client rate limiting visible in the plugin layer. This may be handled by reverse proxies in production.

4. **How does the `colony` plugin relate to the API layer?** — colony_order in pre-shutdown suggests it's significant for consensus, but its API surface is not exposed.

5. **What's the `queen` plugin?** — Referenced in the plugin directory but no API exposed. Likely internal consensus mechanism.
