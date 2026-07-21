#!/usr/bin/env python3
"""
beam_search_module.py — Beam Search + PRM (TTC Phase 4)

Given a branching search space (each node has multiple candidate next
steps), beam search keeps the top-k partial solutions at each expansion,
scored by the Process Reward Model (PRM). Low-reward branches are pruned,
concentrating compute on promising paths.

This is a pure search-logic module: it does not execute tools, it ranks
and prunes candidate step-sequences. The DAG coordinator can call it to
choose which branches to materialize.

Algorithm:
  - state = ordered list of steps so far (a partial trajectory)
  - candidates(state) = list of next-step dicts (provided by caller)
  - score(step) = PRM step reward (0..1), or a caller-supplied scorer
  - beam width k: keep k highest-scoring states after each expansion

Analog: the brain's "keep several hypotheses active, drop the weak ones"
behavior in deliberative reasoning (prefrontal branching / winner-take-all).
"""

import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

BEAM_PATH = DATA_DIR / "beam-runs.json"


def _load_runs():
    p = BEAM_PATH
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_runs(runs):
    p = BEAM_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(runs, indent=2), encoding="utf-8")


def _step_reward(step, goal, scorer):
    if scorer is not None:
        return float(scorer(step))
    # default: delegate to PRM heuristic if available, else lexical fallback
    try:
        from engine.prm_module import _score_step
        return _score_step(step, goal=goal)["reward"]
    except Exception:
        text = (step.get("text") or "").lower()
        return 0.5 + 0.5 * min(1.0, len(text.split()) / 12)


def beam_search(
    initial_state,
    candidates_fn,
    beam_width=3,
    max_depth=4,
    goal=None,
    scorer=None,
    run_id=None,
    dry_run=False,
):
    """
    Run beam search over a step space.

    Args:
        initial_state: list of steps (the starting partial trajectory)
        candidates_fn: callable(state) -> list of candidate next-step dicts
        beam_width: k (how many states to keep per layer)
        max_depth: max expansions
        goal: optional goal string for scoring
        scorer: optional callable(step) -> float in [0,1]
        run_id: optional key to persist the run
        dry_run: if True, do not persist

    Returns:
        {
          "best": <state list>, "best_score": float,
          "layers": [ {kept states + scores} ... ],
        }
    """
    states = [{"steps": list(initial_state), "score": 0.0}]

    layers = []
    for depth in range(max_depth):
        expanded = []
        for st in states:
            cands = candidates_fn(st["steps"]) or []
            for c in cands:
                reward = _step_reward(c, goal, scorer)
                # cumulative uses mean reward so long paths don't dominate
                n = len(st["steps"]) + 1
                new_score = (st["score"] * (n - 1) + reward) / n
                expanded.append({
                    "steps": st["steps"] + [c],
                    "score": round(new_score, 4),
                    "last_reward": round(reward, 4),
                })

        if not expanded:
            break

        # keep top-k by score
        expanded.sort(key=lambda x: -x["score"])
        states = expanded[:beam_width]
        layers.append([
            {"score": s["score"], "last_reward": s.get("last_reward"), "steps": s["steps"]}
            for s in states
        ])

    best = max(states, key=lambda x: x["score"]) if states else {"steps": list(initial_state), "score": 0.0}

    result = {
        "best": best["steps"],
        "best_score": best["score"],
        "layers": layers,
        "beam_width": beam_width,
        "max_depth": max_depth,
    }

    if not dry_run:
        runs = _load_runs()
        rid = run_id or f"run_{int(time.time())}"
        runs[rid] = {"result": result, "created_at": time.time()}
        _save_runs(runs)
        result["run_id"] = rid

    return result


def read_run(run_id):
    runs = _load_runs()
    return runs.get(run_id, {"error": "run not found"})


def list_runs():
    return {"runs": list(_load_runs().keys())}


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

BEAM_SEARCH_TOOLS = [
    {
        "name": "read_search_beam",
        "description": " READ — Run beam search over a candidate step space, keeping the top-k partial trajectories scored by the PRM. Returns the best path and per-layer kept states.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "initial_state": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Starting partial trajectory (list of steps)",
                },
                "candidates": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Candidate next-step dicts (text, tool)",
                },
                "beam_width": {"type": "integer", "default": 3, "description": "k: states kept per layer"},
                "max_depth": {"type": "integer", "default": 4, "description": "Max expansions"},
                "goal": {"type": "string", "description": "Goal for PRM scoring"},
                "run_id": {"type": "string", "description": "Persist key for the run"},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["candidates"],
        },
    },
    {
        "name": "read_search_best_of_n",
        "description": " READ — Score N candidate steps with PRM and return the highest-scoring one with full ranking.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "candidates": {"type": "array", "items": {"type": "object"}},
                "goal": {"type": "string"},
            },
            "required": ["candidates"],
        },
    },
    {
        "name": "read_search_beam_read",
        "description": " READ — Recall a persisted beam-search run by id.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "string"}},
            "required": ["run_id"],
        },
    },
    {
        "name": "read_search_beam_list",
        "description": " READ — List all persisted beam-search run ids.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

def handle_tool_call(name, args):
    stripped = name.split("_", 1)[1] if "_" in name else name

    if stripped == "search_beam":
        # candidates are passed inline for a self-contained demo/search
        initial = args.get("initial_state", [])
        raw_candidates = args.get("candidates", [])
        width = args.get("beam_width", 3)
        depth = args.get("max_depth", 4)
        goal = args.get("goal")

        def cands(state):
            # first expansion uses full candidate list; deeper expansions
            # reuse the same list (caller can refine via max_depth)
            return raw_candidates

        return beam_search(
            initial_state=initial,
            candidates_fn=cands,
            beam_width=width,
            max_depth=depth,
            goal=goal,
            run_id=args.get("run_id"),
            dry_run=args.get("dry_run", False),
        )
    elif stripped == "search_best_of_n":
        # generate N candidates, return the highest PRM-scored one
        candidates = args.get("candidates", [])
        goal = args.get("goal")
        if not candidates:
            return {"error": "search_best_of_n requires candidates"}
        scored = [
            {"candidate": c, "reward": _step_reward(c, goal, None)}
            for c in candidates
        ]
        scored.sort(key=lambda x: -x["reward"])
        return {
            "best": scored[0]["candidate"],
            "best_reward": scored[0]["reward"],
            "ranked": scored,
        }
    elif stripped == "search_beam_read":
        return read_run(args.get("run_id"))
    elif stripped == "search_beam_list":
        return list_runs()
    return {"error": f"Unknown beam search tool: {name}"}


if __name__ == "__main__":
    import os
    if BEAM_PATH.exists():
        os.remove(BEAM_PATH)

    print("=== Beam Search Self-Test ===\n")

    # Candidates at each expansion: one good, two weak
    cands_pool = [
        {"text": "Use read_memory_search to pull prior allocator designs", "tool": "read_memory_search"},
        {"text": "um maybe", "tool": ""},
        {"text": "actually no, that's wrong", "tool": ""},
    ]

    def cfn(state):
        return cands_pool

    r = beam_search(
        initial_state=[],
        candidates_fn=cfn,
        beam_width=2,
        max_depth=2,
        goal="design an allocator",
    )
    print("best score:", r["best_score"])
    print("best steps:", [s.get("tool") for s in r["best"]])
    # best path should prefer the good candidate, not the hedging ones
    assert any("read_memory_search" in (s.get("tool") or "") for s in r["best"])
    assert r["best_score"] > 0.5

    # best_of_n
    b = handle_tool_call("read_search_best_of_n", {"candidates": cands_pool, "goal": "design an allocator"})
    print("best_of_n reward:", b["best_reward"], "tool:", b["best"]["tool"])
    assert "read_memory_search" in b["best"]["tool"]

    print("\nALL BEAM SEARCH SELF-TESTS PASSED")
