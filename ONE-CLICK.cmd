@echo off
title opencode-container-server
cd /d "%~dp0"

echo ============================================
echo   opencode-container-server
echo   MCP Server + OpenCode CLI + mem0
echo ============================================
echo.
echo  Installing Docker + MCP server container.
echo  This window will stay open. Do NOT close it.
echo.

REM ─── Elevate to Admin ───────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting admin privileges...
    powershell Start-Process cmd -ArgumentList "/c `"%~f0`"" -Verb RunAs
    exit /b
)

cd /d "%~dp0"

REM ─── Step 1: Docker ─────────────────────────────────────────────
echo.
echo [1/3] Checking for Docker...
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   Docker not found. Installing Docker Desktop...
    echo   Downloading installer...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile '%TEMP%\DockerDesktopInstaller.exe'}"
    if %errorlevel% neq 0 (
        echo   FAILED to download Docker. Check your internet connection.
        pause
        exit /b 1
    )
    echo   Running installer (this takes a few minutes)...
    start /wait "" "%TEMP%\DockerDesktopInstaller.exe" install --quiet
    echo   Starting Docker...
    "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
    echo   Waiting 30 seconds for Docker to start...
    timeout /t 30 /nobreak >nul
) else (
    echo   Docker already installed!
)

REM ─── Step 2: Download files ─────────────────────────────────────
echo.
echo [2/3] Downloading container files...
mkdir "%USERPROFILE%\opencode-container" 2>nul
cd /d "%USERPROFILE%\opencode-container"

echo   Downloading docker-compose.yml...
powershell -Command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/opencode-compose.yml' -OutFile 'docker-compose.yml'}"
if %errorlevel% neq 0 (
    echo   FAILED to download. Check your internet.
    pause
    exit /b 1
)

echo   Downloading Dockerfile...
powershell -Command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/Dockerfile' -OutFile 'Dockerfile'}"
if %errorlevel% neq 0 (
    echo   FAILED to download Dockerfile.
    pause
    exit /b 1
)

REM ─── Step 3: Build and Run ─────────────────────────────────────
echo.
echo [3/3] Building and starting container...
echo   First build takes 1-3 minutes...
docker compose up -d --build
if %errorlevel% neq 0 (
    echo.
    echo   BUILD FAILED. Common fixes:
    echo   - Open Docker Desktop and wait for it to say "Running"
    echo   - Restart your computer
    echo   - Then run ONE-CLICK.cmd again
    pause
    exit /b 1
)

REM ─── Test ──────────────────────────────────────────────────────
echo.
echo   Testing connection...
timeout /t 3 /nobreak >nul
docker exec opencode-server python3 -c "import json; t=json.load(open('/app/data/tool-inventory.json')); print(f'OK - {len(t)} tools ready')" 2>nul
if %errorlevel% equ 0 (
    cls
    echo ============================================
    echo   SUCCESS!
    echo ============================================
    echo.
    echo   The container is running at port 3100.
    echo.
    echo   To use it with OpenCode, add this to your
    echo   opencode.json config file:
    echo.
    echo   {
    echo     "mcpServers": {
    echo       "opencode-container-server": {
    echo         "command": "docker",
    echo         "args": ["exec", "-i", "opencode-server",
    echo                  "python3", "/app/scripts/tools-mcp-server.py"]
    echo       }
    echo     }
    echo   }
    echo.
    echo   Press any key to exit.
    pause >nul
) else (
    echo.
    echo   Container built but not responding yet.
    echo   Run this to check logs:
    echo   docker logs opencode-server
    echo.
    echo   Press any key to exit.
    pause >nul
)
