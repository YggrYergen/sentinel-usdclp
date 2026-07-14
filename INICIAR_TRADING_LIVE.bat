@echo off
rem ============================================================
rem  SENTINEL — Watchdog del ejecutor live (DEMO 2883015767)
rem  Mantiene el ejecutor corriendo mientras esta ventana viva:
rem   - Espera a que el terminal MT5 portable este abierto (ATTACH-ONLY:
rem     el terminal lo abres TU con MT5_DEMO_TOMAS.bat, nunca este script).
rem   - Si el ejecutor no corre, lo (re)lanza armado via --confirm-account.
rem   - Registra cada relanzamiento en scripts\live\watchdog.log.
rem  Detener todo: cierra esta ventana Y la del ejecutor (o Ctrl-C aqui).
rem  Pausar solo aperturas: PAUSAR_TRADING.bat (kill-switch STOP).
rem  Roster: --configs live = LIVE_ROSTER en live_configs_20.py (4 configs).
rem ============================================================
setlocal
cd /d D:\FOREX

:loop
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'terminal64.exe' -and $_.ExecutablePath -like 'D:\FOREX\MT5_Portable*'}) {exit 0} else {exit 1}"
if errorlevel 1 (
    echo [%date% %time%] MT5 portable NO abierto - abre MT5_DEMO_TOMAS.bat. Reintento en 60s. >> scripts\live\watchdog.log
    echo MT5 portable no esta abierto. Abrelo con MT5_DEMO_TOMAS.bat - reintento en 60s...
    timeout /t 60 /nobreak >NUL
    goto loop
)

powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'python.exe' -and $_.CommandLine -match 'run_live_20'}) {exit 0} else {exit 1}"
if errorlevel 1 (
    echo [%date% %time%] Ejecutor no corre - relanzando armado. >> scripts\live\watchdog.log
    echo Relanzando ejecutor armado...
    python -m scripts.live.run_live_20 --arm --confirm-account 2883015767 --configs live
    echo [%date% %time%] Ejecutor termino (exit %errorlevel%). >> scripts\live\watchdog.log
)

timeout /t 30 /nobreak >NUL
goto loop
