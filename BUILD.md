# Build Pipeline

## Overview

```

                  CortexStratum Build Pipeline                    

                                                                   
                
    Source     Python      Test     Package    
    Code           Compile        Suite                    
                
                                                              
                                                              
  *.py files      py_compile     5 test suites     Inno Setup     
  skill files     passes all     all pass         .exe output     
  JSON config     syntax check                                      
  .iss script                                                      

```

## Prerequisites

### Required
- **Python 3.10+** — https://python.org
- **Git** — https://git-scm.com

### For Installer Build (Windows only)
- **Inno Setup 6+** — https://jrsoftware.org/isdl.php
- Add `iscc` to PATH (default: `C:\Program Files (x86)\Inno Setup 6\`)

### For Full Test Suite
- `playwright install firefox` (for sensory module browser tests)
- `pip install pdfplumber trafilatura beautifulsoup4 pytesseract Pillow requests` (optional modules)

## Quick Start

```powershell
# Clone
git clone https://github.com/ohmpatel3877/CortexStratum.git
cd CortexStratum

# Install dev tools (optional)
pip install ruff

# Lint all Python files
ruff check . --exclude .build-venv --exclude build --exclude dist

# Verify Python syntax
python -m py_compile scripts/tools-mcp-server.py
python -m py_compile scripts/memory_search.py
python -m py_compile scripts/verifier_middleware.py
python -m py_compile scripts/trace.py
python -m py_compile scripts/sensory-module.py

# Run all test suites
python scripts/test-mcp-server.py           # 10 MCP protocol tests
python scripts/memory_search.py             # SQLite+FTS5 memory engine smoke test
python scripts/verifier_middleware.py       # 15 verifier tests
python scripts/test-skill-pipeline.py       # 157 skill pipeline tests
python scripts/test-smoke-server.py         # 8 server health checks

# Check CLI flags
python scripts/tools-mcp-server.py --help
python scripts/tools-mcp-server.py --version
python scripts/tools-mcp-server.py --list-tools

# Start server (interactive mode)
python scripts/tools-mcp-server.py

# Start server (permissive mode — all tools allowed)
python scripts/tools-mcp-server.py --permissive

# Start server (debug logging)
python scripts/tools-mcp-server.py --debug
```

## Build Pipeline Stages

### Stage 1: Source Code

All Python source code is in `scripts/`. The core structure:

| File | Purpose | Dependencies |
|------|---------|-------------|
| `tools-mcp-server.py` | MCP server (176 tools, permission guard, CLI flags) | stdlib only |
| `memory_search.py` | SQLite+FTS5 engine (add, search, synthesize, consolidate) | stdlib only (sqlite3) |
| `trace.py` | Error/decision/goal/commitment registry | stdlib only |
| `verifier_middleware.py` | Pre/post tool verification + renudge signals | guardrails.py |
| `guardrails.py` | Prompt injection, PII redaction, provenance | stdlib only |
| `sensory-module.py` | Web browsing (Playwright), PDF, OCR, API, RSS | optional 3rd party |
| `coder-module.py` | Code analysis, review, debug, framework gen | optional 3rd party |
| `art-module.py` | SVG generation, color themes | stdlib only |
| `audio-module.py` | WAV analysis, tone generation, music theory | stdlib only |
| `literature-module.py` | Text analysis, concepts, study guides | stdlib only |
| `devops-module.py` | Container debug, compose, Samba, network | stdlib only |
| `game-dev-module.py` | Game design analysis, scaffolding | stdlib only |

### Stage 2: Python Compile Check

Every Python file must pass `py_compile`:

```powershell
# Batch check all scripts
Get-ChildItem scripts/*.py | ForEach-Object {
    python -m py_compile $_.FullName
    if ($LASTEXITCODE -eq 0) { Write-Host "OK: $_" -ForegroundColor Green }
}
```

### Stage 3: Test Suite

**5 test suites** must all pass before release:

#### Suite 1: MCP Protocol (`test-mcp-server.py`)
- 10 tests: initialize, tools/list, tools/call (8 tool types), unknown tool, unknown method
- **Expected: 10/10 pass**

#### Suite 2: BM25 Engine (`memory_search.py`)
- Smoke test: add, search, synthesize, consolidate, status
- No formal test assertions (demonstration mode)

#### Suite 3: Verifier Middleware (`verifier_middleware.py`)
- 15 tests: pre_verify (clean, injection, secrets), post_verify, security, fingerprint/drift, renudge, thread safety, limbic inhibition
- **Expected: ALL TESTS PASSED**

#### Suite 4: Skill Pipeline (`test-skill-pipeline.py`)
- 157 tests across 5 sub-suites:
  1. Local skill file validation (12 skills)
  2. Router structure (52 rules, schema, defaults)
  3. End-to-end matching (10 task descriptions)
  4. Dud skill detection (77 skill references cross-checked)
  5. MCP tool inventory (176 tools, naming conventions, permissions)
- **Expected: 157/157 pass, 0 dud skills**

#### Suite 5: Smoke Test (`test-smoke-server.py`)
- 8 tests: initialize, tools/list, ping, health, skill_router_match, memory_status, error handling
- **Expected: 8/8 pass**

### Stage 4: Installer Build (Windows)

```powershell
# Compile Inno Setup installer
iscc .\opencode-container-server.iss

# Output: opencode-container-server-setup.exe
```

The installer:
1. Checks for Docker Desktop (installs if missing)
2. Downloads skill modules from GitHub (component-selectable)
3. Builds and starts the MCP server container
4. Creates Start Menu shortcuts
5. Offers "Launch OpenCode" and "Open verification terminal" post-install options

### Stage 5: Release

1. Update `VERSION` file
2. Update `CHANGELOG.md`
3. Run all 5 test suites
4. Build installer (Windows)
5. Tag release: `git tag v{VERSION} && git push --tags`
6. Create GitHub Release with:
   - Built installer `.exe`
   - CHANGELOG entry
   - Test results summary

## GitHub Actions CI (Recommended)

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Check syntax
        run: |
          python -m py_compile scripts/tools-mcp-server.py
          python -m py_compile scripts/memory_search.py
          python -m py_compile scripts/verifier_middleware.py
          python -m py_compile scripts/trace.py
      - name: Run tests
        run: |
          python scripts/test-mcp-server.py
          python scripts/verifier_middleware.py
          python scripts/test-skill-pipeline.py

  build-installer:
    runs-on: windows-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - name: Install Inno Setup
        run: choco install innosetup -y
      - name: Build installer
        run: iscc opencode-container-server.iss
      - uses: actions/upload-artifact@v4
        with:
          name: installer
          path: opencode-container-server-setup.exe
```

## File Inventory

| Path | Purpose | Auto-generated? |
|------|---------|----------------|
| `scripts/*.py` | Python source | No |
| `skills/*/SKILL.md` | Skill definitions | No |
| `data/*.json` | Persistent state (error registry, decisions, goals, commitments) | Yes — created at runtime |
| `.memory/ne/memories.json` | BM25 memory entries | Yes — created at runtime |
| `.memory/ne/data/synonyms.json` | Synonym expansion map | No |
| `docs/memory-store-schema.md` | Memory store JSON schema | No |
| `docs/issue-backlog.md` | GitHub issue templates | No |

## Versioning

Version is tracked in two places:
1. `VERSION` file — plain text, single line (e.g., `1.3.0`)
2. `scripts/tools-mcp-server.py` — `VERSION = "1.3.0"` constant

Update both on every release. Releases follow [SemVer](https://semver.org/).
