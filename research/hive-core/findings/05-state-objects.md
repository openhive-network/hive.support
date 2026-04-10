# Findings: State Objects — Blockchain Database Schema

## Summary

The Hive blockchain maintains its state as a set of **35 object types** stored in shared memory via chainbase (a memory-mapped database). Each object type has a unique numeric ID from the `object_type` enum, and each instance is stored in a Boost.MultiIndex container that provides multiple lookup indices. This document catalogs every state object, its fields, indices, and role in the system.

**Key architectural points:**
- All state objects live in chainbase shared memory (no RocksDB for core state)
- Objects are accessed through Boost.MultiIndex containers with composite keys
- Several objects are **singletons** (one instance): `dynamic_global_property_object`, `feed_history_object`, `hardfork_property_object`, `reward_fund_object`, `rc_resource_param_object`, `rc_pool_object`
- The `witness_schedule_object` and `rc_stats_object` are **doubletons** (exactly 2 instances — current and future/archive)
- The `block_summary_object` is a **multiton** (exactly 65536 instances for TaPOS)
- `account_metadata_object` lives in a **plugin** (metadata plugin), not core chain
- `block_stats_object` is **forward-declared but never defined** — a reserved type ID
- RC state (mana) is embedded directly in `account_object`, not in a separate RC account object
- The `comment_object` stores only a RIPEMD-160 hash of author+permlink, not the raw strings

## Object Type Enum

Source: `libraries/chain/include/hive/chain/hive_object_types.hpp:47-88`

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
| 24 | `block_stats_object_type` | Blocks (RESERVED) |
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

**Total: 39 type IDs** (0–38), of which 37 have actual object definitions (block_stats_object is reserved; account_metadata is plugin-level).

---

## State Objects Reference

---

### dynamic_global_property_object (Singleton)

**Source:** `detail/state/global_property_object.hpp`

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
| `total_vesting_fund_hive` | `HIVE_asset` | HIVE backing all VESTS |
| `total_vesting_shares` | `VEST_asset` | Total VESTS in existence |
| `total_reward_fund_hive` | `HIVE_asset` | Pending liquid reward pool |
| `total_reward_shares2` | `fc::uint128` | Running total of REWARD^2 |
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

**Computed Properties:**
- `get_vesting_share_price()` — VEST/HIVE conversion price (from `total_vesting_shares` / `total_vesting_fund_hive`)
- `get_reward_vesting_share_price()` — includes pending rewards in price calculation

**Indices:** Only `by_id` (singleton — only one instance)

---

### account_object

**Source:** `detail/state/account_object.hpp`

The largest and most complex state object. Stores all account state including balances, manabars, voting data, and RC state.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `account_name_type` | Account name (3-16 chars) |
| `proxy` | `account_id_type` | Governance proxy (0 = none) |
| `recovery_account` | `account_id_type` | Recovery account (0 = top witness) |
| `last_account_recovery` | `time_point_sec` | Last successful recovery |
| `block_last_account_recovery` | `time_point_sec` | Same from block time |
| **Balances** | | |
| `balance` | `HIVE_asset` | Liquid HIVE |
| `savings_balance` | `HIVE_asset` | HIVE in savings (3-day withdrawal) |
| `reward_hive_balance` | `HIVE_asset` | Unclaimed HIVE rewards |
| `hbd_balance` | `HBD_asset` | Liquid HBD |
| `savings_hbd_balance` | `HBD_asset` | HBD in savings (earns interest) |
| `reward_hbd_balance` | `HBD_asset` | Unclaimed HBD rewards |
| `reward_vesting_balance` | `VEST_asset` | Unclaimed VEST rewards |
| `reward_vesting_hive` | `HIVE_asset` | HIVE counterweight to reward VESTS |
| **Vesting** | | |
| `vesting_shares` | `VEST_asset` | Total VESTS held |
| `delegated_vesting_shares` | `VEST_asset` | VESTS delegated out |
| `received_vesting_shares` | `VEST_asset` | VESTS delegated in |
| `vesting_withdraw_rate` | `VEST_asset` | Weekly power down rate |
| `withdrawn` | `VEST_asset` | VESTS already withdrawn in current powerdown |
| `to_withdraw` | `VEST_asset` | Total VESTS to withdraw in current powerdown |
| `next_vesting_withdrawal` | `time_point_sec` | Next powerdown payment (max = inactive) |
| `withdraw_routes` | `uint16_t` | Number of withdrawal routes (max 10) |
| **Manabars** | | |
| `voting_manabar` | `manabar` | Upvote mana {current_mana: int64, last_update_time: uint32} |
| `downvote_manabar` | `manabar` | Downvote mana |
| `rc_manabar` | `manabar` | Resource credit mana |
| **RC** | | |
| `rc_adjustment` | `share_type` | Extra RC from account creation fee |
| `delegated_rc` | `share_type` | RC delegated out |
| `received_rc` | `share_type` | RC delegated in |
| `last_max_rc` | `share_type` | Debug: last max RC value |
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
| `post_count` | `uint32_t` | Total posts (non-consensus) |
| `post_bandwidth` | `uint32_t` | Post bandwidth (HF12-17 root comment reward influence) |
| `last_post` | `time_point_sec` | Last post/comment time |
| `last_root_post` | `time_point_sec` | Last root post time |
| `last_post_edit` | `time_point_sec` | Last post edit time |
| `last_vote_time` | `time_point_sec` | Last vote time (non-consensus) |
| **Delayed Voting** | | |
| `delayed_votes` | `t_vector<delayed_votes_data>` | VESTS per day pending activation (30-day delay) |
| `sum_delayed_votes` | `ushare_type` | Sum of delayed votes |
| **Other** | | |
| `pending_claimed_accounts` | `share_type` | Claimed but unused account tokens |
| `pending_escrow_transfers` | `uint16_t` | Active escrow count (max 255) |
| `open_recurrent_transfers` | `uint16_t` | Active recurrent transfers (max 255) |
| `savings_withdraw_requests` | `uint8_t` | Active savings withdrawals |
| `curation_rewards` | `HIVE_asset` | Cumulative curation rewards (non-consensus) |
| `posting_rewards` | `HIVE_asset` | Cumulative author rewards (non-consensus) |
| `created` | `time_point_sec` | Account creation time (non-consensus) |
| `block_created` | `time_point_sec` | Creation time from block (non-consensus) |
| `last_account_update` | `time_point_sec` | Last account update (non-consensus) |
| `mined` | `bool` | Created via POW mining (non-consensus) |
| `memo_key` | `public_key_type` | Memo key (33 bytes) |

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

---

### account_authority_object

**Source:** `detail/state/account_object.hpp:339`

Separate object for authority storage (owner/active/posting keys). Split from account_object to reduce size of main object.

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

---

### account_metadata_object (Plugin)

**Source:** `plugins/metadata/include/hive/plugins/metadata/metadata_objects.hpp`

**Note:** This is a plugin-level object, not core chain. Stores JSON metadata separately from account_object.

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

---

### comment_object

**Source:** `detail/state/comment_object.hpp`

Minimal comment/post identity object. Stores only a hash (not raw author+permlink strings). No dynamic allocations.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `parent_comment` | `comment_id_type` | Parent comment ID (null = root post) |
| `author_and_permlink_hash` | `fc::ripemd160` | RIPEMD-160 hash of `permlink@author_id` |
| `depth` | `uint16_t` | Nesting depth (0 = root post) |

**Computed:**
- `is_root()` — true when `parent_comment` is null
- `compute_author_and_permlink_hash(author_id, permlink)` = `RIPEMD160(permlink + "@" + to_string(author_id))`

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Primary |
| `by_permlink` | `author_and_permlink_hash` | Consensus lookup by author+permlink |

---

### comment_cashout_object

**Source:** `detail/state/comment_object.hpp:103`

Holds payout-related data for comments with pending cashout. **Removed after cashout** (since HF19). Shares `id` with its `comment_object`.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `author_id` | `account_id_type` | Comment author |
| `permlink` | `shared_string` | Comment permlink |
| `net_rshares` | `share_type` | Sum of all vote rshares |
| `vote_rshares` | `share_type` | Sum of positive vote rshares |
| `total_vote_weight` | `uint64_t` | Accumulated vote weight for curation split |
| `max_accepted_payout` | `HBD_asset` | Max payout (default 1000 HBD) |
| `net_votes` | `int32_t` | Upvotes minus downvotes (API only) |
| `children` | `uint32_t` | Direct reply count |
| `created` | `time_point_sec` | Creation time |
| `cashout_time` | `time_point_sec` | Scheduled cashout (7 days after creation since HF17) |
| `percent_hbd` | `uint16_t` | Percent of reward in HBD (BPS) |
| `allow_votes` | `bool` | Voting enabled |
| `allow_curation_rewards` | `bool` | Curation rewards enabled |
| `was_voted_on` | `bool` | Has received at least one vote |
| `beneficiaries` | `t_vector<stored_beneficiary_route_type>` | Beneficiary list {account_id, weight} |

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Shares ID with comment_object |
| `by_cashout_time` | `(cashout_time, id)` | Process pending payouts |

---

### comment_cashout_ex_object (Legacy)

**Source:** `detail/state/comment_object.hpp:272`

Extended cashout data from pre-HF19. **Empty after HF19** — no new objects created. Shares `id` with `comment_object`.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `root_comment` | `comment_id_type` | Root of discussion tree |
| `last_payout` | `time_point_sec` | Previous payout time |
| `max_cashout_time` | `time_point_sec` | Max cashout deadline (pre-HF17) |
| `abs_rshares` | `share_type` | Absolute rshares |
| `children_abs_rshares` | `share_type` | Discussion abs rshares |
| `total_payout_value` | `HBD_asset` | Cumulative payouts |
| `curator_payout_value` | `HBD_asset` | Cumulative curator payouts |
| `beneficiary_payout_value` | `HBD_asset` | Cumulative beneficiary payouts |
| `reward_weight` | `uint16_t` | Reward weight percentage (BPS) |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_root` | `(root_comment, id)` |

---

### comment_vote_object

**Source:** `detail/state/comment_object.hpp:372`

Tracks each voter/comment pair. One object per vote.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `voter` | `account_id_type` | Voting account |
| `comment` | `comment_id_type` | Voted comment |
| `weight` | `uint64_t` | Vote weight for curation rewards (0 for downvotes/edits) |
| `rshares` | `int64_t` | rshares this vote contributes |
| `vote_percent` | `int16_t` | Vote percentage (-10000 to 10000) |
| `last_update` | `time_point_sec` | Last update time (non-consensus) |

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Primary |
| `by_comment_voter` | `(comment, voter)` | Find vote for specific comment |
| `by_voter_comment` | `(voter, comment)` | Find all votes by voter |

---

### witness_object

**Source:** `detail/state/witness_objects.hpp:69`

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

---

### witness_vote_object

**Source:** `detail/state/witness_objects.hpp:173`

Links accounts to witnesses they voted for.

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

---

### witness_schedule_object (Doubleton)

**Source:** `detail/state/witness_objects.hpp:183`

Current witness schedule. Two instances: current and future schedule.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `current_virtual_time` | `fc::uint128` | Virtual time state |
| `next_shuffle_block_num` | `uint32_t` | Next schedule shuffle block |
| `current_shuffled_witnesses` | `fc::array<account_name_type, 21>` | Shuffled witness list |
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

**Indices:** Only `by_id` (doubleton — max 2+1 internal instances)

---

### feed_history_object (Singleton)

**Source:** `detail/state/feed_history_object.hpp`

Tracks HBD/HIVE price feed history. Updated once per hour.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `current_median_history` | `HBD_price` | Current median price (used for conversions) |
| `market_median_history` | `HBD_price` | Market median (same unless artificially adjusted) |
| `current_min_history` | `HBD_price` | Min price (for collateralized conversion) |
| `current_max_history` | `HBD_price` | Max price in window |
| `price_history` | `t_deque<HBD_price>` | Last week of hourly medians |

**Indices:** Only `by_id` (singleton)

---

### limit_order_object

**Source:** `detail/state/limit_order_object.hpp`

Open internal market (HIVE/HBD) limit orders.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `created` | `time_point_sec` | Order creation time |
| `expiration` | `time_point_sec` | Expiration time |
| `seller` | `account_name_type` | Seller account |
| `orderid` | `uint32_t` | User-assigned order ID |
| `for_sale` | `share_type` | Amount for sale (asset type from sell_price.base) |
| `sell_price` | `price` | Price (base/quote pair) |

**Indices:**

| Index Tag | Key Fields | Ordering | Notes |
|-----------|------------|----------|-------|
| `by_id` | `id` | asc | Primary |
| `by_expiration` | `(expiration, id)` | asc | Auto-cleanup expired orders |
| `by_price` | `(sell_price, id)` | **price DESC**, id asc | Order matching |
| `by_account` | `(seller, orderid)` | asc | Find user's orders |

---

### convert_request_object

**Source:** `detail/state/convert_request_object.hpp`

Pending HBD->HIVE conversion requests (3.5-day delay).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `account_id_type` | Request owner |
| `amount` | `HBD_asset` | HBD amount to convert |
| `requestid` | `uint32_t` | User-assigned request ID |
| `conversion_date` | `time_point_sec` | Conversion execution date |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_conversion_date` | `(conversion_date, id)` |
| `by_owner` | `(owner, requestid)` |

---

### collateralized_convert_request_object

**Source:** `detail/state/collateralized_convert_request_object.hpp`

Pending HIVE->HBD collateralized conversion requests (3.5-day delay). HBD is given immediately; HIVE collateral returned after conversion minus actual price.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `account_id_type` | Request owner |
| `collateral_amount` | `HIVE_asset` | HIVE collateral locked |
| `converted_amount` | `HBD_asset` | HBD already given to owner |
| `requestid` | `uint32_t` | User-assigned request ID |
| `conversion_date` | `time_point_sec` | Conversion execution date |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_conversion_date` | `(conversion_date, id)` |
| `by_owner` | `(owner, requestid)` |

---

### escrow_object

**Source:** `detail/state/escrow_object.hpp`

Active escrow transfers between accounts with an agent.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `escrow_id` | `uint32_t` | User-assigned escrow ID |
| `from` | `account_name_type` | Sender |
| `to` | `account_name_type` | Receiver |
| `agent` | `account_name_type` | Escrow agent |
| `ratification_deadline` | `time_point_sec` | Approval deadline |
| `escrow_expiration` | `time_point_sec` | Escrow expiration |
| `hbd_balance` | `HBD_asset` | HBD in escrow |
| `hive_balance` | `HIVE_asset` | HIVE in escrow |
| `pending_fee` | `asset` | Fee for agent (HIVE or HBD) |
| `to_approved` | `bool` | Receiver approved |
| `agent_approved` | `bool` | Agent approved |
| `disputed` | `bool` | Escrow is disputed |

**Indices:**

| Index Tag | Key Fields | Notes |
|-----------|------------|-------|
| `by_id` | `id` | Primary |
| `by_from_id` | `(from, escrow_id)` | Find user's escrows |
| `by_ratification_deadline` | `(is_approved, ratification_deadline, id)` | Auto-cleanup unapproved |

---

### savings_withdraw_object

**Source:** `detail/state/savings_withdraw_object.hpp`

Pending savings withdrawal requests (3-day delay).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `from` | `account_name_type` | Source account |
| `to` | `account_name_type` | Destination account |
| `memo` | `shared_string` | Memo |
| `request_id` | `uint32_t` | User-assigned request ID |
| `amount` | `asset` | Withdrawal amount (HIVE or HBD) |
| `complete` | `time_point_sec` | Completion time |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_from_rid` | `(from, request_id)` |
| `by_complete_from_rid` | `(complete, from, request_id)` |
| `by_to_complete` | `(to, complete, id)` |

---

### decline_voting_rights_request_object

**Source:** `detail/state/decline_voting_rights_request_object.hpp`

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

---

### vesting_delegation_object

**Source:** `detail/state/account_object.hpp:366`

Active VESTS delegation from one account to another.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `delegator` | `account_id_type` | Delegation sender |
| `delegatee` | `account_id_type` | Delegation receiver |
| `vesting_shares` | `VEST_asset` | Delegated amount |
| `min_delegation_time` | `time_point_sec` | Earliest return time |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_delegation` | `(delegator, delegatee)` |

---

### vesting_delegation_expiration_object

**Source:** `detail/state/account_object.hpp:402`

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

---

### withdraw_vesting_route_object

**Source:** `detail/state/withdraw_vesting_route_object.hpp`

Routes for power-down payouts to other accounts.

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

---

### owner_authority_history_object

**Source:** `detail/state/account_object.hpp:427`

Historical owner authority changes (for account recovery).

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `account` | `account_name_type` | Account name |
| `previous_owner_authority` | `shared_authority` | Previous owner authority |
| `last_valid_time` | `time_point_sec` | When this authority was valid |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_account` | `(account, last_valid_time, id)` |

---

### account_recovery_request_object

**Source:** `detail/state/account_object.hpp:454`

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

---

### change_recovery_account_request_object

**Source:** `detail/state/account_object.hpp:498`

Pending change of recovery account (30-day delay).

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

---

### reward_fund_object (Singleton)

**Source:** `detail/state/reward_fund_object.hpp`

Reward pool configuration. One instance named "post".

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `reward_fund_name_type` | Fund name (fixed_string<16>) |
| `reward_balance` | `HIVE_asset` | HIVE in reward pool |
| `recent_claims` | `uint128_t` | Recent reward claims |
| `last_update` | `time_point_sec` | Last update time |
| `content_constant` | `uint128_t` | Content constant for curve |
| `percent_curation_rewards` | `uint16_t` | Curation reward share (default 25%) |
| `percent_content_rewards` | `uint16_t` | Content reward share (default 100%) |
| `author_reward_curve` | `curve_id` | Author reward curve type |
| `curation_reward_curve` | `curve_id` | Curation reward curve type |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_name` | `name` (unique) |

---

### proposal_object (DHF)

**Source:** `detail/state/dhf_objects.hpp`

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

---

### recurrent_transfer_object

**Source:** `detail/state/recurrent_transfer_object.hpp`

Scheduled recurring transfers between accounts.

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
| `pair_id` | `uint8_t` | Unique per from/to pair |

**Indices:**

| Index Tag | Key Fields |
|-----------|------------|
| `by_id` | `id` |
| `by_trigger_date` | `(trigger_date, id)` |
| `by_from_id` | `(from_id, id)` |
| `by_from_to_id` | `(from_id, to_id, pair_id)` |

---

### transaction_object

**Source:** `detail/state/transaction_object.hpp`

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

---

### block_summary_object (Multiton — 64K)

**Source:** `detail/state/block_summary_object.hpp`

Minimal past block info for TaPOS (Transaction as Proof of Stake) validation. Fixed ring buffer of 65536 entries.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `block_id` | `block_id_type` | Block hash |

**Indices:** Only `by_id` (accessed by `block_num & 0xFFFF`)

---

### hardfork_property_object (Singleton)

**Source:** `detail/state/hardfork_property_object.hpp`

Tracks hardfork state and history.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `processed_hardforks` | `t_vector<time_point_sec>` | Timestamps of all processed hardforks |
| `last_hardfork` | `uint32_t` | Last processed hardfork number |
| `current_hardfork_version` | `hardfork_version` | Current HF version |
| `next_hardfork` | `hardfork_version` | Next pending HF |
| `next_hardfork_time` | `time_point_sec` | Scheduled time of next HF |
| `h23_balances` | `t_flat_map<account_name_type, hf23_item>` | Balances cleared during HF23 |

**Indices:** Only `by_id` (singleton)

---

### liquidity_reward_balance_object (Legacy)

**Source:** `detail/state/liquidity_reward_balance_object.hpp`

**Not used after HF12.** Tracked market maker liquidity rewards.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `account_id_type` | Account |
| `last_update` | `time_point_sec` | Last update |
| `weight` | `uint128_t` | Volume weight |
| `hive_volume` | `int64_t` | HIVE volume |
| `hbd_volume` | `int64_t` | HBD volume |

**Indices:**

| Index Tag | Key Fields | Ordering |
|-----------|------------|----------|
| `by_id` | `id` | asc |
| `by_owner` | `owner` | asc (unique) |
| `by_volume_weight` | `(weight, owner)` | **weight DESC** |

---

### block_stats_object (RESERVED)

**Source:** Forward-declared in `hive_object_types.hpp:114` but **never defined**. Type ID 24 is reserved.

---

## RC (Resource Credits) Objects

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

---

### rc_pool_object (Singleton)

**Source:** `rc/rc_objects.hpp:44`

Global resource pools — consumed each block, regenerated per budget.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `pool_array` | `resource_count_type` | Current pool levels (5 resources) |
| `usage_in_window` | `resource_count_type` | Cumulative usage in window |
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

---

### rc_stats_object (Doubleton)

**Source:** `rc/rc_objects.hpp:130`

Daily RC statistics. Two instances: `RC_PENDING_STATS_ID` (0) for accumulating current day, `RC_ARCHIVE_STATS_ID` (1) for previous day (used by API).

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

---

### rc_direct_delegation_object

**Source:** `rc/rc_objects.hpp:179`

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

---

### rc_expired_delegation_object

**Source:** `rc/rc_objects.hpp:201`

Overflow RC delegations pending removal (when mass removal hits per-block limit).

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

---

### rc_usage_bucket_object (Multiton — 24)

**Source:** `rc/rc_objects.hpp:222`

Fixed set of 24 time buckets for RC resource usage tracking. Each covers `HIVE_RC_BUCKET_TIME_LENGTH` seconds. Sum across all buckets = `rc_pool_object.usage_in_window`.

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

---

### node_property_object (Non-persisted)

**Source:** `node_property_object.hpp`

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
3. **Reward distribution**: `total_reward_fund_hive`, `content_reward_percent`, `vesting_reward_percent`, `proposal_fund_percent`
4. **HBD stability**: `hbd_print_rate`, `hbd_stop_percent`, `hbd_start_percent`, `hbd_interest_rate`
5. **Block production**: `head_block_number`, `time`, `current_witness`, `maximum_block_size`
6. **Witness participation**: `recent_slots_filled` (128-bit), `participation_count`
7. **Account subsidies**: `available_account_subsidies`
8. **DHF timing**: `next_maintenance_time`, `last_budget_time`, `dhf_interval_ledger`
9. **Recurrent transfer limits**: `max_consecutive_recurrent_transfer_failures`, `max_open_recurrent_transfers`, `min_recurrent_transfers_recurrence`

---

## Multi-Index Summary

### Singleton Objects (1 instance)
| Object | Allocator Hint |
|--------|---------------|
| `dynamic_global_property_object` | 2 |
| `feed_history_object` | 2 |
| `hardfork_property_object` | 2 |
| `reward_fund_object` | 2 |
| `rc_resource_param_object` | 2 |
| `rc_pool_object` | 2 |

### Doubleton Objects (2 instances)
| Object | Allocator Hint |
|--------|---------------|
| `witness_schedule_object` | 4 |
| `rc_stats_object` | 4 |

### Fixed-Size Multiton Objects
| Object | Count | Allocator Hint |
|--------|-------|---------------|
| `block_summary_object` | 65536 | default |
| `rc_usage_bucket_object` | 24 | 32 |

### Legacy/Unused Objects
| Object | Notes |
|--------|-------|
| `liquidity_reward_balance_object` | Not used after HF12, allocator hint 1024 |
| `comment_cashout_ex_object` | Empty after HF19 |
| `block_stats_object` | Reserved type ID, never defined |

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

1. **RC mana is embedded in account_object**, not in a separate `rc_account_object`. The `rc_manabar`, `rc_adjustment`, `delegated_rc`, `received_rc`, and `last_max_rc` fields are all directly on the account. This is architecturally significant — RC is deeply coupled with account state.

2. **comment_object stores only a hash, not author+permlink strings.** The `author_and_permlink_hash` is a RIPEMD-160 of `permlink + "@" + to_string(author_id)`. The actual permlink string is stored in `comment_cashout_object` (which is deleted after cashout). This means that for cashed-out comments, the permlink is not available from the core chain state.

3. **comment_cashout_object shares its ID with comment_object.** The relationship is 1:0..1 — each comment_object may have zero or one cashout objects, and they share the same numeric ID. This is possible because the IDs are monotonically assigned to comment_objects and cashout objects reference the same ID space.

4. **Several "REMOVE" comments** mark fields not used by consensus but needed for API:
   - `account_object`: `created`, `block_created`, `last_account_update`, `last_vote_time`, `post_count`, `mined`, `block_last_account_recovery`
   - `comment_vote_object`: `last_update`

5. **block_stats_object is a phantom** — type ID 24 is reserved in the enum but the class is only forward-declared and never defined. No multiindex container exists for it.

6. **account_metadata_object is plugin-level**, not core chain. The metadata plugin stores `json_metadata` and `posting_json_metadata` separately from `account_object`. This means nodes running without the metadata plugin don't track JSON metadata at all.

7. **Delayed voting** uses a vector of `{time, val}` pairs on the account_object. VESTS received through power-up have a 30-day delay before they count toward governance voting power. The `sum_delayed_votes` provides quick access to the total.

8. **Many ID-vs-name inconsistencies**: Some objects use `account_id_type` for references (convert_request, vesting_delegation, recurrent_transfer, RC), while others use `account_name_type` (escrow, savings_withdraw, witness_vote, proposal_vote). Code comments mark several of these with "TODO: can be replaced with account_id_type".

9. **Witness scheduling uses virtual time**: Three `fc::uint128` fields (`virtual_last_update`, `virtual_position`, `virtual_scheduled_time`) implement a virtual time scheduling algorithm that gives witnesses block production time proportional to their votes.

10. **HBD interest is tracked via a time-weighted accumulator**: `hbd_seconds = balance × seconds_held`. Interest is paid at most once per month based on this accumulator pattern.

---

## Code References

| Object | Header | Multiindex |
|--------|--------|------------|
| `account_object` | `detail/state/account_object.hpp` | `detail/state/account_object_multiindex.hpp` |
| `comment_object` | `detail/state/comment_object.hpp` | `detail/state/comment_object_multiindex.hpp` |
| `witness_object` | `detail/state/witness_objects.hpp` | `detail/state/witness_objects_multiindex.hpp` |
| `dynamic_global_property_object` | `detail/state/global_property_object.hpp` | `detail/state/global_property_object_multiindex.hpp` |
| `proposal_object` | `detail/state/dhf_objects.hpp` | `detail/state/dhf_objects_multiindex.hpp` |
| `limit_order_object` | `detail/state/limit_order_object.hpp` | `detail/state/limit_order_object_multiindex.hpp` |
| `convert_request_object` | `detail/state/convert_request_object.hpp` | `detail/state/convert_request_object_multiindex.hpp` |
| `collat. convert_request_object` | `detail/state/collateralized_convert_request_object.hpp` | same pattern |
| `escrow_object` | `detail/state/escrow_object.hpp` | `detail/state/escrow_object_multiindex.hpp` |
| `savings_withdraw_object` | `detail/state/savings_withdraw_object.hpp` | `detail/state/savings_withdraw_object_multiindex.hpp` |
| `recurrent_transfer_object` | `detail/state/recurrent_transfer_object.hpp` | `detail/state/recurrent_transfer_object_multiindex.hpp` |
| RC objects | `rc/rc_objects.hpp` | same file (indices defined inline) |
| `account_metadata_object` | `plugins/metadata/.../metadata_objects.hpp` | same file |

---

## Discrepancies and Potential Issues

1. **Type ID for `block_stats_object` (24) is wasted** — forward-declared but never defined. Should be cleaned up or documented as explicitly reserved.

2. **`account_metadata_object_type` (ID 2) is in the core enum** but the object is defined in a plugin. This means the type ID space couples core chain with plugin objects.

3. **`liquidity_reward_balance_object` still exists with allocator hint 1024** despite being unused since HF12. The allocator hint suggests it once held many objects but now wastes reserved memory.

4. **`comment_cashout_ex_object` index remains after HF19** even though no new objects are created. Both the index structure and any remaining objects consume memory.

5. **Inconsistent use of `account_id_type` vs `account_name_type`** across objects complicates lookups. Converting name-based references to ID-based would save memory but requires hardfork.

6. **`witness_schedule_object` comment says "dubleton (plus one internal)"** with allocator hint 4 — it stores both current and future schedule.

---

## Open Questions

1. **When does `block_stats_object` get its definition?** Is it planned for a future hardfork, or is it permanently abandoned?

2. **Are there plans to migrate remaining `account_name_type` references to `account_id_type`?** The code has TODO comments on several objects (escrow, savings_withdraw).

3. **How much memory do legacy objects consume?** `liquidity_reward_balance_object` (HF12) and `comment_cashout_ex_object` (HF19) are effectively dead but still allocated.

4. **The `manabar` struct stores `last_update_time` as `uint32_t` (Unix seconds).** This will overflow in 2106. Is there a plan for year-2106 compatibility? (Probably not a concern given blockchain timescales.)

5. **The `account_object` has 50+ fields.** Some marked "REMOVE" suggest future cleanup. Is there a planned refactoring to split this into smaller objects (similar to how authorities were separated)?
