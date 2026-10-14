#!/usr/bin/env python3
"""hive.support MCP server - serves the source-verified Hive knowledge base to any MCP client.

Dependency-free (Python 3.8+ standard library only). Read-only. No LLM inside: the
consuming agent is the LLM; this server only finds and returns verified KB text.

Transports:
  python3 mcp/hive_support_mcp.py                       # stdio (Claude Code, Claude Desktop, Cursor, ...)
  python3 mcp/hive_support_mcp.py --http 127.0.0.1:8765 # Streamable HTTP (POST /mcp, JSON responses)
  python3 mcp/hive_support_mcp.py --root /path/to/hive.support
  python3 mcp/hive_support_mcp.py --selftest            # in-process smoke test, exit code != 0 on failure

Tools (see TOOLS below): hive_index, hive_tasks, hive_operation, hive_rules, hive_search, hive_read.
Resources: every KB markdown file as hive-support://<relative path>.
"""

import argparse
import json
import os
import re
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

SERVER_NAME = "hive-support"
SERVER_VERSION = "0.1.0"
SUPPORTED_PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]
DEFAULT_MAX_CHARS = 24000

SERVER_INSTRUCTIONS = (
    "hive.support: a source-verified, release-anchored knowledge base about the Hive blockchain "
    "(hived protocol, wax client library, HAF indexing framework, hivemind social API). "
    "Every claim cites KB files that in turn cite source file:line. Use hive_tasks to get a reading "
    "path for a developer task, hive_operation for one protocol operation, hive_rules before reviewing "
    "code, hive_search for anything else, and hive_read to pull a file or section. Cite the KB paths "
    "you used. Facts not found here are not verified by this KB - say so instead of guessing."
)


# ----------------------------------------------------------------------------
# Knowledge base access
# ----------------------------------------------------------------------------

class Section:
    __slots__ = ("level", "title", "start", "end")

    def __init__(self, level: int, title: str, start: int, end: int):
        self.level = level
        self.title = title
        self.start = start  # 0-based line index of the heading
        self.end = end      # exclusive


class KB:
    """Indexes the markdown files of a hive.support checkout."""

    SCOPES = {
        "reference": ["reference"],
        "rules": ["reference/rules"],
        "findings": ["research"],
        "all": ["reference", "research", "CLAUDE.md", "CONTRIBUTING.md", "README.md"],
    }

    def __init__(self, root: str):
        self.root = os.path.realpath(root)
        if not os.path.isdir(os.path.join(self.root, "reference")):
            raise SystemExit("KB root %r has no reference/ directory" % self.root)
        self._cache = {}  # type: Dict[str, Tuple[float, List[str], List[Section]]]

    # -- files -----------------------------------------------------------------

    def files(self, scope: str = "all") -> List[str]:
        """Relative paths of markdown files in scope, sorted."""
        roots = self.SCOPES.get(scope)
        if roots is None:
            raise ValueError("unknown scope %r (use one of %s)" % (scope, ", ".join(sorted(self.SCOPES))))
        out = []
        for rel in roots:
            abs_path = os.path.join(self.root, rel)
            if os.path.isfile(abs_path) and rel.endswith(".md"):
                out.append(rel)
                continue
            if not os.path.isdir(abs_path):
                continue
            for dirpath, dirnames, filenames in os.walk(abs_path):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                if scope == "findings" and os.path.basename(dirpath) not in ("findings",) and dirpath != abs_path:
                    # only research/<topic>/findings/*.md (and verification.md at topic level)
                    pass
                for fn in sorted(filenames):
                    if not fn.endswith(".md"):
                        continue
                    relp = os.path.relpath(os.path.join(dirpath, fn), self.root)
                    if scope == "findings" and "/findings/" not in relp and not relp.endswith("verification.md"):
                        continue
                    out.append(relp)
        return sorted(set(out))

    def _safe_path(self, rel: str) -> str:
        rel = rel.strip().lstrip("/")
        abs_path = os.path.realpath(os.path.join(self.root, rel))
        if not abs_path.startswith(self.root + os.sep) and abs_path != self.root:
            raise ValueError("path escapes the KB root")
        if not abs_path.endswith(".md"):
            raise ValueError("only .md files are served")
        if not os.path.isfile(abs_path):
            raise ValueError("no such KB file: %s" % rel)
        return abs_path

    def load(self, rel: str) -> Tuple[List[str], List[Section]]:
        abs_path = self._safe_path(rel)
        mtime = os.path.getmtime(abs_path)
        cached = self._cache.get(abs_path)
        if cached and cached[0] == mtime:
            return cached[1], cached[2]
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
        sections = parse_sections(lines)
        self._cache[abs_path] = (mtime, lines, sections)
        return lines, sections

    # -- queries ---------------------------------------------------------------

    def read(self, rel: str, heading: Optional[str] = None, max_chars: int = DEFAULT_MAX_CHARS) -> str:
        lines, sections = self.load(rel)
        if heading:
            sec = find_section(sections, heading)
            if sec is None:
                titles = ", ".join(s.title for s in sections[:60])
                return "No heading matching %r in %s. Headings: %s" % (heading, rel, titles)
            text = "\n".join(lines[sec.start:sec.end])
            header = "%s (lines %d-%d)\n\n" % (rel, sec.start + 1, sec.end)
            return truncate(header + text, max_chars)
        return truncate("%s (%d lines)\n\n%s" % (rel, len(lines), "\n".join(lines)), max_chars)

    def search(self, query: str, scope: str = "reference", max_results: int = 20,
               max_chars: int = DEFAULT_MAX_CHARS) -> str:
        try:
            rx = re.compile(query, re.IGNORECASE)
        except re.error:
            rx = re.compile(re.escape(query), re.IGNORECASE)
        hits = []  # (rel, lineno, heading_chain, line)
        for rel in self.files(scope):
            lines, sections = self.load(rel)
            chain = HeadingChain(sections)
            for i, line in enumerate(lines):
                if rx.search(line):
                    hits.append((rel, i + 1, chain.at(i), line.strip()))
                    if len(hits) >= max_results * 4:
                        break
            if len(hits) >= max_results * 4:
                break
        if not hits:
            return "No matches for %r in scope %s." % (query, scope)
        # Rank: reference hubs first, then fewer hits per file first; keep file order stable otherwise.
        per_file = {}  # type: Dict[str, int]
        for h in hits:
            per_file[h[0]] = per_file.get(h[0], 0) + 1
        hits.sort(key=lambda h: (0 if h[0].startswith("reference/") else 1, h[0], h[1]))
        shown = hits[:max_results]
        out = ["%d match(es) for %r in scope %s (showing %d). Use hive_read(path, heading) for a section." %
               (len(hits), query, scope, len(shown)), ""]
        current = None
        for rel, lineno, chain, line in shown:
            if rel != current:
                out.append("== %s (%d hit(s))" % (rel, per_file[rel]))
                current = rel
            where = " > ".join(chain) if chain else "(top)"
            out.append("  :%d [%s] %s" % (lineno, where, clip(line, 220)))
        return truncate("\n".join(out), max_chars)

    def operation(self, name: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
        base = name.strip().lower()
        base = re.sub(r"_operation$", "", base)
        op = base + "_operation"
        rel = "reference/operations.md"
        lines, sections = self.load(rel)
        sec = None
        for s in sections:
            if s.level == 3 and s.title.lower().startswith(op + " "):
                sec = s
                break
            if s.level == 3 and s.title.lower() == op:
                sec = s
                break
        out = []
        if sec is None:
            # maybe a virtual op or an unknown name: fall back to the index table rows mentioning it
            rows = [l for l in lines if ("| " + base + " |") in l.lower() or ("| " + op + " |") in l.lower()]
            if rows:
                out.append("No per-operation section for %s in %s; index rows:" % (op, rel))
                out.extend(rows)
            else:
                return ("No operation named %r in %s. Virtual operations are listed in the index table; "
                        "try hive_search(%r, scope='all')." % (op, rel, base))
        else:
            out.append("%s (lines %d-%d)" % (rel, sec.start + 1, sec.end))
            out.append("")
            out.extend(lines[sec.start:sec.end])
        # index table row
        for l in lines:
            if re.match(r"^\|\s*\d+\s*\|\s*%s\s*\|" % re.escape(base), l):
                out.append("")
                out.append("Index row: " + l.strip())
                break
        # deeper material: findings parts mentioning the operation (hive-core) and wax builder mentions
        pointers = []
        for relf in self.files("findings"):
            if not relf.startswith("research/hive-core/"):
                continue
            flines, fsections = self.load(relf)
            chain = HeadingChain(fsections)
            count = 0
            first = None
            for i, l in enumerate(flines):
                if op in l:
                    count += 1
                    if first is None:
                        first = (i + 1, " > ".join(chain.at(i)))
            if count:
                pointers.append("  %s: %d mention(s), first at :%d [%s]" % (relf, count, first[0], first[1]))
        if pointers:
            out.append("")
            out.append("Deeper (research findings mentioning %s):" % op)
            out.extend(pointers[:12])
        wax_hits = []
        for relw in ("reference/wax/operations.md", "reference/wax/README.md"):
            try:
                wlines, _ = self.load(relw)
            except ValueError:
                continue
            for i, l in enumerate(wlines):
                if base in l.lower():
                    wax_hits.append("  %s:%d %s" % (relw, i + 1, clip(l.strip(), 160)))
        if wax_hits:
            out.append("")
            out.append("wax (client library) mentions:")
            out.extend(wax_hits[:8])
        rules = self.rules(query=base, max_chars=4000, titles_only=True)
        if not rules.startswith("No "):
            out.append("")
            out.append("Rules mentioning it:")
            out.append(rules)
        return truncate("\n".join(out), max_chars)

    def rules(self, query: Optional[str] = None, topic: Optional[str] = None,
              max_chars: int = DEFAULT_MAX_CHARS, titles_only: bool = False) -> str:
        rules_dir = os.path.join(self.root, "reference", "rules")
        if not os.path.isdir(rules_dir):
            return "No rules layer in this KB checkout (reference/rules/ missing)."
        rx = None
        if query:
            try:
                rx = re.compile(query, re.IGNORECASE)
            except re.error:
                rx = re.compile(re.escape(query), re.IGNORECASE)
        out = []
        total = 0
        for fn in sorted(os.listdir(rules_dir)):
            if not fn.endswith(".md") or fn == "README.md":
                continue
            t = fn[:-3]
            if topic and t != topic:
                continue
            rel = "reference/rules/" + fn
            lines, sections = self.load(rel)
            for s in sections:
                if s.level != 2 or ":" not in s.title:
                    continue
                body = "\n".join(lines[s.start:s.end]).rstrip()
                if rx and not rx.search(body):
                    continue
                total += 1
                if titles_only or not query:
                    out.append("- %s  (%s:%d)" % (s.title, rel, s.start + 1))
                else:
                    out.append("%s:%d\n%s\n" % (rel, s.start + 1, body))
        if not out:
            return "No rules match%s%s." % (" query %r" % query if query else "", " in topic %r" % topic if topic else "")
        head = "%d rule(s)%s. Each rule cites KB sections and source file:line; read the cited sections before relying on it." % (
            total, " matching %r" % query if query else "")
        if not query and not titles_only:
            head += " Call hive_rules(query=...) for full text."
        return truncate(head + "\n" + "\n".join(out), max_chars)

    def tasks(self, query: Optional[str] = None, max_chars: int = DEFAULT_MAX_CHARS) -> str:
        rel = "reference/tasks.md"
        try:
            lines, sections = self.load(rel)
        except ValueError:
            return "No task index in this KB checkout (reference/tasks.md missing)."
        tasks = [s for s in sections if s.level == 2]
        if not query:
            out = ["%d developer tasks in %s. Call hive_tasks(query=...) for the reading path of one." % (len(tasks), rel)]
            for s in tasks:
                out.append("- %s" % s.title)
            return truncate("\n".join(out), max_chars)
        try:
            rx = re.compile(query, re.IGNORECASE)
        except re.error:
            rx = re.compile(re.escape(query), re.IGNORECASE)
        matched = []
        for s in tasks:
            body = "\n".join(lines[s.start:s.end])
            score = 2 if rx.search(s.title) else (1 if rx.search(body) else 0)
            if score:
                matched.append((score, s))
        if not matched:
            return "No task matches %r. Tasks: %s" % (query, "; ".join(s.title for s in tasks))
        matched.sort(key=lambda m: (-m[0], m[1].start))
        out = []
        for _, s in matched[:3]:
            out.append("%s (lines %d-%d)\n%s\n" % (rel, s.start + 1, s.end, "\n".join(lines[s.start:s.end]).rstrip()))
        return truncate("\n".join(out), max_chars)

    def index(self, max_chars: int = DEFAULT_MAX_CHARS) -> str:
        out = ["hive.support KB at %s" % self.root, ""]
        try:
            lines, sections = self.load("reference/README.md")
            sec = find_section(sections, "Quick Lookup")
            if sec:
                out.append("reference/README.md > Quick Lookup:")
                out.extend(lines[sec.start:sec.end])
                out.append("")
        except ValueError:
            pass
        for topic, hub in (("wax", "reference/wax/README.md"), ("haf", "reference/haf/README.md"),
                           ("hivemind", "reference/hivemind/README.md")):
            try:
                lines, sections = self.load(hub)
            except ValueError:
                continue
            sec = find_section(sections, "Quick Lookup")
            first = next((l for l in lines if l.strip()), "")
            out.append("%s (%s):" % (hub, clip(first.lstrip("# "), 100)))
            if sec:
                out.extend(l for l in lines[sec.start + 1:sec.end] if l.startswith("|") and "---" not in l)
            out.append("")
        extras = []
        for rel, label in (("reference/tasks.md", "task -> reading-path index"),
                           ("reference/rules/README.md", "rules layer (reviewer checklist)"),
                           ("reference/verify.md", "verification recipes (claim -> tool)")):
            if os.path.isfile(os.path.join(self.root, rel)):
                extras.append("- %s: %s" % (rel, label))
        if extras:
            out.append("Agent helpers:")
            out.extend(extras)
            out.append("")
        counts = {}
        for rel in self.files("findings"):
            topic = rel.split("/")[1] if rel.count("/") >= 2 else "?"
            counts[topic] = counts.get(topic, 0) + 1
        out.append("Research findings (deep, file:line-cited): " +
                   ", ".join("%s: %d files" % (t, n) for t, n in sorted(counts.items())))
        out.append("Reference files: %d. Tools: hive_tasks, hive_operation, hive_rules, hive_search, hive_read." %
                   len(self.files("reference")))
        return truncate("\n".join(out), max_chars)


# ----------------------------------------------------------------------------
# Markdown helpers
# ----------------------------------------------------------------------------

HEADING_RX = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def parse_sections(lines: List[str]) -> List[Section]:
    sections = []  # type: List[Section]
    in_fence = False
    for i, line in enumerate(lines):
        if line.startswith("```") or line.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RX.match(line)
        if m:
            sections.append(Section(len(m.group(1)), m.group(2).strip(), i, len(lines)))
    # close sections: a section ends at the next heading of same or higher level
    for idx, sec in enumerate(sections):
        for nxt in sections[idx + 1:]:
            if nxt.level <= sec.level:
                sec.end = nxt.start
                break
    return sections


def find_section(sections: List[Section], query: str) -> Optional[Section]:
    q = query.strip().lower().lstrip("#").strip()
    if not q:
        return None
    exact = [s for s in sections if s.title.lower() == q]
    if exact:
        return exact[0]
    starts = [s for s in sections if s.title.lower().startswith(q)]
    if starts:
        return starts[0]
    contains = [s for s in sections if q in s.title.lower()]
    if contains:
        return contains[0]
    return None


class HeadingChain:
    """Gives the chain of heading titles enclosing a line index."""

    def __init__(self, sections: List[Section]):
        self.sections = sections

    def at(self, line_idx: int) -> List[str]:
        chain = []  # type: List[Tuple[int, str]]
        for s in self.sections:
            if s.start > line_idx:
                break
            while chain and chain[-1][0] >= s.level:
                chain.pop()
            chain.append((s.level, s.title))
        return [t for _, t in chain]


def clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 3] + "..."


def truncate(text: str, max_chars: int) -> str:
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n\n[truncated at %d chars; narrow the query or request a heading]" % max_chars
    return text


# ----------------------------------------------------------------------------
# MCP protocol
# ----------------------------------------------------------------------------

TOOLS = [
    {
        "name": "hive_index",
        "description": "Map of the knowledge base: topics (hive-core protocol, wax client library, HAF indexing "
                       "framework, hivemind social API), their lookup tables, and the agent helper files. Call once "
                       "to orient.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "hive_tasks",
        "description": "Developer-task router: given what you are trying to do (e.g. 'broadcast a transfer', "
                       "'display an asset', 'build a HAF app', 'debug a rejected transaction'), returns the ordered "
                       "reading path through the KB, the rules to check and how to verify. Without a query, lists the tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Words describing the task (regex allowed)."}},
            "additionalProperties": False,
        },
    },
    {
        "name": "hive_operation",
        "description": "Everything the KB knows about one Hive protocol operation: fields, required authority, "
                       "validation, evaluator behavior, hardfork notes, plus pointers into the deep findings, the wax "
                       "builder surface and related rules. Name with or without the _operation suffix.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "e.g. transfer, vote, custom_json, claim_account"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hive_rules",
        "description": "Verified best-practice rules and traps (ids HC-*, WAX-*, HAF-*, HM-*), each with evidence, "
                       "applicability and what to look for in code review. No arguments lists all rules; a query "
                       "returns the full text of matching rules; topic filters to hive-core | wax | haf | hivemind.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Regex matched against rule text (e.g. 'posting', 'NaiAsset', 'custom_json')."},
                "topic": {"type": "string", "enum": ["hive-core", "wax", "haf", "hivemind"]},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "hive_search",
        "description": "Regex search over the KB. scope: reference (default, compact lookup docs), findings "
                       "(deep file:line-cited research), rules, or all. Returns file, line and enclosing headings per hit.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Case-insensitive regex (falls back to literal on error)."},
                "scope": {"type": "string", "enum": ["reference", "findings", "rules", "all"], "default": "reference"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hive_read",
        "description": "Read a KB file (e.g. reference/rc.md) or one section of it by heading "
                       "(e.g. heading='Cost Calculation'). Paths are relative to the KB root; use hive_search or "
                       "hive_index to find them.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "heading": {"type": "string", "description": "Optional heading text (exact, prefix or substring match)."},
                "max_chars": {"type": "integer", "minimum": 500, "maximum": 200000, "default": DEFAULT_MAX_CHARS},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
]


class MCPServer:
    def __init__(self, kb: KB):
        self.kb = kb

    # -- JSON-RPC dispatch -------------------------------------------------------

    def handle_message(self, msg: Any) -> Optional[Dict[str, Any]]:
        """Returns a JSON-RPC response dict, or None for notifications."""
        if not isinstance(msg, dict):
            return jsonrpc_error(None, -32600, "Invalid Request")
        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        if method is None:
            # a response from the client (e.g. to a server ping) - nothing to do
            return None
        is_notification = "id" not in msg
        try:
            if method == "initialize":
                result = self.initialize(params)
            elif method == "notifications/initialized" or method.startswith("notifications/"):
                return None
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                result = self.call_tool(params)
            elif method == "resources/list":
                result = self.resources_list()
            elif method == "resources/read":
                result = self.resources_read(params)
            elif method == "resources/templates/list":
                result = {"resourceTemplates": []}
            elif method == "prompts/list":
                result = {"prompts": []}
            else:
                if is_notification:
                    return None
                return jsonrpc_error(msg_id, -32601, "Method not found: %s" % method)
        except ValueError as exc:
            if is_notification:
                return None
            return jsonrpc_error(msg_id, -32602, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            if is_notification:
                return None
            return jsonrpc_error(msg_id, -32603, "Internal error: %s" % exc)
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}, "resources": {"subscribe": False, "listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": SERVER_INSTRUCTIONS,
        }

    def call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        try:
            text = self.run_tool(name, args)
            return {"content": [{"type": "text", "text": text}], "isError": False}
        except ValueError as exc:
            return {"content": [{"type": "text", "text": "error: %s" % exc}], "isError": True}

    def run_tool(self, name: str, args: Dict[str, Any]) -> str:
        kb = self.kb
        if name == "hive_index":
            return kb.index()
        if name == "hive_tasks":
            return kb.tasks(query=opt_str(args, "query"))
        if name == "hive_operation":
            return kb.operation(req_str(args, "name"))
        if name == "hive_rules":
            return kb.rules(query=opt_str(args, "query"), topic=opt_str(args, "topic"))
        if name == "hive_search":
            scope = opt_str(args, "scope") or "reference"
            max_results = int(args.get("max_results") or 20)
            max_results = max(1, min(100, max_results))
            return kb.search(req_str(args, "query"), scope=scope, max_results=max_results)
        if name == "hive_read":
            max_chars = int(args.get("max_chars") or DEFAULT_MAX_CHARS)
            max_chars = max(500, min(200000, max_chars))
            return kb.read(req_str(args, "path"), heading=opt_str(args, "heading"), max_chars=max_chars)
        raise ValueError("unknown tool %r" % name)

    def resources_list(self) -> Dict[str, Any]:
        resources = []
        for rel in self.kb.files("all"):
            resources.append({
                "uri": "hive-support://" + rel,
                "name": rel,
                "mimeType": "text/markdown",
            })
        return {"resources": resources}

    def resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uri = req_str(params, "uri")
        prefix = "hive-support://"
        if not uri.startswith(prefix):
            raise ValueError("unknown resource scheme; expected %s<path>" % prefix)
        rel = uri[len(prefix):]
        lines, _ = self.kb.load(rel)
        return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": "\n".join(lines)}]}


def req_str(args: Dict[str, Any], key: str) -> str:
    val = args.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ValueError("missing required string argument %r" % key)
    return val


def opt_str(args: Dict[str, Any], key: str) -> Optional[str]:
    val = args.get(key)
    if val is None or val == "":
        return None
    if not isinstance(val, str):
        raise ValueError("argument %r must be a string" % key)
    return val


def jsonrpc_error(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


# ----------------------------------------------------------------------------
# Transports
# ----------------------------------------------------------------------------

def serve_stdio(server: MCPServer) -> None:
    """Newline-delimited JSON-RPC over stdin/stdout (the MCP stdio transport)."""
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        raw = stdin.readline()
        if not raw:
            return
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            write_message(stdout, jsonrpc_error(None, -32700, "Parse error"))
            continue
        messages = msg if isinstance(msg, list) else [msg]
        responses = [r for r in (server.handle_message(m) for m in messages) if r is not None]
        if isinstance(msg, list):
            if responses:
                write_message(stdout, responses)
        else:
            for r in responses:
                write_message(stdout, r)


def write_message(stream, obj: Any) -> None:
    stream.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
    stream.flush()


def make_http_handler(server: MCPServer):
    sessions = set()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "%s/%s" % (SERVER_NAME, SERVER_VERSION)

        def log_message(self, fmt, *args):  # quiet by default; stderr only
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _send(self, status: int, body: Optional[bytes], content_type: str = "application/json",
                  extra: Optional[Dict[str, str]] = None) -> None:
            self.send_response(status)
            if body is not None:
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
            else:
                self.send_header("Content-Length", "0")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            if self.path.rstrip("/") in ("", "/mcp", "/health"):
                if self.path.rstrip("/") == "/health":
                    self._send(200, b'{"ok":true}')
                    return
                # No server-initiated stream support: tell the client to use POST.
                self._send(405, b'{"error":"use POST for JSON-RPC; SSE streams are not offered"}',
                           extra={"Allow": "POST, DELETE"})
                return
            self._send(404, b'{"error":"not found"}')

        def do_DELETE(self):
            sid = self.headers.get("Mcp-Session-Id")
            if sid in sessions:
                sessions.discard(sid)
            self._send(200, None)

        def do_POST(self):
            if self.path.rstrip("/") not in ("", "/mcp"):
                self._send(404, b'{"error":"not found"}')
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                msg = json.loads(raw.decode("utf-8"))
            except ValueError:
                self._send(400, json.dumps(jsonrpc_error(None, -32700, "Parse error")).encode("utf-8"))
                return
            messages = msg if isinstance(msg, list) else [msg]
            extra = {}
            if any(isinstance(m, dict) and m.get("method") == "initialize" for m in messages):
                sid = uuid.uuid4().hex
                sessions.add(sid)
                extra["Mcp-Session-Id"] = sid
            responses = [r for r in (server.handle_message(m) for m in messages) if r is not None]
            if not responses:
                self._send(202, None, extra=extra)
                return
            payload = responses if isinstance(msg, list) else responses[0]
            self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), extra=extra)

    return Handler


def serve_http(server: MCPServer, host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), make_http_handler(server))
    sys.stderr.write("%s %s: Streamable HTTP on http://%s:%d/mcp (read-only KB at %s)\n" %
                     (SERVER_NAME, SERVER_VERSION, host, httpd.server_address[1], server.kb.root))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


# ----------------------------------------------------------------------------
# Self-test
# ----------------------------------------------------------------------------

def selftest(server: MCPServer) -> int:
    failures = []

    def check(label: str, cond: bool, detail: str = ""):
        status = "ok  " if cond else "FAIL"
        print("%s %s%s" % (status, label, (" - " + clip(detail, 160)) if detail and not cond else ""))
        if not cond:
            failures.append(label)

    init = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "selftest", "version": "0"}}})
    check("initialize", init is not None and init.get("result", {}).get("protocolVersion") == "2025-06-18")
    check("initialized notification is silent",
          server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None)
    tools = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in tools["result"]["tools"]]
    check("tools/list has 6 tools", len(names) == 6, ", ".join(names))

    def call(tool, **args):
        resp = server.handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                      "params": {"name": tool, "arguments": args}})
        res = resp["result"]
        return res["isError"], res["content"][0]["text"]

    err, text = call("hive_index")
    check("hive_index", not err and "reference/" in text, text)
    err, text = call("hive_operation", name="transfer")
    check("hive_operation transfer has authority line", not err and "**Authority**" in text and "transfer_operation" in text, text)
    err, text = call("hive_operation", name="vote_operation")
    check("hive_operation accepts _operation suffix", not err and "vote_operation (ID: 0)" in text, text)
    err, text = call("hive_operation", name="no_such_thing")
    check("hive_operation unknown name is a clean message", not err and text.startswith("No operation"), text)
    err, text = call("hive_search", query="downvote", scope="reference", max_results=5)
    check("hive_search finds downvote in reference", not err and "reference/" in text, text)
    err, text = call("hive_search", query="[invalid regex", scope="reference")
    check("hive_search tolerates invalid regex", not err, text)
    err, text = call("hive_read", path="reference/rc.md", heading="Cost Calculation")
    check("hive_read section", not err and text.startswith("reference/rc.md (lines"), text)
    err, text = call("hive_read", path="../../etc/passwd")
    check("hive_read refuses traversal", err, text)
    err, text = call("hive_read", path="reference/README.md", max_chars=600)
    check("hive_read honors max_chars", not err and "[truncated" in text, text)
    err, text = call("hive_rules")
    check("hive_rules lists or reports absence", not err, text)
    err, text = call("hive_tasks")
    check("hive_tasks lists or reports absence", not err, text)
    res = server.handle_message({"jsonrpc": "2.0", "id": 4, "method": "resources/list"})
    uris = [r["uri"] for r in res["result"]["resources"]]
    check("resources/list includes operations.md", "hive-support://reference/operations.md" in uris)
    res = server.handle_message({"jsonrpc": "2.0", "id": 5, "method": "resources/read",
                                 "params": {"uri": "hive-support://reference/hardforks.md"}})
    check("resources/read", "result" in res and "Hardfork" in res["result"]["contents"][0]["text"])
    res = server.handle_message({"jsonrpc": "2.0", "id": 6, "method": "nope/nope"})
    check("unknown method -> -32601", res.get("error", {}).get("code") == -32601)
    print("%d check(s), %d failure(s)" % (17, len(failures)))
    return 1 if failures else 0


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def default_root() -> str:
    here = os.path.dirname(os.path.realpath(__file__))
    return os.path.realpath(os.path.join(here, os.pardir))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="hive.support MCP server (stdlib only, read-only)")
    parser.add_argument("--root", default=os.environ.get("HIVE_SUPPORT_ROOT") or default_root(),
                        help="path of the hive.support checkout (default: parent of this script, or $HIVE_SUPPORT_ROOT)")
    parser.add_argument("--http", metavar="HOST:PORT", help="serve Streamable HTTP instead of stdio, e.g. 127.0.0.1:8765")
    parser.add_argument("--selftest", action="store_true", help="run in-process checks and exit")
    args = parser.parse_args(argv)
    server = MCPServer(KB(args.root))
    if args.selftest:
        return selftest(server)
    if args.http:
        host, _, port = args.http.rpartition(":")
        serve_http(server, host or "127.0.0.1", int(port))
        return 0
    serve_stdio(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
