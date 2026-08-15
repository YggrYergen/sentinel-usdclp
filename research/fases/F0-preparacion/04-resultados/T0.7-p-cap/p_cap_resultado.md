# P-CAP -- resultado del comparador (Componente E)

Sin conclusiones ni veredicto (charter §A.4/§A.13) -- el memo de interpretación lo escribe Opus en `05-analisis/`.

## Denominadores (regla dura 7 -- nunca se mezclan)

| corte | valor | detalle |
|---|---|---|
| posiciones (este comparador) | 140 | 152 posiciones reales en ventana VENTANA_902 - 11 CLIENT_manual - 1 TP |
| barras-señal (A6, citado) | 91 | S6=49 / ST=42 |

## Criterio de paso -- 6 campos (D-45, D-46)

Denominador evaluable: **140** (emparejadas: 134, sin pareja real: 6).

Casan los 6 campos: **0**. No casan: **134**.

### Por campo (sobre las emparejadas evaluables)

'si'/'no' es bit-identidad estricta (delta==0, D-45) para precio_open/precio_close/razon_cierre/resultado; para t_open/t_close es mismo segundo tras truncar -- floor, no round (D-46). Para los 4 campos numéricos se añade la distribución de |delta| crudo (sin truncar) como contexto -- no decide ningún umbral de paso.

| campo | si | no | no_evaluable |
|---|---|---|---|
| precio_open | 19 | 115 | 0 |
| t_open | 19 | 115 | 0 |
| t_close | 78 | 56 | 0 |
| precio_close | 7 | 127 | 0 |
| razon_cierre | 128 | 5 | 1 |
| resultado | 130 | 4 | 0 |

### Distribución de |delta| (campos numéricos, emparejadas evaluables)

| campo | n | min | p50 | p90 | max |
|---|---|---|---|---|---|
| precio_open | 134 | 0.0000 | 0.1000 | 1.2950 | 42.5000 |
| t_open | 134 | 0.0000 | 1.2300 | 631.3060 | 66564.0000 |
| t_close | 134 | 0.0000 | 0.7575 | 360.3769 | 57658.1820 |
| precio_close | 134 | 0.0000 | 0.0850 | 0.4440 | 37.4100 |

## Excluidos del criterio de paso

| categoria | n |
|---|---|
| CLIENT_manual | 11 |
| TP | 1 |
| total | 12 |

Profit CLIENT_manual: 28,416,355.78 CLP.

## SL de entrada (medido, sin poder de bloqueo)

| evaluable | no_evaluable | coincide |
|---|---|---|
| 61 | 73 | 9 |

## Residuos del emparejamiento 1-a-1

Réplica sin pareja: **9** ({'SAR::S6-K2P0': 4, 'SuperTrend::SuperTrend-p14x3-M15': 5}). Real sin pareja (evaluables): **6**.

## Divergencia conocida -- primera orden

primera orden real: retcode=10027 (AutoTrading deshabilitado), reabre 60s despues (D.6). No se cuenta como fallo generico de paridad de instante de entrada; se reporta con su propio delta.

Posiciones marcadas: 1.

## Monetario (CLP, charter §A.1)

| neto 152 posiciones (CLP) | neto por lote (CLP/lote) | lote vivo |
|---|---|---|
| 16,146,299.81 | 24,098,954.94 | 0.67 |

## Lineage

| run_id | area | experimento | config_hash | substrate_id | engine_sha | git_sha | etapa | generador | timestamp |
|---|---|---|---|---|---|---|---|---|---|
| T0.7-P-CAP-comparador-20260815T195427Z | F0 | T0.7-P-CAP | 4f1347b460be708a31f574d1aa9ab438c3ec379a8950a5aea5c237c77c2f5ab9 | posiciones_replica.csv + verdad_terreno_902.csv | b113eb7 | aa0a8052fa53ee5c0101e1cc317dc62337a94a68 | F0 | scripts/analysis/realtick_bt/faulty/comparador.py | 2026-08-15T19:54:27.902246Z |
