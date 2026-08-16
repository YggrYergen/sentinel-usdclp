# T0.7-M-F -- fix_lookahead_ticksava

Brief: `research/fases/F0-preparacion/02-specs/T0.7-M-F-brief-fix-lookahead-ticksava.md`
Commit: `43785dcd7dbc420b4c78a88d665683daea3fb75c`

## F.1 -- cambio aplicado

`scripts/analysis/a6_pata_a/signal_level.py`, clase `TicksAva` (línea 73, NO subclase de `bt.Ticks`):

- `TicksAva.__init__` (línea 75): kwarg `tolerance_s: float = 60.0` (keyword-only, con default),
  guardado como `self.tolerance_s`.
- `TicksAva.first_at` (línea 131): retorna `None` si `t_tick - t_sec > self.tolerance_s`, en vez
  del tick. Mismo valor (`60.0`) y misma semántica que `bt.Ticks.first_at` (`backtest.py`, T0.7-M-E,
  commit `f3dda1a`).
- No se refactorizó `TicksAva` para heredar de `bt.Ticks` (fuera de alcance por brief F.1).

## F.2 -- auditoría de consumidores (solo lectura)

- Único consumidor de la instancia `TicksAva` (`ava_ticks`, `signal_level.py:299`):
  `st_signals(ava_bars_st, ava_ticks, gated=False)` (`signal_level.py:339`).
- Dentro de `st_signals` (`signal_level.py:209-234`), `ticks` (=`ava_ticks`) se pasa a
  `run_supertrend(bars, ticks)` (`backtest.py:306`). `run_supertrend` llama únicamente
  `ticks.range(t0, t1)` (`backtest.py:331`); **no llama `ticks.first_at()` en ningún punto de su
  cuerpo** (`backtest.py:306-350`).
- `resolve(pos, ticks, bar_times)` (`backtest.py:354`) es la **única** función que llama
  `.first_at()` en todo el árbol de llamadas alcanzable desde `TicksAva` (`backtest.py:371` y
  `:401`, ambos ya manejan `None` con `continue` / `return None`, sin cambio de esta tarea).
  `st_signals` solo invoca `resolve(p, ticks, bar_times)` cuando `gated=True`
  (`signal_level.py:217`); la llamada con `ava_ticks` en `signal_level.py:339` usa `gated=False`
  (`signal_level.py:339`), por lo que `resolve()` **nunca** se invoca con `ava_ticks`.
- Conclusión de hecho (verificada por lectura, sin ejecución): `TicksAva.first_at` **no tiene
  ningún call site activo** en el código actual del repositorio. Es un método publicado por
  simetría con `bt.Ticks` (mismo shape de API), no ejecutado por ningún flujo hoy.
- Instanciación de `Ticks` (ya acotado por `f3dda1a`, importado de
  `scripts.analysis.realtick_bt.backtest`) confirmada por lectura de imports:
  - `scripts/analysis/a6_pata_a/capa1_senal_cruda.py:389` (`st_ticks = Ticks()`), import en línea
    108 (`from scripts.analysis.realtick_bt.backtest import (...)`).
  - `scripts/analysis/a6_pata_a/capa3_gate_spread.py:413` (`ticks = Ticks()`), import en línea 36.
  - `scripts/analysis/a6_pata_a/exp_active_fichas.py:195` (`ticks = Ticks()`), import en línea 60.
  - `scripts/analysis/a6_pata_a/signal_level.py:298` (`cap_ticks = Ticks()`), import en línea 41.
- Ningún consumidor de `TicksAva` requirió escalar por manejo de `None` faltante (no hay
  consumidor activo que llame el método).

## Comandos ejecutados y salida real

### RED

```
$ python -m pytest tests/analysis/test_lookahead_ticksava.py -q
[...]
FAILED tests/analysis/test_lookahead_ticksava.py::test_first_at_hueco_artificial_devuelve_none_bajo_tolerancia_default
FAILED tests/analysis/test_lookahead_ticksava.py::test_first_at_hueco_artificial_con_tolerancia_grande_reproduce_comportamiento_viejo
FAILED tests/analysis/test_lookahead_ticksava.py::test_first_at_cruza_fichero_de_mes_pero_none_bajo_tolerancia_default
FAILED tests/analysis/test_lookahead_ticksava.py::test_first_at_cruza_fichero_de_mes_con_tolerancia_grande_reproduce_comportamiento_viejo
FAILED tests/analysis/test_lookahead_ticksava.py::test_first_at_comprueba_distancia_none_si_excede_tolerancia_default
FAILED tests/analysis/test_lookahead_ticksava.py::test_first_at_limite_exacto_de_tolerancia_no_es_none
FAILED tests/analysis/test_lookahead_ticksava.py::test_first_at_con_tolerancia_grande_reproduce_comportamiento_viejo
FAILED tests/analysis/test_lookahead_ticksava.py::test_ticksava_init_sin_argumentos_tolerancia_default_es_60
8 failed, 3 passed in 1.90s
```
Causas: `TypeError: TicksAva.__init__() got an unexpected keyword argument 'tolerance_s'` /
`AttributeError: 'TicksAva' object has no attribute 'tolerance_s'` -- confirman rojo por ausencia
de implementación.

### GREEN

```
$ python -m pytest tests/analysis/test_lookahead_ticksava.py -q
...........                                                              [100%]
11 passed in 1.14s
```

### Suite dirigida

```
$ python -m pytest tests/analysis -q
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 70%]
........................................................................ [ 94%]
.................                                                        [100%]
305 passed in 55.41s
```
(294 baseline commit `404a125` + 11 tests nuevos de `test_lookahead_ticksava.py`, 0 fallos, 0
regresiones.)

### Parity gate

```
$ python -m pytest tests/research/test_baseline_parity.py -m slow -q
.FFF                                                                     [100%]
3 failed, 1 passed in 2.72s
```
Fallos (idénticos a los reportados por T0.7-M-E post-fix, `T0.7-M-E-reporte.md` sección 2.6):
- `S6-K2P0`: `AssertionError: S6-K2P0: numero de posiciones cambio -- congelado=633 actual=624.`
- `S7-TPNONE`: `AssertionError: S7-TPNONE: numero de posiciones cambio -- congelado=717 actual=708.`
- `SuperTrend-p14x3-M15`: mismo número de posiciones, posición `#102` difiere:
  `{'entry_delay_bars': (0, 1), 'entry_fill': (4768.84, 4770.43), 'margin1': (4466018.66, 4467507.695),
  'net1': (-507583.0000000068, -656486.5000000205), 't_in_exec': (1775754000.0, 1775758500.0)}`.

No apareció un cuarto caso de fallo. No se re-congeló la línea base, no se agregó `skip`/`xfail`,
no se tocó `research/fases/F0-preparacion/04-resultados/T0.6-baseline/`.

### git status

Antes (`scripts/analysis/a6_pata_a/` y `tests/analysis/`, filtrado):
```
?? scripts/analysis/a6_pata_a/barras_nativas_vs_derivadas.py
?? scripts/analysis/a6_pata_a/capa3_gate_spread.py
?? scripts/analysis/a6_pata_a/exp_active_fichas.py
?? scripts/analysis/a6_pata_a/fills_vs_feed_capitaria.py
?? scripts/analysis/a6_pata_a/signal_level.py
?? tests/analysis/test_bar_fill.py.OBSOLETO
```

Después del commit `43785dc` (mismo filtro):
```
?? scripts/analysis/a6_pata_a/barras_nativas_vs_derivadas.py
?? scripts/analysis/a6_pata_a/capa3_gate_spread.py
?? scripts/analysis/a6_pata_a/exp_active_fichas.py
?? scripts/analysis/a6_pata_a/fills_vs_feed_capitaria.py
?? tests/analysis/test_bar_fill.py.OBSOLETO
```
`scripts/analysis/a6_pata_a/signal_level.py` deja de aparecer como `??`: entra a control de
versión por primera vez con el commit `43785dc`. `barras_nativas_vs_derivadas.py`,
`capa3_gate_spread.py`, `exp_active_fichas.py`, `fills_vs_feed_capitaria.py` siguen `??`
(no tocados, no son de esta tarea).

## Artefactos producidos

- `scripts/analysis/a6_pata_a/signal_level.py` (modificado -- primera vez en control de versión)
- `tests/analysis/test_lookahead_ticksava.py` (nuevo)
- `research/fases/F0-preparacion/02-specs/T0.7-M-F-progreso.md` (nuevo)
- `research/fases/F0-preparacion/04-resultados/T0.7-p-cap/fix_lookahead_ticksava.md` (este fichero)
