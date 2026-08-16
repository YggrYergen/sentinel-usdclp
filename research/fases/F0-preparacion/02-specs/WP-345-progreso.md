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
