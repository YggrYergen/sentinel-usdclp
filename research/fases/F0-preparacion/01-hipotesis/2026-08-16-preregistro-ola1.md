# PRE-REGISTRO — OLA 1 (palancas de salida sobre S6 / S7 / SuperTrend)

**Fecha:** 2026-08-16 · **Autor:** controlador (Opus 5) · **Rama:** `equipo1`
**Escrito ANTES de correr nada.** Ése es el punto: hipótesis, métrica y regla de decisión quedan
fijadas antes de ver un solo número (charter §A.4, plan §9 «significancia pre-fijada por A/B ANTES
de correr»).
**Manda:** D-52 (instrumentación de un viaje) · **D-56** (la Ola 1 no es toda pareada) · **D-57**
(esto corre como piloto pre-congelado; el congelado del motor está escalado al user).
**Catálogo de origen:** `05-analisis/2026-08-15-catalogo-palancas-y-requisitos-motor.md` (`0198002`).

---

## 1 · Qué se puede concluir de esta ola, y qué no

Esto va primero porque condiciona todo lo demás.

A6 midió la fidelidad del simulador contra la ventana real de la cuenta 902 y la respuesta fue mala:
**divergencia de neto del 16,72 %** sobre 134 posiciones emparejadas, contra un umbral de aceptación
del **0,3 %**. Peor: el sesgo **no es común a las dos estrategias, es de signo opuesto** —el
simulador **castiga a S6 en −5,13 USD/posición** y **favorece a SuperTrend en +45,22 USD/posición**,
la estrategia que en la realidad perdió 16.483 USD. El argumento «si el error es común, la
comparación sobrevive» ya se intentó en este programa y quedó **cerrado como no válido**
(`NEGATIVOS.md`, 2026-08-15).

**Lo que sobrevive:** comparaciones **dentro de la misma estrategia sobre el mismo conjunto de
entradas**. El sesgo compartido se cancela en la resta.
**Lo que NO sobrevive:** cualquier cifra absoluta de dinero, y cualquier comparación
S6-vs-SuperTrend.

🔴 **Y la cancelación hay que MEDIRLA, no presuponerla.** S6 y S7 corren con
`stop_and_reverse=True` (verificado en `live_configs_20.py`): una salida distinta puede desplazar la
**entrada** siguiente. Además `resolve()` descarta posiciones que no pasaron el gate de spread. Por
eso toda comparación de esta ola se hace **sobre el subconjunto casado** y se publica **siempre** con
su tasa de emparejamiento al lado. **Regla dura, fijada aquí y ahora: tasa de emparejamiento < 0,90
⇒ la palanca se degrada a no-pareada** y su resultado pasa a descriptivo (D-56).

---

## 2 · Sustrato, unidades y brazos

| | |
|---|---|
| **Sustrato** | `capitaria-ticks-2026-preholdout` — ticks reales de Capitaria, barras M15 `2026-01-01 20:00` → `2026-05-11 23:45`, **8.334 barras**. Holdout D-31 acto 1 **excluido** (`2026-05-12` → `2026-07-26`). Es el MISMO corte con el que está congelada la puerta de paridad, a propósito. |
| **Por qué este corte** | Es sustrato de veredicto (real-tick, charter §A.6) y no toca el holdout (§A.14). Las barras M15 no llegan más allá de `2026-07-24` (pipeline de barras desatendido), así que pre-holdout es lo utilizable. |
| **Tamaño de muestra en el brazo por defecto** | S6-K2P0 **624** posiciones · S7-TPNONE **708** · SuperTrend **153** (línea base re-congelada, ENMIENDA E-03, `35fdde2`). |
| **Unidades** | Resultados **siempre** por-lote **Y** en múltiplos de R (charter §A.1). Lote de investigación fijo. |
| **Brazo de control** | En cada palanca, el brazo `default` = la configuración VIVA sin tocar. Tiene que reproducir la línea base exactamente; si no, la corrida es inválida y se para. |

⚠️ **Limitación declarada por adelantado:** SuperTrend tiene **153** posiciones en la ventana. Para un
barrido de siete niveles (P-05) eso es poco, y la potencia estadística lo va a reflejar. Se declara
ahora, no cuando los intervalos salgan anchos.

---

## 3 · Las palancas, una por una

### P-02 · Time-stop por edad de la señal · **Ola 1-A (pareada, sujeta a verificación)**
- **Estrategias:** S6-K2P0, S7-TPNONE. Ambas tienen hoy `max_hold_bars` **ausente** (= `None` =
  deshabilitado), verificado en las kwargs vivas.
- **Hipótesis falsable:** el alfa de la señal decae con la edad; existe un `N` a partir del cual
  forzar el cierre **mejora** la expectancy por posición sobre el conjunto casado de entradas.
- **Hipótesis nula:** ningún `N` de la grilla mejora la expectancy; el time-stop sólo amputa
  ganadoras.
- **Grilla:** `max_hold_bars ∈ {off(default), 10, 15, 20, 30, 48, 64}` → 7 brazos × 2 estrategias.
- 🔴 **Confound conocido de 64 barras, y cómo se neutraliza:** el plan §12 arrastra un ítem abierto
  («`max_hold_bars=64` confound — re-correr suite PX SIN max_hold + controles 64/48 solos»). En
  aquella suite el 64 estaba **horneado en la base**. Aquí **no**: nuestro brazo por defecto es
  literalmente `off`, y **48 y 64 entran a la grilla como controles explícitos**. El confound
  histórico deja de heredarse y pasa a ser **medible**. No hay que redescubrirlo: está resuelto por
  diseño.
- **Métrica primaria:** diferencia **pareada** de neto por posición casada (brazo − default).
- **Métrica secundaria decisiva:** expectancy **condicional** de las posiciones que el time-stop
  cerró — ¿eran predominantemente perdedoras (buena poda) o ganadoras (upside amputado)? El catálogo
  exige decidir por esto y no sólo por el P&L agregado.
- **Regla de decisión (fijada AQUÍ):** se declara efecto sólo si el IC del bootstrap por bloques a
  nivel de episodio sobre la diferencia pareada **excluye 0**, **y** la métrica secundaria no
  contradice el signo. Además, regla de meseta (plan §9): un `N` aislado rodeado de vecinos peores
  es sospecha de sobreajuste, no un hallazgo.

### P-03 · Umbral y lookback del apriete por desaceleración de AC · **Ola 1-A**
- **Estrategia: sólo S6-K2P0.** Verificado en kwargs vivas: S6 tiene `ac_modulate=True,
  ac_modulate_factor=0.25`; **S7 tiene `ac_modulate=False`**, así que barrer el trigger en S7 sería
  inerte por construcción. Correrlo en S7 sería gastar cuota en un no-op: **no se corre**.
- **Hipótesis falsable:** el trigger de desaceleración de AC (hoy fijo en código, `emasar_ref.py`
  `ac_desacelerando`) no está en su óptimo; existe una combinación umbral × lookback × duración que
  mejora la expectancy pareada frente al valor hardcodeado.
- **Hipótesis nula:** el valor actual es indistinguible de cualquier otro de la grilla.
- **Grilla:** umbral `{25, 50, 75}` pips × lookback `{1, 2}` barras × duración del apriete
  `{3, 5, 10}` barras = **18 brazos** + `default` = 19.
- **Métrica primaria:** diferencia pareada de neto por posición casada.
- **Métrica secundaria:** **% de re-flips falsos tras el apriete** (coste de whipsaw), que es el
  mecanismo que la palanca dice manipular. Si el neto mejora pero el whipsaw no se mueve, el efecto
  no es el postulado y se declara así.
- **Regla de decisión:** idéntica a P-02 (IC pareado que excluye 0 + meseta). Con 18 brazos, la
  corrección por comparaciones múltiples **no es opcional**: se cuentan los 18 en el conteo de
  intentos para DSR/PBO (charter §A.9, plan §9).

### P-08 · Offset de SL consciente del fill · **Ola 1-A**
- **Estrategia:** SuperTrend.
- **Hipótesis falsable:** ensanchar el nivel de stop en un offset fijo compensa el deslizamiento real
  del bróker en los stops server-side y mejora el neto pareado.
- **Hipótesis nula:** el offset sólo ensancha pérdidas; el neto empeora monótonamente con el offset.
- **Grilla:** `sl_offset ∈ {0.00(default), 0.10, 0.20, 0.30}` USD.
- **Anclaje empírico, no arbitrario:** el deslizamiento propio ya está medido — desvío mediano
  **0,255** (spread 0,50) y **0,270** (spread 0,60) en cierres por stop contra **0,053** en cierres a
  mercado ⇒ deslizamiento ≈ **0,20**. La grilla cubre ese valor por ambos lados a propósito. La
  re-calibración fina va en `T0.7-M-H` y **no bloquea** esta corrida.
- **Métrica primaria:** diferencia pareada de neto por posición casada.
- **Métrica secundaria obligatoria, los dos lados:** posiciones **salvadas** (stop casi tocado que
  ya no se toca) contra **falsos disparos añadidos / pérdida extra por stop más ancho**. Medir un
  solo lado sería propaganda.
- **Regla de decisión:** IC pareado que excluye 0, y **monotonía**: si el óptimo aparece en un
  extremo de la grilla, se extiende la grilla en vez de declarar óptimo de borde.

### P-05 · Multiplicador ATR de SuperTrend · 🔴 **Ola 1-B — NO PAREADA**
- **Estrategia:** SuperTrend.
- **Por qué no es pareada (D-56):** el multiplicador **define la línea SuperTrend, que ES la señal de
  flip**. Cambiarlo cambia el conjunto de entradas. La ficha de la palanca en el catálogo ya lo decía
  «NO»; el encabezado de la ola que decía «todo pareado» estaba generalizando de más.
- **Hipótesis falsable:** el `3.0` vivo **no tiene derivación** en la literatura (la propia fuente lo
  marca como folklore, «probablemente ajustado en un solo mercado»). Existe un multiplicador con
  mejor compromiso whipsaw ↔ give-back sobre esta ventana.
- **Hipótesis nula:** el desempeño es plano en el rango 2,0–5,0 y el 3,0 es tan bueno como cualquiera.
- **Grilla:** `{2.0, 2.5, 3.0(default), 3.5, 4.0, 4.5, 5.0}` — unión de la grilla de la fuente y la
  del plan (§7 familia B7d).
- **Métrica primaria:** Sharpe, **nº de flips** y **máx. pérdidas consecutivas** (las tres del
  catálogo), más neto por lote y en R, todas **dentro de SuperTrend**.
- 🔴 **Regla de decisión, más exigente que las demás por no ser pareada:** el simulador **embellece a
  SuperTrend en +45,22 USD/posición**. Ninguna diferencia entre multiplicadores de escala comparable
  o menor se declara efecto. Se decide **sólo por meseta** (una región contigua de multiplicadores
  que domina, plan §9), nunca por un pico aislado, y **jamás en cifra absoluta de dinero**.
- **Conflicto declarado:** interactúa con P-07 (período ATR adaptativo, Ola 2). **No** se corren como
  «on» simultáneo sin sondeo de interacción explícito. En esta ola el período ATR queda fijo en 14.

### P-27 · SL estructural por swing · **DIFERIDA de esta ola**
Su requisito de motor (detección de swings/pivotes conectada al SL inicial) **no** entra en WP-1+2:
tiene una trampa de look-ahead propia —un pivote fractal en la barra `i` sólo se conoce `k` barras
después— y merece su propio paquete con el contrato antitrampa del spec §1. **Pendiente declarado**
(charter §11) con recomendación: paquete WP-1+2b inmediatamente después de la Ola 1, grilla ya
fijada por el catálogo (lookback `{5,10,20}` barras × tamaño mínimo `{0.5,1.0}`×ATR).

### P-33 · `stop_and_reverse` como folklore · **NO SE CORRE** (D-56)
No es una palanca nueva: es la **cita literaria de respaldo** a las familias A3/E3, que siguen **en
cuarentena §2.1 del plan hasta que A6 cierre**. Además no es pareada. Pendiente declarado, se ejecuta
con A3/E3 cuando se levante la cuarentena.

---

## 4 · Reglas globales de la ola (fijadas antes de correr)

1. **Conteo de intentos para la corrección estadística: 7×2 + 19 + 4 + 7 = 44 brazos**, y se declaran
   los 44 —incluidos los que salgan mal— en el conteo de DSR/PBO. La honestidad del haircut depende
   de contar **todo** lo intentado (`NEGATIVOS.md`, preámbulo).
2. **Un negativo bien medido es un resultado legítimo**, no un fracaso (charter §A.2). Si las cinco
   palancas salen planas, eso se publica igual y con el mismo detalle.
3. **Ninguna cifra absoluta de USD** sale de esta ola como resultado del programa. Ninguna
   comparación S6-vs-SuperTrend, en ningún caso.
4. **Regla de meseta** (plan §9): meseta ⇒ refinar paso ≤0,25; picos aislados ⇒ sospecha de
   sobreajuste.
5. **Los brazos por defecto se verifican contra la línea base congelada** antes de leer nada más. Si
   un brazo `default` no reproduce la línea base, la corrida entera se descarta: el instrumento está
   roto y los demás brazos no son interpretables.
6. **Interpretación sólo en memo aparte y sólo Opus** (charter §A.4 y §B). Los artefactos de datos no
   llevan conclusiones.
7. **Estado del resultado:** `piloto-instrumento` mientras el congelado del motor no esté firmado por
   el user (D-57). Se etiqueta así en el LEDGER desde la primera fila, no a posteriori.
