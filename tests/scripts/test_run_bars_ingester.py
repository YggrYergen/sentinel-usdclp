"""tests/scripts/test_run_bars_ingester.py -- offline tests for the durable
incremental bars ingester daemon (`scripts/live/run_bars_ingester.py`).

Hermetic: `tmp_path` lake roots + an injected FAKE mt5 stub. NEVER imports or
connects real MetaTrader5, NEVER touches the real `data/lake`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.live import run_bars_ingester as ing
from sentinel_engine.lake import store


# --------------------------------------------------------------------------
# Fake MT5: exposes copy_rates_from_pos + symbol_info/symbol_select + the
# TIMEFRAME_* constants the daemon reads. Read-only; no order APIs.
# --------------------------------------------------------------------------
_DTYPE = [
    ("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
    ("close", "f8"), ("tick_volume", "i8"),
]

# Minimal set of TIMEFRAME constants (values arbitrary, just identity tokens).
_TF_CONSTS = {
    "TIMEFRAME_M1": 1, "TIMEFRAME_M2": 2, "TIMEFRAME_M5": 5,
    "TIMEFRAME_M15": 15, "TIMEFRAME_H1": 60, "TIMEFRAME_D1": 1440,
}


class FakeMt5:
    def __init__(self, rates_by_key):
        # rates_by_key: {(broker_sym, mt5_tf): list of (t,o,h,l,c,tv)}
        self._rates = rates_by_key
        self.calls = []
        self.initialized = False
        for name, val in _TF_CONSTS.items():
            setattr(self, name, val)

    def initialize(self, path=None, **kw):
        self.initialized = True
        return True

    def shutdown(self):
        self.initialized = False

    def symbol_info(self, sym):
        return object()  # present

    def symbol_select(self, sym, on):
        return True

    def copy_rates_from_pos(self, sym, tf, start, count):
        self.calls.append((sym, tf, start, count))
        rows = self._rates.get((sym, tf), [])
        return np.array(rows[-count:], dtype=_DTYPE) if rows else np.array([], dtype=_DTYPE)

    def last_error(self):
        return (0, "ok")


def _seed_monolith(lake_root, lake_key, tf_min, epochs):
    idx = pd.to_datetime(epochs, unit="s", utc=True)
    df = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        index=idx)
    store.write_bars(lake_root, lake_key, tf_min, df)


# --------------------------------------------------------------------------
# Test 1: incremental merge (tail extends monolith, no rows lost, tiers rebuilt)
# --------------------------------------------------------------------------
def test_run_cycle_merges_tail_and_rebuilds_tiers(tmp_path, monkeypatch):
    lake_root = tmp_path / "lake"
    # seed monolith M1 up to t=120
    _seed_monolith(lake_root, "XAUUSD", 1, [0, 60, 120])
    now_epoch = 1000  # far in the future so nothing is "forming"

    # fake returns a tail extending to t=300 (bars close well before now).
    tail = [(0, 1, 1, 1, 1, 1), (60, 1, 1, 1, 1, 1), (120, 1, 1, 1, 1, 1),
            (180, 2, 2, 2, 2, 2), (240, 2, 2, 2, 2, 2), (300, 2, 2, 2, 2, 2)]
    fake = FakeMt5({("XAUUSD", fake_tf): tail for fake_tf in _TF_CONSTS.values()})

    tier_calls = []
    monkeypatch.setattr(ing, "build_tiers",
                        lambda key, root, **kw: tier_calls.append(key))

    ing.run_cycle(fake, lake_root, symbol_map={"XAUUSD": "XAUUSD"},
                  timeframes={1: fake.TIMEFRAME_M1}, tail_bars=1500,
                  now_epoch=now_epoch)

    got = store.read_bars(lake_root, "XAUUSD", 1)
    epochs = [int(t.timestamp()) for t in got.index]
    assert epochs == [0, 60, 120, 180, 240, 300]  # merged, nothing lost
    assert tier_calls == ["XAUUSD"]  # tiers rebuilt for the changed symbol


# --------------------------------------------------------------------------
# Test 2: skip-unchanged tiering (no advance -> build_tiers NOT called)
# --------------------------------------------------------------------------
def test_run_cycle_skips_tiers_when_no_new_bars(tmp_path, monkeypatch):
    lake_root = tmp_path / "lake"
    _seed_monolith(lake_root, "XAUUSD", 1, [0, 60, 120])
    now_epoch = 1000

    # fake returns ONLY already-present bars (no advance).
    same = [(0, 1, 1, 1, 1, 1), (60, 1, 1, 1, 1, 1), (120, 1, 1, 1, 1, 1)]
    fake = FakeMt5({("XAUUSD", fake_tf): same for fake_tf in _TF_CONSTS.values()})

    tier_calls = []
    monkeypatch.setattr(ing, "build_tiers",
                        lambda key, root, **kw: tier_calls.append(key))

    ing.run_cycle(fake, lake_root, symbol_map={"XAUUSD": "XAUUSD"},
                  timeframes={1: fake.TIMEFRAME_M1}, tail_bars=1500,
                  now_epoch=now_epoch)

    assert tier_calls == []  # no new bars -> tiers NOT rebuilt


# --------------------------------------------------------------------------
# Test 3: forming-bar drop (last still-open bar excluded)
# --------------------------------------------------------------------------
def test_run_cycle_drops_forming_bar(tmp_path, monkeypatch):
    lake_root = tmp_path / "lake"
    # M1 bars; last bar opens at t=180, closes at 240. now=200 -> forming.
    tail = [(0, 1, 1, 1, 1, 1), (60, 1, 1, 1, 1, 1),
            (120, 1, 1, 1, 1, 1), (180, 9, 9, 9, 9, 9)]
    fake = FakeMt5({("XAUUSD", fake_tf): tail for fake_tf in _TF_CONSTS.values()})
    monkeypatch.setattr(ing, "build_tiers", lambda key, root, **kw: None)

    ing.run_cycle(fake, lake_root, symbol_map={"XAUUSD": "XAUUSD"},
                  timeframes={1: fake.TIMEFRAME_M1}, tail_bars=1500,
                  now_epoch=200)

    got = store.read_bars(lake_root, "XAUUSD", 1)
    epochs = [int(t.timestamp()) for t in got.index]
    assert 180 not in epochs  # forming bar dropped
    assert epochs == [0, 60, 120]


def test_run_cycle_uses_copy_rates_from_pos_not_paging(tmp_path, monkeypatch):
    """Guard: the daemon must do a light tail fetch (copy_rates_from_pos with
    start=0), NOT backward-paging via copy_rates_from."""
    lake_root = tmp_path / "lake"
    tail = [(0, 1, 1, 1, 1, 1), (60, 1, 1, 1, 1, 1)]
    fake = FakeMt5({("XAUUSD", 1): tail})
    monkeypatch.setattr(ing, "build_tiers", lambda key, root, **kw: None)

    ing.run_cycle(fake, lake_root, symbol_map={"XAUUSD": "XAUUSD"},
                  timeframes={1: fake.TIMEFRAME_M1}, tail_bars=777,
                  now_epoch=10_000)

    assert fake.calls == [("XAUUSD", 1, 0, 777)]  # pos-based tail, count=tail_bars
    assert not hasattr(fake, "_paged")


def test_module_does_not_import_metatrader5_at_top():
    src = open(ing.__file__, encoding="utf-8").read()
    assert "import MetaTrader5" not in src.split("def ")[0]  # not at module top
    assert "order_send" not in src  # read-only
