@echo off
setlocal EnableDelayedExpansion
title SENTINEL - USD/CLP Trading Intelligence
color 0A

echo.
echo   ============================================
echo     SENTINEL v3.4 - Scalper Pro
echo     USD/CLP Trading Intelligence
echo   ============================================
echo.

:: ===========================================
:: CONFIG
:: ===========================================
set "BRANCH=release"
set "PORT=8501"
set "URL=http://localhost:%PORT%"
set "SCRIPT_DIR=%~dp0"

cd /d "%SCRIPT_DIR%"

:: ===========================================
:: STEP 1: Already running?
:: ===========================================
echo   [1/5] Checking if SENTINEL is active...
powershell -Command "try { $r = Invoke-WebRequest -Uri '%URL%' -TimeoutSec 2 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] SENTINEL is running - checking for updates...

    git --version >nul 2>&1
    if !ERRORLEVEL! NEQ 0 goto :ALREADY_NO_UPDATE
    git fetch origin %BRANCH% >nul 2>&1
    if !ERRORLEVEL! NEQ 0 goto :ALREADY_NO_UPDATE

    for /f %%h in ('git rev-parse HEAD 2^>nul') do set "LOCAL_CHK=%%h"
    for /f %%h in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE_CHK=%%h"

    if "!LOCAL_CHK!"=="!REMOTE_CHK!" goto :ALREADY_NO_UPDATE

    echo.
    echo   [UPDATE] New version found - restarting SENTINEL...
    echo   Stopping old version...

    powershell -Command "Get-Process -Name 'streamlit' -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1
    powershell -Command "Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" >nul 2>&1
    timeout /t 3 /nobreak >nul

    echo   [OK] Stopped. Updating and relaunching...
    echo.
    goto :CHECK_PYTHON
)
goto :CHECK_PYTHON

:ALREADY_NO_UPDATE
echo   [OK] No pending updates
echo   Opening browser...
start "" "%URL%"
echo.
echo   Done. You can close this window.
timeout /t 5 >nul
exit /b 0

:: ===========================================
:: STEP 2: Python
:: ===========================================
:CHECK_PYTHON
echo   [2/5] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   [ERROR] Python not found.
    echo.
    echo   Install Python 3.11+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: Check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   [OK] %%v

:: ===========================================
:: STEP 3: Git + Auto-update
:: ===========================================
echo   [3/5] Checking for updates...
git --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Git not found - skipping updates
    goto :DEPS
)

git fetch origin %BRANCH% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Cannot reach server - using current version
    goto :DEPS
)

for /f %%h in ('git rev-parse HEAD 2^>nul') do set "LOCAL=%%h"
for /f %%h in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE=%%h"

if "%LOCAL%"=="%REMOTE%" (
    echo   [OK] Already on latest version
) else (
    echo.
    echo   [UPDATE] New version available - downloading...
    git stash >nul 2>&1
    git checkout %BRANCH% >nul 2>&1
    git pull origin %BRANCH%
    if !ERRORLEVEL! NEQ 0 (
        echo   [WARN] Update failed - using current version
        git stash pop >nul 2>&1
    ) else (
        echo   [OK] Updated successfully
        git stash pop >nul 2>&1
    )
)

:: ===========================================
:: STEP 4: Dependencies
:: ===========================================
:DEPS
echo   [4/5] Checking dependencies...
python -c "import streamlit; import MetaTrader5" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   Installing dependencies (first time, may take a few minutes)...
    pip install -r sentinel\requirements.txt --quiet
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo   [ERROR] Failed to install dependencies.
        echo   Run manually: pip install -r sentinel\requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo   [OK] Dependencies installed
) else (
    echo   [OK] Dependencies OK
)

:: ===========================================
:: STEP 5: Launch
:: ===========================================
echo   [5/5] Starting SENTINEL...
echo.
echo   ============================================
echo     SENTINEL starting at %URL%
echo     Browser will open in 5 seconds
echo.
echo     To stop: close this window
echo   ============================================
echo.

:: Open browser after 5 seconds (parallel)
start /b cmd /c "timeout /t 5 /nobreak >nul & start "" %URL%"

:: Start Streamlit (blocks this window)
streamlit run sentinel\dashboard.py --server.headless true --server.port %PORT% --browser.gatherUsageStats false --server.address 0.0.0.0

:: If we get here, streamlit exited
echo.
echo   SENTINEL has stopped.
pause
