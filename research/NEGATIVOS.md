# REGISTRO DE NEGATIVOS — lo que NO funcionó, con evidencia

> Un negativo bien documentado vale tanto como un positivo: evita volver a gastar presupuesto en
> lo mismo, y es lo que hace honesta la corrección estadística (el haircut de DSR cuenta **todo**
> lo intentado, no solo lo que sobrevivió).
>
> **Append-only.** Un negativo puede re-abrirse, pero **solo con causa escrita** — típicamente
> porque cambió el instrumento de medición, el sustrato, o porque el diseño original no controlaba
> una variable relevante. Al re-abrir, la entrada original **permanece**.

Formato: `<fecha> · <experimento> · <qué se probó> · <resultado> · <evidencia: ruta> · <estado>`

---

## Negativos vigentes

| Fecha | Qué se probó | Resultado | Evidencia | Estado |
|---|---|---|---|---|
| 2026-07 | **Régimen por ATR14-percentil** como gate, en la forma probada | Sharpe gateado por debajo del no-gateado | `2026-07-22-prior-experiments-audit.md` | 🔓 **Re-abierto acotado**: solo esa forma funcional quedó quemada. Nueva grilla (períodos, múltiplos, ventanas, pendiente, cruces multi-TF) con causa registrada — plan D3 |
| 2026-07 | **Take-profit fijo a-priori** (`tp_min`), todos los valores | Activamente perjudicial | `2026-07-22-prior-experiments-audit.md` §Wave-6 | 🔓 **Re-abierto (B5)**: el veredicto precede a los fixes de reloj/`reverse`/fills y nunca controló re-entradas. Además, un trailing en positivo es un TP a-posteriori: esa familia nunca estuvo quemada |
| 2026-07 | **TK-BW** tal como está | 0 posiciones: c1 (pullback<EMA8) y c4 (breakout) son geométricamente incompatibles; forzada a operar, pierde | memoria `tk-bw-structural-contradiction` | 🔒 Gated por **rediseño de entrada con múltiples alternativas**; gate de éxito = neto positivo, no "toma posiciones" |
| 2026-07 | **Fills same-bar** (look-ahead) en backtest | Colapso ~−121 % neto | `2026-07-22-prior-experiments-audit.md`; `emasar_ref.py:489-503` | 🔒 **Resuelto, no re-abrible**: `live_fill_mode=True` obligatorio |
| 2026-08-12 | **El gate de spread 0,50 es un filtro de liquidez/volumen** — hipótesis del user y del controlador, para poder trasladarlo a AVA vía densidad de ticks (feed-independiente) | ❌ **Refutada, y en dirección contraria.** El estado que DEJA operar tiene *menos* volumen: mediana 2.496 ticks/vela contra 3.336 del estado que no deja (0,75×). Por deciles de volumen, el % de velas en estado estrecho cae **62,6 → 50,2 → 42,8 → 41,6 → 40,7 → 34,0 → 32,5 → 26,9 → 24,5 → 13,9**, monótono y sin una sola inversión. Capitaria **ensancha** el spread cuando hay actividad (comportamiento normal de dealer), así que el gate vivo selecciona **calma**, no liquidez. Como sustituto es además inservible: solo el 23,2 % de las velas en estado 0,50 supera el umbral de volumen de selectividad equivalente | Reproducible con la condición exacta del harness (`backtest.py:349-359`) sobre 8.334 velas M15 de Capitaria, holdout excluido. Ver bitácora del TRACKER 2026-08-12 (c) | 🔒 **Cerrado como sustituto del gate.** No se re-abre por esta vía: lo que el gate marca resultó ser una **ventana horaria** (T0.13, `18:00→02:00 ET`), y esa sí es transferible. 🟢 **Subproducto de valor propio, a explotar en D3/A4:** queda documentado que el sistema vivo opera en condiciones de **baja actividad relativa**, algo que nadie había decidido y que hasta ahora nadie sabía |
| 2026-08-12 | **Reproducir la selectividad del gate en AVA por cuantil de spread** (dejar pasar el 31,165 % de ticks más estrechos, mes a mes) | ❌ **No es reproducible.** AVA es casi unimodal en buena parte de la serie: un cuantil no puede partir un pico. 2022-01 con umbral 0,34 deja pasar el **99,86 %**; 2026-02 (modo 0,92) el **99,99 %**. Y el spread de AVA **no tiene estructura horaria**: su modo estrecho está al 96-100 % en casi todas las horas, mientras que el de Capitaria es un interruptor (99-100 % dentro de la ventana, 0-5 % fuera) | Distribución por mes y por hora sobre 218.388.690 ticks de AVA (2023 excluido por holdout) y 34.004.053 de Capitaria | 🔒 **Cerrado.** El estado de mercado que en Capitaria se lee vía spread, el feed de AVA no lo codifica. La ventana solo se puede reconstruir en AVA como **regla de reloj explícita** (T0.13) |

## Eliminados por directiva (no son negativos experimentales)

| Ítem | Motivo |
|---|---|
| Cross-instrumento | Directiva del user: solo oro |
| Spread como variable de barrido | Se opera solo con spread ≤0,5; A4 mide **dentro** de esa condición |

## Resultados degradados a "direccionales" (NO concluyentes)

| Ítem | Motivo |
|---|---|
| Todo resultado de **TOKATA** (steps de SAR, ladder F1/F2/F3, PF 2,82 / 4,56, etc.) | El motor de esa época se determinó faulty (Model=1 open-prices-only + look-ahead same-bar + SL inválido bajo el mínimo del bróker). Sirven como **dirección y recomendación**, jamás como evidencia. Todo se re-corre bajo el motor honesto |
| Cifras en prosa de `b1-wait-curve.md`, `b1-robustness.md`, `long-backtest-queue.md` | Prosa anterior a la regeneración de sus JSON. **Leer siempre el JSON**, nunca la prosa |

### N-xx · 2026-08-13 · El harness importa `live_configs_20.py` del working tree, no del commit congelado — INOCUO
*(Procedencia: dato reportado sin evaluar por T0.6-A; verificado por el controlador.)*

`backtest.py:41` hace `from sentinel_engine.strategies.live_configs_20 import _GOLIVE_M15`, es decir
lee el módulo del **working tree**, no el de `b113eb7`. Ese fichero difiere entre ambos en **225
líneas** de diff, lo que abría la sospecha de que el harness estuviera simulando una estrategia
distinta de la que corrió en vivo.

**Refutado con medición.** Comparadas las kwargs efectivas clave a clave:

```
S6-K2P0:    21 claves, 0 DIFERENCIAS
S7-TPNONE:  22 claves, 0 DIFERENCIAS
```

(Método: extraer `git show b113eb7:sentinel_engine/strategies/live_configs_20.py`, importar ambos
módulos por separado y comparar `{c["id"]: c["kwargs"] for c in _GOLIVE_M15}`.)

El diff de 225 líneas no toca las kwargs de las estrategias que el harness consume. **No es una
divergencia.** Nótese que esto es sobre el `_GOLIVE_M15` **base**; el roster vivo `tomachine`
aplica encima `_tomachine_copy("S6-K2P0", 0.67, active_fichas=1)`, y esa sí es una divergencia real
— pero ya está catalogada como **D3**, no es ésta.

### N-xx · 2026-08-13 · «El fill del bróker es el residuo central en las APERTURAS» — REFUTADA
*(Medición `F0-A6-FILL-0001`, commit `50ff2b8`. Interpretación: memo P-CAP ADDENDUM II §H.1.)*

El memo marcó como hipótesis que el precio de llenado del bróker sería un **techo estructural** y que
la bit-identidad sobre precio sería tan inalcanzable como lo era sobre instante.

**Refutada para las aperturas.** El precio real de llenado **sí está en el lago**: casa exacto con
alguna cotización del mismo segundo en **120/152 (78,9 %)**, **98,0 %** a ±1 s y **100 % a ±5 s**.
Control de lado invertido 0,7 %. **No hay techo en apertura: el residuo es nuestro**, y está
localizado — el tick *vigente* acierta el 31,6 % frente al 78,9 % de *algún* tick del segundo, luego
la réplica elige mal cuál tick dentro de un segundo que la fuente no sabe subdividir.

🔒 **Cerrada como explicación de las aperturas.** Sigue **viva y confirmada** para los cierres por
stop (§H.2), que es una población distinta y no se toca aquí.

### N-xx · 2026-08-13 · «El gate horario explica la cola del p90 de Δt_open» — REFUTADA
*(Medición `F0-A6-COLA-0001`, commit `50ff2b8`. Interpretación: memo ADDENDUM II §I.)*

El memo §6 escribió que «el sospechoso natural es el gate horario».

**Refutada.** De las **39** posiciones con |Δt_open| > 60 s, **una sola** tiene algún
`TIME_GATE_SKIP` en su intervalo, y **39 de 39** abren **fuera** de `blocked_open_window` tanto en la
realidad como en la réplica. La causa real resultó ser el **borde del día**, y su mecanismo se midió
después (ver la entrada siguiente).

🔒 **Cerrada.** No re-abrible por esta vía: el gate horario funciona y hace bien en no disparar.

### N-xx · 2026-08-15 · «El spread o la comisión explican el desvío sistemático de los cierres por stop» — REFUTADA
*(Hipótesis del user y del controlador. Medida por el controlador sobre `fill_vs_cotizacion.csv`.)*

El desvío de los cierres por stop era llamativamente regular —mediana **−0,18** al cerrar largos y
**+0,18** al cerrar cortos— y se planteó que fuera el spread o una comisión.

**Refutada, con tres cortes:**
- Correlación de Pearson entre `|delta_vigente|` y `spread_tick_vigente` en los 119 stops:
  **−0,0075**. Cero.
- Mediana de `|delta|` con spread 0,50: **0,255** (n=110). Con spread 0,60: **0,270** (n=9). Si el
  spread fuera la causa, el segundo grupo sería ~20 % mayor.
- Control: los **21 cierres a mercado** tienen **el mismo spread (0,50 en los 21)** y `|delta|` medio
  **0,053** frente a **0,333** de los stops. Un orden de magnitud menos, mismo bróker y mismo spread.

La comisión queda descartada por construcción: en MT5 va en el campo `commission` del deal, **nunca
en el precio de ejecución**. Y el «±0,18» no es una constante — era la mediana con signo por lado; la
magnitud absoluta va de **0,03 a 1,74** (p50 0,26 · p90 0,66).

🟢 **Subproducto de valor propio:** verificado en `fill_vs_cotizacion.py:69-77` que la referencia
contra la que se midió es **la cotización al PRINCIPIO del segundo**, y un stop se dispara por
construcción durante un movimiento en contra ⇒ **parte del desvío es artefacto del método de
medida**, no dinero perdido. Cuantificarlo es la tarea `T0.7-M-A`, aún sin correr.

🔒 **Cerrada como explicación.** No se re-abre por spread ni por comisión.

### N-xx · 2026-08-15 · «Si el sesgo de la réplica es común a las dos estrategias, la comparación entre ellas sobrevive» — REFUTADA
*(Argumento dado por el CONTROLADOR al user el 2026-08-15 para justificar seguir con presupuesto
acotado. Medición `F0-A6-NETO-0001`, commit `efa17c1`. Interpretación: memo ADDENDUM IV §S.)*

El controlador argumentó que aunque el simulador tuviera sesgo absoluto, si el error era **común** a
S6 y a SuperTrend, el veredicto **comparativo** seguiría siendo válido y bastaría declarar una banda.

**Refutada, y en la peor dirección posible.** El sesgo es **diferencial y de signo opuesto**:

| | diferencia réplica − real | por posición |
|---|---:|---:|
| S6 (n=80) | **−831,47 USD** | **−10,39** |
| SuperTrend (n=55) | **+2.994,23 USD** | **+54,44** |

Cociente **5,24×**. La réplica **penaliza a S6 y favorece a SuperTrend** — es decir, embellece
justamente a la estrategia que **en la realidad perdió** (−16.483,34 USD reales frente a +3.960,37
de S6). Cualquier ventaja de SuperTrend en un backtest por debajo de ~54 USD por posición es
indistinguible de este sesgo.

🔒 **Cerrado como justificación.** El veredicto comparativo **no** puede apoyarse en el simulador tal
como está. Queda como opción declarada: apoyarlo en la ventana real de la 902, que es dato directo.
