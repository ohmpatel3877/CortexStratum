@echo off
title patelserver — 1-Click Setup
cd /d "%~dp0"

echo ============================================
echo   patelserver — 1-Click Setup
echo   Portainer + AI Memory + Media Stack
echo ============================================
echo.
echo This will set up your entire home server.
echo Close this window to cancel.
echo.

REM ─── Check Admin ───────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell Start-Process cmd -ArgumentList "/c `"%~f0`"" -Verb RunAs
    exit /b
)

cd /d "%~dp0"

REM ─── Step 1: Check Docker ─────────────────────────────────────
echo [1/4] Checking for Docker...
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   Docker not found. Downloading Docker Desktop...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile '%TEMP%\DockerDesktopInstaller.exe'}"
    echo   Installing Docker Desktop (this may take a few minutes)...
    start /wait "" "%TEMP%\DockerDesktopInstaller.exe" install --quiet
    echo   Docker installed. Starting Docker...
    net start com.docker.service 2>nul
    "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
    echo   Waiting for Docker to start...
    timeout /t 30 /nobreak >nul
) else (
    echo   Docker found!
)

REM ─── Step 2: Clone / Pull Repo ────────────────────────────────
echo [2/4] Getting ai-memory-core...
if not exist "scripts\tools-mcp-server.py" (
    if exist "C:\ProgramData\patelserver" rmdir /s /q "C:\ProgramData\patelserver"
    mkdir "C:\ProgramData\patelserver" 2>nul
    cd /d "C:\ProgramData\patelserver"
    powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/ohmpatel3877/ai-memory-core/archive/refs/heads/main.zip' -OutFile '%TEMP%\ai-memory-core.zip'}"
    powershell -Command "& {Expand-Archive -Path '%TEMP%\ai-memory-core.zip' -DestinationPath 'C:\ProgramData\patelserver' -Force}"
    xcopy /e /i /y "C:\ProgramData\patelserver\ai-memory-core-main\*" "C:\ProgramData\patelserver\" >nul
    rmdir /s /q "C:\ProgramData\patelserver\ai-memory-core-main" 2>nul
) else (
    echo   Already have ai-memory-core!
)
cd /d "C:\ProgramData\patelserver"

REM ─── Step 3: Deploy Stack ─────────────────────────────────────
echo [3/4] Deploying containers...
docker compose -f docker\docker-compose.yml pull 2>nul
docker compose -f docker\docker-compose.yml up -d --build

echo [4/4] Finalizing...
timeout /t 5 /nobreak >nul

REM ─── Done ─────────────────────────────────────────────────────
cls
echo ============================================
echo   patelserver is LIVE!
echo ============================================
echo.
echo   Open Portainer:
echo   http://localhost:9000
echo.
echo   First time? Set your admin password in Portainer.
echo   Then explore your containers.
echo.
echo   Press any key to open Portainer now...
pause >nul
start http://localhost:9000
echo.
echo ============================================
echo   To manage:      http://localhost:9000
echo   To stop:        docker compose -f "C:\ProgramData\patelserver\docker\docker-compose.yml" down
echo   To update:      run this file again
echo ============================================
pause
