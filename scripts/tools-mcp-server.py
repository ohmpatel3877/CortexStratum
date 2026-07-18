#!/usr/bin/env python3
"""
MCP Server: CortexStratum Toolchain
133 tools: memory, trace, simulation (mechanics/FEA/CFD/math), compact, mutation,
plumber, focus, pedagogy, consolidation, sensory, audio, coder, devops, gamedev,
art, lit, verifier, hooks, skill router, goal registry, commitment checker.

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
VERSION = "0.5.0"

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
        return (False, f"Tool '{tool_name}' requires {permission} permission — blocked in auto mode. Fix: start server with --permissive flag, or pass dry_run=true to preview.")
    if permission in (PERMISSION_WRITE, PERMISSION_MUTATE):
        return (True, f" {tool_name} modifies persistent state ({permission} permission). Use dry_run=true to preview before committing.")
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

from utils import load_json, save_json

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

# 
# TOOL DEFINITIONS (79 tools, all annotated)
# 

A = lambda d: {"destructiveHint": d, "readOnlyHint": not d, "idempotentHint": not d, "openWorldHint": False}
DR = lambda: {"type": "boolean", "default": False, "description": "Preview without executing"}

TOOLS = [
    #  xTrace Error Registry 
    {"name": "write_xtrace_log_error", "description": " WRITE — Log an error to the xTrace registry. Use dry_run=true to preview before persisting.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}, "error_output": {"type": "string"}, "exit_code": {"type": "integer"}, "dry_run": DR()}, "required": ["command", "error_output"]}},
    {"name": "read_xtrace_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}},
    {"name": "read_xtrace_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},

    #  DTrace Decision Registry 
    {"name": "write_dtrace_add", "description": " WRITE — Register an architecture decision. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "context": {"type": "string"}, "decision": {"type": "string"}, "alternatives": {"type": "string"}, "rationale": {"type": "string"}, "category": {"type": "string", "enum": ["architecture", "process", "technology", "security"]}, "dry_run": DR()}, "required": ["title", "decision", "rationale"]}},
    {"name": "read_dtrace_search", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}},

    #  Skill Router 
    {"name": "read_skill_router_match", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]}},

    #  Tool Router 
    {"name": "read_tools_suggest", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"task": {"type": "string", "description": "Describe what you want to do"}, "top_k": {"type": "integer", "default": 3}}, "required": ["task"]}},

    #  Goal Registry 
    {"name": "write_goal_registry_init", "description": " WRITE — Initialize a new goal. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"goal": {"type": "string"}, "dry_run": DR()}, "required": ["goal"]}},
    {"name": "write_goal_registry_add_subgoal", "description": " WRITE — Add a sub-goal to the current goal. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"description": {"type": "string"}, "dry_run": DR()}, "required": ["description"]}},
    {"name": "read_goal_registry_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "read_goal_registry_check_alignment", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"current_action": {"type": "string"}}, "required": ["current_action"]}},

    #  Commitment Checker 
    {"name": "read_commitment_checker_list", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "write_commitment_verify", "description": " MUTATE — Verify a commitment (marks as fulfilled). Use dry_run=true to preview.", "permission": "mutate", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "dry_run": DR()}, "required": ["id"]}},

    #  Lifecycle Hooks 
    {"name": "read_hooks_prefetch", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}, "project": {"type": "string"}, "goal": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}}, "max_memories": {"type": "integer", "default": 8}, "max_decisions": {"type": "integer", "default": 5}, "max_errors": {"type": "integer", "default": 5}}}},
    {"name": "write_hooks_observe", "description": " WRITE — Log a session event. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}, "event_type": {"type": "string", "enum": ["decision", "error", "insight", "preference", "milestone", "handoff"]}, "description": {"type": "string"}, "metadata": {"type": "object"}, "dry_run": DR()}, "required": ["session_id", "event_type", "description"]}},
    {"name": "read_hooks_session_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}}, "required": ["session_id"]}},
    {"name": "write_hooks_session_end", "description": " WRITE — End a session and persist observations. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}, "summary": {"type": "string"}, "persist_observations": {"type": "boolean", "default": True}, "dry_run": DR()}, "required": ["session_id"]}},

    #  Permission Audit 
    {"name": "write_audit_undo", "description": " MUTATE — Undo a previous write/mutate operation via checkpoint ID. Destructive — cannot be reversed.", "permission": "mutate", "annotations": {"destructiveHint": False, "readOnlyHint": False, "idempotentHint": True, "openWorldHint": False}, "inputSchema": {"type": "object", "properties": {"checkpoint_id": {"type": "string"}}, "required": ["checkpoint_id"]}},
    {"name": "read_audit_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "read_phase_status", "description": "MERGED - Get status for any domain: compact, mutation, audit, consolidation.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"domain": {"type": "string", "default": "compact", "enum": ["compact", "mutation", "audit", "consolidation"]}}, "required": ["domain"]}},

    #  NE-Memory Search (BM25 + vector + reranker) 
    {"name": "read_memory_search", "description": "MERGED — Search memory. mode=[bm25|vector|hybrid|reranked]. Replaces vector/hybrid/reranked variants.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "mode": {"type": "string", "default": "bm25", "enum": ["bm25", "vector", "hybrid", "reranked"]}, "limit": {"type": "integer", "default": 10}, "fuzzy_threshold": {"type": "number", "default": 0.85}, "bm25_weight": {"type": "number", "default": 0.5}, "vector_weight": {"type": "number", "default": 0.5}, "rrf_k": {"type": "integer", "default": 60}, "candidates": {"type": "integer", "default": 20}}, "required": ["query"]}},
    {"name": "read_memory_synthesize", "description": "Narrative synthesis from search results.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "max_sources": {"type": "integer", "default": 5}, "min_confidence": {"type": "number", "default": 0.7}}, "required": ["query"]}},

    {"name": "write_memory_add", "description": " WRITE — Store a new memory entry. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "source": {"type": "string", "default": "manual"}, "metadata": {"type": "object"}, "dry_run": DR()}, "required": ["text"]}},
    {"name": "write_memory_consolidate", "description": " WRITE — Consolidate memory (dedup, prune, index). Use dry_run=true to preview.", "permission": "write", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"threshold": {"type": "number", "default": 0.85}, "dry_run": {"type": "boolean", "default": False}}}},
    {"name": "read_memory_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},

    #  Verifier Middleware 
    {"name": "read_verifier_status", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "write_verifier_renudge", "description": " WRITE — Apply a correction renudge to verifier state. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}, "correction": {"type": "object"}, "strategy": {"type": "string", "enum": ["incremental", "rollback", "override", "halt"], "default": "incremental"}, "dry_run": DR()}, "required": ["target", "correction"]}},
    {"name": "write_verifier_clear_renudge", "description": " WRITE — Clear a previous renudge. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}, "dry_run": DR()}, "required": ["target"]}},

    #  Art Module 
    {"name": "read_art_generate_svg", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"description": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}}, "required": ["description"]}},
    {"name": "read_art_generate_theme", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"description": {"type": "string", "default": "dark cyberpunk"}}, "required": ["description"]}},
    {"name": "read_art_extract_palette", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"color": {"type": "string"}}, "required": ["color"]}},
    {"name": "read_art_design_concept", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"requirements": {"type": "string"}}, "required": ["requirements"]}},

    #  Literature Module 
    {"name": "read_lit_analyze_text", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "read_lit_extract_concepts", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "read_lit_generate_study_guide", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},


    #  Sensory Module 
    {"name": "read_sensory_fetch", "description": "MERGED — Fetch URL content. Replaces browse + scrape + extract_article. method=[browser|http|article]", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string", "default": "browser", "enum": ["browser", "http", "article"]}, "mode": {"type": "string", "default": "text", "enum": ["text", "html", "markdown", "links", "metadata", "tables", "json"]}, "headers": {"type": "object"}, "timeout_ms": {"type": "integer", "default": 30000}}, "required": ["url"]}},

    {"name": "read_sensory_screenshot", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "output_path": {"type": "string"}, "timeout_ms": {"type": "integer", "default": 30000}}, "required": ["url"]}},
    {"name": "write_sensory_interact", "description": " MUTATE — Interact with a web page (click, type, press). Use dry_run=true to preview.", "permission": "mutate", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "actions": {"type": "array", "items": {"type": "object", "properties": {"type": {"type": "string", "enum": ["click", "type", "press", "wait"]}, "selector": {"type": "string"}, "value": {"type": "string"}}}}, "dry_run": DR()}, "required": ["url", "actions"]}},
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

    #  Audio Module 
    {"name": "read_audio_analyze_file", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": []}},
    {"name": "read_audio_waveform", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "width": {"type": "integer", "default": 80}, "height": {"type": "integer", "default": 20}}, "required": ["file_path"]}},
    {"name": "read_audio_frequency_analysis", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "num_bands": {"type": "integer", "default": 10}}, "required": ["file_path"]}},
    {"name": "read_audio_music_theory", "description": "Foundation for audio suite: chord/scale/mode analysis. Future: EQ, room analysis, convolution.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"notes": {"type": "array", "items": {"type": "string"}}, "frequencies": {"type": "array", "items": {"type": "number"}}}, "required": []}},
    {"name": "read_audio_generate_tone", "description": "Foundation for audio suite: tone synthesis. Future: sweeps, noise, impulse responses.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"frequency": {"type": "number", "default": 440}, "duration_seconds": {"type": "number", "default": 1}}, "required": []}},

    {"name": "read_audio_speech_analysis", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"transcript": {"type": "string"}, "duration_seconds": {"type": "number"}}, "required": ["transcript", "duration_seconds"]}},
    {"name": "read_audio_convert_guide", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"source_format": {"type": "string"}, "target_format": {"type": "string"}}, "required": ["source_format", "target_format"]}},


    #  Coder Module 
    {"name": "read_coder_analyze_code", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}}, "required": ["code", "language"]}},
    {"name": "read_coder_generate_framework", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "language": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}}}, "required": ["project_type", "language"]}},
    {"name": "read_coder_debug", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"error": {"type": "string"}, "code_context": {"type": "string", "default": ""}, "language": {"type": "string"}}, "required": ["error", "language"]}},
    {"name": "read_coder_review", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}, "focus": {"type": "string", "default": "all"}}, "required": ["code", "language"]}},
    {"name": "read_coder_explain", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}, "level": {"type": "string", "default": "intermediate"}}, "required": ["code", "language"]}},
    {"name": "read_coder_convert", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "from": {"type": "string"}, "to": {"type": "string"}}, "required": ["code", "from", "to"]}},
    {"name": "read_coder_architecture", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "scale": {"type": "string", "default": "medium"}, "requirements": {"type": "array", "items": {"type": "string"}}}, "required": ["project_type"]}},

    #  DevOps Module 
    {"name": "read_devops_container_debug", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"error_log": {"type": "string"}, "runtime": {"type": "string", "default": "podman"}}, "required": ["error_log"]}},
    {"name": "read_devops_permissions_analyze", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"mount_path": {"type": "string"}, "container_user": {"type": "string"}, "host_user": {"type": "string"}, "error_symptom": {"type": "string"}}, "required": []}},
    {"name": "read_devops_compose_generator", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"services": {"type": "array"}, "networks": {"type": "array"}, "runtime": {"type": "string", "default": "docker"}}, "required": ["services"]}},

    {"name": "read_devops_mergerfs_setup", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"source_paths": {"type": "array"}, "mount_point": {"type": "string"}, "policy": {"type": "string", "default": "epmfs"}}, "required": ["source_paths", "mount_point"]}},
    {"name": "read_devops_dockerfile_analyze", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"dockerfile": {"type": "string"}}, "required": ["dockerfile"]}},
    {"name": "read_devops_network_troubleshoot", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"symptom": {"type": "string"}}, "required": ["symptom"]}},

    #  Game Dev Module 
    {"name": "read_gamedev_design_analyze", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"concept": {"type": "string"}, "genre": {"type": "string"}}, "required": ["concept", "genre"]}},
    {"name": "read_gamedev_scaffold_project", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"engine": {"type": "string"}, "genre": {"type": "string"}, "name": {"type": "string", "default": "MyGame"}}, "required": ["engine", "genre"]}},
    {"name": "read_gamedev_mechanics_guide", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}}, "required": ["genre"]}},

    {"name": "read_gamedev_optimization", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"engine": {"type": "string"}, "issue": {"type": "string"}}, "required": ["engine", "issue"]}},
    {"name": "read_gamedev_compare_engines", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "team_size": {"type": "string", "default": "solo"}, "budget": {"type": "string", "default": "indie"}}, "required": ["project_type"]}},
    {"name": "read_gamedev_level_design", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}, "level_type": {"type": "string"}}, "required": ["genre", "level_type"]}},

    #  Simulation: Applied Mechanics 

    {"name": "read_sim_mech_beam_analysis", "description": "MERGED - Beam analysis: calculate=[stress,shear,deflection,all]. Replaces 3 tools.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"calculate": {"type": "string", "default": "all", "enum": ["stress", "shear", "deflection", "all"]}, "moment": {"type": "number"}, "distance_neutral": {"type": "number"}, "I": {"type": "number"}, "shear_force": {"type": "number"}, "Q": {"type": "number"}, "width": {"type": "number"}, "load": {"type": "number"}, "length": {"type": "number"}, "E": {"type": "number"}}, "required": []}},
    {"name": "read_sim_mech_buckle", "description": "MERGED — Column buckling: Euler (E,I) or Johnson (sigma_y,A,r). Auto-selects based on params.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"E": {"type": "number"}, "I": {"type": "number", "description": "Moment of inertia (m^4) — for Euler"}, "K": {"type": "number", "default": 1.0}, "L": {"type": "number"}, "sigma_y": {"type": "number", "description": "Yield strength (Pa) — for Johnson"}, "A": {"type": "number", "description": "Area (m^2) — for Johnson"}, "r": {"type": "number", "description": "Radius of gyration (m) — for Johnson"}}, "required": ["E", "L"]}},
    {"name": "read_sim_mech_buckle_johnson", "description": "Johnson column buckling for intermediate columns.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"E": {"type": "number"}, "sigma_y": {"type": "number", "description": "Yield strength (Pa)"}, "A": {"type": "number", "description": "Cross-sectional area (m^2)"}, "K": {"type": "number", "default": 1.0}, "L": {"type": "number"}, "r": {"type": "number", "description": "Radius of gyration (m)"}}, "required": ["E", "sigma_y", "A", "L", "r"]}},
    {"name": "read_sim_mech_fatigue", "description": "MERGED — S-N fatigue: solve for 'stress' or 'cycles'. Replaces sn + cycles.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"Sf_prime": {"type": "number", "description": "Fatigue strength coefficient (Pa)"}, "b": {"type": "number", "default": -0.1}, "N": {"type": "integer", "default": 1000}, "stress_amplitude": {"type": "number"}, "solve_for": {"type": "string", "default": "stress", "enum": ["stress", "cycles"]}}, "required": ["Sf_prime"]}},

    {"name": "read_sim_mech_fatigue_goodman", "description": "Goodman mean stress correction. Checks (S_alt/S_e)+(S_mean/S_ut) <= 1.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"S_alt": {"type": "number"}, "S_mean": {"type": "number"}, "S_ut": {"type": "number", "description": "Ultimate tensile strength"}, "S_e": {"type": "number", "description": "Endurance limit"}}, "required": ["S_alt", "S_mean", "S_ut", "S_e"]}},
    {"name": "read_sim_mech_fatigue_miner", "description": "Miner's cumulative damage: D = Σ(n_i/N_i).", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"blocks": {"type": "array", "items": {"type": "object", "properties": {"cycles": {"type": "integer"}, "cycles_to_failure": {"type": "integer"}}}, "description": "Load blocks"}}, "required": ["blocks"]}},

    {"name": "read_sim_mech_joint", "description": "MERGED - Joint analysis: type=[fastener,bolt,bonded]. Replaces 3 tools.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"type": {"type": "string", "enum": ["fastener", "bolt", "bonded"]}, "force": {"type": "number"}, "area": {"type": "number"}, "num_fasteners": {"type": "integer", "default": 1}, "K": {"type": "number", "default": 0.2}, "D": {"type": "number"}, "F": {"type": "number"}, "width": {"type": "number"}, "overlap_length": {"type": "number"}}, "required": ["type"]}},
    {"name": "read_sim_mech_moi", "description": "MERGED — Moment of inertia: shape=[rect|circle]. Replaces moi_rect + moi_circle.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"shape": {"type": "string", "default": "rect", "enum": ["rect", "circle"]}, "width": {"type": "number", "description": "For rect"}, "height": {"type": "number", "description": "For rect"}, "diameter": {"type": "number", "description": "For circle"}}, "required": []}},


    #  Mutation Phase (Algorithmic Mutation Engine) 
    {"name": "read_mutate_scope", "description": "Parse execution triggers → define functional boundaries and target metrics.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"trigger": {"type": "string", "description": "Task description, error log, or command to analyze"}}, "required": ["trigger"]}},
    {"name": "read_mutate_audit", "description": "Scan tool inventories + DAGs for redundancy and overlapping execution flows.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"scope_id": {"type": "string"}, "domains": {"type": "array", "items": {"type": "string"}}}, "required": []}},
    {"name": "write_mutate_execute", "description": " MUTATE — Execute algorithmic mutation cycle (audit → refactor plan → persist). Use dry_run=true to preview.", "permission": "mutate", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"scope_id": {"type": "string"}, "dry_run": DR()}, "required": []}},


    #  Compact Phase (Context Compaction Engine) 
    {"name": "read_compact_token_velocity", "description": "Check current token velocity and compaction recommendation.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "read_compact_synthesize", "description": "Condense verbose content into a high-density summary (preserves code/math blocks).", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}, "max_chars": {"type": "integer", "default": 2000}}, "required": ["content"]}},

    {"name": "write_compact_execute", "description": " WRITE — Execute context compaction cycle. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"content": {"type": "string", "description": "Content to compact (leave empty to status-only)"}, "dry_run": DR()}, "required": []}},
    {"name": "read_compact_record_tick", "description": "Record a manual token velocity tick.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"context": {"type": "string", "default": "manual"}}, "required": []}},

    #  Plumber Module (Execution Pipelines) 
    {"name": "read_plumber_inspect_socket", "description": "Check socket latency and structural integrity (TCP or Unix).", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"host": {"type": "string", "default": "localhost"}, "port": {"type": "integer"}, "socket_path": {"type": "string", "description": "Unix socket path (alternative to TCP)"}}, "required": []}},
    {"name": "read_plumber_trace_handoff", "description": "Trace data handoff between components. Filter by source/target/protocol.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"source": {"type": "string"}, "target": {"type": "string"}, "protocol_filter": {"type": "string"}}, "required": []}},
    {"name": "write_plumber_checkpoint", "description": " WRITE — Create runtime checkpoint before destructive ops. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"artifact_type": {"type": "string", "default": "session"}, "file_paths": {"type": "array", "items": {"type": "string"}}, "metadata": {"type": "object"}, "dry_run": DR()}, "required": []}},
    {"name": "read_plumber_checkpoints", "description": "List recent checkpoints from history.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}, "required": []}},

    #  CAD Module (3D modeling / OpenSCAD) 
    {"name": "read_cad_validate_scad", "description": "Validate OpenSCAD file syntax and structure.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}},
    {"name": "read_cad_beam_stress", "description": "Rectangular beam stress analysis for 3D printed parts.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"force_N": {"type": "number"}, "length_mm": {"type": "number"}, "width_mm": {"type": "number"}, "height_mm": {"type": "number"}, "yield_MPa": {"type": "number", "default": 40}}, "required": ["force_N", "length_mm", "width_mm", "height_mm"]}},

    #  Electrical Module (Circuit Design) 
    {"name": "read_electrical_design_circuit", "description": "Design a circuit schematic with components and connections.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"components": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"}}}}, "connections": {"type": "array", "items": {"type": "object", "properties": {"from": {"type": "string"}, "to": {"type": "string"}}}}}, "required": ["components", "connections"]}},
    {"name": "read_electrical_analyze_circuit", "description": "Analyze a circuit for connectivity and validation.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"circuit_json": {"type": "string"}}, "required": ["circuit_json"]}},

    #  Focus Module (Scope & Session Management) 
    {"name": "read_focus_scope_check", "description": "Check user input for scope creep, topic switching, feature bloat.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"input_text": {"type": "string"}, "current_project": {"type": "string", "default": "CortexStratum"}}, "required": ["input_text"]}},
    {"name": "read_focus_nudge", "description": "Generate context-aware nudge message based on scope analysis.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"scope_result": {"type": "object"}, "user_input": {"type": "string"}}, "required": ["scope_result", "user_input"]}},
    {"name": "write_focus_store_global", "description": " WRITE — Store out-of-scope task in Global Projects Memory. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"project": {"type": "string"}, "task": {"type": "string"}, "context": {"type": "string"}, "source_session": {"type": "string"}, "dry_run": DR()}, "required": ["project", "task"]}},
    {"name": "read_focus_global", "description": "Retrieve global projects memory. Filter by project.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"project": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": []}},
    {"name": "read_focus_pipeline_status", "description": "Show current session pipeline phase and stats.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {}}},
    {"name": "write_focus_pipeline_advance", "description": " WRITE — Advance session pipeline phase. Phases: help→context→executing→wrapping→learning→end.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"next_phase": {"type": "string", "enum": ["help", "context", "executing", "wrapping", "learning", "end"]}, "summary": {"type": "string"}, "dry_run": DR()}, "required": ["next_phase"]}},
    {"name": "read_focus_decompose", "description": "Decompose complex prompt into atomic tasks grouped by category.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"prompt_text": {"type": "string"}}, "required": ["prompt_text"]}},
    {"name": "read_focus_prioritize", "description": "Score and sequence tasks from decomposer into execution plan.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"tasks": {"type": "array", "items": {"type": "object"}}}, "required": ["tasks"]}},
    {"name": "write_focus_learn", "description": " MUTATE — Post-session learning analysis. Use dry_run=true to preview.", "permission": "mutate", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}, "events": {"type": "array", "items": {"type": "object"}}, "dry_run": DR()}, "required": ["session_id"]}},

    #  Simulation: FEA (Finite Element Analysis) 
    {"name": "read_sim_fea_beam", "description": "1D beam element stiffness matrix (4x4). Returns K, LaTeX.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"E": {"type": "number", "description": "Young's modulus (Pa)"}, "I": {"type": "number", "description": "Moment of inertia (m^4)"}, "L": {"type": "number", "description": "Element length (m)"}}, "required": ["E", "I", "L"]}},
    {"name": "read_sim_fea_truss", "description": "1D truss element axial stiffness k=EA/L. Returns stiffness and stress.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"E": {"type": "number"}, "A": {"type": "number", "description": "Cross-section (m^2)"}, "L": {"type": "number"}, "force": {"type": "number", "description": "Axial force (N)"}}, "required": ["E", "A", "L", "force"]}},
    {"name": "read_sim_fea_modal", "description": "Cantilever beam 1st natural frequency: f1 = (1.875²/2πL²)·√(EI/ρA).", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"E": {"type": "number"}, "I": {"type": "number"}, "rho": {"type": "number", "description": "Density (kg/m³)"}, "A": {"type": "number"}, "L": {"type": "number"}}, "required": ["E", "I", "rho", "A", "L"]}},
    {"name": "read_sim_fea_heat", "description": "1D steady-state heat conduction: q = -k·A·(T2-T1)/L.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"k": {"type": "number", "description": "Thermal conductivity (W/mK)"}, "A": {"type": "number", "description": "Area (m²)"}, "T1": {"type": "number", "description": "Temperature 1 (°C)"}, "T2": {"type": "number", "description": "Temperature 2 (°C)"}, "L": {"type": "number", "description": "Length (m)"}}, "required": ["k", "A", "T1", "T2", "L"]}},

    #  Simulation: CFD (Computational Fluid Dynamics) 
    {"name": "read_sim_cfd_pipe", "description": "Pipe flow: Darcy-Weisbach ΔP, Reynolds number, friction factor.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"rho": {"type": "number", "description": "Density (kg/m³)"}, "v": {"type": "number", "description": "Velocity (m/s)"}, "D": {"type": "number", "description": "Pipe diameter (m)"}, "mu": {"type": "number", "description": "Dynamic viscosity (Pa·s)"}, "L": {"type": "number", "description": "Pipe length (m)"}}, "required": ["rho", "v", "D", "mu", "L"]}},
    {"name": "read_sim_cfd_boundary", "description": "Boundary layer thickness (laminar/turbulent) on flat plate.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"rho": {"type": "number"}, "v": {"type": "number"}, "x": {"type": "number", "description": "Position along plate (m)"}, "mu": {"type": "number"}, "regime": {"type": "string", "default": "auto", "enum": ["auto", "laminar", "turbulent"]}}, "required": ["rho", "v", "x", "mu"]}},
    {"name": "read_sim_cfd_drag", "description": "Drag force: Fd = 0.5·ρ·v²·Cd·A.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"rho": {"type": "number"}, "v": {"type": "number"}, "Cd": {"type": "number", "description": "Drag coefficient"}, "A": {"type": "number", "description": "Reference area (m²)"}}, "required": ["rho", "v", "Cd", "A"]}},
    {"name": "read_sim_cfd_bernoulli", "description": "Bernoulli: solve for any one unknown from P, v, h.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"P1": {"type": "number", "description": "Pressure 1 (Pa)"}, "v1": {"type": "number", "description": "Velocity 1 (m/s)"}, "h1": {"type": "number", "description": "Height 1 (m)"}, "P2": {"type": "number"}, "v2": {"type": "number"}, "h2": {"type": "number"}, "rho": {"type": "number", "description": "Fluid density (kg/m³)"}, "solve_for": {"type": "string", "enum": ["P1", "v1", "h1", "P2", "v2", "h2"]}}, "required": ["rho", "solve_for"]}},

    #  Simulation: Math Engine 
    {"name": "read_sim_matrix_solve", "description": "Solve Ax = b via Gaussian elimination. Returns solution + LaTeX derivation.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"A": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}}, "b": {"type": "array", "items": {"type": "number"}}}, "required": ["A", "b"]}},
    {"name": "read_sim_ode", "description": "Solve ODE system (RK4 or Euler). Returns trajectory + LaTeX system.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"derivatives": {"type": "array", "items": {"type": "string"}}, "y0": {"type": "array", "items": {"type": "number"}}, "t_start": {"type": "number", "default": 0}, "t_end": {"type": "number", "default": 10}, "steps": {"type": "integer", "default": 100}, "method": {"type": "string", "default": "rk4", "enum": ["rk4", "euler"]}}, "required": ["derivatives", "y0"]}},
    {"name": "read_sim_latex", "description": "Generate LaTeX from common expressions (quadratic, buckling, bending, integral, derivative).", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"expression": {"type": "string"}, "notation": {"type": "string", "default": "aligned", "enum": ["aligned", "derivation"]}}, "required": ["expression"]}},


    #  Pedagogy Engine (Cognitive Architecture) 
    {"name": "read_pedagogy_assess", "description": "Assess user understanding level from queries/topic. Returns depth recommendation.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}}, "topic": {"type": "string"}}, "required": []}},
    {"name": "read_pedagogy_adapt", "description": "Generate explanation prompt at appropriate depth for a topic.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"topic": {"type": "string"}, "complexity": {"type": "integer", "description": "1-5 (intuitive to expert)"}, "format": {"type": "string", "default": "text"}}, "required": []}},
    {"name": "write_pedagogy_profile", "description": " WRITE — Store user comprehension profile. Use dry_run=true to preview.", "permission": "write", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"depth": {"type": "integer", "description": "1-5"}, "topic": {"type": "string"}, "feedback_score": {"type": "number"}, "dry_run": DR()}, "required": []}},

    #  Consolidation Daemon (Offline Cross-Pollination) 

    {"name": "write_consolidation_run", "description": " MUTATE — Execute cross-pollination cycle (TF-IDF similarity linking). Use dry_run=true to preview.", "permission": "mutate", "annotations": A(True), "inputSchema": {"type": "object", "properties": {"dry_run": DR()}, "required": []}},
    {"name": "read_consolidation_links", "description": "Show discovered cross-pollination links between memory entries.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}, "min_similarity": {"type": "number", "default": 0}}, "required": []}},
]

# 
# HANDLE TOOL CALL
# 

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
    if name in ("write_memory_add", "write_memory_consolidate") and not args.get("dry_run"):
        ckpt = _get_audit().checkpoint(name, args)
    else:
        ckpt = None

    # Memory tools
    if name in ("read_memory_search", "read_memory_synthesize", "read_memory_vector_search",
                "read_memory_hybrid_search", "read_memory_reranked_search",
                "write_memory_add", "write_memory_consolidate", "read_memory_status"):
        mem = _get_memory_search()
        if name == "read_memory_search":
            mode = args.get("mode", "bm25")
            if mode == "vector":
                r = mem.vector_search(args.get("query",""), args.get("limit",10))
            elif mode == "hybrid":
                r = mem.hybrid_search(args.get("query",""), args.get("limit",10),
                                      args.get("bm25_weight",0.5), args.get("vector_weight",0.5), args.get("rrf_k",60))
            elif mode == "reranked":
                r = mem.reranked_search(args.get("query",""), args.get("limit",5), args.get("candidates",20))
            else:
                r = mem.search(args.get("query",""), args.get("limit",10), args.get("fuzzy_threshold",0.85))
        elif name == "read_memory_synthesize":
            r = mem.synthesize(args.get("query",""), args.get("max_sources",5), args.get("min_confidence",0.7))
        elif name == "read_memory_vector_search":  # deprecated
            r = mem.vector_search(args.get("query",""), args.get("limit",10))
        elif name == "read_memory_hybrid_search":  # deprecated
            r = mem.hybrid_search(args.get("query",""), args.get("limit",10),
                                  args.get("bm25_weight",0.5), args.get("vector_weight",0.5), args.get("rrf_k",60))
        elif name == "read_memory_reranked_search":  # deprecated
            r = mem.reranked_search(args.get("query",""), args.get("limit",5), args.get("candidates",20))
        elif name == "write_memory_add":
            r = {"memory_id": mem.add_memory(args.get("text",""), args.get("source","manual"), args.get("metadata",{})), "status": "stored"}
        elif name == "write_memory_consolidate":
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
    if name == "write_audit_undo":
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
                "read_commitment_checker_list", "write_commitment_verify"):
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
        else: r = {"error": "Unknown literature tool"}
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    # Sensory
    if name.startswith("read_sensory_") or name.startswith("write_sensory_"):
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

    # Plumber Module
    if name.startswith("read_plumber_") or name.startswith("write_plumber_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("plumber_module","plumber-module.py").handle_tool_call(name, args), indent=2)}]}

    # Simulation: Applied Mechanics
    if name.startswith("read_sim_mech_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("mechanics_module","sim-mechanics-module.py").handle_tool_call(name, args), indent=2)}]}

    # Mutation Phase
    if name.startswith("read_mutate_") or name == "write_mutate_execute":
        return {"content": [{"type": "text", "text": json.dumps(_get_module("mutation_module","mutation-module.py").handle_tool_call(name, args), indent=2)}]}

    # Compact Phase
    if name.startswith("read_compact_") or name.startswith("write_compact_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("compact_module","compact-module.py").handle_tool_call(name, args), indent=2)}]}

    # CAD Module
    if name.startswith("read_cad_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("cad_wrapper","cad-module/cad_wrapper.py").handle_tool_call(name, args), indent=2)}]}

    # Electrical Module
    if name.startswith("read_electrical_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("electrical_wrapper","electrical-module/electrical_wrapper.py").handle_tool_call(name, args), indent=2)}]}

    # Focus Module (Scope & Session Management)
    if name.startswith("read_focus_") or name.startswith("write_focus_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("focus_module","focus-module.py").handle_tool_call(name, args), indent=2)}]}

    # Simulation: FEA
    if name.startswith("read_sim_fea_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("fea_module","sim-fea-module.py").handle_tool_call(name, args), indent=2)}]}

    # Simulation: CFD
    if name.startswith("read_sim_cfd_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("cfd_module","sim-cfd-module.py").handle_tool_call(name, args), indent=2)}]}

    # Simulation: Math Engine
    if name.startswith("read_sim_matrix_") or name.startswith("read_sim_ode") or name.startswith("read_sim_latex"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("math_module","sim-math-module.py").handle_tool_call(name, args), indent=2)}]}

    # Pedagogy Engine
    if name.startswith("read_pedagogy_") or name.startswith("write_pedagogy_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("pedagogy_module","pedagogy-module.py").handle_tool_call(name, args), indent=2)}]}

    # Consolidation Daemon
    if name.startswith("read_consolidation_") or name.startswith("write_consolidation_"):
        return {"content": [{"type": "text", "text": json.dumps(_get_module("consolidation_module","consolidation-daemon.py").handle_tool_call(name, args), indent=2)}]}

    # Hooks
    if name.startswith("read_hooks_") or name.startswith("write_hooks_"):
        hooks = _get_module("hooks_module", "hooks.py")
        if not hasattr(hooks, '_wired'):
            hm = hooks._get_hooks()
            hm._memory_search = _get_memory_search().search
            hm._trace_handle = _get_trace().handle_tool_call
            hooks._wired = True
        return {"content": [{"type": "text", "text": json.dumps(hooks.hooks_handle_tool_call(name, args), indent=2)}]}

    # Merged: read_phase_status dispatch
    if name == "read_phase_status":
        domain = args.get("domain", "compact")
        if domain == "compact":
            mod = _get_module("compact_module","compact-module.py")
            r = mod.session_status()
        elif domain == "mutation":
            mod = _get_module("mutation_module","mutation-module.py")
            r = mod.get_status()
        elif domain == "audit":
            r = _get_audit().status()
        elif domain == "consolidation":
            mod = _get_module("consolidation_module","consolidation-daemon.py")
            r = mod.get_status()
        else:
            r = {"error": f"Unknown domain: {domain}"}
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

# 
# MCP Protocol
# 

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
            send_message({"jsonrpc":"2.0","id":mid,"result":{"protocolVersion":"2024-11-05","serverInfo":{"name":"CortexStratum","version":VERSION},"capabilities":{"tools":{"listChanged":True}}}}); return True
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
    _log("INFO", f"CortexStratum v{VERSION} starting ({len(TOOLS)} tools)...")
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
        print(f"\nCortexStratum MCP Server v{VERSION}\n{len(TOOLS)} tools\n")
        _sys.exit(0)
    if "--version" in args: print(f"v{VERSION}"); _sys.exit(0)
    if "--list-tools" in args: print(json.dumps(TOOLS, indent=2)); _sys.exit(0)
    if "--permissive" in args: import sys as m; m.modules[__name__].PERMISSIVE_MODE = True
    if "--debug" in args: import sys as m; m.modules[__name__].DEBUG_MODE = True
    main()

