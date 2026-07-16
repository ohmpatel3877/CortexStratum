# Goal Registry — tracks session goal stack, detects drift, persists as JSON
# Usage:
#   .\scripts\goal-registry.ps1 -Command Init -Goal "Implement feature X"
#   .\scripts\goal-registry.ps1 -Command AddSubGoal -Description "Search memory for prior context"
#   .\scripts\goal-registry.ps1 -Command CompleteSubGoal -Id 1
#   .\scripts\goal-registry.ps1 -Command CheckAlignment -CurrentAction "Writing tests for module Y"
#   .\scripts\goal-registry.ps1 -Command Status

param(
    [Parameter(Mandatory)]
    [ValidateSet('Init', 'AddSubGoal', 'CompleteSubGoal', 'CheckAlignment', 'Status')]
    [string]$Action,

    [string]$Goal,
    [string]$Description,
    [int]$Id = -1,
    [string]$CurrentAction
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DataDir = Join-Path $ProjectRoot "data"
$RegistryPath = Join-Path $DataDir "goal-registry.json"

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

# ---------- helpers ----------
function Get-SessionId {
    $envId = $env:OPENCODE_SESSION_ID
    if ($envId) { return $envId }
    return "ses_$(Get-Random -Maximum 1000000000)_$( -join ((65..90) + (97..122) | Get-Random -Count 6 | ForEach-Object { [char]$_ }) )"
}

function Get-Elapsed($startTime) {
    $elapsed = [DateTime]::UtcNow - $startTime
    $mins = [math]::Floor($elapsed.TotalMinutes)
    $secs = $elapsed.Seconds
    if ($mins -ge 60) {
        $hours = [math]::Floor($mins / 60)
        $mins = $mins % 60
        return "${h}h ${mins}m ${secs}s"
    }
    return "${mins}m ${secs}s"
}

function Write-Box($title, $lines) {
    $width = ($lines | Measure-Object -Maximum Length).Maximum
    $bar = "=" * ($width + 4)
    Write-Host $bar -ForegroundColor Cyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host $bar -ForegroundColor Cyan
    foreach ($line in $lines) {
        Write-Host "  $line"
    }
    Write-Host $bar -ForegroundColor Cyan
}

# ---------- Init ----------
if ($Action -eq 'Init') {
    if (-not $Goal) { Write-Error "Init requires -Goal"; exit 1 }

    $now = [DateTime]::UtcNow.ToString('o')
    $registry = @{
        session_id    = Get-SessionId
        original_goal = $Goal
        start_time    = $now
        sub_goals     = @()
    }
    $json = $registry | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[GOAL REGISTRY] Initialized" -ForegroundColor Green
    Write-Host "  Session ID:   $($registry.session_id)" -ForegroundColor Yellow
    Write-Host "  Original goal: $Goal" -ForegroundColor Yellow
    Write-Host "  Path:         $RegistryPath" -ForegroundColor Yellow
    exit 0
}

# ---------- load existing ----------
if (-not (Test-Path $RegistryPath)) {
    if ($Action -eq 'Status') {
        Write-Host "=== GOAL REGISTRY STATUS ==="
        Write-Host "No active goal registry. Run Init to start."
        exit 0
    }
    Write-Error "No goal registry found. Run Init first."
    exit 1
}
try {
    $registry = Get-Content $RegistryPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Error "Failed to read goal registry: corrupt or missing JSON at $RegistryPath"
    exit 1
}

# ---------- AddSubGoal ----------
if ($Action -eq 'AddSubGoal') {
    if (-not $Description) { Write-Error "AddSubGoal requires -Description"; exit 1 }

    $now = [DateTime]::UtcNow.ToString('o')
    $id = $registry.sub_goals.Count
    $entry = @{
        id          = $id
        description = $Description
        status      = "pending"
        created_at  = $now
        completed_at = $null
    }
    $registry.sub_goals += $entry
    $json = $registry | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[GOAL REGISTRY] Added sub-goal #${id}: $Description" -ForegroundColor Green
    exit 0
}

# ---------- CompleteSubGoal ----------
if ($Action -eq 'CompleteSubGoal') {
    if ($Id -lt 0) { Write-Error "CompleteSubGoal requires -Id (0-based index)"; exit 1 }

    $sg = $registry.sub_goals | Where-Object { $_.id -eq $Id }
    if (-not $sg) { Write-Error "Sub-goal with id=$Id not found"; exit 1 }

    $sg.status = "completed"
    $sg.completed_at = [DateTime]::UtcNow.ToString('o')
    $json = $registry | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[GOAL REGISTRY] Completed sub-goal #${Id}: $($sg.description)" -ForegroundColor Green
    exit 0
}

# ---------- CheckAlignment ----------
if ($Action -eq 'CheckAlignment') {
    if (-not $CurrentAction) { Write-Error "CheckAlignment requires -CurrentAction"; exit 1 }

    $goalWords = $registry.original_goal.ToLower() -split '\W+' | Where-Object { $_.Length -gt 2 } | Select-Object -Unique
    $actionWords = $CurrentAction.ToLower() -split '\W+' | Where-Object { $_.Length -gt 2 } | Select-Object -Unique

    if ($goalWords.Count -eq 0) {
        Write-Host "[GOAL REGISTRY] ALIGNED (insufficient keywords in original goal)" -ForegroundColor Green
        exit 0
    }

    $overlap = $actionWords | Where-Object { $_ -in $goalWords }
    $overlapCount = ($overlap | Measure-Object).Count
    $ratio = $overlapCount / $goalWords.Count

    $lastSubgoal = $registry.sub_goals | Select-Object -Last 1
    $lastLine = if ($lastSubgoal) {
        "Most recent sub-goal: $($lastSubgoal.description) | Status: $($lastSubgoal.status)"
    } else {
        "Most recent sub-goal: (none) | Status: -"
    }

    if ($ratio -ge 0.30) {
        Write-Host "[GOAL REGISTRY] ALIGNED (${ratio:P0} keyword overlap)" -ForegroundColor Green
    } else {
        Write-Host "[GOAL REGISTRY] DRIFT_DETECTED (${ratio:P0} keyword overlap)" -ForegroundColor Red
    }
    Write-Host "  Goal keywords:     $($goalWords -join ', ')" -ForegroundColor Yellow
    Write-Host "  Action keywords:   $($actionWords -join ', ')" -ForegroundColor Yellow
    Write-Host "  $lastLine" -ForegroundColor Yellow
    exit 0
}

# ---------- Status ----------
if ($Action -eq 'Status') {
    $startTime = [DateTime]::Parse($registry.start_time)
    $elapsed = Get-Elapsed $startTime

    $goalWords = $registry.original_goal.ToLower() -split '\W+' | Where-Object { $_.Length -gt 2 } | Select-Object -Unique

    Write-Box "GOAL REGISTRY STATUS" @(
        "Session:        $($registry.session_id)",
        "Original Goal:  $(if ($registry.original_goal.Length -gt 80) { $registry.original_goal.Substring(0,80) + '...' } else { $registry.original_goal })",
        "Elapsed:        $elapsed",
        "Sub-Goals:      $($registry.sub_goals.Count) total"
    )

    Write-Host ""

    if ($registry.sub_goals.Count -eq 0) {
        Write-Host "  (no sub-goals)" -ForegroundColor DarkGray
    } else {
        $now = [DateTime]::UtcNow
        foreach ($sg in $registry.sub_goals) {
            $marker = switch ($sg.status) {
                'completed' { "[X]" }
                'pending'   { "[ ]" }
                'in_progress' { "[~]" }
                'cancelled' { "[-]" }
                default     { "[?]" }
            }
            $color = switch ($sg.status) {
                'completed' { 'Green' }
                'pending'   { 'DarkGray' }
                'in_progress' { 'Yellow' }
                'cancelled' { 'Red' }
                default     { 'Gray' }
            }

            $duration = ""
            if ($sg.created_at) {
                $created = [DateTime]::Parse($sg.created_at)
                $dur = $now - $created
                if ($sg.status -eq 'completed' -and $sg.completed_at) {
                    $completed = [DateTime]::Parse($sg.completed_at)
                    $dur = $completed - $created
                }
                $durMins = [math]::Floor($dur.TotalMinutes)
                $durSecs = $dur.Seconds
                $duration = "(${durMins}m ${durSecs}s $(if ($sg.status -eq 'completed') { 'completed' } else { $sg.status }))"
            }

            Write-Host "  $marker $($sg.id). $($sg.description) $duration" -ForegroundColor $color

            # Warn if in_progress > 20 minutes
            if ($sg.status -eq 'in_progress' -and $sg.created_at) {
                $created = [DateTime]::Parse($sg.created_at)
                if (($now - $created).TotalMinutes -gt 20) {
                    Write-Host "         WARNING: in_progress for more than 20 minutes!" -ForegroundColor Red
                }
            }
        }
    }

    # Alignment score
    Write-Host ""
    $recentActions = $registry.sub_goals | Where-Object { $_.status -ne 'cancelled' } | Select-Object -Last 3
    if ($recentActions) {
        $allWords = @()
        foreach ($sg in $recentActions) {
            $allWords += $sg.description.ToLower() -split '\W+' | Where-Object { $_.Length -gt 2 }
        }
        $actionWords = $allWords | Select-Object -Unique
        $overlap = $actionWords | Where-Object { $_ -in $goalWords }
        $overlapCount = ($overlap | Measure-Object).Count
        $ratio = if ($goalWords.Count -gt 0) { $overlapCount / $goalWords.Count } else { 1.0 }
        $aligned = if ($ratio -ge 0.30) { "ALIGNED" } else { "DRIFT_DETECTED" }
        $color = if ($ratio -ge 0.30) { 'Green' } else { 'Red' }
        Write-Host "Alignment: $aligned (${ratio:P0} overlap)" -ForegroundColor $color
        Write-Host "  Keywords: $($goalWords -join ', ')" -ForegroundColor DarkGray
    }
}
