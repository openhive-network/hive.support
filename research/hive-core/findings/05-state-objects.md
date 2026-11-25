# Findings: State Objects — Blockchain Database Schema

## Summary

The Hive blockchain maintains its consensus state as a set of objects stored in shared memory via chainbase (a memory-mapped Boost.Interprocess database). The core `object_type` enum defines **39 type IDs (0–38)**: 37 are defined and registered by the core chain library, one (`account_metadata_object`, ID 2) is defined in the metadata plugin, and one (`block_stats_object`, ID 24) is a historical leftover with no definition at all. Each object type is stored in a Boost.MultiIndex container with one or more lookup indices. This document catalogs every state object, its fields, indices, lifecycle (what creates/modifies/removes it), and role in the system.

**Key architectural points:**
- Core consensus state lives in chainbase shared memory, **with one important exception**: since 1.28, paid-out (cashed-out) comments are by default migrated out of chainbase into a **RocksDB comment archive** (ROCKSDB is the default of the chain plugin option `comment-archive`, which exists only in testnet and mirrornet builds; mainnet builds always use ROCKSDB: `libraries/plugins/chain/chain_plugin.cpp:1539-1541`, `:1604-1606`). See "Comment Archive and External Storage" below.
- Objects are accessed through Boost.MultiIndex containers with composite keys; node memory comes from a pool allocator that allocates blocks of N objects at a time (N = power of 2, default 4096 for multi-index nodes).
- Several objects are **singletons** (one instance): `dynamic_global_property_object`, `feed_history_object`, `hardfork_property_object`, `reward_fund_object`, `rc_resource_param_object`, `rc_pool_object`
- The `witness_schedule_object` and `rc_stats_object` are **doubletons** (exactly 2 instances). The second witness schedule (the *future* schedule, id 1) is created at HF26; `rc_stats_object` has pending (id 0) and archive (id 1) instances created at HF20.
- The `block_summary_object` is a **multiton** (exactly 65536 instances for TaPOS); `rc_usage_bucket_object` always has 24 instances (one per hour of the RC usage window).
- `account_metadata_object` lives in the **metadata plugin** (which is *not* in hived's default plugin set — a default node does not track account JSON metadata).
- `block_stats_object` is **forward-declared but never defined** — it is a remnant of an early Steem object deleted in 2016; the enum slot is kept so later type IDs don't shift.
- RC state (mana) is embedded directly in `account_object`; there is no separate `rc_account_object` (the old RC-plugin object of that name disappeared when RC was merged into the chain library).
- The `comment_object` stores only a RIPEMD-160 hash of permlink+author_id, not the raw strings.
- Object IDs (`oid`/`oid_ref`) are **uint32_t** (4 bytes): `chainbase/util/object_id.hpp:20-23`. Typed assets (`HIVE_asset`/`HBD_asset`/`VEST_asset` = `tiny_asset<SYM>`) store only an 8-byte `share_type` amount; the symbol is a compile-time template parameter (`libraries/protocol/include/hive/protocol/asset.hpp:219-221`). Since 1.28.8 the amounts that hold funds in chain objects are balance classes wrapped around them (`tiny_balance<SYM>` such as `HIVE_balance`, or `balance` around a full `asset` where the symbol varies: `libraries/chain/include/hive/chain/util/balance.hpp:25-27`, `:262-307`) with the same JSON and binary form (`:385-422`); they change only by transfers between balances or through the dgpo supply methods (see the dgpo Lifecycle below), while counters and records keep `tiny_asset`. See Part 01, section tiny_asset and tiny_price.
- All chain timestamps use `fc::time_point_sec`, which stores **uint32_t seconds since epoch** — the entire chain (not just manabars) has a year-2106 representation horizon; `time_point_sec::maximum()` = `0xffffffff`.

## Object Type Enum

Source: `libraries/chain/include/hive/chain/hive_object_types.hpp:48-90`

| ID | Type Name | Category |
|----|-----------|----------|
| 0 | `dynamic_global_property_object_type` | Global State |
| 1 | `account_object_type` | Accounts |
| 2 | `account_metadata_object_type` | Accounts (plugin) |
| 3 | `account_authority_object_type` | Accounts |
| 4 | `witness_object_type` | Witnesses |
| 5 | `transaction_object_type` | Transactions |
| 6 | `block_summary_object_type` | Blocks |
| 7 | `witness_schedule_object_type` | Witnesses |
| 8 | `comment_object_type` | Social |
| 9 | `comment_vote_object_type` | Social |
| 10 | `witness_vote_object_type` | Witnesses |
| 11 | `limit_order_object_type` | Market |
| 12 | `feed_history_object_type` | Market |
| 13 | `convert_request_object_type` | Market |
| 14 | `collateralized_convert_request_object_type` | Market |
| 15 | `liquidity_reward_balance_object_type` | Market (legacy) |
| 16 | `hardfork_property_object_type` | Global State |
| 17 | `withdraw_vesting_route_object_type` | Vesting |
| 18 | `owner_authority_history_object_type` | Accounts |
| 19 | `account_recovery_request_object_type` | Accounts |
| 20 | `change_recovery_account_request_object_type` | Accounts |
| 21 | `escrow_object_type` | Transfers |
| 22 | `savings_withdraw_object_type` | Transfers |
| 23 | `decline_voting_rights_request_object_type` | Governance |
| 24 | `block_stats_object_type` | Blocks (DEAD — see below) |
| 25 | `reward_fund_object_type` | Rewards |
| 26 | `vesting_delegation_object_type` | Vesting |
| 27 | `vesting_delegation_expiration_object_type` | Vesting |
| 28 | `proposal_object_type` | DHF |
| 29 | `proposal_vote_object_type` | DHF |
| 30 | `comment_cashout_object_type` | Social |
| 31 | `comment_cashout_ex_object_type` | Social (legacy) |
| 32 | `recurrent_transfer_object_type` | Transfers |
| 33 | `rc_resource_param_object_type` | RC |
| 34 | `rc_pool_object_type` | RC |
| 35 | `rc_direct_delegation_object_type` | RC |
| 36 | `rc_usage_bucket_object_type` | RC |
| 37 | `rc_stats_object_type` | RC |
| 38 | `rc_expired_delegation_object_type` | RC |

**Total: 39 type IDs** (0–38). 37 have core definitions; `account_metadata_object` (ID 2) is defined in the metadata plugin; `block_stats_object` (ID 24) is never defined.

### Chainbase objects outside the core enum (space-ID scheme)

The core enum is not the full universe of chainbase objects. Plugins (and one core subsystem) define additional chainbase objects using a *space ID* convention: the object's 16-bit type value is `(SPACE_ID << 8) + n`, keeping them clear of core IDs 0-38. The chainbase `object<>` template takes `uint16_t TypeNumber` (`libraries/chainbase/include/chainbase/util/object.hpp:15`).

Space IDs defined at this revision:

| Space ID | Subsystem | Example object |
|----------|-----------|----------------|
| 7 | market_history plugin | bucket/order history objects |
| 11 | account_by_key plugin | key lookup objects |
| 14 | block_log_info plugin | block log info objects |
| 15 | account_history_rocksdb plugin | volatile AH operation objects |
| 17 | reputation plugin | reputation objects |
| 18 | transaction_status plugin | transaction status objects |
| 21 | **core comment RocksDB archive** | `volatile_comment_object` (`external_storage/comment_rocksdb_objects.hpp:8-17`) |
| 22 | metadata plugin (reserved; the actual `account_metadata_object` uses core ID 2) | — |
| 666 | comment_cashout_logging plugin | none: the plugin defines the macro (`comment_cashout_logging_plugin.hpp:13-15`) but no chainbase object, and `666 << 8` would not fit the 16-bit type number |

Notably, `volatile_comment_object` (type value `21 << 8` = 5376) is a *consensus-relevant* chainbase object registered by core chain code (not a plugin) whenever the default ROCKSDB comment archive is active — see the dedicated section below.

### Storage classification (answers to the original prompt)

- **Chainbase (shared memory `shared_memory.bin`)**: all 37 core-defined objects above + `volatile_comment_object` (when ROCKSDB archive active) + plugin objects of enabled plugins.
- **RocksDB external storage (core)**: archived (paid-out) comments, as serialized `rocksdb_comment_object` records keyed by author+permlink hash — only when `comment-archive = ROCKSDB` (the default). This is the only core state that leaves chainbase.
- **RocksDB external storage (plugin)**: `account_history_rocksdb` stores account history operations in RocksDB (non-consensus, out of scope here).
- **Not persisted at all**: `node_property_object` (per-node runtime config, `node_property_object.hpp:15`) and the `block_stats` *telemetry class* in `block_flow_control.hpp:18` (unrelated to the dead enum slot — see Discrepancies).
- **State files of 1.28.7 cannot be reused** (per code reading and the unit-test checksums, not observed on a node): on open, hived compares the checksums of the reflected state types stored in shared memory (each over the type and its members' types, names and offsets) with its own and throws `shm_state_definitions_mismatch_exception` on a mismatch (`libraries/chain/database.cpp:187`, `libraries/chain/database_init.cpp:76-87`, `libraries/chain/util/state_checker_tools.cpp:34-38`, `libraries/chain/include/hive/chain/util/decoded_types_data_storage.hpp:182-216`). The objects whose members became balance classes changed checksum in 1.28.8 (for example `tests/unit/tests/basic_tests.cpp:1519`), so a 1.28.8 node refuses a `shared_memory.bin` or state snapshot written by 1.28.7 and state must be rebuilt: `--force-replay`, `--resync-blockchain`, or `--load-snapshot` of a snapshot made by 1.28.8 (only these wipe shared memory before the open, `libraries/plugins/chain/chain_plugin.cpp:955-956`; a snapshot load then runs the same check, `libraries/plugins/state_snapshot/state_snapshot_plugin.cpp:1601-1611`).

---

## State Objects Reference

Conventions used below:
- "Lifecycle" lists verified create/modify/remove sites (`file:line` at release 1.28.8, commit `274384a8a`).
- The `*_multiindex.hpp` files of the core state objects live in `libraries/chain/include/hive/chain/detail/state/` unless noted; object headers in the same directory. Since 1.28.8 the other chainbase index definitions have their own headers too: `rc/rc_objects_multiindex.hpp` (RC objects), `external_storage/comment_rocksdb_objects_multiindex.hpp` (`volatile_comment_index`), and a `<name>_objects_multiindex.hpp` next to each plugin's object header (for example `plugins/metadata/include/hive/plugins/metadata/metadata_objects_multiindex.hpp`); at 1.28.7 they were defined next to the objects.
- The chainbase `object<>` base template is `object<TypeNumber, Derived, HasDynamicAlloc = std::false_type, EnableNoUndo = std::false_type>` (`chainbase/util/object.hpp:15-37`). `HasDynamicAlloc = true` marks objects whose members need an allocator (shared_string / t_vector) and enables dynamic-allocation benchmarking; `EnableNoUndo = true` enables `remove_no_undo()` destruction outside the undo stack (used only by `comment_object`, for the MEMORY comment archive's migration: safe because comments are immutable and the 7-day cashout window guarantees no pending undo entry references them; the chainbase comment explicitly contrasts this with `volatile_comment_object`, which must NOT use it).
- Since 1.28.8 chainbase's `remove()` and `erase()` call the object's `check_on_remove()` when its class defines one (`chainbase/chainbase.hpp:172-181`, `:417-444`); undo, `clear()`, `remove_no_undo()` and `move_to_external_storage()` skip it. The eight classes with balance members (account, dgpo, reward fund, escrow, limit order, savings withdraw, convert and collateralized convert requests) define it to assert that every balance is empty, so the code that removes them moves the funds out to temp balances first (for example `cancel_order`, `database_market.cpp:408-423`).
- Field tables list the reflected member names (`FC_REFLECT`). Since 1.28.8 many more objects keep these members private behind getters and setters (among them the dgpo, the funds and delegation members of `account_object`, `account_authority_object` and `limit_order_object`; the comment family, the conversion requests and recurrent transfers were private already at 1.28.7); the tables keep the reflected names.

---

### dynamic_global_property_object (Singleton)

**Source:** `detail/state/global_property_object.hpp:29`

The single most important state object — tracks ALL global chain state. One instance exists.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `head_block_number` | `uint32_t` | Current head block number |
| `head_block_id` | `block_id_type` | Hash of head block |
| `time` | `time_point_sec` | Timestamp of head block |
| `current_witness` | `account_name_type` | Witness who produced head block |
| `total_pow` | `uint64_t` | Total accumulated POW (init -1) |
| `num_pow_witnesses` | `uint32_t` | Count of pending POW witnesses |
| `virtual_supply` | `HIVE_asset` | HIVE supply including virtual HBD conversion |
| `current_supply` | `HIVE_asset` | **Main HIVE token counter** |
| `init_hbd_supply` | `HBD_asset` | Initial HBD supply |
| `current_hbd_supply` | `HBD_asset` | **Main HBD token counter** |
| `total_vesting_fund_hive` | `HIVE_balance` | HIVE backing all VESTS (a balance class since 1.28.8, `HIVE_asset` at 1.28.7) |
| `total_vesting_shares` | `VEST_asset` | Total VESTS in existence |
| `pending_rewarded_vesting_shares` | `VEST_asset` | Unclaimed vest rewards |
| `pending_rewarded_vesting_hive` | `HIVE_asset` | HIVE backing unclaimed vest rewards |
| `hbd_interest_rate` | `uint16_t` | HBD interest rate (BPS) |
| `hbd_print_rate` | `uint16_t` | Percent of rewards paid in HBD (BPS) |
| `maximum_block_size` | `uint32_t` | Current max block size (witness median) |
| `current_aslot` | `uint64_t` | Absolute slot number |
| `recent_slots_filled` | `fc::uint128_t` | Bitfield for witness participation |
| `participation_count` | `uint8_t` | Count of bits set (÷128 = participation %) |
| `vote_power_reserve_rate` | `uint32_t` | Votes regenerated per day |
| `delegation_return_period` | `uint32_t` | Delegation return period (seconds) |
| `reverse_auction_seconds` | `uint64_t` | Reverse auction window |
| `early_voting_seconds` | `uint64_t` | Early voting window |
| `mid_voting_seconds` | `uint64_t` | Mid voting window |
| `available_account_subsidies` | `int64_t` | Pool of free account creation tokens |
| `hbd_stop_percent` | `uint16_t` | HBD market cap % to stop printing |
| `hbd_start_percent` | `uint16_t` | HBD market cap % to resume printing |
| `next_maintenance_time` | `time_point_sec` | Next DHF maintenance |
| `last_budget_time` | `time_point_sec` | Last DHF budget calculation |
| `next_daily_maintenance_time` | `time_point_sec` | Next daily treasury conversion |
| `content_reward_percent` | `uint16_t` | Content reward share (BPS) |
| `vesting_reward_percent` | `uint16_t` | Vesting reward share (BPS) |
| `proposal_fund_percent` | `uint16_t` | DHF fund share (BPS) |
| `dhf_interval_ledger` | `HBD_asset` | Accumulated HBD for DHF interval |
| `downvote_pool_percent` | `uint16_t` | Downvote pool as % of upvote pool |
| `current_remove_threshold` | `int16_t` | Max objects removed per auto-operation |
| `max_consecutive_recurrent_transfer_failures` | `uint8_t` | Max failures before deletion |
| `max_recurrent_transfer_end_date` | `uint16_t` | Max end date for recurrent transfers |
| `min_recurrent_transfers_recurrence` | `uint8_t` | Min recurrence in hours |
| `max_open_recurrent_transfers` | `uint16_t` | Max active recurrent transfers per account |

(41 reflected fields + `id`; matches `FC_REFLECT` at `global_property_object.hpp:400-443`. 1.28.7 also had `total_reward_fund_hive` and `total_reward_shares2` (43 fields); 1.28.8 removed both from the object and from the `database_api` and `condenser_api` dgpo responses (`database_api_objects.hpp:691-703`, `condenser_api.hpp:1062-1075`). The pre-HF17 data they held, the content reward pool and the running rshares2 total, is kept in `reward_fund_object` (`reward_balance`, `recent_claims`) since 1.28.8 (`database.cpp:1687-1699`, `:1953-1966`); see its section below.)

**Computed Properties:**
- `get_vesting_share_price()` — VEST/HIVE conversion price (from `total_vesting_shares` / `total_vesting_fund_hive`)
- `get_reward_vesting_share_price()` — includes pending rewards in price calculation

**Indices:** Only `by_id` (singleton)

**Lifecycle:** created once at genesis (`database_init.cpp:256`); modified every block (`update_global_dynamic_data`, `process_funds`, supply changes, witness-median property updates); never removed. Since 1.28.8 HIVE and HBD are issued, burned and converted only through the dgpo's own methods, which replace `database::adjust_supply` and hand out or take in temp balances (`global_property_object.hpp:295-396`): `issue_HIVE`/`burn_HIVE` (`current_supply`, `virtual_supply`), `issue_HBD`/`burn_HBD` (`current_hbd_supply`, `virtual_supply`), `convert_HIVE_to_HBD` (raises `current_hbd_supply`, lowers `current_supply`, may recompute `virtual_supply`), `issue_VESTS`/`burn_VESTS` (`total_vesting_shares`, or `pending_rewarded_vesting_shares` for rewards), `convert_HIVE_to_VESTS` (moves the HIVE into `total_vesting_fund_hive`, or for rewards adds its amount to `pending_rewarded_vesting_hive`, and issues the VESTS) and `convert_VESTS_to_HIVE` (pays the HIVE out of `total_vesting_fund_hive` and burns the VESTS). Some counters are still written directly through the dgpo's `access_*` mutators: `update_virtual_supply()` recomputes `virtual_supply` every block (`database.cpp:2905-2913`, called at `:2348` and `:2359`), and `claim_reward_balance` and `liquify_reward_balance` adjust the reward VESTS counters (`hive_evaluator_transfer.cpp:711-718`, `database.cpp:1172-1176`).

---

### account_object

**Source:** `detail/state/account_object.hpp:27` (declared `object<..., std::true_type>` — has dynamic alloc, for `delayed_votes`)

The largest and most complex state object. Stores all account state including balances, manabars, voting data, and RC state. A source comment at `account_object.hpp:200` states: *"members are organized in such a way that the object takes up as little space as possible (note that object starts with 4byte id)"*: the declaration order in the header is deliberate packing, not historical accident; the table below groups the fields by topic instead. Since 1.28.8 the nine members that hold funds are balance classes (types below) and, with `delegated_vesting_shares` and `received_vesting_shares`, private behind getters such as `get_hive_balance()` (`account_object.hpp:70-127`, `:217-230`); two of them were renamed in 1.28.8 (`balance` -> `hive_balance`, `savings_balance` -> `savings_hive_balance`; `FC_REFLECT` at `account_object.hpp:608-609`), while the `database_api` and `condenser_api` account objects keep the old names (`database_api_objects.hpp:312-313`, `condenser_api.hpp:195-196`).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `account_name_type` | Account name (3-16 chars) |
| `proxy` | `account_id_type` | Governance proxy (0 = none) |
| `recovery_account` | `account_id_type` | Recovery account (0 = top witness) |
| `last_account_recovery` | `time_point_sec` | Last successful recovery |
| `block_last_account_recovery` | `time_point_sec` | Same from block time (REMOVE — API only) |
| **Balances** | | |
| `hive_balance` | `HIVE_balance` | Liquid HIVE (`balance` at 1.28.7 and in the API account objects) |
| `savings_hive_balance` | `HIVE_balance` | HIVE in savings (3-day withdrawal; `savings_balance` at 1.28.7 and in the API account objects) |
| `reward_hive_balance` | `HIVE_balance` | Unclaimed HIVE rewards |
| `hbd_balance` | `HBD_balance` | Liquid HBD |
| `savings_hbd_balance` | `HBD_balance` | HBD in savings (earns interest) |
| `reward_hbd_balance` | `HBD_balance` | Unclaimed HBD rewards |
| `reward_vesting_balance` | `VEST_balance` | Unclaimed VEST rewards |
| `reward_vesting_hive` | `HIVE_balance` | HIVE counterweight to reward VESTS |
| **Vesting** | | |
| `vesting_shares` | `VEST_balance` | Total VESTS held |
| `delegated_vesting_shares` | `VEST_asset` | VESTS delegated out |
| `received_vesting_shares` | `VEST_asset` | VESTS delegated in |
| `vesting_withdraw_rate` | `VEST_asset` | Weekly power down rate |
| `withdrawn` | `VEST_asset` | VESTS already withdrawn in current powerdown (source comment: "why do we even need this?") |
| `to_withdraw` | `VEST_asset` | Total VESTS to withdraw in current powerdown |
| `next_vesting_withdrawal` | `time_point_sec` | Next powerdown payment (max = inactive) |
| `withdraw_routes` | `uint16_t` | Number of withdrawal routes (max 10; comment: "why is it 16bit?") |
| **Manabars** | | |
| `voting_manabar` | `manabar` | Upvote mana {current_mana: int64, last_update_time: uint32} |
| `downvote_manabar` | `manabar` | Downvote mana |
| `rc_manabar` | `manabar` | Resource credit mana |
| **RC** | | |
| `rc_adjustment` | `share_type` | Extra RC from account creation fee |
| `delegated_rc` | `share_type` | RC delegated out |
| `received_rc` | `share_type` | RC delegated in |
| `last_max_rc` | `share_type` | Maximum RC as last recorded by the RC code, which updates and caps `rc_manabar` against it when the maximum changes (`rc/rc_utility.cpp:468-488`) and compares it with the current maximum to catch RC bugs (`:344-358`). Source comment: "for bug catching with RC code, can be removed once RC becomes part of consensus" (`account_object.hpp:243`); HF29, defined in 1.28.8 and inactive on mainnet, makes RC part of consensus (Part 01, section HF29 (Defined in 1.28.8, Inactive on Mainnet)) |
| **HBD Interest** | | |
| `hbd_seconds` | `uint128_t` | Liquid HBD × time held |
| `hbd_seconds_last_update` | `time_point_sec` | Last HBD seconds update |
| `hbd_last_interest_payment` | `time_point_sec` | Last interest payment |
| `savings_hbd_seconds` | `uint128_t` | Savings HBD × time held |
| `savings_hbd_seconds_last_update` | `time_point_sec` | Last savings HBD update |
| `savings_hbd_last_interest_payment` | `time_point_sec` | Last savings interest payment |
| **Governance** | | |
| `witnesses_voted_for` | `uint16_t` | Number of witnesses voted for (max 30) |
| `governance_vote_expiration_ts` | `time_point_sec` | When governance vote expires |
| `proxied_vsf_votes` | `fc::array<share_type, 4>` | Proxied governance power (4 depth levels) |
| `can_vote` | `bool` | Voting enabled |
| **Social** | | |
| `post_count` | `uint32_t` | Total posts (REMOVE — API only) |
| `post_bandwidth` | `uint32_t` | Post bandwidth (HF12-17 root comment reward influence) |
| `last_post` | `time_point_sec` | Last post/comment time |
| `last_root_post` | `time_point_sec` | Last root post time (influenced rewards HF12–17) |
| `last_post_edit` | `time_point_sec` | Last post edit time (source comment: could be merged with `last_post`, needs HF) |
| `last_vote_time` | `time_point_sec` | Last vote time (REMOVE — non-consensus) |
| **Delayed Voting** | | |
| `delayed_votes` | `t_vector<delayed_votes_data>` | VESTS per day pending activation (30-day delay); TODO comment: "check how frequently it is filled - maybe separate index would be better" (`account_object.hpp:291`) |
| `sum_delayed_votes` | `ushare_type` | Sum of delayed votes (comment: should be `VEST_asset`) |
| **Other** | | |
| `pending_claimed_accounts` | `share_type` | Claimed but unused account tokens (comment: could be 32bit) |
| `pending_escrow_transfers` | `uint16_t` | Active escrow count (max 255 for now) |
| `open_recurrent_transfers` | `uint16_t` | Active recurrent transfers (max 255 for now) |
| `savings_withdraw_requests` | `uint8_t` | Active savings withdrawals |
| `curation_rewards` | `HIVE_asset` | Cumulative curation rewards (non-consensus) |
| `posting_rewards` | `HIVE_asset` | Cumulative author rewards (non-consensus) |
| `created` | `time_point_sec` | Account creation time (REMOVE — unit tests only) |
| `block_created` | `time_point_sec` | Creation time from block (REMOVE — API and colony) |
| `last_account_update` | `time_point_sec` | Last account update (REMOVE — non-consensus) |
| `mined` | `bool` | Created via POW mining (REMOVE — API only) |
| `memo_key` | `public_key_type` | Memo key, 33 bytes align(1). Source comment: "it belongs to metadata as it is not used by consensus, but witnesses need it here since they don't use metadata plugin" (`account_object.hpp:282`) |

**Computed Properties:**
- `get_effective_vesting_shares()` = `vesting_shares - delegated_vesting_shares + received_vesting_shares - next_withdrawal_step`
- `get_maximum_rc()` = `effective_vesting_shares - delegated_rc + rc_adjustment + received_rc`
- `get_governance_vote_power()` = `vesting_shares - sum_delayed_votes + sum(proxied_vsf_votes)`

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Primary |
| `by_name` | `name` | Unique account lookup |
| `by_proxy` | `(proxy, name)` | Find accounts by proxy |
| `by_next_vesting_withdrawal` | `(next_vesting_withdrawal, name)` | Process powerdowns |
| `by_delayed_voting` | `(oldest_delayed_vote_time, id)` | Mature delayed votes |
| `by_governance_vote_expiration_ts` | `(governance_vote_expiration_ts, id)` | Expire governance votes |

**Lifecycle:** created by `account_create` / `account_create_with_delegation` / `create_claimed_account` / `pow` / `pow2` evaluators through the free `create_account()` helper (`hive_evaluator_account.cpp:152`); at genesis for the builtin accounts (`miners`, `null`, `temp`, `initminer` and `steem`; testnet and mirrornet builds add their configured init witnesses, testnet and iceberg-converter builds both treasury accounts: `database_init.cpp:197-252`); at HF21 (`steem.dao`) and HF24 (`hive.fund`) for the treasury, each only if that account does not exist yet (`database_hardfork.cpp:428`, `database_hardfork.cpp:529`). Modified by virtually every balance/vesting/voting/RC operation and per-block processing. **Never removed** (accounts are permanent; HF23 zeroed balances of specific accounts via `clear_account` but kept the objects).

---

### account_authority_object

**Source:** `detail/state/account_object.hpp:364` (has dynamic alloc - shared_authority maps)

Separate object for authority storage (owner/active/posting keys). Split from account_object so that the hot account data stays small.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `account` | `account_name_type` | Account name |
| `owner` | `shared_authority` | Owner authority (backup control) |
| `active` | `shared_authority` | Active authority (monetary ops) |
| `posting` | `shared_authority` | Posting authority (social ops) |
| `previous_owner_update` | `time_point_sec` | Previous owner key change |
| `last_owner_update` | `time_point_sec` | Last owner key change |

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Primary |
| `by_account` | `(account, id)` | Lookup by account name |

**Lifecycle:** created alongside every `account_object` (`hive_evaluator_account.cpp:200`, `:256`, `:476` in the three creation evaluators, pow paths `hive_evaluator.cpp:426,559`, genesis `database_init.cpp:198-252`), and by `lock_account` for a treasury account that has none (`database.cpp:1407`); modified by `account_update`/`account_update2` (`hive_evaluator_account.cpp:311`, `:343-347`, `:368`, `:385-389`), `recover_account` (`:567`), the HF9 reset of the compromised accounts (`database_hardfork.cpp:226-232`) and `lock_account` at HF21 and HF24, which overwrites all three authorities of a treasury account that already has the object (`database.cpp:1411-1416`, called at `database_hardfork.cpp:433`, `:534`); never removed. `change_recovery_account` does not touch it (it changes `account_object.recovery_account`, `database.cpp:2020-2023`). Owner changes go through `set_owner()`, which moves `last_owner_update` into `previous_owner_update` and records the change time (`account_object.hpp:390-395`); since 1.28.8 `lock_account` writes the owner this way too, so it also moves both timestamps. Owner updates are rate-limited via these two fields: since HF26 at most two changes per `HIVE_OWNER_UPDATE_LIMIT` (60 minutes on mainnet, `hive/protocol/config.hpp:165`), before HF26 one (`util/owner_update_limit_mgr.cpp:10-26`); `account_update` checks it from HF11 except in converter builds (`hive_evaluator_account.cpp:301-307`), `account_update2` always (`:362-364`).

---

### account_metadata_object (Plugin — not in default config)

**Source:** `libraries/plugins/metadata/include/hive/plugins/metadata/metadata_objects.hpp:10`

**Note:** Defined in the `metadata` plugin but occupies core enum slot 2. The plugin registers `account_metadata_index` via `HIVE_ADD_PLUGIN_INDEX` in `metadata_plugin.cpp:199` and fills it from a `post_apply_operation` handler. The plugin has **no config options** of its own and is **not part of hived's default plugin set** (`programs/hived/main.cpp:117-122` lists defaults: witness, account_by_key, account_by_key_api, state_snapshot). A node without the plugin stores no account JSON metadata at all (and cannot serve it). The plugin separately reserves space ID 22 (`metadata_plugin.hpp:9`) even though this object uses core ID 2 — the object was moved out of core into the plugin while keeping its original type ID, since changing it would break state compatibility.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `account` | `account_id_type` | Account reference |
| `json_metadata` | `shared_string` | Active-level JSON metadata |
| `posting_json_metadata` | `shared_string` | Posting-level JSON metadata |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_account` | `account` (unique) |

**Lifecycle:** created/modified by the plugin's operation handler on account create/update operations; never removed.

---

### comment_object

**Source:** `detail/state/comment_object.hpp:24`

Minimal comment/post identity object. Stores only a hash (not raw author+permlink strings). Declared as `object<comment_object_type, comment_object, std::false_type /* no dynamic alloc */, std::true_type /* enable no undo remove */>`: the only object using the `EnableNoUndo` feature, which lets the MEMORY comment archive destroy paid-out comments outside the undo stack (`memory_comment_archive.cpp:44`; the default ROCKSDB archive removes them with the regular, undoable `remove()`, `rocksdb_comment_archive.cpp:131`). `chainbase/util/object.hpp:26-35` documents when this is safe, with `comment_object` as the example and `volatile_comment_object` as the counterexample.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `parent_comment` | `comment_id_type` | Parent comment ID (null = root post) |
| `author_and_permlink_hash` | `fc::ripemd160` | RIPEMD-160 hash of `permlink + "@" + author_id` |
| `depth` | `uint16_t` | Nesting depth (0 = root post); source comment flags it as a removal candidate (steemit/steem#767) and still says it is soft-limited in the witness plugin with no consensus limit needed (`comment_object.hpp:60-61`), but the comment evaluator enforces the limit: `HIVE_MAX_COMMENT_DEPTH_PRE_HF17` (6) before HF17 and `HIVE_MAX_COMMENT_DEPTH` (0xffff) from HF17, lowered to `HIVE_SOFT_MAX_COMMENT_DEPTH` (255) when the node is in control (`hive_evaluator_social.cpp:186-190`; Part 03, section comment_operation (ID 1)) |

A source comment on the hash field (`comment_object.hpp:57-58`, ABW) sketches a future optimization: splitting it into author_id + 128-bit hash would allow moving comment identity to external DB with only active authors cached.

**Computed:**
- `is_root()` — true when `parent_comment` is null
- `compute_author_and_permlink_hash(author_id, permlink)` = `RIPEMD160(permlink + "@" + std::to_string(author_id))` (`comment_object.hpp:92-96`)

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Primary |
| `by_permlink` | `author_and_permlink_hash` | Consensus lookup by author+permlink |

**Lifecycle:** created by `comment_evaluator` on first posting (`hive_evaluator_social.cpp:246`); **never modified** (edits touch only `comment_cashout_object`); removed by `delete_comment_evaluator` (when no replies, no positive rshares, never paid), or — under MEMORY/ROCKSDB archive modes — removed from the chainbase index when migrated to the archive after its cashout becomes irreversible (see Comment Archive section). Under `comment-archive = NONE` it stays in chainbase forever.

**Lookup API:** consensus code never queries the chainbase index directly for author+permlink lookups; it goes through `database::find_comment(author, permlink)` / `get_comment(...)` (`database.cpp:404-451`), which delegate to the comments handler so archived comments are still found. The handler returns a `comment` wrapper (`external_storage/comment.hpp`) that either points into shared memory or owns a heap copy reconstructed from RocksDB.

---

### comment_cashout_object

**Source:** `detail/state/comment_object.hpp:103` (has dynamic alloc — permlink, beneficiaries)

Holds payout-related data for comments with pending cashout. **Removed after cashout** (since HF19). Shares `id` with its `comment_object` (1:0..1 relation, `comment_object.hpp:125`).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `author_id` | `account_id_type` | Comment author |
| `permlink` | `shared_string` | Comment permlink |
| `net_rshares` | `share_type` | Sum of all vote rshares |
| `vote_rshares` | `share_type` | Sum of positive vote rshares |
| `total_vote_weight` | `uint64_t` | Accumulated vote weight for curation split |
| `max_accepted_payout` | `HBD_asset` | Max payout (default `HBD_asset( 1'000'000'000 )`, i.e. 1,000,000.000 HBD since HBD has 3 decimals: `comment_object.hpp:238`) |
| `net_votes` | `int32_t` | Upvotes minus downvotes (API only) |
| `children` | `uint32_t` | Direct reply count |
| `created` | `time_point_sec` | Creation time |
| `cashout_time` | `time_point_sec` | Scheduled cashout (7 days after creation since HF17); `maximum()` = disabled |
| `percent_hbd` | `uint16_t` | Percent of reward in HBD (BPS) |
| `allow_votes` | `bool` | Voting enabled |
| `allow_curation_rewards` | `bool` | Curation rewards enabled |
| `was_voted_on` | `bool` | Has received at least one real vote |
| `beneficiaries` | `t_vector<stored_beneficiary_route_type>` | Beneficiary list {account_id, weight} |

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Shares ID with comment_object |
| `by_cashout_time` | `(cashout_time, id)` | Process pending payouts |

**Lifecycle:** created with the comment (`hive_evaluator_social.cpp:256`); modified by votes (`on_vote`, `accumulate_vote_rshares`), replies (`on_reply`), edits, and `comment_options_evaluator` (`configure_options`); removed at payout in `process_comment_cashout` post-HF19 (`database_comment.cpp:471-475` — handler `on_cashout` is invoked, then `remove`), at HF19 itself for already-paid comments (`remove_old_cashouts`, `database_comment.cpp:94-112`), or by `delete_comment`.

---

### comment_cashout_ex_object (Legacy — empty after HF19)

**Source:** `detail/state/comment_object.hpp:272`

Extended cashout data needed only for pre-HF19 reward rules (mostly pre-HF17, plus `last_payout`). Shares `id` with `comment_object`.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `root_comment` | `comment_id_type` | Root of discussion tree |
| `last_payout` | `time_point_sec` | Previous payout time |
| `max_cashout_time` | `time_point_sec` | Max cashout deadline (pre-HF17) |
| `abs_rshares` | `share_type` | Absolute rshares (very early comments) |
| `children_abs_rshares` | `share_type` | Discussion abs rshares (pre-HF17 discussion-wide cashout) |
| `total_payout_value` | `HBD_asset` | Cumulative payouts |
| `curator_payout_value` | `HBD_asset` | Cumulative curator payouts |
| `beneficiary_payout_value` | `HBD_asset` | Cumulative beneficiary payouts |
| `reward_weight` | `uint16_t` | Reward weight (BPS; below 100% only for root posts created between HF12 and HF17, the frequent-post penalty) |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_root` | `(root_comment, id)` |

**Lifecycle:** created with every comment **only before HF19** (`hive_evaluator_social.cpp:262`); modified during pre-HF19 vote/payout processing; **the entire index is cleared at HF19 application**: `remove_old_cashouts()` calls `comment_cashout_ex_idx.clear()` (`database_comment.cpp:96-98`, invoked from `database_hardfork.cpp:328`). On a synced node this index is empty; it only holds objects transiently during replay of pre-HF19 blocks (one per comment existing at that point). `find_comment_cashout_ex` short-circuits to `nullptr` once HF19 is active (`database_comment.cpp:71-82`).

---

### comment_vote_object

**Source:** `detail/state/comment_object.hpp:372`

Tracks each voter/comment pair. One object per vote — but only while the comment is in its cashout window (see lifecycle).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `voter` | `account_id_type` | Voting account |
| `comment` | `comment_id_type` | Voted comment |
| `weight` | `uint64_t` | Vote weight for curation rewards (0 for downvotes/edits) |
| `rshares` | `int64_t` | rshares this vote contributes |
| `vote_percent` | `int16_t` | Vote percentage (-10000 to 10000) |
| `last_update` | `time_point_sec` | Last update time (REMOVE — API only, `comment_object.hpp:405`) |

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Primary |
| `by_comment_voter` | `(comment, voter)` | Find vote for specific comment |
| `by_voter_comment` | `(voter, comment)` | Find all votes by voter |

**Lifecycle:** created by `vote_evaluator` (`hive_evaluator_social.cpp:559` pre-HF20 path, `:843` current path); modified on vote edits (`set(...)`); **removed in bulk at comment payout** — the tail of `cashout_comment_helper` walks `by_comment_voter` and removes every vote of the paid comment (`database_comment.cpp:365-372`) — and on `delete_comment` (`hive_evaluator_social.cpp:78-86`). Consequently the index holds only votes on comments inside the 7-day window, which is why total state stays bounded despite ~unbounded vote history.

---

### witness_object

**Source:** `detail/state/witness_objects.hpp:69` (has dynamic alloc — url string)

Witness configuration, stats, and scheduling data.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `account_name_type` | Witness account name |
| `created` | `time_point_sec` | Registration time |
| `url` | `shared_string` | Witness URL |
| `total_missed` | `uint32_t` | Missed blocks count |
| `last_aslot` | `uint64_t` | Last absolute slot |
| `last_confirmed_block_num` | `uint64_t` | Last confirmed block |
| `pow_worker` | `uint64_t` | POW worker position (0 = not POW) |
| `signing_key` | `public_key_type` | Block signing key (empty = disabled) |
| `props` | `chain_properties` | Witness-voted chain properties |
| `hbd_exchange_rate` | `price` | HBD/HIVE price feed |
| `last_hbd_exchange_update` | `time_point_sec` | Last price feed update |
| `votes` | `share_type` | Total governance votes received |
| `schedule` | `witness_schedule_type` | Last schedule type: elected/timeshare/miner/none |
| `virtual_last_update` | `fc::uint128` | Virtual time scheduling |
| `virtual_position` | `fc::uint128` | Virtual position |
| `virtual_scheduled_time` | `fc::uint128` | Expected virtual lap completion |
| `last_work` | `digest_type` | Last POW hash |
| `running_version` | `version` | Reported hived version |
| `hardfork_version_vote` | `hardfork_version` | Hardfork version vote |
| `hardfork_time_vote` | `time_point_sec` | Hardfork time vote |
| `available_witness_account_subsidies` | `int64_t` | Free account creation pool |

**chain_properties sub-struct:**

| Field | Type | Description |
|-------|------|-------------|
| `account_creation_fee` | `HIVE_asset` | Minimum account creation fee |
| `maximum_block_size` | `uint32_t` | Voted max block size |
| `hbd_interest_rate` | `uint16_t` | Voted HBD interest rate |
| `account_subsidy_budget` | `int32_t` | Free accounts per block |
| `account_subsidy_decay` | `uint32_t` | Free account decay rate |

**Indices:**

| Index Tag | Key Fields | Ordering | Notes |
|-----------|------------|----------|-------|
| `by_id` | `id` | asc | Primary |
| `by_name` | `owner` | asc | Unique name lookup |
| `by_work` | `(last_work, id)` | asc | POW lookup |
| `by_pow` | `(pow_worker, id)` | asc | POW scheduling |
| `by_vote_name` | `(votes, owner)` | **votes DESC**, name asc | Rank witnesses by votes |
| `by_schedule_time` | `(virtual_scheduled_time, id)` | asc | Virtual time scheduling |

**Lifecycle:** created by `witness_update_evaluator` for new witnesses (`hive_evaluator.cpp:90`), by pow/pow2 evaluators (`hive_evaluator.cpp:467,562`), and for initminer at genesis (`database_init.cpp:220`); modified by `witness_update`, `witness_set_properties`, `feed_publish`, `account_witness_vote` tallies (`adjust_witness_votes`), block production stats, and schedule shuffling; never removed (disabled witnesses just have a null signing key).

---

### witness_vote_object

**Source:** `detail/state/witness_objects.hpp:171`

Links accounts to witnesses they voted for. Both references are **names**, not ids.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `witness` | `account_name_type` | Witness name |
| `account` | `account_name_type` | Voting account name |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_account_witness` | `(account, witness)` |
| `by_witness_account` | `(witness, account)` |

**Lifecycle:** created by `account_witness_vote_evaluator` (`hive_evaluator.cpp:283`); removed by the same evaluator (unvote, `hive_evaluator.cpp:324`) and by `clear_witness_votes` (`database_witness.cpp:96-111`), which runs when an account sets a proxy (`account_witness_proxy`, `hive_evaluator.cpp:235`), during decline-voting-rights processing (`database_dhf.cpp:208+`) and on governance vote expiration (`database.cpp:3526`). HF23 account clearing keeps them (`clear_account` only takes the account's VESTS out of the vote tallies, `database.cpp:1558`).

---

### witness_schedule_object (Doubleton since HF26)

**Source:** `detail/state/witness_objects.hpp:181`

Witness schedule state. **Two instances**: the *current* schedule (id 0, created at genesis `database_init.cpp:308`) and the *future* schedule (id 1, created at HF26 application with `FC_ASSERT(fwso.get_id() == 1)` — `database_hardfork.cpp:498-503`). The allocator comment "dubleton (plus one internal)" (`witness_objects_multiindex.hpp`) refers to these two plus the pool allocator's internal node — hence block size 4.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `current_virtual_time` | `fc::uint128` | Virtual time state |
| `next_shuffle_block_num` | `uint32_t` | Next schedule shuffle block |
| `current_shuffled_witnesses` | `fc::array<account_name_type, 21>` | Shuffled witness list (HIVE_MAX_WITNESSES) |
| `num_scheduled_witnesses` | `uint8_t` | Count of scheduled witnesses |
| `elected_weight` | `uint8_t` | Weight for elected witnesses |
| `timeshare_weight` | `uint8_t` | Weight for timeshare witnesses |
| `miner_weight` | `uint8_t` | Weight for miner witnesses |
| `witness_pay_normalization_factor` | `uint32_t` | Pay normalization factor |
| `median_props` | `chain_properties` | Median of witness-voted properties |
| `majority_version` | `version` | Majority hived version |
| `max_voted_witnesses` | `uint8_t` | Max voted witnesses |
| `max_miner_witnesses` | `uint8_t` | Max miner witnesses |
| `max_runner_witnesses` | `uint8_t` | Max runner witnesses |
| `hardfork_required_witnesses` | `uint8_t` | Witnesses needed for HF |
| `account_subsidy_rd` | `rd_dynamics_params` | Account subsidy resource dynamics |
| `account_subsidy_witness_rd` | `rd_dynamics_params` | Witness account subsidy dynamics |
| `min_witness_account_subsidy_decay` | `int64_t` | Minimum decay |

**Indices:** Only `by_id`

**Lifecycle:** current schedule created at genesis, future at HF26; both modified every schedule round (21 blocks); never removed.

---

### feed_history_object (Singleton)

**Source:** `detail/state/feed_history_object.hpp:15` (has dynamic alloc — price deque)

Tracks HBD/HIVE price feed history. Updated once per hour.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `current_median_history` | `HBD_price` | Current median price (used for conversions) |
| `market_median_history` | `HBD_price` | Market median (same unless artificially adjusted) |
| `current_min_history` | `HBD_price` | Min price (for collateralized conversion) |
| `current_max_history` | `HBD_price` | Max price in window |
| `price_history` | `t_deque<HBD_price>` | Hourly medians: the last 84 (3.5 days) since HF16, 168 (7 days) before; the HF16 switch trimmed it to 84 (`database.cpp:2457-2463`, `database_hardfork.cpp:256-263`, `protocol/config.hpp:186-187`; Part 07, section Feed History) |

**Indices:** Only `by_id` (singleton)

**Lifecycle:** created at genesis (`database_init.cpp:265` in testnet and iceberg-converter builds, `:299` otherwise); modified hourly by `update_median_feed` from witness `feed_publish` data; never removed.

---

### limit_order_object

**Source:** `detail/state/limit_order_object.hpp:21`

Open internal market (HIVE/HBD) limit orders. Which markets an order may use: Part 02, section SMT residue in limit-order validation (resolves open question).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `created` | `time_point_sec` | Order creation time |
| `expiration` | `time_point_sec` | Expiration time |
| `orderid` | `uint32_t` | User-assigned order ID (declared and reflected before `seller` since 1.28.8, after it at 1.28.7) |
| `seller` | `account_name_type` | Seller account (a name: the source comment says an id is not possible because `by_account` serves `database_api.list_limit_orders`, `limit_order_object.hpp:68`) |
| `for_sale` | `balance` | Amount for sale with its symbol, which the constructor asserts equals `sell_price.base.symbol` (`limit_order_object.hpp:34`); at 1.28.7 a `share_type` amount whose symbol came from `sell_price.base`. The API objects still return only the amount (`share_type`, `database_api_objects.hpp:186`) |
| `sell_price` | `price` | Price (base/quote pair) |

**Indices:**

| Index Tag | Key Fields | Ordering | Notes |
|-----------|------------|----------|-------|
| `by_id` | `id` | asc | Primary |
| `by_expiration` | `(expiration, id)` | asc | Auto-cleanup expired orders |
| `by_price` | `(sell_price, id)` | **price DESC**, id asc | Order matching |
| `by_account` | `(seller, orderid)` | asc | Find user's orders |

**Lifecycle:** created by `limit_order_create` / `limit_order_create2` evaluators (`hive_evaluator_transfer.cpp:565,600`); modified (partial fill) / removed (full fill) during matching (`database_market.cpp:346-359`, `:384-388`); removed by `limit_order_cancel` and by `clear_expired_orders` (`database_market.cpp:425`), and at HF23 by `remove_pending_limit_orders` for the cleared accounts (`database_market.cpp:455-465`). Removal requires an empty `for_sale` (`check_on_remove()`, `limit_order_object.hpp:55-58`): a full fill removes the order once matching has drained it, and every other path goes through `cancel_order`, which first returns the remainder to the seller (`database_market.cpp:408-423`).

---

### convert_request_object

**Source:** `detail/state/convert_request_object.hpp:14`

Pending HBD->HIVE conversion requests (3.5-day delay).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `account_id_type` | Request owner |
| `amount` | `HBD_balance` | HBD amount to convert (a balance class since 1.28.8, `HBD_asset` at 1.28.7) |
| `requestid` | `uint32_t` | User-assigned request ID |
| `conversion_date` | `time_point_sec` | Conversion execution date |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_conversion_date` | `(conversion_date, id)` |
| `by_owner` | `(owner, requestid)` |

**Lifecycle:** created by `convert_evaluator` (`hive_evaluator_transfer.cpp:482`); removed when executed in `process_conversions` (`database_conversion.cpp:35`), and at HF23 by `remove_pending_conversion_requests` for the cleared accounts, which returns the HBD to the owner's balance (`database_conversion.cpp:198-216`).

---

### collateralized_convert_request_object

**Source:** `detail/state/collateralized_convert_request_object.hpp:15`

Pending HIVE->HBD collateralized conversion requests (3.5-day delay). HBD is given immediately; HIVE collateral returned after conversion minus actual price.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `account_id_type` | Request owner |
| `collateral_amount` | `HIVE_balance` | HIVE collateral locked (a balance class since 1.28.8, `HIVE_asset` at 1.28.7) |
| `converted_amount` | `HBD_asset` | HBD already given to owner |
| `requestid` | `uint32_t` | User-assigned request ID |
| `conversion_date` | `time_point_sec` | Conversion execution date |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_conversion_date` | `(conversion_date, id)` |
| `by_owner` | `(owner, requestid)` |

**Lifecycle:** created by `collateralized_convert_evaluator` (`hive_evaluator_transfer.cpp:529`); removed when executed in `process_conversions`.

---

### escrow_object

**Source:** `detail/state/escrow_object.hpp:14`

Active escrow transfers between accounts with an agent. All three account references are **names** with explicit TODO comments: *"TODO: can be replaced with account_id_type (ABW: would make looking for escrow object harder)"* (`escrow_object.hpp:69-71`): operations identify escrows by `(from_name, escrow_id)`, so an id-based object would force an extra account lookup per access. `to_approved`/`agent_approved`/`disputed` have a further TODO: "can be replaced with bit field along with all flags" (`escrow_object.hpp:77`).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `escrow_id` | `uint32_t` | User-assigned escrow ID |
| `from` | `account_name_type` | Sender |
| `to` | `account_name_type` | Receiver |
| `agent` | `account_name_type` | Escrow agent |
| `ratification_deadline` | `time_point_sec` | Approval deadline |
| `escrow_expiration` | `time_point_sec` | Escrow expiration |
| `hbd_balance` | `HBD_balance` | HBD in escrow (a balance class since 1.28.8, `HBD_asset` at 1.28.7) |
| `hive_balance` | `HIVE_balance` | HIVE in escrow (a balance class since 1.28.8, `HIVE_asset` at 1.28.7) |
| `pending_fee` | `balance` | Fee for agent (HIVE or HBD; a balance class since 1.28.8, `asset` at 1.28.7) |
| `to_approved` | `bool` | Receiver approved |
| `agent_approved` | `bool` | Agent approved |
| `disputed` | `bool` | Escrow is disputed |

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Primary |
| `by_from_id` | `(from, escrow_id)` | Find user's escrows |
| `by_ratification_deadline` | `(is_approved, ratification_deadline, id)` | Auto-cleanup unapproved |

**Lifecycle:** created by `escrow_transfer_evaluator` (`hive_evaluator_transfer.cpp:115`); modified by `escrow_approve` / `escrow_dispute` and by partial releases; removed by `escrow_approve` (rejection), `escrow_release` (when emptied), `expire_escrow_ratification` (`database_market.cpp:91`) for unratified escrows past deadline, and at HF23 by `remove_pending_escrows` for the escrows sent by the cleared accounts (`database_market.cpp:105-116`). Since 1.28.8 rejection, expiry and the HF23 removal share `remove_escrow`, which returns all funds to `from` before removing the object (`database_market.cpp:58-89`).

---

### savings_withdraw_object

**Source:** `detail/state/savings_withdraw_object.hpp:11` (has dynamic alloc - memo string)

Pending savings withdrawal requests (3-day delay). Since 1.28.8 `from`/`to` carry the note "can't be replaced with account_id_type - see database_api.list_savings_withdrawals API" (`savings_withdraw_object.hpp:54-55`); at 1.28.7 a TODO said they could be.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `from` | `account_name_type` | Source account |
| `to` | `account_name_type` | Destination account |
| `memo` | `shared_string` | Memo |
| `request_id` | `uint32_t` | User-assigned request ID |
| `amount` | `balance` | Withdrawal amount (HIVE or HBD; a balance class since 1.28.8, `asset` at 1.28.7) |
| `complete` | `time_point_sec` | Completion time |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_from_rid` | `(from, request_id)` |
| `by_complete_from_rid` | `(complete, from, request_id)` |
| `by_to_complete` | `(to, complete, id)` |

**Lifecycle:** created by `transfer_from_savings_evaluator` (`hive_evaluator_transfer.cpp:638`); removed by `cancel_transfer_from_savings` or on payout in `process_savings_withdraws` (`database_market.cpp:145`), and at HF23 by `remove_pending_savings_withdraws` for the requests from or to the cleared accounts (`database_market.cpp:182-228`).

---

### decline_voting_rights_request_object

**Source:** `detail/state/decline_voting_rights_request_object.hpp:7`

Pending requests to permanently decline voting rights (30-day delay).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `account` | `account_name_type` | Account declining |
| `effective_date` | `time_point_sec` | When decline takes effect |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_account` | `account` (unique) |
| `by_effective_date` | `(effective_date, account)` |

**Lifecycle:** created by `decline_voting_rights_evaluator` (`hive_evaluator_account.cpp:618`) and once at HF28 by `remove_proposal_votes_for_accounts_without_voting_rights()` (`database_hardfork.cpp:507`), which gives every proposal voter that had already declined its voting rights a request effective at once, so that its proposal votes get removed; an account that already has a request (possible before HF28 by declining again) only gets its `effective_date` reset (`database_dhf.cpp:147-206`, `:186-204`). Removed when the request executes in `process_decline_voting_rights` (`database_dhf.cpp:208`), which also removes the account's witness votes, proposal votes (HF28+, throttled by `remove_guard`) and proxy, or when cancelled (`decline = false`).

---

### vesting_delegation_object

**Source:** `detail/state/account_object.hpp:421`

Active VESTS delegation from one account to another. Uses **ids** for both parties.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `delegator` | `account_id_type` | Delegation sender |
| `delegatee` | `account_id_type` | Delegation receiver |
| `vesting_shares` | `VEST_asset` | Delegated amount (`set_vesting` asserts > 0) |
| `min_delegation_time` | `time_point_sec` | Earliest return time |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_delegation` | `(delegator, delegatee)` |

**Lifecycle:** created by `delegate_vesting_shares_evaluator` (`hive_evaluator_transfer.cpp:813`) and `account_create_with_delegation` (`hive_evaluator_account.cpp:268`); modified on delegation increase/decrease; removed when delegation set to 0 (evaluator), plus a one-time HF19 cleanup of all zero-value delegation objects (`database_hardfork.cpp:311-326`) and, at HF23, the delegations made by the cleared accounts (`clear_account`, `database.cpp:1513-1543`).

---

### vesting_delegation_expiration_object

**Source:** `detail/state/account_object.hpp:458`

Expiring delegation — delegation was removed/reduced, VESTS returning to delegator after cooldown.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `delegator` | `account_id_type` | Original delegator |
| `vesting_shares` | `VEST_asset` | Returning amount |
| `expiration` | `time_point_sec` | Return time |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_expiration` | `(expiration, id)` |
| `by_account_expiration` | `(delegator, expiration, id)` |

**Lifecycle:** created on delegation decrease/removal (`hive_evaluator_transfer.cpp:902`); removed when VESTS return in `clear_expired_delegations` (`database.cpp:3147`), and at HF23 for the VESTS returning to the cleared accounts (`clear_account`, `database.cpp:1545-1555`).

---

### withdraw_vesting_route_object

**Source:** `detail/state/withdraw_vesting_route_object.hpp:10`

Routes for power-down payouts to other accounts. Uses **names**; since 1.28.8 the source comment says they cannot become ids "because power down uses name order" (`withdraw_vesting_route_object.hpp:16-17`).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `from_account` | `account_name_type` | Source account |
| `to_account` | `account_name_type` | Destination account |
| `percent` | `uint16_t` | Percentage of powerdown to route (BPS) |
| `auto_vest` | `bool` | Auto-vest at destination |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_withdraw_route` | `(from_account, to_account)` |
| `by_destination` | `(to_account, id)` |

**Lifecycle:** created/modified/removed by `set_withdraw_vesting_route_evaluator` (`hive_evaluator_transfer.cpp:421`; percent 0 removes); read during `process_vesting_withdrawals` (`database_vesting.cpp:111`).

---

### owner_authority_history_object

**Source:** `detail/state/account_object.hpp:484` (has dynamic alloc - shared_authority)

Historical owner authority changes (for account recovery).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `account` | `account_name_type` | Account name (since 1.28.8 the source comment says an id would change `database_api.list_owner_histories`, `account_object.hpp:511`) |
| `previous_owner_authority` | `shared_authority` | Previous owner authority |
| `last_valid_time` | `time_point_sec` | When this authority was valid |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_account` | `(account, last_valid_time, id)` |

**Lifecycle:** created by `update_owner_authority` (`database.cpp:1701-1711`, object at `:1705`), which saves the owner authority it replaces each time it runs from block `HIVE_OWNER_AUTH_HISTORY_TRACKING_START_BLOCK_NUM` on (3186477 on mainnet, `hive/protocol/config.hpp:166`): for `account_update` / `account_update2` with an `owner` field (`hive_evaluator_account.cpp:311`, `:368`), `recover_account` (`:567`) and the HF9 reset of the compromised accounts (`database_hardfork.cpp:226`). `lock_account` (the HF21 and HF24 treasury lock) writes the owner with `set_owner()` directly and leaves no history object (`database.cpp:1411-1416`). Removed by per-block account-recovery processing once older than `HIVE_OWNER_AUTH_RECOVERY_PERIOD` (30 days) (`database.cpp:2000-2007`).

---

### account_recovery_request_object

**Source:** `detail/state/account_object.hpp:518` (has dynamic alloc - shared_authority)

Pending account recovery requests.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `account_to_recover` | `account_name_type` | Target account |
| `new_owner_authority` | `shared_authority` | Proposed new owner authority |
| `expires` | `time_point_sec` | Request expiration |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_account` | `account_to_recover` (unique) |
| `by_expiration` | `(expires, account_to_recover)` |

**Lifecycle:** created by `request_account_recovery_evaluator` (`hive_evaluator_account.cpp:519`); modified on re-request (or removed when re-requested with empty authority); removed by `recover_account_evaluator` on success, by expiration processing (`database.cpp:1990-1997`) or by `lock_account` (the HF21 and HF24 treasury lock, `database.cpp:1425-1427`).

---

### change_recovery_account_request_object

**Source:** `detail/state/account_object.hpp:562`

Pending change of recovery account (30-day delay). A field comment documents why `account_to_recover` stays a name: *"changing it to id would influence response from database_api.list_change_recovery_account_requests"* (`account_object.hpp:590`); `recovery_account` is marked "could be changed to id" (`:591`).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `account_to_recover` | `account_name_type` | Target account |
| `recovery_account` | `account_name_type` | New recovery account |
| `effective_on` | `time_point_sec` | When change takes effect |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_account` | `account_to_recover` (unique) |
| `by_effective_date` | `(effective_on, account_to_recover)` |

**Lifecycle:** created by `change_recovery_account_evaluator` (`hive_evaluator_account.cpp:587`); modified/removed on repeat request; removed when applied by per-block recovery processing (`database.cpp:2010+`) or by `lock_account` (the HF21 and HF24 treasury lock, `database.cpp:1429-1431`).

---

### reward_fund_object (Singleton)

**Source:** `detail/state/reward_fund_object.hpp:14`

Reward pool configuration. One instance named "post".

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `reward_fund_name_type` | Fund name (fixed_string<16>) |
| `reward_balance` | `HIVE_balance` | HIVE in reward pool (a balance class since 1.28.8, `HIVE_asset` at 1.28.7) |
| `recent_claims` | `uint128_t` | Recent reward claims |
| `last_update` | `time_point_sec` | Last update time |
| `content_constant` | `uint128_t` | Content constant for curve |
| `percent_curation_rewards` | `uint16_t` | Curation reward share |
| `percent_content_rewards` | `uint16_t` | Content reward share |
| `author_reward_curve` | `curve_id` | Author reward curve type |
| `curation_reward_curve` | `curve_id` | Curation reward curve type |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_name` | `name` (unique) |

**Lifecycle:** since 1.28.8 created at genesis with an empty balance and the default parameters (quadratic / bounded_curation curves, 25% curation, `reward_fund_object.hpp:66-70`), asserting that it gets id 0 (`database_init.cpp:258-262`); at 1.28.7 HF17 created it from the dgpo's `total_reward_fund_hive`. Before HF17 it plays the roles of the two dgpo fields that 1.28.8 removed: every block's content reward is paid into `reward_balance` (`pay_reward_funds`, `database.cpp:1953-1975`, called from both `process_funds` branches at `:1799`, `:1836`) and `recent_claims` holds the undecayed running total of rshares2 (`adjust_rshares2`, `database.cpp:1687-1699`). HF17 sets `last_update` to the HF17 block time and, except in testnet (`IS_TEST_NET`) builds, `recent_claims` to `HIVE_HF_17_RECENT_CLAIMS` (`database_hardfork.cpp:281-287`); from HF17 `process_comment_cashout` decays `recent_claims` every block (`database_comment.cpp:397-420`). Later hardforks re-tune the parameters: HF19 linear / square_root curves (`database_hardfork.cpp:301-308`), HF21 50% curation, convergent curves and `HIVE_CONTENT_CONSTANT_HF21` (`:435-444`), HF25 linear curves (`:478-482`); HF19 and HF21 also re-seed `recent_claims` outside testnet builds. Modified every block by `process_funds` and every payout by `process_comment_cashout`; never removed (`reward_fund_object.hpp:41-45`).

---

### proposal_object (DHF)

**Source:** `detail/state/dhf_objects.hpp:14` (has dynamic alloc — subject/permlink strings)

Decentralized Hive Fund proposals.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `proposal_id` | `uint32_t` | Additional key (same as id) |
| `creator` | `account_name_type` | Proposal creator |
| `receiver` | `account_name_type` | Funded account |
| `start_date` | `time_point_sec` | Funding start date |
| `end_date` | `time_point_sec` | Funding end date |
| `daily_pay` | `HBD_asset` | Requested daily HBD payment |
| `subject` | `shared_string` | Brief title |
| `permlink` | `shared_string` | Link to full description |
| `total_votes` | `uint64_t` | Recalculated every maintenance |
| `removed` | `bool` | Soft-delete flag |

**Indices:**

| Index Tag | Key Fields | Ordering |
|-----------|------------|----------|
| `by_id` | `id` | asc |
| `by_proposal_id` | `proposal_id` | asc (unique) |
| `by_start_date` | `(start_date, proposal_id)` | asc |
| `by_end_date` | `(end_date_with_delay, proposal_id)` | asc |
| `by_creator` | `(creator, proposal_id)` | asc |
| `by_total_votes` | `(total_votes, proposal_id)` | asc |

**Lifecycle:** created by `create_proposal_evaluator` (`dhf_evaluator.cpp:75`); modified by `update_proposal` and maintenance vote recalculation; soft-removed by `remove_proposal_evaluator` (sets `removed`, actual deletion throttled by `remove_guard` / `current_remove_threshold`), hard-removed by the per-block DHF cycle, which deletes only proposals flagged `removed`; expired proposals are not removed automatically and stay queryable (`dhf_processor.cpp:43-69`, code comment at `:57-63`).

---

### proposal_vote_object (DHF)

**Source:** `detail/state/dhf_objects.hpp:68`

DHF proposal votes (one object per voter/proposal pair).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `voter` | `account_name_type` | Voting account |
| `proposal_id` | `uint32_t` | Proposal being voted for |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_voter_proposal` | `(voter, proposal_id)` |
| `by_proposal_voter` | `(proposal_id, voter)` |

**Lifecycle:** created by `update_proposal_votes_evaluator` (`dhf_evaluator.cpp:197`); removed on unvote, on proposal removal, on decline-voting-rights execution (HF28+, `database_dhf.cpp:224`), and on governance vote expiration.

---

### recurrent_transfer_object

**Source:** `detail/state/recurrent_transfer_object.hpp:11` (has dynamic alloc — memo)

Scheduled recurring transfers between accounts. Uses **ids** for both parties.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `trigger_date` | `time_point_sec` | Next execution time |
| `from_id` | `account_id_type` | Sender |
| `to_id` | `account_id_type` | Receiver |
| `amount` | `asset` | Transfer amount (HIVE or HBD) |
| `memo` | `shared_string` | Memo |
| `recurrence` | `uint16_t` | Interval in hours |
| `remaining_executions` | `uint16_t` | Remaining execution count |
| `consecutive_failures` | `uint8_t` | Failure count (auto-delete at max) |
| `pair_id` | `uint8_t` | Unique per from/to pair (allows multiple transfers to same recipient, HF28 extension) |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_trigger_date` | `(trigger_date, id)` |
| `by_from_id` | `(from_id, id)` |
| `by_from_to_id` | `(from_id, to_id, pair_id)` |

**Lifecycle:** created by `recurrent_transfer_evaluator` (`hive_evaluator_transfer.cpp:979`); modified on each execution in `process_recurrent_transfers` (`database_dhf.cpp:37`) and on user edits; removed when amount set to 0, when `remaining_executions` exhausts, or after `HIVE_MAX_CONSECUTIVE_RECURRENT_TRANSFER_FAILURES` (10) consecutive failures (`database_dhf.cpp:103`, `:131-139`; the dgpo field `max_consecutive_recurrent_transfer_failures` only mirrors that constant: Part 12, Key Discovery 5).

---

### transaction_object

**Source:** `detail/state/transaction_object.hpp:21`

Tracks recent transactions for duplicate detection. Removed after expiration.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `trx_id` | `transaction_id_type` | Transaction hash |
| `expiration` | `time_point_sec` | Transaction expiration |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_trx_id` | `trx_id` (unique) |
| `by_expiration` | `(expiration, id)` |

**Lifecycle:** created for every applied transaction (`database.cpp:2695`) unless the dupe check is skipped (`:2690`), as in a replay without full validation (`chain_plugin.cpp:1255-1266`); removed by `clear_expired_transactions` (`database.cpp:3137`) once `expiration` passes. The object stores the transaction's own `expiration` field, not its runtime expiration (`database.cpp:2697-2698`), so its lifetime is bounded by `HIVE_MAX_TIME_UNTIL_EXPIRATION` (1 hour) before HF28 and by `HIVE_MAX_TIME_UNTIL_SIGNATURE_EXPIRATION` (24 hours) since HF28, when the field may be up to 24 hours ahead while the runtime expiration stays capped at 1 hour (`database.cpp:2550-2563`; Part 01, Key Discovery 8).

---

### block_summary_object (Multiton — 64K ring buffer)

**Source:** `detail/state/block_summary_object.hpp:17`

Minimal past block info for TaPOS (Transaction as Proof of Stake) validation: lets the node check `ref_block_num`/`ref_block_prefix` of incoming transactions. Fixed ring of 65536 entries.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `block_id` | `block_id_type` | Block hash |

**Indices:** Only `by_id` (accessed by `block_num & 0xFFFF`)

**Lifecycle:** all 65536 created at genesis (`database_init.cpp:305`); slot `block_num & 0xFFFF` overwritten as each block is applied; never removed.

---

### hardfork_property_object (Singleton)

**Source:** `detail/state/hardfork_property_object.hpp:15` (has dynamic alloc — vectors/maps)

Tracks hardfork state and history.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `processed_hardforks` | `t_vector<time_point_sec>` | Timestamps of all processed hardforks |
| `last_hardfork` | `uint32_t` | Last processed hardfork number |
| `current_hardfork_version` | `hardfork_version` | Current HF version |
| `next_hardfork` | `hardfork_version` | Next pending HF |
| `next_hardfork_time` | `time_point_sec` | Scheduled time of next HF |
| `h23_balances` | `t_flat_map<account_name_type, hf23_item>` | Balances cleared during HF23 (restored to airdrop list later) |

**Indices:** Only `by_id` (singleton)

**Lifecycle:** created at genesis (`database_init.cpp:257`); modified by `process_hardforks` (`database_hardfork.cpp:119`) and witness HF version voting; never removed.

---

### liquidity_reward_balance_object (Legacy — index cleared at HF12)

**Source:** `detail/state/liquidity_reward_balance_object.hpp:18`

Tracked market-maker liquidity rewards: every `HIVE_LIQUIDITY_REWARD_BLOCKS` blocks (1200, one hour) the account with the highest `weight` won a HIVE reward (`database_vesting.cpp:36`, `hive/protocol/config.hpp:287-288`; the doc comment at `liquidity_reward_balance_object.hpp:7-17` still says every 1000 blocks).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `account_id_type` | Account |
| `last_update` | `time_point_sec` | Last update (a week or more later, the next adjustment resets both volumes and the weight to 0: `database_vesting.cpp:70-75`) |
| `weight` | `uint128_t` | Volume weight: `hive_volume * hbd_volume` computed in `uint128`, or `min(hive_volume, hbd_volume)` for objects created from HF9 and for every update from HF10, when all weights were recomputed; 0 unless both volumes are positive (`liquidity_reward_balance_object.hpp:34-60`; `database_vesting.cpp:82`, `:96`, `:102-109`; `database_hardfork.cpp:236-237`) |
| `hive_volume` | `int64_t` | HIVE volume (maker +, taker -) |
| `hbd_volume` | `int64_t` | HBD volume |

**Indices:**

| Index Tag | Key Fields | Ordering |
|-----------|------------|----------|
| `by_id` | `id` | asc |
| `by_owner` | `owner` | asc (unique) |
| `by_volume_weight` | `(weight, owner)` | **weight DESC** |

**Lifecycle:** created/modified by `adjust_liquidity_reward` during order matching, which is gated by `!has_hardfork(HIVE_HARDFORK_0_12__178)` (`database_market.cpp:326-340`, create at `database_vesting.cpp:88`), i.e. only during replay of pre-HF12 blocks. **At HF12 application the entire index is cleared**: `liquidity_reward_balance_idx.clear()` with comment "liquidity reward mechanism no longer active after HF12" (`database_hardfork.cpp:245-247`). On a synced mainnet node the index is **empty**: the only residual costs are the empty container + pool allocator bookkeeping and the compiled code. The reduced pool block size of 1024 (vs default 4096) in `liquidity_reward_balance_object_multiindex.hpp:25` limits the worst-case block allocation during replay.

---

### block_stats_object (DEAD enum slot — resolved history)

**Source:** forward-declared at `hive_object_types.hpp:115`, enum slot 24 at `hive_object_types.hpp:74`, oid typedef at `:155`. **No definition exists.**

History (from git archaeology of the inherited Steem history):
- Introduced **2016-10-10** in Steem commit `4bb8af74a` ("Progress on syncing"), defined in `block_summary_object.hpp` alongside `block_summary_object`. It held one `block_id_type` per block with a unique `by_block_id` index (an unbounded catalog of all block IDs, with `block_num() = id + 1`).
- Removed **2016-12-13** in Steem commit `d4ba29d3c` ("Remove block_stats_object #675", Michael Vandeberg) — the full class, index, and reflection were deleted, but the enum entry and forward declaration were retained so the numeric values of all subsequent object types (`reward_fund_object_type` = 25 onward) would not shift, which would have invalidated the reflected enum and any serialized references.
- It is **permanently dead**, not reserved for future use. The modern `block_stats` class (`block_flow_control.hpp:18`) is an unrelated, non-chainbase telemetry struct measuring block processing times, reported via the `"block_stats"` notification (`block_flow_control.cpp:121`).

---

## Comment Archive and External Storage (RocksDB)

**This subsystem is new in 1.28 and changes the long-standing assumption that all consensus state stays in chainbase.** Source: `libraries/chain/include/hive/chain/external_storage/`, `libraries/chain/external_storage/*.cpp`, selection logic in `libraries/plugins/chain/chain_plugin.cpp`.

### The comments_handler interface

`comments_handler` (`external_storage/comments_handler.hpp:15-34`) abstracts what happens to a comment after payout:
- `on_cashout(block_num, comment, comment_cashout)` — called by consensus when a comment is paid (`database_comment.cpp:473` in `process_comment_cashout`, and `database_comment.cpp:110` in HF19's `remove_old_cashouts`)
- `on_irreversible_block(block_num)` — called from LIB processing (`database.cpp:3121`)
- `get_comment(author_id, permlink, required)`: unified lookup used by every author+permlink comment accessor of the database (`database.cpp:404-451`; the by-id accessors read chainbase only, `database_comment.cpp:46-49`, `:84-92`); returns the `comment` wrapper (`external_storage/comment.hpp`) which either points into SHM or owns a heap-reconstructed `comment_object`

### The three implementations (chain plugin option `comment-archive`)

Selection: `chain_plugin.cpp:818-837`; option declared at `chain_plugin.cpp:1540`: *"Type of comment archive to use: NONE means comments won't be archived, MEMORY keeps archived comments in memory, ROCKSDB stores them in RocksDB. Default: ROCKSDB"*. The option is declared only in builds with `USE_ALTERNATE_CHAIN_ID` (testnet and mirrornet, `chain_plugin.cpp:1539-1541`); a mainnet build always selects ROCKSDB (`:1604-1606`). Default enum value confirmed at `chain_plugin.cpp:176` (`comment_archive_choice = comment_archive_type::ROCKSDB`). Changing the option requires a replay (`memory_comment_archive.cpp` open(): "did you change comment-archive config option? if so, you need to replay").

1. **NONE → `placeholder_comment_archive`** (`placeholder_comment_archive.cpp`): pre-1.28 behavior. `on_cashout` only counts stats; paid comments stay in the chainbase `comment_index` forever; lookup goes straight to the index.

2. **MEMORY -> `memory_comment_archive`** (`memory_comment_archive.hpp/.cpp`): on cashout, remembers `(block_num -> comment_id)` in a volatile (process-memory) map; when those blocks become irreversible, each comment is **copied into a separate SHM structure and removed from the main `comment_index` via `remove_no_undo`** (`memory_comment_archive.cpp:42-46`). The archive structure is a named SHM object (`find_or_construct<archive_object_type>("memory_comment_archive")`) holding a **`hashed_unique` index over `comment_object`** keyed by the author+permlink hash, using an adaptive-pool allocator with 128K-object blocks (`memory_comment_archive.hpp:45-55`). An ABW comment explains the trade-off: the hashed index is the fastest, but rehashing it once in a while takes minutes and a lot of space, so it cannot be used in live sync, especially not on witness nodes (`memory_comment_archive.hpp:49-50`). Lookup checks the live index first, then the archive. Snapshot save/load is **not implemented** (`FC_ASSERT(false && "save_snapshot not implemented yet")`).

3. **ROCKSDB -> `rocksdb_comment_archive`** (default; `rocksdb_comment_archive.hpp/.cpp`): on cashout, creates a **`volatile_comment_object`** (chainbase, under undo, so fork switches roll it back correctly) holding a copy of the comment's fields plus `block_number` (`rocksdb_comment_archive.cpp:51-59`). On LIB processing, once the volatile index holds at least `volatile_objects_limit` entries (10,000 while the node syncs, `rocksdb_comment_archive.hpp:16`; set to 0 at the end of syncing, `rocksdb_comment_archive.cpp:215-219`), every volatile entry at/below LIB is serialized as a `rocksdb_comment_object {comment_id, parent_comment, depth}` keyed by the 20-byte author+permlink hash and written to RocksDB; then **both the volatile object and the original `comment_object` are removed from chainbase** (`rocksdb_comment_archive.cpp:100-137`). Lookup: live chainbase index first, then RocksDB point-read reconstructing a heap `comment_object` (`get_comment_impl`, `rocksdb_comment_archive.cpp:82-98`). RocksDB files live next to the shared memory file; snapshots are supported via `rocksdb_snapshot`.

### volatile_comment_object (chainbase, space ID 21)

`external_storage/comment_rocksdb_objects.hpp:19-39`:

| Field | Type | Description |
|-------|------|-------------|
| `comment_id` | `comment_id_type` | Original comment id |
| `parent_comment` | `comment_id_type` | Parent id |
| `depth` | `uint16_t` | Nesting depth |
| `block_number` | `uint32_t` | Block of cashout (drives LIB migration) |
| `author_and_permlink_hash` | `ripemd160` | Lookup key (private, get/set) |

Indices: `by_id`, `by_block` `(block_number, id)`, `by_permlink` (unique hash), defined since 1.28.8 in `external_storage/comment_rocksdb_objects_multiindex.hpp:9-24` (at 1.28.7 next to the object). Registered dynamically via `HIVE_ADD_PLUGIN_INDEX` in the archive constructor (`rocksdb_comment_archive.cpp:25`), so this index exists only on nodes running the ROCKSDB archive.

### Consequences

- On a 1.28.8 node using the ROCKSDB archive (the default, and the only choice in mainnet builds), the chainbase `comment_index` holds only comments whose payout is still pending or not yet irreversible, plus, while the node syncs, up to about 10,000 paid-out comments awaiting migration (nothing migrates before HF19: until then every comment stays in `comment_index`, and at HF19 `remove_old_cashouts` hands all paid comments to the archive at once, `rocksdb_comment_archive.cpp:104-105`, `database_comment.cpp:94-112`); the bulk of historical comments live in RocksDB on disk, dramatically reducing `shared_memory.bin` size.
- Consensus still depends on archived comments (e.g. replying to an old post must find the parent and detect permlink reuse), which is why `get_comment` transparently consults the archive and why changing archive modes requires replay.
- The archived record retains only `{comment_id, parent_comment, depth}` + hash key — consistent with the in-memory `comment_object`; the permlink string itself is still unrecoverable from core state after cashout (only its hash).

---

## RC (Resource Credits) Objects

All created at **HF20 application** (`database_hardfork.cpp:370-396`): `rc_resource_param_object`, the 24 `rc_usage_bucket_object`s, `rc_pool_object`, and both `rc_stats_object`s.

### rc_resource_param_object (Singleton)

**Source:** `rc/rc_objects.hpp:25`

Global RC resource parameters.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `resource_param_array` | `fc::int_array<rc_resource_params, 5>` | Per-resource parameters |

Each `rc_resource_params` contains:
- `resource_dynamics_params` — pool equilibrium, budget, decay rate
- `price_curve_params` — pricing coefficients {coeff_a, coeff_b, shift}

**Indices:** Only `by_id` (singleton)

**Lifecycle:** created at HF20 from `libraries/jsonball/data/resource_parameters.json` (`database_hardfork.cpp:363-381`); afterwards only the `resource_new_accounts` entry changes: at each witness schedule update from HF20 it is set from the witnesses' median `account_subsidy_rd` when that differs, with its price curve regenerated from the `rc_curve_gen_params` defaults (`rc/rc_utility.cpp:864-882`, called at `witness_schedule.cpp:437-438`); never removed.

---

### rc_pool_object (Singleton)

**Source:** `rc/rc_objects.hpp:44`

Global resource pools — consumed each block, regenerated per budget.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `pool_array` | `resource_count_type` | Current pool levels (5 resources) |
| `usage_in_window` | `resource_count_type` | Cumulative usage in window (sum of the 24 buckets) |
| `last_known_budget` | `resource_count_type` | Per-block budgets |
| `resource_weights` | `fc::int_array<uint64_t, 5>` | Popularity weights (BPS of budget) |
| `sum_of_resource_weights` | `uint64_t` | Sum of weights (divisor) |

**5 RC Resource Types:**
1. `resource_history_bytes` — transaction size on disk
2. `resource_new_accounts` — account creation tokens
3. `resource_market_bytes` — market order data
4. `resource_state_bytes` — state storage
5. `resource_execution_time` — CPU computation

**Indices:** Only `by_id` (singleton)

**Lifecycle:** created at HF20; modified every block by RC processing; never removed.

---

### rc_stats_object (Doubleton)

**Source:** `rc/rc_objects.hpp:130`; instance ids fixed at `rc_objects.hpp:179-180`

Daily RC statistics. Two instances: `RC_PENDING_STATS_ID` (oid 0) accumulating the current day, `RC_ARCHIVE_STATS_ID` (oid 1) holding the previous day (served by `rc_api`).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `block_num` | `uint32_t` | Starting block for this period |
| `regen` | `int64_t` | Global RC regeneration rate |
| `stamp` | `fc::restartable_sha256` | Rolling hash of payer RC mana |
| `budget` | `resource_count_type` | Budget at period start |
| `pool` | `resource_count_type` | Pool values at period start |
| `share` | `resource_share_type` | Popularity shares at period start |
| `op_stats` | `fc::int_array<rc_op_stats, N+1>` | Per-operation stats |
| `payer_stats` | `fc::int_array<rc_payer_stats, 8>` | Per-rank payer stats |
| `average_cost` | `fc::int_array<int64_t, 3>` | Average cost for vote/comment/transfer |

**Indices:** Only `by_id` (doubleton)

**Lifecycle:** created at HF20; pending copied to archive and reset daily; never removed.

---

### rc_direct_delegation_object

**Source:** `rc/rc_objects.hpp:182`

Direct RC delegation from one account to another.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `from` | `account_id_type` | Delegator |
| `to` | `account_id_type` | Delegatee |
| `delegated_rc` | `uint64_t` | Delegated RC amount |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_from_to` | `(from, to)` |

**Lifecycle:** created by the `delegate_rc` custom_json operation handler (`rc/rc_utility.cpp:78`); modified on re-delegation; removed on zero-delegation and when delegator's max RC drops (powerdown/delegation of underlying VESTS).

---

### rc_expired_delegation_object

**Source:** `rc/rc_objects.hpp:205`

Overflow RC delegations pending removal (when the delegation removals for one VEST change reach the remove threshold).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `from` | `account_id_type` | Original delegator |
| `expired_delegation` | `uint64_t` | Remaining RC to un-delegate |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_account` | `from` (unique) |

**Lifecycle:** created when the delegation removals for one VEST change reach the object-removal limit (`db.get_remove_threshold()`, one `remove_guard` per call, `rc/rc_utility.cpp:436-457`); drained by per-block processing of expired delegations, which has one such limit per block (`rc/rc_utility.cpp:617-656`); removed when fully processed.

---

### rc_usage_bucket_object (Multiton — 24)

**Source:** `rc/rc_objects.hpp:227`

Fixed set of 24 time buckets for RC resource usage tracking. Each covers `HIVE_RC_BUCKET_TIME_LENGTH` = 1 hour (`config.hpp:482`); `HIVE_RC_WINDOW_BUCKET_COUNT` = 24 (`config.hpp:483`). Sum across all buckets = `rc_pool_object.usage_in_window`.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `time_point_sec` | Start time of this bucket |
| `usage` | `resource_count_type` | Accumulated usage per resource |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_timestamp` | `timestamp` (unique) |

**Lifecycle:** 24 created at HF20; oldest bucket reset/reused every hour; never removed.

---

### node_property_object (Non-persisted)

**Source:** `node_property_object.hpp:15`

**Not a chainbase object.** Per-node runtime configuration. Not persisted to shared memory.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `skip_flags` | `uint32_t` | Processing skip flags |

---

## Global Properties Deep Dive

The `dynamic_global_property_object` is the source of truth for:

1. **Supply tracking**: `current_supply` (HIVE), `current_hbd_supply` (HBD), `total_vesting_shares` (VESTS), `total_vesting_fund_hive` (HIVE backing VESTS)
2. **Price derivation**: VEST price = `total_vesting_shares / total_vesting_fund_hive`
3. **Reward distribution**: `content_reward_percent`, `vesting_reward_percent`, `proposal_fund_percent`; the content reward pool itself is `reward_fund_object.reward_balance` (1.28.8 removed the dgpo's `total_reward_fund_hive`; see the note under the dgpo field table)
4. **HBD stability**: `hbd_print_rate`, `hbd_stop_percent`, `hbd_start_percent`, `hbd_interest_rate`
5. **Block production**: `head_block_number`, `time`, `current_witness`, `maximum_block_size`
6. **Witness participation**: `recent_slots_filled` (128-bit), `participation_count`
7. **Account subsidies**: `available_account_subsidies`
8. **DHF timing**: `next_maintenance_time`, `last_budget_time`, `dhf_interval_ledger`
9. **Recurrent transfer limits**: `max_consecutive_recurrent_transfer_failures`, `max_open_recurrent_transfers`, `min_recurrent_transfers_recurrence`, which only mirror the `HIVE_*` constants that the chain code reads (Part 12, Key Discovery 5)
10. **Mass-removal throttling**: `current_remove_threshold` caps how many objects automatic processing may remove per step (used with `remove_guard`, e.g. proposal/vote cleanup)

---

## Multi-Index Containers and Memory

### Index registration

Core indices are registered in 12 `initialize_core_indexes_NN()` functions (numbered 01 to 13; `_10` is commented out) spread across the `database_*.cpp` files (e.g. `database_comment.cpp:37-44`), which `initialize_core_indexes()` calls in order (`libraries/chain/index.cpp:19-34`) from `database::initialize_indexes()` (`database_init.cpp:60-64`). **37 core indices** exist: one per defined core object type. Two further chainbase indices are conditional:
- `volatile_comment_index` - added by `rocksdb_comment_archive` constructor when the ROCKSDB archive is in use (the default, and the only choice in mainnet builds; `rocksdb_comment_archive.cpp:25`)
- `account_metadata_index` — added by the metadata plugin when enabled (`metadata_plugin.cpp:199`)

### Pool allocator semantics (the "allocator hints")

Multi-index nodes use `chainbase::multi_index_allocator<T, BLOCK_SIZE>` = `pool_allocator_t<T, BLOCK_SIZE, false>` (`pool_allocator.hpp:435`). **BLOCK_SIZE is the number of objects per allocated memory block** ("BLOCK_SIZE - it means how many objects fit in allocated memory block", `pool_allocator.hpp:16`), must be a power of 2, and defaults to **4096** for multi-index nodes and 256 for undo state (`pool_allocator.hpp:430-432`). Blocks are allocated on demand — a small or empty index does not consume a full default block until objects are actually created. Singletons/doubletons therefore declare tiny block sizes:

| Object | BLOCK_SIZE | Source comment |
|--------|-----------|----------------|
| `dynamic_global_property_object` | 2 | "singleton (plus one internal)" |
| `feed_history_object` | 2 | "singleton (plus one internal)" |
| `hardfork_property_object` | 2 | "singleton (plus one internal)" |
| `reward_fund_object` | 2 | "singleton (plus one internal)" |
| `rc_resource_param_object` | 2 | "singleton (plus one internal)" |
| `rc_pool_object` | 2 | "singleton (plus one internal)" |
| `witness_schedule_object` | 4 | "dubleton (plus one internal)" |
| `rc_stats_object` | 4 | "dubleton (plus one internal)" |
| `rc_usage_bucket_object` | 32 | "multiton (always 24 plus one internal)" |
| `liquidity_reward_balance_object` | 1024 | "not used after HF12" (reduced from default 4096) |
| all others | 4096 (default) | `block_summary_object` annotated "multiton (exactly 64k objects plus one internal)" |

The "(plus one internal)" refers to the multi-index container's internal header node, which is allocated from the same pool.

### Memory cost of the legacy objects (answers former open question)

- **`liquidity_reward_balance_object`** is ~48 bytes of payload (id 4 + owner 4 + last_update 4 + pad, weight 16, 2 x int64 16) plus three ordered-index node headers. **The index is cleared at HF12** (`database_hardfork.cpp:246-247`) and only repopulated transiently during replay of pre-HF12 blocks (one object per account that took part in a qualifying order fill before HF12; nothing removes them before the HF12 clear). On a synced node: zero objects; residual cost is the empty container + pool bookkeeping (sub-KB).
- **`comment_cashout_ex_object`** is ~64 bytes of payload (2×oid 8, 2×time 8, 2×share_type 16, 3×HBD_asset 24, reward_weight 2 + pad) plus two ordered-index node headers (~120–130 B total per object, node overhead estimated). Pre-HF19 one exists per live comment, so during replay the index grows to tens of millions of objects approaching the HF19 block — then is wiped in one shot by `remove_old_cashouts()`. On a synced node: zero objects.
- The dominant residual cost of both is therefore **replay-time peak memory**, not steady-state waste. (Byte counts are computed from the field layouts at 1.28.8, unchanged from 1.28.7; padding/node overhead are estimates, not measured.)

### Singleton/Doubleton/Multiton summary

| Pattern | Objects |
|---------|---------|
| Singleton (1) | `dynamic_global_property_object`, `feed_history_object`, `hardfork_property_object`, `reward_fund_object`, `rc_resource_param_object`, `rc_pool_object` |
| Doubleton (2) | `witness_schedule_object` (current id 0 + future id 1, since HF26), `rc_stats_object` (pending id 0 + archive id 1) |
| Fixed multiton | `block_summary_object` (65536), `rc_usage_bucket_object` (24) |
| Empty post-HF | `liquidity_reward_balance_object` (cleared HF12), `comment_cashout_ex_object` (cleared HF19) |
| Never defined | `block_stats_object` |

### Objects with Most Indices

| Object | Index Count |
|--------|-------------|
| `account_object` | 6 |
| `witness_object` | 6 |
| `proposal_object` | 6 |
| `savings_withdraw_object` | 4 |
| `limit_order_object` | 4 |
| `recurrent_transfer_object` | 4 |

---

## Key Discoveries

1. **Paid-out comments leave chainbase by default (1.28).** The ROCKSDB comment archive (the default of the `comment-archive` chain option, which exists only in testnet and mirrornet builds; mainnet builds always use ROCKSDB) migrates comments to RocksDB once their cashout is irreversible: `on_cashout` creates an undo-tracked `volatile_comment_object`; LIB processing (once 10,000 are pending while the node syncs, at every irreversible block once live) writes `{comment_id, parent_comment, depth}` keyed by author+permlink hash to RocksDB and removes both objects from chainbase. Lookups transparently fall back to the archive via `database::get_comment` -> `comments_handler::get_comment`. MEMORY mode instead keeps archived comments in a hashed SHM index; NONE preserves the old keep-everything behavior. Switching modes requires replay.

2. **RC mana is embedded in account_object**, not in a separate `rc_account_object`. The `rc_manabar`, `rc_adjustment`, `delegated_rc`, `received_rc`, and `last_max_rc` fields are directly on the account (`last_max_rc` is the maximum RC last recorded by the RC code, which adds to or caps `rc_manabar` against it when the maximum changes, `rc/rc_utility.cpp:468-488`; its source comment calls it a bug-catching aid that "can be removed once RC becomes part of consensus", see the account_object field table). The old RC plugin's `rc_account_object` no longer exists.

3. **comment_object stores only a hash, not author+permlink strings.** `author_and_permlink_hash` = RIPEMD-160 of `permlink + "@" + author_id`. The permlink string lives only in `comment_cashout_object` (deleted at payout), so for cashed-out comments the permlink is unrecoverable from core state — including from the RocksDB archive, which stores the same hash-keyed minimal record.

4. **comment_cashout_object shares its ID with comment_object** (1:0..1; same for the legacy `comment_cashout_ex_object`). The shared-id trick is documented in the constructors (`comment_object.hpp:125,280`).

5. **comment_vote_objects are short-lived**: removed in bulk at the comment's payout (`database_comment.cpp:365-372`) and on comment deletion. The index only holds votes for comments inside the 7-day cashout window — this, plus the comment archive, is what keeps `shared_memory.bin` bounded.

6. **block_stats_object is a fossil, not a reservation**: a real object in Steem from 2016-10-10 (one block_id per block) deleted on 2016-12-13 (steemit/steem#675); the enum slot survives only to keep later type IDs stable. The modern `block_stats` telemetry class in `block_flow_control.hpp` is unrelated.

7. **account_metadata_object is plugin-level and OFF by default**: the metadata plugin is not in hived's default plugin set (`programs/hived/main.cpp:117-122`), so a default node tracks no JSON metadata. `memo_key` stays on `account_object` precisely because witnesses don't run the metadata plugin (`account_object.hpp:282`). The plugin reserves space ID 22 but the object keeps core ID 2 (it was moved out of core without changing its type id).

8. **Object IDs are 4-byte** (`oid`/`oid_ref` wrap `uint32_t`), and typed assets are 8-byte amounts with compile-time symbols; since 1.28.8 the balance classes that hold funds in chain objects have the size of what they wrap (8 bytes for the `tiny_balance` types such as `HIVE_balance`, 16 for `balance` like `asset`: `tests/unit/tests/basic_tests.cpp:706-709`). This is relevant when reasoning about object sizes and the id-vs-name trade-off (a name is 16 bytes, an id 4).

9. **Name-vs-id inconsistency is documented in-code, with reasons**: escrow's TODO carries ABW's counterargument (id would make lookup harder since operations address escrows by `(from_name, escrow_id)`); `change_recovery_account_request` notes that switching to ids would change `database_api.list_change_recovery_account_requests` responses. Since 1.28.8 the source gives reasons for more of them: savings withdrawals and the limit order `seller` keep names because `database_api.list_savings_withdrawals` and `database_api.list_limit_orders` use them, withdraw routes because power down uses name order, and the owner authority history because of `database_api.list_owner_histories` (`savings_withdraw_object.hpp:54-55`, `limit_order_object.hpp:68`, `withdraw_vesting_route_object.hpp:16-17`, `account_object.hpp:511`). So the remaining name-based objects (escrow, savings_withdraw, limit_order seller, witness_vote, proposal/proposal_vote, withdraw_route, recovery family, decline_voting) are blocked less by hardfork mechanics than by lookup ergonomics and API stability.

10. **Hardforks create and destroy whole index populations**: HF12 clears liquidity rewards; HF19 wipes all `comment_cashout_ex` objects and all paid `comment_cashout` objects (`remove_old_cashouts`); HF20 creates the RC infrastructure objects (param, pool, two stats, 24 buckets); HF21/HF24 create the treasury account if it does not exist yet; HF26 creates the future witness schedule (asserting it gets id 1). HF17 created the reward fund at 1.28.7; since 1.28.8 genesis creates it and HF17 only sets its `last_update` and seeds `recent_claims` (see the reward_fund_object Lifecycle).

11. **Witness scheduling uses virtual time**: three `fc::uint128` fields (`virtual_last_update`, `virtual_position`, `virtual_scheduled_time`) implement proportional-to-votes scheduling for the timeshare slot.

12. **HBD interest is tracked via a time-weighted accumulator**: `hbd_seconds = balance × seconds_held`, paid at most monthly, with separate accumulators for liquid and savings HBD (only savings earns interest since HF25 — the liquid accumulator fields remain).

13. **The whole chain shares a year-2106 timestamp horizon**: `fc::time_point_sec` stores `uint32_t utc_seconds` (`fc/time.hpp:78-90`), and `manabar.last_update_time` mirrors that as raw `uint32_t` (`util/manabar.hpp:35`). `manabar::regenerate_mana` would trip `FC_ASSERT(now >= last_update_time)` on wraparound, but no field anywhere in state survives 2106 without a (state-breaking, not consensus-urgent) migration. Not a practical concern for decades.

14. **Field packing in account_object is deliberate** (`account_object.hpp:200`): members are ordered to minimize padding around the leading 4-byte id, which is why the declaration order looks scrambled relative to logical grouping.

15. **`EnableNoUndo` is a special-purpose chainbase feature used only by comment_object**, and only the MEMORY archive uses it (`memory_comment_archive.cpp:44`; the default ROCKSDB archive removes comments with the undoable `remove()`, `rocksdb_comment_archive.cpp:131`): safe because comments are immutable and archived >= 7 days after creation, so no undo session can reference them; the chainbase doc comment explicitly warns it would be unsafe for `volatile_comment_object` (`chainbase/util/object.hpp:26-35`).

---

## Code References

| Object | Header | Multiindex |
|--------|--------|------------|
| `account_object` family | `detail/state/account_object.hpp` | `detail/state/account_object_multiindex.hpp` |
| `comment_object` family | `detail/state/comment_object.hpp` | `detail/state/comment_object_multiindex.hpp` |
| `witness_object` family | `detail/state/witness_objects.hpp` | `detail/state/witness_objects_multiindex.hpp` |
| `dynamic_global_property_object` | `detail/state/global_property_object.hpp` | `detail/state/global_property_object_multiindex.hpp` |
| `proposal_object` family | `detail/state/dhf_objects.hpp` | `detail/state/dhf_objects_multiindex.hpp` |
| `limit_order_object` | `detail/state/limit_order_object.hpp` | `detail/state/limit_order_object_multiindex.hpp` |
| `convert_request_object` | `detail/state/convert_request_object.hpp` | `detail/state/convert_request_object_multiindex.hpp` |
| `collat. convert_request_object` | `detail/state/collateralized_convert_request_object.hpp` | same pattern |
| `escrow_object` | `detail/state/escrow_object.hpp` | `detail/state/escrow_object_multiindex.hpp` |
| `savings_withdraw_object` | `detail/state/savings_withdraw_object.hpp` | `detail/state/savings_withdraw_object_multiindex.hpp` |
| `recurrent_transfer_object` | `detail/state/recurrent_transfer_object.hpp` | `detail/state/recurrent_transfer_object_multiindex.hpp` |
| RC objects | `rc/rc_objects.hpp` | `rc/rc_objects_multiindex.hpp` (since 1.28.8; inline at 1.28.7) |
| `account_metadata_object` | `plugins/metadata/.../metadata_objects.hpp` | `plugins/metadata/.../metadata_objects_multiindex.hpp` (since 1.28.8; same file at 1.28.7) |
| Comment archive | `external_storage/comments_handler.hpp`, `comment_rocksdb_objects.hpp`, `rocksdb_comment_archive.hpp`, `memory_comment_archive.hpp`, `placeholder_comment_archive.hpp` | `external_storage/comment_rocksdb_objects_multiindex.hpp` (`volatile_comment_index`, since 1.28.8; inline at 1.28.7) |
| Archive selection | `libraries/plugins/chain/chain_plugin.cpp:172-176, 818-837, 1540` | — |
| Object id / pool allocator | `chainbase/util/object_id.hpp`, `chainbase/pool_allocator.hpp` | — |
| Index registration | `initialize_core_indexes_NN` in `database_*.cpp` (e.g. `database_comment.cpp:37`) | — |
| HF cleanups | `database_hardfork.cpp:245-247` (HF12), `:281-287` (HF17, sets the reward fund's `last_update` and seeds `recent_claims`; genesis creates the fund since 1.28.8), `:328` (HF19), `:370-396` (HF20), `:498-503` (HF26) | - |
| Cashout/vote removal | `database_comment.cpp:94-112` (`remove_old_cashouts`), `:365-372` (vote removal), `:471-475` (cashout removal + archive call) | — |

---

## Discrepancies and Potential Issues

1. **Type ID 24 (`block_stats_object`) is dead weight, not a reservation.** The class was deleted from Steem in Dec 2016; only the enum entry, forward declaration, and an `oid_ref` typedef remain, kept solely to preserve subsequent enum values. A same-named but unrelated telemetry class (`block_flow_control.hpp:18`) now exists, which invites confusion. Cleanup would require either renaming the dead slot (e.g. `legacy_object_type_24`) or documenting it in-code.

2. **`account_metadata_object_type` (ID 2) couples the core enum to a plugin.** The object was moved into the metadata plugin while keeping its core type ID (changing it would break state). The plugin also reserves space ID 22 that this object doesn't use. Consequence: the core enum is not a reliable inventory of core-managed state, and one core ID is owned by optional code.

3. **(Corrected from earlier revision)** `liquidity_reward_balance_object`'s `1024` is a *pool block size* (objects per allocation block), not pre-reserved memory — and it is *smaller* than the 4096 default, deliberately so for a dead index. The index is **cleared at HF12** (`database_hardfork.cpp:246-247`); it does not waste meaningful memory on a synced node, only transiently during pre-HF12 replay.

4. **(Corrected from earlier revision)** `comment_cashout_ex_object`s do **not** linger after HF19: `remove_old_cashouts()` clears the entire index at HF19 application (`database_comment.cpp:97-98`). The remaining cost is the (empty) registered index, the compiled code paths, and the replay-time population before HF19.

5. **Inconsistent `account_id_type` vs `account_name_type` across objects persists**, but in-code comments show it's a conscious trade-off (escrow lookup ergonomics, API response stability) rather than mere debt. Migrating would save 12 bytes per reference and require a hardfork plus API versioning; nothing in the code signals active plans.

6. **`witness_schedule_object` doubleton semantics changed at HF26**: id 0 = current schedule, id 1 = future schedule (created with an `FC_ASSERT` on its id). Code reading "the" schedule must pick the right instance; the allocator comment "dubleton (plus one internal)" documents the expected population.

7. **The memory comment archive cannot snapshot**: `memory_comment_archive::save_snapshot/load_snapshot` are `FC_ASSERT( false && "... not implemented yet" )` (`memory_comment_archive.cpp:83-93`). Nodes using `comment-archive = MEMORY` (an option that only testnet and mirrornet builds have) cannot use state snapshots; ROCKSDB mode implements snapshot supplements. Operationally this makes MEMORY mode a second-class option.

8. **Several "REMOVE" comments** mark fields kept only for APIs/tests: `account_object` (`created`, `block_created`, `last_account_update`, `last_vote_time`, `post_count`, `mined`, `block_last_account_recovery`), `comment_vote_object` (`last_update`). Removing them is a state-format change (replay/migration), not consensus-breaking.

---

## Open Questions

1. **Are there plans to migrate remaining `account_name_type` references to `account_id_type`?** At 1.28.8 a "can be replaced with account_id_type" TODO remains on the escrow parties, with ABW's counterargument (`escrow_object.hpp:69-71`), `change_recovery_account_request_object::recovery_account` is still marked "could be changed to id" (`account_object.hpp:591`), and the dgpo's `current_witness` TODO reads "check if worth replacing with account_id_type (ABW: probably not)" (`global_property_object.hpp:208`); the savings-withdraw and limit-order TODOs of 1.28.7 became notes that the names must stay, and withdraw routes and owner histories gained such notes (Key Discovery 9). No migration scaffolding exists in the code; would need confirmation from the dev team whether anything is scheduled for a future HF. *(Partially answered: the blockers are documented; no plan is visible in source.)*

2. **Is a split of the 50+-field `account_object` planned** (analogous to the authority/metadata splits)? The packing comment and REMOVE markers suggest awareness, and the metadata/memo_key comment shows the direction (move non-consensus data to plugins), but no split is visible at 1.28.8, which made the account's fund and delegation members private behind getters but kept every field in the object.

3. **What are the operational parameters of the RocksDB comment archive at scale** (compaction behavior, read latency for `get_comment` misses on old posts, disk footprint vs the SHM savings)? The code fixes `volatile_objects_limit = 10'000` while the node syncs (0 once live, `rocksdb_comment_archive.cpp:215-219`) and submits the RocksDB write batch after each LIB batch (`:137`); since 1.28.8 the periodic state flush only submits that write batch too, and a full RocksDB flush (`flushDb`) happens when the node closes or finishes syncing and when a state snapshot is written (also when the database is first created, `rocksdb_storage_provider.cpp:211`, and before a snapshot load replaces it, `rocksdb_snapshot.cpp:93`; `rocksdb_comment_archive.cpp:202-213`; `database.cpp:304`, `:863`; `rocksdb_snapshot.cpp:55`). Real-world sizing data belongs to a deployment-focused zoom (candidate for a dedicated deep-dive on `external_storage/`).

4. **Why does the comment_cashout_logging plugin use space ID 666** while all other plugins use small sequential IDs? Cosmetic curiosity; no functional impact found. *(Answered by code reading: the plugin only defines the macro, no chainbase object uses it, and `666 << 8` would not fit the 16-bit type number; see the Space ID table above. Same at 1.28.7.)*
