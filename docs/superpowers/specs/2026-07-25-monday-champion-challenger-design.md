# Spec — Entrega del lunes: campeón/retador aditivo

> Fecha: 2026-07-25 · Deadline: lunes 2026-07-27, primera hora
> Estado: **SPEC PARA REVISIÓN DEL USER** (paso 6 de `superpowers:brainstorming`)
> Decisiones que lo originan: **D150** (densidad de grilla) y **D151** (entrega del lunes)
> Siguiente skill autorizado tras la aprobación: `superpowers:writing-plans`. Ningún otro.

---

## 1. Problema

Hay un deadline duro el lunes a primera hora con dos entregables: **(a) un despliegue vivo
[prioridad] y (b) un documento**. Quedan ~36 horas y el mercado está cerrado, lo que da una
ventana limpia para trabajar y desplegar sin riesgo vivo.

La tentación obvia —re-optimizar los parámetros de las señales con el backtest real-tick de 7
meses recién construido— **es exactamente el error que ya se cometió** y que produjo DSR≈0 sobre
225 trials. No se puede hacer honestamente en 36 horas porque la infraestructura que lo haría
legítimo no existe todavía:

- **Fase 0 no está construida**: sin `clamp_sl_distance()`, sin `statgate.py`, sin bloque de
  configuración `experiment`, sin costura de scoring.
- **Task 2.2 (confirmación contra MT5) no está hecha** ⇒ las magnitudes real-tick están sin
  confirmar. El reporte del 07-25 está marcado PRELIMINAR por esa razón.
- **Fase 12 (walk-forward + holdout) no existe.**

Sin esas tres piezas, cualquier parámetro "mejor" que salga este fin de semana es un artefacto de
sobreajuste con la apariencia de un hallazgo.

## 2. Qué se entrega en su lugar

Un **sleeve retador puramente aditivo**: las mismas señales, byte por byte, más una capa de
gestión de riesgo. Ninguna optimización, ningún parámetro re-tuneado.

La justificación es que la brecha real entre lo que corre hoy y un sistema profesional **no está
en los parámetros de la señal** — está en las envolturas que hoy no existen: sin blackout de
noticias, sin tope de exposición de portafolio, correlación entre estrategias desconocida,
gap-wait diagnosticado pero no desplegado, sin circuit breaker de drawdown, sizing no reconciliado
contra Kelly. Todas esas son **wrappers**: no cambian la identidad de la estrategia, y por eso
pueden desplegarse sin re-abrir la pregunta estadística que no se puede cerrar en 36 horas.

### 2.1 Restricciones no negociables (D151)

| # | Restricción | Origen |
|---|---|---|
| R1 | Las señales S6/S7/ST son **INTOCABLES**. Siguen corriendo el lunes como backup vivo. | D151 |
| R2 | El lote del campeón queda en **0.1**, pese al DD estimado −28,6%. "Esa cuenta es demo." | D151 |
| R3 | **Prohibido re-tunear** cualquier parámetro este fin de semana. | D151 |
| R4 | El retador es **aditivo o no es**. No puede modificar ningún objeto compartido. | Ver §4.2 |
| R5 | Todo número lo calcula **código**, nunca el LLM. | Regla vigente del proyecto |

## 3. Arquitectura

Una máquina (máq1, rama `equipo1`), una cuenta (DEMO 2883015767), **dos sleeves conviviendo**.

```
                      máq1 · DEMO 2883015767 · roster `local`
    ┌──────────────────────────────────┬──────────────────────────────────┐
    │  SLEEVE A — CAMPEÓN (control)    │  SLEEVE B — RETADOR              │
    ├──────────────────────────────────┼──────────────────────────────────┤
    │  S6-K2P0          magic 724010   │  S6-K2P0-R        magic 726010   │
    │  S7-TPNONE        magic 724020   │  S7-TPNONE-R      magic 726020   │
    │  SuperTrend-p14x3 magic 724070   │  SuperTrend-R     magic 726070   │
    │  TK-Momentum      magic 999999998│                                  │
    │                                  │                                  │
    │  lote 0.1 (TK 0.01) — INTOCADO   │  lote piloto 0.02                │
    │  sin gates de riesgo             │  + capa de riesgo B1–B4          │
    │  = comportamiento de HOY,        │                                  │
    │    byte por byte                 │                                  │
    └──────────────────────────────────┴──────────────────────────────────┘
                 señales IDÉNTICAS · misma vela · mismo motor
```

### 3.1 Por qué campeón/retador y no un reemplazo

Un reemplazo obligaría a apostar el lunes a que la capa de riesgo mejora las cosas, sin evidencia
para sostenerlo. El diseño paralelo convierte el despliegue en **un experimento que genera la
evidencia que hoy falta**: cada día vivo produce pares A/B sobre la misma señal, en el mismo
mercado, al mismo tiempo. Eso es evidencia genuinamente out-of-sample, y vale más que cualquier
backtest fabricable en 36 horas.

Comparación **por trade y normalizada por tamaño** ⇒ no requiere paridad de lote, que es lo que
permite correr el retador a 0.02 mientras el campeón sigue a 0.1 sin romper la lectura.

### 3.2 Por qué esto es también la garantía de backup

B es puramente aditivo: configs nuevas, banda de magics nueva, copias profundas. **B no puede
romper A.** Si el retador resulta ser un desastre, el campeón siguió corriendo intacto todo el
tiempo y el sistema del lunes es el sistema de hoy. El "riesgo de desplegar" es estructuralmente
cero.

## 4. Componentes

### 4.1 Sleeve A — campeón

`CONFIGS_LOCAL` tal como está hoy en `sentinel_engine/strategies/live_configs_20.py:572`.
**Cero cambios.** Magics 724010 / 724020 / 724070 / 999999998, volúmenes 0.1/0.1/0.1/0.01.

El criterio de éxito de esta pieza es negativo y se verifica por test: *después* de todo el
trabajo del lunes, `CONFIGS_LOCAL` debe seguir siendo byte-idéntico.

### 4.2 Sleeve B — retador

Un roster nuevo, `CONFIGS_CHALLENGER`, con **exactamente tres configs**: los espejos de S6-K2P0,
S7-TPNONE y SuperTrend-p14x3-M15. **TK-Momentum NO se espeja** — está en desarrollo, a 0.01, y no
es parte del track que se quiere comparar. El retador tiene 3 configs, no 4.

Se construye con el mismo patrón que ya usa `CONFIGS_LOCAL`:

```python
c = copy.deepcopy(<config go-live fuente>)   # copia PROFUNDA, nunca el objeto compartido
c["id"] = cid + "-R"
c["magic"] = 726000 + (magic_fuente - 724000)  # 726010 / 726020 / 726070
c["volume"] = 0.02
c["risk_gates"] = {...}                      # ver §4.3
```

**La banda 726xxx.** Las bandas 722xxx y 723xxx están **reservadas por assert**
(`live_configs_20.py:500`). La 725xxx la ocupa TK-BW2 de máq2. La 726xxx está libre y es la
siguiente en la secuencia. Se añaden los mismos asserts de disyunción que ya protegen las otras
bandas.

**La trampa de la copia profunda.** El archivo documenta explícitamente
(`live_configs_20.py:554`) que si un roster muta un objeto compartido en vez de copiarlo, el lote
de `tomachine` **se vuelve 0.1 en silencio**. Está probado por el snapshot
`tomachine-volume-None` de `tests/scripts/test_run_live_20.py`, y por los asserts de
inmutabilidad de `live_configs_20.py:594-599`. El retador replica esa disciplina y añade sus
propios asserts de inmutabilidad.

### 4.3 La capa de riesgo — cuatro wrappers

Todos son **gates de apertura**, se aplican **solo a configs del sleeve B**, y ninguno toca el
motor `simular_variant` (que está bajo parity gate y no se refactoriza).

**Mecanismo de aislamiento.** Se sigue el patrón ya establecido por `cfg["volume"]`: una clave
**opcional** `cfg["risk_gates"]`. Una config **sin la clave se comporta exactamente como hoy**.
Esta es la propiedad que hace que A no pueda verse afectada, y es verificable por test.

**Punto de inserción.** El camino de OPEN de `scripts/live/run_live_20.py`, donde ya vive
`SPREAD_GATE_SKIP` (`run_live_20.py:497`). Los wrappers son gates hermanos del que ya existe:
mismo lugar, misma forma, mismo logging. No se inventa arquitectura nueva.

| ID | Wrapper | Definición | Nota de honestidad |
|---|---|---|---|
| **B1** | Gap-wait post-apertura | No abrir hasta **≥50 min** después de que el spread baje a ≤0.5 tras la reapertura del mercado. | El 50 sale del diagnóstico previo ([[xauusd-market-open-gap-wait]]), no de un barrido de este fin de semana. |
| **B2** | Blackout de noticias | Calendario **estático, commiteado**. Ventana **30 min antes / 30 min después**. | El 30/30 es **por CONVENCIÓN, no ajustado**. Elegir el número por backtest sería re-tunear. |
| **B3** | Tope de exposición simultánea | Máximo de **fichas** abiertas a la vez en el sleeve. | Expresado en fichas, no en lotes ⇒ independiente del tamaño de posición. El número sale de la Pista A (§5.1); **si la Pista A no arroja un número defendible a tiempo, el tope es el pico observado de fichas simultáneas en los 7 meses** — un tope que no habría mordido nunca, y por lo tanto conservador por construcción. |
| **B4** | Legalidad de SL | Verificar que ningún SL quede bajo el mínimo del bróker (0,50). | **Si aparecen SL ilegales, es un BUG, no una optimización.** Se arregla como bug. |

Además: **tag de git sobre el commit vivo actual + revert de un paso probado**, para que revertir
el lunes sea una operación de un comando y no una improvisación.

### 4.4 La regla que sostiene la honestidad de todo esto

Cada wrapper se mide como **máscara retrospectiva** sobre las 2.347 posiciones de
`data/analysis/realtick_bt/positions_*.csv`: se aplica el filtro a las posiciones ya simuladas y
se mira qué habría pasado.

> **Ese número VETA si resulta catastrófico; NUNCA selecciona.**

Si la máscara muestra que el wrapper habría destruido el resultado, no se despliega. Pero **no se
usa para elegir entre variantes del wrapper** — elegir por ese número sería ajustar, y ajustar es
justo lo que no se puede hacer sin Fase 0 / Task 2.2 / Fase 12. Por eso B2 usa 30/30 por
convención en vez de barrer ventanas.

## 5. Las tres pistas

### 5.1 Pista A — auditoría (~4h, corre PRIMERO)

Corre primero porque **define los números de B** (concretamente el tope de B3). Todo se hace
sobre `data/analysis/realtick_bt/positions_*.csv` (2.347 posiciones: S6 912 / S7 1167 / ST 268;
columnas `side,ficha,reason,t_in,t_out,entry_fill,exit_fill,spread,entry_delay_bars,
net_067lot_clp,month`). **Sin re-simular nada.**

1. **Verificar el maxDD ≈−28,6%.** Hoy es una regla de tres (114.092.025 CLP @0.67 → ≈−17,0MM
   @0.1 → ≈−28,6% de los 59,6MM de la cuenta), sin verificar contra los CSV. La decisión de
   mantener 0.1 ya está tomada igual (R2), pero el número merece confirmarse antes de ponerlo en
   un documento.
2. **Solape y correlación S6/S7/ST** (Task 7.1). De aquí sale el tope de exposición de B3.
3. **Atribución por `exit_reason`** (Task 3.2).
4. **Correlación serial** (Task 3.4).
5. **Validar el gate de spread 0.5 sobre los 7 meses.** Hoy solo está validado sobre 5 sesiones
   vivas.

**Cabo suelto ya resuelto durante la escritura de este spec:** `CONFIGS_GOLIVE_DEDUP` **no está
sin usar** — está cableado como los rosters `golive-dedup` y `golive-dedup+tk`
(`run_live_20.py:940,954`). El roster `local` que corre hoy es su sucesor: el mismo dedup **menos
V11-M2**, con volumen por config (D142). La desduplicación ya ocurrió; no hay que re-proponerla.

### 5.2 Pista B — sleeve retador (~10–14h) — EL ENTREGABLE

Construir §4.2 + §4.3 con TDD por tarea, más el tag de git y el revert probado.

### 5.3 Pista C — entrada aleatoria (Task 3.1, ~4–6h CPU / ~1h humana)

Corre **en paralelo** mientras se codea B, porque no comparte archivos con ella. **No cambia nada
del lunes.** Su valor es que redirige las próximas semanas: responde si el edge vive en las
entradas o en las salidas. Si las entradas aleatorias con las mismas salidas rinden parecido,
fases enteras del plan v2 se cancelan.

### 5.4 El documento (~2h)

Qué cambió, qué no, **por qué las señales quedaron intocadas**, y el protocolo de lectura A vs B.

## 6. Manejo de errores

- **Fallo de un gate de riesgo** ⇒ el gate deniega la apertura y lo registra (mismo patrón que
  `SPREAD_GATE_SKIP`). Nunca lanza hacia el ciclo del executor: un bug en el wrapper del retador
  no puede tumbar el proceso que también corre al campeón.
- **Calendario de noticias ausente o corrupto (B2)** ⇒ **fail-closed**: sin calendario legible, el
  sleeve B no abre. Es la opción conservadora y solo afecta a B.
- **Violación de disyunción de bandas de magics** ⇒ `AssertionError` en tiempo de import. El
  proceso no arranca. Preferimos no arrancar antes que arrancar con magics cruzados, porque un
  cruce corrompe la contabilidad por estrategia de forma retroactiva.
- **SL ilegal detectado (B4)** ⇒ se trata como bug y se corrige; no se "compensa" con un wrapper.

## 7. Testing

TDD por tarea (`superpowers:test-driven-development`), y además tres guardias específicas de este
diseño:

1. **Guardia de no-regresión de A.** Snapshot de `CONFIGS_LOCAL` y `CONFIGS_TOMACHINE`
   (ids, magics, volúmenes). Falla si el trabajo del retador los tocó. Es la traducción a test de
   la garantía "B no puede romper A".
2. **Guardia de inmutabilidad.** Los objetos compartidos de `CONFIGS_GOLIVE` no deben ganar
   claves `volume` ni `risk_gates`. Mismo patrón que `live_configs_20.py:594-599`.
3. **Guardia de disyunción de bandas.** La banda 726xxx no intersecta live / shadow / go-live /
   TK / TK-BW2, y se mantiene fuera de las reservadas 722xxx-723xxx.
4. **Gates opt-in.** Una config sin `risk_gates` produce decisiones de apertura **byte-idénticas**
   a las de hoy.

`scripts/live/supervisor_live.py` y su test están **fuera del parity gate del motor**, así que la
superficie de despliegue puede modificarse sin tocar el golden master.

**Nota pre-existente:** hay 2 tests rojos en `test_web_positions.py` (botón "Analizar") que no son
de este trabajo y no lo bloquean.

## 8. Fuera de alcance (explícito)

Re-tuneo de cualquier parámetro · pirámide de fichas · meta-labeling · **Task 2.2** (requiere un
EA nuevo y un terminal) · sleeve de reversión a la media · tocar la **máquina 2** (rama `alvaro`,
repo de Álvaro — usarla requeriría coordinación y desplazaría TK-BW2) · resolver las V11-M2
huérfanas · registrar 2883016567 en `CUENTAS.md` (pendiente, pero no es del lunes).

## 9. Criterio de aceptación

El lunes a primera hora:

- [ ] Sleeve A corriendo, verificablemente idéntico a hoy (snapshot verde).
- [ ] Sleeve B corriendo a 0.02 con B1–B4 activos, en la banda 726xxx.
- [ ] Máscara retrospectiva corrida sobre las 2.347 posiciones para cada wrapper, con el veredicto
      registrado (veto / no-veto) y **sin haberla usado para seleccionar**.
- [ ] Tag de git sobre el commit vivo + revert de un paso probado.
- [ ] Pista A completa, con el maxDD confirmado o corregido.
- [ ] Documento entregado.
- [ ] Pista C corriendo o entregada (no bloquea el lunes).
