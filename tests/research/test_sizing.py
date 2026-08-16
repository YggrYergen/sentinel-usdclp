r"""tests/research/test_sizing.py -- WP-4 (hook de tamano de posicion + estado
de cuenta agregado). Cubre: off-by-default byte-identical (spec acceptance:
"con multiplicador fijo en 1.0, resultado byte-identico al de hoy"), cada
factor del multiplicador por separado, y que la reconstruccion del estado de
cuenta es determinista e independiente del orden de iteracion.

Ver: research/fases/F0-preparacion/02-specs/2026-08-15-spec-instrumentacion-motor-un-viaje.md (WP-4)
     research/fases/F0-preparacion/02-specs/WP-345-progreso.md
"""
from __future__ import annotations

import copy

from scripts.analysis.realtick_bt import backtest
from scripts.analysis.realtick_bt.sizing import (
    AccountState,
    SizingConfig,
    apply_sizing,
    kelly_factor,
    lot_fn,
    rolling_sharpe,
)

DAY = 86400
BAR_SEC = 900


def _pos(sid: str, ficha: str, t_in: float, t_out: float, net1: float,
         margin1: float = 1000.0, side: str = "LONG") -> dict:
    return {
        "side_l": "L" if side == "LONG" else "S", "side": side, "ficha": ficha,
        "reason": "EXIT_TP", "t_in": t_in, "t_out": t_out, "entry_bid": 100.0,
        "exit_bid": 101.0, "same_bar": False, "spread": 0.5, "band": 0.5,
        "entry_fill": 100.0, "exit_fill": 101.0, "t_in_exec": t_in,
        "entry_delay_bars": 0, "t_exit": t_out, "net1": net1, "margin1": margin1,
        "level_slip": False, "_sid_tag": sid,
    }


# --------------------------------------------------------------------- off by default
def test_apply_sizing_with_cfg_none_returns_the_same_object_unchanged():
    resolved = {"S6-K2P0": [_pos("S6-K2P0", "F1", 0, BAR_SEC, 50.0)]}
    out = apply_sizing(resolved, None)
    assert out is resolved
    assert "lot_mult" not in out["S6-K2P0"][0]


def test_apply_sizing_neutral_config_adds_only_lot_mult_equal_to_one():
    resolved = {
        "S6-K2P0": [_pos("S6-K2P0", "F1", 0, BAR_SEC, 50.0),
                    _pos("S6-K2P0", "F2", BAR_SEC, 2 * BAR_SEC, -30.0)],
        "SuperTrend-p14x3-M15": [_pos("SuperTrend-p14x3-M15", "F1", 3 * BAR_SEC, 4 * BAR_SEC, 20.0)],
    }
    original = copy.deepcopy(resolved)
    out = apply_sizing(resolved, SizingConfig())
    for sid, rows in out.items():
        for i, r in enumerate(rows):
            assert r["lot_mult"] == 1.0
            core = {k: v for k, v in r.items() if k != "lot_mult"}
            assert core == original[sid][i]  # every existing key/value untouched
    # order preserved per strategy
    assert [r["t_in_exec"] for r in out["S6-K2P0"]] == [0, BAR_SEC]


def test_backtest_metrics_and_peak_margin_default_lot_fn_none_byte_identical():
    rows = [_pos("S6-K2P0", "F1", 0, BAR_SEC, 50.0, margin1=1000.0),
            _pos("S6-K2P0", "F2", BAR_SEC, 2 * BAR_SEC, -30.0, margin1=1000.0)]
    m0 = backtest.metrics(rows, 0.67)
    m1 = backtest.metrics(rows, 0.67, lot_fn=None)
    assert m0 == m1
    pm0 = backtest.peak_margin(rows, 0.67)
    pm1 = backtest.peak_margin(rows, 0.67, lot_fn=None)
    assert pm0 == pm1


def test_neutral_sizing_through_metrics_reproduces_global_lot_result():
    """Full round-trip: apply_sizing(SizingConfig()) -> lot_mult=1.0 everywhere
    -> sizing.lot_fn(lot) fed into backtest.metrics()/peak_margin() must give
    EXACTLY the same numbers as calling them with the plain global `lot`."""
    resolved = {
        "S6-K2P0": [_pos("S6-K2P0", "F1", 0, BAR_SEC, 50.0),
                    _pos("S6-K2P0", "F2", BAR_SEC, 2 * BAR_SEC, -30.0)],
        "S7-TPNONE": [_pos("S7-TPNONE", "F1", 5 * BAR_SEC, 6 * BAR_SEC, 12.5)],
    }
    lot = 0.67
    sized = apply_sizing(resolved, SizingConfig())
    for sid in resolved:
        rows_plain = resolved[sid]
        rows_sized = sized[sid]
        assert backtest.metrics(rows_plain, lot) == backtest.metrics(rows_sized, lot, lot_fn=lot_fn(lot))
        assert backtest.peak_margin(rows_plain, lot) == backtest.peak_margin(rows_sized, lot, lot_fn=lot_fn(lot))


# --------------------------------------------------------------------- rolling_sharpe
def test_rolling_sharpe_none_below_two_samples_or_zero_variance():
    assert rolling_sharpe([]) is None
    assert rolling_sharpe([10.0]) is None
    assert rolling_sharpe([5.0, 5.0, 5.0]) is None  # zero variance


def test_rolling_sharpe_matches_hand_computed_value():
    returns = [10.0, -5.0, 8.0, -2.0]
    mean = sum(returns) / 4
    var = sum((r - mean) ** 2 for r in returns) / 3
    expected = mean / (var ** 0.5)
    assert abs(rolling_sharpe(returns) - expected) < 1e-9


# --------------------------------------------------------------------- kelly
def test_kelly_factor_zero_edge_coinflip_even_payoff_is_zero():
    cfg = SizingConfig(kelly_mult=0.5, kelly_payoff_default=1.0)
    state = AccountState()  # no history -> assumed win_rate=0.5, payoff=default 1.0
    f = kelly_factor(state, "S6-K2P0", cfg)
    assert abs(f - 0.0) < 1e-12


def test_kelly_factor_positive_edge_from_history():
    cfg = SizingConfig(kelly_mult=0.5, kelly_clip=(0.0, 1.0))
    state = AccountState(trade_returns={"S6-K2P0": [10.0, 10.0, -5.0]})  # wr=2/3, payoff=10/5=2
    # f* = 2/3 - (1/3)/2 = 0.6667 - 0.1667 = 0.5
    f = kelly_factor(state, "S6-K2P0", cfg)
    assert abs(f - (0.5 * 0.5)) < 1e-9


# --------------------------------------------------------------------- drawdown bands / ficha / sharpe floor / loss streak
def test_apply_sizing_dd_band_kicks_in_after_a_drawdown():
    cfg = SizingConfig(dd_bands=[(5.0, 1.0), (100.0, 0.5)])
    resolved = {
        "S6-K2P0": [
            _pos("S6-K2P0", "F1", 0, BAR_SEC, 100.0),                 # equity 100, peak 100, dd 0%
            _pos("S6-K2P0", "F2", BAR_SEC, 2 * BAR_SEC, -20.0),       # BEFORE this trade: dd 0% -> band 1.0
            _pos("S6-K2P0", "F3", 2 * BAR_SEC, 3 * BAR_SEC, -5.0),    # BEFORE: equity 80, peak 100, dd 20% -> band 0.5
        ],
    }
    out = apply_sizing(resolved, cfg)
    rows = out["S6-K2P0"]
    assert rows[0]["lot_mult"] == 1.0
    assert rows[1]["lot_mult"] == 1.0   # dd was 0% when this one was sized
    assert rows[2]["lot_mult"] == 0.5   # dd was 20% when this one was sized


def test_apply_sizing_dd_continuous_linear_ramp_floored():
    # OLA2 (P-16 continuous alternative): factor = max(floor, 1 - dd_pct/ref).
    cfg = SizingConfig(dd_continuous=(20.0, 0.25))
    resolved = {
        "S6-K2P0": [
            _pos("S6-K2P0", "F1", 0, BAR_SEC, 100.0),                  # dd 0% before -> factor 1.0
            _pos("S6-K2P0", "F2", BAR_SEC, 2 * BAR_SEC, -20.0),        # dd 0% before -> factor 1.0
            _pos("S6-K2P0", "F3", 2 * BAR_SEC, 3 * BAR_SEC, -80.0),    # dd 20% before -> ref hit -> floor 0.25
        ],
    }
    out = apply_sizing(resolved, cfg)["S6-K2P0"]
    assert out[0]["lot_mult"] == 1.0
    assert out[1]["lot_mult"] == 1.0
    assert out[2]["lot_mult"] == 0.25   # dd_pct=20 -> 1-20/20=0 -> floored at 0.25


def test_apply_sizing_dd_bands_takes_precedence_over_dd_continuous_when_both_set():
    cfg = SizingConfig(dd_bands=[(5.0, 0.9)], dd_continuous=(20.0, 0.25))
    resolved = {"S6-K2P0": [_pos("S6-K2P0", "F1", 0, BAR_SEC, 100.0)]}
    out = apply_sizing(resolved, cfg)["S6-K2P0"]
    assert out[0]["lot_mult"] == 0.9   # dd_bands wins, dd_continuous never evaluated


def test_apply_sizing_ficha_factors_applied_per_position():
    cfg = SizingConfig(ficha_factors={"F1": 1.0, "F2": 0.5, "F3": 0.25})
    resolved = {"S6-K2P0": [
        _pos("S6-K2P0", "F1", 0, BAR_SEC, 10.0),
        _pos("S6-K2P0", "F2", 0, BAR_SEC, 10.0),
        _pos("S6-K2P0", "F3", 0, BAR_SEC, 10.0),
    ]}
    out = apply_sizing(resolved, cfg)["S6-K2P0"]
    assert [r["lot_mult"] for r in out] == [1.0, 0.5, 0.25]


def test_apply_sizing_sharpe_floor_reduces_size_once_breached():
    cfg = SizingConfig(sharpe_floor=0.0, sharpe_floor_factor=0.3, sharpe_window=50)
    resolved = {"S6-K2P0": [
        _pos("S6-K2P0", "F1", 0 * BAR_SEC, 1 * BAR_SEC, -10.0),
        _pos("S6-K2P0", "F1", 1 * BAR_SEC, 2 * BAR_SEC, -5.0),
        _pos("S6-K2P0", "F1", 2 * BAR_SEC, 3 * BAR_SEC, -10.0),  # sharpe of [-10,-5] before this trade < 0
    ]}
    out = apply_sizing(resolved, cfg)["S6-K2P0"]
    assert out[0]["lot_mult"] == 1.0   # no history yet
    assert out[2]["lot_mult"] == 0.3   # negative rolling sharpe from the first two losses


def test_apply_sizing_loss_streak_cutoff_resets_on_new_server_day():
    cfg = SizingConfig(loss_streak_cutoff=2, loss_streak_factor=0.0)
    day1 = 10 * DAY
    day2 = 11 * DAY
    resolved = {"S6-K2P0": [
        _pos("S6-K2P0", "F1", day1, day1 + BAR_SEC, -10.0),
        _pos("S6-K2P0", "F1", day1 + BAR_SEC, day1 + 2 * BAR_SEC, -10.0),
        _pos("S6-K2P0", "F1", day1 + 2 * BAR_SEC, day1 + 3 * BAR_SEC, -10.0),  # 2 losses today already -> cutoff
        _pos("S6-K2P0", "F1", day2, day2 + BAR_SEC, -10.0),                    # new day -> counter reset
    ]}
    out = apply_sizing(resolved, cfg)["S6-K2P0"]
    assert out[0]["lot_mult"] == 1.0
    assert out[1]["lot_mult"] == 1.0
    assert out[2]["lot_mult"] == 0.0   # streak cutoff hit
    assert out[3]["lot_mult"] == 1.0   # new day, streak reset


def test_apply_sizing_correlation_discount_when_strategies_overlap():
    cfg = SizingConfig(correlation_discount_per_extra=1.0)  # factor = 1/(1+1*n_extra)
    resolved = {
        "S6-K2P0": [_pos("S6-K2P0", "F1", 0, 4 * BAR_SEC, 10.0)],
        "S7-TPNONE": [_pos("S7-TPNONE", "F1", BAR_SEC, 2 * BAR_SEC, 10.0)],  # opens WHILE S6's is open
    }
    out = apply_sizing(resolved, cfg)
    # S6 opens alone (n_concurrent=1 -> factor 1.0); S7 opens while S6 still open (n_concurrent=2 -> factor 0.5)
    assert out["S6-K2P0"][0]["lot_mult"] == 1.0
    assert abs(out["S7-TPNONE"][0]["lot_mult"] - 0.5) < 1e-12


def test_apply_sizing_clip_bounds_the_final_multiplier():
    cfg = SizingConfig(ficha_factors={"F1": 10.0}, clip=(0.0, 2.0))
    resolved = {"S6-K2P0": [_pos("S6-K2P0", "F1", 0, BAR_SEC, 10.0)]}
    out = apply_sizing(resolved, cfg)["S6-K2P0"]
    assert out[0]["lot_mult"] == 2.0


# --------------------------------------------------------------------- determinism / order independence
def test_apply_sizing_is_independent_of_dict_iteration_order():
    rows_s6 = [_pos("S6-K2P0", "F1", 0, BAR_SEC, 40.0),
               _pos("S6-K2P0", "F2", 3 * BAR_SEC, 4 * BAR_SEC, -15.0)]
    rows_s7 = [_pos("S7-TPNONE", "F1", 1 * BAR_SEC, 2 * BAR_SEC, -20.0),
               _pos("S7-TPNONE", "F1", 5 * BAR_SEC, 6 * BAR_SEC, 30.0)]
    cfg = SizingConfig(dd_bands=[(5.0, 1.0), (100.0, 0.6)], sharpe_floor=0.0, sharpe_floor_factor=0.4)

    resolved_a = {"S6-K2P0": copy.deepcopy(rows_s6), "S7-TPNONE": copy.deepcopy(rows_s7)}
    resolved_b = {"S7-TPNONE": copy.deepcopy(rows_s7), "S6-K2P0": copy.deepcopy(rows_s6)}

    out_a = apply_sizing(resolved_a, cfg)
    out_b = apply_sizing(resolved_b, cfg)

    for sid in ("S6-K2P0", "S7-TPNONE"):
        mults_a = [(r["t_in_exec"], r["lot_mult"]) for r in out_a[sid]]
        mults_b = [(r["t_in_exec"], r["lot_mult"]) for r in out_b[sid]]
        assert mults_a == mults_b
