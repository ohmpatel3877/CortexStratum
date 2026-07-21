#!/usr/bin/env python3
"""
Data Lineage — track which tool calls produced which MLM entries with quality scoring.

Links every memory write to its source tool and session. Quality score =
access_count × limbic_reinforcement × recency_factor.

Stored in data/lineage.json
"""

import json
import threading
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LINEAGE_FILE = DATA_DIR / "lineage.json"


class LineageTracker:
    """Track lineage of memory entries: source tool, session, quality score."""

    def __init__(self):
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}  # mem_id → lineage info
        self._load()

    def _load(self):
        try:
            if LINEAGE_FILE.exists():
                self._entries = json.loads(LINEAGE_FILE.read_text())
        except Exception:
            pass

    def _save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            LINEAGE_FILE.write_text(json.dumps(self._entries, indent=2, default=str))
        except Exception:
            pass

    def track(self, mem_id: str, source_tool: str, source_session: str = "",
              content: str = "", tags: str = "") -> dict:
        """Record a new memory entry's lineage."""
        with self._lock:
            self._entries[mem_id] = {
                "mem_id": mem_id,
                "source_tool": source_tool,
                "source_session": source_session,
                "content_preview": content[:100],
                "tags": tags,
                "created_at": time.time(),
                "access_count": 0,
                "quality_score": 0.5,  # start neutral
                "limbic_reinforcement": 0.0,
            }
            self._save()
        return self._entries[mem_id]

    def record_access(self, mem_id: str) -> dict | None:
        """Record an access to a memory entry, updating quality score."""
        with self._lock:
            entry = self._entries.get(mem_id)
            if entry is None:
                return None
            entry["access_count"] += 1
            # Quality = access_count × recency × reinforcement
            age_hours = (time.time() - entry["created_at"]) / 3600
            recency = max(0.1, 1.0 - age_hours / 168)  # 7-day half-life
            reinforcement = entry.get("limbic_reinforcement", 0.0) + 0.1
            entry["limbic_reinforcement"] = min(reinforcement, 1.0)
            entry["quality_score"] = round(
                (entry["access_count"] ** 0.5) * recency * (0.5 + entry["limbic_reinforcement"] / 2),
                3,
            )
            self._save()
        return entry

    def set_reinforcement(self, mem_id: str, value: float):
        """Set limbic reinforcement value for a memory entry."""
        with self._lock:
            entry = self._entries.get(mem_id)
            if entry:
                entry["limbic_reinforcement"] = max(0.0, min(value, 1.0))
                self._save()

    def query(self, tool: str = "", session: str = "",
              min_quality: float = 0.0, limit: int = 50) -> list[dict]:
        """Query lineage entries, sorted by quality score descending."""
        results = []
        with self._lock:
            for e in self._entries.values():
                if tool and tool.lower() not in e.get("source_tool", "").lower():
                    continue
                if session and session not in e.get("source_session", ""):
                    continue
                if e.get("quality_score", 0) < min_quality:
                    continue
                results.append(dict(e))

        results.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        return results[:limit]

    def status(self) -> dict:
        with self._lock:
            scored = sum(1 for e in self._entries.values() if e.get("quality_score", 0) >= 0.5)
            return {
                "total_tracked": len(self._entries),
                "high_quality": scored,
                "source_tools": list(set(e.get("source_tool", "") for e in self._entries.values())),
                "sessions": list(set(e.get("source_session", "") for e in self._entries.values())),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_LINEAGE: LineageTracker | None = None


def get_lineage() -> LineageTracker:
    global _LINEAGE
    if _LINEAGE is None:
        _LINEAGE = LineageTracker()
    return _LINEAGE


# ---------------------------------------------------------------------------
# MCP Tool definitions & handler
# ---------------------------------------------------------------------------

LINEAGE_TOOLS = [
    {
        "name": "read_lineage_query",
        "description": " READ — Query data lineage by source tool, session, or minimum quality score.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "description": "Filter by source tool"},
                "session": {"type": "string", "description": "Filter by source session"},
                "min_quality": {"type": "number", "description": "Minimum quality score (0-1)"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": [],
        },
    },
    {
        "name": "read_lineage_status",
        "description": " READ — View lineage tracker status: entries, quality stats, tracked tools.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_lineage_track",
        "description": " WRITE — Manually track a memory entry's lineage (used by middleware auto-track).",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mem_id": {"type": "string"},
                "source_tool": {"type": "string"},
                "source_session": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "string"},
            },
            "required": ["mem_id", "source_tool"],
        },
    },
]


def handle_tool_call(name: str, args: dict) -> dict:
    lg = get_lineage()
    if name == "read_lineage_query":
        return {"content": [{"type": "text", "text": json.dumps(
            lg.query(
                tool=args.get("tool", ""),
                session=args.get("session", ""),
                min_quality=args.get("min_quality", 0.0),
                limit=args.get("limit", 50),
            ), indent=2)}]}
    elif name == "read_lineage_status":
        return {"content": [{"type": "text", "text": json.dumps(lg.status(), indent=2)}]}
    elif name == "write_lineage_track":
        return {"content": [{"type": "text", "text": json.dumps(lg.track(
            mem_id=args.get("mem_id", ""),
            source_tool=args.get("source_tool", ""),
            source_session=args.get("source_session", ""),
            content=args.get("content", ""),
            tags=args.get("tags", ""),
        ), indent=2)}]}
    msg = "Unknown lineage tool: " + str(name)
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}]}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Data Lineage Self-Test ===\n")

    # Use a temp file
    test_file = Path(__file__).resolve().parent.parent / "data" / "lineage-test.json"
    old_file = LINEAGE_FILE
    import sys
    sys.modules[__name__].LINEAGE_FILE = test_file

    lg = LineageTracker()

    # 1. Fresh
    s = lg.status()
    print(f"1. Fresh: {s['total_tracked']} tracked")
    assert s["total_tracked"] == 0

    # 2. Track entries
    lg.track("mem_1", "write_memory_add", "session_1", "Important fact about X", "core")
    lg.track("mem_2", "write_memory_add", "session_1", "Trivial detail", "noise")
    lg.track("mem_3", "write_compute_execute", "session_1", "Computed result: 42", "compute")
    s2 = lg.status()
    print(f"2. Tracked 3: {s2['total_tracked']}, tools={s2['source_tools']}")
    assert s2["total_tracked"] == 3
    assert "write_memory_add" in s2["source_tools"]

    # 3. Access tracking
    lg.record_access("mem_1")
    lg.record_access("mem_1")
    lg.record_access("mem_3")
    q = lg.query()
    print(f"3. After access: {len(q)} entries, top = mem_{q[0]['mem_id']} qual={q[0]['quality_score']}")
    assert q[0]["mem_id"] == "mem_1"  # most accessed
    assert q[0]["quality_score"] > q[2]["quality_score"]

    # 4. Query filters
    q2 = lg.query(tool="compute")
    print(f"4. Filter compute: {len(q2)} results")
    assert len(q2) == 1
    assert q2[0]["mem_id"] == "mem_3"

    q3 = lg.query(min_quality=0.1)
    print(f"5. Min quality 0.1: {len(q3)} results")
    assert len(q3) >= 1

    # Cleanup
    if test_file.exists():
        test_file.unlink()

    # Restore
    sys.modules[__name__].LINEAGE_FILE = old_file

    print("\nAll self-tests passed.")
