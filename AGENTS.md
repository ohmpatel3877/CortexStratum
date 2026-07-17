# ai-memory-core - Agent Instructions

**72-tool MCP server** for local memory, trace system, lifecycle hooks, skill routing, and multi-modal AI. Pure Python, stdlib-only core. v0.3.0.

[CLAUDE.md](CLAUDE.md) covers basic MCP tool usage. This file covers everything an agent would likely miss without help.

## Quick Reference

```powershell
# Start server (3 modes)
python scripts/tools-mcp-server.py
python scripts/tools-mcp-server.py --permissive   # bypass all permission checks
python scripts/tools-mcp-server.py --debug        # verbose logging

# List all 72 tools (verify registration)
python scripts/tools-mcp-server.py --list-tools

# Run full test suite (each script is self-validating, exit non-zero on failure)
python scripts/test-mcp-server.py         # 10 MCP protocol tests
python scripts/test-smoke-server.py       # 8 server health checks (spawns real subprocess)
python scripts/test-skill-pipeline.py     # 157 skill router tests (cross-checks 77 skill refs)
python scripts/verifier_middleware.py      # 15 verifier middleware tests
python scripts/memory_search.py           # BM25 smoke test (no assertions)
```

**Prerequisites:** Python 3.10+. No pip required for core. Optional: `pip install -r requirements-full.txt` + `playwright install firefox` for web/OCR/audio tools.

## Permission Model (enforced per-call)

The guard is `can_call_tool()` in `tools-mcp-server.py` (line 37). Fix permission errors with `--permissive` flag, **not** by editing code.

| Prefix | Count | auto mode | interactive mode | permissive mode |
|--------|-------|-----------|-----------------|-----------------|
| `read_*` | 58 | ✅ | ✅ | ✅ |
| `write_*` | 6 | ❌ blocked | ⚠️ warning | ✅ |
| `mutate_*` | 3 | ❌ blocked | ⚠️ warning | ✅ |

## Module Architecture

Two patterns exist. This matters when adding tools.

**Pattern A - Inline dispatch (literature-module.py):** Tools are called by name in `handle_tool_call()` in `tools-mcp-server.py` (line 932). Module exports standalone functions (`analyze_text`, `extract_concepts`, etc.). No `handle_tool_call()` in the module.

**Pattern B - Module dispatch (sensory, audio, coder):** Module has its own `handle_tool_call(name, args)` function. The server calls `module.handle_tool_call()` by prefix match. Module also exports `AUDIO_TOOLS`/`AUDIO_DISPATCH` dicts for routing.

**All modules are lazy-loaded** via `_get_module()` (line 85) - imported only on first tool call. Missing optional packages (e.g., `playwright`) error at runtime, not at import time.

To add a new module:
1. Create `scripts/new-module.py` with exported handler functions
2. Add tool definitions to `TOOLS` list in `tools-mcp-server.py`
3. Wire dispatch logic in `handle_tool_call()` using either pattern above
4. If module has optional deps, add to `requirements-full.txt` (not `requirements.txt` - core must stay stdlib-only)

## Test Suite Specifics

- **Not pytest-based.** `pyproject.toml` defines pytest config but tests are standalone scripts. Always run with `python scripts/test-*.py`.
- **test-skill-pipeline.py** checks 77 skill router references. Any dangling reference (skill file missing, skill name doesn't resolve) causes failure. Run this after changing skill-router.json.
- **test-smoke-server.py** spawns a real server subprocess, sends JSON-RPC messages, checks responses. Most reliable way to verify a new tool registers.
- **test-mcp-server.py** validates MCP protocol compliance (initialize, tools/list, tools/call, error handling).
- Full suite runs in ~15s on modern hardware.

## /check Gate (this project)

This project has no linter or typechecker (pure Python stdlib). The verification gate uses:

```powershell
# 1. Syntax check all Python files
Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }

# 2. MCP smoke test (boots server, tests protocol)
python scripts/test-smoke-server.py

# 3. MCP protocol compliance
python scripts/test-mcp-server.py

# 4. Skill router integrity (catches dangling references)
python scripts/test-skill-pipeline.py

# 5. Verifier middleware
python scripts/verifier_middleware.py

# 6. Tool count (must be 68)
python scripts/tools-mcp-server.py --list-tools | python -c "import sys,json; tools=json.load(sys.stdin); print(f'{len(tools)} tools'); assert len(tools)==68"

# 7. Re-read changed files, hunt oversights
```

All test scripts are self-validating (exit 0 on pass, non-zero on failure). No pytest needed.

## Repo-Specific Gotchas

| Gotcha | Detail |
|--------|--------|
| **Version in 2 places** | `VERSION` file AND `VERSION = "..."` constant in `tools-mcp-server.py` (line 28). Update both on release. |
| **No CI** | `.github/workflows/` does not exist despite BUILD.md referencing it. |
| **PS1 scripts are legacy** | `scripts/*.ps1` files have Python equivalents in `scripts/`. Don't extend PS1; migrate to Python. |
| **requirements.txt is a no-op** | Lists zero packages. Core must stay stdlib-only. Optional deps go in `requirements-full.txt`. |
| **stdio transport** | JSON-RPC over stdin/stdout, not HTTP. Cannot curl directly. Use MCP client (OpenCode, Claude Code). |
| **.agents/ is for plugin marketplace** | `.agents/plugins/marketplace.json` is unrelated to OpenCode agent definitions (those are in `.opencode/agents.md`). |
| **opencode.json vs .opencode/opencode.jsonc** | Root `opencode.json` registers MCP servers. `.opencode/opencode.jsonc` has more config (permissive, debug modes). Both need updating for new server configs. |

## Data Storage

All runtime data is local JSON in `data/` and `.memory/`. **Not git-tracked** (except `data/synonyms.json`).

| Path | Content |
|------|---------|
| `data/memory_store.json` | BM25 memory entries (facts, preferences, learnings) |
| `data/error-registry.json` | Error signatures with occurrence counts and resolutions |
| `data/decision-registry.json` | Architecture decisions with rationale |
| `data/goal-registry.json` | Current goal with sub-goal decomposition |
| `data/commitments.json` | Session promises with cross-session verification |
| `data/synonyms.json` | BM25 synonym expansion map (**git-tracked**) |
| `data/tool-inventory.json` | All 68 tool definitions (for verification) |
| `.memory/ne/` | BM25 index files |
| `.memory/profiles/` | Agent identity profiles |

## Agent Definitions

`.opencode/agents.md` defines 8 agent personas: @architect, @debugger, @tester, @reviewer, @researcher, @memory, @designer, @installer. Each has fixed skill and tool sets. When adding a new tool, update relevant agent definitions.

## Skills Directory

14 skills in `skills/` directory, 45 active in `.opencode/active-skills.json`. Router at `skills/skill-router.json` has 54 trigger rules with priority-based dedup and 3-level fallback chain. When adding a new skill, register in all three places.

### Backward Skill Execution

The router supports **backward matching** for prompt+command sequences. When a task query gets zero keyword matches and a `previous_task` is provided (e.g., "/run check" after "debug this crash"), the router re-scans the previous task for trigger keywords. If the previous task had real matches, those skills are returned instead of the default fallback. This handles:

- User gives a prompt ("debug this crash"), then a command ("/run check") -- `/run check` inherits the `troubleshooting-master` skill from context.
- User names a specific MCP tool ("read_xtrace_search for the error") -- the catch-all rule at priority 1 matches known tool names.

The `previous_task` parameter is accepted by the `read_skill_router_match` MCP tool. Response includes a `backward_matched: true` flag when backward matching was applied.

## Commands

`COMMANDS.md` is the central command registry. Run `python scripts/tools-mcp-server.py --help` for server flags.

## MCP Server Entrypoint

`scripts/tools-mcp-server.py` (1238 lines) is the single entrypoint. It owns:
- Permission guard (`can_call_tool`, line 37)
- Module factory (`_get_module`, line 85)
- All 68 tool definitions (`TOOLS` list, starts ~line 150)
- Tool dispatch (`handle_tool_call`, line 748)
- CLI flags (`--permissive`, `--debug`, `--list-tools`, `--version`)
- stdio JSON-RPC loop (`main()`, ~line 1100)

Do not split this file without explicit approval.
