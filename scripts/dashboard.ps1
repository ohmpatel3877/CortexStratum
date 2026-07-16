<#
.SYNOPSIS
  ai-memory-core Dashboard — usage, memories, goals, commitments, errors, MCP status.
.DESCRIPTION
  Full-session overview panel pulling from mem0, Goal Registry, Commitment Checker,
  xTrace error registry, DTrace decisions, and MCP server status.
  Registered as /dashboard command.

.PARAMETER Memories
  Show N recent relevant memories (default: 5, max: 20).
.PARAMETER Browse
  Open interactive memory browser by type (architecture_decisions, bug_fix, etc.)
.PARAMETER Refresh
  Force re-fetch all data instead of using cached values.
.PARAMETER Simple
  Compact one-line-per-section output (no boxes/borders).
#>

param(
    [int]$Memories = 5,
    [string]$Browse,
    [switch]$Refresh,
    [switch]$Simple
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DataDir = Join-Path $ProjectRoot "data"

# Colors
$cHeader = "Cyan"
$cLabel = "Yellow"
$cValue = "White"
$cGood = "Green"
$cWarn = "Yellow"
$cBad = "Red"
$cDim = "DarkGray"
$cAccent = "Magenta"

function Write-Box($title, $lines) {
    if ($Simple) { Write-Host "[$title] $($lines[0])"; return }
    $w = [Math]::Max(40, ($lines | ForEach-Object { $_.Length } | Measure-Object -Maximum).Maximum + 4)
    $bar = "=" * $w
    Write-Host $bar -ForegroundColor $cHeader
    Write-Host "  $title" -ForegroundColor $cHeader
    Write-Host $bar -ForegroundColor $cHeader
    foreach ($l in $lines) { Write-Host "  $l" }
    Write-Host $bar -ForegroundColor $cHeader
}

function Write-ProgressBar($label, $pct, $used, $total) {
    $w = 20
    $filled = [Math]::Floor($pct / 100 * $w)
    $empty = $w - $filled
    $bar = "[" + ("#" * $filled) + ("." * $empty) + "]"
    $color = if ($pct -gt 80) { $cBad } elseif ($pct -gt 50) { $cWarn } else { $cGood }
    Write-Host "  $label $bar $([Math]::Round($pct,1))% ($used / $total)" -ForegroundColor $color
}

# ───── HEADER ─────
if (-not $Simple) {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor $cHeader
    Write-Host "  ║       ai-memory-core DASHBOARD           ║" -ForegroundColor $cHeader
    Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor $cHeader
    Write-Host ("  Session: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))") -ForegroundColor $cDim
}

# ───── 1. USAGE BAR ─────
Write-Box "📊 USAGE" @(
    "Model: opencode-go/deepseek-v4-flash-free",
    "Status: Active (this session)"
)
# Attempt to read usage from prompt-history or env
$usageFile = Join-Path (Join-Path $env:USERPROFILE ".local") "state/opencode/prompt-history.jsonl"
if (Test-Path $usageFile) {
    $lines = Get-Content $usageFile -ErrorAction SilentlyContinue
    $totalTokens = 0
    foreach ($l in $lines[-20..-1]) {
        try { $obj = $l | ConvertFrom-Json -ErrorAction SilentlyContinue; if ($obj.tokens) { $totalTokens += [int]$obj.tokens } } catch {}
    }
    if ($totalTokens -gt 0) {
        $limit = 1000000
        $pct = [Math]::Min(100, [Math]::Round($totalTokens / $limit * 100, 1))
        $usedStr = if ($totalTokens -gt 1000) { "$([Math]::Round($totalTokens/1000,1))K" } else { "$totalTokens" }
        $limitStr = if ($limit -gt 1000) { "$([Math]::Round($limit/1000,1))K" } else { "$limit" }
        Write-ProgressBar "Tokens" $pct $usedStr $limitStr
    }
}

# ───── 2. RECENT MEMORIES (memory book) ─────
Write-Box "📚 MEMORY BOOK (last $Memories)" @(
    "Source: mem0 (ohmpa/ohmpa)",
    "Run '/dashboard -Browse bug_fix' to filter by type"
)

if ($Browse) {
    # Browse mode: filter by type
    $searchResults = & {
        # Use mem0-search compatible approach - search by type keyword
        python -c "
import json, urllib.request, os
query = 'type:$Browse'
url = 'https://api.mem0.ai/v3/memories/?user_id=ohmpa&app_id=ohmpa&limit=10'
try:
    req = urllib.request.Request(url, headers={'Authorization': 'Token ' + os.environ.get('MEM0_API_KEY','')})
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read())
    for m in data.get('results',[])[:10]:
        t = m.get('metadata',{}).get('type','unknown')
        txt = m.get('memory','')[:120]
        print(f'{t}|{m[\"id\"][:8]}|{txt}')
except Exception as e:
    print(f'error: {e}')
" 2>$null
    }
    if ($LASTEXITCODE -eq 0 -and $searchResults) {
        $count = 0
        foreach ($r in $searchResults) {
            if ($r -match '^(.+?)\|(.+?)\|(.+)$') {
                $t = $matches[1]; $id = $matches[2]; $txt = $matches[3]
                if ($t -eq $Browse -or $Browse -eq "all") {
                    $count++
                    $color = switch ($t) {
                        'bug_fix' { $cBad }
                        'task_learning' { $cAccent }
                        'code_preference' { $cGood }
                        'user_preference' { $cWarn }
                        default { $cDim }
                    }
                    Write-Host ("  [$t] $txt") -ForegroundColor $color
                }
            }
        }
        if ($count -eq 0) { Write-Host "  (no memories of type '$Browse')" -ForegroundColor $cDim }
    } else {
        Write-Host "  (mem0 API unavailable for browse)" -ForegroundColor $cDim
    }
} else {
    # Default: show recent memories via mem0 search
    $memResults = & {
        python -c "
import json, urllib.request, os
url = 'https://api.mem0.ai/v3/memories/?user_id=ohmpa&app_id=ohmpa&limit=$Memories'
try:
    req = urllib.request.Request(url, headers={'Authorization': 'Token ' + os.environ.get('MEM0_API_KEY','')})
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read())
    for m in data.get('results',[])[:$Memories]:
        t = m.get('metadata',{}).get('type','unknown')
        txt = m.get('memory','')[:100]
        created = m.get('createdAt','')[:10]
        print(f'{t}|{created}|{txt}')
except Exception as e:
    print(f'error: {e}')
" 2>$null
    }
    if ($LASTEXITCODE -eq 0 -and $memResults) {
        foreach ($r in $memResults) {
            if ($r -match '^(.+?)\|(.+?)\|(.+)$') {
                $t = $matches[1]; $d = $matches[2]; $txt = $matches[3]
                $color = switch ($t) {
                    'bug_fix' { $cBad }
                    'task_learning' { $cAccent }
                    'code_preference' { $cGood }
                    'user_preference' { $cWarn }
                    default { $cDim }
                }
                Write-Host ("  [$t] $txt") -ForegroundColor $color
            }
        }
    } else {
        Write-Host "  (no memories loaded yet this session)" -ForegroundColor $cDim
    }
}

# ───── 3. COMMITMENTS ─────
$commitPath = Join-Path $DataDir "commitment-registry.json"
if (Test-Path $commitPath) {
    try {
        $reg = Get-Content $commitPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $today = (Get-Date).ToString("yyyy-MM-dd")
        $pending = $reg.commitments | Where-Object { $_.next_verify -le $today }
        $done = $reg.commitments | Where-Object { $_.verified_sessions -contains (Get-Date).ToString("yyyyMMdd-HHmmss") -or $_.verified_sessions.Count -gt 0 }
        $total = $reg.commitments.Count
        Write-Box "📋 COMMITMENTS ($($pending.Count) pending / $total total)" @(
            "Behavioral rules to verify each session"
        )
        foreach ($c in $reg.commitments) {
            $verified = $c.verified_sessions.Count -gt 0
            $mark = if ($verified) { "[X]" } else { "[ ]" }
            $col = if ($verified) { $cGood } else { $cDim }
            $txt = $c.text
            if ($txt.Length -gt 80) { $txt = $txt.Substring(0,77) + "..." }
            Write-Host ("  $mark $($c.id) - $txt") -ForegroundColor $col
        }
    } catch {
        Write-Host "  (commitment registry corrupt)" -ForegroundColor $cBad
    }
} else {
    Write-Host "  (no commitment registry)" -ForegroundColor $cDim
}

# ───── 4. GOAL STATUS ─────
$goalPath = Join-Path $DataDir "goal-registry.json"
if (Test-Path $goalPath) {
    try {
        $goal = Get-Content $goalPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $sgCount = $goal.sub_goals.Count
        $completed = ($goal.sub_goals | Where-Object { $_.status -eq "completed" }).Count
        $orig = $goal.original_goal
        if ($orig.Length -gt 50) { $orig = $orig.Substring(0,47) + "..." }
        Write-Box "🎯 GOAL REGISTRY" @(
            "Goal: $orig",
            "Sub-goals: $completed/$sgCount completed"
        )
    } catch {
        Write-Host "  (goal registry corrupt)" -ForegroundColor $cBad
    }
} else {
    Write-Box "🎯 GOAL REGISTRY" @(
        "No active goal. Start one with:",
        "  .\goal-registry.ps1 -Action Init -Goal ""<goal>"""
    )
}

# ───── 5. DECISIONS (DTrace) ─────
$decPath = Join-Path $DataDir "decision-registry.json"
if (Test-Path $decPath) {
    try {
        $dReg = Get-Content $decPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $totalD = $dReg.decisions.Count
        $activeD = ($dReg.decisions | Where-Object { $_.status -eq "active" }).Count
        $recent = $dReg.decisions | Sort-Object created_at -Descending | Select-Object -First 3
        $lines = @("$totalD decisions logged, $activeD active")
        foreach ($d in $recent) {
            $t = $d.title
            if ($t.Length -gt 55) { $t = $t.Substring(0,52) + "..." }
            $lines += "  [$($d.id)] $t"
        }
        Write-Box "📝 DECISIONS (DTrace)" $lines
    } catch {
        Write-Host "  (decision registry corrupt)" -ForegroundColor $cBad
    }
} else {
    Write-Box "📝 DECISIONS (DTrace)" @("No decisions logged yet")
}

# ───── 6. ERRORS (xTrace) ─────
$errPath = Join-Path $DataDir "error-registry.json"
if (Test-Path $errPath) {
    try {
        $eReg = Get-Content $errPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $totalE = $eReg.errors.Count
        $unresolved = ($eReg.errors | Where-Object { $_.status -eq "unresolved" }).Count
        $resolved = $totalE - $unresolved
        $statusColor = if ($unresolved -gt 0) { $cWarn } else { $cGood }
        Write-Box "❌ ERRORS (xTrace)" @(
            "Total: $totalE | Resolved: $resolved | Unresolved: $unresolved"
        )
    } catch {
        Write-Host "  (error registry corrupt)" -ForegroundColor $cBad
    }
} else {
    Write-Box "❌ ERRORS (xTrace)" @("No errors logged — clean slate")
}

# ───── 7. MCP STATUS ─────
$mcpStatus = @("ai-memory-core-tools: check right sidebar", "mem0: connected via API", "LSP: disabled")
Write-Box "🔌 MCP SERVERS" $mcpStatus

# ───── 8. QUICK ACTIONS ─────
Write-Box "⚡ QUICK ACTIONS" @(
    "  /consult <question>    — Multi-perspective decision analysis",
    "  /mem0-dream            — Consolidate duplicate memories",
    "  /mem0-search <query>   — Search memories",
    "  /verify                — Run verification gate",
    "  /review <files>        — Review code changes"
)

# ───── FOOTER ─────
Write-Host ""
Write-Host "  Dashboard loaded at $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor $cDim
Write-Host "  Tip: use -Browse <type> to filter memories by category" -ForegroundColor $cDim
Write-Host "  Tip: use -Simple for compact output" -ForegroundColor $cDim
