#!/usr/bin/env python3
"""
pedagogy-module.py — Agent Pedagogy Engine

Master Spec:
  - Assess user's current understanding level
  - Generate explanation at appropriate depth
  - Store user comprehension profile
  - Dynamically adjust explanation depth for maximum retention
"""

import time
from pathlib import Path

from utils import load_json, save_json

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

#  Depth levels
DEPTHS = {
    1: {
        "label": "intuitive",
        "description": "Analogy-based, minimal jargon, big picture",
    },
    2: {"label": "basic", "description": "Core concepts with simple examples"},
    3: {
        "label": "intermediate",
        "description": "Formal definitions, standard notation",
    },
    4: {
        "label": "advanced",
        "description": "Full mathematical rigor, proofs, edge cases",
    },
    5: {
        "label": "expert",
        "description": "Research frontiers, open problems, trade-offs",
    },
}


def assess(queries=None, topic=""):
    """Assess user understanding based on query patterns and optional topic."""
    profile = load_json(DATA_DIR / "pedagogy-profile.json", {"depth": 3, "history": []})
    history = profile.get("history", [])

    # Heuristic: if queries contain advanced terms, bump depth
    advanced_terms = [
        "eigenvalue",
        "tensor",
        "convolution",
        "manifold",
        "homology",
        "lagrangian",
        "hamiltonian",
        "functional analysis",
    ]
    basic_terms = ["what is", "how to", "simple", "beginner", "explain like"]

    # Determine suggested depth
    suggested = profile.get("depth", 3)
    queries_text = " ".join(queries or []).lower() if queries else ""
    topic_text = (topic or "").lower()

    combined = queries_text + " " + topic_text
    advanced_count = sum(1 for t in advanced_terms if t in combined)
    basic_count = sum(1 for t in basic_terms if t in combined)

    if advanced_count >= 2:
        suggested = min(suggested + 1, 5)
    elif basic_count >= 2:
        suggested = max(suggested - 1, 1)

    return {
        "current_depth": profile.get("depth", 3),
        "suggested_depth": suggested,
        "depth_info": DEPTHS.get(suggested, DEPTHS[3]),
        "all_levels": {k: v["label"] for k, v in DEPTHS.items()},
        "interactions_tracked": len(history),
        "topic": topic or "general",
    }


def adapt(topic="", complexity=None, format="text"):
    """Generate an explanation prompt at appropriate depth for the given topic."""
    profile = load_json(DATA_DIR / "pedagogy-profile.json", {"depth": 3})
    depth = complexity if complexity else profile.get("depth", 3)
    depth = max(1, min(5, depth))

    level = DEPTHS[depth]

    prompt = (
        f"Explain '{topic or 'the requested topic'}' at {level['label']} level "
        f"({level['description']}). "
        f"Output format: {format}. "
        f"Adjust vocabulary, notation depth, and example complexity to match."
    )

    return {
        "pedagogy_prompt": prompt,
        "depth": depth,
        "depth_label": level["label"],
        "format": format,
        "topic": topic or "general",
        "note": "Feed this prompt into a generation tool (e.g., read_coder_explain) for the adapted output.",
    }


def store_profile(depth=None, topic="", feedback_score=None):
    """Store or update user comprehension profile."""
    profile = load_json(DATA_DIR / "pedagogy-profile.json", {"depth": 3, "history": []})

    if depth is not None:
        profile["depth"] = max(1, min(5, depth))

    entry = {
        "timestamp": time.time(),
        "topic": topic,
        "feedback_score": feedback_score,
        "depth_used": profile["depth"],
    }
    profile.setdefault("history", []).append(entry)
    # Keep last 100
    profile["history"] = profile["history"][-100:]

    save_json(DATA_DIR / "pedagogy-profile.json", profile)

    return {
        "status": "stored",
        "current_depth": profile["depth"],
        "total_interactions": len(profile["history"]),
        "last_topic": topic,
    }


def handle_tool_call(name, args):
    if name == "read_pedagogy_assess":
        return assess(args.get("queries"), args.get("topic", ""))
    elif name == "read_pedagogy_adapt":
        return adapt(
            args.get("topic", ""), args.get("complexity"), args.get("format", "text")
        )
    elif name == "write_pedagogy_profile":
        return store_profile(
            args.get("depth"), args.get("topic", ""), args.get("feedback_score")
        )
    return {"error": f"Unknown pedagogy tool: {name}"}
