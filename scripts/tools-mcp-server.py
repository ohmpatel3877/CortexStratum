#!/usr/bin/env python3
"""
MCP Server: ai-memory-core Toolchain
Exposes xTrace, DTrace, Skill Router, Goal Registry,
and Commitment Checker as MCP tools for use by OpenCode and benchmark runners.

Protocol: JSON-RPC over stdio (Model Context Protocol)
"""

import json, sys, os, subprocess, time, re, threading, queue, select, hashlib
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

TOOL_EXECUTOR_TIMEOUT = 60
POLL_INTERVAL = 0.5  # seconds between poll cycles when waiting for a tool

# Permission categories
PERMISSION_READ = "read"
PERMISSION_WRITE = "write"
PERMISSION_MUTATE = "mutate"

# Auto-mode: only read_* tools allowed without human review
def can_call_tool(tool_name: str, context: dict | None = None) -> tuple[bool, str]:
    """Check if a tool call is permitted based on its permission level.

    Returns (allowed, reason). In 'auto' mode, only read_ tools pass.
    In 'interactive' mode, all tools pass but write_/mutate_ return a warning.
    """
    permission = None
    for t in TOOLS:
        if t["name"] == tool_name:
            permission = t.get("permission", PERMISSION_READ)
            break

    if permission is None:
        return (False, f"Unknown tool: {tool_name}")

    mode = (context or {}).get("mode", "interactive")

    if mode == "auto" and permission != PERMISSION_READ:
        return (False, f"Tool '{tool_name}' requires {permission} permission — blocked in auto mode. Only read_ tools allowed without human review.")

    if permission in (PERMISSION_WRITE, PERMISSION_MUTATE):
        return (True, f"⚠️  Tool '{tool_name}' has {permission} permission — confirm this action is intended.")

    return (True, "ok")


_verifier = None
_memory_search = None
_MODULE_CACHE = {}


def _get_module(name, filename):
    """Factory: lazy-load a module from scripts/ by name, caching it."""
    if name not in _MODULE_CACHE:
        import importlib.util as _util
        spec = _util.spec_from_file_location(name, str(SCRIPTS_DIR / filename))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODULE_CACHE[name] = mod
    return _MODULE_CACHE[name]


def _get_verifier():
    global _verifier
    if _verifier is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("verifier_middleware", str(SCRIPTS_DIR / "verifier_middleware.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _verifier = mod.VerifierMiddleware(mode="advisory")
    return _verifier


def _get_memory_search():
    global _memory_search
    if _memory_search is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("memory_search", str(SCRIPTS_DIR / "memory_search.py"))
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _memory_search = mod.NEMemorySearch()
    return _memory_search


def _get_trace():
    return _get_module("trace", "trace.py")


def read_exact(n: int) -> bytes:
    """Read exactly n bytes from stdin, looping until complete."""
    buffer = b""
    while len(buffer) < n:
        chunk = sys.stdin.buffer.read(n - len(buffer))
        if not chunk:
            raise EOFError(f"Expected {n} bytes, got {len(buffer)} before EOF")
        buffer += chunk
    return buffer

BASE = Path(__file__).resolve().parent  # scripts/
PROJECT_ROOT = BASE.parent              # ai-memory-core/
SCRIPTS_DIR = BASE                      # scripts/
DATA_DIR = PROJECT_ROOT / "data"
SKILLS_DIR = PROJECT_ROOT / "skills"


def execute_tool_async(name: str, args: dict, result_queue: queue.Queue):
    """Execute a tool call in a separate thread and put the result on the queue."""
    try:
        result = handle_tool_call(name, args)
        result_queue.put(("result", result))
    except Exception as e:
        result_queue.put(("error", str(e)))

# Tool definitions
TOOLS = [
    {
        "name": "write_xtrace_log_error",
        "permission": "write",
        "description": "Log an error occurrence with signature for xTrace error tracking",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The failed command"},
                "error_output": {"type": "string", "description": "The error message/output"},
                "exit_code": {"type": "integer", "description": "The exit code"}
            },
            "required": ["command", "error_output"]
        }
    },
    {
        "name": "read_xtrace_search",
        "permission": "read",
        "description": "Search xTrace error registry for a known error signature",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Error keyword to search for"}
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "read_xtrace_status",
        "permission": "read",
        "description": "Get xTrace error tracking summary statistics",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "write_dtrace_add",
        "permission": "write",
        "description": "Log an architectural decision to DTrace",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "context": {"type": "string"},
                "decision": {"type": "string"},
                "alternatives": {"type": "string"},
                "rationale": {"type": "string"},
                "category": {"type": "string", "enum": ["architecture", "process", "technology", "security"]}
            },
            "required": ["title", "decision", "rationale"]
        }
    },
    {
        "name": "read_dtrace_search",
        "permission": "read",
        "description": "Search DTrace decision registry",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"}
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "read_skill_router_match",
        "permission": "read",
        "description": "Match a task description to relevant skills using the Skill Router",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task description to find skills for"}
            },
            "required": ["task"]
        }
    },
    {
        "name": "write_goal_registry_init",
        "permission": "write",
        "description": "Initialize a new goal in the Goal Registry",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "The original goal description"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "write_goal_registry_add_subgoal",
        "permission": "write",
        "description": "Add a sub-goal to the current goal stack",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Sub-goal description"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "read_goal_registry_status",
        "permission": "read",
        "description": "Get current goal registry status"
    },
    {
        "name": "read_goal_registry_check_alignment",
        "permission": "read",
        "description": "Check if current action aligns with the original goal",
        "inputSchema": {
            "type": "object",
            "properties": {
                "current_action": {"type": "string", "description": "Current action being taken"}
            },
            "required": ["current_action"]
        }
    },
    {
        "name": "read_commitment_checker_list",
        "permission": "read",
        "description": "List pending commitments for this session",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "mutate_commitment_checker_verify",
        "permission": "mutate",
        "description": "Mark a commitment as verified for this session",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Commitment ID to verify (e.g. b1, b2)"}
            },
            "required": ["id"]
        }
    },

    # --- Art Module tools ---
    {
        "name": "read_art_generate_svg",
        "permission": "read",
        "description": "Generate SVG diagrams, flowcharts, and illustrations from a text description",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Description of the SVG to generate (e.g. 'flowchart with 4 steps', 'bar chart of sales data')"},
                "width": {"type": "integer", "description": "SVG width in pixels (optional)"},
                "height": {"type": "integer", "description": "SVG height in pixels (optional)"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "read_art_generate_theme",
        "permission": "read",
        "description": "Generate a color theme with roles and WCAG contrast validation from a description",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Theme description (e.g. 'dark cyberpunk', 'forest green study palette', 'ocean blue')"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "read_art_extract_palette",
        "permission": "read",
        "description": "Extract complementary, analogous, and triadic palettes from a base hex color",
        "inputSchema": {
            "type": "object",
            "properties": {
                "color": {"type": "string", "description": "Base hex color (e.g. '#3b82f6' or '3b82f6')"}
            },
            "required": ["color"]
        }
    },
    {
        "name": "read_art_design_concept",
        "permission": "read",
        "description": "Generate a design concept with layout, typography, and spacing guidelines from requirements",
        "inputSchema": {
            "type": "object",
            "properties": {
                "requirements": {"type": "string", "description": "Design requirements description"}
            },
            "required": ["requirements"]
        }
    },

    # --- Literature Module tools ---
    {
        "name": "read_lit_analyze_text",
        "permission": "read",
        "description": "Analyze text for reading level (Flesch-Kincaid), key concepts, argument structure, and sentiment",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text content to analyze"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "read_lit_extract_concepts",
        "permission": "read",
        "description": "Extract key concepts, their definitions, context, and relationships from text",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text content to extract concepts from"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "read_lit_generate_study_guide",
        "permission": "read",
        "description": "Generate a study guide from content with key terms, discussion questions, and section summaries",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Textbook chapter or article content"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "read_lit_analyze_philosophy",
        "permission": "read",
        "description": "Analyze philosophical arguments: premises, conclusions, reasoning type, detected philosophers, and schools",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Philosophical text to analyze"}
            },
            "required": ["text"]
        }
    },

    # --- Sensory Module tools ---
    {
        "name": "read_sensory_browse",
        "permission": "read",
        "description": "Navigate to a URL using Playwright (headless Firefox) and extract content. Modes: text, html, markdown, links, metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to browse"},
                "extract_mode": {"type": "string", "enum": ["text", "html", "markdown", "links", "metadata"], "default": "text"},
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_sensory_screenshot",
        "permission": "read",
        "description": "Take a screenshot of a web page via Playwright",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to screenshot"},
                "output_path": {"type": "string", "description": "Optional output file path"},
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "mutate_sensory_interact",
        "permission": "mutate",
        "description": "Navigate to URL and perform actions (click, type, press, wait) — can modify external state",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["click", "type", "press", "wait"]},
                            "selector": {"type": "string"},
                            "value": {"type": "string"},
                        },
                    },
                },
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url", "actions"],
        },
    },
    {
        "name": "read_sensory_extract_pdf",
        "permission": "read",
        "description": "Extract text from a PDF file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to PDF file"},
                "max_pages": {"type": "integer", "default": 50},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "read_sensory_extract_html",
        "permission": "read",
        "description": "Extract text from raw HTML content. Modes: clean (trafilatura), soup (BeautifulSoup), tables",
        "inputSchema": {
            "type": "object",
            "properties": {
                "html_content": {"type": "string"},
                "mode": {"type": "string", "enum": ["clean", "soup", "tables"], "default": "clean"},
            },
            "required": ["html_content"],
        },
    },
    {
        "name": "read_sensory_extract_image",
        "permission": "read",
        "description": "Extract text from an image via OCR (if pytesseract installed) or return image metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to image file"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "read_sensory_scrape",
        "permission": "read",
        "description": "Fetch a URL via HTTP (no JS) and extract content. Modes: text, html, links, tables, json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "mode": {"type": "string", "enum": ["text", "html", "links", "tables", "json"], "default": "text"},
                "headers": {"type": "object"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_sensory_extract_article",
        "permission": "read",
        "description": "Extract clean article content from a URL using trafilatura",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_sensory_api_request",
        "permission": "read",
        "description": "Make an HTTP API request (GET/POST/PUT/DELETE/PATCH) with structured response",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"], "default": "GET"},
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
        "permission": "read",
        "description": "Parse an RSS/Atom feed and return structured items",
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
        "permission": "read",
        "description": "Read a local text file and return its content",
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
        "permission": "read",
        "description": "Web search via DuckDuckGo (no API key needed). Returns title, URL, snippet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
    },

    # --- Audio Module tools ---
    {"name": "read_audio_analyze_file", "permission": "read", "description": "Analyze WAV audio file: duration, channels, sample rate, amplitude stats", "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "data_base64": {"type": "string"}, "format": {"type": "string", "default": "wav"}}, "required": []}},
    {"name": "read_audio_waveform", "permission": "read", "description": "Generate ASCII waveform visualization from audio file", "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "width": {"type": "integer", "default": 80}, "height": {"type": "integer", "default": 20}}, "required": ["file_path"]}},
    {"name": "read_audio_frequency_analysis", "permission": "read", "description": "DFT-based frequency analysis: band energy, dominant frequency, spectral centroid", "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "num_bands": {"type": "integer", "default": 10}}, "required": ["file_path"]}},
    {"name": "read_audio_music_theory", "permission": "read", "description": "Music theory analysis: chord detection, scale matching, intervals from notes or frequencies", "inputSchema": {"type": "object", "properties": {"notes": {"type": "array", "items": {"type": "string"}}, "frequencies": {"type": "array", "items": {"type": "number"}}}, "required": []}},
    {"name": "read_audio_speech_analysis", "permission": "read", "description": "Speech transcript analysis: WPM, filler words, pace rating, readability", "inputSchema": {"type": "object", "properties": {"transcript": {"type": "string"}, "duration_seconds": {"type": "number"}}, "required": ["transcript", "duration_seconds"]}},
    {"name": "read_audio_convert_guide", "permission": "read", "description": "Audio format conversion guide with ffmpeg commands and quality comparison", "inputSchema": {"type": "object", "properties": {"source_format": {"type": "string"}, "target_format": {"type": "string"}, "quality": {"type": "string", "default": "high"}}, "required": ["source_format", "target_format"]}},
    {"name": "read_audio_generate_tone", "permission": "read", "description": "Generate sine/square/saw/triangle wave tone as base64 WAV", "inputSchema": {"type": "object", "properties": {"frequency": {"type": "number", "default": 440}, "duration_seconds": {"type": "number", "default": 1}, "sample_rate": {"type": "integer", "default": 44100}, "amplitude": {"type": "number", "default": 0.5}, "waveform": {"type": "string", "default": "sine"}}, "required": []}},

    # --- Coder Module tools ---
    {"name": "read_coder_analyze_code", "permission": "read", "description": "Analyze code for quality, complexity, smells, and security issues across 12 languages", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}}, "required": ["code", "language"]}},
    {"name": "read_coder_generate_framework", "permission": "read", "description": "Generate complete project scaffold (web-api, cli-tool, library, desktop, microservice, data-pipeline, fullstack) for 12 languages", "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "language": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}}, "name": {"type": "string", "default": "my-project"}}, "required": ["project_type", "language"]}},
    {"name": "read_coder_debug", "permission": "read", "description": "Analyze error messages and stack traces, suggest fixes (50+ error patterns across languages)", "inputSchema": {"type": "object", "properties": {"error": {"type": "string"}, "code_context": {"type": "string", "default": ""}, "language": {"type": "string"}}, "required": ["error", "language"]}},
    {"name": "read_coder_review", "permission": "read", "description": "Code review with severity ratings (security, performance, readability, architecture, testing)", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}, "focus": {"type": "string", "default": "all"}}, "required": ["code", "language"]}},
    {"name": "read_coder_explain", "permission": "read", "description": "Educational code explanation at beginner/intermediate/advanced level", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}, "level": {"type": "string", "default": "intermediate"}}, "required": ["code", "language"]}},
    {"name": "read_coder_convert", "permission": "read", "description": "Convert code between languages (Python↔JS, Python→Go, Python→Rust, JS↔TS)", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "from": {"type": "string"}, "to": {"type": "string"}}, "required": ["code", "from", "to"]}},
    {"name": "read_coder_architecture", "permission": "read", "description": "Architecture pattern recommendation (MVC, Hexagonal, CQRS, Event-Driven, Microservices, etc.)", "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "scale": {"type": "string", "default": "medium"}, "requirements": {"type": "array", "items": {"type": "string"}}}, "required": ["project_type"]}},

    # --- DevOps Module tools ---
    {"name": "read_devops_container_debug", "permission": "read", "description": "Diagnose container issues (Podman/Docker) from error logs", "inputSchema": {"type": "object", "properties": {"error_log": {"type": "string"}, "runtime": {"type": "string", "default": "podman"}, "context": {"type": "string", "default": "standalone"}}, "required": ["error_log"]}},
    {"name": "read_devops_permissions_analyze", "permission": "read", "description": "Analyze permission/usernamespace issues in container environments", "inputSchema": {"type": "object", "properties": {"mount_path": {"type": "string"}, "container_user": {"type": "string"}, "host_user": {"type": "string"}, "error_symptom": {"type": "string"}}, "required": []}},
    {"name": "read_devops_compose_generator", "permission": "read", "description": "Generate Docker/Podman Compose files from service definitions", "inputSchema": {"type": "object", "properties": {"services": {"type": "array"}, "networks": {"type": "array"}, "runtime": {"type": "string", "default": "docker"}}, "required": ["services"]}},
    {"name": "read_devops_samba_config", "permission": "read", "description": "Generate Samba/SMB share configurations with OS-specific troubleshooting", "inputSchema": {"type": "object", "properties": {"share_name": {"type": "string"}, "path": {"type": "string"}, "users": {"type": "array"}, "options": {"type": "object"}}, "required": ["share_name", "path"]}},
    {"name": "read_devops_mergerfs_setup", "permission": "read", "description": "Configure mergerfs for drive pooling with policy explanations and optimization tips", "inputSchema": {"type": "object", "properties": {"source_paths": {"type": "array"}, "mount_point": {"type": "string"}, "policy": {"type": "string", "default": "epmfs"}, "options": {"type": "object"}}, "required": ["source_paths", "mount_point"]}},
    {"name": "read_devops_dockerfile_analyze", "permission": "read", "description": "Analyze and optimize Dockerfiles for security, caching, and size", "inputSchema": {"type": "object", "properties": {"dockerfile": {"type": "string"}}, "required": ["dockerfile"]}},
    {"name": "read_devops_network_troubleshoot", "permission": "read", "description": "Diagnose container networking issues (DNS, ports, bridges, host networking)", "inputSchema": {"type": "object", "properties": {"symptom": {"type": "string"}}, "required": ["symptom"]}},

    # --- Game Dev Module tools ---
    {"name": "read_gamedev_design_analyze", "permission": "read", "description": "Analyze game concept: fun factor, engagement loops, monetization fit, market position", "inputSchema": {"type": "object", "properties": {"concept": {"type": "string"}, "genre": {"type": "string"}, "platform": {"type": "string", "default": "pc"}}, "required": ["concept", "genre"]}},
    {"name": "read_gamedev_scaffold_project", "permission": "read", "description": "Generate Unity/Unreal/Roblox project scaffold with real working boilerplate files", "inputSchema": {"type": "object", "properties": {"engine": {"type": "string"}, "genre": {"type": "string"}, "name": {"type": "string", "default": "MyGame"}, "features": {"type": "array"}}, "required": ["engine", "genre"]}},
    {"name": "read_gamedev_mechanics_guide", "permission": "read", "description": "Game mechanics design guide: core loops, progression systems, reward schedules by genre", "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}, "complexity": {"type": "string", "default": "core"}}, "required": ["genre"]}},
    {"name": "read_gamedev_monetization", "permission": "read", "description": "Monetization strategy recommendations with revenue estimates and ethical guidance", "inputSchema": {"type": "object", "properties": {"platform": {"type": "string"}, "genre": {"type": "string"}, "audience": {"type": "string", "default": "casual"}}, "required": ["platform", "genre"]}},
    {"name": "read_gamedev_optimization", "permission": "read", "description": "Engine-specific optimization advice (FPS, draw calls, memory, load times, network)", "inputSchema": {"type": "object", "properties": {"engine": {"type": "string"}, "issue": {"type": "string"}}, "required": ["engine", "issue"]}},
    {"name": "read_gamedev_compare_engines", "permission": "read", "description": "Compare game engines (Unity/Unreal/Godot/Roblox) for specific project types", "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "team_size": {"type": "string", "default": "solo"}, "budget": {"type": "string", "default": "indie"}}, "required": ["project_type"]}},
    {"name": "read_gamedev_level_design", "permission": "read", "description": "Level design principles, flow diagrams, pacing guides, and playtesting checklists", "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}, "level_type": {"type": "string"}}, "required": ["genre", "level_type"]}},

    # --- NE-Memory Search tools (zero-LLM BM25) ---
    {
        "name": "read_memory_search",
        "permission": "read",
        "description": "Local BM25 memory search with synonym expansion and fuzzy matching — zero LLM cost",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 10, "description": "Max results"},
                "fuzzy_threshold": {"type": "number", "default": 0.85, "description": "Fuzzy match cutoff (0-1)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_memory_synthesize",
        "permission": "read",
        "description": "Search and synthesize memory results into a narrative with inline citations",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Synthesis query"},
                "max_sources": {"type": "integer", "default": 5},
                "min_confidence": {"type": "number", "default": 0.7}
            },
            "required": ["query"]
        }
    },
    {
        "name": "write_memory_add",
        "permission": "write",
        "description": "Add a memory entry for future BM25 search and synthesis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Memory content to store"},
                "source": {"type": "string", "default": "manual", "description": "Source label"},
                "metadata": {"type": "object", "default": {}, "description": "Arbitrary metadata JSON"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "mutate_memory_consolidate",
        "permission": "mutate",
        "description": "Merge duplicate/similar memory entries by Jaccard similarity threshold",
        "inputSchema": {
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "default": 0.85, "description": "Similarity threshold (0-1)"}
            }
        }
    },
    {
        "name": "read_memory_status",
        "permission": "read",
        "description": "Get NE-Memory engine status: entry count, storage size, unique terms, last timestamp",
        "inputSchema": {"type": "object", "properties": {}}
    },

    # --- Verifier Middleware tools ---
    {
        "name": "read_verifier_status",
        "permission": "read",
        "description": "Get verifier middleware status: checks run, violations found, renudges sent, uptime",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "write_verifier_renudge",
        "permission": "write",
        "description": "Send a correction signal (renudge) to steer the agent back on track",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Agent or task ID to target"},
                "correction": {"type": "object", "description": "Correction parameters"},
                "strategy": {"type": "string", "enum": ["incremental", "rollback", "override", "halt"], "default": "incremental"}
            },
            "required": ["target", "correction"]
        }
    },
    {
        "name": "write_verifier_clear_renudge",
        "permission": "write",
        "description": "Clear an active renudge signal for a target tool or agent",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target tool name or agent ID to clear"}
            },
            "required": ["target"]
        }
    },
]

def handle_tool_call(name: str, args: dict) -> dict:
    """Execute a tool and return result."""

    # --- Permission check (before verifier — enforce access control) ---
    allowed, reason = can_call_tool(name, {})
    if not allowed:
        return {"content": [{"type": "text", "text": json.dumps({
            "error": "permission_denied",
            "tool": name,
            "reason": reason,
            "message": "Tool call blocked by permission middleware. Use interactive mode or request human approval."
        }, indent=2)}]}

    # --- Verifier pre-check (every tool call) ---
    verifier = _get_verifier()
    pre = verifier.pre_verify(name, args)
    if not pre["passed"]:
        return {"content": [{"type": "text", "text": json.dumps({
            "error": "verifier_rejected",
            "violations": pre["violations"],
            "message": "Tool call blocked by verifier middleware"
        }, indent=2)}]}

    # --- NE-Memory tools ---
    if name == "read_memory_search":
        mem = _get_memory_search()
        result = mem.search(args.get("query", ""), args.get("limit", 10), args.get("fuzzy_threshold", 0.85))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "read_memory_synthesize":
        mem = _get_memory_search()
        result = mem.synthesize(args.get("query", ""), args.get("max_sources", 5), args.get("min_confidence", 0.7))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "write_memory_add":
        mem = _get_memory_search()
        mem_id = mem.add_memory(args.get("text", ""), args.get("source", "manual"), args.get("metadata", {}))
        return {"content": [{"type": "text", "text": json.dumps({"memory_id": mem_id, "status": "stored"})}]}

    if name == "mutate_memory_consolidate":
        mem = _get_memory_search()
        result = mem.consolidate(args.get("threshold", 0.85))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "read_memory_status":
        mem = _get_memory_search()
        result = mem.status()
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "read_verifier_status":
        result = verifier.get_status()
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "write_verifier_renudge":
        result = verifier.renudge(args.get("target", ""), args.get("correction", {}), args.get("strategy", "incremental"))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "write_verifier_clear_renudge":
        result = verifier.clear_renudge(args.get("target", ""))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Special tools implemented inline
    if name == "read_skill_router_match":
        router = SKILLS_DIR / "skill-router.json"
        if router.exists():
            config = json.loads(router.read_text(encoding="utf-8"))
            matched = []
            task_lower = args.get("task", "").lower()
            for rule in config.get("rules", []):
                for t in rule.get("triggers", []):
                    if t.lower() in task_lower:
                        matched.extend(rule.get("skills", []))
                        break
            matched = list(dict.fromkeys(matched))  # deduplicate
            return {"content": [{"type": "text", "text": json.dumps({"matched_skills": matched, "count": len(matched)}, indent=2)}]}
        return {"content": [{"type": "text", "text": "Skill router not found"}]}

    # Forward to unified trace system (xTrace, DTrace, Goal Registry, Commitment Checker)
    if name in ("write_xtrace_log_error", "read_xtrace_search", "read_xtrace_status",
                 "write_dtrace_add", "read_dtrace_search",
                 "write_goal_registry_init", "write_goal_registry_add_subgoal",
                 "read_goal_registry_status", "read_goal_registry_check_alignment",
                 "read_commitment_checker_list", "mutate_commitment_checker_verify"):
        trace = _get_trace()
        return {"content": [{"type": "text", "text": json.dumps(trace.handle_tool_call(name, args), indent=2)}]}

    # Art Module tools (inline)
    if name == "read_art_generate_svg":
        art = _get_module("art_module", "art-module.py")
        desc = args.get("description", "")
        w = args.get("width", 400)
        h = args.get("height", 300)
        svg = art.generate_svg(desc, width=w, height=h)
        return {"content": [{"type": "text", "text": svg}]}

    if name == "read_art_generate_theme":
        art = _get_module("art_module", "art-module.py")
        desc = args.get("description", "dark cyberpunk")
        theme = art.generate_theme(desc)
        return {"content": [{"type": "text", "text": json.dumps(theme, indent=2)}]}

    if name == "read_art_extract_palette":
        art = _get_module("art_module", "art-module.py")
        color = args.get("color", "#3b82f6")
        palette = art.extract_palette(color)
        return {"content": [{"type": "text", "text": json.dumps(palette, indent=2)}]}

    if name == "read_art_design_concept":
        art = _get_module("art_module", "art-module.py")
        reqs = args.get("requirements", "A modern dashboard")
        concept = art.design_concept(reqs)
        return {"content": [{"type": "text", "text": json.dumps(concept, indent=2)}]}

    # Literature Module tools (inline)
    if name == "read_lit_analyze_text":
        lit = _get_module("literature_module", "literature-module.py")
        text = args.get("text", "")
        result = lit.analyze_text(text)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "read_lit_extract_concepts":
        lit = _get_module("literature_module", "literature-module.py")
        text = args.get("text", "")
        result = lit.extract_concepts(text)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "read_lit_generate_study_guide":
        lit = _get_module("literature_module", "literature-module.py")
        content = args.get("content", "")
        result = lit.generate_study_guide(content)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "read_lit_analyze_philosophy":
        lit = _get_module("literature_module", "literature-module.py")
        text = args.get("text", "")
        result = lit.analyze_philosophy(text)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Sensory Module tools (dispatched via module's handle_tool_call)
    if name.startswith("read_sensory_") or name.startswith("mutate_sensory_"):
        sensory = _get_module("sensory_module", "sensory-module.py")
        result = sensory.handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Audio Module tools (dispatched via module's handle_tool_call)
    if name.startswith("read_audio_"):
        audio = _get_module("audio_module", "audio-module.py")
        result = audio.handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Coder Module tools (dispatched via coder_handle_tool_call)
    if name.startswith("read_coder_"):
        coder = _get_module("coder_module", "coder-module.py")
        result = coder.coder_handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # DevOps Module tools (dispatched via devops_handle_tool_call)
    if name.startswith("read_devops_"):
        devops = _get_module("devops_module", "devops-module.py")
        result = devops.devops_handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Game Dev Module tools (dispatched via gamedev_handle_tool_call)
    if name.startswith("read_gamedev_"):
        gamedev = _get_module("gamedev_module", "game-dev-module.py")
        result = gamedev.gamedev_handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    result = {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}
    _get_verifier().post_verify(name, args, result, 0)
    return result


# ============================================================
# MCP Protocol over stdio
# ============================================================

def send_message(msg: dict):
    """Send a JSON-RPC message over stdout with Content-Length header."""
    payload = json.dumps(msg, ensure_ascii=False)
    raw = payload.encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()

def read_message() -> dict | None:
    """Read a JSON-RPC message from stdin using MCP stdio transport."""
    content_length = 0
    deadline = time.monotonic() + 30.0
    while True:
        if time.monotonic() > deadline:
            print("[mcp-server] Timeout waiting for header", file=sys.stderr, flush=True)
            return None
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line == b"\r\n":
            break
        decoded = line.decode("utf-8", errors="replace").strip()
        if ":" in decoded:
            key, val = decoded.split(":", 1)
            if key.strip().lower() == "content-length":
                content_length = int(val.strip())

    if content_length == 0:
        return None

    body = read_exact(content_length)
    return json.loads(body.decode("utf-8"))


def _handle_ping(msg_id):
    """Respond to ping immediately — never blocks."""
    send_message({"jsonrpc": "2.0", "id": msg_id, "result": {}})


def _handle_health(msg_id):
    """Health check — always responds instantly."""
    send_message({
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {"status": "ok", "uptime": time.monotonic()}
    })


def _process_message(msg: dict) -> bool:
    """Process a single JSON-RPC message. Returns True to keep running, False to exit."""
    try:
        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})

        if method == "ping":
            _handle_ping(msg_id)
            return True

        if method in ("health", "status"):
            _handle_health(msg_id)
            return True

        if method == "initialize":
            send_message({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "ai-memory-core-tools", "version": "1.0.0"},
                    "capabilities": {"tools": {"listChanged": True}}
                }
            })
            return True

        if method == "notifications/initialized":
            print("[mcp-server] Ready — accepting requests", file=sys.stderr, flush=True)
            return True

        if method == "tools/list":
            send_message({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
            return True

        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            tq = queue.Queue()
            t = threading.Thread(target=execute_tool_async, args=(tool_name, tool_args, tq), daemon=True)
            t.start()
            deadline = time.monotonic() + TOOL_EXECUTOR_TIMEOUT + 5
            while time.monotonic() < deadline:
                try:
                    kind, data = tq.get(timeout=POLL_INTERVAL)
                    if kind == "result":
                        send_message({"jsonrpc": "2.0", "id": msg_id, "result": data})
                    else:
                        send_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": data}})
                    return True
                except queue.Empty:
                    pass
                _drain_pending()
            send_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": "Tool execution timed out"}})
            return True

        if msg_id is not None:
            send_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})
        return True

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[mcp-server] Error processing message: {e}", file=sys.stderr, flush=True)
        if msg_id is not None:
            send_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32700, "message": f"Parse error: {e}"}})
        return True


_pending_queue: queue.Queue = queue.Queue()
_reader_shutdown = threading.Event()


def _reader_loop():
    """Background thread: reads MCP messages from stdin and enqueues them."""
    while not _reader_shutdown.is_set():
        try:
            msg = read_message()
        except (EOFError, ConnectionError) as e:
            print(f"[mcp-server] Reader EOF: {e}", file=sys.stderr, flush=True)
            break
        if msg is None:
            break
        _pending_queue.put(msg)
    _reader_shutdown.set()


def _drain_pending():
    """Process any messages accumulated in the pending queue (e.g. ping during tool exec)."""
    while not _pending_queue.empty():
        try:
            pending = _pending_queue.get_nowait()
            _process_message(pending)
        except queue.Empty:
            break


def main():
    """Main MCP server loop — pulls messages from the reader thread's queue."""
    print("[mcp-server] ai-memory-core-tools starting...", file=sys.stderr, flush=True)

    reader = threading.Thread(target=_reader_loop, daemon=True)
    reader.start()

    while not _reader_shutdown.is_set():
        try:
            msg = _pending_queue.get(timeout=POLL_INTERVAL)
            keep_running = _process_message(msg)
            if not keep_running:
                break
        except queue.Empty:
            continue

    _reader_shutdown.set()
    print("[mcp-server] Shutting down", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()
