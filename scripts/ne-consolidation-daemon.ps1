#!/usr/bin/env pwsh
<#
.SYNOPSIS
    NE-Memory auto-consolidation daemon — runs every N minutes to deduplicate
    memory entries, merge similar records, and log results to DTrace.
.DESCRIPTION
    Launches the memory consolidation engine (memory_search.py) on a timer.
    Designed to run as a scheduled task or background job.
.PARAMETER IntervalMinutes
    How often to run consolidation (default: 30)
.PARAMETER SimilarityThreshold
    Jaccard similarity threshold (0-1, default: 0.85)
#>

param(
    [int]$IntervalMinutes = 30,
    [float]$SimilarityThreshold = 0.85,
    [string]$LogPath = "$env:USERPROFILE\github\CortexStratum\data\logs"
)

# Ensure log directory exists
New-Item -ItemType Directory -Path $LogPath -Force -ErrorAction SilentlyContinue | Out-Null

$ScriptDir = "$env:USERPROFILE\github\CortexStratum\scripts"
$MemoryScript = Join-Path $ScriptDir "memory_search.py"
$DecisionTrace = Join-Path $ScriptDir "decision-trace.ps1"
$LogFile = Join-Path $LogPath "ne-consolidation.log"

Write-Host "[ne-daemon] Starting consolidation daemon (interval=${IntervalMinutes}m, threshold=${SimilarityThreshold})"

while ($true) {
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[ne-daemon] $Timestamp — Running consolidation..."

    # Run consolidation via memory_search.py
    $Result = python $MemoryScript consolidate --threshold $SimilarityThreshold 2>&1

    if ($LASTEXITCODE -eq 0) {
        $Output = $Result | Out-String
        Add-Content -Path $LogFile -Value "$Timestamp — CONSOLIDATION OK: $Output"

        # Log to DTrace if available
        if (Test-Path $DecisionTrace) {
            & $DecisionTrace -Action Add -Title "NE-Memory auto-consolidation" `
                -Context "Interval=${IntervalMinutes}m, threshold=${SimilarityThreshold}" `
                -Decision "Consolidation completed" `
                -Rationale $Output `
                -Category process
        }
    } else {
        $ErrorMsg = $Result | Out-String
        Add-Content -Path $LogFile -Value "$Timestamp — CONSOLIDATION FAILED: $ErrorMsg"
        Write-Warning "[ne-daemon] Consolidation failed: $ErrorMsg"
    }

    Write-Host "[ne-daemon] Sleeping for ${IntervalMinutes} minutes..."
    Start-Sleep -Seconds ($IntervalMinutes * 60)
}
