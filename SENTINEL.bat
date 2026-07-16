@echo off
title SENTINEL - USD/CLP Trading Intelligence
cd /d "%~dp0"

:: Prefer portable Python if it exists (already set up by a previous run)
if exist "_python\python.exe" (
    "_python\python.exe" -m sentinel.launcher
    pause
    exit /b %ERRORLEVEL%
)

:: Fallback to system Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   =============================================
    echo   Python not found!
    echo.
    echo   Download Python 3.12 from:
    echo   https://www.python.org/downloads/release/python-3120/
    echo.
    echo   IMPORTANT: Check "Add Python to PATH"
    echo   =============================================
    echo.
    pause
    exit /b 1
)

python -m sentinel.launcher
pause
