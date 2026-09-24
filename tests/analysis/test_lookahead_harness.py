"""T0.7-M-C -- Auditoria look-ahead del harness de backtest largo.

INVESTIGADOR REPORT-ONLY. No prueba que el codigo "este bien" ni "roto":
caracteriza el comportamiento EXACTO de `Ticks.first_at` (backtest.py:130-139)
con huecos artificiales, y las funciones puras del script de auditoria
(`scripts/analysis/realtick_bt/auditoria_lookahead.py`).

Brief: research/fases/F0-preparacion/02-specs/T0.7-M-C-brief-auditoria-lookahead-harness.md
No se toca `backtest.py` (R1-bis / territorio ajeno a esta tarea): solo se
importa read-only y se construyen datos sinteticos via el cache interno
`Ticks._m`, sin tocar disco.

ADDENDUM T0.7-M-E (2026-08-15): el defecto que este fichero caracterizaba
(`Ticks.first_at` sin cota temporal) fue corregido en `backtest.py:130-149`
(brief `02-specs/T0.7-M-E-brief-fix-lookahead-motor-largo.md`). Los tests que
antes afirmaban el comportamiento SIN cota ahora afirman el comportamiento
CON cota (tolerancia default 60.0s -> None fuera de rango); el comportamiento
viejo se conserva verificado pasando `tolerance_s` grande explicito. Ver el
diff de este fichero / mensaje del commit T0.7-M-E para el detalle exacto.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from scripts.analysis.realtick_bt.backtest import Ticks
from scripts.analysis.realtick_bt import auditoria_lookahead as al


def _synthetic_ticks(
    month_data: dict[str, tuple[list[float], list[float], list[float]]],
    tolerance_s: float | None = None,
) -> Ticks:
    """Construye un `Ticks` con `_m` precargado a mano (sin tocar disco),
    para que `_load` (que solo consulta el cache si `ym in self._m`) nunca
    llegue a abrir un parquet. `tolerance_s=None` deja el default de
    `Ticks.__init__` (T0.7-M-E: 60.0s)."""
    t = Ticks() if tolerance_s is None else Ticks(tolerance_s=tolerance_s)
    for ym, (ta, bid, ask) in month_data.items():
        t._m[ym] = (np.array(ta, dtype="float64"), np.array(bid, dtype="float64"),
                    np.array(ask, dtype="float64"))
    return t


# --------------------------------------------------------------------- Q1


def test_first_at_hueco_artificial_devuelve_none_bajo_tolerancia_default():
    """T0.7-M-E: hueco de mantenimiento artificial: ticks en 202608 hasta
    t=100, luego nada hasta t=4000 (hueco de 3900s, mayor que cualquier corte
    de mantenimiento medido). Pedir un instante DENTRO del hueco (t=200) debe
    devolver None bajo la tolerancia default (60s): el salto al tick de
    despues del hueco (3800s) excede la tolerancia. ANTES de T0.7-M-E este
    test (entonces `..._sin_cota`) afirmaba que se devolvia el tick de
    t=4000 sin cota -- ese era exactamente el look-ahead medido (945/13.672
    llamadas, T0.7-M-C)."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ta = [base + 100.0, base + 4000.0, base + 4001.0]
    ticks = _synthetic_ticks({
        "202607": ([], [], []),  # explicito: aisla del disco real (202607.parquet existe)
        "202608": (ta, [10.0, 20.0, 20.0], [10.5, 20.5, 20.5]),
        "202609": ([], [], []),
    })
    hueco_t = base + 200.0  # dentro del hueco [100, 4000)
    assert ticks.first_at(hueco_t) is None


def test_first_at_hueco_artificial_con_tolerancia_grande_reproduce_comportamiento_viejo():
    """El comportamiento pre-T0.7-M-E (busqueda sin cota) sigue siendo
    alcanzable pasando una `tolerance_s` explicita mayor que el salto."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ta = [base + 100.0, base + 4000.0, base + 4001.0]
    ticks = _synthetic_ticks({
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
    assert salto > 3600  # > 1h: el mismo orden de magnitud que 3592-3665s medidos en la replica


def test_first_at_devuelve_none_si_no_hay_tick_posterior_en_los_3_meses():
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks({
        "202607": ([base - 500.0], [1.0], [1.5]),
        "202608": ([base + 10.0], [1.0], [1.5]),
        "202609": ([], [], []),
    })
    # pedir un instante posterior al ultimo tick de los 3 meses candidatos
    r = ticks.first_at(base + 1000.0)
    assert r is None


def test_first_at_cruza_fichero_de_mes_pero_none_bajo_tolerancia_default():
    """T0.7-M-E: sin mas ticks en el mes actual tras t_sec, el candidato mas
    cercano es el primer tick del mes siguiente -- aqui 40 dias despues.
    Bajo la tolerancia default (60s) eso excede la cota: None. ANTES de
    T0.7-M-E este test (entonces `..._sin_cota`) afirmaba que se devolvia
    ese tick lejano sin cota."""
    base = float(int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()))
    t_junio_ultimo = base + 10.0
    t_julio_primero = base + 40 * 86400.0  # ~40 dias despues, cruzando meses
    ticks = _synthetic_ticks({
        "202605": ([], [], []),  # explicito: aisla del disco real (202605.parquet existe)
        "202606": ([t_junio_ultimo], [1.0], [1.5]),
        "202607": ([t_julio_primero], [2.0], [2.5]),
        "202608": ([], [], []),
    })
    pedido = base + 20.0  # tras el ultimo tick de junio, sin mas datos en junio
    assert ticks.first_at(pedido) is None


def test_first_at_cruza_fichero_de_mes_con_tolerancia_grande_reproduce_comportamiento_viejo():
    """El comportamiento pre-T0.7-M-E (cruzar de mes sin cota) sigue siendo
    alcanzable pasando una `tolerance_s` explicita mayor que el salto."""
    base = float(int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()))
    t_junio_ultimo = base + 10.0
    t_julio_primero = base + 40 * 86400.0  # ~40 dias despues, cruzando meses
    ticks = _synthetic_ticks({
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
    """T0.7-M-E: bajo la tolerancia default (60s) un tick a 999999s de
    distancia excede la cota -> None. ANTES de T0.7-M-E este test (entonces
    `..._no_comprueba_distancia_devuelve_precio_tal_cual`) afirmaba que
    first_at no aplicaba ninguna tolerancia y devolvia ese precio lejano tal
    cual -- exactamente el defecto que este task corrige."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks({"202608": ([base, base + 999999.0], [1.0, 9.0], [1.1, 9.1])})
    assert ticks.first_at(base + 5.0) is None


def test_first_at_dentro_de_tolerancia_default_devuelve_precio_tal_cual():
    """Complemento del anterior: un tick DENTRO de la tolerancia default
    (60s) se sigue devolviendo tal cual, sin marca ni modificacion -- el fix
    no toca calls sanos."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks({"202608": ([base, base + 30.0], [1.0, 9.0], [1.1, 9.1])})
    r = ticks.first_at(base + 5.0)
    assert r == (base + 30.0, 9.0, 9.1)


def test_first_at_limite_exacto_de_tolerancia_no_es_none():
    """Frontera: `t_tick - t_sec == tolerance` NO excede la tolerancia (el
    brief especifica '> tolerance' -> None, así que '== tolerance' se sigue
    devolviendo)."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks({"202608": ([base + 60.0], [1.0], [1.1])}, tolerance_s=60.0)
    r = ticks.first_at(base)
    assert r == (base + 60.0, 1.0, 1.1)


def test_first_at_con_tolerancia_grande_reproduce_comportamiento_viejo():
    """El comportamiento pre-T0.7-M-E (sin comprobar distancia) sigue siendo
    alcanzable pasando una `tolerance_s` explicita mayor que el salto."""
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks(
        {"202608": ([base, base + 999999.0], [1.0, 9.0], [1.1, 9.1])},
        tolerance_s=1_000_000.0,
    )
    r = ticks.first_at(base + 5.0)
    assert r == (base + 999999.0, 9.0, 9.1)


def test_ticks_init_sin_argumentos_tolerancia_default_es_60():
    """E.1: `tolerance_s` es keyword-with-default (60.0s), no posicional ni
    obligatorio -- `AvaTicks.__init__` (scripts/research/backtest_largo_ava.py:283)
    llama `super().__init__()` sin argumentos y no debe romperse."""
    t = Ticks()
    assert t.tolerance_s == 60.0


# --------------------------------------------------------------------- funciones puras de auditoria_lookahead


def test_decision_grid_bar_close_alineada_a_900s():
    t0 = 900.0  # ya en la rejilla -- primer cierre es el propio t0
    t1 = 900.0 + 3 * 900.0
    grid = al.decision_grid(t0, t1, bar_sec=900)
    assert grid == [900.0, 1800.0, 2700.0]


def test_decision_grid_redondea_al_siguiente_cierre_si_t0_no_esta_alineado():
    grid = al.decision_grid(1000.0, 1000.0 + 3 * 900.0, bar_sec=900)
    assert grid == [1800.0, 2700.0, 3600.0]


def test_decision_grid_vacia_si_ventana_menor_a_un_bar():
    grid = al.decision_grid(1000.0, 1000.0, bar_sec=900)
    assert grid == []


def test_medir_delays_marca_no_evaluable_cuando_first_at_none():
    ticks = _synthetic_ticks({"202608": ([], [], [])})
    rows = al.medir_delays(ticks, [1.0, 2.0])
    assert all(r["evaluable"] is False for r in rows)
    assert all(r["delta_s"] is None for r in rows)


def test_medir_delays_calcula_delta_correcto():
    base = float(int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()))
    ticks = _synthetic_ticks({"202608": ([base + 50.0], [1.0], [1.1])})
    rows = al.medir_delays(ticks, [base + 10.0])
    assert rows[0]["evaluable"] is True
    assert rows[0]["delta_s"] == pytest.approx(40.0)


def test_resumen_delays_percentiles_y_umbrales():
    rows = [
        {"delta_s": 0.5, "evaluable": True},
        {"delta_s": 30.0, "evaluable": True},
        {"delta_s": 70.0, "evaluable": True},       # > 60s
        {"delta_s": 1000.0, "evaluable": True},      # > 900s (15min)
        {"delta_s": 4000.0, "evaluable": True},      # > 3600s (1h)
        {"delta_s": None, "evaluable": False},
    ]
    r = al.resumen_delays(rows)
    assert r["n_total"] == 6
    assert r["n_evaluable"] == 5
    assert r["n_no_evaluable"] == 1
    assert r["max"] == 4000.0
    assert r["n_gt_60s"] == 3
    assert r["n_gt_15min"] == 2
    assert r["n_gt_1h"] == 1


def test_resumen_delays_vacio():
    r = al.resumen_delays([{"delta_s": None, "evaluable": False}])
    assert r["n_evaluable"] == 0
    assert r["p50"] is None
    assert r["n_gt_60s"] == 0


def test_clasificar_hueco_fin_de_semana():
    # 2026-08-08 es sabado (verificar con datetime.weekday())
    sabado = float(int(datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc).timestamp()))
    assert al.clasificar_hueco(sabado) == "fin_de_semana"


def test_clasificar_hueco_corte_mantenimiento_dia_normal():
    # 2026-08-04 es martes; 17:15 cae dentro de 16:59-17:59
    t = float(int(datetime(2026, 8, 4, 17, 15, 0, tzinfo=timezone.utc).timestamp()))
    assert al.clasificar_hueco(t) == "corte_mantenimiento"


def test_clasificar_hueco_viernes_ventana_ampliada():
    # 2026-08-07 es viernes; 18:30 cae dentro de 16:55-18:49 (viernes) pero
    # NO dentro de 16:59-17:59 (dia normal) -- distingue la ventana ampliada
    t = float(int(datetime(2026, 8, 7, 18, 30, 0, tzinfo=timezone.utc).timestamp()))
    assert al.clasificar_hueco(t) == "corte_mantenimiento"


def test_clasificar_hueco_otro():
    t = float(int(datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc).timestamp()))
    assert al.clasificar_hueco(t) == "otro"


def test_clasificar_hueco_viernes_noche_es_cierre_semanal_no_otro():
    """Hallazgo empirico (medicion real sobre Capitaria, ventana 2026-07-27..
    08-11): los instantes 2026-07-31 19:00..23:45 (viernes, TRAS el fin del
    corte ampliado 16:55-18:49) devuelven TODOS el mismo tick de reapertura
    2026-08-02 18:00:05.896 (domingo) -- es decir, son la MISMA cola continua
    del cierre semanal, no un hueco distinto. Antes de este fix,
    `clasificar_hueco` los marcaba "otro" (40 casos), separandolos
    artificialmente del cierre de fin de semana."""
    t = float(int(datetime(2026, 7, 31, 19, 0, 0, tzinfo=timezone.utc).timestamp()))
    assert al.clasificar_hueco(t) == "fin_de_semana"
    t2 = float(int(datetime(2026, 7, 31, 23, 45, 0, tzinfo=timezone.utc).timestamp()))
    assert al.clasificar_hueco(t2) == "fin_de_semana"
    # el propio corte ampliado del viernes (16:55-18:49) sigue siendo
    # "corte_mantenimiento", no "fin_de_semana"
    t3 = float(int(datetime(2026, 7, 31, 18, 30, 0, tzinfo=timezone.utc).timestamp()))
    assert al.clasificar_hueco(t3) == "corte_mantenimiento"
