# Knowledge Base Contributions

This directory collects feedback from agents and community members. Contributions here are **inputs to the next knowledge base revision** — they are never applied directly but are investigated and incorporated during the next pipeline run.

## Who Can Contribute

- **hive-researcher agent**: Automatically writes notes when it discovers gaps or questions the KB can't answer
- **hive-reviewer agent**: Automatically writes notes when it finds inconsistencies between KB and actual code
- **Community members**: Anyone can write a contribution file manually

## How It Works

1. Write a `.md` file in `contrib/<topic>/` (e.g., `contrib/hive-core/my-finding.md`)
2. Follow the format below
3. Next time the KB is updated, your contribution will be:
   - Read and grouped by affected findings part
   - Injected as context into the analysis/verification prompts
   - Investigated and either incorporated or refuted with evidence
   - Archived to `contrib/<topic>/.digested/` after processing

## Contribution Format

```markdown
# <Short descriptive title>

- **Topic**: hive-core
- **Type**: correction | addition | question | inconsistency
- **Affects**: reference/operations.md, research/hive-core/findings/04-chain-evaluators.md
- **Source**: (optional) file:line in source repo, or URL, or "observed behavior"

## Description

<What you found, what's wrong, or what's missing. Be specific.>

## Evidence

<Source code citations, test output, API responses, or reasoning that supports your claim.>
```

## Naming Convention

```
YYYY-MM-DD-<source>-<slug>.md
```

Examples:
- `2026-04-08-researcher-dhf-funding-gap.md` — from hive-researcher agent
- `2026-04-09-reviewer-rc-mana-inconsistency.md` — from hive-reviewer agent
- `2026-04-10-user-transfer-edge-case.md` — from a community member

## Types

| Type | When to Use |
|------|------------|
| `correction` | A specific fact in the KB is wrong |
| `addition` | Something is missing from the KB that should be there |
| `question` | You're unsure about something and want it investigated |
| `inconsistency` | The KB says one thing but the code does another |

## Directory Structure

```
contrib/
├── README.md          ← This file
├── hive-core/
│   ├── *.md           ← Pending contributions
│   └── .digested/     ← Archived after pipeline processed them
├── haf/
│   └── ...
└── <topic>/
    └── ...
```

## Important

- **Do not edit files in `reference/` or `research/` directly.** The pipeline manages those.
- **Do not worry about perfect formatting.** The pipeline prompts will interpret your contribution regardless.
- **Be specific.** "The RC section seems wrong" is less useful than "rc.md says mana regenerates over 5 days but config.hpp:230 says HIVE_RC_REGEN_TIME = 432000 seconds = 5 days, confirmed correct" or "rc.md doesn't mention the max_rc_creation_adjustment parameter at rc_utility.cpp:89".
