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
