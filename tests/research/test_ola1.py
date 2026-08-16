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
