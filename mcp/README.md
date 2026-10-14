# hive.support MCP server

Serves this knowledge base to any MCP client (Claude Code, Claude Desktop, Cursor, Copilot,
custom agents) so an agent that cannot clone a repository can still read verified Hive
knowledge on demand. One file, Python 3.8+ standard library only, read-only, no network
calls, no LLM inside (the consuming agent is the LLM).

```
python3 mcp/hive_support_mcp.py                        # stdio transport
python3 mcp/hive_support_mcp.py --http 127.0.0.1:8765  # Streamable HTTP on POST /mcp
python3 mcp/hive_support_mcp.py --selftest             # in-process checks
python3 mcp/test_mcp.py                                # end-to-end test of both transports
```

The KB root defaults to the parent of this directory; override with `--root PATH` or
`HIVE_SUPPORT_ROOT`.

## Tools

| Tool | Use it for |
|------|-----------|
| `hive_index` | Orientation: topics, lookup tables, helper files. Call once. |
| `hive_tasks(query)` | A developer task ("broadcast a transfer", "build a HAF app") -> ordered reading path, rules, verification recipe. Without `query`: the task list. |
| `hive_operation(name)` | One protocol operation: fields, authority, validation, evaluator, hardfork notes, pointers into findings, wax builders, related rules. |
| `hive_rules(query, topic)` | Verified best-practice rules and traps with evidence and review hints. No args: the list. |
| `hive_search(query, scope, max_results)` | Regex search; `scope` = `reference` (default), `findings`, `rules`, `all`. Returns file, line, enclosing headings. |
| `hive_read(path, heading, max_chars)` | A KB file or one section by heading. |

Every KB markdown file is also exposed as an MCP resource `hive-support://<relative path>`.

Responses are plain text, capped (default 24000 chars) with a truncation note, and always
name the KB file and lines they came from so the agent can cite them.

## Client configuration

Claude Code (project scope, `.mcp.json` in the consuming project, or `claude mcp add`):

```json
{
  "mcpServers": {
    "hive-support": {
      "command": "python3",
      "args": ["/absolute/path/to/hive.support/mcp/hive_support_mcp.py"]
    }
  }
}
```

```
claude mcp add hive-support -- python3 /absolute/path/to/hive.support/mcp/hive_support_mcp.py
```

Claude Desktop (`claude_desktop_config.json`) and Cursor (`.cursor/mcp.json`) take the same
`mcpServers` object.

Remote (one shared instance for a team or a bot): run `--http HOST:PORT` behind your own
TLS/auth proxy and point clients at `http://HOST:PORT/mcp` (Claude Code:
`claude mcp add --transport http hive-support http://HOST:PORT/mcp`). The server offers no
server-initiated streams (GET returns 405); it answers every POST with a JSON body.

## Security posture

- Read-only: no tool writes anything. Paths are confined to the KB root and to `.md` files.
- No dependencies, no package installs, no outbound network. Audit the one file.
- Safe to expose publicly in read-only form: the KB is public; still rate-limit at the proxy.

## Updating

The server has no state. Pull the KB (`git pull`) and restart; content is re-read on change.
