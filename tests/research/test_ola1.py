r"""tests/research/test_ola1.py -- OLA1-EXEC (paquete de ejecucion de la Ola 1).

Bloques se agregan incrementalmente segun se completan (TDD: rojo -> minimo
-> verde -> commit por bloque; ver
research/fases/F0-preparacion/02-specs/OLA1-EXEC-progreso.md).

Ver brief: research/fases/F0-preparacion/02-specs/OLA1-EXEC-brief-paquete-de-ejecucion.md

Todos los tests usan datos reales del sustrato salvo donde se diga
sinteticamente (fixtures sinteticas, marcadas como tales). Ninguna prueba de
este fichero corre la ola completa ni escribe en research/LEDGER.jsonl ni en
research/fases/F0-preparacion/04-resultados/OLA1/ (SS9 del brief): manifiestos
de humo, tmp_path, LEDGER temporal.
"""
from __future__ import annotations

import numpy as np
import pytest

BAR_SEC = 900


# --------------------------------------------------------------------- Bloque 1
class TestSustrato:
    def test_cargar_barras_preholdout(self):
        from scripts.research.baseline_golden import HOLDOUT_INI
        from scripts.research.ola1.sustrato import cargar_barras

        bars = cargar_barras()
        assert len(bars) == 8334
        assert all(b["t"] < HOLDOUT_INI for b in bars)

    def test_guarda_de_holdout_dispara(self):
        from scripts.research.baseline_golden import HOLDOUT_INI
        from scripts.research.ola1.sustrato import HoldoutVioladoError, verificar_holdout

        limpias = [{"t_in_exec": HOLDOUT_INI - 1000, "t_exit": HOLDOUT_INI - 100}]
        verificar_holdout(limpias)  # no debe lanzar

        intrusas = [
            {"t_in_exec": HOLDOUT_INI - 1000, "t_exit": HOLDOUT_INI - 100},
            {"t_in_exec": HOLDOUT_INI - 500, "t_exit": HOLDOUT_INI + 10},
        ]
        with pytest.raises(HoldoutVioladoError):
            verificar_holdout(intrusas)

    @pytest.mark.slow
    @pytest.mark.parametrize("sid", ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"])
    def test_control_reproduce_linea_base_para_las_tres_estrategias(self, sid):
        from scripts.analysis.realtick_bt import backtest as bt
        from scripts.research.ola1.sustrato import cargar_barras, verificar_control_contra_linea_base

        bars = cargar_barras()
        resolved = bt.build_all(bt.Ticks(), bars)
        resultado = verificar_control_contra_linea_base(sid, resolved[sid])
        assert resultado["identico"] is True
        assert resultado["n_congelado"] == resultado["n_control"]

    def test_control_no_reproduce_linea_base_dispara(self, monkeypatch, tmp_path):
        import json

        from scripts.research.ola1 import sustrato

        congelado = [{"a": 1.0, "t_in_exec": 1.0, "t_exit": 2.0}]
        (tmp_path / "posiciones_S6-K2P0.json").write_text(
            json.dumps(congelado), encoding="utf-8"
        )
        monkeypatch.setattr(sustrato, "BASELINE_DIR", tmp_path)

        distinta = [{"a": 2.0, "t_in_exec": 1.0, "t_exit": 2.0}]
        with pytest.raises(sustrato.ControlNoReproduceLineaBaseError):
            sustrato.verificar_control_contra_linea_base("S6-K2P0", distinta)

        # numero de posiciones distinto tambien dispara
        with pytest.raises(sustrato.ControlNoReproduceLineaBaseError):
            sustrato.verificar_control_contra_linea_base("S6-K2P0", [])

        # claves extra en el control (p.ej. R1) NO disparan -- solo se comparan
        # las claves que trae el congelado.
        extra = [{"a": 1.0, "t_in_exec": 1.0, "t_exit": 2.0, "R1": 999.0}]
        resultado = sustrato.verificar_control_contra_linea_base("S6-K2P0", extra)
        assert resultado["identico"] is True

    # ------------------------------------------------------------- D-60 (BLOCK-3(a)): P-02 substrate trim
    def test_cargar_barras_margen_extra_cero_es_byte_identico(self):
        from scripts.research.ola1.sustrato import cargar_barras

        sin_margen = cargar_barras()
        con_margen_cero = cargar_barras(margen_extra_s=0.0)
        assert con_margen_cero == sin_margen

    def test_cargar_barras_margen_p02_recorta_el_sustrato(self):
        from scripts.research.baseline_golden import HOLDOUT_INI
        from scripts.research.ola1.sustrato import MARGEN_P02_S, cargar_barras

        completo = cargar_barras()
        recortado = cargar_barras(margen_extra_s=MARGEN_P02_S)
        assert len(recortado) < len(completo)
        assert recortado == completo[: len(recortado)]  # prefijo exacto, nada mas se movio
        assert recortado[-1]["t"] < HOLDOUT_INI - MARGEN_P02_S

    @pytest.mark.slow
    @pytest.mark.parametrize("sid", ["S6-K2P0", "S7-TPNONE"])
    @pytest.mark.parametrize("max_hold_bars", [4, 10, 64, 128])
    def test_margen_p02_ningun_max_hold_bars_de_la_grilla_toca_el_holdout(self, sid, max_hold_bars):
        """La medicion exacta que fuerza D-60: con el sustrato recortado,
        NINGUN valor de la grilla congelada de P-02 (manifiesto._grid_p02,
        max=128) puede producir una posicion cuyo t_exit caiga en o despues
        de HOLDOUT_INI -- verificar_holdout debe pasar limpio, no lanzar."""
        import numpy as np

        from scripts.analysis.realtick_bt import backtest as bt
        from scripts.analysis.realtick_bt.overlay import overlay_kwargs
        from scripts.research.ola1.sustrato import MARGEN_P02_S, cargar_barras, verificar_holdout

        bars = cargar_barras(margen_extra_s=MARGEN_P02_S)
        ticks = bt.Ticks()
        bar_times = np.array([b["t"] for b in bars], dtype="float64")
        eff = overlay_kwargs(sid, {"max_hold_bars": max_hold_bars})
        raw = bt.run_ladder(eff, bars)
        resolved = [r for p in raw if (r := bt.resolve(p, ticks, bar_times)) is not None]
        verificar_holdout(resolved)  # no debe lanzar

    @pytest.mark.slow
    @pytest.mark.parametrize("sid", ["S6-K2P0", "S7-TPNONE"])
    def test_control_reproduce_linea_base_recortada(self, sid):
        """El control (default, sin max_hold_bars) sobre el sustrato
        RECORTADO debe reproducir EXACTAMENTE el prefijo (por t_exit) de la
        linea base T0.6 completa -- el motor es causal, asi que recortar el
        sustrato no puede cambiar ninguna posicion que ya cerraba dentro del
        tramo compartido."""
        import numpy as np

        from scripts.analysis.realtick_bt import backtest as bt
        from scripts.research.ola1.sustrato import (
            MARGEN_P02_S,
            cargar_barras,
            verificar_control_contra_linea_base_recortada,
        )

        bars = cargar_barras(margen_extra_s=MARGEN_P02_S)
        ticks = bt.Ticks()
        bar_times = np.array([b["t"] for b in bars], dtype="float64")
        raw = bt.run_ladder(bt._GL[sid], bars)
        resolved = [r for p in raw if (r := bt.resolve(p, ticks, bar_times)) is not None]
        resultado = verificar_control_contra_linea_base_recortada(sid, resolved, bars[-1]["t"])
        assert resultado["identico"] is True
        assert resultado["n_congelado_recortado"] == resultado["n_control"]

    def test_control_no_reproduce_linea_base_recortada_dispara(self, monkeypatch, tmp_path):
        import json

        from scripts.research.ola1 import sustrato

        congelado = [
            {"a": 1.0, "t_in_exec": 1.0, "t_exit": 2.0},
            {"a": 9.0, "t_in_exec": 100.0, "t_exit": 200.0},  # fuera del corte -> se ignora
        ]
        (tmp_path / "posiciones_S6-K2P0.json").write_text(json.dumps(congelado), encoding="utf-8")
        monkeypatch.setattr(sustrato, "BASELINE_DIR", tmp_path)

        # dentro del corte (ultimo_t_bar=50): solo la primera posicion cuenta.
        correcta = [{"a": 1.0, "t_in_exec": 1.0, "t_exit": 2.0}]
        resultado = sustrato.verificar_control_contra_linea_base_recortada(
            "S6-K2P0", correcta, ultimo_t_bar=50.0
        )
        assert resultado["identico"] is True
        assert resultado["n_congelado_recortado"] == 1

        distinta = [{"a": 2.0, "t_in_exec": 1.0, "t_exit": 2.0}]
        with pytest.raises(sustrato.ControlNoReproduceLineaBaseError):
            sustrato.verificar_control_contra_linea_base_recortada(
                "S6-K2P0", distinta, ultimo_t_bar=50.0
            )


# --------------------------------------------------------------------- Bloque 2
class TestParesContraControl:
    def test_pares_contra_control_coincide_con_todos(self, monkeypatch):
        from scripts.analysis.realtick_bt import backtest
        from scripts.analysis.realtick_bt.paired_harness import run_paired_arms

        class _FakeTicks:
            def __init__(self, ticks):
                self._t = np.array([t for t, _, _ in ticks], dtype="float64")
                self._bid = np.array([b for _, b, _ in ticks], dtype="float64")
                self._ask = np.array([a for _, _, a in ticks], dtype="float64")

            def first_at(self, t_sec):
                i = int(np.searchsorted(self._t, t_sec, "left"))
                if i < len(self._t):
                    return float(self._t[i]), float(self._bid[i]), float(self._ask[i])
                return None

            def range(self, t0, t1):
                lo = int(np.searchsorted(self._t, t0, "left"))
                hi = int(np.searchsorted(self._t, t1, "left"))
                return self._t[lo:hi], self._bid[lo:hi], self._ask[lo:hi]

        def _trend_bars(n=40):
            bars = []
            t0 = 1_700_000_000
            price = 100.0
            for i in range(n):
                drift = 0.8 if i < n // 2 else -0.8
                price += drift
                o = price - drift
                c = price
                h = max(o, c) + 0.3
                l = min(o, c) - 0.3
                bars.append({"t": t0 + BAR_SEC * i, "open": o, "high": h, "low": l,
                             "close": c, "volume": 1})
            return bars

        bars = _trend_bars()
        events_by_marker = {
            "default": [
                {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
                {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
                {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
                {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
            ],
            "u1": [
                {"idx": 1, "lado": "L", "precio": 101.0, "motivo": "ENTRY_L"},
                {"idx": 6, "lado": "L", "precio": 106.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
                {"idx": 6, "lado": "L", "precio": 106.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
                {"idx": 6, "lado": "L", "precio": 106.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
            ],
            "u2": [
                {"idx": 2, "lado": "S", "precio": 99.0, "motivo": "ENTRY_S"},
                {"idx": 7, "lado": "S", "precio": 94.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
                {"idx": 7, "lado": "S", "precio": 94.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
                {"idx": 7, "lado": "S", "precio": 94.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
            ],
        }

        def fake_simular_variant(bars_, **kw):
            return events_by_marker[kw["_marker"]]

        monkeypatch.setattr(backtest, "simular_variant", fake_simular_variant)
        ticks = _FakeTicks([(t0, 99.75, 100.25) for t0 in
                            (b["t"] + BAR_SEC for b in bars)])
        arms = {"default": {"_marker": "default"}, "u1": {"_marker": "u1"},
                "u2": {"_marker": "u2"}}
        sid = "S6-K2P0"

        todos = run_paired_arms(sid, arms, bars, ticks=ticks, pares="todos")
        contra_control = run_paired_arms(sid, arms, bars, ticks=ticks,
                                          pares="contra_control", brazo_control="default")

        assert len(contra_control.alignment_signal) == len(arms) - 1
        assert len(contra_control.alignment_filled) == len(arms) - 1
        for otro in ("u1", "u2"):
            key = ("default", otro)
            assert contra_control.alignment_signal[key] == todos.alignment_signal[key]
            assert contra_control.alignment_filled[key] == todos.alignment_filled[key]

    def test_pares_contra_control_valueerror_si_falta_el_control(self):
        from scripts.analysis.realtick_bt.paired_harness import run_paired_arms

        with pytest.raises(ValueError):
            run_paired_arms("S6-K2P0", {"a": {}, "b": {}}, [], pares="contra_control",
                             brazo_control="no_existe")


# --------------------------------------------------------------------- Bloque 3
class TestMetricas:
    def test_overlay_de_coste_solo_toca_salidas_por_nivel(self):
        from scripts.research.ola1.metricas import COSTE_CLP, metricas_de_brazo

        assert abs(COSTE_CLP - 21071.25) < 1e-6

        reasons_con_coste = ["EXIT_INITSL", "EXIT_SL_RAISED", "EXIT_TRAIL", "EXIT_STLINE"]
        reasons_sin_coste = ["EXIT_TP", "EXIT_STFLIP", "time_stop", "reverse"]

        posiciones = []
        t = 1_700_000_000.0
        for reason in reasons_con_coste + reasons_sin_coste:
            posiciones.append({
                "t_in_exec": t, "t_exit": t + 900.0, "net1": 1000.0, "reason": reason,
                "side_l": "L", "R1": 500.0, "margin1": 100.0,
            })
            t += 3600.0

        m = metricas_de_brazo("S6-K2P0", "default", {}, posiciones, [])
        esperado = sum(1000.0 for _ in reasons_sin_coste) + sum(
            1000.0 - COSTE_CLP for _ in reasons_con_coste
        )
        assert abs(m["net_con_coste_lote1"] - esperado) < 1e-6
        assert m["n_posiciones_con_coste"] == len(reasons_con_coste)

    def test_metricas_de_brazo_n_cero(self):
        from scripts.research.ola1.metricas import metricas_de_brazo

        m = metricas_de_brazo("S6-K2P0", "default", {}, [], [])
        assert m["n"] == 0
        assert m["net_por_posicion_lote1"] is None
        assert m["sharpe_por_posicion"] is None
        assert m["sharpe_diario_ann"] is None
        assert m["R_mediana"] is None

    @pytest.mark.slow
    def test_metricas_de_brazo_sobre_datos_reales(self):
        from scripts.analysis.realtick_bt import backtest as bt
        from scripts.research.ola1 import riesgo
        from scripts.research.ola1.metricas import metricas_de_brazo
        from scripts.research.ola1.sustrato import cargar_barras

        bars = cargar_barras()
        resolved = bt.build_all(bt.Ticks(), bars)
        sid = "S6-K2P0"
        posiciones = resolved[sid]
        r_vals = riesgo.r_por_posicion(sid, {}, posiciones, bars)
        for p, r in zip(posiciones, r_vals):
            p["R1"] = r
        m = metricas_de_brazo(sid, "default", {}, posiciones, bars)
        assert m["n"] == len(posiciones) == 624
        assert abs(m["net_lote1"] - sum(p["net1"] for p in posiciones)) < 1e-6
        assert m["n_R_no_computable"] == sum(1 for r in r_vals if r is None)
        assert set(m["n_por_reason"]) <= {
            "EXIT_INITSL", "EXIT_SL_RAISED", "EXIT_TRAIL", "EXIT_TP", "time_stop", "reverse",
        }


# --------------------------------------------------------------------- Bloque 4
class TestPareado:
    def test_ic_de_diferencia_cero_contiene_cero(self):
        from scripts.research.ola1 import pareado

        posiciones = []
        t0 = 1_700_000_000.0
        for i in range(10):
            posiciones.append({
                "t_in": t0 + i * 86400, "t_in_exec": t0 + i * 86400 + 60,
                "t_exit": t0 + i * 86400 + 900, "side": "LONG", "side_l": "L",
                "ficha": "F1", "net1": 100.0 * (i % 3 - 1),
            })
        r_control = [500.0] * len(posiciones)
        resultado = pareado.pareado_vs_control("S6-K2P0", posiciones, posiciones, r_control)
        assert resultado["tasa_emparejamiento"] == 1.0
        assert resultado["n_casadas"] == 10
        assert resultado["media_diff"] == 0.0
        assert resultado["suma_diff"] == 0.0
        assert resultado["ic_excluye_0"] is False
        assert resultado["p_bootstrap"] == 1.0
        assert resultado["n_identidades_duplicadas"] == 0

    def test_bootstrap_vectorizado_igual_al_ingenuo(self):
        from scripts.research.ola1.pareado import _bootstrap_bloques

        dias = ["2026-01-01", "2026-01-02", "2026-01-03"]
        diffs_por_dia = {
            "2026-01-01": [10.0, -5.0],
            "2026-01-02": [3.0],
            "2026-01-03": [-2.0, 4.0, 1.0],
        }
        suma_dia = {d: sum(v) for d, v in diffs_por_dia.items()}
        n_dia = {d: len(v) for d, v in diffs_por_dia.items()}
        B = 500
        seed = 20260816

        resultado = _bootstrap_bloques(dias, suma_dia, n_dia, B=B, seed=seed)

        rng = np.random.default_rng(seed)
        idx = rng.integers(0, len(dias), size=(B, len(dias)))
        stats_ingenuo = []
        for fila in idx:
            pool = []
            for i in fila:
                pool.extend(diffs_por_dia[dias[i]])
            stats_ingenuo.append(float(np.mean(pool)))
        stats_ingenuo = np.array(stats_ingenuo)
        ic_bajo_ing, ic_alto_ing = np.percentile(stats_ingenuo, [2.5, 97.5])

        assert abs(resultado["ic95_bajo"] - ic_bajo_ing) < 1e-9
        assert abs(resultado["ic95_alto"] - ic_alto_ing) < 1e-9
        frac_le0 = float(np.mean(stats_ingenuo <= 0))
        frac_ge0 = float(np.mean(stats_ingenuo >= 0))
        p_ing = min(max(2 * min(frac_le0, frac_ge0), 0.0), 1.0)
        assert abs(resultado["p_bootstrap"] - p_ing) < 1e-9

    def test_bootstrap_es_reproducible(self):
        from scripts.research.ola1.pareado import _bootstrap_bloques

        dias = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
        suma_dia = {"2026-01-01": 10.0, "2026-01-02": -3.0,
                    "2026-01-03": 5.0, "2026-01-04": 0.0}
        n_dia = {"2026-01-01": 2, "2026-01-02": 1, "2026-01-03": 3, "2026-01-04": 1}
        r1 = _bootstrap_bloques(dias, suma_dia, n_dia)
        r2 = _bootstrap_bloques(dias, suma_dia, n_dia)
        assert r1 == r2

    def test_no_evaluable_si_no_hay_casadas_o_menos_de_2_dias(self):
        from scripts.research.ola1 import pareado

        resultado = pareado.pareado_vs_control("S6-K2P0", [], [], [])
        assert resultado["p_bootstrap"] is None
        assert resultado["motivo_no_evaluable"] == "n_casadas == 0"

        t0 = 1_700_000_000.0
        posiciones = [{
            "t_in": t0, "t_in_exec": t0 + 60, "t_exit": t0 + 900, "side": "LONG",
            "side_l": "L", "ficha": "F1", "net1": 100.0,
        }]
        resultado2 = pareado.pareado_vs_control("S6-K2P0", posiciones, posiciones, [500.0])
        assert resultado2["p_bootstrap"] is None
        assert resultado2["motivo_no_evaluable"] == "n_dias_bloque < 2"

    def test_identidades_duplicadas_se_cuentan_y_publican(self):
        from scripts.research.ola1 import pareado

        t0 = 1_700_000_000.0
        # dos posiciones con la MISMA identidad (mismo t_in/side/ficha) en el
        # brazo -- debe quedarse con la primera por t_exit y contar 1 duplicada.
        posiciones_brazo = [
            {"t_in": t0, "t_in_exec": t0 + 60, "t_exit": t0 + 900, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": 50.0},
            {"t_in": t0, "t_in_exec": t0 + 60, "t_exit": t0 + 1800, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": 999.0},
        ]
        posiciones_control = [
            {"t_in": t0, "t_in_exec": t0 + 60, "t_exit": t0 + 900, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": 10.0},
        ]
        resultado = pareado.pareado_vs_control("S6-K2P0", posiciones_brazo,
                                                posiciones_control, [500.0])
        assert resultado["n_identidades_duplicadas"] == 1
        assert resultado["n_casadas"] == 1
        assert resultado["media_diff"] == 40.0  # 50.0 - 10.0, la PRIMERA por t_exit


# --------------------------------------------------------------------- Bloque 5
class TestSecundarias:
    def test_secundaria_p02_podadas_y_amputadas(self):
        from scripts.research.ola1.secundarias import secundaria_p02

        t0 = 1_700_000_000.0
        posiciones_brazo = [
            {"t_in": t0, "t_in_exec": t0 + 60, "t_exit": t0 + 900, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": -10.0, "reason": "time_stop"},
            {"t_in": t0 + 3600, "t_in_exec": t0 + 3660, "t_exit": t0 + 4500, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": 20.0, "reason": "time_stop"},
            {"t_in": t0 + 7200, "t_in_exec": t0 + 7260, "t_exit": t0 + 8100, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": 5.0, "reason": "EXIT_TP"},
        ]
        posiciones_control = [
            {"t_in": t0, "t_in_exec": t0 + 60, "t_exit": t0 + 900, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": -50.0, "reason": "EXIT_INITSL"},
            {"t_in": t0 + 3600, "t_in_exec": t0 + 3660, "t_exit": t0 + 4500, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": 100.0, "reason": "EXIT_TRAIL"},
            {"t_in": t0 + 7200, "t_in_exec": t0 + 7260, "t_exit": t0 + 8100, "side": "LONG",
             "side_l": "L", "ficha": "F1", "net1": 5.0, "reason": "EXIT_TP"},
        ]
        r = secundaria_p02("S6-K2P0", posiciones_brazo, posiciones_control)
        assert r["n_cerradas_por_time_stop"] == 2
        assert r["podadas_perdedoras"] == {"n": 1, "suma_delta": 40.0}
        assert r["amputadas_ganadoras"] == {"n": 1, "suma_delta": -80.0}
        assert r["net_medio_time_stop_lote1"] == 5.0
        assert r["wr_time_stop"] == 50.0

    def test_reflip_definicion(self):
        from scripts.research.ola1.secundarias import secundaria_p03

        t0 = 1_700_000_000.0
        posiciones = [
            # dentro de 3 barras (2700s), sentido contrario, resultado negativo -> reflip FALSO
            {"t_exit": t0, "t_in_exec": t0 + 100, "side": "LONG", "ficha": "F1", "net1": 5.0},
            {"t_exit": t0 + 1000, "t_in_exec": t0 + 100, "side": "SHORT", "ficha": "F1",
             "net1": -3.0},
            # fuera de la ventana (>2700s) -> no cuenta como reflip
            {"t_exit": t0 + 5000, "t_in_exec": t0 + 5000 + 3000, "side": "LONG", "ficha": "F1",
             "net1": 1.0},
            {"t_exit": t0 + 9000, "t_in_exec": t0 + 9000 + 3600, "side": "SHORT", "ficha": "F1",
             "net1": 2.0},
        ]
        r = secundaria_p03("S6-K2P0", posiciones)
        assert r["n_reflips"] == 1
        assert r["n_reflips_falsos"] == 1
        assert r["pct_reflip_falso"] == 1.0

    def test_reflip_n_cero_es_none_no_cero(self):
        from scripts.research.ola1.secundarias import secundaria_p03

        t0 = 1_700_000_000.0
        posiciones = [
            {"t_exit": t0, "t_in_exec": t0 + 100, "side": "LONG", "ficha": "F1", "net1": 5.0},
        ]
        r = secundaria_p03("S6-K2P0", posiciones)
        assert r["n_reflips"] == 0
        assert r["pct_reflip_falso"] is None

    def test_secundaria_p08_suma_exactamente_la_diferencia(self):
        from scripts.research.ola1.secundarias import secundaria_p08

        t0 = 1_700_000_000.0

        def _pos(t_off, net1, reason):
            return {"t_in": t0 + t_off, "t_in_exec": t0 + t_off + 60,
                    "t_exit": t0 + t_off + 900, "side": "LONG", "side_l": "L",
                    "ficha": "F1", "net1": net1, "reason": reason}

        posiciones_brazo = [
            _pos(0, 10.0, "EXIT_TRAIL"),      # salvadas: control salio STLINE, brazo no
            _pos(3600, -20.0, "EXIT_STLINE"),  # mismo_stop_peor_fill: ambos STLINE
            _pos(7200, 5.0, "EXIT_TP"),        # otros
        ]
        posiciones_control = [
            _pos(0, -30.0, "EXIT_STLINE"),
            _pos(3600, -15.0, "EXIT_STLINE"),
            _pos(7200, 2.0, "EXIT_TP"),
        ]
        r = secundaria_p08("S6-K2P0", posiciones_brazo, posiciones_control)
        assert r["salvadas"] == {"n": 1, "suma_delta": 40.0}
        assert r["mismo_stop_peor_fill"] == {"n": 1, "suma_delta": -5.0}
        assert r["otros"] == {"n": 1, "suma_delta": 3.0}
        suma = (r["salvadas"]["suma_delta"] + r["mismo_stop_peor_fill"]["suma_delta"]
                + r["otros"]["suma_delta"])
        esperado = sum(pb["net1"] - pc["net1"]
                       for pb, pc in zip(posiciones_brazo, posiciones_control))
        assert abs(suma - esperado) < 1e-6


# --------------------------------------------------------------------- Bloque 8
class TestManifiesto:
    def test_los_44_preregistrados_son_subconjunto_exacto(self, tmp_path):
        """El test mas importante del fichero: codifica los 44 brazos
        confirmatorios TAL COMO los lista el pre-registro (`22ee9fb`) +
        ampliacion E-04 (`1c7279d`) y comprueba, contra el YAML generado,
        que los 44 estan presentes con su overlay EXACTO y que hay 157
        brazos en total."""
        from scripts.research.ola1.manifiesto import construir_manifiesto

        data = construir_manifiesto(engine_sha="test-sha")
        por_run = {c["run_key"]: c for c in data["corridas"]}

        # P-02, S6 y S7: off(default), 10, 15, 20, 30, 48, 64 -- 7 x 2 = 14
        p02_confirm = {
            "default": {}, "mhb10": {"max_hold_bars": 10}, "mhb15": {"max_hold_bars": 15},
            "mhb20": {"max_hold_bars": 20}, "mhb30": {"max_hold_bars": 30},
            "mhb48": {"max_hold_bars": 48}, "mhb64": {"max_hold_bars": 64},
        }
        for run_key in ("P02-S6", "P02-S7"):
            corrida = por_run[run_key]
            assert set(corrida["confirmatorios"]) == set(p02_confirm)
            for nombre, overlay in p02_confirm.items():
                assert corrida["brazos"][nombre] == overlay

        # P-03, S6: default + {25,50,75}x{1,2}x{3,5,10} = 1 + 18 = 19
        p03 = por_run["P03-S6"]
        p03_confirm_esperados = {"default"}
        for u in (25, 50, 75):
            for lb in (1, 2):
                for h in (3, 5, 10):
                    nombre = f"u{u}-lb{lb}-h{h}"
                    p03_confirm_esperados.add(nombre)
                    assert p03["brazos"][nombre] == {
                        "ac_decel_umbral": round(u * 0.01, 10),
                        "ac_decel_lookback": lb,
                        "ac_modulate_hold_bars": h,
                    }
        assert set(p03["confirmatorios"]) == p03_confirm_esperados
        assert len(p03_confirm_esperados) == 19
        assert p03["brazos"]["default"] == {}

        # P-05, SuperTrend: {2.0,2.5,3.0(default),3.5,4.0,4.5,5.0} = 7
        p05 = por_run["P05-ST"]
        p05_confirm = {
            "default": {}, "mult2.00": {"mult": 2.0}, "mult2.50": {"mult": 2.5},
            "mult3.50": {"mult": 3.5}, "mult4.00": {"mult": 4.0},
            "mult4.50": {"mult": 4.5}, "mult5.00": {"mult": 5.0},
        }
        assert set(p05["confirmatorios"]) == set(p05_confirm)
        for nombre, overlay in p05_confirm.items():
            assert p05["brazos"][nombre] == overlay

        # P-08, SuperTrend: {0.00(default),0.10,0.20,0.30} = 4
        p08 = por_run["P08-ST"]
        p08_confirm = {
            "default": {}, "slo0.10": {"sl_offset": 0.10}, "slo0.20": {"sl_offset": 0.20},
            "slo0.30": {"sl_offset": 0.30},
        }
        assert set(p08["confirmatorios"]) == set(p08_confirm)
        for nombre, overlay in p08_confirm.items():
            assert p08["brazos"][nombre] == overlay

        # totales: 44 confirmatorios, 157 brazos
        n_confirm_total = sum(len(c["confirmatorios"]) for c in data["corridas"])
        n_brazos_total = sum(len(c["brazos"]) for c in data["corridas"])
        assert n_confirm_total == 44
        assert n_brazos_total == 157
        assert [len(c["brazos"]) for c in data["corridas"]] == [17, 17, 95, 17, 11]

    def test_manifiesto_valida_contra_el_runner(self, tmp_path):
        from scripts.research.ola1.manifiesto import construir_manifiesto, escribir_manifiesto
        from scripts.research.runner import tasks_ola1  # noqa: F401 -- registra ola1_paired
        from scripts.research.runner.manifest import load_manifest

        data = construir_manifiesto(engine_sha="test-sha")
        salida = tmp_path / "manifiesto.yaml"
        escribir_manifiesto(data, salida)

        cargado = load_manifest(salida)  # no debe lanzar
        assert len(cargado["corridas"]) == 5
        for c in cargado["corridas"]:
            assert c["tipo"] == "ola1_paired"


class TestTaskType:
    def test_task_type_registrado_y_manifiesto_de_humo_corre(self, tmp_path):
        from scripts.research.runner import tasks_ola1  # noqa: F401 -- registra ola1_paired
        from scripts.research.runner import tasks
        from scripts.research.runner.manifest import load_manifest
        from scripts.research.runner.runner import run_manifest

        assert "ola1_paired" in tasks.get_registry()

        manifest_path = tmp_path / "humo.yaml"
        resultados_dir = tmp_path / "resultados"
        ledger_path = tmp_path / "LEDGER.jsonl"
        manifest_path.write_text(f"""
experimento: OLA1-humo
area: B
etapa: F0
hipotesis: research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-ola1.md
substrate_id: capitaria-ticks-2026-preholdout
engine_sha: humo
salidas:
  resultados: {resultados_dir.as_posix()}
  ledger: append
corridas:
  - run_key: HUMO-P08
    tipo: ola1_paired
    palanca: P-08
    sid: SuperTrend-p14x3-M15
    clase: "1-A"
    brazo_control: default
    secundaria: p08
    brazos:
      default: {{}}
      slo0.10: {{sl_offset: 0.10}}
    confirmatorios: [default, slo0.10]
""", encoding="utf-8")

        load_manifest(manifest_path)  # no debe lanzar; ve 1 corrida con tipo registrado

        resultado = run_manifest(manifest_path, ledger_path=ledger_path,
                                  on_error="continue", workers=1)
        assert resultado["failed_run_keys"] == []

        out_dir = resultados_dir / "HUMO-P08"
        assert (out_dir / "metricas.json").exists()
        assert (out_dir / "posiciones.csv").exists()
        assert (out_dir / "alineacion.json").exists()
        assert (out_dir / "_brazos.txt").exists()
        assert ledger_path.exists()

    def test_resolver_con_progreso_idem_run_paired_arms(self, monkeypatch, tmp_path):
        """El camino propio de tasks_ola1 (resolucion brazo-a-brazo con
        progreso) debe producir posiciones IDENTICAS a run_paired_arms para
        un caso de 2 brazos (brief Bloque 6, sin divergencia silenciosa)."""
        from scripts.analysis.realtick_bt import backtest
        from scripts.analysis.realtick_bt.paired_harness import run_paired_arms
        from scripts.research.runner.tasks_ola1 import _resolver_brazos_con_progreso

        def _trend_bars(n=40):
            bars = []
            t0 = 1_700_000_000
            price = 100.0
            for i in range(n):
                drift = 0.8 if i < n // 2 else -0.8
                price += drift
                o = price - drift
                c = price
                h = max(o, c) + 0.3
                l = min(o, c) - 0.3
                bars.append({"t": t0 + BAR_SEC * i, "open": o, "high": h, "low": l,
                             "close": c, "volume": 1})
            return bars

        class _FakeTicks:
            def __init__(self, ticks):
                self._t = np.array([t for t, _, _ in ticks], dtype="float64")
                self._bid = np.array([b for _, b, _ in ticks], dtype="float64")
                self._ask = np.array([a for _, _, a in ticks], dtype="float64")

            def first_at(self, t_sec):
                i = int(np.searchsorted(self._t, t_sec, "left"))
                if i < len(self._t):
                    return float(self._t[i]), float(self._bid[i]), float(self._ask[i])
                return None

            def range(self, t0, t1):
                lo = int(np.searchsorted(self._t, t0, "left"))
                hi = int(np.searchsorted(self._t, t1, "left"))
                return self._t[lo:hi], self._bid[lo:hi], self._ask[lo:hi]

        bars = _trend_bars()
        events = [
            {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
            {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
            {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
            {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
        ]
        monkeypatch.setattr(backtest, "simular_variant", lambda bars_, **kw: events)
        ticks = _FakeTicks([(t0, 99.75, 100.25) for t0 in
                            (b["t"] + BAR_SEC for b in bars)])
        sid = "S6-K2P0"
        arms = {"default": {}, "mhb5": {"max_hold_bars": 5}}

        expected = run_paired_arms(sid, arms, bars, ticks=ticks, pares="contra_control",
                                    brazo_control="default")
        _sig, resolved = _resolver_brazos_con_progreso(sid, arms, bars, ticks, tmp_path)
        assert resolved == expected.arms


class TestRiesgo:
    @pytest.mark.slow
    @pytest.mark.parametrize("sid", ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"])
    def test_r_por_posicion_escalera_y_supertrend(self, sid):
        from scripts.analysis.realtick_bt import backtest as bt
        from scripts.research.ola1 import riesgo
        from scripts.research.ola1.sustrato import cargar_barras

        bars = cargar_barras()
        resolved = bt.build_all(bt.Ticks(), bars)
        posiciones = resolved[sid]
        r_vals = riesgo.r_por_posicion(sid, {}, posiciones, bars)
        assert len(r_vals) == len(posiciones)
        n_computable = sum(1 for r in r_vals if r is not None and r > 0)
        assert n_computable / len(posiciones) >= 0.95, (
            f"{sid}: solo {n_computable}/{len(posiciones)} R computables (>=95% esperado)"
        )
