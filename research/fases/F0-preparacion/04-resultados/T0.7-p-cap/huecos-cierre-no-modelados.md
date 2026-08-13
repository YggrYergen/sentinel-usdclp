# Huecos de cierre no modelados por la réplica — SAME_BAR_EXIT_FALLBACK y TP

**Rol:** Sonnet 5 high effort · INVESTIGADOR (report-only). Sin interpretación, sin recomendación,
sin propuesta de diseño.

**Motor congelado:** commit `b113eb7471c104f9178518c02365129818c203e8` (2026-07-27 18:51:46 -0400),
leído exclusivamente con `git show b113eb7:<ruta>` / `git grep ... b113eb7 -- <rutas>`. No se hizo
`checkout`; el working tree no fue tocado.

**Réplica auditada (sólo lectura):** `scripts/analysis/realtick_bt/faulty/ciclos.py`.

**Fuentes de datos:** `data/analysis/p_cap/eventos_ejecutor_902.csv`,
`data/analysis/p_cap/verdad_terreno_902.csv`, `data/analysis/2883016902/2883016902_deals_raw.csv`,
`data/analysis/2883016902/2883016902_positions.csv`.

---

## Hueco 1 — `SAME_BAR_EXIT_FALLBACK`

### 1.1 · Condición exacta que lo dispara (reconciliador)

Fichero: `sentinel_engine/live/reconciler.py` en `b113eb7` (302 líneas totales).

El comentario en `reconciler.py:194-201` distingue dos variantes dentro del mismo bucle de cierre
de "huérfanos":

```python
# reconciler.py:192-201
    for tag in FICHA_TAGS:
        ...
    # Two flavors:
    #   (a) SAME_BAR_EXIT_FALLBACK -- the sim exited this ficha DURING the just
    #       -closed bar (present in last_bar_exits) using that bar's own high/AC.
    #       Live's server-side SL sat at the prior bar's level so the broker did
    #       NOT stop it out mid-bar. Close at MARKET (next tick) and record the
    #       by-design price gap (sim exit level vs live market fill) + its $
    #       cost. NOT a divergence -- "same-bar optimism, by design".
    #   (b) plain orphan -- the ficha was already flat in the sim before this
    #       bar (a stale live position); ordinary CLOSE.
```

La condición **real** (no la paráfrasis del comentario) está en el código, `reconciler.py:202-224`:

```python
# reconciler.py:202-224
    for tag in FICHA_TAGS:
        if tag in live_by_tag and tag not in open_state:
            p = live_by_tag[tag]
            magic = base_magic + FICHA_OFFSET[tag]
            ex = last_bar_exits.get(tag)
            if ex is not None:
                side = _SIDE_NORM_L.get(str(ex.get("side")).upper(), "?")
                res.actions.append(Action(
                    "SAME_BAR_EXIT_FALLBACK", config_id, magic, tag,
                    side=side, ticket=p.get("ticket"), volume=p.get("volume"),
                    sim_fill=ex.get("price"), motivo=ex.get("motivo"),
                    reason=(...)))
            else:
                res.actions.append(Action(
                    "CLOSE", config_id, magic, tag,
                    ticket=p.get("ticket"), volume=p.get("volume"),
                    reason="sim has this ficha flat; live position orphaned"))
```

La condición exacta, en términos del código, es la conjunción de tres hechos evaluados por ficha
(`tag` en `F1`/`F2`/`F3`):

1. `tag in live_by_tag` — hay una posición viva en MT5 para esa ficha (`reconciler.py:203`).
2. `tag not in open_state` — el sim (`simular_variant(..., return_state=True)`) ya NO desea esa
   ficha abierta al cierre de la barra recién cerrada (`reconciler.py:203`).
3. `ex = last_bar_exits.get(tag)` **no es `None`** (`reconciler.py:206-207`) — el propio sim tiene
   registrado, en el snapshot `last_bar_exits` (segunda mitad de la tupla devuelta por
   `_split_snapshot`, `reconciler.py:107-115`), que ESA ficha salió DENTRO de la barra que acaba de
   cerrar (no antes).

Si (1) y (2) se cumplen pero (3) es falsa (`ex is None`), la rama es un `CLOSE` ordinario
("huérfano" — la ficha ya estaba plana en una barra anterior). `SAME_BAR_EXIT_FALLBACK` sólo se
dispara cuando además el sim aporta la evidencia explícita de que la salida ocurrió durante la
barra que se está reconciliando ahora mismo.

### 1.2 · Qué información lleva la acción y de dónde sale

`Action` (`reconciler.py:54-76`) declara los campos:

```python
# reconciler.py:67-68
    sim_fill: float | None = None    # SAME_BAR_EXIT_FALLBACK: sim's exit level
    motivo: str | None = None        # SAME_BAR_EXIT_FALLBACK: sim exit motivo
```

y `reconciler.py:76`:

```python
    def sendable(self) -> bool:
        return self.kind in ("OPEN", "CLOSE", "MODIFY", "SAME_BAR_EXIT_FALLBACK")
```

En la construcción de la acción (`reconciler.py:210-219`):
- `sim_fill = ex.get("price")` — el precio de salida que calculó el sim para esa barra.
- `motivo = ex.get("motivo")` — la razón de salida que registró el sim (p. ej. `EXIT_INITSL`, ver
  §1.6).
- `side = _SIDE_NORM_L.get(str(ex.get("side")).upper(), "?")` — el lado de la ficha normalizado.
- `ticket = p.get("ticket")`, `volume = p.get("volume")` — de la posición viva en MT5
  (`live_by_tag[tag]`), no del sim.

Los tres primeros (`price`, `motivo`, `side`) provienen de `ex = last_bar_exits.get(tag)`, es decir
del diccionario `last_bar_exits` de la parte "rica" del snapshot de `simular_variant(...,
return_state=True)` (`reconciler.py:9-11, 107-115`): el módulo no lo calcula, lo recibe ya calculado
del simulador.

### 1.3 · Qué hace el ejecutor con la acción

Fichero: `scripts/live/run_live_20.py` en `b113eb7` (1266 líneas totales).

Docstring de `execute_action` (`run_live_20.py:510-512`):

```python
      * SAME_BAR_EXIT_FALLBACK -> market-close the ficha; account the by-design
        price gap (sim exit level vs live market fill) into `same_bar_cost`
        keyed by config_id ("same-bar optimism, by design" -- NOT a divergence).
```

**Dry-run** (`run_live_20.py:615-618`): sólo añade `sim_fill=... motivo=...` al mensaje de log; no
manda nada.

**Camino armado** (`run_live_20.py:652-703`): `SAME_BAR_EXIT_FALLBACK` entra por la MISMA rama que
`CLOSE`:

```python
# run_live_20.py:652-667
    if a.kind in ("CLOSE", "SAME_BAR_EXIT_FALLBACK"):
        pos = None
        for p in (mt5.positions_get(ticket=a.ticket) or []):
            pos = p
        if pos is None:
            logger.warning("  [%s] ticket %s not found (already closed?)", a.kind, a.ticket)
            return
        tick = mt5.symbol_info_tick(symbol)
        is_long = getattr(pos, "type", 0) == getattr(mt5, "POSITION_TYPE_BUY", 0)
        price = tick.bid if is_long else tick.ask
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
               "volume": float(getattr(pos, "volume", a.volume or 0.0)),
               "type": mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY,
               "position": int(a.ticket), "price": price, "deviation": deviation,
               "magic": int(a.magic), "comment": f"{a.config_id}:{a.ficha}:close",
               "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)}
```

**¿A qué precio?** `price = tick.bid if is_long else tick.ask` (`run_live_20.py:661`) — el precio de
MERCADO del tick vigente en el momento del cierre, NO el `sim_fill` que trae la acción. `sim_fill`
sólo se usa después, para calcular el gap contable (`run_live_20.py:691-696`):

```python
# run_live_20.py:687-696
        if a.kind == "SAME_BAR_EXIT_FALLBACK":
            gap = 0.0
            if a.sim_fill is not None:
                d = (price - a.sim_fill) if is_long else (a.sim_fill - price)
                gap = d * float(getattr(pos, "volume", a.volume or 0.0)) * contract_size
            if same_bar_cost is not None:
                same_bar_cost[a.config_id] = same_bar_cost.get(a.config_id, 0.0) + gap
```

**¿Cierra a mercado?** Sí — `req["action"] = mt5.TRADE_ACTION_DEAL` (`run_live_20.py:662`), idéntico
tipo de orden que un `CLOSE` ordinario.

**¿Pasa por el gate de spread?** No. El bloque del gate de spread está condicionado explícitamente a
`if a.kind == "OPEN":` (`run_live_20.py:580`); `SAME_BAR_EXIT_FALLBACK` nunca entra en ese bloque
(entra en la rama `a.kind in ("CLOSE", "SAME_BAR_EXIT_FALLBACK")`, `run_live_20.py:652`, posterior al
bloque del gate). El propio docstring lo dice: "Exits / MODIFY / CLOSE are NEVER gated (they must
always be free to run risk management)" (`run_live_20.py:576-577`) y, en la sección `SPREAD_GATE_SKIP`:
"Exits / MODIFY / CLOSE are never gated" (`run_live_20.py:535-536`).

El test citado en el brief lo confirma explícitamente:

```python
# tests/live/test_executor_dryrun.py:788-799
def test_spread_gate_never_gates_same_bar_exit_fallback():
    # SAME_BAR_EXIT_FALLBACK (a market exit) must be sent despite a wide spread.
    pos = _Pos(ticket=779, magic=101, type=MockMT5.POSITION_TYPE_BUY,
               volume=0.01, sl=1990.0)
    mt5 = _wide_spread_mt5(positions=[pos])
    a = Action(kind="SAME_BAR_EXIT_FALLBACK", config_id="SS-M1", magic=101,
               ficha="F1", side="L", ticket=779, volume=0.01, sim_fill=2001.5,
               motivo="sar", reason="same-bar exit")
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                               max_spread_open=0.70)
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_DEAL
```

`_wide_spread_mt5` construye un spread por encima del cap (`max_spread_open=0.70`) y el envío
igualmente se produce (`len(mt5.sent) == 1`), confirmando que el gate de spread no aplica a esta
acción.

### 1.4 · ¿Es distinguible de un `CLOSE` normal desde fuera?

**No, por el request que se manda.** El request de `SAME_BAR_EXIT_FALLBACK` y el de `CLOSE`
ordinario se construyen con el MISMO diccionario `req` (`run_live_20.py:652-667`, ver §1.3), incluido
el `comment` — `f"{a.config_id}:{a.ficha}:close"` (`run_live_20.py:666`) — idéntico texto para ambos
`a.kind`. La única diferencia está en el LOG local del ejecutor tras el envío
(`run_live_20.py:697-703`: `[SAME_BAR_EXIT_FALLBACK] ... sim_fill=... motivo=...` vs
`[SENT CLOSE] ticket=...`), que no viaja a MT5.

Esto se confirma empíricamente contra los 10 casos reales (§1.6): sus deals `OUT` en
`data/analysis/2883016902/2883016902_deals_raw.csv` llevan todos `comment = "S6-K2P0:F1:close"` y
`reason = "3"` — el mismo formato de comentario y el mismo código de razón MT5 que un `CLOSE`
ordinario (`reason=3` = `DEAL_REASON_EXPERT`, según el comentario de
`scripts/live/run_deals_watcher.py:137-138`: `"reason (DEAL_REASON_* int -- 3=EA/expert, 4=SL,
5=TP, ...)"`). El único registro que sobrevive para distinguir un `SAME_BAR_EXIT_FALLBACK` de un
`CLOSE` es la línea de log del ejecutor (columna `event` en
`data/analysis/p_cap/eventos_ejecutor_902.csv`), no el historial de MT5.

### 1.5 · ¿Puede la réplica producirlo hoy?

Fichero auditado: `scripts/analysis/realtick_bt/faulty/ciclos.py` (291 líneas, sólo lectura).

`correr_ciclos` (`ciclos.py:74-290`) sólo rastrea **una** posición a la vez (`posicion_viva: dict |
None`, `ciclos.py:98`), y sólo toma **una** ficha del estado por barra:

```python
# ciclos.py:122-123
                if len(estado) > 0:
                    ficha_id, ficha = next(iter(estado.items()))
```

El módulo NO recibe ni construye ningún equivalente a `last_bar_exits` — la firma de
`correr_ciclos` (`ciclos.py:74-85`) sólo toma `estados: list[dict | None]` (un estado deseado por
barra), sin un segundo canal de "salidas ocurridas dentro de la barra con su propio motivo/precio".

Hay DOS rutas de cierre en el bucle:

- **Paso 5 — `CLOSE_RECONCILER`** (`ciclos.py:233-246`): se dispara cuando, en un ciclo con
  `posicion_viva` no nula, `ficha_id not in estado` (`ciclos.py:181` evalúa lo contrario; el `else`
  de la línea 233 es el caso `ficha_id not in estado`). Como `estado = estados[idx]`
  (`ciclos.py:109`) y `idx` sólo cambia cuando el reloj `t` cruza a una barra distinta
  (`ciclos.py:105`, vía `bar_closes`), `estado` permanece CONSTANTE durante todos los ciclos de una
  misma barra. La ficha que se abrió en el paso 3 de una barra, por construcción, SÍ está en el
  `estado` de esa misma barra — así que el paso 5 no puede evaluarse como verdadero para esa ficha
  hasta que `idx` avance a una barra siguiente cuyo `estado` ya no la contenga. Es decir: el cierre
  `CLOSE_RECONCILER` no puede ocurrir en la misma barra en que se abrió la posición.
- **Paso 6 — barrido de SL** (`ciclos.py:248-269`): se ejecuta SIEMPRE al final de cada ciclo, tanto
  si la posición se acaba de abrir en el paso 3 de ESE MISMO ciclo como si viene de ciclos
  anteriores. Recorre los ticks entre `t` y `t + cycle_sec` y cierra con `motivo_cierre = "SL"` si el
  precio cruza `posicion_viva["sl_vivo"]` (`ciclos.py:252-262`). Esto SÍ puede ocurrir en el mismo
  ciclo/barra en que se abrió la posición (nada en el código lo impide: el paso 6 corre
  incondicionalmente tras el paso 3 dentro de la misma iteración del bucle `while`).

Con su algoritmo actual, la réplica **sí tiene un camino que cierra una posición en el mismo
ciclo/barra en que se abrió** (paso 6, cruce literal de `sl_vivo` contra el tick), pero ese camino:
(a) siempre etiqueta el cierre `"SL"`, nunca un motivo distinto; (b) se dispara por cruce de precio
contra un nivel de SL ya calculado (`sl_vivo`), no por una decisión de salida del sim basada en el
OHLC de la barra con su propio `motivo` (p. ej. `EXIT_INITSL`) y su propio precio de salida
(`sim_fill`), como en el motor congelado. No hay en `ciclos.py` ningún parámetro `last_bar_exits`,
ningún `motivo_cierre` distinto de `{"SL", "CLOSE_RECONCILER", "FALLBACK_CLOSE_INVALID_SL",
"FIN_VENTANA"}`, ni ningún campo `sim_fill`/gap contable.

### 1.6 · Los 10 casos reales

Cruce de `data/analysis/p_cap/eventos_ejecutor_902.csv` (`event == "SAME_BAR_EXIT_FALLBACK"`) contra
`data/analysis/p_cap/verdad_terreno_902.csv` por proximidad de epoch (`t_close_epoch` más cercano al
`epoch` del evento). El CSV de eventos tiene **11** filas con `event == "SAME_BAR_EXIT_FALLBACK"`;
una de ellas (`epoch=1786492804`, `2026-08-12 00:00:04`) trae `en_ventana_canonica = False` y su
epoch más cercano en `verdad_terreno_902.csv` está a 61.135 s de distancia (ninguna posición real
coincide) — es la fila que el criterio de ventana canónica excluye, dejando **10** casos dentro de
los 21 `EXPERT` medidos. Todas las coincidencias de las 10 restantes son exactas o a 0-1 s de
diferencia de epoch.

| epoch evento | timestamp servidor (evento) | gap_usd | sim_fill | live_fill | motivo (sim) | position_id | config | side | t_open_servidor | t_close_servidor | duration_seconds | profit (CLP) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1785204008 | 2026-07-28 02:00:08,275 | -28.4419 | 4045.795493571076 | 4046.22 | EXIT_INITSL | 55205837 | SAR::S6-K2P0 | SELL | 2026-07-27 18:53:30 | 2026-07-28 02:00:08 | 25598 | 1.767.284,39 |
| 1785357011 | 2026-07-29 20:30:11,033 | -5.6054 | 4075.4736628300916 | 4075.39 | EXIT_INITSL | 55230412 | SAR::S6-K2P0 | BUY | 2026-07-29 20:29:56 | 2026-07-29 20:30:12 | 16 | -33.792,12 |
| 1785460502 | 2026-07-31 01:15:02,578 | 197.8710 | 4083.0532990489846 | 4080.1 | EXIT_INITSL | 55244539 | SAR::S6-K2P0 | SELL | 2026-07-31 01:06:38 | 2026-07-31 01:15:02 | 504 | 132.078,11 |
| 1785789002 | 2026-08-03 20:30:02,893 | -7.7395 | 4058.995514294596 | 4058.88 | EXIT_INITSL | 55267286 | SAR::S6-K2P0 | BUY | 2026-08-03 18:45:14 | 2026-08-03 20:30:03 | 6289 | 347.623,37 |
| 1785802515 | 2026-08-04 00:15:15,366 | 408.8170 | 4051.0782544107406 | 4057.18 | EXIT_INITSL | 55268678 | SAR::S6-K2P0 | BUY | 2026-08-03 22:45:04 | 2026-08-04 00:15:15 | 5411 | -339.935,09 |
| 1785811507 | 2026-08-04 02:45:07,556 | 278.8463 | 4056.2681146421123 | 4060.43 | EXIT_INITSL | 55269559 | SAR::S6-K2P0 | BUY | 2026-08-04 02:39:37 | 2026-08-04 02:45:07 | 330 | 220.595,22 |
| 1785960910 | 2026-08-05 20:15:10,805 | 447.1560 | 4265.246030206027 | 4271.92 | EXIT_INITSL | 55292962 | SAR::S6-K2P0 | BUY | 2026-08-05 20:14:08 | 2026-08-05 20:15:11 | 63 | 298.677,96 |
| 1786050903 | 2026-08-06 21:15:03,773 | 37.1330 | 4244.694223370418 | 4244.14 | EXIT_INITSL | 55305439 | SAR::S6-K2P0 | SELL | 2026-08-06 21:14:47 | 2026-08-06 21:15:03 | 16 | 23.318,81 |
| 1786396508 | 2026-08-10 21:15:08,215 | 568.9124 | 4405.248769976096 | 4413.74 | EXIT_INITSL | 55332605 | SAR::S6-K2P0 | BUY | 2026-08-10 21:07:04 | 2026-08-10 21:15:08 | 484 | 631.248,54 |
| 1786401907 | 2026-08-10 22:45:07,666 | 97.3508 | 4416.8970028484555 | 4418.35 | EXIT_INITSL | 55333670 | SAR::S6-K2P0 | BUY | 2026-08-10 22:40:24 | 2026-08-10 22:45:07 | 283 | -34.424,60 |

Líneas `raw` completas (columna `raw` de `eventos_ejecutor_902.csv`, en el mismo orden que la
tabla):

1. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4045.795493571076 live_fill=4046.22 gap$=-28.4419 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
2. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4075.4736628300916 live_fill=4075.39 gap$=-5.6054 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
3. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4083.0532990489846 live_fill=4080.1 gap$=197.8710 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
4. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4058.995514294596 live_fill=4058.88 gap$=-7.7395 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
5. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4051.0782544107406 live_fill=4057.18 gap$=408.8170 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
6. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4056.2681146421123 live_fill=4060.43 gap$=278.8463 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
7. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4265.246030206027 live_fill=4271.92 gap$=447.1560 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
8. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4244.694223370418 live_fill=4244.14 gap$=37.1330 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
9. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4405.248769976096 live_fill=4413.74 gap$=568.9124 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`
10. `[SAME_BAR_EXIT_FALLBACK] S6-K2P0 F1 sim_fill=4416.8970028484555 live_fill=4418.35 gap$=97.3508 motivo=EXIT_INITSL -> retcode=10009 (by design, not a divergence)`

Las 10 posiciones son todas de la estrategia `SAR::S6-K2P0`, ficha `F1`, `magic=724011` (banda
724010+1); todas con `reason_name = EXPERT`, `cerrada_fuera_de_ventana = False`, `retcode = 10009`
(`TRADE_RETCODE_DONE`) y `motivo` (sim) = `EXIT_INITSL` en las 10.

**Duración (`duration_seconds`) de las 10 posiciones**, ordenadas: 16, 16, 63, 283, 330, 484, 504,
5411, 6289, 25598. Mínimo 16 s, máximo 25598 s (≈7 h 6 min), media 3899,4 s.

**Comparación con el resto de cierres `EXPERT` (los otros 11: 3 `SENT CLOSE` + 8
`FALLBACK_CLOSE_INVALID_SL`)**, duraciones: 16, 16, 16, 16, 31, 31, 31, 32, 2703, 4494, 6586.
Mínimo 16 s, máximo 6586 s, media 1270,2 s.

**Los 21 `EXPERT` en conjunto**: mínimo 16 s, máximo 25598 s, media 2522,2 s.

**Los 152 cierres reales completos** (`verdad_terreno_902.csv`, todos los `reason_name`): mínimo
1 s, máximo 53703 s, media 4903,0 s. Desglosado por `reason_name`:

| reason_name | n | min (s) | max (s) | media (s) |
|---|---|---|---|---|
| EXPERT | 21 | 16 | 25598 | 2522,2 |
| CLIENT_manual | 11 | 2122 | 53703 | 27946,5 |
| SL | 119 | 1 | 28426 | 3042,0 |
| TP | 1 | 22883 | 22883 | 22883,0 |

Las duraciones de los 10 casos `SAME_BAR_EXIT_FALLBACK` van de 16 segundos a 25.598 segundos
(≈7 horas). Tomando 900 s (una barra M15) como referencia: 7 de las 10 duraciones son menores a
900 s (16, 16, 63, 283, 330, 484, 504) y 3 de las 10 lo superan ampliamente (5411 s ≈ 1h30min,
6289 s ≈ 1h45min, 25598 s ≈ 7h6min).

---

## Hueco 2 — el único cierre `TP`

Posición: `position_id 55268071 · SuperTrend::SuperTrend-p14x3-M15 · BUY · 0.67 · abre 2026-08-03
21:11:55 @ 4047.26 · cierra 2026-08-04 03:33:18 @ 4065.91 · profit 1.155.646,32 CLP · duration
22.883 s · reason_name TP`.

Confirmado en `verdad_terreno_902.csv`: `reason_code = 5`, `reason_name = TP`, `origin_out =
strategy`, `magic = 724071`, `spread_open = 0.5`.

### 2.1 · ¿El ejecutor congelado envía alguna vez un take-profit?

Barrido exhaustivo sobre `b113eb7`, más allá del grep estrecho previo del controlador (que cubrió
sólo dos ficheros):

```
$ git grep -n -i -E "take_profit|TRADE_ACTION_SLTP" b113eb7 -- '*.py'
```

Resultado completo (todo el repo, no sólo `sentinel_engine/live/**` y `scripts/live/**`):

- `scripts/live/run_live_20.py:752` — único uso de `TRADE_ACTION_SLTP` en código de producción
  (ver más abajo).
- `sentinel_engine/opt/labels.py:40,132,140` — `TAKE_PROFIT` como enum de
  `BarrierOutcome` en el módulo de ETIQUETADO offline (triple-barrier para entrenamiento/opt), sin
  relación con el envío de órdenes en vivo.
- `tests/live/test_executor_dryrun.py`, `tests/scripts/test_run_live_20.py`,
  `tests/opt/test_labels.py` — sólo tests, ninguno de producción.

Los 4 (únicos) `order_send(...)` de todo el repo están en `scripts/live/run_live_20.py`:

```
$ git grep -n "order_send(" b113eb7 -- '*.py'
scripts/live/run_live_20.py:677   (CLOSE / SAME_BAR_EXIT_FALLBACK, request TRADE_ACTION_DEAL)
scripts/live/run_live_20.py:737   (FALLBACK_CLOSE_INVALID_SL, request TRADE_ACTION_DEAL)
scripts/live/run_live_20.py:755   (MODIFY, request TRADE_ACTION_SLTP)
scripts/live/run_live_20.py:793   (OPEN, request TRADE_ACTION_DEAL)
```

Los 4 requests, verbatim:

```python
# run_live_20.py:662-667 (CLOSE / SAME_BAR_EXIT_FALLBACK)
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
               "volume": ..., "type": ..., "position": int(a.ticket),
               "price": price, "deviation": deviation, "magic": int(a.magic),
               "comment": f"{a.config_id}:{a.ficha}:close",
               "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)}

# run_live_20.py:730-736 (FALLBACK_CLOSE_INVALID_SL)
                close_req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
                             "volume": ..., "type": ..., "position": int(a.ticket),
                             "price": value, "deviation": deviation, "magic": int(a.magic),
                             "comment": f"{a.config_id}:{a.ficha}:fallback_close",
                             "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)}

# run_live_20.py:752-754 (MODIFY -- único uso de TRADE_ACTION_SLTP)
            req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": symbol,
                   "position": int(a.ticket), "sl": float(value),
                   "magic": int(a.magic)}

# run_live_20.py:787-792 (OPEN)
            req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
                   "volume": float(a.volume), "type": ..., "price": price,
                   "sl": float(sl_to_send), "deviation": deviation, "magic": int(a.magic),
                   "comment": f"{a.config_id}:{a.ficha}", "type_filling": ...}
```

**Ninguno de los 4 diccionarios `req` incluye una clave `"tp"`.** El único uso de
`TRADE_ACTION_SLTP` (`run_live_20.py:752-754`) modifica exclusivamente `"sl"`. `Action` en
`reconciler.py` no tiene ningún campo `tp` (sólo `sl`, `sim_fill`, `motivo`; ver §1.2 y
`reconciler.py:54-69`), y el conjunto de `kind` de `Action` (`reconciler.py:56-58`) no incluye
ningún kind relacionado con TP: `OPEN | CLOSE | MODIFY | NOOP | REJECT_VOLUME | REJECT_CAP |
SUPPRESSED_OPEN | SAME_BAR_EXIT_FALLBACK | MISSING_SL_ALARM`.

Confirmado (no desmentido): **el ejecutor congelado, en `b113eb7`, no envía nunca un take-profit.**

### 2.2 · ¿De dónde puede salir un `reason = TP` en el historial?

No hay ficheros de órdenes crudas en el repo. `data/analysis/2883016902/` sólo contiene
`2883016902_deals_raw.csv` y `2883016902_positions.csv` — no existe ningún `*orders*` (verificado
con `find data/analysis -iname "*order*"`, sin resultados).

`2883016902_positions.csv` no tiene columnas `sl`/`tp` (columnas disponibles: `position_id, symbol,
side, strategy, magic_base, tanda, open_srv, close_srv, status, n_deals, volume_in, net`) — no
permite corroborar si la posición tenía un TP server-side adjunto en ningún momento de su vida.

`2883016902_deals_raw.csv` sí tiene las dos filas de esta posición:

```
IN  ticket=55968314 position_id=55268071 order=55268071  time_srv=2026-08-03 21:11:55 price=4047.26 magic=724071 comment=''              reason=3
OUT ticket=55969820 position_id=55268071 order=55269609  time_srv=2026-08-04 03:33:18 price=4065.91 magic=724071 comment='[tp 4065.91]'   reason=5
```

- La fila `IN` tiene `reason=3` (`DEAL_REASON_EXPERT` según el mapeo documentado en
  `scripts/live/run_deals_watcher.py:137-138`: `"reason (DEAL_REASON_* int -- 3=EA/expert, 4=SL,
  5=TP, ...)"`), consistente con una apertura enviada por `order_send` (magic 724071 = banda
  SuperTrend-p14x3-M15 F1, ver §2.4).
- La fila `OUT` tiene `reason=5` (TP) y `comment='[tp 4065.91]'`. `run_deals_watcher.py:135-138`
  documenta que `comment`/`reason` en el `TradeDeal` de MT5 se leen tal cual del objeto que devuelve
  la librería (`getattr(d, "comment", None)`, `getattr(d, "reason", None)`,
  `run_deals_watcher.py:136,139`), no los escribe este repo: `d.comment='[tp 2410.00]'` está citado
  en ese mismo comentario como un formato NATIVO de MT5 para cierres disparados por un take-profit
  server-side. El texto `[tp 4065.91]` en la fila real coincide exactamente con `precio_close =
  4065.91`.
- Ese formato de comentario (`[tp X]`) es DISTINTO del que produce el propio ejecutor para sus
  cierres enviados (`f"{a.config_id}:{a.ficha}:close"` / `:fallback_close`, ver §1.4 y §2.1) — los
  cierres que sí manda `run_live_20.py` (CLOSE, SAME_BAR_EXIT_FALLBACK, FALLBACK_CLOSE_INVALID_SL)
  se ven en `deals_raw.csv` con `comment` en formato `"{config}:{ficha}:close"` y `reason=3`
  (verificado empíricamente contra los 10 casos de §1.6). La fila `OUT` de 55268071 no encaja en ese
  patrón.

**Lo que el dato permite comprobar:** que MT5 clasificó el cierre de esta posición como disparado
por una orden de take-profit server-side (`reason=5`, `comment='[tp 4065.91]'`), con ese campo
`comment`/`reason` originado en el propio objeto `TradeDeal` de MT5 (no generado por el código de
este repo).

**Lo no evaluable con estos artefactos:** cómo o cuándo se adjuntó ese nivel de TP a la posición
55268071 del lado del bróker/terminal. No hay en el repo ningún fichero de órdenes crudas
(`orders_raw`, historial de `order_send`/`positions_get` con campo `tp`) que documente el momento en
que ese nivel se fijó, y el código de `b113eb7` (§2.1) no contiene ninguna ruta que hubiera podido
enviarlo. Se declara no evaluable con los artefactos disponibles.

### 2.3 · Si sí lo envía

No aplica — §2.1 concluye que no lo envía en ningún punto del código de `b113eb7`.

### 2.4 · Config congelada del roster tomachine — claves de TP

`git show b113eb7:sentinel_engine/strategies/live_configs_20.py` (693 líneas).

**`SuperTrend-p14x3-M15`** (la estrategia de la posición 55268071), definición completa de kwargs:

```python
# live_configs_20.py:341-351
_GOLIVE_SUPERTREND: dict[str, Any] = {
    "id": "SuperTrend-p14x3-M15", "tf": "M15", "k": None,
    "kwargs": {"symbol": "XAUUSD"},
    "engine": "supertrend_always_in",
    "direction_filter": False,
    "notes": ("Wave-5 P34 always-in SuperTrend(14,3.0) M15; single flipping "
              "position, SL=SuperTrend line; reconciled additively (GL-T3)"),
}
```

`kwargs` de esta estrategia es literalmente `{"symbol": "XAUUSD"}` — **sin ninguna clave de
take-profit ni de ningún otro parámetro**. Su generador de estado deseado,
`supertrend_always_in_target` (`live_configs_20.py:306-338`), construye el `open_state` con sólo
`side, entry, sl, max_fav` (`live_configs_20.py:336-337`) y fija `"last_bar_exits": {}` siempre
(`live_configs_20.py:324, 332, 338` — las tres rutas de retorno usan un diccionario vacío), por lo
que esta estrategia tampoco puede producir un `SAME_BAR_EXIT_FALLBACK` (§1 no aplica a
SuperTrend-p14x3-M15: su `last_bar_exits` nunca tiene contenido).

**`S7-TPNONE`** (contexto, no es la estrategia de la posición TP): `live_configs_20.py:204-205`
documenta que el lever `tp_min` fue "DECISIVELY REFUTED (most harmful lever tested) and is
deliberately ABSENT" del roster tomachine/go-live; `S7-TPNONE` es una de las 5 config M15 SAR
(`live_configs_20.py:258-260`) que NO trae ese lever. El lever emparentado que sí aparece en otra
config de la misma familia es `f1_tp_r` (una clave de `simular_variant`, no de MT5):

```python
# live_configs_20.py:263-265
    _golive_m15("S7-TP1P0", ac_modulate=False, trail_atr_floor_k=1.5,
                extra=dict(f1_tp_r=1.0, be_at_r=1.0),
                notes="HON-W2-S7-TP1P0-M15-SAR (league rank 4)"),
```

`f1_tp_r`/`tp_min` son parámetros que alimentan el SIMULADOR (`simular_variant`), un umbral de
salida en múltiplos de R evaluado dentro del propio motor de simulación — no son una clave del
`request` de `order_send` ni del `Action` del reconciliador. Ninguna de las configs relacionadas con
la posición 55268071 (`SuperTrend-p14x3-M15`) usa `f1_tp_r` ni `tp_min`; su único kwarg es
`{"symbol": "XAUUSD"}`.

`git show b113eb7:sentinel_engine/strategies/live_configs_20.py` no arroja ninguna otra ocurrencia
de una clave de take-profit ligada a `SuperTrend-p14x3-M15` o a su magic band (724070/724071).

---

## Lo no evaluable con los artefactos disponibles

- **Hueco 1 — origen del nivel de SL "vivo" pre-barra que no atrapa el cierre intrabar del sim.** El
  código muestra QUE el SL server-side queda un paso atrás del sim (comentario
  `reconciler.py:196-197`: "Live's server-side SL sat at the prior bar's level so the broker did NOT
  stop it out mid-bar"), pero los artefactos de datos disponibles no permiten reconstruir, para cada
  uno de los 10 casos, el valor exacto de ese SL server-side en el momento en que el precio lo cruzó
  intrabar (no hay tick-by-tick de MT5 en los CSV consultados, sólo el epoch/precio del evento de
  cierre). Se declara no evaluable con estos artefactos.
- **Hueco 2 — quién/cómo adjuntó el nivel de take-profit 4065.91 a la posición 55268071.** Confirmado
  que el código de `b113eb7` no lo envía (§2.1) y que MT5 clasificó el cierre como TP-triggered
  (§2.2), pero no hay en el repo ningún fichero de órdenes crudas (`orders_raw` / historial de
  `order_send` con campo `tp`) ni ningún log de terminal/bróker que documente el origen de ese nivel.
  Búsqueda realizada: `find data/analysis -iname "*order*"` sin resultados; `2883016902_positions.csv`
  no tiene columnas `sl`/`tp`. Se declara no evaluable con los artefactos disponibles.
- **Hueco 2 — si existió alguna orden de tipo TP visible en algún otro registro de la cuenta 902.**
  Sólo se dispone de `deals_raw` (histórico de deals ejecutados) y `positions` (agregado derivado);
  no hay histórico de órdenes pendientes/activas (`history_orders_get` / `orders_get`) para la
  cuenta 2883016902 en `data/analysis/`. Se declara no evaluable con los artefactos disponibles.
