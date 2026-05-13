@echo off
title SENTINEL v3.2 — Instalador
color 0A
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║           🛡️  SENTINEL v3.2 — USD/CLP              ║
echo  ║           Instalador para Windows                   ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ❌ Python no encontrado. Instálalo desde python.org
    echo     Descarga: https://www.python.org/downloads/
    echo     IMPORTANTE: Marca "Add Python to PATH" al instalar.
    pause
    exit /b 1
)

echo  ✅ Python encontrado
python --version

:: Verificar MetaTrader 5
echo.
echo  Verificando MetaTrader 5...
if exist "C:\Program Files\MetaTrader 5\terminal64.exe" (
    echo  ✅ MetaTrader 5 encontrado en Program Files
) else (
    echo  ⚠️  MetaTrader 5 no encontrado en la ubicación estándar.
    echo     Necesitas tener MT5 de MetaQuotes instalado.
    echo     Descarga: https://www.metatrader5.com/en/download
    echo.
    set /p CONTINUE="¿Continuar de todos modos? (S/N): "
    if /i not "%CONTINUE%"=="S" exit /b 1
)

:: Instalar dependencias
echo.
echo  📦 Instalando dependencias Python...
echo  Esto puede tomar unos minutos la primera vez...
echo.
pip install --upgrade pip >nul 2>&1
pip install -r "%~dp0sentinel\requirements.txt"

if errorlevel 1 (
    echo.
    echo  ❌ Error instalando dependencias.
    echo     Intenta ejecutar como Administrador.
    pause
    exit /b 1
)

echo.
echo  ✅ Todas las dependencias instaladas correctamente.
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  ✅ INSTALACIÓN COMPLETA                            ║
echo  ║                                                     ║
echo  ║  Para iniciar SENTINEL:                             ║
echo  ║  1. Abre MetaTrader 5 y loguéate en tu cuenta      ║
echo  ║  2. Haz doble clic en "INICIAR_SENTINEL.bat"       ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
pause
