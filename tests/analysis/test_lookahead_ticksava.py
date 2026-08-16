"""T0.7-M-F -- Acota `TicksAva.first_at` (scripts/analysis/a6_pata_a/signal_level.py)
al mismo `tolerance_s=60.0` que T0.7-M-E aplico a `bt.Ticks.first_at`.

`TicksAva` es una clase INDEPENDIENTE (no subclase de `bt.Ticks`) que
`signal_level.py` usa para leer el feed AVA; llevaba una copia verbatim del
mismo defecto sin cota corregido en `backtest.py` por T0.7-M-E (commit
f3dda1a). Estos tests mirroran, para `TicksAva`, las mismas propiedades que
`tests/analysis/test_lookahead_harness.py` verifica para `bt.Ticks`: un hueco
mayor que la tolerancia devuelve `None`; un tick dentro de la tolerancia se
devuelve tal cual; el comportamiento viejo (sin cota) sigue siendo alcanzable
pasando un `tolerance_s` explicito grande; y el salto de fichero de mes no
sortea la cota.

Brief: research/fases/F0-preparacion/02-specs/T0.7-M-F-brief-fix-lookahead-ticksava.md
No se toca `backtest.py` ni `scripts/analysis/realtick_bt/faulty/` (fuera de
alcance de esta tarea). Solo se importa `TicksAva` read-only y se construyen
datos sinteticos via el cache interno `TicksAva._m`, sin tocar disco.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from scripts.analysis.a6_pata_a.signal_level import TicksAva


def _synthetic_ticks_ava(
    month_data: dict[str, tuple[list[float], list[float], list[float]]],
    tolerance_s: float | None = None,
) -> TicksAva:
    """Construye un `TicksAva` con `_m` precargado a mano (sin tocar disco),
    para que `_load` (que solo consulta el cache si `ym in self._m`) nunca
    llegue a abrir un parquet del lake AVA. `tolerance_s=None` deja el
    default de `TicksAva.__init__` (T0.7-M-F: 60.0s, mismo valor que
    `bt.Ticks`)."""
    t = TicksAva() if tolerance_s is None else TicksAva(tolerance_s=tolerance_s)
    for ym, (ta, bid, ask) in month_data.items():
        t._m[ym] = (np.array(ta, dtype="float64"), np.array(bid, dtype="float64"),
                    np.array(ask, dtype="float64"))
    return t


def test_first_at_hueco_artificial_devuelve_none_bajo_tolerancia_default():
    """Hueco artificial: ticks en 202608 hasta t=100, luego nada hasta
    t=4000 (hueco de 3900s). Pedir un instante DENTRO del hueco (t=200) debe
    devolver None bajo la tolerancia default (60s)."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ta = [base + 100.0, base + 4000.0, base + 4001.0]
    ticks = _synthetic_ticks_ava({
        "202607": ([], [], []),
        "202608": (ta, [10.0, 20.0, 20.0], [10.5, 20.5, 20.5]),
        "202609": ([], [], []),
    })
    hueco_t = base + 200.0  # dentro del hueco [100, 4000)
    assert ticks.first_at(hueco_t) is None


def test_first_at_hueco_artificial_con_tolerancia_grande_reproduce_comportamiento_viejo():
    """El comportamiento pre-fix (busqueda sin cota) sigue siendo alcanzable
    pasando una `tolerance_s` explicita mayor que el salto."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ta = [base + 100.0, base + 4000.0, base + 4001.0]
    ticks = _synthetic_ticks_ava({
        "202607": ([], [], []),
        "202608": (ta, [10.0, 20.0, 20.0], [10.5, 20.5, 20.5]),
        "202609": ([], [], []),
    }, tolerance_s=10_000.0)
    hueco_t = base + 200.0
    r = ticks.first_at(hueco_t)
    assert r is not None
    t_dev, bid, ask = r
    assert t_dev == base + 4000.0
    salto = t_dev - hueco_t
    assert salto == pytest.approx(3800.0)


def test_first_at_devuelve_none_si_no_hay_tick_posterior_en_los_3_meses():
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks_ava({
        "202607": ([base - 500.0], [1.0], [1.5]),
        "202608": ([base + 10.0], [1.0], [1.5]),
        "202609": ([], [], []),
    })
    r = ticks.first_at(base + 1000.0)
    assert r is None


def test_first_at_cruza_fichero_de_mes_pero_none_bajo_tolerancia_default():
    """Sin mas ticks en el mes actual tras t_sec, el candidato mas cercano es
    el primer tick del mes siguiente -- aqui 40 dias despues. Bajo la
    tolerancia default (60s) eso excede la cota: None."""
    base = float(int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()))
    t_junio_ultimo = base + 10.0
    t_julio_primero = base + 40 * 86400.0  # ~40 dias despues, cruzando meses
    ticks = _synthetic_ticks_ava({
        "202605": ([], [], []),
        "202606": ([t_junio_ultimo], [1.0], [1.5]),
        "202607": ([t_julio_primero], [2.0], [2.5]),
        "202608": ([], [], []),
    })
    pedido = base + 20.0  # tras el ultimo tick de junio, sin mas datos en junio
    assert ticks.first_at(pedido) is None


def test_first_at_cruza_fichero_de_mes_con_tolerancia_grande_reproduce_comportamiento_viejo():
    """El comportamiento pre-fix (cruzar de mes sin cota) sigue siendo
    alcanzable pasando una `tolerance_s` explicita mayor que el salto."""
    base = float(int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()))
    t_junio_ultimo = base + 10.0
    t_julio_primero = base + 40 * 86400.0
    ticks = _synthetic_ticks_ava({
        "202605": ([], [], []),
        "202606": ([t_junio_ultimo], [1.0], [1.5]),
        "202607": ([t_julio_primero], [2.0], [2.5]),
        "202608": ([], [], []),
    }, tolerance_s=45 * 86400.0)
    pedido = base + 20.0
    r = ticks.first_at(pedido)
    assert r is not None
    t_dev, bid, ask = r
    assert t_dev == t_julio_primero
    assert (t_dev - pedido) > 39 * 86400.0


def test_first_at_comprueba_distancia_none_si_excede_tolerancia_default():
    """Bajo la tolerancia default (60s) un tick a 999999s de distancia excede
    la cota -> None."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks_ava({"202608": ([base, base + 999999.0], [1.0, 9.0], [1.1, 9.1])})
    assert ticks.first_at(base + 5.0) is None


def test_first_at_dentro_de_tolerancia_default_devuelve_precio_tal_cual():
    """Complemento del anterior: un tick DENTRO de la tolerancia default
    (60s) se sigue devolviendo tal cual, sin marca ni modificacion."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks_ava({"202608": ([base, base + 30.0], [1.0, 9.0], [1.1, 9.1])})
    r = ticks.first_at(base + 5.0)
    assert r == (base + 30.0, 9.0, 9.1)


def test_first_at_limite_exacto_de_tolerancia_no_es_none():
    """Frontera: `t_tick - t_sec == tolerance` NO excede la tolerancia (el
    brief especifica '> tolerance' -> None, asi que '== tolerance' se sigue
    devolviendo). Mismo criterio que `bt.Ticks.first_at`."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks_ava({"202608": ([base + 60.0], [1.0], [1.1])}, tolerance_s=60.0)
    r = ticks.first_at(base)
    assert r == (base + 60.0, 1.0, 1.1)


def test_first_at_con_tolerancia_grande_reproduce_comportamiento_viejo():
    """El comportamiento pre-fix (sin comprobar distancia) sigue siendo
    alcanzable pasando una `tolerance_s` explicita mayor que el salto."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks_ava(
        {"202608": ([base, base + 999999.0], [1.0, 9.0], [1.1, 9.1])},
        tolerance_s=1_000_000.0,
    )
    r = ticks.first_at(base + 5.0)
    assert r == (base + 999999.0, 9.0, 9.1)


def test_ticksava_init_sin_argumentos_tolerancia_default_es_60():
    """`tolerance_s` es keyword-with-default (60.0s, identico a `bt.Ticks`),
    no posicional ni obligatorio -- `signal_level.py:299` (`TicksAva()`)
    llama sin argumentos y no debe romperse."""
    t = TicksAva()
    assert t.tolerance_s == 60.0


def test_ticksava_no_es_subclase_de_bt_ticks():
    """F.1 del brief: prohibido refactorizar `TicksAva` para heredar de
    `bt.Ticks` (su `_load` difiere y el cambio alteraria comportamiento mas
    alla de la cota). Verifica que el fix no lo hizo por accidente."""
    from scripts.analysis.realtick_bt.backtest import Ticks as BtTicks
    assert not issubclass(TicksAva, BtTicks)
