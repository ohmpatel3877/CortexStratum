"""
task_session.py — In-session todo tracking for CortexStratum (stdlib only).

Discipline enforced (mirrors the agent's drift-prevention rule):
  - exactly ONE task in_progress at a time
  - a task is only 'completed' after a verification note is recorded
  - every mutation is an atomic write (temp + os.replace) under a file lock

State: .memory/task-sessions/<session_id>.json
"""

from __future__ import annotations
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = PROJECT_ROOT / ".memory" / "task-sessions"

_lock = threading.Lock()
VALID = ("pending", "in_progress", "completed", "cancelled")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _path(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "default"
    return SESSIONS_DIR / f"{safe}.json"


def _read(session_id: str) -> dict:
    p = _path(session_id)
    if not p.exists():
        return {"session_id": session_id, "tasks": [], "updated_at": _now()}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"session_id": session_id, "tasks": [], "updated_at": _now()}


def _write(state: dict) -> None:
    _ensure()
    p = _path(state["session_id"])
    state["updated_at"] = _now()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _next_id(state: dict) -> str:
    nums = [int(t["id"][1:]) for t in state["tasks"]
            if t["id"].startswith("t") and t["id"][1:].isdigit()]
    return f"t{(max(nums) + 1) if nums else 1}"


def task_create(session_id: str, content: str, status: str = "pending") -> dict:
    if not content or not content.strip():
        return {"ok": False, "error": "content required"}
    if status not in VALID:
        status = "pending"
    with _lock:
        state = _read(session_id)
        if status == "in_progress" and any(t["status"] == "in_progress" for t in state["tasks"]):
            for t in state["tasks"]:
                if t["status"] == "in_progress":
                    t["status"] = "pending"
        tid = _next_id(state)
        state["tasks"].append({
            "id": tid, "content": content.strip(), "status": status,
            "verifications": [], "created_at": _now(),
        })
        _write(state)
    return {"ok": True, "id": tid, "status": status}


def task_list(session_id: str) -> dict:
    state = _read(session_id)
    return {"ok": True, "summary": {
        "total": len(state["tasks"]),
        "pending": sum(1 for t in state["tasks"] if t["status"] == "pending"),
        "in_progress": sum(1 for t in state["tasks"] if t["status"] == "in_progress"),
        "completed": sum(1 for t in state["tasks"] if t["status"] == "completed"),
        "cancelled": sum(1 for t in state["tasks"] if t["status"] == "cancelled"),
    }, "tasks": state["tasks"]}


def task_start(session_id: str, task_id: str) -> dict:
    with _lock:
        state = _read(session_id)
        t = next((x for x in state["tasks"] if x["id"] == task_id), None)
        if not t:
            return {"ok": False, "error": f"unknown task {task_id}"}
        if t["status"] == "completed":
            return {"ok": False, "error": "cannot start a completed task"}
        for x in state["tasks"]:
            if x["status"] == "in_progress":
                x["status"] = "pending"
        t["status"] = "in_progress"
        _write(state)
    return {"ok": True, "id": task_id, "status": "in_progress"}


def task_verify(session_id: str, task_id: str, note: str) -> dict:
    if not note or not note.strip():
        return {"ok": False, "error": "verification note required"}
    with _lock:
        state = _read(session_id)
        t = next((x for x in state["tasks"] if x["id"] == task_id), None)
        if not t:
            return {"ok": False, "error": f"unknown task {task_id}"}
        t.setdefault("verifications", []).append({"note": note.strip(), "at": _now()})
        _write(state)
    return {"ok": True, "id": task_id, "verifications": len(t["verifications"])}


def task_complete(session_id: str, task_id: str) -> dict:
    with _lock:
        state = _read(session_id)
        t = next((x for x in state["tasks"] if x["id"] == task_id), None)
        if not t:
            return {"ok": False, "error": f"unknown task {task_id}"}
        if not t.get("verifications"):
            return {"ok": False, "error": "refuse: record verification first (task_verify)",
                    "hint": "a task is 'completed' only after a real check, not just an edit"}
        t["status"] = "completed"
        _write(state)
    return {"ok": True, "id": task_id, "status": "completed"}


def task_cancel(session_id: str, task_id: str) -> dict:
    with _lock:
        state = _read(session_id)
        t = next((x for x in state["tasks"] if x["id"] == task_id), None)
        if not t:
            return {"ok": False, "error": f"unknown task {task_id}"}
        t["status"] = "cancelled"
        _write(state)
    return {"ok": True, "id": task_id, "status": "cancelled"}
