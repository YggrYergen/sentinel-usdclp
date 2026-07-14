"""tests/scripts/test_check_live_sim_parity.py -- PHASE 3.5 shadow-parity
checker tests. Builds a synthetic 'recorded-live' deals dataset directly from
the simulator's own event stream (a perfectly faithful live run), asserts
MATCH; then injects divergences (missed entry, extra entry, price beyond
tolerance) and asserts each is caught as HARD. No DB, no lake, no network --
exercises the pure `diff_config` core."""
from __future__ import annotations

import random
from datetime import datetime, timezone

from scripts.live.check_live_sim_parity import diff_config, TF_SECONDS
from sentinel_engine.strategies.emasar_variant import simular_variant
from sentinel_engine.strategies.live_configs_20 import CONFIGS_20


def _cfg(cid: str) -> dict:
    return next(c for c in CONFIGS_20 if c["id"] == cid)


def _synthetic_bars(n=800, seed=11, tf_s=300):
    rnd = random.Random(seed)
    bars, price = [], 4500.0
    base = int(datetime(2026, 7, 13, tzinfo=timezone.utc).timestamp())
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        o, c = price - drift, price
        h = max(o, c) + abs(rnd.uniform(0.3, 1.2))
        lo = min(o, c) - abs(rnd.uniform(0.3, 1.2))
        bars.append({"open": o, "high": h, "low": lo, "close": c, "t": base + k * tf_s})
    return bars


def _fake_live_deals(cfg: dict, bars: list[dict], *, spread: float = 0.5) -> list[dict]:
    """Perfect live replay: for each sim ENTRY, 3 IN deals (fichas, magics
    base+1..+3, entry px = sim px + half-spread) inside the signal bar; for
    each EXIT, one OUT deal on the exit bar at the sim exit price."""
    events = simular_variant(bars, **cfg["kwargs"])
    deals, ticket, pos_ids = [], 1, []
    half = spread / 2.0
    for ev in events:
        t_fill = bars[ev["idx"]]["t"] + 5  # a few seconds into the bar
        if ev["motivo"].startswith("ENTRY"):
            side = "BUY" if ev["lado"] == "L" else "SELL"
            px = ev["precio"] + (half if ev["lado"] == "L" else -half)
            pos_ids = []
            for off in (1, 2, 3):
                deals.append({"ticket": ticket, "position_id": 1000 + ticket,
                              "symbol": "XAUUSD", "side": side, "volume": 0.10,
                              "price": px, "profit": 0.0,
                              "magic": cfg["magic"] + off, "time": t_fill,
                              "entry_type": "IN"})
                pos_ids.append(1000 + ticket)
                ticket += 1
        else:
            if not pos_ids:
                continue
            pid = pos_ids.pop(0)
            deals.append({"ticket": ticket, "position_id": pid,
                          "symbol": "XAUUSD", "side": "SELL" if ev["lado"] == "L" else "BUY",
                          "volume": 0.10, "price": ev["precio"], "profit": 0.0,
                          "magic": cfg["magic"] + 1, "time": t_fill,
                          "entry_type": "OUT"})
            ticket += 1
    return deals


CFG = _cfg("V06D-M5")
BARS = _synthetic_bars(tf_s=TF_SECONDS[CFG["tf"]])
DEALS = _fake_live_deals(CFG, BARS)


def test_fixture_has_signal():
    assert any(d["entry_type"] == "IN" for d in DEALS), "fixture must produce entries"


def test_perfect_replay_is_match():
    rep = diff_config(CFG, BARS, DEALS)
    assert rep.verdict == "MATCH", [d.detail for d in rep.hard_divergences]
    assert rep.sim_entries >= 1
    assert rep.matches == rep.sim_entries
    # half-spread entry offset must be classified, not fail hard
    assert all(not d.hard for d in rep.divergences)


def test_injected_missed_entry_is_hard():
    # drop the live fichas of the FIRST sim entry entirely
    first_in_t = min(d["time"] for d in DEALS if d["entry_type"] == "IN")
    pids = {d["position_id"] for d in DEALS if d["time"] == first_in_t and d["entry_type"] == "IN"}
    pruned = [d for d in DEALS if d["position_id"] not in pids]
    rep = diff_config(CFG, BARS, pruned)
    assert rep.verdict == "DIVERGENCE"
    assert any(d.kind == "MISSED_ENTRY" for d in rep.hard_divergences)


def test_injected_extra_entry_is_hard():
    # add a live position on a bar where the sim has no entry
    events = simular_variant(BARS, **CFG["kwargs"])
    entry_bars = {e["idx"] for e in events if e["motivo"].startswith("ENTRY")}
    rogue_bar = next(i for i in range(50, len(BARS)) if i not in entry_bars)
    rogue = dict(DEALS[0]) if DEALS else {}
    rogue.update({"ticket": 999999, "position_id": 999999, "side": "BUY",
                  "price": BARS[rogue_bar]["close"], "magic": CFG["magic"] + 1,
                  "time": BARS[rogue_bar]["t"] + 5, "entry_type": "IN",
                  "volume": 0.10, "symbol": "XAUUSD", "profit": 0.0})
    rep = diff_config(CFG, BARS, DEALS + [rogue])
    assert rep.verdict == "DIVERGENCE"
    assert any(d.kind == "EXTRA_ENTRY" for d in rep.hard_divergences)


def test_injected_price_out_of_tolerance_is_hard():
    # shift one live entry fill 5.0 beyond the sim price (>> tol 0.51)
    bad = [dict(d) for d in DEALS]
    for d in bad:
        if d["entry_type"] == "IN":
            d["price"] = d["price"] + 5.0
            break
    rep = diff_config(CFG, BARS, bad)
    assert rep.verdict == "DIVERGENCE"
    assert any(d.kind == "ENTRY_PRICE_OUT_OF_TOL" for d in rep.hard_divergences)


def test_within_tolerance_is_classified_not_hard():
    rep = diff_config(CFG, BARS, DEALS)
    # the fixture applies half-spread (0.25) > tick (0.01) -> WITHIN_TOL
    assert rep.within_tolerance >= 1
    assert all(d.kind.endswith("WITHIN_TOL") for d in rep.divergences)
