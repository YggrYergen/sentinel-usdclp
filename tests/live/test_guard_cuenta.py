"""tests/live/test_guard_cuenta.py -- HARD account guard (order-safety)."""
from __future__ import annotations

import pytest

from sentinel_engine.live import guard_cuenta
from sentinel_engine.live.guard_cuenta import (
    DEMO_LOGIN, REAL_LOGIN, TRADE_MODE_DEMO, TRADE_MODE_REAL, GuardError,
    assert_demo,
)


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
