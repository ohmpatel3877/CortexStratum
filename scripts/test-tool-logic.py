#!/usr/bin/env python3
"""
test-tool-logic.py — Logic tests for CortexStratum's REAL behaviors.

The MCP protocol test (test-mcp-server.py) only checks handshake. These tests
exercise actual tool logic the handshake misses:
  - JSON Schema validation rejects bad args (pre_verify)
  - renudge halt blocks execution of the targeted tool
  - verifier drift detection returns real per-key diffs
  - a dispatched tool returns correct output (no phantom/mock)

Run:  python scripts/test-tool-logic.py
Exit non-zero on any failure. Output: JSON summary to data/tool-logic-results.json
"""

import importlib.util as _util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
RESULTS_PATH = ROOT / "data" / "tool-logic-results.json"


def _load_server():
    spec = _util.spec_from_file_location("tools_mcp_server", SCRIPTS / "tools-mcp-server.py")
    mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _call(name, args):
    """Call a tool through the real handle_tool_call choke point."""
    return _load_server().handle_tool_call(name, args)


def _main():
    results = {"tests": [], "overall": {"passed": 0, "failed": 0, "total": 0}}

    def record(name, passed, detail=""):
        results["tests"].append({"name": name, "passed": passed, "detail": detail})
        results["overall"]["total"] += 1
        results["overall"]["passed" if passed else "failed"] += 1
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail and not passed else ""))

    server = _load_server()
    verifier = server._get_verifier()

    # 1) JSON Schema validation — missing required field is rejected.
    #    memory_add requires 'text'. Call without it; pre_verify must flag it.
    _, pre = verifier, None
    m = server._get_verifier()
    r_missing = m.pre_verify("memory_add", {})  # no 'text'
    schema_v = [v for v in r_missing["violations"] if v["type"] == "schema_violation"]
    record("schema: missing required 'text' on memory_add is flagged",
           bool(schema_v), detail=str(schema_v[:1]))

    # 2) valid call produces no schema violation
    r_valid = m.pre_verify("memory_add", {"text": "hello"})
    schema_v_ok = [v for v in r_valid["violations"] if v["type"] == "schema_violation"]
    record("schema: valid memory_add call is clean", not schema_v_ok,
           detail=str(schema_v_ok[:1]))

    # 3) renudge halt blocks the targeted tool.
    #    Arm a halt renudge on memory_status, then call it — must be blocked.
    sig = server.handle_tool_call("verifier_renudge", {
        "target": "memory_status", "correction": {}, "strategy": "halt",
    })
    blocked = server.handle_tool_call("memory_status", {})
    blocked_txt = json.dumps(blocked)
    record("renudge: halt blocks targeted tool (memory_status)",
           "renudge_halt" in blocked_txt, detail=blocked_txt[:80])

    # 4) renudge halt persists across calls (safety: only override/incremental auto-clear).
    #    Arming halt on memory_status must block EVERY call until explicitly cleared.
    sig = server.handle_tool_call("verifier_renudge", {
        "target": "memory_status", "correction": {}, "strategy": "halt",
    })
    blocked1 = server.handle_tool_call("memory_status", {})
    blocked2 = server.handle_tool_call("memory_status", {})
    record("renudge: halt persists across calls (memory_status stays blocked)",
           "renudge_halt" in json.dumps(blocked1) and "renudge_halt" in json.dumps(blocked2))

    # 5) verifier drift — real per-key diff, not all-keys.
    d0 = {"a": 1, "b": 2, "c": 3}
    m.fingerprint_state("drift_t1", d0)
    d1 = {"a": 1, "b": 999, "c": 3}  # only b changed
    drift = m.detect_drift("drift_t1", d1)
    record("drift: changed_keys isolates only modified key",
           drift["drifted"] and drift["changed_keys"] == ["b"],
           detail=str(drift["changed_keys"]))

    # 6) a real dispatched tool returns correct output (no mock/placeholder).
    #    memory_search returns a list of {text, score, source, ...} dicts.
    out = server.handle_tool_call("memory_search", {"query": "nonexistent_zzz_query", "limit": 3})
    content = json.loads(out["content"][0]["text"])
    import re as _re
    mock_sig = _re.compile(r"<\s*\w+\s*>_result")
    has_mock = isinstance(content, list) and any(mock_sig.search(str(it.get("text", ""))) for it in content if isinstance(it, dict))
    record("tool: memory_search returns real list of results (no <x>_result mock)",
           isinstance(content, list) and not has_mock,
           detail=f"type={type(content).__name__}, len={len(content) if isinstance(content, list) else 'n/a'}")

    # 7) context_compress: older large raw output is trimmed, recent window kept verbatim
    os.environ["CORTEX_MODEL_TIER"] = "standard"
    big = "x" * 5000
    hist = [{"id": "n1", "output": {"stdout": big, "status": "ok"}},
            {"id": "n2", "output": {"stdout": "y", "status": "ok"}},
            {"id": "n3", "output": {"stdout": "z", "status": "ok"}}]
    cc = server.handle_tool_call("context_compress", {"history": hist, "window": 1})
    ccj = json.loads(cc["content"][0]["text"])
    trimmed = len(ccj["history"][0]["output"]["stdout"]) < 5000
    recent_verbatim = ccj["history"][2]["output"]["stdout"] == "z"
    record("context_compress: trims old raw output, keeps recent window verbatim",
           ccj["ok"] and ccj["compressed_count"] == 2 and trimmed and recent_verbatim,
           detail=f"compressed={ccj['compressed_count']}, trimmed={trimmed}, recent={recent_verbatim}")

    # 8) model_profile: tier drives behavior; 'small' forbids halt renudge (downgraded to override)
    os.environ["CORTEX_MODEL_TIER"] = "small"
    gp = json.loads(server.handle_tool_call("get_model_profile", {})["content"][0]["text"])
    record("model_profile: 'small' tier read from env, forbids halt",
           gp["tier"] == "small" and "halt" not in gp["profile"]["allowed_renudge"],
           detail=f"tier={gp['tier']}, retries={gp['profile']['dag_max_retries']}")
    server.handle_tool_call("verifier_renudge", {"target": "memory_status", "correction": {}, "strategy": "halt"})
    blocked_small = server.handle_tool_call("memory_status", {})
    record("model_profile: halt renudge downgraded to override under 'small' (executes)",
           "renudge_halt" not in json.dumps(blocked_small))
    os.environ.pop("CORTEX_MODEL_TIER", None)

    results["overall"]["status"] = "passed" if results["overall"]["failed"] == 0 else "failed"
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nRESULTS: {results['overall']['passed']}/{results['overall']['total']} passed, "
          f"{results['overall']['failed']} failed")
    return results["overall"]["failed"]


if __name__ == "__main__":
    sys.exit(1 if _main() else 0)
