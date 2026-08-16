# WP-1+2 — Bitácora de progreso (una línea por bloque)

## Bloque 0 — Recon (2026-08-16)
1. `scripts/analysis/realtick_bt/backtest.py` (719 líneas): confirmado. `run_supertrend(bars, ticks)` en línea 306, hardcodea `_atr_wilder(highs, lows, closes, 14)` (L316) y `supertrend(highs, lows, closes, atrf, 3.0)` (L318). `sl = line[j - 1]` en L327, usado en el test de toque (L334) y como `exit_bid` (L340) — el mismo `sl` alimenta ambos, confirma el requisito del Bloque 5.
2. `run_ladder(kwargs, bars)` en L239 ya acepta kwargs arbitrarios (`simular_variant(bars, **{**{"symbol": SYMBOL}, **kwargs})`, L251). `resolve(pos, ticks, bar_times)` en L354, descarta posiciones sin fill de entrada (`return None`, L379) o sin fill de salida (L403).
3. `_GL = {c["id"]: c["kwargs"] for c in _GOLIVE_M15}` en L70; `STRATS = ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"]` en L71. `build_all(ticks, bars)` en L462 orquesta: `run_supertrend(bars, ticks)` para ST, `run_ladder(_GL[sid], bars)` para S6/S7 — ninguno pasa kwargs nuevos hoy.
4. `sentinel_engine/strategies/emasar_variant.py:simular_variant` firma en L86-142: confirma `max_hold_bars: int | None = None` (L130), `ac_modulate: bool = False` (L113), `ac_modulate_factor: float = 0.5` (L114) YA kwargs. `ac_desacelerando(ac, i, f.lado)` se llama en L965 (bloque ac_modulate trail) y L1053 (bloque f3_ac_decel_exit) — ambos SIN threshold/lookback hoy.
5. `sentinel_engine/strategies/emasar_ref.py:291` `ac_desacelerando(ac, idx, direccion)`: compara `ac[idx] < ac[idx-1]` (long) / `ac[idx] > ac[idx-1]` (short) — lookback=1 implícito, sin umbral (comparación de signo pura). Guard `idx < 1` (línea 294). Llamada también desde `emasar_ref.py:437,498` dentro de `simular` (la función REF/golden, no la variante viva) — no se toca, sólo se benefician de defaults nuevos si se decide extenderla (no obligatorio, fuera de alcance).
6. `sentinel_engine/strategies/_supertrend_ref.py:supertrend(highs, lows, closes, atr, mult)` (L19-43) y `flips(trend)` (L46-51): vendored frozen copy, NO EDITAR (docstring explícito L10-14) — confirma que Bloque 1 sólo toca `backtest.py`, nunca este fichero.
7. `sentinel_engine/strategies/emasar_ref.py:_atr_wilder(highs, lows, closes, period)` (L589-601): firma ya acepta `period` como parámetro posicional — `run_supertrend` hoy la llama con literal `14` (L316), confirma que el Bloque 1 sólo necesita exponer `atr_period` en `run_supertrend` y pasarlo aquí.
8. `_GOLIVE_M15` / `_GL` — R1-bis: nunca se mutan. Ningún caller de `run_supertrend`/`build_all` fuera de mis rutas pasa argumentos posicionales extra tras `bars, ticks` (grep confirmó 35 ficheros con matches de texto, la mayoría docs/JSON; callers python: `scripts/research/baseline_golden.py`, `scripts/research/backtest_largo_ava.py`, `scripts/analysis/a6_pata_a/*.py`, `scripts/report/gen_*.py` — todos llaman `run_supertrend(bars, ticks)`/`build_all(ticks, bars)` sin kwargs nuevos, compatibles con kwargs-only añadidos con default).
9. `tests/research/test_baseline_parity.py` es `-m slow`, re-corre `bt.build_all(bt.Ticks(), bars)` sobre `bars` recortados a `< HOLDOUT_INI` y compara contra JSON congelados en `research/fases/F0-preparacion/04-resultados/T0.6-baseline/` — PROHIBIDO tocar ese test o esos JSON (son del controlador D-55). Estado antes de empezar: **4 passed**.
10. Línea de partida (Bloque 0, medida): `python -m pytest tests/analysis -q` → **307 passed**. `python -m pytest tests/research -q` → **279 passed, 4 deselected** (los 4 son los `slow` de parity, coherente con el brief). Sin tests propios nuevos todavía (se crean en `tests/research/test_harness_pareado.py`, Bloque 1 en adelante).

Parity gate antes de empezar: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed**.

## Bloque 1 — Parámetros de SuperTrend expuestos (2026-08-16)
`run_supertrend(bars, ticks, *, atr_period: int = 14, mult: float = 3.0)` en
`scripts/analysis/realtick_bt/backtest.py:306-307`; `_atr_wilder(..., atr_period)` (antes `14`
literal) y `supertrend(..., mult)` (antes `3.0` literal). `build_all()` no cambió (sigue
llamando sin kwargs nuevos). Tests nuevos:
`tests/research/test_harness_pareado.py::test_run_supertrend_defaults_match_explicit_hardcoded_values`
y `::test_run_supertrend_different_params_change_result` → 2 passed.
Parity gate: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed**.

## Bloque 2 — Overlay de kwargs por deep-copy (2026-08-16)
`scripts/analysis/realtick_bt/overlay.py::overlay_kwargs(sid: str, overlay: dict[str, Any]) ->
dict[str, Any]` — `copy.deepcopy(backtest._GL[sid])` + `.update(overlay)` sobre la copia; `_GL`/
`_GOLIVE_M15` nunca mutados (nunca `dict.update` sobre el original). Overlay vacío ⇒ igual por
valor a `_GL[sid]`, distinto por identidad (deep copy). Tests nuevos: 3 (no-mutación, overlay
vacío, overlay aplica sobre la copia) → total fichero 5 passed.
Parity gate: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed**.

## Bloque 3 — Harness pareado + tabla de alineación (2026-08-16)
`scripts/analysis/realtick_bt/paired_harness.py`: `entry_identity(sid, pos) -> tuple` (SuperTrend:
`(t_in, side)`; ladder: `(sid, ficha, t_in, side)`); `run_paired_arms(sid, arms: dict[str, dict],
bars, ticks=None) -> PairedResult` corre cada brazo una sola vez (ladder vía `overlay_kwargs` +
`run_ladder`; SuperTrend vía `run_supertrend(bars, ticks, **overlay)`), resuelve una sola vez, y
mide (nunca asume) el solape par-a-par en `alignment_signal`/`alignment_filled`
(`dict[(armA,armB), {"n_casadas","n_solo_A","n_solo_B","no_casadas"}]`), en los dos niveles
exigidos (señal pre-`resolve()`, rellenado post-`resolve()`). `PairedResult.rows()` da salida
columnar con `pos_id` (identidad serializada) unible sin ambigüedad. Tests nuevos: 5 (brazo
default reproduce `run_ladder`+`resolve` de hoy exacto — no-regresión; tabla mide solape real con
un caso donde S6 con `stop_and_reverse` diverge aguas abajo — 3 casadas / 3 solo-B / 0 solo-A;
identidad SuperTrend sin ficha; identidad ladder con sid+ficha; filas unibles por `pos_id`) →
total fichero 10 passed.
Parity gate: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed**.

## Bloque 4 — Umbral y lookback de desaceleración de AC (2026-08-16)
`sentinel_engine/strategies/emasar_ref.py:291`
`ac_desacelerando(ac, idx, direccion, *, lookback: int = 1, umbral: float = 0.0)` —
generaliza `idx-1` fijo → `idx-lookback`, y añade exigencia de magnitud (`umbral`); con
`lookback=1, umbral=0.0` es byte-idéntica a la versión original (`ac[idx] < ac[idx-1]` /
`ac[idx] > ac[idx-1]`). `sentinel_engine/strategies/emasar_variant.py`: `simular_variant` gana
`ac_decel_lookback: int = 1`, `ac_decel_umbral: float = 0.0` (aditivos, al final de la firma),
enhebrados en los DOS call-sites de `ac_desacelerando` (línea ~965 bloque `ac_modulate`, línea
~1053 bloque `f3_ac_decel_exit`). No se tocó `live_configs_20.py` ni ningún dict de config viva.
⚠️ Nota de recon: `emasar_ref.py` lleva un docstring de módulo "DO NOT EDIT ... vendored frozen
copy" (líneas 1-18) que en principio prohíbe tocar el fichero; el brief (§Bloque 4) nombra este
mismo `emasar_ref.py:291` como objetivo explícito, aclara que R1-bis se hace cumplir aquí **por
comportamiento** vía la puerta de paridad, y da instrucción de PARAR sólo si hiciera falta
cambiar un default o una config viva — no es el caso (cambio 100% aditivo). Se procedió conforme
al brief cerrado, citando la tensión aquí para que quede trazada.
Tests nuevos (4): defaults byte-idénticos a la versión legacy; lookback/umbral cambian el
resultado; `simular_variant` con los kwargs nuevos explícitos en su default es byte-idéntico
(con `ac_modulate=True, f3_ac_decel_exit=True` para ejercitar ambos call-sites, sobre 400 barras
reales); `ac_decel_umbral` grande sí cambia el resultado cuando el bloque está activo → total
fichero 18 passed.
Parity gate: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed**.
Extra (fuera de mis rutas, verificación de seguridad porque toqué ficheros compartidos):
`python -m pytest tests/strategies -q` → **272 passed**.

🔴 **REGRESIÓN COLATERAL DETECTADA (fuera de mis rutas, NO corregida por mí):**
`python -m pytest tests/analysis -q` → **306 passed, 1 failed** (línea de partida Bloque 0: 307
passed). El único rojo es
`tests/analysis/test_borde_del_dia.py::test_cita_gate_spread_harness_verificada_contra_el_fichero_real`,
que lee `scripts/analysis/realtick_bt/backtest.py` y afirma `"abs(sp - 0.5) <= 0.05" in
lineas[375]` (línea 376 hardcodeada). Mi edición del Bloque 1 (docstring de `run_supertrend`,
+3 líneas) desplazó esa línea a **379** (verificado: `grep -n "abs(sp - 0.5) <= 0.05"
scripts/analysis/realtick_bt/backtest.py` → `379:`). Es una cita `file:line` frágil, NO deriva de
comportamiento (R1-bis no aplica: ninguna estrategia viva cambió), y hay precedente idéntico ya
documentado en el propio test (comentario línea 308-310: T0.7-M-E ya desplazó esta misma cita de
358→376 y la actualizó). El fichero que falla (`tests/analysis/test_borde_del_dia.py`) y el
módulo que cita la constante (`scripts/analysis/realtick_bt/faulty/borde_del_dia.py`) están
**fuera de mis TUS RUTAS** del brief — no los toqué. Queda para el controlador: o autoriza que un
agente actualice esa cita (`lineas[375]` → `lineas[378]`, y el comentario de rango) en esos dos
ficheros, o lo hace el dueño de `faulty/`. `tests/research -q` no tiene regresión: **293 passed,
4 deselected** (línea de partida Bloque 0: 279 passed, 4 deselected — la diferencia +14 son mis
tests nuevos en `test_harness_pareado.py`).

## Bloque 5 — Offset de SL consciente del fill (2026-08-16)
`run_supertrend(bars, ticks, *, atr_period=14, mult=3.0, sl_offset: float = 0.0)` —
`sl_eff = sl - sl_offset` (LONG) / `sl + sl_offset` (SHORT), calculado UNA vez por barra y
usado TANTO en el test de toque (`cond = (bb <= sl_eff) ...`) COMO en `exit_bid` cuando
`hit=True` (`reason, exit_bid = "EXIT_STLINE", sl_eff`). Default `0.0` ⇒ `sl_eff == sl` ⇒
byte-idéntico. Tests nuevos (2): default cero byte-idéntico; coherencia toque/precio probada en
dos direcciones sobre la MISMA fixture — (a) un tick que toca el nivel ORIGINAL no dispara
`EXIT_STLINE` una vez ensanchado (prueba que el test de toque usa el nivel desplazado, no sólo
el precio reportado); (b) un tick exactamente en el nivel ENSANCHADO sí dispara, y su
`exit_bid` es el nivel ensanchado — total fichero 16 passed.
Parity gate: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed**.
