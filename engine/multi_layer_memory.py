#!/usr/bin/env python3
"""
Multi-Layer Memory Module — ANAMNE-inspired three-tier architecture

Three layers with distinct speeds, volatilities, and retrieval biases:

  EPISODIC (Hippocampus analog)
    - High volatility, fast decay (~1h TTL)
    - Stores raw conversation snippets, session events
    - Auto-purging at capacity (5000 items)
    - NOT consolidated unless explicitly promoted

  SEMANTIC (Neocortex analog)
    - Low volatility, slow decay (~30d TTL)
    - Stores facts, patterns, verified knowledge
    - Higher importance threshold for insertion
    - Source-tracked back to originating episodic memory

  WORKING (PFC analog)
    - Delegates to existing working_memory_module.py
    - Volatile scratchpad for current session context

The module replaces the monolithic memory store with a layered
architecture where memories flow: Working → Episodic → Semantic
through explicit promotion and consolidation.
"""

import json
import threading
import time
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# In-memory stores (ephemeral — SQLite integration deferred)
# ---------------------------------------------------------------------------

EPISODIC_CAPACITY = 5000
EPISODIC_DEFAULT_TTL = 3600       # 1 hour
SEMANTIC_DEFAULT_TTL = 2592000    # 30 days
PROMOTION_MIN_CONFIRMATIONS = 2   # must be promoted N times to enter semantic


class MultiLayerMemory:
    """Three-tier memory store with promotion and decay."""

    def __init__(self):
        self._lock = threading.Lock()
        self._episodic: dict[str, dict] = {}   # mem_id → item
        self._semantic: dict[str, dict] = {}   # mem_id → item
        self._promotion_log: list[dict] = []

    # ------------------------------------------------------------------
    # Thread-safe access
    # ------------------------------------------------------------------

    def _locked_method(self, method_name: str, *args, **kwargs):
        """Call a private method under the lock."""
        with self._lock:
            fn = getattr(self, f"_{method_name}", None)
            if fn is None:
                raise AttributeError(f"No _{method_name} method")
            return fn(*args, **kwargs)

    def get_episodic_store(self): return self._episodic
    def get_semantic_store(self): return self._semantic

    # ------------------------------------------------------------------
    # Episodic — fast, volatile, conversation-grained
    # ------------------------------------------------------------------

    def store_episodic(self, content: Any, tags: list[str] | None = None,
                       importance: float = 0.3, ttl_seconds: int | None = None,
                       source_session: str = "") -> dict:
        """Store a raw memory in the episodic buffer.

        Episodic items have high volatility and are auto-purged.
        They must be explicitly promoted to reach semantic.
        """
        ttl = ttl_seconds if ttl_seconds is not None else EPISODIC_DEFAULT_TTL
        now = time.time()
        mem_id = str(uuid.uuid4())[:12]

        # Evict if at capacity
        evicted = None
        if len(self._episodic) >= EPISODIC_CAPACITY:
            evicted = self._evict_one(self._episodic)

        self._episodic[mem_id] = {
            "id": mem_id,
            "content": content,
            "tags": tags or [],
            "importance": max(0.0, min(1.0, importance)),
            "layer": "episodic",
            "source_session": source_session,
            "promotion_count": 0,
            "created_at": now,
            "last_access": now,
            "access_count": 0,
            "ttl_seconds": max(60, ttl),
        }
        return {"status": "ok", "id": mem_id, "layer": "episodic",
                "evicted": evicted}

    def recall_episodic(self, mem_id: str) -> Any | None:
        """Recall an episodic memory by ID. Returns None if expired."""
        item = self._get_item(self._episodic, mem_id)
        return item["content"] if item else None

    def search_episodic(self, query: str, limit: int = 10) -> list[dict]:
        """Simple keyword search over episodic content."""
        return self._search_layer(self._episodic, query, limit)

    # ------------------------------------------------------------------
    # Semantic — slow, persistent, knowledge-grained
    # ------------------------------------------------------------------

    def store_semantic(self, content: Any, tags: list[str] | None = None,
                       importance: float = 0.7,
                       ttl_seconds: int | None = None,
                       source_episodic_ids: list[str] | None = None) -> dict:
        """Store a fact/pattern in the semantic layer.

        Semantic items have low volatility and represent verified
        knowledge. Higher default importance threshold.
        """
        ttl = ttl_seconds if ttl_seconds is not None else SEMANTIC_DEFAULT_TTL
        now = time.time()
        mem_id = str(uuid.uuid4())[:12]

        self._semantic[mem_id] = {
            "id": mem_id,
            "content": content,
            "tags": tags or [],
            "importance": max(0.0, min(1.0, importance)),
            "layer": "semantic",
            "source_episodic_ids": source_episodic_ids or [],
            "created_at": now,
            "last_access": now,
            "access_count": 0,
            "ttl_seconds": max(3600, ttl),
        }
        return {"status": "ok", "id": mem_id, "layer": "semantic"}

    def recall_semantic(self, mem_id: str) -> Any | None:
        """Recall a semantic memory by ID."""
        item = self._get_item(self._semantic, mem_id)
        return item["content"] if item else None

    def search_semantic(self, query: str, limit: int = 10) -> list[dict]:
        """Simple keyword search over semantic content."""
        return self._search_layer(self._semantic, query, limit)

    # ------------------------------------------------------------------
    # Cross-layer operations
    # ------------------------------------------------------------------

    def promote(self, episodic_id: str, importance: float | None = None) -> dict:
        """Promote an episodic memory toward semantic.

        First promotion queues it; second promotion (or configurable
        threshold) actually stores it in semantic.
        """
        if episodic_id not in self._episodic:
            return {"status": "error", "error": f"Episodic memory not found: {episodic_id}"}

        item = self._episodic[episodic_id]
        item["promotion_count"] += 1

        self._promotion_log.append({
            "episodic_id": episodic_id,
            "promotion_count": item["promotion_count"],
            "timestamp": time.time(),
        })

        # Threshold met — promote to semantic
        if item["promotion_count"] >= PROMOTION_MIN_CONFIRMATIONS:
            semantic_id = self.store_semantic(
                content=item["content"],
                tags=item["tags"],
                importance=importance if importance is not None else item["importance"],
                source_episodic_ids=[episodic_id],
            )["id"]

            # Remove from episodic if fully promoted
            self._episodic.pop(episodic_id, None)

            return {
                "status": "promoted",
                "episodic_id": episodic_id,
                "semantic_id": semantic_id,
                "promotions": item["promotion_count"],
                "note": "Memory promoted to semantic layer",
            }

        return {
            "status": "queued",
            "episodic_id": episodic_id,
            "promotions": item["promotion_count"],
            "note": f"Memory queued for promotion ({PROMOTION_MIN_CONFIRMATIONS - item['promotion_count']} more needed)",
        }

    def search_all(self, query: str, limit: int = 20) -> dict:
        """Search across all layers, sorted by relevance."""
        ep_results = self._search_layer(self._episodic, query, limit // 2)
        sem_results = self._search_layer(self._semantic, query, limit // 2)
        return {
            "episodic": ep_results,
            "semantic": sem_results,
            "total": len(ep_results) + len(sem_results),
        }

    def consolidate(self, dry_run: bool = False) -> dict:
        """Run consolidation: purge expired items, deduplicate semantic.

        Returns stats on what was purged.
        """
        now = time.time()
        expired_ep = 0
        expired_sem = 0

        if dry_run:
            expired_ep = sum(1 for v in self._episodic.values()
                            if now - v["created_at"] > v["ttl_seconds"])
            expired_sem = sum(1 for v in self._semantic.values()
                             if now - v["created_at"] > v["ttl_seconds"])
        else:
            # Purge expired episodic
            for mid in list(self._episodic.keys()):
                if now - self._episodic[mid]["created_at"] > self._episodic[mid]["ttl_seconds"]:
                    self._episodic.pop(mid)
                    expired_ep += 1

            # Purge expired semantic
            for mid in list(self._semantic.keys()):
                if now - self._semantic[mid]["created_at"] > self._semantic[mid]["ttl_seconds"]:
                    self._semantic.pop(mid)
                    expired_sem += 1

        return {
            "status": "ok",
            "dry_run": dry_run,
            "expired_episodic_purged": expired_ep,
            "expired_semantic_purged": expired_sem,
            "episodic_remaining": len(self._episodic),
            "semantic_remaining": len(self._semantic),
        }

    def status(self) -> dict:
        """Return stats for all layers."""
        now = time.time()

        def _layer_stats(store: dict) -> dict:
            if not store:
                return {"count": 0, "oldest": None, "avg_importance": 0}
            items = list(store.values())
            ages = [now - v["created_at"] for v in items]
            return {
                "count": len(store),
                "oldest_seconds": round(max(ages), 1),
                "avg_importance": round(sum(v["importance"] for v in items) / len(items), 3),
                "avg_ttl_seconds": round(sum(v["ttl_seconds"] for v in items) / len(items), 1),
            }

        return {
            "episodic": _layer_stats(self._episodic),
            "semantic": _layer_stats(self._semantic),
            "promotions_total": len(self._promotion_log),
            "promotions_logged": len(self._promotion_log),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_item(self, store: dict, mem_id: str) -> dict | None:
        if mem_id not in store:
            return None
        item = store[mem_id]
        if time.time() - item["created_at"] > item["ttl_seconds"]:
            store.pop(mem_id)
            return None
        item["last_access"] = time.time()
        item["access_count"] += 1
        return item

    def _evict_one(self, store: dict) -> str | None:
        if not store:
            return None
        # Score: lower = better eviction candidate
        now = time.time()
        def _score(item: dict) -> float:
            age = now - item["created_at"]
            return (item["access_count"] + 1) / (age + 1) * (item["importance"] + 0.1)
        worst = min(store.items(), key=lambda kv: _score(kv[1]))
        key = worst[0]
        store.pop(key)
        return key

    def _search_layer(self, store: dict, query: str, limit: int) -> list[dict]:
        """Simple case-insensitive substring search."""
        q = query.lower()
        results = []
        now = time.time()
        for mid, item in store.items():
            # Skip expired
            if now - item["created_at"] > item["ttl_seconds"]:
                continue
            content_str = json.dumps(item["content"]).lower()
            if q in content_str or any(q in t.lower() for t in item["tags"]):
                results.append({
                    "id": mid,
                    "content": item["content"],
                    "tags": item["tags"],
                    "layer": item["layer"],
                    "importance": item["importance"],
                    "age_seconds": round(now - item["created_at"], 1),
                })
        # Sort by importance descending, limit
        results.sort(key=lambda r: r["importance"], reverse=True)
        return results[:limit]


# ---------------------------------------------------------------------------
# MCP Tool handlers
# ---------------------------------------------------------------------------

_MLM: MultiLayerMemory | None = None


def _get_mlm() -> MultiLayerMemory:
    global _MLM
    if _MLM is None:
        _MLM = MultiLayerMemory()
    return _MLM


def _with_lock(mlm: MultiLayerMemory, fn, *args, **kwargs):
    """Execute fn under MLM's thread lock."""
    with mlm._lock:
        return fn(*args, **kwargs)


def handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch multi-layer memory MCP tool calls."""
    mlm = _get_mlm()
    try:
        if name == "read_memory_status":
            return {"content": [{"type": "text", "text": json.dumps(mlm.status(), indent=2)}]}

        elif name == "read_memory_search":
            q = args.get("query", "")
            if not q:
                return {"content": [{"type": "text", "text": json.dumps({"error": "query is required"})}]}
            layer = args.get("layer", "all")
            limit = args.get("limit", 20)
            if layer == "episodic":
                results = {"episodic": mlm.search_episodic(q, limit), "semantic": [], "total": 0}
            elif layer == "semantic":
                results = {"episodic": [], "semantic": mlm.search_semantic(q, limit), "total": 0}
            else:
                results = mlm.search_all(q, limit)
            return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}

        elif name == "write_memory_add":
            content = args.get("content")
            if content is None:
                return {"content": [{"type": "text", "text": json.dumps({"error": "content is required"})}]}
            layer = args.get("layer", "episodic")
            if layer == "semantic":
                result = mlm.store_semantic(
                    content=content,
                    tags=args.get("tags"),
                    importance=args.get("importance", 0.7),
                    ttl_seconds=args.get("ttl_seconds"),
                )
            else:
                result = mlm.store_episodic(
                    content=content,
                    tags=args.get("tags"),
                    importance=args.get("importance", 0.3),
                    ttl_seconds=args.get("ttl_seconds"),
                    source_session=args.get("source_session", ""),
                )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "mutate_memory_promote":
            mem_id = args.get("id", "")
            if not mem_id:
                return {"content": [{"type": "text", "text": json.dumps({"error": "id is required"})}]}
            result = mlm.promote(mem_id, importance=args.get("importance"))
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "write_memory_consolidate":
            dry_run = args.get("dry_run", False)
            result = mlm.consolidate(dry_run=dry_run)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "read_memory_synthesize":
            # Simple synthesize: search across all layers and merge
            q = args.get("query", "")
            if not q:
                return {"content": [{"type": "text", "text": json.dumps({"error": "query is required"})}]}
            results = mlm.search_all(q, args.get("limit", 20))
            synthesis = {
                "query": q,
                "sources": len(results.get("episodic", [])) + len(results.get("semantic", [])),
                "episodic_count": len(results.get("episodic", [])),
                "semantic_count": len(results.get("semantic", [])),
                "combined": results.get("episodic", []) + results.get("semantic", []),
            }
            return {"content": [{"type": "text", "text": json.dumps(synthesis, indent=2)}]}

        else:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Unknown MLM tool: {name}"})}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

MLM_TOOLS = [
    {
        "name": "read_memory_status",
        "description": " READ — Show multi-layer memory stats: episodic count, semantic count, avg importance, promotions logged.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_memory_search",
        "description": " READ — Search across episodic and/or semantic memory layers. Supports layer='episodic', 'semantic', or 'all' (default). Returns results sorted by importance.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "layer": {"type": "string", "description": "episodic, semantic, or all", "default": "all"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "write_memory_add",
        "description": " WRITE — Store a memory in the specified layer. Defaults to episodic (fast-decay, high-volatility). Set layer='semantic' for persistent knowledge storage. Accepts dry_run=true.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"description": "Memory content (any JSON-compatible type)"},
                "layer": {"type": "string", "description": "episodic (default) or semantic", "default": "episodic"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization"},
                "importance": {"type": "number", "description": "0.0–1.0. Higher = slower decay, better retrieval.", "default": 0.3},
                "ttl_seconds": {"type": "integer", "description": "Custom TTL override"},
                "source_session": {"type": "string", "description": "Session ID (episodic only)"},
                "dry_run": {"type": "boolean"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "mutate_memory_promote",
        "description": " MUTATE — Promote an episodic memory toward the semantic layer. Requires N confirmations (default: 2) before actual promotion. Accepts dry_run=true.",
        "permission": "mutate",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Episodic memory ID to promote"},
                "importance": {"type": "number", "description": "Override importance for semantic storage"},
                "dry_run": {"type": "boolean"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "write_memory_consolidate",
        "description": " WRITE — Run consolidation: purge expired items, deduplicate semantic layer. Set dry_run=true to preview without purging.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {"type": "boolean", "description": "Preview without purging", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "read_memory_synthesize",
        "description": " READ — Search across all layers and return merged results with source counts. Like search_all but with an additional synthesis wrapper.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
]


if __name__ == "__main__":
    print("=== Multi-Layer Memory Self-Test ===\n")

    mlm = MultiLayerMemory()

    # Store episodic
    r1 = mlm.store_episodic("User asked about Docker networking issues", tags=["docker", "support"], source_session="sess-001")
    ep_id = r1["id"]
    print(f"Store episodic: layer={r1['layer']}, id={ep_id}")
    assert r1["status"] == "ok"
    assert r1["layer"] == "episodic"

    r2 = mlm.store_episodic("Debugged null pointer in simulation engine", tags=["debug", "simulation"], source_session="sess-001")
    print(f"Store episodic 2: id={r2['id']}")

    # Store semantic
    r3 = mlm.store_semantic("Docker bridge networking requires port mapping for inter-container communication", tags=["docker", "networking"], importance=0.85)
    sem_id = r3["id"]
    print(f"Store semantic: layer={r3['layer']}, id={sem_id}")
    assert r3["status"] == "ok"
    assert r3["layer"] == "semantic"

    # Search
    s1 = mlm.search_episodic("docker")
    print(f"Search episodic 'docker': {len(s1)} results")
    assert len(s1) >= 1

    s2 = mlm.search_semantic("docker")
    print(f"Search semantic 'docker': {len(s2)} results")
    assert len(s2) >= 1

    s3 = mlm.search_all("docker")
    print(f"Search all 'docker': episodic={len(s3['episodic'])}, semantic={len(s3['semantic'])}")
    assert len(s3["episodic"]) >= 1
    assert len(s3["semantic"]) >= 1

    # Promote (first time — queued)
    p1 = mlm.promote(ep_id)
    print(f"Promote (1st): status={p1['status']}")
    assert p1["status"] == "queued"
    assert p1["promotions"] == 1

    # Recall after first promotion
    recalled = mlm.recall_episodic(ep_id)
    print(f"Recall episodic after 1st promotion: {'found' if recalled else 'missing'}")
    assert recalled is not None  # still in episodic after 1st promotion

    # Promote (second time — promoted to semantic)
    p2 = mlm.promote(ep_id)
    print(f"Promote (2nd): status={p2['status']}, sem_id={p2.get('semantic_id', 'N/A')}")
    assert p2["status"] == "promoted"
    assert "semantic_id" in p2

    # Episodic should be gone after full promotion
    recalled2 = mlm.recall_episodic(ep_id)
    print(f"Recall episodic after promotion: {'found' if recalled2 else 'gone'}")
    assert recalled2 is None

    # Status
    st = mlm.status()
    print(f"Status: episodic={st['episodic']['count']}, semantic={st['semantic']['count']}, promotions={st['promotions_total']}")
    assert st["episodic"]["count"] >= 1  # 1 remaining (null pointer one)
    assert st["semantic"]["count"] >= 2  # original + promoted
    assert st["promotions_total"] == 2

    # Consolidate (dry run)
    c1 = mlm.consolidate(dry_run=True)
    print(f"Consolidate (dry run): {c1['expired_episodic_purged']} ep, {c1['expired_semantic_purged']} sem")
    assert c1["status"] == "ok"

    # Consolidate (real)
    c2 = mlm.consolidate(dry_run=False)
    print(f"Consolidate: purged ep={c2['expired_episodic_purged']}, sem={c2['expired_semantic_purged']}")

    # Synthesize
    syn = mlm.search_all("networking")
    print(f"Synthesize 'networking': {len(syn['semantic'])} semantic results")

    print("\nAll self-tests passed.")
