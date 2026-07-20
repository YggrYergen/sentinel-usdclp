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
    CONFIGS_LIVE,
    CONFIGS_SHADOW,
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
