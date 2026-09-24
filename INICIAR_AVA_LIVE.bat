@echo off
rem ============================================================
rem  AVA LIVE (D-62, 2026-08-20) -- S6-K2P0 + SuperTrend ORIGINALES
rem  sobre la demo AVA 101744074 (simbolo GOLD, lote 0.01,
rem  UNA posicion por estrategia, ventana R1/R2).
rem
rem  Proposito: calibrar la paridad backtest<->live que compuerta
rem  el congelado del motor. NO es una prueba de rentabilidad.
rem
rem  Arranca scripts.live.supervisor_live, que a su vez:
rem    - corre el preflight y SE NIEGA a armar si falla
rem      (p.ej. terminal MT5 cerrado -> lo dice y no lanza nada)
rem    - lanza el ejecutor armado como subproceso
rem      (--arm --confirm-account 101744074 --configs ava)
rem    - lo RELANZA con backoff exponencial si muere, sin limite
rem    - alarma si el audit log se queda rancio (>5 min) y, con
rem      SUPERVISOR_STALE_AUTORESTART=1, lo recicla
rem
rem  ATTACH-ONLY: este script NUNCA lanza el terminal MT5. Debes
rem  tener D:\FOREX\MT5_Tester\terminal64.exe abierto y logueado
rem  en la cuenta 101744074 ANTES de correr esto.
rem
rem  Parar: PAUSAR_TRADING.bat (kill-switch por fichero STOP) o
rem         cerrar esta ventana.
rem  Logs:  scripts\live\watchdog.log
rem         scripts\live\run_live_20.audit.log
rem ============================================================
cd /d "%~dp0"

rem --- Entorno SOLO de este proceso. NO tocamos las variables
rem     persistidas con setx (SUPERVISOR_CONFIGS=local,
rem     SUPERVISOR_MAX_SPREAD_OPEN=0.5), que son de la maquina
rem     Capitaria y deben seguir intactas para ese stack.
set "SUPERVISOR_CONFIGS=ava"

rem --- AVA no tiene XAUUSD en absoluto. Sin esto el preflight
rem     falla (symbol_info('XAUUSD') -> None) y el supervisor se
rem     niega a armar: correcto, pero nada se ejecutaria nunca.
set "SUPERVISOR_SYMBOL=GOLD"

rem --- 🔴 CRITICO: el gate de spread 0.5 de Capitaria NO es
rem     transferible a AVA (regla R2, directiva del user).
rem     Medido 2026-08-20: el spread de GOLD en AVA es 0.73-0.80,
rem     asi que un cap de 0.5 bloquearia el 100% de las aperturas
rem     EN SILENCIO -- el sistema pareceria sano sin abrir nada.
rem     Vacio = no se anade ningun cap estatico.
set "SUPERVISOR_MAX_SPREAD_OPEN="

rem --- Reciclar el ejecutor si el audit log se queda rancio.
set "SUPERVISOR_STALE_AUTORESTART=1"

echo ============================================================
echo  AVA LIVE  ^|  cuenta 101744074  ^|  GOLD  ^|  lote 0.01
echo  roster: ava (S6-K2P0-AVA 727010 + SuperTrend-AVA 727020)
echo  spread cap: OFF (R2 -- el 0.5 de Capitaria no aplica aqui)
echo ============================================================
echo.

"C:\Users\tomas\AppData\Local\Programs\Python\Python311\python.exe" -m scripts.live.supervisor_live

echo.
echo [AVA LIVE] el supervisor termino. Revisa scripts\live\watchdog.log
pause
