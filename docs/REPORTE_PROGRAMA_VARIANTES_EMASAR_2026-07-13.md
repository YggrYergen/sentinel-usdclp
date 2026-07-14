# Programa de Variantes EMASAR — Reporte Consolidado Final
**Fecha:** 2026-07-13 · **Ventana:** 2026-06-08 → 2026-07-07 (in-sample, un mes) · **Símbolo:** XAUUSD
**Condiciones:** spread 0.5 modelado en el fill · stop legal (`init_sl_mode='range'`) · barras BID del lake · motor `emasar_variant.simular_variant` (entradas idénticas al motor congelado `emasar_ref`)

---

## 1. Qué se hizo

Se implementaron y backtestearon **15 variantes de mejora + 4 extensiones de barrido** sobre la estrategia EMASAR (escalera de 3 fichas), en 5 tandas secuenciales, cada una evaluada en **M1, M2, M5 y M15**. Total: **74 corridas ganadoras ingestadas** en `data/research.db` (visibles en Trade View) + cientos de celdas de barrido documentadas en los reportes por tanda (`docs/superpowers/research/2026-07-13-emasar-variants-batch{1..5}.md`).

**Convención de lectura:** `n` = trades-ficha (3 fichas por señal). Net/DD en USD al loteo del backtest. Todas las cifras son de la MISMA ventana y el MISMO motor — comparables entre sí, **no** comparables con los ledgers históricos de TOKATA (aquellos usaban stop ilegal de 3 pips y sin spread).

### Linaje del campeón (cómo se construyó la mejor config)
1. **V-09** — réplica del bundle ganador C04 (`confirm_mode=1, require_ema_order=False, EMA 8/20, SAR 0.3/0.3, trailing plano 100/100/100, k=1.0`) = **control**.
2. **+ V-01/V-01b** — stop legal más ancho: k óptimo por TF (M2 k=3 · M5 k=6 · M15 k=2.5 · M1 k=6). El codo real está en k≈2.5–3.
3. **+ V-06/V-06b/V-06c** — trailing modulado por AC: cuando el Accelerator se desacelera contra la posición, la distancia de trailing se multiplica por un factor. 0.5 → 0.25 → **0.10** mejoró monótonamente (5 tandas sin encontrar el codo).
4. **+ V-13** — reentrada controlada (max 2) tras salida completa por trailing con SAR intacto: única palanca de la tanda 5 **sin desventaja en ningún TF**.

---

## 2. Tabla 💰 — MAYOR NET (top 20, sin V-12*)

| # | Config | TF | net | PF | WR% | maxDD | n |
|---|---|---|---:|---:|---:|---:|---:|
| 1 | **V-13 reentrada (rmax2, apilado)** | M5 | **+46,264.8** | 6.92 | 64.6 | 186.0 | 2,964 |
| 2 | V-06c AC-mod 0.10 (campeón) | M5 | +45,815.7 | 7.34 | 65.8 | 209.7 | 2,853 |
| 3 | V-06b AC-mod 0.25 (campeón) | M5 | +45,059.7 | 7.03 | 64.8 | 218.7 | 2,853 |
| 4 | V-06 AC-mod 0.5 (apilado) | M5 | +43,799.7 | 6.48 | 63.3 | 233.7 | 2,853 |
| 5 | **V-13 reentrada (rmax2, apilado)** | M15 | **+43,027.8** | 30.38 | 79.3 | 186.6 | 1,002 |
| 6 | V-15 SAR adaptativo (apilado) | M5 | +42,425.1 | 8.44 | 68.0 | 241.5 | 2,424 |
| 7 | V-01b k=6.0 | M5 | +41,279.7 | 5.43 | 61.1 | 263.7 | 2,853 |
| 8 | V-06c AC-mod 0.10 (campeón) | M15 | +41,126.7 | 31.66 | 79.8 | 150.3 | 948 |
| 9 | V-06b AC-mod 0.25 (campeón) | M15 | +40,897.2 | 30.51 | 79.4 | 948 |
| 10 | V-06 AC-mod 0.5 (apilado) | M15 | +40,514.7 | 28.70 | 78.8 | 150.3 | 948 |
| 11 | V-01/V-01b k=2.0/2.5 | M15 | +39,749.7 | 25.11 | 77.9 | 150.3 | 948 |
| 12 | V-05 TP 1.5/3.0R (apilado, ≈inerte) | M15 | +38,714.4 | 24.48 | 77.9 | 150.3 | 948 |
| 13 | V-09 control C04 | M5 | +37,469.7 | 3.87 | 60.9 | 633.6 | 2,853 |
| 14 | V-09 control C04 | M15 | +37,326.6 | 10.71 | 76.9 | 881.1 | 948 |
| 15 | V-15 SAR adaptativo (apilado) | M15 | +36,639.9 | **32.38** | 79.4 | 129.3 | 801 |
| 16 | V-02 breakeven 1.5R | M15 | +36,449.1 | 10.41 | 76.3 | 881.1 | 948 |
| 17 | V-04 escalera 80/150/230 | M15 | +32,455.0 | 7.26 | 71.6 | 881.1 | 945 |
| 18 | **V-15 SAR adaptativo (apilado)** | M2 | **+31,181.4** | 2.27 | 48.0 | 1,116.0 | 6,048 |
| 19 | V-06c AC-mod 0.10 (campeón) | M2 | +30,777.9 | 2.00 | 46.0 | 1,854.9 | 7,233 |
| 20 | V-13 reentrada (rmax2, apilado) | M2 | +30,174.6 | 1.93 | 45.1 | 2,083.5 | 7,524 |

\* **V-12 (entrada intrabar)** produjo M1 +231,783 · M2 +224,542 · M5 +169,597 · M15 +123,455 — se reporta APARTE en §7 porque su firma estadística (WR 98.7%, PF 1287 en M15) es la de un **sesgo de anticipación** pendiente de auditoría. No compite en esta tabla hasta validarse.

**Comentario:** El dinero vive en **M5** — las 4 primeras posiciones son M5 y todas comparten el mismo esqueleto (k=6 + escalera plana + AC-modulado). La reentrada (V-13) le gana por nariz al AC-0.10 en net, pero con PF levemente menor — son ganancias del mismo orden por caminos distintos. En M2 la sorpresa es **V-15 (SAR adaptativo): mejor net, mejor PF y menor DD que cualquier otra config M2** — la única mejora M2 que domina en las tres métricas a la vez. M1 no aparece: **ninguna config limpia fue rentable en M1** (mejor caso V-11 con −5,063; M1 queda descartado para operar con este linaje).

---

## 3. Tabla 🏆 — MAYOR PROFIT FACTOR (top 15, solo rentables, sin V-12)

| # | Config | TF | PF | net | WR% | maxDD | n |
|---|---|---|---:|---:|---:|---:|---:|
| 1 | **V-15 SAR adaptativo** | M15 | **32.38** | +36,639.9 | 79.4 | 129.3 | 801 |
| 2 | V-06c AC-mod 0.10 | M15 | 31.66 | +41,126.7 | 79.8 | 150.3 | 948 |
| 3 | V-10 máscara ST-M15 | M15 | 31.63 | +22,688.7 | 79.6 | **77.1** | 486 |
| 4 | V-06b AC-mod 0.25 | M15 | 30.51 | +40,897.2 | 79.4 | 150.3 | 948 |
| 5 | V-13 reentrada rmax2 | M15 | 30.38 | +43,027.8 | 79.3 | 186.6 | 1,002 |
| 6 | V-06 AC-mod 0.5 | M15 | 28.70 | +40,514.7 | 78.8 | 150.3 | 948 |
| 7 | V-01/V-01b k óptimo | M15 | 25.11 | +39,749.7 | 77.9 | 150.3 | 948 |
| 8 | V-05 TP-R (≈inerte) | M15 | 24.48 | +38,714.4 | 77.9 | 150.3 | 948 |
| 9 | V-08 gate ac4 | M15 | 24.24 | +11,613.6 | 74.2 | 118.8 | 267 |
| 10 | V-09 control | M15 | 10.71 | +37,326.6 | 76.9 | 881.1 | 948 |
| 11 | V-02 breakeven 1.5R | M15 | 10.41 | +36,449.1 | 76.3 | 881.1 | 948 |
| 12 | V-14 solo-long | M15 | 10.04 | +18,814.5 | 76.5 | 881.1 | 447 |
| 13 | **V-15 SAR adaptativo** | M5 | **8.44** | +42,425.1 | 68.0 | 241.5 | 2,424 |
| 14 | V-06c AC-mod 0.10 | M5 | 7.34 | +45,815.7 | 65.8 | 209.7 | 2,853 |
| 15 | V-06b AC-mod 0.25 | M5 | 7.03 | +45,059.7 | 64.8 | 218.7 | 2,853 |

**Comentario:** La **calidad vive en M15** — PF de dos dígitos en todo el top-12. Y el nº1 es de nuevo **V-15**: el SAR adaptativo pierde algo de net vs el campeón en M15 (36.6k vs 41.1k) pero lo convierte en el PF más alto del programa completo y uno de los DD más bajos — el clasificador de régimen filtra trades malos a costa de volumen. Esto replica exactamente el patrón histórico del sarprobe (el SAR pequeño incondicional perdía en M15; el adaptativo evita ese daño cambiando a 0.3/0.3 cuando corresponde). En M5, V-15 también es el PF líder (8.44). El AC-modulado 0.10 es el mejor equilibrio PF×net.

---

## 4. Tabla 🎯 — MAYOR WIN RATE (top 12, solo rentables, sin V-12)

| # | Config | TF | WR% | net | PF | maxDD |
|---|---|---|---:|---:|---:|---:|
| 1 | V-06c AC-mod 0.10 | M15 | **79.8** | +41,126.7 | 31.66 | 150.3 |
| 2 | V-10 máscara ST-M15 | M15 | 79.6 | +22,688.7 | 31.63 | 77.1 |
| 3 | V-06b AC-mod 0.25 | M15 | 79.4 | +40,897.2 | 30.51 | 150.3 |
| 4 | V-15 SAR adaptativo | M15 | 79.4 | +36,639.9 | 32.38 | 129.3 |
| 5 | V-13 reentrada rmax2 | M15 | 79.3 | +43,027.8 | 30.38 | 186.6 |
| 6 | V-06 AC-mod 0.5 | M15 | 78.8 | +40,514.7 | 28.70 | 150.3 |
| 7 | V-01/V-01b k óptimo | M15 | 77.9 | +39,749.7 | 25.11 | 150.3 |
| 8 | V-09 control | M15 | 76.9 | +37,326.6 | 10.71 | 881.1 |
| 9 | **V-15 SAR adaptativo** | M5 | **68.0** | +42,425.1 | 8.44 | 241.5 |
| 10 | V-06c AC-mod 0.10 | M5 | 65.8 | +45,815.7 | 7.34 | 209.7 |
| 11 | V-13 reentrada rmax2 | M5 | 64.6 | +46,264.8 | 6.92 | 186.0 |
| 12 | V-10 máscara ST-M15 | M5 | 64.4 | +24,273.9 | 6.81 | 142.5 |

**Comentario:** WR alto NO paga con cola izquierda aquí (el miedo clásico) — las configs de WR≥78% también tienen los PF y DD mejores. La razón estructural: el AC-modulado convierte trades que iban a devolver todo en salidas pequeñas positivas/neutras, subiendo WR y bajando DD a la vez. Para un trader que necesita confort psicológico (rachas cortas de pérdida), M15 con cualquier config del top-6 es el hábitat natural.

---

## 5. Tabla 🛡️ — MENOR DRAWDOWN (top 12, solo rentables, sin V-12)

| # | Config | TF | maxDD | net | net/DD | PF |
|---|---|---|---:|---:|---:|---:|
| 1 | **V-10 máscara ST-M15** | M15 | **77.1** | +22,688.7 | 294× | 31.63 |
| 2 | V-08 gate ac4 | M15 | 118.8 | +11,613.6 | 98× | 24.24 |
| 3 | V-15 SAR adaptativo | M15 | 129.3 | +36,639.9 | 283× | 32.38 |
| 4 | V-10 máscara ST-M15 | M5 | 142.5 | +24,273.9 | 170× | 6.81 |
| 5 | V-06c AC-mod 0.10 | M15 | 150.3 | +41,126.7 | 274× | 31.66 |
| 6 | V-01b/V-05/V-06/V-06b/V-07 | M15 | 150.3 | 38.7k–40.9k | ~260× | 24–31 |
| 7 | **V-13 reentrada rmax2** | M5 | **186.0** | **+46,264.8** | **249×** | 6.92 |
| 8 | V-13 reentrada rmax2 | M15 | 186.6 | +43,027.8 | 231× | 30.38 |
| 9 | V-06c AC-mod 0.10 | M5 | 209.7 | +45,815.7 | 218× | 7.34 |
| 10 | V-06b AC-mod 0.25 | M5 | 218.7 | +45,059.7 | 206× | 7.03 |
| 11 | V-06 AC-mod 0.5 | M5 | 233.7 | +43,799.7 | 187× | 6.48 |
| 12 | V-15 SAR adaptativo | M5 | 241.5 | +42,425.1 | 176× | 8.44 |

**Comentario:** Los ratios net/DD de 150-300× en un mes son **anormalmente buenos y hay que decirlo sin anestesia: es un mes tendencial e in-sample** — estos ratios NO van a sostenerse fuera de muestra; lo que importa es el ORDEN relativo, no el valor absoluto. Dicho eso, dos perfiles destacan: **V-10 (máscara SuperTrend M15)** es la config "defensiva" — sacrifica la mitad del net a cambio del DD más bajo del programa (perfil para capital sensible), y **V-13 M5** logra el mejor net del programa con el 4º menor DD de M5 — no es un trade-off, es dominancia. Nótese que el control V-09 tiene DD 881 en M15: el linaje completo (k + AC-mod) redujo el drawdown **5.9×** mientras subía el net.

---

## 6. Los hallazgos estructurales (lo interesante y lo positivo)

1. **La palanca maestra fue el trailing modulado por AC (V-06→06c).** Mecanismo: distancia normal mientras el Accelerator empuja a favor; al desacelerarse, la distancia se multiplica por el factor. Con factor 0.10, en la práctica es "el primer parpadeo del momentum te pone un trailing de 10 pips". Mejoró monótonamente 0.7→0.5→0.25→0.10 en CINCO tandas sin encontrar el codo. Es también la única palanca que mejoró M1 (aunque no lo volvió rentable). **Herencia STAC confirmada:** las transiciones del AC llevan señal real en XAU.

2. **El stop legal ancho gana, y el codo está en k≈2.5–3.** Más allá de k≈3 el stop casi nunca se toca y las métricas convergen. El trailing (no el stop inicial) es quien gestiona el riesgo en este linaje. Positivo adicional: el stop legal por rango era la corrección del trader — validada cuantitativamente.

3. **La reentrada (V-13) fue la única palanca sin desventaja.** Mejoró o empató en los 4 TFs. Racional confirmado: cuando la escalera completa sale por trailing y el SAR sigue a favor, la tendencia suele continuar — reengancharse (hasta 2 veces) captura ese tramo. +5.2% en M15, +2.7% en M5 sobre un campeón ya optimizado.

4. **El SAR adaptativo (V-15) valida la intuición del trader — con matices finos.** No ganó por net en M5/M15, pero es el **mejor PF del programa** (32.4 en M15), el **mejor M2 en las tres métricas**, y replicó con stop legal el patrón sarprobe (SAR pequeño ayuda selectivamente; el switching evita su daño en M15). Es la variante con mejor *calidad por trade* del programa. El precedente histórico (sarprobe: SAR 0.005/0.05 campeón local en M5 con PF 4.56) fue localizado y contrastado — el recuerdo del trader era correcto.

5. **Saber qué NO funciona vale tanto como lo que sí** (todo con evidencia de 4 TFs):
   - ❌ Cobrar antes pierde: breakeven (V-02), TP escalonado (V-05), trailing por rango (V-03) — toda interferencia "protectora" temprana costó net.
   - ❌ Des-igualar la escalera (V-04): la plana 100/100/100 domina; en M2 las 24 combinaciones alternativas dieron negativo.
   - ❌ Asimetría long/short (V-14): no hay sesgo estructural explotable.
   - ⚪ Salida AC-decel del runner (V-07): inerte — el trailing la domina siempre (0 disparos reales).
   - 🌗 Filtros de población (V-08 ac4, V-10 máscara ST): salvan M1/DD pero cortan demasiado volumen en los TFs rentables — útiles solo como perfil defensivo.

6. **Jerarquía de timeframes nítida:** M15 = calidad (PF 25-32, WR ~80%) · M5 = dinero (net máximo) · M2 = volumen con filo fino (solo V-15/V-06c/V-13 lo hacen decente) · **M1 = descartado** (ninguna config limpia rentable; 463 trades/día muelen el net contra el spread).

---

## 7. Advertencias (léelas antes de decidir nada)

- 🔴 **V-12 (entrada intrabar): SESGO DE ANTICIPACIÓN CONFIRMADO** (auditoría 2026-07-13, `docs/superpowers/research/2026-07-13-v12-lookahead-audit.md`). El "toque" intrabar se fija en `ema_pull[i]`, una EMA calculada **con el cierre de la propia vela i** — nivel incognoscible al momento del toque; el SL inicial usa además el rango completo de esa vela. La re-simulación causal (gates al cierre i, fill al open i+1, mismas señales) reproduce el campeón casi exacto: **la supervivencia del exceso es −1.0% a −2.6% en los 4 TFs** (M2 +26,117 vs los +224,542 reclamados; M5 +43,822 vs +169,597; M15 +38,762 vs +123,455) y el peor-caso de fill pierde contra el campeón en 0/4 TFs. El 60-95% del net reclamado era mejora fantasma del precio de entrada (entradas en el 22-32% superior del rango favorable de la vela). **V-12 queda DESCARTADO; las 4 recomendaciones del §8 no cambian.** Runs auditables: `sim-report-emasar-v12a-*` (causal) y `v12w-*` (peor-caso) en Trade View.
- ⚠️ **V-11 (filtro horario): las horas se eligieron en la misma ventana que se evalúan** (overfit por construcción). Solo M1/M2 mostraron efecto. Requiere validación en ventana distinta.
- ⚠️ **Todo el programa es UNA ventana de un mes, tendencial, in-sample.** Los rankings son sólidos; los valores absolutos (especialmente net/DD) no son promesas. Antes de operar cualquier config: validar en 1-2 ventanas de contraste del lake (ideal: un mes lateral).
- ⚠️ Combinaciones no probadas: V-13 se probó sobre AC-0.25 (no 0.10); V-15 y V-13 nunca se apilaron juntos. El "super-stack" (k + escalera plana + AC-0.10 + reentrada + SAR adaptativo) NO existe aún como corrida.

---

## 8. 🏅 Las 4 configuraciones más recomendadas

| Rango | Config completa | TF | net | PF | WR% | maxDD | Por qué |
|---|---|---|---:|---:|---:|---:|---|
| 🥇 | **V-13**: k=6.0 + escalera 100/100/100 + AC-mod 0.25 + reentrada max 2 | **M5** | +46,265 | 6.92 | 64.6 | 186.0 | **El mejor net limpio del programa con el 4º menor DD de M5.** No es un trade-off: domina. Todas sus piezas fueron validadas por separado. `sim-report-emasar-v13-m5` |
| 🥈 | **V-13**: k=2.5 + escalera 100/100/100 + AC-mod 0.25 + reentrada max 2 | **M15** | +43,028 | 30.38 | 79.3 | 186.6 | El mejor M15 por net con PF 30 y WR 79%: la config "dormir tranquilo" — pocas operaciones, alta calidad, drawdown mínimo. `sim-report-emasar-v13-m15` |
| 🥉 | **V-15**: k=3.0 + escalera plana + AC-mod 0.25 + SAR adaptativo (0.3/0.3 ↔ 0.005/0.05, ventana 200) | **M2** | +31,181 | 2.27 | 48.0 | 1,116 | **Domina M2 en las TRES métricas** (net, PF, DD) — único caso del programa. Y es la validación práctica de la intuición del trader sobre el SAR pequeño del sarprobe. `sim-report-emasar-v15-m2` |
| 4º | **V-06c**: k=6.0 + escalera 100/100/100 + AC-mod **0.10** | **M5** | +45,816 | 7.34 | 65.8 | 209.7 | La config más SIMPLE del top (una sola palanca sobre el k óptimo), 2º mejor net, mejor PF de M5 entre los top-net. Menos piezas móviles = menos riesgo de sobreajuste. `sim-report-emasar-v06c-m5` |

**Mención defensiva:** si el criterio fuera proteger capital ante todo, `V-10 M15` (DD 77, PF 31.6, medio net) es el perfil conservador.

**Criterio usado:** solo configs sin caveats pendientes (excluye V-12 y V-11), dominancia multi-métrica antes que net puro, y diversidad de palancas (reentrada, SAR adaptativo, AC puro) para que la validación fuera de muestra pueda discriminar cuál mecanismo es robusto y cuál era ruido de la ventana.

---

## 9. Próximos pasos sugeridos (en orden de valor)

1. **Validación out-of-window** de las 4 recomendadas en 1-2 ventanas de contraste del lake (crítico antes de operar).
2. **Auditoría del sesgo de V-12** (gates sobre vela anterior cerrada) — el premio potencial es demasiado grande para ignorarlo, y demasiado sospechoso para creerlo.
3. **El super-stack**: probar V-13 + AC-0.10 + V-15 juntos (las piezas nunca se combinaron todas).
4. Continuar el barrido AC-mod bajo 0.10 (el codo sigue sin aparecer).
5. Real-tick / validación MT5 del finalista que sobreviva el punto 1.

---

## 10. Extensión post-programa: barrido AC-mod bajo 0.10 (V-06d)

Continuación mecánica del punto 4 de la sección 9: barrido de `ac_modulate_factor`
en {0.01, 0.03, 0.05, 0.07, 0.09} sobre la config campeona (mismo stack que V-06c),
4 TF × 5 factores = 20 corridas. Cero código nuevo de motor. Runner:
`scripts/report/gen_variant_batch6.py`. Reporte completo:
`docs/superpowers/research/2026-07-13-emasar-variants-batch6-acsub01.md`.

**Tabla de resultados (factor descendente, incluye la referencia 0.10 = V-06c):**

### M1

| factor | net | PF | WR | maxDD | n |
|---|---:|---:|---:|---:|---:|
| 0.10 (ref) | -14,922.0 | 0.80 | -- | -- | -- |
| 0.09 | -14,662.2 | 0.8017 | 33.96 | 19,589.1 | 13,923 |
| 0.07 | -14,142.6 | 0.8079 | 34.20 | 19,187.1 | 13,923 |
| 0.05 | -13,623.0 | 0.8142 | 34.43 | 18,785.1 | 13,923 |
| 0.03 | -13,103.4 | 0.8206 | 34.63 | 18,383.1 | 13,923 |
| **0.01** | **-12,583.8** | 0.8270 | 34.82 | 17,981.1 | 13,923 |

### M2

| factor | net | PF | WR | maxDD | n |
|---|---:|---:|---:|---:|---:|
| 0.10 (ref) | +30,777.9 | 2.00 | 46.0 | 1,854.9 | -- |
| 0.09 | +30,903.0 | 2.0109 | 46.00 | 1,846.2 | 7,233 |
| 0.07 | +31,153.2 | 2.0232 | 46.25 | 1,828.8 | 7,233 |
| 0.05 | +31,403.4 | 2.0354 | 46.50 | 1,811.4 | 7,233 |
| 0.03 | +31,653.6 | 2.0476 | 46.62 | 1,794.0 | 7,233 |
| **0.01** | **+31,903.8** | 2.0599 | 46.74 | 1,776.6 | 7,233 |

### M5

| factor | net | PF | WR | maxDD | n |
|---|---:|---:|---:|---:|---:|
| 0.10 (ref) | +45,815.7 | 7.34 | 65.8 | 209.7 | -- |
| 0.09 | +45,866.1 | 7.3653 | 66.04 | 209.1 | 2,853 |
| 0.07 | +45,966.9 | 7.4054 | 66.25 | 207.9 | 2,853 |
| 0.05 | +46,067.7 | 7.4458 | 66.25 | 206.7 | 2,853 |
| 0.03 | +46,168.5 | 7.4866 | 66.25 | 205.5 | 2,853 |
| **0.01** | **+46,269.3** | 7.5269 | 66.46 | 204.3 | 2,853 |

### M15

| factor | net | PF | WR | maxDD | n |
|---|---:|---:|---:|---:|---:|
| 0.10 (ref) | +41,126.7 | 31.66 | 79.8 | 150.3 | -- |
| 0.09 | +41,142.0 | 31.7282 | 79.75 | 150.3 | 948 |
| 0.07 | +41,172.6 | 31.8617 | 80.38 | 150.3 | 948 |
| 0.05 | +41,203.2 | 31.9822 | 80.38 | 150.3 | 948 |
| 0.03 | +41,233.8 | 32.1034 | 80.38 | 150.3 | 948 |
| **0.01** | **+41,264.4** | 32.2254 | 80.38 | 150.3 | 948 |

**Hallazgo del codo (regla mecánica: primer factor cuyo net cae por debajo del
factor anterior, ordenando 0.10→0.01):** en las **4 TF el net mejora
monotónicamente en cada paso** de 0.10 a 0.01, sin invertirse en ningún punto del
rango barrido. **Codo: monótono hasta 0.01 en M1, M2, M5 y M15** — el barrido no
llegó al punto de retornos decrecientes; 0.01 (el valor más bajo probado) es el
mejor factor en las 4 TF.

**¿V-06d supera el mejor vigente del programa por TF?**

- **M1**: mejor V-06d = -12,583.8 (factor 0.01). Sigue sin ser rentable — no hay
  "mejor vigente" positivo en M1 que superar; mejora +2,338.2 sobre la referencia
  0.10 pero no cambia el veredicto de M1.
- **M2**: mejor V-06d = +31,903.8 (factor 0.01) **supera** el mejor vigente del
  programa (V-15 +31,181.4) por +722.4.
- **M5**: mejor V-06d = +46,269.3 (factor 0.01) **NO supera** el mejor vigente del
  programa (V-13 +46,264.8) — queda apenas +4.5 por encima en términos absolutos,
  pero V-06d es una config más simple (una sola palanca AC-mod sobre el k óptimo,
  sin reentrada) por lo que en la práctica **empata/mejora marginalmente** con
  menos piezas móviles.
- **M15**: mejor V-06d = +41,264.4 (factor 0.01) **NO supera** el mejor vigente
  del programa (V-13 +43,027.8) — queda -1,763.4 por debajo.

## 11. Extensión post-programa: super-stack (S1/S2/S3)

Combinación mecánica del punto 3 de la sección 9: apilar por primera vez las dos
palancas ganadoras nunca combinadas -- **V-13 (reentrada, `reentry_max=2`)** y
**V-15 (SAR adaptativo por régimen, `sar_adaptive=True`)** -- sobre el esqueleto
campeón, cruzado con `ac_modulate_factor` en {0.10, 0.01}. 3 formas de stack (S1
= solo reentrada, S2 = solo SAR adaptativo, S3 = ambas) × 2 factores × 4 TF = 24
corridas. Cero código nuevo de motor. Runner: `scripts/report/gen_variant_batch7.py`.
Reporte completo: `docs/superpowers/research/2026-07-13-emasar-variants-batch7-superstack.md`.

**Resultados -- mejor stack/factor por TF:**

| TF | ganador | net | PF | maxDD | vs mejor vigente previo | Δ | % |
|---|---|---:|---:|---:|---|---:|---:|
| M1 | S3 (reentrada+SAR adapt.) f=0.01 | +803.4 | 1.01 | 8,332.5 | V-06d f=0.01 (-12,583.8) | +13,387.2 | +106.4% |
| M2 | S3 (reentrada+SAR adapt.) f=0.01 | +40,263.6 | 2.55 | 800.7 | V-06d f=0.01 (+31,903.8) | +8,359.8 | +26.2% |
| M5 | S3 (reentrada+SAR adapt.) f=0.01 | +48,849.9 | 8.95 | 128.1 | V-06d f=0.01 (+46,269.3) | +2,580.6 | +5.6% |
| M15 | S1 (solo reentrada) f=0.01 | +43,459.8 | 32.47 | 186.6 | V-13 rmax2 f=0.25 (+43,027.8) | +432.0 | +1.0% |

**Interacción (base = V-06c/d sin ninguna palanca, mismo factor):** M2 y M5
muestran **SINERGIA** (S3 supera la suma de las mejoras individuales de S1 y S2
por un margen amplio, ~+95-102% en M2). M1 queda en el límite ADDITIVE/SYNERGY
(+9.9% del esperado en f=0.01). **M15 es el único caso de INTERFERENCIA:** el
SAR adaptativo solo (S2) ya resta net frente a la base en M15, y apilarlo con la
reentrada (S3) diluye la ganancia de la reentrada en vez de sumarse -- por eso el
ganador M15 es S1 (reentrada sola), no el stack completo.

**¿Se convierte en el nuevo mejor vigente del programa, por TF?**

- **M1**: SÍ, y es el hallazgo más notable -- **primera config del programa
  entero con net positivo en M1** (todas las tandas 1-6 lo tenían descartado
  como no rentable con ninguna config limpia).
- **M2**: SÍ, +26.2% sobre el mejor vigente (V-06d f=0.01).
- **M5**: SÍ, +5.6% sobre el mejor vigente (V-06d f=0.01).
- **M15**: SÍ, aunque marginal (+1.0%) -- y el ganador NO es el super-stack
  completo sino reentrada sola con f=0.01 (la mejora viene de bajar el factor
  AC, no de sumar el SAR adaptativo, que en M15 interfiere).

*Fuentes: reportes por tanda en `docs/superpowers/research/2026-07-13-emasar-variants-batch{1..5}.md`, extensión `docs/superpowers/research/2026-07-13-emasar-variants-batch6-acsub01.md` y super-stack `docs/superpowers/research/2026-07-13-emasar-variants-batch7-superstack.md` · corridas en `data/research.db` (`sim-report-emasar-v*`, `sim-report-emasar-ss-*`) auditables posición por posición en Trade View · precedente histórico sarprobe en `D:/WebDev/TOKATA/backtest_results/_sarprobe_ledger.csv` y `emasar_exploracion_apendice.md`.*

---

## 12. Cota realista de fills (live_fill_mode)

El backtest clásico sube el stop trailing de cada ficha con el **high (y, si `ac_modulate=True`, el AC) de la MISMA barra**, y puede registrar la salida intra-barra a ese nivel recién subido — información solo conocible al cierre de esa barra. Un ejecutor en vivo no puede replicarlo (su SL en el servidor solo se actualiza al cierre de barra). Nuevo kwarg aditivo `live_fill_mode: bool = False` en `simular_variant` (motor sin cambios cuando está OFF, pineado con 5 tests nuevos + gate completo en 137/137) reproduce esa semántica exacta: el chequeo intra-barra usa el SL vigente al **cierre de la barra anterior**, y si el nivel recién subido ya está violado por el CIERRE de la misma barra (sin haber tocado el nivel anterior), la ficha cierra a ese cierre con un fallback marcado `same_bar_fallback`.

Se re-simularon los 13 configs del roster (SS-M1/M2/M5/M15, V06B/C/D en sus TFs, V13-M5/M15, V15-M2) en AMBOS modos, sobre IW + las 3 ventanas OOW (W1/W2/W3; M2 sin W3 por límite del lake) — 51 combinaciones config×ventana con datos. Runner: `scripts/report/gen_livefill_bound.py`. Reporte completo: `docs/superpowers/research/2026-07-13-livefill-bound.md`.

**Resultado central:** en las **51/51 combinaciones**, el 100% de las salidas `EXIT_TRAIL` son eventos `same_bar_fallback` — el trailing calibrado en este programa (estrecho, agravado por `ac_modulate_factor` bajo) queda violado por el cierre de la misma barra en que se calcula prácticamente siempre en este dataset, no como excepción rara.

**Tabla resumen — headline configs (IW):**

| Config | Net clásico (IW) | Net live-fill (IW) | Δ Net | Δ Net % | % fallback |
|---|---:|---:|---:|---:|---:|
| SS-M2 | 40,263.6 | −30,955.2 | −71,218.8 | −176.9% | 100.0% |
| SS-M5 | 48,849.9 | −9,993.3 | −58,843.2 | −120.5% | 100.0% |
| SS-M15 | 43,459.8 | −1,124.4 | −44,584.2 | −102.6% | 100.0% |
| V06D-M5 | 46,269.3 | −9,975.6 | −56,244.9 | −121.6% | 100.0% |

**Veredicto por TF (f=0.01 vs. 0.10 vs. 0.25, bajo live-fill, IW):**

- **M15: `family flat`** — V06D (0.01) / V06C (0.10) / V06B (0.25) dan el net **exactamente idéntico** (−452.1, 918 trades) bajo `live_fill_mode`: una vez que el fallback mismo-barra se activa, el precio de salida es el cierre de la barra, independiente del factor AC — el eje que dominó el ranking in-sample deja de discriminar.
- **M5: `family flat`** — V06D (0.01, −9,975.6) vs. V06C (0.10, −9,980.4): diferencia de $4.8 sobre ~−$10k, ruido.
- **M2/M1**: sin par aislado f=0.01 vs. otro factor dentro de este roster (solo hay una config por TF); ambos quedan negativos bajo live-fill en todas las ventanas con datos.

**¿Cambia la recomendación §7 OOW?** El §7 de `REPORTE_VALIDACION_OOW_EMASAR_2026-07-13.md` (top-4: SS-M5 🥇, SS-M15 🥈, V06D-M5 🥉, SS-M2 4º) queda **descalificado tal cual está calibrado para operar en vivo al net reportado**: las 4 configs recomendadas dan net NEGATIVO bajo `live_fill_mode` en el régimen tendencial (IW/W1) que las ventanas de validación usaron como base. La ÚNICA franja donde el edge sobrevive es la ventana de volatilidad extrema (W2, marzo 2026) en M15 (SS-M15/V06D-M15/V06C-M15/V06B-M15/V13-M15, todas +$9.2k a +$9.6k, PF ~1.24-1.26 bajo fills realistas) y, más débilmente, en el régimen lateral W3 en M15 (+$1.6k a +$2.9k). **Nuevo ranking bajo fills realistas (solo dentro de §12, no reemplaza §7):** ninguna de las 13 configs queda recomendable para demo AL CALIBRE ACTUAL del trail; si hay que elegir una familia para seguir iterando, **M15 con cualquier factor AC (son indistinguibles bajo live-fill)** es la menos mala (única con tramos de net positivo bajo fills realistas), mientras que M1/M2/M5 no muestran ninguna celda positiva bajo `live_fill_mode` en ninguna ventana. **Antes de demo, el trail debe re-calibrarse (más ancho, o `ac_modulate_factor` menos agresivo, o lógica explícita "next-bar-only") y re-evaluarse contra `live_fill_mode=True`, no contra el net clásico.**

*Fuente adicional: `docs/superpowers/research/2026-07-13-livefill-bound.md` (tablas completas 51 celdas, mecanismo del 100% fallback, gates del motor) · runner `scripts/report/gen_livefill_bound.py` · raw `scripts/report/livefill_bound_raw.json` · corridas live-fill auditables en Trade View (`sim-report-emasar-lf-*`).*
