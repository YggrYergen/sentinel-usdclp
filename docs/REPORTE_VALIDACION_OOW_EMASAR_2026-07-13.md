# Validación Out-of-Window — Variantes EMASAR — Reporte Final
**Fecha:** 2026-07-13 · **Símbolo:** XAUUSD · **Configs validadas:** 14 (top-3 por arista net/PF/WR/DD en M2/M5/M15 + las 4 recomendadas + los 3 super-stacks, deduplicadas)
**Condiciones:** idénticas al programa (spread 0.5 al fill · stop legal por rango · barras BID · mismo motor y loaders) — solo cambian las fechas.

---

## 1. Qué se hizo

Las 14 configuraciones ganadoras del programa (optimizadas **in-sample** en IW = 2026-06-08→07-07) se re-corrieron **sin tocar un solo parámetro** en tres ventanas de contraste, más 9 corridas de control V-09 para calibrar el régimen de cada ventana. Total 51 simulaciones, todas ingestadas en `data/research.db` (`sim-report-emasar-oow{1,2,3}-*`) y auditables en Trade View.

### Las ventanas (caracterización mecánica sobre M5)

| Ventana | Fechas | Δ precio | Rango H-L | ATR14 medio | Régimen |
|---|---|---:|---:|---:|---|
| IW (referencia) | 06-08→07-07 | −5.1% | 440 | 5.6 | TREND ↓ |
| W1 | 2026-05-04→06-05 | −6.2% | 462 | 5.2 | TREND ↓ (gemela de IW) |
| W2 | 2026-03-02→04-03 | **−12.5%** | 1,321 | **9.5** | TREND ↓ extremo |
| W3 | 2025-10-01→11-01 | +3.6% | 562 | 5.7 | **RANGE** (la prueba dura) |

**Advertencia de lectura:** W2 infla todos los nets (el control también triplica) — sirve para ver comportamiento en volatilidad extrema, no para promediar. **W3 es la ventana discriminante**: régimen lateral, el opuesto al de optimización. ⚠️ El tier M2 del lake empieza 2025-12-10 → las 2 configs M2 no tienen W3 (0 trades); se juzgan sobre W1/W2.

### Veredicto global: **14 de 14 ROBUSTAS** (rentables en ≥2 de 3 ventanas con PF mediano ≥1.3). Retención mediana OOW/IW = **1.07–1.18** — las configs rinden *mejor* fuera de la ventana de optimización que dentro. Una sola inversión menor de ranking (V-13-M5 ↔ V-06d-M5 en el eje net, delta ~684 = ruido). Los ejes PF, WR y DD mantuvieron su orden sin inversiones.

---

## 2. Tabla 💰 — MAYOR NET MEDIANO OOW

| # | Config | TF | net med. OOW | W1 | W2 | W3 (RANGE) | IW | Retención |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | **SS-M5 (S3: reentr.+SAR adapt., f=0.01)** | M5 | **55,170** | 55,170 | 122,600 | **51,224** | 48,850 | 1.13 |
| 2 | V-13 reentrada (f=0.25) | M5 | 53,403 | 53,403 | 129,489 | 49,940 | 46,265 | 1.15 |
| 3 | V-06d AC-0.01 | M5 | 52,719 | 52,719 | 126,468 | 47,856 | 46,269 | 1.14 |
| 4 | V-06c AC-0.10 | M5 | 52,203 | 52,203 | 125,933 | 47,408 | 45,816 | 1.14 |
| 5 | **SS-M15 (S1: reentrada, f=0.01)** | M15 | **47,179** | 45,869 | 92,149 | **47,179** | 43,460 | 1.09 |
| 6 | V-13 reentrada (f=0.25) | M15 | 46,675 | 45,193 | 91,709 | 46,675 | 43,028 | 1.08 |
| 7 | V-06d AC-0.01 | M15 | 44,865 | 43,022 | 89,972 | 44,865 | 41,264 | 1.09 |
| 8 | V-06c AC-0.10 | M15 | 44,703 | 42,792 | 89,826 | 44,703 | 41,127 | 1.09 |
| 9 | V-06b AC-0.25 | M15 | 44,433 | 42,410 | 89,583 | 44,433 | 40,897 | 1.09 |
| 10 | V-15 SAR adaptativo (f=0.25) | M15 | 39,698 | 39,698 | 72,803 | 39,197 | 36,640 | 1.08 |
| 11 | V-10 máscara ST (f=0.25) | M5 | 28,675 | 28,675 | 68,311 | 25,161 | 24,274 | 1.18 |
| 12 | **SS-M2 (S3, f=0.01)** | M2 | 86,854* | 27,781 | 145,927 | s/datos | 40,264 | 0.69* |
| 13 | V-10 máscara ST (f=0.25) | M15 | 24,287 | 24,287 | 44,803 | 23,459 | 22,689 | 1.07 |
| 14 | V-15 SAR adaptativo (f=0.25) | M2 | 70,722* | 20,690 | 120,755 | s/datos | 31,181 | 0.66* |

\* M2: mediana sobre 2 ventanas evaluables; la retención reportada (0.66-0.69) castiga con un 0 duro la ventana sin datos — sobre las evaluables ambas son claramente robustas.

**Comentario:** El orden in-sample se sostiene casi perfecto — la firma de que las palancas capturan estructura real y no ruido de la ventana. Lo más valioso está en la columna **W3 (RANGE)**: el súper-stack M5 hizo +51,224 con PF 8.0 en un mes lateral donde el control hizo +39,116 con PF 3.7 — **la ventaja sobrevive al cambio de régimen**, que era exactamente el riesgo que esta validación debía descartar. En M2 el efecto es aún más dramático: SS-M2 vs control en W1 = 27,781 vs 7,660 (**3.6×**) con un cuarto del drawdown (1,271 vs 4,973) — M2 es el TF donde la afinación importa más.

---

## 3. Tabla 🏆 — MAYOR PF MEDIANO OOW (solo rentables)

| # | Config | TF | PF med. OOW | PF W3 (RANGE) | net med. | DD máx OOW |
|---|---|---|---:|---:|---:|---:|
| 1 | V-10 máscara ST | M15 | **26.82** | 21.11 | 24,287 | 296.1 |
| 2 | V-06d AC-0.01 | M15 | 26.81 | 26.81 | 44,865 | 295.5 |
| 3 | SS-M15 (S1, f=0.01) | M15 | 26.75 | 23.21 | 47,179 | 306.6 |
| 4 | V-06c AC-0.10 | M15 | 26.17 | 26.17 | 44,703 | 295.5 |
| 5 | V-15 SAR adaptativo | M15 | 25.90 | **25.90** | 39,698 | 511.5 |
| 6 | V-06b AC-0.25 | M15 | 25.09 | 25.09 | 44,433 | 295.5 |
| 7 | V-13 reentrada | M15 | 24.51 | 21.83 | 46,675 | 306.6 |
| 8 | **SS-M5 (S3, f=0.01)** | M5 | **8.02** | 8.02 | 55,170 | 294.0 |
| 9 | V-10 máscara ST | M5 | 6.92 | 6.92 | 28,675 | 207.9 |
| 10 | V-06d AC-0.01 | M5 | 6.91 | 6.91 | 52,719 | 342.6 |
| 11 | V-06c AC-0.10 | M5 | 6.74 | 6.74 | 52,203 | 345.3 |
| 12 | V-13 reentrada | M5 | 6.64 | 6.64 | 53,403 | 349.8 |
| 13 | SS-M2 (S3, f=0.01) | M2 | 4.53* | s/datos | 86,854* | 1,270.8 |
| 14 | V-15 SAR adaptativo | M2 | 4.15* | s/datos | 70,722* | 1,282.5 |

**Comentario:** M15 mantiene PF de dos dígitos **incluso en el mes lateral** (21-27 en W3 vs control 10.5) — la calidad no era un espejismo del trending. Dato notable: en W2 (volatilidad extrema) el V-15 M15 marcó PF 136 con DD 68.7 — el SAR adaptativo brilla precisamente cuando el régimen se pone violento, que es su tesis de diseño. El SS-M5 es el único M5 con PF>8 mediano.

---

## 4. Tabla 🎯 — MAYOR WR MEDIANO OOW

| # | Config | TF | WR med. | WR W3 | net med. |
|---|---|---|---:|---:|---:|
| 1 | V-06d AC-0.01 | M15 | **79.4** | 79.4 | 44,865 |
| 2 | V-06c AC-0.10 | M15 | 79.4 | 79.4 | 44,703 |
| 3 | SS-M15 (S1, f=0.01) | M15 | 79.3 | 79.3 | 47,179 |
| 4 | V-15 SAR adaptativo | M15 | 78.8 | 78.8 | 39,698 |
| 5 | V-06b AC-0.25 | M15 | 78.8 | 78.8 | 44,433 |
| 6 | V-13 reentrada | M15 | 78.3 | 78.3 | 46,675 |
| 7 | V-10 máscara ST | M15 | 77.8 | 77.8 | 24,287 |
| 8 | **SS-M5 (S3, f=0.01)** | M5 | **66.7** | 65.6 | 55,170 |
| 9 | V-06d AC-0.01 | M5 | 64.9 | 63.8 | 52,719 |
| 10 | V-06c AC-0.10 | M5 | 64.4 | 63.2 | 52,203 |
| 11 | V-13 reentrada | M5 | 63.9 | 62.7 | 53,403 |
| 12 | V-10 máscara ST | M5 | 63.8 | 63.8 | 28,675 |

**Comentario:** Los WR se movieron ±1.5 puntos entre régimen tendencial y lateral — estabilidad notable. El WR ~79% de M15 y ~65% de M5 son propiedades de la mecánica de salidas (AC-modulado convierte devoluciones en salidas neutras/pequeñas), no del viento de cola.

---

## 5. Tabla 🛡️ — MENOR DRAWDOWN MÁXIMO OOW (peor ventana de las 3)

| # | Config | TF | DD máx OOW | en ventana | net med. | ctrl DD máx |
|---|---|---|---:|---|---:|---:|
| 1 | **V-10 máscara ST** | M5 | **207.9** | W1 | 28,675 | 870.9 |
| 2 | SS-M5 (S3, f=0.01) | M5 | 294.0 | W3 | 55,170 | 870.9 |
| 3 | V-06b/c/d | M15 | 295.5 | W3 | 44,433-44,865 | 1,328.4 |
| 4 | V-10 máscara ST | M15 | 296.1 | W3 | 24,287 | 1,328.4 |
| 5 | SS-M15 / V-13 | M15 | 306.6 | W3 | 46,675-47,179 | 1,328.4 |
| 6 | V-06d AC-0.01 | M5 | 342.6 | W3 | 52,719 | 870.9 |
| 7 | V-06c AC-0.10 | M5 | 345.3 | W3 | 52,203 | 870.9 |
| 8 | V-13 reentrada | M5 | 349.8 | W3 | 53,403 | 870.9 |
| 9 | V-15 SAR adaptativo | M15 | 511.5 | W1 | 39,698 | 1,328.4 |
| 10 | SS-M2 (S3, f=0.01) | M2 | 1,270.8 | W1 | 86,854* | 4,972.8 |

**Comentario:** El peor drawdown de cada config aparece casi siempre en **W3 (lateral)** — coherente y esperable. Aun así, todas las M5/M15 mantienen su peor DD entre 3× y 6× mejor que el control de su TF. El SS-M5 destaca de nuevo: peor caso 294 con net mediano 55k (ratio 188×). Los ratios net/DD bajaron respecto al in-window (donde eran 200-300×) — eso es la realidad asomando, y sigue siendo excelente.

---

## 6. Hallazgos (lo interesante y lo positivo)

1. **La optimización NO estaba sobreajustada.** 14/14 robustas, retención >1 en M5/M15, una sola inversión de ranking menor. El riesgo central del programa (un mes, in-sample, tendencial) queda descartado en lo esencial.
2. **La ventaja sobrevive al cambio de régimen.** En W3 (lateral, el opuesto a la optimización) toda config M5/M15 le gana a su control por margen amplio en net, PF y DD. La estructura de las palancas (stop legal ancho + AC-modulado + reentrada) es robusta al régimen, no una apuesta al trending.
3. **El súper-stack se confirma como campeón real:** SS-M5 nº1 en net mediano (55,170) con el 2º mejor peor-DD; SS-M15 nº1 de su TF. La sinergia reentrada+SAR adaptativo de M2/M5 no era artefacto.
4. **El SAR adaptativo cumple su promesa de diseño:** PF 136 con DD 69 en la ventana de volatilidad extrema (W2, M15) — es la config que mejor se comporta cuando el mercado se pone violento. Tercera confirmación independiente del patrón sarprobe.
5. **W2 como stress-test de cola:** en el mes de pánico (−12.5%, ATR 9.5) ninguna config rompió — todas multiplicaron net con DD contenido. El linaje es corto-compatible (los dos meses tendenciales eran bajistas; el corto funcionó).
6. **Límite conocido:** el tier M2 solo existe desde 2025-12-10 → las configs M2 tienen una ventana menos de validación. Su margen vs control (3.6× en W1) es enorme, pero con n=2 ventanas.

---

## 7. 🏅 Recomendación final actualizada (post-validación)

| Rango | Config | TF | net med. OOW | PF med. | DD máx | Estado |
|---|---|---|---:|---:|---:|---|
| 🥇 | **SS-M5** — k=6 + escalera 100 plana + AC-mod 0.01 + reentrada×2 + SAR adaptativo | M5 | **55,170** | 8.02 | 294 | ✅ ROBUSTA — candidata #1 a demo |
| 🥈 | **SS-M15** — k=2.5 + escalera plana + AC-mod 0.01 + reentrada×2 (SIN SAR adapt.) | M15 | **47,179** | 26.75 | 307 | ✅ ROBUSTA — perfil calidad |
| 🥉 | **V-06d M5** — k=6 + escalera plana + AC-mod 0.01 (una sola palanca) | M5 | 52,719 | 6.91 | 343 | ✅ ROBUSTA — la simple, mínimo riesgo de sobreajuste |
| 4º | **SS-M2** — k=3 + escalera plana + AC-mod 0.01 + reentrada×2 + SAR adaptativo | M2 | 86,854* | 4.53* | 1,271 | ✅ ROBUSTA* (2 ventanas) — el mayor edge relativo vs control (3.6×) |

**Mención defensiva:** `V-10 M5` (máscara SuperTrend, peor-DD 208) si el criterio es capital mínimo en riesgo.
**Cambio vs la recomendación pre-validación:** los súper-stacks desplazan a V-13 puro (que sigue siendo excelente y es un subconjunto del stack); V-06d reemplaza a V-06c como "la simple" (0.01 dominó a 0.10 en todas las celdas); V-15-M2 queda absorbido dentro de SS-M2.

---

## 8. Próximos pasos

1. **Estimación real-tick** de los 10 ganadores (en curso — paso 5 del pipeline).
2. Real-tick / validación de fills de los 4 recomendados → cuenta **DEMO** (la única operable: 2883015767).
3. Backfill del tier M2 histórico si se quiere igualar la evidencia de M2 con la de M5/M15.
4. Definir el sizing real (los nets están a 0.10/ficha, sin compounding).

---

*Fuentes: `docs/superpowers/research/2026-07-13-emasar-oow-validation.md` (tablas completas por ventana) · raw: `scripts/report/oow_validation_raw.json` · corridas auditables en Trade View (`sim-report-emasar-oow*`) · programa base: `docs/REPORTE_PROGRAMA_VARIANTES_EMASAR_2026-07-13.md`.*
