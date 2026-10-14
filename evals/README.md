# Evals - does the KB actually make an agent more accurate?

A benchmark of questions a developer (or their coding agent) realistically asks about Hive,
each with a verified expected answer, the wrong answers people commonly give, and the KB and
source evidence behind the expected answer. The same model answers every question twice,
once from its own knowledge and once with this KB available, and a grader scores both. The
difference is the KB's measured value, and every miss is a work item for the KB.

| File | Items | Anchor |
|------|-------|--------|
| [hive-core.json](hive-core.json) | 25 protocol questions | hived `1.28.7` |
| [wax.json](wax.json) | 10 client-library questions | wax `2.0.2` |
| [haf.json](haf.json) | 8 indexing-framework questions | HAF `1.28.6` |
| [hivemind.json](hivemind.json) | 10 social-API questions | hivemind `1.28.6` |
| `results/` | one report per run (`YYYY-MM-DD-<model>.md`) | |

## Item schema

```json
{
  "topic": "hive-core",
  "anchor": {"version": "1.28.7", "sha": "1584099c3054a97f02abfb4788b23f02eea98728"},
  "items": [
    {
      "id": "HC-E001",
      "kind": "trap | lookup | reasoning",
      "question": "the question as a developer would ask it",
      "expected": "the specific facts a correct answer must contain (1-3 sentences)",
      "forbidden": ["plausible wrong answer", "..."],
      "evidence": {
        "kb": ["reference/operations.md (vote_operation)", "research/hive-core/findings/04-chain-evaluators.md (vote_evaluator)"],
        "source": ["libraries/chain/hive_evaluator_social.cpp:620-623"]
      },
      "applies": "HF19+ (current HF28)",
      "origin": "where the item came from (contrib note, findings part, hub facts)",
      "leak_risk": "claude-md"
    }
  ]
}
```

- `kind`: `trap` = a common misconception (the forbidden answer is what most people say);
  `lookup` = a specific fact (limit, authority level, field, block number); `reasoning` =
  needs two facts combined.
- `forbidden`: an answer that asserts any of these fails even if it also contains the expected
  facts.
- `evidence.source` is the `file:line` at the topic's pinned commit, as cited by the KB; the
  audit (`/forge-audit`) keeps those citations honest, so eval ground truth is source code,
  not the KB's prose.
- `leak_risk: "claude-md"` marks items whose one-line answer also appears in the repo's
  `CLAUDE.md` Key Facts. A baseline run inside this repository may see that file, so reports
  show results with and without these items.
- Files are plain JSON (validate with `python3 -m json.tool evals/<topic>.json`), ASCII only.

## Running

The producer skill `/forge-eval` (in `.claude/skills/forge-eval/`) runs the benchmark inside
an interactive Claude Code session with parallel subagents and writes `results/`. The
procedure, so any agent framework can replicate it:

1. **Baseline condition**: for each item, an agent with NO file or search tools answers the
   question from its own knowledge, in at most five sentences, stating uncertainty when unsure.
2. **KB condition**: the same model answers the same question with read-only access to this
   repository and the instruction to consult `CLAUDE.md`, `reference/` and
   `research/*/findings/` and to cite the files used.
3. **Grading**: a separate grader sees the question, `expected`, `forbidden`, and the two
   answers (labelled A/B in random order), and returns per answer: `pass` (contains the
   expected facts, asserts nothing forbidden), `fail`, or `abstain` (the answer says it does
   not know; counted separately because an honest "I don't know" beats a confident wrong
   answer). For the KB answer the grader also records whether a cited KB file exists.
4. **Report**: pass rate per condition, per topic and per kind; the list of KB-condition
   failures (each is a KB gap, a routing gap, or a bad item); and the abstain counts.

Both conditions use the same model and effort. Reports name the model and the date.

## Caveats

- The grader is an LLM; disagreements are resolved by a human reading the cited source.
- Items are derived from the KB, so a KB error would make its eval item wrong too. That is why
  every item carries a source citation and why `/forge-audit` runs against the pinned worktree.
- The benchmark measures "does the agent find and use verified knowledge", not model quality
  in general. Expect the baseline to move between model generations; the KB delta is the signal.

## Adding items

Every contrib correction, every reviewer finding and every "obvious once you know it" fact is
a candidate. Add it to the topic file with the next free id and a real citation; keep the
question as a developer would phrase it; make `expected` specific enough that a grader cannot
pass a vague answer.
