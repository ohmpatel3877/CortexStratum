# Skill: task-orchestrator

# Task Orchestrator — Automatic Subagent Routing

Automatically evaluates every incoming task for complexity, decomposes large tasks into parallel workstreams, and spawns subagents without requiring manual prompt engineering.

## How It Works

On every task, evaluate complexity BEFORE executing. Use the complexity matrix below.

### Complexity Matrix

| Factor | Low (0-2) | Medium (3-5) | High (6-10) |
|---|---|---|---|
| Files affected | 1 file | 2-5 files | 6+ files |
| Tech domains | 1 (e.g., just frontend) | 2-3 (frontend + backend) | 4+ (full stack + infra + DB) |
| Risk keywords | — | "refactor", "update" | "security", "auth", "payment", "migration", "data-loss" |
| Independence | Single sequential path | Some parallelizable work | 3+ independent workstreams |
| Domain novelty | Done before same stack | Done before similar | New stack or domain |
| Business logic | Cosmetic/read-only | Simple logic | Complex branching/state |

### Scoring
Sum the scores from each factor. If score >= 12, the task MUST be parallelized with subagents.

### Routing Decisions

| Score | Mode | Action |
|---|---|---|
| 0-5 | 🔵 **Direct** | Execute in current context. No subagents needed. |
| 6-11 | 🟡 **Split** | Identify independent workstreams. Use 2-3 parallel subagents for those, keep sequential parts inline. |
| 12-17 | 🟠 **Orchestrate** | Full orchestration: decompose into workstreams, spawn 3-5 parallel subagents, merge results. |
| 18+ | 🔴 **Pipeline** | Multi-phase: discovery → design → parallel build → integration → verify. Use serial phases with parallel subagents within each. |

### Orchestration Protocol

When a task scores ≥ 12 (or at least one High factor), follow this protocol:

1. **ANALYZE**: Run the analyzer: `python scripts/task-analyzer.py --task "<task description>"`
2. **DECOMPOSE**: Break the task into independent workstreams (max one per file)
3. **SPAWN**: Launch subagents in parallel using the `task` tool with `subagent_type="general"`
4. **MONITOR**: Track each agent's progress. If one stalls (no output after a while), diagnose and retry.
5. **MERGE**: When all subagents complete, merge their outputs, resolve conflicts, verify consistency.

### Auto-Detect Parallelizable Patterns

These patterns are ALWAYS candidates for parallel execution (score them high):
- Multi-file refactoring (one agent per file/family)
- Full-stack features (frontend agent + backend agent + DB agent)
- Documentation + Implementation (doc agent writes docs, build agent implements)
- Debugging + Fixing (scout agent traces, build agent fixes)
- Audit + Remediation (audit agent finds issues, fix agent resolves)

### Integration

This skill should be loaded at session start via the skill-router or as a default skill.
