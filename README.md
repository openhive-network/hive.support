# hive.support

Source-verified knowledge base for the [Hive blockchain](https://hive.io), built for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Give your AI coding assistant accurate, source-level knowledge of Hive's operations, consensus, economics, RC system, API, and hardfork history — all verified against the actual C++ source code.

## Verify. Correct. Evolve.

This knowledge base is built by reading Hive's C++ source code directly — not by copying docs or trusting wikis. But both carbon-based and silicon-based contributors make mistakes. A function gets misread. A hardfork condition gets overlooked. An edge case slips through.

That's the point of the tool: **use the KB to verify code, use the code to verify the KB.** When something doesn't match, write it down in `contrib/` — the next iteration gets closer to truth.

Every claim in `reference/` traces back to a `file:line` citation in `research/`. If a citation is wrong, the fix is one contribution away.

## Quick Start

Clone this repo alongside your Hive project:

```bash
git clone https://gitlab.syncad.com/hive/hive.support.git
```

Then tell Claude Code about it — either add it to your project's `CLAUDE.md`:

```markdown
For Hive blockchain reference, read files in ../hive.support/
Start with ../hive.support/CLAUDE.md for navigation.
```

Or add it as a git submodule:

```bash
git submodule add https://gitlab.syncad.com/hive/hive.support.git
```

Claude Code will read `CLAUDE.md` automatically and navigate the knowledge base from there.

## What's Inside

| Directory | What | For |
|-----------|------|-----|
| `reference/` | Compact lookup tables | Quick answers (fields, constants, limits) |
| `research/hive-core/findings/` | Detailed analysis with `file:line` citations | Deep investigation |
| `.claude/agents/` | Hive-specialized agents | Automated research and code review |
| `.claude/skills/` | Slash commands | `/hive-lookup`, `/hive-verify`, `/hive-op` |
| `contrib/` | Feedback directory | Report errors, gaps, or questions |

## Agents

- **hive-researcher** — Answers Hive questions using the KB. Writes notes to `contrib/` when it finds gaps.
- **hive-reviewer** — Reviews code that interacts with Hive. Checks operations, authority, RC, economics against the KB.

## Skills

| Command | What it does |
|---------|-------------|
| `/hive-lookup <query>` | Quick reference lookup |
| `/hive-verify <claim>` | Verify a claim against the KB |
| `/hive-op <name>` | Full documentation for an operation |

## Coverage

**hive-core** (complete) — 10-part source-level analysis of hived, verified against release `1.28.6`.

Covers: operations, validation, evaluators, state objects, consensus, economics, RC, hardforks, and API.

Not yet covered: HAF, Wax, Hivemind, P2P protocol.

## How This Repo Works

This is a **consumer repo** — a read-only published snapshot of the knowledge base. You use it, you don't build it.

```
Producer (private)                Consumer (this repo)
+-----------------------+         +-----------------------+
| Source code analysis  |         | reference/            |
| Research pipeline     |--publish-->  research/findings/ |
| Verification          |         | .claude/ agents+skills|
| Contrib digestion     |<-feedback--  contrib/           |
+-----------------------+         +-----------------------+
```

- **reference/** and **research/** are generated and verified by the producer pipeline. Don't edit them directly.
- **contrib/** is the feedback channel. Found something wrong? Write a file there. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The knowledge base content documents the behavior of [hive/hive](https://gitlab.syncad.com/hive/hive), which is MIT-licensed open source software.
