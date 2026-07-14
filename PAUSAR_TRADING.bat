@echo off
rem Congela NUEVAS aperturas del ejecutor live (kill-switch STOP).
rem Las posiciones abiertas siguen gestionadas (trailing SL y cierres continúan).
type NUL > "%~dp0scripts\live\STOP"
echo [SENTINEL] Kill-switch ACTIVADO: no se abriran posiciones nuevas.
echo            Las posiciones abiertas siguen protegidas y gestionadas.
pause
