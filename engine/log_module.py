#!/usr/bin/env python3
"""
Structured Logging — JSON-line log with levels, search, and rotation.

Writes to data/logs/ by default. Each line is a JSON object with:
  ts, level, session_id, tool, message, duration_ms, error

Integrated with the server's _log() function and mid.py middleware.
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


# Default paths
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"

# Levels
LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}


class StructuredLog:
    """JSON-line structured log writer with level filtering."""

    def __init__(self, log_dir: str | Path | None = None):
        self._log_dir = Path(log_dir) if log_dir else LOG_DIR
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._session_id = self._generate_session_id()
        self._min_level = "DEBUG"  # filter: only log entries >= this level
        self._log_file = self._log_dir / f"session-{self._session_id}.jsonl"
        self._file = None
        self._total_logged = 0
        self._start_time = time.monotonic()

    def _generate_session_id(self) -> str:
        """Short session ID based on timestamp."""
        return datetime.now().strftime("%Y%m%d-%H%M%S-") + os.urandom(2).hex()

    def _get_file(self):
        """Lazy-open log file."""
        if self._file is None:
            self._file = open(self._log_dir / f"session-{self._session_id}.jsonl",
                              "a", encoding="utf-8")
        return self._file

    def log(self, level: str, message: str, tool: str = "",
            duration_ms: float | None = None, extra: dict | None = None):
        """Write a structured log entry if level meets threshold."""
        level = level.upper()
        if LEVELS.get(level, 0) < LEVELS.get(self._min_level, 0):
            return

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "session": self._session_id,
            "tool": tool,
            "message": message[:500],
        }
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 1)
        if extra:
            entry["extra"] = extra

        with self._lock:
            try:
                f = self._get_file()
                f.write(json.dumps(entry, default=str) + "\n")
                f.flush()
                self._total_logged += 1
            except Exception:
                pass  # don't crash on log write failure

    def info(self, msg: str, **kw):
        self.log("INFO", msg, **kw)

    def warn(self, msg: str, **kw):
        self.log("WARN", msg, **kw)

    def error(self, msg: str, **kw):
        self.log("ERROR", msg, **kw)

    def debug(self, msg: str, **kw):
        self.log("DEBUG", msg, **kw)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def set_level(self, level: str) -> dict:
        level = level.upper()
        if level not in LEVELS:
            return {"status": "error", "error": f"Invalid level: {level}. Valid: {list(LEVELS.keys())}"}
        self._min_level = level
        return {"status": "ok", "min_level": level, "session": self._session_id}

    def search(self, query: str = "", level: str = "", tool: str = "",
               limit: int = 50) -> list[dict]:
        """Search log entries. Returns newest first."""
        results = []
        log_path = self._log_dir / f"session-{self._session_id}.jsonl"
        if not log_path.exists():
            return results

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if query and query.lower() not in json.dumps(entry).lower():
                        continue
                    if level and entry.get("level", "").upper() != level.upper():
                        continue
                    if tool and tool.lower() not in entry.get("tool", "").lower():
                        continue
                    results.append(entry)
        except FileNotFoundError:
            pass

        results.reverse()  # newest first
        return results[:limit]

    def status(self) -> dict:
        log_path = self._log_dir / f"session-{self._session_id}.jsonl"
        size = log_path.stat().st_size if log_path.exists() else 0
        return {
            "session": self._session_id,
            "min_level": self._min_level,
            "total_logged": self._total_logged,
            "file_size_bytes": size,
            "file_path": str(log_path),
            "uptime_seconds": round(time.monotonic() - self._start_time, 1),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_LOG: StructuredLog | None = None


def get_log() -> StructuredLog:
    global _LOG
    if _LOG is None:
        _LOG = StructuredLog()
    return _LOG


# ---------------------------------------------------------------------------
# MCP Tool definitions & handler
# ---------------------------------------------------------------------------

LOG_TOOLS = [
    {
        "name": "read_log_search",
        "description": " READ — Search structured logs by keyword, level, or tool. Returns newest first.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword search across all log fields"},
                "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARN", "ERROR"]},
                "tool": {"type": "string", "description": "Filter by tool name (substring match)"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": [],
        },
    },
    {
        "name": "mutate_log_level",
        "description": " MUTATE — Change the minimum log level. Only entries at or above this level are written.",
        "permission": "mutate",
        "inputSchema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["DEBUG", "INFO", "WARN", "ERROR"],
                    "description": "Minimum log level",
                },
            },
            "required": ["level"],
        },
    },
    {
        "name": "read_log_status",
        "description": " READ — View log session status: level, entries logged, file size.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def handle_tool_call(name: str, args: dict) -> dict:
    lg = get_log()
    if name == "read_log_search":
        results = lg.search(
            query=args.get("query", ""),
            level=args.get("level", ""),
            tool=args.get("tool", ""),
            limit=args.get("limit", 50),
        )
        return {"content": [{"type": "text", "text": json.dumps({"count": len(results), "entries": results}, indent=2)}]}
    elif name == "mutate_log_level":
        return {"content": [{"type": "text", "text": json.dumps(lg.set_level(args.get("level", "INFO")))}]}
    elif name == "read_log_status":
        return {"content": [{"type": "text", "text": json.dumps(lg.status(), indent=2)}]}
    msg = "Unknown log tool: " + str(name)
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}]}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import tempfile

    print("=== Structured Log Self-Test ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        lg = StructuredLog(log_dir=tmpdir)

        # 1. Fresh
        s0 = lg.status()
        print(f"1. Fresh: session={s0['session'][:8]}..., level={s0['min_level']}, logged={s0['total_logged']}")
        assert s0["total_logged"] == 0
        assert s0["min_level"] == "DEBUG"

        # 2. Write entries
        lg.info("Server started", tool="tools-mcp-server")
        lg.warn("High memory usage", tool="compute_exec", extra={"mem_pct": 85})
        lg.error("Tool timed out", tool="some_tool", duration_ms=65000.0)
        lg.debug("Verbose detail", tool="read_mlm_status")

        s1 = lg.status()
        print(f"2. After 4 entries: logged={s1['total_logged']}, file_size={s1['file_size_bytes']}")
        assert s1["total_logged"] == 4

        # 3. Search
        r1 = lg.search(query="timed out")
        print(f"3. Search 'timed out': {len(r1)} results")
        assert len(r1) == 1
        assert r1[0]["level"] == "ERROR"

        r2 = lg.search(level="WARN")
        print(f"   Search WARN: {len(r2)} results")
        assert len(r2) == 1

        r3 = lg.search(tool="compute")
        print(f"   Search tool 'compute': {len(r3)} results")
        assert len(r3) == 1

        # 4. Level filter
        lg.set_level("WARN")
        lg.info("This should be filtered out", tool="test")
        s2 = lg.status()
        print(f"4. After level=WARN: logged={s2['total_logged']}")
        assert s2["total_logged"] == 4  # didn't increment

        # 5. Set back to DEBUG
        lg.set_level("DEBUG")
        lg.info("Back to debug", tool="test")
        s3 = lg.status()
        print(f"5. After level=DEBUG: logged={s3['total_logged']}")
        assert s3["total_logged"] == 5

        # Cleanup for Windows tempdir
        if lg._file:
            lg._file.close()

        print("\nAll self-tests passed.")
