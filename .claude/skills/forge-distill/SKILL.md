# /forge-distill

Produce (or refresh) the compact `reference/<topic>/` lookup layer from a topic's
findings. This is the step that turns deep, cited `research/<topic>/findings/` into the
quick-answer tables a consumer reaches for first. Run it after a topic's findings parts
are complete, or to refresh after findings change. There was no `tools/research.sh`
equivalent - `reference/` was historically hand-authored; this codifies it.

## Usage

```
/forge-distill <topic> [--no-branch]
```

- `/forge-distill wax`
- `/forge-distill hive-core`   (refresh an existing layer)

## Steps

### 1. Setup

- Read `research/<topic>/.pinned` for the version anchor (the reference layer states it).
- Read every `research/<topic>/findings/*.md`. Harvest each part's key tables, numbers,
  and "Notable findings" / gotchas.

### 2. Git ceremony (unless --no-branch)

```bash
git checkout -b distill/<topic> master
```

### 3. Distill into `reference/<topic>/`

- `README.md` - the hub:
  - a **Quick Lookup** table ("I need to know X -> doc"),
  - **Key Numbers**,
  - **Important Non-Obvious Facts** - pull every gotcha from the findings' Notable-findings
    sections up here,
  - the version anchor, and a pointer to `../../research/<topic>/findings/` for depth.
- **By-area compact docs** - one per natural area (not 1:1 with findings parts). Each is
  **tables and cheat-sheets**, not prose: signatures, options, enums, defaults, file
  pointers. Lead with the most common lookups; point to the matching findings part for
  detail.

Mirror the existing `reference/` style (hive-core at top level; wax under
`reference/wax/`). Keep it dense - depth lives in findings; reference is the index.

### 4. Wire into navigation

Add a `reference/<topic>/` pointer to the top-level `CLAUDE.md` Quick Reference. For a
client library, separate the **protocol** layer (hive-core) from the **client** layer.

### 5. Git ceremony (unless --no-branch)

```bash
git add reference/<topic>/ CLAUDE.md
git commit --author="Gandalf <gandalf@storm.pl>" -m "distill(<topic>): reference/ lookup layer"
git push -u origin distill/<topic>
glab mr create --source-branch distill/<topic> --target-branch master \
    --title "distill: <topic> reference layer" --remove-source-branch --no-editor
git checkout master
```

After merge, `/forge-publish` ships `reference/<topic>/` to the consumer.

## Rules

- Compact only - tables, cheat-sheets, key signatures. No re-derivation; cross-reference
  the findings for everything deep.
- Every "non-obvious fact" / gotcha from the findings belongs in the README hub.
- Stay anchored to the same `.pinned` version the findings used; state it.
- Distillation is one-directional: read `research/findings/`, write `reference/` - do not
  edit findings here.
- Point to the findings part (or `file:line`) where a reader goes for detail.
