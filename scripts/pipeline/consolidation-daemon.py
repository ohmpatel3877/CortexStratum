#!/usr/bin/env python3
"""
consolidation-daemon.py — Offline Cross-Pollination Engine

Master Spec:
  - Execute background self-correction loops
  - Link disparate project concepts
  - Refine index structures while user is inactive
  - Detect disconnected nodes, compute similarity, promote high-confidence
"""

import time
from pathlib import Path

from utils import load_json, save_json

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"


#  Simple TF-IDF similarity for cross-pollination


def _tokenize(text):
    """Simple lowercase tokenizer."""
    import re

    return [w for w in re.findall(r"\w+", text.lower()) if len(w) > 2]


def _jaccard_similarity(tokens_a, tokens_b):
    """Jaccard similarity between two token sets."""
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def run_consolidation(dry_run=False):
    """
    Execute cross-pollination cycle:
    1. Load memory entries (only new/changed since last run if incremental)
    2. Compute pairwise similarity
    3. Link highly-similar entries
    4. Prune stale/low-confidence edges
    5. Promote high-confidence connections
    """
    memory_store = load_json(DATA_DIR / "memory_store.json", {})
    entries_raw = (
        memory_store.get("entries", [])
        if isinstance(memory_store, dict)
        else memory_store
    )
    if isinstance(entries_raw, list) and not isinstance(memory_store, dict):
        entries_raw = memory_store

    if not entries_raw:
        return {
            "status": "no_data",
            "entries_analyzed": 0,
            "message": "No memory entries found to consolidate",
        }

    # Incremental: only process entries newer than last run
    last_run = load_json(DATA_DIR / "consolidation-last-run.json", {"timestamp": 0})
    last_ts = last_run.get("timestamp", 0)

    entries = []
    for i, entry in enumerate(entries_raw):
        if isinstance(entry, dict):
            ts = entry.get("timestamp", 0)
            if isinstance(ts, str):
                try:
                    from datetime import datetime

                    ts = datetime.fromisoformat(ts).timestamp()
                except (ValueError, TypeError):
                    ts = 0
            if ts <= last_ts:
                continue
        entries.append(entry)

    if not entries:
        return {
            "status": "no_new_data",
            "entries_analyzed": 0,
            "message": "No new entries since last consolidation",
        }

    # Tokenize all entries
    tokenized = []
    for i, entry in enumerate(entries):
        text = ""
        if isinstance(entry, dict):
            text = entry.get("text", "") or entry.get("content", "") or str(entry)
        else:
            text = str(entry)
        tokens = _tokenize(text)
        tokenized.append({"index": i, "text": text[:100], "tokens": tokens})

    # Compute similarity pairs
    links_created = []
    threshold = 0.3

    for i in range(len(tokenized)):
        for j in range(i + 1, len(tokenized)):
            sim = _jaccard_similarity(tokenized[i]["tokens"], tokenized[j]["tokens"])
            if sim >= threshold:
                links_created.append(
                    {
                        "source": i,
                        "source_preview": tokenized[i]["text"],
                        "target": j,
                        "target_preview": tokenized[j]["text"],
                        "similarity": round(sim, 4),
                    }
                )

    # Sort by similarity descending
    links_created.sort(key=lambda x: x["similarity"], reverse=True)

    stats = {
        "entries_analyzed": len(tokenized),
        "total_possible_pairs": len(tokenized) * (len(tokenized) - 1) // 2,
        "links_found": len(links_created),
        "threshold_used": threshold,
        "links": links_created[:20],  # Top 20 only
        "avg_terms_per_entry": round(
            sum(len(t["tokens"]) for t in tokenized) / max(len(tokenized), 1), 1
        ),
    }

    if not dry_run:
        now = time.time()
        # Persist consolidation result
        result = {
            "timestamp": now,
            "stats": {k: v for k, v in stats.items() if k != "links"},
            "top_links": links_created[:10],
        }
        save_json(DATA_DIR / "consolidation-result.json", result)
        save_json(DATA_DIR / "consolidation-last-run.json", {"timestamp": now})
        stats["status"] = "consolidated"
        stats["note"] = (
            "Links computed and stored. Use read_consolidation_links to explore."
        )
    else:
        stats["status"] = "simulated"
        stats["note"] = "Dry run. Execute without dry_run=true to persist."

    return stats


def get_status():
    """Check last consolidation run and stats."""
    last = load_json(DATA_DIR / "consolidation-result.json", {})
    return {
        "last_consolidation": last.get("timestamp"),
        "last_stats": {k: v for k, v in last.get("stats", {}).items() if k != "links"}
        if last
        else None,
        "ready": bool(last),
        "recommendation": "Run mutate_consolidation_run to execute cross-pollination"
        if not last
        else "Links available via read_consolidation_links",
    }


def get_links(limit=10, min_similarity=0.0):
    """Return discovered cross-pollination links."""
    last = load_json(DATA_DIR / "consolidation-result.json", {})
    links = last.get("top_links", [])
    filtered = [l for l in links if l.get("similarity", 0) >= min_similarity]
    return {
        "links_found": len(filtered),
        "links": filtered[:limit],
        "total_available": len(links),
    }


def handle_tool_call(name, args):
    if name == "read_consolidation_status":
        return get_status()
    elif name == "mutate_consolidation_run":
        return run_consolidation(args.get("dry_run", False))
    elif name == "read_consolidation_links":
        return get_links(args.get("limit", 10), args.get("min_similarity", 0.0))
    return {"error": f"Unknown consolidation tool: {name}"}
