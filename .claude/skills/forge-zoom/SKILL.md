# /forge-zoom

Create a new sub-area deep-dive as a new findings part, with branch+MR
workflow. Replaces `tools/research.sh zoom`.

## Usage

```
/forge-zoom <topic> --area <name> --entry <file> [--entry <file>...] [--no-branch]
```

- `/forge-zoom hive-core --area rc-delegation --entry libraries/chain/rc/`
- `/forge-zoom hive-core --area escrow-gaps --entry libraries/chain/hive_evaluator_transfer.cpp --no-branch`

Default topic: `hive-core`.

## Steps

### 1. Setup

- Read `research/<topic>/.pinned` for the pinned SHA.
- Ensure worktree at `workspace/<topic>/<short-sha>/`.
- Determine next part number: highest existing `NN-` prefix in `findings/` + 1.
- The new part slug is the `--area` value.

### 2. Git ceremony (unless --no-branch)

```bash
git checkout -b zoom/<topic>/<area> master
```

### 3. Research

Read each entry file/directory from the worktree. Map out: data structures,
key functions, state transitions, invariants, hardfork-conditional behavior,
error paths.

Write findings to `research/<topic>/findings/<NN>-<area>.md` with standard
structure:

```markdown
# Findings: <area>

## Summary
[2-3 sentences]

## Key Discoveries
### 1. [Title]
- **What**: [detail]
- **Where**: `file.cpp:123`
- **Impact**: [why it matters]

## [Area-specific sections]

## Code References
| Component | File | Line | Purpose |
|-----------|------|------|---------|

## Cross-references to existing parts

## Open Questions
```

Add a cross-reference pointer to `findings/00-consolidated.md`.

### 4. Git ceremony (unless --no-branch)

```bash
git add research/<topic>/findings/ reference/
git commit --author="Gandalf <gandalf@storm.pl>" -m "zoom(<topic>/<area>): add deep-dive"
git push -u origin zoom/<topic>/<area>
glab mr create --source-branch zoom/<topic>/<area> --target-branch master \
    --title "zoom: <topic> <area>" --remove-source-branch --no-editor
git checkout master
```

## Rules

- Cite `file:line` for every substantive finding.
- Stay within the area scope. If you find material for a different area,
  note it under Open Questions.
- Never speculate about current chain state.
- Use the standard 4-column Code References table format:
  `| Component | File | Line | Purpose |`
