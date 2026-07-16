# GitHub Repository Setup & Integration

Comprehensive guide for configuring, documenting, and populating GitHub repositories
and integrating them with OpenCode.

Based on real-world experience building ai-memory-core v0.3.0.

## When to Use

Use this skill when:
- Setting up a new GitHub repository from scratch
- Populating an existing repo with CI, issues, milestones, wiki
- Configuring OpenCode integration for a project
- Creating project boards, issue templates, and automation
- Need to audit or improve a repo's GitHub presence
- Debugging gh CLI auth, API token, or PowerShell escaping issues

---

## Phase 1: Repository Foundation

### 1.1 Initialize Repo

```bash
# Create repo on GitHub first, then:
git init
git add -A
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

### 1.2 Essential Root Files

| File | Purpose | Required |
|------|---------|----------|
| `README.md` | Project overview, quick start, badges | ✅ Yes |
| `ARCHITECTURE.md` | System design, permission model, data flow | ✅ Recommended |
| `QUICKSTART.md` | Minimal steps to get running in 2 minutes | ✅ Recommended |
| `LICENSE` | MIT, Apache 2.0, GPL — pick one | ✅ Yes |
| `.gitignore` | Ignore build artifacts, deps, secrets | ✅ Yes |
| `CHANGELOG.md` | Keep a Changelog format | ✅ Recommended |
| `VERSION` | Plain-text single-line version | ✅ Recommended |
| `BUILD.md` | Build pipeline documentation | ✅ Recommended |
| `COMMANDS.md` | Central command registry | For CLIs |
| `DEPENDENCIES.md` | Required vs optional packages per module | For multi-module |
| `MILESTONES.md` | Project roadmap with dates | Recommended |
| `requirements.txt` | Core deps (even if empty/stdlib) | ✅ Recommended |
| `requirements-full.txt` | Optional/extra deps | For large projects |
| `CONTRIBUTING.md` | How to contribute | For OSS |

### 1.3 `.gitignore` Template

```gitignore
# Dependencies
node_modules/
vendor/

# Build artifacts
dist/
build/
*.exe
*.dll
*.so

# Environment
.env
.env.local
*.log

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Auto-generated test artifacts
data/*-test-results.json
.memory/ne/memories.json
```

### 1.4 VERSION File

Single line, SemVer pre-1.0:
```
0.3.0
```

**CRITICAL**: All version references must stay in sync or users will see inconsistent behavior:

| File | Location | How to Update |
|------|----------|---------------|
| `VERSION` | Root | `echo "0.4.0" > VERSION` |
| `package.json` | Root | `"version": "0.4.0"` |
| `opencode.json` | Root | `"version": "0.4.0"` |
| Installer script | e.g. `*.iss` | `#define MyAppVersion "0.4.0"` |
| CLI constant | e.g. `scripts/*.py` | `VERSION = "0.4.0"` |
| Plugin config | `.claude-plugin/plugin.json` | `"version": "0.4.0"` |
| `CHANGELOG.md` | Root | Add entry for new version |

> **Anti-pattern**: Having diverging version numbers across these files. Always update all
> of them in the same commit. Consider writing a `scripts/bump-version.py` if the list grows.

---

## Phase 2: OpenCode Integration

### 2.1 MCP Server Registration

Create `opencode.json` in repo root:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "name": "my-project",
  "version": "0.3.0",
  "description": "One-line description",
  "icon": "🧠",
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["scripts/server.py"]
    },
    "my-server-permissive": {
      "command": "python",
      "args": ["scripts/server.py", "--permissive"]
    }
  },
  "references": {
    "my-project": {
      "path": "~/github/my-project",
      "repository": "username/my-project",
      "description": "One-line description"
    }
  }
}
```

### 2.2 Skill Groups

Organize skills into groups for the OpenCode UI:

```json
{
  "skillGroups": [
    {
      "title": "Core Infrastructure",
      "description": "Essential operations.",
      "skills": ["skill-a", "skill-b"]
    },
    {
      "title": "Testing & Verification",
      "description": "Quality gates.",
      "skills": ["skill-c", "skill-d"]
    }
  ]
}
```

### 2.3 OpenCode Agent Definitions

Create `.opencode/agents.md`:

```markdown
# Project Agents

### @agent-name
**Purpose**: What this agent does
**Skills**: skill1, skill2
**Tools**: tool1, tool2
**Behavior**: How it should behave
```

### 2.4 Active Skills

Create `.opencode/active-skills.json`:

```json
[
    "skill-name-1",
    "skill-name-2"
]
```

### 2.5 Global Config Integration

Add the repo to `~/.config/opencode/opencode.jsonc` under `references`:

```json
"references": {
    "my-project": {
      "path": "~/github/my-project",
      "repository": "username/my-project",
      "description": "One-line description"
    }
}
```

---

## Phase 3: GitHub Automation

### 3.1 CI Pipeline

Create `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]
jobs:
  syntax-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python -m py_compile scripts/*.py
  core-tests:
    runs-on: ubuntu-latest
    needs: syntax-check
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python scripts/test-suite.py
```

### 3.2 Release Pipeline

Create `.github/workflows/release.yml` (triggered by tags):

```yaml
name: Release
on:
  push:
    tags: ["v*"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make build
      - uses: actions/upload-artifact@v4
        with:
          name: release
          path: dist/
```

### 3.3 Issue Templates

Create `.github/ISSUE_TEMPLATE/` directory with YAML frontmatter:

#### `bug-report.md`
```markdown
---
name: Bug Report
about: Report a bug
title: "[Bug] "
labels: bug
---
## Describe the Bug
## To Reproduce
## Expected Behavior
## Environment
```

#### `feature-request.md`
```markdown
---
name: Feature Request
about: Suggest an idea
title: "[Feature] "
labels: enhancement
---
## Problem Statement
## Proposed Solution
## Alternatives
```

#### `config.yml`
```yaml
blank_issues_enabled: true
contact_links:
  - name: Wiki
    url: https://github.com/username/repo/wiki
    about: Documentation and guides
```

### 3.4 Bulk Issue Creator

Create `.github/create-issues.ps1` for creating many issues at once:

```powershell
# Run from authenticated gh terminal at repo root
$Issues = @(
    @{title="Issue 1"; labels=@("enhancement"); milestone=1; body="Description"}
    @{title="Issue 2"; labels=@("bug"); milestone=1; body="Description"}
)
$Issues | ForEach-Object -Parallel {
    gh issue create --repo "username/repo" --title $_.title --label $($_.labels -join ",") --milestone $_.milestone --body $_.body
}
```

---

## Phase 4: Issues & Milestones

### 4.1 Create Milestones

```bash
# Via GitHub API
gh api repos/<user>/<repo>/milestones \
  --field title="v0.1.0 - Foundation" \
  --field description="Core features" \
  --field due_on="2026-08-01T00:00:00Z"
```

Common milestone progression:
```
v0.1.0 - Foundation
v0.2.0 - Expansion
v0.3.0 - Polish & Stability
v0.4.0 - Installer Hardening
v1.0.0 - Stable Release
```

### 4.2 Create Issues

```bash
# Single issue linked to milestone
gh issue create \
  --title "Feature title" \
  --label enhancement \
  --milestone "v0.3.0 - Polish and Stability" \
  --body "Description"
```

**Watch out**: The `--milestone` flag uses the milestone **title**, not number.
If the title contains em dashes (`—`), the parser may fail. Use simple dashes (`-`) instead.

### 4.3 Close Issues

```bash
# Close with comment
gh issue close <number> --comment "Implemented in v0.3.0"

# Close as "not planned" (for invalid/test issues)
gh issue close <number> --reason "not planned"

# Cannot delete via CLI — use API or web UI for deletion
```

### 4.4 Known Issues with `gh` CLI

| Issue | Symptom | Fix |
|-------|---------|-----|
| Auth not propagating | `gh` works in user terminal but not in subprocesses | Extract token via `git credential-manager get`, use API directly |
| Token expiration | `gho_*` tokens expire after a few hours | Run `gh auth login` again |
| PowerShell bracket escaping | `f"#{i[\"number\"]}"` causes SyntaxError | Use `%d` formatting: `"#%d" % i["number"]`, or write Python to a `.py` file |
| API rate limiting | 5000 req/hr for authenticated, 60 req/hr unauthenticated | Always use authenticated requests |
| Milestone number vs title | `--milestone 1` may fail but `--milestone "title"` works | Use milestone title string |

### 4.5 GitHub API Token Extraction

When `gh` is available in the user's terminal but not in the agent's subprocess:

```powershell
# Extract token from Windows Credential Manager
$token = Write-Output "protocol=https`nhost=github.com`n" | git credential-manager get | Select-String "^password=" | ForEach-Object { $_.ToString().Replace("password=","") }

# Use directly in API calls
$headers = @{ Authorization = "Bearer $token"; Accept = "application/vnd.github+json" }
Invoke-RestMethod -Uri "https://api.github.com/repos/user/repo/issues" -Method POST -Headers $headers -Body $json -ContentType "application/json"
```

### 4.6 Issue Labels to Create

| Label | Color | Description |
|-------|-------|-------------|
| `bug` | `d73a4a` | Something isn't working |
| `enhancement` | `a2eeef` | New feature or request |
| `documentation` | `0075ca` | Improvements or additions to documentation |
| `technical debt` | `003399` | Code quality, refactoring |
| `good first issue` | `7057ff` | Good for newcomers |
| `help wanted` | `008672` | Extra attention is needed |

Create a label:
```bash
gh label create "technical debt" --description "Code quality improvements" --color "003399"
```

---

## Phase 5: Wiki

### 5.1 How Wiki Setup Actually Works

The GitHub wiki is a **separate git repo** at `https://github.com/<user>/<repo>.wiki.git`.
It only exists after you create the first page via the web UI.

**Step-by-step**:
1. Go to `https://github.com/<user>/<repo>/wiki`
2. Click "Create the first page"
3. Put any content (e.g., "# Home") and save
4. Now the wiki repo exists — clone and push:

```bash
git clone https://github.com/<user>/<repo>.wiki.git
cd <repo>.wiki
# Add your pages...
git add -A
git commit -m "Initialize wiki"
git push origin master
```

### 5.2 Essential Pages

| Page | Content |
|------|---------|
| `Home.md` | Overview, quick links to all pages |
| `Getting-Started.md` | Prerequisites, quick start, verification |
| `Architecture.md` | System design, data flow, components |
| `Permission-Model.md` | Security model, modes, examples |
| `Memory-System.md` | Storage, BM25, consolidation |
| `MCP-Server-Tools.md` | All tools by module with permissions |
| `Build-Pipeline.md` | CI/CD, test suites, installer |
| `Skill-Router.md` | Trigger rules, fallback, extension |
| `Troubleshooting.md` | Common issues and fixes |

### 5.3 Wiki Links

Use `[[Page-Name|Display Text]]` for internal links.

```markdown
# Home
- [[Getting-Started|Getting Started]]
- [[Permission-Model|Permission Model]]
- [[Troubleshooting|Troubleshooting]]
```

### 5.4 Push After Web UI Init

```bash
cd <repo>.wiki
git pull origin master --rebase   # pull the initial auto-created page
# Resolve any conflicts in Home.md if needed
git push origin master
```

If you get a rejected push, force is OK for a fresh wiki:
```bash
git push origin master --force
```

---

## Phase 6: Multi-Harness Packaging

Package your project for multiple AI assistants from a single source:

### 6.1 Directory Structure

```
├── .claude-plugin/
│   └── plugin.json          # Claude Code marketplace
├── .cursor-plugin/
│   ├── plugin.json          # Cursor IDE
│   └── marketplace.json     # Cursor marketplace
├── .codex-plugin/
│   └── plugin.json          # Codex CLI
├── .agents/
│   └── plugins/
│       └── marketplace.json # Open Agent marketplace
├── .mcp.json                # Generic MCP registration
└── CLAUDE.md                # Claude Code agent guide
```

### 6.2 Claude Code Plugin

`.claude-plugin/plugin.json`:
```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
  "name": "my-plugin",
  "description": "Description",
  "version": "0.3.0",
  "author": {"name": "Your Name"},
  "repository": "https://github.com/user/repo",
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"]
}
```

### 6.3 Cursor Plugin

`.cursor-plugin/plugin.json`:
```json
{
  "name": "my-plugin",
  "description": "Description",
  "version": "0.3.0",
  "author": "Your Name",
  "repository": "https://github.com/user/repo",
  "license": "MIT",
  "tools": [{"name": "tool-name", "description": "Tool description"}]
}
```

`.cursor-plugin/marketplace.json`:
```json
{
  "name": "my-plugin",
  "interface": {"displayName": "My Plugin"},
  "plugins": [{
    "name": "my-plugin",
    "source": {"source": "local", "path": "./"},
    "policy": {"installation": "AVAILABLE", "authentication": "NONE"},
    "category": "Developer Tools"
  }]
}
```

### 6.4 Codex Plugin

`.codex-plugin/plugin.json`:
```json
{
  "name": "my-plugin",
  "description": "Description",
  "version": "0.3.0",
  "author": "Your Name",
  "repository": "https://github.com/user/repo",
  "categories": ["Developer Tools"]
}
```

### 6.5 CLAUDE.md

Create `CLAUDE.md` in the repo root for Claude Code compatibility:

```markdown
# Project Name — Agent Guide

## What This Repo Is
One-line description.

## Quick Start
```bash
# Commands to verify/run
```

## Key Files
| File | Purpose |
|------|---------|
| `path/to/file` | What it does |

## Architecture
Brief system overview.
```

---

## Phase 7: Documentation Suite

### 7.1 Essential Docs

Create these documentation files for a complete project:

| File | Content | Audience |
|------|---------|----------|
| `README.md` | Overview, badges, quick start, TOC | Everyone |
| `ARCHITECTURE.md` | System design, permission model, data flow, module table | Developers |
| `QUICKSTART.md` | 5-step setup in under 2 minutes | New users |
| `BUILD.md` | Build pipeline, test suites, CI, release | Contributors |
| `COMMANDS.md` | Every CLI command in one place | CLI users |
| `DEPENDENCIES.md` | Required vs optional, per-module breakdown | Installers |
| `CHANGELOG.md` | Keep a Changelog format | All users |
| `MILESTONES.md` | Roadmap, target dates, status | Stakeholders |
| `requirements.txt` | Core deps (even if empty/stdlib only) | pip installers |
| `requirements-full.txt` | All optional deps | Power users |

### 7.2 Quick Start Pattern

`QUICKSTART.md` should cover these 5 steps:

```
Step 1: Clone
Step 2: Install (point to requirements*.txt)
Step 3: Start (command to run)
Step 4: Connect (OpenCode/Cursor/Claude config)
Step 5: Verify (test command or --version)
```

### 7.3 Requirements.txt Pattern

Even if your project is stdlib-only, create `requirements.txt` with a comment:

```bash
# Core dependencies — zero pip packages needed.
# This project runs entirely on Python stdlib.
# This file exists for compatibility tooling.
```

Create `requirements-full.txt` for optional features:

```bash
# Full installation — all optional modules
# Install with: pip install -r requirements-full.txt
package>=version
other-package>=version
```

---

## Phase 8: Badges & Visual Design

### 8.1 Shield Badges for README

Add to `docs/badges/`:
- Version badge
- Build status (CI)
- License badge
- Tool count badge
- Permission model badge

Use SVG shields.io-style badges or create custom SVGs.

### 8.2 Dashboard

Create `dashboard.html` with:
- **Stats bar**: tool count, memory, errors, decisions, goals, OpenCode status
- **Tabs**: Tools, Trace, Decisions, Goals, Commitments, OpenCode integration
- **Data sources**: JSON files in `data/` directory
- **Style**: Dark theme, monospace, professional
- **OpenCode tab**: MCP server status, permission bar chart, skill router, active skills, quick integration snippets

### 8.3 README Badges Row

```markdown
<p align="center">
  <img src="https://img.shields.io/badge/version-0.3.0-blue" />
  <img src="https://img.shields.io/badge/tools-68-green" />
  <img src="https://img.shields.io/badge/OpenCode-Ready-purple" />
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" />
</p>
```

---

## Phase 9: Versioning Convention

### 9.1 Pre-1.0 Convention

| Version | Meaning |
|---------|---------|
| `0.1.0` | Initial foundation |
| `0.2.0` | Feature expansion |
| `0.3.0` | Polish, testing, docs |
| `0.4.0`+ | Iterative improvements |
| `1.0.0` | Stable release |

- **0.x.0** minor bumps can include breaking changes (pre-1.0)
- **0.0.x** patches for bug fixes only
- All version files must be updated in the same commit

### 9.2 Bump Process

```bash
# 1. Update VERSION
echo "0.4.0" > VERSION

# 2. Update CHANGELOG.md with new entry

# 3. Update all config files
sed -i 's/"version": "0.3.0"/"version": "0.4.0"/' package.json opencode.json .claude-plugin/plugin.json

# 4. Update Python constant
sed -i 's/VERSION = "0.3.0"/VERSION = "0.4.0"/' scripts/server.py

# 5. Update installer
sed -i 's/MyAppVersion "0.3.0"/MyAppVersion "0.4.0"/' installer.iss

# 6. Commit and tag
git add VERSION CHANGELOG.md package.json opencode.json .claude-plugin/plugin.json scripts/server.py installer.iss
git commit -m "bump version 0.3.0 -> 0.4.0"
git tag v0.4.0
git push --tags
```

---

## Phase 10: Token & Shell Workarounds

### 10.1 PowerShell Bracket Escaping

**Problem**: Python f-strings with dict access in PowerShell:
```powershell
python -c "print(f\"#{i['number']}\")"  # FAILS: SyntaxError
```

PowerShell interprets `["number"]` before Python receives it.

**Workarounds** (use in order of preference):

```python
# A) Write a .py file (cleanest, preferred)
code = 'print("#" + str(i["number"]))'
open("tmp.py", "w").write(code)

# B) % formatting
"#%d" % i["number"]

# C) str() concatenation
"#" + str(i["number"])

# D) Avoid dict access in f-strings entirely
n = i["number"]
f"#{n}"
```

### 10.2 GitHub Token Extraction

When `gh` CLI is authenticated in the user's session but not in subprocesses:

```powershell
# Extract token from git credential manager
$token = Write-Output "protocol=https`nhost=github.com`n" | git credential-manager get | Select-String "^password=" | ForEach-Object { $_.ToString().Replace("password=","") }
```

### 10.3 API Direct Calls

Once you have a token, use it directly:

```powershell
$headers = @{ Authorization = "Bearer $token"; Accept = "application/vnd.github+json" }
$body = '{"title":"Issue title","labels":["enhancement"],"body":"Description"}'
Invoke-RestMethod -Uri "https://api.github.com/repos/user/repo/issues" -Method POST -Headers $headers -Body $body -ContentType "application/json"
```

---

## Phase 11: Maintenance Checklist

### Weekly
- [ ] Close stale issues with "not planned"
- [ ] Review open PRs
- [ ] Check CI health

### Per Release
- [ ] Bump version in ALL files (use the checklist in Phase 9)
- [ ] Update CHANGELOG
- [ ] Run full test suite
- [ ] Build installer (if applicable)
- [ ] Tag release: `git tag v0.4.0 && git push --tags`
- [ ] Update wiki
- [ ] Close milestone on GitHub

### Per Quarter
- [ ] Audit dependencies for CVEs
- [ ] Review issue templates for freshness
- [ ] Update CI workflows
- [ ] Refresh README badges
- [ ] Archive old milestones

---

## Anti-Patterns to Avoid

| Anti-Pattern | Fix |
|-------------|------|
| Orphaned issues (no activity 6+ months) | Close or assign |
| No `.gitignore` | Add one matching your stack |
| Stale milestone with all closed issues | Close the milestone |
| Wiki out of sync with code | Update wiki with each release |
| Diverging version references | Use the Version Bump checklist |
| Missing issue templates | Add `.github/ISSUE_TEMPLATE/` |
| No CI | Add `.github/workflows/ci.yml` |
| Token in code | Use `GITHUB_TOKEN` env var |
| `gh` assumed available in subprocesses | Extract token from credential manager instead |
| F-strings with dict access in PowerShell | Use `.py` files or `%d` formatting |
| Wiki not pushed because repo doesn't exist | Create first page via web UI first |
| Only packaging for one AI platform | Use multi-harness: Claude + Cursor + Codex + OpenCode |
