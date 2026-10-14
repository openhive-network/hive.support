# hivemind KB gaps found while drafting rules and evals (2026-10-14)

- **Topic**: hivemind
- **Type**: correction
- **Affects**: research/hivemind/findings/06-legacy-apis.md (Key Discovery 3); research/hivemind/findings/07-serving-internals.md (error message shape)
- **Source**: hivemind worktree `workspace/hivemind/cab9e328bf/` (1.28.6)

## Description

Found by the rules/evals drafting pass. Five related items were verified by the maintainer
and applied the same day (limits raise instead of clamping; unknown namespace returns
-32601 `Api not found <api>`; bridge `stats` also carries `hide` and `total_votes`;
`author_payout_value` exists only on bridge objects while condenser writes the same
`payout - curator` arithmetic into `total_payout_value`; the hive-core custom_json entry now
lists `notify`). Pending:

1. **findings/06 Key Discovery 3 overstates the 1000-vote cap.** "1000 is the effective
   ceiling on votes visible through ANY hivemind endpoint - posts with more voters are
   silently truncated" is true per response, not per post: `database_api.list_votes` with
   order `by_comment_voter` takes an optional start voter and filters `voter_id >= start`
   ordered by voter id (`hive/db/sql_scripts/postgrest/database_api/database_api_list_votes.sql:44-50`,
   `utilities/list_votes.sql` WHERE / ORDER BY), so full enumeration is possible by paging on
   the last voter (inclusive start, so drop the repeated first row). Rule HM-002 and eval
   HM-E002 already state the paging form.
2. **Unknown-method message shape (cosmetic).** The message is built as
   `'bridge_api' || method`, `'tags_api' || method` etc. without a dot separator
   (`utilities/get_api_method.sql:162,203,228,251,272`), while condenser / follow use
   `'condenser_api.'`. The KB's `unknown method: ...` wording is fine; anyone matching the
   exact text should know the namespaces differ.

## Evidence

Line references above, read in the pinned 1.28.6 worktree by the drafting agent; the
`list_votes` cursor behavior is consistent with `database_api_list_votes.sql:42,64-66` which
the KB already cites for the [1,1000] limit.
