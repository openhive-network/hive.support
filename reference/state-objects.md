# Hive State Objects Reference

Source: hive-core release 1.28.8. 39 type IDs (37 core-defined + 1 plugin-defined + 1 dead). State lives in chainbase shared memory, with one exception: since 1.28 paid-out comments are archived to RocksDB by default (ROCKSDB is the default of the `comment-archive` option, which exists only in testnet and mirrornet builds; mainnet builds always use ROCKSDB): from HF19 the chainbase comment index holds only comments whose payout is pending or not yet irreversible, plus, while the node syncs, up to about 10,000 paid-out comments awaiting migration; before HF19 nothing is archived (`database_comment.cpp:471-475`, `external_storage/rocksdb_comment_archive.cpp:104-105`).

---

## Enum Table

| ID | Object | Category | Source File |
|----|--------|----------|-------------|
| 0 | `dynamic_global_property_object` | Singleton | `detail/state/global_property_object.hpp` |
| 1 | `account_object` | Dynamic multiton (one per account) | `detail/state/account_object.hpp` |
| 2 | `account_metadata_object` | Dynamic multiton (plugin-level) | `plugins/metadata/.../metadata_objects.hpp` |
| 3 | `account_authority_object` | Dynamic multiton (one per account) | `detail/state/account_object.hpp:364` |
| 4 | `witness_object` | Dynamic multiton (one per witness) | `detail/state/witness_objects.hpp:69` |
| 5 | `transaction_object` | Ephemeral multiton (recent txs) | `detail/state/transaction_object.hpp` |
| 6 | `block_summary_object` | Fixed multiton (65536 ring buffer) | `detail/state/block_summary_object.hpp` |
| 7 | `witness_schedule_object` | Doubleton (current id 0 + future id 1, since HF26) | `detail/state/witness_objects.hpp:181` |
| 8 | `comment_object` | Dynamic multiton (one per post/comment) | `detail/state/comment_object.hpp` |
| 9 | `comment_vote_object` | Dynamic multiton (one per vote) | `detail/state/comment_object.hpp:372` |
| 10 | `witness_vote_object` | Dynamic multiton (one per witness vote) | `detail/state/witness_objects.hpp:171` |
| 11 | `limit_order_object` | Dynamic multiton (open orders) | `detail/state/limit_order_object.hpp` |
| 12 | `feed_history_object` | Singleton | `detail/state/feed_history_object.hpp` |
| 13 | `convert_request_object` | Dynamic multiton (pending HBD->HIVE) | `detail/state/convert_request_object.hpp` |
| 14 | `collateralized_convert_request_object` | Dynamic multiton (pending HIVE->HBD) | `detail/state/collateralized_convert_request_object.hpp` |
| 15 | `liquidity_reward_balance_object` | Legacy (index cleared at HF12) | `detail/state/liquidity_reward_balance_object.hpp` |
| 16 | `hardfork_property_object` | Singleton | `detail/state/hardfork_property_object.hpp` |
| 17 | `withdraw_vesting_route_object` | Dynamic multiton (powerdown routes) | `detail/state/withdraw_vesting_route_object.hpp` |
| 18 | `owner_authority_history_object` | Dynamic multiton (recovery history) | `detail/state/account_object.hpp:484` |
| 19 | `account_recovery_request_object` | Dynamic multiton (pending recovery) | `detail/state/account_object.hpp:518` |
| 20 | `change_recovery_account_request_object` | Dynamic multiton (pending change) | `detail/state/account_object.hpp:562` |
| 21 | `escrow_object` | Dynamic multiton (active escrows) | `detail/state/escrow_object.hpp` |
| 22 | `savings_withdraw_object` | Dynamic multiton (pending withdrawals) | `detail/state/savings_withdraw_object.hpp` |
| 23 | `decline_voting_rights_request_object` | Dynamic multiton (pending requests) | `detail/state/decline_voting_rights_request_object.hpp` |
| 24 | `block_stats_object` | **DEAD** (Steem-era object removed 2016; slot kept so later IDs don't shift) | `hive_object_types.hpp:115` |
| 25 | `reward_fund_object` | Singleton | `detail/state/reward_fund_object.hpp` |
| 26 | `vesting_delegation_object` | Dynamic multiton (active delegations) | `detail/state/account_object.hpp:421` |
| 27 | `vesting_delegation_expiration_object` | Dynamic multiton (returning delegations) | `detail/state/account_object.hpp:458` |
| 28 | `proposal_object` | Dynamic multiton (DHF proposals) | `detail/state/dhf_objects.hpp` |
| 29 | `proposal_vote_object` | Dynamic multiton (DHF votes) | `detail/state/dhf_objects.hpp:68` |
| 30 | `comment_cashout_object` | Dynamic multiton (pending payout) | `detail/state/comment_object.hpp:103` |
| 31 | `comment_cashout_ex_object` | Legacy (index cleared at HF19) | `detail/state/comment_object.hpp:272` |
| 32 | `recurrent_transfer_object` | Dynamic multiton (scheduled transfers) | `detail/state/recurrent_transfer_object.hpp` |
| 33 | `rc_resource_param_object` | Singleton | `rc/rc_objects.hpp:25` |
| 34 | `rc_pool_object` | Singleton | `rc/rc_objects.hpp:44` |
| 35 | `rc_direct_delegation_object` | Dynamic multiton (RC delegations) | `rc/rc_objects.hpp:182` |
| 36 | `rc_usage_bucket_object` | Fixed multiton (24 time buckets) | `rc/rc_objects.hpp:227` |
| 37 | `rc_stats_object` | Doubleton (pending + archive) | `rc/rc_objects.hpp:130` |
| 38 | `rc_expired_delegation_object` | Dynamic multiton (pending RC undelegation) | `rc/rc_objects.hpp:205` |

---

## Key Object Details

### dynamic_global_property_object

**File**: `detail/state/global_property_object.hpp`
**Category**: Singleton (exactly one instance)

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `head_block_number` | `uint32_t` | Current head block number |
| `head_block_id` | `block_id_type` | Hash of head block |
| `time` | `time_point_sec` | Timestamp of head block |
| `current_witness` | `account_name_type` | Witness who produced head block |
| `current_supply` | `HIVE_asset` | All HIVE in existence, including the HIVE backing VESTS (main HIVE token counter) |
| `current_hbd_supply` | `HBD_asset` | Total HBD in existence |
| `virtual_supply` | `HIVE_asset` | HIVE supply including virtual HBD conversion |
| `total_vesting_fund_hive` | `HIVE_balance` | HIVE backing all VESTS (a balance class since 1.28.8, `HIVE_asset` at 1.28.7) |
| `total_vesting_shares` | `VEST_asset` | Total VESTS in existence |
| `pending_rewarded_vesting_shares` | `VEST_asset` | Unclaimed vest rewards |
| `pending_rewarded_vesting_hive` | `HIVE_asset` | HIVE backing unclaimed vest rewards |
| `hbd_interest_rate` | `uint16_t` | HBD savings interest rate (BPS) |
| `hbd_print_rate` | `uint16_t` | Percent of rewards paid in HBD (BPS) |
| `hbd_stop_percent` | `uint16_t` | HBD market cap % to stop printing |
| `hbd_start_percent` | `uint16_t` | HBD market cap % to resume printing |
| `maximum_block_size` | `uint32_t` | Current max block size (witness median) |
| `content_reward_percent` | `uint16_t` | Content reward share (BPS) |
| `vesting_reward_percent` | `uint16_t` | Vesting reward share (BPS) |
| `proposal_fund_percent` | `uint16_t` | DHF fund share (BPS) |
| `downvote_pool_percent` | `uint16_t` | Downvote pool as % of upvote pool |
| `available_account_subsidies` | `int64_t` | Pool of free account creation tokens |
| `next_maintenance_time` | `time_point_sec` | Next DHF maintenance |
| `last_budget_time` | `time_point_sec` | Last DHF budget calculation |
| `dhf_interval_ledger` | `HBD_asset` | Accumulated HBD for DHF interval |
| `vote_power_reserve_rate` | `uint32_t` | Votes regenerated per day |
| `delegation_return_period` | `uint32_t` | Delegation return cooldown (seconds) |
| `reverse_auction_seconds` | `uint64_t` | Reverse auction window |
| `early_voting_seconds` | `uint64_t` | Early voting window |
| `mid_voting_seconds` | `uint64_t` | Mid voting window |

1.28.8 removed `total_reward_fund_hive` and `total_reward_shares2` from this object (`global_property_object.hpp:400-443`) and from the `database_api` / `condenser_api` dgpo responses. The content reward pool is `reward_fund_object.reward_balance`, which since 1.28.8 also holds the pre-HF17 pool, with the pre-HF17 rshares2 total in `recent_claims` (see reward_fund_object below; Part 05, section dynamic_global_property_object (Singleton)).

**Computed Properties**:
- `get_vesting_share_price()` = `total_vesting_shares / total_vesting_fund_hive` (VEST/HIVE conversion)
- `get_reward_vesting_share_price()` = includes pending rewards in price calculation

**Indices**: Only `by_id` (singleton)

**Tracks**: supply, rewards, HBD stability, block production, witness participation, DHF timing, recurrent transfer limits (these fields only mirror the `HIVE_*` constants that the chain code reads: Part 12, Key Discovery 5)

---

### account_object

**File**: `detail/state/account_object.hpp`
**Category**: Dynamic multiton (one per account)

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `account_name_type` | Account name (3-16 chars, unique key of `by_name`) |
| `memo_key` | `public_key_type` | Memo encryption key |
| `proxy` | `account_id_type` | Governance proxy (0 = none) |
| `recovery_account` | `account_id_type` | Recovery account (0 = top witness) |
| **Balances** | | |
| `hive_balance` | `HIVE_balance` | Liquid HIVE (`balance` at 1.28.7 and in the API account objects) |
| `hbd_balance` | `HBD_balance` | Liquid HBD |
| `savings_hive_balance` | `HIVE_balance` | HIVE in savings (3-day withdrawal; `savings_balance` at 1.28.7 and in the API account objects) |
| `savings_hbd_balance` | `HBD_balance` | HBD in savings (earns interest) |
| `reward_hive_balance` | `HIVE_balance` | Unclaimed HIVE rewards |
| `reward_hbd_balance` | `HBD_balance` | Unclaimed HBD rewards |
| `reward_vesting_balance` | `VEST_balance` | Unclaimed VEST rewards |
| `reward_vesting_hive` | `HIVE_balance` | HIVE counterweight to reward VESTS |
| **Vesting** | | |
| `vesting_shares` | `VEST_balance` | Total VESTS held |
| `delegated_vesting_shares` | `VEST_asset` | VESTS delegated out |
| `received_vesting_shares` | `VEST_asset` | VESTS delegated in |
| `vesting_withdraw_rate` | `VEST_asset` | Weekly power down rate |
| `to_withdraw` | `VEST_asset` | Total VESTS to withdraw in current powerdown |
| `withdrawn` | `VEST_asset` | VESTS already withdrawn |
| `next_vesting_withdrawal` | `time_point_sec` | Next powerdown payment |
| **Manabars** | | |
| `voting_manabar` | `manabar` | Upvote mana `{current_mana, last_update_time}` |
| `downvote_manabar` | `manabar` | Downvote mana |
| `rc_manabar` | `manabar` | Resource credit mana |
| **RC** | | |
| `rc_adjustment` | `share_type` | Extra RC from account creation fee |
| `delegated_rc` | `share_type` | RC delegated out |
| `received_rc` | `share_type` | RC delegated in |
| **Governance** | | |
| `witnesses_voted_for` | `uint16_t` | Number of witnesses voted for (max 30) |
| `governance_vote_expiration_ts` | `time_point_sec` | When governance vote expires |
| `can_vote` | `bool` | Voting enabled (false if declined) |
| `delayed_votes` | `t_vector<delayed_votes_data>` | VESTS pending activation (30-day delay) |
| `sum_delayed_votes` | `ushare_type` | Sum of delayed votes |
| **Social** | | |
| `post_count` | `uint32_t` | Total posts (non-consensus) |
| `last_post` | `time_point_sec` | Last post/comment time |
| `last_root_post` | `time_point_sec` | Last root post time |
| `last_vote_time` | `time_point_sec` | Last vote time (non-consensus) |
| **Other** | | |
| `pending_claimed_accounts` | `share_type` | Claimed but unused account tokens |
| `open_recurrent_transfers` | `uint16_t` | Active recurrent transfers (max 255) |
| `created` | `time_point_sec` | Account creation time (non-consensus) |

**Computed Properties**:
- `get_effective_vesting_shares()` = `vesting_shares - delegated_vesting_shares + received_vesting_shares - next_withdrawal_step`
- `get_maximum_rc()` = `effective_vesting_shares - delegated_rc + rc_adjustment + received_rc`
- `get_governance_vote_power()` = `vesting_shares - sum_delayed_votes + sum(proxied_vsf_votes)`

**Indices**:

| Index | Key | Notes |
|-------|-----|-------|
| `by_name` | `name` | Unique account lookup |
| `by_proxy` | `(proxy, name)` | Find accounts by proxy |
| `by_next_vesting_withdrawal` | `(next_vesting_withdrawal, name)` | Process powerdowns |
| `by_delayed_voting` | `(oldest_delayed_vote_time, id)` | Mature delayed votes |
| `by_governance_vote_expiration_ts` | `(governance_vote_expiration_ts, id)` | Expire governance votes |

**Modified By**: transfer, vote, comment cashout, power up/down, delegation, claim rewards, account create/update, RC delegation

**Note**: RC mana is embedded directly in account_object, not in a separate RC object. Authority keys are in a separate `account_authority_object`. JSON metadata is in plugin-level `account_metadata_object`. Since 1.28.8 the nine fund members are balance classes (`HIVE_balance`, `HBD_balance`, `VEST_balance`: same JSON and binary form as the `*_asset` types, changed only by transfers between balances; Part 01, section tiny_asset and tiny_price) and, with `delegated_vesting_shares` / `received_vesting_shares`, private behind getters; two were renamed (`balance` -> `hive_balance`, `savings_balance` -> `savings_hive_balance`), while the `database_api` and `condenser_api` account objects keep the old names (Part 05, section account_object).

---

### comment_object

**File**: `detail/state/comment_object.hpp`
**Category**: Dynamic multiton (one per post/comment)

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `parent_comment` | `comment_id_type` | Parent comment ID (null = root post) |
| `author_and_permlink_hash` | `fc::ripemd160` | RIPEMD-160 of `permlink@author_id` |
| `depth` | `uint16_t` | Nesting depth (0 = root post) |

**Indices**:

| Index | Key | Notes |
|-------|-----|-------|
| `by_permlink` | `author_and_permlink_hash` | Consensus lookup by author+permlink |

**Note**: Stores only a hash, not raw author+permlink strings. The actual permlink is in `comment_cashout_object` (deleted after cashout). For cashed-out comments, permlink is not available from core chain state. Use `is_root()` to check if root post.

**Archive (1.28)**: with the ROCKSDB archive (the default of the `comment-archive` option, which exists only in testnet and mirrornet builds; mainnet builds always use ROCKSDB), paid-out comments are removed from the chainbase index once their cashout is irreversible (staged as `volatile_comment_object`; from HF19, moved in batches once 10,000 are pending while the node syncs, at every irreversible block once live) and stored in RocksDB as `{comment_id, parent_comment, depth}` keyed by the author+permlink hash. Author+permlink lookups go through `database::find_comment(...)` / `get_comment(...)`, which transparently fall back to the archive (the by-id accessors read chainbase only). `MEMORY` keeps archived comments in a separate hashed SHM index instead; `NONE` keeps the pre-1.28 keep-everything behavior. Changing the option requires replay (Part 05, section Comment Archive and External Storage (RocksDB); Part 13, Key Discoveries 1 and 8).

---

### comment_cashout_object

**File**: `detail/state/comment_object.hpp:103`
**Category**: Dynamic multiton (one per comment with pending payout; deleted after cashout)

Shares `id` with its `comment_object` (1:0..1 relationship).

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `author_id` | `account_id_type` | Comment author |
| `permlink` | `shared_string` | Comment permlink (only source after creation) |
| `net_rshares` | `share_type` | Sum of all vote rshares (up + down) |
| `vote_rshares` | `share_type` | Sum of positive vote rshares only |
| `total_vote_weight` | `uint64_t` | Accumulated vote weight for curation split |
| `max_accepted_payout` | `HBD_asset` | Max payout (default 1,000,000.000 HBD) |
| `net_votes` | `int32_t` | Upvotes minus downvotes (API only) |
| `children` | `uint32_t` | Direct reply count |
| `created` | `time_point_sec` | Creation time |
| `cashout_time` | `time_point_sec` | Scheduled cashout (7 days after creation since HF17) |
| `percent_hbd` | `uint16_t` | Percent of reward in HBD (BPS) |
| `allow_votes` | `bool` | Voting enabled |
| `allow_curation_rewards` | `bool` | Curation rewards enabled |
| `beneficiaries` | `t_vector<stored_beneficiary_route_type>` | Beneficiary list `{account_id, weight}` |

**Indices**:

| Index | Key | Notes |
|-------|-----|-------|
| `by_cashout_time` | `(cashout_time, id)` | Process pending payouts |

**Modified By**: comment, vote, comment_options, cashout processing

---

### witness_object

**File**: `detail/state/witness_objects.hpp:69`
**Category**: Dynamic multiton (one per registered witness)

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `owner` | `account_name_type` | Witness account name |
| `url` | `shared_string` | Witness info URL |
| `signing_key` | `public_key_type` | Block signing key (empty = disabled) |
| `total_missed` | `uint32_t` | Missed blocks count |
| `last_confirmed_block_num` | `uint64_t` | Last confirmed block |
| `votes` | `share_type` | Total governance votes received |
| `schedule` | `witness_schedule_type` | Last schedule type: elected/timeshare/miner/none |
| `running_version` | `version` | Reported hived version |
| `hardfork_version_vote` | `hardfork_version` | Hardfork version vote |
| `hardfork_time_vote` | `time_point_sec` | Hardfork time vote |
| `hbd_exchange_rate` | `price` | HBD/HIVE price feed |
| `last_hbd_exchange_update` | `time_point_sec` | Last price feed update |
| `props` | `chain_properties` | Witness-voted chain properties |
| `available_witness_account_subsidies` | `int64_t` | Free account creation pool |

**chain_properties sub-struct**:

| Field | Type | Description |
|-------|------|-------------|
| `account_creation_fee` | `HIVE_asset` | Minimum account creation fee |
| `maximum_block_size` | `uint32_t` | Voted max block size |
| `hbd_interest_rate` | `uint16_t` | Voted HBD interest rate |
| `account_subsidy_budget` | `int32_t` | Free accounts per block |
| `account_subsidy_decay` | `uint32_t` | Free account decay rate |

**Indices**:

| Index | Key | Ordering | Notes |
|-------|-----|----------|-------|
| `by_name` | `owner` | asc | Unique name lookup |
| `by_vote_name` | `(votes, owner)` | **votes DESC**, name asc | Rank witnesses |
| `by_schedule_time` | `(virtual_scheduled_time, id)` | asc | Virtual time scheduling |
| `by_pow` | `(pow_worker, id)` | asc | POW scheduling |

**Modified By**: witness_update, witness_set_properties, account_witness_vote, feed_publish, block production

---

### witness_schedule_object

**File**: `detail/state/witness_objects.hpp:181`
**Category**: Doubleton — current schedule (id 0, from genesis) + future schedule (id 1, created at HF26)

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `current_shuffled_witnesses` | `fc::array<account_name_type, 21>` | Current round's shuffled witness list |
| `num_scheduled_witnesses` | `uint8_t` | Count of scheduled witnesses |
| `next_shuffle_block_num` | `uint32_t` | Next schedule shuffle block |
| `current_virtual_time` | `fc::uint128` | Virtual time state |
| `median_props` | `chain_properties` | Median of all witness-voted properties |
| `majority_version` | `version` | Majority hived version |
| `max_voted_witnesses` | `uint8_t` | Max voted witness slots |
| `max_runner_witnesses` | `uint8_t` | Max runner-up witness slots |
| `hardfork_required_witnesses` | `uint8_t` | Witnesses needed for hardfork activation |

**Indices**: Only `by_id`

---

### proposal_object

**File**: `detail/state/dhf_objects.hpp`
**Category**: Dynamic multiton (one per DHF proposal)

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `proposal_id` | `uint32_t` | Proposal ID |
| `creator` | `account_name_type` | Proposal creator |
| `receiver` | `account_name_type` | Account receiving funds |
| `start_date` | `time_point_sec` | Funding start date |
| `end_date` | `time_point_sec` | Funding end date |
| `daily_pay` | `HBD_asset` | Requested daily HBD payment |
| `subject` | `shared_string` | Brief title |
| `permlink` | `shared_string` | Link to full description post |
| `total_votes` | `uint64_t` | Recalculated every maintenance cycle |
| `removed` | `bool` | Soft-delete flag |

**Indices**:

| Index | Key | Notes |
|-------|-----|-------|
| `by_proposal_id` | `proposal_id` | Unique lookup |
| `by_start_date` | `(start_date, proposal_id)` | Active proposal range |
| `by_end_date` | `(end_date_with_delay, proposal_id)` | Expiration |
| `by_creator` | `(creator, proposal_id)` | Creator's proposals |
| `by_total_votes` | `(total_votes, proposal_id)` | Rank by support |

**Modified By**: create_proposal, update_proposal, remove_proposal, the DHF maintenance cycle (hourly on mainnet; recalculates `total_votes` before the `proposal_pay` payments, `dhf_processor.cpp:238-286`)

---

### reward_fund_object

**File**: `detail/state/reward_fund_object.hpp`
**Category**: Singleton (one instance named "post"; since 1.28.8 created at genesis, at 1.28.7 at HF17; never removed)

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `reward_fund_name_type` | Fund name (always "post") |
| `reward_balance` | `HIVE_balance` | HIVE available in reward pool (a balance class since 1.28.8, `HIVE_asset` at 1.28.7) |
| `recent_claims` | `uint128_t` | Recent reward claims (denominator for reward calc) |
| `last_update` | `time_point_sec` | Last update time |
| `content_constant` | `uint128_t` | Reward-curve shape constant (`s`/`var1`); used by `quadratic`, `bounded_curation`, `convergent_linear`, `convergent_square_root` — ignored by `linear`/`square_root` |
| `percent_curation_rewards` | `uint16_t` | Curation reward share (currently 50%) |
| `percent_content_rewards` | `uint16_t` | Content reward share |
| `author_reward_curve` | `curve_id` | Author reward curve type |
| `curation_reward_curve` | `curve_id` | Curation reward curve type |

**Indices**: `by_id`, `by_name` (unique)

**Key formula** (HF17+, `util/reward.cpp:7-31`): `payout = reward_balance * evaluate_reward_curve(rshares, author_reward_curve, content_constant) / recent_claims`, with the claim first scaled by the comment's `reward_weight` (below 100% only for root posts created between HF12 and HF17), zeroed if below dust, and capped at the comment's `max_accepted_payout`. The curve is **configurable** (see `author_reward_curve` / `curation_reward_curve` above), not fixed: the fund's author curve is `quadratic` (its default) until HF19, then `linear` (HF19), `convergent_linear` (HF21) and `linear` again (HF25). Since **HF25 the author curve is `linear`**, so `evaluate_reward_curve(rshares, linear) = rshares` and `payout ~ reward_balance * rshares / recent_claims`. From HF17 `recent_claims` is the time-decayed sum of `evaluate_reward_curve(net_rshares, ...)` over all cashing-out comments (HF17 seeds it, HF19 and HF21 re-seed it, outside testnet builds); before HF17 it holds the undecayed running total of rshares2, which 1.28.7 kept in the dgpo's `total_reward_shares2` (Part 05, section reward_fund_object (Singleton)).

---

### feed_history_object

**File**: `detail/state/feed_history_object.hpp`
**Category**: Singleton (updated once per hour from witness feeds)

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `current_median_history` | `HBD_price` | Current median price (used for HBD conversions) |
| `market_median_history` | `HBD_price` | Market median (same unless artificially adjusted) |
| `current_min_history` | `HBD_price` | Min price in window (for collateralized conversions) |
| `current_max_history` | `HBD_price` | Max price in window |
| `price_history` | `t_deque<HBD_price>` | Hourly median prices: the last 84 (3.5 days) since HF16, 168 (a week) before (`database.cpp:2457-2463`; the source comment still says a week) |

**Indices**: Only `by_id` (singleton)

---

## Other Objects (Brief)

| Object | Description |
|--------|-------------|
| `account_authority_object` | Owner/active/posting keys for an account. Separate from account_object for size. |
| `account_metadata_object` | JSON metadata (plugin-level, not core chain). `json_metadata` + `posting_json_metadata`. The metadata plugin is NOT in hived's default plugin set — default nodes store no account JSON metadata. |
| `comment_vote_object` | One per voter/comment pair. Tracks `rshares`, `vote_percent` (-10000 to 10000), `weight`. Removed in bulk when the comment is paid out (or deleted) — the index only holds votes within the 7-day cashout window. |
| `witness_vote_object` | Links accounts to witnesses they voted for. |
| `limit_order_object` | Open HIVE/HBD internal market orders. Indexed by price (DESC) for matching. |
| `convert_request_object` | Pending HBD-to-HIVE conversion (3.5-day delay). |
| `collateralized_convert_request_object` | Pending HIVE-to-HBD conversion with collateral (3.5-day delay). HBD given immediately. |
| `escrow_object` | Three-party escrow (sender, receiver, agent) with ratification deadline. |
| `savings_withdraw_object` | Pending savings withdrawal (3-day delay). |
| `recurrent_transfer_object` | Scheduled recurring transfers with configurable interval and max executions. |
| `vesting_delegation_object` | Active VESTS delegation from one account to another. |
| `vesting_delegation_expiration_object` | VESTS returning after delegation removal (cooldown period). |
| `withdraw_vesting_route_object` | Routes power-down payouts to other accounts (max 10 routes, BPS allocation). |
| `owner_authority_history_object` | Historical owner authority changes (for account recovery window). |
| `account_recovery_request_object` | Pending account recovery requests (one per account). |
| `change_recovery_account_request_object` | Pending recovery account change (30-day delay). |
| `decline_voting_rights_request_object` | Pending request to permanently decline voting (30-day delay). |
| `hardfork_property_object` | Singleton tracking hardfork state, version, and history. |
| `block_summary_object` | Ring buffer of 65536 block hashes for TaPOS validation. Accessed by `block_num & 0xFFFF`. |
| `transaction_object` | Recent transaction hashes for duplicate detection. Removed after expiration. |
| `proposal_vote_object` | DHF proposal votes (one per voter/proposal pair). |
| `comment_cashout_ex_object` | Legacy extended cashout data. Entire index cleared at HF19 (`remove_old_cashouts`); populated only during pre-HF19 replay. |
| `liquidity_reward_balance_object` | Legacy market maker rewards. Index cleared at HF12; populated only during pre-HF12 replay. |
| `block_stats_object` | **Dead type ID 24.** Steem-era object (one block_id per block) removed in 2016 (steemit/steem#675); enum slot kept so later type IDs don't shift. Never defined in Hive. |
| `volatile_comment_object` | Comment-archive staging object (chainbase space ID 21, outside the core enum; exists only with the ROCKSDB archive, the default and the only choice in mainnet builds). Created on cashout from HF19, under undo; moved to RocksDB and removed (with its `comment_object`) once irreversible: from HF19, in batches once 10,000 are pending while the node syncs, at every irreversible block once live. |
| `rc_resource_param_object` | Singleton. Per-resource RC parameters (dynamics + pricing for 5 resource types). |
| `rc_pool_object` | Singleton. Global RC resource pools, usage, and budgets for 5 resources. |
| `rc_stats_object` | Doubleton (pending + archive). Daily RC statistics per operation type. |
| `rc_direct_delegation_object` | Direct RC delegation between accounts. |
| `rc_expired_delegation_object` | Overflow RC undelegations pending removal. |
| `rc_usage_bucket_object` | 24 time buckets for RC resource usage tracking. |

---

## Key Architectural Notes

1. **RC mana is embedded in account_object**, not in a separate RC object. Fields: `rc_manabar`, `rc_adjustment`, `delegated_rc`, `received_rc`.

2. **comment_object stores only a RIPEMD-160 hash** of author+permlink, not the raw strings. The actual permlink lives in `comment_cashout_object`, which is deleted after cashout. Cashed-out comments have no permlink in core chain state.

3. **Paid-out comments are archived out of chainbase by default (1.28)**: the ROCKSDB archive (the default of the `comment-archive` option, which exists only in testnet and mirrornet builds; mainnet builds always use ROCKSDB) moves comments to RocksDB once their cashout is irreversible; `MEMORY` moves them to a separate hashed SHM index; `NONE` keeps the old keep-everything behavior. Author+permlink lookups via `database::get_comment` / `find_comment` transparently consult the archive. Changing the option requires replay.

4. **comment_cashout_object shares its ID** with comment_object (1:0..1 relationship).

5. **comment_vote_objects are short-lived**: removed in bulk when their comment is paid out or deleted, so the index only covers the 7-day cashout window. Together with the comment archive, this is what keeps `shared_memory.bin` bounded.

6. **Account authority keys** are in `account_authority_object`, not `account_object`. JSON metadata is plugin-level (`account_metadata_object`) — and the metadata plugin is not in hived's default plugin set, so default nodes store no JSON metadata.

7. **5 RC resource types**: history_bytes (tx size), new_accounts (account creation), market_bytes (market orders), state_bytes (state storage), execution_time (CPU).

8. **HBD interest** uses a time-weighted accumulator: `hbd_seconds = balance * seconds_held`. Interest paid at most once per month.

9. **Delayed voting**: VESTS from power-up (and VESTS that an auto-vest power-down route sends to another account) count toward governance voting power only after a delay: they are kept in daily buckets that mature 30 days after the bucket opened, so the effective delay is (29, 30] days (Part 14, Key Discoveries 4 and 6).

10. **Witness scheduling** uses virtual time (three `fc::uint128` fields) for the timeshare (runner-up) slot, giving the witnesses outside the top-voted set block production proportional to their votes (Part 06, section Virtual Time Fair Queuing (Timeshare Selection)).
