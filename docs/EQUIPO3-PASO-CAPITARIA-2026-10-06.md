# Equipo 3 — runbook de ejecución: levantar Capitaria 2883016902 y desmontar el stack B (AVA 101744076)

> **Fecha:** 2026-10-06 · **Quién lo ejecuta:** el Claude Code del equipo 3 (Windows 10 Pro 19045,
> usuario `Administrator`, Windows PowerShell 5.1, Git for Windows) · **Quién supervisa:** el humano.
>
> Este documento es una **orden de trabajo**, no un ensayo. Se ejecuta **fase a fase, en orden**.
> Cada paso trae: el motivo en una línea, el comando exacto, el resultado esperado y la condición de
> **STOP**. Si se cumple un STOP: **párate, informa al humano con la salida literal y no improvises**
> (ver «Cómo informar un STOP»). La spec de fondo es `docs/EQUIPO3-ESTADO-Y-PENDIENTES.md` §5; si hay
> contradicción con este runbook, **manda este runbook para lo que se hace hoy**.

---

## A · Qué hay que dejar hecho hoy

Al final de la jornada el equipo 3 corre **exactamente dos stacks aislados, autosanables**, y ninguno más:

| Stack | Cuenta | Carpeta / rama | Intérprete | MT5 | Tarea programada | Dashboard |
|---|---|---|---|---|---|---|
| **AVA** (ya VIVO) | 101744074 — S6 + SuperTrend, `GOLD`, 0.01 | `C:\FOREX` · `equipo3-runner` | Python 3.11 del sistema (`py -3.11`) | `C:\MT5_AVA1` | `SENTINEL_Watchdog_Equipo3` | `:8501` |
| **Capitaria** (NUEVO) | 2883016902 (demo, ~71 MM CLP) — roster `tomachine`: S6-K2P0 + SuperTrend, `XAUUSD`, 0.67 | `C:\FOREX_CAP` · `equipo3-capitaria` | CPython **3.12.10 propio**, `C:\FOREX_CAP\_py\python.exe` (**no venv**) | `C:\MT5_CAPITARIA` | `SENTINEL_Watchdog_Capitaria` | `:8502` |

Y se **desmonta** el stack B de AVA (**101744076**, MT5 `C:\MT5_AVA2`): esa cuenta se muda al equipo 1 más
adelante. En el equipo 3 deja de existir como stack.

**Hechos fijos (no los «corrijas»; si no cuadran con lo que ves, es un STOP):**

| Dato | Valor |
|---|---|
| SHA de código auditado de `equipo3-runner` | `76295c0bb974d4302cd3efe9fb57b066f66976d3` (el tip actual puede ser un descendiente que solo añade este runbook: ver 3.1) |
| SHA de `equipo3-capitaria` | `91ad3e74b55b594722367a19227027284ccf3308` |
| Remoto | el que diga `git -C C:\FOREX remote get-url origin` (esperado `https://github.com/YggrYergen/sentinel-usdclp.git`) |
| Servidor MT5 de Capitaria | `Capitaria-All` (según `guard_cuenta.py` de `equipo3-capitaria`) |
| Perfil Capitaria | `terminal_path` `C:\MT5_CAPITARIA\terminal64.exe` · `portable` `false` · `demo_login` `2883016902` · `terminal_marker` `mt5_capitaria` |
| Magics Capitaria | S6-K2P0 = **724011** · SuperTrend = **724071** (los de AVA son 727011 / 727021) |
| Línea de comandos del ejecutor de Capitaria | `run_live_20 --arm --confirm-account 2883016902 --configs tomachine --max-spread-open 0.5 --blocked-open-window 18:00-18:45 --no-adaptive-spread` (idéntica a M2) |

### A.1 · Mapa de procesos esperados al final

| Stack | `ExecutablePath` de todos sus python | Procesos |
|---|---|---|
| AVA | `C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe` (se confirma en la fase 0) | ejecutor armado, `supervisor_live`, watcher `research.db`, `run_bars_ingester`, dashboard 8501 |
| Capitaria | exactamente `C:\FOREX_CAP\_py\python.exe` | watcher `research.db`, `supervisor_live`, ejecutor armado, dashboard 8502. El `run_bars_ingester` **no** se espera (el de AVA ya corre y el supervisor de Capitaria lo da por suyo: cruce de `process_running` aceptado, ver «Riesgos») |
| Terminales | exactamente 2 `terminal64.exe` | `C:\MT5_AVA1\terminal64.exe` y `C:\MT5_CAPITARIA\terminal64.exe`. **Ninguno** de `C:\MT5_AVA2` |

---

## B · Reglas de ejecución (leer antes de empezar)

1. **Usa la herramienta PowerShell (Windows PowerShell 5.1).** No uses Bash para estos comandos. No uses `&&`,
   `||`, `?:`, `??`, `?.` (no existen en 5.1). No redirijas con `2>&1` un ejecutable nativo.
2. **Cada llamada a la herramienta es independiente: no conserva variables.** Lo que hay que recordar entre
   pasos viaja en `"$env:TEMP\eq3_state.json"` y `"$env:TEMP\eq3_t0.txt"` (los crea este runbook). Los
   bloques de verificación empiezan por las mismas dos líneas (`Chk`) y terminan en `RESULTADO: PASS` o
   `RESULTADO: STOP`. **Cualquier línea que empiece por `STOP:` es una condición de parada.**
3. **Timeouts:** las llamadas largas llevan indicado el `timeout` (ms) a pasar a la herramienta. Sin él, el
   defecto son 2 minutos.
4. **Un solo cambio a la vez, y solo los que este runbook ordena.** No «arregles» nada que no esté aquí.
   Si algo inesperado aparece (aunque parezca inofensivo): STOP.
5. **Nunca** escribas, pidas, leas ni almacenes una contraseña. La del terminal la teclea el humano en la GUI de MT5.
6. **No hagas ninguna llamada a MT5** (`mt5.initialize`, `verify_two_terminals`, etc.). Los únicos que se
   enganchan a MT5 son los propios watchdogs/stack. Todo se verifica por procesos, logs y puertos.
7. **Trampa de los watchdogs:** el watchdog de cada stack se niega a arrancar si ve **otro** `powershell`
   cuya línea de comandos contenga la ruta literal `watchdog_equipo3.ps1` / `watchdog_capitaria.ps1`.
   Por eso, en los comandos que lanzan o conviven con un watchdog, esa ruta se escribe **partida**
   (`'watchdog_equipo3.' + 'ps1'`) y los filtros usan el regex `watchdog_equipo3\.ps1` (con la barra), que no se
   reconoce a sí mismo. **No «simplifiques» esos comandos.**

### Bloque `Chk` (se repite en cada verificación)

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
```

### Cómo informar un STOP

Detén la ejecución y responde al humano **solo** con: (1) fase y paso; (2) la condición que falló; (3) la salida
literal del comando; (4) el estado actual (qué se hizo ya y qué no; PIDs de AVA); (5) «no he cambiado nada más».
No escribas ni pushees el acta salvo que el humano lo pida expresamente.

---

## Fase 0 — Foto del estado actual (no se cambia nada)

**Por qué:** hay que saber exactamente qué corre hoy (sobre todo la 74, que opera en vivo) para poder
demostrar al final que no se tocó. **Esta fase no cambia nada** (el `git fetch` del mensaje inicial solo movió
referencias).

### 0.1 Entorno, privilegios y reloj

```powershell
$PSVersionTable.PSVersion.ToString()
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
whoami
Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
$tz = Get-TimeZone; $off = $tz.GetUtcOffset((Get-Date))
"zona={0} | nombre={1} | offset_ahora={2} | offset_base={3} | horario_verano={4}" -f $tz.Id, $tz.DisplayName, $off, $tz.BaseUtcOffset, $tz.IsDaylightSavingTime((Get-Date))
git --version
git -C C:\FOREX remote get-url origin
git -C C:\FOREX config user.name
git -C C:\FOREX config user.email
Get-PSDrive C | Select-Object Used, Free
```

**Esperado:** versión `5.1.x`; segunda línea `True`; `whoami` termina en `\administrator`; la zona es
`Pacific SA Standard Time`. Anota `offset_ahora` (se espera `-03:00` porque Chile está en horario de verano;
esto **importa en 7.4**). `user.name`/`user.email` pueden salir vacíos (se trata en 1.4).
**STOP si:** la versión no es 5.1.x; o la sesión **no** es administrador (`False`): el humano debe reabrir
Claude Code desde un PowerShell «Ejecutar como administrador» (hacen falta privilegios para la fase 8).

### 0.2 Git de `C:\FOREX`

```powershell
$st = @(git -C C:\FOREX status --porcelain=v1)
$st
git -C C:\FOREX status --branch --short | Select-Object -First 1
git -C C:\FOREX log -1 --format='%H %s'
git -C C:\FOREX rev-parse origin/equipo3-runner
git -C C:\FOREX merge-base --is-ancestor HEAD origin/equipo3-runner; "HEAD es ancestro de origin/equipo3-runner: exit=$LASTEXITCODE"
git -C C:\FOREX worktree list
$allowed = @(' M sentinel_engine/live/guard_cuenta.py', ' M tests/live/test_guard_cuenta.py', '?? scripts/live/bars_ingester_console.log', '?? docs/EQUIPO3-SESION-2026-09-24-INSTALACION-REALIZADA.md')
"entradas inesperadas: " + (@($st | Where-Object { $allowed -notcontains $_ }) -join ' || ')
"faltan las 2 modificaciones D-63: " + (@($allowed[0..1] | Where-Object { $st -notcontains $_ }) -join ' || ')
```

**Esperado:** rama `equipo3-runner`; `HEAD` = `b9c101b…` (o `a088146…`), ancestro de `origin/equipo3-runner`
(`exit=0`); `git status` con **exactamente** `M guard_cuenta.py`, `M test_guard_cuenta.py`,
`?? scripts/live/bars_ingester_console.log` y, si existe en esa carpeta, `?? docs/EQUIPO3-SESION-2026-09-24-INSTALACION-REALIZADA.md`;
`worktree list` con una sola línea. Las dos últimas líneas de salida deben terminar vacías.
**STOP si:** hay entradas inesperadas; falta alguna de las dos modificaciones D-63 (alguien ya las trató);
`HEAD` no es ancestro (`exit` ≠ 0); hay más de un worktree.

### 0.3 Tareas programadas

```powershell
Get-ScheduledTask | Where-Object { $_.TaskName -like 'SENTINEL*' } | ForEach-Object {
    $i = Get-ScheduledTaskInfo -TaskName $_.TaskName
    [pscustomobject]@{ Tarea = $_.TaskName; Estado = $_.State; UltimoResultado = $i.LastTaskResult; MultiplesInstancias = $_.Settings.MultipleInstances;
        Accion = (($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments + ' [wd=' + $_.WorkingDirectory + ']' }) -join ' ; ') }
} | Format-List
```

**Esperado:** **una sola** tarea `SENTINEL*`: `SENTINEL_Watchdog_Equipo3`, `Estado = Running`, acción `powershell.exe … -File "C:\FOREX\scripts\live\watchdog_equipo3.ps1"` con `wd=C:\FOREX`. Anota `MultiplesInstancias`.
**STOP si:** no existe la tarea; no está `Running`; existe cualquier otra tarea `SENTINEL*` (p. ej. una Capitaria a medias).

### 0.4 Procesos: volcado completo (solo lectura)

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(pythonw?|terminal64)\.exe$' -or ($_.Name -match '^powershell(\.exe)?$' -and $_.CommandLine -match 'watchdog_' -and $_.ProcessId -ne $PID) } |
    Select-Object ProcessId, ParentProcessId, Name, ExecutablePath, CommandLine | Format-List
Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 15
(Get-Item C:\FOREX\scripts\live\watchdog_equipo3.log).LastWriteTime
```

**Esperado (acta 2026-09-24):** python bajo `…\Python311\python.exe`: ejecutor (`run_live_20 --arm --confirm-account 101744074 --configs ava`),
`supervisor_live`, watcher `--db data/research.db`, watcher `--db data/research_ava2.db` (stack B),
`run_bars_ingester` (y el dashboard `run_service.py … --port 8501` si ya lo lanzó el watchdog);
dos `terminal64.exe` (`C:\MT5_AVA1\…` y `C:\MT5_AVA2\…`); un `powershell` con `watchdog_equipo3.ps1`.
La cola del log termina en líneas `OK: watcher1=True supervisor=True watcher2=True stack2=True STOP=False`
y `LastWriteTime` de hace menos de 2 minutos. (Los PIDs del acta —12520, 11636, …— ya no valen: lo que
cuenta es lo que veas ahora.)

### 0.5 Comprobación de AVA y registro de PIDs

**Por qué:** fija la línea base (PIDs + hora de creación + intérprete) contra la que se demostrará que AVA
no se tocó. **No sigas si AVA no está como se espera.**

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$wp  = @(Get-CimInstance Win32_Process)
$py  = @($wp | Where-Object { $_.Name -match '^pythonw?\.exe$' })
$trm = @($wp | Where-Object { $_.Name -eq 'terminal64.exe' })
$wdg = @($wp | Where-Object { $_.Name -match '^powershell(\.exe)?$' -and $_.CommandLine -match 'watchdog_equipo3\.ps1' -and $_.ProcessId -ne $PID })
function Sel([string]$rx) { return @($py | Where-Object { $_.CommandLine -match $rx }) }
function Same($a, $b) { return [bool]($a -and $b -and ($a.ToLower() -eq $b.ToLower())) }
$ex   = @(Sel 'run_live_20' | Where-Object { $_.CommandLine -match '--arm' })
$sup  = @(Sel 'supervisor_live')
$w1   = @(Sel 'run_deals_watcher' | Where-Object { $_.CommandLine -match 'research\.db' })
$w2   = @(Sel 'run_deals_watcher' | Where-Object { $_.CommandLine -match 'research_ava2\.db' })
$ing  = @(Sel 'run_bars_ingester')
$dash = @(Sel 'run_service\.py')
$prof1 = Get-Content -Raw -LiteralPath 'C:\FOREX\scripts\live\machine_local.json' | ConvertFrom-Json
$prof2 = Get-Content -Raw -LiteralPath 'C:\FOREX\scripts\live\machine_local.ava2.json' | ConvertFrom-Json
$t1 = @($trm | Where-Object { Same $_.ExecutablePath $prof1.terminal_path })
$t2 = @($trm | Where-Object { Same $_.ExecutablePath $prof2.terminal_path })
Chk ($prof1.demo_login -eq 101744074) "machine_local.json = stack A, demo_login $($prof1.demo_login)"
Chk ($prof2.demo_login -eq 101744076) "machine_local.ava2.json = stack B, demo_login $($prof2.demo_login)"
Chk ($ex.Count -eq 1) "ejecutor armado de AVA: exactamente 1 (hay $($ex.Count))"
Chk (($ex.Count -eq 1) -and ($ex[0].CommandLine -match 'confirm-account 101744074')) 'el ejecutor lleva --confirm-account 101744074'
Chk ($sup.Count -eq 1) "supervisor_live: exactamente 1 (hay $($sup.Count))"
Chk ($w1.Count -eq 1) "watcher stack A (research.db): exactamente 1 (hay $($w1.Count))"
Chk ($t1.Count -eq 1) "terminal stack A ($($prof1.terminal_path)): exactamente 1 (hay $($t1.Count))"
Chk ($wdg.Count -eq 1) "watchdog_equipo3: exactamente 1 powershell (hay $($wdg.Count))"
$exes = @(@($ex + $sup + $w1) | ForEach-Object { $_.ExecutablePath } | Select-Object -Unique)
Chk ($exes.Count -eq 1) "ejecutor, supervisor y watcher A comparten UN python.exe: $($exes -join ' ; ')"
Chk (-not (Test-Path 'C:\FOREX\.venv\Scripts\python.exe')) 'no hay .venv en C:\FOREX (el watchdog resolveria otro interprete)'
$leak = @($wp | Where-Object { $_.Name -match '^(pythonw?|terminal64)\.exe$' -and (($_.CommandLine -match 'FOREX_CAP|MT5_CAPITARIA') -or ($_.ExecutablePath -match 'FOREX_CAP|MT5_CAPITARIA')) })
Chk ($leak.Count -eq 0) 'no existe todavia ningun python/terminal de Capitaria'
"info: watcher stack B = $($w2.Count) | terminal stack B = $($t2.Count) | ingester = $($ing.Count) | dashboard = $($dash.Count)"
function Rec($p) { if ($null -eq $p) { return $null }; return [pscustomobject]@{ Pid = [int]$p.ProcessId; Created = $p.CreationDate.ToString('o'); Exe = $p.ExecutablePath } }
if ($global:bad -eq 0) {
    $state = [pscustomobject]@{
        taken = (Get-Date).ToString('o'); python_exe = $ex[0].ExecutablePath
        executor = (Rec $ex[0]); supervisor = (Rec $sup[0]); watcher1 = (Rec $w1[0]); watcher2 = (Rec $w2[0])
        ingester = (Rec $ing[0]); dashboard = (Rec $dash[0]); terminal1 = (Rec $t1[0]); terminal2 = (Rec $t2[0]); watchdog = (Rec $wdg[0])
        term1_path = $prof1.terminal_path; term2_path = $prof2.terminal_path
    }
    $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $env:TEMP 'eq3_state.json') -Encoding ASCII
    "estado guardado en $(Join-Path $env:TEMP 'eq3_state.json')"
    Get-Content -Raw -LiteralPath (Join-Path $env:TEMP 'eq3_state.json')
}
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

**Esperado:** todas las líneas `OK:` y `RESULTADO: PASS`; el JSON mostrado trae los PIDs de ejecutor, supervisor,
watchers, terminales y watchdog. **Anota esos PIDs en tu informe final.**
**STOP si:** cualquier línea `STOP:`. En particular: más de un ejecutor (¡ejecutor duplicado en vivo!), ningún
ejecutor, intérprete distinto entre procesos, o procesos de Capitaria ya presentes. No arregles nada.

---

## Fase 1 — Preservar el cambio D-63 sin tocar el árbol vivo

**Por qué:** la sanción de la cuenta 101744076 en `guard_cuenta.py` (D-63) y el acta del 2026-09-24 existen **solo en el
disco de esta máquina, sin commitear**. Se salvan en la rama `equipo3-d63` usando un `git worktree` aparte, para
**no hacer ningún commit ni checkout sobre `C:\FOREX`** mientras la 74 opera. Después se devuelve el árbol a
limpio en esos dos ficheros (la 76 se va, ya no los necesita).

**Por qué es seguro con AVA corriendo:** Python ya tiene cargados esos módulos en memoria; un relanzamiento
del ejecutor/supervisor de la 74 vuelve a importar `guard_cuenta.py`, y la 74 (101744074) **ya** está en el
conjunto sancionado original; **no necesita** 101744076. El único consumidor de la 76 (watcher del stack B) se
apaga en la fase 2.

### 1.1 Contenido del cambio

```powershell
git -C C:\FOREX diff --stat
git -C C:\FOREX diff -- sentinel_engine/live/guard_cuenta.py
Select-String -LiteralPath C:\FOREX\sentinel_engine\live\guard_cuenta.py -Pattern '101744076' | Select-Object LineNumber, Line
Select-String -LiteralPath C:\FOREX\tests\live\test_guard_cuenta.py -Pattern '101744076' | Select-Object LineNumber, Line
git -C C:\FOREX ls-remote --heads origin equipo3-d63 equipo3-actas
```

**Esperado:** `diff --stat` con **solo 2 ficheros** (`guard_cuenta.py`, `test_guard_cuenta.py`) y pocas líneas; el diff añade
`101744076` al frozenset `SANCTIONED_DEMO_LOGINS` con comentario D-63; ambos `Select-String` devuelven líneas; `ls-remote` **sin salida**
(las ramas `equipo3-d63` y `equipo3-actas` no existen aún).
**STOP si:** el diff toca otros ficheros; los `Select-String` no encuentran `101744076`; ya existe `equipo3-d63` en el remoto
(si existe `equipo3-actas` no es STOP: ver 10.3).

### 1.2 Worktree y rama nueva sobre el `HEAD` actual

```powershell
git -C C:\FOREX worktree add -b equipo3-d63 C:\FOREX_WT_D63 HEAD
git -C C:\FOREX_WT_D63 status --short --branch
```

**Esperado:** `Preparing worktree (new branch 'equipo3-d63')` y `HEAD is now at …`; `status` limpio en `## equipo3-d63`.
**STOP si:** el directorio o la rama ya existen, o el comando falla.

### 1.3 Copiar los ficheros al worktree

```powershell
Copy-Item -LiteralPath C:\FOREX\sentinel_engine\live\guard_cuenta.py -Destination C:\FOREX_WT_D63\sentinel_engine\live\guard_cuenta.py -Force
Copy-Item -LiteralPath C:\FOREX\tests\live\test_guard_cuenta.py -Destination C:\FOREX_WT_D63\tests\live\test_guard_cuenta.py -Force
$acta = 'C:\FOREX\docs\EQUIPO3-SESION-2026-09-24-INSTALACION-REALIZADA.md'
if (Test-Path -LiteralPath $acta) { Copy-Item -LiteralPath $acta -Destination C:\FOREX_WT_D63\docs\ -Force; 'acta 2026-09-24 copiada' } else { 'acta 2026-09-24 NO esta en C:\FOREX\docs (se omite; queda anotado en el acta de hoy)' }
git -C C:\FOREX_WT_D63 status --short
git -C C:\FOREX_WT_D63 diff --numstat
```

**Esperado:** `status` con `M sentinel_engine/live/guard_cuenta.py`, `M tests/live/test_guard_cuenta.py` (+ `?? docs/EQUIPO3-SESION-2026-09-24-…` si había acta);
`--numstat` con **pocas líneas por fichero** (cifras de un solo dígito o pocas decenas).
**STOP si:** `status` muestra algo más; o un fichero cambia en bloque (cientos de líneas = problema de finales de línea; no commitees).

### 1.4 Commit y push (nunca `git add -A`, nunca `-f`)

```powershell
$gn = (git -C C:\FOREX config user.name); $ge = (git -C C:\FOREX config user.email)
$idArgs = @()
if ((-not $gn) -or (-not $ge)) { $idArgs = @('-c', 'user.name=Claude Code equipo3', '-c', 'user.email=noreply@anthropic.com') }
git -C C:\FOREX_WT_D63 add -- sentinel_engine/live/guard_cuenta.py tests/live/test_guard_cuenta.py
if (Test-Path -LiteralPath C:\FOREX_WT_D63\docs\EQUIPO3-SESION-2026-09-24-INSTALACION-REALIZADA.md) { git -C C:\FOREX_WT_D63 add -- docs/EQUIPO3-SESION-2026-09-24-INSTALACION-REALIZADA.md }
git -C C:\FOREX_WT_D63 status --short
git -C C:\FOREX_WT_D63 @idArgs commit -m 'feat(guard): sanciona la DEMO 101744076 (D-63, stack B del equipo 3) y archiva el acta de instalacion 2026-09-24' -m 'Cambio que existia solo en el disco del equipo 3 (spec EQUIPO3-ESTADO-Y-PENDIENTES s5.1). La 101744076 se muda al equipo 1; esto es trazabilidad. No se aplica a equipo3-runner.' -m 'Co-Authored-By: Claude <noreply@anthropic.com>'
git -C C:\FOREX_WT_D63 push origin equipo3-d63
git -C C:\FOREX ls-remote --heads origin equipo3-d63
git -C C:\FOREX_WT_D63 rev-parse HEAD
```

**Esperado:** `status` antes del commit con solo ficheros en verde (`M `/`A `); el push imprime `* [new branch]      equipo3-d63 -> equipo3-d63`;
`ls-remote` y `rev-parse` dan **el mismo SHA**. **Anota ese SHA.**
**STOP si:** el push falla (credenciales, red, rechazo). Si aparece una ventana de login de Git, pide al humano que la complete él;
**nunca** pidas ni guardes un token en el chat. Si el commit falla por identidad, repórtalo (no escribas `git config`).

### 1.5 Retirar el worktree

```powershell
git -C C:\FOREX worktree remove C:\FOREX_WT_D63
git -C C:\FOREX worktree prune
git -C C:\FOREX worktree list
Test-Path C:\FOREX_WT_D63
```

**Esperado:** `worktree list` con una sola línea (`C:/FOREX`); `Test-Path` → `False`. La rama local `equipo3-d63` queda en `C:\FOREX` (inofensiva).
**STOP si:** `worktree remove` protesta por cambios.

### 1.6 Dejar `C:\FOREX` limpio en esos dos ficheros

```powershell
git -C C:\FOREX checkout -- sentinel_engine/live/guard_cuenta.py tests/live/test_guard_cuenta.py
git -C C:\FOREX status --porcelain=v1
```

**Esperado:** solo `?? scripts/live/bars_ingester_console.log` y, si existía, `?? docs/EQUIPO3-SESION-2026-09-24-INSTALACION-REALIZADA.md`
(el acta sigue sin trackear en `C:\FOREX`: ya está salvada en `equipo3-d63`; se deja ahí, no se borra).
**STOP si:** quedan otras entradas.

---

## Fase 2 — Desmontar el stack B (AVA 101744076)

**Por qué:** la 76 se muda al equipo 1. Se apaga **solo** lo que es del stack B, y se hace en este orden para que nada lo
relance mientras se desmonta. Stack A (74) no se toca: se prueba con los PIDs de la fase 0.

**Regla de oro:** `Stop-Process` **por PID** y **solo** de lo identificado abajo. Prohibidos `Stop-ScheduledTask`, `taskkill /IM`,
`Stop-Process -Name`, `Get-Process … | Stop-Process` sin filtro por PID.

### 2.1 Comprobar que AVA sigue intacto antes de empezar

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$s  = Get-Content -Raw -LiteralPath (Join-Path $env:TEMP 'eq3_state.json') | ConvertFrom-Json
$wp = @(Get-CimInstance Win32_Process)
foreach ($k in 'executor', 'supervisor', 'watcher1', 'ingester', 'dashboard', 'terminal1') {
    $r = $s.$k
    if ($null -eq $r) { "SKIP: $k no existia en la fase 0"; continue }
    $m = @($wp | Where-Object { $_.ProcessId -eq $r.Pid })
    Chk (($m.Count -eq 1) -and (([datetime]$r.Created).Ticks -eq $m[0].CreationDate.Ticks)) "$k PID $($r.Pid) sigue siendo el mismo proceso"
}
$nEx = @($wp | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'run_live_20' -and $_.CommandLine -match '--arm' -and $_.CommandLine -match '101744074' }).Count
Chk ($nEx -eq 1) "ejecutores armados de la 101744074: $nEx (debe ser 1)"
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

**Esperado:** `RESULTADO: PASS`. **STOP si:** cualquier `STOP:` (AVA cambió desde la fase 0: informa, no continúes).
*(Este mismo bloque se reutiliza en 2.7, 3.5 y 9.1 con el nombre «bloque INTACTO».)*

### 2.2 Deshabilitar el perfil del stack B (reversible; antes de parar nada)

**Por qué:** si el Programador de tareas relanzara el watchdog antiguo tras matarlo, sin este fichero el stack B queda desactivado y no resucita.

```powershell
$j = 'C:\FOREX\scripts\live\machine_local.ava2.json'
Rename-Item -LiteralPath $j -NewName 'machine_local.ava2.json.disabled'
"existe el original: " + (Test-Path -LiteralPath $j)
"existe .disabled:  " + (Test-Path -LiteralPath ($j + '.disabled'))
```

**Esperado:** `False` y `True`. (El `.disabled` aparecerá como `??` en `git status`: es esperado, **no se commitea**, no contiene secretos.)
**STOP si:** `Rename-Item` falla (p. ej. ya existe el `.disabled`). **No borres el fichero.**

### 2.3 Parar solo el watchdog de AVA (por PID)

**Por qué:** hay que detenerlo para que no relance el stack B mientras se desmonta; el watchdog es un `powershell`, sus hijos (supervisor, ejecutor…) **no** mueren con él.

```powershell
$s = Get-Content -Raw -LiteralPath (Join-Path $env:TEMP 'eq3_state.json') | ConvertFrom-Json
$w = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^powershell(\.exe)?$' -and $_.CommandLine -match 'watchdog_equipo3\.ps1' -and $_.ProcessId -ne $PID })
$w | Select-Object ProcessId, ParentProcessId, CreationDate | Format-Table -AutoSize
"watchdogs encontrados: $($w.Count) | PID esperado (fase 0): $($s.watchdog.Pid)"
if (($w.Count -eq 1) -and ($w[0].ProcessId -eq $s.watchdog.Pid)) {
    Stop-Process -Id $w[0].ProcessId -Force
    Start-Sleep -Seconds 3
    "watchdog PID $($w[0].ProcessId) sigue vivo: " + [bool](Get-Process -Id $w[0].ProcessId -ErrorAction SilentlyContinue)
} else { 'STOP: el watchdog no es el esperado; no se mata nada' }
```

**Esperado:** `watchdogs encontrados: 1`, mismo PID que en la fase 0; `sigue vivo: False`.
**STOP si:** salió la línea `STOP:` (cantidad o PID distintos). Un `lock` obsoleto es normal: el watchdog nuevo dirá «Lockfile rancio … tomo el relevo».

### 2.4 Parar solo el watcher del stack B (por PID)

**Por qué:** el watcher del stack B es el único proceso python propio del stack B (era solo monitorización: sin supervisor ni ejecutor).
Se identifica sin ambigüedad por su `--db data/research_ava2.db` (el del stack A usa `research.db`, que **no** contiene `research_ava2`).

```powershell
$s  = Get-Content -Raw -LiteralPath (Join-Path $env:TEMP 'eq3_state.json') | ConvertFrom-Json
$w2 = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'run_deals_watcher' -and $_.CommandLine -match 'research_ava2\.db' })
$w2 | Select-Object ProcessId, ParentProcessId, ExecutablePath, CommandLine | Format-List
"watchers B encontrados: $($w2.Count) | PID esperado: $($s.watcher2.Pid)"
if (($w2.Count -eq 1) -and ($w2[0].ProcessId -eq $s.watcher2.Pid) -and ($w2[0].ExecutablePath -eq $s.python_exe)) {
    $ppid = $w2[0].ParentProcessId
    Stop-Process -Id $w2[0].ProcessId -Force
    Start-Sleep -Seconds 5
    "watcher B vivo: " + [bool](Get-Process -Id $w2[0].ProcessId -ErrorAction SilentlyContinue)
    $cmdp = Get-CimInstance Win32_Process -Filter "ProcessId=$ppid"
    if ($cmdp) { "AVISO: el padre $ppid sigue vivo: $($cmdp.Name) :: $($cmdp.CommandLine)" } else { "padre $ppid ya no existe" }
} elseif ($w2.Count -eq 0) { 'info: no habia watcher del stack B (ya estaba parado)' }
else { 'STOP: el watcher B no es el esperado; no se mata nada' }
```

**Esperado:** 1 watcher, PID = `watcher2` de la fase 0, mismo `ExecutablePath` que AVA; después `watcher B vivo: False` y el `cmd.exe` padre ya no existe.
**STOP si:** salió `STOP:`; o el padre sigue vivo y es algo distinto de un `cmd.exe` (no lo mates: informa).

### 2.5 Cerrar solo el terminal MT5 #2 (por su `ExecutablePath` exacto)

**Por qué:** `C:\MT5_AVA2` es el terminal de la 76. Se identifica por la ruta que dice el propio perfil deshabilitado (no por nombre). Se cierra con la ventana; solo si no responde, por PID.

```powershell
$s  = Get-Content -Raw -LiteralPath (Join-Path $env:TEMP 'eq3_state.json') | ConvertFrom-Json
$t2 = @(Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" | Where-Object { $_.ExecutablePath -and ($_.ExecutablePath.ToLower() -eq $s.term2_path.ToLower()) })
$t2 | Select-Object ProcessId, ExecutablePath | Format-Table -AutoSize
"terminales #2: $($t2.Count) | ruta: $($s.term2_path) | PID esperado: $($s.terminal2.Pid)"
if (($t2.Count -eq 1) -and ($t2[0].ProcessId -eq $s.terminal2.Pid)) {
    $tpid = $t2[0].ProcessId
    [void](Get-Process -Id $tpid).CloseMainWindow()
    Start-Sleep -Seconds 15
    if (Get-Process -Id $tpid -ErrorAction SilentlyContinue) { 'no cerro con la ventana -> Stop-Process por PID'; Stop-Process -Id $tpid -Force; Start-Sleep -Seconds 3 }
    "terminal #2 vivo: " + [bool](Get-Process -Id $tpid -ErrorAction SilentlyContinue)
} elseif ($t2.Count -eq 0) { 'info: el terminal #2 ya estaba cerrado' }
else { 'STOP: el terminal #2 no es el esperado; no se cierra nada' }
```

**Esperado:** `terminal #2 vivo: False`. **STOP si:** salió `STOP:`.

### 2.6 Autoarranque del stack B (solo lectura)

**Por qué:** la spec dice que el único autoarranque es la tarea `SENTINEL_Watchdog_Equipo3`. Se comprueba que no haya nada propio del stack B.

```powershell
Get-ScheduledTask | ForEach-Object { $t = $_; foreach ($a in $t.Actions) { $txt = "$($a.Execute) $($a.Arguments) $($a.WorkingDirectory)"; if ($txt -match 'ava2|MT5_AVA2') { "HIT tarea: $($t.TaskName) -> $txt" } } }
(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run', 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue | Out-String -Width 400) -split "`n" | Where-Object { $_ -match 'ava2|MT5_AVA2' }
Get-ChildItem ([Environment]::GetFolderPath('Startup')), ([Environment]::GetFolderPath('CommonStartup')) -ErrorAction SilentlyContinue | Select-Object FullName
```

**Esperado:** **sin salida `HIT`** ni líneas de `Run`; la carpeta Inicio no contiene nada de `ava2`/`MT5_AVA2`.
**STOP si:** hay un `HIT` (no lo elimines: informa con el texto; lo decide el humano).

### 2.7 Verificación final de la fase 2 (espera el posible relanzamiento de la tarea)

**Por qué:** el Programador puede relanzar solo el watchdog (reintentos cada minuto). Si lo hace, arranca el **script antiguo** con el stack B ya deshabilitado: es aceptable; la fase 3 lo reemplaza.

```powershell
Start-Sleep -Seconds 75
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^powershell(\.exe)?$' -and $_.CommandLine -match 'watchdog_equipo3\.ps1' -and $_.ProcessId -ne $PID } | Select-Object ProcessId, ParentProcessId, CreationDate | Format-Table -AutoSize
"estado de la tarea: " + (Get-ScheduledTask -TaskName SENTINEL_Watchdog_Equipo3).State
Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 8
Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" | Select-Object ProcessId, ExecutablePath | Format-Table -AutoSize
@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'research_ava2' }).Count
```

Después ejecuta el **bloque INTACTO** (2.1) otra vez.
**Esperado:** o bien ningún watchdog corriendo (la tarea no lo relanzó) o bien uno nuevo (PID distinto) cuyo log dice `stack #2: sin perfil … DESACTIVADO`; un único `terminal64.exe` (`C:\MT5_AVA1\…`); la última cifra `0`; bloque INTACTO en `PASS`.
Anota cuál de los dos casos ocurrió (importa para el acta).
**STOP si:** reaparece cualquier proceso del stack B (watcher `research_ava2` o terminal `C:\MT5_AVA2`); el bloque INTACTO da `STOP:`.

---

## Fase 3 — Actualizar AVA (`git pull`) y reiniciar su watchdog

**Por qué:** el watchdog de AVA en disco es anterior a los parches de aislamiento (arreglos de `Start-Hidden`, `Get-OwnPythonProcs`, mensaje
«stack B deshabilitado»). Sin ellos, los dos watchdogs podrían destruirse entre sí al arrancar el de Capitaria. El pull y el reinicio van **después** de
desmontar el stack B para que el watchdog nuevo ya nazca con un solo stack.

### 3.1 `git pull --ff-only`

```powershell
git -C C:\FOREX pull --ff-only origin equipo3-runner
$head = (git -C C:\FOREX rev-parse HEAD); $tip = (git -C C:\FOREX rev-parse origin/equipo3-runner)
"HEAD=$head"; "tip =$tip"
git -C C:\FOREX merge-base --is-ancestor 76295c0bb974d4302cd3efe9fb57b066f66976d3 HEAD; "contiene el codigo auditado 76295c0: exit=$LASTEXITCODE"
"ficheros cambiados respecto a 76295c0 (solo se admiten docs/):"
git -C C:\FOREX diff --name-only 76295c0bb974d4302cd3efe9fb57b066f66976d3 HEAD
git -C C:\FOREX status --porcelain=v1
```

**Esperado:** fast-forward sin conflicto; `HEAD` = `tip`; `exit=0`; la lista de cambios respecto a `76295c0` vacía o con rutas **solo bajo `docs/`** (este runbook);
`status` con solo untracked (`bars_ingester_console.log`, `machine_local.ava2.json.disabled` y, si existía, el acta 2026-09-24).
**STOP si:** el pull no es fast-forward o hay conflicto; `exit` ≠ 0; el diff incluye cualquier ruta fuera de `docs/`; hay ficheros modificados.

### 3.2 Los parches están en disco

```powershell
$f = 'C:\FOREX\scripts\live\watchdog_' + 'equipo3.ps1'
Select-String -LiteralPath $f -SimpleMatch -Pattern 'stack B deshabilitado (sin machine_local.ava2.json)', 'function Get-OwnPythonProcs' | Select-Object LineNumber, Line
```

**Esperado:** dos coincidencias (≈ líneas 217 y 278). **STOP si:** falta alguna.

### 3.3 Cerrojo de intérprete — **crítico**

**Por qué:** el watchdog nuevo reconoce los procesos vivos de AVA por `ExecutablePath == su intérprete`. Si resolviera otro python distinto del que usa hoy el supervisor,
**no vería** el supervisor/ejecutor vivos, lanzaría un segundo supervisor y **segaría el ejecutor armado de la 74**. Se comprueba **antes** de reiniciarlo.

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$s = Get-Content -Raw -LiteralPath (Join-Path $env:TEMP 'eq3_state.json') | ConvertFrom-Json
$cand = (& py -3.11 -c "import sys; print(sys.executable)" | Select-Object -First 1).ToString().Trim()
Chk (-not (Test-Path 'C:\FOREX\.venv\Scripts\python.exe')) 'sin .venv en C:\FOREX'
Chk ($cand.ToLower() -eq $s.python_exe.ToLower()) "py -3.11 -> $cand | procesos vivos de AVA -> $($s.python_exe)"
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

**Esperado:** `PASS` (ambas rutas iguales, `…\Python311\python.exe`). **STOP si:** difieren: **no reinicies el watchdog.**

### 3.4 Reiniciar el watchdog de AVA (receta + alternativa)

**Por qué:** el Programador puede negarse a lanzar otra instancia mientras haya hijos del anterior vivos; por eso se verifica y, si hace falta, se lanza a mano. **Nunca** `Stop-ScheduledTask`.

```powershell
(Get-Date).ToString('yyyy-MM-dd HH:mm:ss') | Set-Content -LiteralPath (Join-Path $env:TEMP 'eq3_t0.txt') -Encoding ASCII
$w = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^powershell(\.exe)?$' -and $_.CommandLine -match 'watchdog_equipo3\.ps1' -and $_.ProcessId -ne $PID })
"watchdogs vivos ahora: $($w.Count)"
if ($w.Count -gt 1) { 'STOP: hay mas de un watchdog; no se mata nada' }
else {
    foreach ($x in $w) { Stop-Process -Id $x.ProcessId -Force; "parado watchdog PID $($x.ProcessId)" }
    Start-Sleep -Seconds 5
    "estado de la tarea antes de arrancarla: " + (Get-ScheduledTask -TaskName SENTINEL_Watchdog_Equipo3).State
    Start-ScheduledTask -TaskName SENTINEL_Watchdog_Equipo3
    Start-Sleep -Seconds 30
    Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 15
}
```

Ahora decide **leyendo el log** (hora de arranque guardada en `eq3_t0.txt`):

```powershell
$t0  = [datetime](Get-Content -LiteralPath (Join-Path $env:TEMP 'eq3_t0.txt') | Select-Object -First 1)
$all = @(Get-Content -LiteralPath C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 400)
$n = 0
foreach ($l in $all) { if (($l -match '^\[(.{19})\] watchdog_equipo3\.ps1 ARRANCADO') -and (([datetime]$Matches[1]) -ge $t0)) { $n++ } }
"lineas ARRANCADO posteriores al reinicio: $n"
$w = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^powershell(\.exe)?$' -and $_.CommandLine -match 'watchdog_equipo3\.ps1' -and $_.ProcessId -ne $PID })
"watchdogs vivos: $($w.Count)"
```

- Si `n ≥ 1` y hay **1** watchdog vivo → la tarea lo arrancó: pasa a 3.5.
- Si `n = 0` y hay **0** watchdogs (la tarea no lanzó otra instancia) → **alternativa**: lanzarlo directamente (el cerrojo singleton impide duplicados). La ruta va partida a propósito (ver regla B.7):

```powershell
$f = 'C:\FOREX\scripts\live\watchdog_' + 'equipo3.' + 'ps1'
Start-Process -FilePath powershell.exe -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', $f -WorkingDirectory C:\FOREX
Start-Sleep -Seconds 30
Get-Content -LiteralPath C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 12
```

  Si usaste la alternativa, **anótalo como DESVIACIÓN en el acta**: ese watchdog queda como hijo de tu sesión y no bajo la tarea programada, así que podría no sobrevivir al cierre de Claude Code. Díselo al humano (fase 9.5 lo medirá).
- Si `n = 0` y hay watchdog(s) vivo(s) con arranque anterior, o `n ≥ 2` o hay >1 vivos → **STOP** (estado ambiguo).

**STOP si:** tras la alternativa sigue sin aparecer una línea `ARRANCADO` nueva.

### 3.5 Verificar el watchdog nuevo y que AVA no se enteró

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$st  = Get-Content -Raw -LiteralPath (Join-Path $env:TEMP 'eq3_state.json') | ConvertFrom-Json
$t0  = [datetime](Get-Content -LiteralPath (Join-Path $env:TEMP 'eq3_t0.txt') | Select-Object -First 1)
$all = @(Get-Content -LiteralPath C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 400)
$idx = -1
for ($i = 0; $i -lt $all.Count; $i++) { if (($all[$i] -match '^\[(.{19})\] watchdog_equipo3\.ps1 ARRANCADO') -and (([datetime]$Matches[1]) -ge $t0)) { $idx = $i } }
Chk ($idx -ge 0) 'hay un ARRANCADO posterior al reinicio'
if ($idx -ge 0) {
    $new = @($all[$idx..($all.Count - 1)])
    $new
    Chk (@($new | Where-Object { $_ -match ('interprete clavado: ' + [regex]::Escape($st.python_exe)) }).Count -ge 1) "linea 'interprete clavado: $($st.python_exe)'"
    Chk (@($new | Where-Object { $_ -match 'stack #1: terminal=.*login=101744074' }).Count -ge 1) "linea 'stack #1: terminal=… login=101744074'"
    Chk (@($new | Where-Object { $_ -match 'stack B deshabilitado \(sin machine_local\.ava2\.json\)' }).Count -ge 1) "linea 'stack B deshabilitado (sin machine_local.ava2.json)'"
    Chk (@($new | Where-Object { $_ -match 'OK: watcher1=True supervisor=True watcher2=False stack2=False' }).Count -ge 1) "linea periodica 'OK: watcher1=True supervisor=True watcher2=False stack2=False' (si aun no salio, espera 25 s y repite)"
    Chk (@($new | Where-Object { $_ -match 'CAIDO|relanzando|segando|HUERFANO|GUARD DE CUENTA KO|ERROR en el bucle|ME NIEGO A ARRANCAR(?!: ya hay otro)' }).Count -eq 0) 'el watchdog nuevo no relanzo, no sego y no tuvo errores'
}
$wp = @(Get-CimInstance Win32_Process)
Chk (@($wp | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'research_ava2' }).Count -eq 0) 'ningun watcher del stack B'
Chk (@($wp | Where-Object { $_.Name -eq 'terminal64.exe' -and $_.ExecutablePath -and ($_.ExecutablePath.ToLower() -eq $st.term2_path.ToLower()) }).Count -eq 0) 'ningun terminal MT5 #2'
Chk (@($wp | Where-Object { $_.Name -match '^powershell(\.exe)?$' -and $_.CommandLine -match 'watchdog_equipo3\.ps1' -and $_.ProcessId -ne $PID }).Count -eq 1) 'exactamente 1 watchdog de AVA'
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

Ejecuta después el **bloque INTACTO** (2.1).
**Esperado:** `PASS` en ambos. Líneas `ME NIEGO A ARRANCAR: ya hay otro watchdog_equipo3.ps1` posteriores son **benignas** (reintento de la tarea frenado por el cerrojo singleton).
**STOP si:** cualquier `STOP:`. Si el watchdog nuevo relanzó/segó algo, **no toques nada más**: informa con PIDs (puede haber un ejecutor duplicado).

---

## Fase 4 — MT5 de Capitaria (asistida por el humano)

**Por qué:** Capitaria necesita su **propia instalación** de MT5. El instalador de marca guarda `Config\servers.dat` + `Config\terminal.lic`; **copiar la carpeta rompe la instalación**
(se perdió la lista de servidores el 2026-09-24). Método que funciona: instalar de cero con `/auto` y **MOVER** (no copiar) a su destino. El Market Watch **no sobrevive al movimiento**
(el hash de `%APPDATA%\MetaQuotes\Terminal\<hash>` deriva de la ruta): hay que añadir `XAUUSD` **después** de mover (si no: `[FAIL] symbol-tradable: symbol=XAUUSD visible=False`).

**Reglas duras de esta fase:** nunca `Copy-Item -Recurse` de una instalación MT5; nunca `terminal64.exe /login: /password:`; nunca pidas/escribas/guardes la contraseña. Si el humano te la ofrece en el chat, recházala: debe teclearla él en la ventana de MT5.

### 4.1 Precondiciones (solo lectura)

```powershell
"existe C:\MT5_CAPITARIA: " + (Test-Path C:\MT5_CAPITARIA)
Get-ChildItem 'C:\Program Files' -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'terminal64.exe') } | Select-Object -ExpandProperty FullName
Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" | Select-Object ProcessId, ExecutablePath | Format-Table -AutoSize
```

**Esperado:** `False`; la lista de instalaciones puede traer la residual `C:\Program Files\MetaTrader 5` (~375 MB, del intento genérico del 2026-09-24; **no la uses ni la borres**) y **no** debe traer `Capitaria MT5 Terminal`; un solo terminal en ejecución (`C:\MT5_AVA1`).
**STOP si:** `C:\MT5_CAPITARIA` existe, o ya hay una carpeta `Capitaria MT5 Terminal` en Program Files.

### 4.2 Pedir el instalador al humano

El instalador de marca **no tiene URL pública**: se baja del portal de Capitaria con sesión iniciada. Pregunta al humano **la ruta completa del instalador** (p. ej. en Descargas). **Espera su respuesta.** Con la ruta en `$inst`:

```powershell
$inst = 'PEGA_AQUI_LA_RUTA_QUE_DA_EL_HUMANO'
Get-Item -LiteralPath $inst | Select-Object FullName, Length, LastWriteTime
(Get-AuthenticodeSignature -LiteralPath $inst).Status
(Get-FileHash -LiteralPath $inst -Algorithm SHA256).Hash
```

**Esperado:** el fichero existe; anota nombre, tamaño, firma y SHA256 (informativos, para el acta). **STOP si:** no existe. (No lo busques ni lo descargues tú.)

### 4.3 Instalar con `/auto` y localizar la carpeta instalada

```powershell
$inst = 'PEGA_AQUI_LA_RUTA_QUE_DA_EL_HUMANO'
$before = @(Get-ChildItem 'C:\Program Files' -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'terminal64.exe') } | ForEach-Object { $_.FullName })
$pr = Start-Process -FilePath $inst -ArgumentList '/auto' -PassThru
$deadline = (Get-Date).AddMinutes(10)
while (((Get-Date) -lt $deadline) -and (-not $pr.HasExited)) { Start-Sleep -Seconds 5 }
"instalador terminado: $($pr.HasExited)"
if ($pr.HasExited) { "codigo de salida: $($pr.ExitCode)" }
$after = @(Get-ChildItem 'C:\Program Files' -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'terminal64.exe') } | ForEach-Object { $_.FullName })
"instalaciones nuevas:"; @($after | Where-Object { $before -notcontains $_ })
```

Pasa `timeout` = **720000** a la herramienta. **Esperado:** `instalador terminado: True` y **exactamente una** instalación nueva: `C:\Program Files\Capitaria MT5 Terminal` (es la ruta con que operó M2).
**STOP si:** el instalador sigue vivo a los 10 minutos (no lo mates; puede estar esperando un UAC o descargando: avisa al humano); no aparece ninguna carpeta nueva (pide al humano que ejecute el instalador a mano **aceptando la carpeta por defecto** y avísate; no sigas hasta entonces); la carpeta nueva se llama de otro modo.

### 4.4 Cerrar un terminal que el instalador haya abierto (solo de esa ruta) y MOVER

```powershell
Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" | Where-Object { $_.ExecutablePath -like 'C:\Program Files\Capitaria MT5 Terminal\*' } | ForEach-Object { "cerrando terminal recien instalado PID $($_.ProcessId)"; Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 3
Move-Item -LiteralPath 'C:\Program Files\Capitaria MT5 Terminal' -Destination 'C:\MT5_CAPITARIA'
"existe terminal64.exe en el destino: " + (Test-Path C:\MT5_CAPITARIA\terminal64.exe)
"existe la carpeta original: " + (Test-Path 'C:\Program Files\Capitaria MT5 Terminal')
Get-ChildItem C:\MT5_CAPITARIA\Config -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'servers\.dat|terminal\.lic' } | Select-Object Name, Length
```

**Esperado:** `True` y `False`; se ven `servers.dat` y `terminal.lic` (informativo: si faltan, anótalo; la prueba real es el login en 4.6).
**STOP si:** `Move-Item` falla (archivos en uso, permisos).

### 4.5 Arrancar el terminal

**Por qué:** el modo es **no portable** (sin `/portable`), igual que M2 y que `portable=false` del perfil.

```powershell
Start-Process -FilePath 'C:\MT5_CAPITARIA\terminal64.exe'
Start-Sleep -Seconds 12
Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" | Select-Object ProcessId, ExecutablePath | Format-Table -AutoSize
```

**Esperado:** **dos** terminales: `C:\MT5_AVA1\terminal64.exe` (mismo PID de la fase 0) y `C:\MT5_CAPITARIA\terminal64.exe` (nuevo). **STOP si:** hay más de dos, o aparece alguno en una ruta inesperada.

### 4.6 ENTREGA AL HUMANO (detente aquí y espera)

Muestra literalmente al humano este bloque y **espera su respuesta**:

> **Tu turno (MT5 de Capitaria, ventana ya abierta):**
> 1. Inicia sesión con la cuenta **2883016902**, servidor **`Capitaria-All`**, **tecleando tú la contraseña en la ventana de MT5**. Si el diálogo ofrece guardar la información de la cuenta, déjalo marcado (así el terminal reabre la sesión solo cuando el watchdog lo relance).
> 2. `Herramientas → Opciones → Asesores Expertos` → marca **«Permitir trading algorítmico»**.
> 3. Añade **`XAUUSD`** a **Observación de Mercado** (hazlo ahora, después del movimiento de carpeta).
> 4. Confirma en la ventana que la cuenta es **DEMO** y que el saldo es de **≈ 71 MM CLP**.
> 5. Respóndeme con: login hecho (sí/no), DEMO (sí/no), saldo que ves, trading algorítmico activo (sí/no), `XAUUSD` visible en Observación de Mercado (sí/no). **No me pegues la contraseña.**

**Esperado:** cinco «sí» y un saldo ≈ 71 MM CLP. **STOP si:** cualquier «no»; no es DEMO; el servidor `Capitaria-All` no aparece/no conecta; saldo muy distinto de lo esperado.

### 4.7 Comprobación posterior (informativa)

```powershell
Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" | Select-Object ProcessId, ExecutablePath | Format-Table -AutoSize
Get-ChildItem "$env:APPDATA\MetaQuotes\Terminal" -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name, LastWriteTime
```

**Esperado:** los dos terminales siguen en ejecución; aparece una carpeta de datos reciente (la nueva, de `C:\MT5_CAPITARIA`). La confirmación definitiva de login/DEMO la darán el guard del watchdog y el ejecutor en la fase 8.

---

## Fase 5 — Clon de Capitaria e intérprete propio

**Por qué:** dos clones separados (`STOP`, audit log, `research.db`, spread store son rutas fijas por clon) y un **CPython real propio** por clon: es el mecanismo de aislamiento de procesos
(los filtros de ambos watchdogs exigen `ExecutablePath ==` el intérprete propio). **Nada de venv**: su `python.exe` es un redirector que lanza como hijo al Python del sistema, que comparte ruta con AVA.

### 5.1 Clonar

```powershell
"existe C:\FOREX_CAP: " + (Test-Path C:\FOREX_CAP)
$url = (git -C C:\FOREX remote get-url origin)
git clone --branch equipo3-capitaria --single-branch --depth 1 $url C:\FOREX_CAP
"exit: $LASTEXITCODE"
git -C C:\FOREX_CAP rev-parse HEAD
git -C C:\FOREX_CAP status --short --branch
```

**Esperado:** primero `False`; el clon termina con `exit: 0`; `HEAD` = **`91ad3e74b55b594722367a19227027284ccf3308`**; `status` limpio en `## equipo3-capitaria`.
**STOP si:** `C:\FOREX_CAP` ya existe; el clon falla; `HEAD` es otro SHA.

### 5.2 Instalar CPython 3.12.10 (NuGet) y las dependencias fijadas

**Por qué:** M2 corría 3.12.10 (`C:\Program Files\Python312\python.exe`). El paquete NuGet `python` es el CPython oficial, completo y con pip; se descomprime en `C:\FOREX_CAP\_py`. Es idempotente (si `_py` ya es 3.12.10, salta la descarga; si es otra cosa, lo borra y reinstala).
Pasa `timeout` = **900000** (≈ 2-5 min típico).

```powershell
$repo = 'C:\FOREX_CAP'
$py   = "$repo\_py\python.exe"
$ok   = $false
if (Test-Path $py) { $ok = ((& $py -c "import sys; print('%d.%d.%d' % sys.version_info[:3])") -eq '3.12.10') }
if (-not $ok) {
    if (Test-Path "$repo\_py") { Remove-Item -Recurse -Force "$repo\_py" }
    $tmp = Join-Path $env:TEMP 'py312-nuget'
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.nuget.org/api/v2/package/python/3.12.10' -OutFile "$tmp\python.nupkg"
    Copy-Item "$tmp\python.nupkg" "$tmp\python.zip"
    Expand-Archive -Path "$tmp\python.zip" -DestinationPath "$tmp\x"
    Copy-Item -Recurse "$tmp\x\tools" "$repo\_py"
}
& $py -m pip install --disable-pip-version-check --no-warn-script-location -r "$repo\scripts\live\requirements-capitaria.txt"
"pip exit: $LASTEXITCODE"
& $py -c "import sys, MetaTrader5, numpy, pandas, ta, fastapi; print(sys.version); print(sys.executable); print(numpy.__version__, pandas.__version__)"
"import exit: $LASTEXITCODE"
```

**Esperado:** `pip exit: 0`, `import exit: 0` y, en las tres últimas líneas: `3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, …) [MSC v.1943 64 bit (AMD64)]`, `C:\FOREX_CAP\_py\python.exe`, `2.3.3 2.3.3`.
**STOP si:** cualquier `exit` ≠ 0; la versión no es 3.12.10; `sys.executable` no es `C:\FOREX_CAP\_py\python.exe`; la descarga de NuGet falla (red: informa, no uses otro Python).

### 5.3 Comprobar que es CPython real y que las versiones son las fijadas

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$py = 'C:\FOREX_CAP\_py\python.exe'
Chk ((& $py --version) -eq 'Python 3.12.10') "python --version = $(& $py --version)"
Chk (-not (Test-Path 'C:\FOREX_CAP\_py\pyvenv.cfg')) 'no existe pyvenv.cfg junto al interprete (no es un venv)'
$chk = Join-Path $env:TEMP 'cap_pins_check.py'
@'
import sys
import importlib.metadata as m
bad = []
for line in open(sys.argv[1], encoding="utf-8"):
    s = line.split("#")[0].strip()
    if not s or "==" not in s:
        continue
    name, ver = [x.strip() for x in s.split("==", 1)]
    try:
        got = m.version(name)
    except m.PackageNotFoundError:
        got = None
    if got != ver:
        bad.append((name, ver, got))
print("PINS_OK" if not bad else "PINS_MISMATCH %r" % (bad,))
sys.exit(0 if not bad else 1)
'@ | Set-Content -LiteralPath $chk -Encoding ASCII
$o = & $py $chk 'C:\FOREX_CAP\scripts\live\requirements-capitaria.txt'
Chk ($LASTEXITCODE -eq 0) "versiones instaladas = versiones fijadas ($o)"
Chk ((git -C C:\FOREX_CAP status --porcelain=v1 | Measure-Object).Count -eq 0) 'git status de C:\FOREX_CAP limpio (_py/ esta ignorado)'
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

**Esperado:** `PASS`. (Fijadas: MetaTrader5 5.0.5735, numpy 2.3.3, pandas 2.3.3, scipy 1.18.0, PyYAML 6.0.2, ta 0.11.0, streamlit 1.59.2, plotly 6.9.0, altair 6.1.0, fastapi 0.127.0, starlette 0.47.2, uvicorn 0.35.0, anyio 4.9.0, pyarrow 24.0.0, requests 2.32.4, pytest 8.4.1, pytest-asyncio 1.1.0, httpx 0.28.1.)
**STOP si:** cualquier `STOP:`. (pandas/numpy 2.3.3 **no** son los de M2: desvío deliberado documentado en la cabecera de `requirements-capitaria.txt`, porque pandas 3 rompe `lake/tiers.py:87`.)

---

## Fase 6 — Perfil de máquina de Capitaria

**Por qué:** `machine_profile.load_profile()` lee `scripts\live\machine_local.json` **de este clon**; sin él caería a los valores de la máquina 1 (terminal portable, login 2883015767) y el guard lo rechazaría todo.
El fichero está ignorado por git y **no se commitea nunca**. El login solo *selecciona* un miembro del conjunto sancionado de `guard_cuenta` (que ya incluye 2883016902 en esta rama).

> **Aviso:** la plantilla `machine_local.capitaria.example.json` de la rama trae `"terminal_path": "C:\MT5_CAPITARIA\terminal64.exe"` con **una sola barra invertida**, que **no es JSON válido** (`\M`, `\t`). **No la copies tal cual:** usa el JSON literal de abajo (barras dobles).
> La escritura va en **ASCII** a propósito: un BOM UTF-8 rompe `json.loads`.

```powershell
$json = @'
{
  "terminal_path": "C:\\MT5_CAPITARIA\\terminal64.exe",
  "portable": false,
  "demo_login": 2883016902,
  "terminal_marker": "mt5_capitaria"
}
'@
Set-Content -LiteralPath C:\FOREX_CAP\scripts\live\machine_local.json -Value $json -Encoding ASCII
Get-Content -LiteralPath C:\FOREX_CAP\scripts\live\machine_local.json
Set-Location C:\FOREX_CAP
& C:\FOREX_CAP\_py\python.exe -c "from sentinel_engine.live.machine_profile import load_profile; p = load_profile(); print(p.terminal_path, p.portable, p.demo_login, p.terminal_marker)"
"exit: $LASTEXITCODE"
git -C C:\FOREX_CAP check-ignore -v scripts/live/machine_local.json
git -C C:\FOREX_CAP status --porcelain=v1
"marker == carpeta del exe en minusculas: " + ((Split-Path (Split-Path 'C:\MT5_CAPITARIA\terminal64.exe' -Parent) -Leaf).ToLower() -eq 'mt5_capitaria')
```

(El cierre `'@` debe ir **en la columna 0**, sin sangría.)
**Esperado:** el `print` da `C:\MT5_CAPITARIA\terminal64.exe False 2883016902 mt5_capitaria` y `exit: 0`; `check-ignore` cita la regla `.gitignore:…:scripts/live/machine_local.json`; `git status` sin salida; última línea `True`.
**STOP si:** `MachineProfileError` o cualquier traza; el fichero no está ignorado; `git status` lo muestra. **Nunca** lo añadas a git.

---

## Fase 7 — Entorno limpio, tests y compuerta de reloj

### 7.1 Entorno limpio

**Por qué:** una variable `SUPERVISOR_*` o `SENTINEL_MACHINE_PROFILE` persistida se aplicaría a **los dos stacks** (p. ej. `SUPERVISOR_MAX_SPREAD_OPEN=0.5` bloquearía el 100 % de las aperturas de AVA sin un solo error) y falsea pytest. **Jamás `setx`.**

```powershell
$bad = @()
foreach ($scope in 'User', 'Machine') {
    $d = [Environment]::GetEnvironmentVariables($scope)
    foreach ($k in $d.Keys) { if ($k -match '^(SUPERVISOR_|SENTINEL_MACHINE_PROFILE$)') { $bad += "$scope $k=$($d[$k])" } }
}
foreach ($e in (Get-ChildItem Env:)) { if ($e.Name -match '^(SUPERVISOR_|SENTINEL_MACHINE_PROFILE$)') { $bad += "Process $($e.Name)=$($e.Value)" } }
if ($bad.Count -eq 0) { 'OK: sin SUPERVISOR_* ni SENTINEL_MACHINE_PROFILE (User / Machine / Process)' } else { $bad | ForEach-Object { "STOP: $_" } }
```

**Esperado:** la línea `OK:`. **STOP si:** sale cualquier `STOP:` (no borres variables por tu cuenta: informa; el humano decide).

### 7.2 Instantánea previa, perfil aparcado y lanzamiento de pytest

**Por qué:** la lista de fallos aceptables se midió en un clon limpio **sin** `machine_local.json` y con el intérprete `_py`. Para repetir exactamente esa línea base se aparca el perfil fuera del repo durante la prueba y se comprueba después que pytest no ensució el clon vivo.

```powershell
git -C C:\FOREX_CAP status --porcelain=v1 --ignored | Where-Object { $_ -notmatch '__pycache__' } | Set-Content -LiteralPath (Join-Path $env:TEMP 'cap_status_before.txt') -Encoding ASCII
Move-Item -LiteralPath C:\FOREX_CAP\scripts\live\machine_local.json -Destination (Join-Path $env:TEMP 'machine_local.cap.json')
"perfil aparcado; en el repo: " + (Test-Path C:\FOREX_CAP\scripts\live\machine_local.json)
$py  = 'C:\FOREX_CAP\_py\python.exe'
$out = Join-Path $env:TEMP 'pytest_cap.out'
$err = Join-Path $env:TEMP 'pytest_cap.err'
$pr = Start-Process -FilePath $py -ArgumentList '-m pytest tests -q -m "not slow" -p no:cacheprovider' -WorkingDirectory 'C:\FOREX_CAP' -RedirectStandardOutput $out -RedirectStandardError $err -Wait -PassThru -NoNewWindow
"pytest exit: $($pr.ExitCode)"
Get-Content -LiteralPath $out -Tail 3
```

**La suite tardó 8 min 40 s en una máquina rápida; esta es más lenta.** Lanza **solo este bloque** con la herramienta en **segundo plano** (`run_in_background: true`, `timeout` = **1800000**), no hagas nada más mientras corre y espera la notificación de fin. Si tu herramienta no admite segundo plano, divide la suite (`tests\live`, `tests\opt tests\scripts`, el resto) con el mismo comando y junta los `FAILED`.
**Esperado:** `pytest exit: 1` (hay fallos aceptables) y, en la última línea, algo como `13 failed, 1967 passed, 17 skipped, 1 deselected, 1 warning in …`.
**STOP si:** pytest no termina; hay `error` de recolección.

### 7.3 Restaurar el perfil y evaluar los resultados

```powershell
Move-Item -LiteralPath (Join-Path $env:TEMP 'machine_local.cap.json') -Destination C:\FOREX_CAP\scripts\live\machine_local.json
"perfil restaurado: " + (Test-Path C:\FOREX_CAP\scripts\live\machine_local.json)
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$txt = @(Get-Content -LiteralPath (Join-Path $env:TEMP 'pytest_cap.out'))
$allowed = @(
 'tests/opt/test_fast_replay.py::test_oracle_equivalence_and_ranking_and_speed',
 'tests/opt/test_fast_replay.py::test_indicator_levers_move_score_and_stay_bit_exact',
 'tests/opt/test_fast_replay.py::test_determinism',
 'tests/opt/test_fast_replay.py::test_cache_correctness',
 'tests/opt/test_fast_replay.py::test_plateau_like_speed_evidence',
 'tests/opt/test_study.py::test_safety_invariant_no_instrument_config_modified',
 'tests/opt/test_study.py::test_fast_smoke_study_minimal',
 'tests/opt/test_study.py::test_parallel_matches_serial_determinism',
 'tests/opt/test_study.py::test_fleet_end_to_end_matches_standalone_studies',
 'tests/scripts/test_gen_v10_completion.py::test_lake_feasibility_matrix_marks_missing_windows',
 'tests/service/test_chat.py::test_review_strategy_happy_path_sse_sequence',
 'tests/service/test_web_positions.py::test_positions_js_humano_panel_has_analizar_button_disabled_with_tooltip',
 'tests/service/test_web_positions.py::test_positions_js_analizar_button_no_longer_hard_disabled')
$failed = @()
foreach ($l in $txt) { if ($l -match '^FAILED (\S+)') { $failed += $Matches[1] } }
$unexpected = @($failed | Where-Object { $allowed -notcontains $_ })
$errs = @($txt | Where-Object { $_ -match '^ERROR ' })
"resumen: " + ($txt | Select-Object -Last 1)
"fallos totales: $($failed.Count) | aceptables: $($allowed.Count)"
Chk ($unexpected.Count -eq 0) "ningun fallo fuera de la lista aceptable $(if ($unexpected.Count) { '-> ' + ($unexpected -join ' ; ') })"
Chk ($errs.Count -eq 0) "sin errores de recoleccion/ejecucion (lineas ERROR: $($errs.Count))"
Chk (@($txt | Where-Object { $_ -match '\d+ passed' }).Count -ge 1) 'hay linea final de resumen con tests pasados'
$before = @(Get-Content -LiteralPath (Join-Path $env:TEMP 'cap_status_before.txt'))
$after  = @(git -C C:\FOREX_CAP status --porcelain=v1 --ignored | Where-Object { $_ -notmatch '__pycache__' })
$diff   = @(Compare-Object $before $after | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" })
$diff
Chk (@($diff | Where-Object { $_ -match 'data/|scripts/live/' }).Count -eq 0) 'pytest no creo ficheros en data/ ni scripts/live/ del clon vivo'
Chk (-not (Test-Path C:\FOREX_CAP\scripts\live\STOP)) 'no hay fichero STOP en el clon'
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

**Esperado:** `PASS`. Los **únicos fallos aceptables son estos 13** (todos medidos en la línea base): 10 porque el *lake* real de barras no viaja en el clon
(`tests/opt/test_fast_replay.py` ×5, `tests/opt/test_study.py` ×4, `tests/scripts/test_gen_v10_completion.py::test_lake_feasibility_matrix_marks_missing_windows`) y 3 preexistentes
(`tests/service/test_chat.py::test_review_strategy_happy_path_sse_sequence`, `tests/service/test_web_positions.py` ×2). Cifras de la línea base: `13 failed, 1967 passed, 17 skipped, 1 deselected`;
si el recuento de pasados difiere ligeramente pero **todo fallo está en la lista**, no es STOP (anótalo).
**STOP si:** cualquier fallo fuera de la lista, cualquier `ERROR`, o pytest ensució `data/`/`scripts/live/`.
**Pase lo que pase, el perfil debe quedar restaurado** (la primera línea del bloque): si el bloque se interrumpe, restáuralo antes de informar.

### 7.4 Compuerta de reloj — **antes de arrancar nada que pueda operar**

**Por qué:** `SUPERVISOR_BLOCKED_OPEN_WINDOW=18:00-18:45` se compara con el reloj **LOCAL** de esta máquina (`run_live_20._local_now()` = `datetime.now()`, naive), no con la hora del servidor MT5.
El código y M2 dan por hecho que *reloj local = reloj del servidor de Capitaria = UTC−4* (en M2: log de ejecutor con hora local 18:52 sobre una barra etiquetada 18:30; comentarios del código «both UTC-4»).
Esa igualdad solo vale con offset local `-04:00` (Chile en horario estándar, p. ej. julio-agosto, cuando operó M2). Con Chile en horario de verano (`-03:00`, como hoy) la ventana caería **una hora antes** del reinicio real del mercado (cubriría 17:00-17:45 del servidor y dejaría **sin proteger** las velas con gap de apertura 18:00-18:45 del servidor).

```powershell
$tz  = Get-TimeZone
$off = $tz.GetUtcOffset((Get-Date))
"zona=$($tz.Id) | $($tz.DisplayName) | offset_ahora=$off | base=$($tz.BaseUtcOffset) | horario_verano=$($tz.IsDaylightSavingTime((Get-Date)))"
if ($off.TotalHours -eq -4) { 'OK:   offset local -04:00 = el de M2 (reloj local == reloj del servidor, UTC-4); la ventana 18:00-18:45 significa lo mismo que en M2' }
else { "STOP: offset local $off distinto de -04:00 (el de M2). NO cambies la ventana ni el entorno. Informa al humano: debe decidir (aceptar el riesgo, esperar al horario estandar o cambiar la ventana por una via autorizada)." }
```

**Esperado hoy según el acta del 2026-09-24:** offset `-03:00` ⇒ sale **STOP**.
**STOP si:** el offset no es `-04:00`. En ese caso **no pases a la fase 8**: no se registra la tarea ni se arranca el stack de Capitaria. Informa (incluye la salida literal). El humano decide; **tú no cambias** `18:00-18:45` ni ningún entorno. (Lo ya hecho —MT5, clon, intérprete, perfil, tests— queda reutilizable.)

---

## Fase 8 — Autoarranque de Capitaria y arranque del stack

**Por qué:** `setup_autostart_capitaria.ps1` registra la tarea `SENTINEL_Watchdog_Capitaria` (al iniciar sesión, oculta, reinicio ante fallo, sin caducidad) tras cuatro cerrojos
(intérprete propio real, carpeta distinta de AVA, perfil presente, sin variables persistidas). No hace `setx` ni toca energía. El watchdog de Capitaria mantiene vivos terminal, watcher, supervisor y dashboard :8502,
inyectando por proceso el entorno exacto de M2 (`SUPERVISOR_CONFIGS=tomachine`, `SUPERVISOR_MAX_SPREAD_OPEN=0.5`, `SUPERVISOR_BLOCKED_OPEN_WINDOW=18:00-18:45`, `SUPERVISOR_NO_ADAPTIVE_SPREAD=1`).
Solo se llega aquí si 7.4 dio OK (o si el humano, tras un STOP de 7.4, ordenó explícitamente continuar).

### 8.1 Registrar la tarea

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\FOREX_CAP\scripts\live\setup_autostart_capitaria.ps1
"exit: $LASTEXITCODE"
```

**Esperado:** secciones `Cerrojo 1…4` con `OK:` —
`OK: interprete propio en C:\FOREX_CAP\_py\python.exe (Python 3.12.10)`;
`OK: el stack AVA vive en 'C:\FOREX', distinto de este clon.`;
`OK: machine_local.json -> demo_login=2883016902 terminal=C:\MT5_CAPITARIA\terminal64.exe`;
`OK: ninguna variable persistida.` — luego `Tarea 'SENTINEL_Watchdog_Capitaria' registrada …`, `OK.` y `exit: 0`.
**STOP si:** aparece `ME NIEGO`, `ERROR`, `FATAL` o `exit` ≠ 0.

### 8.2 La tarea de Capitaria existe y la de AVA no se tocó

```powershell
Get-ScheduledTask -TaskName SENTINEL_Watchdog_Capitaria, SENTINEL_Watchdog_Equipo3 | Select-Object TaskName, State | Format-Table -AutoSize
(Get-ScheduledTask -TaskName SENTINEL_Watchdog_Capitaria).Actions | Select-Object Execute, Arguments, WorkingDirectory | Format-List
(Get-ScheduledTask -TaskName SENTINEL_Watchdog_Capitaria).Principal | Select-Object RunLevel, LogonType | Format-List
```

**Esperado:** Capitaria `Ready`, AVA `Running`; la acción apunta a `…\watchdog_capitaria.ps1` con `WorkingDirectory C:\FOREX_CAP`; `RunLevel Highest`, `LogonType Interactive`.
**STOP si:** otra cosa.

### 8.3 Arrancar la tarea y esperar a que el stack se levante

```powershell
Start-ScheduledTask -TaskName SENTINEL_Watchdog_Capitaria
$log = 'C:\FOREX_CAP\scripts\live\watchdog_capitaria.log'
$deadline = (Get-Date).AddMinutes(4)
$ready = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 10
    if (Test-Path -LiteralPath $log) { if (@(Get-Content -LiteralPath $log | Where-Object { $_ -match 'supervisor relanzado, PID \d+' }).Count -ge 1) { $ready = $true; break } }
}
"supervisor lanzado dentro del plazo: $ready"
Get-Content -LiteralPath $log -Tail 40
```

**Esperado:** `True` y un log con, en este orden aproximado: `watchdog_capitaria.ps1 ARRANCADO (PID n). Sondeo cada 20s. Repo: C:\FOREX_CAP`;
`interprete: C:\FOREX_CAP\_py\python.exe (Python 3.12)`; `perfil: terminal=C:\MT5_CAPITARIA\terminal64.exe portable=False demo_login=2883016902`;
`guard OK: DEMO 2883016902 confirmada.`; `watcher CAIDO -- relanzando.` / `watcher relanzado, PID n.`; `supervisor CAIDO -- relanzando (roster tomachine, XAUUSD, cap 0.50, ventana 18:00-18:45, gate adaptativo OFF).` / `supervisor relanzado, PID n.`;
`dashboard CAIDO (nadie escucha en 8502) -- relanzando.` / `dashboard relanzado, PID n.`; luego líneas `OK: watcher=True supervisor=True dashboard=True STOP=False`.
**STOP si:** `False` (pasaron 4 min); aparece `ME NIEGO A ARRANCAR`; `GUARD DE CUENTA KO` / `esperando confirmacion de cuenta…` se repite más de 3 minutos (el terminal no está logueado en la 2883016902 o no responde: informa con las líneas); `ERROR en el bucle del watchdog`; el terminal no se detecta.

### 8.4 Verificación del log + procesos propios

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$log = Get-Content -LiteralPath C:\FOREX_CAP\scripts\live\watchdog_capitaria.log
function Has([string]$rx) { return (@($log | Where-Object { $_ -match $rx }).Count -ge 1) }
Chk (Has 'watchdog_capitaria\.ps1 ARRANCADO \(PID \d+\)') 'ARRANCADO'
Chk (Has 'interprete: C:\\FOREX_CAP\\_py\\python\.exe \(Python 3\.12\)') 'interprete: C:\FOREX_CAP\_py\python.exe (Python 3.12)'
Chk (-not (Has 'AVISO: el interprete no es Python 3\.12')) 'sin AVISO de interprete'
Chk (Has 'perfil: terminal=C:\\MT5_CAPITARIA\\terminal64\.exe portable=False demo_login=2883016902') 'perfil terminal/portable/login'
Chk (Has 'guard OK: DEMO 2883016902 confirmada') 'guard de cuenta: DEMO 2883016902 confirmada'
Chk (-not (Has 'ME NIEGO A ARRANCAR|ERROR en el bucle|segando ejecutor HUERFANO')) 'sin negativas, errores ni siega de huerfanos'
$cap = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.ExecutablePath -and ($_.ExecutablePath.ToLower() -eq 'c:\forex_cap\_py\python.exe') })
$cap | Select-Object ProcessId, ParentProcessId, ExecutablePath, CommandLine | Format-List
function CapHas([string]$rx) { return (@($cap | Where-Object { $_.CommandLine -match $rx }).Count) }
Chk ((CapHas 'run_deals_watcher') -eq 1) 'watcher Capitaria: 1 (exe C:\FOREX_CAP\_py\python.exe)'
Chk ((CapHas 'supervisor_live') -eq 1) 'supervisor Capitaria: 1'
Chk ((CapHas 'run_service\.py.*--port 8502') -eq 1) 'dashboard Capitaria en 8502: 1'
$otros = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'FOREX_CAP' -and (-not $_.ExecutablePath -or $_.ExecutablePath.ToLower() -ne 'c:\forex_cap\_py\python.exe') })
Chk ($otros.Count -eq 0) 'ningun python con FOREX_CAP en la linea de comandos corre sobre otro ejecutable'
"info: ejecutores Capitaria visibles ahora = $(CapHas 'run_live_20') | ingester Capitaria = $(CapHas 'run_bars_ingester') (0 esperado: lo cubre el de AVA)"
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

**Esperado:** `PASS`. El watcher y el dashboard llevan `-X sentinel_stack=capitaria` tras el exe (marca de defensa); el ejecutor y el ingester que lance el supervisor no la llevan pero comparten el exe `_py`.
**STOP si:** cualquier `STOP:`.

### 8.5 Preflight, ejecutor armado y enganche a la 2883016902 (por los logs propios del stack)

**Por qué:** la confirmación de que el ejecutor se enganchó a la cuenta correcta sale del propio ejecutor (`connected + guard OK`) y del guard del watchdog; no se hace ninguna llamada ad-hoc a MT5.
(`verify_two_terminals.py` **no** se usa: solo existe en la rama de AVA, tiene `GOLD` fijo y haría `initialize()` contra el terminal vivo de la 74.)

```powershell
$deadline = (Get-Date).AddMinutes(10)
$wl = 'C:\FOREX_CAP\scripts\live\watchdog.log'
$al = 'C:\FOREX_CAP\scripts\live\run_live_20.audit.log'
$pass = $false; $conn = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 15
    if (Test-Path -LiteralPath $wl) { $pass = (@(Get-Content -LiteralPath $wl | Where-Object { $_ -match 'preflight PASS' }).Count -ge 1) }
    if (Test-Path -LiteralPath $al) { $conn = (@(Get-Content -LiteralPath $al -Tail 300 | Where-Object { $_ -match 'connected \+ guard OK: DEMO login 2883016902' }).Count -ge 1) }
    if ($pass -and $conn) { break }
}
"preflight PASS: $pass | ejecutor conectado a 2883016902: $conn"
if (Test-Path -LiteralPath $wl) { Get-Content -LiteralPath $wl | Where-Object { $_ -match 'preflight|launching executor|FAIL' } | Select-Object -Last 15 }
if (Test-Path -LiteralPath $al) { Get-Content -LiteralPath $al -Tail 300 | Where-Object { $_ -match 'connected \+ guard OK' } | Select-Object -Last 2 }
```

**Esperado:** `True | True`; en `watchdog.log` aparece
`launching executor: C:\FOREX_CAP\_py\python.exe -m scripts.live.run_live_20 --arm --confirm-account 2883016902 --configs tomachine --max-spread-open 0.5 --blocked-open-window 18:00-18:45 --no-adaptive-spread`
(exactamente esos argumentos: son los de M2) y en el audit log
`connected + guard OK: DEMO login 2883016902 (dry_run=False, 2 configs, window=10000, max_spread_open=0.5, adaptive_spread=OFF eps=n/a, blocked_open_window=18:00-18:45)`.
**STOP si:** al cabo de 10 min no hay `preflight PASS` (informa las últimas líneas de `watchdog.log`; si dice `symbol-tradable: symbol=XAUUSD visible=False`, falta añadir `XAUUSD` a Observación de Mercado: pide al humano que lo haga, **tú no lo arreglas**);
los argumentos del ejecutor difieren de los de M2; el login del ejecutor no es 2883016902. Un `SPREAD_GATE_SKIP` o cero aperturas no son STOP.

---

## Fase 9 — Verificación cruzada de aislamiento

**Por qué:** el objetivo no es solo que Capitaria corra, sino que **ninguno de los dos stacks vea ni toque al otro**.

### 9.1 AVA intacto desde la fase 0

Ejecuta el **bloque INTACTO** (2.1). **Esperado:** `PASS` (ejecutor, supervisor, watcher A, ingester, dashboard y terminal A con los mismos PIDs y horas de creación que en la fase 0; un solo ejecutor armado de la 101744074).
**STOP si:** cualquier `STOP:`.

### 9.2 Cada log sin acciones contra el otro stack

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$t0  = [datetime](Get-Content -LiteralPath (Join-Path $env:TEMP 'eq3_t0.txt') | Select-Object -First 1)
$ava = @(Get-Content -LiteralPath C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 600 | Where-Object { ($_ -match '^\[(.{19})\]') -and (([datetime]$Matches[1]) -ge $t0) })
$cap = @(Get-Content -LiteralPath C:\FOREX_CAP\scripts\live\watchdog_capitaria.log)
"lineas AVA desde el reinicio: $($ava.Count) | lineas Capitaria: $($cap.Count)"
Chk (@($ava | Where-Object { $_ -match 'segando|HUERFANO|relanzando|CAIDO|GUARD DE CUENTA KO|ERROR en el bucle' }).Count -eq 0) 'AVA: sin siega ni relanzamientos desde el reinicio'
Chk (@($ava | Where-Object { $_ -match 'FOREX_CAP|MT5_CAPITARIA|capitaria|2883016902' }).Count -eq 0) 'AVA: ninguna mencion a Capitaria'
Chk (@($cap | Where-Object { $_ -match 'segando|HUERFANO' }).Count -eq 0) 'Capitaria: sin siega de huerfanos'
Chk (@($cap | Where-Object { $_ -match 'C:\\FOREX(?!_CAP)|MT5_AVA|101744074|101744076' }).Count -eq 0) 'Capitaria: ninguna mencion a AVA'
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

**Esperado:** `PASS` (los `relanzando` de Capitaria de la fase 8.3 son legítimos y por eso solo se vigila `segando|HUERFANO` allí).
**STOP si:** cualquier `STOP:`.

### 9.3 Procesos por ejecutable, terminales y dashboards

```powershell
$global:bad = 0
function Chk([bool]$ok, [string]$msg) { if ($ok) { "OK:   $msg" } else { "STOP: $msg"; $global:bad++ } }
$st = Get-Content -Raw -LiteralPath (Join-Path $env:TEMP 'eq3_state.json') | ConvertFrom-Json
$wp = @(Get-CimInstance Win32_Process)
"python por ejecutable:"
$wp | Where-Object { $_.Name -match '^pythonw?\.exe$' } | Group-Object ExecutablePath | Select-Object Count, Name | Format-Table -AutoSize
$trm = @($wp | Where-Object { $_.Name -eq 'terminal64.exe' })
$trm | Select-Object ProcessId, ExecutablePath | Format-Table -AutoSize
Chk ($trm.Count -eq 2) "exactamente 2 terminales (hay $($trm.Count))"
Chk (@($trm | Where-Object { $_.ExecutablePath.ToLower() -eq $st.term1_path.ToLower() }).Count -eq 1) "terminal AVA 74: $($st.term1_path)"
Chk (@($trm | Where-Object { $_.ExecutablePath.ToLower() -eq 'c:\mt5_capitaria\terminal64.exe' }).Count -eq 1) 'terminal Capitaria: C:\MT5_CAPITARIA\terminal64.exe'
Chk (@($trm | Where-Object { $_.ExecutablePath.ToLower() -eq $st.term2_path.ToLower() }).Count -eq 0) 'terminal de la 76 cerrado'
Chk (@($wp | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'research_ava2' }).Count -eq 0) 'sin watcher del stack B'
$allPy = @($wp | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'scripts\.live|run_service|supervisor_live|run_live_20' })
$bad2 = @($allPy | Where-Object { $_.ExecutablePath -and ($_.ExecutablePath.ToLower() -ne $st.python_exe.ToLower()) -and ($_.ExecutablePath.ToLower() -ne 'c:\forex_cap\_py\python.exe') })
Chk ($bad2.Count -eq 0) 'todo python del stack corre sobre el exe de AVA o sobre _py (ninguno mezclado)'
foreach ($port in 8501, 8502) {
    $c = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    Chk ($c.Count -ge 1) "puerto $port escuchando"
    if ($c.Count -ge 1) {
        $o = $wp | Where-Object { $_.ProcessId -eq $c[0].OwningProcess }
        $esperado = if ($port -eq 8501) { $st.python_exe } else { 'C:\FOREX_CAP\_py\python.exe' }
        Chk ($o -and ($o.ExecutablePath.ToLower() -eq $esperado.ToLower())) "el dueno del puerto $port es $esperado (PID $($c[0].OwningProcess))"
        try { $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/" -TimeoutSec 20; "info: http://127.0.0.1:$port/ -> $($r.StatusCode)" } catch { "info: http://127.0.0.1:$port/ -> $($_.Exception.Message)" }
    }
}
if ($global:bad -eq 0) { 'RESULTADO: PASS' } else { "RESULTADO: STOP ($global:bad)" }
```

**Esperado:** `PASS`; dos terminales; el 8501 lo posee un python de AVA y el 8502 uno de `_py`; las peticiones HTTP dan `200` (si responden otra cosa pero el puerto escucha con el dueño correcto, anótalo; no es STOP).
**STOP si:** cualquier `STOP:`. (Si el dashboard de AVA no estuviera levantado, no lo arregles: informa.)

### 9.4 Magics por stack (si ya hubo aperturas)

```powershell
"AVA magics (esperado solo 727011/727021):"
Get-Content -LiteralPath C:\FOREX\scripts\live\run_live_20.audit.log -Tail 20000 | ForEach-Object { if ($_ -match 'magic=(\d+)') { $Matches[1] } } | Sort-Object -Unique
"Capitaria magics (esperado solo 724011/724071, o ninguno si aun no hubo aperturas):"
Get-Content -LiteralPath C:\FOREX_CAP\scripts\live\run_live_20.audit.log -Tail 20000 | ForEach-Object { if ($_ -match 'magic=(\d+)') { $Matches[1] } } | Sort-Object -Unique
```

**Esperado:** AVA solo `727…`; Capitaria solo `724011`/`724071` o ninguno. **STOP si:** aparece un magic `724…` en AVA o `727…` en Capitaria. (Cero aperturas hoy no es un fallo.)

### 9.5 Quién es el padre de cada watchdog y estado de las tareas

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^powershell(\.exe)?$' -and ($_.CommandLine -match 'watchdog_equipo3\.ps1' -or $_.CommandLine -match 'watchdog_capitaria\.ps1') -and $_.ProcessId -ne $PID } | ForEach-Object {
    $pp = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.ParentProcessId)"
    "{0} PID {1} <- padre {2} ({3})" -f ($(if ($_.CommandLine -match 'capitaria') { 'watchdog Capitaria' } else { 'watchdog AVA' })), $_.ProcessId, $_.ParentProcessId, $(if ($pp) { $pp.Name } else { 'ya no existe' })
}
Get-ScheduledTask -TaskName SENTINEL_Watchdog_Capitaria, SENTINEL_Watchdog_Equipo3 | Select-Object TaskName, State | Format-Table -AutoSize
```

**Esperado:** un watchdog de cada; padre `svchost.exe`/`taskeng.exe` (lanzados por la tarea); tareas `Running`. Si el watchdog de AVA tiene como padre tu sesión (Claude Code/powershell), es la **alternativa** de 3.4: anótalo como desviación y avisa al humano.
**STOP si:** falta alguno de los dos watchdogs.

### 9.6 Prueba de resiliencia (OPCIONAL, solo Capitaria, solo el dashboard)

**Por qué:** demuestra que el auto-sanado de Capitaria funciona. Se mata **únicamente el dashboard de Capitaria, por PID**. **Jamás** se hace esto con el ejecutor, el supervisor ni nada de AVA.

```powershell
$d = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.ExecutablePath -and ($_.ExecutablePath.ToLower() -eq 'c:\forex_cap\_py\python.exe') -and $_.CommandLine -match 'run_service\.py' })
"dashboards Capitaria: $($d.Count)"
if ($d.Count -eq 1) {
    $old = $d[0].ProcessId
    Stop-Process -Id $old -Force
    $new = $null; $deadline = (Get-Date).AddSeconds(90)
    while (((Get-Date) -lt $deadline) -and (-not $new)) {
        Start-Sleep -Seconds 5
        $n = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.ExecutablePath -and ($_.ExecutablePath.ToLower() -eq 'c:\forex_cap\_py\python.exe') -and $_.CommandLine -match 'run_service\.py' })
        if (($n.Count -eq 1) -and ($n[0].ProcessId -ne $old)) { $new = $n[0].ProcessId }
    }
    "dashboard viejo PID $old -> nuevo PID $new"
    Get-Content -LiteralPath C:\FOREX_CAP\scripts\live\watchdog_capitaria.log -Tail 6
} else { 'STOP: no hay exactamente un dashboard de Capitaria; no se mata nada' }
```

Después ejecuta el **bloque INTACTO** (2.1).
**Esperado:** nuevo PID en menos de 90 s, log con `dashboard CAIDO (nadie escucha en 8502) -- relanzando.` y `dashboard relanzado, PID n.`; bloque INTACTO en `PASS`.
**STOP si:** no reaparece; o AVA cambió.

---

## Fase 10 — Acta y entrega

**Por qué:** que quede por escrito qué se hizo, con qué SHAs y PIDs, y con las desviaciones. El acta se sube a la rama `equipo3-actas` mediante un `git worktree` (nunca un commit sobre `C:\FOREX`).

### 10.1 Redactar el acta

Se redacta directamente en el worktree del paso 10.3 (no en `C:\FOREX`). Contenido obligatorio de `docs/EQUIPO3-SESION-2026-10-06-CAPITARIA.md` (Markdown, español):

1. **Resultado** (una frase: qué quedó corriendo y qué no) y, si hubo STOP, en qué paso y por qué.
2. **Estado por fase** (tabla fase → PASS/STOP/omitida, con una nota).
3. **SHAs:** `HEAD` de `C:\FOREX` antes y después; `HEAD` de `C:\FOREX_CAP`; SHA de `equipo3-d63`; SHA del commit del acta.
4. **PIDs de AVA** (fase 0 vs fase 9: ejecutor, supervisor, watcher A, ingester, dashboard, terminal A) y los PIDs nuevos de Capitaria (watchdog, watcher, supervisor, ejecutor, dashboard, terminal).
5. **Resumen de la salida de cada verificación** (las líneas `OK:`/`STOP:` clave, no volcados enteros): log de ambos watchdogs, `launching executor`, `connected + guard OK`, pins, pytest (recuento y lista de fallos).
6. **Reloj:** zona, offset local, y el resultado de la compuerta 7.4.
7. **Desviaciones** respecto de este runbook (p. ej. alternativa de 3.4, acta 2026-09-24 ausente, instalador distinto) y **problemas abiertos**.
8. **Residuos:** `machine_local.ava2.json.disabled`, `data/research_ava2.db` (no borrados), `C:\Program Files\MetaTrader 5` residual, `bars_ingester_console.log` sin ignorar.

**Prohibido en el acta:** contraseñas, tokens, contenido de `CUENTAS.md`, volcados de `machine_local*.json` (puedes citar login y rutas, que ya son públicos en la spec).

### 10.2 Estado final de `C:\FOREX` y `C:\FOREX_CAP` (para el acta)

```powershell
git -C C:\FOREX status --porcelain=v1
git -C C:\FOREX_CAP status --porcelain=v1
git -C C:\FOREX log -1 --format='%H %s'
git -C C:\FOREX_CAP log -1 --format='%H %s'
```

**Esperado:** `C:\FOREX`: solo untracked (`bars_ingester_console.log`, `machine_local.ava2.json.disabled`, y el acta 2026-09-24 si existía); `C:\FOREX_CAP`: sin salida.

### 10.3 Subirla a `equipo3-actas` con un worktree

```powershell
$ex = (git -C C:\FOREX ls-remote --heads origin equipo3-actas)
"equipo3-actas en el remoto: " + $(if ($ex) { 'SI' } else { 'no' })
```

- Si **no existe** (caso esperado):
```powershell
git -C C:\FOREX worktree add -b equipo3-actas C:\FOREX_WT_ACTAS HEAD
```
- Si **existe**:
```powershell
git -C C:\FOREX fetch origin equipo3-actas
git -C C:\FOREX worktree add --detach C:\FOREX_WT_ACTAS origin/equipo3-actas
```

Escribe el acta en `C:\FOREX_WT_ACTAS\docs\EQUIPO3-SESION-2026-10-06-CAPITARIA.md` (crea la carpeta `docs` si hace falta) y publica:

```powershell
$gn = (git -C C:\FOREX config user.name); $ge = (git -C C:\FOREX config user.email)
$idArgs = @()
if ((-not $gn) -or (-not $ge)) { $idArgs = @('-c', 'user.name=Claude Code equipo3', '-c', 'user.email=noreply@anthropic.com') }
git -C C:\FOREX_WT_ACTAS add -- docs/EQUIPO3-SESION-2026-10-06-CAPITARIA.md
git -C C:\FOREX_WT_ACTAS status --short
git -C C:\FOREX_WT_ACTAS @idArgs commit -m 'docs(equipo3): acta de la sesion 2026-10-06 -- Capitaria 2883016902 y baja del stack B (101744076)' -m 'Co-Authored-By: Claude <noreply@anthropic.com>'
git -C C:\FOREX_WT_ACTAS push origin HEAD:equipo3-actas
git -C C:\FOREX ls-remote --heads origin equipo3-actas
git -C C:\FOREX_WT_ACTAS rev-parse HEAD
git -C C:\FOREX worktree remove C:\FOREX_WT_ACTAS
git -C C:\FOREX worktree prune
```

**Esperado:** `status` con **solo** el acta; el push termina bien (rama nueva o fast-forward); `ls-remote` y `rev-parse` coinciden; el worktree se retira.
**STOP si:** `status` muestra cualquier otro fichero (en particular `machine_local*.json` o `CUENTAS.md`: **no los añadas jamás**); el push falla o es rechazado (**sin `--force`**).

### 10.4 Respuesta final al humano

Responde **solo** con: la ruta del acta (`docs/EQUIPO3-SESION-2026-10-06-CAPITARIA.md` en la rama `equipo3-actas`) y su SHA, el SHA de `equipo3-d63`, el estado de cada stack (una línea) y **una línea por desviación o STOP**.

---

## Lista «NUNCA»

- **Nunca `setx`** (ni `[Environment]::SetEnvironmentVariable`) de nada, y menos de `SUPERVISOR_*` o `SENTINEL_MACHINE_PROFILE`.
- **Nunca `Stop-ScheduledTask`** (puede tumbar el árbol de procesos: supervisor y ejecutor armado). Para parar un watchdog: solo su `powershell`, por PID.
- **Nunca matar procesos por nombre** (`Stop-Process -Name`, `taskkill /IM`, `Get-Process python | Stop-Process`). Siempre por PID tras identificarlo por `ExecutablePath`/línea de comandos.
- **Nunca tocar la 74:** ni su ejecutor, ni su supervisor, ni su terminal, ni sus ficheros (`STOP`, `research.db`, perfiles).
- **Nunca editar** `sentinel_engine/`, `scripts/live/*.py`, configs de estrategia ni los watchdogs. (Lo único que se revierte es el `git checkout --` de la fase 1.6.)
- **Nunca `git push --force`**, `git add -A`, `git commit` sobre el checkout vivo de `C:\FOREX`, ni commitear `machine_local*.json`, `CUENTAS.md` o contraseñas.
- **Nunca manejar contraseñas:** no pedirlas, no escribirlas, no guardarlas, no pasarlas por línea de comandos (`terminal64.exe /login: /password:`).
- **Nunca llamadas a MT5** (`mt5.initialize`, órdenes, `symbol_select`…) ni ejecutar `verify_two_terminals`.
- **Nunca `Copy-Item -Recurse`** de una instalación MT5 (se mueve, no se copia).
- **Nunca «arreglar» lo inesperado:** se para y se informa.
- **Nunca borrar** `machine_local.ava2.json.disabled`, `research_ava2.db` ni `C:\Program Files\MetaTrader 5`.
- **Nunca cambiar la ventana `18:00-18:45`** ni el cap de spread.

---

## Riesgos abiertos para el humano (NO son parte de la ejecución de hoy)

1. **Compuerta de reloj (7.4):** con Chile en horario de verano (`-03:00`) la ventana `18:00-18:45` —que se compara con el reloj **local**— no coincide con la de M2 (`-04:00`). Decisión del humano antes de arrancar Capitaria.
2. **BIOS `Restore on AC Power Loss` = Power On + autologin (`netplwiz`)** sin hacer (spec §5.4 #1): sin ellos, un corte de luz deja **los dos stacks** muertos hasta que alguien inicie sesión (las tareas se disparan al iniciar sesión). Con autologin, quien tenga acceso físico entra al escritorio.
3. **Backup de `research.db`** del equipo 1 (serie histórica de la 74) sin verificar (§5.4 #2), y que el **equipo 1 esté de verdad parado** para la 74 (§5.4 #3): dos ejecutores sobre la misma cuenta se cierran las posiciones entre sí.
4. **La máquina M2 (W11) de Capitaria debe seguir con su MT5 apagado:** dos ejecutores sobre la 2883016902 se pisarían (el usuario confirmó que no corre; no está verificado técnicamente).
5. **Contraseña de la 902 no persistida** (§5.4 #6): si el terminal pierde la sesión de madrugada y no la guardó MT5 (`Config\accounts.dat`, cifrada y ligada a la instalación), nadie la reintroduce.
6. **Ingesta de barras de Capitaria:** el supervisor de Capitaria da por suyo el `run_bars_ingester` de AVA (cruce de `process_running`, aceptado) y el de AVA no ingiere `XAUUSD`; el *lake* de OHLC de Capitaria puede quedar sin alimentar (solo investigación, no trading). Y `deals_seen=0` sostenido en cualquiera de los dos stacks sigue siendo un incidente de pérdida de datos (§6).
7. **La 101744076 se muda al equipo 1 y todavía no está planificado cómo.** Mientras tanto no opera en ningún sitio. Queda `data/research_ava2.db` (sin borrar) y la rama `equipo3-d63` con la sanción D-63.
8. **`CUENTAS.md` del equipo 1** sigue diciendo que la 902 no se opera (§5.4 #5); actualizar a mano.
9. **D-39** (el ejecutor abre a mercado con el SL ya arrastrado del simulador) sigue vigente en ambos stacks a propósito (§5.4 #9).
10. **Un watchdog lanzado a mano** (alternativa de 3.4) no está bajo la tarea programada y puede no sobrevivir al cierre de Claude Code: si se usó, el humano decide cómo devolverlo a la tarea (cierre/inicio de sesión de Windows reinicia **todo** el stack).
11. Residuos sin tocar: `C:\Program Files\MetaTrader 5` (~375 MB), `scripts/live/bars_ingester_console.log` sin ignorar, tests (10 necesitan el *lake* real; 3 preexistentes).
