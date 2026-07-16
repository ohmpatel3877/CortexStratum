@echo off
title opencode-container-server — 1-Click Setup
cd /d "%~dp0"

echo ============================================
echo   opencode-container-server
echo   MCP Server + OpenCode CLI + mem0
echo ============================================
echo.
echo  This installs Docker + the MCP container.
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
echo.
echo Step 1 of 3 — Checking for Docker...
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   Docker not found. Installing Docker Desktop...
    echo   (This downloads ~500MB and runs the installer silently.)
    powershell -Command "& {Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile '%TEMP%\DockerDesktopInstaller.exe'}"
    echo   Running installer...
    start /wait "" "%TEMP%\DockerDesktopInstaller.exe" install --quiet
    echo   Starting Docker...
    "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
    echo   Waiting 30 seconds for Docker to initialize...
    timeout /t 30 /nobreak >nul
) else (
    echo   Docker already installed!
)

REM ─── Step 2: Download and Deploy Container ─────────────────────
echo.
echo Step 2 of 3 — Downloading and deploying container...
if not exist "%USERPROFILE%\opencode-container\docker-compose.yml" (
    mkdir "%USERPROFILE%\opencode-container" 2>nul
    cd /d "%USERPROFILE%\opencode-container"
    powershell -Command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/opencode-compose.yml' -OutFile 'docker-compose.yml'}"
    powershell -Command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/Dockerfile' -OutFile 'Dockerfile'}"
) else (
    cd /d "%USERPROFILE%\opencode-container"
)
docker compose up -d --build
if %errorlevel% neq 0 (
    echo.
    echo ! Build failed. Common fixes:
    echo   1. Make sure Docker Desktop is running
    echo   2. Restart Docker and try again
    echo   3. Run: docker compose logs
    pause
    exit /b 1
)

REM ─── Step 3: Test ──────────────────────────────────────────────
echo.
echo Step 3 of 3 — Testing connection...
timeout /t 3 /nobreak >nul
docker exec opencode-server python3 -c "import json; t=json.load(open('/app/data/tool-inventory.json')); print(f'Server OK - {len(t)} tools ready')" 2>nul
if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   SUCCESS — Server is running!
    echo ============================================
    echo.
    echo   Add this to your OpenCode config:
    echo   {
    echo     "mcpServers": {
    echo       "opencode-container-server": {
    echo         "command": "docker",
    echo         "args": ["exec", "-i", "opencode-server",
    echo                  "python3", "/app/scripts/tools-mcp-server.py"]
    echo       }
    echo     }
    echo   }
) else (
    echo.
    echo   Container deployed but not responding yet.
    echo   Run: docker logs opencode-server
)
echo.
echo   Press any key to exit.
pause >nul
