# Memory Core Bloat Audit

**Project:** CortexStratum v0.4.0
**Date:** 2026-07-18
**Scope:** `scripts/` directory, tool inventory, module dispatch graph

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total tools defined | **124** |
| Tool permission mix | 108 read / 8 write / 8 mutate |
| Header claim | "79 tools" (line 4 of `tools-mcp-server.py`) |
| Python files in `scripts/` | 56 |
| Module files (`*-module.py`) | 17 |
| Test files | 5 |
| Infrastructure/utility scripts | 34 |
| Core memory tools | **8 (6.5%)** |
| Simulation/engineering tools | **26 (21%)** |
| Agent skill tools (non-memory) | 45 (36%) |
| Total lines of Python | ~22,000 |

**Health Score: 4/10 — Poor.** The project suffers from severe scope creep. Only 6.5% of tools relate to its stated purpose ("local memory, trace system, lifecycle hooks, skill routing"). The remaining 93.5% are unrelated agent skills, engineering calculators, web scrapers, audio analyzers, game dev scaffolds, and DevOps ops guides that should never live in a memory-core MCP server.

---

## Breakout by Domain

### Memory Core (actual purpose)
| Domain | Tools | % of Total |
|--------|-------|-----------|
| `memory_*` | 8 | 6.5% |
| `xtrace_*` (error registry) | 3 | 2.4% |
| `dtrace_*` (decision registry) | 2 | 1.6% |
| `hooks_*` (lifecycle) | 4 | 3.2% |
| `goal_registry_*` | 4 | 3.2% |
| `commitment_checker_*` | 2 | 1.6% |
| `consolidation_*` | 3 | 2.4% |
| `compact_*` (context compaction) | 5 | 4.0% |
| `mutation_*` (algorithmic mutation) | 4 | 3.2% |
| `plumber_*` (execution pipelines) | 4 | 3.2% |
| `verifier_*` | 3 | 2.4% |
| `audit_*` / `undo` | 2 | 1.6% |
| **Subtotal** | **44** | **35.5%** |

### Agent Skills (scope creep)
| Domain | Tools | % of Total | Assessment |
|--------|-------|-----------|------------|
| `sensory_*` (web/scrape/browse) | 13 | 10.5% | Belongs in a separate MCP server |
| `coder_*` | 7 | 5.6% | Belongs in a separate MCP server |
| `devops_*` | 7 | 5.6% | Belongs in a separate MCP server |
| `gamedev_*` | 7 | 5.6% | Belongs in a separate MCP server |
| `audio_*` | 7 | 5.6% | Belongs in a separate MCP server |
| `art_*` | 4 | 3.2% | Belongs in a separate MCP server |
| `lit_*` | 4 | 3.2% | Belongs in a separate MCP server |
| `pedagogy_*` | 3 | 2.4% | Belongs in a separate MCP server |
| `skill_router_*` / `tools_suggest` | 2 | 1.6% | Borderline — could stay |
| **Subtotal** | **54** | **43.5%** | |

### Simulation / Engineering Calculators
| Domain | Tools | % of Total | Assessment |
|--------|-------|-----------|------------|
| `sim_mech_*` (mechanics) | 14 | 11.3% | Belongs in separate MCP server |
| `sim_fea_*` (FEA) | 4 | 3.2% | Belongs in separate MCP server |
| `sim_cfd_*` (CFD) | 4 | 3.2% | Belongs in separate MCP server |
| `sim_matrix_*` / `sim_ode` / `sim_latex` / `sim_plot` | 4 | 3.2% | Belongs in separate MCP server |
| **Subtotal** | **26** | **21.0%** | |

### Grand Total: 124 tools

---

## Redundancy Analysis

### Critical Overlaps (tools that do essentially the same thing)

| Redundancy | Tools | Problem |
|-----------|-------|---------|
| **5 memory search variants** | `read_memory_search`, `read_memory_vector_search`, `read_memory_hybrid_search`, `read_memory_reranked_search`, `read_memory_synthesize` | All search memory with slightly different algorithms. `memory_search` already does BM25; `vector_search` requires embeddings that aren't generated; `hybrid_search` just combines the two; `reranked_search` adds a cross-encoder that likely doesn't exist. **Merge into 2 tools max.** |
| **3 URL content readers** | `read_sensory_browse`, `read_sensory_scrape`, `read_sensory_extract_article` | All fetch a URL and extract text. `browse` and `scrape` differ only in `extract_mode` vs `mode` parameter. `extract_article` is a subset of `browse`. **Merge into 1 tool with mode parameter.** |
| **HTML extraction duplication** | `read_sensory_extract_html`, `read_sensory_browse` (with `extract_mode=html`) | Same operation — parse HTML string. **Remove `extract_html` or make it a private helper.** |
| **Inverse fatigue formulas** | `read_sim_mech_fatigue_sn` (stress at N cycles), `read_sim_mech_fatigue_cycles` (cycles at stress) | Same equation, just solving for different variables. **Merge into 1 tool with a `solve_for` parameter.** |
| **Overlapping buckling formulas** | `read_sim_mech_buckle` (Euler), `read_sim_mech_buckle_johnson` (Johnson) | Both column buckling. Johnson is only needed when Euler gives non-physical results. **Merge into 1 tool that auto-selects based on slenderness ratio.** |
| **Moment of inertia tools** | `read_sim_mech_moi_rect`, `read_sim_mech_moi_circle` | Each is a single formula. **Merge into 1 tool with a `shape` parameter, or inline them.** |
| **Consolidation overlap with memory** | `read_consolidation_status`, `mutate_consolidation_run`, `read_consolidation_links` | These duplicate `read_memory_status` and `write_memory_consolidate`. The "consolidation daemon" is just a TF-IDF similarity linker built on top of the same memory store. **Merge into the memory module.** |
| **2 status-only tools with empty schemas** | `read_compact_status`, `read_mutation_status` | Both return a status dict with no input parameters. Could be a single `read_phase_status` tool. |

### Moderate Overlaps

| Pair | Issue |
|------|-------|
| `read_sensory_api_request` vs `read_sensory_browse` | API request is just HTTP with headers; browse is HTTP via Playwright. Different backends but overlapping purpose. |
| `read_sensory_read_file` vs `read_sensory_extract_pdf`/`extract_image` | File reading with different format handlers. |
| `read_sensory_search` vs `read_sensory_browse` | Search is a web search; browse fetches a single URL. Different but adjacent. |
| `read_sensory_fetch_rss` vs `read_sensory_scrape` | RSS fetching is a specialized scrape. |

---

## Externalization Candidates

These tool domains should be extracted into their own independent MCP servers. They have zero dependency on the memory core.

| Domain | Tools | Lines | Rationale |
|--------|-------|-------|-----------|
| **sensory (web/browser)** | 13 | 846 (module) | Playwright-dependent web tools. Separate concerns, separate dependencies. |
| **coder** | 7 | 1,924 | General-purpose code analysis/generation. Not memory. |
| **devops** | 7 | 1,172 | Docker/Podman/Samba/mergerfs ops. Not memory. |
| **gamedev** | 7 | 1,848 | Unity/Unreal game templates. Not memory. |
| **audio** | 7 | 913 | Audio file analysis, waveform, music theory. Not memory. |
| **sim mechanics** | 14 | 419 | Engineering formula calculators. Not memory. |
| **sim FEA** | 4 | 176 | Structural analysis formulas. Not memory. |
| **sim CFD** | 4 | 219 | Fluid dynamics formulas. Not memory. |
| **sim math** | 4 | 310 | Matrix solver, ODE, LaTeX, plot. Not memory. |
| **art** | 4 | 306 | SVG/color/design generation. Not memory. |
| **lit** | 4 | 310 | Text analysis/study guides. Not memory. |
| **pedagogy** | 3 | 110 | Teaching adaptation engine. Not memory. |
| **Total externalizable** | **78 tools (63%)** | **~6,639 lines** | |

---

## Consolidation Recommendations

### Merge Operations

| Action | Tools | Saved |
|--------|-------|-------|
| Merge 5 search tools → 2 | `memory_search`, `vector_search`, `hybrid_search`, `reranked_search`, `synthesize` | 3 tool definitions |
| Merge 3 URL readers → 1 | `sensory_browse`, `sensory_scrape`, `sensory_extract_article` | 2 tool definitions |
| Merge fatigue tools → 1 | `sim_mech_fatigue_sn`, `sim_mech_fatigue_cycles` | 1 tool definition |
| Merge buckling tools → 1 | `sim_mech_buckle`, `sim_mech_buckle_johnson` | 1 tool definition |
| Merge MOI tools → 1 | `sim_mech_moi_rect`, `sim_mech_moi_circle` | 1 tool definition |
| Consolidation → memory | `consolidation_*` → `memory_*` | 3 tool definitions |
| Status tools → 1 | `compact_status`, `mutation_status` | 1 tool definition |
| Remove `sensory_extract_html` | In favor of `browse(mode=html)` | 1 tool definition |
| **Total consolidation savings** | | **13 fewer tools (→111)** |

---

## Module Size Heatmap

### Top 10 Largest Files

| File | Lines | Role |
|------|-------|------|
| `coder-module.py` | **1,924** | Agent skill (scope creep) |
| `game-dev-module.py` | **1,848** | Agent skill (scope creep) |
| `devops-module.py` | **1,172** | Agent skill (scope creep) |
| `audio-module.py` | **913** | Agent skill (scope creep) |
| `sensory-module.py` | **846** | Agent skill (scope creep) |
| `trace.py` | **763** | Core (trace system) |
| `task-orchestrator.py` | **739** | Infrastructure |
| `sandbox-manager.py` | **648** | Infrastructure |
| `verifier_middleware.py` | **625** | Core (verifier) |
| `run-eval-harness.py` | **635** | Infrastructure |

### Size by Category

| Category | Total Lines | % of Codebase |
|----------|------------|---------------|
| Core memory/trace/verifier | ~3,500 | 16% |
| Agent skills (scope creep) | ~8,300 | 38% |
| Simulation calculators | ~1,124 | 5% |
| Infrastructure/utility | ~7,000 | 32% |
| Tests | ~1,500 | 7% |

---

## Orphaned / Undispatched Code

| Directory/File | Content | Status |
|---------------|---------|--------|
| `cad-module/` | 5 Python files (468 lines) + OpenSCAD lib | **Undispatched** — no tools in TOOLS list, no dispatch in handle_tool_call |
| `electrical-module/` | circuit_designer.py | **Undispatched** — no tools in TOOLS list |
| `hermes-plugin/` | Plugin definition + provider | **External plugin** — not wired into main server |
| `check_dispatch.py` | Dispatch coverage checker | **Orphaned utility** — 36 lines, never run in CI |

---

## Zombie Tools

No true zombie tools were found (all 124 tools in the TOOLS list have dispatch logic in `handle_tool_call()`). However:

| Issue | Detail |
|-------|--------|
| **Version discrepancy** | Header says "79 tools" (line 4), actual count is 124. Hasn't been updated since last expansion. |
| **tool_router.py stale** | Only covers 83 of 124 tools. 41 tools are missing their category/tag entries. |
| **AGENTS.md stale** | References "72-tool MCP server" and asserts 68 tools in the check gate. Both numbers are wrong. |
| **CLAUDE.md stale** | Also claims 72 tools. |

---

## Top 5 Quick Wins

### 1. Fix stale version/header numbers (5 minutes)
Update `tools-mcp-server.py` line 4 (`"79 tools"` → `"124 tools"`), `AGENTS.md`, `CLAUDE.md`, and `tool_router.py` to reflect actual counts.

### 2. Merge the 5 memory search tools into 2 (2 hours)
Collapse `read_memory_search` (BM25) and `read_memory_hybrid_search` (BM25 + vector) into one tool with an optional `mode` parameter. Remove `read_memory_vector_search` (requires embeddings infrastructure that doesn't exist) and `read_memory_reranked_search` (requires cross-encoder). Keep `read_memory_synthesize` as a separate tool since it returns narrative synthesis, not raw results. **Saves 3 tool definitions.**

### 3. Merge sensory URL readers (1 hour)
Collapse `read_sensory_browse`, `read_sensory_scrape`, and `read_sensory_extract_article` into a single `read_sensory_fetch` tool with `mode` parameter (options: text, html, markdown, article, links, tables, json). **Saves 2 tool definitions, eliminates duplicate code paths.**

### 4. Merge sim_mech fatigue pair (30 minutes)
Merge `read_sim_mech_fatigue_sn` and `read_sim_mech_fatigue_cycles` into one `read_sim_mech_fatigue` tool with a `solve_for` parameter (`"stress"` or `"cycles"`). Also merge buckling pair and MOI pair. **Saves 3 tool definitions.**

### 5. Remove or disable undispatched modules (1 hour)
Either wire `cad-module/` and `electrical-module/` into the dispatch chain, or add a `# TODO` comment and remove them from the repo until they're ready. Dead code confuses contributors and inflates the perceived footprint. **Saves 6 undispatched files (468+ lines).**

---

## Summary

This project has **124 tools** where it advertises 68–79. Only **8 tools (6.5%)** serve the project's core purpose of memory management. The remaining **93.5%** is scope creep — general-purpose agent skills (coder, devops, gamedev, audio, art, lit, sensory, pedagogy) and engineering formula calculators (mechanics, FEA, CFD, math) that should be external MCP servers.

The module dispatch is well-structured (no zombie tools), but the codebase is top-heavy with dead directories (`cad-module/`, `electrical-module/`), stale documentation, and a tool router that's missing 33% of its entries.

**Target architecture:** Strip to ~40 core tools, externalize ~78 non-core tools to independent MCP servers, merge the redundancies down by ~13. This would reduce the codebase by ~60% while improving focus and maintainability.
