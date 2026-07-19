"""
model_profile.py — Declared capability tiers for model-adaptive orchestration (stdlib only).

The server cannot introspect the active model's real capability (no self-report API), so the
tier is DECLARED: via env var CORTEX_MODEL_TIER, or a set_model_profile tool call. This is
honest — it does not fake detection. The tier changes HOW the server orchestrates:

  small     : lightweight path. Lower DAG retry budget, simpler renudge strategy
              (override only, no halt), heavy simulation modules off, verification relaxed.
  standard  : balanced defaults (matches current hard-coded behavior).
  frontier  : aggressive. Max retries, all renudge strategies allowed, heavy modules on,
              strict verification.

read_tier() returns the active tier (env > in-memory override > 'standard' default).
"""

from __future__ import annotations
import os

TIERS = ("small", "standard", "frontier")
DEFAULT_TIER = "standard"

# In-memory override set by set_model_profile(); env wins unless override is explicit.
_override: str | None = None

# Per-tier behavioral knobs (real, consulted by the server).
PROFILE = {
    "small": {
        "dag_max_retries": 1,
        "allowed_renudge": ("override", "incremental"),
        "heavy_modules": False,          # art/coder/devops/gamedev/off
        "strict_verify": False,
        "note": "lightweight path; conservative retries, no halt renudge",
    },
    "standard": {
        "dag_max_retries": 2,
        "allowed_renudge": ("override", "incremental", "halt", "rollback"),
        "heavy_modules": True,
        "strict_verify": True,
        "note": "balanced defaults",
    },
    "frontier": {
        "dag_max_retries": 4,
        "allowed_renudge": ("override", "incremental", "halt", "rollback"),
        "heavy_modules": True,
        "strict_verify": True,
        "note": "aggressive; max retries, all strategies, strict verification",
    },
}


def set_tier(tier: str) -> str:
    global _override
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}; expected one of {TIERS}")
    _override = tier
    return tier


def read_tier() -> str:
    env = os.environ.get("CORTEX_MODEL_TIER", "").strip().lower()
    if env in TIERS:
        return env
    if _override in TIERS:
        return _override
    return DEFAULT_TIER


def profile() -> dict:
    return PROFILE[read_tier()]


def allows_renudge(strategy: str) -> bool:
    return strategy in profile()["allowed_renudge"]


def dag_retries(default: int) -> int:
    return profile()["dag_max_retries"]


def heavy_modules_enabled() -> bool:
    return profile()["heavy_modules"]
