@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BridgAI - Web Server

echo ========================================
echo   BridgAI - Direct Web Server Startup
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    pause
    exit /b 1
)

:: Set source directory path
set PYTHONPATH=src

:: Launch web server directly
".venv\Scripts\python.exe" -m local_ai_bridge.web --port 8765

pause