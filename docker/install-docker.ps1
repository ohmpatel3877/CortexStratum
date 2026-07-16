<#
.SYNOPSIS
    Install Docker Desktop on Windows — if not already present.
.DESCRIPTION
    Detects Docker, downloads official installer if missing, installs silently.
    Safe to run on systems that already have Docker.
    Part of the patelserver stack.
.EXAMPLE
    .\install-docker.ps1
#>

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Docker Installer — opencode-container-server"

Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    Docker Installer — opencode-container-server ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── Admin check ───────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Requesting administrator privileges..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# ─── Check if Docker already works ─────────────────────────────────
try {
    $version = docker --version 2>&1
    docker info 2>&1 | Out-Null
    Write-Host "  ✓ Docker already installed: $version" -ForegroundColor Green
    exit 0
} catch {}

# ─── Check if Docker binary exists but daemon not running ──────────
try {
    $version = docker --version 2>&1
    Write-Host "  ⚠ Docker binary found but not running. Starting..." -ForegroundColor Yellow
    # Try starting Docker Desktop
    $dockerPath = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerPath) {
        Start-Process $dockerPath
        Write-Host "  Waiting for Docker to start..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
        try {
            docker info 2>&1 | Out-Null
            Write-Host "  ✓ Docker started!" -ForegroundColor Green
            exit 0
        } catch {
            Write-Host "  ✗ Could not start Docker. Reinstalling..." -ForegroundColor Red
        }
    }
} catch {}

# ─── Download Docker Desktop ───────────────────────────────────────
Write-Host "  Downloading Docker Desktop..." -ForegroundColor Yellow
$installer = "$env:TEMP\DockerDesktopInstaller.exe"
$url = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"

try {
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($url, $installer)
} catch {
    Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
}

# ─── Install ───────────────────────────────────────────────────────
Write-Host "  Installing Docker Desktop..." -ForegroundColor Yellow
Write-Host "  (This may take a few minutes. The installer will run silently.)" -ForegroundColor DarkYellow

$proc = Start-Process -FilePath $installer -ArgumentList "install --quiet" -Wait -PassThru

if ($proc.ExitCode -eq 0) {
    Write-Host "  ✓ Docker Desktop installed" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Installer exited with code $($proc.ExitCode). Trying to launch anyway..." -ForegroundColor Yellow
}

# ─── Start Docker ──────────────────────────────────────────────────
$dockerPath = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
if (Test-Path $dockerPath) {
    Write-Host "  Starting Docker Desktop..." -ForegroundColor Yellow
    Start-Process $dockerPath
}

Write-Host ""
Write-Host "  ⚡ Verifying installation..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

try {
    docker info 2>&1 | Out-Null
    Write-Host "  ✓ Docker is running: $(docker --version)" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Docker installed but not yet running." -ForegroundColor Yellow
    Write-Host "  Launch Docker Desktop manually from the Start Menu," -ForegroundColor Yellow
    Write-Host "  then run the patelserver setup again." -ForegroundColor Yellow
}
