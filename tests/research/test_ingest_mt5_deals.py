"""tests/research/test_ingest_mt5_deals.py — TDD for
`sentinel_engine.research.ingest_mt5_deals` (EMASAR V1 MT5-fidelity
integration, design spec
docs/superpowers/specs/2026-07-10-emasar-v1-mt5-integration-design.md,
Components 2-4).

Covers: (1) pairing MT5 deals into 3-ficha signals, (2) matching
`emasar_ref.simular` events to those deals to tag ficha+motivo, (3) the T1
signal-parity fidelity gate (pass on a known window, fail on a corrupted
deal set), (4) the "bars unavailable" graceful-degradation path, (5) the
end-to-end `ingest_mt5_htm` entrypoint writing signal_id/ficha-tagged trades
+ a fidelity_ref into `research.db` without ever touching the real
`research.db` / TOKATA tree (uses the small fixture `.htm` + a synthetic bar
set built to reproduce the fixture's 3-ficha signal via `simular`).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_engine.research import ingest_mt5_deals as ing
from sentinel_engine.research.mt5_report import parse_mt5_report
from sentinel_engine.research.registry2 import ResearchRegistry

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def reg(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def _sample_report():
    return parse_mt5_report(FIXTURES / "mt5_report_emasar_sample.htm")


# ---------------------------------------------------------------------
# pair_deals_into_signals
# ---------------------------------------------------------------------

def test_three_simultaneous_in_deals_become_one_signal_with_three_fichas():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    anchor = next(s for s in signals if s["ts_in"] == "2026.01.11 20:00:00")
    assert len(anchor["fichas"]) == 3
    assert {f["ficha"] for f in anchor["fichas"]} == {"F1", "F2", "F3"}
    assert all(f["px_in"] == pytest.approx(4511.96) for f in anchor["fichas"])
    assert anchor["side"] == "LONG"


def test_fichas_paired_to_their_out_deal_by_order_sequence():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    anchor = next(s for s in signals if s["ts_in"] == "2026.01.11 20:00:00")
    profits = sorted(f["pnl"] for f in anchor["fichas"])
    assert profits == pytest.approx([154.10, 280.30, 551.70])
    for f in anchor["fichas"]:
        assert f["ts_out"] is not None
        assert f["px_out"] is not None


def test_signal_id_stable_and_unique_per_signal():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    ids = [s["signal_id"] for s in signals]
    assert len(ids) == len(set(ids))
    assert all(ids)


def test_balance_deposit_row_is_not_a_signal():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    assert all(s["ts_in"] != "2026.01.02 00:00:00" for s in signals)


# ---------------------------------------------------------------------
# match_events_to_deals / annotate
# ---------------------------------------------------------------------

def _anchor_bars():
    """A tiny synthetic OHLC series engineered so `emasar_ref.simular`
    (V1, sar 0.3/0.3) fires an ENTRY_L at bar index matching the anchor
    signal's price (4511.96), so ficha/motivo matching can be exercised
    without needing the real (lake-gapped) XAUUSD M5 history."""
    bars = []
    price = 4490.0
    for i in range(30):
        drift = 1.0 if i < 20 else -0.5
        price += drift
        bars.append({
            "open": price - drift, "high": price + 1.0,
            "low": price - drift - 1.0, "close": price,
        })
    return bars


def test_annotate_signals_tags_ficha_and_motivo_when_events_available():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    anchor = next(s for s in signals if s["ts_in"] == "2026.01.11 20:00:00")
    # Fabricate emasar_ref-shaped events matching the anchor's 3 fichas so
    # the matching logic itself (independent of simular()'s real gate
    # firing on this toy series) is under test here.
    events = [
        {"idx": 5, "lado": "L", "precio": 4511.96, "motivo": "ENTRY_L", "ficha": None},
        {"idx": 6, "lado": "L", "precio": 4527.37, "motivo": "EXIT_ENGULF", "ficha": "F1"},
        {"idx": 7, "lado": "L", "precio": 4539.99, "motivo": "EXIT_STFLIP", "ficha": "F2"},
        {"idx": 8, "lado": "L", "precio": 4567.13, "motivo": "EXIT_TRAIL", "ficha": "F3"},
    ]
    annotated = ing.annotate_signal_with_events(anchor, events)
    by_ficha = {f["ficha"]: f for f in annotated["fichas"]}
    assert by_ficha["F1"]["motivo"] == "EXIT_ENGULF"
    assert by_ficha["F1"]["exit_reason_source"] == "emasar_ref"
    assert by_ficha["F2"]["motivo"] == "EXIT_STFLIP"
    assert by_ficha["F3"]["motivo"] == "EXIT_TRAIL"


def test_annotate_falls_back_to_htm_sl_comment_when_no_matching_event():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    anchor = next(s for s in signals if s["ts_in"] == "2026.01.11 20:00:00")
    # No emasar_ref events at all -> fall back to the .htm comment on the
    # ficha whose out-deal carries "sl <price>" (F1's out has comment
    # "sl 4527.37" per the real report).
    annotated = ing.annotate_signal_with_events(anchor, [])
    f1 = next(f for f in annotated["fichas"] if f["px_out"] == pytest.approx(4527.37))
    assert f1["exit_reason_source"] == "mt5-comment"
    assert f1["motivo"] == "sl"


# ---------------------------------------------------------------------
# Requirement 0 (Wave-2 plan 2026-07-10): 7/69 real trades on the certified
# run come back with a null exit_reason -- all of them F2/F3 fichas whose
# out-deal carries NO ".htm" comment (only F1's SL-hit exits do) and no
# emasar_ref event matched (lake gap for Jan/Feb -> bars_unavailable
# degrades to motivo=None). Per the design: a ficha that closed WITHOUT an
# SL/TP comment, but DID fully close (has px_out/ts_out), was closed by the
# strategy's own opposite-signal/flip logic -- label it deterministically
# `signal` (source `derived`) instead of leaving it null, rather than
# guessing wrong data.
# ---------------------------------------------------------------------

def test_annotate_labels_closed_ficha_signal_flip_when_no_sl_comment_or_event():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    anchor = next(s for s in signals if s["ts_in"] == "2026.01.11 20:00:00")
    # No emasar_ref events at all, and F2/F3's out-deals carry no comment in
    # the sample fixture -> they still fully closed (px_out/ts_out present)
    # so must be labeled signal/flip, never left null.
    annotated = ing.annotate_signal_with_events(anchor, [])
    by_ficha = {f["ficha"]: f for f in annotated["fichas"]}
    assert by_ficha["F2"]["motivo"] == "signal"
    assert by_ficha["F2"]["exit_reason_source"] == "derived"
    assert by_ficha["F3"]["motivo"] == "signal"
    assert by_ficha["F3"]["exit_reason_source"] == "derived"


def test_annotate_leaves_still_open_ficha_null_not_derived():
    """A ficha with no px_out/ts_out (position still open, never closed)
    must stay null -- the `signal`/`flip` fallback only applies to fichas
    that DID close (deal-structure evidence exists), never fabricated on an
    open position."""
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    open_signal = next(s for s in signals if s["ts_in"] == "2026.01.28 21:35:00")
    annotated = ing.annotate_signal_with_events(open_signal, [])
    for f in annotated["fichas"]:
        if f["px_out"] is None:
            assert f["motivo"] is None
            assert f["exit_reason_source"] is None


# ---------------------------------------------------------------------
# fidelity gate (T1 signal parity + monetary cross-check)
# ---------------------------------------------------------------------

def test_fidelity_gate_passes_when_event_counts_and_timestamps_match():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    # Build events that exactly cover every in/out deal in the sample
    # fixture (9 deals: 1 balance + 3 in + 3 out + 2 more in for a second
    # unmatched signal) -- for T1 we only need count+timestamp coverage of
    # deals that HAVE a matching bar-derived event; unmatched deals are
    # reported, not silently dropped.
    events = [
        {"idx": 0, "lado": "L", "precio": 4511.96, "motivo": "ENTRY_L", "ficha": None},
        {"idx": 1, "lado": "L", "precio": 4527.37, "motivo": "EXIT_ENGULF", "ficha": "F1"},
        {"idx": 2, "lado": "L", "precio": 4539.99, "motivo": "EXIT_STFLIP", "ficha": "F2"},
        {"idx": 3, "lado": "L", "precio": 4567.13, "motivo": "EXIT_TRAIL", "ficha": "F3"},
    ]
    anchor = next(s for s in signals if s["ts_in"] == "2026.01.11 20:00:00")
    gate = ing.check_signal_parity(anchor, events)
    assert gate["status"] == "pass"
    assert gate["matched"] == 4
    assert gate["unmatched"] == 0


def test_fidelity_gate_fails_on_corrupted_deal_set():
    report = _sample_report()
    signals = ing.pair_deals_into_signals(report["deals"])
    anchor = next(s for s in signals if s["ts_in"] == "2026.01.11 20:00:00")
    # Corrupt: F3's exit price so it can never match any emasar_ref event
    # (check_signal_parity matches exits by px_out, not px_in).
    corrupted = dict(anchor)
    corrupted["fichas"] = [
        dict(f, px_out=9999.99) if f["ficha"] == "F3" else f for f in anchor["fichas"]
    ]
    events = [
        {"idx": 0, "lado": "L", "precio": 4511.96, "motivo": "ENTRY_L", "ficha": None},
        {"idx": 1, "lado": "L", "precio": 4527.37, "motivo": "EXIT_ENGULF", "ficha": "F1"},
        {"idx": 2, "lado": "L", "precio": 4539.99, "motivo": "EXIT_STFLIP", "ficha": "F2"},
        {"idx": 3, "lado": "L", "precio": 4567.13, "motivo": "EXIT_TRAIL", "ficha": "F3"},
    ]
    gate = ing.check_signal_parity(corrupted, events)
    assert gate["status"] == "fail"
    assert gate["unmatched"] > 0


def test_monetary_cross_check_to_the_cent():
    report = _sample_report()
    check = ing.check_monetary_parity(report)
    assert check["status"] == "pass"
    assert check["htm_net"] == pytest.approx(check["deals_net"], abs=0.01)


# ---------------------------------------------------------------------
# end-to-end ingest entrypoint
# ---------------------------------------------------------------------

def test_ingest_mt5_htm_certifies_run_when_bars_available(reg):
    """Sample fixture has 2 signals: the 3-ficha anchor (01-11, fully
    closed) + a 2-ficha partial signal (01-28, F1/F2 opened, no F3/no
    closes -- the fixture is a 9-row truncation of the real report) -> 5
    trade rows total, 2 distinct signal_ids, the anchor's 3 fichas F1-F3."""
    report_path = FIXTURES / "mt5_report_emasar_sample.htm"
    bars = _anchor_bars()
    result = ing.ingest_mt5_htm(
        report_path, reg, bars_lookup=lambda symbol, tf, desde, hasta: bars,
        variant_id="EMS_XAU_V1_M5_c2_sar3m3",
    )
    assert result["run_id"]
    run = reg.get_run(result["run_id"])
    assert run["engine"] == "mt5-import"
    assert run["fidelity"] == "mt5-htm"
    trades = reg.get_trades_for_run(result["run_id"])
    assert len(trades) == 5
    signal_ids = {t["origin_id"] for t in trades}
    assert len(signal_ids) == 2
    # get_trades_for_run normalizes ts_in to ISO-8601 UTC (defect D, Wave-2
    # plan 2026-07-10) -- the MT5-dotted "2026.01.11 20:00:00" the ingester
    # stored comes back "2026-01-11T20:00:00Z".
    anchor_trades = [t for t in trades if t["ts_in"] == "2026-01-11T20:00:00Z"]
    assert len(anchor_trades) == 3
    assert sorted(t["ficha"] for t in anchor_trades) == ["F1", "F2", "F3"]


def test_ingest_mt5_htm_degrades_gracefully_when_bars_unavailable(reg):
    """Per design spec §Error handling: bars gap -> import still stores the
    imported (.htm-identical) numbers, fidelity report marks signal-parity
    'not_verified: bars_unavailable' -- MUST NOT crash, MUST NOT fake a
    pass."""
    report_path = FIXTURES / "mt5_report_emasar_sample.htm"

    def _no_bars(symbol, tf, desde, hasta):
        import pandas as pd
        return pd.DataFrame()

    result = ing.ingest_mt5_htm(
        report_path, reg, bars_lookup=_no_bars,
        variant_id="EMS_XAU_V1_M5_c2_sar3m3",
    )
    assert result["run_id"]
    run = reg.get_run(result["run_id"])
    fidelity_ref = result["fidelity_report"]
    assert fidelity_ref["signal_parity"]["status"] == "not_verified"
    assert fidelity_ref["signal_parity"]["reason"] == "bars_unavailable"
    # Monetary numbers are STILL imported identically -- degradation only
    # affects the annotation/verification layer, never the imported P&L.
    trades = reg.get_trades_for_run(result["run_id"])
    assert len(trades) == 5
    assert fidelity_ref["monetary"]["status"] == "pass"


def test_ingest_mt5_htm_trades_carry_signal_id_and_ficha_columns(reg):
    report_path = FIXTURES / "mt5_report_emasar_sample.htm"
    bars = _anchor_bars()
    result = ing.ingest_mt5_htm(
        report_path, reg, bars_lookup=lambda symbol, tf, desde, hasta: bars,
        variant_id="EMS_XAU_V1_M5_c2_sar3m3",
    )
    trades = reg.get_trades_for_run(result["run_id"])
    for t in trades:
        assert t["signal_id"] is not None
        assert t["ficha"] in ("F1", "F2", "F3")
        # exit_reason_source is populated from: an emasar_ref event match
        # (needs simular() to actually fire on the given toy `_anchor_bars`
        # fixture, which it does not for every ficha here); the .htm
        # out-deal's "sl <price>" comment (only F1's anchor exit has one,
        # per the real report); or (requirement 0, Wave-2 plan) "derived"
        # for a ficha that fully closed (px_out/ts_out present) with
        # neither -- deterministically a signal/flip close, never left
        # null nor a fabricated non-evidenced value. Only a STILL-OPEN
        # ficha (no px_out at all, e.g. the fixture's 2nd/truncated signal)
        # can legitimately stay None.
        assert t["exit_reason_source"] in ("emasar_ref", "mt5-comment", "derived", None)
    f1_anchor = next(t for t in trades if t["ficha"] == "F1" and t["ts_in"] == "2026-01-11T20:00:00Z")
    assert f1_anchor["exit_reason_source"] == "mt5-comment"
    assert f1_anchor["exit_reason"] == "sl"


def test_ingest_flags_bars_feed_mismatch_when_events_flood(reg):
    """When bars exist but are a DIFFERENT feed than MT5's own (so
    emasar_ref fires far more signals than MT5 recorded), the gate fails AND
    tags the cause 'bars_feed_mismatch' -- honest fail, actionable
    diagnosis, never a faked pass (design spec §Error handling)."""
    report_path = FIXTURES / "mt5_report_emasar_sample.htm"

    def _noisy_bars(symbol, tf, desde, hasta):
        # A long, jagged series unrelated to the .htm's prices -> emasar_ref
        # fires many entries none of which match the imported deals.
        import random
        rnd = random.Random(7)
        bars, price = [], 4000.0
        for _ in range(400):
            drift = rnd.uniform(-2.0, 2.5)
            price += drift
            bars.append({
                "open": price - drift, "high": price + abs(rnd.uniform(0.5, 2.0)),
                "low": price - drift - abs(rnd.uniform(0.5, 2.0)), "close": price,
            })
        return bars

    result = ing.ingest_mt5_htm(
        report_path, reg, bars_lookup=_noisy_bars,
        variant_id="EMS_XAU_V1_M5_c2_sar3m3",
    )
    sp = result["fidelity_report"]["signal_parity"]
    assert sp["status"] == "fail"
    assert sp["diagnosis"] == "bars_feed_mismatch"
    # Monetary numbers still imported identically regardless.
    assert result["fidelity_report"]["monetary"]["status"] == "pass"


def test_mt5_import_sets_native_tf(reg):
    """Task 1.2 (Wave-3 Stage 1): /api/runs/{id} must return a non-null `tf`
    for mt5-import runs so REVIEW opens on the run's native timeframe (never
    a hardcoded M1, which lacks history for January trades). The sample
    fixture's `.htm` settings block reports Período "M5 (...)" -> tf="M5"."""
    report_path = FIXTURES / "mt5_report_emasar_sample.htm"
    bars = _anchor_bars()
    result = ing.ingest_mt5_htm(
        report_path, reg, bars_lookup=lambda symbol, tf, desde, hasta: bars,
        variant_id="EMS_XAU_V1_M5_c2_sar3m3",
    )
    run = reg.get_run(result["run_id"])
    assert run["tf"] == "M5"


def test_legacy_sim_trades_unaffected_by_new_nullable_columns(reg):
    """The additive migration must not break existing single-exit sim
    trades: signal_id/ficha are NULL for rows inserted the old way (no
    special-casing needed by callers that predate this wave)."""
    sid = reg.upsert_strategy("EMASAR", "emasar", "mt5")
    vid = reg.upsert_variant(sid, "emasar_test_v2", {}, "M5", "XAUUSD", "engulfing")
    run_id = "legacy-run-0001"
    reg.insert_run({
        "run_id": run_id, "variant_id": vid, "engine": "sentinel-sim",
        "fidelity": "research", "trades": 1, "net": 10.0,
    })
    reg.insert_trades(run_id, [{
        "trade_id": "t1", "ts_in": "2026-01-01T00:00:00Z", "px_in": 100.0,
        "side": "LONG",
    }])
    trades = reg.get_trades_for_run(run_id)
    assert trades[0]["signal_id"] is None
    assert trades[0]["ficha"] is None
