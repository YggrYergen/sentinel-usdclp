# MEMO DE INTERPRETACIÓN — P-CAP, primera corrida extremo a extremo

**Autor:** controlador (Opus 5). **Fecha:** 2026-08-13.
**Capa:** análisis. Los datos viven en `04-resultados/T0.7-p-cap/` y en `data/analysis/p_cap/`;
este fichero interpreta, y por eso está separado de ellos (charter §A.4).
**Insumos:** `p_cap_resultado.{json,md}`, `data/analysis/p_cap/comparacion_p_cap.csv` (161 filas),
`metricas_p_cap.json`. **Motor replicado:** `b113eb7` (`engine-faulty-tomachine-902`).

---

## 1 · El titular, sin adornos

**P-CAP no pasa.** De las **140** posiciones evaluables, **cero** casan en los seis campos que
D-45 fija como criterio. Y no pasa tampoco relajando los instantes a una tolerancia de 1 segundo:
también cero.

Ése es el hecho. Lo que sigue explica por qué ese cero **no significa que la réplica esté
equivocada**, y por qué dos de los seis campos no podían casar por construcción.

## 2 · La medición que ordena todo lo demás

De las 137 posiciones emparejadas, hay **7 en las que la réplica abrió dentro de 1 segundo** del
instante real. En esas 7:

| \|Δ precio de apertura\| | posiciones |
|---|---|
| **exactamente 0,00** | **5 de 7** |
| ≤ 0,05 | 6 de 7 |
| ≤ 0,17 | 7 de 7 |

**Cuando el instante coincide, el precio coincide exacto.** No «se aproxima»: es idéntico en cinco
de siete, y las dos restantes están dentro de dos centésimas y diecisiete centésimas.

Esto identifica la causa. La réplica **decide bien** —el mismo lado, sobre la misma señal, con el
mismo SL— y lo que diverge es **cuándo mira**. El desvío de precio no es un error independiente:
es la consecuencia aritmética de mirar el mercado unos segundos después.

Lo confirma la distribución completa: la mediana de \|Δ t_open\| es **9,0 s**, y el ciclo del
ejecutor es de **15 s**. Nueve segundos es, casi exactamente, el desfase medio esperable entre dos
relojes de sondeo de 15 segundos con fase independiente. Y la mediana de \|Δ precio de apertura\|
es **0,23**, que es lo que el oro se mueve en nueve segundos de sesión activa.

## 3 · Por qué el criterio, tal como está redactado, es insatisfacible en dos campos

🔴 **La verdad de terreno tiene resolución de SEGUNDO ENTERO. La réplica, resolución de TICK.**

Verificado leyendo las dos fuentes:

- `2883016902_deals_raw.csv` sólo trae la columna `time` — **no existe `time_msc`**. Los 152
  `t_close_epoch` de `verdad_terreno_902.csv` son enteros, sin excepción.
- `posiciones_replica.csv` cierra en instantes como `1785268336.309`, `1785268575.299`.

Un número con fracción **no puede ser igual** a uno entero salvo que el tick caiga exactamente en el
borde del segundo. Con resolución de milisegundo eso ocurre ~1 vez de cada 1.000.

⇒ **`t_close` marcó 0 de 137, y habría marcado 0 aunque la réplica fuera perfecta.** Ese cero no
mide fidelidad: mide que se están comparando dos relojes de distinta precisión. Lo mismo afecta a
`t_open`, atenuado.

**Esto es un defecto en cómo se operacionalizó D-45, no en la réplica.** La decisión hablaba de
«bit-identidad sobre instante de entrada y de salida» sin que nadie hubiera comprobado que las dos
fuentes tuvieran la misma resolución. Es el mismo error de clase que el `SPREAD_GATE_SKIP` de D-43
y que el «7 %» de los cierres manuales: usar una medida sin verificar qué mide.

## 4 · Lo que sí está medido, y es mucho

Con la causa identificada, las cifras se leen distinto:

| Campo | Bit-idéntico | Dentro de 1 ciclo (16 s) | Dentro de 1,00 USD |
|---|---:|---:|---:|
| instante de apertura | 7 / 137 | **89 (65 %)** | — |
| instante de cierre | 0 / 137 | **95 (69 %)** | — |
| precio de apertura | 7 / 137 | — | **116 (85 %)** |
| precio de cierre | 4 / 137 | — | **125 (91 %)** |
| **razón de cierre** | **126 / 137 (92 %)** | — | — |
| **resultado** | **130 / 137 (95 %)** | — | — |

**El carácter de las operaciones se reproduce.** La razón por la que cada posición murió acierta en
el 92 % de los casos, y si ganó o perdió en el 95 %. Eso, con un motor que hasta esta semana no se
podía ni ejecutar, es un salto real: D-43 dejó registrado que la réplica «se intentó repetidamente
en backtests real-tick y falló todas las veces».

**Pero no es paridad, y conviene no maquillarlo.** Sólo el 46 % de las aperturas cae dentro de 20
centavos del precio real. Una réplica que se usara para proyectar 4,7 años acumularía ese sesgo
operación tras operación.

## 5 · La corrección que propongo, y por qué no es hacer trampa

**El ejecutor vivo dejó registrados los instantes en que miró.** `eventos_ejecutor_902.csv` tiene
1.710 filas con su epoch. La réplica, en cambio, sintetiza su propia rejilla: arranca en `t0` y
avanza en pasos exactos de 15,0 s. La cadencia real medida fue **15,77 s de mediana** (T0.6-A Q6),
irregular porque cada ciclo hacía trabajo real.

⇒ **Propuesta: alimentar el bucle de ciclos con los instantes reales del log, en vez de una rejilla
sintética.**

🔴 **Por qué esto NO es ajustar la réplica a su respuesta.** La distinción importa y la hago
explícita: los instantes de sondeo son un **insumo** del sistema real, exactamente igual que el flujo
de ticks. Replicar un motor asíncrono sin replicar cuándo despertaba es como replicarlo sin darle los
precios. Lo que **sí** sería trampa —y queda prohibido— es tocar umbrales, gates, `stops_level` o la
ventana hasta que los números cuadren. La diferencia es que un insumo se copia; un parámetro se
ajusta.

**Predicción falsable, que es lo que hace útil a la propuesta:** si la fase es la causa dominante,
al alimentar los ciclos reales el bloque de las 7 posiciones de §2 debe extenderse al grueso de las
137, y `precio_open` debe saltar de 7 bit-idénticas a la mayoría. **Si no ocurre, la hipótesis de
§2 está mal y hay una segunda causa que buscar.**

## 6 · Lo que queda abierto, y de quién es cada cosa

**Del user, porque D-45 fue suya:** el criterio de paso necesita re-especificarse en los dos campos
de instante. La verdad de terreno no tiene la precisión que el criterio exige. Opciones, sin
recomendar ninguna todavía:
comparar el instante **truncado al segundo**; exigir tolerancia de **1 tick**; o quitar el instante
del criterio y dejar sólo precio, razón y resultado.

**Del programa, medido y sin resolver:**

- **Las 6 posiciones de más de S6 y las 9 de la réplica sin pareja.** Dos de ellas abren en el borde
  de `blocked_open_window` (16:55:14) y duran ~48 h — posible artefacto de fin de semana. Constatado,
  no investigado.
- **El p90 de \|Δ t_open\| = 6.295 s** (1 h 45 min) frente a una mediana de 9 s. La cola no la
  explica la fase: hay un subconjunto donde réplica y realidad discrepan sobre **si una señal fue
  bloqueada**, y el sospechoso natural es el gate horario.
- **3 posiciones reales de SuperTrend, todas con `reason = SL`, sin pareja en la réplica.**

**Corrección de un número que el controlador dio mal:** dije que SuperTrend salía «67 contra 67,
exacto». Es **67 contra 68**. Comparé las posiciones de la réplica contra las *cerradas* que reportó
T0.5, olvidando la que seguía abierta. El agente lo recalculó desde el CSV en vez de aceptar mi
cifra, que es exactamente lo que el charter §A.13 pide de él.

## 7 · Qué NO se puede concluir de esto

- **No** que las estrategias funcionen o no. Esto mide el **motor**, no el edge.
- **No** que la réplica sirva ya para el backtest largo. Con 46 % de aperturas dentro de 20 centavos,
  proyectar 4,7 años acumularía el sesgo.
- **No** que la Fase 2 (la copia rápida del motor) esté justificada o no por coste. Ahora hay número
  real —**350 s** por ventana de dos semanas, escalando **lineal**— pero esa decisión depende de que
  la Fase 1 sea fiel primero.
