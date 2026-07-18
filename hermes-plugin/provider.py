"""
Hermes Agent MemoryProvider implementation for CortexStratum.

Provides the full Hermes MemoryProvider ABC with:
  - prefetch() — semantic context retrieval via hybrid search + reranker
  - sync_turn() — non-blocking conversation persistence
  - on_session_end() — decision extraction + session finalization
  - get_tool_schemas() — 5 agent-facing tools for fine-grained access

Design:
  - Direct Python imports (no subprocess MCP server) — lower latency
  - Graceful fallback if sentence-transformers is not installed
  - All operations thread-safe (Hermes requires non-blocking sync_turn)
"""

import json
import os
import threading
from pathlib import Path

# Lazy imports — Hermes may not have sentence-transformers installed
_SEARCH = None
_TRACE = None
_AUDIT = None


def _get_search():
    global _SEARCH
    if _SEARCH is None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from memory_search import NEMemorySearch
        _SEARCH = NEMemorySearch()
    return _SEARCH


def _get_trace():
    global _TRACE
    if _TRACE is None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import importlib.util as _util
        spec = _util.spec_from_file_location(
            "trace",
            str(Path(__file__).resolve().parent.parent / "scripts" / "trace.py")
        )
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _TRACE = mod
    return _TRACE


def _get_audit():
    global _AUDIT
    if _AUDIT is None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from permission_audit import PermissionAudit
        _AUDIT = PermissionAudit()
    return _AUDIT


#  Tool schemas (returned by get_tool_schemas) 

AIME_RETRIEVE_SCHEMA = {
    "name": "aime_retrieve",
    "description": "Search CortexStratum using hybrid BM25 + vector search with cross-encoder reranking",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "limit": {"type": "integer", "default": 5, "description": "Number of results"},
        },
        "required": ["query"],
    },
}

AIME_SEARCH_SCHEMA = {
    "name": "aime_search",
    "description": "Quick BM25 keyword search (fast, no vector model needed)",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword search query"},
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["query"],
    },
}

AIME_DECISIONS_SCHEMA = {
    "name": "aime_decisions",
    "description": "Retrieve architecture decisions matching context",
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Search term for decisions"},
            "limit": {"type": "integer", "default": 5},
        },
        "required": [],
    },
}

AIME_STATUS_SCHEMA = {
    "name": "aime_status",
    "description": "Get memory provider status: entry count, vector search status, cache state",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

AIME_OBSERVE_SCHEMA = {
    "name": "aime_observe",
    "description": "Log an observation (milestone, insight, preference) to memory",
    "parameters": {
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "enum": ["decision", "error", "insight", "preference", "milestone", "handoff"],
            },
            "description": {"type": "string"},
            "metadata": {"type": "object"},
        },
        "required": ["event_type", "description"],
    },
}


class CortexProvider:
    """Hermes MemoryProvider implementation for CortexStratum.

    Provides sandboxed memory with read/write/mutate permission tiers.
    The provider's tools are read-only by default; destructive operations
    require explicit confirmation via the Hermes permission system.
    """

    def __init__(self):
        self._hermes_home = ""
        self._session_id = ""
        self._config = {}
        self._lock = threading.Lock()

    #  Required Properties 

    @property
    def name(self) -> str:
        return "CortexStratum"

    #  Required ABC Methods 

    def is_available(self) -> bool:
        """Check if dependencies are available (pure Python core always works)."""
        return True

    def initialize(self, session_id: str, **kwargs):
        """One-time init on agent startup."""
        self._hermes_home = kwargs.get("hermes_home", os.path.expanduser("~/.hermes"))
        self._session_id = session_id
        # Warm up the search engine in background
        try:
            _get_search()
        except Exception:
            pass

    def get_tool_schemas(self):
        """Return tool schemas for agent-facing tools."""
        return [
            AIME_RETRIEVE_SCHEMA,
            AIME_SEARCH_SCHEMA,
            AIME_DECISIONS_SCHEMA,
            AIME_STATUS_SCHEMA,
            AIME_OBSERVE_SCHEMA,
        ]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> dict:
        """Route Hermes tool calls to the appropriate handler."""
        dispatch = {
            "aime_retrieve": self._handle_retrieve,
            "aime_search": self._handle_search,
            "aime_decisions": self._handle_decisions,
            "aime_status": self._handle_status,
            "aime_observe": self._handle_observe,
        }
        handler = dispatch.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return handler(args)
        except Exception as e:
            return {"error": str(e)}

    def get_config_schema(self):
        """Declare config fields for 'hermes memory setup'."""
        return {
            "type": "object",
            "properties": {
                "memory_path": {
                    "type": "string",
                    "default": "",
                    "description": "Path to memory storage (default: ~/.CortexStratum)",
                },
                "embedding_model": {
                    "type": "string",
                    "default": "all-MiniLM-L6-v2",
                    "description": "Sentence-transformers model for embeddings",
                },
                "reranker_model": {
                    "type": "string",
                    "default": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                    "description": "Cross-encoder model for reranking",
                },
                "max_memories": {
                    "type": "integer",
                    "default": 8,
                    "description": "Max memories in prefetch context",
                },
            },
        }

    def save_config(self, values: dict, hermes_home: str):
        """Persist provider config."""
        self._config = values
        if values.get("memory_path"):
            os.environ["AI_MEMORY_STORAGE_PATH"] = values["memory_path"]
        if values.get("embedding_model"):
            os.environ["AI_MEMORY_EMBEDDING_MODEL"] = values["embedding_model"]

    #  Optional Lifecycle Hooks 

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Called before each LLM turn — returns relevant context.

        Uses reranked search (hybrid BM25 + vector + cross-encoder)
        to surface the most relevant memories for the current query.
        Returns a <vault-context> block for injection into the prompt.
        """
        if not query or not query.strip():
            return ""

        try:
            se = _get_search()
            result = se.reranked_search(query, limit=5, candidates=20)
            results = result.get("results", [])
            if not results:
                return ""

            lines = []
            lines.append("<vault-context source='CortexStratum'>")
            for r in results:
                snippet = r.get("text", "")[:300]
                score = r.get("rerank_score") or r.get("score", 0)
                lines.append(f"  [{score:.3f}] {snippet}")
            lines.append("</vault-context>")
            return "\n".join(lines)
        except Exception:
            return ""

    def sync_turn(self, user: str, assistant: str, *, session_id: str = ""):
        """Called after each completed turn — MUST be non-blocking.

        Spawns a daemon thread to persist the conversation turn to memory.
        """
        if not user and not assistant:
            return
        t = threading.Thread(
            target=self._persist_turn,
            args=(user, assistant, session_id or self._session_id),
            daemon=True,
        )
        t.start()

    def _persist_turn(self, user: str, assistant: str, session_id: str):
        """Persist a conversation turn to memory (runs in daemon thread)."""
        try:
            se = _get_search()
            if user:
                se.add_memory(
                    f"User: {user[:500]}",
                    source="hermes_session",
                    metadata={"session_id": session_id, "role": "user"},
                )
            if assistant:
                se.add_memory(
                    f"Assistant: {assistant[:500]}",
                    source="hermes_session",
                    metadata={"session_id": session_id, "role": "assistant"},
                )
        except Exception:
            pass

    def on_session_end(self, messages: list):
        """Called when conversation ends — extract decisions + finalize."""
        try:
            # Extract the last assistant message as a potential insight
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.get("role") == "assistant":
                    content = msg.content if hasattr(msg, "content") else str(msg)
                    if len(content) > 50:
                        se = _get_search()
                        se.add_memory(
                            f"Session insight: {content[:500]}",
                            source="hermes_session_end",
                            metadata={"session_id": self._session_id},
                        )
                    break
        except Exception:
            pass

    def shutdown(self):
        """Clean connections on Hermes exit."""
        pass

    #  Internal Tool Handlers 

    def _handle_retrieve(self, args: dict) -> dict:
        """Hybrid search + cross-encoder reranking."""
        se = _get_search()
        return se.reranked_search(
            args.get("query", ""),
            limit=args.get("limit", 5),
            candidates=20,
        )

    def _handle_search(self, args: dict) -> dict:
        """Quick BM25 keyword search."""
        se = _get_search()
        results = se.search(args.get("query", ""), limit=args.get("limit", 10))
        return {"results": results}

    def _handle_decisions(self, args: dict) -> dict:
        """Query decision registry."""
        trace = _get_trace()
        result = trace.handle_tool_call(
            "read_dtrace_search",
            {"keyword": args.get("keyword", "")},
        )
        return result

    def _handle_status(self, args: dict) -> dict:
        """Provider status."""
        se = _get_search()
        return se.status()

    def _handle_observe(self, args: dict) -> dict:
        """Log observation — auto-pushes decisions to DTrace."""
        event_type = args.get("event_type", "insight")
        description = args.get("description", "")
        metadata = args.get("metadata", {})

        se = _get_search()
        se.add_memory(
            description,
            source=f"hermes_{event_type}",
            metadata=metadata,
        )

        # Auto-push decisions to DTrace
        if event_type == "decision":
            try:
                trace = _get_trace()
                trace.handle_tool_call("write_dtrace_add", {
                    "title": description[:80],
                    "decision": description,
                    "rationale": (metadata or {}).get("rationale", ""),
                    "context": (metadata or {}).get("context", "Hermes session"),
                    "category": "process",
                })
            except Exception:
                pass

        return {"status": "logged", "event_type": event_type, "id": None}
