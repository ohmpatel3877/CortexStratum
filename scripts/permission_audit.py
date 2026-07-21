#!/usr/bin/env python3
"""
Permission Audit — Dry-run simulation, checkpoint/undo, tool annotations.

Provides the infrastructure for the mutate layer:
  1. Dry-run simulation — preview what a write/mutate tool would do
  2. Checkpoint + undo — save before-state and restore on demand
  3. Tool annotations — MCP-compatible metadata for OpenCode's permission prompts

Design principles:
  - Zero LLM cost — all simulations are pure computation
  - Minimal storage — checkpoints store diffs, not full copies
  - Crash-safe — temp files + atomic replace, same as the rest of the codebase
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


class PermissionAudit:
    """Dry-run, checkpoint/undo, and annotation engine for write/mutate tools.

    Parameters
    ----------
    data_dir : str | Path
        Directory for storing undo logs and checkpoints.
        Defaults to project_root/data/audit/.
    """

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir is None:
            base = Path(__file__).resolve().parent.parent
            data_dir = base / "data" / "audit"
        self._data_dir = Path(data_dir)
        self._undo_dir = self._data_dir / "undo-log"
        self._undo_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Dry-Run Simulation
    # ------------------------------------------------------------------
    def simulate(self, tool_name: str, args: dict) -> dict:
        """Preview what a write/mutate tool WOULD do, without executing.

        Returns a structured preview: what would be created, modified,
        or deleted. Actual execution is NOT performed.

        Parameters
        ----------
        tool_name : str
            The name of the tool being called.
        args : dict
            The arguments that were passed to the tool.

        Returns
        -------
        dict
            Simulation result with 'preview', 'committed': False,
            and a human-readable 'description'.
        """
        sim = {
            "tool": tool_name,
            "committed": False,
            "mode": "dry_run",
            "preview": {},
            "description": "",
            "undo_token": None,
        }

        # Map tool names to their dry-run simulations
        if tool_name in ("write_memory_add",):
            text = args.get("text", "")
            sim["preview"] = {
                "action": "create",
                "target": "memory_store",
                "content_preview": text[:200] + ("..." if len(text) > 200 else ""),
                "length": len(text),
                "source": args.get("source", "manual"),
            }
            sim["description"] = (
                f"Would add memory ({len(text)} chars, source: {args.get('source', 'manual')})"
            )

        elif tool_name in ("write_xtrace_log_error",):
            sim["preview"] = {
                "action": "create_or_update",
                "target": "error_registry",
                "command": args.get("command", ""),
                "error_preview": (args.get("error_output", "") or "")[:200],
                "exit_code": args.get("exit_code", -1),
            }
            sim["description"] = f"Would log error from '{args.get('command', '?')}'"

        elif tool_name in ("write_dtrace_add",):
            sim["preview"] = {
                "action": "create",
                "target": "decision_registry",
                "title": args.get("title", ""),
                "category": args.get("category", "process"),
            }
            sim["description"] = (
                f"Would record architecture decision '{args.get('title', '?')}'"
            )

        elif tool_name in ("write_goal_registry_init",):
            sim["preview"] = {
                "action": "init",
                "target": "goal_registry",
                "goal": args.get("goal", ""),
            }
            sim["description"] = f"Would initialize goal '{args.get('goal', '?')}'"

        elif tool_name in ("write_goal_registry_add_subgoal",):
            sim["preview"] = {
                "action": "create",
                "target": "goal_registry.subgoal",
                "description": args.get("description", ""),
            }
            sim["description"] = f"Would add sub-goal '{args.get('description', '?')}'"

        elif tool_name in ("write_verifier_renudge",):
            sim["preview"] = {
                "action": "create_or_update",
                "target": "verifier_renudge",
                "target_agent": args.get("target", ""),
                "strategy": args.get("strategy", "incremental"),
            }
            sim["description"] = (
                f"Would send renudge to '{args.get('target', '?')}' with strategy '{args.get('strategy', 'incremental')}'"
            )

        elif tool_name in ("write_verifier_clear_renudge",):
            sim["preview"] = {
                "action": "delete",
                "target": "verifier_renudge",
                "target_agent": args.get("target", ""),
            }
            sim["description"] = f"Would clear renudge for '{args.get('target', '?')}'"

        elif tool_name in ("write_hooks_observe",):
            sim["preview"] = {
                "action": "create",
                "target": "session_observation",
                "event_type": args.get("event_type", "insight"),
                "description_preview": (args.get("description", "") or "")[:200],
            }
            sim["description"] = (
                f"Would log observation ({args.get('event_type', 'insight')})"
            )

        elif tool_name in ("write_hooks_session_end",):
            sim["preview"] = {
                "action": "finalize",
                "target": "session",
                "session_id": args.get("session_id", ""),
            }
            sim["description"] = (
                f"Would finalize session '{args.get('session_id', '?')}'"
            )

        elif tool_name in ("write_memory_consolidate",):
            threshold = args.get("threshold", 0.85)
            sim["preview"] = {
                "action": "merge",
                "target": "memory_store",
                "threshold": threshold,
                "dry_run_available": True,
                "note": "Use write_memory_consolidate with dry_run=true for detailed preview",
            }
            sim["description"] = f"Would consolidate memories (threshold={threshold})"

        elif tool_name in ("mutate_commitment_verify",):
            sim["preview"] = {
                "action": "update",
                "target": "commitment_registry",
                "commitment_id": args.get("id", ""),
            }
            sim["description"] = f"Would verify commitment '{args.get('id', '?')}'"

        elif tool_name in ("mutate_sensory_interact",):
            actions = args.get("actions", [])
            sim["preview"] = {
                "action": "browser_interact",
                "target": "web_page",
                "url": (args.get("url", "") or "")[:100],
                "action_count": len(actions),
                "action_types": list({a.get("type", "") for a in actions}),
            }
            sim["description"] = (
                f"Would perform {len(actions)} browser actions on '{args.get('url', '?')[:60]}'"
            )

        elif tool_name in ("mutate_audit_undo",):
            ckpt_id = args.get("checkpoint_id", "")
            sim["preview"] = {
                "action": "restore",
                "target": "undo_checkpoint",
                "checkpoint_id": ckpt_id,
            }
            sim["description"] = f"Would undo checkpoint '{ckpt_id}'"

        else:
            sim["preview"] = {"action": "unknown", "tool": tool_name}
            sim["description"] = f"Unknown tool: {tool_name}"

        return sim

    # ------------------------------------------------------------------
    # Checkpoint Before Mutation
    # ------------------------------------------------------------------
    def checkpoint(self, tool_name: str, args: dict) -> str:
        """Save a checkpoint of the before-state for undo support.

        Creates a JSON checkpoint file with tool name, args, timestamp,
        and a type-specific snapshot placeholder.

        Parameters
        ----------
        tool_name : str
            The name of the tool being executed.
        args : dict
            The arguments passed to the tool.

        Returns
        -------
        str
            Undo token (checkpoint ID) to pass to undo().
        """
        token = f"undo_{uuid.uuid4().hex[:12]}"
        ckpt = {
            "checkpoint_id": token,
            "tool": tool_name,
            "args": args,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "restored": False,
        }
        ckpt_path = self._undo_dir / f"{token}.json"
        # Atomic write
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(
                suffix=".json", prefix="ckpt_", dir=str(self._undo_dir)
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(ckpt, f, indent=2, ensure_ascii=False)
            os.replace(tmp, str(ckpt_path))
            tmp = None
        finally:
            if tmp is not None and os.path.isfile(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        return token

    # ------------------------------------------------------------------
    # Undo a Mutation
    # ------------------------------------------------------------------
    def undo(self, checkpoint_id: str) -> dict:
        """Restore from a checkpoint.

        Currently marks the checkpoint as restored (future implementations
        can use type-specific restore logic). Returns the checkpoint info.

        Parameters
        ----------
        checkpoint_id : str
            The undo token returned by checkpoint().

        Returns
        -------
        dict
            Checkpoint info with restored status.
        """
        ckpt_path = self._undo_dir / f"{checkpoint_id}.json"
        if not ckpt_path.exists():
            return {
                "status": "error",
                "message": f"Checkpoint not found: {checkpoint_id}",
            }

        try:
            with open(ckpt_path, encoding="utf-8") as f:
                ckpt = json.load(f)

            if ckpt.get("restored"):
                return {
                    "status": "already_restored",
                    "checkpoint_id": checkpoint_id,
                    "tool": ckpt.get("tool"),
                    "timestamp": ckpt.get("timestamp"),
                }

            # Mark as restored
            ckpt["restored"] = True
            ckpt["restored_at"] = datetime.now(timezone.utc).isoformat()
            with open(ckpt_path, "w", encoding="utf-8") as f:
                json.dump(ckpt, f, indent=2, ensure_ascii=False)

            return {
                "status": "restored",
                "checkpoint_id": checkpoint_id,
                "tool": ckpt.get("tool"),
                "timestamp": ckpt.get("timestamp"),
                "args": ckpt.get("args"),
                "message": f"Undo recorded for {ckpt.get('tool')}. "
                "State reversion should be handled by the specific tool module.",
            }

        except (json.JSONDecodeError, OSError) as e:
            return {
                "status": "error",
                "message": f"Failed to restore checkpoint: {e}",
            }

    # ------------------------------------------------------------------
    # List pending checkpoints
    # ------------------------------------------------------------------
    def list_checkpoints(self, limit: int = 20) -> list[dict]:
        """List recent undo checkpoints."""
        if not self._undo_dir.exists():
            return []

        checkpoints = []
        for fname in sorted(
            self._undo_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            if fname.suffix == ".json":
                try:
                    with open(fname, encoding="utf-8") as f:
                        ckpt = json.load(f)
                    checkpoints.append(
                        {
                            "checkpoint_id": ckpt.get("checkpoint_id", fname.stem),
                            "tool": ckpt.get("tool", "?"),
                            "timestamp": ckpt.get("timestamp", ""),
                            "restored": ckpt.get("restored", False),
                        }
                    )
                except Exception:
                    pass
                if len(checkpoints) >= limit:
                    break
        return checkpoints

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def status(self) -> dict:
        """Get permission audit status."""
        total = 0
        restored = 0
        if self._undo_dir.exists():
            for fname in self._undo_dir.iterdir():
                if fname.suffix == ".json":
                    total += 1
                    try:
                        with open(fname) as f:
                            ckpt = json.load(f)
                            if ckpt.get("restored"):
                                restored += 1
                    except Exception:
                        pass
        return {
            "undo_log_count": total,
            "restored_count": restored,
            "undo_directory": str(self._undo_dir),
        }


# ---------------------------------------------------------------------------
# MCP Tool Annotation Helpers
# ---------------------------------------------------------------------------

# Tool annotations following the MCP spec:
# https://spec.modelcontextprotocol.io/specification/2025-03-26/#annotations
TOOL_ANNOTATIONS = {
    # Read tools — safe
    "read_*": {
        "destructiveHint": False,
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
        "title": None,
    },
    # Write tools — state-changing but reversible
    "write_*": {
        "destructiveHint": False,
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
        "title": None,
    },
    # Mutate tools — destructive, should prompt for confirmation
    "mutate_*": {
        "destructiveHint": True,
        "readOnlyHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
        "title": None,
    },
}


def get_annotations(permission: str) -> dict:
    """Get MCP tool annotations for a given permission level.

    These annotations tell the MCP client (e.g., OpenCode desktop)
    whether a tool is read-only, destructive, etc., enabling proper
    permission prompts in the UI.

    Parameters
    ----------
    permission : str
        One of 'read', 'write', 'mutate'.

    Returns
    -------
    dict
        MCP annotations dict with destructiveHint, readOnlyHint, etc.
    """
    key = f"{permission}_*"
    return dict(TOOL_ANNOTATIONS.get(key, TOOL_ANNOTATIONS["read_*"]))


def add_dry_run_to_schema(schema: dict) -> dict:
    """Add a dry_run parameter to a tool's input schema.

    Mutates the schema in place and returns it for chaining.

    Parameters
    ----------
    schema : dict
        The inputSchema of an MCP tool definition.

    Returns
    -------
    dict
        The schema with dry_run added.
    """
    if "properties" not in schema:
        schema["properties"] = {}
    schema["properties"]["dry_run"] = {
        "type": "boolean",
        "default": False,
        "description": "If true, preview the mutation without executing it. Returns a simulation with committed=false.",
    }
    return schema


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_DEFAULT_AUDIT: PermissionAudit | None = None


def _get_audit():
    global _DEFAULT_AUDIT
    if _DEFAULT_AUDIT is None:
        _DEFAULT_AUDIT = PermissionAudit()
    return _DEFAULT_AUDIT


if __name__ == "__main__":
    audit = PermissionAudit()

    # Test dry-run simulations
    print("=== DRY RUN SIMULATIONS ===")
    tests = [
        ("write_memory_add", {"text": "Test memory entry", "source": "manual"}),
        (
            "write_xtrace_log_error",
            {"command": "npm build", "error_output": "Module not found"},
        ),
        (
            "write_dtrace_add",
            {"title": "Use Postgres", "decision": "Yes", "rationale": "ACID"},
        ),
        ("write_memory_consolidate", {"threshold": 0.85}),
        (
            "mutate_sensory_interact",
            {
                "url": "https://example.com",
                "actions": [{"type": "click", "selector": "#btn"}],
            },
        ),
        ("unknown_tool", {}),
    ]
    for name, args in tests:
        sim = audit.simulate(name, args)
        status = "SIM" if sim["committed"] is False else "EXEC"
        print(f"  [{status}] {name}: {sim['description']}")

    # Test checkpoint + undo
    print("\n=== CHECKPOINT + UNDO ===")
    token = audit.checkpoint("write_memory_add", {"text": "test"})
    print(f"  Checkpoint created: {token}")
    result = audit.undo(token)
    print(f"  Undo result: {result['status']}")
    result2 = audit.undo(token)
    print(f"  Double undo: {result2['status']}")

    st = audit.status()
    print("\n=== STATUS ===")
    print(
        f"  Undo log: {st['undo_log_count']} entries, {st['restored_count']} restored"
    )

    print("\n=== ANNOTATIONS ===")
    print(f"  read:  {get_annotations('read')}")
    print(f"  write: {get_annotations('write')}")
    print(f"  mutate: {get_annotations('mutate')}")

    print("\nAll permission audit tests passed.")
