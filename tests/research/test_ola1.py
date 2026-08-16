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
