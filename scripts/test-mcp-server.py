#!/usr/bin/env python3
"""
Test harness for tools-mcp-server.py
Validates the MCP stdio protocol and all 6 tool categories.

ANTI-FALSE-POSITIVE POLICY:
A tools/call test passes ONLY if the server returns a well-formed success payload
whose JSON-RPC envelope carries no 'error' key. An application-level denial
(e.g. {"error":"permission_denied", ...} returned inside a normal 'result') is
NOT a crash and is acceptable. A real crash is an envelope-level error, a
Traceback, or an exception string in the result text. We want REAL errors surfaced.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

RESULTS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "mcp-server-test-results.json"
)

# Real crash markers inside result text (app-level denial text is excluded).
CRASH_MARKERS = re.compile(
    r"\bTraceback\b|\bException\b|\bKeyError\b|\bTypeError\b|"
    r"\bValueError\b|\bAttributeError\b"
)


def send_mcp_message(proc_stdin, msg: dict):
    """Send a JSON-RPC message to the server's stdin."""
    payload = json.dumps(msg, ensure_ascii=False)
    raw = payload.encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode()
    proc_stdin.write(header + raw)
    proc_stdin.flush()


def read_mcp_response(proc_stdout, timeout=5) -> dict | None:
    """Read one JSON-RPC response from the server's stdout."""
    content_length = 0
    start = time.time()

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


def result_text(resp):
    """Extract the text of a tools/call result, or '' if malformed."""
    if not resp or "result" not in resp:
        return ""
    try:
        return resp["result"]["content"][0].get("text", "")
    except (KeyError, IndexError, TypeError):
        return ""


def envelope_is_error(resp):
    """A REAL failure: the JSON-RPC envelope itself carries an 'error' key."""
    return bool(resp and "error" in resp)


def text_is_crash(text):
    """Result text contains a real crash traceback/exception (not an app denial)."""
    return bool(CRASH_MARKERS.search(text))


def main():
    results = {
        "test_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "server_script": "tools-mcp-server.py",
        "tests": [],
        "overall": {"passed": 0, "failed": 0, "total": 0},
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

    def record_call(name, resp, ok_predicate, detail=""):
        """Anti-false-positive core: well-formed result, envelope not an error,
        no crash text, and the predicate holds."""
        text = result_text(resp)
        well_formed = resp is not None and "result" in resp
        not_error = not envelope_is_error(resp)
        not_crash = not text_is_crash(text)
        ok = well_formed and not_error and not_crash and ok_predicate(text)
        record(name, ok, detail or (text[:100] if text else "no response"))

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
        send_mcp_message(
            proc.stdin,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        resp = read_mcp_response(proc.stdout)
        record(
            "initialize",
            resp is not None and resp.get("jsonrpc") == "2.0" and "result" in resp,
            f"serverInfo={resp.get('result', {}).get('serverInfo', {})}" if resp else "no response",
        )

        # ---- Test 2: tools/list — healthy CORE-exposed count ----
        # NOTE: tools/list returns only ACTIVE (core) modules by default (~87).
        # The total registered set is larger (see --list-tools / tool-inventory.json).
        # We assert the exposed core surface is healthy, not an exact match to the
        # full inventory (that would be wrong — they are different surfaces).
        print("\n--- Test 2: tools/list ---")
        send_mcp_message(
            proc.stdin,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        resp = read_mcp_response(proc.stdout)
        tools = resp.get("result", {}).get("tools", []) if resp else []
        tool_names = [t["name"] for t in tools]
        tool_count = len(tool_names)
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
        record(
            "tools/list",
            resp is not None and "result" in resp and tool_count >= CORE_MIN and not missing,
            f"{tool_count} core-exposed tools (total registered is higher), missing={missing}"
            if missing
            else f"{tool_count} core-exposed tools",
        )

        # ---- Test 3: tools/call - skill_router_match ----
        print("\n--- Test 3: tools/call (read_skill_router_match) ---")
        send_mcp_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "read_skill_router_match",
                    "arguments": {"task": "debug error fix"},
                },
            },
        )
        resp = read_mcp_response(proc.stdout)
        text = result_text(resp)

        def _has_skills(t):
            try:
                return bool(json.loads(t).get("matched_skills"))
            except Exception:
                return False

        record_call(
            "tools/call (skill_router_match)",
            resp,
            _has_skills,
            str(json.loads(text).get("matched_skills", [])) if text else "",
        )

        # ---- Test 4: tools/call - read_xtrace_status ----
        print("\n--- Test 4: tools/call (read_xtrace_status) ---")
        send_mcp_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "read_xtrace_status", "arguments": {}},
            },
        )
        resp = read_mcp_response(proc.stdout)
        text = result_text(resp)
        record_call(
            "tools/call (xtrace_status)",
            resp,
            lambda t: len(t) > 0,
            f"got {len(text)} chars of output",
        )

        # ---- Test 5: tools/call - read_goal_registry_status ----
        print("\n--- Test 5: tools/call (read_goal_registry_status) ---")
        send_mcp_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "read_goal_registry_status", "arguments": {}},
            },
        )
        resp = read_mcp_response(proc.stdout)
        text = result_text(resp)
        record_call(
            "tools/call (goal_registry_status)",
            resp,
            lambda t: len(t) > 0,
            f"got {len(text)} chars of output",
        )

        # ---- Test 6: tools/call - read_commitment_checker_list ----
        print("\n--- Test 6: tools/call (read_commitment_checker_list) ---")
        send_mcp_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "read_commitment_checker_list", "arguments": {}},
            },
        )
        resp = read_mcp_response(proc.stdout)
        text = result_text(resp)
        record_call(
            "tools/call (commitment_checker_list)",
            resp,
            lambda t: len(t) > 0,
            f"got {len(text)} chars of output",
        )

        # ---- Test 7: tools/call - read_memory_status ----
        print("\n--- Test 7: tools/call (read_memory_status) ---")
        send_mcp_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "read_memory_status", "arguments": {}},
            },
        )
        resp = read_mcp_response(proc.stdout)
        text = result_text(resp)

        def _mem_ok(t):
            return ("memory_count" in t) or ("entries" in t) or ("status" in t)

        record_call(
            "tools/call (read_memory_status)",
            resp,
            _mem_ok,
            f"got: {text[:100]}",
        )

        # ---- Test 8: tools/call - read_dtrace_search ----
        print("\n--- Test 8: tools/call (read_dtrace_search) ---")
        send_mcp_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {"name": "read_dtrace_search", "arguments": {"keyword": "test"}},
            },
        )
        resp = read_mcp_response(proc.stdout)
        text = result_text(resp)
        record_call(
            "tools/call (dtrace_search)",
            resp,
            lambda t: len(t) > 0,
            f"got {len(text)} chars",
        )

        # ---- Test 9: Unknown tool returns error gracefully ----
        print("\n--- Test 9: unknown tool ---")
        send_mcp_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            },
        )
        resp = read_mcp_response(proc.stdout)
        text = result_text(resp)
        # Acceptable: a proper denial inside 'result'. Forbidden: a crash that
        # puts 'error' in the JSON-RPC envelope.
        record(
            "unknown tool handled gracefully",
            resp is not None and "result" in resp and not envelope_is_error(resp),
            "returned a response (not crash)" if not text else text[:80],
        )

        # ---- Test 10: Unknown method returns error ----
        print("\n--- Test 10: unknown method ---")
        send_mcp_message(
            proc.stdin,
            {"jsonrpc": "2.0", "id": 10, "method": "bogus_method", "params": {}},
        )
        resp = read_mcp_response(proc.stdout)
        has_error = resp is not None and "error" in resp
        record(
            "unknown method returns error",
            has_error,
            f"error code: {resp.get('error', {}).get('code')}" if has_error else "no error",
        )

    finally:
        print("\n--- Shutting down server ---")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        # Surface any stderr the server emitted during the run (real errors hide here).
        err = proc.stderr.read().decode("utf-8", errors="replace").strip()
        if err:
            print(f"  [server stderr]\n{err[-800:]}")

    # Summary
    total = results["overall"]["total"]
    passed = results["overall"]["passed"]
    failed = results["overall"]["failed"]
    print(f"\n{'=' * 50}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 50}")

    results["overall"]["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0
    results["overall"]["all_passed"] = failed == 0

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to: {RESULTS_PATH}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
