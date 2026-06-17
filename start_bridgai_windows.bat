@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BridgAI

echo ========================================
echo        BridgAI - Avvio
echo ========================================
echo.

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo ERRORE: Python 3 non e' stato trovato.
    echo Installa Python 3.11 o 3.12 e abilita "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creazione ambiente virtuale...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :venv_error
) else (
    echo [1/3] Ambiente virtuale gia' presente.
)

echo [2/3] Installazione o aggiornamento dipendenze...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :pip_error

echo [3/3] Avvio del programma...
".venv\Scripts\python.exe" run.py
set "APP_EXIT=%ERRORLEVEL%"

if not "%APP_EXIT%"=="0" (
    echo.
    echo Il programma si e' chiuso con codice %APP_EXIT%.
    pause
)
exit /b %APP_EXIT%

:venv_error
echo.
echo ERRORE: impossibile creare l'ambiente virtuale.
echo Verifica che l'installazione di Python includa il modulo venv.
pause
exit /b 1

:pip_error
echo.
echo ERRORE: installazione delle dipendenze non riuscita.
echo Controlla la connessione Internet e riprova.
pause
exit /b 1
