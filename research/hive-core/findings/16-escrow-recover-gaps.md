# Findings: escrow-recover-gaps

> Source pinned at hive-core `274384a8adddf54b69965a7fd43d8eb0ddda7701` (release
> 1.28.8). Every `file:line` below is from that worktree. Where a fact could not be verified from
> the area's files it is called out explicitly.

## Summary

The four escrow operations and the account-recovery/change-recovery operations share a common
shape: stateless `validate()` checks the operation's internal consistency, while the evaluator
holds **all** the consensus-relevant rules (existence, balances, approval/dispute state, time
windows, permission matrices). This zoom maps the full escrow state machine, the recovery request
lifecycle, their once-per-block cleanup passes, and several subtle gaps: an **approved-or-disputed
escrow has no timeout** (it stays until `escrow_release` empties it), the `recover_account` rate-limit
**enforces once-per-hour but emits the "twice an hour" message** post-HF26, the
`request_account_recovery` authority size is the subject of an HF29 switch (Key Discovery 3), and
the "no recovery account -> top witness" sentinel is **account id 0 = `miners`**, so an account
whose recovery account is `miners` is treated as having none, although the in-code comment of
`change_recovery_account` says the agent cannot be cleared back to the top witness.

## Key Discoveries

### 1. Escrow has two distinct removal triggers with different time semantics
- **What**: An **unapproved** escrow is auto-refunded after `ratification_deadline` by the
  per-block `expire_escrow_ratification()`. An **approved** escrow has **no** automatic cleanup —
  `escrow_expiration` only changes *who may release to whom* and ends the dispute window
  (`hive_evaluator_transfer.cpp:190`), never forces resolution. A disputed
  escrow likewise never times out. If the agent (disputed) or both parties (non-disputed) never act,
  the funds stay in the `escrow_object` forever.
- **Where**: `database_market.cpp:91-103` (`expire_escrow_ratification`, iterates
  `by_ratification_deadline` `lower_bound(false)` - only `is_approved()==false` rows; since 1.28.8
  each expired escrow is refunded and removed by `remove_escrow`, `database_market.cpp:58-89`);
  `hive_evaluator_transfer.cpp:204-266` (`escrow_release` - the only operation that empties an
  approved escrow; the one-time HF23 account clearing also removed the escrows sent by the cleared
  accounts, approved or not, see Counters and limits); `escrow_object_multiindex.hpp:19-26` (the
  deadline index keys on `is_approved` first).
- **Impact**: By design (the `escrow_transfer_operation` doc comment, `hive_operations.hpp:225-229`),
  a disputed escrow stays until the agent releases it and an approved one
  until `from` or `to` releases it; no timed or per-block process removes it. Part 05 lists the
  removal triggers but does not call out the "approved escrows never expire" property.

### 2. `recover_account` rate-limit message/behavior mismatch after HF26
- **What**: `recover_account` calls the **2-argument** `owner_update_limit_mgr::check(head_block_time,
  last_account_recovery_time)`, which is the strict `now - last > HIVE_OWNER_UPDATE_LIMIT` (60 min)
  rule. But the error message is produced by `msg(has_hardfork(HIVE_HARDFORK_1_26_AUTH_UPDATE))`,
  which returns *"Owner authority can only be updated twice an hour."* post-HF26. So after HF26 the
  enforced limit is still **once per hour** while the message advertises **twice per hour**.
- **Where**: `hive_evaluator_account.cpp:544-545`; `owner_update_limit_mgr.cpp:10-12` (2-arg check),
  `:28-31` (`msg` selects `message_hf26`). Contrast `account_update`/`account_update2` which use the
  **4-argument** check (HF26 flag, head block time, `previous_owner_update`, `last_owner_update`;
  `owner_update_limit_mgr.cpp:15-26`) that genuinely doubles the rate post-HF26
  (`hive_evaluator_account.cpp:304-306`, `:362-364`).
- **Impact**: Recovery is asymmetric with ordinary owner-auth updates: HF26 relaxed `account_update`
  to twice/hour but **not** `recover_account`. The mismatched message is a minor correctness wart
  (user sees a limit that does not match reality).

### 3. `request_account_recovery` authority size: checked on every path when in control or under HF29
- **What**: HF29 switch `HIVE_HARDFORK_1_29_FIX_ENFORCEMENT_OF_AUTHORITY_SIZE_ON_RECOVERY_REQUEST`
  (defined in 1.28.8, inactive on mainnet): `request_account_recovery` checks the size of the new
  owner authority on every request path (`hive_evaluator_account.cpp:500-506`). A 1.28.8 node
  already applies this check to new transactions submitted to it (API or P2P) and to blocks it
  produces (`is_in_control()`, `database.hpp:176`). See Part 01, section HF29 (Defined in 1.28.8,
  Inactive on Mainnet), and Part 11, Key Discovery 5.
- **Where**: `hive_evaluator_account.cpp:500-506` (the check before the branch on new / cancel /
  change request; the comment at `:501` says to check after HF29 activation whether it can move to
  `validate()`); the switch is defined at `hardfork.d/1_29.hf:24`.
- **Impact**: The size rule for this operation is an evaluator rule: stateless `validate()`
  (`hive_operations.cpp:720-725`) only runs `new_owner_authority.validate()` (account names, not
  size).

### 4. "No recovery account" sentinel is account id 0 = `miners`
- **What**: `has_recovery_account()` is defined as `recovery_account != account_id_type()`, i.e. the
  stored `account_id_type` is not 0. The first account created at genesis is `HIVE_MINER_ACCOUNT`
  (`"miners"`), so it holds **id 0**. Consequently an account whose recovery account is literally
  `miners` is indistinguishable from one with *no* recovery account, and the recovery path falls back
  to "top-voted witness must recover."
- **Where**: `account_object.hpp:167` (`has_recovery_account`), `:169` (`get_recovery_account`),
  `:171-174` (`set_recovery_account` stores `new_recovery_account.get_id()`);
  `database_init.cpp:197` (`miners` created first -> id 0);
  `hive_evaluator_account.cpp:492-495` (no-recovery -> top-witness branch in
  `request_account_recovery`).
- **Impact**: See Discovery 5: the ABW comment in `change_recovery_account` says the recovery agent
  cannot be cleared back to "top witness"; the evaluator checks only that `new_recovery_account`
  exists (`hive_evaluator_account.cpp:577`), and for `"miners"` the id stored when the change is
  applied is 0, which `has_recovery_account()` reads as no recovery account.

### 5. `change_recovery_account` to `"miners"` contradicts its own "can't clear" comment
- **What**: The evaluator comment at `hive_evaluator_account.cpp:577-578` states *"can't clear
  existing recovery agent to set it to top voted witness."* That is true for the *empty-string* case
  (the op validates `new_recovery_account` as a real account name). But `"miners"` **is** a real
  account; setting it makes `recovery_account == id 0`, which `has_recovery_account()` reports as
  false, re-enabling the top-witness fallback. The change is applied by
  `account_recovery_processing()` via `set_recovery_account(get_account(...))`.
- **Where**: comment at `hive_evaluator_account.cpp:577-578`; application at
  `database.cpp:2015-2028` (`account_recovery_processing` change-request loop, calls
  `a.set_recovery_account( new_recovery_account )`).
- **Impact**: A behavioral edge that the comment denies. **Not empirically tested** in this zoom —
  flagged as a discrepancy to verify on testnet (does `change_recovery_account` with
  `new_recovery_account = "miners"` succeed, and does the resulting account then route recovery to
  the top witness?). Whether intended or an oversight is unclear from the code alone.

### 6. RC: recover_account is paid by the *victim* and conditionally free
- **What**: The RC "user" (payer) for `recover_account` is `account_to_recover`, **not** the
  recovery agent (one of the three overrides of the payer rule, Part 08, section Summary). The
  transaction is **subsidized (free)** iff `recover_account` is its only operation, the new owner
  authority has exactly one total entry (single key or single account-auth) and the tx carries at
  most 2 signatures (Part 08, Key Discovery 6); multisig recoveries are **not** subsidized.
  `request_account_recovery` has no payer override: as the first operation of a transaction it makes
  its required active authority, `recovery_account` (the agent), the payer.
- **Where**: `rc/resource_user.cpp:22-24` (payer = `account_to_recover`);
  `rc/resource_count.cpp:534-545` (`subsidized_op = 1 == (key_auths + account_auths)`,
  `subsidized_signatures = 2`), `:606-611` (single-subsidized-op tx → zero cost);
  `rc/resource_count.cpp:89-98` (differential: old owner-auth bytes ignored when subsidized).
- **Impact**: A compromised account with **no RC** can still be recovered (single-key replacement is
  free), but the design deliberately denies the subsidy to multisig recoveries to avoid funding the
  setup of new multisig from a stolen account. Part 08 gives the differential usage and the subsidy
  conditions (Key Discovery 6); this zoom adds which account the `recover_account` payer override
  names.

### 7. Either escrow party can unilaterally cancel before ratifying
- **What**: In `escrow_approve`, `reject_escrow = !o.approve`. The "already approved" assert fires
  for the *acting* party, but rejection refunds **everything to `from`** and deletes the escrow
  regardless of the *other* party's approval state. So after `to` approves, the `agent` can still
  reject and kill the escrow (and vice-versa) — until a party has itself approved, it can reject.
- **Where**: `hive_evaluator_transfer.cpp:136-166`. Reject branch (`:163-166`) calls
  `remove_escrow` (since 1.28.8, `database_market.cpp:58-89`), which refunds
  `hive_balance + hbd_balance + fee` to `from`, emits `escrow_rejected_operation`, decrements
  `pending_escrow_transfers` and removes the object.
- **Impact**: The approval handshake is *cancellable* by either counterparty up to the moment they
  approve; only mutual approval (`hive_evaluator_transfer.cpp:167`) locks the escrow into the active
  state. Worth documenting for anyone modelling escrow as "2-of-2 commit."

## Escrow State Machine

### Objects and fields
`escrow_object` (`escrow_object.hpp:14-84`) holds three **account names** (`from`/`to`/`agent` -
explicit TODO: "can be replaced with account_id_type (ABW: would make looking for escrow object
harder)", `escrow_object.hpp:69-71`), the two deadlines, `hbd_balance`/`hive_balance`
(`HBD_balance`/`HIVE_balance` since 1.28.8, `HBD_asset`/`HIVE_asset` at 1.28.7), a single
`pending_fee` (`balance` since 1.28.8, `asset` at 1.28.7; can be HIVE *or* HBD, `:76`), and three
flags `to_approved`/`agent_approved`/`disputed` (TODO: pack into a bitfield, `:77-79`); field table
in Part 05, section escrow_object. Since 1.28.8 the fields are private behind getters, balance
accessors and the flag setters `approve_to()`, `approve_agent()`, `start_dispute()` (`:30-65`), and
removing the object asserts that all three balances are empty (`check_on_remove()`, `:51-55`).
`is_approved() == to_approved && agent_approved` (`:48`). Init copies the three names
(`hive_objects.cpp:47-52`).

Indices (`escrow_object_multiindex.hpp`):
- `by_from_id` = `(from, escrow_id)` — how every evaluator finds an escrow (`get_escrow`,
  `find_escrow`, `database_market.cpp:33-43`).
- `by_ratification_deadline` = `(is_approved, ratification_deadline, id)` with comparator
  `less<bool>, less<time_point_sec>, less<id>` — so `lower_bound(false)` walks **unapproved** escrows
  in deadline order; approved escrows sort after and are never visited by the expiry pass.

### States and transitions

```
                       escrow_transfer (from, active auth)
                          | debits from: hive_amount+hbd_amount+fee
                          v
                 [PENDING: !to_approved && !agent_approved]
                  |              |                     |
   escrow_approve |  escrow_approve(approve=false)     | ratification_deadline passes
   (to or agent,  |  by either party, OR               | (per-block expire_escrow_ratification)
    approve=true) |                                    |
                  v              v                     v
        [partial approval]   refund-all-to-from + remove  refund-all-to-from + remove
                  |            (escrow_rejected_op)        (escrow_rejected_op)
   both approved  |
                  v
        pay fee to agent, pending_fee emptied  <-- escrow_approve (hive_evaluator_transfer.cpp:167-178)
                  |
                  v
              [ACTIVE: is_approved(), fee paid]
                /            \
   escrow_dispute            escrow_release (no dispute)
   (from or to,              - before escrow_expiration: from->to or to->from only
    before expiration)       - after  escrow_expiration: from/to -> either party
                |              who must be from|to (NOT agent)
                v
            [DISPUTED]
                |
   escrow_release (agent only, to either party, any time)
                |
                v (when both balances hit 0)
        remove escrow, pending_escrow_transfers--
```

### Time-boundary details (strict vs non-strict)
- Create: `ratification_deadline > head_block_time` **and** `escrow_expiration > head_block_time`
  (both strict, `hive_evaluator_transfer.cpp:83-84`).
- Approve: allowed while `ratification_deadline >= head_block_time` (**non-strict**, `:134`).
- Expire pass removes when `ratification_deadline <= head_block_time` (**non-strict**,
  `database_market.cpp:97`).
- The transactions of a block are evaluated while `head_block_time` is still the previous block's
  timestamp (loop `database.cpp:2309-2319`; `update_global_dynamic_data`, called at `:2331`, moves it
  to the block's timestamp at `database.cpp:2866`), and the per-block passes run after that
  (`database.cpp:2361-2362` calls `account_recovery_processing()` then `expire_escrow_ratification()`).
  So in the block whose timestamp equals `ratification_deadline`, `escrow_approve` is still accepted,
  an escrow whose approval completes in that block is skipped by the expiry pass, and one still
  unapproved is refunded at the end of that block. The `>=` equality is met only when the previous
  block's timestamp equals the deadline, after that block's expiry pass has already refunded any
  escrow still unapproved.
- Dispute requires `head_block_time < escrow_expiration` (strict,
  `hive_evaluator_transfer.cpp:190`; the `escrow_transfer_operation` doc comment says "before or on",
  `hive_operations.hpp:230`) -> dispute window is `[full-approval, escrow_expiration)`.

### Release permission matrix (evaluator-only)
`validate()` permits `who ∈ {from, to, agent}` and `receiver ∈ {from, to}`
(`hive_operations.cpp:704-718`). The evaluator narrows it by state
(`hive_evaluator_transfer.cpp:218-243`):

| Escrow state | Who may release | Valid receiver |
|--------------|-----------------|----------------|
| Disputed | `agent` only | `from` or `to` |
| Not disputed, **not** expired, `who==from` | `from` | `to` only |
| Not disputed, **not** expired, `who==to` | `to` | `from` only |
| Not disputed, **expired** | `from` or `to` | `from` or `to` (either) |

`agent` can release **only** when disputed; otherwise the `who == from || who == to` assert
(`hive_evaluator_transfer.cpp:228`) rejects the agent even though `validate()` accepted it. Release
also requires `is_approved()` (`hive_evaluator_transfer.cpp:219`) and that each requested amount
is <= the escrow's balance (`hive_evaluator_transfer.cpp:214-215`).

### Fee accounting
- On create, `fee` is debited from `from` **in addition to** the transferred amounts and held in the
  escrow's `pending_fee` (`hive_evaluator_transfer.cpp:89-117`).
- On rejection/expiry, the fee is **returned to `from`** (since 1.28.8 both go through
  `remove_escrow`, `database_market.cpp:78`, called at `hive_evaluator_transfer.cpp:165` and
  `database_market.cpp:101`).
- On mutual approval, the fee is moved out of `pending_fee` and paid to `agent`
  (`hive_evaluator_transfer.cpp:167-178`; at 1.28.7 `pending_fee.amount` was set to 0), so it is not
  paid again. `escrow_release` never touches the fee.

### Counters and limits
- `pending_escrow_transfers` (`uint16_t`, `account_object.hpp:272`, "for now max is 255") is
  incremented on create (`hive_evaluator_transfer.cpp:118-121`) and decremented on reject/expire
  (`database_market.cpp:84-87`) and empty-release (`hive_evaluator_transfer.cpp:258-261`). Create is
  gated by `pending_escrow_transfers < HIVE_MAX_PENDING_TRANSFERS` (255, `protocol/config.hpp:236`;
  `hive_evaluator_transfer.cpp:85`). Decrements always pair with a removal, so underflow requires a
  pre-existing inconsistency.
- HF23 account clearing returns all of an account's escrow balances via `remove_pending_escrows`
  (`database.cpp:1591`, impl `database_market.cpp:105-116`) - same refund pattern as the expiry pass
  (since 1.28.8 the same `remove_escrow`) but keyed on `by_from_id` for one account, and **no**
  `escrow_rejected_operation` is pushed (`remove_escrow( escrow, false )`, `database_market.cpp:114`).

## Account-Recovery Lifecycle

### Three persistent objects
1. `owner_authority_history_object` (`account_object.hpp:484-516`) - snapshot of a previous owner
   authority + `last_valid_time`. Created by `update_owner_authority` **only when**
   `head_block_num() >= HIVE_OWNER_AUTH_HISTORY_TRACKING_START_BLOCK_NUM` (3186477 mainnet, 1
   testnet - `protocol/config.hpp:166`, `:88`; `database.cpp:1701-1712`).
2. `account_recovery_request_object` (`account_object.hpp:518-560`) - the agent's proposed
   `new_owner_authority` + `expires`. Indexed `by_account` and `by_expiration`.
3. `change_recovery_account_request_object` (`account_object.hpp:562-594`) - a pending recovery-agent
   change + `effective_on`. Indexed `by_account` and `by_effective_date`.

### `request_account_recovery` (agent, active auth)
`hive_evaluator_account.cpp:481-538`. Permission depends on whether the target has a recovery agent:
- Has one → the signing `recovery_account` must equal the target's stored recovery account
  (`:485-491`); a `wlog` is emitted if it is `temp`.
- None (id 0) → the `recovery_account` must be the **top-voted witness**, read live as
  `get_index<witness_index, by_vote_name>().begin()->owner` (`:492-495`). `by_vote_name` orders
  `votes` descending then `owner` ascending (`witness_objects_multiindex.hpp:32-38`), so `.begin()`
  is the single highest-voted witness, **re-evaluated at request time** (a vote shift changes who may
  request).

Three sub-paths keyed on the existing request and the op's `new_owner_authority.weight_threshold`
(the size check on the new owner authority: Key Discovery 3):
- **New** (no existing request, `hive_evaluator_account.cpp:508-521`): reject impossible/open
  authority, `verify_authority_accounts_exist`, create request expiring at
  `now + HIVE_ACCOUNT_RECOVERY_REQUEST_EXPIRATION_PERIOD` (1 day mainnet, `protocol/config.hpp:164`).
- **Cancel** (`weight_threshold == 0`): remove the request (`hive_evaluator_account.cpp:522-525`).
- **Change** (existing request, non-zero threshold): reject impossible authority, verify accounts,
  reset authority + expiry (`hive_evaluator_account.cpp:526-537`).

### `recover_account` (dual authority: new + recent)
`hive_evaluator_account.cpp:540-573`. Requires satisfying **both** `new_owner_authority` and
`recent_owner_authority` (`hive_operations.hpp:851-855` - the only enabled op whose `get_required_authorities`
always pushes two authorities; the disallowed `custom_binary` pushes its whole `required_auths` list,
`hive_operations.hpp:564`, `hive_evaluator.cpp:378`). Steps:
1. Rate-limit since `last_account_recovery` (Discovery 2; only when HF12 active,
   `hive_evaluator_account.cpp:544-545`).
2. A request must exist and its `new_owner_authority` must equal `o.new_owner_authority`
   (`hive_evaluator_account.cpp:550-551`).
3. `o.recent_owner_authority` must match some `owner_authority_history` row for the account
   (`hive_evaluator_account.cpp:553-564`) - i.e. an owner authority valid within the last 30 days
   (the history pruning window).
4. Remove the request, `update_owner_authority(account, new_owner_authority)`, set
   `last_account_recovery = head_block_time` and `block_last_account_recovery = current_timestamp`
   (`hive_evaluator_account.cpp:566-572`).

`block_last_account_recovery` is explicitly marked *"REMOVE - not used by consensus checks (only
API)"* (`account_object.hpp:206`); the consensus rate-limit reads `last_account_recovery` via
`get_last_account_recovery_time()`.

### `change_recovery_account` (owner auth, 30-day delay)
`hive_evaluator_account.cpp:575-601`. `new_recovery_account` must be an existing account (`:577`).
Three branches:
- **New request**: create, effective at `now + HIVE_OWNER_AUTH_RECOVERY_PERIOD` (30 days,
  `config.hpp:163`).
- **Change existing**: if the *current effective* recovery account `!= new`, reset the request's
  target and timer (`hive_evaluator_account.cpp:589-596`). (Comparison is against the **current**
  recovery account, not the pending request's target.)
- **Cancel**: if naming the *current* recovery account while a request exists, remove the request
  (`hive_evaluator_account.cpp:597-600`).

### Per-block cleanup: `account_recovery_processing()` then `expire_escrow_ratification()`
`database.cpp:1987-2030`, invoked from `_apply_block` at `database.cpp:2361-2362` (recovery first,
then escrow). Three loops:
1. Remove `account_recovery_request` rows past `expiration` (`by_expiration`).
2. Remove `owner_authority_history` rows where `last_valid_time + 30d < head_block_time`
   (`database.cpp:2003-2007`) - this is what bounds the "recent owner authority" recovery window to
   30 days.
3. Apply due `change_recovery_account_request` rows (`by_effective_date`): set the account's recovery
   account, emit `changed_recovery_account_operation`, remove the request (`:2010-2029`).

### Recovery-account assignment at creation
`create_account` free function (`hive_evaluator_account.cpp:130-154`):
- Pre-HF11: recovery account is **forced** to `"steem"` regardless of the passed value (`:139-142`).
- Post-HF11: if the would-be recovery account is `temp`, treat as **none** (nullptr → id 0,
  `hive_evaluator_account.cpp:134-138`).
- From HF11, mined accounts (`pow`/`pow2`) pass `recovery_account = nullptr` -> id 0 -> top-witness
  fallback; the comment at `hive_evaluator.cpp:422` (`pow`; `:555` for `pow2`) confirms "empty
  recovery account parameter means highest voted witness at time of recovery."

`lock_account` (`database.cpp:1400-1432`), run on the treasury account at HF21 and at the HF24
treasury rename (`database_hardfork.cpp:433`, `:534`), resets its recovery account to **self**
(`a.set_recovery_account(a)`) and removes any pending recovery/change requests
(`database.cpp:1419-1431`). The HF23 `clear_account` does not touch recovery state
(`database.cpp:1491-1667`).

## Preconditions / Side Effects / Postconditions (escrow)

| Op | Key preconditions (evaluator) | Side effects | Postcondition |
|----|-------------------------------|--------------|---------------|
| `escrow_transfer` | both deadlines `> now`; `pending_escrow_transfers < 255`; `from` balance ≥ amounts+fee | debit `from`; create escrow; `pending_escrow_transfers++` | PENDING escrow exists |
| `escrow_approve` | escrow exists; op `to`/`agent` match; `ratification_deadline >= now`; party not already approved | set approval flag; on reject refund+remove (since 1.28.8 via `remove_escrow`); on mutual approve move the fee out of `pending_fee` and pay it to `agent` | partial / ACTIVE / removed |
| `escrow_dispute` | `from` exists; escrow fully approved; `now < escrow_expiration`; not already disputed; `to`/`agent` match | set `disputed=true` | DISPUTED |
| `escrow_release` | escrow exists; amounts ≤ balances; `to`/`agent` match; `receiver ∈{from,to}`; approved; permission matrix | credit `receiver`; decrement balances; when empty remove + `pending_escrow_transfers--` | balances reduced / removed |

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| `escrow_transfer_evaluator` | `libraries/chain/hive_evaluator_transfer.cpp` | 75-124 | create escrow, debit from, counter++ |
| `escrow_approve_evaluator` | `libraries/chain/hive_evaluator_transfer.cpp` | 126-181 | approve/reject, fee payout on mutual approve |
| `escrow_dispute_evaluator` | `libraries/chain/hive_evaluator_transfer.cpp` | 183-202 | set disputed within window |
| `escrow_release_evaluator` | `libraries/chain/hive_evaluator_transfer.cpp` | 204-266 | permission matrix, balance decrement, removal |
| `remove_escrow` | `libraries/chain/database_market.cpp` | 58-89 | since 1.28.8: refund all to `from`, `escrow_rejected_operation` (not on the HF23 path), counter--, remove; used by rejection, expiry and the HF23 clear |
| `expire_escrow_ratification` | `libraries/chain/database_market.cpp` | 91-103 | per-block refund of unapproved expired escrows |
| `remove_pending_escrows` | `libraries/chain/database_market.cpp` | 105-116 | HF23 account-clear escrow refund |
| `escrow_object` | `libraries/chain/include/hive/chain/detail/state/escrow_object.hpp` | 14-92 | fields, getters/setters, `is_approved`, `check_on_remove`, FC_REFLECT |
| `escrow_index` | `.../detail/state/escrow_object_multiindex.hpp` | 8-29 | `by_from_id`, `by_ratification_deadline` |
| escrow `init` | `libraries/chain/hive_objects.cpp` | 47-52 | copies from/to/agent names |
| escrow `validate()` | `libraries/protocol/hive_operations.cpp` | 664-718 | stateless checks for all 4 escrow ops |
| escrow op structs | `libraries/protocol/include/hive/protocol/hive_operations.hpp` | 242-332 | active-auth(from/who), `escrow_id=30` default |
| `pending_escrow_transfers` | `.../detail/state/account_object.hpp` | 272 | uint16_t counter |
| `HIVE_MAX_PENDING_TRANSFERS` | `libraries/protocol/include/hive/protocol/config.hpp` | 236 | 255 |
| `request_account_recovery_evaluator` | `libraries/chain/hive_evaluator_account.cpp` | 481-538 | request lifecycle; HF29 authority-size switch (Key Discovery 3) |
| `recover_account_evaluator` | `libraries/chain/hive_evaluator_account.cpp` | 540-573 | rate-limit, history match (the dual authority comes from the operation, `hive_operations.hpp:851-855`) |
| `change_recovery_account_evaluator` | `libraries/chain/hive_evaluator_account.cpp` | 575-601 | 30-day delayed agent change |
| `account_recovery_processing` | `libraries/chain/database.cpp` | 1987-2030 | per-block request expiry, history pruning, change apply |
| per-block call order | `libraries/chain/database.cpp` | 2361-2362 | recovery then escrow |
| `update_owner_authority` | `libraries/chain/database.cpp` | 1701-1712 | history snapshot (gated on start block) |
| `lock_account` recovery reset | `libraries/chain/database.cpp` | 1419-1431 | treasury lock (HF21, HF24): set recovery to self, drop requests |
| recovery op structs | `libraries/protocol/include/hive/protocol/hive_operations.hpp` | 760-923 | auth requirements, doc comments |
| recovery `validate()` | `libraries/protocol/hive_operations.cpp` | 720-742 | stateless recovery checks |
| `owner_update_limit_mgr` | `libraries/chain/util/owner_update_limit_mgr.cpp` | 10-31 | 2-arg vs 4-arg check, message selection |
| recovery objects | `.../detail/state/account_object.hpp` | 484-594 | history + request + change-request objects |
| recovery indices | `.../detail/state/account_object_multiindex.hpp` | 50-163 | by_account / by_expiration / by_effective_date |
| `has_recovery_account` (id-0) | `.../detail/state/account_object.hpp` | 167-174 | `recovery_account != account_id_type()` |
| `miners` = id 0 | `libraries/chain/database_init.cpp` | 197 | first genesis account |
| top-witness fallback index | `.../detail/state/witness_objects_multiindex.hpp` | 32-38 | `by_vote_name` votes-desc, owner-asc |
| RC payer (recover) | `libraries/chain/rc/resource_user.cpp` | 22-24 | `account_to_recover` |
| RC subsidy predicate | `libraries/chain/rc/resource_count.cpp` | 534-545, 606-611 | only op, single-auth, <= 2 sig -> free |
| RC differential (recover) | `libraries/chain/rc/resource_count.cpp` | 89-98 | old owner-auth bytes ignored if subsidized |

## Cross-references to existing parts

- **Part 11 (validate-evaluate-gaps)** - *deepens / confirms.* Part 11's Key Discovery 5 and its
  gap-catalog row for `request_account_recovery` describe the HF29 authority-size switch as Key
  Discovery 3 does, and its gap catalog has an "evaluator-only" row for `escrow_transfer`. This zoom
  adds the **release permission matrix** and **time-boundary (strict vs non-strict)** detail that
  Part 11 summarizes only as "escrow deadlines" (section Division of Labor).
- **Part 04 (chain-evaluators)** — *complements.* Part 04 lists the recovery evaluators and the
  top-witness fallback (section request_account_recovery_evaluator); this zoom adds the
  **id-0/`miners` alias** and the rate-limit message/behavior mismatch (Discovery 2), neither of
  which Part 04 covers.
- **Part 05 (state-objects)** — *deepens.* Part 05 documents the `escrow_object` fields/indices and
  states removal triggers, but does not note that **approved/disputed escrows never auto-expire**
  (Discovery 1). Part 05's `recovery_account` row ("0 = top witness", section account_object) is
  the same fact this zoom traces to `miners`/id 0.
- **Part 08 (resource-credits)** - *complements.* Part 08 gives the `recover_account` differential
  usage (section RC Cost Calculation, Step 2), the subsidy conditions (Key Discovery 6) and the payer
  rule with its three overrides (Summary); this zoom adds that the `recover_account` override names
  the **payer = `account_to_recover`** (Discovery 6).
- **Part 02 (operations-catalog)** — *complements.* Confirms the `escrow_id=30` default, the
  dual-authority `recover_account`, and the ~24h request / 30-day owner-auth windows.
- **Part 09 (hardfork-history)** - *complements.* The HF23 `clear_account` -> `remove_pending_escrows`
  path is the escrow slice of the HF23 clear documented in Part 09 (section The HF23 Clear / HF24
  Restore Mechanism); the recovery reset of `lock_account` belongs to the treasury lock of HF21 and of
  the HF24 treasury rename (Part 09, sections HF21 and HF24). Part 09's section HF29 (Defined in
  1.28.8, Inactive on Mainnet) lists the switch of Key Discovery 3.

## Discrepancies and Potential Issues

1. **Comment vs behavior — `change_recovery_account` "can't clear" (Discovery 5).** The comment at
   `hive_evaluator_account.cpp:577-578` is contradicted by the id-0/`miners` alias. **Unverified
   empirically** — needs a testnet check.
2. **Message vs enforcement — `recover_account` rate limit (Discovery 2).** Post-HF26 the message
   says "twice an hour" but the enforced limit is once per hour (`hive_evaluator_account.cpp:544-545`
   + `owner_update_limit_mgr.cpp:10-12,28-31`). Cosmetic but real.
3. **No timeout for approved/disputed escrows (Discovery 1).** By design, a disputed escrow stays
   until the agent releases it and an approved one until `from` or `to` releases it; no timed or
   per-block process removes it (`database_market.cpp:94-97`).
4. **`request_account_recovery` authority size (Discovery 3).** Changed in 1.28.8: the size rule is
   the subject of the HF29 switch described in Key Discovery 3 (defined in 1.28.8, inactive on
   mainnet; `hive_evaluator_account.cpp:500-506`), which replaces the `FC_TODO` and its HF29 comment
   of the 1.28.7 code.
5. **`escrow_dispute` reads `from` but uses name-keyed lookup.** `_db.get_account(o.from)` at
   `hive_evaluator_transfer.cpp:187` only verifies existence; the escrow is found by
   `(o.from, o.escrow_id)`. Harmless but the account fetch result is discarded. Same pattern as
   `escrow_release`'s `from_account` which **is** used (for the counter decrement at
   `hive_evaluator_transfer.cpp:258-261`).
6. **`escrow_approve` "already approved" assert blocks self-reject but not counterparty-reject
   (Discovery 7).** Not a bug, but a non-obvious cancellation property.

## Open Questions

1. **Is the `change_recovery_account` → `"miners"` path actually reachable and does it re-enable the
   top-witness fallback?** Requires a testnet experiment (create account with a recovery agent,
   `change_recovery_account` to `miners`, wait 30 days / fast-forward, then attempt
   `request_account_recovery` and confirm the top-witness rule applies). Out of scope for static
   reading.
2. **Did any mainnet account ever actually carry `recovery_account == "miners"` (id 0) other than via
   genesis/mined defaults?** Needs an account-history / state scan, not answerable from the worktree.
3. **`witness_index` lives outside this area.** The exact tie-break and live-recompute behavior of
   `by_vote_name` for the no-recovery fallback would benefit from a consensus/witness-schedule zoom
   (Part 06 territory).
4. **HF29 plans for the escrow/recovery TODOs** (auth-size move to `validate`, escrow account
   names -> ids). *Partly answered by 1.28.8:* HF29 is defined in 1.28.8 code with five switches and
   is inactive on mainnet (`hardfork.d/1_29.hf:1-31`; Part 01, section HF29 (Defined in 1.28.8,
   Inactive on Mainnet)). The recovery authority-size rule is one of the switches
   (`hardfork.d/1_29.hf:24`; Key Discovery 3), and the 1.28.8 comment at
   `hive_evaluator_account.cpp:501` leaves moving the check to `validate()` until after HF29
   activation. The escrow name-to-id TODOs (`escrow_object.hpp:69-71`) are not part of HF29; no plan
   for them is visible in the source (Part 05, Open Question 1).
```
