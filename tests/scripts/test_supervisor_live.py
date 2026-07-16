"""tests/scripts/test_supervisor_live.py -- offline tests for the live
executor supervisor (`scripts/live/supervisor_live.py`): preflight gating,
relaunch-with-backoff, and staleness alarm logic. All MT5/subprocess/time
interactions are injected fakes -- no real MT5, no real subprocess, no real
sleeping.
"""
from __future__ import annotations

import pytest

from scripts.live import supervisor_live as sup
from scripts.live import preflight_live as pf


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
def _ok_report() -> pf.PreflightReport:
    r = pf.PreflightReport()
    r.add("fake-check", True, "ok")
    return r


def _fail_report() -> pf.PreflightReport:
    r = pf.PreflightReport()
    r.add("fake-check", False, "nope")
    return r


class _FakeProc:
    """Fake subprocess.Popen: `poll()` returns None until `exit_after_polls`
    poll() calls have happened, then returns `exit_code`."""

    def __init__(self, exit_code=0, exit_after_polls=1):
        self.exit_code = exit_code
        self.exit_after_polls = exit_after_polls
        self._polls = 0

    def poll(self):
        self._polls += 1
        if self._polls >= self.exit_after_polls:
            return self.exit_code
        return None


class _FakeClock:
    """Deterministic now()/sleep(): each sleep() advances the clock by the
    requested amount; no real waiting."""

    def __init__(self, start=0.0):
        self.t = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def _cfg(**overrides) -> sup.SupervisorConfig:
    base = dict(
        executor_argv=["python", "-m", "scripts.live.run_live_20"],
        watchdog_log=overrides.pop("watchdog_log"),
        audit_log=overrides.pop("audit_log"),
        backoff_initial_s=30.0,
        backoff_max_s=600.0,
        backoff_reset_after_s=600.0,
        preflight_retry_s=60.0,
        stale_after_s=300.0,
        stale_recheck_s=30.0,
        max_iterations=1,
    )
    base.update(overrides)
    return sup.SupervisorConfig(**base)


# --------------------------------------------------------------------------
# wait_for_preflight
# --------------------------------------------------------------------------
def test_wait_for_preflight_passes_immediately(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log")
    clock = _FakeClock()
    ok = sup.wait_for_preflight(cfg, preflight_fn=_ok_report, sleep_fn=clock.sleep)
    assert ok is True
    assert clock.sleeps == []
    assert "preflight PASS" in (cfg.watchdog_log.read_text(encoding="utf-8"))


def test_wait_for_preflight_retries_until_pass(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log")
    clock = _FakeClock()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return _ok_report() if calls["n"] >= 3 else _fail_report()

    ok = sup.wait_for_preflight(cfg, preflight_fn=flaky, sleep_fn=clock.sleep)
    assert ok is True
    assert calls["n"] == 3
    assert clock.sleeps == [60.0, 60.0]
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert log_text.count("preflight FAIL") == 2
    assert "preflight PASS" in log_text


def test_wait_for_preflight_gives_up_after_max_attempts(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log")
    clock = _FakeClock()
    ok = sup.wait_for_preflight(cfg, preflight_fn=_fail_report, sleep_fn=clock.sleep,
                               max_attempts=3)
    assert ok is False
    assert clock.sleeps == [60.0, 60.0]  # 3 attempts, sleeps between but not after last


# --------------------------------------------------------------------------
# watch_while_running (staleness alarm)
# --------------------------------------------------------------------------
def test_watch_while_running_returns_exit_code_immediately_if_already_dead(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_recheck_s=10.0)
    clock = _FakeClock()
    proc = _FakeProc(exit_code=2, exit_after_polls=1)
    rc = sup.watch_while_running(cfg, proc, mtime_fn=lambda p: clock.t,
                                 now_fn=clock.now, sleep_fn=clock.sleep)
    assert rc == 2
    assert clock.sleeps == []


def test_watch_while_running_alarms_on_stale_audit_log(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_after_s=300.0, stale_recheck_s=100.0)
    clock = _FakeClock()
    # audit log mtime fixed at t=0; process stays alive long enough (6 polls,
    # 100s apart) that the clock passes the 300s staleness threshold before exit.
    proc = _FakeProc(exit_code=0, exit_after_polls=6)
    rc = sup.watch_while_running(cfg, proc, mtime_fn=lambda p: 0.0,
                                 now_fn=clock.now, sleep_fn=clock.sleep)
    assert rc == 0
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert "ALARM" in log_text


def test_watch_while_running_clears_alarm_when_fresh_again(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_after_s=50.0, stale_recheck_s=40.0)
    clock = _FakeClock()
    # mtime sequence: stale at the first two checks (mtime pinned at 0 while the
    # clock advances past the 50s threshold), then fresh (mtime == now) for the
    # rest, so the loop must observe: not-stale -> ALARM -> alarm-cleared.
    state = {"phase": 0}

    def mtime_fn(_path):
        state["phase"] += 1
        if state["phase"] <= 3:
            return 0.0  # stale once clock.t > 50 (happens by phase 2's sleep)
        return clock.t  # fresh: mtime == now

    proc = _FakeProc(exit_code=0, exit_after_polls=6)
    rc = sup.watch_while_running(cfg, proc, mtime_fn=mtime_fn, now_fn=clock.now,
                                 sleep_fn=clock.sleep)
    assert rc == 0
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert "ALARM" in log_text
    assert "alarm cleared" in log_text


def test_watch_while_running_missing_audit_log_is_stale(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_after_s=300.0, stale_recheck_s=100.0)
    clock = _FakeClock()
    proc = _FakeProc(exit_code=0, exit_after_polls=2)
    rc = sup.watch_while_running(cfg, proc, mtime_fn=lambda p: None,
                                 now_fn=clock.now, sleep_fn=clock.sleep)
    assert rc == 0
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert "ALARM" in log_text
    assert "missing" in log_text


# --------------------------------------------------------------------------
# next_backoff
# --------------------------------------------------------------------------
def test_next_backoff_doubles_up_to_max(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              backoff_initial_s=30.0, backoff_max_s=600.0)
    b = cfg.backoff_initial_s
    seen = []
    for _ in range(6):
        b = sup.next_backoff(b, cfg=cfg)
        seen.append(b)
    assert seen == [60.0, 120.0, 240.0, 480.0, 600.0, 600.0]


# --------------------------------------------------------------------------
# run_supervised: end-to-end with fakes
# --------------------------------------------------------------------------
def test_run_supervised_refuses_to_launch_when_preflight_fails(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              preflight_retry_s=10.0, max_iterations=1)
    clock = _FakeClock()
    launch_calls = []

    def launcher(argv):
        launch_calls.append(argv)
        return _FakeProc(exit_code=0, exit_after_polls=1)

    sup.run_supervised(cfg, preflight_fn=lambda: _preflight_gate_once_then_ok(cfg),
                       launcher=launcher, mtime_fn=lambda p: clock.t,
                       sleep_fn=clock.sleep, now_fn=clock.now)
    # preflight fails first then passes (handled by helper) -> exactly 1 launch
    assert len(launch_calls) == 1


def _preflight_gate_once_then_ok(cfg):
    """Helper: fails on first call (per-test call count tracked on cfg object
    via a mutable attribute), passes afterwards."""
    n = getattr(cfg, "_pf_calls", 0) + 1
    setattr(cfg, "_pf_calls", n)
    return _ok_report() if n >= 2 else _fail_report()


def test_run_supervised_relaunches_with_backoff_and_logs_events(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              backoff_initial_s=5.0, backoff_max_s=600.0, backoff_reset_after_s=600.0,
              preflight_retry_s=1.0, stale_recheck_s=1.0, max_iterations=2)
    clock = _FakeClock()
    launch_calls = []

    def launcher(argv):
        launch_calls.append(argv)
        return _FakeProc(exit_code=2, exit_after_polls=1)

    sup.run_supervised(cfg, preflight_fn=_ok_report, launcher=launcher,
                      mtime_fn=lambda p: clock.t, sleep_fn=clock.sleep, now_fn=clock.now)

    assert len(launch_calls) == 2
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert log_text.count("launching executor") == 2
    assert "exited with code 2" in log_text.lower()
    assert "backing off 5s" in log_text.lower()


def test_run_supervised_reports_deals_watcher_status_once(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              max_iterations=1)
    clock = _FakeClock()
    calls = {"n": 0}

    def watcher_check():
        calls["n"] += 1
        return False

    def launcher(argv):
        return _FakeProc(exit_code=0, exit_after_polls=1)

    sup.run_supervised(cfg, preflight_fn=_ok_report, launcher=launcher,
                      mtime_fn=lambda p: clock.t, sleep_fn=clock.sleep, now_fn=clock.now,
                      deals_watcher_check=watcher_check)
    assert calls["n"] == 1
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert "deals watcher" in log_text.lower()
    assert "not detected" in log_text.lower()


def test_run_supervised_never_touches_mt5_module():
    """Sanity guardrail: supervisor_live must not import MetaTrader5 order
    APIs. We simply assert the module has no `order_send`-shaped attribute
    and doesn't import MetaTrader5 at module scope."""
    assert not hasattr(sup, "MetaTrader5")
    import sys
    # module-level import shouldn't have pulled MetaTrader5 into sys.modules
    # as a side effect of importing supervisor_live (it may already be there
    # from another test in the session touching run_live_20 with a real
    # import guarded behind attach_checker=False, so this is a soft check).
    src = open(sup.__file__, encoding="utf-8").read()
    assert "import MetaTrader5" not in src
    assert "order_send" not in src
