@echo off
rem ============================================================
rem  EQUIPO 3 -- runner oficial (2026-09-24)
rem
rem  Arranca watchdog_equipo3.ps1 EN PRIMER PLANO, con la ventana
rem  visible. Sirve para la primera puesta en marcha y para
rem  diagnosticar: en regimen normal el watchdog lo lanza la tarea
rem  programada SENTINEL_Watchdog_Equipo3, oculto y al iniciar
rem  sesion (ver scripts\live\setup_autostart_equipo3.ps1).
rem
rem  El watchdog mantiene vivos:
rem    STACK #1 (AVA 101744074, ARMADO)
rem       terminal MT5 #1 + deals watcher + supervisor
rem       roster `ava`: S6-K2P0-AVA (magic 727010)
rem                   + SuperTrend-p14x3-M15-AVA (magic 727020)
rem       simbolo GOLD, lote 0.01, una posicion por estrategia.
rem       Configuracion IDENTICA a la que corria en el equipo 1.
rem    STACK #2 (segunda demo AVA, SOLO MONITORIZACION)
rem       terminal MT5 #2 + deals watcher a data/research_ava2.db
rem       sin supervisor y sin ejecutor: hoy no tiene estrategias.
rem       Si falta su perfil, el watchdog lo salta sin quejarse.
rem    Dashboard en http://127.0.0.1:8501
rem
rem  NO CORRAS ESTO A LA VEZ QUE LA TAREA PROGRAMADA. El watchdog
rem  es singleton (lockfile + comprobacion de linea de comandos) y
rem  la segunda instancia se negara a arrancar, pero es ruido
rem  evitable. Para el modo manual:
rem     Stop-ScheduledTask -TaskName SENTINEL_Watchdog_Equipo3
rem
rem  ANTES de la primera vez: abre los DOS terminales MT5 a mano e
rem  inicia sesion en cada cuenta. El watchdog sabe relanzarlos,
rem  pero el primer login lo haces tu.
rem
rem  Parar el trading sin parar el watchdog: PAUSAR_TRADING.bat
rem  (kill-switch por fichero STOP; el supervisor sigue vivo y se
rem  niega a armar mientras exista).
rem
rem  Logs: scripts\live\watchdog_equipo3.log
rem        scripts\live\run_live_20.audit.log
rem        scripts\live\deals_watcher_local.log   (stack #1)
rem        scripts\live\deals_watcher_ava2.log    (stack #2)
rem ============================================================
cd /d "%~dp0"

rem --- El entorno NO se define aqui. El watchdog inyecta las
rem     variables SUPERVISOR_* y SENTINEL_MACHINE_PROFILE en cada
rem     hijo por separado, porque en esta maquina conviven dos
rem     stacks y una variable global se aplicaria a los dos.

echo ============================================================
echo  EQUIPO 3 ^| runner oficial ^| watchdog en primer plano
echo  stack #1: AVA 101744074 - S6-K2P0-AVA + SuperTrend-AVA
echo  stack #2: segunda demo AVA - solo monitorizacion
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\live\watchdog_equipo3.ps1"

echo.
echo [EQUIPO 3] el watchdog termino. Revisa scripts\live\watchdog_equipo3.log
pause
