#!/usr/bin/env python3
"""
Compute-Optimal Allocation Module — TTC Phase 1

Estimates task difficulty and allocates reasoning depth, allowing CortexStratum
to spend more compute on hard problems and less on trivial ones.

Analog: The brain's effort allocation systems (anterior cingulate / dorsolateral PFC)
that evaluate task difficulty and allocate attentional resources accordingly.

Key idea: not all tasks need the same reasoning depth. A "read the time" tool call
should be near-instant; a "debug this multi-module regression" should get deep
verifier passes, beam search, and multiple retry attempts.
"""

import json
import math
import time

# Difficulty heuristics
_COMPLEXITY_KEYWORDS = {
    "debug": 0.3,
    "refactor": 0.3,
    "architecture": 0.4,
    "design": 0.3,
    "optimize": 0.3,
    "migrate": 0.4,
    "integration": 0.3,
    "security": 0.4,
    "concurrency": 0.4,
    "distributed": 0.4,
    "ml": 0.4,
    "neural": 0.4,
    "simulation": 0.3,
    "cfd": 0.4,
    "fea": 0.4,
    "eigenvalue": 0.4,
    "ode": 0.3,
    "pde": 0.4,
    "docker": 0.2,
    "ci/cd": 0.2,
    "kubernetes": 0.3,
    "terraform": 0.3,
    "api": 0.2,
    "rest": 0.1,
    "regex": 0.1,
    "csv": 0.0,
    "json": 0.0,
}

_DIFFICULT_DOMAINS = {
    "simulation", "cad", "electrical", "gamedev", "devops", "research",
}

_MUTATE_TOOLS = {"mutate_", "write_"}  # write/mutate tools are harder than reads


def estimate_difficulty(task_description: str = "",
                        domain: str = "general",
                        tool_name: str = "",
                        input_size: int = 0) -> dict:
    """Estimate task difficulty on 0.0–1.0 scale.

    Returns breakdown for explainability.
    """
    text = f"{task_description} {tool_name} {domain}".lower()
    score = 0.1  # baseline

    # Domain boost
    if domain.lower() in _DIFFICULT_DOMAINS:
        score += 0.15

    # Tool type: write/mutate tools are generally harder
    if any(text.startswith(p) for p in _MUTATE_TOOLS):
        score += 0.1

    # Keyword matches
    for kw, boost in _COMPLEXITY_KEYWORDS.items():
        if kw in text:
            score += boost

    # Input size penalty (longer inputs = more complex)
    if input_size > 5000:
        score += 0.1
    elif input_size > 1000:
        score += 0.05

    # Instruction length heuristic (word count)
    word_count = len(task_description.split())
    if word_count > 100:
        score += 0.1
    elif word_count > 30:
        score += 0.05

    # Cap at [0.0, 1.0]
    score = max(0.0, min(1.0, score))
    confidence = min(1.0, 0.3 + word_count / 200 + input_size / 10000)

    return {
        "difficulty": round(score, 3),
        "confidence": round(confidence, 3),
        "breakdown": {
            "baseline": 0.1,
            "domain_boost": 0.15 if domain.lower() in _DIFFICULT_DOMAINS else 0.0,
            "tool_type_boost": 0.1 if any(text.startswith(p) for p in _MUTATE_TOOLS) else 0.0,
            "keyword_matches": sum(_COMPLEXITY_KEYWORDS.get(kw, 0) for kw in _COMPLEXITY_KEYWORDS if kw in text),
            "input_size_boost": 0.1 if input_size > 5000 else (0.05 if input_size > 1000 else 0.0),
            "verbosity_boost": 0.1 if word_count > 100 else (0.05 if word_count > 30 else 0.0),
        },
        "factors": {
            "task_length_words": word_count,
            "input_size_chars": input_size,
            "domain": domain,
            "tool_name": tool_name,
        },
    }


def allocate_compute_budget(difficulty: float, max_budget: int = 5) -> dict:
    """Map difficulty score to a compute budget tier.

    Budget levels:
      0 — trivial (instant, no retries)
      1 — simple (1 verify pass)
      2 — medium (1-2 passes)
      3 — complex (2-3 passes, use verifier)
      4 — very complex (beam search, PRM scoring)
      5 — research (full TTC: beam search + PRM + best-of-N)
    """
    levels = [
        (0.0, 0.15, 0, "trivial", "Instant, zero retries"),
        (0.15, 0.3, 1, "simple", "Single verify pass"),
        (0.3, 0.5, 2, "medium", "1-2 verify passes, optional rerun"),
        (0.5, 0.7, 3, "complex", "2-3 verifier passes, mandatory retry logic"),
        (0.7, 0.9, 4, "very_complex", "Beam search candidates + verifier scoring"),
        (0.9, 1.01, 5, "research", "Full TTC: beam search + PRM + best-of-N sampling"),
    ]

    level = levels[0]
    for lo, hi, budget, label, desc in levels:
        if lo <= difficulty < hi:
            level = (lo, hi, budget, label, desc)
            break

    _, _, budget, label, desc = level
    allocated = min(budget, max_budget)

    return {
        "budget_tier": allocated,
        "label": label,
        "description": desc,
        "max_budget": max_budget,
        "difficulty_input": difficulty,
    }


def allocate_depth(task_description: str = "",
                   domain: str = "general",
                   tool_name: str = "",
                   input_size: int = 0,
                   max_budget: int = 5) -> dict:
    """Full pipeline: difficulty → budget → depth allocation."""
    diff_result = estimate_difficulty(task_description, domain, tool_name, input_size)
    budget_result = allocate_compute_budget(diff_result["difficulty"], max_budget)

    # Distribute budget across reasoning phases
    phases = ["plan", "research", "implement", "verify"]
    total_units = budget_result["budget_tier"] * 4 + 1  # at least 1 unit total
    phase_weights = {
        "plan": 0.2,
        "research": 0.25,
        "implement": 0.35,
        "verify": 0.2,
    }

    if budget_result["budget_tier"] == 0:
        phase_allocation = {p: 0 for p in phases}
        phase_allocation["verify"] = 0
    else:
        phase_allocation = {
            p: max(0, int(math.ceil(total_units * w)))
            for p, w in phase_weights.items()
        }

    return {
        "difficulty": diff_result,
        "budget": budget_result,
        "depth": {
            "total_units": total_units,
            "phases": phase_allocation,
            "recommended_strategy": (
                "instant" if budget_result["budget_tier"] == 0 else
                "verify_once" if budget_result["budget_tier"] == 1 else
                "verify_loop" if budget_result["budget_tier"] <= 3 else
                "beam_search" if budget_result["budget_tier"] == 4 else
                "full_ttc"
            ),
        },
        "computed_at": time.time(),
    }


# ---------------------------------------------------------------------------
# MCP Tool handlers
# ---------------------------------------------------------------------------

def handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch compute-alloc MCP tool calls."""
    try:
        if name == "read_focus_difficulty_estimate":
            result = estimate_difficulty(
                task_description=args.get("task_description", ""),
                domain=args.get("domain", "general"),
                tool_name=args.get("tool_name", ""),
                input_size=args.get("input_size", 0),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "read_focus_compute_budget":
            difficulty = args.get("difficulty", 0.5)
            max_budget = args.get("max_budget", 5)
            result = allocate_compute_budget(difficulty, max_budget)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "read_focus_allocate_depth":
            result = allocate_depth(
                task_description=args.get("task_description", ""),
                domain=args.get("domain", "general"),
                tool_name=args.get("tool_name", ""),
                input_size=args.get("input_size", 0),
                max_budget=args.get("max_budget", 5),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        else:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"})}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

COMPUTE_ALLOC_TOOLS = [
    {
        "name": "read_focus_difficulty_estimate",
        "description": " READ — Estimate task difficulty (0.0–1.0) using keyword heuristics, input size, domain, and tool type. Returns breakdown for explainability.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "Task description or prompt text"},
                "domain": {"type": "string", "description": "Domain: general, simulation, cad, electrical, gamedev, devops, research, etc."},
                "tool_name": {"type": "string", "description": "Name of the tool being called"},
                "input_size": {"type": "integer", "description": "Size of the input/payload in characters"},
            },
            "required": [],
        },
    },
    {
        "name": "read_focus_compute_budget",
        "description": " READ — Map a difficulty score (0.0–1.0) to a compute budget tier (0-5). Returns label, description, and budget level for use in resource allocation.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "difficulty": {"type": "number", "description": "Difficulty score (0.0–1.0)"},
                "max_budget": {"type": "integer", "description": "Maximum budget tier to allow (0-5)", "default": 5},
            },
            "required": ["difficulty"],
        },
    },
    {
        "name": "read_focus_allocate_depth",
        "description": " READ — Full pipeline: estimate difficulty → map to budget → distribute across reasoning phases (plan/research/implement/verify). Returns recommended strategy.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "Task description or prompt text"},
                "domain": {"type": "string", "description": "Domain for difficulty estimation"},
                "tool_name": {"type": "string", "description": "Tool name"},
                "input_size": {"type": "integer", "description": "Input size in characters"},
                "max_budget": {"type": "integer", "description": "Maximum budget tier (0-5)", "default": 5},
            },
            "required": [],
        },
    },
]


if __name__ == "__main__":
    # Self-test
    print("=== Compute-Alloc Self-Test ===\n")

    # Test 1: Difficulty estimate
    r1 = estimate_difficulty("Debug a multi-threaded deadlock in the simulation engine",
                              domain="simulation", tool_name="read_focus_scope_check", input_size=1500)
    print(f"Difficulty: {r1['difficulty']} (expected >0.5)")
    assert r1["difficulty"] > 0.5, f"Expected >0.5, got {r1['difficulty']}"
    assert 0 <= r1["difficulty"] <= 1.0
    print(f"  Confidence: {r1['confidence']}")

    # Test 2: Trivial task
    r2 = estimate_difficulty("Read current time", domain="general", tool_name="read_focus_scope_check", input_size=10)
    print(f"Trivial difficulty: {r2['difficulty']} (expected <0.2)")
    assert r2["difficulty"] < 0.2

    # Test 3: Budget mapping
    r3 = allocate_compute_budget(0.1)
    print(f"Budget for diff=0.1: tier={r3['budget_tier']} label={r3['label']}")
    assert r3["budget_tier"] == 0

    r4 = allocate_compute_budget(0.8)
    print(f"Budget for diff=0.8: tier={r4['budget_tier']} label={r4['label']}")
    assert r4["budget_tier"] == 4

    # Test 4: Full depth allocation
    r5 = allocate_depth("Design and implement a CFD pipe flow simulation with turbulence modeling",
                         domain="simulation", tool_name="write_sim_cfd_pipe", input_size=3000)
    print(f"Depth allocation: budget={r5['budget']['budget_tier']}, strategy={r5['depth']['recommended_strategy']}")
    assert r5["depth"]["total_units"] > 0
    assert r5["depth"]["recommended_strategy"] in ["full_ttc", "beam_search", "verify_loop"]
    assert sum(r5["depth"]["phases"].values()) >= r5["depth"]["total_units"]

    # Test 5: Zero budget allocation
    r6 = allocate_depth("hello world", domain="general", tool_name="read_focus_global", input_size=5)
    print(f"Trivial depth: budget={r6['budget']['budget_tier']}, strategy={r6['depth']['recommended_strategy']}")
    assert r6["budget"]["budget_tier"] == 0

    print("\nAll self-tests passed.")
