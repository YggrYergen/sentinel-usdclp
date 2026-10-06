@echo off
rem ============================================================
rem  STACK CAPITARIA -- equipo 3 (2026-09-24)
rem
rem  Arranca watchdog_capitaria.ps1 EN PRIMER PLANO, ventana
rem  visible. Para la primera puesta en marcha y diagnostico.
rem  En regimen normal lo lanza la tarea programada
rem  SENTINEL_Watchdog_Capitaria, oculta y al iniciar sesion.
rem
rem  Mantiene vivos, TODOS sobre el CPython propio de este clon (_py):
rem    terminal MT5 Capitaria + deals watcher + supervisor
rem    roster `tomachine`: S6-K2P0 (ficha unica) + SuperTrend
rem    XAUUSD, lote 0.67, max_volume 0.67
rem    cap de spread 0.50 (gate adaptativo APAGADO)
rem    ventana de apertura bloqueada 18:00-18:45 (hora de NUEVA YORK: los
rem      procesos de este stack, y solo ellos, corren con TZ=EST5EDT, inyectado
rem      por proceso por watchdog_capitaria.ps1; decision del usuario 2026-10-06)
rem    dashboard en http://127.0.0.1:8502  (el 8501 es de AVA)
rem
rem  Configuracion IDENTICA a M2_ENTREGA (commit b113eb7).
rem
rem  NO lo corras a la vez que la tarea programada: el watchdog
rem  es singleton y la segunda instancia se negara a arrancar.
rem     NO uses Stop-ScheduledTask (puede tumbar el arbol de procesos, o sea
rem     supervisor y ejecutor). Para el watchdog PARA SOLO su powershell:
rem       Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'watchdog_capitaria\.ps1' }
rem       Stop-Process -Id <PID del powershell>
rem
rem  ANTES de la primera vez: abre el terminal MT5 de Capitaria,
rem  inicia sesion y anade XAUUSD a Observacion de Mercado.
rem
rem  Logs: scripts\live\watchdog_capitaria.log
rem        scripts\live\watchdog.log           (preflight)
rem        scripts\live\run_live_20.audit.log  (decisiones)
rem ============================================================
cd /d "%~dp0"

rem --- El entorno NO se define aqui: lo inyecta el watchdog por
rem     proceso, porque en esta maquina conviven dos stacks.

echo ============================================================
echo  CAPITARIA ^| equipo 3 ^| XAUUSD ^| lote 0.67
echo  roster tomachine: S6-K2P0 + SuperTrend-p14x3-M15
echo  cap spread 0.50 ^| ventana bloqueada 18:00-18:45
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\live\watchdog_capitaria.ps1"

echo.
echo [CAPITARIA] el watchdog termino. Revisa scripts\live\watchdog_capitaria.log
pause
