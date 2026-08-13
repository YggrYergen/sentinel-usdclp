# P-CAP -- resultado del comparador (Componente E)

Sin conclusiones ni veredicto (charter §A.4/§A.13) -- el memo de interpretación lo escribe Opus en `05-analisis/`.

## Denominadores (regla dura 7 -- nunca se mezclan)

| corte | valor | detalle |
|---|---|---|
| posiciones (este comparador) | 140 | 152 posiciones reales en ventana VENTANA_902 - 11 CLIENT_manual - 1 TP |
| barras-señal (A6, citado) | 91 | S6=49 / ST=42 |

## Criterio de paso -- 6 campos (D-45, D-46)

Denominador evaluable: **140** (emparejadas: 137, sin pareja real: 3).

Casan los 6 campos: **0**. No casan: **137**.

### Por campo (sobre las emparejadas evaluables)

'si'/'no' es bit-identidad estricta (delta==0, D-45) para precio_open/precio_close/razon_cierre/resultado; para t_open/t_close es mismo segundo tras truncar -- floor, no round (D-46). Para los 4 campos numéricos se añade la distribución de |delta| crudo (sin truncar) como contexto -- no decide ningún umbral de paso.

| campo | si | no | no_evaluable |
|---|---|---|---|
| precio_open | 7 | 130 | 0 |
| t_open | 7 | 130 | 0 |
| t_close | 72 | 65 | 0 |
| precio_close | 4 | 133 | 0 |
| razon_cierre | 126 | 11 | 0 |
| resultado | 130 | 7 | 0 |

### Distribución de |delta| (campos numéricos, emparejadas evaluables)

| campo | n | min | p50 | p90 | max |
|---|---|---|---|---|---|
| precio_open | 137 | 0.0000 | 0.2300 | 3.9340 | 21.0500 |
| t_open | 137 | 0.0000 | 9.0000 | 6295.6000 | 179389.0000 |
| t_close | 137 | 0.0260 | 0.9500 | 185.1184 | 330310.0000 |
| precio_close | 137 | 0.0000 | 0.1000 | 0.8380 | 11.0100 |

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
| 61 | 76 | 4 |

## Residuos del emparejamiento 1-a-1

Réplica sin pareja: **9** ({'SAR::S6-K2P0': 6, 'SuperTrend::SuperTrend-p14x3-M15': 3}). Real sin pareja (evaluables): **4**.

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
| T0.7-P-CAP-comparador-20260813T205406Z | F0 | T0.7-P-CAP | 4f1347b460be708a31f574d1aa9ab438c3ec379a8950a5aea5c237c77c2f5ab9 | posiciones_replica.csv + verdad_terreno_902.csv | b113eb7 | be51d0a882cb3ff91f0d11c68800d731e31c5feb | F0 | scripts/analysis/realtick_bt/faulty/comparador.py | 2026-08-13T20:54:06.107088Z |
