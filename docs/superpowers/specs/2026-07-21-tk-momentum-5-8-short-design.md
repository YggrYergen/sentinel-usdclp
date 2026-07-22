# TK-Momentum-5-8-short — live-forward strategy (design)

> Fecha: 2026-07-21 · Cuenta: DEMO 2883015767 (Capitaria-All, ~59,6 MM CLP,
> verificado en vivo) · Símbolo: XAUUSD · Magic (posición): **999999999**
> Estado: aprobado por el trader; test forward en vivo (no es un edge probado).

## Objetivo

Un trader quiere ver EN VIVO una estrategia nueva de momentum/medias sobre oro,
corriendo junto a las demás en el MT5 ya abierto de esta máquina, con su propio
magic de "puros nueves". Es un **motor nuevo, aditivo**: no toca los motores
existentes (`simular_variant`, `supertrend_always_in`) ni sus rosters.

## Señales (velas M6 CERRADAS, sobre precios de cierre)
<!-- M6 desde 2026-07-21 (era M10); ver Addendum "M10 -> M6" al final. -->


- `SMA5` = media móvil **simple** de 5 periodos.
- `SMA8` = media móvil **simple** de 8 periodos.
- `MOM2` = momentum de 2 periodos = `close[i] / close[i-2] * 100` (iMomentum
  estándar de MT5). Oscila alrededor de 100.

Warmup: señales válidas desde el índice `i >= 7` (SMA8 necesita 8 cierres; MOM2
necesita `i-2`).

## Régimen (filtra SOLO la apertura)

- `SMA5[i] < SMA8[i]` → régimen bajista → **solo se permiten cortos**.
- `SMA5[i] > SMA8[i]` → régimen alcista → **solo se permiten largos**.
- `SMA5[i] == SMA8[i]` → sin permiso, no abre.

## Entrada (cruce real del 100, UNA sola posición)

Solo se evalúa si se está **plano** al entrar a la vela `i`:

- **Corto**: régimen bajista **y** MOM2 cruza a la baja el 100
  (`MOM2[i-1] >= 100` **y** `MOM2[i] < 100`) → abre corto al `close[i]`.
- **Largo**: régimen alcista **y** MOM2 cruza al alza el 100
  (`MOM2[i-1] <= 100` **y** `MOM2[i] > 100`) → abre largo al `close[i]`.

Sin pirámide ni re-entrada mientras haya posición. Sin re-entrada en la misma
vela en que se cerró (se espera a la próxima vela).

## Salida (lo que ocurra PRIMERO)

Con posición abierta, en cada vela `i` (en este orden de prioridad):

1. **Trailing stop 0.6 USD** (SL server-side): el SL en vigor durante la vela
   `i` proviene de la excursión favorable hasta `i-1`. Si el precio lo toca:
   - Corto: `high[i] >= sl` → cierre al SL (stop-out).
   - Largo: `low[i]  <= sl` → cierre al SL (stop-out).
2. **Reversión del momentum**: si no hubo stop-out:
   - Corto: MOM2 cruza al alza el 100 → cierre al `close[i]`.
   - Largo: MOM2 cruza a la baja el 100 → cierre al `close[i]`.

Si sigue abierta, se **arrastra** el SL (solo se aprieta, nunca se afloja):
- Corto: `extremo = min(extremo, low[i])`, `sl = min(sl, extremo + 0.6)`.
- Largo: `extremo = max(extremo, high[i])`, `sl = max(sl, extremo - 0.6)`.

SL inicial al abrir: corto `entry + 0.6`, largo `entry - 0.6` (extremo = entry).

> Nota operativa: la distancia mínima legal de stop del broker para XAUUSD es
> **0.5 USD** (`trade_stops_level` = 50 puntos × 0.01, verificado en vivo), por
> lo que un SL a 0.5 es ilegal. El trader eligió (2026-07-21) un trailing de
> **3.0 USD** — cómodamente legal (sin clamping) y con más aire para la posición.

## Contrato con el reconciliador (parity-by-construction)

`tk_momentum_5_8_target(bars, *, trail_usd=0.5)` reproduce las barras y emite el
MISMO snapshot que consume el reconciliador (igual que `supertrend_always_in`):

```
{"open": {"F1": {"side": "L"|"S", "entry": float, "sl": float, "max_fav": float}} | {},
 "last_bar_exits": {}, "last_idx": n-1}
```

Una sola ficha **F1** (posición única). El reconciliador abre (OPEN), arrastra
el SL (MODIFY) y, al quedar plano, cierra el huérfano (CLOSE) — sin cambios en
el reconciliador. El SL siempre presente satisface la exigencia de SL en OPEN.

## Despliegue

- Config independiente en `live_configs_20.py`:
  `id="TK-Momentum-5-8-short"`, `tf="M6"`, `engine="tk_momentum"`,
  `kwargs={"symbol":"XAUUSD","trail_usd":0.6}`, `magic_base = 999999998`
  (⇒ F1 = **999999999**, "puros nueves", lo que ve el trader).
- Banda magic `{999999999, 1000000000, 1000000001}` — disjunta de todas las
  bandas en uso (720xxx/721xxx/724xxx, legacy 33xxxx, 710000, 900xxx). Assert.
- Roster propio `--configs tk-momentum` → corre como proceso AISLADO junto a lo
  demás. Volumen `0.01`/ficha. Sin adaptive-spread (evita carrera con el store).
- `run_live_20.py`: rama de dispatch `engine=="tk_momentum"`, rama de roster,
  y M6 añadido a `TF_MT5_MINUTES`/`TF_SECONDS` (6 / 360).
- Seguridad SIN cambios: `guard_cuenta.assert_demo` (login 2883015767 = DEMO,
  verificado), dry-run por defecto, arma con `--confirm-account 2883015767`.

## Addendum 2026-07-21 — modo INTRA-VELA (pedido del trader)

Por defecto el motor es close-driven (actúa al cerrar la vela M6). A pedido del
trader se agregó **modo intra-vela** (`intrabar=True` en kwargs): el ejecutor
evalúa la señal sobre la **vela en formación** (precio actual) y **entra apenas
se cumplen las condiciones, sin esperar el cierre**. Implementación: `fetch_bars(
include_forming=True)` conserva la vela en formación como última barra y el motor
la evalúa igual que una cerrada. Decisión asociada: tras un stop, **se reabre si
la condición sigue vigente** (sin guardia anti-churn — elección del trader).

> Trade-off honesto: intra-vela **repinta** (una señal a mitad de vela puede
> desaparecer antes del cierre) y la operativa **deja de coincidir con el
> backtest** (que es por cierre). Puede además generar más entradas/salidas
> (churn) que el modo por cierre.

## Addendum 2026-07-21 — timeframe M10 → M6 + invariante "una sola posición"

Pedido del trader: **verla reaccionar más rápido** → se cambió el timeframe de
**M10 a M6**. Los periodos `5/8/2` se **mantienen** (cuentan velas, no minutos),
así que ahora abarcan **30 / 48 / 12 min** en vez de 50 / 80 / 20 → mismo diseño,
reacción más rápida y más señales (a costa de más ruido/churn y stops más
frecuentes; el trailing `3.0 USD` no cambia). Implementación: `M6` añadido a
`TF_MT5_MINUTES`/`TF_SECONDS` (6 / 360) y `tf="M6"` en la config; el motor es
timeframe-agnóstico (opera sobre las velas que reciba).

Además el trader pidió **garantizar máximo UNA posición abierta** para TK, nunca
más de una. El motor ya era single-slot por construcción (`pos` es un único
hueco → emite a lo sumo `F1`); se **blindó** con: (1) un `assert len(open) <= 1`
en la rama `tk_momentum` del ejecutor (falla cerrado antes de mandar una 2ª
orden si un cambio futuro rompiera la invariante), y (2) un test aleatorizado
(`test_never_more_than_one_open_position`, 400 series) que fija que ninguna
secuencia produce >1 ficha.

## Addendum 2026-07-21 (v2) — entrada por ESTADO (no por cruce)

Pedido del trader: que la entrada sea un **estado**, no un cruce. Motivación: con
la lógica de cruce, tras consumir un cruce del 100 la estrategia se quedaba fuera
aunque las medias siguieran al alza y el momentum sobre 100 (ver diagnóstico
2026-07-21: régimen alcista + MOM2>100 sostenido, pero sin gatillo porque no había
un cruce nuevo). El trader quiere entrar **siempre que se cumplan las dos
condiciones**.

### Entrada (CAMBIA)
Estando **plano** y con los indicadores calentados, en cada vela M6 se evalúa el
ESTADO (nivel, no evento):
- **LARGO** si `SMA5 > SMA8` **y** `MOM2 > 100`.
- **CORTO** si `SMA5 < SMA8` **y** `MOM2 < 100`.
- Se abre apenas se cumplen **ambas** condiciones (ya no se exige `m_prev` a un
  lado del 100). Igualdades (`SMA5 == SMA8` o `MOM2 == 100`) NO abren (desigualdad
  estricta). Si ambos estados fueran imposibles a la vez, no hay ambigüedad; el
  código evalúa corto y luego largo (mutuamente excluyentes por construcción).

El régimen de medias sigue siendo **solo puerta de apertura**: filtra qué lado se
permite abrir, no fuerza el cierre.

### Salida (NO cambia)
Igual que hoy, en este orden por vela: (1) **trailing stop `trail_usd` (3.0)** —
SL server-side que solo se aprieta (ratchet); (2) **reversión de momentum** —
MOM2 cruza el 100 de vuelta (largo cierra si MOM2 baja del 100; corto si sube).
Nota de asimetría intencional (elección del trader "mantener salida actual"): la
entrada es por nivel y la salida por cruce/trailing; un giro de medias por sí solo
NO cierra la posición (solo lo hacen el trailing o la reversión de momentum).

### Una sola posición (NO cambia, blindado)
Un único slot → ficha F1 (magic 999999999). Se mantiene el `assert len(open) <= 1`
en la rama `tk_momentum` del ejecutor y el test aleatorizado.

### Re-entrada = vela SIGUIENTE (NO cambia la guarda)
Se conserva la guarda "no re-entrada en la misma vela en que salió": la entrada
solo ocurre si la posición estaba **plana al INICIO** de la vela (`pos is None and
not exited_this_bar`). Así, tras una salida, si el estado sigue vigente, re-entra
en la **próxima** vela M6 — nunca abre/cierra dentro de la misma vela en
formación (evita churn intra-vela extremo). En intra-vela esto se traduce en: si
el trailing la saca a mitad de vela, no re-abre hasta que empiece la vela
siguiente.

### Implicación honesta
Entrada por estado ⇒ la estrategia estará **en posición casi todo el tiempo** que
régimen y momentum coincidan (entra mucho antes y más seguido que con el cruce),
y con el trailing ajustado de 3.0 USD re-entrará vela-a-vela con frecuencia →
**muchas más operaciones/costos** que la versión de cruce. Es el comportamiento
elegido explícitamente.

### Cambio de código
- `sentinel_engine/strategies/tk_momentum.py`: reemplazar el bloque de entrada
  (cruce `down_cross`/`up_cross`) por estado (`maf < mas and m_now < 100` →
  short; `maf > mas and m_now > 100` → long). `m_prev` deja de usarse para la
  entrada (sigue usándose para la reversión de salida y el guard de warmup).
- Reescribir los tests de entrada de `tests/strategies/test_tk_momentum.py` para
  el contrato de estado (bajo estado, las series monótonas abren en la PRIMERA
  vela calentada donde se cumple el estado, no en el cruce). Salida, trailing,
  ratchet, single-position y no-same-bar-reentry se conservan.
- Docstrings de `tk_momentum.py` actualizados (entrada por estado).
- Gate localizado (suite TK + parity golden) + redespliegue (reinicio del
  ejecutor supervisado para reimportar el motor).

## Testing

- `tests/strategies/test_tk_momentum.py`: warmup/flat, régimen bloquea el lado
  contrario, entrada por cruce (no por nivel), salida por reversión, stop-out
  por trailing, arrastre monótono del SL, sin re-entrada misma vela, forma del
  snapshot lista para el reconciliador.
- Config/roster: id/tf/engine/magic 999999999 y disjunción de banda.
- Gate: la suite completa + parity golden 3/3 deben quedar verdes.
- Verificación en vivo: un ciclo `--once` en dry-run mostrando las intenciones
  antes de armar.
