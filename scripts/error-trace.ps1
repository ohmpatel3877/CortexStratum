param(
    [Parameter(Position=0, Mandatory=$false)]
    [string]$Action,

    [string]$FailedCommand,
    [string]$ErrorOutput,
    [string]$ExitCode,
    [string]$ErrorSignature,
    [string]$Fix,
    [string]$Result,
    [string]$RootCause,
    [string]$Resolution,
    [string]$Keyword
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$script:RegistryPath = Join-Path (Join-Path $ProjectRoot "data") "error-registry.json"
$script:NextId = 1

function Ensure-Registry {
    $dir = Split-Path $RegistryPath -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    if (-not (Test-Path $RegistryPath)) {
        $initial = @{ version = 1; errors = @() }
        $json = $initial | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
    }
}

function Load-Registry {
    Ensure-Registry
    try {
        $content = Get-Content -Path $RegistryPath -Raw -Encoding UTF8
        $data = $content | ConvertFrom-Json
    } catch {
        Write-Host "[warn] corrupt registry - resetting to empty"
        $data = @{ version = 1; errors = @() }
    }
    if ($data.errors.Count -gt 0) {
        $last = $data.errors[-1].id
        $num = [int]($last -replace 'err-', '')
        $script:NextId = $num + 1
    }
    return $data
}

function Save-Registry($data) {
    $json = $data | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Normalize-Signature($text) {
    $normalized = $text -replace '\s+', ' ' -replace '"', '' -replace "'", '' -replace '`', ''
    $normalized.Trim().Substring(0, [Math]::Min(100, $normalized.Length))
}

function Invoke-LogError {
    if (-not $ErrorOutput -or -not $FailedCommand) {
        Write-Error -Message "LogError requires FailedCommand and ErrorOutput parameters"
        exit 1
    }
    $data = Load-Registry
    $sig = Normalize-Signature $ErrorOutput
    $existing = $data.errors | Where-Object { $_.error_signature -eq $sig }
    $now = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")

    if ($existing) {
        $existing.occurrence_count = [int]$existing.occurrence_count + 1
        $existing.last_seen = $now
    }
    else {
        $entry = @{
            id                = "err-{0:D3}" -f $script:NextId
            error_signature   = $sig
            command           = $FailedCommand
            exit_code         = [int]$ExitCode
            first_seen        = $now
            last_seen         = $now
            occurrence_count  = 1
            status            = "unresolved"
            root_cause        = ""
            resolution        = ""
            attempts          = @()
        }
        $data.errors += $entry
        $script:NextId++
    }
    Save-Registry $data
    Write-Host "Logged error: $sig"
}

function Invoke-LogAttempt {
    if (-not $ErrorSignature -or -not $Fix) {
        Write-Error -Message "LogAttempt requires ErrorSignature and Fix parameters"
        exit 1
    }
    $data = Load-Registry
    $entry = $data.errors | Where-Object { $_.error_signature -like "*$ErrorSignature*" }
    if (-not $entry) {
        Write-Error -Message "Error signature not found: $ErrorSignature"
        exit 1
    }
    $attempt = @{
        fix       = $Fix
        result    = if ($Result) { $Result } else { "unknown" }
        timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
    }
    $entry.attempts += $attempt
    $entry.last_seen = $attempt.timestamp
    Save-Registry $data
    Write-Host "Logged attempt for: $ErrorSignature / fix: $Fix / result: $Result"
}

function Invoke-Resolve {
    if (-not $ErrorSignature -or -not $RootCause -or -not $Resolution) {
        Write-Error -Message "Resolve requires ErrorSignature, RootCause, and Resolution parameters"
        exit 1
    }
    $data = Load-Registry
    $entry = $data.errors | Where-Object { $_.error_signature -like "*$ErrorSignature*" }
    if (-not $entry) {
        Write-Error -Message "Error signature not found: $ErrorSignature"
        exit 1
    }
    $entry.status = "resolved"
    $entry.root_cause = $RootCause
    $entry.resolution = $Resolution
    $entry.last_seen = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
    Save-Registry $data
    Write-Host ("Resolved error: $ErrorSignature / cause: $RootCause / resolution: $Resolution")
}

function Invoke-Search {
    if (-not $Keyword) {
        Write-Error -Message "Search requires -Keyword"
        exit 1
    }
    $data = Load-Registry
    $results = $data.errors | Where-Object {
        $_.error_signature -like "*$Keyword*" -or
        $_.root_cause -like "*$Keyword*" -or
        ($_.attempts | Where-Object { $_.fix -like "*$Keyword*" })
    }
    if ($results.Count -eq 0) {
        Write-Host "No errors match keyword: $Keyword"
        return
    }
    $results | ForEach-Object {
        Write-Host "--- $($_.id) ---"
        Write-Host "  signature: $($_.error_signature)"
        Write-Host "  command:   $($_.command)"
        Write-Host "  status:    $($_.status)"
        Write-Host "  attempts:  $($_.attempts.Count)"
        if ($_.root_cause) { Write-Host "  cause:     $($_.root_cause)" }
        if ($_.resolution) { Write-Host "  fix:       $($_.resolution)" }
    }
}

function Invoke-Status {
    $data = Load-Registry
    $total = $data.errors.Count
    $resolved = ($data.errors | Where-Object { $_.status -eq "resolved" }).Count
    $unresolved = $total - $resolved

    Write-Host "=== Error Registry Status ==="
    Write-Host "Total errors logged:   $total"
    Write-Host "Resolved:              $resolved"
    Write-Host "Unresolved:            $unresolved"

    if ($total -gt 0) {
        $sorted = $data.errors | Sort-Object -Property occurrence_count -Descending
        Write-Host ""
        Write-Host "Top 3 most frequent:"
        $sorted | Select-Object -First 3 | ForEach-Object {
            Write-Host "  [$($_.occurrence_count)x] $($_.error_signature)"
        }
        $totalAttempts = ($data.errors | ForEach-Object { $_.attempts.Count } | Measure-Object -Sum).Sum
        $avg = if ($total -gt 0) { [math]::Round($totalAttempts / $total, 2) } else { 0 }
        Write-Host ""
        Write-Host "Average attempts to resolve: $avg"
    }
}

switch ($Action) {
    "LogError"  { Invoke-LogError }
    "LogAttempt" { Invoke-LogAttempt }
    "Resolve"   { Invoke-Resolve }
    "Search"    { Invoke-Search }
    "Status"    { Invoke-Status }
    default {
        Write-Host 'Usage: .\error-trace.ps1 -Action (LogError|LogAttempt|Resolve|Search|Status) [params]'
        Write-Host ''
        Write-Host 'Commands:'
        Write-Host '  LogError   -Action LogError -FailedCommand [cmd] -ErrorOutput [text] [-ExitCode [int]]'
        Write-Host '  LogAttempt -Action LogAttempt -ErrorSignature [sig] -Fix [text] [-Result success|failed]'
        Write-Host '  Resolve    -Action Resolve -ErrorSignature [sig] -RootCause [text] -Resolution [text]'
        Write-Host '  Search     -Action Search -Keyword [text]'
        Write-Host '  Status     -Action Status'
    }
}
