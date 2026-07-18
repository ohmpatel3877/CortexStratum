# Externalization Plan: CortexStratum Non-Core Modules

**Status:** Draft · **Target:** v0.5.0–v0.7.0

Move 7 largest non-core modules from the monolithic `tools-mcp-server.py` into standalone MCP servers. This shrinks the core server from ~133 tools to ~86, reduces startup risk from optional dependencies, and enables independent release cycles.

---

## 1. Module Inventory

| # | Module | File | Tools | Lines | Deps | Pattern |
|---|--------|------|-------|-------|------|---------|
| 1 | Sensory | `sensory-module.py` | 14 | 854 | **optional** (playwright, bs4, trafilatura, pdfplumber, requests) | Module dispatch (`handle_tool_call`) |
| 2 | Coder | `coder-module.py` | 7 | 1,924 | stdlib only | Module dispatch (`coder_handle_tool_call`) |
| 3 | Audio | `audio-module.py` | 7 | 913 | stdlib only | Module dispatch (`handle_tool_call`) |
| 4 | DevOps | `devops-module.py` | 7 | 1,172 | stdlib only | Module dispatch (`devops_handle_tool_call`) |
| 5 | Gamedev | `game-dev-module.py` | 7 | 1,848 | stdlib only | Module dispatch (`gamedev_handle_tool_call`) |
| 6 | Art | `art-module.py` | 4 | 306 | stdlib only | Inline dispatch (direct function calls) |
| 7 | Lit | `literature-module.py` | 4 | 310 | stdlib only | Inline dispatch (direct function calls) |
| | **Total** | | **50** | **7,327** | | |

**Note:** Sensory is the only module with non-stdlib dependencies. All others are pure stdlib — trivial to extract.

---

## 2. Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                    tools-mcp-server.py                       │
│  (stdlib: json, sys, os, subprocess, time, re, threading,   │
│   queue, select, hashlib, pathlib)                          │
│                                                             │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ sensory   │  │ coder    │  │ audio    │  │ devops    │  │
│  │ 854 lines │  │ 1924 L   │  │ 913 L    │  │ 1172 L    │  │
│  │ ──stdlib  │  │──stdlib  │  │──stdlib  │  │──stdlib   │  │
│  │ ──opt:    │  │──no opts │  │──no opts │  │──no opts  │  │
│  │  playwright│  │          │  │          │  │           │  │
│  │  bs4       │  │          │  │          │  │           │  │
│  │  trafilatura│ │          │  │          │  │           │  │
│  │  pdfplumber│ │          │  │          │  │           │  │
│  │  requests  │  │          │  │          │  │           │  │
│  └─────┬─────┘  └───┬──────┘  └───┬──────┘  └─────┬─────┘  │
│        │            │             │               │         │
│  ┌─────▼─────┐  ┌───▼──────┐  ┌──▼───────┐  ┌────▼──────┐ │
│  │ gamedev   │  │ art      │  │ lit      │  │ (core)   │ │
│  │ 1848 L    │  │ 306 L    │  │ 310 L    │  │ ~86 tools│ │
│  │──stdlib   │  │──stdlib  │  │──stdlib  │  │          │ │
│  │──no opts  │  │──no opts │  │──no opts │  │          │ │
│  └───────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────┘

Legend:
  ──stdlib  = only Python standard library imports
  ──opt:    = lazy-loaded optional third-party packages

Key observations:
  - Every module is 100% self-contained — zero cross-module imports
  - No shared state, no singletons, no circular deps between modules
  - Sensory is the only module with optional pip dependencies
  - All modules follow dict-in → dict-out handler pattern
  - Extraction is mechanical: wrap in stdio JSON-RPC loop, no refactoring needed
```

---

## 3. Suggested Directory Structure

All external MCP servers live under a new `external/` directory, one folder per server:

```
CortexStratum/
├── docs/
│   └── externalization-plan.md        ← this file
├── external/
│   ├── cortex-sensory-mcp/
│   │   ├── server.py                  ← wrapped sensory-module.py
│   │   ├── requirements.txt           ← playwright, bs4, trafilatura, pdfplumber, requests
│   │   └── README.md
│   ├── cortex-coder-mcp/
│   │   ├── server.py                  ← wrapped coder-module.py
│   │   └── README.md
│   ├── cortex-audio-mcp/
│   │   ├── server.py                  ← wrapped audio-module.py
│   │   └── README.md
│   ├── cortex-devops-mcp/
│   │   ├── server.py                  ← wrapped devops-module.py
│   │   └── README.md
│   ├── cortex-gamedev-mcp/
│   │   ├── server.py                  ← wrapped game-dev-module.py
│   │   └── README.md
│   ├── cortex-art-mcp/
│   │   ├── server.py                  ← wrapped art-module.py
│   │   └── README.md
│   └── cortex-lit-mcp/
│       ├── server.py                  ← wrapped literature-module.py
│       └── README.md
├── scripts/
│   ├── tools-mcp-server.py             ← core (86 tools, slimmed)
│   ├── sensory-module.py               ← kept during migration, removed in v0.7
│   ├── coder-module.py                 ← kept during migration, removed in v0.7
│   └── ... (all other module files)
└── opencode.json
```

---

## 4. Extraction Steps (Per Module)

Each module follows the same mechanical extraction. The only variation is how `handle_tool_call()` is connected in the 4 dispatch patterns.

### 4.1 Create Wrapper Server

Each external server is a standalone Python script with a stdio JSON-RPC loop (identical to `tools-mcp-server.py`'s `main()`). The wrapper:

1. **Copy** the module file into `external/<server-name>/`
2. **Create** `external/<server-name>/server.py` in this skeleton:

```python
#!/usr/bin/env python3
"""Standalone MCP server for <module-name> tools."""
import json, sys, os, threading, queue, time
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Import the module
sys.path.insert(0, os.path.dirname(__file__))
import <module-file> as mod

VERSION = "0.1.0"
TOOLS = [...]  # <-- copied from tools-mcp-server.py TOOLS list, only this module's entries

def send_message(msg):
    payload = json.dumps(msg, ensure_ascii=False)
    raw = payload.encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw)
    sys.stdout.buffer.flush()

def read_message():
    # Same stdio reader as tools-mcp-server.py
    ...

def handle_call(name, args):
    # <module-pattern> — match the appropriate dispatch line:
    # Pattern A (sensory/audio): mod.handle_tool_call(name, args)
    # Pattern B (coder):         mod.coder_handle_tool_call(name, args)
    # Pattern C (devops):        mod.devops_handle_tool_call(name, args)
    # Pattern D (gamedev):       mod.gamedev_handle_tool_call(name, args)
    # Pattern E (art/lit):       direct function calls, prefix-matching on name
    ...

# main() with reader thread, same pattern as tools-mcp-server.py
if __name__ == "__main__":
    main()
```

### 4.2 Dispatch Patterns Reference

| Module | Pattern | Handler signature |
|--------|---------|------------------|
| sensory | Module dispatch | `handle_tool_call(name, args)` |
| audio | Module dispatch | `handle_tool_call(name, args)` |
| coder | Module dispatch | `coder_handle_tool_call(name, args)` |
| devops | Module dispatch | `devops_handle_tool_call(name, args)` |
| gamedev | Module dispatch | `gamedev_handle_tool_call(name, args)` |
| art | Inline dispatch | `art.generate_svg(...)` / `art.extract_palette(...)` etc. |
| lit | Inline dispatch | `lit.analyze_text(...)` / `lit.extract_concepts(...)` etc. |

### 4.3 Update `opencode.json`

Register each server in the `mcpServers` section. See §6 for example.

### 4.4 Remove from Core

After migration window (see §7), strip the tool definitions and dispatch lines from `tools-mcp-server.py`.

**Dispatch lines to remove** (from `tools-mcp-server.py`):

| Lines | Prefix | Module |
|-------|--------|--------|
| 428–435 | `read_art_*` → `_get_module("art_module", ...)` → art |
| 437–444 | `read_lit_*` → `_get_module("lit_module", ...)` → lit |
| 446–448 | `read_sensory_*` / `write_sensory_*` → sensory |
| 450–452 | `read_audio_*` → audio |
| 454–456 | `read_coder_*` → coder |
| 458–460 | `read_devops_*` → devops |
| 462–464 | `read_gamedev_*` → gamedev |

**Tool definitions to remove** (from the `TOOLS` list in `tools-mcp-server.py`):

- Lines 167–171: art tools (4 entries)
- Lines 173–177: lit tools (4 entries)
- Lines 179–193: sensory tools (14 entries)
- Lines 195–202: audio tools (7 entries)
- Lines 204–211: coder tools (7 entries)
- Lines 213–220: devops tools (7 entries)
- Lines 222–229: gamedev tools (7 entries)

---

## 5. Backward Compatibility Strategy

### Phase 1: Dual Registration (v0.5.0)

Core server retains tools AND dispatch. External servers are registered alongside.

```python
# In tools-mcp-server.py — unchanged during Phase 1
TOOLS = [...]  # still includes all 133 tools
# Dispatch retains all module branches
```

OpenCode client sees both the core-internal and external versions. Tools with identical names are deduplicated by OpenCode's MCP client at the connection level (last-registered wins). To avoid conflicts:

- **Keep core tools as-is** during Phase 1
- **Let external servers shadow** the core when both are registered (OpenCode uses the external server's tool list)
- Users can disable the external server to fall back to core

### Phase 2: Deprecation Warnings (v0.6.0)

Add deprecation notes to the core tool descriptions:

```python
{"name": "read_sensory_fetch", "description": "[DEPRECATED — use cortex-sensory-mcp] Merged fetch URL...", ...}
```

### Phase 3: Core Removal (v0.7.0)

Delete tool definitions and dispatch lines from `tools-mcp-server.py`. Core drops to ~86 tools. Update `requirements.txt` to document that optional deps moved. Update `AGENTS.md` with new server instructions.

---

## 6. `opencode.json` Registration Fragment

Add to the `"mcpServers"` section of `CortexStratum/opencode.json`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "name": "CortexStratum",
  "version": "0.7.0",

  "mcpServers": {
    "CortexStratum": {
      "name": "CortexStratum",
      "description": "86-tool core MCP server: memory, simulation, cognitive pipeline",
      "command": "python",
      "args": ["scripts/tools-mcp-server.py"],
      "disabled": false
    },

    "cortex-sensory-mcp": {
      "name": "cortex-sensory-mcp",
      "description": "14 web browsing & content extraction tools (Playwright-based)",
      "command": "python",
      "args": ["external/cortex-sensory-mcp/server.py"],
      "disabled": false
    },

    "cortex-coder-mcp": {
      "name": "cortex-coder-mcp",
      "description": "7 code analysis, review, conversion & architecture tools",
      "command": "python",
      "args": ["external/cortex-coder-mcp/server.py"],
      "disabled": false
    },

    "cortex-audio-mcp": {
      "name": "cortex-audio-mcp",
      "description": "7 audio analysis, waveform, frequency & speech tools",
      "command": "python",
      "args": ["external/cortex-audio-mcp/server.py"],
      "disabled": false
    },

    "cortex-devops-mcp": {
      "name": "cortex-devops-mcp",
      "description": "7 devops: container, samba, mergerfs & network diagnostics",
      "command": "python",
      "args": ["external/cortex-devops-mcp/server.py"],
      "disabled": false
    },

    "cortex-gamedev-mcp": {
      "name": "cortex-gamedev-mcp",
      "description": "7 game dev: design analysis, scaffolding, optimization",
      "command": "python",
      "args": ["external/cortex-gamedev-mcp/server.py"],
      "disabled": false
    },

    "cortex-art-mcp": {
      "name": "cortex-art-mcp",
      "description": "4 SVG generation, color themes & design tools",
      "command": "python",
      "args": ["external/cortex-art-mcp/server.py"],
      "disabled": false
    },

    "cortex-lit-mcp": {
      "name": "cortex-lit-mcp",
      "description": "4 text analysis, concept extraction & study guide tools",
      "command": "python",
      "args": ["external/cortex-lit-mcp/server.py"],
      "disabled": false
    }
  }
}
```

---

## 7. Migration Timeline

| Phase | Version | Action | Core Tools | External Servers |
|-------|---------|--------|-----------|-----------------|
| **Phase 0** | v0.4.x | Audit & plan | 133 | 0 |
| **Phase 1** | v0.5.0 | Extract all 7 → external servers. Core retains tools (dual registration). Update `opencode.json`. | 133 | 7 |
| **Phase 1.5** | v0.5.1 | Test each server independently. `pip install -r external/*/requirements.txt`. Run `--list-tools` on each. | 133 | 7 |
| **Phase 2** | v0.6.0 | Add `[DEPRECATED — use <server-name>]` tags in core tool descriptions. Update docs. | 133 (deprecated) | 7 |
| **Phase 3** | v0.7.0 | Remove from core. Delete tool defs + dispatch lines. Core drops to ~86 tools. Update AGENTS.md, tests, version. | 86 | 7 |

---

## 8. Verification Checklist

Before each external server ships independently:

- [ ] `python server.py --list-tools` returns correct tool count
- [ ] Each tool call returns valid MCP JSON-RPC response (test with `test-smoke-server.py` equivalent)
- [ ] Server starts, handles initialize, tools/list, tools/call, shutdown
- [ ] Optional deps (sensory only) produce informative ImportError, not a crash
- [ ] Core server still boots with module file absent (tests for Phase 3)
- [ ] No cross-module regressions (other 86 core tools unchanged)
- [ ] `opencode.json` validates against `https://opencode.ai/config.json`

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Tool naming collision (core + external) | High | Medium | Prefix all external tools with their module scope (already done: `read_sensory_*`, `read_coder_*`). OpenCode MCP client deduplicates by server. |
| Sensory's optional deps break at import | Medium | High | Keep lazy-loading pattern (`_get_playwright()`, etc.) — error only at call time, not import. |
| Users lose tools if they don't register externals | Low | High | Document in AGENTS.md, make external registration the default in opencode.json. |
| Module file moves break symlinks | Low | Medium | Use relative paths in opencode.json `args`. All servers are inside the repo. |
| Test scripts reference removed tools | Medium | Medium | Update `test-mcp-server.py` and `test-smoke-server.py` in Phase 3 to test only core tools. Add per-server smoke tests. |

---

## 10. Immediate Next Steps

1. Create `external/cortex-sensory-mcp/` (highest value — has optional deps, removes startup risk)
2. Create `external/cortex-coder-mcp/` (largest file at 1,924 lines)
3. Create remaining 5 servers (each is a ~30-minute mechanical extraction)
4. Update `opencode.json` with all 7 server entries
5. Run full test suite: `python scripts/test-smoke-server.py`
6. Tag v0.5.0
