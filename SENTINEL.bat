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

:: Start fresh log
echo ============================================ > "%LOGFILE%"
echo  SENTINEL launcher - %date% %time% >> "%LOGFILE%"
echo ============================================ >> "%LOGFILE%"

echo.
echo   ============================================
echo     SENTINEL v3.4 - Scalper Pro
echo   ============================================
echo.

:: ===========================================
:: STEP 1: Already running?
:: ===========================================
echo   [1/5] Checking if already active...
powershell -Command "try { Invoke-WebRequest -Uri '%URL%' -TimeoutSec 2 -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] Already running - opening browser
    start "" "%URL%"
    echo.
    echo   Press any key to close...
    pause >nul
    exit /b 0
)

:: ===========================================
:: STEP 2: Python
:: ===========================================
echo   [2/5] Checking Python...
python --version > "%SCRIPT_DIR%_pyver.tmp" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [ERROR] Python not found >> "%LOGFILE%"
    echo   [ERROR] Python not found!
    echo   Install from https://www.python.org/downloads/
    echo   Check "Add Python to PATH"
    goto :FATAL
)
set /p PYVER=<"%SCRIPT_DIR%_pyver.tmp"
echo   [OK] %PYVER%
echo [OK] %PYVER% >> "%LOGFILE%"
del "%SCRIPT_DIR%_pyver.tmp" >nul 2>&1

:: ===========================================
:: STEP 3: Git + Auto-update
:: ===========================================
echo   [3/5] Checking for updates...
git --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [SKIP] Git not installed
    echo [SKIP] No git >> "%LOGFILE%"
    goto :DEPS
)

git fetch origin %BRANCH% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [SKIP] Cannot reach GitHub
    goto :DEPS
)

for /f %%h in ('git rev-parse HEAD 2^>nul') do set "LOCAL=%%h"
for /f %%h in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE=%%h"

if "%LOCAL%"=="%REMOTE%" (
    echo   [OK] Latest version
) else (
    echo   [UPDATE] Downloading...
    git stash >nul 2>&1
    git checkout %BRANCH% >nul 2>&1
    git pull origin %BRANCH% >> "%LOGFILE%" 2>&1
    git stash pop >nul 2>&1
    echo   [OK] Updated
)

:: ===========================================
:: STEP 4: Dependencies
:: ===========================================
:DEPS
echo   [4/5] Checking dependencies...
python -c "import streamlit" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   Installing dependencies (may take minutes)...
    echo [INFO] pip install start >> "%LOGFILE%"
    pip install -r sentinel\requirements.txt >> "%LOGFILE%" 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo   [ERROR] pip install failed - see log below
        echo.
        echo   === LOG ===
        type "%LOGFILE%"
        goto :FATAL
    )
    echo   [OK] Installed
) else (
    echo   [OK] Dependencies OK
)

:: ===========================================
:: STEP 5: Launch
:: ===========================================
echo   [5/5] Starting SENTINEL...
echo.
echo   ============================================
echo     Dashboard: %URL%
echo     Browser opens in 8 seconds
echo     DO NOT close this window
echo   ============================================
echo.

:: Browser open in background
start "" cmd /c "timeout /t 8 /nobreak >nul && start %URL%"

:: Run Streamlit - ALL output to log (stdout + stderr)
echo. >> "%LOGFILE%"
echo === Streamlit start %date% %time% === >> "%LOGFILE%"

streamlit run sentinel\dashboard.py --server.headless true --server.port %PORT% --browser.gatherUsageStats false --server.address 0.0.0.0 >> "%LOGFILE%" 2>&1

:: ============================================
:: CRASHED - show everything
:: ============================================
echo.
echo   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo   SENTINEL stopped unexpectedly
echo   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo.
echo   === FULL LOG ===
echo.
type "%LOGFILE%"
echo.
echo   === END LOG ===
echo.
echo   Log saved to: %LOGFILE%

:FATAL
echo.
echo   ============================================
echo   Press any key to close this window...
echo   ============================================
pause >nul
exit /b 1
