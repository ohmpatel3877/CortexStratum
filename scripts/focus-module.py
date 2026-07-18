#!/usr/bin/env python3
"""
adhd-module.py — Cognitive Focus / Scope Management Engine for AI agents.

Detects scope creep, generates redirect nudges, stores global out-of-scope tasks,
enforces /help → work → /end session pipeline, decomposes complex prompts,
prioritizes tasks, and learns from session behavior.

Registered as MCP tools via tools-mcp-server.py. Pattern B — module dispatch.

Architecture:
  Pure handler pattern, dict in → dict out, stdlib only.
  Data stored in data/ subdirectory as JSON.
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils import load_json, save_json

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

_GLOBAL_MEMORY_PATH = DATA_DIR / "global-projects-memory.json"
_PIPELINE_PATH = DATA_DIR / "session-pipeline.json"
_LEARNING_PATH = DATA_DIR / "session-learning.json"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Known project names (extendable)
# ---------------------------------------------------------------------------

KNOWN_PROJECTS = [
    "CortexStratum", "skills", "studyspace", "StudySpace",
    "wshobson-agents", "opencode", "agent-memory-mcp",
    "compose-repo", "vibecode-projects",
]


# ===================================================================
# Component 1: Scope Detector
# ===================================================================

def check_scope(input_text, current_project="CortexStratum"):
    """
    Analyze user input and classify scope status.

    Detects:
    - Topic switching (mentions of different project names)
    - Feature bloat (lists of unrelated features)
    - Cross-project references
    - Goal drift (start vs end mentions)

    Returns dict with classification, details, and nudge recommendation.
    """
    lines = input_text.strip().split("\n")
    words = input_text.lower().split()

    mentioned_projects = []
    features_requested = []
    bullets = 0
    numbered = 0

    for proj in KNOWN_PROJECTS:
        if proj.lower() in input_text.lower() and proj.lower() != current_project.lower():
            mentioned_projects.append(proj)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("• "):
            bullets += 1
            features_requested.append(stripped.lstrip("- *• "))
        elif re.match(r"^\d+[\.\)]\s", stripped):
            numbered += 1
            features_requested.append(re.sub(r"^\d+[\.\)]\s", "", stripped))

    detect_keywords = ["also", "and also", "additionally", "another thing", "while you're at it",
                       "separately", "on a different note", "by the way"]
    drift_signals = sum(1 for kw in detect_keywords if kw in input_text.lower())

    feature_count = bullets + numbered
    classification = "in_scope"
    reasons = []

    if mentioned_projects:
        classification = "cross_project"
        reasons.append(f"References other project(s): {', '.join(mentioned_projects)}")

    if feature_count >= 5:
        classification = "bloated" if classification == "in_scope" else classification
        reasons.append(f"Contains {feature_count} distinct feature requests")

    if drift_signals >= 2:
        if classification == "in_scope":
            classification = "scope_creep"
        reasons.append("Goal drift detected (multiple topic shifts)")

    if not reasons:
        reasons.append("Content appears focused on current project")

    return {
        "classification": classification,
        "current_project": current_project,
        "mentioned_projects": mentioned_projects,
        "feature_count": feature_count,
        "features_requested": features_requested,
        "drift_signals": drift_signals,
        "reasons": reasons,
        "overall_risk": "high" if classification in ("bloated", "cross_project") else (
            "medium" if classification == "scope_creep" else "low"
        ),
    }


# ===================================================================
# Component 2: Nudge Generator
# ===================================================================

def generate_nudge(scope_result, user_input):
    """
    Generate a gentle, context-aware redirect message based on scope analysis.

    Returns dict with message, suggested_action, and severity.
    """
    classification = scope_result.get("classification", "in_scope")
    projects = scope_result.get("mentioned_projects", [])
    feature_count = scope_result.get("feature_count", 0)

    if classification == "in_scope":
        return {
            "message": None,
            "suggested_action": "proceed",
            "severity": "none",
        }

    if classification == "cross_project":
        proj_names = ", ".join(projects)
        message = (
            f"You mentioned **{proj_names}** \u2014 that\u2019s a different project "
            f"from **{scope_result.get('current_project')}**. "
            f"Want me to save a spec to `future/` for later?"
        )
        return {
            "message": message,
            "suggested_action": "write_future_spec",
            "severity": "medium",
            "projects": projects,
            "note": "Save a markdown spec to future/ instead of building now. Build when the endpoint is real."
        }

    if classification == "bloated":
        message = (
            f"That\u2019s **{feature_count}** distinct requests in one go. "
            f"Let me break them down so we can tackle them one at a time. "
            f"Off-topic items go to `future/` as specs."
        )
        return {
            "message": message,
            "suggested_action": "decompose",
            "severity": "high",
            "feature_count": feature_count,
        }

    if classification == "scope_creep":
        message = (
            f"I notice we\u2019re drifting from the original goal. "
            f"Let me log this as a future spec so we can stay focused on what matters now."
        )
        return {
            "message": message,
            "suggested_action": "write_future_spec",
            "severity": "low",
        }

    return {
        "message": None,
        "suggested_action": "proceed",
        "severity": "none",
    }


# ===================================================================
# Component 3: Global Projects Memory
# ===================================================================

def store_global(project, task, context="", source_session=""):
    """
    Store an out-of-scope task in the cross-session global memory store.

    Returns dict with stored entry and current total count.
    """
    memory = load_json(_GLOBAL_MEMORY_PATH, {"entries": []})
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "project": project,
        "task": task,
        "context": context,
        "source_session": source_session,
        "status": "pending",
    }
    memory.setdefault("entries", []).append(entry)
    save_json(_GLOBAL_MEMORY_PATH, memory)

    return {
        "stored": entry,
        "total_entries": len(memory["entries"]),
        "message": f"Saved task to {project}'s Global Memory.",
    }


def read_global(project=None, limit=10):
    """
    Retrieve entries from the global memory store, optionally filtered by project.

    Returns dict with entries list and metadata.
    """
    memory = load_json(_GLOBAL_MEMORY_PATH, {"entries": []})
    entries = memory.get("entries", [])

    if project:
        entries = [e for e in entries if e.get("project", "").lower() == project.lower()]

    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    limited = entries[:limit]

    projects = {}
    for e in memory.get("entries", []):
        p = e.get("project", "unknown")
        projects[p] = projects.get(p, 0) + 1

    return {
        "entries": limited,
        "total_entries": len(entries),
        "total_all": len(memory.get("entries", [])),
        "projects_summary": projects,
        "limit_applied": len(entries) > limit,
    }


# ===================================================================
# Component 4: Session Pipeline
# ===================================================================

VALID_PHASES = ["help", "context", "executing", "wrapping", "learning", "end"]
VALID_TRANSITIONS = {
    "help": ["context"],
    "context": ["executing"],
    "executing": ["wrapping"],
    "wrapping": ["learning"],
    "learning": ["end"],
    "end": [],
}


def pipeline_status():
    """
    Return current pipeline phase and session statistics.

    Returns dict with current_phase, transitions, and stats.
    """
    pipeline = load_json(_PIPELINE_PATH, {"phases": [], "current_phase": None})

    current = pipeline.get("current_phase")
    phases = pipeline.get("phases", [])
    next_allowed = VALID_TRANSITIONS.get(current, VALID_TRANSITIONS.get("help", []))

    total_tools = sum(p.get("tool_count", 0) for p in phases)

    return {
        "current_phase": current or "help",
        "phase_history": phases,
        "next_allowed_phases": next_allowed,
        "total_tools_used": total_tools,
        "phase_count": len(phases),
        "is_terminal": current == "end",
    }


def advance_pipeline(next_phase, summary=""):
    """
    Advance the session pipeline to the next phase. Validates transition.

    Returns dict with result, previous_phase, new_phase, and error (if invalid).
    """
    pipeline = load_json(_PIPELINE_PATH, {"phases": [], "current_phase": None})

    current = pipeline.get("current_phase")
    next_allowed = VALID_TRANSITIONS.get(current, VALID_TRANSITIONS.get("help", []))

    if current is None:
        if next_phase != "help":
            next_allowed = ["help"]
        else:
            next_allowed = ["help"]

    if next_phase not in VALID_PHASES:
        return {"error": f"Invalid phase: {next_phase}. Valid phases: {', '.join(VALID_PHASES)}"}

    if current is not None and next_phase not in VALID_TRANSITIONS.get(current, []):
        return {
            "error": f"Cannot transition from '{current}' to '{next_phase}'. "
                     f"Allowed: {', '.join(VALID_TRANSITIONS.get(current, []))}",
            "previous_phase": current,
            "new_phase": next_phase,
        }

    entry = {
        "phase": next_phase,
        "start_time": _now_iso(),
        "summary": summary,
        "tool_count": 0,
    }

    pipeline.setdefault("phases", []).append(entry)
    pipeline["current_phase"] = next_phase
    save_json(_PIPELINE_PATH, pipeline)

    return {
        "result": "ok",
        "previous_phase": current,
        "new_phase": next_phase,
        "entry": entry,
        "total_phases": len(pipeline["phases"]),
    }


# ===================================================================
# Component 5: Prompt Decomposer
# ===================================================================

CATEGORY_KEYWORDS = {
    "code": ["write", "implement", "code", "function", "class", "script", "program", "build", "create"],
    "research": ["research", "find", "search", "investigate", "look up", "what is", "how does"],
    "design": ["design", "ui", "ux", "layout", "style", "theme", "component", "mockup"],
    "bug_fix": ["bug", "fix", "error", "crash", "broken", "not working", "issue", "fail"],
    "refactor": ["refactor", "clean", "optimize", "restructure", "rewrite", "improve"],
    "documentation": ["document", "readme", "docstring", "comment", "explain", "writeup"],
    "planning": ["plan", "strategy", "roadmap", "milestone", "goal", "architect"],
}


def decompose(prompt_text):
    """
    Break a complex prompt into atomic tasks grouped by category.

    Returns dict with tasks list, category breakdown, and complexity estimate.
    """
    lines = [l.strip() for l in prompt_text.strip().split("\n") if l.strip()]
    tasks = []
    seen = set()

    for i, line in enumerate(lines):
        text = line
        if re.match(r"^[-*•\d+\.\)]\s", text):
            text = re.sub(r"^[-*•\d+\.\)]\s*", "", text)

        if len(text) < 10:
            continue
        if text.lower() in seen:
            continue
        seen.add(text.lower())

        category = "other"
        best_score = 0
        for cat, kws in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in kws if kw in text.lower())
            if score > best_score:
                best_score = score
                category = cat

        word_count = len(text.split())
        complexity = "low"
        if word_count > 20:
            complexity = "medium"
        if word_count > 50:
            complexity = "high"

        deps = []
        dep_markers = ["after", "then", "once", "first", "prerequisite", "depends on"]
        for marker in dep_markers:
            if marker in text.lower():
                deps.append(marker)

        tasks.append({
            "id": i + 1,
            "description": text,
            "category": category,
            "complexity": complexity,
            "word_count": word_count,
            "dependencies": deps,
        })

    category_counts = {}
    for t in tasks:
        cat = t["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    overall = "low"
    avg_complexity = sum(
        1 if t["complexity"] == "low" else 2 if t["complexity"] == "medium" else 3
        for t in tasks
    ) / max(len(tasks), 1)
    if avg_complexity >= 2.5:
        overall = "high"
    elif avg_complexity >= 1.5:
        overall = "medium"

    return {
        "tasks": tasks,
        "task_count": len(tasks),
        "category_breakdown": category_counts,
        "overall_complexity": overall,
        "original_length_chars": len(prompt_text),
        "original_length_lines": len(lines),
    }


# ===================================================================
# Component 6: Task Prioritizer
# ===================================================================

CATEGORY_WEIGHTS = {
    "bug_fix": 10,
    "code": 8,
    "refactor": 7,
    "planning": 6,
    "design": 5,
    "research": 4,
    "documentation": 3,
    "other": 2,
}

URGENCY_SIGNALS = [
    "urgent", "asap", "critical", "blocker", "blocking", "deadline",
    "today", "immediately", "priority", "important",
]


def prioritize(tasks):
    """
    Score and sequence tasks for optimal execution order.

    Priority = f(complexity, dependencies, category_weight, urgency_signals).

    Returns a sorted execution plan with dependency-respecting order.
    """
    if not tasks:
        return {"plan": [], "total_tasks": 0, "message": "No tasks to prioritize."}

    scored = []
    for t in tasks:
        desc = t.get("description", "")
        category = t.get("category", "other")
        complexity = t.get("complexity", "low")

        urgency_bonus = sum(2 for sig in URGENCY_SIGNALS if sig in desc.lower())
        category_weight = CATEGORY_WEIGHTS.get(category, 2)
        complexity_penalty = {"low": 0, "medium": -2, "high": -5}.get(complexity, 0)
        word_bonus = min(len(desc.split()) // 5, 3)

        score = category_weight + urgency_bonus + complexity_penalty + word_bonus
        score = max(score, 0)

        scored.append({
            **t,
            "priority_score": score,
            "_sort_key": -score,
        })

    scored.sort(key=lambda x: x["_sort_key"])

    dep_graph = {}
    for t in scored:
        tid = t["id"]
        dep_graph[tid] = []
        for dep_marker in t.get("dependencies", []):
            for other in scored:
                if other["id"] != tid:
                    desc_lower = other.get("description", "").lower()
                    if dep_marker in desc_lower or dep_marker in other.get("dependencies", []):
                        dep_graph[tid].append(other["id"])

    sorted_tasks = _topological_sort(scored, dep_graph)

    plan = []
    for i, t in enumerate(sorted_tasks):
        plan.append({
            "order": i + 1,
            "id": t["id"],
            "description": t["description"],
            "category": t["category"],
            "complexity": t["complexity"],
            "priority_score": t["priority_score"],
            "dependencies": t.get("dependencies", []),
        })

    return {
        "plan": plan,
        "total_tasks": len(plan),
        "high_priority": len([p for p in plan if p["priority_score"] >= 10]),
        "medium_priority": len([p for p in plan if 5 <= p["priority_score"] < 10]),
        "low_priority": len([p for p in plan if p["priority_score"] < 5]),
    }


def _topological_sort(tasks, dep_graph):
    """Simple topological sort (Kahn's algorithm) on task dependency graph."""
    in_degree = {t["id"]: 0 for t in tasks}
    for tid, deps in dep_graph.items():
        in_degree[tid] = len(deps)

    queue = [t for t in tasks if in_degree[t["id"]] == 0]
    sorted_list = []

    while queue:
        queue.sort(key=lambda t: -t.get("priority_score", 0))
        node = queue.pop(0)
        sorted_list.append(node)
        for other in tasks:
            oid = other["id"]
            if oid in dep_graph and node["id"] in dep_graph[oid]:
                in_degree[oid] -= 1
                if in_degree[oid] == 0:
                    queue.append(other)

    remaining = [t for t in tasks if t not in sorted_list]
    sorted_list.extend(remaining)

    return sorted_list


# ===================================================================
# Component 7: Session Learning
# ===================================================================

def learn(session_id, events=None):
    """
    Post-session analysis. Generates insights from the session pipeline
    and stores learning in session-learning.json.

    Returns dict with insights, stats, and recommendations.
    """
    pipeline = load_json(_PIPELINE_PATH, {"phases": [], "current_phase": None})
    learning_db = load_json(_LEARNING_PATH, {"sessions": []})

    phases = pipeline.get("phases", [])
    phase_names = [p["phase"] for p in phases]

    scope_creep_events = 0
    tool_counts = []
    context_switches = 0
    session_duration = None

    if len(phases) >= 2:
        try:
            first = phases[0].get("start_time", "")
            last = phases[-1].get("start_time", "")
            if first and last:
                from datetime import datetime as dt
                f = dt.fromisoformat(first)
                l = dt.fromisoformat(last)
                session_duration = (l - f).total_seconds()
        except (ValueError, TypeError):
            pass

    for phase in phases:
        tc = phase.get("tool_count", 0)
        tool_counts.append(tc)

    global_memory = load_json(_GLOBAL_MEMORY_PATH, {"entries": []})
    project_tasks = {}
    for e in global_memory.get("entries", []):
        src = e.get("source_session", "")
        if src == session_id:
            scope_creep_events += 1
        proj = e.get("project", "unknown")
        project_tasks[proj] = project_tasks.get(proj, 0) + 1

    what_went_well = []
    if len(phases) >= 3:
        what_went_well.append("Completed multiple pipeline phases")
    if any("executing" in p["phase"] for p in phases):
        what_went_well.append("Reached execution phase")
    if pipeline.get("current_phase") == "end":
        what_went_well.append("Session completed through all phases")

    what_caused_switches = []
    if scope_creep_events > 0:
        what_caused_switches.append(f"{scope_creep_events} out-of-scope tasks saved to Global Memory")
    if len(project_tasks) > 1:
        what_caused_switches.append(f"Tasks span {len(project_tasks)} different projects")

    avg_tools = sum(tool_counts) / max(len(tool_counts), 1)

    recommendations = []
    if scope_creep_events > 2:
        recommendations.append("Consider tighter scope definitions at session start")
    if avg_tools < 2:
        recommendations.append("Low tool usage suggests more automation opportunities")
    if session_duration and session_duration > 3600:
        recommendations.append("Session exceeded 1 hour \u2014 consider shorter focused sessions")
    if len(phase_names) < 2:
        recommendations.append("Try completing more pipeline phases for better session structure")

    learning_entry = {
        "session_id": session_id,
        "timestamp": _now_iso(),
        "phases_completed": phase_names,
        "session_duration_seconds": session_duration,
        "total_tools_used": sum(tool_counts),
        "scope_creep_events": scope_creep_events,
        "context_switches": context_switches,
        "projects_touched": list(project_tasks.keys()),
        "what_went_well": what_went_well,
        "causes_of_context_switches": what_caused_switches,
        "recommendations": recommendations,
        "tool_pattern": tool_counts,
    }

    learning_db.setdefault("sessions", []).append(learning_entry)
    if len(learning_db["sessions"]) > 100:
        learning_db["sessions"] = learning_db["sessions"][-100:]
    save_json(_LEARNING_PATH, learning_db)

    return {
        "session_id": session_id,
        "insights": {
            "what_went_well": what_went_well,
            "causes_of_context_switches": what_caused_switches,
            "scope_creep_events": scope_creep_events,
            "session_duration_seconds": session_duration,
        },
        "stats": {
            "phases_completed": len(phase_names),
            "total_tools_used": sum(tool_counts),
            "average_tools_per_phase": round(avg_tools, 1),
        },
        "recommendations": recommendations,
        "total_learned_sessions": len(learning_db["sessions"]),
    }


# ===================================================================
# Handler Dispatch
# ===================================================================

def handle_tool_call(name, args):
    if name == "read_focus_scope_check":
        return check_scope(
            args.get("input_text", ""),
            args.get("current_project", "CortexStratum"),
        )
    elif name == "read_focus_nudge":
        return generate_nudge(
            args.get("scope_result", {}),
            args.get("user_input", ""),
        )
    elif name == "write_adhd_store_global":
        return store_global(
            args.get("project", "unknown"),
            args.get("task", ""),
            args.get("context", ""),
            args.get("source_session", ""),
        )
    elif name == "read_focus_global":
        return read_global(
            args.get("project"),
            args.get("limit", 10),
        )
    elif name == "read_focus_pipeline_status":
        return pipeline_status()
    elif name == "write_adhd_pipeline_advance":
        return advance_pipeline(
            args.get("next_phase", ""),
            args.get("summary", ""),
        )
    elif name == "read_focus_decompose":
        return decompose(
            args.get("prompt_text", ""),
        )
    elif name == "read_focus_prioritize":
        return prioritize(
            args.get("tasks", []),
        )
    elif name == "write_focus_learn":
        return learn(
            args.get("session_id", ""),
            args.get("events"),
        )
    return {"error": f"Unknown adhd tool: {name}"}


# ===================================================================
# Standalone entry point
# ===================================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_text = "Fix the login bug and also build a dashboard for StudySpace"
        sr = check_scope(test_text)
        print(json.dumps(sr, indent=2))

        nudge = generate_nudge(sr, test_text)
        print(json.dumps(nudge, indent=2))

        dec = decompose("1. Write API handler\n2. Design the UI layout\n3. Research auth libraries")
        print(json.dumps(dec, indent=2))

        prio = prioritize(dec["tasks"])
        print(json.dumps(prio, indent=2))

        store = store_global("StudySpace", "Build dashboard", "From scope check", "test-001")
        print(json.dumps(store, indent=2))

        gl = read_global()
        print(json.dumps(gl, indent=2))

        adv = advance_pipeline("help")
        print(json.dumps(adv, indent=2))
        adv2 = advance_pipeline("context")
        print(json.dumps(adv2, indent=2))

        st = pipeline_status()
        print(json.dumps(st, indent=2))

        lr = learn("test-001")
        print(json.dumps(lr, indent=2))

        print("\nAll components OK.")
    else:
        print("adhd-module.py — Cognitive Focus Engine")
        print("Usage: python adhd-module.py --test")
