# /hive-lookup

Quick lookup against the Hive knowledge base reference docs (protocol, wax, HAF, hivemind).

## Usage

```
/hive-lookup <query>
```

## Behavior

1. Parse the query to identify the topic and concept area
2. Read the relevant reference file(s) from `reference/`
3. Extract and return the specific answer, naming the file and section it came from

## Query Routing

| Query contains | Read |
|---------------|------|
| "how do I ...", a developer task | `reference/tasks.md` (then follow its reading path) |
| operation name, fields, authority, validation | `reference/operations.md` |
| state object, index, account_object, comment_object | `reference/state-objects.md` |
| constant, limit, max, min, HIVE_ | `reference/constants.md` |
| reward, inflation, HBD, vesting, DHF, treasury, vote value | `reference/economics.md` |
| witness, block, schedule, consensus, fork, irreversible | `reference/consensus.md` |
| API, endpoint, plugin, condenser, database_api | `reference/api.md` |
| RC, resource credit, mana, cost | `reference/rc.md` |
| hardfork, HF, version | `reference/hardforks.md` |
| wax, createHiveChain, NaiAsset, waxify, signer, sigDigest, broadcast (client side) | `reference/wax/README.md` then the file its Quick Lookup names |
| HAF, hafd, hive_fork_manager, context, app_next_block, sql_serializer, filtering | `reference/haf/README.md` then the file its Quick Lookup names |
| hivemind, bridge, condenser_api posts/feeds, follow, community, notification, reputation | `reference/hivemind/README.md` then the file its Quick Lookup names |
| best practice, pitfall, "should I", code review | `reference/rules/` (the topic file) |
| "how can I check/verify/test ..." | `reference/verify.md` |

If the query spans multiple areas, read all relevant files.

## Output Format

Return the relevant section/table from the reference doc with its path. If the answer is a table row, return just that row with the header. If it's a section, return the section. Keep it concise; the user wants a quick answer, not the whole document.

If the query can't be answered from reference docs, check `research/<topic>/findings/` for deeper detail and note that the answer comes from findings (which include source citations).

If the query can't be answered at all, say so clearly; do not fill the gap from general knowledge.

## Examples

- `/hive-lookup transfer_operation fields` -> the fields table for transfer_operation from operations.md
- `/hive-lookup HBD print rate` -> the HBD print rate section from economics.md
- `/hive-lookup rc cost model` -> the RC cost calculation from rc.md
- `/hive-lookup HIVE_MAX_WITNESSES` -> the constant value from constants.md
- `/hive-lookup custom_json authority` -> the authority requirements for custom_json_operation
- `/hive-lookup NaiAsset amount type` -> the NaiAsset section from reference/wax/assets.md
- `/hive-lookup events_queue block_num` -> the Events & forks section from reference/haf/schema.md
- `/hive-lookup bridge get_ranked_posts limit` -> the bridge method table from reference/hivemind/api.md
