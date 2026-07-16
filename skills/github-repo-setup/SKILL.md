# GitHub Repository Setup & Integration

Comprehensive guide for configuring, documenting, and populating GitHub repositories
and integrating them with OpenCode.

## When to Use

Use this skill when:
- Setting up a new GitHub repository from scratch
- Populating an existing repo with CI, issues, milestones, wiki
- Configuring OpenCode integration for a project
- Creating project boards, issue templates, and automation
- Need to audit or improve a repo's GitHub presence

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
| `LICENSE` | MIT, Apache 2.0, GPL — pick one | ✅ Yes |
| `.gitignore` | Ignore build artifacts, deps, secrets | ✅ Yes |
| `CHANGELOG.md` | Keep a Changelog format | Recommended |
| `VERSION` | Plain-text single-line version | Recommended |
| `BUILD.md` | Build pipeline documentation | Recommended |
| `COMMANDS.md` | Central command registry | For CLIs |
| `MILESTONES.md` | Project roadmap with dates | Recommended |
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
```

### 1.4 `VERSION` File

Single line, SemVer pre-1.0:
```
0.3.0
```

All version references must stay in sync:
- `VERSION` file
- `package.json` → `"version"`
- Installer script (e.g., `#define MyAppVersion`)
- CLI `--version` constant
- Plugin configs (`.claude-plugin/plugin.json`, `opencode.json`)

---

## Phase 2: OpenCode Integration

### 2.1 MCP Server Registration

Create `opencode.json` in repo root:

```json
{
  "mcpServers": {
    "my-server": {
      "name": "my-server",
      "description": "Description of what it does",
      "command": "python",
      "args": ["scripts/server.py"],
      "env": {}
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

### 2.2 OpenCode Agent Definitions

Create `.opencode/agents.md`:

```markdown
# Project Agents

### @agent-name
**Purpose**: What this agent does
**Skills**: skill1, skill2
**Tools**: tool1, tool2
**Behavior**: How it should behave
```

### 2.3 Active Skills

Create `.opencode/active-skills.json`:

```json
[
    "skill-name-1",
    "skill-name-2",
    "skill-name-3"
]
```

### 2.4 Global Config Integration

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
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: pytest
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

Create `.github/ISSUE_TEMPLATE/` directory with:

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

---

## Phase 4: Issues & Milestones

### 4.1 Create Milestones

```bash
# Via GitHub API
gh api repos/<user>/<repo>/milestones \
  --field title="v0.1.0 - Foundation" \
  --field description="Core features" \
  --field due_on="2026-08-01T00:00:00Z"

# Common milestones:
# v0.1.0 - Foundation
# v0.2.0 - Expansion
# v0.3.0 - Polish & Stability
# v1.0.0 - Stable Release
```

### 4.2 Create Issues from Backlog

```bash
# Single issue
gh issue create \
  --title "Feature title" \
  --label enhancement \
  --milestone "v0.3.0 - Polish & Stability" \
  --body "Description"

# Bulk via script (create create-issues.ps1):
# See .github/create-issues.ps1 for template
```

### 4.3 Issue Lifecycle

```
[Open] → Assigned → [In Progress] → PR → [Review] → Merge → [Closed]
                                    ↘ [Failed CI] → Fix → [In Progress]
```

Use these labels:
- `bug` — something is broken
- `enhancement` — new feature or request
- `documentation` — docs improvement
- `technical debt` — code quality
- `good first issue` — onboarding
- `help wanted` — community contribution

---

## Phase 5: Wiki

### 5.1 Initialize

```bash
# Enable wiki in repo settings (has_wiki: true), then:
git clone https://github.com/<user>/<repo>.wiki.git
cd <repo>.wiki
```

### 5.2 Essential Pages

| Page | Content |
|------|---------|
| `Home.md` | Overview, quick links to all pages |
| `Getting-Started.md` | Prerequisites, quick start, verification |
| `Architecture.md` | System design, data flow, components |
| `API-Reference.md` | All endpoints, tools, functions |
| `Configuration.md` | Config files, environment variables |
| `Troubleshooting.md` | Common issues and fixes |
| `Contributing.md` | Dev workflow, PR process, code style |

### 5.3 Wiki Links

Use `[[Page-Name|Display Text]]` for internal links.

```markdown
# Home
- [[Getting-Started|Getting Started]]
- [[API-Reference|API Reference]]
- [[Troubleshooting|Troubleshooting]]
```

### 5.4 Push Wiki

```bash
cd <repo>.wiki
git add -A
git commit -m "Initialize wiki"
git push origin master
```

> **Note**: The wiki repo is created automatically when you create the first wiki page on GitHub. If the push fails, create one page via the GitHub web UI first.

---

## Phase 6: Badges & Visual Design

### 6.1 Shield Badges for README

Add to `docs/badges/`:
- Version badge
- Build status (CI)
- License badge
- Tool count badge
- Permission model badge

Use SVG shields.io-style badges or create custom SVGs.

### 6.2 Dashboard

Create `dashboard.html` with:
- **Stats bar**: tool count, memory, errors, decisions, goals, OpenCode status
- **Tabs**: Tools, Trace, Decisions, Goals, Commitments, OpenCode integration
- **Data sources**: JSON files in `data/` directory
- **Style**: Dark theme, monospace, professional

### 6.3 README Structure

```markdown
# Project Title

Badges row (version, CI, license, tools)

## Overview
1-2 paragraphs

## Quick Start
Code blocks

## Architecture
ASCII diagram or mermaid

## Features
Bullet list

## Installation
Prerequisites + commands

## Configuration
Links to config docs

## Project Structure
Directory tree

## Related Projects
Links

## License
```

---

## Phase 7: Versioning Convention

### Pre-1.0 Convention

| Version | Meaning |
|---------|---------|
| `0.1.0` | Initial foundation |
| `0.2.0` | Feature expansion |
| `0.3.0` | Polish, testing, docs |
| `0.4.0`+ | Iterative improvements |
| `1.0.0` | Stable release |

- **0.x.0** minor bumps can include breaking changes
- **0.0.x** patches for bug fixes only
- Keep `VERSION`, `package.json`, `CHANGELOG.md`, and all configs in sync

### Bump Process

```bash
# 1. Update VERSION
echo "0.4.0" > VERSION

# 2. Update CHANGELOG.md with new entry

# 3. Update all config files (package.json, opencode.json, etc.)

# 4. Update Python constant
# In scripts/*.py: VERSION = "0.4.0"

# 5. Commit and tag
git add VERSION CHANGELOG.md package.json
git commit -m "bump version 0.3.0 → 0.4.0"
git tag v0.4.0
git push --tags
```

---

## Phase 8: Maintenance Checklist

### Weekly
- [ ] Close stale issues with "not planned"
- [ ] Review open PRs
- [ ] Check CI health

### Per Release
- [ ] Bump version in all files
- [ ] Update CHANGELOG
- [ ] Run full test suite
- [ ] Build installer (if applicable)
- [ ] Tag release
- [ ] Update wiki
- [ ] Close milestone on GitHub

### Per Quarter
- [ ] Audit dependencies for CVEs
- [ ] Review issue templates for freshness
- [ ] Update CI workflows
- [ ] Refresh README badges

---

## Anti-Patterns to Avoid

| Anti-Pattern | Fix |
|-------------|-----|
| Orphaned issues (no activity 6+ months) | Close or assign |
| No `.gitignore` | Add one matching your stack |
| Stale milestone with closed issues only | Close the milestone |
| Wiki out of sync with code | Update wiki with each release |
| Multiple diverging version references | Write a version sync script |
| Missing issue templates | Add `.github/ISSUE_TEMPLATE/` |
| No CI | Add `.github/workflows/ci.yml` |
| Token in code | Use `GITHUB_TOKEN` env var |
