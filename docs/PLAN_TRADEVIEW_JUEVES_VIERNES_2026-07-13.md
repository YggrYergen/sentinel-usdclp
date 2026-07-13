# Plan: graficar en "Trade View" las corridas del jueves-viernes con sus indicadores
### Archivo 2 de 2 · Fecha 2026-07-13 · ESTADO: PLAN PARA REVISAR (no ejecutado)

> Este documento describe **cómo** dejar las corridas pedidas visibles y analizables en Trade View. **No se ha tocado código** para escribirlo. Se revisa, se corrige, y **recién cuando esté aprobado se ejecuta** (ahí sí habrá cambios de código, acotados y "agregar, no modificar").

---

## 🔴 0. El bloqueador que manda sobre todo: NO hay datos del jueves-viernes

Verificado hoy: **el lake de datos de XAUUSD termina el 2026-07-07 ~18:57 en todos los timeframes** (M1/M2/M5/M15/H1/D). El jueves **2026-07-09** y viernes **2026-07-10** (las fechas que queremos) **tienen 0 barras descargadas.**

**Consecuencia:** sin esas velas no hay nada que graficar ni sobre qué correr las estrategias. **Todo lo demás depende de resolver esto primero.**

**Cómo se resuelve (Prerrequisito 0 — requiere acción tuya):**
- Abrir a mano el terminal MT5 (regla del proyecto: *attach-only*, ningún script abre terminales).
- Con MT5 attachado, correr el backfill del lake (script existente `copy_rates_range` → `scripts/build_tiers.py`) para el rango **2026-07-07 → 2026-07-11** (incluye warmup previo y el jue-vie completo).
- Verificar que M2/M5/M15 cubran 07-09 y 07-10.
- *(Esto es "descargar datos", no cambia lógica: no viola el "no modificar código".)*

> **Sin el Prerrequisito 0, el resto del plan no puede ejecutarse.** Es lo primero a coordinar.

---

## 1. Qué vamos a mostrar (alcance cerrado contigo)

Ventana: **jueves 2026-07-09 y viernes 2026-07-10**, XAUUSD, **spread real 0,5 (Capitaria/MT5)**. **Sin** validación real-tick (la urgencia es verlas graficadas para analizar cada posición).

| # | Estrategia | Versión | TF | Variante / config | ¿Corrible? |
|---|---|---|---|---|---|
| 1 | **EMASAR original** | SAR 0,3/0,3 (la que usó el trader) | **M2** | `V1` (3 fichas), confirm=acelerando | ✅ Python |
| 2 | **EMASAR mayor PF** | PF 4,56 | M5 | `V1_M5_c2_sar005m05` | ✅ Python |
| 3 | **EMASAR mayor WR** | WR ~39,6% | M15 | `V2_M15_c1` | ✅ Python |
| 4 | **SuperTrend pura** | `p14x3` | M15 | ATR 14, mult 3, always-in | ✅ Python (trivial) |
| 5 | **Sapitos mayor PF** | PF 5,87 ⚠️ (8 trades) | M5 | `o01` | ⚠️ **solo MT5** |
| 6 | **Sapitos mayor net** | +$7.521 | M5 | `W4_070` | ⚠️ **solo MT5** |

> **Nota sobre Sapitos `o01`:** tiene solo 8 operaciones en 5 meses → en 2 días (jue-vie) es muy probable que dé **0 o 1 trade**. Lo mismo aplica en menor grado a las demás: en una ventana de 2 días habrá **pocas posiciones por corrida**. Es esperable; te lo anticipo para que no sorprenda.
> **STAC quedó fuera** de esta tanda (no la mencionaste). Si la quieres dentro, se agrega (modo ac4).

---

## 2. Factibilidad por estrategia (qué se puede generar y cómo)

**EMASAR (corridas 1-3) — ✅ directo en Python.**
`sentinel_engine/strategies/emasar_ref.py::simular(...)` corre la estrategia completa (V1 y V2) sobre las barras del TF que se le pase (M2/M5/M15). Los parámetros exactos de cada variante se toman del registro (`param_set`/`preregistration`). **Bonus:** ese mismo archivo ya tiene programados **Awesome (`ao_series`), Accelerator (`ac_series`) y Momentum (`momentum_series`)** — o sea, los indicadores que faltan en el gráfico **ya existen como función**, solo hay que enchufarlos (sección 5).

**SuperTrend `p14x3` (corrida 4) — ✅ Python, script nuevo trivial.**
`_supertrend_ref.py::supertrend()` da la línea; la lógica "always-in" (dar vuelta con cada flip) son ~15 líneas en un script nuevo de reporte. No toca código existente.

**Sapitos `o01` y `W4_070` (corridas 5-6) — ⚠️ NO hay port en Python (confirmado: 0 coincidencias en `sentinel_engine`).** Dos caminos:
- **(A) Recomendado — correr el EA en el probador de MT5 y exportar.** Ya vas a tener MT5 abierto para el Prerrequisito 0, así que corres `TOKATA_Sapitos_v3.mq5` con los presets de `o01`/`W4_070`, ventana jue-vie, **spread configurado en 50 puntos (=0,5)**, y exportas. Después se ingiere (sección 6). **Máxima fidelidad, cero reimplementación.**
- **(B) Reimplementar Sapitos en Python** (ORB + ADX + Choppiness + salida en 3 fases). Es un archivo nuevo, pero **es harto código y con riesgo de no calzar exacto** con el MQL5. No lo recomiendo salvo que quieras evitar MT5.

> **Decisión abierta #1:** ¿Sapitos por camino A (MT5-export) o B (reimplementar)? Recomiendo **A**.

---

## 3. Cómo se aplica el spread 0,5 (Capitaria)

El simulador de EMASAR **no modela spread** hoy. Para respetarlo sin tocar su código:
- **EMASAR/SuperTrend (Python):** un **envoltorio nuevo** modela bid/ask: compra al *ask* (= precio + 0,5), vende/stop al *bid*. Ideal aplicarlo **en el momento del fill** (no como descuento posterior), porque el spread puede cambiar si un stop se toca o no. *(Si por tiempo se aplica como ajuste posterior al PnL, lo dejo señalado como aproximación — no cambia qué trades gatillan.)*
- **Sapitos (MT5):** se configura directo en el probador (spread fijo 50 puntos), fidelidad nativa.

> **Decisión abierta #2:** spread modelado en el fill (más fiel, algo más de trabajo) vs. ajuste posterior al PnL (rápido, aproximado). Recomiendo **en el fill**.

---

## 4. Los indicadores en el gráfico (el corazón de "verlas con sus indicadores")

Principio que pediste: **AGREGAR, no modificar los existentes.** Estado y plan por indicador:

| Indicador | ¿Está? | Config que necesitamos | Acción |
|---|---|---|---|
| EMA 8 / EMA 20 | ✅ sí | períodos 8 y 20 | usar tal cual |
| Parabolic SAR | ✅ sí (default 0,02/0,20) | **0,3/0,3** (EMASAR orig) y **0,005/0,05** (EMASAR PF) | **AGREGAR** esas 2 instancias parametrizadas |
| SuperTrend | ✅ sí (default 10/3) | **14/3** (corrida 4) y 10/3 (interno EMASAR V1) | **AGREGAR** ST(14,3) |
| **Awesome (AO)** | ❌ no en el gráfico | estándar | **AGREGAR** (math ya en `ao_series`) |
| **Accelerator (AC)** | ❌ no en el gráfico | estándar (+ modo color) | **AGREGAR** (math ya en `ac_series`) |
| **Momentum (14)** | ❌ no en el gráfico | período 14 | **AGREGAR** (math ya en `momentum_series`) |

Todos deben quedar **toggleables** (encender/apagar por estrategia).

> **⚠️ Punto técnico importante (Decisión abierta #3):** AO, AC y Momentum **no van sobre el precio** — son osciladores de otra escala y necesitan un **subpanel** debajo del gráfico. El chart actual **no tiene subpaneles** (la tarea "charts avanzado subpanes" está en backlog). Opciones: (a) agregar soporte de subpanel a la librería de gráficos (la vendorizada quizá ya lo soporta con su API de "panes" — a verificar); (b) un panel chico separado; (c) overlay normalizado sobre el precio (feo, no recomendado). Como el trader **decide con estos osciladores**, verlos en el momento de cada entrada es importante, no opcional. **A resolver en la revisión del plan.**

**Restricción de "no código":** agregar estos overlays/toggles y el subpanel **es código** (en `routers/bars.py` para el cálculo server-side y en `web/lib/chart.js` + la sección para los toggles). Por eso va en la **fase de ejecución, después de que apruebes el plan** — hoy no se toca.

---

## 5. Cómo entran las corridas a Trade View

El camino ya existe (`sentinel_engine/ingest_tokata/`): por cada corrida se genera **fila de ledger + historial de señales + trades**, se ingiere al registro (`research.db`) y queda un `run_id` que Trade View carga y dibuja con sus marcadores de entrada/salida (como ya funciona el run de prueba `mt5import-abc1043ef513`). Las corridas EMASAR/SuperTrend (Python) y Sapitos (MT5-export) siguen el mismo formato de ingesta.

---

## 6. Fases de ejecución (cuando apruebes)

- **Fase 0 — Backfill del lake** (tú + MT5): descargar 07-07→07-11. *Bloqueante.*
- **Fase 1 — Generar las 6 corridas** con spread 0,5: EMASAR×3 y SuperTrend×1 en Python (scripts nuevos); Sapitos×2 vía MT5-export.
- **Fase 2 — Ingesta** al registro (`ingest_tokata`).
- **Fase 3 — Indicadores en el chart** (código acotado): agregar overlays AO/AC/Momentum + instancias SAR/SuperTrend con configs exactas + toggles + (según Decisión #3) subpanel de osciladores.
- **Fase 4 — Verificación** en navegador headless (patrón ORC-5 ya existente): que cada run cargue, marque posiciones y muestre los indicadores encendibles.

---

## 7. Alternativa rápida (puente, si la urgencia no puede esperar a la Fase 3)

Si quieres **ver algo cuanto antes** sin esperar el código del chart: un **reporte HTML autónomo** (archivo nuevo, cero código de la app) por corrida, usando la misma librería de gráficos ya vendorizada, con **los indicadores calculados offline** (la math ya existe) y las posiciones marcadas. Es visualmente equivalente a la vista objetivo y **no depende de las Fases 3-4**. Igual necesita la Fase 0 (los datos). Lo dejo como opción, no como reemplazo del Trade View nativo.

---

## 8. Decisiones abiertas (para la revisión del plan)
1. **Prerrequisito 0:** ¿coordinamos el backfill del lake (abres MT5)? Sin esto no arranca nada.
2. **Sapitos:** camino **A (MT5-export, recomendado)** vs B (reimplementar en Python).
3. **Spread:** modelado **en el fill (recomendado)** vs ajuste posterior aproximado.
4. **Osciladores AO/AC/Momentum:** ¿subpanel nuevo en el chart, panel separado, o (puente) reporte HTML autónomo?
5. **STAC:** ¿dentro (modo ac4) o fuera de esta tanda?
6. **Fechas:** confirmado jue-vie = **2026-07-09 / 2026-07-10** (hoy es lunes 13). ✔
