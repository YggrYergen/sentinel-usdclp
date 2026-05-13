@echo off
title SENTINEL - USD/CLP Trading Intelligence
cd /d "%~dp0"

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

python sentinel\launcher.py
pause
