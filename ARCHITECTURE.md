# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client                                │
│          (OpenCode, Claude Code, Cursor...)                  │
├─────────────────────────────────────────────────────────────┤
│                  JSON-RPC 2.0 over stdio                     │
├─────────────────────────────────────────────────────────────┤
│                   tools-mcp-server.py                        │
│                                                              │
│  ┌──────────── Permission Guard ─────────────────────────┐  │
│  │  can_call_tool(name, {mode})                          │  │
│  │  auto mode     → blocks write_/mutate_                │  │
│  │  interactive   → allows all, warns on write/mutate    │  │
│  │  permissive    → all tools allowed, no warnings       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────┐ ┌──────┐ ┌──────┐ ┌────────┐ ┌──────────┐   │
│  │ Trace    │ │Memory│ │Coder │ │ Audio  │ │Sensory   │   │
│  │ 13 tools │ │5 tls │ │7 tls │ │ 7 tls  │ │ 12 tls   │   │
│  └──────────┘ └──────┘ └──────┘ └────────┘ └──────────┘   │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │DevOps  │ │GameDev │ │Art     │ │Lit     │ │Verifier│   │
│  │ 7 tls  │ │ 7 tls  │ │4 tls   │ │4 tls   │ │ 4 tls  │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │
│                                                              │
│  ┌─────────── Module Factory ─────────────────────────┐     │
│  │  _get_module(name, filename) — lazy-loaded, cached  │     │
│  │  Error handling: try/except with user-friendly msgs │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
         │                                      │
         ▼                                      ▼
┌────────────────────┐              ┌─────────────────────────┐
│ data/              │              │ .memory/                │
│  error-registry    │              │  profiles/              │
│  decision-registry │              │  identity/              │
│  goal-registry     │              │  ne/ (BM25 index)      │
│  commitments       │              └─────────────────────────┘
│  tool-inventory    │
│  synonyms          │
└────────────────────┘
```

## Permission Model

The `can_call_tool()` guard is the core safety architecture. Every tool has
a `permission` field: `read`, `write`, or `mutate`. The guard enforces access
at three levels:

### Mode Comparison

| Mode | Flag | `read_*` | `write_*` | `mutate_*` | Use Case |
|------|------|----------|-----------|------------|----------|
| **auto** | default | ✅ Allowed | ❌ Blocked | ❌ Blocked | Unattended agents, CI |
| **interactive** | default | ✅ Allowed | ⚠️ Warning | ⚠️ Warning | Human-in-the-loop |
| **permissive** | `--permissive` | ✅ Allowed | ✅ Allowed | ✅ Allowed | Trusted environments |

### Auto Mode Failure Behavior

When an agent calls a `write_` or `mutate_` tool in auto mode, the server
returns a clear JSON error:

```json
{
  "error": "permission_denied",
  "tool": "write_memory_add",
  "reason": "Tool 'write_memory_add' requires write permission — blocked in auto mode. Only read_ tools allowed without human review. Use --permissive flag or interactive mode to bypass.",
  "message": "Tool call blocked by permission middleware."
}
```

The error is deterministic, immediate, and leaves the system in a consistent
state — no partial writes, no silent failures, no hangs.

### CLI Flags

```
--help         Show usage information
--version      Show version string (current: 0.3.0)
--list-tools   List all 68 tools as JSON
--permissive   Bypass all permission checks
--debug        Enable verbose logging
```

## Data Flow

```
Request Flow:
  MCP Client → tools/call → can_call_tool() → verifier.pre_verify()
    → handle_tool_call() → module handler → verifier.post_verify()
    → JSON-RPC response

Memory Flow:
  write_memory_add → BM25 tokenize → index rebuild → save to .memory/ne/memories.json
  read_memory_search → tokenize → synonym expand → fuzzy match → BM25 score → rank → return
  mutate_memory_consolidate → Jaccard similarity → confidence-based merge → save

Trace Flow:
  write_xtrace_log_error → normalize signature → increment or create → save
  read_xtrace_search → keyword match across signature/cause/fixes → sort by recency
```

## Module Architecture

Each module in `scripts/` follows the same pattern:
1. Pure functions: `dict in → dict out`
2. Lazy-loaded dependencies (imported only when the module is first called)
3. Dispatched via a `handle_tool_call(name, args)` function

| Module | File | Dependencies | Status |
|--------|------|-------------|--------|
| Memory | `memory_search.py` | stdlib only | ✅ Pure BM25 |
| Trace | `trace.py` | stdlib only | ✅ No deps |
| Verifier | `verifier_middleware.py` | guardrails.py | ✅ |
| Guardrails | `guardrails.py` | stdlib only | ✅ |
| Sensory | `sensory-module.py` | playwright, bs4, pdfplumber, trafilatura | ⚠️ Optional |
| Coder | `coder-module.py` | stdlib only | ✅ |
| Audio | `audio-module.py` | numpy (optional) | ⚠️ Optional |
| Art | `art-module.py` | stdlib only | ✅ |
| DevOps | `devops-module.py` | stdlib only | ✅ |
| Game Dev | `game-dev-module.py` | stdlib only | ✅ |
| Literature | `literature-module.py` | stdlib only | ✅ |

## Skill Router

The skill router (`skills/skill-router.json`) maps task keywords to skills:

- **53 rules** covering 20+ domains
- **Priority-based dedup**: duplicate trigger keywords resolve to highest-priority rule
- **3-level fallback**: env var → user config → built-in defaults
- **78 unique skill references**, 0 dud skills

## Versioning

Current: **0.3.0** (pre-1.0). All version references synced across:
- `VERSION` file
- `scripts/tools-mcp-server.py` (VERSION constant)
- `package.json`, `opencode.json`, `.claude-plugin/plugin.json`
- `opencode-container-server.iss` (installer)

## Related

- [BUILD.md](BUILD.md) — Build pipeline
- [COMMANDS.md](COMMANDS.md) — CLI command registry
- [docs/memory-store-schema.md](docs/memory-store-schema.md) — Memory store schema
