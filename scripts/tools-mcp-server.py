#!/usr/bin/env python3
"""
MCP Server: ai-memory-core Toolchain
79 tools: xTrace, DTrace, Skill Router, Goal Registry, Commitment Checker,
Lifecycle Hooks, Permission Audit, Tool Router, NE-Memory, Sensory, Audio,
Coder, DevOps, Game Dev, Art, Literature, Verifier.

All tools have MCP annotations (destructiveHint, readOnlyHint).
All write/mutate tools accept dry_run=true for preview.
"""

import json, sys, os, subprocess, time, re, threading, queue, select, hashlib
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
VERSION = "0.4.0"

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
        return (False, f"Tool '{tool_name}' requires {permission} — blocked in auto mode")
    if permission in (PERMISSION_WRITE, PERMISSION_MUTATE):
        return (True, f"⚠️ {tool_name} has {permission} permission")
    return (True, "ok")

_verifier = None; _memory_search = None; _MODULE_CACHE = {}

def _get_module(name, filename):
    if name not in _MODULE_CACHE:
        import importlib.util as _util
        fp = SCRIPTS_DIR / filename
        if not fp.exists(): raise FileNotFoundError(f"Module not found: {fp}")
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
        if t["name"] == name: return t.get("permission") in permissions
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
        if not chunk: raise EOFError(f"Expected {n} bytes, got {len(buf)}")
        buf += chunk
    return buf

def execute_tool_async(name, args, result_queue):
    try:
        result = handle_tool_call(name, args)
        result_queue.put(("result", result))
    except Exception as e:
        result_queue.put(("error", str(e)))

# ═══════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS (79 tools, all annotated)
# ═══════════════════════════════════════════════════════════════════════

A = lambda d: {"destructiveHint": d, "readOnlyHint": not d, "idempotentHint": not d, "openWorldHint": False}
DR = lambda: {"type": "boolean", "default": False, "description": "Preview without executing"}

TOOLS = [
    # ── xTrace Error Registry ───────────────────────────────────────
    {"name": "write_xtrace_log_error", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}, "error_output": {"type": "string"}, "exit_code": {"type": "integer"}, "dry_run": DR()}, "required": ["command", "error_output"]}},
    {"name": "read_xtrace_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}},
    {"name": "read_xtrace_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},

    # ── DTrace Decision Registry ────────────────────────────────────
    {"name": "write_dtrace_add", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "context": {"type": "string"}, "decision": {"type": "string"}, "alternatives": {"type": "string"}, "rationale": {"type": "string"}, "category": {"type": "string", "enum": ["architecture", "process", "technology", "security"]}, "dry_run": DR()}, "required": ["title", "decision", "rationale"]}},
    {"name": "read_dtrace_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}},

    # ── Skill Router ──────────────────────────────────────────────
    {"name": "read_skill_router_match", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]}},

    # ── Tool Router ────────────────────────────────────────────────
    {"name": "read_tools_suggest", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"task": {"type": "string", "description": "Describe what you want to do"}, "top_k": {"type": "integer", "default": 3}}, "required": ["task"]}},

    # ── Goal Registry ─────────────────────────────────────────────
    {"name": "write_goal_registry_init", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"goal": {"type": "string"}, "dry_run": DR()}, "required": ["goal"]}},
    {"name": "write_goal_registry_add_subgoal", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"description": {"type": "string"}, "dry_run": DR()}, "required": ["description"]}},
    {"name": "read_goal_registry_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "read_goal_registry_check_alignment", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"current_action": {"type": "string"}}, "required": ["current_action"]}},

    # ── Commitment Checker ─────────────────────────────────────────
    {"name": "read_commitment_checker_list", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "mutate_commitment_checker_verify", "permission": "mutate", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "dry_run": DR()}, "required": ["id"]}},

    # ── Lifecycle Hooks ────────────────────────────────────────────
    {"name": "read_hooks_prefetch", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}, "project": {"type": "string"}, "goal": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}}, "max_memories": {"type": "integer", "default": 8}, "max_decisions": {"type": "integer", "default": 5}, "max_errors": {"type": "integer", "default": 5}}}},
    {"name": "write_hooks_observe", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}, "event_type": {"type": "string", "enum": ["decision", "error", "insight", "preference", "milestone", "handoff"]}, "description": {"type": "string"}, "metadata": {"type": "object"}, "dry_run": DR()}, "required": ["session_id", "event_type", "description"]}},
    {"name": "read_hooks_session_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}}, "required": ["session_id"]}},
    {"name": "write_hooks_session_end", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}, "summary": {"type": "string"}, "persist_observations": {"type": "boolean", "default": True}, "dry_run": DR()}, "required": ["session_id"]}},

    # ── Permission Audit ───────────────────────────────────────────
    {"name": "mutate_undo", "permission": "mutate", "annotations": {"destructiveHint": False, "readOnlyHint": False, "idempotentHint": True, "openWorldHint": False}, "inputSchema": {"type": "object", "properties": {"checkpoint_id": {"type": "string"}}, "required": ["checkpoint_id"]}},
    {"name": "read_audit_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},

    # ── NE-Memory Search (BM25 + vector + reranker) ────────────────
    {"name": "read_memory_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}, "fuzzy_threshold": {"type": "number", "default": 0.85}}, "required": ["query"]}},
    {"name": "read_memory_synthesize", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "max_sources": {"type": "integer", "default": 5}, "min_confidence": {"type": "number", "default": 0.7}}, "required": ["query"]}},
    {"name": "read_memory_vector_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": ["query"]}},
    {"name": "read_memory_hybrid_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}, "bm25_weight": {"type": "number", "default": 0.5}, "vector_weight": {"type": "number", "default": 0.5}, "rrf_k": {"type": "integer", "default": 60}}, "required": ["query"]}},
    {"name": "read_memory_reranked_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}, "candidates": {"type": "integer", "default": 20}}, "required": ["query"]}},
    {"name": "write_memory_add", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "source": {"type": "string", "default": "manual"}, "metadata": {"type": "object"}, "dry_run": DR()}, "required": ["text"]}},
    {"name": "mutate_memory_consolidate", "permission": "mutate", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"threshold": {"type": "number", "default": 0.85}, "dry_run": {"type": "boolean", "default": False}}}},
    {"name": "read_memory_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},

    # ── Verifier Middleware ────────────────────────────────────────
    {"name": "read_verifier_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "write_verifier_renudge", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}, "correction": {"type": "object"}, "strategy": {"type": "string", "enum": ["incremental", "rollback", "override", "halt"], "default": "incremental"}, "dry_run": DR()}, "required": ["target", "correction"]}},
    {"name": "write_verifier_clear_renudge", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}, "dry_run": DR()}, "required": ["target"]}},

    # ── Art Module ─────────────────────────────────────────────────
    {"name": "read_art_generate_svg", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"description": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}}, "required": ["description"]}},
    {"name": "read_art_generate_theme", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"description": {"type": "string", "default": "dark cyberpunk"}}, "required": ["description"]}},
    {"name": "read_art_extract_palette", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"color": {"type": "string"}}, "required": ["color"]}},
    {"name": "read_art_design_concept", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"requirements": {"type": "string"}}, "required": ["requirements"]}},

    # ── Literature Module ──────────────────────────────────────────
    {"name": "read_lit_analyze_text", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "read_lit_extract_concepts", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "read_lit_generate_study_guide", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
    {"name": "read_lit_analyze_philosophy", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},

    # ── Sensory Module ─────────────────────────────────────────────
    {"name": "read_sensory_browse", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "extract_mode": {"type": "string", "enum": ["text", "html", "markdown", "links", "metadata"], "default": "text"}, "timeout_ms": {"type": "integer", "default": 30000}}, "required": ["url"]}},
    {"name": "read_sensory_screenshot", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "output_path": {"type": "string"}, "timeout_ms": {"type": "integer", "default": 30000}}, "required": ["url"]}},
    {"name": "mutate_sensory_interact", "permission": "mutate", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "actions": {"type": "array", "items": {"type": "object", "properties": {"type": {"type": "string", "enum": ["click", "type", "press", "wait"]}, "selector": {"type": "string"}, "value": {"type": "string"}}}}, "dry_run": DR()}, "required": ["url", "actions"]}},
    {"name": "read_sensory_extract_pdf", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "max_pages": {"type": "integer", "default": 50}}, "required": ["file_path"]}},
    {"name": "read_sensory_extract_html", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"html_content": {"type": "string"}, "mode": {"type": "string", "enum": ["clean", "soup", "tables"], "default": "clean"}}, "required": ["html_content"]}},
    {"name": "read_sensory_extract_image", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
    {"name": "read_sensory_scrape", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "mode": {"type": "string", "enum": ["text", "html", "links", "tables", "json"], "default": "text"}, "headers": {"type": "object"}}, "required": ["url"]}},
    {"name": "read_sensory_extract_article", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "read_sensory_api_request", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"], "default": "GET"}, "data": {"type": "object"}, "headers": {"type": "object"}, "params": {"type": "object"}, "timeout": {"type": "integer", "default": 15}}, "required": ["url"]}},
    {"name": "read_sensory_fetch_rss", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"feed_url": {"type": "string"}, "max_items": {"type": "integer", "default": 50}}, "required": ["feed_url"]}},
    {"name": "read_sensory_read_file", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "max_size_kb": {"type": "integer", "default": 500}}, "required": ["file_path"]}},
    {"name": "read_sensory_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "num_results": {"type": "integer", "default": 8}}, "required": ["query"]}},
    {"name": "read_sensory_set_browser_type", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"browser_type": {"type": "string", "enum": ["firefox", "chromium"]}}, "required": ["browser_type"]}},

    # ── Audio Module ───────────────────────────────────────────────
    {"name": "read_audio_analyze_file", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": []}},
    {"name": "read_audio_waveform", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "width": {"type": "integer", "default": 80}, "height": {"type": "integer", "default": 20}}, "required": ["file_path"]}},
    {"name": "read_audio_frequency_analysis", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "num_bands": {"type": "integer", "default": 10}}, "required": ["file_path"]}},
    {"name": "read_audio_music_theory", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"notes": {"type": "array", "items": {"type": "string"}}, "frequencies": {"type": "array", "items": {"type": "number"}}}, "required": []}},
    {"name": "read_audio_speech_analysis", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"transcript": {"type": "string"}, "duration_seconds": {"type": "number"}}, "required": ["transcript", "duration_seconds"]}},
    {"name": "read_audio_convert_guide", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"source_format": {"type": "string"}, "target_format": {"type": "string"}}, "required": ["source_format", "target_format"]}},
    {"name": "read_audio_generate_tone", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"frequency": {"type": "number", "default": 440}, "duration_seconds": {"type": "number", "default": 1}}, "required": []}},

    # ── Coder Module ───────────────────────────────────────────────
    {"name": "read_coder_analyze_code", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}}, "required": ["code", "language"]}},
    {"name": "read_coder_generate_framework", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "language": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}}}, "required": ["project_type", "language"]}},
    {"name": "read_coder_debug", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"error": {"type": "string"}, "code_context": {"type": "string", "default": ""}, "language": {"type": "string"}}, "required": ["error", "language"]}},
    {"name": "read_coder_review", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}, "focus": {"type": "string", "default": "all"}}, "required": ["code", "language"]}},
    {"name": "read_coder_explain", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}, "level": {"type": "string", "default": "intermediate"}}, "required": ["code", "language"]}},
    {"name": "read_coder_convert", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "from": {"type": "string"}, "to": {"type": "string"}}, "required": ["code", "from", "to"]}},
    {"name": "read_coder_architecture", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "scale": {"type": "string", "default": "medium"}, "requirements": {"type": "array", "items": {"type": "string"}}}, "required": ["project_type"]}},

    # ── DevOps Module ──────────────────────────────────────────────
    {"name": "read_devops_container_debug", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"error_log": {"type": "string"}, "runtime": {"type": "string", "default": "podman"}}, "required": ["error_log"]}},
    {"name": "read_devops_permissions_analyze", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"mount_path": {"type": "string"}, "container_user": {"type": "string"}, "host_user": {"type": "string"}, "error_symptom": {"type": "string"}}, "required": []}},
    {"name": "read_devops_compose_generator", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"services": {"type": "array"}, "networks": {"type": "array"}, "runtime": {"type": "string", "default": "docker"}}, "required": ["services"]}},
    {"name": "read_devops_samba_config", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"share_name": {"type": "string"}, "path": {"type": "string"}}, "required": ["share_name", "path"]}},
    {"name": "read_devops_mergerfs_setup", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"source_paths": {"type": "array"}, "mount_point": {"type": "string"}, "policy": {"type": "string", "default": "epmfs"}}, "required": ["source_paths", "mount_point"]}},
    {"name": "read_devops_dockerfile_analyze", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"dockerfile": {"type": "string"}}, "required": ["dockerfile"]}},
    {"name": "read_devops_network_troubleshoot", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"symptom": {"type": "string"}}, "required": ["symptom"]}},

    # ── Game Dev Module ────────────────────────────────────────────
    {"name": "read_gamedev_design_analyze", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"concept": {"type": "string"}, "genre": {"type": "string"}}, "required": ["concept", "genre"]}},
    {"name": "read_gamedev_scaffold_project", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"engine": {"type": "string"}, "genre": {"type": "string"}, "name": {"type": "string", "default": "MyGame"}}, "required": ["engine", "genre"]}},
    {"name": "read_gamedev_mechanics_guide", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}}, "required": ["genre"]}},
    {"name": "read_gamedev_monetization", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"platform": {"type": "string"}, "genre": {"type": "string"}}, "required": ["platform", "genre"]}},
    {"name": "read_gamedev_optimization", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"engine": {"type": "string"}, "issue": {"type": "string"}}, "required": ["engine", "issue"]}},
    {"name": "read_gamedev_compare_engines", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "team_size": {"type": "string", "default": "solo"}, "budget": {"type": "string", "default": "indie"}}, "required": ["project_type"]}},
    {"name": "read_gamedev_level_design", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}, "level_type": {"type": "string"}}, "required": ["genre", "level_type"]}},
]

# ═══════════════════════════════════════════════════════════════════════
# HANDLE TOOL CALL
# ═══════════════════════════════════════════════════════════════════════

def handle_tool_call(name, args):
    _log("DEBUG", f"handle_tool_call: {name}")
    # Permission check
    allowed, reason = can_call_tool(name, {"mode": "interactive" if not PERMISSIVE_MODE else "permissive"})
    if not allowed:
        return {"content": [{"type": "text", "text": json.dumps({"error": "permission_denied", "tool": name, "reason": reason})}]}
    verifier = _get_verifier()
    pre = verifier.pre_verify(name, args)
    if not pre["passed"]:
        return {"content": [{"type": "text", "text": json.dumps({"error": "verifier_rejected", "violations": pre["violations"]})}]}

    # Dry-run intercept
    if args.get("dry_run") and _is_permission(name, (PERMISSION_WRITE, PERMISSION_MUTATE)):
        audit = _get_audit()
        sim = audit.simulate(name, args)
        sim["undo_token"] = None
        sim["note"] = "Dry run only. Execute without dry_run=true to commit."
        return {"content": [{"type": "text", "text": json.dumps(sim, indent=2)}]}

    # Checkpoint before memory mutations
    if name in ("write_memory_add", "mutate_memory_consolidate") and not args.get("dry_run"):
        ckpt = _get_audit().checkpoint(name, args)
    else:
        ckpt = None

    # Memory tools
    if name in ("read_memory_search", "read_memory_synthesize", "read_memory_vector_search",
                "read_memory_hybrid_search", "read_memory_reranked_search",
                "write_memory_add", "mutate_memory_consolidate", "read_memory_status"):
        mem = _get_memory_search()
        if name == "read_memory_search":
            r = mem.search(args.get("query",""), args.get("limit",10), args.get("fuzzy_threshold",0.85))
        elif name == "read_memory_synthesize":
            r = mem.synthesize(args.get("query",""), args.get("max_sources",5), args.get("min_confidence",0.7))
        elif name == "read_memory_vector_search":
            r = mem.vector_search(args.get("query",""), args.get("limit",10))
        elif name == "read_memory_hybrid_search":
            r = mem.hybrid_search(args.get("query",""), args.get("limit",10),
                                  args.get("bm25_weight",0.5), args.get("vector_weight",0.5), args.get("rrf_k",60))
        elif name == "read_memory_reranked_search":
            r = mem.reranked_search(args.get("query",""), args.get("limit",5), args.get("candidates",20))
        elif name == "write_memory_add":
            r = {"memory_id": mem.add_memory(args.get("text",""), args.get("source","manual"), args.get("metadata",{})), "status": "stored"}
        elif name == "mutate_memory_consolidate":
            r = mem.consolidate(threshold=args.get("threshold",0.85), dry_run=args.get("dry_run",False))
        else:
            r = mem.status()
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    # Verifier
    if name in ("read_verifier_status", "write_verifier_renudge", "write_verifier_clear_renudge"):
        if name == "read_verifier_status": r = verifier.get_status()
        elif name == "write_verifier_renudge": r = verifier.renudge(args.get("target",""), args.get("correction",{}), args.get("strategy","incremental"))
        else: r = verifier.clear_renudge(args.get("target",""))
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    # Permission Audit
    if name == "read_audit_status":
        return {"content": [{"type": "text", "text": json.dumps(_get_audit().status(), indent=2)}]}
    if name == "mutate_undo":
        return {"content": [{"type": "text", "text": json.dumps(_get_audit().undo(args.get("checkpoint_id","")), indent=2)}]}

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
                            if s not in matched: matched.append(s)
                        break
            if not matched:
                matched = config.get("default_skills", [])
            return {"content": [{"type": "text", "text": json.dumps({"matched_skills": matched, "count": len(matched)})}]}
        return {"content": [{"type": "text", "text": "Router not found"}]}

    # Tool suggest
    if name == "read_tools_suggest":
        try:
            from tool_router import suggest
            s = suggest(args.get("task",""), TOOLS, args.get("top_k",3))
            return {"content": [{"type": "text", "text": json.dumps({"task": args.get("task",""), "suggestions": s, "total_tools": len(TOOLS)})}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Tool suggest failed: {e}"})}]}

    # Trace system
    if name in ("write_xtrace_log_error", "read_xtrace_search", "read_xtrace_status",
                "write_dtrace_add", "read_dtrace_search",
                "write_goal_registry_init", "write_goal_registry_add_subgoal",
                "read_goal_registry_status", "read_goal_registry_check_alignment",
                "read_commitment_checker_list", "mutate_commitment_checker_verify"):
        return {"content": [{"type": "text", "text": json.dumps(_get_trace().handle_tool_call(name, args), indent=2)}]}

    # Art
    if name.startswith("read_art_"):
        art = _get_module("art_module", "art-module.py")
        if "svg" in name: r = art.generate_svg(args.get("description",""), args.get("width",400), args.get("height",300))
        elif "theme" in name: r = art.generate_theme(args.get("description","dark cyberpunk"))
        elif "palette" in name: r = art.extract_palette(args.get("color","#3b82f6"))
        else: r = art.design_concept(args.get("requirements","A modern dashboard"))
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2) if isinstance(r,dict) else r}]}

    # Literature
    if name.startswith("read_lit_"):
        lit = _get_module("lit_module", "literature-module.py")
        if "analyze_text" in name: r = lit.analyze_text(args.get("text",""))
        elif "concepts" in name: r = lit.extract_concepts(args.get("text",""))
        elif "study" in name: r = lit.generate_study_guide(args.get("content",""))
        else: r = lit.analyze_philosophy(args.get("text",""))
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    # Sensory
    if name.startswith("read_sensory_") or name.startswith("mutate_sensory_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("sensory_module","sensory-module.py").handle_tool_call(name, args), indent=2)}]}

    # Audio
    if name.startswith("read_audio_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("audio_module","audio-module.py").handle_tool_call(name, args), indent=2)}]}

    # Coder
    if name.startswith("read_coder_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("coder_module","coder-module.py").coder_handle_tool_call(name, args), indent=2)}]}

    # DevOps
    if name.startswith("read_devops_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("devops_module","devops-module.py").devops_handle_tool_call(name, args), indent=2)}]}

    # GameDev
    if name.startswith("read_gamedev_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("gamedev_module","game-dev-module.py").gamedev_handle_tool_call(name, args), indent=2)}]}

    # Hooks
    if name.startswith("read_hooks_") or name.startswith("write_hooks_"):
        hooks = _get_module("hooks_module", "hooks.py")
        if not hasattr(hooks, '_wired'):
            hm = hooks._get_hooks()
            hm._memory_search = _get_memory_search().search
            hm._trace_handle = _get_trace().handle_tool_call
            hooks._wired = True
        return {"content": [{"type": "text", "text": json.dumps(hooks.hooks_handle_tool_call(name, args), indent=2)}]}

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

# ═══════════════════════════════════════════════════════════════════════
# MCP Protocol
# ═══════════════════════════════════════════════════════════════════════

def send_message(msg):
    payload = json.dumps(msg, ensure_ascii=False)
    raw = payload.encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("utf-8") + raw)
    sys.stdout.buffer.flush()

def read_message():
    cl = 0; deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        line = sys.stdin.buffer.readline()
        if not line: return None
        if line == b"\r\n": break
        d = line.decode("utf-8", errors="replace").strip()
        if ":" in d:
            k, v = d.split(":", 1)
            if k.strip().lower() == "content-length": cl = int(v.strip())
    if cl == 0: return None
    return json.loads(read_exact(cl).decode("utf-8"))

def _process_message(msg):
    try:
        mid = msg.get("id"); method = msg.get("method"); params = msg.get("params", {})
        if method == "ping": send_message({"jsonrpc":"2.0","id":mid,"result":{}}); return True
        if method in ("health","status"): send_message({"jsonrpc":"2.0","id":mid,"result":{"status":"ok"}}); return True
        if method == "initialize":
            send_message({"jsonrpc":"2.0","id":mid,"result":{"protocolVersion":"2024-11-05","serverInfo":{"name":"ai-memory-core","version":VERSION},"capabilities":{"tools":{"listChanged":True}}}}); return True
        if method == "notifications/initialized": return True
        if method == "tools/list":
            send_message({"jsonrpc":"2.0","id":mid,"result":{"tools":TOOLS}}); return True
        if method == "tools/call":
            tname = params.get("name",""); targs = params.get("arguments",{})
            q = queue.Queue()
            t = threading.Thread(target=execute_tool_async, args=(tname, targs, q), daemon=True)
            t.start()
            deadline = time.monotonic() + 65
            while time.monotonic() < deadline:
                try:
                    k, d = q.get(timeout=0.5)
                    if k == "result": send_message({"jsonrpc":"2.0","id":mid,"result":d})
                    else: send_message({"jsonrpc":"2.0","id":mid,"error":{"code":-32000,"message":d}})
                    return True
                except queue.Empty: pass
            send_message({"jsonrpc":"2.0","id":mid,"error":{"code":-32000,"message":"Tool timed out"}}); return True
        if mid: send_message({"jsonrpc":"2.0","id":mid,"error":{"code":-32601,"message":f"Method not found: {method}"}})
        return True
    except Exception as e:
        print(f"[mcp-server] Error: {e}", file=sys.stderr, flush=True)
        if msg.get("id"): send_message({"jsonrpc":"2.0","id":msg["id"],"error":{"code":-32700,"message":str(e)}})
        return True

_pending_queue = queue.Queue()
_reader_shutdown = threading.Event()

def _reader_loop():
    while not _reader_shutdown.is_set():
        try:
            msg = read_message()
            if msg is None: break
            _pending_queue.put(msg)
        except: break
    _reader_shutdown.set()

def _drain_pending():
    while not _pending_queue.empty():
        try: _process_message(_pending_queue.get_nowait())
        except queue.Empty: break

def main():
    _log("INFO", f"ai-memory-core v{VERSION} starting ({len(TOOLS)} tools)...")
    reads = sum(1 for t in TOOLS if t.get("permission")=="read")
    writes = sum(1 for t in TOOLS if t.get("permission")=="write")
    mutates = sum(1 for t in TOOLS if t.get("permission")=="mutate")
    _log("INFO", f"Tools: {reads} read, {writes} write, {mutates} mutate")
    reader = threading.Thread(target=_reader_loop, daemon=True)
    reader.start()
    while not _reader_shutdown.is_set():
        try: _process_message(_pending_queue.get(timeout=0.5))
        except queue.Empty: continue
    _reader_shutdown.set()

if __name__ == "__main__":
    import sys as _sys
    args = [a.lower() for a in _sys.argv[1:]]
    if any(a in args for a in ("--help","-h","/?")):
        print(f"\nai-memory-core MCP Server v{VERSION}\n{len(TOOLS)} tools\n")
        _sys.exit(0)
    if "--version" in args: print(f"v{VERSION}"); _sys.exit(0)
    if "--list-tools" in args: print(json.dumps(TOOLS, indent=2)); _sys.exit(0)
    if "--permissive" in args: import sys as m; m.modules[__name__].PERMISSIVE_MODE = True
    if "--debug" in args: import sys as m; m.modules[__name__].DEBUG_MODE = True
    main()
