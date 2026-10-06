# Equipo 3 — estado, decisiones y pendientes

> **Actualizado:** 2026-10-06 · **Documento de traspaso.** Es la fuente de verdad
> del despliegue multi-cuenta. Si esto y cualquier otro documento se contradicen,
> manda esto.
>
> Antecedentes que NO se repiten aquí y conviene leer antes de tocar nada:
> - `docs/EQUIPO3-INSTALACION.md` — runbook de instalación del equipo 3
> - `docs/EQUIPO3-SESION-2026-09-24-INSTALACION-REALIZADA.md` — acta de lo que
>   realmente pasó al instalar (está en el disco del equipo 3, **sin commitear**)
> - `docs/superpowers/specs/2026-09-24-equipo3-runner-oficial-design.md` — diseño

---

## 1 · Reparto de cuentas — DECISIÓN FIRME (usuario, 2026-10-06)

Esto **sustituye** cualquier reparto anterior. Tres cuentas, dos máquinas:

| Cuenta | Qué corre | Dónde | Estado |
|---|---|---|---|
| **AVA 101744074** | S6-K2P0-AVA + SuperTrend-p14x3-M15-AVA (GOLD, 0.01) | **Equipo 3** (W10) | OK **VIVO desde 2026-09-24 20:00** |
| **Capitaria 2883016902** | roster `tomachine`: S6-K2P0 + SuperTrend (XAUUSD, 0.67) | **Equipo 3** (W10) | **PENDIENTE — es el trabajo de hoy** |
| **AVA 101744076** | campo de pruebas, estrategias NUEVAS | **Equipo 1** (este, W11) | **A MOVER — hoy corre en el equipo 3** |

**La 74 y la Capitaria corren LO MISMO** (S6 + SuperTrend), una en cada bróker.
Ése es el objetivo del despliegue: las dos estrategias idénticas sobre dos
brókers distintos.

### Cambio de alcance pendiente: la 101744076 se va del equipo 3

Hasta el 2026-10-06 la 76 estaba montada en el equipo 3 como «stack #2,
monitorización solamente». La directiva nueva es que **el campo de pruebas corre
en el equipo 1**. Implica:

- **En el equipo 3:** borrar `scripts/live/machine_local.ava2.json`. Con eso el
  watchdog registra `stack #2: sin perfil -- DESACTIVADO` y lo salta sin más —
  está diseñado exactamente para eso. El terminal `C:\MT5_AVA2` se puede cerrar.
  Opcional: borrar `data/research_ava2.db`.
- **En el equipo 1:** montar ahí la 76. **No está hecho ni planificado todavía.**
- **No bloquea** la puesta en marcha de Capitaria. Son independientes.

### Credenciales

`CUENTAS.md` está gitignoreado y es la única fuente de verdad. No viaja en
ninguna rama; cada máquina tiene el suyo.

- **AVA 101744074 y 101744076** — misma password, servidor `Ava-Demo 1-MT5`.
  Está en el `CUENTAS.md` del equipo 1 y en el que la sesión del 2026-09-24 creó
  en el equipo 3.
- **Capitaria 2883016902** — **la password NO está persistida en ningún sitio.**
  El charter §A.12 lo prohibía expresamente. **La aporta el usuario a mano al
  loguear el terminal.**
  > Dato que ahorra una ida y vuelta: MT5 guarda las credenciales en
  > `Config\accounts.dat`, **cifradas y ligadas a la instalación**. No se pueden
  > leer por línea de comandos. Pedírselas a la máquina W11 es inútil: tienen que
  > venir del usuario o del portal de Capitaria.

### Enmienda explícita sobre la 902 (usuario, 2026-10-06)

`CUENTAS.md` y el charter §A.12 marcan la 2883016902 como «NO-R&D / SOLO LECTURA
— jamás operar». **Esa regla queda enmendada.** Directiva textual del usuario:

> «La cuenta de capitaria que corre en el otro equipo ES la que hay que usar,
> estan sus creds, todo lo necesario. Esto es lo necesario y la nueva directiva
> por sobre lo que dicen ahí ellas.» · «La cuenta de capitaria a utilizar ES la
> 2883016902.»

La regla original se escribió cuando la 902 corría en **otra** máquina y desde
aquí solo se leía su historial. El equipo 3 pasa a ser esa máquina.

**No hace falta tocar código por esto:** la rama `equipo3-capitaria` (nacida de
`b113eb7`) ya tiene la 902 en su propio
`guard_cuenta.SANCTIONED_DEMO_LOGINS = {2883015767, 2883016902}`, porque es el
guard con el que la máquina W11 operó de verdad. Solo se escribe el login en un
JSON local.

**Nota:** el `CUENTAS.md` del equipo 1 y los tests de la rama `equipo3-runner`
siguen diciendo lo contrario (hay un test,
`test_real_and_902_stay_outside_the_sanctioned_set`, que existe como alambre
trampa). Hay que actualizar `CUENTAS.md` a mano en el equipo 1 para que el
registro no quede mintiendo. **No hecho.** El test de `equipo3-runner` no
estorba: esa rama no opera la 902.

---

## 2 · Arquitectura: dos clones, un intérprete por clon

El equipo 3 corre **dos stacks operando en paralelo desde clones separados**:

```
C:\FOREX       rama equipo3-runner      AVA 101744074   GOLD    dashboard :8501
               intérprete: py -3.11  (Python311\python.exe del usuario)

C:\FOREX_CAP   rama equipo3-capitaria   Capitaria 902   XAUUSD  dashboard :8502
               intérprete: C:\FOREX_CAP\_py\python.exe  (CPython 3.11.9 real, no venv)
```

**Por qué dos clones y no uno:** el stack es mono-instancia por diseño. `STOP`,
`run_live_20.audit.log`, `data/xauusd_spread_store.json` y `data/research.db`
(asignación de magics + watermark `deals_watcher.last_sync`) son rutas fijas. Dos
ejecutores armados en un mismo clon se pisan. Clones separados lo resuelven con
el sistema de ficheros, sin necesidad de código de scoping por instancia.

### Las cuatro colisiones entre clones, y cómo se arreglan

Los singletons de fichero se separan con el clon. Lo que **no** se separa son los
procesos: son globales a la máquina. El watchdog original asume una única
instancia y tiene cuatro colisiones. **Ninguna da un error visible.**

| # | En `watchdog_local.ps1` | Qué pasaría |
|---|---|---|
| 1 | `Get-Process -Name "terminal64"` es global | Con 2-3 terminales siempre da verdadero → **el terminal caído no se relanza jamás** |
| 2 | `Find-ProcByCmdline 'supervisor_live'` | Ve el supervisor del OTRO clon → **su stack no arranca nunca, en silencio** |
| 3 | `Find-ProcByCmdline 'run_deals_watcher'` | Ídem; y los dos clones usan el mismo `--db data/research.db` relativo, así que el patrón coincide |
| 4 | Siega de huérfanos: mata todo `run_live_20` | **Cada relanzamiento del supervisor mataría el ejecutor armado del otro stack**, dejando posiciones abiertas sin gestionar |

**El arreglo: un intérprete distinto por clon.** Todo filtro de proceso exige
`ExecutablePath == el intérprete propio`. Es exacto, no heurístico: dos rutas de
exe distintas no se pueden confundir.

- Capitaria corre sobre su **CPython 3.11 real y propio** (`<repo>\_py\python.exe`,
  paquete NuGet `python` 3.11.9). **NO un venv** (ver la corrección de abajo). Este
  intérprete aparte **no es opcional** — es el mecanismo de aislamiento.
- AVA resuelve en este orden: venv del clon → `py -3.11` → `python` con aviso.
  Verificado en el equipo 3: `py -3.11` apunta a
  `C:\Users\<user>\AppData\Local\Programs\Python\Python311\python.exe`.

> **CORRECCIÓN (2026-10-06): un venv NO aísla "por `ExecutablePath`".** En Windows,
> `<venv>\Scripts\python.exe` es un *redirector*: lanza como **hijo** al Python base
> del sistema, y ese hijo (el trabajador real) tiene el **mismo `ExecutablePath` que
> los procesos de AVA** y los mismos módulos en la línea de comandos. Medido en el
> equipo: padre = `<venv>\Scripts\python.exe`, hijo = `...\Python311\python.exe`. Con un
> venv, el watchdog de AVA confundiría los trabajadores de Capitaria con los suyos, y
> `supervisor_live._default_kill` (`proc.kill()`) mataría solo el redirector, dejando
> vivo al ejecutor real (el supervisor relanzaría otro: órdenes dobles).
> Regla vigente: **Capitaria corre sobre un CPython real en `C:\FOREX_CAP\_py\python.exe`**
> (ruta distinta de la de AVA), y los hijos que lanza el supervisor con
> `sys.executable` son procesos reales en esa misma ruta; el aislamiento por
> `ExecutablePath` vuelve a ser exacto en los dos sentidos. Como defensa en
> profundidad, el watchdog de Capitaria marca todo python que lanza con
> `-X sentinel_stack=capitaria` y mata siempre el árbol (`taskkill /T /F`), y el de
> AVA ignora lo marcado y todo hijo de un python con otro `ExecutablePath`.
> Además, el stack B de AVA (`machine_local.ava2.json`) solo se vigila si ese
> perfil existe; sin él el watchdog registra `stack B deshabilitado (sin
> machine_local.ava2.json)` y no toca su terminal.

De paso cierra el **riesgo D1** del acta: el equipo 3 tiene también un Python
3.14.5, y `python` a secas resolvía a 3.14 en consola interactiva y a 3.11 bajo
la tarea programada. Con 3.14 faltaría PyYAML y pandas/numpy serían otras
versiones.

### Variables de entorno — SIEMPRE por proceso, NUNCA `setx`

Los dos watchdogs inyectan el entorno en la línea de comandos de cada hijo. Una
variable persistida se aplicaría a los dos stacks:

| Stack | Variables |
|---|---|
| AVA | `SUPERVISOR_CONFIGS=ava` · `SUPERVISOR_SYMBOL=GOLD` · `SUPERVISOR_MAX_SPREAD_OPEN=` **(vacío)** · `SUPERVISOR_STALE_AUTORESTART=1` |
| Capitaria | `SUPERVISOR_CONFIGS=tomachine` · `SUPERVISOR_MAX_SPREAD_OPEN=0.5` · `SUPERVISOR_BLOCKED_OPEN_WINDOW=18:00-18:45` · `SUPERVISOR_NO_ADAPTIVE_SPREAD=1` |

**`SUPERVISOR_MAX_SPREAD_OPEN=0.5` es correcta para XAUUSD y letal para AVA.**
El spread de GOLD en AVA medido el 2026-09-24 fue 0.29, pero el histórico es
0.73-0.80: un cap de 0.5 bloquea aperturas **sin un solo error en los logs**. El
sistema parece sano y no abre nada. Por eso el watchdog de AVA la **limpia**
explícitamente con `set SUPERVISOR_MAX_SPREAD_OPEN=` aunque viniera heredada.

Sintaxis cmd: `set VAR=valor&&` **sin espacio antes de los `&&`** (un espacio ahí
entraría dentro del valor). `set VAR=&&` deja la variable **inexistente**, no
vacía — verificado empíricamente.

Ambos scripts de autoarranque **se niegan a correr** si encuentran variables
`SUPERVISOR_*` o `SENTINEL_MACHINE_PROFILE` persistidas en ámbito User/Machine.

### El override `SENTINEL_MACHINE_PROFILE`

Añadido en `sentinel_engine/live/machine_profile.py` (módulo documentado en su
cabecera como «NOT a safety module: mutable, machine-local SELECTION config»).
Permite que **un proceso concreto** lea otro fichero de perfil.

- **Inerte por defecto**: sin definir resuelve a la ruta fija de siempre.
- **Solo selecciona**: el `demo_login` sigue pasando por el frozenset escrito a
  mano de `guard_cuenta`. No puede introducir una cuenta no sancionada.
- **Fichero ausente = error duro** cuando la ruta vino de la variable. Caer a los
  valores por defecto le daría a un stack el terminal y el login del otro.
- **Nunca `setx`**: persistida apuntaría todos los procesos, incluido el ejecutor
  armado.
- 7 pruebas en `tests/live/test_machine_profile.py` lo cubren, incluida la de que
  apuntar a la cuenta REAL es rechazado.

Se usaba para el watcher de la 76 en el equipo 3. Al mover la 76 al equipo 1
deja de usarse allí, pero el mecanismo queda disponible.

---

## 3 · Ramas y commits

| Rama | Commit | Qué es |
|---|---|---|
| `equipo3-runner` | `a088146` | Rama **ligera** del stack AVA. 8.4 MB / 580 ficheros (la completa son 95.8 MB / 1171). Clonar con `--branch equipo3-runner --single-branch --depth 1`. |
| `equipo3-capitaria` | `b1b0223` | Stack Capitaria. **Huérfana, nacida de `b113eb7`** = HEAD exacto de M2_ENTREGA. 38.2 MB. |
| `equipo3` | `490ae65` | Rama intermedia con historia completa. No se usa para desplegar. |
| `equipo1` | local, 259 commits por delante de origin | Máquina de desarrollo |

Los tres modificadores del clonado importan: sin `--single-branch --depth 1` se
descargarían los 96 MB de todos modos aunque la rama sea pequeña.

### Qué excluye la rama ligera, y la excepción que importa

Fuera: `research/` (55.9 MB), `docs/superpowers/` (24 MB), `backups/` (8.6 MB),
`data/analysis/` (1 MB).

**Excepción obligatoria:**
`research/fases/F0-preparacion/04-resultados/T0.13-ventana-ny/` (15 KB) **sí
viaja**. `sentinel_engine/live/ava_window_gate.py:55` lee de ahí
`calendario-ventana.json` en **cada decisión de apertura**, y ese gate **falla
duro** por diseño (nunca abre «por si acaso»). Sin el fichero, las dos
estrategias AVA dejan de abrir: no un error ruidoso, una parada total del
servicio. Si alguna vez se mueve o regenera ese calendario, acordarse de esto.

También conservados por dependencia perezosa (no aparecen al importar el stack,
solo al evaluar una apertura): `scripts/research/ventana_calendario.py` y
`scripts/research/ny_window.py`.

### Divergencia de `equipo3-capitaria`

`b113eb7` (2026-07-27 18:51) se separó de nuestra línea en `f93e54a`
(2026-07-22, HEAD de `alvaro`). Desde ahí: **10 commits** por el lado de M2 y
**261** por el nuestro. Los 10 existen en este repo como objetos sueltos,
alcanzables por SHA, sin rama que los apunte — nunca se pushearon desde el W11.

Esa rama **no tiene nada de AVA**: ni `CONFIGS_AVA`, ni `ava_window_gate`, ni el
override `SENTINEL_MACHINE_PROFILE`, ni `news_calendar.py`. Es correcto: está
congelada a propósito para ser idéntica a M2_ENTREGA.

Lo que **sí** tiene y la rama de AVA **no**: `max_volume` por config,
`_tomachine_copy` con lote 0.67, el time-gate `--blocked-open-window`, y
`SUPERVISOR_NO_ADAPTIVE_SPREAD`.

### Lo que hay en `equipo3-capitaria` y no venía de M2

Estrategias y parámetros **byte-idénticos** a `b113eb7`. Solo infraestructura:

- `scripts/live/watchdog_capitaria.ps1` — arregla las 4 colisiones, dashboard 8502
- `scripts/live/setup_autostart_capitaria.ps1` — tarea `SENTINEL_Watchdog_Capitaria`, 4 cerrojos, sin `setx`, no toca la energía (ya la dejó el setup de AVA; es propiedad de la máquina)
- `scripts/live/machine_local.capitaria.example.json`
- `scripts/live/requirements-capitaria.txt` — versiones fijadas a las verificadas
- `INICIAR_CAPITARIA.bat`
- `.gitignore` — `_py/`, logs y lock propios

### Config exacta del roster `tomachine` (verificada en `b113eb7`)

- 2 configs: **S6-K2P0** (`active_fichas=1`) + **SuperTrend-p14x3-M15**
- símbolo **XAUUSD**, `volume=0.67`, `max_volume=0.67` por config
- magics: S6 base 724010 → **F1 = 724011** · SuperTrend base 724070 → **F1 = 724071**
- `max_volume` por config es **imprescindible**: el `MAX_VOLUME` global de
  `reconciler.py` es **0.10**. Sin el override, todo OPEN a 0.67 saldría
  `REJECT_VOLUME` — el stack arrancaría, parecería sano y **no abriría ni una
  posición**. Está en `b113eb7`; **NO está en `equipo3-runner`**.
- gate de spread **NO adaptativo** desde 2026-07-27 18:52: solo cap duro 0.50
- `preflight_live.SYMBOL = "XAUUSD"` por defecto en esa rama (no hace falta
  `SUPERVISOR_SYMBOL`, que además no existe allí)

---

## 4 · Hecho y verificado

### Equipo 3, stack AVA 101744074 — VIVO

Instalado el 2026-09-24. Primeras dos posiciones a las **20:00:05** hora Chile,
`retcode=10009` (`TRADE_RETCODE_DONE`):

| Ticket | Magic | Estrategia | Lado | Vol | Precio | SL |
|---|---|---|---|---|---|---|
| 70141709 | 727011 | S6-K2P0-AVA | BUY | 0.01 | 4273.72 | 4260.84 |
| 70141711 | 727021 | SuperTrend-p14x3-M15-AVA | SELL | 0.01 | 4273.40 | 4277.20 |

Abrieron en direcciones opuestas: es el comportamiento esperado de dos
estrategias independientes sobre el mismo símbolo, no un error, pero deja la
exposición neta casi plana. Tenerlo en cuenta al leer el P&L.

Máquina: Windows 10 Pro build 19045 (22H2), i7-4702MQ, 15 GB, TZ Chile
(`Pacific SA Standard Time`). Usuario `Administrator`. Repo `C:\FOREX`.
Claude Code 2.1.268. Balance de la 74 al cierre: 1400.00 / equity 1399.39.

### Verificado en seco desde el equipo 1

- Detección de terminal **por `ExecutablePath`**: `True` para la ruta real,
  `False` para otra. Es el arreglo de la colisión 1.
- Inyección de entorno inline: valor exacto sin espacio final; `set VAR=&&` deja
  la variable inexistente.
- `py -3.11` resuelve al Python311 correcto.
- Clon de `equipo3-runner` desde GitHub: **4.5 s**, 580 ficheros, **235 pruebas
  pasan** (`tests/live/` 229 + `tests/golden/` 6), el roster AVA se construye, el
  calendario de ventana carga y `open_allowed()` corre sin excepción.
- `git diff` confirma que `run_live_20.py`, `supervisor_live.py`,
  `preflight_live.py`, `reconciler.py`, `guard_cuenta.py`, `live_configs_20.py`,
  `INICIAR_AVA_LIVE.bat`, `watchdog_local.ps1` y `setup_autostart_machine1.ps1`
  quedan **byte-idénticos** entre `equipo1` y `equipo3-runner` (R1-bis).
- Los dos `.ps1` nuevos pasan el parser de PowerShell 5.1.

### Lecciones de instalación que cuestan horas si se olvidan

1. **MT5: instalar de cero y MOVER, nunca copiar.** `Copy-Item -Recurse` rompe
   **ambas** instalaciones: el instalador de marca guarda `Config\servers.dat` +
   `Config\terminal.lic`, y la copia no produce dos instalaciones válidas —
   pierden la lista de servidores del bróker y caen a modo genérico, donde el
   servidor del bróker no existe. Método real: `<instalador>.exe /auto` →
   instala en `C:\Program Files\<Broker> MT5 Terminal` → **`Move-Item`** a su
   destino → repetir el instalador desde cero para la siguiente instancia.
2. **El instalador de marca no tiene URL pública.** Se descarga del portal del
   bróker con sesión iniciada.
3. **Mover la instalación pierde la Observación de Mercado.** MT5 guarda el
   Market Watch en `%APPDATA%\MetaQuotes\Terminal\<hash>` y **el hash deriva de
   la ruta de instalación**. Al mover se crea una carpeta de datos nueva y vacía.
   Hay que **volver a añadir el símbolo DESPUÉS de mover**. El 2026-09-24 esto
   costó **11 ciclos de preflight fallido**. Síntoma exacto:
   `[FAIL] symbol-tradable: symbol=GOLD visible=False`
4. **El supervisor NO escribe en `supervisor_local.log`** (queda a 0 bytes y
   hace dudar). Escribe en **`scripts\live\watchdog.log`** vía `_log_watchdog`.
   Ahí aparecen los `preflight FAIL`.
5. **Permitir trading algorítmico** en cada terminal:
   `Herramientas → Opciones → Asesores Expertos`.
6. El `.bat` de `REANUDAR_TRADING` termina en `pause` — se cuelga en consola no
   interactiva. Cuidado al automatizar.
7. Intentar loguear por línea de comandos
   (`terminal64.exe /login: /password:`) queda bloqueado y además no funciona:
   MT5 no reenvía el login a una instancia ya abierta, y la password quedaría
   visible en el listado de procesos. **El login se hace a mano en la GUI.**

---

## 5 · PENDIENTE — el trabajo de hoy

### 5.1 · El equipo 3 debe commitear y pushear su cambio de `guard_cuenta.py`

**Verificado el 2026-10-06:** `origin/equipo3-runner` contiene **cero**
ocurrencias de `101744076`. La sanción de la segunda cuenta AVA (D-63) que hizo
la sesión del 2026-09-24 existe **solo en el disco del equipo 3**, sin
commitear. Si ese disco falla, el stack #2 no arranca
(`MachineProfileError`) y nadie sabe por qué.

Estado en esa máquina al cierre de aquella sesión:

```
 M sentinel_engine/live/guard_cuenta.py     (+101744076 en el frozenset, D-63)
 M tests/live/test_guard_cuenta.py          (conjunto esperado actualizado)
?? scripts/live/bars_ingester_console.log   (NO commitear; ya está en .gitignore)
```

Commitear los dos primeros, más el acta
`docs/EQUIPO3-SESION-2026-09-24-INSTALACION-REALIZADA.md`.
**NUNCA** `CUENTAS.md` ni `machine_local*.json` (credenciales; ya gitignoreados).

Sigue siendo útil aunque la 76 se mueva al equipo 1: el cambio de código y el
acta son trazabilidad que ahora solo existe en un disco.

### 5.2 · Capitaria en el equipo 3 — orden exacto

1. **Proteger AVA primero.** `git stash` de los dos ficheros modificados,
   `git pull origin equipo3-runner` (debe llegar a `a088146`), `git stash pop`.
   Reiniciar la tarea `SENTINEL_Watchdog_Equipo3`. En
   `scripts\live\watchdog_equipo3.log` debe aparecer
   `interprete clavado: ...Python311\python.exe`.
   **Sin este parche los dos watchdogs se destruyen** (colisiones 2, 3 y 4).
   Reiniciar el watchdog es seguro: no mata a sus hijos, solo se relanza.
2. **Instalar el tercer MT5** (Capitaria, instalador de marca del portal) →
   `/auto` → `Move-Item` a `C:\MT5_CAPITARIA`. **No copiar.**
3. **Loguear la 2883016902** a mano (password del usuario), permitir trading
   algorítmico, y **añadir XAUUSD a Observación de Mercado DESPUÉS de mover**.
   Confirmar en la esquina que el balance es ~71 MM CLP y que es DEMO.
4. **Clonar** `equipo3-capitaria` en `C:\FOREX_CAP`
   (`--branch equipo3-capitaria --single-branch --depth 1`).
5. **Instalar el CPython propio** (NO un venv): paquete NuGet `python` 3.11.9
   descomprimido en `C:\FOREX_CAP\_py`, y luego
   `C:\FOREX_CAP\_py\python.exe -m pip install -r scripts\live\requirements-capitaria.txt`.
   Los comandos exactos están en la cabecera de `requirements-capitaria.txt`. Debe dar
   `3.11.9` y `MetaTrader5 5.0.5735`.
6. **`machine_local.json`** en ese clon:
   `C:\MT5_CAPITARIA\terminal64.exe`, `portable: false`,
   `demo_login: 2883016902`, `terminal_marker: mt5_capitaria`.
7. `pytest tests\live\ -q` con `C:\FOREX_CAP\_py\python.exe`.
8. `setup_autostart_capitaria.ps1` (PowerShell elevado) → `Start-ScheduledTask`.
9. **Verificar los dos stacks en paralelo** (§6).

### 5.3 · Mover la 101744076 al equipo 1

Ver §1. En el equipo 3: borrar `machine_local.ava2.json`. En el equipo 1: montar
el campo de pruebas. **No planificado todavía.**

### 5.4 · Riesgos abiertos, no resueltos

| # | Asunto | Gravedad |
|---|---|---|
| 1 | **BIOS `Restore on AC Power Loss` = Power On + autologin (`netplwiz`)** sin hacer. La tarea se dispara **al iniciar sesión**, no al arrancar, porque MT5 necesita escritorio. Sin autologin, un corte de luz deja el stack muerto hasta que alguien entre. Coste a valorar: con autologin, acceso físico = escritorio abierto. | **Alta** |
| 2 | **Backup de `D:\FOREX\data\research.db`** del equipo 1 (serie histórica de la 74). No verificado. | Media |
| 3 | **Equipo 1 realmente parado** para la 74. Confirmado verbalmente, no técnicamente. Misma cuenta → dos ejecutores se cerrarían las posiciones entre sí. | Alta si no lo está |
| 4 | `C:\Program Files\MetaTrader 5` residual (~375 MB) del intento con el instalador genérico. Borrable sin consecuencias. | Baja |
| 5 | `CUENTAS.md` del equipo 1 sigue diciendo que la 902 no se opera. Actualizar a mano. | Baja |
| 6 | **Password de la 902 no persistida** vs. runner desatendido: si ese terminal pierde sesión de madrugada, nadie la reintroduce. No tiene solución técnica limpia. | Media |
| 7 | **`SUPERVISOR_BLOCKED_OPEN_WINDOW=18:00-18:45`: reloj sin confirmar.** Si se evalúa contra el reloj local y ambas máquinas están en Chile, el comportamiento es idéntico. **Verificar en el audit log** una vez corra. | Media |
| 8 | **Ingesta de barras sin GOLD**: el `SYMBOL_MAP` de `mt5_dump_history.py` no contiene `GOLD` (sí `XAUUSD`). En AVA no ingesta nada; el ruido `MISSING on broker` es esperado. Queda fuera del watchdog a propósito: vigilarlo lo haría oscilar en bucle. | Baja |
| 9 | **D-39 sigue vigente** y viaja a los dos stacks sin arreglar, a propósito, para no romper la comparabilidad de la serie. El ejecutor abre a precio de mercado pero hereda el SL ya arrastrado del simulador; `price_ref` viaja en la acción y se descarga sin leerse. El 21-09 produjo 1.016 `OPEN_SKIPPED_SL_CROSSED` en AVA, y los `SL_CLAMPED OPEN` que sí salen nacen con el stop a la distancia mínima legal. Diagnosticado; pendiente de decisión aparte. | Declarada |
| 10 | El calendario de ventanas R2 **extrapola sin marcarlo** pasado 2026-08-11. | Baja |

---

## 6 · Verificación de los dos stacks en paralelo

```powershell
Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" |
    Select-Object ProcessId,ExecutablePath
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'supervisor_live|run_live_20|run_deals_watcher' } |
    Select-Object ProcessId,ExecutablePath | Format-Table -AutoSize
```

Esperado tras mover la 76 al equipo 1:

- **2 terminales**: `C:\MT5_AVA1` (login 101744074) y `C:\MT5_CAPITARIA`
  (login 2883016902)
- **~4 procesos** sobre `...Python311\python.exe` → AVA (watcher + supervisor +
  ejecutor armado, más el bars ingester)
- **~3 procesos** sobre `C:\FOREX_CAP\_py\python.exe` → Capitaria
- Dashboards: AVA `:8501`, Capitaria `:8502`
- Magics en el audit log de Capitaria: **724011** y **724071**

### Vigilancia diaria

```powershell
Get-Content C:\FOREX\scripts\live\run_live_20.audit.log      -Wait -Tail 40  # AVA, decisiones
Get-Content C:\FOREX\scripts\live\watchdog.log               -Wait -Tail 40  # AVA, preflight
Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log       -Wait -Tail 40  # AVA, auto-sanado
Get-Content C:\FOREX_CAP\scripts\live\run_live_20.audit.log  -Wait -Tail 40  # CAP, decisiones
Get-Content C:\FOREX_CAP\scripts\live\watchdog_capitaria.log -Wait -Tail 40  # CAP, auto-sanado
```

Tres alarmas: **audit log sin líneas nuevas >5 min** con mercado abierto ·
**`deals_seen=0` sostenido** (incidente de pérdida de datos) · **cero aperturas
en todo un día**. Ante cero aperturas en Capitaria, mirar primero el cap de
spread y los `SPREAD_GATE_SKIP` / `TIME_GATE_SKIP` del audit log.

### Qué sana solo el watchdog, y qué no

| Cae… | ¿Solo? | Cómo |
|---|---|---|
| Un terminal MT5 | Sí | Detección por ruta + `Start-Process` |
| Un deals watcher | Sí | Relanzado en ≤20 s |
| Un supervisor | Sí | Relanzado, previa siega de ejecutores huérfanos **del propio stack** |
| El ejecutor armado | Sí | Es hijo del supervisor: preflight + backoff exponencial |
| Ejecutor «rancio» | Sí (AVA) | `SUPERVISOR_STALE_AUTORESTART=1`; en Capitaria **no está puesta** (M2 no la usaba) |
| El dashboard | Sí | Si nadie escucha en su puerto |
| El propio watchdog | Sí | La tarea lo reinicia (999 veces, cada minuto) |
| Cierre de sesión | Sí | La tarea se dispara al iniciar sesión |
| **Máquina apagada** | **No** | Necesita BIOS + autologin → §5.4 #1 |
| Ingesta de barras | **No vigilada** | §5.4 #8 |

### Parar

```powershell
cd C:\FOREX     ; .\PAUSAR_TRADING.bat    # pausa AVA (kill-switch por fichero STOP)
cd C:\FOREX_CAP ; .\PAUSAR_TRADING.bat    # pausa Capitaria, independiente
Stop-ScheduledTask -TaskName SENTINEL_Watchdog_Equipo3
Stop-ScheduledTask -TaskName SENTINEL_Watchdog_Capitaria
```

Los ficheros `STOP` son **por clon**, así que se pausa un stack sin tocar el
otro. Es una de las razones por las que hay dos clones.

---

## 7 · Qué NO se ha recibido, y qué no hace falta pedir

**Última entrega de la máquina Capitaria (W11): `M2_ENTREGA`, 2026-08-12.** Nada
después. El sitrep que se redactó para esa máquina nunca volvió respondido, y en
`origin` no existe ninguna rama suya (`alvaro-tomachine-s6st-config`, `m2-live`).

**No hace falta pedirle nada.** `b113eb7` ya está en este repo y publicado como
`origin/equipo3-capitaria`; el usuario confirmó que esa máquina no se ha
modificado desde la entrega. Y su MT5 **no está corriendo** (usuario,
2026-10-06), así que no hay riesgo de que dos ejecutores se peleen por la 902.

Lo único que esa máquina no puede dar de ninguna forma es la **password**: MT5 la
guarda cifrada y ligada a la instalación en `Config\accounts.dat`.

### `M2_ENTREGA` — solo lectura absoluta

`C:\Users\tomas\Downloads\M2_ENTREGA\M2_ENTREGA\` (468 MB / 1271 ficheros) es la
**única copia viva** del setup de la 902: el `data/entregas/...` del repo se
borró del disco entre el 31-ago y el 22-sep. Prohibido crear, editar, mover,
borrar o descomprimir nada ahí dentro. Contiene `RESUMEN.md`, `config_efectiva/`
(los ficheros vivos exactos con que operó la 902),
`diff_vs_origin-alvaro.patch`, `commits_sin_pushear.txt`, `logs_ejecutor/`
(audit de 70 MB), `mt5_logs_capitaria/`, `repo/` (copia completa, incl.
`research.db` con `deals_raw`) y los zips/bundle.

Su `RESUMEN.md` declara que `server`, `company` y `balance` eran **no
obtenibles** en el momento de la entrega — de ahí que el balance de la 902 nunca
se haya verificado desde aquí, y que la confirmación de los ~71 MM CLP tenga que
hacerse al loguear el terminal.
