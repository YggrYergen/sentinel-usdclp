"""
Regression test for Defect 3 (SENTINEL revamp, Task 0.5).

sentinel/ai_chat.py::build_market_context hardcoded STALE scoring weights
into the AI system prompt: composite "Tech x0.75 + Corr x0.25" (actual is
50/50 per sentinel.config.WEIGHTS) and TF weights "M1=40%, M2=30%, M5=20%,
M15=10%" (actual is M1=35, M2=35, M5=20, M15=10 per the tf_w dict in
sentinel/technical_scorer.py).

This test asserts the emitted context reflects the CURRENT weights, and
proves the values are SOURCED (not literals) by monkeypatching the
authoritative constants and checking the rendered text changes accordingly.
"""
from __future__ import annotations

from sentinel.ai_chat import build_market_context
from sentinel import config
from sentinel import technical_scorer


def _minimal_result():
    return {
        "components": {
            "technical": {"score": 0, "direction": "NEUTRAL", "details": {"tf_scores": {}}},
            "correlation": {"score": 0, "direction": "NEUTRAL", "details": {"correlations": {}}},
        },
        "composite_score": 0,
        "direction": "NEUTRAL",
        "signal": "",
        "levels": {},
        "alerts": [],
        "divergences": [],
    }


def _minimal_price_info():
    return {"bid": 0, "ask": 0, "spread": 0}


def test_context_reflects_current_composite_and_tf_weights():
    ctx = build_market_context(_minimal_result(), _minimal_price_info())

    assert "Tech" in ctx and "0.50" in ctx and "0.50" in ctx
    assert "[peso: 50%]" in ctx
    assert ctx.count("[peso: 50%]") == 2
    assert "M1=35%, M2=35%, M5=20%, M15=10%" in ctx


def test_context_composite_weights_are_sourced_not_literal(monkeypatch):
    monkeypatch.setattr(config.WEIGHTS, "technical", 0.6)
    monkeypatch.setattr(config.WEIGHTS, "correlation", 0.4)

    ctx = build_market_context(_minimal_result(), _minimal_price_info())

    assert "0.60" in ctx
    assert "0.40" in ctx
    assert "[peso: 60%]" in ctx
    assert "[peso: 40%]" in ctx
    assert "[peso: 75%]" not in ctx
    assert "[peso: 25%]" not in ctx


def test_context_tf_weights_are_sourced_not_literal(monkeypatch):
    monkeypatch.setattr(
        technical_scorer, "TF_WEIGHTS",
        {"M1": 0.5, "M2": 0.3, "M5": 0.15, "M15": 0.05},
    )

    ctx = build_market_context(_minimal_result(), _minimal_price_info())

    assert "M1=50%, M2=30%, M5=15%, M15=5%" in ctx
    assert "M1=40%, M2=30%, M5=20%, M15=10%" not in ctx


# ── Engine single-producer path: render_ai_context(snapshot, cfg) ──
# Same anti-literal guarantee as build_market_context, but sourced from the
# per-instrument InstrumentConfig (composite weights via the snapshot's
# config-set component weights, TF weights via cfg.technical.tf_weights).
import dataclasses

from sentinel_engine.ai_context import render_ai_context
from sentinel_engine.config import load_instrument
from sentinel_engine.engine import Engine
from tests.golden.capture_engine import ENGINE_WARMUP_TICKS
from tests.golden.fake_feed import FakeFeed


def _engine_snapshot(cfg):
    engine = Engine(cfg, FakeFeed())
    for _ in range(ENGINE_WARMUP_TICKS):
        engine._macro.update_tick(engine.feed)
    return engine.step()


def test_render_ai_context_weights_are_sourced_from_config():
    cfg = load_instrument("usdclp")
    snap = _engine_snapshot(cfg)

    ctx = render_ai_context(snap, cfg)

    # usdclp config: technical=0.50/correlation=0.50, tf M1=35 M2=35 M5=20 M15=10
    w_tech = cfg.composite.weights["technical"]
    w_corr = cfg.composite.weights["correlation"]
    assert f"Tech×{w_tech:.2f} + Corr×{w_corr:.2f}" in ctx
    assert f"[peso: {w_tech*100:.0f}%]" in ctx
    assert f"[peso: {w_corr*100:.0f}%]" in ctx
    tf = cfg.technical.tf_weights
    assert (f"M1={tf['M1']*100:.0f}%, M2={tf['M2']*100:.0f}%, "
            f"M5={tf['M5']*100:.0f}%, M15={tf['M15']*100:.0f}%") in ctx


def test_render_ai_context_composite_weights_not_literal():
    cfg = load_instrument("usdclp")
    snap = _engine_snapshot(cfg)

    # Mutate the config-derived composite weights carried by the snapshot;
    # the rendered text must follow (proving no hardcoded 50/50 literal).
    comps = dict(snap.components)
    comps["technical"] = {**comps["technical"], "weight": 0.6}
    comps["correlation"] = {**comps["correlation"], "weight": 0.4}
    snap = dataclasses.replace(snap, components=comps)

    ctx = render_ai_context(snap, cfg)

    assert "Tech×0.60 + Corr×0.40" in ctx
    assert "[peso: 60%]" in ctx
    assert "[peso: 40%]" in ctx
    assert "[peso: 50%]" not in ctx


def test_render_ai_context_tf_weights_not_literal():
    cfg = load_instrument("usdclp")
    snap = _engine_snapshot(cfg)

    # Swap tf_weights on a config copy → rendered TF header must change.
    new_tech = dataclasses.replace(
        cfg.technical, tf_weights={"M1": 0.5, "M2": 0.3, "M5": 0.15, "M15": 0.05}
    )
    cfg2 = dataclasses.replace(cfg, technical=new_tech)

    ctx = render_ai_context(snap, cfg2)

    assert "M1=50%, M2=30%, M5=15%, M15=5%" in ctx
    assert "M1=35%, M2=35%, M5=20%, M15=10%" not in ctx


def test_render_ai_context_is_deterministic():
    cfg = load_instrument("usdclp")
    outs = {render_ai_context(_engine_snapshot(cfg), cfg) for _ in range(3)}
    assert len(outs) == 1
    ctx = next(iter(outs))
    assert "now(" not in ctx.lower()
