# Reporte integral — Olas 1, 1B y 2

**Fecha:** 2026-08-16 · **Autor:** controlador (Opus) · **Estado:** PROPUESTA DE LECTURA.

🔴 Ninguna interpretación es válida hasta discutirse con el humano y ser aprobada por él (directiva
del user, 2026-08-16). Estado del resultado: **piloto-instrumento** (D-57) — el congelado del motor
no está firmado.

**Unidad:** `net_lote1` está en **CLP por lote 1,0**, USDCLP = 936,50, confirmado en
`backtest.py:520`. En este documento el neto se da en USD (÷936,5) y la diferencia pareada en
USD por posición.

**Regla de lectura que gobierna todo el documento:** el simulador diverge **3,28 %** del neto real
(D-54), con **signo opuesto por estrategia**. Sobrevive la **diferencia pareada contra el control**;
no sobrevive el nivel absoluto ni ninguna comparación S6-contra-SuperTrend.

**Fuentes:** `04-resultados/OLA1/_consolidado.md` (`48fe8d5`) · `OLA1B/_consolidado.md` (`69bad91`) ·
`OLA2/_consolidado.md` (commit de resultados de OLA2).

---

# PARTE I — Validez del instrumento por familia

Antes de cualquier número: **no todas las palancas se midieron con un instrumento capaz de verlas.**
Esto es lo primero que hay que saber para no leer ceros como resultados.

| familia | palancas | diseño usado | ¿el instrumento puede ver el efecto? |
|---|---|---|---|
| Salidas / distancia de stop | P-02, P-03, P-05, P-08, P-34 | pareado por entrada | **Sí** salvo P-05 |
| Multiplicador de SuperTrend | P-05 | pareado | **No** — cambia las entradas; emparejamiento 0,02–0,49 |
| Filtros de entrada | P-09, P-19, P-20, P-21, P-28 | pareado por entrada | **NO — estructuralmente imposible** |
| Tamaño de posición | P-13, P-15, P-16, P-17, P-18 | pareado por posición | **Sí**, emparejamiento 1,00 |

**Por qué el pareado no puede medir un filtro de entrada.** Un filtro solo **quita** operaciones; no
altera cómo se comporta ninguna de las que sobreviven. El estadístico pareado empareja por identidad
de entrada y compara las que existen en ambos brazos — exactamente aquellas que el filtro no tocó.
La diferencia sale **0,00 exacto con p = 1,00 por construcción**, aunque el `n` y el neto difieran de
forma masiva. Los 30 brazos de P-09/P-19/P-20/P-21/P-28 están en esa situación.

El catálogo ya marcaba esas palancas como **no compatibles con el diseño pareado**; se despacharon
por la tubería pareada igual. Es un error de controlador y así queda registrado. **Los datos crudos
sirven; hay que re-analizarlos sin emparejar, no volver a correrlos.**

---

# PARTE II — Detalle por palanca

## II.1 · P-08 — Offset de SL para SuperTrend · **EL RESULTADO MÁS FUERTE DEL PROGRAMA**

**Qué prueba.** Añadir un colchón fijo a la línea de SuperTrend antes de disparar el stop, para
compensar el deslizamiento del bróker. Origen: literatura Área 1, regla H.
**Validez:** pareado real, emparejamiento **0,84–0,98**, n 129–150.

| offset | n | neto USD | diferencia USD/pos | IC 95 % (CLP) | p | BH |
|---|---|---|---|---|---|---|
| control (0) | 153 | 65.590 | — | — | — | — |
| 0,05 | 150 | 66.113 | **−3,30** | −4.615 · −1.748 | 0,00 | total |
| 0,10 | 149 | 65.796 | **−7,84** | −9.470 · −5.397 | 0,00 | **conf + total** |
| 0,15 | 149 | 65.268 | **−11,39** | −13.105 · −8.407 | 0,00 | total |
| 0,20 | 148 | 64.893 | **−16,07** | −18.397 · −11.971 | 0,00 | **conf + total** |
| 0,25 | 145 | 65.056 | −2,46 | −23.819 · 40.770 | 0,65 | no |
| 0,30 | 144 | 60.099 | −5,67 | −26.814 · 38.148 | 0,53 | no |
| 0,40 | 141 | 53.362 | −3,13 | −34.956 · 48.551 | 0,79 | no |
| 0,50 | 137 | 54.403 | −13,96 | −46.031 · 40.165 | 0,50 | no |
| 0,75 | 133 | 52.191 | −40,95 | −71.966 · 15.427 | 0,13 | no |
| 1,00 | 129 | 50.706 | −24,23 | −92.587 · 74.133 | 0,55 | no |

**Lo que hace único a este resultado:** cuatro puntos independientes, los cuatro negativos, con
intervalos que **no tocan el cero**, y un coste **casi exactamente proporcional a la dosis** —
−66,0 · −78,5 · −75,9 · −80,3 USD por unidad de offset. Una relación dosis-respuesta tan estable en
cuatro puntos no es casualidad. **Es el único hallazgo de las tres olas que pasa corrección por
multiplicidad.**

**Matiz técnico que conviene ver, porque enseña a leer estas tablas:** con offset 0,10 el **neto
absoluto sube** (65.796 contra 65.590) mientras la **diferencia pareada baja** (−7,84). No es
contradicción: el brazo tiene 149 posiciones y el control 153, así que el neto agregado mezcla el
efecto por posición con un conteo distinto. **La diferencia pareada es la cifra correcta**; el neto
absoluto es engañoso aquí y este es el ejemplo perfecto de por qué.

A partir de 0,25 el efecto se disuelve: los intervalos cruzan el cero y las p suben a 0,5–0,8.
Coherente — con offsets grandes el emparejamiento cae y el offset deja de ser solo un retraso de
salida para empezar a cambiar qué posiciones existen.

**Veredicto: HIPÓTESIS REFUTADA con evidencia fuerte.** Ensanchar el stop no salva nada; cuesta, y
cuesta en proporción directa. La propia literatura ya la llamaba parche y recomendaba arreglar la
entrada. El parche está medido y es negativo.

## II.2 · P-34 — Suelo del trailing de S6 (`trail_atr_floor_k`) · **PALANCA NUEVA**

**Qué prueba.** El parámetro que gobierna la distancia del trailing de S6 el **100 % del tiempo**, y
que nunca se había probado. Su valor vivo, 2,0 × ATR, fuerza una distancia nunca menor a 8,67.
**Validez:** pareado, emparejamiento 0,97–1,00.

| suelo | n | neto USD | diferencia USD/pos | p |
|---|---|---|---|---|
| 0,00 | 1074 | −77.685 | −201,92 | 0,34 |
| 0,25 | 1020 | −83.487 | −221,38 | 0,29 |
| 0,50 | 999 | −96.937 | −179,17 | 0,37 |
| 0,75 | 936 | −112.414 | −203,90 | 0,26 |
| **1,00** | 876 | **−159.390** | **−258,80** | 0,11 |
| 1,25 | 783 | −57.180 | −160,03 | 0,34 |
| 1,50 | 708 | −16.788 | −59,18 | 0,72 |
| 1,75 | 678 | 17.139 | −39,43 | 0,81 |
| **2,00 (vivo)** | 624 | **42.976** | control | — |

**Los ocho brazos negativos**, y la mejora es monótona conforme el suelo se acerca al valor vivo.
Nótese también que el `n` crece de 624 a 1074 al eliminar el suelo: un trailing más apretado cierra
antes y libera a la estrategia para reentrar más veces — y esas reentradas adicionales pierden.

**Veredicto:** apretar el trailing de S6 destruye dinero. **El 2,0 vivo es el mejor valor probado.**
⚠️ La grilla solo exploró **por debajo** de 2,0. **No se ha probado ensanchar.** Es un hueco real.

**Esto refutó una predicción explícita del controlador.** Yo había extrapolado de P-08 que un suelo
de 2,0 era «sospechoso de estar costando dinero». Es al revés. La predicción se declaró falsable y
los datos la mataron.

## II.3 · P-03 — Apriete por desaceleración de AC · **DOS HALLAZGOS EN UNO**

### Fase 1 — la palanca estaba muerta (diagnóstico `7c4ea92`)

Los 95 brazos de la Ola 1 devolvieron **el mismo número hasta el último decimal**, incluido `ac_off`.
Causa medida: la condición **sí se activa** (6.306 de 13.947 llamadas), pero en
`emasar_variant.py:997` `trail_efectivo` se multiplica por el factor de AC y en **`:1001-1003` se
sobrescribe** con `max(trail_efectivo, trail_atr_floor_k · atr14_floor)`. Con el suelo vivo, el
mínimo medido es **8,67** y el máximo posible del trailing modulado es **1,00**: el suelo domina en
el **100 %** de las 8.321 barras con ATR válido.

**Ningún barrido de umbral podía arreglarlo**: el suelo es un `max`, impone un **mínimo**, y
`max(1,00 · 8,67)` da 8,67 para todo valor de la grilla. **El mecanismo de apriete que S6 supone que
tiene, en la estrategia viva no opera nunca.** Es un hecho sobre dinero real, no sobre el backtest.

### Fase 2 — se hizo funcionar, y funciona peor

Con el parámetro nuevo `ac_modulate_floor_relief_k` el trailing pequeño gana sobre el suelo.
**Validez:** pareado, emparejamiento 1,00.

| alivio | n | neto USD | diferencia USD/pos | p |
|---|---|---|---|---|
| 0,00 (bypass total) | 891 | 37.875 | −35,40 | 0,84 |
| 0,25 | 846 | 23.379 | −41,11 | 0,80 |
| 0,50 | 780 | 36.410 | −34,12 | 0,83 |
| 0,75 | 678 | 22.140 | −48,89 | 0,74 |
| **1,00 (control, suelo intacto)** | 624 | **42.976** | control | — |

**Los 16 brazos con alivio tienen diferencia negativa. Los dieciséis.** Ninguno significativo por
separado (p 0,65–0,91), pero el signo es unánime. Y los brazos de alivio 1,00 dan exactamente 0,00,
confirmando el diagnóstico por tercera vía.

**Veredicto:** el suelo que se tragaba el apriete **estaba protegiendo a la estrategia sin querer**.
El mecanismo, de haber funcionado, habría perdido dinero.

## II.4 · P-02 — Stop temporal por edad de la señal

**Validez:** pareado, emparejamiento 0,99–1,00. Sustrato **acortado** por D-60 (colisión con el borde
del holdout), aplicado por igual a control y a todos los brazos: sin sesgo, algo menos de potencia.
n del control: **615** en S6, **696** en S7 (contra 624/708 sin recorte).

### S6

| barras | n | neto USD | diferencia USD/pos | IC 95 % (CLP) | p |
|---|---|---|---|---|---|
| control (sin límite) | 615 | 45.850 | — | — | — |
| 4 | 849 | −50.418 | −155,62 | −451.440 · 121.839 | 0,33 |
| 6 | 774 | −62.346 | −153,19 | −512.253 · 159.751 | 0,40 |
| 8 | 723 | −46.049 | −124,91 | −394.031 · 99.593 | 0,35 |
| **10** | 693 | −70.761 | **−180,98** | −397.159 · 6.788 | **0,06** |
| 12 | 666 | −34.584 | −146,20 | −336.356 · 18.744 | 0,09 |
| **15** | 636 | **82.624** | **+26,68** | −174.635 · 183.442 | 0,73 |
| **20** | 630 | **67.224** | **+38,29** | −52.316 · 127.968 | 0,41 |
| 25 | 621 | 51.957 | −6,46 | −59.525 · 29.154 | 0,89 |
| 30 | 618 | 33.699 | −12,91 | −49.361 · 9.635 | 0,67 |
| 40 | 615 | 45.432 | −0,68 | −2.045 · 0 | 0,73 |
| 48 | 615 | 50.730 | +7,94 | 0 · 23.932 | 0,73 |
| 56 · 64 · 80 · 96 · 128 | 615 | 45.850 | **0,00 exacto** | 0 · 0 | 1,00 |

### S7

| barras | n | neto USD | diferencia USD/pos | p |
|---|---|---|---|---|
| control | 696 | −10.305 | — | — |
| 4 | 858 | −36.582 | −54,55 | 0,63 |
| 6 | 795 | −67.575 | −67,66 | 0,49 |
| 8 | 750 | −30.246 | −48,20 | 0,50 |
| **10** | 735 | −48.252 | **−104,24** | **0,06** |
| **12** | 720 | −47.970 | **−84,82** | **0,05** |
| 15 | 705 | −4.896 | −3,89 | 0,94 |
| **20** | 702 | −9.996 | **+7,75** | 0,80 |
| 25 | 699 | −14.214 | −3,04 | 0,55 |
| **30** | 696 | −7.686 | **+3,76** | 0,74 |
| 40 en adelante | 696 | −10.305 | **0,00 exacto** | 1,00 |

**Tres lecturas, en orden de solidez:**

1. **Los stops temporales cortos hacen daño, y es lo más cercano a significativo del programa después
   de P-08.** A 10 barras: p=0,06 en S6 **y** p=0,06 en S7; a 12 barras p=0,05 en S7. **Dos
   estrategias medidas por separado apuntando igual** vale más que cualquiera sola. Cortar pronto
   mata ganadores.
2. **A partir de cierto punto la palanca deja de morder**: la diferencia es **cero exacto** desde 56
   barras en S6 y desde 40 en S7. Ninguna posición vive tanto. El rango útil ya está barrido entero.
3. **Hay una ventana positiva alrededor de 15–20 barras** (+26,68 y +38,29 USD/pos en S6; +7,75 en
   S7 a 20 barras) que **no se descarta**: las p son altas (0,41–0,80), pero el signo coincide en las
   dos estrategias a 20 barras, y +38 USD/pos sobre 630 posiciones no es un margen despreciable si
   resultara real. **Merece réplica dirigida, no descarte.**

**Aviso estructural:** acortar posiciones **aumenta** el conteo (849 contra 615), porque salir libera
reentradas. P-02 **no es una palanca puramente de salida** y su efecto mezcla dos cosas.
⚠️ Confound conocido de 64 barras documentado en el catálogo.

## II.5 · P-05 — Multiplicador ATR de SuperTrend · **NO PAREADO**

Emparejamiento **0,02–0,49**: mover el multiplicador mueve los giros y cambia las entradas. **Su
estadístico pareado no es citable.** Lo legítimo es el conteo y la forma del neto.

| mult | n | neto USD | | mult | n | neto USD |
|---|---|---|---|---|---|---|
| 1,50 | 458 | 25.123 | | 3,25 | 151 | 49.220 |
| 1,75 | 354 | −3.484 | | 3,50 | 132 | 60.614 |
| 2,00 | 309 | 25.396 | | 3,75 | 137 | 34.245 |
| 2,25 | 259 | 57.470 | | 4,00 | 121 | 44.788 |
| **2,50** | 208 | **69.084** | | 4,25 | 96 | 12.577 |
| 2,75 | 168 | 61.251 | | 4,50 | 86 | 10.489 |
| **3,00 (vivo)** | **153** | **65.590** | | 4,75 | 77 | 72.107 |
| | | | | 5,00 | 65 | −7.953 |
| | | | | 5,50 | 58 | −25.578 |
| | | | | 6,00 | 52 | 41.163 |

**Control de sanidad:** el conteo cae de 458 a 52 monótonamente — el parámetro actúa.
**Meseta ancha entre 2,25 y 3,50** con netos altos; el 3,0 vivo cae dentro.
**La trampa:** el máximo de la grilla es **4,75 con 72.107 USD**, intercalado entre 10.489 y −7.953,
con n=77. Es ruido. Quien tomara el argmax sobreajustaría de manual.
**Lo único firme tras multiplicidad:** 5,00 · 5,50 · 6,00 son **peores**, con diferencia negativa.
**Veredicto:** ningún multiplicador supera al 3,0. Deja de ser prioridad tocarlo.

## II.6 · Filtros de entrada — P-09, P-19, P-20, P-21, P-28 · **SIN MEDIR**

Los 30 brazos dan `media_diff = 0,00` con p = 1,00 por la razón estructural de la Parte I. Lo que sí
es información útil son los **conteos y netos de las poblaciones filtradas**, que aún no se han
comparado con el estadístico correcto:

| palanca | brazo | n | neto USD | control USD |
|---|---|---|---|---|
| P-09 régimen S6 | k2-adx25 | 330 | **146.096** | 42.976 |
| | k2-vr095 | 426 | 85.769 | |
| | k2-er050 | 411 | 80.184 | |
| | k2-baseline | 420 | 72.591 | |
| | k3-vr095 | 180 | 10.227 | |
| | k3-chop38 | 42 | 27.395 | |
| P-19 H4 EMA S6 | p10 | 324 | 43.629 | 42.976 |
| | p30 | 309 | **−30.522** | |
| P-19 H4 EMA S7 | todos | 348–369 | −36.140 a −52.048 | −14.874 |
| P-20 alineación H4-ST | h4st | 153 | 65.590 | 65.590 |
| P-21 momento H1 S6 | emaslope | 378 | −56.577 | 42.976 |
| | momentum | 432 | −18.981 | |
| P-28 alineación H1 S6 | p10..p30 | 351–417 | −19.284 a −56.577 | 42.976 |
| P-28 alineación H1 S7 | p10..p30 | 399–462 | −32.505 a −62.980 | −14.874 |

**Lo que insinúan estas cifras, y hay que tratarlo como insinuación hasta re-analizar:**
- **P-09 con ADX>25 y acuerdo de 2 de 4 llega a 146.096 USD contra 42.976 del control**, con casi la
  mitad de operaciones (330 contra 624). Es, de lejos, el número más alto de todo el programa. Puede
  ser real o puede ser un artefacto de haber quitado un tramo malo por azar. **Exige el re-análisis
  no pareado antes de creer nada.**
- **Los filtros de temporalidad superior son sistemáticamente destructivos**: P-19 en S7, P-21 y P-28
  en ambas estrategias empeoran el neto respecto a su control en todos los brazos. Si el
  re-análisis lo confirma, **refuta la recomendación de mayor confianza de la literatura** (el filtro
  H4 era «la adición de mayor confianza y menor esfuerzo»).
- 🔴 **P-20 es un defecto, no un resultado:** el brazo filtrado tiene n, neto y emparejamiento
  **idénticos** al control. El filtro no quitó ni una operación. Hay que verificar si actúa.

## II.7 · Tamaño de posición — P-13, P-15, P-16, P-17, P-18 · **VÁLIDO**

Emparejamiento **1,00**, n = 1485 en todos: el sizing multiplica las **mismas** posiciones.
Control común (`neutral`): **93.691 USD**.

### P-16 · Freno por drawdown — **AMBOS BRAZOS POSITIVOS**

| brazo | neto USD | Δ neto | diferencia USD/pos | p |
|---|---|---|---|---|
| **continuo** (`1 − DD/20 %`, suelo 25 %) | **117.715** | **+24.024 (+25,6 %)** | **+16,18** | 0,88 |
| **escalonado** (5/10/15 % → 75/50/25 %) | **108.257** | **+14.566 (+15,5 %)** | **+9,81** | 0,93 |
| control | 93.691 | — | — | — |

Las p son altísimas y no se acercan a significancia. **Pero es el único punto de las tres olas donde
dos operacionalizaciones distintas de la misma idea apuntan las dos en la misma dirección positiva**,
y el margen no es marginal: un 25,6 % de neto. **No se descarta.**

### P-17 · Ponderación de fichas — **PATRÓN EN ESPEJO**

| brazo | pesos F1/F2/F3 | neto USD | Δ neto | diferencia USD/pos | IC 95 % (CLP) | p |
|---|---|---|---|---|---|---|
| **peso adelante** | 40 / 35 / 25 | **106.809** | **+13.118 (+14,0 %)** | **+8,83** | −4.888 · 24.809 | **0,25** |
| control | 33 / 33 / 33 | 93.691 | — | — | — | — |
| peso atrás | 30 / 30 / 40 | 87.132 | −6.559 (−7,0 %) | −4,42 | −12.405 · 2.444 | **0,25** |

**Es la p más baja del bloque de sizing y el patrón más limpio que ha aparecido fuera de P-08.**
No es un brazo suelto que salió bien: son **dos brazos espejo con signos opuestos y magnitudes
coherentes** (+8,83 y −4,42). Eso tiene forma de efecto, no de ruido.

**Qué dice, en cristiano:** S6 abre tres «fichas» por señal. Cargar volumen en **la primera** mejora;
cargarlo en **la tercera** empeora. **La primera ficha es la buena y la tercera es la mala.**

**Y encaja con la historia de las salidas.** P-08 midió que las posiciones que tocan el nivel de stop
siguen yendo en contra en vez de recuperarse. Las fichas posteriores se añaden conforme el movimiento
se extiende, o sea más tarde y peor situadas. Dos familias independientes apuntando al mismo hecho
subyacente es lo más parecido a una señal estructural que tiene el programa.

### P-13 · Kelly fraccional — negativo, y el mecanismo se entiende

| brazo | neto USD | diferencia USD/pos | p |
|---|---|---|---|
| α = 0,25 | 2.189 | −61,62 | 0,71 |
| α = 0,50 | 4.379 | −60,14 | 0,71 |
| α = 1,00 | 8.757 | −57,19 | 0,71 |
| control | 93.691 | — | — |

El neto se hunde de 93.691 a 2.189 USD. **No es que Kelly pierda: es que con un borde estadístico
casi nulo Kelly manda a operar con tamaño casi cero, y el neto escala con el tamaño.** La literatura
lo anticipó — recomendó Kelly fraccional precisamente porque la calidad estadística de S6 es ≈0.
Confirma el diagnóstico de la literatura sobre la debilidad de la señal.

### P-15 · Descuento por correlación — negativo y monótono

| descuento | neto USD | diferencia USD/pos | p |
|---|---|---|---|
| 0,70 | 29.655 | −43,12 | 0,51 |
| 0,77 | 26.796 | −45,05 | 0,51 |
| 0,85 | 23.853 | −47,03 | 0,51 |

Cuanto más se descuenta, peor. ⚠️ **Discrepancia de fórmula declarada:** la fuente propone
`size/√(1+overlap)` y lo implementado es `1/(1+descuento·n_extra)`. **Este resultado mide la fórmula
implementada, no la de la literatura.** Pendiente de decisión.

### P-18 · Freno por Sharpe rodante — negativo en los diez brazos

| umbral × reducción | neto USD | diferencia USD/pos | p |
|---|---|---|---|
| 0,3 × 20 % | 6.145 | −58,95 | 0,66 |
| 0,3 × 50 % | 38.976 | −36,85 | 0,66 |
| 0,5 × 50 % | **52.630** | **−27,65** | 0,74 |
| 0,7 × 50 % | 52.170 | −27,96 | 0,74 |

Los diez negativos. Patrón claro: **cuanto menos frena, menos daño hace** — la mejor variante es la
que casi no interviene. Es la firma de una intervención que no aporta.

---

# PARTE III — Cuadro de mejores candidatos y su composición

**Ninguno de estos alcanza significancia estadística.** Se listan porque muestran margen positivo
sobre la línea base y no se descartan prematuramente.

| # | candidato | Δ neto | Δ USD/pos | p | familia | calidad de la evidencia |
|---|---|---|---|---|---|---|
| 1 | **P-16 freno por drawdown, continuo** | +25,6 % | +16,18 | 0,88 | sizing | dos variantes, ambas positivas |
| 2 | **P-17 peso en la primera ficha** | +14,0 % | +8,83 | 0,25 | sizing | espejo con signos opuestos; p más baja del bloque |
| 3 | **P-16 freno por drawdown, escalonado** | +15,5 % | +9,81 | 0,93 | sizing | variante de #1 |
| 4 | **P-02 stop temporal 20 barras** | +46,6 % | +38,29 | 0,41 | salidas | signo coincide en S6 y S7 |
| 5 | **P-02 stop temporal 15 barras** | +80,2 % | +26,68 | 0,73 | salidas | solo S6 |
| 6 | **P-09 régimen ADX>25, k=2** | +240 % | n/d | n/d | entradas | **instrumento inválido; pendiente de re-análisis** |
| — | *statu quo confirmado* | — | — | — | — | P-05 mult 3,0 · P-34 suelo 2,0 |

## Composición: qué se puede juntar y qué no

| par | ¿componen? | razón |
|---|---|---|
| **P-16 × P-17** | **Sí, con cuidado** | Son multiplicadores de lote en dimensiones distintas: P-16 al nivel de cuenta según drawdown, P-17 al nivel de ficha. Se multiplican de forma natural. **Riesgo:** ambos reducen tamaño en algún régimen; combinados pueden encoger de más. **Medir juntos, no sumar los efectos sobre el papel.** |
| **P-16 × P-02** | **Sí, pero con interacción esperada** | El sizing es ortogonal al momento de salida. **Pero** P-02 cambia el número de posiciones y con ello la trayectoria de drawdown, que es justo la entrada de P-16. El efecto conjunto **no es la suma**. Exige brazo conjunto. |
| **P-17 × P-02** | **Sí, e interesa especialmente** | Ambos dicen algo sobre qué parte de la posición vale. Si la primera ficha es la buena y las posiciones largas decaen, apretar el tiempo y cargar adelante pueden reforzarse. **Hipótesis conjunta con fundamento, no combinatoria ciega.** |
| **P-17 × P-34** | **Sí, pero confundidos** | P-17 pondera fichas; P-34 fija el suelo del trailing **común a todas**. Parte del beneficio de P-17 puede venir de despriorizar la ficha más expuesta a ese suelo. **Medirlos juntos o el crédito se asigna mal.** |
| **P-16 × P-13 × P-18** | **NO** | Los tres son multiplicadores de lote que reaccionan al desempeño. Componerlos multiplica el encogimiento, y **P-13 y P-18 midieron negativo**. Añadirlos solo puede restar. |
| **P-08 × cualquiera** | **NO** | Refutada con evidencia fuerte. No entra en ninguna combinación. |
| **P-03-alivio × cualquiera** | **NO** | 16 de 16 negativos. El suelo protege; no se toca. |
| **P-34 (apretar) × cualquiera** | **NO** | 8 de 8 negativos. |
| **P-09 × sizing** | **Pendiente** | Si el re-análisis confirma a P-09, es la única palanca de **entradas** viva, y compone bien con las de sizing porque actúan en momentos distintos. **No combinar hasta validar el instrumento.** |

**La combinación mínima defendible hoy** sería **P-16 continuo + P-17 peso adelante**, ambas del
mismo bloque, ambas positivas, ambas sobre las mismas posiciones — y por tanto medibles como un
único brazo pareado adicional, sin coste de motor. Es el experimento más barato con más margen.

---

# PARTE III-B — Composición de resultados: cómo combinar lo que superó a la línea base

Esta sección trata **únicamente** los brazos que quedaron **por encima de su control**, aunque
ninguno alcance significancia. El criterio para incluirlos no es que sean creíbles por separado —
no lo son — sino que **componerlos es, estadísticamente, la forma correcta de averiguar si son
reales**. La justificación está en III-B.4.

## III-B.1 · Inventario completo de lo que superó a su control

| # | brazo | familia | Δ neto | Δ USD/pos | p | n | base de comparación |
|---|---|---|---|---|---|---|---|
| C1 | P-16 freno DD **continuo** | sizing | +25,6 % | +16,18 | 0,88 | 1485 | control sizing 93.691 |
| C2 | P-16 freno DD **escalonado** | sizing | +15,5 % | +9,81 | 0,93 | 1485 | control sizing 93.691 |
| C3 | P-17 **peso adelante** 40/35/25 | sizing | +14,0 % | +8,83 | 0,25 | 1485 | control sizing 93.691 |
| C4 | P-02 **15 barras** (S6) | salidas | +80,2 % | +26,68 | 0,73 | 636 | control S6 45.850 |
| C5 | P-02 **20 barras** (S6) | salidas | +46,6 % | +38,29 | 0,41 | 630 | control S6 45.850 |
| C6 | P-02 **48 barras** (S6) | salidas | +10,6 % | +7,94 | 0,73 | 615 | control S6 45.850 |
| C7 | P-02 **20 barras** (S7) | salidas | +3,1 % | +7,75 | 0,80 | 702 | control S7 −10.305 |
| C8 | P-02 **30 barras** (S7) | salidas | +25,4 % | +3,76 | 0,74 | 696 | control S7 −10.305 |
| C9 | P-05 **mult 2,50** (ST) | geometría ST | +5,3 % | n/a | n/a | 208 | control ST 65.590 · **no pareado** |
| C10 | P-09 **ADX>25, k=2** (S6) | entradas | +240 % | n/a | n/a | 330 | control S6 42.976 · **instrumento inválido** |

🔴 **Advertencia de base, crítica para no sumar peras con manzanas.** Los porcentajes **no comparten
denominador**. El bloque de sizing corre sobre **n = 1485** con control 93.691 USD; P-02 corre sobre
**n ≈ 615–636** con control 45.850 USD (S6) y −10.305 (S7); P-05 sobre 153 posiciones de SuperTrend.
**Los porcentajes no se suman ni se multiplican entre bloques.** Lo único comparable entre familias
es la **diferencia por posición**, y aun esa está medida sobre poblaciones distintas.

## III-B.2 · Taxonomía: en qué dimensión actúa cada uno

Componer es seguro cuando dos palancas actúan sobre dimensiones ortogonales, y peligroso cuando
compiten por la misma decisión. Ordenadas por punto de intervención:

| palanca | ¿qué decide? | ¿cuándo actúa? | ¿es de suma cero? |
|---|---|---|---|
| **P-09** (entradas) | si la operación se abre o no | antes de abrir | reduce el conteo |
| **P-16** (freno DD) | **cuánto** volumen, según el drawdown de la cuenta | al abrir | **reduce el total** |
| **P-17** (pesos de ficha) | **cómo se reparte** el volumen entre las tres fichas | al abrir | **suma cero: 40+35+25 = 33+33+33** |
| **P-02** (stop temporal) | cuándo se cierra | durante la vida | cambia el conteo (libera reentradas) |
| **P-05** (mult ST) | geometría de entrada y salida de SuperTrend | continuo | otra estrategia, otro sustrato |

**El hecho técnico que hace de C1 × C3 el mejor par, y conviene entenderlo bien:**
**P-17 es una reasignación de suma cero** — mueve volumen entre fichas sin cambiar el total.
**P-16 es un estrangulador** — reduce el total sin tocar el reparto.
**No compiten por el mismo presupuesto de volumen.** Actúan sobre ejes matemáticamente independientes
del mismo multiplicador de lote: uno fija su magnitud, el otro su distribución. Es la única pareja
del inventario de la que se puede decir eso.

## III-B.3 · Cómo se compone cada par, uno por uno

### C1 × C3 — freno por drawdown × peso adelante · **la pareja limpia**
**Mecánica:** los dos son multiplicadores de lote, así que en el motor **se multiplican
literalmente**: `lote = base × f_drawdown(estado_cuenta) × w_ficha(índice)`. No hay conflicto de
precedencia ni orden de aplicación que decidir.
**Aritmética si fueran independientes:** 1,256 × 1,140 = **1,432**, o sea **+43,2 %** → 134.164 USD
sobre el control de 93.691.
**Por qué esa cifra es un techo, no una predicción:** exige que ambos efectos sean reales, aditivos
en logaritmo, y no correlacionados con las mismas posiciones. Ninguna de las tres cosas está
demostrada. Trátese como la **cota superior** de lo que el experimento conjunto podría devolver.
**Riesgo concreto:** ambos reducen exposición en algún régimen — P-16 en drawdown, P-17 en las fichas
tardías — y las fichas tardías tienden a abrirse cuando el movimiento ya se extendió, que es
correlacionado con los tramos que generan drawdown. **El solapamiento no es cero.**
**Coste:** ninguno. Mismas posiciones, `task-type` de sizing ya construido, brazo pareado adicional.

### C1 × C5 — freno por drawdown × stop temporal de 20 barras
**Mecánica:** ortogonales en apariencia (uno dimensiona, otro cierra), **pero no separables**. P-02
cambia el número y la secuencia de posiciones, y esa secuencia **es la entrada de P-16**: el
drawdown de la cuenta es una función del camino. Cambiar el camino cambia cuándo se dispara el freno.
**Dirección esperada de la interacción, y es ambigua a propósito:** si el stop temporal produce más
posiciones perdedoras (lo hace en el tramo corto), el drawdown se profundiza y **P-16 frena más**,
lo que podría **amortiguar el daño** de P-02 — o, si el stop temporal mejora el camino, P-16 frena
menos y **aporta menos**. Ambos signos son defendibles a priori. **Solo el brazo conjunto lo decide.**
**Coste:** medio. Exige correr el sizing sobre las posiciones que produce P-02, no sobre las del
control.

### C3 × C5 — peso adelante × stop temporal · **la pareja con más contenido teórico**
**Por qué interesa más que las otras:** las dos dicen algo sobre **qué parte de la operación vale**.
P-17 dice que la primera ficha es la buena. P-02 (en su tramo positivo) insinúa que la exposición
prolongada no aporta. P-08 dice que las posiciones que van en contra siguen yendo en contra.
**Las tres podrían ser la misma cosa vista desde tres sitios.**
🔴 **Y de ahí sale el riesgo más sutil de toda esta sección: el doble conteo.** Si el beneficio de
C3 y el de C5 provienen del **mismo hecho subyacente** —que la exposición tardía es peor—, entonces
sumarlos cuenta dos veces un solo efecto, y el brazo conjunto rendirá **cerca del máximo individual,
no de la suma**.
**Eso es medible, y es el diagnóstico más valioso disponible:**
- efecto conjunto ≈ suma de los individuales ⇒ **causas independientes**, ambas palancas valen;
- efecto conjunto ≈ máximo de los individuales ⇒ **una sola causa**, y sobra una de las dos;
- efecto conjunto < máximo ⇒ **interfieren**, y hay que elegir.

### C3 × P-34 — peso de fichas × suelo del trailing · **confundidos por diseño**
P-34 fija el suelo del trailing **común a las tres fichas**. Si el beneficio de C3 viene de
despriorizar la ficha más expuesta a ese suelo, entonces el crédito pertenece al suelo, no al peso.
**Medirlos juntos o la atribución será incorrecta.** No es una composición para ganar: es una
composición para **saber a quién atribuir la ganancia**.

### C10 (P-09) × sizing — **substitutos, probablemente, no complementos**
Aquí está la predicción no obvia más importante de la sección. P-09 filtra los regímenes malos.
P-16 frena el tamaño **cuando el drawdown ya se produjo**, y ese drawdown se genera mayoritariamente
en los regímenes malos.
**Si P-09 funciona, elimina la causa de los drawdowns a los que P-16 reacciona.** Un filtro que
evita el mal tramo y un freno que reacciona al mal tramo **atacan el mismo dinero**. Compuestos
rendirían **menos que la suma**, posiblemente mucho menos.
**Predicción falsable, y la dejo escrita para poder equivocarme:** el brazo conjunto P-09 × P-16
rendirá **por debajo** de la suma de sus efectos individuales. Si rinde por encima, esta lectura
está mal y hay una complementariedad que no veo.
**No componer hasta validar el instrumento de P-09** (re-análisis no pareado).

### C9 (P-05 mult 2,50) — **pista separada, no componible con lo anterior**
Es de SuperTrend, otra estrategia, otro sustrato, y **no pareada**. No entra en ninguna combinación
con las palancas de S6. Se anota porque es el único brazo de SuperTrend por encima de su control,
con un margen modesto (+5,3 %) y dentro de la meseta ya identificada. **Prioridad baja.**

### Lo que no entra en ninguna combinación
**P-08** (refutada con evidencia fuerte, la única con significancia), **P-03-alivio** (16 de 16
negativos), **P-34 por debajo de 2,0** (8 de 8 negativos), **P-13 Kelly**, **P-15 descuento**,
**P-18 freno por Sharpe** (los tres negativos). Y **P-16 × P-13 × P-18** en conjunto está
explícitamente desaconsejado: los tres son multiplicadores que reaccionan al desempeño, componerlos
multiplica el encogimiento del tamaño, y dos de ellos midieron negativo.

## III-B.4 · Por qué componer efectos no significativos es legítimo — y cuándo deja de serlo

Esta es la parte que decide si toda la sección vale algo.

**El argumento a favor: potencia, no confirmación.** Un brazo conjunto pre-registrado —«C1 y C3
juntos contra el control»— es **una sola prueba**, no dos. No paga penalización por multiplicidad, y
si los efectos son reales y aproximadamente aditivos, **el tamaño del efecto conjunto es mayor
respecto al mismo ruido**. Una diferencia de +16,18 y otra de +8,83 USD por posición, cada una
ahogada en su propio intervalo, pueden dar juntas ~+25 contra la misma varianza. **Componer es la
forma barata de ganar potencia sin recolectar más datos.**

**El argumento en contra, y es el que mata programas enteros: seleccionar sobre ruido.** Si de cada
palanca se toma **el mejor brazo** y se apilan cinco, se han hecho cinco selecciones sobre datos
ruidosos. La pila se verá espléndida dentro de la muestra y se evaporará fuera. Es exactamente el
mecanismo por el que el máximo de la grilla de P-05 es 4,75 con n=77 — un número que no significa
nada y que parecería un hallazgo si se apilara con otros.

**Las tres condiciones que separan una cosa de la otra, y son obligatorias:**
1. **La combinación se pre-registra ANTES de correrla**, con su hipótesis y su regla de decisión —
   igual que se hizo con los 157 brazos de la Ola 1 (`1c7279d`). Una combinación elegida después de
   ver los resultados no es evidencia, es una descripción de los resultados.
2. **Se declaran los contrastes de interacción por adelantado**, no solo el efecto conjunto. Sin
   ellos no se puede distinguir «dos causas» de «una causa contada dos veces» (III-B.3, C3 × C5).
3. **La combinación ganadora, si aparece, se confirma en el holdout**, que sigue **intacto**. Es la
   única defensa real contra la selección sobre ruido, y es el motivo por el que el holdout no se ha
   tocado.

**Y una restricción que sobrevive a todo lo anterior:** el simulador diverge 3,28 % con signo opuesto
por estrategia. **Nada de esto autoriza a citar una cifra absoluta de dinero.** Lo que la composición
puede entregar es un **veredicto comparativo** —esta combinación supera al control sobre las mismas
entradas— con banda de error declarada. No un pronóstico de beneficio.

## III-B.5 · Diseño concreto propuesto: factorial 2×2×2

Ocho brazos, todos pareados sobre las mismas entradas, pre-registrados en bloque:

| factor | nivel 0 | nivel 1 |
|---|---|---|
| **A · freno por drawdown** (P-16) | apagado | continuo, `1 − DD/20 %`, suelo 25 % |
| **B · pesos de ficha** (P-17) | 33 / 33 / 33 | 40 / 35 / 25 |
| **C · stop temporal** (P-02) | sin límite | 20 barras |

**Qué entrega, y por qué un factorial y no ocho pruebas sueltas:**
- Los **efectos principales** de A, B y C se estiman cada uno usando **los ocho brazos**, no dos —
  cuatro veces más datos por efecto que probándolos por separado.
- Las **interacciones** A×B, A×C, B×C salen del mismo experimento sin coste adicional. La
  interacción B×C es precisamente el diagnóstico de doble conteo de III-B.3.
- El **brazo A1B1C1** es la combinación completa, y su comparación contra A0B0C0 es una única prueba
  pre-registrada.

**Reglas de decisión a fijar antes de correr:**
- efecto conjunto ≈ suma de los tres principales ⇒ causas independientes, se conservan las tres;
- efecto conjunto ≈ el mayor de los principales ⇒ una sola causa; se conserva la palanca más simple
  y se descartan las otras dos como redundantes;
- cualquier interacción negativa relevante ⇒ las palancas implicadas **no** se combinan y se elige
  una.

**Coste:** A y B no cuestan motor —son multiplicadores sobre las mismas posiciones—; C exige correr
el sustrato de P-02, ya construido y con el recorte de D-60 aplicado. **Es el experimento de mayor
margen por unidad de esfuerzo que existe hoy en el programa.**

**Fuera de este factorial, por decisión explícita:** P-09 (instrumento sin validar), P-05 (otra
estrategia y no pareada), y todo lo refutado.

---

# PARTE IV — Avance del plan

| pieza | estado |
|---|---|
| T0.7 · A6 fidelidad del motor | **hecho** — divergencia 17,6 % → 3,28 % |
| Puerta de paridad re-congelada | **hecho** — 4 passed |
| T0.9 · Runner + modo desatendido | **hecho** |
| T0.10 · Literatura formal | **parcial** — 4 de 7 áreas; 3 pendiente declarado |
| T0.11 · Videos | **parcial** — 21 de 28; 7 pendiente declarado (D-51) |
| WP-1+2 · Harness pareado e instrumentación | **hecho** |
| WP-3 · Feed H1/H4 | **hecho** (construido y cableado) |
| WP-4 · Hook de sizing | **hecho** (construido y con task-type) |
| WP-5 · Cómputos de régimen | **hecho** (cableado a nivel de harness, no del núcleo) |
| Ola 1 · 157 brazos | **hecho** — 123 corrieron |
| Ola 1B · 63 brazos | **hecho** — 63/63 |
| Ola 2 · 62 brazos | **corrido, mitad inválido** |
| **T0.8 · Congelado del motor** | **NO HECHO** — sin firmar; todo es piloto-instrumento |
| Re-análisis no pareado de filtros de entrada | **NO HECHO** |
| Verificación de P-20 | **NO HECHO** |
| Reporte OLA2 | **NO HECHO** |
| §5 · Autopsia de posiciones | **NO EMPEZADO** |
| §9 · Validación estadística formal | **NO EMPEZADO** |
| Holdout | **INTACTO** |
| Olas 3 · HMM, GARCH, Hurst, VWAP, trendline, P-14, P-22/23/29 | **BLOQUEADAS** — sin implementación, diferidas a propósito |

**Palancas: 34 en total.** 10 medidas con instrumento válido · 5 corridas con instrumento inválido ·
19 sin correr o bloqueadas.

---

# PARTE V — Decisiones pendientes y propuesta

## Sin responder

1. **Re-análisis no pareado de los filtros de entrada** — ¿se autoriza? Es barato, no re-corre el
   motor, y desbloquea 30 brazos ya ejecutados. Bloquea a P-09, la única candidata de entradas.
2. **P-20** — el filtro no quita nada. ¿Defecto o comportamiento real?
3. **Fórmula de P-15** — ¿se implementa la de la fuente o se acepta la sustitución?
4. **Curación de P-09, P-16, P-17 y P-18** — las tuplas exactas las construyó un agente a partir de
   conjuntos de valores. Requiere revisión antes de tratarse como definitiva.
5. **T0.8, congelado del motor** — sin firmar, y sin firma nada de esto sale de «piloto».
6. **Ensanchar el suelo de P-34 por encima de 2,0** — nunca se probó. Hueco declarado.
7. 🔴 **Pregunta de seguridad, abierta desde el 2026-08-15 y no técnica:** once cierres manuales
   (`reason=CLIENT`, `magic=0`) sobre posiciones de estrategia, diez de ellos ganadores, dos en el
   mismo segundo, moviendo +30.965 USD; más un take-profit con comentario nativo que el motor no
   puso. Si no fuiste tú, **alguien más tiene acceso a la cuenta 902.**

## Propuesta, en orden

1. **Re-analizar los filtros de entrada sin emparejar** (expectativa condicional, bootstrap por día
   de servidor, regla S0 del plan). Barato y con el número más alto del programa en juego.
2. **Verificar P-20.**
3. **Correr el brazo combinado P-16 continuo + P-17 peso adelante.** Mismo bloque, mismas posiciones,
   sin coste de motor: es el experimento con mejor relación margen/esfuerzo que existe hoy.
4. **Réplica dirigida de P-02 en la ventana 15–25 barras**, con brazos densos, para decidir si
   la ventana positiva es real o ruido.
5. **Ampliar P-34 por encima de 2,0.**
6. **Escribir el reporte de OLA2** y firmar o no **T0.8**.
