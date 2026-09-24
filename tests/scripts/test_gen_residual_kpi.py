"""tests/scripts/test_gen_residual_kpi.py -- P65 (Wave 6 governance) sim-vs-live
NET RESIDUAL tracked-KPI tests.

The KPI parses the LIVE side from the run_live_20 audit-log telemetry (per-config
SAME_BAR by-design cost, SL_CLAMP gap, and realized-fill counts) and pairs it
against the sim-expected net for the same configs/window from the honest
pipeline. The residual is decomposed so a residual is ATTRIBUTABLE (SAME_BAR +
SL_CLAMP broken out), not mysterious.

These tests exercise the PURE, injectable core (`parse_audit_telemetry`,
`build_residual_row`, `residual_report`) on a synthetic audit-log fixture -- no
MT5, no live daemon, no lake, no network. The sim-expected net is injected, so
these tests never re-run the strategy engine (that path is covered by the
existing gen_livefill_bound / parity tests it reuses).
"""
from __future__ import annotations

import json

import pytest

from scripts.report.gen_residual_kpi import (
    build_residual_row,
    parse_audit_telemetry,
    residual_report,
    INSUFFICIENT_SAMPLE,
    DEFAULT_MIN_LIVE_FILLS,
)


# --------------------------------------------------------------------------
# Synthetic audit-log fixture: mirrors the real run_live_20.audit.log line
# formats exactly (the cumulative by-design lines + SENT OPEN/CLOSE fills).
# --------------------------------------------------------------------------
SAME_BAR_LINE = (
    "2026-07-20 07:18:06,739 INFO SAME_BAR cumulative by-design cost (this run): "
    "total=$-205.7864 | V11-M2=$-73.6500, V11-M2-F=$13.3636, V13-M2=$-80.7300, "
    "V13-M2-F=$23.7698, V15-M15=$-45.4300, V15-M15-F=$5.3149, V15-M2=$-72.5300, "
    "V15-M2-F=$24.1053"
)
SL_CLAMP_LINE = (
    "2026-07-20 07:17:33,469 INFO SL_CLAMP cumulative gap (this run): "
    "total=$69.8499 | V11-M2-F=$16.8467, V13-M2=$1.4200, V13-M2-F=$29.6460, "
    "V15-M15-F=$0.4067, V15-M2-F=$21.5305"
)
SENT_OPEN_LINES = [
    "2026-07-14 01:03:36,125 INFO   [SENT OPEN] V11-M2 F1 magic=720201 -> retcode=10009",
    "2026-07-14 01:03:36,125 INFO   [SENT OPEN] V11-M2 F2 magic=720202 -> retcode=10009",
    "2026-07-14 01:03:36,141 INFO   [SENT OPEN] V13-M2 F1 magic=720161 -> retcode=10009",
]
SENT_CLOSE_LINES = [
    "2026-07-14 01:18:16,902 INFO   [SENT CLOSE] ticket=55110832 -> retcode=10009",
]
CONNECT_LINE = (
    "2026-07-14 09:58:54,795 INFO connected + guard OK: DEMO login 2883015767 "
    "(dry_run=False, 6 configs, window=10000)"
)


def _fixture_log(tmp_path, extra_lines=None):
    lines = [CONNECT_LINE, SL_CLAMP_LINE, SAME_BAR_LINE, *SENT_OPEN_LINES, *SENT_CLOSE_LINES]
    if extra_lines:
        lines += extra_lines
    p = tmp_path / "audit.log"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# parse_audit_telemetry
# --------------------------------------------------------------------------

def test_parse_same_bar_and_sl_clamp_per_config(tmp_path):
    tel = parse_audit_telemetry(_fixture_log(tmp_path))
    # last cumulative line wins per config (the running total at run-end)
    assert tel["V11-M2"]["same_bar_cost"] == pytest.approx(-73.65)
    assert tel["V13-M2"]["same_bar_cost"] == pytest.approx(-80.73)
    assert tel["V15-M2"]["same_bar_cost"] == pytest.approx(-72.53)
    assert tel["V15-M15"]["same_bar_cost"] == pytest.approx(-45.43)
    # -F fixed siblings parsed independently
    assert tel["V11-M2-F"]["same_bar_cost"] == pytest.approx(13.3636)
    # SL_CLAMP gaps
    assert tel["V13-M2"]["sl_clamp_gap"] == pytest.approx(1.42)
    assert tel["V15-M2-F"]["sl_clamp_gap"] == pytest.approx(21.5305)
    # a config with SAME_BAR but no SL_CLAMP line -> gap defaults to 0.0
    assert tel["V11-M2"]["sl_clamp_gap"] == pytest.approx(0.0)


def test_parse_fill_counts(tmp_path):
    tel = parse_audit_telemetry(_fixture_log(tmp_path))
    # V11-M2 had 2 SENT OPEN fills; V13-M2 had 1
    assert tel["V11-M2"]["n_opens"] == 2
    assert tel["V13-M2"]["n_opens"] == 1
    # SENT CLOSE lines are ticket-only (no config id) -> counted at total level
    assert tel["_total"]["n_closes"] == 1


def test_parse_last_cumulative_wins(tmp_path):
    # an EARLIER cumulative line with different values must be superseded by the
    # LATER one (running total at run-end is authoritative).
    early = (
        "2026-07-20 06:00:00,000 INFO SAME_BAR cumulative by-design cost (this run): "
        "total=$-10.0000 | V11-M2=$-10.0000"
    )
    tel = parse_audit_telemetry(_fixture_log(tmp_path, extra_lines=[]))
    # baseline from fixture
    assert tel["V11-M2"]["same_bar_cost"] == pytest.approx(-73.65)
    # now prepend an earlier line -> still the fixture's later line wins
    p = tmp_path / "audit2.log"
    p.write_text(early + "\n" + SAME_BAR_LINE + "\n", encoding="utf-8")
    tel2 = parse_audit_telemetry(p)
    assert tel2["V11-M2"]["same_bar_cost"] == pytest.approx(-73.65)


def test_parse_empty_log(tmp_path):
    p = tmp_path / "empty.log"
    p.write_text("", encoding="utf-8")
    tel = parse_audit_telemetry(p)
    assert tel == {"_total": {"n_opens": 0, "n_closes": 0}}


# --------------------------------------------------------------------------
# build_residual_row -- the residual math + by-design breakout
# --------------------------------------------------------------------------

def test_residual_math_and_breakout_sums(tmp_path):
    tel = parse_audit_telemetry(_fixture_log(tmp_path))
    row = build_residual_row(
        "V13-M2", tel["V13-M2"], sim_expected_net=-50.0, live_realized_net=-140.0,
        min_live_fills=1,
    )
    # residual = live - sim
    assert row["residual"] == pytest.approx(-140.0 - (-50.0))
    # by-design components broken out
    assert row["same_bar_cost"] == pytest.approx(-80.73)
    assert row["sl_clamp_gap"] == pytest.approx(1.42)
    # attributable = same_bar + sl_clamp; unexplained = residual - attributable
    assert row["by_design_total"] == pytest.approx(-80.73 + 1.42)
    assert row["unexplained"] == pytest.approx(row["residual"] - row["by_design_total"])
    assert row["status"] == "OK"


def test_insufficient_live_sample_when_realized_net_absent(tmp_path):
    tel = parse_audit_telemetry(_fixture_log(tmp_path))
    # live_realized_net=None (audit log carries NO realized P&L) -> INSUFFICIENT
    row = build_residual_row(
        "V13-M2", tel["V13-M2"], sim_expected_net=-50.0, live_realized_net=None,
        min_live_fills=1,
    )
    assert row["status"] == INSUFFICIENT_SAMPLE
    assert row["residual"] is None
    # by-design components are STILL reported honestly (they ARE observable)
    assert row["same_bar_cost"] == pytest.approx(-80.73)
    assert row["sl_clamp_gap"] == pytest.approx(1.42)
    assert row["unexplained"] is None


def test_insufficient_live_sample_when_fills_below_threshold(tmp_path):
    tel = parse_audit_telemetry(_fixture_log(tmp_path))
    # V13-M2 has 1 open; require 5 -> insufficient even with a realized net
    row = build_residual_row(
        "V13-M2", tel["V13-M2"], sim_expected_net=-50.0, live_realized_net=-140.0,
        min_live_fills=5,
    )
    assert row["status"] == INSUFFICIENT_SAMPLE
    assert row["residual"] is None
    assert row["reason"] and "fills" in row["reason"].lower()


# --------------------------------------------------------------------------
# residual_report -- top-level artifact assembly
# --------------------------------------------------------------------------

def test_residual_report_totals_and_determinism(tmp_path):
    tel = parse_audit_telemetry(_fixture_log(tmp_path))
    sim_nets = {"V11-M2": -20.0, "V13-M2": -50.0, "V15-M2": -30.0, "V15-M15": -10.0}
    live_nets = {"V11-M2": -90.0, "V13-M2": -140.0, "V15-M2": -100.0, "V15-M15": -55.0}
    rep1 = residual_report(tel, sim_nets, live_nets, min_live_fills=1)
    rep2 = residual_report(tel, sim_nets, live_nets, min_live_fills=1)
    # determinism: identical inputs -> byte-identical JSON
    assert json.dumps(rep1, sort_keys=True) == json.dumps(rep2, sort_keys=True)
    # total residual = sum of per-config OK residuals
    ok_rows = [r for r in rep1["configs"] if r["status"] == "OK"]
    assert rep1["total"]["residual"] == pytest.approx(sum(r["residual"] for r in ok_rows))
    assert rep1["total"]["same_bar_cost"] == pytest.approx(
        sum(r["same_bar_cost"] for r in ok_rows))


def test_residual_report_insufficient_when_no_live_net(tmp_path):
    tel = parse_audit_telemetry(_fixture_log(tmp_path))
    sim_nets = {"V11-M2": -20.0, "V13-M2": -50.0}
    # no live realized nets available at all -> every row insufficient, total says so
    rep = residual_report(tel, sim_nets, live_realized_nets=None, min_live_fills=1)
    assert rep["total"]["status"] == INSUFFICIENT_SAMPLE
    assert all(r["status"] == INSUFFICIENT_SAMPLE for r in rep["configs"])
    # but by-design components still surface at the total level
    assert rep["total"]["same_bar_cost"] is not None


def test_default_min_live_fills_is_conservative():
    # governance honesty: the default fill threshold must be > 1 so a single
    # live fill does not masquerade as a meaningful sample.
    assert DEFAULT_MIN_LIVE_FILLS > 1


# --------------------------------------------------------------------------
# governance-only: the KPI must NOT mutate any score/DSR.
# --------------------------------------------------------------------------

def test_no_scoring_or_dsr_mutation(tmp_path):
    import sentinel_engine.opt.registry as reg
    before = (reg.AUDIT_REQUIRED_NULL_MAX_MULT,)
    tel = parse_audit_telemetry(_fixture_log(tmp_path))
    residual_report(tel, {"V11-M2": -20.0}, {"V11-M2": -90.0}, min_live_fills=1)
    after = (reg.AUDIT_REQUIRED_NULL_MAX_MULT,)
    assert before == after
    # the residual KPI module must not import or call the DSR/scoring mutators
    import scripts.report.gen_residual_kpi as kpi
    src = kpi.__file__
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    assert "insert_run" not in text  # does not write runs/scores
    assert "deflated_sharpe_ratio" not in text  # does not touch DSR
