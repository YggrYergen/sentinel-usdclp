# Equipo 3 — agregar Capitaria 2883016902 (checklist)

Objetivo final: **exactamente dos stacks**. AVA 101744074 (`C:\FOREX`, tarea
`SENTINEL_Watchdog_Equipo3`, dashboard :8501) y Capitaria 2883016902
(`C:\FOREX_CAP`, tarea `SENTINEL_Watchdog_Capitaria`, dashboard :8502). La AVA
101744076 (stack B) **deja el equipo 3** (pasa al equipo 1).

## Reglas (si algo no cuadra: PARAR y avisar al humano, no improvisar)
- No matar procesos por nombre. No `Stop-ScheduledTask`/`Stop-Process` sobre AVA.
- No `setx`. No editar `sentinel_engine\`, configs de estrategias ni `.ps1`.
- La password de MT5 la escribe **el humano** en la GUI. Claude nunca la pide.
- Nunca commitear `machine_local*.json` ni `CUENTAS.md`.
- No lanzar a mano ningún `python -m scripts.live.*` de Capitaria.
- MT5, reinicios y logins los hace **el humano**. Un proceso lanzado desde
  Claude muere al cerrar la sesión.

## Por qué el orden importa
El watchdog AVA que corre hoy (`b9c101b`) reconoce procesos solo por línea de
comandos. Vería el supervisor de Capitaria como propio, y su limpieza de
huérfanos mata **cualquier** `run_live_20`. Por eso Capitaria **no arranca**
hasta que el watchdog AVA nuevo esté corriendo. Ambos arrancan juntos en el
reinicio del paso 7. El nuevo watchdog AVA solo reconoce procesos de
`...\Python311\python.exe` sin la marca `sentinel_stack=capitaria`. Capitaria usa
su propio CPython real, `C:\FOREX_CAP\_py\python.exe`. Un venv no sirve, porque
su python.exe es un redirector cuyo hijo comparte ruta con AVA.

## 1. Foto inicial (solo leer)
```powershell
git -C C:\FOREX status --short; git -C C:\FOREX log -1 --oneline
Get-ScheduledTask SENTINEL* | Select TaskName,State
Get-CimInstance Win32_Process | ? { $_.Name -in 'python.exe','terminal64.exe' } |
  Select ProcessId,ParentProcessId,ExecutablePath,CommandLine | Format-List
Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 15
```
Esperado: HEAD `b9c101b`, AVA con supervisor y `run_live_20` vivos. Solo
`guard_cuenta.py` y su test aparecen modificados (D-63, añade la 101744076).
PARAR si no es así.

## 2. Guardar D-63 y sacar la 76 (sin tocar procesos)
```powershell
git -C C:\FOREX diff --output="$env:USERPROFILE\d63-guard-101744076.patch"
git -C C:\FOREX checkout -- sentinel_engine tests
Rename-Item C:\FOREX\scripts\live\machine_local.ava2.json machine_local.ava2.json.disabled
```
Los módulos ya cargados en memoria no cambian, así que AVA sigue igual. El
watchdog viejo leyó los perfiles al arrancar: seguirá cuidando la 76 hasta el
reinicio del paso 7. Es aceptable.

## 3. Actualizar el código AVA en disco
```powershell
git -C C:\FOREX pull --ff-only origin equipo3-runner
git -C C:\FOREX log -1 --oneline
```
Esperado: HEAD = el commit de esta checklist o posterior. El código nuevo se
activa en el paso 7.

## 4. MT5 de Capitaria (humano)
1. El humano descarga el instalador de marca de Capitaria desde su portal (no
   hay URL pública). Lo ejecuta con `/auto`. Luego, con Claude:
   `Move-Item "C:\Program Files\Capitaria MT5 Terminal" C:\MT5_CAPITARIA`.
   **Mover, nunca copiar.** Confirmar antes la ruta real de instalación.
2. El humano abre `C:\MT5_CAPITARIA\terminal64.exe` con doble clic. Inicia
   sesión con la 2883016902 y marca "guardar password". Verifica DEMO y un
   balance de ~71 MM CLP. Activa *Trading algorítmico*
   (Herramientas→Opciones→Asesores Expertos). Añade **XAUUSD** a Observación
   de Mercado (se pierde al mover).

## 5. Clon + intérprete propio
```powershell
git clone --branch equipo3-capitaria --single-branch --depth 1 (git -C C:\FOREX remote get-url origin) C:\FOREX_CAP
```
Después ejecutar **literalmente** el bloque de instalación de la cabecera de
`C:\FOREX_CAP\scripts\live\requirements-capitaria.txt` (NuGet CPython 3.12.10 en
`C:\FOREX_CAP\_py` + pip). Verificar:
```powershell
& C:\FOREX_CAP\_py\python.exe -c "import sys,pandas,numpy,MetaTrader5 as m;print(sys.version.split()[0],pandas.__version__,numpy.__version__,m.__version__)"
Test-Path C:\FOREX_CAP\_py\pyvenv.cfg
```
Esperado: `3.12.10 2.3.3 2.3.3 5.0.5735` y `False`.

## 6. Perfil + tests
Escribir `C:\FOREX_CAP\scripts\live\machine_local.json` (ASCII, sin BOM):
```powershell
$j = '{"terminal_path": "C:\\MT5_CAPITARIA\\terminal64.exe", "portable": false, "demo_login": 2883016902, "terminal_marker": "mt5_capitaria"}'
[IO.File]::WriteAllText('C:\FOREX_CAP\scripts\live\machine_local.json', $j)
```
Tests en primer plano, con el entorno limpio:
```powershell
foreach ($s in 'User','Machine') { [Environment]::GetEnvironmentVariables($s).Keys | ? { $_ -like 'SUPERVISOR_*' -or $_ -in 'SENTINEL_MACHINE_PROFILE','TZ' } }
Get-ChildItem env: | ? { $_.Name -like 'SUPERVISOR_*' -or $_.Name -eq 'SENTINEL_MACHINE_PROFILE' } | % { Remove-Item "env:$($_.Name)" }
cd C:\FOREX_CAP; & .\_py\python.exe -m pytest tests\live -q -p no:cacheprovider
```
Esperado: la primera línea no imprime nada, y `tests\live` da **0 failed**.
PARAR si no.

## 7. Autostart Capitaria + reinicio en la pausa del oro
1. Desde PowerShell elevado:
   `powershell -ExecutionPolicy Bypass -File C:\FOREX_CAP\scripts\live\setup_autostart_capitaria.ps1`.
   Solo registra la tarea. **No ejecutar `Start-ScheduledTask`**: el watchdog AVA
   viejo sigue vivo.
2. Esperar la **pausa diaria de XAUUSD: 17:00–18:00 de Nueva York** (hoy, 18:00–19:00 en Chile):
   `[TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date),'Eastern Standard Time')`.
3. El humano revisa en el MT5 de AVA si hay posiciones abiertas y lo anota.
   Si las hay, el humano decide si se sigue. El reinicio equivale a la
   caída y el relanzamiento que el watchdog ya hace solo.
4. **El humano reinicia Windows** e inicia sesión como Administrator. Las dos
   tareas arrancan en el logon. Es el reinicio completo de AVA con el
   watchdog nuevo, y a la vez la prueba del autoarranque.

## 8. Verificación (5–10 min tras el logon)
```powershell
Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 30
Get-Content C:\FOREX_CAP\scripts\live\watchdog_capitaria.log -Tail 30
Get-CimInstance Win32_Process | ? { $_.Name -in 'python.exe','terminal64.exe' } |
  Select ProcessId,ExecutablePath,CommandLine | Format-List
```
Debe cumplirse:
- Log AVA: `interprete clavado: ...Python311\python.exe` y `stack B deshabilitado (sin machine_local.ava2.json)`.
- Log Capitaria: `interprete: C:\FOREX_CAP\_py\python.exe (Python 3.12.10)` y luego líneas `OK: watcher=True supervisor=True dashboard=True`.
- Exactamente **un** `supervisor_live` y **un** `run_live_20` por stack. Los de Capitaria van con exe `C:\FOREX_CAP\_py\python.exe` y `-X sentinel_stack=capitaria`. Los de AVA van con `...\Python311\python.exe`.
- Terminales: solo el de AVA 74 y `C:\MT5_CAPITARIA\terminal64.exe`. Si el de la 76 está abierto, lo cierra el humano.
- El MT5 de Capitaria entró solo en la 2883016902 y tiene XAUUSD en Observación de Mercado.
- Las posiciones AVA anotadas siguen igual, sin duplicados.
- `http://localhost:8501` (AVA) y `http://localhost:8502` (Capitaria) responden.
- Los timestamps de los logs Python de Capitaria van en hora de Nueva York (hoy, 1 h menos que Chile; es lo esperado, `TZ=EST5EDT`). El `watchdog_capitaria.log` va en hora de Chile.
- La primera línea `dashboard CAIDO ... relanzando` tras el arranque es normal.

## 9. Acta
Escribir `docs\EQUIPO3-SESION-2026-10-06-CAPITARIA.md` (lo hecho, PIDs, SHAs,
desvíos, pendientes) y subirla junto con el parche D-63:
```powershell
git -C C:\FOREX worktree add -b equipo3-actas C:\FOREX_ACTAS origin/equipo3-runner
# copiar ahí el acta, d63-guard-101744076.patch y el acta del 2026-09-24 si existe
git -C C:\FOREX_ACTAS add -A; git -C C:\FOREX_ACTAS commit -m "acta(equipo3): Capitaria 2883016902 en marcha"
git -C C:\FOREX_ACTAS push origin equipo3-actas; git -C C:\FOREX worktree remove C:\FOREX_ACTAS
```
Si el push falla por credenciales: dejar los ficheros en `C:\FOREX_ACTAS` y avisar.

Pendiente fuera de hoy: BIOS "restore on AC power loss" + autologin de
Windows, backup de `research.db`, montar la 76 en el equipo 1.
