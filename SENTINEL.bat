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
echo   Log: %LOGFILE%
echo.

:: ===========================================
:: STEP 1: Already running?
:: ===========================================
echo   [1/5] Checking if SENTINEL is active...
echo [1/5] Checking if already running... >> "%LOGFILE%"
powershell -Command "try { $r = Invoke-WebRequest -Uri '%URL%' -TimeoutSec 2 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] SENTINEL is running - checking for updates...
    echo [OK] Already running >> "%LOGFILE%"

    git --version >nul 2>&1
    if !ERRORLEVEL! NEQ 0 goto :ALREADY_NO_UPDATE
    git fetch origin %BRANCH% >nul 2>&1
    if !ERRORLEVEL! NEQ 0 goto :ALREADY_NO_UPDATE

    for /f %%h in ('git rev-parse HEAD 2^>nul') do set "LOCAL_CHK=%%h"
    for /f %%h in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE_CHK=%%h"

    if "!LOCAL_CHK!"=="!REMOTE_CHK!" goto :ALREADY_NO_UPDATE

    echo.
    echo   [UPDATE] New version found - restarting SENTINEL...
    echo [UPDATE] Restarting with new version >> "%LOGFILE%"

    powershell -Command "Get-Process -Name 'streamlit' -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1
    powershell -Command "Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" >nul 2>&1
    timeout /t 3 /nobreak >nul

    echo   [OK] Old version stopped. Updating...
    goto :CHECK_PYTHON
)
goto :CHECK_PYTHON

:ALREADY_NO_UPDATE
echo   [OK] No pending updates - opening browser
echo [OK] No updates, opening browser >> "%LOGFILE%"
start "" "%URL%"
echo.
echo   SENTINEL is already running at %URL%
echo   Browser opened. You can close this window.
echo.
echo   ============================================
echo   Press any key to close...
echo   ============================================
pause >nul
exit /b 0

:: ===========================================
:: STEP 2: Python
:: ===========================================
:CHECK_PYTHON
echo   [2/5] Checking Python...
echo [2/5] Checking Python... >> "%LOGFILE%"
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   [ERROR] Python not found.
    echo   Install Python 3.11+ from https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install.
    echo [ERROR] Python not found >> "%LOGFILE%"
    echo.
    goto :FATAL
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do (
    echo   [OK] %%v
    echo [OK] %%v >> "%LOGFILE%"
)

:: ===========================================
:: STEP 3: Git + Auto-update
:: ===========================================
echo   [3/5] Checking for updates...
echo [3/5] Checking updates... >> "%LOGFILE%"
git --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Git not found - skipping updates
    echo [WARN] Git not found >> "%LOGFILE%"
    goto :DEPS
)

git fetch origin %BRANCH% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Cannot reach server - using current version
    echo [WARN] Cannot reach GitHub >> "%LOGFILE%"
    goto :DEPS
)

for /f %%h in ('git rev-parse HEAD 2^>nul') do set "LOCAL=%%h"
for /f %%h in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE=%%h"

echo   Local:  %LOCAL% >> "%LOGFILE%"
echo   Remote: %REMOTE% >> "%LOGFILE%"

if "%LOCAL%"=="%REMOTE%" (
    echo   [OK] Already on latest version
    echo [OK] Up to date >> "%LOGFILE%"
) else (
    echo   [UPDATE] Downloading new version...
    echo [UPDATE] Pulling from %BRANCH%... >> "%LOGFILE%"
    git stash >nul 2>&1
    git checkout %BRANCH% >nul 2>&1
    git pull origin %BRANCH% >> "%LOGFILE%" 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo   [WARN] Update failed - using current version
        echo [WARN] Pull failed >> "%LOGFILE%"
        git stash pop >nul 2>&1
    ) else (
        echo   [OK] Updated successfully
        echo [OK] Pull success >> "%LOGFILE%"
        git stash pop >nul 2>&1
    )
)

:: ===========================================
:: STEP 4: Dependencies
:: ===========================================
:DEPS
echo   [4/5] Checking dependencies...
echo [4/5] Checking deps... >> "%LOGFILE%"
python -c "import streamlit; import MetaTrader5" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   Installing dependencies (first time, may take a few minutes)...
    echo [INFO] Installing deps... >> "%LOGFILE%"
    pip install -r sentinel\requirements.txt >> "%LOGFILE%" 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo   [ERROR] Failed to install dependencies.
        echo   Check %LOGFILE% for details.
        echo [ERROR] pip install failed >> "%LOGFILE%"
        goto :FATAL
    )
    echo   [OK] Dependencies installed
    echo [OK] Deps installed >> "%LOGFILE%"
) else (
    echo   [OK] Dependencies OK
    echo [OK] Deps OK >> "%LOGFILE%"
)

:: ===========================================
:: STEP 5: Launch
:: ===========================================
echo   [5/5] Starting SENTINEL...
echo [5/5] Starting Streamlit... >> "%LOGFILE%"
echo.
echo   ============================================
echo     SENTINEL starting at %URL%
echo     Browser will open in 8 seconds
echo.
echo     DO NOT close this window while using SENTINEL
echo   ============================================
echo.

:: Open browser after 8 seconds (parallel)
start /b cmd /c "timeout /t 8 /nobreak >nul & start "" %URL%"

:: Start Streamlit - capture ALL output including tracebacks
echo. >> "%LOGFILE%"
echo === Streamlit output === >> "%LOGFILE%"
streamlit run sentinel\dashboard.py --server.headless true --server.port %PORT% --browser.gatherUsageStats false --server.address 0.0.0.0 2>&1 | powershell -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"

:: If we get here, streamlit exited (crash or manual close)
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo   ============================================
echo     SENTINEL has stopped (exit code: %EXIT_CODE%)
echo.
echo     Full log saved to:
echo     %LOGFILE%
echo.
if %EXIT_CODE% NEQ 0 (
    echo     [ERROR] SENTINEL crashed. Check the log above
    echo     and in the log file for the full traceback.
    echo.
)
echo   ============================================
echo.
goto :FATAL

:: ===========================================
:: FATAL: Always pause before exit
:: ===========================================
:FATAL
echo.
echo   Press any key to close this window...
pause >nul
exit /b 1
