# Hivemind Part 08 - L1 Consistency Cross-Check (hivemind vs hive-core)

**Anchors:** hivemind `1.28.6` (`cab9e328bf`, worktree
`workspace/hivemind/cab9e328bf/`) cross-checked against hive-core `1.28.7`
(`1584099c3`, worktree `workspace/hive-core/1584099c30/`; the delta vs the
1.28.6 protocol hivemind pairs with is a 6-file maintenance patch that touches
none of the code cited here - see `research/hive-core/verification.md`). HAF
`1.28.6` (`workspace/haf/222c848355/`) consulted where L1 semantics live in HAF.

**Scope:** hivemind is an L2 that RE-DERIVES protocol semantics instead of
reading hived state. Every re-derivation embeds an assumption about how Hive
works. This part enumerates those assumptions and verifies each against
hive-core source, classifying:

- **CONSISTENT** - verified match with L1;
- **LEGACY-DELIBERATE** - faithful port of old hivemind/condenser behavior
  that knowingly deviates from L1 precision;
- **GAP** - a real inconsistency (wrong or missing relative to L1);
- **APPROXIMATION** - close-enough model with bounded drift.

Citations: hivemind paths as in parts 01-07; hive-core paths prefixed `core:`.

---

## Summary

The cross-check found **no false L1 assumption in hivemind's payout, vote,
delete, or hardfork-constant logic** - the subtle constants (HF1 block 905693
rshares scaling, HF17 block 10629455, cumulative pre-HF19 reward vops,
comment_payout_update emission rules) all check out exactly. It found **one
genuine data gap** (accounts created by hardfork code - the DHF treasuries -
never enter `hive_accounts`), **one dead L2 flag** (`is_declined` has no
producer), and a set of **deliberate legacy deviations** worth knowing:
active-auth custom_jsons are invisible to hivemind, `author_payout_value`
silently includes the beneficiary cut, and post timestamps run 3 s behind
their blocks.

---

## Key Discoveries

### 1. GAP: hardfork-created accounts (the treasuries) never enter hive_accounts
- **What**: hivemind creates accounts only from ops 9/14/23/30/41
  (`massive_sync.sql:215-283`). But L1 also creates accounts in hardfork code:
  `steem.dao` at HF21 and `hive.fund` at HF24
  (`core:libraries/chain/database_hardfork.cpp:435,536` - each with an
  `account_created_operation`, vop id 80, which "covers all account creation
  methods" per the hive-core KB `reference/operations.md:431`). Hivemind does
  not stage vop 80, and only the 4 genesis accounts are hand-seeded
  (`hive/db/schema.py:63-67`), so both treasury accounts are absent from
  `hivemind_app.hive_accounts`.
- **Mainnet correction (empirical, 2026-08-02)**: on the REAL chain this gap
  is neutralized by historical accident. Both names were registered as
  ORDINARY accounts months before their hardforks - `steem.dao` created
  2019-02-11 (HF21: 2019-08-27), `hive.fund` created 2020-03-18 (HF24:
  2020-10-06) per `condenser_api.get_accounts` - so they entered history via
  regular creation ops that hivemind ingests; the hardfork code found them
  existing and only emptied their authorities (both show keyless owner/active
  and self-recovery). Production `bridge.get_profile` works for both
  (steem.dao: 73 followers, hive.fund: 83 - proving follows of them work
  too).
- **What remains true**: hivemind ignores vop 80, so the gap is LATENT: any
  future hardfork-created account whose name was not pre-registered, and any
  from-scratch chain (testnet/mirrornet) where the treasury names are free at
  HF time, produces accounts that exist on L1 but not in `hive_accounts`
  (mention join drops, follow resolution drops, get_profile errors).
- **Impact**: none observed on mainnet today; robustness/portability issue
  only. Fix shape if desired upstream: stage vop 80.

### 2. CONSISTENT: the pre-905693 rshares x1e6 scaling IS the HF1 vesting split
- **What**: hivemind multiplies `effective_comment_vote.rshares` by 1,000,000
  for `block_num < 905693` (`massive_sync.sql:374-377`). hive-core KB
  `reference/hardforks.md:11`: HF1 activated at block **905,693** and its
  payload was the **vesting share split (all VESTS x1,000,000)**. Pre-HF1
  rshares derive from unsplit VESTS, so they are 1e6 smaller; hivemind
  normalizes the whole history to post-split scale.
- **Impact**: the magic constant is exactly right, and now has its L1
  explanation on record. Any re-derivation of trending/vote data from raw
  vops must replicate it.

### 3. CONSISTENT: safe-cashout block 10629455 == HF17, and the 7-day rule holds
- **What**: `Blocks.set_end_of_sync_lib` treats posts older than LIB - 201600
  blocks as certainly-paid only past block 10629455, "posts created before
  HF17 could stay unpaid forever" (`hive/indexer/blocks.py:132-143`).
  hive-core KB `reference/hardforks.md:27`: HF17 = block **10,629,455**
  (2017-03-30), the reward-fund rework that unified cashout to the single
  7-day window (`reference/economics.md`). Exact match, correct semantics on
  both sides of the boundary.

### 4. CONSISTENT (with one misnamed L1 field): payout mirroring matches vop emission
- **What**: at emission (`core:libraries/chain/database_comment.cpp:290-317`),
  `comment_reward_operation` is filled with: vop `payout` = the TOTAL claimed
  reward in HBD; **`total_payout_value` = the AUTHOR-ONLY portion** (HBD +
  HIVE + vesting parts converted to HBD - despite the "total" name; struct
  comments at `core:libraries/protocol/include/hive/protocol/hive_virtual_operations.hpp:88-93`);
  `curator_payout_value` and `beneficiary_payout_value` separate; and
  pre-HF19 all three value fields are CUMULATIVE across cashouts
  (`add_payout_values` at `core:database_comment.cpp:306-315`).
  Hivemind (part 04): `payout = total + curator + beneficiary` reconstructs
  the vop's total ✓; last-writer-wins per batch is correct precisely BECAUSE
  the pre-HF19 fields are cumulative ✓; `author_rewards` (per-cashout, HIVE
  satoshis) is accumulated, matching its non-cumulative nature ✓.
- **Impact**: a re-derivation minefield navigated correctly; documented here
  because the field naming invites the opposite (wrong) reading.

### 5. LEGACY-DELIBERATE: `author_payout_value` includes the beneficiary cut
- **What**: the bridge post object computes
  `author_payout_value = payout - curator_payout_value`
  (`postgrest/utilities/create_bridge_post_object.sql:104-115`); the condenser
  object has no `author_payout_value` field and writes the same difference into
  `total_payout_value` (`create_condenser_post_object.sql:67-107`, assignments at
  `:75` and `:106`). Since `payout` = author +
  curator + beneficiary (Discovery 4), the result = author + beneficiary -
  beneficiary rewards are presented as author payout. This mirrors old
  hivemind/condenser exactly (same subtraction).
- **Impact**: not a bug to fix silently (API compatibility), but an L1
  imprecision every consumer comparing against `author_reward_operation`
  values will hit on posts with beneficiaries.

### 6. LEGACY-DELIBERATE: active-auth custom_jsons are invisible to hivemind
- **What**: L1 accepts custom_json with active auths, posting auths, or any
  mix (>= 1 total; `core:libraries/protocol/hive_operations.cpp:421-427`).
  Every hivemind custom_json consumer - follows
  (`hafapp_api.sql:108-115`), reblogs (`massive_sync.sql:533-539`),
  setLastRead (`massive_sync.sql:700-707`), community ops
  (`massive_sync.sql:2151-2157`) - requires EXACTLY one posting auth and zero
  active auths, silently skipping everything else.
- **Impact**: a follow/reblog/community op signed with an active key is valid
  on-chain, charged RC, included in blocks - and has no social effect. Same
  as old hivemind (compat), but an L1-capability mismatch integrators should
  know: always broadcast social custom_jsons with posting auth.

### 7. CONSISTENT (security): actor identity is enforced against the auth
- **What**: follows require `follower == required_posting_auths[0]`
  (`hafapp_api.sql:165-168`), reblogs require `account == auth`
  (`massive_sync.sql:571-576`), community ops resolve the ACTOR from the auth
  account, not from payload fields (`massive_sync.sql:1793`).
- **Impact**: payload spoofing (naming someone else as follower/account) is
  neutralized - consistent with L1's authorization model even though L1 never
  interprets the payloads.

### 8. CONSISTENT: "empty metadata = no change" matches the canonical L1-side rule
- **What**: hived consensus no longer stores account metadata at 1.28 (no
  `json_metadata` handling in `core:libraries/chain/hive_evaluator_account.cpp`'s
  account_update path) - the ecosystem-canonical implementation is HAF's
  metadata state provider, which takes the last NON-EMPTY value per field
  (`haf:src/hive_fork_manager/state_providers/metadata.sql:120-137`).
  Hivemind implements the identical rule with per-field last-non-empty
  aggregation (`massive_sync.sql:628-679`). (Hivemind's in-code reference to
  "metadata_plugin.cpp" is a stale pointer to old steemd, but the rule it
  describes is right.)

### 9. CONSISTENT: genesis epoch and genesis accounts; one cosmetic drift
- **What**: `hive_genesis_time()` returns 2016-03-24T16:00:00
  (`utility_functions.sql:101-110`) == `HIVE_GENESIS_TIME` 1458835200
  (`core:libraries/protocol/include/hive/protocol/config.hpp:150`) - the
  notification snowflake epoch is exact. The 4 seeded system accounts
  (miners/null/temp/initminer, `hive/db/schema.py:63-67`) are exactly L1's
  genesis set (`config.hpp:219,443-447`; genesis emits `account_created` for
  each, `core:libraries/chain/database.cpp:2373-2399`).
- **Cosmetic**: hivemind seeds their `created_at` as 16:05:00 (block-1 time)
  while L1 creates them at genesis 16:00:00 - a 5-minute display drift on 4
  accounts.

### 10. CONSISTENT: comment_payout_update semantics exactly match emission rules
- **What**: hivemind treats CPU (op 61) as "final - is_paidout, cashout
  'infinity', zero pending" (part 04). L1 emits CPU at cashout only
  `if( has_hardfork( HIVE_HARDFORK_0_17__769 ) || payout_time == maximum() )`
  (`core:libraries/chain/database_comment.cpp:361-363`) - i.e. post-HF17
  always at the (single) final cashout, pre-HF17 only when NO further cashout
  is scheduled. Intermediate pre-HF17 cashouts emit comment_reward without
  CPU, and hivemind correspondingly zeroes pending without marking paidout.
- **Impact**: the multi-cashout era is modeled correctly - a place where a
  "CPU fires at every payout" assumption would have corrupted pre-2017 state.

### 11. GAP (vestigial): `is_declined` was never wired - draft-schema residue
- **What**: `hive_posts.is_declined` (`schema/create_tables.sql:44`) has no
  producer and no consumer in the entire tree - the comment_options handler
  (`massive_sync.sql:1212-1248`) does not derive it from
  `max_accepted_payout == 0.000 HBD` (the L1 payout-decline mechanism,
  hive-core KB `reference/operations.md` comment_options). History (verified
  by grepping tags 0.25.4, v1.24.2, v1.25.2, v1.26.0, 1.27.10): the column
  has been definition-only since its birth in the 2018 draft-schema commit
  (`758fabeb "draft schema mods #28"`) - this is never-completed wiring from
  the communities-rewrite draft, NOT a regression from a working feature.
- **Impact**: zero user-visible effect - the API never exposes the flag, and
  frontends detect "Declined" from `max_accepted_payout == '0.000 HBD'`
  (which hivemind mirrors correctly); payout math is also right (declined
  posts get CPU but no comment_reward, so payout stays 0 and pending zeroes
  at cashout). The real hazards: (a) anyone querying the COLUMN directly
  (analytics, HAF apps, agents reading the schema) gets FALSE for every post
  ever - silently wrong data; (b) declined posts participate fully in
  trending/hot/payout-sorted lists and in `payout_stats_view` pending sums
  via pending payouts that will pay 0 - internally consistent, but
  payout-sorted surfaces can show never-paying posts. Recommend upstream:
  drop the column, or wire it if decline-aware filtering is wanted.

### 12. CONSISTENT: ECV fires for every vote application, including unvotes
- **What**: `effective_comment_vote_operation` is pushed unconditionally on
  both vote-evaluator paths (`core:libraries/chain/hive_evaluator_social.cpp:602,851`),
  including weight-0 unvotes (rshares 0). Hivemind's merge model (type 0
  gives percent/time, type 72 gives weight/rshares/is_effective,
  `num_changes` = ECV count - 1) is therefore complete over the real event
  stream.

### 13. LEGACY-DELIBERATE: real-op timestamps lag their block by 3 seconds
- **What**: `load_ops_staging` assigns real ops the PREVIOUS block's
  timestamp and vops the current block's (`massive_sync.sql:177-193`,
  replicating the old Python `_head_block_date`). L1 truth: an op in block N
  happens at block N's timestamp.
- **Impact**: every `created_at`/`updated_at`/`last_update` in hivemind is
  3 s earlier than the L1 block time (vop-derived times are exact). Harmless
  for display, but exact-time joins against HAF/hived data will off-by-one-
  block unless this is known.

### 14. APPROXIMATION: time windows assume a perfect 3-second cadence
- **What**: `block_before_head(interval)` computes `head - seconds/3`
  (`head_block_time.sql:13-19`) - correct only if no block slots were ever
  missed. The chain has missed slots (most in the 2016 mining era), so
  block-counted windows (notification 90 days, post age 97 days) reach
  slightly FURTHER back in wall time than labeled.
- **Impact**: bounded, one-sided drift; irrelevant for UX, relevant only if
  someone treats the windows as exact wall-clock cutoffs.

---

## Verified-consistent quick list (no discussion needed)

| Assumption | hivemind | hive-core evidence |
|------------|----------|--------------------|
| Op id map (17 staged ids) | part 04 table | `reference/operations.md` ids match 1:1 |
| Vote identity = (voter, author, permlink) | `hive_votes` UQ | protocol vote/comment_vote identity |
| Ineffective delete (73) pre-HF19 only | posts step 1/7 | `reference/operations.md:98,424` |
| comment_options defaults 10000 / 1,000,000.000 HBD | step 6 COALESCEs | protocol defaults (`reference/operations.md`) |
| Beneficiaries extension shape `{type, value:{beneficiaries}}` | step 6 extraction | HAF op-body serialization of static_variant extensions |
| Vops occupy ids 50-92 at 1.28 (date rule `>= 50`) | `massive_sync.sql:184` | 50 real + 43 virtual (`reference/operations.md`) |
| pow2 name at `work.value.input.worker_account` | accounts processor | pow2 static_variant body shape |
| 3 s block interval in time math | `head_block_time.sql` | `HIVE_BLOCK_INTERVAL` = 3 |

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Treasury creation (HF21/HF24) | core:libraries/chain/database_hardfork.cpp | 435,536 | account_created vops hivemind never stages |
| Genesis account_created loop | core:libraries/chain/database.cpp | 2373-2399 | Genesis accounts announced via vop 80 |
| account_created emission (5 ops) | core:libraries/chain/hive_evaluator.cpp, hive_evaluator_account.cpp | 432,578; 207,282,496 | The op set hivemind mirrors |
| comment_reward field semantics | core:libraries/protocol/include/hive/protocol/hive_virtual_operations.hpp | 79-94 | total_payout_value = author-only (comments) |
| comment_reward emission + pre-HF19 accumulation | core:libraries/chain/database_comment.cpp | 290-317 | payout composition; add_payout_values |
| CPU emission condition | core:libraries/chain/database_comment.cpp | 361-363 | HF17-or-final rule |
| ECV emission (both paths) | core:libraries/chain/hive_evaluator_social.cpp | 602,851 | Fires for every vote incl. unvote |
| custom_json auth validation | core:libraries/protocol/hive_operations.cpp | 421-427 | Active-auth form legal on L1 |
| Genesis time + special accounts | core:libraries/protocol/include/hive/protocol/config.hpp | 150,219,443-447 | 1458835200; miners/null/temp/initminer |
| HF1/HF17 blocks | reference/hardforks.md | 11,27 | 905693 vesting split; 10629455 |
| Metadata last-non-empty rule (canonical) | haf:src/hive_fork_manager/state_providers/metadata.sql | 120-137 | Matches hivemind's rule |
| Follow auth + follower==auth | hive/db/sql_scripts/hafapp_api.sql | 108-115,165-168 | Posting-only; spoof-proof |
| Community auth + actor | hive/db/sql_scripts/massive_sync.sql | 2151-2157,1793 | Same pattern |
| Reblog account==auth | hive/db/sql_scripts/massive_sync.sql | 571-576 | Same pattern |
| rshares HF1 scaling | hive/db/sql_scripts/massive_sync.sql | 374-377 | x1e6 below 905693 |
| Safe-cashout constant | hive/indexer/blocks.py | 132-143 | LIB-201600 past 10629455 |
| Real-op timestamp lag | hive/db/sql_scripts/massive_sync.sql | 177-193 | prev-block date for real ops |
| Genesis epoch fn | hive/db/sql_scripts/utility_functions.sql | 101-110 | 2016-03-24T16:00:00 |
| Seeded system accounts | hive/db/schema.py | 63-67 | 4 names @ 16:05:00 |
| Dead is_declined | hive/db/sql_scripts/schema/create_tables.sql | 44 | No producer/reader (grep-verified) |

## Cross-references to existing parts

- Parts 02/04/05 for the hivemind-side mechanics each check leans on
  (accounts processor, payout mirror, post objects, mention join).
- hive-core KB `reference/hardforks.md`, `reference/operations.md`,
  `reference/economics.md` - the L1 facts used as ground truth.
- HAF KB part 04 (state providers) for the metadata rule's home.

## Open Questions

- Whether any OTHER account has ever been created outside the 5 ops + genesis
  + treasuries on mainnet (a full answer needs a HAF query over vop 80 vs
  hivemind's account set - empirical, out of scope for source-only research).
- Whether upstream wants `is_declined` reconnected (set from
  `max_accepted_payout == 0`) or dropped; and whether staging vop 80 (or
  seeding the treasuries) is the preferred fix for Discovery 1.
- The exact wall-clock drift of the 90-day windows (needs missed-slot counts
  from chain data; bounded and small post-2016).

## Upstream-worthy summary (hivemind repo)

1. vop 80 (`account_created`) not staged (Discovery 1) - latent
   robustness/portability gap; harmless on mainnet today because both
   treasury names pre-existed as regular accounts, but bites on fresh chains
   and any future hardfork-created account.
2. `is_declined` dead column (Discovery 11) - never-wired draft residue;
   drop or wire.
3. (Documentation-grade) active-auth custom_jsons ignored (Discovery 6) and
   `author_payout_value` includes beneficiaries (Discovery 5) - worth stating
   in hivemind's own docs even if behavior stays for compatibility.
