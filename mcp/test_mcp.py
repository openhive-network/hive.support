#!/usr/bin/env python3
"""End-to-end test of the hive.support MCP server over both transports (stdlib only).

Run: python3 mcp/test_mcp.py
Exit code 0 = all checks passed.
"""

import json
import os
import subprocess
import sys
import threading
import urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
SERVER = os.path.join(HERE, "hive_support_mcp.py")
ROOT = os.path.realpath(os.path.join(HERE, os.pardir))

failures = []


def check(label, cond, detail=""):
    print("%s %s%s" % ("ok  " if cond else "FAIL", label, (" - " + str(detail)[:200]) if (detail and not cond) else ""))
    if not cond:
        failures.append(label)


def rpc(id_, method, params=None):
    msg = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


# --- stdio transport -----------------------------------------------------------

def test_stdio():
    proc = subprocess.Popen([sys.executable, SERVER, "--root", ROOT], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def send(obj):
        proc.stdin.write((json.dumps(obj) + "\n").encode())
        proc.stdin.flush()

    def recv():
        line = proc.stdout.readline()
        return json.loads(line.decode()) if line else None

    try:
        send(rpc(1, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                   "clientInfo": {"name": "test", "version": "0"}}))
        r = recv()
        check("stdio initialize", r and r["result"]["protocolVersion"] == "2025-03-26", r)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(rpc(2, "tools/list"))
        r = recv()
        check("stdio tools/list", r and r["id"] == 2 and len(r["result"]["tools"]) == 6, r)
        send(rpc(3, "tools/call", {"name": "hive_operation", "arguments": {"name": "custom_json"}}))
        r = recv()
        text = r["result"]["content"][0]["text"]
        check("stdio hive_operation custom_json", "custom_json_operation" in text and "**Authority**" in text, text[:200])
        send(rpc(4, "tools/call", {"name": "hive_search", "arguments": {"query": "NaiAsset", "scope": "reference"}}))
        r = recv()
        text = r["result"]["content"][0]["text"]
        check("stdio hive_search NaiAsset hits wax reference", "reference/wax/" in text, text[:200])
        send(rpc(5, "tools/call", {"name": "hive_read", "arguments": {"path": "reference/hardforks.md", "heading": "Key Hardfork Details"}}))
        r = recv()
        text = r["result"]["content"][0]["text"]
        check("stdio hive_read section", text.startswith("reference/hardforks.md (lines") and "HF28" in text, text[:200])
        send(rpc(6, "ping"))
        r = recv()
        check("stdio ping", r and r["result"] == {}, r)
        send([rpc(7, "ping"), rpc(8, "ping")])
        r = recv()
        check("stdio batch", isinstance(r, list) and len(r) == 2, r)
        send(rpc(9, "tools/call", {"name": "hive_read", "arguments": {"path": "/etc/passwd"}}))
        r = recv()
        check("stdio hive_read refuses absolute path", r["result"]["isError"] is True, r)
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)
        err = proc.stderr.read().decode()
        check("stdio server exited cleanly", proc.returncode == 0, "rc=%s stderr=%s" % (proc.returncode, err[:200]))


# --- HTTP transport ------------------------------------------------------------

def test_http():
    sys.path.insert(0, HERE)
    import hive_support_mcp as mod  # noqa: E402

    server = mod.MCPServer(mod.KB(ROOT))
    httpd = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.make_http_handler(server))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = "http://127.0.0.1:%d/mcp" % port

    def post(obj, headers=None):
        data = json.dumps(obj).encode()
        req = urllib.request.Request(base, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
                return resp.status, dict(resp.headers), (json.loads(body) if body else None)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), None

    try:
        status, headers, body = post(rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                           "clientInfo": {"name": "test", "version": "0"}}))
        sid = headers.get("Mcp-Session-Id")
        check("http initialize 200 + session id", status == 200 and sid and body["result"]["serverInfo"]["name"] == "hive-support", (status, body))
        status, headers, body = post({"jsonrpc": "2.0", "method": "notifications/initialized"}, {"Mcp-Session-Id": sid})
        check("http notification -> 202", status == 202, status)
        status, headers, body = post(rpc(2, "tools/call", {"name": "hive_rules", "arguments": {}}), {"Mcp-Session-Id": sid})
        check("http tools/call hive_rules", status == 200 and body["result"]["isError"] is False, body)
        status, headers, body = post(rpc(3, "resources/read", {"params": 1}), {"Mcp-Session-Id": sid})
        check("http bad params -> jsonrpc error", status == 200 and "error" in body, body)
        req = urllib.request.Request(base, method="GET")
        try:
            urllib.request.urlopen(req, timeout=10)
            check("http GET -> 405", False, "no error raised")
        except urllib.error.HTTPError as e:
            check("http GET -> 405", e.code == 405, e.code)
        with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=10) as resp:
            check("http /health", resp.status == 200)
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    test_stdio()
    test_http()
    print("%d failure(s)" % len(failures))
    sys.exit(1 if failures else 0)
