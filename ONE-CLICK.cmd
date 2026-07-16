@echo off
title patelserver — 1-Click Setup
cd /d "%~dp0"

echo ============================================
echo   patelserver — 1-Click Setup
echo   Portainer + AI Memory + Media Stack
echo ============================================
echo.
echo  You only need Docker. This script installs it if missing.
echo  Close this window to cancel.
echo.

REM ─── Elevate to Admin ───────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell Start-Process cmd -ArgumentList "/c `"%~f0`"" -Verb RunAs
    exit /b
)

cd /d "%~dp0"

REM ─── Step 1: Install Docker (if missing) ───────────────────────
echo [1/4] Checking for Docker...
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   Docker not found. Running installer...
    if exist "docker\install-docker.ps1" (
        powershell -ExecutionPolicy Bypass -File "docker\install-docker.ps1"
    ) else (
        powershell -Command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/install-docker.ps1' -OutFile '%TEMP%\install-docker.ps1'}"
        powershell -ExecutionPolicy Bypass -File "%TEMP%\install-docker.ps1"
    )
    echo   Waiting for Docker to initialize...
    timeout /t 10 /nobreak >nul
) else (
    echo   Docker found!
)

REM ─── Step 2: Clone / Pull Repo ─────────────────────────────────
echo [2/4] Getting ai-memory-core...
if not exist "scripts\tools-mcp-server.py" (
    if exist "C:\ProgramData\patelserver" rmdir /s /q "C:\ProgramData\patelserver"
    mkdir "C:\ProgramData\patelserver" 2>nul
    cd /d "C:\ProgramData\patelserver"
    echo   Downloading...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/ohmpatel3877/ai-memory-core/archive/refs/heads/main.zip' -OutFile '%TEMP%\ai-memory-core.zip'}"
    powershell -Command "& {Expand-Archive -Path '%TEMP%\ai-memory-core.zip' -DestinationPath 'C:\ProgramData\patelserver' -Force}"
    xcopy /e /i /y "C:\ProgramData\patelserver\ai-memory-core-main\*" "C:\ProgramData\patelserver\" >nul
    rmdir /s /q "C:\ProgramData\patelserver\ai-memory-core-main" 2>nul
) else (
    echo   Already have ai-memory-core!
)
cd /d "C:\ProgramData\patelserver"

REM ─── Step 3: Configure API Keys ────────────────────────────────
echo [3/4] Configuring...
if not exist ".env" (
    echo   No .env found. Creating template...
    (
        echo MEM0_API_KEY=
        echo OPENCODE_ZEN_API_KEY=
        echo OPENCODE_ZEN_BASE_URL=https://api.opencode.ai
        echo OPENCODE_HOST=patelserver
        echo LOG_LEVEL=info
    ) > .env
    echo   Edit .env to add your API keys, or leave blank for later.
    notepad .env
)

REM ─── Step 4: Deploy Stack ──────────────────────────────────────
echo [4/4] Deploying containers...
docker compose -f docker\docker-compose.yml pull 2>nul
docker compose -f docker\docker-compose.yml up -d --build

timeout /t 5 /nobreak >nul

REM ─── Done ──────────────────────────────────────────────────────
cls
echo ============================================
echo   patelserver is LIVE!
echo ============================================
echo.
echo   Portainer: http://localhost:9000
echo   First login: set your admin password.
echo.
echo  Press any key to open Portainer now...
pause >nul
start http://localhost:9000
echo.
echo ============================================
echo   Manage:  http://localhost:9000
echo   Stop:    docker compose -f "C:\ProgramData\patelserver\docker\docker-compose.yml" down
echo   Update:  Run this file again
echo ============================================
pause
