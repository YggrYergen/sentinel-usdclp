# Cota realista de fills — `live_fill_mode` — Programa EMASAR

**Fecha:** 2026-07-13 · **Símbolo:** XAUUSD · **Motor:** `sentinel_engine.strategies.emasar_variant.simular_variant` (`live_fill_mode=True`, nuevo kwarg aditivo, default `False`)
**Runner:** `scripts/report/gen_livefill_bound.py` · **Raw JSON:** `scripts/report/livefill_bound_raw.json` · **Tests del motor:** `tests/strategies/test_emasar_variant.py` (5 tests nuevos)

---

## 1. Qué se hizo y por qué

El motor de simulación clásico (`live_fill_mode=False`, comportamiento sin cambios) sube el stop trailing de cada ficha usando el **high de la MISMA barra** (y, con `ac_modulate=True`, el **AC de esa misma barra**) y puede registrar una salida intra-barra al nivel recién subido — un orden intra-barra que solo es conocible al **cierre** de la barra. Un ejecutor en vivo (servidor con SL actualizado al cierre de barra, más fallback a mercado) **no puede replicar eso**: su SL en el servidor sigue en el nivel de la barra anterior hasta que el cierre de la barra actual lo actualiza.

`live_fill_mode=True` (kwarg aditivo, ver docstring de `simular_variant`) reproduce EXACTAMENTE esa semántica:

1. El chequeo intra-barra de la barra `i` usa el SL vigente al **cierre de la barra `i-1`** (el "orden en el servidor"): el SL inicial de rango (sin cambios) y el nivel de trailing FIJADO al cierre de `i-1`.
2. El trailing se sigue calculando al cierre de la barra `i` (con el high/AC propios de `i`), pero ese nuevo nivel solo se vuelve el nivel activo del servidor a partir de la barra `i+1`.
3. **FALLBACK MISMO-BARRA:** si al cierre de `i` el nuevo SL calculado ya está violado por el **cierre** de esa misma barra `i` — es decir, el modo clásico habría salido intra-barra al nivel subido pero el SL del servidor (aún en el nivel de `i-1`) nunca fue tocado — la ficha se cierra AL CIERRE de la barra `i`, motivo `EXIT_TRAIL`, y el evento se marca `"same_bar_fallback": True`.

`live_fill_mode=False` reproduce el stream de eventos clásico byte-por-byte (pineado con tests sintéticos y sobre una ventana real del lake M5 — ver §5). Gates finales: `python -m pytest -q tests/golden/test_parity.py tests/strategies tests/scripts tests/live` → **137 passed** (132 previos + 5 nuevos de `live_fill_mode`).

Este reporte re-simula los 13 configs del roster del programa, en AMBOS modos, sobre las 4 ventanas de investigación (IW/W1/W2/W3), y cuantifica cuánto del edge backtesteado sobrevive a fills sin look-ahead.

---

## 2. Ventanas y roster

| Ventana | Fechas |
|---|---|
| IW | 2026-06-08 → 2026-07-07 |
| W1 | 2026-05-04 → 2026-06-05 |
| W2 | 2026-03-02 → 2026-04-03 |
| W3 | 2025-10-01 → 2025-11-01 |

M2 solo tiene datos en el lake desde 2025-12-10 → las 3 configs M2 (SS-M2, V06D-M2, V15-M2) y SS-M1 **saltan W3** (0 barras, no "0 trades" — se marca `SKIPPED`).

Esqueleto campeón fijo (todas las configs): `confirm_mode=1, confirm_count=2, require_ema_order=False, ema 8/20, sar 0.3/0.3, escalera plana 100/100/100 pips`, `ac_modulate=True`; `init_sl_range_k` por TF: M1=6.0, M2=3.0, M5=6.0, M15=2.5. BID + spread 0.5 al fill, mismo protocolo que todo el programa.

---

## 3. Tabla completa — clásico vs. live-fill, por config × ventana

| Config | TF | Ventana | n | Net clásico | PF clás. | WR clás. | DD clás. | Net live-fill | PF live | WR live | DD live | Δ Net | Δ Net % | Fallback / EXIT_TRAIL | % fallback |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SS-M2 | M2 | IW | 7,218 | 40,263.6 | 2.55 | 51.62 | 800.7 | −30,955.2 | 0.61 | 36.34 | 31,684.5 | −71,218.8 | −176.9% | 5,682/5,682 | 100.0% |
| SS-M2 | M2 | W1 | 8,085 | 27,781.2 | 1.87 | 46.79 | 1,270.8 | −38,649.0 | 0.54 | 32.82 | 38,714.4 | −66,430.2 | −239.1% | 6,156/6,156 | 100.0% |
| SS-M2 | M2 | W2 | 8,130 | 145,926.6 | 7.18 | 66.27 | 1,000.8 | −26,175.9 | 0.81 | 42.11 | 26,727.6 | −172,102.5 | −117.9% | 7,125/7,125 | 100.0% |
| SS-M2 | M2 | W3 | — | — | — | — | — | *sin datos (lake M2 desde 2025-12-10)* | | | | | | |
| SS-M5 | M5 | IW | 2,910 | 48,849.9 | 8.95 | 69.90 | 128.1 | −9,993.3 | 0.78 | 41.43 | 10,432.8 | −58,843.2 | −120.5% | 2,838/2,838 | 100.0% |
| SS-M5 | M5 | W1 | 3,570 | 55,170.3 | 7.74 | 66.72 | 231.6 | −17,133.3 | 0.69 | 40.42 | 17,814.3 | −72,303.6 | −131.1% | 3,252/3,252 | 100.0% |
| SS-M5 | M5 | W2 | 3,075 | 122,599.5 | 31.35 | 79.51 | 107.7 | −1,172.4 | 0.98 | 43.77 | 5,658.0 | −123,771.9 | −101.0% | 3,147/3,147 | 100.0% |
| SS-M5 | M5 | W3 | 3,066 | 51,224.4 | 8.02 | 65.56 | 294.0 | −12,999.3 | 0.74 | 39.91 | 13,227.3 | −64,223.7 | −125.4% | 2,607/2,607 | 100.0% |
| SS-M15 | M15 | IW | 1,002 | 43,459.8 | 32.47 | 80.54 | 186.6 | −1,124.4 | 0.96 | 46.86 | 5,201.7 | −44,584.2 | −102.6% | 1,050/1,050 | 100.0% |
| SS-M15 | M15 | W1 | 1,218 | 45,869.4 | 26.75 | 76.60 | 130.8 | −8,137.2 | 0.77 | 40.92 | 10,653.3 | −54,006.6 | −117.7% | 1,302/1,302 | 100.0% |
| SS-M15 | M15 | W2 | 1,071 | 92,148.6 | 123.28 | 89.08 | 88.5 | **+9,265.8** | 1.24 | 43.75 | 6,401.7 | −82,882.8 | −89.9% | 1,239/1,239 | 100.0% |
| SS-M15 | M15 | W3 | 1,104 | 47,178.6 | 23.21 | 79.35 | 306.6 | **+1,614.6** | 1.06 | 43.47 | 3,508.2 | −45,564.0 | −96.6% | 1,110/1,110 | 100.0% |
| SS-M1 | M1 | IW | 13,947 | 803.4 | 1.01 | 38.20 | 8,332.5 | −64,096.2 | 0.48 | 31.34 | 64,224.6 | −64,899.6 | −8,078.1% | 9,453/9,453 | 100.0% |
| SS-M1 | M1 | W1 | 16,095 | −5,115.3 | 0.93 | 36.64 | 9,631.2 | −71,320.2 | 0.47 | 30.72 | 71,449.8 | −66,204.9 | −1,294.3%* | 10,785/10,785 | 100.0% |
| SS-M1 | M1 | W2 | 4,011 | 35,096.4 | 3.65 | 56.47 | 560.7 | −15,032.7 | 0.70 | 40.65 | 15,690.0 | −50,129.1 | −142.8% | 2,673/2,673 | 100.0% |
| SS-M1 | M1 | W3 | — | — | — | — | — | *sin datos* | | | | | | |
| V06D-M2 | M2 | IW | 7,233 | 31,903.8 | 2.06 | 46.74 | 1,776.6 | −32,144.7 | 0.61 | 35.32 | 32,796.9 | −64,048.5 | −200.8% | 5,649/5,649 | 100.0% |
| V06D-M2 | M2 | W1 | 8,289 | 23,115.3 | 1.63 | 44.23 | 1,476.6 | −36,355.5 | 0.59 | 33.37 | 36,406.2 | −59,470.8 | −257.3% | 6,219/6,219 | 100.0% |
| V06D-M2 | M2 | W2 | 8,067 | 132,680.4 | 6.01 | 62.10 | 1,133.1 | −30,348.0 | 0.78 | 39.91 | 32,282.1 | −163,028.4 | −122.9% | 6,996/6,996 | 100.0% |
| V06D-M2 | M2 | W3 | — | — | — | — | — | *sin datos* | | | | | | |
| **V06D-M5** | M5 | IW | 2,853 | 46,269.3 | 7.53 | 66.46 | 204.3 | **−9,975.6** | 0.78 | 42.62 | 10,332.9 | −56,244.9 | −121.6% | 2,706/2,706 | 100.0% |
| V06D-M5 | M5 | W1 | 3,510 | 52,719.0 | 6.85 | 64.87 | 302.1 | −17,073.0 | 0.70 | 40.09 | 18,778.5 | −69,792.0 | −132.4% | 3,189/3,189 | 100.0% |
| V06D-M5 | M5 | W2 | 3,144 | 126,467.7 | 29.02 | 79.48 | 114.3 | −1,509.0 | 0.98 | 45.45 | 5,529.3 | −127,976.7 | −101.2% | 3,243/3,243 | 100.0% |
| V06D-M5 | M5 | W3 | 3,012 | 47,856.0 | 6.91 | 63.84 | 342.6 | −15,127.2 | 0.71 | 39.29 | 15,491.7 | −62,983.2 | −131.6% | 2,577/2,577 | 100.0% |
| V06D-M15 | M15 | IW | 948 | 41,264.4 | 32.23 | 80.38 | 150.3 | −452.1 | 0.98 | 47.71 | 4,768.8 | −41,716.5 | −101.1% | 1,017/1,017 | 100.0% |
| V06D-M15 | M15 | W1 | 1,149 | 43,021.8 | 26.05 | 76.50 | 130.8 | −9,423.9 | 0.73 | 40.54 | 11,862.0 | −52,445.7 | −121.9% | 1,242/1,242 | 100.0% |
| V06D-M15 | M15 | W2 | 1,026 | 89,971.8 | 122.13 | 88.89 | 90.9 | +9,551.4 | 1.26 | 43.32 | 6,064.8 | −80,420.4 | −89.4% | 1,188/1,188 | 100.0% |
| V06D-M15 | M15 | W3 | 1,035 | 44,865.3 | 26.81 | 79.42 | 295.5 | +2,926.8 | 1.12 | 43.81 | 3,555.3 | −41,938.5 | −93.5% | 1,050/1,050 | 100.0% |
| V13-M5 | M5 | IW | 2,964 | 46,264.8 | 6.92 | 64.57 | 186.0 | −10,389.9 | 0.77 | 42.62 | 10,764.6 | −56,654.7 | −122.5% | 2,748/2,748 | 100.0% |
| V13-M5 | M5 | W1 | 3,669 | 53,402.7 | 6.55 | 63.94 | 316.5 | −18,352.8 | 0.69 | 39.91 | 19,776.6 | −71,755.5 | −134.4% | 3,261/3,261 | 100.0% |
| V13-M5 | M5 | W2 | 3,249 | 129,489.0 | 26.33 | 77.19 | 129.3 | −189.9 | 1.00 | 45.66 | 5,049.0 | −129,678.9 | −100.1% | 3,315/3,315 | 100.0% |
| V13-M5 | M5 | W3 | 3,177 | 49,939.8 | 6.64 | 62.70 | 349.8 | −14,515.2 | 0.73 | 39.79 | 14,874.3 | −64,455.0 | −129.1% | 2,664/2,664 | 100.0% |
| V13-M15 | M15 | IW | 1,002 | 43,027.8 | 30.38 | 79.34 | 186.6 | −1,124.4 | 0.96 | 46.86 | 5,201.7 | −44,152.2 | −102.6% | 1,044/1,044 | 100.0% |
| V13-M15 | M15 | W1 | 1,218 | 45,192.6 | 24.51 | 75.37 | 130.8 | −8,094.0 | 0.77 | 41.13 | 10,610.1 | −53,286.6 | −117.9% | 1,290/1,290 | 100.0% |
| V13-M15 | M15 | W2 | 1,071 | 91,709.4 | 114.35 | 88.24 | 102.9 | +9,281.7 | 1.24 | 43.87 | 6,383.1 | −82,427.7 | −89.9% | 1,230/1,230 | 100.0% |
| V13-M15 | M15 | W3 | 1,104 | 46,674.6 | 21.83 | 78.26 | 306.6 | +1,989.3 | 1.07 | 43.71 | 3,513.9 | −44,685.3 | −95.7% | 1,095/1,095 | 100.0% |
| V15-M2 | M2 | IW | 6,048 | 31,181.4 | 2.27 | 48.02 | 1,116.0 | −26,674.5 | 0.63 | 36.19 | 27,506.7 | −57,855.9 | −185.6% | 4,767/4,767 | 100.0% |
| V15-M2 | M2 | W1 | 6,885 | 20,690.1 | 1.69 | 44.18 | 1,282.5 | −33,887.7 | 0.55 | 33.03 | 33,953.1 | −54,577.8 | −263.8% | 5,232/5,232 | 100.0% |
| V15-M2 | M2 | W2 | 6,762 | 120,754.8 | 6.61 | 63.89 | 1,014.6 | −21,234.9 | 0.82 | 42.25 | 22,002.3 | −141,989.7 | −117.6% | 5,895/5,895 | 100.0% |
| V15-M2 | M2 | W3 | — | — | — | — | — | *sin datos* | | | | | | |
| V06C-M5 | M5 | IW | 2,853 | 45,815.7 | 7.34 | 65.83 | 209.7 | −9,980.4 | 0.78 | 42.62 | 10,337.4 | −55,796.1 | −121.8% | 2,700/2,700 | 100.0% |
| V06C-M5 | M5 | W1 | 3,510 | 52,203.3 | 6.70 | 64.36 | 307.5 | −17,031.3 | 0.70 | 40.13 | 18,734.1 | −69,234.6 | −132.6% | 3,180/3,180 | 100.0% |
| V06C-M5 | M5 | W2 | 3,144 | 125,933.1 | 28.11 | 78.44 | 117.0 | −1,512.0 | 0.98 | 45.45 | 5,529.6 | −127,445.1 | −101.2% | 3,240/3,240 | 100.0% |
| V06C-M5 | M5 | W3 | 3,012 | 47,407.8 | 6.74 | 63.25 | 345.3 | −15,118.8 | 0.71 | 39.34 | 15,482.4 | −62,526.6 | −131.9% | 2,559/2,559 | 100.0% |
| V06C-M15 | M15 | IW | 948 | 41,126.7 | 31.66 | 79.75 | 150.3 | −452.1 | 0.98 | 47.71 | 4,768.8 | −41,578.8 | −101.1% | 1,017/1,017 | 100.0% |
| V06C-M15 | M15 | W1 | 1,149 | 42,792.3 | 25.32 | 75.98 | 130.8 | −9,423.9 | 0.73 | 40.54 | 11,862.0 | −52,216.2 | −122.0% | 1,242/1,242 | 100.0% |
| V06C-M15 | M15 | W2 | 1,026 | 89,826.0 | 119.72 | 88.60 | 93.6 | +9,551.4 | 1.26 | 43.32 | 6,064.8 | −80,274.6 | −89.4% | 1,188/1,188 | 100.0% |
| V06C-M15 | M15 | W3 | 1,035 | 44,703.3 | 26.17 | 79.42 | 295.5 | +2,925.6 | 1.12 | 43.81 | 3,556.5 | −41,777.7 | −93.5% | 1,047/1,047 | 100.0% |
| V06B-M15 | M15 | IW | 948 | 40,897.2 | 30.51 | 79.43 | 150.3 | −452.1 | 0.98 | 47.71 | 4,768.8 | −41,349.3 | −101.1% | 1,011/1,011 | 100.0% |
| V06B-M15 | M15 | W1 | 1,149 | 42,409.8 | 24.01 | 75.20 | 130.8 | −9,407.4 | 0.73 | 40.65 | 11,845.5 | −51,817.2 | −122.2% | 1,236/1,236 | 100.0% |
| V06B-M15 | M15 | W2 | 1,026 | 89,583.0 | 114.93 | 88.30 | 98.1 | +9,548.7 | 1.26 | 43.32 | 6,064.8 | −80,034.3 | −89.3% | 1,185/1,185 | 100.0% |
| V06B-M15 | M15 | W3 | 1,035 | 44,433.3 | 25.09 | 78.84 | 295.5 | +2,919.9 | 1.12 | 43.94 | 3,561.0 | −41,513.4 | −93.4% | 1,038/1,038 | 100.0% |

\* SS-M1/W1: el clásico ya era negativo (−5,115.3); el % de Δ es artefacto de la base negativa, léase el Δ absoluto (−66,204.9), no el %.

---

## 4. El hallazgo estructural: 100% de fallback mismo-barra, en TODAS las celdas

En **las 51 combinaciones config × ventana** con datos, el % de salidas `EXIT_TRAIL` marcadas `same_bar_fallback` es **100.0%**. No es un artefacto de una sola config: se sostiene en M1/M2/M5/M15, en las 4 ventanas, con `ac_modulate_factor` en {0.01, 0.10, 0.25}, y persiste incluso probando (diagnóstico fuera de la tabla, ver script de verificación) un trail *sin* modulación AC de 10× el tamaño habitual ($10 en vez de $1-2.5).

**Por qué:** este programa optimizó explícitamente para trades cortos y de alta rotación (WR 65-89%, PF de dos dígitos, `trades_per_day` altísimo) — la métrica que domina el ranking IS-optimizado es "salir rápido con ganancia pequeña, muchas veces". Diagnóstico directo (M15, roster real): de 319 trades F1, **139 (43.6%) cierran en la barra SIGUIENTE a la entrada**, y de los que duran >1 barra, el 94.7% SÍ salen al nivel genuino del servidor (prior-bar level) — el mecanismo funciona correctamente, pero la geometría de la config (trail estrecho relativo al rango típico de la barra M5/M15 en este período, agravado por `ac_modulate_factor` bajo) hace que, salvo en tramos de rango extremadamente calmo, el trail recién calculado casi siempre quede ya violado por el cierre de la MISMA barra en la que se calculó — exactamente el sesgo optimista que este experimento existe para medir.

**Corolario notable (M15):** bajo `live_fill_mode`, V06D (f=0.01), V06C (f=0.10) y V06B (f=0.25) dan el **net exacto idéntico** en cada ventana (ver §5) — el factor AC solo cambia CUÁNTO se sube el SL, no si la barra ya lo rompió al cierre; una vez que el fallback se activa, el precio de salida es el cierre de la barra, independiente del factor. El factor AC deja de discriminar bajo fills realistas en este TF.

---

## 5. Veredicto por TF — ¿sobrevive f=0.01 a fills realistas?

Comparación decisiva, familia por TF, sobre IW bajo `live_fill_mode=True` (mismos 13 configs, agrupados por factor AC dentro de la misma familia de palancas):

| TF | Familia comparada | Net live f=0.01 | Net live f=0.10 | Net live f=0.25 | Veredicto |
|---|---|---:|---:|---:|---|
| **M5** | V06D (0.01) / V06C (0.10) / V06B\* | −9,975.6 | −9,980.4 | n/a (V06B solo existe en M15 en este roster) | **family flat** (0.01 y 0.10 difieren en $4.8 sobre −$10k, ruido puro) |
| **M15** | V06D (0.01) / V06C (0.10) / V06B (0.25) | −452.1 | −452.1 | −452.1 | **family flat** (net EXACTAMENTE idéntico — el fallback mismo-barra anula la discriminación del factor AC, ver §4) |
| **M2** | V06D (0.01) vs. V15 (0.25, con SAR adaptativo, no aislado) | −32,144.7 | n/a | −26,674.5 (config distinta, no comparable en aislado) | *no hay par aislado f=0.01 vs f=0.10/0.25 en M2 dentro del roster de esta tarea — ambos M2 negativos bajo live-fill* |
| **M1** | Solo SS-M1 (f=0.01) en el roster | −64,096.2 | — | — | *no hay comparación de familia en M1 (un solo config)* |

**Lectura:** el runner calcula el veredicto mecánico (script `gen_livefill_bound.py`, sección `_verdicts`) comparando net-live-IW dentro de la MISMA familia de trail (V06B/C/D, que solo difieren en `ac_modulate_factor`). El resultado es:

- **M5: family flat.** −9,975.6 (f=0.01) vs. −9,980.4 (f=0.10) — diferencia de $4.8 sobre una base de ~−$10k, ruido estadístico, no una preferencia real.
- **M15: family flat**, de forma exacta y mecánica (§4): el fallback mismo-barra hace que el precio de salida (cierre de barra) sea INDEPENDIENTE del factor AC una vez que éste dispara — 918 trades, net −452.1 en los tres factores, sin ninguna diferencia.

**Conclusión clave:** bajo fills realistas, **el eje f=0.01-vs-0.10-vs-0.25 que dominó el ranking in-sample del programa (§10 del reporte base) deja de discriminar por completo** en M5 y M15 — no es que 0.01 pierda contra 0.10/0.25, es que la ventaja marginal que 0.01 mostraba en el backtest clásico era, en gran parte, la ventaja de mirar el high/AC de la barra actual antes de que termine — algo que un ejecutor real no puede hacer.

---

## 6. Cuánto del edge backtesteado sobrevive a fills realistas (lenguaje llano)

**Prácticamente nada, en el régimen tendencial (IW/W1), y una fracción modesta en el régimen de volatilidad extrema (W2).** Las 51 celdas de la tabla muestran una caída de Δnet entre −89% y −8,078% (mediana ≈ −121%) al pasar de fills clásicos a fills con la semántica del ejecutor en vivo — es decir, en la inmensa mayoría de los casos el net se vuelve **negativo**, no solo menor. La única excepción sistemática es la ventana W2 (marzo 2026, volatilidad extrema, ATR14 ≈ 9.5 vs. ~5.5 del resto) en M15, donde SS-M15/V06D-M15/V06C-M15/V06B-M15 y V13-M15 SÍ retienen net positivo bajo fills realistas (+$9.3k a +$9.6k, PF ~1.24-1.26) — y W3 (régimen lateral) también deja net levemente positivo en M15 (+$1.6k a +$2.9k). En M5/M2/M1 NINGUNA celda queda positiva bajo `live_fill_mode` en ninguna ventana. La causa mecánica es uniforme: **el 100% de las salidas por trailing en este roster son eventos "mismo-barra"** — el backtest clásico, al fijar el trail con el high/AC de la barra que todavía no cerró, está comprando información del futuro dentro de esa barra en CADA salida, no solo en una fracción de ellas. El programa de investigación completo (§§1-11 del reporte base) queda con su estructura de gates/entradas intacta y validada (la parte de ENTRADA no se toca en `live_fill_mode`), pero la capa de SALIDA (trailing) tal como está calibrada (trail estrecho + `ac_modulate` agresivo) es, en su forma actual, **no ejecutable en vivo al net reportado** — el próximo paso obligatorio antes de demo es re-calibrar el trail (distancias más anchas, o un `ac_modulate_factor` menos agresivo, o lógica de trail explícitamente "next-bar-only") contra la métrica `live_fill_mode=True`, no contra la clásica.

---

## 7. Ingestión (headline configs, IW, auditable en Trade View)

| Config | `run_id` | net (live-fill, IW) | trades |
|---|---|---:|---:|
| SS-M2 | `sim-report-emasar-lf-ss-m2` | −30,955.2 | 6,390 |
| SS-M5 | `sim-report-emasar-lf-ss-m5` | −9,993.3 | 2,730 |
| SS-M15 | `sim-report-emasar-lf-ss-m15` | −1,124.4 | 954 |
| V06D-M5 | `sim-report-emasar-lf-v06d-m5` | −9,975.6 | 2,703 |

Verificado e2e: servicio propio en `127.0.0.1:8622` (`scripts/run_service.py --port 8622`, `PYTHONPATH=D:/FOREX`), `GET /api/runs/sim-report-emasar-lf-ss-m5` y `GET /api/runs/sim-report-emasar-lf-ss-m5/trades` devolvieron el run y sus 2,730 trades (con `ts_in`/`ts_out`/`px_in`/`px_out`/`pnl` por ficha, auditables posición por posición). Proceso propio (PID 57000) terminado al finalizar la verificación; no se tocó ningún proceso preexistente (`e2e_service.py`, PID 77420, ni el proceso de producción :8601).

---

## 8. Motor y tests

`sentinel_engine/strategies/emasar_variant.py`: nuevo kwarg `live_fill_mode: bool = False` en `simular_variant` (default OFF, aditivo). No se tocó `emasar_ref.py`, `emasar_variant.py`'s `return_state`/reconciler logic, ni ningún archivo bajo `sentinel_engine/live/` o `scripts/live/`.

`tests/strategies/test_emasar_variant.py`: 5 tests nuevos —
- `test_live_fill_mode_default_off_matches_classic_synthetic` / `..._real_m5`: default `False` reproduce el stream clásico byte-por-byte (sintético + ventana real M5 2026-06).
- `test_live_fill_mode_ac_modulate_default_off_matches_classic_real_m5`: idem con `ac_modulate=True, ac_modulate_factor=0.01` (la familia de config que más expone el sesgo).
- `test_live_fill_mode_same_bar_fallback_synthetic`: fixture determinista donde el clásico sale intra-barra al nivel recién subido y `live_fill_mode` cae al fallback de cierre de barra — verifica el precio Y la etiqueta `same_bar_fallback`.
- `test_live_fill_mode_never_worse_than_classic_direction_synthetic`: sanity general sobre una corrida sintética larga con `ac_modulate=True, factor=0.01`.

Gate final: `python -m pytest -q tests/golden/test_parity.py tests/strategies tests/scripts tests/live` → **137 passed** (132 base + 5 nuevos).

---

*Fuentes: `sentinel_engine/strategies/emasar_variant.py` (nuevo kwarg `live_fill_mode`) · `tests/strategies/test_emasar_variant.py` · runner `scripts/report/gen_livefill_bound.py` · raw `scripts/report/livefill_bound_raw.json` · corridas ingestadas auditables en Trade View (`sim-report-emasar-lf-*`) · programa base `docs/REPORTE_PROGRAMA_VARIANTES_EMASAR_2026-07-13.md` · validación OOW previa `docs/REPORTE_VALIDACION_OOW_EMASAR_2026-07-13.md`.*
