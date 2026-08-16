r"""tests/research/test_manifiesto_ola2.py -- BLOCK-B manifest generator shape
and counts, plus a load_manifest() smoke check (registered tipos, no
duplicate run_key) matching what the pre-registration declares.
"""
from __future__ import annotations


class TestConstruirManifiestoOla2:
    def test_forma_y_conteos(self):
        from scripts.research.ola1.manifiesto_ola2 import construir_manifiesto

        data = construir_manifiesto(engine_sha="test-sha")
        por_run = {c["run_key"]: c for c in data["corridas"]}

        assert set(por_run) == {
            "P19-S6", "P19-S7", "P28-S6", "P28-S7", "P21-S6", "P20-ST", "P09-S6",
            "SIZING-P13", "SIZING-P15", "SIZING-P16", "SIZING-P17", "SIZING-P18",
        }

        expected_n_brazos = {
            "P19-S6": 5, "P19-S7": 5, "P28-S6": 5, "P28-S7": 5,
            "P21-S6": 3, "P20-ST": 2, "P09-S6": 13,
            "SIZING-P13": 4, "SIZING-P15": 4, "SIZING-P16": 3,
            "SIZING-P17": 3, "SIZING-P18": 10,
        }
        expected_n_conf = {
            "P19-S6": 4, "P19-S7": 4, "P28-S6": 4, "P28-S7": 4,
            "P21-S6": 2, "P20-ST": 1, "P09-S6": 12,
            "SIZING-P13": 3, "SIZING-P15": 3, "SIZING-P16": 2,
            "SIZING-P17": 2, "SIZING-P18": 9,
        }
        for run_key, corrida in por_run.items():
            assert len(corrida["brazos"]) == expected_n_brazos[run_key], run_key
            assert len(corrida["confirmatorios"]) == expected_n_conf[run_key], run_key
            assert corrida["brazo_control"] in corrida["brazos"]
            assert corrida["brazo_control"] not in corrida["confirmatorios"]

        total_brazos = sum(len(c["brazos"]) for c in data["corridas"])
        total_conf = sum(len(c["confirmatorios"]) for c in data["corridas"])
        assert total_brazos == 62
        assert total_conf == 50

        for run_key in ("P19-S6", "P19-S7", "P28-S6", "P28-S7", "P21-S6", "P20-ST", "P09-S6"):
            assert por_run[run_key]["tipo"] == "ola1_paired"
        for run_key in ("SIZING-P13", "SIZING-P15", "SIZING-P16", "SIZING-P17", "SIZING-P18"):
            assert por_run[run_key]["tipo"] == "ola1_sizing"

    def test_p09_grid_has_twelve_confirmatorios_plus_control_and_fixed_periods_are_not_swept(self):
        from scripts.research.ola1.manifiesto_ola2 import construir_manifiesto

        data = construir_manifiesto(engine_sha="test-sha")
        p09 = next(c for c in data["corridas"] if c["run_key"] == "P09-S6")
        assert p09["brazo_control"] == "control"
        assert p09["brazos"]["control"] == {}
        ks = {arm: spec["_regime"]["k_of_m"] for arm, spec in p09["brazos"].items()
              if arm != "control"}
        assert sorted(ks.values()) == sorted([2] * 6 + [3] * 6)
        # exactly one arm (per k) differs from baseline in each dimension.
        baseline = p09["brazos"]["k2-baseline"]["_regime"]
        assert baseline == {"adx_min": 20.0, "vr_low": 1.00, "er_min": 0.35,
                             "chop_max": 61.8, "k_of_m": 2}

    def test_p16_ladder_has_no_reduction_below_five_percent(self):
        from scripts.research.ola1.manifiesto_ola2 import construir_manifiesto

        data = construir_manifiesto(engine_sha="test-sha")
        p16 = next(c for c in data["corridas"] if c["run_key"] == "SIZING-P16")
        first_band = p16["brazos"]["ladder"]["dd_bands"][0]
        assert first_band == [5.0, 1.0]

    def test_manifiesto_carga_via_load_manifest(self, tmp_path):
        from scripts.research.ola1 import tasks_sizing  # noqa: F401 -- registra ola1_sizing
        from scripts.research.ola1.manifiesto_ola2 import construir_manifiesto, escribir_manifiesto
        from scripts.research.runner import tasks_ola1  # noqa: F401 -- registra ola1_paired
        from scripts.research.runner.manifest import load_manifest

        data = construir_manifiesto(engine_sha="test-sha")
        salida = tmp_path / "ola2.yaml"
        escribir_manifiesto(data, salida)
        loaded = load_manifest(salida)
        assert len(loaded["corridas"]) == 12
