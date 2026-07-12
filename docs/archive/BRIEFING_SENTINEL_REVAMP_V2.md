# SENTINEL Revamp — Briefing v2 (segunda pasada para Fable 5)

> **Fecha:** 2026-07-08 · **Estado:** solicitud de diagnóstico + diseño · **Owner:** usuario (YggrYergen)
> **Rama/commit al redactar:** `release` @ `f07ffbf`
> **Autor del brief:** orquestador Opus 4.8 (transcribe intención del usuario; no diseña la solución — eso se le pide a Fable).

---

## 0. Propósito y cómo leer este documento

Este es un **brief de segunda pasada**. La primera pasada (brief original + respuesta de Fable) definió una arquitectura de core headless + backtesting/optimización + UI liviana + IA + replay/logging, y esa arquitectura **ya está mayoritariamente construida** (ver §2). Sobre esa base, el proyecto ha **afinado y expandido** lo que realmente necesita del sistema. Este documento expone ese alcance expandido y **le pide a Fable un diagnóstico detallado y un diseño estructurado** que lo haga realidad, encajando con lo ya construido y con el plan existente.

**Qué le pedimos a Fable (resumen; detalle en §7):** una respuesta **extensa y detallada, en lenguaje conciso y técnicamente denso**, que entregue diagnóstico + recomendaciones + **todas las especificaciones y decisiones de diseño** necesarias (arquitectura, componentes, contratos de datos, flujo, faseo, encaje con el plan y con lo construido), con **assumptions etiquetadas** y **motivo** de cada recomendación.

**Documentos base que Fable debe considerar (contexto completo — no se reproducen aquí):**
- `BRIEFING_SENTINEL_REVAMP.md` — brief original (v3.7.1)(no tan reevante, no vigente).
- `FABLE5_RESPONSE_SENTINEL_REVAMP.md` — **respuesta de diseño original de Fable (§0–§7)**. Es la fuente de verdad técnica previa; este v2 la extiende, no la reemplaza. Releerla es obligatorio: gran parte del vocabulario (Snapshot, InstrumentConfig, capas de ground-truth, walk-forward, registry) se hereda de ahí.
- `docs/superpowers/plans/2026-07-07-sentinel-revamp.md` — plan por fases (P0–P7) derivado de esa respuesta.
- `docs/superpowers/specs/2026-07-07-sentinel-revamp-workflow-design.md` — gobernanza (ruteo de modelos, 2-strikes, gate Fable).
- `INFORME_TECNICO_SENTINEL.md` — informe técnico del estado.

**Cómo usar §2:** es el ancla en la **realidad construida** (no en lo planeado). Cualquier recomendación de Fable debe partir de estos componentes concretos, reusándolos donde ya cumplen y señalando explícitamente dónde propone extender, refactorizar o reemplazar.

---

## 1. Contexto de una línea

SENTINEL puntúa en vivo, por asset (XAUUSD/NQ100/USDCLP), un score compuesto técnico+macro sobre datos MT5 read-only, con un core determinista (`sentinel_engine`) que emite `Snapshot` inmutables, replayables bit-exactos sobre un lake histórico. Queremos convertirlo en el **ecosistema único** donde (a) se optimiza la **calidad de la señal** (técnica y macro por separado, como espacio combinatorio flexible), (b) vive un **asistente IA multi-rol** (advisor + copiloto de investigación + ejecutor semi-autónomo con límites), y (c) las **estrategias** (incluidas las de TOKATA) son ciudadanas de primer nivel: backtesteables, editables, y con desempeño/historial visibles en la UI — con **procedencia de cada posición diferenciada** (humano / estrategia autónoma / IA) con su id único trackeable y debidametne registrado.

---

## 2. Estado construido (ground truth, no lo planeado)

Todo lo siguiente **existe hoy** en `sentinel_engine/` (rama `release` @ `f07ffbf`), con gate de paridad golden verde (6/6) y suite opt verde salvo lo marcado.

### 2.1 Core headless (P1 — hecho)
- `config.py` — `InstrumentConfig` (+ `IndicatorConfig`, `MacroConfig`, `TechnicalConfig`, `CompositeConfig`, `TrackerConfig`, `DataConfig`), `load_instrument()`, `config_hash()`. Un YAML por asset en `instruments/{gold,nasdaq,usdclp}.yaml`.
- `feed.py` — protocolo `Feed`; `technical.py` — `TechnicalScorer(cfg)`; `macro.py` — `MacroScorer(cfg)` (EWMA dual-lambda, warm-up, concordancia).
- `engine.py` — `Engine(cfg, feed).step(seq) -> Snapshot`; el compuesto = `tech*w_tech + macro*w_corr`, dirección por voto ponderado (`direction_vote_weights`), semáforo por umbrales.
- `ai_context.py` — `render_ai_context()` (único productor de contexto IA, sin literales). `timeline.py` — `TimelineAligner`.
- **Determinismo/paridad:** `tests/golden/test_parity.py` (6/6, byte-idéntico) es el gate de aceptación de todo cambio de scoring.

### 2.2 Lake + replay punto-en-el-tiempo (P2 — hecho)
- `lake/store.py` (`read_bars`), `lake/ingest_dukascopy.py`, `lake/ingest_mt5.py`, `lake/manifest.py`. Lake real presente en `data/lake` (barras MT5 reales).
- `feed_historical.py` — `HistoricalFeed(as_of)` con gate de leakage (`ts <= as_of` **antes** de computar).
- Ingesta de trades reales: `trades/schema.py`, `trades/ingest_xtb.py`, `trades/ingest_mt5_trades.py`.

### 2.3 Servicio + UI liviana (P3 + UI-rework — hecho)
- `service/app.py` (FastAPI), `service/stream.py` (WS broadcaster), `service/chat.py`.
- `service/web/`: `index.html`, `app.js`, `chat.js`, `lab.js`, `style.css`, `vendor/` (uPlot vendorizado, sin CDN). Réplica v2 multi-instrumento; secciones Regime/News/Study/Chat; endpoints `GET /levers`, `GET /models`, stubs 501 gateados para replay/variant/study/fleet/calendar; controles de web-search vs extended-thinking mutuamente excluyentes. **Falta:** verificación visual en navegador (pendiente) y algunos gaps (HOY%/sparklines de correlación).

### 2.4 Motor de optimización / validación (P4 — maquinaria construida; estudios reales pendientes)
Presentes en `sentinel_engine/opt/`:
- `labels.py` — `triple_barrier` (López de Prado) + `purge_labels_at_boundary`.
- `objective.py` — `objective()` → `J = PF_capped(3.0) * sqrt(n_trades/n_ref)` con gates (maxDD, n_min, win_rate); `ObjectiveResult` con set de métricas persistible.
- `walkforward.py` — `anchored_walkforward` (train/test/embargo, purga).
- `search.py` — `staged_search` (Optuna TPE + grids), `LeverGroup`, `ParamSpec`.
- `selection.py`, `registry.py` (SQLite+Parquet), `report.py`.
- `evaluator.py` — `evaluate_config()` (oracle: replay del `Engine` bar-a-bar, etiquetado direccional, objetivo), `_ReplayFeed`, `make_objective_fn`.
- `fast_replay.py` — `fast_evaluate_config()` + `FastReplayCache` (memoización, ~6.1×, bit-exacto vs oracle).
- `levers.py` — `LEVER_GROUPS` (G1–G7, mapeados a campos reales de `InstrumentConfig`), `apply_overrides`, `priors_for`.
- `study.py` — driver de estudio P4 con `--workers` (paralelismo). `run_fleet.py` — orquestador de flota bajo presupuesto fijo de cores (6//K).

### 2.5 Divergencias vs el plan original y hallazgos que motivan re-evaluar
- **Mapeo de levers G1–G7 repurposado:** el `InstrumentConfig` real es más chico que la superficie "fusion/risk/regime" que Fable imaginó, durante la implementación argumentó algunas de inertes. `levers.py` documenta las decisiones: G6 = indicadores secundarios (no fusion/risk, que no existe como campo), G7 = simplex de asset-weights (no regime, que es P6 futuro), G2/G3 fusionados, `rsi_ob/os` **eliminados como lever por probadamente inertes**. Esto importa: **la superficie de levers actual está limitada por la forma del `InstrumentConfig`, no por lo que queremos optimizar** (ver Objetivo A, §3). 
- **Hallazgo G1 de bajo apalancamiento (esta sesión, evidencia real sobre lake de gold):** los levers de indicadores están correctamente cableados y son bit-exactos oracle==fast, pero **mueven muy poco el objetivo**: sólo 1 de 25 configs cambió el score, porque (i) técnico pesa 0.5 en el compuesto y (ii) la dirección la domina macro (voto 3 vs 2), de modo que los indicadores casi nunca cruzan el umbral ni cambian el lado de una entrada. *Corolario de diseño:* optimizar indicadores aislados rinde poco bajo la arquitectura de scoring actual pero siguen siendo relevantes y valiosos de tener a mano; además, la **calidad de señal debe optimizarse como sistema** (indicadores × pesos × sub-scores × dirección × umbral × TF), no sólo lever-por-lever. Esto es exactamente lo que el Objetivo A pide repensar: se requiere poder optimizar varias cosas: primero que nada cada asset (XAUUSD,USDCLP,NQ100) tiene su propia cofig optima,, segundo en cada una de ellas se desglozan dos rutas la técnica y la macro, son distintas y cada una se debe optimizar con diferentes ideas/propuestas/enfoque/diseño, lo importante es probar la mayor catindad de hipótesis que pueda rendir beneficios o mejorar respecto al desempeño actual (que tampoco se ha medido hasta ahora).
- **Regime (P6) no construido:** `regime/` sólo tiene `__init__`. El labeler de régimen y el ajuste global-first/regime-delta están pendientes.

---

## 3. Objetivo A — Calidad de señal como framework combinatorio flexible (XAUUSD primero)

**Intención central:** poder **medir y optimizar** qué tan fiel es la recomendación del sistema, tratando técnico y macro como **dos capas separables** cuyo espacio de configuración es **combinatorio y extensible**, no un set fijo de levers.

### 3.1 Capa técnica
- Debe poder probarse **N combinatorias** de: *qué* indicadores entran, *qué* variables/períodos usan, *cómo* se ponderan entre sí (sub-scores) y cómo agregan a la dirección/score.
- **Extensibilidad de features es un requisito de primer nivel:** a futuro añadiremos consideraciones nuevas — p.ej. **zonas de compra / zonas de venta** (S/R, order-blocks, niveles), y otras aún no definidas. El diseño debe permitir **agregar un nuevo tipo de señal/feature** y su peso sin reescribir el motor ni romper paridad.
- Pregunta a Fable: ¿cuales son todas las configuraciones que vale la pena testear para el scorer técnico, para que el conjunto de indicadores/features y su ponderación sean además de **datos configurables** (parte del genoma `InstrumentConfig`/variante) entreguen resultados reales que den edge y net profit +, habilitando búsqueda combinatoria (selección de subconjunto + pesos + params) sin explotar la dimensionalidad ni el overfitting?
- Para estudios grandes se debe poder paralelizar la corrida de backtests y tests.

### 3.2 Capa macro
- **Primero:** encontrar las mejores maneras de estimar, **por cada referencia y por asset objetivo**, hacia **dónde y cuánto** "recomienda" esa referencia (sube/baja + magnitud/confianza). Es decir, convertir cada referenciado (DXY, silver, VIX, EURUSD, SP500, USDJPY, copper, …) en un **pronosticador direccional con magnitud** respecto del target, y aprender cómo combinarlos/pesarlos. Vale la pena considerar mixes de distintos timerames de qué? Queremos poder realizar las pruebas.
- **Luego, en vivo/diario:** **selección adaptativa** de cuáles referencias considerar y cuáles no, en base a **algún indicador que detecte cuándo se están comportando de forma similar** al minuto / 5 minutos / n-minutos (co-movimiento/correlación/coherencia en tiempo real, multi-escala). Referencias que dejan de co-moverse coherentemente deberían **auto-desactivarse** (o bajar peso); las que entran en régimen coherente, **activarse**.
- Preguntas a Fable: ¿qué familia de estimadores direccionales-con-magnitud por referencia recomienda (y cómo se validan sin leakage sobre el lake)? ¿Qué **indicador de co-movimiento multi-timeframe** propone para la selección adaptativa en vivo, cómo se computa punto-en-el-tiempo, y cómo se integra al `Snapshot`/engine sin romper determinismo/paridad? ¿cuales neuvos podemos diseñar y testear por neustra cuenta, que tengan probabilidad de entregar resutlados positivos?

### 3.3 Descomposición multi-timeframe (pregunta abierta explícita)
- Hoy el blend multi-TF es un peso por TF (`tf_weights` M15/M5/M2/M1). Sospechamos que **la mejor solución descompone la consideración multi-TF de distintas cosas** (p.ej. dirección a un TF, timing/entrada a otro, régimen/volatilidad a otro, co-movimiento macro a otro).
- Pregunta a Fable: ¿cómo descomponer la señal por timeframe de forma principiada (qué se decide a qué escala), y qué implica para el engine, el espacio de búsqueda y la validación walk-forward? ¿cuales son las distintas opciones? Querremos dejarlas listadas y utilizar el sistema implementado para poder probarlas, generarles variantes, hacer versiones fork, etc. cómo esto es súper relevante es donde más se requiere ofrecer alternativas, disitnas opciones, disitnas estrategias para que podamos realizar una prueba y análsiis sólido al respecto. 

### 3.4 Qué debe permitir el sistema (métricas y backtesting)
- **Métricas de "calidad de señal" separadas por capa** (técnica vs macro), no sólo el PnL final del objetivo. Necesitamos poder decir "el compuesto técnico solo predice X" y "la capa macro sola predice Y", además del sistema combinado.
- El engine + registry deben permitir correr y **comparar** estas combinatorias sobre **historial real** (el lake), con el protocolo de validación heredado (walk-forward anclado, purga, holdout, DSR) para no auto-engañarnos.
- Nota de encaje: reconciliar esto con las 3 capas de ground-truth de Fable (§2.4 original: labels triple-barrier, PnL de reference-policy, cross-check de trades reales). La "calidad de señal por capa" probablemente es una **cuarta lente de evaluación** (endorsement/accuracy por capa) que hay que definir bien.

---

## 4. Objetivo B — Asistente IA multi-rol

El chat IA debe cumplir **tres roles**, todos de primer nivel, cada uno con su presencia en la UI. Toggle de **modelo y nivel de esfuerzo** siempre disponible; a futuro, capacidad de **conectar un MCP** (u orquestación de herramientas equivalente).

### 4.1 Rol 1 — Advisor de posiciones en vivo
- La IA debe **ver las posiciones abiertas en vivo** (de cualquier procedencia, §5.3) y poder opinar sobre ellas: mérito, riesgo, SL/TP sugeridos, watch-items.
- Debe poder **buscar noticias relacionadas** (web-search) y cruzar con el calendario económico y el `Snapshot`/régimen del momento.
- debe pdoer ver en vivo la información del asset de la posición sobre la que se está discutiendo y sus disintos indicadores y comportamiento a disitntos timeframes, velas a distintos timeframes, poder ver lo sindicadores qu muestra sentinel y lo que ha mostrado en el último n tiempo) (ojo será crucial antes de realizar ésa implementacaión en partcualr investiar actualmetne cual es el mejor formato para transmitir esa info compleja a opus y fable, series de datos, indicadores técnicos, macors, custom, señales e historial, zonas de venta y compra, etc; todo lo que necesite apra poder informadamente entregar una opinión porfesional. 

### 4.2 Rol 2 — Copiloto de investigación de estrategias (SENTINEL + TOKATA)
- Asistir en **crear, testear, mejorar y re-evaluar** estrategias, tanto de este proyecto como de **TOKATA**.
- Debe poder **ver todos los datos de cada trade** (histórico, enriquecido con el Snapshot at-entry, MAE/MFE, régimen, etc.), **correr tests/backtests**, y **entregar informes**.
- En la práctica: la IA es un usuario más del motor de backtesting/registry (§2.4) y del ecosistema de estrategias (§5), operándolo vía herramientas.

### 4.3 Rol 3 — Ejecutor semi-autónomo de estrategias (SÓLO demo)
- Debe poder **tomar posiciones** según **N estrategias configurables** durante el día. Cada estrategia = reglas + parámetros; visible y gestionable en la UI.
- Flujo típico: se le señala a la IA "**la estrategia X está recomendando comprar**" y la IA puede **entrar / sumar posición**, dentro de límites.
- **Límites/guardarraíles obligatorios por estrategia** (configurables): máximo de posiciones por día, tamaño máximo de posición, stop-loss máximo, y más reglas (exposición total, horario/sesión, buffer de noticias, R:R mínimo, etc.).
- Las posiciones 100% IA **pueden tener SL/TP programáticos**, y la **IA puede overridearlos** (con registro de la decisión).
- **Frontera de ejecución (no-negociable actualizado):** la ejecución (colocación de órdenes) ocurre **exclusivamente en cuenta(s) demo** (p.ej. `MT5_DEMO_TOMAS`). Las cuentas reales (p.ej. la de "papá", `MT5_REAL_PAPA_SOLO_LECTURA`) permanecen **estrictamente read-only, sin órdenes jamás**. Fable debe diseñar la **capa de ejecución + salvaguardas** respetando esta separación dura (broker/cuenta de ejecución aislada, límites aplicados antes de enviar, auditoría de cada orden, kill-switch).

### 4.4 Requisitos transversales de la IA
- Toggle de modelo + esfuerzo (roster actualizable, tipo `models.yaml` + refresh contra API de modelos, como en §3.1 original).
- Preparado para **MCP** a futuro (arquitectura de herramientas extensible).
- Contexto siempre derivado del `Snapshot`/estado (nunca literales), con time-context (trayectoria de snapshots logueados), posiciones, régimen y calendario.
- Gobernanza de uso/costo (presupuesto, medidor), y **ruteo de modelos** respetando la restricción de costo del proyecto.

---

## 5. Objetivo C — Estrategias como ciudadanos de primer nivel + integración TOKATA

**Meta macro:** que **toda la investigación que se ha corrido y se sigue corriendo en TOKATA pueda realizarse dentro del ecosistema SENTINEL** — sin perder lo que TOKATA ya produjo.

### 5.1 Qué es TOKATA (referencia; ubicación `D:/WebDev/TOKATA`)
Proyecto hermano de investigación/backtesting de estrategias de trading, con:
- **Estrategias concretas** (EAs): Sapitos V1, PedroV2, familia **G3**, TrailGuard / ExitTrailGuard, entre otras; implementaciones **MQL5** (`mt5/`) y **NinjaTrader** (`NinjaTrader_Strategies/`).
- **Generación de variantes + runner de backtest** (`mt5/scripts/gen_variant.py`, `variantes_forward.py`, `correr_backtest.ps1`), optimizador de trailing (`trailguard_opt/`).
- **Protocolos de forward-test / walk-forward en vivo** (`PROTOCOLO_FORWARD_*`, `research/DOSSIER_FORWARD_WALK_*`), auditorías de fidelidad (`research/AUDITORIA_FIDELIDAD_*`), resultados (`backtest_results/`, `research/`).
- Concepto de estrategias que **"se gradúan"** (semifinalistas → forward test → corriendo en vivo).
Fable debe revisar estos artefactos para entender el **formato de estrategia, de variante y de resultado** que hay que absorber o interoperar.

### 5.2 Qué queremos en SENTINEL
- Cada estrategia como **entidad registrada y visible en la UI**, con lugar para **ver y correr sus backtests** y **editar variables/parámetros**.
- **Sí o sí** para las estrategias **graduadas** que corren en **testeo live / walk-forward en vivo**: ver su **desempeño** y **historial de posiciones** en la UI.
- A futuro: estrategias con **indicadores/configuraciones distintas** conviviendo; comparables bajo una misma vara metodológica.
- **Modelo de integración con TOKATA: se le delega a Fable** — exponer trade-offs entre (a) re-implementar las estrategias como reference-policies/variantes nativas backtesteadas por *nuestro* engine (máxima comparabilidad; más porteo), (b) ingerir y mostrar los artefactos que TOKATA ya produce (rápido; menor comparabilidad), o (c) un faseo de ambos. Recomendar arquitectura + camino.

### 5.3 Procedencia de posiciones — taxonomía de primer nivel (requisito duro)
La aplicación funcionando debe **diferenciar** y permitir **revisar en secciones/pestañas/componentes distintos de la UI** las posiciones según su **origen**:
1. **Humano** — tomadas manualmente por el trader.
2. **Estrategia autónoma** — tomadas por las estrategias que corren solas (las **graduadas de TOKATA**), según sus reglas/params.
3. **100% IA** — tomadas por la IA (Rol 3). Pueden tener **SL/TP programáticos**; la IA **puede overridearlos** (con traza).

Esta procedencia debe ser **parte del modelo de datos de cada posición/trade** (no sólo de la vista), de modo que desempeño, historial, enriquecimiento y reportes puedan **segmentarse por origen** de forma consistente en toda la app (live, replay, backtest, registry). Fable debe definir el **esquema de procedencia** y cómo se propaga end-to-end.

### 5.4 Entrelazamiento B↔C (nota para Fable)
Los Objetivos B y C **no son aislados**: la IA (Rol 2/3) **opera y backtestea** las estrategias, y las estrategias provienen en parte de TOKATA. El diseño debe tratar "estrategia" como un **contrato de primera clase** compartido por: definición/params, backtest, registro de desempeño, ejecución (demo), procedencia de posiciones, y las herramientas que la IA usa para investigarlas/ejecutarlas.

---

## 6. Restricciones y no-negociables (actualizados)

- **Ejecución vs read-only (ACTUALIZADO):** cuentas reales **estrictamente read-only, sin órdenes jamás**; la ejecución de IA/estrategias ocurre **sólo en cuenta(s) demo**, bajo límites y con salvaguardas/auditoría. (Reemplaza el anterior "sin colocación de órdenes en ningún lado".)
- **OS:** correr en **Windows 10 y 11**. `pathlib`; `encoding="utf-8"` explícito; sin APIs de versión de OS; reusar el launcher embebido; sin supuestos WSL.
- **Paridad/determinismo:** ningún cambio de scoring puede alterar el output vs el golden master (`tests/golden/test_parity.py`). Mismo feed + config ⇒ Snapshot byte-idéntico (config_hash + seq).
- **Costo/OSS:** sólo herramientas free/OSS; API de Anthropic permitida sólo como feature de runtime. **Ruteo de modelos** con restricción de costo (Opus escaso; Sonnet default; ver gobernanza).
- **HW target:** ~4–6 GB RAM, 4 hilos, SSD ~50 GB, con MT5 corriendo al lado. Nada puede volver la UI más lenta que hoy.
- **Compatibilidad hacia atrás:** lo ya construido (§2) se reusa; los cambios se integran vía el gate de paridad y el registro de variantes (drift siempre visible).

---

## 7. Qué le pedimos exactamente a Fable (formato de la respuesta)

Una **respuesta extensa y detallada, en lenguaje conciso y técnicamente denso** (estilo de su respuesta original), que cubra —sin omitir ninguno— los Objetivos A, B y C, y que incluya:

1. **Diagnóstico** del alcance expandido contra lo ya construido (§2): qué encaja tal cual, qué hay que extender/refactorizar/reemplazar, qué riesgos y tensiones (incluida la de bajo apalancamiento de señal §2.5, y la de ejecución/read-only §4.3).
2. **Diseño por objetivo**, con para cada uno: **arquitectura, componentes (con su propósito, interfaz de uso y dependencias), contratos de datos, flujo de datos, manejo de errores, y estrategia de testeo/validación** (respetando paridad y no-leakage).
3. **Especificaciones recomendadas con su motivo:** para cada decisión relevante, indicar la recomendación concreta **y por qué** (trade-offs evaluados, alternativas descartadas). Etiquetar toda suposición como `ASSUMPTION`.
4. **Objetivo A:** framework combinatorio de señal (técnica extensible a features tipo zonas compra/venta; macro con estimadores direccionales-con-magnitud por referencia + selección adaptativa multi-TF por co-movimiento), descomposición multi-timeframe, y **métricas de calidad de señal por capa** integradas al protocolo de validación.
5. **Objetivo B:** arquitectura del asistente multi-rol (advisor / copiloto de investigación / ejecutor semi-autónomo), la **capa de ejecución demo con salvaguardas y límites por estrategia**, toggle modelo/esfuerzo, y preparación para MCP.
6. **Objetivo C:** contrato de "estrategia" de primera clase, modelo de integración TOKATA (recomendado, con trade-offs y faseo), UI de backtest/params/desempeño/historial, y el **esquema de procedencia de posiciones (humano/estrategia/IA)** propagado end-to-end.
7. **Encaje con el plan existente:** cómo se insertan estos objetivos en/junto a las fases P0–P7 (qué fases se extienden, cuáles se agregan, dependencias, orden), manteniendo las restricciones de §6.
8. **Faseo accionable y priorización** por valor/esfuerzo, con hitos verificables.
9. **Preguntas abiertas** que, respondidas, afinarían una tercera pasada (sin que ninguna bloquee el diseño).

---

## 8. Punteros / adjuntos (rutas exactas a revisar)

**Este repo (`D:/FOREX`):**
- Docs base: `BRIEFING_SENTINEL_REVAMP.md`, `FABLE5_RESPONSE_SENTINEL_REVAMP.md`, `INFORME_TECNICO_SENTINEL.md`, `docs/superpowers/plans/2026-07-07-sentinel-revamp.md`, `docs/superpowers/specs/2026-07-07-sentinel-revamp-workflow-design.md`.
- Core: `sentinel_engine/{config,feed,technical,macro,engine,ai_context,timeline,feed_historical}.py`, `sentinel_engine/instruments/*.yaml`.
- Opt: `sentinel_engine/opt/{labels,objective,walkforward,search,selection,registry,report,evaluator,fast_replay,levers,study,run_fleet}.py`.
- Lake/trades: `sentinel_engine/lake/*.py`, `sentinel_engine/trades/*.py`.
- Servicio/UI: `sentinel_engine/service/{app,stream,chat}.py`, `sentinel_engine/service/web/*`.
- Gate: `tests/golden/`, `tests/opt/`.
- Cuentas/ejecución: `MT5_DEMO_TOMAS.bat` (demo, ejecutable), `MT5_REAL_PAPA_SOLO_LECTURA.bat` (real, read-only), `CUENTAS.md`.

**Proyecto TOKATA (`D:/WebDev/TOKATA`):**
- Guías/protocolos: `FABLE_OPERATING_GUIDE.md`, `PROTOCOLO_FORWARD_G3_1MES.md`, `PROTOCOLO_OPERATIVO_FORWARD_TEST.md`.
- Estrategias: `NinjaTrader_Strategies/`, `mt5/` (incl. `mt5/scripts/{gen_variant.py,variantes_forward.py,correr_backtest.ps1}`), `trailguard_opt/`.
- Investigación/resultados: `research/` (dossiers forward-walk, auditorías de fidelidad, nominación de semifinalistas G3), `backtest_results/`, `reporte/`, `data/`.
- Explicaciones de estrategia: `Sapitos_V1_Completa.txt`, `PedroV2_Completa.txt` (+ PDFs).

---

> **Instrucción para el subagente Fable 5 (one-shot, xhigh):** Lee los documentos base (§0) y el estado construido (§2) antes de responder. Entrega la respuesta de §7 completa, extensa, técnicamente densa y con motivos. No omitas ninguno de los Objetivos A/B/C ni el requisito de procedencia de posiciones (§5.3). Etiqueta assumptions. No implementes: sólo diagnostica y diseña.
