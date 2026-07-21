@echo off
title CortexStratum
echo.
echo ==========================================
echo   CortexStratum — 1-Click Setup
echo ==========================================
echo.
echo   This launches the PowerShell installer which
echo   downloads Docker, builds the container,
echo   and prints your MCP config.
echo.
echo   Repository: https://github.com/ohmpatel3877/CortexStratum
echo.
echo ==========================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
