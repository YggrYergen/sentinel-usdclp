r"""tests/research/test_ola2.py -- OLA2: P-09 (composite regime gate, harness-level
post-filter on S6 signal entries) wiring inside tasks_ola1.ola1_paired.

`_extraer_regime_de_brazos` mirrors `_expandir_htf_en_brazos` (same "logical overlay
key, popped before the real motor call" pattern): an overlay `_regime` (logical
`regime.RegimeGateConfig` kwargs, minus `enabled`) never reaches `overlay_kwargs`/
`run_ladder`/`run_supertrend` -- it is extracted BEFORE those calls and applied AFTER
`run_ladder` (on the SIGNAL positions, before `resolve()`) via
`backtest.apply_regime_gate_by_entry_bar` (WP-5, harness-level, never touches
`sentinel_engine`).
"""
from __future__ import annotations

import numpy as np

BAR_SEC = 900


def _trend_bars(n: int = 40) -> list[dict]:
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


class TestExtraerRegimeDeBrazos:
    def test_overlay_sin_regime_pasa_intacto_y_cfg_none(self):
        from scripts.research.runner.tasks_ola1 import _extraer_regime_de_brazos

        brazos = {"default": {}, "mhb10": {"max_hold_bars": 10}}
        out, cfg_por_brazo = _extraer_regime_de_brazos(brazos)
        assert out == brazos
        assert cfg_por_brazo == {"default": None, "mhb10": None}

    def test_overlay_con_regime_se_extrae_y_no_llega_al_overlay_real(self):
        from scripts.analysis.realtick_bt.regime import RegimeGateConfig
        from scripts.research.runner.tasks_ola1 import _extraer_regime_de_brazos

        brazos = {
            "gate1": {"max_hold_bars": 5,
                      "_regime": {"adx_min": 20.0, "vr_low": 1.00, "k_of_m": 2}},
        }
        out, cfg_por_brazo = _extraer_regime_de_brazos(brazos)
        assert "_regime" not in out["gate1"]
        assert out["gate1"]["max_hold_bars"] == 5
        cfg = cfg_por_brazo["gate1"]
        assert isinstance(cfg, RegimeGateConfig)
        assert cfg.enabled is True
        assert cfg.adx_min == 20.0
        assert cfg.vr_low == 1.00
        assert cfg.k_of_m == 2


class TestResolverConProgresoAplicaRegimeGate:
    def test_gate_activo_reduce_o_iguala_las_posiciones_de_senal(self, monkeypatch, tmp_path):
        """Con un cfg cuyo adx_min es imposible de satisfacer (None siempre
        cuenta como fallo), el brazo gateado debe perder TODAS las entradas
        de senal frente al mismo brazo sin gate -- prueba que el filtro se
        aplica de verdad, no que se ignora en silencio."""
        from scripts.analysis.realtick_bt import backtest
        from scripts.analysis.realtick_bt.regime import RegimeGateConfig, compute_regime_series
        from scripts.research.runner.tasks_ola1 import _resolver_brazos_con_progreso

        bars = _trend_bars()
        events = [
            {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
            {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
        ]
        monkeypatch.setattr(backtest, "simular_variant", lambda bars_, **kw: events)
        ticks = _FakeTicks([(t0, 99.75, 100.25) for t0 in
                            (b["t"] + BAR_SEC for b in bars)])
        sid = "S6-K2P0"
        arms = {"default": {}, "gated": {}}
        series = compute_regime_series(bars)
        # adx_min=999 is unreachable -> regime_gate() is always False -> the
        # gated arm's signal positions must all be dropped.
        cfg_por_brazo = {"default": None, "gated": RegimeGateConfig(enabled=True, adx_min=999.0)}

        sig, resolved = _resolver_brazos_con_progreso(
            sid, arms, bars, ticks, tmp_path,
            regime_cfg_por_brazo=cfg_por_brazo, regime_series=series,
        )
        assert len(sig["default"]) >= 1
        assert sig["gated"] == []
        assert resolved["gated"] == []

    def test_cfg_none_en_todos_los_brazos_es_byte_identico(self, monkeypatch, tmp_path):
        from scripts.analysis.realtick_bt import backtest
        from scripts.research.runner.tasks_ola1 import _resolver_brazos_con_progreso

        bars = _trend_bars()
        events = [
            {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
            {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
        ]
        monkeypatch.setattr(backtest, "simular_variant", lambda bars_, **kw: events)
        ticks = _FakeTicks([(t0, 99.75, 100.25) for t0 in
                            (b["t"] + BAR_SEC for b in bars)])
        sid = "S6-K2P0"
        arms = {"default": {}}

        sig_plain, resolved_plain = _resolver_brazos_con_progreso(sid, arms, bars, ticks, tmp_path)
        sig_none, resolved_none = _resolver_brazos_con_progreso(
            sid, arms, bars, ticks, tmp_path, regime_cfg_por_brazo=None, regime_series=None,
        )
        assert sig_plain == sig_none
        assert resolved_plain == resolved_none


class TestOla1PairedConRegimeOverlay:
    def test_manifiesto_de_humo_con_regime_corre_y_reduce_n(self, tmp_path):
        """Extremo a extremo por el manifiesto YAML: un brazo con `_regime`
        imposible de satisfacer debe terminar con menos posiciones (n menor
        en metricas.json) que el control, y `pareado.tasa_emparejamiento`
        debe reflejarlo (no asumir 1.0)."""
        from scripts.research.runner import tasks_ola1  # noqa: F401
        from scripts.research.runner.manifest import load_manifest
        from scripts.research.runner.runner import run_manifest

        manifest_path = tmp_path / "humo_regime.yaml"
        resultados_dir = tmp_path / "resultados"
        ledger_path = tmp_path / "LEDGER.jsonl"
        manifest_path.write_text(f"""
experimento: OLA2-humo-regime
area: B
etapa: F0
hipotesis: research/fases/F0-preparacion/01-hipotesis/2026-08-16-preregistro-OLA2.md
substrate_id: capitaria-ticks-2026-preholdout
engine_sha: humo
salidas:
  resultados: {resultados_dir.as_posix()}
  ledger: append
corridas:
  - run_key: HUMO-P09
    tipo: ola1_paired
    palanca: P-09
    sid: S6-K2P0
    clase: "1-B"
    brazo_control: default
    secundaria: none
    brazos:
      default: {{}}
      imposible: {{_regime: {{adx_min: 999.0}}}}
    confirmatorios: [imposible]
""", encoding="utf-8")

        load_manifest(manifest_path)
        resultado = run_manifest(manifest_path, ledger_path=ledger_path,
                                  on_error="continue", workers=1)
        assert resultado["failed_run_keys"] == []

        import json
        with (resultados_dir / "HUMO-P09" / "metricas.json").open(encoding="utf-8") as f:
            doc = json.load(f)
        assert doc["brazos"]["imposible"]["metricas"]["n"] == 0
        assert doc["brazos"]["default"]["metricas"]["n"] > 0
        assert doc["brazos"]["imposible"]["pareado"]["tasa_emparejamiento"] == 0.0
