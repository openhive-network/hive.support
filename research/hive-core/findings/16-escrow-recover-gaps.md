# Findings: escrow-recover-gaps

> Source pinned at hive-core `1584099c3054a97f02abfb4788b23f02eea98728` (release-adjacent to
> 1.28.7). Every `file:line` below is from that worktree. Where a fact could not be verified from
> the area's files it is called out explicitly.

## Summary

The four escrow operations and the account-recovery/change-recovery operations share a common
shape: stateless `validate()` checks the operation's internal consistency, while the evaluator
holds **all** the consensus-relevant rules (existence, balances, approval/dispute state, time
windows, permission matrices). This zoom maps the full escrow state machine, the recovery request
lifecycle, their once-per-block cleanup passes, and several subtle gaps: an **approved-or-disputed
escrow has no timeout** (funds can be locked indefinitely), the `recover_account` rate-limit
**enforces once-per-hour but emits the "twice an hour" message** post-HF26, the
`request_account_recovery` change-path **skips `validate_auth_size`** (documented `FC_TODO`, awaiting
HF29), and the "no recovery account → top witness" sentinel is **account id 0 = `miners`**, which
makes `change_recovery_account` to `"miners"` a back-door to the top-witness fallback that the
in-code comment claims is impossible.

## Key Discoveries

### 1. Escrow has two distinct removal triggers with different time semantics
- **What**: An **unapproved** escrow is auto-refunded after `ratification_deadline` by the
  per-block `expire_escrow_ratification()`. An **approved** escrow has **no** automatic cleanup —
  `escrow_expiration` only changes *who may release to whom*, never forces resolution. A disputed
  escrow likewise never times out. If the agent (disputed) or both parties (non-disputed) never act,
  the funds stay in the `escrow_object` forever.
- **Where**: `database_market.cpp:58-79` (`expire_escrow_ratification`, iterates
  `by_ratification_deadline` `lower_bound(false)` — only `is_approved()==false` rows);
  `hive_evaluator_transfer.cpp:198-258` (`escrow_release` — the only path that empties an approved
  escrow); `escrow_object_multiindex.hpp:19-26` (the deadline index keys on `is_approved` first).
- **Impact**: A grief/lock vector by design — an unresponsive agent in a disputed escrow leaves
  funds permanently locked. There is no consensus mechanism to recover them. Part 05 lists the
  removal triggers but does not call out the "approved escrows never expire" property.

### 2. `recover_account` rate-limit message/behavior mismatch after HF26
- **What**: `recover_account` calls the **2-argument** `owner_update_limit_mgr::check(head_block_time,
  last_account_recovery_time)`, which is the strict `now - last > HIVE_OWNER_UPDATE_LIMIT` (60 min)
  rule. But the error message is produced by `msg(has_hardfork(HIVE_HARDFORK_1_26_AUTH_UPDATE))`,
  which returns *"Owner authority can only be updated twice an hour."* post-HF26. So after HF26 the
  enforced limit is still **once per hour** while the message advertises **twice per hour**.
- **Where**: `hive_evaluator_account.cpp:558-559`; `owner_update_limit_mgr.cpp:10-12` (2-arg check),
  `:28-31` (`msg` selects `message_hf26`). Contrast `account_update`/`account_update2` which use the
  **3-arg** check (`previous_owner_update`, `last_owner_update`) that genuinely doubles the rate
  post-HF26 (`hive_evaluator_account.cpp:313-315,370-372`).
- **Impact**: Recovery is asymmetric with ordinary owner-auth updates: HF26 relaxed `account_update`
  to twice/hour but **not** `recover_account`. The mismatched message is a minor correctness wart
  (user sees a limit that does not match reality).

### 3. `request_account_recovery` "change" path bypasses `validate_auth_size`
- **What**: When a recovery request already exists and is being **edited** (non-zero weight
  threshold), the evaluator calls `verify_authority_accounts_exist` but **not** `validate_auth_size`.
  The **new-request** path calls both. An `FC_TODO` documents that this lets an edit introduce an
  authority wider than `HIVE_MAX_AUTHORITY_MEMBERSHIP`, which can then also be used when cancelling.
- **Where**: `hive_evaluator_account.cpp:518-551`. New path: `validate_auth_size` at `:528`. Change
  path (`:540-551`): no size check. The `FC_TODO` at `:518-521` states a HF29 fix is needed and the
  check should move to `validate`.
- **Impact**: Latent state-bloat / consensus-divergence risk; already catalogued in Part 11 but
  confirmed here against the exact lines. Stateless `validate()`
  (`hive_operations.cpp:720-725`) only runs `new_owner_authority.validate()` (structure, not size),
  so nothing else catches it.

### 4. "No recovery account" sentinel is account id 0 = `miners`
- **What**: `has_recovery_account()` is defined as `recovery_account != account_id_type()`, i.e. the
  stored `account_id_type` is not 0. The first account created at genesis is `HIVE_MINER_ACCOUNT`
  (`"miners"`), so it holds **id 0**. Consequently an account whose recovery account is literally
  `miners` is indistinguishable from one with *no* recovery account, and the recovery path falls back
  to "top-voted witness must recover."
- **Where**: `account_object.hpp:152` (`has_recovery_account`), `:154` (`get_recovery_account`),
  `:156-159` (`set_recovery_account` stores `new_recovery_account.get_id()`);
  `database_init.cpp:195` (`miners` created first → id 0);
  `hive_evaluator_account.cpp:510-513` (no-recovery → top-witness branch in
  `request_account_recovery`).
- **Impact**: See Discovery 5 — the ABW comment in `change_recovery_account` says you *cannot* clear
  the recovery agent back to "top witness," but naming `"miners"` does exactly that via the id-0
  alias.

### 5. `change_recovery_account` to `"miners"` contradicts its own "can't clear" comment
- **What**: The evaluator comment at `hive_evaluator_account.cpp:591-592` states *"can't clear
  existing recovery agent to set it to top voted witness."* That is true for the *empty-string* case
  (the op validates `new_recovery_account` as a real account name). But `"miners"` **is** a real
  account; setting it makes `recovery_account == id 0`, which `has_recovery_account()` reports as
  false, re-enabling the top-witness fallback. The change is applied by
  `account_recovery_processing()` via `set_recovery_account(get_account(...))`.
- **Where**: comment at `hive_evaluator_account.cpp:591-592`; application at
  `database.cpp:1990-2003` (`account_recovery_processing` change-request loop, calls
  `a.set_recovery_account( new_recovery_account )`).
- **Impact**: A behavioral edge that the comment denies. **Not empirically tested** in this zoom —
  flagged as a discrepancy to verify on testnet (does `change_recovery_account` with
  `new_recovery_account = "miners"` succeed, and does the resulting account then route recovery to
  the top witness?). Whether intended or an oversight is unclear from the code alone.

### 6. RC: recover_account is paid by the *victim* and conditionally free
- **What**: The RC "user" (payer) for `recover_account` is `account_to_recover`, **not** the
  recovery agent. The op is **subsidized (free)** iff the new owner authority has exactly one total
  entry (single key or single account-auth) and the tx carries ≤2 signatures; multisig recoveries
  are **not** subsidized. `request_account_recovery` has no special RC handling, so its payer is the
  first required active authority = `recovery_account` (the agent).
- **Where**: `rc/resource_user.cpp:22-24` (payer = `account_to_recover`);
  `rc/resource_count.cpp:534-545` (`subsidized_op = 1 == (key_auths + account_auths)`,
  `subsidized_signatures = 2`), `:606-611` (single-subsidized-op tx → zero cost);
  `rc/resource_count.cpp:89-98` (differential: old owner-auth bytes ignored when subsidized).
- **Impact**: A compromised account with **no RC** can still be recovered (single-key replacement is
  free), but the design deliberately denies the subsidy to multisig recoveries to avoid funding the
  setup of new multisig from a stolen account. Part 08 mentions the differential usage; this zoom
  adds the payer identity and the exact subsidy predicate.

### 7. Either escrow party can unilaterally cancel before ratifying
- **What**: In `escrow_approve`, `reject_escrow = !o.approve`. The "already approved" assert fires
  for the *acting* party, but rejection refunds **everything to `from`** and deletes the escrow
  regardless of the *other* party's approval state. So after `to` approves, the `agent` can still
  reject and kill the escrow (and vice-versa) — until a party has itself approved, it can reject.
- **Where**: `hive_evaluator_transfer.cpp:119-160`. Reject branch (`:146-160`) refunds
  `hive_balance + hbd_balance + fee` to `o.from`, emits `escrow_rejected_operation`, decrements
  `pending_escrow_transfers`, removes the object.
- **Impact**: The approval handshake is *cancellable* by either counterparty up to the moment they
  approve; only mutual approval (`:161`) locks the escrow into the active state. Worth documenting
  for anyone modelling escrow as "2-of-2 commit."

## Escrow State Machine

### Objects and fields
`escrow_object` (`escrow_object.hpp:14-56`) holds three **account names** (`from`/`to`/`agent` —
explicit TODO that id-based storage would slow `(from, escrow_id)` lookups, `:40-42`), the two
deadlines, `hbd_balance`/`hive_balance`, a single `pending_fee` (`asset`, can be HIVE *or* HBD,
`:47`), and three flags `to_approved`/`agent_approved`/`disputed` (TODO: pack into a bitfield,
`:48-50`). `is_approved() == to_approved && agent_approved` (`:37`). Init copies the three names
(`hive_objects.cpp:43-48`).

Indices (`escrow_object_multiindex.hpp`):
- `by_from_id` = `(from, escrow_id)` — how every evaluator finds an escrow (`get_escrow`,
  `database.cpp:1342-1351`).
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
        pay fee to agent, pending_fee=0   <-- escrow_approve (:161-172)
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
- Approve: allowed while `ratification_deadline >= head_block_time` (**non-strict**, `:117`).
- Expire pass removes when `ratification_deadline <= head_block_time` (**non-strict**,
  `database_market.cpp:62`).
- At the exact tick `head_block_time == ratification_deadline`, an `escrow_approve` transaction in
  that block is processed during `apply_transaction` (allowed, `>=`) **before** the per-block
  `expire_escrow_ratification()` runs at end-of-block (`database.cpp:2347-2348` calls
  `account_recovery_processing()` then `expire_escrow_ratification()` after all transactions). So a
  same-tick approval wins the race and the now-approved escrow is skipped by the expiry pass.
- Dispute requires `head_block_time < escrow_expiration` (strict, `:184`) → dispute window is
  `[full-approval, escrow_expiration)`.

### Release permission matrix (evaluator-only)
`validate()` permits `who ∈ {from, to, agent}` and `receiver ∈ {from, to}`
(`hive_operations.cpp:704-718`). The evaluator narrows it by state
(`hive_evaluator_transfer.cpp:212-237`):

| Escrow state | Who may release | Valid receiver |
|--------------|-----------------|----------------|
| Disputed | `agent` only | `from` or `to` |
| Not disputed, **not** expired, `who==from` | `from` | `to` only |
| Not disputed, **not** expired, `who==to` | `to` | `from` only |
| Not disputed, **expired** | `from` or `to` | `from` or `to` (either) |

`agent` can release **only** when disputed; otherwise the `who ∈ {from,to}` assert (`:222`) rejects
the agent even though `validate()` accepted it. Release also requires `is_approved()` (`:213`) and
that the requested amount ≤ escrow balance (`:208-209`).

### Fee accounting
- On create, `fee` is debited from `from` **in addition to** the transferred amounts
  (`hive_evaluator_transfer.cpp:89-97`).
- On rejection/expiry, the fee is **returned to `from`** (`:150`, `database_market.cpp:70`).
- On mutual approval, the fee is paid to `agent` and `pending_fee.amount` is zeroed (`:163-171`) so
  it is not paid again. `escrow_release` never touches the fee.

### Counters and limits
- `pending_escrow_transfers` (`uint16_t`, `account_object.hpp:247`, "for now max is 255") is
  incremented on create (`:100-103`) and decremented on reject/expire/empty-release. Create is
  gated by `pending_escrow_transfers < HIVE_MAX_PENDING_TRANSFERS` (255, `config.hpp:240`;
  `hive_evaluator_transfer.cpp:85`). Decrements always pair with a removal, so underflow requires a
  pre-existing inconsistency.
- HF23 account clearing returns all of an account's escrow balances via `remove_pending_escrows`
  (`database.cpp:1577`, impl `database_market.cpp:81-103`) — same refund pattern as the expiry pass
  but keyed on `by_from_id` for one account, and **no** `escrow_rejected_operation` is pushed.

## Account-Recovery Lifecycle

### Three persistent objects
1. `owner_authority_history_object` (`account_object.hpp:427-452`) — snapshot of a previous owner
   authority + `last_valid_time`. Created by `update_owner_authority` **only when**
   `head_block_num() >= HIVE_OWNER_AUTH_HISTORY_TRACKING_START_BLOCK_NUM` (3186477 mainnet, 1
   testnet — `config.hpp:170`, `:89`; `database.cpp:1678-1690`).
2. `account_recovery_request_object` (`account_object.hpp:454-496`) — the agent's proposed
   `new_owner_authority` + `expires`. Indexed `by_account` and `by_expiration`.
3. `change_recovery_account_request_object` (`account_object.hpp:498-529`) — a pending recovery-agent
   change + `effective_on`. Indexed `by_account` and `by_effective_date`.

### `request_account_recovery` (agent, active auth)
`hive_evaluator_account.cpp:499-552`. Permission depends on whether the target has a recovery agent:
- Has one → the signing `recovery_account` must equal the target's stored recovery account
  (`:503-509`); a `wlog` is emitted if it is `temp`.
- None (id 0) → the `recovery_account` must be the **top-voted witness**, read live as
  `get_index<witness_index, by_vote_name>().begin()->owner` (`:510-513`). `by_vote_name` orders
  `votes` descending then `owner` ascending (`witness_objects_multiindex.hpp:32-38`), so `.begin()`
  is the single highest-voted witness, **re-evaluated at request time** (a vote shift changes who may
  request).

Three sub-paths keyed on the existing request and the op's `new_owner_authority.weight_threshold`:
- **New** (no existing request): reject impossible/open authority, `validate_auth_size`,
  `verify_authority_accounts_exist`, create request expiring at
  `now + HIVE_ACCOUNT_RECOVERY_REQUEST_EXPIRATION_PERIOD` (1 day mainnet, `config.hpp:168`).
- **Cancel** (`weight_threshold == 0`): remove the request (`:536-539`).
- **Change** (existing request, non-zero threshold): reject impossible authority, verify accounts,
  reset authority + expiry — **but no `validate_auth_size`** (Discovery 3).

### `recover_account` (dual authority: new + recent)
`hive_evaluator_account.cpp:554-587`. Requires satisfying **both** `new_owner_authority` and
`recent_owner_authority` (`hive_operations.hpp:906-910` — the only op using `get_required_authorities`
to push two authorities). Steps:
1. Rate-limit since `last_account_recovery` (Discovery 2; only when HF12 active, `:558-559`).
2. A request must exist and its `new_owner_authority` must equal `o.new_owner_authority` (`:564-565`).
3. `o.recent_owner_authority` must match some `owner_authority_history` row for the account
   (`:567-578`) — i.e. an owner authority valid within the last 30 days (the history pruning window).
4. Remove the request, `update_owner_authority(account, new_owner_authority)`, set
   `last_account_recovery = head_block_time` and `block_last_account_recovery = current_timestamp`
   (`:580-586`).

`block_last_account_recovery` is explicitly marked *"REMOVE - not used by consensus checks (only
API)"* (`account_object.hpp:182`); the consensus rate-limit reads `last_account_recovery` via
`get_last_account_recovery_time()`.

### `change_recovery_account` (owner auth, 30-day delay)
`hive_evaluator_account.cpp:589-615`. `new_recovery_account` must be an existing account (`:591`).
Three branches:
- **New request**: create, effective at `now + HIVE_OWNER_AUTH_RECOVERY_PERIOD` (30 days,
  `config.hpp:167`).
- **Change existing**: if the *current effective* recovery account `!= new`, reset the request's
  target and timer (`:603-610`). (Comparison is against the **current** recovery account, not the
  pending request's target.)
- **Cancel**: if naming the *current* recovery account while a request exists, remove the request
  (`:611-614`).

### Per-block cleanup: `account_recovery_processing()` then `expire_escrow_ratification()`
`database.cpp:1962-2006`, invoked from `_apply_block` at `database.cpp:2347-2348` (recovery first,
then escrow). Three loops:
1. Remove `account_recovery_request` rows past `expiration` (`by_expiration`).
2. Remove `owner_authority_history` rows where `last_valid_time + 30d < head_block_time`
   (`:1978-1982`) — this is what bounds the "recent owner authority" recovery window to 30 days.
3. Apply due `change_recovery_account_request` rows (`by_effective_date`): set the account's recovery
   account, emit `changed_recovery_account_operation`, remove the request (`:1985-2004`).

### Recovery-account assignment at creation
`create_account` free function (`hive_evaluator_account.cpp:130-154`):
- Pre-HF11: recovery account is **forced** to `"steem"` regardless of the passed value (`:139-142`).
- Post-HF11: if the would-be recovery account is `temp`, treat as **none** (nullptr → id 0,
  `:134-138`).
- Mined accounts (`pow`/`pow2`) pass `recovery_account = nullptr` → id 0 → top-witness fallback;
  the comment at `hive_evaluator.cpp:421` confirms "empty recovery account parameter means highest
  voted witness at time of recovery."

`clear_account` (HF23) resets the recovery account to **self** (`a.set_recovery_account(a)`) and
removes any pending recovery/change requests (`database.cpp:1407-1419`).

## Preconditions / Side Effects / Postconditions (escrow)

| Op | Key preconditions (evaluator) | Side effects | Postcondition |
|----|-------------------------------|--------------|---------------|
| `escrow_transfer` | both deadlines `> now`; `pending_escrow_transfers < 255`; `from` balance ≥ amounts+fee | debit `from`; create escrow; `pending_escrow_transfers++` | PENDING escrow exists |
| `escrow_approve` | escrow exists; op `to`/`agent` match; `ratification_deadline >= now`; party not already approved | set approval flag; on reject refund+remove; on mutual approve pay agent fee, zero `pending_fee` | partial / ACTIVE / removed |
| `escrow_dispute` | `from` exists; escrow fully approved; `now < escrow_expiration`; not already disputed; `to`/`agent` match | set `disputed=true` | DISPUTED |
| `escrow_release` | escrow exists; amounts ≤ balances; `to`/`agent` match; `receiver ∈{from,to}`; approved; permission matrix | credit `receiver`; decrement balances; when empty remove + `pending_escrow_transfers--` | balances reduced / removed |

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| `escrow_transfer_evaluator` | `libraries/chain/hive_evaluator_transfer.cpp` | 75-106 | create escrow, debit from, counter++ |
| `escrow_approve_evaluator` | `libraries/chain/hive_evaluator_transfer.cpp` | 108-175 | approve/reject, fee payout on mutual approve |
| `escrow_dispute_evaluator` | `libraries/chain/hive_evaluator_transfer.cpp` | 177-196 | set disputed within window |
| `escrow_release_evaluator` | `libraries/chain/hive_evaluator_transfer.cpp` | 198-258 | permission matrix, balance decrement, removal |
| `expire_escrow_ratification` | `libraries/chain/database_market.cpp` | 58-79 | per-block refund of unapproved expired escrows |
| `remove_pending_escrows` | `libraries/chain/database_market.cpp` | 81-103 | HF23 account-clear escrow refund |
| `escrow_object` | `libraries/chain/include/hive/chain/detail/state/escrow_object.hpp` | 14-64 | fields, `is_approved`, FC_REFLECT |
| `escrow_index` | `.../detail/state/escrow_object_multiindex.hpp` | 8-29 | `by_from_id`, `by_ratification_deadline` |
| escrow `init` | `libraries/chain/hive_objects.cpp` | 43-48 | copies from/to/agent names |
| escrow `validate()` | `libraries/protocol/hive_operations.cpp` | 664-718 | stateless checks for all 4 escrow ops |
| escrow op structs | `libraries/protocol/include/hive/protocol/hive_operations.hpp` | 242-330 | active-auth(from/who), `escrow_id=30` default |
| `pending_escrow_transfers` | `.../detail/state/account_object.hpp` | 247 | uint16_t counter |
| `HIVE_MAX_PENDING_TRANSFERS` | `libraries/protocol/include/hive/protocol/config.hpp` | 240 | 255 |
| `request_account_recovery_evaluator` | `libraries/chain/hive_evaluator_account.cpp` | 499-552 | request lifecycle; auth-size gap |
| `recover_account_evaluator` | `libraries/chain/hive_evaluator_account.cpp` | 554-587 | dual-auth, rate-limit, history match |
| `change_recovery_account_evaluator` | `libraries/chain/hive_evaluator_account.cpp` | 589-615 | 30-day delayed agent change |
| `account_recovery_processing` | `libraries/chain/database.cpp` | 1962-2006 | per-block request expiry + change apply |
| per-block call order | `libraries/chain/database.cpp` | 2344-2345 | recovery then escrow |
| `update_owner_authority` | `libraries/chain/database.cpp` | 1678-1690 | history snapshot (gated on start block) |
| `clear_account` recovery reset | `libraries/chain/database.cpp` | 1407-1419 | set recovery to self, drop requests |
| recovery op structs | `libraries/protocol/include/hive/protocol/hive_operations.hpp` | 787-940 | auth requirements, doc comments |
| recovery `validate()` | `libraries/protocol/hive_operations.cpp` | 720-742 | stateless recovery checks |
| `owner_update_limit_mgr` | `libraries/chain/util/owner_update_limit_mgr.cpp` | 10-31 | 2-arg vs 3-arg check, message selection |
| recovery objects | `.../detail/state/account_object.hpp` | 427-529 | history + request + change-request objects |
| recovery indices | `.../detail/state/account_object_multiindex.hpp` | 50-163 | by_account / by_expiration / by_effective_date |
| `has_recovery_account` (id-0) | `.../detail/state/account_object.hpp` | 152-159 | `recovery_account != account_id_type()` |
| `miners` = id 0 | `libraries/chain/database_init.cpp` | 195 | first genesis account |
| top-witness fallback index | `.../detail/state/witness_objects_multiindex.hpp` | 32-38 | `by_vote_name` votes-desc, owner-asc |
| RC payer (recover) | `libraries/chain/rc/resource_user.cpp` | 22-24 | `account_to_recover` |
| RC subsidy predicate | `libraries/chain/rc/resource_count.cpp` | 534-545, 606-611 | single-auth + ≤2 sig → free |
| RC differential (recover) | `libraries/chain/rc/resource_count.cpp` | 89-98 | old owner-auth bytes ignored if subsidized |

## Cross-references to existing parts

- **Part 11 (validate-evaluate-gaps)** — *deepens / confirms.* Part 11's gap table already lists the
  `request_account_recovery` change-path auth-size bypass (Discovery 3) and the escrow "evaluator-only"
  rows. This zoom verifies those against exact lines and adds the **release permission matrix** and
  **time-boundary (strict vs non-strict)** detail that Part 11 summarizes only as "deadlines."
- **Part 04 (chain-evaluators)** — *complements.* Part 04 lists the recovery evaluators and the
  top-witness fallback (`04-chain-evaluators.md:1321-1328`); this zoom adds the **id-0/`miners` alias**
  and the rate-limit message/behavior mismatch (Discovery 2), neither of which Part 04 covers.
- **Part 05 (state-objects)** — *deepens.* Part 05 documents the `escrow_object` fields/indices and
  states removal triggers, but does not note that **approved/disputed escrows never auto-expire**
  (Discovery 1). Part 05's `recovery_account` row ("0 = top witness", `05-state-objects.md:184`) is
  the same fact this zoom traces to `miners`/id 0.
- **Part 08 (resource-credits)** — *complements.* Part 08 notes the recover_account differential
  usage; this zoom adds the **payer = `account_to_recover`** and the exact subsidy predicate
  (Discovery 6).
- **Part 02 (operations-catalog)** — *complements.* Confirms the `escrow_id=30` default, the
  dual-authority `recover_account`, and the ~24h request / 30-day owner-auth windows.
- **Part 09 (hardfork-history)** — *complements.* The HF23 `clear_account` → `remove_pending_escrows`
  and recovery-request removal path is the escrow/recovery slice of the HF23 clear documented in
  Part 09.

## Discrepancies and Potential Issues

1. **Comment vs behavior — `change_recovery_account` "can't clear" (Discovery 5).** The comment at
   `hive_evaluator_account.cpp:591-592` is contradicted by the id-0/`miners` alias. **Unverified
   empirically** — needs a testnet check.
2. **Message vs enforcement — `recover_account` rate limit (Discovery 2).** Post-HF26 the message
   says "twice an hour" but the enforced limit is once per hour (`hive_evaluator_account.cpp:558-559`
   + `owner_update_limit_mgr.cpp:10-12,28-31`). Cosmetic but real.
3. **No timeout for approved/disputed escrows (Discovery 1).** Funds can be locked indefinitely if an
   agent (disputed) or both parties (active) never act. By design, but a documented lock vector.
4. **Auth-size bypass on recovery-request edit (Discovery 3).** Already flagged by the in-code
   `FC_TODO`; awaiting HF29. Confirmed at `hive_evaluator_account.cpp:518-551`.
5. **`escrow_dispute` reads `from` but uses name-keyed lookup.** `_db.get_account(o.from)` at
   `:181` only verifies existence; the escrow is found by `(o.from, o.escrow_id)`. Harmless but the
   account fetch result is discarded. Same pattern as `escrow_release`'s `from_account` which **is**
   used (for the counter decrement at `:250`).
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
4. **HF29 plans for the escrow/recovery `FC_TODO`s** (auth-size move to `validate`, escrow account
   names → ids) are referenced in comments but the HF29 definition/timing is not in these files —
   candidate for a hardfork-roadmap expand.
```
