# Rules - verified best practices and traps, for code review

The KB's "obvious once you know it" layer. Each rule is a fact that a competent developer
without Hive experience gets wrong, stated so that a reviewer (human or agent) can check code
against it. Every rule cites the KB sections it is distilled from, and those sections cite
source `file:line` at the pinned release. Rules are never asserted from memory: if the
evidence chain is missing, the rule does not exist.

| File | Prefix | Rules | Scope | Anchor |
|------|--------|-------|-------|--------|
| [hive-core.md](hive-core.md) | `HC-` | 12 | protocol: authority, operations, mana/RC, limits, hardfork-conditional behavior | hived `1.28.7` |
| [wax.md](wax.md) | `WAX-` | 8 | client library: assets, transactions, signing, API surface | wax `2.0.2` |
| [haf.md](haf.md) | `HAF-` | 6 | indexing framework: contexts, views, forks, filtering | HAF `1.28.6` |
| [hivemind.md](hivemind.md) | `HM-` | 7 | social API layer: params, response objects, custom_json, payout fields | hivemind `1.28.6` |

## Rule format

```
## HC-001: <short title>

- **Rule**: what to do or not do (declarative)
- **Why**: the mechanism in one or two sentences
- **Evidence**: KB file (section); KB file (section); source: file:line as the KB cites it
- **Applies**: version / hardfork range
- **Detect**: what a reviewer looks for in code (API names, patterns, grep hints)
- **Wrong**: the mistake, in one line or a tiny snippet
- **Right**: the correct approach, in one line or a tiny snippet
```

IDs are stable. A retired rule keeps its id with a `(retired: reason)` suffix; ids are never
reused. New rules append at the end of the topic file.

## How agents use this layer

- **Reviewing code** that touches Hive: read the topic file(s) for the libraries the code
  uses, then check each `Detect` hint against the diff. Cite the rule id and its evidence in
  the review. The `hive-reviewer` agent does this first.
- **Writing code**: scan `Detect` hints for the APIs you are about to call.
- **MCP**: `hive_rules(query=...)` returns the matching rules' full text; `hive_operation`
  lists the rules that mention an operation.

## Adding or correcting a rule

Rules are distilled from `reference/` and `research/*/findings/`. To propose one, write a
`contrib/<topic>/` note (type `addition` or `correction`) with the evidence; the maintainer
verifies it against the pinned source and adds it here. Each rule should also have at least
one eval item in `evals/<topic>.json` so regressions in agent behavior are measurable.
