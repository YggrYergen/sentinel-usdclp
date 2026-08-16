r"""Componente B de la réplica en harness del motor faulty (tag
engine-faulty-tomachine-902 -> b113eb7): el bucle de reconciliación de 15 s
del ejecutor vivo.

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md,
sección 3.

No importa `estado_por_barra` (Componente A): recibe la línea temporal de
estado ya calculada como parámetro `estados`, indexada por barra. Eso
desacopla ambos componentes y permite testear con estados sintéticos.

CLOCK CONVENTION (igual que backtest.py -- no "simplificar" esto)
-------------------------------------------------------------------
Los epochs de MT5 codifican el reloj de SERVIDOR (UTC-4) verbatim. La única
conversión correcta epoch -> hora-del-día es `datetime.utcfromtimestamp()`.
`datetime.fromtimestamp()` re-aplica el huso local del host y es INCORRECTO
aquí.

D-39 -- el corazón de la réplica
---------------------------------
El ejecutor vivo abre a precio de mercado pero le pega el SL ACTUAL del sim,
ya arrastrado por el trailing -- no el SL inicial de la barra de señal. Por
eso `estado[ficha]["entry"]` no se usa nunca en este módulo: el precio de
apertura es siempre el precio de mercado del tick vigente, y el SL enviado
sale de `estado[ficha]["sl"]` (posiblemente clampado), nunca de "entry".

Re-entrada (D4): no se codifica, emerge. Si el SL cierra la posición y el
ciclo siguiente ve que el sim la sigue deseando, el paso de apertura (3) la
reabre sola -- no hay ninguna rama especial de "reabrir" en este código.

D-46 -- instantes reales en vez de la rejilla sintética
---------------------------------------------------------
`correr_ciclos` sintetizaba su propia rejilla de ciclos (t0, t0+15, t0+30,
...), pero el ejecutor vivo tuvo cadencia irregular (mediana 15,77 s, no
15,0 s exactos) porque cada ciclo hacía trabajo real. D-46
(`research/DECISIONES.md`) decidió alimentar el bucle con los instantes REALES
que el ejecutor dejó registrados, en vez de la rejilla sintética.

El parámetro opcional `instantes` es ADITIVO: cuando es `None` (default), el
comportamiento es BYTE-IDÉNTICO al de antes de D-46 (rejilla `t += cycle_sec`).
Cuando se pasa una secuencia de epochs, sustituye la rejilla: el bucle mira el
mercado exactamente en esos instantes, ordenados, deduplicados y filtrados a
`[t0, t1)`.

El paso 6 (barrido del SL entre ciclos) también cambia con `instantes`: en vez
de barrer siempre `ticks.range(t, t + cycle_sec)`, barre hasta el PRÓXIMO
instante de la secuencia (`t1` para el último). Con instantes irregulares el
intervalo entre ciclos ya no es constante -- barrer un intervalo fijo de 15 s
dejaría huecos (cruces de SL entre ciclos separados > 15 s no detectados hasta
el ciclo siguiente) o solapes (mismo tick barrido dos veces). Ver brief
`.superpowers/sdd/2026-08-13-replica-motor-faulty-spec/f-fase-ciclos-brief.md`
§2.2.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

import numpy as np

CYCLE_SEC = 15.0
BAR_SEC = 900


def _seconds_of_day(t_sec: float) -> int:
    """Hora-del-día de SERVIDOR a partir de un epoch MT5. Nunca
    `datetime.fromtimestamp()` -- ver CLOCK CONVENTION arriba."""
    d = datetime.utcfromtimestamp(t_sec)
    return d.hour * 3600 + d.minute * 60 + d.second


def _clamp_or_cross(
    side: str, desired_sl: float, tick_bid: float, tick_ask: float, stops_level: float
) -> tuple[str, float | None]:
    """Aplica la lógica de clamp/crossed del spec §3 paso 3.iii, compartida
    entre apertura (paso 3) y modificación (paso 4).

    Devuelve (status, sl_enviado) con status en {"crossed", "clamped", "legal"}.
    Para "crossed", sl_enviado es None (no se abre / no se modifica: se cierra).
    """
    if side == "L":
        ref = tick_bid
        if desired_sl >= ref:
            return "crossed", None
        if desired_sl > ref - stops_level:
            return "clamped", ref - stops_level
        return "legal", desired_sl
    else:  # side == "S"
        ref = tick_ask
        if desired_sl <= ref:
            return "crossed", None
        if desired_sl < ref + stops_level:
            return "clamped", ref + stops_level
        return "legal", desired_sl


def _pasos(t0: float, t1: float, cycle_sec: float, instantes: Sequence[float] | None):
    """Genera pares (t, t_siguiente) para el bucle de `correr_ciclos`.

    D-46: si `instantes` es None, reproduce EXACTAMENTE la rejilla sintética
    de siempre (t0, t0+cycle_sec, ...), con t_siguiente = t + cycle_sec --
    byte-idéntico al comportamiento anterior a D-46.

    Si `instantes` trae una secuencia, se ordena, deduplica y filtra a
    `[t0, t1)`, y se itera sobre ella; t_siguiente es el próximo instante de
    la secuencia, o t1 para el último (no hay "ciclo siguiente" que barrer
    hasta él salvo el fin de la ventana)."""
    if instantes is None:
        t = t0
        while t < t1:
            yield t, t + cycle_sec
            t += cycle_sec
    else:
        tiempos = sorted({float(x) for x in instantes if t0 <= float(x) < t1})
        for i, t in enumerate(tiempos):
            t_siguiente = tiempos[i + 1] if i + 1 < len(tiempos) else t1
            yield t, t_siguiente


def correr_ciclos(
    estados: list[dict | None],
    bar_times: np.ndarray,
    ticks: Any,
    t0: float,
    t1: float,
    *,
    max_spread_open: float = 0.50,
    blocked_open_window: tuple = ((18, 0), (18, 45)),
    stops_level: float = 0.0,
    cycle_sec: float = CYCLE_SEC,
    instantes: Sequence[float] | None = None,
    tolerancia_tick_s: float | None = None,
) -> tuple[list[dict], list[dict]]:
    """Reproduce el bucle del ejecutor vivo. Devuelve (posiciones, eventos).

    Ver spec §3 para el algoritmo por ciclo, en orden exacto.

    `instantes` (D-46, aditivo): secuencia opcional de epochs reales que
    sustituye la rejilla sintética de `cycle_sec`. `None` (default) preserva
    el comportamiento anterior byte-idéntico -- ver `_pasos()`.

    `tolerancia_tick_s` (T0.7-M-D): tolerancia máxima, en segundos, entre el
    instante del ciclo `t` y el timestamp del tick que `ticks.first_at(t)`
    devuelve. `first_at` es búsqueda hacia adelante SIN COTA (backtest.py) --
    en un hueco de mercado (corte de mantenimiento del bróker, fin de
    semana) no devuelve `None`: devuelve el primer tick DESPUÉS del hueco,
    potencialmente miles de segundos por delante de `t`. Usar ese tick para
    decidir en `t` es look-ahead (F0-A6-BORDE-0001). Si
    `t_tick - t > tolerancia_tick_s`, el ciclo se salta (`continue`), igual
    que cuando `first_at` devuelve `None`, y se emite `TICK_STALE_SKIP`.
    `None` (default) toma el valor de `cycle_sec` -- el propio paso del
    bucle. NO se re-sella `t_open` con `t_tick`: eso conservaría el
    look-ahead. NO se usa `last_at(t)` (cotización rancia): alternativa
    considerada y descartada por el controlador -- es un cambio de semántica
    mayor sin medir.
    """
    if tolerancia_tick_s is None:
        tolerancia_tick_s = cycle_sec

    bar_times_arr = np.asarray(bar_times, dtype=float)
    bar_closes = bar_times_arr + BAR_SEC

    blocked_start = blocked_open_window[0][0] * 3600 + blocked_open_window[0][1] * 60
    blocked_end = blocked_open_window[1][0] * 3600 + blocked_open_window[1][1] * 60

    posiciones: list[dict] = []
    eventos: list[dict] = []
    posicion_viva: dict | None = None
    last_bid: float | None = None
    last_ask: float | None = None

    for t, t_siguiente in _pasos(t0, t1, cycle_sec, instantes):
        # --- paso 1: barra vigente -------------------------------------
        idx = int(np.searchsorted(bar_closes, t, side="right")) - 1
        if idx < 0:
            continue
        estado = estados[idx] if idx < len(estados) else None

        # --- paso 2: tick vigente ---------------------------------------
        tick = ticks.first_at(t)
        if tick is None:
            continue
        _tick_ts, tick_bid, tick_ask = tick
        # T0.7-M-D: `first_at` es sin cota -- en un hueco de mercado
        # devuelve el primer tick DESPUÉS del hueco, no None. Usarlo aquí
        # sería decidir en `t` con un precio que en `t` no existía
        # (look-ahead, F0-A6-BORDE-0001). Se salta ANTES de usar el tick
        # para cualquier cosa (precio, spread, hora, t_open).
        adelanto_s = _tick_ts - t
        if adelanto_s > tolerancia_tick_s:
            eventos.append(
                {"t": t, "tipo": "TICK_STALE_SKIP",
                 "detalle": {"t_tick": _tick_ts, "adelanto_s": adelanto_s}}
            )
            continue
        last_bid, last_ask = tick_bid, tick_ask

        if estado is not None:
            if posicion_viva is None:
                # --- paso 3: estado desea ficha abierta, sin posición viva
                if len(estado) > 0:
                    ficha_id, ficha = next(iter(estado.items()))
                    side = ficha["side"]
                    desired_sl = ficha["sl"]

                    # T0.7-M-G: la hora que decide si estamos dentro de la
                    # ventana bloqueada debe ser la del TICK REAL usado para
                    # esta decision (`_tick_ts`), no la del instante
                    # sintetico del bucle (`t`). `first_at(t)` puede devolver
                    # un tick hasta `tolerancia_tick_s` por delante de `t`
                    # (no es stale, ya paso el chequeo de arriba) -- si ese
                    # adelanto cruza el borde 18:00:00, `t` cae ANTES del
                    # borde pero la unica cotizacion real de este ciclo ya
                    # esta DESPUES. Usar `t` ahi deja pasar una apertura que
                    # el ejecutor real, mirando esa misma cotizacion, habria
                    # bloqueado. Medido: 5 posiciones abrieron ~45 min antes
                    # de las 18:45 reales por este mecanismo (T0.7-M-G-reporte.md).
                    hms = _seconds_of_day(_tick_ts)
                    if blocked_start <= hms < blocked_end:
                        eventos.append(
                            {"t": t, "tipo": "TIME_GATE_SKIP",
                             "detalle": {"ficha": ficha_id, "hms": hms}}
                        )
                    else:
                        spread = tick_ask - tick_bid
                        if spread > max_spread_open + 1e-6:
                            eventos.append(
                                {"t": t, "tipo": "SPREAD_GATE_SKIP",
                                 "detalle": {"ficha": ficha_id, "spread": spread}}
                            )
                        else:
                            status, sl_enviado = _clamp_or_cross(
                                side, desired_sl, tick_bid, tick_ask, stops_level
                            )
                            if status == "crossed":
                                eventos.append(
                                    {"t": t, "tipo": "OPEN_SKIPPED_SL_CROSSED",
                                     "detalle": {"ficha": ficha_id,
                                                 "desired_sl": desired_sl}}
                                )
                            else:
                                clamp_aplicado = status == "clamped"
                                if clamp_aplicado:
                                    eventos.append(
                                        {"t": t, "tipo": "SL_CLAMPED",
                                         "detalle": {"ficha": ficha_id,
                                                     "desired_sl": desired_sl,
                                                     "sl_enviado": sl_enviado}}
                                    )
                                precio_open = tick_ask if side == "L" else tick_bid
                                posicion_viva = {
                                    "ficha": ficha_id,
                                    "side": side,
                                    "t_open": t,
                                    "precio_open": precio_open,
                                    "sl_open_deseado": desired_sl,
                                    "sl_open_enviado": sl_enviado,
                                    "clamp_aplicado": clamp_aplicado,
                                    "sl_vivo": sl_enviado,
                                    "t_close": None,
                                    "precio_close": None,
                                    "motivo_cierre": None,
                                }
                                eventos.append(
                                    {"t": t, "tipo": "OPEN",
                                     "detalle": {"ficha": ficha_id, "side": side,
                                                 "precio_open": precio_open,
                                                 "sl_enviado": sl_enviado}}
                                )
            else:
                ficha_id = posicion_viva["ficha"]
                if ficha_id in estado:
                    # --- paso 4: posición viva, estado la sigue deseando
                    nuevo_sl_deseado = estado[ficha_id]["sl"]
                    if abs(nuevo_sl_deseado - posicion_viva["sl_vivo"]) > 1e-9:
                        status, sl_enviado = _clamp_or_cross(
                            posicion_viva["side"], nuevo_sl_deseado,
                            tick_bid, tick_ask, stops_level,
                        )
                        if status == "crossed":
                            # FALLBACK_CLOSE_INVALID_SL: el SL nuevo ya está
                            # cruzado al intentar un MODIFY, así que el
                            # ejecutor cierra a mercado en vez de mandar un
                            # MODIFY inválido. Spec §3-bis: NO se colapsa en
                            # "SL" -- un SL lo ejecuta el bróker contra un
                            # stop server-side; esto es una orden de cierre a
                            # mercado que manda el ejecutor. Son eventos
                            # distintos, con distinto `reason` en MT5, y la
                            # razón de cierre está dentro del criterio de
                            # paso de P-CAP (D-45).
                            precio_close = (
                                tick_bid if posicion_viva["side"] == "L" else tick_ask
                            )
                            posicion_viva["t_close"] = t
                            posicion_viva["precio_close"] = precio_close
                            posicion_viva["motivo_cierre"] = "FALLBACK_CLOSE_INVALID_SL"
                            posiciones.append(posicion_viva)
                            eventos.append(
                                {"t": t, "tipo": "FALLBACK_CLOSE_INVALID_SL",
                                 "detalle": {"ficha": ficha_id,
                                             "nuevo_sl_deseado": nuevo_sl_deseado}}
                            )
                            posicion_viva = None
                        else:
                            clamp_aplicado = status == "clamped"
                            posicion_viva["sl_vivo"] = sl_enviado
                            if clamp_aplicado:
                                eventos.append(
                                    {"t": t, "tipo": "SL_CLAMPED",
                                     "detalle": {"ficha": ficha_id,
                                                 "desired_sl": nuevo_sl_deseado,
                                                 "sl_enviado": sl_enviado}}
                                )
                            eventos.append(
                                {"t": t, "tipo": "MODIFY",
                                 "detalle": {"ficha": ficha_id,
                                             "sl_enviado": sl_enviado}}
                            )
                    else:
                        eventos.append(
                            {"t": t, "tipo": "NOOP",
                             "detalle": {"ficha": ficha_id}}
                        )
                else:
                    # --- paso 5: posición viva, estado ya NO la desea
                    precio_close = (
                        tick_bid if posicion_viva["side"] == "L" else tick_ask
                    )
                    posicion_viva["t_close"] = t
                    posicion_viva["precio_close"] = precio_close
                    posicion_viva["motivo_cierre"] = "CLOSE_RECONCILER"
                    posiciones.append(posicion_viva)
                    eventos.append(
                        {"t": t, "tipo": "CLOSE",
                         "detalle": {"ficha": ficha_id, "motivo": "CLOSE_RECONCILER"}}
                    )
                    posicion_viva = None

        # --- paso 6: barrido del SL entre este ciclo y el siguiente ---------
        # D-46: hasta t_siguiente (próximo instante real, o t1 para el
        # último), NO t + cycle_sec -- con instantes irregulares el intervalo
        # entre ciclos no es constante (ver `_pasos()`).
        if posicion_viva is not None:
            ts_r, bid_r, ask_r = ticks.range(t, t_siguiente)
            for j in range(len(ts_r)):
                if posicion_viva["side"] == "L":
                    crossed = bid_r[j] <= posicion_viva["sl_vivo"]
                    precio = float(bid_r[j])
                else:
                    crossed = ask_r[j] >= posicion_viva["sl_vivo"]
                    precio = float(ask_r[j])
                if crossed:
                    t_cross = float(ts_r[j])
                    posicion_viva["t_close"] = t_cross
                    posicion_viva["precio_close"] = precio
                    posicion_viva["motivo_cierre"] = "SL"
                    posiciones.append(posicion_viva)
                    eventos.append(
                        {"t": t_cross, "tipo": "CLOSE",
                         "detalle": {"ficha": posicion_viva["ficha"], "motivo": "SL"}}
                    )
                    posicion_viva = None
                    break

    # --- fin de ventana: cerrar toda posición aún abierta -------------------
    if posicion_viva is not None:
        tick_final = ticks.first_at(t1)
        if tick_final is not None:
            _, fb, fa = tick_final
        else:
            fb, fa = last_bid, last_ask
        precio_close = fb if posicion_viva["side"] == "L" else fa
        posicion_viva["t_close"] = t1
        posicion_viva["precio_close"] = precio_close
        posicion_viva["motivo_cierre"] = "FIN_VENTANA"
        posiciones.append(posicion_viva)
        eventos.append(
            {"t": t1, "tipo": "CLOSE",
             "detalle": {"ficha": posicion_viva["ficha"], "motivo": "FIN_VENTANA"}}
        )

    return posiciones, eventos
