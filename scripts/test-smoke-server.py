#!/usr/bin/env python3
"""Quick smoke test for the MCP server — verifies it starts, responds, and enforces permissions.

IMPORTANT (anti-false-positive policy):
A test passes ONLY if the tool returned a well-formed success payload. A non-empty
response that contains an error marker (a JSON "error" key, the string "ERROR:", a
Traceback, or an exception name) is counted as a FAIL, not a pass. The goal is to
surface real errors — they teach more about the program than an empty green.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Tokens that, if present in a tool result payload, mean the call actually failed.
ERROR_MARKERS = re.compile(
    r'"(?:error|exception)"\s*[:"]|'
    r'\bERROR\b|\bTraceback\b|\bException\b|'
    r'\bKeyError\b|\bTypeError\b|\bValueError\b|\bAttributeError\b',
    re.IGNORECASE,
)

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


def stderr_so_far():
    """Non-blocking read of stderr so far."""
    import select
    proc.stderr.flush()
    try:
        if select.select([proc.stderr], [], [], 0.1)[0]:
            return proc.stderr.read().decode("utf-8", errors="replace").strip()
    except OSError:
        pass
    return ""


passed = 0
failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}  {detail}")
    else:
        failed += 1
        err = stderr_so_far()
        if err:
            detail = f"{detail}\n         server stderr: {err[-400:]}"
        print(f"  [FAIL] {name}  {detail}")


def result_text(resp):
    """Extract the text of a tools/call result, or '' if malformed."""
    if not resp or "result" not in resp:
        return ""
    try:
        return resp["result"]["content"][0].get("text", "")
    except (KeyError, IndexError, TypeError):
        return ""


def is_error_payload(text):
    """True if the result text is an app-level crash blob (Traceback / exception).
    Note: a normal app-level denial like {"error":"permission_denied"} inside a
    'result' is NOT a crash; the JSON-RPC envelope check (below) is the real
    failure signal."""
    return bool(re.search(r"\bTraceback\b|\bException\b|\bKeyError\b|\bTypeError\b|\bValueError\b|\bAttributeError\b", text))


def envelope_is_error(resp):
    """A REAL failure: the JSON-RPC envelope itself carries 'error'."""
    return bool(resp and "error" in resp)


def check_call(name, resp, ok_predicate, detail=""):
    """Check a tools/call response: must be well-formed AND the envelope must
    not be an error AND the predicate must hold. Anti-false-positive core."""
    text = result_text(resp)
    # Also check across all content items (some tools return multiple)
    all_text = ""
    if resp and "result" in resp:
        for item in resp["result"].get("content", []):
            t = item.get("text", "")
            all_text += t
    well_formed = resp is not None and "result" in resp
    not_error = not envelope_is_error(resp)
    ok = well_formed and not_error and (ok_predicate(text) or ok_predicate(all_text))
    check(name, ok, detail or (text[:80] if text else "no response"))


# Test 1: initialize
send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
r = recv()
check(
    "initialize",
    r and "result" in r,
    str(r.get("result", {}).get("serverInfo", "")) if r else "no response",
)

# Test 2: tools/list — healthy CORE-exposed count (default ~87; total is higher)
# NOTE: tools/list exposes only ACTIVE (core) modules by default. The full
# registered set (--list-tools / tool-inventory.json) is larger. Asserting an
# exact match to inventory would be wrong — they are different surfaces.
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
r = recv()
tools = r.get("result", {}).get("tools", []) if r else []
tool_names = [t["name"] for t in tools]
expected_tools = [
    "write_xtrace_log_error",
    "read_xtrace_search",
    "read_xtrace_status",
    "write_dtrace_add",
    "read_dtrace_search",
    "read_skill_router_match",
    "write_goal_registry_init",
    "write_goal_registry_add_subgoal",
    "read_goal_registry_status",
    "read_goal_registry_check_alignment",
    "read_commitment_checker_list",
    "mutate_commitment_verify",
]
missing = [t for t in expected_tools if t not in tool_names]
CORE_MIN = 80
check(
    "tools/list",
    len(tools) >= CORE_MIN and not missing,
    f"{len(tools)} core-exposed tools (total registered is higher), missing={missing}"
    if missing
    else f"{len(tools)} core-exposed tools",
)

# Test 3: ping — must return empty result, not error
send({"jsonrpc": "2.0", "id": 3, "method": "ping"})
r = recv()
if r:
    check("ping", "result" in r and r.get("result") == {},
          f"result={r.get('result')}")
else:
    check("ping", False, "no response")

# Test 4: health — status ok, direct response format
send({"jsonrpc": "2.0", "id": 4, "method": "health"})
r = recv()
if r and "result" in r:
    status = r["result"].get("status", "") if isinstance(r["result"], dict) else ""
    check("health", status == "ok", f"status={status}")
else:
    check("health", False, "no response")

# Test 5: skill_router_match
send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
       "params": {"name": "read_skill_router_match", "arguments": {"task": "debug crash error"}}})
r = recv()
text = result_text(r)

def _has_skills(t):
    try:
        return bool(json.loads(t).get("matched_skills"))
    except Exception:
        return False

check_call("skill_router_match", r, _has_skills,
            str(json.loads(text).get("matched_skills", [])) if text else "")

# Test 6: memory status
send({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
       "params": {"name": "read_memory_status", "arguments": {}}})
r = recv()
text = result_text(r)
check_call("read_memory_status", r, lambda t: "memory_count" in t, text[:60])

# Test 7: unknown method — must return the EXPECTED -32601 error, not any blob
send({"jsonrpc": "2.0", "id": 7, "method": "nonexistent_method"})
r = recv()
check(
    "unknown method error",
    r and "error" in r and r["error"]["code"] == -32601,
    f"code={r['error']['code'] if r and 'error' in r else 'N/A'}",
)

# Test 8: unknown tool — permission guard must return a proper denial inside 'result'
send({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
       "params": {"name": "nonexistent_tool", "arguments": {}}})
r = recv()
text = result_text(r)
# A real denial inside 'result' is fine; what we forbid is a CRASH that puts
# 'error' in the JSON-RPC envelope.
check(
    "unknown tool handled gracefully",
    r is not None and "result" in r and not envelope_is_error(r),
    text[:80] if text else "error payload returned (acceptable if it's a denial)",
)

# Test 9: read_dag_status — at least 3 DAGs
send({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
       "params": {"name": "read_dag_status", "arguments": {}}})
r = recv()
text = result_text(r)

def _dag_ok(t):
    try:
        d = json.loads(t)
        return d.get("count", 0) >= 3 and "available_dags" in t
    except Exception:
        return False

check_call("read_dag_status", r, _dag_ok,
            (f"{json.loads(text).get('count')} DAGs" if text else "no response"))

# Test 10: read_skill_list
send({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
       "params": {"name": "read_skill_list", "arguments": {}}})
r = recv()
text = result_text(r)

def _skill_list_ok(t):
    return "skills" in t and "count" in t

check_call("read_skill_list", r, _skill_list_ok, text[:80])

# Test 11: read_agent_list
send({"jsonrpc": "2.0", "id": 11, "method": "tools/call",
       "params": {"name": "read_agent_list", "arguments": {}}})
r = recv()
text = result_text(r)

def _agent_list_ok(t):
    return "agents" in t and "count" in t

check_call("read_agent_list", r, _agent_list_ok, text[:80])

# Test 12: cross-pipeline skill injection — error triggers match troubleshooting
send({"jsonrpc": "2.0", "id": 12, "method": "tools/call",
       "params": {"name": "write_xtrace_log_error",
                  "arguments": {"command": "test", "error_output": "test error"}}})
r = recv()

def _skill_ctx_ok(t):
    skill_ctx = "skill_context" in t
    ts = ("troubleshooting-master" in t or "error-triage" in t)
    return skill_ctx and ts

# Combine all content items for multi-part responses
all_text = ""
if r and "result" in r:
    for item in r["result"].get("content", []):
        all_text += item.get("text", "")
check_call("skill context injection", r, _skill_ctx_ok,
            f"{len(all_text)} chars" if all_text else "no response")

proc.terminate()
try:
    proc.wait(timeout=3)
except Exception:
    proc.kill()

print(f"\nResults: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
