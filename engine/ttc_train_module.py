#!/usr/bin/env python3
"""
ttc_train_module.py — Internal Test-Time Compute Training (TTC Phase 5)

Extracts resolved cases (successful reasoning trajectories + final answers)
from the persistent memory stores and pipeline traces, then formats them as
reasoning-trajectory training samples. This is the "Internal TTC" lever:
spend zero GPU now, accumulate a curated corpus that a future distillation
pass can train on.

What counts as "resolved":
  - A memory item tagged status=resolved / verified
  - A DAG trace whose final node succeeded
  - A semantic-store item with confirmation_count >= threshold

Output: a JSONL corpus at data/ttc-corpus.jsonl, one sample per line:
  {"prompt": <task>, "trajectory": [steps], "answer": <final>, "source": ...}

Zero GPU. Produces the dataset; the actual training is a downstream step
(planned, not implemented here — staying within stdlib-only scope).

Analog: the brain's memory consolidation that replays successful episodes
to strengthen the underlying policy (offline rehearsal).
"""

import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

MEMORY_JSON = DATA_DIR / "global-projects-memory.json"
SUMMARY_JSON = DATA_DIR / "memory-summary.json"
DAG_TRACE_DIR = DATA_DIR / "dag-traces"
CORPUS_PATH = DATA_DIR / "ttc-corpus.jsonl"


def _read_json(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_from_memory_store(store, min_confirmations=2):
    """Yield resolved cases from a memory dict keyed by id."""
    samples = []
    if not isinstance(store, dict):
        return samples
    for mid, item in store.items():
        if not isinstance(item, dict):
            continue
        status = (item.get("status") or "").lower()
        confirm = item.get("confirmation_count") or item.get("confirmations") or 0
        verified = item.get("verified", False)
        if status in ("resolved", "verified") or verified or confirm >= min_confirmations:
            traj = item.get("trajectory") or item.get("steps") or []
            samples.append({
                "prompt": item.get("task") or item.get("prompt") or item.get("query") or mid,
                "trajectory": traj if isinstance(traj, list) else [traj],
                "answer": item.get("answer") or item.get("result") or item.get("resolution") or "",
                "source": "memory",
            })
    return samples


def _extract_from_dag_traces():
    """Yield resolved cases from completed DAG traces."""
    samples = []
    if not DAG_TRACE_DIR.exists():
        return samples
    for f in DAG_TRACE_DIR.glob("*.json"):
        trace = _read_json(f)
        if not isinstance(trace, dict):
            continue
        nodes = trace.get("nodes") or trace.get("steps") or []
        final = trace.get("final") or trace.get("result") or ""
        all_ok = all(
            (n.get("status") in ("done", "success", "ok", True)) for n in nodes
        ) if nodes else False
        if all_ok and final:
            samples.append({
                "prompt": trace.get("goal") or trace.get("dag_id") or f.name,
                "trajectory": [n.get("tool") or n.get("name") for n in nodes if isinstance(n, dict)],
                "answer": final,
                "source": f"dag:{f.name}",
            })
    return samples


def extract(min_confirmations=2, dry_run=False):
    """
    Build the TTC training corpus from memory + traces.

    Args:
        min_confirmations: min confirmation_count for a memory item to count
        dry_run: if True, return the planned samples without writing the file
    Returns:
        {"samples": N, "sources": {...}, "corpus_path": ...}
    """
    samples = []

    mem = _read_json(MEMORY_JSON)
    if isinstance(mem, dict):
        # memory files often nest stores under keys
        for v in mem.values():
            samples.extend(_extract_from_memory_store(v, min_confirmations))

    summary = _read_json(SUMMARY_JSON)
    if isinstance(summary, dict):
        for v in summary.values():
            samples.extend(_extract_from_memory_store(v, min_confirmations))

    samples.extend(_extract_from_dag_traces())

    # de-dup by prompt+answer
    seen = set()
    deduped = []
    for s in samples:
        key = (s["prompt"], s["answer"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)

    result = {
        "samples": len(deduped),
        "sources": {
            "memory": sum(1 for s in deduped if s["source"] == "memory"),
            "dag": sum(1 for s in deduped if s["source"].startswith("dag")),
        },
        "corpus_path": str(CORPUS_PATH),
    }

    if dry_run:
        result["status"] = "simulated"
        result["sample_preview"] = deduped[:3]
        return result

    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("w", encoding="utf-8") as fh:
        for s in deduped:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    result["status"] = "written"
    return result


def corpus_status():
    if not CORPUS_PATH.exists():
        return {"exists": False}
    n = sum(1 for _ in CORPUS_PATH.open(encoding="utf-8"))
    return {"exists": True, "lines": n, "path": str(CORPUS_PATH)}


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

TTC_TRAIN_TOOLS = [
    {
        "name": "read_ttc_train",
        "description": " WRITE — Extract resolved cases (successful trajectories + final answers) from persistent memory and DAG traces, write them as a JSONL reasoning-trajectory corpus for future distillation.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_confirmations": {
                    "type": "integer",
                    "default": 2,
                    "description": "Min confirmation_count for a memory item to count as resolved",
                },
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "read_ttc_corpus_status",
        "description": " READ — Show TTC corpus stats: exists, line count, path.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

def handle_tool_call(name, args):
    stripped = name.split("_", 1)[1] if "_" in name else name

    if stripped == "ttc_train":
        return extract(
            min_confirmations=args.get("min_confirmations", 2),
            dry_run=args.get("dry_run", False),
        )
    elif stripped == "ttc_corpus_status":
        return corpus_status()
    return {"error": f"Unknown ttc tool: {name}"}


if __name__ == "__main__":
    print("=== TTC Train Self-Test ===\n")

    # With no memory files present, corpus should be empty but not crash
    r = extract(dry_run=True)
    print("dry-run extract:", r)
    assert "samples" in r
    assert r["status"] == "simulated"

    # Real write (will produce an empty/near-empty corpus if no data)
    r2 = extract()
    print("write extract:", r2)
    assert r2["status"] == "written"
    assert corpus_status()["exists"] is True

    print("\nALL TTC TRAIN SELF-TESTS PASSED")
