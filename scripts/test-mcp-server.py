#!/usr/bin/env python3
"""
Test harness for tools-mcp-server.py
Validates the MCP stdio protocol and all 6 tool categories.
Sends initialize, tools/list, and tools/call requests, then saves results.
"""

import json, subprocess, sys, time
from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent.parent / "data" / "mcp-server-test-results.json"

def send_mcp_message(proc_stdin, msg: dict):
    """Send a JSON-RPC message to the server's stdin."""
    payload = json.dumps(msg, ensure_ascii=False)
    raw = payload.encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("utf-8")
    proc_stdin.write(header + raw)
    proc_stdin.flush()

def read_mcp_response(proc_stdout, timeout=5) -> dict | None:
    """Read one JSON-RPC response from the server's stdout."""
    import select
    content_length = 0
    start = time.time()
    buf = b""

    while True:
        if time.time() - start > timeout:
            return None
        line = proc_stdout.readline()
        if not line:
            return None
        if line == b"\r\n":
            break
        decoded = line.decode("utf-8", errors="replace").strip()
        if ":" in decoded:
            key, val = decoded.split(":", 1)
            if key.strip().lower() == "content-length":
                content_length = int(val.strip())

    if content_length == 0:
        return None

    body = proc_stdout.read(content_length)
    return json.loads(body.decode("utf-8"))


def main():
    results = {
        "test_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "server_script": "tools-mcp-server.py",
        "tests": [],
        "overall": {"passed": 0, "failed": 0, "total": 0}
    }

    def record(name, passed, detail=""):
        results["tests"].append({"name": name, "passed": passed, "detail": detail})
        results["overall"]["total"] += 1
        if passed:
            results["overall"]["passed"] += 1
        else:
            results["overall"]["failed"] += 1
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if detail:
            print(f"         {detail}")

    print("Starting MCP server subprocess...")
    proc = subprocess.Popen(
        ["python", str(Path(__file__).resolve().parent / "tools-mcp-server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).resolve().parent.parent,
    )

    time.sleep(0.5)  # let server initialize

    try:
        # ---- Test 1: Initialize ----
        print("\n--- Test 1: initialize ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}
        })
        resp = read_mcp_response(proc.stdout)
        record("initialize",
               resp is not None and resp.get("jsonrpc") == "2.0" and "result" in resp,
               f"serverInfo={resp.get('result',{}).get('serverInfo',{})}" if resp else "no response")

        # ---- Test 2: tools/list ----
        print("\n--- Test 2: tools/list ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
        })
        resp = read_mcp_response(proc.stdout)
        tools = resp.get("result", {}).get("tools", []) if resp else []
        tool_names = [t["name"] for t in tools]
        tool_count = len(tool_names)
        expected_tools = [
            "xtrace_log_error", "xtrace_search", "xtrace_status",
            "dtrace_add", "dtrace_search",
            "skill_router_match", "output_condenser",
            "goal_registry_init", "goal_registry_add_subgoal",
            "goal_registry_status", "goal_registry_check_alignment",
            "commitment_checker_list", "commitment_checker_verify",
        ]
        missing = [t for t in expected_tools if t not in tool_names]
        record("tools/list",
               resp is not None and "result" in resp and tool_count >= 11,
               f"{tool_count} tools registered, missing: {missing}" if missing else f"{tool_count} tools: {', '.join(tool_names)}")

        # ---- Test 3: tools/call - skill_router_match ----
        print("\n--- Test 3: tools/call (skill_router_match) ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "skill_router_match", "arguments": {"task": "debug error fix"}}
        })
        resp = read_mcp_response(proc.stdout)
        result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        has_skills = "matched_skills" in result_text or "troubleshooting" in result_text.lower()
        record("tools/call (skill_router_match)",
               resp is not None and "result" in resp and has_skills,
               f"result has matched_skills: {has_skills}")

        # ---- Test 4: tools/call - xtrace_status ----
        print("\n--- Test 4: tools/call (xtrace_status) ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "xtrace_status", "arguments": {}}
        })
        resp = read_mcp_response(proc.stdout)
        result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        record("tools/call (xtrace_status)",
               resp is not None and "result" in resp and len(result_text) > 0,
               f"got {len(result_text)} chars of output")

        # ---- Test 5: tools/call - goal_registry_status ----
        print("\n--- Test 5: tools/call (goal_registry_status) ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "goal_registry_status", "arguments": {}}
        })
        resp = read_mcp_response(proc.stdout)
        result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        record("tools/call (goal_registry_status)",
               resp is not None and "result" in resp and len(result_text) > 0,
               f"got {len(result_text)} chars of output")

        # ---- Test 6: tools/call - commitment_checker_list ----
        print("\n--- Test 6: tools/call (commitment_checker_list) ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"name": "commitment_checker_list", "arguments": {}}
        })
        resp = read_mcp_response(proc.stdout)
        result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        record("tools/call (commitment_checker_list)",
               resp is not None and "result" in resp and len(result_text) > 0,
               f"got {len(result_text)} chars of output")

        # ---- Test 7: tools/call - output_condenser ----
        print("\n--- Test 7: tools/call (output_condenser) ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {
                "name": "output_condenser",
                "arguments": {"output_type": "bash", "content": "line1\nBuild completed successfully\nline3\nerror: something failed\nline5"}
            }
        })
        resp = read_mcp_response(proc.stdout)
        result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        has_key = "Build" in result_text or "error" in result_text or "completed" in result_text
        record("tools/call (output_condenser)",
               resp is not None and "result" in resp and has_key,
               f"got: {result_text[:80]}")

        # ---- Test 8: tools/call - dtrace_search ----
        print("\n--- Test 8: tools/call (dtrace_search) ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 8, "method": "tools/call",
            "params": {"name": "dtrace_search", "arguments": {"keyword": "test"}}
        })
        resp = read_mcp_response(proc.stdout)
        result_text = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        record("tools/call (dtrace_search)",
               resp is not None and "result" in resp and len(result_text) > 0,
               f"got {len(result_text)} chars")

        # ---- Test 9: Unknown tool returns error gracefully ----
        print("\n--- Test 9: unknown tool ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}}
        })
        resp = read_mcp_response(proc.stdout)
        record("unknown tool handled gracefully",
               resp is not None and ("result" in resp or "error" in resp),
               "returned a response (not crash)")

        # ---- Test 10: Unknown method returns error ----
        print("\n--- Test 10: unknown method ---")
        send_mcp_message(proc.stdin, {
            "jsonrpc": "2.0", "id": 10, "method": "bogus_method", "params": {}
        })
        resp = read_mcp_response(proc.stdout)
        has_error = resp is not None and "error" in resp
        record("unknown method returns error",
               has_error,
               f"error code: {resp.get('error',{}).get('code')}" if has_error else "no error")

    finally:
        print("\n--- Shutting down server ---")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except:
            proc.kill()

    # Summary
    total = results["overall"]["total"]
    passed = results["overall"]["passed"]
    failed = results["overall"]["failed"]
    print(f"\n{'='*50}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*50}")

    results["overall"]["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0
    results["overall"]["all_passed"] = failed == 0

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to: {RESULTS_PATH}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
