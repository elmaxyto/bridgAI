@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if /i not "%~1"=="--background" (
    if exist "%~dp0start_windows_hidden.vbs" (
        wscript.exe "%~dp0start_windows_hidden.vbs"
        if not errorlevel 1 exit /b 0
    )
)

set "LOG_DIR=%LOCALAPPDATA%\LocalAIBridge\LocalAIBridge\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
set "LOG_FILE=%LOG_DIR%\desktop.log"

call :bootstrap >> "%LOG_FILE%" 2>&1
set "BOOTSTRAP_EXIT=%ERRORLEVEL%"
if not "%BOOTSTRAP_EXIT%"=="0" (
    powershell.exe -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show(('BridgAI could not start. Check the log: ' + $env:LOG_FILE),'BridgAI')" >nul 2>nul
)
exit /b %BOOTSTRAP_EXIT%

:bootstrap
echo.
echo ==================================================
echo [%DATE% %TIME%] BridgAI - Windows startup
echo ==================================================

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo ERROR: Python 3 was not found.
    echo Install Python 3.11 or 3.12 and enable "Add Python to PATH".
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 exit /b 1
) else (
    echo [1/3] Virtual environment already exists.
)

echo [2/3] Installing or updating dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 exit /b 1

set "LAUNCH_MODE=hidden"
set "MODE_FILE=%TEMP%\bridgai_launch_mode_%RANDOM%_%RANDOM%.txt"
".venv\Scripts\python.exe" run.py --windows-launch-mode > "%MODE_FILE%"
if exist "%MODE_FILE%" (
    set /p "LAUNCH_MODE="<"%MODE_FILE%"
    del /q "%MODE_FILE%" >nul 2>nul
)

echo [3/3] Launching BridgAI in %LAUNCH_MODE% mode...
if /i "%LAUNCH_MODE%"=="console" (
    start "BridgAI" /D "%CD%" ".venv\Scripts\python.exe" run.py
) else (
    set "BRIDGAI_DESKTOP_LOG=%LOG_FILE%"
    call :run_hidden
    if errorlevel 1 exit /b 1
)
exit /b 0

:run_hidden
".venv\Scripts\pythonw.exe" run.py
exit /b %ERRORLEVEL%
