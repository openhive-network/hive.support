# Hivemind: Operation Semantics (cheat sheet)

Anchor `1.28.6`. Depth: findings part 04. Handlers live in
`massive_sync.sql`, `hive_post_operations.sql`, `hafapp_api.sql`,
`follow_ops.sql`, `community.sql`.

## The op filter (staging)

`load_ops_staging` stages `op_type_id IN (0,1,9,10,14,17,18,19,23,30,41,43,
51,53,61,72,73)`; custom_json (18) only for ids
`follow`/`reblog`/`community`/`notify` (HAF `custom_json_type_id`). Date quirk:
vops (>= 50) get the CURRENT block's timestamp, real ops the PREVIOUS block's.

| id | Operation | Effect |
|----|-----------|--------|
| 0 | vote | vote_percent + last_update |
| 1 | comment | post create/edit (waves) |
| 9 / 23 / 41 | account_create / create_claimed / with_delegation | new account + metadata |
| 14 / 30 | pow / pow2 | miner account (no metadata; pow2 name nested) |
| 10 / 43 | account_update / account_update2 | json_metadata (both), posting_json_metadata (43 only); empty string = no change |
| 17 | delete_comment | delete / delete-create cycles |
| 18 | custom_json (4 ids) | follows / reblogs / community ops / setLastRead |
| 19 | comment_options | max_accepted_payout, percent_hbd, allow_*, beneficiaries |
| 51 | author_reward (vop) | author_rewards_{hive,hbd,vests} |
| 53 | comment_reward (vop) | author_rewards units; total/curator payout strings; `payout` = total+curator+beneficiary; zeroes pending |
| 61 | comment_payout_update (vop) | is_paidout, payout_at, cashout_time='infinity', zero pending + total_vote_weight |
| 72 | effective_comment_vote (vop) | weight/rshares/is_effective; pending_payout + total_vote_weight (**x1e6 before block 905693**) |
| 73 | ineffective_delete_comment (vop) | cancels the matching op-17 delete (pre-HF19) |

Payout precedence: 53 supersedes 72's pending data; 61 finalizes.
`author_rewards` accumulates, guarded by the `last_payout_block` high-water
mark. Votes merge per (voter, author, permlink): last 0-op + last 72-op;
`num_changes` = ECV count - 1, replay-guarded by block_num.

## Follow custom_json (id `follow`)

Array `['follow', {follower, following, what: [action]}]` (bare object
auto-wrapped pre-block-6M). Last action per group wins per batch.

| Action | Table | Group |
|--------|-------|-------|
| blog / follow | follows | follow_group |
| ignore | muted | follow_group |
| '' (empty) | clears follows + muted | follow_group |
| blacklist / unblacklist | blacklisted | blacklist_group |
| follow_blacklist / unfollow_blacklist | follow_blacklisted | fb_group |
| follow_muted / unfollow_muted | follow_muted | fm_group |
| reset_blacklist / reset_following_list / reset_muted_list / reset_follow_blacklist / reset_follow_muted_list / reset_all_lists | bulk deletes | - |

## Reblog custom_json (ids `follow` OR `reblog`)

`['reblog', {account, author, permlink[, delete: "delete"]}]` - exactly 1
posting auth, 0 active auths, `account` == auth; last op per
(author, permlink, account) wins; any delete also purges prior feed entries.

## Community custom_json (id `community`)

Two-phase: phase 1 state ops (`subscribe`, `unsubscribe`, `updateProps`,
`setRole`, `setUserTitle`) BEFORE posts; phase 2 post ops (`mutePost`,
`unmutePost`, `pinPost`, `unpinPost`, `flagPost`) after. Communities are
`hive-*` accounts registered at account creation (past start block);
`hive_communities.id` = the account id; creator gets role 8 (owner).

**Posting gate** (`process_community_post`, at post insert):

| Community type | Rule |
|----------------|------|
| 1 topic | never muted |
| 2 journal | comments free; top posts need role >= 2 (member) |
| 3 council | everything needs role >= 2 |

Failing => `is_muted` + reason bit 1 (COMMUNITY_TYPE); muted parent => bit 2
(PARENT) on the comment. Deferred subtree propagation runs at finalization.

## Notifications (write-time production)

| Kind (type_id) | Trigger | Score | Extra gates |
|----------------|---------|-------|-------------|
| vote (17) | effective votes | payout-based (`calculate_notify_vote_score`) | rshares >= 10e9, value >= 0.02 HBD, score >= 0, voter != author, post < 97 d, mute-filtered (direct + transitive), counter = 2xN |
| reply/reply_comment (12/13), reblog (14), follow (15) | posts/reblogs/follow events | reputation `*7.5+25` | 90-day window; scores rewritten from final reputations at fills |
| mention (16) | regex `@name` in bodies | same formula (inlined) | hourly old-mention cleanup |
| community kinds (1-11) + error (10) | community ops | fixed (e.g. 35) | `community_op_counter` sequence |

Retention: hourly prune of rows older than 90 days; `clear_muted_notifications`
purges muted pairs at finalization. `setLastRead` (custom_json `notify`)
updates `hive_accounts.lastread_at` (regex-validated, clamped to block time).

## Derived-state maintenance

| Function | Purpose |
|----------|---------|
| update_posts_rshares / recalculate_all_posts_rshares | vote aggregates + sc_trend/sc_hot |
| hot_and_trends.sql | log10(rshares/1e7) mod-score + time component (sec/10000) |
| update_feed_cache | own top posts + reblogs -> hive_feed_cache (NULL range = full) |
| update_hive_posts_children_count / __post_children | children counters |
| update_hive_posts_root_id | root_id fix (depth-0 inserted with 0) |
| update_communities_posts_and_rank | community rank (10-min + fills) |
| delete_hive_posts_mentions / process_hive_post_mentions | mention extract/cleanup |

## Gotchas

- Two references hardcode `reptracker_app.` (`reputation_score`,
  mention-score join) - custom `--reptracker-schema-name` breaks them.
- Edits bump `hive_posts.block_num` (notification timestamps rely on it);
  votes filter by `block_num_created` for delete/recreate correctness.
- Delete-create cycles mint NEW post ids (votes do not carry over); children
  re-linked, comment_options re-applied.
- Last edit's tags fully override creation tags for root posts.
