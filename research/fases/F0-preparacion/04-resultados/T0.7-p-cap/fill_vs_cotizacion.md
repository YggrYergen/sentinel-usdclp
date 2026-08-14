# fill_vs_cotizacion -- F0-A6-FILL-0001

Comando: `python scripts/analysis/realtick_bt/faulty/fill_vs_cotizacion.py`

Fecha: 2026-08-14

REPORT-ONLY. Sin interpretación.

## Global

### global

n_eventos = 304

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0000 | 0.0540 | 0.5400 | 287 |
| dist_min_1 | 0.0000 | 0.0500 | 0.5300 | 300 |
| dist_min_2 | 0.0000 | 0.0400 | 0.4800 | 302 |
| dist_min_5 | 0.0000 | 0.0200 | 0.4800 | 304 |
| dist_min_30 | 0.0000 | 0.0100 | 0.1300 | 304 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 53.29 | 162 | 304 |
| hit_exacto_vigente | 19.08 | 58 | 304 |
| hit_exacto_segundo_lado_opuesto | 0.66 | 2 | 304 |
| hit_exacto_1 | 65.13 | 198 | 304 |
| hit_exacto_2 | 68.75 | 209 | 304 |
| hit_exacto_5 | 73.03 | 222 | 304 |
| hit_exacto_30 | 84.87 | 258 | 304 |
| dentro_rango_segundo | 86.84 | 264 | 304 |
| dentro_rango_1 | 98.68 | 300 | 304 |
| dentro_rango_2 | 99.34 | 302 | 304 |
| dentro_rango_5 | 100.00 | 304 | 304 |
| dentro_rango_30 | 100.00 | 304 | 304 |

n_ticks_segundo_cero = 17, n_vigente_no_evaluable = 0, n_ticks_1_cero = 4, n_ticks_2_cero = 2, n_ticks_5_cero = 0, n_ticks_30_cero = 0

## Por evento

### evento = OPEN

n_eventos = 152

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0000 | 0.0100 | 0.1500 | 138 |
| dist_min_1 | 0.0000 | 0.0000 | 0.0000 | 149 |
| dist_min_2 | 0.0000 | 0.0000 | 0.0000 | 150 |
| dist_min_5 | 0.0000 | 0.0000 | 0.0000 | 152 |
| dist_min_30 | 0.0000 | 0.0000 | 0.0000 | 152 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 78.95 | 120 | 152 |
| hit_exacto_vigente | 31.58 | 48 | 152 |
| hit_exacto_segundo_lado_opuesto | 0.66 | 1 | 152 |
| hit_exacto_1 | 98.03 | 149 | 152 |
| hit_exacto_2 | 98.68 | 150 | 152 |
| hit_exacto_5 | 100.00 | 152 | 152 |
| hit_exacto_30 | 100.00 | 152 | 152 |
| dentro_rango_segundo | 82.89 | 126 | 152 |
| dentro_rango_1 | 98.03 | 149 | 152 |
| dentro_rango_2 | 98.68 | 150 | 152 |
| dentro_rango_5 | 100.00 | 152 | 152 |
| dentro_rango_30 | 100.00 | 152 | 152 |

n_ticks_segundo_cero = 14, n_vigente_no_evaluable = 0, n_ticks_1_cero = 3, n_ticks_2_cero = 2, n_ticks_5_cero = 0, n_ticks_30_cero = 0

### evento = CLOSE

n_eventos = 152

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0200 | 0.0840 | 0.5400 | 149 |
| dist_min_1 | 0.0100 | 0.0800 | 0.5300 | 151 |
| dist_min_2 | 0.0100 | 0.0600 | 0.4800 | 152 |
| dist_min_5 | 0.0100 | 0.0500 | 0.4800 | 152 |
| dist_min_30 | 0.0000 | 0.0200 | 0.1300 | 152 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 27.63 | 42 | 152 |
| hit_exacto_vigente | 6.58 | 10 | 152 |
| hit_exacto_segundo_lado_opuesto | 0.66 | 1 | 152 |
| hit_exacto_1 | 32.24 | 49 | 152 |
| hit_exacto_2 | 38.82 | 59 | 152 |
| hit_exacto_5 | 46.05 | 70 | 152 |
| hit_exacto_30 | 69.74 | 106 | 152 |
| dentro_rango_segundo | 90.79 | 138 | 152 |
| dentro_rango_1 | 99.34 | 151 | 152 |
| dentro_rango_2 | 100.00 | 152 | 152 |
| dentro_rango_5 | 100.00 | 152 | 152 |
| dentro_rango_30 | 100.00 | 152 | 152 |

n_ticks_segundo_cero = 3, n_vigente_no_evaluable = 0, n_ticks_1_cero = 1, n_ticks_2_cero = 0, n_ticks_5_cero = 0, n_ticks_30_cero = 0

## Por reason_name (sólo cierres)

### reason_name = SL

n_eventos = 119

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0200 | 0.1000 | 0.5400 | 119 |
| dist_min_1 | 0.0200 | 0.1000 | 0.5300 | 119 |
| dist_min_2 | 0.0100 | 0.0800 | 0.4800 | 119 |
| dist_min_5 | 0.0100 | 0.0520 | 0.4800 | 119 |
| dist_min_30 | 0.0000 | 0.0200 | 0.1300 | 119 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 15.13 | 18 | 119 |
| hit_exacto_vigente | 0.00 | 0 | 119 |
| hit_exacto_segundo_lado_opuesto | 0.84 | 1 | 119 |
| hit_exacto_1 | 15.13 | 18 | 119 |
| hit_exacto_2 | 22.69 | 27 | 119 |
| hit_exacto_5 | 31.93 | 38 | 119 |
| hit_exacto_30 | 62.18 | 74 | 119 |
| dentro_rango_segundo | 94.12 | 112 | 119 |
| dentro_rango_1 | 100.00 | 119 | 119 |
| dentro_rango_2 | 100.00 | 119 | 119 |
| dentro_rango_5 | 100.00 | 119 | 119 |
| dentro_rango_30 | 100.00 | 119 | 119 |

n_ticks_segundo_cero = 0, n_vigente_no_evaluable = 0, n_ticks_1_cero = 0, n_ticks_2_cero = 0, n_ticks_5_cero = 0, n_ticks_30_cero = 0

### reason_name = EXPERT

n_eventos = 21

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0000 | 0.0200 | 0.0300 | 18 |
| dist_min_1 | 0.0000 | 0.0000 | 0.0000 | 20 |
| dist_min_2 | 0.0000 | 0.0000 | 0.0000 | 21 |
| dist_min_5 | 0.0000 | 0.0000 | 0.0000 | 21 |
| dist_min_30 | 0.0000 | 0.0000 | 0.0000 | 21 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 66.67 | 14 | 21 |
| hit_exacto_vigente | 33.33 | 7 | 21 |
| hit_exacto_segundo_lado_opuesto | 0.00 | 0 | 21 |
| hit_exacto_1 | 95.24 | 20 | 21 |
| hit_exacto_2 | 100.00 | 21 | 21 |
| hit_exacto_5 | 100.00 | 21 | 21 |
| hit_exacto_30 | 100.00 | 21 | 21 |
| dentro_rango_segundo | 66.67 | 14 | 21 |
| dentro_rango_1 | 95.24 | 20 | 21 |
| dentro_rango_2 | 100.00 | 21 | 21 |
| dentro_rango_5 | 100.00 | 21 | 21 |
| dentro_rango_30 | 100.00 | 21 | 21 |

n_ticks_segundo_cero = 3, n_vigente_no_evaluable = 0, n_ticks_1_cero = 1, n_ticks_2_cero = 0, n_ticks_5_cero = 0, n_ticks_30_cero = 0

### reason_name = CLIENT_manual

n_eventos = 11

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0000 | 0.0000 | 0.0100 | 11 |
| dist_min_1 | 0.0000 | 0.0000 | 0.0000 | 11 |
| dist_min_2 | 0.0000 | 0.0000 | 0.0000 | 11 |
| dist_min_5 | 0.0000 | 0.0000 | 0.0000 | 11 |
| dist_min_30 | 0.0000 | 0.0000 | 0.0000 | 11 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 90.91 | 10 | 11 |
| hit_exacto_vigente | 27.27 | 3 | 11 |
| hit_exacto_segundo_lado_opuesto | 0.00 | 0 | 11 |
| hit_exacto_1 | 100.00 | 11 | 11 |
| hit_exacto_2 | 100.00 | 11 | 11 |
| hit_exacto_5 | 100.00 | 11 | 11 |
| hit_exacto_30 | 100.00 | 11 | 11 |
| dentro_rango_segundo | 100.00 | 11 | 11 |
| dentro_rango_1 | 100.00 | 11 | 11 |
| dentro_rango_2 | 100.00 | 11 | 11 |
| dentro_rango_5 | 100.00 | 11 | 11 |
| dentro_rango_30 | 100.00 | 11 | 11 |

n_ticks_segundo_cero = 0, n_vigente_no_evaluable = 0, n_ticks_1_cero = 0, n_ticks_2_cero = 0, n_ticks_5_cero = 0, n_ticks_30_cero = 0

### reason_name = TP

n_eventos = 1

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0200 | 0.0200 | 0.0200 | 1 |
| dist_min_1 | 0.0200 | 0.0200 | 0.0200 | 1 |
| dist_min_2 | 0.0200 | 0.0200 | 0.0200 | 1 |
| dist_min_5 | 0.0200 | 0.0200 | 0.0200 | 1 |
| dist_min_30 | 0.0100 | 0.0100 | 0.0100 | 1 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 0.00 | 0 | 1 |
| hit_exacto_vigente | 0.00 | 0 | 1 |
| hit_exacto_segundo_lado_opuesto | 0.00 | 0 | 1 |
| hit_exacto_1 | 0.00 | 0 | 1 |
| hit_exacto_2 | 0.00 | 0 | 1 |
| hit_exacto_5 | 0.00 | 0 | 1 |
| hit_exacto_30 | 0.00 | 0 | 1 |
| dentro_rango_segundo | 100.00 | 1 | 1 |
| dentro_rango_1 | 100.00 | 1 | 1 |
| dentro_rango_2 | 100.00 | 1 | 1 |
| dentro_rango_5 | 100.00 | 1 | 1 |
| dentro_rango_30 | 100.00 | 1 | 1 |

n_ticks_segundo_cero = 0, n_vigente_no_evaluable = 0, n_ticks_1_cero = 0, n_ticks_2_cero = 0, n_ticks_5_cero = 0, n_ticks_30_cero = 0

## Por estrategia

### strategy_id = SAR::S6-K2P0

n_eventos = 168

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0000 | 0.0500 | 0.1500 | 156 |
| dist_min_1 | 0.0000 | 0.0400 | 0.1400 | 165 |
| dist_min_2 | 0.0000 | 0.0400 | 0.1000 | 167 |
| dist_min_5 | 0.0000 | 0.0200 | 0.1000 | 168 |
| dist_min_30 | 0.0000 | 0.0100 | 0.0500 | 168 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 54.76 | 92 | 168 |
| hit_exacto_vigente | 20.24 | 34 | 168 |
| hit_exacto_segundo_lado_opuesto | 1.19 | 2 | 168 |
| hit_exacto_1 | 68.45 | 115 | 168 |
| hit_exacto_2 | 73.21 | 123 | 168 |
| hit_exacto_5 | 77.38 | 130 | 168 |
| hit_exacto_30 | 88.10 | 148 | 168 |
| dentro_rango_segundo | 85.12 | 143 | 168 |
| dentro_rango_1 | 98.21 | 165 | 168 |
| dentro_rango_2 | 99.40 | 167 | 168 |
| dentro_rango_5 | 100.00 | 168 | 168 |
| dentro_rango_30 | 100.00 | 168 | 168 |

n_ticks_segundo_cero = 12, n_vigente_no_evaluable = 0, n_ticks_1_cero = 3, n_ticks_2_cero = 1, n_ticks_5_cero = 0, n_ticks_30_cero = 0

### strategy_id = SuperTrend::SuperTrend-p14x3-M15

n_eventos = 136

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0000 | 0.0700 | 0.5400 | 131 |
| dist_min_1 | 0.0000 | 0.0560 | 0.5300 | 135 |
| dist_min_2 | 0.0000 | 0.0460 | 0.4800 | 135 |
| dist_min_5 | 0.0000 | 0.0200 | 0.4800 | 136 |
| dist_min_30 | 0.0000 | 0.0100 | 0.1300 | 136 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 51.47 | 70 | 136 |
| hit_exacto_vigente | 17.65 | 24 | 136 |
| hit_exacto_segundo_lado_opuesto | 0.00 | 0 | 136 |
| hit_exacto_1 | 61.03 | 83 | 136 |
| hit_exacto_2 | 63.24 | 86 | 136 |
| hit_exacto_5 | 67.65 | 92 | 136 |
| hit_exacto_30 | 80.88 | 110 | 136 |
| dentro_rango_segundo | 88.97 | 121 | 136 |
| dentro_rango_1 | 99.26 | 135 | 136 |
| dentro_rango_2 | 99.26 | 135 | 136 |
| dentro_rango_5 | 100.00 | 136 | 136 |
| dentro_rango_30 | 100.00 | 136 | 136 |

n_ticks_segundo_cero = 5, n_vigente_no_evaluable = 0, n_ticks_1_cero = 1, n_ticks_2_cero = 1, n_ticks_5_cero = 0, n_ticks_30_cero = 0

## Por side

### side = BUY

n_eventos = 164

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0000 | 0.0700 | 0.4100 | 160 |
| dist_min_1 | 0.0000 | 0.0500 | 0.3000 | 162 |
| dist_min_2 | 0.0000 | 0.0400 | 0.3000 | 162 |
| dist_min_5 | 0.0000 | 0.0200 | 0.3000 | 164 |
| dist_min_30 | 0.0000 | 0.0100 | 0.1300 | 164 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 57.32 | 94 | 164 |
| hit_exacto_vigente | 14.02 | 23 | 164 |
| hit_exacto_segundo_lado_opuesto | 0.61 | 1 | 164 |
| hit_exacto_1 | 65.24 | 107 | 164 |
| hit_exacto_2 | 69.51 | 114 | 164 |
| hit_exacto_5 | 73.78 | 121 | 164 |
| hit_exacto_30 | 84.76 | 139 | 164 |
| dentro_rango_segundo | 90.85 | 149 | 164 |
| dentro_rango_1 | 98.78 | 162 | 164 |
| dentro_rango_2 | 98.78 | 162 | 164 |
| dentro_rango_5 | 100.00 | 164 | 164 |
| dentro_rango_30 | 100.00 | 164 | 164 |

n_ticks_segundo_cero = 4, n_vigente_no_evaluable = 0, n_ticks_1_cero = 2, n_ticks_2_cero = 2, n_ticks_5_cero = 0, n_ticks_30_cero = 0

### side = SELL

n_eventos = 140

| métrica | p50 | p90 | max | n_evaluable |
|---|---|---|---|---|
| dist_min_segundo | 0.0000 | 0.0500 | 0.5400 | 127 |
| dist_min_1 | 0.0000 | 0.0400 | 0.5300 | 138 |
| dist_min_2 | 0.0000 | 0.0310 | 0.4800 | 140 |
| dist_min_5 | 0.0000 | 0.0200 | 0.4800 | 140 |
| dist_min_30 | 0.0000 | 0.0100 | 0.0600 | 140 |

| métrica | % true | n_true | n |
|---|---|---|---|
| hit_exacto_segundo | 48.57 | 68 | 140 |
| hit_exacto_vigente | 25.00 | 35 | 140 |
| hit_exacto_segundo_lado_opuesto | 0.71 | 1 | 140 |
| hit_exacto_1 | 65.00 | 91 | 140 |
| hit_exacto_2 | 67.86 | 95 | 140 |
| hit_exacto_5 | 72.14 | 101 | 140 |
| hit_exacto_30 | 85.00 | 119 | 140 |
| dentro_rango_segundo | 82.14 | 115 | 140 |
| dentro_rango_1 | 98.57 | 138 | 140 |
| dentro_rango_2 | 100.00 | 140 | 140 |
| dentro_rango_5 | 100.00 | 140 | 140 |
| dentro_rango_30 | 100.00 | 140 | 140 |

n_ticks_segundo_cero = 13, n_vigente_no_evaluable = 0, n_ticks_1_cero = 2, n_ticks_2_cero = 0, n_ticks_5_cero = 0, n_ticks_30_cero = 0

## Signo de delta_vigente, por side x evento

| side|evento | n_total | n_evaluable | n_no_evaluable | mediana_con_signo | n_positivo | n_cero | n_negativo |
|---|---|---|---|---|---|---|---|
| BUY|OPEN | 82 | 82 | 0 | 0.0000 | 40 | 19 | 23 |
| BUY|CLOSE | 82 | 82 | 0 | -0.1800 | 8 | 4 | 70 |
| SELL|OPEN | 70 | 70 | 0 | 0.0000 | 17 | 29 | 24 |
| SELL|CLOSE | 70 | 70 | 0 | 0.1800 | 57 | 6 | 7 |
