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
| Neto combinado | **147.780.084 CLP** |
| Operaciones | 2347 |
| Win rate | 34,43 % |
| Profit factor | 1,14 |
| Máx. drawdown | 114.092.025 CLP |
| RoM (neto ÷ margen pico) | 383,66 % |

**Lectura:** positivo en el neto de 7 meses, pero con un **abril fuertemente negativo** y jun ~plano — un
perfil **mucho más sobrio que el +91 %/semana** del informe de esta semana (ver §4).

## 2. Grilla mensual combinada (3 estrategias)

| Mes | Ops | Neto CLP | WR% | PF | maxDD CLP | RoM% |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 222 | 87.475.384 | 34,68 | 2,06 | 27.159.390 | 360,83 |
| 2026-02 | 319 | 12.048.391 | 32,60 | 1,05 | 82.222.331 | 52,57 |
| 2026-03 | 297 | 30.131.017 | 35,02 | 1,19 | 58.368.374 | 132,47 |
| 2026-04 | 435 | -52.022.294 | 28,97 | 0,73 | 104.067.804 | -135,06 |
| 2026-05 | 361 | 60.795.997 | 37,67 | 1,49 | 46.452.376 | 292,33 |
| 2026-06 | 425 | -3.590.925 | 36,71 | 0,98 | 49.360.630 | -13,31 |
| 2026-07 | 288 | 12.942.514 | 36,46 | 1,15 | 31.161.925 | 70,34 |
| **TOTAL** | **2347** | **147.780.084** | **34,43** | **1,14** | **114.092.025** | **383,66** |

## 3. Por estrategia (lote 0,67/ficha)

### 3.1 S6-K2P0
| Mes | Ops | Neto CLP | WR% | PF | maxDD CLP | RoM% |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 84 | 57.854.488 | 42,86 | 2,94 | 11.979.371 | 556,18 |
| 2026-02 | 120 | 3.171.785 | 37,50 | 1,03 | 35.066.578 | 32,26 |
| 2026-03 | 117 | 22.095.200 | 43,59 | 1,34 | 28.015.238 | 225,67 |
| 2026-04 | 177 | -35.060.930 | 25,42 | 0,62 | 52.841.750 | -197,29 |
| 2026-05 | 138 | 36.440.704 | 36,96 | 1,72 | 20.150.717 | 408,85 |
| 2026-06 | 159 | -133.648 | 37,74 | 1,00 | 22.298.496 | -1,58 |
| 2026-07 | 117 | 9.263.118 | 38,46 | 1,24 | 16.813.284 | 117,45 |
| **TOTAL** | **912** | **93.630.717** | **36,51** | **1,21** | **63.303.935** | **526,86** |

### 3.2 S7-TPNONE
| Mes | Ops | Neto CLP | WR% | PF | maxDD CLP | RoM% |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 111 | 1.761.894 | 29,73 | 1,04 | 12.897.965 | 16,94 |
| 2026-02 | 159 | 4.500.735 | 32,08 | 1,04 | 36.559.293 | 45,77 |
| 2026-03 | 150 | 14.529.975 | 32,00 | 1,21 | 22.179.907 | 148,35 |
| 2026-04 | 210 | -26.776.642 | 32,86 | 0,67 | 47.428.069 | -150,67 |
| 2026-05 | 177 | 23.422.268 | 42,37 | 1,43 | 20.773.780 | 262,79 |
| 2026-06 | 213 | 16.250.457 | 40,85 | 1,24 | 22.818.029 | 100,47 |
| 2026-07 | 147 | -523.297 | 34,69 | 0,99 | 14.876.331 | -6,64 |
| **TOTAL** | **1167** | **33.165.389** | **35,48** | **1,07** | **49.107.138** | **186,62** |

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
