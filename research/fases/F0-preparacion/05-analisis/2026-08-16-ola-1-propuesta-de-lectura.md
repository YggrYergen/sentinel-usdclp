# Ola 1 — PROPUESTA DE LECTURA

**Fecha:** 2026-08-16 · **Autor:** controlador (Opus) · **Estado:** propuesta, no veredicto.

🔴 Según la cabecera del consolidado y la directiva del user del 2026-08-16, ninguna interpretación
de estos datos es válida hasta haber sido discutida con el humano y aprobada por él. Este documento
es **propuesta de lectura**, vive aparte del artefacto de datos, y no modifica ningún resultado.

**Estado del resultado:** piloto-instrumento (D-57). El congelado del motor no está firmado.

**Fuente única:** `04-resultados/OLA1/_consolidado.md` y `_consolidado.json`, commit `48fe8d5`.
Corrida `ad5b95d`, 36,3 s de reloj para 157 brazos.

---

## 0 · Cobertura real de la ola

| corrida | brazos | estado |
|---|---|---|
| P03-S6 | 95 | corrió |
| P05-ST | 17 | corrió |
| P08-ST | 11 | corrió |
| P02-S6 | — | **falló** |
| P02-S7 | — | **falló** |

**123 de 157 brazos completaron. Los 34 que faltan son P-02 entero, incluidos sus 14
confirmatorios.** Causa: `HoldoutVioladoError` reproducible — una posición con time-stop
`max_hold_bars=10` cierra exactamente en `t_exit == HOLDOUT_INI` y dispara la guarda fail-loud. La
guarda funciona como está especificada; lo que falta es decidir cómo tratar la colisión de borde.

Corrección por multiplicidad Benjamini-Hochberg, α=0,05: **3 de 27 confirmatorios rechazados**;
7 de 120 en total.

---

## 1 · P-03 · Apriete por desaceleración de AC — **NO MIDIÓ NADA**

**Los 95 brazos devuelven el mismo número, hasta el último decimal: `net_lote1 = 40.246.087,50`,
`n = 624`, `media_diff = 0,00`, `p = 1,00`.**

Esto **no es** una respuesta plana, y la distinción es la más importante de todo el documento. La
prueba está en un brazo concreto: **`ac_off`** —que apaga el mecanismo por completo— **también
devuelve el mismo número que `default`**. Si desactivar entero el mecanismo no cambia ni un
decimal, entonces el mecanismo **no se está ejerciendo** sobre este sustrato. El barrido no midió un
efecto pequeño: midió cero información.

Las dos explicaciones compatibles con la evidencia, ninguna descartada:
1. La rama de desaceleración de AC **nunca se activa** en esta ventana de datos, por lo que ningún
   umbral, ventana ni modulación puede cambiar nada.
2. El parámetro llega al motor —el implementador lo verificó— pero **el punto donde llega no
   gobierna ninguna decisión** en esta configuración.

Conecta con el hallazgo de unidades ya registrado (`979eb91`): el umbral de P-03 estaba en pips
×0,01. Si la escala está mal, toda la grilla puede haber barrido una región donde la condición es
inalcanzable.

**Veredicto propuesto:** NO EVALUABLE. Se declara así, no como «sin efecto». Cuesta una tarea barata
de diagnóstico: contar cuántas veces se activa la condición de desaceleración de AC en el sustrato.
Si la respuesta es cero, la palanca no es medible aquí y hay que decirlo; si es distinta de cero, hay
un defecto de cableado que encontrar. **Hasta saberlo, ningún brazo de P-03 es citable.**

---

## 2 · P-05 · Multiplicador ATR de SuperTrend — sin ganador, con un extremo descartado

**Naturaleza del dato: NO PAREADO (1-B), y los números lo confirman.** La tasa de emparejamiento
cae a **0,02–0,25** en casi toda la grilla. Es lo esperado y estaba pre-registrado: SuperTrend está
siempre en mercado, así que mover el multiplicador mueve los puntos de giro y por tanto **cambia el
conjunto de entradas**. Consecuencia dura: `media_diff` y su intervalo se calculan sobre el puñado de
posiciones que por casualidad coinciden, que es una submuestra auto-seleccionada, no una comparación
pareada. **Ese estadístico no debe citarse para P-05.**

Lo que sí es legítimo mirar es el conteo de posiciones y la forma del neto.

| mult | n | net_lote1 |
|---|---|---|
| 1,50 | 458 | 23.527.689,50 |
| 1,75 | 354 | −3.262.766,00 |
| 2,00 | 309 | 23.783.354,00 |
| 2,25 | 259 | 53.818.782,00 |
| 2,50 | 208 | 64.697.166,00 |
| 2,75 | 168 | 57.361.561,50 |
| **3,00 (default)** | **153** | **61.425.035,00** |
| 3,25 | 151 | 46.094.530,00 |
| 3,50 | 132 | 56.765.011,00 |
| 3,75 | 137 | 32.070.442,50 |
| 4,00 | 121 | 41.943.962,00 |
| 4,25 | 96 | 11.778.360,50 |
| 4,50 | 86 | 9.822.948,50 |
| 4,75 | 77 | 67.528.205,50 |
| 5,00 | 65 | −7.447.984,50 |
| 5,50 | 58 | −23.953.797,00 |
| 6,00 | 52 | 38.549.149,50 |

**Lo monótono y creíble:** el número de posiciones cae de 458 a 52 al ampliar la banda. Es mecánico
—banda más ancha, menos giros— y sirve de control de sanidad de que el parámetro sí actúa.

**Lo que la grilla sugiere:** hay una **meseta ancha entre 2,25 y 3,50** donde el neto se mantiene
alto (53,8 · 64,7 · 57,4 · 61,4 · 46,1 · 56,8), y degradación errática fuera de ella. El 3,0
heredado **cae dentro de la meseta**.

**Lo que impide llamarlo resultado:** la serie es no monótona de forma incompatible con una
superficie de respuesta real. `mult4,75` da **67,5 millones —el valor más alto de toda la grilla—
intercalado entre 9,8 y −7,4 millones**, con n=77. Eso es ruido, y es el ejemplo de manual de por
qué elegir el máximo de una grilla es sobreajustar. Cualquiera que tomase el argmax de esta tabla se
llevaría 4,75.

**Lo único estadísticamente firme:** tras corrección por multiplicidad, los brazos rechazados son
**5,00 · 5,50 · 6,00**, los tres con diferencia **negativa**. Es decir, lo único que la ola demuestra
sobre P-05 es que **los multiplicadores muy anchos son peores**. Y aun eso está calculado sobre
tasas de emparejamiento del 2–3 %, así que se sostiene débilmente.

**Veredicto propuesto contra la regla pre-registrada:** ningún multiplicador supera al 3,0.
La hipótesis de la literatura —que el 3,0 no tiene derivación y podría no ser óptimo para oro en
M15— **no queda confirmada ni refutada**: no aparece un valor mejor, y el 3,0 resulta estar dentro
de una meseta razonable. Es un resultado modesto pero real: **deja de ser urgente tocar ese
parámetro**.

---

## 3 · P-08 · Offset de SL consciente del fill — **REFUTADA, y es el resultado limpio de la ola**

**Naturaleza del dato: PAREADO de verdad.** Tasa de emparejamiento **0,84–0,98**, n entre 129 y 150.
Es la única comparación de toda la ola donde el diseño pareado funciona como se diseñó, y por tanto
la única cuyo resultado sobrevive al sesgo del simulador.

| offset | n | media_diff | IC 95 % | p | BH |
|---|---|---|---|---|---|
| 0,05 | 150 | **−3.090,45** | −4.615,37 · −1.748,11 | 0,00 | rechaza |
| 0,10 | 149 | **−7.347,44** | −9.469,77 · −5.396,65 | 0,00 | rechaza (confirmatorio) |
| 0,15 | 149 | **−10.666,04** | −13.105,40 · −8.407,33 | 0,00 | rechaza |
| 0,20 | 148 | **−15.047,28** | −18.396,91 · −11.970,90 | 0,00 | rechaza (confirmatorio) |
| 0,25 | 145 | −2.299,27 | −23.819,42 · 40.769,52 | 0,65 | no |
| 0,30 | 144 | −5.313,34 | −26.814,00 · 38.148,29 | 0,53 | no |
| 0,40 | 141 | −2.929,05 | −34.955,65 · 48.550,80 | 0,79 | no |
| 0,50 | 137 | −13.076,82 | −46.030,57 · 40.165,49 | 0,50 | no |
| 0,75 | 133 | −38.347,21 | −71.965,57 · 15.426,95 | 0,13 | no |
| 1,00 | 129 | −22.693,79 | −92.586,94 · 74.132,59 | 0,55 | no |

**Los cuatro offsets pequeños dan un efecto negativo, significativo, con intervalos que no tocan el
cero, y — lo más informativo — casi perfectamente lineal en la dosis:** −61.800 · −73.470 · −71.107
· −75.235 por unidad de offset. Una relación dosis-respuesta así de estable en cuatro puntos
independientes no es casualidad.

A partir de 0,25 el efecto se disuelve en ruido: los intervalos cruzan el cero y las p suben a 0,5–0,8.
Coherente: con offsets grandes la tasa de emparejamiento empieza a caer y el offset ya no solo
retrasa la salida, también cambia qué posiciones existen.

**Veredicto propuesto: HIPÓTESIS REFUTADA, con evidencia fuerte.** La propuesta de la literatura
(Área 1, regla H) era que un colchón sobre la línea de SuperTrend compensaría el deslizamiento del
bróker y evitaría salidas «por poco». Medido: ensanchar el stop **no salva nada, cuesta dinero, y
cuesta en proporción directa a cuánto lo ensanches**. La propia fuente ya la calificaba de parche y
recomendaba arreglar la entrada, no la salida. El parche está medido y es negativo.

---

## 4 · P-02 · Time-stop por edad de la señal — **NO CORRIÓ**

Los 34 brazos, incluidos los 14 confirmatorios, fallaron con `HoldoutVioladoError`: con
`max_hold_bars=10` una posición cierra exactamente en `t_exit == HOLDOUT_INI`.

Es una **colisión de borde**, no un defecto del motor ni de la palanca. La guarda de holdout hace
justo lo que debe: impedir que una corrida toque el periodo reservado. El time-stop, al forzar
cierres en instantes que la salida natural no producía, empuja alguno contra ese borde.

**Es la pérdida más cara de la ola.** P-02 era, junto con P-08, una de las dos palancas de mayor
valor esperado del bloque de salidas, y S6 hoy **no tiene ningún límite temporal**: una posición
puede quedarse abierta indefinidamente. Sigue sin medirse.

Requiere decisión de diseño; hay tres opciones en `OLA1-EXEC-reporte.md`. Ninguna es obvia y por eso
no la tomo aquí.

---

## 5 · Reserva transversal que afecta a toda cifra absoluta

**Las magnitudes de `net_lote1` no son creíbles como dólares.** Un neto de 61.425.035 sobre 153
posiciones de XAUUSD con lote 1 está tres órdenes de magnitud fuera de lo plausible. La hipótesis
más probable es que la unidad sea **pesos chilenos** —el programa ya calcula el neto en dólares y en
pesos por separado, con tasa implícita 908–940— lo que dejaría el neto en unos 65.000 USD, cifra
razonable.

Sea cual sea la causa, **ninguna cifra absoluta de este documento debe citarse hasta confirmar la
unidad**. No afecta a P-08: una comparación pareada es una resta, y la unidad se cancela. Sí afecta
a cualquier lectura del neto de P-05.

Se suma a la reserva ya conocida: el simulador tenía 17,6 % de divergencia contra la realidad, hoy
**3,28 %** tras aplicar el coste de deslizamiento de D-54, todavía sobre el umbral de 0,3 %.

---

## 6 · Lectura de conjunto

### Lo que la ola entrega

**Un resultado firme y uno modesto, de cuatro palancas.**

- **P-08 refutada con evidencia fuerte.** Ensanchar el stop de SuperTrend cuesta dinero linealmente.
- **P-05 sin ganador.** El 3,0 heredado está dentro de una meseta; nada lo supera; solo los valores
  muy anchos son claramente peores. Deja de ser prioridad tocarlo.
- **P-03 no evaluable** por defecto de instrumento, no por ausencia de efecto.
- **P-02 no corrió.**

### La extrapolación no obvia, y es la más valiosa

La linealidad de P-08 dice más que el propio veredicto de P-08.

Si ensanchar el stop solo retrasara salidas de forma aleatoria, la respuesta sería ruidosa o en
forma de U: unas veces el colchón salva la posición, otras la empeora. Lo que se mide es un **coste
casi exactamente proporcional a la distancia añadida, con intervalos estrechos**. Eso significa que
la distancia extra **se paga casi siempre** — es decir, que **las posiciones que tocan la línea de
SuperTrend siguen yendo en contra en vez de recuperarse.**

Ese es un enunciado sobre el comportamiento del precio, no sobre el parámetro. Y si se sostiene,
tiene tres consecuencias que van mucho más allá de esta palanca:

1. **Toda la familia de «darle más aire» queda bajo sospecha** — stops más anchos, colchones,
   tolerancias. La evidencia apunta a que en este instrumento y esta temporalidad, dar aire es pagar.
2. **La familia opuesta gana prioridad**: salir antes, o no entrar. Refuerza P-02 (time-stop) —
   justo la que no corrió— y el bloque de régimen (no operar en lateral).
3. **Predicción falsable para P-04**, la palanca de stop condicionado a la recuperación histórica
   desde una excursión adversa: si esta lectura es correcta, P-04 debería encontrar **tasas de
   recuperación bajas** desde excursiones profundas en SuperTrend. Si las encuentra altas, esta
   lectura está mal y hay que revisarla. Vale la pena medirlo precisamente porque puede refutarme.

### Lo que la ola NO sostiene

- Ninguna cifra absoluta de dinero, ni en P-05 ni en P-08, hasta confirmar la unidad.
- Ninguna comparación S6 contra SuperTrend.
- Nada sobre P-03 ni sobre P-02.
- Nada sobre el multiplicador «óptimo». **El máximo de la grilla de P-05 es 4,75 y es ruido**; quien
  lo tomase estaría sobreajustando a n=77.

### Qué merece seguir, por orden

1. **Diagnóstico de P-03** — contar activaciones de la condición de AC en el sustrato. Barato,
   y desbloquea 95 brazos ya construidos o los declara no medibles.
2. **Decidir la colisión de holdout y correr P-02** — la palanca de mayor valor esperado que sigue
   sin medir, y la que la lectura de P-08 refuerza.
3. **Confirmar la unidad de `net_lote1`** — trivial, y sin ella no se cita ninguna cifra.
4. **P-04 como prueba de la extrapolación** — mide la tasa de recuperación desde excursión adversa,
   y puede refutar la lectura del punto anterior.
5. **P-05 se archiva** hasta tener el motor congelado. No hay señal que perseguir.
