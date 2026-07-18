# CortexStratum — Create GitHub Issues
# Run this from your authenticated gh terminal (at repo root)
# One-liner: pwsh -NoProfile .github\create-issues.ps1

$Repo = "ohmpatel3877/CortexStratum"

# Milestones already exist:
# 1 = v0.3.0 - Polish and Stability (closed)
# 2 = v0.4.0 - Installer Hardening

$Issues = @(
    @{title="Installer: Add Run OpenCode checkbox and CLI flags"; labels=@("enhancement"); milestone=1; body="Post-install checkboxes and CLI --help/--version/--list-tools/--permissive/--debug flags. Implemented in v0.3.0."}
    @{title="Permission Model: Add --permissive flag and document 3 modes"; labels=@("enhancement"); milestone=1; body="--permissive flag, 3-mode hierarchy, README documentation. Implemented in v0.3.0."}
    @{title="Skill Router: Expand 30 to 52 rules with fallback mechanism"; labels=@("enhancement"); milestone=1; body="52 trigger rules, 3-level fallback, user config overrides. Implemented in v0.3.0."}
    @{title="Memory Consolidation: Confidence merging, source priority, dry-run"; labels=@("enhancement"); milestone=1; body="Confidence-based text selection, source priority, dry_run parameter. Implemented in v0.3.0."}
    @{title="In-Code Documentation: Docstrings, memory_store schema, --list-tools"; labels=@("documentation"); milestone=1; body="Full docstrings, memory store schema doc, --list-tools flag. Implemented in v0.3.0."}
    @{title="Test Suite: Fix broken tests, create pipeline + smoke tests"; labels=@("bug"); milestone=1; body="Fixed 8 tool name mismatches, created 157 pipeline tests + 8 smoke tests. Implemented in v0.3.0."}
    @{title="Dud Skill Detection: Cross-reference all 77 router skills"; labels=@("enhancement"); milestone=1; body="0 dud skills found out of 77 references. Automated detection in test-skill-pipeline.py. Implemented in v0.3.0."}
    @{title="Duplicate Router Triggers Cleanup"; labels=@("technical debt"); milestone=2; body="17 duplicate trigger keywords across 52 rules. Deferred to v0.4.0."}
)

Write-Host "Creating $($Issues.Count) issues..." -ForegroundColor Cyan
$Results = $Issues | ForEach-Object -Parallel {
    $issue = $_
    $result = gh issue create `
        --repo "ohmpatel3877/CortexStratum" `
        --title $issue.title `
        --label $($issue.labels -join ",") `
        --milestone $issue.milestone `
        --body $issue.body
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: $($issue.title)" -ForegroundColor Green
        return $result
    } else {
        Write-Host "  FAIL: $($issue.title)" -ForegroundColor Red
        return $null
    }
}
Write-Host "`nDone. $($Results | Where-Object { $_ }).Count / $($Issues.Count) created." -ForegroundColor Cyan
