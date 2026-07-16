"""tests/scripts/test_preflight_live.py -- offline tests for the read-only
live preflight checklist (`scripts/live/preflight_live.py`).

Fully offline: no real MetaTrader5 module, no real MT5 terminal. Uses a fake
mt5 module (reusing the shapes from tests/live/test_executor_dryrun.py) plus
tmp_path for the STOP file / audit log checks.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts.live import preflight_live as pf
from sentinel_engine.live import guard_cuenta


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
class _Info:
    def __init__(self, login, mode):
        self.login = login
        self.trade_mode = mode


class _Tick:
    def __init__(self, time):
        self.time = time


class _Rate(dict):
    pass


class FakeMt5:
    TIMEFRAME_M2 = 2

    def __init__(self, *, login=guard_cuenta.DEMO_LOGIN, mode=guard_cuenta.TRADE_MODE_DEMO,
                 n_bars=101, bar_step=120, last_bar_t=None, tick_time=None,
                 initialize_ok=True, rates_override="unset"):
        self.login = login
        self.mode = mode
        self.initialize_ok = initialize_ok
        self.initialized = False
        self.shutdown_calls = 0
        base = last_bar_t if last_bar_t is not None else int(
            datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc).timestamp())
        if rates_override != "unset":
            self._rates = rates_override
        else:
            self._rates = [_Rate({"time": base - (n_bars - 1 - k) * bar_step,
                                  "open": 2000.0, "high": 2001.0, "low": 1999.0,
                                  "close": 2000.5}) for k in range(n_bars)]
        self._tick_time = tick_time if tick_time is not None else base

    def initialize(self, path=None, portable=None):
        self.initialized = True
        return self.initialize_ok

    def last_error(self):
        return (0, "ok")

    def account_info(self):
        return _Info(self.login, self.mode)

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        if self._rates is None:
            return None
        return self._rates[-count:]

    def symbol_info_tick(self, symbol):
        return _Tick(self._tick_time)

    def shutdown(self):
        self.shutdown_calls += 1


def _always() -> bool:
    return True


def _never() -> bool:
    return False


# --------------------------------------------------------------------------
# check_portable_running / terminal gating
# --------------------------------------------------------------------------
def test_terminal_not_running_short_circuits_mt5_checks():
    report = pf.run_all_checks(mt5_module=FakeMt5(), attach_checker=_never)
    assert report.ok is False
    by_name = {c.name: c for c in report.checks}
    assert by_name["portable-terminal-running"].ok is False
    assert by_name["mt5-attach"].ok is False
    assert "skipped" in by_name["mt5-attach"].detail
    assert by_name["account-guard"].ok is False
    assert by_name["fresh-bars"].ok is False


def test_full_happy_path_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "STOP_FILE", tmp_path / "STOP")
    monkeypatch.setattr(pf, "AUDIT_LOG", tmp_path / "run_live_20.audit.log")
    (tmp_path / "run_live_20.audit.log").write_text("x", encoding="utf-8")

    mt5 = FakeMt5()
    report = pf.run_all_checks(mt5_module=mt5, attach_checker=_always,
                               now_server=datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc))
    assert report.ok is True, report.summary_lines()
    assert mt5.initialized is True
    assert mt5.shutdown_calls == 1


def test_mt5_attach_failure_fails_only_attach_and_downstream():
    mt5 = FakeMt5(initialize_ok=False)
    report = pf.run_all_checks(mt5_module=mt5, attach_checker=_always)
    by_name = {c.name: c for c in report.checks}
    assert by_name["mt5-attach"].ok is False
    assert by_name["account-guard"].ok is False
    assert by_name["fresh-bars"].ok is False
    assert report.ok is False


def test_account_guard_fails_on_real_login():
    mt5 = FakeMt5(login=guard_cuenta.REAL_LOGIN, mode=guard_cuenta.TRADE_MODE_REAL)
    report = pf.run_all_checks(mt5_module=mt5, attach_checker=_always)
    by_name = {c.name: c for c in report.checks}
    assert by_name["account-guard"].ok is False
    assert "REAL" in by_name["account-guard"].detail or "real" in by_name["account-guard"].detail.lower()
    assert report.ok is False


def test_account_guard_never_hard_exits(monkeypatch):
    """preflight is read-only: even a REAL-account mismatch must return a
    normal FAIL result, never call sys.exit (unlike guard_cuenta's default
    hard_exit=True behavior used by the order-capable executor)."""
    mt5 = FakeMt5(login=guard_cuenta.REAL_LOGIN, mode=guard_cuenta.TRADE_MODE_REAL)
    report = pf.PreflightReport()
    ok = pf.check_account_guard(report, mt5)
    assert ok is False
    assert report.checks[-1].ok is False


# --------------------------------------------------------------------------
# fresh-bars staleness
# --------------------------------------------------------------------------
def test_fresh_bars_not_enough_bars_fails():
    mt5 = FakeMt5(n_bars=50)
    report = pf.PreflightReport()
    ok = pf.check_fresh_bars(report, mt5, min_bars=100)
    assert ok is False
    assert "50" in report.checks[-1].detail


def test_fresh_bars_none_response_fails():
    mt5 = FakeMt5(rates_override=None)
    report = pf.PreflightReport()
    ok = pf.check_fresh_bars(report, mt5, min_bars=100)
    assert ok is False


def test_fresh_bars_stale_bar_fails():
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    last_closed_bar_t = int(now.timestamp()) - 3600  # 1 hour old
    # newest row is the forming bar (dropped internally by index -2 logic);
    # make row -2 the stale closed bar.
    rates = [_Rate({"time": last_closed_bar_t - (100 - k) * 120, "open": 1, "high": 1,
                    "low": 1, "close": 1}) for k in range(100)]
    rates.append(_Rate({"time": last_closed_bar_t, "open": 1, "high": 1, "low": 1, "close": 1}))
    rates.append(_Rate({"time": last_closed_bar_t + 120, "open": 1, "high": 1, "low": 1, "close": 1}))
    mt5 = FakeMt5(rates_override=rates)
    report = pf.PreflightReport()
    ok = pf.check_fresh_bars(report, mt5, min_bars=100, max_age_s=300, now_server=now)
    assert ok is False
    assert "old" in report.checks[-1].detail


def test_fresh_bars_fresh_bar_passes():
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    last_closed_bar_t = int(now.timestamp()) - 60  # 1 min old, well within limit
    rates = [_Rate({"time": last_closed_bar_t - (100 - k) * 120, "open": 1, "high": 1,
                    "low": 1, "close": 1}) for k in range(100)]
    rates.append(_Rate({"time": last_closed_bar_t, "open": 1, "high": 1, "low": 1, "close": 1}))
    rates.append(_Rate({"time": last_closed_bar_t + 120, "open": 1, "high": 1, "low": 1, "close": 1}))
    mt5 = FakeMt5(rates_override=rates)
    report = pf.PreflightReport()
    ok = pf.check_fresh_bars(report, mt5, min_bars=100, max_age_s=300, now_server=now)
    assert ok is True


# --------------------------------------------------------------------------
# roster
# --------------------------------------------------------------------------
def test_roster_resolves_passes():
    report = pf.PreflightReport()
    ok = pf.check_roster_resolves(report)
    assert ok is True
    assert report.checks[-1].name == "roster-resolves"


# --------------------------------------------------------------------------
# STOP file
# --------------------------------------------------------------------------
def test_stop_file_present_fails(tmp_path):
    stop = tmp_path / "STOP"
    stop.write_text("", encoding="utf-8")
    report = pf.PreflightReport()
    ok = pf.check_stop_file_absent(report, stop_file=stop)
    assert ok is False
    assert "PAUSED" in report.checks[-1].detail


def test_stop_file_absent_passes(tmp_path):
    stop = tmp_path / "STOP"
    report = pf.PreflightReport()
    ok = pf.check_stop_file_absent(report, stop_file=stop)
    assert ok is True


# --------------------------------------------------------------------------
# audit log writable
# --------------------------------------------------------------------------
def test_audit_log_parent_missing_fails(tmp_path):
    audit = tmp_path / "nope" / "run_live_20.audit.log"
    report = pf.PreflightReport()
    ok = pf.check_audit_log_writable(report, audit_log=audit)
    assert ok is False


def test_audit_log_writable_dir_no_file_yet_passes(tmp_path):
    audit = tmp_path / "run_live_20.audit.log"
    report = pf.PreflightReport()
    ok = pf.check_audit_log_writable(report, audit_log=audit)
    assert ok is True


def test_audit_log_existing_file_writable_passes(tmp_path):
    audit = tmp_path / "run_live_20.audit.log"
    audit.write_text("x", encoding="utf-8")
    report = pf.PreflightReport()
    ok = pf.check_audit_log_writable(report, audit_log=audit)
    assert ok is True


# --------------------------------------------------------------------------
# CLI entrypoint
# --------------------------------------------------------------------------
def test_main_returns_1_on_failure():
    rc = pf.main([], mt5_module=FakeMt5(), attach_checker=_never)
    assert rc == 1


def test_main_json_output(capsys):
    rc = pf.main(["--json"], mt5_module=FakeMt5(), attach_checker=_never)
    assert rc == 1
    captured = capsys.readouterr()
    assert '"ok": false' in captured.out


def test_main_returns_0_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "STOP_FILE", tmp_path / "STOP")
    monkeypatch.setattr(pf, "AUDIT_LOG", tmp_path / "run_live_20.audit.log")
    (tmp_path / "run_live_20.audit.log").write_text("x", encoding="utf-8")
    rc = pf.main([], mt5_module=FakeMt5(), attach_checker=_always)
    assert rc == 0


# --------------------------------------------------------------------------
# process_running helper (used by supervisor for the deals-watcher check)
# --------------------------------------------------------------------------
def test_process_running_is_callable_and_boolean():
    # We don't assert a specific outcome (depends on the real machine's
    # processes at test time) -- just that it returns a bool and never raises.
    result = pf.process_running("some-marker-that-should-not-exist-xyz123")
    assert isinstance(result, bool)
