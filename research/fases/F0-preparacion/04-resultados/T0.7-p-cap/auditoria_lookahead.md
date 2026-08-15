# T0.7-M-C — Auditoría look-ahead del harness de backtest largo

INVESTIGADOR REPORT-ONLY. Sin conclusiones ni recomendaciones: números, rutas,
conteos, citas `file:line` y salidas de comandos.

Brief: `research/fases/F0-preparacion/02-specs/T0.7-M-C-brief-auditoria-lookahead-harness.md`

## Lineage

- run_id: `T0.7-M-C-auditoria-lookahead-20260815T201813Z`
- git_sha: `ef243e362597df9816e7a21157c324f5b2a33c05`
- generador: `scripts/analysis/realtick_bt/auditoria_lookahead.py`
- artefactos hermanos: `auditoria_lookahead.json` (completo, máquina),
  `auditoria_lookahead.csv` (rejilla Q4/Q5 sobre Capitaria, 1.536 filas),
  `auditoria_lookahead_ava_q6.csv` (13.672 llamadas genuinas del backtest
  largo AVA, Q6)

---

## Pregunta 1 — `first_at`: comportamiento exacto

Cita verbatim, `scripts/analysis/realtick_bt/backtest.py:130-139`:

```python
def first_at(self, t_sec: float):
    """First tick with t >= t_sec (spills across month files as needed)."""
    for ym in self._candidates(t_sec):     # chronological -> first hit is the earliest
        ta, bid, ask = self._load(ym)
        if not len(ta):
            continue
        i = int(np.searchsorted(ta, t_sec, "left"))
        if i < len(ta):
            return float(ta[i]), float(bid[i]), float(ask[i])
    return None
```

`_candidates(t_sec)` (`backtest.py:113-128`) devuelve exactamente 3 meses:
`[mes(t_sec)-1, mes(t_sec), mes(t_sec)+1]`, en orden cronológico. `first_at`
recorre esos 3 ficheros en ese orden y devuelve el **primer** tick con
`t >= t_sec` que encuentre en cualquiera de ellos.

**¿Puede devolver un tick arbitrariamente lejano?** Acotado solo por los 3
meses candidatos, NO por ninguna distancia temporal. Demostrado con datos
sintéticos (`tests/analysis/test_lookahead_harness.py`):

- `test_first_at_salta_un_hueco_artificial_sin_cota`: hueco artificial de
  3.900 s → `first_at` devuelve el tick de después del hueco, salto de
  3.800 s, sin error ni marca de distancia.
- `test_first_at_cruza_fichero_de_mes_sin_cota`: sin más ticks en el mes
  pedido, toma el primer tick del mes SIGUIENTE aunque esté a >39 días.
- `test_first_at_no_comprueba_distancia_devuelve_precio_tal_cual`: el precio
  del tick lejano se devuelve idéntico al almacenado, sin ninguna marca.

**¿Qué devuelve si no hay ningún tick posterior?** `None`, solo si NINGUNO
de los 3 meses candidatos tiene un tick con `t >= t_sec`
(`test_first_at_devuelve_none_si_no_hay_tick_posterior_en_los_3_meses`).

**¿Cruza ficheros de mes?** Sí, sin cota — confirmado por
`test_first_at_cruza_fichero_de_mes_sin_cota`.

Comando + salida real:

```
$ python -m pytest tests/analysis/test_lookahead_harness.py -q
................                                                         [100%]
16 passed in 1.34s
```

## Pregunta 2 — las dos llamadas del harness

### `backtest.py:353` (dentro de `resolve()`, entrada)

Bloque completo (`backtest.py:343-362`):

```python
    side_l = pos["side_l"]
    lo = int(np.searchsorted(bar_times, pos["t_in"], "left"))
    hi = int(np.searchsorted(bar_times, pos["t_out"], "right"))
    hi = min(hi, lo + 1 + MAX_RETRY_BARS)
    entry = None
    delay_bars = 0
    for bi in range(lo, max(lo + 1, hi)):
        tc = float(bar_times[bi]) + BAR_SEC
        if tc >= pos["t_out"] + BAR_SEC:            # would open at/after its own exit
            break
        e = ticks.first_at(tc)
        if e is None:
            continue
        _, ebid, eask = e
        sp = eask - ebid
        if abs(sp - 0.5) <= 0.05:
            entry = (tc, ebid, eask, round(sp, 3)); delay_bars = bi - lo; break
```

- **Instante pasado:** `tc = bar_times[bi] + BAR_SEC` — el cierre de una vela
  M15 candidata (la vela de la señal, o hasta `MAX_RETRY_BARS=1` vela más).
- **¿Se comprueba la distancia entre el tick devuelto y `tc`?** NO. Barrido
  del cuerpo completo de `resolve()` (`backtest.py:336-395`) y de todo
  `backtest.py`: no existe ninguna comparación `e[0] - tc`, ni constante de
  tolerancia temporal (`grep -n "MAX_DELAY\|tolerance\|abs(.*first_at"
  scripts/analysis/realtick_bt/backtest.py` → sin resultados).
- **¿Qué se hace con el tick devuelto?** `ebid`/`eask` se usan para calcular
  el spread (`sp = eask - ebid`), que decide si pasa el gate `0.5±0.05`, y
  si pasa, `eask`/`ebid` se usan directamente como `entry_fill`
  (`entry_fill = eask if side_l == "L" else ebid`, `:364`). Es a la vez el
  precio de entrada Y la evaluación del gate de spread.

### `backtest.py:383` (dentro de `resolve()`, salida fallback)

Bloque completo (`backtest.py:366-387`):

```python
    reason = pos["reason"]; level = pos["exit_bid"]
    t_out_close = pos["t_out"] + BAR_SEC
    exit_fill = None; t_exit = t_out_close; slipped = False
    if reason in LEVEL_EXITS and not pos["same_bar"]:
        tt, bb, aa = ticks.range(pos["t_out"], t_out_close)
        ...
    if exit_fill is None:                           # bar-close exit (or level un-crossed)
        x = ticks.first_at(t_out_close)
        if x is None:
            return None
        _, xbid, xask = x
        exit_fill = xbid if side_l == "L" else xask
```

- **Instante pasado:** `t_out_close = pos["t_out"] + BAR_SEC` — el cierre de
  la vela de salida (`pos["t_out"]` es un `bar["t"]`).
- **¿Se comprueba la distancia?** NO, mismo barrido, mismo resultado: no
  existe.
- **Qué se hace con el tick devuelto:** `xbid`/`xask` se usan DIRECTAMENTE
  como `exit_fill` (precio de salida) cuando el nivel server-side no fue
  cruzado intra-vela.

Ambas llamadas SIEMPRE pasan un argumento de la forma
`"límite de vela M15" + BAR_SEC(900)` — un cierre de vela.

## Pregunta 3 — otras llamadas (barrido repo-wide)

Comando: `Grep "first_at|last_at|searchsorted|\.range\(" D:\FOREX` (excluyendo
`faulty/` y `data/analysis/p_cap/`, prohibidos). 34 ficheros con coincidencia;
tras filtrar por relevancia (acceso a ticks por instante, no `Index`/barras):

| file:line | clase | nota |
|---|---|---|
| `scripts/analysis/realtick_bt/backtest.py:353` | `bt.Ticks.first_at` | bajo auditoría (Q2) |
| `scripts/analysis/realtick_bt/backtest.py:383` | `bt.Ticks.first_at` | bajo auditoría (Q2) |
| `scripts/research/backtest_largo_ava.py` (clase `AvaTicks`) | subclase de `bt.Ticks`; `first_at`/`range`/`_candidates` HEREDADOS byte-idénticos, solo `_load` sobrescrito | **es "el motor de backtest largo"** — produjo `F0-BT-LARGO-0001`. Ver Q6. |
| `scripts/analysis/a6_pata_a/signal_level.py:90-133` | `Ticks` propia, reimplementación independiente (mismo patrón/mismo comportamiento) | NO es la clase del harness — módulo A6 aparte |
| `scripts/analysis/a6_pata_a/capa3_gate_spread.py:36-38,111-168` | importa `Ticks`/`resolve` de `backtest.py` (read-only) | replica las dos llamadas para instrumentar el gate de spread — análisis A6 aparte |
| `scripts/analysis/a6_pata_a/exp_active_fichas.py:195,112` | `bt.Ticks` + `bt.resolve` importados de `backtest.py`, sin copiar | llama a los MISMOS `backtest.py:353/:383` desde otro caller (confirmado por import) |
| `scripts/analysis/a6_pata_a/capa1_senal_cruda.py:389,390` | `bt.Ticks` + `bt.run_supertrend` importados | `run_supertrend()` usa SOLO `ticks.range(t0,t1)` (`backtest.py:313`), **nunca** `first_at()` — `range()` está acotado por los dos argumentos, no busca hacia adelante sin cota. DESCARTADO de esta familia de riesgo. |
| `tests/analysis/test_realtick_pairing.py:61-78` | `Ticks` propia en fixture de test | reimplementación independiente, no es el harness |
| `sentinel_engine/ai/dossier.py:254`, `sentinel_engine/opt/fast_replay.py:230,236,528,561`, `sentinel_engine/service/routers/runs.py:81` | `pandas Index.searchsorted` | DESCARTADO: lookup "as-of" HACIA ATRÁS sobre barras (`side="right")-1`), no acceso a ticks por instante hacia adelante |
| `web/vendor/uplot/uPlot.iife.min.js` | JS minificado, `.range(` genérico | falso positivo, sin relación |

## Pregunta 4 — medición sobre Capitaria (ambigüedad declarada + rejilla)

**Ambigüedad declarada:** `_bars_M15.parquet` (sustrato de barras del harness
Capitaria) cubre solo hasta `2026-07-24 16:45:00`
(`python -c "import pandas as pd; from datetime import datetime; df=pd.read_parquet('data/lake_ticks/XAUUSD/_bars_M15.parquet'); print(datetime.utcfromtimestamp(df.t.max()))"`
→ `2026-07-24 16:45:00`), ANTES de la ventana pedida
`2026-07-27 → 2026-08-11`. El harness NO PUEDE generar posiciones
(ENTRY/EXIT) reales en esa ventana por falta de barras.

**Rejilla declarada** (`decision_grid()`,
`scripts/analysis/realtick_bt/auditoria_lookahead.py`): dado que ambos call
sites del Q2 SIEMPRE construyen su argumento como "límite de vela M15 +
`BAR_SEC`" (un cierre de vela), se generan TODOS los cierres de vela M15
(múltiplos de 900 s) en `[2026-07-27 00:00:00, 2026-08-12 00:00:00)` hora
servidor, y se les aplica `ticks.first_at()` (la clase `Ticks` real, sin
tocar) directamente contra `data/lake_ticks/XAUUSD/*.parquet` (filtrado
`^[0-9]{6}$`, excluye `_bars_M15.parquet` y `.bak`).

Comando:

```
$ python -m scripts.analysis.realtick_bt.auditoria_lookahead
```

Salida (sección Q4, `resumen_delays_q4` del JSON):

```json
{
  "n_total": 1536,
  "n_evaluable": 1530,
  "n_no_evaluable": 6,
  "p50": 0.1755000352859497,
  "p90": 108005.8942000389,
  "p99": 169844.8945800114,
  "max": 176405.89599990845,
  "n_gt_60s": 432,
  "n_gt_15min": 432,
  "n_gt_1h": 396
}
```

- `n=1536` instantes en la rejilla (15,5 días × 96 cierres M15/día).
- `n_no_evaluable=6`: los 6 últimos cierres del `2026-08-11` (22:30→23:45),
  porque `data/lake_ticks/XAUUSD/202608.parquet` termina en
  `2026-08-11 22:27:31.136` (verificado: max `t_msc` del fichero) — no hay
  ningún tick posterior en los 3 meses candidatos. Es borde del lago, no un
  hueco de mercado.
- `p50 = 0.18 s` (la inmensa mayoría de instantes cae en horario líquido).
- `max = 176.405,90 s` (≈2,04 días) — mismo orden de magnitud que el caso de
  fin de semana citado en el brief (176.699 s).
- `n_gt_60s = n_gt_15min = 432` (idéntico): no hay ningún caso con delay
  entre 60 s y 15 min en esta rejilla — la distribución es bimodal (casi
  nada, o el hueco completo).
- `n_gt_1h = 396`.

## Pregunta 5 — cruce con huecos conocidos (corte de mantenimiento / fin de semana)

Clasificación (`clasificar_hueco()`) sobre los 432 casos con delay > 60 s,
usando los horarios MEDIDOS del brief (corte normal 16:59-17:59 hora
servidor; viernes 16:55-18:49) + fin de semana (sábado/domingo completos):

```json
{
  "fin_de_semana": 376,
  "corte_mantenimiento": 56,
  "otro": 0
}
```

**Corrección aplicada durante esta tarea:** la primera versión de
`clasificar_hueco` dejaba 40 casos en `"otro"` — los 40 correspondían a
`2026-07-31 19:00..23:45` y `2026-08-07 19:00..23:45` (viernes, DESPUÉS del
fin del corte ampliado 18:49). Verificado con los propios datos: los 20
instantes del viernes `2026-07-31 19:00→23:45` devuelven TODOS el mismo tick
`2026-08-02 18:00:05.896` (domingo) — es la cola continua del mismo cierre
semanal, no un hueco distinto. `clasificar_hueco` se corrigió para que
viernes > 18:49 clasifique `fin_de_semana`. Tras la corrección, `otro = 0`:
el 100 % de los 432 casos > 60 s cae en corte de mantenimiento o fin de
semana.

Ejemplos (5 de cada categoría, `t_pedido` → `t_devuelto`, `delta_s`):

**`fin_de_semana`:**

| t_pedido | t_devuelto | delta_s |
|---|---|---:|
| 2026-07-31 19:00:00 | 2026-08-02 18:00:05.896 | 169.205,90 |
| 2026-07-31 19:15:00 | 2026-08-02 18:00:05.896 | 168.305,90 |
| 2026-07-31 19:30:00 | 2026-08-02 18:00:05.896 | 167.405,90 |
| 2026-07-31 19:45:00 | 2026-08-02 18:00:05.896 | 166.505,90 |
| 2026-07-31 20:00:00 | 2026-08-02 18:00:05.896 | 165.605,90 |

**`corte_mantenimiento`:**

| t_pedido | t_devuelto | delta_s |
|---|---|---:|
| 2026-07-27 17:00:00 | 2026-07-27 18:00:05.732 | 3.605,73 |
| 2026-07-27 17:15:00 | 2026-07-27 18:00:05.732 | 2.705,73 |
| 2026-07-27 17:30:00 | 2026-07-27 18:00:05.732 | 1.805,73 |
| 2026-07-27 17:45:00 | 2026-07-27 18:00:05.732 | 905,73 |
| 2026-07-28 17:00:00 | 2026-07-28 18:00:06.393 | 3.606,39 |

## Pregunta 6 — ¿contamina esto `F0-BT-LARGO-0001`?

`F0-BT-LARGO-0001` corrió sobre AVA (`substrate_id:
ava-ticks-2022-2026-sans-holdout`, git_sha `86166f1`, ledger
`research/LEDGER.jsonl`), vía `scripts/research/backtest_largo_ava.py`, cuya
clase `AvaTicks` hereda `first_at`/`range`/`_candidates` de `bt.Ticks`
BYTE-IDÉNTICOS (solo `_load` está sobrescrito — confirmado por lectura del
módulo, líneas 10-16 y 274-315).

**Método:** en vez de una rejilla aproximada, se reprodujeron las llamadas
GENUINAS: se subclaseó `AvaTicks` (`_AvaTicksInstrumentado`, solo registra el
argumento antes de delegar a `super().first_at()`, sin tocar
`backtest_largo_ava.py` ni `backtest.py`) y se corrió `bt.build_all()` sobre
los `bars_final` reales (mismas funciones de carga/filtrado que usa el
propio `backtest_largo_ava.py`: `load_bars_ava`, `ventana_calendario.filter_bars`,
`filter_exclusiones`), modo `mediana` (el `modo_principal` del ledger).

Comando: el mismo `python -m scripts.analysis.realtick_bt.auditoria_lookahead`
de arriba (sección `q6_ava_f0_bt_largo_0001` del JSON). Verificación de
fidelidad de la reproducción: el conteo de posiciones por estrategia coincide
EXACTO con `F0-BT-LARGO-0001` (`research/LEDGER.jsonl`):

| estrategia | n (esta corrida) | n (`F0-BT-LARGO-0001`, ledger) |
|---|---:|---:|
| S6-K2P0 | 4.578 | 4.578 |
| S7-TPNONE | 5.364 | 5.364 |
| SuperTrend-p14x3-M15 | 1.617 | 1.617 |

Salida real:

```json
{
  "modo": "mediana",
  "n_bars_final": 31700,
  "n_llamadas_first_at": 13672,
  "tiempo_medido_seg": 173.53,
  "resumen_delays": {
    "n_total": 13672, "n_evaluable": 13672, "n_no_evaluable": 0,
    "p50": 0.10800004005432129, "p90": 3.2682999134063624,
    "p99": 23400.06544007063, "max": 76129.38899993896,
    "n_gt_60s": 945, "n_gt_15min": 736, "n_gt_1h": 651
  },
  "n_llamadas_dentro_de_exclusion_ava": 1,
  "n_intervalos_exclusion_ava": 44,
  "ejemplos_llamadas_dentro_de_exclusion": ["2026-02-20T00:00:00"]
}
```

**Cruce con `exclusiones-ava.json`** (44 intervalos, ya construidos por T0.3,
huecos intradía de continuidad del feed de AVA dentro de la ventana
operativa): de las **13.672 llamadas genuinas** a `first_at()` que el motor
largo hizo de verdad al correr sobre AVA, **1 sola** cae dentro de alguno de
los 44 intervalos declarados (`2026-02-20T00:00:00`).

**Dato aparte, sin cruzar con la lista declarada:** de esas mismas 13.672
llamadas, **945 (6,9 %)** tienen `t_devuelto - t_pedido > 60 s`, **736
(5,4 %)** > 15 min, y **651 (4,8 %)** > 1 h — usando el propio retorno real
de `first_at()`, no una estimación. `exclusiones-ava.json` solo captura
huecos intradía DENTRO de la ventana operativa filtrada por
`ventana_calendario.filter_bars`; estos 945 casos no se cruzaron contra
ningún otro catálogo de huecos de AVA (declarado en Pregunta 7).

Top-10 delays (mayor a menor):

| t_pedido | t_devuelto | delta_s |
|---|---|---:|
| 2026-02-22 23:15:00 | 2026-02-23 20:23:49.389 | 76.129,39 |
| 2026-01-21 23:15:00 | 2026-01-22 20:18:22.556 | 75.802,56 |
| 2026-02-22 23:30:00 | 2026-02-23 20:23:49.389 | 75.229,39 |
| 2026-01-21 23:30:00 | 2026-01-22 20:18:22.556 | 74.902,56 |
| 2026-01-29 23:15:00 | 2026-01-30 16:20:28.619 | 61.528,62 |
| 2026-01-29 23:30:00 | 2026-01-30 16:20:28.619 | 60.628,62 |
| 2026-02-20 00:00:00 | 2026-02-20 14:44:35.390 | 53.075,39 |
| 2026-01-22 23:15:00 | 2026-01-23 12:08:21.552 | 46.401,55 |
| 2026-01-22 23:30:00 | 2026-01-23 12:08:21.552 | 45.501,55 |
| 2026-02-04 23:15:00 | 2026-02-05 08:00:00.091 | 31.500,09 |

Datos crudos completos (13.672 filas): `auditoria_lookahead_ava_q6.csv`.

## Pregunta 7 — no evaluables

- **Réplica (`faulty/`, `data/analysis/p_cap/`):** PROHIBIDO leer por
  frontera de fichero (otro agente editando en paralelo). No evaluable desde
  esta tarea. Todo lo citado del comportamiento de la réplica en este informe
  proviene literalmente del brief, no de lectura propia.
- **Q4/Q5 con posiciones REALES de Capitaria en la ventana
  2026-07-27→2026-08-11:** no evaluable — `_bars_M15.parquet` no cubre esa
  ventana (ver Q4). Se usó la rejilla declarada como sustituto explícito.
- **Q6, modo `media`** (la segunda variante de overlay de costes que
  `backtest_largo_ava.py` también corre): no evaluable en esta tarea por
  costo (cada modo tarda ≈174 s; se corrió solo `mediana`, el
  `modo_principal` declarado en el ledger de `F0-BT-LARGO-0001`). No se
  estimó su resultado.
- **Q6, los 945/736/651 casos > 60s/15min/1h fuera de `exclusiones-ava.json`:**
  no se cruzaron contra ningún catálogo adicional de huecos de AVA (fuera de
  alcance de esta tarea — `exclusiones-ava.json` es la única lista que el
  brief cita). Se reportan como hecho crudo, sin clasificar por causa.
- **Comparación cuantitativa de magnitud entre el defecto en la réplica y en
  el motor largo** (p. ej. "¿es igual de severo?"): no evaluable por este
  investigador — es interpretación, prohibida por el rol REPORT-ONLY.
