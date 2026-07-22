# TK-BW — new trader strategy: backtest + registry + UI (design & plan)

> Fecha: 2026-07-21 · Autor: sesión brain unfiled-20260707 · Símbolo: XAUUSD
> Estado: aprobado por el trader (descripción textual + 4 respuestas de clarificación).
> Ejecutar con subagent-driven-development, implementers **Sonnet 5 high**, ≤2 en
> paralelo, jamás sobre los mismos archivos/tarea.

## Contexto (por qué)

Un trader ("TK") pidió una **estrategia nueva** de momentum/medias sobre oro y
quiere **ver su backtest de ayer (2026-07-20) y hoy (2026-07-21, hasta el último
dato ~16:58 hora broker)** en la Sentinel UI, en **"runs"** y en **"Trade View"**
(la vista REVIEW: gráfico de velas + marcadores de trades + curva de equity +
overlays de indicadores). Debe quedar **registrada** en `data/research.db`.

Es un **motor NUEVO y aditivo** (`tk_bw`): NO toca `simular_variant`,
`supertrend_always_in` ni `tk_momentum` (ese último es otra estrategia distinta:
SMA5/SMA8+MOM2 de una ficha). Este usa EMA8/EMA5 + Parabolic SAR(0.3,30) +
Awesome Oscillator + Momentum + Accelerator + SuperTrend + rupturas de vela, con
break-even + trailing y **3 fichas** con salidas independientes, en 3 timeframes.

Alcance de ESTA entrega: **backtest + registro + visibilidad en UI**. El cableado
LIVE (run_live_20 dispatch, banda magic, reconciler 3-fichas, loop 5s) queda como
follow-up explícito (NO en esta entrega).

## Decisiones cerradas por el trader (4 respuestas + follow-ups)

1. **Break-even trigger = +$0.60** desde el precio de apertura (pip = $0.01; "60
   pips" = 0.60 USD). Elegido explícitamente pese a la nota de inconsistencia.
   Resolución: **el trailing es un ratchet monótono que nunca afloja bajo BE**
   (tras BE el SL queda en la apertura hasta que el precio supere +$5, luego
   toma el trailing de $5).
2. **SAR = exactamente (0.3, 30.00)** — `sar_step=0.3`, `sar_max=30.0` (literal;
   es un SAR muy rápido, es intencional).
3. **Costos = spread 0.60 constante, comisión 0, swap 0** (verificado EN VIVO en
   la DEMO Capitaria XAUUSD: `commission+swap+fee=0` en 1.011 posiciones reales;
   spread 60 puntos × 0.01 = 0.60 USD). Lake bars = **BID** (copy_rates MT5).
4. **Granularidad = intra-vela por sub-pasos M1**: cada vela M2/M5/M15 en
   formación se reconstruye desde velas M1 y las condiciones de entrada/salida se
   reevalúan a resolución M1 (repinta, como el loop live de 5s). No hay ticks, así
   que M1 es el proxy más fino disponible.

## Supuestos documentados (defaults canónicos del repo; el trader puede corregir tras ver resultados)

- **Momentum**: `momentum_series(closes, 14)` (MT5 default 14; el overlay del UI
  también usa 14). "creciendo/decreciendo" = pendiente entre las **dos últimas velas
  NATIVAS cerradas** (ver "REGLA DE LECTURA" en Reglas: pendientes/régimen sobre
  cerradas, no sobre la vela en formación).
- **SuperTrend**: `_supertrend_ref.supertrend` con `st_atr_period=14`,
  `st_mult=3.0` (canónico repo, ATR de Wilder). "cambio de tendencia" = flip del
  signo de `trend` (de +1 a −1 = pasa a CORTO; de −1 a +1 = pasa a LARGO).
- **AO** = `ao_series` (SMA(median,5)−SMA(median,34)); **AC** = `ac_series`
  (AO−SMA(AO,5)). Ambos fijos 5/34/5. "creciendo/decreciendo" = pendiente 1 paso.
- **EMA8 / EMA5** = `ema_series(closes, 8)` / `ema_series(closes, 5)` (EMA con
  semilla SMA, parity iMA). "crecientes" = EMA actual > EMA del paso anterior.
- **Vela alcista** = `close>open`; **vela bajista** = `close<open`; doji
  (`close==open`) no es ni una ni otra (no dispara condiciones de vela).
- **"última vela bajista/alcista anterior"** = la vela NATIVA cerrada más reciente
  (antes de la vela en formación) cuyo cuerpo es bajista/alcista. Su `high`/`low`
  son los niveles de ruptura.
- **SL inicial** (relativo a esa vela, en términos BID):
  - LARGO: `sl_bid = low(última vela bajista) − 0.60`.
  - CORTO: `sl_bid = high(última vela alcista) + 0.60`.
- **Short TP2 (texto garbleado del trader)**: se asume **simétrico** al largo →
  "una vela alcista CIERRA sobre EMA8 **y** SAR bajo EMA8". (Largo TP2: "vela
  bajista cierra bajo EMA8 y SAR sobre EMA8".) FLAG: confirmar con trader.
- **Warmup**: se requieren ≥ ~39 velas NATIVAS cerradas antes de habilitar señales
  (AO/AC necesitan 34 + SMA5; SuperTrend ATR14). El runner carga lookback previo
  suficiente y sólo registra trades con `ts_in` dentro de [desde, hasta].

## Convención de spread / fills (para paridad con el mercado real)

Lake bars = BID. Spread constante `S=0.60`. Comisión 0.
- **LARGO**: entra comprando al ASK → `px_in = entry_bid + S`. Sale vendiendo al
  BID → `px_out = exit_bid`. `pnl = (px_out − px_in) × 1oz`.
- **CORTO**: entra vendiendo al BID → `px_in = entry_bid`. Sale comprando al ASK →
  `px_out = exit_bid + S`. `pnl = (px_in − px_out) × 1oz`.
- **1 ficha = 0.01 lote = 1 oz** (contract_size 100 ⇒ $1 por $1/oz de movimiento).
  `pnl` en USD = Δprecio × 1 (sin factor extra). 3 fichas por señal.
- **Niveles SL/TP/BE/trail se mantienen en términos BID.** Disparos:
  - LARGO stop: `bar.low ≤ sl_bid` ⇒ sale al `sl_bid` (o `bar.open` si abrió por
    debajo del SL, gap). `px_out = sl_bid` (venta al bid).
  - CORTO stop: `bar.high ≥ sl_bid` ⇒ `px_out = sl_bid + S` (compra al ask).
  - SL-first: si en el mismo paso colisionan stop y señal de salida, gana el stop.
- **Break-even**:
  - LARGO: gatilla cuando `precio_bid ≥ px_in + 0.60`; setea `sl_bid = px_in`
    (vender a px_in ⇒ pnl 0).
  - CORTO: gatilla cuando `precio_bid ≤ px_in − 0.60`; setea `sl_bid = px_in − S`
    (comprar a `sl_bid+S = px_in` ⇒ pnl 0).
- **Trailing $5 (post-BE, ratchet, nunca afloja bajo BE)**:
  - LARGO: `sl_bid = max(sl_bid, precio_bid − 5.0)`.
  - CORTO: `sl_bid = min(sl_bid, precio_bid + 5.0)`.

## Reglas de la estrategia (traducción cerrada de la descripción)

Indicadores: `EMA8`, `EMA5`, `SAR(0.3,30)`, `AO`, `AC`, `MOM(14)`,
`SuperTrend(14,3.0)`, todos con `emasar_ref`/`_supertrend_ref`.

**🔴 REGLA DE LECTURA (resuelve una contradicción matemática real):** una EMA es un
blend convexo `EMA_cur = k·price + (1−k)·EMA_prev`, así que "EMA creciente" (sobre el
valor repintado con la vela en formación) equivale a `price>EMA_prev`, lo que es
INCOMPATIBLE con "precio bajo EMA8". El setup del trader es un **pullback en
tendencia alcista** (comprar cuando el precio baja bajo una EMA8 que viene subiendo).
Por eso se separan dos tipos de condición:
- **Régimen / pendiente ("creciente/decreciente")** — EMA8, EMA5, AO, MOM, AC y la
  relación SAR↔EMA8 — se calculan sobre **velas NATIVAS CERRADAS**: "actual" = último
  cierre nativo, "previo" = penúltimo cierre nativo. NO usan la vela en formación (no
  repintan). "creciente" = valor(último cerrado) > valor(penúltimo cerrado);
  "decreciente" = <.
- **Nivel / gatillo en vivo** — precio vs EMA8, ruptura del máx/mín de la última vela
  opuesta, y si la vela en formación es alcista/bajista — usan el **precio actual
  (M1) y la vela en formación**. (Para el chequeo de nivel `precio < EMA8` da igual
  usar la EMA8 del último cierre o la repintada: ambas dan el mismo umbral por la
  convexidad.)
Así, entrar largo = "EMA8/EMA5 venían subiendo y momentum al alza (velas cerradas)
Y el precio hizo pullback bajo la EMA8 con una vela alcista que rompe el máx de la
última bajista (en vivo)". Coherente y dispara con datos reales.

### Entrada LARGO (las 5 condiciones, evaluadas cada sub-paso M1, estando PLANO)
1. `precio_bid < EMA8` **y** vela en formación alcista (`close>open` con el close
   = precio actual).
2. `SAR < EMA8`.
3. `precio_bid > high(última vela bajista anterior)` (rompe el máximo de la última
   bajista cerrada).
4. `EMA8` creciente **y** `EMA5` creciente (ambas > su valor del paso previo).
5. `AO`, `MOM(14)` **y** `AC` los tres crecientes.
⇒ abre **3 fichas LARGO** al `px_in = precio_bid + S`. SL inicial común
   `sl_bid = low(última vela bajista) − 0.60`.

### Entrada CORTO (espejo)
1. `precio_bid > EMA8` **y** vela en formación bajista.
2. `SAR > EMA8`.
3. `precio_bid < low(última vela alcista anterior)`.
4. `EMA8` y `EMA5` decrecientes.
5. `AO`, `MOM(14)`, `AC` los tres decrecientes.
⇒ abre **3 fichas CORTO** al `px_in = precio_bid`. SL inicial común
   `sl_bid = high(última vela alcista) + 0.60`.

### Stop común a las fichas abiertas (cada sub-paso)
SL inicial → BE al ±0.60 → trailing $5 ratchet (ver convención arriba). El stop
cierra CUALQUIER ficha que siga abierta (a `px_out` según convención).

### Take-profits por ficha (cada ficha cierra por SU condición O por el stop común, lo que ocurra primero)
LARGO:
- **F1 (TP1, intra-vela)**: vela en formación bajista **y** `precio_bid < low(última
  vela alcista anterior)` **y** `SAR > EMA8`.
- **F2 (TP2, al cierre de vela)**: una vela NATIVA bajista **cierra** por debajo de
  `EMA8` **y** `SAR > EMA8`.
- **F3 (TP3, al cierre de vela)**: SuperTrend hace flip a CORTO (trend +1→−1).

CORTO (espejo):
- **F1 (TP1, intra-vela)**: vela en formación alcista **y** `precio_bid > high(última
  vela bajista anterior)` **y** `SAR < EMA8`.
- **F2 (TP2, al cierre de vela)**: una vela NATIVA alcista **cierra** sobre `EMA8`
  **y** `SAR < EMA8` (simetría asumida, ver supuestos).
- **F3 (TP3, al cierre de vela)**: SuperTrend hace flip a LARGO (trend −1→+1).

### Invariantes
- **Una sola posición** (las 3 fichas nacen juntas de una señal). No re-entra
  mientras haya ≥1 ficha abierta. No re-entra en el mismo sub-paso/vela en que se
  cerró la última ficha (re-entrada recién en la vela nativa siguiente).
- Las condiciones "al cierre de vela" (F2, F3) sólo se evalúan en sub-pasos que
  cierran una vela nativa; F1, SL, BE y trailing se evalúan en cada sub-paso M1.

## Global Constraints (para reviewers — copiar verbatim)

- Motor **aditivo**: nuevos archivos `sentinel_engine/strategies/tk_bw.py`,
  `scripts/research/run_tk_bw_backtest.py` y sus tests. NO editar motores
  existentes, routers, ni la UI.
- Reutilizar indicadores existentes de `sentinel_engine/strategies/emasar_ref.py`
  (`ema_series`, `sar_series`, `ao_series`, `ac_series`, `momentum_series`,
  `_atr_wilder`) y `_supertrend_ref.supertrend`. NO reimplementar indicadores.
- `SAR=(0.3, 30.0)`, `EMA8/EMA5`, `MOM(14)`, `SuperTrend(14,3.0)`, `spread=0.60`,
  `commission=0`, BE `+0.60`, trailing `$5`, SL inicial `±0.60` sobre la vela,
  3 fichas de 0.01 lote (1 oz), 1 posición máx. Valores EXACTOS.
- Registry: `engine="sentinel-sim"` (CHECK constraint — NO "tk_bw"),
  `fidelity="research"`, `modelo_sim="tk_bw-v1-intrabar-m1"`. `metrics_json` NOT
  NULL (default "{}"). `familia` distinta de "supertrend" para que el overlay del
  UI dibuje EMA/SAR/SuperTrend. `params_delta` DEBE ser compatible con
  `EmasarPolicy` y llevar `ema_fast=5, ema_slow=8, sar_step=0.3, sar_max=30.0,
  st_atr_period=14, st_mult=3.0` para que el overlay renderice los valores exactos.
- Determinismo: mismo lake + mismos params ⇒ mismo trade list (sin wall-clock en
  la lógica de simulación; `fecha_corrida` puede ser wall-clock).
- Windows 10/11: pathlib, utf-8 explícito, sin APIs OS-version.
- Cuentas: el backtest NO abre órdenes; no toca MT5. `guard_cuenta` no aplica.

---

## Task 1 — Motor `tk_bw.py` (puro) + tests TDD

**Archivos (exclusivos):** `sentinel_engine/strategies/tk_bw.py`,
`tests/strategies/test_tk_bw.py`.

**Qué construir:** un motor puro, sin I/O ni MT5, que consume una secuencia de
"pasos" de evaluación y emite una lista de trades por ficha. Diseño desacoplado de
datos para TDD:

- Estructura `step`: `{"ts": int(epoch_s), "closed": list[bar], "forming": bar|None,
  "price": float, "is_close": bool}` donde `bar={"t","open","high","low","close"}`
  (BID). `closed` = velas nativas ya cerradas (crecientes en t); `forming` = vela
  nativa en formación (su `close` == `price`); `is_close=True` cuando este paso
  finaliza la vela nativa (⇒ en el próximo paso `forming` pasa a `closed`).
- Firma sugerida:
  `def tk_bw_run(steps, *, spread=0.60, commission=0.0, ema_fast=5, ema_slow=8,
   sar_step=0.3, sar_max=30.0, mom_period=14, st_period=14, st_mult=3.0,
   be_trigger=0.60, trail_usd=5.0, init_sl_offset=0.60, allow_long=True,
   allow_short=True) -> list[dict]`.
- Cada trade emitido: `{"ts_in","ts_out","px_in","px_out","side"("LONG"|"SHORT"),
  "ficha"("F1"|"F2"|"F3"),"volume":0.01,"sl","exit_reason","pnl","mae","mfe"}`.
  `ts_in`/`ts_out` epoch_s. `exit_reason ∈
  {"TP1","TP2","TP3","SL_INIT","SL_BE","SL_TRAIL"}`. `mae`/`mfe` en USD por ficha.
- Indicadores: en cada paso construir `series = closed(+forming)` OHLC y llamar a
  las funciones de `emasar_ref`/`_supertrend_ref` (import directo). "actual" = último
  índice; "previo" = penúltimo. Implementar inline sólo el helper "última vela
  bajista/alcista anterior" (buscar hacia atrás en `closed`).
- Aplicar EXACTAMENTE la convención de spread/fills y las reglas de entrada/salida
  de este documento (secciones arriba). SL-first en colisiones. Ratchet BE/trail.
  Una posición máx; sin re-entrada misma vela; F2/F3 sólo si `is_close`.

**Tests (MÍNIMOS, mecánicos — directiva del trader "minimizar tests, avanzar
rápido"):** NO perseguir un fixture "natural" de 5 condiciones (es difícil de
construir y ya costó dos intentos fallidos); la CORRECCIÓN DE LA ENTRADA se valida
EMPÍRICAMENTE en datos reales vía el runner + Trade View (el trader lo revisa). Los
unit tests cubren SÓLO las partes mecánicas, con fixtures simples (incluida la
opción de inyectar una posición YA abierta para probar salidas/stop sin tener que
disparar una entrada natural):
- smoke: importa, corre sobre una serie trivial sin error, devuelve trades bien
  formados (todas las claves del dict, tipos correctos).
- spread exacto: LARGO paga spread en la entrada, CORTO en la salida; commission 0;
  pnl = Δprecio × 1oz con el signo correcto.
- stop: SL inicial y stop-out; BE se fija a la apertura al ±0.60 y el trailing
  **nunca afloja bajo BE**; trailing $5 ratchet monótono.
- estructura: F2/F3 sólo disparan cuando `is_close`; una sola posición; no
  re-entrada en la misma vela; forma del trade dict; determinismo (misma entrada ⇒
  misma salida).
Si además logras UN test de entrada LARGO con la lectura corregida (pendientes sobre
velas cerradas), bienvenido pero OPCIONAL — construir el fixture así: ~40 velas
NATIVAS cerradas en rampa alcista ACELERADA (para que EMA5/EMA8/AO/AC/MOM salgan
todas crecientes y SAR bajo EMA8; verificar con UN chequeo numérico, NO un loop de
búsqueda), inyectar una vela cerrada bajista cerca del final (su máx = nivel de
ruptura), y una vela en formación alcista cuyo `price` quede entre ese máx y la EMA8
del último cierre. Si un slope sale marginal, subir la aceleración un paso; máximo
2-3 intentos, luego seguir.

**Report contract:** escribir informe en el path que te indique el dispatch;
devolver status (DONE/…); commits; resumen 1 línea de tests (N/N passing, comando);
concerns.

---

## Task 2 — Runner `run_tk_bw_backtest.py` + registro + tests (depende de Task 1)

**Archivos (exclusivos):** `scripts/research/run_tk_bw_backtest.py`,
`tests/scripts/test_run_tk_bw_backtest.py`.

**Qué construir:** un CLI que, para cada TF ∈ {M15, M5, M2}:
1. Carga velas M1 y nativas del lake con `load_tf_frame(lake_root,"XAUUSD",tf)` y
   `load_tf_frame(lake_root,"XAUUSD","M1")` (o `sentinel_engine/service/bars.py`).
   Ventana: `desde = 2026-07-20T00:00` menos lookback de warmup (≥1 día), `hasta`
   = último bar disponible (o `--hasta`). VERIFICAR y reportar la cobertura real
   del lake (primer/último bar por TF) — si el lake está viejo, avisar.
2. Construye la secuencia de `steps` alineando M1 dentro de cada vela nativa
   (agrupar M1 por período nativo; `forming` = agregado de los M1 vistos;
   `is_close` en el último M1 del período; al cerrar, la vela nativa pasa a
   `closed`). Las velas nativas cerradas para indicadores deben cuadrar con las del
   parquet nativo (usar el parquet nativo como fuente de `closed`, y M1 sólo para
   el `forming`/`price` intra-vela).
3. Corre `tk_bw_run(steps, ...)` con los params EXACTOS (constants arriba) para
   ambos lados (allow_long y allow_short).
4. Filtra trades con `ts_in ∈ [desde, hasta]` (descarta los del lookback de
   warmup).
5. Calcula métricas de run (net, pf, wr, payoff, maxdd; net = suma de pnl; equity
   acumulada por ts_out) — puedes reutilizar el patrón de `sentinel_engine/sim/
   lite.py` (líneas ~171-206) o de `scripts/report/gen_variant_batch1.py`.
6. Registra en `ResearchRegistry(Path("data/research.db"))`:
   - `upsert_strategy(name, familia, platform="python-sim")` con `familia`≠
     "supertrend" (p.ej. `familia="TK"`, `name="tk_bw"`).
   - `upsert_variant(strategy_id, variant_id, params_delta, tf, "XAUUSD",
     modo_salida)` — `variant_id` legible por TF (p.ej. `TK_XAUUSD_BW_M15`).
     `params_delta` = dict EmasarPolicy-completo con overrides `ema_fast=5,
     ema_slow=8, sar_step=0.3, sar_max=30.0, st_atr_period=14, st_mult=3.0,
     mom_period=14` (LEER `sentinel_engine/strategies/emasar.py` `EmasarPolicy`
     para las claves requeridas y completar defaults, de modo que
     `EmasarPolicy(params_delta).params` no falle y el overlay `/api/runs/{id}/
     indicators` lea EMA5/EMA8/SAR(0.3,30)/ST(14,3) correctos).
   - `insert_run(run_dict)` con `run_id=f"sim-...{tf}"`, `variant_id`,
     `engine="sentinel-sim"`, `fidelity="research"`,
     `modelo_sim="tk_bw-v1-intrabar-m1"`, `status="done"`, métricas,
     `periodo_desde/hasta`, `metrics_json` (JSON con params + engine="tk_bw" +
     spread/commission + cobertura + supuestos), `source_file`.
   - `insert_trades(run_id, trades)` — cada trade con `trade_id` único,
     `origin`=None, `exit_reason_source="sentinel-sim"`, `ficha` F1/F2/F3, `side`
     "LONG"/"SHORT".
7. `--dry-run` (default): corre y reporta sin escribir en la db. `--write` para
   persistir. Idempotencia: registry es ADITIVO — usar run_ids estables por
   corrida/fecha o documentar que cada corrida agrega runs nuevos.

**Tests:** integración sobre un lake sintético mínimo (o fixture pequeño) y una
`research.db` temporal (`tmp_path`): que corra, produzca ≥0 trades, registre
strategy/variant/run/trades, y que `query_runs`/`get_trades_for_run` los devuelvan;
que `engine`/`fidelity` cumplan el CHECK; que `EmasarPolicy(params_delta)` no lance;
que `--dry-run` no escriba. Determinismo del pipeline dado el fixture.

**Report contract:** igual que Task 1.

## Protocolo de ejecución (rápido — directiva del trader 2026-07-21)

- **Velocidad sin sacrificar calidad**: implementación sub-agéntica (Sonnet 5
  high, ≤2 en paralelo, archivos disjuntos), pero SE MINIMIZA la ceremonia:
  NO hay subagente task-reviewer por tarea ni review amplio final; el controlador
  hace un self-check ligero de cada diff. Tests **enfocados de alto valor**
  solamente (las conductas núcleo), sin cobertura exhaustiva de edge cases.
- **Foco de calidad = fidelidad de graficado**: lo crítico es que en "Trade View"
  las posiciones queden **centradas** y las **entradas/salidas exactas** bien
  ploteadas (ts correctos, side LONG/SHORT, marcadores por ficha). El controlador
  VERIFICA esto en el browser (CDP headless) antes de avisar.
- **Una sola notificación**: el controlador avisa al trader UNA vez — cuando el
  backtest está corrido y los trades REALES se ven correctos en Trade View
  (formato/centrado/entradas-salidas verificados). Hasta entonces, autónomo.

## Verificación end-to-end (la hace el controlador, no subagente)

1. Correr `python -m scripts.research.run_tk_bw_backtest --write` (o el invocador
   equivalente) sobre el lake real → 3 runs (M15/M5/M2) en `data/research.db`.
   Reportar net/pf/wr/#trades por TF y la cobertura real de la ventana.
2. Levantar/usar el service y abrir la UI: confirmar que los 3 runs aparecen en
   **"runs"** y que en **"Trade View"** (REVIEW) cada run muestra velas + marcadores
   de trades (por ficha) + curva de equity + overlays EMA5/EMA8/SAR(0.3/30)/
   SuperTrend/AO/AC/MOM. (Verificación CDP headless si aplica.)
3. Reportar al trader los números y capturas; anotar los supuestos abiertos
   (short-TP2 simetría, Momentum 14, SuperTrend 14/3) para su confirmación.
</content>
</invoke>
