# Plan — roster tomachine = S6 + SuperTrend (1 ficha, 0.3 lotes) + time-gate 18:00–18:45

**Fecha:** 2026-07-27 · **Rama:** `alvaro-tomachine-s6st-config` (LOCAL, base `62d94d6`)
**Máquina:** TOMACHINE (máquina 2) · **Cuenta:** DEMO 2883016567 (Capitaria-All)

## Contexto

El roster `tomachine` corre hoy con 4 configs (S6-K2P0, S7-TPNONE, SuperTrend-p14x3-M15,
TK-BW2-fix2atr), 3 fichas por estrategia y el lote global 0.01. El reporte de desempeño
`docs/REPORTE_DESEMPENO_S6_S7_ST_2026-07-27.md` llevó al owner a quedarse con **S6 + SuperTrend**,
a **ficha única**, a **0.3 lotes**, y a **no abrir posiciones entre 18:00 y 18:45** hora local
(= hora del servidor Capitaria = UTC-4) para que el gap de apertura no contamine las primeras
velas M15.

Decisiones del owner ya tomadas (no re-litigar):

- Roster final: exactamente **2 configs** — S6-K2P0 (magic 724010) y SuperTrend-p14x3-M15
  (magic 724070). S7-TPNONE y TK-BW2-fix2atr **salen**.
- Lote **0.3** por ficha, aceptando explícitamente el escalamiento 10× de exposición.
- El bloqueo horario va **en el ejecutor**, junto al spread-gate — no dentro de
  `simular_variant`. Razón: `blocked_hours` sólo aplica a S6 (SuperTrend usa
  `supertrend_always_in_target`, otro motor sin filtro temporal), tiene granularidad de
  hora entera, y mide la hora de APERTURA de la vela señal en vez del instante de la
  ejecución — un desfase de una vela M15. Un gate en el ejecutor mide el reloj de pared en
  el momento real del OPEN, cubre todos los motores por igual y no altera ningún parámetro
  investigado.
- SuperTrend **queda plano** si su flip cae dentro de la ventana bloqueada: el CLOSE del lado
  viejo se ejecuta (los cierres nunca se gatean) y el OPEN del lado nuevo espera a las 18:45.
- No hay posiciones abiertas (owner confirmó 2026-07-27); la transición es segura.

## Global Constraints

1. **SEGURIDAD — cuenta.** Sólo DEMO `2883016567`. La cuenta REAL `2883011573` jamás.
   `sentinel_engine/live/guard_cuenta.py::assert_demo` no se debilita, no se bypassea, no se
   modifica. Ningún subagente toca `guard_cuenta.py`.
2. **SEGURIDAD — cierres nunca gateados.** El time-gate aplica EXCLUSIVAMENTE a
   `a.kind == "OPEN"`. MODIFY, CLOSE, exits y cualquier acción de gestión de riesgo deben
   pasar siempre, en cualquier horario. Mismo principio que el spread-gate existente
   (`run_live_20.py:472-502`).
3. **INMUTABILIDAD de los configs compartidos.** Los dicts de `S6-K2P0`, `S7-TPNONE` y
   `SuperTrend-p14x3-M15` están compartidos POR REFERENCIA entre `CONFIGS_GOLIVE`,
   `CONFIGS_GOLIVE_DEDUP` y `CONFIGS_TOMACHINE`. Después de este cambio deben seguir **sin
   key `volume`** y **sin `active_fichas`** en sus `kwargs` (es decir, el default 3).
   Cualquier override va sobre `copy.deepcopy`, siguiendo el patrón `_local_copy`
   (`live_configs_20.py:564-569`).
4. **El roster `local` (máquina 1) no cambia.** `CONFIGS_LOCAL` sigue siendo 4 configs
   (S6/S7/ST @0.1 + TK-Momentum @0.01), magics `[724010, 724020, 724070, 999999998]`.
   Ningún test de `CONFIGS_LOCAL` debe necesitar edición.
5. **Los rosters `live`, `shadow`, `golive`, `golive-dedup`, `tk-momentum` no cambian.**
6. **Compatibilidad por defecto = comportamiento actual.** Con la variable de entorno del
   time-gate sin definir, el argv del ejecutor y su comportamiento quedan byte-idénticos a
   antes de este cambio. La máquina 1 no se ve afectada.
7. **Fail-loud en la config de seguridad.** Una ventana malformada NO arranca el sistema con
   la protección apagada: aborta ruidosamente, igual que hace hoy
   `SUPERVISOR_MAX_SPREAD_OPEN` (`supervisor_live.py:129-144`).
8. **Hora.** Reloj local del equipo == hora del servidor Capitaria == UTC-4. El gate usa el
   reloj **local naive** (`datetime.now()`), NO UTC. Debe ser inyectable para los tests.
9. **Sin `git push`.** La rama es local. No se toca `alvaro`.
10. **Sin ejecutar el stack live.** Ningún subagente lanza, mata ni reinicia el ejecutor,
    el supervisor, el watchdog, la UI ni el terminal MT5. Ningún subagente abre conexión a
    MT5. Sólo código y tests (`pytest`). El despliegue lo hace el controlador.
11. **Tests.** Correr con `python -m pytest` desde la raíz del repo. Los tests nuevos van en
    los archivos de test existentes correspondientes. No se borran tests existentes: se
    actualizan cuando su intención cambió, preservando la propiedad que protegían.

---

## Task 1 — Roster `tomachine` = S6-K2P0 + SuperTrend, ficha única, 0.3 lotes

**Archivos:** `sentinel_engine/strategies/live_configs_20.py`,
`tests/strategies/test_live_configs_tomachine.py`,
`tests/strategies/test_live_configs_local.py`,
`tests/scripts/test_run_live_20.py`

### Cambio de producción

Reemplazar el bloque `CONFIGS_TOMACHINE` (`live_configs_20.py:505-539`) para que el roster
sea exactamente 2 configs, construidos como **deep copies independientes** de los dicts
go-live compartidos:

- `S6-K2P0` — copia con `kwargs["active_fichas"] = 1` y `volume = 0.3`. Magic `724010`
  SIN CAMBIO.
- `SuperTrend-p14x3-M15` — copia con `volume = 0.3`. Magic `724070` SIN CAMBIO.
  **NO** agregarle `active_fichas`: su `kwargs` es `{"symbol": "XAUUSD"}` y el motor
  `supertrend_always_in_target` no acepta ese parámetro; ya emite una sola ficha F1.

`_TOMACHINE_GOLIVE_IDS` pasa a `("S6-K2P0", "SuperTrend-p14x3-M15")`. Los asserts del
módulo se actualizan: 2 configs, ids únicos, y las exclusiones explícitas se amplían a
`S7-TPNONE` y `TK-BW2-fix2atr` además de las que ya están (`V11-M2`,
`TK-Momentum-5-8-short`, los shadow FIXED4). Se conserva la verificación de bandas de
magic disjuntas.

Agregar asserts de módulo nuevos que fijen las dos propiedades que el owner pidió y la
invariante de inmutabilidad:

- cada config de `CONFIGS_TOMACHINE` tiene `volume == 0.3`;
- el config `S6-K2P0` de tomachine tiene `kwargs["active_fichas"] == 1`;
- los dicts go-live compartidos (`_tomachine_golive_by_id` fuentes) NO tienen key `volume`
  y NO tienen `active_fichas` en sus `kwargs`.

Actualizar el comentario de cabecera del bloque para que describa la selección
2026-07-27 (S6 + ST, ficha única, 0.3) y por qué usa copias en vez de referencias
compartidas, citando el reporte de desempeño.

`CONFIG_TK_BW2_FIX2ATR` **se conserva definido** en el módulo (con sus asserts de banda de
magic): sale del roster, no del código. Lo mismo `CONFIGS_TK` / `CONFIG_TK_MOMENTUM`.

### Tests

En `tests/strategies/test_live_configs_tomachine.py`, actualizar los tests del roster para
la nueva forma (los del config TK-BW2 en sí mismo siguen válidos y no se tocan):

- `test_tomachine_is_exactly_four_configs` → dos configs.
- `test_tomachine_ids_and_magics_exact` → `["S6-K2P0", "SuperTrend-p14x3-M15"]` y
  `[724010, 724070]`.
- `test_tomachine_contains_tk_bw2_fix2atr` → invertirlo: TK-BW2 ya NO está en el roster
  (preserva la propiedad "el roster es exactamente la selección del trader").
- `test_tomachine_excludes_v11_m2_and_tk_momentum` → ampliar a S7-TPNONE y TK-BW2-fix2atr.
- Tests nuevos: volumen 0.3 en ambos configs; `active_fichas == 1` en S6; SuperTrend sin
  key `active_fichas` en `kwargs`; los dicts go-live fuente sin `volume` ni
  `active_fichas` (inmutabilidad).

En `tests/strategies/test_live_configs_local.py`: `test_tomachine_configs_have_no_volume_key`
cambia de intención — ahora tomachine SÍ tiene volume propio (0.3). Reescribirlo para que
siga protegiendo la propiedad real: el 0.1 del roster `local` no se filtró a tomachine
(cuyos configs valen 0.3) ni a los dicts go-live compartidos (que siguen sin key `volume`).
Los demás tests de `CONFIGS_LOCAL` no se tocan.

En `tests/scripts/test_run_live_20.py`:

- `test_configs_tomachine_selects_four` → dos configs.
- `test_configs_tomachine_evaluates_tk_bw2_fix2atr_without_error` → ya no aplica al roster
  tomachine; adaptarlo o retirarlo dejando registrado por qué (TK-BW2 salió del roster).
- `test_local_roster_volume_did_not_leak_into_tomachine` → misma reescritura de intención
  que arriba: tomachine vale 0.3, local 0.1/0.01, los compartidos sin `volume`.
- `test_golive_config_objects_shared_not_copied_for_tomachine` → tomachine ya NO comparte
  los dicts (usa copias). Reescribirlo como: los `kwargs` de tomachine son iguales a los
  go-live SALVO `active_fichas`, los magics son idénticos, y los objetos son distintos
  (`is not`).
- `test_armed_rosters_unchanged_by_tomachine_addition` debe seguir pasando sin editarlo.

### Verificación

`python -m pytest tests/strategies/test_live_configs_tomachine.py tests/strategies/test_live_configs_local.py tests/scripts/test_run_live_20.py -q`
en verde, y `python -c "from sentinel_engine.strategies.live_configs_20 import CONFIGS_TOMACHINE; print([(c['id'], c['magic'], c['volume'], c['kwargs'].get('active_fichas')) for c in CONFIGS_TOMACHINE])"`
imprimiendo los dos configs con 0.3 y `active_fichas` 1 / None.

---

## Task 2 — Time-gate de aperturas en el ejecutor

**Archivos:** `scripts/live/run_live_20.py`, `tests/scripts/test_run_live_20.py`

### Cambio de producción

**(a) Reloj inyectable.** Helper a nivel de módulo:

```python
def _local_now() -> datetime:
    """Wall-clock LOCAL time (naive). The Capitaria server clock EQUALS this
    machine's local clock (both UTC-4), so the blocked-open window is expressed
    in the trader's own hours. Indirected through this function so tests can
    monkeypatch the clock."""
    return datetime.now()
```

**(b) Parser fail-loud.** `parse_blocked_open_window(spec: str) -> tuple[time, time]`:

- Acepta exactamente `"HH:MM-HH:MM"`, dos dígitos por campo, 24 horas.
- Devuelve `(start, end)` como `datetime.time`.
- `raise ValueError` con mensaje explícito si: el formato no calza; horas/minutos fuera de
  rango; o `start >= end`. **No se soporta ventana que cruce medianoche** — es una
  limitación deliberada (la ventana pedida es 18:00–18:45) y cruzar medianoche en silencio
  sería peor que rechazarlo.

**(c) Predicado.** `in_blocked_open_window(now: time, window: tuple[time, time] | None) -> bool`
→ `False` si `window is None`; si no, **semiabierto** `start <= now < end`. Con
`18:00-18:45`: 17:59:59 NO bloquea, 18:00:00 bloquea, 18:44:59 bloquea, 18:45:00 NO bloquea.

**(d) El gate.** `execute_action` recibe un kwarg nuevo
`blocked_open_window: tuple[time, time] | None = None`. Dentro del bloque
`if a.kind == "OPEN":` existente (`run_live_20.py:483`), la comprobación de tiempo va
**ANTES** del spread-gate — no requiere leer el tick de MT5, así que gatear primero evita
una llamada innecesaria. Al bloquear:

```
logger.warning("  [TIME_GATE_SKIP] config=%s ficha=%s now=%s within blocked open "
               "window %s-%s (local == Capitaria server time; open deferred, "
               "reconciler re-evaluates next cycle)", ...)
return
```

Aplica igual en dry-run y en armado (el `return` está antes del `if dry_run:`), exactamente
como el spread-gate. Documentar `TIME_GATE_SKIP` en el docstring de `execute_action`, en la
lista de side-effects del audit log, dejando explícito que exits/MODIFY/CLOSE nunca se
gatean.

**(e) Plumbing.** `run_cycle` recibe `blocked_open_window` y lo pasa a cada
`execute_action`. `main` gana el flag:

```
ap.add_argument("--blocked-open-window", type=str, default=None,
                help="OPTIONAL 'HH:MM-HH:MM' local-time window (server time == "
                     "local time, UTC-4) during which NO new position is opened: "
                     "OPENs inside it are SKIPPED (logged TIME_GATE_SKIP) and the "
                     "reconciler retries next cycle. Exits/MODIFY/CLOSE are NEVER "
                     "gated. End is EXCLUSIVE. Default OFF.")
```

`main` parsea el flag con `parse_blocked_open_window`; ante `ValueError` loguea el error a
nivel ERROR y **retorna 2 sin abrir ningún ciclo ni conexión** (fail-loud: arrancar sin la
protección pedida es peor que no arrancar). El banner de arranque
(`run_live_20.py:1062-1064`) suma `blocked_open_window=%s`, imprimiendo `OFF` cuando es
`None`.

### Tests (en `tests/scripts/test_run_live_20.py`)

1. `parse_blocked_open_window("18:00-18:45")` → `(time(18, 0), time(18, 45))`.
2. Malformados que deben levantar `ValueError`: `"18:00"`, `"18:00-"`, `"-18:45"`,
   `"abc-def"`, `"25:00-25:30"`, `"18:60-19:00"`, `"18:45-18:00"` (start > end),
   `"18:00-18:00"` (vacía), `""`.
3. Bordes de `in_blocked_open_window` con la ventana 18:00–18:45: `17:59:59` False,
   `18:00:00` True, `18:30:00` True, `18:44:59` True, `18:45:00` False, `19:00:00` False.
   Y `window=None` → False para cualquier hora.
4. `execute_action` con un OPEN y el reloj dentro de la ventana: **no** se manda orden
   (`mt5.order_send` no se llama), se loguea `TIME_GATE_SKIP`.
5. Mismo caso con el reloj fuera de la ventana: la orden sí se manda.
6. `execute_action` con MODIFY y con CLOSE dentro de la ventana: **sí** se ejecutan
   (los cierres nunca se gatean) — este es el test que protege la Global Constraint 2.
7. El gate corre también en `dry_run=True`: nada se manda y se loguea el skip.
8. `blocked_open_window=None` → ningún OPEN se gatea (comportamiento por defecto intacto).
9. El time-gate corre ANTES del spread-gate: con el reloj dentro de la ventana, no se
   consulta el tick (`mt5.symbol_info_tick` no se llama para el gate de spread).
10. `main(["--once", "--blocked-open-window", "no-es-una-ventana"])` → retorna 2 y no corre
    ningún ciclo.
11. `main(["--once", "--blocked-open-window", "18:00-18:45"])` parsea bien y el banner
    reporta la ventana.
12. `run_cycle` propaga `blocked_open_window` hasta `execute_action`.

El reloj se controla monkeypatcheando `run_live_20._local_now`.

---

## Task 3 — Propagación por el supervisor (auto-lanzado / auto-sanado)

**Archivos:** `scripts/live/supervisor_live.py`, `tests/scripts/test_supervisor_live.py`

### Contexto de integración

El watchdog (`scripts/live/watchdog_local.ps1`) NO setea variables `SUPERVISOR_*`: las
hereda del entorno de usuario, persistido con `setx`. La cadena completa es
`env de usuario → tarea SENTINEL_LIVE_TOMACHINE (AtLogOn) → watchdog → supervisor →
argv del ejecutor`. Por eso el único punto que hay que tocar para que el auto-lanzamiento y
el self-heal preserven el bloqueo es `build_executor_argv`.

### Cambio de producción

Espejar exactamente el patrón de `SUPERVISOR_MAX_SPREAD_OPEN` (`supervisor_live.py:94-145`):

- `SUPERVISOR_BLOCKED_OPEN_WINDOW = os.environ.get("SUPERVISOR_BLOCKED_OPEN_WINDOW")`, con
  un comentario que explique la semántica, que hora local == hora del servidor, que los
  cierres nunca se gatean, y que sin definir no se agrega nada al argv.
- `build_executor_argv` gana el parámetro
  `blocked_open_window: str | None = SUPERVISOR_BLOCKED_OPEN_WINDOW`. Si tiene valor
  no vacío, lo valida con `run_live_20.parse_blocked_open_window` (misma función que el
  ejecutor — una sola verdad sobre el formato, no re-implementar el parseo) y lo agrega
  como `["--blocked-open-window", <valor>]`. Si es vacío/None, el argv queda
  byte-idéntico a hoy.
- Ventana malformada → `_log_watchdog("FATAL: ...")` + `raise SystemExit(2)`, con un mensaje
  que diga explícitamente que se rehúsa a armar el ejecutor sin la protección horaria
  pedida y que hay que corregir o borrar `SUPERVISOR_BLOCKED_OPEN_WINDOW` y reiniciar.
  Mismo tono y estructura que el error de `SUPERVISOR_MAX_SPREAD_OPEN`.
- Actualizar el docstring de `build_executor_argv` y el comentario de `SUPERVISOR_CONFIGS`
  para reflejar que `tomachine` es ahora S6-K2P0 + SuperTrend-p14x3-M15 (2 configs, ficha
  única, 0.3 lotes), no la lista de 8/4 que describe hoy.

El import de `run_live_20` dentro del supervisor debe ser **local a la función** si un
import a nivel de módulo arrastrara dependencias no deseadas o riesgo de ciclo; verificar
qué hace hoy el módulo y elegir la opción coherente con el archivo.

### Tests (en `tests/scripts/test_supervisor_live.py`)

1. `build_executor_argv(blocked_open_window=None)` → argv sin el flag, byte-idéntico al de
   hoy.
2. `build_executor_argv(blocked_open_window="")` → igual, sin flag.
3. `build_executor_argv(configs="tomachine", max_spread_open="0.5",
   blocked_open_window="18:00-18:45")` → contiene `--configs tomachine`,
   `--max-spread-open 0.5` y `--blocked-open-window 18:00-18:45`, y sigue conteniendo
   `--arm` y `--confirm-account <DEMO_LOGIN>`.
4. Ventanas malformadas (al menos `"garbage"`, `"18:00"`, `"18:45-18:00"`) →
   `SystemExit` con código 2.
5. Con `SUPERVISOR_BLOCKED_OPEN_WINDOW=18:00-18:45` en el entorno, un reimport del módulo
   produce `EXECUTOR_ARGV` con el flag (mismo estilo que
   `test_supervisor_env_tomachine` en `tests/scripts/test_run_live_20.py:442`).
6. El test de inmutabilidad de argv existente debe seguir pasando: hoy requiere correr con
   `SUPERVISOR_MAX_SPREAD_OPEN` y `SUPERVISOR_CONFIGS` desactivadas; ahora también
   `SUPERVISOR_BLOCKED_OPEN_WINDOW`. Hacerlo robusto desde el propio test
   (`monkeypatch.delenv(..., raising=False)`) en vez de depender del entorno del que
   invoca — el entorno de esta máquina tiene las tres seteadas.

### Verificación

`python -m pytest tests/scripts/test_supervisor_live.py tests/scripts/test_run_live_20.py -q`
en verde **sin** limpiar variables de entorno a mano.

---

## Despliegue (lo hace el controlador, fuera del loop de subagentes)

1. Verificar 0 posiciones abiertas en las bandas 724020-724023 (S7) y 725010-725013
   (TK-BW2) con una conexión MT5 read-only breve + `mt5.shutdown()` inmediato.
2. `setx SUPERVISOR_BLOCKED_OPEN_WINDOW 18:00-18:45`.
3. Reiniciar el watchdog para que el árbol de procesos herede la variable nueva
   (`setx` no afecta procesos ya vivos).
4. Verificar: argv del ejecutor con `--configs tomachine --max-spread-open 0.5
   --blocked-open-window 18:00-18:45`; guard OK login 2883016567; el log de arranque
   listando 2 configs; ciclos cada ~18s sin gaps > 60s durante ≥10 min.
