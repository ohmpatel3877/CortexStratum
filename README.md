# CortexStratum

**Persistent memory infrastructure for AI coding agents.** A 159-tool MCP server giving OpenCode, Claude Code, and Cursor agents cross-session memory, cognitive pipelines, engineering simulation, and Wolfram-class mathematics — all offline, zero API keys, pure Python stdlib core.

<p align="center">
  <img src="https://img.shields.io/badge/Tools-159-blue?style=for-the-badge" alt="Tools"/>
  <img src="https://img.shields.io/badge/Memory-SQLite%20%2B%20FTS5-blue?style=for-the-badge" alt="Memory"/>
  <img src="https://img.shields.io/badge/Local-Pure%20Python%2C%20Zero%20GPU-brightgreen?style=for-the-badge" alt="Local"/>
  <img src="https://img.shields.io/badge/Zero%20API%20Keys-3776AB?style=for-the-badge" alt="Zero API Keys"/>
</p>

Zero cloud dependencies. Zero GPU. Zero API keys. Pure Python stdlib core.

> **Honest Engineering** — This README calls out limitations and constraints alongside features. Every tool has documented edges; knowing them saves debugging time.

### Hard Constraints
| Constraint | Implication |
|:---|---:|
| **Single-threaded stdio** | One JSON-RPC request at a time. No concurrent tool execution. |
| **No authentication** | No users, roles, or API keys. Any process reaching stdin calls any tool. |
| **No encryption at rest** | Memory, registries, and logs are plain files. |
| **No web UI** | MCP protocol only — no dashboard, REST API, or graphical interface. |
| **No hot-reload** | Module code loaded once; changes require server restart. |
| **Single machine** | No clustering, failover, or shared state across processes. |
| **No plugin system** | Adding a tool requires editing `tools-mcp-server.py` and wiring dispatch. |

---

## About

CortexStratum exists because AI agents deserve better than amnesia.

Every session starts fresh. Agents don't remember yesterday's bugs, the architecture decisions they made last week, or the fix they already tried three times. CortexStratum fixes that. It's an **MCP server** that layers persistent memory, structured cognition, and numerical computation onto any LLM-powered coding agent — without a single cloud call, API key, or GPU.

**The problem:** LLM agents are stateless by design. They have no hippocampus, no prefrontal cortex, no ability to learn from past mistakes. Every conversation is Groundhog Day.

**The solution:** A 159-tool digital nervous system that runs locally, covering everything from cross-session error tracking (learn from past debugging) to Wolfram-class mathematics (solve `Ax = b` with full LaTeX derivation) to engineering-grade CFD (pipe flow via Darcy-Weisbach with Colebrook friction). No cloud. No API keys. Pure Python stdlib.

**Who it's for:**
- **Agent developers** who want their agents to actually remember things — error signatures, decisions, preferences, commitments
- **Engineers** who need CFD, FEA, or mechanical analysis without licensing MATLAB or Ansys
- **Mathematicians and scientists** who want quick numerical computation — matrix solve, FFT, root finding, integration — with LaTeX-formatted output, without firing up a CAS
- **OpenCode / Claude Code / Cursor users** who want scope management, behavioral guardrails, and prompt decomposition built into their agent

**What it's not:**
- A Wolfram Alpha or MATLAB replacement — the math engine is stdlib-only, covering the 80% use case, but won't handle symbolic integration or sparse matrices
- A cloud service — everything runs on your machine, zero telemetry, zero API keys
- A vector database — memory primarily uses BM25+FTS5; vector search is optional and needs extra dependencies
- A security boundary — no auth, no encryption, no sandboxing ([see constraints](#hard-constraints))

### Version
**0.5.0** — 159 tools across 18 engine modules, 4 simulation engines, and 14 skills.  
Full changelog in [`CHANGELOG.md`](CHANGELOG.md).

---

## Cortical Architecture — A Brain-Inspired Design

*CortexStratum* maps modules to mammalian brain circuits — each engine mimics a cortical pathway:

| Engine / Module | Cortical Analog | Function |
|:---|---:|:---|
| **Trace System** (xtrace, dtrace) | **Anterior Cingulate Cortex** — error detection, conflict monitoring | Logs mistakes, recognizes recurring error signatures, prevents repeated debugging |
| **Skill Router** | **Thalamus** — sensory relay, routing | Examines queries, classifies intent, dispatches to correct module — the central switchboard |
| **Goal Registry** | **Prefrontal Cortex** — executive control, planning | Maintains goal hierarchy, decomposes tasks, detects scope drift |
| **NE-Memory** (SQLite+FTS5 + vectors) | **Hippocampus** — episodic memory, consolidation | Stores cross-session learnings; FTS5 for fast pattern completion, vector search for semantic association |
| **Commitment Checker** | **Orbitofrontal Cortex** — value judgment, promise-keeping | Verifies earlier commitments are honored — cross-session promise tracker |
| **Verifier Middleware** | **Cerebellum** — fine motor correction, coordination | Detects behavioral drift mid-execution, renudges agent back on course |
| **Focus Module** | **Dorsolateral Prefrontal Cortex** — working memory, attention | Prevents scope creep, decomposes convoluted prompts, maintains task hierarchy |
| **Sensory Module** | **Sensory Cortex** — multi-modal perception | Web browsing, screenshots, PDF extraction, OCR, RSS — digital senses |
| **Audio Module** | **Auditory Cortex** (superior temporal gyrus) | WAV analysis, waveform visualization, FFT frequency analysis, music theory |
| **Art Module** | **Visual Cortex** (V1–V5) — pattern, color, form | SVG generation, color themes, palette extraction, design concepts |
| **Coder Module** | **Broca's Area / Wernicke's Area** — language production & comprehension | Code analysis (12 languages), framework scaffolding, review, debugging, conversion |
| **Literature Module** | **Angular Gyrus** — reading, concept binding | Text analysis (Flesch-Kincaid), concept extraction, study guides |
| **CFD Engine** | **Parietal Lobe (spatial reasoning)** | Pipe flow (Darcy-Weisbach, Colebrook), boundary layer, drag, Bernoulli solver, pump sizing |
| **FEA Engine** | **Parietal Lobe (numerical computation)** | Beam stiffness matrix, truss elements, modal analysis, heat conduction, stress recovery |
| **Mechanics Engine** | **Parietal Lobe (applied physics)** | Beam stress/shear/deflection, column buckling (Euler+Johnson), fatigue (S-N/Goodman/Miner), fasteners |
| **Math Engine** | **Parietal Lobe (symbolic mathematics)** | 19 Wolfram-class tools: linear algebra, calculus, FFT, root finding, statistics, complex numbers, number theory, unit conversion, ODE solving |
| **Mutation Module** | **Motor Cortex** — action planning & execution | Plans file/state changes, audits before executing |
| **Compaction Module** | **Default Mode Network** — reflection, summarization | Condenses verbose context — active during "idle" compaction cycles |
| **Plumber Module** | **Corpus Callosum** — inter-hemisphere communication | Inspects sockets, traces cross-module handoffs, checkpoints state between pipelines |
| **Pedagogy Module** | **Medial Prefrontal Cortex** — theory of mind, social adaptation | Assesses user understanding, adjusts explanation depth |
| **Hooks System** | **Insula** — interoception, internal state | Monitors session lifecycle (start, observe, end) |
| **Consolidation Daemon** | **Hippocampal Replay** — offline memory consolidation | Replays and links related memories during idle cycles |
| **Audit System** | **Episodic Buffer** — short-term action cache | Checkpoints recent mutations for undo |

### Where the Brain Still Wins

| Limit | Brain Advantage | CortexStratum Reality |
|:---|---:|:---|
| **Power efficiency** | Runs on ~20W for a lifetime | A single LLM inference call burns more energy than a day of thinking |
| **Parallelism** | 86 billion neurons firing simultaneously | Sequential JSON-RPC — one tool call at a time |
| **Neuroplasticity** | Constant rewiring — damaged regions reroute functions | Static module graph; crash kills pathway until restart |
| **One-shot learning** | Single burn teaches never to touch a hot stove | Needs multiple exposures for high FTS5 ranking |
| **Forgetting** | Adaptive pruning (Ebbinghaus curve) | Remembers everything equally until consolidation triggered |
| **Emotional weighting** | Emotion as relevance heuristic | All memories equally important; no salience tagging |
| **Context horizon** | A lifetime of integrated experience | Session-scoped; cross-session persistence requires explicit writes |
| **Self-healing** | Neurogenesis, collateral sprouting | Module crash = dead module until process restart |
| **Sleep consolidation** | Automatic daily hippocampal replay | Manual, on-demand (`write_memory_consolidate`) |

---

## Usage Scenarios

### 1. Focus & Scope Management

```python
# A convoluted prompt arrives — decompose it
read_focus_decompose(prompt_text="Build an API, also add a dashboard, 
  and can you make a mobile app too? Oh and fix the database migration")
# → {"tasks": [{"id": 1, "category": "backend", "description": "Build API"},
# {"id": 2, "category": "frontend", "description": "Add dashboard"},
# {"id": 3, "category": "mobile", "description": "Make mobile app"},
# {"id": 4, "category": "database", "description": "Fix migration"}],
# "total_tasks": 4}

# Prioritize them
read_focus_prioritize(tasks=[...])
# → {"ordered_plan": [4, 1, 2, 3], "rationale": "Migration blocks API, API blocks dashboard"}

# Check for scope creep mid-session
read_focus_scope_check(input_text="Actually let's rewrite everything in Rust instead")
# → {"classification": "scope_creep", "nudge": "That's a new project — store in Global Memory?"}

# Store an off-task idea for later
write_focus_store_global(project="rust-rewrite", task="Evaluate Rust for backend")
```

### 2. Context Compaction

```python
# Check token velocity (how fast context is growing)
read_compact_token_velocity()
# → {"velocity_5min": 12, "spike_detected": true, "recommendation": "compact now"}

# Condense verbose output into a summary
read_compact_synthesize(content="[300 lines of build logs...]")
# → {"summary": "Build failed: ModuleNotFound in 3 files.\nFixed: npm install react-dom",
# "compression_ratio": 0.04, "protected_blocks": 2}

# Execute full compaction cycle
write_compact_execute(content="[session content...]")
# → {"status": "compacted", "compression_ratio": 0.12}
```

> **Compaction limits:** Compression is **extractive** — scores sentences and keeps top ones. Does NOT generate new summaries. Important details can be silently dropped. Token velocity detection assumes steady prompt/response flow; bursty workloads trigger false positives.

### 3. Engineering Simulation

```python
# Pipe flow pressure drop (Darcy-Weisbach + Colebrook friction)
read_sim_cfd_pipe(rho=1000, mu=0.001, v=2.5, D=0.1, L=50, roughness=0.00015)
# → {"pressure_drop_Pa": 42500, "Reynolds_number": 250000, "flow_regime": "turbulent", ...}

# Bernoulli equation solver (solve for any one unknown)
read_sim_cfd_bernoulli(P1=200000, v1=1.5, h1=10, P2=150000, v2=None, h2=12, rho=1000)
# → {"unknown": "v2", "value": 3.27, "units": "m/s", ...}

# Beam stiffness matrix (Euler-Bernoulli 4x4)
read_sim_fea_beam(E=200e9, I=8.33e-6, L=2.0)
# → {"stiffness_matrix": [[...]], "dof": 4, "latex": "K = EI/L³ [matrix]", ...}

# Matrix solve with full LaTeX derivation
read_sim_math_matrix_solve(A=[[3,1],[1,2]], b=[5,5])
# → {"solution": [1.0, 2.0], "latex": "\\begin{cases}3x₁ + 1x₂ = 5\\\\...", "dimension": 2}

# FFT — radix-2 Cooley-Tukey
read_sim_math_fft(samples=[1.0, 0.0, 1.0, 0.0, 0.5, 0.5, 0.0, 0.0])
# → {"fft_magnitudes": [...], "bins": 4, "method": "Radix-2 Cooley-Tukey FFT"}

# Numerical integration (Simpson's rule)
read_sim_math_integrate(expr="math.sin(x)", a=0, b=3.14159, method="simpson")
# → {"integral": 2.0, "steps": 100, "method": "simpson", "latex": "\\int_0^{3.14} sin(x) dx ≈ 2.0"}

# Root finding (Newton-Raphson)
read_sim_math_root(expr="x**2 - 2", method="newton", guess=1.5)
# → {"root": 1.41421356, "iterations": 5, "method": "Newton-Raphson"}

# Prime factorization
read_sim_math_factor(n=123456)
# → {"factors": [2, 2, 2, 2, 2, 2, 3, 643], "latex": "123456 = 2 × 2 × 2 × 2 × 2 × 2 × 3 × 643"}
```

### 4. Mathematics Engine (Wolfram-class)

The math engine provides 19 tools covering the full computational mathematics spectrum:

| Domain | Tools | Method |
|--------|-------|--------|
| **Linear Algebra** | `matrix_solve`, `determinant`, `inverse`, `eigenvalue` | Gaussian elimination, LU decomposition, power iteration |
| **Calculus** | `derivative`, `integrate`, `taylor` | Central difference, Simpson's rule, forward difference expansion |
| **Root Finding** | `root` | Newton-Raphson, bisection, secant (auto-selectable) |
| **Fourier** | `fft` | Radix-2 Cooley-Tukey (recursive, pads to power of 2) |
| **Statistics** | `stats`, `regression` | Descriptive stats, least-squares linear regression with R² |
| **Complex Numbers** | `complex` | Add/sub/mul/div/pow, polar/rectangular conversion |
| **Number Theory** | `factor`, `gcdiv` | Trial division, Euclidean algorithm |
| **Polynomials** | `polynomial` | Horner's method evaluation |
| **Unit Conversion** | `convert` | SI↔imperial, temperature, pressure — 16 conversion types |
| **ODEs** | `ode` | Runge-Kutta 4th order, Euler — string-parsed derivatives |
| **LaTeX** | `latex` | Template-based derivation step generation |
| **Plotting** | `plot` | ASCII line plot from x/y data |

### 5. Code Analysis & Review

```python
# Analyze code for issues
read_coder_analyze_code(code="def add(a,b): return a+b", language="python")
# → {"complexity": "low", "issues": [], "suggestions": ["Add type hints"]}

# Deep review across multiple dimensions
read_coder_review(code="...", language="python", focus="security")
# → {"vulnerabilities": 2, "severity": "medium", "fixes": ["Use parameterized queries"]}

# Debug an error with full context
read_coder_debug(error="TypeError: unsupported operand", code_context="...", language="python")
# → {"root_cause": "str + int concatenation", "fix": "Cast to str(): str(value)"}
```

> **Coder limits:** Analysis is **regex/heuristic-based** — it does NOT parse code into ASTs. Deep structural issues (type mismatches across files, race conditions) are invisible. Debug tool doesn't execute code — it pattern-matches error messages. Language conversion is literal syntax mapping, not idiomatic.

### 6. Web Browsing & Data Extraction

```python
# Fetch a URL as clean text
read_sensory_fetch(url="https://example.com", method="browser", mode="text")
# → {"content": "Page text content...", "source": "browser"}

# Extract article content
read_sensory_fetch(url="https://example.com/blog", method="article")
# → {"title": "...", "body": "...", "author": "..."}

# Take a screenshot
read_sensory_screenshot(url="https://example.com")
# → {"screenshot_path": "...", "resolution": "1024x1024"}
```

> **Sensory limits:** Playwright + Firefox is **optional** — browser tools error gracefully if not installed. Screenshots need a display server (X11/Wayland). Some sites block automation. DuckDuckGo search is rate-limited (~1 req/sec). OCR is English-only by default.

### 7. Memory Consolidation & Cross-Pollination

```python
# Check current memory state
read_memory_status()
# → {"memory_count": 85, "storage_backend": "sqlite+fts5", "last_consolidation": "2026-07-18"}

# Search memory with mode selection
read_memory_search(query="how to handle async errors", mode="bm25")
# → {"results": [...], "mode": "bm25", "latency_ms": 0.5}

# Cross-pollinate linked memories
mutate_consolidation_run()
# → {"links_found": 15, "entries_analyzed": 80, "status": "consolidated"}

# View discovered links
read_consolidation_links(limit=5, min_similarity=0.3)
# → {"links": [{"source": "error: module not found", "target": "fix: npm install", "similarity": 0.85}]}
```

> **Memory limits:** BM25 is **keyword-only** — finds documents sharing exact words, not meaning. Searching "how to fix slow queries" won't return "indexing strategy for PostgreSQL" unless terms overlap. Vector search (semantic) fixes this but requires `sentence-transformers` and `numpy`. Consolidation uses **lexical Jaccard overlap** — "fix bug" and "patch bug" are NOT duplicates. Memory grows unbounded without manual consolidation.

---

## For Non-Technical Users

**You only need Docker. Nothing else. No Node.js, no Python, no npm, no pip.**

### Windows
Send your friend this link — it downloads the file, then they double-click it:
```
https://github.com/ohmpatel3877/cortex-stratum/releases/download/v0.6.0-dev/ONE-CLICK.cmd
```
This is a GitHub Release link, so the browser will **download** it (not display it). They double-click the downloaded file and it runs.

### Mac / Linux
Open Terminal, paste this one line, press Enter:
```bash
curl -fsSL https://raw.githubusercontent.com/ohmpatel3877/cortex-stratum/main/docker/setup-opencode-container.sh | bash
```

## Architecture

```
Layer 1: Persistent Memory & Storage
  BM25 search · SQLite session store · Structured registries (errors, decisions, goals)

Layer 2: Cognitive Pipeline
  /compact  → Context compaction, token velocity, state condensation
  /mutate   → Scope assessment, redundancy audit, execution
  /focus    → Scope detection, nudges, prompt decomposition, session pipeline
  /plumber  → Socket inspection, handoff tracing, artifact checkpointing

Layer 3: Engineering Simulation
  /sim-cfd       → Pipe flow, drag, Bernoulli, pump sizing (5 tools)
  /sim-fea       → Beam/truss FEA, modal analysis, heat conduction (5 tools)
  /sim-mechanics → Beam stress, buckling, fatigue, fasteners (7 tools)
  /sim-math      → Wolfram-class math engine (19 tools)

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
  pipeline/dag-coordinator.py → Topological sort, conditional branching, fan-in merge
  phase-verify-full.py  → Cross-phase integration tests
### What they get
A running container with the 159-tool MCP server. Connect it to OpenCode by adding to `opencode.json`:
```json
{
  "mcpServers": {
    "opencode-container-server": {
      "command": "docker",
      "args": ["exec", "-i", "opencode-server", "python3", "/app/scripts/tools-mcp-server.py"]
    }
  }
}
```

---
## Developer Install

### Prerequisites
- **Python** 3.10+
- **Node.js** 18+ (only needed for OpenCode config; the MCP server itself is pure Python)

> **No API keys required.** Everything runs locally.

### Windows (PowerShell 7+)
```powershell
git clone https://github.com/ohmpatel3877/cortex-stratum.git
cd cortex-stratum
pwsh plugin-tools/install-cortex-stratum.ps1
```

### macOS / Linux
```bash
git clone https://github.com/ohmpatel3877/cortex-stratum.git
cd cortex-stratum
bash plugin-tools/install-cortex-stratum.sh
```

### Docker
```bash
docker compose up -d
```

The installer will:
1.  Validate Python 3.10+
2.  Install Python dependencies (stdlib only for core; optional extras via `requirements-full.txt`)
3.  Register the MCP server in `opencode.json`
4.  Link skills to `~/.config/opencode/skills/`
5.  Run verification checks

> **Note:** The installer may prompt for a `MEM0_API_KEY`. This is a legacy template step — you can skip it. All memory features work fully offline without any API key.

---
## MCP Server — 159 Tools

The MCP server runs on the standard JSON-RPC protocol over stdio. OpenCode and Claude Code auto-discover it from `opencode.json`. Tools use a consistent naming convention: `read_*` (safe queries), `write_*` (state mutations), `mutate_*` (destructive operations — all accept `dry_run=true`).

### Core Infrastructure (13 tools)

| Tool | Purpose |
|------|---------|
| `write_xtrace_log_error` | Log error occurrences for cross-session tracking |
| `read_xtrace_search` | Search the error registry by signature |
| `read_xtrace_status` | Error tracking summary statistics |
| `write_dtrace_add` | Record architectural decisions with context |
| `read_dtrace_search` | Search the decision registry |
| `read_skill_router_match` | Match tasks to skills by intent triggers |
| `read_tools_suggest` | Suggest MCP tools for a given task |
| `write_goal_registry_init` | Initialize a tracked goal |
| `write_goal_registry_add_subgoal` | Decompose goals into sub-goals |
| `read_goal_registry_status` | Current goal stack state |
| `read_goal_registry_check_alignment` | Verify current action aligns with goal |
| `read_commitment_checker_list` | List pending session commitments |
| `mutate_commitment_verify` | Mark commitments as verified |

### Simulation Engine (36 tools)

| Engine | Tools | Description |
|--------|-------|-------------|
| **CFD** | 5 | `read_sim_cfd_pipe`, `read_sim_cfd_boundary`, `read_sim_cfd_drag`, `read_sim_cfd_bernoulli`, `read_sim_cfd_pump` |
| **FEA** | 5 | `read_sim_fea_beam`, `read_sim_fea_truss`, `read_sim_fea_modal`, `read_sim_fea_heat`, `read_sim_fea_stress_recovery` |
| **Mechanics** | 7 | `read_sim_mech_stress`, `read_sim_mech_shear`, `read_sim_mech_deflection`, `read_sim_mech_moi`, `read_sim_mech_buckle`, `read_sim_mech_fatigue`, `read_sim_mech_fastener` |
| **Math** | 19 | `read_sim_math_matrix_solve`, `read_sim_math_determinant`, `read_sim_math_inverse`, `read_sim_math_eigenvalue`, `read_sim_math_derivative`, `read_sim_math_integrate`, `read_sim_math_taylor`, `read_sim_math_root`, `read_sim_math_stats`, `read_sim_math_regression`, `read_sim_math_fft`, `read_sim_math_complex`, `read_sim_math_factor`, `read_sim_math_gcdiv`, `read_sim_math_polynomial`, `read_sim_math_convert`, `read_sim_math_ode`, `read_sim_math_latex`, `read_sim_math_plot` |

### Coder (7 tools)

`read_coder_analyze_code`, `read_coder_generate_framework`, `read_coder_debug`, `read_coder_review`, `read_coder_explain`, `read_coder_convert`, `read_coder_architecture`

Supports: Python, JavaScript, TypeScript, Rust, Go, Java, C#, C++, Swift, Kotlin, Ruby, PHP

### Sensory — Web & File I/O (11 tools)

`read_sensory_fetch` (merged browse+scrape+article), `read_sensory_screenshot`, `mutate_sensory_interact`, `read_sensory_extract_pdf`, `read_sensory_extract_html`, `read_sensory_extract_image`, `read_sensory_api_request`, `read_sensory_fetch_rss`, `read_sensory_read_file`, `read_sensory_search`, `read_sensory_set_browser_type`

Headless Firefox via Playwright. DuckDuckGo search — no API key required.

### Cognitive Pipeline (20 tools)

**Compact**: `read_compact_token_velocity`, `read_compact_synthesize`, `write_compact_execute`, `read_compact_record_tick`  
**Mutation**: `read_mutate_scope`, `read_mutate_audit`, `mutate_execute`  
**Focus**: `read_focus_scope_check`, `read_focus_nudge`, `read_focus_decompose`, `read_focus_prioritize`, `read_focus_pipeline_status`, `write_focus_pipeline_advance`, `read_focus_global`, `write_focus_store_global`, `mutate_focus_learn`  
**Plumber**: `read_plumber_inspect_socket`, `read_plumber_trace_handoff`, `write_plumber_checkpoint`, `read_plumber_checkpoints`

### DevOps & Engineering (8 tools)

`read_devops_container_debug`, `read_devops_permissions_analyze`, `read_devops_compose_generator`, `read_devops_mergerfs_setup`, `read_devops_dockerfile_analyze`, `read_devops_network_troubleshoot`, `read_cad_validate_scad`, `read_cad_beam_stress`

### Audio (7 tools)

`read_audio_analyze_file`, `read_audio_waveform`, `read_audio_frequency_analysis`, `read_audio_music_theory`, `read_audio_generate_tone`, `read_audio_speech_analysis`, `read_audio_convert_guide`

### Game Dev (6 tools)

`read_gamedev_design_analyze`, `read_gamedev_scaffold_project`, `read_gamedev_mechanics_guide`, `read_gamedev_optimization`, `read_gamedev_compare_engines`, `read_gamedev_level_design`

### Art & Literature (7 tools)

**Art**: `read_art_generate_svg`, `read_art_generate_theme`, `read_art_extract_palette`, `read_art_design_concept`  
**Literature**: `read_lit_analyze_text`, `read_lit_extract_concepts`, `read_lit_generate_study_guide`

### Memory & State (5 tools)

`read_memory_search`, `read_memory_synthesize`, `write_memory_add`, `write_memory_consolidate`, `read_memory_status`

### Utility (11 tools)

**Database**: `read_db_query`, `read_db_schema`, `write_db_execute`  
**Data Convert**: `read_convert_csv_to_json`, `read_convert_json_to_csv`, `read_convert_json_to_xml`, `read_convert_xml_to_json`, `read_convert_json_to_yaml`, `read_convert_yaml_to_json`  
**Regex**: `read_regex_test`, `read_regex_explain`

### Verifier, Hooks & Lifecycle (9 tools)

**Verifier**: `read_verifier_status`, `write_verifier_renudge`, `write_verifier_clear_renudge`, `mutate_verify_run`  
**Hooks**: `read_hooks_prefetch`, `write_hooks_observe`, `read_hooks_session_status`, `write_hooks_session_end`  
**Audit**: `mutate_audit_undo`, `read_audit_status`, `read_phase_status`

### DAG, Workstreams & Agents (7 tools)

`read_dag_status`, `write_dag_execute`, `write_dag_resume`, `read_workstream_list`, `read_workstream_status`, `read_skill_list`, `read_agent_list`

---
## Skills

| Skill | File | Description |
|-------|------|-------------|
| **Task Orchestrator** | `skills/task-orchestrator/SKILL.md` | Auto-decompose tasks into parallel subagent workstreams |
| **Security Hardening** | `skills/security-hardening/SKILL.md` | Security audit, CVE detection, encryption hardening |
| **Memory Evaluation** | `skills/memory-evaluation/SKILL.md` | Session-end memory catalog, gap analysis, registration |
| **Parameter Virtualizer** | `skills/parameter-virtualizer/SKILL.md` | Token budget optimization, prompt caching strategies |
| **Speed Optimizer** | `skills/speed-optimizer/SKILL.md` | Performance tuning, latency reduction strategies |
| **Verification Gate** | `skills/verification-before-completion/SKILL.md` | Pre-push verification checklist |
| **Verifier Middleware** | `skills/verifier-middleware/SKILL.md` | Behavioral correction signal engine |

### Skill Router Triggers

The router auto-loads skills based on keywords in your task description:

| Keywords | Skills Loaded |
|----------|--------------|
| `debug`, `error`, `fix`, `broken`, `crash` | `troubleshooting-master`, `error-triage` |
| `test`, `tdd`, `spec`, `coverage` | `test-driven-development`, `test-patterns` |
| `design`, `architecture`, `plan`, `strategy` | `brainstorm`, `adr-write` |
| `electron`, `ipc`, `preload`, `contextbridge` | `electron-desktop-architecture` |
| `security`, `cve`, `harden`, `encrypt`, `xss` | `security-hardening` |
| `memory`, `mem0`, `remember`, `recall` | `mem0-search`, `mem0-remember` |
| `art`, `svg`, `theme`, `palette`, `design` | `art-module` |
| `literature`, `philosophy`, `textbook`, `essay` | `literature-module` |
| `browser`, `scrape`, `crawl`, `playwright` | `browser-automation`, `playwright-automation` |
| *Default* | `concise-filter`, `task-orchestrator` |

---

## Usage Examples

### Quickstart: Track an Error Across Sessions
```
# Agent A encounters an error
→ xtrace_log_error("ModuleNotFoundError: No module named 'xyz'")

# Agent B (next session) searches before debugging
→ xtrace_search("ModuleNotFoundError")
  ← "Already logged. Root cause: missing pip install. Fix: pip install xyz"
```

### Record an Architecture Decision
```
→ dtrace_add(
    title="Choose PostgreSQL over MySQL",
    context="Need JSONB, array columns, and CTEs for the analytics module",
    decision="PostgreSQL 16",
    alternatives=["MySQL 8", "SQLite"],
    consequences="Slightly higher ops overhead, better query capability"
  )
```

### Auto-Route a Task to Skills
```
# User says: "debug the Samba container networking issue"
# Skill Router auto-loads: troubleshooting-master, devops_network_troubleshoot
# No manual skill selection needed
```

### Decompose a Complex Task
```
# Task Orchestrator scores complexity, splits into parallel workstreams:
# [Agent 1: Frontend] React component redesign
# [Agent 2: Backend] API endpoint rewrite
# [Agent 3: DB] Schema migration
# Merge results when all complete
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

Add to your `opencode.json`:

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

Or for Docker deployments:

```json
{
  "mcpServers": {
    "CortexStratum": {
      "command": "docker",
      "args": ["exec", "-i", "opencode-server", "python3", "/app/scripts/tools-mcp-server.py"]
    }
  }
}
```

---

## Scripts

All CLI scripts live in `scripts/`:

| Script | Language | Purpose |
|--------|----------|---------|
| `tools-mcp-server.py` | Python | 159-tool MCP server (main entry point) |
| `task-analyzer.py` | Python | Complexity scoring for task orchestration |
| `task-orchestrator.py` | Python | DAG-based multi-agent pipeline execution |
| `verifier_middleware.py` | Python | Behavioral correction signal engine |
| `memory_search.py` | Python | SQLite+FTS5 memory engine with synonym expansion |
| `identity-manager.py` | Python | Agent identity persistence and evolution |
| `sandbox-manager.py` | Python | Isolated code execution environment |
| `pipeline/dag-coordinator.py` | Python | Multi-phase state machine orchestration |
| `benchmark/benchmark-harness.py` | Python | Performance benchmarking suite |
| `ci/validate-json.py` | Python | CI: validate JSON config files |
| `ci/validate-skill-router.py` | Python | CI: check skill router references |
| `ci/test-memory-engine.py` | Python | CI: memory engine integration tests |
| `consolidate.js` | Node.js | mem0 dream consolidation trigger |
| Engine modules (`engine/`) | Python | Art, audio, coder, devops, game-dev, literature, sensory, ... |
| Pipeline scripts (`scripts/pipeline/`) | Python | focus-module, consolidation-daemon, dag-coordinator, state_file_manager |
| Benchmark scripts (`scripts/benchmark/`) | Python | blind-benchmark, terminal-bench, run-eval-harness, ... |

---
## Customization

### Memory Categories

Edit `.mem0.md` to adjust retention policies or add categories:

```yaml
architecture_decisions: null       # Keep forever
anti_patterns: 365                 # 1 year
session_state: 90                  # 3 months
```

### Skill Router

Edit `skills/skill-router.json` to add trigger rules:

```json
{
  "mcpServers": {
    "CortexStratum": {
      "command": "python",
      "args": ["scripts/tools-mcp-server.py"]
    }
  }
  "triggers": ["kubernetes", "k8s", "helm", "pod"],
  "skills": ["kubernetes-operations-k8s-manifest-generator"],
  "priority": 10
}
```

### MCP Server Config

Edit `package.json` → `mcpServers` or `opencode.json` to change server args:

```json
"cortex-stratum": {
  "command": "python",
  "args": ["scripts/tools-mcp-server.py"]
}
```

---
## Tool Inventory

159 tools across 30+ domains:

| Domain | Tools | Category |
|--------|-------|----------|
| Memory (SQLite+FTS5) | 5 | Core |
| Trace (error/decision registries) | 5 | Core |
| Lifecycle Hooks | 4 | Core |
| Verifier Middleware | 4 | Core |
| Goal Registry | 4 | Core |
| Commitment Checker | 2 | Core |
| Audit / Phase Status | 3 | Core |
| Compact Phase | 4 | Cognitive Pipeline |
| Mutation Phase | 3 | Cognitive Pipeline |
| Focus Module | 9 | Cognitive Pipeline |
| Plumber Module | 4 | Cognitive Pipeline |
| Pedagogy | 3 | Cognitive Pipeline |
| Consolidation | 2 | Cognitive Pipeline |
| CAD (3D printing) | 2 | Engineering |
| Electrical (circuits) | 2 | Engineering |
| **CFD** (pipe, boundary, drag, Bernoulli, pump) | **5** | **Simulation** |
| **FEA** (beam, truss, modal, heat, stress) | **5** | **Simulation** |
| **Mechanics** (stress, shear, deflection, buckle, fatigue) | **7** | **Simulation** |
| **Math Engine** (matrix, calculus, FFT, stats, root, ODE...) | **19** | **Simulation** |
| Sensory (web) | 13 | Agent Skills |
| Coder | 7 | Agent Skills |
| DevOps | 6 | Agent Skills |
| Game Dev | 6 | Agent Skills |
| Audio | 7 | Agent Skills |
| Art/SVG | 4 | Agent Skills |
| Literature | 3 | Agent Skills |
| Data Convert | 6 | Utility |
| Database | 3 | Utility |
| Regex | 2 | Utility |
| Skill Router / Tool Suggest | 2 | Infrastructure |
| DAG / Workstreams | 4 | Orchestration |
| Skills / Agents | 2 | Introspection |

---
## Project Structure

```
CortexStratum/
  engine/                      # Domain-specific engines
    cad-module/                # 3D printing (OpenSCAD)
    electrical-module/         # Circuit design
    art-module.py              # SVG generation
    audio-module.py            # Audio processing
    coder-module.py            # Code analysis
    compact-module.py          # Context compaction
    devops-module.py           # Container/network ops
    game-dev-module.py         # Game development
    literature-module.py       # Text analysis
    mutation-module.py         # Algorithmic mutation
    pedagogy-module.py         # Teaching adaptation
    plumber-module.py          # Execution pipelines
    sensory-module.py          # Web browsing (Playwright)
    utility-module.py          # Shared helpers (format conversion, regex, DB)
    sim-cfd-module.py          # CFD simulation (pipe, drag, Bernoulli)
    sim-fea-module.py          # FEA simulation (beam, truss, modal, heat)
    sim-mechanics-module.py    # Mechanics (stress, buckling, fatigue)
    sim-math-module.py         # Wolfram-class math engine (19 tools)
  scripts/                     # Utility scripts & pipeline orchestration
    tools-mcp-server.py        # MCP server entrypoint (159 tools)
    memory_search.py           # SQLite+FTS5 memory engine
    hooks.py                   # Lifecycle hooks
    pipeline/                  # Pipeline orchestration
    benchmark/                 # Performance benchmarks
    archive/                   # Deprecated scripts
  plugins/                     # External platform plugins
    hermes-plugin/             # Agent MemoryProvider
  future/                      # Spec-first development blueprints
  docs/                        # Guides, audits, architecture reviews
  data/                        # Persistent storage (JSON + SQLite)
  install-tools/               # Installer scripts
  docker/                      # Docker configs
  opencode.json                # Project config
```

---
## Comparisons

| Feature | CortexStratum | Basic MCP memory servers |
|---------|---------------|--------------------------|
| Total tools | **159** | 5-15 |
| Permission model | 3-tier (read/write/mutate) | None |
| Search | BM25 + vector + reranker | Naive substring |
| Simulation engines | CFD, FEA, Mechanics, Wolfram-class Math (36 tools) | None |
| Cognitive pipeline | Compact, mutate, focus, plumber | None |
| Session lifecycle | /help → context → execute → /end | None |
| Scope management | Prompt decomposition, prioritizer | None |
| Orchestration | DAG coordinator, auto-parallelization | None |
| Dry-run preview | All write/mutate tools | None |
| Checkpoint/undo | All mutations | None |
| GPU required | Zero | Varies |
| API keys | Zero | Often required |
