@echo off
rem ============================================================
rem  AVA LIVE -- punto de entrada NO INTERACTIVO para la tarea
rem  programada `FOREX_AVA_LIVE` (D-62, 2026-08-20).
rem
rem  Identico en entorno a INICIAR_AVA_LIVE.bat pero sin banner
rem  ni `pause`, para que la tarea pueda relanzarlo sin dejar un
rem  cmd colgado esperando una tecla.
rem
rem  🔴 SINGLETON (2026-08-21): la tarea se dispara cada 5 min,
rem  asi que esto DEBE ser idempotente. Si ya hay un
rem  supervisor_live vivo, salimos sin hacer nada. Sin esta
rem  guarda cada disparo apilaria otro supervisor, y varios
rem  ejecutores armados sobre la misma cuenta es exactamente el
rem  escenario que duplica posiciones.
rem
rem  ATTACH-ONLY: no lanza el terminal MT5. Si el terminal no
rem  esta abierto y logueado en 101744074, el preflight del
rem  supervisor falla, lo registra en watchdog.log y NO arma nada.
rem  Eso es correcto: reintentara al siguiente disparo.
rem ============================================================
cd /d "%~dp0..\.."

rem --- Guarda de instancia unica -------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*supervisor_live*' }; if ($p) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [%DATE% %TIME%] supervisor_live ya esta corriendo -- no se relanza. >> "%~dp0ava_live_task.log"
    exit /b 0
)

echo [%DATE% %TIME%] supervisor_live NO estaba corriendo -- lanzando. >> "%~dp0ava_live_task.log"

set "SUPERVISOR_CONFIGS=ava"
rem AVA no tiene XAUUSD: sin esto el preflight falla y el
rem supervisor se niega a armar (correcto pero inutil).
set "SUPERVISOR_SYMBOL=GOLD"
rem 🔴 R2: el gate de spread 0.5 de Capitaria NO aplica a AVA
rem (spread medido de GOLD: 0.73-0.80). Vacio = sin cap estatico.
set "SUPERVISOR_MAX_SPREAD_OPEN="
set "SUPERVISOR_STALE_AUTORESTART=1"

"C:\Users\tomas\AppData\Local\Programs\Python\Python311\python.exe" -m scripts.live.supervisor_live >> "%~dp0ava_live_task.log" 2>&1
