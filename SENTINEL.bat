@echo off
setlocal EnableDelayedExpansion
title SENTINEL - USD/CLP Trading Intelligence
color 0A

set "BRANCH=release"
set "PORT=8501"
set "URL=http://localhost:%PORT%"
set "SCRIPT_DIR=%~dp0"
set "LOGFILE=%SCRIPT_DIR%sentinel_log.txt"

cd /d "%SCRIPT_DIR%"

echo ============================================ > "%LOGFILE%"
echo  SENTINEL launcher - %date% %time% >> "%LOGFILE%"
echo ============================================ >> "%LOGFILE%"

echo.
echo   ============================================
echo     SENTINEL v3.4 - Scalper Pro
echo     USD/CLP Trading Intelligence
echo   ============================================
echo.

:: ===========================================
:: STEP 1: Already running?
:: ===========================================
echo   [1/5] Checking if SENTINEL is active...
echo [1/5] Check running >> "%LOGFILE%"
powershell -Command "try { $r = Invoke-WebRequest -Uri '%URL%' -TimeoutSec 2 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] SENTINEL is already running
    echo [OK] Already running >> "%LOGFILE%"

    git --version >nul 2>&1
    if !ERRORLEVEL! NEQ 0 goto :ALREADY_NO_UPDATE
    git fetch origin %BRANCH% >nul 2>&1
    if !ERRORLEVEL! NEQ 0 goto :ALREADY_NO_UPDATE

    for /f %%h in ('git rev-parse HEAD 2^>nul') do set "LOCAL_CHK=%%h"
    for /f %%h in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE_CHK=%%h"

    if "!LOCAL_CHK!"=="!REMOTE_CHK!" goto :ALREADY_NO_UPDATE

    echo   [UPDATE] New version found - restarting...
    echo [UPDATE] Restart >> "%LOGFILE%"
    powershell -Command "Get-Process -Name 'streamlit' -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1
    powershell -Command "Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" >nul 2>&1
    timeout /t 3 /nobreak >nul
    goto :CHECK_PYTHON
)
goto :CHECK_PYTHON

:ALREADY_NO_UPDATE
echo   [OK] No updates - opening browser
start "" "%URL%"
echo.
echo   SENTINEL is running at %URL%
echo.
echo   Press any key to close this window...
pause >nul
exit /b 0

:: ===========================================
:: STEP 2: Python
:: ===========================================
:CHECK_PYTHON
echo   [2/5] Checking Python...
echo [2/5] Python >> "%LOGFILE%"
python --version >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [ERROR] Python not found!
    echo   Install Python 3.11+ from https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH"
    echo [ERROR] Python not found >> "%LOGFILE%"
    goto :FATAL
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   [OK] %%v

:: ===========================================
:: STEP 3: Git + Auto-update
:: ===========================================
echo   [3/5] Checking for updates...
echo [3/5] Git >> "%LOGFILE%"
git --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [SKIP] Git not installed - skipping auto-update
    echo [SKIP] Git not found >> "%LOGFILE%"
    goto :DEPS
)

git fetch origin %BRANCH% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [SKIP] Cannot reach GitHub - using current version
    echo [SKIP] Fetch failed >> "%LOGFILE%"
    goto :DEPS
)

for /f %%h in ('git rev-parse HEAD 2^>nul') do set "LOCAL=%%h"
for /f %%h in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE=%%h"

if "%LOCAL%"=="%REMOTE%" (
    echo   [OK] Already on latest version
    echo [OK] Up to date >> "%LOGFILE%"
) else (
    echo   [UPDATE] Downloading new version...
    echo [UPDATE] Pulling >> "%LOGFILE%"
    git stash >nul 2>&1
    git checkout %BRANCH% >nul 2>&1
    git pull origin %BRANCH% >> "%LOGFILE%" 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo   [WARN] Update failed - using current version
        git stash pop >nul 2>&1
    ) else (
        echo   [OK] Updated
        git stash pop >nul 2>&1
    )
)

:: ===========================================
:: STEP 4: Dependencies
:: ===========================================
:DEPS
echo   [4/5] Checking dependencies...
echo [4/5] Deps >> "%LOGFILE%"
python -c "import streamlit" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   Installing dependencies (first time, may take minutes)...
    echo [INFO] pip install >> "%LOGFILE%"
    pip install -r sentinel\requirements.txt >> "%LOGFILE%" 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo   [ERROR] Failed to install dependencies
        echo   Check log: %LOGFILE%
        echo [ERROR] pip failed >> "%LOGFILE%"
        goto :FATAL
    )
    echo   [OK] Dependencies installed
) else (
    echo   [OK] Dependencies OK
    echo [OK] Deps OK >> "%LOGFILE%"
)

:: ===========================================
:: STEP 5: Launch
:: ===========================================
echo   [5/5] Starting SENTINEL...
echo [5/5] Launch >> "%LOGFILE%"
echo.
echo   ============================================
echo     Starting at %URL%
echo     Browser will open in 8 seconds
echo     DO NOT close this window
echo   ============================================
echo.

:: Open browser after delay
start "" cmd /c "timeout /t 8 /nobreak >nul && start %URL%"

:: Run Streamlit directly (output shows here, errors go to log too)
echo --- Streamlit start %date% %time% --- >> "%LOGFILE%"
streamlit run sentinel\dashboard.py --server.headless true --server.port %PORT% --browser.gatherUsageStats false --server.address 0.0.0.0 2>> "%LOGFILE%"

:: Streamlit exited
echo.
echo   ============================================
echo   SENTINEL stopped (exit code: %ERRORLEVEL%)
echo   Log saved to: %LOGFILE%
echo   ============================================

:FATAL
echo.
echo   Press any key to close...
pause >nul
exit /b 1
