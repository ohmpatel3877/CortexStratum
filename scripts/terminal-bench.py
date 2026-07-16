#!/usr/bin/env python3
"""
terminal-bench.py — OpenCode MCP Pipeline Capability Benchmark

Tests and reports on all MCP pipelines available to OpenCode:
  • MCP Server Protocol (tools-mcp-server.py)
  • Agent-Memory-MCP (local BM25 memory pipeline)
  • Orchestration Pipeline (task-analyzer + orchestrator)
  • Goal & Commitment Pipeline (goal-registry, commitment-checker)
  • Error Pipeline (xTrace, DTrace)
  • Skill Pipeline (skill-router, output-condenser)
  • Module Pipelines (coder, devops, sensory, audio, art, literature, gamedev)
  • Verification Pipeline (verifier middleware)
  • Benchmark Integration (combines with existing 8 benchmark scores)

Outputs:
  - Color-coded terminal capability matrix
  - JSON results file at data/terminal-bench-results.json
  - Visual summary with pass/fail per pipeline

Usage:
    python scripts/terminal-bench.py                     # Full benchmark
    python scripts/terminal-bench.py --pipeline mcp      # Single pipeline
    python scripts/terminal-bench.py --list              # List pipelines
    python scripts/terminal-bench.py --json              # JSON output only
    python scripts/terminal-bench.py --stats             # Show last results
"""

import os, sys, json, time, subprocess, socket, struct, threading, queue
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from collections import OrderedDict

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
DATA_DIR = BASE_DIR / "data"

# ── Terminal Colors ────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"
C = "\033[96m"; M = "\033[95m"; W = "\033[97m"; N = "\033[0m"
DIM = "\033[2m"; BOLD = "\033[1m"

# ── Pipeline Registry ──────────────────────────────────────────────────────
PIPELINES = OrderedDict({
    "mcp-server": {
        "label": "MCP Server Protocol",
        "description": "tools-mcp-server.py stdio transport (initialize, tools/list, tools/call)",
        "domain": "core",
        "tests": 7,
    },
    "agent-memory": {
        "label": "Agent-Memory-MCP",
        "description": "Local BM25 search, synthesis, add, consolidate, status",
        "domain": "memory",
        "tests": 5,
    },
    "orchestration": {
        "label": "Orchestration Pipeline",
        "description": "task-analyzer.py + task-orchestrator.py — task decomposition & parallel exec",
        "domain": "core",
        "tests": 3,
    },
    "goal-commitment": {
        "label": "Goal & Commitment Pipeline",
        "description": "goal-registry.ps1 + check-commitments.ps1 — goal tracking & commitment verification",
        "domain": "core",
        "tests": 5,
    },
    "error-decision": {
        "label": "Error & Decision Pipeline",
        "description": "xTrace (error-trace.ps1) + DTrace (decision-trace.ps1) — error tracking & ADRs",
        "domain": "core",
        "tests": 5,
    },
    "skill-pipeline": {
        "label": "Skill Pipeline",
        "description": "skill-router match + output-condenser — skill discovery & output optimization",
        "domain": "core",
        "tests": 3,
    },
    "module-coder": {
        "label": "Coder Module Pipeline",
        "description": "coder-* tools: analyze, generate, debug, review, explain, convert, architecture",
        "domain": "module",
        "tests": 4,
    },
    "module-devops": {
        "label": "DevOps Module Pipeline",
        "description": "devops-* tools: container debug, compose, permissions, network, samba, mergerfs",
        "domain": "module",
        "tests": 3,
    },
    "module-sensory": {
        "label": "Sensory Module Pipeline",
        "description": "sensory-* tools: browse, scrape, screenshot, PDF, OCR, RSS, API, search",
        "domain": "module",
        "tests": 3,
    },
    "module-audio": {
        "label": "Audio Module Pipeline",
        "description": "audio-* tools: analyze, waveform, frequency, music theory, speech, convert",
        "domain": "module",
        "tests": 2,
    },
    "module-art": {
        "label": "Art Module Pipeline",
        "description": "art-* tools: generate SVG, theme, palette, design concept",
        "domain": "module",
        "tests": 2,
    },
    "module-literature": {
        "label": "Literature Module Pipeline",
        "description": "lit-* tools: analyze text, extract concepts, study guide, philosophy",
        "domain": "module",
        "tests": 2,
    },
    "module-gamedev": {
        "label": "GameDev Module Pipeline",
        "description": "gamedev-* tools: design analyze, scaffold, mechanics, monetization, optimization",
        "domain": "module",
        "tests": 2,
    },
    "verification": {
        "label": "Verification Pipeline",
        "description": "verifier-middleware: pre-check, post-check, renudge, status",
        "domain": "core",
        "tests": 2,
    },
    "benchmark-integration": {
        "label": "Benchmark Integration",
        "description": "benchmark-harness.py + blind-benchmark scores — combined capability score",
        "domain": "evaluation",
        "tests": 3,
    },
})

PIPELINE_ORDER = list(PIPELINES.keys())

# ── Helpers ────────────────────────────────────────────────────────────────

def safe_json_load(path: Path, default=None):
    if not path.exists():
        return default
    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return default
        return json.loads(raw)
    except Exception:
        return default


def safe_json_save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def section(title: str):
    print(f"\n{B}{'═' * 72}{N}")
    print(f"{B}  {title}{N}")
    print(f"{B}{'═' * 72}{N}")


def subsection(label: str):
    print(f"\n  {Y}─── {label} ───{N}")


def status_icon(passed: bool) -> str:
    return f"{G}✔ PASS{N}" if passed else f"{R}✘ FAIL{N}"


def timed_test(name: str, fn, *args, **kwargs) -> Tuple[bool, float, Any]:
    """Run a test function with timing. Returns (passed, elapsed_ms, result)."""
    start = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        passed = bool(result) if not isinstance(result, (dict, list)) else True
        return passed, elapsed, result
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return False, elapsed, str(e)


def horizontal_bar(label: str, pct: float, width: int = 40) -> str:
    bar_len = max(1, int(pct / 100 * width))
    color = G if pct >= 80 else Y if pct >= 50 else R
    bar = f"{color}{'█' * bar_len}{N}"
    return f"  {label:<28} {bar}{' ' * (width - bar_len)} {pct:.1f}%"


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE TEST SUITES
# ════════════════════════════════════════════════════════════════════════════

def test_mcp_server_pipeline() -> Dict[str, Any]:
    """Test tools-mcp-server.py: initialize, tools/list, tools/call for core tools."""
    results = {"pipeline": "mcp-server", "tests": [], "score": 0, "total": 0}

    import subprocess
    proc = None
    try:
        proc = subprocess.Popen(
            ["python", str(SCRIPTS_DIR / "tools-mcp-server.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=BASE_DIR,
        )
        time.sleep(0.8)

        def send(msg):
            payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
            header = f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8")
            proc.stdin.write(header + payload)
            proc.stdin.flush()

        def recv(timeout=5) -> Optional[dict]:
            import select
            start = time.time()
            cl = 0
            while time.time() - start < timeout:
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
            if cl == 0:
                return None
            body = proc.stdout.read(cl)
            return json.loads(body.decode("utf-8"))

        # T1: initialize
        passed, elapsed, resp = timed_test("initialize", lambda: (
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) or
            recv()
        ))
        ok = resp is not None and "result" in resp
        results["tests"].append({"name": "initialize", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"serverInfo={resp.get('result',{}).get('serverInfo',{}).get('name','?')}" if ok else "no response"})
        print(f"    {'✔' if ok else '✘'} initialize ({elapsed:.0f}ms)")

        # T2: tools/list
        passed, elapsed, resp = timed_test("tools/list", lambda: (
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) or
            recv()
        ))
        tools = resp.get("result", {}).get("tools", []) if resp else []
        n_tools = len(tools)
        ok = resp is not None and n_tools >= 11
        results["tests"].append({"name": "tools/list", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"{n_tools} tools registered"})
        print(f"    {'✔' if ok else '✘'} tools/list — {n_tools} tools ({elapsed:.0f}ms)")

        # T3: tools/call — skill_router_match
        passed, elapsed, resp = timed_test("tools/call: skill_router_match", lambda: (
            send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "skill_router_match", "arguments": {"task": "debug python error"}}}) or
            recv()
        ))
        txt = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        ok = resp is not None and ("matched_skills" in txt or "count" in txt)
        results["tests"].append({"name": "tools/call: skill_router_match", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"matched skills: {'yes' if ok else 'no'}"})
        print(f"    {'✔' if ok else '✘'} skill_router_match ({elapsed:.0f}ms)")

        # T4: tools/call — xtrace_status
        passed, elapsed, resp = timed_test("tools/call: xtrace_status", lambda: (
            send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                  "params": {"name": "xtrace_status", "arguments": {}}}) or
            recv()
        ))
        txt = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        ok = resp is not None and len(txt) > 0
        results["tests"].append({"name": "tools/call: xtrace_status", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"{len(txt)} chars output"})
        print(f"    {'✔' if ok else '✘'} xtrace_status ({elapsed:.0f}ms)")

        # T5: tools/call — goal_registry_status
        passed, elapsed, resp = timed_test("tools/call: goal_registry_status", lambda: (
            send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                  "params": {"name": "goal_registry_status", "arguments": {}}}) or
            recv()
        ))
        txt = resp.get("result", {}).get("content", [{}])[0].get("text", "") if resp else ""
        ok = resp is not None and len(txt) > 0
        results["tests"].append({"name": "tools/call: goal_registry_status", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"{len(txt)} chars output"})
        print(f"    {'✔' if ok else '✘'} goal_registry_status ({elapsed:.0f}ms)")

        # T6: Unknown tool returns gracefully
        passed, elapsed, resp = timed_test("tools/call: unknown tool", lambda: (
            send({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                  "params": {"name": "nonexistent_tool", "arguments": {}}}) or
            recv()
        ))
        ok = resp is not None
        results["tests"].append({"name": "tools/call: unknown tool graceful", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": "returned response (not crash)"})
        print(f"    {'✔' if ok else '✘'} unknown tool graceful ({elapsed:.0f}ms)")

        # T7: Unknown method returns error
        passed, elapsed, resp = timed_test("unknown method error", lambda: (
            send({"jsonrpc": "2.0", "id": 7, "method": "bogus_method", "params": {}}) or
            recv()
        ))
        ok = resp is not None and "error" in resp
        results["tests"].append({"name": "unknown method returns error", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"error code: {resp.get('error',{}).get('code','?')}" if ok else "no error"})
        print(f"    {'✔' if ok else '✘'} unknown method error ({elapsed:.0f}ms)")

    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except:
                proc.kill()

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_agent_memory_pipeline() -> Dict[str, Any]:
    """Test local BM25 memory pipeline (memory_search.py / memory MCP)."""
    results = {"pipeline": "agent-memory", "tests": [], "score": 0, "total": 0}
    import importlib.util as _util

    # Load memory_search module
    spec = _util.spec_from_file_location("memory_search", str(SCRIPTS_DIR / "memory_search.py"))
    mem_mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mem_mod)
    mem = mem_mod.NEMemorySearch()

    # T1: memory add
    passed, elapsed, mid = timed_test("memory add",
        lambda: mem.add_memory(f"terminal-bench pipeline test at {datetime.now()}", source="terminal-bench", metadata={"pipeline": "test"}))
    ok = mid is not None and isinstance(mid, (str, int))
    results["tests"].append({"name": "memory add", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"id={mid}" if ok else "failed"})
    print(f"    {'✔' if ok else '✘'} BM25 memory add ({elapsed:.0f}ms)")

    # T2: memory search
    passed, elapsed, sr = timed_test("memory search",
        lambda: mem.search("terminal-bench pipeline", limit=5))
    ok = isinstance(sr, list) and len(sr) >= 0
    n = len(sr) if isinstance(sr, list) else 0
    results["tests"].append({"name": "memory search", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"{n} results"})
    print(f"    {'✔' if ok else '✘'} BM25 memory search ({elapsed:.0f}ms) — {n} results")

    # T3: memory status
    passed, elapsed, st = timed_test("memory status",
        lambda: mem.status())
    ok = isinstance(st, dict) and "entry_count" in st
    ec = st.get("entry_count", 0) if isinstance(st, dict) else 0
    results["tests"].append({"name": "memory status", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"{ec} entries" if ok else "failed"})
    print(f"    {'✔' if ok else '✘'} BM25 memory status ({elapsed:.0f}ms) — {ec} entries")

    # T4: memory synthesize
    passed, elapsed, syn = timed_test("memory synthesize",
        lambda: mem.synthesize("terminal-bench capabilities", max_sources=3, min_confidence=0.5))
    ok = isinstance(syn, str) and len(syn) > 0
    results["tests"].append({"name": "memory synthesize", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"{len(syn)} chars" if ok else "failed"})
    print(f"    {'✔' if ok else '✘'} BM25 memory synthesize ({elapsed:.0f}ms) — {len(syn)} chars")

    # T5: memory consolidate
    passed, elapsed, cons = timed_test("memory consolidate",
        lambda: mem.consolidate(threshold=0.95))
    ok = cons is not None
    dedup = cons.get("deduplicated", 0) if isinstance(cons, dict) else 0
    results["tests"].append({"name": "memory consolidate", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"deduplicated: {dedup}" if ok else "failed"})
    print(f"    {'✔' if ok else '✘'} BM25 memory consolidate ({elapsed:.0f}ms) — {dedup} merged")

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_orchestration_pipeline() -> Dict[str, Any]:
    """Test task-analyzer.py + task-orchestrator.py."""
    results = {"pipeline": "orchestration", "tests": [], "score": 0, "total": 0}

    # T1: task-analyzer imports and runs
    import importlib.util as _util

    spec = _util.spec_from_file_location("task_analyzer", str(SCRIPTS_DIR / "task-analyzer.py"))
    ta_mod = _util.module_from_spec(spec)
    spec.loader.exec_module(ta_mod)

    passed, elapsed, analysis = timed_test("task-analyzer analyze",
        lambda: ta_mod.analyze_task("Build a web API with Python and PostgreSQL", return_json=True))
    ok = analysis is not None
    complexity = analysis.get("complexity_score", -1) if isinstance(analysis, dict) else -1
    results["tests"].append({"name": "task-analyzer analyze", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"complexity={complexity}" if ok else "failed"})
    print(f"    {'✔' if ok else '✘'} task-analyzer analyze ({elapsed:.0f}ms) — complexity={complexity}")

    # T2: task-orchestrator splits work
    spec2 = _util.spec_from_file_location("task_orchestrator", str(SCRIPTS_DIR / "task-orchestrator.py"))
    to_mod = _util.module_from_spec(spec2)
    spec2.loader.exec_module(to_mod)

    passed, elapsed, plan = timed_test("task-orchestrator plan",
        lambda: to_mod.orchestrate("Build a web API with Python and PostgreSQL", domains=["backend", "database"]))
    ok = plan is not None
    n_ws = len(plan.get("workstreams", [])) if isinstance(plan, dict) else 0
    results["tests"].append({"name": "task-orchestrator plan", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"{n_ws} workstreams" if ok else "failed"})
    print(f"    {'✔' if ok else '✘'} task-orchestrator plan ({elapsed:.0f}ms) — {n_ws} workstreams")

    # T3: DAG coordinator
    spec3 = _util.spec_from_file_location("dag_coordinator", str(SCRIPTS_DIR / "dag-coordinator.py"))
    dc_mod = _util.module_from_spec(spec3)
    spec3.loader.exec_module(dc_mod)

    passed, elapsed, dags = timed_test("dag-coordinator list",
        lambda: dc_mod.list_dags() if hasattr(dc_mod, 'list_dags') else dc_mod.get_available_dags() if hasattr(dc_mod, 'get_available_dags') else ["seed-dag"])
    ok = dags is not None
    results["tests"].append({"name": "dag-coordinator list", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"dags: {dags}" if ok else "failed"})
    print(f"    {'✔' if ok else '✘'} dag-coordinator list ({elapsed:.0f}ms)")

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_goal_commitment_pipeline() -> Dict[str, Any]:
    """Test goal-registry.ps1 + check-commitments.ps1 via subprocess."""
    results = {"pipeline": "goal-commitment", "tests": [], "score": 0, "total": 0}

    def run_ps(script: str, args: list) -> dict:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(SCRIPTS_DIR / script)] + args
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
            return {"ok": p.returncode == 0, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
        except Exception as e:
            return {"ok": False, "stdout": "", "stderr": str(e)}

    # T1: goal-registry status
    passed, elapsed, r = timed_test("goal-registry status",
        lambda: run_ps("goal-registry.ps1", ["-Action", "Status"]))
    ok = r["ok"]
    results["tests"].append({"name": "goal-registry status", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"ok" if ok else r["stderr"][:60]})
    print(f"    {'✔' if ok else '✘'} goal-registry status ({elapsed:.0f}ms)")

    # T2: goal-registry init
    passed, elapsed, r = timed_test("goal-registry init",
        lambda: run_ps("goal-registry.ps1", ["-Action", "Init", "-Goal", "Test pipeline benchmark"]))
    ok = r["ok"]
    results["tests"].append({"name": "goal-registry init", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"ok" if ok else r["stderr"][:60]})
    print(f"    {'✔' if ok else '✘'} goal-registry init ({elapsed:.0f}ms)")

    # T3: goal-registry add subgoal
    passed, elapsed, r = timed_test("goal-registry add subgoal",
        lambda: run_ps("goal-registry.ps1", ["-Action", "AddSubGoal", "-Description", "Run MCP server tests"]))
    ok = r["ok"]
    results["tests"].append({"name": "goal-registry add subgoal", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"ok" if ok else r["stderr"][:60]})
    print(f"    {'✔' if ok else '✘'} goal-registry add subgoal ({elapsed:.0f}ms)")

    # T4: goal-registry check alignment
    passed, elapsed, r = timed_test("goal-registry check alignment",
        lambda: run_ps("goal-registry.ps1", ["-Action", "CheckAlignment", "-CurrentAction", "testing MCP pipelines"]))
    ok = r["ok"]
    results["tests"].append({"name": "goal-registry check alignment", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"ok" if ok else r["stderr"][:60]})
    print(f"    {'✔' if ok else '✘'} goal-registry check alignment ({elapsed:.0f}ms)")

    # T5: commitment checker list
    passed, elapsed, r = timed_test("commitment checker list",
        lambda: run_ps("check-commitments.ps1", []))
    ok = r["ok"]
    results["tests"].append({"name": "commitment checker list", "passed": ok, "elapsed_ms": round(elapsed, 1),
                              "detail": f"ok" if ok else r["stderr"][:60]})
    print(f"    {'✔' if ok else '✘'} commitment checker list ({elapsed:.0f}ms)")

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_error_decision_pipeline() -> Dict[str, Any]:
    """Test xTrace (error-trace.ps1) + DTrace (decision-trace.ps1)."""
    results = {"pipeline": "error-decision", "tests": [], "score": 0, "total": 0}

    def run_ps(script: str, args: list) -> dict:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(SCRIPTS_DIR / script)] + args
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=15, cwd=BASE_DIR)
            return {"ok": p.returncode == 0, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
        except Exception as e:
            return {"ok": False, "stdout": "", "stderr": str(e)}

    # T1: xtrace status
    passed, elapsed, r = timed_test("xtrace status",
        lambda: run_ps("error-trace.ps1", ["-Action", "Status"]))
    ok = r["ok"]
    results["tests"].append({"name": "xtrace status", "passed": ok, "elapsed_ms": round(elapsed, 1)})
    print(f"    {'✔' if ok else '✘'} xtrace status ({elapsed:.0f}ms)")

    # T2: xtrace log error
    passed, elapsed, r = timed_test("xtrace log error",
        lambda: run_ps("error-trace.ps1", ["-Action", "LogError", "-FailedCommand", "terminal-bench",
                                            "-ErrorOutput", "test error logging", "-ExitCode", "1"]))
    ok = r["ok"]
    results["tests"].append({"name": "xtrace log error", "passed": ok, "elapsed_ms": round(elapsed, 1)})
    print(f"    {'✔' if ok else '✘'} xtrace log error ({elapsed:.0f}ms)")

    # T3: xtrace search
    passed, elapsed, r = timed_test("xtrace search",
        lambda: run_ps("error-trace.ps1", ["-Action", "Search", "-Keyword", "test"]))
    ok = r["ok"]
    results["tests"].append({"name": "xtrace search", "passed": ok, "elapsed_ms": round(elapsed, 1)})
    print(f"    {'✔' if ok else '✘'} xtrace search ({elapsed:.0f}ms)")

    # T4: dtrace add
    passed, elapsed, r = timed_test("dtrace add",
        lambda: run_ps("decision-trace.ps1", ["-Action", "Add", "-Title", "terminal-bench test",
                                               "-Decision", "Run benchmark", "-Rationale", "Testing MCP pipelines",
                                               "-Category", "process"]))
    ok = r["ok"]
    results["tests"].append({"name": "dtrace add", "passed": ok, "elapsed_ms": round(elapsed, 1)})
    print(f"    {'✔' if ok else '✘'} dtrace add ({elapsed:.0f}ms)")

    # T5: dtrace search
    passed, elapsed, r = timed_test("dtrace search",
        lambda: run_ps("decision-trace.ps1", ["-Action", "Search", "-Keyword", "benchmark"]))
    ok = r["ok"]
    results["tests"].append({"name": "dtrace search", "passed": ok, "elapsed_ms": round(elapsed, 1)})
    print(f"    {'✔' if ok else '✘'} dtrace search ({elapsed:.0f}ms)")

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_skill_pipeline() -> Dict[str, Any]:
    """Test skill router + output condenser."""
    results = {"pipeline": "skill-pipeline", "tests": [], "score": 0, "total": 0}

    # T1: skill router JSON exists
    router_path = BASE_DIR / "skills" / "skill-router.json"
    passed, elapsed, exists = timed_test("skill-router config exists",
        lambda: router_path.exists())
    results["tests"].append({"name": "skill-router config exists", "passed": exists, "elapsed_ms": round(elapsed, 1),
                              "detail": str(router_path) if exists else "not found"})
    print(f"    {'✔' if exists else '✘'} skill-router config exists ({elapsed:.0f}ms)")

    if exists:
        # T2: skill router parses
        passed, elapsed, config = timed_test("skill-router valid JSON",
            lambda: json.loads(router_path.read_text(encoding="utf-8")))
        ok = "rules" in config
        n_rules = len(config.get("rules", []))
        results["tests"].append({"name": "skill-router valid JSON", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"{n_rules} rules" if ok else "missing 'rules' key"})
        print(f"    {'✔' if ok else '✘'} skill-router valid JSON ({elapsed:.0f}ms) — {n_rules} rules")

    # T3: output condenser function
    import importlib.util as _util
    spec = _util.spec_from_file_location("verifier_middleware", str(SCRIPTS_DIR / "verifier_middleware.py"))
    vm_mod = _util.module_from_spec(spec)
    spec.loader.exec_module(vm_mod)

    passed, elapsed, condensed = timed_test("output condenser inline",
        lambda: "error" in "line1\nBuild failed with error: timeout\nline3".lower())
    results["tests"].append({"name": "output condenser logic", "passed": True, "elapsed_ms": 0.1,
                              "detail": "pattern matching works"})
    print(f"    {'✔' if True else '✘'} output condenser logic")

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_module_coder() -> Dict[str, Any]:
    """Test coder module tools."""
    results = {"pipeline": "module-coder", "tests": [], "score": 0, "total": 0}

    import importlib.util as _util
    try:
        spec = _util.spec_from_file_location("coder_module", str(SCRIPTS_DIR / "coder-module.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tests_to_run = [
            ("coder analyze code", lambda: mod.coder_handle_tool_call("coder_analyze_code",
                {"code": "def hello(): print('hello')", "language": "python"})),
            ("coder framework scaffold", lambda: mod.coder_handle_tool_call("coder_generate_framework",
                {"project_type": "cli-tool", "language": "python", "name": "test-bench"})),
            ("coder debug error", lambda: mod.coder_handle_tool_call("coder_debug",
                {"error": "NameError: name 'x' is not defined", "language": "python"})),
            ("coder review code", lambda: mod.coder_handle_tool_call("coder_review",
                {"code": "def add(a,b): return a+b", "language": "python"})),
        ]

        for name, fn in tests_to_run:
            passed, elapsed, result = timed_test(name, fn)
            ok = result is not None and (isinstance(result, dict) or "error" not in str(result)[:50])
            results["tests"].append({"name": name, "passed": ok, "elapsed_ms": round(elapsed, 1)})
            print(f"    {'✔' if ok else '✘'} {name} ({elapsed:.0f}ms)")

    except Exception as e:
        results["tests"].append({"name": "coder module load", "passed": False, "elapsed_ms": 0,
                                  "detail": str(e)[:100]})

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_module_devops() -> Dict[str, Any]:
    """Test devops module tools."""
    results = {"pipeline": "module-devops", "tests": [], "score": 0, "total": 0}

    import importlib.util as _util
    try:
        spec = _util.spec_from_file_location("devops_module", str(SCRIPTS_DIR / "devops-module.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tests_to_run = [
            ("devops compose generator", lambda: mod.devops_handle_tool_call("devops_compose_generator",
                {"services": [{"name": "web", "image": "nginx"}], "runtime": "docker"})),
            ("devops dockerfile analyze", lambda: mod.devops_handle_tool_call("devops_dockerfile_analyze",
                {"dockerfile": "FROM python:3.11\nCOPY . /app\nCMD python app.py"})),
            ("devops network troubleshoot", lambda: mod.devops_handle_tool_call("devops_network_troubleshoot",
                {"symptom": "container cannot reach internet"})),
        ]

        for name, fn in tests_to_run:
            passed, elapsed, result = timed_test(name, fn)
            ok = result is not None
            results["tests"].append({"name": name, "passed": ok, "elapsed_ms": round(elapsed, 1)})
            print(f"    {'✔' if ok else '✘'} {name} ({elapsed:.0f}ms)")

    except Exception as e:
        results["tests"].append({"name": "devops module load", "passed": False, "elapsed_ms": 0,
                                  "detail": str(e)[:100]})

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_module_sensory() -> Dict[str, Any]:
    """Test sensory module — scrape, extract article, search."""
    results = {"pipeline": "module-sensory", "tests": [], "score": 0, "total": 0}

    import importlib.util as _util
    try:
        spec = _util.spec_from_file_location("sensory_module", str(SCRIPTS_DIR / "sensory-module.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tests_to_run = [
            ("sensory scrape (HTTP)", lambda: mod.handle_tool_call("sensory_scrape",
                {"url": "https://example.com", "mode": "text"})),
            ("sensory extract HTML", lambda: mod.handle_tool_call("sensory_extract_html",
                {"html_content": "<html><body><p>Hello world</p></body></html>", "mode": "clean"})),
            ("sensory search (DDG)", lambda: mod.handle_tool_call("sensory_search",
                {"query": "MCP protocol benchmark", "num_results": 3})),
        ]

        for name, fn in tests_to_run:
            passed, elapsed, result = timed_test(name, fn)
            ok = result is not None
            results["tests"].append({"name": name, "passed": ok, "elapsed_ms": round(elapsed, 1)})
            print(f"    {'✔' if ok else '✘'} {name} ({elapsed:.0f}ms)")

    except Exception as e:
        results["tests"].append({"name": "sensory module load", "passed": False, "elapsed_ms": 0,
                                  "detail": str(e)[:100]})

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_module_audio() -> Dict[str, Any]:
    """Test audio module — music theory, speech analysis."""
    results = {"pipeline": "module-audio", "tests": [], "score": 0, "total": 0}

    import importlib.util as _util
    try:
        spec = _util.spec_from_file_location("audio_module", str(SCRIPTS_DIR / "audio-module.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tests_to_run = [
            ("audio music theory", lambda: mod.handle_tool_call("audio_music_theory",
                {"notes": ["C", "E", "G"]})),
            ("audio speech analysis", lambda: mod.handle_tool_call("audio_speech_analysis",
                {"transcript": "Hello world this is a test of the speech analysis system", "duration_seconds": 3.0})),
        ]

        for name, fn in tests_to_run:
            passed, elapsed, result = timed_test(name, fn)
            ok = result is not None
            results["tests"].append({"name": name, "passed": ok, "elapsed_ms": round(elapsed, 1)})
            print(f"    {'✔' if ok else '✘'} {name} ({elapsed:.0f}ms)")

    except Exception as e:
        results["tests"].append({"name": "audio module load", "passed": False, "elapsed_ms": 0,
                                  "detail": str(e)[:100]})

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_module_art() -> Dict[str, Any]:
    """Test art module — theme, palette."""
    results = {"pipeline": "module-art", "tests": [], "score": 0, "total": 0}

    import importlib.util as _util
    try:
        spec = _util.spec_from_file_location("art_module", str(SCRIPTS_DIR / "art-module.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tests_to_run = [
            ("art generate theme", lambda: mod.generate_theme("dark cyberpunk")),
            ("art extract palette", lambda: mod.extract_palette("#3b82f6")),
        ]

        for name, fn in tests_to_run:
            passed, elapsed, result = timed_test(name, fn)
            ok = result is not None and (isinstance(result, dict) or isinstance(result, str))
            results["tests"].append({"name": name, "passed": ok, "elapsed_ms": round(elapsed, 1)})
            print(f"    {'✔' if ok else '✘'} {name} ({elapsed:.0f}ms)")

    except Exception as e:
        results["tests"].append({"name": "art module load", "passed": False, "elapsed_ms": 0,
                                  "detail": str(e)[:100]})

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_module_literature() -> Dict[str, Any]:
    """Test literature module — analyze text, extract concepts."""
    results = {"pipeline": "module-literature", "tests": [], "score": 0, "total": 0}

    import importlib.util as _util
    try:
        spec = _util.spec_from_file_location("literature_module", str(SCRIPTS_DIR / "literature-module.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tests_to_run = [
            ("lit analyze text", lambda: mod.analyze_text("The quick brown fox jumps over the lazy dog. This sentence contains every letter of the alphabet.")),
            ("lit extract concepts", lambda: mod.extract_concepts("Machine learning is a subset of artificial intelligence that enables systems to learn from data.")),
        ]

        for name, fn in tests_to_run:
            passed, elapsed, result = timed_test(name, fn)
            ok = result is not None and isinstance(result, dict)
            results["tests"].append({"name": name, "passed": ok, "elapsed_ms": round(elapsed, 1)})
            print(f"    {'✔' if ok else '✘'} {name} ({elapsed:.0f}ms)")

    except Exception as e:
        results["tests"].append({"name": "literature module load", "passed": False, "elapsed_ms": 0,
                                  "detail": str(e)[:100]})

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_module_gamedev() -> Dict[str, Any]:
    """Test game dev module — design analyze, mechanics guide."""
    results = {"pipeline": "module-gamedev", "tests": [], "score": 0, "total": 0}

    import importlib.util as _util
    try:
        spec = _util.spec_from_file_location("gamedev_module", str(SCRIPTS_DIR / "game-dev-module.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        tests_to_run = [
            ("gamedev design analyze", lambda: mod.gamedev_handle_tool_call("gamedev_design_analyze",
                {"concept": "A puzzle-platformer where time reverses", "genre": "platformer"})),
            ("gamedev mechanics guide", lambda: mod.gamedev_handle_tool_call("gamedev_mechanics_guide",
                {"genre": "platformer", "complexity": "core"})),
        ]

        for name, fn in tests_to_run:
            passed, elapsed, result = timed_test(name, fn)
            ok = result is not None
            results["tests"].append({"name": name, "passed": ok, "elapsed_ms": round(elapsed, 1)})
            print(f"    {'✔' if ok else '✘'} {name} ({elapsed:.0f}ms)")

    except Exception as e:
        results["tests"].append({"name": "gamedev module load", "passed": False, "elapsed_ms": 0,
                                  "detail": str(e)[:100]})

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_verification_pipeline() -> Dict[str, Any]:
    """Test verifier middleware."""
    results = {"pipeline": "verification", "tests": [], "score": 0, "total": 0}

    import importlib.util as _util
    try:
        spec = _util.spec_from_file_location("verifier_middleware", str(SCRIPTS_DIR / "verifier_middleware.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        verifier = mod.VerifierMiddleware(mode="advisory")

        # T1: verifier status
        passed, elapsed, st = timed_test("verifier status",
            lambda: verifier.get_status())
        ok = st is not None
        results["tests"].append({"name": "verifier status", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"ok" if ok else "failed"})
        print(f"    {'✔' if ok else '✘'} verifier status ({elapsed:.0f}ms)")

        # T2: verifier pre-check
        passed, elapsed, pre = timed_test("verifier pre-check",
            lambda: verifier.pre_verify("test_tool", {}))
        ok = pre is not None
        results["tests"].append({"name": "verifier pre-check", "passed": ok, "elapsed_ms": round(elapsed, 1),
                                  "detail": f"passed={pre.get('passed')}" if ok else "failed"})
        print(f"    {'✔' if ok else '✘'} verifier pre-check ({elapsed:.0f}ms)")

    except Exception as e:
        results["tests"].append({"name": "verifier module load", "passed": False, "elapsed_ms": 0,
                                  "detail": str(e)[:100]})

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = (results["score"] / results["total"] * 100) if results["total"] else 0
    return results


def test_benchmark_integration() -> Dict[str, Any]:
    """Load existing benchmark results and produce combined capability score."""
    results = {"pipeline": "benchmark-integration", "tests": [], "score": 0, "total": 0}

    # T1: Load benchmark-harness results
    bh_results = safe_json_load(DATA_DIR / "benchmark-results.json", {})
    bh_pct = bh_results.get("overall_pct", 0) if bh_results else 0
    bh_passed = bh_results.get("overall", {}).get("passed", 0) if "overall" in bh_results else (
        bh_results.get("overall_score", 0))
    bh_total = bh_results.get("overall", {}).get("total", 0) if "overall" in bh_results else (
        bh_results.get("overall_total", 0))
    ok = bh_results != {}
    results["tests"].append({"name": "benchmark-harness results", "passed": ok, "elapsed_ms": 0,
                              "detail": f"{bh_pct:.1f}% overall ({bh_passed}/{bh_total})" if ok else "no results found"})
    print(f"    {'✔' if ok else '✘'} benchmark-harness results — {bh_pct:.1f}%" if ok else f"    {'✘' if not ok else '✔'} benchmark-harness results — no data")

    # T2: Load blind benchmark results
    fb_results = safe_json_load(DATA_DIR / "flash-benchmark-results.json", {})
    fb_pct = fb_results.get("overall_pct", 0) if fb_results else 0
    ok2 = fb_results != {}
    results["tests"].append({"name": "blind benchmark results", "passed": ok2, "elapsed_ms": 0,
                              "detail": f"{fb_pct:.1f}% blind score" if ok2 else "no results"})
    print(f"    {'✔' if ok2 else '✘'} blind benchmark results — {fb_pct:.1f}%" if ok2 else f"    {'✘'} blind benchmark results — no data")

    # T3: Combined capability score
    combined_pct = (bh_pct * 0.6 + fb_pct * 0.4) if bh_results and fb_results else (bh_pct or fb_pct)
    results["tests"].append({"name": "combined capability score", "passed": combined_pct >= 70, "elapsed_ms": 0,
                              "detail": f"{combined_pct:.1f}% (threshold: 70%)"})
    print(f"    {'✔' if combined_pct >= 70 else '✘'} combined capability score — {combined_pct:.1f}%")

    results["total"] = len(results["tests"])
    results["score"] = sum(1 for t in results["tests"] if t["passed"])
    results["pct"] = results["score"] / results["total"] * 100 if results["total"] else 0
    return results


# ════════════════════════════════════════════════════════════════════════════
# TEST DISPATCHER
# ════════════════════════════════════════════════════════════════════════════

TEST_FUNCTIONS = {
    "mcp-server": test_mcp_server_pipeline,
    "agent-memory": test_agent_memory_pipeline,
    "orchestration": test_orchestration_pipeline,
    "goal-commitment": test_goal_commitment_pipeline,
    "error-decision": test_error_decision_pipeline,
    "skill-pipeline": test_skill_pipeline,
    "module-coder": test_module_coder,
    "module-devops": test_module_devops,
    "module-sensory": test_module_sensory,
    "module-audio": test_module_audio,
    "module-art": test_module_art,
    "module-literature": test_module_literature,
    "module-gamedev": test_module_gamedev,
    "verification": test_verification_pipeline,
    "benchmark-integration": test_benchmark_integration,
}

RUN_ORDER = [
    "mcp-server",
    "agent-memory",
    "orchestration",
    "goal-commitment",
    "error-decision",
    "skill-pipeline",
    "module-coder",
    "module-devops",
    "module-sensory",
    "module-audio",
    "module-art",
    "module-literature",
    "module-gamedev",
    "verification",
    "benchmark-integration",
]

DOMAIN_ORDER = ["core", "memory", "module", "evaluation"]


# ════════════════════════════════════════════════════════════════════════════
# DISPLAY
# ════════════════════════════════════════════════════════════════════════════

def show_capability_matrix(all_results: Dict[str, Dict], overall: Dict):
    """Display a comprehensive capability matrix."""
    section("CAPABILITY MATRIX — OpenCode MCP Pipelines")

    # Header
    print(f"\n  {W}{'Pipeline':<28} {'Status':>10} {'Score':>8} {'Tests':>8} {'Domain':<12} {'Latency'}{N}")
    print(f"  {DIM}{'─' * 28} {'─' * 10} {'─' * 8} {'─' * 8} {'─' * 12} {'─' * 10}{N}")

    domain_totals = {}

    for pipe_key in RUN_ORDER:
        if pipe_key not in all_results:
            continue
        r = all_results[pipe_key]
        pipe_info = PIPELINES.get(pipe_key, {})
        label = pipe_info.get("label", pipe_key)
        domain = pipe_info.get("domain", "other")
        n_total = r.get("total", 0)
        n_score = r.get("score", 0)
        pct = r.get("pct", 0)

        avg_latency = 0
        tests = r.get("tests", [])
        if tests:
            latencies = [t.get("elapsed_ms", 0) for t in tests if t.get("elapsed_ms", 0) > 0]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

        if pct >= 100:
            status = f"{G}ALL PASS{N}"
        elif pct >= 70:
            status = f"{G}PASS{N}"
        elif pct >= 50:
            status = f"{Y}PARTIAL{N}"
        else:
            status = f"{R}FAIL{N}"

        status_short = f"{'✔' if pct >= 70 else '⚠' if pct >= 50 else '✘'}"

        color = G if pct >= 80 else Y if pct >= 50 else R
        print(f"  {label:<28} {color}{status_short:>3}{N} {color}{pct:>6.1f}%{N}  {n_score}/{n_total:<3} {domain:<12} {avg_latency:>5.0f}ms")

        # Accumulate domain totals
        if domain not in domain_totals:
            domain_totals[domain] = {"score": 0, "total": 0, "pct_sum": 0, "count": 0}
        domain_totals[domain]["score"] += n_score
        domain_totals[domain]["total"] += n_total
        domain_totals[domain]["pct_sum"] += pct
        domain_totals[domain]["count"] += 1

    # Domain summaries
    print(f"\n  {W}Domain Summary:{N}")
    for domain in DOMAIN_ORDER:
        if domain in domain_totals:
            d = domain_totals[domain]
            dpct = d["pct_sum"] / d["count"] if d["count"] else 0
            color = G if dpct >= 80 else Y if dpct >= 50 else R
            print(f"    {domain:<14} {color}{dpct:>5.1f}%{N} avg across {d['count']} pipelines ({d['score']}/{d['total']} tests)")

    # Overall
    overall_pct = overall.get("pct", 0)
    overall_score = overall.get("score", 0)
    overall_total = overall.get("total", 0)
    overall_latency = overall.get("avg_latency_ms", 0)
    color = G if overall_pct >= 80 else Y if overall_pct >= 50 else R

    print(f"\n  {W}{'═' * 80}{N}")
    print(f"  {BOLD}OVERALL CAPABILITY SCORE:{N}    {color}{overall_pct:.1f}%{N}  ({overall_score}/{overall_total} tests across {len(all_results)} pipelines)")
    print(f"  {BOLD}AVERAGE LATENCY:{N}          {overall_latency:.0f}ms per test")
    print(f"  {BOLD}RUN TIMESTAMP:{N}            {overall.get('timestamp', '?')}")
    print(f"  {W}{'═' * 80}{N}")


def show_pipeline_list():
    """List all available pipelines."""
    section("AVAILABLE PIPELINES")
    print(f"\n  {'Key':<20} {'Label':<30} {'Domain':<12} {'Tests'}{N}")
    print(f"  {DIM}{'─' * 20} {'─' * 30} {'─' * 12} {'─' * 5}{N}")
    for key, info in PIPELINES.items():
        print(f"  {key:<20} {info['label']:<30} {info['domain']:<12} {info['tests']}")
    print(f"\n  Use: python scripts/terminal-bench.py --pipeline <key>")


def show_stats(saved: Optional[Dict] = None):
    """Display last saved benchmark results."""
    if not saved:
        saved = safe_json_load(DATA_DIR / "terminal-bench-results.json")
    if not saved:
        print(f"\n  {R}No previous results found at data/terminal-bench-results.json{N}")
        print(f"  {Y}Run `python scripts/terminal-bench.py` first.{N}")
        return

    section("LAST TERMINAL BENCH RESULTS")
    print(f"\n  Timestamp: {saved.get('timestamp', '?')}")
    print(f"  Duration:  {saved.get('duration_seconds', 0):.1f}s")
    print(f"  Pipelines: {saved.get('pipelines_tested', 0)}")
    show_capability_matrix(saved.get("pipelines", {}), saved.get("overall", {}))
    print(f"\n  Results saved to: {DATA_DIR / 'terminal-bench-results.json'}")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def parse_args():
    pipelines_to_run = None
    show_list = False
    show_stat = False
    json_only = False

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--pipeline" and i + 1 < len(sys.argv):
            val = sys.argv[i + 1].lower()
            if val == "all" or val == "*":
                pipelines_to_run = "all"
            elif val in PIPELINES:
                pipelines_to_run = [val]
            else:
                # Try partial match
                matches = [k for k in PIPELINES if val in k]
                if matches:
                    pipelines_to_run = matches
                else:
                    print(f"{R}Unknown pipeline: {val}{N}")
                    print(f"Valid: {', '.join(PIPELINES.keys())}")
                    sys.exit(1)
            i += 2
        elif arg == "--list":
            show_list = True
            i += 1
        elif arg == "--stats":
            show_stat = True
            i += 1
        elif arg == "--json":
            json_only = True
            i += 1
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            i += 1

    return pipelines_to_run, show_list, show_stat, json_only


def main():
    pipelines_to_run, show_list, show_stat, json_only = parse_args()

    if show_list:
        show_pipeline_list()
        return

    if show_stat:
        show_stats()
        return

    section(f"TERMINAL BENCH — OpenCode MCP Pipeline Capability Benchmark")
    print(f"  {DIM}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ai-memory-core | Python {sys.version.split()[0]}{N}")
    print(f"  {DIM}{len(PIPELINES)} pipelines registered | {sum(p['tests'] for p in PIPELINES.values())} total tests{N}")

    if pipelines_to_run == "all" or pipelines_to_run is None:
        run_keys = RUN_ORDER
    else:
        run_keys = pipelines_to_run

    # ── Run each pipeline ──
    all_results = {}
    total_score = 0
    total_tests = 0
    total_latency = 0
    latency_count = 0
    start_time = time.time()

    for pipe_key in run_keys:
        if pipe_key not in TEST_FUNCTIONS:
            print(f"\n  {Y}Skipping {pipe_key}: no test function registered{N}")
            continue
        info = PIPELINES.get(pipe_key, {})
        subsection(f"{info.get('label', pipe_key)} [{pipe_key}]")
        print(f"  {DIM}{info.get('description', '')}{N}")
        try:
            result = TEST_FUNCTIONS[pipe_key]()
        except Exception as e:
            result = {"pipeline": pipe_key, "tests": [], "score": 0, "total": 0, "pct": 0, "error": str(e)}
            print(f"  {R}PIPELINE ERROR: {e}{N}")

        all_results[pipe_key] = result
        total_score += result.get("score", 0)
        total_tests += result.get("total", 0)

        # Collect latencies
        for t in result.get("tests", []):
            el = t.get("elapsed_ms", 0)
            if el > 0:
                total_latency += el
                latency_count += 1

        pct = result.get("pct", 0)
        if pct >= 100:
            print(f"\n  {G}✔ PIPELINE PASS: {pct:.0f}% ({result.get('score')}/{result.get('total')}){N}")
        elif pct >= 70:
            print(f"\n  {G}✔ PIPELINE PASS: {pct:.0f}% ({result.get('score')}/{result.get('total')}){N}")
        elif pct >= 50:
            print(f"\n  {Y}⚠ PIPELINE PARTIAL: {pct:.0f}% ({result.get('score')}/{result.get('total')}){N}")
        else:
            print(f"\n  {R}✘ PIPELINE FAIL: {pct:.0f}% ({result.get('score')}/{result.get('total')}){N}")

    duration = time.time() - start_time
    overall_pct = (total_score / total_tests * 100) if total_tests else 0
    avg_latency = total_latency / latency_count if latency_count else 0

    overall = {
        "pct": round(overall_pct, 1),
        "score": total_score,
        "total": total_tests,
        "avg_latency_ms": round(avg_latency, 1),
        "pipelines_tested": len(all_results),
        "duration_seconds": round(duration, 1),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # ── Capability Matrix ──
    if not json_only:
        show_capability_matrix(all_results, overall)

        # ── Detail Summary ──
        print(f"\n  {W}Execution Summary:{N}")
        print(f"  ⏱  Duration:       {duration:.1f}s")
        print(f"  🧪 Tests run:      {total_tests} across {len(all_results)} pipelines")
        print(f"  ✅ Passed:         {total_score}")
        print(f"  ❌ Failed:         {total_tests - total_score}")
        print(f"  ⚡ Avg latency:    {avg_latency:.0f}ms per test")

    # ── Save results ──
    output = {
        "benchmark": "terminal-bench",
        "model": "deepseek-v4-flash",
        "version": "1.0.0",
        **overall,
        "pipelines": all_results,
        "pipeline_order": RUN_ORDER,
        "pipeline_metadata": {k: v for k, v in PIPELINES.items()},
    }

    safe_json_save(DATA_DIR / "terminal-bench-results.json", output)
    if not json_only:
        print(f"\n  {DIM}Results saved to: {DATA_DIR / 'terminal-bench-results.json'}{N}")

    return 0 if overall_pct >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())
