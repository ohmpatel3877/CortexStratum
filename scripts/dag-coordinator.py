#!/usr/bin/env python3
"""
DAG Coordinator — topological execution engine for multi-agent pipelines.

Reads a DAG definition JSON, performs topological sort (Kahn's algorithm),
creates state files per node, monitors heartbeat files, passes upstream
outputs as downstream inputs, handles conditional branching and fan-in
merge, and logs execution traces.

Usage:
    python scripts/dag-coordinator.py --dag data/dag-definitions/research-implement-verify.json
    python scripts/dag-coordinator.py --dag data/dag-definitions/research-implement-verify.json --dry-run
    python scripts/dag-coordinator.py --dag data/dag-definitions/research-implement-verify.json --resume
"""

import json, sys, os, time, copy, threading, math, re as _re
from datetime import datetime, timezone
from collections import deque
from typing import Optional, Any

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS = os.path.join(PROJECT_ROOT, "scripts")
DATA = os.path.join(PROJECT_ROOT, "data")
DAG_DEF_DIR = os.path.join(DATA, "dag-definitions")
DAG_TRACE_DIR = os.path.join(DATA, "dag-traces")

G = "\033[92m"; Y = "\033[93m"; B = "\033[94m"; M = "\033[95m"
R = "\033[91m"; C = "\033[96m"; N = "\033[0m"; BOLD = "\033[1m"
BAR = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

_state_manager = None


def get_state_manager(dag_id: str):
    global _state_manager
    if _state_manager is None or _state_manager.dag_id != dag_id:
        from state_file_manager import DAGStateManager as DSM
        _state_manager = DSM(dag_id)
    return _state_manager


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs():
    for d in [DAG_DEF_DIR, DAG_TRACE_DIR]:
        os.makedirs(d, exist_ok=True)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp, path)


# ── DAG Definition Loader ──────────────────────────────────

def load_dag_definition(path: str) -> dict:
    dag = load_json(path)
    required = ["dag_id", "name", "description", "nodes", "edges"]
    for field in required:
        if field not in dag:
            raise ValueError(f"DAG definition missing required field: {field}")
    if not isinstance(dag["nodes"], list) or len(dag["nodes"]) == 0:
        raise ValueError("DAG must have at least one node")
    node_ids = {n["id"] for n in dag["nodes"]}
    for edge in dag.get("edges", []):
        if edge["from"] not in node_ids:
            raise ValueError(f"Edge from '{edge['from']}' references unknown node")
        if edge["to"] not in node_ids:
            raise ValueError(f"Edge to '{edge['to']}' references unknown node")
    dag.setdefault("version", "1.0.0")
    dag.setdefault("tags", [])
    dag.setdefault("merge_rules", [])
    dag.setdefault("config", {})
    return dag


# ── Topological Sort (Kahn's Algorithm) ────────────────────

def topological_sort(dag: dict) -> list[list[str]]:
    nodes = {n["id"]: n for n in dag["nodes"]}
    in_degree = {nid: 0 for nid in nodes}
    adjacency = {nid: [] for nid in nodes}
    for edge in dag.get("edges", []):
        adjacency[edge["from"]].append(edge["to"])
        in_degree[edge["to"]] += 1
    queue = deque()
    for nid, deg in in_degree.items():
        if deg == 0:
            queue.append(nid)
    levels = []
    visited = set()
    while queue:
        level = []
        for _ in range(len(queue)):
            nid = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            level.append(nid)
        if level:
            levels.append(level)
        for nid in level:
            for neighbor in adjacency[nid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
    all_nodes = set(nodes.keys())
    if visited != all_nodes:
        raise ValueError(f"Cycle detected. Unreachable: {all_nodes - visited}")
    return levels


def get_dependents(dag: dict) -> dict[str, list[str]]:
    deps = {n["id"]: [] for n in dag["nodes"]}
    for edge in dag.get("edges", []):
        deps[edge["to"]].append(edge["from"])
    return deps


# ── Condition Evaluation ───────────────────────────────────

def _evaluate_condition(condition: str, state: dict) -> bool:
    if not condition:
        return True
    m = _re.match(r'^\$\.(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)$', condition.strip())
    if not m:
        return True
    path = m.group(1)
    op = m.group(2)
    raw_val = m.group(3).strip()
    parts = path.split(".")
    val = state
    try:
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, None)
            elif isinstance(val, list) and p.isdigit():
                val = val[int(p)]
            else:
                val = None; break
    except (IndexError, TypeError, ValueError):
        val = None
    if val is None:
        return False
    try:
        cmp_val = int(raw_val)
    except ValueError:
        try:
            cmp_val = float(raw_val)
        except ValueError:
            cmp_val = raw_val.strip("\"'")
    if op == "==": return val == cmp_val
    if op == "!=": return val != cmp_val
    if isinstance(val, (int, float)) and isinstance(cmp_val, (int, float)):
        if op == ">": return val > cmp_val
        if op == "<": return val < cmp_val
        if op == ">=": return val >= cmp_val
        if op == "<=": return val <= cmp_val
    return False


# ── Input Builder ──────────────────────────────────────────

def _build_node_input(nid, node_def, upstream_outputs, root_input):
    input_data = {
        "task": node_def.get("prompt_template", node_def["description"]),
        "context": dict(root_input.get("context", {})),
        "artifacts": [],
    }
    mapping = node_def.get("input_mapping", {})
    for target, source in mapping.items():
        parts = source.split(".")
        if len(parts) >= 3:
            src_node = parts[0]
            val = upstream_outputs.get(src_node, {})
            for p in parts[1:]:
                if isinstance(val, dict):
                    val = val.get(p, None)
                else:
                    val = None; break
            if val is not None:
                _set_nested(input_data, target, val)
    for dep_id, dep_out in upstream_outputs.items():
        input_data.setdefault("parent", {})[dep_id] = {"output": dep_out}
        artifacts = dep_out.get("artifacts", [])
        if artifacts:
            input_data["artifacts"].extend(artifacts)
    input_data["task"] = _substitute_template(input_data["task"], input_data)
    return input_data


def _set_nested(d, path, val):
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur:
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = val


def _substitute_template(template, context):
    def _resolver(m):
        path = m.group(1).strip()
        parts = path.split(".")
        val = context
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, m.group(0))
            else:
                return m.group(0)
        if not isinstance(val, str):
            val = json.dumps(val)
        return val
    return _re.sub(r'\{\{(.+?)\}\}', _resolver, template)


# ── Simulated Node Execution ───────────────────────────────

def _simulate_node_execution(nid, node_def, input_data, timeout_s):
    import random as _random
    sim_duration = min(0.5 + _random.random() * 1.0, timeout_s * 0.5)
    time.sleep(sim_duration)
    expected = node_def.get("expected_outputs", [])
    output = {"summary": f"Completed: {input_data.get('task', node_def['description'])[:80]}",
              "data": {}, "artifacts": [], "files_changed": [], "decisions": []}
    for exp in expected:
        output["data"][exp] = f"<{exp}_result>"
    return {"success": True, "output": output, "errors": []}


# ── Pipeline Execution ─────────────────────────────────────

def execute_pipeline(dag, dry_run=False, resume=False, task_input=None):
    dag_id = dag["dag_id"]
    nodes_map = {n["id"]: n for n in dag["nodes"]}
    levels = topological_sort(dag)
    dependents_map = get_dependents(dag)

    trace = {"dag_id": dag_id, "name": dag["name"], "started_at": now_iso(),
             "completed_at": None, "node_count": len(dag["nodes"]),
             "edge_count": len(dag.get("edges", [])),
             "levels": [[n for n in lvl] for lvl in levels],
             "status": "running", "summary": {}}

    print(f"\n{B}{BAR}{N}")
    print(f"{B}{BOLD}  DAG PIPELINE: {dag['name']}{N}")
    print(f"{B}{BAR}{N}")
    print(f"  DAG ID:    {dag_id}")
    print(f"  Nodes:     {len(dag['nodes'])}")
    print(f"  Edges:     {len(dag.get('edges', []))}")
    print(f"  Levels:    {len(levels)}")
    for i, level in enumerate(levels):
        print(f"    Level {i+1}: {', '.join(level)}")
    print()

    if dry_run:
        print(f"{Y}  [DRY RUN] Plan displayed. No execution.{N}")
        trace["status"] = "dry_run"
        trace["completed_at"] = now_iso()
        return trace

    mgr = get_state_manager(dag_id)
    if not resume:
        mgr.clear_states()

    root_input = task_input or {}
    for node in dag["nodes"]:
        nid = node["id"]
        if resume and mgr.get_phase(nid) == "completed":
            print(f"  {Y}↻ Resume: {nid} already completed{N}")
            continue
        mgr.init_node_state(nid, {"task": node.get("prompt_template", node["description"]),
                                   "context": dict(root_input)}, node.get("temperature", 0.7))

    completed_nodes = 0
    failed_nodes = []
    error_mode = dag.get("config", {}).get("error_mode", "abort")
    global_timeout = dag.get("config", {}).get("global_timeout_seconds", 3600)
    start_wall = time.time()

    for level_idx, level in enumerate(levels):
        if error_mode == "abort" and failed_nodes:
            print(f"\n{R}  ⛔ Aborted due to failures{N}")
            break
        if time.time() - start_wall > global_timeout:
            print(f"\n{R}  ⏰ Timeout ({global_timeout}s){N}")
            trace["status"] = "timeout"
            break

        print(f"\n{C}  {'─'*60}{N}")
        print(f"{C}{BOLD}  Level {level_idx+1}/{len(levels)}: {', '.join(level)}{N}")
        print(f"{C}  {'─'*60}{N}")

        for nid in level:
            if error_mode == "abort" and failed_nodes:
                break
            if time.time() - start_wall > global_timeout:
                trace["status"] = "timeout"
                break

            node_def = nodes_map[nid]
            temp = node_def.get("temperature", 0.7)
            timeout_s = node_def.get("timeout_seconds", 300)
            deps = dependents_map.get(nid, [])
            upstream_outputs = {}
            skip_node = False

            for dep_id in deps:
                dep_state = mgr.read_state(dep_id)
                if dep_state is None:
                    print(f"  {R}  ✗ {nid}: missing dep {dep_id}{N}")
                    mgr.mark_failed(nid, [{"type": "missing_dependency",
                                            "message": f"Dependency {dep_id} has no state"}])
                    failed_nodes.append(nid); skip_node = True; break
                dep_phase = dep_state.get("phase", "unknown")
                for edge in dag.get("edges", []):
                    if edge["from"] == dep_id and edge["to"] == nid and edge.get("condition"):
                        if not _evaluate_condition(edge["condition"], dep_state):
                            print(f"  {Y}  ⏭ {nid}: condition not met{N}")
                            mgr.mark_skipped(nid, f"Condition {edge['condition']} not met")
                            skip_node = True; break
                if skip_node:
                    break
                if dep_phase == "failed":
                    if error_mode == "skip_downstream":
                        mgr.mark_skipped(nid, f"Upstream {dep_id} failed")
                        skip_node = True; break
                    elif error_mode == "abort":
                        failed_nodes.append(nid); skip_node = True; break
                upstream_outputs[dep_id] = dep_state.get("output", {})

            if skip_node:
                continue

            merged_input = _build_node_input(nid, node_def, upstream_outputs, root_input)
            mgr.write_state(nid, {**mgr.read_state(nid), "input": merged_input})
            mgr.mark_running(nid)

            node_start = time.time()
            node_result = _simulate_node_execution(nid, node_def, merged_input, timeout_s)
            elapsed_ms = (time.time() - node_start) * 1000

            if node_result["success"]:
                mgr.mark_completed(nid, node_result["output"], elapsed_ms)
                completed_nodes += 1
            else:
                mgr.mark_failed(nid, node_result.get("errors", []), elapsed_ms)
                failed_nodes.append(nid)

    wall_elapsed = time.time() - start_wall
    all_states = mgr.list_states()
    phase_counts = {}
    for s in all_states:
        p = s.get("phase", "unknown")
        phase_counts[p] = phase_counts.get(p, 0) + 1

    final_status = "failed" if failed_nodes else ("timeout" if trace["status"] == "timeout" else "completed")
    trace["completed_at"] = now_iso()
    trace["status"] = final_status
    trace["summary"] = {"total_nodes": len(all_states), "phases": phase_counts,
                        "failed_nodes": failed_nodes, "duration_seconds": round(wall_elapsed, 1)}

    trace_path = os.path.join(DAG_TRACE_DIR, f"{dag_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    write_json(trace_path, trace)

    print(f"\n{B}{BAR}{N}")
    print(f"{B}{BOLD}  PIPELINE COMPLETE{N}")
    print(f"{B}{BAR}{N}")
    print(f"  Duration: {wall_elapsed:.1f}s")
    print(f"  Status:   {final_status}")
    print(f"  Nodes:    {len(all_states)} total -> {dict(phase_counts)}")
    print(f"  Trace:    {trace_path}\n")
    return trace


# ── DAG Info Display ───────────────────────────────────────

def show_dag_info(dag):
    levels = topological_sort(dag)
    deps = get_dependents(dag)
    print(f"\n{B}{BAR}{N}")
    print(f"{B}{BOLD}  DAG: {dag['name']}{N}")
    print(f"{B}{BAR}{N}")
    print(f"  ID:          {dag['dag_id']}")
    print(f"  Description: {dag['description']}")
    print(f"  Version:     {dag.get('version', '1.0.0')}")
    print(f"  Tags:        {', '.join(dag.get('tags', [])) or 'none'}")
    print(f"  Nodes:       {len(dag['nodes'])}")
    print(f"  Edges:       {len(dag.get('edges', []))}")
    print(f"  Levels:      {len(levels)}")
    print()
    for node in dag["nodes"]:
        nid = node["id"]
        upstream = deps.get(nid, [])
        print(f"  {B}Node: {nid}{N}")
        print(f"    Desc:  {node['description']}")
        print(f"    Temp:  {node.get('temperature', 0.7)}")
        if upstream:
            print(f"    Deps:  {', '.join(upstream)}")
        print()
    print(f"  Execution order:")
    for i, lvl in enumerate(levels):
        print(f"    Level {i+1}: {', '.join(lvl)}")
    config = dag.get("config", {})
    if config:
        print(f"\n  Config: {json.dumps(config, indent=4)}")
    print()


# ── Main ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DAG Coordinator")
    parser.add_argument("--dag", type=str, help="Path to DAG definition JSON")
    parser.add_argument("--info", action="store_true", help="Show DAG info and exit")
    parser.add_argument("--dry-run", action="store_true", help="Validate + print plan, no execution")
    parser.add_argument("--resume", action="store_true", help="Skip already-completed nodes")
    parser.add_argument("--task", type=str, help="Task input JSON string")
    args = parser.parse_args()

    if not args.dag:
        ensure_dirs()
        print(f"\n{C}Available DAGs:{N}")
        for fname in sorted(os.listdir(DAG_DEF_DIR)):
            if fname.endswith(".json"):
                fpath = os.path.join(DAG_DEF_DIR, fname)
                try:
                    d = load_json(fpath)
                    print(f"  {fname}  ({d.get('dag_id','?')})  {d.get('name','?')}  [{len(d.get('nodes',[]))} nodes]")
                except Exception as e:
                    print(f"  {fname}  (error: {e})")
        print()
        sys.exit(1)

    ensure_dirs()
    dag = load_dag_definition(args.dag)
    if args.info:
        show_dag_info(dag)
        sys.exit(0)

    task_input = None
    if args.task:
        try:
            task_input = json.loads(args.task)
        except json.JSONDecodeError:
            task_input = {"context": {"description": args.task}}

    execute_pipeline(dag, dry_run=args.dry_run, resume=args.resume, task_input=task_input)
