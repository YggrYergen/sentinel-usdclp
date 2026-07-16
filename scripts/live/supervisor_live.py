r"""scripts/live/supervisor_live.py -- survivability wrapper around the guarded
live executor (SENTINEL, 2026-07-15). NOT ORDER-CAPABLE ITSELF: this module
never imports MetaTrader5 and never sends an order; it only launches/monitors
the executor SUBPROCESS and re-runs the read-only preflight checklist.

WHY THIS EXISTS (2026-07-14 incident): the executor died at 12:13:22 when
`guard_cuenta` detected the MT5 IPC link was gone (exit code 2, BY DESIGN --
see run_live_20.py). Nothing relaunched it and nothing alarmed:
`INICIAR_TRADING_LIVE.bat`'s old watchdog loop only fired if that exact batch
window had been left open continuously, wrote to `watchdog.log` only on the
two branches it happened to hit, and blocked synchronously inside
`python -m scripts.live.run_live_20` (a `start`-less foreground call) for the
executor's entire lifetime -- so a closed/never-opened window meant zero
relaunches and zero log lines. `scripts/live/watchdog.log` not existing on
this machine is the proof.

WHAT THIS MODULE DOES
  1. On start: run `scripts.live.preflight_live.run_all_checks()`. Refuse to
     launch if it fails; print exactly what to fix (e.g. "open the MT5
     portable terminal by hand") and log the failure to `watchdog.log`.
  2. Launch the executor as a SUBPROCESS, armed with the roster
     (`python -m scripts.live.run_live_20 --arm --confirm-account
     <this machine's guard_cuenta.DEMO_LOGIN, e.g. 2883015767> --configs
     live`), via the injectable `launcher` callable
     (production default: `subprocess.Popen`). We NEVER call
     `MetaTrader5.initialize()` ourselves -- that happens inside the child
     process, which itself re-checks ATTACH-ONLY before doing so.
  3. If the executor process exits (ANY exit code): log it loudly to
     `watchdog.log`, wait a backoff (starts at `BACKOFF_INITIAL_S`, doubles up
     to `BACKOFF_MAX_S`), re-run preflight, and relaunch ONLY when preflight
     passes again. Backoff resets to the initial value after any relaunch
     that stays up longer than `BACKOFF_RESET_AFTER_S` (avoids one long stable
     run leaving a maxed-out backoff for the next, unrelated failure).
     Unlimited patience: the loop keeps retrying forever (or until
     `max_iterations` in tests / Ctrl-C in production).
  4. Staleness alarm: while the executor runs, if
     `scripts/live/run_live_20.audit.log`'s mtime is older than
     `STALE_AFTER_S` (5 minutes), log ALARM lines (repeatable, not just once)
     to both `watchdog.log` and stdout. Does NOT kill the process automatically.
  5. Startup-only: report whether the deals watcher
     (`scripts.live.run_deals_watcher`) process appears to be running (via
     `preflight_live.process_running`) -- warn if absent, never start it.

This module contains NO MetaTrader5 order APIs. All MT5-specific read-only
logic lives in `preflight_live.py` (imported); the executor's own decision
logic in `run_live_20.py` is untouched.

USAGE
    python -m scripts.live.supervisor_live
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.live import preflight_live  # noqa: E402
from sentinel_engine.live import guard_cuenta  # noqa: E402

WATCHDOG_LOG = REPO_ROOT / "scripts" / "live" / "watchdog.log"
AUDIT_LOG = preflight_live.AUDIT_LOG

EXECUTOR_ARGV = [sys.executable, "-m", "scripts.live.run_live_20", "--arm",
                 "--confirm-account", str(guard_cuenta.DEMO_LOGIN),
                 "--configs", "live"]
DEALS_WATCHER_MARKER = "run_deals_watcher"

BACKOFF_INITIAL_S = 30.0
BACKOFF_MAX_S = 600.0  # 10 minutes
BACKOFF_RESET_AFTER_S = 600.0  # a run that survives this long resets backoff
PREFLIGHT_RETRY_S = 60.0  # wait between preflight re-checks while it's failing
STALE_AFTER_S = 5 * 60.0
STALE_RECHECK_S = 30.0  # how often the running-executor loop polls

logger = logging.getLogger("supervisor_live")


def _log_watchdog(msg: str, *, log_path: Path = WATCHDOG_LOG) -> None:
    """Append one UTF-8 timestamped line to watchdog.log AND emit it via the
    standard logger (console). Never raises -- a logging failure must not
    take down the supervisor."""
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}"
    logger.info(msg)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 -- logging must never crash the supervisor
        logger.exception("failed to append to watchdog.log")


@dataclass
class SupervisorConfig:
    executor_argv: list[str]
    watchdog_log: Path = WATCHDOG_LOG
    audit_log: Path = AUDIT_LOG
    backoff_initial_s: float = BACKOFF_INITIAL_S
    backoff_max_s: float = BACKOFF_MAX_S
    backoff_reset_after_s: float = BACKOFF_RESET_AFTER_S
    preflight_retry_s: float = PREFLIGHT_RETRY_S
    stale_after_s: float = STALE_AFTER_S
    stale_recheck_s: float = STALE_RECHECK_S
    max_iterations: int | None = None  # None = run forever (production)


# --------------------------------------------------------------------------
# Preflight gate: block until preflight passes (or max_iterations exhausted).
# --------------------------------------------------------------------------
def wait_for_preflight(cfg: SupervisorConfig, *,
                       preflight_fn: Callable[[], "preflight_live.PreflightReport"],
                       sleep_fn: Callable[[float], None] = time.sleep,
                       max_attempts: int | None = None) -> bool:
    """Repeatedly runs `preflight_fn()` until it passes. Logs a loud summary
    on every failed attempt. Returns True as soon as preflight passes; returns
    False only if `max_attempts` is exhausted (tests only -- production callers
    pass max_attempts=None for unlimited patience)."""
    attempt = 0
    while True:
        attempt += 1
        report = preflight_fn()
        if report.ok:
            _log_watchdog(f"preflight PASS (attempt {attempt}).", log_path=cfg.watchdog_log)
            return True
        _log_watchdog(
            "preflight FAIL -- refusing to (re)launch the executor. "
            f"attempt={attempt}. Fix and it will retry automatically:",
            log_path=cfg.watchdog_log)
        for line in report.summary_lines():
            if line.startswith("[FAIL]"):
                _log_watchdog(f"  {line}", log_path=cfg.watchdog_log)
        if max_attempts is not None and attempt >= max_attempts:
            return False
        sleep_fn(cfg.preflight_retry_s)


# --------------------------------------------------------------------------
# Staleness watch: polls while the executor subprocess is alive.
# --------------------------------------------------------------------------
def watch_while_running(cfg: SupervisorConfig, proc: Any, *,
                        mtime_fn: Callable[[Path], float | None],
                        now_fn: Callable[[], float] = time.time,
                        sleep_fn: Callable[[float], None] = time.sleep) -> int:
    """Polls `proc.poll()` every `stale_recheck_s` while the executor runs.
    Logs (repeatable) ALARM lines if the audit log hasn't been touched for
    more than `stale_after_s`. Returns the process's exit code once it exits.
    Never kills `proc` itself -- staleness is alarm-only per spec."""
    was_stale = False
    while True:
        rc = proc.poll()
        if rc is not None:
            return rc

        mtime = mtime_fn(cfg.audit_log)
        now = now_fn()
        if mtime is None:
            age = None
            stale = True
        else:
            age = now - mtime
            stale = age > cfg.stale_after_s

        if stale:
            age_str = "unknown (audit log missing)" if age is None else f"{age:.0f}s"
            _log_watchdog(
                f"ALARM: audit log stale (age={age_str}, limit={cfg.stale_after_s:.0f}s) "
                "-- executor process is alive but may not be completing cycles. "
                "NOT killing it automatically; investigate manually.",
                log_path=cfg.watchdog_log)
            was_stale = True
        elif was_stale:
            _log_watchdog(f"audit log fresh again (age={age:.0f}s) -- alarm cleared.",
                         log_path=cfg.watchdog_log)
            was_stale = False

        sleep_fn(cfg.stale_recheck_s)


# --------------------------------------------------------------------------
# Backoff helper.
# --------------------------------------------------------------------------
def next_backoff(current_s: float, *, cfg: SupervisorConfig) -> float:
    return min(current_s * 2.0, cfg.backoff_max_s)


# --------------------------------------------------------------------------
# One full relaunch cycle: gate on preflight, launch, watch, return exit info.
# --------------------------------------------------------------------------
def run_supervised(
    cfg: SupervisorConfig, *,
    preflight_fn: Callable[[], "preflight_live.PreflightReport"],
    launcher: Callable[[list[str]], Any],
    mtime_fn: Callable[[Path], float | None],
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.time,
    deals_watcher_check: Callable[[], bool] | None = None,
) -> None:
    """The main supervisor loop. Runs until `cfg.max_iterations` relaunches
    have happened (production: None = forever / Ctrl-C)."""
    if deals_watcher_check is not None:
        if deals_watcher_check():
            _log_watchdog("deals watcher: RUNNING (informational).", log_path=cfg.watchdog_log)
        else:
            _log_watchdog(
                "deals watcher: NOT detected running. This supervisor will NOT "
                "start it -- if you want deal-level parity tracking tonight, "
                "launch it yourself: python -m scripts.live.run_deals_watcher",
                log_path=cfg.watchdog_log)

    backoff = cfg.backoff_initial_s
    iterations = 0
    while cfg.max_iterations is None or iterations < cfg.max_iterations:
        iterations += 1

        ok = wait_for_preflight(cfg, preflight_fn=preflight_fn, sleep_fn=sleep_fn)
        if not ok:
            # Only reachable in tests (max_attempts set) -- production never
            # gives up. Treat as "stop the whole supervisor loop" for tests.
            return

        _log_watchdog(f"launching executor: {' '.join(cfg.executor_argv)}",
                     log_path=cfg.watchdog_log)
        start_ts = now_fn()
        proc = launcher(cfg.executor_argv)

        rc = watch_while_running(cfg, proc, mtime_fn=mtime_fn, now_fn=now_fn,
                                 sleep_fn=sleep_fn)
        uptime = now_fn() - start_ts
        _log_watchdog(f"executor EXITED with code {rc} after {uptime:.0f}s uptime.",
                     log_path=cfg.watchdog_log)

        if uptime >= cfg.backoff_reset_after_s:
            backoff = cfg.backoff_initial_s
        _log_watchdog(f"backing off {backoff:.0f}s before re-checking preflight "
                     "and relaunching.", log_path=cfg.watchdog_log)
        sleep_fn(backoff)
        backoff = next_backoff(backoff, cfg=cfg)


# --------------------------------------------------------------------------
# Production wiring.
# --------------------------------------------------------------------------
def _default_launcher(argv: list[str]) -> subprocess.Popen:
    return subprocess.Popen(argv, cwd=str(REPO_ROOT))


def _default_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _default_deals_watcher_check() -> bool:
    return preflight_live.process_running(DEALS_WATCHER_MARKER)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    cfg = SupervisorConfig(executor_argv=EXECUTOR_ARGV)
    _log_watchdog("=== supervisor_live starting ===", log_path=cfg.watchdog_log)
    try:
        run_supervised(
            cfg,
            preflight_fn=preflight_live.run_all_checks,
            launcher=_default_launcher,
            mtime_fn=_default_mtime,
            deals_watcher_check=_default_deals_watcher_check,
        )
    except KeyboardInterrupt:
        _log_watchdog("Ctrl-C received -- supervisor stopping (executor subprocess, "
                     "if any, is left running; stop it separately if desired).",
                     log_path=cfg.watchdog_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
