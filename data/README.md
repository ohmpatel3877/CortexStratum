# `/data/` — CortexStratum Runtime Data

This directory holds all persistent runtime state for the CortexStratum MCP server. Files are JSON unless noted.

## Convention

| Scope | Location | Pattern |
|-------|----------|---------|
| Core registries | `data/*.json` | Always at root — loaded by dashboard and MCP tools |
| Archive | `data/archive/` | Deprecated/orphan files, kept for reference |
| Benchmark | `data/benchmark-archive/` | Historical benchmark outputs |
| DAG | `data/dag-definitions/`, `data/dag-schemas/`, `data/dag-traces/` | Pipeline execution definitions, schemas, and traces |
| Session logs | `data/session-logs/` | Raw session traces (JSON/JSONL) |
| Audit | `data/audit/` | Undo log and audit trail |
| Condensed | `data/condensed/` | Context compaction artifacts |

## Core Registries (root `data/`)

| File | Purpose | Written by |
|------|---------|------------|
| `tool-inventory.json` | Authoritative list of all MCP tools with permissions | Manual / `tools-mcp-server.py` |
| `error-registry.json` | Error trace log with status, frequency, root cause | `trace.py` |
| `decision-registry.json` | Architecture decision record log | `decision-trace.ps1` / manual |
| `commitment-registry.json` | Active commitments with verification sessions | Manual |
| `goal-registry.json` | Current session goal and sub-goals | `focus-module.py` |
| `memory.db` | SQLite+FTS5 memory store (documents + full-text index) | `memory_search.py` |
| `synonyms.json` | Synonym map for BM25 query expansion | Manual |
| `session-pipeline.json` | Session phase state (help → context → work → end) | `focus-module.py` |
| `session-learning.json` | Per-session learning: scope creep, context switches, recommendations | `focus-module.py` |
| `session-overview.json` | Session summary: tool count, new tools, bugs fixed, optimizations | Manual |
| `global-projects-memory.json` | Out-of-scope tasks saved for future sessions | `focus-module.py` |
| `compact-sessions.db` | SQLite database for context compaction | `compact-module.py` |
| `compact-velocity.json` | Compaction velocity tracking ticks | `compact-module.py` |
| `pedagogy-profile.json` | Learning depth profile per topic | `pedagogy-module.py` |
| `identity-evolution-log.json` | Identity version history and trait changes | `identity-manager.py` |
| `security-scan-report.json` | Static analysis security findings | `security-scan.py` |
| `sandbox-log.json` | Sandbox execution history | `sandbox-manager.py` |
| `doc-index.json` | Script documentation index (functions, classes) | `doc-generator.py` |

## Cleanup Roadmap

1. **Benchmark files** (`benchmark-results.json`, `blind-*.json`, etc.) → move to `benchmark-archive/` once stable
2. **Session logs** (`data/session-logs/*`) → could be rotated to `docs/session-archive/`
3. **DAG directories** → could merge `dag-definitions/`, `dag-schemas/`, `dag-traces/` into one `dag/` directory
4. **Duplicate PS1/Python** → `.ps1` files that write to `data/` should be consolidated into their Python equivalents
