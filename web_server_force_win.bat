@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BridgAI - Web Server

echo ========================================
echo   BridgAI - Avvio Diretto Server Web
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERRORE: Ambiente virtuale non trovato!
    pause
    exit /b 1
)

:: Imposta il percorso sorgente
set PYTHONPATH=src

:: Lancia il server web direttamente
".venv\Scripts\python.exe" -m local_ai_bridge.web --port 8765

pause