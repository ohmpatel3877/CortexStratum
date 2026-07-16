@echo off
title opencode-container-server
cd /d "%~dp0"

echo ============================================
echo   opencode-container-server — 1-Click Setup
echo ============================================
echo.
echo  This window stays open. Close it when you're done.
echo.

REM ─── Elevate to Admin ───────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting admin privileges...
    powershell Start-Process cmd -ArgumentList "/c `"%~f0`" & pause" -Verb RunAs
    exit /b
)

cd /d "%~dp0"

REM ─── Step 1: Docker ─────────────────────────────────────────────
echo.
echo [1/3] Checking for Docker...

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   Docker not found. Downloading installer...
    echo   (This is ~500MB and may take a few minutes...)
    powershell -Command "& {Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile '%TEMP%\DockerDesktopInstaller.exe'}"
    if %errorlevel% neq 0 (
        echo   FAILED to download Docker.
        echo   Check your internet connection and try again.
        goto :done
    )
    echo   Running Docker Desktop installer...
    start /wait "" "%TEMP%\DockerDesktopInstaller.exe" install --quiet
    echo   Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo   Waiting 30 seconds for Docker to initialize...
    timeout /t 30 /nobreak
) else (
    echo   Docker found: 
    docker --version
)

REM ─── Step 2: Create working directory ──────────────────────────
echo.
echo [2/3] Setting up container files...

if not exist "%USERPROFILE%\opencode-container" mkdir "%USERPROFILE%\opencode-container"
cd /d "%USERPROFILE%\opencode-container"
echo   Working directory: %USERPROFILE%\opencode-container

echo   Downloading compose file...
powershell -Command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/opencode-compose.yml' -OutFile 'docker-compose.yml'}"
if %errorlevel% neq 0 (
    echo   FAILED to download compose file.
    goto :done
)

echo   Downloading Dockerfile...
powershell -Command "& {Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/Dockerfile' -OutFile 'Dockerfile'}"
if %errorlevel% neq 0 (
    echo   FAILED to download Dockerfile.
    goto :done
)

REM ─── Step 3: Build container ───────────────────────────────────
echo.
echo [3/3] Building and starting container...
echo   First build downloads packages — this takes 1-3 minutes.
echo.
docker compose up -d --build
if %errorlevel% neq 0 (
    echo.
    echo   BUILD FAILED. Possible fixes:
    echo   - Make sure Docker Desktop is running (look for the whale icon)
    echo   - Restart your computer and try again
    echo   - Run this manually: docker compose logs
    goto :done
)

REM ─── Verify ─────────────────────────────────────────────────────
echo.
echo   Testing container...
timeout /t 3 /nobreak >nul
docker exec opencode-server python3 -c "import json; t=json.load(open('/app/data/tool-inventory.json')); print(f'OK - {len(t)} tools ready')" 2>nul
if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   SUCCESS! Server is running.
    echo ============================================
    echo.
    echo   Add this to your OpenCode config:
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
    echo   To check status later: docker ps
    echo   To view logs:         docker logs opencode-server
) else (
    echo   Container built but not responding yet.
    echo   Check logs: docker logs opencode-server
)

:done
echo.
echo  Press any key to close this window.
pause >nul
