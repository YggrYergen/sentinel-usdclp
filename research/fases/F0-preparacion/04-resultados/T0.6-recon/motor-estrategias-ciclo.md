# Recon motor / estrategias vivas / ciclo de posicion -- T0.6

Fecha: 2026-08-11. Rol: INVESTIGADOR REPORT-ONLY (rama `equipo1`). Ningun fichero del repo fue
editado salvo este mismo artefacto. Cero operaciones git. Cero pytest ejecutado.

**Comandos ejecutados** (bash tool, D:\FOREX como cwd; POSIX paths via `/d/FOREX/...`):
```
find /d/FOREX/sentinel_engine -maxdepth 2 -type f -name "*.py" | sort
find /d/FOREX/sentinel_engine -maxdepth 4 -type d | sort
find /d/FOREX/scripts -iname "*run_live*" -o -iname "*reconciler*"
find /d/FOREX/tests -iname "*reconcil*" -o -iname "*emasar*" -o -iname "*live_configs*" \
    -o -iname "*executor*" -o -iname "*risk_gate*" -o -iname "*run_live*"
wc -l /d/FOREX/docs/superpowers/research/2026-07-22-strategy-mechanics-reference.md
wc -l /d/FOREX/scripts/live/run_live_20.py
grep -n "^def test_" tests/strategies/test_emasar_variant.py tests/live/test_reconciler.py \
    tests/live/test_risk_gates.py tests/live/test_executor_dryrun.py tests/scripts/test_run_live_20.py
grep -n "markers\|slow" pytest.ini
grep -rl "pytest.mark.slow" tests/live tests/strategies tests/scripts
```
Mas lecturas directas (`Read`) de los ficheros citados abajo y `Grep` puntuales
(`reentry_enable`, `class _Ficha`, `def ema_series|sar_series|...`, `wrapper`, `direction_mask`).

Se usa como mapa de partida (y se verifica contra fuente, no se copia a ciegas) el informe previo
`docs/superpowers/research/2026-07-22-strategy-mechanics-reference.md` (618 lineas, fechado
2026-07-22, mismo tipo de tarea report-only sobre S6-K2P0/S7-TPNONE/SuperTrend-p14x3-M15/
TK-Momentum). Toda cita de ese documento fue re-verificada leyendo el fichero fuente citado en
esta sesion, salvo donde se indica explicitamente "no re-verificado en esta pasada".

---

## 1. Mapa de las estrategias vivas

Las estrategias vivas **no son modulos/clases separadas**: son **dicts de configuracion** en un
registro central que parametrizan DOS motores compartidos. No hay fichero `s6.py`/`s7.py`/
`supertrend.py`.

**Registro central**: `sentinel_engine/strategies/live_configs_20.py`. Cada config es
`{id, tf, k, kwargs, magic, engine?, direction_filter, notes}`.

- **S6-K2P0**: construido por `_golive_m15("S6-K2P0", ac_modulate=True, trail_atr_floor_k=2.0, ...)`
  (`sentinel_engine/strategies/live_configs_20.py:256-257`), via el helper `_golive_m15()`
  (`:242-252`), a partir de `_GOLIVE_BASE_M15` (`:232-239`). No lleva clave `"engine"` -> el
  executor usa la rama por defecto = `simular_variant`.
- **S7-TPNONE**: `_golive_m15("S7-TPNONE", ac_modulate=False, trail_atr_floor_k=1.5,
  extra=dict(be_at_r=1.0), ...)` (`live_configs_20.py:258-260`). Tambien motor `simular_variant`
  (sin `"engine"`).
- **SuperTrend-p14x3-M15**: dict literal `_GOLIVE_SUPERTREND` (`live_configs_20.py:341-351`),
  `"engine": "supertrend_always_in"` (`:347`). Su "entrada" es la funcion
  `supertrend_always_in_target(bars)` (`:306-338`), definida en el MISMO fichero
  `live_configs_20.py`, no en `sentinel_engine/strategies/emasar_variant.py`.
- Ambos S6/S7 corren sobre `def simular_variant(bars, *, ...)`
  (`sentinel_engine/strategies/emasar_variant.py:86-142`), que a su vez importa indicadores/gates
  de `sentinel_engine/strategies/emasar_ref.py` (fichero marcado "VENDORED FROZEN COPY -- DO NOT
  EDIT", `emasar_ref.py:1-24`).

**Instanciacion (call graph)**: `scripts/live/run_live_20.py::reconcile_config()`
(`scripts/live/run_live_20.py:262-344`) es el unico punto de despacho:
```python
# scripts/live/run_live_20.py:285-316
if cfg.get("engine") == "supertrend_always_in":
    desired = supertrend_always_in_target(bars)
elif cfg.get("engine") == "tk_momentum":
    desired = tk_momentum_5_8_target(bars, trail_usd=cfg["kwargs"].get("trail_usd", 0.5))
    assert len(desired.get("open", {})) <= 1, (...)
elif cfg.get("engine") == "tk_bw2_fix2atr":
    desired = tk_bw2_fix2atr_target(bars[-TK_BW2_LIVE_BAR_CAP:], **engine_kwargs)
else:
    kwargs = dict(cfg["kwargs"])
    if cfg.get("direction_filter"):
        kwargs["direction_mask"] = _direction_mask(bars)
    _events, desired = simular_variant(bars, return_state=True, **kwargs)
```
Confirmado leyendo el fichero directamente; coincide con la cita del informe previo
(`2026-07-22-strategy-mechanics-reference.md:27-36`).

**De donde salen los kwargs**: literales Python en `live_configs_20.py`, copiados byte-a-byte del
manifiesto de la liga honesta `scripts/report/honest_manifest_full_2026_07_20_v3.json` (nota del
propio modulo, `live_configs_20.py:207-220`; no re-verifique el JSON linea por linea en esta
pasada -- ver §9 "no evaluable").

**Rosters que incluyen los tres vivos**:
- `CONFIGS_TOMACHINE` = [S6-K2P0, S7-TPNONE, SuperTrend-p14x3-M15, TK-BW2-fix2atr]
  (`live_configs_20.py:505-530`).
- `CONFIGS_LOCAL` (maquina "equipo1") = [S6-K2P0, S7-TPNONE, SuperTrend-p14x3-M15 @0.1 lot/ficha,
  TK-Momentum-5-8-short @0.01 lot] (`:541-607`), via `_local_copy()` que hace `copy.deepcopy` del
  dict compartido y le anade una clave `volume` a la COPIA, nunca al original (`:564-569`,
  asserts de inmutabilidad `:594-599`).
- `CONFIGS_CHALLENGER` = copias `-R` de los mismos 3 con banda de magic 726xxx + `risk_gates`
  (`:608-701`).

Los dicts `S6-K2P0`/`S7-TPNONE`/`SuperTrend-p14x3-M15` de `CONFIGS_GOLIVE` se comparten POR
REFERENCIA entre `CONFIGS_GOLIVE`, `CONFIGS_GOLIVE_DEDUP` y `CONFIGS_TOMACHINE`
(`live_configs_20.py:549-556`); solo `CONFIGS_LOCAL` y `CONFIGS_CHALLENGER` trabajan sobre
`copy.deepcopy()` independientes.

---

## 2. Bandas magicas (magic numbers)

**No hay una unica constante `MAGIC_BASE`**; hay VARIAS bandas, una por roster/generacion,
definidas todas en `sentinel_engine/strategies/live_configs_20.py` y verificadas con `assert` al
importar el modulo:

| Banda | Base | Rango ficha (base+1..+3) | Roster | Cita |
|---|---|---|---|---|
| CONFIGS_20 (curados) | `720000 + 10*posicion` | 720011..720203 | `CONFIGS_20`/`CONFIGS_LIVE` | `:141-150` |
| SHADOW (FIXED4) | `721000 + 10*(i+1)` | 721011..721043 | `CONFIGS_SHADOW` | `:162-192` |
| GO-LIVE | `724000 + 10*posicion` | 724011..724073 | `CONFIGS_GOLIVE`/`_DEDUP`/`CONFIGS_TOMACHINE`/`CONFIGS_LOCAL` | `:356-376` |
| TK-Momentum | `999999998` (fijo) | 999999999..1000000001 | `CONFIGS_TK` | `:421-451` |
| TK-BW2-fix2atr | `725010` (fijo) | 725011..725013 | dentro de `CONFIGS_TOMACHINE` | `:480-503` |
| CHALLENGER | `726000 + (magic_golive-724000)` | 726011..726073 | `CONFIGS_CHALLENGER` | `:628-700` |

**S6-K2P0** = magic base `724010` (`live_configs_20.py:255-257`, 1a entrada de `_GOLIVE_M15`, loop
`_i, _c in enumerate(CONFIGS_GOLIVE, start=1)` con `_GOLIVE_MAGIC_BASE = 724000` y paso `10*_i`,
`:356-358`). Fichas F1/F2/F3 -> 724011/724012/724013.
**S7-TPNONE** = magic base `724020` (2a entrada, `:258-260`). Fichas 724021/724022/724023.
**SuperTrend-p14x3-M15** = magic base `724070` (6a entrada de la lista `[*_GOLIVE_M15,
_GOLIVE_V11_M2, _GOLIVE_SUPERTREND]`, `:353-354`, confirmado por el propio assert
`assert [c["magic"] for c in CONFIGS_GOLIVE] == [724010,...,724070]` en `:362-364`). Solo F1 se usa
-> 724071.

**Offset por ficha**: `FICHA_OFFSET = {"F1": 1, "F2": 2, "F3": 3}`
(`sentinel_engine/live/reconciler.py:45`), consumido por `reconcile()` como
`base_magic + FICHA_OFFSET[tag]` (`reconciler.py:186,216,230,238,244,252,262,270,274-278`).

**Registro central de atribucion (no de asignacion)**: `data/research.db`, tabla
`magic_allocation(magic PK, strategy_id, variant_id, asignado)`, poblada de forma idempotente
(`INSERT OR IGNORE`, nunca UPDATE/DELETE) por
`sentinel_engine/live/magic_seed.py::ensure_magic_allocations()` (`magic_seed.py:43-65`). El
`strategy_id` se deriva del campo `engine` del config:
```python
# sentinel_engine/live/magic_seed.py:33-40
def _strategy_id(cfg):
    engine = cfg.get("engine", "simular_variant")
    cid = cfg["id"]
    if engine == "supertrend_always_in":
        return f"SuperTrend::{cid}"
    if engine.startswith("tk_") or engine == "tk":
        return f"TK::{cid}"
    return f"SAR::{cid}"
```
Este seeder es READ/INSERT sobre `data/research.db` unicamente; no es la fuente de verdad de los
NUMEROS de magic (esos son literales Python en `live_configs_20.py`) -- es solo el catalogo que
usa la UI/atribucion de deals en tiempo real.

Cada bloque de rango es auditado por `assert`s de disjuncion en el propio modulo (p.ej.
`_live_band.isdisjoint(_shadow_band)` `:190-192`, `_golive_band.isdisjoint(_live_band)` `:373-374`,
etc.) -- no hay una tabla declarativa unica de rangos, son invariantes verificados a import-time.

---

## 3. Ciclo de vida de una posicion en el motor

Dos niveles: (A) el motor de simulacion (`simular_variant`) decide un ESTADO DESEADO; (B) el
`reconciler` diferencia ese estado deseado contra las posiciones MT5 reales y emite acciones.

### 3A. Dentro de `simular_variant` (`sentinel_engine/strategies/emasar_variant.py`)

- **Apertura**: bucle principal `for i in range(n):` (`:704`). La entrada estricta (sin
  reentry/reverse) se evalua en el bloque `if entry_timing in (1,3): ... else: long_ok, _ =
  gate_long(...); short_ok, _ = gate_short(...)` (`:1214-1277`), y el fill/creacion de fichas en
  `if long_ok and allow_long: ... fichas = {t: _Ficha(+1, px_long, sl) for t in active_tags}`
  (`:1410-1425`, mirror short `:1426-1439`).
- **Cierre**: evaluado AL PRINCIPIO de cada iteracion, antes de la entrada, sobre las fichas
  abiertas: `for tag in list(fichas.keys()): f = fichas[tag]; ...` (`:715-`), con checks en orden
  TP-por-R (`:732-754`) -> TP fijo en pips (bloque posterior no citado arriba) -> initial-SL
  (`:780-799` aprox.) -> breakeven (`:801-838`) -> ratchet (`:840-901`) -> wait-MAE/BE (`:903-953`)
  -> trailing (`:955-1045` aprox.) -> AC-decel-exit -> time-stop (`:1063-1076`).
- **Objeto posicion abierta**: `_Ficha`, definido en `emasar_ref.py:254-264` (importado, NO
  redefinido en `emasar_variant.py`):
  ```python
  # sentinel_engine/strategies/emasar_ref.py:254-264
  class _Ficha:
      __slots__ = ("lado", "entry", "sl", "max_fav", "abierta", "es_runner", "stall_consec")
      def __init__(self, lado, entry, sl, es_runner=False):
          self.lado = lado          # +1 long, -1 short
          self.entry = entry
          self.sl = sl
          self.max_fav = entry
          self.abierta = True
          self.es_runner = es_runner
          self.stall_consec = 0
  ```
  Campos: `lado` (+1/-1), `entry` (float), `sl` (float, muta), `max_fav` (float, muta),
  `abierta` (bool), `es_runner` (bool, no usado por `simular_variant`, es de `emasar_ref.simular`),
  `stall_consec` (int, idem). Es `__slots__` (frozen en el sentido de "sin atributos extra"), por
  eso el motor lleva contadores auxiliares FUERA del objeto (`entry_bar_by_tag`,
  `sl_inicial_by_tag`, `r_by_tag`, `server_sl_by_tag`, todos dicts locales al bucle, `:660-702`).
- **Salida del motor (snapshot)**: cuando `return_state=True`, tras el bucle, el motor construye
  `{"open": {tag: {"side","entry","sl","max_fav"}}, "last_bar_exits": {...}, "last_idx": n-1}` --
  este es el "objeto posicion abierta" que ve el resto del sistema (reconciler). No pude fijar la
  linea exacta del bloque de construccion final en esta pasada (esta despues de `:1441`, dentro de
  un bloque largo no citado arriba; el docstring lo describe en `:1441-1449` pero el `return`
  mismo no se transcribio -- ver §9).

### 3B. Reconciliacion contra MT5 (`sentinel_engine/live/reconciler.py`)

```python
# sentinel_engine/live/reconciler.py:114-126
def reconcile(
    config_id: str,
    base_magic: int,
    desired_state: dict[str, Any],
    live_positions: list[dict[str, Any]],
    *,
    volume: float = 0.01,
    bar_t: int | None = None,
    sl_tol: float = 0.05,
    kill_switch: bool = False,
    total_open_fichas: int = 0,
    contract_size: float = 100.0,
) -> ReconcileResult:
```
Orden interno (docstring `:147-149`, verificado en el cuerpo): 1) CLOSE de huerfanos
(`:183-205`), 2) MODIFY de SL desalineado (`:208-246`), 3) OPEN de fichas deseadas sin posicion
viva (`:249-278`). Devuelve `ReconcileResult(config_id, base_magic, bar_t, actions: list[Action])`
(`:75-84`). `Action` es un dataclass:
```python
# sentinel_engine/live/reconciler.py:50-72
@dataclass
class Action:
    kind: str      # OPEN|CLOSE|MODIFY|NOOP|REJECT_VOLUME|REJECT_CAP|
                    # SUPPRESSED_OPEN|SAME_BAR_EXIT_FALLBACK|MISSING_SL_ALARM
    config_id: str
    magic: int
    ficha: str      # F1/F2/F3
    side: str | None = None
    volume: float | None = None
    price_ref: float | None = None
    sl: float | None = None
    ticket: int | None = None
    sim_fill: float | None = None
    motivo: str | None = None
    reason: str = ""
```
El envio real de ordenes (o el log en dry-run) ocurre en `execute_action()`
(`scripts/live/run_live_20.py:428-`), que llama a la API MT5 solo si `--arm` esta activo.

---

## 4. Salidas y proteccion de utilidad (SL / TP / trailing / ratchet)

Todo dentro de `sentinel_engine/strategies/emasar_variant.py::simular_variant`, parametros
declarados en la firma (`:86-142`).

- **SL inicial ("range-SL")**: `_sl_inicial(lado, idx)` (`:621-624`):
  ```python
  def _sl_inicial(lado, idx):
      rango = bars[idx]["high"] - bars[idx]["low"]
      return (bars[idx]["low"] - init_sl_range_k * rango) if lado == +1 \
          else (bars[idx]["high"] + init_sl_range_k * rango)
  ```
  Parametro: `init_sl_range_k: float = 1.0`. Version acotada por MAE (`wait_mae_atr_k`):
  `_sl_inicial_bounded(lado, idx, entry_px)` (`:626-`).
- **TP por R-multiple**: `f1_tp_r`, `f2_tp_r` (default `0.0` = desactivado), F1/F2 solamente, F3
  nunca hace TP (`:732-754`, `tp_by_tag = {"F1": f1_tp_r, "F2": f2_tp_r}` en `:662`).
- **TP fijo en pips**: `tp_min_pips: float | None = None` -- aplica a F1/F2/F3, target fijo
  `entry +/- tp_min_pips*pip` (documentado `:406-424`, no re-cite el bloque de codigo en esta
  pasada).
- **Trailing por ficha**: `f1_trail_pips/f2_trail_pips/f3_trail_pips` (pips) o
  `f1_trail_range_k/f2_trail_range_k/f3_trail_range_k` (multiplo del rango de la barra) segun
  `trail_mode_ladder: str = "pips"` (`"pips"|"range"`). Calculo efectivo (`:955-971`):
  ```python
  if trail_mode_ladder == "range":
      trail_efectivo = trail_range_by_tag[tag] * (bar["high"] - bar["low"])
  else:
      trail_efectivo = trail_by_tag[tag]
  if ac_modulate and ac_desacelerando(ac, i, f.lado):
      trail_efectivo = trail_efectivo * ac_modulate_factor
  if atr14_floor is not None and atr14_floor[i] is not None:
      trail_efectivo = max(trail_efectivo, trail_atr_floor_k * atr14_floor[i])
  ```
- **AC-modulate**: `ac_modulate: bool = False`, `ac_modulate_factor: float = 0.5` -- multiplica
  (tightening) la distancia de trailing cuando `ac_desacelerando(ac, i, f.lado)` es True
  (`emasar_ref.py`, funcion importada).
- **Piso ATR del trail**: `trail_atr_floor_k: float = 0.0` -- `trail_efectivo = max(trail_efectivo,
  trail_atr_floor_k * ATR14[i])`, aplicado DESPUES del pips/range y del AC-modulate (`:967-971`,
  "es la ultima palabra" segun el docstring `:334-339`).
- **Breakeven**: `be_at_r: float = 0.0`, `be_offset_pips: float = 0.5` (`:801-838`):
  ```python
  if be_at_r > 0.0:
      r_dist = abs(f.entry - sl_inicial_by_tag[tag])
      if f.lado == +1:
          f.max_fav = max(f.max_fav, bar["high"])
          if r_dist > 0.0 and f.max_fav >= f.entry + be_at_r * r_dist:
              be_floor = f.entry + be_offset_pips * pip
              if f.sl is None or be_floor > f.sl:
                  f.sl = be_floor
      # (mirror short con min/`<=`)
  ```
- **Ratchet/chandelier (lock de ganancia, PX-T1)**: `ratchet_lock_frac: float = 0.0`,
  `ratchet_arm_r: float = 1.0`, `ratchet_atr_k: float = 0.0` -- mutuamente exclusivos
  (`ValueError` en `:537-541` si ambos > 0). Codigo (`:859-882`):
  ```python
  if ratchet_lock_frac > 0.0 or ratchet_atr_k > 0.0:
      r_dist = abs(f.entry - sl_inicial_by_tag[tag])
      if f.lado == +1:
          f.max_fav = max(f.max_fav, bar["high"])
          if r_dist > 0.0 and f.max_fav >= f.entry + ratchet_arm_r * r_dist:
              if ratchet_lock_frac > 0.0:
                  ratchet_floor = f.entry + ratchet_lock_frac * (f.max_fav - f.entry)
              elif atr14_floor is not None and atr14_floor[i] is not None:
                  ratchet_floor = f.max_fav - ratchet_atr_k * atr14_floor[i]
              else:
                  ratchet_floor = None
              if ratchet_floor is not None and (f.sl is None or ratchet_floor > f.sl):
                  f.sl = ratchet_floor
      # (mirror short)
  ```
- **Wait-MAE / wait-BE (PX-T2)**: `wait_mae_atr_k: float = 0.0`, `wait_be_exit: bool = False`.
  `wait_mae_atr_k > 0` EXIGE `max_hold_bars is not None` (guard `ValueError`, `:548-552`).
- **Trail-arm-delay (PX-T3)**: `trail_arm_r: float = 0.0` -- retrasa el INICIO del trailing hasta
  que `f.max_fav` alcance `entry + trail_arm_r*R`.
- **Time-stop**: `max_hold_bars: int | None = None` -- cierra a mercado (`px`) tras N barras desde
  `entry_bar_by_tag[tag]` (`:1070-1076`).
- **live_fill_mode**: `live_fill_mode: bool = False` -- cuando True, los checks intrabar usan
  `server_sl_by_tag.get(tag, f.sl)` (el nivel resting AL CIERRE de la barra i-1), no el nivel recien
  elevado en la propia barra i; con "same-bar fallback" si el nuevo nivel ya seria violado por el
  cierre de la propia barra i (`:305-333` docstring; `sl_check = server_sl_by_tag.get(tag, f.sl) if
  live_fill_mode else f.sl`, `:730`).
- **Stop-loss efectivo en vivo (SuperTrend-p14x3-M15)**: NO usa ninguno de los mecanismos
  anteriores -- `sl = line[-1]` es la propia banda SuperTrend
  (`sentinel_engine/strategies/live_configs_20.py:336`), recalculada/"trailed" cada barra por
  definicion del indicador.
- **Clamp MT5-legal**: `_clamp_sl(mt5, symbol, side, desired_sl)`
  (`scripts/live/run_live_20.py:384-408`) -- ajusta el SL deseado al minimo legal del broker
  (`trade_stops_level`/`trade_freeze_level`) antes de enviarlo; devuelve `("crossed"|"clamp"|
  "legal", valor)`.

---

## 5. `reentry_enable`

Parametro `reentry_enable: bool = False`, `reentry_max: int = 1`
(`sentinel_engine/strategies/emasar_variant.py:121-122`). Estado de bucle:
```python
# emasar_variant.py:671-679
signal_exit_motivos: list[str] = []
reentry_armed = False
reentry_lado = 0
reentry_count = 0
```

**Bloque 1 -- registrar motivos de salida de la senal actual** (`:1078-1084`):
```python
if reentry_enable:
    for ev in eventos[_n_eventos_before_exits:]:
        if ev["motivo"].startswith("EXIT"):
            signal_exit_motivos.append(ev["motivo"])
```

**Bloque 2 -- armar re-entrada cuando la ultima ficha de la senal cierra** (`:1097-1105`):
```python
fichas = {k: v for k, v in fichas.items() if v.abierta}
if reentry_enable and not fichas and signal_exit_motivos:
    if all(m == "EXIT_TRAIL" for m in signal_exit_motivos) and reentry_count < reentry_max:
        reentry_armed = True
    signal_exit_motivos = []
```
Condicion literal que dispara `reentry_armed = True`: TODAS las 3 fichas de la senal cerraron
(`not fichas`), habia motivos de salida registrados (`signal_exit_motivos` no vacio), y **CADA**
motivo registrado era exactamente `"EXIT_TRAIL"` (ningun `EXIT_INITSL`/`EXIT_TP`/`EXIT_ACDECEL`/
`time_stop`/`reverse` en la lista), Y `reentry_count < reentry_max`.

**Bloque 3 -- cancelar el armado si el SAR flipa** (`:1161-1167`):
```python
if reentry_armed and sar_trend[i] is not None and sar_trend[i] != reentry_lado:
    reentry_armed = False
    reentry_lado = 0
```

**Bloque 4 -- disparo de la re-entrada** (`:1177-1212`):
```python
if reentry_armed and sar_trend[i] == reentry_lado:
    if entry_timing == 1:
        # toque intrabar (_toque_long/_toque_short)
        ...
    else:
        g3_ok = _gate_g3_only(bars, ema_f, i, reentry_lado)
        reentry_px = px
    if g3_ok and _gate_g1_g4_only(ema_f, ema_s, sar_trend, i, reentry_lado):
        lado_txt = "L" if reentry_lado == +1 else "S"
        eventos.append({"idx": i, "lado": lado_txt, "precio": reentry_px,
                        "motivo": "ENTRY_L" if reentry_lado == +1 else "ENTRY_S", "ficha": None})
        sl = _sl_inicial_bounded(reentry_lado, i, reentry_px)
        fichas = {t: _Ficha(reentry_lado, reentry_px, sl) for t in active_tags}
        sl_inicial_by_tag = {t: sl for t in active_tags}
        server_sl_by_tag = {t: sl for t in active_tags}
        r_dist = abs(reentry_px - sl)
        r_by_tag = {t: r_dist for t in active_tags}
        ac_decel_consec_by_tag = {}
        entry_bar_by_tag = {t: i for t in active_tags}
        signal_exit_motivos = []
        reentry_count += 1
        if reentry_count >= reentry_max:
            reentry_armed = False
            reentry_lado = 0
        continue
```
Condicion literal que dispara la re-entrada EN CADA BARRA subsiguiente mientras esta armada:
`reentry_armed AND sar_trend[i] == reentry_lado` (direccion original) AND `g3_ok` (pullback: con
`entry_timing==1` es el toque intrabar; en caso contrario `_gate_g3_only(bars, ema_f, i,
reentry_lado)`, formula copiada literal del G3 de `gate_long`/`gate_short`) AND
`_gate_g1_g4_only(ema_f, ema_s, sar_trend, i, reentry_lado)` (G1 EMA-order + G2 mismo-slope + G4
SAR-trend, formula copiada de `gate_long`/`gate_short`, **sin** G5/confirmacion de osciladores --
por eso el docstring lo llama "G5-bypassed", `:263-289`).

`_gate_g1_g4_only`/`_gate_g3_only` (`emasar_variant.py:46-83`): funciones locales que reimplementan
G1/G2/G3/G4 con las MISMAS formulas que `emasar_ref.gate_long`/`gate_short`, porque ese fichero es
frozen y no expone un bypass de G5 como parametro.

**Reset a lineage nueva**: toda entrada ESTRICTA (no re-entrada) resetea
`signal_exit_motivos = []; reentry_armed = False; reentry_lado = +1/-1; reentry_count = 0`
(`:1420-1425` long, `:1436-1439` short).

De los tres vivos, ninguno tiene `reentry_enable=True` en sus kwargs efectivos de go-live
(`_GOLIVE_BASE_M15`, `live_configs_20.py:232-239`, no incluye `reentry_enable`; ni `_golive_m15`
lo agrega para S6-K2P0/S7-TPNONE) -- el lever esta definido en el motor pero INACTIVO para los tres
vivos actuales. Configs de `CONFIGS_20` que SI lo usan: `SS-*` (`_SS_EXTRAS`,
`live_configs_20.py:71-72`), `V13-*` (`:99,103,121`).

---

## 6. Concurrencia y direccion

**Direccion**: `allow_long: bool = True`, `allow_short: bool = True`
(`emasar_variant.py:103-104`) -- flags a nivel de motor, no usados por ninguno de S6-K2P0/S7-TPNONE
(quedan en su default `True/True`, no aparecen en `_GOLIVE_BASE_M15` ni en los per-cell deltas). No
hay ningun otro flag de restriccion direccional en `simular_variant`. SuperTrend-p14x3-M15 tampoco
restringe direccion (siempre desea una posicion, en el lado que indique la tendencia). Para
TK-Momentum, el codigo soporta ambos lados (`tk_momentum.py`, no auditado linea por linea en esta
pasada -- ver informe previo `2026-07-22-strategy-mechanics-reference.md:423-429`, que ya lo marca
como ambiguedad sin resolver: el sufijo "-short" del id NO corresponde a una restriccion de codigo
verificada).

**Concurrencia dentro de UNA senal (una llamada a `simular_variant`)**: NO hay pyramiding. El choke
clasico es `if fichas: continue` (`emasar_variant.py:1117`), bypaseado UNICAMENTE por
`stop_and_reverse=True` para una senal en direccion OPUESTA (`:1117-1159`), que primero cierra
todas las fichas abiertas (motivo `"reverse"`) y luego, en la MISMA barra, abre el lado opuesto por
el camino de entrada normal. `stop_and_reverse=True` esta activo en S6-K2P0 y S7-TPNONE
(`_GOLIVE_BASE_M15`, `live_configs_20.py:236`). Senal en la MISMA direccion (o ninguna) mientras hay
posicion abierta: se ignora (`continue`).

**Concurrencia entre estrategias/configs (nivel reconciler, cross-strategy)**:
```python
# sentinel_engine/live/reconciler.py:41-45
MAX_VOLUME = 0.10
MAX_FICHAS_PER_CONFIG = 3
MAX_FICHAS_TOTAL = 60
FICHA_TAGS = ("F1", "F2", "F3")
```
`MAX_VOLUME` se aplica por-ficha en el paso OPEN (`REJECT_VOLUME` si `volume > MAX_VOLUME`,
`reconciler.py:253-259`). `MAX_FICHAS_TOTAL=60` se aplica across TODOS los configs pasados en la
misma corrida del daemon, via el contador `total_open_fichas` que el LLAMADOR (`run_live_20.py`)
acumula entre configs dentro del mismo ciclo (`REJECT_CAP` si `running_total >= MAX_FICHAS_TOTAL`,
`reconciler.py:260-267`). `MAX_FICHAS_PER_CONFIG = 3` esta declarado como constante pero **no se
referencia en ningun `if` del cuerpo de `reconcile()`** en esta pasada -- estructuralmente ya esta
acotado porque solo existen 3 tags (`FICHA_TAGS`), asi que el cap no necesita enforcement explicito
adicional; no encontre un test que lo ejercite como violacion directa (ver §9).

**Cap adicional opt-in (solo CHALLENGER, via `risk_gates`)**: `max_open_fichas` (B3), ver §7.

**Riesgo de netting no verificado**: no encontre en esta pasada codigo que consulte el modo de
margen de la cuenta MT5 (`ACCOUNT_MARGIN_MODE_RETAIL_NETTING` vs `_HEDGING`); el diseno del
reconciler (bandas de magic por config) asume implicitamente HEDGING. No re-audite esto a fondo en
esta sesion -- coincide con el gap #3 ya senalado en el informe previo
(`2026-07-22-strategy-mechanics-reference.md:586-597`).

---

## 7. Wrapper / masks

Dos mecanismos DISTINTOS conviven bajo ese nombre en el repo, ambos fuera de `simular_variant`:

### 7a. `direction_mask` (mascara de regimen, parametro de `simular_variant`)
`direction_mask: list[int] | None = None` (`emasar_variant.py:120`) -- un valor por barra
(+1 solo-largo / -1 solo-corto / 0 ambos), calculado por el LLAMADOR (nunca dentro del motor) via
`compute_direction_mask()` (`scripts/report/gen_variant_batch5.py:210-245`), que resamplea a M15,
corre SuperTrend(14, 3.0) y mapea cada barra a la tendencia de la barra M15 CERRADA anterior (sin
look-ahead). En produccion, el executor lo invoca solo si `cfg.get("direction_filter")` es True
(`scripts/live/run_live_20.py:254-256,314-315`) -- **ninguno de S6-K2P0/S7-TPNONE/
SuperTrend-p14x3-M15 tiene `direction_filter=True`** (solo `V10-M5`/`V10-M15` en `CONFIGS_20` lo
usan, `live_configs_20.py:114-119`).

### 7b. `risk_gates` (mascaras de veto B1-B4, `sentinel_engine/live/risk_gates.py`)
Es un mecanismo OPT-IN a nivel de CONFIG (clave `risk_gates` en el dict, ausente = no se evalua
nada, comportamiento identico al de antes de que existiera este modulo). Interfaz:
```python
# sentinel_engine/live/risk_gates.py:32-58
@dataclass(frozen=True)
class GateInput:
    now: datetime
    spread_ok_since: datetime | None
    open_fichas: int
    desired_sl: float | None
    market_ref: float | None
    news_windows: tuple[tuple[datetime, datetime], ...] | None

@dataclass(frozen=True)
class GateDecision:
    allow: bool
    gate: str
    reason: str

def evaluate_open_gates(gates: dict[str, Any] | None, gi: GateInput) -> GateDecision: ...
```
Cuatro gates evaluados en ORDEN FIJO B1->B2->B3->B4 (la PRIMERA denegacion se reporta):
- **B1** `gap_wait_minutes`: no abrir hasta N min despues de que el spread empezo a imprimir fino
  tras una reapertura de sesion.
- **B2** `news_blackout_minutes`: no abrir dentro de +/-N min de un evento del calendario.
  FAIL-CLOSED: sin calendario disponible -> nunca abre.
- **B3** `max_open_fichas`: tope de fichas simultaneas EN el sleeve (en unidades de fichas, no de
  lotes).
- **B4** `min_sl_distance`: rechaza un SL mas cerca que el minimo del broker (marcado en el propio
  codigo como "THIS IS A BUG", no un filtro de tuning).

Solo se llama desde `execute_action()`, y solo para acciones `kind == "OPEN"` de un config que
lleve `risk_gates` (`scripts/live/run_live_20.py:541-560`). El `GateCycleContext` (now,
spread_ok_since, news_windows, open_fichas) se construye UNA vez por ciclo por
`_build_gate_ctx(mt5, challenger_cfgs)` (`run_live_20.py:763-793`), y `open_fichas` se incrementa
en admision (no en fill) para que B3 tambien acote DENTRO de un mismo ciclo.

**Ninguno de S6-K2P0/S7-TPNONE/SuperTrend-p14x3-M15 lleva `risk_gates`** en `CONFIGS_GOLIVE`; el
mecanismo solo se activa hoy para `CONFIGS_CHALLENGER` (las copias `-R`,
`CHALLENGER_RISK_GATES = {"gap_wait_minutes": 50, "news_blackout_minutes": 30, "max_open_fichas":
7, "min_sl_distance": 0.50}`, `live_configs_20.py:638-643`).

Hay ademas un informe de VEREDICTOS de estas mascaras aplicadas post-hoc sobre 2542 posiciones
reconstruidas (`docs/superpowers/research/2026-07-25-wrapper-mask-verdicts.md`): B1 "NO VETO", B2
"kept_n == total_n" (0 dropped), B3 "expected ZERO drops (cap == peak observado)", B4 "NOT
MASKABLE" (no evaluable desde los CSV de posiciones, falta columna SL). Ese documento usa el
lenguaje "wrapper" para referirse exactamente a `risk_gates.py` + su substrato de evaluacion, no a
un tercer mecanismo adicional.

No encontre ningun modulo llamado literalmente `wrapper.py` o clase `Wrapper` en
`sentinel_engine/**` ni en `scripts/live/**` en esta pasada.

---

## 8. Indicadores disponibles al decidir entrada/salida

**Estructura que transporta las barras**: `list[dict[str, Any]]`, cada barra
`{"t": int (epoch seg), "open": float, "high": float, "low": float, "close": float}` -- shape fijado
por `fetch_bars()`:
```python
# scripts/live/run_live_20.py:211-229
def fetch_bars(mt5, symbol, tf, window, *, include_forming: bool = False) -> list[dict[str, Any]]:
    timeframe = getattr(mt5, f"TIMEFRAME_{tf}")
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, window + 1)
    if rates is None or len(rates) < 2:
        return []
    bars = [{"t": int(r["time"]), "open": float(r["open"]),
             "high": float(r["high"]), "low": float(r["low"]),
             "close": float(r["close"])} for r in rates]
    return bars if include_forming else bars[:-1]
```
Por defecto EXCLUYE la barra en formacion (`include_forming=False`); solo TK-Momentum (con
`intrabar=True` en sus kwargs) la incluye (`run_live_20.py:271-273`).

**Timeframes soportados por el executor**: `TF_MT5_MINUTES = {"M1":1,"M2":2,"M5":5,"M6":6,
"M10":10,"M15":15}`, `TF_SECONDS = {"M1":60,"M2":120,"M5":300,"M6":360,"M10":600,"M15":900}`
(`run_live_20.py:72-73`). S6-K2P0/S7-TPNONE/SuperTrend-p14x3-M15 usan **M15**
(`live_configs_20.py:255,258,341`, campo `"tf"` de cada config).

**Cómputo de indicadores** (dentro de `simular_variant`, sobre listas paralelas `highs/lows/closes`
extraidas de `bars`, `emasar_variant.py:554-563`), todas funciones importadas de `emasar_ref.py`:
```python
def ema_series(closes, period)                     # emasar_ref.py:43
def sar_series(highs, lows, step, max_step)         # emasar_ref.py:58 -> (sar_val, sar_trend)
def ao_series(highs, lows)                          # emasar_ref.py:100
def ac_series(highs, lows)                          # emasar_ref.py:109
def momentum_series(closes, period)                 # emasar_ref.py:117
def gate_long(bars, ema8, ema20, ema5, sar_trend, ao, ac, mom, i, *,
              confirm_mode, use_ema5, confirm_count=2,
              ac_mag_threshold=0.0, skip_g3=False, require_ema_order=True)   # emasar_ref.py:176
def gate_short(bars, ema8, ema20, ema5, sar_trend, ao, ac, mom, i, *, ...)   # emasar_ref.py:213
def pip_size(symbol, pipsize_input=0.0)              # emasar_ref.py:244 -> XAUUSD=0.01
def _atr_wilder(highs, lows, closes, period)         # emasar_ref.py:589
```
`sar_adaptive=True` (activo en S6-K2P0 y S7-TPNONE) computa DOS series SAR (`sar_fast=(0.3,0.3)`,
`sar_slow=(0.005,0.05)`) mas ATR14, y selecciona por barra la serie "fast"/"slow" segun si
`atr14[i]` supera la mediana movil de las ultimas `vol_regime_window=200` barras
(`emasar_variant.py:568-584`).

**Acceso**: todo indicador es una LISTA alineada por indice `i` con `bars` (misma longitud `n`);
se accede como `ema_f[i]`, `sar_trend[i]`, etc. Ningun indicador vive en un objeto/clase
"contenedor" -- son listas sueltas pasadas explicitamente por parametro a cada gate/ficha.

**SuperTrend-p14x3-M15**: motor totalmente distinto, un unico indicador. `_atr_wilder` (mismo de
arriba, importado desde `emasar_ref.py`) + `supertrend(highs, lows, closes, atr, mult)`
(`sentinel_engine/strategies/_supertrend_ref.py:19-43`, no re-leido linea por linea en esta pasada
-- confirmado solo su punto de entrada y su import en `live_configs_20.py:319-320`).

---

## 9. Tests existentes

No se ejecuto pytest (prohibido por el brief). Listado por `grep -n "^def test_"` sobre los
ficheros; rutas y nombres exactos:

**`tests/strategies/test_emasar_variant.py`** (motor `simular_variant`, incluye reentry):
- `test_reentry_default_matches_pre_extension_events_synthetic` (:752)
- `test_reentry_default_matches_pre_extension_events_real_m5` (:762)
- `test_reentry_enabled_adds_entries_and_only_after_all_trail_exit` (:772)
- `test_reentry_max_1_vs_2_more_reentries_allowed_with_higher_max` (:799)
- `test_reentry_synthetic_trigger_case_fires_only_after_all_trail_exit_same_trend` (:811)
(mas tests de otros levers en el mismo fichero, no listados aqui -- fuera del alcance de esta
seccion). Ficheros hermanos con un lever cada uno: `tests/strategies/test_emasar_confirmbar.py`,
`test_emasar_fichacount.py`, `test_emasar_livefill_state.py`, `test_emasar_pullbacklimit.py`,
`test_emasar_sar.py`, `test_emasar_timestop.py`, `test_emasar_tp_min.py`.

**`tests/strategies/test_emasar_ref.py`**: golden test del fichero vendored/frozen (no listado
funcion por funcion en esta pasada).

**`tests/strategies/test_live_configs_20.py`**, `test_live_configs_local.py`,
`test_live_configs_tomachine.py`: pinning de que los kwargs de cada config coinciden byte-a-byte
con su fuente (manifiesto honesto / runner de investigacion).

**`tests/live/test_reconciler.py`** (motor de reconciliacion, `sentinel_engine/live/reconciler.py`):
`test_open_missing_fichas` (:26), `test_close_orphan_no_exit` (:37),
`test_same_bar_exit_fallback` (:44), `test_sl_update` (:55), `test_noop_when_in_sync` (:62),
`test_missing_sl_alarm_and_modify` (:68), `test_volume_cap_rejects` (:76),
`test_total_ficha_cap_rejects` (:82), `test_kill_switch_suppresses_open_not_logging` (:88),
`test_kill_switch_still_closes` (:95), `test_wrong_side_closes_to_resync` (:102),
`test_magic_band_isolation` (:109).

**`tests/live/test_risk_gates.py`** (mascaras B1-B4, `sentinel_engine/live/risk_gates.py`):
`test_no_gates_always_allows` (:22), `test_b1_denies_before_the_wait_elapses` (:32),
`test_b1_allows_once_the_wait_elapsed` (:39),
`test_b1_denies_when_the_thin_regime_never_started` (:45),
`test_b2_fails_closed_without_a_calendar` (:50),
`test_b2_denies_inside_a_window_and_allows_outside` (:56),
`test_b2_boundaries_are_inclusive` (:65), `test_b3_denies_at_and_above_the_cap` (:74),
`test_b4_flags_an_illegal_sl_as_a_bug` (:80), `test_b4_allows_a_legal_sl_on_either_side` (:87),
`test_b4_fails_closed_when_it_cannot_verify` (:94), `test_gate_order_is_b1_b2_b3_b4` (:99).

**`tests/live/test_executor_dryrun.py`** (executor completo, dry-run): incluye
`test_parity_desired_state_matches_sim` (:188, parametrizado por config id),
`test_supertrend_reconciles_to_single_open_when_flat` (:633),
`test_supertrend_flip_closes_wrong_side_then_reopens` (:650), mas ~25 tests de clamp de SL,
confirmacion de cuenta, spread gate, roster selection (lista completa disponible en el fichero,
no transcrita entera aqui por espacio).

**`tests/scripts/test_run_live_20.py`** (CLI/roster wiring, incluye challenger/risk_gates):
`test_configs_tomachine_selects_four` (:248), `test_configs_local_selects_four` (:309),
`test_challenger_roster_is_exactly_three_mirrored_configs` (:506),
`test_challenger_signals_are_byte_identical_to_the_champion` (:517),
`test_challenger_carries_all_four_gates` (:528),
`test_champion_only_roster_never_builds_a_gate_context` (:606), mas ~30 tests de bandas de magic
disjuntas, volumen por config, y wiring de supervisor (lista completa en el fichero).

**Suites dirigidas / marcadores**: `pytest.ini` define `addopts = -m "not slow"` con un unico
marcador `slow` ("heavy replay/optimizer tests que puntuan datos reales de mercado", `pytest.ini:9,
11-12`). Ningun fichero bajo `tests/live/`, `tests/strategies/` o `tests/scripts/` (los que cubren
las 9 secciones de este informe) esta marcado `@pytest.mark.slow` -- verificado con
`grep -rl "pytest.mark.slow" tests/live tests/strategies tests/scripts` (0 resultados). No
determine desde codigo cual comando exacto de CI/runner dirige especificamente estas suites (el
CHARTER §C menciona `tests/analysis`, `tests/live` como ejemplos de suites dirigidas, pero no
encontre en esta pasada un manifest declarativo que enumere `tests/strategies`/`tests/scripts` como
suite nombrada -- ver §10).

---

## 10. Lo que NO pude determinar (declarado explicitamente, sin inventar)

1. **Linea exacta del `return` final de `simular_variant` bajo `return_state=True`** (la
   construccion literal del dict `{"open":...}` que se devuelve). Le el docstring que lo describe
   (`emasar_variant.py:1441-1449`) pero no transcribi el bloque de codigo posterior (fuera de la
   ventana de lectura de esta sesion) -- no evaluable en esta pasada sin una lectura adicional del
   tramo `:1450-fin` del fichero.
2. **`sentinel_engine/strategies/tk_momentum.py`**: no lo lei linea por linea en esta sesion; toda
   cita sobre el en este informe (§6, direccionalidad) proviene del informe previo
   2026-07-22, re-etiquetada como "no re-verificado en esta pasada", no como hecho propio.
3. **`sentinel_engine/strategies/_supertrend_ref.py`**: solo confirme su punto de entrada
  (`supertrend(...)`) y su import; no transcribi la formula completa en esta pasada (si esta
  transcrita en el informe previo, `2026-07-22-strategy-mechanics-reference.md:353-364`, pero no la
  re-verifique yo mismo linea por linea).
4. **`data/lake_ticks_ava/`**: no tocado, por instruccion explicita (proceso de ingesta activo).
5. **Modo de margen de la cuenta MT5 (netting vs hedging)**: no encontre codigo que lo consulte;
   declarado como no evaluable, igual que en el informe previo (gap #3 alli).
6. **Fichero de arranque/entorno de la maquina "equipo1" (launch script fuera del repo)**: no
   localizado; por tanto no puedo confirmar desde codigo si el gate de spread adaptativo esta
   forzado via variable de entorno en esa maquina especifica (el DEFAULT de codigo para el roster
   `local` es adaptativo OFF salvo forzado, `run_live_20.py:993-997` segun el informe previo, no
   re-verificado por mi en esta pasada).
7. **Manifiesto declarativo de "suites dirigidas" por nombre** (mas alla de lo que dice el CHARTER
   §C en prosa): no encontre un fichero tipo `protocolos/06-runners.md` o similar que enumere
   `tests/strategies`/`tests/scripts` como suite nombrada formalmente para este dominio -- solo
   infiero la agrupacion por convencion de directorio.
8. **`MAX_FICHAS_PER_CONFIG = 3`** (`reconciler.py:42`): declarado pero no vi un `if` que lo
   consuma explicitamente en el cuerpo de `reconcile()` en esta pasada (el limite estructural via
   `FICHA_TAGS = ("F1","F2","F3")` lo hace redundante, pero no verifique si existe enforcement
   explicito en otro punto del codigo, p.ej. en `run_live_20.py`).
