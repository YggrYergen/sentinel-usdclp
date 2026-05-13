@echo off
title 🔄 SENTINEL — Actualizar
color 0E
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║           🔄 SENTINEL — Actualización               ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Verificar Git
git --version >nul 2>&1
if errorlevel 1 (
    echo  ❌ Git no encontrado. Instálalo desde https://git-scm.com
    pause
    exit /b 1
)

echo  📥 Descargando última versión...
echo.

:: Guardar cambios locales (si los hay)
git stash >nul 2>&1

:: Actualizar
git pull origin main
if errorlevel 1 (
    echo.
    echo  ❌ Error descargando actualización.
    echo     Verifica tu conexión a internet.
    git stash pop >nul 2>&1
    pause
    exit /b 1
)

:: Restaurar cambios locales
git stash pop >nul 2>&1

:: Actualizar dependencias (por si hay nuevas)
echo.
echo  📦 Actualizando dependencias...
pip install -r sentinel\requirements.txt --quiet

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  ✅ ACTUALIZACIÓN COMPLETA                          ║
echo  ║                                                     ║
echo  ║  Cierra y reabre SENTINEL para ver los cambios.     ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
pause
