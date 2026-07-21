#!/usr/bin/env python3
"""
suffix_decode_module.py — SuffixDecoding Engine (TTC Phase 2)

An n-gram model over observed tool-call sequences. Given the recent tail of
calls (the "suffix"), it predicts the most likely next tool(s) so the
dispatcher can speculatively pre-warm or shortcut repetitive workflows.

Why n-gram over a reversed trie: prediction must key on the CALL TAIL
("after B, C usually follows") independent of what preceded B. A reversed
trie only matches from the root, so it cannot answer "given the last k
calls, what's next" without knowing the whole sequence. An n-gram keyed on
the tail context does exactly that, and stays zero-GPU / stdlib-only.

Storage: for each learned order n in {1,2,3} we keep
    GRAMS[n][context_tuple] = {next_tool: count}
Prediction walks the longest context match available (3-gram -> 2 -> 1).

Analog: the brain's sequence-completion systems (supplementary motor area /
basal ganglia) that pre-activate the next motor step from a learned habit.
"""

import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

SUFFIX_PATH = DATA_DIR / "suffix-tree.json"
MAX_GRAMS = 50000          # hard cap on stored (context,next) pairs
MIN_COUNT = 1             # below this a pair is forgotten on prune


# ---------------------------------------------------------------------------
# Persistence (self-contained, no cross-module imports)
# ---------------------------------------------------------------------------

def _load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _empty_store():
    return {
        "grams": {"1": {}, "2": {}, "3": {}},
        "sequences": 0,
        "updated": 0,
    }


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def add_sequence(tools, metadata=None, dry_run=False):
    """
    Record a completed tool-call sequence.

    Args:
        tools: ordered list of tool names (>=2)
        metadata: optional dict (task type, source harness)
        dry_run: if True, simulate and return the plan
    """
    if not isinstance(tools, list) or len(tools) < 2:
        return {"error": "add_sequence requires a list of >=2 tool names"}

    tools = [str(t) for t in tools]

    if dry_run:
        return {
            "status": "simulated",
            "sequence_len": len(tools),
            "note": "Dry run. Execute without dry_run=true to persist.",
        }

    store = _load_json(SUFFIX_PATH, _empty_store())
    grams = store["grams"]
    seq = tools

    # For each order n, slide a window: context = seq[i-n:i], next = seq[i]
    for n in (1, 2, 3):
        g = grams[str(n)]
        for i in range(n, len(seq)):
            ctx = tuple(seq[i - n:i])
            nxt = seq[i]
            bucket = g.setdefault(str(ctx), {})
            bucket[nxt] = bucket.get(nxt, 0) + 1

    store["sequences"] = store.get("sequences", 0) + 1
    store["updated"] = time.time()

    _save_json(SUFFIX_PATH, store)
    return {
        "status": "inserted",
        "sequence_len": len(tools),
        "total_sequences": store["sequences"],
    }


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------

def predict(context=None, next_n=1, top_k=5):
    """
    Given a recent call context (ordered, most recent LAST), predict the
    most likely next tool(s).

    Args:
        context: ordered list of recent tool names (most recent LAST)
        next_n: how many future steps to project (1 = immediate next)
        top_k: how many candidates to return
    """
    if not context:
        return {"predictions": [], "note": "No context supplied"}

    ctx = [str(t) for t in context]
    store = _load_json(SUFFIX_PATH, _empty_store())
    grams = store["grams"]

    # Try longest matching n-gram context first (3 -> 2 -> 1)
    for n in (3, 2, 1):
        if len(ctx) < n:
            continue
        tail = tuple(ctx[len(ctx) - n:])
        bucket = grams[str(n)].get(str(tail))
        if bucket:
            total = sum(bucket.values())
            ranked = sorted(bucket.items(), key=lambda kv: -kv[1])
            preds = [
                {
                    "tool": t,
                    "count": c,
                    "probability": round(c / total, 4),
                    "matched_order": n,
                }
                for t, c in ranked[:top_k]
            ]
            return {
                "predictions": preds,
                "context_len": len(ctx),
                "context_seen": True,
            }

    return {
        "predictions": [],
        "context_len": len(ctx),
        "context_seen": False,
        "note": "No learned continuation for this tail",
    }


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

def prune(min_count=MIN_COUNT, dry_run=False):
    """Drop (context,next) pairs whose count is below min_count."""
    store = _load_json(SUFFIX_PATH, _empty_store())
    removed = 0
    for n in ("1", "2", "3"):
        g = store["grams"][n]
        for ctx, bucket in list(g.items()):
            for t, c in list(bucket.items()):
                if c < min_count:
                    del bucket[t]
                    removed += 1
            if not bucket:
                del g[ctx]
    if not dry_run:
        _save_json(SUFFIX_PATH, store)
    return {
        "status": "simulated" if dry_run else "pruned",
        "pairs_removed": removed,
    }


def stats():
    store = _load_json(SUFFIX_PATH, _empty_store())
    counts = {n: len(store["grams"][n]) for n in ("1", "2", "3")}
    return {
        "sequences": store.get("sequences", 0),
        "gram_pairs": counts,
        "updated": store.get("updated", 0),
    }


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

SUFFIX_DECODE_TOOLS = [
    {
        "name": "read_suffix_predict",
        "description": " READ — Predict the most likely next tool(s) given a recent call-context tail using the learned n-gram model. Returns ranked candidates with probability. Use to pre-warm or shortcut repetitive workflows.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of recent tool names (most recent LAST)",
                },
                "next_n": {
                    "type": "integer",
                    "description": "How many future steps to project (1 = immediate next)",
                    "default": 1,
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of candidate predictions to return",
                    "default": 5,
                },
            },
            "required": ["context"],
        },
    },
    {
        "name": "mutate_suffix_update",
        "description": " WRITE — Record a completed tool-call sequence into the n-gram model so future predictions improve. Pass the full ordered tool list.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of tool names (>=2) observed in one workflow",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional: task type, source harness, etc.",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, simulate the insert without persisting",
                    "default": False,
                },
            },
            "required": ["tools"],
        },
    },
    {
        "name": "read_suffix_stats",
        "description": " READ — Show suffix-model stats: total sequences learned, gram-pair counts, last update time.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "mutate_suffix_prune",
        "description": " WRITE — Prune low-frequency pairs (forgetting) to bound model size.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_count": {
                    "type": "integer",
                    "description": "Pairs with count below this are dropped",
                    "default": 1,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, simulate without persisting",
                    "default": False,
                },
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

def handle_tool_call(name, args):
    stripped = name.split("_", 1)[1] if "_" in name else name

    if stripped == "suffix_predict":
        return predict(
            context=args.get("context", []),
            next_n=args.get("next_n", 1),
            top_k=args.get("top_k", 5),
        )
    elif stripped == "suffix_update":
        return add_sequence(
            tools=args.get("tools", []),
            metadata=args.get("metadata"),
            dry_run=args.get("dry_run", False),
        )
    elif stripped == "suffix_stats":
        return stats()
    elif stripped == "suffix_prune":
        return prune(
            min_count=args.get("min_count", MIN_COUNT),
            dry_run=args.get("dry_run", False),
        )
    return {"error": f"Unknown suffix_decode tool: {name}"}


if __name__ == "__main__":
    # Self-test
    import os
    if SUFFIX_PATH.exists():
        os.remove(SUFFIX_PATH)

    print("=== SuffixDecoding Self-Test ===\n")

    # Learn a habit: search -> add -> compact -> synthesize
    seq = ["read_memory_search", "write_memory_add", "read_compact_synthesize", "write_compact_merge"]
    r = add_sequence(seq)
    print("insert:", r)
    assert r["status"] == "inserted"

    # Repeat to build counts
    add_sequence(seq)
    add_sequence(["read_memory_search", "write_memory_add", "read_compact_synthesize", "write_compact_merge"])

    # Predict after tail [write_memory_add, read_compact_synthesize] -> expect write_compact_merge
    p = predict(context=["read_memory_search", "write_memory_add", "read_compact_synthesize"])
    print("predict after 3-grams:", p["predictions"])
    assert p["predictions"][0]["tool"] == "write_compact_merge"

    # Predict after 2-gram tail [write_memory_add] -> expect read_compact_synthesize
    p2 = predict(context=["write_memory_add"], top_k=3)
    print("predict after write_memory_add:", p2["predictions"])
    assert p2["predictions"][0]["tool"] == "read_compact_synthesize"

    # Unknown tail
    p3 = predict(context=["totally_unknown_tool"])
    print("unknown tail:", p3["predictions"], p3["context_seen"])
    assert p3["context_seen"] is False

    print("stats:", stats())
    print("\nALL SUFFIX SELF-TESTS PASSED")
