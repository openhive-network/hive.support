# /hive-lookup

Quick lookup against the Hive knowledge base reference docs.

## Usage

```
/hive-lookup <query>
```

## Behavior

1. Parse the query to identify the concept area
2. Read the relevant reference file(s) from `reference/`
3. Extract and return the specific answer

## Query Routing

| Query contains | Read |
|---------------|------|
| operation name, fields, authority, validation | `reference/operations.md` |
| state object, index, account_object, comment_object | `reference/state-objects.md` |
| constant, limit, max, min, HIVE_ | `reference/constants.md` |
| reward, inflation, HBD, vesting, DHF, treasury | `reference/economics.md` |
| witness, block, schedule, consensus, fork | `reference/consensus.md` |
| API, endpoint, plugin, condenser, database_api | `reference/api.md` |
| RC, resource credit, mana, cost | `reference/rc.md` |
| hardfork, HF, version | `reference/hardforks.md` |

If the query spans multiple areas, read all relevant files.

## Output Format

Return the relevant section/table from the reference doc. If the answer is a table row, return just that row with the header. If it's a section, return the section. Keep it concise — the user wants a quick answer, not the whole document.

If the query can't be answered from reference docs, check `research/hive-core/findings/` for deeper detail and note that the answer comes from findings (which includes source citations).

If the query can't be answered at all, say so clearly.

## Examples

- `/hive-lookup transfer_operation fields` → returns the fields table for transfer_operation from operations.md
- `/hive-lookup HBD print rate` → returns the HBD print rate section from economics.md
- `/hive-lookup rc cost model` → returns the RC cost calculation from rc.md
- `/hive-lookup HIVE_MAX_WITNESSES` → returns the constant value from constants.md
- `/hive-lookup custom_json authority` → returns the authority requirements for custom_json_operation
