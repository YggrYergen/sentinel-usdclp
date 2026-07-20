"""tests/report/test_gen_mfe_capture.py -- PX-T4 (PATIENT-EXIT program).

Tests for `scripts/report/gen_mfe_capture.py`: the report-only MFE-capture% +
give-back metrics module. The module runs `simular_variant(live_fill_mode=True)`,
pairs each ficha's entry->exit, and computes -- over the held-bar span, against
the LAKE bars' highs/lows, no look-ahead -- the two per-trade metrics the
PATIENT-EXIT success criterion needs (MFE-capture%, give-back USD).

Coverage (TDD order from the brief):
  1. HAND-COMPUTED metric math for a known LONG and a known SHORT ficha
     (pins MFE / MAE / booked / mfe_capture / give-back exactly).
  2. Determinism: same input -> byte-identical JSON.
  3. Report-only / governance: the compute path takes bars/kwargs and returns
     metrics with no DB handle; the writers only touch the given output path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.report import gen_mfe_capture as mfe

# The pnl scaling the whole league uses (lot 0.10, contract 100 -> $10 / $1 move).
USD_PER_PRICE = mfe.LOT * mfe.CONTRACT_SIZE  # 0.10 * 100.0 == 10.0


# ---------------------------------------------------------------------------
# Synthetic bars with HAND-PICKED highs/lows so MFE/MAE are exact.
# ---------------------------------------------------------------------------
def _bar(t: int, o: float, h: float, l: float, c: float) -> dict:
    return {"t": t, "open": o, "high": h, "low": l, "close": c, "volume": 1.0}


def test_usd_scaling_is_b1():
    """Give-back USD must use the _B1 lot/contract scaling, not a hardcode."""
    assert mfe.LOT == 0.10
    assert mfe.CONTRACT_SIZE == 100.0
    assert USD_PER_PRICE == pytest.approx(10.0)


def test_long_ficha_hand_computed():
    """A LONG ficha held over bars [1..3]. entry (fill-in) = 100.5 (spread at
    fill: long buys at ask = bid 100.0 + 0.5). Span highs/lows (bars 1..3 only,
    no look-ahead onto bar 4):
        bar1 high=101.0 low= 99.5
        bar2 high=108.0 low=100.0   <- max high 108.0
        bar3 high=104.0 low= 96.0   <- min low   96.0
    Exit at bar 3, bid 103.0 -> long sells at BID -> px_out = 103.0.

    booked = px_out - entry            = 103.0 - 100.5 = 2.5
    MFE    = max_high - entry          = 108.0 - 100.5 = 7.5
    MAE    = entry - min_low           = 100.5 -  96.0 = 4.5
    mfe_capture = booked / MFE         = 2.5 / 7.5 = 0.333333...
    giveback_price = max(MFE-booked,0) = 7.5 - 2.5 = 5.0
    giveback_usd   = 5.0 * 10.0        = 50.0
    """
    bars = [
        _bar(0, 100.0, 100.2, 99.8, 100.0),   # pre-entry bar, must NOT count
        _bar(1, 100.0, 101.0, 99.5, 100.5),   # entry bar
        _bar(2, 100.5, 108.0, 100.0, 107.0),  # peak favourable
        _bar(3, 107.0, 104.0, 96.0, 103.0),   # exit bar (adverse dip too)
        _bar(4, 103.0, 200.0, 50.0, 103.0),   # post-exit bar, must NOT count
    ]
    ficha = {
        "side": "L", "ficha": "F1",
        "entry_bar_idx": 1, "exit_bar_idx": 3,
        "entry_price": 100.0,  # BID; module applies spread-at-fill (+0.5 long)
        "exit_price": 103.0,   # BID; long sells at bid, no adj
        "exit_reason": "EXIT_TRAIL",
    }
    m = mfe.ficha_metrics(bars, ficha)
    assert m["entry"] == pytest.approx(100.5)
    assert m["booked"] == pytest.approx(2.5)
    assert m["mfe"] == pytest.approx(7.5)
    assert m["mae"] == pytest.approx(4.5)
    assert m["mfe_capture"] == pytest.approx(2.5 / 7.5)
    assert m["giveback_price"] == pytest.approx(5.0)
    assert m["giveback_usd"] == pytest.approx(50.0)


def test_short_ficha_hand_computed_mirror():
    """A SHORT ficha, mirror of the long. entry (fill-in) = 100.0 (short sells
    at BID, no adj). Span highs/lows over bars [1..2]:
        bar1 high=101.0 low= 99.5
        bar2 high=103.0 low= 90.0   <- min low 90.0, max high 103.0
    Exit at bar 2, bid 96.5 -> short buys back at ASK = 96.5 + 0.5 = 97.0.

    booked = entry - px_out            = 100.0 - 97.0 = 3.0
    MFE    = entry - min_low           = 100.0 - 90.0 = 10.0
    MAE    = max_high - entry          = 103.0 - 100.0 = 3.0
    mfe_capture = booked / MFE         = 3.0 / 10.0 = 0.30
    giveback_price = max(MFE-booked,0) = 10.0 - 3.0 = 7.0
    giveback_usd   = 7.0 * 10.0        = 70.0
    """
    bars = [
        _bar(0, 100.0, 100.2, 99.9, 100.0),
        _bar(1, 100.0, 101.0, 99.5, 100.0),   # entry bar
        _bar(2, 100.0, 103.0, 90.0, 96.5),    # exit bar
        _bar(3, 96.5, 500.0, 10.0, 96.5),     # post-exit, must NOT count
    ]
    ficha = {
        "side": "S", "ficha": "F2",
        "entry_bar_idx": 1, "exit_bar_idx": 2,
        "entry_price": 100.0,  # BID; short sells at bid, no adj
        "exit_price": 96.5,    # BID; short buys back at ask (+0.5)
        "exit_reason": "EXIT_TRAIL",
    }
    m = mfe.ficha_metrics(bars, ficha)
    assert m["entry"] == pytest.approx(100.0)
    assert m["booked"] == pytest.approx(3.0)
    assert m["mfe"] == pytest.approx(10.0)
    assert m["mae"] == pytest.approx(3.0)
    assert m["mfe_capture"] == pytest.approx(0.30)
    assert m["giveback_price"] == pytest.approx(7.0)
    assert m["giveback_usd"] == pytest.approx(70.0)


def test_mfe_zero_is_capture_zero_no_divide():
    """MFE == 0 (trade never went favourable) -> mfe_capture = 0.0, no divide
    by zero. Give-back follows the brief formula max(MFE - booked, 0)."""
    bars = [
        _bar(0, 100.0, 100.0, 100.0, 100.0),
        _bar(1, 100.0, 100.0, 98.0, 99.0),    # long entry, high never exceeds entry
        _bar(2, 99.0, 100.0, 97.0, 98.0),     # exit; high==100 == entry-bid, MFE=100-100.5<0 ->0
    ]
    # exit bid 100.0 -> long sells at bid -> px_out 100.0; entry bid 100.0 -> +0.5
    # -> 100.5. Span highs are both 100.0 -> span_high 100.0 -> MFE = 100.0-100.5
    # = -0.5 -> floored to 0.0 (never went favourable). booked = 100.0-100.5=-0.5.
    ficha = {
        "side": "L", "ficha": "F1",
        "entry_bar_idx": 1, "exit_bar_idx": 2,
        "entry_price": 100.0, "exit_price": 100.0, "exit_reason": "EXIT_INITSL",
    }
    m = mfe.ficha_metrics(bars, ficha)
    assert m["mfe"] == pytest.approx(0.0)
    assert m["mfe_capture"] == pytest.approx(0.0)  # MFE==0 -> no divide, capture 0
    # brief formula verbatim: giveback = max(MFE - booked, 0) = max(0 - (-0.5), 0)
    assert m["giveback_price"] == pytest.approx(0.5)
    assert m["giveback_usd"] == pytest.approx(5.0)


def test_mfe_capture_clamped_to_one():
    """booked > MFE (can't normally happen without spread quirks, but the clamp
    is a hard requirement) -> mfe_capture clamps to 1.0, giveback floors at 0."""
    bars = [
        _bar(0, 100.0, 100.0, 100.0, 100.0),
        _bar(1, 100.0, 101.0, 100.0, 100.0),   # entry
        _bar(2, 100.0, 101.0, 100.0, 105.0),   # exit above the span high
    ]
    # exit bid 105 -> long px_out 105; entry bid 100 -> +0.5 -> 100.5.
    # booked = 105 - 100.5 = 4.5 ; span max high = 101 -> MFE = 101-100.5 = 0.5.
    ficha = {
        "side": "L", "ficha": "F1",
        "entry_bar_idx": 1, "exit_bar_idx": 2,
        "entry_price": 100.0, "exit_price": 105.0, "exit_reason": "EXIT_TP",
    }
    m = mfe.ficha_metrics(bars, ficha)
    assert m["mfe_capture"] == pytest.approx(1.0)   # clamped
    assert m["giveback_price"] == pytest.approx(0.0)  # floored


# ---------------------------------------------------------------------------
# Aggregation over a small engine run (real simular_variant, synthetic bars).
# ---------------------------------------------------------------------------
def _trending_bars(n: int = 300) -> list[dict]:
    """A deterministic gently-trending series (no RNG) that produces a handful
    of fichas under the default engine config."""
    bars: list[dict] = []
    price = 4500.0
    base = 1_700_000_000
    for k in range(n):
        drift = 2.0 if (k // 20) % 2 == 0 else -1.5
        o = price
        price += drift
        c = price
        h = max(o, c) + 0.8
        l = min(o, c) - 0.8
        bars.append(_bar(base + k * 900, o, h, l, c))
    return bars


def test_compute_config_metrics_shape_and_aggregates():
    bars = _trending_bars()
    rep = mfe.compute_config_metrics("TEST-M15", {}, bars, tf="M15")
    assert rep["config_id"] == "TEST-M15"
    assert rep["tf"] == "M15"
    # aggregate keys the PX-T6 report consumes
    for k in ("n_trades", "mean_mfe_capture", "median_mfe_capture",
              "mean_giveback_usd", "total_giveback_usd", "net"):
        assert k in rep
    # every mfe_capture in [0, 1]
    for t in rep["trades"]:
        assert 0.0 <= t["mfe_capture"] <= 1.0
        assert t["giveback_usd"] >= 0.0
    if rep["n_trades"]:
        assert rep["total_giveback_usd"] == pytest.approx(
            sum(t["giveback_usd"] for t in rep["trades"]))


def test_no_trades_is_safe():
    """A window with no signals -> zero trades, no divide-by-zero in aggregates."""
    flat = [_bar(1_700_000_000 + k * 900, 4500.0, 4500.1, 4499.9, 4500.0)
            for k in range(30)]
    rep = mfe.compute_config_metrics("FLAT-M15", {}, flat, tf="M15")
    assert rep["n_trades"] == 0
    assert rep["mean_mfe_capture"] is None
    assert rep["median_mfe_capture"] is None
    assert rep["mean_giveback_usd"] == pytest.approx(0.0)
    assert rep["total_giveback_usd"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Determinism: byte-identical JSON on repeat.
# ---------------------------------------------------------------------------
def test_json_is_byte_identical_on_repeat(tmp_path):
    bars = _trending_bars()
    rep = mfe.compute_config_metrics("DET-M15", {}, bars, tf="M15")
    out1 = tmp_path / "a.json"
    out2 = tmp_path / "b.json"
    mfe.write_json([rep], out1)
    mfe.write_json([rep], out2)
    b1 = out1.read_bytes()
    b2 = out2.read_bytes()
    assert b1 == b2
    # keys are sorted (deterministic order) and it parses
    parsed = json.loads(b1.decode("utf-8"))
    assert parsed["configs"][0]["config_id"] == "DET-M15"


def test_recompute_is_stable():
    """Same bars + kwargs -> identical aggregate numbers across two runs."""
    bars = _trending_bars()
    a = mfe.compute_config_metrics("S-M15", {}, bars, tf="M15")
    b = mfe.compute_config_metrics("S-M15", {}, bars, tf="M15")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ---------------------------------------------------------------------------
# Report-only / governance.
# ---------------------------------------------------------------------------
def test_compute_takes_no_db_handle():
    """The pure compute function's signature accepts bars/kwargs and returns a
    dict -- no DB path/handle among its parameters (report-only stance)."""
    import inspect

    params = set(inspect.signature(mfe.compute_config_metrics).parameters)
    forbidden = {"db", "db_path", "conn", "registry", "connection"}
    assert not (params & forbidden)
    # ficha_metrics likewise
    params2 = set(inspect.signature(mfe.ficha_metrics).parameters)
    assert not (params2 & forbidden)


def test_module_never_imports_registry_or_opens_research_db():
    """Source-level guard: the module must not import sqlite / the registry nor
    call any registry write (report-only isolation, Global Constraint 7).

    The scan strips comments and string literals (docstrings) first so the
    module's own PROSE describing what it does NOT do isn't mistaken for a
    reference -- only real code tokens are checked."""
    import io
    import tokenize

    src = Path(mfe.__file__).read_text(encoding="utf-8")
    code_tokens: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue  # skip docstrings/comments -- prose, not code
        code_tokens.append(tok.string)
    code = " ".join(code_tokens)
    for banned in ("insert_run", "insert_trades", "upsert_strategy", "upsert_variant",
                   "ResearchRegistry", "sqlite3", "registry2"):
        assert banned not in code, f"module code must not reference {banned!r}"


def test_markdown_writer_only_touches_given_path(tmp_path):
    bars = _trending_bars()
    rep = mfe.compute_config_metrics("MD-M15", {}, bars, tf="M15")
    out = tmp_path / "sub" / "report.md"
    mfe.write_markdown([rep], out)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "MD-M15" in text
    assert "mfe_capture" in text.lower() or "mfe-capture" in text.lower()
