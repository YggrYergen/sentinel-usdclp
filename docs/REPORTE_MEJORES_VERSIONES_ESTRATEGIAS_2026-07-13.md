# Reporte de mejores versiones por estrategia (multi-eje)
### Archivo 1 de 2 · Fecha 2026-07-13

> **Qué es esto:** para cada estrategia, la "mejor versión" **no es una sola** — depende de qué mides. Aquí están las **top-2 por cada eje** (más ganancia, más rentable por riesgo, menos caída, etc.), y al final **mi elección del mejor "todo-terreno"** con potencial real, argumentada.
> **Archivo 2** (aparte): cómo meter estas corridas del jueves-viernes pasado en "Trade View" con los indicadores correctos. Este archivo va primero; lo discutimos y después vemos el 2.

---

## Cómo leer los números (léelo, es importante)

- **Fuente:** ledgers maestros de backtests de TOKATA (`mt5_ledger.csv` + staging `st0`/`st1val`/`stac1`/`sarprobe`), deduplicados por variante. Ventana enero–mayo 2026, XAUUSD (oro), 0,10 lote.
- **Los ejes ("aristas") de 'mejor':**
  1. **Net** = ganancia neta total en dólares.
  2. **Factor de ganancia (PF)** = cuánto ganas por cada dólar que pierdes. >1 gana; 2 = ganas el doble de lo que pierdes.
  3. **Drawdown (DD)** = la peor caída de racha (cuánto sufre la cuenta antes de recuperarse). **Menos es mejor.** Solo lo miro entre las que ganan.
  4. **Win rate (WR)** = % de operaciones ganadoras.
  5. **Payoff** = tamaño de la ganancia media ÷ pérdida media (las de tendencia ganan pocas pero grandes → payoff alto, WR bajo).
  6. **Robustez** (agregado por mí): ¿está rodeada de vecinas ganadoras (meseta, no pico de suerte) y **sobrevive a ticks reales**?
  7. **Ejecutabilidad real** (agregado por mí): ¿respeta el stop mínimo del bróker? ¿está validada con ticks reales o es solo "screening" (simulación rápida y optimista)?
- **Dos advertencias que aplican a todo:**
  - **"screening-m1" ≠ "real-tick".** El screening usa velas de 1 min como proxy y suele ser **optimista**. `registro-realtick` es la validación seria. Lo marco en cada tabla.
  - **El DD en dólares no es comparable entre familias distintas** (cada una mueve rangos distintos). Sí es comparable *dentro* de una misma estrategia.

---

# TRADER 1 — el linaje "SuperTrend"

Tu estrategia arrancó de **dos puntos de partida**, y conviene verlos así:

- **Punto de partida A — SuperTrend "pura" (always-in):** la idea original, "seguir la tendencia y darse vuelta con cada cambio, sin stop ni objetivo".
- **Punto de partida B — STAC:** lo que se propuso en la investigación inmediata — *"el SuperTrend a 2 min debe recomendar compra; recién ahí compro si el Accelerator pasa de negativo a positivo y el SAR de 2 min cruza bajo el precio"*.

Ambos puntos de partida, **en su forma original, no ganaban**: la SuperTrend pura pierde en velas cortas (1/5 min) por el serrucho; STAC en su versión literal (Accelerator por cruce de cero) dio **0 de 20** positivas. La ganancia apareció al **refinarlos**. Veamos cada uno.

## 1A. SuperTrend "pura" — mejores versiones

*Recordatorio simple: una línea sigue al precio; cuando el precio la cruza, se da vuelta. Nunca sale del mercado, no usa stop. Gana en tendencias largas, sufre en mercado lateral.*

| Eje | Variante ganadora | Net | PF | WR | DD | Trades | Validación |
|---|---|---|---|---|---|---|---|
| **Más net** | `p14x3` M15 | **+$17.512** | 1,49 | 40,3% | 4.357 | 206 | **real-tick ✓** |
| 2º net | `p7x3` M15 | +$14.768 | 1,41 | 42,2% | 4.377 | 206 | real-tick ✓ |
| **Más PF** | `p14x3` M15 | +$17.512 | **1,49** | 40,3% | 4.357 | 206 | real-tick ✓ |
| 2º PF | `p7x3` M15 | +$14.768 | 1,41 | 42,2% | 4.377 | 206 | real-tick ✓ |
| **Menos DD** (entre rentables) | `p14x3` M15 | +$17.512 | 1,49 | 40,3% | **4.357** | 206 | real-tick ✓ |
| **Más WR** | `p7x3` M15 | +$14.768 | 1,41 | **42,2%** | 4.377 | 206 | real-tick ✓ |

> **Lo notable:** las tres mejores (`p14x3`, `p7x3`, `p10x3`, todas M15 con multiplicador 3) **ganan todos los ejes a la vez** y están pegadas → es una **meseta**, no un pico de suerte. Y los números en screening y en real-tick son **casi idénticos** (17.512 vs 17.510) → la ventaja **no es un espejismo del simulador**. De todo el inventario, esto es lo más creíble.
> **La cara B:** gana <41% de las veces (aguanta psicológicamente muchas rachas perdedoras), el DD es grande ($4.357), y **aún no se validó "fuera de muestra"** (datos que nunca vio).
>
> **Mejor todo-terreno de SuperTrend:** **`p14x3` en M15** — sin discusión, domina todos los ejes.

## 1B. STAC — mejores versiones (me corrijo respecto a lo que dije antes)

*Recordatorio simple: SuperTrend + dos "guardaespaldas" (Accelerator y SAR), solo compra.*

Cargando las **114 variantes completas**, resulta que **sí hay 11 rentables**, y **todas usan el modo `ac4` ("rojo→verde" del Accelerator)** — exactamente la reformulación que el trader pidió tras el fracaso de la versión literal. O sea: el "empezó a dar ganancia" **está respaldado por los datos** (antes vi un subconjunto incompleto y te dije que no — corregido).

| Eje | Variante ganadora | Net | PF | WR | DD | Trades | Validación |
|---|---|---|---|---|---|---|---|
| **Más net** | `SARFLIP_s005m20_ac4` | **+$2.369** | 1,36 | 41,9% | 2.385 | 105 | screening ⚠️ |
| 2º net | `SARFLIP_s005m20_ac1` | +$2.473 | 1,07 | 40,7% | 4.451 | 482 | screening ⚠️ (PF flojo) |
| **Más PF** | `SARFLIP_s005m20_ac4` | +$2.369 | **1,36** | 41,9% | 2.385 | 105 | screening ⚠️ |
| 2º PF | `SARFLIP_s04m20_ac4` | +$1.126 | 1,21 | 38,3% | 1.007 | 222 | screening ⚠️ |
| **Menos DD** | `SARFLIP_s01m20_ac4` | +$1.062 | 1,20 | 46,4% | **838** | 110 | screening ⚠️ |
| **Más WR** | `ATRBRK_s01m20_sl20tp15_ac4` | +$791 | 1,14 | **50,0%** | 1.049 | 106 | screening ⚠️ |

> **Lectura honesta:** STAC "revivió" con el modo color (ac4), pero es **ganancia modesta** (PF 1,1–1,4, no 2+), **todas en screening** (ninguna validada con ticks reales todavía) y solo 11 de 114 ganan → frágil. **Mejor todo-terreno de STAC:** **`SARFLIP_s005m20_ac4`** (mejor net y PF juntos). Pero con asterisco grande: **validar con ticks reales antes de creerle.**

**Veredicto del linaje trader 1:** la **SuperTrend `p14x3` M15** es muchísimo más sólida que cualquier STAC. Si hubiera que mostrar "la mejor de tu estrategia", es esa.

---

# TRADER 2 — EMASAR

*Recordatorio simple: entrar a favor de la tendencia tras un pequeño retroceso, cuando coinciden varias señales (medias + SAR + 2 de 3 osciladores de fuerza).*

| Eje | Variante ganadora | Net | PF | WR | DD | Trades | Validación |
|---|---|---|---|---|---|---|---|
| **Más net** | `V2_M15_c2` (1 ficha, sin stop duro) | **+$4.205** | 1,08 | 37,7% | **8.320** 🔴 | 496 | screening ⚠️ |
| 2º net | `V1_M5_c2_sar005m05` | +$3.277 | 4,56 | 21,3% | 371 | 75 | screening ⚠️ |
| **Más PF** | `V1_M5_c2_sar005m05` | +$3.277 | **4,56** | 21,3% | 371 | 75 | screening ⚠️ |
| 2º PF | `V1_M5_c2_sar01m1` | +$1.804 | 3,54 | 16,7% | 382 | 54 | screening ⚠️ |
| **Menos DD** | `V1_M5_c2` (SAR 0,02/0,20) | +$908 | 2,24 | 15,8% | **301** | 57 | screening ⚠️ |
| **Más WR** | `V2_M15_c1` | +$2.995 | 1,06 | **39,6%** | 4.071 | 502 | screening ⚠️ |
| *(referencia)* **Original "de verdad"** | `V1_M5_c2_sar3m3` | +$1.625 | 2,82 | 17,4% | 341 | 69 | screening ⚠️ |

> **Ojo con "más net":** el líder por net (`V2_M15_c2`, +$4.205) tiene un **DD de $8.320** — es una V2 "sin stop duro" que gana en bruto pero puede fundir la cuenta. **Más net NO es mejor estrategia** (justo lo que anticipaste).
> **La joya:** `V1_M5_c2_sar005m05` — **PF 4,56 con DD de solo $371** y net $3.277. Es la mejor combinación riesgo/retorno de TODO el inventario… en screening.
> 🔴 **Advertencia de ejecutabilidad (crítica para EMASAR):** el stop inicial original de la familia (3 pips) **está por debajo del mínimo del bróker (0,50)** → en real esas órdenes **se rechazan**. Cualquier versión operable necesita stops ≥50 pips, lo que puede cambiar estos números. **A validar antes de operar.**
>
> **Mejor todo-terreno de EMASAR:** **`V1_M5_c2_sar005m05`** (PF 4,56 / DD $371) como candidata estrella, con la **original `sar3m3`** (PF 2,82 / DD $341) como la versión "más probada y equilibrada". Ambas en M5.

---

# LAS DEMÁS (agrupadas por parecido)

## 3. Sapitos (ruptura de apertura de Londres) — la mejor en backtest

| Eje | Variante | Net | PF | WR | DD | Trades | Validación |
|---|---|---|---|---|---|---|---|
| **Más net** | `W4_070` | **+$7.521** | 2,74 | 42,5% | 1.722 | 40 | **real-tick ✓** |
| 2º net | `W5_013` | +$7.038 | 2,50 | 41,5% | 1.368 | 41 | screening ⚠️ |
| **Más PF** | `o01` | +$1.893 | **5,87** | 62,5% | 312 | **8** 🔴 | screening ⚠️ |
| 2º PF | `W4_019` | +$2.179 | 3,44 | 44,4% | 418 | 18 | screening ⚠️ |
| **Menos DD** | `W5_012` | +$1.759 | 2,50 | 41,5% | **342** | 41 | screening ⚠️ |
| **Mejor riesgo-ajustado** | `W5_005` | +$3.721 | 2,74 | 43,6% | 684 | 39 | **real-tick ✓** |

> **Trampa:** el líder por PF (`o01`, PF 5,87) tiene **solo 8 operaciones** → sobreajuste, no confiable. **Mejor todo-terreno de Sapitos:** **`W5_005`** (+$3.721, PF 2,74, DD $684, validada real-tick) — el mejor equilibrio.
> 🔴 **PERO — la alerta que atraviesa todo:** las variantes de Sapitos que corren **en vivo (demo, forward walk)** van **en rojo** (−2,97M CLP, muy pocas operaciones, sin aciertos aún). Es decir: **la reina del backtest está fallando en vivo.** Puede ser muestra minúscula o error de despliegue, pero **hasta aclararlo, desconfío de sus números de backtest para el mundo real.**

## 4. SapTrail (Sapitos con salida por arrastre)
Una sola prueba: +$3.028, PF 1,83, DD $861. Prometedora pero **sin explorar** — no hay "top-2", no hay barrido. No se puede rankear.

## 5. Pedro (reversión a la media) — descartada
Su única versión: en simulador rápido se veía espectacular (+$2.462, PF 2,33, WR 75,6%); con **ticks reales colapsa a −$173** (PF 0,92), etiquetada **"NO-VIABLE / espejismo intrabar"**. **No tiene "mejor versión" operable.**

---

# 🏆 Mi elección: mejor todo-terreno con potencial real (argumentada)

Si tuviera que apostar por **una** para llevar al mundo real, en este orden:

### 🥇 1º — SuperTrend `p14x3` en M15 (trader 1)
**Por qué gana en potencial real, no solo en un número:**
- **Es una meseta, no un pico de suerte:** `p14x3`, `p7x3` y `p10x3` ganan **todas** → la ventaja es estructural, no una variante afortunada entre cientos.
- **Sobrevive a ticks reales:** screening y real-tick dan **lo mismo** ($17.512 vs $17.510). No es un artefacto del simulador (que es justo lo que mató a Pedro).
- **No tiene el problema del stop mínimo:** al no usar stop-loss, **no hay órdenes que el bróker rechace** ni "caza de stops". Un dolor de cabeza menos que EMASAR.
- **Muestra grande (206 operaciones):** estadísticamente creíble, no 8 trades.
- **Simplísima de operar y monitorear.**
- **Lo que debes aceptar:** gana <41% de las veces y el DD es de $4.357 → requiere **disciplina para aguantar rachas**. Y falta la prueba final: validación **fuera de muestra**.

### 🥈 2º — EMASAR `V1_M5_c2_sar005m05` (trader 2) — la de mayor techo, pero con condiciones
PF **4,56** y DD de solo **$371** es el mejor perfil riesgo/retorno del inventario. Si valida, **supera a SuperTrend**. Pero antes hay que resolver **dos cosas sí o sí**: (1) confirmarla con **ticks reales** (hoy es solo screening) y (2) rehacerla con **stops legales (≥50 pips)** porque el stop original es rechazado por el bróker. Hasta entonces, es "promesa con asterisco".

### ⚠️ Mención aparte — Sapitos
En backtest sería la número 1 fácil (`W5_005`, PF 2,74 real-tick). **La dejo fuera del podio a propósito** porque **está fallando en vivo ahora mismo** y esa divergencia backtest-vs-real es exactamente el riesgo que más pesa en el mundo real. Merece que resolvamos *por qué* antes de confiar en ella.

**Resumen de una línea:** *hoy, la apuesta más honesta al mundo real es **SuperTrend M15 p14x3** (sólida y validada en su tipo); **EMASAR sar005m05** es la de mayor techo si pasa dos validaciones; y **Sapitos** hay que arreglarla en vivo antes de creerle al backtest.*

---

## Cabos sueltos / a discutir
1. **"Mejor" y ejecutabilidad:** casi todas las campeonas son **screening**, no real-tick. ¿Priorizamos validar con ticks reales las 2-3 finalistas antes de mostrarlas como "la mejor versión"?
2. **STAC ac4:** ganancia modesta y no validada — ¿la incluimos como "mejor versión del trader 1" junto a SuperTrend, o la mostramos solo como "intento que revivió pero aún flojo"?
3. **EMASAR y el stop mínimo:** ¿rehago las tablas con stops legales antes del Archivo 2? Cambiaría los números.
4. **Sapitos en vivo:** ¿investigamos la divergencia (muestra chica vs. error de despliegue) como tarea aparte?
