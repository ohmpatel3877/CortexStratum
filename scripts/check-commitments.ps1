param(
  [switch]$SessionStart,
  [string]$Verify,
  [switch]$DryRun
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$RegistryPath = Join-Path (Join-Path $ProjectRoot "data") "commitment-registry.json"
$Today = (Get-Date).ToString("yyyy-MM-dd")
$CurrentSession = if ($env:OPENCODE_SESSION_ID) { $env:OPENCODE_SESSION_ID } else { (Get-Date).ToString("yyyyMMdd-HHmmss") }

function Seed-DefaultRegistry {
  $seed = @{
    version = 1
    commitments = @(
      @{ id = "b1"; text = "Batch-load skills at session start before any tool execution"; source = "code_preference"; stored_date = "2026-07-15"; verified_sessions = @(); next_verify = "2026-07-16" }
      @{ id = "b2"; text = "Use 2 targeted memory queries max per round"; source = "code_preference"; stored_date = "2026-07-15"; verified_sessions = @(); next_verify = "2026-07-16" }
      @{ id = "b3"; text = "Verify all file:line claims with read/grep before stating as fact"; source = "code_preference"; stored_date = "2026-07-15"; verified_sessions = @(); next_verify = "2026-07-16" }
      @{ id = "b4"; text = "Group independent reads and searches into single parallel batches"; source = "code_preference"; stored_date = "2026-07-15"; verified_sessions = @(); next_verify = "2026-07-16" }
      @{ id = "b5"; text = "Run lint + typecheck + tests before marking any code task complete"; source = "code_preference"; stored_date = "2026-07-15"; verified_sessions = @(); next_verify = "2026-07-16" }
    )
  }

  $parent = Split-Path $RegistryPath -Parent
  if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  $json = $seed | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
  Write-Host "[seed] Created commitment-registry.json with 5 default commitments"
}

function Read-Registry {
  if (-not (Test-Path $RegistryPath)) {
    Write-Host "[warn] commitment-registry.json not found — auto-seeding defaults"
    Seed-DefaultRegistry
  }
  try {
    $raw = Get-Content $RegistryPath -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    Write-Host "[warn] corrupt registry — re-seeding defaults"
    Seed-DefaultRegistry
    $raw = Get-Content $RegistryPath -Raw -Encoding UTF8 | ConvertFrom-Json
  }
  return $raw
}

function Write-Registry($registry) {
  $json = $registry | ConvertTo-Json -Depth 10; [System.IO.File]::WriteAllText($RegistryPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Format-Checklist($active) {
  $count = $active.Count
  Write-Host "===== ACTIVE COMMITMENTS ($count pending) ====="
  foreach ($c in $active) {
    Write-Host "[ ] $($c.text)"
  }
  Write-Host ""
  Write-Host "Usage: .\check-commitments.ps1 -Verify [id]  (marks commitment verified for this session)"
}

if (-not $SessionStart -and -not $Verify) {
  Write-Host "Usage:"
  Write-Host "  check-commitments.ps1 -SessionStart          # Show pending commitments"
  Write-Host "  check-commitments.ps1 -Verify <id>           # Mark commitment as verified"
  exit 0
}

$registry = Read-Registry

if ($SessionStart) {
  $active = $registry.commitments | Where-Object { $_.next_verify -le $Today }
  Format-Checklist $active
  exit 0
}

if ($Verify) {
  $match = $registry.commitments | Where-Object { $_.id -eq $Verify }
  if (-not $match) {
    Write-Error "Commitment '$Verify' not found in registry"
    exit 1
  }

  if ($match.verified_sessions -contains $CurrentSession) {
    Write-Host "[ok] Commitment '$Verify' already verified this session"
    exit 0
  }

  if (-not $DryRun) {
    $match.verified_sessions += $CurrentSession
    Write-Registry $registry
    Write-Host "[verified] Commitment '$Verify' marked verified for session $CurrentSession"
  } else {
    Write-Host "[dry-run] Would mark '$Verify' as verified for session $CurrentSession"
  }
  exit 0
}
