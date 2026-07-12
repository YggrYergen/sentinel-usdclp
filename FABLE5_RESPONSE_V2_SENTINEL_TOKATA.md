# FABLE 5 — Respuesta de diseño, segunda pasada (SENTINEL V2 + TOKATA)

> **Fecha:** 2026-07-09 · **Modelo:** Fable 5 (xhigh) · **Inputs:** `BRIEFING_SENTINEL_REVAMP_V2.md` + `docs/REQUISITOS_WEBAPP_ANALISIS_ESTRATEGIAS.md` (TOKATA, R1–R36) + decisiones del usuario de esta sesión.
> **Decisiones del usuario que gobiernan esta respuesta:** (1) **UNA sola web app** — todo lo nuevo vive como secciones del navbar vertical existente, en el área de contenido a su derecha (donde hoy viven las señales de USDCLP/NQ100/XAUUSD); (2) la dualidad de motores de backtest debe resolverse **profesionalmente y en profundidad**; (3) los sweeps multi-parámetro deben poder **correr y registrar el comportamiento del panel de señales** dentro del backtest; (4) UI **dark neon cyberpunk minimalista**, intuitiva y **muy liviana** (laptops de oficina 4–8 GB RAM, Win 10/11); (5) ASAP con calidad completa.
> **Reglas heredadas intactas:** paridad golden byte-exacta, determinismo, cuentas reales READ-ONLY jamás órdenes, ejecución sólo demo, OSS-only, Win 10+11, Sonnet 5 implementa / Opus-Fable sólo diseña-verifica.

---

## §0. Resumen ejecutivo y tabla de decisiones

El sistema construido (`sentinel_engine/`: core determinista + lake + fast_replay + walk-forward + registry + servicio FastAPI/WS + UI vanilla) **es la base correcta y se reusa entero**. Lo que falta no es reemplazo sino **cuatro extensiones estructurales**: (1) un **contrato de estrategia** y un **simulador broker Tier-1 en Python** que unifica la investigación masiva, con el **MT5 Strategy Tester como Tier-2 de validación** — esto resuelve la dualidad de motores; (2) un **genoma v2 (ScoringGraph)** que convierte el scorer técnico/macro en un grafo de features componible y buscable — esto resuelve el hallazgo de bajo apalancamiento de G1; (3) un **esquema canónico de resultados y procedencia** (registry v2) que absorbe el ledger TOKATA sin rehacerlo y etiqueta cada posición humano/estrategia/IA end-to-end; (4) una **capa de charts profesional vendorizada** (lightweight-charts) + secciones de UI nuevas bajo el navbar existente, con presupuesto de performance explícito.

| ID | Decisión | Por qué (resumen; detalle en §ref) |
|---|---|---|
| D-V2-1 | Una sola web app; secciones nuevas en el navbar vertical existente, lazy-loaded | Decisión del usuario; el servicio FastAPI+WS ya soporta multi-sección; evita duplicar feed/estado (§6) |
| D-V2-2 | **Dos tiers de ejecución, un solo contrato de resultados**: Tier-1 = simulador Python propio (investigación masiva), Tier-2 = MT5 Strategy Tester (validación screening/real-tick). NT8 = sólo ingesta | Resuelve la incompatibilidad semántica sin sacrificar ni volumen ni fidelidad (§2) |
| D-V2-3 | `StrategyPolicy` protocol + **fidelity audit** como run-type que habilita "sweepable" | Una estrategia sólo se barre masivamente en Tier-1 cuando su port Python pasa auditoría vs MT5 (§2.4) |
| D-V2-4 | Genoma v2 = **ScoringGraph** (registry de features + pesos + reglas), con `graph_v1` como ancla de paridad bit-exacta | Repite el patrón P1 (default = comportamiento legacy byte-idéntico); habilita búsqueda estructural (§3) |
| D-V2-5 | Macro v2 = **forecasters de beta-rezagada por referencia** + **gate de coherencia multi-escala con histéresis**; el voto de concordancia actual queda como variante baseline | Familia interpretable, punto-en-el-tiempo por construcción, barata; el gate implementa la selección adaptativa pedida (§3.3) |
| D-V2-6 | Descomposición multi-TF = **5 políticas nombradas** expresadas como variantes del genoma, decididas por estudio, no por opinión | El usuario pide alternativas testeables, no una elección a priori (§3.4) |
| D-V2-7 | Calidad de señal por capa = **cuarta lente**: hit-rate vs triple-barrier, IC, calibración, PnL de política standalone, ΔJ por ablación | Métricas separables técnica/macro pedidas en §3.4 del brief (§3.5) |
| D-V2-8 | Charts = **TradingView lightweight-charts vendorizado** (Apache-2.0, ~45 KB, canvas) para superficies de velas; uPlot se queda para sparklines/equity | Cumple R1–R6 con el menor peso posible en 4–8 GB (§6.2) |
| D-V2-9 | Procedencia = campo `origin` + `origin_id` en el modelo de datos de trade/posición, poblado en vivo por **rangos de magic-number** MT5 | Estándar MT5, cero ambigüedad, segmentable en toda la app (§4.3) |
| D-V2-10 | Ejecución demo = **un único módulo gateway** con allowlist de cuentas + verificación `trade_mode==DEMO` + guardarraíles pre-envío + audit log append-only + kill-switch + test CI "ningún otro módulo importa funciones de orden" | Frontera dura exigida; enforcement técnico, no convención (§4.4) |
| D-V2-11 | **Pre-registro TOKATA adoptado globalmente** (también para estudios SENTINEL), fusionado con walk-forward/purga/DSR en una sola gobernanza de validación | Toma lo mejor de ambos mundos: disciplina anti-snooping + estadística anti-overfitting (§5) |
| D-V2-12 | **Estudio de línea-base PRIMERO**: medir el desempeño actual (J + métricas por capa, por asset) antes de optimizar nada | El brief admite que "tampoco se ha medido hasta ahora"; sin baseline no hay claims de mejora (§7, S0) |
| D-V2-13 | Registry v2 = SQLite (WAL) + sidecars Parquet; **job-queue de un solo escritor** en el servicio | Consistente con lo construido; evita corrupción por concurrencia (§4.1) |
| D-V2-14 | **Modo signal-history** en corridas Tier-1: persistir por barra el estado del panel de señales (scores por capa, dirección, semáforo) en Parquet compacto | Requisito explícito del usuario: el panel es optimizable y scrubbable por backtest (§2.5) |
| D-V2-15 | Estilo cyberpunk **sólo vía CSS tokens** (paleta + glow acotado); sin frameworks; presupuesto de perf explícito | "Muy muy liviano" es un requisito duro, el estilo no puede costar runtime (§6.3) |

---

## §1. Diagnóstico: lo construido vs el alcance expandido

### 1.1 Encaja tal cual (reusar sin tocar)
- `lake/` + `feed_historical` (gate de leakage), `trades/` ingestas, `walkforward`, `labels` (triple-barrier + purge), `objective`, `search` (staged TPE), `selection`, `fast_replay`+`FastReplayCache`, `study`/`run_fleet` (paralelismo 6//K), servicio FastAPI + WS broadcaster, launcher embebido, gates golden/opt.
- La arquitectura Snapshot/InstrumentConfig/config_hash es exactamente el sustrato que los tres objetivos necesitan.

### 1.2 Se extiende
- `registry.py` → **registry v2** (esquema canónico §4.1: engine/fidelity/origin/preregistro; absorbe ledger TOKATA).
- `report.py` → añade lentes por capa y curvas equity/DD (R29).
- `levers.py` → deja de ser la fuente del espacio de búsqueda; el espacio se **genera desde el ScoringGraph** (§3.2). G1–G7 sobreviven como "presets" del espacio para el genoma v1.
- `service/app.py` → endpoints nuevos (§6.1); los stubs 501 gateados (replay/variant/study/fleet/calendar) se implementan sobre esta base — ya están en el lugar correcto.
- `ai_context.py` → secciones nuevas (posiciones con procedencia, estado de estrategias, calendario); sigue siendo el ÚNICO productor de contexto IA.

### 1.3 Se reemplaza (con ancla de paridad, patrón P1)
- El scorer técnico de composite fijo (5 sub-scores hardcodeados) → **evaluador de ScoringGraph**. El grafo `graph_v1.yaml` reproduce el comportamiento actual **byte-exacto** (nuevo caso golden); el path legacy convive hasta el cutover, commit revertible aislado, igual que P1.6.

### 1.4 Nuevo (no existe hoy)
- `sentinel_engine/sim/` — broker-sim Tier-1 (§2.3). `sentinel_engine/strategies/` — contrato + ports (§4.2). `sentinel_engine/exec/` — gateway demo-only (§4.4). `sentinel_engine/ingest_tokata/` — importadores de artefactos (§4.5). `regime/` labeler (P6, se materializa en S3). Charts pro + secciones UI (§6). Adaptador MT5-tester (§2.4). Calendario económico (§8, con flag de fuente).

### 1.5 Tensiones diagnosticadas y su resolución
1. **Bajo apalancamiento G1** (evidencia real: 1/25 configs movió J; técnico pesa 0.5 y macro domina el voto 3v2): no es un bug, es la arquitectura de scoring. La respuesta correcta NO es más trials sobre los mismos levers sino **búsqueda estructural** (qué features entran, cómo votan, cómo se agrega la dirección, qué TF decide qué). El ScoringGraph pone exactamente eso en el espacio de búsqueda (§3). Los levers de indicadores siguen disponibles (útiles, baratos de mantener), pero dejan de ser la apuesta principal.
2. **Dos motores de backtest con semántica incompatible**: resuelto con el modelo de dos tiers + contrato único + auditoría de fidelidad (§2). Ni "todo al tester MT5" (lento, no barre miles de variantes, no mide señal por capa) ni "todo a Python" (pierde real-tick, reglas de bróker, fidelidad de ejecución) son aceptables; el funnel usa cada uno donde es fuerte.
3. **Charts profesionales vs "nada puede ser más lento"**: lightweight-charts es canvas puro, ~45 KB gzip, sin DOM por vela; con fetch por ventana + LOD (§6.2) el costo es acotado y sólo se paga en las secciones que lo usan (lazy-load).
4. **Ejecución vs read-only**: la frontera se vuelve **técnica** (gateway único, allowlist, verificación de `trade_mode`, test CI de imports) en vez de disciplina (§4.4).
5. **Muestras finas en USDCLP**: pooling jerárquico de priors (lo aprendido en XAUUSD/NQ100 informa priors, no parámetros) + n_min gates ya existentes. XAUUSD primero, como pide el brief.
6. **SQLite bajo escritores múltiples** (fleet + servicio + importadores): WAL + un solo proceso escritor (job-queue en el servicio); los workers de estudio escriben a staging Parquet y el escritor consolida.
7. **Fragilidad de la automatización del tester MT5**: NO se reescribe el pipeline TOKATA (batch_runner/gen_variant funcionan y tienen historial); se **envuelve** como adaptador invocable por el servicio (§2.4). Riesgo contenido: si el wrapper falla, el pipeline manual sigue operativo.

---

## §2. La resolución de la dualidad de motores (centro de esta respuesta)

### 2.1 Principio
**Un contrato, dos ejecutores, fidelidad como dimensión de primera clase.** Toda corrida —venga del replay de señales SENTINEL, del simulador Tier-1 o del tester MT5— produce una fila del MISMO esquema de resultados (§4.1) con `engine ∈ {sentinel-replay, sentinel-sim, mt5-tester, nt8-manual}` y `fidelity ∈ {research, screening, real-tick, forward, live-demo}`. La UI, el ranking, la comparación y la IA operan sobre ese esquema único; **la fidelidad siempre es visible junto al número** (R25/R31). Nunca se comparan silenciosamente corridas de fidelidad distinta: la UI las separa o marca el cruce.

### 2.2 Los dos tiers y el funnel

```
 pre-registro (hipótesis, umbral, descarte)                    [gobernanza §5]
      │
      ▼
 TIER-1 · sentinel-sim (Python, lake, paralelo 6//K)           [volumen]
   - miles de variantes: estrategias portadas × levers × TF × ventanas
   - walk-forward anclado + purga + embargo + DSR + plateau
   - señales SENTINEL opcionalmente grabadas por barra (§2.5)
      │  top-K sobrevivientes de meseta
      ▼
 TIER-2 · mt5-tester (adaptador sobre batch_runner TOKATA)     [fidelidad]
   - screening Model=1 → validación Model=4 (real tick)
   - reglas de bróker reales, fills reales, .htm + signals.csv
      │  ganadores validados
      ▼
 FORWARD demo (perfil tipo FORWARD39, cuenta demo, §4.4)       [tiempo real]
      │  criterio explícito de graduación (R33)
      ▼
 GRADUADA → monitoreo live-demo en UI, procedencia=strategy
```

**Por qué así:** el Tier-1 es donde el volumen es posible (fast_replay ya demostró 6.1×, la flota ya reparte 6 cores; un sim de barras corre 10³–10⁴ variantes/noche). El Tier-2 es donde la verdad de ejecución vive (ticks reales, stops del bróker, swaps). El funnel garantiza que **ningún número de investigación se publicite como validado** y que **ningún costo de real-tick se gaste en variantes basura**. Es la misma filosofía del walk-forward de TOKATA (screening→validación→forward) formalizada y automatizada.

### 2.3 Tier-1: `sentinel_engine/sim/` (nuevo)
Componentes:
- **`policy.py` — `StrategyPolicy` protocol**: `on_bar(ctx: BarContext) -> list[OrderIntent]`. `BarContext` expone: barras causales por TF (`ctx.bars(tf, n)`, servidas por el mismo path point-in-time del lake), posición abierta, equity, y —clave— `ctx.snapshot` (el Snapshot SENTINEL del bar, si el run lo habilita). Puro, determinista, sin I/O.
- **`broker_sim.py`**: motor de fills a nivel de barra. Especificación:
  - Fill de mercado al open de la barra siguiente ± slippage (modelo: constante + fracción de spread; spread por instrumento constante o tabla por hora-del-día muestreada de ticks reales — `ASSUMPTION: empezar constante, tabla en S2`).
  - Comisión/swap por instrumento desde config (valores de CUENTAS/bróker).
  - SL/TP intrabar: si ambos son tocables en la misma barra, **regla conservadora SL-first** (peor caso). Esta ambigüedad es exactamente la que el Tier-2 real-tick resuelve; el sim la declara en el reporte (`intrabar_ambiguous_count`).
  - **Validación de bróker (R28)**: distancia mínima de stop, tamaño mínimo/step de lote, freeze level; una orden inválida se **rechaza y registra** (el reporte muestra "config no ejecutable en condiciones reales").
  - Sesiones/horarios y buffer de noticias como filtros declarativos.
- **`runner.py`**: reusa `study.py`/`run_fleet.py` (mismo presupuesto de cores, misma semilla determinista, mismo formato de progreso). Un sweep es: pre-registro → grid/TPE sobre el espacio declarado → N corridas sim → filas en registry v2 + artefactos Parquet (trades, equity curve, signal-history opcional).
- **Métricas**: las del ledger TOKATA como mínimo (net, PF, WR, payoff, maxDD, sharpe, trades) + MAE/MFE por trade + las lentes por capa (§3.5) cuando `record_snapshots=on`.

### 2.4 Tier-2: adaptador MT5 + auditoría de fidelidad
- **`mt5_adapter/`** (dentro de FOREX, invocando el tooling TOKATA in-situ; `ASSUMPTION`: `D:/WebDev/TOKATA/mt5/scripts` permanece en su ruta, referenciada por config): job del servicio que (1) toma un variant_id + ventana + modelo, (2) genera el `.ini` vía `gen_variant.py`, (3) encola en `batch_runner.py` (SECUENCIAL, como hoy — el tester no se paraleliza bien y no lo intentaremos), (4) parsea el `.htm`/`_signals.csv` y escribe la fila canónica. La compilación de un `.mq5` modificado sigue siendo **paso manual asistido** (MetaEditor CLI existe pero es frágil; la UI muestra "requiere compilación" cuando el delta toca código y no sólo inputs — la gran mayoría de sweeps toca sólo inputs y no requiere recompilar).
- **`fidelity_audit` (run-type nuevo, decisión D-V2-3)**: para cada estrategia portada a Python, correr la MISMA variante + ventana en ambos tiers y comparar trade-a-trade (entradas idénticas ± tolerancia de 1 barra; PnL total ± tolerancia %; conteo de trades exacto o justificado). TOKATA ya hace esto a mano (`AUDITORIA_FIDELIDAD_*`, `emasar_ref.py` con suite de paridad verde) — se formaliza como artefacto de primera clase con umbrales configurables. **Sólo una estrategia con auditoría verde adquiere el flag `sweepable=true`**; sin él, la UI permite correrla en Tier-2 pero no barrerla masivamente en Tier-1. Esto es lo que hace los resultados "repeatable and usable" que el usuario exige.
- **NT8**: sin API de automatización sana; sus estrategias (.cs) se **ingieren como registro histórico** y sus lógicas se portan a Python desde las fuentes MQL5 equivalentes (Sapitos v3 y Pedro v1 existen en ambas plataformas — se porta desde MQL5, se audita contra MT5).

### 2.5 El panel de señales dentro del backtest (requisito nuevo del usuario)
- `record_snapshots=on` en cualquier corrida Tier-1 activa la persistencia por barra de: score compuesto, score técnico, score macro, dirección, semáforo, votos por sub-score/feature, confidencias macro por referencia, y (genoma v2) el estado del gate de coherencia. Formato: Parquet columnar compacto (float32/int8 cuantizados donde no rompe determinismo del REGISTRO — el cálculo interno nunca se cuantiza), un archivo por corrida, `signal_history/{run_id}.parquet`.
- Esto habilita tres cosas: (a) **scrubbing** — la sección Replay/Charts reconstruye el panel de señales en cualquier barra de cualquier backtest (R13 extendido a señales); (b) **el panel como política optimizable** — una `SignalPanelPolicy` (entrar cuando composite ≥ umbral y dirección ≠ NEUTRAL, salir por triple-barrier o reglas) es una StrategyPolicy más, barrible como cualquier estrategia — así "optimizar el panel" y "optimizar estrategias" usan el mismo camino; (c) **las lentes por capa** (§3.5) se computan de este mismo artefacto.
- Costo: ~10–20 columnas × barras M1 de la ventana; para sweeps grandes, grabar signal-history sólo en top-K + baseline (config del sweep), no en las 10³ corridas descartadas.

---

## §3. Objetivo A — Framework combinatorio de señal (genoma v2)

### 3.1 FeatureSpec registry (extensibilidad de primer nivel)
```python
class Feature(Protocol):
    feature_id: str                    # estable, versionado ("supertrend@1")
    params_schema: dict                # nombre → (tipo, rango, default, prior)
    def compute(self, bars: pd.DataFrame, params) -> pd.DataFrame
    # PURA y CAUSAL: sólo mira bars[:t]; añade columnas namespaced
```
- Cada feature declara sus columnas de salida y un **test de invarianza punto-en-el-tiempo** automático: `compute(bars[:t])[t] == compute(bars_full)[t]` para una muestra de t — el harness lo corre para TODO feature registrado (gate anti-leakage estructural, no por convención).
- **Catálogo inicial** (cubre SENTINEL + TOKATA R6): `ema_stack` (los 4 EMAs + cruce + tendencia — el actual), `rsi`, `macd`, `bbands`, `price_action` (cuerpo/rango + engulfing), `supertrend` (ATR×mult), `parabolic_sar` (step/max), `awesome_osc`, `accel_osc`, `momentum`, `adx`, `choppiness`, `orb` (opening-range), `sr_zones` (distancia a Camarilla + swings — la feature "zonas de compra/venta"), `session_time` (hora/sesión), `atr_vol_regime`.
- **Sub-score**: cada feature usada en un grafo lleva `(params, weight, vote_rule)` donde `vote_rule` mapea columnas→(score 0–100, voto −1/0/+1). Las reglas actuales de `technical.py` se transcriben 1:1 para el ancla de paridad.

### 3.2 ScoringGraph (el genoma v2)
YAML versionado dentro del `InstrumentConfig` (o referenciado por él), cubierto por `config_hash`:
```yaml
graph_version: 2
technical:
  features:
    - {id: ema_stack@1, params: {...}, weight: 0.30, vote_weight: 1}
    - {id: supertrend@1, params: {atr: 10, mult: 3.0}, weight: 0.15, vote_weight: 1}
  aggregation: weighted_mean          # opciones: weighted_mean | median | trimmed
  direction_rule: {type: net_votes, threshold: 2}
macro:
  estimator: lagged_beta@1            # o concordance@1 (baseline = actual)
  references: [dxy, silver, vix, ...] # con pesos base
  comovement_gate: {on: 0.55, off: 0.35, dwell_bars: 10}   # §3.3
composite:
  weights: {technical: 0.5, macro: 0.5}
  direction_vote: {technical: 2, macro: 3}
  thresholds: {alert: 65, strong: 75}
tf_policy: {type: blend, weights: {M15: .10, M5: .20, M2: .35, M1: .35}}  # §3.4
```
- **Paridad**: `graph_v1.yaml` = transcripción exacta del scorer actual; test golden nuevo exige `evaluate(graph_v1) == legacy` byte-exacto sobre los 6 casos. El path legacy no se borra hasta un cutover aislado y revertible (patrón P1.6, misma regla pinned).
- **El espacio de búsqueda se GENERA del grafo**: cada feature on/off (categórico), sus params (rangos del schema), pesos (simplex Dirichlet), reglas de dirección (umbral de votos), gate macro, tf_policy. `levers.py` se convierte en un generador de `ParamSpec`s desde el grafo — G1–G7 quedan como presets del genoma v1.
- **Control de dimensionalidad (respuesta a la pregunta explícita del brief)**: (i) **screening barato por feature**: IC standalone (Spearman score-feature vs retorno forward k-bars) por walk-forward — se computa vectorizado sobre el lake sin sim completo; features con IC ~0 estable no entran al combinatorio; (ii) **sparsity cap**: máx K features activas por grafo (K∈{4..7} como lever categórico); (iii) **búsqueda staged** (ya construida): estructura (subset+reglas) → params → pesos, cada stage con presupuesto ≥25×dims trials; (iv) plateau + DSR + holdout single-touch ya existentes como gates de selección. Con esto el combinatorio es tratable sin explosión ni auto-engaño.

### 3.3 Capa macro v2
**Estimador recomendado — beta rezagada por referencia (`lagged_beta@1`):** para cada referencia r y target a, regresión EWMA rolling del retorno forward del target sobre retornos pasados de r en lags {0..L} (por TF): `forecast_r(t) = Σ_l β_l(t)·ret_r(t−l)`; dirección = signo, magnitud = |forecast|/σ_target (en unidades de vol), confianza = IC out-of-sample rolling de ese estimador. Punto-en-el-tiempo por construcción (todo EWMA causal), barato (vectorizable en fast_replay), interpretable (β por lag y TF visible en la UI). **Por qué esta familia:** es el paso mínimo desde el voto de concordancia actual hacia "dónde y cuánto", sin saltar a ML opaco con muestras chicas.
- Alternativas evaluadas: (a) voto de concordancia actual — se queda como **baseline obligatorio** de todo estudio macro; (b) beta con filtro de Kalman (time-varying más suave) — fase 2, si la beta EWMA muestra inestabilidad; (c) gradient boosting por referencia — **descartado ahora**: riesgo de overfit con este tamaño de muestra + opacidad + costo de validación; (d) z-score de spread cointegrado para pares naturales (XAU–XAG, NQ–SP) — **incluir como feature adicional**, es barato y ortogonal.
- **Gate de co-movimiento multi-escala (selección adaptativa en vivo):** coherencia `C_r(t) = Σ_tf w_tf · [|ewma_corr_tf| × concordancia_tf]` sobre TF ∈ {M1, M5, M15}; activación con **histéresis** (on > 0.55, off < 0.35, `ASSUMPTION`: umbrales a calibrar en estudio) + dwell mínimo (anti-flapping); peso efectivo = peso_base × smoothstep(C_r). Se computa de los mismos EWMAs que ya existen (costo marginal ~0) y entra al Snapshot **primero como metadata aditiva** (paridad intacta), luego como cambio de scoring vía variante del genoma (golden se actualiza deliberadamente, nunca en silencio).
- **Nuevos diseñables por nosotros (pedidos explícitamente):** matriz lead-lag completa (¿quién lidera a quién y con cuánto lag, por sesión?), factor PCA de la canasta DXY-like, spillover de vol realizada (vol de r predice vol de a), alineación de retorno relativo a sesión (Asia/Londres/NY). Todos expresables como Features del registry → testeables con la misma maquinaria. Prioridad: lead-lag y cointegración (mayor probabilidad de edge documentada en la literatura para metales/índices).

### 3.4 Descomposición multi-TF — las opciones a estudiar (D-V2-6)
Cinco políticas nombradas, todas expresables como `tf_policy` del genoma (⇒ comparables en el mismo estudio, forkeable cada una):
1. **`blend`** (actual): promedio ponderado de scores por TF. Baseline.
2. **`role_based`**: dirección en M15, timing/gatillo en M1–M2 (sólo se entra cuando el gatillo fino confirma la dirección gruesa), vol/régimen en M15+, co-movimiento macro en M5. La hipótesis favorita de la literatura de scalping; mi recomendación como primer challenger.
3. **`cascade_veto`**: el TF superior fija la dirección permitida; los inferiores generan entradas; conflicto ⇒ veto (no NEUTRAL diluido, veto duro).
4. **`dominant_switch`**: el labeler de régimen (P6) elige qué TF lidera según el régimen del día (trending ⇒ M15 manda; choppy ⇒ nadie, umbral sube).
5. **`ensemble_wf`**: políticas por-TF independientes con pesos actualizados por desempeño walk-forward (meta-pesos re-estimados por fold, nunca dentro del fold).
Implicación para validación: las políticas 4–5 consumen el labeler de régimen ⇒ P6 se adelanta (S3). El estudio comparativo usa las mismas ventanas/folds para las 5 (comparación pareada, no absoluta).

### 3.5 Métricas de calidad de señal por capa (la cuarta lente)
Computadas desde `signal_history` + labels triple-barrier, por capa ∈ {técnica sola, macro sola, compuesto}:
1. **Hit-rate direccional** vs label triple-barrier a horizontes {15m, 1h, 4h}.
2. **IC** (Spearman de score vs retorno forward k-bars) con IC decay por k.
3. **Calibración**: deciles de score vs win-rate realizado (la curva debe ser monótona; su pendiente ES la utilidad del score).
4. **PnL de política standalone**: "entrar cuando esta capa sola cruza umbral" → J de esa política.
5. **ΔJ por ablación**: J(compuesto) − J(compuesto sin la capa, pesos renormalizados) — cuánto aporta de verdad.
Estas cinco van al reporte estándar de todo estudio y a la sección Study de la UI. Se reconcilian con las 3 capas de ground-truth originales así: labels TB alimentan (1); la reference-policy PnL es (4); el cross-check de trades reales sigue siendo la lente de realismo; esta cuarta lente mide **endorsement por capa**, que ninguna de las tres cubría.

---

## §4. Objetivo C — Estrategias de primera clase, TOKATA, procedencia, ejecución

### 4.1 Registry v2 — esquema canónico (SQLite WAL + Parquet)
Tablas (columnas clave; supersets del ledger TOKATA — R11/R19/R21/R23/R25):
- **`strategy`**: id, nombre, plataforma_impls (json: {mq5, cs, py}), indicadores (feature_ids), param_schema (json con reglas de validez de bróker), defaults, sweepable(bool), graduated(bool), notas.
- **`variant`**: variant_id (formato TOKATA: `EMS_XAU_V1_M5_c2_sar3m3`), strategy_id, params_delta (json), tf, instrumento, modo_salida.
- **`param_set`**: params_hash, params_efectivos (json completo, R23).
- **`run`**: run_id, variant_id, params_hash, **engine**, **fidelity**, ventana desde/hasta, modelo_sim, status, métricas (trades, net, pf, wr, payoff, maxdd, sharpe, mae_avg, mfe_avg, + json extensible), preregistro_id, artefactos (paths: report .htm/.md, trades.parquet, equity.parquet, signal_history.parquet), fecha, seed, config_hash.
- **`trade`**: trade_id, run_id (null ⇒ vivo), **origin ∈ {human, strategy, ai}**, origin_id, session_id, ts_in/out, px_in/out, lado, volumen, sl/tp (+ historia de modificaciones), **exit_reason** (consolidado, R27), pnl, mae, mfe, snapshot_at_entry_ref, decision_trace_ref (IA).
- **`preregistration`**: id, variant_id, hipótesis, mecanismo, métrica primaria, umbral de éxito, condición de descarte, fecha, autor (R35).
- **`forward_session`**: id, strategy_id/variant_id, cuenta (demo), perfil, inicio/fin, estado.
- **`audit_log`**: append-only; toda orden (intención→veredicto guardarraíl→resultado), toda graduación, todo override de IA.
- **`calendar_event`**: ts, país, impacto, título, fuente.
Los CSV `;` de TOKATA (`mt5_ledger`, `preregistro`) se importan 1:1 a `run`/`preregistration` con `engine=mt5-tester` y su `report_path` preservado (R19–R21: nada se rehace, todo se referencia).

### 4.2 Contrato de estrategia y ports
- `StrategySpec` + `StrategyPolicy` (§2.3). Orden de porteo: **EMASAR primero** (referencia Python con paridad verde YA existe — el activo más barato), luego SuperTrend_v1 y STAC_v1 (lógica simple de indicadores ya en el catálogo de features), luego Sapitos v3 / Pedro v1 (más complejos: ORB/ADX/Choppiness/engulfing — sus features también sirven al genoma v2, doble uso). TrailGuard/SapTrail se modelan como **política de salida componible** (`ExitPolicy` separada de la de entrada — así el sweep "stop inicial {50,70,100,150,200} × modo de salida" de R24 es literalmente un producto cartesiano declarativo).
- **Crear variantes/estrategias desde la UI (R8/R10)**: la UI edita params (schema-driven forms) y crea variantes con delta; "implementar estrategia nueva" en v1 = combinar entry/exit policies + features existentes de forma declarativa (sin escribir código); estrategias con lógica genuinamente nueva siguen requiriendo código Python (y eso está bien — la IA Rol 2 asiste).

### 4.3 Procedencia end-to-end (D-V2-9)
- **En vivo**: poller read-only de la cuenta demo (posiciones/deals cada N s) clasifica por **rangos de magic-number**: cada estrategia graduada recibe un rango asignado (registrado en `strategy`), la IA ejecutora tiene su propio rango, y todo lo que no matchea = `human`. El magic es el mecanismo estándar MT5 y sobrevive en el historial de deals ⇒ la procedencia es reconstruible incluso retroactivamente.
- **En backtest/sim**: origin=strategy por construcción. **En IA**: cada orden lleva `decision_trace_ref` → conversación + evaluación de guardarraíles + snapshot en el momento (auditable, R36).
- La UI segmenta por origin en tabs de la sección Posiciones (§6.1) y TODO reporte/desempeño es filtrable por origin (es una columna, no una vista).

### 4.4 Gateway de ejecución demo-only (D-V2-10 — frontera dura)
`sentinel_engine/exec/gateway.py` — **el único módulo del repo autorizado a importar funciones de orden MT5** (`order_send`, etc.). Salvaguardas en capas, todas obligatorias:
1. **Allowlist de cuentas**: login+server demo explícitos en config firmada (config_hash); al iniciar, `account_info()` debe matchear la allowlist Y reportar `trade_mode == ACCOUNT_TRADE_MODE_DEMO`; si no ⇒ el gateway se niega a arrancar (no degrada, se apaga).
2. **Guardarraíles por estrategia, evaluados PRE-envío**: máx posiciones/día, tamaño máx, SL máx obligatorio, exposición total, horario/sesión, buffer de noticias (calendar), R:R mínimo. Cada regla emite veredicto individual al audit_log; un solo veto ⇒ no se envía.
3. **Kill-switch**: archivo sentinel + botón UI + endpoint; el gateway lo chequea antes de cada envío.
4. **Audit append-only** (§4.1) de intención/veredicto/resultado, con origin e ids.
5. **Test CI estructural**: un test que escanea imports de todo el repo y FALLA si cualquier módulo ≠ gateway importa funciones de orden — la regla "read-only en todas partes" deja de ser convención y pasa a ser gate.
La instalación MT5 real permanece en proceso/terminal separado, sin credenciales en este repo, jamás referenciada por el gateway.

### 4.5 Ingesta TOKATA (R19–R21)
`ingest_tokata/` con importadores idempotentes (checksum por archivo): ledger CSV, preregistro CSV, `_signals.csv` (trades por corrida → tabla `trade` con exit_reason del EA), `forward_*.csv` + `forward_daily/` (→ `forward_session` + trades), `.htm` (se parsean métricas clave; el archivo queda referenciado como evidencia, no se re-renderiza), `.md` de análisis (indexados como documentos vinculados a variantes). **Consolidación de exit_reason (R27)**: regla de precedencia señales-CSV > htm > referencia Python; los cierres por stop del bróker (ausentes del signals CSV) se recuperan del deal history/htm — el importador fusiona y marca la fuente de cada campo.

---

## §5. Gobernanza de validación unificada (TOKATA × SENTINEL)
Una sola política para TODA corrida (estudios de señal Y sweeps de estrategia):
1. **Pre-registro obligatorio** para toda corrida "que cuenta" (hipótesis, métrica primaria, umbral, condición de descarte). Corridas exploratorias se permiten pero quedan marcadas `exploratory=true` y NO son elegibles para promoción/graduación. (Disciplina TOKATA, ahora también para estudios SENTINEL.)
2. **Anti-overfitting estadístico** (SENTINEL, ahora también para sweeps de estrategia): walk-forward anclado + purga/embargo, selección por plateau (no por pico), DSR sobre el ganador, holdout single-touch.
3. **Fidelity ladder**: research → screening → real-tick → forward → graduada; ningún salto se omite; el criterio de graduación (R33) es explícito y pre-registrado (ej.: "≥ N trades forward, PF ≥ x, maxDD ≤ y, sin violaciones de guardarraíl").
4. **Evidencia (R36)**: toda fila de `run` referencia sus artefactos; la UI no muestra números sin link a evidencia.
5. **Baseline primero (D-V2-12)**: el primer estudio S0 mide el sistema ACTUAL (genoma v1 por asset: J, lentes por capa, curvas). Todo claim posterior es relativo a ese baseline versionado.

---

## §6. UI — una app, navbar vertical, cyberpunk liviano

### 6.1 Topología (decisión del usuario, D-V2-1; **corregida 2026-07-09**)
Layout de tres bandas: **tercio izquierdo (~1/3) = réplica pixel-exact del UI /v2 tal como estaba en `release` hasta el 4 de julio** (las señales/indicadores de los 3 assets), SIEMPRE visible e intacta; **navbar vertical mínimo cyberpunk al centro**, entre ambas mitades, para navegar la app; **dos tercios derechos (~2/3) = área de contenido de la sección activa** (todo lo nuevo). Verificación pixel-exact contra el worktree baseline `D:/FOREX_baseline_2026-06-11` + estado del 4 de julio en git. Secciones del navbar (las nuevas, lazy-loaded — JS de cada sección se carga al entrar, no antes):
1. **Live** (existente): panel de señales 3 assets — intacto.
2. **Charts**: velas pro (R1–R6) por instrumento, TF switch (M1/M2/M5/M10/M15, ampliable), pan/zoom/crosshair-hover con OHLC+indicadores+marcadores, overlays de features del catálogo con params efectivos, subpanes para osciladores (AO/AC/Momentum).
3. **Estrategias**: lista unificada NT8+MT5+nativas (R7), detalle con params (R9), edición/creación de variantes (R8/R10), estado sweepable/graduada, historial de resultados.
4. **Runs / Registry**: tabla-ranking navegable, ordenable, filtrable (R30) con engine/fidelity/origin visibles (R25/R31), comparación de variantes con equity/DD superpuestas (R12/R29), link a evidencia (R36).
5. **Sweeps / Studies**: pre-registro (form), definición de barridos (producto declarativo de rangos, R24), lanzamiento y progreso en vivo (reusa el progress de study/fleet), resultados con lentes por capa.
6. **Trade Review**: recorrer trade-a-trade cualquier corrida (R13) sobre el chart, con entrada/salida/motivo/PnL/MAE-MFE y —si hay signal_history— el estado del panel de señales en esa barra; TF conmutable con el trade anclado por timestamps.
7. **Posiciones**: tabs por procedencia humano/estrategia/IA (§4.3), P&L, deals, sesión forward en curso (R32).
8. **Replay**: cursor temporal por instrumento (lo diseñado en P7 + scrubbing de signal_history).
9. **AI Chat** (existente, crece a §7 roles), **Calendario**, **Settings** (modelos, presupuesto, kill-switch, cuentas).

### 6.2 Stack de charts (D-V2-8)
- **TradingView lightweight-charts** vendorizado (Apache-2.0, sin CDN, ~45 KB gzip, canvas): velas, pan, zoom, crosshair, series superpuestas, panes para osciladores, markers para trades. Cubre R1–R5 out-of-the-box y R6 con series adicionales.
- Alternativa evaluada: extender uPlot a candlesticks+markers+hover — más liviano en KB pero semanas de trabajo de UX para llegar a "nivel profesional"; **descartada** por tiempo/calidad. uPlot **se queda** para sparklines y equity/DD (ya vendorizado).
- **Datos bajo demanda**: el cliente pide ventanas (`GET /bars?symbol&tf&from&to&max_points`) y el servidor decima (LOD) si la ventana excede max_points; nunca se envía el histórico completo. Indicadores se computan **en el servidor** (mismo código causal del catálogo — una sola fuente de verdad) y se envían como series alineadas.
- Presupuesto de perf: ≤ 60 MB de heap del tab con chart abierto; una sola rAF loop; tablas virtualizadas (>200 filas); WS sólo diffs; `prefers-reduced-motion` respetado.
- **Frescura de datos (corrección usuario 2026-07-09): la liviandad NUNCA a costa de inmediatez.** Refresh de indicadores **sub-1 s**; canal WS de **ticks** (bid/ask de Capitaria vía `symbol_info_tick`, loop on-change ~250 ms) por símbolo suscrito, para que la última vela del chart se mueva **al ritmo de los ticks** cuando la sección lo requiera (`series.update()` de lightweight-charts está diseñado exactamente para esto, costo ~0). Indicadores recomputados ≤1 s; línea de precio por tick.

### 6.3 Estilo cyberpunk minimal (D-V2-15)
Sólo tokens CSS sobre la base actual (sin frameworks, sin fuentes pesadas — system stack o una sola variable-font vendorizada):
- Paleta: fondo `#0a0e14`/`#0d1117`, superficie `#131a24`, texto `#c9d4e3`, acentos neón **cian `#00e5ff`** (señal/acción), **magenta `#ff2ec4`** (alertas/SHORT), **lima `#a6ff4d`** (LONG/éxito), ámbar `#ffb020` (warning). Un acento dominante por sección.
- Glow: `box-shadow` con blur ≤ 8 px SOLO en elementos interactivos/estado activo (el glow grande arruina GPU en integradas); bordes 1 px con el acento al 30 % de alpha; scanline/grid sutil como background-image estático (costo cero en runtime).
- Tipografía monospace para números/ids (tabular-nums), sans para prosa. Densidad alta, chrome mínimo — el estilo sale de color+borde+glow puntual, no de ornamentos.

---

## §7. Objetivo B — Asistente IA multi-rol (resumen de diseño)
- **Arquitectura**: `service/chat.py` evoluciona a agente con **tool registry** (JSON-schema por tool ⇒ export MCP trivial a futuro): `get_snapshot(asset)`, `get_bars(asset, tf, n)`, `get_positions(origin?)`, `get_calendar(window)`, `query_registry(filters)`, `get_trade_detail(id)`, `run_backtest(variant, window)` (job async, respeta pre-registro), `propose_order(intent)` (→ pipeline de guardarraíles → gateway §4.4; Rol 3).
- **Rol 1 (advisor)**: contexto = `render_ai_context()` extendido (posiciones con procedencia + trayectoria de snapshots + régimen + calendario) + web-search. El formato óptimo para series complejas hacia el modelo es **una tarea de investigación pre-implementación** (como pide el brief): construir un mini-eval (mismas preguntas, formatos distintos: tabla compacta vs JSON vs resumen estadístico) y medir calidad de respuesta; `ASSUMPTION` inicial: tablas compactas estilo CSV + stats agregadas > arrays crudos.
- **Rol 2 (copiloto)**: la IA es un usuario más del registry/sim vía tools; entrega informes citando run_ids/evidencia (R36 aplica también a la IA).
- **Rol 3 (ejecutor, SOLO demo)**: la IA NUNCA llama `order_send`; sólo `propose_order` — el gateway y sus guardarraíles deciden. Override de SL/TP por IA = nueva propuesta auditada con traza. Presupuesto de uso/costo por rol (medidor ya diseñado en §3.1 original; los toggles modelo/esfuerzo y roster `models.yaml`+`GET /models` ya están construidos).

---

## §8. Encaje con P0–P7 y faseo accionable (ASAP, hitos verificables)
P0–P3+P5 hechos; P4 en vuelo (commitear G1+PAR primero — lane existente). Fases nuevas **S0–S6** (Sonnet 5 implementa; cada una con gate verificable; orden por valor/desbloqueo — S0–S2 atacan el dolor "asap" del proyecto hermano):
- **S0 · Fundación de datos (días)**: registry v2 + importadores TOKATA + **estudio baseline** (genoma v1 por asset, lentes por capa). *Gate*: ledger TOKATA visible unificado en registry; reporte baseline versionado; golden 6/6 intacto.
- **S1 · Charts + Trade Review**: lightweight-charts vendorizado, sección Charts (R1–R6), endpoint /bars con LOD, overlays server-side, Trade Review (R13) sobre corridas TOKATA importadas. *Gate*: recorrer trade-a-trade una corrida EMASAR real sobre el chart, TF conmutable, hover completo.
- **S2 · Tier-1 sim + primer port**: `sim/` (broker-sim spec §2.3), `StrategyPolicy`, port EMASAR (desde `emasar_ref.py`), **fidelity audit vs MT5** con umbrales, sweep runner sobre study/fleet, `record_snapshots` + signal_history. *Gate*: sweep ≥100 variantes EMASAR en sim con walk-forward; auditoría de fidelidad verde; panel de señales scrubbable en una corrida.
- **S3 · Genoma v2 + regime (P6)**: FeatureSpec registry + catálogo inicial + ScoringGraph + `graph_v1` (paridad byte-exacta) + macro v2 (lagged_beta + gate coherencia) + labeler de régimen + estudio comparativo: graph_v1 vs ≥3 challengers (incl. `role_based` tf_policy) en XAUUSD con las 5 lentes. *Gate*: golden verde con ancla v1; estudio con reporte y diff PROPUESTO (nunca auto-aplicado).
- **S4 · Adaptador MT5 + funnel**: wrapper batch_runner como job del servicio, flujo promote-to-validation, pre-registro enforced en UI, fidelity ladder visible en toda la reportería (R25/R31). *Gate*: un click promueve el ganador de un sweep → corrida screening MT5 → fila canónica + .htm linkeado.
- **S5 · Forward/live + procedencia**: poller demo read-only, magic-ranges, sección Posiciones por origen, forward_session (FORWARD39 visible), criterio de graduación (R33). *Gate*: posiciones demo en vivo correctamente segmentadas por origen en la UI.
- **S6 · Gateway + IA Rol 2/3**: gateway demo-only completo (§4.4, incl. test CI de imports), tools de lectura + run_backtest (Rol 2), luego propose_order (Rol 3). *Gate*: orden demo tomada por IA bajo instrucción explícita, con traza de guardarraíles y audit completo; test CI de frontera verde.
Transversal: paridad golden en cada fase; cutover del scorer legacy→graph como commit aislado revertible (regla P1 pinned); browser-check visual del UI-rework (pendiente D38) se hace en S1 junto con la primera sección nueva.

## §9. Preguntas abiertas — RESUELTAS por el usuario (2026-07-09)
1. **Magic-numbers**: diseñar para escala amplia (muchas estrategias × múltiples variantes/configs; al menos TODAS las ya probadas en TOKATA). Esquema adoptado: `magic = 100000 + strategy_seq*1000 + variant_seq` (≈900 estrategias × 1000 variantes), rango `900xxx` reservado IA, no-match = human; tabla `magic_allocation` en registry v2, asignación automática al registrar variante.
2. **Calendario económico**: sin licencia ni capital → alternativa gratis (scrape u otras). Al momento de implementarlo, **subagente de pre-investigación** entrega un reporte de opciones (fuentes, formato, fragilidad, legalidad) antes de codear.
3. **Símbolos a importar**: por ahora sólo los 3 targets (USDCLP, NQ100, XAUUSD) + sus referencias macro.
4. **Compilación `.mq5`**: la manual NO es aceptable al volumen requerido → **asistida por IA / semi-automatizada**; flujo conversacional con Claude Code es solución aceptable (es quien las ha realizado hasta ahora). S4 intenta además MetaEditor CLI con fallback al flujo asistido.
5. **NT8**: congelado, irrelevante, no se utilizará (ingesta histórica solamente).
6. **Umbrales de fidelity audit**: se aceptan los recomendados (±1 barra, ±% PnL, conteo exacto); testear 2–3 sets de umbrales en S2 si aporta.

> **Assumptions etiquetadas** inline (`ASSUMPTION`) en §2.3, §2.4, §3.3, §6.1, §7. Fin de la respuesta.
