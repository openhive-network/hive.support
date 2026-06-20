# /forge-expand

Bootstrap a brand-new library/topic in the KB: decide the version anchor, set up a
read-only source worktree, scaffold `research/<topic>/`, and produce the first findings
part - on a branch + draft MR. This is the "add a new library" entry point (e.g. wax,
HAF, hivemind). There was no `tools/research.sh` equivalent - expansion was a manual
bootstrap; this codifies it. Subsequent parts use `/forge-zoom`; the compact lookup
layer is distilled afterward (step 5).

## Usage

```
/forge-expand <topic> --source <repo-path> [--lang ts|py|both]
```

- `/forge-expand wax --source ~/workspace/hive/wax`
- `/forge-expand haf --source ~/workspace/hive/haf`

## Steps

### 1. Decide the version anchor (a user decision - ASK)

Source versioning is rarely obvious. Investigate, then confirm with the user via
AskUserQuestion - never guess, the anchor is the exact commit everything is verified
against:

- Tags/releases: `git -C <source> tag`, GitLab releases, npm/PyPI `latest`.
- Is the version **git-tag-driven** (manifest holds a build placeholder) or real in the
  manifest?
- Are there **multiple lineages** (e.g. a public semver line vs an internal RC line that
  only tracks a submodule)? Anchor to the public release a developer actually installs.
- Pick ONE exact release; record its **version string + full commit SHA**.

For multi-language libs, also confirm the **language emphasis** (`--lang`): which API to
lead with; the other is noted only where it diverges.

### 2. Pin + worktree

```bash
# research/<topic>/.pinned  -> two lines:  <version>\n<full-sha>
git -C <source> worktree add <repo-root>/workspace/<topic>/<short-sha> <full-sha>
```

`workspace/` is gitignored. If the source has submodules needed for citations (e.g.
proto), prefer committed/generated artifacts already in the worktree, or read the exact
submodule commit from a sibling clone via `git show <sha>:<path>` - avoid a heavy
submodule fetch unless genuinely required.

### 3. Scaffold `research/<topic>/`

- `README.md`: source repo + version anchor (+ SHA); a **versioning note**; the **scope**
  (document the library's OWN surface; cross-reference existing topics for protocol
  semantics rather than re-deriving them); the **part roadmap** (status table); and the
  method (read-only worktree, `file:line` citations, no build).
- `findings/` (empty); `prompts/` (optional).

### 4. Git ceremony + first part

```bash
git checkout -b expand/<topic> master
```

Research and write `findings/01-<area>.md` (start with architecture / entry points),
fully `file:line`-cited against the worktree; update the README status table.

```bash
git add research/<topic>/
git commit --author="Gandalf <gandalf@storm.pl>" \
  -m "expand(<topic>): bootstrap KB topic, anchor <version>, add part 01"
git push -u origin expand/<topic>
glab mr create --source-branch expand/<topic> --target-branch master --draft \
  --title "expand(<topic>): new KB topic" --no-editor
```

Keep the MR **draft**. Push subsequent parts (continued research, or `/forge-zoom` once
`.pinned` + findings exist) as commits to the same branch, then mark ready.

### 5. Distill reference (after all findings parts are done)

No automated step exists - hand-distill `reference/<topic>/` mirroring the hive-core
`reference/` structure: a `README.md` hub (navigation, key numbers, non-obvious facts)
plus by-area compact lookup docs (tables / cheat-sheets), each pointing to
`research/<topic>/findings/` for depth. Add a `reference/<topic>/` pointer to the
top-level `CLAUDE.md` Quick Reference. (Candidate for its own `/forge-distill` skill.)

### 6. Finalize

- Self-review the findings' citations before marking the MR ready (catches slips).
- Move the topic to "Complete" in the `CLAUDE.md` Research Coverage section.
- After merge, `/forge-publish` ships `research/<topic>/findings/` + `reference/` +
  `CLAUDE.md` to the consumer repo.

## Rules

- Cite source `file:line` for every substantive claim, against the pinned worktree.
- The anchor is a user decision - confirm it; never guess.
- Document the library's surface, not the protocol - cross-reference existing topics
  (don't re-derive operations/consensus/economics).
- Never speculate about current chain state.
- Default topic source lives under `~/workspace/hive/<repo>`.
