#!/usr/bin/env python3
"""
DAG State File Manager — atomic file-based state passing between DAG nodes.

Provides DAGStateManager for reading, writing, merging, and clearing per-node
state files stored in .memory/dag-states/{dag_id}/. Uses atomic writes via
temp+rename and advisory lock files to prevent corruption.

Usage:
    from state_file_manager import DAGStateManager
    mgr = DAGStateManager("dag-abc-123")
    mgr.write_state("node-1", {"output": {"summary": "done"}})
    state = mgr.read_state("node-1")
"""

import json, os, time, uuid, threading
from datetime import datetime, timezone
from typing import Optional, Any

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DAG_STATES_ROOT = os.path.join(PROJECT_ROOT, ".memory", "dag-states")


def now_iso() -> str:
    """ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: str) -> str:
    """Create directory if it doesn't exist, return path."""
    os.makedirs(path, exist_ok=True)
    return path


class DAGStateManager:
    """
    Manages per-node state files for DAG pipeline execution.

    Each DAG execution gets a directory under .memory/dag-states/{dag_id}/.
    Each node within that DAG gets a state JSON file: {node_id}.state.json.
    Lock files ({node_id}.lock) provide advisory locking for concurrent access.

    State files follow the state-contract-v1 schema:
        { dag_id, phase, node_id, input, output, metadata }
    """

    def __init__(self, dag_id: str, base_dir: Optional[str] = None):
        """
        Initialize state manager for a DAG execution.

        Args:
            dag_id: Unique identifier for this DAG execution.
            base_dir: Override base directory (default: .memory/dag-states/).
        """
        self.dag_id = dag_id
        self.base_dir = base_dir or DAG_STATES_ROOT
        self.state_dir = _ensure_dir(os.path.join(self.base_dir, dag_id))
        self._lock = threading.Lock()

    # ── Path Helpers ────────────────────────────────────────

    def _state_path(self, node_id: str) -> str:
        """Path to a node's state JSON file."""
        return os.path.join(self.state_dir, f"{node_id}.state.json")

    def _lock_path(self, node_id: str) -> str:
        """Path to a node's advisory lock file."""
        return os.path.join(self.state_dir, f"{node_id}.lock")

    def _temp_path(self, node_id: str) -> str:
        """Path for temporary write before atomic rename."""
        return os.path.join(self.state_dir, f".{node_id}.{uuid.uuid4().hex[:8]}.tmp")

    # ── Locking ─────────────────────────────────────────────

    def acquire_lock(self, node_id: str, timeout: float = 10.0) -> bool:
        """
        Acquire an advisory lock for a node. Blocks up to timeout seconds.

        Args:
            node_id: Node to lock.
            timeout: Max seconds to wait for the lock.

        Returns:
            True if lock acquired, False if timeout.
        """
        lock_file = self._lock_path(node_id)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()}:{threading.get_ident()}".encode())
                os.close(fd)
                return True
            except FileExistsError:
                # Check if stale (>30s old)
                try:
                    mtime = os.path.getmtime(lock_file)
                    if time.time() - mtime > 30:
                        os.unlink(lock_file)
                        continue
                except OSError:
                    pass
                time.sleep(0.1)
        return False

    def release_lock(self, node_id: str) -> None:
        """Release an advisory lock for a node."""
        lock_file = self._lock_path(node_id)
        try:
            if os.path.isfile(lock_file):
                os.unlink(lock_file)
        except OSError:
            pass

    # ── CRUD Operations ─────────────────────────────────────

    def write_state(self, node_id: str, data: dict) -> str:
        """
        Atomically write a state file for a node using temp+rename.

        Args:
            node_id: Node identifier.
            data: State dict (should conform to state-contract-v1 schema).

        Returns:
            Path to the written state file.

        Raises:
            IOError: If write fails.
        """
        data.setdefault("dag_id", self.dag_id)
        data.setdefault("node_id", node_id)
        data.setdefault("phase", "completed")
        data.setdefault("input", {})
        data.setdefault("output", {})
        data.setdefault("metadata", {})
        data["metadata"]["updated_at"] = now_iso()

        temp = self._temp_path(node_id)
        final = self._state_path(node_id)

        with self._lock:
            try:
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(temp, final)
            except Exception:
                try:
                    if os.path.isfile(temp):
                        os.unlink(temp)
                except OSError:
                    pass
                raise
        return final

    def read_state(self, node_id: str) -> Optional[dict]:
        """
        Read a node's state file.

        Args:
            node_id: Node identifier.

        Returns:
            State dict, or None if the file doesn't exist.
        """
        path = self._state_path(node_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            return {"dag_id": self.dag_id, "node_id": node_id, "phase": "failed",
                    "input": {}, "output": {},
                    "metadata": {"errors": [{"type": "json_decode", "message": str(e)}],
                                 "updated_at": now_iso()}}

    def delete_state(self, node_id: str) -> bool:
        """
        Delete a node's state file and lock.

        Args:
            node_id: Node identifier.

        Returns:
            True if deleted, False if not found.
        """
        deleted = False
        for path in [self._state_path(node_id), self._lock_path(node_id)]:
            try:
                if os.path.isfile(path):
                    os.unlink(path)
                    deleted = True
            except OSError:
                pass
        return deleted

    def list_states(self) -> list[dict]:
        """
        List all node states for this DAG.

        Returns:
            List of state dicts sorted by node_id.
        """
        states = []
        if not os.path.isdir(self.state_dir):
            return states
        for fname in sorted(os.listdir(self.state_dir)):
            if fname.endswith(".state.json"):
                node_id = fname[:-len(".state.json")]
                state = self.read_state(node_id)
                if state:
                    states.append(state)
        return states

    def clear_states(self) -> int:
        """
        Clear all state files for this DAG.

        Returns:
            Number of files removed.
        """
        count = 0
        if not os.path.isdir(self.state_dir):
            return count
        for fname in os.listdir(self.state_dir):
            fpath = os.path.join(self.state_dir, fname)
            try:
                if fname.endswith((".state.json", ".lock")) or fname.startswith("."):
                    os.unlink(fpath)
                    count += 1
            except OSError:
                pass
        return count

    def state_exists(self, node_id: str) -> bool:
        """Check if a state file exists for the given node."""
        return os.path.isfile(self._state_path(node_id))

    def get_phase(self, node_id: str) -> str:
        """Get the phase of a node, or 'unknown' if no state exists."""
        state = self.read_state(node_id)
        return state.get("phase", "unknown") if state else "unknown"

    # ── Merge Operations ────────────────────────────────────

    def merge_outputs(self, node_ids: list[str], strategy: str = "deep_merge") -> dict:
        """
        Merge outputs from multiple upstream nodes into a single dict.

        Args:
            node_ids: List of upstream node IDs to merge.
            strategy: Merge strategy — deep_merge, concat, pick_first, pick_last.

        Returns:
            Merged output dict.
        """
        states = []
        for nid in node_ids:
            s = self.read_state(nid)
            if s and s.get("phase") in ("completed", "skipped"):
                states.append(s)

        if not states:
            return {}

        if strategy == "pick_first":
            return states[0].get("output", {})
        if strategy == "pick_last":
            return states[-1].get("output", {})

        merged: dict = {}
        if strategy == "deep_merge":
            for s in states:
                self._deep_merge(merged, s.get("output", {}))
        elif strategy == "concat":
            for s in states:
                out = s.get("output", {})
                for k, v in out.items():
                    if k not in merged:
                        merged[k] = []
                    if isinstance(v, list):
                        merged[k].extend(v)
                    else:
                        merged[k].append(v)
        else:
            # fallback: take all, last writer wins per top-level key
            for s in states:
                merged.update(s.get("output", {}))

        return merged

    @staticmethod
    def _deep_merge(target: dict, source: dict) -> None:
        """Recursively merge source into target (mutates target)."""
        for key, val in source.items():
            if key in target:
                if isinstance(target[key], dict) and isinstance(val, dict):
                    DAGStateManager._deep_merge(target[key], val)
                elif isinstance(target[key], list) and isinstance(val, list):
                    target[key].extend(val)
                else:
                    target[key] = val
            else:
                target[key] = val

    # ── Initialization ──────────────────────────────────────

    def init_node_state(self, node_id: str, input_data: dict, temperature: float = 0.7) -> dict:
        """
        Create an initial 'pending' state for a node.

        Args:
            node_id: Node identifier.
            input_data: Input data for the node.
            temperature: Temperature setting.

        Returns:
            The created state dict.
        """
        state = {
            "dag_id": self.dag_id,
            "phase": "pending",
            "node_id": node_id,
            "input": input_data,
            "output": {},
            "metadata": {
                "started_at": None,
                "updated_at": now_iso(),
                "completed_at": None,
                "errors": [],
                "warnings": [],
                "duration_ms": None,
                "retry_count": 0,
                "temperature": temperature,
                "node_version": "1.0.0",
            },
        }
        self.write_state(node_id, state)
        return state

    def mark_running(self, node_id: str) -> dict:
        """Mark a node as running (set phase and started_at)."""
        state = self.read_state(node_id) or self.init_node_state(node_id, {})
        state["phase"] = "running"
        state["metadata"]["started_at"] = now_iso()
        state["metadata"]["updated_at"] = now_iso()
        self.write_state(node_id, state)
        return state

    def mark_completed(self, node_id: str, output: dict, duration_ms: Optional[float] = None) -> dict:
        """Mark a node as completed with its output."""
        state = self.read_state(node_id) or {}
        state["phase"] = "completed"
        state["output"] = output
        state["metadata"]["completed_at"] = now_iso()
        state["metadata"]["updated_at"] = now_iso()
        if duration_ms is not None:
            state["metadata"]["duration_ms"] = duration_ms
        self.write_state(node_id, state)
        return state

    def mark_failed(self, node_id: str, errors: list, duration_ms: Optional[float] = None) -> dict:
        """Mark a node as failed with error details."""
        state = self.read_state(node_id) or {}
        state["phase"] = "failed"
        state["metadata"]["errors"] = errors
        state["metadata"]["completed_at"] = now_iso()
        state["metadata"]["updated_at"] = now_iso()
        if duration_ms is not None:
            state["metadata"]["duration_ms"] = duration_ms
        self.write_state(node_id, state)
        return state

    def mark_skipped(self, node_id: str, reason: str = "") -> dict:
        """Mark a node as skipped (e.g., conditional edge not taken)."""
        state = self.read_state(node_id) or {}
        state["phase"] = "skipped"
        state["metadata"]["warnings"] = state["metadata"].get("warnings", []) + [reason]
        state["metadata"]["updated_at"] = now_iso()
        self.write_state(node_id, state)
        return state

    # ── Heartbeat ───────────────────────────────────────────

    def write_heartbeat(self, node_id: str, step: str = "") -> None:
        """
        Write a lightweight heartbeat file to show a node is alive.

        Args:
            node_id: Node identifier.
            step: Current step description.
        """
        hb = {
            "dag_id": self.dag_id,
            "node_id": node_id,
            "step": step,
            "timestamp": time.time(),
            "iso": now_iso(),
        }
        hb_path = os.path.join(self.state_dir, f"{node_id}.heartbeat.json")
        temp = self._temp_path(f"{node_id}.hb")
        try:
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(hb, f)
            os.replace(temp, hb_path)
        except Exception:
            try:
                if os.path.isfile(temp):
                    os.unlink(temp)
            except OSError:
                pass

    def read_heartbeat(self, node_id: str) -> Optional[dict]:
        """Read a node's heartbeat file."""
        hb_path = os.path.join(self.state_dir, f"{node_id}.heartbeat.json")
        try:
            with open(hb_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None


# ── CLI Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DAG State File Manager CLI")
    parser.add_argument("--dag-id", type=str, required=True, help="DAG execution ID")
    parser.add_argument("--action", type=str, required=True,
                        choices=["read", "write", "list", "clear", "merge", "status"])
    parser.add_argument("--node-id", type=str, help="Node ID for read/write actions")
    parser.add_argument("--data", type=str, help="JSON string for write action")
    parser.add_argument("--strategy", type=str, default="deep_merge",
                        choices=["deep_merge", "concat", "pick_first", "pick_last"])
    args = parser.parse_args()

    mgr = DAGStateManager(args.dag_id)

    if args.action == "read":
        if not args.node_id:
            print("ERROR: --node-id required for read action")
            sys.exit(1)
        state = mgr.read_state(args.node_id)
        print(json.dumps(state, indent=2) if state else "null")

    elif args.action == "write":
        if not args.node_id or not args.data:
            print("ERROR: --node-id and --data required for write action")
            sys.exit(1)
        data = json.loads(args.data)
        path = mgr.write_state(args.node_id, data)
        print(json.dumps({"path": path, "status": "written"}))

    elif args.action == "list":
        states = mgr.list_states()
        print(json.dumps(states, indent=2))

    elif args.action == "clear":
        count = mgr.clear_states()
        print(json.dumps({"cleared": count}))

    elif args.action == "merge":
        if not args.node_id:
            print("ERROR: --node-id (comma-separated) required for merge action")
            sys.exit(1)
        node_ids = [n.strip() for n in args.node_id.split(",")]
        merged = mgr.merge_outputs(node_ids, args.strategy)
        print(json.dumps(merged, indent=2))

    elif args.action == "status":
        states = mgr.list_states()
        summary = {
            "dag_id": args.dag_id,
            "total_nodes": len(states),
            "phases": {},
            "nodes": [{"id": s["node_id"], "phase": s.get("phase")} for s in states],
        }
        for s in states:
            p = s.get("phase", "unknown")
            summary["phases"][p] = summary["phases"].get(p, 0) + 1
        print(json.dumps(summary, indent=2))
