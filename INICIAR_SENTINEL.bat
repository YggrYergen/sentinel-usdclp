@echo off
title 🛡️ SENTINEL v3.2 — USD/CLP Trading System
color 0B
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║           🛡️  SENTINEL v3.2 — USD/CLP              ║
echo  ║           Sistema de Análisis de Trading            ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Verificar que MT5 esté corriendo
tasklist /FI "IMAGENAME eq terminal64.exe" 2>NUL | find /I "terminal64.exe" >NUL
if errorlevel 1 (
    echo  ⚠️  MetaTrader 5 no está corriendo.
    echo     Abre MT5 y loguéate en tu cuenta antes de continuar.
    echo.
    echo  Intentando abrir MT5...
    if exist "C:\Program Files\MetaTrader 5\terminal64.exe" (
        start "" "C:\Program Files\MetaTrader 5\terminal64.exe"
        echo  Esperando 10 segundos para que MT5 inicie...
        timeout /t 10 /nobreak >nul
    ) else (
        echo  ❌ MT5 no encontrado. Instálalo primero.
        pause
        exit /b 1
    )
)

echo  ✅ MetaTrader 5 detectado
echo.
echo  🚀 Iniciando SENTINEL Dashboard...
echo  El dashboard se abrirá en tu navegador en unos segundos.
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  📌 NO cierres esta ventana mientras uses SENTINEL  ║
echo  ║  📌 Para detener: cierra esta ventana o Ctrl+C      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Iniciar Streamlit
cd /d "%~dp0"
streamlit run sentinel\dashboard.py --server.headless true --server.port 8501 --browser.gatherUsageStats false

:: Si streamlit falla
if errorlevel 1 (
    echo.
    echo  ❌ Error iniciando SENTINEL.
    echo     Ejecuta INSTALAR_SENTINEL.bat primero.
    pause
)
