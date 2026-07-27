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

*Fin del cuerpo de cifras de R3. Sin veredictos hasta aquí — por diseño. La sección siguiente
la añadió R4 (Opus 5 high) el 2026-07-27, sin tocar ni una cifra de las 11 secciones anteriores.*

---

# §VEREDICTOS — Task R4 (Opus 5 high, 2026-07-27)

**Rol de esta sección.** Las 11 secciones anteriores son cifras sin juicio. Ésta es la etapa de
análisis de resultados: aquí SÍ se interpreta, SÍ se dictamina y SÍ se recomienda. Lo que aquí
**no** se hace es decidir despliegues ni re-tunear parámetros — eso es del user. Ningún `.py` fue
modificado por esta tarea; el roster retador (`CONFIGS_CHALLENGER`, magics 726xxx) está intacto.

**Convención numérica:** la misma del cuerpo del documento (coma de miles, punto decimal).

**Regla de arbitraje aplicada.** Cuando el dato medido contradice al tracker, al plan o al
controlador, **gana el dato**, y la contradicción se declara explícitamente (ver §V15).

**Procedencia de cada cifra.** Todo lo que se cita abajo sale de un artefacto en disco
(`data/analysis/monday_audit/*.json`, `data/analysis/realtick_bt/positions_*.csv`,
`data/analysis/pre_repair_snapshot/**`) o de una medición ejecutada por código en esta tarea y
declarada como tal en §V14. Nada está estimado a ojo. Los cocientes y porcentajes derivados
(medias, fracciones, tasas de supervivencia) se calcularon con código sobre esos artefactos.

---

## V0 — El hecho central, dictaminado

**Las estrategias vivas no empeoraron. El instrumento de medición dejó de estar ciego.**

Esta frase es el eje de todo lo que sigue y hay que sostenerla con el dato exacto, porque
comunicarla mal en cualquiera de las dos direcciones sería el peor resultado posible de toda la
cadena de reparación.

La prueba es aritmética y no admite lectura alternativa (§11 del cuerpo, re-verificada por R4
sumando directamente las CSV regeneradas):

- Las **2,347 filas** del substrato viejo están **todas** en el nuevo: 367 idénticas + 1,980 solo
  re-etiquetadas, **0 re-atribuidas, 0 desaparecidas**. Su suma de `net_067lot_clp` en el
  substrato nuevo es **147,780,084.05** — el neto viejo completo, **al céntimo**.
- Todo el delta son **195 filas nuevas**, el 100 % con `reason="reverse"`, con suma
  **−108,266,105.49**.

Es decir: **ni una sola posición que el backtest ya mostraba cambió de resultado.** No se corrigió
un cálculo, no se re-valoró una operación, no se movió un fill. Se destapó una población de
cierres —el stop-and-reverse, que en S6/S7 vivos está **activo y disparándose**— que el
emparejador descartaba en silencio.

La consecuencia inmediata, y hay que decirla sin adornos: **el número de 147,8 MM que estuvo a
punto de emitirse el lunes nunca fue el resultado del sistema.** Era el resultado de un sistema
que no paga sus reversiones. El sistema real, tal como opera en la cuenta, es el de 39,5 MM. La
caída del 73 % no es una pérdida ocurrida entre el viernes y el lunes: es la diferencia entre lo
que creíamos medir y lo que estábamos midiendo.

---

## V1 — Neto y perfil de 7 meses · **CAMBIA**

| | Antes | Después | Δ |
|---|---:|---:|---:|
| net COMBINED (0.67 lot) | 147,780,084.05 | 39,513,978.56 | **−108,266,105.49 (−73.26 %)** |
| n posiciones | 2,347 | 2,542 | +195 (+8.31 %) |
| WR % | 34.427 | 32.258 | −2.169 |
| PF | 1.1381 | 1.0333 | −0.1048 |

**Veredicto: CAMBIA, y cambia el mensaje entero del lunes.** No es un ajuste de segundo orden.
Tres lecturas obligatorias del nuevo número:

1. **El PF se desploma a 1.0333.** Ése, y no el neto, es el titular honesto. Un profit factor de
   1.03 sobre 2,542 operaciones y 7 meses describe un sistema que está **apenas** del lado
   correcto de cero. El PF viejo, 1.14, describía algo cualitativamente distinto. La distancia
   entre "1.14" y "1.03" es la distancia entre un edge modesto y un edge que no se distingue del
   ruido con este tamaño de muestra.
2. **El reparto entre estrategias se rompe.** S6-K2P0 pasa de 93.6 MM a 17.9 MM (**−80.93 %**);
   S7-TPNONE de 33.2 MM a **670,122.03** (**−97.98 %**) — S7 queda, en 7 meses, en un empate
   técnico con cero (PF 1.0013, `a5_spread_gate.json`). SuperTrend queda **intacto** en 20,983,977.53.
   🔴 Consecuencia de primer orden: **en el substrato reparado, SuperTrend es la estrategia que
   más neto aporta de las tres** (20.98 MM de 39.51 MM = 53 % del total), con 268 posiciones
   frente a 2,274 de S6+S7. Eso invierte la jerarquía implícita en toda la narrativa previa.
3. **La caída se concentra donde el instrumento estaba ciego, no donde el sistema opera mal.**
   S7 pierde el 98 % de su neto con solo 54 filas nuevas; S6 pierde el 81 % con 141. La
   fragilidad que esto revela no es "S6/S7 son malas": es que **su neto declarado dependía de no
   contabilizar sus reversiones**.

**Para el documento del lunes:** el titular no puede ser "el sistema rinde 39,5 MM". Tiene que ser
"el sistema rinde 39,5 MM **medido correctamente por primera vez**, contra 147,8 MM que era una
medición incompleta". Y debe ir acompañado del PF, no solo del neto.

---

## V1-bis — La asimetría de las 195 filas · **hallazgo de primer orden, SE SOSTIENE**

El controlador señaló que 195 filas produciendo −108.3 MM implica del orden de −555 k por
operación contra ~+63 k de media del resto del libro, y pidió verificarlo. **Se verifica, y con
margen.** Medido por código sobre las CSV en disco:

| Población | n | suma CLP | media CLP |
|---|---:|---:|---:|
| Filas supervivientes (las 2,347 viejas) | 2,347 | 147,780,084.05 | **+62,965.52** |
| Filas nuevas (`reason="reverse"`) | 195 | −108,266,105.49 | **−555,210.80** |

**Ratio de magnitudes: 8.82×, con el signo invertido.** La media de una reversión es casi nueve
veces la media de una operación normal, en dirección contraria. Se sostiene la caracterización de
"orden de magnitud".

Y el perfil interno de esa población lo confirma como fenómeno estructural, no como cola de
outliers (medido sobre las 195 filas de las CSV):

- **183 de 195 son pérdidas; solo 12 son ganancias** (WR **6.15 %**).
- Mediana **−519,532.74**; p25 −815,064.05; p75 −313,727.50. La *mediana* ya está en −0.5 MM: no
  es que unas pocas reversiones catastróficas arrastren la media, es que **casi todas pierden, y
  pierden mucho**.
- Profit factor de la población (`a3_exit_reason.json`): **0.0825** en S6, **0.0087** en S7. Un PF
  de 0.009 significa que por cada peso ganado en reversiones de S7 se pierden 115.
- Rango: mínimo −1,658,363.57, máximo +1,734,285.62. **Ninguna de las 195 entra en el top-10 del
  libro por |net|** (el 10.º mayor |net| del libro es 8,013,227.81, casi 5× el mayor reverse).

**Dictamen: es un hallazgo de primer orden sobre el comportamiento del stop-and-reverse, no un
detalle contable.** Y tiene una lectura mecánica coherente que hay que dar, porque explica el
número y evita que se lea como un misterio. Comparando medias por motivo (`a3_exit_reason.json`):

| Motivo | media S6 | media S7 | lectura |
|---|---:|---:|---|
| `EXIT_INITSL` (stop inicial genuino) | −946,045.27 | −1,171,458.49 | pérdida completa |
| **`reverse`** | **−537,381.83** | **−601,764.21** | **pérdida parcial** |
| `EXIT_SL_RAISED` (stop ya levantado) | +114,939.91 | +25,494.85 | ganancia media |
| `EXIT_TRAIL` | +188,146.86 | +136,665.68 | ganancia media |

La reversión **sale antes de que el stop la mate, pero sale perdiendo**: su media está entre el
stop-out completo y la salida con stop levantado, más cerca del primero. Eso es exactamente lo que
se espera de un mecanismo que cierra cuando la señal se da vuelta — si la señal se dio vuelta, la
posición casi siempre estaba a contramano. El stop-and-reverse **corta la pérdida, no la evita**,
y en 7 meses ese corte costó 108.3 MM que el backtest no mostraba.

⚠️ **Lo que este hallazgo NO autoriza a concluir:** que haya que desactivar el stop-and-reverse.
Un mecanismo cuyo trabajo es cortar posiciones perdedoras *tiene* que exhibir una media negativa;
juzgar su valor exige el contrafactual "qué habrían hecho esas 195 posiciones sin reversión, hasta
su stop o su trailing", y ese contrafactual **no existe en ningún artefacto**. Ver §V16.

---

## V2 — A1 `maxDD` · **CAMBIA. El «CONFIRMA» del tracker YA NO SE SOSTIENE**

| | Antes | Después |
|---|---:|---:|
| `max_dd_clp` (@0.1 lot) | 17,028,660.47 | **19,276,260.47** |
| `max_dd_pct_of_initial` | **28.5716 %** | **32.3427 %** (+3.771 pp) |
| `max_dd_pct_of_peak_equity` | 20.3814 % | **25.0727 %** |
| `peak_equity_clp` | 23,949,863.73 | 17,281,515.46 |
| `trough_equity_clp` | 6,921,203.26 | **−1,994,745.01** |
| `t_peak` / `t_trough` | 2026-03-23 / 2026-04-29 | **idénticos** |

El tracker (Task 7) afirmaba: «**CONFIRMA** la estimación previa de −28,6 %», y justificaba la
confirmación con una coincidencia fuerte: 114,092,025 × 0.1/0.67 = 17,028,660.45 ≈ 17,028,660.47
calculado.

**Veredicto: la cifra CAMBIA; el razonamiento que la validaba SE SOSTIENE.** Hay que separar las
dos cosas con cuidado, porque es un caso donde el método era bueno y el insumo estaba incompleto:

- **La cifra −28,57 % está muerta.** El maxDD real del substrato reparado es **−32,34 % del
  balance inicial**. La frase «confirma la estimación previa de −28,6 %» debe desaparecer del
  documento del lunes; repetirla sería afirmar un número que el dato ya desmintió.
- **La coherencia interna sobrevive intacta.** R4 re-verificó la misma regla de tres con los
  números nuevos: 129,150,945 (maxDD de la grilla mensual @0.67) × 0.1/0.67 = **19,276,260.45**,
  contra **19,276,260.47** que emite `a1_maxdd.json`. La concordancia es igual de buena que antes.
  Es decir: A1 nunca estuvo mal calculado. Calculaba correctamente sobre un stream al que le
  faltaban 195 cierres.
- **`t_peak` y `t_trough` no se mueven ni un milisegundo.** La ventana de drawdown es la misma
  (23-mar → 29-abr); lo que cambió es su profundidad. Eso refuerza que no estamos ante otro
  fenómeno, sino ante el mismo episodio medido con el libro completo.

🔴 **`trough_equity_clp` negativo — cómo se comunica sin exagerar ni minimizar.** El campo vale
**−1,994,745.01**. Leyendo `a1_maxdd.py`: "equity" es la **suma acumulada de P&L**, no el saldo de
la cuenta (el balance de 59.6 MM entra solo como denominador). Por tanto:

- **Lo correcto:** la curva de P&L acumulado del track llegó a estar **1.99 MM por debajo de su
  punto de partida**; es decir, en el peor momento el track había devuelto todo lo ganado en los
  primeros meses y algo más. En términos de saldo de cuenta: pico 76,881,515.46 → valle
  57,605,254.99 CLP.
- **Lo incorrecto, y hay que evitarlo activamente:** decir o insinuar que la cuenta se agotó, se
  quedó sin margen o entró en negativo. No ocurrió: el valle de saldo son 57.6 MM sobre 59.6 MM
  iniciales, una caída del **25.07 % del pico de equity**.

**Dictamen operativo:** −32,34 % es el número que va al documento, con las tres cifras de contexto
(−19,276,260 CLP @0.1 lot · −25,07 % del pico de equity · valle de P&L acumulado en −1.99 MM).

---

## V3 — A2 cap B3 (`max_simultaneous_fichas`) · **SE SOSTIENE. El roster retador NO requiere cambio**

| | Antes | Después |
|---|---:|---:|
| `max_simultaneous_fichas` | 7 | **7** |
| `p95_simultaneous` / `p99_simultaneous` | 7 / 7 | **7 / 7** |
| B3 `dropped_n` (b6) | 0 | **0** |

**Veredicto: SE SOSTIENE, sin reservas. Confirmo que `CONFIGS_CHALLENGER` (magics 726xxx) no
requiere ningún cambio y NO debe tocarse.** El valor `max_open_fichas=7` que Task 4 leyó de
`a2_overlap.json` sigue siendo exactamente el valor que ese artefacto contiene tras la
regeneración. **No discrepo.**

Y hay un argumento adicional que refuerza la conclusión, no solo la deja pasar: el histograma de
simultaneidad **subió en todos los bins** (N=7: 267 → 304 barras; N=5: 696 → 792), es decir el
substrato reparado tiene *más* solape, no menos — y aun así el pico sigue clavado en 7. El cap no
se salvó por poco: se salvó porque 7 es un techo estructural (3 configs × hasta 3 fichas, con la
tercera raramente coincidente), no un máximo muestral frágil. Añadir 195 posiciones no lo movió.

⚠️ **Matiz honesto que debe acompañar al cap en el documento:** B3 con `cap = pico observado` es,
por construcción, una puerta que **nunca muerde** (`dropped_n = 0`, y el propio artefacto lo dice:
"ZERO drops — the cap IS the observed peak"). No es una restricción de riesgo validada: es un
**fusible** contra un régimen de solape que nunca se vio en 7 meses. Presentarlo como "control de
exposición demostrado" sería falso. Presentarlo como "tope de seguridad calibrado sobre el peor
solape observado" es exacto.

La nota del tracker en Task 12 («el cap B3=7 se calibró sobre substrato incompleto y podría
moverse») queda **resuelta: no se movió.** Task 12 deja de estar condicionada por este punto.

---

## V4 — A2 correlaciones por par · **SE SOSTIENE (y la frase «SuperTrend es casi independiente» sigue enterrada)**

| par | Task 8 (reloj roto) | pre-reparación | post-reparación |
|---|---:|---:|---:|
| S6\|S7 | +0.730 | 0.7596 | **0.7669** |
| S6\|ST | +0.295 | 0.3520 | **0.3556** |
| S7\|ST | +0.047 | 0.1409 | **0.1535** |
| `n_trading_days` | 161 | 163 | **163** |

**Veredicto: SE SOSTIENE.** La reparación mueve las tres correlaciones en el tercer decimal
(+0.0073 / +0.0037 / +0.0126). Añadir 195 posiciones no altera la estructura de dependencia entre
estrategias. Los valores post-reparación son los definitivos.

**Sobre la frase de Task 8 «SuperTrend es casi independiente de ambas»: sigue sin sostenerse, y la
reparación no la rehabilita.** Ya la había matado el arreglo del reloj (S6\|ST 0.295 → 0.352,
S7\|ST 0.047 → 0.141); la reparación la empuja un poco más lejos (0.3556 / 0.1535). Redacción
correcta para el lunes: **«S6 y S7 comparten la mayor parte de la misma apuesta direccional
(+0.77). SuperTrend es la única fuente de diversificación real del track, pero es diversificación
parcial, no independencia: +0.36 contra S6 y +0.15 contra S7.»**

🔴 Y ahora esa frase carga un peso que antes no tenía. Con SuperTrend aportando el 53 % del neto
reparado y siendo la única pata poco correlacionada, **la diversificación del track descansa sobre
268 posiciones de una sola estrategia**. Eso es una observación de riesgo, no de correlación, y
debe aparecer en el documento.

---

## V5 — A3 atribución por motivo de salida · **CAMBIA. Es la corrección narrativa nº 1 del lunes**

**Lo que el tracker (Task 9) dejó escrito y que hoy es engañoso:**

> «S6-K2P0 EXIT_INITSL n=891 net=89,68MM CLP (WR 36,0 %) + EXIT_TRAIL n=21 net=3,95MM (WR 57,1 %);
> S7-TPNONE EXIT_INITSL n=1104 net=24,56MM (WR 34,8 %)…»

Leído de buena fe, eso dice: *«el grueso del libro sale por stop inicial, y los stops iniciales
son rentables»*. **Las dos mitades de esa lectura son falsas**, por dos motivos independientes que
el substrato reparado separa por fin:

**(a) El 98.7 % / 99.7 % de esos "stop-outs iniciales" no eran stops iniciales** (hallazgo H3,
implementado por R2-bis). El motor etiquetaba `EXIT_INITSL` a stops **ya levantados** por trailing
o breakeven. Separados:

| | `EXIT_INITSL` genuino | `EXIT_SL_RAISED` | verificación |
|---|---:|---:|---|
| S6-K2P0 | n=12, net −11,352,543.30, **WR 0.0 %** | n=879, net +101,032,176.60, WR 36.52 % | 12+879 = 891 ✔ |
| S7-TPNONE | n=3, net −3,514,375.47, **WR 0.0 %** | n=1,101, net +28,069,826.97, WR 34.88 % | 3+1,101 = 1,104 ✔ |

**WR = 0.0 % en los 15 stops genuinos, exactamente como debe ser** (un stop inicial intacto es una
pérdida por definición). El grupo que "era rentable" es el de los stops levantados — que es otra
cosa: es el trailing haciendo su trabajo y siendo mal etiquetado. La aritmética cierra al céntimo
contra los buckets viejos, lo que prueba que esto es **partición, no recálculo**.

**(b) Faltaba un motivo entero.** `reverse` no existía en A3 porque no existía en el substrato.
Ahora: S6 n=141 net −75,770,838.42 (WR 6.38 %), S7 n=54 net −32,495,267.07 (WR 5.56 %).

**Atribución correcta y completa del substrato reparado** (`a3_exit_reason.json`, 9 grupos):

| Motivo (agregado) | n | net CLP | lectura |
|---|---:|---:|---|
| `EXIT_SL_RAISED` (S6+S7) | 1,980 | +129,102,003.57 | el trailing/BE es **la máquina de ganar** del track |
| `EXIT_STLINE` (ST) | 268 | +20,983,977.53 | SuperTrend, motivo único |
| `EXIT_TRAIL` (S6+S7) | 84 | +12,561,021.72 | subida y toque en la misma barra |
| `reverse` (S6+S7) | 195 | **−108,266,105.49** | **la máquina de perder** |
| `EXIT_INITSL` genuino (S6+S7) | 15 | −14,866,918.77 | stop intacto, WR 0 % |

**Veredicto: CAMBIA por completo, y en la dirección más informativa posible.** La narrativa
correcta del lunes es de una sola frase: **el track gana con el trailing y pierde con las
reversiones**; el stop inicial genuino casi nunca se toca (15 de 2,542 = 0.6 %). La versión del
tracker («el grueso sale por stop inicial y es rentable») **induce a error en los dos sentidos** y
no puede sobrevivir a la revisión.

⚠️ **Duda que R2-bis dejó abierta para R4** (¿es `EXIT_SL_RAISED` el nombre definitivo?):
**dictamino que sí para la entrega del lunes** — es descriptivo, no colisiona con ningún motivo
del motor y ya está commiteado en el substrato y en los tests. Renombrarlo ahora obligaría a
regenerar todo Track A por motivos estéticos, a horas de la entrega. Si el programa post-lunes
prefiere `EXIT_SL_TRAILED` o similar cuando se afine la etiqueta **en el motor** (item ya
registrado, sobre copia), ése es el momento de cambiarlo, no éste.

---

## V6 — A4 serial · **SE SOSTIENE**

Todos los movimientos son de tercer o cuarto decimal: S6 lag_1 0.6353 → 0.6366; S7 lag_1 0.6554 →
0.6544; SuperTrend **idéntico en las cinco lags** y en ambas rachas. Rachas: S6 pérdidas 27 → 30
(+3), S7 pérdidas 42 → 42, ganancias 15/15/4 sin cambio en las tres estrategias.

**Veredicto: SE SOSTIENE sin matices.** La conclusión de Task 9 sigue vigente palabra por palabra:
S6 y S7 tienen autocorrelación lag-1 positiva y notable (~+0.64/+0.65) que decae a ~0 en lag-3+ —
los resultados se agrupan en rachas cortas, consistente con régimen; SuperTrend es prácticamente
independiente en serie (lag-1 −0.063). Es, de hecho, el bloque **más estable** de todo el diff:
195 filas nuevas no movieron la estructura temporal del libro.

Único apunte digno de mención: la racha máxima de pérdidas de S6 pasa de 27 a 30. Es coherente con
inyectar 141 pérdidas nuevas (183 de las 195 filas nuevas pierden) y **no cambia ninguna
conclusión**; si acaso, hace más urgente que el documento cite la racha de 42 de S7 como el número
de tolerancia psicológica que el user debe conocer.

---

## V7 — A5 spread · **SE SOSTIENE: sigue NO EVALUABLE, y con más muestra que antes**

| ámbito | at_0.5 n | at_0.6 n |
|---|---:|---:|
| COMBINED | 2,542 | **0** |
| S6-K2P0 / S7-TPNONE / SuperTrend | 1,053 / 1,221 / 268 | **0 / 0 / 0** |

**Veredicto: SE SOSTIENE exactamente el veredicto de Task 9 — NO EVALUABLE**, y el substrato
reparado lo refuerza: ahora son **2,542 filas** (195 más) y siguen siendo **el 100 % a spread
0.5, cero a 0.6**. No hay ni una fila con la que comparar.

Esto es lo contrario de un problema: es la regla «lo no evaluable se declara no evaluable»
funcionando. El filtro de spread 0,5 sigue validado **únicamente** por las cinco sesiones live
citadas en su momento; esta auditoría de 7 meses **ni lo corrobora ni lo refuta**. Y la corrección
nº 3 del user del 2026-07-26 («spread 0,5 y solo 0,5; 0,6 es operable pero no lo haremos»)
convierte esa no-evaluabilidad en irrelevante para la decisión: no se va a operar a 0.6, así que
no hace falta evidencia sobre 0.6.

⚠️ Lo que **no** puede decir el documento: «el gate 0.5 está validado sobre 7 meses». No lo está.
Lo que puede decir: «los 7 meses reconstruidos ocurren íntegramente a spread 0.5, que es el único
régimen en que estas estrategias operan por diseño».

---

## V8 — B6 veredictos de máscara B1–B4 · **veredictos SE SOSTIENEN, magnitudes CAMBIAN (B1 de forma extrema)**

| Máscara | Veredicto Antes | Veredicto Después | Dictamen |
|---|---|---|---|
| **B1** @50 min | NO VETO | **NO VETO** (texto idéntico) | **SE SOSTIENE el veredicto; CAMBIA la magnitud** |
| **B2** noticias | 0 descartes, evaluable | **0 descartes** | SE SOSTIENE (con la limitación de siempre) |
| **B3** cap 7 | 0 descartes | **0 descartes** | SE SOSTIENE (ver §V3) |
| **B4** SL mínimo | NOT MASKABLE | **NOT MASKABLE** | SE SOSTIENE |

**B1 — el punto delicado.** El veredicto textual no se mueve, pero los números que lo rodean sí, y
mucho:

| | Antes | Después |
|---|---:|---:|
| `dropped_n` | 209 | **227** |
| `kept_n` | 2,138 | **2,315** |
| `kept_net_clp` | 177,357,685.37 | **80,302,945.79** (−54.72 %) |
| `net_delta_clp` | 29,577,601.32 | **40,788,967.23** |
| `net_delta_pct` | **+20.01 %** | **+103.23 %** |
| `n_reopens` | 145 | 145 (idéntico) |

**Veredicto: NO-VETO SE SOSTIENE — y se sostiene por el motivo correcto.** El veredicto de máscara
pregunta «¿esta puerta habría sido catastrófica?», y la respuesta sigue siendo no: B1@50min habría
**mejorado** el neto, no destruido el track. Que la mejora pase de +20 % a +103 % no cambia el
signo del veredicto.

🔴 **Pero el +103.23 % es un número tóxico si se cita solo, y hay que blindarlo.** El salto de
+20 % a +103 % **no significa que la puerta se haya vuelto cinco veces mejor**. `net_delta_clp`
sube un 38 % (29.6 MM → 40.8 MM); lo que se desplomó es el **denominador** (`total_net_clp`
147.8 MM → 39.5 MM). Un porcentaje calculado contra una base que cayó un 73 % **se infla
mecánicamente**. Citar «+103 %» sin el denominador a la vista sería, en la práctica, engañar.

**Redacción obligatoria:** «B1@50 min habría evitado 227 posiciones y añadido **+40,8 MM CLP** al
neto de 7 meses (de 39,5 MM a 80,3 MM). Expresado en porcentaje son +103 %, pero ese porcentaje
está inflado por la caída de la base: la mejora en CLP subió un 38 %, no un 400 %.»

Y el `caveat` que el propio artefacto ya arrastra sigue vigente y debe ir junto al número: el
signo **no es estable** en el parámetro de espera, y los 50 min se fijaron por diagnóstico previo,
no se eligieron de este barrido. La máscara **veta, no selecciona**.

**B2 / B4:** sin cambio, y sus limitaciones siguen siendo limitaciones, no ausencias de problema —
B2 solo cubre NFP (sin CPI/FOMC/PPI), B4 no es enmascarable porque las CSV no llevan columna de
SL y porque B4 es un detector de bug vivo, no un filtro. Ambas van al documento como **«sin
evidencia»**, no como «sin problema».

---

## V9 — B1 curva (Task 16), peldaños N2..N6 · **ranking CAMBIA parcialmente; magnitudes CAMBIAN; la forma SE SOSTIENE**

| Rung | wait | Δ% Antes | Δ% Después | n_blocked A→D |
|---|---:|---:|---:|---:|
| N2 | 30 min | +13.27 | **+58.14** | 92 → 98 |
| N3 | 45 min | **+32.67** | **+137.59** | 159 → 168 |
| N4 | 60 min | +20.01 | **+103.23** | 209 → 227 |
| N5 | 75 min | +9.72 | **+89.92** | 293 → 317 |
| N6 | 90 min | **−15.24** | **+3.38** | 362 → 395 |

Ranking Antes `[N3, N4, N2, N5, N6]` → Después `[N3, N4, N5, N2, N6]`.

**Veredicto desglosado:**

- **El ganador SE SOSTIENE.** N3 (45 min) es primero en ambos substratos, y con holgura mayor que
  antes (+137.59 % vs +103.23 % del segundo).
- **El podio de arriba y el farolillo SE SOSTIENEN.** N3 > N4 en ambos; N6 último en ambos.
- **El medio CAMBIA:** N2 y N5 intercambian los puestos 3 y 4. Es un cambio real y hay que
  registrarlo, pero afecta a dos peldaños separados por 31 puntos porcentuales de un ranking que
  ya se declaró in-sample: **no cambia ninguna decisión**.
- 🔴 **El cambio cualitativamente relevante es N6: pasa de −15.24 % a +3.38 %, o sea de signo
  negativo a positivo.** El titular de Task 16 —«el signo se da vuelta entre 60 y 90 minutos»—
  **YA NO ES CIERTO**: en el substrato reparado **los cinco peldaños son positivos**. Esa frase
  está en el tracker (§Task 16) y en `2026-07-27-b1-wait-curve.md`, y debe corregirse.
- **La forma de "joroba, no codo" SE SOSTIENE**, e incluso se acentúa: sube hasta N3 y baja
  monótonamente después (137.6 → 103.2 → 89.9 → 3.4). Sigue sin haber un codo que justifique fijar
  el parámetro por geometría de la curva.

⚠️ **Advertencia sobre las magnitudes de esta tabla, idéntica a la de §V8:** los cinco Δ% comparten
el mismo denominador colapsado. **Los cinco están inflados.** Lo comparable entre substratos son
los CLP, no los porcentajes. En CLP la curva se movió mucho menos de lo que sugieren los %: N3
pasa de +48.3 MM a +54.4 MM de delta.

---

## V10 — B1 robustez M1/M2/M3 · **M1 SE SOSTIENE y mejora · M2 CAMBIA y es lo más grave del diff · M3 SE SOSTIENE**

### M1 — consistencia mensual de signo

| Rung | pos/neg Antes | pos/neg Después |
|---|---:|---:|
| N2 | 3/4 | 3/4 |
| N3 | **5/2** | **5/2** |
| N4 | 4/3 | 4/3 |
| N5 | 3/4 | **4/3** |
| N6 | 4/3 | **5/2** |

**Veredicto: SE SOSTIENE, y para N5/N6 mejora en un mes.** Bajo D170 la consistencia mensual es
uno de los tres criterios, y N3 mantiene 5 meses positivos de 7 en ambos substratos.

🔴 **Pero el juicio duro de Task 16 sobre la robustez mensual hay que re-emitirlo, porque cambió
de forma.** El tracker decía: «la mejora NO sobrevive consistencia mensual (sin 2026-02 los 5
peldaños negativos)». Con los meses nuevos a la vista (`m1_sign_consistency_by_month`, rung N3):
2026-02 aporta un `delta_clp` de **+64,939,710.15** sobre un delta total de 40.8 MM. **Sigue
siendo cierto que un solo mes carga con más del 100 % de la mejora** — de hecho más que antes en
términos relativos. La dependencia de febrero **SE SOSTIENE como advertencia**: la mejora de B1 es,
en lo esencial, un fenómeno de febrero de 2026.

**Y hay un dato mensual que el documento del lunes debe usar, porque es de los pocos buenos:** el
**perfil de signo mensual del libro base NO cambió**. Antes y después, los mismos 5 meses positivos
y los mismos 2 negativos (abril y junio), sin una sola inversión de signo:

| Mes | baseline Antes | baseline Después | signo |
|---|---:|---:|:--:|
| 2026-01 | 87,475,384 | 66,714,780 | + → + |
| 2026-02 | 12,048,391 | 4,695,873 | + → + |
| 2026-03 | 30,131,017 | 9,263,118 | + → + |
| 2026-04 | −52,022,294 | −62,778,128 | − → − |
| 2026-05 | 60,795,997 | 39,459,390 | + → + |
| 2026-06 | −3,590,925 | −22,881,402 | − → − |
| 2026-07 | 12,942,514 | 5,040,346 | + → + |

**La reparación cambió el nivel del libro, no su forma temporal.** Es el argumento más limpio
disponible para sostener que esto fue un cambio de instrumento y no un cambio de sistema.

### M2 — sensibilidad top-K · **CAMBIA, y es el hallazgo más incómodo del diff**

| K | best Antes (Δ%) | best Después (Δ%) | orden Después |
|---:|---|---|---|
| 1 | N3 (+38.90) | N3 (**+343.61**) | [N3,N4,N5,N2,N6] |
| 3 | N3 (+47.93) | N3 (**−719.37**) | [N3,N4,N5,N2,N6] |
| 5 | N3 (+58.69) | N3 (**−208.94**) | [N3,N4,N5,N2,N6] |
| 10 | N3 (+115.65) | **N5** (−89.55) | [N5,N3,N4,N6,N2] |

**Veredicto: el RANKING SE SOSTIENE en K=1/3/5 (N3 sigue primero) y CAMBIA en K=10 (N3 → N5).**
Eso, en sí, es un deterioro moderado de la robustez del ranking. Task 16 decía «el ranking SÍ
sobrevive top-K»; hoy hay que decir **«sobrevive hasta K=5 y se rompe en K=10»**.

Pero el titular de M2 no es el ranking. Es lo que revela sobre la base — ver §V11.

### M3 — perfil bloqueadas vs mantenidas (rung N3)

| | blocked Antes | blocked Después | kept Antes | kept Después |
|---|---:|---:|---:|---:|
| n | 159 | 168 | 2,188 | 2,374 |
| mean_clp | −303,601.40 | **−323,617.39** | +89,603.61 | **+39,545.79** |
| median_clp | −454,904.88 | **−499,454.18** | −262,276.19 | −303,688.22 |
| win_rate | 29.56 | **27.98** | 34.78 | 32.56 |
| profit_factor | 0.6202 | **0.5918** | 1.2080 | **1.0892** |

**Veredicto: SE SOSTIENE, y se refuerza.** La afirmación clave de Task 16 —«lo vetado ES peor que
lo mantenido»— sigue siendo cierta en las cuatro métricas y **con más margen** que antes: las
bloqueadas empeoran (media −303 k → −324 k, PF 0.620 → 0.592) mientras las mantenidas también
bajan pero conservan PF > 1 (1.089). La puerta B1 sigue separando poblaciones genuinamente
distintas, no cortando al azar.

⚠️ Matiz que el documento debe llevar: el PF de las mantenidas cae de 1.208 a **1.089**. Aplicar
B1@45min al substrato reparado deja un libro con PF 1.09, no 1.21. La puerta ayuda; no rescata.

---

## V11 — 🔴 D171, concentración del neto · **CAMBIA, y a mucho peor. Recálculo obligatorio**

El brief pide re-emitir el juicio de D171 («antes de la reparación, 10 trades eran el 72 % del
neto y recortar 30 lo volvía pérdida») con los números nuevos. Recalculado por código a partir de
`m2_topk_sensitivity.global.K{k}.curve.COMBINED.baseline` en ambos substratos:

| K (mayores por \|net\|) | suma top-K | % del neto **Antes** | % del neto **Después** | neto tras recortar, Antes | neto tras recortar, **Después** |
|---:|---:|---:|---:|---:|---:|
| 1 | 23,691,445.89 | 16.03 % | **59.96 %** | 124,088,638.16 | 15,822,532.67 |
| 3 | 47,071,674.09 | 31.85 % | **119.13 %** | 100,708,409.96 | **−7,557,695.53** |
| 5 | 65,534,537.47 | 44.35 % | **165.85 %** | 82,245,546.58 | **−26,020,558.91** |
| 10 | 106,039,895.02 | **71.76 %** | **268.36 %** | 41,740,189.03 | **−66,525,916.46** |

🔴 **Dos hechos que hay que leer juntos, porque por separado engañan:**

1. **Las sumas top-K son IDÉNTICAS al céntimo en ambos substratos** (23,691,445.89 / 47,071,674.09
   / 65,534,537.47 / 106,039,895.02). Es decir: **la reparación no tocó la cola grande del libro.**
   Verificado además directamente sobre las CSV: el mayor |net| de las 195 filas nuevas es
   1,734,285.62, y el 10.º mayor |net| del libro entero es 8,013,227.81 — **ninguna fila nueva
   entra en el top-10**. La cola es exactamente la misma; lo que se encogió es el cuerpo.
2. **Por eso la concentración explota:** de 71.76 % a **268.36 %** en K=10. Y el umbral de
   supervivencia se derrumba: antes hacía falta quitar **30** operaciones para volver el libro
   negativo; **ahora bastan TRES**.

El recorte **por estrategia** (`m2_topk_sensitivity.by_group`, K mayores de *cada* estrategia) —que
es la vista de la que salió literalmente el enunciado de D171— lo dice todavía más crudo:

| K por estrategia | ops retiradas | neto **Antes** | neto **Después** |
|---:|---:|---:|---:|
| 1 | 3 | 109,318,347.45 | **+1,052,241.96** |
| 3 | 9 | 56,397,537.83 | **−51,868,567.66** |
| 5 | 15 | 34,774,811.06 | **−73,491,294.43** |
| 10 | 30 | **−49,641,729.77** | **−157,907,835.26** |

La fila K=1 es la que hay que citar el lunes: **quitando UNA sola operación de cada estrategia —tres
en total, el 0.12 % de la muestra— los 7 meses quedan en +1,052,242 CLP**, es decir el **2.7 %** del
neto declarado. El enunciado original de D171 (30 operaciones → −49,6 MM) **se sostiene y empeora**:
hoy son −157,9 MM.

**Veredicto: el juicio de D171 CAMBIA de "riesgo de concentración serio" a "el neto de 7 meses no
sobrevive a quitar 3 operaciones de 2,542".** Bajo la métrica **D170** —neto + consistencia
mensual + recorte top-K— esto es determinante y hay que decirlo sin suavizar: **el substrato
reparado NO pasa el criterio de recorte top-K**. Un track cuyo resultado positivo depende de 3
operaciones (0.12 % de la muestra) no tiene un edge demostrado en estos 7 meses; tiene un
resultado dominado por su cola.

Nota metodológica que evita una mala lectura: el recorte de `b1_robustness.py` es por **|net|**
(`_trim_key = -abs(net)`), así que quita indistintamente ganadoras y perdedoras. Que el neto caiga
al recortar significa que **las mayores por magnitud son ganadoras netas**, no que se hayan
eliminado solo las buenas a propósito.

**Esto es lo más importante del diff después del propio neto, y no puede faltar en el documento
del lunes.** Es también, por sí solo, justificación suficiente para la Entrada 6 de la cola de
backtests largos (concentración del neto), que queda **confirmada como prioritaria**.

---

## V12 — Grilla mensual · **CAMBIA en nivel, SE SOSTIENE en forma**

**Veredicto:** la grilla del reporte mensual (`REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md`)
es válida y es la que va al documento; la anterior queda **superada**, no corregida.

Lo que **SE SOSTIENE**:
- El **perfil de signo mensual** (5 positivos / 2 negativos, mismos meses) — ver tabla en §V10.
- **SuperTrend idéntico en las 7 filas y el TOTAL** (Δ = 0 en las 24 celdas). Es un control
  interno excelente: la estrategia sin stop-and-reverse no se movió ni un peso, exactamente como
  predice el mecanismo del bug.
- **Abril sigue siendo el peor mes** y mayo/enero los mejores.

Lo que **CAMBIA**:
- Todos los niveles bajan; los 7 meses tienen Δnet < 0, sin excepción.
- El deterioro está **repartido**, no concentrado en un mes: las 195 filas nuevas se distribuyen
  36/24/27/24/27/39/18 entre enero y julio (medido sobre la columna `month` de las CSV), y la suma
  de su `net` por mes reproduce el Δnet mensual de §10.1 **al peso** (salvo el redondeo a CLP
  entero del propio reporte). Ningún mes explica el fenómeno; es sistemático.
- **Junio se agrava mucho:** −3.59 MM → −22.88 MM. Junio deja de ser "un mes plano ligeramente
  negativo" y pasa a ser el segundo peor mes del track.
- El maxDD mensual COMBINED sube de 114,092,025 a **129,150,945** (@0.67 lot).

---

## V13 — Validación contra la semana vivida (§10.5) · **SE SOSTIENE — y hay que explicar con cuidado por qué**

| | BT ops | BT neto CLP |
|---|---:|---:|
| S6-K2P0 | 30 → **30** | 76,306 → **76,306** |
| S7-TPNONE | 36 → **36** | 12,587 → **12,587** |
| SuperTrend | 4 → **4** | 15,106 → **15,106** |
| Combinado | 70 → **70** | 103,998 → **103,998** |

**Veredicto: SE SOSTIENE, con Δ = 0 en las 8 celdas.** El único ancla que conecta el backtest con
la realidad vivida **no se movió**. Eso es valioso y debe decirse: la reparación no rompió la
correspondencia entre el backtest y la semana que el user vio ocurrir.

🔴 **Pero hay que decir inmediatamente por qué no se movió, o la afirmación se vuelve una
trampa.** R4 lo midió sobre las CSV: en la ventana 2026-07-20..07-23 hay **70 posiciones y CERO
con `reason="reverse"`**. La semana de validación no contiene ni un solo cierre por reversión.

De ahí se siguen dos cosas simétricas, y el documento debe llevar las dos:

- ✅ **A favor:** la semana vivida confirma que el motor de reconstrucción sigue reproduciendo el
  vivo donde puede compararse, y que la reparación no introdujo ninguna distorsión ahí.
- ⚠️ **En contra:** esa misma semana **no puede corroborar el hallazgo del stop-and-reverse**,
  porque no contiene ninguno. Presentar la validación semanal como respaldo de las cifras nuevas
  sería un error lógico. Es un control de no-regresión, no una confirmación.

Y el caveat de siempre sigue vivo: el backtest da 70 operaciones y +103,998 CLP contra 116
operaciones y +282,373 CLP del track live combinado de esa semana. La brecha sim-vs-live no la
cerró esta reparación y **no debe presentarse como cerrada**.

---

## V14 — Completitud del substrato reparado · **INDETERMINADO acotado — el instrumento sigue sin ver parte de los cierres, y ahora sabemos cuántos**

R3 dejó explícitamente sin verificar la relación entre los cierres `reverse` crudos que R1 midió
(504 en S6, 240 en S7 = **744**) y las **195** filas que llegaron a las CSV. R4 lo midió.

**Medición ejecutada por R4** (script read-only en el scratchpad de la sesión, `r4_survival.py`:
importa `backtest.py` y llama solo a `load_bars()` y `run_ladder()`, **no escribe nada**, no
invoca `main()` ni `build_all()`; el lado "resuelto" se lee de las CSV en disco). 🔴 **Declaración
de procedencia:** estas cifras las produjo código de forma reproducible, pero **no provienen de un
artefacto commiteado** — el conteo del ladder crudo no se persiste en ninguno. Se marcan como tal.

| Motivo | filas crudas del ladder | filas resueltas en CSV | supervivencia |
|---|---:|---:|---:|
| `EXIT_SL_RAISED` | 5,331 | 1,980 | **37.1 %** |
| `EXIT_INITSL` | 45 | 15 | 33.3 % |
| `EXIT_TRAIL` | 297 | 84 | 28.3 % |
| **`reverse`** | **744** | **195** | **26.2 %** |
| **TOTAL S6+S7** | **6,417** | **2,274** | **35.4 %** |

**Mecanismo, verificado en el código (sin modificarlo):** `resolve()` devuelve `None` y descarta la
posición cuando ninguna barra de la ventana de reintento tiene un tick con spread ≈ 0.5
(`abs(sp - 0.5) <= 0.05`, `MAX_RETRY_BARS = 1`), y además corta la ventana con
`if tc >= pos["t_out"] + BAR_SEC: break`. Esto **espeja el vivo a propósito**: si la ficha nunca
pudo abrirse a 0.5, en la cuenta real no existió.

**Dictamen en tres partes:**

1. **La supervivencia de `reverse` (26.2 %) es MENOR que la media (35.4 %), pero NO es anómala.**
   Está en la misma banda que `EXIT_TRAIL` (28.3 %) y `EXIT_INITSL` (33.3 %). No hay indicio de que
   el gate discrimine contra las reversiones por su naturaleza.
2. **La causa del déficit está identificada y es de duración, no de motivo.** Las posiciones
   cerradas por reversión son más cortas: mediana 4 barras (S6) y 3 (S7) frente a 7 y 4 del resto;
   y la fracción que dura ≤1 barra es **7.1 % vs 1.2 %** en S6 y **13.8 % vs 3.5 %** en S7. Una
   posición corta tiene menos cierres de barra donde intentar entrar a 0.5, luego se descarta más.
   El sesgo es **estructural por duración** y afecta a cualquier motivo de vida corta.
3. 🔴 **Sí, el veredicto de completitud DEBE declarar que el instrumento sigue sin ver una parte de
   los cierres reales — pero por diseño, no por bug.** De los 6,417 emparejamientos crudos solo
   2,274 (35.4 %) llegan al libro; **549 cierres `reverse` crudos quedan fuera**. Eso no es un
   segundo bug de emparejamiento: es el gate de spread 0.5 haciendo su trabajo de espejo del vivo.
   **Lo que R1 arregló está arreglado**: los `reverse` ya no se pierden en el emparejamiento; los
   que faltan faltan por la misma razón por la que faltan 3,594 cierres de todos los demás motivos.

**Qué queda INDETERMINADO, y qué haría falta:** si el corte de ventana (`MAX_RETRY_BARS = 1` más el
`break` en `t_out`) es un espejo **fiel** del reintento close-driven del vivo para posiciones de 1–2
barras, o si penaliza de más a las posiciones cortas. Como las reversiones son la población corta
**y** la población perdedora, un sesgo ahí desplazaría el resultado. **Dirección del sesgo: no
determinable** con los artefactos actuales — las 549 filas descartadas no tienen fills, así que su
neto no existe en ningún sitio. Para determinarlo haría falta instrumentar `resolve()` para emitir
las descartadas con el motivo del descarte y un fill contrafactual — trabajo del programa
post-lunes, **sobre copia** (R1-bis), nunca sobre el original a estas horas.

⚠️ **Consecuencia honesta para el lunes:** el 39.5 MM es la mejor cifra disponible, **no una cifra
cerrada**. La dirección del error residual es desconocida.

---

## V15 — Dónde el dato contradice al tracker, al plan o al controlador

Se registran explícitamente, como pide la norma de arbitraje. En los tres casos **gana el dato**.

1. **Contra el PLAN — el "bug 2" (fills) no existía.** El plan afirmaba que `resolve()` inventaba
   fills. R2 lo midió: `EXIT_INITSL` cruza **891/891** (S6) y **1104/1104** (S7) dentro de su
   barra. Refutado. Lo que había era una **etiqueta gruesa**, corregida por R2-bis en la capa de
   análisis. 🔴 **Impacto directo en la entrega:** la corrección narrativa nº 4 del tracker
   («disclosure bug reverse+fills») haría que el documento del lunes **afirmara un bug que la
   medición desmintió**. Debe reescribirse (§V17, punto 4).

2. **Contra el CONTROLADOR — la re-atribución de filas no ocurrió.** El controlador corrigió la
   expectativa del plan escribiendo que «R1 no solo AÑADE filas: **re-atribuye** algunas
   existentes» y que el gate pass-fail del plan «daría falsa alarma». **El dato dice 0 filas
   re-atribuidas y 0 desaparecidas**, con las 2,347 filas viejas conservando su `net` al céntimo.
   Es decir: **la expectativa original del plan era correcta y la corrección del controlador era
   equivocada.** El gate pass-fail que el plan proponía habría **pasado**, no dado falsa alarma.

   *Por qué el dato tiene sentido mecánico* (y no es casualidad): al no emparejarse el `reverse`,
   la ficha quedaba abierta en `open_pos`, y la siguiente entrada de esa misma ficha **sobreescribía**
   la anterior; el cierre posterior emparejaba con la entrada nueva. Resultado: la fila que sí se
   emitía era **correcta**, y la pierna del reverse **desaparecía entera y en silencio**. Eso
   produce exactamente el patrón medido: 0 re-atribuidas, 195 filas nuevas con `(t_in, ficha)`
   inexistentes en el baseline. **La cuantificación de R3 no era una red de seguridad
   innecesaria** —fue lo que permitió detectar que la corrección era falsa—, pero su motivación
   declarada era errónea.

3. **Contra el TRACKER — dos afirmaciones commiteadas quedan superadas:**
   - Task 7: «maxDD −28,57 % · **CONFIRMA** la estimación previa de −28,6 %» → hoy **−32,34 %**
     (§V2). La frase «confirma» no puede repetirse.
   - Task 16: «el signo se da vuelta entre 60 y 90 [minutos]» / «N6 −15,24 %» → hoy **los cinco
     peldaños son positivos**, N6 = **+3.38 %** (§V9).
   - Task 9 (A3): «el grueso sale por `EXIT_INITSL` y es rentable» → **inducía a error** en las dos
     mitades (§V5).

---

## V16 — Riesgos y no-evaluables

**Lo que NO puede concluirse con este dato, y qué haría falta para concluirlo:**

1. **No puede concluirse que el stop-and-reverse deba desactivarse.** Falta el contrafactual: qué
   habrían hecho esas 195 posiciones sin reversión, corriendo hasta su stop o su trailing. Haría
   falta una corrida de backtest sobre **copia** con el reverse desactivado, comparada bajo D170
   completo. *(Este resultado empuja fuerte esa pregunta a la cabeza de la cola del programa
   post-lunes — señalado, no planificado.)*
2. **No puede concluirse que 39,5 MM sea la cifra definitiva.** Ver §V14: 549 cierres `reverse`
   crudos quedan fuera por el gate/ventana, y la dirección del sesgo residual es indeterminable
   con los artefactos existentes.
3. **No puede concluirse nada sobre el gate de spread 0.6.** Cero filas. Sigue no evaluable (§V7).
4. **No puede concluirse que B1 funcione fuera de muestra.** Los cinco peldaños, el ranking y las
   tres pruebas de robustez son **in-sample** sobre los mismos 7 meses. El propio artefacto lo
   declara en su `caveat`. Haría falta un periodo out-of-sample.
5. **No puede concluirse que el edge del track sea estadísticamente distinto de cero.** PF 1.0333,
   y el neto no sobrevive a recortar 3 operaciones (§V11). Haría falta más historia, o una prueba
   de significancia sobre el propio libro — que **nadie ha corrido**, así que hoy es no evaluable.
6. **No puede concluirse que el cap B3 sea un control de riesgo validado.** `dropped_n = 0` por
   construcción (§V3). Es un fusible sin evidencia de haber sido necesario.
7. **No puede concluirse que la brecha sim-vs-live esté cerrada** (§V13): 70 ops / +104 k en
   backtest contra 116 ops / +282 k en vivo, en la misma semana.
8. **B2 y B4 siguen sin evidencia**, no sin problema: B2 solo cubre NFP; B4 no es enmascarable.

**Qué queda tocado del programa post-lunes** (señalado, no planificado):
- **Entrada 6 de la cola de backtests largos (concentración del neto): confirmada como
  prioritaria** — §V11 la convierte en el riesgo dominante, no en uno más.
- **Task 15 (escalera de distancia de SL)** debe correr sobre el substrato reparado; sus
  resultados sobre el viejo no serían comparables.
- **Afinar la etiqueta de salida del motor** (item ya registrado): §V5 muestra que el motor
  etiqueta mal 1,980 de 2,542 cierres. Sigue siendo trabajo **sobre copia**.
- **Instrumentar el descarte de `resolve()`** (§V14) se añade como candidato nuevo al programa.
- **Task 12** queda **liberada** del condicionante del cap B3 (§V3): el cap no se movió.

---

## V17 — Correcciones OBLIGATORIAS para Task 13 (documento del lunes)

Lista cerrada, numerada y accionable. Quien escriba el documento **no debe interpretar nada**: cada
punto dice qué afirmar y qué no.

**1. El titular del neto, y cómo se comunica la caída (lo más delicado de toda la entrega).**
 - **Afirmar:** «El neto reconstruido de 7 meses es **39,513,979 CLP** (0.67 lot/ficha, gate 0.5),
   con PF **1.033**, WR **32.26 %** sobre **2,542** posiciones.»
 - **Afirmar, en el mismo párrafo y sin separarlo:** «La cifra anterior de 147,780,084 CLP
   **no era el resultado del sistema**: era el resultado de una medición a la que le faltaba una
   población entera de cierres. El emparejador del backtest descartaba los cierres por
   stop-and-reverse — un mecanismo que en S6/S7 **está activo en la cuenta real y se dispara**.»
 - **Afirmar la prueba:** «Las 2,347 posiciones que el backtest ya mostraba conservan su resultado
   **idéntico al céntimo** (0 re-atribuidas, 0 desaparecidas). La diferencia completa son **195
   posiciones nuevas** que antes no aparecían.»
 - 🔴 **PROHIBIDO afirmar o insinuar:** que las estrategias empeoraron, que el rendimiento cayó,
   que "perdimos" 108 MM, o cualquier redacción con verbo de cambio temporal ("bajó", "se
   deterioró"). Nada bajó. **Cambió el instrumento, no el sistema.**
 - 🔴 **PROHIBIDO también la dirección contraria:** presentar la caída como un tecnicismo contable
   sin consecuencias. Sí tiene consecuencia: el edge real del track es mucho menor de lo que se
   creía y el PF está en 1.03.

**2. maxDD.** Sustituir **−28,57 %** por **−32,34 % del balance inicial** (−19,276,260 CLP @0.1 lot;
−25,07 % del pico de equity). **Eliminar la frase «CONFIRMA la estimación previa de −28,6 %»** —
ya no es cierta. Al citar `trough_equity` negativo, decir «el P&L acumulado llegó a estar 1.99 MM
por debajo de su punto de partida (saldo de 76.9 MM a 57.6 MM)»; **no** decir que la cuenta se
agotó. *(Sustituye a la fila de maxDD del tracker.)*

**3. Correlaciones — corrección ya existente, con números actualizados.** «SuperTrend es casi
independiente» **no se usa**. Redacción: S6\|S7 **+0.767**, S6\|ST **+0.356**, S7\|ST **+0.153**,
sobre **163** días. Añadir la lectura de riesgo: SuperTrend es la única pata poco correlacionada
**y aporta el 53 % del neto reparado con 268 posiciones**.

**4. 🔴 REESCRITA — el disclosure de bugs.** La corrección nº 4 del tracker decía «disclosure bug
reverse+**fills**». **Hay UN bug y UNA etiqueta engañosa, no dos bugs.** Redacción obligatoria:
 - **Bug real (corregido, commit `fadf1ec`):** `run_ladder` no emparejaba los cierres `reverse`.
   Impacto: +195 posiciones, −108,266,105 CLP.
 - **Bug que se sospechaba y NO existe (refutado por medición):** se creía que `resolve()` inventaba
   fills. **Falso**: `EXIT_INITSL` cruza 891/891 (S6) y 1104/1104 (S7) dentro de su barra. El
   documento **no debe afirmar este bug**.
 - **Etiqueta engañosa (corregida en la capa de análisis, commit `2823160`):** el motor marcaba
   `EXIT_INITSL` a stops ya levantados por trailing/BE.

**5. 🔴 OBSOLETA — retirar.** La corrección nº 3 del tracker («reporte mensual regenerado **sin
snapshot previo**, no hay diff viejo-contra-nuevo») **ya no aplica**: R3a (`b3c53e2`) creó el
snapshot inmutable y este documento **es** el diff viejo-contra-nuevo. Sustituir por: «existe
snapshot pre-reparación verificado por sha256 y diff número-por-número
(`2026-07-27-substrate-repair-diff.md`)».

**6. Atribución por motivo de salida (corrección narrativa nº 1).** Sustituir la versión de Task 9.
Afirmar: **el track gana con el trailing y pierde con las reversiones**. `EXIT_SL_RAISED` 1,980
cierres +129.1 MM · `EXIT_STLINE` 268 +21.0 MM · `EXIT_TRAIL` 84 +12.6 MM · **`reverse` 195
−108.3 MM** · `EXIT_INITSL` genuino **15** cierres, **WR 0 %**, −14.9 MM. Decir explícitamente que
el stop inicial genuino se toca en **0.6 %** de los cierres. **No** repetir «el grueso sale por
stop inicial y es rentable».

**7. 🆕 La asimetría del stop-and-reverse.** Afirmar: media por reversión **−555,211 CLP** contra
**+62,966** de la media del resto del libro (**8.8×**, signo invertido); **183 de 195 pierden**
(WR 6.15 %); mediana −519,533. Dar la lectura mecánica: la reversión **corta la pérdida, no la
evita**. 🔴 **No concluir que haya que desactivarla** — falta el contrafactual (§V16.1).

**8. 🆕 Concentración del neto (D171).** Afirmar: **quitar las 3 operaciones mayores por |net| deja
el neto de 7 meses en −7,557,696 CLP**; quitar 10 lo deja en −66,525,916. La operación mayor sola
vale el **60 %** del neto. En la vista por estrategia: **quitando la mayor de cada una (3 ops, 0.12 %
de la muestra) quedan +1,052,242 CLP**, el 2.7 % del neto declarado; quitando 30 (10 por estrategia),
−157,907,835 CLP. Decir que **las mismas operaciones dominaban el libro antes** (las sumas top-K son
idénticas al céntimo): lo que cambió es que ahora el resto del libro ya no las compensa. Bajo D170,
**el track no supera el criterio de recorte top-K**, y así debe declararse.

**9. B1 @50 min.** Veredicto **NO-VETO se mantiene**. Citar en CLP: 227 posiciones vetadas,
**+40,788,967 CLP** (de 39.5 MM a 80.3 MM). 🔴 Si se cita el **+103.23 %**, va obligatoriamente con
la aclaración de que el porcentaje está inflado por la caída de la base (la mejora en CLP subió
38 %, no 400 %). Mantener el caveat de que el signo no es estable y que 50 min se fijó de antemano.

**10. Task 16 / curva B1.** Ranking **N3 > N4 > N5 > N2 > N6** (N2 y N5 intercambiados respecto de
lo publicado). 🔴 **Corregir**: la frase «el signo se da vuelta entre 60 y 90 minutos» **ya no es
cierta** — los cinco peldaños son positivos, N6 = +3.38 %. Mantener «joroba, no codo» y el caveat
in-sample. Registrar que el ranking sobrevive el recorte top-K **hasta K=5 y se rompe en K=10**
(antes se afirmaba que sobrevivía).

**11. Consistencia mensual — el argumento bueno, úsese.** Afirmar que el **perfil de signo mensual
del libro no cambió**: los mismos 5 meses positivos y 2 negativos (abril, junio), sin una sola
inversión. Es la evidencia más limpia de que esto fue un cambio de instrumento. Añadir que junio
se agrava de −3.6 MM a −22.9 MM y que la mejora de B1 sigue dependiendo de febrero
(+64.9 MM de delta sobre un total de 40.8 MM).

**12. Grilla mensual — corrección ya existente, con la fuente actualizada.** Usar la grilla
regenerada; declarar que **SuperTrend sale idéntico en las 24 celdas** (control interno de que el
bug afectaba solo a las estrategias con stop-and-reverse).

**13. Validación contra la semana vivida.** Afirmar: **Δ = 0 en las 8 celdas** (70 ops, +103,998
CLP). 🔴 Decir en la misma frase que esa semana **no contiene ningún cierre `reverse`**, así que es
un control de **no-regresión**, no una confirmación de las cifras nuevas. Mantener la brecha
sim-vs-live declarada (116 ops / +282,373 CLP en vivo).

**14. 🆕 Completitud declarada.** Afirmar: el gate de spread 0.5 (espejo del vivo) descarta el
64.6 % de los emparejamientos crudos, incluidos **549 cierres `reverse`**; la tasa de supervivencia
de `reverse` (26.2 %) es menor que la media (35.4 %) pero está en la banda de `EXIT_TRAIL`
(28.3 %), y la causa medida es la **duración corta** de esas posiciones, no su motivo. Declarar que
**39,5 MM es la mejor cifra disponible, no una cifra cerrada**, y que la dirección del sesgo
residual **no es determinable** hoy.

**15. Cap B3 y roster.** Afirmar que `max_simultaneous_fichas` sigue en **7** tras la regeneración
y que el roster retador (`CONFIGS_CHALLENGER`, magics 726xxx) **no requirió ningún cambio**.
Presentar B3 como **fusible** (0 descartes por construcción), no como control de riesgo validado.

**16. A5 spread.** Repetir sin cambios el veredicto **NO EVALUABLE**: 2,542 filas, **100 % a 0.5,
cero a 0.6**. No afirmar que el gate 0.5 «está validado sobre 7 meses».

**17. Tono general.** El documento debe poder leerse por alguien que apostó dinero a la cifra
anterior. Dos frases que deben aparecer literalmente en alguna forma: **(a)** «ninguna operación
que ya mostrábamos cambió de resultado»; **(b)** «lo que cambió es que ahora contamos todas las
operaciones que la cuenta real ejecuta».

---

*Fin de §Veredictos — Task R4, Opus 5 high, 2026-07-27. Ningún `.py` fue modificado. El roster
retador no fue tocado. Todas las cifras proceden de artefactos en disco salvo las de §V14, cuya
procedencia se declara ahí.*
