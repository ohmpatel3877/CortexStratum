#!/usr/bin/env python3
"""
Working Memory Module — Prefrontal Cortex analog

A dedicated, fast-access scratchpad that holds the current session's active context.
Mirrors the PFC's ability to keep information "online" for immediate manipulation.

Characteristics:
  - In-memory dict (no disk I/O) — volatile, session-scoped
  - Max 50 items (configurable)
  - TTL-based decay — items expire after reaching their time-to-live
  - LRU-2D eviction — Least Recently Used, decay-aware
  - Full flush on server restart
"""

import json
import time
from typing import Any

DEFAULT_CAPACITY = 50
DEFAULT_TTL = 300  # 5 minutes


class WorkingMemory:
    """Volatile, session-scoped working memory store."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY, default_ttl: int = DEFAULT_TTL):
        self._capacity = capacity
        self._default_ttl = default_ttl
        self._store: dict[str, dict] = {}  # key → item

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, key: str, value: Any, importance: float = 0.5,
              ttl_seconds: int | None = None) -> dict:
        """Store an item in working memory.

        Args:
            key: Unique identifier within this session.
            value: The content to store (any JSON-serializable type).
            importance: 0.0–1.0, affects decay speed (higher = slower decay).
            ttl_seconds: Time-to-live in seconds. Defaults to module default.

        Returns:
            {"status": "ok", "key": key, "evicted": old_key or None}
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        now = time.time()

        # If key already exists, just update
        if key in self._store:
            self._store[key] = {
                "key": key,
                "value": value,
                "importance": max(0.0, min(1.0, importance)),
                "created_at": self._store[key]["created_at"],
                "last_access": now,
                "access_count": self._store[key]["access_count"] + 1,
                "ttl_seconds": max(10, ttl),
            }
            return {"status": "ok", "key": key, "evicted": None}

        # Evict if at capacity
        evicted = None
        if len(self._store) >= self._capacity:
            evicted = self._evict_one()

        self._store[key] = {
            "key": key,
            "value": value,
            "importance": max(0.0, min(1.0, importance)),
            "created_at": now,
            "last_access": now,
            "access_count": 0,
            "ttl_seconds": max(10, ttl),
        }
        return {"status": "ok", "key": key, "evicted": evicted}

    def recall(self, key: str) -> Any | None:
        """Fetch an item from working memory.

        Returns the value (not the metadata) if found and not expired,
        or None if missing/expired. Refreshes last_access on hit.
        """
        if key not in self._store:
            return None

        item = self._store[key]
        if self._is_expired(item):
            del self._store[key]
            return None

        item["last_access"] = time.time()
        item["access_count"] += 1
        return item["value"]

    def recall_metadata(self, key: str) -> dict | None:
        """Fetch an item with full metadata (for inspection tools)."""
        if key not in self._store:
            return None

        item = self._store[key]
        if self._is_expired(item):
            del self._store[key]
            return None

        item["last_access"] = time.time()
        item["access_count"] += 1
        return {
            "key": item["key"],
            "value": item["value"],
            "importance": item["importance"],
            "created_at": item["created_at"],
            "last_access": item["last_access"],
            "access_count": item["access_count"],
            "ttl_seconds": item["ttl_seconds"],
            "age_seconds": round(time.time() - item["created_at"], 1),
            "ttl_remaining": round(
                item["ttl_seconds"] - (time.time() - item["created_at"]), 1
            ),
        }

    def set_importance(self, key: str, importance: float) -> dict:
        """Adjust an item's importance mid-session. Higher = slower decay."""
        if key not in self._store:
            return {"status": "error", "error": f"Key not found: {key}"}
        self._store[key]["importance"] = max(0.0, min(1.0, importance))
        return {"status": "ok", "key": key, "importance": self._store[key]["importance"]}

    def clear(self, keep_keys: list[str] | None = None) -> dict:
        """Flush working memory.

        If keep_keys provided, only those survive (selective reset).
        """
        if keep_keys:
            survivors = {}
            for k in keep_keys:
                if k in self._store:
                    survivors[k] = self._store[k]
            removed = len(self._store) - len(survivors)
            self._store = survivors
            return {"status": "ok", "removed": removed, "kept": len(survivors)}
        else:
            removed = len(self._store)
            self._store.clear()
            return {"status": "ok", "removed": removed, "kept": 0}

    def status(self) -> dict:
        """Return current WM stats."""
        now = time.time()
        # Purge expired items lazily
        expired = [k for k, v in self._store.items() if self._is_expired(v)]
        for k in expired:
            del self._store[k]

        if not self._store:
            return {
                "item_count": 0,
                "capacity": self._capacity,
                "oldest_item_age": None,
                "most_active_key": None,
                "most_active_accesses": 0,
                "expired_purged": len(expired),
            }

        oldest = min(self._store.values(), key=lambda x: x["created_at"])
        most_active = max(self._store.values(), key=lambda x: x["access_count"])
        return {
            "item_count": len(self._store),
            "capacity": self._capacity,
            "oldest_item_age": round(now - oldest["created_at"], 1),
            "most_active_key": most_active["key"],
            "most_active_accesses": most_active["access_count"],
            "expired_purged": len(expired),
        }

    def list_keys(self) -> list[str]:
        """List all active (non-expired) keys."""
        # Purge expired while listing
        now = time.time()
        active = [k for k, v in self._store.items() if not self._is_expired(v)]
        expired = [k for k in self._store if k not in active]
        for k in expired:
            del self._store[k]
        return active

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_expired(self, item: dict) -> bool:
        age = time.time() - item["created_at"]
        return age > item["ttl_seconds"]

    def _evict_one(self) -> str | None:
        """Evict the lowest-value item (LRU-2D: Least Recently Used × Decay-aware).

        Score = (access_count + 1) / (age_seconds + 1) × importance
        Lower score = better eviction candidate.
        """
        if not self._store:
            return None
        now = time.time()
        # Purge expired first
        expired = [k for k, v in self._store.items() if self._is_expired(v)]
        if expired:
            k = expired[0]
            del self._store[k]
            return k

        def _score(item: dict) -> float:
            age = now - item["created_at"]
            return (item["access_count"] + 1) / (age + 1) * (item["importance"] + 0.1)

        worst = min(self._store.items(), key=lambda kv: _score(kv[1]))
        key = worst[0]
        del self._store[key]
        return key


# ---------------------------------------------------------------------------
# MCP Tool handlers
# ---------------------------------------------------------------------------

_WM: WorkingMemory | None = None


def _get_wm() -> WorkingMemory:
    global _WM
    if _WM is None:
        _WM = WorkingMemory()
    return _WM


def handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch WM-related MCP tool calls.

    Registered for prefixes: read_wm_*, write_wm_*, mutate_wm_*
    """
    wm = _get_wm()
    try:
        if name == "read_wm_status":
            return {"content": [{"type": "text", "text": json.dumps(wm.status(), indent=2)}]}

        elif name == "read_wm_recall":
            key = args.get("key", "")
            if not key:
                return {"content": [{"type": "text", "text": json.dumps({"error": "key is required"})}]}
            # Try recall_metadata first for detailed view, fall back to raw value
            detailed = args.get("detailed", False)
            if detailed:
                result = wm.recall_metadata(key)
            else:
                val = wm.recall(key)
                result = {"value": val} if val is not None else None
            if result is None:
                return {"content": [{"type": "text", "text": json.dumps({"error": "not_found", "key": key})}]}
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "write_wm_store":
            key = args.get("key", "")
            value = args.get("value")
            if not key or value is None:
                return {"content": [{"type": "text", "text": json.dumps({"error": "key and value are required"})}]}
            result = wm.store(
                key=key,
                value=value,
                importance=args.get("importance", 0.5),
                ttl_seconds=args.get("ttl_seconds"),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "write_wm_importance":
            key = args.get("key", "")
            importance = args.get("importance", 0.5)
            if not key:
                return {"content": [{"type": "text", "text": json.dumps({"error": "key is required"})}]}
            result = wm.set_importance(key, importance)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "mutate_wm_clear":
            keep_keys = args.get("keep_keys")
            result = wm.clear(keep_keys=keep_keys)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        else:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Unknown WM tool: {name}"})}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

WM_TOOLS = [
    {
        "name": "read_wm_status",
        "description": " READ — Show working memory stats: item count, capacity, oldest item, most active key, expired items purged.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_wm_recall",
        "description": " READ — Fetch an item from working memory by key. Returns null (not error) if key missing or expired. Set detailed=true for full metadata.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Item key to retrieve"},
                "detailed": {"type": "boolean", "description": "Return full metadata including TTL, access count, importance"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "write_wm_store",
        "description": " WRITE — Store an item in working memory. Displaces oldest/lowest-importance item if at capacity. Accepts dry_run=true.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Unique identifier within session"},
                "value": {"description": "Content to store (any JSON type)"},
                "importance": {"type": "number", "description": "0.0–1.0. Higher = slower decay.", "default": 0.5},
                "ttl_seconds": {"type": "integer", "description": "Time-to-live in seconds. Default 300 (5 min).", "default": 300},
                "dry_run": {"type": "boolean", "description": "Preview eviction without storing"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "write_wm_importance",
        "description": " WRITE — Adjust an item's importance mid-session. Higher importance = slower decay.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Item key"},
                "importance": {"type": "number", "description": "New importance value (0.0–1.0)"},
                "dry_run": {"type": "boolean"},
            },
            "required": ["key", "importance"],
        },
    },
    {
        "name": "mutate_wm_clear",
        "description": " MUTATE — Flush working memory. If keep_keys provided, only those survive. Accepts dry_run=true.",
        "permission": "mutate",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keep_keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional keys to preserve (selective reset)",
                },
                "dry_run": {"type": "boolean"},
            },
            "required": [],
        },
    },
]


if __name__ == "__main__":
    # Quick self-test
    wm = WorkingMemory(capacity=3)

    # Store 3 items
    wm.store("alpha", {"data": "first"}, importance=0.9)
    wm.store("beta", {"data": "second"}, importance=0.5)
    wm.store("gamma", {"data": "third"}, importance=0.3)

    # Recall
    val = wm.recall("beta")
    print(f"Recall beta: {val}")

    # Capacity eviction
    wm.store("delta", {"data": "fourth"}, importance=0.8)
    print(f"After store delta (cap 3): keys = {wm.list_keys()}")

    # Status
    s = wm.status()
    print(f"Status: {s['item_count']} items, oldest={s['oldest_item_age']}s")

    # Clear (keep alpha)
    wm.clear(keep_keys=["alpha"])
    print(f"After clear(keep=['alpha']): {wm.list_keys()}")

    # Set importance
    wm.set_importance("alpha", 1.0)
    print(f"Alpha importance→1.0: {wm.recall_metadata('alpha')['importance']}")

    print("\nAll self-tests passed.")
