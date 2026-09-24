@echo off
rem Quita el kill-switch: el ejecutor vuelve a poder abrir posiciones.
del "%~dp0scripts\live\STOP" 2>NUL
echo [SENTINEL] Kill-switch DESACTIVADO: el ejecutor puede abrir posiciones de nuevo.
pause
