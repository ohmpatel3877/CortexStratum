<p align="center">
  <img src="https://img.shields.io/badge/MCP%20Server-68%20tools-blue?style=for-the-badge" alt="68 MCP Tools"/>
  <img src="https://img.shields.io/badge/mem0-Cloud%20Memory-purple?style=for-the-badge" alt="mem0 Cloud"/>
  <img src="https://img.shields.io/badge/OpenCode-Ready-4ade80?style=for-the-badge" alt="OpenCode Ready"/>
  <img src="https://img.shields.io/badge/Claude%20Code-Ready-4ade80?style=for-the-badge" alt="Claude Code Ready"/>
</p>

# ai-memory-core

**Persistent memory infrastructure for AI coding agents.** A 68-tool MCP server that gives OpenCode, Claude Code, and Cursor agents memory that persists across sessions — error tracking, decision logging, skill routing, task orchestration, multi-modal AI generation, and behavioral verification.

Built on [mem0](https://mem0.ai) for cloud-backed cross-session memory and agent-memory-mcp for local project-specific conventions.

---

## 🌟 Features

### 🧠 Memory & Persistence
| Feature | What It Does |
|---------|-------------|
| **xTrace Error Tracking** | Log, search, and aggregate error signatures across sessions — never debug the same thing twice |
| **DTrace Decision Registry** | Record every architectural decision with rationale, alternatives, and consequences (ADR on autopilot) |
| **Memory Search** | Local BM25 search with synonym expansion — zero-LLM-cost retrieval of past learnings |
| **Memory Consolidation** | Auto-merge duplicate entries by Jaccard similarity to keep memory lean |
| **Goal Registry** | Track goals, sub-goals, and alignment checks — prevents scope drift mid-session |
| **Commitment Checker** | List and verify pending session commitments so nothing falls through cracks |

### 🤖 Multi-Modal AI Generation
| Module | Tools | Capabilities |
|--------|-------|-------------|
| **Coder** | 7 tools | Code analysis (12 langs), framework scaffolding, debug analysis, code review, explanation, language conversion, architecture recommendations |
| **Sensory** | 12 tools | Web browsing (Playwright), screenshots, interaction, PDF extraction, HTML parsing, OCR, RSS feeds, web search (DuckDuckGo), API requests |
| **Art** | 4 tools | SVG generation, color themes with WCAG validation, palette extraction, design concepts |
| **Audio** | 7 tools | WAV analysis, waveform visualization, frequency/FFT analysis, music theory, speech metrics, tone generation |
| **DevOps** | 7 tools | Container debugging, permissions analysis, compose generation, Samba config, mergerfs setup, Dockerfile optimization, network troubleshooting |
| **Game Dev** | 7 tools | Design analysis, project scaffolding (Unity/Unreal/Roblox), mechanics design, monetization strategy, optimization, engine comparison, level design |
| **Literature** | 4 tools | Text analysis (Flesch-Kincaid), concept extraction, study guide generation, philosophical argument analysis |

### 🧩 Agent Infrastructure
| Feature | Description |
|---------|-------------|
| **Skill Router** | 30+ trigger rules that auto-load the right skill based on task intent — priority resolved |
| **Task Orchestrator** | Complexity scoring → auto-decompose into parallel subagent workstreams |
| **Verifier Middleware** | Behavioral correction signals — detects drift and renudges the agent back on track |
| **Output Condenser** | Compress verbose command output to essential information |
| **DAG Coordinator** | Multi-phase pipeline orchestration with state contracts |

---

## 🚀 For Non-Technical Users

**You only need Docker. Nothing else. No Node.js, no Python, no npm, no pip.**

### Windows
Send your friend this link — it downloads the file, then they double-click it:
```
https://github.com/ohmpatel3877/ai-memory-core/releases/download/v1.0.0/ONE-CLICK.cmd
```
This is a GitHub Release link, so the browser will **download** it (not display it). They double-click the downloaded file and it runs.

### Mac / Linux
Open Terminal, paste this one line, press Enter:
```bash
curl -fsSL https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/setup-opencode-container.sh | bash
```

### What they get
A running container with the 68-tool MCP server. Connect it to OpenCode by adding to `opencode.json`:
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

## 📦 Developer Install

### Prerequisites
- **Node.js** 18+
- **Python** 3.10+
- A [mem0 API key](https://app.mem0.ai) (free tier available)

### Windows (PowerShell 7+)
```powershell
git clone https://github.com/ohmpatel3877/ai-memory-core.git
cd ai-memory-core
pwsh plugin-tools/install-ai-memory-core.ps1
```

### macOS / Linux
```bash
git clone https://github.com/ohmpatel3877/ai-memory-core.git
cd ai-memory-core
bash plugin-tools/install-ai-memory-core.sh
```

### Docker
```bash
docker compose up -d
```

The installer will:
1. ✅ Validate Node.js + Python versions
2. ✅ Install npm dependencies
3. ✅ Prompt for MEM0_API_KEY (or read from `.env`)
4. ✅ Register the MCP server in `opencode.json`
5. ✅ Link skills to `~/.config/opencode/skills/`
6. ✅ Run verification checks

---

## 🛠 MCP Server — 68 Tools

The MCP server runs on the standard JSON-RPC protocol over stdio. OpenCode and Claude Code auto-discover it from `opencode.json`.

### Core Infrastructure (13 tools)

| Tool | Purpose |
|------|---------|
| `xtrace_log_error` | Log error occurrences for cross-session tracking |
| `xtrace_search` | Search the error registry by signature |
| `xtrace_status` | Error tracking summary statistics |
| `dtrace_add` | Record architectural decisions with context |
| `dtrace_search` | Search the decision registry |
| `skill_router_match` | Match tasks to skills by intent triggers |
| `output_condenser` | Compress command output to essentials |
| `goal_registry_init` | Initialize a tracked goal |
| `goal_registry_add_subgoal` | Decompose goals into sub-goals |
| `goal_registry_status` | Current goal stack state |
| `goal_registry_check_alignment` | Verify current action aligns with original goal |
| `commitment_checker_list` | List pending session commitments |
| `commitment_checker_verify` | Mark commitments as verified |

### Coder (7 tools)

`coder_analyze_code`, `coder_generate_framework`, `coder_debug`, `coder_review`, `coder_explain`, `coder_convert`, `coder_architecture`

Supports: Python, JavaScript, TypeScript, Rust, Go, Java, C#, C++, Swift, Kotlin, Ruby, PHP

### Sensory — Web & File I/O (12 tools)

`sensory_browse`, `sensory_screenshot`, `sensory_interact`, `sensory_extract_pdf`, `sensory_extract_html`, `sensory_extract_image`, `sensory_scrape`, `sensory_extract_article`, `sensory_api_request`, `sensory_fetch_rss`, `sensory_read_file`, `sensory_search`

Headless Firefox via Playwright. DuckDuckGo search — no API key required.

### DevOps — Infrastructure (7 tools)

`devops_container_debug`, `devops_permissions_analyze`, `devops_compose_generator`, `devops_samba_config`, `devops_mergerfs_setup`, `devops_dockerfile_analyze`, `devops_network_troubleshoot`

### Audio (7 tools)

`audio_analyze_file`, `audio_waveform`, `audio_frequency_analysis`, `audio_music_theory`, `audio_speech_analysis`, `audio_convert_guide`, `audio_generate_tone`

### Game Dev (7 tools)

`gamedev_design_analyze`, `gamedev_scaffold_project`, `gamedev_mechanics_guide`, `gamedev_monetization`, `gamedev_optimization`, `gamedev_compare_engines`, `gamedev_level_design`

### Art (4 tools)

`art_generate_svg`, `art_generate_theme`, `art_extract_palette`, `art_design_concept`

### Literature (4 tools)

`lit_analyze_text`, `lit_extract_concepts`, `lit_generate_study_guide`, `lit_analyze_philosophy`

### Memory Search (5 tools)

`memory_search`, `memory_synthesize`, `memory_add`, `memory_consolidate`, `memory_status`

### Verifier (2 tools)

`verifier_status`, `verifier_renudge`

---

## 🧩 Skills

| Skill | File | Description |
|-------|------|-------------|
| **Task Orchestrator** | `skills/task-orchestrator/SKILL.md` | Auto-decompose tasks into parallel subagent workstreams using the Complexity Matrix |
| **Security Hardening** | `skills/security-hardening/SKILL.md` | Security audit, CVE detection, encryption, CSP, XSS, SQL injection prevention |
| **Skill Router** | `skills/skill-router.json` | 30+ trigger rules mapping user intent → skill auto-load; priority-based conflict resolution |

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

## 📐 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    OpenCode / Claude Code             │
├─────────────────────────────────────────────────────┤
│                    MCP Protocol (stdio)              │
├─────────────────────────────────────────────────────┤
│                  tools-mcp-server.py                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐  │
│  │ Core │ │Coder │ │Audio │ │ Art  │ │  Sensory  │  │
│  │13 tls│ │ 7 tls│ │ 7 tls│ │4 tls │ │  12 tls  │  │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────────┘  │
│  ┌──────┐ ┌────────┐ ┌──────┐ ┌────────┐ ┌──────┐  │
│  │DevOps│ │Game Dev│ │ Lit  │ │Memory  │ │Verif │  │
│  │ 7 tls│ │ 7 tls  │ │4 tls │ │Search  │ │2 tls │  │
│  └──────┘ └────────┘ └──────┘ └──┬─────┘ └──────┘  │
├───────────────────────────────────┼─────────────────┤
│        mem0 (Cloud-Backed)        │  Agent-Memory-MCP│
│   ┌─────────────────────────┐     │  ┌─────────────┐ │
│   │ Cross-session memory    │     │  │ Project-local│ │
│   │ User preferences        │     │  │ Conventions  │ │
│   │ Anti-patterns           │     │  │ ADR history  │ │
│   │ Resolved bugs           │     │  │ State files  │ │
│   └─────────────────────────┘     │  └─────────────┘ │
└───────────────────────────────────┴───────────────────┘
```

### Memory Categories

ai-memory-core uses 16 custom memory categories with configurable retention:

| Category | Retention | Purpose |
|----------|-----------|---------|
| `architecture_decisions` | ∞ (pinned) | Design choices, trade-off analyses |
| `coding_conventions` | ∞ (pinned) | Code style, naming, patterns |
| `user_preferences` | ∞ (pinned) | Tool/workflow preferences |
| `anti_patterns` | 365 days | Failed approaches & alternatives |
| `bug_fixes` | 365 days | Root causes & exact fixes |
| `task_learnings` | 180 days | Multi-step workflow insights |
| `session_state` | 90 days | Ephemeral session continuity |
| `session_summaries` | 180 days | Completed session summaries |
| `environmental` | 90 days | Tooling & environment setup |
| `health_check` | 7 days | Probe results |
| *(6 more)* | | Security, API design, performance, testing, deployment, dependencies, monitoring, project_profile |

---

## 🚀 Usage Examples

### Track an Error Across Sessions
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

## 📋 Scripts

All CLI scripts live in `scripts/`:

| Script | Language | Purpose |
|--------|----------|---------|
| `tools-mcp-server.py` | Python | 68-tool MCP server (main entry point) |
| `task-analyzer.py` | Python | Complexity scoring for task orchestration |
| `task-orchestrator.py` | Python | DAG-based multi-agent pipeline execution |
| `verifier_middleware.py` | Python | Behavioral correction signal engine |
| `memory_search.py` | Python | BM25 local memory with synonym expansion |
| `dag-coordinator.py` | Python | Multi-phase state machine orchestration |
| `identity-manager.py` | Python | Agent identity persistence and evolution |
| `sandbox-manager.py` | Python | Isolated code execution environment |
| `benchmark-harness.py` | Python | Performance benchmarking suite |
| `seed-memories.js` | Node.js | Seed mem0 with initial knowledge base |
| `check-status.js` | Node.js | mem0 connectivity and health diagnostic |
| `consolidate.js` | Node.js | mem0 dream consolidation trigger |
| Various `.ps1` scripts | PowerShell | Dashboard, decision trace, error trace, goal registry, team mode |
| Various module `.py` | Python | Art, audio, coder, devops, game-dev, literature, sensory modules |

---

## 🔧 Customization

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
  "triggers": ["kubernetes", "k8s", "helm", "pod"],
  "skills": ["kubernetes-operations-k8s-manifest-generator"],
  "priority": 10
}
```

### MCP Server Config

Edit `package.json` → `mcpServers` or `opencode.json` to change server args:

```json
"ai-memory-core": {
  "command": "python",
  "args": ["scripts/tools-mcp-server.py"]
}
```

---

## 🔗 Related Projects

| Project | Description |
|---------|-------------|
| [agent-memory-mcp](https://github.com/ohmpatel3877/agent-memory-mcp) | Local Markdown-native MCP memory for project-specific conventions |
| [wshobson-agents](https://github.com/ohmpatel3877/wshobson-agents) | Multi-harness plugin marketplace with 94 plugins, 203 agents, 175 skills |
| [StudySpace](https://github.com/ohmpatel3877/StudySpace) | Tauri 2 + React 19 cross-platform desktop study workspace |

---

## 📄 License

MIT © Ohm Patel

---

<p align="center">
  <sub>Built with mem0, OpenCode, and too much coffee.</sub>
</p>
