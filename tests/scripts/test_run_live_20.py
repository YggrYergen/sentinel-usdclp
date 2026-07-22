"""tests/scripts/test_run_live_20.py -- roster resolution for the guarded live
executor (`--configs live | shadow | live+shadow`) plus the supervisor's
SUPERVISOR_CONFIGS env/const plumbing (Addendum §1.2, D114).

Machine-2 runs `--configs shadow` ONLY (the uncorrected live-4 never arms
there). Machine-1 keeps the default `live` roster untouched. These are pure
argv/roster-resolution tests: all MT5 interaction is mocked, ZERO orders sent.
"""
from __future__ import annotations

import importlib
import random
from datetime import datetime, timezone

from scripts.live import run_live_20
from sentinel_engine.live import guard_cuenta
from sentinel_engine.strategies.live_configs_20 import (
    CONFIGS_GOLIVE,
    CONFIGS_GOLIVE_DEDUP,
    CONFIGS_LIVE,
    CONFIGS_LOCAL,
    CONFIGS_SHADOW,
    CONFIGS_TK,
    CONFIGS_TOMACHINE,
    CONFIGS_20,
    LIVE_ROSTER,
)

# Reuse the mock MT5 surface from the executor dry-run test module.
from tests.live.test_executor_dryrun import MockMT5


def _bars(n=400, seed=7):
    rnd = random.Random(seed)
    price = 2000.0
    base = int(datetime(2026, 6, 2, tzinfo=timezone.utc).timestamp())
    out = []
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        o = price - drift
        c = price
        hi = max(o, c) + abs(rnd.uniform(0.3, 1.2))
        lo = min(o, c) - abs(rnd.uniform(0.3, 1.2))
        out.append({"t": base + k * 120, "open": o, "high": hi, "low": lo, "close": c})
    return out


# --------------------------- --configs shadow ------------------------------
def test_configs_shadow_selects_only_fixed4(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "shadow"], mt5_module=mt5,
                              attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert f"{len(CONFIGS_SHADOW)} configs" in caplog.text
    for c in CONFIGS_SHADOW:
        assert f"[{c['id']}]" in caplog.text
    # the uncorrected live-4 must NOT be reconciled under `shadow`.
    for c in CONFIGS_LIVE:
        assert f"[{c['id']}]" not in caplog.text


def test_configs_shadow_case_insensitive(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "SHADOW"], mt5_module=mt5,
                              attach_checker=lambda: True)
    assert rc == 0
    assert f"{len(CONFIGS_SHADOW)} configs" in caplog.text


# ------------------------- --configs live+shadow ---------------------------
def test_configs_live_plus_shadow_selects_eight(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "live+shadow"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == []
    assert "8 configs" in caplog.text
    for c in CONFIGS_LIVE + CONFIGS_SHADOW:
        assert f"[{c['id']}]" in caplog.text


def test_configs_live_plus_shadow_magic_bands_disjoint():
    # resolve the roster the same way the executor does, assert no band overlap.
    combined = CONFIGS_LIVE + CONFIGS_SHADOW
    seen: set[int] = set()
    for c in combined:
        band = {c["magic"] + off for off in (0, 1, 2, 3)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band


# ------------------------- --configs live+tk -------------------------------
def test_configs_live_plus_tk_selects_five(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "live+tk"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert f"{len(CONFIGS_LIVE) + len(CONFIGS_TK)} configs" in caplog.text
    for c in CONFIGS_LIVE + CONFIGS_TK:
        assert f"[{c['id']}]" in caplog.text
    # the trader's new strategy is part of the supervised roster.
    assert "[TK-Momentum-5-8-short]" in caplog.text


def test_configs_live_plus_tk_magic_bands_disjoint():
    combined = CONFIGS_LIVE + CONFIGS_TK
    seen: set[int] = set()
    for c in combined:
        band = {c["magic"] + off for off in (0, 1, 2, 3)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band


# --------------------- --configs golive-dedup+tk ---------------------------
def test_configs_golive_dedup_plus_tk_selects_five(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        # force adaptive OFF here so this selection test never touches the real
        # spread store; the adaptive-default is covered separately below.
        rc = run_live_20.main(["--once", "--configs", "golive-dedup+tk",
                               "--no-adaptive-spread"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert f"{len(CONFIGS_GOLIVE_DEDUP) + len(CONFIGS_TK)} configs" in caplog.text
    for c in CONFIGS_GOLIVE_DEDUP + CONFIGS_TK:
        assert f"[{c['id']}]" in caplog.text
    assert "[TK-Momentum-5-8-short]" in caplog.text


def test_configs_golive_dedup_plus_tk_magic_bands_disjoint():
    combined = CONFIGS_GOLIVE_DEDUP + CONFIGS_TK
    seen: set[int] = set()
    for c in combined:
        band = {c["magic"] + off for off in (0, 1, 2, 3)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band


def test_configs_golive_dedup_plus_tk_adaptive_defaults_on(caplog, monkeypatch, tmp_path):
    # golive-dedup runs the adaptive running-min spread-gate ON; the combined
    # golive-dedup+tk roster must PRESERVE that (else the go-live behavior would
    # silently change). Redirect the spread store to a tmp dir so the live
    # data/ store is never touched by the test.
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "golive-dedup+tk"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert "adaptive_spread=ON" in caplog.text
    assert mt5.sent == []


# ----------------------- default `live` unchanged --------------------------
def test_configs_live_still_selects_only_the_four(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "live"], mt5_module=mt5,
                              attach_checker=lambda: True)
    assert rc == 0
    assert f"{len(LIVE_ROSTER)} configs" in caplog.text
    for c in CONFIGS_SHADOW:
        assert f"[{c['id']}]" not in caplog.text


# ----------------- supervisor SUPERVISOR_CONFIGS plumbing ------------------
def test_supervisor_default_argv_stays_live(monkeypatch):
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    import scripts.live.supervisor_live as sup
    sup = importlib.reload(sup)
    assert sup.SUPERVISOR_CONFIGS == "live"
    # default EXECUTOR_ARGV must still target the `live` roster (unchanged
    # behavior for the running machine-1 stack).
    assert sup.EXECUTOR_ARGV[-2:] == ["--configs", "live"]


def test_supervisor_env_overrides_configs(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_CONFIGS", "shadow")
    import scripts.live.supervisor_live as sup
    sup = importlib.reload(sup)
    assert sup.SUPERVISOR_CONFIGS == "shadow"
    assert sup.EXECUTOR_ARGV[-2:] == ["--configs", "shadow"]
    # still armed to the sanctioned DEMO account, still attach-only child.
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    assert "--arm" in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


def test_supervisor_env_live_plus_shadow(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_CONFIGS", "live+shadow")
    import scripts.live.supervisor_live as sup
    sup = importlib.reload(sup)
    assert sup.EXECUTOR_ARGV[-2:] == ["--configs", "live+shadow"]
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


def test_supervisor_env_golive_dedup_plus_tk(monkeypatch):
    # the auto-healing supervisor arms the golive-dedup roster + TK-Momentum in
    # one supervised, self-restarting executor (2026-07-21 user decision).
    monkeypatch.setenv("SUPERVISOR_CONFIGS", "golive-dedup+tk")
    import scripts.live.supervisor_live as sup
    sup = importlib.reload(sup)
    assert sup.EXECUTOR_ARGV[-2:] == ["--configs", "golive-dedup+tk"]
    assert "--arm" in sup.EXECUTOR_ARGV
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


def test_supervisor_env_live_plus_tk(monkeypatch):
    # the auto-healing supervisor can arm the `live` roster + TK-Momentum in one
    # supervised, self-restarting executor (2026-07-21).
    monkeypatch.setenv("SUPERVISOR_CONFIGS", "live+tk")
    import scripts.live.supervisor_live as sup
    sup = importlib.reload(sup)
    assert sup.EXECUTOR_ARGV[-2:] == ["--configs", "live+tk"]
    assert "--arm" in sup.EXECUTOR_ARGV
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


# --------------------------- --configs tomachine ----------------------------
def test_configs_tomachine_selects_four(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "tomachine"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert f"{len(CONFIGS_TOMACHINE)} configs" in caplog.text
    for c in CONFIGS_TOMACHINE:
        assert f"[{c['id']}]" in caplog.text
    # explicitly excluded from this roster (trader's machine-2 selection).
    assert "[V11-M2]" not in caplog.text
    assert "[TK-Momentum-5-8-short]" not in caplog.text
    # FIXED4 shadow configs removed from this roster (2026-07-22 shrink).
    for c in CONFIGS_SHADOW:
        assert f"[{c['id']}]" not in caplog.text


def test_configs_tomachine_case_insensitive(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "TOMACHINE"], mt5_module=mt5,
                              attach_checker=lambda: True)
    assert rc == 0
    assert f"{len(CONFIGS_TOMACHINE)} configs" in caplog.text


def test_configs_tomachine_magic_bands_disjoint():
    seen: set[int] = set()
    for c in CONFIGS_TOMACHINE:
        band = {c["magic"] + off for off in (0, 1, 2, 3)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band


def test_configs_tomachine_adaptive_spread_default_on(caplog, monkeypatch, tmp_path):
    # tomachine carries golive configs (S6-K2P0/S7-TPNONE/SuperTrend) -> the
    # adaptive running-min spread-gate must default ON here too.
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "tomachine"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert "adaptive_spread=ON" in caplog.text
    assert mt5.sent == []


def test_configs_tomachine_evaluates_tk_bw2_fix2atr_without_error(caplog):
    # M5 bars, enough warmup for TK-BW2's EMA/ATR/regime indicators.
    mt5 = MockMT5(_bars(n=600, seed=11))
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "tomachine",
                               "--no-adaptive-spread"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == []
    assert "[TK-BW2-fix2atr]" in caplog.text


# --------------------------- --configs local -------------------------------
def test_configs_local_selects_four(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "local",
                               "--no-adaptive-spread"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert f"{len(CONFIGS_LOCAL)} configs" in caplog.text
    for c in CONFIGS_LOCAL:
        assert f"[{c['id']}]" in caplog.text
    # excluded from the machine-1 local roster.
    assert "[V11-M2]" not in caplog.text
    for c in CONFIGS_SHADOW:
        assert f"[{c['id']}]" not in caplog.text


def test_configs_local_case_insensitive(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "LOCAL",
                               "--no-adaptive-spread"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert f"{len(CONFIGS_LOCAL)} configs" in caplog.text


def test_configs_local_magic_bands_disjoint():
    seen: set[int] = set()
    for c in CONFIGS_LOCAL:
        band = {c["magic"] + off for off in (0, 1, 2, 3)}
        assert seen.isdisjoint(band), f"magic band overlap at {c['id']}"
        seen |= band


# --------------- per-config volume reaches the order path ------------------
def test_per_config_volume_reaches_open_action():
    # A config WITH `volume=0.1` must produce OPEN actions carrying vol 0.1;
    # a config WITHOUT the key must fall back to the global `--volume`. We
    # drive reconcile_config directly (from an empty live book -> the sim's
    # desired fichas become OPENs) and read the OPEN action volumes.
    st_cfg = next(c for c in CONFIGS_LOCAL if c["id"] == "SuperTrend-p14x3-M15")
    assert st_cfg.get("volume") == 0.1

    mt5 = MockMT5(_bars(n=600, seed=5))
    # per-config override: cfg carries volume 0.1, global volume is 0.01.
    res, _bar_t = run_live_20.reconcile_config(
        mt5, st_cfg, window=600, volume=0.01, kill_switch=False,
        total_open_fichas=0)
    assert res is not None
    opens = [a for a in res.actions if a.kind == "OPEN"]
    assert opens, "SuperTrend always-in must desire an open position"
    for a in opens:
        assert a.volume == 0.1, "per-config volume 0.1 must reach the OPEN action"

    # a config WITHOUT a volume key falls back to the global --volume.
    bare = {k: v for k, v in st_cfg.items() if k != "volume"}
    assert "volume" not in bare
    res2, _ = run_live_20.reconcile_config(
        mt5, bare, window=600, volume=0.01, kill_switch=False,
        total_open_fichas=0)
    opens2 = [a for a in res2.actions if a.kind == "OPEN"]
    assert opens2
    for a in opens2:
        assert a.volume == 0.01, "no volume key -> global --volume (0.01) is used"


# ----------------------- immutability: armed rosters unchanged -------------
def _roster_fingerprint(configs):
    return [
        (c["id"], c["magic"], c.get("engine", "simular_variant"), tuple(sorted(c["kwargs"].items())))
        for c in configs
    ]


# Fingerprints of the rosters ALREADY ARMED on machine 1, captured as literal
# expected values (not re-derived from the live module) so a change to
# live_configs_20 that accidentally mutates one of these shared config dicts
# -- e.g. via the new tomachine/TK-BW2 construction -- is caught even though
# both "before" and "after" would otherwise come from the same import.
_EXPECTED_GOLIVE_DEDUP_TK_HEAD = [
    ("S6-K2P0", 724010, "simular_variant"),
    ("S7-TPNONE", 724020, "simular_variant"),
    ("V11-M2", 724060, "simular_variant"),
    ("SuperTrend-p14x3-M15", 724070, "supertrend_always_in"),
    ("TK-Momentum-5-8-short", 999999998, "tk_momentum"),
]


def test_armed_rosters_unchanged_by_tomachine_addition():
    # SNAPSHOT-ASSERT (mandatory, plan Task 2): the configs served by
    # "golive-dedup+tk", "golive-dedup", "shadow", "live" (ids, magics,
    # engine, kwargs) must be IDENTICAL to what they were before this
    # change -- protects the armed rosters running on machine 1 right now
    # from any accidental coupling introduced by the new tomachine roster /
    # TK-BW2-fix2atr config / executor dispatch branch.
    golive_dedup_tk = list(CONFIGS_GOLIVE_DEDUP) + list(CONFIGS_TK)
    fp_golive_dedup_tk = _roster_fingerprint(golive_dedup_tk)
    fp_golive_dedup = _roster_fingerprint(CONFIGS_GOLIVE_DEDUP)
    fp_shadow = _roster_fingerprint(CONFIGS_SHADOW)
    fp_live = _roster_fingerprint(CONFIGS_LIVE)

    assert [(cid, magic, engine) for cid, magic, engine, _kw in fp_golive_dedup_tk] \
        == _EXPECTED_GOLIVE_DEDUP_TK_HEAD
    assert [(cid, magic, engine) for cid, magic, engine, _kw in fp_golive_dedup] \
        == _EXPECTED_GOLIVE_DEDUP_TK_HEAD[:4]
    assert [cid for cid, _magic, _engine, _kw in fp_shadow] == [c["id"] for c in CONFIGS_SHADOW]
    assert {cid for cid, _magic, _engine, _kw in fp_live} == set(LIVE_ROSTER)

    # touching/constructing CONFIGS_TOMACHINE (already imported above at
    # module load, sharing the golive config dicts by reference per
    # `test_golive_config_objects_shared_not_copied_for_tomachine`) must not
    # have mutated any of the four armed rosters -- re-fingerprint and diff.
    assert _roster_fingerprint(list(CONFIGS_GOLIVE_DEDUP) + list(CONFIGS_TK)) == fp_golive_dedup_tk
    assert _roster_fingerprint(CONFIGS_GOLIVE_DEDUP) == fp_golive_dedup
    assert _roster_fingerprint(CONFIGS_SHADOW) == fp_shadow
    assert _roster_fingerprint(CONFIGS_LIVE) == fp_live


def test_local_roster_volume_did_not_leak_into_tomachine():
    # THE LEAK PROOF (plan hard invariant): the machine-1 `local` roster adds
    # 0.1/0.01 per-config volumes on independent COPIES. tomachine shares the
    # SAME S6/S7/SuperTrend dicts by reference -- their `volume` must stay
    # None (absent), so machine-2's lot remains the global --volume (0.01).
    for c in CONFIGS_TOMACHINE:
        assert c.get("volume") is None, \
            f"tomachine config {c['id']} volume leaked to {c.get('volume')}"
    # and the local roster DOES carry the intended per-config volumes.
    local_by_id = {c["id"]: c for c in CONFIGS_LOCAL}
    assert local_by_id["S6-K2P0"]["volume"] == 0.1
    assert local_by_id["S7-TPNONE"]["volume"] == 0.1
    assert local_by_id["SuperTrend-p14x3-M15"]["volume"] == 0.1
    assert local_by_id["TK-Momentum-5-8-short"]["volume"] == 0.01


def test_golive_config_objects_shared_not_copied_for_tomachine():
    # tomachine's 3 named golive configs must be the SAME dicts (by id/magic)
    # as CONFIGS_GOLIVE serves under `--configs golive` -- no parallel/forked
    # definition that could drift.
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    tomachine_by_id = {c["id"]: c for c in CONFIGS_TOMACHINE}
    for cid in ("S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"):
        assert tomachine_by_id[cid]["kwargs"] == golive_by_id[cid]["kwargs"]
        assert tomachine_by_id[cid]["magic"] == golive_by_id[cid]["magic"]


# ----------------- supervisor SUPERVISOR_CONFIGS plumbing (tomachine) ------
def test_supervisor_env_tomachine(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_CONFIGS", "tomachine")
    import scripts.live.supervisor_live as sup
    sup = importlib.reload(sup)
    assert sup.EXECUTOR_ARGV[-2:] == ["--configs", "tomachine"]
    assert "--arm" in sup.EXECUTOR_ARGV
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


def test_supervisor_env_local(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_CONFIGS", "local")
    import scripts.live.supervisor_live as sup
    sup = importlib.reload(sup)
    assert sup.EXECUTOR_ARGV[-2:] == ["--configs", "local"]
    assert "--arm" in sup.EXECUTOR_ARGV
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


# ---------------- TK-BW2-fix2atr: bounded replay window (perf) -------------
def test_tk_bw2_fix2atr_dispatch_caps_bars_fed_to_the_adapter(monkeypatch):
    # The tk_bw_v2 engine recomputes ALL indicators over `closed` on EVERY
    # step (O(n) per step) -- replaying the FULL --window (default 10000)
    # bars through it is O(n^2) and far too slow for a live poll cycle
    # (~15s). The dispatch must cap the bars it hands to
    # `tk_bw2_fix2atr_target` to a small, warmup-sufficient tail window,
    # independent of the (possibly much larger) `--window` used for MT5
    # fetch / other configs.
    from sentinel_engine.strategies.live_configs_20 import CONFIG_TK_BW2_FIX2ATR
    seen_lengths = []
    real_target = run_live_20.tk_bw2_fix2atr_target

    def _spy(bars, **kwargs):
        seen_lengths.append(len(bars))
        return real_target(bars, **kwargs)

    monkeypatch.setattr(run_live_20, "tk_bw2_fix2atr_target", _spy)
    mt5 = MockMT5(_bars(n=5000, seed=3))
    run_live_20.reconcile_config(
        mt5, CONFIG_TK_BW2_FIX2ATR, window=5000, volume=0.01,
        kill_switch=False, total_open_fichas=0)
    assert seen_lengths, "the spy must have been called"
    assert seen_lengths[0] <= run_live_20.TK_BW2_LIVE_BAR_CAP
    assert seen_lengths[0] < 5000, "the full 5000-bar window must NOT be replayed"
