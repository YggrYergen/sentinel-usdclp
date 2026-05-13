@echo off
chcp 65001 >nul 2>&1
title SENTINEL — USD/CLP Trading Intelligence
color 0A

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   🛡️  SENTINEL — Scalper Pro v3.4       ║
echo   ║   USD/CLP Trading Intelligence          ║
echo   ╚══════════════════════════════════════════╝
echo.

:: ═══════════════════════════════════════════
:: CONFIGURACIÓN
:: ═══════════════════════════════════════════
set "BRANCH=release"
set "PORT=8501"
set "URL=http://localhost:%PORT%"
set "SCRIPT_DIR=%~dp0"

cd /d "%SCRIPT_DIR%"

:: ═══════════════════════════════════════════
:: 1. ¿Ya está corriendo?
:: ═══════════════════════════════════════════
echo   [1/5] Verificando si SENTINEL ya está activo...
powershell -Command "try { $r = Invoke-WebRequest -Uri '%URL%' -TimeoutSec 2 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo.
    echo   ✅ SENTINEL ya está corriendo!
    echo   📂 Abriendo en el navegador...
    start "" "%URL%"
    echo.
    echo   Listo. Puedes cerrar esta ventana.
    timeout /t 5 >nul
    exit /b 0
)

:: ═══════════════════════════════════════════
:: 2. Verificar Python
:: ═══════════════════════════════════════════
echo   [2/5] Verificando Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   ❌ ERROR: Python no encontrado.
    echo.
    echo   Instala Python 3.11+ desde:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANTE: Marca "Add Python to PATH" al instalar.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   ✅ Python %%v encontrado

:: ═══════════════════════════════════════════
:: 3. Verificar Git y Auto-update
:: ═══════════════════════════════════════════
echo   [3/5] Buscando actualizaciones...
git --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   ⚠️  Git no encontrado — saltando actualizaciones
    goto :DEPS
)

:: Fetch remote sin modificar nada
git fetch origin %BRANCH% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   ⚠️  No se pudo conectar al servidor — usando versión actual
    goto :DEPS
)

:: Comparar versiones
for /f %%h in ('git rev-parse HEAD 2^>nul') do set "LOCAL=%%h"
for /f %%h in ('git rev-parse origin/%BRANCH% 2^>nul') do set "REMOTE=%%h"

if "%LOCAL%"=="%REMOTE%" (
    echo   ✅ Ya tienes la última versión
) else (
    echo.
    echo   📦 Nueva versión disponible — actualizando...
    git stash >nul 2>&1
    git checkout %BRANCH% >nul 2>&1
    git pull origin %BRANCH%
    if %ERRORLEVEL% NEQ 0 (
        echo   ⚠️  Error al actualizar — usando versión actual
        git stash pop >nul 2>&1
    ) else (
        echo   ✅ Actualizado correctamente
        git stash pop >nul 2>&1
    )
)

:: ═══════════════════════════════════════════
:: 4. Verificar dependencias
:: ═══════════════════════════════════════════
:DEPS
echo   [4/5] Verificando dependencias...
python -c "import streamlit; import MetaTrader5" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   📦 Instalando dependencias (primera vez, puede tardar)...
    pip install -r sentinel\requirements.txt --quiet
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo   ❌ ERROR al instalar dependencias.
        echo   Ejecuta manualmente:
        echo   pip install -r sentinel\requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo   ✅ Dependencias instaladas
) else (
    echo   ✅ Dependencias OK
)

:: ═══════════════════════════════════════════
:: 5. Iniciar SENTINEL
:: ═══════════════════════════════════════════
echo   [5/5] Iniciando SENTINEL...
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   🟢 SENTINEL iniciando en %URL%    ║
echo   ║   El navegador se abrirá en 5 segundos  ║
echo   ║                                          ║
echo   ║   Para detener: cierra esta ventana      ║
echo   ╚══════════════════════════════════════════╝
echo.

:: Abrir navegador después de 5 segundos (en paralelo)
start /b cmd /c "timeout /t 5 /nobreak >nul & start "" %URL%"

:: Iniciar Streamlit (bloquea esta ventana)
streamlit run sentinel\dashboard.py --server.headless true --server.port %PORT% --browser.gatherUsageStats false --server.address 0.0.0.0
