# /forge-eval

Run the KB accuracy benchmark in `evals/`: the same model answers every item without and with
the KB, a grader scores both, and a report lands in `evals/results/`. Runs entirely inside the
interactive session with subagents (no `claude -p`).

## Usage

```
/forge-eval [topic ...] [--items N] [--only-kb] [--only-baseline]
```

- `/forge-eval` runs all topics (`hive-core`, `wax`, `haf`, `hivemind`).
- `/forge-eval wax hivemind` runs a subset.
- `--items 10` samples the first N items per topic (smoke run).
- `--only-kb` / `--only-baseline` run one condition (e.g. to re-measure after a KB change
  without re-spending the baseline).

## Procedure

1. Load `evals/<topic>.json` for each topic in scope; validate with `python3 -m json.tool`.
   Collect the items (id, question, expected, forbidden, evidence, kind, leak_risk).
2. **Baseline condition.** Batch the questions (about 10 per subagent) and spawn one
   `general-purpose` subagent per batch with this instruction: "Answer each question from
   your own knowledge only. Do NOT read any file, do NOT search, do NOT use any tool. Answer
   in at most five sentences per question. If you are not sure, say so explicitly rather than
   guessing. Return a JSON array of {id, answer}." Record each answer verbatim.
3. **KB condition.** Same batches, one subagent per batch, instruction: "You are in the
   hive.support knowledge base checkout at <repo root>. For each question, consult
   `CLAUDE.md`, `reference/` (including `reference/tasks.md`, `reference/rules/`), and
   `research/*/findings/` as needed, then answer in at most five sentences, citing the KB
   file(s) you relied on. Do not read anything outside this checkout. Return a JSON array of
   {id, answer, cited_files}."
4. **Grading.** For each batch spawn one grader subagent (`general-purpose`, no file access
   needed) with, per item: question, expected, forbidden, and the two answers labelled A/B in
   a random order (record the mapping). Instruction: "For each answer return pass, fail or
   abstain. pass = contains the expected facts and asserts nothing in forbidden; fail =
   contradicts expected or asserts a forbidden statement; abstain = the answer explicitly
   declines or says it does not know (even if it also hedges a guess). Give a one-sentence
   reason. Return a JSON array of {id, A: {verdict, reason}, B: {verdict, reason}}." Unmap
   A/B back to baseline/KB. For KB answers also check that every cited file exists in the
   checkout (a cited file that does not exist is a hallucinated citation; note it).
5. **Report.** Write `evals/results/YYYY-MM-DD-<model>.md` with: run metadata (date, model,
   effort, topics, item counts, batch size); a pass/fail/abstain table per condition, per
   topic, per kind; the same table excluding `leak_risk` items; the list of every KB-condition
   non-pass with the grader's reason and a triage column (KB gap / routing gap / bad item /
   grader error); the list of baseline passes that the KB condition failed (regressions
   caused by the KB, the most important rows); hallucinated citations; and a short
   conclusion. Keep the raw per-item verdicts in a `## Per-item verdicts` appendix.
6. Print the headline numbers and the triage list.

## Rules

- Same model and effort for both conditions; name them in the report.
- Baseline subagents run inside this repository, so `CLAUDE.md` may be in their context;
  that is why items whose answer appears in `CLAUDE.md` Key Facts carry `leak_risk` and the
  report shows both totals. Do not try to "fix" the baseline by editing the eval items.
- The grader is an LLM. When the grader's verdict disagrees with your own reading, the
  cited source line decides; note the disagreement in the triage column.
- Every KB-condition failure triaged as a KB gap or routing gap becomes a `contrib/` note or
  a direct fix (maintainer's call), and the item stays in the set so the fix is measurable.
- Never edit `expected` to match an answer; edit it only when the cited source proves the
  item wrong.
- Spawn subagents in parallel (several Agent calls in one response); keep batches around 10
  items so a single bad subagent run does not lose everything.
