# Command Reference

Central registry of every CLI command available in ai-memory-core.

## MCP Server

| Command | Description |
|---------|-------------|
| `python scripts/tools-mcp-server.py` | Start MCP server (stdio transport) |
| `python scripts/tools-mcp-server.py --help` | Show usage information |
| `python scripts/tools-mcp-server.py --version` | Show version string |
| `python scripts/tools-mcp-server.py --list-tools` | List all 68 tools as JSON |
| `python scripts/tools-mcp-server.py --permissive` | Start in permissive mode (no permission checks) |
| `python scripts/tools-mcp-server.py --debug` | Start with verbose debug logging |

## Test Suite

| Command | Description | Tests |
|---------|-------------|-------|
| `python scripts/test-mcp-server.py` | MCP protocol tests | 10 |
| `python scripts/test-skill-pipeline.py` | Skill pipeline integrity | 157 |
| `python scripts/test-smoke-server.py` | Server health checks | 8 |
| `python scripts/verifier_middleware.py` | Verifier module tests | 15 |
| `python scripts/memory_search.py` | BM25 engine smoke test | -- |
| `python scripts/trace.py error-status` | Error registry status | -- |
| `python scripts/trace.py decision-status` | Decision registry status | -- |
| `python scripts/trace.py goal-status` | Goal registry status | -- |
| `python scripts/trace.py commitment-list` | Commitment listing | -- |
| `python scripts/guardrails.py` | Safety pipeline demo | -- |
| `python scripts/check-status.py` | Project status summary | -- |

## Build & Install

| Command | Description |
|---------|-------------|
| `iscc opencode-container-server.iss` | Compile Inno Setup installer (.exe) |
| `docker compose up -d` | Start containerized MCP server |
| `pip install -r requirements.txt` | Install Python dependencies |
| `playwright install firefox` | Install Playwright browser (optional) |

## Code Quality

| Command | Description |
|---------|-------------|
| `python -m py_compile scripts/*.py` | Check Python syntax on all scripts |
| `python -c "import json; json.load(open('skills/skill-router.json'))"` | Validate skill router JSON |
| `python -c "import json; json.load(open('package.json'))"` | Validate package.json |

## Trace System (CLI)

| Command | Description |
|---------|-------------|
| `python scripts/trace.py error-log --command <cmd> --error-output <text>` | Log an error |
| `python scripts/trace.py error-search <keyword>` | Search errors |
| `python scripts/trace.py error-status` | Error registry summary |
| `python scripts/trace.py error-resolve --error-signature <sig> --root-cause <t> --resolution <t>` | Resolve an error |
| `python scripts/trace.py decision-add --title <t> --decision <d> --category <c>` | Log a decision |
| `python scripts/trace.py decision-search <keyword>` | Search decisions |
| `python scripts/trace.py goal-init <goal>` | Initialize a goal |
| `python scripts/trace.py goal-status` | Goal progress |
| `python scripts/trace.py commitment-list --session-start` | List pending commitments |
| `python scripts/trace.py commitment-verify <id>` | Verify a commitment |

## Skills & Router

| Command | Description |
|---------|-------------|
| `python scripts/tools-mcp-server.py --list-tools \| python -c "import sys,json; d=json.load(sys.stdin); print(len(d))"` | Count registered tools |
| `python scripts/tools-mcp-server.py --list-tools \| python -c "..."` | Inspect tool permissions |
| View `skills/skill-router.json` | Inspect all 52 trigger rules |

## Memory

| Command | Description |
|---------|-------------|
| `python scripts/memory_search.py` | BM25 engine smoke test |
| View `.memory/ne/memories.json` | Direct memory store inspection |
| View `data/synonyms.json` | Synonym expansion map |

## Utilities

| Command | Description |
|---------|-------------|
| `python scripts/check-status.py` | Project health check |
| `python scripts/task-analyzer.py --task "<desc>" --json` | Complexity analysis |
| `python scripts/task-orchestrator.py` | DAG pipeline executor |
| `python scripts/security-scan.py` | Security audit scan |
| `python scripts/benchmark-harness.py` | Performance benchmark |
| `python scripts/doc-generator.py` | Documentation generator |

## GitHub Actions

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `.github/workflows/ci.yml` | Push/PR to main | 5-stage CI pipeline |
| `.github/workflows/release.yml` | Tag push (v*) | Inno Setup installer build + upload |

## PowerShell Scripts (Legacy)

Located in `scripts/` — being replaced by pure Python equivalents:

| Script | Status | Replacement |
|--------|--------|-------------|
| `check-status.ps1` | Active | `check-status.py` |
| `load-skills.ps1` | Active | `tools-mcp-server.py` (module loader) |
| `consultation-room.ps1` | Active | `trace.py` |
| `inject-identity.ps1` | Active | `identity-manager.py` |
| `logic-verify.ps1` | Active | `verifier_middleware.py` |
| `team-mode.ps1` | Active | `task-orchestrator.py` |
