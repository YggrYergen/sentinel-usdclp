# Cola de re-validación sobre backtest largo

**Fecha de apertura: 2026-07-27**
**Estado: ABIERTA — acumulativa.**

## Qué es esto

Todo el análisis reciente (curva de espera post-apertura, máscaras B1-B6,
auditoría de solapes, etc.) se ha corrido sobre el mismo substrato de
backtest real-tick: **7 meses**, 2.347 posiciones repartidas en tres
estrategias — S6-K2P0 (912), S7-TPNONE (1167) y SuperTrend-p14x3-M15 (268).
Siete meses alcanzan para *detectar* un efecto, pero no para *confirmarlo*:
varios de los hallazgos recientes conviven con la sospecha de ser ruido, de
estar dominados por un puñado de operaciones grandes, o de ser artefactos de
haber buscado el "mejor punto" en los mismos datos que se usan para medirlo
(in-sample por construcción).

Esta cola existe para no perder esas preguntas ni correrlas a destiempo:
cada vez que un hallazgo sobre el periodo corto merezca confirmarse sobre un
periodo largo, se anota aquí una entrada. Cuando exista el backtest largo
(v2, o la continuación que corresponda), esta cola es la lista de qué
preguntarle y cómo se decide.

## Qué NO es esta cola

- **No es un plan de ejecución.** No define cronograma, no asigna implementador,
  no dice "hacer esto ahora".
- **No autoriza a correr nada.** Ninguna entrada aquí habilita, por sí sola, un
  backtest largo ni un cambio de configuración.
- **No es un veredicto ni una recomendación de despliegue.** Es un registro de
  preguntas pendientes con su criterio de decisión ya pactado, para que la
  respuesta no dependa de quién la corra ni de cuándo.

## Formato obligatorio de cada entrada

Cada entrada debe tener, explícitamente, estos cuatro campos:

- **Pregunta** — qué se quiere saber, en una frase verificable.
- **Por qué necesita periodo largo** — qué es lo que 7 meses no pueden
  resolver (ruido, dominancia de outliers, in-sample, n insuficiente, etc.).
- **Métrica de decisión** — con qué número y qué umbral se contesta la
  pregunta cuando exista el dato largo.
- **De qué hallazgo corto viene** — referencia al commit, fichero o doc donde
  se originó, marcando si ese hallazgo es in-sample.

---

## Entrada 1 — La curva de espera post-apertura, desagregada por estrategia

**Pregunta.** ¿Debe la espera post-reapertura (la puerta que bloquea entradas
durante las primeras N barras M15 tras cada reapertura de mercado) ser **una
sola para las tres estrategias**, o **una espera distinta por estrategia**?

**Por qué necesita periodo largo.** Desagregado por estrategia, S6-K2P0 y
SuperTrend-p14x3-M15 son positivas en **todos** los peldaños probados (N2 a
N6), mientras que S7-TPNONE cambia de signo **tres veces** y se desploma a
**−93,28%** en N6. Esa sola estrategia explica casi toda la inestabilidad del
combinado. Con 1.167 posiciones (S7) y menos aún por peldaño tras bloquear,
no se puede distinguir si ese comportamiento es una característica real de
S7 o ruido de muestra pequeña.

**Métrica de decisión.** Repetir la desagregación por estrategia sobre
periodo largo y comprobar si S7-TPNONE sigue cambiando de signo con la misma
magnitud. Si el patrón se mantiene (S6/ST estables y positivas, S7
inestable), eso apoya una espera diferenciada por estrategia; si desaparece,
apoya mantener una espera única.

**De qué hallazgo corto viene.** Commit `c402976` ("feat(analysis): Task 16
-- B1 wait-window curve, N=2..6 M15 bars"), artefacto
`data/analysis/monday_audit/b1_wait_window.json`, doc
`docs/superpowers/research/2026-07-27-b1-wait-curve.md`. Deltas de neto
combinado: N2 (30 min) +13,27%, N3 (45 min) +32,67%, N4 (60 min) +20,01%, N5
(75 min) +9,72%, N6 (90 min) −15,24%. **In-sample** (7 meses, mismo dato que
la curva). Decisión del usuario: no resolver esto sobre 7 meses; mientras
tanto se generaliza **N3 (45 min)** de forma preliminar.

---

## Entrada 2 — Re-validar la propia curva N=2..6

**Pregunta.** ¿Se sostiene el ranking de peldaños N3 > N4 > N2 > N5 > N6
sobre periodo largo, y aparece una meseta o codo que hoy no existe?

**Por qué necesita periodo largo.** La diferencia entre N3 (+32,67%) y N4
(+20,01%) puede ser ruido de muestra. El ranking fue construido buscando el
mejor punto en los mismos datos con los que se mide (in-sample por
construcción, declarado explícitamente así en el doc de origen). Hoy la
curva no tiene ni codo limpio ni meseta: es una joroba que sube de N2 a un
pico en N3 y cae hasta cambiar de signo en N6.

**Métrica de decisión.** Repetir la curva N=2..6 sobre periodo largo y
comparar la forma: (a) ¿se mantiene el orden N3 > N4 > N2 > N5 > N6?, (b)
¿aparece un tramo estable (meseta) en vez de la joroba con cambio de signo
actual?, (c) ¿el pico se sigue ubicando en N3 o se desplaza?

**De qué hallazgo corto viene.** Mismo origen que la Entrada 1: commit
`c402976`, `data/analysis/monday_audit/b1_wait_window.json`,
`docs/superpowers/research/2026-07-27-b1-wait-curve.md`. **In-sample**,
declarado como tal en el propio documento de origen ("esto es tunear").

---

## Entrada 3 — La escalera de distancia de SL (Task 15)

**Pregunta.** ¿Se sostiene sobre periodo largo cualquier peldaño de la
escalera de distancias de stop-loss que se especifique bajo Task 15?

**Por qué necesita periodo largo.** Task 15 está definida (ver
`docs/superpowers/plans/2026-07-25-monday-tracker.md`, líneas donde se
distingue de B4: "la escalera de distancias de SL que el user quiere probar
no es B4: es una mutación de la estrategia y vive en la nueva Task 15,
backtest primero, sin desplegar nada hasta discutir resultados") para
correrse sobre el mismo substrato de 7 meses que el resto de este análisis,
con el mismo riesgo de sobreajuste que las Entradas 1 y 2.

**Métrica de decisión.** Pendiente de que Task 15 se ejecute y arroje un
resultado sobre 7 meses; en ese momento, esta entrada pasa a pedir la
repetición de esa métrica de decisión (aún no definida en el material
disponible) sobre periodo largo, antes de que cualquier peldaño se
considere adoptable.

**De qué hallazgo corto viene.** `docs/superpowers/plans/2026-07-25-monday-tracker.md`
(definición de Task 15). **Nota de dato faltante:** al momento de escribir
esta entrada no existe todavía script ni artefacto de resultados de Task 15
en `scripts/analysis/monday_audit/` ni en `data/analysis/monday_audit/` — la
tarea está definida pero, según lo que pude verificar en el repo, aún no
corrida. Cuando exista el hallazgo corto de Task 15, esta entrada debe
actualizarse con su commit/fichero de referencia y sus cifras concretas.

---

## Entrada 4 — La hipótesis de la "lotería": ¿el filtro selecciona o baraja?

**Es la entrada más importante de la cola. Es una hipótesis, no está
medida.**

**Pregunta.** Cuando la espera post-apertura (o cualquier filtro temporal
similar) bloquea una entrada, ¿está descartando sistemáticamente
oportunidades peores, o simplemente está reordenando al azar cuál
oportunidad se toma?

**Por qué necesita periodo largo.** Las estrategias sólo pueden tener **una
posición abierta a la vez**, así que se pierden muchas oportunidades
concurrentes. La señal de entrada es **on/off, sin fuerza**: hoy no existe
ningún indicador de calidad ni tooling para puntuar cuán favorable es una
entrada frente a otra que se descartó por estar la posición ya ocupada o por
caer dentro de la ventana bloqueada. Consecuencia hipotética: cuál
oportunidad se toma depende en buena parte del azar de cuál llegó primero,
no de cuál era mejor. Si las entradas no están ordenadas por calidad,
filtrar por tiempo estaría descartando oportunidades casi al azar, y una
mejora de +32,67% en el neto (ver Entrada 1/2) podría ser tanto "evitamos las
malas" como "tuvimos suerte con cuáles quedaron" — lo que explicaría el
cambio de signo entre peldaños. Distinguir "selecciona" de "baraja" con
confianza no es algo que 7 meses y 2.347 posiciones (con sub-muestras aún
más chicas por estrategia y por peldaño) puedan resolver: se necesita mucho
más n para separar señal de ruido de muestreo en una hipótesis sobre el
orden de llegada de oportunidades raras.

**Métrica de decisión.** Aún no especificada. El camino natural, si se
decide seguirlo: construir una noción de *strength* de señal (hoy
inexistente) y medir si las entradas descartadas por la espera eran
sistemáticamente peores en esa medida de fuerza, o simplemente distintas sin
patrón de calidad. Sobre periodo largo, la pregunta operativa sería si esa
diferencia (peores vs. distintas) se sostiene con suficiente potencia
estadística.

**De qué hallazgo corto viene.** Deriva de la inestabilidad observada en la
Entrada 1 (commit `c402976`,
`docs/superpowers/research/2026-07-27-b1-wait-curve.md`), pero **no está
medida como tal todavía**: es una hipótesis explicativa formulada por el
usuario, no un resultado de ningún script. Nota: una primera aproximación
in-sample sobre 7 meses (perfil distribucional de lo vetado frente a lo
conservado) se está construyendo por separado, en paralelo a este documento.
Distinguir selección de barajado con confianza requiere periodo largo.

---

## Entrada 5 — Re-correr la prueba de robustez de la métrica sobre periodo largo

**Pregunta.** ¿Sobrevive la mejora de neto observada (p. ej. la de la
Entrada 1/2) una prueba de robustez — consistencia de signo mes a mes y
sensibilidad a quitar las operaciones más grandes — cuando se corre sobre
periodo largo?

**Por qué necesita periodo largo.** Decisión del usuario de esta sesión: la
métrica que gobierna la decisión es el **NETO**, pero sólo si la mejora
**sobrevive una prueba de robustez** y **sin cerrar la puerta a lo que
enseñen los backtests más largos** (v2 o continuación de este plan). Motivo
concreto: en la curva actual el **win rate se mueve menos de 1 punto
(34,41%–35,35%)** entre peldaños mientras el **neto barre 48 puntos
porcentuales** (de −15,24% a +32,67%), y las dos métricas **rankean
distinto** — el mejor WR es N5 (35,35%), el mejor neto es N3 (+32,67%). Con
WR ~34% y PF ~1,14 (baseline: WR 34,43%, PF 1,138), eso apunta a que todo se
juega en la cola de la distribución (pocas operaciones grandes deciden el
neto), justo el tipo de resultado que una prueba de robustez sobre 7 meses
no puede confirmar por sí sola: es in-sample por construcción y con pocos
meses no hay suficiente variación mes a mes para separar una mejora
estructural de un puñado de operaciones favorables.

**Métrica de decisión.** Repetir sobre periodo largo la misma prueba de
robustez pactada: (a) consistencia de signo mes a mes de la mejora de neto,
(b) sensibilidad del resultado a excluir las N operaciones más grandes. Si
ambas se sostienen sobre periodo largo, la mejora de neto se considera
robusta; si el signo se invierte mes a mes o el resultado depende de pocas
operaciones grandes, no se considera robusta aunque el neto agregado corto
sea positivo.

**De qué hallazgo corto viene.** Cifras de WR/PF/neto de
`data/analysis/monday_audit/b1_wait_window.json` (commit `c402976`,
doc `docs/superpowers/research/2026-07-27-b1-wait-curve.md`). **In-sample**.
La prueba de robustez sobre 7 meses en sí misma es in-sample por
construcción; esta entrada pide su repetición sobre periodo largo. **Nota de
dato faltante:** no encontré en el repo, al momento de escribir esta
entrada, un artefacto o script que ya haya corrido la prueba de robustez
(consistencia mes a mes / sensibilidad a operaciones grandes) sobre el
periodo corto — si existe, debe añadirse aquí como referencia cuando se
localice; si no existe todavía, esta entrada aplica igual una vez que se
corra, tanto en corto como en largo.

**Actualización 2026-07-27 (mismo día):** la prueba corta ya corrió — commit
`059a5a2`, `scripts/analysis/monday_audit/b1_robustness.py`, artefacto
`data/analysis/monday_audit/b1_robustness.json`, doc
`docs/superpowers/research/2026-07-27-b1-robustness.md`. Resultado corto,
in-sample: (a) la mejora de neto **no sobrevive** la consistencia mensual —
sin 2026-02, los cinco peldaños N2..N6 quedan en negativo; (b) el *ranking*
N3 > N4 > N2 > N5 **sí sobrevive** el recorte top-K global (K=1..10); (c) lo
vetado es peor que lo conservado en mediana/WR/PF en N2–N5, y se invierte en
N6. La repetición sobre periodo largo que pide esta entrada sigue pendiente.

---

## Entrada 6 — Concentración del neto en un puñado de operaciones (riesgo de primer orden)

**Pregunta.** ¿Es estructural que una fracción minúscula de las operaciones
sostenga casi todo el resultado — y que su ausencia lo vuelva negativo — o es
un artefacto del periodo corto?

**Por qué necesita periodo largo.** Sobre los 7 meses: una sola operación
(SuperTrend, 2026-01-29 22:15, +23,69 MM) es el 16% del neto total; las 10
mayores por |net| (0,43% de 2.347) sostienen el 72%; quitando las 10 mayores
de cada estrategia (30 operaciones, 1,28%) el baseline completo se vuelve
**−49,6 MM**. Con colas así de pesadas, 7 meses no alcanzan para estimar la
frecuencia real de los grandes ganadores ni la probabilidad de atravesar un
periodo sin ninguno — que es el escenario de riesgo que importa.

**Métrica de decisión.** Sobre periodo largo: (a) fracción del neto aportada
por el top 0,5% y el top 1% de operaciones por |net|, por año; (b) neto tras
recorte top-K, por año; (c) frecuencia de ganadores por encima de un umbral
(p. ej. > 5 MM a 0,67 lot) por semestre. Si la concentración se mantiene, el
riesgo es estructural y toda decisión de despliegue debe dimensionarse contra
el escenario "sin cola", no contra el neto agregado.

**De qué hallazgo corto viene.** Commit `059a5a2` (medición M2 de
`data/analysis/monday_audit/b1_robustness.json`, doc
`docs/superpowers/research/2026-07-27-b1-robustness.md`). **In-sample.**
Decisión del usuario 2026-07-27: es un riesgo de primer orden; requiere
generar alternativas / estrategias en profundidad que ayuden a subsanarlo,
sin sacrificar los grandes payouts que sostienen la rentabilidad.

---

## Cómo añadir una entrada nueva

1. Usa el mismo formato de cuatro campos: **Pregunta**, **Por qué necesita
   periodo largo**, **Métrica de decisión**, **De qué hallazgo corto viene**.
2. Numera la entrada de forma consecutiva al final de la lista existente —
   no reordenes ni renumeres las entradas anteriores.
3. En "De qué hallazgo corto viene", cita commit y/o ruta de fichero exacta.
   Si el hallazgo de origen es in-sample (la inmensa mayoría de lo producido
   sobre el substrato de 7 meses lo es), dilo explícitamente.
4. Si necesitas una cifra o fecha que no tengas a mano, no la inventes:
   escribe la entrada igual y marca el dato como faltante, indicando dónde
   se debería buscar o quién lo tiene.
5. No conviertas ninguna entrada en un plan de ejecución ni le asignes
   fecha de corrida: eso vive en otro documento (un plan o el tracker), no
   aquí. Esta cola solo registra qué preguntar y cómo se decide.
6. No borres ni cierres entradas al añadir una nueva: si una entrada se
   resuelve, se anota su resultado dentro de la misma entrada (no se
   elimina), para conservar la trazabilidad de qué se preguntó y qué se
   contestó.
