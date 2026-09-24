"""tests/scripts/test_supervisor_live.py -- offline tests for the live
executor supervisor (`scripts/live/supervisor_live.py`): preflight gating,
relaunch-with-backoff, and staleness alarm logic. All MT5/subprocess/time
interactions are injected fakes -- no real MT5, no real subprocess, no real
sleeping.
"""
from __future__ import annotations

import sys

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


# --------------------------------------------------------------------------
# deals-watcher survivability: the supervisor now STARTS and KEEPS ALIVE the
# watcher (not just warns), so `deals_raw` is always being written. Idempotent
# by cmdline-marker detection -- never doubles an already-running watcher.
# --------------------------------------------------------------------------
def test_ensure_watcher_running_launches_when_absent(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              watcher_argv=["python", "-m", "scripts.live.run_deals_watcher", "--poll", "5"])
    launches = []
    launched = sup.ensure_watcher_running(
        cfg, is_running_fn=lambda: False,
        launcher=lambda argv: launches.append(argv))
    assert launched is True
    assert launches == [cfg.watcher_argv]
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert "deals watcher" in log_text.lower()
    assert "launching" in log_text.lower()


def test_ensure_watcher_running_noop_when_already_running(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              watcher_argv=["python", "-m", "scripts.live.run_deals_watcher"])
    launches = []
    launched = sup.ensure_watcher_running(
        cfg, is_running_fn=lambda: True,
        launcher=lambda argv: launches.append(argv))
    assert launched is False
    assert launches == []


def test_watch_while_running_invokes_watcher_keepalive_each_poll(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_recheck_s=10.0)
    clock = _FakeClock()
    proc = _FakeProc(exit_code=0, exit_after_polls=3)  # alive for 2 poll cycles
    keepalive_calls = {"n": 0}

    rc = sup.watch_while_running(
        cfg, proc, mtime_fn=lambda p: clock.t, now_fn=clock.now, sleep_fn=clock.sleep,
        watcher_keepalive=lambda: keepalive_calls.__setitem__("n", keepalive_calls["n"] + 1))
    assert rc == 0
    # Keepalive fired on every poll cycle where the process was still alive.
    assert keepalive_calls["n"] >= 2


def test_run_supervised_starts_watcher_at_startup(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              max_iterations=1)
    clock = _FakeClock()
    keepalive_calls = {"n": 0}

    def launcher(argv):
        return _FakeProc(exit_code=0, exit_after_polls=1)

    sup.run_supervised(cfg, preflight_fn=_ok_report, launcher=launcher,
                      mtime_fn=lambda p: clock.t, sleep_fn=clock.sleep, now_fn=clock.now,
                      watcher_keepalive=lambda: keepalive_calls.__setitem__("n", keepalive_calls["n"] + 1))
    # Watcher keepalive ran at least once (startup) even though the executor
    # exited immediately.
    assert keepalive_calls["n"] >= 1


# --------------------------------------------------------------------------
# Console-write-block regression (2026-07-15 incident): the executor must
# never inherit this process's console, and watchdog logging must not depend
# on a console echo either.
# --------------------------------------------------------------------------
def test_default_launcher_redirects_executor_stdio_to_file(tmp_path, monkeypatch):
    console_log = tmp_path / "executor_console.log"
    monkeypatch.setattr(sup, "EXECUTOR_CONSOLE_LOG", console_log)

    captured = {}
    real_popen = sup.subprocess.Popen

    class _FakePopenResult:
        def poll(self):
            return 0

    def fake_popen(argv, **kwargs):
        captured.update(kwargs)
        captured["argv"] = argv
        return _FakePopenResult()

    monkeypatch.setattr(sup.subprocess, "Popen", fake_popen)
    proc = sup._default_launcher(["python", "-m", "scripts.live.run_live_20"])

    assert proc.poll() == 0
    assert "stdout" in captured and captured["stdout"] is not None
    assert "stderr" in captured and captured["stderr"] is not None
    # Must NOT inherit the parent console: no console-inheriting kwargs set,
    # and stdout/stderr point at real file objects backed by our log path.
    assert captured["stdout"] is captured["stderr"]
    assert console_log.exists()
    monkeypatch.setattr(sup.subprocess, "Popen", real_popen)


def test_log_watchdog_writes_file_only_no_console_handler_required(tmp_path, capsys):
    """Regression for the 2026-07-15 freeze: `_log_watchdog` used to also call
    `logger.info(msg)` (a console StreamHandler emit) which can block forever
    under Windows QuickEdit/conhost stalls. It must now write to watchdog.log
    ONLY -- no console output is required for the watchdog line to land."""
    log_path = tmp_path / "watchdog.log"
    sup._log_watchdog("test message, no console needed", log_path=log_path)
    assert "test message, no console needed" in log_path.read_text(encoding="utf-8")
    # No assertion on stdout content: the point is correctness does not
    # depend on console output succeeding. We only assert this doesn't hang
    # (implicitly, by the test completing) and the module has no
    # StreamHandler wired into `logger` by default.
    assert not any(isinstance(h, __import__("logging").StreamHandler)
                  for h in sup.logger.handlers)


def test_main_does_not_configure_console_stream_handler(tmp_path, monkeypatch):
    """`main()` must not attach a StreamHandler(stdout) to the root/module
    logger -- that was the exact mechanism that let a console write-block
    freeze the supervisor on 2026-07-15."""
    import logging as _logging

    monkeypatch.setattr(sup, "WATCHDOG_LOG", tmp_path / "watchdog.log")

    def fake_run_supervised(cfg, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(sup, "run_supervised", fake_run_supervised)

    root_handlers_before = list(_logging.getLogger().handlers)
    sup.main()
    root_handlers_after = list(_logging.getLogger().handlers)
    assert not any(isinstance(h, _logging.StreamHandler) and h.stream is sys.stdout
                  for h in root_handlers_after
                  if h not in root_handlers_before)


def test_ensure_bars_ingester_running_launches_when_absent(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              bars_ingester_argv=["python", "-m", "scripts.live.run_bars_ingester"])
    launches = []
    launched = sup.ensure_bars_ingester_running(
        cfg, is_running_fn=lambda: False,
        launcher=lambda argv: launches.append(argv))
    assert launched is True
    assert launches == [cfg.bars_ingester_argv]
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert "bars ingester" in log_text.lower()
    assert "launching" in log_text.lower()


def test_ensure_bars_ingester_running_noop_when_already_running(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              bars_ingester_argv=["python", "-m", "scripts.live.run_bars_ingester"])
    launches = []
    launched = sup.ensure_bars_ingester_running(
        cfg, is_running_fn=lambda: True,
        launcher=lambda argv: launches.append(argv))
    assert launched is False
    assert launches == []


def test_ensure_bars_ingester_running_noop_when_argv_none(tmp_path):
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log")
    launches = []
    launched = sup.ensure_bars_ingester_running(
        cfg, is_running_fn=lambda: False,
        launcher=lambda argv: launches.append(argv))
    assert launched is False
    assert launches == []


# --------------------------------------------------------------------------
# build_executor_argv: optional static hard spread cap (SUPERVISOR_MAX_SPREAD_OPEN)
# passed through to the executor's `--max-spread-open`. Machine-1 immutability:
# unset/empty => argv identical to the pre-existing shape (no cap flag at all).
# --------------------------------------------------------------------------
def test_build_executor_argv_default_has_no_spread_cap():
    argv = sup.build_executor_argv(configs="tomachine", max_spread_open=None)
    assert "--configs" in argv
    assert argv[argv.index("--configs") + 1] == "tomachine"
    assert "--max-spread-open" not in argv


def test_build_executor_argv_with_cap_appends_flag_and_keeps_existing_args():
    argv = sup.build_executor_argv(configs="tomachine", max_spread_open="0.5")
    assert argv[-2:] == ["--max-spread-open", "0.5"]
    assert "--arm" in argv
    assert "--confirm-account" in argv
    login_idx = argv.index("--confirm-account") + 1
    assert argv[login_idx] == str(sup.guard_cuenta.DEMO_LOGIN)
    assert "--configs" in argv
    assert argv[argv.index("--configs") + 1] == "tomachine"


@pytest.mark.parametrize("value", ["", None])
def test_build_executor_argv_empty_or_none_treated_as_unset(value):
    argv = sup.build_executor_argv(max_spread_open=value)
    assert "--max-spread-open" not in argv


@pytest.mark.parametrize("value", ["abc", "-1", "0"])
def test_build_executor_argv_invalid_cap_raises_system_exit(value):
    with pytest.raises(SystemExit):
        sup.build_executor_argv(max_spread_open=value)


def test_default_executor_argv_has_no_spread_cap_when_env_unset(monkeypatch):
    """Proves machine-1 (env var unset) is unchanged: the module-level
    EXECUTOR_ARGV built at import time never contains --max-spread-open when
    SUPERVISOR_MAX_SPREAD_OPEN is unset."""
    assert sup.SUPERVISOR_MAX_SPREAD_OPEN in (None, "")
    assert "--max-spread-open" not in sup.EXECUTOR_ARGV


# --------------------------------------------------------------------------
# P1 (2026-07-22): env-gated auto-recycle of a STALE executor. Default OFF =
# today's alarm-only behavior, byte-identical. When SUPERVISOR_STALE_AUTORESTART
# is truthy, `watch_while_running` terminates the executor after the audit log
# has been stale past `stale_after_s` AND stays stale for one recheck
# confirmation (avoids killing on a single race), then returns so the outer
# preflight-gated relaunch cycle restarts it.
# --------------------------------------------------------------------------
class _FakeKillableProc:
    """Fake Popen that stays alive until terminate()/kill() is called."""

    def __init__(self):
        self._rc = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0
        self._die_on_wait = True

    def poll(self):
        return self._rc

    def terminate(self):
        self.terminate_calls += 1
        if self._die_on_wait:
            self._rc = -15  # SIGTERM-ish

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self._rc is None:
            raise _FakeTimeoutExpired()
        return self._rc

    def kill(self):
        self.kill_calls += 1
        self._rc = -9


class _FakeTimeoutExpired(Exception):
    pass


def test_watch_stale_autorestart_off_does_not_kill(tmp_path):
    """Flag OFF => stale executor is NOT killed (existing alarm-only behavior)."""
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_after_s=300.0, stale_recheck_s=100.0, stale_autorestart=False)
    clock = _FakeClock()
    proc = _FakeProc(exit_code=0, exit_after_polls=6)
    rc = sup.watch_while_running(cfg, proc, mtime_fn=lambda p: 0.0,
                                 now_fn=clock.now, sleep_fn=clock.sleep)
    assert rc == 0
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert "ALARM" in log_text
    assert "AUTORESTART" not in log_text


def test_watch_stale_autorestart_on_kills_after_confirmation(tmp_path):
    """Flag ON => after stale + one recheck confirmation, terminate() is called
    and the function returns (so the outer loop relaunches)."""
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_after_s=300.0, stale_recheck_s=100.0, stale_autorestart=True)
    clock = _FakeClock()
    proc = _FakeKillableProc()
    rc = sup.watch_while_running(cfg, proc, mtime_fn=lambda p: 0.0,
                                 now_fn=clock.now, sleep_fn=clock.sleep)
    # terminate() was called; function returned an exit code.
    assert proc.terminate_calls >= 1
    assert rc is not None
    log_text = cfg.watchdog_log.read_text(encoding="utf-8")
    assert "AUTORESTART" in log_text
    assert "killing stale executor" in log_text.lower()


def test_watch_stale_autorestart_on_but_fresh_does_not_kill(tmp_path):
    """Flag ON but audit log FRESH => nothing killed."""
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_after_s=300.0, stale_recheck_s=10.0, stale_autorestart=True)
    clock = _FakeClock()
    proc = _FakeKillableProc()
    # mtime always == now => never stale; proc must exit on its own. Use a
    # proc that dies after a couple polls so the loop terminates.
    normal = _FakeProc(exit_code=0, exit_after_polls=3)
    rc = sup.watch_while_running(cfg, normal, mtime_fn=lambda p: clock.t,
                                 now_fn=clock.now, sleep_fn=clock.sleep)
    assert rc == 0
    log_text = cfg.watchdog_log.read_text(encoding="utf-8") if cfg.watchdog_log.exists() else ""
    assert "AUTORESTART" not in log_text


def test_watch_stale_autorestart_needs_confirmation_recheck(tmp_path):
    """Flag ON: a SINGLE stale observation must NOT kill -- the executor is only
    killed after it remains stale on the confirmation recheck."""
    cfg = _cfg(watchdog_log=tmp_path / "watchdog.log", audit_log=tmp_path / "audit.log",
              stale_after_s=50.0, stale_recheck_s=40.0, stale_autorestart=True)
    clock = _FakeClock()
    proc = _FakeKillableProc()
    # phase1: stale (mtime 0, clock passes 50). phase2 recheck: FRESH again ->
    # alarm cleared, NOT killed. Then let it die on its own.
    state = {"n": 0}

    def mtime_fn(_p):
        state["n"] += 1
        # checks 1-2: mtime pinned at 0 (clock passes 50 by check 2 -> ALARM,
        # was_stale=True). check 3+: fresh (mtime == now) -> alarm cleared, the
        # confirmation recheck sees fresh, so NO kill happens.
        if state["n"] <= 3:
            return 0.0
        return clock.t

    normal = _FakeProc(exit_code=0, exit_after_polls=6)
    rc = sup.watch_while_running(cfg, normal, mtime_fn=mtime_fn,
                                 now_fn=clock.now, sleep_fn=clock.sleep)
    assert rc == 0
    log_text = cfg.watchdog_log.read_text(encoding="utf-8") if cfg.watchdog_log.exists() else ""
    # A single stale observation armed the alarm, but the confirmation recheck
    # saw a FRESH log -> the executor was NOT killed.
    assert "killing stale executor" not in log_text.lower()
    assert "alarm cleared" in log_text


def test_stale_autorestart_env_unset_is_off_and_immutable(monkeypatch):
    """Immutability (machine-2 safety): with SUPERVISOR_STALE_AUTORESTART unset,
    the SupervisorConfig default is OFF, matching pre-P1 behavior."""
    # module-level flag read at import time must be falsey when env unset
    assert sup.SUPERVISOR_STALE_AUTORESTART in (None, "", "0", "false", "False")
    # A default SupervisorConfig must default stale_autorestart to False.
    cfg = sup.SupervisorConfig(executor_argv=["python"])
    assert cfg.stale_autorestart is False


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
