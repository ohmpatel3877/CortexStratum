<#
.SYNOPSIS
  Unified Orchestration Entry Point — Full pipeline orchestrator for CortexStratum.

.DESCRIPTION
  Orchestrates the complete pipeline: task analysis → complexity scoring →
  plan generation → dispatch (DAG or standard) → result collection → decision logging.

.PARAMETER Task
  The task description to orchestrate.

.PARAMETER Mode
  Execution mode: plan (dry-run), execute (run pipeline), dag (DAG dispatch), full (all).

.PARAMETER DagFile
  Path to DAG definition JSON file (required in dag mode).

.PARAMETER Json
  Output results as JSON.

.EXAMPLE
  .\scripts\orchestrate-all.ps1 -Task "Build auth module" -Mode plan
  .\scripts\orchestrate-all.ps1 -Task "Build auth module" -Mode dag -DagFile data\dag-definitions\seed-dag.json
  .\scripts\orchestrate-all.ps1 -Task "Build auth module" -Mode full
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Task,

    [ValidateSet("plan", "execute", "dag", "full")]
    [string]$Mode = "plan",

    [string]$DagFile,

    [switch]$Json
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PythonCmd = "python"

$G = "$([char]0x1b)[92m"
$Y = "$([char]0x1b)[93m"
$B = "$([char]0x1b)[94m"
$M = "$([char]0x1b)[95m"
$R = "$([char]0x1b)[91m"
$C = "$([char]0x1b)[96m"
$N = "$([char]0x1b)[0m"
$BOLD = "$([char]0x1b)[1m"
$BAR = ("=" * 50)

$Result = @{
    timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
    task = $Task
    mode = $Mode
    steps = @()
    analysis = $null
    plan = $null
    dispatch = $null
    status = "running"
    error = $null
}

function Write-Step($color, $label, $message) {
    Write-Host "$color  $label $N$message"
}

function Add-StepResult($stepName, $success, $output, $error) {
    $step = @{
        step = $stepName
        success = $success
        timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
        output = $output
        error = $error
    }
    $Result.steps += $step
}

# ── Header ─────────────────────────────────────────────────
Write-Host "`n$C$BAR$N"
Write-Host "$C$BOLD  UNIFIED ORCHESTRATION ENGINE$N"
Write-Host "$C$BAR$N"
Write-Host "  Task:    $Task"
Write-Host "  Mode:    $Mode"
Write-Host "  Time:    $($Result.timestamp)"

# Step 1: Run task-analyzer.py
Write-Host "`n$Y  [1/6] Analyzing task complexity...$N"
try {
    $analysisOutput = & $PythonCmd "$ProjectRoot\scripts\task-analyzer.py" --task "$Task" --json 2>&1
    $analysis = $analysisOutput | ConvertFrom-Json
    Write-Step -color $G -label "" -message "Score: $($analysis.score)/100 ($($analysis.threshold))"
    Add-StepResult -stepName "analyze" -success $true -output $analysis
} catch {
    Write-Step -color $R -label "" -message "Analysis failed: $_"
    Add-StepResult -stepName "analyze" -success $false -error "$_"
    $Result.status = "failed"
    $Result.error = "Analysis failed"
    if ($Json) { $Result | ConvertTo-Json -Depth 10 }
    exit 1
}

# Step 2: Generate plan (if MEDIUM+)
$score = [double]$analysis.score
Write-Host "`n$Y  [2/6] Generating plan...$N"
if ($score -ge 25) {
    $planMode = "plan"
    try {
        $planOutput = & $PythonCmd "$ProjectRoot\scripts\task-orchestrator.py" --task "$Task" --plan 2>&1
        Write-Step -color $G -label "" -message "Plan generated for complexity $score"
        Add-StepResult -stepName "plan" -success $true -output $planOutput
    } catch {
        Write-Step -color $Y -label "~" -message "Plan skipped (orchestrator note)"
        Add-StepResult -stepName "plan" -success $false -error "$_"
    }
} else {
    Write-Step -color $C -label "i" -message "LOW complexity ($score) — direct execution, no plan needed"
    Add-StepResult -stepName "plan" -success $true -output @{ note = "Skipped — LOW complexity" }
}

# Step 3: Dispatch
Write-Host "`n$Y  [3/6] Dispatching execution...$N"
if ($Mode -eq "dag" -or ($Mode -eq "full" -and $score -ge 45)) {
    if (-not $DagFile) {
        $DagFile = "$ProjectRoot\data\dag-definitions\seed-dag.json"
        Write-Step -color $C -label "i" -message "No DagFile specified, using seed: $DagFile"
    }
    if (-not (Test-Path $DagFile)) {
        Write-Step -color $R -label "" -message "DAG file not found: $DagFile"
        Add-StepResult -stepName "dispatch" -success $false -error "DAG file not found: $DagFile"
    } else {
        try {
            $dagOutput = & $PythonCmd "$ProjectRoot\scripts\dag-coordinator.py" --dag "$DagFile" --dry-run 2>&1
            Write-Step -color $G -label "" -message "DAG plan generated"
            Add-StepResult -stepName "dispatch" -success $true -output ($dagOutput | Out-String)
            if ($Mode -eq "dag" -or $Mode -eq "full") {
                $dagExecOutput = & $PythonCmd "$ProjectRoot\scripts\dag-coordinator.py" --dag "$DagFile" 2>&1
                Write-Step -color $G -label "" -message "DAG execution complete"
            }
        } catch {
            Write-Step -color $R -label "" -message "DAG dispatch failed: $_"
            Add-StepResult -stepName "dispatch" -success $false -error "$_"
        }
    }
} else {
    # Standard dispatch via task-orchestrator
    $orchMode = if ($Mode -eq "full") { "orchestrate" } else { $Mode }
    try {
        $orchOutput = & $PythonCmd "$ProjectRoot\scripts\task-orchestrator.py" --task "$Task" "--$orchMode" 2>&1
        Write-Step -color $G -label "" -message "Standard dispatch ($orchMode)"
        Add-StepResult -stepName "dispatch" -success $true -output ($orchOutput | Out-String)
    } catch {
        Write-Step -color $R -label "" -message "Standard dispatch failed: $_"
        Add-StepResult -stepName "dispatch" -success $false -error "$_"
    }
}

# Step 4: Collect results
Write-Host "`n$Y  [4/6] Collecting results...$N"
$Result.dispatch = @{ mode = $Mode }
Add-StepResult -stepName "collect" -success $true -output @{ note = "Results aggregated" }

# Step 5: Log to decision-trace.ps1
Write-Host "`n$Y  [5/6] Logging decision trace...$N"
try {
    & "$ProjectRoot\scripts\decision-trace.ps1" `
        -Action Add `
        -Title "Orchestrated: $($Task.Substring(0, [Math]::Min(80, $Task.Length)))" `
        -Decision "Auto-orchestrated via orchestrate-all.ps1 in $Mode mode" `
        -Rationale "Complexity $score/100 ($($analysis.threshold))" `
        -Category process
    Write-Step -color $G -label "" -message "Decision logged"
    Add-StepResult -stepName "log-decision" -success $true -output "Logged to decision-registry.json"
} catch {
    Write-Step -color $Y -label "~" -message "Decision log skipped: $_"
    Add-StepResult -stepName "log-decision" -success $false -error "$_"
}

# Step 6: Output structured result
Write-Host "`n$Y  [6/6] Finalizing...$N"
$Result.status = "completed"
Add-StepResult -stepName "finalize" -success $true -output @{ status = "completed" }

Write-Host "`n$G$BAR$N"
Write-Host "$G   ORCHESTRATION COMPLETE$N"
Write-Host "$G$BAR$N"
Write-Host "  Task:    $Task"
Write-Host "  Mode:    $Mode"
Write-Host "  Score:   $score/$($analysis.threshold)"
Write-Host "  Status:  $($Result.status)"

if ($Json) {
    Write-Host "`n---JSON_OUTPUT---"
    $Result | ConvertTo-Json -Depth 10
}

exit 0
