# T0.7-p-cap -- censo de la cola de |delta t_open| (réplica vs. 152 posiciones reales, 902), medido

INVESTIGADOR REPORT-ONLY. Sin conclusiones, hipótesis ni recomendaciones. Recolección de datos.

## Comando exacto que generó este reporte

```
python scripts/analysis/realtick_bt/faulty/censo_cola_t_open.py
```

## Lineage

- `run_id`: F0-A6-COLA-0001
- `area`: T0.7
- `experimento`: censo_cola_t_open
- `substrate_id`: p_cap_reloj_reconstruido
- `git_sha`: 3e15070505756f0dd68bd5710fd774898295f5f6
- `etapa`: medicion
- `generador`: scripts/analysis/realtick_bt/faulty/censo_cola_t_open.py
- `timestamp`: 2026-08-14T00:15:50.101354Z

## §3.1 -- Estratificación de |delta_t_open_s| (147 emparejadas)

n_emparejadas = 147

| tramo | n | % |
|---|---|---|
| <1 s | 42 | 28.57% |
| 1-16 s | 57 | 38.78% |
| 16-60 s | 9 | 6.12% |
| 1-15 min | 19 | 12.93% |
| 15-60 min | 0 | 0.00% |
| 1-6 h | 16 | 10.88% |
| >6 h | 4 | 2.72% |

### Percentiles globales (s)

| n | p50 | p75 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| 147 | 1.2300000190734863 | 61.0 | 6357.500054359436 | 8381.530999994275 | 71579.92500025741 | 179395.71005296707 |

### Percentiles por estrategia (s)

| strategy_id | n | p50 | p75 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|
| SAR::S6-K2P0 | 83 | 1.2300000190734863 | 60.88499999046326 | 6258.5200487136835 | 6368.684034538269 | 57164.84835454932 | 66564.0 |
| SuperTrend::SuperTrend-p14x3-M15 | 64 | 1.2300000190734863 | 89.25 | 6358.739059686661 | 8418.765499997138 | 114163.64521989797 | 179395.71005296707 |

### Percentiles por side (s)

| side | n | p50 | p75 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|
| BUY | 78 | 1.2300000190734863 | 165.69249999523163 | 6362.408052825927 | 14234.349999999975 | 99667.63081255 | 179395.71005296707 |
| SELL | 69 | 1.2300000190734863 | 46.769999980926514 | 1278.3539999962004 | 6358.87405500412 | 23412.361982249895 | 55101.61994457245 |

## §3.2 -- La cola: 39 posiciones con |delta_t_open_s| > 60 s

Tabla íntegra en `censo_cola_t_open.csv`. Resumen de identificación:

| position_id | strategy_id | side | real_t_open_servidor | replica_t_open_servidor | delta_t_open_s | signo | n_eventos_intervalo | tipo_dominante_intervalo | n_eventos_ejecutor_intervalo | real_open_en_blocked_window | replica_open_en_blocked_window |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 55256241 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-02 18:45:03 | 2026-07-31 16:55:07 | -179395.71005296707 | REPLICA_TEMPRANO | 11377 | OPEN | 1 | False | False |
| 55267287 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-03 18:45:14 | 2026-08-02 21:41:01 | -75852.75000047684 | REPLICA_TEMPRANO | 4917 | SPREAD_GATE_SKIP | 162 | False | False |
| 55218465 | SAR::S6-K2P0 | BUY | 2026-07-29 01:57:23 | 2026-07-29 20:26:47 | 66564.0 | REPLICA_TARDE | 2695 | SPREAD_GATE_SKIP | 27 | False | False |
| 55218387 | SAR::S6-K2P0 | SELL | 2026-07-29 01:40:40 | 2026-07-29 16:59:01 | 55101.61994457245 | REPLICA_TARDE | 1979 | SPREAD_GATE_SKIP | 39 | False | False |
| 55292360 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-05 18:45:05 | 2026-08-05 23:25:14 | 16809.0 | REPLICA_TARDE | 1076 | MODIFY | 27 | False | False |
| 55217645 | SAR::S6-K2P0 | BUY | 2026-07-28 21:55:24 | 2026-07-29 01:45:04 | 13780.0 | REPLICA_TARDE | 1019 | OPEN_SKIPPED_SL_CROSSED | 188 | False | False |
| 55217492 | SAR::S6-K2P0 | SELL | 2026-07-28 21:35:33 | 2026-07-28 23:57:12 | 8499.769999980927 | REPLICA_TARDE | 649 | OPEN_SKIPPED_SL_CROSSED | 164 | False | False |
| 55333601 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-10 22:35:27 | 2026-08-11 00:56:23 | 8456.0 | REPLICA_TARDE | 544 | CLOSE | 13 | False | False |
| 55293817 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-05 21:12:06 | 2026-08-05 23:28:53 | 8207.769999980927 | REPLICA_TARDE | 534 | OPEN_SKIPPED_SL_CROSSED | 16 | False | False |
| 55267286 | SAR::S6-K2P0 | BUY | 2026-08-03 18:45:14 | 2026-08-03 16:59:04 | -6369.730031490326 | REPLICA_TEMPRANO | 405 | MODIFY | 2 | False | False |
| 55229919 | SuperTrend::SuperTrend-p14x3-M15 | SELL | 2026-07-29 18:45:06 | 2026-07-29 16:59:01 | -6364.380055427551 | REPLICA_TEMPRANO | 405 | OPEN | 2 | False | False |
| 55279444 | SAR::S6-K2P0 | SELL | 2026-08-04 18:45:03 | 2026-08-04 16:59:03 | -6359.270061969757 | REPLICA_TEMPRANO | 405 | MODIFY | 2 | False | False |
| 55279445 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-04 18:45:03 | 2026-08-04 16:59:03 | -6359.270061969757 | REPLICA_TEMPRANO | 405 | OPEN | 2 | False | False |
| 55216338 | SAR::S6-K2P0 | SELL | 2026-07-28 18:45:07 | 2026-07-28 16:59:08 | -6358.280044555664 | REPLICA_TEMPRANO | 405 | MODIFY | 2 | False | False |
| 55331537 | SAR::S6-K2P0 | BUY | 2026-08-10 18:45:11 | 2026-08-10 16:59:13 | -6357.500054359436 | REPLICA_TEMPRANO | 405 | MODIFY | 2 | False | False |
| 55331538 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-10 18:45:11 | 2026-08-10 16:59:13 | -6357.500054359436 | REPLICA_TEMPRANO | 405 | MODIFY | 2 | False | False |
| 55242135 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-07-30 18:45:00 | 2026-07-30 16:59:10 | -6349.480060577393 | REPLICA_TEMPRANO | 404 | OPEN | 2 | False | False |
| 55242134 | SAR::S6-K2P0 | SELL | 2026-07-30 18:45:00 | 2026-07-30 17:00:13 | -6286.400060892105 | REPLICA_TEMPRANO | 400 | MODIFY | 2 | False | False |
| 55229918 | SAR::S6-K2P0 | BUY | 2026-07-29 18:45:06 | 2026-07-29 20:27:33 | 6147.0 | REPLICA_TARDE | 400 | MODIFY | 12 | False | False |
| 55218120 | SAR::S6-K2P0 | SELL | 2026-07-29 00:00:09 | 2026-07-29 01:32:00 | 5511.7699999809265 | REPLICA_TARDE | 356 | OPEN_SKIPPED_SL_CROSSED | 12 | False | False |
| 55218420 | SAR::S6-K2P0 | BUY | 2026-07-29 01:45:05 | 2026-07-29 01:56:50 | 705.0 | REPLICA_TARDE | 48 | CLOSE | 3 | False | False |
| 55295218 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-05 23:29:26 | 2026-08-05 23:40:11 | 645.2499995231628 | REPLICA_TARDE | 45 | CLOSE | 2 | False | False |
| 55334110 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-11 00:56:24 | 2026-08-11 01:06:22 | 598.7699999809265 | REPLICA_TARDE | 44 | OPEN_SKIPPED_SL_CROSSED | 5 | False | False |
| 55295271 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-05 23:33:38 | 2026-08-05 23:42:01 | 503.0 | REPLICA_TARDE | 39 | OPEN_SKIPPED_SL_CROSSED | 5 | False | False |
| 55295210 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-05 23:28:55 | 2026-08-05 23:33:37 | 282.0 | REPLICA_TARDE | 22 | CLOSE | 4 | False | False |
| 55295132 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-05 23:25:15 | 2026-08-05 23:29:24 | 249.7699999809265 | REPLICA_TARDE | 30 | OPEN_SKIPPED_SL_CROSSED | 17 | False | False |
| 55280254 | SuperTrend::SuperTrend-p14x3-M15 | SELL | 2026-08-04 21:18:58 | 2026-08-04 21:15:18 | -220.0 | REPLICA_TEMPRANO | 26 | OPEN_SKIPPED_SL_CROSSED | 17 | False | False |
| 55318627 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-09 21:13:32 | 2026-08-09 21:10:38 | -174.0 | REPLICA_TEMPRANO | 23 | OPEN_SKIPPED_SL_CROSSED | 13 | False | False |
| 55218381 | SAR::S6-K2P0 | SELL | 2026-07-29 01:37:31 | 2026-07-29 01:40:07 | 156.0 | REPLICA_TARDE | 17 | OPEN_SKIPPED_SL_CROSSED | 6 | False | False |
| 55218362 | SAR::S6-K2P0 | SELL | 2026-07-29 01:34:23 | 2026-07-29 01:36:57 | 154.7699999809265 | REPLICA_TARDE | 16 | OPEN_SKIPPED_SL_CROSSED | 9 | False | False |
| 55218379 | SAR::S6-K2P0 | SELL | 2026-07-29 01:36:59 | 2026-07-29 01:39:20 | 141.0 | REPLICA_TARDE | 18 | MODIFY | 7 | False | False |
| 55217634 | SAR::S6-K2P0 | BUY | 2026-07-28 21:53:02 | 2026-07-28 21:55:22 | 140.7699999809265 | REPLICA_TARDE | 17 | OPEN_SKIPPED_SL_CROSSED | 10 | False | False |
| 55218376 | SAR::S6-K2P0 | SELL | 2026-07-29 01:35:25 | 2026-07-29 01:37:29 | 124.76999998092651 | REPLICA_TARDE | 18 | OPEN_SKIPPED_SL_CROSSED | 10 | False | False |
| 55218357 | SAR::S6-K2P0 | SELL | 2026-07-29 01:32:18 | 2026-07-29 01:34:21 | 123.76999998092651 | REPLICA_TARDE | 12 | OPEN_SKIPPED_SL_CROSSED | 5 | False | False |
| 55218101 | SAR::S6-K2P0 | SELL | 2026-07-28 23:58:49 | 2026-07-29 00:00:07 | 78.76999998092651 | REPLICA_TARDE | 18 | MODIFY | 10 | False | False |
| 55218383 | SAR::S6-K2P0 | SELL | 2026-07-29 01:39:21 | 2026-07-29 01:40:38 | 77.76999998092651 | REPLICA_TARDE | 11 | OPEN_SKIPPED_SL_CROSSED | 4 | False | False |
| 55205837 | SAR::S6-K2P0 | SELL | 2026-07-27 18:53:30 | 2026-07-27 18:52:29 | -61.0 | REPLICA_TEMPRANO | 9 | OPEN | 13 | False | False |
| 55205838 | SuperTrend::SuperTrend-p14x3-M15 | SELL | 2026-07-27 18:53:30 | 2026-07-27 18:52:29 | -61.0 | REPLICA_TEMPRANO | 9 | OPEN | 13 | False | False |
| 55230389 | SAR::S6-K2P0 | BUY | 2026-07-29 20:26:48 | 2026-07-29 20:27:48 | 60.769999980926514 | REPLICA_TARDE | 9 | OPEN_SKIPPED_SL_CROSSED | 3 | False | False |

### Conteo de `tipo_dominante_intervalo` sobre la cola

| tipo_dominante_intervalo | n |
|---|---|
| OPEN_SKIPPED_SL_CROSSED | 16 |
| MODIFY | 10 |
| OPEN | 6 |
| CLOSE | 4 |
| SPREAD_GATE_SKIP | 3 |

## §3.3 -- Las 15 filas SIN_PAREJA

| tipo_fila | position_id | strategy_id | side | t_open_servidor | precio_open | motivo_cierre | n_eventos_intervalo | tipo_dominante_intervalo | real_open_en_blocked_window | replica_open_en_blocked_window |
|---|---|---|---|---|---|---|---|---|---|---|
| REPLICA_SIN_PAREJA |  | SAR::S6-K2P0 | L | 2026-07-29 18:45:05 | 4081.81 | SL | 115 | TIME_GATE_SKIP |  | False |
| REPLICA_SIN_PAREJA |  | SAR::S6-K2P0 | L | 2026-07-31 16:55:07 | 4078.22 | CLOSE_RECONCILER | 115 | SPREAD_GATE_SKIP |  | False |
| REPLICA_SIN_PAREJA |  | SAR::S6-K2P0 | L | 2026-08-05 20:13:35 | 4265.77 | FALLBACK_CLOSE_INVALID_SL | 75 | CLOSE |  | False |
| REPLICA_SIN_PAREJA |  | SAR::S6-K2P0 | S | 2026-08-07 16:55:14 | 4342.51 | FALLBACK_CLOSE_INVALID_SL | 115 | SPREAD_GATE_SKIP |  | False |
| REPLICA_SIN_PAREJA |  | SAR::S6-K2P0 | S | 2026-08-09 22:29:59 | 4330.7 | SL | 67 | CLOSE |  | False |
| REAL | 55333600 | SAR::S6-K2P0 | BUY | 2026-08-10 22:35:27 | 4425.42 | SL | 100 | OPEN_SKIPPED_SL_CROSSED | False |  |
| REPLICA_SIN_PAREJA |  | SuperTrend::SuperTrend-p14x3-M15 | L | 2026-07-28 16:59:08 | 4030.88 | SL | 115 | SPREAD_GATE_SKIP |  | False |
| REPLICA_SIN_PAREJA |  | SuperTrend::SuperTrend-p14x3-M15 | S | 2026-07-28 22:26:12 | 4033.1 | SL | 146 | OPEN_SKIPPED_SL_CROSSED |  | False |
| REPLICA_SIN_PAREJA |  | SuperTrend::SuperTrend-p14x3-M15 | L | 2026-08-03 16:59:04 | 4054.45 | SL | 115 | SPREAD_GATE_SKIP |  | False |
| REPLICA_SIN_PAREJA |  | SuperTrend::SuperTrend-p14x3-M15 | L | 2026-08-04 19:00:32 | 4073.52 | SL | 162 | OPEN_SKIPPED_SL_CROSSED |  | False |
| REPLICA_SIN_PAREJA |  | SuperTrend::SuperTrend-p14x3-M15 | S | 2026-08-04 21:13:58 | 4084.14 | SL | 154 | OPEN_SKIPPED_SL_CROSSED |  | False |
| REAL | 55317670 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-09 18:45:15 | 4340.99 | SL | 115 | SOLO_NOOP | False |  |
| REAL | 55318544 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-09 21:07:14 | 4326.55 | SL | 154 | OPEN_SKIPPED_SL_CROSSED | False |  |
| REAL | 55318552 | SuperTrend::SuperTrend-p14x3-M15 | BUY | 2026-08-09 21:08:17 | 4325.99 | SL | 154 | OPEN_SKIPPED_SL_CROSSED | False |  |
| REAL | 55321392 | SuperTrend::SuperTrend-p14x3-M15 | SELL | 2026-08-10 01:40:44 | 4343.24 | SL | 143 | OPEN_SKIPPED_SL_CROSSED | False |  |

## §3.4 -- Verificación epoch<->hora de servidor (3 filas de verdad_terreno_902.csv)

| epoch | t_open_servidor (csv) | calculado | coincide |
|---|---|---|---|
| 1785178410.0 | 2026-07-27 18:53:30 | 2026-07-27 18:53:30 | True |
| 1785178410.0 | 2026-07-27 18:53:30 | 2026-07-27 18:53:30 | True |
| 1785264307.0 | 2026-07-28 18:45:07 | 2026-07-28 18:45:07 | True |

`blocked_open_window` leído del log (fila 0, columna `raw`): 18:00-18:45

## Nota metodológica -- censo del log del ejecutor real (dato, no interpretación)

En `eventos_ejecutor_902.csv`, la columna `magic` sólo está poblada para el evento `SENT OPEN` (724011 / 724071); la columna `config` sólo está poblada para `OPEN_SKIPPED_SL_CROSSED`, `SL_CLAMPED OPEN`, `ALARM` y `ACTIONS_SUMMARY:SAME_BAR_EXIT_FALLBACK`. Para `SENT MODIFY` (431 filas), `SL_CLAMPED` (35), `SENT CLOSE` (3), `FALLBACK_CLOSE_INVALID_SL` (9), `SAME_BAR_EXIT_FALLBACK` (11) y `OTRO` (5), ninguna de las dos columnas identifica la estrategia. Por eso el censo del log del ejecutor en §3.2 **no está filtrado por estrategia** (a diferencia del censo de la réplica, que sí lo está): cuenta todos los eventos del ejecutor en el intervalo, sin importar a qué posición pertenecen. La columna `ejecutor_eventos_conteo_json` en `censo_cola_t_open.csv` lista los valores distintos de `event` encontrados y su conteo, tal cual, sin normalizar.

