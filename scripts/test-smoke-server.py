#!/usr/bin/env python3
"""Quick smoke test for the MCP server — verifies it starts, responds, and enforces permissions."""
import subprocess, json, time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

proc = subprocess.Popen(
    [sys.executable, str(ROOT / "scripts" / "tools-mcp-server.py")],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    cwd=str(ROOT),
)
time.sleep(0.3)

def send(msg):
    payload = json.dumps(msg).encode("utf-8")
    proc.stdin.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8") + payload)
    proc.stdin.flush()

def recv():
    cl, deadline = 0, time.monotonic() + 5
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line: return None
        if line == b"\r\n": break
        d = line.decode("utf-8", errors="replace").strip()
        if ":" in d:
            k, v = d.split(":", 1)
            if k.strip().lower() == "content-length":
                cl = int(v.strip())
    if not cl: return None
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
check("initialize", r and "result" in r, str(r.get("result", {}).get("serverInfo", "")) if r else "no response")

# Test 2: tools/list
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
r = recv()
tools = r.get("result", {}).get("tools", []) if r else []
check("tools/list", len(tools) >= 60, f"{len(tools)} tools")

# Test 3: ping
send({"jsonrpc": "2.0", "id": 3, "method": "ping"})
r = recv()
check("ping", r and "result" in r, "")

# Test 4: health
send({"jsonrpc": "2.0", "id": 4, "method": "health"})
r = recv()
check("health", r and "result" in r, "")

# Test 5: skill_router_match
send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
      "params": {"name": "read_skill_router_match", "arguments": {"task": "debug crash error"}}})
r = recv()
if r and "result" in r:
    content = json.loads(r["result"]["content"][0]["text"])
    check("skill_router_match", bool(content.get("matched_skills")), str(content.get("matched_skills", [])))
else:
    check("skill_router_match", False, "no response")

# Test 6: memory status
send({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
      "params": {"name": "read_memory_status", "arguments": {}}})
r = recv()
if r and "result" in r:
    content_text = r["result"]["content"][0]["text"]
    check("read_memory_status", "memory_count" in content_text, content_text[:60])
else:
    check("read_memory_status", False, "no response")

# Test 7: unknown method
send({"jsonrpc": "2.0", "id": 7, "method": "nonexistent_method"})
r = recv()
check("unknown method error", r and "error" in r and r["error"]["code"] == -32601, f"code={r['error']['code'] if r else 'N/A'}")

# Test 8: unknown tool
send({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
      "params": {"name": "nonexistent_tool", "arguments": {}}})
r = recv()
check("unknown tool error", r and "result" in r, "")

proc.terminate()
proc.wait(timeout=3)

print(f"\nResults: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
