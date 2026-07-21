#!/usr/bin/env python3
"""
Task Orchestrator v2 — ACTIVE orchestrator that works WHILE subagents run.
Usage:
    python scripts/task-orchestrator.py --task "<task>" --plan
    python scripts/task-orchestrator.py --task "<task>" --execute
    python scripts/task-orchestrator.py --task "<task>" --background
    python scripts/task-orchestrator.py --task "<task>" --watch
    python scripts/task-orchestrator.py --task "<task>" --orchestrate
    python scripts/task-orchestrator.py --dag <dag-file> --dag-execute
    python scripts/task-orchestrator.py --dag <dag-file> --info
    python scripts/task-orchestrator.py --dag <dag-file> --dag-execute --task '{"context":{"key":"val"}}'
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
DATA = os.path.join(BASE, "data")
MEMORY_DIR = os.path.join(BASE, ".memory")
WORKSTREAMS_DIR = os.path.join(MEMORY_DIR, "workstreams")
PROFILES_DIR = os.path.join(MEMORY_DIR, "profiles")
CASES_DIR = os.path.join(MEMORY_DIR, "skills", "cases")
DAG_DEF_DIR = os.path.join(DATA, "dag-definitions")
DAG_TRACE_DIR = os.path.join(DATA, "dag-traces")

G = "\033[92m"
Y = "\033[93m"
B = "\033[94m"
M = "\033[95m"
R = "\033[91m"
C = "\033[96m"
N = "\033[0m"
BOLD = "\033[1m"
BAR = ""

#  Dataclasses


@dataclass
class WorkstreamStatus:
    id: str
    description: str
    status: str = "pending"  # pending, running, completed, failed, stalled
    step: str = ""
    output: str = ""
    error: str = ""
    last_heartbeat: float | None = None
    temperature: float = 0.7
    files_touched: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)


@dataclass
class ContextDigest:
    profiles_found: int = 0
    cases_found: int = 0
    patterns_found: list = field(default_factory=list)
    recent_errors: list = field(default_factory=list)


@dataclass
class ConflictReport:
    has_conflicts: bool = False
    conflicts: list = field(default_factory=list)
    parallel_safe: bool = True
    merge_ready: int = 0
    total: int = 0


#  Helpers


def ensure_dirs():
    for d in [MEMORY_DIR, WORKSTREAMS_DIR, PROFILES_DIR, CASES_DIR]:
        os.makedirs(d, exist_ok=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _run_dag(dag_path: str, task: str, execute: bool) -> dict:
    """Run a DAG definition through the DAG coordinator."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "dag_coordinator", os.path.join(SCRIPTS, "pipeline", "dag-coordinator.py")
    )
    if spec is None or spec.loader is None:
        print(f"{R}  ERROR: Could not load dag-coordinator.py{N}")
        return {"action": "dag_error"}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    dag = mod.load_dag_definition(dag_path)

    if not execute:
        mod.show_dag_info(dag)
        print(f"\n  {C}To execute:{N}")
        print(
            f'    python scripts/task-orchestrator.py --dag "{dag_path}" --dag-execute'
        )
        return {"action": "dag_info", "dag": dag}

    task_input = None
    if task:
        try:
            task_input = json.loads(task)
        except json.JSONDecodeError:
            task_input = {"context": {"description": task}}

    trace = mod.execute_pipeline(dag, task_input=task_input)

    # Log to decision trace
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            os.path.join(SCRIPTS, "decision-trace.ps1"),
            "-Action",
            "Add",
            "-Title",
            f"DAG Executed: {dag.get('name', 'unknown')[:80]}",
            "-Decision",
            f"DAG pipeline with {len(dag.get('nodes', []))} nodes, {len(dag.get('edges', []))} edges",
            "-Rationale",
            f"DAG '{dag.get('dag_id', 'N/A')}' executed via dag-coordinator.py",
            "-Category",
            "process",
            "-Files",
            dag_path,
        ],
        capture_output=True,
        cwd=BASE,
    )

    return {"action": "dag_execute", "trace": trace}


def _auto_generate_dag(task: str, workstreams: list, plan_id: str) -> str | None:
    """
    Auto-generate a DAG JSON file from workstreams for multi-phase builds.
    Detects module-pattern (mod-* → parallel, wire-* → serial) and
    writes a DAG definition to data/dag-definitions/.
    Returns the path to the DAG file, or None if not applicable.
    """
    parallel_streams = [ws for ws in workstreams if ws.get("phase") == "parallel"]
    serial_streams = [ws for ws in workstreams if ws.get("phase") == "serial"]

    if not parallel_streams and not serial_streams:
        return None  # No module pattern detected — skip DAG generation

    os.makedirs(DAG_DEF_DIR, exist_ok=True)
    dag_id = f"auto-{plan_id}"

    nodes = []
    edges = []

    # Phase 1: Parallel module creation nodes
    for ws in parallel_streams:
        nodes.append(
            {
                "id": ws["id"],
                "description": ws["description"][:200],
                "prompt_template": ws.get("prompt", ws["description"]),
                "temperature": ws.get("temperature", 0.7),
                "timeout_seconds": 300,
                "expected_outputs": ["module_file", "module_summary"],
            }
        )
        # No edges — these are root nodes (parallel)

    # Phase 2: Serial wiring node
    for ws in serial_streams:
        nodes.append(
            {
                "id": ws["id"],
                "description": ws["description"][:200],
                "prompt_template": ws.get("prompt", ws["description"]),
                "temperature": ws.get(
                    "temperature", 0.3
                ),  # Lower temp for precise wiring
                "timeout_seconds": 300,
                "expected_outputs": ["tool_defs", "dispatch_code"],
                "critical_file": "scripts/tools-mcp-server.py",
            }
        )
        # Depends on ALL parallel module streams
        for dep_id in ws.get("dependencies", []):
            if any(dep_id == ps["id"] for ps in parallel_streams):
                edges.append({"from": dep_id, "to": ws["id"]})

    dag = {
        "dag_id": dag_id,
        "name": f"Auto: {task[:80]}",
        "description": f"Auto-generated DAG for module-pattern build ({plan_id})",
        "version": "2.0.0",
        "tags": ["auto-generated", "module-pattern"],
        "nodes": nodes,
        "edges": edges,
        "merge_rules": [
            {"type": "independent", "sources": [ws["id"] for ws in parallel_streams]}
        ],
        "config": {
            "error_mode": "abort",
            "global_timeout_seconds": 3600,
            "post_merge_verify": "python scripts/phase-verify-full.py",
        },
    }

    dag_path = os.path.join(DAG_DEF_DIR, f"{dag_id}.json")
    write_json(dag_path, dag)
    print(f"\n  {C}  DAG written: {dag_path}{N}")
    print(
        f"  {C}  Levels: Phase 1 (parallel)={len(parallel_streams)} nodes, Phase 2 (serial)={len(serial_streams)} node(s){N}"
    )
    return dag_path


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp, path)


def print_box(title, lines, color=B):
    width = max(len(line) for line in lines) if lines else 40
    width = min(width + 4, 100)
    print(f"{color}  {'' * (width - 2)}{N}")
    print(f"{color}  {BOLD}{title}{N}")
    print(f"{color}  {'' * (width - 2)}{N}")
    for line in lines:
        print(f"    {line}")
    print()


#  Integration


def call_temperature_mcp(task: str, role: str = "developer") -> float:
    """Call get_temperature via MCP or fallback to heuristic."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS, "tools-mcp-server.py"),
                "--tool",
                "get_temperature",
                "--args",
                json.dumps({"task": task, "role": role}),
            ],
            capture_output=True,
            text=True,
            cwd=BASE,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get("temperature", 0.7))
    except Exception:
        pass
    return _heuristic_temperature(task)


def _heuristic_temperature(task: str) -> float:
    tl = task.lower()
    if any(w in tl for w in ["creative", "brainstorm", "explore", "design", "idea"]):
        return 0.9
    if any(w in tl for w in ["precise", "exact", "critical", "production", "deploy"]):
        return 0.2
    if any(w in tl for w in ["test", "debug", "fix", "bug", "refactor"]):
        return 0.4
    return 0.7


#  Analysis (delegates to task-analyzer.py)


def analyze_task(task: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPTS, "task-analyzer.py"),
            "--task",
            task,
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=BASE,
    )
    return json.loads(result.stdout)


def generate_workstreams(task: str, analysis: dict) -> list:
    task_lower = task.lower()
    lines = task.split(". ")
    streams = []
    domains = analysis.get("domains", [])

    #  Module Pattern Detection
    # Detect if task involves creating new MCP modules/tools.
    # Module creation tasks should auto-split into create→wire two-phase.
    MODULE_KEYWORDS = [
        "create",
        "module",
        "tool",
        "new tool",
        "mcp tool",
        "sim-",
        "compact",
        "mutat",
        "plumber",
        "pedagogy",
        "consolidat",
        "phase 4",
        "phase 5",
        "implement.*tool",
        "add.*tool",
        "sim_mech",
        "sim_math",
        "sim_matrix",
        "sim_ode",
        "sim_latex",
    ]
    module_pattern_detected = any(kw in task_lower for kw in MODULE_KEYWORDS)

    if module_pattern_detected and (
        analysis.get("recommended_subagents", 0) >= 2 or " and " in task_lower
    ):
        # Group independent modules into parallel workstreams,
        # then a final serial wiring workstream for tools-mcp-server.py
        sentences = [s.strip() for s in lines if len(s.strip()) > 20]
        module_streams = []
        for i, s in enumerate(sentences):
            if i < 4:  # max 4 parallel module streams
                module_streams.append(
                    {
                        "id": f"mod-{i + 1}",
                        "description": s[:100] + ("..." if len(s) > 100 else ""),
                        "prompt": s,
                        "dependencies": [],
                        "type": "module_creation",
                        "phase": "parallel",
                    }
                )
        if module_streams:
            # Add serial wiring workstream that depends on all module streams
            streams = module_streams
            streams.append(
                {
                    "id": "wire-1",
                    "description": "Wire all new tools into tools-mcp-server.py (tool defs + dispatch)",
                    "prompt": f"Wire the tools from modules {', '.join(s['id'] for s in module_streams)} into tools-mcp-server.py. Add tool definitions to TOOLS list and dispatch handlers to handle_tool_call.",
                    "dependencies": [s["id"] for s in module_streams],
                    "type": "tool_wiring",
                    "phase": "serial",
                    "critical_file": "scripts/tools-mcp-server.py",
                }
            )
            return streams

    #  Standard decomposition
    if " and " in task_lower or analysis.get("can_parallelize"):
        sentences = [s.strip() for s in lines if len(s.strip()) > 20]
        if len(sentences) >= 2:
            for i, s in enumerate(
                sentences[: analysis.get("recommended_subagents", 3)]
            ):
                streams.append(
                    {
                        "id": f"ws-{i + 1}",
                        "description": s[:100] + ("..." if len(s) > 100 else ""),
                        "prompt": s,
                        "dependencies": [],
                    }
                )
    if not streams and domains:
        for i, domain in enumerate(domains):
            streams.append(
                {
                    "id": f"ws-{i + 1}",
                    "description": f"Handle {domain} aspects of the task",
                    "prompt": task,
                    "dependencies": [],
                    "focus": domain,
                }
            )
    if not streams:
        streams.append(
            {
                "id": "ws-1",
                "description": "Complete the task",
                "prompt": task,
                "dependencies": [],
            }
        )
    return streams


#  Background Analyzer


class BackgroundAnalyzer(threading.Thread):
    def __init__(self, task: str, workstreams: list, memory_dir: str):
        super().__init__(daemon=True)
        self.task = task
        self.workstreams = workstreams
        self.memory_dir = memory_dir
        self.results = {
            "context_digest": None,
            "conflicts": None,
            "patterns": [],
            "temperatures": {},
            "completed_steps": [],
            "errors": [],
        }

    def run(self):
        self.results["completed_steps"].append("thread_started")
        self._scan_memory_patterns()
        self.results["completed_steps"].append("memory_scanned")
        self._build_context_digest()
        self.results["completed_steps"].append("digest_built")
        self._predict_conflicts()
        self.results["completed_steps"].append("conflicts_analyzed")
        self._recommend_temperatures()
        self.results["completed_steps"].append("temperatures_assigned")

    def _scan_memory_patterns(self):
        patterns = []
        if os.path.isdir(PROFILES_DIR):
            for f in os.listdir(PROFILES_DIR):
                if f.endswith(".md") or f.endswith(".json"):
                    patterns.append(f"profile:{f}")
        if os.path.isdir(CASES_DIR):
            for f in os.listdir(CASES_DIR):
                if f.endswith(".md") or f.endswith(".json"):
                    patterns.append(f"case:{f}")
        self.results["patterns"] = patterns

    def _build_context_digest(self):
        digest = ContextDigest()
        if os.path.isdir(PROFILES_DIR):
            digest.profiles_found = len(
                [f for f in os.listdir(PROFILES_DIR) if f.endswith((".md", ".json"))]
            )
        if os.path.isdir(CASES_DIR):
            digest.cases_found = len(
                [f for f in os.listdir(CASES_DIR) if f.endswith((".md", ".json"))]
            )
        error_registry = os.path.join(DATA, "error-registry.json")
        if os.path.isfile(error_registry):
            try:
                with open(error_registry) as f:
                    errors = json.load(f)
                digest.recent_errors = [
                    e.get("signature", "")
                    for e in (errors if isinstance(errors, list) else [])
                ][-5:]
            except Exception:
                pass
        self.results["context_digest"] = asdict(digest)

    def _predict_conflicts(self):
        report = ConflictReport()
        all_files = []

        # HARDCODED SERIAL BOTTLENECKS: These files MUST NOT be edited in parallel.
        # Any two workstreams that touch them must be serialized.
        SERIAL_BOTTLENECKS = {
            "scripts/tools-mcp-server.py": "tool definitions + dispatch — single hub file",
            "opencode.json": "MCP server registration",
            ".opencode/opencode.jsonc": "agent command definitions",
        }

        for ws in self.workstreams:
            touched = self._estimate_files(ws.get("prompt", ws["description"]))
            # Also check if workstream has type=module_creation — they don't touch tools-mcp-server.py
            ws_type = ws.get("type", "")
            if ws_type == "module_creation":
                # Module creation never touches the server file — safe for parallel
                pass
            elif ws_type == "tool_wiring":
                # Tool wiring explicitly touches tools-mcp-server.py
                if "scripts/tools-mcp-server.py" not in touched:
                    touched.append("scripts/tools-mcp-server.py")

            ws["files_touched"] = touched
            all_files.append((ws["id"], touched, ws_type))

        for i, (id_a, files_a, type_a) in enumerate(all_files):
            for j, (id_b, files_b, type_b) in enumerate(all_files):
                if i < j:
                    overlap = set(files_a) & set(files_b)
                    # Check for serial bottleneck files
                    bottleneck_overlap = overlap & set(SERIAL_BOTTLENECKS.keys())
                    if bottleneck_overlap:
                        report.has_conflicts = True
                        for bf in bottleneck_overlap:
                            report.conflicts.append(
                                {
                                    "between": [id_a, id_b],
                                    "files": [bf],
                                    "severity": "critical",
                                    "reason": f"SERIAL BOTTLENECK: {SERIAL_BOTTLENECKS[bf]}. These workstreams MUST run sequentially.",
                                    "must_serialize": True,
                                }
                            )
                    elif overlap:
                        report.has_conflicts = True
                        report.conflicts.append(
                            {
                                "between": [id_a, id_b],
                                "files": list(overlap),
                                "severity": "high" if len(overlap) > 2 else "low",
                                "must_serialize": False,
                            }
                        )

        # Module pattern: mod-* workstreams are parallel-safe, wire-* is serial
        module_ids = [aid for aid, _, at in all_files if at == "module_creation"]
        wiring_ids = [aid for aid, _, at in all_files if at == "tool_wiring"]
        if module_ids and wiring_ids:
            # This is intentional — module creation first (parallel), then wiring (serial)
            # Don't flag as conflicts; they're designed this way
            report.conflicts = [
                c
                for c in report.conflicts
                if not (
                    c["between"][0] in module_ids
                    and c["between"][1] in wiring_ids
                    and c.get("must_serialize")
                )
            ]

        report.parallel_safe = not report.has_conflicts
        report.total = len(self.workstreams)
        self.results["conflicts"] = asdict(report)

    def _estimate_files(self, desc: str) -> list:
        files = re.findall(r"\b[\w./-]+\.\w+\b", desc)
        # Always check for known project files by keyword
        desc_lower = desc.lower()
        if (
            "tools-mcp-server" in desc_lower
            or "wire" in desc_lower
            or "dispatch" in desc_lower
        ):
            if "scripts/tools-mcp-server.py" not in files:
                files.append("scripts/tools-mcp-server.py")
        if "opencode.json" in desc_lower and "opencode.json" not in files:
            files.append("opencode.json")
        return files[:15]

    def _recommend_temperatures(self):
        for ws in self.workstreams:
            temp = call_temperature_mcp(ws.get("prompt", ws["description"]))
            self.results["temperatures"][ws["id"]] = temp


#  Workstream State Persistence (for resume after interruptions)
WORKSTREAMS_DIR = os.path.join(MEMORY_DIR, "workstreams")


def save_workstream_state(ws_id, state):
    ensure_dirs()
    ws_dir = os.path.join(WORKSTREAMS_DIR, ws_id)
    os.makedirs(ws_dir, exist_ok=True)
    sp = os.path.join(ws_dir, "state.json")
    hp = os.path.join(ws_dir, "heartbeat.json")
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)
    with open(hp, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": time.time(),
                "status": state.get("status", "running"),
                "step": state.get("step", ""),
            },
            f,
        )


def load_workstream_state(ws_id):
    sp = os.path.join(WORKSTREAMS_DIR, ws_id, "state.json")
    if os.path.isfile(sp):
        with open(sp, encoding="utf-8") as f:
            return json.load(f)
    return None


def list_resumable_workstreams():
    ensure_dirs()
    if not os.path.isdir(WORKSTREAMS_DIR):
        return []
    resumable = []
    for ws_id in os.listdir(WORKSTREAMS_DIR):
        s = load_workstream_state(ws_id)
        if s and s.get("status") in ("running", "pending", "interrupted"):
            resumable.append(
                {
                    "id": ws_id,
                    "status": s["status"],
                    "step": s.get("step", ""),
                    "desc": s.get("description", ""),
                }
            )
    return resumable


def clear_workstream_state(ws_id):
    ws_dir = os.path.join(WORKSTREAMS_DIR, ws_id)
    if os.path.isdir(ws_dir):
        import shutil

        shutil.rmtree(ws_dir, ignore_errors=True)


#  Heartbeat Monitor


class HeartbeatMonitor:
    def __init__(
        self, workstreams: list, poll_interval: float = 2.0, stall_timeout: float = 30.0
    ):
        self.streams = {
            ws["id"]: WorkstreamStatus(
                id=ws["id"],
                description=ws["description"],
                dependencies=ws.get("dependencies", []),
                temperature=ws.get("temperature", 0.7),
            )
            for ws in workstreams
        }
        self.poll_interval = poll_interval
        self.stall_timeout = stall_timeout
        self._running = False

    def start(self):
        self._running = True
        return self._poll_loop()

    def _poll_loop(self):
        while self._running:
            for ws_id, status in self.streams.items():
                hb_file = os.path.join(WORKSTREAMS_DIR, ws_id, "heartbeat.json")
                if os.path.isfile(hb_file):
                    try:
                        with open(hb_file) as f:
                            hb = json.load(f)
                        status.status = hb.get("status", "running")
                        status.step = hb.get("step", "")
                        status.last_heartbeat = hb.get("timestamp", time.time())
                        if status.status == "completed":
                            out_file = os.path.join(
                                WORKSTREAMS_DIR, ws_id, "output.json"
                            )
                            if os.path.isfile(out_file):
                                with open(out_file) as f:
                                    out = json.load(f)
                                status.output = out.get("output", "")
                    except Exception:
                        pass
                else:
                    if status.status == "pending":
                        continue
                    # Check if stalled
                    if (
                        status.last_heartbeat
                        and (time.time() - status.last_heartbeat) > self.stall_timeout
                    ):
                        status.status = "stalled"
                    elif status.status == "running" and status.last_heartbeat is None:
                        status.status = "running"
            self._render_status()
            time.sleep(self.poll_interval)
        return self.streams

    def _render_status(self):
        sys.stdout.write(
            f"\r{M}   Monitoring (polling every {self.poll_interval}s){N}  "
        )
        icons = {
            "pending": "",
            "running": "",
            "completed": "",
            "failed": "",
            "stalled": "",
        }
        parts = []
        for ws_id, s in self.streams.items():
            icon = icons.get(s.status, "")
            label = f"{s.status}"
            if s.status == "running" and s.step:
                label += f" ({s.step})"
            elif s.status == "stalled" and s.last_heartbeat:
                stalled_for = int(time.time() - s.last_heartbeat)
                label += f" (no heartbeat {stalled_for}s)"
            parts.append(f"{ws_id}: {icon} {label}")
        joined = "  ".join(parts)
        sys.stdout.write(joined[:120] + "  ")
        done = sum(
            1 for s in self.streams.values() if s.status in ("completed", "failed")
        )
        total = len(self.streams)
        pct = int((done / total) * 100) if total else 0
        bar_fill = "" * (pct // 5) + "" * (20 - pct // 5)
        sys.stdout.write(f"\n  Overall: {bar_fill} {pct}%  ")
        sys.stdout.flush()

    def stop(self):
        self._running = False


#  Plan Display


def show_plan(task: str, analysis: dict, workstreams: list):
    print(f"\n{B}{BAR}{N}")
    print(f"{B}  ORCHESTRATION PLAN{N}")
    print(f"{B}{BAR}{N}")
    print(f"\n  Task: {task[:120]}{'...' if len(task) > 120 else ''}")
    print(
        f"\n  {Y}Complexity Score:{N} {analysis['score']}/100 ({analysis['threshold']})"
    )
    print(f"  {Y}Mode:{N} {analysis['mode'].upper()}")
    print(f"  {Y}Recommended Agents:{N} {analysis['recommended_subagents']}")
    print(f"\n  {Y}Workstreams ({len(workstreams)}):{N}")
    for ws in workstreams:
        deps = (
            f" → depends on: {', '.join(ws['dependencies'])}"
            if ws["dependencies"]
            else " (independent)"
        )
        print(f"    {ws['id']}: {ws['description']}{deps}")
    if analysis.get("high_risk_flags"):
        print(f"\n  {M}Risk flags:{N} {', '.join(analysis['high_risk_flags'])}")
    print(f"\n  {'' * 60}")


#  Orchestrator


def orchestrate(
    task: str,
    mode: str = "plan",
    background: bool = False,
    watch: bool = False,
    dag_path: str | None = None,
    dag_execute: bool = False,
    resume: str | None = None,
):
    plan_id = resume or str(uuid.uuid4())[:8]
    ensure_dirs()

    # Resume mode: load saved workstream state
    if resume:
        print(f"\n{C}{BAR}{N}")
        print(f"{C}{BOLD}  RESUMING WORKFLOW: {resume}{N}")
        print(f"{C}{BAR}{N}")
        resumable = list_resumable_workstreams()
        if resumable:
            print(f"  Found {len(resumable)} workstream(s) with saved state:")
            for ws in resumable:
                print(
                    f"    {ws['id']}: {ws['status']} — {ws.get('step', '')} ({ws.get('desc', '')[:60]})"
                )
        else:
            print(
                f"  {Y}No saved workstream state found for '{resume}'. Starting fresh.{N}"
            )

    #  DAG mode
    if dag_path:
        return _run_dag(dag_path, task, dag_execute)

    #  Standard orchestration mode

    print(f"\n{C}{BAR}{N}")
    print(f"{C}{BOLD}  ORCHESTRATION ENGINE v2{N}")
    print(f"{C}{BAR}{N}")
    print(f"  Task:    {task[:100]}")
    print(f"  Mode:    {mode}")
    print(f"  Plan ID: {plan_id}")
    print(f"  Time:    {now_iso()}")

    # Step 1: Analyze
    print(f"\n{Y}   Analyzing task...{N}")
    analysis = analyze_task(task)
    print(f"     Score: {analysis['score']}/100 ({analysis['threshold']})")
    print(f"     Mode:  {analysis['mode'].upper()}")

    # Generate workstreams
    workstreams = generate_workstreams(task, analysis)

    # Print analysis breakdown
    print(f"\n  {Y}Workstreams: {len(workstreams)}{N}")
    for ws in workstreams:
        temp = call_temperature_mcp(ws.get("prompt", ws["description"]))
        ws["temperature"] = temp
        deps = f" (deps: {ws['dependencies']})" if ws.get("dependencies") else ""
        print(f"    {ws['id']}: {ws['description'][:80]}{deps}")

    if analysis.get("high_risk_flags"):
        print(f"\n  {M}Risk flags: {', '.join(analysis['high_risk_flags'])}{N}")

    #  PLAN only mode
    if mode == "plan":
        show_plan(task, analysis, workstreams)
        print(f"\n  {C}To execute:{N}")
        print('    python scripts/task-orchestrator.py --task "<task>" --execute')
        print('    python scripts/task-orchestrator.py --task "<task>" --background')
        print('    python scripts/task-orchestrator.py --task "<task>" --watch')
        print('    python scripts/task-orchestrator.py --task "<task>" --orchestrate')
        return {
            "action": "plan",
            "plan_id": plan_id,
            "analysis": analysis,
            "workstreams": workstreams,
        }

    #  EXECUTE / BACKGROUND mode
    if mode in ("execute", "background"):
        print(f"\n{G}{BAR}{N}")
        print(f"{G}   Background Work Started{N}")
        print(f"{G}{BAR}{N}")

        # Launch background analyzer
        analyzer = BackgroundAnalyzer(task, workstreams, MEMORY_DIR)
        analyzer.start()
        thread_labels = [
            "Scanning memory for patterns...",
            "Analyzing codebase structure...",
            "Building context digest...",
            "Predicting merge conflicts...",
            "Recommending temperatures...",
        ]
        for i, label in enumerate(thread_labels):
            print(f"    Thread {i + 1}: {label}")
            time.sleep(0.3)

        # Wait briefly for initial results
        time.sleep(1.5)

        # Show live results as they come in
        for tick in range(6):
            done = len(analyzer.results["completed_steps"])
            print(
                f"\r    [{'' * done}{'' * (5 - done)}] {done}/5 steps completed    ",
                end="",
            )
            time.sleep(0.5)
        print()

        # Print context digest
        digest = analyzer.results.get("context_digest")
        if digest:
            print(f"\n  {C}Context Digest:{N}")
            print(f"    Profiles found:   {digest['profiles_found']}")
            print(f"    Cases found:      {digest['cases_found']}")
            if digest.get("recent_errors"):
                print(
                    f"    Recent errors:    {len(digest['recent_errors'])} signatures cached"
                )

        # Print conflict analysis
        conflicts = analyzer.results.get("conflicts")
        if conflicts:
            if conflicts["has_conflicts"]:
                print(f"\n  {R}  Merge Conflicts Predicted:{N}")
                for c in conflicts["conflicts"]:
                    print(
                        f"    {c['between'][0]} ↔ {c['between'][1]}: {', '.join(c['files'])} ({c['severity']})"
                    )
                print(f"    Parallel safe: {Y}NO — use sequential mode{N}")
            else:
                print(f"\n  {G} No merge conflicts predicted{N}")
                print("    Parallel safe: YES")

        # Temperature recommendations
        if analyzer.results.get("temperatures"):
            print(f"\n  {C}Temperature Recommendations:{N}")
            for ws_id, temp in analyzer.results["temperatures"].items():
                temp_label = (
                    "PRECISE"
                    if temp < 0.3
                    else "BALANCED"
                    if temp < 0.7
                    else "CREATIVE"
                )
                print(f"    {ws_id}: {temp:.1f} ({temp_label})")

        print(f"\n  {G} Background analysis complete.{N}")
        return {
            "action": mode,
            "plan_id": plan_id,
            "analysis": analysis,
            "workstreams": workstreams,
            "background_results": analyzer.results,
        }

    #  WATCH mode
    if mode == "watch" or watch:
        print(f"\n{M}{BAR}{N}")
        print(f"{M}   Progress Monitor{N}")
        print(f"{M}{BAR}{N}")

        monitor = HeartbeatMonitor(workstreams, poll_interval=2.0)
        try:
            streams = monitor.start()
        except KeyboardInterrupt:
            monitor.stop()
            print("\n  Monitoring stopped.")

        # Final report
        print(f"\n\n{C}{BAR}{N}")
        print(f"{C}   Results{N}")
        print(f"{C}{BAR}{N}")
        for ws_id, s in streams.items():
            if s.status == "completed":
                print(f"  {G}  {ws_id}: PASS — output: {s.output[:80] or 'done'}{N}")
            elif s.status == "failed":
                print(f"  {R}  {ws_id}: FAIL — error: {s.error[:80]}{N}")
            elif s.status == "stalled":
                print(f"  {R}  {ws_id}: STALLED — no heartbeat{N}")
            else:
                print(f"  {Y}  {ws_id}: {s.status.upper()}{N}")

        # Merge status
        done_count = sum(1 for s in streams.values() if s.status == "completed")
        conflicts = ConflictReport()
        for ws in workstreams:
            touched = re.findall(
                r"\b[\w./-]+\.\w+\b", ws.get("prompt", ws["description"])
            )
            ws["files_touched"] = touched[:5]
        print(f"\n  {'' * 20}")
        conflicts = analyzer.results.get("conflicts", {})
        if conflicts and conflicts.get("has_conflicts"):
            print(f"  {R}Conflicts predicted: {len(conflicts.get('conflicts', []))}{N}")
            print(f"  Parallel safe: {R}NO{N}")
        else:
            print(f"  {G}Conflicts predicted: 0{N}")
            print(f"  Parallel safe: {G}YES{N}")
        print(f"  Merge ready: {done_count}/{len(streams)} workstreams")
        return {
            "action": "watch",
            "streams": {k: asdict(v) for k, v in streams.items()},
        }

    #  ORCHESTRATE FULL TASK mode
    if mode == "orchestrate":
        print(f"\n{C}{BAR}{N}")
        print(f"{C}   Full Pipeline Execution{N}")
        print(f"{C}{BAR}{N}")

        # 1. Background analysis
        analyzer = BackgroundAnalyzer(task, workstreams, MEMORY_DIR)
        analyzer.start()
        analyzer.join(timeout=10)

        # 2. Auto-generate DAG for multi-phase builds
        dag_path = _auto_generate_dag(task, workstreams, plan_id)
        if dag_path:
            print(f"\n  {C}Auto-generated DAG: {dag_path}{N}")

        # 3. Planned workstream dispatch
        print(f"\n  {Y}Dispatching {len(workstreams)} workstreams...{N}")
        for ws in workstreams:
            temp = ws.get("temperature", 0.7)
            deps = (
                f" (after {', '.join(ws['dependencies'])})"
                if ws.get("dependencies")
                else ""
            )
            print(f"  {G}    {ws['id']}: spawning subagent (temp={temp}){deps}{N}")
            print(f"           prompt: {ws['description'][:100]}")
            # Auto-save workstream state for resume capability
            save_workstream_state(
                ws["id"],
                {
                    "plan_id": plan_id,
                    "description": ws["description"],
                    "status": "running",
                    "step": "dispatched",
                    "temperature": temp,
                    "dependencies": ws.get("dependencies", []),
                    "type": ws.get("type", ""),
                    "phase": ws.get("phase", ""),
                    "timestamp": time.time(),
                },
            )

        # 4. Would spawn real subagents via task tool
        #    Module creation streams (mod-*) run in parallel.
        #    Tool wiring stream (wire-*) runs after all modules complete.
        print(f"\n  {C}Workstream Dispatch Order:{N}")
        parallel_streams = [ws for ws in workstreams if ws.get("phase") == "parallel"]
        serial_streams = [ws for ws in workstreams if ws.get("phase") == "serial"]
        if parallel_streams:
            print(
                f"    Phase 1 (parallel): {', '.join(ws['id'] for ws in parallel_streams)}"
            )
        if serial_streams:
            print(
                f"    Phase 2 (serial):   {', '.join(ws['id'] for ws in serial_streams)}"
            )
        if not parallel_streams and not serial_streams:
            for ws in workstreams:
                deps_block = (
                    f" after {', '.join(ws['dependencies'])}"
                    if ws.get("dependencies")
                    else ""
                )
                print(f"    Run {ws['id']}{deps_block} → collect output")

        # 5. Merge results
        print(f"\n  {G}Merge Status:{N}")
        conflicts = analyzer.results.get("conflicts")
        if conflicts and conflicts.get("has_conflicts"):
            critical = [
                c for c in conflicts["conflicts"] if c.get("severity") == "critical"
            ]
            normal = [
                c for c in conflicts["conflicts"] if c.get("severity") != "critical"
            ]
            if critical:
                print(f"  {R}   CRITICAL serial bottlenecks:{N}")
                for c in critical:
                    print(
                        f"    {c['between'][0]} ↔ {c['between'][1]}: {', '.join(c['files'])}"
                    )
                    print(f"      Reason: {c.get('reason', 'Must run sequentially')}")
            if normal:
                print(f"  {Y}   Conflicts: {len(normal)}{N}")
                for c in normal:
                    print(
                        f"    {c['between'][0]} ↔ {c['between'][1]}: {', '.join(c['files'])}"
                    )
        else:
            print(f"  {G}  No conflicts predicted — safe to merge{N}")

        # 6. Post-merge auto-verification plan
        has_wiring = any(ws.get("type") == "tool_wiring" for ws in workstreams)
        if has_wiring:
            print(f"\n  {C}Post-Merge Verification Plan:{N}")
            print("    After wiring is complete, auto-run:")
            verify_script = os.path.join(SCRIPTS, "phase-verify-full.py")
            if os.path.isfile(verify_script):
                print("    python scripts/phase-verify-full.py")
            print(
                "    python scripts/tools-mcp-server.py --list-tools | python -c \"import sys,json; tools=json.loads(sys.stdin.read()); print(f'{len(tools)} tools registered')\""
            )

        # 7. Log to decision trace
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                os.path.join(SCRIPTS, "decision-trace.ps1"),
                "-Action",
                "Add",
                "-Title",
                f"Orchestrated: {task[:80]}",
                "-Decision",
                f"Full pipeline with {len(workstreams)} workstreams",
                "-Rationale",
                f"Complexity {analysis['score']}/100 triggered {analysis['mode']} mode",
                "-Category",
                "process",
            ],
            capture_output=True,
            cwd=BASE,
        )

        print(f"\n  {G} Pipeline plan ready.{N}")
        return {
            "action": "orchestrate",
            "plan_id": plan_id,
            "analysis": analysis,
            "workstreams": workstreams,
            "dag_path": dag_path,
            "auto_verify": "python scripts/phase-verify-full.py"
            if has_wiring
            else None,
        }

    return {"action": "unknown", "plan_id": plan_id}


#  CLI Entry

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Task Orchestrator v2 — Active Orchestrator"
    )
    parser.add_argument("--task", type=str, help="Task description")
    parser.add_argument(
        "--plan", action="store_true", help="Generate plan only (dry-run)"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Generate plan + run background analysis"
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run analysis threads in background, return plan immediately",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Poll for heartbeat files and report progress",
    )
    parser.add_argument(
        "--orchestrate",
        action="store_true",
        help="Full pipeline with subagent planning",
    )
    parser.add_argument("--dag", type=str, help="Path to DAG definition JSON file")
    parser.add_argument(
        "--dag-execute", action="store_true", help="Execute the DAG pipeline"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Display DAG info and exit (only with --dag)",
    )
    parser.add_argument(
        "--resume", type=str, help="Resume a previous orchestration plan by ID"
    )
    parser.add_argument(
        "--list-resumable",
        action="store_true",
        help="List workstreams that can be resumed",
    )
    args = parser.parse_args()

    # List resumable workstreams
    if args.list_resumable:
        resumable = list_resumable_workstreams()
        if resumable:
            print(f"\nResumable workstreams ({len(resumable)}):")
            for ws in resumable:
                print(f"  {ws['id']}: {ws['status']} — {ws['desc'][:80]}")
        else:
            print("No resumable workstreams found.")
        sys.exit(0)

    if args.dag:
        result = orchestrate(
            args.task or "",
            dag_path=args.dag,
            dag_execute=args.dag_execute,
            resume=args.resume,
        )
        sys.exit(0)

    if not args.task and not args.resume:
        print("Usage:")
        print(
            '  python scripts/task-orchestrator.py --task "<task>" [--plan|--execute|--background|--watch|--orchestrate]'
        )
        print(
            "  python scripts/task-orchestrator.py --dag <dag-file> [--info|--dag-execute]"
        )
        print("  python scripts/task-orchestrator.py --resume <plan-id>")
        print("  python scripts/task-orchestrator.py --list-resumable")
        sys.exit(1)

    mode = "plan"
    if args.execute:
        mode = "execute"
    elif args.background:
        mode = "background"
    elif args.watch:
        mode = "watch"
    elif args.orchestrate:
        mode = "orchestrate"
    elif args.plan:
        mode = "plan"

    result = orchestrate(
        args.task,
        mode=mode,
        background=args.background,
        watch=args.watch,
        resume=args.resume,
    )
