"""tests/scripts/test_p32_regime.py -- Wave 5, Task P32.

Tests for `scripts/report/gen_p32_regime.py`, the W2-regime specialist that
regime-gates the M15 tie-pool on an ATR14 percentile band characteristic of
window W2. All tests run on SYNTHETIC fixtures (no lake, no research.db).
Covers the brief's required assertions:

(a) the ATR14 percentile band is computed correctly on a synthetic bar fixture;
(b) a trade whose entry-ATR is inside the band is KEPT and one outside is
    DROPPED by the gate;
(c) regime-gated net == sum of only the in-band trades' pnl on a fixture.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.report import gen_p32_regime as p32


# ---------------------------------------------------------------------------
# (a) ATR14 percentile band on a synthetic bar fixture.
# ---------------------------------------------------------------------------
def _synthetic_bars(n: int = 300, step: float = 3.0, base: float = 4000.0) -> pd.DataFrame:
    """n M15 bars, each with a fixed high-low range so Wilder ATR14 converges
    to a known-ish value. Naive (tz-stripped) index, MT5-server convention."""
    idx = pd.date_range("2026-03-02 00:00:00", periods=n, freq="15min")
    price = base + np.arange(n) * step
    rng = 5.0  # constant intrabar range
    df = pd.DataFrame(
        {
            "open": price,
            "high": price + rng / 2,
            "low": price - rng / 2,
            "close": price,
            "volume": 1.0,
        },
        index=idx,
    )
    return df


def test_atr14_series_is_wilder_causal():
    bars = _synthetic_bars(n=200, step=0.0)  # flat price, constant range -> ATR->range
    atr = p32.wilder_atr14(bars)
    # First 13 entries are NaN (min_periods=14); a warmed value must be positive.
    assert atr.iloc[:13].isna().all()
    warm = atr.dropna()
    assert len(warm) > 0
    # With a perfectly constant 5.0 true-range (no gaps), ATR14 converges to 5.0.
    assert abs(warm.iloc[-1] - 5.0) < 1e-6


def test_w2_band_is_p25_p75_of_w2_atr():
    bars = _synthetic_bars(n=300, step=3.0)
    lo, hi, med = p32.w2_regime_band(bars, "2026-03-02", "2026-04-03")
    atr = p32.wilder_atr14(bars)
    w2 = atr.loc["2026-03-02":"2026-04-03"].dropna()
    exp_lo, exp_hi = np.percentile(w2, [25, 75])
    assert abs(lo - exp_lo) < 1e-9
    assert abs(hi - exp_hi) < 1e-9
    assert lo <= med <= hi


# ---------------------------------------------------------------------------
# (b) gate keeps in-band, drops out-of-band.
# ---------------------------------------------------------------------------
def test_gate_keeps_in_band_drops_out_of_band():
    band = (10.0, 20.0)
    # atr_lookup is a plain callable ts->atr for the fixture.
    atrs = {"in": 15.0, "below": 5.0, "above": 25.0, "edge_lo": 10.0, "edge_hi": 20.0}
    look = lambda ts: atrs[ts]  # noqa: E731
    trades = [
        {"ts_in": "in", "pnl": 100.0},
        {"ts_in": "below", "pnl": 999.0},
        {"ts_in": "above", "pnl": 888.0},
        {"ts_in": "edge_lo", "pnl": 1.0},
        {"ts_in": "edge_hi", "pnl": 2.0},
    ]
    kept = p32.gate_in_band(trades, band, look)
    kept_ts = {t["ts_in"] for t in kept}
    assert "in" in kept_ts
    assert "below" not in kept_ts
    assert "above" not in kept_ts
    # Band is inclusive at both edges.
    assert "edge_lo" in kept_ts and "edge_hi" in kept_ts


# ---------------------------------------------------------------------------
# (c) regime-gated net == sum of only in-band trades' pnl.
# ---------------------------------------------------------------------------
def test_gated_net_sums_only_in_band_pnl():
    band = (10.0, 20.0)
    atrs = {"a": 15.0, "b": 5.0, "c": 12.0, "d": 30.0}
    look = lambda ts: atrs[ts]  # noqa: E731
    trades = [
        {"ts_in": "a", "pnl": 100.0},   # in
        {"ts_in": "b", "pnl": 50.0},    # out (below)
        {"ts_in": "c", "pnl": -40.0},   # in
        {"ts_in": "d", "pnl": 200.0},   # out (above)
    ]
    net = p32.gated_net(trades, band, look)
    assert net == 60.0  # 100 + (-40) only


def test_gated_net_nan_atr_is_dropped():
    band = (10.0, 20.0)
    look = lambda ts: float("nan")  # noqa: E731
    trades = [{"ts_in": "x", "pnl": 100.0}]
    # A trade whose entry ATR is undefined cannot be placed in-band -> dropped.
    assert p32.gated_net(trades, band, look) == 0.0
    assert p32.gate_in_band(trades, band, look) == []


# ---------------------------------------------------------------------------
# net-series Sharpe helper.
# ---------------------------------------------------------------------------
def test_sharpe_series():
    assert p32.sharpe([1.0]) is None            # <2 obs
    assert p32.sharpe([2.0, 2.0, 2.0]) is None  # zero variance
    s = p32.sharpe([1.0, 2.0, 3.0])
    assert s is not None and s > 0
