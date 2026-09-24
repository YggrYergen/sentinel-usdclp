"""tests/research/test_ac_modulate_hold.py -- WP-2b Bloque 2, palanca P-03
(`ac_modulate_hold_bars`: duracion del apriete de AC del trailing V-06).

Spec: research/fases/F0-preparacion/02-specs/WP-2b-brief-ac-hold-y-cita-por-contenido.md

`ac_modulate_hold_bars` es un kwarg aditivo de
`sentinel_engine.strategies.emasar_variant.simular_variant`, default 1 =
comportamiento de hoy exacto (el apriete de AC dura exactamente la barra en
la que la condicion se cumple). Con `hold_bars=N>1`, el apriete persiste N
barras desde el disparo y se re-arma a N si vuelve a dispararse dentro de la
ventana. `ac_modulate=False` (S7 vivo) sigue saltandose el bloque entero,
sea cual sea `hold_bars`.

R1-bis: S6/S7/SuperTrend vivos son byte-identicos; este fichero solo LEE sus
kwargs vivos (`live_configs_20._GOLIVE_M15`), siempre via `copy.deepcopy` --
jamas muta el dict vivo.
"""
from __future__ import annotations

import copy
import random

import pytest

from scripts.analysis.realtick_bt.backtest import load_bars
from sentinel_engine.strategies.emasar_variant import simular_variant
from sentinel_engine.strategies.live_configs_20 import _GOLIVE_M15

_S6_K2P0_KWARGS = next(c["kwargs"] for c in _GOLIVE_M15 if c["id"] == "S6-K2P0")
_S7_TPNONE_KWARGS = next(c["kwargs"] for c in _GOLIVE_M15 if c["id"] == "S7-TPNONE")


def test_default_hold_1_es_byte_identico_al_motor_de_hoy():
    """S6-K2P0 (ac_modulate=True en vivo) sobre las 400 primeras barras
    reales del sustrato: no pasar el kwarg nuevo y pasar
    ac_modulate_hold_bars=1 explicito deben producir la MISMA lista de
    eventos, exacta."""
    bars = load_bars()[:400]
    kwargs_sin = copy.deepcopy(_S6_K2P0_KWARGS)
    kwargs_con = copy.deepcopy(_S6_K2P0_KWARGS)
    kwargs_con["ac_modulate_hold_bars"] = 1

    eventos_sin = simular_variant(bars, **kwargs_sin)
    eventos_con = simular_variant(bars, **kwargs_con)

    assert eventos_sin == eventos_con


# --------------------------------------------------------------------------
# Fixture sintetica determinista (semilla fija, sin I/O) para los dos tests
# de mecanica del contador. La secuencia de precios es un paseo aleatorio
# generado con random.Random(seed) -- reproducible bit a bit en cada corrida
# (mismo patron que tests/strategies/test_emasar_variant.py::_synthetic_bars).
# Los parametros de gate se relajan (confirm_mode=1, require_ema_order=False)
# para que una entrada LONG se dispare pronto y la ficha F1 quede abierta
# el tiempo suficiente para observar el efecto del contador de hold.
# --------------------------------------------------------------------------
_PARAMS_SINTETICOS = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=800.0, f2_trail_pips=800.0, f3_trail_pips=800.0,
    init_sl_range_k=3.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3, symbol="XAUUSD",
    ac_modulate=True, ac_modulate_factor=0.3, active_fichas=1,
)


def _bars_sinteticos(n: int, seed: int) -> list[dict]:
    rnd = random.Random(seed)
    bars = []
    price = 4500.0
    for _ in range(n):
        drift = rnd.uniform(-0.6, 0.9)
        price += drift
        open_ = price - drift
        close = price
        high = max(open_, close) + abs(rnd.uniform(0.1, 0.4))
        low = min(open_, close) - abs(rnd.uniform(0.1, 0.4))
        bars.append({"open": open_, "high": high, "low": low, "close": close})
    return bars


def test_hold_mayor_que_1_persiste_el_apriete():
    """Caso sintetico minimo (semilla 1): la condicion de desaceleracion de
    AC se cumple en la barra de indice 60 y NO en la 61 (verificado offline
    con sentinel_engine.strategies.emasar_ref.ac_desacelerando sobre esta
    misma fixture). Con hold_bars=1 el apriete de la barra 60 no sobrevive a
    la 61 (trail SIN apretar en 61); con hold_bars=3 SI sobrevive (trail
    apretado en 61). Efecto observable: el SL de F1 reportado por
    return_state=True es estrictamente mas alto (mas apretado) bajo
    hold_bars=3 que bajo hold_bars=1, en el MISMO bar (61) de la MISMA
    fixture -- las barras 0..59 son identicas entre ambas corridas (mismo
    entry, mismo SL hasta la barra 59: verificado offline), asi que la
    diferencia solo puede venir del manejo del contador en la barra 61."""
    bars = _bars_sinteticos(n=62, seed=1)  # a traves del indice 61 (i0+1)

    kwargs_hold1 = dict(_PARAMS_SINTETICOS, ac_modulate_hold_bars=1)
    kwargs_hold3 = dict(_PARAMS_SINTETICOS, ac_modulate_hold_bars=3)

    _, estado_hold1 = simular_variant(bars, return_state=True, **kwargs_hold1)
    _, estado_hold3 = simular_variant(bars, return_state=True, **kwargs_hold3)

    f1_hold1 = estado_hold1["open"].get("F1")
    f1_hold3 = estado_hold3["open"].get("F1")
    assert f1_hold1 is not None, "F1 debe seguir abierta en la fixture (hold_bars=1)"
    assert f1_hold3 is not None, "F1 debe seguir abierta en la fixture (hold_bars=3)"
    assert f1_hold3["sl"] > f1_hold1["sl"], (
        f"con hold_bars=3 el SL de F1 en la barra 61 debe ser mas alto "
        f"(trail mas apretado) que con hold_bars=1; "
        f"hold1={f1_hold1['sl']!r} hold3={f1_hold3['sl']!r}"
    )


def test_rearme_dentro_de_la_ventana():
    """Caso sintetico minimo (semilla 11): la condicion de desaceleracion se
    cumple en las barras 146 y 148 (con la 147 sin cumplirla en medio --
    "2 disparos separados por 1 barra"), verificado offline con
    ac_desacelerando sobre esta misma fixture. Con hold_bars=2, el segundo
    disparo (barra 148) debe RE-ARMAR el contador a 2 en vez de dejarlo
    decaer -- efecto observable: en la barra 149 (bar del segundo disparo +1)
    el trail SIGUE apretado bajo hold_bars=2 (el contador re-armado en 148
    todavia esta vivo), mientras que bajo hold_bars=1 el disparo de la barra
    148 solo aprieta esa misma barra y ya expiro para la 149. El SL de F1 en
    la barra 149 es por tanto estrictamente mas alto bajo hold_bars=2 que
    bajo hold_bars=1, en la MISMA fixture (las barras 0..148 son identicas
    entre ambas corridas: verificado offline)."""
    bars = _bars_sinteticos(n=150, seed=11)  # a traves del indice 149

    kwargs_hold1 = dict(_PARAMS_SINTETICOS, ac_modulate_hold_bars=1)
    kwargs_hold2 = dict(_PARAMS_SINTETICOS, ac_modulate_hold_bars=2)

    _, estado_hold1 = simular_variant(bars, return_state=True, **kwargs_hold1)
    _, estado_hold2 = simular_variant(bars, return_state=True, **kwargs_hold2)

    f1_hold1 = estado_hold1["open"].get("F1")
    f1_hold2 = estado_hold2["open"].get("F1")
    assert f1_hold1 is not None, "F1 debe seguir abierta en la fixture (hold_bars=1)"
    assert f1_hold2 is not None, "F1 debe seguir abierta en la fixture (hold_bars=2)"
    assert f1_hold2["sl"] > f1_hold1["sl"], (
        f"con hold_bars=2 el segundo disparo debe re-armar el contador y "
        f"mantener el trail apretado en la barra 149, dando un SL mas alto "
        f"que con hold_bars=1; hold1={f1_hold1['sl']!r} hold2={f1_hold2['sl']!r}"
    )


@pytest.mark.parametrize("valor_invalido", [0, -1])
def test_hold_bars_invalido_falla_ruidoso(valor_invalido):
    with pytest.raises(ValueError) as excinfo:
        simular_variant([], ac_modulate_hold_bars=valor_invalido)
    assert str(valor_invalido) in str(excinfo.value)


def test_ac_modulate_false_ignora_el_parametro():
    """S7-TPNONE (ac_modulate=False en vivo): hold_bars=1 y hold_bars=10
    deben producir eventos identicos, porque el bloque entero se salta
    cuando ac_modulate=False (sea cual sea ac_modulate_hold_bars)."""
    bars = load_bars()[:400]
    kwargs_hold1 = copy.deepcopy(_S7_TPNONE_KWARGS)
    kwargs_hold1["ac_modulate_hold_bars"] = 1
    kwargs_hold10 = copy.deepcopy(_S7_TPNONE_KWARGS)
    kwargs_hold10["ac_modulate_hold_bars"] = 10

    eventos_hold1 = simular_variant(bars, **kwargs_hold1)
    eventos_hold10 = simular_variant(bars, **kwargs_hold10)

    assert eventos_hold1 == eventos_hold10
