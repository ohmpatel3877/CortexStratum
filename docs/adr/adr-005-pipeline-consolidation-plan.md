# ADR-005: Pipeline & Script Consolidation Plan

**Status:** Proposed  
**Date:** 2026-07-20

## Context

The `scripts/` directory has grown to 70+ files with significant overlap in functionality. Multiple pipeline/phase scripts, consolidation daemons (Python + PS1 + JS), and verification scripts operate independently with no unified controller. The `data/` directory had orphan files mixed with active registries.

## Decision

### Phase A: `/data` Cleanup (done)
1. Move ADRs from `data/adr/` to `docs/adr/` — they're documentation, not runtime data
2. Archive orphan files: `provider-signup-guide.md`, `free-provider-template.json`, `dcp-demo-validation.txt`, `orchestration-research.json`
3. Create `data/README.md` with full directory map and cleanup roadmap
4. Keep all active data files at `data/` root — changing paths breaks 20+ scripts

### Phase B: Pipeline Unification (next)
1. **DAG Coordinator** (`dag-coordinator.py`) is the topological execution engine — keep it
2. **Focus Module** (`focus-module.py`) is the session lifecycle manager — keep it
3. **Phase scripts** (`phase-a-merge.py`, `phase-verify.py`, `phase-verify-full.py`) are one-shot migration tools — move to `scripts/archive/` after documenting purpose
4. **Consolidation daemons**: keep `consolidation-daemon.py` (Python), deprecate `ne-consolidation-daemon.ps1` and `consolidate.js`
5. **PS1 → Python dupes**: `check-status.ps1` → use `check-status.py`, `ne-consolidation-daemon.ps1` → use `consolidation-daemon.py`

### Phase C: Script Reorganization (future)
1. Create `scripts/benchmark/` → move 8 benchmark scripts
2. Create `scripts/simulation/` → move 4 sim modules
3. Create `scripts/pipeline/` → move dag-coordinator, focus-module, consolidation-daemon
4. Create `scripts/archive/` → move phase scripts, one-shot tools
5. Merge `sim-cfd-module.py` + `sim-fea-module.py` + `sim-math-module.py` + `sim-mechanics-module.py` into `sim-module.py` with dispatch

## Version & Config Truth

| Artifact | Source of Truth | Current Value |
|----------|----------------|---------------|
| Version | `VERSION` file | 0.5.0 |
| Tool count | `data/tool-inventory.json` | 68 |
| MCP server config | `opencode.json` (root) | v0.5.0 |
| VS Code config | `.opencode/opencode.jsonc` | References root |

## Consequences
- Cleaner `/data` directory with clear boundaries between runtime data, archives, and docs
- Single source of truth for version, config, and tool inventory
- Dashboard now surfaces version, security findings, sandbox usage, identity evolution, and dynamic future specs
- Future `scripts/` reorganization will reduce cognitive load but requires updating references in `tools-mcp-server.py`
