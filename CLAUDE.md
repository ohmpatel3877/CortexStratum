# CortexStratum — Agent Guide

This file helps AI agents navigate and use this repository effectively.

## What This Repo Is

A 68-tool MCP server providing local memory infrastructure for AI coding agents.
Pure Python, zero cloud LLM dependencies for memory operations.

## How MCP Tools Work

Tools are defined in `scripts/tools-mcp-server.py` and dispatched to handler
functions in 12 Python modules under `scripts/`. Permission model:

| Prefix | Permission | Auto Mode | Interactive | Permissive |
|--------|-----------|-----------|-------------|------------|
| `read_*` | read |  |  |  |
| `write_*` | write |  blocked |  warning |  |
| `mutate_*` | mutate |  blocked |  warning |  |

## Key Files

| File | Purpose |
|------|---------|
| `scripts/tools-mcp-server.py` | Main MCP server (135 tools, permission guard, CLI flags) |
| `scripts/memory_search.py` | BM25 engine with synonym expansion and consolidation |
| `scripts/trace.py` | Error, decision, goal, commitment registries |
| `scripts/verifier_middleware.py` | Pre/post tool verification + renudge signals |
| `skills/skill-router.json` | 52 trigger rules mapping intents to skills |
| `opencode.json` | OpenCode MCP server registration |
| `COMMANDS.md` | Central command registry |

## Quick Start

```bash
# Show available tools
python scripts/tools-mcp-server.py --list-tools

# Start server (default: interactive mode)
python scripts/tools-mcp-server.py

# Start server (bypass permission checks)
python scripts/tools-mcp-server.py --permissive

# Run test suite
python scripts/test-mcp-server.py
python scripts/test-skill-pipeline.py
```

## Skill Router

The skill router (`skills/skill-router.json`) maps task keywords to skills.
When no rule matches, a 3-level fallback applies: env var → user config → defaults.
Duplicate trigger keywords are resolved by highest priority.

## Architecture

```
MCP Client → JSON-RPC over stdio → tools-mcp-server.py
   Permission Guard (can_call_tool)
   Verifier Middleware (security, drift, renudge)
   Trace System (error, decision, goal, commitment)
   NE-Memory (BM25 search, synthesis, consolidation)
   7 Modules: Sensory, Coder, Audio, Art, DevOps, Game Dev, Literature
```

## Related

- Repository: https://github.com/ohmpatel3877/CortexStratum
- Wiki: https://github.com/ohmpatel3877/CortexStratum/wiki
- Issues: https://github.com/ohmpatel3877/CortexStratum/issues
