# TK-BW Fixes Matrix — 5 configs, run first, graph after (2026-07-22)

> Contexto: el veredicto TK-BW (2026-07-21/22) probó: (1) as-written 0 trades
> (c1 pullback vs c4 breakout geométricamente incompatibles), (2) forzada con
> c1_tol pierde (M5 k3-c3: 80 fichas, net −167.90, 70% de entradas adversas a
> 30 min), (3) el inverso también pierde (WR 11%, no 97%) porque las salidas
> dominan (47/80 scratches en BE +0.60; TP1/TP2 netos NEGATIVOS −41.59),
> (4) 29% de la pérdida es spread. Este plan construye la matriz de fixes que
> el usuario pidió ver corriendo y graficada: un run por fix aislado + uno
> con todos combinados. NO es un sweep de optimización: son 5 configs fijas,
> derivadas 1:1 del diagnóstico, corridas una vez y registradas.

## Global Constraints (BINDING)

- **Motor NUEVO aditivo** `sentinel_engine/strategies/tk_bw_v2.py`. PROHIBIDO
  modificar `tk_bw.py`, `run_tk_bw_backtest.py`, o cualquier motor existente.
- Pure function, sin I/O, sin MT5, sin wall-clock. Mismo **step contract** que
  `tk_bw.tk_bw_run` (ver docstring de `tk_bw.py`): steps construidos por el
  runner con `{"ts","closed","forming","price","is_close"}`, barras BID.
- Indicadores SOLO via `emasar_ref` (`ema_series`, `sar_series`, `ao_series`,
  `ac_series`, `momentum_series`, `_atr_wilder`) y `_supertrend_ref.supertrend`
  — NO reimplementar matemática de indicadores.
- Convención spread/fills/pnl/MAE-MFE/trade-dict **idéntica byte-a-byte** a
  `tk_bw.py` (spread 0.60 constante, LONG compra ask `price+S` sale bid,
  SHORT vende bid sale ask `exit_bid+S`, 1 ficha=0.01 lot=1oz ⇒ pnl=delta
  firmado, 3 fichas F1/F2/F3, stop común, dict de trade con las mismas keys).
- **PARITY GATE (test obligatorio):** `tk_bw_v2_run` con
  `entry_mode="forced", regime_mode="full5", stop_mode="fixed",
  tp_mode="pattern"` y los mismos params debe producir la MISMA lista de
  trades (byte-idéntica) que `tk_bw.tk_bw_run` sobre los mismos steps.
- Windows 10+11: pathlib, utf-8 explícito. Tests deterministas, sin red.
- Commits: SOLO los archivos propios de cada task (el repo tiene trabajo sin
  commitear de otros focos — NO stagear nada ajeno).
- Cuentas: ninguna interacción con MT5 en este plan (todo es lake + sqlite).

## Motor — firma exacta (Task 1)

```python
def tk_bw_v2_run(
    steps, *,
    spread=0.60, commission=0.0,
    ema_fast=5, ema_slow=8, sar_step=0.3, sar_max=30.0,
    mom_period=14, st_period=14, st_mult=3.0,
    regime_lookback=3,
    # --- entrada ---
    entry_mode="forced",        # "forced" | "sequence"
    c1_tol=3.0,                 # solo forced
    seq_timeout=6,              # sequence: velas nativas armado antes de desarmar
    # --- régimen ---
    regime_mode="full5",        # "full5" | "simple"
    session_hours=None,         # None | (start_h, end_h) hora del bar-clock, gate SOLO de entrada
    # --- stops ---
    stop_mode="fixed",          # "fixed" | "atr"
    init_sl_offset=0.60, be_trigger=0.60, trail_usd=5.0,    # fixed
    atr_sl_mult=1.5, atr_be_mult=1.0, atr_trail_mult=2.5,   # atr (ATR14 congelado al entrar)
    # --- take profits ---
    tp_mode="pattern",          # "pattern" | "r"
    r1_mult=1.0, r2_mult=2.0,   # r: F1 a 1R, F2 a 2R, F3 solo trailing
    allow_long=True, allow_short=True,
) -> list[dict]  # mismo trade dict que tk_bw_run; exit_reason añade "TP1R","TP2R"
```

### Semántica BINDING

**Régimen** (velas nativas CERRADAS, sin repaint, igual que v1):
- `full5` LONG: EMA5, EMA8, AO, MOM, AC todos `cur > back(K)` **y**
  `sar_cur < ema8_cur`. SHORT espejado (`cur < back(K)`, `sar_cur > ema8_cur`).
- `simple` LONG: `st_trend_cur == 1` **y** `ema8_cur > ema8_back(K)`.
  SHORT: `st_trend_cur == -1` **y** `ema8_cur < ema8_back(K)`.
- None en cualquier serie requerida ⇒ flag False (igual que v1).

**Session gate**: si `session_hours=(a,b)`, la ENTRADA solo se permite cuando
`a <= hour_utc(step.ts) < b` (hora del timestamp del bar tal como está en el
lake). Salidas/stops SIEMPRE activos, sin gate.

**Entrada `forced`**: lógica c1..c9 de v1 calcada (con `c1_tol` aditivo,
mismas comparaciones, mismo `_last_native_extreme`, mismo bloqueo de
re-entrada por vela nativa `blocked_native_idx`).

**Entrada `sequence`** (máquina de estados, LONG; SHORT espejado):
1. ARMADO — se evalúa cada vez que una vela nueva aparece en `closed`
   (detectar por `len(closed)` creciente entre steps). Si en ese step
   `regime_long` es True **y** `new_candle["low"] <= ema8_cur` (la EMA8 de
   cierres que YA incluye esa vela) ⇒ `armed_long=True`,
   `breakout_level = new_candle["high"]`,
   `pullback_low = new_candle["low"]`,
   `armed_until = n_closed + seq_timeout`.
   Un nuevo touch mientras está armado REEMPLAZA nivel y expiración.
2. DESARME — si `n_closed > armed_until` o `regime_long` deja de ser True.
3. DISPARO — en cualquier step (intrabar) con `armed_long` y `regime_long`
   y session gate OK y plano (sin posición, y respetando
   `blocked_native_idx`): `price > breakout_level` ⇒ entra LONG,
   `px_in = price + spread`. Al entrar se desarman ambos lados.
   SHORT espejado: touch `new_candle["high"] >= ema8_cur`,
   `breakout_level = new_candle["low"]`, `pullback_high = new_candle["high"]`,
   dispara `price < breakout_level`, `px_in = price`.

**SL inicial**:
- `fixed` + forced: igual a v1 (prev_bear.low − offset / prev_bull.high + offset).
- `fixed` + sequence: `pullback_low − init_sl_offset` (LONG) /
  `pullback_high + init_sl_offset` (SHORT).
- `atr` (ambos entry modes): `entry_bid − atr_sl_mult*ATR` (LONG) /
  `entry_bid + atr_sl_mult*ATR` (SHORT), donde `entry_bid = price` en el step
  de entrada y `ATR` = último valor no-None de
  `_atr_wilder(highs, lows, closes, 14)` sobre las velas CERRADAS en ese step,
  **congelado** para toda la vida de la posición. Si ATR es None ⇒ NO entrar.

**Runtime de stops** (mismo esqueleto v1: SL-first, gap-open rule, ratchet
monotónico, MAE/MFE por ficha):
- `fixed`: BE arma a `±be_trigger` (BE sl LONG=`px_in`, SHORT=`px_in−spread`),
  trailing `trail_usd` ratchet. Idéntico a v1.
- `atr`: BE arma a `±atr_be_mult*ATR_entry`; trailing usa
  `atr_trail_mult*ATR_entry` como distancia (reemplaza `trail_usd`); misma
  convención de BE sl y mismo ratchet.

**Take profits**:
- `pattern`: TP1/TP2/TP3 idénticos a v1 (mismas condiciones, mismos px_out).
- `r`: define `R = |entry_bid − sl_inicial_bid|` al entrar (entry_bid =
  `px_in − spread` LONG, `px_in` SHORT). En CUALQUIER step:
  F1 cierra si `price >= entry_bid + r1_mult*R` (LONG; SHORT espejado con −),
  `exit_reason="TP1R"`; F2 igual con `r2_mult*R`, `exit_reason="TP2R"`.
  px_out = `price` (LONG) / `price + spread` (SHORT) — misma convención TP v1.
  F3 NO tiene TP (sale solo por SL/BE/trail). TP3-SuperTrend NO existe en
  modo r.

## Runner — `scripts/research/run_tk_bw_v2_backtest.py` (Task 2)

- **REUTILIZA** de `scripts.research.run_tk_bw_backtest` (import, NO copiar):
  `_df_to_bars`, `build_steps`, `compute_metrics`, `build_params_delta`,
  `_iso_utc`, y las constantes de ventana (`DESDE_DEFAULT`,
  `WARMUP_LOOKBACK`). Symbol XAUUSD, TF **M5 únicamente** (tf_minutes=5).
- CLI: `--lake-root`, `--db`, `--desde` (default 2026-07-20T00:00:00Z),
  `--hasta` (default última barra), `--write` (default dry-run),
  `--configs` (lista coma, default las 5).
- **Las 5 configs — EXACTAS, no tunables por CLI** (dict CONFIGS):

| key | entry_mode | regime_mode | session_hours | stop_mode | tp_mode | resto |
|---|---|---|---|---|---|---|
| `fix1seq` | sequence | full5 | None | fixed | pattern | seq_timeout=6 |
| `fix2atr` | forced (c1_tol=3.0) | full5 | None | atr | pattern | 1.5/1.0/2.5 |
| `fix3r`   | forced (c1_tol=3.0) | full5 | None | fixed | r | 1R/2R |
| `fix4reg` | forced (c1_tol=3.0) | simple | (7,17) | fixed | pattern | K=3 |
| `fixall`  | sequence | simple | (7,17) | atr | r | seq_timeout=6, 1.5/1.0/2.5, 1R/2R |

  Comunes a todas: spread 0.60, commission 0, ema 5/8, sar 0.3/30, mom 14,
  st 14/3.0, regime_lookback=3, fixed 0.60/0.60/5.0, volume 0.01, 3 fichas.
- Registro (mismo patrón que el runner v1):
  - strategy `upsert_strategy(name="tk_bw_v2", familia="TK", platform="python-sim")`
  - variant_id `TK_XAUUSD_BW2_M5-<key>`
  - run_id `sim-tk_bw2-m5-<desde YYYYMMDD>-<hasta YYYYMMDD>-<key>`
  - engine `"sentinel-sim"`, fidelity `"research"`, status `"done"`,
    modelo_sim `tk_bw_v2-intrabar-m1-<key>`
  - metrics_json incluye el dict COMPLETO de la config + coverage (mismo
    formato v1) + `"fix_matrix": "2026-07-22"`.
  - params_delta = `build_params_delta()` del runner v1 (EmasarPolicy-safe,
    validar con `EmasarPolicy(params_delta)` antes de escribir).
  - trades con signal_id compartido por (ts_in, side) y ficha, igual v1.
- Filtro de trades a `[desde, hasta]` por ts_in y sort igual v1.
- Dry-run imprime por config: `trades / signals / net / pf / wr / maxdd` en
  una tabla, y NO escribe.

## Tests

**Task 1** (`tests/strategies/test_tk_bw_v2.py`):
1. PARITY: forced/full5/fixed/pattern (mismos params que v1 defaults con
   regime_lookback=3, c1_tol=3.0) sobre una secuencia sintética de steps que
   genera ≥2 trades ⇒ lista de trades == `tk_bw.tk_bw_run(...)` exacta.
2. sequence: touch arma (candle.low<=EMA8 en régimen long), breakout dispara
   intrabar, `px_in=price+spread`.
3. sequence: timeout desarma (sin breakout en seq_timeout velas ⇒ no entra).
4. sequence: pérdida de régimen desarma.
5. atr: SL inicial a 1.5*ATR del entry_bid; BE arma a 1.0*ATR; trail 2.5*ATR
   ratchet (solo aprieta).
6. r: F1 cierra a +1R y F2 a +2R con exit_reason TP1R/TP2R; F3 sigue viva y
   sale por trailing/SL; en modo r NO dispara TP3.
7. session gate: entrada bloqueada fuera de (a,b), permitida dentro; una
   posición abierta SÍ se gestiona (stop ejecuta) fuera de sesión.
8. warmup: ATR None ⇒ no entra (modo atr).

**Task 2** (`tests/scripts/test_run_tk_bw_v2.py` — mismo patrón que
`tests/scripts` existentes):
1. CONFIGS: exactamente 5 keys con los valores de la tabla (assert dict).
2. run_id/variant_id con sufijo correcto por config.
3. dry-run (sin --write) no toca la DB (tmp_path db).
4. --write registra 5 runs + trades y params_delta pasa EmasarPolicy.
5. build_steps/compute_metrics importados del runner v1 (no duplicados) —
   assert por identidad de objeto (`is`).

## Tasks

- **Task 1 — Motor `tk_bw_v2.py` + tests.** Archivos:
  `sentinel_engine/strategies/tk_bw_v2.py`,
  `tests/strategies/test_tk_bw_v2.py`. Gate: suite del task verde + parity
  test verde. Commit solo esos 2 archivos.
- **Task 2 — Runner `run_tk_bw_v2_backtest.py` + tests.** Archivos:
  `scripts/research/run_tk_bw_v2_backtest.py`,
  `tests/scripts/test_run_tk_bw_v2.py`. Depende de Task 1 (importa el
  motor). Gate: suite del task verde. Commit solo esos 2 archivos.

Después de Task 2 (orquestador, NO subagente): correr las 5 configs en
dry-run sobre el lake real, **notificar al usuario los resultados
preliminares ANTES de `--write`**, luego registrar y verificar en Trade View.
