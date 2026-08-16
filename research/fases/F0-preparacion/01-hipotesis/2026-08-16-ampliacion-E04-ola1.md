# AMPLIACIÓN E-04 DEL PRE-REGISTRO DE LA OLA 1 — grilla densa, unidades y estadística

**Fecha:** 2026-08-16 · **Autor:** controlador (Opus 5) · **Rama:** `equipo1`
**Estado:** 🔴 **ESCRITA Y COMMITEADA ANTES DE CORRER UN SOLO BRAZO.** Ése es todo el punto.
El commit de este fichero precede en el historial a cualquier artefacto de resultados de la
Ola 1; si no fuera así, este documento no valdría nada.

**Amplía (no reemplaza):** `01-hipotesis/2026-08-16-preregistro-ola1.md` (`22ee9fb`).
**Manda por encima:** D-56 (partición 1-A / 1-B), D-57 (piloto pre-congelado), charter §A.3
(«los rankings pueden EXTENDER profundidad; JAMÁS recortar amplitud»), §A.4, §A.9, §A.10.

---

## 0 · Por qué existe esta ampliación

Tres hechos, todos anteriores a ver un solo resultado:

1. **Directiva del user (2026-08-16):** la ola se corre **completa y de una sola pasada por
   script** —«cada una de las variantes, sus grillas, granularidades, distintos parámetros,
   todo»— con trabajo agéntico **cero** mientras corre, y con los resultados debidamente
   registrados en el sistema de investigación antes de que nadie los interprete.
2. **El cómputo es prácticamente gratis, medido:** `build_all()` sobre las tres estrategias y las
   8.334 barras del sustrato pre-holdout tarda **1,55 s** (medición del controlador, 2026-08-16,
   sobre `659a121`). Una grilla de 44 brazos y una de 160 cuestan lo mismo en términos prácticos:
   segundos. **Correr la grilla mínima sería una decisión de coste que no tiene coste que
   justificarla.**
3. **El pre-registro ya obliga a densificar en dos de sus reglas:** «regla de meseta ⇒ refinar
   paso ≤0,25» (P-05, regla global 4) y «si el óptimo aparece en un extremo de la grilla, se
   extiende la grilla en vez de declarar óptimo de borde» (P-08). Aplicar esas reglas **después**
   de ver los resultados obliga a una segunda pasada y, peor, deja la elección del refinamiento
   contaminada por lo ya visto. Declarar la densidad **ahora** las cumple por adelantado y sin
   contaminación.

---

## 1 · La partición que gobierna todo lo que sigue

Cada brazo de la Ola 1 pertenece a **exactamente una** de estas dos clases, fijada aquí:

| Clase | Qué es | Qué puede afirmar |
|---|---|---|
| **CONFIRMATORIO** | Los **44 brazos** del pre-registro `22ee9fb`, sin tocar ni uno. | Veredicto contra la regla de decisión **tal como fue registrada**. |
| **EXPLORATORIO** | Los brazos que esta ampliación añade. | **Describe la superficie de respuesta.** Jamás revierte ni rescata un veredicto confirmatorio. |

**Reglas duras de la partición, fijadas aquí y ahora:**

1. Los 44 confirmatorios son un **subconjunto exacto** de las grillas densas de §3 — se comprueba
   por código, no por confianza (`test_los_44_preregistrados_son_subconjunto_exacto`). Si algún
   brazo pre-registrado no apareciera en la grilla densa, la corrida es inválida.
2. **Un brazo exploratorio no puede producir un veredicto.** Si el mejor brazo de una palanca es
   exploratorio, eso **no** promueve la palanca: se reporta como «el confirmatorio dice X; la
   superficie densa sugiere que el óptimo podría estar en Y, **no verificado**», y Y se propone
   para la etapa siguiente.
3. **Todos los brazos —confirmatorios y exploratorios— entran en el conteo de intentos** para la
   corrección por comparaciones múltiples (charter §A.9, plan §9, regla global 1 del
   pre-registro). Densificar **encarece** el haircut estadístico y se acepta ese precio a
   sabiendas: es el precio de mirar más. Se reportan las dos correcciones, la del conjunto
   confirmatorio solo y la del conjunto total.
4. **Nada de lo exploratorio cambia una regla de decisión.** Las cuatro reglas de decisión del
   pre-registro (IC pareado que excluye 0 + métrica secundaria coherente + meseta; monotonía en
   P-08; meseta y sólo meseta en P-05) se aplican **literalmente como están escritas**.

---

## 2 · Resoluciones de unidad y de método (todas ANTES de correr)

Cinco ambigüedades del pre-registro que hay que cerrar para poder ejecutar. Se cierran por
**medición o por definición explícita**, nunca por conveniencia, y quedan aquí por escrito.

### 2.1 🔴 El umbral de P-03 va en PIPS, y un pip son 0,01 — medido, no supuesto

El pre-registro escribe «umbral `{25, 50, 75}` **pips**». El motor recibe `ac_decel_umbral` en
**unidades del oscilador AC**, que vive en unidades de precio. `pip_size("XAUUSD")` = **0,01**
(verificado en `sentinel_engine/strategies/emasar_ref.py`), luego 25 pips = **0,25**.

**Por qué esto no es un detalle.** Medición del controlador sobre las 8.334 barras del sustrato
(distribución de `|AC[i] − AC[i−1]|`, n=8.296): p50 = **1,287**, p90 = **4,356**, p99 = **12,806**,
máx = **49,63**. De ahí:

| interpretación de «25/50/75» | fracción de barras que superan el umbral |
|---|---|
| unidades AC crudas (25 / 50 / 75) | **0,1 % / 0,0 % / 0,0 %** |
| pips × 0,01 (0,25 / 0,50 / 0,75) | **89,3 % / 78,9 % / 68,9 %** |

Leerlo en crudo haría que **el trigger no se dispare nunca** en los 18 brazos: los tres valores de
umbral serían idénticos entre sí e idénticos a «AC-modulate apagado», y P-03 saldría plana por un
error de unidades disfrazado de resultado. **Se adopta pips × 0,01.** La conversión se hace en el
generador del manifiesto y el manifiesto guarda **las dos** columnas (`umbral_pips` y
`ac_decel_umbral`) para que la traza sea legible sin recalcular nada.

### 2.2 La tercera dimensión de P-03 no existía en el motor; se construye antes de correr

«Duración del apriete `{3,5,10}` barras» no tenía parámetro: el apriete duraba exactamente la
barra del disparo. Se añade `ac_modulate_hold_bars` (**WP-2b**, aditivo, default `1` =
comportamiento de hoy byte-idéntico, bajo la puerta de paridad). Sin él, 12 de los 44 brazos
pre-registrados serían duplicados exactos de otros 6.

### 2.3 Definición de R (fijada aquí; el charter §A.1 la exige y el repo no la tenía)

**R_i = |precio_de_entrada_rellenado_i − SL_inicial_i| × 100 oz × 936,50 CLP/USD**, en CLP por
**1,0 lote**. Es riesgo **por posición**, no una escala global.

- **Escalera (S6/S7):** `SL_inicial` = el stop genuino de barra de entrada, vía
  `backtest._sl_inicial_genuine(side_l, idx, bars, k_init, entry_bid, wait_mae_atr_k, atr14)` —
  **el mismo helper que usa `run_ladder`**, no una reimplementación.
- **SuperTrend:** `SL_inicial` = la línea SuperTrend de la barra de entrada, recalculada con el
  `atr_period`/`mult` **del propio brazo** y desplazada por su `sl_offset` (LONG `línea − offset`,
  SHORT `línea + offset`), con los mismos helpers (`_atr_wilder`, `supertrend`) que
  `run_supertrend`.
- Si `R_i` no es computable o sale ≤ 0: la posición **no** entra en las cifras en R y **se cuenta
  y se publica** el número de exclusiones. Nunca se rellena con un valor por defecto.
- En las diferencias pareadas, el denominador es el **R del brazo de control**: la entrada es
  compartida, luego el riesgo de entrada es una propiedad de la entrada, no de la política de
  salida. Usar el R de cada brazo mezclaría numerador y denominador.

### 2.4 Bootstrap por bloques: el bloque es el DÍA de servidor

- **Bloque = día natural del reloj del servidor** (UTC−4) del instante de entrada rellenado
  (`t_in_exec`, vía `datetime.utcfromtimestamp`). Captura la dependencia intradía, que es la que
  invalida el bootstrap i.i.d.
- **B = 10.000** remuestreos, **semilla fija `20260816`** (reproducible bit a bit).
- Se remuestrean **días con reemplazo** (tantos días como días observados) y se recalcula la
  **media de la diferencia pareada** sobre el pool remuestreado.
- **IC percentil 2,5 / 97,5.** `ic_excluye_0` es booleano y es lo que la regla de decisión mira.
- `p_bootstrap` = `2 × min(fracción ≤ 0, fracción ≥ 0)`, recortado a [0, 1].
- **Corrección por comparaciones múltiples:** Benjamini–Hochberg (FDR) al 5 %, calculada **dos
  veces y publicadas ambas**: (a) sobre los brazos confirmatorios no-control; (b) sobre **todos**
  los brazos no-control de la ola. La (a) es la que gobierna el veredicto pre-registrado; la (b)
  es la honesta sobre todo lo mirado.

### 2.5 Overlay de coste de deslizamiento (SECUNDARIO y declarado, no toca la métrica primaria)

El simulador no modela deslizamiento en los stops. T0.7-M-H lo calibró contra la realidad de la
902 (D-54): **0,225 USD** a spread 0,50. Cada brazo publica, **además** de su neto primario, un
`net_con_coste`, que penaliza en 0,225 USD en contra a toda posición cerrada por nivel
(`EXIT_INITSL`, `EXIT_SL_RAISED`, `EXIT_TRAIL`, `EXIT_STLINE`) — 21.071,25 CLP por posición y por
lote — y **no toca** salidas a cierre de barra ni `EXIT_TP`.

**La métrica primaria de todas las reglas de decisión sigue siendo el neto SIN overlay**, tal
como se pre-registró. El overlay existe porque P-08 es literalmente una palanca sobre el
deslizamiento de los stops, y medir esa palanca en un mundo con deslizamiento cero es medirla en
el único mundo donde no puede ganar. Se publican las dos columnas, siempre, lado a lado.

---

## 3 · Las grillas densas, exhaustivas y fijadas aquí

Notación: **negrita** = brazo confirmatorio (pre-registrado en `22ee9fb`); el resto es
exploratorio. `default` = configuración VIVA sin tocar, y es el brazo de control de su palanca.

### P-02 · Time-stop por edad de la señal — S6-K2P0 **y** S7-TPNONE · Ola 1-A

`max_hold_bars` ∈ { **off (default)**, 4, 6, 8, **10**, 12, **15**, **20**, 25, **30**, 40,
**48**, 56, **64**, 80, 96, 128 }

**17 brazos × 2 estrategias = 34** (de los cuales **7 × 2 = 14 confirmatorios**).

Justificación de la densidad: la métrica que el catálogo pide es la **curva
expectancy-vs-barras**, y una curva de cuatro puntos no es una curva. Los extremos (4 y 128)
existen para acotar los dos límites: 4 barras es casi «salir enseguida», 128 barras (32 h) es
holgadamente más que la vida típica de una posición y debe ser indistinguible de `off` — **si 128
NO fuera indistinguible de `off`, el instrumento estaría mal y el resto de la palanca no sería
interpretable.** Es un control de sanidad, no un brazo con hipótesis.

### P-03 · Trigger de desaceleración de AC — S6-K2P0 · Ola 1-A

Producto completo de tres factores:
- `umbral_pips` ∈ { 10, **25**, **50**, **75**, 100, 150 } → `ac_decel_umbral` = pips × 0,01
- `ac_decel_lookback` ∈ { **1**, **2**, 3 }
- `ac_modulate_hold_bars` ∈ { 1, **3**, **5**, **10**, 20 }

**6 × 3 × 5 = 90 brazos** (de los cuales **18 confirmatorios**), más:
- `default` — el S6 vivo (control).
- 🆕 **`ac_off`** — `{ac_modulate: False}`. Control **exploratorio explícito**: es el límite de
  umbral → ∞ y responde una pregunta que el pre-registro no hace y que hay que poder responder:
  **¿el mecanismo AC-modulate aporta algo, en cualquier ajuste?** Sin este brazo, P-03 sólo puede
  decir cuál ajuste es mejor, nunca si el mecanismo entero vale la pena.
- 🆕 **`factor` ∈ {0,10, 0,50, 0,75}** con el resto en default (3 brazos). El catálogo trae
  `AC-modulate {off, 0.25, 0.5}` en la familia B★ como el **factor** del apriete; el pre-registro
  de P-03 barre el **trigger** y deja el factor fijo en el 0,25 vivo. Tres brazos cubren el tercer
  mando del mismo mecanismo sin abrir un producto cartesiano.

**Total P-03: 95 brazos.**

### P-05 · Multiplicador ATR de SuperTrend · 🔴 Ola 1-B (NO pareada)

`mult` ∈ { 1,5 · 1,75 · **2,0** · 2,25 · **2,5** · 2,75 · **3,0 (default)** · 3,25 · **3,5** ·
3,75 · **4,0** · 4,25 · **4,5** · 4,75 · **5,0** · 5,5 · 6,0 }

**17 brazos** (de los cuales **7 confirmatorios**). `atr_period` fijo en **14** (el pre-registro
lo congela por el conflicto declarado con P-07, Ola 2). `sl_offset` fijo en 0,0.

Justificación de la densidad: la regla de decisión de P-05 es **«sólo por meseta, nunca por pico
aislado»**, y la regla global 4 manda «meseta ⇒ refinar paso ≤0,25». **Paso 0,25 en todo el rango
2,0–5,0 cumple esa regla por adelantado**, sin segunda pasada y sin que la elección del
refinamiento dependa de lo ya visto. Los extremos 1,5 y 6,0 (paso 0,5) sirven para ver la forma
completa de la curva, no para ganar.

### P-08 · Offset de SL consciente del fill — SuperTrend · Ola 1-A (sujeta a verificación)

`sl_offset` (USD) ∈ { **0,00 (default)**, 0,05, **0,10**, 0,15, **0,20**, 0,25, **0,30**, 0,40,
0,50, 0,75, 1,00 }

**11 brazos** (de los cuales **4 confirmatorios**). `mult`=3,0 y `atr_period`=14 fijos.

Justificación de la densidad: la regla de decisión de P-08 exige **monotonía** y prohíbe declarar
un óptimo de borde sin extender la grilla. La grilla pre-registrada llega hasta 0,30, que está
apenas por encima del deslizamiento medido (≈0,20): si el óptimo cayera en 0,30, la propia regla
obligaría a extender. **Extenderla ahora hasta 1,00 elimina esa segunda pasada** y además cubre el
paso fino (0,05) alrededor del valor calibrado.

🔴 **Advertencia mecánica declarada por adelantado, no descubierta después:** P-08 está clasificada
1-A, pero SuperTrend es *always-in* — al cambiar el nivel del stop cambia **en qué barra** sale la
posición, y la siguiente entra en la barra de salida de la anterior. Es decir, **el emparejamiento
de P-08 puede romperse por construcción**. Por eso D-56 fijó la regla dura: **tasa de
emparejamiento < 0,90 ⇒ la palanca se degrada automáticamente a 1-B** y su resultado pasa a
descriptivo. Aquí se anticipa que P-08 es la candidata más probable a esa degradación. Se medirá;
no se presupone en ninguna dirección.

### Recuento total de la ola

| Palanca | Estrategia | Clase | Confirmatorios | Total brazos |
|---|---|---|---:|---:|
| P-02 | S6-K2P0 | 1-A | 7 | 17 |
| P-02 | S7-TPNONE | 1-A | 7 | 17 |
| P-03 | S6-K2P0 | 1-A | 19 | 95 |
| P-05 | SuperTrend | **1-B** | 7 | 17 |
| P-08 | SuperTrend | 1-A (a verificar) | 4 | 11 |
| **TOTAL** | | | **44** | **157** |

Los 44 confirmatorios coinciden exactamente con el recuento del pre-registro
(`7×2 + 19 + 4 + 7 = 44`), y se verifica por código que son subconjunto de los 157.

---

## 4 · Métricas secundarias: definiciones operativas cerradas ANTES de correr

El pre-registro exige métricas secundarias pero no las define de forma ejecutable. Se cierran
aquí. Ninguna se ajusta después.

**P-02 — ¿buena poda o upside amputado?** Sobre el subconjunto casado con el control, mirando sólo
las posiciones que el brazo cerró con `reason == "time_stop"`:
- `podadas_perdedoras` = el control terminó en pérdida **y** el brazo sacó más (n y suma de Δ).
- `amputadas_ganadoras` = el control terminó en ganancia **y** el brazo sacó menos (n y suma de Δ).
- Se publican los dos lados, siempre. La regla de decisión pide que la secundaria **no contradiga
  el signo** de la primaria.

**P-03 — coste de whipsaw.** Un **re-flip** es un par de posiciones consecutivas en el tiempo donde
la segunda abre en **sentido contrario** a la primera dentro de **3 barras M15 (2.700 s)** desde el
cierre de la primera. Es **falso** si esa segunda posición termina en pérdida.
`pct_reflip_falso` = falsos / total de re-flips; se publican numerador y denominador, no sólo el
porcentaje. Fijado en 3 barras aquí, antes de ver nada.

**P-08 — los dos lados, obligatorio.** Sobre el subconjunto casado, descomposición **exhaustiva y
que debe sumar exactamente** la diferencia total (se comprueba con un assert):
- `salvadas`: el control salió por `EXIT_STLINE` y el brazo **no** (el stop más ancho no se tocó).
- `mismo_stop_peor_fill`: ambos salieron por `EXIT_STLINE` (el stop más ancho sí se tocó, y más
  lejos).
- `otros`: el resto.

**P-05 — las tres del catálogo, dentro de SuperTrend.** `sharpe`, **nº de flips** y **máxima racha
de pérdidas consecutivas**, más neto por lote y en R. Sharpe se publica en dos formas declaradas,
porque no hay una sola honesta: `sharpe_por_posicion` = media/desvío de `net1` (ddof=1), y
`sharpe_diario_ann` = media/desvío del neto agregado por día de servidor × √252. Ninguna es
anualizada a partir de la otra.

---

## 5 · Lo que esta ampliación NO cambia (y por qué importa decirlo)

- **No cambia ninguna hipótesis, ninguna nula, ninguna regla de decisión.** Las cuatro reglas del
  pre-registro se aplican literalmente.
- **No añade palancas.** P-27 sigue diferida (necesita detección de swings con su propio contrato
  antitrampa) y P-33 sigue sin correr (D-56). Densificar lo pre-registrado no es lo mismo que
  ampliar el alcance, y aquí sólo se hace lo primero.
- **No toca el sustrato.** Mismo corte `2026-01-01 20:00` → `2026-05-11 23:45`, 8.334 barras,
  holdout de D-31 **excluido** y verificado por guarda dura en cada corrida: si alguna posición
  resuelta tocara el sello, la corrida **aborta y no escribe nada** (charter §A.14).
- **No cambia el estado del resultado.** Todo sigue siendo `estado=piloto-instrumento` mientras el
  user no firme el congelado del motor (D-57), y así se etiqueta en el LEDGER desde la primera
  fila.

---

## 6 · Régimen de interpretación (directiva del user, 2026-08-16)

1. Todo artefacto de datos de la Ola 1 nace y se queda **PRE-INTERPRETACIÓN**, marcado como tal en
   el propio fichero (`_ESTADO.md` y cabecera de `_consolidado.md`). Charter §A.4: los artefactos
   de datos **no llevan conclusiones**, y aquí ni siquiera llevan lectura.
2. **Ninguna interpretación es válida hasta haber sido discutida en profundidad con el humano y
   aprobada.** Lo que el controlador escriba antes de esa conversación es **propuesta de lectura**,
   y va rotulado así, en fichero aparte de los datos.
3. Negativos, neutros y positivos se registran **con el mismo detalle**. Un negativo bien medido es
   un resultado (charter §A.2), y la ola publica los 157 brazos, no el mejor.
4. **Componibilidad:** al cerrar la ola se registra explícitamente qué hallazgos son componibles
   entre sí y cuáles no, con el mecanismo por el que lo son o no lo son. No se presupone
   aditividad entre palancas en ningún caso.
5. **Ninguna mejora se descarta por improbable.** Toda mejora vista, por remota que sea, se
   consigna y se propone para segunda etapa o para prueba en demo. El coste de probar en demo es
   ~0 y el coste de no registrar una pista es que se pierde.
