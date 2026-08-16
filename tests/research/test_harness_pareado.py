r"""tests/research/test_harness_pareado.py -- WP-1+2 (harness pareado real-tick
+ parametros hoy hardcodeados). Cubre, un bloque por clase de test:

  B1 - run_supertrend(atr_period, mult) expuestos, defaults byte-identicos.
  B2 - overlay de kwargs por deep-copy sobre _GL[sid], _GL/_GOLIVE_M15 nunca mutados.
  B3 - harness pareado de K brazos + tabla de alineacion de entradas (con un caso
       donde los brazos NO comparten todas las entradas).
  B4 - umbral/lookback de ac_desacelerando, defaults byte-identicos.
  B5 - sl_offset de SuperTrend: coherencia toque/precio, default 0.0 byte-identico.
  B6 - instrumentacion de camino: apagada por defecto, inerte cuando esta encendida.

Bloques se agregan incrementalmente a este fichero segun se completan (TDD:
rojo -> minimo -> verde -> commit por bloque; ver
research/fases/F0-preparacion/02-specs/WP-1-2-progreso.md).

Ver brief: research/fases/F0-preparacion/02-specs/WP-1-2-brief-harness-pareado-y-parametros.md
"""
from __future__ import annotations

import copy

import numpy as np

from scripts.analysis.realtick_bt import backtest
from scripts.analysis.realtick_bt.backtest import run_supertrend
from scripts.analysis.realtick_bt.overlay import overlay_kwargs

BAR_SEC = 900


class _FakeTicks:
    """Minimal stand-in for backtest.Ticks (same shape as
    tests/analysis/test_realtick_pairing.py's _FakeTicks): .first_at(t) and
    .range(t0, t1) on the epoch-seconds axis."""

    def __init__(self, ticks: list[tuple[float, float, float]]) -> None:
        self._t = np.array([t for t, _, _ in ticks], dtype="float64")
        self._bid = np.array([b for _, b, _ in ticks], dtype="float64")
        self._ask = np.array([a for _, _, a in ticks], dtype="float64")

    def first_at(self, t_sec: float):
        i = int(np.searchsorted(self._t, t_sec, "left"))
        if i < len(self._t):
            return float(self._t[i]), float(self._bid[i]), float(self._ask[i])
        return None

    def range(self, t0: float, t1: float):
        lo = int(np.searchsorted(self._t, t0, "left"))
        hi = int(np.searchsorted(self._t, t1, "left"))
        return self._t[lo:hi], self._bid[lo:hi], self._ask[lo:hi]


def _trend_bars(n: int = 40) -> list[dict]:
    """Synthetic bars with enough range/drift to make SuperTrend(14,3.0) flip
    at least once -- an up-leg then a down-leg, deterministic, no ticks needed
    for the flip path itself (EXIT_STFLIP fires on bar-close trend change)."""
    bars = []
    t0 = 1_700_000_000
    price = 100.0
    for i in range(n):
        # up for the first half, down for the second half; small oscillation
        # so highs/lows are never degenerate (division-by-zero-free ATR).
        drift = 0.8 if i < n // 2 else -0.8
        price += drift
        o = price - drift
        c = price
        h = max(o, c) + 0.3
        l = min(o, c) - 0.3
        bars.append({"t": t0 + BAR_SEC * i, "open": o, "high": h, "low": l,
                     "close": c, "volume": 1})
    return bars


# --------------------------------------------------------------------- B1
def test_run_supertrend_defaults_match_explicit_hardcoded_values():
    bars = _trend_bars()
    ticks = _FakeTicks([])   # no intra-bar touches -> exits are pure EXIT_STFLIP
    default_out = run_supertrend(bars, ticks)
    explicit_out = run_supertrend(bars, ticks, atr_period=14, mult=3.0)
    assert default_out == explicit_out
    assert len(default_out) > 0, "fixture must actually exercise at least one exit"


def test_run_supertrend_different_params_change_result():
    """Sanity: atr_period/mult are not silently ignored."""
    bars = _trend_bars()
    ticks = _FakeTicks([])
    default_out = run_supertrend(bars, ticks)
    wide_out = run_supertrend(bars, ticks, atr_period=14, mult=6.0)
    assert default_out != wide_out


# --------------------------------------------------------------------- B2
def test_overlay_kwargs_does_not_mutate_gl():
    sid = "S6-K2P0"
    before = copy.deepcopy(backtest._GL[sid])
    _ = overlay_kwargs(sid, {"max_hold_bars": 5})
    after = backtest._GL[sid]
    assert after == before, "overlay_kwargs must never mutate _GL[sid] in place"


def test_overlay_kwargs_empty_overlay_equals_gl():
    sid = "S7-TPNONE"
    out = overlay_kwargs(sid, {})
    assert out == backtest._GL[sid]
    assert out is not backtest._GL[sid], "must be a deep copy, not the same object"


def test_overlay_kwargs_applies_on_top_of_deepcopy():
    sid = "S6-K2P0"
    out = overlay_kwargs(sid, {"max_hold_bars": 7})
    assert out["max_hold_bars"] == 7
    for k, v in backtest._GL[sid].items():
        if k != "max_hold_bars":
            assert out[k] == v
    assert backtest._GL[sid].get("max_hold_bars") != 7


# --------------------------------------------------------------------- B3
def test_default_arm_reproduces_todays_run_ladder_exactly(monkeypatch):
    """The default arm (empty overlay) run alone must reproduce
    run_ladder(_GL[sid], bars) + resolve() exactly -- the non-regression test
    the brief requires for Bloque 3."""
    from scripts.analysis.realtick_bt.backtest import resolve, run_ladder
    from scripts.analysis.realtick_bt.paired_harness import run_paired_arms

    bars = _trend_bars()
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
    ]
    monkeypatch.setattr(backtest, "simular_variant", lambda bars_, **kw: events)

    ticks = _FakeTicks([(t0, 99.75, 100.25) for t0 in
                        (b["t"] + BAR_SEC for b in bars)])
    sid = "S6-K2P0"
    result = run_paired_arms(sid, {"default": {}}, bars, ticks=ticks)

    bar_times = np.array([b["t"] for b in bars], dtype="float64")
    expected = [r for p in run_ladder(backtest._GL[sid], bars)
                for r in [resolve(p, ticks, bar_times)] if r is not None]
    assert result.arms["default"] == expected


def test_alignment_table_measures_not_assumes_overlap(monkeypatch):
    """Two arms whose exits diverge produce DIFFERENT downstream entries
    (stop_and_reverse-style divergence): the alignment table must report the
    real n_casadas/n_solo_A/n_solo_B at both levels, never assume overlap."""
    from scripts.analysis.realtick_bt.paired_harness import run_paired_arms

    bars = _trend_bars()

    events_a = [   # single entry, no reverse
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
    ]
    events_b = [   # exits earlier AND reverses -> a genuinely different 2nd entry
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 2, "lado": "L", "precio": 102.0, "motivo": "reverse", "ficha": "F1"},
        {"idx": 2, "lado": "L", "precio": 102.0, "motivo": "reverse", "ficha": "F2"},
        {"idx": 2, "lado": "L", "precio": 102.0, "motivo": "reverse", "ficha": "F3"},
        {"idx": 2, "lado": "S", "precio": 102.0, "motivo": "ENTRY_S"},
        {"idx": 6, "lado": "S", "precio": 99.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
        {"idx": 6, "lado": "S", "precio": 99.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
        {"idx": 6, "lado": "S", "precio": 99.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
    ]

    def fake_simular_variant(bars_, **kw):
        return events_a if kw.get("_marker") == "A" else events_b

    monkeypatch.setattr(backtest, "simular_variant", fake_simular_variant)

    ticks = _FakeTicks([(t0, 99.75, 100.25) for t0 in
                        (b["t"] + BAR_SEC for b in bars)])
    sid = "S6-K2P0"
    arms = {"A": {"_marker": "A"}, "B": {"_marker": "B"}}
    result = run_paired_arms(sid, arms, bars, ticks=ticks)

    table_signal = result.alignment_signal[("A", "B")]
    table_filled = result.alignment_filled[("A", "B")]

    # A has ONE entry (LONG @ idx0, 3 fichas); B has TWO entries (LONG @ idx0,
    # SHORT @ idx2 from the reverse) -- they can only casar on the shared
    # LONG@idx0 entries (one per ficha: F1/F2/F3 -> 3 casadas).
    assert table_signal["n_casadas"] == 3
    assert table_signal["n_solo_B"] == 3        # the 3 SHORT@idx2 fichas, B-only
    assert table_signal["n_solo_A"] == 0
    assert len(table_signal["no_casadas"]) == 3

    assert "n_casadas" in table_filled and "n_solo_A" in table_filled and "n_solo_B" in table_filled


def test_entry_identity_supertrend_has_no_ficha_axis():
    from scripts.analysis.realtick_bt.paired_harness import entry_identity

    pos = {"t_in": 1000.0, "side": "LONG"}
    assert entry_identity("SuperTrend-p14x3-M15", pos) == (1000.0, "LONG")


def test_entry_identity_ladder_includes_sid_ficha_t_in_side():
    from scripts.analysis.realtick_bt.paired_harness import entry_identity

    pos = {"t_in": 1000.0, "side": "LONG", "ficha": "F2"}
    assert entry_identity("S6-K2P0", pos) == ("S6-K2P0", "F2", 1000.0, "LONG")


def test_paired_result_rows_are_joinable_by_pos_id(monkeypatch):
    from scripts.analysis.realtick_bt.paired_harness import run_paired_arms

    bars = _trend_bars()
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
    ]
    monkeypatch.setattr(backtest, "simular_variant", lambda bars_, **kw: events)
    ticks = _FakeTicks([(t0, 99.75, 100.25) for t0 in
                        (b["t"] + BAR_SEC for b in bars)])
    result = run_paired_arms("S6-K2P0", {"default": {}}, bars, ticks=ticks)
    rows = result.rows()
    assert len(rows) == 3
    for r in rows:
        assert r["arm"] == "default" and r["sid"] == "S6-K2P0"
        assert r["pos_id"] == f"S6-K2P0|{r['ficha']}|{r['t_in']}|{r['side']}"


# --------------------------------------------------------------------- B4
def test_ac_desacelerando_defaults_match_legacy_behavior():
    from sentinel_engine.strategies.emasar_ref import ac_desacelerando

    ac = [None, 1.0, 0.5, 0.6, 0.4]
    for idx in range(1, len(ac)):
        for direccion in (1, -1):
            if ac[idx] is None or ac[idx - 1] is None:
                legacy = False
            else:
                legacy = (ac[idx] < ac[idx - 1]) if direccion == 1 else (ac[idx] > ac[idx - 1])
            assert ac_desacelerando(ac, idx, direccion) == legacy
            assert (ac_desacelerando(ac, idx, direccion, lookback=1, umbral=0.0)
                    == ac_desacelerando(ac, idx, direccion))


def test_ac_desacelerando_lookback_and_umbral_change_result():
    from sentinel_engine.strategies.emasar_ref import ac_desacelerando

    ac = [1.0, 0.9, 0.85, 0.80, 0.95]
    assert ac_desacelerando(ac, 3, 1) is True          # 0.80 < 0.85 -> decel
    assert ac_desacelerando(ac, 3, 1, umbral=1.0) is False   # tiny drop, big umbral suppresses
    assert ac_desacelerando(ac, 3, 1, lookback=3) is True    # 0.80 vs ac[0]=1.0 -> still decel
    assert ac_desacelerando(ac, 2, 1, lookback=3) is False   # idx < lookback -> guard False


def test_simular_variant_ac_decel_kwargs_default_byte_identical():
    """Threading ac_decel_lookback/ac_decel_umbral through simular_variant
    with defaults must not change emitted events at all -- the parity gate
    enforces this at the whole-engine level; this pins the same invariant
    directly at the kwarg-threading site (ac_modulate=True + f3_ac_decel_exit=
    True so both call sites of ac_desacelerando actually execute)."""
    from sentinel_engine.strategies.emasar_variant import simular_variant
    from scripts.analysis.realtick_bt import backtest as bt

    bars = bt.load_bars()[:400]
    kwargs = {**bt._GL["S6-K2P0"], "ac_modulate": True, "f3_ac_decel_exit": True}
    base = simular_variant(bars, **{**{"symbol": "XAUUSD"}, **kwargs})
    explicit = simular_variant(bars, **{**{"symbol": "XAUUSD"}, **kwargs,
                                         "ac_decel_lookback": 1, "ac_decel_umbral": 0.0})
    assert base == explicit


def test_simular_variant_ac_decel_kwargs_change_result_when_active():
    """Sanity: the new kwargs are actually wired, not silently ignored, when
    the AC-consuming blocks are active."""
    from sentinel_engine.strategies.emasar_variant import simular_variant
    from scripts.analysis.realtick_bt import backtest as bt

    bars = bt.load_bars()[:400]
    kwargs = {**bt._GL["S6-K2P0"], "ac_modulate": True, "f3_ac_decel_exit": True}
    base = simular_variant(bars, **{**{"symbol": "XAUUSD"}, **kwargs})
    tightened = simular_variant(bars, **{**{"symbol": "XAUUSD"}, **kwargs,
                                          "ac_decel_umbral": 1e6})
    assert base != tightened


# --------------------------------------------------------------------- B5
def test_sl_offset_default_zero_byte_identical():
    bars = _trend_bars()
    ticks = _FakeTicks([])
    base = run_supertrend(bars, ticks)
    explicit = run_supertrend(bars, ticks, sl_offset=0.0)
    assert base == explicit


def test_sl_offset_shifts_both_touch_test_and_exit_price_coherently():
    """sl_offset must widen BOTH the touch test and the exit price using the
    SAME shifted level -- if only one were shifted, touch/exit would be
    incoherent (brief SS2, Bloque 5). Proven two ways on the SAME fixture:
    (a) a tick that touches the ORIGINAL line does NOT trigger once widened
        (the touch test itself uses the shifted level, not just the reported
        price); (b) a tick placed exactly at the WIDENED level DOES trigger,
        and its reported exit_bid equals the widened level, not the original."""
    from sentinel_engine.strategies._supertrend_ref import supertrend
    from sentinel_engine.strategies.emasar_ref import _atr_wilder

    bars = _trend_bars()
    highs = [b["high"] for b in bars]; lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    atr = _atr_wilder(highs, lows, closes, 14)
    atrf = [a if a is not None else 0.0 for a in atr]
    trend, line = supertrend(highs, lows, closes, atrf, 3.0)
    fv = next(i for i in range(len(atr)) if atr[i] is not None)

    # find the first bar j > fv where the trend has NOT flipped (so the
    # active stop is the line, and a touch is what would fire EXIT_STLINE).
    j = fv + 1
    side_l = "L" if trend[fv] == 1 else "S"
    while (trend[j] == 1) != (side_l == "L"):
        j += 1
    sl = line[j - 1]
    offset = 0.5
    t0 = bars[j]["t"]
    touch_tick_ts = t0 + 1.0

    # (a) tick exactly at the ORIGINAL line: touches with offset=0, must NOT
    # touch (no EXIT_STLINE at this bar) once widened.
    if side_l == "L":
        ticks_at_original = _FakeTicks([(touch_tick_ts, sl, sl + 0.2)])
    else:
        ticks_at_original = _FakeTicks([(touch_tick_ts, sl - 0.2, sl)])

    base = run_supertrend(bars, ticks_at_original, sl_offset=0.0)
    widened = run_supertrend(bars, ticks_at_original, sl_offset=offset)
    base_this_bar = [p for p in base if p["t_out"] == bars[j]["t"]]
    widened_this_bar = [p for p in widened if p["t_out"] == bars[j]["t"]]
    assert base_this_bar and base_this_bar[0]["reason"] == "EXIT_STLINE"
    assert base_this_bar[0]["exit_bid"] == sl
    assert not (widened_this_bar and widened_this_bar[0]["reason"] == "EXIT_STLINE"), (
        "touch test must use the WIDENED level -- an original-line touch must not "
        "fire EXIT_STLINE once sl_offset widens the stop"
    )

    # (b) tick exactly at the WIDENED level: must touch, and exit_bid must be
    # the widened level (not the original sl).
    sl_widened = (sl - offset) if side_l == "L" else (sl + offset)
    if side_l == "L":
        ticks_at_widened = _FakeTicks([(touch_tick_ts, sl_widened, sl_widened + 0.2)])
    else:
        ticks_at_widened = _FakeTicks([(touch_tick_ts, sl_widened - 0.2, sl_widened)])
    out = run_supertrend(bars, ticks_at_widened, sl_offset=offset)
    this_bar = [p for p in out if p["t_out"] == bars[j]["t"]]
    assert this_bar and this_bar[0]["reason"] == "EXIT_STLINE"
    assert abs(this_bar[0]["exit_bid"] - sl_widened) < 1e-9


# --------------------------------------------------------------------- B6
_INSTRUMENT_KEYS = ("path_mfe_mae", "bars_elapsed", "entry_context",
                    "spread_at_entry", "spread_at_exit_decision")


def _instrument_fixture():
    from scripts.analysis.realtick_bt.backtest import resolve

    bars = _trend_bars()
    pos = {"side_l": "L", "side": "LONG", "ficha": "F1",
           "t_in": bars[0]["t"], "t_out": bars[5]["t"],
           "entry_bid": bars[0]["close"], "exit_bid": bars[5]["close"] - 1.0,
           "reason": "EXIT_TRAIL", "same_bar": False}
    bar_times = np.array([b["t"] for b in bars], dtype="float64")
    entry_tc = bars[0]["t"] + BAR_SEC
    exit_close = bars[5]["t"] + BAR_SEC
    ticks = _FakeTicks([
        (entry_tc, 99.75, 100.25),                          # entry retry tick, spread 0.5
        (bars[5]["t"] + 5.0, pos["exit_bid"], pos["exit_bid"] + 0.5),  # crosses the level
        (exit_close, pos["exit_bid"] - 0.1, pos["exit_bid"] + 0.4),
    ])
    return resolve, pos, ticks, bar_times, bars


def test_instrumentation_off_by_default_no_extra_keys():
    resolve, pos, ticks, bar_times, bars = _instrument_fixture()
    r = resolve(pos, ticks, bar_times)
    assert r is not None
    for k in _INSTRUMENT_KEYS:
        assert k not in r


def test_instrumentation_on_does_not_change_the_decision():
    resolve, pos, ticks, bar_times, bars = _instrument_fixture()
    plain = resolve(pos, ticks, bar_times)
    instrumented = resolve(pos, ticks, bar_times, instrument=True, bars=bars)
    assert plain is not None and instrumented is not None
    stripped = {k: v for k, v in instrumented.items() if k not in _INSTRUMENT_KEYS}
    assert stripped == plain


def test_instrumentation_on_populates_path_data():
    resolve, pos, ticks, bar_times, bars = _instrument_fixture()
    r = resolve(pos, ticks, bar_times, instrument=True, bars=bars)
    assert r is not None
    assert isinstance(r["path_mfe_mae"], list) and len(r["path_mfe_mae"]) > 0
    assert set(r["path_mfe_mae"][0]) == {"t", "mfe", "mae"}
    assert isinstance(r["bars_elapsed"], int) and r["bars_elapsed"] == 5
    assert r["entry_context"] == {"t": bars[0]["t"], "open": bars[0]["open"],
                                  "high": bars[0]["high"], "low": bars[0]["low"],
                                  "close": bars[0]["close"]}
    assert r["spread_at_entry"] == r["spread"]
    assert r["spread_at_exit_decision"] is not None


def test_instrumentation_entry_context_none_without_bars():
    resolve, pos, ticks, bar_times, _bars = _instrument_fixture()
    r = resolve(pos, ticks, bar_times, instrument=True)   # bars omitted
    assert r is not None
    assert r["entry_context"] is None


def test_build_all_instrument_flag_default_off_and_inert_when_on(monkeypatch):
    from scripts.analysis.realtick_bt import backtest as bt

    bars = _trend_bars()
    events = [
        {"idx": 0, "lado": "L", "precio": 100.0, "motivo": "ENTRY_L"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F1"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F2"},
        {"idx": 5, "lado": "L", "precio": 105.0, "motivo": "EXIT_TRAIL", "ficha": "F3"},
    ]
    monkeypatch.setattr(bt, "simular_variant", lambda bars_, **kw: events)
    ticks = _FakeTicks([(t0, 99.75, 100.25) for t0 in
                        (b["t"] + BAR_SEC for b in bars)])

    off = bt.build_all(ticks, bars)
    on = bt.build_all(ticks, bars, instrument=True)
    for sid in off:
        assert len(off[sid]) == len(on[sid])
        for p_off, p_on in zip(off[sid], on[sid]):
            for k in _INSTRUMENT_KEYS:
                assert k not in p_off
            stripped_on = {k: v for k, v in p_on.items() if k not in _INSTRUMENT_KEYS}
            assert stripped_on == p_off
