"""tests/analysis/test_realtick_pairing.py -- run_ladder must pair "reverse"
closures (stop-and-reverse, active on live S6/S7 kwargs) into position rows,
exactly like it already does for EXIT*/time_stop. Today it silently drops them
(the `elif motivo.startswith("EXIT") or motivo == "time_stop"` branch does not
match "reverse", so the event falls through with no row, no ficha-discard, no
open_pos.pop -- see task-R1-brief.md).

Step-1 measurement (replayed simular_variant on S6-K2P0/S7-TPNONE, live
kwargs, full 7-month bar set) showed reverse events are emitted ONE PER
FICHA (never one-per-signal): 504 events for S6 across 168 distinct bars
(504 / 3 == 168), all carrying a "ficha" key, none carrying
"same_bar_fallback". That shape is identical to the existing EXIT*/time_stop
events, so these tests exercise the SAME open_pos/last/fallback-sweep
machinery already in run_ladder -- not a new code path.
"""
from __future__ import annotations

from scripts.analysis.realtick_bt import backtest
from scripts.analysis.realtick_bt.backtest import LEVEL_EXITS, run_ladder

BAR_SEC = 900


def _bars(n: int = 5) -> list[dict]:
    return [{"t": 1000 + BAR_SEC * i, "open": 1.0, "high": 1.0, "low": 1.0,
             "close": 1.0, "volume": 1} for i in range(n)]


def _run(monkeypatch, events, bars=None):
    bars = bars if bars is not None else _bars()
    monkeypatch.setattr(backtest, "simular_variant", lambda bars_, **kw: events)
    return run_ladder({}, bars), bars


def test_reverse_not_in_level_exits():
    """resolve() only special-cases LEVEL_EXITS for the intra-bar-crossing fill
    path; "reverse" must stay OUT of that set so a reverse row takes the
    bar-close fill path (backtest.py:280-285) -- the correct semantics for a
    market close at bar close, not a server-side level touch."""
    assert "reverse" not in LEVEL_EXITS


def test_reverse_emits_one_row_per_open_ficha(monkeypatch):
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F1"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F2"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F3"},
    ]
    positions, bars = _run(monkeypatch, events)

    assert len(positions) == 3
    assert {p["ficha"] for p in positions} == {"F1", "F2", "F3"}
    for p in positions:
        assert p["reason"] == "reverse"
        assert p["side_l"] == "L" and p["side"] == "LONG"
        assert p["t_in"] == bars[0]["t"]
        assert p["entry_bid"] == 100.0
        assert p["t_out"] == bars[1]["t"]      # the bar OF THE REVERSE EVENT
        assert p["exit_bid"] == 105.0            # ev["precio"]
        assert p["same_bar"] is False             # no same_bar_fallback key on reverse events


def test_reverse_leaves_no_orphaned_ficha_in_open_pos(monkeypatch):
    """After a full reverse-close, the reverted signal must be gone from
    open_pos. Observed by effect: a late/spurious EXIT-shaped event that would
    only match if the reverted signal's ficha were still sitting in open_pos
    must find nothing and be dropped (not silently paired to the stale,
    already-closed signal)."""
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F1"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F2"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F3"},
        # spurious, no signal open anymore -- must NOT produce a 4th row
        {"idx": 3, "lado": "L", "precio": 999.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
    ]
    positions, _bars = _run(monkeypatch, events)

    assert len(positions) == 3
    assert all(p["reason"] == "reverse" for p in positions)


def test_new_entry_same_bar_as_reverse_pairs_with_its_own_close(monkeypatch):
    """Realistic same-bar shape (emasar_variant.py: the opposite-direction
    entry falls through on the SAME bar as the reverse-close). The new
    signal's own exit must report t_in/entry_bid from the NEW entry, not the
    reverted one."""
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F1"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F2"},
        {"idx": 1, "lado": "L", "precio": 105.0, "motivo": "reverse", "ficha": "F3"},
        {"idx": 1, "lado": "S", "precio": 105.0, "motivo": "ENTRY_S"},   # same bar, opposite side
        {"idx": 2, "lado": "S", "precio": 103.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
    ]
    positions, bars = _run(monkeypatch, events)

    reverse_rows = [p for p in positions if p["reason"] == "reverse"]
    exit_rows = [p for p in positions if p["reason"] == "EXIT_TRAIL"]
    assert len(reverse_rows) == 3
    assert len(exit_rows) == 1
    e = exit_rows[0]
    assert e["side_l"] == "S" and e["side"] == "SHORT"
    assert e["t_in"] == bars[1]["t"]      # paired with the NEW signal (same bar), not the reverted one
    assert e["entry_bid"] == 105.0
    assert e["t_out"] == bars[2]["t"]
    assert e["exit_bid"] == 103.0
