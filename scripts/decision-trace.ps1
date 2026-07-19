param(
    [Parameter(Position=0)]
    [string]$Action,

    [string]$Title,
    [string]$Context,
    [string]$Decision,
    [string[]]$Alternatives,
    [string]$Rationale,
    [string[]]$Consequences,
    [string[]]$Files,
    [string]$Category,
    [string]$Id,
    [string]$Status,
    [string]$Notes,
    [string]$SupersededBy,
    [string]$Keyword,
    [string]$FilePath
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$script:RegistryPath = Join-Path (Join-Path $ProjectRoot "data") "decision-registry.json"
$script:NextNum = 1

function Ensure-Registry {
    $dir = Split-Path $RegistryPath -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    if (-not (Test-Path $RegistryPath)) {
        $seed = @(
            @{
                id = "dt-20260715-001"
                title = "Store behavioral fixes as code_preference not task_learning"
                context = "Mem0 memory categorization was inconsistent; task_learning had too much noise"
                decision = "Use metadata.type='code_preferences' for behavioral/process fixes, task_learning only for factual domain learnings"
                alternatives = @("Keep everything in task_learning", "Create a separate rule_preferences type")
                rationale = "Separates actionable behavioral rules from passive knowledge, enabling targeted retrieval"
                consequences = @("Must set metadata.type explicitly on every memory write", "May need migration of existing mixed entries")
                category = "architecture"
                files = @("scripts\decision-trace.ps1", "AGENTS.md")
                status = "active"
                superseded_by = $null
                created_at = "2026-07-15T10:00:00Z"
                updated_at = "2026-07-15T10:00:00Z"
                notes = ""
            }
            @{
                id = "dt-20260715-002"
                title = "Limit mem0 search to 2 queries max per round"
                context = "Parallel mem0 searches were spawning 5+ simultaneous calls, wasting tokens and hitting rate limits"
                decision = "Cap parallel mem0 queries to 2 per round; use broader queries with top_k=15 instead of narrow queries with top_k=5"
                alternatives = @("No limit (parallelism handles it)", "Single query per round with rerank")
                rationale = "Reduces token waste by 60% while maintaining recall quality through broader result windows"
                consequences = @("Slightly higher latency per query from larger top_k", "Rare edge cases may need manual re-query")
                category = "process"
                files = @("AGENTS.md")
                status = "active"
                superseded_by = $null
                created_at = "2026-07-15T10:30:00Z"
                updated_at = "2026-07-15T10:30:00Z"
                notes = ""
            }
            @{
                id = "dt-20260715-003"
                title = "Centralize meta-cognitive artifacts in cortex-stratum"
                context = "Model study guides, behavioral fix lists, and process docs were scattered across multiple repos and local paths"
                decision = "All meta-cognitive artifacts live under cortex-stratum"
                alternatives = @("Keep artifacts co-located with each project", "Use a separate meta-knowledge repo")
                rationale = "Single source of truth for agent improvement artifacts; accessible from any project context via reference"
                consequences = @("cortex-stratum becomes a dependency for all agent sessions", "Must maintain consistent cross-references")
                category = "architecture"
                files = @("model-study-guide.md", "data\decision-registry.json", "data\error-registry.json")
                status = "active"
                superseded_by = $null
                created_at = "2026-07-15T11:00:00Z"
                updated_at = "2026-07-15T11:00:00Z"
                notes = ""
            }
        )
        $initial = @{ version = 1; decisions = $seed }
        $json = $initial | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
        $script:NextNum = 4
    }
}

function Load-Registry {
    Ensure-Registry
    try {
        $content = Get-Content -Path $RegistryPath -Raw -Encoding UTF8
        $data = $content | ConvertFrom-Json
    } catch {
        Write-Host "[warn] corrupt registry - resetting to empty"
        $data = @{ version = 1; decisions = @() }
    }
    if ($data.decisions.Count -gt 0) {
        $last = $data.decisions[-1].id
        if ($last -match 'dt-\d{8}-(\d+)') {
            $script:NextNum = [int]$Matches[1] + 1
        }
    }
    return $data
}

function Save-Registry($data) {
    $json = $data | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Get-Timestamp {
    (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
}

function Invoke-Add {
    if (-not $Title -or -not $Decision -or -not $Category) {
        Write-Error -Message "Add requires Title, Decision, and Category parameters"
        exit 1
    }
    $data = Load-Registry
    $today = (Get-Date).ToString("yyyyMMdd")
    $id = "dt-$today-$($script:NextNum.ToString('D3'))"
    $now = Get-Timestamp

    $entry = @{
        id = $id
        title = $Title
        context = if ($Context) { $Context } else { "" }
        decision = $Decision
        alternatives = if ($Alternatives) { @($Alternatives) } else { @() }
        rationale = if ($Rationale) { $Rationale } else { "" }
        consequences = if ($Consequences) { @($Consequences) } else { @() }
        category = $Category
        files = if ($Files) { @($Files) } else { @() }
        status = "active"
        superseded_by = $null
        created_at = $now
        updated_at = $now
        notes = if ($Notes) { $Notes } else { "" }
    }
    $data.decisions += $entry
    $script:NextNum++
    Save-Registry $data
    Write-Host ("Added decision: $id - $Title")
}

function Invoke-Update {
    if (-not $Id) {
        Write-Error -Message "Update requires ID parameter"
        exit 1
    }
    $data = Load-Registry
    $entry = $data.decisions | Where-Object { $_.id -eq $Id }
    if (-not $entry) {
        $errMsg = "Decision not found: $Id"
        Write-Error -Message $errMsg
        exit 1
    }

    $validStatuses = @("active", "superseded", "deprecated", "reverted")
    if ($Status -and $validStatuses -notcontains $Status) {
        $statusMsg = "Status must be one of: " + ($validStatuses -join ', ')
        Write-Error -Message $statusMsg
        exit 1
    }
    if ($Status) { $entry.status = $Status }
    if ($Notes) { $entry.notes = $Notes }

    if ($Status -eq "superseded") {
        if ($SupersededBy) {
            $entry.superseded_by = $SupersededBy
        }
    }

    $entry.updated_at = Get-Timestamp
    Save-Registry $data
    Write-Host ("Updated decision: $Id -- status: $Status, superseded_by: $SupersededBy")
}

function Invoke-Search {
    if (-not $Keyword) {
        Write-Error -Message "Search requires Keyword parameter"
        exit 1
    }
    $data = Load-Registry
    $kw = $Keyword.ToLower()
    $results = $data.decisions | Where-Object {
        $_.title.ToLower() -like "*$kw*" -or
        $_.context.ToLower() -like "*$kw*" -or
        $_.decision.ToLower() -like "*$kw*" -or
        $_.rationale.ToLower() -like "*$kw*" -or
        $_.category.ToLower() -like "*$kw*"
    }
    if ($results.Count -eq 0) {
        Write-Host "No decisions match keyword: $Keyword"
        return
    }
    foreach ($item in $results) {
        Write-Host ("--- " + $item.id + " ---")
        Write-Host ("  title:    " + $item.title)
        Write-Host ("  category: " + $item.category)
        Write-Host ("  status:   " + $item.status)
        Write-Host ("  date:     " + $item.created_at)
    }
}

function Invoke-ByFile {
    if (-not $FilePath) {
        Write-Error -Message "ByFile requires FilePath parameter"
        exit 1
    }
    $data = Load-Registry
    $results = $data.decisions | Where-Object {
        $_.files -contains $FilePath
    }
    if ($results.Count -eq 0) {
        Write-Host "No decisions affect file: $FilePath"
        return
    }
    Write-Host ("=== Decisions affecting " + $FilePath + " ===")
    foreach ($item in $results) {
        Write-Host ("  " + $item.id + " - " + $item.title + " - " + $item.status + " - " + $item.category)
    }
}

function Invoke-Status {
    $data = Load-Registry
    $total = $data.decisions.Count

    $byCategory = $data.decisions | Group-Object -Property category | Sort-Object Count -Descending
    $byStatus = $data.decisions | Group-Object -Property status

    $thirtyDaysAgo = (Get-Date).AddDays(-30)
    $superseded = $data.decisions | Where-Object {
        $_.status -eq "superseded" -and
        $_.updated_at -and
        [DateTime]$_.updated_at -ge $thirtyDaysAgo
    }

    Write-Host "=== Decision Registry Status ==="
    Write-Host "Total decisions:  $total"
    Write-Host ""
    Write-Host "By category:"
    foreach ($item in $byCategory) {
        Write-Host ("  " + $item.Name + ": " + $item.Count)
    }
    Write-Host ""
    Write-Host "By status:"
    foreach ($item in $byStatus) {
        Write-Host ("  " + $item.Name + ": " + $item.Count)
    }
    if ($superseded.Count -gt 0) {
        Write-Host ""
        Write-Host "Recently superseded (last 30 days):"
        foreach ($item in $superseded) {
            Write-Host ("  " + $item.id + " - " + $item.title + " (superseded_by=" + $item.superseded_by + ")")
        }
    }
}

switch ($Action) {
    "Add"     { Invoke-Add }
    "Update"  { Invoke-Update }
    "Search"  { Invoke-Search }
    "ByFile"  { Invoke-ByFile }
    "Status"  { Invoke-Status }
    default {
        Write-Host 'Usage: .\decision-trace.ps1 -Action (Add|Update|Search|ByFile|Status) [params]'
        Write-Host ''
        Write-Host 'Commands:'
        Write-Host '  Add     -Action Add -Title [text] -Decision [text] -Category [category]'
        Write-Host '          [-Context [text]] [-Alternatives a,b] [-Rationale [text]]'
        Write-Host '          [-Consequences [a,b]] [-Files [path,...]] [-Notes [text]]'
        Write-Host '  Update  -Action Update -Id [id] -Status (active|superseded|deprecated|reverted)'
        Write-Host '          [-Notes [text]] [-SupersededBy [id]]'
        Write-Host '  Search  -Action Search -Keyword [text]'
        Write-Host '  ByFile  -Action ByFile -FilePath [path]'
        Write-Host '  Status  -Action Status'
    }
}
