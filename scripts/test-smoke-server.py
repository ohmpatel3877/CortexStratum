#!/usr/bin/env python3
"""Quick smoke test for the MCP server — verifies it starts, responds, and enforces permissions."""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

proc = subprocess.Popen(
    [sys.executable, str(ROOT / "scripts" / "tools-mcp-server.py")],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=str(ROOT),
)
time.sleep(0.3)


def send(msg):
    payload = json.dumps(msg).encode("utf-8")
    proc.stdin.write(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
    proc.stdin.flush()


def recv():
    cl, deadline = 0, time.monotonic() + 5
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            return None
        if line == b"\r\n":
            break
        d = line.decode("utf-8", errors="replace").strip()
        if ":" in d:
            k, v = d.split(":", 1)
            if k.strip().lower() == "content-length":
                cl = int(v.strip())
    if not cl:
        return None
    return json.loads(proc.stdout.read(cl).decode("utf-8"))


passed = 0
failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}  {detail}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


# Test 1: initialize
send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
r = recv()
check(
    "initialize",
    r and "result" in r,
    str(r.get("result", {}).get("serverInfo", "")) if r else "no response",
)

# Test 2: tools/list — verify count is in expected range
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
r = recv()
tools = r.get("result", {}).get("tools", []) if r else []
# Verify at least 100 tools registered (exact count varies, but should be high)
check("tools/list", len(tools) >= 100, f"{len(tools)} tools")

# Test 3: ping — should return empty result, not error
send({"jsonrpc": "2.0", "id": 3, "method": "ping"})
r = recv()
if r:
    check("ping", "result" in r and r.get("result") == {}, f"result={r.get('result')}")
else:
    check("ping", False, "no response")

# Test 4: health — should return status ok, not error
send({"jsonrpc": "2.0", "id": 4, "method": "health"})
r = recv()
if r and "result" in r:
    status = r["result"].get("status", "")
    check("health", status == "ok", f"status={status}")
else:
    check("health", False, "no response")

# Test 5: skill_router_match
send(
    {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "read_skill_router_match",
            "arguments": {"task": "debug crash error"},
        },
    }
)
r = recv()
if r and "result" in r:
    content = json.loads(r["result"]["content"][0]["text"])
    check(
        "skill_router_match",
        bool(content.get("matched_skills")),
        str(content.get("matched_skills", [])),
    )
else:
    check("skill_router_match", False, "no response")

# Test 6: memory status
send(
    {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "read_memory_status", "arguments": {}},
    }
)
r = recv()
if r and "result" in r:
    content_text = r["result"]["content"][0]["text"]
    check("read_memory_status", "memory_count" in content_text, content_text[:60])
else:
    check("read_memory_status", False, "no response")

# Test 7: unknown method
send({"jsonrpc": "2.0", "id": 7, "method": "nonexistent_method"})
r = recv()
check(
    "unknown method error",
    r and "error" in r and r["error"]["code"] == -32601,
    f"code={r['error']['code'] if r else 'N/A'}",
)

# Test 8: unknown tool — permission guard should block with error
send(
    {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "nonexistent_tool", "arguments": {}},
    }
)
r = recv()
if r and "result" in r:
    content_text = r["result"]["content"][0].get("text", "")
    # Permission guard rejects unknown tools (not in TOOLS list)
    check(
        "unknown tool error",
        "permission_denied" in content_text or "error" in content_text,
        content_text[:80],
    )
else:
    check("unknown tool error", False, "no response")

# Test 9: read_dag_status — list available DAGs (should return at least 3 defs)
send(
    {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {"name": "read_dag_status", "arguments": {}},
    }
)
r = recv()
if r and "result" in r:
    content_text = r["result"]["content"][0].get("text", "")
    try:
        dag_data = json.loads(content_text)
        dag_count = dag_data.get("count", 0)
        check(
            "read_dag_status",
            dag_count >= 3 and "available_dags" in content_text,
            f"{dag_count} DAGs",
        )
    except json.JSONDecodeError:
        check("read_dag_status", False, f"invalid JSON: {content_text[:80]}")
else:
    check("read_dag_status", False, "no response")

# Test 10: read_skill_list — list active skills
send(
    {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": "read_skill_list", "arguments": {}},
    }
)
r = recv()
if r and "result" in r:
    content_text = r["result"]["content"][0].get("text", "")
    check(
        "read_skill_list",
        "skills" in content_text and "count" in content_text,
        content_text[:80],
    )
else:
    check("read_skill_list", False, "no response")

# Test 11: read_agent_list — list agent personas
send(
    {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "read_agent_list", "arguments": {}},
    }
)
r = recv()
if r and "result" in r:
    content_text = r["result"]["content"][0].get("text", "")
    check(
        "read_agent_list",
        "agents" in content_text and "count" in content_text,
        content_text[:80],
    )
else:
    check("read_agent_list", False, "no response")

# Test 12: cross-pipeline skill injection — error triggers should match troubleshooting
send(
    {
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "write_xtrace_log_error",
            "arguments": {"command": "test", "error_output": "test error"},
        },
    }
)
r = recv()
if r and "result" in r:
    contents = r["result"].get("content", [])
    all_text = " ".join(c.get("text", "") for c in contents)
    has_skill_ctx = "skill_context" in all_text
    has_troubleshooting = (
        "troubleshooting-master" in all_text or "error-triage" in all_text
    )
    check(
        "skill context injection",
        has_skill_ctx and has_troubleshooting,
        f"{len(contents)} items, skill_ctx={has_skill_ctx}",
    )
else:
    check("skill context injection", False, "no response")

proc.terminate()
proc.wait(timeout=3)

print(f"\nResults: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
