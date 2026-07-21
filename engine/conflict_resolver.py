#!/usr/bin/env python3
"""
Conflict Resolver — Corticostriatal Gate

A middleware layer that sits between tool dispatch and execution.
Detects and resolves conflicts between competing tool calls, mirroring
the cortico-striatal loop where the striatum gates cortical commands.

Strategies:
  - priority (default): mutate > write > read safety ordering
  - conservative: block any potential conflict, log warning
  - permissive: report conflicts but allow through

Architecture:
  Gate.check(name, args) → {"allowed": bool, "conflict": dict|None, "strategy": str}
  Gate.record(name, args, result) → None
"""

import json
import time
from collections import deque
from typing import Any

# ---------------------------------------------------------------------------
# Conflict types
# ---------------------------------------------------------------------------

CONFLICT_WRITE_WRITE = "write_write"
CONFLICT_WRITE_READ = "write_read"  # Write then read on same domain
CONFLICT_READ_WRITE = "read_write"  # Read then write on same domain (stale data risk)
CONFLICT_MUTATE_SAFE = "mutate_no_dryrun"  # Mutate without dry_run=true first

# ---------------------------------------------------------------------------
# Domain classification: which data domain does a tool operate on?
# ---------------------------------------------------------------------------

# Prefix → data domain mappings for conflict detection
_DOMAIN_MAP = {
    "write_xtrace_": "trace",
    "read_xtrace_": "trace",
    "write_dtrace_": "dtrace",
    "read_dtrace_": "dtrace",
    "write_goal_": "goals",
    "read_goal_": "goals",
    "read_commitment_": "commitments",
    "mutate_commitment_": "commitments",
    "write_memory_": "memory",
    "read_memory_": "memory",
    "write_compact_": "compaction",
    "read_compact_": "compaction",
    "write_focus_": "focus",
    "read_focus_": "focus",
    "mutate_focus_": "focus",
    "write_pedagogy_": "pedagogy",
    "read_pedagogy_": "pedagogy",
    "write_db_": "database",
    "read_db_": "database",
    "mutate_consolidation_": "consolidation",
    "read_consolidation_": "consolidation",
    "write_plumber_": "plumber",
    "read_plumber_": "plumber",
    "write_hooks_": "hooks",
    "read_hooks_": "hooks",
    "write_dag_": "dag",
    "read_dag_": "dag",
    "write_gate_": "gate",
    "read_gate_": "gate",
    "read_art_": "art",
    "read_lit_": "literature",
    "read_sensory_": "sensory",
    "write_": "unknown_write",
    "mutate_": "unknown_mutate",
    "read_coder_": "code_analysis",
    "read_devops_": "devops",
    "read_gamedev_": "gamedev",
    "read_sim_": "simulation",
    "read_cad_": "cad",
    "read_electrical_": "electrical",
    "read_audio_": "audio",
    "read_convert_": "conversion",
    "read_regex_": "regex",
    "read_skill_": "skills",
    "read_tools_": "tools",
    "read_verifier_": "verifier",
    "read_wm_": "working_memory",
    "write_wm_": "working_memory",
    "mutate_wm_": "working_memory",
}


def _classify(name: str) -> tuple[str, str]:
    """Return (category, domain) for a tool name.

    Category: read | write | mutate
    Domain: memory | trace | goals | sensory | simulation | ...
    """
    if name.startswith("mutate_"):
        category = "mutate"
    elif name.startswith("write_"):
        category = "write"
    else:
        category = "read"

    domain = None
    for prefix, d in sorted(_DOMAIN_MAP.items(), key=lambda x: -len(x[0])):
        if name.startswith(prefix):
            domain = d
            break
    if domain is None:
        domain = "other"

    return category, domain


def _priority(category: str) -> int:
    """Higher number = higher priority when resolving conflicts."""
    return {"mutate": 3, "write": 2, "read": 1}.get(category, 0)


# ---------------------------------------------------------------------------
# ConflictResolver class
# ---------------------------------------------------------------------------


class ConflictResolver:
    """Corticostriatal Gate — resolves conflicts between competing tool calls."""

    def __init__(self, strategy: str = "priority"):
        if strategy not in ("priority", "conservative", "permissive"):
            strategy = "priority"
        self.strategy = strategy
        # Ring buffer of recent tool calls
        self.history: deque[dict] = deque(maxlen=100)
        self._conflicts_log: list[dict] = []
        self._max_log = 50
        self._gates_checked = 0
        self._gates_blocked = 0
        self._gates_warned = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, name: str, args: dict) -> dict:
        """Check if a tool call would create a conflict.

        Returns:
            {"allowed": True/False,
             "conflict": None or conflict_detail dict,
             "strategy": current strategy,
             "blocked_by": None or tool_name}
        """
        self._gates_checked += 1
        category, domain = _classify(name)

        # Look for conflicts against recent history
        conflict = self._detect_conflict(name, category, domain, args)

        if conflict is None:
            return {"allowed": True, "conflict": None, "strategy": self.strategy, "blocked_by": None}

        # Apply strategy
        if self.strategy == "conservative":
            self._gates_blocked += 1
            self._log_conflict(name, conflict, "blocked")
            return {
                "allowed": False,
                "conflict": conflict,
                "strategy": self.strategy,
                "blocked_by": conflict.get("conflicting_tool"),
            }

        elif self.strategy == "priority":
            # Check if the conflict involves a higher-priority tool
            conflicting_tool = conflict.get("conflicting_tool")
            if conflicting_tool:
                conflict_cat, _ = _classify(conflicting_tool)
                if _priority(category) >= _priority(conflict_cat):
                    # Equal or higher priority: let it through
                    self._log_conflict(name, conflict, "allowed_priority")
                    return {
                        "allowed": True,
                        "conflict": conflict,
                        "strategy": self.strategy,
                        "blocked_by": None,
                    }
                else:
                    self._gates_blocked += 1
                    self._log_conflict(name, conflict, "blocked")
                    return {
                        "allowed": False,
                        "conflict": conflict,
                        "strategy": self.strategy,
                        "blocked_by": conflicting_tool,
                    }
            else:
                # No specific conflicting tool, allow
                self._log_conflict(name, conflict, "allowed")
                return {
                    "allowed": True,
                    "conflict": conflict,
                    "strategy": self.strategy,
                    "blocked_by": None,
                }

        else:  # permissive
            self._gates_warned += 1
            self._log_conflict(name, conflict, "warned")
            return {
                "allowed": True,
                "conflict": conflict,
                "strategy": self.strategy,
                "blocked_by": None,
            }

    def record(self, name: str, args: dict, result: Any) -> None:
        """Record a completed tool call in gate history."""
        category, domain = _classify(name)
        self.history.append({
            "name": name,
            "category": category,
            "domain": domain,
            "args_keys": list(args.keys()),
            "timestamp": time.time(),
        })

    def status(self) -> dict:
        """Return diagnostic status of the gate."""
        recent = list(self.history)[-15:] if self.history else []
        return {
            "strategy": self.strategy,
            "gates_checked": self._gates_checked,
            "gates_blocked": self._gates_blocked,
            "gates_warned": self._gates_warned,
            "history_size": len(self.history),
            "history_max": self.history.maxlen,
            "conflicts_logged": len(self._conflicts_log),
            "recent_conflicts": list(self._conflicts_log)[-5:],
            "recent_calls": [
                {
                    "name": c["name"],
                    "category": c["category"],
                    "domain": c["domain"],
                    "age_seconds": round(time.time() - c["timestamp"], 1),
                }
                for c in recent
            ],
        }

    def set_strategy(self, strategy: str) -> dict:
        """Change resolution strategy at runtime."""
        if strategy not in ("priority", "conservative", "permissive"):
            return {"status": "error", "error": f"Unknown strategy: {strategy}"}
        self.strategy = strategy
        return {"status": "ok", "strategy": strategy}

    def reset(self) -> dict:
        """Clear history and conflict log."""
        self.history.clear()
        self._conflicts_log.clear()
        self._gates_checked = 0
        self._gates_blocked = 0
        self._gates_warned = 0
        return {"status": "ok", "message": "Gate state reset"}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _detect_conflict(self, name: str, category: str, domain: str, args: dict) -> dict | None:
        """Scan recent history for conflicts with this tool call.

        Returns conflict dict or None.
        """
        if not self.history:
            return None

        # Only scan recent entries (last 10 or within 30 seconds)
        now = time.time()
        window = []
        for entry in reversed(self.history):
            if len(window) >= 10:
                break
            if now - entry["timestamp"] < 30.0:
                window.append(entry)
            else:
                break  # entries are chronological, so once we hit old we can stop

        for entry in window:
            # Same domain conflict
            if entry["domain"] == domain and entry["name"] != name:
                # Write-write on same domain
                if category == "write" and entry["category"] == "write":
                    return {
                        "type": CONFLICT_WRITE_WRITE,
                        "conflicting_tool": entry["name"],
                        "domain": domain,
                        "detail": f"Two writes in succession on domain '{domain}'",
                    }

                # Write-read: writing after reading the same domain (stale data risk)
                if category == "write" and entry["category"] == "read":
                    return {
                        "type": CONFLICT_READ_WRITE,
                        "conflicting_tool": entry["name"],
                        "domain": domain,
                        "detail": f"Read followed by write on domain '{domain}' — stale data risk",
                    }

            # Mutate without dry_run first (only if args don't include dry_run)
            if category == "mutate" and not args.get("dry_run"):
                # Check if any read on this domain exists in history
                for prior in window:
                    if prior["domain"] == domain and prior["category"] == "read":
                        # This is a mutate without dry-run after a read — flag as risky
                        return {
                            "type": CONFLICT_MUTATE_SAFE,
                            "conflicting_tool": prior["name"],
                            "domain": domain,
                            "detail": f"Mutate on '{domain}' without dry_run=true after a read — risky",
                        }

        return None

    def _log_conflict(self, name: str, conflict: dict, action: str) -> None:
        self._conflicts_log.append({
            "tool": name,
            "conflict": conflict,
            "action": action,
            "strategy": self.strategy,
            "timestamp": time.time(),
        })
        if len(self._conflicts_log) > self._max_log:
            self._conflicts_log = self._conflicts_log[-self._max_log:]


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-init)
# ---------------------------------------------------------------------------

_GATE: ConflictResolver | None = None


def get_gate(strategy: str = "priority") -> ConflictResolver:
    global _GATE
    if _GATE is None:
        _GATE = ConflictResolver(strategy)
    return _GATE


# ---------------------------------------------------------------------------
# MCP Tool handlers
# ---------------------------------------------------------------------------


def handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch gate-related MCP tool calls.

    Registered for prefixes: read_gate_*, write_gate_*, mutate_gate_*
    """
    gate = get_gate()
    if name == "read_gate_status":
        return {"content": [{"type": "text", "text": json.dumps(gate.status(), indent=2)}]}
    elif name == "write_gate_strategy":
        result = gate.set_strategy(args.get("strategy", "priority"))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    elif name == "mutate_gate_reset":
        result = gate.reset()
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    else:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"error": f"Unknown gate tool: {name}"}),
                }
            ]
        }


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

GATE_TOOLS = [
    {
        "name": "read_gate_status",
        "description": " READ — Show current gate state: strategy, conflict history, recent calls.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "write_gate_strategy",
        "description": " WRITE — Change conflict resolution strategy. Options: priority, conservative, permissive.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["priority", "conservative", "permissive"],
                    "description": "Resolution strategy",
                },
                "dry_run": {"type": "boolean", "description": "Preview without changing"},
            },
            "required": ["strategy"],
        },
    },
    {
        "name": "mutate_gate_reset",
        "description": " MUTATE — Clear gate history and conflict log. Resets all counters.",
        "permission": "mutate",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {"type": "boolean", "description": "Preview without resetting"},
            },
            "required": [],
        },
    },
]

if __name__ == "__main__":
    # Quick self-test
    g = ConflictResolver("priority")
    # Simulate a write, then another write on same domain
    r1 = g.check("write_memory_add", {"content": "hello"})
    g.record("write_memory_add", {"content": "hello"}, {"status": "ok"})
    r2 = g.check("write_memory_add", {"content": "world"})
    print(f"Test 1 - first write allowed: {r1['allowed']}")
    print(f"Test 2 - second write (same domain): allowed={r2['allowed']}, conflict={r2['conflict'] is not None}")
    print(f"Status: {json.dumps(g.status(), indent=2)}")
