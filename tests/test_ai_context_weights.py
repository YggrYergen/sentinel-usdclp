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
