"""tests/analysis/test_realtick_sl_attribution.py -- split the GENUINE initial
SL from an ALREADY-RAISED stop inside run_ladder's exit attribution.

Background (task-R2bis-brief.md, hallazgo H3 measured by task-R2-report.md):
`emasar_variant.py` tags a closed ficha `EXIT_INITSL` purely by WHICH CHECK
fired this bar (the initial-range-SL check, `emasar_variant.py:784-793`), not
by whether that stop is still the untouched entry-bar level. Once trailing or
breakeven-at-R has raised `f.sl` in an earlier bar, a later stop-out still
reads `EXIT_INITSL` even though the level is not the original one. Measured:
98.7% of S6-K2P0's and 99.7% of S7-TPNONE's resolved `EXIT_INITSL` rows are
this "already-raised" case, and 100% of the profitable `EXIT_INITSL` rows
live in that mislabeled group (0% of the truly-genuine ones are profitable,
as expected for an intact stop-loss).

This test file covers `run_ladder`'s new split: a `motivo == "EXIT_INITSL"`
event is re-classified as `reason == "EXIT_SL_RAISED"` when the level in the
event does not match the genuine initial-SL formula recomputed from the
signal's OWN entry bar. All other motivos (`EXIT_TRAIL`, `reverse`,
`time_stop`, ...) must pass through with their `reason` unchanged -- this
file does not touch, and must not need to touch, that machinery (already
covered by tests/analysis/test_realtick_pairing.py, R1).

Same monkeypatch-`simular_variant` + synthetic-bars pattern as
tests/analysis/test_realtick_pairing.py (read as reference, not modified).
"""
from __future__ import annotations

from scripts.analysis.realtick_bt import backtest
from scripts.analysis.realtick_bt.backtest import run_ladder

BAR_SEC = 900


def _bars(n: int = 4) -> list[dict]:
    """Bars with a fixed 10-unit range (high=110, low=100) on every index, so
    the genuine-initial-SL formula gives the same number regardless of which
    bar index is used as the "entry bar" in a given scenario."""
    return [{"t": 1000 + BAR_SEC * i, "open": 105.0, "high": 110.0, "low": 100.0,
             "close": 105.0, "volume": 1} for i in range(n)]


def _run(monkeypatch, events, kwargs, bars=None):
    bars = bars if bars is not None else _bars()
    monkeypatch.setattr(backtest, "simular_variant", lambda bars_, **kw: events)
    return run_ladder(kwargs, bars), bars


# genuine initial SL for a LONG entered at bar 0 (high=110, low=100, rango=10)
# with k=2.5:  low - k*rango = 100 - 2.5*10 = 75.0
# with k=1.0:  low - k*rango = 100 - 1.0*10 = 90.0


def test_a_matching_level_stays_exit_initsl(monkeypatch):
    """(a) EXIT_INITSL whose event level COINCIDES with the genuine
    entry-bar stop (k=2.5 -> 75.0) keeps reason == 'EXIT_INITSL'."""
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 1, "lado": "L", "precio": 75.0, "motivo": "EXIT_INITSL", "ficha": "F1"},
    ]
    positions, _bars = _run(monkeypatch, events, {"init_sl_range_k": 2.5})
    assert len(positions) == 1
    assert positions[0]["reason"] == "EXIT_INITSL"


def test_b_nonmatching_level_becomes_exit_sl_raised(monkeypatch):
    """(b) EXIT_INITSL whose event level does NOT coincide with the genuine
    entry-bar stop (level 90.0 vs. genuine 75.0 at k=2.5) is reclassified to
    reason == 'EXIT_SL_RAISED' -- this is the already-levantado case."""
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 1, "lado": "L", "precio": 90.0, "motivo": "EXIT_INITSL", "ficha": "F1"},
    ]
    positions, _bars = _run(monkeypatch, events, {"init_sl_range_k": 2.5})
    assert len(positions) == 1
    assert positions[0]["reason"] == "EXIT_SL_RAISED"


def test_b2_short_side_nonmatching_level_becomes_exit_sl_raised(monkeypatch):
    """Same as (b) but on the SHORT side, to exercise the sign-flipped half
    of the genuine formula (high + k*rango for lado=='S'). Genuine short stop
    at k=2.5 is 110 + 2.5*10 = 135.0; event reports 120.0 (already raised
    down toward entry) -> must reclassify."""
    events = [
        {"idx": 0, "lado": "S", "precio": 100.0, "motivo": "ENTRY_S"},
        {"idx": 1, "lado": "S", "precio": 120.0, "motivo": "EXIT_INITSL", "ficha": "F1"},
    ]
    positions, _bars = _run(monkeypatch, events, {"init_sl_range_k": 2.5})
    assert len(positions) == 1
    assert positions[0]["reason"] == "EXIT_SL_RAISED"


def test_c_other_motivos_keep_reason_unchanged(monkeypatch):
    """(c) EXIT_TRAIL / reverse / time_stop are untouched by this task: their
    `reason` must come out EXACTLY as the motivo emitted by the engine, even
    when their level does not match the genuine-initial-SL formula (proving
    the reclassification logic is scoped strictly to EXIT_INITSL)."""
    for motivo in ("EXIT_TRAIL", "reverse", "time_stop"):
        events = [
            {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
            {"idx": 1, "lado": "L", "precio": 999.0, "motivo": motivo, "ficha": "F1"},
        ]
        positions, _bars = _run(monkeypatch, events, {"init_sl_range_k": 2.5})
        assert len(positions) == 1
        assert positions[0]["reason"] == motivo, f"motivo {motivo} was reclassified"


def test_d_k_comes_from_kwargs_not_hardcoded(monkeypatch):
    """(d) The SAME feed (event level 90.0) classifies DIFFERENTLY depending
    on which `init_sl_range_k` is passed in kwargs -- proving k is read live
    from kwargs and is not a hardcoded constant in backtest.py.

    k=2.5 -> genuine stop is 75.0; 90.0 != 75.0 -> EXIT_SL_RAISED.
    k=1.0 -> genuine stop is 90.0; 90.0 == 90.0 -> EXIT_INITSL (genuine).
    """
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 1, "lado": "L", "precio": 90.0, "motivo": "EXIT_INITSL", "ficha": "F1"},
    ]
    positions_k25, _ = _run(monkeypatch, events, {"init_sl_range_k": 2.5})
    positions_k10, _ = _run(monkeypatch, events, {"init_sl_range_k": 1.0})
    assert positions_k25[0]["reason"] == "EXIT_SL_RAISED"
    assert positions_k10[0]["reason"] == "EXIT_INITSL"


def test_default_k_matches_simular_variant_default_when_key_absent(monkeypatch):
    """If kwargs carries no `init_sl_range_k` key at all, run_ladder must fall
    back to the SAME default simular_variant itself uses (1.0), not some
    other hardcoded value -- so an empty kwargs dict (as used by
    tests/analysis/test_realtick_pairing.py's `_run` helper) classifies
    exactly like an explicit k=1.0."""
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 1, "lado": "L", "precio": 90.0, "motivo": "EXIT_INITSL", "ficha": "F1"},
    ]
    positions, _bars = _run(monkeypatch, events, {})
    assert positions[0]["reason"] == "EXIT_INITSL"
