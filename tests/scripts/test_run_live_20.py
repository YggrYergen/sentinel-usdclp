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
from datetime import datetime, time as dtime, timezone

import pytest

from scripts.live import run_live_20
from sentinel_engine.live.reconciler import Action
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

# Reuse the mock MT5 surface (and its tick/symbol-info/position doubles) from
# the executor dry-run test module.
from tests.live.test_executor_dryrun import MockMT5, _Pos, _SymbolInfo, _Tick


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
# ROBUSTNESS (2026-07-27): these tests assert WHICH roster reaches the executor
# argv. They used to do it with `EXECUTOR_ARGV[-2:]`, which silently depended on
# `--configs` being the LAST flag -- false as soon as the machine also exports
# SUPERVISOR_MAX_SPREAD_OPEN / SUPERVISOR_BLOCKED_OPEN_WINDOW (this machine
# does). They now clear every SUPERVISOR_* argv var and assert positionally on
# the value that follows `--configs`, which is what they always meant.
_SUPERVISOR_ARGV_ENV_VARS = ("SUPERVISOR_CONFIGS", "SUPERVISOR_MAX_SPREAD_OPEN",
                             "SUPERVISOR_BLOCKED_OPEN_WINDOW")


def _reload_supervisor_with_clean_env(monkeypatch, configs=None):
    """Reload supervisor_live with a KNOWN-clean SUPERVISOR_* environment
    (optionally with SUPERVISOR_CONFIGS set to `configs`) and return it."""
    for var in _SUPERVISOR_ARGV_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    if configs is not None:
        monkeypatch.setenv("SUPERVISOR_CONFIGS", configs)
    import scripts.live.supervisor_live as sup
    return importlib.reload(sup)


def _assert_configs_is(sup, expected):
    argv = sup.EXECUTOR_ARGV
    assert argv[argv.index("--configs") + 1] == expected


def test_supervisor_default_argv_stays_live(monkeypatch):
    sup = _reload_supervisor_with_clean_env(monkeypatch)
    assert sup.SUPERVISOR_CONFIGS == "live"
    # default EXECUTOR_ARGV must still target the `live` roster (unchanged
    # behavior for the running machine-1 stack).
    _assert_configs_is(sup, "live")
    monkeypatch.undo()
    importlib.reload(sup)


def test_supervisor_env_overrides_configs(monkeypatch):
    sup = _reload_supervisor_with_clean_env(monkeypatch, "shadow")
    assert sup.SUPERVISOR_CONFIGS == "shadow"
    _assert_configs_is(sup, "shadow")
    # still armed to the sanctioned DEMO account, still attach-only child.
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    assert "--arm" in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


def test_supervisor_env_live_plus_shadow(monkeypatch):
    sup = _reload_supervisor_with_clean_env(monkeypatch, "live+shadow")
    _assert_configs_is(sup, "live+shadow")
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


def test_supervisor_env_golive_dedup_plus_tk(monkeypatch):
    # the auto-healing supervisor arms the golive-dedup roster + TK-Momentum in
    # one supervised, self-restarting executor (2026-07-21 user decision).
    sup = _reload_supervisor_with_clean_env(monkeypatch, "golive-dedup+tk")
    _assert_configs_is(sup, "golive-dedup+tk")
    assert "--arm" in sup.EXECUTOR_ARGV
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


def test_supervisor_env_live_plus_tk(monkeypatch):
    # the auto-healing supervisor can arm the `live` roster + TK-Momentum in one
    # supervised, self-restarting executor (2026-07-21).
    sup = _reload_supervisor_with_clean_env(monkeypatch, "live+tk")
    _assert_configs_is(sup, "live+tk")
    assert "--arm" in sup.EXECUTOR_ARGV
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


# --------------------------- --configs tomachine ----------------------------
def test_configs_tomachine_selects_two(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "tomachine"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert f"{len(CONFIGS_TOMACHINE)} configs" in caplog.text
    for c in CONFIGS_TOMACHINE:
        assert f"[{c['id']}]" in caplog.text
    # explicitly excluded from this roster (owner's machine-2 selection).
    assert "[V11-M2]" not in caplog.text
    assert "[TK-Momentum-5-8-short]" not in caplog.text
    # dropped by the owner's 2026-07-27 selection (S6 + SuperTrend only).
    assert "[S7-TPNONE]" not in caplog.text
    assert "[TK-BW2-fix2atr]" not in caplog.text
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
    # tomachine carries golive configs (S6-K2P0/SuperTrend) -> the adaptive
    # running-min spread-gate must default ON here too.
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "tomachine"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert "adaptive_spread=ON" in caplog.text
    assert mt5.sent == []


# REMOVED 2026-07-27: `test_configs_tomachine_evaluates_tk_bw2_fix2atr_
# without_error` asserted that a `--configs tomachine` sweep evaluated
# TK-BW2-fix2atr. TK-BW2-fix2atr LEFT the tomachine roster on 2026-07-27
# (owner's selection: S6-K2P0 + SuperTrend only), so no armed roster carries
# it and the assertion no longer describes any real behaviour. The config
# itself is still defined in live_configs_20 and keeps its own coverage in
# tests/strategies/test_live_configs_tomachine.py, plus the executor's
# TK-BW2 dispatch path is still tested directly by
# `test_tk_bw2_fix2atr_dispatch_caps_bars_fed_to_the_adapter` below.


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
    # module load; it deep-COPIES the golive config dicts per
    # `test_tomachine_configs_are_copies_matching_golive_except_active_fichas`)
    # must not have mutated any of the four armed rosters -- re-fingerprint
    # and diff.
    assert _roster_fingerprint(list(CONFIGS_GOLIVE_DEDUP) + list(CONFIGS_TK)) == fp_golive_dedup_tk
    assert _roster_fingerprint(CONFIGS_GOLIVE_DEDUP) == fp_golive_dedup
    assert _roster_fingerprint(CONFIGS_SHADOW) == fp_shadow
    assert _roster_fingerprint(CONFIGS_LIVE) == fp_live


def test_local_roster_volume_did_not_leak_into_tomachine():
    # THE LEAK PROOF (plan hard invariant), restated 2026-07-27: BOTH rosters
    # now add per-config volumes on independent deep COPIES -- `local` 0.1/0.01
    # and `tomachine` 0.3. The property protected here is that neither leaks
    # into the other, nor into the SHARED S6/S7/SuperTrend dicts (which must
    # keep NO `volume` key at all, so `golive`/`golive-dedup` still use the
    # global --volume).
    for c in CONFIGS_TOMACHINE:
        assert c.get("volume") == 0.3, \
            f"tomachine config {c['id']} volume is {c.get('volume')}, expected 0.3"
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for cid in ("S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"):
        assert "volume" not in golive_by_id[cid], \
            f"a per-config volume leaked into the shared {cid} dict"
    # and the local roster DOES carry the intended per-config volumes.
    local_by_id = {c["id"]: c for c in CONFIGS_LOCAL}
    assert local_by_id["S6-K2P0"]["volume"] == 0.1
    assert local_by_id["S7-TPNONE"]["volume"] == 0.1
    assert local_by_id["SuperTrend-p14x3-M15"]["volume"] == 0.1
    assert local_by_id["TK-Momentum-5-8-short"]["volume"] == 0.01


def test_tomachine_configs_are_copies_matching_golive_except_active_fichas():
    # INTENTION UPDATE (2026-07-27): tomachine no longer SHARES the go-live
    # dicts -- it deep-copies them so its 0.3 volume / single-ficha lever
    # cannot touch the armed rosters. What must still hold is NO DRIFT: the
    # copies' kwargs equal the go-live kwargs except for `active_fichas`, the
    # magics are identical, and the objects are distinct (`is not`).
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    tomachine_by_id = {c["id"]: c for c in CONFIGS_TOMACHINE}
    for cid in ("S6-K2P0", "SuperTrend-p14x3-M15"):
        tm, gl = tomachine_by_id[cid], golive_by_id[cid]
        assert tm is not gl, f"{cid} must be an independent COPY"
        assert tm["kwargs"] is not gl["kwargs"], f"{cid} kwargs must be deep-copied"
        assert tm["magic"] == gl["magic"], f"{cid} magic must be UNCHANGED"
        strip = {k: v for k, v in tm["kwargs"].items() if k != "active_fichas"}
        assert strip == gl["kwargs"], \
            f"{cid} tomachine kwargs drifted from go-live beyond active_fichas"


# ----------------- supervisor SUPERVISOR_CONFIGS plumbing (tomachine) ------
def test_supervisor_env_tomachine(monkeypatch):
    sup = _reload_supervisor_with_clean_env(monkeypatch, "tomachine")
    _assert_configs_is(sup, "tomachine")
    assert "--arm" in sup.EXECUTOR_ARGV
    assert str(guard_cuenta.DEMO_LOGIN) in sup.EXECUTOR_ARGV
    monkeypatch.delenv("SUPERVISOR_CONFIGS", raising=False)
    importlib.reload(sup)


def test_supervisor_env_local(monkeypatch):
    sup = _reload_supervisor_with_clean_env(monkeypatch, "local")
    _assert_configs_is(sup, "local")
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


# ======================= BLOCKED-OPEN TIME WINDOW ==========================
# Owner request 2026-07-27: no NEW position may be opened between 18:00 and
# 18:45 local time (the market-open gap contaminates the indicators on the
# first M15 bars). The gate is OPEN-ONLY: MODIFY/CLOSE/exits must ALWAYS run.
# The clock is the LOCAL naive wall clock (local == Capitaria server time,
# UTC-4), injected in tests by monkeypatching `run_live_20._local_now`.
def _at(hh, mm, ss=0):
    """A `_local_now` replacement pinned to a local wall-clock time."""
    return lambda: datetime(2026, 7, 27, hh, mm, ss)


WIN = (dtime(18, 0), dtime(18, 45))


# ------------------------- parse_blocked_open_window -----------------------
def test_parse_blocked_open_window_happy_path():
    assert run_live_20.parse_blocked_open_window("18:00-18:45") == (dtime(18, 0),
                                                                   dtime(18, 45))


@pytest.mark.parametrize("spec", [
    "18:00",         # no end
    "18:00-",        # empty end
    "-18:45",        # empty start
    "abc-def",       # not digits
    "25:00-25:30",   # hour out of range
    "18:60-19:00",   # minute out of range
    "18:45-18:00",   # start after end (midnight crossing is NOT supported)
    "18:00-18:00",   # empty window
    "",              # nothing at all
])
def test_parse_blocked_open_window_malformed_raises(spec):
    # FAIL-LOUD: a malformed window must NEVER degrade to "protection off".
    with pytest.raises(ValueError):
        run_live_20.parse_blocked_open_window(spec)


# --------------------------- in_blocked_open_window ------------------------
@pytest.mark.parametrize("t,expected", [
    (dtime(17, 59, 59), False),  # one second before -> NOT blocked
    (dtime(18, 0, 0), True),     # start is INCLUSIVE
    (dtime(18, 30, 0), True),
    (dtime(18, 44, 59), True),
    (dtime(18, 45, 0), False),   # end is EXCLUSIVE
    (dtime(19, 0, 0), False),
])
def test_in_blocked_open_window_boundaries(t, expected):
    assert run_live_20.in_blocked_open_window(t, WIN) is expected


@pytest.mark.parametrize("t", [dtime(0, 0), dtime(18, 0), dtime(18, 30),
                               dtime(18, 45), dtime(23, 59, 59)])
def test_in_blocked_open_window_none_never_blocks(t):
    # Default (flag absent) => behaviour byte-identical to before the gate.
    assert run_live_20.in_blocked_open_window(t, None) is False


# ------------------------------- the gate ---------------------------------
def _gate_mt5(positions=None):
    """MockMT5 with a THIN spread and a far, legal SL level, so ONLY the
    time-gate can block an OPEN (never the spread-gate or the SL-clamp)."""
    return MockMT5(_bars(50), positions=positions or [],
                   tick=_Tick(bid=2000.0, ask=2000.2),         # spread 0.20
                   symbol_info=_SymbolInfo(trade_stops_level=50, point=0.01))


def _open_a():
    return Action(kind="OPEN", config_id="S6-K2P0", magic=724011, ficha="F1",
                  side="L", sl=1995.0, volume=0.3, reason="entry")


def test_time_gate_skips_open_inside_window(caplog, monkeypatch):
    monkeypatch.setattr(run_live_20, "_local_now", _at(18, 10))
    mt5 = _gate_mt5()
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, _open_a(), symbol="XAUUSD", dry_run=False,
                                   blocked_open_window=WIN)
    assert mt5.sent == [], "an OPEN inside the blocked window must NOT be sent"
    assert "TIME_GATE_SKIP" in caplog.text


def test_time_gate_sends_open_outside_window(monkeypatch):
    monkeypatch.setattr(run_live_20, "_local_now", _at(19, 0))
    mt5 = _gate_mt5()
    run_live_20.execute_action(mt5, _open_a(), symbol="XAUUSD", dry_run=False,
                              blocked_open_window=WIN)
    assert len(mt5.sent) == 1
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_DEAL


def test_time_gate_never_gates_modify_inside_window(monkeypatch):
    # GLOBAL CONSTRAINT 2: risk management is NEVER time-gated.
    monkeypatch.setattr(run_live_20, "_local_now", _at(18, 10))
    pos = _Pos(ticket=555, magic=724011, type=MockMT5.POSITION_TYPE_BUY,
               volume=0.3, sl=1990.0)
    mt5 = _gate_mt5(positions=[pos])
    a = Action(kind="MODIFY", config_id="S6-K2P0", magic=724011, ficha="F1",
               side="L", sl=1995.0, ticket=555, reason="trail")
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                              blocked_open_window=WIN)
    assert len(mt5.sent) == 1, "MODIFY must ALWAYS be sent, at any hour"
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_SLTP


def test_time_gate_never_gates_close_inside_window(monkeypatch):
    # GLOBAL CONSTRAINT 2: closes are NEVER time-gated.
    monkeypatch.setattr(run_live_20, "_local_now", _at(18, 10))
    pos = _Pos(ticket=777, magic=724011, type=MockMT5.POSITION_TYPE_BUY,
               volume=0.3, sl=1990.0)
    mt5 = _gate_mt5(positions=[pos])
    a = Action(kind="CLOSE", config_id="S6-K2P0", magic=724011, ficha="F1",
               ticket=777, volume=0.3, reason="exit")
    run_live_20.execute_action(mt5, a, symbol="XAUUSD", dry_run=False,
                              blocked_open_window=WIN)
    assert len(mt5.sent) == 1, "CLOSE must ALWAYS be sent, at any hour"
    assert mt5.sent[0]["action"] == mt5.TRADE_ACTION_DEAL


def test_time_gate_applies_in_dry_run_too(caplog, monkeypatch):
    monkeypatch.setattr(run_live_20, "_local_now", _at(18, 44, 59))
    mt5 = _gate_mt5()
    with caplog.at_level("WARNING"):
        run_live_20.execute_action(mt5, _open_a(), symbol="XAUUSD", dry_run=True,
                                   blocked_open_window=WIN)
    assert mt5.sent == []
    assert "TIME_GATE_SKIP" in caplog.text


def test_time_gate_none_window_never_gates_open(monkeypatch):
    # Default OFF: even at 18:10 the OPEN goes out exactly as before.
    monkeypatch.setattr(run_live_20, "_local_now", _at(18, 10))
    mt5 = _gate_mt5()
    run_live_20.execute_action(mt5, _open_a(), symbol="XAUUSD", dry_run=False,
                              blocked_open_window=None)
    assert len(mt5.sent) == 1


def test_time_gate_runs_before_the_spread_gate(monkeypatch):
    # The time-gate needs no broker read, so it must short-circuit BEFORE the
    # spread-gate consults the tick.
    monkeypatch.setattr(run_live_20, "_local_now", _at(18, 10))
    mt5 = _gate_mt5()
    calls: list[str] = []
    real_tick = mt5.symbol_info_tick
    mt5.symbol_info_tick = lambda symbol: (calls.append(symbol), real_tick(symbol))[1]
    run_live_20.execute_action(mt5, _open_a(), symbol="XAUUSD", dry_run=False,
                              blocked_open_window=WIN, max_spread_open=0.70,
                              spread_threshold=0.60)
    assert mt5.sent == []
    assert calls == [], "no tick may be read once the time-gate has skipped"


# ------------------------------ main() plumbing ---------------------------
def test_main_rejects_malformed_window_with_rc2(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("ERROR"):
        rc = run_live_20.main(["--once", "--blocked-open-window", "no-es-una-ventana"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 2, "a malformed safety window must abort loudly"
    assert mt5.initialized is False, "no MT5 connection may be opened"
    assert mt5.sent == []
    assert "--blocked-open-window rejected" in caplog.text
    assert "=== cycle" not in caplog.text, "no cycle may have run"


def test_main_accepts_window_and_reports_it_in_the_banner(caplog, monkeypatch,
                                                          tmp_path):
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "tomachine",
                               "--blocked-open-window", "18:00-18:45"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert "blocked_open_window=18:00-18:45" in caplog.text


def test_main_default_banner_reports_window_off(caplog, monkeypatch, tmp_path):
    monkeypatch.setenv("SPREAD_STORE_DIR", str(tmp_path))
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "tomachine"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert "blocked_open_window=OFF" in caplog.text


def test_run_cycle_propagates_blocked_open_window(monkeypatch):
    seen: list[object] = []

    def _spy(mt5, a, **kwargs):
        seen.append(kwargs.get("blocked_open_window", "MISSING"))

    monkeypatch.setattr(run_live_20, "execute_action", _spy)
    mt5 = MockMT5(_bars(n=600, seed=5))
    run_live_20.run_cycle(mt5, list(CONFIGS_TOMACHINE), window=600,
                          volume=0.01, dry_run=True, deviation=20,
                          blocked_open_window=WIN)
    assert seen, "run_cycle must have dispatched at least one action"
    assert all(w == WIN for w in seen), \
        "every execute_action must receive the window verbatim"
