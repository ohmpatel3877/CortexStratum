<#
.SYNOPSIS
    Matches a user message against skill-router.json triggers and outputs skill names to load.

.DESCRIPTION
    Loads skill-router.json, parses the user message for trigger keywords (case-insensitive),
    deduplicates matched skills, and sorts them by priority descending.
    Supports a -DryRun switch to preview matches without invoking any loader.

.PARAMETER Message
    The user's natural language input message to analyze.

.PARAMETER DryRun
    If specified, only prints the matched skills without loading them.

.PARAMETER ConfigPath
    Override path to skill-router.json. Defaults to '../skills/skill-router.json' relative to this script.

.EXAMPLE
    .\load-skills.ps1 -Message "Fix this bug in the Electron IPC"
    -> ["troubleshooting-master", "error-triage", "electron-desktop-architecture", "concise-filter"]

.EXAMPLE
    .\load-skills.ps1 -Message "Write tests for the new component" -DryRun
    -> Prints matched skills without loading.
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Message,

    [switch]$DryRun,

    [string]$ConfigPath = ""
)

# --- Resolve config path ---
if (-not $ConfigPath) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ConfigPath = Join-Path -Path $ScriptDir -ChildPath "..\skills\skill-router.json"
}
$ConfigPath = Resolve-Path -Path $ConfigPath -ErrorAction Stop
Write-Verbose "Loading skill router config from: $ConfigPath"

# --- Load config ---
try {
    $config = Get-Content -Path $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Error "Failed to parse skill-router.json: $_"
    exit 1
}

Write-Verbose "Skill router v$($config.version) loaded with $($config.rules.Count) rules"

# --- Normalise message to lowercase for matching ---
$lowerMessage = $Message.ToLowerInvariant()

# --- Collect matched skills with their priorities ---
$matched = [System.Collections.Generic.List[hashtable]]::new()

foreach ($rule in $config.rules) {
    $matchedTriggers = @()
    foreach ($trigger in $rule.triggers) {
        if ($lowerMessage -match [regex]::Escape($trigger.ToLowerInvariant())) {
            $matchedTriggers += $trigger
        }
    }
    if ($matchedTriggers.Count -gt 0) {
        foreach ($skill in $rule.skills) {
            $matched.Add(@{
                Skill    = $skill
                Priority = [int]$rule.priority
                Triggers = $matchedTriggers -join ', '
            })
        }
    }
}

# — Add default skills ---
foreach ($defaultSkill in $config.default_skills) {
    $matched.Add(@{
        Skill    = $defaultSkill
        Priority = 0
        Triggers = 'default'
    })
}

# — Deduplicate by skill name (keep highest priority entry) ---
$dedup = @{}
foreach ($entry in $matched) {
    $name = $entry.Skill
    if (-not $dedup.ContainsKey($name) -or $dedup[$name].Priority -lt $entry.Priority) {
        $dedup[$name] = $entry
    }
}

# — Sort by priority descending, then alphabetically ---
$sorted = $dedup.Values | Sort-Object -Property @{Expression='Priority'; Descending=$true}, @{Expression='Skill'; Descending=$false}

$skillNames = $sorted | ForEach-Object { $_.Skill }
$uniqueCount = $skillNames.Count

# — Output ---
if ($DryRun) {
    Write-Host "`n[Dry-Run] Matched skills for message: '$Message'" -ForegroundColor Cyan
    if ($uniqueCount -eq 0) {
        Write-Host "  (no skills matched)" -ForegroundColor Yellow
    } else {
        $sorted | ForEach-Object {
            Write-Host "  [P:$($_.Priority)] $($_.Skill)  <- $($_.Triggers)" -ForegroundColor Green
        }
    }
    Write-Host "`n[Dry-Run] Total unique skills: $uniqueCount" -ForegroundColor Cyan
} else {
    # Return deduplicated, sorted skill names as a JSON array for piping
    $skillNames | ConvertTo-Json -Compress
}

# — Also update a marker file for interop with other tools ---
$markerDir = Join-Path -Path $PSScriptRoot -ChildPath "..\.opencode"
if (-not (Test-Path -Path $markerDir)) {
    $null = New-Item -ItemType Directory -Path $markerDir -Force
}
$markerPath = Join-Path -Path $markerDir -ChildPath "active-skills.json"
$skillNames | ConvertTo-Json | Set-Content -Path $markerPath -Encoding UTF8 -Force

if ($DryRun) {
    Write-Host "  (marker written to: $markerPath)" -ForegroundColor DarkGray
}
