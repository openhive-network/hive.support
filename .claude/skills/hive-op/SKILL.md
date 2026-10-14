# /hive-op

Complete documentation for a specific Hive operation: protocol spec, evaluator behavior, client-side builders, social-layer interpretation, related rules.

## Usage

```
/hive-op <operation_name>
```

The operation name can be with or without the `_operation` suffix:
- `/hive-op transfer` or `/hive-op transfer_operation`
- `/hive-op vote` or `/hive-op vote_operation`
- `/hive-op custom_json` or `/hive-op custom_json_operation`

## Behavior

1. Look up the operation in `reference/operations.md` for the spec
2. Check `research/hive-core/findings/02-operations-catalog.md` for detailed field info
3. Check `research/hive-core/findings/03-operation-validation.md` for validation rules
4. Check `research/hive-core/findings/04-chain-evaluators.md` for evaluator behavior (and `11-validate-evaluate-gaps.md` for checks that live in the evaluator only)
5. Check `reference/wax/operations.md` for how wax models and builds it (builders, `complex_operations/`, `hive_apps_operations/`)
6. For `vote`, `comment`, `comment_options`, `delete_comment`, `custom_json` and the payout virtual ops, check `reference/hivemind/operations.md` for how hivemind interprets them
7. Grep `reference/rules/*.md` for rules that mention the operation
8. Combine into a complete operation profile

## Output Format

```markdown
# <operation_name>

**ID**: <numeric ID>
**Category**: <category>
**Authority**: <posting|active|owner>

## Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| ... | ... | ... | ... |

## Validation Rules

- <rule 1>
- <rule 2>
- ...

## Evaluator Behavior

<What happens when this operation is processed:>
1. <step 1>
2. <step 2>
...

## State Objects Affected

| Object | How Modified |
|--------|-------------|
| ... | ... |

## Building it with wax

<builder or pushOperation shape; asset and authority notes>

## Social-layer interpretation (hivemind), if any

<which custom_json ids / which tables; or "not interpreted">

## Rules

- <rule id>: <one line>

## Common Pitfalls

- <pitfall 1>
- <pitfall 2>

## Hardfork Notes

<Any hardfork-conditional behavior>

## How to verify

<the recipe from reference/verify.md that observes this operation's behavior>
```

## Examples

- `/hive-op transfer` -> full profile of transfer_operation
- `/hive-op delegate_vesting_shares` -> delegation operation with its complex evaluator
- `/hive-op witness_update` -> witness configuration with all fields
- `/hive-op custom_json` -> custom_json with its special multi-authority model, the chain-interpreted `rc` id and the four hivemind ids
