# Findings: delayed-voting

Deep-dive into the HF24 delayed (governance) voting subsystem of hive-core, verified
against release `1.28.8` (`274384a8adddf54b69965a7fd43d8eb0ddda7701`, worktree
`workspace/hive-core/274384a8ad`). Entry files `util/delayed_voting.{hpp,cpp}` were the
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
and only charge the matured surplus against live vote power; VESTS that a power-down
auto-vest route sends to another account are delayed again (Key Discovery 4). Every other
VESTS-creation path grants governance power immediately: producer rewards, PoW rewards and
pre-HF20 creation fees via `create_vesting`/`create_vesting2`, claimed reward VESTS at claim
time (Key Discovery 2).

## Key Discoveries

### 1. The delay applies ONLY to `transfer_to_vesting` (and power-down auto-vest routes)

- **What**: `create_vesting2` (`database_vesting_helpers.hpp:13-22`) is the common vesting
  helper, and at `database_vesting_helpers.hpp:18-19` it calls
  `db.adjust_proxied_witness_votes( to_account, new_vesting.amount )` whenever
  `is_reward == false` (the parameter was named `to_reward_balance` at 1.28.7): immediate
  governance power. The HF24 `transfer_to_vesting` evaluator deliberately bypasses it: it
  calls `adjust_account_vesting_balance` directly with a no-op callback
  (`hive_evaluator_transfer.cpp:324`) and registers a delayed bucket instead
  (`hive_evaluator_transfer.cpp:326-327`). All other callers go through
  `create_vesting`/`create_vesting2` and get instant vote power: producer (witness block)
  rewards (`database.cpp:1808`, `database.cpp:1845`), pre-HF20 account-creation-fee
  vesting (`hive_evaluator_account.cpp:197,253`), PoW rewards
  (`hive_evaluator.cpp:493,592`); the exceptions are the author, curation and beneficiary
  reward callers, which pass `is_reward = true` since HF17 (Key Discovery 2).
- **Where**: `database_vesting_helpers.hpp:18-19`, `hive_evaluator_transfer.cpp:322-328`
- **Impact**: "30-day delay on new VESTS" is only accurate for power-ups. A witness's
  block pay and any claimed reward VESTS raise governance weight in the same block. This
  is the precise boundary of the HF24 anti-takeover mechanism (the in-code rationale is
  the comment at `hive_evaluator_transfer.cpp:316-321`: immediate voting "is dangerous,
  because malicious accounts would take over whole HIVE network").

### 2. Claimed reward VESTS skip the delay explicitly

- **What**: `claim_reward_balance_evaluator` moves `reward_vesting_balance` into
  `vesting_shares` and then calls
  `_db.adjust_proxied_witness_votes( acnt, op_reward_vests.amount )` directly — no
  `delayed_voting` involvement. (When the reward was earned, `create_vesting2` was called
  with `is_reward = true` (post-HF17, `HIVE_HARDFORK_0_17__659`), which skips the
  witness-vote adjustment at that earlier moment, so the claim is when power activates.)
- **Where**: `hive_evaluator_transfer.cpp:705,720`; earning side
  `database_comment.cpp:171,272,294`
- **Impact**: Confirms and pins down Part 07's claim (section Claiming Rewards
  (`claim_reward_balance_operation`), and Key Discoveries, item 12). Author/curation rewards
  are treated as "already aged": only externally injected capital is quarantined.

### 3. Power-down consumes immature votes newest-first; only the surplus hits live power

- **What**: During `process_vesting_withdrawals`, the withdrawing account contributes a
  negative entry (`add_votes(items, true /*withdraw_executor*/, -to_withdraw, from)`,
  `database_vesting.cpp:257`). `update_votes` then erases `abs_val` from the
  account's buckets — `delayed_voting_processor::erase` pops from the **back** (newest
  buckets first, `delayed_voting_processor.hpp:108-122`) — and only if the withdrawal
  exceeds `sum_delayed_votes` does the leftover (`res = abs_val - sum_delayed_votes`)
  get applied as `adjust_proxied_witness_votes( from_account, -leftover )`
  (`delayed_voting.cpp:64-73`, `database_vesting.cpp:292-295`).
- **Where**: `util/delayed_voting.cpp:44-77`, `database_vesting.cpp:254-301`
- **Impact**: Powering down freshly vested HIVE costs you immature (never-counted) votes
  first; mature vote power is reduced only by the excess. Erase-from-back means the
  oldest, closest-to-maturity buckets survive longest — the most favorable ordering for
  the account. Confirmed by unit test `delayed_voting_processor_02`
  (`tests/unit/tests/delayed_voting_tests.cpp:1852-1899`).

### 4. Auto-vest withdraw routes to other accounts get a fresh 30-day delay

- **What**: When a power-down routes VESTS to another account with `auto_vest`, the
  recipient's amount is collected via
  `add_votes(items, to_self, routed_vests, to_account)` (`database_vesting.cpp:216`)
  and, in `update_votes`, positive entries call `add_delayed_value(account, now, val)`
  (`delayed_voting.cpp:61-62`): the value is added at time *now*, as a new bucket or into the
  recipient's newest bucket if that one is less than one interval old
  (`delayed_voting_processor.hpp:65-72`). A route back to
  self merges (same set key) with the executor's negative entry and nets out ≤ 0, so
  self-routed VESTS keep their original bucket ages.
- **Where**: `database_vesting.cpp:213-221`, `util/delayed_voting.cpp:26-42,61-62`
- **Impact**: VESTS that a power-down routes to another account do not carry their age
  along: the clock restarts for the recipient. Pre-HF24 the same code path credited
  the recipient instantly (`database_vesting.cpp:220`).

### 5. The `by_delayed_voting` index uses a `time_point_sec::maximum()` sentinel and the `has_delayed_votes()` guard is load-bearing

- **What**: `get_oldest_delayed_vote_time()` returns `time_point_sec::maximum()` for
  accounts with no buckets (`account_object.hpp:317-324`), pushing them to the end of the
  `by_delayed_voting` index (`detail/state/account_object_multiindex.hpp:32-37`). The
  maturation loop condition checks `current->has_delayed_votes()` *before* evaluating
  `head_time >= oldest + HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS`
  (`delayed_voting.cpp:87-89`); without that short-circuit, `maximum() + 30 days` would
  wrap `fc::time_point_sec`'s 32-bit seconds counter and make the comparison true,
  leading to `delayed_votes.begin()` on an empty vector.
- **Where**: `util/delayed_voting.cpp:87-91`, `account_object.hpp:317-324`
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
  `protocol/config.hpp:178-179`
- **Impact**: API consumers and tests must not assume "exactly 30 days from power-up";
  the guarantee is per-bucket, with up to ~1 day of forward credit for late merges into
  an existing bucket. Verified by `delayed_voting_processor_01` (merge at interval−3 s
  stays in bucket; merge at exactly +interval opens a new one;
  `delayed_voting_tests.cpp:1928-1939`).

### 7. Latent inconsistency: `clear_account` subtracts full `vesting_shares` from witness votes, ignoring `sum_delayed_votes`

- **What**: `clear_account` (HF23 Steem-fork seizure machinery) calls
  `adjust_proxied_witness_votes( account, -account.get_vesting().amount )`
  (`database.cpp:1558`) — but if the account had pending delayed votes, only
  `vesting_shares − sum_delayed_votes` ever entered the witness-vote chain, so this would
  over-subtract by `sum_delayed_votes`. The function *does* clear `delayed_votes` under a
  `has_hardfork( HIVE_HARDFORK_1_24 )` guard a few lines later (`database.cpp:1574-1578`),
  showing partial HF24 adaptation. Today `clear_account` is reachable only from HF23
  processing (`database_hardfork.cpp:451` via `clear_accounts`), where delayed voting did
  not yet exist (`sum_delayed_votes == 0` for every account), so the bug cannot fire on
  mainnet history — it is latent, not active.
- **Where**: `database.cpp:1558` vs `database.cpp:1574-1578`;
  caller `database_hardfork.cpp:449-451` (the HF23 case)
- **Impact**: If `clear_account` were ever reused for a future seizure/cleanup after
  HF24, accounts with immature buckets would corrupt witness-vote accounting (the correct
  delta is `-get_direct_governance_vote_power()` plus proxy handling, as
  `nullify_proxied_witness_votes` does at `database.cpp:1133-1140`). Flagged for contrib.

### 8. The 30-bucket cap is a steady-state guarantee; 31 buckets can exist transiently inside a block

- **What**: The comment in `run()` (`delayed_voting.cpp:101-109`) explains the design
  target of <= 30 entries (30 d / 1 d). A 31st bucket needs an addition whose
  `head_time >= oldest.time + 30 d` (bucket times are >= 1 day apart, so entry *i*
  satisfies `time[i] >= time[0] + i*1d`). A `transfer_to_vesting` transaction never meets
  it: transactions run with the previous block's timestamp (`database.cpp:2317`, before
  `database.cpp:2331`), at which that block's maturation already popped every bucket with
  `time + 30 d <=` that timestamp, so an account with 30 buckets has a newest bucket under
  one day old and the transaction merges into it. A power-down auto-vest route to another
  account runs after the head time moved to the new block's timestamp
  (`database_vesting.cpp:118`) and before maturation, so it can add a 31st bucket;
  maturation compares with that same timestamp and pops the oldest bucket at the end of
  the same block. So after every block, size <= 30 holds.
- **Where**: `delayed_voting_processor.hpp:65-72`, `delayed_voting.cpp:87-117`,
  ordering `database.cpp:2317` (transactions), `database.cpp:2331` (head time set to the
  block's timestamp, `database.cpp:2866`), `database.cpp:2355` (power-downs) vs
  `database.cpp:2365` (maturation, `database.cpp:1683`)
- **Impact**: Iteration/memory bounds hold per-block; only observers during end-of-block
  processing (between `database.cpp:2355` and `:2365`) can see 31 entries, while between
  transactions an account has at most 30.

## Data Structures and State

### Per-account state (`detail/state/account_object.hpp`)

| Field | Type | Notes |
|---|---|---|
| `delayed_votes` | `t_vector<delayed_votes_data>` | `account_object.hpp:286-291`; `t_vector` = `boost::interprocess::vector` in shared memory (`chainbase/allocator_helpers.hpp:91`); needs allocator at load: `CHAINBASE_UNPACK_CONSTRUCTOR( account_object, (delayed_votes) )` (`account_object.hpp:361`); counted in `get_dynamic_alloc` (`account_object.hpp:354-359`) |
| `sum_delayed_votes` | `ushare_type` (= `fc::safe<uint64_t>`, `protocol/types.hpp:72`) | cached sum of bucket vals (`account_object.hpp:247`); in-code TODO says "should be changed to VEST_asset" |

`delayed_votes_data` is `{ time_point_sec time; ushare_type val; }` with `operator==`,
reflected `(time)(val)` (`delayed_voting_processor.hpp:18-27,130-132`). Bucket `time` is
the **creation** head-block time of the bucket (start of its 1-day fill window), not its
maturation time.

### Derived vote-power accessors (`account_object.hpp:326-347`)

- `get_direct_governance_vote_power() = vesting_shares - sum_delayed_votes` with an
  embedded `FC_ASSERT( sum_delayed_votes <= vesting_shares )` (`account_object.hpp:329-334`;
  since 1.28.8 `vesting_shares` is a `VEST_balance`, read through `as_asset()`: Part 05,
  section account_object).
- `get_governance_vote_power() = direct + sum of proxied_vsf_votes` (`account_object.hpp:338-342`)
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
`account_object.hpp:291` second-guesses ("maybe separate index would be better").

### Helper structures for batch updates (`util/delayed_voting.hpp:11-33`)

`votes_update_data { bool withdraw_executor; mutable share_type val; const
account_object* account; }` collected in a `std::set` keyed **only** by `account->get_id()`
(`votes_update_data_less`, `delayed_voting.hpp:19-26`; null-pointer guarded by FC_ASSERT
with `object_is_null` message). `val` is `mutable` and *signed* so repeated `add_votes`
calls merge deposits/withdrawals for the same account in place through the const set
iterator (`delayed_voting.cpp:33-41`). `opt_votes_update_data_items` is
`fc::optional<set>`: an unset optional makes every `add_votes`/`update_votes` call a
no-op (`delayed_voting.cpp:28`, `:46`). Before HF24 `process_vesting_withdrawals` leaves
the optional and the `delayed_voting` helper unset (`database_vesting.cpp:151-155`) and
guards each call with `has_hardfork( HIVE_HARDFORK_1_24 )` (`:213`, `:254`, `:288`).

## The Bucket Collection Algebra (`delayed_voting_processor.hpp`)

Three static template functions maintain the parallel `(items, sum)` pair:

- **`add(items, sum, head_time, val)`** (`delayed_voting_processor.hpp:31-73`): no-op for
  `val == 0`; first entry just appended. Otherwise asserts `head_time >= back.time`
  (`incorrect_head_time`, `delayed_voting_processor.hpp:61`): bucket times are monotonic;
  then either merges into the back bucket (`head_time < back.time + 1 day`) or appends a
  new `{head_time, val}` bucket. The doc-comment example
  (`delayed_voting_processor.hpp:34-49`) showing per-calendar-date grouping is illustrative
  only: real windows are anchored at bucket creation time (see Key Discovery 6).
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

`transfer_to_vesting_evaluator::do_apply` (HF24 branch, `hive_evaluator_transfer.cpp:322-328`):

1. `adjust_account_vesting_balance(to_account, vesting_funds, false, no-op)`, where since
   1.28.8 `vesting_funds` is the `temp_HIVE_balance` the amount was moved into from the
   sender (`hive_evaluator_transfer.cpp:311-312`): VESTS credited immediately; mana bar
   and RC updated; global `total_vesting_shares` bumped (`database.cpp:1007-1044`; Part 04,
   section 2.2 Vesting Helpers). **No** witness-vote adjustment (this is the create_vesting2
   bypass).
2. `delayed_voting::add_delayed_value(to_account, head_block_time, amount_vested)` →
   `db.modify` + `processor::add` (`delayed_voting.cpp:7-13`).
3. `transfer_to_vesting_completed_operation` is emitted unconditionally — the in-code
   comment stresses the VESTS balance changed now, independent of the delayed governance
   activation (`hive_evaluator_transfer.cpp:334-335`; vop doc
   `hive_virtual_operations.hpp:498-509` cross-references `delayed_voting_operation`).

### Maturation (end-of-block)

`database::process_delayed_voting(note)` (`database.cpp:1678-1685`) — gated on
`has_hardfork( HIVE_HARDFORK_1_24 )` — constructs a `delayed_voting` and calls
`run( block_timestamp )` (`delayed_voting.cpp:79-120`):

```
while begin-account has buckets AND head_time ≥ oldest.time + 30 days:
    val = oldest bucket value
    emit delayed_voting_operation( account, val )          // :95-97
    adjust_proxied_witness_votes( account, val )           // :99
    modify: processor::erase_front( buckets, sum )         // :110-113
    re-fetch idx.begin()                                   // delayed_voting.cpp:115 (modify re-keyed the account)
```

One bucket per iteration, one vop per bucket; an account with several matured buckets is
revisited because erasing the front re-keys it (usually still at `begin()`). The injected
value follows the proxy chain exactly like any live vote-power delta
(`database.cpp:1110-1131`): with a proxy set it lands in the proxy's
`proxied_vsf_votes[0]`; without one, `adjust_witness_votes` adds it in full to each witness
the account currently votes for (`database_witness.cpp:58-67`). For an account that declined voting rights the call is a
harmless no-op (no proxy, no witness-vote records — `database_dhf.cpp:226-238` cleared
them), and its remaining buckets simply drain over the following days.

Maturation is wrapped in benchmark-dumper instrumentation labeled
`"hive::protocol::transfer_to_vesting_operation"` (`delayed_voting.cpp:84-86,118-119`) —
the label names the originating operation, not a real evaluator run.

### Cancellation (power-down) — the `withdraw_executor` protocol

`process_vesting_withdrawals` (`database_vesting.cpp:111-307`; pools and conversion: Part 07,
section Power Down (VESTS -> HIVE)) builds one batch per withdrawing account per weekly
installment:

1. HF24 setup: `optional<delayed_voting> dv` + an engaged `opt_votes_update_data_items`
   (`database_vesting.cpp:148-155`); pre-HF24 both stay unset and all calls degrade to no-ops.
2. **Routes** (auto-vest pass first): each auto-vest route deposit > 0 adds
   `add_votes(items, to_self, +routed_vests, to_account)` (`database_vesting.cpp:213-221`);
   `to_self` is true when the route loops back to the withdrawer (`database_vesting.cpp:179`).
   Pre-HF24 branch instead credits the recipient instantly (`database_vesting.cpp:220`).
3. **Executor**: `add_votes(items, true, -to_withdraw, from_account)`
   (`database_vesting.cpp:254-258`).
4. **Resolution**: `update_votes(items, now)` (`delayed_voting.cpp:44-77`) walks the set:
   - Sign/role invariant per entry: `(!withdraw_executor && val > 0) || (withdraw_executor
     && val ≤ 0)` (`:53-56`, `incorrect_votes_update`). Merging in `add_votes` asserts the
     flag never flips for a given account (`:39`, `incorrect_withdraw_data`).
   - Positive entries (route recipients): `add_delayed_value(account, now, val)`: delayed
     again, as a new bucket or merged into the recipient's newest one (Key Discovery 4).
   - The single possible negative entry (the executor; a self-route merges into it and
     nets `routed − to_withdraw ≤ 0`): erase `min(abs_val, sum_delayed)` from buckets;
     `res = abs_val − sum_delayed` if the withdrawal exceeds the buffer (`:63-73`).
   - Returns `res` as `fc::optional<ushare_type>` (engaged iff items engaged).
5. Caller applies the matured surplus: `adjust_proxied_witness_votes(from, −leftover)`
   (`database_vesting.cpp:288-296`); pre-HF24 it subtracted the whole `to_withdraw`
   (`database_vesting.cpp:297-301`).

A 100 %-auto-vest-to-self power-down therefore nets `val == 0`, which `update_votes`
skips (`delayed_voting.cpp:58-59`): buckets, ages, and live power all stay untouched,
correctly modeling that nothing actually left the account.

Note `update_votes` *assigns* (`res = …`) rather than accumulates; this is sound only
because the set can contain at most one negative entry (the executor — route targets are
distinct accounts with positive values, and a self-route shares the executor's entry).

## Per-Block Processing Order (`database.cpp:2350-2366`)

```
clear_null_account_balance();        // database.cpp:2350 - zeroes null's buckets outright (:1244-1245)
consolidate_treasury_balance();      // database.cpp:2351 - zeroes old-treasury buckets (:1363-1364)
...
process_vesting_withdrawals();       // database.cpp:2355 - bucket cancellation + route re-delays
...
process_decline_voting_rights();     // database.cpp:2363
process_proposals( note );           // database.cpp:2364 - DHF tally: delayed votes excluded
process_delayed_voting( note );      // database.cpp:2365 - maturation
remove_expired_governance_votes();   // database.cpp:2366
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
| Decline-voting-rights nullify | Yes — `nullify_proxied_witness_votes` uses direct power | `database.cpp:1133-1140`, `database_dhf.cpp:226` |
| Comment voting mana | **No** - manabars track raw/effective VESTS | `database.cpp:1033-1035` (mana grows at vest time) |
| RC max mana | **No** - `get_maximum_rc` (`account_object.hpp:130-136`) builds on `get_effective_vesting_shares`, which never subtracts `sum_delayed_votes` | `account_object.hpp:111-117` |
| Delegation capacity | **No** - same `get_effective_vesting_shares` basis | `account_object.hpp:111-117`, `hive_evaluator_transfer.cpp:744-751` |
| Power-down eligibility | **No** — checks `vesting − delegated` | `hive_evaluator_transfer.cpp:353-354` |

VESTS-creation paths vs. the delay:

| Path | Governance power | Where |
|---|---|---|
| `transfer_to_vesting` (HF24+) | Delayed ~30 d | `hive_evaluator_transfer.cpp:322-328` |
| `transfer_to_vesting` (pre-HF24) | Immediate | `hive_evaluator_transfer.cpp:331` |
| Power-down auto-vest route -> other account | Re-delayed, (29, 30] d like a power-up (HF24+) | `database_vesting.cpp:216` + `delayed_voting.cpp:61-62` |
| Power-down auto-vest route -> self | Nets against the withdrawal: buckets untouched only for a 100% route to self (`delayed_voting.cpp:58-59`), otherwise the net erases buckets (`delayed_voting.cpp:63-72`) | `database_vesting.cpp:179,216` + `delayed_voting.cpp:58-59` |
| Producer (witness) reward | Immediate | `database.cpp:1807-1814,1844-1851` via `database_vesting_helpers.hpp:18-19` |
| `claim_reward_balance` VESTS | Immediate at claim | `hive_evaluator_transfer.cpp:720` |
| Account-creation fee vesting (pre-HF20) | Immediate | `hive_evaluator_account.cpp:192-198,248-254` |
| PoW mining rewards (legacy) | Immediate | `hive_evaluator.cpp:493,592` |

## Invariants

1. **Per-account cache coherence**: `sum_delayed_votes == Σ buckets[i].val` — asserted in
   `validate_invariants` (`database.cpp:3453-3456`).
2. **Bound**: `sum_delayed_votes ≤ vesting_shares` — asserted both in
   `get_direct_governance_vote_power` (`account_object.hpp:329-332`) and in
   `validate_invariants` (`database.cpp:3457`). Holds because only vested amounts create
   buckets and every vesting decrease cancels buckets first.
3. **Global conservation**: `gpo.total_vesting_shares == total_vsf_votes +
   total_delayed_votes`, where `total_vsf_votes` is the recomputed per-account governance
   power (proxied accounts counted via their top-level proxy slot)
   (`database.cpp:3436-3480`). I.e., every VEST is either active governance weight or
   sitting in someone's buckets.
4. **Bucket times strictly increase, adjacent gaps ≥ 1 day** — by construction in
   `processor::add` (`delayed_voting_processor.hpp:61-72`).
5. **<= 30 buckets after end-of-block processing** (transiently 31 during end-of-block
   processing; Key Discovery 8).
6. **At most one `withdraw_executor` entry per update batch**, and it is the withdrawing
   account (`add_votes` merge assert `delayed_voting.cpp:39`; sign invariant `:53-56`).

## Hardfork-Conditional Behavior

| Guard | Effect | Where |
|---|---|---|
| `HIVE_HARDFORK_1_24` | enables `process_delayed_voting` | `database.cpp:1680` |
| `HIVE_HARDFORK_1_24` | transfer_to_vesting buffers instead of instant power | `hive_evaluator_transfer.cpp:322` |
| `HIVE_HARDFORK_1_24` | power-down uses batch protocol (4 sites: setup / route / executor / resolve) | `database_vesting.cpp:151,213,254,288` |
| `HIVE_HARDFORK_1_24` | `clear_account` clears buckets | `database.cpp:1574-1578` |
| `HIVE_HARDFORK_1_24_TREASURY_RENAME` (= HF24, `1_24.hf:34`) | old-treasury consolidation liquifies VESTS and zeroes buckets (comment: moving vests in vested form "would complicate delayed_votes part") | `database.cpp:1296-1373` |
| HF24 activation block itself | the HF24 case runs `restore_accounts` + `set_chain_id`; after the hardfork is marked applied, the treasury-rename block (which calls `consolidate_treasury_balance`) and the blockchain-config update run; none of them creates buckets - **no retroactive bucket initialization**; all pre-HF24 VESTS started fully mature | `database_hardfork.cpp:466-475`, `:524-547` |
| `HIVE_HARDFORK_1_28_FIX_POWER_DOWN` / `_FIX_CANCEL_POWER_DOWN` | adjacent power-down fixes: the last-installment amount in the withdrawal loop, and the `withdraw_vesting` evaluator rejecting a request that would not change the withdraw rate (cancel without an active power-down included) - they alter how much is withdrawn or which requests are accepted, feeding the delayed-voting batch, but not the batch logic itself | `database_vesting.cpp:128`, `hive_evaluator_transfer.cpp:360-361`, `:389-390`, `1_28.hf:15,17` |

Constants: mainnet `HIVE_DELAYED_VOTING_TOTAL_INTERVAL_SECONDS = 60*60*24*30` (30 days),
`HIVE_DELAYED_VOTING_INTERVAL_SECONDS = 60*60*24*1` (1 day) (`protocol/config.hpp:178-179`);
`IS_TEST_NET` builds route both through `configuration_data` (`protocol/config.hpp:100-101`):
the total defaults to 1 day and is the only settable value (tests can shrink it), and the
interval getter returns total / 30 (integer division), which keeps the 30-entry shape
("similary to mainnet" comment) for any total that is a multiple of 30
(`testnet_blockchain_configuration.hpp:53`, `:121-122`, `:215-219`; the same at 1.28.7).

HF24 anchors: `HIVE_HARDFORK_1_24_TIME = 1601992800` (2020-10-06 14:00 UTC, earliest
allowed) and `HIVE_HARDFORK_1_24_ACTUAL_TIME = 1602703884` (2020-10-14 19:31:24 UTC,
block where it took effect on mainnet) (`1_24.hf:22,27`).

## Account Clearing Paths

- **`clear_null_account_balance`** (`database.cpp:1234-1255`): burning `null`'s VESTS
  zeroes `sum_delayed_votes`/`delayed_votes` directly (no witness-vote adjustment —
  `null` cannot vote). Unguarded by HF24 (clearing empty vectors is harmless pre-HF24).
- **`consolidate_treasury_balance`** (`database.cpp:1355-1373`): old treasury
  (`steem.dao`) VESTS are liquified to HIVE on the new treasury and buckets zeroed.
  `is_treasury` matches both `steem.dao` and `hive.fund` (`database.cpp:373-376`), so the
  HF21 treasury asserts of `transfer_to_vesting` and `set_withdraw_vesting_route` reject
  both names (`hive_evaluator_transfer.cpp:307-308`, `:411-413`; the same at 1.28.7). The
  consolidation is called every block (`database.cpp:2351`) and returns early while the old
  treasury holds nothing (`database.cpp:1309-1311`).
- **`clear_account`** (`database.cpp:1491-1667`): HF23 seizure path - see Key Discovery 7
  for the latent `sum_delayed_votes` accounting hole at `database.cpp:1558`.

## API Exposure

- `database_api.find_accounts` / `list_accounts` take `delayed_votes_active` (default
  `true`, `database_api_args.hpp:186,198`); `api_account_object` fills its
  `fc::optional<vector<delayed_votes_data>> delayed_votes` only when the flag is set
  (`database_api_objects.hpp:363,726`; constructor
  `database_api_objects_constructors.cpp:198,271-272`; call sites
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
| `incorrect_head_time` | `processor::add` (`delayed_voting_processor.hpp:61`) | new contribution older than back bucket (monotonicity breach) |
| `incorrect_sum_greater_equal` | `processor::erase_front` (`delayed_voting_processor.hpp:82`) | cached sum < front bucket value |
| `incorrect_sum_equal` | `processor::erase_front` (`delayed_voting_processor.hpp:88`) | empty buckets but nonzero cached sum |
| `incorrect_erased_votes` | `processor::erase` (`delayed_voting_processor.hpp:97`) | cancel amount exceeds cached sum |
| `object_is_null` | `votes_update_data_less` (`delayed_voting.hpp:23`) | null account pointer in batch set |
| `incorrect_votes_update` | `update_votes` (`delayed_voting.cpp:53-56`) | sign/role invariant violated |
| `incorrect_withdraw_data` | `add_votes` (`delayed_voting.cpp:39`) | same account merged with flipped executor flag |

All are `FC_ASSERT`s on the block-application path — corruption tripwires, not
recoverable validation errors. Additional belt-and-braces asserts guard the power-down
batch plumbing (`database_vesting.cpp:215,256,290,293` — note `:256` and `:290` use the
buggy-but-harmless `FC_ASSERT( dv.valid() && "msg" )` idiom where the string is part of
the condition, and `database_vesting.cpp:293` asserts the optional result is engaged).

## Test Coverage (`tests/unit/tests/delayed_voting_tests.cpp`)

Two suites (`delayed_voting_proposal_tests`, `delayed_voting_tests`, both on
`delayed_vote_database_fixture`), 24 cases: processor-level algebra
(`delayed_voting_processor_01..03` — merge windows, erase-from-back, error paths,
`delayed_voting_tests.cpp:1789-2032`), evaluator/maturation scenarios (`delayed_voting_01/04/05/06`,
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
| `delayed_votes`, `sum_delayed_votes` | `libraries/chain/include/hive/chain/detail/state/account_object.hpp` | 247, 286-291 | per-account state |
| `has_delayed_votes`, `get_oldest_delayed_vote_time` | `libraries/chain/include/hive/chain/detail/state/account_object.hpp` | 315-324 | index key + maximum() sentinel |
| `get_direct_governance_vote_power` | `libraries/chain/include/hive/chain/detail/state/account_object.hpp` | 326-335 | vesting - delayed (asserted bound) |
| `by_delayed_voting` index | `libraries/chain/include/hive/chain/detail/state/account_object_multiindex.hpp` | 32-37 | (oldest_time, id) ordering |
| constants (mainnet) | `libraries/protocol/include/hive/protocol/config.hpp` | 178-179 | 30 d total / 1 d interval |
| constants (testnet-configurable) | `libraries/protocol/include/hive/protocol/config.hpp` | 100-101 | via `configuration_data` |
| `transfer_to_vesting` HF24 branch | `libraries/chain/hive_evaluator_transfer.cpp` | 322-328 | delayed entry at transaction time (the other entry: power-down auto-vest routes, Key Discovery 4) |
| `claim_reward_balance` bypass | `libraries/chain/hive_evaluator_transfer.cpp` | 720 | immediate power on claim |
| `create_vesting2` | `libraries/chain/database_vesting_helpers.hpp` | 13-22 | immediate-power helper (vote call `database_vesting_helpers.hpp:18-19`) |
| power-down batch | `libraries/chain/database_vesting.cpp` | 148-155, 213-221, 254-258, 288-301 | routes, executor, resolution, leftover |
| `process_delayed_voting` | `libraries/chain/database.cpp` | 1678-1685 | HF24 gate |
| block-processing order | `libraries/chain/database.cpp` | 2350-2366 | withdrawals before maturation |
| `adjust_proxied_witness_votes` | `libraries/chain/database.cpp` | 1110-1131 | delta propagation (proxy chain → witnesses) |
| `clear_account` delayed handling | `libraries/chain/database.cpp` | 1558, 1574-1578 | latent over-subtraction (Discovery 7) |
| null/treasury clearing | `libraries/chain/database.cpp` | 1244-1245, 1363-1364 | bucket zeroing |
| invariants | `libraries/chain/database.cpp` | 3436-3480 | sum coherence, bound, global conservation |
| `delayed_voting_operation` | `libraries/protocol/include/hive/protocol/hive_virtual_operations.hpp` | 381-396 | vop #70 |
| op position | `libraries/protocol/include/hive/protocol/operations.hpp` | 100 | `last_regular + 21` |
| impacted accounts | `libraries/protocol/forward_impacted.cpp` | 502-507 | voter |
| API field + flag | `libraries/plugins/apis/database_api/` | `database_api_objects.hpp:363`, `database_api_args.hpp:186,198`, `database_api_objects_constructors.cpp:271-272` | optional `delayed_votes` in account objects |
| condenser positional flag | `libraries/plugins/apis/condenser_api/condenser_api.cpp` | 363-377, 405-418 | get_accounts / lookup_account_names |
| HF24 time anchors | `libraries/protocol/hardfork.d/1_24.hf` | 22, 27 | planned vs actual activation |
| HF23/HF24 account actions | `libraries/chain/database_hardfork.cpp` | 449-475 | clear (HF23) / restore (HF24) |
| unit tests | `tests/unit/tests/delayed_voting_tests.cpp` | 85-2908 | 24 cases incl. processor algebra |

## Cross-references to existing parts

- **Part 04 (chain-evaluators) §2.14, §2.15-adjacent, finding 15**: this zoom **deepens**
  it substantially: adds the `create_vesting2` vote-call mechanism
  (`database_vesting_helpers.hpp:18-19`) that explains *why* producer VESTS bypass the
  delay while reward VESTS gain power only at claim time (Part 04 states the claim-reward
  bypass, section 2.14 Delayed Voting, and the facts behind the producer case, sections
  2.2 Vesting Helpers and 2.13 Other End-of-Block Processing Methods, without drawing that
  consequence), the `withdraw_executor` batch protocol and
  its single-negative-entry constraint, route-to-self netting, erase-from-back ordering,
  the (29, 30]-day effective-delay window, the `maximum()` sentinel guard, and the
  transient-31-bucket bound. No contradictions found: Part 04's statements (30-bucket
  cap, leftover rule, one vop per bucket, HF24 gate at `database.cpp:1678-1685`) all
  verify at 1.28.8.
- **Part 05 (state-objects)**: **complements** — confirms field/index tables
  (section account_object) and adds the `CHAINBASE_UNPACK_CONSTRUCTOR`/`get_dynamic_alloc`
  shared-memory details and the sentinel-key semantics of `by_delayed_voting`.
- **Part 07 (economic-model)**: **confirms** its section Claiming Rewards
  (`claim_reward_balance_operation`) and Key Discoveries, item 12 (claimed reward VESTS get
  immediate power, citing the same `hive_evaluator_transfer.cpp:720`) and extends them with
  the full per-path table.
- **Part 02 (operations-catalog)** / `reference/operations.md`: **confirms** vop #70
  identity, fields, and "last_regular + 21" position.
- **Part 09 (hardfork-history)**: **complements** the HF24 entry — adds that HF24's
  activation block performed no retroactive bucket initialization (pre-existing VESTS
  stayed fully mature); the TIME vs ACTUAL_TIME anchor values agree with Part 09, sections
  TIME vs ACTUAL_TIME and HF24.
- **Part 10 (api-layer)**: **complements** — pins the `delayed_votes_active` default
  (`true`) and the omit-when-false optional-field behavior for both database_api and
  condenser_api.

## Discrepancies and Potential Issues

1. **Latent `clear_account` accounting hole** (`database.cpp:1558` vs `:1574-1578`):
   subtracts full `vesting_shares` from the witness-vote/proxy chain while separately
   clearing buckets — over-subtracts by `sum_delayed_votes` if ever invoked post-HF24 on
   an account with immature buckets. Unreachable today (the only caller in node code is HF23
   processing, `database_hardfork.cpp:451` via `clear_accounts`, `database.cpp:1487`, when no
   buckets could exist; the HF23 unit tests also call both functions directly). Candidate for a
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
5. **`FC_ASSERT( dv.valid() && "..." )` idiom** (`database_vesting.cpp:256,290`): the
   string literal is ANDed into the condition (always-true operand) instead of being the
   message argument (compare correct form at `database_vesting.cpp:215`). Harmless - assert still fires on
   `!dv.valid()`; the format message is empty, but fc keeps the condition text, string
   included, as the assertion expression and prints it (fc `exception.hpp:382`). Cosmetic.
6. **`account_object.hpp:289` comment** says "VESTS from day `X` will be matured after
   `X` + 30 days" — accurate for the bucket as a whole but, per Discovery 6, individual
   contributions late in a bucket's window wait less than 30 days. Same minor imprecision
   as item 4.

## Open Questions

- **HAF / sql_serializer representation** of `delayed_voting_operation` and bucket state
  (outside this area; belongs to a HAF-focused part).
- **RC cost shaping**: whether the `by_delayed_voting` index re-keying on every power-up
  contributes measurably to `transfer_to_vesting`'s RC cost model (RC area, Part 08).
- **Mirrornet/testnet shrink behavior** (resolved; the code answers it, the same at
  1.28.7): the "at most 30 entries" comment at `protocol/config.hpp:101` seemed to imply
  that the testnet ratio must be preserved manually. It is enforced by construction: only
  the total is settable (`set_governance_voting_related_values`, default 1 day), and
  `get_hive_delayed_voting_interval_seconds()` returns total / 30, an integer division, so
  the 30-entry shape holds for any total that is a multiple of 30
  (`testnet_blockchain_configuration.hpp:53`, `:121-122`, `:215-219`). In-tree only a unit
  test sets the total, to 1 day and to 90 s
  (`condenser_api_ops_in_block_tests.cpp:553`, `:688`). Builds without `IS_TEST_NET` use
  the fixed 30 d / 1 d (`protocol/config.hpp:67`, `:178-179`).
- **Historical**: whether any mainnet account actually held `delayed_votes` at a moment
  `clear_account`-like machinery could have been re-invoked (chain-state question; cannot
  be answered from code, and per the rules no claim is made about chain state).
