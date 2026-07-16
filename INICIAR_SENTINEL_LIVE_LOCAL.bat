@echo off
rem ============================================================
rem  SENTINEL LIVE (local machine) -- one-command entry point.
rem  Starts scripts\live\watchdog_local.ps1 hidden in the background.
rem  The watchdog then ensures (and keeps alive):
rem    - MT5 terminal (Capitaria, DEMO 2883016567)
rem    - deals watcher (position logger)
rem    - armed executor (--arm --confirm-account 2883016567)
rem    - dashboard (FastAPI revamp UI, http://127.0.0.1:8501)
rem  Safe to run again any time: the watchdog is a singleton (refuses
rem  to start twice) and only relaunches components that are missing,
rem  so running this while everything is already up is a harmless no-op.
rem  After starting/detecting the watchdog, this also waits for the UI
rem  (http://127.0.0.1:8501) to answer and opens it in the default
rem  browser. Re-running while everything is already up simply
rem  re-opens the browser tab -- it changes nothing else.
rem  Logs: scripts\live\watchdog_local.log
rem ============================================================
cd /d "%~dp0"
start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0scripts\live\watchdog_local.ps1"
echo SENTINEL LIVE watchdog launch requested (hidden, detached). Check scripts\live\watchdog_local.log for status.
timeout /t 3 /nobreak >nul

echo Waiting for SENTINEL UI at http://127.0.0.1:8501 ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline = (Get-Date).AddSeconds(120); $up = $false;" ^
  "while ((Get-Date) -lt $deadline) {" ^
  "  try {" ^
  "    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8501' -UseBasicParsing -TimeoutSec 3;" ^
  "    if ($r.StatusCode -eq 200) { $up = $true; break }" ^
  "  } catch {}" ^
  "  Start-Sleep -Seconds 2" ^
  "}" ^
  "if ($up) { exit 0 } else { exit 1 }"

if errorlevel 1 (
    echo.
    echo [SENTINEL] ERROR: la UI no respondio en http://127.0.0.1:8501 dentro de 120s.
    echo            Revisa scripts\live\watchdog_local.log para ver el estado del watchdog.
    goto :eof
)

start "" http://127.0.0.1:8501
echo SENTINEL LIVE UI abierta en el navegador.
