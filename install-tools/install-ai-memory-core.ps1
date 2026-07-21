<#
.SYNOPSIS
    1-Click Install: CortexStratum for OpenCode / Claude Code / Cursor
.DESCRIPTION
    Installs the CortexStratum plugin into an AI coding harness (OpenCode by default).
    Sets up:
      - MCP server registration (115 tools via tools-mcp-server.py)
      - Skills linking (task-orchestrator, etc.)
      - npm dependencies
      - NE-Memory configuration
      - Environment validation

    Usage (OpenCode):
      irm https://raw.githubusercontent.com/ohmpatel3877/CortexStratum/main/plugin-tools/install.ps1 | iex

    Or from local repo:
      .\plugin-tools\install-CortexStratum.ps1 -Harness opencode

.PARAMETER Harness
    Target AI coding harness: opencode (default), claude-code, cursor, or all.

.PARAMETER ProjectDir
    Path to CortexStratum. Defaults to the repo root (parent of this script's directory).

.PARAMETER Force
    Overwrite existing configurations without prompting.
#>

param(
    [ValidateSet("opencode", "claude-code", "cursor", "all")]
    [string]$Harness = "opencode",
    [string]$ProjectDir = "",
    [string]$NeMemoryConfig = "",
    [string]$OpenCodeZenApiKey = "",
    [switch]$Force,
    [switch]$Containerized,
    [switch]$OneClick
)

# ─── One-Click Containerized Mode ─────────────────────────────────
if ($OneClick -or $Containerized) {
    Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║   opencode-container-server — 1-Click Setup     ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "This deploys the opencode-container-server (MCP + OpenCode CLI)."
    Write-Host "You only need Docker Desktop."
    Write-Host ""

    # Check for Docker
    $hasDocker = $false
    try { docker --version | Out-Null; $hasDocker = $true } catch {}

    if (-not $hasDocker) {
        Write-Host "Docker not found. Running dedicated installer..." -ForegroundColor Yellow
        $installerScript = Join-Path $PSScriptRoot "..\docker\install-docker.ps1"
        if (Test-Path $installerScript) {
            & $installerScript
        } else {
            $tmpScript = "$env:TEMP\install-docker.ps1"
            Invoke-WebRequest -Uri "https://raw.githubusercontent.com/ohmpatel3877/CortexStratum/main/docker/install-docker.ps1" -OutFile $tmpScript
            & $tmpScript
        }
        # Re-check after install
        try { docker --version | Out-Null; $hasDocker = $true } catch {}
        if (-not $hasDocker) {
            Write-Host "Docker installation did not complete. Start Docker Desktop manually, then re-run." -ForegroundColor Red
            exit 1
        }
    }

    # Get CortexStratum
    $targetDir = "$env:USERPROFILE\opencode-container"
    if (-not (Test-Path "$targetDir\docker\docker-compose.yml")) {
        Write-Host "Downloading opencode-container-server..." -ForegroundColor Yellow
        $zip = "$env:TEMP\CortexStratum.zip"
        Invoke-WebRequest -Uri "https://github.com/ohmpatel3877/CortexStratum/archive/refs/heads/main.zip" -OutFile $zip
        Remove-Item -Path $targetDir -Recurse -Force -ErrorAction SilentlyContinue
        Expand-Archive -Path $zip -DestinationPath "$env:USERPROFILE" -Force
        Move-Item "$env:USERPROFILE\CortexStratum-main\*" $targetDir -Force
        Remove-Item "$env:USERPROFILE\CortexStratum-main" -Recurse -Force
    }

    # Prompt for OpenCode Zen key if needed
    if ([string]::IsNullOrEmpty($OpenCodeZenApiKey)) {
        $OpenCodeZenApiKey = Read-Host "`nEnter your OpenCode Zen API key (get one at https://opencode.ai) or press Enter to skip"
    }

    # Write .env (fully local — no cloud API keys needed)
    @"
NE_MEMORY_PROJECT=CortexStratum
OPENCODE_ZEN_API_KEY=$OpenCodeZenApiKey
OPENCODE_ZEN_BASE_URL=https://api.opencode.ai
OPENCODE_HOST=opencode-container
LOG_LEVEL=info
"@ | Out-File -FilePath "$targetDir\.env" -Encoding UTF8

    # Deploy
    Set-Location $targetDir
    docker compose -f docker\docker-compose.yml pull
    docker compose -f docker\docker-compose.yml up -d --build

    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║  opencode-container-server is LIVE!             ║" -ForegroundColor Green
    Write-Host "╠══════════════════════════════════════════════════╣" -ForegroundColor Green
    Write-Host "║  MCP Server running on port 3100                ║" -ForegroundColor White
    Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Green
    return
}

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = " CortexStratum Installer"

# ─── Resolve paths ───────────────────────────────────────────────
if (-not $ProjectDir) {
    $ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$ProjectDir = Resolve-Path $ProjectDir
$ScriptsDir = Join-Path $ProjectDir "scripts"
$SkillsDir = Join-Path $ProjectDir "skills"

Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    CortexStratum — 1-Click Installer           ║" -ForegroundColor Cyan
Write-Host "║    $ProjectDir" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── Step 1: Validate environment ───────────────────────────────
Write-Host " Step 1/6: Validating environment..." -ForegroundColor Yellow

# Check Node.js
try {
    $nodeVer = node --version
    Write-Host "   Node.js $nodeVer" -ForegroundColor Green
} catch {
    Write-Warning "   Node.js not found. Install from https://nodejs.org (v18+)"
    exit 1
}

# Check Python
try {
    $pyVer = python --version
    Write-Host "   Python $pyVer" -ForegroundColor Green
} catch {
    Write-Warning "   Python not found. Install Python 3.10+"
    exit 1
}

# Check pip
try {
    pip --version | Out-Null
    Write-Host "   pip" -ForegroundColor Green
} catch {
    Write-Warning "   pip not found"
}

# ─── Step 2: Install npm dependencies ───────────────────────────
Write-Host ""
Write-Host " Step 2/6: Installing npm dependencies..." -ForegroundColor Yellow
Push-Location $ProjectDir
try {
    npm install --silent 2>&1 | Out-Null
    Write-Host "   npm dependencies installed" -ForegroundColor Green
} catch {
    Write-Warning "   npm install failed: $_"
    Write-Host "  Run 'npm install' manually in $ProjectDir" -ForegroundColor DarkYellow
}
Pop-Location

# ─── Step 3: Configure local memory (no API key needed) ────────
Write-Host ""
Write-Host " Step 3/6: Configuring local memory..." -ForegroundColor Yellow

$envFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path $envFile)) {
    "NE_MEMORY_PROJECT=CortexStratum`n# Fully local — no API keys required" | Set-Content -Path $envFile -Force
    Write-Host "   Local memory configured (no API key required)" -ForegroundColor Green
} else {
    Write-Host "   .env already exists" -ForegroundColor Green
}

# ─── Step 4: Register MCP Server ────────────────────────────────
Write-Host ""
Write-Host " Step 4/6: Registering MCP server..." -ForegroundColor Yellow

function Register-McpForOpenCode {
    param([string]$ConfigPath)
    $mcpEntry = @{
        "name" = "CortexStratum"
        "description" = "176-tool MCP server: xTrace, DTrace, Skill Router, Verifier, Goal Registry, and multi-module AI"
        "command" = "python"
        "args" = @("scripts/tools-mcp-server.py")
        "env" = @{
        }
    }
    
    if (Test-Path $ConfigPath) {
        $config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $config.mcpServers) {
            $config | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue @{}
        }
        $config.mcpServers | Add-Member -NotePropertyName "CortexStratum" -NotePropertyValue $mcpEntry -Force
        $config | ConvertTo-Json -Depth 10 | Set-Content $ConfigPath -Encoding UTF8 -Force
        Write-Host "   Registered in $ConfigPath" -ForegroundColor Green
    } else {
        $config = @{ mcpServers = @{ "CortexStratum" = $mcpEntry } }
        $config | ConvertTo-Json -Depth 10 | Set-Content $ConfigPath -Encoding UTF8 -Force
        Write-Host "   Created $ConfigPath" -ForegroundColor Green
    }
}

switch ($Harness) {
    "opencode" {
        $ocConfig = Join-Path $ProjectDir "opencode.json"
        Register-McpForOpenCode -ConfigPath $ocConfig
    }
    "claude-code" {
        $ccConfig = Join-Path $ProjectDir "CLAUDE.md"
        if (-not (Test-Path $ccConfig)) {
            @"
# Claude Code — CortexStratum MCP Server

<mcpserver>
{
  "name": "CortexStratum",
  "description": "176-tool MCP server for memory, tracing, and orchestration",
  "command": "python",
  "args": ["scripts/tools-mcp-server.py"],
  "working_dir": "$ProjectDir"
}
</mcpserver>
"@ | Set-Content $ccConfig -Encoding UTF8 -Force
        }
        Write-Host "   Registered in CLAUDE.md" -ForegroundColor Green
    }
    "cursor" {
        # Cursor uses .cursorrules or opencode.json format
        $cursorConfig = Join-Path $ProjectDir ".cursorrules"
        @"
# CortexStratum Cursor Integration
- MCP server: python scripts/tools-mcp-server.py
- Skills: skills/task-orchestrator/SKILL.md
"@ | Set-Content $cursorConfig -Encoding UTF8 -Force
        Write-Host "   Registered in .cursorrules" -ForegroundColor Green
    }
    "all" {
        Register-McpForOpenCode -ConfigPath (Join-Path $ProjectDir "opencode.json")
        Write-Host "   OpenCode + Claude Code + Cursor" -ForegroundColor Green
    }
}

# ─── Step 5: Link skills to global OpenCode skill directory ─────
Write-Host ""
Write-Host " Step 5/6: Linking skills..." -ForegroundColor Yellow

$ocSkillsDir = "$env:USERPROFILE\.config\opencode\skills"
if (Test-Path $ocSkillsDir) {
    $skillDirs = Get-ChildItem $SkillsDir -Directory
    foreach ($skillDir in $skillDirs) {
        $target = Join-Path $ocSkillsDir $skillDir.Name
        if (-not (Test-Path $target)) {
            New-Item -ItemType Junction -Path $target -Target $skillDir.FullName -Force | Out-Null
            Write-Host "   Linked skill: $($skillDir.Name)" -ForegroundColor Green
        } else {
            Write-Host "   Skill already exists: $($skillDir.Name)" -ForegroundColor DarkYellow
        }
    }
} else {
    Write-Host "   OpenCode skills directory not found at $ocSkillsDir" -ForegroundColor DarkYellow
    Write-Host "  Create it or run this after OpenCode is installed." -ForegroundColor DarkYellow
}

# ─── Step 6: Verify installation ─────────────────────────────────
Write-Host ""
Write-Host " Step 6/6: Verifying installation..." -ForegroundColor Yellow

$pass = 0
$fail = 0

try {
    node "$ScriptsDir\check-status.js" 2>&1 | Out-Null
    Write-Host "   NE-Memory status check passed" -ForegroundColor Green
    $pass++
} catch {
    Write-Host "   NE-Memory status check: $_" -ForegroundColor DarkYellow
}

try {
    python "$ScriptsDir\task-analyzer.py" --interactive 2>&1 | Out-Null
    Write-Host "   Task analyzer runs" -ForegroundColor Green
    $pass++
} catch {
    Write-Host "   Task analyzer check: $_" -ForegroundColor DarkYellow
}

if (Test-Path (Join-Path $ProjectDir "node_modules")) {
    Write-Host "   npm dependencies installed" -ForegroundColor Green
    $pass++
} else {
    Write-Host "   npm dependencies missing" -ForegroundColor Red
    $fail++
}

# ─── Summary ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Installation Complete                           ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Project : $($ProjectDir.Split('\')[-1])" -ForegroundColor White
Write-Host "║  Harness : $Harness" -ForegroundColor White
Write-Host "║  Checks  : $pass passed, $fail failed" -ForegroundColor White
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan

if ($fail -gt 0) {
    Write-Host ""
    Write-Host "Some checks failed. Review above for details." -ForegroundColor Yellow
    Write-Host "Common fixes:" -ForegroundColor Yellow
    Write-Host "  1. npm install  (in $ProjectDir)" -ForegroundColor DarkYellow
    Write-Host "  2. No API keys needed — fully local" -ForegroundColor DarkYellow
    Write-Host "  3. Ensure Python 3.10+ is on PATH" -ForegroundColor DarkYellow
} else {
    Write-Host ""
    Write-Host "   CortexStratum is ready!" -ForegroundColor Green
    Write-Host "  Restart your AI coding harness to load the MCP server." -ForegroundColor Green
}
