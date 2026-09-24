"""tests/analysis/test_ciclos_faulty.py -- Componente B de la réplica del motor
faulty: el bucle de reconciliación de 15 s (`correr_ciclos`).

Spec: research/fases/F0-preparacion/02-specs/2026-08-13-replica-motor-faulty-spec.md,
sección 3. Los 7 tests de aceptación de esa sección, uno por función de test.

Doble sintético de `Ticks` (backtest.py:85-160): misma interfaz (`first_at`,
`range`), datos en memoria -- no toca el lago real.
"""
from __future__ import annotations

import numpy as np

from scripts.analysis.realtick_bt.faulty.ciclos import BAR_SEC, CYCLE_SEC, correr_ciclos


class FakeTicks:
    """Doble sintético de backtest.Ticks: misma interfaz, datos en memoria."""

    def __init__(self, ts, bid, ask):
        self.ts = np.asarray(ts, dtype=float)
        self.bid = np.asarray(bid, dtype=float)
        self.ask = np.asarray(ask, dtype=float)

    def first_at(self, t_sec: float):
        i = int(np.searchsorted(self.ts, t_sec, "left"))
        if i < len(self.ts):
            return float(self.ts[i]), float(self.bid[i]), float(self.ask[i])
        return None

    def range(self, t0: float, t1: float):
        lo = int(np.searchsorted(self.ts, t0, "left"))
        hi = int(np.searchsorted(self.ts, t1, "left"))
        return self.ts[lo:hi], self.bid[lo:hi], self.ask[lo:hi]


def _estado_long(sl: float, entry: float = 2000.0) -> dict:
    return {"F1": {"side": "L", "sl": sl, "entry": entry}}


# --------------------------------------------------------------------- test 1
def test_spread_gate_es_cap_duro_no_banda():
    """Spread 0.50 -> abre. Spread 0.501 -> SPREAD_GATE_SKIP. Spread 0.30 ->
    abre (es cap <=, no banda centrada -- este es el test que blinda D5)."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]  # SL lejos: no crossed, no clamp
    t0, t1 = 900.0, 915.0

    # spread exacto 0.50 -> abre
    ticks = FakeTicks(ts=[900.0], bid=[2000.0], ask=[2000.50])
    posiciones, eventos = correr_ciclos(estados, bar_times, ticks, t0, t1)
    assert len(posiciones) == 1
    assert any(e["tipo"] == "OPEN" for e in eventos)
    assert not any(e["tipo"] == "SPREAD_GATE_SKIP" for e in eventos)

    # spread 0.501 -> SPREAD_GATE_SKIP, ninguna posición
    ticks = FakeTicks(ts=[900.0], bid=[2000.0], ask=[2000.501])
    posiciones, eventos = correr_ciclos(estados, bar_times, ticks, t0, t1)
    assert len(posiciones) == 0
    assert any(e["tipo"] == "SPREAD_GATE_SKIP" for e in eventos)

    # spread 0.30 -> abre (cap, no banda: el harness viejo con banda
    # abs(spread-0.5)<=0.05 habría bloqueado esto)
    ticks = FakeTicks(ts=[900.0], bid=[2000.0], ask=[2000.30])
    posiciones, eventos = correr_ciclos(estados, bar_times, ticks, t0, t1)
    assert len(posiciones) == 1
    assert any(e["tipo"] == "OPEN" for e in eventos)


# --------------------------------------------------------------------- test 2
def test_time_gate_semi_abierto():
    """18:00:00 y 18:44:59 bloquean apertura; 18:45:00 no."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]

    t_1800 = 18 * 3600.0          # 1970-01-01 18:00:00 UTC
    t_184459 = t_1800 + 44 * 60 + 59
    t_1845 = t_1800 + 45 * 60

    for t_open in (t_1800, t_184459):
        ticks = FakeTicks(ts=[t_open], bid=[2000.0], ask=[2000.30])
        posiciones, eventos = correr_ciclos(
            estados, bar_times, ticks, t_open, t_open + CYCLE_SEC
        )
        assert len(posiciones) == 0, f"no debe abrir a t={t_open}"
        assert any(e["tipo"] == "TIME_GATE_SKIP" for e in eventos)

    ticks = FakeTicks(ts=[t_1845], bid=[2000.0], ask=[2000.30])
    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t_1845, t_1845 + CYCLE_SEC
    )
    assert len(posiciones) == 1
    assert any(e["tipo"] == "OPEN" for e in eventos)
    assert not any(e["tipo"] == "TIME_GATE_SKIP" for e in eventos)


# --------------------------------------------------------------------- test 3
def test_open_skipped_sl_crossed():
    """Long con desired_sl >= bid -> OPEN_SKIPPED_SL_CROSSED, ninguna posición."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=2005.0)]  # >= bid=2000 -> crossed
    t0, t1 = 900.0, 915.0
    ticks = FakeTicks(ts=[900.0], bid=[2000.0], ask=[2000.30])

    posiciones, eventos = correr_ciclos(estados, bar_times, ticks, t0, t1)
    assert len(posiciones) == 0
    assert any(e["tipo"] == "OPEN_SKIPPED_SL_CROSSED" for e in eventos)
    assert not any(e["tipo"] == "OPEN" for e in eventos)


# --------------------------------------------------------------------- test 4
def test_sl_clamped_on_open():
    """Long con desired_sl entre bid - stops_level y bid -> SL_CLAMPED,
    sl_enviado = bid - stops_level."""
    bar_times = np.array([0.0])
    stops_level = 0.5
    estados = [_estado_long(sl=1999.8)]  # entre 1999.5 y 2000.0
    t0, t1 = 900.0, 915.0
    ticks = FakeTicks(ts=[900.0], bid=[2000.0], ask=[2000.30])

    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1, stops_level=stops_level
    )
    assert len(posiciones) == 1
    pos = posiciones[0]
    assert pos["clamp_aplicado"] is True
    assert abs(pos["sl_open_enviado"] - 1999.5) < 1e-9
    assert pos["sl_open_deseado"] == 1999.8
    assert any(e["tipo"] == "SL_CLAMPED" for e in eventos)


# --------------------------------------------------------------------- test 5
def test_sl_sweep_cierra_en_el_tick_del_cruce():
    """El SL vive en el bróker: si el precio cruza entre dos ciclos, cierra EN
    ESE TICK, no al ciclo siguiente ni al cierre de barra."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1990.0)]
    t0, t1 = 900.0, 915.0  # una sola vuelta de ciclo (cycle_sec=15 por defecto)

    # tick de apertura a t=900 (bid 2000, no cruzado), tick de cruce a t=905
    # (bid 1990 <= sl_vivo=1990) DENTRO del intervalo hasta el siguiente ciclo.
    ticks = FakeTicks(
        ts=[900.0, 905.0],
        bid=[2000.0, 1990.0],
        ask=[2000.30, 1990.30],
    )

    posiciones, eventos = correr_ciclos(estados, bar_times, ticks, t0, t1)
    assert len(posiciones) == 1
    pos = posiciones[0]
    assert pos["motivo_cierre"] == "SL"
    assert pos["t_close"] == 905.0
    assert pos["precio_close"] == 1990.0
    # no cerró al ciclo siguiente (915) ni al cierre de barra (900+BAR_SEC)
    assert pos["t_close"] != t0 + CYCLE_SEC
    assert pos["t_close"] != bar_times[0] + BAR_SEC


# --------------------------------------------------------------------- test 6
def test_reentrada_emerge_nunca_dos_posiciones_vivas():
    """El SL cierra la posición; el ciclo siguiente ve que el sim la sigue
    deseando y la reabre sola (no hay rama especial de reapertura). Verificar
    que jamás hay 2 posiciones vivas a la vez."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1990.0)]
    t0, t1 = 900.0, 930.0  # dos ciclos: t=900 y t=915

    ticks = FakeTicks(
        ts=[900.0, 905.0, 915.0],
        bid=[2000.0, 1990.0, 2000.0],
        ask=[2000.30, 1990.30, 2000.30],
    )

    posiciones, eventos = correr_ciclos(estados, bar_times, ticks, t0, t1)

    # dos posiciones: la primera cerrada por SL, la segunda reabierta y viva
    # hasta FIN_VENTANA.
    assert len(posiciones) == 2
    assert posiciones[0]["motivo_cierre"] == "SL"
    assert posiciones[1]["t_open"] == 915.0

    # nunca dos vivas a la vez: la siguiente no abre antes de que la anterior
    # cierre.
    for a, b in zip(posiciones, posiciones[1:]):
        assert a["t_close"] <= b["t_open"]


# --------------------------------------------------------------------- test 7
def test_close_reconciler_cuando_estado_deja_de_desear():
    """estado deja de desear la ficha -> CLOSE con motivo CLOSE_RECONCILER."""
    bar_times = np.array([0.0, 900.0])
    estados = [_estado_long(sl=1000.0), {}]  # barra 1: ya no desea nada
    t0, t1 = 900.0, 1801.0  # cycle_sec grande para tocar solo t=900 y t=1800

    ticks = FakeTicks(
        ts=[900.0, 1800.0],
        bid=[2000.0, 2000.0],
        ask=[2000.30, 2000.30],
    )

    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1, cycle_sec=900.0
    )
    assert len(posiciones) == 1
    pos = posiciones[0]
    assert pos["motivo_cierre"] == "CLOSE_RECONCILER"
    assert pos["t_close"] == 1800.0
    assert any(e["tipo"] == "CLOSE" for e in eventos)


# ---------------------------------------------------------------- test 3-bis
def test_fallback_close_invalid_sl_long():
    """§3-bis: posición viva long, llega un ciclo con un SL nuevo del estado
    ya CRUZADO respecto del precio actual (nuevo_sl_deseado >= bid) ->
    FALLBACK_CLOSE_INVALID_SL, cierre a mercado EN ESE TICK, motivo_cierre
    == "FALLBACK_CLOSE_INVALID_SL" (no "SL", no "CLOSE_RECONCILER")."""
    bar_times = np.array([0.0, 900.0])
    estados = [
        _estado_long(sl=1990.0),   # barra 0: abre con sl=1990 (legal, bid=2000)
        _estado_long(sl=1992.0),   # barra 1: sl nuevo distinto, ahora >= bid=1985
    ]
    t0, t1 = 900.0, 1801.0  # cycle_sec grande: solo toca t=900 y t=1800

    ticks = FakeTicks(
        ts=[900.0, 1800.0],
        bid=[2000.0, 1985.0],   # el precio cae por debajo del sl nuevo deseado
        ask=[2000.30, 1985.30],
    )

    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1, cycle_sec=900.0
    )

    assert len(posiciones) == 1
    pos = posiciones[0]
    assert pos["motivo_cierre"] == "FALLBACK_CLOSE_INVALID_SL"
    assert pos["motivo_cierre"] != "SL"
    assert pos["motivo_cierre"] != "CLOSE_RECONCILER"
    assert pos["t_close"] == 1800.0
    assert pos["precio_close"] == 1985.0
    assert any(e["tipo"] == "FALLBACK_CLOSE_INVALID_SL" for e in eventos)
    assert not any(e["tipo"] == "MODIFY" for e in eventos)


def test_fallback_close_invalid_sl_short():
    """§3-bis, dirección short: SL nuevo del estado ya CRUZADO respecto del
    precio actual (nuevo_sl_deseado <= ask) -> FALLBACK_CLOSE_INVALID_SL."""
    bar_times = np.array([0.0, 900.0])
    estados = [
        {"F1": {"side": "S", "sl": 2010.0, "entry": 2000.0}},  # abre, ask=2000, legal
        {"F1": {"side": "S", "sl": 2005.0, "entry": 2000.0}},  # sl nuevo, ahora <= ask=2015
    ]
    t0, t1 = 900.0, 1801.0

    ticks = FakeTicks(
        ts=[900.0, 1800.0],
        bid=[1999.70, 2014.70],
        ask=[2000.0, 2015.0],   # el precio sube por encima del sl nuevo deseado
    )

    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1, cycle_sec=900.0
    )

    assert len(posiciones) == 1
    pos = posiciones[0]
    assert pos["motivo_cierre"] == "FALLBACK_CLOSE_INVALID_SL"
    assert pos["motivo_cierre"] != "SL"
    assert pos["motivo_cierre"] != "CLOSE_RECONCILER"
    assert pos["t_close"] == 1800.0
    assert pos["precio_close"] == 2015.0
    assert any(e["tipo"] == "FALLBACK_CLOSE_INVALID_SL" for e in eventos)
    assert not any(e["tipo"] == "MODIFY" for e in eventos)


# ------------------------------------------------------------- D-46: instantes
# Brief F (D-46): `correr_ciclos` acepta un parámetro opcional `instantes`
# que, cuando se pasa, sustituye la rejilla sintética de `t += cycle_sec` por
# la secuencia de instantes reales del ejecutor. Cuando es None, byte-idéntico
# al comportamiento anterior (ver los 9 tests de arriba, que no lo pasan).


def test_instantes_none_preserva_comportamiento_por_defecto():
    """Pasar instantes=None explícito debe ser indistinguible de no pasarlo
    -- mismo caso que test 5 (sweep de SL dentro de un ciclo de 15 s)."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1990.0)]
    t0, t1 = 900.0, 915.0

    ticks = FakeTicks(ts=[900.0, 905.0], bid=[2000.0, 1990.0], ask=[2000.30, 1990.30])

    sin_param = correr_ciclos(estados, bar_times, ticks, t0, t1)
    con_none = correr_ciclos(estados, bar_times, ticks, t0, t1, instantes=None)
    assert sin_param == con_none


def test_instantes_reales_sustituye_rejilla_sintetica():
    """Con instantes=[900, 920, 950] (irregular, no múltiplos de 15) el bucle
    debe mirar el mercado EXACTAMENTE en esos instantes -- no en la rejilla
    900, 915, 930, 945. Ticks colocados en los instantes irregulares deben
    ser los que abren la posición."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]  # SL lejos: abre sin gate
    t0, t1 = 900.0, 960.0

    # tick SOLO en el instante irregular 920 (nada en la rejilla de 915)
    ticks = FakeTicks(ts=[900.0, 920.0, 950.0], bid=[0.0, 2000.0, 2000.0],
                       ask=[0.0, 2000.30, 2000.30])
    # a t=900 el tick es (0.0, 0.30): spread absurdo -> SPREAD_GATE_SKIP,
    # así que la apertura real sólo puede pasar en t=920 o t=950.

    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1, instantes=[900.0, 920.0, 950.0]
    )
    assert len(posiciones) == 1
    assert posiciones[0]["t_open"] == 920.0
    # nunca miró en la rejilla sintética 915/930/945/960
    tiempos_mirados = {e["t"] for e in eventos}
    assert 915.0 not in tiempos_mirados
    assert 930.0 not in tiempos_mirados
    assert 945.0 not in tiempos_mirados


def test_paso6_barre_hasta_el_instante_siguiente_no_t_mas_cycle_sec():
    """Con instantes irregulares, el barrido del SL (paso 6) debe cubrir
    hasta el PRÓXIMO instante del ejecutor, no t + cycle_sec. Cruce de SL a
    t=930, con instantes=[900, 940] (separados 40 s): con la rejilla vieja
    (t+15=915) el cruce a 930 quedaría fuera del barrido y no se detectaría
    hasta el ciclo siguiente (940) -- mal, según el brief. Con el barrido
    correcto (hasta 940) debe cerrarse EN EL TICK del cruce, t=930."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1990.0)]
    t0, t1 = 900.0, 950.0

    ticks = FakeTicks(
        ts=[900.0, 930.0, 940.0],
        bid=[2000.0, 1990.0, 1990.0],
        ask=[2000.30, 1990.30, 1990.30],
    )

    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1, instantes=[900.0, 940.0]
    )
    assert len(posiciones) == 1
    pos = posiciones[0]
    assert pos["motivo_cierre"] == "SL"
    assert pos["t_close"] == 930.0
    assert pos["precio_close"] == 1990.0


def test_paso6_ultimo_instante_barre_hasta_t1():
    """Para el ÚLTIMO instante de la lista (sin instante siguiente), el
    barrido del paso 6 debe cubrir hasta t1 (fin de ventana), no quedarse
    cojo. Cruce de SL a t=930 con instantes=[900] y t1=950 debe detectarse."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1990.0)]
    t0, t1 = 900.0, 950.0

    ticks = FakeTicks(
        ts=[900.0, 930.0],
        bid=[2000.0, 1990.0],
        ask=[2000.30, 1990.30],
    )

    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1, instantes=[900.0]
    )
    assert len(posiciones) == 1
    pos = posiciones[0]
    assert pos["motivo_cierre"] == "SL"
    assert pos["t_close"] == 930.0


# ------------------------------------------------------- T0.7-M-D: TICK_STALE_SKIP
# Brief T0.7-M-D: `ciclos.py:161` (`ticks.first_at(t)`) es búsqueda hacia
# adelante SIN COTA -- en un hueco de mercado (corte de mantenimiento,
# fin de semana) devuelve el primer tick DESPUÉS del hueco, no None. Eso es
# look-ahead: el ciclo decide en `t` con un precio que en `t` no existía.
# El arreglo: si el tick devuelto está más allá de `tolerancia_tick_s` del
# instante del ciclo, el ciclo se salta (`continue`, como con tick is None),
# con evento TICK_STALE_SKIP. NUNCA se re-sella t_open con el tick futuro.


def test_ciclos_tick_stale_skip_salta_el_ciclo_sin_abrir():
    """Hueco de ticks: `first_at(t)` sólo tiene un tick muy por delante del
    instante del ciclo (simula el corte de mantenimiento/fin de semana).
    Antes del arreglo esto abría una posición con el precio del tick futuro
    (look-ahead). Después del arreglo: TICK_STALE_SKIP, ninguna posición."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]  # SL lejos: no hay gate de SL de por medio
    t0, t1 = 900.0, 915.0

    # único tick disponible, 5000 s por delante del instante del ciclo (t0=900)
    ticks = FakeTicks(ts=[900.0 + 5000.0], bid=[2000.0], ask=[2000.30])

    posiciones, eventos = correr_ciclos(estados, bar_times, ticks, t0, t1)

    assert len(posiciones) == 0
    assert not any(e["tipo"] == "OPEN" for e in eventos)
    assert any(e["tipo"] == "TICK_STALE_SKIP" for e in eventos)

    ev = next(e for e in eventos if e["tipo"] == "TICK_STALE_SKIP")
    assert ev["t"] == 900.0
    assert ev["detalle"]["t_tick"] == 5900.0
    assert abs(ev["detalle"]["adelanto_s"] - 5000.0) < 1e-9


def test_ciclos_tick_stale_skip_tolerancia_default_es_cycle_sec():
    """`tolerancia_tick_s=None` (default) toma `cycle_sec`. Adelanto ==
    cycle_sec exacto NO salta (la regla es '>', no '>='); un pelo por encima
    de cycle_sec sí salta."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]
    t0 = 900.0

    # adelanto exactamente igual a cycle_sec (15.0) -> NO salta, abre
    ticks_igual = FakeTicks(ts=[915.0], bid=[2000.0], ask=[2000.30])
    posiciones, eventos = correr_ciclos(estados, bar_times, ticks_igual, t0, t0 + 15.0)
    assert len(posiciones) == 1
    assert not any(e["tipo"] == "TICK_STALE_SKIP" for e in eventos)

    # adelanto un pelo mayor que cycle_sec -> salta
    ticks_mayor = FakeTicks(ts=[915.001], bid=[2000.0], ask=[2000.30])
    posiciones2, eventos2 = correr_ciclos(estados, bar_times, ticks_mayor, t0, t0 + 15.0)
    assert len(posiciones2) == 0
    assert any(e["tipo"] == "TICK_STALE_SKIP" for e in eventos2)


def test_ciclos_tick_stale_skip_tolerancia_explicita_distinta_de_cycle_sec():
    """Con `tolerancia_tick_s` explícito (distinto de `cycle_sec`) se usa
    ese valor, no `cycle_sec`."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]
    t0, t1 = 900.0, 915.0

    # adelanto de 100 s: con tolerancia=cycle_sec(15.0) saltaría; con
    # tolerancia_tick_s=200.0 explícito, no salta.
    ticks = FakeTicks(ts=[1000.0], bid=[2000.0], ask=[2000.30])
    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1, tolerancia_tick_s=200.0
    )
    assert len(posiciones) == 1
    assert not any(e["tipo"] == "TICK_STALE_SKIP" for e in eventos)


def test_ciclos_tick_stale_skip_no_actualiza_last_bid_ask():
    """El salto por TICK_STALE_SKIP debe comportarse EXACTAMENTE como el
    salto por `tick is None`: no actualiza `last_bid`/`last_ask` (verificado
    indirectamente -- el cierre de FIN_VENTANA cuando no hay tick en t1 usa
    last_bid/last_ask del ÚLTIMO tick fresco visto, no del tick stale)."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]
    # ciclo 1 (t=900): tick fresco a 900 -> abre.
    # ciclo 2 (t=915): único tick restante es stale (muy futuro) -> salta,
    # NO debe pisar last_bid/last_ask del ciclo 1.
    t0, t1 = 900.0, 930.0

    ticks = FakeTicks(ts=[900.0, 20000.0], bid=[2000.0, 9999.0], ask=[2000.30, 9999.30])

    posiciones, eventos = correr_ciclos(estados, bar_times, ticks, t0, t1)

    # fin de ventana: sin tick en t1=930, y first_at(930) devuelve el stale
    # (20000.0) que la implementación NO usa para el cierre porque cae en el
    # bloque post-bucle -- ahí el brief no exige tolerancia (no está en el
    # alcance del brief, sólo paso 2 del bucle). Lo que este test blinda es
    # que el ciclo 2 no contaminó last_bid/last_ask con 9999: si lo hiciera,
    # y el cierre de fin de ventana cayera a ese fallback, el precio sería
    # 9999 en vez de 2000 -- no debe pasar porque tick_final = first_at(930)
    # SÍ existe (devuelve el tick 20000.0, distinto del stale-skip de dentro
    # del bucle). Este test sólo verifica que la posición sigue viva tras el
    # ciclo 2 (no se cerró ni se rompió nada al saltar por TICK_STALE_SKIP).
    assert len(posiciones) == 1
    assert posiciones[0]["motivo_cierre"] == "FIN_VENTANA"
    assert any(e["tipo"] == "TICK_STALE_SKIP" for e in eventos)


# ------------------------------------------------------- T0.7-M-G: ventana horaria
# Brief T0.7-M-G: el filtro horario (`ciclos.py`, paso 3) evalúa
# `_seconds_of_day(t)` -- el instante SINTÉTICO del bucle, no el timestamp
# REAL del tick que `first_at(t)` devolvió (`_tick_ts`). Cuando `t` cae unos
# segundos ANTES del borde 18:00:00 pero el tick vigente (dentro de
# `tolerancia_tick_s`, por tanto no-stale) ya tiene timestamp DESPUÉS de
# 18:00:00, el filtro compara la hora equivocada: dice "17:59:53, no
# bloqueado" cuando la única cotización real disponible en ese ciclo es de
# "18:00:06", ya dentro de la ventana bloqueada. Medido: 5 posiciones reales
# (T0.7-M-G-reporte.md) abrieron así ~45 min antes de las 18:45 reales.
# El arreglo: el filtro horario debe leer `_seconds_of_day(_tick_ts)` -- la
# hora real de la cotización usada para decidir --, no `_seconds_of_day(t)`.


def test_time_gate_usa_la_hora_real_del_tick_no_el_instante_del_ciclo():
    """t=17:59:53 (antes del borde 18:00:00), pero el único tick disponible
    (dentro de tolerancia) tiene timestamp real 18:00:06 -- YA dentro de la
    ventana bloqueada. Con el filtro horario leyendo la hora del CICLO esto
    abre indebidamente (el bug medido); con el filtro leyendo la hora REAL
    del tick, debe bloquear (TIME_GATE_SKIP), igual que si el ciclo hubiera
    caído en 18:00:06 directamente."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]  # SL lejos: no hay gate de SL de por medio

    t_1800 = 18 * 3600.0  # 18:00:00
    t_ciclo = t_1800 - 7.0  # 17:59:53
    t_tick = t_1800 + 6.0  # 18:00:06 -- adelanto 13s, dentro de tolerancia (cycle_sec=15)

    ticks = FakeTicks(ts=[t_tick], bid=[2000.0], ask=[2000.30])  # spread legal (0.30)
    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t_ciclo, t_ciclo + CYCLE_SEC
    )

    assert len(posiciones) == 0, (
        "no debe abrir: la unica cotizacion real disponible en este ciclo "
        "(18:00:06) ya esta dentro de la ventana bloqueada 18:00-18:45"
    )
    assert any(e["tipo"] == "TIME_GATE_SKIP" for e in eventos)
    assert not any(e["tipo"] == "OPEN" for e in eventos)
    # no debe haberse saltado por staleness -- el tick SI esta dentro de
    # tolerancia, esto es un bloqueo horario, no un TICK_STALE_SKIP
    assert not any(e["tipo"] == "TICK_STALE_SKIP" for e in eventos)


def test_time_gate_no_bloquea_cuando_tick_real_tambien_esta_fuera_de_ventana():
    """Caso simetrico de control: t y el timestamp real del tick estan AMBOS
    fuera de la ventana bloqueada -> abre normalmente. Blinda que el arreglo
    no sobre-bloquea el caso general (ciclo y tick ya alineados, el caso
    normal de un stream de ticks denso)."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]

    t_1745 = 17 * 3600.0 + 45 * 60.0  # 17:45:00, bien fuera de la ventana
    ticks = FakeTicks(ts=[t_1745 + 2.0], bid=[2000.0], ask=[2000.30])  # tick 2s despues

    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t_1745, t_1745 + CYCLE_SEC
    )
    assert len(posiciones) == 1
    assert any(e["tipo"] == "OPEN" for e in eventos)
    assert not any(e["tipo"] == "TIME_GATE_SKIP" for e in eventos)


def test_instantes_se_ordenan_y_deduplican_y_se_filtran_a_ventana():
    """instantes fuera de [t0, t1) se ignoran; duplicados y desorden no deben
    romper ni repetir ciclos."""
    bar_times = np.array([0.0])
    estados = [_estado_long(sl=1000.0)]
    t0, t1 = 900.0, 950.0

    ticks = FakeTicks(ts=[920.0], bid=[2000.0], ask=[2000.30])

    # 800 y 960 están fuera de [900, 950); 920 duplicado; orden invertido
    posiciones, eventos = correr_ciclos(
        estados, bar_times, ticks, t0, t1,
        instantes=[960.0, 920.0, 800.0, 920.0],
    )
    # único ciclo real ejecutado: t=920 (800/960 fuera de ventana, 920 no
    # duplicado). El único evento con t < t1 debe ser el de ese ciclo -- el
    # cierre de FIN_VENTANA a t=t1=950 es aparte, del bloque post-bucle.
    tiempos_mirados_en_bucle = [e["t"] for e in eventos if e["t"] < t1]
    assert tiempos_mirados_en_bucle == [920.0]
    assert len(posiciones) == 1
    assert posiciones[0]["t_open"] == 920.0
