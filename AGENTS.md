# CortexStratum - Agent Instructions

**209-tool MCP server** for local memory, trace system, lifecycle hooks, skill routing, and multi-modal AI. Pure Python, stdlib-only core. v0.5.0.

[CLAUDE.md](CLAUDE.md) covers basic MCP tool usage. This file covers everything an agent would likely miss without help.

## CortexStratum Ecosystem Constraints

### Architectural Boundaries
The system is a distinct, local-first architecture.

**CortexStratum (Executive Memory Layer):**
- **Language:** Python standard library strictly.
- **Dependencies:** Zero `pip` installations permitted in the core server.
- **Integration:** External engines (Node/WASM, OpenGeometry, etc.) are bridged via `subprocess` execution, not imported.
- **Search Engine:** BM25 via a local standard-library implementation.

### Tools and Skills Utilization Protocol
The toolchain runs over standard input/output (stdio). Use it proactively before guessing syntax or state. Check the current `VERSION` and existing test coverage with filesystem tools before writing code.

### Development & Execution Loop
1. **Read:** Check `VERSION` and read existing test coverage.
2. **Code:** Implement logic adhering to the project's language and dependency constraints.
3. **Test:** Run relevant verification scripts (`test-tool-logic.py`, `verifier_middleware.py`). End-to-end validation is required, not just green unit mocks.
4. **Validate Behavior:** Assert behavior contracts and invariants (how two pieces of data must relate), not frozen snapshot values.
5. **Halt on Failure:** If tests do not pass, rollback or correct the implementation immediately.

### Build Stabilization (plumber)
`read_plumber_verify_build` scans installer scripts and docs for stale tool-count references against current project state. `write_plumber_stabilize_build` auto-fixes them (dry-run by default). Run both before any commit that changes tool counts or installer files. Current count: 211.

## Quick Reference

```powershell
# Start server (3 modes)
python scripts/tools-mcp-server.py
python scripts/tools-mcp-server.py --permissive   # bypass all permission checks
python scripts/tools-mcp-server.py --debug        # verbose logging

# List all 209 tools (verify registration)
python scripts/tools-mcp-server.py --list-tools

# Run full test suite (each script is self-validating, exit non-zero on failure)
python scripts/test-mcp-server.py         # 10 MCP protocol tests
python scripts/test-smoke-server.py       # 8 server health checks (spawns real subprocess)
python scripts/test-skill-pipeline.py     # 157 skill router tests (cross-checks 77 skill refs)
python scripts/verifier_middleware.py      # 15 verifier middleware tests
python scripts/memory_search.py           # SQLite+FTS5 memory smoke test (no assertions)
```

**Prerequisites:** Python 3.10+. No pip required for core. Optional: `pip install -r requirements-full.txt` + `playwright install firefox` for web/OCR/audio tools.

## Permission Model & Workflow

Every tool is self-documenting: `read_*` tools are safe, `write_*` and `mutate_*` tools include a ` WRITE`/` MUTATE` prefix in their description and accept `dry_run=true` to preview before executing.

**Single server.** There is one `CortexStratum` MCP server. The `--permissive` flag exists but is only needed if your MCP client enforces strict auto-mode blocking (rare).

**Workflow:** `verify → check → mutate`
1. **Verify** — use analysis/validation tools to confirm intent
2. **Check** — use `read_*` tools to inspect current state
3. **Mutate** — use `write_*` or `mutate_*` tools to persist changes

All write/mutate tools accept `dry_run=true` for zero-risk preview. The permission guard in `can_call_tool()` (line 37) only blocks writes in auto mode; in interactive mode it returns a warning advisory.

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

Python linting via **ruff** (install: `pip install ruff` or `pip install -r requirements-full.txt`). The verification gate uses:

```powershell
# 1. Ruff linting (all Python files) — MUST be clean before merge
ruff check .

# 2. Syntax check all Python files
Get-ChildItem -Recurse -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }

# 3. MCP smoke test (boots server, tests protocol)
python scripts/test-smoke-server.py

# 4. MCP protocol compliance
python scripts/test-mcp-server.py

# 5. Skill router integrity (catches dangling references)
python scripts/test-skill-pipeline.py

# 6. Verifier middleware
python scripts/verifier_middleware.py

# 7. Guardrails safety pipeline
python scripts/guardrails.py

# 8. Tool count (must be 150+)
python scripts/tools-mcp-server.py --list-tools | python -c "import sys,json; tools=json.load(sys.stdin); print(f'{len(tools)} tools'); assert len(tools)>=150"

# 9. Re-read changed files, hunt oversights
```

All test scripts are self-validating (exit 0 on pass, non-zero on failure). No pytest needed.

## Repo-Specific Gotchas

| Gotcha | Detail |
|--------|--------|
| **Version in 2 places** | `VERSION` file AND `VERSION = "..."` constant in `tools-mcp-server.py` (line 28). Update both on release. |
|| **No GH Actions CI properly configured** | `.github/workflows/` exists (`ci.yml`, `release.yml`) but CI may not trigger automatically. Verify with `git push` test. |
| **PS1 scripts are legacy** | `scripts/*.ps1` files have Python equivalents in `scripts/`. Don't extend PS1; migrate to Python. |
| **requirements.txt is a no-op** | Lists zero packages. Core must stay stdlib-only. Optional deps go in `requirements-full.txt`. |
| **stdio transport** | JSON-RPC over stdin/stdout, not HTTP. Cannot curl directly. Use MCP client (OpenCode, Claude Code). |
| **.agents/ is for plugin marketplace** | `.agents/plugins/marketplace.json` is unrelated to OpenCode agent definitions (those are in `.opencode/agents.md`). |
| **opencode.json vs .opencode/opencode.jsonc** | Root `opencode.json` registers MCP servers. `.opencode/opencode.jsonc` has more config (permissive, debug modes). Both need updating for new server configs. |

## Data Storage

All runtime data is local JSON in `data/` and `.memory/`. **Not git-tracked** (except `data/synonyms.json`).

| Path | Content |
|------|---------|
| `data/memory_store.json` | Legacy BM25 memory entries (migrated to SQLite+FTS5) |
| `data/error-registry.json` | Error signatures with occurrence counts and resolutions |
| `data/decision-registry.json` | Architecture decisions with rationale |
| `data/goal-registry.json` | Current goal with sub-goal decomposition |
| `data/commitments.json` | Session promises with cross-session verification |
| `data/synonyms.json` | BM25 synonym expansion map (**git-tracked**) |
|| `data/tool-inventory.json` | All 209 tool definitions (for verification) |
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

`scripts/tools-mcp-server.py` (3929 lines) is the single entrypoint. It owns:
||- Permission guard (`can_call_tool`, line 37)
||- Module factory (`_get_module`, line 85)
||- All 211 tool definitions (`TOOLS` list, starts ~line 250)
|- Tool dispatch (`handle_tool_call`, line ~750)
|- CLI flags (`--permissive`, `--debug`, `--list-tools`, `--version`)
|- stdio JSON-RPC loop (`main()`, ~line 3520)

Do not split this file without explicit approval.
