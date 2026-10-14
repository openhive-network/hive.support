# Hive API Reference

Source: hive-core release 1.28.7. 18 API plugins registering methods + the built-in `jsonrpc` introspection API (19 method namespaces); 198 registered endpoints. JSON-RPC 2.0.

---

## Transport

| Transport | Config Flag | Default |
|-----------|------------|---------|
| HTTP | `--webserver-http-endpoint` | `127.0.0.1:8090` |
| HTTPS | `--webserver-https-endpoint` | disabled |
| WebSocket | `--webserver-ws-endpoint` | `127.0.0.1:8091` |
| Unix Socket | `--webserver-unix-endpoint` | disabled |

Thread pool: `--webserver-thread-pool-size` (default 16). WebSocket supports permessage-deflate compression. No per-client rate limiting at the node level (handle via reverse proxy).

## Calling Convention

Two equivalent forms:

```json
{"jsonrpc":"2.0", "method":"database_api.find_accounts", "params":{"accounts":["alice"]}, "id":1}
```

```json
{"jsonrpc":"2.0", "method":"call", "params":["database_api","find_accounts",{"accounts":["alice"]}], "id":1}
```

JSON-RPC error codes: -32700 (parse), -32600 (invalid request), -32601 (method not found), -32602 (invalid params), -32603 (internal), -32000 (server), -32001 (no params), -32002 (param parse), -32003 (error during call).

---

## Plugin Overview

| Plugin | Methods | Purpose | Default Enabled? |
|--------|---------|---------|-----------------|
| database_api | 51 | Direct chain state access (find/list pattern) | Yes |
| condenser_api | 62 | Legacy API for Steem-era clients (delegates to other APIs) | Yes |
| block_api | 3 | Block retrieval | Yes |
| account_history_api | 4 | Account operation history, virtual ops enumeration | Yes (needs rocksdb plugin) |
| account_by_key_api | 1 | Reverse lookup: public key to accounts | Yes (needs account_by_key plugin) |
| network_broadcast_api | 1 | Transaction broadcast to network | Yes |
| rc_api | 7 | Resource Credits: mana, costs, delegations | Yes |
| market_history_api | 7 | Internal market OHLCV, ticker, order book | Requires market_history plugin |
| wallet_bridge_api | 35 | Unified wallet convenience API (aggregates other APIs) | Yes |
| reputation_api | 1 | Account reputation scores | Requires reputation plugin |
| rewards_api | 1 | Reward curve simulation | Explicit enable |
| transaction_status_api | 1 | Transaction lifecycle tracking | Requires transaction_status plugin |
| chain_api | 1 | Direct transaction push (bypasses broadcast) | Yes |
| node_status_api | 1 | Node sync status | Yes |
| app_status_api | 1 | Application health status | Yes |
| witness_api | 3 | Fast-confirm control (witness nodes only) | Witness nodes only |
| network_node_api | 4 | P2P peer management | Explicit enable |
| debug_node_api | 12 | Testing/debugging (NOT for production) | Never in production |
| jsonrpc | 2 | Introspection: list methods, get signatures | Always (built-in) |

---

## database_api (51 methods)

Direct access to chain state objects. Uses find/list pattern: `find_*` does direct key lookup, `list_*` does ordered pagination.

Pagination: `{start: variant, limit: uint32, order: sort_order}`. Max limit: 1000.

### Global Properties

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_config | (none) | variant_object | All consensus config constants |
| get_version | (none) | variant_object | Version info + chain_id |
| get_dynamic_global_properties | (none) | api_dynamic_global_property_object | 70+ fields: head block, supplies, rates, timing |
| get_witness_schedule | include_future?: bool | api_witness_schedule_object | Optional future schedule |
| get_hardfork_properties | (none) | api_hardfork_property_object | HF history and versions |
| get_reward_funds | (none) | vector\<api_reward_fund_object\> | All reward funds |

### Witnesses

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| find_witnesses | owners: string[] | api_witness_object[] | Direct lookup by name |
| list_witnesses | start, limit, order | api_witness_object[] | Orders: by_name, by_vote_name, by_schedule_time |
| list_witness_votes | start, limit, order | api_witness_vote_object[] | Orders: by_account_witness, by_witness_account |
| get_active_witnesses | include_future?: bool | witnesses + future_witnesses | Current (and optional future) schedule |

### Accounts (12 find/list pairs = 24 methods)

| Object | find_ Params | list_ Order Options |
|--------|-------------|-------------------|
| accounts | names: string[] | by_name, by_proxy, by_next_vesting_withdrawal |
| owner_histories | owner: string | by_account |
| account_recovery_requests | accounts: string[] | by_account, by_expiration |
| change_recovery_account_requests | accounts: string[] | by_account, by_effective_date |
| escrows | from: string | by_from_id, by_ratification_deadline |
| withdraw_vesting_routes | account + order | by_withdraw_route, by_destination |
| savings_withdrawals | account: string | by_from_id, by_complete_from_id, by_to_complete |
| vesting_delegations | account: string | by_delegation |
| vesting_delegation_expirations | account: string | by_expiration, by_account_expiration |
| hbd_conversion_requests | account: string | by_account, by_conversion_date |
| collateralized_conversion_requests | account: string | by_account, by_conversion_date |
| decline_voting_rights_requests | accounts: string[] | by_account, by_effective_date |

### Content

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_comment_pending_payouts | [{author, permlink}, ...] | comment_pending_payout_info[] | Cashout: rshares, votes, payout timing |

### Market / Orders

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| find_limit_orders | account: string | api_limit_order_object[] | Orders for account |
| list_limit_orders | start, limit, order | api_limit_order_object[] | Orders: by_price, by_account |
| get_order_book | limit: uint32 | {asks, bids} | Internal market order book |

### DHF Proposals

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| find_proposals | ids: int64[] | api_proposal_object[] | By proposal ID |
| list_proposals | start, limit, order, direction, status, last_id? | api_proposal_object[] | Orders: by_creator, by_start_date, by_end_date, by_total_votes |
| list_proposal_votes | start, limit, order, direction, status | api_proposal_vote_object[] | Orders: by_voter_proposal, by_proposal_voter |

Proposal status filter: `all`, `inactive`, `active`, `expired`, `votable`.

### Other

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| find_recurrent_transfers | from: string | api_recurrent_transfer_object[] | |

### Authority / Validation (7 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_transaction_hex | trx | hex_string | Serialize transaction |
| get_required_signatures | trx + available_keys | set\<pubkey\> | Which keys needed |
| get_potential_signatures | trx | set\<pubkey\> | All possible signers |
| verify_authority | trx, pack_type? | bool | Is properly signed? |
| verify_account_authority | account, signers, level? | bool | level: owner/active/posting |
| verify_signatures | hash, signatures, required_auths | bool | Low-level check |
| is_known_transaction | txid | bool | In chain or mempool? |

---

## condenser_api (62 methods)

Legacy API for Steem-era clients. All methods take positional args (`vector<variant>`). Returns use legacy asset format ("1.000 HIVE" strings). Delegates to database_api, block_api, account_history_api, and others internally.

**One method is permanently broken:** `get_account_references` throws "Needs to be refactored for Hive."

### condenser_api to database_api mapping

Most condenser_api methods map 1:1 to database_api equivalents with legacy serialization applied. Key differences:
- condenser_api uses positional args; database_api uses named params
- condenser_api returns legacy_asset ("1.000 HIVE"); database_api returns NAI format ({amount, precision, nai})
- condenser_api `get_accounts` returns extended_account (includes history); database_api `find_accounts` returns api_account_object

### Version and Config (3)

| Method | Parameters | Returns |
|--------|-----------|---------|
| get_version | (none) | {blockchain_version, hive_revision, fc_revision, chain_id} |
| get_config | (none) | variant_object |
| get_hardfork_version | (none) | string (e.g. "1.27.0") |

### Global State (5)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_dynamic_global_properties | (none) | extended_dynamic_global_properties | Head block, supplies, rates |
| get_chain_properties | (none) | api_chain_properties | Median witness props |
| get_current_median_history_price | (none) | legacy_price | HBD/HIVE price feed |
| get_feed_history | (none) | api_feed_history_object | Price history with min/max/median |
| get_next_scheduled_hardfork | (none) | scheduled_hardfork | Next HF version and time |

### Witnesses (9)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_active_witnesses | (include_future?: bool) | account_name[] | |
| get_witness_schedule | (include_future?: bool) | api_witness_schedule_object | |
| get_witnesses | (ids: witness_id[]) | api_witness_object?[] | By numeric ID |
| get_witness_by_account | (account: string) | api_witness_object? | |
| get_witnesses_by_vote | (start: string, limit: uint32) | api_witness_object[] | Descending vote order |
| lookup_witness_accounts | (lower_bound: string, limit: uint32) | string[] | Name pagination |
| get_witness_count | (none) | uint64 | |
| get_reward_fund | (name: string) | api_reward_fund_object | e.g. "post" |
| list_rc_direct_delegations | (start, limit) | rc_direct_delegation[] | |

### Accounts (11)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_accounts | (names: string[], delayed_votes?: bool) | extended_account[] | Full account objects |
| lookup_account_names | (names: string[], delayed_votes?: bool) | api_account_object?[] | Nulls for missing |
| lookup_accounts | (lower_bound: string, limit: uint32) | set\<string\> | Max 1000 |
| get_account_count | (none) | uint64 | |
| get_account_references | (account) | -- | DEPRECATED: throws exception |
| get_account_reputations | (name, limit?) | account_reputation[] | Requires reputation_api |
| get_key_references | (keys: public_key[]) | string[][] | Accounts using these keys |
| get_owner_history | (account: string) | owner_authority_history[] | |
| get_recovery_request | (account: string) | recovery_request? | |
| find_rc_accounts | (accounts: string[]) | rc_account[] | RC mana pools |
| list_rc_accounts | (start: string, limit: uint32) | rc_account[] | |

### Vesting and Delegation (5)

| Method | Parameters | Returns |
|--------|-----------|---------|
| get_vesting_delegations | (delegator, start, limit) | vesting_delegation[] |
| get_expiring_vesting_delegations | (delegator, start_time, limit) | vesting_delegation_expiration[] |
| get_withdraw_routes | (account, type?) | withdraw_vesting_route[] |
| get_savings_withdraw_from | (account) | savings_withdraw[] |
| get_savings_withdraw_to | (account) | savings_withdraw[] |

### Escrow and Conversions (4)

| Method | Parameters | Returns |
|--------|-----------|---------|
| get_escrow | (from, escrow_id) | escrow_object? |
| get_conversion_requests | (account) | convert_request[] |
| get_collateralized_conversion_requests | (account) | collateralized_convert_request[] |
| find_recurrent_transfers | (account) | recurrent_transfer[] |

### Blockchain Data (5)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_block_header | (block_num) | block_header? | Legacy serialization |
| get_block | (block_num) | legacy_signed_block? | Legacy format |
| get_ops_in_block | (block_num, only_virtual?) | api_operation_object[] | |
| get_account_history | (account, from, limit, op_filter_low?, op_filter_high?) | map | Bitmask operation filtering |
| is_known_transaction | (txid) | bool | |

### Transactions (6)

| Method | Parameters | Returns |
|--------|-----------|---------|
| get_transaction | (txid: hex) | annotated_signed_transaction |
| get_transaction_hex | (trx) | hex_string |
| get_required_signatures | (trx, available_keys) | set\<pubkey\> |
| get_potential_signatures | (trx) | set\<pubkey\> |
| verify_authority | (trx) | bool |
| verify_account_authority | (account, signers, level?) | bool |

### Voting and Content (4)

| Method | Parameters | Returns |
|--------|-----------|---------|
| get_active_votes | (author, permlink) | vote_state[] |
| list_proposals | (start, limit, order, direction?, status?, last_id?) | api_proposal_object[] |
| find_proposals | (ids: int64[]) | api_proposal_object[] |
| list_proposal_votes | (start, limit, order, direction?, status?) | proposal_vote_object[] |

### Market (7)

| Method | Parameters | Returns |
|--------|-----------|---------|
| get_ticker | (none) | ticker |
| get_volume | (none) | volume |
| get_order_book | (depth?: uint32) | order_book |
| get_trade_history | (start_time, end_time, limit?) | market_trade[] |
| get_recent_trades | (limit?) | market_trade[] |
| get_market_history | (bucket_secs, start_time, end_time) | bucket_object[] |
| get_market_history_buckets | (none) | uint32[] |

### Broadcast (2)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| broadcast_transaction | (trx) | void | Async: returns after mempool acceptance |
| broadcast_transaction_synchronous | (trx) | {id, block_num, trx_num, rc_cost, expired} | Blocks until included or expired |

---

## block_api (3 methods)

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_block_header | block_num: uint32 | block_header? | Header only |
| get_block | block_num: uint32 | api_signed_block_object? | Full block with tx IDs |
| get_block_range | starting_block_num: uint32, count: uint32 | api_signed_block_object[] | Batch retrieval |

---

## rc_api (7 methods)

Resource Credits system: mana tracking, cost estimation, delegations.

RC resource types: history (bytes), tokens, market (bytes), state (hbytes), execution (nanoseconds).

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| get_resource_params | (none) | resource_names + resource_params + size_info | RC system configuration |
| get_resource_pool | (none) | resource_pool | Current pool levels and fill states |
| find_rc_accounts | accounts: string[] | rc_account_api_object[] | RC mana, max_rc, delegated/received |
| list_rc_accounts | start, limit | rc_account_api_object[] | Paginated listing |
| list_rc_direct_delegations | start, limit | rc_direct_delegation_api_object[] | RC delegation details |
| get_rc_stats | (none) | variant_object | Aggregate RC statistics |
| get_rc_operation_stats | operation: string | {count, avg_cost_rc, resource_cost, ...} | Per-operation RC cost breakdown |

rc_account_api_object: `{account, rc_manabar: {current_mana, last_update_time}, max_rc, max_rc_creation_adjustment, delegated_rc, received_delegated_rc}`

---

## Other APIs (method lists)

### account_history_api (4 methods)
- `get_ops_in_block` -- operations in a block (with only_virtual filter)
- `get_transaction` -- lookup by transaction ID
- `get_account_history` -- account ops with bitmask operation type filtering
- `enum_virtual_ops` -- cursor-paginated virtual op enumeration across block ranges

### account_by_key_api (1 method)
- `get_key_references` -- maps public keys to account names

### network_broadcast_api (1 method)
- `broadcast_transaction` -- validate, accept to mempool, broadcast to peers

### market_history_api (7 methods)
- `get_ticker`, `get_volume`, `get_order_book`, `get_trade_history`, `get_recent_trades`, `get_market_history`, `get_market_history_buckets`

### wallet_bridge_api (35 methods)
Convenience wrapper for wallet apps. Aggregates database_api, block_api, account_history_api, rc_api, market_history_api, account_by_key_api, network_broadcast_api. Simplified return types. Includes both sync and async broadcast.

Methods: `get_version`, `get_witness_schedule`, `get_current_median_history_price`, `get_hardfork_version`, `get_block`, `get_chain_properties`, `get_ops_in_block`, `get_feed_history`, `get_active_witnesses`, `get_withdraw_routes`, `list_my_accounts`, `list_accounts`, `get_dynamic_global_properties`, `get_account`, `get_accounts`, `get_transaction`, `list_witnesses`, `get_witness`, `get_conversion_requests`, `get_collateralized_conversion_requests`, `get_order_book`, `get_open_orders`, `get_owner_history`, `get_account_history`, `list_proposals`, `find_proposals`, `is_known_transaction`, `list_proposal_votes`, `get_reward_fund`, `broadcast_transaction_synchronous`, `broadcast_transaction`, `find_recurrent_transfers`, `find_rc_accounts`, `list_rc_accounts`, `list_rc_direct_delegations`

### reputation_api (1 method)
- `get_account_reputations` -- paginated reputation scores

### rewards_api (1 method)
- `simulate_curve_payouts` -- simulate payouts under different reward curves

### transaction_status_api (1 method)
- `find_transaction` -- transaction lifecycle status: unknown, within_mempool, within_reversible_block, within_irreversible_block, expired_reversible, expired_irreversible, too_old

### chain_api (1 method)
- `push_transaction` -- direct transaction push (bypasses p2p broadcast)

### node_status_api (1 method)
- `get_node_status` -- {last_processed_block_num, last_processed_block_time}

### app_status_api (1 method)
- `get_app_status` -- application health status

### witness_api (3 methods)
- `enable_fast_confirm`, `disable_fast_confirm`, `is_fast_confirm_enabled` -- fast-confirm control for witness nodes

### network_node_api (4 methods)
- `get_info`, `add_node`, `set_allowed_peers`, `get_connected_peers` -- P2P peer management

### debug_node_api (12 methods, testing only)
- `debug_generate_blocks`, `debug_generate_blocks_until`, `debug_get_head_block`, `debug_get_witness_schedule`, `debug_get_future_witness_schedule`, `debug_get_hardfork_property_object`, `debug_set_hardfork`, `debug_has_hardfork`, `debug_get_json_schema`, `debug_throw_exception`, `debug_set_vest_price`, `debug_fail_transaction`

### jsonrpc (2 methods, built-in)
- `jsonrpc.get_methods` -- list all registered API methods
- `jsonrpc.get_signature` -- get argument/return type schema for a method

---

## Key Notes

1. **condenser_api vs database_api** -- condenser_api is the legacy compatibility layer. New code should prefer database_api (named params, NAI asset format). condenser_api uses positional args and legacy string assets ("1.000 HIVE").

2. **Dual serialization** -- Broadcast methods accept both legacy and HF26 transaction formats (tries HF26 first, falls back to legacy).

3. **Operation filtering** -- `get_account_history` uses two uint64 bitmasks (low + high) where each bit = one operation type ID. Set bit = include that type.

4. **Pagination** -- database_api `list_*` methods use cursor-based pagination with `{start, limit, order}`. Max limit is 1000. condenser_api limits vary per method.

5. **Optional plugins** -- a condenser_api method whose soft-dependency plugin (market_history, reputation, rc, account_history, block, ...) is not enabled throws `FC_ASSERT("X_plugin not enabled.")`, surfaced as JSON-RPC error -32003, so "plugin missing" is distinguishable from "no data" (empty result). The only silent degradation is the reputation field inside `get_accounts` (`condenser_api.cpp:379`). Unknown api/method names come back as -32002 (via `find_api_method`), not the nominal -32601.

6. **wallet_bridge_api shortcuts** -- Some methods (`get_account`, `list_accounts`, `get_open_orders`, `get_reward_fund`) bypass database_api and query chain DB directly for efficiency.
