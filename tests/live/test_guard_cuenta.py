"""tests/live/test_guard_cuenta.py -- HARD account guard (order-safety)."""
from __future__ import annotations

import pytest

from sentinel_engine.live import guard_cuenta
from sentinel_engine.live.guard_cuenta import (
    DEMO_LOGIN, REAL_LOGIN, SANCTIONED_DEMO_LOGINS, TRADE_MODE_CONTEST,
    TRADE_MODE_DEMO, TRADE_MODE_REAL, GuardError, assert_demo,
)

OTHER_SANCTIONED_LOGIN = next(iter(SANCTIONED_DEMO_LOGINS - {DEMO_LOGIN}))

# Machine 1's login and TOMACHINE's login (rotated 2026-07-27), plus the login
# RETIRED from the sanctioned set that same day. Spelled out literally on
# purpose: these are the account numbers the guard is supposed to bake in.
MACHINE_1_LOGIN = 2883015767
TOMACHINE_LOGIN = 2883016902
RETIRED_TOMACHINE_LOGIN = 2883016567


class _Info:
    def __init__(self, login, trade_mode):
        self.login = login
        self.trade_mode = trade_mode


class _MT5:
    def __init__(self, info):
        self._info = info

    def account_info(self):
        return self._info


def test_correct_demo_passes():
    mt5 = _MT5(_Info(DEMO_LOGIN, TRADE_MODE_DEMO))
    assert assert_demo(mt5, hard_exit=False) == DEMO_LOGIN


def test_wrong_login_raises():
    mt5 = _MT5(_Info(9999999, TRADE_MODE_DEMO))
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False)


def test_real_login_raises():
    mt5 = _MT5(_Info(REAL_LOGIN, TRADE_MODE_DEMO))
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False)


def test_demo_login_but_real_trade_mode_raises():
    # login matches demo but broker reports REAL trade_mode -> must refuse.
    mt5 = _MT5(_Info(DEMO_LOGIN, TRADE_MODE_REAL))
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False)


def test_none_account_info_raises():
    mt5 = _MT5(None)
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False)


def test_hard_exit_calls_sys_exit():
    mt5 = _MT5(_Info(REAL_LOGIN, TRADE_MODE_REAL))
    with pytest.raises(SystemExit) as ei:
        assert_demo(mt5, hard_exit=True)
    assert ei.value.code == 2


def test_account_info_raising_is_refused():
    class _Boom:
        def account_info(self):
            raise RuntimeError("disconnected")
    with pytest.raises(GuardError):
        assert_demo(_Boom(), hard_exit=False)


# --------------------------------------------------------------------------
# Multi-machine set logic (2026-07-15): SANCTIONED_DEMO_LOGINS is a
# hard-coded frozenset; the machine profile can only SELECT within it
# (via expected_login), never extend it.
# --------------------------------------------------------------------------
def test_sanctioned_set_has_both_machines():
    # Machine 1 + TOMACHINE's CURRENT demo (2026-07-27 rotation). Exact
    # equality, so an accidental extra login fails the suite.
    assert SANCTIONED_DEMO_LOGINS == frozenset({MACHINE_1_LOGIN, TOMACHINE_LOGIN})


def test_retired_tomachine_login_is_no_longer_sanctioned():
    # 2883016567 was RETIRED 2026-07-27: the owner switched TOMACHINE to
    # 2883016902 "from now on". A retired login must fail CLOSED, never be
    # accepted silently, and must not linger in the frozenset.
    assert RETIRED_TOMACHINE_LOGIN not in SANCTIONED_DEMO_LOGINS


def test_retired_tomachine_login_is_refused_by_the_guard():
    mt5 = _MT5(_Info(RETIRED_TOMACHINE_LOGIN, TRADE_MODE_DEMO))
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False)
    # ... and cannot be re-authorized by passing it as this machine's
    # expected login either (config SELECTS, never EXTENDS).
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False,
                    expected_login=RETIRED_TOMACHINE_LOGIN)


def test_machine_1_login_still_sanctioned():
    assert MACHINE_1_LOGIN in SANCTIONED_DEMO_LOGINS


def test_current_tomachine_login_passes_when_expected():
    # 2883016902: verified DEMO (watchdog probe LOGIN=2883016902
    # TRADE_MODE=0) and sanctioned since 2026-07-27.
    assert TOMACHINE_LOGIN in SANCTIONED_DEMO_LOGINS
    mt5 = _MT5(_Info(TOMACHINE_LOGIN, TRADE_MODE_DEMO))
    assert assert_demo(mt5, hard_exit=False,
                       expected_login=TOMACHINE_LOGIN) == TOMACHINE_LOGIN


def test_current_tomachine_login_refused_when_trade_mode_not_demo():
    # Being in the sanctioned set is NOT enough: the broker must also report
    # trade_mode DEMO (0). CONTEST and REAL are both refused.
    for mode in (TRADE_MODE_CONTEST, TRADE_MODE_REAL):
        mt5 = _MT5(_Info(TOMACHINE_LOGIN, mode))
        with pytest.raises(GuardError):
            assert_demo(mt5, hard_exit=False, expected_login=TOMACHINE_LOGIN)


def test_other_sanctioned_login_rejected_when_not_expected_by_this_machine():
    # OTHER_SANCTIONED_LOGIN is a real sanctioned login, but not THIS
    # machine's expected one (DEMO_LOGIN) -- must still be refused: the
    # profile picks exactly one login per machine, not "any sanctioned one".
    mt5 = _MT5(_Info(OTHER_SANCTIONED_LOGIN, TRADE_MODE_DEMO))
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False)


def test_unsanctioned_login_outside_frozenset_rejected_even_if_passed_as_expected():
    # A profile cannot authorize a login outside the hard-coded frozenset,
    # even if (hypothetically) it were passed explicitly as expected_login.
    unsanctioned = 1111111
    assert unsanctioned not in SANCTIONED_DEMO_LOGINS
    mt5 = _MT5(_Info(unsanctioned, TRADE_MODE_DEMO))
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False, expected_login=unsanctioned)


def test_real_login_always_refused_even_as_expected_login():
    # REAL_LOGIN must never pass, even if somehow passed as expected_login.
    mt5 = _MT5(_Info(REAL_LOGIN, TRADE_MODE_DEMO))
    with pytest.raises(GuardError):
        assert_demo(mt5, hard_exit=False, expected_login=REAL_LOGIN)


def test_correct_login_and_mode_passes_with_explicit_expected_login():
    mt5 = _MT5(_Info(OTHER_SANCTIONED_LOGIN, TRADE_MODE_DEMO))
    assert assert_demo(mt5, hard_exit=False,
                       expected_login=OTHER_SANCTIONED_LOGIN) == OTHER_SANCTIONED_LOGIN
