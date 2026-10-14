# hive.support

Source-verified knowledge base for the [Hive blockchain](https://hive.io), built for AI coding agents ([Claude Code](https://docs.anthropic.com/en/docs/claude-code) first, any MCP client second).

Give your agent accurate, source-level knowledge of Hive's protocol (operations, consensus, economics, RC, API, hardfork history), the wax client library, the HAF indexing framework and the hivemind social API, all verified against the actual source code at pinned releases.

## Verify. Correct. Evolve.

This knowledge base is built by reading the source code directly, not by copying docs or trusting wikis. But both carbon-based and silicon-based contributors make mistakes. A function gets misread. A hardfork condition gets overlooked. An edge case slips through.

That's the point of the tool: **use the KB to verify code, use the code to verify the KB.** When something doesn't match, write it down in `contrib/`; the next iteration gets closer to truth.

Every claim in `reference/` traces back to a `file:line` citation in `research/`. If a citation is wrong, the fix is one contribution away.

## Quick Start

Clone this repo alongside your Hive project:

```bash
git clone https://gitlab.syncad.com/hive/hive.support.git
```

Then tell Claude Code about it, either in your project's `CLAUDE.md`:

```markdown
For Hive blockchain reference, read files in ../hive.support/
Start with ../hive.support/CLAUDE.md for navigation.
```

or as a git submodule:

```bash
git submodule add https://gitlab.syncad.com/hive/hive.support.git
```

Claude Code reads `CLAUDE.md` automatically and navigates the knowledge base from there.

Any other MCP client (Claude Desktop, Cursor, a hosted agent) can use the bundled server instead of cloning; see [mcp/README.md](mcp/README.md):

```bash
python3 mcp/hive_support_mcp.py            # stdio, no dependencies, read-only
```

## What's Inside

| Directory | What | For |
|-----------|------|-----|
| `reference/` | Compact lookup tables per topic | Quick answers (fields, constants, limits, API methods) |
| `reference/tasks.md` | Developer task -> reading path | "I need to do X with Hive, what do I read?" |
| `reference/rules/` | Verified best-practice rules and traps with evidence | Code review, writing correct code |
| `reference/verify.md` | Claim type -> the tool that checks it | Replacing "I think" with "I ran it" |
| `research/*/findings/` | Detailed analysis with `file:line` citations | Deep investigation |
| `evals/` | Benchmark questions with verified answers, plus run reports | Measuring whether the KB helps an agent |
| `mcp/` | Dependency-free MCP server serving this KB | Agents that cannot clone a repo |
| `.claude/agents/` | Hive-specialized agents | Automated research and code review |
| `.claude/skills/` | Slash commands | `/hive-lookup`, `/hive-verify`, `/hive-op` |
| `contrib/` | Feedback directory | Report errors, gaps, or questions |

## Agents

- **hive-researcher** answers Hive questions using the KB and writes notes to `contrib/` when it finds gaps.
- **hive-reviewer** reviews code that interacts with Hive: rules first, then operations, authority, RC, economics, indexing and social-API semantics against the KB.

## Skills

| Command | What it does |
|---------|-------------|
| `/hive-lookup <query>` | Quick reference lookup (any topic) |
| `/hive-verify <claim>` | Verify a claim against the KB |
| `/hive-op <name>` | Full documentation for an operation |

## Coverage

| Topic | Anchor | Depth |
|-------|--------|-------|
| **hive-core** (hived: protocol, consensus, economics, RC, API, hardforks) | release `1.28.7` | 18 findings parts + 8 reference docs |
| **wax** (client library, TypeScript-first) | `2.0.2` | 7 findings parts + 5 reference docs |
| **HAF** (Hive Application Framework, SQL indexing) | `1.28.6` | 7 findings parts + 5 reference docs |
| **hivemind** (social API: posts, follows, communities, notifications) | `1.28.6` | 8 findings parts + 6 reference docs |

Not yet covered: P2P protocol.

## How This Repo Works

This is a **consumer repo**, a read-only published snapshot of the knowledge base. You use it, you don't build it.

```
Producer (private)                Consumer (this repo)
+-----------------------+         +-----------------------+
| Source code analysis  |         | reference/ + rules    |
| Research pipeline     |--publish-->  research/findings/ |
| Verification + evals  |         | evals/ mcp/ .claude/  |
| Contrib digestion     |<-feedback--  contrib/           |
+-----------------------+         +-----------------------+
```

- **reference/** and **research/** are generated and verified by the producer pipeline. Don't edit them directly.
- **contrib/** is the feedback channel. Found something wrong? Write a file there. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The knowledge base content documents the behavior of [hive/hive](https://gitlab.syncad.com/hive/hive) and its ecosystem projects, which are MIT-licensed open source software.
