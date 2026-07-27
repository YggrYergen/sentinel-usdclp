"""tests/live/test_reconciler.py -- pure diff core: open/close/SL-update/no-op,
same-bar-exit fallback, missing-SL alarm, caps, kill-switch."""
from __future__ import annotations

import pytest

from sentinel_engine.live.reconciler import (
    reconcile, MAX_VOLUME, MAX_FICHAS_TOTAL,
)

BASE = 720010  # SS-M2 base magic


def _live(tag_offset, side_type, sl, ticket=1, volume=0.01):
    return {"ticket": ticket, "magic": BASE + tag_offset, "type": side_type,
            "volume": volume, "sl": sl}


def _desired(open_state, last_bar_exits=None):
    return {"open": open_state, "last_bar_exits": last_bar_exits or {},
            "last_idx": 100}


def _kinds(res):
    return sorted(a.kind for a in res.actions)


def test_open_missing_fichas():
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0},
                        "F2": {"side": "L", "entry": 2000.0, "sl": 1990.0},
                        "F3": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [])
    opens = [a for a in res.actions if a.kind == "OPEN"]
    assert len(opens) == 3
    assert {a.magic for a in opens} == {BASE + 1, BASE + 2, BASE + 3}
    assert all(a.sl == 1990.0 and a.side == "L" for a in opens)


def test_close_orphan_no_exit():
    # live F1 open, sim wants nothing, no last-bar exit -> plain CLOSE.
    res = reconcile("SS-M2", BASE, _desired({}), [_live(1, 0, 1990.0)])
    assert _kinds(res) == ["CLOSE"]
    assert res.actions[0].ticket == 1


def test_same_bar_exit_fallback():
    # sim exited F1 on the last bar; live still open -> SAME_BAR_EXIT_FALLBACK.
    desired = _desired({}, last_bar_exits={
        "F1": {"price": 1995.5, "motivo": "EXIT_TRAIL", "side": "L", "idx": 100}})
    res = reconcile("SS-M2", BASE, desired, [_live(1, 0, 1990.0)])
    assert _kinds(res) == ["SAME_BAR_EXIT_FALLBACK"]
    a = res.actions[0]
    assert a.sim_fill == 1995.5 and a.motivo == "EXIT_TRAIL"
    assert a.sendable()  # it IS a market close


def test_sl_update():
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1995.0}})
    res = reconcile("SS-M2", BASE, desired, [_live(1, 0, 1990.0)])
    mods = [a for a in res.actions if a.kind == "MODIFY"]
    assert len(mods) == 1 and mods[0].sl == 1995.0


def test_noop_when_in_sync():
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [_live(1, 0, 1990.0)])
    assert [a.kind for a in res.actions] == ["NOOP"]


def test_missing_sl_alarm_and_modify():
    # open ficha with SL=0 -> alarm + modify installs it.
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [_live(1, 0, 0.0)])
    assert "MISSING_SL_ALARM" in _kinds(res)
    assert "MODIFY" in _kinds(res)


def test_volume_cap_rejects():
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [], volume=MAX_VOLUME + 0.01)
    assert [a.kind for a in res.actions] == ["REJECT_VOLUME"]


def test_per_config_max_volume_allows_a_lot_above_the_global_cap():
    # PER-CONFIG CAP (2026-07-27): a roster that legitimately trades above the
    # 0.10 anti-fat-finger default passes its OWN cap; the OPEN must be SENDABLE
    # and carry the exact volume (never clamped, never rejected).
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [], volume=0.67, max_volume=0.67)
    assert [a.kind for a in res.actions] == ["OPEN"]
    assert res.actions[0].sendable()
    assert res.actions[0].volume == 0.67


def test_per_config_max_volume_still_rejects_above_that_cap():
    # The override is a real backstop, not a blank cheque: above the config's
    # OWN cap we still REJECT (and still never clamp).
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [], volume=0.68, max_volume=0.67)
    assert [a.kind for a in res.actions] == ["REJECT_VOLUME"]
    assert not res.actions[0].sendable()


def test_reject_volume_reason_names_the_effective_cap():
    # The log must tell the TRUTH about which limit was applied -- naming the
    # module constant while a per-config cap was in force would send a debugger
    # down the wrong path.
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [], volume=0.68, max_volume=0.67)
    reason = res.actions[0].reason
    assert "0.67" in reason
    assert str(MAX_VOLUME) not in reason


def test_non_positive_max_volume_fails_loudly():
    # A non-positive cap is a CONFIG ERROR, not "reject everything quietly".
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    for bad in (0.0, -0.1):
        with pytest.raises(ValueError):
            reconcile("SS-M2", BASE, desired, [], volume=0.01, max_volume=bad)


def test_default_max_volume_is_unchanged_for_callers_that_omit_it():
    # Byte-identical behaviour for every existing caller.
    assert MAX_VOLUME == 0.10
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    ok = reconcile("SS-M2", BASE, desired, [], volume=MAX_VOLUME)
    assert [a.kind for a in ok.actions] == ["OPEN"]
    bad = reconcile("SS-M2", BASE, desired, [], volume=MAX_VOLUME + 0.01)
    assert [a.kind for a in bad.actions] == ["REJECT_VOLUME"]


def test_total_ficha_cap_rejects():
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [], total_open_fichas=MAX_FICHAS_TOTAL)
    assert [a.kind for a in res.actions] == ["REJECT_CAP"]


def test_kill_switch_suppresses_open_not_logging():
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [], kill_switch=True)
    assert [a.kind for a in res.actions] == ["SUPPRESSED_OPEN"]
    assert not res.actions[0].sendable()


def test_kill_switch_still_closes():
    # kill-switch must NOT block CLOSE/MODIFY of existing positions.
    res = reconcile("SS-M2", BASE, _desired({}), [_live(1, 0, 1990.0)],
                    kill_switch=True)
    assert _kinds(res) == ["CLOSE"]


def test_wrong_side_closes_to_resync():
    # live F1 is SHORT (type=1) but sim wants LONG -> close, then re-open.
    desired = _desired({"F1": {"side": "L", "entry": 2000.0, "sl": 1990.0}})
    res = reconcile("SS-M2", BASE, desired, [_live(1, 1, 1990.0)])
    assert "CLOSE" in _kinds(res) and "OPEN" in _kinds(res)


def test_magic_band_isolation():
    # a position with a magic outside this config's band is ignored.
    res = reconcile("SS-M2", BASE, _desired({}), [_live(9, 0, 1990.0)])  # BASE+9
    assert res.actions == []
