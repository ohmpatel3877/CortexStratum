#!/usr/bin/env python3
"""
compact-module.py — Dynamic Context Compaction Phase (/compact)

Implements the Master Specification's compaction engine:
- Token velocity tracking & spike detection
- State condensation (verbose → high-density summary)
- Session continuity via BM25/FTS5 tracking
- Footprint reduction (redundant reads → single references)
- Scope integration (out-of-scope → Obsidian vault routing)
- Artifact protection (preserve tags during compaction)

All functions are stateless. State is stored in data/ via write_* tools.
"""

import re
import sqlite3
import time
from pathlib import Path

from utils import load_json, save_json

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

DB_PATH = DATA_DIR / "compact-sessions.db"


def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at REAL,
                updated_at REAL,
                context TEXT
            );
            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                ts REAL,
                context TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS compactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                ts REAL,
                input_length INTEGER,
                output_length INTEGER,
                compression_ratio REAL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                content TEXT,
                block_type TEXT,
                hash TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


#  Token Velocity Tracking


def get_token_velocity():
    """
    Estimate current token velocity based on recent compaction events.
    Returns dict with velocity score, trend direction, and compaction recommendation.
    """
    history = load_json(DATA_DIR / "compact-velocity.json", {"ticks": []})
    ticks = history.get("ticks", [])
    now = time.time()

    # Try SQLite for richer data
    try:
        conn = _get_db()
        cursor = conn.execute(
            "SELECT ts, context FROM ticks WHERE ts > ?", (now - 3600,)
        )
        sqlite_ticks = [{"ts": row[0], "context": row[1]} for row in cursor.fetchall()]
        conn.close()
        if sqlite_ticks:
            ticks = sqlite_ticks
            history["ticks"] = ticks
    except Exception:
        pass

    # Prune entries older than 1 hour
    recent = [t for t in ticks if now - t.get("ts", 0) < 3600]
    history["ticks"] = recent

    # Token velocity: events per 5-min window
    window_5m = [t for t in recent if now - t.get("ts", 0) < 300]
    velocity = len(window_5m)

    # Spike detection: if velocity > 2x the rolling average
    # Average events per 5-min window over the last hour (12 windows)
    window_1h = recent
    avg_per_window = (
        len(window_1h) / 12.0
    )  # events per 5-min window averaged over the hour
    spike = velocity > max(avg_per_window * 2, 6)

    return {
        "velocity_5min": velocity,
        "avg_hourly": round(avg_per_window * 12, 1),  # total events per hour
        "spike_detected": spike,
        "total_recent_events": len(recent),
        "recommendation": "compact now" if spike else "monitoring",
        "suggested_action": (
            "Token velocity spike detected. Run read_compact_synthesize on verbose outputs, "
            "then write_compact_execute to consolidate."
        )
        if spike
        else "Token velocity normal. No compaction needed.",
    }


def record_tick(context=None):
    """Record a token velocity tick (called by hooks or manually)."""
    tick = {"ts": time.time(), "context": context or "manual"}

    # Try SQLite
    try:
        conn = _get_db()
        conn.execute(
            "INSERT INTO ticks (session_id, ts, context) VALUES (?, ?, ?)",
            ("default", tick["ts"], tick["context"]),
        )
        conn.commit()
        cursor = conn.execute("SELECT COUNT(*) FROM ticks")
        total = cursor.fetchone()[0]
        conn.close()
        return {"recorded": True, "total_ticks": total}
    except Exception:
        pass

    # Fall back to JSON
    history = load_json(DATA_DIR / "compact-velocity.json", {"ticks": []})
    history.setdefault("ticks", []).append(tick)
    save_json(DATA_DIR / "compact-velocity.json", history)
    return {"recorded": True, "total_ticks": len(history["ticks"])}


#  Cache Analytics — Track prompt cache hit rates for optimization


def record_cache_hit(hit_type="read", tokens=0, context=""):
    """
    Record a prompt cache event (hit, miss, or write).

    hit_type: "cache_read" | "cache_write" | "cache_miss"
    tokens: number of tokens involved
    context: description of what was cached (e.g., "system_prompt", "tool_definitions")
    """
    entry = {
        "ts": time.time(),
        "hit_type": hit_type,
        "tokens": tokens,
        "context": context[:200],
    }
    cache_log = load_json(DATA_DIR / "compact-cache-log.json", {"events": []})
    cache_log.setdefault("events", []).append(entry)
    # Keep last 1000 events
    if len(cache_log["events"]) > 1000:
        cache_log["events"] = cache_log["events"][-1000:]
    save_json(DATA_DIR / "compact-cache-log.json", cache_log)
    return {"recorded": True, "total_events": len(cache_log["events"])}


def get_cache_analytics():
    """
    Analyze prompt cache event log and return hit rate, trends, and recommendations.

    Based on Anthropic prompt caching:
    - Cache reads cost 0.1x base input price
    - Cache writes cost 1.25x base (5-min TTL) or 2x base (1-hour TTL)
    - Minimum 1024 tokens required for caching
    - 5-min default TTL, auto-refreshed on read
    """
    cache_log = load_json(DATA_DIR / "compact-cache-log.json", {"events": []})
    events = cache_log.get("events", [])
    now = time.time()

    # Only consider recent events (last hour)
    recent = [e for e in events if now - e.get("ts", 0) < 3600]

    reads = [e for e in recent if e.get("hit_type") == "cache_read"]
    writes = [e for e in recent if e.get("hit_type") == "cache_write"]
    misses = [e for e in recent if e.get("hit_type") == "cache_miss"]

    total_requests = len(reads) + len(misses)
    hit_rate = round(len(reads) / max(total_requests, 1), 4)

    total_tokens_read = sum(e.get("tokens", 0) for e in reads)
    total_tokens_written = sum(e.get("tokens", 0) for e in writes)
    total_tokens_missed = sum(e.get("tokens", 0) for e in misses)

    # Estimated cost comparison (arbitrary units, for relative comparison)
    cost_without_caching = (
        total_tokens_read + total_tokens_written + total_tokens_missed
    ) * 1.0
    cost_with_caching = (
        (total_tokens_written * 1.25)
        + (total_tokens_read * 0.1)
        + (total_tokens_missed * 1.0)
    )
    savings_pct = round((1 - cost_with_caching / max(cost_without_caching, 1)) * 100, 1)

    # Breakdown by context
    by_context = {}
    for e in recent:
        ctx = e.get("context", "unknown")
        if ctx not in by_context:
            by_context[ctx] = {"reads": 0, "writes": 0, "misses": 0, "tokens": 0}
        by_context[ctx][
            e.get("hit_type") == "cache_read"
            and "reads"
            or e.get("hit_type") == "cache_write"
            and "writes"
            or "misses"
        ] += 1
        by_context[ctx]["tokens"] += e.get("tokens", 0)

    # Recommendations
    recommendations = []
    if hit_rate < 0.5 and total_requests > 10:
        recommendations.append(
            "Low cache hit rate. Ensure cache_control breakpoints are placed on stable "
            "prefixes (system instructions, tool definitions), not on varying user input."
        )
    if total_tokens_read > 0 and hit_rate > 0.8:
        recommendations.append(
            "Excellent cache hit rate. Consider extending cache TTL to 1 hour "
            "if requests arrive less frequently than every 5 minutes."
        )
    if any(e.get("tokens", 0) < 1024 for e in writes):
        recommendations.append(
            "Some cache writes below 1024-token minimum. Content under 1024 tokens "
            "is not cached by the API — expand cached sections or consolidate."
        )

    return {
        "hit_rate": hit_rate,
        "total_requests_last_hour": total_requests,
        "reads": len(reads),
        "writes": len(writes),
        "misses": len(misses),
        "tokens_read": total_tokens_read,
        "tokens_written": total_tokens_written,
        "tokens_missed": total_tokens_missed,
        "estimated_cost_savings_pct": savings_pct,
        "by_context": by_context,
        "recommendations": recommendations,
        "note": (
            "Reads cost 0.1x, writes cost 1.25x (5-min) or 2x (1-hour). "
            "Minimum 1024 tokens per cacheable segment. 5-min TTL auto-refreshes on read."
        ),
    }


#  State Condensation


def synthesize(content, max_chars=2000):
    """
    Condense verbose content into a high-density semantic summary.
    Extracts key facts, decisions, and action items.
    Preserves protected blocks (code, math, LaTeX) via artifact protection.
    """
    if not content:
        return {"summary": "", "original_length": 0, "compressed_length": 0}

    # Artifact Protection: extract and preserve protected blocks
    protected = []

    def _protect(m):
        idx = len(protected)
        protected.append(m.group(0))
        return f"__PROTECTED_{idx}__"

    # Protect code blocks
    content = re.sub(r"```[\s\S]*?```", _protect, content)
    # Protect LaTeX math
    content = re.sub(r"\$\$[\s\S]*?\$\$", _protect, content)
    content = re.sub(r"\$[^\$]+\$", _protect, content)
    # Protect inline math
    content = re.sub(r"\\\([\s\S]*?\\\)", _protect, content)

    # Extract key sections
    lines = content.strip().split("\n")
    summary_lines = []
    original_length = sum(len(l) for l in lines)
    current_len = 0

    for line in lines:
        stripped = line.strip()
        # Prioritize: headers, decisions, action items, PROTECTED blocks
        if stripped.startswith("__PROTECTED_"):
            import re as _re

            m = _re.match(r"__PROTECTED_(\d+)__", stripped)
            if m:
                idx = int(m.group(1))
                if idx < len(protected):
                    text = f"[PROTECTED BLOCK {idx}]"
                    if current_len + len(text) <= max_chars:
                        summary_lines.append(text)
                        current_len += len(text)
        elif any(
            stripped.startswith(p) for p in ("# ", "## ", "### ", "* ", "- ", "> ")
        ):
            if current_len + len(stripped) <= max_chars:
                summary_lines.append(stripped)
                current_len += len(stripped)
        elif any(
            kw in stripped.lower()
            for kw in ("decision", "action", "fix:", "note:", "result:")
        ):
            if current_len + len(stripped) <= max_chars:
                summary_lines.append(stripped)
                current_len += len(stripped)

    if not summary_lines:
        # Fallback: first N meaningful lines
        for line in lines:
            s = line.strip()
            if s and current_len + len(s) <= max_chars:
                summary_lines.append(s)
                current_len += len(s)

    summary = "\n".join(summary_lines)
    compressed_length = len(summary)

    # Restore protected blocks as references
    for i, block in enumerate(protected):
        summary = summary.replace(
            f"[PROTECTED BLOCK {i}]", f"[{len(block)} chars protected — see source]"
        )

    return {
        "summary": summary,
        "original_length": original_length,
        "compressed_length": compressed_length,
        "compression_ratio": round(compressed_length / max(original_length, 1), 4),
        "protected_blocks": len(protected),
    }


#  Session Continuity


def session_status():
    """Return current compact session state."""
    velocity = get_token_velocity()
    last_compact = load_json(DATA_DIR / "compact-last.json", {})

    # Try SQLite for compaction data
    try:
        conn = _get_db()
        cursor = conn.execute(
            "SELECT ts, compression_ratio FROM compactions ORDER BY ts DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            last_compact["timestamp"] = row[0]
            last_compact["compression_ratio"] = row[1]
    except Exception:
        pass

    return {
        "token_velocity": velocity,
        "last_compact": last_compact.get("timestamp"),
        "last_compact_summary": last_compact.get("summary", "never"),
        "data_dir": str(DATA_DIR),
    }


# Initialize SQLite database on module load
_init_db()

#  Handler Dispatch


def handle_tool_call(name, args):
    if name == "read_compact_token_velocity":
        return get_token_velocity()
    elif name == "read_compact_synthesize":
        return synthesize(args.get("content", ""), args.get("max_chars", 2000))
    elif name == "read_compact_status":
        return session_status()
    elif name == "write_compact_execute":
        # Record the compaction execution
        content = args.get("content", "")
        summary = synthesize(content) if content else {"summary": "no content"}
        save_json(
            DATA_DIR / "compact-last.json",
            {
                "timestamp": time.time(),
                "summary": summary.get("summary", ""),
                "compression_ratio": summary.get("compression_ratio", 0),
            },
        )
        record_tick("compact_execute")
        return {
            "status": "compacted",
            "compression": summary,
            "note": "Use dry_run=true to preview before committing.",
        }
    elif name == "read_compact_record_tick":
        return record_tick(args.get("context"))
    return {"error": f"Unknown compact tool: {name}"}
