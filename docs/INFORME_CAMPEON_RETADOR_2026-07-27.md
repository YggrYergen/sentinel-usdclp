# INFORME — Campeón / Retador

**Fecha:** 2026-07-27 · **Cuenta:** DEMO 2883015767 (59.600.000 CLP) · **Instrumento:** XAUUSD
**Rama:** `equipo1` · **Reloj:** todas las horas y fechas son **hora de servidor del broker (UTC−4)**
**Convención numérica:** punto de miles, coma decimal (39.513.979 CLP · PF 1,033)

> **Regla que gobierna este documento:** cada cifra está copiada de un artefacto en disco. Ninguna
> está escrita de memoria ni estimada. Al final, el **Anexo A** lista el artefacto exacto del que
> sale cada bloque de números. Donde nadie calculó un número, este documento dice **NO DISPONIBLE**
> en lugar de estimarlo; donde el dato no permite concluir, dice **NO EVALUABLE** en lugar de
> insinuar una conclusión.

---

## 0. Resumen ejecutivo

Cinco cosas, en orden de importancia:

1. **El neto reconstruido de 7 meses es 39.513.979 CLP**, con **profit factor 1,033** y win rate
   **32,26 %** sobre **2.542** posiciones (0,67 lote/ficha, gate de spread 0,5). La cifra anterior
   de **147.780.084 CLP no era el resultado del sistema**: era el resultado de una medición a la que
   le faltaba una población entera de cierres.

2. **Ninguna operación que ya mostrábamos cambió de resultado.** Las 2.347 posiciones del backtest
   anterior conservan su resultado **idéntico al céntimo** — 0 re-atribuidas, 0 desaparecidas. Lo que
   cambió es que **ahora contamos todas las operaciones que la cuenta real ejecuta**: 195 cierres por
   *stop-and-reverse* que siempre ocurrieron en el vivo y que el instrumento descartaba por un error
   de emparejamiento.

3. **El titular honesto no es el neto, es el profit factor: 1,138 → 1,033.** Un PF de 1,03 sobre
   2.542 operaciones describe un sistema apenas del lado correcto de cero. Y la jerarquía entre
   estrategias se invierte: **SuperTrend, con 268 posiciones, aporta el 53 % del neto**; S7-TPNONE
   queda en **670.122 CLP** en 7 meses (PF 1,0013), un empate técnico con cero.

4. 🔴 **Lo más grave: bastan TRES operaciones para volver negativos los 7 meses.** Quitando las tres
   mayores por magnitud, el neto pasa de +39.513.979 a **−7.557.696 CLP**. Bajo la métrica D170
   (neto + consistencia mensual + recorte top-K), **el track NO supera el criterio de recorte
   top-K**. Esto no es un matiz: es el hallazgo que condiciona todo lo demás.

5. **39,5 MM es la mejor cifra disponible, no una cifra cerrada.** El gate de spread 0,5 —que espeja
   el vivo a propósito— deja fuera del libro **549 cierres `reverse`** adicionales. La dirección del
   sesgo residual **no es determinable** con los artefactos que existen hoy.

**Estado de la entrega:** el código del retador está escrito, probado y commiteado; el **arranque en
la máquina 1 todavía NO ha ocurrido** — es una acción manual del user (ver §3.3 y §11).

---

## 1. El número principal y cómo debe leerse

### 1.1 La cifra

| Métrica (7 meses, 0,67 lote/ficha, gate 0,5) | Valor |
|---|---:|
| Neto combinado | **39.513.978,56 CLP** |
| Operaciones | **2.542** |
| Win rate | **32,26 %** |
| Profit factor | **1,0333** |
| Máximo drawdown (grilla mensual, @0,67) | 129.150.945 CLP |

*Fuente: `data/analysis/monday_audit/a5_spread_gate.json` (`COMBINED.at_0.5`) y
`docs/REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md` §1–2.*

### 1.2 Qué pasó con los 147,8 MM

La cifra de **147.780.084,05 CLP** que estuvo a punto de emitirse **nunca fue el resultado del
sistema**. Era el resultado de un sistema que no pagaba sus reversiones.

El motor de S6 y S7 lleva un mecanismo de *stop-and-reverse*: cuando la señal se da vuelta, cierra
la posición y abre la contraria. Ese mecanismo **está activo en la cuenta real y se dispara**. El
emparejador del backtest (`run_ladder`, en `scripts/analysis/realtick_bt/backtest.py`) no reconocía
el evento `reverse` como un cierre, así que la pierna que se cerraba **desaparecía entera y en
silencio** del libro reconstruido.

La prueba de que esto es un cambio de instrumento y no un cambio de sistema es aritmética y no
admite lectura alternativa:

| Población | n | Suma CLP | Media CLP |
|---|---:|---:|---:|
| Filas que el backtest ya mostraba | **2.347** | **147.780.084,05** | +62.965,52 |
| Filas nuevas (100 % `reason="reverse"`) | **195** | **−108.266.105,49** | −555.210,80 |
| **Total del libro reparado** | **2.542** | **39.513.978,56** | +15.544,44 |

De las 2.347 filas viejas: **367 idénticas** en los cinco campos, **1.980 solo re-etiquetadas**
(mismo `net`, distinto texto de motivo), **0 re-atribuidas** y **0 desaparecidas**. Su suma en el
substrato nuevo es 147.780.084,05 CLP — el neto viejo completo, **al céntimo**.

*Fuente: `2026-07-27-substrate-repair-diff.md` §11 (R3) y suma directa sobre
`data/analysis/realtick_bt/positions_*.csv`, re-verificada de forma independiente al escribir este
documento.*

### 1.3 Las dos lecturas que hay que sostener a la vez

Este es el punto donde equivocarse en cualquiera de las dos direcciones sería el peor resultado de
todo el trabajo. Las dos afirmaciones siguientes son ambas ciertas y ninguna cancela a la otra:

- **Las estrategias no empeoraron.** No se corrigió un cálculo, no se re-valoró una operación, no se
  movió un fill. Nada de lo que la cuenta hizo entre el viernes y el lunes cambió. **Ninguna
  operación que ya mostrábamos cambió de resultado.**
- **Y sin embargo, el edge real del track es mucho menor de lo que creíamos.** El PF está en 1,033,
  no en 1,138. Presentar esto como un tecnicismo contable sin consecuencias sería tan falso como
  presentarlo como un derrumbe del sistema. **La consecuencia es real: durante meses medimos un
  sistema que no pagaba sus reversiones.**

### 1.4 El reparto entre estrategias se rompe

| Estrategia | n | Neto CLP | PF | WR % | % del neto |
|---|---:|---:|---:|---:|---:|
| SuperTrend-p14x3-M15 | 268 | **20.983.977,53** | 1,1425 | 22,76 | **53 %** |
| S6-K2P0 | 1.053 | 17.859.879,00 | 1,0334 | 32,48 | 45 % |
| S7-TPNONE | 1.221 | **670.122,03** | **1,0013** | 34,15 | 2 % |
| **COMBINADO** | **2.542** | **39.513.978,56** | **1,0333** | **32,26** | 100 % |

*Fuente: `a5_spread_gate.json`. Los porcentajes son el cociente de la columna de neto sobre el total.*

Tres lecturas obligatorias:

- **SuperTrend queda intacto** (Δ = 0,00 CLP): no tiene *stop-and-reverse*, así que el error no lo
  tocaba. Es el control interno más limpio que tiene esta reparación.
- **SuperTrend pasa a ser la estrategia que más neto aporta** — con 268 posiciones frente a 2.274 de
  S6+S7. Eso invierte la jerarquía implícita en toda la narrativa anterior.
- **S7-TPNONE queda en 670.122 CLP en 7 meses, con PF 1,0013.** No es "poco rentable": es
  indistinguible de cero con esta muestra.

La diferencia entre las dos mediciones se concentra **donde el instrumento estaba ciego**, no donde
el sistema opera mal: el neto declarado de S7 se reduce en un **98 %** al contabilizar solo 54 filas
nuevas, y el de S6 en un **81 %** con 141. Lo que esto revela no es "S6 y S7 son malas", es que **su
neto declarado dependía de no contabilizar sus reversiones**.

---

## 2. 🔴 Lo más grave: el neto no sobrevive a quitar tres operaciones

Este es el hallazgo que más pesa sobre cualquier decisión que se tome con estos números, y va aquí,
no en un anexo.

### 2.1 Recorte de las mayores del libro (por magnitud de resultado)

| Operaciones retiradas | Neto restante (CLP) |
|---:|---:|
| 0 (libro completo) | **+39.513.978,56** |
| **1** (la mayor) | +15.822.532,67 |
| **3** | **−7.557.695,53** |
| 5 | −26.020.558,91 |
| 10 | −66.525.916,46 |

*Fuente: `data/analysis/monday_audit/b1_robustness.json`,
`m2_topk_sensitivity.global.K{1,3,5,10}.curve.COMBINED.baseline`.*

**La operación mayor del libro vale 23.691.445,89 CLP — el 60 % del neto de 7 meses ella sola.** Con
tres, el track queda en negativo. Tres operaciones son el **0,12 %** de la muestra.

### 2.2 Recorte por estrategia (la vista de la que salió el enunciado original)

| K por estrategia | Operaciones retiradas | Neto restante (CLP) |
|---:|---:|---:|
| 1 | **3** (una de cada estrategia) | **+1.052.241,96** |
| 3 | 9 | −51.868.567,66 |
| 5 | 15 | −73.491.294,43 |
| 10 | 30 | **−157.907.835,26** |

*Fuente: `b1_robustness.json`, `m2_topk_sensitivity.by_group.K{k}.curve.COMBINED.baseline`.*

Quitando **una sola operación de cada estrategia** —tres en total— los 7 meses quedan en
**1.052.242 CLP**, es decir el **2,7 %** del neto declarado.

### 2.3 Por qué la concentración medida es peor ahora, y qué significa exactamente

Un detalle que evita la mala lectura: **las sumas de las mayores operaciones son idénticas al
céntimo en el substrato viejo y en el nuevo** (la mayor: 23.691.445,89; las tres mayores:
47.071.674,09; las diez mayores: 106.039.895,02). La mayor de las 195 filas nuevas vale 1.734.285,62
CLP, y la décima mayor del libro entero vale 8.013.227,81 — **ninguna fila nueva entra en la cola**.

Es decir: **la reparación no tocó la cola grande del libro. Lo que se encogió fue el cuerpo.** Las
mismas operaciones que dominaban el libro antes lo dominan ahora; lo que cambió es que el resto del
libro ya no las compensa. Antes había que quitar 30 operaciones para volver el track negativo; ahora
bastan tres.

Nota metodológica: el recorte es por **magnitud absoluta** del resultado, así que retira
indistintamente ganadoras y perdedoras. Que el neto caiga al recortar significa que las mayores por
magnitud son ganadoras netas — no que se hayan eliminado a propósito solo las buenas.

### 2.4 El veredicto que sigue de esto

**Bajo la métrica D170 —neto, consistencia mensual y recorte top-K— este track NO supera el criterio
de recorte top-K.** Un resultado positivo que depende de 3 operaciones de 2.542 no es un edge
demostrado sobre estos 7 meses: es un resultado dominado por su cola. Esto debe pesar más que el
signo del neto en cualquier decisión de tamaño o de despliegue.

---

## 3. Qué se entrega

### 3.1 El experimento

Campeón y retador corriendo **en paralelo, en una sola cuenta y un solo proceso**, sobre las **mismas
tres señales**:

| | Campeón (sleeve A) | Retador (sleeve B) |
|---|---|---|
| Configs | `S6-K2P0`, `S7-TPNONE`, `SuperTrend-p14x3-M15` | los mismos con sufijo `-R` |
| Magics | banda vigente (724xxx) | **banda fresca 726010 / 726020 / 726070** |
| Lote | 0,1 | **0,1 (paridad de tamaño)** |
| Capa de riesgo | ninguna (ruta de código idéntica a hoy) | **B1–B4 activas en el OPEN** |
| Señal / parámetros | intactos | **byte-idénticos al campeón** |

*Fuente: `sentinel_engine/strategies/live_configs_20.py`, bloque `CONFIGS_CHALLENGER`
(commit `36979a3`, lote corregido a 0,1 el 2026-07-26).*

El retador es una **copia profunda independiente** de cada config del campeón: nunca un alias. Hay
asertos en tiempo de importación que fallan —y con ellos el arranque del executor— si esa disciplina
de copia se rompiera, si la banda de magics se solapara con cualquier otra, o si el campeón ganara
por accidente las claves `risk_gates` o `volume` del retador.

TK-Momentum **no** se espeja deliberadamente: sigue en desarrollo a 0,01 y no forma parte del track
que se compara. Son **tres** configs, no cuatro.

### 3.2 Por qué la paridad de lote

El retador nació a 0,02 y el user lo corrigió a **0,1 el 2026-07-26**: con el mismo tamaño, el A/B es
directamente comparable en vez de tener que normalizarse por operación. La contrapartida, aceptada
explícitamente por el user, es que **duplica la exposición de la cuenta**.

### 3.3 Lo que todavía NO ha ocurrido

🔴 **El retador no está corriendo.** El código está commiteado y probado; el arranque —cambiar el
roster del supervisor a `local+challenger` y reiniciarlo— es una **acción manual del user**, y no se
ha ejecutado. Todo lo que este documento afirma sobre el retador es sobre **código verificado en
tests**, no sobre comportamiento observado en la cuenta.

Del criterio de aceptación de la entrega:

| Criterio | Estado |
|---|---|
| Sleeve A corriendo, idéntico a hoy | ✅ intacto (no se tocó ningún config del campeón) |
| Sleeve B corriendo a 0,1 con B1–B4 en la banda 726xxx | ⏳ **pendiente — arranque manual del user** |
| Máscara retrospectiva corrida y veredicto registrado, sin usarla para seleccionar | ✅ §5 |
| Tag de git + revert de un paso probado | ✅ §12 |
| Pista A completa, con el maxDD confirmado o corregido | ✅ **corregido** (§6.1) |
| Documento entregado | 🔵 este documento — *emitido, pendiente de revisión del user* |
| Pista C (entrada aleatoria) | ⏳ no bloquea; no corrida |

---

## 4. Qué NO se tocó, y por qué

**No se re-optimizó ni un parámetro.** Ni un barrido, ni un "probé este y va mejor". Las tres señales
del retador llevan los `kwargs` del campeón, byte por byte, y hay un test que lo verifica.

Conviene decir por qué, porque la tentación estaba disponible y era la opción fácil de este fin de
semana. Re-optimizar los parámetros ahora habría sido **exactamente el error que produjo un DSR≈0
sobre 225 trials** en la ronda anterior: buscar en un espacio grande sobre un solo tramo de historia
y quedarse con el mejor resultado del ruido. La infraestructura que haría legítima una
re-optimización —la confirmación de las magnitudes contra el motor MT5 real-tick, la Fase 0, el
walk-forward/holdout— **todavía no existe**. Mientras no exista, cualquier número "mejorado" sería un
número elegido, no un número medido.

Por el mismo motivo, los cuatro parámetros de la capa de riesgo se fijaron **antes** de mirar
cualquier resultado retrospectivo (§5), y **las máscaras de este documento vetan, nunca
seleccionan**: sirven para responder "¿esta puerta habría sido catastrófica?", no para elegir la
mejor puerta.

Tampoco se tocó, en toda esta cadena de trabajo: ningún `.py` del motor vivo, ningún config del
campeón, y —tras la reparación del substrato— **ningún valor del roster retador**, porque el único
número del roster que dependía de la auditoría (el cap B3 = 7) **no se movió**.

---

## 5. La capa de riesgo (B1–B4) y sus veredictos de máscara

Cuatro puertas, evaluadas en orden fijo, que solo se ejecutan en la ruta de apertura de un config que
lleve `risk_gates` — es decir, solo del retador. Un config sin esa clave toma la ruta de código
idéntica a la de hoy.

Junto a cada una va su **veredicto de máscara retrospectiva**: qué habría pasado si esa puerta
hubiera estado activa sobre los 7 meses reconstruidos. Se incluyen **las dos que no son evaluables**.

### 5.1 B1 — espera tras la apertura de mercado · **NO VETO**

**Qué hace:** bloquea aperturas durante los primeros **50 minutos** desde que el spread baja a 0,5
tras una interrupción de sesión (≥60 min sin barras). **De dónde sale el 50:** de un diagnóstico
previo de las velas contaminadas por el hueco de apertura de XAUUSD — **no** de un barrido corrido
este fin de semana.

**Veredicto retrospectivo:** **NO VETO** — la puerta no habría sido catastrófica. Habría bloqueado
**227** de 2.542 posiciones, dejando 2.315, y el neto de 7 meses habría pasado de **39.513.979 a
80.302.946 CLP**, es decir **+40.788.967 CLP**. Reaperturas de mercado medidas sobre el stream de
barras: **145**.

🔴 **Cómo debe citarse la magnitud.** El artefacto expresa esa mejora como **+103,23 %**, y ese
porcentaje **está inflado por la caída de la base**: el numerador (la mejora en CLP) subió un 38 %
—de 29.577.601 a 40.788.967— mientras el denominador (el neto total) cayó un 73 %. **Cítese en CLP.**
Decir "la puerta pasó de mejorar un 20 % a mejorar un 103 %" sugeriría que la puerta se volvió cinco
veces mejor, y eso es falso.

**Caveat que va pegado al número, del propio artefacto:** el signo de esta mejora **no es estable** en
el parámetro de espera, y los 50 minutos se fijaron de antemano. Esta máscara **evalúa esa elección
fija; no busca una mejor**. La curva completa de esperas alternativas está en el **Anexo C**,
declarada aparte y marcada como in-sample.

### 5.2 B2 — ventana de noticias · **0 descartes, con evidencia parcial**

**Qué hace:** bloquea aperturas dentro de ±**30 minutos** de un evento de calendario. **De dónde sale
el 30:** por convención de la especificación. Elegirlo desde un backtest habría sido re-tunear.

**Veredicto retrospectivo:** **0 descartes** sobre el rango cubierto (2.540 posiciones evaluadas;
2 quedan fuera del rango del calendario). Ninguna de las 2.542 entradas cayó dentro de una ventana de
noticias conocida.

⚠️ **Esto es "sin evidencia", no "sin problema".** El calendario commiteado
(`data/live/news_calendar.csv`, 36 filas, 2026-01-02 a 2028-12-01) cubre **únicamente NFP** (primer
viernes del mes), porque es la única regla derivable sin una fuente externa. **CPI, FOMC y PPI son
irregulares y no están en el calendario**, así que su efecto **no ha sido medido**. La puerta corre
*fail-closed*: si el calendario falta o es ilegible, deniega la apertura.

### 5.3 B3 — tope de fichas simultáneas · **0 descartes, por construcción**

**Qué hace:** impide abrir por encima de **7** fichas simultáneas en el conjunto del retador.
**De dónde sale el 7:** es el **pico observado** de fichas simultáneas en los 7 meses reconstruidos
(`a2_overlap.json`).

**Veredicto retrospectivo:** **0 descartes**. Y aquí hay que ser exactos: como el tope **es** el pico
observado, **nunca podía morder**. El propio artefacto lo dice.

**Por tanto B3 es un fusible, no un control de riesgo validado.** Presentarlo como "control de
exposición demostrado" sería falso. Es exacto llamarlo "tope de seguridad calibrado sobre el peor
solape observado en 7 meses".

🟢 **Dato relevante de la reparación:** tras regenerar el substrato con 195 posiciones más, el
histograma de simultaneidad **subió en todos los bins** (7 fichas simultáneas: 267 → 304 momentos) y
aun así el pico **sigue clavado en 7**. El tope no se salvó por poco: 7 es un techo estructural
(3 configs × hasta 3 fichas). **El roster retador no requirió ningún cambio y no se tocó.**

### 5.4 B4 — distancia mínima de stop · **NO EVALUABLE**

**Qué hace:** rechaza una apertura cuyo stop quede a menos de **0,50** del precio. **De dónde sale el
0,50:** es el mínimo del bróker. Su incumplimiento no es una preferencia: **es un bug**.

**Veredicto retrospectivo: NO EVALUABLE.** Los CSV de posiciones **no llevan columna de SL**, y
reconstruirla exigiría re-simular. Además, B4 no es conceptualmente una máscara: es un **detector de
bug vivo**, no un filtro de operaciones. Va al documento como **"sin evidencia"**, no como "sin
problema".

---

## 6. La auditoría (A1–A5)

### 6.1 A1 — Máximo drawdown · **CORREGIDO**

| Métrica (@0,1 lote sobre cuenta virtual combinada) | Valor |
|---|---:|
| Máximo drawdown | **−19.276.260,47 CLP** |
| Como % del balance inicial (59.600.000 CLP) | **−32,34 %** |
| Como % del pico de equity | −25,07 % |
| Pico de P&L acumulado | 17.281.515,46 CLP · **2026-03-23 05:32:53** |
| Valle de P&L acumulado | −1.994.745,01 CLP · **2026-04-29 01:57:51** |

*Fuente: `data/analysis/monday_audit/a1_maxdd.json`.*

🔴 **La cifra de −28,57 % que circulaba queda muerta, y con ella la frase «confirma la estimación
previa de −28,6 %».** El drawdown real del substrato reparado es **−32,34 % del balance inicial**.

Lo que **sí** sobrevive es el método: la regla de tres que validaba el número viejo sigue validando
el nuevo (129.150.945 × 0,1/0,67 = 19.276.260,45, contra los 19.276.260,47 que emite el artefacto).
A1 nunca estuvo mal calculado — calculaba correctamente sobre un stream al que le faltaban 195
cierres. Y la **ventana** del drawdown no se mueve ni un milisegundo: mismo pico del 23 de marzo,
mismo valle del 29 de abril. Cambió su profundidad, no el episodio.

⚠️ **Sobre el valle negativo, con precisión.** El campo vale −1.994.745,01 CLP, y "equity" aquí es la
**suma acumulada de P&L**, no el saldo de la cuenta. Lo correcto: en el peor momento el track había
devuelto todo lo ganado en los primeros meses **y 1,99 MM más**; en términos de saldo, el pico fueron
76.881.515 CLP y el valle 57.605.255 CLP. **Lo incorrecto, y hay que evitarlo activamente: decir o
insinuar que la cuenta se agotó o se quedó sin margen. No ocurrió.**

### 6.2 A2 — Solape y correlaciones

| Métrica | Valor |
|---|---:|
| Pico de fichas simultáneas (cap B3) | **7** |
| p95 / p99 de simultaneidad | 7 / 7 |
| Días de trading | 163 |
| % del tiempo con alguna posición abierta | 93,29 % |
| Correlación diaria de neto **S6 \| S7** | **+0,767** |
| Correlación diaria de neto **S6 \| SuperTrend** | **+0,356** |
| Correlación diaria de neto **S7 \| SuperTrend** | **+0,153** |

*Fuente: `data/analysis/monday_audit/a2_overlap.json`.*

🔴 **La frase «SuperTrend es casi independiente de ambas» no se usa: no es cierta.** La redacción
correcta es: **S6 y S7 comparten la mayor parte de la misma apuesta direccional (+0,767). SuperTrend
es la única fuente de diversificación real del track, pero es diversificación parcial, no
independencia: +0,356 contra S6 y +0,153 contra S7.**

Y esa frase carga ahora un peso que antes no tenía. Con SuperTrend aportando el **53 % del neto** y
siendo la única pata poco correlacionada, **la diversificación del track descansa sobre 268
posiciones de una sola estrategia**. Es una observación de riesgo, no de correlación.

### 6.3 A3 — Atribución por motivo de salida · **la corrección narrativa nº 1**

| Motivo | n | Neto CLP | Lectura |
|---|---:|---:|---|
| `EXIT_SL_RAISED` (S6+S7) | 1.980 | **+129.102.003,57** | stop ya levantado por trailing/breakeven |
| `EXIT_STLINE` (SuperTrend) | 268 | +20.983.977,53 | motivo único de ST |
| `EXIT_TRAIL` (S6+S7) | 84 | +12.561.021,72 | subida y toque en la misma vela |
| **`reverse` (S6+S7)** | **195** | **−108.266.105,49** | *stop-and-reverse* |
| `EXIT_INITSL` genuino (S6+S7) | **15** | −14.866.918,77 | stop inicial intacto · **WR 0 %** |
| **TOTAL** | **2.542** | **+39.513.978,56** | |

*Fuente: `data/analysis/monday_audit/a3_exit_reason.json` (9 grupos, agregados por motivo aquí).*

**La narrativa correcta cabe en una frase: el track gana con el trailing y pierde con las
reversiones.** El stop inicial genuino se toca en **15 de 2.542 cierres — el 0,6 %**, y con win rate
**0,0 %**, exactamente como debe ser: un stop inicial intacto es una pérdida por definición.

🔴 **Esto sustituye a la versión anterior de la auditoría** («el grueso del libro sale por stop
inicial, y los stops iniciales son rentables»), que inducía a error en sus dos mitades. Las 891 y
1.104 salidas que se contaban como "stop inicial" eran, en el **98,7 %** y el **99,7 %** de los
casos, **stops ya levantados** por el trailing o el breakeven y tocados después. El grupo que "era
rentable" es el del trailing haciendo su trabajo y siendo mal etiquetado. La aritmética cierra al
céntimo contra los buckets viejos (12 + 879 = 891; 3 + 1.101 = 1.104), lo que prueba que esto es una
**partición**, no un recálculo.

### 6.4 La asimetría del *stop-and-reverse*

Merece su propio bloque, porque es el hallazgo de comportamiento más importante de esta entrega.

| Población | n | Media CLP |
|---|---:|---:|
| Operación normal del libro | 2.347 | **+62.965,52** |
| Cierre por reversión | 195 | **−555.210,80** |

**Una reversión pesa 8,8 veces la media de una operación normal, con el signo invertido.** Y no es
una cola de outliers, es un fenómeno estructural: **183 de las 195 pierden** (WR **6,15 %**), la
**mediana** está en **−519.532,74 CLP**, y el profit factor de la población es **0,083** en S6 y
**0,009** en S7 — en S7, por cada peso ganado en reversiones se pierden 115.

La lectura mecánica, comparando medias por motivo, explica el número y evita que se lea como un
misterio:

| Motivo | Media S6 | Media S7 |
|---|---:|---:|
| `EXIT_INITSL` (stop inicial genuino) | −946.045,27 | −1.171.458,49 |
| **`reverse`** | **−537.381,83** | **−601.764,21** |
| `EXIT_SL_RAISED` | +114.939,91 | +25.494,85 |
| `EXIT_TRAIL` | +188.146,86 | +136.665,68 |

La media de una reversión cae **entre el stop-out completo y la salida con stop levantado, más cerca
del primero**. Es exactamente lo que se espera de un mecanismo que cierra cuando la señal se da
vuelta: si la señal se dio vuelta, la posición casi siempre estaba a contramano. **El
*stop-and-reverse* corta la pérdida, no la evita** — y en 7 meses ese corte costó 108,3 MM CLP que el
backtest no mostraba.

⚠️ **Lo que este hallazgo NO autoriza a concluir: que haya que desactivar el *stop-and-reverse*.** Un
mecanismo cuyo trabajo es cortar posiciones perdedoras *tiene* que exhibir una media negativa.
Juzgar su valor exige el contrafactual —qué habrían hecho esas 195 posiciones sin reversión, corriendo
hasta su stop o su trailing— y **ese contrafactual no existe en ningún artefacto**. Es la pregunta
que este resultado empuja a la cabeza de la cola de trabajo, no una conclusión.

### 6.5 A4 — Estructura serial

| Estrategia | n | Autocorr. lag-1 | lag-2 | lag-3 | Racha máx. de pérdidas | Racha máx. de ganancias |
|---|---:|---:|---:|---:|---:|---:|
| S6-K2P0 | 1.053 | **+0,637** | +0,273 | −0,090 | **30** | 15 |
| S7-TPNONE | 1.221 | **+0,654** | +0,309 | −0,037 | **42** | 15 |
| SuperTrend-p14x3-M15 | 268 | −0,063 | −0,002 | +0,089 | 13 | 4 |

*Fuente: `data/analysis/monday_audit/a4_serial.json`.*

S6 y S7 tienen autocorrelación lag-1 positiva y notable que decae a ~0 en lag-3: **los resultados se
agrupan en rachas cortas**, consistente con régimen de mercado. SuperTrend es prácticamente
independiente en serie.

**El número de tolerancia psicológica que hay que conocer es la racha de 42 pérdidas seguidas de
S7** — y la de S6 sube de 27 a 30 con el libro completo, coherente con inyectar 141 pérdidas nuevas.

### 6.6 A5 — El gate de spread 0,5 · **NO EVALUABLE**

| Ámbito | n a spread 0,5 | n a spread 0,6 |
|---|---:|---:|
| COMBINADO | **2.542** | **0** |
| S6-K2P0 / S7-TPNONE / SuperTrend | 1.053 / 1.221 / 268 | 0 / 0 / 0 |

*Fuente: `data/analysis/monday_audit/a5_spread_gate.json`.*

**Veredicto: NO EVALUABLE, y el substrato reparado lo refuerza** — ahora son 195 filas más y siguen
siendo el **100 % a spread 0,5, cero a 0,6**. No hay ni una fila con la que comparar.

⚠️ **Lo que este documento no puede decir: «el gate 0,5 está validado sobre 7 meses».** No lo está.
El filtro sigue validado únicamente por las cinco sesiones en vivo citadas en su momento; esta
auditoría **ni lo corrobora ni lo refuta**. Lo que sí puede decirse: **los 7 meses reconstruidos
ocurren íntegramente a spread 0,5, que es el único régimen en que estas estrategias operan por
diseño.** Y como la decisión del user es operar a 0,5 y solo a 0,5, esa no-evaluabilidad no bloquea
ninguna decisión.

---

## 7. Grilla mensual y validación contra la semana vivida

### 7.1 La grilla mensual reconstruida

| Mes | Ops | Neto CLP | WR % | PF | maxDD CLP | RoM % |
|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | 258 | 66.714.780 | 29,84 | 1,64 | 43.618.789 | 161,34 |
| 2026-02 | 343 | 4.695.873 | 32,07 | 1,02 | 83.442.103 | 11,11 |
| 2026-03 | 324 | 9.263.118 | 33,02 | 1,05 | 61.730.278 | 23,40 |
| 2026-04 | 459 | **−62.778.128** | 27,45 | 0,69 | 114.823.638 | −162,98 |
| 2026-05 | 388 | 39.459.390 | 35,05 | 1,27 | 52.120.177 | 103,05 |
| 2026-06 | 464 | **−22.881.401** | 34,27 | 0,88 | 60.990.508 | −66,83 |
| 2026-07 | 306 | 5.040.346 | 34,31 | 1,05 | 35.481.953 | 14,96 |
| **TOTAL** | **2.542** | **39.513.979** | **32,26** | **1,03** | **129.150.945** | **93,45** |

*Fuente: `docs/REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md` §2, regenerado sobre el substrato
reparado. La versión anterior de esta grilla queda **superada**, no corregida.*

### 7.2 El argumento más limpio de todos: la forma temporal no cambió

**El perfil de signo mensual del libro es idéntico antes y después de la reparación:** los mismos
cinco meses positivos (enero, febrero, marzo, mayo, julio) y los mismos dos negativos (**abril y
junio**), **sin una sola inversión de signo**. Todos los niveles bajan; ninguno cambia de lado.

Es la evidencia más limpia disponible de que **esto fue un cambio de instrumento y no un cambio de
sistema**: si las estrategias hubieran empeorado, el deterioro se habría concentrado en algún tramo.
No lo hace. Las 195 filas nuevas se reparten **36 / 24 / 27 / 24 / 27 / 39 / 18** entre enero y julio,
y su suma mensual reproduce al peso el cambio de cada mes. **Ningún mes explica el fenómeno; es
sistemático.**

Dos apuntes que hay que dar junto a esto:
- **Junio se agrava mucho:** de −3.590.925 a **−22.881.401 CLP**. Deja de ser "un mes plano
  ligeramente negativo" y pasa a ser el segundo peor mes del track.
- **SuperTrend sale idéntico en las 24 celdas de su tabla mensual** (n, neto, WR, PF, maxDD, RoM en
  los 7 meses y el total). La estrategia sin *stop-and-reverse* no se movió ni un peso: es el control
  interno que confirma el mecanismo del error.

### 7.3 Validación contra la semana del informe (2026-07-20 a 07-23, 0,01 lote)

| Estrategia | Backtest ops | Backtest neto CLP | Vivido ops | Vivido neto CLP |
|---|---:|---:|---:|---:|
| S6-K2P0 | 30 | 76.306 | 69 | 114.348 |
| S7-TPNONE | 36 | 12.587 | 42 | 45.776 |
| SuperTrend-p14x3-M15 | 4 | 15.106 | 5 | 122.249 |
| **Combinado** | **70** | **103.998** | **116** | **282.373** |

*Fuente: `REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md` §4.*

**El único ancla que conecta el backtest con la realidad vivida no se movió: Δ = 0 en las 8 celdas
numéricas.** La reparación no rompió la correspondencia entre el backtest y la semana que el user vio
ocurrir.

🔴 **Y hay que decir en la misma frase por qué no se movió, o la afirmación se vuelve una trampa:**
en esa ventana hay **70 posiciones y CERO cierres `reverse`**. La semana de validación no contiene ni
una sola reversión. De ahí se siguen dos cosas, y valen las dos:

- ✅ **A favor:** la semana vivida confirma que el motor de reconstrucción sigue reproduciendo el
  vivo donde puede compararse, y que la reparación no introdujo distorsión ahí.
- ⚠️ **En contra:** esa misma semana **no puede corroborar el hallazgo del *stop-and-reverse***,
  porque no contiene ninguno. **Es un control de no-regresión, no una confirmación de las cifras
  nuevas.**

Y el desfase de siempre sigue vivo: 70 operaciones y +103.998 CLP en backtest contra 116 operaciones
y +282.373 CLP en el track vivo de esa semana. **La brecha sim-vs-live no la cerró esta reparación y
no debe presentarse como cerrada.**

---

## 8. Lo que sigue sin saberse

Esta sección existe porque la regla de la entrega es que **lo no evaluable se declara no evaluable**.
Ninguno de los puntos siguientes es "sin problema": son "sin evidencia".

### 8.1 🔴 Completitud del substrato: 39,5 MM no es una cifra cerrada

De los **6.417** emparejamientos crudos que el motor produce para S6+S7, solo **2.274 (35,4 %)**
llegan al libro: **el gate de spread 0,5 descarta el 64,6 %**. Por motivo:

| Motivo | Crudos | En el libro | Supervivencia |
|---|---:|---:|---:|
| `EXIT_SL_RAISED` | 5.331 | 1.980 | 37,1 % |
| `EXIT_INITSL` | 45 | 15 | 33,3 % |
| `EXIT_TRAIL` | 297 | 84 | 28,3 % |
| **`reverse`** | **744** | **195** | **26,2 %** |
| **TOTAL S6+S7** | **6.417** | **2.274** | **35,4 %** |

*Procedencia declarada: estas cifras las produjo código read-only en la tarea de veredictos
(§V14 del diff de reparación); **no provienen de un artefacto commiteado**, porque el conteo del
ladder crudo no se persiste en ninguno.*

**El mecanismo está identificado y es deliberado:** el resolvedor descarta una posición cuando ninguna
vela de su ventana de reintento tiene un tick a spread ≈0,5. Eso **espeja el vivo a propósito**: si la
ficha nunca pudo abrirse a 0,5, en la cuenta real no existió.

Tres conclusiones, en orden:

1. **La supervivencia de `reverse` (26,2 %) es menor que la media (35,4 %) pero no es anómala:** está
   en la misma banda que `EXIT_TRAIL` (28,3 %). No hay indicio de que el gate discrimine contra las
   reversiones por su naturaleza.
2. **La causa medida es la duración, no el motivo.** Las posiciones cerradas por reversión son más
   cortas —mediana de 4 velas en S6 y 3 en S7, frente a 7 y 4 del resto— y la fracción que dura ≤1
   vela es 7,1 % vs 1,2 % (S6) y 13,8 % vs 3,5 % (S7). Una posición corta tiene menos cierres de vela
   donde intentar entrar a 0,5, luego se descarta más. El sesgo es **estructural por duración** y
   afecta a cualquier motivo de vida corta.
3. 🔴 **El instrumento sigue sin ver una parte de los cierres reales: 549 cierres `reverse` quedan
   fuera del libro.** Eso **no es un segundo error de emparejamiento** —lo que se reparó está
   reparado—: faltan por la misma razón por la que faltan otros 3.594 cierres de todos los demás
   motivos.

**Lo que queda INDETERMINADO:** si la ventana de reintento es un espejo *fiel* del reintento del vivo
para posiciones de 1–2 velas, o si penaliza de más a las posiciones cortas. Como las reversiones son
a la vez la población corta **y** la población perdedora, un sesgo ahí desplazaría el resultado.
**La dirección de ese sesgo no es determinable** con los artefactos actuales: las 549 filas
descartadas no tienen fills, así que su neto no existe en ningún sitio.

⚠️ **Consecuencia honesta: 39,5 MM es la mejor cifra disponible, no una cifra cerrada.**

### 8.2 Las demás cosas que este dato no permite concluir

| No puede concluirse | Qué haría falta |
|---|---|
| Que haya que desactivar el *stop-and-reverse* | El contrafactual: una corrida sobre copia con el mecanismo desactivado, comparada bajo D170 completo |
| Que 39,5 MM sea la cifra definitiva | Instrumentar el descarte del resolvedor para emitir las 549 filas con un fill contrafactual (§8.1) |
| Nada sobre el gate de spread 0,6 | Filas a 0,6. Hay **cero** (§6.6) |
| Que B1 funcione fuera de muestra | Un periodo out-of-sample. Los cinco peldaños, el ranking y las tres pruebas de robustez son **in-sample** sobre los mismos 7 meses |
| Que el edge del track sea estadísticamente distinto de cero | Más historia, o una prueba de significancia sobre el libro — que **nadie ha corrido**. Hoy: NO EVALUABLE |
| Que el cap B3 sea un control de riesgo validado | Un régimen de solape que lo hubiera hecho morder. `dropped_n = 0` por construcción (§5.3) |
| Que la brecha sim-vs-live esté cerrada | 70 ops / +104 k en backtest contra 116 ops / +282 k en vivo, la misma semana (§7.3) |
| Que B2 y B4 no tengan problema | B2 solo cubre NFP; B4 no es enmascarable. **Sin evidencia, no sin problema** (§5.2, §5.4) |
| **El tamaño de muestra mínimo para que el A/B campeón-retador signifique algo** | **NO DISPONIBLE** — no se corrió ningún cálculo de potencia estadística. Ver §9 |

---

## 9. Cómo se lee el A/B (campeón vs. retador)

**Con lote en paridad (0,1 contra 0,1), la comparación es directa** y no necesita normalizarse por
tamaño. Lo que sí hay que normalizar es el **conteo**: el retador abrirá **menos** operaciones que el
campeón por definición, porque sus puertas vetan algunas. Por tanto la comparación honesta es
**por operación**, no por neto acumulado, y el neto acumulado solo se lee junto al número de
operaciones de cada sleeve.

**Cuánta muestra hace falta para que el A/B signifique algo: NO DISPONIBLE.** Nadie corrió un cálculo
de potencia, y este documento no va a inventar uno. Lo que sí se puede decir con los artefactos en la
mano, y que basta para fijar la expectativa:

- Sobre 7 meses, la única puerta que muerde en el retrospectivo es **B1**, y veta **227 de 2.542**
  posiciones (**8,9 %**). B2, B3 y B4 vetan **cero**.
- El libro tiene 2.542 posiciones en **163 días de trading** = **15,6 posiciones/día**. Una semana de
  cinco sesiones son del orden de **78 posiciones**, de las que B1 vetaría del orden de **7**.

**De ahí se sigue lo único que importa operativamente: una semana de datos no va a resolver nada.**
La diferencia esperada entre los dos sleeves en una semana es de unas pocas operaciones vetadas, y la
racha máxima de pérdidas consecutivas medida en este mismo libro es de **42** (§6.5). Cualquier
lectura del A/B antes de acumular varios múltiplos de esa escala estará leyendo ruido.

Y una advertencia que vale más que la anterior: **el criterio para juzgar el A/B no puede ser el neto
solo.** Por §2, este track tiene un neto dominado por tres operaciones. Un sleeve puede "ganar" una
semana por una sola operación grande sin que eso diga nada de su capa de riesgo.

---

## 10. Honestidad de proceso: qué se encontró roto en el instrumento

Esta entrega descubrió errores **en el instrumento de medición**, no en el código que opera la
cuenta. Se declaran para que un lector pueda auditar cómo se llegó a las cifras de este documento.

### 10.1 Un error real, corregido

**`run_ladder` no emparejaba los cierres `reverse`** (`scripts/analysis/realtick_bt/backtest.py`).
La pierna que se cerraba por reversión quedaba abierta en la estructura de posiciones, la siguiente
entrada de esa misma ficha la sobreescribía, y el cierre posterior emparejaba con la entrada nueva.
Resultado: la fila que sí se emitía era **correcta**, y la de la reversión **desaparecía entera y en
silencio**. Eso explica exactamente el patrón medido —0 filas re-atribuidas, 195 filas nuevas.

**Corregido en el commit `fadf1ec`. Impacto: +195 posiciones, −108.266.105 CLP.**

### 10.2 Un error que se sospechaba y que NO existe

Se creía —y estaba escrito en el plan— que el resolvedor **inventaba fills** cuando ningún tick
cruzaba el nivel del stop, lo que habría inflado artificialmente los resultados. **Al medirlo,
resultó FALSO.** Los cierres por stop cruzan dentro de su propia vela en el **891 de 891** de S6 y el
**1.104 de 1.104** de S7. La rama de respaldo **no se dispara nunca** en este dataset.

**Este documento no afirma ese error, porque la medición lo desmintió.** Se deja registrado porque
una de las dos hipótesis con las que se abrió esta investigación era falsa, y ocultarlo daría una
impresión equivocada de lo bien diagnosticado que estaba el problema.

### 10.3 Una etiqueta engañosa, corregida en la capa de análisis

El motor marcaba `EXIT_INITSL` a cierres cuyo stop **ya había sido levantado** por el trailing o por
el breakeven en velas anteriores, sin distinguirlos de un stop inicial intacto. No es un error de
código vivo —el motor sale al nivel correcto y los fills son reales; neto, PF, WR y drawdown no
cambian por esto—, pero hacía que la atribución por motivo de salida **indujera a error** (§6.3).

**Separado en `EXIT_INITSL` (genuino) y `EXIT_SL_RAISED` en la capa de análisis, commit `2823160`.**
El motor no se tocó: afinar su etiqueta va sobre una copia independiente y pertenece al programa
posterior a esta entrega.

### 10.4 Cómo se verificó que la reparación no rompió nada

- **Existe un snapshot inmutable pre-reparación** (`data/analysis/pre_repair_snapshot/`, commit
  `b3c53e2`): los 12 artefactos base con `sha256` por fichero, más el multiset de las 2.347 filas
  originales copiadas como texto verbatim.
- **Existe el diff número-por-número viejo-contra-nuevo**
  (`docs/superpowers/research/2026-07-27-substrate-repair-diff.md`), con las 2.347 filas clasificadas
  una a una: 367 idénticas, 1.980 solo re-etiquetadas, **0 re-atribuidas, 0 desaparecidas**, 195
  nuevas.
- **Los controles internos salen limpios:** SuperTrend idéntico al peso (no tiene el mecanismo), la
  semana de validación idéntica en las 8 celdas, y las sumas de las mayores operaciones idénticas al
  céntimo en ambos substratos.

---

## 11. Rollback

Los tres niveles, verbatim del ensayo del 2026-07-27 (commit `f65ff02`). **El nivel 2 fue ensayado
sobre un árbol real de git; el nivel 1 fue verificado por test, no contra un supervisor corriendo.**

**Punto de retorno:** tag `pre-challenger-2026-07-25` → `dfdc4d7cd34d473484ce20ca4d00f9e2ed52ba37`.

**Nivel 1 — segundos, sin tocar código.** Poner `SUPERVISOR_CONFIGS=local` y reiniciar el supervisor.
El retador deja de abrir; el campeón queda intacto. Las posiciones 726xxx que estuvieran abiertas se
gestionan hasta su salida re-armando `local+challenger` brevemente, o se cierran a mano.

**Nivel 2 — un comando.** En `equipo1`, del más nuevo al más viejo (orden obligatorio):

```
git -C D:/FOREX revert --no-edit 13c4898 826de0f 36979a3
```

- `13c4898` — executor: roster `local+challenger` + puertas en el OPEN
- `826de0f` — lote del retador 0,02 → 0,1
- `36979a3` — `CONFIGS_CHALLENGER`, banda 726xxx

⚠️ Los tres se revierten **juntos o ninguno**: revertir el plumbing dejando el roster haría que un
config pasara `risk_gates` a una firma que ya no lo acepta. El módulo `risk_gates.py` **no** entra en
el revert: revertidos el roster y el plumbing queda inalcanzable, y su bloque está guardado por
`if a.kind == "OPEN" and risk_gates:`.

**Nivel 3 — nuclear.**
`git -C D:/FOREX checkout pre-challenger-2026-07-25 -- sentinel_engine scripts` y commit. Devuelve el
código al estado pre-retador exactamente.

---

## 12. Qué sigue

En orden de lo que este informe hace más urgente:

1. **Concentración del neto (§2) — prioridad número uno.** Un track cuyo resultado positivo depende
   de 3 operaciones de 2.542 necesita entenderse antes que optimizarse. Esto deja de ser un item más
   de la cola y pasa a ser el riesgo dominante.
2. **El contrafactual del *stop-and-reverse* (§6.4).** Correr el backtest **sobre copia** con la
   reversión desactivada y comparar bajo D170 completo. Es la única forma de saber si el mecanismo
   ayuda o estorba; hoy no se sabe.
3. **Instrumentar el descarte del resolvedor (§8.1)** para poder acotar la dirección del sesgo
   residual de los 549 cierres que faltan. También sobre copia.
4. **Confirmación de magnitudes contra el motor MT5 real-tick** (gold-standard "every tick based on
   real ticks"), empezando por SuperTrend, cuya magnitud sigue marcada como provisional — y que
   ahora carga el 53 % del neto.
5. **Fase 0 y walk-forward/holdout.** Es la infraestructura que tiene que existir **antes** de que
   cualquier re-optimización sea honesta (§4).
6. **Afinar la etiqueta de salida en el motor** (§10.3), sobre copia independiente.
7. **Pendientes que no bloquean:** el estudio de entrada aleatoria (¿el edge está en las entradas o
   en las salidas?) y la escalera de distancia de SL, que debe correr sobre el substrato **reparado**
   — sus resultados sobre el viejo no serían comparables.

---

## Anexo A — Procedencia de cada cifra

Todo número de este documento sale de uno de estos ficheros. Ninguna cifra fue escrita de memoria.

| Bloque de este documento | Artefacto |
|---|---|
| Neto, PF, WR, n por estrategia y combinado (§1, §6.6) | `data/analysis/monday_audit/a5_spread_gate.json` |
| Drawdown, pico, valle, fechas (§6.1) | `data/analysis/monday_audit/a1_maxdd.json` |
| Cap de fichas, correlaciones, días, histograma (§5.3, §6.2) | `data/analysis/monday_audit/a2_overlap.json` |
| Atribución por motivo de salida, medias, PF por motivo (§6.3, §6.4) | `data/analysis/monday_audit/a3_exit_reason.json` |
| Autocorrelación y rachas (§6.5) | `data/analysis/monday_audit/a4_serial.json` |
| Veredictos de máscara B1–B4 y sus magnitudes (§5) | `data/analysis/monday_audit/b6_mask_verdicts.json` |
| Recorte top-K y consistencia mensual (§2, §7.2, Anexo C) | `data/analysis/monday_audit/b1_robustness.json` |
| Curva de espera N2–N6 (Anexo C) | `data/analysis/monday_audit/b1_wait_window.json` |
| Grilla mensual y validación semanal (§7) | `docs/REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md` |
| Libro de posiciones (verificaciones directas de §1.2, §6.4) | `data/analysis/realtick_bt/positions_*.csv` |
| Clasificación fila-a-fila viejo-contra-nuevo (§1.2, §10.4) | `docs/superpowers/research/2026-07-27-substrate-repair-diff.md` |
| Substrato pre-reparación con `sha256` (§10.4) | `data/analysis/pre_repair_snapshot/` |
| Roster del retador, magics, lote, puertas (§3) | `sentinel_engine/strategies/live_configs_20.py` |
| Calendario de noticias (§5.2) | `data/live/news_calendar.csv` + `.README.md` |

**Única excepción declarada:** las tasas de supervivencia de §8.1 (6.417 → 2.274; `reverse` 744 → 195)
las produjo código read-only durante la fase de veredictos y **no provienen de un artefacto
commiteado**, porque el conteo del ladder crudo no se persiste en ninguno. Están marcadas como tal
allí donde aparecen.

---

## Anexo B — Afirmaciones anteriores que quedan superadas

Registro aditivo: nada se borra, se declara qué sustituye a qué.

| Afirmación anterior | Estado | Sustituida por |
|---|---|---|
| «Neto de 7 meses: 147.780.084 CLP, PF 1,138, 2.347 ops» | **SUPERADA** | 39.513.979 CLP, PF 1,033, 2.542 ops (§1) |
| «maxDD −28,57 %, **confirma** la estimación previa de −28,6 %» | **MUERTA** | −32,34 % del balance inicial (§6.1) |
| «SuperTrend es casi independiente de ambas» | **ENTERRADA** | +0,356 contra S6 y +0,153 contra S7 (§6.2) |
| «El grueso del libro sale por stop inicial, y los stops iniciales son rentables» | **INDUCÍA A ERROR** | El track gana con el trailing y pierde con las reversiones (§6.3) |
| «10 operaciones son el 72 % del neto; recortar 30 lo vuelve −49,6 MM» | **EMPEORA** | Bastan 3 operaciones para volverlo negativo; recortar 30 lo deja en −157,9 MM (§2) |
| «El signo de la curva de espera se da vuelta entre 60 y 90 minutos» | **YA NO ES CIERTA** | Los cinco peldaños son positivos (Anexo C) |
| «El ranking de la curva de espera sobrevive el recorte top-K» | **PARCIAL** | Sobrevive hasta K=5 y se rompe en K=10 (Anexo C) |
| «El reporte mensual se regeneró sin snapshot previo; no hay diff» | **OBSOLETA** | Existe snapshot verificado por `sha256` y diff número-por-número (§10.4) |
| «Hay dos errores en el backtest: reverse y fills» | **REESCRITA** | Hay **un** error real (reverse) y **una** etiqueta engañosa. El de fills **no existe** (§10) |

---

## Anexo C — La curva de espera post-apertura (experimento aparte, in-sample)

🔴 **Este anexo NO es el veredicto de B1.** El veredicto de B1 para esta entrega es el de los **50
minutos fijados de antemano por diagnóstico** (§5.1). Buscar el mejor punto de una curva **es
tunear**, así que el resultado va declarado aparte. Se registra —por decisión explícita del user—
para que nadie reintente 15 o 90 minutos más adelante sin saber por qué le fue peor.

Espera = bloquear las primeras N velas M15 tras una reapertura de mercado (las entradas solo ocurren
en múltiplos de 15 minutos, así que 50 y 60 minutos son el **mismo** experimento). N=1 fue descartado
por el user.

| Peldaño | Espera | Neto resultante (CLP) | Δ% sobre la base | Posiciones bloqueadas |
|---|---:|---:|---:|---:|
| **N3** | 45 min | **93.881.699,49** | +137,59 % | 168 |
| N4 | 60 min | 80.302.945,79 | +103,23 % | 227 |
| N5 | 75 min | 75.046.755,24 | +89,92 % | 317 |
| N2 | 30 min | 62.488.870,92 | +58,14 % | 98 |
| N6 | 90 min | 40.847.947,90 | +3,38 % | 395 |
| *base* | 0 | 39.513.978,56 | — | 0 |

*Fuente: `data/analysis/monday_audit/b1_wait_window.json`.*

**Ranking: N3 > N4 > N5 > N2 > N6.** Respecto de lo publicado antes, **N2 y N5 intercambian los
puestos 3 y 4**.

🔴 **Corrección obligatoria: la frase «el signo se da vuelta entre 60 y 90 minutos» ya no es cierta.**
Sobre el substrato reparado **los cinco peldaños son positivos**; N6 pasa de −15,24 % a **+3,38 %**.

⚠️ **Los cinco porcentajes comparten el mismo denominador colapsado y por tanto los cinco están
inflados.** Lo comparable entre substratos son los CLP, no los porcentajes: en CLP, la mejora de N3
pasa de +48,3 MM a +54,4 MM.

**La forma se sostiene: es una joroba, no un codo.** Sube hasta N3 y baja monótonamente después
(137,6 → 103,2 → 89,9 → 3,4). **No hay un codo que justifique fijar el parámetro por geometría de la
curva.**

### Robustez de la curva (tres pruebas, todas in-sample)

- **Consistencia mensual:** N3 mantiene **5 meses positivos de 7**. Pero **un solo mes carga con más
  del 100 % de la mejora**: febrero de 2026 aporta un delta de **+64.939.710 CLP** sobre un delta
  total de 40,8 MM. **La mejora de B1 es, en lo esencial, un fenómeno de febrero de 2026.**
- **Recorte top-K:** N3 sigue siendo el mejor peldaño con K=1, 3 y 5, pero **en K=10 el mejor pasa a
  ser N5**. El ranking **sobrevive hasta K=5 y se rompe en K=10** — antes se afirmaba que sobrevivía.
- **Perfil de lo bloqueado vs. lo mantenido (peldaño N3):** lo que la puerta bloquea **es peor** en
  las cuatro métricas, y con más margen que antes.

| | Bloqueadas | Mantenidas |
|---|---:|---:|
| n | 168 | 2.374 |
| Media CLP | −323.617,39 | +39.545,79 |
| Mediana CLP | −499.454,18 | −303.688,22 |
| Win rate | 27,98 % | 32,56 % |
| Profit factor | **0,5918** | **1,0892** |

*Fuente: `b1_robustness.json`, `m1_sign_consistency_by_month`, `m2_topk_sensitivity`,
`m3_blocked_vs_kept_profile`.*

**La puerta separa poblaciones genuinamente distintas, no corta al azar.** ⚠️ Pero el matiz importa:
aplicar la espera al substrato reparado deja un libro con **PF 1,089**, no 1,208. **La puerta ayuda;
no rescata.**

**Caveat final, del propio artefacto:** todo este anexo es **in-sample** sobre los mismos 7 meses.
Sobrevivir estas pruebas significa que la forma de la curva no es un artefacto de unas pocas
operaciones grandes ni de un mes afortunado **dentro de este substrato**. **No** significa que la
curva, ni ningún peldaño de ella, vaya a sostenerse fuera de muestra.

---

*Documento emitido el 2026-07-27. **Emitido no es entregado:** nada de esto está entregado hasta que
el user lo haya revisado.*
