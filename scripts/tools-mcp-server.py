#!/usr/bin/env python3
"""
MCP Server: ai-memory-core Toolchain
Exposes xTrace, DTrace, Skill Router, Output Condenser, Goal Registry,
and Commitment Checker as MCP tools for use by OpenCode and benchmark runners.

Protocol: JSON-RPC over stdio (Model Context Protocol)
"""

import json, sys, os, subprocess, time, re, threading, queue, select, hashlib
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

TOOL_EXECUTOR_TIMEOUT = 60
POLL_INTERVAL = 0.5  # seconds between poll cycles when waiting for a tool

# Lazy-loaded verifier & memory search singletons
_verifier = None
_memory_search = None

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

# Lazy-loaded module placeholders (populated on first use)
_art_module = None
_lit_module = None
_sensory_module = None
_audio_module = None
_coder_module = None
_devops_module = None
_gamedev_module = None

def _get_art_module():
    global _art_module
    if _art_module is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("art_module", SCRIPTS_DIR / "art-module.py")
        _art_module = _util.module_from_spec(spec)
        spec.loader.exec_module(_art_module)
    return _art_module

def _get_lit_module():
    global _lit_module
    if _lit_module is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("literature_module", SCRIPTS_DIR / "literature-module.py")
        _lit_module = _util.module_from_spec(spec)
        spec.loader.exec_module(_lit_module)
    return _lit_module

def _get_sensory_module():
    global _sensory_module
    if _sensory_module is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("sensory_module", SCRIPTS_DIR / "sensory-module.py")
        _sensory_module = _util.module_from_spec(spec)
        spec.loader.exec_module(_sensory_module)
    return _sensory_module

def _get_audio_module():
    global _audio_module
    if _audio_module is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("audio_module", SCRIPTS_DIR / "audio-module.py")
        _audio_module = _util.module_from_spec(spec)
        spec.loader.exec_module(_audio_module)
    return _audio_module

def _get_coder_module():
    global _coder_module
    if _coder_module is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("coder_module", SCRIPTS_DIR / "coder-module.py")
        _coder_module = _util.module_from_spec(spec)
        spec.loader.exec_module(_coder_module)
    return _coder_module

def _get_devops_module():
    global _devops_module
    if _devops_module is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("devops_module", SCRIPTS_DIR / "devops-module.py")
        _devops_module = _util.module_from_spec(spec)
        spec.loader.exec_module(_devops_module)
    return _devops_module

def _get_gamedev_module():
    global _gamedev_module
    if _gamedev_module is None:
        import importlib.util as _util
        spec = _util.spec_from_file_location("gamedev_module", SCRIPTS_DIR / "game-dev-module.py")
        _gamedev_module = _util.module_from_spec(spec)
        spec.loader.exec_module(_gamedev_module)
    return _gamedev_module

def run_powershell(script: str, args: list) -> dict:
    """Run a PowerShell script and return structured output."""
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_EXECUTOR_TIMEOUT, cwd=PROJECT_ROOT)
        return {"exit_code": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "TIMEOUT"}


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
        "name": "xtrace_log_error",
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
        "name": "xtrace_search",
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
        "name": "xtrace_status",
        "description": "Get xTrace error tracking summary statistics",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "dtrace_add",
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
        "name": "dtrace_search",
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
        "name": "skill_router_match",
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
        "name": "output_condenser",
        "description": "Condense command output to essential information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_type": {"type": "string", "enum": ["bash", "read", "grep", "mem0"]},
                "content": {"type": "string", "description": "Raw output to condense"}
            },
            "required": ["output_type", "content"]
        }
    },
    {
        "name": "goal_registry_init",
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
        "name": "goal_registry_add_subgoal",
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
        "name": "goal_registry_status",
        "description": "Get current goal registry status"
    },
    {
        "name": "goal_registry_check_alignment",
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
        "name": "commitment_checker_list",
        "description": "List pending commitments for this session",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "commitment_checker_verify",
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
        "name": "art_generate_svg",
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
        "name": "art_generate_theme",
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
        "name": "art_extract_palette",
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
        "name": "art_design_concept",
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
        "name": "lit_analyze_text",
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
        "name": "lit_extract_concepts",
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
        "name": "lit_generate_study_guide",
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
        "name": "lit_analyze_philosophy",
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
        "name": "sensory_browse",
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
        "name": "sensory_screenshot",
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
        "name": "sensory_interact",
        "description": "Navigate to URL and perform actions (click, type, press, wait)",
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
        "name": "sensory_extract_pdf",
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
        "name": "sensory_extract_html",
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
        "name": "sensory_extract_image",
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
        "name": "sensory_scrape",
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
        "name": "sensory_extract_article",
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
        "name": "sensory_api_request",
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
        "name": "sensory_fetch_rss",
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
        "name": "sensory_read_file",
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
        "name": "sensory_search",
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
    {"name": "audio_analyze_file", "description": "Analyze WAV audio file: duration, channels, sample rate, amplitude stats", "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "data_base64": {"type": "string"}, "format": {"type": "string", "default": "wav"}}, "required": []}},
    {"name": "audio_waveform", "description": "Generate ASCII waveform visualization from audio file", "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "width": {"type": "integer", "default": 80}, "height": {"type": "integer", "default": 20}}, "required": ["file_path"]}},
    {"name": "audio_frequency_analysis", "description": "DFT-based frequency analysis: band energy, dominant frequency, spectral centroid", "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}, "num_bands": {"type": "integer", "default": 10}}, "required": ["file_path"]}},
    {"name": "audio_music_theory", "description": "Music theory analysis: chord detection, scale matching, intervals from notes or frequencies", "inputSchema": {"type": "object", "properties": {"notes": {"type": "array", "items": {"type": "string"}}, "frequencies": {"type": "array", "items": {"type": "number"}}}, "required": []}},
    {"name": "audio_speech_analysis", "description": "Speech transcript analysis: WPM, filler words, pace rating, readability", "inputSchema": {"type": "object", "properties": {"transcript": {"type": "string"}, "duration_seconds": {"type": "number"}}, "required": ["transcript", "duration_seconds"]}},
    {"name": "audio_convert_guide", "description": "Audio format conversion guide with ffmpeg commands and quality comparison", "inputSchema": {"type": "object", "properties": {"source_format": {"type": "string"}, "target_format": {"type": "string"}, "quality": {"type": "string", "default": "high"}}, "required": ["source_format", "target_format"]}},
    {"name": "audio_generate_tone", "description": "Generate sine/square/saw/triangle wave tone as base64 WAV", "inputSchema": {"type": "object", "properties": {"frequency": {"type": "number", "default": 440}, "duration_seconds": {"type": "number", "default": 1}, "sample_rate": {"type": "integer", "default": 44100}, "amplitude": {"type": "number", "default": 0.5}, "waveform": {"type": "string", "default": "sine"}}, "required": []}},

    # --- Coder Module tools ---
    {"name": "coder_analyze_code", "description": "Analyze code for quality, complexity, smells, and security issues across 12 languages", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}}, "required": ["code", "language"]}},
    {"name": "coder_generate_framework", "description": "Generate complete project scaffold (web-api, cli-tool, library, desktop, microservice, data-pipeline, fullstack) for 12 languages", "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "language": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}}, "name": {"type": "string", "default": "my-project"}}, "required": ["project_type", "language"]}},
    {"name": "coder_debug", "description": "Analyze error messages and stack traces, suggest fixes (50+ error patterns across languages)", "inputSchema": {"type": "object", "properties": {"error": {"type": "string"}, "code_context": {"type": "string", "default": ""}, "language": {"type": "string"}}, "required": ["error", "language"]}},
    {"name": "coder_review", "description": "Code review with severity ratings (security, performance, readability, architecture, testing)", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}, "focus": {"type": "string", "default": "all"}}, "required": ["code", "language"]}},
    {"name": "coder_explain", "description": "Educational code explanation at beginner/intermediate/advanced level", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "language": {"type": "string"}, "level": {"type": "string", "default": "intermediate"}}, "required": ["code", "language"]}},
    {"name": "coder_convert", "description": "Convert code between languages (Python↔JS, Python→Go, Python→Rust, JS↔TS)", "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}, "from": {"type": "string"}, "to": {"type": "string"}}, "required": ["code", "from", "to"]}},
    {"name": "coder_architecture", "description": "Architecture pattern recommendation (MVC, Hexagonal, CQRS, Event-Driven, Microservices, etc.)", "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "scale": {"type": "string", "default": "medium"}, "requirements": {"type": "array", "items": {"type": "string"}}}, "required": ["project_type"]}},

    # --- DevOps Module tools ---
    {"name": "devops_container_debug", "description": "Diagnose container issues (Podman/Docker) from error logs", "inputSchema": {"type": "object", "properties": {"error_log": {"type": "string"}, "runtime": {"type": "string", "default": "podman"}, "context": {"type": "string", "default": "standalone"}}, "required": ["error_log"]}},
    {"name": "devops_permissions_analyze", "description": "Analyze permission/usernamespace issues in container environments", "inputSchema": {"type": "object", "properties": {"mount_path": {"type": "string"}, "container_user": {"type": "string"}, "host_user": {"type": "string"}, "error_symptom": {"type": "string"}}, "required": []}},
    {"name": "devops_compose_generator", "description": "Generate Docker/Podman Compose files from service definitions", "inputSchema": {"type": "object", "properties": {"services": {"type": "array"}, "networks": {"type": "array"}, "runtime": {"type": "string", "default": "docker"}}, "required": ["services"]}},
    {"name": "devops_samba_config", "description": "Generate Samba/SMB share configurations with OS-specific troubleshooting", "inputSchema": {"type": "object", "properties": {"share_name": {"type": "string"}, "path": {"type": "string"}, "users": {"type": "array"}, "options": {"type": "object"}}, "required": ["share_name", "path"]}},
    {"name": "devops_mergerfs_setup", "description": "Configure mergerfs for drive pooling with policy explanations and optimization tips", "inputSchema": {"type": "object", "properties": {"source_paths": {"type": "array"}, "mount_point": {"type": "string"}, "policy": {"type": "string", "default": "epmfs"}, "options": {"type": "object"}}, "required": ["source_paths", "mount_point"]}},
    {"name": "devops_dockerfile_analyze", "description": "Analyze and optimize Dockerfiles for security, caching, and size", "inputSchema": {"type": "object", "properties": {"dockerfile": {"type": "string"}}, "required": ["dockerfile"]}},
    {"name": "devops_network_troubleshoot", "description": "Diagnose container networking issues (DNS, ports, bridges, host networking)", "inputSchema": {"type": "object", "properties": {"symptom": {"type": "string"}}, "required": ["symptom"]}},

    # --- Game Dev Module tools ---
    {"name": "gamedev_design_analyze", "description": "Analyze game concept: fun factor, engagement loops, monetization fit, market position", "inputSchema": {"type": "object", "properties": {"concept": {"type": "string"}, "genre": {"type": "string"}, "platform": {"type": "string", "default": "pc"}}, "required": ["concept", "genre"]}},
    {"name": "gamedev_scaffold_project", "description": "Generate Unity/Unreal/Roblox project scaffold with real working boilerplate files", "inputSchema": {"type": "object", "properties": {"engine": {"type": "string"}, "genre": {"type": "string"}, "name": {"type": "string", "default": "MyGame"}, "features": {"type": "array"}}, "required": ["engine", "genre"]}},
    {"name": "gamedev_mechanics_guide", "description": "Game mechanics design guide: core loops, progression systems, reward schedules by genre", "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}, "complexity": {"type": "string", "default": "core"}}, "required": ["genre"]}},
    {"name": "gamedev_monetization", "description": "Monetization strategy recommendations with revenue estimates and ethical guidance", "inputSchema": {"type": "object", "properties": {"platform": {"type": "string"}, "genre": {"type": "string"}, "audience": {"type": "string", "default": "casual"}}, "required": ["platform", "genre"]}},
    {"name": "gamedev_optimization", "description": "Engine-specific optimization advice (FPS, draw calls, memory, load times, network)", "inputSchema": {"type": "object", "properties": {"engine": {"type": "string"}, "issue": {"type": "string"}}, "required": ["engine", "issue"]}},
    {"name": "gamedev_compare_engines", "description": "Compare game engines (Unity/Unreal/Godot/Roblox) for specific project types", "inputSchema": {"type": "object", "properties": {"project_type": {"type": "string"}, "team_size": {"type": "string", "default": "solo"}, "budget": {"type": "string", "default": "indie"}}, "required": ["project_type"]}},
    {"name": "gamedev_level_design", "description": "Level design principles, flow diagrams, pacing guides, and playtesting checklists", "inputSchema": {"type": "object", "properties": {"genre": {"type": "string"}, "level_type": {"type": "string"}}, "required": ["genre", "level_type"]}},

    # --- NE-Memory Search tools (zero-LLM BM25) ---
    {
        "name": "memory_search",
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
        "name": "memory_synthesize",
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
        "name": "memory_add",
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
        "name": "memory_consolidate",
        "description": "Merge duplicate/similar memory entries by Jaccard similarity threshold",
        "inputSchema": {
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "default": 0.85, "description": "Similarity threshold (0-1)"}
            }
        }
    },
    {
        "name": "memory_status",
        "description": "Get NE-Memory engine status: entry count, storage size, unique terms, last timestamp",
        "inputSchema": {"type": "object", "properties": {}}
    },

    # --- Verifier Middleware tools ---
    {
        "name": "verifier_status",
        "description": "Get verifier middleware status: checks run, violations found, renudges sent, uptime",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "verifier_renudge",
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
]

# Map MCP tool names to (script_name, action, args_map)
# args_map: (ps_param_name -> json_field_name)
TOOL_ROUTES = {
    "xtrace_log_error": ("error-trace.ps1", "LogError", [
        ("-FailedCommand", "command"),
        ("-ErrorOutput", "error_output"),
        ("-ExitCode", "exit_code"),
    ]),
    "xtrace_search": ("error-trace.ps1", "Search", [
        ("-Keyword", "keyword"),
    ]),
    "xtrace_status": ("error-trace.ps1", "Status", []),
    "dtrace_add": ("decision-trace.ps1", "Add", [
        ("-Title", "title"),
        ("-Context", "context"),
        ("-Decision", "decision"),
        ("-Alternatives", "alternatives"),
        ("-Rationale", "rationale"),
        ("-Category", "category"),
    ]),
    "dtrace_search": ("decision-trace.ps1", "Search", [
        ("-Keyword", "keyword"),
    ]),
    "goal_registry_init": ("goal-registry.ps1", "Init", [
        ("-Goal", "goal"),
    ]),
    "goal_registry_add_subgoal": ("goal-registry.ps1", "AddSubGoal", [
        ("-Description", "description"),
    ]),
    "goal_registry_status": ("goal-registry.ps1", "Status", []),
    "goal_registry_check_alignment": ("goal-registry.ps1", "CheckAlignment", [
        ("-CurrentAction", "current_action"),
    ]),
    "commitment_checker_list": ("check-commitments.ps1", "", [
    ]),
    "commitment_checker_verify": ("check-commitments.ps1", "", [
        ("-Verify", "id"),
    ]),
}

def handle_tool_call(name: str, args: dict) -> dict:
    """Execute a tool and return result."""

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
    if name == "memory_search":
        mem = _get_memory_search()
        result = mem.search(args.get("query", ""), args.get("limit", 10), args.get("fuzzy_threshold", 0.85))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "memory_synthesize":
        mem = _get_memory_search()
        result = mem.synthesize(args.get("query", ""), args.get("max_sources", 5), args.get("min_confidence", 0.7))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "memory_add":
        mem = _get_memory_search()
        mem_id = mem.add_memory(args.get("text", ""), args.get("source", "manual"), args.get("metadata", {}))
        return {"content": [{"type": "text", "text": json.dumps({"memory_id": mem_id, "status": "stored"})}]}

    if name == "memory_consolidate":
        mem = _get_memory_search()
        result = mem.consolidate(args.get("threshold", 0.85))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "memory_status":
        mem = _get_memory_search()
        result = mem.status()
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "verifier_status":
        result = verifier.get_status()
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "verifier_renudge":
        result = verifier.renudge(args.get("target", ""), args.get("correction", {}), args.get("strategy", "incremental"))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Special tools implemented inline
    if name == "skill_router_match":
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

    if name == "output_condenser":
        content = args.get("content", "")
        otype = args.get("output_type", "bash")
        lines = content.split("\n")
        if otype == "bash":
            key_lines = [l for l in lines if any(w in l.lower() for w in ["error", "fail", "warning", "\u2713", "\u221a", "build", "completed"])]
            condensed = key_lines[-8:] if len(key_lines) > 8 else key_lines
        elif otype == "grep":
            condensed = lines[:20]
        else:
            condensed = lines[:10]
        result = {"content": [{"type": "text", "text": "\n".join(condensed) if condensed else "(empty output)"}]}
        _get_verifier().post_verify(name, args, result, 0)
        return result

    # Route to PowerShell scripts
    route = TOOL_ROUTES.get(name)
    if route:
        script_name, action, param_map = route
        script_path = SCRIPTS_DIR / script_name
        ps_args = []
        if action:
            ps_args += ["-Action", action]
        for ps_param, json_field in param_map:
            val = args.get(json_field)
            if val is not None:
                ps_args += [ps_param, str(val)]

        if name.startswith("commitment_checker_list"):
            ps_args += ["-SessionStart"]
        if name.startswith("commitment_checker_verify"):
            pass  # -Verify id is handled in param_map

        result = run_powershell(script_path, ps_args)
        output = result["stdout"] or result["stderr"] or "(no output)"
        content = {"content": [{"type": "text", "text": output}]}
        # Verifier post-check
        _get_verifier().post_verify(name, args, content, 0)
        return content

    # Art Module tools (inline)
    if name == "art_generate_svg":
        art = _get_art_module()
        desc = args.get("description", "")
        w = args.get("width", 400)
        h = args.get("height", 300)
        svg = art.generate_svg(desc, width=w, height=h)
        return {"content": [{"type": "text", "text": svg}]}

    if name == "art_generate_theme":
        art = _get_art_module()
        desc = args.get("description", "dark cyberpunk")
        theme = art.generate_theme(desc)
        return {"content": [{"type": "text", "text": json.dumps(theme, indent=2)}]}

    if name == "art_extract_palette":
        art = _get_art_module()
        color = args.get("color", "#3b82f6")
        palette = art.extract_palette(color)
        return {"content": [{"type": "text", "text": json.dumps(palette, indent=2)}]}

    if name == "art_design_concept":
        art = _get_art_module()
        reqs = args.get("requirements", "A modern dashboard")
        concept = art.design_concept(reqs)
        return {"content": [{"type": "text", "text": json.dumps(concept, indent=2)}]}

    # Literature Module tools (inline)
    if name == "lit_analyze_text":
        lit = _get_lit_module()
        text = args.get("text", "")
        result = lit.analyze_text(text)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "lit_extract_concepts":
        lit = _get_lit_module()
        text = args.get("text", "")
        result = lit.extract_concepts(text)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "lit_generate_study_guide":
        lit = _get_lit_module()
        content = args.get("content", "")
        result = lit.generate_study_guide(content)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    if name == "lit_analyze_philosophy":
        lit = _get_lit_module()
        text = args.get("text", "")
        result = lit.analyze_philosophy(text)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Sensory Module tools (dispatched via module's handle_tool_call)
    if name.startswith("sensory_"):
        sensory = _get_sensory_module()
        result = sensory.handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Audio Module tools (dispatched via module's handle_tool_call)
    if name.startswith("audio_"):
        audio = _get_audio_module()
        result = audio.handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Coder Module tools (dispatched via coder_handle_tool_call)
    if name.startswith("coder_"):
        coder = _get_coder_module()
        result = coder.coder_handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # DevOps Module tools (dispatched via devops_handle_tool_call)
    if name.startswith("devops_"):
        devops = _get_devops_module()
        result = devops.devops_handle_tool_call(name, args)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    # Game Dev Module tools (dispatched via gamedev_handle_tool_call)
    if name.startswith("gamedev_"):
        gamedev = _get_gamedev_module()
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
            # Poll both the tool queue and the pending queue so we never miss pings.
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
                    pass  # re-check incoming messages below
                # Drain any pending messages (pings etc) that arrived during execution
                _drain_pending()
            send_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": "Tool execution timed out"}})
            return True

        # Unknown method
        if msg_id is not None:
            send_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})
        return True

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[mcp-server] Error processing message: {e}", file=sys.stderr, flush=True)
        if msg_id is not None:
            send_message({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32700, "message": f"Parse error: {e}"}})
        return True


# Shared: pending messages read by the reader thread
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
