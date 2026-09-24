# Equipo 3 — runner oficial de dos stacks MT5

> Diseño · 2026-09-24 · rama `equipo3`
> Runbook del operador: `docs/EQUIPO3-INSTALACION.md`

## 1 · Problema

El equipo 1 (`D:\FOREX`, Windows 11) opera hoy la demo AVA 101744074 con
`S6-K2P0-AVA` y `SuperTrend-p14x3-M15-AVA`, y a la vez es la máquina de
desarrollo. Las dos funciones se estorban: reiniciar para desarrollar corta el
servicio, y operar impide tocar nada.

Se quiere separar: una tercera máquina (Windows 10) pasa a ser el **runner
oficial**, operando de forma continua y auto-sanable, y el equipo 1 queda solo
para desarrollo. El equipo 3 corre además un **segundo MT5** con otra demo AVA
como campo de pruebas para variantes futuras.

### Restricciones fijadas por el usuario

- La cuenta 101744074 **migra**; no corre en paralelo. Una cuenta de bróker con
  dos ejecutores armados es un fallo garantizado (los reconciliadores se pisan).
- El stack #1 conserva la **configuración exacta** de las estrategias, sin
  modificaciones salvo las necesarias para que corra y se compruebe.
- El MT5 #2, **por ahora, solo necesita la conexión básica**: sin estrategias,
  pero visible para runners y monitores.
- El sistema debe auto-sanarse: detectar un terminal cerrado, reabrirlo,
  recuperarse de caídas y de reinicios.

## 2 · Lo que impedía hacerlo

El stack es **mono-instancia por diseño**, con singletons de ruta fija:

| Recurso | Ruta | Colisión con dos stacks |
|---|---|---|
| Perfil de máquina | `scripts/live/machine_local.json` | un solo objeto: un terminal, un login |
| Kill-switch | `scripts/live/STOP` | pararía los dos |
| Audit log | `scripts/live/run_live_20.audit.log` | dos escritores ⇒ la alarma de «rancio» deja de detectar |
| Spread store | `data/xauusd_spread_store.json` | mezcla running-min de símbolos distintos |
| Magics + deals | `data/research.db` | un solo watermark (`deals_watcher.last_sync`) |
| Detección de terminal | `watchdog_local.ps1:153` | `Get-Process -Name "terminal64"` es **global**: con dos terminales da verdadero aunque el caído sea el otro, y ese no se relanza jamás |

Y `guard_cuenta.SANCTIONED_DEMO_LOGINS` es un `frozenset` escrito a mano a
propósito: el guard no depende de configuración mutable para saber qué cuentas
son operables. Una cuenta nueva es un cambio de código con autorización
explícita, como lo fue D-62.

## 3 · Enfoques considerados

**A · Dos clones del repo.** Cero cambios de código; cada clon con sus
singletons. Descartado: dos árboles que sincronizar a mano, deals partidos en
dos bases, y **aun así** hay que arreglar la detección de terminal, que es
global a la máquina y no al clon. Paga el precio sin comprar la seguridad que
aparenta.

**B · Scoping completo por instancia.** Una variable que sufije todos los
singletons. Descartado *por ahora*: toca constantes de módulo en cinco ficheros,
dos de ellos order-capable, para cubrir un requisito (armar el stack #2) que hoy
no existe.

**C · Asimétrico — ELEGIDO.** Se apoya en el hecho de que **el stack #2 no lleva
estrategias**. Sin estrategias no hace falta ejecutor ni supervisor: basta un
terminal vivo y un watcher capturando su historial. El código order-capable
(`run_live_20.py`, `supervisor_live.py`, `preflight_live.py`) **no se toca en
absoluto**.

## 4 · Arquitectura

```
                   watchdog_equipo3.ps1   (tarea programada, al iniciar sesión)
                            │
        ┌───────────────────┴────────────────────┐
        │                                        │
   STACK #1  (ARMADO)                      STACK #2  (MONITORIZACIÓN)
   AVA 101744074                           2ª demo AVA
   C:\MT5_AVA1\terminal64.exe              C:\MT5_AVA2\terminal64.exe
        │                                        │
        ├── run_deals_watcher --db research.db   └── run_deals_watcher
        │                                             --db research_ava2.db
        └── supervisor_live                           SENTINEL_MACHINE_PROFILE=
             └── run_live_20 --arm --configs ava        machine_local.ava2.json
                  S6-K2P0-AVA         727010
                  SuperTrend-AVA      727020        (sin supervisor,
                  GOLD · 0.01 · 1 pos · R1/R2        sin ejecutor)
                            │
                     dashboard :8501
```

### 4.1 · La única costura nueva: `SENTINEL_MACHINE_PROFILE`

`machine_profile.load_profile()` ya aceptaba `path=` inyectado; lo que faltaba
era poder elegir el fichero **desde fuera del proceso**. Se añade una variable
de entorno que selecciona qué perfil lee un proceso concreto.

- **Inerte por defecto.** Sin definir ⇒ exactamente `MACHINE_LOCAL_JSON`. El
  stack #1 nunca la define y se comporta byte-idénticamente a antes.
- **Solo selecciona.** El `demo_login` del fichero sigue pasando por
  `_validate_demo_login` contra el `frozenset` escrito a mano. La variable no
  puede introducir una cuenta no sancionada, igual que no puede
  `machine_local.json`.
- **Un fichero ausente es error duro** cuando la ruta vino de la variable —
  *no* se cae a los valores por defecto. Caer ahí sería el peor fallo posible
  del diseño: le daría al stack #2 el terminal y el login del stack #1, que es
  justo lo que produciría una errata en la variable.
- **Nunca `setx`.** Persistida repuntaría todo, incluido el ejecutor armado.
  Tanto el watchdog como el script de autoarranque **se niegan a correr** si la
  encuentran en ámbito User o Machine.

`machine_profile.py` está documentado en su propia cabecera como *«NOT a safety
module: this is mutable, machine-local SELECTION config»*. El cambio vive donde
corresponde.

### 4.2 · Watchdog

`watchdog_equipo3.ps1`, derivado de `watchdog_local.ps1`, conserva sus
salvaguardas (singleton por lockfile + línea de comandos, detección por cmdline,
siega de ejecutores huérfanos, guard de cuenta antes de relanzar) y cambia tres
cosas:

1. **Detección de terminal por `ExecutablePath`**, vía `Win32_Process`, en vez
   de por nombre de proceso. Es el arreglo del defecto que hacía imposible el
   caso de dos terminales.
2. **Dos stacks asimétricos**, con el #2 **opcional**: si su perfil no existe o
   es inválido, lo registra y sigue cuidando del #1. El día 1 funciona sin la
   segunda cuenta.
3. **Entorno por proceso.** `SUPERVISOR_CONFIGS=ava`, `SUPERVISOR_SYMBOL=GOLD`,
   `SUPERVISOR_MAX_SPREAD_OPEN=` (vacío a propósito) y
   `SUPERVISOR_STALE_AUTORESTART=1` se inyectan en la línea de comandos del
   supervisor, replicando `INICIAR_AVA_LIVE.bat`. El cap de spread se **limpia**
   explícitamente aunque viniera heredado: el 0.5 de Capitaria contra el spread
   de GOLD en AVA (0.73–0.80) bloquea el 100 % de las aperturas en silencio.

Se niega a arrancar si los dos perfiles apuntan al mismo terminal o al mismo
login.

**No gestiona `run_bars_ingester`**: su `SYMBOL_MAP` es de Capitaria y no
contiene `GOLD`, así que en AVA no ingestaría nada y el watchdog lo relanzaría
en bucle. Queda como punto abierto.

### 4.3 · Autoarranque

`setup_autostart_equipo3.ps1`: tarea al iniciar sesión con reinicio ante fallo y
`ExecutionTimeLimit=0`, y desactivación de suspensión/hibernación con CA. Tiene
cerrojo de equipo 3 (exige `demo_login=101744074`) y **no hace `setx` de nada**,
a diferencia del de la máquina 1 — cuyas variables persistidas ya envenenaron
pytest una vez.

La tarea se dispara **al iniciar sesión**, no al arrancar: MT5 es una aplicación
gráfica y necesita escritorio. Recuperarse de un apagón exige, fuera del repo,
BIOS «Restore on AC Power Loss = Power On» + inicio de sesión automático. Ningún
software enciende una máquina apagada; se documenta como paso de operador con su
coste de seguridad declarado.

## 5 · Riesgo principal y su mitigación

Todo el diseño de un solo clon depende de que `mt5.initialize(path=...)` se
enganche **a ese terminal y no al otro**. Con un solo terminal abierto eso nunca
se puso a prueba, y el 2026-07-24 ya hubo un incidente en que un desajuste del
flag `/portable` hizo que `initialize()` levantara un terminal fantasma.

`scripts/live/verify_two_terminals.py` es la puerta: estrictamente de solo
lectura, comprueba que cada perfil devuelve **su** login, que `GOLD` existe en
ambos, que no apareció ningún terminal nuevo, y que los dos logins son
distintos. **Es el paso 8 del runbook y precede a armar nada.**

**Plan B, si esa verificación falla:** el enfoque A (dos clones del repo, uno por
stack). Es más caro de mantener pero no depende de que `path=` desambigüe. Mejor
descubrirlo el día uno.

## 6 · Pruebas

- 7 pruebas nuevas en `tests/live/test_machine_profile.py`: variable sin definir
  ⇒ ruta histórica; valor vacío tratado como sin definir; selección de otro
  perfil; ruta relativa resuelta contra `REPO_ROOT`; **fichero ausente ⇒ error
  duro**; **no puede introducir un login no sancionado** (se prueba con la
  cuenta REAL); `path=` explícito sigue ganando sobre la variable.
- `tests/live/` completa: 229 pruebas. El único fallo,
  `test_news_calendar.py::test_the_committed_calendar_is_loadable`, es
  **preexistente y ajeno**: `data/live/news_calendar.csv` está borrado del árbol
  de trabajo del equipo 1, pero sigue commiteado, así que un clon nuevo lo
  recibe intacto y allí pasa.
- Verificado en seco en el equipo 1: la detección por ruta distingue
  correctamente (`True` para la ruta real, `False` para la otra), y la inyección
  de entorno inline deja la variable con el valor exacto sin espacio final, y
  `set VAR=&&` la deja **inexistente**, no vacía.

## 7 · Decisiones que quedan abiertas

1. **Sancionar el login de la 2ª demo AVA** (`guard_cuenta.py` +
   `CUENTAS.md`) — requiere autorización explícita del usuario, como D-62. Sin
   ella el stack #2 queda desactivado y el resto funciona.
2. **Cómo armar el stack #2** cuando haya candidatos. Ahí sí habrá que evaluar
   el enfoque B (scoping completo por instancia): `STOP`, audit log y spread
   store tendrían que separarse.
3. **Ingesta de barras en AVA**: qué símbolos seguir y con qué mapa.
4. **D-39** sigue vigente y viaja al equipo 3 sin cambios, deliberadamente: este
   despliegue es una migración a configuración idéntica y arreglarlo aquí
   rompería la comparabilidad de la serie.

## 8 · Ficheros

| Fichero | |
|---|---|
| `sentinel_engine/live/machine_profile.py` | **modificado** — variable `SENTINEL_MACHINE_PROFILE`, inerte por defecto |
| `tests/live/test_machine_profile.py` | **modificado** — 7 pruebas nuevas |
| `.gitignore` | **modificado** — perfiles y logs del stack #2 |
| `scripts/live/watchdog_equipo3.ps1` | nuevo — watchdog de dos stacks |
| `scripts/live/setup_autostart_equipo3.ps1` | nuevo — tarea + energía + guardas de entorno |
| `scripts/live/verify_two_terminals.py` | nuevo — verificación de solo lectura |
| `scripts/live/machine_local.equipo3.example.json` | nuevo — plantillas de perfil |
| `scripts/live/requirements-equipo3.txt` | nuevo — dependencias fijadas a las verificadas |
| `INICIAR_EQUIPO3.bat` | nuevo — arranque manual en primer plano |
| `docs/EQUIPO3-INSTALACION.md` | nuevo — runbook del operador |

**No se ha tocado**: `run_live_20.py`, `supervisor_live.py`, `preflight_live.py`,
`reconciler.py`, `guard_cuenta.py`, `live_configs_20.py`, `INICIAR_AVA_LIVE.bat`,
`watchdog_local.ps1`, `setup_autostart_machine1.ps1`. Las estrategias vivas
siguen byte-idénticas (R1-bis).
