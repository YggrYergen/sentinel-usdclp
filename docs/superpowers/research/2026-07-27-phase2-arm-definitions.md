# Fase 2 — definición de brazos y dos confounds encontrados antes de correr

> Controlador, 2026-07-27. Todo read-only. Ningún fichero de estrategia viva tocado (R1-bis).
> Preparación para el head-to-head del backtest largo. **Nada aquí es un resultado**: son
> definiciones verificadas contra el código y dos problemas de diseño detectados antes de medir.

## 1. El lake de 4,32 años es usable, y comparte reloj con el substrato

`data/lake/XAUUSD/15.parquet` — medido, no supuesto:

| Propiedad | Valor |
|---|---|
| Barras M15 | 101.287 |
| Rango | 2022-03-31 05:15 → 2026-07-27 16:45 (**4,32 años**) |
| Timestamps duplicados | 0 |
| NaN / precios en cero | 0 en open/high/low/close |
| Gaps de exactamente 15 min | 100.165 (98,9 %) |
| Gaps > 6 h | 230 — todos fines de semana (Fri→Mon) |
| Barras por año | 2022: 17.646 (parcial) · 2023: 23.332 · 2024: 23.485 · 2025: 23.496 · 2026: 13.328 (parcial) |

La cobertura anual constante (23,3–23,5k) descarta agujeros silenciosos. El gap recurrente de
75 min es la parada diaria del bróker (la "hora muerta", que además se desplaza — ver memoria).

### 🔴 Riesgo de reloj descartado por medición

El índice del lake viene etiquetado `datetime64[ns, UTC]`, pero los epochs de MT5 son **hora de
bróker (UTC−4)**, y el substrato de 7 meses fue reparado justamente por ese bug. Si las etiquetas
no coincidieran, unir ambos datasets reintroduciría el bug que R3 acaba de arreglar.

Medido sobre el solape:
- **13.236 de 13.236 barras** con `close` idéntico (máx. diferencia absoluta `0.000000`).
- Barrido de desplazamiento −6h..+6h: **100 % de identidad en +0h**, ~0 % en todos los demás.

**Conclusión: la etiqueta UTC es nominal; los valores ya son hora de servidor.** Los dos datasets
se unen tal cual, sin corrección de huso.

## 2. Las 21 variantes PX — definiciones exactas

Fuente: `scripts/report/patient_exit_manifest_2026_07_20.json` (los `.trials.db` solo guardan
`variant_id`, no los kwargs). Familias:

| Fam | Palanca | Problema que ataca |
|---|---|---|
| F1 | ratchet / chandelier (`ratchet_lock_frac`, `ratchet_atr_k`, `ratchet_arm_r`) | A — devolución de utilidad |
| F2 | piso ATR del trail + SAR lento (`trail_atr_floor_k`, `sar_slow`) | A — devolución |
| F3 | presupuesto MAE de espera (`wait_be_exit`, `wait_mae_atr_k`) | B — salida prematura |
| F4 | escalera de TP parcial (`f1_tp_r`, `f2_tp_r`) | B — salida prematura |
| F5 | armado retardado del trail (`trail_arm_r`) | A — devolución |

Criterio de retención pre-registrado del programa: *mantener una variante solo si MFE-capture% >
base **Y** give-back USD < base **Y** net_honest ≥ base*. Holdout pre-comprometido por familia:
F1→PX-RATCHET-L50 · F2→PX-FLOOR-K3 · F3→PX-WAIT-MAE2 · F4→PX-PART-F1TP1 · F5→PX-TRAIL-ARM1.

## 3. 🔴 CONFOUND 1 — las variantes PX ganadoras mueven DOS palancas, no una

Contra su propia base (`PX-BASE-S6K2P0`), las de mayor net_honest cambian dos cosas a la vez:

| Variante | net_honest | Palanca nominal | **Palanca extra no declarada en el nombre** |
|---|---:|---|---|
| PX-TRAIL-ARM1 | 123.011 | `trail_arm_r=1.0` | **`max_hold_bars=64`** |
| PX-SAR-SLOW | 54.461 | `sar_slow=(0.002,0.03)` | **`max_hold_bars=64`** |
| PX-FLOOR-K3 | 53.679 | `trail_atr_floor_k=3.0` | **`max_hold_bars=64`** |

La base NO lleva `max_hold_bars`. Por tanto **el mérito de PX-TRAIL-ARM1 no está atribuido**: puede
ser el armado retardado, puede ser el cierre forzado a 64 barras, o la interacción.

**Consecuencia para la Fase 2 (obligatoria):** añadir un brazo de control
`max_hold_bars=64` SOLO, sobre la misma base. Sin ese control, cualquier conclusión sobre
`trail_arm_r` es no-atribuible. Las de F1-ratchet y F4-partial sí son de palanca única.

## 4. 🔴 CONFOUND 2 — la base S7 del programa PX NO es la S7 viva

| | S7 viva (`live_configs_20.py`) | Base del manifest PX |
|---|---|---|
| Origen declarado | `HON-W2-S7-TPNONE-M15-SAR` (liga rank 2, +32.683,5) | **`HON-S7-V15-TPNONE-BE1P0-M15`** (otra liga, +13.355,7) |
| `stop_and_reverse` | **`True`** (heredado de `_GOLIVE_BASE_M15`) | **ausente** |
| `be_at_r` | 1.0 | 1.0 |
| `trail_atr_floor_k` | 1.5 | 1.5 |

Los ecos S7 del programa (`PX-RATCHET-*-S7`, `PX-CHAND-*-S7`) están anclados en una estrategia
distinta de la que corre en vivo, y sin `stop_and_reverse` — que es precisamente el mecanismo
responsable de los 195 cierres `reverse` que dominan la economía de S6/S7.

**Consecuencia:** los ecos S7 **no son transplantables** tal cual. O se re-anclan sobre la S7 viva,
o se excluyen del head-to-head y se declara por qué.

La base S6 **sí** coincide: `PX-BASE-S6K2P0` = `stop_and_reverse=True`, `ac_modulate=True`,
`trail_atr_floor_k=2.0`, `init_sl_range_k=2.5` = exactamente la S6-K2P0 viva. Los brazos S6 del
programa PX (incluida la ganadora) son válidos para transplantar.

## 5. Roster de brazos propuesto para la Fase 2

1. **Control**: S6-K2P0, S7-TPNONE, SuperTrend-p14x3-M15 vivas, byte-idénticas.
2. **Wrappers**: peldaños de espera post-apertura N2..N6.
3. **PX sobre base S6** (válidos): F1 ratchet L33/L50/L66, chandelier ATR2/ATR3, F2 floor K3/K4,
   SAR-SLOW, F3 wait-MAE2/MAE3, F4 part-F1TP1/F1TP0P5/F1F2, F5 trail-ARM1.
4. **Controles de atribución nuevos**: `max_hold_bars=64` solo; `max_hold_bars=48` solo.
5. **Cat-B4 trailing trifásico** (nunca medido): F1 supervivencia→BE; F2 apretar hasta
   `W* = L̄·(1−WR)/WR`; F3 runner con apriete por indicador. Transiciones R {(1,2),(1,2.5),(1,3),(0.75,2)}.
6. **Ecos S7**: excluidos o re-anclados (§4).

Todo brazo va sobre **copia independiente** (cfg deep-copy / módulo nuevo). R1-bis sin excepción.
