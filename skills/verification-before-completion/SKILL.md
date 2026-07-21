# Verification-Before-Completion

**Use when**: Running `/verify`, `/check`, or any pre-commit/CI/quality gate workflow. Also triggered by keywords: "verify", "validate", "check", "quality", "gate", "pre-commit", "ci", "lint", "typecheck".

**Do NOT use when**: Debugging a specific error (use `troubleshooting-master`), running unit tests (use `test-driven-development`).

## What This Skill Does

Runs the full CortexStratum verification gate to ensure code quality before committing or completing a task. This skill connects the **skill router** → **MCP verifier tools** → **local verification scripts** into one workflow.

## Verification Workflow

### Step 1: Lint with Ruff

```powershell
ruff check .
```

Fixes common issues automatically where possible. If errors remain, list them for the user.

### Step 2: Syntax Check

```powershell
Get-ChildItem -Recurse -Filter *.py -Exclude *.build-venv* | ForEach-Object { python -m py_compile $_.FullName }
```

### Step 3: MCP Protocol Compliance

```powershell
python scripts/test-mcp-server.py
```

Expected: **10/10 passed**

### Step 4: Skill Router Integrity

```powershell
python scripts/test-skill-pipeline.py
```

Catches dangling skill references. Expected: **all tests pass, no duds**

### Step 5: Verifier Middleware

```powershell
python scripts/verifier_middleware.py
```

Expected: **ALL TESTS PASSED**

### Step 6: Tool Count Check

```powershell
python scripts/tools-mcp-server.py --list-tools | python -c "import sys,json; tools=json.load(sys.stdin); print(f'{len(tools)} tools'); assert len(tools) >= 120"
```

### Step 7: Persist Results to Registry

After all checks pass, log the successful verification to persist it across sessions:

```powershell
# Log a milestone event
# Use write_hooks_observe with event_type="milestone" to record the verification
```

This records the verification completion in `data/decision-registry.json` so the commitment checker can track it.

### Step 8: Verifier MCP Tools

Use the verifier middleware tools to check current state:
- `read_verifier_status` — check current verifier state and any active renudges
- `read_audit_status` — check permission audit trail
- `read_xtrace_status` — check error registry health

## MCP Tools Used

| Tool | When |
|------|------|
| `read_verifier_status` | Before/after changes to check middleware state |
| `write_verifier_renudge` | Apply correction when verifier flags an issue |
| `write_verifier_clear_renudge` | Clear resolved renudges |
| `read_audit_status` | Verify permission audit trail |
| `read_commitment_checker_list` | Check pending commitments before finishing |

## Common Fixes

| Issue | Fix |
|-------|-----|
| Ruff lint errors | Run `ruff check --fix .` to auto-fix, review remaining |
| Syntax error | Fix the reported file, re-run py_compile |
| MCP test failure | Check tools-mcp-server.py for recent changes |
| Skill pipeline duds | Ensure all referenced skills have SKILL.md files |
| Verifier rejection | Call `write_verifier_renudge` with correction, then retry |
