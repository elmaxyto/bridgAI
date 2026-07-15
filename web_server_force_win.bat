@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BridgAI - Web Server

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: ambiente virtuale non trovato.
    exit /b 1
)

set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
"%~dp0.venv\Scripts\python.exe" "%~dp0run.py" --web-server --port 8765
exit /b %ERRORLEVEL%
