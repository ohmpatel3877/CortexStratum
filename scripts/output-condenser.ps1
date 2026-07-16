<#
.SYNOPSIS
    Condenses verbose tool outputs to extract only signal (errors, key data, summaries),
    discarding noise to stretch the agent's context window 3-5x.

.DESCRIPTION
    Supports 4 condensation modes:
      CondenseBash  - Condense command output (build, test, npm, git, generic)
      CondenseRead  - Condense file read output with signature extraction
      CondenseGrep  - Condense grep/search results grouped by file
      CondenseMem0  - Condense mem0 search JSON results

    All modes save condensed output to the condenser log at
    $PSScriptRoot\..\data\condensed\condenser-log.txt
    with a UTC timestamp.

.PARAMETER Command
    One of: CondenseBash, CondenseRead, CondenseGrep, CondenseMem0

.PARAMETER InputText
    The raw tool output text to condense.

.PARAMETER CommandType
    For CondenseBash: "build", "test", "npm", "git", or "generic" (default).

.PARAMETER FilePath
    For CondenseRead: the file path being read (for display in output).

.EXAMPLE
    .\output-condenser.ps1 -Command CondenseBash -InputText "..." -CommandType build

.EXAMPLE
    .\output-condenser.ps1 -Command CondenseRead -InputText "..." -FilePath "src/main/index.ts"

.EXAMPLE
    .\output-condenser.ps1 -Command CondenseGrep -InputText "..."

.EXAMPLE
    .\output-condenser.ps1 -Command CondenseMem0 -InputText "..."
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('CondenseBash', 'CondenseRead', 'CondenseGrep', 'CondenseMem0')]
    [string]$Command,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$InputText,

    [Parameter(Mandatory = $false)]
    [ValidateSet('build', 'test', 'npm', 'git', 'generic')]
    [string]$CommandType = 'generic',

    [Parameter(Mandatory = $false)]
    [string]$FilePath = ''
)

# --- Paths ---
$ScriptRoot = $PSScriptRoot
$ProjectRoot = Resolve-Path (Join-Path $ScriptRoot '..')
$DataDir = Join-Path $ProjectRoot 'data\condensed'
$LogFile = Join-Path $DataDir 'condenser-log.txt'

# --- Ensure data directory exists ---
if (-not (Test-Path $DataDir)) {
    $null = New-Item -ItemType Directory -Path $DataDir -Force
}

# --- Timestamp ---
$Timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss')
$FileTimestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')

# --- Helper: append to log file ---
function Write-CondenserLog {
    param([string]$Entry)
    $Entry | Out-File -FilePath $LogFile -Encoding UTF8 -Append
}

# --- Helper: compute cosine similarity between two strings (naive character n-gram) ---
function Get-CosineSimilarity {
    param([string]$A, [string]$B)
    $a = $A.ToLowerInvariant() -replace '\s+', ''
    $b = $B.ToLowerInvariant() -replace '\s+', ''
    if ([string]::IsNullOrEmpty($a) -or [string]::IsNullOrEmpty($b)) { return 0.0 }

    $n = 3
    $setA = @{}
    for ($i = 0; $i -le $a.Length - $n; $i++) {
        $gram = $a.Substring($i, $n)
        if ($setA.ContainsKey($gram)) { $setA[$gram]++ } else { $setA[$gram] = 1 }
    }
    $setB = @{}
    for ($i = 0; $i -le $b.Length - $n; $i++) {
        $gram = $b.Substring($i, $n)
        if ($setB.ContainsKey($gram)) { $setB[$gram]++ } else { $setB[$gram] = 1 }
    }

    $intersection = 0.0
    $magA = 0.0
    $magB = 0.0
    foreach ($k in $setA.Keys) {
        $v = [double]$setA[$k]
        $magA += $v * $v
        if ($setB.ContainsKey($k)) { $intersection += $v * [double]$setB[$k] }
    }
    foreach ($k in $setB.Keys) { $v = [double]$setB[$k]; $magB += $v * $v }

    $denom = [Math]::Sqrt($magA) * [Math]::Sqrt($magB)
    if ($denom -eq 0.0) { return 0.0 }
    return $intersection / $denom
}

# --- Splitter ---
$Separator = '-' * 60

# ======================================================================
# CondenseBash
# ======================================================================
function Invoke-CondenseBash {
    param([string]$Text, [string]$Type)

    $lines = $Text -split '\r?\n'
    $totalLines = $lines.Count
    $output = New-Object System.Text.StringBuilder

    [void]$output.AppendLine($Separator)
    [void]$output.AppendLine("[CONDENSED] Type: $Type | Lines: $totalLines")

    switch ($Type) {
        'build' {
            $exitCode = ($Text | Select-String -Pattern '(?:exit code|Exit code|errorlevel|exited with code)\s*:?\s*(\d+)').Matches | ForEach-Object { $_.Groups[1].Value }
            $exitLabel = if ($exitCode) { "FAILED (exit $exitCode)" } else { "UNKNOWN" }

            $errors = $lines | Select-String -Pattern '(?:error|Error|ERROR|TS\d+|cannot find|is not assignable|Property.*does not exist)' -Raw
            $warnings = $lines | Select-String -Pattern '(?:warning|Warning|WARN|TS\d+\s*:) warning' -Raw
            $summary = $lines | Select-String -Pattern '(?:tests?|passed|failed|TODO|done in|Duration|seconds?|executed|overall)' -Raw

            $passedCount = 0; $failedCount = 0; $totalTests = 0
            if ($Text -match '(\d+)\s+passed') { $passedCount = [int]$Matches[1] }
            if ($Text -match '(\d+)\s+failed') { $failedCount = [int]$Matches[1] }
            if ($Text -match '(\d+)\s+tests?') { $totalTests = [int]$Matches[1] }
            if ($passedCount -or $failedCount -or $totalTests) {
                $testSummary = "$totalTests tests -> ${passedCount} passed, ${failedCount} failed"
                [void]$output.AppendLine("Status: $exitLabel | $testSummary")
            } else {
                [void]$output.AppendLine("Status: $exitLabel")
            }

            if ($errors) {
                [void]$output.AppendLine("Errors ($($errors.Count)):")
                $errors | ForEach-Object { [void]$output.AppendLine("  $_") }
            }
            if ($warnings) {
                [void]$output.AppendLine("Warnings ($($warnings.Count)):")
                $warnings | ForEach-Object { [void]$output.AppendLine("  $_") }
            }
            if ($summary) {
                [void]$output.AppendLine("Summary:")
                $summary | ForEach-Object { [void]$output.AppendLine("  $_") }
            }
        }
        'test' {
            $testFiles = $lines | Select-String -Pattern '(?:PASS|FAIL|ok|not ok)\s+(.+?)(?:\s|\()' -Raw
            $passFail = $lines | Select-String -Pattern '(?:tests:|passed|failed|Tests:|Suites:|specs?|overall)' -Raw
            $failedTests = $lines | Select-String -Pattern '(?:FAIL|not ok)\s+(.*)' -Raw
            $duration = $lines | Select-String -Pattern '(?:\d+\.?\d*\s*ms|\d+\.?\d*\s*s\b|Duration:|Time:)' -Raw

            [void]$output.AppendLine("Test files referenced: $($testFiles.Count)")
            if ($testFiles) { $testFiles | ForEach-Object { [void]$output.AppendLine("  $_") } }
            if ($passFail) { [void]$output.AppendLine("Pass/Fail summary:"); $passFail | ForEach-Object { [void]$output.AppendLine("  $_") } }
            if ($failedTests) {
                [void]$output.AppendLine("Failed tests ($($failedTests.Count)):")
                $failedTests | ForEach-Object { [void]$output.AppendLine("  $_") }
            }
            if ($duration) { [void]$output.AppendLine("Duration: $($duration[0])") }
        }
        'npm' {
            $warnings = $lines | Select-String -Pattern '(?:npm warn|npm WARN|deprecated|SKIPPING|peer|vulnerability)' -Raw
            $errors = $lines | Select-String -Pattern '(?:npm ERR|ERR!|error|EACCES|ENOENT|EPERM|ERR_PNPM)' -Raw
            $audit = $lines | Select-String -Pattern '(?:audited|vulnerabilit|found\s+\d+|critical|high|moderate|low|fixed\s+\d+)' -Raw

            if ($errors) { [void]$output.AppendLine("Errors ($($errors.Count)):"); $errors | ForEach-Object { [void]$output.AppendLine("  $_") } }
            if ($warnings) { [void]$output.AppendLine("Warnings ($($warnings.Count)):"); $warnings | ForEach-Object { [void]$output.AppendLine("  $_") } }
            if ($audit) { [void]$output.AppendLine("Audit summary:"); $audit | ForEach-Object { [void]$output.AppendLine("  $_") } }
        }
        'git' {
            $fileList = $lines | Select-String -Pattern '(?:\+\+\+|---|modified:|deleted:|renamed:|new file:|diff --git)' -Raw
            $diffStats = $lines | Select-String -Pattern '(?:insertion|deletion|file changed|files changed|\d+\s+files?\b)' -Raw
            $conflicts = $lines | Select-String -Pattern '(?:CONFLICT|conflict|>>>>>>>|<<<<<<<|=======)' -Raw

            if ($fileList) { [void]$output.AppendLine("Files changed ($($fileList.Count)):"); $fileList | ForEach-Object { [void]$output.AppendLine("  $_") } }
            if ($diffStats) { [void]$output.AppendLine("Diff stats:"); $diffStats | ForEach-Object { [void]$output.AppendLine("  $_") } }
            if ($conflicts) { [void]$output.AppendLine("CONFLICTS ($($conflicts.Count)):"); $conflicts | ForEach-Object { [void]$output.AppendLine("  $_") } }
        }
        default {
            $condensedLines = @()
            $blankStreak = 0
            foreach ($line in $lines) {
                if ([string]::IsNullOrWhiteSpace($line)) {
                    $blankStreak++
                    if ($blankStreak -eq 2) { $condensedLines += '' }
                    continue
                }
                $blankStreak = 0
                $candidate = if ($line.Length -gt 500) { $line.Substring(0, 497) + '...' } else { $line }

                $isSignal = $line -match '(?:error|fail|warn|exception|traceback|at\s|Error\s|exit code|fatal|CRITICAL|SEVERE)'
                if ($isSignal) { $condensedLines += "[SIGNAL] $candidate" }
                else { $condensedLines += $candidate }
            }

            $signalLines = $condensedLines | Where-Object { $_ -match '^\[SIGNAL\]' }
            $nonSignalCount = ($condensedLines | Where-Object { $_ -notmatch '^\[SIGNAL\]' }).Count
            [void]$output.AppendLine("Total lines: $totalLines | Reduced to: $($condensedLines.Count) | Signal lines: $($signalLines.Count)")
            if ($signalLines) {
                [void]$output.AppendLine("Signal lines:")
                $signalLines | ForEach-Object { [void]$output.AppendLine("  $_") }
            }
            if ($nonSignalCount -gt 0) {
                [void]$output.AppendLine("($nonSignalCount lines of body suppressed)")
            }
        }
    }

    return $output.ToString().TrimEnd()
}

# ======================================================================
# CondenseRead
# ======================================================================
function Invoke-CondenseRead {
    param([string]$Text, [string]$Path)

    $lines = $Text -split '\r?\n'
    $totalLines = $lines.Count

    $sigPattern = '(?:function\s+\w+|class\s+\w+|fn\s+\w+|def\s+\w+|export\s+(?:default\s+)?(?:function|class|const)\s+\w+)'
    $signatures = $lines | Select-String -Pattern $sigPattern -Raw | ForEach-Object { $_.Trim() } | Select-Object -Unique

    $importPattern = '(?:import\s+|using\s+|require\s*\(|from\s+|#include)'
    $importLines = $lines | Select-String -Pattern $importPattern -Raw | ForEach-Object { $_.Trim() } | Select-Object -Unique

    $todoPattern = '(?:TODO|FIXME|HACK|XXX|WORKAROUND)'
    $todos = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $todoPattern) {
            $todos += "line $($i + 1) - $($lines[$i].Trim())"
        }
    }

    $codeLines = $lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and $_ -notmatch '^\s*(?:\/\/|#|--|\*|\/\*|\*\/)\s*$' }
    $signalCount = $signatures.Count + $importLines.Count + $todos.Count + $codeLines.Count
    $usefulRatio = if ($totalLines -gt 0) { [Math]::Round(($signalCount / $totalLines) * 100) } else { 0 }

    $output = New-Object System.Text.StringBuilder
    [void]$output.AppendLine($Separator)
    [void]$output.AppendLine("[CONDENSED] File: $Path ($totalLines lines | useful: ${usefulRatio}%)")
    if ($importLines) {
        $importSummary = ($importLines | ForEach-Object { $_ -replace '^(?:import|using|require|from|#include)\s*', '' } | Select-Object -First 20) -join ', '
        [void]$output.AppendLine("Imports: $importSummary")
    }
    if ($signatures) { [void]$output.AppendLine("Signatures ($($signatures.Count)): $($signatures -join ', ')") }
    if ($todos) { [void]$output.AppendLine("TODOs ($($todos.Count)):"); $todos | ForEach-Object { [void]$output.AppendLine("  $_") } }
    [void]$output.AppendLine("Full body suppressed. Use Read offset=50 limit=100 for specific section.")

    return $output.ToString().TrimEnd()
}

# ======================================================================
# CondenseGrep
# ======================================================================
function Invoke-CondenseGrep {
    param([string]$Text)

    $lines = $Text -split '\r?\n'
    $output = New-Object System.Text.StringBuilder

    $patternLine = $lines | Select-String -Pattern '^(?:Searching|grep|Finding|matches? for)' -Raw
    $pattern = if ($patternLine) { $patternLine[0] } else { '<search>' }

    $fileMatches = @{}
    $currentFile = $null
    foreach ($line in $lines) {
        if ($line -match '^(.+?\.\w+)\s*[:]\s*(\d+)?:?(.*)') {
            $currentFile = $Matches[1].Trim()
            if (-not $fileMatches.ContainsKey($currentFile)) { $fileMatches[$currentFile] = @() }
            $fileMatches[$currentFile] += $line.Trim()
        } elseif ($line -match '^\S+\.\w+\s*[-]+\s*\d+') {
            $parts = $line -split '\s*[-]+\s*'
            if ($parts.Count -ge 2) {
                $currentFile = $parts[0].Trim()
                if (-not $fileMatches.ContainsKey($currentFile)) { $fileMatches[$currentFile] = @() }
                $fileMatches[$currentFile] += $line.Trim()
            }
        }
    }

    if ($fileMatches.Count -eq 0) {
        $uniqueLines = $lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique
        [void]$output.AppendLine($Separator)
        [void]$output.AppendLine("[CONDENSED] Grep: `"$pattern`" -> $($uniqueLines.Count) unique matches")
        $uniqueLines | ForEach-Object { [void]$output.AppendLine("  $_") }
    } else {
        $totalMatches = ($fileMatches.Values | ForEach-Object { $_.Count }) | Measure-Object -Sum | Select-Object -ExpandProperty Sum
        [void]$output.AppendLine($Separator)
        [void]$output.AppendLine("[CONDENSED] Grep: `"$pattern`" -> $totalMatches matches in $($fileMatches.Count) files")
        foreach ($file in ($fileMatches.Keys | Sort-Object)) {
            $count = $fileMatches[$file].Count
            [void]$output.AppendLine("  $file ($count matches)")
        }
    }

    return $output.ToString().TrimEnd()
}

# ======================================================================
# CondenseMem0
# ======================================================================
function Invoke-CondenseMem0 {
    param([string]$Text)

    $output = New-Object System.Text.StringBuilder
    [void]$output.AppendLine($Separator)

    try {
        $data = $Text | ConvertFrom-Json
    } catch {
        [void]$output.AppendLine("[CONDENSED] Mem0: Input is not valid JSON - treating as raw text")
        $lines = $Text -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        [void]$output.AppendLine("Raw lines: $($lines.Count)")
        $lines | Select-Object -First 20 | ForEach-Object { [void]$output.AppendLine("  $_") }
        if ($lines.Count -gt 20) {
            [void]$output.AppendLine("  ... ($($lines.Count - 20) more lines omitted)")
        }
        return $output.ToString().TrimEnd()
    }

    $results = if ($data -is [array]) { $data } elseif ($data.results) { $data.results } elseif ($data.data) { $data.data } else { @($data) }
    $totalResults = $results.Count

    [void]$output.AppendLine("[CONDENSED] Mem0: $totalResults total results")

    $byType = @{}
    $byCategory = @{}
    $lowScore = @()
    $sortedByScore = $results | Sort-Object -Property @{Expression = {
        if ($null -ne $_.score) { [double]$_.score }
        elseif ($null -ne $_.relevance) { [double]$_.relevance }
        else { 0.0 }
    }} -Descending

    foreach ($r in $results) {
        $typeVal = if ($r.type) { $r.type } elseif ($r.metadata -and $r.metadata.type) { $r.metadata.type } else { 'unknown' }
        if (-not $byType.ContainsKey($typeVal)) { $byType[$typeVal] = 0 }
        $byType[$typeVal]++

        $catVal = if ($r.category) { $r.category } elseif ($r.metadata -and $r.metadata.category) { $r.metadata.category } else { 'none' }
        if (-not $byCategory.ContainsKey($catVal)) { $byCategory[$catVal] = 0 }
        $byCategory[$catVal]++

        $score = if ($null -ne $r.score) { [double]$r.score } elseif ($null -ne $r.relevance) { [double]$r.relevance } else { 0.5 }
        if ($score -lt 0.3) { $lowScore += @{result = $r; score = $score } }
    }

    [void]$output.AppendLine("By type: $($byType.Keys | ForEach-Object { "$_=$($byType[$_])" })")
    [void]$output.AppendLine("By category: $($byCategory.Keys | ForEach-Object { "$_=$($byCategory[$_])" })")

    [void]$output.AppendLine("Top 3 most relevant:")
    $sortedByScore | Select-Object -First 3 | ForEach-Object {
        $s = if ($null -ne $_.score) { $_.score } elseif ($null -ne $_.relevance) { $_.relevance } else { 'N/A' }
        $txt = if ($_.text) { $_.text.Substring(0, [Math]::Min(120, $_.text.Length)) } else { '<no text>' }
        $id = if ($_.id) { $_.id } elseif ($_.memory_id) { $_.memory_id } else { '<no id>' }
        [void]$output.AppendLine("  [$s] [$id] $txt")
    }

    if ($lowScore.Count -gt 0) {
        [void]$output.AppendLine("Low relevance (<0.3) - $($lowScore.Count) results:")
        $lowScore | ForEach-Object {
            $txt = if ($_.result.text) { $_.result.text.Substring(0, [Math]::Min(80, $_.result.text.Length)) } else { '<no text>' }
            [void]$output.AppendLine("  [$($_.score)] $txt")
        }
    }

    $texts = @()
    $dupCount = 0
    foreach ($r in $results) {
        $t = if ($r.text) { $r.text } else { '' }
        if ([string]::IsNullOrWhiteSpace($t)) { continue }
        $texts += $t
    }
    for ($i = 0; $i -lt $texts.Count; $i++) {
        for ($j = $i + 1; $j -lt $texts.Count; $j++) {
            $sim = Get-CosineSimilarity -A $texts[$i] -B $texts[$j]
            if ($sim -ge 0.8) {
                $dupCount++
                if ($dupCount -le 5) {
                    $t1 = $texts[$i].Substring(0, [Math]::Min(60, $texts[$i].Length))
                    $t2 = $texts[$j].Substring(0, [Math]::Min(60, $texts[$j].Length))
                    [void]$output.AppendLine("  [DUPE $i<->$j sim=$([Math]::Round($sim,2))] `"$t1...`" == `"$t2...`"")
                }
            }
        }
    }
    if ($dupCount -gt 5) { [void]$output.AppendLine("  ... ($($dupCount - 5) more duplicate pairs not shown)") }
    if ($dupCount -eq 0) { [void]$output.AppendLine("No duplicates detected (cosine > 0.8)") }

    return $output.ToString().TrimEnd()
}

# ======================================================================
# Main dispatch
# ======================================================================
$condensedOutput = ''

switch ($Command) {
    'CondenseBash' { $condensedOutput = Invoke-CondenseBash -Text $InputText -Type $CommandType }
    'CondenseRead' { $condensedOutput = Invoke-CondenseRead -Text $InputText -Path $FilePath }
    'CondenseGrep' { $condensedOutput = Invoke-CondenseGrep -Text $InputText }
    'CondenseMem0' { $condensedOutput = Invoke-CondenseMem0 -Text $InputText }
}

# --- Output to console ---
Write-Host "`n$condensedOutput`n" -ForegroundColor Cyan

# --- Log to condenser log ---
$logEntry = @"
[$Timestamp] Command=$Command Type=$CommandType File=$FilePath
$condensedOutput
$Separator

"@
Write-CondenserLog -Entry $logEntry

Write-Host "[Condenser] Log saved to: $LogFile" -ForegroundColor DarkGray
Write-Host "[Condenser] Modes: CondenseBash, CondenseRead, CondenseGrep, CondenseMem0" -ForegroundColor DarkGray
