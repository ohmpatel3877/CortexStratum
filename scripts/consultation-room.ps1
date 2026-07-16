<#
.SYNOPSIS
  Multi-perspective decision analysis for the Consultation Room.
.DESCRIPTION
  Analyzes a decision question from multiple structured perspectives
  (architect, pragmatist, security, minimalist, performance, maintainer)
  and produces a structured report with synthesis and recommendation.
  Integrates with DTrace, Goal Registry, and xTrace.

.PARAMETER Question
  The decision question to analyze (required).
.PARAMETER Perspectives
  Comma-separated list of perspectives (default: architect,pragmatist,security,minimalist).
.PARAMETER LogDecision
  If set, log the final synthesized decision to DTrace via decision-trace.ps1.
.PARAMETER Category
  DTrace category (default: architecture).
.PARAMETER Title
  Decision title (auto-generated from Question if omitted).
.PARAMETER SavePath
  Optional path to save the consultation report JSON.

.EXAMPLE
  .\consultation-room.ps1 -Question "Should we add a Redis cache layer?"

.EXAMPLE
  .\consultation-room.ps1 -Question "Migrate to SQLite?" -Perspectives "architect,security,maintainer" -LogDecision
#>

param(
    [string]$Question,
    [string]$Perspectives = "architect,pragmatist,security,minimalist",
    [switch]$LogDecision,
    [string]$Category = "architecture",
    [string]$Title,
    [string]$SavePath
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DataDir = Join-Path $ProjectRoot "data"

$KnownPerspectives = @("architect", "pragmatist", "security", "minimalist", "performance", "maintainer")

$PerspectiveGuide = @{
    architect   = @{
        label = "Architect"
        questions = @(
            "How does this affect system architecture?",
            "What is the scalability impact?",
            "What are the integration points?",
            "How does it affect component coupling?"
        )
    }
    pragmatist  = @{
        label = "Pragmatist"
        questions = @(
            "What is the simplest working solution?",
            "What is the effort vs. value ratio?",
            "What are the risks of over-engineering?",
            "Can we deliver this incrementally?"
        )
    }
    security    = @{
        label = "Security"
        questions = @(
            "What are the security implications?",
            "What attack vectors exist?",
            "Is there sensitive data exposure?",
            "Does this follow least-privilege principles?"
        )
    }
    minimalist  = @{
        label = "Minimalist"
        questions = @(
            "What is the minimum viable change?",
            "Can we remove complexity?",
            "What is unnecessary here?",
            "Is there a simpler alternative?"
        )
    }
    performance = @{
        label = "Performance"
        questions = @(
            "What is the performance impact?",
            "Where are the bottlenecks?",
            "Is this CPU/memory efficient?",
            "Does it affect latency or throughput?"
        )
    }
    maintainer  = @{
        label = "Maintainer"
        questions = @(
            "How maintainable is this?",
            "Will future developers understand it?",
            "What is the documentation impact?",
            "How testable is this approach?"
        )
    }
}

function Write-Box($title, $lines) {
    $width = ($lines | Measure-Object -Maximum Length).Maximum
    if ($width -lt 40) { $width = 40 }
    $bar = "=" * ($width + 4)
    Write-Host $bar -ForegroundColor Cyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host $bar -ForegroundColor Cyan
    foreach ($line in $lines) {
        Write-Host "  $line"
    }
    Write-Host $bar -ForegroundColor Cyan
}

function Write-Section($title) {
    Write-Host ""
    Write-Host "-- $title " -ForegroundColor Yellow -NoNewline
    Write-Host ("-" * [Math]::Max(1, 60 - $title.Length - 4)) -ForegroundColor DarkGray
}

function Get-Timestamp {
    (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
}

function Get-FileTimestamp {
    (Get-Date).ToString("yyyyMMdd-HHmmss")
}

# ---------- Validate ----------
if (-not $Question) {
    Write-Host "Consultation Room - Multi-Perspective Decision Analysis" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\consultation-room.ps1 -Question ""<decision question>"" [-Perspectives ""architect,pragmatist,security,minimalist,performance,maintainer""]"
    Write-Host "                        [-LogDecision] [-Category <category>] [-Title <title>] [-SavePath <path>]"
    Write-Host ""
    Write-Host "Perspectives:" -ForegroundColor Yellow
    foreach ($kv in $PerspectiveGuide.GetEnumerator() | Sort-Object Name) {
        Write-Host "  $($kv.Value.label) ($($kv.Name))" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "Example:" -ForegroundColor Yellow
    Write-Host "  .\consultation-room.ps1 -Question ""Should we add Redis?"" -Perspectives ""architect,security,maintainer"" -LogDecision"
    exit 0
}

# ---------- Parse and validate perspectives ----------
$SelectedPerspectives = $Perspectives -split ',' | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ -ne '' }
$Invalid = $SelectedPerspectives | Where-Object { $_ -notin $KnownPerspectives }
if ($Invalid) {
    Write-Error "Unknown perspective(s): $($Invalid -join ', '). Valid options: $($KnownPerspectives -join ', ')"
    exit 1
}
if ($SelectedPerspectives.Count -eq 0) {
    Write-Error "At least one perspective is required"
    exit 1
}

$DecisionTitle = if ($Title) { $Title } else { "Decision: $Question" }

$Now = Get-Timestamp
$ReportId = "cr-$(Get-FileTimestamp)"

Write-Host ""
Write-Box "CONSULTATION ROOM" @(
    "Question:   $Question",
    "Date:       $Now",
    "Session:    $ReportId",
    "Categories: $($SelectedPerspectives -join ', ')",
    "Title:      $DecisionTitle"
)

# ---------- Generate analysis per perspective ----------
$Analyses = @()

foreach ($p in $SelectedPerspectives) {
    $guide = $PerspectiveGuide[$p]
    Write-Section "$($guide.label) ($p) Analysis"

    $considerations = @()
    foreach ($q in $guide.questions) {
        $considerations += @{ question = $q; notes = "" }
        Write-Host "  [$($guide.label)] $q" -ForegroundColor DarkGray
    }

    $analysis = @{
        perspective    = $p
        label          = $guide.label
        considerations = $considerations
        recommendation = ""
    }
    $Analyses += $analysis
}

# ---------- Build Comparison Table ----------
Write-Section "Perspective Comparison"
$header = "Perspective".PadRight(16)
$alignCol = "Alignment / Conflict"
Write-Host ("  " + $header + " | " + $alignCol) -ForegroundColor Yellow
Write-Host ("  " + ("-" * 16) + "-+-" + ("-" * $alignCol.Length)) -ForegroundColor DarkGray

for ($i = 0; $i -lt $Analyses.Count; $i++) {
    for ($j = $i + 1; $j -lt $Analyses.Count; $j++) {
        $left = $Analyses[$i].label.PadRight(14)
        $right = $Analyses[$j].label
        Write-Host ("  $left <-> $right  | Complementary perspectives (awaiting human input)") -ForegroundColor DarkGray
    }
}
Write-Host "  (Enter your analysis per perspective in the generated JSON report)" -ForegroundColor DarkGray

# ---------- Synthesis ----------
Write-Section "Synthesis & Summary"
Write-Host "  Perspectives analyzed: $($SelectedPerspectives.Count)" -ForegroundColor Green
Write-Host "  Question scope:        $(if ($Question.Length -gt 60) { $Question.Substring(0,60) + '...' } else { $Question })" -ForegroundColor Green
Write-Host "  Suggested decision:    (awaiting human synthesis of perspectives)" -ForegroundColor Yellow

$Summary = @"
  The Consultation Room has prepared $($SelectedPerspectives.Count) perspective analyses for:
    "$Question"

  To complete the decision:
    1. Review each perspective's guiding questions
    2. Fill in your notes in the saved JSON report
    3. Write your recommendation per perspective
    4. Synthesize a final decision

  Run with -LogDecision once you have synthesized your decision.
"@

# ---------- Save Report ----------
$Report = @{
    id          = $ReportId
    question    = $Question
    title       = $DecisionTitle
    date        = $Now
    perspectives = $SelectedPerspectives
    analyses    = $Analyses
    synthesis   = @{
        summary           = "Synthesis pending human review of $($SelectedPerspectives.Count) perspectives"
        recommended_action = ""
        conflicts         = @()
    }
    log_decision = $LogDecision.IsPresent
    category     = $Category
}

$ReportDir = $DataDir
if ($SavePath) {
    $ReportDir = Split-Path $SavePath -Parent
    if (-not (Test-Path $ReportDir)) {
        try {
            New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
        } catch {
            Write-Error "Cannot create save directory: $ReportDir"
            exit 1
        }
    }
} else {
    if (-not (Test-Path $DataDir)) {
        New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    }
}

$ReportPath = if ($SavePath) { $SavePath } else { Join-Path $DataDir "consultation-$($ReportId).json" }
try {
    $json = $Report | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($ReportPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Host ""
    Write-Host "Report saved: $ReportPath" -ForegroundColor Green
} catch {
    Write-Error "Failed to save report: $_"
    # Log to error-trace compatible format
    Write-Host "[xTrace] err | consultation-room.ps1 | Save report failed | $_"
}

# ---------- Goal Alignment Check ----------
$GoalScript = Join-Path $ScriptDir "goal-registry.ps1"
if (Test-Path $GoalScript) {
    Write-Host ""
    Write-Host "[consultation] Checking goal alignment..." -ForegroundColor DarkGray
    $goalOutput = & $GoalScript -Action CheckAlignment -CurrentAction "Consultation: $Question" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[consultation] Goal registry not active (run .\goal-registry.ps1 -Action Init -Goal '$Question' first)" -ForegroundColor DarkGray
    } else {
        Write-Host $goalOutput -ForegroundColor DarkGray
    }
}

# ---------- DTrace Logging ----------
if ($LogDecision) {
    $DtScript = Join-Path $ScriptDir "decision-trace.ps1"
    if (Test-Path $DtScript) {
        Write-Host ""
        Write-Host "[consultation] Logging decision to DTrace..." -ForegroundColor DarkGray
        try {
            & $DtScript -Action Add -Title $DecisionTitle -Context $Question -Category $Category
            Write-Host "[consultation] Decision logged successfully" -ForegroundColor Green
        } catch {
            Write-Host "[consultation] Failed to log decision: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "[consultation] decision-trace.ps1 not found at $DtScript" -ForegroundColor Red
    }
}

# ---------- DTrace-compatible output ----------
if ($LogDecision) {
    Write-Host ""
    Write-Host "--- DTrace Output ---" -ForegroundColor Magenta
    Write-Host "Action: Add"
    Write-Host "Title: $DecisionTitle"
    Write-Host "Context: $Question"
    Write-Host "Category: $Category"
    Write-Host "Perspectives: $($SelectedPerspectives -join ', ')"
}

Write-Host ""
Write-Host "Consultation complete. Review the report at $ReportPath" -ForegroundColor Cyan
Write-Host "Strongly consider running: .\decision-trace.ps1 -Action Add -Title ""$DecisionTitle"" -Context ""$Question"" -Category $Category" -ForegroundColor Yellow
