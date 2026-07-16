# ai-memory-core

**Production memory infrastructure for AI coding agents.** A 68-tool MCP server with permission-gated access — local BM25 memory, cross-session trace system, and 7 multi-modal modules. Zero cloud LLM dependencies.

<p align="center">
  <img src="https://img.shields.io/badge/MCP%20Server-67%20tools-blue?style=for-the-badge" alt="68 MCP Tools"/>
  <img src="https://img.shields.io/badge/Permissions-read%20%2F%20write%20%2F%20mutate-orange?style=for-the-badge" alt="Permissions"/>
  <img src="https://img.shields.io/badge/Memory-Local%20BM25-brightgreen?style=for-the-badge" alt="Local Memory"/>
  <img src="https://img.shields.io/badge/OpenCode-Ready-4ade80?style=for-the-badge" alt="OpenCode Ready"/>
  <img src="https://img.shields.io/badge/Python%20Only-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Only"/>
</p>

**Fully local memory + trace system.** No API keys. No Node.js. No cloud LLM calls for memory operations. Pure Python.

> ⚠️ **Local ≠ airgapped.** The Sensory module (web browsing, search, API requests) makes outbound HTTP calls — those are real network operations. Memory, trace, and computation tools run entirely offline.

---

## Why This Exists

AI coding agents start every session from zero. They don't remember the bug you fixed yesterday, the architecture decision you made last week, or the tool preference you set an hour ago.

ai-memory-core fixes that. It gives your agent:

- **Cross-session memory** — BM25 search across everything it learned, with zero LLM cost
- **Error trace registry** — Every error logged once, searchable across sessions. Never debug the same thing twice
- **Decision registry** — Architecture decisions with rationale, stored as searchable records
- **Goal tracking** — Current goal + sub-goal decomposition with alignment checks
- **Commitment verification** — Session promises listed, verified, tracked across restarts

**And 49 additional tools** for code analysis, web browsing, SVG generation, audio processing, game design, devops diagnostics, and text analysis — all permission-gated so your agent can explore safely.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    MCP Client                              │
│          (OpenCode, Claude Code, Cursor...)                │
├──────────────────────────────────────────────────────────┤
│                JSON-RPC 2.0 over stdio                     │
├──────────────────────────────────────────────────────────┤
│                 tools-mcp-server.py                        │
│                                                           │
│  ┌────────────   Permission Guard   ──────────────────┐   │
│  │  can_call_tool(name, {mode})                       │   │
│  │  auto mode     → blocks write_/mutate_             │   │
│  │  interactive   → allows all, warns on write/mutate │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  ┌──────────┐ ┌──────┐ ┌──────┐ ┌────────┐ ┌──────────┐ │
│  │ Trace    │ │Memory│ │Coder │ │ Audio  │ │Sensory   │ │
│  │ 13 tools │ │5 tls │ │7 tls │ │ 7 tls  │ │ 12 tls   │ │
│  └──────────┘ └──────┘ └──────┘ └────────┘ └──────────┘ │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│  │DevOps  │ │GameDev │ │Art     │ │Lit     │ │Verifier│ │
│  │ 7 tls  │ │ 7 tls  │ │4 tls   │ │4 tls   │ │ 4 tls  │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │
│                                                           │
│  ┌──────────── Module Factory ───────────────────────┐    │
│  │  _get_module(name, filename) — lazy-loaded, cached │    │
│  │  One function replaces 7 individual loaders       │    │
│  └───────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
         │                                      │
         ▼                                      ▼
┌───────────────────┐              ┌──────────────────────┐
│ data/             │              │ .memory/             │
│  error-registry   │              │  profiles/           │
│  decision-registry│              │  identity/           │
│  goal-registry    │              │  ne/                 │
│  commitments      │              │  (BM25 index)        │
│  memory_store     │              └──────────────────────┘
│  synonyms         │
│  tool-inventory   │
└───────────────────┘
```

---

## Permission Model

This is the core safety architecture. Every tool has a `permission` field. The `can_call_tool()` guard enforces it:

```python
def can_call_tool(tool_name, context):
    if mode == "auto" and permission != "read":
        return (False, f"Blocked — {permission} requires human review")
    if permission in ("write", "mutate"):
        return (True, f"⚠️ {tool_name} has {permission} permission")
    return (True, "ok")
```

| Prefix | Permission | Count | Auto Mode | Interactive Mode |
|--------|-----------|-------|-----------|-----------------|
| `read_*` | read | 58 | ✅ Allowed | ✅ Allowed |
| `write_*` | write | 6 | ❌ Blocked | ⚠️ Allowed + warning |
| `mutate_*` | mutate | 3 | ❌ Blocked | ⚠️ Allowed + warning |

**What this means in practice:** An agent running in auto mode can browse the web, analyze code, generate SVGs, search memory, and read the trace registry — but it cannot write to memory, log errors, add decisions, or interact with web page forms without a human saying yes.

---

## 68 tools — What They Actually Do

### Trace System (13 tools) — `trace.py`

The brain of the operation. Logs, searches, and tracks everything across sessions. Replaces 4 PowerShell scripts with pure Python.

#### Error Registry — never debug the same error twice

```python
# Log an error (write_)
{"name": "write_xtrace_log_error", "arguments": {
    "command": "npm run build",
    "error_output": "Module not found: 'react'",
    "exit_code": 1
}}
# → {"id": "err-001", "status": "logged", "occurrence_count": 1}

# Search past errors (read_) — next session, before debugging
{"name": "read_xtrace_search", "arguments": {"keyword": "Module not found"}}
# → {"results": [{"id": "err-001", "root_cause": "Missing dependency", "resolution": "npm install react", "occurrence_count": 3}]}

# Get status summary (read_)
{"name": "read_xtrace_status"}
# → {"total": 12, "resolved": 8, "unresolved": 4, "top_frequent": ["Module not found", "TypeError"]}
```

#### Decision Registry — architectural decisions as searchable records

```python
# Log a decision (write_)
{"name": "write_dtrace_add", "arguments": {
    "title": "PostgreSQL over MySQL",
    "decision": "PostgreSQL 16 with JSONB + CTEs",
    "rationale": "Need array columns and recursive queries for analytics",
    "context": "Database selection for analytics pipeline",
    "category": "architecture"
}}
# → {"id": "dt-001", "status": "active"}

# Search decisions (read_)
{"name": "read_dtrace_search", "arguments": {"keyword": "PostgreSQL"}}
# → {"results": [{"title": "PostgreSQL over MySQL", "status": "active", ...}]}
```

#### Goal Registry — prevent scope drift

```python
# Set a goal (write_)
{"name": "write_goal_registry_init", "arguments": {
    "goal": "Implement user authentication module"
}}
# → {"goal_id": "goal-001", "status": "active"}

# Add sub-goals (write_)
{"name": "write_goal_registry_add_subgoal", "arguments": {
    "description": "Design database schema for users table"
}}
# → {"subgoals": [{"id": 1, "description": "Design database schema...", "status": "pending"}]}

# Check if you're still on track (read_)
{"name": "read_goal_registry_check_alignment", "arguments": {
    "current_action": "Installing bcrypt for password hashing"
}}
# → {"aligned": true, "reason": "Implementation step for authentication"}

# Get progress (read_)
{"name": "read_goal_registry_status"}
# → {"goal": "Implement user authentication", "pct_complete": 60, "subgoals": [...]}
```

#### Commitment Checker — session promises tracked across restarts

```python
# List pending commitments (read_)
{"name": "read_commitment_checker_list"}
# → {"commitments": [{"id": "b1", "text": "Batch-load skills at session start", "verified_sessions": ["ses_abc"], "next_verify": "2026-07-17"}, ...]}

# Mark as verified (mutate_) — persists to data/commitments.json
{"name": "mutate_commitment_checker_verify", "arguments": {"id": "b1"}}
# → {"status": "verified", "session": "ses_def456"}

# Next session: reads from disk, shows unverified
# → {"status": "verified", "session": "ses_abc123"} (already verified from different session)
```

### Memory System (5 tools)

Local BM25 search with synonym expansion. Zero LLM calls. All data in `data/memory_store.json`.

```python
# Store a memory (write_)
{"name": "write_memory_add", "arguments": {
    "text": "SM-2 algorithm: ease factor starts at 2.5, minimum 1.3",
    "source": "task_learning",
    "metadata": {"topic": "spaced-repetition"}
}}
# → {"memory_id": "mem_001", "status": "stored"}

# Search (read_) — synonym expansion finds "spaced repetition" even if you store "SM-2"
{"name": "read_memory_search", "arguments": {"query": "spaced repetition algorithm", "limit": 5}}
# → {"results": [{"text": "SM-2 algorithm: ease factor...", "score": 0.89, "source": "task_learning"}], "count": 1}

# Consolidate duplicates (mutate_) — merges by Jaccard similarity
{"name": "mutate_memory_consolidate", "arguments": {"threshold": 0.85}}
# → {"merged": 2, "removed": 0, "remaining": 24}

# Synthesize (read_) — search + narrative assembly
{"name": "read_memory_synthesize", "arguments": {"query": "consolidation strategy", "max_sources": 3}}
# → {"narrative": "Based on 2 sources: Jaccard threshold of 0.85...", "confidence": 0.82}

# Status (read_)
{"name": "read_memory_status"}
# → {"entries": 27, "storage_kb": 4.2, "unique_terms": 312}
```

### Verifier Middleware (4 tools)

Every tool call passes through a two-phase verifier. The renudge system lets you halt or override specific tools mid-session.

```python
# Check verifier status (read_)
{"name": "read_verifier_status"}
# → {"checks_run": 142, "violations_found": 3, "renudges_sent": 1, "active_renudges": {}}

# Halt a tool mid-session (write_) — next call to read_memory_* will be blocked
{"name": "write_verifier_renudge", "arguments": {
    "target": "read_memory_search",
    "strategy": "halt",
    "correction": {}
}}
# → {"signal_id": "sig_001", "strategy": "halt", "needs_human": false}

# Clear the renudge (write_)
{"name": "write_verifier_clear_renudge", "arguments": {"target": "read_memory_search"}}
# → {"status": "cleared", "target": "read_memory_search"}
```

### Sensory Module (12 tools) — web browsing, extraction, API

**One mutate tool, 11 read tools.** The `mutate_sensory_interact` can click buttons and fill forms on real websites — that's why it's `mutate_`.

```python
# Browse a page (read_)
{"name": "read_sensory_browse", "arguments": {"url": "https://example.com", "extract_mode": "markdown"}}
# → {"status": "ok", "title": "Example Domain", "content": "# Example Domain\nThis domain is for use in...", "links": [...]}

# Screenshot (read_)
{"name": "read_sensory_screenshot", "arguments": {"url": "https://example.com"}}
# → {"status": "ok", "saved_to": "/tmp/screenshot_abc123.png"}

# Search the web (read_) — DuckDuckGo, no API key
{"name": "read_sensory_search", "arguments": {"query": "Rust async best practices 2026", "num_results": 5}}
# → {"results": [{"title": "...", "url": "...", "snippet": "..."}]}

# Fill a form and click submit (mutate_)
{"name": "mutate_sensory_interact", "arguments": {
    "url": "https://example.com/login",
    "actions": [
        {"type": "type", "selector": "#username", "value": "user"},
        {"type": "type", "selector": "#password", "value": "pass"},
        {"type": "click", "selector": "#submit"}
    ]
}}
# → {"status": "ok", "actions_executed": [...], "final_text": "Welcome, user!"}

# Extract from PDF (read_)
{"name": "read_sensory_extract_pdf", "arguments": {"file_path": "/path/to/doc.pdf", "max_pages": 10}}
# → {"pages_extracted": 10, "full_text": "..."}

# API requests (read_)
{"name": "read_sensory_api_request", "arguments": {"url": "https://api.github.com/repos/ohmpatel3877/ai-memory-core", "method": "GET"}}
# → {"status_code": 200, "headers": {...}, "data": {...}}
```

### Coder Module (7 tools)

```python
# Analyze code (read_)
{"name": "read_coder_analyze_code", "arguments": {
    "code": "function add(a,b){return a+b}",
    "language": "javascript"
}}
# → {"complexity": 1, "maintainability": "A", "smells": [], "security": {"issues": [], "score": 100}}

# Debug an error (read_)
{"name": "read_coder_debug", "arguments": {
    "error": "TypeError: Cannot read properties of undefined (reading 'map')",
    "language": "javascript",
    "code_context": "const items = data.map(...)"
}}
# → {"root_cause": "data is undefined — likely API response not checked", "fix": "Add null guard: const items = (data || []).map(...)"}

# Generate framework scaffold (read_)
{"name": "read_coder_generate_framework", "arguments": {
    "project_type": "web-api",
    "language": "python",
    "features": ["fastapi", "sqlalchemy", "auth"]
}}
# → {"files": [{"path": "main.py", "content": "..."}, {"path": "models.py", "content": "..."}, ...]}
```

### Audio Module (7 tools)

```python
# Analyze WAV file (read_)
{"name": "read_audio_analyze_file", "arguments": {"file_path": "recording.wav"}}
# → {"duration_s": 3.2, "channels": 1, "sample_rate": 44100, "amplitude": {"peak": 0.85, "rms": 0.32}}

# Generate a tone (read_)
{"name": "read_audio_generate_tone", "arguments": {"frequency": 440, "duration_seconds": 2, "waveform": "sine"}}
# → {"format": "wav", "data_base64": "UklGRiR...", "duration_s": 2.0, "sample_rate": 44100}
```

### Art Module (4 tools)

```python
# Generate SVG (read_)
{"name": "read_art_generate_svg", "arguments": {
    "description": "flowchart with 4 steps: input, process, decision, output",
    "width": 500, "height": 400
}}
# → <svg viewBox="0 0 500 400">...flowchart...</svg>

# Generate color theme (read_)
{"name": "read_art_generate_theme", "arguments": {"description": "dark cyberpunk"}}
# → {"colors": {"primary": "#00ff88", "secondary": "#ff00ff", "background": "#0a0a0f"}, "wcag_contrast": {"pass": true}}
```

### DevOps Module (7 tools)

```python
# Debug container (read_)
{"name": "read_devops_container_debug", "arguments": {
    "error_log": "Error response from daemon: driver failed programming external connectivity",
    "runtime": "podman"
}}
# → {"root_cause": "Port conflict on host", "fix": "Change host port mapping or stop conflicting container"}

# Generate Docker Compose (read_)
{"name": "read_devops_compose_generator", "arguments": {
    "services": [{"name": "web", "image": "nginx", "ports": ["80:80"]}]
}}
# → {"compose": "version: '3.8'\nservices:\n  web:\n    image: nginx\n    ports:\n      - '80:80'"}
```

### Game Dev Module (7 tools)

```python
# Design analysis (read_)
{"name": "read_gamedev_design_analyze", "arguments": {
    "concept": "A roguelike deckbuilder where cards are program snippets",
    "genre": "strategy"
}}
# → {"fun_factor": 8, "engagement_loops": ["Draw → Execute → Debug → Compile → Draw"], "market_fit": "niche"}

# Scaffold Unity project (read_)
{"name": "read_gamedev_scaffold_project", "arguments": {
    "engine": "unity", "genre": "platformer", "name": "MyGame"
}}
# → {"files": [{"path": "Assets/Scripts/PlayerController.cs", "content": "..."}]}
```

### Literature Module (4 tools)

```python
# Analyze text (read_)
{"name": "read_lit_analyze_text", "arguments": {"text": "The mitochondrion is the powerhouse of the cell..."}}
# → {"reading_level": "grade_9", "flesch_kincaid": 8.7, "key_concepts": ["mitochondrion", "ATP"], "sentiment": "neutral"}

# Extract concepts (read_)
{"name": "read_lit_extract_concepts", "arguments": {"text": "..."}}
# → {"concepts": [{"term": "mitochondrion", "definition": "...", "relationships": ["ATP → energy"]}]}
```

---

## End-to-End Workflow Examples

### Debug a build failure across sessions

```
Session 1 — Agent encounters error:
  write_xtrace_log_error("npm run build", "Module not found: 'react'")

Session 2 — Different agent, same project:
  read_xtrace_search("Module not found")
  → Found! Resolved in session 1: "npm install react"

  write_memory_add("Always run 'npm install' before assuming a module exists")
  
  write_dtrace_add(
    title="Add pre-build dependency check to CI",
    decision="Run npm ci before npm run build in CI pipeline",
    rationale="Prevents ModuleNotFound errors that waste debug time"
  )
```

### Research, extract, and remember

```
  read_sensory_search("Rust async Tokio best practices 2026")
  → 5 results

  read_sensory_browse("https://tokio.rs/blog/2026-best-practices", "markdown")
  → Full article content

  read_lit_extract_concepts(article_content)
  → {"concepts": ["tokio::spawn", "backpressure", "structured concurrency"]}

  write_memory_add("Tokio best practice: use tokio::spawn for CPU-bound work")
  
  write_dtrace_add(
    title="Use tokio::spawn for CPU-bound tasks",
    decision="Defer CPU-intensive work to tokio::spawn_blocking",
    rationale="Prevents blocking the async runtime and starving other tasks"
  )
```

### Code review + architecture recommendation

```
  read_coder_review(code, "typescript")
  → {"security": [{"severity": "high", "finding": "SQL injection in line 42"}], "score": 72}

  read_coder_architecture("web-api", "medium", ["auth", "rate-limiting"])
  → {"recommended": "Clean Architecture with middleware pipeline", "diagram": "...", "files": [...]}

  write_dtrace_add(
    title="Adopt Clean Architecture for API",
    decision="Use repository pattern + use case layer",
    rationale="Separates business logic from framework concerns"
  )
```

---

## Memory System Details

### How the BM25 Engine Works

The NE-Memory system uses pure BM25 ranking with:
- **Tokenization**: Whitespace + punctuation splitting with lowercase normalization
- **BM25 scoring**: Standard Okapi BM25 with k1=1.5, b=0.75
- **Synonym expansion**: Configurable in `data/synonyms.json` — searches for "memory" also match "recall", "remember", "store"
- **Fuzzy matching**: Levenshtein distance with configurable threshold (default 0.85)
- **Consolidation**: Jaccard similarity between entry texts — merges pairs above threshold

**Zero LLM calls.** Every search, add, and consolidate operation is pure math — no API keys, no tokens, no latency from external services.

### Data Storage

| File | Purpose |
|------|---------|
| `data/memory_store.json` | All memory entries with text, metadata, and timestamps |
| `data/synonyms.json` | Expansion map for BM25 query broadening |
| `data/error-registry.json` | Error signatures with occurrence counts and resolutions |
| `data/decision-registry.json` | Architecture decisions with rationale and alternatives |
| `data/commitments.json` | Session commitments with cross-session verification tracking |
| `data/goal-registry.json` | Current goal with sub-goal decomposition |
| `.memory/ne/` | BM25 index files for fast retrieval |
| `.memory/profiles/` | Consolidated identity profiles |

---

## Installation

### Prerequisites
- **Python 3.10+**
- No API keys, no Node.js, no cloud dependencies for the core system
- ⚠️ Sensory module requires Playwright: `playwright install firefox` (optional — skip if not browsing)

### Quick Start
```bash
git clone https://github.com/ohmpatel3877/ai-memory-core.git
cd ai-memory-core
python -m pip install -r requirements.txt   # if requirements.txt exists
python scripts/tools-mcp-server.py          # starts MCP server on stdio
```

### Docker
```bash
docker compose up -d
```

### Connect to OpenCode
Add to `opencode.json`:
```json
{
  "mcpServers": {
    "ai-memory-core": {
      "command": "python",
      "args": ["scripts/tools-mcp-server.py"]
    }
  }
}
```

---

## Scripts

All scripts in `scripts/` are pure Python:

| Script | Purpose |
|--------|---------|
| `tools-mcp-server.py` | Main MCP server (68 tools, permission guard, module loader) |
| `trace.py` | Unified trace CLI — error, decision, goal, commitment ops |
| `memory_search.py` | BM25 engine — add, search, synthesize, consolidate |
| `verifier_middleware.py` | Pre/post tool verification + renudge signal system |
| `identity-manager.py` | Agent identity consolidation with versioned evolution |
| `task-analyzer.py` | Complexity scoring for task decomposition |
| `task-orchestrator.py` | DAG-based multi-agent pipeline execution |
| `sensory-module.py` | Web browsing (Playwright), extraction, API, search |
| `coder-module.py` | Code analysis, review, debug, framework generation |
| `audio-module.py` | WAV analysis, frequency, music theory, tone generation |
| `art-module.py` | SVG generation, color themes, palette extraction |
| `literature-module.py` | Text analysis, concept extraction, study guides |
| `devops-module.py` | Container debugging, compose, Samba, network |
| `game-dev-module.py` | Game design analysis, project scaffolding, optimization |

---

## Skills

| Skill | Description |
|-------|-------------|
| **Task Orchestrator** | Auto-decompose tasks into parallel subagent workstreams using complexity scoring |
| **Skill Router** | 30+ trigger rules mapping task intent → skill auto-load |
| **Security Hardening** | Audit, CVE detection, CSP, XSS, SQL injection prevention |
| **Parameter Virtualizer** | Cognitive scaffolding to make smaller models perform like larger ones |
| **Pattern Flipper** | 6 reasoning strategy router (Chain-of-Thought, Tree of Thoughts, Reflexion, etc.) |
| **Speed Optimizer** | Cross-session bottleneck monitoring with automated workarounds |

---

## Project Structure

```
ai-memory-core/
├── scripts/              # All Python modules (MCP server + 15 tools)
│   ├── tools-mcp-server.py    # Main MCP server entry point
│   ├── trace.py               # Unified trace system
│   ├── memory_search.py       # BM25 engine
│   ├── verifier_middleware.py # Pre/post verification
│   └── *-module.py            # 7 capability modules
├── data/                 # JSON persistence (all cross-session state)
├── skills/               # OpenCode/Claude Code skill definitions
├── docs/                 # Documentation
├── docker/               # Container setup
├── dashboard.html        # Web dashboard (open in browser)
└── .memory/              # Local BM25 index files
```

---

## Related Projects

| Project | Description |
|---------|-------------|
| [agent-memory-mcp](https://github.com/ohmpatel3877/agent-memory-mcp) | Local Markdown-native MCP memory for project-specific conventions |
| [StudySpace](https://github.com/ohmpatel3877/StudySpace) | Tauri 2 + React 19 cross-platform desktop study workspace |

---

## License

MIT © Ohm Patel
