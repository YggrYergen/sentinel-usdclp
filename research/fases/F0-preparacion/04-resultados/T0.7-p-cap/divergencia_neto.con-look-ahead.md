# divergencia_neto -- T0.7-M-0

Comando: `python scripts/analysis/realtick_bt/faulty/divergencia_neto.py`

Fecha: 2026-08-15 · git_sha: `d85ea1b85c73858e22b0265ebccd2c9cd06ff182` · run_id: `T0.7-M-0-DIVNETO-0001`

REPORT-ONLY. Sin interpretación, sin veredicto. Divergencia situada junto a los umbrales 0.3% (aceptable) / 0.15% (ideal), sin emitirlo.

## 0 · Discrepancia brief vs artefacto (n emparejadas)

El brief (prosa, no el artefacto) menciona 137 posiciones emparejadas ('128 de 137', '131 de 137'). El artefacto p_cap_resultado.json (criterio_de_paso_6_campos.n_emparejadas) dice 135, y recomputado directamente de comparacion_p_cap.csv (140 evaluables - 5 sin pareja) da tambien 135. Se usa 135 (gana el artefacto, por instrucción del propio brief: 'Verifica contra el artefacto, nunca contra lo que yo te diga').

- brief (prosa): 137
- artefacto p_cap_resultado.json: 135
- recomputado de comparacion_p_cap.csv: 135

## 1 · Resultado monetario de cada posición de la réplica

Global: n=157, sum_bruto_usd=12053.97

| estrategia | n | sum_bruto_usd |
|---|---|---|
| SAR::S6-K2P0 | 88 | 5398.86 |
| SuperTrend::SuperTrend-p14x3-M15 | 69 | 6655.11 |

Detalle posición a posición: ver `divergencia_neto.csv`, columna `bruto_usd` (filas del fichero réplica, 157) y `replica_bruto_usd` (vista unida con el real, en `divergencia_neto.csv` de comparacion_p_cap).

## 2 · CONTROL de la fórmula (antes de creer nada del punto 1)

n_bruto_usd_cero (división imposible, excluidas): 0

Tasa implícita global (152 reales evaluables):

n=152, p10=911.5001, p50=924.9750, p90=931.5001, min=908.4000, max=939.7000, dispersion_relativa=0.009309

Tasa implícita por día de cierre (dispersión relativa dentro de cada día):

| día | n | p50 | dispersion_relativa |
|---|---|---|---|
| 2026-07-28 | 22 | 931.5000 | 0.002448 |
| 2026-07-29 | 20 | 931.5000 | 0.001318 |
| 2026-07-30 | 5 | 933.0000 | 0.003401 |
| 2026-07-31 | 7 | 925.5000 | 0.000577 |
| 2026-08-02 | 7 | 930.7000 | 0.000000 |
| 2026-08-03 | 13 | 930.7000 | 0.002891 |
| 2026-08-04 | 20 | 911.5001 | 0.006816 |
| 2026-08-05 | 15 | 914.5000 | 0.001518 |
| 2026-08-06 | 10 | 916.9000 | 0.001346 |
| 2026-08-07 | 2 | 912.1500 | 0.005814 |
| 2026-08-09 | 13 | 913.7500 | 0.000304 |
| 2026-08-10 | 12 | 916.5000 | 0.002048 |
| 2026-08-11 | 6 | 917.5000 | 0.000445 |

## 3 · La divergencia de neto (cifra pedida)

### Primaria en dólares, población (a) = emparejadas evaluables (n=135, ver §0)

neto_real_usd=-12522.9700, neto_replica_usd=-10360.2100, diff_abs=2162.7600, divergencia_pct=17.270344 (n_real=135, n_replica=135)

Umbrales: aceptable ≤0.3%, ideal ≤0.15%. Sin veredicto.

Por estrategia:

| estrategia | neto_real_usd | neto_replica_usd | diff_abs | divergencia_pct | n |
|---|---|---|---|---|---|
| SAR::S6-K2P0 | 3960.3700 | 3128.9000 | -831.4700 | -20.994756 | 80 |
| SuperTrend::SuperTrend-p14x3-M15 | -16483.3400 | -13489.1100 | 2994.2300 | 18.165190 | 55 |

### Secundaria en pesos (población a), tasa emparejada por día de cierre de la réplica

neto_real_clp=-11576967.95, neto_replica_clp_estimado=-9612926.86, diff_abs=1964041.09, divergencia_pct=16.965073 (n_real=135, n_replica_evaluable=135)

Por estrategia (CLP, población a):

| estrategia | neto_real_clp | neto_replica_clp_est | diff_abs | divergencia_pct |
|---|---|---|---|---|
| SAR::S6-K2P0 | 3572929.11 | 2820314.94 | -752614.17 | -21.064347 |
| SuperTrend::SuperTrend-p14x3-M15 | -15149897.06 | -12433241.80 | 2716655.26 | 17.931840 |

### Conexión con el neto real registrado (16.146.299,81 CLP), población (b) = 152 real / 157 réplica, sin excluir nada

neto_real_clp (152, recomputado) = 16146299.81 (registrado en p_cap_resultado.json: 16146299.81)
neto_replica_clp_estimado (157, tasa por día) = 10905168.21 (n_evaluable=157/157)
diff_abs = -5241131.60, divergencia_pct = -32.460264

## 4 · ¿El sesgo es diferencial? (población a, USD)

claves: ['SAR::S6-K2P0', 'SuperTrend::SuperTrend-p14x3-M15']
mismo_signo: False
cociente_magnitud_abs_diff (diff2/diff1): 3.601128122482143
diff_abs_por_estrategia: {'SAR::S6-K2P0': -831.4699999999903, 'SuperTrend::SuperTrend-p14x3-M15': 2994.2300000001924}
diff_por_posicion (diff_abs/n): {'SAR::S6-K2P0': -10.393374999999878, 'SuperTrend::SuperTrend-p14x3-M15': 54.44054545454895}
diff_por_lote (diff_por_posicion/0.67): {'SAR::S6-K2P0': -15.512499999999816, 'SuperTrend::SuperTrend-p14x3-M15': 81.25454545455067}
cociente_diff_por_posicion: 5.2380045417922085

## 5 · Sensibilidad al conjunto evaluado

| población | n_real | n_replica | neto_real_usd | neto_replica_usd | diff_abs | divergencia_pct |
|---|---|---|---|---|---|---|
| (a) emparejadas evaluables | 135 | 135 | -12522.9700 | -10360.2100 | 2162.7600 | 17.270344 |
| (b) todas sin excluir | 152 | 157 | 17671.2500 | 12053.9700 | -5617.2800 | -31.787678 |
| (c) matched sin filtrar criterio | 147 | 147 | 19691.9700 | 15164.1100 | -4527.8600 | -22.993433 |

Excluidos del criterio (12, aparte, nunca fundidos en el neto): n=12, sum_real_bruto_usd=32214.94, sum_real_profit_clp=29572002.10

| categoría | n | sum_real_bruto_usd | sum_real_profit_clp |
|---|---|---|---|
| CLIENT_manual | 11 | 30965.39 | 28416355.78 |
| TP | 1 | 1249.55 | 1155646.32 |

## 6 · Descomposición de la divergencia (sobre población (b), USD)

term_replica_sin_pareja (10 posiciones) = -3110.1400
term_real_sin_pareja_neg (-1 × 5 posiciones) = 2020.7200
term_matched_diff (147 posiciones, réplica-real) = -4527.8600
suma_terminos = -5617.280000
diff_total (población b) = -5617.280000
residuo = 0.000000000 (1.819e-12, ruido de punto flotante si es de este orden)

## 7 · No evaluables

- real_bruto_usd == 0 (división imposible para tasa implícita): 0
- reales sin réplica (fuera de comparación pareada): 5 (position_id: [55333600.0, 55317670.0, 55318544.0, 55318552.0, 55321392.0])
- réplica sin real (fuera de comparación pareada): 10
- tasa del día no evaluable, población (a): 0
- tasa del día no evaluable, población (b): 0
- delta_precio_open nulo desde el origen (propagado, no relleno): 5
