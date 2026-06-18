# /forge-audit

Audit KB citations against source code at the pinned commit. Replaces the
`tools/research.sh verify` mode — no `claude -p` calls; runs entirely
within the interactive session using subagents.

## Usage

```
/forge-audit [topic] [--part N]
```

- `/forge-audit` or `/forge-audit hive-core` — audit all parts
- `/forge-audit hive-core --part 01` — audit only part 01

Default topic: `hive-core`.

## How it works

1. Read `research/<topic>/.pinned` for the pinned SHA.
2. Ensure a git worktree exists at `workspace/<topic>/<short-sha>/`
   (create with `git -C ~/workspace/hive/<topic> worktree add ...` if missing).
3. List findings files in scope: `research/<topic>/findings/[0-9][0-9]-*.md`
   (or just the specified `--part`).
4. For EACH findings file, spawn an Agent (subagent) that:
   - Reads the findings file
   - Finds the `## Code References` table (any format — 2-col, 3-col, 4-col)
   - For each row with a file path and line number:
     - Resolves the file path in the worktree (try exact path, then prefix with
       the Source Location from the sibling prompt, then basename search)
     - Reads the cited lines (±3 lines context) from the worktree
     - Compares the source against the table row's claim/purpose
     - Classifies: confirmed / drifted / broken / unparseable
   - Returns a structured report: list of citations with status + reason
5. Aggregate all subagent reports into `research/<topic>/verification.md`.
6. Print summary (confirmed / drifted / broken / unparseable counts).

## Subagent prompt template

For each part, spawn with:

```
Audit the Code References citations in <findings_file> against source at
<worktree_path> (pinned commit <sha>).

For each citation row in the Code References table:
1. Resolve the file path in the worktree (check exact path, then try
   prefixing with the Source Location from the sibling prompt at
   research/<topic>/prompts/<part>.md, then search by basename).
2. Read the cited line range (±3 lines context).
3. Compare the source excerpt against the claim/purpose text.
4. Classify: confirmed (source supports claim), drifted (moved or
   minor mismatch), broken (claim contradicts source), unparseable
   (file not found or ambiguous).

Return your results as a markdown section:

### Part NN — <part-name>

| # | File:Line | Status | Reason |
|---|-----------|--------|--------|
| 1 | path:line | confirmed | one sentence |
| 2 | path:line | drifted | one sentence |
...

Summary: X confirmed, Y drifted, Z broken, W unparseable
```

## Rules

- Each subagent gets its own context — no bloat in the main session.
- Spawn subagents in parallel where possible (multiple Agent tool calls
  in one response).
- The worktree is read-only for verification — do not modify source files.
- Do not speculate about current chain state. Only compare code against claims.
- Use `model: haiku` for subagents if available (simple comparison task).
- Write verification.md in the same format as the existing report (header
  with topic/pinned/date/count, then per-citation entries, then summary table).
