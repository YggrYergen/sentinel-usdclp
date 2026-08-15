# T0.7-M-E — Verificacion cuantitativa del fix de look-ahead (E.5)

Brief: `research/fases/F0-preparacion/02-specs/T0.7-M-E-brief-fix-lookahead-motor-largo.md`
Datos completos: `fix_lookahead_harness.json` (mismo directorio).
Commit del fix: `f3dda1aff0f84ae739b09a467da4c0bffe0252c4`.

Medicion: Q6 AVA -- llamadas GENUINAS de `ticks.first_at()` durante `bt.build_all()` sobre el motor
largo AVA, via `auditoria_lookahead.medir_q6_ava(modo="mediana")` (no modificado, solo invocado).
BEFORE = medicion de T0.7-M-C (codigo sin cota). AFTER = misma funcion, mismo modo, ejecutada en
esta sesion con el fix aplicado.

## Tabla resumen

| medida | antes (T0.7-M-C) | despues (este fix) |
|---|---:|---:|
| llamadas genuinas `first_at` | 13.672 | 13.824 |
| llamadas evaluables | 13.672 | 12.830 |
| llamadas que devuelven `None` | 0 | 994 |
| p50 | 0,108 s | 0,097 s |
| p90 | 3,268 s | 0,663 s |
| p99 | 23.400,07 s | 21,71 s |
| max | 76.129,39 s | 59,92 s |
| `n_gt_60s` | **945** | **0** |
| `n_gt_15min` | 736 | 0 |
| `n_gt_1h` | 651 | 0 |

## Sensibilidad de umbral (15 s / 60 s / 300 s)

| umbral | antes: n_gt_X | despues: n_gt_X |
|---|---:|---:|
| 15 s | 1.122 | 189 |
| 60 s | 945 | 0 |
| 300 s | 794 | 0 |

Antes recomputado sobre `auditoria_lookahead_ava_q6.csv.bak-20260815T204419Z` (respaldo tomado
antes de que la re-ejecucion de `medir_q6_ava` sobrescribiera el CSV). Despues recomputado sobre
`auditoria_lookahead_ava_q6.csv` (estado actual, post-fix).

## Delta de posiciones por estrategia vs `F0-BT-LARGO-0001`

| estrategia | F0-BT-LARGO-0001 / antes | despues (con fix) | delta | delta % |
|---|---:|---:|---:|---:|
| S6-K2P0 | 4.578 | 4.482 | −96 | −2,10 % |
| S7-TPNONE | 5.364 | 5.253 | −111 | −2,07 % |
| SuperTrend-p14x3-M15 | 1.617 | 1.566 | −51 | −3,15 % |

Medicion NO declarada "no evaluable": el costo de correr Q6 completo con el fix fue 234,16 s
(build_all: 116,3 s), barato.

## Criterios de exito del brief (E.5), declarados uno a uno

- **`n_gt_60s` 945 → 0:** CUMPLE, exacto.
- **p50/p90 esencialmente sin mover:**
  - p50: 0,108 s → 0,097 s (−10,2 % relativo).
  - p90: 3,268 s → 0,663 s (**−79,7 % relativo**).
  - El brief dice textualmente: *"If they move appreciably, the fix is touching healthy calls and
    you must STOP and escalate."* p90 se movio 79,7 % en relativo. Esta cifra se declara medida,
    **no se interpreta** (rol IMPLEMENTADOR, charter §B): no se decide aqui si "appreciably" se
    cumple o no, ni la causa. Dato factual adicional, tambien medido sin interpretar: el numero
    total de llamadas cambio (13.672 → 13.824, +152) y 994 de ellas ahora devuelven `None` (antes
    0) -- la poblacion de llamadas "evaluables" sobre la que se calculan p50/p90 no es la misma
    poblacion antes y despues. Señalado para escalar, ver reporte final.
- **Sensibilidad 15/60/300s:** reportada arriba, antes y despues.
- **Delta de posiciones por estrategia:** medido (no fue caro), tabla arriba.

## Parity gate

- **Antes** del fix: `python -m pytest tests/research/test_baseline_parity.py -m slow -q` →
  `4 passed in 2.53s`.
- **Despues** del fix: mismo comando → `3 failed, 1 passed in 2.42s`. Primera discrepancia nombrada
  por el propio test:
  ```
  AssertionError: S6-K2P0: numero de posiciones cambio -- congelado=633 actual=624.
  assert 624 == 633
  ```
  Rojo esperado por diseno (el look-ahead vivia dentro de la linea base congelada). No se
  re-congelo la baseline, no se agrego `skip`/`xfail`, no se toco `04-resultados/T0.6-baseline/`.

## Artefactos tocados durante la medicion (respaldados, no perdidos)

- `auditoria_lookahead_ava_q6.csv` (dentro de este mismo directorio) fue **sobrescrito** por
  `medir_q6_ava()` al re-ejecutarla con el fix -- efecto colateral documentado de esa funcion
  (E.4 permite invocarla, no modificarla). El estado PRE-FIX quedo respaldado en
  `auditoria_lookahead_ava_q6.csv.bak-20260815T204419Z` antes de la re-ejecucion.
- `auditoria_lookahead.json` / `auditoria_lookahead.csv` (Q4/Q5 Capitaria + Q6, de T0.7-M-C) **NO**
  se tocaron: no se invoco `auditoria_lookahead.main()`, solo las funciones puras y
  `medir_q6_ava()` directamente.
