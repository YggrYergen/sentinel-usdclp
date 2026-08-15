# T0.7-M-B1 -- borde del día: por qué la réplica abre a las 16:59

INVESTIGADOR REPORT-ONLY. Sin conclusiones, hipótesis ni recomendaciones.

## Comando exacto que generó este reporte

```
python scripts/analysis/realtick_bt/faulty/borde_del_dia.py
```

## Lineage

- `run_id`: T0.7-M-B1-BORDE-DIA-0001
- `area`: T0.7
- `experimento`: borde_del_dia
- `substrate_id`: capitaria_ticks_XAUUSD_202607_202608 + capitaria_bars_M15 + p_cap_reloj_reconstruido
- `git_sha`: d85ea1b85c73858e22b0265ebccd2c9cd06ff182
- `etapa`: medicion
- `generador`: scripts/analysis/realtick_bt/faulty/borde_del_dia.py
- `timestamp`: 2026-08-15T19:14:11.926139Z

## Pregunta 1 -- spread visto por la réplica en cada apertura (10 casos)

| position_id | grupo | replica_t_open_servidor | q1_n_ticks_segundo | q1_spread_vigente | q1_spread_vigente_supera_umbral | q1_spread_primer_tick_futuro | q1_spread_primer_tick_futuro_supera_umbral | q1_delay_primer_tick_futuro_s |
|---|---|---|---|---|---|---|---|---|
| 55267286 | principal | 2026-08-03 16:59:04 | 0.0 | 0.6000000000003638 | True | 0.5 | False | 3661.8200314044952 |
| 55229919 | principal | 2026-07-29 16:59:01 | 0.0 | 0.599999999999909 | True | 0.5 | False | 3664.327055454254 |
| 55279444 | principal | 2026-08-04 16:59:03 | 0.0 | 0.599999999999909 | True | 0.5 | False | 3662.466062068939 |
| 55279445 | principal | 2026-08-04 16:59:03 | 0.0 | 0.599999999999909 | True | 0.5 | False | 3662.466062068939 |
| 55216338 | principal | 2026-07-28 16:59:08 | 0.0 | 0.599999999999909 | True | 0.5 | False | 3657.6730444431305 |
| 55331537 | principal | 2026-08-10 16:59:13 | 0.0 | 0.5999999999994543 | True | 0.5 | False | 3652.63805437088 |
| 55331538 | principal | 2026-08-10 16:59:13 | 0.0 | 0.5999999999994543 | True | 0.5 | False | 3652.63805437088 |
| 55242135 | principal | 2026-07-30 16:59:10 | 0.0 | 0.6000000000003638 | True | 0.5 | False | 3655.4510605335236 |
| 55242134 | principal | 2026-07-30 17:00:13 | 0.0 | 0.6000000000003638 | True | 0.5 | False | 3592.371060848236 |
| 55256241 | fin_de_semana | 2026-07-31 16:55:07 | 0.0 | 0.599999999999909 | True | 0.5 | False | 176698.60605287552 |

Umbral del gate: 0.5. Tabla íntegra (con min/max/mediana del segundo) en `borde_del_dia.csv`.

## Pregunta 2 -- umbral efectivo del gate de spread, file:line

Réplica: `scripts/analysis/realtick_bt/faulty/ciclos.py:127`

```
    max_spread_open: float = 0.50,
```

Condición: `scripts/analysis/realtick_bt/faulty/ciclos.py:182-183`

```
spread = tick_ask - tick_bid
                        if spread > max_spread_open + 1e-6:
```

Harness vivo: `scripts/analysis/realtick_bt/backtest.py:349-359`

```
sp = eask - ebid
        if abs(sp - 0.5) <= 0.05:
            entry = (tc, ebid, eask, round(sp, 3)); delay_bars = bi - lo; break
```

## Pregunta 3 -- ¿modela la réplica el corte 17:00-17:45 o el fin de semana?

`scripts/analysis/realtick_bt/faulty/llamador.py:474-478`:

```
Los huecos de fin de semana (hasta 2,62 días medidos) NO reciben
    tratamiento especial: se rellenan igual que cualquier otro hueco, y
    `correr_ciclos` ya salta en O(1) por ciclo los instantes sin tick
    (`ticks.first_at(t) is None -> continue`), así que el coste de rellenar
    un hueco de mercado cerrado es el mismo por ciclo que cualquier otro.
```

Ficheros revisados sin ningún otro tratamiento de hueco de sesión / fin de semana / borde de día (grep `17:00|maint|weekend|fin_de_semana|domingo|saturday|sunday|session|sesion|blocked|gate`, sin resultado salvo lo citado arriba y los propios gates de `ciclos.py` ya citados en la pregunta 2):

- `scripts/analysis/realtick_bt/faulty/estado_por_barra.py`
- `scripts/analysis/realtick_bt/faulty/ciclos.py`
- `scripts/analysis/realtick_bt/faulty/config_faulty.py`
- `scripts/analysis/realtick_bt/faulty/llamador.py`
- `scripts/analysis/realtick_bt/faulty/comparador.py`

Mecanismo -- `t_open` guarda el instante del bucle, no el tick que `ticks.first_at()` encontró: `scripts/analysis/realtick_bt/faulty/ciclos.py:161` (`tick = ticks.first_at(t)`), `:164` (`_tick_ts, tick_bid, tick_ask = tick`), `:211` (`"t_open": t,`).

## Pregunta 4 -- ticks por minuto, ventana 16:45→18:50 hora de servidor, 7 días del cluster

| fecha | n_ticks_total_ventana | huecos_cero_ticks |
|---|---|---|
| 2026-07-28 | 22226 | 16:59-17:59 (61 min) |
| 2026-07-29 | 27494 | 16:59-17:59 (61 min) |
| 2026-07-30 | 22873 | 16:59-17:59 (61 min) |
| 2026-07-31 | 2993 | 16:55-18:49 (115 min) |
| 2026-08-03 | 19845 | 16:59-17:59 (61 min) |
| 2026-08-04 | 21751 | 16:59-17:59 (61 min) |
| 2026-08-10 | 20522 | 16:59-17:59 (61 min) |

Serie completa minuto a minuto en `borde_del_dia.json` (`q4_ticks_por_minuto_por_dia`).

## Pregunta 5 -- barra M15 que originó la señal (10 casos)

| position_id | grupo | q5_bar_open_servidor | q5_bar_idx | q5_siguiente_bar_contigua | q5_gap_siguiente_bar_s |
|---|---|---|---|---|---|
| 55267286 | principal | 2026-08-03 16:30:00 | 13786.0 | True | 0.0 |
| 55229919 | principal | 2026-07-29 16:30:00 | 13510.0 | True | 0.0 |
| 55279444 | principal | 2026-08-04 16:30:00 | 13878.0 | True | 0.0 |
| 55279445 | principal | 2026-08-04 16:30:00 | 13878.0 | True | 0.0 |
| 55216338 | principal | 2026-07-28 16:30:00 | 13418.0 | True | 0.0 |
| 55331537 | principal | 2026-08-10 16:30:00 | 14246.0 | True | 0.0 |
| 55331538 | principal | 2026-08-10 16:30:00 | 14246.0 | True | 0.0 |
| 55242135 | principal | 2026-07-30 16:30:00 | 13602.0 | True | 0.0 |
| 55242134 | principal | 2026-07-30 16:45:00 | 13603.0 | False | 3600.0 |
| 55256241 | fin_de_semana | 2026-07-31 16:30:00 | 13694.0 | True | 0.0 |

## Pregunta 6 -- segunda población de la cola (16 casos OPEN_SKIPPED_SL_CROSSED)

| position_id | delta_t_open_s | signo | delta_precio_open | q6_evento_en_real_t_open_tipo | q6_evento_en_real_t_open_dist_s | q6_evento_en_real_t_open_no_evaluable | q6_desired_sl_min_en_intervalo | q6_desired_sl_max_en_intervalo | q6_n_open_skipped_en_intervalo |
|---|---|---|---|---|---|---|---|---|---|
| 55217645 | 13780.0 | REPLICA_TARDE | -16.539999999999964 | SL_CLAMPED | 1.0 | False | 4023.995598208076 | 4032.0884190754664 | 83.0 |
| 55217492 | 8499.769999980927 | REPLICA_TARDE | -0.7800000000002001 | OPEN_SKIPPED_SL_CROSSED | 1.0 | False | 4023.2186397525807 | 4023.995598208076 | 91.0 |
| 55293817 | 8207.769999980927 | REPLICA_TARDE | 20.329999999999927 | NOOP | 1.0 | False | 4263.16342017078 | 4263.16342017078 | 20.0 |
| 55218120 | 5511.769999980927 | REPLICA_TARDE | -7.400000000000091 | NOOP | 1.0 | False | 4032.0884190754664 | 4032.0884190754664 | 10.0 |
| 55334110 | 598.7699999809265 | REPLICA_TARDE | 0.4000000000005457 | SL_CLAMPED | 0.0 | False | 4403.290504272683 | 4403.290504272683 | 4.0 |
| 55295271 | 503.0 | REPLICA_TARDE | 0.4099999999998545 | SL_CLAMPED | 1.0 | False | 4263.16342017078 | 4263.16342017078 | 7.0 |
| 55295132 | 249.7699999809265 | REPLICA_TARDE | -0.9099999999998544 | SL_CLAMPED | 1.0 | False | 4263.16342017078 | 4263.16342017078 | 21.0 |
| 55280254 | -220.0 | REPLICA_TEMPRANO | 0.0 | OPEN_SKIPPED_SL_CROSSED | 0.0 | False | 4086.549796448797 | 4086.549796448797 | 23.0 |
| 55318627 | -174.0 | REPLICA_TEMPRANO | -0.0799999999999272 | OPEN_SKIPPED_SL_CROSSED | 0.0 | False | 4324.655114914415 | 4324.655114914415 | 20.0 |
| 55218381 | 156.0 | REPLICA_TARDE | -0.2100000000000363 | SL_CLAMPED | 1.0 | False | 4032.0884190754664 | 4032.0884190754664 | 4.0 |
| 55218362 | 154.7699999809265 | REPLICA_TARDE | -0.25 | SL_CLAMPED | 1.0 | False | 4032.0884190754664 | 4032.0884190754664 | 12.0 |
| 55217634 | 140.7699999809265 | REPLICA_TARDE | 0.0700000000001637 | NOOP | 0.0 | False | 4023.2186397525807 | 4023.2186397525807 | 13.0 |
| 55218376 | 124.76999998092651 | REPLICA_TARDE | -0.0199999999999818 | OPEN_SKIPPED_SL_CROSSED | 0.0 | False | 4032.0884190754664 | 4032.0884190754664 | 8.0 |
| 55218357 | 123.76999998092651 | REPLICA_TARDE | -0.2400000000002364 | NOOP | 1.0 | False | 4032.0884190754664 | 4032.0884190754664 | 6.0 |
| 55218383 | 77.76999998092651 | REPLICA_TARDE | -0.0799999999999272 | SL_CLAMPED | 1.0 | False | 4032.0884190754664 | 4032.0884190754664 | 5.0 |
| 55230389 | 60.769999980926514 | REPLICA_TARDE | 0.0199999999999818 | SL_CLAMPED | 1.0 | False | 4074.73625227856 | 4074.73625227856 | 3.0 |

Nota: el brief sugiere `sl_vivo` de `posiciones_replica.csv` para esta pregunta. Los 16 casos son eventos OPEN_SKIPPED_SL_CROSSED -- ocurren en el paso 3 de `ciclos.py` (`posicion_viva is None`), es decir NUNCA se creó una posición en ese ciclo, así que ninguno tiene fila propia en `posiciones_replica.csv` con la que emparejar por ese instante: `sl_vivo` NO EVALUABLE por esta vía para estos 16 casos. En su lugar se reporta `desired_sl` del propio `detalle` JSON del evento OPEN_SKIPPED_SL_CROSSED (`eventos_replica.csv`), que es el nivel de stop que la ficha deseaba y que estaba cruzado en el momento del rechazo.

## Pregunta 7 -- no evaluables

- Pregunta 6, `evento_en_real_t_open`: 0 de 16 casos sin ningún evento de la réplica dentro de ±1 s del `real_t_open_epoch` (declarado no evaluable con ese margen, no inferido).
- Pregunta 6, `desired_sl`: 0 de 16 casos sin ningún evento OPEN_SKIPPED_SL_CROSSED dentro del intervalo `[real_t_open, replica_t_open]` censado (declarado no evaluable).
- `sl_vivo` de `posiciones_replica.csv`, sugerido por el brief para la pregunta 6: no evaluable para los 16 casos por el motivo dado arriba (ver nota de la pregunta 6).
- Preguntas 1, 2, 3, 4 y 5: sin casos no evaluables -- los 10 instantes del cluster tienen tick vigente y tick futuro localizables, y las 7 fechas tienen cobertura de ticks en la ventana pedida.

