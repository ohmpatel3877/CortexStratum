"""
compress_context.py — Deterministic context compression for long pipelines (stdlib only).

Goal: when a DAG run or session accumulates large intermediate state, summarize/compact
old context so downstream nodes and the consuming model don't blow the context window,
while PRESERVING decision-critical info.

What is KEPT vs DROPPED (no LLM call — purely heuristic, reproducible):
  KEPT  : errors, verify-gate failures, renudge signals, decisions, task status, structured
          output fields (keys), and the most recent N nodes verbatim (rolling window).
  DROPPED: raw stdout/stderr of older nodes above a byte threshold (replaced by a one-line
          summary: byte count + first/last significant line).

This is a real, lossy-but-safe compaction. If a caller needs semantic summarization, they
delegate to a designated model tool — this module only does heuristic trimming.
"""

from __future__ import annotations
import re
from typing import Optional

# Keep any output field whose key signals decision-critical content.
CRITICAL_KEYS = (
    "error", "errors", "verification", "verdict", "decision", "gate", "drift",
    "renudge", "status", "changed_keys", "score", "returncode", "signal",
)
RAW_FIELDS = ("stdout", "stderr", "raw", "logs", "trace")
DEFAULT_WINDOW = 3          # most-recent N nodes kept verbatim
DEFAULT_RAW_LIMIT = 2000    # bytes; above this, older-node raw output is trimmed


def _is_critical(key: str) -> bool:
    k = key.lower()
    return any(c in k for c in CRITICAL_KEYS)


def _trim_raw(text: str, limit: int) -> str:
    """Trim a raw blob: keep head + tail if over limit, else return as-is."""
    if len(text) <= limit:
        return text
    head = text[: limit // 2].rstrip()
    tail = text[-limit // 2:].rstrip()
    return f"{head}\n…[{len(text) - limit} bytes dropped]…\n{tail}"


def compress_node_state(state: dict, is_recent: bool, raw_limit: int = DEFAULT_RAW_LIMIT) -> dict:
    """Compress one node's state dict. Recent nodes are returned unchanged."""
    if is_recent:
        return state
    out = dict(state)
    # Trim raw blobs at top level AND inside the nested 'output' dict (real node states nest them)
    for container in (out, out.get("output") if isinstance(out.get("output"), dict) else None):
        if not isinstance(container, dict):
            continue
        for fld in RAW_FIELDS:
            if fld in container and isinstance(container[fld], str):
                container[fld] = _trim_raw(container[fld], raw_limit)
    # Drop verbose non-critical data subkeys in older nodes
    if isinstance(out.get("data"), dict):
        out["data"] = {k: v for k, v in out["data"].items() if _is_critical(k)}
    return out


def compress_history(history: list[dict], window: int = DEFAULT_WINDOW,
                    raw_limit: int = DEFAULT_RAW_LIMIT) -> list[dict]:
    """Compress a list of node states. Keep the last `window` verbatim; trim the rest.

    Returns a new list (does not mutate input). Each item gains a `_compressed` flag.
    """
    if not history:
        return []
    recent = set(range(max(0, len(history) - window), len(history)))
    out = []
    for i, node in enumerate(history):
        is_recent = i in recent
        compressed = compress_node_state(node, is_recent, raw_limit)
        compressed = dict(compressed)
        compressed["_compressed"] = (not is_recent)
        out.append(compressed)
    return out


def summarize_text(text: str, max_lines: int = 8) -> str:
    """Heuristic line-summary: drop blank/verbose lines, keep signal lines."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not re.fullmatch(r"[-=#*_ ]{4,}", ln)]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    head = lines[: max_lines // 2]
    tail = lines[-max_lines // 2:]
    return "\n".join(head + [f"…[{len(lines) - max_lines} lines dropped]…"] + tail)
