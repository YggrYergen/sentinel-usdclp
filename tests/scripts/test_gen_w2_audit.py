"""tests/scripts/test_gen_w2_audit.py -- Task B4 (P31, honest program).

Fixture-scale tests for `scripts/report/gen_w2_audit.py` -- the W2/OOW2
forensic audit that upgrades the 17 `sim-report-emasar-oow2-*` runs from
REGIME_UNAUDITED to W2_AUDIT_PASS / W2_AUDIT_FAIL(reason).

NO real-DB dependency: the protocol functions run on synthetic trades/bars
and the validity-upgrade / idempotency / atomicity tests run on a temp
fixture DB built in tmp_path (never `data/research.db`).

Covers:
- Protocol maths (pure functions on synthetic trades+bars):
    * entry-improvement forensics vs entry-bar close (TEST-2 style),
    * same-bar exit census (look-ahead signature),
    * causal sanity verdict,
    * honest re-pricing verdict PASS/FAIL(reason).
- Honest-twin matching by full param signature (variant/tf/window),
  including the trail_atr_floor_k distinguisher that must NOT collapse
  distinct configs into one twin, and the live_fill_mode requirement.
- Validity upgrade: REGIME_UNAUDITED -> W2_AUDIT_PASS / W2_AUDIT_FAIL(...)
  via the SAME atomic single-transaction pattern as mark_validity, one
  audit row per change, ADDITIVE-ONLY, idempotent, crash-atomic.
- --dry-run writes nothing.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.report import gen_w2_audit as wa
from sentinel_engine.research.registry2 import ResearchRegistry


# ---------------------------------------------------------------------------
# Synthetic bar/trade builders
# ---------------------------------------------------------------------------

def _bar(t, o, h, l, c):
    return {"t": t, "open": o, "high": h, "low": l, "close": c, "volume": 1.0}


def _trade(ts_in, ts_out, px_in, px_out, side, exit_reason="EXIT_TRAIL"):
    return {
        "ts_in_epoch": ts_in, "ts_out_epoch": ts_out,
        "px_in": px_in, "px_out": px_out, "side": side,
        "exit_reason": exit_reason,
    }


# ---------------------------------------------------------------------------
# Protocol maths
# ---------------------------------------------------------------------------

def test_entry_improvement_zero_when_entering_at_close():
    """A causal-clean config enters at the signal bar's close: after we strip
    the fill spread, mean signed improvement vs bar close must be ~0."""
    bars = [_bar(100, 10.0, 11.0, 9.0, 10.5), _bar(200, 10.5, 12.0, 10.0, 11.0)]
    # LONG bought ASK = close+spread; SHORT sold BID = close.
    trades = [
        _trade(100, 200, 10.5 + wa.SPREAD, 11.0, "LONG"),
        _trade(200, 200, 11.0, 10.5, "SHORT"),
    ]
    res = wa.entry_improvement(trades, bars, spread=wa.SPREAD)
    assert res["n_matched"] == 2
    assert abs(res["mean_signed"]) < 1e-9


def test_entry_improvement_detects_favorable_lookahead():
    """If a LONG fills BELOW the bar close (bought cheaper than any causal
    engine could), that is positive (favorable) entry improvement -- the
    look-ahead signature TEST-2 hunts for."""
    bars = [_bar(100, 10.0, 11.0, 9.0, 10.5)]
    # raw entry (spread stripped) = 9.5, bar close = 10.5 -> +1.0 favorable.
    trades = [_trade(100, 200, 9.5 + wa.SPREAD, 11.0, "LONG")]
    res = wa.entry_improvement(trades, bars, spread=wa.SPREAD)
    assert res["n_matched"] == 1
    assert res["mean_signed"] == pytest.approx(1.0)


def test_entry_improvement_ignores_unmatched_bars():
    bars = [_bar(100, 10.0, 11.0, 9.0, 10.5)]
    trades = [_trade(999, 999, 10.0, 10.0, "LONG")]  # no bar at t=999
    res = wa.entry_improvement(trades, bars, spread=wa.SPREAD)
    assert res["n_matched"] == 0
    assert res["mean_signed"] == 0.0


def test_same_bar_exit_fraction():
    trades = [
        _trade(100, 100, 10.0, 10.5, "LONG"),   # same bar
        _trade(200, 300, 10.0, 10.5, "LONG"),   # different bar
        _trade(400, 400, 10.0, 10.5, "SHORT"),  # same bar
    ]
    res = wa.same_bar_exit_census(trades)
    assert res["n"] == 3
    assert res["n_same_bar"] == 2
    assert res["fraction"] == pytest.approx(2 / 3)


def test_causal_verdict_clean_and_dirty():
    assert wa.causal_verdict(0.0)["clean"] is True
    assert wa.causal_verdict(0.001)["clean"] is True   # within tolerance
    dirty = wa.causal_verdict(5.0)
    assert dirty["clean"] is False
    assert "non-causal" in dirty["note"].lower() or "improvement" in dirty["note"].lower()


def test_honest_verdict_pass_when_profit_survives():
    v = wa.honest_verdict(classic_net=90000.0, honest_net=8000.0)
    assert v["verdict"] == "W2_AUDIT_PASS"


def test_honest_verdict_fail_when_profit_collapses_to_loss():
    v = wa.honest_verdict(classic_net=111130.5, honest_net=-29030.7)
    assert v["verdict"] == "W2_AUDIT_FAIL"
    assert v["reason"]
    assert "honest" in v["reason"].lower()


def test_honest_verdict_fail_when_profit_evaporates_near_zero():
    """Classic +$120k -> honest +$50 is a fail: the money did not survive."""
    v = wa.honest_verdict(classic_net=120000.0, honest_net=50.0)
    assert v["verdict"] == "W2_AUDIT_FAIL"


# ---------------------------------------------------------------------------
# Honest-twin matching
# ---------------------------------------------------------------------------

def test_param_signature_ignores_freetext_and_mode_keys():
    a = {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01,
         "variant": "OOW ss-m5", "live_fill_mode": None}
    b = {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01,
         "variant": "HON ss-m5", "live_fill_mode": True}
    assert wa.param_signature(a) == wa.param_signature(b)


def test_param_signature_distinguishes_trail_atr_floor_k():
    """The s6 sweep adds trail_atr_floor_k; a config with a nonzero floor is
    NOT the same config as one without it -- they must NOT collapse."""
    base = {"init_sl_range_k": 3.0, "ac_modulate_factor": 0.25}
    floored = {**base, "trail_atr_floor_k": 2.0}
    assert wa.param_signature(base) != wa.param_signature(floored)


def test_match_honest_twin_links_exact_signature_live_fill_only():
    oow_params = {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01}
    honest_rows = [
        # right signature but NOT a live-fill run -> ignored.
        {"run_id": "hon-classic", "tf": "M5",
         "params": {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01}},
        # right signature + live_fill -> the twin.
        {"run_id": "hon-lf", "tf": "M5", "net": -5589.9,
         "params": {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01,
                    "live_fill_mode": True}},
        # wrong tf.
        {"run_id": "hon-wrongtf", "tf": "M15", "net": 100.0,
         "params": {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01,
                    "live_fill_mode": True}},
    ]
    twin = wa.match_honest_twin(oow_params, "M5", honest_rows)
    assert twin is not None
    assert twin["run_id"] == "hon-lf"


def test_match_honest_twin_none_when_no_live_fill_signature():
    oow_params = {"init_sl_range_k": 2.5, "direction_mask": "supertrend"}
    honest_rows = [
        {"run_id": "hon-other", "tf": "M5", "net": 1.0,
         "params": {"init_sl_range_k": 2.5, "live_fill_mode": True}},
    ]
    assert wa.match_honest_twin(oow_params, "M5", honest_rows) is None


def test_match_honest_twin_ambiguous_ties_are_deterministic():
    """When several live-fill twins share the exact signature (identical
    config re-run under different sweep labels), pick deterministically by
    lowest run_id -- and they must all carry the same net."""
    oow_params = {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01}
    honest_rows = [
        {"run_id": "hon-b", "tf": "M5", "net": -5589.9,
         "params": {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01,
                    "live_fill_mode": True}},
        {"run_id": "hon-a", "tf": "M5", "net": -5589.9,
         "params": {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01,
                    "live_fill_mode": True}},
    ]
    twin = wa.match_honest_twin(oow_params, "M5", honest_rows)
    assert twin["run_id"] == "hon-a"


# ---------------------------------------------------------------------------
# Validity upgrade on a fixture DB
# ---------------------------------------------------------------------------

def _mk_run(run_id, variant_id, net, params, fidelity="screening",
            periodo_desde="2026-03-02", validity=None):
    return {
        "run_id": run_id, "variant_id": variant_id,
        "engine": "sentinel-sim", "fidelity": fidelity,
        "trades": 100, "net": net, "pf": 1.2, "wr": 60.0,
        "periodo_desde": periodo_desde, "periodo_hasta": "2026-04-03",
        "metrics_json": json.dumps({"params": params}, ensure_ascii=False),
        "fecha_corrida": "2026-07-19", "source_file": "tests/fixture",
    }


@pytest.fixture()
def fixture_db(tmp_path: Path) -> Path:
    """Mini registry with two oow2 rows (one that should PASS, one FAIL) and
    their honest live-fill twins, plus a control oow2 row that is NOT marked
    REGIME_UNAUDITED (so the audit leaves it alone)."""
    db = tmp_path / "research_fixture.db"
    reg = ResearchRegistry(db)
    sid = reg.upsert_strategy("EMASAR", "emasar", "python-sim")
    for vid in ("EMS_XAU_OOW_SS_M5_M5_W2", "EMS_XAU_OOW_CTRL_M2_W2",
                "EMS_XAU_OOW_V06B_M15_M15_W2", "HON_SS_M5", "HON_V06B_M15"):
        reg.upsert_variant(sid, vid, {}, "M5", "XAUUSD", None)

    ss_params = {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.01,
                 "sar_adaptive": True, "reentry_max": 2}
    v06b_params = {"init_sl_range_k": 2.5, "ac_modulate_factor": 0.25}

    # oow2 rows, already marked REGIME_UNAUDITED (the state B1 left them in).
    reg.insert_run(_mk_run("sim-report-emasar-oow2-ss-m5",
                           "EMS_XAU_OOW_SS_M5_M5_W2", 122599.5, ss_params))
    reg.insert_run(_mk_run("sim-report-emasar-oow2-v06b-m15",
                           "EMS_XAU_OOW_V06B_M15_M15_W2", 89583.0, v06b_params))
    _mark_regime(db, "sim-report-emasar-oow2-ss-m5")
    _mark_regime(db, "sim-report-emasar-oow2-v06b-m15")

    # honest live-fill twins on W2: ss-m5 collapses to a loss (FAIL);
    # v06b-m15 stays profitable (PASS). The twin is identified by its params
    # (live_fill_mode=True + matching signature + W2 window), NOT its fidelity
    # label, so 'screening' (a valid CHECK enum value) is fine for the fixture.
    reg.insert_run(_mk_run(
        "honest-hon-ss-m5-m5-w2", "HON_SS_M5", -5589.9,
        {**ss_params, "live_fill_mode": True}, fidelity="screening"))
    reg.insert_run(_mk_run(
        "honest-hon-v06b-m15-m15-w2", "HON_V06B_M15", 7744.5,
        {**v06b_params, "live_fill_mode": True}, fidelity="screening"))
    return db


def _mark_regime(db: Path, run_id: str) -> None:
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("UPDATE run SET validity='REGIME_UNAUDITED' WHERE run_id=?",
                     (run_id,))
        conn.commit()
    finally:
        conn.close()


def _validity(db: Path) -> dict:
    conn = sqlite3.connect(str(db))
    try:
        return dict(conn.execute("SELECT run_id, validity FROM run"))
    finally:
        conn.close()


def _audit_rows(db: Path) -> list:
    conn = sqlite3.connect(str(db))
    try:
        return [
            (actor, accion, json.loads(dj))
            for actor, accion, dj in conn.execute(
                "SELECT actor, accion, detalle_json FROM audit_log "
                "WHERE accion='validity-mark' ORDER BY id")
        ]
    finally:
        conn.close()


def _snapshot_sans_validity(db: Path) -> list:
    conn = sqlite3.connect(str(db))
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(run)")
                if r[1] != "validity"]
        sel = ", ".join(f'"{c}"' for c in cols)
        return conn.execute(f"SELECT rowid, {sel} FROM run ORDER BY rowid").fetchall()
    finally:
        conn.close()


def test_audit_upgrades_pass_and_fail(fixture_db: Path):
    verdicts = wa.audit_w2(fixture_db, dry_run=False)
    v = _validity(fixture_db)

    # v06b-m15 survives honest fill (+$7.7k) -> PASS.
    assert v["sim-report-emasar-oow2-v06b-m15"] == "W2_AUDIT_PASS"
    # ss-m5 collapses to a loss under honest fill -> FAIL(reason).
    assert v["sim-report-emasar-oow2-ss-m5"].startswith("W2_AUDIT_FAIL")

    by_id = {d["run_id"]: d for d in verdicts}
    assert by_id["sim-report-emasar-oow2-ss-m5"]["twin_run_id"] == "honest-hon-ss-m5-m5-w2"
    assert by_id["sim-report-emasar-oow2-ss-m5"]["linked"] is True


def test_audit_writes_one_audit_row_per_change(fixture_db: Path):
    wa.audit_w2(fixture_db, dry_run=False)
    rows = _audit_rows(fixture_db)
    assert len(rows) == 2  # exactly the two oow2 REGIME_UNAUDITED rows
    marked = _validity(fixture_db)
    for actor, accion, detalle in rows:
        assert actor == "honest-program"
        assert accion == "validity-mark"
        assert detalle["run_id"] in marked
        assert marked[detalle["run_id"]] == detalle["label"]
        assert detalle["label"].startswith("W2_AUDIT_")
        assert detalle["reason"]


def test_audit_additive_only_other_columns_untouched(fixture_db: Path):
    before = _snapshot_sans_validity(fixture_db)
    wa.audit_w2(fixture_db, dry_run=False)
    after = _snapshot_sans_validity(fixture_db)
    assert before == after


def test_audit_idempotent(fixture_db: Path):
    wa.audit_w2(fixture_db, dry_run=False)
    v1 = _validity(fixture_db)
    a1 = _audit_rows(fixture_db)
    v2 = wa.audit_w2(fixture_db, dry_run=False)
    # nothing new upgraded (all already W2_AUDIT_*, no longer REGIME_UNAUDITED).
    assert all(not r["upgraded"] for r in v2)
    assert _validity(fixture_db) == v1
    assert _audit_rows(fixture_db) == a1


def test_audit_only_touches_regime_unaudited_rows(fixture_db: Path):
    """A row whose validity is NOT REGIME_UNAUDITED is never re-marked, even
    if it matches the oow2 prefix."""
    # Pre-set one oow2 row to a foreign label -> must be left alone.
    conn = sqlite3.connect(str(fixture_db))
    conn.execute("UPDATE run SET validity='SOME_OTHER_LABEL' "
                 "WHERE run_id='sim-report-emasar-oow2-ss-m5'")
    conn.commit(); conn.close()

    wa.audit_w2(fixture_db, dry_run=False)
    v = _validity(fixture_db)
    assert v["sim-report-emasar-oow2-ss-m5"] == "SOME_OTHER_LABEL"


def test_audit_atomic_under_crash(fixture_db: Path, monkeypatch):
    calls = {"n": 0}
    real = ResearchRegistry.audit_on

    def flaky(self, conn, actor, accion, detalle=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated crash mid-batch")
        return real(self, conn, actor, accion, detalle)

    monkeypatch.setattr(ResearchRegistry, "audit_on", flaky)
    with pytest.raises(RuntimeError):
        wa.audit_w2(fixture_db, dry_run=False)

    # Whole batch rolled back: still REGIME_UNAUDITED, no audit rows.
    v = _validity(fixture_db)
    assert v["sim-report-emasar-oow2-ss-m5"] == "REGIME_UNAUDITED"
    assert v["sim-report-emasar-oow2-v06b-m15"] == "REGIME_UNAUDITED"
    assert _audit_rows(fixture_db) == []

    monkeypatch.setattr(ResearchRegistry, "audit_on", real)
    wa.audit_w2(fixture_db, dry_run=False)
    assert len(_audit_rows(fixture_db)) == 2


def _add_trade(db: Path, run_id: str, ts_in="2026.03.02 00:15:00",
               ts_out="2026.03.02 00:20:00") -> None:
    """Give a fixture run a persisted trade so the causal entry-bar join is
    ATTEMPTED for it (runs with zero trades are vacuously clean)."""
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "INSERT INTO trade(trade_id, run_id, origin, ts_in, ts_out, "
            "px_in, px_out, side, exit_reason, pnl) "
            "VALUES (?, ?, 'strategy', ?, ?, 100.0, 101.0, 'LONG', "
            "'EXIT_TRAIL', 10.0)",
            (f"{run_id}-t1", run_id, ts_in, ts_out),
        )
        conn.commit()
    finally:
        conn.close()


def _raise(exc):
    raise exc


def test_bars_load_failure_is_unverified_and_blocks_pass(
        fixture_db: Path, monkeypatch):
    """B4 review fix 1: a swallowed bars-load failure must NEVER default to a
    'clean' causal verdict. A PASS-leaning cell with UNVERIFIED causal becomes
    ENV-ERROR (PASS blocked); a FAIL-leaning cell still FAILs on the
    honest-net rule with the reason noting causal=UNVERIFIED. Apply aborts,
    zero writes."""
    _add_trade(fixture_db, "sim-report-emasar-oow2-v06b-m15")  # PASS-leaning
    _add_trade(fixture_db, "sim-report-emasar-oow2-ss-m5")     # FAIL-leaning
    monkeypatch.setattr(wa, "_bars_for_cell",
                        lambda tf: _raise(RuntimeError("lake unavailable")))

    verdicts = wa.audit_w2(fixture_db, dry_run=True)
    by_id = {v["run_id"]: v for v in verdicts}

    v_pass = by_id["sim-report-emasar-oow2-v06b-m15"]
    assert v_pass["causal_status"] == "UNVERIFIED"
    assert v_pass["verdict"] == "ENV-ERROR"      # PASS blocked
    assert v_pass["label"] is None               # never persistable
    assert "causal" in v_pass["reason"].lower()

    v_fail = by_id["sim-report-emasar-oow2-ss-m5"]
    assert v_fail["causal_status"] == "UNVERIFIED"
    assert v_fail["verdict"] == "W2_AUDIT_FAIL"   # still fails on honest-net
    assert "UNVERIFIED" in v_fail["reason"]

    # Apply must ABORT before writing anything -- even the resolvable cell.
    with pytest.raises(wa.AuditEnvError):
        wa.audit_w2(fixture_db, dry_run=False)
    v = _validity(fixture_db)
    assert v["sim-report-emasar-oow2-v06b-m15"] == "REGIME_UNAUDITED"
    assert v["sim-report-emasar-oow2-ss-m5"] == "REGIME_UNAUDITED"
    assert _audit_rows(fixture_db) == []


def test_zero_joined_bars_is_unverified_not_clean(fixture_db: Path, monkeypatch):
    """Bars 'load' but join nothing (n_matched==0) while the run HAS trades ->
    UNVERIFIED, never clean, and PASS is blocked (ENV-ERROR)."""
    _add_trade(fixture_db, "sim-report-emasar-oow2-v06b-m15")
    monkeypatch.setattr(wa, "_bars_for_cell", lambda tf: [])
    verdicts = wa.audit_w2(fixture_db, dry_run=True)
    v = {x["run_id"]: x for x in verdicts}["sim-report-emasar-oow2-v06b-m15"]
    assert v["n_matched"] == 0
    assert v["causal_status"] == "UNVERIFIED"
    assert v["verdict"] == "ENV-ERROR"


def test_fresh_sim_failure_aborts_apply_with_zero_writes(
        fixture_db: Path, monkeypatch):
    """B4 review fix 2: a FRESH cell whose re-simulation raises must NOT be
    persisted as a forensic-sounding FAIL. Dry-run shows ENV-ERROR (label
    None); apply aborts before ANY write (all cells stay REGIME_UNAUDITED, no
    audit rows)."""
    reg = ResearchRegistry(fixture_db)
    sid = reg.upsert_strategy("EMASAR", "emasar", "python-sim")
    reg.upsert_variant(sid, "EMS_XAU_OOW_V10_M5_M5_W2", {}, "M5", "XAUUSD", None)
    reg.insert_run(_mk_run(
        "sim-report-emasar-oow2-v10-m5", "EMS_XAU_OOW_V10_M5_M5_W2", 68310.6,
        {"init_sl_range_k": 6.0, "ac_modulate_factor": 0.25,
         "direction_mask": "supertrend_m15_atr14_mult3.0_prev_closed_bar"}))
    _mark_regime(fixture_db, "sim-report-emasar-oow2-v10-m5")
    monkeypatch.setattr(
        wa, "_fresh_honest_net",
        lambda tf, params: _raise(RuntimeError("pyarrow exploded")))

    # Dry-run: the env failure is visible as ENV-ERROR, never a FAIL verdict.
    verdicts = wa.audit_w2(fixture_db, dry_run=True)
    v = {x["run_id"]: x for x in verdicts}["sim-report-emasar-oow2-v10-m5"]
    assert v["honest_net"] is None
    assert v["fresh"] is True
    assert v["verdict"] == "ENV-ERROR"
    assert v["label"] is None  # never a persistable label

    # Apply: aborts naming the cell; ZERO writes anywhere.
    with pytest.raises(wa.AuditEnvError, match="v10-m5"):
        wa.audit_w2(fixture_db, dry_run=False)
    vmap = _validity(fixture_db)
    assert vmap["sim-report-emasar-oow2-v10-m5"] == "REGIME_UNAUDITED"
    assert vmap["sim-report-emasar-oow2-ss-m5"] == "REGIME_UNAUDITED"
    assert vmap["sim-report-emasar-oow2-v06b-m15"] == "REGIME_UNAUDITED"
    assert _audit_rows(fixture_db) == []


def test_dry_run_writes_nothing(fixture_db: Path):
    before = _snapshot_sans_validity(fixture_db)
    verdicts = wa.audit_w2(fixture_db, dry_run=True)
    # dry-run still computes verdicts...
    assert {r["verdict"] for r in verdicts} == {"W2_AUDIT_PASS", "W2_AUDIT_FAIL"}
    # ...but writes nothing.
    assert _validity(fixture_db) == {
        "sim-report-emasar-oow2-ss-m5": "REGIME_UNAUDITED",
        "sim-report-emasar-oow2-v06b-m15": "REGIME_UNAUDITED",
        "honest-hon-ss-m5-m5-w2": None,
        "honest-hon-v06b-m15-m15-w2": None,
    }
    assert _audit_rows(fixture_db) == []
    assert _snapshot_sans_validity(fixture_db) == before
