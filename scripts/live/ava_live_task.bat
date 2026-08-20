@echo off
rem ============================================================
rem  AVA LIVE -- punto de entrada NO INTERACTIVO para la tarea
rem  programada `FOREX_AVA_LIVE` (D-62, 2026-08-20).
rem
rem  Identico en entorno a INICIAR_AVA_LIVE.bat pero sin banner
rem  ni `pause`, para que la tarea pueda relanzarlo sin dejar un
rem  cmd colgado esperando una tecla.
rem
rem  ATTACH-ONLY: no lanza el terminal MT5. Si el terminal no
rem  esta abierto y logueado en 101744074, el preflight del
rem  supervisor falla, lo registra en watchdog.log y NO arma nada.
rem  Eso es correcto: reintentara al siguiente ciclo de la tarea.
rem ============================================================
cd /d "%~dp0..\.."

set "SUPERVISOR_CONFIGS=ava"
rem AVA no tiene XAUUSD: sin esto el preflight falla y el
rem supervisor se niega a armar (correcto pero inutil).
set "SUPERVISOR_SYMBOL=GOLD"
rem 🔴 R2: el gate de spread 0.5 de Capitaria NO aplica a AVA
rem (spread medido de GOLD: 0.73-0.80). Vacio = sin cap estatico.
set "SUPERVISOR_MAX_SPREAD_OPEN="
set "SUPERVISOR_STALE_AUTORESTART=1"

"C:\Users\tomas\AppData\Local\Programs\Python\Python311\python.exe" -m scripts.live.supervisor_live >> "%~dp0ava_live_task.log" 2>&1
