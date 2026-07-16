# .mem0.md Generator - Creates per-project mem0 configuration
# Usage: .\scripts\generate-config.ps1 -ProjectName "my-project" -Description "My project description" -OutputPath "..\my-project\.mem0.md"

param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectName,

    [Parameter(Mandatory = $false)]
    [string]$Description = "No description provided",

    [Parameter(Mandatory = $false)]
    [string]$OutputPath,

    [Parameter(Mandatory = $false)]
    [switch]$Force
)

# Default output: project root
if (-not $OutputPath) {
    $OutputPath = ".\$ProjectName\.mem0.md"
}

# Check if file exists
if ((Test-Path $OutputPath) -and (-not $Force)) {
    $confirm = Read-Host "File $OutputPath exists. Overwrite? [y/N]"
    if ($confirm -ne 'y' -and $confirm -ne 'Y') {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# Ensure directory exists
$parentDir = Split-Path $OutputPath -Parent
if ($parentDir) {
    New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
}

$config = @"
# mem0 Configuration for $ProjectName

## Project
Project: $ProjectName
Description: $Description
Version: 1.0.0

## Custom Instructions

When extracting memories from conversations in this project:

1. Capture ALL architecture decisions with rationale and alternatives considered. Tag as architecture_decisions.
2. For every bug fix, store the root cause (not just the symptom) and the exact fix. Tag as bug_fixes.
3. Capture coding conventions the moment they're stated or discovered. Tag as coding_conventions.
4. Track user preferences about tools, workflows, and output format. Tag as user_preferences.
5. Store anti-patterns immediately when something fails or is ruled out. Tag as anti_patterns.
6. Capture task learnings for any multi-step process that took >3 steps. Tag as task_learnings.
7. For any technology decision, store WHY it was chosen over alternatives. Tag as architecture_decisions.
8. Extract session summaries at natural break points. Tag as session_summaries.
9. Always include the relevant file paths, function names, and module names in memories so they're searchable by code location.
10. When storing performance-related memories, include before/after metrics if available.

## Retention

architecture_decisions: null       # Keep forever (pinned)
coding_conventions: null           # Keep forever (pinned)
user_preferences: null             # Keep forever (pinned)
anti_patterns: 365                 # 1 year
bug_fixes: 365                     # 1 year
task_learnings: 180                # 6 months
session_state: 90                  # 3 months
session_summaries: 180             # 6 months
environmental: 90                  # 3 months

## Categories

- architecture_decisions: Design choices, technology selections, and trade-off analyses
- coding_conventions: Code style, naming, project structure, and linting rules
- user_preferences: Tool preferences, workflow habits, output format preferences
- anti_patterns: Things that failed, reasons why, and what to do instead
- bug_fixes: Root causes, reproduction steps, and exact fixes
- task_learnings: Multi-step workflow insights and process optimizations
- session_state: Ephemeral state for current session continuity
- session_summaries: High-level summaries of completed sessions
- environmental: Tooling setup, config changes, and environment specifics
- security: Security decisions, vulnerabilities, and hardening steps
- api_design: API contract decisions, endpoints, and data models
- performance: Performance metrics, bottlenecks, and optimizations
- testing: Testing strategies, test patterns, and coverage decisions
- deployment: Deployment config, CI/CD, and infrastructure decisions
- dependencies: Package choices, versions, and dependency management
- monitoring: Observability, logging, and alerting decisions

## Search

rerank: true
hybrid_search: true
similarity_threshold: 0.6
max_results: 10
"@

$config | Out-File -FilePath $OutputPath -Encoding utf8
Write-Host "Created $OutputPath" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. OpenCode will auto-detect this .mem0.md next session"
Write-Host "  2. Run your first task from $ProjectName directory"
Write-Host "  3. Memories will be scoped under app_id=$ProjectName"
