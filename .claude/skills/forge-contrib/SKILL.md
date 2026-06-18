# /forge-contrib

Process pending contributions against source code. Replaces
`tools/research.sh contrib`.

## Usage

```
/forge-contrib [topic]
```

Default topic: `hive-core`.

## Steps

1. List `contrib/<topic>/*.md` files (skip `.digested/`).
2. If none: report "no pending contribs" and stop.
3. Read `research/<topic>/.pinned` for the pinned SHA. Ensure worktree.
4. For each contrib file:
   a. Read it. Parse the frontmatter: Type, Affects, Source.
   b. Read the affected KB files (from the Affects field).
   c. If the Source field cites a `file:line`, read that source from the worktree.
   d. If Type is `cascade`: grep `reference/` and `research/<topic>/findings/`
      for the key terms from the contrib title to see the spread.
   e. Determine: **confirmed** (KB is wrong per the contrib), **refuted**
      (KB is correct, contrib misreads source), or **needs-info**.
   f. For confirmed: apply the minimal correction to the affected files.
   g. Archive the contrib to `contrib/<topic>/.digested/<filename>` with a
      `## Pipeline Resolution` section appended (disposition + reasoning).
   h. For needs-info: leave in place, append a `## Status` section.
5. Report what was processed.

## Rules

- Verify every contrib claim against actual source at the pinned commit.
  Never take a contrib at face value.
- For cascade-type contribs: check ALL locations where the error appears,
  not just the files listed in Affects.
- Maintainer edits to `reference/` and `research/` are direct — no MR
  needed for contrib-driven corrections.
