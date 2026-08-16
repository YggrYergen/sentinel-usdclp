# WP-1+2 — Reporte final: harness pareado, parámetros expuestos e instrumentación

**Rol:** IMPLEMENTADOR (Sonnet 5 high effort). **Rama:** `equipo1`. **Fecha:** 2026-08-16.
**Brief:** `research/fases/F0-preparacion/02-specs/WP-1-2-brief-harness-pareado-y-parametros.md`.
**Bitácora completa (10 líneas de recon + una entrada por bloque + cierre):**
`research/fases/F0-preparacion/02-specs/WP-1-2-progreso.md`.

Los 6 bloques están **verdes y commiteados**, en orden, uno por commit:

| Bloque | SHA | Contenido |
|---|---|---|
| 1 | `01d775a` | `run_supertrend` con `atr_period`/`mult` expuestos |
| 2 | `035efaf` | `overlay_kwargs` (deep-copy sobre `_GL`) |
| 3 | `fc3773b` | Harness pareado de K brazos + tabla de alineación |
| 4 | `389b09d` | `ac_desacelerando` con `lookback`/`umbral` |
| 5 | `9e1bc54` | `sl_offset` de SuperTrend |
| 6 | `85cbb88` | Instrumentación de camino |

---

## 1 · API exacta que se deja (para el manifiesto de la Ola 1)

### `scripts/analysis/realtick_bt/backtest.py`

```python
def run_supertrend(bars: list[dict[str, Any]], ticks: Ticks, *,
                    atr_period: int = 14, mult: float = 3.0,
                    sl_offset: float = 0.0) -> list[dict[str, Any]]
```
Palancas P-05 (`atr_period`, `mult`) y P-08 (`sl_offset`, USD, ensancha el nivel de SL: LONG
`line[j-1] - sl_offset`, SHORT `line[j-1] + sl_offset`, usado tanto en el test de toque como en
el `exit_bid` reportado). Defaults ⇒ comportamiento de hoy.

```python
def resolve(pos: dict[str, Any], ticks: Ticks, bar_times: np.ndarray, *,
            instrument: bool = False,
            bars: list[dict[str, Any]] | None = None) -> dict[str, Any] | None
```
Con `instrument=True` añade a la posición resuelta: `path_mfe_mae` (`list[{"t","mfe","mae"}]`,
serie completa, no sólo el final), `bars_elapsed` (int), `entry_context`
(`{"t","open","high","low","close"}` de la barra de entrada, o `None` si `bars` no se pasa),
`spread_at_entry` (alias de `spread`), `spread_at_exit_decision` (spread del tick que cerró la
posición, o `None` si el cierre no fue por cruce de tick). No altera ninguna clave existente ni
su valor.

```python
def build_all(ticks: Ticks, bars: list[dict[str, Any]], *,
              instrument: bool = False) -> dict[str, list[dict[str, Any]]]
```
`instrument=False` (default) llama `resolve()` con la misma firma posicional de siempre
(byte-idéntico; es lo que usa `test_baseline_parity.py`). `instrument=True` pasa
`instrument=True, bars=bars` a cada `resolve()`.

`run_ladder(kwargs: dict[str, Any], bars: list[dict[str, Any]]) -> list[dict[str, Any]]` — sin
cambios (ya aceptaba kwargs arbitrarios).

### `scripts/analysis/realtick_bt/overlay.py` (módulo nuevo)

```python
def overlay_kwargs(sid: str, overlay: dict[str, Any]) -> dict[str, Any]
```
`copy.deepcopy(backtest._GL[sid])` + `.update(overlay)` sobre la copia. `_GL`/`_GOLIVE_M15`
nunca mutados. `overlay={}` ⇒ igual por valor a `_GL[sid]` (distinto por identidad). Deja
`max_hold_bars` (P-02) y cualquier otro kwarg de `simular_variant` barribles sin tocar el motor.

### `scripts/analysis/realtick_bt/paired_harness.py` (módulo nuevo)

```python
def entry_identity(sid: str, pos: dict[str, Any]) -> tuple
    # SuperTrend-p14x3-M15 -> (t_in, side)
    # ladder (S6/S7)       -> (sid, ficha, t_in, side)

@dataclass
class PairedResult:
    sid: str
    arms: dict[str, list[dict]]              # brazo -> posiciones RESUELTAS (post-resolve)
    signal_positions: dict[str, list[dict]]  # brazo -> posiciones de SEÑAL (pre-resolve)
    alignment_signal: dict[tuple[str, str], dict]  # (armA,armB) -> {"n_casadas","n_solo_A","n_solo_B","no_casadas"}
    alignment_filled: dict[tuple[str, str], dict]  # idem, nivel post-resolve()
    def rows(self) -> list[dict]  # columnar, con "arm","sid","pos_id" añadidos; unible por pos_id

def run_paired_arms(sid: str, arms: dict[str, dict[str, Any]],
                     bars: list[dict[str, Any]],
                     ticks: Ticks | None = None) -> PairedResult
```
`arms`: `{nombre_brazo: overlay_dict}`. Para `sid` ladder, cada `overlay_dict` pasa por
`overlay_kwargs(sid, overlay_dict)` → `run_ladder`. Para `sid == "SuperTrend-p14x3-M15"`, el
`overlay_dict` se pasa como kwargs directos de `run_supertrend(bars, ticks, **overlay_dict)`
(o sea: claves válidas ahí son `atr_period`, `mult`, `sl_offset`). Cada brazo se corre y se
resuelve **una sola vez**. El brazo con overlay `{}` reproduce exactamente `run_ladder(_GL[sid],
bars)` + `resolve()` de hoy (test de no-regresión, ver `test_default_arm_reproduces_todays_run_ladder_exactly`).
La tabla de alineación **mide, no asume**: el test
`test_alignment_table_measures_not_assumes_overlap` prueba un caso con `stop_and_reverse` donde
un brazo genera una entrada SHORT aguas abajo que el otro no tiene, y el resultado
(`n_casadas=3, n_solo_A=0, n_solo_B=3`) sale de la medición real, no de un supuesto.

### `sentinel_engine/strategies/emasar_ref.py`

```python
def ac_desacelerando(ac, idx, direccion, *, lookback: int = 1, umbral: float = 0.0)
```
`lookback=1, umbral=0.0` ⇒ byte-idéntica a la versión original (`ac[idx] < ac[idx-1]` /
`ac[idx] > ac[idx-1]`, guard `idx < 1`). Generaliza el guard a `idx < lookback`.

### `sentinel_engine/strategies/emasar_variant.py`

`simular_variant(..., ac_decel_lookback: int = 1, ac_decel_umbral: float = 0.0)` — dos kwargs
nuevos al final de la firma, enhebrados en los dos call-sites de `ac_desacelerando` (bloque
`ac_modulate` trail y bloque `f3_ac_decel_exit`). Defaults ⇒ comportamiento de hoy exacto.
`live_configs_20.py` **no fue tocado**.

---

## 2 · Comandos ejecutados y salida real

Bloque 0 (antes de empezar):
```
python -m pytest tests/research/test_baseline_parity.py -m slow -q
....                                                                     [100%]
4 passed in 2.28s

python -m pytest tests/analysis -q
........................................................................ [ 23%]
........................................................................ [ 46%]
........................................................................ [ 70%]
........................................................................ [ 93%]
...................                                                      [100%]
307 passed in 55.14s

python -m pytest tests/research -q
........................................................................ [ 25%]
........................................................................ [ 51%]
........................................................................ [ 77%]
...............................................................          [100%]
279 passed, 4 deselected in 16.39s
```

Después de CADA uno de los 6 bloques (idéntico en los 6):
```
python -m pytest tests/research/test_baseline_parity.py -m slow -q
....                                                                     [100%]
4 passed in ~2.3-2.4s
```

Tests propios, acumulativo por bloque (`tests/research/test_harness_pareado.py`):
B1 → 2 passed · B2 → 5 passed · B3 → 10 passed · B4 → 18 passed (incluye 4 nuevos: 2 de
`ac_desacelerando` directo, 2 de `simular_variant` con los kwargs nuevos sobre 400 barras
reales) · B5 → 16 passed · B6 → **21 passed** (final).

Cierre (después del bloque 6, fichero final):
```
python -m pytest tests/research/test_harness_pareado.py -q
.....................                                                   [100%]
21 passed in 0.80s

python -m pytest tests/research/test_baseline_parity.py -m slow -q
....                                                                     [100%]
4 passed in 2.42s

python -m pytest tests/analysis -q
    ...
    def test_cita_gate_spread_harness_verificada_contra_el_fichero_real():
        ...
>       assert "abs(sp - 0.5) <= 0.05" in lineas[375]  # linea 376, indice 375
E       AssertionError: assert 'abs(sp - 0.5) <= 0.05' in '    `instrument` (WP-1+2 Bloque 6, ...'
=========================== short test summary info ===========================
FAILED tests/analysis/test_borde_del_dia.py::test_cita_gate_spread_harness_verificada_contra_el_fichero_real
1 failed, 306 passed in 52.16s

python -m pytest tests/research -q
........................................................................ [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
............                                                             [100%]
300 passed, 4 deselected in 16.54s

python -m pytest tests/strategies -q      # extra, fuera de mandato, verificacion de seguridad
........................................................................ [ 26%]
........................................................................ [ 52%]
........................................................................ [ 79%]
........................................................                 [100%]
272 passed in 3.68s

grep -n "abs(sp - 0.5) <= 0.05" scripts/analysis/realtick_bt/backtest.py
400:        if abs(sp - 0.5) <= 0.05:
```

---

## 3 · Lo que NO se hizo, y por qué

1. **Una regresión colateral, no corregida, fuera de mandato.**
   `tests/analysis/test_borde_del_dia.py::test_cita_gate_spread_harness_verificada_contra_el_fichero_real`
   pasó de verde a rojo. Causa: esa prueba lee `scripts/analysis/realtick_bt/backtest.py` de
   verdad y afirma que la cadena `"abs(sp - 0.5) <= 0.05"` está en `lineas[375]` (línea 376
   hardcodeada) — una cita `file:line` frágil, con precedente idéntico ya documentado en el
   propio test (comentario: T0.7-M-E ya desplazó esta cita de 358→376). Mis ediciones en
   `backtest.py` (docstrings de `run_supertrend`/`resolve`/`build_all`, todas dentro de mis
   rutas y aditivas por diseño) movieron esa línea de **376 a 400**. **No es R1-bis**: ninguna
   estrategia viva cambió de comportamiento (la puerta de paridad, que sí prueba eso, está verde
   en los 6 bloques). El fichero que falla (`tests/analysis/test_borde_del_dia.py`) y el módulo
   con la constante citada (`scripts/analysis/realtick_bt/faulty/borde_del_dia.py`) están **fuera
   de mis TUS RUTAS** del brief — no los toqué, ni el test ni el módulo. Fix mecánico pendiente
   para quien tenga mandato sobre `faulty/`: actualizar `lineas[375]` → `lineas[399]` (índice) y
   el comentario de rango en `tests/analysis/test_borde_del_dia.py:308-313`.
2. **Nada más del alcance del brief quedó sin hacer.** Los 6 bloques, en el orden fijado, están
   completos, verdes y commiteados.
3. **Fuera de alcance por diseño (brief §3), no intentado:** P-27 (SL estructural por swing),
   régimen (WP-5), feed H1/H4 (WP-3), sizing (WP-4), correr grillas/barridos, y escritura en
   LEDGER/TRACKER/DECISIONES/plan maestro.
4. **Tensión de recon documentada, no un pendiente:** `emasar_ref.py` lleva un docstring de
   módulo "DO NOT EDIT ... vendored frozen copy"; el brief nombra explícitamente
   `emasar_ref.py:291` como objetivo del Bloque 4 y preautoriza el cambio aditivo bajo la puerta
   de paridad (ver `WP-1-2-progreso.md`, Bloque 4). Se procedió conforme al brief cerrado.
