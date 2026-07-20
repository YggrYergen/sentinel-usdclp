"""tests/scripts/test_check_live_sim_parity.py -- PHASE 3.5 shadow-parity
checker tests. Builds a synthetic 'recorded-live' deals dataset directly from
the simulator's own event stream (a perfectly faithful live run), asserts
MATCH; then injects divergences (missed entry, extra entry, price beyond
tolerance) and asserts each is caught as HARD. No DB, no lake, no network --
exercises the pure `diff_config` core."""
from __future__ import annotations

import copy
import json
import random
from datetime import datetime, timezone

import pytest

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


# ---------------------------------------------------------------------------
# SAME_BAR_OPTIMISM: a sim exit fired via a trail motivo (EXIT_TRAIL) can
# legitimately land beyond spread+tick tolerance vs. the live fallback fill
# (which happens at market on the NEXT tick, i.e. same bar or the bar right
# after). These synthetic-events tests bypass `simular_variant` entirely by
# monkeypatching it, giving full control over entry/exit motivo + bar_idx +
# price, per the "reuse diff_config w/ monkeypatched simular_variant" fallback
# noted in the task spec.
# ---------------------------------------------------------------------------

def _synthetic_events_bars(entry_bar=10, exit_bar=12, entry_px=4500.0,
                            exit_motivo="EXIT_TRAIL", n=30, tf_s=300):
    base = int(datetime(2026, 7, 13, tzinfo=timezone.utc).timestamp())
    bars = [{"open": 4500.0, "high": 4501.0, "low": 4499.0, "close": 4500.0,
             "t": base + k * tf_s} for k in range(n)]
    events = [
        {"idx": entry_bar, "lado": "L", "precio": entry_px, "motivo": "ENTRY_L", "ficha": None},
        {"idx": exit_bar, "lado": "L", "precio": entry_px + 10.0, "motivo": exit_motivo, "ficha": "F1"},
    ]
    return events, bars


def _make_deals(cfg, bars, entry_bar, entry_px, live_exit_bar, live_exit_px, tf_s):
    """3 fichas open (magic+1/+2/+3, satisfying FICHA_COUNT); only F1
    (magic+1) exits -- the sim's single synthetic exit event pairs against
    it (fichas 2/3 stay open, which the sim-exits-vs-live-exit-count pairing
    tolerates since s['exits'] has exactly 1 entry)."""
    t_entry = bars[entry_bar]["t"] + 5
    t_exit = bars[live_exit_bar]["t"] + 5
    deals = [
        {"ticket": 100 + off, "position_id": 1000 + off, "symbol": "XAUUSD", "side": "BUY",
         "volume": 0.10, "price": entry_px, "profit": 0.0,
         "magic": cfg["magic"] + off, "time": t_entry, "entry_type": "IN"}
        for off in (1, 2, 3)
    ]
    deals.append({"ticket": 200, "position_id": 1001, "symbol": "XAUUSD", "side": "SELL",
                  "volume": 0.10, "price": live_exit_px, "profit": 0.0,
                  "magic": cfg["magic"] + 1, "time": t_exit, "entry_type": "OUT"})
    return deals


def test_same_bar_optimism_classified_not_hard(monkeypatch):
    tf_s = TF_SECONDS[CFG["tf"]]
    entry_bar, exit_bar = 10, 12
    entry_px = 4500.0
    sim_exit_px = entry_px + 10.0  # sim trail exit price (bar `exit_bar`)
    events, bars = _synthetic_events_bars(entry_bar, exit_bar, entry_px,
                                          exit_motivo="EXIT_TRAIL", tf_s=tf_s)
    monkeypatch.setattr(
        "scripts.live.check_live_sim_parity.simular_variant",
        lambda bars_, **kw: events)
    # live fallback fill lands next bar, at market, well beyond tol (>0.51)
    live_exit_px = sim_exit_px - 5.0
    deals = _make_deals(CFG, bars, entry_bar, entry_px, exit_bar + 1, live_exit_px, tf_s)
    rep = diff_config(CFG, bars, deals)
    kinds = [d.kind for d in rep.divergences]
    assert "SAME_BAR_OPTIMISM" in kinds
    sbo = next(d for d in rep.divergences if d.kind == "SAME_BAR_OPTIMISM")
    assert sbo.hard is False
    assert rep.verdict == "MATCH"
    assert rep.same_bar_optimism == 1
    assert rep.same_bar_cost == pytest.approx(abs(sim_exit_px - live_exit_px))
    assert not any(d.kind == "EXIT_PRICE_OUT_OF_TOL" for d in rep.divergences)


def test_out_of_tol_non_samebar_still_hard(monkeypatch):
    tf_s = TF_SECONDS[CFG["tf"]]
    entry_bar, exit_bar = 10, 12
    entry_px = 4500.0
    sim_exit_px = entry_px + 10.0
    # non-trail motivo -> does not qualify for SAME_BAR_OPTIMISM even though
    # the live fill lands on the same bar
    events, bars = _synthetic_events_bars(entry_bar, exit_bar, entry_px,
                                          exit_motivo="EXIT_TP", tf_s=tf_s)
    monkeypatch.setattr(
        "scripts.live.check_live_sim_parity.simular_variant",
        lambda bars_, **kw: events)
    live_exit_px = sim_exit_px - 5.0
    deals = _make_deals(CFG, bars, entry_bar, entry_px, exit_bar, live_exit_px, tf_s)
    rep = diff_config(CFG, bars, deals)
    assert any(d.kind == "EXIT_PRICE_OUT_OF_TOL" and d.hard for d in rep.divergences)
    assert rep.verdict == "DIVERGENCE"
    assert rep.same_bar_optimism == 0

    # also: trail motivo but live fill 2+ bars later -> still hard
    events2, bars2 = _synthetic_events_bars(entry_bar, exit_bar, entry_px,
                                            exit_motivo="EXIT_TRAIL", tf_s=tf_s)
    monkeypatch.setattr(
        "scripts.live.check_live_sim_parity.simular_variant",
        lambda bars_, **kw: events2)
    deals2 = _make_deals(CFG, bars2, entry_bar, entry_px, exit_bar + 2, live_exit_px, tf_s)
    rep2 = diff_config(CFG, bars2, deals2)
    # too far (2 bars later) to qualify for the same-bar-optimism fallback --
    # classified hard, either as an outright exit-bars mismatch or (if bars
    # happen to line up) as EXIT_PRICE_OUT_OF_TOL; either way must be hard.
    assert any(d.kind in ("EXIT_PRICE_OUT_OF_TOL", "EXIT_BARS_MISMATCH") and d.hard
              for d in rep2.divergences)
    assert rep2.verdict == "DIVERGENCE"
    assert rep2.same_bar_optimism == 0


def test_within_tol_unchanged(monkeypatch):
    tf_s = TF_SECONDS[CFG["tf"]]
    entry_bar, exit_bar = 10, 12
    entry_px = 4500.0
    sim_exit_px = entry_px + 10.0
    events, bars = _synthetic_events_bars(entry_bar, exit_bar, entry_px,
                                          exit_motivo="EXIT_TRAIL", tf_s=tf_s)
    monkeypatch.setattr(
        "scripts.live.check_live_sim_parity.simular_variant",
        lambda bars_, **kw: events)
    live_exit_px = sim_exit_px - 0.2  # within tol (0.51)
    deals = _make_deals(CFG, bars, entry_bar, entry_px, exit_bar, live_exit_px, tf_s)
    rep = diff_config(CFG, bars, deals)
    assert any(d.kind == "EXIT_PRICE_WITHIN_TOL" for d in rep.divergences)
    assert rep.verdict == "MATCH"
    assert rep.same_bar_optimism == 0


def test_json_includes_same_bar_fields(monkeypatch, tmp_path):
    tf_s = TF_SECONDS[CFG["tf"]]
    entry_bar, exit_bar = 10, 12
    entry_px = 4500.0
    sim_exit_px = entry_px + 10.0
    events, bars = _synthetic_events_bars(entry_bar, exit_bar, entry_px,
                                          exit_motivo="EXIT_TRAIL", tf_s=tf_s)
    monkeypatch.setattr(
        "scripts.live.check_live_sim_parity.simular_variant",
        lambda bars_, **kw: events)
    live_exit_px = sim_exit_px - 5.0
    deals = _make_deals(CFG, bars, entry_bar, entry_px, exit_bar + 1, live_exit_px, tf_s)
    rep = diff_config(CFG, bars, deals)
    dump = {
        "config_id": rep.config_id, "same_bar_optimism": rep.same_bar_optimism,
        "same_bar_cost": rep.same_bar_cost,
    }
    out = tmp_path / "report.json"
    out.write_text(json.dumps([dump]), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))[0]
    assert "same_bar_optimism" in loaded
    assert "same_bar_cost" in loaded
    assert loaded["same_bar_optimism"] == 1
    assert loaded["same_bar_cost"] == pytest.approx(abs(sim_exit_px - live_exit_px))


# ---------------------------------------------------------------------------
# FIX A -- next-bar entry matching: the live executor decides at bar-close and
# the fill lands on the NEXT tick, whose timestamp maps into bar N+1, while
# sim entries are recorded at the signal bar N. These tests exercise
# ENTRY_NEXT_BAR classification, genuine MISSED/EXTRA entries, and the FIX B
# warmup window via monkeypatched simular_variant (per the spec's suggested
# approach).
# ---------------------------------------------------------------------------

def test_entry_filled_next_bar_matched_not_hard(monkeypatch):
    tf_s = TF_SECONDS[CFG["tf"]]
    entry_bar = 10
    entry_px = 4500.0
    events, bars = _synthetic_events_bars(entry_bar, entry_bar + 2, entry_px,
                                          exit_motivo="EXIT_TRAIL", tf_s=tf_s)
    # keep only the entry event -- no exit needed for this test
    entry_only = [events[0]]
    monkeypatch.setattr(
        "scripts.live.check_live_sim_parity.simular_variant",
        lambda bars_, **kw: entry_only)
    # live fill lands one bar later (next tick), with a price gap
    live_entry_px = entry_px + 2.0  # gap >> tol (spread 0.5 + tick 0.01)
    t_fill = bars[entry_bar + 1]["t"] + 5
    deals = [
        {"ticket": 100 + off, "position_id": 1000 + off, "symbol": "XAUUSD", "side": "BUY",
         "volume": 0.10, "price": live_entry_px, "profit": 0.0,
         "magic": CFG["magic"] + off, "time": t_fill, "entry_type": "IN"}
        for off in (1, 2, 3)
    ]
    rep = diff_config(CFG, bars, deals)
    assert rep.verdict == "MATCH", [d.detail for d in rep.hard_divergences]
    assert rep.matches == 1
    assert rep.entry_next_bar == 1
    assert rep.entry_slip_cost == pytest.approx(abs(live_entry_px - entry_px))
    kinds = [d.kind for d in rep.divergences]
    assert "ENTRY_NEXT_BAR" in kinds
    assert "MISSED_ENTRY" not in kinds
    assert "EXTRA_ENTRY" not in kinds
    assert "ENTRY_PRICE_OUT_OF_TOL" not in kinds
    nb = next(d for d in rep.divergences if d.kind == "ENTRY_NEXT_BAR")
    assert nb.hard is False


def test_genuine_missed_entry_no_live_at_n_or_n1(monkeypatch):
    tf_s = TF_SECONDS[CFG["tf"]]
    entry_bar = 10
    entry_px = 4500.0
    events, bars = _synthetic_events_bars(entry_bar, entry_bar + 2, entry_px,
                                          exit_motivo="EXIT_TRAIL", tf_s=tf_s)
    entry_only = [events[0]]
    monkeypatch.setattr(
        "scripts.live.check_live_sim_parity.simular_variant",
        lambda bars_, **kw: entry_only)
    rep = diff_config(CFG, bars, [])  # no live deals at all
    assert rep.verdict == "DIVERGENCE"
    assert any(d.kind == "MISSED_ENTRY" and d.hard for d in rep.divergences)
    assert rep.entry_next_bar == 0


def test_genuine_extra_entry_no_sim_at_n_or_n_minus_1(monkeypatch):
    tf_s = TF_SECONDS[CFG["tf"]]
    entry_bar = 10
    entry_px = 4500.0
    events, bars = _synthetic_events_bars(entry_bar, entry_bar + 2, entry_px,
                                          exit_motivo="EXIT_TRAIL", tf_s=tf_s)
    entry_only = [events[0]]
    monkeypatch.setattr(
        "scripts.live.check_live_sim_parity.simular_variant",
        lambda bars_, **kw: entry_only)
    # live position far from the sim entry bar (not N, not N-1)
    rogue_bar = entry_bar + 5
    t_fill = bars[rogue_bar]["t"] + 5
    deals = [
        {"ticket": 100 + off, "position_id": 1000 + off, "symbol": "XAUUSD", "side": "BUY",
         "volume": 0.10, "price": entry_px, "profit": 0.0,
         "magic": CFG["magic"] + off, "time": t_fill, "entry_type": "IN"}
        for off in (1, 2, 3)
    ]
    rep = diff_config(CFG, bars, deals)
    assert rep.verdict == "DIVERGENCE"
    assert any(d.kind == "EXTRA_ENTRY" and d.hard for d in rep.divergences)
    # the genuine MISSED_ENTRY for the sim's own entry_bar should also fire
    assert any(d.kind == "MISSED_ENTRY" and d.hard for d in rep.divergences)


def test_warmup_window_passes_full_bars_and_trims_diff(monkeypatch, tmp_path):
    """FIX B: build a synthetic bars list where the sim's signal depends on
    bars before `start`. We monkeypatch simular_variant to assert it received
    the FULL warmup+day bars list, and return one entry inside the window and
    one entry BEFORE the window (which must be excluded from the diff)."""
    tf_s = TF_SECONDS[CFG["tf"]]
    base = int(datetime(2026, 7, 13, tzinfo=timezone.utc).timestamp())
    n_warmup = 20
    n_day = 15
    total = n_warmup + n_day
    bars = [{"open": 4500.0, "high": 4501.0, "low": 4499.0, "close": 4500.0,
             "t": base + k * tf_s} for k in range(total)]
    first_in_window_idx = n_warmup

    captured = {}

    def fake_sim(bars_, **kw):
        captured["n_bars"] = len(bars_)
        return [
            # an entry BEFORE the window -- must be excluded from the diff
            {"idx": 5, "lado": "L", "precio": 4500.0, "motivo": "ENTRY_L", "ficha": None},
            # an entry INSIDE the window
            {"idx": n_warmup + 3, "lado": "L", "precio": 4500.0, "motivo": "ENTRY_L", "ficha": None},
        ]

    monkeypatch.setattr("scripts.live.check_live_sim_parity.simular_variant", fake_sim)

    t_fill = bars[n_warmup + 3]["t"] + 5
    deals = [
        {"ticket": 100 + off, "position_id": 1000 + off, "symbol": "XAUUSD", "side": "BUY",
         "volume": 0.10, "price": 4500.0, "profit": 0.0,
         "magic": CFG["magic"] + off, "time": t_fill, "entry_type": "IN"}
        for off in (1, 2, 3)
    ]
    rep = diff_config(CFG, bars, deals, first_in_window_idx=first_in_window_idx)
    assert captured["n_bars"] == total  # simular_variant saw warmup + day bars
    assert rep.sim_entries == 1  # only the in-window entry is diffed
    assert rep.n_bars == n_day
    assert rep.verdict == "MATCH", [d.detail for d in rep.hard_divergences]
    assert rep.matches == 1


# ---------------------------------------------------------------------------
# P36 (Wave 6 governance) -- extend the sim<->live parity axis to cover the
# tp_min_pips fixed-TP lever (commit 0f3e7c0). The `diff_config` core re-runs
# `simular_variant(**config["kwargs"])`, so a config carrying `tp_min_pips` in
# its kwargs exercises the EXIT_TP exit path end-to-end. A PERFECT live replay
# built from that same tp_min-active sim event stream must still verdict MATCH:
# the fixed-TP exits are a pre-existing (non-trail) level, so live fills them
# at the exact sim price on the exact sim bar -- no divergence.
#
# This is the tp_min coverage of the sim<->live parity axis (the intrabar
# fill-mode / return_state / carry axes are pinned in
# tests/strategies/test_emasar_livefill_state.py). No tolerance is needed;
# the fixed TP is exact.
# ---------------------------------------------------------------------------

# Wide trails + wide initial stop so fichas HOLD and a small fixed tp_min_pips
# actually bites (otherwise the trail exits first and no EXIT_TP ever fires).
CFG_TPMIN = copy.deepcopy(CFG)
CFG_TPMIN["id"] = f"{CFG['id']}-TPMIN"
CFG_TPMIN["kwargs"] = dict(
    CFG["kwargs"],
    f1_trail_pips=2000.0, f2_trail_pips=2000.0, f3_trail_pips=2000.0,
    init_sl_range_k=6.0, ac_modulate=False,
    tp_min_pips=50.0,
)
BARS_TPMIN = _synthetic_bars(tf_s=TF_SECONDS[CFG_TPMIN["tf"]])
DEALS_TPMIN = _fake_live_deals(CFG_TPMIN, BARS_TPMIN)


def test_tpmin_config_actually_fires_exit_tp():
    """Guard: the tp_min-active fixture must genuinely exercise EXIT_TP exits
    (otherwise the parity cell below would be vacuous vs the no-op default)."""
    events = simular_variant(BARS_TPMIN, **CFG_TPMIN["kwargs"])
    n_tp = sum(1 for e in events if e["motivo"] == "EXIT_TP")
    assert n_tp > 0, "tp_min fixture produced no EXIT_TP exits -- not exercising the lever"


def test_tpmin_perfect_replay_is_match():
    """A perfect live replay of a tp_min-ACTIVE config still verdicts MATCH:
    the fixed-TP exits reconcile exactly against live at the sim bar/price."""
    rep = diff_config(CFG_TPMIN, BARS_TPMIN, DEALS_TPMIN)
    assert rep.verdict == "MATCH", [d.detail for d in rep.hard_divergences]
    assert rep.sim_entries >= 1
    assert rep.matches == rep.sim_entries
    # only the half-spread ENTRY offset is classified; no hard exit divergence.
    assert all(not d.hard for d in rep.divergences)


def test_tpmin_injected_exit_price_out_of_tol_is_hard():
    """Sanity that the tp_min cell still CATCHES a genuine break: shifting one
    tp_min exit fill far beyond tolerance must be flagged hard (the parity gate
    is not silently disabled by the fixed-TP motivo)."""
    bad = [dict(d) for d in DEALS_TPMIN]
    for d in bad:
        if d["entry_type"] == "OUT":
            d["price"] = d["price"] + 5.0
            break
    rep = diff_config(CFG_TPMIN, BARS_TPMIN, bad)
    assert rep.verdict == "DIVERGENCE"
    assert any(d.kind == "EXIT_PRICE_OUT_OF_TOL" and d.hard for d in rep.divergences)
