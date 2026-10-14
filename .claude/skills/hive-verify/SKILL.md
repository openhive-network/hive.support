# /hive-verify

Verify a claim about Hive behavior (protocol, wax, HAF, hivemind) against the source-verified knowledge base.

## Usage

```
/hive-verify <claim>
```

## Behavior

1. Parse the claim to identify what is being asserted and which topic it belongs to
2. Read the relevant reference doc(s) and/or findings; check `reference/rules/` for a rule that covers the claim
3. Compare the claim against the KB evidence
4. Return a verdict with citations, and name the tool that would settle it empirically (`reference/verify.md`)

## Output Format

```
Claim: "<the claim>"

Verdict: CONFIRMED | DENIED | PARTIALLY CORRECT | UNVERIFIABLE

Evidence:
- <what the KB says, with file and section>
- <source citation from findings if available>
- <rule id, if a rule covers it>

Correction (if applicable):
- <what the correct information is>

Empirical check (if one exists):
- <the recipe from reference/verify.md that observes the behavior directly>
```

## Verdicts

| Verdict | Meaning |
|---------|---------|
| CONFIRMED | The claim matches the KB exactly |
| DENIED | The claim contradicts the KB |
| PARTIALLY CORRECT | The claim is partially right but missing nuance or has an error in detail |
| UNVERIFIABLE | The KB doesn't cover this topic well enough to confirm or deny |

## Process

1. Identify the topic (hive-core protocol, wax, HAF, hivemind) and concept area
2. Read the relevant reference doc(s): `reference/*.md` for the protocol, `reference/wax/`, `reference/haf/`, `reference/hivemind/` for the libraries and layers
3. If reference docs don't have enough detail, check `research/<topic>/findings/` for source-level citations
4. Compare the claim against what the KB says
5. For DENIED or PARTIALLY CORRECT, provide the correct information
6. For UNVERIFIABLE, say so and write a `contrib/<topic>/` question note if the claim matters

## Examples

- `/hive-verify "voting power regenerates over 5 days"` -> economics.md and findings for vote mana regeneration time
- `/hive-verify "HBD interest rate is set by witnesses"` -> economics.md for the HBD interest mechanism
- `/hive-verify "transfer_operation requires active authority"` -> operations.md for transfer authority
- `/hive-verify "RC is enforced during block replay"` -> rc.md; DENIED (RC is mempool-only)
- `/hive-verify "votes on paid-out posts consume voting mana"` -> operations.md vote_operation; DENIED (early return, RC still charged)
- `/hive-verify "NaiAsset.amount is a number"` -> reference/wax/assets.md; DENIED (string, BigInt-backed)
- `/hive-verify "hivemind indexes every custom_json id"` -> reference/hivemind/operations.md; DENIED (four ids)
