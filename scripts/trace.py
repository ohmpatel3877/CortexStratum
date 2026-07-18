"""
trace.py — Consolidated trace system replacing error-trace.ps1, decision-trace.ps1,
goal-registry.ps1, and check-commitments.ps1.

Pure Python — replaces 4 PowerShell scripts. JSON file persistence under DATA_DIR.

CLI usage:
  python trace.py error-log --command <cmd> --error-output <text> [--exit-code <n>]
  python trace.py error-attempt --error-signature <sig> --fix <text> [--result <str>]
  python trace.py error-resolve --error-signature <sig> --root-cause <text> --resolution <text>
  python trace.py error-search <keyword>
  python trace.py error-status

  python trace.py decision-add --title <text> --decision <text> --category <cat> [--rationale <text>] [--context <text>] [--alternatives <a,b>] [--consequences <a,b>] [--files <a,b>] [--notes <text>]
  python trace.py decision-update --id <id> [--status <str>] [--notes <text>] [--superseded-by <id>]
  python trace.py decision-search <keyword>
  python trace.py decision-by-file <path>
  python trace.py decision-status

  python trace.py goal-init <goal>
  python trace.py goal-add-subgoal <description>
  python trace.py goal-complete <id>
  python trace.py goal-check <current action ...>
  python trace.py goal-status

  python trace.py commitment-list [--session-start]
  python trace.py commitment-verify <id> [--dry-run]
"""

import json, os, re, uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _today_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _session_id() -> str:
    sid = os.environ.get("OPENCODE_SESSION_ID")
    if sid:
        return sid
    return f"ses_{uuid.uuid4().hex[:12]}"


from utils import load_json, save_json


def _result(success: bool, data=None, error: str = None) -> dict:
    out = {"success": success, "data": data, "error": error}
    return out


# ===========================================================================
# Error Trace  (replaces error-trace.ps1)
# ===========================================================================
# File: data/error-registry.json
# Structure: { "version": 1, "errors": [...] }
# Entry: { id, error_signature, command, exit_code, first_seen, last_seen,
#          occurrence_count, status, root_cause, resolution, attempts }
# Attempt: { fix, result, timestamp }

ERROR_REGISTRY_PATH = DATA_DIR / "error-registry.json"


def _normalize_signature(text: str) -> str:
    normalized = re.sub(r'\s+', ' ', text)
    normalized = normalized.replace('"', '').replace("'", '').replace('`', '')
    return normalized.strip()[:100]


def _ensure_error_registry():
    if not ERROR_REGISTRY_PATH.exists():
        save_json(ERROR_REGISTRY_PATH, {"version": 1, "errors": []})


def _load_error_registry():
    _ensure_error_registry()
    return load_json(ERROR_REGISTRY_PATH, {"version": 1, "errors": []})


def _save_error_registry(data):
    save_json(ERROR_REGISTRY_PATH, data)


def _next_error_id(data):
    max_num = 0
    for e in data.get("errors", []):
        m = re.match(r'err-(\d+)', e.get("id", ""))
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"err-{max_num + 1:03d}"


def error_log_error(command: str, error_output: str, exit_code: int = None) -> dict:
    if not command or not error_output:
        return _result(False, error="error_log_error requires command and error_output")
    data = _load_error_registry()
    sig = _normalize_signature(error_output)
    now = _now_iso()

    for entry in data.get("errors", []):
        if entry.get("error_signature") == sig:
            entry["occurrence_count"] = entry.get("occurrence_count", 0) + 1
            entry["last_seen"] = now
            # Detect recurring: resolved error being logged again
            was_resolved = entry.get("status") == "resolved"
            if was_resolved:
                entry["status"] = "recurring"
                entry.setdefault("recurrences", []).append(now)
            _save_error_registry(data)
            return _result(True, {
                "action": "LogError", "id": entry["id"],
                "status": "recurring" if was_resolved else "incremented",
                "signature": sig, "occurrence_count": entry["occurrence_count"],
            })

    entry = {
        "id": _next_error_id(data),
        "error_signature": sig,
        "command": command,
        "exit_code": exit_code if exit_code is not None else 0,
        "first_seen": now,
        "last_seen": now,
        "occurrence_count": 1,
        "status": "unresolved",
        "root_cause": "",
        "resolution": "",
        "attempts": [],
    }
    data.setdefault("errors", []).append(entry)
    _save_error_registry(data)
    return _result(True, {
        "action": "LogError", "id": entry["id"],
        "status": "created", "signature": sig,
    })


def error_log_attempt(error_signature: str, fix: str, result: str = "unknown") -> dict:
    if not error_signature or not fix:
        return _result(False, error="error_log_attempt requires error_signature and fix")
    data = _load_error_registry()
    for entry in data.get("errors", []):
        if error_signature.lower() in entry.get("error_signature", "").lower():
            attempt = {"fix": fix, "result": result, "timestamp": _now_iso()}
            entry.setdefault("attempts", []).append(attempt)
            entry["last_seen"] = attempt["timestamp"]
            _save_error_registry(data)
            return _result(True, {
                "action": "LogAttempt", "id": entry["id"],
                "fix": fix, "result": result,
            })
    return _result(False, error="Error signature not found", data={"signature": error_signature})


def error_resolve(error_signature: str, root_cause: str, resolution: str) -> dict:
    if not error_signature or not root_cause or not resolution:
        return _result(False, error="error_resolve requires error_signature, root_cause, and resolution")
    data = _load_error_registry()
    for entry in data.get("errors", []):
        if error_signature.lower() in entry.get("error_signature", "").lower():
            entry["status"] = "resolved"
            entry["root_cause"] = root_cause
            entry["resolution"] = resolution
            entry["last_seen"] = _now_iso()
            _save_error_registry(data)
            return _result(True, {
                "action": "Resolve", "id": entry["id"], "status": "resolved",
            })
    return _result(False, error="Error signature not found", data={"signature": error_signature})


def error_search(keyword: str) -> dict:
    if not keyword:
        return _result(False, error="error_search requires keyword")
    data = _load_error_registry()
    kw = keyword.lower()
    results = []
    for entry in data.get("errors", []):
        if (kw in entry.get("error_signature", "").lower()
                or kw in entry.get("root_cause", "").lower()
                or any(kw in a.get("fix", "").lower() for a in entry.get("attempts", []))):
            results.append(entry)
    results.sort(key=lambda e: e.get("last_seen", ""), reverse=True)
    return _result(True, {"action": "Search", "keyword": keyword, "count": len(results), "results": results})


def error_status() -> dict:
    data = _load_error_registry()
    errors = data.get("errors", [])
    total = len(errors)
    resolved = sum(1 for e in errors if e.get("status") == "resolved")
    recurring = sum(1 for e in errors if e.get("status") == "recurring")
    unresolved = total - resolved - recurring

    sorted_by_count = sorted(errors, key=lambda e: e.get("occurrence_count", 0), reverse=True)
    top_3 = [
        {"id": e["id"], "signature": e.get("error_signature", ""), "count": e.get("occurrence_count", 0),
         "status": e.get("status", "")}
        for e in sorted_by_count[:3]
    ]

    total_attempts = sum(len(e.get("attempts", [])) for e in errors)
    avg_attempts = round(total_attempts / total, 2) if total else 0.0

    return _result(True, {
        "action": "Status",
        "total": total,
        "resolved": resolved,
        "recurring": recurring,
        "unresolved": unresolved,
        "top_3_most_frequent": top_3,
        "avg_attempts_to_resolve": avg_attempts,
    })


# ===========================================================================
# Decision Trace  (replaces decision-trace.ps1)
# ===========================================================================
# File: data/decision-registry.json
# Structure: { "version": 1, "decisions": [...] }
# Entry: { id, title, context, decision, alternatives, rationale, consequences,
#          category, files, status, superseded_by, created_at, updated_at, notes }

DECISION_REGISTRY_PATH = DATA_DIR / "decision-registry.json"

_SEED_DECISIONS = [
    {
        "id": "dt-20260715-001",
        "title": "Store behavioral fixes as code_preference not task_learning",
        "context": "Memory categorization was inconsistent; task_learning had too much noise",
        "decision": "Use metadata.type='code_preferences' for behavioral/process fixes, task_learning only for factual domain learnings",
        "alternatives": ["Keep everything in task_learning", "Create a separate rule_preferences type"],
        "rationale": "Separates actionable behavioral rules from passive knowledge, enabling targeted retrieval",
        "consequences": ["Must set metadata.type explicitly on every memory write", "May need migration of existing mixed entries"],
        "category": "architecture",
        "files": ["scripts\\decision-trace.ps1", "AGENTS.md"],
        "status": "active",
        "superseded_by": None,
        "created_at": "2026-07-15T10:00:00Z",
        "updated_at": "2026-07-15T10:00:00Z",
        "notes": "",
    },
    {
        "id": "dt-20260715-002",
        "title": "Limit parallel memory searches to 2 queries max per round",
        "context": "Parallel memory searches were spawning 5+ simultaneous calls, wasting tokens and hitting rate limits",
        "decision": "Cap parallel memory queries to 2 per round; use broader queries with more results instead of narrow queries",
        "alternatives": ["No limit (parallelism handles it)", "Single query per round with rerank"],
        "rationale": "Reduces token waste by 60% while maintaining recall quality through broader result windows",
        "consequences": ["Slightly higher latency per query from larger top_k", "Rare edge cases may need manual re-query"],
        "category": "process",
        "files": ["AGENTS.md"],
        "status": "active",
        "superseded_by": None,
        "created_at": "2026-07-15T10:30:00Z",
        "updated_at": "2026-07-15T10:30:00Z",
        "notes": "",
    },
    {
        "id": "dt-20260715-003",
        "title": "Centralize meta-cognitive artifacts in CortexStratum",
        "context": "Model study guides, behavioral fix lists, and process docs were scattered across multiple repos and local paths",
        "decision": "All meta-cognitive artifacts live under CortexStratum",
        "alternatives": ["Keep artifacts co-located with each project", "Use a separate meta-knowledge repo"],
        "rationale": "Single source of truth for agent improvement artifacts; accessible from any project context via reference",
        "consequences": ["CortexStratum becomes a dependency for all agent sessions", "Must maintain consistent cross-references"],
        "category": "architecture",
        "files": ["model-study-guide.md", "data\\decision-registry.json", "data\\error-registry.json"],
        "status": "active",
        "superseded_by": None,
        "created_at": "2026-07-15T11:00:00Z",
        "updated_at": "2026-07-15T11:00:00Z",
        "notes": "",
    },
]

_VALID_DECISION_STATUSES = {"active", "superseded", "deprecated", "reverted"}


def _ensure_decision_registry():
    if not DECISION_REGISTRY_PATH.exists():
        save_json(DECISION_REGISTRY_PATH, {"version": 1, "decisions": list(_SEED_DECISIONS)})


def _load_decision_registry():
    _ensure_decision_registry()
    return load_json(DECISION_REGISTRY_PATH, {"version": 1, "decisions": []})


def _save_decision_registry(data):
    save_json(DECISION_REGISTRY_PATH, data)


def _next_decision_id(data):
    max_num = 0
    for d in data.get("decisions", []):
        m = re.match(r'dt-\d{8}-(\d+)', d.get("id", ""))
        if m:
            max_num = max(max_num, int(m.group(1)))
    today = _today_compact()
    return f"dt-{today}-{max_num + 1:03d}"


def decision_add(title: str, decision: str, rationale: str = "",
                 context: str = "", alternatives: str = "",
                 category: str = "architecture") -> dict:
    if not title or not decision:
        return _result(False, error="decision_add requires title and decision")
    data = _load_decision_registry()
    now = _now_iso()
    alts = [a.strip() for a in alternatives.split(",") if a.strip()] if isinstance(alternatives, str) and alternatives else []
    entry = {
        "id": _next_decision_id(data),
        "title": title,
        "context": context or "",
        "decision": decision,
        "alternatives": alts,
        "rationale": rationale or "",
        "consequences": [],
        "category": category,
        "files": [],
        "status": "active",
        "superseded_by": None,
        "created_at": now,
        "updated_at": now,
        "notes": "",
    }
    data.setdefault("decisions", []).append(entry)
    _save_decision_registry(data)
    return _result(True, {"action": "Add", "id": entry["id"], "title": title, "status": "created"})


def decision_update(decision_id: str, status: str = None,
                    notes: str = None, superseded_by: str = None) -> dict:
    if not decision_id:
        return _result(False, error="decision_update requires decision_id")
    data = _load_decision_registry()
    for entry in data.get("decisions", []):
        if entry.get("id") == decision_id:
            if status:
                if status not in _VALID_DECISION_STATUSES:
                    return _result(False, error=f"Status must be one of: {', '.join(sorted(_VALID_DECISION_STATUSES))}", data={"id": decision_id})
                entry["status"] = status
            if notes is not None:
                entry["notes"] = notes
            if status == "superseded" and superseded_by:
                entry["superseded_by"] = superseded_by
            entry["updated_at"] = _now_iso()
            _save_decision_registry(data)
            return _result(True, {"action": "Update", "id": decision_id, "status": status or "unchanged"})
    return _result(False, error=f"Decision not found: {decision_id}", data={"id": decision_id})


def decision_search(keyword: str) -> dict:
    if not keyword:
        return _result(False, error="decision_search requires keyword")
    data = _load_decision_registry()
    kw = keyword.lower()
    results = []
    for d in data.get("decisions", []):
        if (kw in d.get("title", "").lower()
                or kw in d.get("context", "").lower()
                or kw in d.get("decision", "").lower()
                or kw in d.get("rationale", "").lower()
                or kw in d.get("category", "").lower()):
            results.append(d)
    results.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return _result(True, {"action": "Search", "keyword": keyword, "count": len(results), "results": results})


def decision_by_file(file_path: str) -> dict:
    if not file_path:
        return _result(False, error="decision_by_file requires file_path")
    data = _load_decision_registry()
    results = [d for d in data.get("decisions", []) if file_path in d.get("files", [])]
    return _result(True, {"action": "ByFile", "file_path": file_path, "count": len(results), "results": results})


def decision_status() -> dict:
    data = _load_decision_registry()
    decisions = data.get("decisions", [])
    total = len(decisions)

    by_category = {}
    for d in decisions:
        cat = d.get("category", "uncategorized")
        by_category[cat] = by_category.get(cat, 0) + 1
    by_category_sorted = sorted(by_category.items(), key=lambda x: -x[1])

    by_status = {}
    for d in decisions:
        st = d.get("status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recently_superseded = []
    for d in decisions:
        if d.get("status") == "superseded" and d.get("updated_at"):
            try:
                updated = datetime.fromisoformat(d["updated_at"].replace("Z", "+00:00"))
                if updated >= thirty_days_ago:
                    recently_superseded.append({
                        "id": d["id"], "title": d["title"],
                        "superseded_by": d.get("superseded_by"),
                    })
            except ValueError:
                pass

    return _result(True, {
        "action": "Status",
        "total": total,
        "by_category": dict(by_category_sorted),
        "by_status": by_status,
        "recently_superseded": recently_superseded,
    })


# ===========================================================================
# Goal Registry  (replaces goal-registry.ps1)
# ===========================================================================
# File: data/goal-registry.json
# Structure: { session_id, original_goal, start_time, sub_goals }
# Sub-goal: { id, description, status, created_at, completed_at }

GOAL_REGISTRY_PATH = DATA_DIR / "goal-registry.json"


def _load_goal_registry():
    return load_json(GOAL_REGISTRY_PATH, None)


def _save_goal_registry(data):
    save_json(GOAL_REGISTRY_PATH, data)


def _require_goal_registry():
    registry = _load_goal_registry()
    if registry is None:
        raise FileNotFoundError("No goal registry found. Run goal_init first.")
    return registry


def goal_init(goal: str) -> dict:
    if not goal:
        return _result(False, error="goal_init requires goal")
    now = _now_iso()
    registry = {
        "session_id": _session_id(),
        "original_goal": goal,
        "start_time": now,
        "sub_goals": [],
    }
    _save_goal_registry(registry)
    return _result(True, {
        "action": "Init",
        "session_id": registry["session_id"],
        "original_goal": goal,
        "status": "initialized",
    })


def goal_add_subgoal(description: str) -> dict:
    if not description:
        return _result(False, error="goal_add_subgoal requires description")
    try:
        registry = _require_goal_registry()
    except FileNotFoundError as e:
        return _result(False, error=str(e))
    now = _now_iso()
    entry = {
        "id": len(registry.get("sub_goals", [])),
        "description": description,
        "status": "pending",
        "created_at": now,
        "completed_at": None,
    }
    registry.setdefault("sub_goals", []).append(entry)
    _save_goal_registry(registry)
    return _result(True, {"action": "AddSubGoal", "id": entry["id"], "description": description})


def goal_complete_subgoal(subgoal_id: int) -> dict:
    try:
        registry = _require_goal_registry()
    except FileNotFoundError as e:
        return _result(False, error=str(e))
    for sg in registry.get("sub_goals", []):
        if sg.get("id") == subgoal_id:
            sg["status"] = "completed"
            sg["completed_at"] = _now_iso()
            _save_goal_registry(registry)
            return _result(True, {"action": "CompleteSubGoal", "id": subgoal_id, "description": sg["description"]})
    return _result(False, error=f"Sub-goal with id={subgoal_id} not found")


def goal_check_alignment(current_action: str) -> dict:
    if not current_action:
        return _result(False, error="goal_check_alignment requires current_action")
    try:
        registry = _require_goal_registry()
    except FileNotFoundError as e:
        return _result(False, error=str(e))

    goal = registry.get("original_goal", "")
    goal_words = set(w for w in re.split(r'\W+', goal.lower()) if len(w) > 2)
    action_words = set(w for w in re.split(r'\W+', current_action.lower()) if len(w) > 2)

    if not goal_words:
        return _result(True, {
            "action": "CheckAlignment",
            "aligned": True,
            "reason": "insufficient keywords in original goal",
        })

    overlap = goal_words & action_words
    ratio = len(overlap) / len(goal_words)
    aligned = ratio >= 0.30

    sub_goals = registry.get("sub_goals", [])
    last_subgoal = sub_goals[-1] if sub_goals else None
    last_line = {
        "description": last_subgoal["description"] if last_subgoal else None,
        "status": last_subgoal.get("status") if last_subgoal else None,
    }

    return _result(True, {
        "action": "CheckAlignment",
        "aligned": aligned,
        "ratio": round(ratio, 4),
        "goal_keywords": sorted(goal_words),
        "action_keywords": sorted(action_words),
        "overlap": sorted(overlap),
        "last_subgoal": last_line,
    })


def goal_status() -> dict:
    registry = _load_goal_registry()
    if registry is None:
        return _result(True, {"action": "Status", "active": False, "message": "No active goal registry"})

    sub_goals = registry.get("sub_goals", [])
    now_dt = datetime.now(timezone.utc)

    elapsed_str = ""
    try:
        start = datetime.fromisoformat(registry["start_time"].replace("Z", "+00:00"))
        elapsed = now_dt - start
        total_secs = int(elapsed.total_seconds())
        h, r = divmod(total_secs, 3600)
        m, s = divmod(r, 60)
        if h:
            elapsed_str = f"{h}h {m}m {s}s"
        else:
            elapsed_str = f"{m}m {s}s"
    except (ValueError, KeyError):
        elapsed_str = "unknown"

    goal_text = registry.get("original_goal", "")
    goal_display = goal_text[:80] + "..." if len(goal_text) > 80 else goal_text

    subgoal_details = []
    for sg in sub_goals:
        duration_str = ""
        try:
            created = datetime.fromisoformat(sg.get("created_at", "").replace("Z", "+00:00"))
            if sg.get("status") == "completed" and sg.get("completed_at"):
                end = datetime.fromisoformat(sg["completed_at"].replace("Z", "+00:00"))
                dur = end - created
            else:
                dur = now_dt - created
            dm, ds = divmod(int(dur.total_seconds()), 60)
            duration_str = f"{dm}m {ds}s"
        except (ValueError, TypeError):
            pass

        subgoal_details.append({
            "id": sg.get("id"),
            "description": sg.get("description"),
            "status": sg.get("status", "unknown"),
            "duration": duration_str,
            "created_at": sg.get("created_at"),
            "completed_at": sg.get("completed_at"),
        })

    alignment = None
    goal_words = set(w for w in re.split(r'\W+', goal_text.lower()) if len(w) > 2)
    recent = [sg for sg in sub_goals if sg.get("status") != "cancelled"][-3:]
    if recent and goal_words:
        all_words = set()
        for sg in recent:
            all_words.update(w for w in re.split(r'\W+', sg.get("description", "").lower()) if len(w) > 2)
        overlap = all_words & goal_words
        ratio = len(overlap) / len(goal_words) if goal_words else 1.0
        aligned = ratio >= 0.30
        alignment = {
            "aligned": aligned,
            "ratio": round(ratio, 4),
            "keywords": sorted(goal_words),
        }

    return _result(True, {
        "action": "Status",
        "active": True,
        "session_id": registry.get("session_id"),
        "original_goal": goal_display,
        "elapsed": elapsed_str,
        "sub_goals": subgoal_details,
        "total_sub_goals": len(sub_goals),
        "alignment": alignment,
    })


# ===========================================================================
# Commitment Checker  (replaces check-commitments.ps1)
# ===========================================================================
# File: data/commitments.json
# Structure: { "version": 1, "commitments": [...] }
# Commitment: { id, text, source, stored_date, verified_sessions, next_verify }

COMMITMENTS_PATH = DATA_DIR / "commitments.json"

_SEED_COMMITMENTS = [
    {"id": "b1", "text": "Batch-load skills at session start before any tool execution", "source": "code_preference", "stored_date": "2026-07-15", "verified_sessions": [], "next_verify": "2026-07-16"},
    {"id": "b2", "text": "Use 2 targeted memory queries max per round", "source": "code_preference", "stored_date": "2026-07-15", "verified_sessions": [], "next_verify": "2026-07-16"},
    {"id": "b3", "text": "Verify all file:line claims with read/grep before stating as fact", "source": "code_preference", "stored_date": "2026-07-15", "verified_sessions": [], "next_verify": "2026-07-16"},
    {"id": "b4", "text": "Group independent reads and searches into single parallel batches", "source": "code_preference", "stored_date": "2026-07-15", "verified_sessions": [], "next_verify": "2026-07-16"},
    {"id": "b5", "text": "Run lint + typecheck + tests before marking any code task complete", "source": "code_preference", "stored_date": "2026-07-15", "verified_sessions": [], "next_verify": "2026-07-16"},
]


def _ensure_commitments():
    if not COMMITMENTS_PATH.exists():
        save_json(COMMITMENTS_PATH, {"version": 1, "commitments": list(_SEED_COMMITMENTS)})


def _load_commitments():
    _ensure_commitments()
    return load_json(COMMITMENTS_PATH, {"version": 1, "commitments": list(_SEED_COMMITMENTS)})


def _save_commitments(data):
    save_json(COMMITMENTS_PATH, data)


def commitment_list(session_start: bool = False) -> dict:
    data = _load_commitments()
    commitments = data.get("commitments", [])
    today = _today_str()

    if session_start:
        pending = [c for c in commitments if c.get("next_verify", "") <= today]
        return _result(True, {
            "action": "List",
            "mode": "session_start",
            "total_pending": len(pending),
            "commitments": pending,
        })

    return _result(True, {
        "action": "List",
        "mode": "all",
        "total": len(commitments),
        "commitments": commitments,
    })


def commitment_verify(commitment_id: str, dry_run: bool = False) -> dict:
    if not commitment_id:
        return _result(False, error="commitment_verify requires commitment_id")
    data = _load_commitments()
    current_session = _session_id()

    for c in data.get("commitments", []):
        if c.get("id") == commitment_id:
            verified_sessions = c.get("verified_sessions", [])
            if current_session in verified_sessions:
                return _result(True, {
                    "action": "Verify", "id": commitment_id,
                    "status": "already_verified", "session": current_session,
                })

            if not dry_run:
                verified_sessions.append(current_session)
                c["verified_sessions"] = verified_sessions
                _save_commitments(data)
                return _result(True, {
                    "action": "Verify", "id": commitment_id,
                    "status": "verified", "session": current_session,
                })
            else:
                return _result(True, {
                    "action": "Verify", "id": commitment_id,
                    "status": "dry_run", "session": current_session,
                })

    return _result(False, error=f"Commitment '{commitment_id}' not found")


def commitment_add(text: str, source: str = "manual") -> dict:
    if not text:
        return _result(False, error="commitment_add requires text")
    data = _load_commitments()
    commitments = data.setdefault("commitments", [])
    now = _today_str()

    existing_ids = [c.get("id", "") for c in commitments]
    num = 1
    while f"b{num}" in existing_ids:
        num += 1

    entry = {
        "id": f"b{num}",
        "text": text,
        "source": source,
        "stored_date": now,
        "verified_sessions": [],
        "next_verify": now,
    }
    commitments.append(entry)
    _save_commitments(data)
    return _result(True, {"action": "Add", "id": entry["id"], "text": text})


# ===========================================================================
# Tool call dispatcher  (mirrors tools-mcp-server.py routing)
# ===========================================================================

def handle_tool_call(name: str, args: dict) -> dict:
    """Route MCP tool calls to the right handler."""
    handlers = {
        "write_xtrace_log_error": lambda a: error_log_error(
            command=a.get("command", ""),
            error_output=a.get("error_output", ""),
            exit_code=a.get("exit_code"),
        ),
        "read_xtrace_search": lambda a: error_search(
            keyword=a.get("keyword", ""),
        ),
        "read_xtrace_status": lambda a: error_status(),
        "write_dtrace_add": lambda a: decision_add(
            title=a.get("title", ""),
            decision=a.get("decision", ""),
            rationale=a.get("rationale", ""),
            context=a.get("context", ""),
            alternatives=a.get("alternatives", ""),
            category=a.get("category", "architecture"),
        ),
        "read_dtrace_search": lambda a: decision_search(
            keyword=a.get("keyword", ""),
        ),
        "write_goal_registry_init": lambda a: goal_init(
            goal=a.get("goal", ""),
        ),
        "write_goal_registry_add_subgoal": lambda a: goal_add_subgoal(
            description=a.get("description", ""),
        ),
        "read_goal_registry_status": lambda a: goal_status(),
        "read_goal_registry_check_alignment": lambda a: goal_check_alignment(
            current_action=a.get("current_action", ""),
        ),
        "read_commitment_checker_list": lambda a: commitment_list(
            session_start=a.get("session_start", False),
        ),
        "write_commitment_verify": lambda a: commitment_verify(
            commitment_id=a.get("commitment_id", ""),
            dry_run=a.get("dry_run", False),
        ),
    }
    handler = handlers.get(name)
    if handler is None:
        return _result(False, error=f"Unknown tool call: {name}")
    try:
        return handler(args)
    except Exception as e:
        return _result(False, error=f"Error handling tool call '{name}': {str(e)}")


# ===========================================================================
# CLI entry point
# ===========================================================================

def main():
    import sys
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]

    # --- error trace ---
    if cmd == "error-log":
        kwargs = {}
        for i in range(1, len(args) - 1):
            if args[i] in ("--command", "--error-output", "--exit-code"):
                kwargs[args[i][2:].replace("-", "_")] = args[i + 1]
        if "exit_code" in kwargs:
            kwargs["exit_code"] = int(kwargs["exit_code"])
        print(json.dumps(error_log_error(**kwargs), indent=2))

    elif cmd == "error-search":
        kw = args[1] if len(args) > 1 else ""
        print(json.dumps(error_search(kw), indent=2, default=str))

    elif cmd == "error-status":
        print(json.dumps(error_status(), indent=2))

    elif cmd == "error-attempt":
        kwargs = {}
        for i in range(1, len(args) - 1):
            if args[i] in ("--error-signature", "--fix", "--result"):
                kwargs[args[i][2:].replace("-", "_")] = args[i + 1]
        print(json.dumps(error_log_attempt(**kwargs), indent=2))

    elif cmd == "error-resolve":
        kwargs = {}
        for i in range(1, len(args) - 1):
            if args[i] in ("--error-signature", "--root-cause", "--resolution"):
                kwargs[args[i][2:].replace("-", "_")] = args[i + 1]
        print(json.dumps(error_resolve(**kwargs), indent=2))

    # --- decision trace ---
    elif cmd == "decision-add":
        kwargs = {}
        for i in range(1, len(args) - 1):
            if args[i] in ("--title", "--decision", "--category", "--context", "--rationale", "--notes", "--alternatives"):
                key = args[i][2:].replace("-", "_")
                kwargs[key] = args[i + 1]
        print(json.dumps(decision_add(**kwargs), indent=2))

    elif cmd == "decision-update":
        kwargs = {}
        for i in range(1, len(args) - 1):
            if args[i] in ("--id", "--status", "--notes", "--superseded-by"):
                key = args[i][2:].replace("-", "_")
                kwargs[key] = args[i + 1]
        print(json.dumps(decision_update(**kwargs), indent=2))

    elif cmd == "decision-search":
        kw = args[1] if len(args) > 1 else ""
        print(json.dumps(decision_search(kw), indent=2, default=str))

    elif cmd == "decision-by-file":
        fp = args[1] if len(args) > 1 else ""
        print(json.dumps(decision_by_file(fp), indent=2, default=str))

    elif cmd == "decision-status":
        print(json.dumps(decision_status(), indent=2))

    # --- goal registry ---
    elif cmd == "goal-init":
        goal = args[1] if len(args) > 1 else ""
        print(json.dumps(goal_init(goal), indent=2))

    elif cmd == "goal-add-subgoal":
        desc = args[1] if len(args) > 1 else ""
        print(json.dumps(goal_add_subgoal(desc), indent=2))

    elif cmd == "goal-complete":
        sid = int(args[1]) if len(args) > 1 else -1
        print(json.dumps(goal_complete_subgoal(sid), indent=2))

    elif cmd == "goal-check":
        action = " ".join(args[1:]) if len(args) > 1 else ""
        print(json.dumps(goal_check_alignment(action), indent=2))

    elif cmd == "goal-status":
        print(json.dumps(goal_status(), indent=2))

    # --- commitment checker ---
    elif cmd == "commitment-list":
        session_start = "--session-start" in args
        print(json.dumps(commitment_list(session_start=session_start), indent=2, default=str))

    elif cmd == "commitment-verify":
        cid = args[1] if len(args) > 1 else ""
        dry_run = "--dry-run" in args
        print(json.dumps(commitment_verify(cid, dry_run=dry_run), indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: error-log, error-search, error-status, error-attempt, error-resolve,"
              " decision-add, decision-update, decision-search, decision-by-file, decision-status,"
              " goal-init, goal-add-subgoal, goal-complete, goal-check, goal-status,"
              " commitment-list, commitment-verify")


if __name__ == "__main__":
    main()
