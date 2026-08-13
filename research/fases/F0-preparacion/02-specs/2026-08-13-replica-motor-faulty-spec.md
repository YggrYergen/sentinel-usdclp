# SPEC CERRADO — Réplica en harness del motor faulty

**Estado:** cerrado, listo para implementar. **Autor:** controlador (Opus 5).
**Insumos:** `04-resultados/T0.6-A-interfaces-motor-y-reconciliador.md` y
`04-resultados/T0.6-B-verdad-terreno-902.md`. **Decisiones que lo gobiernan:** D-39 a D-45.

## 0 · Qué se construye y por qué

Una **réplica en harness del motor que corrió en producción** (tag `engine-faulty-tomachine-902`
→ `b113eb7`), para poder correr backtests que reproduzcan lo que las estrategias realmente
hicieron. Se valida en dos hitos:

| Hito | Sustrato | Criterio de paso |
|---|---|---|
| **P-CAP** | ticks Capitaria, ventana 902 | **bit-idéntico** sobre precio e instante de entrada, instante y precio de salida, razón de cierre y resultado (D-45) |
| **P-AVA** | ticks AVA, misma ventana | lo más par posible; bit-idéntico es meta asintótica, no criterio de paso |

🔴 **R1-bis.** `emasar_variant.py`, `live_configs_20.py` y los módulos de estrategia vivos quedan
**byte-idénticos**. Todo lo de este spec va en ficheros **nuevos**. Quien concluya que hay que
tocar un original **PARA y escala**.

## 1 · El problema de diseño, y cómo se resuelve

El motor vivo **no guarda estado**: cada 15 s re-simula desde cero sobre las últimas
`window=10000` velas **cerradas** (`run_live_20.py:1244-1255` → `reconcile_config:387`,
`b113eb7`). El SL vigente vive en `f.sl`, sobrescrito barra a barra sin histórico
(`emasar_ref.py:260`, mutado en `emasar_variant.py:989-990` / `:1027-1028`). No hay evento de
trailing: sólo `ENTRY_*` y `EXIT_*`. El único acceso es `return_state=True`
(`emasar_variant.py:1441-1479`), que devuelve el estado **sólo de la última barra** de la lista.

**Hecho que lo hace tratable:** el ejecutor pide las velas con `include_forming=False`. El sim
sólo ve velas **cerradas** ⇒ su estado deseado es **constante entre cierres de vela**. Los ~60
ciclos de 15 s dentro de una vela ven todos exactamente lo mismo. Sólo cambia el mercado.

⇒ **El estado se calcula una vez por vela; los ciclos de 15 s se iteran encima.** Es exacto, no
una aproximación.

**Dos fases, y la primera valida a la segunda:**

- **Fase 1 (este spec, obligatoria para P-CAP).** Obtener el estado por vela llamando al motor
  **sin copiarlo**, con prefijos crecientes: `simular_variant(bars[i-W+1 : i+1], return_state=True)`
  para cada `i`. Es O(n²), pero la ventana 902 son ~1.440 velas M15 ⇒ ~1M pasos de barra: viable.
  **Riesgo de fidelidad: cero**, porque se usa el motor real.
- **Fase 2 (spec aparte, para la corrida larga).** Copia independiente del motor que anote el
  estado por barra en una sola pasada, **validada contra la Fase 1** hasta igualdad exacta sobre la
  ventana 902. No se implementa todavía.

## 2 · Componente A — `estado_por_barra`

**Fichero nuevo:** `scripts/analysis/realtick_bt/faulty/estado_por_barra.py`
**Test nuevo:** `tests/analysis/test_estado_por_barra.py`

### Contrato

```python
def estado_por_barra(
    bars: list[dict],          # velas M15 cerradas, orden ascendente por t
    kwargs: dict,              # kwargs de la estrategia (S6) tal como el roster vivo las pasa
    window: int = 10_000,      # ventana rodante del ejecutivo vivo
    idx_desde: int | None = None,
    idx_hasta: int | None = None,
) -> list[dict | None]:
    """Estado deseado del sim DESPUÉS de cerrar cada barra i.

    Devuelve una lista de la misma longitud que `bars`. El elemento `i` es el segundo
    valor de retorno de `simular_variant(..., return_state=True)` evaluado sobre
    `bars[max(0, i+1-window) : i+1]`, es decir el dict `desired` con forma
    `{ficha: {"side": "L"|"S", "sl": float, "entry": float}}`, o `{}` si no hay ficha
    deseada. Fuera de [idx_desde, idx_hasta] el elemento es None (no calculado).
    """
```

### Reglas de implementación

1. **Ventana rodante idéntica al vivo**: el corte es `bars[max(0, i+1-window) : i+1]`. El vivo
   nunca ve más de `window` velas cerradas; la réplica tampoco.
2. **No modificar `emasar_variant.py`.** Se importa y se llama. Si aparece la tentación de tocarlo:
   PARAR y escalar.
3. `idx_desde`/`idx_hasta` existen para acotar el coste: en P-CAP sólo hacen falta las velas de la
   ventana 902, pero **cada una necesita sus `window` velas previas**, que deben estar en `bars`.
4. La función es **pura**: mismas entradas ⇒ misma salida. Sin caché en disco, sin globals.
5. Para SuperTrend el motor **no** es `simular_variant` sino `supertrend_always_in_target`
   (`b113eb7:live_configs_20.py:306-338`), que ya devuelve el target directamente y es mono-ficha
   por construcción. Expón una segunda función `estado_por_barra_supertrend(bars, window)` con el
   mismo contrato de retorno.

### Test de aceptación (Componente A)

- Sobre un tramo de ≥200 velas reales del lago de Capitaria, para **cada** índice del tramo, el
  elemento `i` debe ser **exactamente igual** (`==` sobre el dict, sin tolerancia) a
  `simular_variant(bars[max(0,i+1-window):i+1], return_state=True)[1]`. Es tautológico por
  construcción y por eso mismo debe estar escrito: fija el contrato para la Fase 2.
- Caso borde `i < window`: el corte empieza en 0 y no falla.
- Caso `bars` vacío ⇒ lista vacía, sin excepción.

## 3 · Componente B — `ciclos`

**Fichero nuevo:** `scripts/analysis/realtick_bt/faulty/ciclos.py`
**Test nuevo:** `tests/analysis/test_ciclos_faulty.py`

Reproduce el bucle del ejecutor. **No importa `estado_por_barra`**: recibe la línea temporal de
estado ya calculada, para poder testearse con estados sintéticos.

### Contrato

```python
CYCLE_SEC = 15.0
BAR_SEC = 900

def correr_ciclos(
    estados: list[dict | None],   # salida del Componente A, indexada por barra
    bar_times: "np.ndarray",      # epoch de APERTURA de cada barra (cierre = t + BAR_SEC)
    ticks,                        # objeto con first_at(t) y range(t0,t1) -- ver §5
    t0: float, t1: float,         # ventana de simulación, epoch de servidor
    *,
    max_spread_open: float = 0.50,
    blocked_open_window: tuple = ((18, 0), (18, 45)),
    stops_level: float = 0.0,     # `level` de _clamp_sl, en unidades de precio
    cycle_sec: float = CYCLE_SEC,
) -> tuple[list[dict], list[dict]]:
    """Devuelve (posiciones, eventos)."""
```

`posiciones`: una fila por posición con
`t_open, precio_open, side, sl_open_deseado, sl_open_enviado, clamp_aplicado (bool),
t_close, precio_close, motivo_cierre ∈ {"SL","CLOSE_RECONCILER","FIN_VENTANA"}`.

`eventos`: una fila por evento con `t, tipo, detalle`, donde `tipo` ∈
`{"OPEN","MODIFY","CLOSE","SPREAD_GATE_SKIP","TIME_GATE_SKIP","OPEN_SKIPPED_SL_CROSSED",
"SL_CLAMPED","FALLBACK_CLOSE_INVALID_SL","NOOP"}`.

### Algoritmo por ciclo, en este orden exacto

Para `t` desde `t0` hasta `t1` en pasos de `cycle_sec`:

1. **Barra vigente.** `i = índice de la última barra cuyo CIERRE (bar_times[i] + BAR_SEC) <= t`.
   Si no hay ninguna, saltar el ciclo. `estado = estados[i]`.
2. **Tick vigente.** `tick = ticks.first_at(t)`, es decir el primer tick con `ts >= t`. Si no hay
   tick (mercado cerrado), saltar el ciclo sin emitir evento.
3. **Si `estado` desea ficha abierta y NO hay posición viva:**
   1. **TIME GATE.** Hora-del-día de servidor de `t`. Bloquea si `18:00:00 <= hhmmss < 18:45:00`
      (semi-abierto: `18:00:00` bloquea, `18:44:59` bloquea, `18:45:00` no).
      ⇒ `TIME_GATE_SKIP`, no abrir. **Sólo afecta a aperturas**, nunca a `CLOSE`/`MODIFY`.
   2. **SPREAD GATE.** `spread = tick.ask - tick.bid`. Si `spread > max_spread_open + 1e-6`
      ⇒ `SPREAD_GATE_SKIP`, no abrir. 🔴 Es un **cap duro `<=`**, NO una banda centrada.
   3. **CLAMP / CROSSED**, con `desired_sl = estado[ficha]["sl"]`:
      - long: `ref = tick.bid`; si `desired_sl >= ref` ⇒ `OPEN_SKIPPED_SL_CROSSED`, **no abrir**.
        Si `desired_sl > ref - stops_level` ⇒ `SL_CLAMPED`, `sl_enviado = ref - stops_level`.
        Si no ⇒ `sl_enviado = desired_sl`.
      - short: `ref = tick.ask`; si `desired_sl <= ref` ⇒ `OPEN_SKIPPED_SL_CROSSED`, **no abrir**.
        Si `desired_sl < ref + stops_level` ⇒ `SL_CLAMPED`, `sl_enviado = ref + stops_level`.
        Si no ⇒ `sl_enviado = desired_sl`.
   4. **OPEN a mercado.** `precio_open = tick.ask` si long, `tick.bid` si short.
      🔴 **El SL es `sl_enviado`, derivado del SL ACTUAL del sim — ya arrastrado por el trailing.**
      No se usa `estado[ficha]["entry"]` para nada. Esto es D-39 y es el corazón de la réplica.
4. **Si hay posición viva y `estado` la sigue deseando:** si `|estado[ficha]["sl"] - sl_vivo| > 1e-9`
   ⇒ aplicar la misma lógica clamp/crossed sobre el SL nuevo:
   - `crossed` ⇒ `FALLBACK_CLOSE_INVALID_SL`: **cerrar a mercado** en este tick.
   - `clamp` / `legal` ⇒ `MODIFY`: `sl_vivo = sl_enviado`.
5. **Si hay posición viva y `estado` ya NO la desea** ⇒ `CLOSE` a mercado en este tick
   (`precio_close = tick.bid` si long, `tick.ask` si short), motivo `CLOSE_RECONCILER`.
6. **Entre este ciclo y el siguiente** — el SL vive en el servidor del bróker: barrer
   `ticks.range(t, t + cycle_sec)` y, si el precio cruza `sl_vivo`
   (long: `bid <= sl_vivo`; short: `ask >= sl_vivo`), **cerrar en ese tick** con motivo `"SL"`.
   El barrido del SL tiene **prioridad sobre el ciclo siguiente**.
7. **Re-entrada.** No se codifica: **emerge**. Si el SL cerró la posición y el siguiente ciclo ve
   que el sim la sigue deseando, el paso 3 la vuelve a abrir. Es D4 y debe salir sola.

Al llegar a `t1`, toda posición aún abierta se cierra con motivo `FIN_VENTANA` y se marca.

### Test de aceptación (Componente B)

Con estados sintéticos y un stream de ticks sintético, cada uno su test:

1. Ficha deseada + spread `0.50` ⇒ abre. Spread `0.501` ⇒ `SPREAD_GATE_SKIP`.
   Spread `0.30` ⇒ **abre** (es cap, no banda — este test es el que blinda D5).
2. `t` a las `18:00:00`, `18:44:59` ⇒ `TIME_GATE_SKIP`. A las `18:45:00` ⇒ abre.
3. Long con `desired_sl >= bid` ⇒ `OPEN_SKIPPED_SL_CROSSED` y **ninguna** posición creada.
4. Long con `desired_sl` entre `bid - stops_level` y `bid` ⇒ `SL_CLAMPED`, `sl_enviado = bid - stops_level`.
5. Posición abierta cuyo SL se cruza entre dos ciclos ⇒ cierra **en el tick del cruce**, no al
   ciclo siguiente ni al cierre de barra.
6. SL cierra la posición y el sim la sigue deseando ⇒ **se reabre en el ciclo siguiente**
   (re-entrada secuencial). Verificar que jamás hay 2 posiciones vivas a la vez.
7. `estado` deja de desear la ficha ⇒ `CLOSE` con motivo `CLOSE_RECONCILER`.

## 4 · Parámetros del motor faulty (no re-derivar, ya verificados)

| Parámetro | Valor | Fuente |
|---|---|---|
| `active_fichas` S6-K2P0 | **1** | `b113eb7:live_configs_20.py:568`, assert `:597` |
| SuperTrend | mono-ficha por construcción | `b113eb7:live_configs_20.py:306-338` |
| Concurrencia real por estrategia | **1**, verificada sobre los deals | T0.6-B |
| `--interval` | **15.0** (cadencia real medida: mediana 15,77 s) | T0.6-A Q6 / T0.6-B Q11 |
| `--window` | **10000** velas cerradas | T0.6-A Q6 |
| `--max-spread-open` | **0.50**, cap duro `<=` con eps `1e-6` | T0.6-A Q10 |
| `--blocked-open-window` | **18:00-18:45**, semi-abierto, sólo OPEN | T0.6-A Q11 |
| `trail_atr_floor_k` | 2.0, **se aplica** | `live_configs_20.py:256` |
| `f1_trail_pips` | 100.0 (pip 0,01 ⇒ 1,00 USD) | `live_configs_20.py:51` |
| `init_sl_range_k` M15 | 2.5 | `live_configs_20.py:60` |
| lote | 0.67 con `max_volume` override | `live_configs_20.py:568-569`, `:560` |
| `MAX_FICHAS_PER_CONFIG` | **código muerto** — definido, nunca referenciado | T0.6-A Q13 |

**`stops_level` está sin determinar** y hay que derivarlo: de los eventos `SL_CLAMPED` del log
(`data/analysis/p_cap/sl_clamped_open_events.json`, 87 eventos) se despeja
`level = |ref - clamped|`. **Comprobar que sale constante**; si no lo es, reportarlo y PARAR.

## 5 · Qué reutilizar, no reescribir

- **Carga de ticks:** clase `Ticks` en `scripts/analysis/realtick_bt/backtest.py:85-160`, con
  `first_at(t_sec)` y `range(t0, t1)`. Ya maneja el particionado mensual del lago.
- **Carga de velas:** `load_bars()` en `backtest.py:75-83`.
- **Verdad de terreno:** `data/analysis/p_cap/verdad_terreno_902.csv` (152 filas) y
  `data/analysis/p_cap/eventos_ejecutor_902.csv` (1.710 filas), producidos por T0.6-B.
- 🔴 **NO modificar `backtest.py`.** Importar de él es correcto; editarlo no. Sus divergencias
  (D1–D10) se corrigen en los ficheros nuevos, no ahí.

## 6 · Gotchas verificados (leer antes de escribir código)

- 🔴 **Relojes, en las dos direcciones.** Los epochs de MT5 codifican el reloj de **servidor
  (UTC−4)** verbatim, y ese reloj **coincide con la hora local de Chile**.
  - epoch → datetime: `datetime.utcfromtimestamp()`. **Nunca** `fromtimestamp()`.
  - datetime → epoch: `calendar.timegm()`. **Nunca** `.timestamp()`.
  El controlador cometió la segunda y perdió 2 aperturas de borde (ver inventario §4.1). No hay
  ninguna conversión de zona horaria válida en este proyecto.
- El time gate del vivo usa `datetime.now()` — el reloj **local naive del SO**, con la asunción
  documentada de que equivale al del servidor (`b113eb7:run_live_20.py:184-198`). La réplica usa la
  hora-del-día de servidor del epoch: es el equivalente fiel **dado que la asunción se cumple**.
  Anotarlo como asunción heredada.
- El SL realmente enviado sólo consta en **61 de 152** aperturas (el log no imprime SL salvo en
  clamp). Por **D-45** esto **no bloquea** P-CAP: se mide y se reporta, sin poder de veto.
- La puerta de paridad del repo exige `-m slow`: `pytest tests/research/test_baseline_parity.py -q`
  sin ese flag devuelve **4 deselected** — un verde que no ejecutó nada.
- El denominador de A6 son **barras-señal (49 S6 / 42 ST)**, nunca las 152 posiciones: éstas son
  re-entradas secuenciales de una misma señal.

## 7 · Definición de HECHO

- [ ] Test escrito y visto **fallar** primero (pegar salida real)
- [ ] Implementación mínima; test en verde (pegar salida real)
- [ ] `pytest tests/analysis -q` sin regresiones, **en foreground** (pegar salida real)
- [ ] Commit acotado **sólo** a las rutas propias
- [ ] Ningún fichero vivo modificado: `git status --short` limpio fuera de las rutas propias

---

## §2-bis · ADDENDUM 2026-08-13 — La config DEBE venir del commit congelado, no del working tree

*(Añadido por el controlador tras una bandera correcta levantada por el implementador del
Componente A. **Aditivo:** no invalida nada de lo anterior.)*

### El problema

El Componente A quedó implementado consumiendo las kwargs de `_GOLIVE_M15`, según decía §2. Eso es
el **roster base**, y le falta lo que el vivo aplicaba encima. Medido:

| | Working tree | `b113eb7` (lo que realmente corrió) |
|---|---|---|
| `CONFIGS_TOMACHINE` | **4 configs**: S6-K2P0, S7-TPNONE, SuperTrend, TK-BW2-fix2atr | **2 configs**: S6-K2P0, SuperTrend |
| Procedencia | "trader selection **2026-07-22**" | "trader selection **2026-07-27**" |
| `volume` / `max_volume` | `None` / `None` | **0.67** / **0.67** |
| `active_fichas` en S6-K2P0 | **ausente** ⇒ default del motor = **3** | **1** |

Una réplica alimentada con el roster del working tree simularía **4 estrategias con 3 fichas cada
una**. Es exactamente la divergencia **D3**, reintroducida por la puerta de atrás.

⚠️ Nótese que esto **no contradice** el negativo ya registrado en `NEGATIVOS.md`: allí se verificó
que las kwargs **base** de `_GOLIVE_M15["S6-K2P0"]` son byte-idénticas entre ambas versiones —y lo
son—. Lo que difiere es el **override del roster tomachine** que se aplica encima. Dos cosas
distintas; ambas mediciones son correctas.

### La regla

🔴 **La réplica del motor faulty toma su configuración del commit congelado `b113eb7`, jamás del
working tree.** El working tree evoluciona con la investigación; el motor faulty no.

### Componente C — `config_faulty`

**Fichero nuevo:** `scripts/analysis/realtick_bt/faulty/config_faulty.py`
**Fichero nuevo (vendored):** `scripts/analysis/realtick_bt/faulty/_vendored_live_configs_20_b113eb7.py`
**Test nuevo:** `tests/analysis/test_config_faulty.py`

1. **Vendorizar** el módulo congelado, byte a byte:
   `git show b113eb7:sentinel_engine/strategies/live_configs_20.py > <ruta vendored>`
   Sin editarlo. Ni una línea, ni el encoding, ni los finales de línea.
2. `config_faulty.py` expone:
   ```python
   def configs_tomachine() -> list[dict]:
       """Los 2 configs del roster tomachine tal como corrieron en la 902, desde b113eb7."""
   def kwargs_de(config_id: str) -> dict:
       """kwargs efectivas de 'S6-K2P0' o 'SuperTrend-p14x3-M15', con el override del roster."""
   ```
   Importa del módulo vendorizado, **nunca** de `sentinel_engine.strategies.live_configs_20`.
3. **Test anti-deriva (el que da valor a todo esto):**
   `git hash-object <ruta vendored>` debe ser **igual** a `git rev-parse b113eb7:sentinel_engine/strategies/live_configs_20.py`.
   Si alguien edita el vendorizado, el test se pone rojo. Es la garantía de que la copia no se
   despega del motor que replica.
4. **Tests de contenido**, todos con aserción exacta:
   - `configs_tomachine()` devuelve **exactamente 2** configs, con ids `S6-K2P0` y `SuperTrend-p14x3-M15`.
   - `kwargs_de("S6-K2P0")["active_fichas"] == 1`.
   - `volume == 0.67` y `max_volume == 0.67` en ambos.
   - `SuperTrend-p14x3-M15` lleva `engine == "supertrend_always_in"` y **no** lleva `active_fichas`.

### Consecuencia sobre el Componente A

**No hay que reescribirlo.** `estado_por_barra(bars, kwargs, ...)` recibe las kwargs como parámetro:
basta con que **el llamador** las tome de `config_faulty.kwargs_de(...)` en vez de `_GOLIVE_M15`.
La corrección vive en el llamador, que aún no existe. Queda anotado aquí para que quien lo escriba
no repita el error.

---

## §3-bis · ADDENDUM 2026-08-13 — `motivo_cierre` de `FALLBACK_CLOSE_INVALID_SL`

*(Añadido por el controlador resolviendo una escalada correcta del implementador del Componente B,
que detectó que el enum de §3 no cubría este caso y lo señaló en vez de inventar. **Aditivo.**)*

### El hueco

§3 define `motivo_cierre ∈ {"SL", "CLOSE_RECONCILER", "FIN_VENTANA"}`, pero el paso 4 del algoritmo
puede cerrar una posición por `FALLBACK_CLOSE_INVALID_SL` — el SL nuevo ya está cruzado al intentar
un `MODIFY`, así que el ejecutor cierra a mercado en vez de mandar un `MODIFY` inválido. No hay
valor para eso.

### La resolución

🔴 **`FALLBACK_CLOSE_INVALID_SL` recibe su propio valor.** El enum pasa a ser:

```
motivo_cierre ∈ {"SL", "CLOSE_RECONCILER", "FALLBACK_CLOSE_INVALID_SL", "FIN_VENTANA"}
```

**No se colapsa en `"SL"`.** Razón: un `SL` lo ejecuta el **bróker** contra un stop server-side; un
fallback es una **orden de cierre a mercado que manda el ejecutor**. Son eventos distintos, dejan
`reason` distinto en el historial de MT5, y la **razón de cierre está dentro del criterio de paso de
P-CAP** (D-45). Colapsarlos rompería exactamente la comparación que el hito mide.

### 🟡 Cuestión abierta que esto destapa — NO resolver por conjetura

El mapeo de los motivos de la réplica a los `reason` de MT5 del historial real **no cuadra todavía**,
y hay que resolverlo con datos antes de construir el comparador:

- Historial real de la ventana canónica: **118 SL · 21 EXPERT · 11 manuales · 1 TP**.
- Log del ejecutor en la misma ventana: **3** acciones `CLOSE` y **9** `FALLBACK_CLOSE_INVALID_SL`.

3 + 9 = 12, contra **21** cierres con `reason=EXPERT`. **Faltan 9 por explicar.** Hipótesis que
habrá que discriminar con el dato, sin elegir ninguna ahora: cierres por `stop_and_reverse`, cierres
emitidos fuera de las acciones contabilizadas, o un desfase entre lo que el log tabula y lo que el
bróker registra.

**Consecuencia operativa:** la tabla de equivalencia `motivo_cierre` ↔ `reason` de MT5 **queda sin
fijar** en este spec. Se determina empíricamente al construir el comparador de P-CAP, cruzando
`data/analysis/p_cap/verdad_terreno_902.csv` con `data/analysis/p_cap/eventos_ejecutor_902.csv`.
Quien lo construya **no debe asumir** la equivalencia: debe medirla y reportar los residuos.
