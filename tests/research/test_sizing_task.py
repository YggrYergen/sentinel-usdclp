r"""tests/research/test_sizing_task.py -- OLA2 task-type `ola1_sizing` (P-13/
P-15/P-16/P-17/P-18). Pairing is by POSITION (index-aligned per sid over the
SAME T0.6 baseline), not by entry_identity -- these tests exercise that
contract directly, with a small synthetic baseline (never the real T0.6 JSON,
to keep the unit tests fast and independent of disk state) plus one
end-to-end smoke test through the registered task-type on the REAL baseline.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from scripts.analysis.realtick_bt.sizing import SizingConfig, apply_sizing
from scripts.research.ola1.tasks_sizing import (
    SizingBaselineDivergedError,
    _metricas_arm,
    _pareado_trivial,
    _pool,
    cargar_baseline,
)

BAR_SEC = 900
SIDS = ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"]


def _pos(sid: str, ficha: str, t_in: float, t_out: float, net1: float) -> dict:
    return {
        "side_l": "L", "side": "LONG", "ficha": ficha, "reason": "EXIT_TP",
        "t_in": t_in, "t_out": t_out, "entry_bid": 100.0, "exit_bid": 101.0,
        "same_bar": False, "spread": 0.5, "band": 0.5, "entry_fill": 100.0,
        "exit_fill": 101.0, "t_in_exec": t_in, "entry_delay_bars": 0,
        "t_exit": t_out, "net1": net1, "margin1": 1000.0, "level_slip": False,
    }


def _synthetic_baseline() -> dict[str, list[dict]]:
    return {
        "S6-K2P0": [
            _pos("S6-K2P0", "F1", 0, BAR_SEC, 100.0),
            _pos("S6-K2P0", "F2", BAR_SEC, 2 * BAR_SEC, -40.0),
        ],
        "S7-TPNONE": [
            _pos("S7-TPNONE", "F1", 2 * BAR_SEC, 3 * BAR_SEC, 30.0),
        ],
        "SuperTrend-p14x3-M15": [
            _pos("SuperTrend-p14x3-M15", "F1", 3 * BAR_SEC, 4 * BAR_SEC, -10.0),
        ],
    }


class TestPool:
    def test_pool_flattens_the_three_strategies(self):
        baseline = _synthetic_baseline()
        pool = _pool(baseline)
        assert len(pool) == 4


class TestMetricasArm:
    def test_neutral_config_reproduces_the_baseline_sum(self):
        baseline = _synthetic_baseline()
        sized = apply_sizing(baseline, SizingConfig())
        m = _metricas_arm(sized)
        assert m["n"] == 4
        assert m["net_lote1"] == pytest.approx(100.0 - 40.0 + 30.0 - 10.0)
        assert m["n_por_sid"]["S6-K2P0"] == 2

    def test_kelly_mult_scales_net_lote1(self):
        baseline = _synthetic_baseline()
        neutral = _metricas_arm(apply_sizing(baseline, SizingConfig()))
        kelly = _metricas_arm(apply_sizing(baseline, SizingConfig(kelly_mult=0.25)))
        assert kelly["net_lote1"] != neutral["net_lote1"]


class TestPareadoTrivial:
    def test_trivially_100_percent_paired_by_construction(self):
        baseline = _synthetic_baseline()
        control = apply_sizing(baseline, SizingConfig())
        arm = apply_sizing(baseline, SizingConfig(kelly_mult=0.5))
        p = _pareado_trivial(arm, control)
        assert p["tasa_emparejamiento"] == 1.0
        assert p["n_casadas"] == 4
        assert p["n_solo_brazo"] == 0 and p["n_solo_control"] == 0

    def test_neutral_arm_against_itself_gives_zero_diff(self):
        baseline = _synthetic_baseline()
        control = apply_sizing(baseline, SizingConfig())
        same = apply_sizing(baseline, SizingConfig())
        p = _pareado_trivial(same, control)
        assert p["media_diff"] == 0.0

    def test_diverged_cardinality_raises_loudly(self):
        baseline = _synthetic_baseline()
        control = apply_sizing(baseline, SizingConfig())
        arm = {sid: list(rows) for sid, rows in control.items()}
        arm["S6-K2P0"] = arm["S6-K2P0"][:1]   # simulate a bug that dropped a position
        with pytest.raises(SizingBaselineDivergedError):
            _pareado_trivial(arm, control)


class TestCargarBaseline:
    def test_cargar_baseline_reads_the_three_live_strategies(self):
        baseline = cargar_baseline()
        assert set(baseline) == set(SIDS)
        assert all(len(v) > 0 for v in baseline.values())


class TestTaskTypeRegistradoYManifiestoDeHumo:
    def test_ola1_sizing_registrado_y_manifiesto_de_humo_corre(self, tmp_path):
        from scripts.research.ola1 import tasks_sizing  # noqa: F401 -- registra ola1_sizing
        from scripts.research.runner import tasks
        from scripts.research.runner.manifest import load_manifest
        from scripts.research.runner.runner import run_manifest

        assert "ola1_sizing" in tasks.get_registry()

        manifest_path = tmp_path / "humo_sizing.yaml"
        resultados_dir = tmp_path / "resultados"
        ledger_path = tmp_path / "LEDGER.jsonl"
        manifest_path.write_text(f"""
experimento: OLA2-humo-sizing
area: B
etapa: F0
hipotesis: research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA2.md
substrate_id: t06-baseline-frozen-golden
engine_sha: humo
salidas:
  resultados: {resultados_dir.as_posix()}
  ledger: append
corridas:
  - run_key: HUMO-P13
    tipo: ola1_sizing
    palanca: P-13
    brazo_control: neutral
    brazos:
      neutral: {{}}
      alpha0.25: {{kelly_mult: 0.25}}
    confirmatorios: [alpha0.25]
""", encoding="utf-8")

        load_manifest(manifest_path)
        resultado = run_manifest(manifest_path, ledger_path=ledger_path,
                                  on_error="continue", workers=1)
        assert resultado["failed_run_keys"] == []

        out_dir = resultados_dir / "HUMO-P13"
        assert (out_dir / "metricas.json").exists()
        with (out_dir / "metricas.json").open(encoding="utf-8") as f:
            doc = json.load(f)
        assert doc["brazos"]["alpha0.25"]["pareado"]["tasa_emparejamiento"] == 1.0
        assert "neutral" not in doc["brazos"]["neutral"].get("pareado", {})
        assert ledger_path.exists()
