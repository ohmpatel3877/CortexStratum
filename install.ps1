<#
.SYNOPSIS
    opencode-container-server — One-click installer
.DESCRIPTION
    Downloads Docker if needed, builds the container, prints config.
    Right-click → "Run with PowerShell". Window stays open.
#>

$Host.UI.RawUI.WindowTitle = "opencode-container-server"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  opencode-container-server — 1-Click Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ─── Self-elevate ─────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Elevating to administrator..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Start-Sleep -Seconds 2
    exit
}

$exitCode = 0

# ─── Step 1: Docker ───────────────────────────────────────────────
Write-Host ""
Write-Host "Step 1/3 — Checking for Docker..." -ForegroundColor Yellow

$hasDocker = $false
try { $null = docker --version; $hasDocker = $true } catch {}

if (-not $hasDocker) {
    Write-Host "  Docker not found. Downloading installer..." -ForegroundColor Yellow
    $installer = "$env:TEMP\DockerDesktopInstaller.exe"
    try {
        Invoke-WebRequest -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -OutFile $installer -UseBasicParsing
    } catch {
        Write-Host "  FAILED to download Docker. Check internet." -ForegroundColor Red
        Write-Host "  $_" -ForegroundColor Red
        $exitCode = 1
    }
    if ($exitCode -eq 0) {
        Write-Host "  Installing Docker Desktop..." -ForegroundColor Yellow
        Start-Process -FilePath $installer -ArgumentList "install --quiet" -Wait
        Write-Host "  Starting Docker..." -ForegroundColor Yellow
        Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
        Write-Host "  Waiting 30 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
    }
} else {
    Write-Host "  Docker: $(docker --version)" -ForegroundColor Green
}

# ─── Step 2: Download files ───────────────────────────────────────
if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "Step 2/3 — Downloading container files..." -ForegroundColor Yellow

    $workDir = "$env:USERPROFILE\opencode-container"
    New-Item -ItemType Directory -Path $workDir -Force | Out-Null
    Set-Location $workDir
    Write-Host "  Working directory: $workDir" -ForegroundColor Gray

    $files = @{
        "docker-compose.yml" = "https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/opencode-compose.yml"
        "Dockerfile" = "https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/Dockerfile"
    }

    foreach ($file in $files.Keys) {
        Write-Host "  Downloading $file..." -ForegroundColor Gray
        try {
            Invoke-WebRequest -Uri $files[$file] -OutFile $file -UseBasicParsing
        } catch {
            Write-Host "  FAILED to download $file" -ForegroundColor Red
            $exitCode = 1
            break
        }
    }
}

# ─── Step 3: Build ────────────────────────────────────────────────
if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "Step 3/3 — Building container..." -ForegroundColor Yellow
    Write-Host "  First build takes 1-3 minutes..." -ForegroundColor Gray

    $result = docker compose up -d --build 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  BUILD FAILED" -ForegroundColor Red
        Write-Host "  $result" -ForegroundColor Red
        Write-Host "  Make sure Docker Desktop is running and try again." -ForegroundColor Yellow
        $exitCode = 1
    }
}

# ─── Verify ────────────────────────────────────────────────────────
if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "  Testing connection..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    try {
        $count = docker exec opencode-server python3 -c "import json; t=json.load(open('/app/data/tool-inventory.json')); print(len(t))" 2>$null
        Write-Host ""
        Write-Host "============================================" -ForegroundColor Green
        Write-Host "  SUCCESS! Server running ($count tools ready)" -ForegroundColor Green
        Write-Host "============================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Add to your OpenCode config:" -ForegroundColor White
        Write-Host '  { "mcpServers": { "opencode-container-server": {' -ForegroundColor Gray
        Write-Host '    "command": "docker",' -ForegroundColor Gray
        Write-Host '    "args": ["exec", "-i", "opencode-server",' -ForegroundColor Gray
        Write-Host '             "python3", "/app/scripts/tools-mcp-server.py"]' -ForegroundColor Gray
        Write-Host '  } } }' -ForegroundColor Gray
    } catch {
        Write-Host "  Container built but not responding." -ForegroundColor Yellow
        Write-Host "  Run: docker logs opencode-server" -ForegroundColor Yellow
    }
}

# ─── Done — window will NOT close until Enter is pressed ──────────
Write-Host ""
if ($exitCode -ne 0) {
    Write-Host "  Something went wrong. Check the red errors above." -ForegroundColor Red
}
Write-Host "Press Enter to close this window."
Read-Host
