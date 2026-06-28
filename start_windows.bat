@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BridgAI

echo ========================================
echo        BridgAI - Startup
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
    echo ERROR: Python 3 was not found.
    echo Please install Python 3.11 or 3.12 and enable "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :venv_error
) else (
    echo [1/3] Virtual environment already exists.
)

echo [2/3] Installing or updating dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :pip_error

echo [3/3] Launching program...
".venv\Scripts\python.exe" run.py
set "APP_EXIT=%ERRORLEVEL%"

if not "%APP_EXIT%"=="0" (
    echo.
    echo The program exited with code %APP_EXIT%.
    pause
)
exit /b %APP_EXIT%

:venv_error
echo.
echo ERROR: Failed to create the virtual environment.
echo Make sure your Python installation includes the venv module.
pause
exit /b 1

:pip_error
echo.
echo ERROR: Failed to install dependencies.
echo Check your internet connection and try again.
pause
exit /b 1
