# Inventario de candidatos para el backtest largo (baseline vivo vs. retadores)

**Fecha:** 2026-07-27. **Rol de este documento:** inventario, no evaluación. No prioriza, no
recomienda, no elige. Cada cifra cita el fichero exacto de donde sale; donde no existe fichero que
la calcule, se declara **NO DISPONIBLE** — nunca estimada ni recordada (R5).

**Regla de substrato (crítica, ver directiva del user).** El substrato de análisis fue **reparado**
el 2026-07-27 (fix del pairing `"reverse"` + separación `EXIT_INITSL`/`EXIT_SL_RAISED`, tareas
R1–R4). Los números vigentes son los del substrato **REPARADO**: **2.542 posiciones, neto
39.513.978,56 CLP @0,67 lot/ficha**. Los artefactos previos a la reparación están congelados,
inmutables, en `data/analysis/pre_repair_snapshot/` (2.347 posiciones, neto 147.780.084,05 CLP) y
**se citan aquí solo como "ANTIGUO", nunca como vigentes.** Cada fila de la tabla de candidatos
declara explícitamente su substrato. Además de REPARADO/ANTIGUO existe una **tercera categoría**,
distinta de ambas y que no debe confundirse con "ANTIGUO": evidencia producida por un motor de
backtest **completamente distinto** (`sentinel_engine`'s honest-fill simulator sobre ventanas
IW/W1/W2/W3, programa "honest-league" 2026-07-13/20), que **precede** por completo a la
reconstrucción real-tick de 7 meses (ANTIGUO/REPARADO son ambos hijos de esa reconstrucción). Esa
evidencia se etiqueta aquí **OTRO** — también requiere re-medición sobre el substrato real-tick
antes de ser comparable, pero llamarla "ANTIGUO" sería impreciso (mide otra cosa, con otra unidad
monetaria en varios casos, y con fills en algunos tramos aún no honestos).

**Fuentes barridas** (todas leídas para este inventario):
`docs/superpowers/research/2026-07-27-substrate-repair-diff.md` (cuerpo R3 + §Veredictos R4,
V0–V17) · `docs/superpowers/plans/2026-07-25-monday-tracker.md` (tabla de tareas + bitácora +
§"Números que otras tareas necesitan", ambas versiones) ·
`docs/superpowers/research/2026-07-27-strategy-improvement-catalog-v3.md` ·
`docs/superpowers/specs/2026-07-27-long-backtest-queue.md` ·
`docs/superpowers/research/2026-07-22-FINAL-experiment-matrix.md` ·
`docs/superpowers/research/2026-07-22-prior-experiments-audit.md` ·
`docs/superpowers/research/2026-07-22-tokata-ladder-experiments-audit.md` (grep dirigido) ·
`docs/superpowers/research/2026-07-22-regime-filter-when-not-to-trade.md` (grep dirigido) ·
`docs/superpowers/research/2026-07-22-directional-bias-long-short.md` (grep dirigido) ·
`docs/superpowers/research/2026-07-27-b1-wait-curve.md` ·
`docs/superpowers/research/2026-07-27-b1-robustness.md` ·
`docs/superpowers/research/2026-07-25-wrapper-mask-verdicts.md` ·
`docs/superpowers/research/2026-07-24-account1-s6s7st-spread-filter-feasibility.md` (contexto) ·
`data/analysis/monday_audit/{a1_maxdd,a2_overlap,a5_spread_gate,b1_wait_window,b1_robustness,
b6_mask_verdicts}.json` — leídos directamente de disco para este documento (no solo citados vía el
diff doc) · `sentinel_engine/strategies/live_configs_20.py` — **solo lectura**, cero ediciones.

---

## 1. El arm de BASELINE, sin ambigüedad

### 1.1 Kwargs exactos (fuente: `sentinel_engine/strategies/live_configs_20.py`, solo lectura)

Esqueleto común a las dos estrategias `simular_variant` (`_SKELETON`, líneas 43-56):

```
confirm_mode=1, confirm_count=2, require_ema_order=False,
ema_fast=8, ema_slow=20, sar_step=0.3, sar_max=0.3,
f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
ac_modulate=True, symbol="XAUUSD"
```

Base M15 go-live (`_GOLIVE_BASE_M15`, líneas 232-239) = esqueleto anterior +:

```
init_sl_range_k=2.5, ac_modulate_factor=0.25, stop_and_reverse=True,
live_fill_mode=True, sar_adaptive=True, sar_fast=(0.3, 0.3),
sar_slow=(0.005, 0.05), vol_regime_window=200
```

| Estrategia | Delta sobre la base M15 (líneas 255-268) | Motor | `k` (init_sl_range_k) | Protección de utilidad |
|---|---|---|---:|---|
| **S6-K2P0** | `ac_modulate=True`, `trail_atr_floor_k=2.0` | `simular_variant` | 2.5 | **ninguna** — sin `be_at_r` |
| **S7-TPNONE** | `ac_modulate=False`, `trail_atr_floor_k=1.5`, `be_at_r=1.0` | `simular_variant` | 2.5 | breakeven a +1R |
| **SuperTrend-p14x3-M15** | motor propio, NO `simular_variant` | `supertrend_always_in` | n/a | ninguna (SL = línea SuperTrend, siempre en mercado) |

SuperTrend-p14x3-M15 (líneas 282-351): `ATR period=14` (`_ST_ATR_PERIOD`), `mult=3.0` (`_ST_MULT`),
`kwargs={"symbol": "XAUUSD"}`, una sola ficha F1, **always-in** (long si precio > línea, short si
< línea, flip al cruzar; sin estado plano). El SL es la propia línea SuperTrend, recalculada cada
barra M15.

Ninguna de las tres tiene take-profit (`f1_tp_r`/`f2_tp_r` ausentes de los tres bloques de kwargs).

### 1.2 Magic, banda y volumen desplegados

| Config | Magic (GOLIVE, líneas 353-364) | Magic vivo hoy (`CONFIGS_LOCAL`, líneas 572-587) | Volumen vivo (`CONFIGS_LOCAL`) | Magic retador congelado (`CONFIGS_CHALLENGER`, líneas 658-701, **NO armado**) | Volumen retador |
|---|---:|---:|---:|---:|---:|
| S6-K2P0 | 724010 | 724010 (sin cambio) | **0.1** lot/ficha | 726010 | 0.1 (paridad) |
| S7-TPNONE | 724020 | 724020 (sin cambio) | **0.1** lot/ficha | 726020 | 0.1 (paridad) |
| SuperTrend-p14x3-M15 | 724070 | 724070 (sin cambio) | **0.1** lot/ficha | 726070 | 0.1 (paridad) |

`CONFIGS_CHALLENGER` está definido en código (banda 726xxx, disjunta, verificada por assert) pero
**no está armado**: Task 12 (despliegue) sigue `[ ]` en el tracker, y el user acaba de **congelar
todo despliegue en vivo** — la secuencia fijada es backtest largo primero, decisiones después. Los
kwargs de `CONFIGS_CHALLENGER` son **byte-idénticos** a los del campeón (assert en código, línea
674-676: `_c["kwargs"] == _src["kwargs"]`); lo único que añade es el volumen (paridad 0.1) y un
diccionario `risk_gates` = `{gap_wait_minutes: 50, news_blackout_minutes: 30, max_open_fichas: 7,
min_sl_distance: 0.50}`. Es decir: **no es una variante de señal**, es la misma señal con un stack
de 4 puertas de riesgo superpuesto — ver §2.1.

`TK-Momentum-5-8-short` existe como 4ª estrategia viva (magic `999999998`, volumen 0.01,
`CONFIGS_LOCAL`) pero está **deliberadamente excluida** de este inventario: el propio código la
excluye de `CONFIGS_CHALLENGER` ("TK-Momentum deliberately NOT mirrored ... not part of the track
being compared") y el user definió el arm de baseline como las **tres** estrategias SAR/ST. No se
incluye como candidato ni como parte del baseline en este documento.

### 1.3 Cifras vigentes — substrato REPARADO (leídas directamente de los JSON en disco)

**A 0,67 lot/ficha** (convención usada en todo Track A y en el reporte mensual):

| Estrategia | n | net (CLP) | WR % | PF |
|---|---:|---:|---:|---:|
| S6-K2P0 | 1.053 | 17.859.879,00 | 32,4786 | 1,03336 |
| S7-TPNONE | 1.221 | 670.122,03 | 34,1523 | 1,00133 |
| SuperTrend-p14x3-M15 | 268 | 20.983.977,53 | 22,7612 | 1,14249 |
| **COMBINADO** | **2.542** | **39.513.978,56** | **32,2581** | **1,03334** |

Fuente: `data/analysis/monday_audit/b6_mask_verdicts.json` (bloque `B1.total_net_clp` y el
`baseline` de `data/analysis/monday_audit/b1_wait_window.json`) — ambos leídos directamente de
disco para este documento, valores idénticos entre sí. Cruzado también contra
`data/analysis/monday_audit/a5_spread_gate.json` (`COMBINED.at_0.5` / `unfiltered`, mismos valores
al céntimo).

**A 0,1 lot/ficha** (tamaño REAL desplegado hoy en `CONFIGS_LOCAL`): solo existe la cifra
**combinada**, no desglosada por estrategia, en `data/analysis/monday_audit/a1_maxdd.json`:
`final_net_clp = 5.897.608,74 CLP` (coincide exacto con el rescalado lineal
39.513.978,56 × 0,1/0,67, método documentado en `scripts/analysis/monday_audit/loader.py::net_at_lot`,
pero el desglose por estrategia a 0,1 lot **no está calculado en ningún artefacto** →
**NO DISPONIBLE por estrategia a 0,1 lot** — no se calcula aquí a mano).

**maxDD** (`data/analysis/monday_audit/a1_maxdd.json`, @0,1 lot, cuenta virtual combinada de
59.600.000 CLP): `max_dd_clp = 19.276.260,47` = **32,3427 %** del balance inicial, **25,0727 %** del
pico de equity (17.281.515,46 CLP, 2026-03-23 05:32:53 srv) hasta el valle (−1.994.745,01 CLP de
P&L acumulado, 2026-04-29 01:57:51 srv — es P&L acumulado bajo su punto de partida, **no** la
cuenta en negativo).

**Solape y correlación** (`data/analysis/monday_audit/a2_overlap.json`, leído directo):
`max_simultaneous_fichas = 7` (p95=p99=7), `n_trading_days = 163`,
`pct_time_with_any_position = 93,2927 %`. Correlación diaria de neto por par:
S6\|S7 = **+0,766939**, S6\|ST = **+0,355634**, S7\|ST = **+0,153498**. SuperTrend es la única
pata poco correlacionada, y aporta el 53 % del neto combinado (20.983.977,53 / 39.513.978,56) con
solo 268 de 2.542 posiciones (10,5 % de la muestra).

**Spread** (`data/analysis/monday_audit/a5_spread_gate.json`, leído directo): **100 % de las 2.542
posiciones a spread 0,5; 0 % a 0,6** en las cuatro vistas (COMBINED + 3 estrategias) —
consistente con que las tres solo operan por diseño a spread ≤0,5.

---

## 2. Tabla de candidatos

Columnas: **Nombre** · **Qué cambia respecto de la viva** · **Evidencia medida (cifra + fichero)**
· **Substrato** · **In-sample** · **Estado**.

Nota de nomenclatura: el catálogo v3 numera su Familia B como `B1..B7` (protección de utilidad) —
**no confundir** con los gates `B1..B4` de `risk_gates`/`b6_mask_verdicts.json` (espera post-apertura,
noticias, cap de fichas, SL mínimo). Aquí los primeros se prefijan **Cat-B#** y los segundos
**Gate-B#**.

### 2.1 Gates de riesgo ya evaluados retrospectivamente (`risk_gates`, banda 726xxx congelada)

| Nombre | Qué cambia vs. la viva | Evidencia medida | Substrato | In-sample | Estado |
|---|---|---|---|:--:|---|
| Gate-B1 @50 min (espera post-apertura fija) | Bloquea entradas <50 min tras reapertura de mercado (`gap_wait_minutes=50`) | `dropped_n=227`, `kept_net_clp=80.302.945,79`, `net_delta_clp=+40.788.967,23` (+103,23 %, **inflado por caída de base** — en CLP la mejora es +38 %), verdict `"NO VETO"` — `data/analysis/monday_audit/b6_mask_verdicts.json` (B1) | REPARADO | Sí | **Medida**. Ya materializada como `risk_gates.gap_wait_minutes=50` en `CONFIGS_CHALLENGER`, no armada |
| Gate-B2 @30 min (blackout de noticias) | Bloquea entradas ±30 min de un evento de calendario | `dropped_n=0` de 2.540 evaluables, calendario **solo NFP** (`2026-01-02T12:00`..`2028-12-01T13:00`), CPI/FOMC/PPI ausentes | REPARADO | Sí | **Medida, pero sin evidencia fuera de NFP** ("sin evidencia", no "sin problema") |
| Gate-B3 cap=7 (`max_open_fichas`) | Veta la 8ª ficha simultánea | `dropped_n=0` — el cap **es** el pico observado (`max_simultaneous_fichas=7`, §1.3); es un fusible, no un control validado (nunca mordió) | REPARADO | Sí | **Medida** (0 drops por construcción) |
| Gate-B4 = 0.50 (`min_sl_distance`) | Detector de bug (SL bajo el mínimo del bróker) | `evaluable=false` — las CSV no llevan columna SL, reconstruirla exige re-simular (fuera de alcance) | REPARADO | — | **NO EVALUABLE** — no es un candidato de estrategia, es un detector de bug; excluido del conteo de §3 |
| Los 4 gates apilados (= `CONFIGS_CHALLENGER` completo) | Señal idéntica al campeón + los 4 gates simultáneos | Consecuencia aritmética exacta (no una nueva medición): dado que B2/B3/B4 aportan `dropped_n=0` cada uno, el efecto retrospectivo del stack completo coincide con el de Gate-B1 solo — pero **esto nunca se corrió como un escenario propio combinado en un artefacto dedicado** | REPARADO (por composición aritmética de ceros, no por corrida directa) | Sí | **Medida indirectamente** — recomendable confirmar con una corrida explícita del stack antes de tratarlo como definitivo |

### 2.2 Curva de espera post-apertura B1 (peldaños N=2..6), `data/analysis/monday_audit/b1_wait_window.json`

Todas las cifras siguientes se leyeron directamente del JSON en disco (no del diff doc), sección
`curve`, vista `COMBINED`.

| Peldaño | Espera | n bloqueadas | net kept (CLP) | Δnet % vs. baseline | Substrato | In-sample | Estado |
|---|---:|---:|---:|---:|:--:|:--:|---|
| N2 | 30 min | 98 | 62.488.870,92 | +58,14 % | REPARADO | Sí | Medida |
| N3 | 45 min | 168 | 93.881.699,49 | **+137,59 %** (mejor peldaño) | REPARADO | Sí | Medida |
| N4 | 60 min | 227 | 80.302.945,79 | +103,23 % | REPARADO | Sí | Medida |
| N5 | 75 min | 317 | 75.046.755,24 | +89,92 % | REPARADO | Sí | Medida |
| N6 | 90 min | 395 | 40.847.947,90 | +3,38 % (positivo; ya no cambia de signo) | REPARADO | Sí | Medida |

Ranking `N3 > N4 > N5 > N2 > N6` (JSON `ranking_best_to_worst`, leído directo). ⚠️ Los narrativos
`docs/superpowers/research/2026-07-27-b1-wait-curve.md` y `...-b1-robustness.md` **todavía imprimen
las cifras del substrato ANTIGUO** (N3 "+32,67 %", N6 "−15,24 %", 2.347 posiciones) aunque los JSON
que dicen documentar ya fueron regenerados sobre el substrato REPARADO — es un desfase de
documentación, no de dato; ver §4. Robustez (`data/analysis/monday_audit/b1_robustness.json`,
leído directo): M1 (consistencia mensual, rung N3) 5 meses positivos / 2 negativos de 7, sin
cambio de signo vs. ANTIGUO; M2 (recorte top-K) el ranking sobrevive hasta K=5 y se rompe en K=10
(N3→N5); M3 (bloqueadas vs. mantenidas, rung N3): blocked PF 0,5918 vs. kept PF 1,0892 — lo vetado
sigue siendo peor.

### 2.3 Cola de re-validación sobre backtest largo (`docs/superpowers/specs/2026-07-27-long-backtest-queue.md`)

Las 6 entradas están, por definición del propio documento, formuladas como preguntas que **necesitan
un periodo más largo que el existente** — ninguna tiene todavía la medición que pide. Se clasifican
aquí como hipótesis/pregunta abierta (columna Estado), con la evidencia CORTA que sí existe hoy
anotada explícitamente por substrato.

| Entrada | Pregunta (resumen) | Evidencia corta disponible | Substrato de la evidencia corta | Estado |
|---|---|---|---|---|
| 1 | ¿Espera post-apertura única o por estrategia? | S7-TPNONE inestable incluso en el JSON REPARADO: N2 Δ=−648,6 %, N6 Δ=−2.885,95 % (`b1_wait_window.json`, por-estrategia); el propio doc de la cola aún cita la cifra ANTIGUA (−93,28 % en N6) | REPARADO (JSON) / ANTIGUO (texto de la cola, desactualizado) | **Hipótesis / pregunta sin la medición que pide** (falta el periodo largo) |
| 2 | ¿Se sostiene el ranking N3>N4>N2>N5 sobre periodo largo? | Ranking REPARADO ya es `N3>N4>N5>N2>N6` (cambió N2↔N5 respecto del ANTIGUO citado en la cola) | REPARADO (JSON) / ANTIGUO (texto de la cola) | **Hipótesis / pregunta sin la medición que pide** |
| 3 | ¿Se sostiene algún peldaño de la escalera de SL (Task 15) sobre periodo largo? | Ninguna — Task 15 **nunca se corrió**, ni siquiera sobre 7 meses; no existe script ni artefacto en `scripts/analysis/monday_audit/` ni `data/analysis/monday_audit/` | — | **Hipótesis, ni siquiera con dato corto** |
| 4 | ¿El filtro temporal selecciona o baraja? ("hipótesis de la lotería") | Ninguna — declarada explícitamente como hipótesis del user, no medida | — | **Hipótesis pura, explícitamente no medida** |
| 5 | ¿Sobrevive la mejora de neto una prueba de robustez sobre periodo largo? | La prueba CORTA sí corrió y está REPARADA (`b1_robustness.json`, §2.2) | REPARADO (insumo corto) | **Hipótesis / pregunta sin la medición que pide** (falta repetir sobre largo) |
| 6 | ¿Es estructural la concentración del neto en pocas operaciones, o artefacto del periodo corto? | Recalculado sobre REPARADO por R4 (`substrate-repair-diff.md` §V11, a partir de `b1_robustness.json::m2_topk_sensitivity`): quitar 3 operaciones (la mayor de cada estrategia) deja el neto en **+1.052.242 CLP**; quitar 10 por estrategia (30 ops) lo deja en **−157.907.835 CLP**; el propio texto de la cola aún cita cifras ANTIGUAS (72 %, −49,6 MM) | REPARADO (recálculo R4) / ANTIGUO (texto de la cola, desactualizado) | **Hipótesis / pregunta sin la medición que pide** (el ask es sobre periodo largo) |

### 2.4 Catálogo v3 — Familia A (instrumento y medición)

| # | Nombre | Qué cambia | Evidencia medida | Substrato | In-sample | Estado |
|---|---|---|---|---|:--:|---|
| A1 | Reparar pairing reverse+fills | N/A — **no es una variante de estrategia**, es la reparación del instrumento de medición ya aplicada (R1–R4) | Es exactamente la reparación descrita en §0; `substrate-repair-diff.md` completo | REPARADO | Sí | **Hecho** — excluido del conteo de candidatos de §3 (no es un arm) |
| A2 | Mapa MFE/MAE por posición | Nueva medición descriptiva (no cambia ninguna estrategia) | Ninguna — no se encontró script ni artefacto que calcule MFE/MAE por posición sobre el substrato real-tick | — | — | **Hipótesis sin medir** |
| A3 | Economía de la reversa (¿suman o restan las patas de reverse?) | N/A — es diagnóstico, no una variante | Medido ad-hoc por R4 (script de sesión, no persistido en artefacto commiteado): supervivencia de `reverse` en el gate de spread = 26,2 % (vs. 35,4 % media); asimetría media −555.211 CLP (reverse) vs. +62.966 CLP (resto del libro), 8,8×, signo invertido; WR de las 195 filas `reverse` = 6,15 % | REPARADO (medición no persistida en artefacto propio — declarado así en `substrate-repair-diff.md` §V14) | Sí | **Medida parcialmente** (diagnóstico, no artefacto commiteado) |
| A4 | Expectancy condicional a spread 0,50/0,60 | Filtro de spread ya operante (cap 0,5), candidato sería operar también a 0,6 | `a5_spread_gate.json`: 0 de 2.542 filas a 0,6 en las 4 vistas | REPARADO | Sí | **NO EVALUABLE** — cero muestra a 0,6; decisión del user confirma que no se operará a 0,6 |
| A5 | Experimento natural S6-vs-S7 (valor aislado del BE-1R) | Comparar S6 (sin BE) vs. S7 (BE=1R) para aislar el valor del breakeven | Dato crudo disponible: S6 net 17.859.879,00 vs. S7 net 670.122,03 (@0,67 lot, REPARADO) — pero S6 y S7 difieren simultáneamente en `ac_modulate`, `trail_atr_floor_k` Y `be_at_r`, no solo en BE | REPARADO (dato crudo, no aislado) | Sí | **Hipótesis — la comparación no aísla la variable** (no hay corrida que fije todo igual salvo BE) |

### 2.5 Catálogo v3 — Familia Cat-B (salidas y protección de utilidad)

| # | Nombre | Qué cambia respecto de la viva | Evidencia medida | Substrato | In-sample | Estado |
|---|---|---|---|---|:--:|---|
| Cat-B1 | Breakeven grid completo (S6 y S7, `be_at_r∈{off,0.25,...,2.0}` × offset {0.5,2,5} pips) | Grid nuevo y más fino que el `be_at_r` actual (S6=ninguno, S7=1.0) | Contexto previo (no la grilla propuesta): `be_at_r∈{0(off),1.0,1.5}` probado en el batch 2026-07-13 — "early breakeven costó neto in-sample" (OTRO substrato, pre-honest-fill); el valor vivo S7=1.0 nunca se aisló del bundle | OTRO (contexto) / sin medición propia | — | **Hipótesis sin medir** (grilla del catálogo nunca corrida) |
| Cat-B2 | Ratchet PX-T1 (`lock_frac∈{0.25..0.8}` + chandelier `atr_k∈{2.0,2.5,3.0}`) | Nuevo mecanismo de ratchet, no existe en la viva | Contexto previo distinto (patient-exit, ratchet trail-arm %): DSR 0,84 in-sample (21-trial family) pero **falla el holdout** en las 5 finalistas pre-comprometidas | OTRO | In-sample (y holdout que sí existió, y falló) | **Hipótesis sin medir** en la parametrización exacta del catálogo |
| Cat-B3 | Piso ATR del trail extendido (`trail_atr_floor_k∈{1.0,1.5,2.0,2.5,3.0}`) | Extiende el rango; S6=2.0/S7=1.5 ya son valores vivos (no aislados) | Los valores 1.5/2.0 son parte del bundle vivo, medidos como parte del baseline REPARADO (§1.3), nunca aislados; 3.0 nunca probado en ningún substrato | REPARADO (solo para 1.5/2.0, no aislado) / sin medición (3.0) | — | **Hipótesis sin medir** (el valor nuevo 3.0 y el aislamiento de los existentes) |
| Cat-B4 | Trailing trifásico (F1 supervivencia→BE; F2 apriete hasta `W*=L̄·(1−WR)/WR`; F3 runner con apriete por indicador) 🆕 | Reemplaza el trailing plano actual por 3 fases con umbral dinámico | Ninguna — nunca implementado. El propio catálogo da `W*≈1.9·L̄` como aproximación, no como valor exacto calculado | — | — | **Hipótesis sin medir**, y con un parámetro (`W*` exacto por estrategia) sin computar — ver §4 |
| Cat-B5 | Re-exploración TP con re-entrada acoplada (`tp_r∈{0.5..3.0}` × F1/F1+F2 × zona × política C) | TP + re-entrada combinados; la viva no tiene TP | El TP bare (sin re-entrada) fue **decisivamente refutado**: `tp_min` dañino en cada valor probado (Wave-6 Familia A), TP R-multiple rankeó bajo TPNONE en la liga honesta | OTRO (refutado, sin re-entrada) | Sí (in-sample) | **Hipótesis sin medir** en la combinación nueva (TP+reentrada); la variante SIN reentrada ya está refutada y no debe repetirse igual |
| Cat-B6 | Time-stop + agotamiento (`max_hold_bars`) — catálogo dice "sin cambios" | Ninguno nuevo respecto de lo ya evaluado | TS20/TS40 evaluados: TS40 en el tramo medio de la liga, TS20 en el tramo rechazado | OTRO | Sí (in-sample) | **Medida (en OTRO substrato)** — requiere re-medición sobre real-tick para ser comparable al baseline REPARADO |
| Cat-B7 | SuperTrend, programa propio: (a) romper always-in con 5 indicadores × 3 umbrales; (b) cierre-a-través + buffer; (c) wrapper BE/ratchet; (d) grillas `mult∈{2.0..3.5}`, `ATR period∈{7,10,14,21}` | Rompe el diseño always-in de la viva o le añade protección que hoy no tiene | Ninguna — nunca implementado ni corrido. El único punto medido es el propio baseline (`mult=3.0`, `ATR=14`, ya contado en §1.3, no es candidato) | — | — | **Hipótesis sin medir** |

### 2.6 Catálogo v3 — Familia C (políticas de re-entrada, 🆕 completa)

Ninguna de las 12 tiene implementación ni medición — el catálogo las marca como "companion
obligatorio de B, alta prioridad user", pero **PROPUESTO, pendiente de revisión**, nada corrido.

| # | Política | Grid propuesto | Evidencia | Substrato | Estado |
|---|---|---|---|---|---|
| C1 | Cooldown fijo tras stop-out en pérdida | K∈{1,2,3,5,8} barras | Ninguna | — | Hipótesis sin medir |
| C2 | Event-ificación (gate debe pasar por falso antes de re-armar) | on/off × {1,2} barras-en-falso | Ninguna | — | Hipótesis sin medir |
| C3 | Solo a mejor precio que el cierre anterior | margen {0, 0.5, 1}·ATR | Ninguna | — | Hipótesis sin medir |
| C4 | Confirmación reforzada en re-entrada (G5 3-de-3) | on/off | Ninguna | — | Hipótesis sin medir |
| C5 | Tamaño reducido en primera re-entrada | fracción {0.5, 0.33} | Ninguna | — | Hipótesis sin medir |
| C6 | Máx. re-entradas por episodio de señal | {1,2,3,∞} | Ninguna | — | Hipótesis sin medir |
| C7 | Condicional a MFE de la pata cerrada | X∈{0.25,0.5,1.0}·R | Ninguna | — | Hipótesis sin medir |
| C8 | SAR-reset (flipea en contra y de vuelta) | on/off × TF del SAR (TF no especificado — ver §4) | Ninguna | — | Hipótesis sin medir |
| C9 | Bloqueo por zona consumida | on/off (acoplado a D2) | Ninguna | — | Hipótesis sin medir |
| C10 | Tiempo-O-distancia | combinaciones C1×C3 | Ninguna | — | Hipótesis sin medir |
| C11 | Asimétrica por tipo de cierre | mapa tipo→política (mapa no especificado — ver §4) | Ninguna | — | Hipótesis sin medir |
| C12 | Presupuesto de pérdida por episodio | Z∈{1.5,2,3}·R | Ninguna | — | Hipótesis sin medir |

Contexto relevante (no una fila C1-C12, un kwarg inerte del motor ya existente): `reentry_enable` /
`reentry_max=2` (V-13) fue medido en el batch 2026-07-13 ("re-entry fue el único lever sin downside
en ningún TF"), pero con semántica **invertida** (solo re-entra tras un trail-out completo, no tras
un stop-out) y sobre el motor **pre-honest-fill** (in-sample, potencialmente contaminado por el
mismo sesgo de same-bar fill que infló todo el batch program). Sustrato **OTRO**, no comparable
directamente a ninguna de las C1-C12 tal como están definidas hoy.

### 2.7 Catálogo v3 — Familia D (entradas, contexto, zonas)

| # | Nombre | Qué cambia | Evidencia medida | Substrato | In-sample | Estado |
|---|---|---|---|---|:--:|---|
| D1a | Multi-TF inferior — gate binario (SAR 1m/2m/5m alineado con M15, k-de-m) | Añade gate de alineación multi-TF | Ninguna | — | — | Hipótesis sin medir |
| D1b | Multi-TF inferior — score graduado (nº TFs alineados como nota, no veto) | Añade sizing/score, no veto | Ninguna | — | — | Hipótesis sin medir |
| D1c | Multi-TF inferior — micro-timing (M15 arma, ejecución espera confirmación 1m/5m) | Cambia el timing de entrada | Ninguna | — | — | Hipótesis sin medir |
| D1d | Multi-TF inferior — frescura del flip (reciente vs. maduro) | Añade condición de frescura | Ninguna | — | — | Hipótesis sin medir |
| D1e | Multi-TF inferior — variantes de indicador (SuperTrend o AO/AC en 5m) | Cambia el indicador del TF inferior | Ninguna | — | — | Hipótesis sin medir |
| D1f | Índice de coherencia 1m→H1 | Combina D1a-e en un score único | Ninguna | — | — | Hipótesis sin medir |
| D2 | Zonas de compra/venta (6 métodos: números redondos, swings, pivotes, volume profile, VWAP, extremos previos) + knobs de distancia/firmeza | Añade filtro de proximidad a zona, "nunca backtesteado localmente" | Solo evidencia de **literatura externa**, no de este codebase (Osler 2000/2003 🟢 para números redondos y swings; VWAP/Volume-Profile 🟠 "descartar reglas de folklore") — `2026-07-22-FINAL-experiment-matrix.md` §3 lo declara explícitamente "white-space puro" | Sin medición local (literatura externa) | — | **Hipótesis sin medir localmente** |
| D3 | Contexto temporal/régimen: hora/día, asimetría L/S, spread-regime, régimen ATR14-percentil | Añade filtro de hora, dirección o régimen | Mixto, 4 piezas: (1) hora/día — V-11 `blocked_hours` probado, "flagged as overfit-by-construction" (fit y evaluado en la misma ventana), nunca revalidado; (2) asimetría L/S — V-14 solo-long probado, "no exploitable asymmetry found"; (3) spread-regime — ya cubierto en A4, NO EVALUABLE; (4) régimen ATR14-percentil (P32) — **medido y refutado**: Sharpe gateado colapsa (DSR 0,0405/p=0,9595 del mejor gated) vs. Sharpe ungated | (1)(2)(4) OTRO · (3) REPARADO (no evaluable) | Sí | **Medida en OTRO substrato (mayormente negativa/refutada) + no evaluable en REPARADO (spread)** — requiere re-medición sobre real-tick |

### 2.8 Catálogo v3 — Familia E (estructura y recombinación, 🔒 gateada — no arranca hasta terminar las demás)

| # | Nombre | Qué cambia | Evidencia medida | Substrato | In-sample | Estado |
|---|---|---|---|---|:--:|---|
| E1 | Escalera de fichas diferenciada (F1/F2/F3 con parámetros propios, hoy son clones) | Hoy las 3 fichas de S6/S7 comparten init_sl/trail/BE idénticos — verificado en código | El pariente más cercano (`active_fichas` F1/F2, contar 1 vs. 2 vs. 3 fichas) solo prueba SOLTAR fichas, no diferenciar sus parámetros — gap explícito documentado en `prior-experiments-audit.md` §6 | OTRO (para el pariente, no para esta propuesta) | — | **Hipótesis sin medir** (la propuesta exacta nunca se corrió) |
| E2 | S6+S7 como una sola estrategia de 6 fichas | Fusiona dos configs en una | Motivada por la correlación medida S6\|S7=+0,7669 (REPARADO, §1.3), pero la fusión en sí **nunca se implementó ni se corrió** | REPARADO (solo la correlación que la motiva) | — | **Hipótesis sin medir** |
| E3 | `stop_and_reverse` como lever on/off | El estado "on" es el vivo actual (medido); "off" es el contrafactual | "On" es el baseline medido (§1.3, incluye las 195 filas `reverse`, −108.266.105,49 CLP dentro del neto de 39,5 MM). El contrafactual "off" (qué habría pasado sin reversión, hasta stop/trailing) **no existe en ningún artefacto** — declarado explícitamente en `substrate-repair-diff.md` §V16.1 | REPARADO (solo el "on"; el "off" no existe) | Sí (para "on") | **"On" medida; "off" hipótesis sin medir** |
| E4 | Piramidación ⭐ | Añadir posiciones a favor sobre una ganadora corriendo | Ninguna — el propio catálogo dice que "requiere la información de casi todo el plan" antes de empezar | — | — | **Hipótesis sin medir**, explícitamente gateada al final |

---

## 3. Los tres cubos

Se excluyen del conteo (no son candidatos de estrategia comparables al baseline, son artefactos
estructurales o el propio instrumento): **A1** (reparación del instrumento, ya hecha) y **Gate-B4**
(detector de bug, sin alternativa que probar). El resto de filas de §2 se reparte así:

### (a) Medido sobre substrato REPARADO — **9 candidatos/filas**

Gate-B1@50min · Gate-B2@30min (news, cobertura parcial) · Gate-B3 cap=7 · el stack combinado de
los 4 gates (por composición aritmética de ceros) · B1 N2 · B1 N3 · B1 N4 · B1 N5 · B1 N6 · A3
(economía de la reversa, diagnóstico no persistido en artefacto propio).

*(Nota: son 10 elementos listados arriba porque el "stack combinado" se cuenta aparte del Gate-B1
individual — 5 rungs B1 + Gate-B1 + Gate-B2 + Gate-B3 + stack combinado + A3 = 10. Se reporta como
9 candidatos "puros" de estrategia si el stack combinado se considera una re-expresión de Gate-B1 y
no un elemento nuevo; ver el detalle exacto fila por fila en §2.1–§2.4 en vez de fiarse solo de este
conteo resumido.)*

Las 6 entradas de la cola de backtest largo **no** entran aquí como "medidas": por diseño, cada una
pide explícitamente el dato de periodo largo que no existe (§2.3) — entran en el cubo (c). Su
evidencia CORTA de apoyo sí está sobre REPARADO en 4 de las 6 (entradas 1, 2, 5, 6), y eso se
declara en la tabla de §2.3, pero la entrada en sí sigue sin la medición que pide.

### (b) Medido solo sobre el substrato ANTIGUO (real-tick pre-reparación) — **0 candidatos**

**Hallazgo explícito:** no se encontró ningún candidato de estrategia cuya única medición sobreviva
exclusivamente en `data/analysis/pre_repair_snapshot/` sin una contraparte ya regenerada en el
substrato REPARADO. La reparación (R3) regeneró los 8 JSON de `monday_audit/` completos, así que
todo lo que antes solo existía en el substrato antiguo (curva B1, robustez, máscaras, atribución
por motivo, maxDD, correlaciones) **ya tiene versión REPARADA en disco**, confirmada leyendo los
JSON directamente para este documento. Lo que sí sobrevive desactualizado es la **prosa narrativa**
de `2026-07-27-b1-wait-curve.md`, `2026-07-27-b1-robustness.md` y el propio
`2026-07-27-long-backtest-queue.md` (entradas 1, 2, 6), que siguen imprimiendo las cifras viejas en
su texto aunque los JSON que describen ya cambiaron — esto es un **hueco de documentación**, no un
candidato de estrategia medido-solo-en-antiguo; se registra en §4.

### (c) Hipótesis nunca medida — **37 candidatos/filas**

6 entradas de la cola (todas, por diseño — §2.3) + A2 + A5 (Familia A) + Cat-B1, Cat-B2, Cat-B3
(valor 3.0), Cat-B4, Cat-B5 (combinación TP+reentrada) y Cat-B7 (Familia Cat-B, 6 de 7 — Cat-B6
tiene evidencia OTRO, ver abajo) + C1..C12 (Familia C, 12) + D1a..D1f y D2 (Familia D, 7) + E1, E2,
E3-"off", E4 (Familia E, 4).
= 6 + 2 + 6 + 12 + 7 + 4 = **37**.

### (d) — cuarta categoría no pedida explícitamente pero necesaria por honestidad de substrato: medido sobre **OTRO** substrato (ni REPARADO ni ANTIGUO real-tick) — **3 candidatos directos** (más contexto en varias filas de (c))

Cat-B6 (time-stop, TS20/TS40) · D3 (hora/día V-11, asimetría L/S V-14, régimen ATR14-percentil P32
— 3 piezas dentro de una fila) · el kwarg inerte `reentry_enable`/V-13 (mencionado como contexto de
la Familia C, no una fila C1-C12 propia). Estos **también requieren re-medición** antes de entrar
al backtest largo junto a las tres vivas — están en un motor de backtest distinto (`sentinel_engine`
honest-fill, ventanas IW/W1/W2/W3), no en la reconstrucción real-tick de 7 meses.

### Resumen numérico (respuesta directa a los tres cubos pedidos)

| Cubo | Conteo |
|---|---:|
| (a) Medido sobre substrato REPARADO | **9** (10 filas si se cuenta el stack de gates aparte de Gate-B1; ver nota en §3(a)) |
| (b) Medido solo sobre substrato ANTIGUO | **0** (ningún candidato quedó exclusivamente en el snapshot congelado; sí hay documentación narrativa desactualizada, ver §4) |
| (c) Hipótesis nunca medida | **37** |
| *(d) medido sobre OTRO substrato, ni reparado ni antiguo — informativo, no pedido explícitamente* | *3 filas directas + contexto en ~8 filas adicionales de (c)* |

---

## 4. Huecos — candidatos sin definición suficiente para implementarse sin ambigüedad

1. **Cat-B4 (trailing trifásico): falta el valor exacto de `W*` por estrategia.** El catálogo da
   `W* = L̄·(1−WR)/WR` como fórmula y dice "hoy ≈1.9·L̄" — una aproximación, no un número calculado
   sobre el substrato REPARADO. No existe ningún artefacto que calcule `L̄`/`WR` por estrategia con
   esta fórmula exacta. **Pregunta abierta:** ¿cuál es el valor numérico exacto de `W*` para
   S6-K2P0, S7-TPNONE y SuperTrend-p14x3-M15 sobre las 2.542 posiciones reparadas?
2. **C8 (SAR-reset): el TF del SAR de referencia no está especificado.** El grid dice "on/off × TF
   del SAR" sin listar los TF candidatos (¿M15 igual que la entrada? ¿un TF inferior como en D1?).
3. **C11 (asimétrica por tipo de cierre): el "mapa tipo→política" no está enumerado.** No hay lista
   cerrada de qué política corresponde a qué tipo de cierre (post-BE libre / post-pérdida gateada
   son los únicos dos ejemplos dados, sin cerrar si hay más tipos).
4. **Entrada 3 de la cola (escalera de distancia de SL, Task 15): no existen los peldaños.** Ni el
   plan, ni el tracker, ni ningún script en `scripts/analysis/monday_audit/` especifican los valores
   concretos de distancia de SL a barrer — la tarea está nombrada pero no parametrizada.
5. **D2 (zonas): "la unidad de distancia correcta es un hallazgo", declarado así en el propio
   catálogo.** No hay una unidad fijada (R, ATR o múltiplos de spread) para ninguno de los 6
   métodos ni para el knob central "distancia a barrera opuesta".
6. **Cat-B7(a): los 3 umbrales por indicador no están dados.** El catálogo nombra 5 indicadores
   (flip-count, ADX(14), distancia/ATR, Choppiness(14), pendiente LR(20)) "cada una × 3 umbrales"
   sin listar los valores de esos umbrales.
7. **El stack combinado de los 4 `risk_gates` (§2.1, última fila) nunca se corrió como escenario
   propio.** Se infiere aritméticamente que equivale a Gate-B1 solo (porque B2/B3/B4 aportan 0
   drops), pero nadie ha corrido ese artefacto específico para confirmarlo directamente.
8. **Desfase de documentación (no un hueco de definición, pero bloquea lectura honesta):**
   `2026-07-27-b1-wait-curve.md`, `2026-07-27-b1-robustness.md` y
   `2026-07-27-long-backtest-queue.md` (entradas 1, 2, 6) imprimen cifras del substrato ANTIGUO en
   su prosa aunque los JSON subyacentes ya están reparados — quien diseñe el backtest largo debe
   usar los JSON de `data/analysis/monday_audit/`, no la prosa de esos tres documentos, hasta que se
   actualicen.
9. **Per-estrategia a 0,1 lot (tamaño real vivo): NO DISPONIBLE.** Solo existe el combinado
   (`a1_maxdd.json`); ningún artefacto desglosa maxDD/net por estrategia al lote realmente
   desplegado hoy.
