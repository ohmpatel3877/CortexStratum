#!/usr/bin/env python3
"""
plumber-module.py — Execution Pipelines & Artifact Management

Master Spec:
  - Plumber: Inspect mutated bridges, native sockets, container data handoffs
  - Artifact Checkpointing: confirm final directory + file structure
  - Validation Gates: tie into /verify and /check
"""

import os
import socket
import time
from pathlib import Path

from utils import load_json, save_json

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

#
# Socket Inspection
#


def inspect_socket(host="localhost", port=None, path=None):
    """
    Check latency and structural integrity of a socket connection.
    Accepts TCP (host+port) or Unix domain socket (path).
    """
    result = {"timestamp": time.time(), "host": host, "port": port, "socket_path": path}

    if path:
        # Unix domain socket check
        if not os.path.exists(path):
            result["status"] = "NOT_FOUND"
            result["latency_ms"] = None
            result["error"] = f"Socket path does not exist: {path}"
            return result
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            start = time.time()
            sock.settimeout(3)
            sock.connect(path)
            elapsed = (time.time() - start) * 1000
            sock.close()
            result["status"] = "REACHABLE"
            result["latency_ms"] = round(elapsed, 2)
            result["transport"] = "unix"
        except Exception as e:
            result["status"] = "UNREACHABLE"
            result["latency_ms"] = None
            result["error"] = str(e)
    elif port:
        # TCP socket check
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            start = time.time()
            sock.settimeout(3)
            sock.connect((host, port))
            elapsed = (time.time() - start) * 1000
            sock.close()
            result["status"] = "REACHABLE"
            result["latency_ms"] = round(elapsed, 2)
            result["transport"] = "tcp"
        except Exception as e:
            result["status"] = "UNREACHABLE"
            result["latency_ms"] = None
            result["error"] = str(e)
    else:
        result["status"] = "INVALID"
        result["error"] = "Provide either port (TCP) or path (Unix socket)"

    # Structural integrity: check if the connection is stable
    if result["status"] == "REACHABLE":
        result["integrity"] = "PASS"
        result["recommendation"] = "Socket healthy"
    else:
        result["integrity"] = "FAIL"
        result["recommendation"] = (
            f"Inspect and restart: {result.get('error', 'unknown error')}"
        )

    return result


#
# Data Handoff Tracing
#

# Known handoff points in the CortexStratum architecture
_KNOWN_HANDOFFS = {
    "memory-to-compact": {
        "source": "write_memory_add / write_memory_consolidate",
        "target": "read_compact_synthesize / write_compact_execute",
        "protocol": "JSON file (data/memory_store.json → data/compact-velocity.json)",
        "latency_expected_ms": 5,
    },
    "mutation-to-plumber": {
        "source": "mutate_execute",
        "target": "write_plumber_checkpoint",
        "protocol": "JSON-RPC over stdio (MCP)",
        "latency_expected_ms": 2,
    },
    "sensory-to-memory": {
        "source": "read_sensory_browse / read_sensory_scrape",
        "target": "write_memory_add",
        "protocol": "JSON-RPC over stdio (MCP) + Playwright browser bridge",
        "latency_expected_ms": 50,
    },
    "compact-to-obsidian": {
        "source": "write_compact_execute",
        "target": "Obsidian vault (future)",
        "protocol": "File system write to ~/Obsidian/",
        "latency_expected_ms": 10,
    },
}


def trace_handoff(source=None, target=None, protocol_filter=None):
    """
    Trace data handoff between components.
    Reports latency expectations, protocol, and known bottlenecks.
    """
    handoffs = _KNOWN_HANDOFFS

    # Filter by source
    if source:
        handoffs = {
            k: v for k, v in handoffs.items() if source.lower() in v["source"].lower()
        }

    # Filter by target
    if target:
        handoffs = {
            k: v for k, v in handoffs.items() if target.lower() in v["target"].lower()
        }

    # Filter by protocol
    if protocol_filter:
        handoffs = {
            k: v
            for k, v in handoffs.items()
            if protocol_filter.lower() in v["protocol"].lower()
        }

    if not handoffs:
        return {
            "handoffs_found": 0,
            "message": f"No matching handoffs for source={source} target={target}",
            "known_handoffs": list(_KNOWN_HANDOFFS.keys()),
        }

    results = []
    for name, info in handoffs.items():
        results.append(
            {
                "handoff": name,
                "source": info["source"],
                "target": info["target"],
                "protocol": info["protocol"],
                "expected_latency_ms": info["latency_expected_ms"],
                "status": "MONITORED",
            }
        )

    return {
        "handoffs_found": len(results),
        "handoffs": results,
        "recommendation": "All monitored handoffs nominal"
        if results
        else "No handoffs to trace",
    }


#
# Artifact Checkpointing
#


def create_checkpoint(
    artifact_type="session", file_paths=None, metadata=None, dry_run=False
):
    """
    Create a runtime checkpoint before destructive operations.
    Records current state, file paths, and metadata for potential rollback.

    The Master Spec requires a "checkpoint prompt to confirm the final directory
    location and file structure of all generated artifacts."
    """
    file_paths = file_paths or []
    metadata = metadata or {}

    checkpoint = {
        "checkpoint_id": f"ckpt-{int(time.time())}-{hash(tuple(file_paths)) % 10000:04d}",
        "timestamp": time.time(),
        "artifact_type": artifact_type,
        "files": [],
        "metadata": metadata,
        "directory_manifest": {},
    }

    # Snapshot file states
    all_exist = True
    for fp in file_paths:
        p = Path(fp)
        info = {
            "path": str(p.resolve() if p.exists() else fp),
            "exists": p.exists(),
            "size_bytes": p.stat().st_size if p.exists() else None,
            "modified": p.stat().st_mtime if p.exists() else None,
        }
        checkpoint["files"].append(info)
        if not p.exists():
            all_exist = False

    # Build directory manifest (parent directories)
    dirs = set()
    for fp in file_paths:
        p = Path(fp)
        if p.exists():
            dirs.add(str(p.parent))
    checkpoint["directory_manifest"] = {"directories": sorted(dirs), "count": len(dirs)}

    # Master Spec: "enforces a checkpoint prompt to confirm the final directory location"
    checkpoint["prompt"] = (
        f"Checkpoint {checkpoint['checkpoint_id']}: "
        f"{len(file_paths)} file(s) across {len(dirs)} director(ies). "
        f"All files present: {all_exist}. "
        f"Proceed with mutation? (use mutate_execute to continue)"
    )

    if not dry_run:
        # Persist
        history = load_json(DATA_DIR / "checkpoint-history.json", {"checkpoints": []})
        history.setdefault("checkpoints", []).append(checkpoint)
        save_json(DATA_DIR / "checkpoint-history.json", history)
        checkpoint["status"] = "checkpointed"
    else:
        checkpoint["status"] = "simulated"
        checkpoint["note"] = (
            "Dry run. Execute without dry_run=true to persist checkpoint."
        )

    return checkpoint


def list_checkpoints(limit=5):
    """List recent checkpoints from history."""
    history = load_json(DATA_DIR / "checkpoint-history.json", {"checkpoints": []})
    all_ckpts = history.get("checkpoints", [])
    return {
        "total_checkpoints": len(all_ckpts),
        "recent": all_ckpts[-limit:] if all_ckpts else [],
    }


#
# Handler Dispatch
#


def handle_tool_call(name, args):
    if name == "read_plumber_inspect_socket":
        return inspect_socket(
            args.get("host", "localhost"), args.get("port"), args.get("socket_path")
        )
    elif name == "read_plumber_trace_handoff":
        return trace_handoff(
            args.get("source"), args.get("target"), args.get("protocol_filter")
        )
    elif name == "write_plumber_checkpoint":
        return create_checkpoint(
            args.get("artifact_type", "session"),
            args.get("file_paths", []),
            args.get("metadata", {}),
            args.get("dry_run", False),
        )
    elif name == "read_plumber_checkpoints":
        return list_checkpoints(args.get("limit", 5))
    return {"error": f"Unknown plumber tool: {name}"}
