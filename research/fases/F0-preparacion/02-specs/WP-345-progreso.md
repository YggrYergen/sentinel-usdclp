# WP-3+4+5 — Bitácora de progreso (una línea por bloque)

## Bloque 0 — Recon (2026-08-16)
1. Spec leída completa: `research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md`
   (WP-3 L139-159, WP-4 L162-185, WP-5 L188-204, contrato antitrampa §1 L25-50, verbatim §4 L225-247).
2. `scripts/analysis/realtick_bt/backtest.py` (786 líneas, ya con Bloques WP-1+2 commiteados):
   `Ticks.range(t0,t1)`/`.first_at(t)` sobre eje epoch segundos = hora servidor "etiquetada como UTC" (CLOCK
   CONVENTION L15-26, `datetime.utcfromtimestamp`, cero conversión de huso). `load_bars()` devuelve M15
   `{"t","open","high","low","close","volume"}`, `t`=apertura de barra, `BAR_SEC=900`. `metrics(rows, lot)`
   L488, `peak_margin(rows, lot)` L475: escalan por un `lot` GLOBAL, sin gancho por posición — punto de
   inyección natural para WP-4 (emisión de orden/tamaño). `build_all(ticks, bars, *, instrument=False)` L520:
   con `instrument=False` (default, usado por `test_baseline_parity.py`) es exactamente el comportamiento de
   hoy — cualquier kwarg nuevo debe ser 100% opt-in para no romper la comparación exacta de claves del test
   de paridad (`set(esperado) | set(obtenido)`, ve claves extra como diferencia).
3. `sentinel_engine/strategies/_supertrend_ref.py` (52 líneas): `supertrend(highs, lows, closes, atr, mult) ->
   (trend, line)` — recursión pura izquierda-a-derecha, `trend[i]`/`line[i]` dependen sólo de `[0..i]`, ya
   importada en `backtest.py`. NO es el módulo de desaceleración de AC (ese es `emasar_ref.py`, fuera de mis
   rutas — NO LEÍDO en esta tarea). Reutilizable para WP-3 (dirección SuperTrend en la serie superior).
4. Confirmado por grep: única forma de importar `backtest.metrics`/`backtest.peak_margin` es `bt.metrics(rows,
   lot)` con 2 posicionales (`baseline_golden.py:92`, `backtest_largo_ava.py:461,468`, `ola1/metricas.py:55-56`)
   — añadir `lot_fn: Callable|None=None` kwarg-only es retrocompatible en los 4 call-sites reales.
5. `emasar_ref.py`, `emasar_variant.py`, `ac_desacelerando`, `ac_modulate_hold_bars`: **NO tocados, NO leídos**
   en esta tarea (prohibición explícita del dispatcher — otro agente diagnostica AC ahora mismo).
   `scripts/research/runner/`, `04-resultados/OLA1*/`, `TRACKER.md`/`LEDGER.jsonl`/`DECISIONES.md`/
   `.gitignore`/`docs/superpowers/plans/`: **NO tocados**.
6. Módulos nuevos decididos (fuera del núcleo salvo los dos puntos de inyección explícitos del spec):
   `scripts/analysis/realtick_bt/higher_tf.py` (WP-3), `scripts/analysis/realtick_bt/sizing.py` (WP-4),
   `scripts/analysis/realtick_bt/regime.py` (WP-5, **sin tocar `backtest.py`**, per spec L190 "no toca el
   núcleo" — confirmado verbatim, sin punto de inyección en la tabla del §2).
7. Diseño WP-3 anti-look-ahead: una barra superior se considera cerrada **la primera vez que una barra M15
   acumulada alcanza o supera el borde de cierre de su propio bucket** (`b["t"]+900 >= bucket_close`) —
   verificable con SOLO la propia barra, sin mirar la siguiente. Buckets H1/H4 por floor-division del epoch
   (`t // 3600*3600`, `t // 14400*14400`): como el eje epoch YA codifica el reloj de servidor (sin conversión,
   ver CLOCK CONVENTION), esta aritmética entera alinea sola con la medianoche de servidor — sin ninguna
   conversión de huso horario explícita.
8. Diseño WP-4: `sizing.py::apply_sizing(resolved, cfg)` recorre TODAS las posiciones resueltas (3 estrategias)
   en un único orden cronológico explícito (`sorted` por `(t_exit, t_in_exec, sid, ficha)` — determinístico,
   independiente del orden de iteración de los dicts de `build_all()`), reconstruye `AccountState` (equity
   peak/drawdown, Sharpe rodante 50 por estrategia, racha de pérdidas consecutivas por día) y adjunta
   `lot_mult` (clave nueva, no toca `net1`/`margin1`). Punto de inyección real en `backtest.py`: `metrics()` y
   `peak_margin()` ganan `lot_fn: Callable[[dict], float] | None = None`; default `None` = comportamiento
   de hoy exacto.
9. Diseño WP-5: `regime.py::compute_regime_series(bars, ...)` — ADX/Variance Ratio/Efficiency Ratio/Choppiness,
   las 4 por paso único izquierda-a-derecha (Wilder para ADX) o ventana rodante estrictamente trasera
   (`bars[i-n+1..i]`), sin `pandas.rolling(center=True)` ni ajuste tras el hecho. `regime_gate(idx, series,
   cfg)` con `cfg.enabled=False` por defecto ⇒ siempre `True` (no filtra nada). Cero cambios en `backtest.py`.
10. Línea de partida (Bloque 0, medida):
    `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed** (2.84s).
    Orden de despacho: WP-3 primero (módulo + inyección en `metrics`/`peak_margin` reservada para WP-4, no
    tocada aquí), luego WP-4, luego WP-5 (sin tocar núcleo). Commit por bloque verde, parity gate tras cada uno.

## Bloque WP-3 — feed H1/H4 (2026-08-16)
`scripts/analysis/realtick_bt/higher_tf.py` (módulo nuevo, cero cambios en `backtest.py`):
`aggregate_closed_with_visibility(bars_m15, tf_sec, *, m15_sec=900) -> (closed_bars, visible_count)` — un
bucket se marca cerrado la PRIMERA vez que una barra M15 propia alcanza/supera el borde de cierre de SU
propio bucket (`b["t"]+m15_sec >= bucket_close`), sin mirar nunca la barra siguiente. `build_higher_series(
bars_m15, tf_sec, *, ema_period=20, st_atr_period=10, st_mult=3.0, momentum_lookback=10) -> HigherSeries`
(`.bars`, `.ema`, `.ema_slope`, `.st_dir`, `.momentum`, `.visible_count`, `.snapshot_at_m15_index(i) -> dict|
None`, O(1)). EMA/ATR-Wilder/SuperTrend-dirección reimplementados localmente (self-contained, CERO import de
`emasar_ref.py` — fuera de mis rutas, no leído). Tests: `tests/research/test_higher_tf.py`, **12 passed**
— incluye el contrato antitrampa §1 (corte de prefijo == valor de la serie completa en `t`, H1 y H4) y el
test explícito de que el bucket en curso nunca es visible (incluso a 15/16 barras M15 de su propio cierre).
Parity gate: **4 passed**. Commit: `0dd14ec`.

## Bloque WP-4 — hook de tamaño + estado de cuenta (2026-08-16)
`scripts/analysis/realtick_bt/sizing.py` (módulo nuevo): `SizingConfig` (kelly_mult/kelly_payoff_default/
kelly_clip, atr_target/atr_clip, dd_bands, ficha_factors, sharpe_window/sharpe_floor/sharpe_floor_factor,
loss_streak_cutoff/loss_streak_factor, correlation_discount_per_extra, clip). `AccountState` (equity,
equity_peak, `drawdown_pct` property, trade_returns por sid, current_day, consecutive_losses_today).
`apply_sizing(resolved, cfg, *, atr_fn=None) -> resolved'` — `cfg=None` devuelve `resolved` SIN TOCAR
(mismo objeto); si no, recorre TODAS las posiciones de las 3 estrategias en un único orden cronológico
explícito `sorted(key=(t_exit,t_in_exec,sid,ficha,indice_plano))` — nunca el orden de iteración del dict —
reconstruye `AccountState`, y adjunta `lot_mult` (clave nueva, `net1`/`margin1` intactos) preservando el
orden ORIGINAL de cada lista por sid en la salida. `lot_multiplier()` combina factores multiplicativamente
(Kelly, ATR-inverso vía `atr_fn` inyectado por el llamador, banda de drawdown, índice de ficha, piso de
Sharpe rodante, corte de racha de pérdidas diaria, descuento de correlación por solape de aperturas —
`_concurrency_at_open()`, sweep de eventos determinista), clip final configurable. `rolling_sharpe()`,
`kelly_factor()`, `lot_fn(base_lot)` (adaptador para el punto de inyección de motor).
**Punto de inyección en el núcleo** (único cambio en `backtest.py`, WP-4): `metrics(rows, lot, *, lot_fn=
None)` y `peak_margin(rows, lot, *, lot_fn=None)` ganan el kwarg `lot_fn` — `None` (default) reproduce
exactamente el `lot` global de siempre, byte-idéntico; con `lot_fn` da el tamaño por fila. Los 4 call-sites
reales (`baseline_golden.py:92`, `backtest_largo_ava.py:461,468`, `ola1/metricas.py:55-56`) llaman con 2
posicionales, retrocompatibles sin cambio.
Bug atrapado por test propio antes de verde: el reseteo del contador de racha diaria ocurría DESPUÉS de
decidir el multiplicador de la primera operación del día nuevo (usaba la racha de ayer) — corregido con
`_roll_day()`, que avanza el borde de día ANTES de `lot_multiplier()` (el día de una operación se conoce de
antemano por su propio `t_exit`, a diferencia de su PnL).
Tests: `tests/research/test_sizing.py`, **15 passed** — apagado por defecto (mismo objeto, sin `lot_mult`),
config neutra = `lot_mult=1.0` en todas + round-trip completo por `backtest.metrics`/`peak_margin` idéntico
al `lot` global plano, `rolling_sharpe`/`kelly_factor` contra cálculo a mano, banda de drawdown, ficha,
piso de Sharpe, racha de pérdidas con reseteo de día, descuento de correlación por solape real, clip, e
independencia del orden de iteración del dict (`resolved` con las mismas 4 posiciones, claves de
estrategia insertadas en orden distinto, mismos `lot_mult` resultantes).
Parity gate: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed**.
Verificación extra (fuera de mandato estricto, porque toqué `backtest.py`): `tests/research -q` →
**353 passed, 11 deselected**; `tests/analysis -q` → **307 passed** (0 rojos — el rojo colateral de cita
`file:line` reportado en `WP-1-2-progreso.md` Bloque 4 ya no está presente, línea realineada por otro
commit intermedio; verificado, no corregido por mí).

## Bloque WP-5 — cómputos de régimen (2026-08-16)
`scripts/analysis/realtick_bt/regime.py` (módulo nuevo, **cero cambios en `backtest.py`** — spec §2 tabla:
"no toca el núcleo", confirmado verbatim). 4 series cerradas, sin dependencia estadística externa:
`compute_adx(highs, lows, closes, period=14)` (recursión de Wilder clásica izquierda-a-derecha sobre TR/
+DM/-DM, warm-up `2*period-1`); `compute_variance_ratio(closes, *, window=40, q=2)` (Lo-MacKinlay, ventana
trasera estricta `closes[i-window..i]`, `None` hasta llenarla); `compute_efficiency_ratio(closes, *,
period=10)` (Kaufman ER, ventana trasera); `compute_choppiness(highs, lows, closes, *, period=14)` (ventana
trasera). `compute_regime_series(bars, ...) -> RegimeSeries` (`.adx`, `.variance_ratio`,
`.efficiency_ratio`, `.choppiness`, alineadas índice a índice con `bars`). `RegimeGateConfig` (`enabled=
False` por defecto) + `regime_gate(idx, series, cfg) -> bool` — gate "k de m" compuesto; con `enabled=False`
siempre `True` (nunca filtra); un indicador `None` (warm-up) cuenta como FALLO del criterio, nunca como
paso. Ningún criterio sin umbral fijado se evalúa (no cuenta en `m`).
Tests: `tests/research/test_regime.py`, **13 passed** — sanity direccional (ER≈1 en tendencia limpia/≈0 en
zigzag puro, Choppiness mayor en zigzag que en tendencia al mismo período, ADX>10 tras un drift sostenido,
VR(2)>1 en un drift persistente); el contrato antitrampa §1 para las 4 series (corte de prefijo == valor de
la serie completa en `t`, sobre bars con tendencia Y sobre bars en zigzag, múltiples puntos de corte
incluyendo justo en los bordes de warm-up); un test explícito adicional del mismo contrato: pegar 50 barras
de régimen TOTALMENTE distinto (zigzag) después del punto `t` no cambia NINGÚN valor ya calculado en `t`;
gate apagado por defecto siempre `True`; `None` cuenta como fallo no como paso; "k de m" con distintos
umbrales de exigencia; sólo se evalúan los criterios con umbral fijado.
Parity gate: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` → **4 passed** (era de
esperar sin cambio real: WP-5 no toca `backtest.py`; corrida igual, por disciplina, tras cada bloque).
Verificación combinada final: `python -m pytest tests/research tests/analysis -q` → **673 passed, 11
deselected**, 72.64s (0 rojos).
