# CortexStratum

**Persistent memory, simulation, and cognitive toolchain for AI agents.**  
135 MCP tools across memory, engineering simulation, focus management, context compaction, and agent orchestration.

<p align="center">
  <img src="https://img.shields.io/badge/Tools-135-blue?style=for-the-badge" alt="Tools"/>
  <img src="https://img.shields.io/badge/Memory-BM25%20%2B%20SQLite-blue?style=for-the-badge" alt="Memory"/>
  <img src="https://img.shields.io/badge/Local-Pure%20Python%2C%20Zero%20GPU-brightgreen?style=for-the-badge" alt="Local"/>
  <img src="https://img.shields.io/badge/Zero%20API%20Keys-3776AB?style=for-the-badge" alt="Zero API Keys"/>
</p>

Zero cloud dependencies. Zero GPU. Zero API keys. Pure Python stdlib core.

---

## Four Scenarios

### Scenario 1: Engineering Simulation

```python
# Beam stress analysis for a 3m steel beam
read_sim_mech_stress(moment=1000, distance_neutral=0.05, I=1.2e-5)
# → {"stress_mpa": 4.17, "formula": "σ = M*y / I"}

# Column buckling check
read_sim_mech_buckle(E=200e9, I=1.2e-5, K=1.0, L=3.0)
# → {"critical_load_kN": 2631.89, "slenderness_ratio": 86.6}

# Pipe flow pressure drop (Darcy-Weisbach)
read_sim_cfd_pipe(rho=1000, v=2.0, D=0.1, mu=1e-3, L=50)
# → {"delta_P_kPa": 8.2, "Reynolds": 200000, "regime": "turbulent"}

# FEA beam element stiffness matrix
read_sim_fea_beam(E=200e9, I=1.2e-5, L=3.0)
# → {"stiffness_matrix": [[4x4 matrix]], "dof": 4}

# Solve Ax = b with LaTeX derivation
read_sim_matrix_solve(A=[[2,1],[1,3]], b=[5,6])
# → {"solution": [1.8, 1.4], "latex": "x = \\begin{bmatrix} 1.8 \\\\ 1.4 \\end{bmatrix}"}
```

### Scenario 2: Focus & Scope Management

```python
# A convoluted prompt arrives — decompose it
read_focus_decompose(prompt_text="Build an API, also add a dashboard, 
  and can you make a mobile app too? Oh and fix the database migration")
# → {"tasks": [
#     {"id": 1, "category": "backend", "description": "Build API"},
#     {"id": 2, "category": "frontend", "description": "Add dashboard"},
#     {"id": 3, "category": "mobile", "description": "Make mobile app"},
#     {"id": 4, "category": "database", "description": "Fix migration"}
#   ], "total_tasks": 4}

# Prioritize them
read_focus_prioritize(tasks=[...])
# → {"ordered_plan": [4, 1, 2, 3], "rationale": "Migration blocks API, API blocks dashboard"}

# Check for scope creep mid-session
read_focus_scope_check(input_text="Actually let's rewrite everything in Rust instead")
# → {"classification": "scope_creep", "nudge": "That's a new project — store in Global Memory?"}

# Store an off-task idea for later
write_focus_store_global(project="rust-rewrite", task="Evaluate Rust for backend")
```

### Scenario 3: Context Compaction

```python
# Check token velocity (how fast context is growing)
read_compact_token_velocity()
# → {"velocity_5min": 12, "spike_detected": true, "recommendation": "compact now"}

# Condense verbose output into a summary
read_compact_synthesize(content="[300 lines of build logs...]")
# → {"summary": "Build failed: ModuleNotFound in 3 files.\nFixed: npm install react-dom",
#     "compression_ratio": 0.04, "protected_blocks": 2}

# Execute full compaction cycle
write_compact_execute(content="[session content...]")
# → {"status": "compacted", "compression_ratio": 0.12}

# Advanced: cross-pollinate memory entries
write_consolidation_run()
# → {"links_found": 15, "entries_analyzed": 80}
```

### Scenario 4: Agent Orchestration

```python
# Analyze task complexity and generate workstream plan
python scripts/task-orchestrator.py --task "Create FEA module and wire it" --plan
# → Workstreams: mod-1 (parallel create) → wire-1 (serial wiring)

# Execute with DAG coordination
python scripts/dag-coordinator.py --dag data/dag-definitions/master-spec-full-build.json --dry-run
# → 3 levels: 6 parallel module nodes → 1 serial wiring → 1 verification

# Auto-detect module pattern (parallel create → serial wire)
python scripts/task-orchestrator.py --task "Create compact and mutation modules" --orchestrate
# → Phase 1 (parallel): mod-1
# → Phase 2 (serial):   wire-1
# → Post-merge: python scripts/phase-verify-full.py
```

---

## Architecture

```
Layer 1: Persistent Memory & Storage
  BM25 search · SQLite session store · Structured registries (errors, decisions, goals)

Layer 2: Cognitive Pipeline
  /compact  → Context compaction, token velocity, state condensation
  /mutate   → Scope assessment, redundancy audit, execution
  /focus    → Scope detection, nudges, prompt decomposition, session pipeline
  /plumber  → Socket inspection, handoff tracing, artifact checkpointing

Layer 3: Simulation Engines
  sim_mech  → Beam stress, column buckling, fatigue (Goodman/Miner), fasteners
  sim_fea   → Beam elements, truss, modal analysis, heat conduction
  sim_cfd   → Pipe flow, boundary layer, drag, Bernoulli
  sim_math  → Matrix solve (Ax=b), ODE (RK4), ASCII plot, LaTeX generation

Layer 4: Agent Skills
  sensory   → Web browsing (Playwright), scraping, PDF/OCR, RSS
  coder     → Analyze, review, debug, convert, scaffold
  devops    → Containers, compose, Samba, network
  gamedev   → Design, scaffold, mechanics, monetization
  audio     → WAV analysis, waveform, frequency, music theory
  art       → SVG, themes, palettes, design concepts
  literature→ Text analysis, concepts, study guides

Layer 5: Orchestration
  task-orchestrator.py  → Module-pattern detection, auto-DAG, parallel subagents
  dag-coordinator.py    → Topological sort, conditional branching, fan-in merge
  phase-verify-full.py  → Cross-phase integration tests
```

---

## Quick Start

### One-Click Install (Windows)

Double-click `ONE-CLICK.cmd` — it downloads Docker, builds the container, and prints your MCP config.

### Manual Install

```bash
git clone https://github.com/ohmpatel3877/CortexStratum.git
cd CortexStratum
python scripts/tools-mcp-server.py
```

Memory works immediately with zero dependencies (stdlib only).  
Optional: `pip install sentence-transformers` for vector search.

### Connect to OpenCode

```json
{
  "mcpServers": {
    "CortexStratum": {
      "command": "python",
      "args": ["scripts/tools-mcp-server.py"]
    }
  }
}
```

---

## Tool Inventory

135 tools across 20 domains:

| Domain | Tools | Category |
|--------|-------|----------|
| Memory (BM25/SQLite) | 8 | Core |
| Trace (error/decision registries) | 5 | Core |
| Lifecycle Hooks | 4 | Core |
| Verifier Middleware | 3 | Core |
| Goal Registry | 4 | Core |
| Commitment Checker | 2 | Core |
| Compact Phase | 5 | Cognitive Pipeline |
| Mutation Phase | 4 | Cognitive Pipeline |
| Focus Module | 9 | Cognitive Pipeline |
| Plumber Module | 4 | Cognitive Pipeline |
| Pedagogy | 3 | Cognitive Pipeline |
| Consolidation | 3 | Cognitive Pipeline |
| Mechanics | 14 | Simulation |
| FEA | 4 | Simulation |
| CFD | 4 | Simulation |
| Math Engine | 4 | Simulation |
| CAD (3D printing) | 2 | Simulation |
| Electrical (circuits) | 2 | Simulation |
| Sensory (web) | 13 | Agent Skills |
| Coder | 7 | Agent Skills |
| DevOps | 7 | Agent Skills |
| Game Dev | 7 | Agent Skills |
| Audio | 7 | Agent Skills |
| Art/SVG | 4 | Agent Skills |
| Literature | 4 | Agent Skills |
| Skill Router / Tool Suggest | 2 | Infrastructure |
| Permission Audit / Undo | 2 | Infrastructure |
| Task Orchestrator | — | Infrastructure |

---

## Project Structure

```
CortexStratum/
  scripts/
    tools-mcp-server.py      # MCP server entrypoint (135 tools)
    memory_search.py          # BM25 + SQLite engine
    compact-module.py         # Context compaction
    mutation-module.py        # Algorithmic mutation
    focus-module.py           # Scope & session management
    plumber-module.py         # Execution pipelines
    sim-mechanics-module.py   # 14 mechanics tools
    sim-fea-module.py         # 4 FEA tools
    sim-cfd-module.py         # 4 CFD tools
    sim-math-module.py        # 4 math tools
    pedagogy-module.py        # Teaching adaptation
    consolidation-daemon.py   # TF-IDF cross-pollination
    sensory-module.py         # Web browsing (Playwright)
    coder-module.py           # Code analysis
    audio-module.py           # Audio processing
    art-module.py             # SVG generation
    literature-module.py      # Text analysis
    devops-module.py          # Container/network ops
    game-dev-module.py        # Game development
    task-orchestrator.py      # Parallel subagent orchestration
    dag-coordinator.py        # DAG execution engine
    phase-verify-full.py      # Cross-phase integration tests
  cad-module/                 # 3D printing (OpenSCAD)
  electrical-module/          # Circuit design
  hermes-plugin/              # Agent MemoryProvider
  data/                       # Persistent storage (JSON + SQLite)
  opencode.json               # Project config
```

---

## Comparisons

| Feature | CortexStratum | Basic MCP memory servers |
|---------|---------------|--------------------------|
| Total tools | **135** | 5-15 |
| Permission model | 3-tier (read/write/mutate) | None |
| Search | BM25 + vector + reranker | Naive substring |
| Simulation engines | Mechanics, FEA, CFD, math | None |
| Cognitive pipeline | Compact, mutate, focus, plumber | None |
| Session lifecycle | /help → context → execute → /end | None |
| Scope management | Prompt decomposition, prioritizer | None |
| Orchestration | DAG coordinator, auto-parallelization | None |
| Dry-run preview | All write/mutate tools | None |
| Checkpoint/undo | All mutations | None |
| GPU required | Zero | Varies |
| API keys | Zero | Often required |
