#!/usr/bin/env python3
"""
MCP Server: CortexStratum Toolchain
122 tools: memory, trace, compact, mutation,
plumber, focus, pedagogy, consolidation, sensory, audio, coder, devops, gamedev,
art, lit, verifier, hooks, skill router, goal registry, commitment checker,
dag, workstream, skills, agents.

All tools have MCP annotations (destructiveHint, readOnlyHint).
All write/mutate tools accept dry_run=true for preview.
"""

import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

TOOL_EXECUTOR_TIMEOUT = 60
POLL_INTERVAL = 0.5

PERMISSION_READ = "read"
PERMISSION_WRITE = "write"
PERMISSION_MUTATE = "mutate"

PERMISSIVE_MODE = False
DEBUG_MODE = False
_SCRIPT_DIR = Path(__file__).resolve().parent
_VERSION_FILE = _SCRIPT_DIR.parent / "VERSION"
try:
    VERSION = _VERSION_FILE.read_text(encoding="utf-8").strip()
except Exception:
    VERSION = "0.5.1-dev"  # fallback


def _log(level, msg):
    if DEBUG_MODE or level in ("ERROR", "WARN"):
        print(f"[mcp-server] [{level}] {msg}", file=sys.stderr, flush=True)


def can_call_tool(tool_name, context=None):
    if PERMISSIVE_MODE:
        return (True, "permissive mode")
    permission = None
    for t in TOOLS:
        if t["name"] == tool_name:
            permission = t.get("permission", PERMISSION_READ)
            break
    if permission is None:
        return (False, f"Unknown tool: {tool_name}")
    mode = (context or {}).get("mode", "interactive")
    if mode == "auto" and permission != PERMISSION_READ:
        return (
            False,
            f"Tool '{tool_name}' requires {permission} permission — blocked in auto mode. Fix: start server with --permissive flag, or pass dry_run=true to preview.",
        )
    if permission in (PERMISSION_WRITE, PERMISSION_MUTATE):
        return (
            True,
            f" {tool_name} modifies persistent state ({permission} permission). Use dry_run=true to preview before committing.",
        )
    return (True, "ok")


_verifier = None
_memory_search = None
_MODULE_CACHE = {}


def _get_module(name, filename):
    if name not in _MODULE_CACHE:
        import importlib.util as _util

        fp = SCRIPTS_DIR / filename
        if not fp.exists():
            raise FileNotFoundError(f"Module not found: {fp}")
        spec = _util.spec_from_file_location(name, str(fp))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODULE_CACHE[name] = mod
    return _MODULE_CACHE[name]


def _get_verifier():
    global _verifier
    if _verifier is None:
        mod = _get_module("verifier_middleware", "verifier_middleware.py")
        _verifier = mod.VerifierMiddleware(mode="advisory")
    return _verifier


def _get_memory_search():
    global _memory_search
    if _memory_search is None:
        mod = _get_module("memory_search_mod", "memory_search.py")
        _memory_search = mod.NEMemorySearch()
    return _memory_search


def _get_trace():
    return _get_module("trace", "trace.py")


def _is_permission(name, permissions):
    for t in TOOLS:
        if t["name"] == name:
            return t.get("permission") in permissions
    return False


def _get_audit():
    return _get_module("permission_audit", "permission_audit.py")._get_audit()


BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent
SCRIPTS_DIR = BASE
DATA_DIR = PROJECT_ROOT / "data"
SKILLS_DIR = PROJECT_ROOT / "skills"


def read_exact(n):
    buf = b""
    while len(buf) < n:
        chunk = sys.stdin.buffer.read(n - len(buf))
        if not chunk:
            raise EOFError(f"Expected {n} bytes, got {len(buf)}")
        buf += chunk
    return buf


def _inject_skill_context(content_text, tool_name):
    """Match tool name against skill router triggers by checking each name segment."""
    try:
        router_path = SKILLS_DIR / "skill-router.json"
        if not router_path.exists():
            return None
        router = json.loads(router_path.read_text(encoding="utf-8"))
        # Split tool name into meaningful segments: read_xtrace_status -> [xtrace, status]
        parts = [
            p
            for p in tool_name.lower().split("_")
            if p not in ("read", "write", "mutate")
        ]
        task_text = " ".join(parts)
        matched = []
        for rule in router.get("rules", []):
            for t in rule.get("triggers", []):
                tl = t.lower()
                # Check if trigger is a substring of any part, or any part contains trigger
                if tl in task_text or any(tl in p or p in tl for p in parts):
                    for s in rule.get("skills", []):
                        if s not in matched:
                            matched.append(s)
                    break
            if len(matched) >= 2:
                break
        if matched:
            return {
                "skill_context": {"matched_skills": matched, "source_tool": tool_name}
            }
    except Exception:
        pass
    return None


def _auto_log_tool_error(name, args, result):
    """If a tool result contains an error, auto-log to xTrace error registry."""
    try:
        content = result.get("content", [{}])[0].get("text", "")
        if not content:
            return
        parsed = json.loads(content) if isinstance(content, str) else content
        error_text = ""
        if isinstance(parsed, dict):
            error_text = parsed.get("error", "") or parsed.get("errors", "")
            if isinstance(error_text, list):
                error_text = "; ".join(error_text)
        if error_text:
            trace = _get_trace()
            trace.handle_tool_call(
                "write_xtrace_log_error",
                {
                    "command": name,
                    "error_output": str(error_text)[:500],
                    "exit_code": 1,
                },
            )
    except Exception:
        pass


def execute_tool_async(name, args, result_queue):
    try:
        result = handle_tool_call(name, args)
        # Cross-pipeline post-processing
        skill_ctx = _inject_skill_context(
            result.get("content", [{}])[0].get("text", ""), name
        )
        if skill_ctx:
            # Append skill context to the result content
            existing = result.get("content", [])
            existing.append({"type": "text", "text": json.dumps(skill_ctx, indent=2)})
            result["content"] = existing
        # Auto-log errors to trace system
        _auto_log_tool_error(name, args, result)
        # Broadcast phase transitions to trace
        if name == "write_focus_pipeline_advance" and not args.get("dry_run"):
            try:
                trace = _get_trace()
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
        # Trigger consolidation after memory writes
        if name == "write_memory_add" and not args.get("dry_run"):
            try:
                mem = _get_memory_search()
                mem.consolidate(threshold=0.92, dry_run=False)
            except Exception:
                pass
        result_queue.put(("result", result))
    except Exception as e:
        result_queue.put(("error", str(e)))


#
# TOOL DEFINITIONS (159 tools, all annotated)
#


def A(d):
    return {
        "destructiveHint": d,
        "readOnlyHint": not d,
        "idempotentHint": not d,
        "openWorldHint": False,
    }


def DR():
    return {
        "type": "boolean",
        "default": False,
        "description": "Preview without executing",
    }


TOOLS = [
    #  xTrace Error Registry
    {
        "name": "write_xtrace_log_error",
        "description": " WRITE — Log an error to the xTrace registry. Use dry_run=true to preview before persisting.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "error_output": {"type": "string"},
                "exit_code": {"type": "integer"},
                "dry_run": DR(),
            },
            "required": ["command", "error_output"],
        },
    },
    {
        "name": "read_xtrace_search",
        "description": " READ — Search the error registry by keyword.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"keyword": {"type": "string"}},
            "required": ["keyword"],
        },
    },
    {
        "name": "read_xtrace_status",
        "description": " READ — Get error tracking summary statistics.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    #  DTrace Decision Registry
    {
        "name": "write_dtrace_add",
        "description": " WRITE — Register an architecture decision. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "context": {"type": "string"},
                "decision": {"type": "string"},
                "alternatives": {"type": "string"},
                "rationale": {"type": "string"},
                "category": {
                    "type": "string",
                    "enum": ["architecture", "process", "technology", "security"],
                },
                "dry_run": DR(),
            },
            "required": ["title", "decision", "rationale"],
        },
    },
    {
        "name": "read_dtrace_search",
        "description": " READ — Search the decision registry by keyword.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"keyword": {"type": "string"}},
            "required": ["keyword"],
        },
    },
    #  Skill Router
    {
        "name": "read_skill_router_match",
        "description": " READ — Match a task to registered skills by intent.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"task": {"type": "string"}},
            "required": ["task"],
        },
    },
    #  Tool Router
    {
        "name": "read_tools_suggest",
        "description": " READ — Suggest MCP tools for a given task.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Describe what you want to do",
                },
                "top_k": {"type": "integer", "default": 3},
            },
            "required": ["task"],
        },
    },
    #  Goal Registry
    {
        "name": "write_goal_registry_init",
        "description": " WRITE — Initialize a new goal. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"goal": {"type": "string"}, "dry_run": DR()},
            "required": ["goal"],
        },
    },
    {
        "name": "write_goal_registry_add_subgoal",
        "description": " WRITE — Add a sub-goal to the current goal. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"description": {"type": "string"}, "dry_run": DR()},
            "required": ["description"],
        },
    },
    {
        "name": "read_goal_registry_status",
        "description": " READ — View current goal stack state.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_goal_registry_check_alignment",
        "description": " READ — Check if an action aligns with the active goal.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"current_action": {"type": "string"}},
            "required": ["current_action"],
        },
    },
    #  Commitment Checker
    {
        "name": "read_commitment_checker_list",
        "description": " READ — List all pending session commitments.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "mutate_commitment_verify",
        "description": " MUTATE — Verify a commitment (marks as fulfilled). Use dry_run=true to preview.",
        "permission": "mutate",
        "annotations": A(True),
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "dry_run": DR()},
            "required": ["id"],
        },
    },
    #  Lifecycle Hooks
    {
        "name": "read_hooks_prefetch",
        "description": " READ — Prefetch session context (memories, decisions, errors).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "project": {"type": "string"},
                "goal": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "max_memories": {"type": "integer", "default": 8},
                "max_decisions": {"type": "integer", "default": 5},
                "max_errors": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "write_hooks_observe",
        "description": " WRITE — Log a session event. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "event_type": {
                    "type": "string",
                    "enum": [
                        "decision",
                        "error",
                        "insight",
                        "preference",
                        "milestone",
                        "handoff",
                    ],
                },
                "description": {"type": "string"},
                "metadata": {"type": "object"},
                "dry_run": DR(),
            },
            "required": ["session_id", "event_type", "description"],
        },
    },
    {
        "name": "read_hooks_session_status",
        "description": " READ — Get current session lifecycle status.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    },
    {
        "name": "write_hooks_session_end",
        "description": " WRITE — End a session and persist observations. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "summary": {"type": "string"},
                "persist_observations": {"type": "boolean", "default": True},
                "dry_run": DR(),
            },
            "required": ["session_id"],
        },
    },
    #  Permission Audit
    {
        "name": "mutate_audit_undo",
        "description": " MUTATE — Undo a previous write/mutate operation via checkpoint ID. Destructive — cannot be reversed.",
        "permission": "mutate",
        "annotations": {
            "destructiveHint": False,
            "readOnlyHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {"checkpoint_id": {"type": "string"}},
            "required": ["checkpoint_id"],
        },
    },
    {
        "name": "read_audit_status",
        "description": " READ — View mutation checkpoint history.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_phase_status",
        "description": "MERGED - Get status for any domain: compact, mutation, audit, consolidation.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "default": "compact",
                    "enum": ["compact", "mutation", "audit", "consolidation"],
                }
            },
            "required": ["domain"],
        },
    },
    #  NE-Memory Search (BM25 + vector + reranker)
    {
        "name": "read_memory_search",
        "description": "MERGED — Search memory. mode=[bm25|vector|hybrid|reranked]. Replaces vector/hybrid/reranked variants.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {
                    "type": "string",
                    "default": "bm25",
                    "enum": ["bm25", "vector", "hybrid", "reranked"],
                },
                "limit": {"type": "integer", "default": 10},
                "fuzzy_threshold": {"type": "number", "default": 0.85},
                "bm25_weight": {"type": "number", "default": 0.5},
                "vector_weight": {"type": "number", "default": 0.5},
                "rrf_k": {"type": "integer", "default": 60},
                "candidates": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_memory_synthesize",
        "description": "Narrative synthesis from search results.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_sources": {"type": "integer", "default": 5},
                "min_confidence": {"type": "number", "default": 0.7},
            },
            "required": ["query"],
        },
    },
    {
        "name": "write_memory_add",
        "description": " WRITE — Store a new memory entry. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "source": {"type": "string", "default": "manual"},
                "metadata": {"type": "object"},
                "dry_run": DR(),
            },
            "required": ["text"],
        },
    },
    {
        "name": "write_memory_consolidate",
        "description": " WRITE — Consolidate memory (dedup, prune, index). Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(True),
        "inputSchema": {
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "default": 0.85},
                "dry_run": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "read_memory_status",
        "description": "Memory engine status — entry count, storage backend, FTS index, vector availability, query cache.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    #  Verifier Middleware
    {
        "name": "read_verifier_status",
        "description": " READ — Get verifier middleware status and drift state.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "write_verifier_renudge",
        "description": " WRITE — Apply a correction renudge to verifier state. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "correction": {"type": "object"},
                "strategy": {
                    "type": "string",
                    "enum": ["incremental", "rollback", "override", "halt"],
                    "default": "incremental",
                },
                "dry_run": DR(),
            },
            "required": ["target", "correction"],
        },
    },
    {
        "name": "write_verifier_clear_renudge",
        "description": " WRITE — Clear a previous renudge. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"target": {"type": "string"}, "dry_run": DR()},
            "required": ["target"],
        },
    },
    #  Art Module
    {
        "name": "read_art_generate_svg",
        "description": " READ — Generate an SVG from a text description.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
            },
            "required": ["description"],
        },
    },
    {
        "name": "read_art_generate_theme",
        "description": " READ — Generate a WCAG color theme from a description.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "default": "dark cyberpunk"}
            },
            "required": ["description"],
        },
    },
    {
        "name": "read_art_extract_palette",
        "description": " READ — Extract a palette from a hex color.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"color": {"type": "string"}},
            "required": ["color"],
        },
    },
    {
        "name": "read_art_design_concept",
        "description": " READ — Generate a design concept from requirements.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"requirements": {"type": "string"}},
            "required": ["requirements"],
        },
    },
    #  Literature Module
    {
        "name": "read_lit_analyze_text",
        "description": " READ — Analyze text for readability and structure.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "read_lit_extract_concepts",
        "description": " READ — Extract key concepts from a text passage.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "read_lit_generate_study_guide",
        "description": " READ — Generate a study guide from content.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
    #  Sensory Module
    {
        "name": "read_sensory_fetch",
        "description": "MERGED — Fetch URL content. Replaces browse + scrape + extract_article. method=[browser|http|article]",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {
                    "type": "string",
                    "default": "browser",
                    "enum": ["browser", "http", "article"],
                },
                "mode": {
                    "type": "string",
                    "default": "text",
                    "enum": [
                        "text",
                        "html",
                        "markdown",
                        "links",
                        "metadata",
                        "tables",
                        "json",
                    ],
                },
                "headers": {"type": "object"},
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_sensory_screenshot",
        "description": " READ — Capture a screenshot of a URL.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "output_path": {"type": "string"},
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "mutate_sensory_interact",
        "description": " MUTATE — Interact with a web page (click, type, press). Use dry_run=true to preview.",
        "permission": "mutate",
        "annotations": A(True),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["click", "type", "press", "wait"],
                            },
                            "selector": {"type": "string"},
                            "value": {"type": "string"},
                        },
                    },
                },
                "dry_run": DR(),
            },
            "required": ["url", "actions"],
        },
    },
    {
        "name": "read_sensory_extract_pdf",
        "description": " READ — Extract text content from a PDF file.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "max_pages": {"type": "integer", "default": 50},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "read_sensory_extract_html",
        "description": " READ — Extract clean text from raw HTML.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "html_content": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["clean", "soup", "tables"],
                    "default": "clean",
                },
            },
            "required": ["html_content"],
        },
    },
    {
        "name": "read_sensory_extract_image",
        "description": " READ — Extract text from an image via OCR.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"file_path": {"type": "string"}},
            "required": ["file_path"],
        },
    },
    {
        "name": "read_sensory_scrape",
        "description": " READ — Scrape a URL for structured data.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["text", "html", "links", "tables", "json"],
                    "default": "text",
                },
                "headers": {"type": "object"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_sensory_extract_article",
        "description": " READ — Extract article content from a URL.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "read_sensory_api_request",
        "description": " READ — Make an HTTP request to any API.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "default": "GET",
                },
                "data": {"type": "object"},
                "headers": {"type": "object"},
                "params": {"type": "object"},
                "timeout": {"type": "integer", "default": 15},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_sensory_fetch_rss",
        "description": " READ — Fetch and parse an RSS/Atom feed.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "feed_url": {"type": "string"},
                "max_items": {"type": "integer", "default": 50},
            },
            "required": ["feed_url"],
        },
    },
    {
        "name": "read_sensory_read_file",
        "description": " READ — Read a local file within allowed roots.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "max_size_kb": {"type": "integer", "default": 500},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "read_sensory_search",
        "description": " READ — Search the web via DuckDuckGo.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_sensory_set_browser_type",
        "description": " READ — Set the Playwright browser engine.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "browser_type": {"type": "string", "enum": ["firefox", "chromium"]}
            },
            "required": ["browser_type"],
        },
    },
    #  Audio Module
    {
        "name": "read_audio_analyze_file",
        "description": " READ — Analyze a WAV file properties and RMS.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"file_path": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "read_audio_waveform",
        "description": " READ — Generate ASCII waveform from a WAV file.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "width": {"type": "integer", "default": 80},
                "height": {"type": "integer", "default": 20},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "read_audio_frequency_analysis",
        "description": " READ — FFT frequency analysis of a WAV file.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "num_bands": {"type": "integer", "default": 10},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "read_audio_music_theory",
        "description": "Foundation for audio suite: chord/scale/mode analysis. Future: EQ, room analysis, convolution.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "notes": {"type": "array", "items": {"type": "string"}},
                "frequencies": {"type": "array", "items": {"type": "number"}},
            },
            "required": [],
        },
    },
    {
        "name": "read_audio_generate_tone",
        "description": "Foundation for audio suite: tone synthesis. Future: sweeps, noise, impulse responses.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "frequency": {"type": "number", "default": 440},
                "duration_seconds": {"type": "number", "default": 1},
            },
            "required": [],
        },
    },
    {
        "name": "read_audio_speech_analysis",
        "description": " READ — Analyze speech metrics from a transcript.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "transcript": {"type": "string"},
                "duration_seconds": {"type": "number"},
            },
            "required": ["transcript", "duration_seconds"],
        },
    },
    {
        "name": "read_audio_convert_guide",
        "description": " READ — Get audio format conversion guidance.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_format": {"type": "string"},
                "target_format": {"type": "string"},
            },
            "required": ["source_format", "target_format"],
        },
    },
    #  Coder Module
    {
        "name": "read_coder_analyze_code",
        "description": " READ — Analyze code for complexity and style issues.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string"}, "language": {"type": "string"}},
            "required": ["code", "language"],
        },
    },
    {
        "name": "read_coder_generate_framework",
        "description": " READ — Generate project scaffold/boilerplate.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_type": {"type": "string"},
                "language": {"type": "string"},
                "features": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["project_type", "language"],
        },
    },
    {
        "name": "read_coder_debug",
        "description": " READ — Debug an error with code context analysis.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "error": {"type": "string"},
                "code_context": {"type": "string", "default": ""},
                "language": {"type": "string"},
            },
            "required": ["error", "language"],
        },
    },
    {
        "name": "read_coder_review",
        "description": " READ — Review code quality and security.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "language": {"type": "string"},
                "focus": {"type": "string", "default": "all"},
            },
            "required": ["code", "language"],
        },
    },
    {
        "name": "read_coder_explain",
        "description": " READ — Explain code at a specified depth.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "language": {"type": "string"},
                "level": {"type": "string", "default": "intermediate"},
            },
            "required": ["code", "language"],
        },
    },
    {
        "name": "read_coder_convert",
        "description": " READ — Convert code between programming languages.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "from": {"type": "string"},
                "to": {"type": "string"},
            },
            "required": ["code", "from", "to"],
        },
    },
    {
        "name": "read_coder_architecture",
        "description": " READ — Generate architecture recommendations.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_type": {"type": "string"},
                "scale": {"type": "string", "default": "medium"},
                "requirements": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["project_type"],
        },
    },
    #  DevOps Module
    {
        "name": "read_devops_container_debug",
        "description": " READ — Debug a failing container from logs.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_log": {"type": "string"},
                "runtime": {"type": "string", "default": "podman"},
            },
            "required": ["error_log"],
        },
    },
    {
        "name": "read_devops_permissions_analyze",
        "description": " READ — Analyze container permission issues.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mount_path": {"type": "string"},
                "container_user": {"type": "string"},
                "host_user": {"type": "string"},
                "error_symptom": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "read_devops_compose_generator",
        "description": " READ — Generate a docker-compose file.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "services": {"type": "array"},
                "networks": {"type": "array"},
                "runtime": {"type": "string", "default": "docker"},
            },
            "required": ["services"],
        },
    },
    {
        "name": "read_devops_mergerfs_setup",
        "description": " READ — Generate mergerfs pool configuration.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_paths": {"type": "array"},
                "mount_point": {"type": "string"},
                "policy": {"type": "string", "default": "epmfs"},
            },
            "required": ["source_paths", "mount_point"],
        },
    },
    {
        "name": "read_devops_dockerfile_analyze",
        "description": " READ — Analyze a Dockerfile for best practices.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"dockerfile": {"type": "string"}},
            "required": ["dockerfile"],
        },
    },
    {
        "name": "read_devops_network_troubleshoot",
        "description": " READ — Troubleshoot container network issues.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"symptom": {"type": "string"}},
            "required": ["symptom"],
        },
    },
    #  Game Dev Module
    {
        "name": "read_gamedev_design_analyze",
        "description": " READ — Analyze a game concept for feasibility.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"concept": {"type": "string"}, "genre": {"type": "string"}},
            "required": ["concept", "genre"],
        },
    },
    {
        "name": "read_gamedev_scaffold_project",
        "description": " READ — Scaffold a game project directory.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "engine": {"type": "string"},
                "genre": {"type": "string"},
                "name": {"type": "string", "default": "MyGame"},
            },
            "required": ["engine", "genre"],
        },
    },
    {
        "name": "read_gamedev_mechanics_guide",
        "description": " READ — Generate game mechanics implementation guide.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"genre": {"type": "string"}},
            "required": ["genre"],
        },
    },
    {
        "name": "read_gamedev_optimization",
        "description": " READ — Suggest game performance optimizations.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"engine": {"type": "string"}, "issue": {"type": "string"}},
            "required": ["engine", "issue"],
        },
    },
    {
        "name": "read_gamedev_compare_engines",
        "description": " READ — Compare game engines for a project.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_type": {"type": "string"},
                "team_size": {"type": "string", "default": "solo"},
                "budget": {"type": "string", "default": "indie"},
            },
            "required": ["project_type"],
        },
    },
    {
        "name": "read_gamedev_level_design",
        "description": " READ — Generate level design principles.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "genre": {"type": "string"},
                "level_type": {"type": "string"},
            },
            "required": ["genre", "level_type"],
        },
    },
    #  Mutation Phase (Algorithmic Mutation Engine)
    {
        "name": "read_mutate_scope",
        "description": "Parse execution triggers → define functional boundaries and target metrics.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "trigger": {
                    "type": "string",
                    "description": "Task description, error log, or command to analyze",
                }
            },
            "required": ["trigger"],
        },
    },
    {
        "name": "read_mutate_audit",
        "description": "Scan tool inventories + DAGs for redundancy and overlapping execution flows.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope_id": {"type": "string"},
                "domains": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
    },
    {
        "name": "mutate_execute",
        "description": " MUTATE — Execute algorithmic mutation cycle (audit → refactor plan → persist). Use dry_run=true to preview.",
        "permission": "mutate",
        "annotations": A(True),
        "inputSchema": {
            "type": "object",
            "properties": {"scope_id": {"type": "string"}, "dry_run": DR()},
            "required": [],
        },
    },
    #  Compact Phase (Context Compaction Engine)
    {
        "name": "read_compact_token_velocity",
        "description": "Check current token velocity and compaction recommendation.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_compact_synthesize",
        "description": "Condense verbose content into a high-density summary (preserves code/math blocks).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "max_chars": {"type": "integer", "default": 2000},
            },
            "required": ["content"],
        },
    },
    {
        "name": "write_compact_execute",
        "description": " WRITE — Execute context compaction cycle. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Content to compact (leave empty to status-only)",
                },
                "dry_run": DR(),
            },
            "required": [],
        },
    },
    {
        "name": "read_compact_record_tick",
        "description": "Record a manual token velocity tick.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"context": {"type": "string", "default": "manual"}},
            "required": [],
        },
    },
    #  Plumber Module (Execution Pipelines)
    {
        "name": "read_plumber_inspect_socket",
        "description": "Check socket latency and structural integrity (TCP or Unix).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "default": "localhost"},
                "port": {"type": "integer"},
                "socket_path": {
                    "type": "string",
                    "description": "Unix socket path (alternative to TCP)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "read_plumber_trace_handoff",
        "description": "Trace data handoff between components. Filter by source/target/protocol.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "target": {"type": "string"},
                "protocol_filter": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "write_plumber_checkpoint",
        "description": " WRITE — Create runtime checkpoint before destructive ops. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_type": {"type": "string", "default": "session"},
                "file_paths": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": "object"},
                "dry_run": DR(),
            },
            "required": [],
        },
    },
    {
        "name": "read_plumber_checkpoints",
        "description": "List recent checkpoints from history.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 5}},
            "required": [],
        },
    },
    #  CAD Module (3D modeling / OpenSCAD)
    {
        "name": "read_cad_validate_scad",
        "description": "Validate OpenSCAD file syntax and structure.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"filepath": {"type": "string"}},
            "required": ["filepath"],
        },
    },
    {
        "name": "read_cad_beam_stress",
        "description": "Rectangular beam stress analysis for 3D printed parts.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "force_N": {"type": "number"},
                "length_mm": {"type": "number"},
                "width_mm": {"type": "number"},
                "height_mm": {"type": "number"},
                "yield_MPa": {"type": "number", "default": 40},
            },
            "required": ["force_N", "length_mm", "width_mm", "height_mm"],
        },
    },
    #  Electrical Module (Circuit Design)
    {
        "name": "read_electrical_design_circuit",
        "description": "Design a circuit schematic with components and connections.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                        },
                    },
                },
                "connections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["components", "connections"],
        },
    },
    {
        "name": "read_electrical_analyze_circuit",
        "description": "Analyze a circuit for connectivity and validation.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"circuit_json": {"type": "string"}},
            "required": ["circuit_json"],
        },
    },
    #  Focus Module (Scope & Session Management)
    {
        "name": "read_focus_scope_check",
        "description": "Check user input for scope creep, topic switching, feature bloat.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_text": {"type": "string"},
                "current_project": {"type": "string", "default": "CortexStratum"},
            },
            "required": ["input_text"],
        },
    },
    {
        "name": "read_focus_nudge",
        "description": "Generate context-aware nudge message based on scope analysis.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope_result": {"type": "object"},
                "user_input": {"type": "string"},
            },
            "required": ["scope_result", "user_input"],
        },
    },
    {
        "name": "write_focus_store_global",
        "description": " WRITE — Store out-of-scope task in Global Projects Memory. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "task": {"type": "string"},
                "context": {"type": "string"},
                "source_session": {"type": "string"},
                "dry_run": DR(),
            },
            "required": ["project", "task"],
        },
    },
    {
        "name": "read_focus_global",
        "description": "Retrieve global projects memory. Filter by project.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "read_focus_pipeline_status",
        "description": "Show current session pipeline phase and stats.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "write_focus_pipeline_advance",
        "description": " WRITE — Advance session pipeline phase. Phases: help→context→executing→wrapping→learning→end.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "next_phase": {
                    "type": "string",
                    "enum": [
                        "help",
                        "context",
                        "executing",
                        "wrapping",
                        "learning",
                        "end",
                    ],
                },
                "summary": {"type": "string"},
                "dry_run": DR(),
            },
            "required": ["next_phase"],
        },
    },
    {
        "name": "read_focus_decompose",
        "description": "Decompose complex prompt into atomic tasks grouped by category.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"prompt_text": {"type": "string"}},
            "required": ["prompt_text"],
        },
    },
    {
        "name": "read_focus_prioritize",
        "description": "Score and sequence tasks from decomposer into execution plan.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"tasks": {"type": "array", "items": {"type": "object"}}},
            "required": ["tasks"],
        },
    },
    {
        "name": "mutate_focus_learn",
        "description": " MUTATE — Post-session learning analysis. Use dry_run=true to preview.",
        "permission": "mutate",
        "annotations": A(True),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "events": {"type": "array", "items": {"type": "object"}},
                "dry_run": DR(),
            },
            "required": ["session_id"],
        },
    },
    #  Pedagogy Engine (Cognitive Architecture)
    {
        "name": "read_pedagogy_assess",
        "description": "Assess user understanding level from queries/topic. Returns depth recommendation.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "queries": {"type": "array", "items": {"type": "string"}},
                "topic": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "read_pedagogy_adapt",
        "description": "Generate explanation prompt at appropriate depth for a topic.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "complexity": {
                    "type": "integer",
                    "description": "1-5 (intuitive to expert)",
                },
                "format": {"type": "string", "default": "text"},
            },
            "required": [],
        },
    },
    {
        "name": "write_pedagogy_profile",
        "description": " WRITE — Store user comprehension profile. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "depth": {"type": "integer", "description": "1-5"},
                "topic": {"type": "string"},
                "feedback_score": {"type": "number"},
                "dry_run": DR(),
            },
            "required": [],
        },
    },
    #  Consolidation Daemon (Offline Cross-Pollination)
    {
        "name": "mutate_consolidation_run",
        "description": " MUTATE — Execute cross-pollination cycle (TF-IDF similarity linking). Use dry_run=true to preview.",
        "permission": "mutate",
        "annotations": A(True),
        "inputSchema": {
            "type": "object",
            "properties": {"dry_run": DR()},
            "required": [],
        },
    },
    {
        "name": "read_consolidation_links",
        "description": "Show discovered cross-pollination links between memory entries.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "min_similarity": {"type": "number", "default": 0},
            },
            "required": [],
        },
    },
    #  Utility Module (Database, Conversion, Regex)
    {
        "name": "read_db_query",
        "description": "Execute a SQL SELECT/PRAGMA query on a SQLite database.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"db_path": {"type": "string"}, "sql": {"type": "string"}},
            "required": ["db_path", "sql"],
        },
    },
    {
        "name": "read_db_schema",
        "description": "List tables and columns in a SQLite database.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"db_path": {"type": "string"}},
            "required": ["db_path"],
        },
    },
    {
        "name": "write_db_execute",
        "description": " WRITE — Execute INSERT/UPDATE/DELETE on a SQLite database. Use dry_run=true to preview.",
        "permission": "write",
        "annotations": A(True),
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string"},
                "sql": {"type": "string"},
                "dry_run": DR(),
            },
            "required": ["db_path", "sql"],
        },
    },
    {
        "name": "read_convert_csv_to_json",
        "description": "Convert CSV text to JSON.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "csv_text": {"type": "string"},
                "dialect": {"type": "string", "default": "excel"},
                "has_header": {"type": "boolean", "default": True},
            },
            "required": ["csv_text"],
        },
    },
    {
        "name": "read_convert_json_to_csv",
        "description": "Convert JSON array to CSV text.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"json_text": {"type": "string"}},
            "required": ["json_text"],
        },
    },
    {
        "name": "read_convert_json_to_xml",
        "description": "Convert JSON to XML string.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "json_text": {"type": "string"},
                "root_name": {"type": "string", "default": "root"},
                "item_name": {"type": "string", "default": "item"},
            },
            "required": ["json_text"],
        },
    },
    {
        "name": "read_convert_xml_to_json",
        "description": "Convert XML string to JSON.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"xml_text": {"type": "string"}},
            "required": ["xml_text"],
        },
    },
    {
        "name": "read_convert_json_to_yaml",
        "description": "Convert JSON to YAML (requires PyYAML).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"json_text": {"type": "string"}},
            "required": ["json_text"],
        },
    },
    {
        "name": "read_convert_yaml_to_json",
        "description": "Convert YAML to JSON (requires PyYAML).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"yaml_text": {"type": "string"}},
            "required": ["yaml_text"],
        },
    },
    {
        "name": "read_regex_test",
        "description": "Test a regex pattern against text and return matches.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "text": {"type": "string"},
                "flags": {"type": "string", "default": ""},
            },
            "required": ["pattern", "text"],
        },
    },
    {
        "name": "read_regex_explain",
        "description": "Explain what a regex pattern does in plain language.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "mutate_verify_run",
        "description": " MUTATE — Run the full verification gate (ruff lint, syntax check, MCP test, skill pipeline, verifier, tool count). Use dry_run=true to preview.",
        "permission": "mutate",
        "annotations": A(True),
        "inputSchema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "ruff",
                            "syntax",
                            "mcp_test",
                            "skill_pipeline",
                            "verifier",
                            "tool_count",
                        ],
                    },
                    "description": "Optional subset of steps to run (default: all)",
                },
                "dry_run": DR(),
            },
            "required": [],
        },
    },
    #  CFD Simulation Engine
    {
        "name": "read_sim_cfd_pipe",
        "description": " READ — Pipe flow pressure drop via Darcy-Weisbach. Returns ΔP, Re, friction factor, regime.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "rho": {"type": "number"},
                "mu": {"type": "number"},
                "v": {"type": "number"},
                "D": {"type": "number"},
                "L": {"type": "number"},
                "roughness": {"type": "number"},
            },
            "required": ["rho", "mu", "v", "D", "L"],
        },
    },
    {
        "name": "read_sim_cfd_boundary",
        "description": " READ — Boundary layer thickness on flat plate (laminar/turbulent).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "v": {"type": "number"},
                "x": {"type": "number"},
                "rho": {"type": "number"},
                "mu": {"type": "number"},
            },
            "required": ["v", "x", "rho", "mu"],
        },
    },
    {
        "name": "read_sim_cfd_drag",
        "description": " READ — Drag force on immersed body: F_d = 0.5·ρ·v²·Cd·A.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "rho": {"type": "number"},
                "v": {"type": "number"},
                "Cd": {"type": "number"},
                "A": {"type": "number"},
            },
            "required": ["rho", "v", "Cd", "A"],
        },
    },
    {
        "name": "read_sim_cfd_bernoulli",
        "description": " READ — Bernoulli's equation solver. Supply 5 of 6 variables, leave 1 as None.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "P1": {"type": "number"},
                "v1": {"type": "number"},
                "h1": {"type": "number"},
                "P2": {"type": "number"},
                "v2": {"type": "number"},
                "h2": {"type": "number"},
                "rho": {"type": "number", "default": 1000},
                "g": {"type": "number", "default": 9.81},
            },
            "required": [],
        },
    },
    {
        "name": "read_sim_cfd_pump",
        "description": " READ — Pump sizing: flow rate from power, efficiency, head.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "power_W": {"type": "number"},
                "eta": {"type": "number", "default": 0.7},
                "rho": {"type": "number", "default": 1000},
                "g": {"type": "number", "default": 9.81},
                "H": {"type": "number"},
            },
            "required": ["power_W", "H"],
        },
    },
    #  FEA Simulation Engine
    {
        "name": "read_sim_fea_beam",
        "description": " READ — 1D Euler-Bernoulli beam element stiffness matrix (4x4).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "E": {"type": "number"},
                "I": {"type": "number"},
                "L": {"type": "number"},
            },
            "required": ["E", "I", "L"],
        },
    },
    {
        "name": "read_sim_fea_truss",
        "description": " READ — Truss element axial stiffness k = EA/L with optional stress.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "E": {"type": "number"},
                "A": {"type": "number"},
                "L": {"type": "number"},
                "F": {"type": "number"},
            },
            "required": ["E", "A", "L"],
        },
    },
    {
        "name": "read_sim_fea_modal",
        "description": " READ — First natural frequency of cantilever beam.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "E": {"type": "number"},
                "I": {"type": "number"},
                "rho": {"type": "number"},
                "A": {"type": "number"},
                "L": {"type": "number"},
            },
            "required": ["E", "I", "rho", "A", "L"],
        },
    },
    {
        "name": "read_sim_fea_heat",
        "description": " READ — 1D steady-state heat conduction via Fourier's law.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "k": {"type": "number"},
                "A": {"type": "number"},
                "T1": {"type": "number"},
                "T2": {"type": "number"},
                "L": {"type": "number"},
            },
            "required": ["k", "A", "T1", "T2", "L"],
        },
    },
    {
        "name": "read_sim_fea_stress_recovery",
        "description": " READ — Stress recovery from strain: σ = E·ε.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"E": {"type": "number"}, "strain": {"type": "number"}},
            "required": ["E", "strain"],
        },
    },
    #  Mechanics Simulation Engine
    {
        "name": "read_sim_mech_stress",
        "description": " READ — Beam bending stress: σ = M·y / I.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "moment": {"type": "number"},
                "distance_neutral": {"type": "number"},
                "I": {"type": "number"},
            },
            "required": ["moment", "distance_neutral", "I"],
        },
    },
    {
        "name": "read_sim_mech_shear",
        "description": " READ — Beam shear stress: τ = V·Q / (I·b).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "shear_force": {"type": "number"},
                "Q": {"type": "number"},
                "I": {"type": "number"},
                "width": {"type": "number"},
            },
            "required": ["shear_force", "Q", "I", "width"],
        },
    },
    {
        "name": "read_sim_mech_deflection",
        "description": " READ — Beam deflection (center or off-center point load).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "load": {"type": "number"},
                "length": {"type": "number"},
                "E": {"type": "number"},
                "I": {"type": "number"},
                "position": {"type": "object"},
            },
            "required": ["load", "length", "E", "I"],
        },
    },
    {
        "name": "read_sim_mech_moi",
        "description": " READ — Moment of inertia for rectangular or circular sections.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "shape": {"type": "string", "enum": ["rect", "circle"]},
                "width": {"type": "number"},
                "height": {"type": "number"},
                "diameter": {"type": "number"},
            },
            "required": ["shape"],
        },
    },
    {
        "name": "read_sim_mech_buckle",
        "description": " READ — Column buckling (Euler or Johnson, auto-selected).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "E": {"type": "number"},
                "I": {"type": "number"},
                "K": {"type": "number", "default": 1.0},
                "L": {"type": "number"},
                "sigma_y": {"type": "number"},
                "A": {"type": "number"},
                "r": {"type": "number"},
            },
            "required": ["E", "L"],
        },
    },
    {
        "name": "read_sim_mech_fatigue",
        "description": " READ — Fatigue analysis (S-N curve, Goodman correction, Miner's rule).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "Sf_prime": {"type": "number"},
                "b": {"type": "number", "default": -0.1},
                "N": {"type": "number", "default": 1000},
                "stress_amplitude": {"type": "number"},
                "solve_for": {"type": "string", "enum": ["stress", "cycles"]},
            },
            "required": ["Sf_prime"],
        },
    },
    {
        "name": "read_sim_mech_fastener",
        "description": " READ — Fastener shear stress and bolt torque-preload.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {"type": "number"},
                "area": {"type": "number"},
                "num_fasteners": {"type": "integer", "default": 1},
                "K": {"type": "number"},
                "D": {"type": "number"},
                "F": {"type": "number"},
                "solve_for": {"type": "string", "enum": ["shear", "torque"]},
            },
            "required": ["solve_for"],
        },
    },
    #  Math Engine
    {
        "name": "read_sim_math_matrix_solve",
        "description": " READ — Solve Ax = b with LaTeX derivation.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"A": {"type": "array"}, "b": {"type": "array"}},
            "required": ["A", "b"],
        },
    },
    {
        "name": "read_sim_math_determinant",
        "description": " READ — Matrix determinant via LU decomposition.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"A": {"type": "array"}},
            "required": ["A"],
        },
    },
    {
        "name": "read_sim_math_inverse",
        "description": " READ — Matrix inverse via Gaussian elimination.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"A": {"type": "array"}},
            "required": ["A"],
        },
    },
    {
        "name": "read_sim_math_eigenvalue",
        "description": " READ — Dominant eigenvalue via power iteration.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "A": {"type": "array"},
                "iterations": {"type": "integer", "default": 100},
            },
            "required": ["A"],
        },
    },
    {
        "name": "read_sim_math_derivative",
        "description": " READ — Numerical derivative (central difference).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"expr": {"type": "string"}, "x": {"type": "number"}},
            "required": ["expr", "x"],
        },
    },
    {
        "name": "read_sim_math_integrate",
        "description": " READ — Numerical integration (Simpson/trapezoidal).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "expr": {"type": "string"},
                "a": {"type": "number"},
                "b": {"type": "number"},
                "n": {"type": "integer", "default": 100},
                "method": {
                    "type": "string",
                    "enum": ["simpson", "trapezoidal"],
                    "default": "simpson",
                },
            },
            "required": ["expr", "a", "b"],
        },
    },
    {
        "name": "read_sim_math_taylor",
        "description": " READ — Taylor series expansion (numerical derivatives).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "expr": {"type": "string"},
                "x0": {"type": "number", "default": 0},
                "order": {"type": "integer", "default": 4},
                "at_x": {"type": "number", "default": 0},
            },
            "required": ["expr"],
        },
    },
    {
        "name": "read_sim_math_root",
        "description": " READ — Root finding (Newton/bisection/secant).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "expr": {"type": "string"},
                "method": {
                    "type": "string",
                    "enum": ["newton", "bisection", "secant"],
                    "default": "newton",
                },
                "guess": {"type": "number", "default": 0},
                "a": {"type": "number", "default": 0},
                "b": {"type": "number", "default": 1},
            },
            "required": ["expr"],
        },
    },
    {
        "name": "read_sim_math_stats",
        "description": " READ — Descriptive statistics (mean, median, std, variance).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"data": {"type": "array"}},
            "required": ["data"],
        },
    },
    {
        "name": "read_sim_math_regression",
        "description": " READ — Linear regression: y = mx + b with R².",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"x_data": {"type": "array"}, "y_data": {"type": "array"}},
            "required": ["x_data", "y_data"],
        },
    },
    {
        "name": "read_sim_math_fft",
        "description": " READ — Radix-2 Cooley-Tukey FFT (pads to power of 2).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"samples": {"type": "array"}},
            "required": ["samples"],
        },
    },
    {
        "name": "read_sim_math_complex",
        "description": " READ — Complex number arithmetic (add/sub/mul/div/pow).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "z1_real": {"type": "number"},
                "z1_imag": {"type": "number"},
                "z2_real": {"type": "number"},
                "z2_imag": {"type": "number"},
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide", "power"],
                    "default": "add",
                },
            },
            "required": ["z1_real", "z1_imag"],
        },
    },
    {
        "name": "read_sim_math_factor",
        "description": " READ — Prime factorization of an integer.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    },
    {
        "name": "read_sim_math_gcdiv",
        "description": " READ — GCD and LCM of two integers.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "read_sim_math_polynomial",
        "description": " READ — Evaluate polynomial via Horner's method.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"coeffs": {"type": "array"}, "x": {"type": "number"}},
            "required": ["coeffs", "x"],
        },
    },
    {
        "name": "read_sim_math_convert",
        "description": " READ — Unit conversion (SI/imperial, temperature, pressure).",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "from": {"type": "string"},
                "to": {"type": "string"},
            },
            "required": ["value", "from", "to"],
        },
    },
    {
        "name": "read_sim_math_ode",
        "description": " READ — ODE solver (RK4/Euler) with LaTeX output.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "derivatives": {"type": "array"},
                "y0": {"type": "array"},
                "t_start": {"type": "number", "default": 0},
                "t_end": {"type": "number", "default": 10},
                "steps": {"type": "integer", "default": 100},
                "method": {
                    "type": "string",
                    "enum": ["rk4", "euler"],
                    "default": "rk4",
                },
            },
            "required": ["derivatives", "y0"],
        },
    },
    {
        "name": "read_sim_math_latex",
        "description": " READ — Generate LaTeX from a mathematical expression.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
                "notation": {
                    "type": "string",
                    "enum": ["aligned", "derivation"],
                    "default": "aligned",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "name": "read_sim_math_plot",
        "description": " READ — ASCII line plot from x/y data arrays.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "x_data": {"type": "array"},
                "y_data": {"type": "array"},
                "width": {"type": "integer", "default": 50},
                "height": {"type": "integer", "default": 15},
                "title": {"type": "string", "default": ""},
            },
            "required": ["x_data", "y_data"],
        },
    },
    #  DAG Orchestration
    {
        "name": "read_dag_status",
        "description": "List available DAG definitions or show info for a specific DAG.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dag_path": {
                    "type": "string",
                    "description": "Optional path to a specific DAG file for detailed info",
                }
            },
            "required": [],
        },
    },
    {
        "name": "write_dag_execute",
        "description": " WRITE — Execute a DAG pipeline. Use dry_run=true to preview the execution plan.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dag_path": {
                    "type": "string",
                    "description": "Path to DAG definition JSON (under data/dag-definitions/)",
                },
                "task_input": {
                    "type": "string",
                    "description": "Optional JSON string of root task input",
                },
                "dry_run": DR(),
            },
            "required": ["dag_path"],
        },
    },
    {
        "name": "write_dag_resume",
        "description": " WRITE — Resume a previously failed DAG pipeline, skipping completed nodes.",
        "permission": "write",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dag_path": {
                    "type": "string",
                    "description": "Path to DAG definition JSON",
                },
                "task_input": {
                    "type": "string",
                    "description": "Optional JSON string of root task input",
                },
                "dry_run": DR(),
            },
            "required": ["dag_path"],
        },
    },
    #  Workstream Management
    {
        "name": "read_workstream_list",
        "description": "List all resumable workstreams from previous sessions.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_workstream_status",
        "description": "Show details for a specific workstream.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {
            "type": "object",
            "properties": {"workstream_id": {"type": "string"}},
            "required": ["workstream_id"],
        },
    },
    #  Skills & Agent Introspection
    {
        "name": "read_skill_list",
        "description": "List all active skills from the skills directory.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_agent_list",
        "description": "List all available agent personas from .opencode/agents.md.",
        "permission": "read",
        "annotations": A(False),
        "inputSchema": {"type": "object", "properties": {}},
    },
]

#
# HANDLE TOOL CALL
#


def handle_tool_call(name, args):
    _log("DEBUG", f"handle_tool_call: {name}")
    # Permission check
    allowed, reason = can_call_tool(
        name, {"mode": "interactive" if not PERMISSIVE_MODE else "permissive"}
    )
    if not allowed:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"error": "permission_denied", "tool": name, "reason": reason}
                    ),
                }
            ]
        }
    verifier = _get_verifier()
    pre = verifier.pre_verify(name, args)
    if not pre["passed"]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"error": "verifier_rejected", "violations": pre["violations"]}
                    ),
                }
            ]
        }

    # Dry-run intercept
    if args.get("dry_run") and _is_permission(
        name, (PERMISSION_WRITE, PERMISSION_MUTATE)
    ):
        audit = _get_audit()
        sim = audit.simulate(name, args)
        sim["undo_token"] = None
        sim["note"] = "Dry run only. Execute without dry_run=true to commit."
        return {"content": [{"type": "text", "text": json.dumps(sim, indent=2)}]}

    # Checkpoint before memory mutations
    if name in ("write_memory_add", "write_memory_consolidate") and not args.get(
        "dry_run"
    ):
        _get_audit().checkpoint(name, args)
    else:
        pass

    # Memory tools
    if name in (
        "read_memory_search",
        "read_memory_synthesize",
        "read_memory_vector_search",
        "read_memory_hybrid_search",
        "read_memory_reranked_search",
        "write_memory_add",
        "write_memory_consolidate",
        "read_memory_status",
    ):
        mem = _get_memory_search()
        if name == "read_memory_search":
            mode = args.get("mode", "bm25")
            if mode == "vector":
                r = mem.vector_search(args.get("query", ""), args.get("limit", 10))
            elif mode == "hybrid":
                r = mem.hybrid_search(
                    args.get("query", ""),
                    args.get("limit", 10),
                    args.get("bm25_weight", 0.5),
                    args.get("vector_weight", 0.5),
                    args.get("rrf_k", 60),
                )
            elif mode == "reranked":
                r = mem.reranked_search(
                    args.get("query", ""),
                    args.get("limit", 5),
                    args.get("candidates", 20),
                )
            else:
                r = mem.search(
                    args.get("query", ""),
                    args.get("limit", 10),
                    args.get("fuzzy_threshold", 0.85),
                )
        elif name == "read_memory_synthesize":
            r = mem.synthesize(
                args.get("query", ""),
                args.get("max_sources", 5),
                args.get("min_confidence", 0.7),
            )
        elif name == "read_memory_vector_search":  # deprecated
            r = mem.vector_search(args.get("query", ""), args.get("limit", 10))
        elif name == "read_memory_hybrid_search":  # deprecated
            r = mem.hybrid_search(
                args.get("query", ""),
                args.get("limit", 10),
                args.get("bm25_weight", 0.5),
                args.get("vector_weight", 0.5),
                args.get("rrf_k", 60),
            )
        elif name == "read_memory_reranked_search":  # deprecated
            r = mem.reranked_search(
                args.get("query", ""), args.get("limit", 5), args.get("candidates", 20)
            )
        elif name == "write_memory_add":
            r = {
                "memory_id": mem.add_memory(
                    args.get("text", ""),
                    args.get("source", "manual"),
                    args.get("metadata", {}),
                ),
                "status": "stored",
            }
        elif name == "write_memory_consolidate":
            r = mem.consolidate(
                threshold=args.get("threshold", 0.85),
                dry_run=args.get("dry_run", False),
            )
        else:
            r = mem.status()
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    # Verifier
    if name in (
        "read_verifier_status",
        "write_verifier_renudge",
        "write_verifier_clear_renudge",
    ):
        if name == "read_verifier_status":
            r = verifier.get_status()
        elif name == "write_verifier_renudge":
            r = verifier.renudge(
                args.get("target", ""),
                args.get("correction", {}),
                args.get("strategy", "incremental"),
            )
        else:
            r = verifier.clear_renudge(args.get("target", ""))
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    # Permission Audit
    if name == "read_audit_status":
        return {
            "content": [
                {"type": "text", "text": json.dumps(_get_audit().status(), indent=2)}
            ]
        }
    if name == "mutate_audit_undo":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_audit().undo(args.get("checkpoint_id", "")), indent=2
                    ),
                }
            ]
        }

    # Skill router
    if name == "read_skill_router_match":
        router = SKILLS_DIR / "skill-router.json"
        if router.exists():
            config = json.loads(router.read_text(encoding="utf-8"))
            task_lower = args.get("task", "").lower()
            matched = []
            for rule in config.get("rules", []):
                for t in rule.get("triggers", []):
                    if t.lower() in task_lower:
                        for s in rule.get("skills", []):
                            if s not in matched:
                                matched.append(s)
                        break
            if not matched:
                matched = config.get("default_skills", [])
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"matched_skills": matched, "count": len(matched)}
                        ),
                    }
                ]
            }
        return {"content": [{"type": "text", "text": "Router not found"}]}

    # Tool suggest
    if name == "read_tools_suggest":
        try:
            from tool_router import suggest

            s = suggest(args.get("task", ""), TOOLS, args.get("top_k", 3))
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "task": args.get("task", ""),
                                "suggestions": s,
                                "total_tools": len(TOOLS),
                            }
                        ),
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": f"Tool suggest failed: {e}"}),
                    }
                ]
            }

    # Trace system
    if name in (
        "write_xtrace_log_error",
        "read_xtrace_search",
        "read_xtrace_status",
        "write_dtrace_add",
        "read_dtrace_search",
        "write_goal_registry_init",
        "write_goal_registry_add_subgoal",
        "read_goal_registry_status",
        "read_goal_registry_check_alignment",
        "read_commitment_checker_list",
        "mutate_commitment_verify",
    ):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_trace().handle_tool_call(name, args), indent=2
                    ),
                }
            ]
        }

    # Art
    if name.startswith("read_art_"):
        art = _get_module("art_module", "../engine/art-module.py")
        if "svg" in name:
            r = art.generate_svg(
                args.get("description", ""),
                width=args.get("width", 400),
                height=args.get("height", 300),
            )
        elif "theme" in name:
            r = art.generate_theme(args.get("description", "dark cyberpunk"))
        elif "palette" in name:
            r = art.extract_palette(args.get("color", "#3b82f6"))
        else:
            r = art.design_concept(args.get("requirements", "A modern dashboard"))
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(r, indent=2) if isinstance(r, dict) else r,
                }
            ]
        }

    # Literature
    if name.startswith("read_lit_"):
        lit = _get_module("lit_module", "../engine/literature-module.py")
        if "analyze_text" in name:
            r = lit.analyze_text(args.get("text", ""))
        elif "concepts" in name:
            r = lit.extract_concepts(args.get("text", ""))
        elif "study" in name:
            r = lit.generate_study_guide(args.get("content", ""))
        else:
            r = {"error": "Unknown literature tool"}
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    # Sensory
    if name.startswith("read_sensory_") or name.startswith("write_sensory_"):
        stripped = name.split("_", 1)[1]  # remove "read_" or "write_" prefix
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "sensory_module", "../engine/sensory-module.py"
                        ).handle_tool_call(stripped, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Audio
    if name.startswith("read_audio_"):
        stripped = name.split("_", 1)[1]  # remove "read_" prefix
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "audio_module", "../engine/audio-module.py"
                        ).handle_tool_call(stripped, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Coder
    if name.startswith("read_coder_"):
        stripped = name.split("_", 1)[1]  # remove "read_" prefix
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "coder_module", "../engine/coder-module.py"
                        ).coder_handle_tool_call(stripped, args),
                        indent=2,
                    ),
                }
            ]
        }

    # DevOps
    if name.startswith("read_devops_"):
        stripped = name.split("_", 1)[1]  # remove "read_" prefix
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "devops_module", "../engine/devops-module.py"
                        ).devops_handle_tool_call(stripped, args),
                        indent=2,
                    ),
                }
            ]
        }

    # GameDev
    if name.startswith("read_gamedev_"):
        stripped = name.split("_", 1)[1]  # remove "read_" prefix
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "gamedev_module", "../engine/game-dev-module.py"
                        ).gamedev_handle_tool_call(stripped, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Plumber Module
    if name.startswith("read_plumber_") or name.startswith("write_plumber_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "plumber_module", "../engine/plumber-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Mutation Phase
    if name.startswith("read_mutate_") or name == "mutate_execute":
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "mutation_module", "../engine/mutation-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Compact Phase
    if name.startswith("read_compact_") or name.startswith("write_compact_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "compact_module", "../engine/compact-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # CAD Module
    if name.startswith("read_cad_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "cad_wrapper", "../engine/cad-module/cad_wrapper.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Electrical Module
    if name.startswith("read_electrical_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "electrical_wrapper",
                            "../engine/electrical-module/electrical_wrapper.py",
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Focus Module (Scope & Session Management)
    if name.startswith("read_focus_") or name.startswith("write_focus_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "focus_module", "pipeline/focus-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Pedagogy Engine
    if name.startswith("read_pedagogy_") or name.startswith("write_pedagogy_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "pedagogy_module", "../engine/pedagogy-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Consolidation Daemon
    if name.startswith("read_consolidation_") or name.startswith(
        "write_consolidation_"
    ):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "consolidation_module", "pipeline/consolidation-daemon.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Hooks
    if name.startswith("read_hooks_") or name.startswith("write_hooks_"):
        hooks = _get_module("hooks_module", "hooks.py")
        if not hasattr(hooks, "_wired"):
            hm = hooks._get_hooks()
            hm._memory_search = _get_memory_search().search
            hm._trace_handle = _get_trace().handle_tool_call
            hooks._wired = True
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        hooks.hooks_handle_tool_call(name, args), indent=2
                    ),
                }
            ]
        }

    # Utility Module (Database, Conversion, Regex, Verification Gate)
    if (
        name.startswith("read_db_")
        or name.startswith("write_db_")
        or name.startswith("read_convert_")
        or name.startswith("read_regex_")
        or name == "mutate_verify_run"
    ):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "utility_module", "../engine/utility-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # Merged: read_phase_status dispatch
    if name == "read_phase_status":
        domain = args.get("domain", "compact")
        if domain == "compact":
            mod = _get_module("compact_module", "../engine/compact-module.py")
            r = mod.session_status()
        elif domain == "mutation":
            mod = _get_module("mutation_module", "../engine/mutation-module.py")
            r = mod.get_status()
        elif domain == "audit":
            r = _get_audit().status()
        elif domain == "consolidation":
            mod = _get_module(
                "consolidation_module", "pipeline/consolidation-daemon.py"
            )
            r = mod.get_status()
        else:
            r = {"error": f"Unknown domain: {domain}"}
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    #  CFD Simulation Engine
    if name.startswith("read_sim_cfd_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "sim_cfd_module", "../engine/sim-cfd-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    #  FEA Simulation Engine
    if name.startswith("read_sim_fea_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "sim_fea_module", "../engine/sim-fea-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    #  Mechanics Simulation Engine
    if name.startswith("read_sim_mech_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "sim_mechanics_module", "../engine/sim-mechanics-module.py"
                        ).handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    #  Math Simulation Engine
    if name.startswith("read_sim_math_"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        _get_module(
                            "sim_math_module", "../engine/sim-math-module.py"
                        ).math_handle_tool_call(name, args),
                        indent=2,
                    ),
                }
            ]
        }

    # DAG Orchestration (uses server DATA_DIR for correct path resolution)
    if name.startswith("read_dag_") or name.startswith("write_dag_"):
        dag_mod = _get_module("dag_coordinator", "pipeline/dag-coordinator.py")
        dag_def_dir = str(DATA_DIR / "dag-definitions")
        if not os.path.isdir(dag_def_dir):
            os.makedirs(dag_def_dir, exist_ok=True)
        if name == "read_dag_status":
            dag_path = args.get("dag_path")
            if dag_path:
                if not os.path.isabs(dag_path):
                    dag_path = os.path.join(dag_def_dir, dag_path)
                dag = dag_mod.load_dag_definition(dag_path)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "dag_id": dag["dag_id"],
                                    "name": dag["name"],
                                    "description": dag["description"],
                                    "nodes": len(dag["nodes"]),
                                    "edges": len(dag.get("edges", [])),
                                    "tags": dag.get("tags", []),
                                },
                                indent=2,
                            ),
                        }
                    ]
                }
            else:
                dags = []
                for fname in sorted(os.listdir(dag_def_dir)):
                    if fname.endswith(".json"):
                        d = dag_mod.load_json(os.path.join(dag_def_dir, fname))
                        dags.append(
                            {
                                "file": fname,
                                "dag_id": d.get("dag_id"),
                                "name": d.get("name"),
                                "nodes": len(d.get("nodes", [])),
                                "tags": d.get("tags", []),
                            }
                        )
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"available_dags": dags, "count": len(dags)}, indent=2
                            ),
                        }
                    ]
                }
        elif name == "write_dag_execute" or name == "write_dag_resume":
            dag_path = args.get("dag_path", "")
            if not os.path.isabs(dag_path):
                dag_path = os.path.join(dag_def_dir, dag_path)
            dag = dag_mod.load_dag_definition(dag_path)
            task_input = None
            if args.get("task_input"):
                task_input = json.loads(args["task_input"])
            dry = args.get("dry_run", False)
            result = dag_mod.execute_pipeline(
                dag,
                dry_run=dry,
                resume=(name == "write_dag_resume"),
                task_input=task_input,
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": f"Unknown DAG tool: {name}"}),
                    }
                ]
            }

    # Workstream Management
    if name.startswith("read_workstream_"):
        orch_mod = _get_module("task_orchestrator", "../task-orchestrator.py")
        if name == "read_workstream_list":
            ws_list = orch_mod.list_resumable_workstreams()
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"workstreams": ws_list, "count": len(ws_list)}, indent=2
                        ),
                    }
                ]
            }
        elif name == "read_workstream_status":
            ws_id = args.get("workstream_id", "")
            state = orch_mod.load_workstream_state(ws_id)
            if state:
                return {
                    "content": [{"type": "text", "text": json.dumps(state, indent=2)}]
                }
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": f"Workstream not found: {ws_id}"}),
                    }
                ]
            }

    # Skills & Agent Introspection
    if name == "read_skill_list":
        skills_dir = PROJECT_ROOT / "skills"
        active_skills = []
        if skills_dir.exists():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir() and (d / "SKILL.md").exists():
                    meta = (d / "SKILL.md").read_text(
                        encoding="utf-8", errors="replace"
                    )[:200]
                    active_skills.append(
                        {"name": d.name, "preview": meta.split("\n")[0] if meta else ""}
                    )
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"skills": active_skills, "count": len(active_skills)}, indent=2
                    ),
                }
            ]
        }

    if name == "read_agent_list":
        agents_file = PROJECT_ROOT / ".opencode" / "agents.md"
        agents = []
        if agents_file.exists():
            import re as _re2

            text = agents_file.read_text(encoding="utf-8", errors="replace")
            for line in text.split("\n"):
                m = _re2.match(r"@(\S+)\s*[:-]\s*(.+)", line)
                if m:
                    agents.append(
                        {"name": m.group(1), "description": m.group(2).strip()}
                    )
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"agents": agents, "count": len(agents)}, indent=2
                    ),
                }
            ]
        }

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}


#
# MCP Protocol
#


def send_message(msg):
    payload = json.dumps(msg, ensure_ascii=False)
    raw = payload.encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw)
    sys.stdout.buffer.flush()


def read_message():
    cl = 0
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line == b"\r\n":
            break
        d = line.decode("utf-8", errors="replace").strip()
        if ":" in d:
            k, v = d.split(":", 1)
            if k.strip().lower() == "content-length":
                cl = int(v.strip())
    if cl == 0:
        return None
    return json.loads(read_exact(cl).decode("utf-8"))


def _process_message(msg):
    try:
        mid = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})
        if method == "ping":
            send_message({"jsonrpc": "2.0", "id": mid, "result": {}})
            return True
        if method in ("health", "status"):
            send_message({"jsonrpc": "2.0", "id": mid, "result": {"status": "ok"}})
            return True
        if method == "initialize":
            send_message(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "CortexStratum", "version": VERSION},
                        "capabilities": {"tools": {"listChanged": True}},
                    },
                }
            )
            return True
        if method == "notifications/initialized":
            return True
        if method == "tools/list":
            send_message({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
            return True
        if method == "tools/call":
            tname = params.get("name", "")
            targs = params.get("arguments", {})
            q = queue.Queue()
            t = threading.Thread(
                target=execute_tool_async, args=(tname, targs, q), daemon=True
            )
            t.start()
            deadline = time.monotonic() + 65
            while time.monotonic() < deadline:
                try:
                    k, d = q.get(timeout=0.5)
                    if k == "result":
                        send_message({"jsonrpc": "2.0", "id": mid, "result": d})
                    else:
                        send_message(
                            {
                                "jsonrpc": "2.0",
                                "id": mid,
                                "error": {"code": -32000, "message": d},
                            }
                        )
                    return True
                except queue.Empty:
                    pass
            send_message(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": -32000, "message": "Tool timed out"},
                }
            )
            return True
        if mid:
            send_message(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )
        return True
    except Exception as e:
        print(f"[mcp-server] Error: {e}", file=sys.stderr, flush=True)
        if msg.get("id"):
            send_message(
                {
                    "jsonrpc": "2.0",
                    "id": msg["id"],
                    "error": {"code": -32700, "message": str(e)},
                }
            )
        return True


_pending_queue = queue.Queue()
_reader_shutdown = threading.Event()


def _reader_loop():
    while not _reader_shutdown.is_set():
        try:
            msg = read_message()
            if msg is None:
                break
            _pending_queue.put(msg)
        except Exception:
            break
    _reader_shutdown.set()


def _drain_pending():
    while not _pending_queue.empty():
        try:
            _process_message(_pending_queue.get_nowait())
        except queue.Empty:
            break


def main():
    _log("INFO", f"CortexStratum v{VERSION} starting ({len(TOOLS)} tools)...")
    reads = sum(1 for t in TOOLS if t.get("permission") == "read")
    writes = sum(1 for t in TOOLS if t.get("permission") == "write")
    mutates = sum(1 for t in TOOLS if t.get("permission") == "mutate")
    _log("INFO", f"Tools: {reads} read, {writes} write, {mutates} mutate")
    # Export memory summary for dashboard
    try:
        ms = _get_memory_search()
        s = ms.status()
        import json as _json

        _json.dump(
            {
                "memory_count": s["memory_count"],
                "fts_indexed": s["fts_indexed"],
                "storage_backend": s["storage_backend"],
                "vector_search": str(s.get("vector_search", "")),
                "vector_count": s.get("vector_count", 0),
                "last_timestamp": str(s.get("last_memory_timestamp", "")),
            },
            open(str(DATA_DIR / "memory-summary.json"), "w"),
            indent=2,
        )
    except Exception as e:
        _log("WARN", f"Could not export memory summary: {e}")
    reader = threading.Thread(target=_reader_loop, daemon=True)
    reader.start()
    while not _reader_shutdown.is_set():
        try:
            _process_message(_pending_queue.get(timeout=0.5))
        except queue.Empty:
            continue
    _reader_shutdown.set()


if __name__ == "__main__":
    import sys as _sys

    args = [a.lower() for a in _sys.argv[1:]]
    if any(a in args for a in ("--help", "-h", "/?")):
        print(f"\nCortexStratum MCP Server v{VERSION}\n{len(TOOLS)} tools\n")
        _sys.exit(0)
    if "--version" in args:
        print(f"v{VERSION}")
        _sys.exit(0)
    if "--list-tools" in args:
        print(json.dumps(TOOLS, indent=2))
        _sys.exit(0)
    if "--permissive" in args:
        import sys as m

        m.modules[__name__].PERMISSIVE_MODE = True
    if "--debug" in args:
        import sys as m

        m.modules[__name__].DEBUG_MODE = True
    main()
