# /hive-verify

Verify a claim about Hive blockchain behavior against the source-verified knowledge base.

## Usage

```
/hive-verify <claim>
```

## Behavior

1. Parse the claim to identify what's being asserted
2. Read the relevant reference doc(s) and/or findings
3. Compare the claim against the KB evidence
4. Return a verdict with citations

## Output Format

```
Claim: "<the claim>"

Verdict: CONFIRMED | DENIED | PARTIALLY CORRECT | UNVERIFIABLE

Evidence:
- <what the KB says, with file references>
- <source citation from findings if available>

Correction (if applicable):
- <what the correct information is>
```

## Verdicts

| Verdict | Meaning |
|---------|---------|
| CONFIRMED | The claim matches the KB exactly |
| DENIED | The claim contradicts the KB |
| PARTIALLY CORRECT | The claim is partially right but missing nuance or has an error in detail |
| UNVERIFIABLE | The KB doesn't cover this topic well enough to confirm or deny |

## Process

1. Identify the concept area (operations, economics, consensus, etc.)
2. Read the relevant reference doc(s)
3. If reference docs don't have enough detail, check findings for source-level citations
4. Compare the claim against what the KB says
5. For DENIED or PARTIALLY CORRECT, provide the correct information

## Examples

- `/hive-verify "voting power regenerates over 5 days"` -> Check economics.md and findings for vote mana regeneration time
- `/hive-verify "HBD interest rate is set by witnesses"` -> Check economics.md for HBD interest mechanism
- `/hive-verify "transfer_operation requires active authority"` -> Check operations.md for transfer authority
- `/hive-verify "RC is enforced during block replay"` -> Check rc.md — this should be DENIED (RC is mempool-only)
