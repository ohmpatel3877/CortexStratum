# Memory Evaluation & Gap Analysis

**One-shot command**: `/mem eval [project]`

Automates the catalog → gap analysis → registration pipeline that previously
required 15+ manual steps. Run at session end to ensure procedural memory
stays in sync with actual work done.

---

## Workflow

### Phase 1: Catalog (60s)

Run these queries in parallel:

```python
# Query all memory tiers
query_agent_memory(query="session record resolved case behavioral rule", top_k=50)
query_agent_memory(query="code_preference architectural_rule task_learning", top_k=50)

# Wiki pages
wiki_list()

# Tool usage
get_tool_stats(days=7)
```

Then from git:

```bash
# Last N commits
git log --oneline -30

# Changed files in current session
git diff --stat HEAD

# Uncommitted changes
git status --short
```

### Phase 2: Gap Analysis (30s)

Cross-reference the catalog against these heuristics:

| Check | Rule | Action if Missing |
|-------|------|-------------------|
| Resolved bugs ↔ git fix commits | Every `fix:` commit should have a `register_resolved_case` | Register any missing |
| Session records ↔ git commits | Every session should have a `session_record` | Create engram session |
| Behavioral rules ↔ recurring errors | Same error 3+ times should have an inhibition | Register inhibition |
| Code preferences ↔ project conventions | Undocumented patterns should be persisted | `wiki_write` a convention |
| Wiki pages ↔ features added | `feat:` commits should have a wiki entry | Create wiki page |

### Phase 3: Registration (automated)

For each gap found, call:

```
register_resolved_case(
    error_signature="<pattern from git commit>",
    task_type="bug_fix|refactor|feature_implementation",
    resolution_steps=[...],
    before_context="...",
    after_context="...",
    source_session_id="<current session>",
    tags=["<auto-detected>"]
)
```

### Phase 4: Consolidate

```
# Run dream cycle to link related cases
dream_cycle(phase="nap")

# Deduplicate any merged cases
dedup_cases()

# Run behavioral analysis
analyze_behavioral_patterns()
```

---

## Verbosity Levels

- `/mem eval quick` — Phase 1 only (stats summary)
- `/mem eval` — Phases 1+2 (catalog + gaps)
- `/mem eval deep` — Phases 1+2+3+4 (catalog + gaps + register + consolidate)

---

## Trigger Keywords

memory evaluation, catalog memories, gap analysis, sync memory, register bugs,
procedural audit, session memory audit, memory health check, mem eval

---

## Automation Script

For `/mem eval auto`, run:

```powershell
# 1. Check git for unregistered fixes
$fixes = git log --oneline --grep="fix:" main..HEAD 2>$null
if ($fixes) { Write-Warning "Unregistered fixes: $fixes" }

# 2. Check session record exists
# (agent handles MCP calls internally)

# 3. Summarize findings to user
Write-Output "Evaluation complete. N gaps found."
```
