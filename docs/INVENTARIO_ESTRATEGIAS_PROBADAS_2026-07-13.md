# Inventario consolidado de estrategias de trading probadas
### (Backtests en MT5 — carpetas `D:/FOREX/` y `D:/WebDev/TOKATA/`)

> Fecha: 2026-07-13. Documento armado a partir de dos barridos forenses independientes (uno por carpeta), reconciliados. Solo lectura; no se ejecutó código ni se tocaron archivos de las estrategias.

## Cómo leer esto
Las dos carpetas **no son estrategias distintas**: son **el mismo proyecto en dos casas**.
- **`D:/WebDev/TOKATA/`** = el "cerebro": diseños, specs, originales de NinjaTrader, seguimiento de campaña, y el frente **TrailGuard**.
- **`D:/FOREX/`** = la "fábrica": el motor SENTINEL, las terminales MT5 donde corren los backtests, la base de datos de resultados, y el **sistema original de SENTINEL**.

Las 6 estrategias MT5 (SuperTrend, EMASAR, Sapitos, SapTrail, Pedro, STAC) están en **ambas**. Escala combinada: **+600 reportes** del probador de MT5 y una base con **274 corridas / 362 variantes / 2.192 operaciones / 476 hipótesis**.

## Resumen en una línea

| # | Estrategia | En criollo | Veredicto |
|---|---|---|---|
| 1 | **SuperTrend** | "Sigue la tendencia y date vuelta cuando cambie, sin parar nunca" | Mala en promedio, **pero con un bolsón real de ganancia** en oro a 15 min |
| 2 | **EMASAR** | "Entra a favor de la tendencia tras un retroceso, con confirmaciones" | Cerca de empatar, **con variantes muy buenas**; su stop original es ilegal en el bróker |
| 3 | **Sapitos** | "Apuesta a la ruptura del rango de apertura de Londres" | **La mejor en backtest** — pero **va en rojo en vivo** |
| 4 | **SapTrail** | Sapitos con otra forma de soltar la ganancia | Prometedora en una prueba; sin explorar |
| 5 | **Pedro** | "El precio se estiró; apuesta a que vuelve" | Se veía excelente, **era un espejismo**: no sirve con datos reales |
| 6 | **STAC** | SuperTrend + 2 confirmaciones, solo compras | Falló su versión base; una variante nueva "empezó a dar" |
| 7 | **SENTINEL (puntaje)** | Un "semáforo" técnico que aconseja, no opera solo | Sistema base del proyecto, en re-afinado; estudio real pendiente por falta de datos |
| 8 | **TrailGuard** | No es entrada: afina salidas del historial real | Regla anti-manoteo mejoraría ~+77% |

---

# 1. SuperTrend — "seguir la tendencia sin bajarse nunca"

**Qué es:** la más simple de todas. Una línea sigue al precio; **cuando el precio la cruza, la estrategia se da vuelta** (de comprada a vendida y viceversa). **Nunca sale del mercado** y **no usa stop ni objetivo**: el único cambio ocurre cuando la tendencia se invierte.

**Cuándo sirve/cuándo no:** brilla con tendencias claras y sostenidas; sufre en mercado lateral ("serrucho"), donde se da vuelta a cada rato y pierde de a poco.

**El hallazgo clave (reconciliando los dos reportes):**
- En **promedio pierde** (factor 0,92 en oro; hasta 672 operaciones por corrida por el serrucho).
- **Pero ese promedio engaña**: incluye 1 y 5 min donde el serrucho la mata. En **oro (XAUUSD) a 15 minutos con multiplicador ATR = 3 sí hay ventaja real**: ATR14×3 → **+$17.512, factor 1,49**; ATR7×3 → +$14.768; ATR10×3 → +$14.508. **Tres configuraciones vecinas ganando** (patrón, no suerte) y **se mantiene idéntico con ticks reales**.
- Nasdaq: 0 operaciones en 50 pruebas → problema técnico, no resultado.

**Variantes:** grilla período×multiplicador × 3 temporalidades × 2 instrumentos = 96 celdas + validación real. 114 reportes.

**Veredicto:** prometedora pero **sin validar fuera de muestra**; no corre en vivo. Nunca se cargó a la base de datos pese a ser la 2ª más probada.

**⚠️ Matiz de los "dos traders":** hay **dos** estrategias con SuperTrend. Esta "pura" se atribuye a "el usuario". La otra, **STAC**, cuyo pedido escrito **empieza literalmente con "el SuperTrend a 2 minutos…"**. Como el trader 1 *pidió algo mencionando SuperTrend*, **su estrategia probablemente es STAC, no esta**. A confirmar.

---

# 2. EMASAR — "entrar a favor de la tendencia en el retroceso, con confirmaciones"

**Es la estrategia del "segundo trader"** (confirmado en los diseños).

**Qué es:** subirse a la tendencia **cuando el precio hace una pausa**. *"El mercado sube; espero un retroceso y, si varias señales coinciden en que sigue, compro en ese respiro."*

**Cómo entra (5 condiciones, todas):** 1) media rápida(8) sobre lenta(20); 2) ambas apuntan igual y sin cruce reciente; 3) hubo un **pequeño retroceso** y la vela vuelve a favor; 4) el SAR confirma; 5) **2 de 3** osciladores de fuerza a favor.

**Variantes:** **V1 "3 fichas"** (abre 3 operaciones con salidas distintas: rápida / por giro de tendencia / corredora); **V2 "1 ficha"** (una sola, salida por vela de reversión — es la portada a Python).

**Desempeño:**
- Promedio en oro: casi empate (factor ~1,24).
- **Original "de verdad"** (SAR 0,3/0,3, 5 min, V1): **+$1.624,60, factor 2,82**.
- **Campeona** (SAR 0,005/0,05): **+$3.276,90, factor 4,56** (mejor de todas).
- Solo funciona bien en **5 minutos**. Nasdaq: 0 operaciones (problema técnico).

**🔴 Crítico:** su stop original de 3 pips **está por debajo del mínimo del bróker (0,50)** → **en real esas órdenes se rechazan**. Las V2 "sin stop duro" ganan bruto pero con **caídas catastróficas** (hasta perder casi todo). Más ganancia bruta ≠ mejor estrategia.

**Estado:** la **más madura en ingeniería** (referencia en Python, tests golden, visor propio). Resultados de empate-a-positivo con variantes muy buenas, **sin validar fuera de muestra**.

---

# Las demás, agrupadas por parecido

## Grupo A — Ruptura del rango de apertura (Sapitos y SapTrail)
*Misma entrada (romper el rango de la apertura de Londres); se diferencian en cómo sueltan la ganancia.*

**3. Sapitos — la "caballo de batalla".** Origen: NinjaTrader de **Matías Amenabar**. Mide el rango 08:00–08:15 (Londres); si el precio lo rompe **y** los filtros dicen que hay movimiento real (ADX, Choppiness, volumen), entra. Salida en **3 etapas** (stop fijo → sin-pérdida → arrastre). Cierra a las 14:00.
- **La mejor en backtest**: 314 reportes, 42 graduadas, mejor corrida **+$7.520,60 / factor 2,74**, confirmada con ticks reales.
- **🔴 Reconciliación clave:** las **39 variantes que corren AHORA en vivo (demo) van en rojo**: −2,97M CLP, 14 operaciones, 0% aciertos (al 12-jul). Puede ser muestra minúscula, error de despliegue, o divergencia real. **Es la alerta más importante del inventario, sin resolver.**

**4. SapTrail — Sapitos con salida distinta.** Entra igual, pero arrastra el stop a distancia fija por volatilidad. **Una sola prueba**: +$3.028 / factor 1,83. Prometedora pero **sin explorar** (prototipo de "entrada × salida" como piezas de Lego).

## Grupo B — Reversión a la media (Pedro)
**5. Pedro — "el precio se estiró, apuesta a que vuelve".** Opuesto a las de tendencia: apuesta a que el precio **recupera un 66,6%** del recorrido desde una vela de referencia.
- Con simulador rápido: **hermoso** (+$2.462, factor 2,33, 75,6% aciertos).
- Con **ticks reales: se derrumba** a −$173,30 (factor 0,92). El registro lo llama **"espejismo intrabar"** y **"NO-VIABLE"**. **Descartada** — caso de manual de backtest que no sobrevive la realidad.

## Grupo C — Tendencia con filtros de confirmación (STAC)
**6. STAC = SuperTrend + Accelerator + SAR, solo compras.** Como la SuperTrend pura pero con **dos guardaespaldas**. Nació de un **pedido textual del trader** (probablemente el "trader 1"): *"El SuperTrend a 2 min tiene que recomendar compra; solo entonces compro cuando el Accelerator pasa de negativo a positivo (1 min) y el SAR de 2 min pasa bajo el precio."*
- **Versión base: no funcionó** (0/20 con ganancia; factor 0,82; 0 graduadas de 114).
- **Pero** el trader pidió reformular usando **el color del Accelerator (rojo→verde)**, y esa variante **"empezó a dar ganancia"** — modesta, **sin validar**, y **los números exactos no están consolidados** (cabo suelto).

## Grupo D — El motor original de SENTINEL (puntaje compuesto)
**7. SENTINEL — el "semáforo" técnico que aconseja, no opera solo.** Sistema **fundacional**, anterior a la campaña. Calcula un **puntaje 0–100** (comprador/vendedor/neutral) mezclando medias/tendencia 30%, RSI 20%, MACD 25%, Bollinger 15%, patrones 10%, en varias temporalidades + correlación con otros activos. Apoya a un **trader humano** (tablero + chat IA). Su "backtest" compara el puntaje contra las **operaciones reales**. Objetivo original: **USDCLP**. **En re-afinado activo, pero el estudio real está bloqueado por falta de datos históricos largos.**

## Grupo E — No es entrada: optimización de salidas (TrailGuard)
**8. TrailGuard.** Toma las **operaciones reales de dos traders** y las re-corre **cambiando solo la forma de salir**. Hallazgos sobre datos reales: operaciones <8 min pierden, >10 min ganan; la hora 11 es tóxica; **regla anti-manoteo (R1): +76,9%** de mejora (hallazgo estrella); regla de achicar tamaño (R4): **refutada, −83,8%**. Parcialmente completa; rama de TraderB bloqueada esperando datos.

---

## Cabos sueltos / a confirmar
1. **Atribución "dos traders":** ningún doc lo mapea con nombre. Lo más probable: **Trader 1 → STAC**, **Trader 2 → EMASAR**; la SuperTrend pura parece idea propia. **A confirmar por el usuario.**
2. **Números de la STAC "por color":** hay que extraerlos de las corridas crudas.
3. **Sapitos en vivo en rojo:** falta aclarar si es muestra chica, error de despliegue o divergencia real. **Lo más urgente.**
4. Matriz grande de EMASAR (Fase 1) parece ejecutada solo en parte.
5. Nasdaq da 0 operaciones (SuperTrend y EMASAR) → problema técnico sin diagnosticar.

---

## Fuentes clave
- Tracker maestro: `D:/WebDev/TOKATA/docs/superpowers/plans/2026-07-02-campana-mt5-MASTER-TRACKER.md`
- Registro de resultados: `D:/WebDev/TOKATA/backtest_results/mt5_ledger.csv` + `D:/FOREX/data/research.db`
- SuperTrend: `D:/WebDev/TOKATA/research/SUPERTREND_FASE0_RESULTADOS_2026-07-06.md`
- EMASAR: `D:/WebDev/TOKATA/backtest_results/emasar_exploracion_apendice.md` + `D:/FOREX/docs/superpowers/specs/2026-07-10-emasar-v1-mt5-integration-design.md`
- Guía simple para traders: `D:/WebDev/TOKATA/research/GUIA_TRADERS_3_ESTRATEGIAS_2026-07-07.md`
- Sapitos en vivo (forward walk): `D:/WebDev/TOKATA/backtest_results/forward_daily/forward_daily_report.md`
- TrailGuard: `D:/WebDev/TOKATA/trailguard_opt/INFORME_REGLAS.md`
- STAC (pedido textual del trader): `D:/WebDev/TOKATA/docs/superpowers/specs/2026-07-07-stac-supertrend-ac-sar-design.md`
