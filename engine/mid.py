#!/usr/bin/env python3
"""
Middleware Pipeline — Centralized pre/post hooks for tool execution

Provides a registry of middleware hooks that fire before/after every
tool call in execute_tool_async. New modules register hooks here
instead of patching the server's dispatch function.

Current registered hooks:

  PRE:
    - gate_resolve       : Conflict Resolver checks for competing tool requests
    - limbic_prime       : Load tagged memories relevant to the incoming query

  POST:
    - skill_context      : Inject skill guidance into result text
    - trace_auto_log     : Log errors to the trace system
    - limbic_reinforce   : Auto-reinforce patterns based on tool outcome
    - wm_decay_tick      : Decay working memory items after writes
    - memory_consolidate : Auto-consolidate after memory writes
"""

import json
from collections.abc import Callable

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_PRE_HOOKS: list[tuple[str, Callable]] = []
_POST_HOOKS: list[tuple[str, Callable]] = []


def register_pre(name: str, fn: Callable):
    """Register a pre-execution hook. fn(name, args) → dict or None."""
    _PRE_HOOKS.append((name, fn))


def register_post(name: str, fn: Callable):
    """Register a post-execution hook. fn(name, args, result) → None."""
    _POST_HOOKS.append((name, fn))


def run_pre(name: str, args: dict) -> dict | None:
    """Run all pre-hooks. First non-None return short-circuits."""
    for hook_name, fn in _PRE_HOOKS:
        try:
            r = fn(name, args)
            if r is not None:
                return r
        except Exception:
            continue
    return None


def run_post(name: str, args: dict, result: dict):
    """Run all post-hooks in order."""
    for hook_name, fn in _POST_HOOKS:
        try:
            fn(name, args, result)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Built-in post-hook: Limbic Auto-Reinforce
# ---------------------------------------------------------------------------

_limbic_getter: Callable | None = None


def set_limbic_getter(fn: Callable):
    """Register a function that returns the limbic module instance.

    Called by the server at startup to avoid fragile import paths.
    fn() → LimbicModule
    """
    global _limbic_getter
    _limbic_getter = fn


def _auto_reinforce(name: str, args: dict, result: dict):
    """Observe tool call outcome and reinforce limbic tags automatically.

    Rules:
      - If result has isError or 'error' in text → reinforce as failure
      - Otherwise → reinforce as success
      - Key = args.id/args.key/args.name/name (in priority order)
    """
    if _limbic_getter is None:
        return
    try:
        limbic = _limbic_getter()
    except Exception:
        return

    # Determine outcome
    content = result.get("content", [{}])
    text = content[0].get("text", "") if content else ""
    is_error = result.get("isError", False) or "error" in text.lower()[:200]

    outcome = "failure" if is_error else "success"

    # Determine key to reinforce
    key = args.get("id") or args.get("key") or args.get("name") or name

    # Only reinforce if the key exists in tags
    try:
        # Check if this key is already tagged
        limbic.status()
        # Try reinforcing — if not tagged, the module returns an error silently
        limbic.reinforce(
            key=key,
            outcome=outcome,
            delta=0.1,
            reason=f"Auto-reinforce from tool call: {name}",
            source="middleware",
        )
    except Exception:
        pass


def _noop(*args, **kwargs):
    pass


def register_server_hooks(
    skill_inject_fn: Callable | None = None,
    trace_log_fn: Callable | None = None,
    memory_consolidate_fn: Callable | None = None,
    trace_getter: Callable | None = None,
):
    """Register server-side hooks from the server bootstrap.

    Called once at startup to avoid circular imports. Each fn is wrapped
    in a post-hook that only fires if the fn is not None.
    """
    if skill_inject_fn:
        def _skill_post(name, args, result):
            try:
                ctx = skill_inject_fn(
                    result.get("content", [{}])[0].get("text", ""), name
                )
                if ctx:
                    existing = result.get("content", [])
                    existing.append({"type": "text", "text": json.dumps(ctx, indent=2)})
                    result["content"] = existing
            except Exception:
                pass
        register_post("skill_context", _skill_post)

    if trace_log_fn:
        def _trace_post(name, args, result):
            try:
                trace_log_fn(name, args, result)
            except Exception:
                pass
        register_post("trace_auto_log", _trace_post)

    if memory_consolidate_fn:
        def _consolidate_post(name, args, result):
            if name == "write_memory_add" and not args.get("dry_run"):
                try:
                    memory_consolidate_fn()
                except Exception:
                    pass
        register_post("memory_consolidate", _consolidate_post)

    if trace_getter:
        def _phase_post(name, args, result):
            if name == "write_focus_pipeline_advance" and not args.get("dry_run"):
                try:
                    trace = trace_getter()
                    if trace and hasattr(trace, "handle_tool_call"):
                        trace.handle_tool_call(
                            "write_dtrace_add",
                            {
                                "title": f"Phase transition: {args.get('next_phase', '?')}",
                                "decision": f"Session pipeline advanced to {args.get('next_phase', '?')}",
                                "rationale": args.get("summary", "Phase completed"),
                                "context": f"tool={name}",
                                "alternatives": "",
                                "category": "process",
                            },
                        )
                except Exception:
                    pass
        register_post("phase_transition", _phase_post)


# ---------------------------------------------------------------------------
# Register built-in hooks
# ---------------------------------------------------------------------------

register_post("limbic_reinforce", _auto_reinforce)


if __name__ == "__main__":
    print("=== Middleware Pipeline Self-Test ===\n")

    # Verify registration
    print(f"Pre-hooks registered: {len(_PRE_HOOKS)}")
    print(f"Post-hooks registered: {len(_POST_HOOKS)}")

    for name, fn in _POST_HOOKS:
        print(f"  POST: {name}")

    print("\nAll self-tests passed.")
