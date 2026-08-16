# DIAG-P03 -- por que los 95 brazos de P-03 (AC-deceleration) dan el mismo numero

**Rol:** investigador, report-only (charter SS B/C). Ningun numero de este fichero es veredicto ni
recomendacion. Rama `equipo1`. HEAD al escribir este reporte: `e6e6b0eb9f60912a24d3ab42b3efc32adc0cfcc3`.
No se toco ningun fichero de motor. Un unico script nuevo:
`research/fases/F0-preparacion/02-specs/diag_p03_activacion.py`.

---

## 1 · La pregunta

95 brazos de P-03 (grid `ac_decel_umbral` x `ac_decel_lookback` x `ac_modulate_hold_bars`, mas
`ac_off` y `factor<F>`), todos con `n=624`, `net_lote1=40246087.50` byte-identico, incluido `ac_off`
(mecanismo apagado). ?Por que.

## 2 · Comandos ejecutados y su salida real

```
python -m research.fases.F0-preparacion.02-specs.diag_p03_activacion
```
(hay un guion en `F0-preparacion`, no es un identificador Python valido como paquete de puntos;
el interprete lo resolvio igual desde la raiz del repo -- se deja el comando textual tal como se
ejecuto, ver salida completa abajo). Escribe
`research/fases/F0-preparacion/04-resultados/OLA1/P03-S6/diag_activacion.json` (unico artefacto de
datos nuevo).

Primera corrida escribio, por un bug de indexacion de `Path(...).parents[N]` en el script, en
`research/fases/04-resultados/...` (directorio jamas existente antes, no rastreado por git);
detectado, borrado (`rm -rf research/fases/04-resultados`, confirmado no rastreado con
`git status --short` antes de borrar), corregido `parents[2]`->`parents[1]`, re-corrido. La corrida
final es la que produjo el JSON citado en este reporte.

## 3 · El condicional y donde se consume -- `file:line`

- **Condicion** `ac_desacelerando`: `sentinel_engine/strategies/emasar_ref.py:291-307`.
  ```
  303  if idx < lookback or ac[idx] is None or ac[idx - lookback] is None:
  304      return False
  305  if direccion == +1:
  306      return (ac[idx - lookback] - ac[idx]) > umbral
  307  return (ac[idx] - ac[idx - lookback]) > umbral
  ```
  Nota de guardia: usa `is None` (no `pd.isna`), pero `ac` es una `list[float | None]` construida por
  `ac_series` con `None` explicito (`emasar_ref.py:109-114`), nunca `NaN` de pandas -- el guard es
  correcto para este tipo de dato, no hay caso de "silenciosamente nunca verdadero" por el
  `NaN`-vs-`None` senalado en el brief. Verificado: `n_ac_none=37` sobre 8.334 barras (warmup de
  `ao_sma5`), consistente con el guard.
- **Consumo**: `sentinel_engine/strategies/emasar_variant.py:992-998` (dentro del loop por ficha
  abierta, `if ac_modulate:` en 992):
  ```
  992  if ac_modulate:
  993      if ac_desacelerando(ac, i, f.lado, lookback=ac_decel_lookback,
  994                           umbral=ac_decel_umbral):
  995          ac_modulate_hold_by_tag[tag] = ac_modulate_hold_bars
  996      if ac_modulate_hold_by_tag.get(tag, 0) > 0:
  997          trail_efectivo = trail_efectivo * ac_modulate_factor
  998          ac_modulate_hold_by_tag[tag] -= 1
  ```
- **El corto-circuito de `ac_off`**: `ac_modulate: false` hace que la linea 992 nunca entre al
  bloque -- `ac_desacelerando` no se llama ni una vez. Confirmado por el spy (SS5, `paso4`):
  `ac_off` -> `n_calls=0`.
- **El punto que absorbe el efecto, inmediatamente despues** --
  `sentinel_engine/strategies/emasar_variant.py:999-1003`:
  ```
  999  # ATR14 trail floor (trail_atr_floor_k=0.0 default -> atr14_floor is
  1000 # None -> this block is skipped entirely, byte-identical no-op).
  1001 if atr14_floor is not None and atr14_floor[i] is not None:
  1002     trail_efectivo = max(trail_efectivo,
  1003                          trail_atr_floor_k * atr14_floor[i])
  ```
  `trail_efectivo` tras el bloque AC-modulate (linea 997, tras la multiplicacion por
  `ac_modulate_factor`) es **reescrito** por `max(trail_efectivo, trail_atr_floor_k*ATR14[i])`
  antes de usarse en ningun calculo de `f.sl` (primer uso: linea 1020, `nuevo_sl = f.max_fav -
  trail_efectivo`).

## 4 · Los kwargs vivos que fijan la escala del piso -- `file:line`

- `sentinel_engine/strategies/live_configs_20.py:256-257`:
  `_golive_m15("S6-K2P0", ac_modulate=True, trail_atr_floor_k=2.0, ...)`.
- `_GOLIVE_BASE_M15` (linea 232-239) trae `ac_modulate_factor=0.25` (heredado de la firma default
  de `_SKELETON`, no sobreescrito para S6-K2P0).
- `_SKELETON` (`live_configs_20.py:51-53`): `f1_trail_pips=f2_trail_pips=f3_trail_pips=100.0`
  (100 pips = 1.00 en unidades de precio, `pip_size("XAUUSD")=0.01`).
- `overlay_kwargs` (`scripts/analysis/realtick_bt/overlay.py:19-30`) parte de
  `copy.deepcopy(backtest._GL["S6-K2P0"])` -- es decir, TODOS los 95 brazos de P-03 heredan
  `ac_modulate=True, ac_modulate_factor=0.25, trail_atr_floor_k=2.0` salvo que su overlay los
  sobreescriba explicitamente; ninguno de los 90 brazos de la grilla sobreescribe
  `trail_atr_floor_k`, y solo `ac_off` sobreescribe `ac_modulate`.

## 5 · Los conteos (mide el script, `diag_p03_activacion.py`)

### 5.1 Sustrato
`n_bars=8334`, `n_ac_none=37`, `n_atr14_none=13` (warmup de 14 barras del Wilder ATR).

### 5.2 Cota superior de disparo sobre TODO el sustrato (bars=8334, ambas direcciones, cada celda
de la grilla preregistrada), `substrate=bars, non-verdict` (charter SS A.6) -- este numero cuenta
la barra como si hubiera una ficha abierta favorable en esa direccion, NO el disparo real
intra-simulacion (eso es la SS5.3):

(`n_total` = `n_long+n_short`, cota superior sobre `n_bars=8334`; porcentaje entre parentesis.)

| umbral (pips / unidades AC) | lookback=1 | lookback=2 | lookback=3 |
|---|---:|---:|---:|
| 10 / 0.10  | 7937 (95.2%) | 8100 (97.2%) | 8147 (97.8%) |
| 25 / 0.25  | 7407 (88.9%) | 7815 (93.8%) | 7942 (95.3%) |
| 50 / 0.50  | 6542 (78.5%) | 7359 (88.3%) | 7565 (90.8%) |
| 75 / 0.75  | 5718 (68.6%) | 6882 (82.6%) | 7221 (86.6%) |
| 100 / 1.00 | 4940 (59.3%) | 6414 (77.0%) | 6885 (82.6%) |
| 150 / 1.50 | 3662 (43.9%) | 5562 (66.7%) | 6232 (74.8%) |

Cifras exactas (`n_long`/`n_short` por celda) en el JSON producido, seccion
`paso2_cota_superior_disparo_por_umbral_lookback_TODO_el_sustrato`. La tabla es monotona
decreciente en umbral y monotona creciente en lookback en las 6x3 celdas medidas.

Referencia adicional (`umbral=0.0, lookback=1` -- fuera de la grilla P-03, sirve de ancla):
`n_long=4198, n_short=4098, n_total=8296` sobre 8296 barras con AC valido (`8334-37-1`).

**Estos numeros muestran variacion real y sustancial a traves de la grilla** (44.8% a 98.4% de
las barras) -- la condicion **no es never-true por unidades**: el hallazgo de unidades del commit
`979eb91` (pips x0.01) esta correctamente aplicado en el manifiesto
(`research/fases/F0-preparacion/03-runs/2026-08-16-ola1.yaml:9-13`, verificado:
`ac_decel_umbral: 0.25` para `umbral_pips: 25`, etc.) y produce disparo con frecuencia muy
distinta segun el umbral. **Esto descarta H1 tal como esta enunciada** ("la condicion nunca
dispara"): dispara, y dispara con frecuencias muy distintas por celda.

### 5.3 Disparo real dentro de una simulacion real (spy sobre `ac_desacelerando`, brazo `default`
de S6-K2P0, kwargs vivos sin overlay, sobre las 8.334 barras del sustrato):

`n_calls=13947` (numero de veces que el motor LLAMO a `ac_desacelerando` -- una vez por ficha
abierta y por barra, de ahi > 8334), `n_true=6306` -- **la condicion evalua verdadero 6.306 veces
en la simulacion real del brazo `default`.**

`ac_off`: `n_calls=0, n_true=0` (corto-circuito de la linea 992, SS3).

`n_eventos_default=2497`, `n_eventos_ac_off=2497`, **`eventos_default == eventos_ac_off` byte a
byte** (comparacion de listas de eventos completa, `True`).

### 5.4 El piso ATR vs. el trail (base y modulado)

Con los kwargs vivos de S6-K2P0 (`trail_atr_floor_k=2.0`, `f1/f2/f3_trail_pips=100.0` ->
`base_trail=1.00`, `ac_modulate_factor=0.25` -> `trail_modulado=0.25`), sobre las 8.321 barras
con ATR14 valido:

- `floor = 2.0 * ATR14[i]` -- percentiles medidos: p10=**14.43**, p50=**22.77**, p90=**46.87**;
  min=**8.67**, max=**148.86** (unidades de precio XAUUSD, USD).
- `n_floor_domina_trail_BASE_sin_modular = 8321 / 8321` (**100%**): el piso supera el trail SIN
  modular (1.00) en absolutamente todas las barras con ATR14 valido.
- `n_floor_domina_trail_MODULADO_por_AC = 8321 / 8321` (**100%**): el piso supera tambien el trail
  YA apretado por AC-modulate (0.25) en absolutamente todas las barras.

El valor MINIMO observado del piso en las 8.334 barras del sustrato (**8.67**) sigue siendo
**34.7x** el trail sin modular (1.00) y **34.7x** el trail modulado (0.25). No hay una sola barra
del sustrato donde el apriete de AC-modulate (con cualquier factor de la grilla: 0.10, 0.25, 0.50,
0.75) pudiera sobrevivir al `max(...)` de la linea 1002 -- ni el mas agresivo (`factor0.10` ->
trail=0.10) se acerca al piso minimo (8.67).

## 6 · Que hipotesis soporta la evidencia

- **H1 ("la condicion nunca dispara")**: refutada por la medicion. Dispara 6.306 veces en la
  simulacion real del brazo `default` (SS5.3), y la cota superior sobre el sustrato (SS5.2) muestra
  variacion sustancial (44.8%-98.4%) a traves de toda la grilla de umbrales -- no es un disparo
  constante en 0% ni en 100% que enmascare la pregunta.
- **H2 ("el parametro llega al motor pero el punto que alcanza no gobierna ninguna decision")**:
  soportada por la medicion, con el mecanismo exacto identificado: `trail_efectivo` SI se
  multiplica por `ac_modulate_factor` en la linea 997 (confirmado: el spy ve 6.306 disparos reales
  que ejecutan esa linea), pero el resultado de esa multiplicacion es **inmediatamente
  sobreescrito** por `max(trail_efectivo, trail_atr_floor_k*ATR14[i])` en la linea 1001-1003, y
  **el piso (minimo medido: 8.67) domina al trail modulado (maximo posible en la grilla: 1.00, sin
  ningun factor) en el 100% de las 8.321 barras con ATR14 valido**. La linea 1020
  (`nuevo_sl = f.max_fav - trail_efectivo`) -- el unico consumidor de `trail_efectivo` que decide
  el nivel del stop -- recibe siempre el mismo valor (el piso) sin importar `ac_decel_umbral`,
  `ac_decel_lookback`, `ac_modulate_hold_bars`, `ac_modulate_factor`, o si `ac_modulate` esta en
  True o False. Esto explica, con mecanismo de codigo verificado, por que `eventos_default ==
  eventos_ac_off` byte a byte (SS5.3) y por que los 95 `net_lote1` son identicos (`_brazos.txt`,
  ya en el repo antes de este diagnostico).
- El hallazgo de unidades del commit `979eb91` (pips x0.01) esta correctamente aplicado (SS4,
  `manifiesto.py`/YAML) y **no es la causa** de la planitud -- es una condicion necesaria para que
  el disparo tenga sentido (y la tiene: SS5.2/5.3 lo confirman), pero **la causa mecanica de la
  planitud es el piso `trail_atr_floor_k=2.0`, no la escala del umbral.**

## 7 · Lo que queda sin resolver

- No se investigo si `trail_atr_floor_k=2.0` domina tambien para S7-TPNONE o para timeframes
  distintos de M15 -- fuera del alcance (P-03 en Ola 1 solo corre sobre S6-K2P0).
- No se investigo la interaccion de AC-modulate con las OTRAS salidas que pueden cerrar una ficha
  antes de que el trailing (linea 1020) se evalue -- initial-SL, BE, ratchet, wait-MAE, TP
  escalonado -- es decir, no se descarta que en un sustrato o config distintos (piso mas bajo,
  volatilidad mas baja) el mecanismo SI llegara a ser vinculante en algunas fichas via esas otras
  rutas; esta medicion es especifica al sustrato y kwargs de Ola 1.
- No se corrio la ola completa ni el harness pareado para ninguna combinacion adicional (prohibido
  por el brief); toda la evidencia de esta seccion viene de una llamada directa a `simular_variant`
  (dos veces: `default` y `ac_off`) mas calculo directo de series sobre el sustrato -- no de
  `paired_harness.run_paired_arms` ni del runner.

## 8 · Rutas de los artefactos producidos

- `research/fases/F0-preparacion/02-specs/diag_p03_activacion.py` (script, nuevo)
- `research/fases/F0-preparacion/04-resultados/OLA1/P03-S6/diag_activacion.json` (datos, nuevo,
  `PRE-INTERPRETACION`)
- `research/fases/F0-preparacion/02-specs/DIAG-P03-progreso.md` (bitacora, nuevo)
- `research/fases/F0-preparacion/02-specs/DIAG-P03-reporte.md` (este fichero, nuevo)
