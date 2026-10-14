# Findings: delayed-voting

Deep-dive into the HF24 delayed (governance) voting subsystem of hive-core, verified
against worktree `1584099c3054a97f02abfb4788b23f02eea98728`
(`workspace/hive-core/1584099c30`). Entry files `util/delayed_voting.{hpp,cpp}` were the
correct entry points; the full picture additionally requires
`util/delayed_voting_processor.hpp` (the collection algebra),
`database_vesting_helpers.hpp` (`create_vesting2` — the keystone that decides which
vesting paths bypass the delay), and `database_vesting.cpp` (power-down interaction).

## Summary

Delayed voting (HF24, mainnet activation 2020-10-14) decouples VESTS ownership from
governance vote power: VESTS obtained via `transfer_to_vesting` are immediately spendable
(RC, comment-vote mana, delegation) but contribute nothing to witness/proposal voting for
~30 days. Each account buffers fresh VESTS in up to 30 daily `{time, val}` buckets
(`account_object::delayed_votes`); an end-of-block processor matures the oldest bucket(s)
once they age past 30 days, emitting `delayed_voting_operation` and injecting the value
into the witness-vote/proxy chain. Power-downs cancel still-immature buckets newest-first
and only charge the matured surplus against live vote power; every other VESTS-creation
path (producer rewards, claimed reward VESTS, pre-HF20 creation fees) grants governance
power immediately via `create_vesting2`.

## Key Discoveries

### 1. The delay applies ONLY to `transfer_to_vesting` (and power-down auto-vest routes)

- **What**: `create_vesting2` (`database_vesting_helpers.hpp:22-35`) is the common vesting
  helper, and at lines 29-30 it calls
  `db.adjust_proxied_witness_votes( to_account, new_vesting.amount )` whenever
  `to_reward_balance == false` — immediate governance power. The HF24
  `transfer_to_vesting` evaluator deliberately bypasses it: it calls
  `adjust_account_vesting_balance` directly with a no-op callback
  (`hive_evaluator_transfer.cpp:313`) and registers a delayed bucket instead
  (`hive_evaluator_transfer.cpp:315-316`). All other callers go through
  `create_vesting`/`create_vesting2` and get instant vote power: producer (witness block)
  rewards (`database.cpp:1787`, `database.cpp:1879`), pre-HF20 account-creation-fee
  vesting (`hive_evaluator_account.cpp:195,256`), PoW rewards
  (`hive_evaluator.cpp:497,600`).
- **Where**: `database_vesting_helpers.hpp:29-30`, `hive_evaluator_transfer.cpp:311-317`
- **Impact**: "30-day delay on new VESTS" is only accurate for power-ups. A witness's
  block pay and any claimed reward VESTS raise governance weight in the same block. This
  is the precise boundary of the HF24 anti-takeover mechanism (the in-code rationale is
  the comment at `hive_evaluator_transfer.cpp:305-310`: immediate voting "is dangerous,
  because malicious accounts would take over whole HIVE network").

### 2. Claimed reward VESTS skip the delay explicitly

- **What**: `claim_reward_balance_evaluator` moves `reward_vesting_balance` into
  `vesting_shares` and then calls
  `_db.adjust_proxied_witness_votes( acnt, op_reward_vests.amount )` directly — no
  `delayed_voting` involvement. (When the reward was earned, `create_vesting2` was called
  with `to_reward_balance = true` — post-HF17 — which skips the witness-vote adjustment at
  that earlier moment, so the claim is when power activates.)
- **Where**: `hive_evaluator_transfer.cpp:658,674`; earning side
  `database_comment.cpp:176,268,295`
- **Impact**: Confirms and pins down Part 07's claim (line 329). Author/curation rewards
  are treated as "already aged" — only externally injected capital is quarantined.

### 3. Power-down consumes immature votes newest-first; only the surplus hits live power

- **What**: During `process_vesting_withdrawals`, the withdrawing account contributes a
  negative entry (`add_votes(items, true /*withdraw_executor*/, -to_withdraw, from)`,
  `database_vesting.cpp:252-253`). `update_votes` then erases `abs_val` from the
  account's buckets — `delayed_voting_processor::erase` pops from the **back** (newest
  buckets first, `delayed_voting_processor.hpp:108-122`) — and only if the withdrawal
  exceeds `sum_delayed_votes` does the leftover (`res = abs_val - sum_delayed_votes`)
  get applied as `adjust_proxied_witness_votes( from_account, -leftover )`
  (`delayed_voting.cpp:64-73`, `database_vesting.cpp:288-291`).
- **Where**: `util/delayed_voting.cpp:44-77`, `database_vesting.cpp:248-297`
- **Impact**: Powering down freshly vested HIVE costs you immature (never-counted) votes
  first; mature vote power is reduced only by the excess. Erase-from-back means the
  oldest, closest-to-maturity buckets survive longest — the most favorable ordering for
  the account. Confirmed by unit test `delayed_voting_processor_02`
  (`tests/unit/tests/delayed_voting_tests.cpp:1844-1891`).

### 4. Auto-vest withdraw routes to other accounts get a fresh 30-day delay

- **What**: When a power-down routes VESTS to another account with `auto_vest`, the
  recipient's amount is collected via
  `add_votes(items, to_self, routed_vests, to_account)` (`database_vesting.cpp:210-211`)
  and, in `update_votes`, positive entries call `add_delayed_value(account, now, val)`
  (`delayed_voting.cpp:61-62`) — creating a new bucket timestamped *now*. A route back to
  self merges (same set key) with the executor's negative entry and nets out ≤ 0, so
  self-routed VESTS keep their original bucket ages.
- **Where**: `database_vesting.cpp:206-216`, `util/delayed_voting.cpp:26-42,61-62`
- **Impact**: You cannot launder the delay away by power-down-routing VESTS to another
  account — the clock restarts for the recipient. Pre-HF24 the same code path credited
  the recipient instantly (`database_vesting.cpp:215`).

### 5. The `by_delayed_voting` index uses a `time_point_sec::maximum()` sentinel and the `has_delayed_votes()` guard is load-bearing

- **What**: `get_oldest_delayed_vote_time()` returns `time_point_sec::maximum()` for
  accounts with no buckets (`account_object.hpp:292-299`), pushing them to the end of the
  `by_delayed_voting` index (`detail/state/account_object_multiindex.hpp:32-37`). The
  maturation loop condition checks `current->has_delayed_votes()` *before* evaluating
  `head_time >= oldest + HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS`
  (`delayed_voting.cpp:87-89`); without that short-circuit, `maximum() + 30 days` would
  wrap `fc::time_point_sec`'s 32-bit seconds counter and make the comparison true,
  leading to `delayed_votes.begin()` on an empty vector.
- **Where**: `util/delayed_voting.cpp:87-91`, `account_object.hpp:292-299`
- **Impact**: Explains why the seemingly redundant `has_delayed_votes()` test exists in
  the loop condition. Anyone refactoring the loop must preserve it.

### 6. Bucket granularity is a rolling 1-day window, so the effective delay is (29, 30] days

- **What**: `delayed_voting_processor::add` merges a contribution into the back bucket if
  `head_time < back.time + HIVE_DELAYED_VOTING_INTERVAL_SECONDS`, else opens a new bucket
  stamped `head_time` (`delayed_voting_processor.hpp:65-72`). Buckets are anchored at the
  first contribution after the previous bucket closed — not at calendar-day boundaries.
  Maturation fires when `head_time >= bucket.time + 30 days`, checked every block (3 s
  cadence). A contribution merged at the end of a bucket's 1-day window therefore waits
  just over 29 days.
- **Where**: `delayed_voting_processor.hpp:50-72`, `delayed_voting.cpp:87-89`,
  `config.hpp:182-183`
- **Impact**: API consumers and tests must not assume "exactly 30 days from power-up";
  the guarantee is per-bucket, with up to ~1 day of forward credit for late merges into
  an existing bucket. Verified by `delayed_voting_processor_01` (merge at interval−3 s
  stays in bucket; merge at exactly +interval opens a new one;
  `delayed_voting_tests.cpp:1920-1931`).

### 7. Latent inconsistency: `clear_account` subtracts full `vesting_shares` from witness votes, ignoring `sum_delayed_votes`

- **What**: `clear_account` (HF23 Steem-fork seizure machinery) calls
  `adjust_proxied_witness_votes( account, -account.get_vesting().amount )`
  (`database.cpp:1545`) — but if the account had pending delayed votes, only
  `vesting_shares − sum_delayed_votes` ever entered the witness-vote chain, so this would
  over-subtract by `sum_delayed_votes`. The function *does* clear `delayed_votes` under a
  `has_hardfork( HIVE_HARDFORK_1_24 )` guard a few lines later (`database.cpp:1560-1564`),
  showing partial HF24 adaptation. Today `clear_account` is reachable only from HF23
  processing (`database_hardfork.cpp:456` via `clear_accounts`), where delayed voting did
  not yet exist (`sum_delayed_votes == 0` for every account), so the bug cannot fire on
  mainnet history — it is latent, not active.
- **Where**: `database.cpp:1545` vs `database.cpp:1560-1564`;
  caller `database_hardfork.cpp:451-456`
- **Impact**: If `clear_account` were ever reused for a future seizure/cleanup after
  HF24, accounts with immature buckets would corrupt witness-vote accounting (the correct
  delta is `-get_direct_governance_vote_power()` plus proxy handling, as
  `nullify_proxied_witness_votes` does at `database.cpp:1131-1138`). Flagged for contrib.

### 8. The 30-bucket cap is a steady-state guarantee; 31 buckets can exist transiently inside a block

- **What**: The comment in `run()` (`delayed_voting.cpp:101-109`) explains the design
  target of ≤ 30 entries (30 d / 1 d). A 31st bucket can only be created by a transaction
  whose `head_time ≥ oldest.time + 30 d` (bucket times are ≥ 1 day apart, so entry *i*
  satisfies `time[i] ≥ time[0] + i·1d`); but transactions execute before end-of-block
  processing, and that same condition makes `process_delayed_voting` pop the oldest
  bucket at the end of the very same block. So after every block, size ≤ 30 holds.
- **Where**: `delayed_voting_processor.hpp:65-72`, `delayed_voting.cpp:87-117`,
  ordering `database.cpp:2303` (transactions) vs `database.cpp:2351` (maturation)
- **Impact**: Iteration/memory bounds hold per-block, but mid-block observers (custom
  plugins reading state between transactions) can see 31 entries.

## Data Structures and State

### Per-account state (`detail/state/account_object.hpp`)

| Field | Type | Notes |
|---|---|---|
| `delayed_votes` | `t_vector<delayed_votes_data>` | `account_object.hpp:261-266`; `t_vector` = `boost::interprocess::vector` in shared memory (`chainbase/allocator_helpers.hpp:91`); needs allocator at load: `CHAINBASE_UNPACK_CONSTRUCTOR(account_object, (delayed_votes))` (`account_object.hpp:336`); counted in `get_dynamic_alloc` (`account_object.hpp:329-334`) |
| `sum_delayed_votes` | `ushare_type` (= `fc::safe<uint64_t>`, `protocol/types.hpp:77`) | cached Σ of bucket vals (`account_object.hpp:222`); in-code TODO says "should be changed to VEST_asset" |

`delayed_votes_data` is `{ time_point_sec time; ushare_type val; }` with `operator==`,
reflected `(time)(val)` (`delayed_voting_processor.hpp:18-27,130-132`). Bucket `time` is
the **creation** head-block time of the bucket (start of its 1-day fill window), not its
maturation time.

### Derived vote-power accessors (`account_object.hpp:301-322`)

- `get_direct_governance_vote_power() = vesting_shares − sum_delayed_votes` with an
  embedded `FC_ASSERT( sum_delayed_votes ≤ vesting_shares )` (`account_object.hpp:304-309`).
- `get_governance_vote_power() = direct + Σ proxied_vsf_votes` (`account_object.hpp:313-317`)
  — used by witness vote/unvote (`hive_evaluator.cpp:290-317`), DHF proposal tallying
  (`util/dhf_processor.cpp:102`), and witness-vote retally (`database_witness.cpp:140`).
- Proxy assignment transfers only the direct power: `delta[0] =
  get_direct_governance_vote_power()` (`hive_evaluator.cpp:248`), so immature VESTS never
  flow into a proxy; when they mature later, `run()` routes them through the proxy chain
  automatically (`adjust_proxied_witness_votes`, `delayed_voting.cpp:99`).

### Index (`detail/state/account_object_multiindex.hpp:32-37`)

`by_delayed_voting` — `ordered_unique` composite key
`(get_oldest_delayed_vote_time(), account_id)`. Accounts without buckets key at
`time_point_sec::maximum()` and sort last. Every bucket mutation through `db.modify`
re-keys the account. The whole-account-object index is the design the in-code TODO at
`account_object.hpp:266` second-guesses ("maybe separate index would be better").

### Helper structures for batch updates (`util/delayed_voting.hpp:11-33`)

`votes_update_data { bool withdraw_executor; mutable share_type val; const
account_object* account; }` collected in a `std::set` keyed **only** by `account->get_id()`
(`votes_update_data_less`, `delayed_voting.hpp:19-26`; null-pointer guarded by FC_ASSERT
with `object_is_null` message). `val` is `mutable` and *signed* so repeated `add_votes`
calls merge deposits/withdrawals for the same account in place through the const set
iterator (`delayed_voting.cpp:33-41`). `opt_votes_update_data_items` is
`fc::optional<set>` — an unset optional makes every `add_votes`/`update_votes` call a
no-op, which is how the pre-HF24 code path is expressed (`delayed_voting.cpp:28,46`).

## The Bucket Collection Algebra (`delayed_voting_processor.hpp`)

Three static template functions maintain the parallel `(items, sum)` pair:

- **`add(items, sum, head_time, val)`** (`:31-73`): no-op for `val == 0`; first entry
  just appended. Otherwise asserts `head_time ≥ back.time` (`incorrect_head_time`,
  `:61`) — bucket times are monotonic; then either merges into the back bucket
  (`head_time < back.time + 1 day`) or appends a new `{head_time, val}` bucket. The
  doc-comment example (`:34-49`) showing per-calendar-date grouping is illustrative only —
  real windows are anchored at bucket creation time (see Key Discovery 6).
- **`erase_front(items, sum)`** (`:75-89`): pops the oldest bucket, asserting
  `sum ≥ front.val` (`incorrect_sum_greater_equal`); on an empty collection asserts
  `sum == 0` (`incorrect_sum_equal`). Used only by maturation.
- **`erase(items, sum, count)`** (`:91-124`): removes `count` from the **newest** buckets
  backward (`items.back()` / `pop_back`), splitting the last partially-consumed bucket
  (`obj.val -= count`). Asserts `count ≤ sum` (`incorrect_erased_votes`). `count == sum`
  clears everything. Used only by power-down cancellation.

All quantities are `ushare_type` (`fc::safe<uint64_t>`) — arithmetic over/underflow would
throw even where the explicit FC_ASSERTs were bypassed.

The error strings live in `delayed_voting_messages` (`delayed_voting_processor.hpp:7-16`);
all but `incorrect_head_time` are prefixed "unexpected error" — they are internal
consistency checks, not user-facing validation. Any of them firing during block
application would reject the block / halt replay.

## Lifecycle

### Recording (transaction time)

`transfer_to_vesting_evaluator::do_apply` (HF24 branch, `hive_evaluator_transfer.cpp:311-317`):

1. `adjust_account_vesting_balance(to_account, amount, false, no-op)` — VESTS credited
   immediately; mana bar and RC updated; global `total_vesting_shares` bumped
   (`database.cpp:995-1041`). **No** witness-vote adjustment (this is the create_vesting2
   bypass).
2. `delayed_voting::add_delayed_value(to_account, head_block_time, amount_vested)` →
   `db.modify` + `processor::add` (`delayed_voting.cpp:7-13`).
3. `transfer_to_vesting_completed_operation` is emitted unconditionally — the in-code
   comment stresses the VESTS balance changed now, independent of the delayed governance
   activation (`hive_evaluator_transfer.cpp:323-324`; vop doc
   `hive_virtual_operations.hpp:498-509` cross-references `delayed_voting_operation`).

### Maturation (end-of-block)

`database::process_delayed_voting(note)` (`database.cpp:1654-1661`) — gated on
`has_hardfork( HIVE_HARDFORK_1_24 )` — constructs a `delayed_voting` and calls
`run( block_timestamp )` (`delayed_voting.cpp:79-120`):

```
while begin-account has buckets AND head_time ≥ oldest.time + 30 days:
    val = oldest bucket value
    emit delayed_voting_operation( account, val )          // :95-97
    adjust_proxied_witness_votes( account, val )           // :99
    modify: processor::erase_front( buckets, sum )         // :110-113
    re-fetch idx.begin()                                   // :115 (modify re-keyed the account)
```

One bucket per iteration, one vop per bucket; an account with several matured buckets is
revisited because erasing the front re-keys it (usually still at `begin()`). The injected
value follows the proxy chain exactly like any live vote-power delta
(`database.cpp:1108-1129`): with a proxy set it lands in the proxy's
`proxied_vsf_votes[0]`; without one, `adjust_witness_votes` spreads it over all witnesses
the account currently votes for. For an account that declined voting rights the call is a
harmless no-op (no proxy, no witness-vote records — `database_dhf.cpp:225-237` cleared
them), and its remaining buckets simply drain over the following days.

Maturation is wrapped in benchmark-dumper instrumentation labeled
`"hive::protocol::transfer_to_vesting_operation"` (`delayed_voting.cpp:84-86,118-119`) —
the label names the originating operation, not a real evaluator run.

### Cancellation (power-down) — the `withdraw_executor` protocol

`process_vesting_withdrawals` (`database_vesting.cpp:111-303`) builds one batch per
withdrawing account per weekly installment:

1. HF24 setup: `optional<delayed_voting> dv` + an engaged `opt_votes_update_data_items`
   (`:148-155`); pre-HF24 both stay unset and all calls degrade to no-ops.
2. **Routes** (auto-vest pass first): each routed deposit > 0 adds
   `add_votes(items, to_self, +routed_vests, to_account)` (`:206-216`); `to_self` is true
   when the route loops back to the withdrawer (`:173`). Pre-HF24 branch instead credits
   the recipient instantly (`:215`).
3. **Executor**: `add_votes(items, true, −to_withdraw, from_account)` (`:248-254`).
4. **Resolution**: `update_votes(items, now)` (`delayed_voting.cpp:44-77`) walks the set:
   - Sign/role invariant per entry: `(!withdraw_executor && val > 0) || (withdraw_executor
     && val ≤ 0)` (`:53-56`, `incorrect_votes_update`). Merging in `add_votes` asserts the
     flag never flips for a given account (`:39`, `incorrect_withdraw_data`).
   - Positive entries (route recipients): `add_delayed_value(account, now, val)` — fresh
     30-day bucket (Key Discovery 4).
   - The single possible negative entry (the executor; a self-route merges into it and
     nets `routed − to_withdraw ≤ 0`): erase `min(abs_val, sum_delayed)` from buckets;
     `res = abs_val − sum_delayed` if the withdrawal exceeds the buffer (`:63-73`).
   - Returns `res` as `fc::optional<ushare_type>` (engaged iff items engaged).
5. Caller applies the matured surplus: `adjust_proxied_witness_votes(from, −leftover)`
   (`database_vesting.cpp:284-292`); pre-HF24 it subtracted the whole `to_withdraw`
   (`:293-297`).

A 100 %-auto-vest-to-self power-down therefore nets `val == 0`, which `update_votes`
skips (`:58-59`) — buckets, ages, and live power all stay untouched, correctly modeling
that nothing actually left the account.

Note `update_votes` *assigns* (`res = …`) rather than accumulates; this is sound only
because the set can contain at most one negative entry (the executor — route targets are
distinct accounts with positive values, and a self-route shares the executor's entry).

## Per-Block Processing Order (`database.cpp:2336-2354`)

```
clear_null_account_balance();        // 2333 — zeroes null's buckets outright (1219-1224)
consolidate_treasury_balance();      // 2334 — zeroes old-treasury buckets (1335-1340)
...
process_vesting_withdrawals();       // 2338 — bucket cancellation + route re-delays
...
process_decline_voting_rights();     // 2346
process_proposals( note );           // 2347 — DHF tally: delayed votes excluded
process_delayed_voting( note );      // 2348 — maturation
remove_expired_governance_votes();   // 2352
```

Two ordering consequences: (a) on a block where a weekly power-down installment and a
maturation coincide, cancellation sees the pre-maturation buckets — but since `erase`
takes newest-first, the about-to-mature oldest bucket is consumed last; (b) a DHF
proposal tally in the same block uses pre-maturation power (maturation runs one step
later).

## What Delayed Votes Do and Don't Affect

| Mechanism | Uses delayed-vote-reduced power? | Where |
|---|---|---|
| Witness vote add/remove | Yes — `get_governance_vote_power()` | `hive_evaluator.cpp:290-317` |
| Proxy set/clear delta | Yes — `get_direct_governance_vote_power()` | `hive_evaluator.cpp:246-251` |
| DHF proposal tally | Yes — `get_governance_vote_power()` | `util/dhf_processor.cpp:100-104` |
| Decline-voting-rights nullify | Yes — `nullify_proxied_witness_votes` uses direct power | `database.cpp:1131-1138`, `database_dhf.cpp:225` |
| Comment voting mana | **No** — manabars track raw/effective VESTS | `database.cpp:1012-1020` (mana grows at vest time) |
| RC max mana | **No** — `get_maximum_rc` (`account_object.hpp:115-121`) builds on `get_effective_vesting_shares`, which never subtracts `sum_delayed_votes` | `account_object.hpp:102-108` |
| Delegation capacity | **No** — same `get_effective_vesting_shares` basis | `account_object.hpp:102-108`, `hive_evaluator_transfer.cpp:677+` |
| Power-down eligibility | **No** — checks `vesting − delegated` | `hive_evaluator_transfer.cpp:342-343` |

VESTS-creation paths vs. the delay:

| Path | Governance power | Where |
|---|---|---|
| `transfer_to_vesting` (HF24+) | Delayed ~30 d | `hive_evaluator_transfer.cpp:311-317` |
| `transfer_to_vesting` (pre-HF24) | Immediate | `hive_evaluator_transfer.cpp:320` |
| Power-down auto-vest route → other account | Re-delayed 30 d (HF24+) | `database_vesting.cpp:210-211` + `delayed_voting.cpp:61-62` |
| Power-down auto-vest route → self | Buckets untouched (nets vs. withdrawal) | `database_vesting.cpp:173,210` + `delayed_voting.cpp:58-59` |
| Producer (witness) reward | Immediate | `database.cpp:1786-1793,1878-1886` via `database_vesting_helpers.hpp:29-30` |
| `claim_reward_balance` VESTS | Immediate at claim | `hive_evaluator_transfer.cpp:674` |
| Account-creation fee vesting (pre-HF20) | Immediate | `hive_evaluator_account.cpp:190-195` |
| PoW mining rewards (legacy) | Immediate | `hive_evaluator.cpp:497,600` |

## Invariants

1. **Per-account cache coherence**: `sum_delayed_votes == Σ buckets[i].val` — asserted in
   `validate_invariants` (`database.cpp:3461-3464`).
2. **Bound**: `sum_delayed_votes ≤ vesting_shares` — asserted both in
   `get_direct_governance_vote_power` (`account_object.hpp:304-307`) and in
   `validate_invariants` (`database.cpp:3465`). Holds because only vested amounts create
   buckets and every vesting decrease cancels buckets first.
3. **Global conservation**: `gpo.total_vesting_shares == total_vsf_votes +
   total_delayed_votes`, where `total_vsf_votes` is the recomputed per-account governance
   power (proxied accounts counted via their top-level proxy slot)
   (`database.cpp:3444-3487`). I.e., every VEST is either active governance weight or
   sitting in someone's buckets.
4. **Bucket times strictly increase, adjacent gaps ≥ 1 day** — by construction in
   `processor::add` (`delayed_voting_processor.hpp:61-72`).
5. **≤ 30 buckets after end-of-block processing** (transiently 31 mid-block; Key
   Discovery 8).
6. **At most one `withdraw_executor` entry per update batch**, and it is the withdrawing
   account (`add_votes` merge assert `delayed_voting.cpp:39`; sign invariant `:53-56`).

## Hardfork-Conditional Behavior

| Guard | Effect | Where |
|---|---|---|
| `HIVE_HARDFORK_1_24` | enables `process_delayed_voting` | `database.cpp:1656` |
| `HIVE_HARDFORK_1_24` | transfer_to_vesting buffers instead of instant power | `hive_evaluator_transfer.cpp:311` |
| `HIVE_HARDFORK_1_24` | power-down uses batch protocol (4 sites: setup / route / executor / resolve) | `database_vesting.cpp:151,206,248,284` |
| `HIVE_HARDFORK_1_24` | `clear_account` clears buckets | `database.cpp:1560-1564` |
| `HIVE_HARDFORK_1_24_TREASURY_RENAME` (≡ HF24) | old-treasury consolidation liquifies VESTS and zeroes buckets (comment: moving vests in vested form "would complicate delayed_votes part") | `database.cpp:1267-1341` |
| HF24 activation block itself | only `restore_accounts` + `set_chain_id` — **no retroactive bucket initialization**; all pre-HF24 VESTS started fully mature | `database_hardfork.cpp:471-480` |
| `HIVE_HARDFORK_1_28_FIX_POWER_DOWN` / `_FIX_CANCEL_POWER_DOWN` | adjacent power-down fixes in the same loop (last-installment rounding; cancel semantics) — they alter *when/how much* is withdrawn, feeding the delayed-voting batch, but not the batch logic itself | `database_vesting.cpp:128`, `hive_evaluator_transfer.cpp:349`, `1_28.hf:15,17` |

Constants: mainnet `HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS = 60*60*24*30` (30 days),
`HIVE_DELAYED_VOTING_INTERVAL_SECONDS = 60*60*24` (1 day) (`config.hpp:182-183`); testnet
builds route both through `configuration_data` so functional tests can shrink them
(`config.hpp:101-102`), keeping the 30-entry shape ("similary to mainnet" comment).

HF24 anchors: `HIVE_HARDFORK_1_24_TIME = 1601992800` (2020-10-06 14:00 UTC, earliest
allowed) and `HIVE_HARDFORK_1_24_ACTUAL_TIME = 1602703884` (2020-10-14 19:31:24 UTC,
block where it took effect on mainnet) (`1_24.hf:22,27`).

## Account Clearing Paths

- **`clear_null_account_balance`** (`database.cpp:1206-1227`): burning `null`'s VESTS
  zeroes `sum_delayed_votes`/`delayed_votes` directly (no witness-vote adjustment —
  `null` cannot vote). Unguarded by HF24 (clearing empty vectors is harmless pre-HF24).
- **`consolidate_treasury_balance`** (`database.cpp:1322-1341`): old treasury
  (`steem.dao`) VESTS are liquified to HIVE on the new treasury and buckets zeroed.
  Notably, post-HF24 vesting *to* `steem.dao` is no longer blocked by the treasury assert
  (it ceased being "the treasury"), so it can transiently hold buckets that this
  consolidation (running every block) wipes.
- **`clear_account`** (`database.cpp:1474-1575`): HF23 seizure path — see Key Discovery 7
  for the latent `sum_delayed_votes` accounting hole at `:1545`.

## API Exposure

- `database_api.find_accounts` / `list_accounts` take `delayed_votes_active` (default
  `true`, `database_api_args.hpp:186,198`); `api_account_object` fills its
  `fc::optional<vector<delayed_votes_data>> delayed_votes` only when the flag is set
  (`database_api_objects.hpp:365,729`; constructor
  `database_api_objects_constructors.cpp:200,273-274`; call sites
  `database_api_accounts.cpp:190,213,229,250`). With the flag false the field is omitted
  from JSON entirely; `sum_delayed_votes` itself is **not** exposed as a separate field —
  clients must sum the array.
- `condenser_api.get_accounts` / `lookup_account_names` accept an optional second boolean
  positional arg with the same meaning (`condenser_api.cpp:363-377,405-418`;
  `condenser_api.hpp:158-159,243`).
- Virtual op `delayed_voting_operation { voter, votes:ushare_type }` — op #70,
  `last_regular + 21` (`operations.hpp:100`; definition
  `hive_virtual_operations.hpp:381-396`, reflected `:845`); impacted account = voter
  (`forward_impacted.cpp:502-507`). One vop per matured bucket, not per account-day with
  zero activity.

## Error Paths

| Message constant | Thrown from | Trigger |
|---|---|---|
| `incorrect_head_time` | `processor::add` (`:61`) | new contribution older than back bucket (monotonicity breach) |
| `incorrect_sum_greater_equal` | `processor::erase_front` (`:82`) | cached sum < front bucket value |
| `incorrect_sum_equal` | `processor::erase_front` (`:88`) | empty buckets but nonzero cached sum |
| `incorrect_erased_votes` | `processor::erase` (`:97`) | cancel amount exceeds cached sum |
| `object_is_null` | `votes_update_data_less` (`delayed_voting.hpp:23`) | null account pointer in batch set |
| `incorrect_votes_update` | `update_votes` (`delayed_voting.cpp:53-56`) | sign/role invariant violated |
| `incorrect_withdraw_data` | `add_votes` (`delayed_voting.cpp:39`) | same account merged with flipped executor flag |

All are `FC_ASSERT`s on the block-application path — corruption tripwires, not
recoverable validation errors. Additional belt-and-braces asserts guard the power-down
batch plumbing (`database_vesting.cpp:208,250,286,289` — note `:250` and `:286` use the
buggy-but-harmless `FC_ASSERT( dv.valid() && "msg" )` idiom where the string is part of
the condition, and `:289` asserts the optional result is engaged).

## Test Coverage (`tests/unit/tests/delayed_voting_tests.cpp`)

Two fixtures (`delayed_voting_proposal_tests`, `delayed_voting_tests` on
`delayed_vote_database_fixture`), 24 cases: processor-level algebra
(`delayed_voting_processor_01..03` — merge windows, erase-from-back, error paths,
`:1781-2024`), evaluator/maturation scenarios (`delayed_voting_01/04/05/06`,
`delayed_voting_basic_01..06`, `delayed_voting_many_vesting_01`), proxy interaction
(`delayed_voting_proxy_01/02`), DHF proposals (`delayed_proposal_test_01/02`), decline
voting rights (`decline_voting_rights_01..04`), and integration (`small_common_test_01`,
`scenario_01`).

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| `delayed_voting` class | `libraries/chain/include/hive/chain/util/delayed_voting.hpp` | 28-50 | facade: add/erase/batch/run |
| `votes_update_data` (+less) | `libraries/chain/include/hive/chain/util/delayed_voting.hpp` | 11-26 | power-down batch entry, keyed by account id |
| `add_delayed_value` | `libraries/chain/util/delayed_voting.cpp` | 7-13 | create/merge bucket |
| `erase_delayed_value` | `libraries/chain/util/delayed_voting.cpp` | 15-24 | cancel from newest buckets |
| `add_votes` | `libraries/chain/util/delayed_voting.cpp` | 26-42 | merge batch entry, executor-flag assert |
| `update_votes` | `libraries/chain/util/delayed_voting.cpp` | 44-77 | resolve batch; leftover rule |
| `run` (maturation) | `libraries/chain/util/delayed_voting.cpp` | 79-120 | end-of-block bucket maturation |
| `delayed_votes_data` | `libraries/chain/include/hive/chain/util/delayed_voting_processor.hpp` | 18-27 | bucket `{time,val}` |
| `processor::add/erase_front/erase` | `libraries/chain/include/hive/chain/util/delayed_voting_processor.hpp` | 31-124 | collection algebra |
| error messages | `libraries/chain/include/hive/chain/util/delayed_voting_processor.hpp` | 7-16 | consistency-tripwire strings |
| `delayed_votes`, `sum_delayed_votes` | `libraries/chain/include/hive/chain/detail/state/account_object.hpp` | 222, 261-266 | per-account state |
| `has_delayed_votes`, `get_oldest_delayed_vote_time` | `libraries/chain/include/hive/chain/detail/state/account_object.hpp` | 290-299 | index key + maximum() sentinel |
| `get_direct_governance_vote_power` | `libraries/chain/include/hive/chain/detail/state/account_object.hpp` | 301-310 | vesting − delayed (asserted bound) |
| `by_delayed_voting` index | `libraries/chain/include/hive/chain/detail/state/account_object_multiindex.hpp` | 32-37 | (oldest_time, id) ordering |
| constants (mainnet) | `libraries/protocol/include/hive/protocol/config.hpp` | 182-183 | 30 d total / 1 d interval |
| constants (testnet-configurable) | `libraries/protocol/include/hive/protocol/config.hpp` | 101-102 | via `configuration_data` |
| `transfer_to_vesting` HF24 branch | `libraries/chain/hive_evaluator_transfer.cpp` | 311-317 | the only delayed entry path |
| `claim_reward_balance` bypass | `libraries/chain/hive_evaluator_transfer.cpp` | 674 | immediate power on claim |
| `create_vesting2` | `libraries/chain/database_vesting_helpers.hpp` | 22-35 | immediate-power helper (line 29-30) |
| power-down batch | `libraries/chain/database_vesting.cpp` | 148-155, 206-216, 248-254, 284-297 | routes, executor, resolution, leftover |
| `process_delayed_voting` | `libraries/chain/database.cpp` | 1654-1661 | HF24 gate |
| block-processing order | `libraries/chain/database.cpp` | 2333-2351 | withdrawals before maturation |
| `adjust_proxied_witness_votes` | `libraries/chain/database.cpp` | 1108-1129 | delta propagation (proxy chain → witnesses) |
| `clear_account` delayed handling | `libraries/chain/database.cpp` | 1545, 1560-1564 | latent over-subtraction (Discovery 7) |
| null/treasury clearing | `libraries/chain/database.cpp` | 1219-1224, 1335-1340 | bucket zeroing |
| invariants | `libraries/chain/database.cpp` | 3441-3484 | sum coherence, bound, global conservation |
| `delayed_voting_operation` | `libraries/protocol/include/hive/protocol/hive_virtual_operations.hpp` | 381-396 | vop #70 |
| op position | `libraries/protocol/include/hive/protocol/operations.hpp` | 100 | `last_regular + 21` |
| impacted accounts | `libraries/protocol/forward_impacted.cpp` | 502-507 | voter |
| API field + flag | `libraries/plugins/apis/database_api/...{database_api_objects.hpp, database_api_args.hpp, database_api_objects_constructors.cpp}` | 365 / 186,198 / 273-274 | optional `delayed_votes` in account objects |
| condenser positional flag | `libraries/plugins/apis/condenser_api/condenser_api.cpp` | 363-377, 405-418 | get_accounts / lookup_account_names |
| HF24 time anchors | `libraries/protocol/hardfork.d/1_24.hf` | 22, 27 | planned vs actual activation |
| HF23/HF24 account actions | `libraries/chain/database_hardfork.cpp` | 451-480 | clear (HF23) / restore (HF24) |
| unit tests | `tests/unit/tests/delayed_voting_tests.cpp` | 85-2397+ | 24 cases incl. processor algebra |

## Cross-references to existing parts

- **Part 04 (chain-evaluators) §2.14, §2.15-adjacent, finding 15**: this zoom **deepens**
  it substantially — adds the `create_vesting2` line-29 mechanism that explains *why*
  reward/producer VESTS bypass the delay (Part 04 noted the claim-reward bypass as a fact;
  the producer-reward path was not covered), the `withdraw_executor` batch protocol and
  its single-negative-entry constraint, route-to-self netting, erase-from-back ordering,
  the (29, 30]-day effective-delay window, the `maximum()` sentinel guard, and the
  transient-31-bucket bound. No contradictions found — Part 04's statements (30-bucket
  cap, leftover rule, one vop per bucket, HF24 gate at `database.cpp:1654-1661`) all
  verify against the worktree.
- **Part 05 (state-objects)**: **complements** — confirms field/index tables
  (`05:234-235,262`) and adds the `CHAINBASE_UNPACK_CONSTRUCTOR`/`get_dynamic_alloc`
  shared-memory details and the sentinel-key semantics of `by_delayed_voting`.
- **Part 07 (economic-model)**: **confirms** line 329 (claimed reward VESTS get immediate
  power, citing the same `hive_evaluator_transfer.cpp:674`) and extends it with the full
  per-path table.
- **Part 02 (operations-catalog)** / `reference/operations.md`: **confirms** vop #70
  identity, fields, and "last_regular + 21" position.
- **Part 09 (hardfork-history)**: **complements** the HF24 entry — adds that HF24's
  activation block performed no retroactive bucket initialization (pre-existing VESTS
  stayed fully mature) and the TIME vs ACTUAL_TIME anchor values.
- **Part 10 (api-layer)**: **complements** — pins the `delayed_votes_active` default
  (`true`) and the omit-when-false optional-field behavior for both database_api and
  condenser_api.

## Discrepancies and Potential Issues

1. **Latent `clear_account` accounting hole** (`database.cpp:1545` vs `:1560-1564`):
   subtracts full `vesting_shares` from the witness-vote/proxy chain while separately
   clearing buckets — over-subtracts by `sum_delayed_votes` if ever invoked post-HF24 on
   an account with immature buckets. Unreachable today (sole caller is HF23 processing,
   `database_hardfork.cpp:456`, when no buckets could exist). Candidate for a
   `contrib/hive-core/` note and an upstream cleanup if the seizure machinery is ever
   reused.
2. **`update_votes` leftover is assigned, not accumulated** (`delayed_voting.cpp:68`):
   correct under the current "exactly one executor entry" calling convention; a silent
   correctness trap if the batch protocol is ever extended (a second negative entry's
   leftover would overwrite the first).
3. **Misleading benchmark label**: maturation work in `run()` reports as
   `hive::protocol::transfer_to_vesting_operation` in the benchmark dumper
   (`delayed_voting.cpp:119`) — cosmetic only.
4. **Doc-comment vs code in `processor::add`** (`delayed_voting_processor.hpp:34-49`):
   the example implies calendar-date bucketing; actual windows are anchored at bucket
   creation time. The net effect (the (29, 30] delay window) is intended behavior, but
   the comment can mislead readers — minor.
5. **`FC_ASSERT( dv.valid() && "..." )` idiom** (`database_vesting.cpp:250,286`): the
   string literal is ANDed into the condition (always-true operand) instead of being the
   message argument (compare correct form at `:208`). Harmless — assert still fires on
   `!dv.valid()` — but the message is lost. Cosmetic.
6. **`account_object.hpp:264` comment** says "VESTS from day `X` will be matured after
   `X` + 30 days" — accurate for the bucket as a whole but, per Discovery 6, individual
   contributions late in a bucket's window wait less than 30 days. Same minor imprecision
   as item 4.

## Open Questions

- **HAF / sql_serializer representation** of `delayed_voting_operation` and bucket state
  (outside this area; belongs to a HAF-focused part).
- **RC cost shaping**: whether the `by_delayed_voting` index re-keying on every power-up
  contributes measurably to `transfer_to_vesting`'s RC cost model (RC area, Part 08).
- **Mirrornet/testnet shrink behavior**: `configuration_data.get_hive_delayed_voting_*`
  setters' interaction with functional tests (test-tools area) — the "at most 30 entries"
  comment at `config.hpp:102` implies the testnet ratio must be preserved manually; what
  enforces it (if anything) was not traced.
- **Historical**: whether any mainnet account actually held `delayed_votes` at a moment
  `clear_account`-like machinery could have been re-invoked (chain-state question; cannot
  be answered from code, and per the rules no claim is made about chain state).
