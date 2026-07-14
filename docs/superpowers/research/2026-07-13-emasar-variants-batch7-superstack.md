# EMASAR Variants -- Batch 7 (extension): "SUPER-STACK" (S1/S2/S3)

**Fecha:** 2026-07-13 · **Ventana:** 2026-06-08 -> 2026-07-07 · **Símbolo:** XAUUSD
**Motor:** `sentinel_engine/strategies/emasar_variant.py::simular_variant` (cero código de motor nuevo -- todos los parámetros usados ya existían). Runner: `scripts/report/gen_variant_batch7.py` (copia la máquina de carga/fill/métricas/ingestión de `gen_variant_batch1.py` via el mismo patrón `importlib` que las tandas 2-6).

## Objetivo

Combinar, por primera vez en el programa, las dos palancas ganadoras que nunca se habían apilado juntas: **V-13 (reentrada controlada, `reentry_enable=True, reentry_max=2`)** y **V-15 (SAR adaptativo por régimen de volatilidad, `sar_adaptive=True, sar_fast=(0.3,0.3), sar_slow=(0.005,0.05), vol_regime_window=200`)**, sobre el esqueleto campeón, cruzado con el factor `ac_modulate_factor` en {0.10 (referencia previa), 0.01 (mejora V-06d recién encontrada)}.

## Esqueleto base (fijo en todas las corridas)

```
confirm_mode=1, confirm_count=2, require_ema_order=False, ema_fast=8, ema_slow=20,
sar_step=0.3, sar_max=0.3, f1_trail_pips=100, f2_trail_pips=100, f3_trail_pips=100,
ac_modulate=True
```
Por TF, `init_sl_range_k`: M1=6.0 · M2=3.0 · M5=6.0 · M15=2.5.
XAUUSD, barras BID, spread 0.5 aplicado al fill, stop legal por rango.

## Grid: 3 formas de stack × 2 factores AC × 4 TF = 24 corridas

- **S1** = esqueleto + `reentry_enable=True, reentry_max=2` (palanca V-13)
- **S2** = esqueleto + `sar_adaptive=True, sar_fast=(0.3,0.3), sar_slow=(0.005,0.05), vol_regime_window=200` (palanca V-15)
- **S3** = esqueleto + AMBAS palancas juntas (parámetros S1 + S2)

---

## Resultados completos (24 celdas, agrupados por TF)

### M1

| stack | factor | net | PF | WR% | maxDD | n | trades/día | %INITSL | %TRAIL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 0.10 | -14,055.0 | 0.8152 | 34.21 | 19,128.9 | 14,478 | 482.6 | 5.55 | 94.45 |
| S1 | 0.01 | -11,460.3 | 0.8464 | 35.25 | 17,112.0 | 14,478 | 482.6 | 5.55 | 94.45 |
| S2 | 0.10 | -3,937.5 | 0.9322 | 35.69 | 11,360.1 | 11,700 | 390.0 | 4.41 | 95.59 |
| S2 | 0.01 | -1,523.7 | 0.9731 | 36.79 | 9,459.3 | 11,700 | 390.0 | 4.41 | 95.59 |
| S3 | 0.10 | -2,803.8 | 0.9572 | 36.63 | 11,202.6 | 13,947 | 464.9 | 4.32 | 95.68 |
| **S3** | **0.01** | **+803.4** | **1.0126** | **38.20** | **8,332.5** | 13,947 | 464.9 | 4.32 | 95.68 |

**Ganador M1: S3 f=0.01, net +803.4** -- primer resultado NET POSITIVO en M1 de todo el programa (todas las tandas anteriores, incluyendo V-06d, quedaron negativas en M1).

### M2

| stack | factor | net | PF | WR% | maxDD | n | trades/día | %INITSL | %TRAIL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 0.10 | +32,253.6 | 2.0293 | 46.37 | 1,881.0 | 7,524 | 250.8 | 1.24 | 98.76 |
| S1 | 0.01 | +33,501.0 | 2.0897 | 47.21 | 1,764.9 | 7,524 | 250.8 | 1.24 | 98.76 |
| S2 | 0.10 | +33,215.4 | 2.4073 | 49.75 | 922.5 | 6,048 | 201.6 | 0.79 | 99.21 |
| S2 | 0.01 | +34,435.8 | 2.4906 | 50.69 | 806.4 | 6,048 | 201.6 | 0.79 | 99.21 |
| S3 | 0.10 | +38,416.8 | 2.4360 | 50.42 | 960.0 | 7,218 | 240.6 | 1.04 | 98.96 |
| **S3** | **0.01** | **+40,263.6** | **2.5487** | **51.62** | **800.7** | 7,218 | 240.6 | 1.04 | 98.96 |

**Ganador M2: S3 f=0.01, net +40,263.6.**

### M5

| stack | factor | net | PF | WR% | maxDD | n | trades/día | %INITSL | %TRAIL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 0.10 | +47,106.3 | 7.2538 | 65.59 | 177.0 | 2,964 | 98.8 | 0.10 | 99.90 |
| S1 | 0.01 | +47,611.2 | 7.4488 | 66.30 | 171.6 | 2,964 | 98.8 | 0.10 | 99.90 |
| S2 | 0.10 | +43,239.6 | 8.9198 | 69.06 | 228.0 | 2,424 | 80.8 | 0.00 | 100.0 |
| S2 | 0.01 | +43,728.3 | 9.1911 | 69.93 | 219.9 | 2,424 | 80.8 | 0.00 | 100.0 |
| S3 | 0.10 | +48,088.5 | 8.5865 | 68.87 | 136.2 | 2,910 | 97.0 | 0.00 | 100.0 |
| **S3** | **0.01** | **+48,849.9** | **8.9520** | **69.90** | **128.1** | 2,910 | 97.0 | 0.00 | 100.0 |

**Ganador M5: S3 f=0.01, net +48,849.9.**

### M15

| stack | factor | net | PF | WR% | maxDD | n | trades/día | %INITSL | %TRAIL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **S1** | **0.10** | +43,297.8 | 31.7797 | 79.64 | 186.6 | 1,002 | 33.4 | 0.00 | 100.0 |
| **S1** | **0.01** | **+43,459.8** | **32.4652** | **80.54** | 186.6 | 1,002 | 33.4 | 0.00 | 100.0 |
| S2 | 0.10 | +36,869.4 | 33.8253 | 79.78 | 129.3 | 801 | 26.7 | 0.00 | 100.0 |
| S2 | 0.01 | +37,007.1 | 34.5209 | 81.27 | 129.3 | 801 | 26.7 | 0.00 | 100.0 |
| S3 | 0.10 | +42,755.1 | 34.4783 | 79.62 | 112.8 | 957 | 31.9 | 0.00 | 100.0 |
| S3 | 0.01 | +42,965.7 | 35.5272 | 81.19 | 112.8 | 957 | 31.9 | 0.00 | 100.0 |

**Ganador M15: S1 f=0.01, net +43,459.8** -- aquí el stack "solo reentrada" gana por sobre S3; el SAR adaptativo interfiere en M15 (ver abajo).

---

## Análisis de interacción (mecánico)

Base (V-06c/d, sin ninguna palanca) por factor y TF:
- f=0.10: M1 -14,922.0 · M2 +30,777.9 · M5 +45,815.7 · M15 +41,126.7
- f=0.01: M1 -12,583.8 · M2 +31,903.8 · M5 +46,269.3 · M15 +41,264.4

Regla usada (en este orden): **INTERFERENCE** si S3 < max(S1, S2); si no, **ADDITIVE** si `|Δ_S3 − (Δ_S1+Δ_S2)| / |Δ_S1+Δ_S2| ≤ 10%`; si no y `Δ_S3 > (Δ_S1+Δ_S2)` → **SYNERGY**.

| TF | factor | Δ_S1 (S1−base) | Δ_S2 (S2−base) | Δ esperado (suma) | Δ_S3 real | S3 | max(S1,S2) | Veredicto |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M1 | 0.10 | +867.0 | +10,984.5 | +11,851.5 | +12,118.2 | -2,803.8 | -3,937.5 | **ADDITIVE** (+2.2%) |
| M1 | 0.01 | +1,123.5 | +11,060.1 | +12,183.6 | +13,387.2 | +803.4 | -1,523.7 | **ADDITIVE** (+9.9%, límite) |
| M2 | 0.10 | +1,475.7 | +2,437.5 | +3,913.2 | +7,638.9 | +38,416.8 | +33,215.4 | **SYNERGY** (+95%) |
| M2 | 0.01 | +1,597.2 | +2,532.0 | +4,129.2 | +8,359.8 | +40,263.6 | +34,435.8 | **SYNERGY** (+102%) |
| M5 | 0.10 | +1,290.6 | -2,576.1 | -1,285.5 | +2,272.8 | +48,088.5 | +47,106.3 | **SYNERGY** |
| M5 | 0.01 | +1,341.9 | -2,541.0 | -1,199.1 | +2,580.6 | +48,849.9 | +47,611.2 | **SYNERGY** |
| M15 | 0.10 | +2,171.1 | -4,257.3 | -2,086.2 | +1,628.4 | +42,755.1 | +43,297.8 | **INTERFERENCE** |
| M15 | 0.01 | +2,195.4 | -4,257.3 | -2,061.9 | +1,701.3 | +42,965.7 | +43,459.8 | **INTERFERENCE** |

**Lectura:**
- **M2** muestra sinergia franca y grande (~+95-102% del esperado): la reentrada y el SAR adaptativo se refuerzan mutuamente -- el SAR adaptativo produce entradas de mayor calidad, y esas mismas entradas son las que la reentrada re-engancha con éxito.
- **M5** también sinergiza, aunque de forma más sutil: individualmente V-15 (S2) le RESTA net a M5 respecto a la base (el filtro de régimen recorta volumen bueno), pero combinado con reentrada (S3) el resultado neto es positivo y por encima de ambos parciales -- la reentrada "recupera" trades que el filtro SAR habría dejado fuera.
- **M1** queda en el límite ADDITIVE/SYNERGY (9.9% en f=0.01): el crecimiento es casi exactamente la suma de los dos efectos individuales, sin refuerzo cruzado relevante -- pero es la combinación que por primera vez cruza a positivo.
- **M15 es el único caso de INTERFERENCE**: apilar ambas palancas (S3) da MENOS que la mejor palanca sola (S1). El SAR adaptativo (S2) por sí solo ya es negativo frente a la base en M15 (-4,257.3, el filtro de régimen recorta demasiado volumen bueno en este TF, igual que se documentó en el programa original), y sumarlo a la reentrada no revierte ese daño -- simplemente diluye la ganancia de la reentrada. Consistente con el patrón ya visto en la tanda 5: V-15 solo en M15 gana en PF/WR pero pierde net frente al campeón.

---

## Veredicto por TF (¿bate el mejor vigente del programa?)

| TF | Ganador super-stack | net | vs mejor vigente | Δ | % |
|---|---|---:|---|---:|---:|
| **M1** | S3 f=0.01 | +803.4 | V-06d f=0.01 (-12,583.8) | **+13,387.2** | +106.4% |
| **M2** | S3 f=0.01 | +40,263.6 | V-06d f=0.01 (+31,903.8) | **+8,359.8** | +26.2% |
| **M5** | S3 f=0.01 | +48,849.9 | V-06d f=0.01 (+46,269.3) | **+2,580.6** | +5.6% |
| **M15** | S1 f=0.01 | +43,459.8 | V-13 rmax2 f=0.25 (+43,027.8) | **+432.0** | +1.0% |

**Las 4 TF establecen nuevo mejor vigente del programa.** El más notable es **M1**, que por primera vez cruza a net positivo (el programa entero lo tenía descartado como "no rentable con ninguna config limpia"). M2 y M5 mejoran con margen sólido (+26% y +5.6%). M15 mejora marginalmente (+1.0%) y confirma que en ese TF el SAR adaptativo no debe combinarse con la reentrada -- la mejor config M15 es reentrada sola (S1), no el super-stack completo.

## Sorpresas

1. **M1 se vuelve rentable** apilando ambas palancas con f=0.01 -- ninguna palanca sola (ni siquiera V-15 solo, que ya achicaba mucho la pérdida) lo había logrado en 6 tandas previas.
2. **M2 y M5 muestran sinergia genuina**, no solo aditividad -- es la primera evidencia del programa de que dos palancas se refuerzan mutuamente en vez de simplemente sumarse.
3. **M15 es el único TF donde "más palancas" empeora el resultado** frente a la mejor palanca individual -- el super-stack completo (S3) no es universal; el ganador correcto varía por TF (S3 en M1/M2/M5, S1 en M15).
4. En todos los TF y ambas formas de stack, **f=0.01 domina f=0.10** siempre -- consistente con el hallazgo de la tanda 6 (V-06d): el codo de `ac_modulate_factor` sigue sin aparecer, 0.01 sigue siendo mejor que 0.10 incluso apilado con otras palancas.

## Ingestión

Solo el mejor-net por TF fue ingestado en `data/research.db` (idempotente, delete-before-insert):

| run_id | variant_id | tf | net | trades |
|---|---|---|---:|---:|
| `sim-report-emasar-ss-m1` | `EMS_XAU_SS_M1_c1_S3_f0p01` | M1 | +803.4 | 13,947 |
| `sim-report-emasar-ss-m2` | `EMS_XAU_SS_M2_c1_S3_f0p01` | M2 | +40,263.6 | 7,218 |
| `sim-report-emasar-ss-m5` | `EMS_XAU_SS_M5_c1_S3_f0p01` | M5 | +48,849.9 | 2,910 |
| `sim-report-emasar-ss-m15` | `EMS_XAU_SS_M15_c1_S1_f0p01` | M15 | +43,459.8 | 1,002 |

Verificado vía `python scripts/dev/e2e_service.py --port 8612` (copia aislada de `research.db`, no toca la real): `GET /api/runs/<run_id>/trades` devolvió trades no vacíos para los 4 run_ids (13,947 / 7,218 / 2,910 / 1,002 respectivamente, coincide exactamente con `n` de las corridas).

*Fuentes: `scripts/report/gen_variant_batch7.py` · corridas auditables en `data/research.db` (`sim-report-emasar-ss-*`) en Trade View · reportes previos `docs/superpowers/research/2026-07-13-emasar-variants-batch{1..6}.md` y `docs/REPORTE_PROGRAMA_VARIANTES_EMASAR_2026-07-13.md`.*
