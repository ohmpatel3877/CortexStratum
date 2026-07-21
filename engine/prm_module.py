#!/usr/bin/env python3
"""
prm_module.py — Process Reward Model (TTC Phase 3)

Scores intermediate reasoning steps (not just final answers) so the agent
can keep high-reward partial solutions and prune dead ends. This is the
step-level upgrade to the existing final-answer verifier.

Design:
  - A "trajectory" is an ordered list of reasoning steps; each step gets a
    reward in [0, 1] from a heuristic scorer (clarity, tool-use fit, progress
    signal, no contradiction).
  - We persist a PRM ledger: per-trajectory cumulative reward + per-step scores.
  - `mutate_prm_prune` drops trajectories whose mean reward falls below a
    threshold (the search-space shrink that beam search relies on).

Zero GPU. The scorer is a transparent heuristic, not a black-box model, so
scores are explainable and debuggable.

Analog: the brain's error-prediction systems (anterior cingulate cortex)
that signal when a reasoning step is going wrong before the final answer.
"""

import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"

PRM_PATH = DATA_DIR / "prm-ledger.json"

# Heuristic weights for the per-step scorer
_W_CLARITY = 0.25      # does the step state what it does
_W_TOOLFIT = 0.25      # does it reference a concrete tool/action
_W_PROGRESS = 0.30     # does it advance toward a stated goal
_W_NOCONTRA = 0.20     # does it avoid self-contradiction


def _load_ledger():
    p = PRM_PATH
    if not p.exists():
        return {"trajectories": {}, "updated": 0}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"trajectories": {}, "updated": 0}


def _save_ledger(ledger):
    p = PRM_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    ledger["updated"] = time.time()
    p.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def _score_step(step, goal=None):
    """
    Heuristic reward for one reasoning step.

    Args:
        step: dict with at least {"text": str, "tool": str (optional)}
        goal: optional stated goal string for progress scoring
    Returns:
        {"reward": float 0..1, "breakdown": {...}}
    """
    text = (step.get("text") or "").strip()
    tool = (step.get("tool") or "").strip()
    low = text.lower()

    clarity = 1.0 if len(text.split()) >= 4 else 0.1

    toolfit = 1.0 if tool else (0.6 if any(k in low for k in ["use ", "call ", "run ", "query ", "read ", "write "]) else 0.1)

    progress = 0.5
    if goal:
        # crude lexical overlap between step and goal => progress signal
        goal_words = set(goal.lower().split())
        step_words = set(low.split())
        if goal_words:
            overlap = len(goal_words & step_words) / len(goal_words)
            progress = 0.3 + 0.7 * min(1.0, overlap * 3)

    # contradiction signal: hedging/self-retraction words
    contra = any(k in low for k in ["actually no", "that's wrong", "nevermind", "contradicts", "i was wrong", "this is wrong"])
    nocon = 0.0 if contra else 1.0

    reward = (
        _W_CLARITY * clarity
        + _W_TOOLFIT * toolfit
        + _W_PROGRESS * progress
        + _W_NOCONTRA * nocon
    )
    reward = max(0.0, min(1.0, reward))

    return {
        "reward": round(reward, 4),
        "breakdown": {
            "clarity": round(clarity, 3),
            "toolfit": round(toolfit, 3),
            "progress": round(progress, 3),
            "nocontra": round(nocon, 3),
        },
    }


# ---------------------------------------------------------------------------
# Score a full trajectory
# ---------------------------------------------------------------------------

def score_trajectory(traj_id, steps, goal=None, dry_run=False):
    """
    Score an ordered list of reasoning steps.

    Args:
        traj_id: string key for the trajectory
        steps: list of {"text": str, "tool": str (opt)}
        goal: optional stated goal
        dry_run: simulate persistence
    """
    if not isinstance(steps, list) or not steps:
        return {"error": "score_trajectory requires a non-empty steps list"}

    per_step = [_score_step(s, goal) for s in steps]
    rewards = [r["reward"] for r in per_step]
    mean = round(sum(rewards) / len(rewards), 4)
    cumulative = round(sum(rewards), 4)

    result = {
        "traj_id": traj_id,
        "steps": len(steps),
        "mean_reward": mean,
        "cumulative_reward": cumulative,
        "per_step": per_step,
    }

    if dry_run:
        result["status"] = "simulated"
        return result

    ledger = _load_ledger()
    ledger["trajectories"][traj_id] = {
        "mean_reward": mean,
        "cumulative_reward": cumulative,
        "steps": len(steps),
        "goal": goal,
        "scored_at": time.time(),
    }
    _save_ledger(ledger)
    result["status"] = "stored"
    return result


# ---------------------------------------------------------------------------
# Status / prune
# ---------------------------------------------------------------------------

def status(traj_id=None):
    ledger = _load_ledger()
    if traj_id:
        return {"traj_id": traj_id, "entry": ledger["trajectories"].get(traj_id)}
    ranked = sorted(
        ledger["trajectories"].items(),
        key=lambda kv: -kv[1].get("mean_reward", 0),
    )
    return {
        "count": len(ranked),
        "top": [{"traj_id": k, "mean_reward": v["mean_reward"]} for k, v in ranked[:5]],
        "updated": ledger.get("updated", 0),
    }


def prune(min_mean_reward=0.4, dry_run=False):
    """Drop trajectories whose mean reward is below the threshold."""
    ledger = _load_ledger()
    removed = []
    for k, v in list(ledger["trajectories"].items()):
        if v.get("mean_reward", 0) < min_mean_reward:
            del ledger["trajectories"][k]
            removed.append(k)
    if not dry_run:
        _save_ledger(ledger)
    return {
        "status": "simulated" if dry_run else "pruned",
        "removed": removed,
        "kept": len(ledger["trajectories"]),
    }


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

PRM_TOOLS = [
    {
        "name": "read_prm_score_step",
        "description": " READ — Score a single reasoning step (0..1) with an explainable heuristic: clarity, tool-fit, progress toward goal, no-contradiction.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The reasoning step text"},
                "tool": {"type": "string", "description": "Tool used in this step (optional)"},
                "goal": {"type": "string", "description": "Stated goal for progress scoring (optional)"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "write_prm_score_trajectory",
        "description": " WRITE — Score an ordered list of reasoning steps as one trajectory; store mean/cumulative reward in the PRM ledger.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "traj_id": {"type": "string", "description": "Trajectory identifier"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "tool": {"type": "string"},
                        },
                    },
                    "description": "Ordered reasoning steps",
                },
                "goal": {"type": "string", "description": "Stated goal (optional)"},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["traj_id", "steps"],
        },
    },
    {
        "name": "read_prm_status",
        "description": " READ — Show PRM ledger status: top trajectories by mean reward, count, last update.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "traj_id": {"type": "string", "description": "If set, show only this trajectory"}
            },
            "required": [],
        },
    },
    {
        "name": "mutate_prm_prune",
        "description": " WRITE — Drop trajectories whose mean reward is below a threshold (search-space shrink for beam search).",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_mean_reward": {"type": "number", "default": 0.4},
                "dry_run": {"type": "boolean", "default": False},
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

    if stripped == "prm_score_step":
        # single-step quick score (no persistence)
        return _score_step(args, goal=args.get("goal"))
    elif stripped == "prm_score_trajectory":
        return score_trajectory(
            traj_id=args.get("traj_id", "default"),
            steps=args.get("steps", []),
            goal=args.get("goal"),
            dry_run=args.get("dry_run", False),
        )
    elif stripped == "prm_status":
        return status(traj_id=args.get("traj_id"))
    elif stripped == "prm_prune":
        return prune(
            min_mean_reward=args.get("min_mean_reward", 0.4),
            dry_run=args.get("dry_run", False),
        )
    return {"error": f"Unknown prm tool: {name}"}


if __name__ == "__main__":
    import os
    if PRM_PATH.exists():
        os.remove(PRM_PATH)

    print("=== PRM Self-Test ===\n")

    # A good trajectory
    good = [
        {"text": "Use read_memory_search to fetch the prior design notes for the allocator", "tool": "read_memory_search"},
        {"text": "Call write_focus_allocate_depth to plan reasoning phases", "tool": "write_focus_allocate_depth"},
        {"text": "Run the compute budget tier mapping and apply it", "tool": "read_focus_compute_budget"},
    ]
    r = score_trajectory("traj_good", good, goal="design an allocator with compute budgeting")
    print("good traj mean:", r["mean_reward"])
    assert r["mean_reward"] > 0.6

    # A bad trajectory (hedging, no tool, no progress)
    bad = [
        {"text": "um", "tool": ""},
        {"text": "actually no, that's wrong, nevermind", "tool": ""},
    ]
    rb = score_trajectory("traj_bad", bad, goal="design an allocator")
    print("bad traj mean:", rb["mean_reward"])
    assert rb["mean_reward"] < r["mean_reward"]

    # prune removes the bad one
    p = prune(min_mean_reward=0.4)
    print("prune removed:", p["removed"])
    assert "traj_bad" in p["removed"]

    print("status:", status())
    print("\nALL PRM SELF-TESTS PASSED")
