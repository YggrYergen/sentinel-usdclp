# divergencia_neto -- T0.7-M-0

Comando: `python scripts/analysis/realtick_bt/faulty/divergencia_neto.py`

Fecha: 2026-08-15 · git_sha: `aa0a8052fa53ee5c0101e1cc317dc62337a94a68` · run_id: `T0.7-M-0-DIVNETO-0001`

REPORT-ONLY. Sin interpretación, sin veredicto. Divergencia situada junto a los umbrales 0.3% (aceptable) / 0.15% (ideal), sin emitirlo.

## 0 · Discrepancia brief vs artefacto (n emparejadas)

El brief (prosa, no el artefacto) menciona 137 posiciones emparejadas ('128 de 137', '131 de 137'). El artefacto p_cap_resultado.json (criterio_de_paso_6_campos.n_emparejadas) dice 135, y recomputado directamente de comparacion_p_cap.csv (140 evaluables - 5 sin pareja) da tambien 135. Se usa 135 (gana el artefacto, por instrucción del propio brief: 'Verifica contra el artefacto, nunca contra lo que yo te diga').

- brief (prosa): 137
- artefacto p_cap_resultado.json: 135
- recomputado de comparacion_p_cap.csv: 134

## 1 · Resultado monetario de cada posición de la réplica

Global: n=155, sum_bruto_usd=14053.92

| estrategia | n | sum_bruto_usd |
|---|---|---|
| SAR::S6-K2P0 | 86 | 6726.80 |
| SuperTrend::SuperTrend-p14x3-M15 | 69 | 7327.12 |

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

neto_real_usd=-12071.3900, neto_replica_usd=-9946.8200, diff_abs=2124.5700, divergencia_pct=17.600044 (n_real=134, n_replica=134)

Umbrales: aceptable ≤0.3%, ideal ≤0.15%. Sin veredicto.

Por estrategia:

| estrategia | neto_real_usd | neto_replica_usd | diff_abs | divergencia_pct | n |
|---|---|---|---|---|---|
| SAR::S6-K2P0 | 4411.9500 | 4319.4900 | -92.4600 | -2.095672 | 79 |
| SuperTrend::SuperTrend-p14x3-M15 | -16483.3400 | -14266.3100 | 2217.0300 | 13.450126 | 55 |

### Secundaria en pesos (población a), tasa emparejada por día de cierre de la réplica

neto_real_clp=-11156321.18, neto_replica_clp_estimado=-9226176.25, diff_abs=1930144.93, divergencia_pct=17.300909 (n_real=134, n_replica_evaluable=134)

Por estrategia (CLP, población a):

| estrategia | neto_real_clp | neto_replica_clp_est | diff_abs | divergencia_pct |
|---|---|---|---|---|
| SAR::S6-K2P0 | 3993575.88 | 3922604.19 | -70971.69 | -1.777146 |
| SuperTrend::SuperTrend-p14x3-M15 | -15149897.06 | -13148780.44 | 2001116.62 | 13.208780 |

### Conexión con el neto real registrado (16.146.299,81 CLP), población (b) = 152 real / 157 réplica, sin excluir nada

neto_real_clp (152, recomputado) = 16146299.81 (registrado en p_cap_resultado.json: 16146299.81)
neto_replica_clp_estimado (157, tasa por día) = 12766222.24 (n_evaluable=155/155)
diff_abs = -3380077.57, divergencia_pct = -20.934069

## 4 · ¿El sesgo es diferencial? (población a, USD)

claves: ['SAR::S6-K2P0', 'SuperTrend::SuperTrend-p14x3-M15']
mismo_signo: False
cociente_magnitud_abs_diff (diff2/diff1): 23.97826086956512
diff_abs_por_estrategia: {'SAR::S6-K2P0': -92.46000000000731, 'SuperTrend::SuperTrend-p14x3-M15': 2217.030000000166}
diff_por_posicion (diff_abs/n): {'SAR::S6-K2P0': -1.1703797468355357, 'SuperTrend::SuperTrend-p14x3-M15': 40.309636363639385}
diff_por_lote (diff_por_posicion/0.67): {'SAR::S6-K2P0': -1.7468354430381128, 'SuperTrend::SuperTrend-p14x3-M15': 60.16363636364087}
cociente_diff_por_posicion: 34.44150197628444

## 5 · Sensibilidad al conjunto evaluado

| población | n_real | n_replica | neto_real_usd | neto_replica_usd | diff_abs | divergencia_pct |
|---|---|---|---|---|---|---|
| (a) emparejadas evaluables | 134 | 134 | -12071.3900 | -9946.8200 | 2124.5700 | 17.600044 |
| (b) todas sin excluir | 152 | 155 | 17671.2500 | 14053.9200 | -3617.3300 | -20.470142 |
| (c) matched sin filtrar criterio | 146 | 146 | 20143.5500 | 16585.1800 | -3558.3700 | -17.665059 |

Excluidos del criterio (12, aparte, nunca fundidos en el neto): n=12, sum_real_bruto_usd=32214.94, sum_real_profit_clp=29572002.10

| categoría | n | sum_real_bruto_usd | sum_real_profit_clp |
|---|---|---|---|
| CLIENT_manual | 11 | 30965.39 | 28416355.78 |
| TP | 1 | 1249.55 | 1155646.32 |

## 6 · Descomposición de la divergencia (sobre población (b), USD)

term_replica_sin_pareja (10 posiciones) = -2531.2600
term_real_sin_pareja_neg (-1 × 5 posiciones) = 2472.3000
term_matched_diff (147 posiciones, réplica-real) = -3558.3700
suma_terminos = -3617.330000
diff_total (población b) = -3617.330000
residuo = -0.000000000 (-9.095e-13, ruido de punto flotante si es de este orden)

## 7 · No evaluables

- real_bruto_usd == 0 (división imposible para tasa implícita): 0
- reales sin réplica (fuera de comparación pareada): 6 (position_id: [55216338.0, 55333600.0, 55317670.0, 55318544.0, 55318552.0, 55321392.0])
- réplica sin real (fuera de comparación pareada): 9
- tasa del día no evaluable, población (a): 0
- tasa del día no evaluable, población (b): 0
- delta_precio_open nulo desde el origen (propagado, no relleno): 6
