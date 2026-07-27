# Substrate repair — diff numérico Antes/Después (Task R3)

**Fecha:** 2026-07-27. **Ejecutor:** Sonnet 5 high effort (Task R3). **Rol de este documento:**
tabla de cifras Antes/Después/Δ. **No contiene interpretación, veredictos ni recomendaciones** —
eso lo escribe R4 (Opus 5 high) en una sección `§Veredictos` separada que este documento no
incluye.

**Fuente de los valores "Antes":** `data/analysis/pre_repair_snapshot/` (commit `b3c53e2`),
árbol inmutable verificado byte-a-byte contra `MANIFEST.json` antes de regenerar (ver
task-R3-report.md §1). **Fuente de los valores "Después":** regeneración de
`data/analysis/realtick_bt/` y `data/analysis/monday_audit/` corrida en esta tarea
(`python scripts/analysis/realtick_bt/backtest.py` seguido de los 6 módulos de Track A, en orden).

**Convención numérica:** las tablas que citan directamente un campo JSON reproducen el valor
`float` del JSON verbatim (punto decimal, sin separador de miles). Las tablas que provienen del
reporte markdown mensual reproducen el formato ahí usado (punto de miles, coma decimal en
prosa — aquí se usa punto de miles y punto decimal para evitar ambigüedad de columna). Δ = 
Después − Antes en todos los casos, mismo signo que esa resta.

---

## 1. `n_posiciones` por estrategia y total; neto total CLP

| Métrica | Antes | Después | Δ |
|---|---:|---:|---:|
| n S6-K2P0 | 912 | 1053 | +141 |
| n S7-TPNONE | 1167 | 1221 | +54 |
| n SuperTrend-p14x3-M15 | 268 | 268 | 0 |
| **n TOTAL** | **2347** | **2542** | **+195** |
| net S6-K2P0 (CLP, 0.67 lot) | 93,630,717.42 | 17,859,879.00 | −75,770,838.42 |
| net S7-TPNONE (CLP, 0.67 lot) | 33,165,389.10 | 670,122.03 | −32,495,267.07 |
| net SuperTrend-p14x3-M15 (CLP, 0.67 lot) | 20,983,977.53 | 20,983,977.53 | 0.00 |
| **net TOTAL (CLP, 0.67 lot)** | **147,780,084.05** | **39,513,978.56** | **−108,266,105.49** |

Fuente Antes: `pre_repair_snapshot/MANIFEST.json` (`summary.*.n_rows`, `summary.*.net_067lot_clp_sum`,
`combined.n_rows_total`, `combined.net_067lot_clp_sum_total`). Fuente Después: suma directa de
las 3 CSV `data/analysis/realtick_bt/positions_*.csv` regeneradas, cruzada contra
`data/analysis/monday_audit/a5_spread_gate.json` (`COMBINED.at_0.5` / `unfiltered`, idénticos entre sí).

---

## 2. A1 — `a1_maxdd.json`

| Métrica | Antes | Después | Δ |
|---|---:|---:|---:|
| n_positions | 2347 | 2542 | +195 |
| lot | 0.1 | 0.1 | 0 |
| account_balance_clp | 59,600,000.0 | 59,600,000.0 | 0.0 |
| final_net_clp | 22,056,728.962686684 | 5,897,608.740298494 | −16,159,120.2224 |
| max_dd_clp | 17,028,660.47014925 | 19,276,260.47014925 | +2,247,600.00 |
| max_dd_pct_of_initial | 28.571577970049077 | 32.34271890964639 | +3.771141 |
| max_dd_pct_of_peak_equity | 20.381434165018078 | 25.072685357159106 | +4.691251 |
| peak_equity_clp | 23,949,863.725373156 | 17,281,515.464179117 | −6,668,348.2612 |
| trough_equity_clp | 6,921,203.255223909 | −1,994,745.0059701323 | −8,915,948.2612 |
| t_peak | 2026-03-23 05:32:53.365000 | 2026-03-23 05:32:53.365000 | idéntico |
| t_trough | 2026-04-29 01:57:51.943000 | 2026-04-29 01:57:51.943000 | idéntico |

Nota mecánica: `max_dd_clp`/`peak_equity_clp`/etc. de A1 están a **lot=0.1** sobre una cuenta
virtual combinada — cifra distinta de base (lote) a la de §1 y §10, que están a 0.67/ficha. No
se mezclan en este documento.

---

## 3. A2 — `a2_overlap.json`

| Métrica | Antes | Después | Δ |
|---|---:|---:|---:|
| **`max_simultaneous_fichas` (cap B3)** | **7** | **7** | **0** |
| p95_simultaneous | 7 | 7 | 0 |
| p99_simultaneous | 7 | 7 | 0 |
| n_positions | 2347 | 2542 | +195 |
| n_trading_days | 163 | 163 | 0 |
| corr S6-K2P0\|S7-TPNONE | 0.7596348811562712 | 0.766939289193862 | +0.007304 |
| corr S6-K2P0\|SuperTrend-p14x3-M15 | 0.3519621016914237 | 0.3556340205290167 | +0.003672 |
| corr S7-TPNONE\|SuperTrend-p14x3-M15 | 0.14090690766147587 | 0.15349823894193204 | +0.012591 |
| pct_time_with_any_position | 92.7993182786536 | 93.29268292682927 | +0.493365 |

`simultaneous_histogram` (conteo de barras con N posiciones simultáneas, 0..7):

| N simultáneas | Antes | Después | Δ |
|---:|---:|---:|---:|
| 0 | 338 | 341 | +3 |
| 1 | 683 | 703 | +20 |
| 2 | 690 | 724 | +34 |
| 3 | 701 | 743 | +42 |
| 4 | 704 | 777 | +73 |
| 5 | 696 | 792 | +96 |
| 6 | 615 | 700 | +85 |
| 7 | 267 | 304 | +37 |

🔴 **`max_simultaneous_fichas` = 7 en ambos casos, sin cambio.** Este valor es el que está
desplegado como `max_simultaneous_fichas` en `a2_overlap.json` y se lee para el cap del roster
retador vivo (`CONFIGS_CHALLENGER`, magics 726xxx). No se tocó ningún `.py` ni el roster; se deja
constancia de que la regeneración no lo modificó.

---

## 4. A3 — `a3_exit_reason.json` (por estrategia × reason: n / net / WR / mean)

| Estrategia | Reason | n Antes | n Después | Δn | net Antes (CLP) | net Después (CLP) | Δnet | WR% Antes | WR% Después | ΔWR | mean Antes | mean Después | Δmean |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S6-K2P0 | EXIT_INITSL | 891 | 12 | NO COMPARABLE (ver nota) | 89,679,633.30 | −11,352,543.30 | NO COMPARABLE | 36.026936 | 0.0 | NO COMPARABLE | 100,650.542424 | −946,045.275 | NO COMPARABLE |
| S6-K2P0 | EXIT_SL_RAISED | — | 879 | (nuevo) | — | 101,032,176.60 | (nuevo) | — | 36.51877133105802 | (nuevo) | — | 114,939.90511945394 | (nuevo) |
| S6-K2P0 | EXIT_TRAIL | 21 | 21 | 0 | 3,951,084.12 | 3,951,084.12 | 0.00 | 57.142857142857146 | 57.142857142857146 | 0 | 188,146.86285714275 | 188,146.86285714275 | 0.00 |
| S6-K2P0 | reverse | — | 141 | (nuevo) | — | −75,770,838.42 | (nuevo) | — | 6.382978723404255 | (nuevo) | — | −537,381.8327659573 | (nuevo) |
| S7-TPNONE | EXIT_INITSL | 1104 | 3 | NO COMPARABLE (ver nota) | 24,555,451.50 | −3,514,375.47 | NO COMPARABLE | 34.78260869565217 | 0.0 | NO COMPARABLE | 22,242.25679347827 | −1,171,458.49 | NO COMPARABLE |
| S7-TPNONE | EXIT_SL_RAISED | — | 1101 | (nuevo) | — | 28,069,826.97 | (nuevo) | — | 34.87738419618529 | (nuevo) | — | 25,494.847384196193 | (nuevo) |
| S7-TPNONE | EXIT_TRAIL | 63 | 63 | 0 | 8,609,937.60 | 8,609,937.60 | 0.00 | 47.61904761904762 | 47.61904761904762 | 0 | 136,665.67619047602 | 136,665.67619047602 | 0.00 |
| S7-TPNONE | reverse | — | 54 | (nuevo) | — | −32,495,267.07 | (nuevo) | — | 5.555555555555555 | (nuevo) | — | −601,764.2050000002 | (nuevo) |
| SuperTrend-p14x3-M15 | EXIT_STLINE | 268 | 268 | 0 | 20,983,977.53 | 20,983,977.53 | 0.00 | 22.761194029850746 | 22.761194029850746 | 0 | 78,298.42361940292 | 78,298.42361940292 | 0.00 |

**Nota mecánica sobre el grupo `EXIT_INITSL` (NO COMPARABLE directo):** el bucket `EXIT_INITSL`
"Antes" agregaba dos poblaciones que "Después" quedan separadas en dos grupos (`EXIT_INITSL`
genuino + `EXIT_SL_RAISED`). Verificación aritmética: S6-K2P0 12 + 879 = 891 (= n Antes exacto);
S7-TPNONE 3 + 1101 = 1104 (= n Antes exacto). Ídem en net: S6-K2P0 −11,352,543.30 + 101,032,176.60
= 89,679,633.30 (= net Antes exacto); S7-TPNONE −3,514,375.47 + 28,069,826.97 = 24,555,451.50
(= net Antes exacto). El desglose fino (genuina vs. levantada) está en la fila de detalle del
§11 (Step 4).

---

## 5. A4 — `a4_serial.json` (autocorrelación lag 1..5 y rachas)

| Estrategia | Métrica | Antes | Después | Δ |
|---|---|---:|---:|---:|
| S6-K2P0 | n | 912 | 1053 | +141 |
| S6-K2P0 | lag_1 | 0.6353165547512026 | 0.6366126584724346 | +0.001296 |
| S6-K2P0 | lag_2 | 0.2705813740843275 | 0.2731532853965226 | +0.002572 |
| S6-K2P0 | lag_3 | −0.0942057238666762 | −0.09037834661506333 | +0.003827 |
| S6-K2P0 | lag_4 | 0.0013890953563384235 | 0.00016703228962282944 | −0.001222 |
| S6-K2P0 | lag_5 | 0.09700502169530927 | 0.09072610510610758 | −0.006279 |
| S6-K2P0 | longest_loss_streak | 27 | 30 | +3 |
| S6-K2P0 | longest_win_streak | 15 | 15 | 0 |
| S7-TPNONE | n | 1167 | 1221 | +54 |
| S7-TPNONE | lag_1 | 0.6553907897179876 | 0.6543826201212153 | −0.001008 |
| S7-TPNONE | lag_2 | 0.3106195071249636 | 0.30859191715785095 | −0.002028 |
| S7-TPNONE | lag_3 | −0.03431438123086481 | −0.037372667669141296 | −0.003058 |
| S7-TPNONE | lag_4 | −0.014355035781218736 | −0.014473986007371884 | −0.000119 |
| S7-TPNONE | lag_5 | 0.005606334085392303 | 0.008426665431926104 | +0.002820 |
| S7-TPNONE | longest_loss_streak | 42 | 42 | 0 |
| S7-TPNONE | longest_win_streak | 15 | 15 | 0 |
| SuperTrend-p14x3-M15 | n | 268 | 268 | 0 |
| SuperTrend-p14x3-M15 | lag_1..lag_5 | (−0.0627042082681346, −0.0023502567385760556, 0.08856368592434817, −0.1307536795657291, 0.20978363165200695) | idéntico | 0 en las 5 |
| SuperTrend-p14x3-M15 | longest_loss_streak / longest_win_streak | 13 / 4 | idéntico | 0 / 0 |

---

## 6. A5 — `a5_spread_gate.json` (conteos @0.5 / @0.6 / unfiltered)

| Ámbito | Bucket | n Antes | n Después | Δn | net Antes (CLP) | net Después (CLP) | Δnet | WR% Antes | WR% Después | ΔWR | PF Antes | PF Después | ΔPF |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| COMBINED | at_0.5 | 2347 | 2542 | +195 | 147,780,084.05000013 | 39,513,978.55999998 | −108,266,105.49 | 34.42692799318279 | 32.25806451612903 | −2.168863 | 1.1381425715686073 | 1.0333414336908222 | −0.104801 |
| COMBINED | at_0.6 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0 |
| COMBINED | unfiltered | 2347 | 2542 | +195 | 147,780,084.05000013 | 39,513,978.55999998 | −108,266,105.49 | 34.42692799318279 | 32.25806451612903 | −2.168863 | 1.1381425715686073 | 1.0333414336908222 | −0.104801 |
| S6-K2P0 | at_0.5 = unfiltered | 912 | 1053 | +141 | 93,630,717.41999993 | 17,859,879.00000002 | −75,770,838.42 | 36.51315789473684 | 32.47863247863248 | −4.034525 | 1.2067622447059316 | 1.0333561846186718 | −0.173406 |
| S6-K2P0 | at_0.6 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0 |
| S7-TPNONE | at_0.5 = unfiltered | 1167 | 1221 | +54 | 33,165,389.100000046 | 670,122.0299999483 | −32,495,267.07 | 35.47557840616967 | 34.152334152334156 | −1.323244 | 1.0706169517886435 | 1.0013337581168495 | −0.069283 |
| S7-TPNONE | at_0.6 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0 |
| SuperTrend-p14x3-M15 | at_0.5 = unfiltered | 268 | 268 | 0 | 20,983,977.529999983 | 20,983,977.529999983 | 0.00 | 22.761194029850746 | 22.761194029850746 | 0 | 1.142485865305544 | 1.142485865305544 | 0 |
| SuperTrend-p14x3-M15 | at_0.6 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 0 |

---

## 7. B6 — `b6_mask_verdicts.json`

| Mask | Métrica | Antes | Después | Δ |
|---|---|---:|---:|---:|
| B1 | dropped_n | 209 | 227 | +18 |
| B1 | kept_n | 2138 | 2315 | +177 |
| B1 | kept_net_clp | 177,357,685.36999962 | 80,302,945.78999996 | −97,054,739.58 |
| B1 | net_delta_clp | 29,577,601.319999486 | 40,788,967.22999998 | +11,211,365.91 |
| B1 | net_delta_pct | 20.014605831454364 | 103.22667753656847 | +83.212072 |
| B1 | total_net_clp | 147,780,084.05000013 | 39,513,978.55999998 | −108,266,105.49 |
| B1 | wait_minutes | 50 | 50 | 0 |
| B1 | n_reopens | 145 | 145 | 0 |
| B1 | verdict (texto) | "NO VETO -- the gap-wait gate was not catastrophic over the 7-month substrate" | idéntico | idéntico |
| B2 | dropped_n | 0 | 0 | 0 |
| B2 | kept_n | 2345 | 2540 | +195 |
| B2 | kept_net_clp | 146,170,661.9800002 | 37,904,556.49000005 | −108,266,105.49 |
| B2 | total_net_clp | 146,170,661.9800002 | 37,904,556.49000005 | −108,266,105.49 |
| B2 | calendar_range | 2026-01-02T12:00:00 .. 2028-12-01T13:00:00 | idéntico | idéntico |
| B3 | cap | 7 | 7 | 0 |
| B3 | dropped_n | 0 | 0 | 0 |
| B3 | expected (texto) | "ZERO drops -- the cap IS the observed peak, so it never bit" | idéntico | idéntico |
| B4 | evaluable | false | false | sin cambio |
| B4 | verdict (texto) | "NOT MASKABLE -- B4 is a live BUG DETECTOR, not a filter" | idéntico | idéntico |

Nota mecánica B2: `kept_n` = 2345 (Antes) / 2540 (Después) — ambos son exactamente `n_total − 2`
(2347−2=2345; 2542−2=2540). El método de B2 solo evalúa posiciones dentro del `calendar_range`
cubierto; 2 posiciones caen fuera de ese rango en ambos casos (`dropped_n=0` cuenta solo vetos
dentro del rango cubierto, no las 2 fuera de rango).

---

## 8. B1 curva — `b1_wait_window.json` (peldaños N=2..6, COMBINED)

| Rung | wait_min | net Antes (CLP) | net Después (CLP) | Δnet | %Δ Antes | %Δ Después | Δ(%Δ) | n_blocked Antes | n_blocked Después | Δ | n_kept Antes | n_kept Después | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N2 | 30 | 167,393,072.5500001 | 62,488,870.92000005 | −104,904,201.63 | 13.271739981798957 | 58.143708118669586 | +44.871968 | 92 | 98 | +6 | 2255 | 2444 | +189 |
| N3 | 45 | 196,052,707.13999993 | 93,881,699.49000025 | −102,171,007.65 | 32.6651750134796 | 137.59110803647786 | +104.925933 | 159 | 168 | +9 | 2188 | 2374 | +186 |
| N4 | 60 | 177,357,685.36999962 | 80,302,945.78999996 | −97,054,739.58 | 20.014605831454364 | 103.22667753656847 | +83.212072 | 209 | 227 | +18 | 2138 | 2315 | +177 |
| N5 | 75 | 162,151,313.39999977 | 75,046,755.23999973 | −87,104,558.16 | 9.724740273619856 | 89.92457346719723 | +80.199833 | 293 | 317 | +24 | 2054 | 2225 | +171 |
| N6 | 90 | 125,260,724.08000012 | 40,847,947.900000066 | −84,412,776.18 | −15.238426825079339 | 3.37594286531922 | +18.61437 | 362 | 395 | +33 | 1985 | 2147 | +162 |
| baseline | 0 | 147,780,084.05000013 | 39,513,978.55999998 | −108,266,105.49 | 0 | 0 | 0 | 0 | 0 | 0 | 2347 | 2542 | +195 |

`ranking_best_to_worst` (por `delta_pct`, orden completo tal cual el JSON):

| Puesto | Antes: rung (Δ%) | Después: rung (Δ%) |
|---|---|---|
| 1 | N3 (+32.6651750134796%) | N3 (+137.59110803647786%) |
| 2 | N4 (+20.014605831454364%) | N4 (+103.22667753656847%) |
| 3 | N2 (+13.271739981798957%) | N5 (+89.92457346719723%) |
| 4 | N5 (+9.724740273619856%) | N2 (+58.143708118669586%) |
| 5 | N6 (−15.238426825079339%) | N6 (+3.37594286531922%) |

Δ de orden (posiciones 3 y 4): Antes = [N3,N4,**N2**,**N5**,N6]; Después = [N3,N4,**N5**,**N2**,N6]
(N2 y N5 intercambian puesto 3↔4; N1 y N6 en los mismos extremos; N6 pasa de único signo negativo
Antes a positivo Después).

---

## 9. B1 robustez — `b1_robustness.json`

### 9.1 M1 — consistencia mensual de signo (COMBINED), meses positivos/negativos/cero de 7

| Rung | pos Antes | neg Antes | pos Después | neg Después | Δpos | Δneg |
|---|---:|---:|---:|---:|---:|---:|
| N2 | 3 | 4 | 3 | 4 | 0 | 0 |
| N3 | 5 | 2 | 5 | 2 | 0 | 0 |
| N4 | 4 | 3 | 4 | 3 | 0 | 0 |
| N5 | 3 | 4 | 4 | 3 | +1 | −1 |
| N6 | 4 | 3 | 5 | 2 | +1 | −1 |

(`n_months_zero` = 0 en los 10 casos, Antes y Después; `n_months_total` = 7 en todos.)

### 9.2 M2 — sensibilidad top-K (recorte GLOBAL, ranking COMBINED)

| K | best Antes | delta_pct del best, Antes (%) | orden completo Antes | best Después | delta_pct del best, Después (%) | orden completo Después |
|---:|---|---:|---|---|---:|---|
| 1 | N3 | 38.90 | [N3, N4, N2, N5, N6] | N3 | 343.61 | [N3, N4, N5, N2, N6] |
| 3 | N3 | 47.93 | [N3, N4, N2, N5, N6] | N3 | −719.37 | [N3, N4, N5, N2, N6] |
| 5 | N3 | 58.69 | [N3, N4, N2, N5, N6] | N3 | −208.94 | [N3, N4, N5, N2, N6] |
| 10 | N3 | 115.65 | [N3, N5, N4, N2, N6] | N5 | −89.55 | [N5, N3, N4, N6, N2] |

Nota: las columnas "delta_pct del best" de esta subsección son el propio valor de
`ranking[0].delta_pct` (Antes y Después por separado, no una resta entre ambos), leído de
`m2_topk_sensitivity.global.K{k}` — distinto del `Δ%` sin recorte de §8.

🔴 En K=10, el rung con mejor `delta_pct` cambia de N3 (Antes) a N5 (Después); en K=1/3/5 se
mantiene N3 en ambos casos, aunque su `delta_pct` cambia de signo/magnitud en K=3 y K=5.

### 9.3 M3 — perfil bloqueadas vs. mantenidas (COMBINED, rung N3)

| Grupo | Métrica | Antes | Después | Δ |
|---|---|---:|---:|---:|
| blocked | n | 159 | 168 | +9 |
| blocked | mean_clp | −303,601.40308176115 | −323,617.38648809545 | −20,015.9834 |
| blocked | median_clp | −454,904.88 | −499,454.18 | −44,549.30 |
| blocked | win_rate | 29.559748427672957 | 27.976190476190474 | −1.583558 |
| blocked | sum_clp | −48,272,623.09000002 | −54,367,720.93000004 | −6,095,097.84 |
| blocked | profit_factor | 0.6201840469838353 | 0.5918028918361417 | −0.028381 |
| blocked | max_loss | −5,632,663.54 | −5,632,663.54 | 0.00 |
| blocked | max_win | 5,018,385.09 | 5,018,385.09 | 0.00 |
| kept | n | 2188 | 2374 | +186 |
| kept | mean_clp | 89,603.61386654475 | 39,545.78748525705 | −50,057.8264 |
| kept | median_clp | −262,276.19 | −303,688.22 | −41,412.03 |
| kept | win_rate | 34.78062157221206 | 32.56107834877843 | −2.219543 |
| kept | sum_clp | 196,052,707.13999993 | 93,881,699.49000025 | −102,171,007.65 |
| kept | profit_factor | 1.207975926256012 | 1.0892461233713904 | −0.11873 |
| kept | max_loss | −6,314,079.66 | −6,314,079.66 | 0.00 |
| kept | max_win | 23,691,445.89 | 23,691,445.89 | 0.00 |

---

## 10. Grilla mensual del reporte markdown (lote 0.67/ficha, gate 0.5)

### 10.1 COMBINED (3 estrategias)

| Mes | n Antes | n Después | Δn | net Antes (CLP) | net Después (CLP) | Δnet | WR% Antes | WR% Después | ΔWR | PF Antes | PF Después | ΔPF | maxDD Antes (CLP) | maxDD Después (CLP) | ΔmaxDD | RoM% Antes | RoM% Después | ΔRoM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-01 | 222 | 258 | +36 | 87,475,384 | 66,714,780 | −20,760,604 | 34.68 | 29.84 | −4.84 | 2.06 | 1.64 | −0.42 | 27,159,390 | 43,618,789 | +16,459,399 | 360.83 | 161.34 | −199.49 |
| 2026-02 | 319 | 343 | +24 | 12,048,391 | 4,695,873 | −7,352,518 | 32.60 | 32.07 | −0.53 | 1.05 | 1.02 | −0.03 | 82,222,331 | 83,442,103 | +1,219,772 | 52.57 | 11.11 | −41.46 |
| 2026-03 | 297 | 324 | +27 | 30,131,017 | 9,263,118 | −20,867,899 | 35.02 | 33.02 | −2.00 | 1.19 | 1.05 | −0.14 | 58,368,374 | 61,730,278 | +3,361,904 | 132.47 | 23.40 | −109.07 |
| 2026-04 | 435 | 459 | +24 | −52,022,294 | −62,778,128 | −10,755,834 | 28.97 | 27.45 | −1.52 | 0.73 | 0.69 | −0.04 | 104,067,804 | 114,823,638 | +10,755,834 | −135.06 | −162.98 | −27.92 |
| 2026-05 | 361 | 388 | +27 | 60,795,997 | 39,459,390 | −21,336,607 | 37.67 | 35.05 | −2.62 | 1.49 | 1.27 | −0.22 | 46,452,376 | 52,120,177 | +5,667,801 | 292.33 | 103.05 | −189.28 |
| 2026-06 | 425 | 464 | +39 | −3,590,925 | −22,881,401 | −19,290,476 | 36.71 | 34.27 | −2.44 | 0.98 | 0.88 | −0.10 | 49,360,630 | 60,990,508 | +11,629,878 | −13.31 | −66.83 | −53.52 |
| 2026-07 | 288 | 306 | +18 | 12,942,514 | 5,040,346 | −7,902,168 | 36.46 | 34.31 | −2.15 | 1.15 | 1.05 | −0.10 | 31,161,925 | 35,481,953 | +4,320,028 | 70.34 | 14.96 | −55.38 |
| **TOTAL** | **2347** | **2542** | **+195** | **147,780,084** | **39,513,979** | **−108,266,105** | **34.43** | **32.26** | **−2.17** | **1.14** | **1.03** | **−0.11** | **114,092,025** | **129,150,945** | **+15,058,920** | **383.66** | **93.45** | **−290.21** |

### 10.2 S6-K2P0

| Mes | n Antes | n Después | Δn | net Antes (CLP) | net Después (CLP) | Δnet | WR% Antes | WR% Después | ΔWR | PF Antes | PF Después | ΔPF | maxDD Antes (CLP) | maxDD Después (CLP) | ΔmaxDD | RoM% Antes | RoM% Después | ΔRoM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-01 | 84 | 111 | +27 | 57,854,488 | 43,516,514 | −14,337,974 | 42.86 | 32.43 | −10.43 | 2.94 | 1.99 | −0.95 | 11,979,371 | 23,680,152 | +11,700,781 | 556.18 | 228.02 | −328.16 |
| 2026-02 | 120 | 138 | +18 | 3,171,785 | −3,162,373 | −6,334,158 | 37.50 | 34.78 | −2.72 | 1.03 | 0.97 | −0.06 | 35,066,578 | 36,286,350 | +1,219,772 | 32.26 | −16.20 | −48.46 |
| 2026-03 | 117 | 135 | +18 | 22,095,200 | 10,503,597 | −11,591,603 | 43.59 | 40.00 | −3.59 | 1.34 | 1.13 | −0.21 | 28,015,238 | 29,696,190 | +1,680,952 | 225.67 | 54.03 | −171.64 |
| 2026-04 | 177 | 195 | +18 | −35,060,930 | −42,938,628 | −7,877,698 | 25.42 | 23.08 | −2.34 | 0.62 | 0.57 | −0.05 | 52,841,750 | 60,719,448 | +7,877,698 | −197.29 | −237.93 | −40.64 |
| 2026-05 | 138 | 159 | +21 | 36,440,704 | 18,567,648 | −17,873,056 | 36.96 | 32.08 | −4.88 | 1.72 | 1.27 | −0.45 | 20,150,717 | 25,818,518 | +5,667,801 | 408.85 | 105.08 | −303.77 |
| 2026-06 | 159 | 183 | +24 | −133,648 | −11,175,601 | −11,041,953 | 37.74 | 34.43 | −3.31 | 1.00 | 0.86 | −0.14 | 22,298,496 | 30,481,136 | +8,182,640 | −1.58 | −68.65 | −67.07 |
| 2026-07 | 117 | 132 | +15 | 9,263,118 | 2,548,722 | −6,714,396 | 38.46 | 34.09 | −4.37 | 1.24 | 1.05 | −0.19 | 16,813,284 | 19,945,540 | +3,132,256 | 117.45 | 16.39 | −101.06 |
| **TOTAL** | **912** | **1053** | **+141** | **93,630,717** | **17,859,879** | **−75,770,838** | **36.51** | **32.48** | **−4.03** | **1.21** | **1.03** | **−0.18** | **63,303,935** | **73,803,767** | **+10,499,832** | **526.86** | **91.51** | **−435.35** |

### 10.3 S7-TPNONE

| Mes | n Antes | n Después | Δn | net Antes (CLP) | net Después (CLP) | Δnet | WR% Antes | WR% Después | ΔWR | PF Antes | PF Después | ΔPF | maxDD Antes (CLP) | maxDD Después (CLP) | ΔmaxDD | RoM% Antes | RoM% Después | ΔRoM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-01 | 111 | 120 | +9 | 1,761,894 | −4,660,736 | −6,422,630 | 29.73 | 27.50 | −2.23 | 1.04 | 0.90 | −0.14 | 12,897,965 | 19,320,594 | +6,422,629 | 16.94 | −24.42 | −41.36 |
| 2026-02 | 159 | 165 | +6 | 4,500,735 | 3,482,375 | −1,018,360 | 32.08 | 32.73 | +0.65 | 1.04 | 1.03 | −0.01 | 36,559,293 | 36,559,293 | 0 | 45.77 | 17.84 | −27.93 |
| 2026-03 | 150 | 159 | +9 | 14,529,975 | 5,253,681 | −9,276,294 | 32.00 | 30.19 | −1.81 | 1.21 | 1.07 | −0.14 | 22,179,907 | 24,146,978 | +1,967,071 | 148.35 | 28.73 | −119.62 |
| 2026-04 | 210 | 216 | +6 | −26,776,642 | −29,654,778 | −2,878,136 | 32.86 | 31.94 | −0.92 | 0.67 | 0.65 | −0.02 | 47,428,069 | 50,306,205 | +2,878,136 | −150.67 | −166.87 | −16.20 |
| 2026-05 | 177 | 183 | +6 | 23,422,268 | 19,958,716 | −3,463,552 | 42.37 | 40.98 | −1.39 | 1.43 | 1.34 | −0.09 | 20,773,780 | 20,773,780 | 0 | 262.79 | 112.96 | −149.83 |
| 2026-06 | 213 | 228 | +15 | 16,250,457 | 8,001,934 | −8,248,523 | 40.85 | 38.16 | −2.69 | 1.24 | 1.11 | −0.13 | 22,818,029 | 26,257,109 | +3,439,080 | 100.47 | 49.47 | −51.00 |
| 2026-07 | 147 | 150 | +3 | −523,297 | −1,711,070 | −1,187,773 | 34.69 | 34.00 | −0.69 | 0.99 | 0.95 | −0.04 | 14,876,331 | 16,064,103 | +1,187,772 | −6.64 | −11.01 | −4.37 |
| **TOTAL** | **1167** | **1221** | **+54** | **33,165,389** | **670,122** | **−32,495,267** | **35.48** | **34.15** | **−1.33** | **1.07** | **1.00** | **−0.07** | **49,107,138** | **53,952,346** | **+4,845,208** | **186.62** | **3.43** | **−183.19** |

### 10.4 SuperTrend-p14x3-M15

Tabla mes-a-mes Antes/Después: **idéntica en las 7 filas y el TOTAL** (n, net, WR%, PF, maxDD,
RoM% — sin ninguna diferencia). Δ = 0 en las 24 celdas numéricas de esta subtabla.

### 10.5 Validación semana informe (0.01 lot) — sección §4 del reporte markdown

| Estrategia | BT ops Antes | BT ops Después | BT neto Antes (CLP) | BT neto Después (CLP) |
|---|---:|---:|---:|---:|
| S6-K2P0 | 30 | 30 | 76,306 | 76,306 |
| S7-TPNONE | 36 | 36 | 12,587 | 12,587 |
| SuperTrend-p14x3-M15 | 4 | 4 | 15,106 | 15,106 |
| Combinado | 70 | 70 | 103,998 | 103,998 |

Esta subtabla (semana puntual 2026-07-20..07-23, lote 0.01/ficha) sale idéntica Antes/Después en
las 8 celdas numéricas — cero Δ.

---

## 11. Cuantificación de las 2,347 filas del baseline (multiset, `strategy,t_in,ficha,reason,net_067lot_clp`)

**Método:** comparación por multiset (`collections.Counter` de tuplas de 5 campos, valores de
`net_067lot_clp` como texto/string verbatim, sin parseo de floats más allá de una conversión a
`float` solo para calcular Δnet en la tabla de re-atribuidas — la clasificación misma usa
igualdad de string). Contra `data/analysis/pre_repair_snapshot/baseline_rows.csv` (2347 filas,
`sha256` verificado contra `MANIFEST.json.baseline_rows_sha256` = coincide). El nuevo substrato
son las 3 CSV regeneradas en `data/analysis/realtick_bt/positions_*.csv` (2542 filas), con la
columna `strategy` tomada del nombre de fichero (no existe como columna propia en esas CSV).

| Categoría | n | Definición aplicada |
|---|---:|---|
| idénticas | 367 | mismo `(strategy, t_in, ficha, reason, net)` completo |
| solo re-etiquetadas | 1980 | mismo `(strategy, t_in, ficha, net)`; `reason` cambió |
| re-atribuidas | 0 | mismo `(strategy, t_in, ficha)`; `net` distinto |
| desaparecidas | 0 | fila del baseline sin ninguna correspondencia en el nuevo |
| nuevas | 195 | fila del nuevo sin ninguna correspondencia en el baseline |

Verificación de suma: 367 + 1980 + 0 + 0 (desaparecidas) = **2347** (= filas del baseline).
367 + 1980 + 0 + 195 (nuevas) = **2542** (= filas del nuevo substrato).

### 11.1 Idénticas (367), desglose por (estrategia, reason)

| Estrategia | Reason | n |
|---|---|---:|
| S6-K2P0 | EXIT_INITSL | 12 |
| S6-K2P0 | EXIT_TRAIL | 21 |
| S7-TPNONE | EXIT_INITSL | 3 |
| S7-TPNONE | EXIT_TRAIL | 63 |
| SuperTrend-p14x3-M15 | EXIT_STLINE | 268 |
| **TOTAL** | | **367** |

### 11.2 Solo re-etiquetadas (1980), desglose por par viejo→nuevo

| Estrategia | reason Antes → reason Después | n |
|---|---|---:|
| S6-K2P0 | EXIT_INITSL → EXIT_SL_RAISED | 879 |
| S7-TPNONE | EXIT_INITSL → EXIT_SL_RAISED | 1101 |
| **TOTAL** | | **1980** |

Estas filas tienen **mismo `net_067lot_clp`** que en el baseline (por eso califican como
"solo re-etiquetadas" y no "re-atribuidas") — únicamente cambió el string de `reason`.

### 11.3 Re-atribuidas (0)

No se encontró ninguna fila con `(strategy, t_in, ficha)` igual al baseline y `net_067lot_clp`
distinto, tras remover las categorías 11.1 y 11.2. **Lista de las 10 de mayor |Δnet|: vacía (0
filas califican).**

### 11.4 Desaparecidas (0)

Ninguna fila del baseline quedó sin corresponder en el nuevo substrato bajo ninguna de las
categorías anteriores.

### 11.5 Nuevas (195), desglose por (estrategia, reason)

| Estrategia | Reason | n |
|---|---|---:|
| S6-K2P0 | reverse | 141 |
| S7-TPNONE | reverse | 54 |
| **TOTAL** | | **195** |

Las 195 filas nuevas tienen `reason = "reverse"` en el 100% de los casos (0 filas nuevas con
cualquier otro `reason`). `reverse` no pertenece al conjunto `LEVEL_EXITS` del script (no es un
cierre resuelto por nivel intra-vela).

---

*Fin del documento. Sin sección de veredictos — la escribe R4 (Opus 5 high) por separado.*
