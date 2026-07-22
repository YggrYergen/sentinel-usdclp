"""tests/test_data_feed_connect.py -- profile-based, ATTACH-ONLY MT5 connection
for the web UI's read-only `DataFeed` (`sentinel/data_feed.py::_try_connect_mt5`).

WHY (2026-07-22 live incident): the old `_try_connect_mt5` connected MT5 with a
HARDCODED `sentinel.config.MT5_TERMINAL_PATH` and, on failure, fell back to a
BARE `mt5.initialize()`. Bare initialize can attach to (or launch) an arbitrary
terminal; on machine-2 that second, non-profile connection stalled the
terminal's IPC and FROZE the live executor. The connection must now mirror the
executor/watcher pattern EXACTLY: load the machine profile, refuse unless the
profile's terminal is ALREADY RUNNING (attach-only, never launch), then
`initialize(path=profile.terminal_path, portable=...)`. NO bare initialize, NO
hardcoded-path branch, ever.

All MetaTrader5 interaction is a mock -- no real MT5, no real terminal.
"""
from __future__ import annotations

import sys
import types

import pytest

from sentinel_engine.live.machine_profile import (
    MachineProfile,
    MachineProfileError,
)


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
def _fake_profile(portable=True):
    return MachineProfile(
        terminal_path=__import__("pathlib").Path(r"D:\FOREX\MT5_Portable\terminal64.exe"),
        portable=portable,
        demo_login=2883015767,
        terminal_marker="mt5_portable",
    )


class _FakeMt5:
    """Minimal mock of the MetaTrader5 module surface `_try_connect_mt5` uses."""

    # timeframe constants (mapped by DataFeed once connected)
    TIMEFRAME_M1 = 1
    TIMEFRAME_M2 = 2
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388
    TIMEFRAME_D1 = 16408

    def __init__(self, init_result=True):
        self._init_result = init_result
        self.init_calls: list[dict] = []

        class _Acc:
            login = 2883015767
            server = "Capitaria-Demo"
            balance = 1000.0

        class _TI:
            build = 4000
            connected = True
            trade_allowed = True

        self._acc = _Acc()
        self._ti = _TI()

    def initialize(self, *args, **kwargs):
        self.init_calls.append({"args": args, "kwargs": kwargs})
        return self._init_result

    def last_error(self):
        return (-1, "fake error")

    def account_info(self):
        return self._acc

    def terminal_info(self):
        return self._ti

    def symbol_info(self, symbol):
        return None

    def symbol_select(self, symbol, on):
        return True


def _install_fake_mt5(monkeypatch, fake):
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)


@pytest.fixture()
def df_module():
    from sentinel import data_feed
    return data_feed


# --------------------------------------------------------------------------
# (a) profile terminal running -> initialize called with profile path + flag
# --------------------------------------------------------------------------
def test_connect_when_terminal_running_uses_profile_path_and_portable(monkeypatch, df_module):
    fake = _FakeMt5(init_result=True)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(df_module, "load_profile", lambda: _fake_profile(portable=True))
    monkeypatch.setattr(df_module, "_terminal_running", lambda marker: True)
    # do not actually hit symbol enabling (needs sentinel.config symbols)
    monkeypatch.setattr(df_module.DataFeed, "_enable_symbols", lambda self: None)

    feed = df_module.DataFeed(mode="mt5")

    assert feed.mt5_connected is True
    assert len(fake.init_calls) == 1
    call = fake.init_calls[0]
    # profile path passed, portable=True (machine-1) -- NEVER a bare initialize()
    assert call["kwargs"].get("path") == r"D:\FOREX\MT5_Portable\terminal64.exe"
    assert call["kwargs"].get("portable") is True


def test_connect_non_portable_profile_omits_portable_kwarg(monkeypatch, df_module):
    fake = _FakeMt5(init_result=True)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(df_module, "load_profile", lambda: _fake_profile(portable=False))
    monkeypatch.setattr(df_module, "_terminal_running", lambda marker: True)
    monkeypatch.setattr(df_module.DataFeed, "_enable_symbols", lambda self: None)

    feed = df_module.DataFeed(mode="mt5")

    assert feed.mt5_connected is True
    call = fake.init_calls[0]
    assert call["kwargs"].get("path")  # path present
    # machine-2 (standard install): portable kwarg must NOT be passed at all
    assert "portable" not in call["kwargs"]


# --------------------------------------------------------------------------
# (b) terminal not running -> initialize NEVER called, mt5_connected False
# --------------------------------------------------------------------------
def test_no_initialize_when_terminal_not_running(monkeypatch, df_module):
    fake = _FakeMt5(init_result=True)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(df_module, "load_profile", lambda: _fake_profile())
    monkeypatch.setattr(df_module, "_terminal_running", lambda marker: False)

    feed = df_module.DataFeed(mode="mt5")

    assert feed.mt5_connected is False
    assert fake.init_calls == []  # attach-only: never launched/initialized


# --------------------------------------------------------------------------
# (c) MachineProfileError -> no connect, no raise
# --------------------------------------------------------------------------
def test_machine_profile_error_is_swallowed_and_no_connect(monkeypatch, df_module):
    fake = _FakeMt5(init_result=True)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)

    def _boom():
        raise MachineProfileError("bad machine_local.json")

    monkeypatch.setattr(df_module, "load_profile", _boom)
    # even if running-check would pass, profile error stops us before it
    monkeypatch.setattr(df_module, "_terminal_running", lambda marker: True)

    feed = df_module.DataFeed(mode="mt5")  # must not raise

    assert feed.mt5_connected is False
    assert fake.init_calls == []


# --------------------------------------------------------------------------
# (d) initialize returns False -> warning, NO bare fallback
# --------------------------------------------------------------------------
def test_initialize_false_does_not_fall_back_to_bare(monkeypatch, df_module):
    fake = _FakeMt5(init_result=False)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(df_module, "load_profile", lambda: _fake_profile())
    monkeypatch.setattr(df_module, "_terminal_running", lambda marker: True)

    feed = df_module.DataFeed(mode="mt5")

    assert feed.mt5_connected is False
    # exactly ONE initialize call, WITH the profile path -- never a bare retry.
    assert len(fake.init_calls) == 1
    assert fake.init_calls[0]["kwargs"].get("path")


# --------------------------------------------------------------------------
# Static guardrail: no bare initialize() or hardcoded MT5_TERMINAL_PATH branch
# remains anywhere in the module source.
# --------------------------------------------------------------------------
def test_source_has_no_bare_initialize_or_hardcoded_path(df_module):
    src = open(df_module.__file__, encoding="utf-8").read()
    # Strip comment lines so prose describing the guard ("...never call
    # mt5.initialize() bare...") does not trip the check; we only forbid a bare
    # initialize() as executable CODE.
    code_lines = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        code_lines.append(line)
    code = "\n".join(code_lines)
    # no bare initialize() with empty parens in executable code
    assert "mt5.initialize()" not in code
    assert ".initialize()" not in code
    # the old hardcoded-path import/branch must be gone from the connect logic
    assert "MT5_TERMINAL_PATH" not in code
