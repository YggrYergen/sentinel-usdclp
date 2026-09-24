"""tests/research/test_metrics.py — TDD for sentinel_engine.research.metrics
(Wave B, B2): pf/wr/payoff/expectancy_r/net_per_day/trades_per_day/
maxdd_pct/sharpe_d/mae_mfe, each vs a hand-computed fixture.
"""
from __future__ import annotations

from sentinel_engine.research import metrics


def test_pf_basic():
    # wins sum=30, losses sum=-20 -> pf = 30/20 = 1.5
    assert metrics.pf([10.0, 20.0], [-10.0, -10.0]) == 1.5


def test_pf_no_losses_is_none():
    assert metrics.pf([10.0], []) is None


def test_pf_no_trades_is_none():
    assert metrics.pf([], []) is None


def test_wr_basic():
    # 2 wins, 3 losses -> wr = 2/5 = 0.4
    assert metrics.wr([10.0, 5.0], [-1.0, -2.0, -3.0]) == 0.4


def test_wr_no_trades_is_none():
    assert metrics.wr([], []) is None


def test_payoff_basic():
    # avg win = (10+20)/2 = 15, avg loss = abs((-10-20)/2) = 15 -> payoff=1.0
    assert metrics.payoff([10.0, 20.0], [-10.0, -20.0]) == 1.0


def test_payoff_no_wins_is_none():
    assert metrics.payoff([], [-5.0]) is None


def test_payoff_no_losses_is_none():
    assert metrics.payoff([5.0], []) is None


def test_expectancy_r_with_sl():
    # trade1: pnl=10, risk_per_unit=abs(100-99)=1, volume=2 -> r=10/(1*2)=5.0
    # trade2: pnl=-4, risk_per_unit=abs(50-52)=2, volume=1 -> r=-4/(2*1)=-2.0
    # mean = (5.0 + -2.0)/2 = 1.5
    trades = [
        {"pnl": 10.0, "px_in": 100.0, "sl": 99.0, "volume": 2.0},
        {"pnl": -4.0, "px_in": 50.0, "sl": 52.0, "volume": 1.0},
    ]
    val, flag = metrics.expectancy_r(trades)
    assert flag == "ok"
    assert val == 1.5


def test_expectancy_r_missing_sl_falls_back_to_ccy():
    trades = [
        {"pnl": 10.0, "px_in": 100.0, "sl": 99.0, "volume": 2.0},
        {"pnl": -4.0, "px_in": 50.0, "sl": None, "volume": 1.0},
    ]
    val, flag = metrics.expectancy_r(trades)
    assert flag == "no_sl_fallback_ccy"
    # fallback = mean raw pnl = (10 + -4) / 2 = 3.0
    assert val == 3.0


def test_expectancy_r_empty_trades():
    val, flag = metrics.expectancy_r([])
    assert val is None
    assert flag == "ok"


def test_net_per_day():
    trades = [
        {"pnl": 10.0, "ts_in": "2026-07-01T00:00:00Z"},
        {"pnl": 20.0, "ts_in": "2026-07-01T05:00:00Z"},
        {"pnl": -6.0, "ts_in": "2026-07-02T00:00:00Z"},
    ]
    # net = 24, days = {07-01, 07-02} = 2 -> 12.0
    assert metrics.net_per_day(trades) == 12.0


def test_net_per_day_empty():
    assert metrics.net_per_day([]) is None


def test_trades_per_day():
    trades = [
        {"ts_in": "2026-07-01T00:00:00Z"},
        {"ts_in": "2026-07-01T05:00:00Z"},
        {"ts_in": "2026-07-02T00:00:00Z"},
    ]
    # 3 trades / 2 days = 1.5
    assert metrics.trades_per_day(trades) == 1.5


def test_trades_per_day_empty():
    assert metrics.trades_per_day([]) is None


def test_maxdd_pct():
    # cum: 100, 50 (peak 100, dd=50), 150 (peak 150), 100 (dd=50)
    trades = [
        {"pnl": 100.0}, {"pnl": -50.0}, {"pnl": 100.0}, {"pnl": -50.0},
    ]
    # base_notional=1000 -> maxdd_pct = 50/1000*100 = 5.0
    assert metrics.maxdd_pct(trades, 1000.0) == 5.0


def test_maxdd_pct_never_drops_is_zero():
    trades = [{"pnl": 10.0}, {"pnl": 20.0}]
    assert metrics.maxdd_pct(trades, 1000.0) == 0.0


def test_maxdd_pct_empty_is_none():
    assert metrics.maxdd_pct([], 1000.0) is None


def test_maxdd_pct_zero_base_notional_is_none():
    assert metrics.maxdd_pct([{"pnl": 10.0}], 0.0) is None


def test_sharpe_d_none_if_fewer_than_10_days():
    trades = [{"pnl": 10.0, "ts_in": f"2026-07-0{i}T00:00:00Z"} for i in range(1, 9)]
    assert metrics.sharpe_d(trades) is None


def test_sharpe_d_computed_with_10_plus_days():
    import math

    daily_pnls = [10.0, -5.0, 8.0, 3.0, -2.0, 6.0, 4.0, -1.0, 7.0, 2.0]
    trades = [
        {"pnl": p, "ts_in": f"2026-07-{i+1:02d}T00:00:00Z"}
        for i, p in enumerate(daily_pnls)
    ]
    mean = sum(daily_pnls) / len(daily_pnls)
    variance = sum((x - mean) ** 2 for x in daily_pnls) / len(daily_pnls)
    std = math.sqrt(variance)
    expected = mean / std * math.sqrt(252)
    result = metrics.sharpe_d(trades)
    assert result is not None
    assert abs(result - expected) < 1e-9


def test_sharpe_d_empty_is_none():
    assert metrics.sharpe_d([]) is None


def test_mae_mfe_long():
    bars = [
        {"t": 0, "h": 105.0, "l": 98.0},
        {"t": 1, "h": 110.0, "l": 100.0},
        {"t": 2, "h": 108.0, "l": 95.0},
    ]
    # entry_px=100, LONG: mae = 100 - min(low)=100-95=5; mfe = max(high)-100=110-100=10
    mae, mfe = metrics.mae_mfe(bars, entry_t=0, exit_t=2, side="LONG", entry_px=100.0)
    assert mae == 5.0
    assert mfe == 10.0


def test_mae_mfe_short():
    bars = [
        {"t": 0, "h": 105.0, "l": 98.0},
        {"t": 1, "h": 110.0, "l": 100.0},
        {"t": 2, "h": 108.0, "l": 95.0},
    ]
    # entry_px=100, SHORT: mae = max(high)-100=110-100=10; mfe = 100-min(low)=100-95=5
    mae, mfe = metrics.mae_mfe(bars, entry_t=0, exit_t=2, side="SHORT", entry_px=100.0)
    assert mae == 10.0
    assert mfe == 5.0


def test_mae_mfe_no_bars_in_window_is_none():
    bars = [{"t": 5, "h": 105.0, "l": 98.0}]
    mae, mfe = metrics.mae_mfe(bars, entry_t=0, exit_t=1, side="LONG", entry_px=100.0)
    assert mae is None
    assert mfe is None
