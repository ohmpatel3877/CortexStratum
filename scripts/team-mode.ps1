param(
    [Parameter(Mandatory)]
    [string]$Task,
    [string]$Roles = "architect,coder,reviewer",
    [switch]$LogDecision,
    [switch]$Verbose
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DataDir = Join-Path $ProjectRoot "data"

$RoleDefinitions = @{
    architect   = @{
        label    = "Architect"
        color    = "Cyan"
        prompt   = "You are a software architect. Analyze the following task from an architectural perspective. Consider: system design, scalability, component boundaries, data flow, tradeoffs, and integration points. Output a concise architectural plan with numbered recommendations."
    }
    coder       = @{
        label    = "Coder"
        color    = "Green"
        prompt   = "You are an implementation engineer. For the following task, produce working code or detailed pseudocode. Focus on: correctness, idiomatic patterns, error handling, and clarity. Output the implementation with file paths and key code blocks."
    }
    reviewer    = @{
        label    = "Reviewer"
        color    = "Yellow"
        prompt   = "You are a code reviewer. Review the following task and any associated implementation for: bugs, security vulnerabilities, performance issues, edge cases, and maintainability concerns. Output a bulleted findings list with severity (HIGH/MED/LOW)."
    }
    tester      = @{
        label    = "Tester"
        color    = "Magenta"
        prompt   = "You are a QA engineer. For the following task, design a test strategy covering: unit tests, integration tests, edge cases, and failure scenarios. Output specific test cases with expected outcomes."
    }
    debugger    = @{
        label    = "Debugger"
        color    = "Red"
        prompt   = "You are a debugger. For the following task, identify potential root causes of failure, common pitfalls, and runtime risks. Output a root-cause analysis with probable fixes ranked by likelihood."
    }
    documenter  = @{
        label    = "Documenter"
        color    = "Blue"
        prompt   = "You are a technical writer. For the following task, produce documentation covering: purpose, usage, API surface, configuration, and examples. Output in markdown format."
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

# ---------- validate ----------
if (-not $Task) {
    Write-Host "Team Mode - Parallel Multi-Agent Orchestration" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\team-mode.ps1 -Task ""<task description>"" [-Roles ""architect,coder,reviewer,tester,debugger,documenter""] [-LogDecision] [-Verbose]"
    Write-Host ""
    Write-Host "Available roles:"
    foreach ($kv in $RoleDefinitions.GetEnumerator() | Sort-Object Name) {
        Write-Host "  $($kv.Value.label) ($($kv.Name))" -ForegroundColor $kv.Value.color
    }
    exit 0
}

$SelectedRoles = $Roles -split ',' | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ -ne '' }
$Invalid = $SelectedRoles | Where-Object { $_ -notin $RoleDefinitions.Keys }
if ($Invalid) {
    Write-Error "Unknown role(s): $($Invalid -join ', '). Valid: $($RoleDefinitions.Keys -join ', ')"
    exit 1
}

$StartTime = Get-Date
$ReportId = "team-$(Get-FileTimestamp)"
$Now = Get-Timestamp

Write-Host ""
$boxLines = @(
    "Task:         $Task",
    "Roles:        $($SelectedRoles -join ', ')",
    "Started:      $Now",
    "Report ID:    $ReportId"
)
Write-Box "TEAM MODE -- Parallel Execution" $boxLines

# ---------- generate role-specific workbooks ----------
$Workbooks = @{}
foreach ($role in $SelectedRoles) {
    $def = $RoleDefinitions[$role]
    $workbook = @"
## Role: $($def.label) ($role)

Task:
$Task

$($def.prompt)

Respond with your analysis. Use clear sections and bullet points.
"@
    $Workbooks[$role] = $workbook
}

# ---------- Goal alignment check ----------
$GoalScript = Join-Path $ScriptDir "goal-registry.ps1"
$GoalActive = $false
if (Test-Path $GoalScript) {
    if ($Verbose) { Write-Host "[team] Checking goal alignment..." -ForegroundColor DarkGray }
    $goalOutput = & $GoalScript -Action CheckAlignment -CurrentAction "Team Mode: $Task" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $GoalActive = $true
        if ($Verbose) { Write-Host "[team] Goal aligned" -ForegroundColor Green }
    } else {
        if ($Verbose) { Write-Host "[team] No active goal registry" -ForegroundColor DarkGray }
    }
}

# ---------- spawn parallel subagents ----------
$Results = @{}
$Pids = @{}

foreach ($role in $SelectedRoles) {
    $def = $RoleDefinitions[$role]
    $workbook = $Workbooks[$role]

    Write-Host ""
    Write-Host ">> Spawning $($def.label)..." -ForegroundColor $def.color

    $TempFile = Join-Path $DataDir "team-${ReportId}-${role}.txt"
    if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir -Force | Out-Null }

    $encodedTask = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($workbook))
    $runnerContent = @'
$b64 = '@encoded_task@'
$task = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
$output = @"
$task
"@
$output | Out-File -FilePath '@tempfile@' -Encoding UTF8
'@
    $runnerContent = $runnerContent.Replace('@encoded_task@', $encodedTask)
    $runnerContent = $runnerContent.Replace('@tempfile@', $TempFile)

    $tempPs1 = Join-Path $DataDir "team-${ReportId}-${role}-runner.ps1"
    $runnerContent | Set-Content -Path $tempPs1 -Encoding UTF8

    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "pwsh"
        $psi.Arguments = "-NoProfile -File `"$tempPs1`""
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true

        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        $proc.Start() | Out-Null

        $Pids[$role] = @{ Process = $proc; TempFile = $TempFile; RunnerScript = $tempPs1 }
        Write-Host "  PID: $($proc.Id)" -ForegroundColor DarkGray

        if ($Verbose) {
            $shortTask = if ($Task.Length -gt 40) { $Task.Substring(0, 37) + "..." } else { $Task }
            Write-Host "  [verbose] spawned: $role / $shortTask" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "  FAILED to spawn $role`: $_" -ForegroundColor Red
        $Results[$role] = "ERROR: $_"
    }
}

# ---------- wait for all roles ----------
if ($Pids.Count -gt 0) {
    Write-Host ""
    Write-Host ">> Waiting for $($Pids.Count) agent(s) to complete..." -ForegroundColor DarkGray

    foreach ($role in $Pids.Keys) {
        $info = $Pids[$role]
        $def = $RoleDefinitions[$role]
        try {
            $info.Process.WaitForExit(120000) | Out-Null
            if ($info.Process.HasExited) {
                Write-Host "  $($def.label) completed (exit: $($info.Process.ExitCode))" -ForegroundColor Green
            } else {
                Write-Host "  $($def.label) timed out (120s)" -ForegroundColor Red
                $info.Process.Kill() | Out-Null
            }
        } catch {
            Write-Host "  $($def.label) wait failed: $_" -ForegroundColor Red
        }

        if (Test-Path $info.TempFile) {
            $content = Get-Content $info.TempFile -Raw -Encoding UTF8
            $Results[$role] = if ($content) { $content.Trim() } else { "(no output)" }
        } else {
            $Results[$role] = "(no output file)"
        }

        if (Test-Path $info.RunnerScript) {
            Remove-Item $info.RunnerScript -Force -ErrorAction SilentlyContinue
        }
    }
}

# ---------- synthesize results ----------
$EndTime = Get-Date
$Duration = $EndTime - $StartTime
$DurationStr = "$($Duration.Minutes)m $($Duration.Seconds)s"

Write-Host ""
Write-Box "TEAM MODE -- Results" @(
    "Task:     $Task",
    "Roles:    $($SelectedRoles -join ', ')",
    "Elapsed:  $DurationStr"
)

foreach ($role in $SelectedRoles) {
    $def = $RoleDefinitions[$role]
    Write-Section "$($def.label) ($role)"
    $output = $Results[$role]
    if ($output) {
        $lines = $output -split "`n"
        foreach ($line in $lines) {
            Write-Host "  $line" -ForegroundColor $def.color
        }
    } else {
        Write-Host "  (no output)" -ForegroundColor DarkGray
    }
}

# ---------- synthesis section ----------
Write-Section "Synthesis"
Write-Host "  Roles executed:     $($SelectedRoles.Count)" -ForegroundColor Green
Write-Host "  Task scope:         $(if ($Task.Length -gt 60) { $Task.Substring(0, 60) + '...' } else { $Task })" -ForegroundColor Green
Write-Host "  Total duration:     $DurationStr" -ForegroundColor Yellow
Write-Host ""
Write-Host "  To merge role outputs:" -ForegroundColor Yellow
Write-Host "  1. Review each role's analysis above" -ForegroundColor Yellow
Write-Host "  2. Identify consensus points and conflicts" -ForegroundColor Yellow
Write-Host "  3. Merge into a unified action plan" -ForegroundColor Yellow
Write-Host "  4. Run with -LogDecision to record the outcome" -ForegroundColor Yellow

# ---------- save session report ----------
$Report = @{
    id         = $ReportId
    task       = $Task
    roles      = $SelectedRoles
    start_time = $Now
    end_time   = Get-Timestamp
    duration   = $DurationStr
    goal_aligned = $GoalActive
    results    = $Results
}

$ReportPath = Join-Path $DataDir "${ReportId}.json"
if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir -Force | Out-Null }
try {
    $json = $Report | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($ReportPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Host ""
    Write-Host "Report saved: $ReportPath" -ForegroundColor Green
} catch {
    Write-Host "[xTrace] err | team-mode.ps1 | Save report failed | $_" -ForegroundColor Red
}

# ---------- DTrace logging ----------
if ($LogDecision) {
    $DtScript = Join-Path $ScriptDir "decision-trace.ps1"
    if (Test-Path $DtScript) {
        $DecisionTitle = "Team Mode: $Task"
        Write-Host ""
        Write-Host "[team] Logging to DTrace..." -ForegroundColor DarkGray
        try {
            & $DtScript -Action Add -Title $DecisionTitle -Context "Team Mode with roles: $($SelectedRoles -join ', ')" -Category "process" -Notes "Duration: $DurationStr"
            Write-Host "[team] Decision logged successfully" -ForegroundColor Green
        } catch {
            Write-Host "[team] Failed to log decision: $_" -ForegroundColor Red
        }
    }
}

# ---------- error-trace compatible output ----------
$anyError = $Results.Values | Where-Object { $_ -like "ERROR*" }
if ($anyError) {
    Write-Host "[xTrace] err | team-mode.ps1 | One or more roles failed | $Task" -ForegroundColor Red
}

Write-Host ""
Write-Host "Team Mode execution complete." -ForegroundColor Cyan
