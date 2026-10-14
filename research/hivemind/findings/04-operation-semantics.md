# Hivemind Part 04 - Operation Semantics (Ops -> Social State)

**Anchor:** hivemind `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`).
**Scope:** what each staged operation does to the tables - the 17-op filter mapped
to protocol operations, then per domain: accounts, posts (create/edit/delete
cycles, community assignment, muting), votes, payout mirroring, reblogs, the
follow state machine, community ops, notifications (production, thresholds,
pruning), mentions, and the derived-state maintenance functions. Pipeline
orchestration is part 03; table shapes are part 02.

Paths are hivemind-repo-relative against the pinned worktree
`workspace/hivemind/cab9e328bf/`; `massive_sync.sql` = `hive/db/sql_scripts/massive_sync.sql`.

---

## Summary

Hivemind consumes 12 real operations + 5 virtual operations. Social state is a
deliberate re-derivation: account rows from 5 creation ops, posts from `comment`
ops resolved in dependency waves, vote rows merged from `vote` +
`effective_comment_vote`, payout columns mirrored from 4 payout vops, and the
follow/mute/blacklist tables driven by a custom_json action machine. Community
rules (types topic/journal/council, roles -2..8) gate who may post unmuted;
notifications are produced per kind with score/vote-value thresholds and a
90-day retention window.

## The op filter, mapped

`load_ops_staging` (part 03) stages `op_type_id IN
(0,1,9,10,14,17,18,19,23,30,41,43,51,53,61,72,73)` (`massive_sync.sql:198`).
Names verified against hive-core KB `reference/operations.md` ids and the
handlers' own comments:

| id | Operation | Consumed by | Effect |
|----|-----------|-------------|--------|
| 0 | vote | `process_votes_from_staging` | vote_percent/last_update |
| 1 | comment | `process_posts_from_staging` | post create/edit |
| 9 / 23 / 41 | account_create / create_claimed_account / account_create_with_delegation | `process_accounts_from_staging` | new account + initial metadata |
| 14 / 30 | pow / pow2 | same | miner account creation (no metadata; pow2 name at `work.value.input.worker_account`) |
| 10 / 43 | account_update / account_update2 | `process_account_updates_from_staging` | json_metadata (both), posting_json_metadata (43 only) |
| 17 | delete_comment | posts step 7 | delete / delete-create cycles |
| 18 | custom_json (`follow`,`reblog`,`community`,`notify` only) | follows / reblogs / community / lastread processors | see sections below |
| 19 | comment_options | posts step 6 | max_accepted_payout, percent_hbd, allow_votes, allow_curation_rewards, beneficiaries |
| 51 | author_reward (vop) | `process_payouts_from_staging` | author_rewards_{hive,hbd,vests} |
| 53 | comment_reward (vop) | same | author_rewards units, total/curator payout strings, `payout` sum |
| 61 | comment_payout_update (vop) | same | is_paidout, payout_at, cashout_time='infinity', zero pending |
| 72 | effective_comment_vote (vop) | votes + payouts | weight/rshares/is_effective; pending_payout, total_vote_weight |
| 73 | ineffective_delete_comment (vop) | posts step 1 | suppresses the matching delete (pre-HF19 soft-fail deletes) |

---

## Key Discoveries

### 1. Pre-block-905693 rshares are scaled by 1,000,000
- **What**: `effective_comment_vote` rshares are multiplied by 1e6 when
  `block_num < 905693` - normalizing the early-chain rshares denomination
  change into one unit space.
- **Where**: `massive_sync.sql:374-377`.
- **Impact**: every rshares-derived value (vote lists, trending scores, vote
  notifications) depends on this constant; naive re-derivation from raw vops
  would be wrong for the first ~905k blocks.

### 2. Vote identity merge + the replay guard
- **What**: type 0 contributes vote_percent/last_update, type 72 contributes
  weight/rshares/is_effective; per (voter, author, permlink) the LAST of each
  wins (FULL OUTER JOIN merge); `num_changes` = ECV count - 1 per batch. The
  upsert refuses to re-increment `num_changes` when `EXCLUDED.block_num <=`
  the stored one - the crash-replay idempotency guard from part 03. Votes cast
  before a post's re-creation are filtered via `block_num_created` (not
  `block_num`, which edits move).
- **Where**: `massive_sync.sql:325-500` (merge 388-421, stale-vote filter
  442-449, guard 470-476).
- **Impact**: hive_votes is an eventually-exact mirror of chain vote state even
  across batch replays and delete/recreate cycles.

### 3. Community gating writes `is_muted` + `muted_reasons` at post creation
- **What**: `process_community_post`: before the community start block - no
  community, unmuted. After: community = `hive_communities.name =
  parent_permlink` (top posts) or the parent's community (comments). Type
  **topic(1)**: never muted. **journal(2)**: comments free, top posts need
  `role_id >= member(2)`. **council(3)**: everything needs member+. Failing the
  gate sets muted with reason bit 1 (`MUTED_COMMUNITY_TYPE`); a muted parent
  forces bit 2 (`MUTED_PARENT`) on the comment regardless.
- **Where**: `hive/db/sql_scripts/hive_post_operations.sql:51-113`; reason-bit
  encode `hive_post_operations.sql:29`; role names -2 muted / 0 guest / 2
  member / 4 mod / 6 admin / 8 owner
  (`postgrest/utilities/get_role_name.sql:9-16`); owner assigned at community
  registration (`community.sql:167-171`).
- **Impact**: muting is *derived state computed at insert time* plus later
  moderation ops; the deferred `propagate_muted_parent_for_batch` /
  `propagate_all_muted_parents` (part 03) keeps subtree consistency.

### 4. Payout mirroring is last-writer-wins with explicit precedence
- **What**: one GROUP BY (author, permlink) pass aggregates the 4 payout vops;
  `comment_reward` (53) supersedes `effective_comment_vote` pending data
  (`has_cr` nullification); `comment_payout_update` (61) marks paidout, zeroes
  pending_payout and total_vote_weight, sets `cashout_time='infinity'`;
  `payout = total + curator + beneficiary` values (HBD units);
  `author_rewards` ACCUMULATES across payout cycles but skips accumulation on
  replay via the `last_payout_block` high-water mark.
- **Where**: `massive_sync.sql:756-889` (precedence 768-769,808-812; replay
  guard 830-835; payout sum 838-846); amount helpers `:890-948`
  (`legacy_amount` renders NAI JSON to `'1.234 HBD'` strings).
- **Impact**: `hive_posts` payout columns exactly mirror what the API must
  serve (part 02 columns); the replay guard is why `_batch_queue` replay is
  safe for payouts.

### 5. The follow machine: 10 actions + 6 resets over 5 tables, last-per-group wins
- **What**: custom_json id `follow` (array `['follow', {...}]`; pre-6M bare
  objects auto-wrapped) with `what` action: `blog`/`follow` -> `follows`;
  `ignore` -> `muted`; `''` (empty) clears follow+mute; `blacklist`/`unblacklist`;
  `follow_blacklist`/`unfollow_blacklist`; `follow_muted`/`unfollow_muted`;
  plus `reset_blacklist` / `reset_following_list` / `reset_muted_list` /
  `reset_follow_blacklist` / `reset_follow_muted_list` / `reset_all_lists`.
  Actions collapse per (follower, following, action-group) - groups:
  follow/blacklist/follow_blacklist/follow_muted - so the batch's last action
  per group is applied via the typed `insert_/delete_/reset_*` helpers.
- **Where**: `hive/db/sql_scripts/hafapp_api.sql:54-508` (action comment 85,
  legacy wrap 124-127, resets 172-243, groups 282-285);
  helpers `hive/db/sql_scripts/follow_ops.sql:97-419` (+ `flush_follows`
  procedure). Follow events for notifications are recorded separately in
  `_follow_notification_events` because the final-state tables can't represent
  re-follows (part 02 section 2).
- **Impact**: this is the full state machine behind the 5 relationship tables;
  reset actions are bulk deletes; `follow`/`blog` are synonyms, as are the
  mute group semantics used by notification filtering.

### 6. Notification production is threshold-gated and mute-filtered at write time
- **What**: vote notifications (type 17): only if `rshares >= 10e9`,
  `vote_value >= 0.02` (USD-ish HBD), `score >= 0`, voter != author, post
  younger than 97 days, block inside the 90-day window; direct AND transitive
  mutes (via followed mute-lists) filter at INSERT; snowflake counter = 2*N to
  match old Python's two-increment behavior. Reputation-based score for
  reply/reblog/follow/mention kinds = `(GREATEST(log10|rep|-9,0)*sign*7.5+25)`
  (`reputation_score`); mention scores use the same formula inlined ("*7.5
  rather than 9 to bring the max value to 100... 0 -> 25 rather than 0").
  Retention: hourly prune of rows older than 90 days
  (`prune_notification_cache`); `clear_muted_notifications` bulk-removes
  muted-pair rows at finalization.
- **Where**: `massive_sync.sql:2338-2400` (vote flush; thresholds 2390-2393,
  counter comment 2362-2364), `reputation_score` `:2402-2409`;
  post/follow/reblog flushes `:2412-2584`; mention scoring
  `hive/db/sql_scripts/hive_post_operations.sql:773-775`;
  `hive/db/sql_scripts/prune_notification_cache.sql:2-14`;
  `hive/db/sql_scripts/clear_muted_notifications.sql:1-11`.
- **Impact**: the notification cache is a *filtered* event stream, not a log -
  thresholds, mutes, and the 90-day horizon are baked in at write time (the
  API only reads).

### 7. Two hardcoded `reptracker_app.` references defeat the configurable schema
- **What**: `reputation_score()` and the mention-notification reputation join
  reference `reptracker_app.account_reputations` with an explicit schema
  qualifier, while the rest of the codebase binds the reptracker schema via
  `search_path` at deploy time (part 02, Key Discovery 1) precisely so
  `--reptracker-schema-name` can change it.
- **Where**: `massive_sync.sql:2406`;
  `hive/db/sql_scripts/hive_post_operations.sql:857`.
- **Impact**: running hivemind against a non-default reptracker schema would
  break follow/reblog/post notification scoring and mention scoring (function
  creation or execution would target the wrong/missing schema). Dormant with
  default deployments; upstream-worthy alongside part 02's VESTS row.

---

## Domain notes (condensed)

### Accounts
5 creation ops; first occurrence per name wins; metadata only from 9/23/41;
`haf_id` resolved from HAF's `accounts_view`; insert ordered by HAF op id "to
match old Python registration order"; community registration hook fires for
`hive-*` accounts past the community start block
(`massive_sync.sql:215-283,284-320`). Updates (10/43): empty string means
"don't change" (protocol semantics, comment cites hived's metadata_plugin);
last non-empty per field wins; rows locked in id order to avoid deadlocks with
the follows processor (`massive_sync.sql:628-679`). `notify` custom_json
`setLastRead` updates `lastread_at`, date regex-validated and clamped to block
time (`massive_sync.sql:684-751`).

### Posts (create/edit/delete)
Steps (`massive_sync.sql:972-1650`, map in part 03): permlink/category dictionary
upsert; root posts via `process_root_posts_batch`; replies via
`process_comments_batch` in dependency waves; edits (non-first occurrences)
reuse the first result but bump `updated_at`/`block_num` ("notification
timestamps use hp.block_num - 1", `:1117-1124`); tags re-derived for root posts
- last edit's tags override creation (`:1137-1211`, `prepare_tags`
`hive_post_operations.sql:2`); comment_options applied last-per-post incl.
beneficiaries extension extraction (`:1212-1248`); deletes: op 73 keys suppress
their matching op 17 (`:991-996`), simple deletes are bulk ("at full chain
scale 783K delete ops... ~4.7M individual" calls replaced, `:1272-1275`),
delete-create cycles replay chronologically producing NEW post ids (votes don't
carry over), with re-application of comment_options and re-linking of children
that pointed at the deleted row (`:1249-1560`, steps 7c/7f/7g).

### Reblogs
custom_json id `follow` OR `reblog`, inner `['reblog', {...}]` (bare object
tolerated pre-6M); exactly one posting auth, zero active auths, and
`data.account == auth` required; `"delete": "delete"` literal unrebogs; last op
per (author, permlink, account) wins; ANY delete in the batch also purges
prior-batch feed entries via `delete_reblog_feed_cache`; inserts land in
`hive_reblogs` + (via `update_feed_cache`) `hive_feed_cache`
(`massive_sync.sql:505-623`).

### Communities
`process_community_from_staging` phases: 1 = state ops
(`subscribe`,`unsubscribe`,`updateProps`,`setRole`,`setUserTitle`) committed
BEFORE posts; 2 = post-targeting ops
(`mutePost`,`unmutePost`,`pinPost`,`unpinPost`,`flagPost`) after posts; 0 = all
(unused by current callers - live calls 1 then 2, part 03)
(`massive_sync.sql:2110-2135`, dispatch `:1764-1783`). Action authorization &
effects live in `process_community_op` (`:1732-2072`) + `community.sql` (role
threshold checks `:84-142`); payload validation helpers
(`_validate_json_keys`, `_validate_str`, `_is_valid_lang`,
`massive_sync.sql:1658-1727`); team notifications via `_community_notify_team`
(`:2073-2105`) and error notifications (type 10) with the
`community_op_counter` sequence (part 02). Full per-action semantics (titles,
props schema, flag payloads) intentionally summarized - the dispatch list + files
above are the map.

### Derived state (maintenance functions)
- `update_posts_rshares(post_ids)` / `recalculate_all_posts_rshares()` -
  vote_rshares/abs_rshares aggregates + trending/hot scores
  (`hive/db/sql_scripts/update_posts_rshares.sql:1-96`).
- Hot/trend math (`hive/db/sql_scripts/hot_and_trends.sql:75-95`): log-scaled
  `rshares/10000000` mod-score, sign-preserving, plus a
  `seconds_since_epoch/10000` time component - the classic ranking pair
  feeding `sc_trend`/`sc_hot` partial indexes (part 02).
- `update_feed_cache(from,to)` - own top-level posts + reblogs, idempotent
  ON CONFLICT DO NOTHING; NULL range = full rebuild (fills)
  (`hive/db/sql_scripts/update_feed_cache.sql`).
- Children counts: per-range in live, full `__post_children` recount at
  finalization (parts 02/03).
- Mentions: regex `@name` extraction from `hive_post_data.body`
  (`hive_post_operations.sql:767-790`; the mention regex at `:788`); hourly
  `Mentions.refresh()` deletes too-old mentions via
  `delete_hive_posts_mentions` (`hive/indexer/mentions.py:13-18`).
- `update_communities_posts_and_rank` every 200 blocks + at finalization
  (part 03).

---

## Code References

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| Accounts from 5 ops | hive/db/sql_scripts/massive_sync.sql | 215-283 | Names per op type; metadata; haf_id |
| Votes merge + guards | hive/db/sql_scripts/massive_sync.sql | 325-500 | 0+72 merge; 905693 scale; replay guard |
| Reblog parsing/rules | hive/db/sql_scripts/massive_sync.sql | 505-623 | Auth rules; legacy form; last-wins |
| Account metadata updates | hive/db/sql_scripts/massive_sync.sql | 628-679 | Empty=no-change; per-field last-wins |
| setLastRead | hive/db/sql_scripts/massive_sync.sql | 684-751 | notify custom_json -> lastread_at |
| Payout mirror | hive/db/sql_scripts/massive_sync.sql | 756-889 | 51/53/61/72 precedence; replay guard |
| Amount helpers | hive/db/sql_scripts/massive_sync.sql | 890-948 | legacy_amount / sbd_amount |
| Posts steps 1-7g | hive/db/sql_scripts/massive_sync.sql | 972-1650 | Waves, edits, tags, options, delete cycles |
| Community dispatch + phases | hive/db/sql_scripts/massive_sync.sql | 1732-2231 | 10 actions; phase 1/2 split |
| Muted-parent propagation | hive/db/sql_scripts/massive_sync.sql | 2240-2332 | Batch + full variants |
| Notification flushes | hive/db/sql_scripts/massive_sync.sql | 2338-2584 | Vote thresholds; rep score; 4 kinds |
| Community/mute gating | hive/db/sql_scripts/hive_post_operations.sql | 51-113 | topic/journal/council rules; reason bits |
| Batch post fns | hive/db/sql_scripts/hive_post_operations.sql | 416-990 | roots/comments/tags/mentions/deletes |
| Mention extraction + score | hive/db/sql_scripts/hive_post_operations.sql | 767-857 | Regex; inlined rep formula; hardcoded schema at 857 |
| Follow machine | hive/db/sql_scripts/hafapp_api.sql | 54-508 | Actions, resets, groups |
| Follow table helpers | hive/db/sql_scripts/follow_ops.sql | 97-419 | insert/delete/reset per table |
| Role names | hive/db/sql_scripts/postgrest/utilities/get_role_name.sql | 9-16 | -2..8 enum |
| Community registration | hive/db/sql_scripts/community.sql | 84-171 | Role thresholds; id=account id; owner=8 |
| Rshares/rank maintenance | hive/db/sql_scripts/update_posts_rshares.sql, hot_and_trends.sql | 1-96, 75-95 | Aggregates; hot/trend formulas |
| Feed cache fill | hive/db/sql_scripts/update_feed_cache.sql | 1-27 | Posts + reblogs; NULL = full |
| Prune / clear notifications | prune_notification_cache.sql / clear_muted_notifications.sql | 2-14 / 1-11 | 90d hourly prune; muted purge |
| Mentions refresh | hive/indexer/mentions.py | 13-18 | Hourly old-mention deletion |

## Cross-references to existing parts

- **hive-core KB** `reference/operations.md`: the id->operation table (0, 1, 9,
  10, 14, 17, 18, 19, 23, 30, 41, 43 real; 51, 53, 61, 72, 73 virtual - ids
  and vop trigger conditions match hivemind's usage), HF19 for
  ineffective_delete_comment, comment_options semantics.
- **Part 02**: table shapes these handlers fill; muted_reasons bitmask;
  NotifyType ids (17=vote; 12-15 rep-scored kinds); snowflake ids;
  `community_op_counter`.
- **Part 03**: phase ordering & transactions; deferred rshares/vote
  notifications; `_follow_notification_events`; the fills that call
  `recalculate_all_posts_rshares`, `propagate_all_muted_parents`,
  `clear_muted_notifications`, `flush_vote_notifications(1, head)`.

## Open Questions

- Per-action community semantics (updateProps schema, flagPost payloads, title
  validation) were summarized, not exhaustively mapped - a future zoom if API
  work (parts 05-07) needs them.
- `process_community_from_staging(_phase => 0)` and `_cutoff_op_id` have no
  live callers - confirm intent upstream.
- The exact trending/hot time-decay constants (`hot_and_trends.sql`) deserve a
  side-by-side with condenser's historical formulas if anyone relies on parity.
- Upstream-worthy: the two hardcoded `reptracker_app.` references (Key
  Discovery 7).
