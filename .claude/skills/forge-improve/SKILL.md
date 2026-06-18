# /forge-improve

Deepen an existing findings part interactively with branch+MR workflow.
Replaces `tools/research.sh improve` — no nested Claude process; runs
the research directly in this session.

## Usage

```
/forge-improve <topic> --part <N> [--no-branch]
```

- `/forge-improve hive-core --part 08` — improve part 08 with branch+MR
- `/forge-improve hive-core --part 04 --no-branch` — improve directly on current branch

Default topic: `hive-core`.

## Steps

### 1. Setup

- Read `research/<topic>/.pinned` for the pinned SHA.
- Ensure worktree exists at `workspace/<topic>/<short-sha>/`.
- Find the findings file: `research/<topic>/findings/<NN>-*.md`
- Find the original prompt: `research/<topic>/prompts/<NN>-*.md` (if exists)

### 2. Git ceremony (unless --no-branch)

```bash
git checkout -b improve/<topic>/<NN>-<slug> master
```

### 3. Research (the actual work)

Read the findings file. Identify gaps:
- Open Questions section
- Shallow sections (short paragraphs with no file:line citations)
- Questions from the original prompt that were answered briefly

For each gap: read the relevant source files from the worktree. Deepen
the findings with source-verified content. Add file:line citations.

Rewrite the findings file in place. Update the Code References table
with any new citations. If the improvement affects tabled facts in
`reference/*.md`, apply those edits too.

### 4. Git ceremony (unless --no-branch)

```bash
git add research/<topic>/findings/ reference/
git commit --author="Gandalf <gandalf@storm.pl>" -m "improve(<topic>/<slug>): deepen findings"
git push -u origin improve/<topic>/<NN>-<slug>
glab mr create --source-branch improve/<topic>/<NN>-<slug> --target-branch master \
    --title "improve: <topic> part <NN> (<slug>)" --remove-source-branch --no-editor
git checkout master
```

## Rules

- Cite source `file:line` for every substantive new claim.
- The pinned commit is the source of truth.
- Never speculate about current chain state (block heights, hardfork
  activation status). Only state what the code defines.
- Do not pad. If the part is well-covered, say so.
- When Claude suggests "commit the changes" or similar git operations
  at the end: do NOT ask — just do the git ceremony directly.
