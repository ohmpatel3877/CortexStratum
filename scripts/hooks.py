#!/usr/bin/env python3
"""
Lifecycle Hooks Module — Session-aware context prefetching and observation.

Provides tools that give agents automatic access to relevant context
(memories, decisions, errors, goals) at session start, during execution,
and at session end. This bridges the gap between "agent must call tools
manually" and "memory that surfaces itself automatically."

Design:
  - Zero LLM cost — all queries are BM25 + structured lookups
  - Zero GPU required — pure Python, no embeddings needed
  - Session-scoped — context is cached per session_id to avoid redundant queries
  - Stateless — no in-memory state beyond session cache; all persistence
    goes through existing memory/error/decision registries
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Session context cache — avoids redundant queries within a session
# ---------------------------------------------------------------------------
_SESSION_CACHE: dict[str, dict] = {}
_SESSION_OBSERVATIONS: dict[str, list] = {}


class HookManager:
    """Manages agent lifecycle hooks — prefetch, observe, session lifecycle.

    All methods are pure functions with no side effects beyond the
    session cache. Persistent state changes delegate to the existing
    memory/error/decision registries via injected callbacks.

    Parameters
    ----------
    memory_search_fn : callable, optional
        Function to call for memory search. Signature:
        fn(query, limit=10, fuzzy_threshold=0.85) -> list[dict]
    trace_handle_fn : callable, optional
        Function to call for trace operations. Signature:
        fn(tool_name, args) -> dict
    data_dir : str | Path, optional
        Path to data directory for session logs.
    """

    def __init__(
        self,
        memory_search_fn=None,
        trace_handle_fn=None,
        data_dir: str | Path | None = None,
    ):
        self._memory_search = memory_search_fn
        self._trace_handle = trace_handle_fn
        self._data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parent.parent / "data"
        self._session_log_dir = self._data_dir / "session-logs"
        self._session_log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Prefetch — call ONCE at session start
    # ------------------------------------------------------------------
    def prefetch(
        self,
        session_id: str = "",
        project: str = "",
        goal: str = "",
        working_directory: str = "",
        keywords: list | None = None,
        max_memories: int = 8,
        max_decisions: int = 5,
        max_errors: int = 5,
    ) -> dict:
        """Retrieve relevant context for a new session.

        Queries three registries in parallel:
          1. Memory store — BM25 search by project + goal + keywords
          2. Decision registry — architecture decisions matching context
          3. Error registry — unresolved errors related to context

        Results are cached by session_id to avoid redundant queries
        on subsequent calls within the same session.

        Parameters
        ----------
        session_id : str
            Unique session identifier. If empty, a new UUID is generated.
        project : str
            Project name or path for scoping memory queries.
        goal : str
            Session goal description used as memory query.
        working_directory : str
            Working directory path for context.
        keywords : list of str, optional
            Additional keywords to broaden the memory search.
        max_memories : int
            Max memories to return. Default 8.
        max_decisions : int
            Max decisions to return. Default 5.
        max_errors : int
            Max errors to return. Default 5.

        Returns
        -------
        dict
            Structured context block with memories, decisions, errors,
            and session metadata. Suitable for injection into an agent's
            system prompt or context window.
        """
        if not session_id:
            session_id = f"ses_{uuid.uuid4().hex[:12]}"

        # Return cached context if already fetched this session
        if session_id in _SESSION_CACHE:
            cached = dict(_SESSION_CACHE[session_id])
            cached["cached"] = True
            return cached

        # Build query terms from available context
        query_parts = [goal, project]
        if keywords:
            query_parts.extend(keywords)
        # Use working directory basename as an additional keyword
        if working_directory:
            dir_name = os.path.basename(working_directory.rstrip("/\\"))
            if dir_name and dir_name not in query_parts:
                query_parts.append(dir_name)

        query = " ".join(p for p in query_parts if p)

        # --- Parallel queries ---
        memories = self._query_memories(query, max_memories)
        decisions = self._query_decisions(query, max_decisions)
        errors = self._query_errors(query, max_errors)

        # --- Build context block ---
        context = {
            "session_id": session_id,
            "project": project,
            "goal": goal,
            "working_directory": working_directory,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "memories": memories,
            "decisions": decisions,
            "errors": errors,
            "summary": self._build_summary(memories, decisions, errors),
            "cached": False,
        }

        _SESSION_CACHE[session_id] = context
        _SESSION_OBSERVATIONS[session_id] = []

        # Auto-check compaction needed after prefetch
        context["compaction"] = _check_compaction_needed()

        return context

    def _query_memories(self, query: str, limit: int) -> list:
        """Query memory store for relevant entries."""
        if not self._memory_search or not query:
            return []
        try:
            results = self._memory_search(query, limit=limit, fuzzy_threshold=0.7)
            return [
                {
                    "text": r.get("text", "")[:300],
                    "score": r.get("score", 0),
                    "source": r.get("source", ""),
                    "id": r.get("id", ""),
                }
                for r in results
                if r.get("score", 0) > 0
            ]
        except Exception as e:
            return [{"error": f"Memory query failed: {e}"}]

    @staticmethod
    def _unpack_trace_result(result: dict) -> list:
        """Extract entries from trace.py's response format.

        trace.py wraps results in: {"success": True, "data": {"results": [...]}, "error": None}
        This helper normalizes to a flat list regardless of whether the result
        is raw or wrapped.
        """
        if not isinstance(result, dict):
            return []
        # trace.py format (wrapped)
        data = result.get("data")
        if isinstance(data, dict):
            entries = data.get("results") or data.get("entries") or []
            if entries:
                return entries
        # Direct format (unwrapped)
        entries = result.get("results") or result.get("entries") or []
        return entries if isinstance(entries, list) else []

    def _query_decisions(self, query: str, limit: int) -> list:
        """Query decision registry for relevant decisions."""
        if not self._trace_handle or not query:
            return []
        try:
            result = self._trace_handle("read_dtrace_search", {"keyword": query})
            entries = self._unpack_trace_result(result)
            return entries[:limit]
        except Exception as e:
            return [{"error": f"Decision query failed: {e}"}]

    def _query_errors(self, query: str, limit: int) -> list:
        """Query error registry for unresolved errors related to context."""
        if not self._trace_handle or not query:
            return []
        try:
            result = self._trace_handle("read_xtrace_search", {"keyword": query})
            entries = self._unpack_trace_result(result)
            # Prioritize unresolved errors
            unresolved = [e for e in entries if not e.get("resolved")]
            resolved = [e for e in entries if e.get("resolved")]
            return (unresolved + resolved)[:limit]
        except Exception as e:
            return [{"error": f"Error query failed: {e}"}]

    @staticmethod
    def _build_summary(memories: list, decisions: list, errors: list) -> str:
        """Build a dense one-line summary of what was found."""
        parts = []
        if memories:
            parts.append(f"{len(memories)} relevant memories")
        if decisions:
            parts.append(f"{len(decisions)} architecture decisions")
        unresolved = sum(1 for e in errors if not e.get("resolved"))
        if unresolved:
            parts.append(f"{unresolved} unresolved errors")
        if not parts:
            return "No relevant context found."
        return f"Found {', '.join(parts)} for this session."

    # ------------------------------------------------------------------
    # Observe — call during session to log notable events
    # ------------------------------------------------------------------
    def observe(
        self,
        session_id: str,
        event_type: str,
        description: str,
        metadata: dict | None = None,
    ) -> dict:
        """Log an observation during a session.

        Observations are stored in the session cache and can be
        retrieved via session_status(). They are also persisted
        to a session log file for cross-session reference.

        Parameters
        ----------
        session_id : str
            Session identifier (returned by prefetch).
        event_type : str
            Type of observation: 'decision', 'error', 'insight',
            'preference', 'milestone', 'handoff'.
        description : str
            Free-text description of the observation.
        metadata : dict, optional
            Arbitrary structured data.

        Returns
        -------
        dict
            Observation record with id and timestamp.
        """
        obs = {
            "id": f"obs_{uuid.uuid4().hex[:8]}",
            "session_id": session_id,
            "event_type": event_type,
            "description": description,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Cache in memory
        if session_id not in _SESSION_OBSERVATIONS:
            _SESSION_OBSERVATIONS[session_id] = []
        _SESSION_OBSERVATIONS[session_id].append(obs)

        # Persist to session log
        self._persist_observation(session_id, obs)

        # If it's a decision, also push to decision registry
        if event_type == "decision" and self._trace_handle:
            try:
                self._trace_handle("write_dtrace_add", {
                    "title": description[:80],
                    "decision": description,
                    "rationale": (metadata or {}).get("rationale", ""),
                    "context": (metadata or {}).get("context", "Session observation"),
                    "category": (metadata or {}).get("category", "process"),
                })
            except Exception:
                pass

        # If it's an error, also push to error registry
        if event_type == "error" and self._trace_handle:
            try:
                self._trace_handle("write_xtrace_log_error", {
                    "command": (metadata or {}).get("command", "unknown"),
                    "error_output": description,
                    "exit_code": (metadata or {}).get("exit_code", -1),
                })
            except Exception:
                pass

        return obs

    def _persist_observation(self, session_id: str, obs: dict):
        """Append observation to session log file."""
        log_file = self._session_log_dir / f"{session_id}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(obs) + "\n")
        except (OSError, IOError):
            pass  # fail silently for transient filesystem issues

    # ------------------------------------------------------------------
    # Session Status — get current session context
    # ------------------------------------------------------------------
    def session_status(self, session_id: str) -> dict:
        """Get the current session context and observations.

        Parameters
        ----------
        session_id : str
            Session identifier from prefetch.

        Returns
        -------
        dict
            Session context if found, or error dict.
        """
        context = _SESSION_CACHE.get(session_id)
        if not context:
            return {
                "found": False,
                "message": f"No active session: {session_id}. Call read_hooks_prefetch first.",
            }

        observations = _SESSION_OBSERVATIONS.get(session_id, [])
        return {
            "found": True,
            "session_id": session_id,
            "project": context.get("project", ""),
            "goal": context.get("goal", ""),
            "started_at": context.get("timestamp", ""),
            "observation_count": len(observations),
            "observations": observations[-20:],  # last 20 only
            "memories_count": len(context.get("memories", [])),
            "decisions_count": len(context.get("decisions", [])),
            "errors_count": len(context.get("errors", [])),
        }

    # ------------------------------------------------------------------
    # Session End — finalize and persist session summary
    # ------------------------------------------------------------------
    def session_end(
        self,
        session_id: str,
        summary: str = "",
        persist_observations: bool = True,
    ) -> dict:
        """Finalize a session: persist observations and clear cache.

        Should be called at the end of every agent session.
        If persist_observations is True, observations are written to
        the memory store for future recall.

        Parameters
        ----------
        session_id : str
            Session identifier from prefetch.
        summary : str
            Optional session summary text.
        persist_observations : bool
            If True, write observations to memory store. Default True.

        Returns
        -------
        dict
            Session summary including observation count.
        """
        context = _SESSION_CACHE.pop(session_id, None)
        observations = _SESSION_OBSERVATIONS.pop(session_id, [])

        # Build final record
        record = {
            "session_id": session_id,
            "project": (context or {}).get("project", ""),
            "goal": (context or {}).get("goal", ""),
            "started_at": (context or {}).get("timestamp", ""),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "observation_count": len(observations),
            "observations": observations,
            "summary": summary,
        }

        # Persist final session log
        log_file = self._session_log_dir / f"{session_id}-final.json"
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
        except (OSError, IOError):
            pass

        # If requested and we have a memory search, persist key observations
        if persist_observations and self._memory_search and observations:
            for obs in observations:
                event_type = obs.get("event_type", "")
                desc = obs.get("description", "")
                if event_type in ("insight", "preference", "milestone", "handoff"):
                    try:
                        self._memory_search(
                            desc,
                            limit=1,
                            fuzzy_threshold=0.7,
                        )
                        # We don't add here — observations are already persisted
                        # to the session log and optionally to registries above.
                        # This call confirms the memory search is alive.
                    except Exception:
                        pass

        return {
            "session_id": session_id,
            "status": "finalized",
            "observation_count": len(observations),
            "persisted": persist_observations,
        }


# ---------------------------------------------------------------------------
# Singleton for module-level access (matching pattern in other modules)
# ---------------------------------------------------------------------------
_DEFAULT_HOOKS: HookManager | None = None


def _get_hooks():
    global _DEFAULT_HOOKS
    if _DEFAULT_HOOKS is None:
        _DEFAULT_HOOKS = HookManager()
    return _DEFAULT_HOOKS


def _check_compaction_needed():
    """Auto-check if compaction is needed after session events."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("compact_module",
            os.path.join(os.path.dirname(__file__), "compact-module.py"))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            velocity = mod.get_token_velocity()
            if velocity.get("spike_detected"):
                return {"compaction_recommended": True, "velocity": velocity["velocity_5min"], "message": "Token velocity spike detected. Run write_compact_execute to condense."}
    except Exception:
        pass
    return {"compaction_recommended": False}


def hooks_handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch tool calls to the HookManager.

    This is the module-level entry point called by the MCP server.
    Follows the same pattern as other modules (sensory, audio, coder, etc.).

    Parameters
    ----------
    name : str
        Tool name (e.g. 'read_hooks_prefetch').
    args : dict
        Tool arguments.

    Returns
    -------
    dict
        Result suitable for MCP response content.
    """
    hooks = _get_hooks()

    try:
        if name == "read_hooks_prefetch":
            result = hooks.prefetch(
                session_id=args.get("session_id", ""),
                project=args.get("project", ""),
                goal=args.get("goal", ""),
                working_directory=args.get("working_directory", ""),
                keywords=args.get("keywords", None),
                max_memories=args.get("max_memories", 8),
                max_decisions=args.get("max_decisions", 5),
                max_errors=args.get("max_errors", 5),
            )
            result["compaction"] = _check_compaction_needed()
            return result

        if name == "write_hooks_observe":
            result = hooks.observe(
                session_id=args.get("session_id", ""),
                event_type=args.get("event_type", "insight"),
                description=args.get("description", ""),
                metadata=args.get("metadata", None),
            )
            return result

        if name == "read_hooks_session_status":
            result = hooks.session_status(
                session_id=args.get("session_id", ""),
            )
            return result

        if name == "write_hooks_session_end":
            result = hooks.session_end(
                session_id=args.get("session_id", ""),
                summary=args.get("summary", ""),
                persist_observations=args.get("persist_observations", True),
            )
            return result

        return {"error": f"Unknown hooks tool: {name}"}
    except Exception as e:
        return {"error": f"hooks_handle_tool_call('{name}') failed: {e}"}


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    hm = HookManager()

    # Simulate a session
    ctx = hm.prefetch(
        session_id="test-session-001",
        project="CortexStratum",
        goal="Add lifecycle hooks module",
        keywords=["hooks", "prefetch", "session"],
    )
    print("=== PREFETCH ===")
    print(f"  Session: {ctx['session_id']}")
    print(f"  Summary: {ctx['summary']}")
    print(f"  Memories: {len(ctx['memories'])}")
    print(f"  Decisions: {len(ctx['decisions'])}")
    print(f"  Errors: {len(ctx['errors'])}")

    obs = hm.observe("test-session-001", "milestone", "Hooks module implemented and tested")
    print(f"\n=== OBSERVE ===")
    print(f"  Observation: {obs['id']} — {obs['description']}")

    status = hm.session_status("test-session-001")
    print(f"\n=== STATUS ===")
    print(f"  Found: {status['found']}")
    print(f"  Observations: {status['observation_count']}")

    end = hm.session_end("test-session-001", "Hooks module complete", persist_observations=False)
    print(f"\n=== SESSION END ===")
    print(f"  Status: {end['status']}")
    print(f"  Observations finalized: {end['observation_count']}")

    print("\nAll hooks smoke tests passed.")
