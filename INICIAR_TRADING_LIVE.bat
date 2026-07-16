@echo off
rem ============================================================
rem  SENTINEL -- Live launcher (DEMO 2883015767)
rem  Thin wrapper: all supervisor logic lives in
rem  scripts\live\supervisor_live.py (preflight gate, relaunch with
rem  backoff, staleness alarm, watchdog.log). This .bat only sets the
rem  working directory and starts the Python supervisor loop.
rem
rem  BEFORE running this: open the MT5 portable terminal YOURSELF via
rem  MT5_DEMO_TOMAS.bat (ATTACH-ONLY -- nothing in this repo ever
rem  launches terminal64.exe for you).
rem
rem  Stop everything: close this window (Ctrl-C), then close the
rem  executor window it spawned if still open.
rem  Pause NEW opens only (STOP kill-switch): PAUSAR_TRADING.bat
rem  Resume: REANUDAR_TRADING.bat
rem  Roster: --configs live = LIVE_ROSTER in live_configs_20.py (4 configs).
rem  Log: scripts\live\watchdog.log (supervisor events, UTF-8, timestamped).
rem ============================================================
setlocal
cd /d D:\FOREX

python -m scripts.live.supervisor_live

endlocal
