# Reporte — Backtest Real-Tick Mensual (S6 / S7 / SuperTrend)

**Fecha:** 2026-07-25 · **Instrumento:** XAUUSD · **Período:** 2026-01 → 2026-07 (7 meses, hora servidor UTC−4)
**Base:** las 3 estrategias como una **cuenta virtual única**, solo aperturas a **spread 0,5** (espejo del vivo).
**Motor:** `simular_variant` graduado (parity-gated) + overlay de **fills sobre ticks reales** (52,6M ticks locales).

> ⚠️ **ESTADO: PRELIMINAR — pendiente de confirmación en motor MT5 real-tick.**
> La **fidelidad de mecanismo está cerrada** (entradas close-driven + gate 0,5, salidas por SL-trailing
> intra-vela para S6/S7 y línea-SL para ST — exactamente el reconciler vivo). Pero las **magnitudes deben
> confirmarse contra el MT5 Strategy Tester "every tick based on real ticks"** (gold-standard). Toda brecha
> que se identifique debe **diagnosticarse**, no asumirse. Todas las cifras son **calculadas por código**
> (`scripts/analysis/realtick_bt/backtest.py`), no derivadas por LLM.

---

## 1. Resumen (7 meses, lote 0,67/ficha)

| Métrica | Valor |
|---|---:|
| Neto combinado | **39.513.979 CLP** |
| Operaciones | 2542 |
| Win rate | 32,26 % |
| Profit factor | 1,03 |
| Máx. drawdown | 129.150.945 CLP |
| RoM (neto ÷ margen pico) | 93,45 % |

**Lectura:** positivo en el neto de 7 meses, pero con un **abril fuertemente negativo** y jun ~plano — un
perfil **mucho más sobrio que el +91 %/semana** del informe de esta semana (ver §4).

## 2. Grilla mensual combinada (3 estrategias)

| Mes | Ops | Neto CLP | WR% | PF | maxDD CLP | RoM% |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 258 | 66.714.780 | 29,84 | 1,64 | 43.618.789 | 161,34 |
| 2026-02 | 343 | 4.695.873 | 32,07 | 1,02 | 83.442.103 | 11,11 |
| 2026-03 | 324 | 9.263.118 | 33,02 | 1,05 | 61.730.278 | 23,40 |
| 2026-04 | 459 | -62.778.128 | 27,45 | 0,69 | 114.823.638 | -162,98 |
| 2026-05 | 388 | 39.459.390 | 35,05 | 1,27 | 52.120.177 | 103,05 |
| 2026-06 | 464 | -22.881.401 | 34,27 | 0,88 | 60.990.508 | -66,83 |
| 2026-07 | 306 | 5.040.346 | 34,31 | 1,05 | 35.481.953 | 14,96 |
| **TOTAL** | **2542** | **39.513.979** | **32,26** | **1,03** | **129.150.945** | **93,45** |

## 3. Por estrategia (lote 0,67/ficha)

### 3.1 S6-K2P0
| Mes | Ops | Neto CLP | WR% | PF | maxDD CLP | RoM% |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 111 | 43.516.514 | 32,43 | 1,99 | 23.680.152 | 228,02 |
| 2026-02 | 138 | -3.162.373 | 34,78 | 0,97 | 36.286.350 | -16,20 |
| 2026-03 | 135 | 10.503.597 | 40,00 | 1,13 | 29.696.190 | 54,03 |
| 2026-04 | 195 | -42.938.628 | 23,08 | 0,57 | 60.719.448 | -237,93 |
| 2026-05 | 159 | 18.567.648 | 32,08 | 1,27 | 25.818.518 | 105,08 |
| 2026-06 | 183 | -11.175.601 | 34,43 | 0,86 | 30.481.136 | -68,65 |
| 2026-07 | 132 | 2.548.722 | 34,09 | 1,05 | 19.945.540 | 16,39 |
| **TOTAL** | **1053** | **17.859.879** | **32,48** | **1,03** | **73.803.767** | **91,51** |

### 3.2 S7-TPNONE
| Mes | Ops | Neto CLP | WR% | PF | maxDD CLP | RoM% |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 120 | -4.660.736 | 27,50 | 0,90 | 19.320.594 | -24,42 |
| 2026-02 | 165 | 3.482.375 | 32,73 | 1,03 | 36.559.293 | 17,84 |
| 2026-03 | 159 | 5.253.681 | 30,19 | 1,07 | 24.146.978 | 28,73 |
| 2026-04 | 216 | -29.654.778 | 31,94 | 0,65 | 50.306.205 | -166,87 |
| 2026-05 | 183 | 19.958.716 | 40,98 | 1,34 | 20.773.780 | 112,96 |
| 2026-06 | 228 | 8.001.934 | 38,16 | 1,11 | 26.257.109 | 49,47 |
| 2026-07 | 150 | -1.711.070 | 34,00 | 0,95 | 16.064.103 | -11,01 |
| **TOTAL** | **1221** | **670.122** | **34,15** | **1,00** | **53.952.346** | **3,43** |

### 3.3 SuperTrend-p14×3-M15 — *provisional, pendiente MT5*
| Mes | Ops | Neto CLP | WR% | PF | maxDD CLP | RoM% |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 27 | 27.859.002 | 29,63 | 3,56 | 5.386.074 | 810,18 |
| 2026-02 | 40 | 4.375.871 | 20,00 | 1,15 | 14.321.660 | 134,19 |
| 2026-03 | 30 | -6.494.159 | 16,67 | 0,77 | 16.957.599 | -194,58 |
| 2026-04 | 48 | 9.815.279 | 25,00 | 1,51 | 6.731.337 | 323,96 |
| 2026-05 | 46 | 933.026 | 21,74 | 1,05 | 11.395.210 | 31,40 |
| 2026-06 | 53 | -19.707.734 | 16,98 | 0,34 | 22.056.926 | -698,56 |
| 2026-07 | 24 | 4.202.694 | 37,50 | 1,40 | 3.432.806 | 160,02 |
| **TOTAL** | **268** | **20.983.978** | **22,76** | **1,14** | **31.158.788** | **610,24** |

## 4. Validación: backtest vs. lo vivido (semana del informe, 0,01/ficha)

| Estrategia | BT ops | BT neto CLP | Vivido ops | Vivido neto CLP |
|---|---:|---:|---:|---:|
| S6-K2P0 | 30 | 76.306 | 69 | 114.348 |
| S7-TPNONE | 36 | 12.587 | 42 | 45.776 |
| SuperTrend-p14x3-M15 | 4 | 15.106 | 5 | 122.249 |
| **Combinado** | **70** | **103.998** | **116** | **282.373** |

**Veredicto (fidelidad):** el backtest reproduce **dirección y perfil** (tendencial, WR≈31 %, PF>1) pero da
**~1/3 del neto** vivido combinado. La brecha está **explicada, no es bug**:

1. **El track vivido es merge de 2 cuentas** stitched (cuenta 1 lun–mié + cuenta 2 mié–jue) → ~2× las
   operaciones que una simulación de **cuenta única** (30 vs 69 en S6). La grilla es cuenta única → saca menos, correctamente.
2. **El +71.707 fue outlier** (posición que quedó abierta por error mientras se programaba el motor y se cerró
   manual out-of-sample). Vivido ex-outlier = **210.666 CLP**; el backtest (~103.998 a 0,01) ≈ **49,37 %** de eso.
3. **ST con línea-SL hace whipsaw** (WR bajo) — más fiel al vivo pero castiga el neto; el gran ganador vivo de ST era justamente el outlier.

**Conclusión de fondo:** un backtest real-tick fiel de esa semana da **~103.998 CLP (cuenta única, 0,01 lote)**,
no +282k. **La semana del informe fue un punto alto favorable, no lo típico** — la grilla mensual (§2) lo confirma.

## 5. SuperTrend — nota

ST se modeló con la **línea SuperTrend como SL server-side intra-vela** (semántica confirmada del reconciler
vivo). Esto produce whipsaw (más stop-outs por mecha) y WR bajo. La **muestra viva es insuficiente para
contrastar** (ST corrió ~1 semana en vivo), así que su magnitud queda **pendiente del gold-standard MT5**.

## 6. Metodología

- **Ticks:** 52,6M ticks reales XAUUSD 2026-01→07 extraídos del cache local de MT5_Tester (`copy_ticks_range`,
  read-only) → `data/lake_ticks/XAUUSD/`. Barras M15 BID autoritativas frescas (`_bars_M15.parquet`).
- **Señal/niveles:** `simular_variant(**_GOLIVE_M15, live_fill_mode=True)` para S6/S7 (motor graduado, intacto);
  SuperTrend(14,3.0) always-in con línea-SL para ST.
- **Fills real-tick:** entrada al primer tick tras el cierre de la vela de confirmación (spread real; gate 0,5
  con retry close-driven ≤1 barra); salida al primer tick que cruza el nivel server-side intra-vela.
- **Costos:** comisión = 0 (Capitaria la embebe en el spread), swap = 0 (posiciones cortas). Neto en CLP
  (USDCLP 936,50), leverage ×100, contrato 100 oz. RoM = neto ÷ margen pico concurrente.
- **Sizing:** grilla a 0,67/ficha; validación a 0,01/ficha (para comparar contra lo vivido, que fue 0,01).

## 7. Próximos pasos

1. **Confirmar en MT5 "every tick real"** (gold-standard) — al menos SuperTrend, para cerrar su magnitud.
2. **Diagnosticar** cada brecha que aparezca contra MT5 (no asumir).
3. Con los backtests validados → **investigación y optimización** (ver objetivo del usuario: análisis
   buy/sell × ganadora/perdedora, maximizar ganadoras / minimizar perdedoras).

---
*Anexo: CSV por posición y estrategia en `data/analysis/realtick_bt/positions_*.csv`.*
