# ai-memory-core Issue Backlog

Created: 2026-07-16
Milestone: v1.3.0 (Polish & Stability)

---

## Issue 1: Installer — Add "Run OpenCode" checkbox and CLI flags

**Type**: Enhancement
**Priority**: High
**Area**: Installer / CLI

### Description
The Inno Setup installer compiles but lacks a "Run OpenCode" post-install option. The MCP server has no `--help`, `--version`, or `--list-tools` CLI flags.

### Changes Made
- Added 2 post-install checkboxes to `[Run]` section: "Launch OpenCode" and "Open verification terminal"
- Added `--help`, `--version`, `--list-tools`, `--permissive`, `--debug` CLI flags to `tools-mcp-server.py`
- Added `_print_help()`, `_print_version()`, `_list_tools()` functions

### Files Changed
- `opencode-container-server.iss` — `[Run]` section
- `scripts/tools-mcp-server.py` — CLI flags + version constant

---

## Issue 2: Permission Model — Add --permissive flag and document 3 modes

**Type**: Enhancement
**Priority**: High
**Area**: Security / Documentation

### Description
The permission model had auto/interactive modes but no way to fully bypass for trusted environments. No documentation explaining the 3 modes.

### Changes Made
- Added `--permissive` flag that skips all permission checks
- Added `DEBUG_MODE` global with `_log()` helper
- Updated `can_call_tool()` with full 3-level permission hierarchy
- Added comprehensive permission model documentation to `README.md`

### Files Changed
- `scripts/tools-mcp-server.py` — `PERMISSIVE_MODE`, updated `can_call_tool()`, `_log()`
- `README.md` — Permission Model section with tables for all 3 modes

---

## Issue 3: Skill Router — Expand coverage from 30 to 52 rules, add fallback

**Type**: Enhancement
**Priority**: Medium
**Area**: Skill System

### Description
Skill router had 30 trigger rules with no fallback mechanism when no triggers match. Many domain areas (Kubernetes, database, payment, CI/CD, monitoring) were missing.

### Changes Made
- Expanded from 30 to 52 trigger rules covering 20+ new domains
- Added 3-level fallback mechanism: env var → user config file → built-in defaults
- Added `user_config_path` support for `~/.opencode/skill-router-overrides.json`
- Updated `read_skill_router_match` handler to implement fallback logic

### Files Changed
- `skills/skill-router.json` — version 2, 52 rules, fallback config
- `scripts/tools-mcp-server.py` — fallback logic in skill router handler

---

## Issue 4: Memory Consolidation — Confidence merging, source awareness, --dry-run

**Type**: Enhancement
**Priority**: Medium
**Area**: NE-Memory

### Description
`mutate_memory_consolidate` used simple text-length-based merging. No confidence scoring, no source priority, no way to preview merges.

### Changes Made
- Added confidence-based text selection (keeps higher confidence entry's text)
- Added source priority ranking: code_preference > user_preference > system > task_learning > manual > test
- Added `dry_run` parameter to preview merges without modifying data
- Added `_get_confidence()` and `_source_priority()` helper methods
- Added detailed merge report with per-merge similarity scores
- Updated the MCP tool definition to expose `dry_run` parameter

### Files Changed
- `scripts/memory_search.py` — `consolidate()` method, new helpers
- `scripts/tools-mcp-server.py` — tool definition + handler for `dry_run`

---

## Issue 5: In-Code Documentation — Docstrings, memory_store schema, --list-tools

**Type**: Enhancement
**Priority**: Medium
**Area**: Documentation / Developer Experience

### Description
Tool handler functions lacked docstrings. Memory store schema was undocumented. No way to inspect available tools without starting the server.

### Changes Made
- Added full docstrings to `handle_tool_call()`, `can_call_tool()`, `_get_module()`, `read_exact()`, `main()`
- Added error handling to `_get_module()` factory (try/except with user-friendly messages)
- Created `docs/memory-store-schema.md` documenting the JSON schema, field reference, metadata conventions, and BM25 scoring
- Added `--list-tools` flag for debugging

### Files Changed
- `scripts/tools-mcp-server.py` — docstrings on all key functions, error handling in module factory
- `docs/memory-store-schema.md` — new file

---

## Issue 6: Test Suite — Fix broken test-mcp-server.py, create skill pipeline tests

**Type**: Bug Fix
**Priority**: High
**Area**: Testing

### Description
`test-mcp-server.py` had incorrect tool names (`skill_router_match` instead of `read_skill_router_match`, `output_condenser` tool doesn't exist). No skill pipeline integrity tests existed.

### Changes Made
- Fixed all tool name mismatches in `test-mcp-server.py` (8 tool names corrected)
- Replaced `output_condenser` test with `read_memory_status` test
- Created `test-skill-pipeline.py` — 5 test suites covering:
  1. Local skill SKILL.md validation (12 skills)
  2. Router structure validation (52 rules, schema checks)
  3. End-to-end router matching (10 test cases)
  4. Dud skill detection (77 referenced skills cross-checked)
  5. MCP tool inventory (68 tools, naming, permissions)

### Files Changed
- `scripts/test-mcp-server.py` — corrected tool names
- `scripts/test-skill-pipeline.py` — new comprehensive pipeline test

---

## Issue 7: Dud Skill Detection — Cross-reference all router skills against local + built-in

**Type**: Analysis
**Priority**: Medium
**Area**: Skill System

### Description
The skill router references many skill names. Some may not exist in the local skills/ directory or the OpenCode built-in list.

### Changes Made
- Created automated dud detection in `test-skill-pipeline.py` (Test 4)
- Cross-referenced all 77 unique skill names against 12 local + 65 known OpenCode built-in skills
- **Result: 0 dud skills found** — all 77 references accounted for

### Findings
- 12 skills are local (in `skills/` directory)
- 65 skills are known OpenCode built-ins
- Most-used local skills: `debug-samba`, `framework-builder`, `inno-setup-pipeline`, `parameter-virtualizer`, `pattern-flipper`, `security-hardening`, `speed-optimizer`, `study-tutor`, `task-orchestrator`, `vm-test-engine`

---

## Issue 8: Duplicate Router Triggers Cleanup

**Type**: Technical Debt
**Priority**: Low
**Area**: Skill System

### Description
With the expansion to 52 rules, 17 trigger keywords appear in multiple rules (e.g., "design" in brainstorm + art rules, "rust" in electron + framework-builder). This is intentional for coverage but generates noise in the audit.

### Current Triggers with Duplicates
`design`, `tauri`, `rust`, `contract`, `migration`, `cve`, `vulnerability`, `subagent`, `mcp server`, `ci`, and 7 more.

### Recommendation
Consider adding an exclusion mechanism or priority-based deduplication that prevents lower-priority rules from matching when a higher-priority rule already matched the same trigger. Currently `priority_highest_wins` only applies to conflict resolution, not trigger deduplication.
