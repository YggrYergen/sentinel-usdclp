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
  5. Deals-watcher survivability (2026-07-20): the supervisor now STARTS and
     KEEPS ALIVE the deals watcher (`scripts.live.run_deals_watcher`), not
     just warns. It (re)launches it at startup and re-checks every poll cycle
     of `watch_while_running` (~`stale_recheck_s`), so a watcher that dies on
     a terminal cycle is revived within ~30s instead of staying dead for
     hours (the 2026-07-16 data-loss incident: nothing restarted it). The
     check is idempotent by cmdline marker (`process_running`) -- an
     already-running watcher is never doubled. ATTACH-ONLY is preserved: the
     watcher process re-checks the terminal before initializing MT5; the
     supervisor only spawns the python process.

This module contains NO MetaTrader5 order APIs. All MT5-specific read-only
logic lives in `preflight_live.py` (imported); the executor's own decision
logic in `run_live_20.py` is untouched.

USAGE
    python -m scripts.live.supervisor_live
"""
from __future__ import annotations

import logging
import os
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
EXECUTOR_CONSOLE_LOG = REPO_ROOT / "scripts" / "live" / "executor_console.log"

# Roster the supervisor arms the executor with. DEFAULT STAYS `live` so the
# running machine-1 stack behaves EXACTLY as before. Machine-1 can set
# SUPERVISOR_CONFIGS=live+shadow for in-process verification; the machine-2
# pack sets SUPERVISOR_CONFIGS=shadow (D114: machine-2 arms the FIXED4
# corrected roster ONLY, never the uncorrected live-4) or, per the trader's
# 2026-07-27 machine-2 selection, SUPERVISOR_CONFIGS=tomachine -- which is now
# EXACTLY TWO configs: S6-K2P0 (magic 724010) + SuperTrend-p14x3-M15 (magic
# 724070), both single-ficha and 0.3 lots via the per-config `volume` in
# live_configs_20. (It no longer includes FIXED4/S7-TPNONE/TK-BW2-fix2atr, and
# never included V11-M2/TK-Momentum.) Accepted values mirror run_live_20's
# `--configs`: live |
# shadow | live+shadow | live+tk | golive | golive-dedup | golive-dedup+tk |
# tk-momentum | tomachine | local (machine-1 LOCAL roster: S6-K2P0 +
# S7-TPNONE + SuperTrend-p14x3-M15 @0.1 + TK-Momentum @0.01, NO V11-M2/shadow)
# (or any comma ids).
SUPERVISOR_CONFIGS = os.environ.get("SUPERVISOR_CONFIGS", "live")

# OPTIONAL static HARD spread cap (USD/oz) the supervisor passes through to
# the executor's `--max-spread-open` (see run_live_20.py -- a STATIC HARD cap
# that combines with the adaptive running-min gate by taking the TIGHTER of
# the two; exits/MODIFY/CLOSE are never gated, so risk management (SL/TP/
# trailing) always keeps running regardless of this setting). UNSET (default,
# None) means no static cap is appended at all -- machine-1's argv, and thus
# its behavior, stays byte-identical to before this option existed (adaptive
# gate only). Machine-2 sets SUPERVISOR_MAX_SPREAD_OPEN=0.5 so strategies
# OPEN only at XAUUSD's observed 0.5 minimum spread and simply pause (skip
# the OPEN, retry next cycle) whenever the spread is wider than that.
SUPERVISOR_MAX_SPREAD_OPEN = os.environ.get("SUPERVISOR_MAX_SPREAD_OPEN")

# OPTIONAL blocked-open time window ('HH:MM-HH:MM', 24h) the supervisor passes
# through to the executor's `--blocked-open-window` (see run_live_20.py). Inside
# the window the executor SUPPRESSES NEW POSITION OPENINGS only; MODIFY, CLOSE,
# exits and every other risk-management action are NEVER gated, at any hour.
# The window is compared against LOCAL time, which on these machines IS the
# broker/server time, so 18:00-18:45 means the 18:00-18:45 the trader sees.
# UNSET (default, None) appends NOTHING to the argv -- machine-1's argv, and
# therefore its behavior, stays byte-identical to before this option existed.
# Machine-2 (TOMACHINE) sets SUPERVISOR_BLOCKED_OPEN_WINDOW=18:00-18:45 (via
# `setx`, inherited: user env -> scheduled task SENTINEL_LIVE_TOMACHINE -> the
# watchdog -> this supervisor -> the executor argv), so both the auto-launch at
# logon and every self-heal relaunch preserve the protection.
SUPERVISOR_BLOCKED_OPEN_WINDOW = os.environ.get("SUPERVISOR_BLOCKED_OPEN_WINDOW")

# OPTIONAL kill-switch for the executor's ADAPTIVE open-spread gate, passed
# through as the bare flag `--no-adaptive-spread` (see run_live_20.py:
# dest="adaptive_spread", store_false; the adaptive gate is ON by default).
# The adaptive gate derives its cap from a PERSISTENT ALL-TIME RUNNING MINIMUM
# of the observed spread, and the executor applies the TIGHTER of that cap and
# the static `--max-spread-open` one. On machine-2 (TOMACHINE) that running min
# has ratcheted down to 0.20, so the adaptive cap started binding tighter than
# the owner's intended 0.5 hard cap and EVERY entry was deferred with
# `SPREAD_GATE_SKIP ... spread=0.50000 > cap=0.20000 (adaptive)` even though
# the real 0.50 spread satisfies the owner's rule ("open when spread <= 0.5").
# Disabling the adaptive gate does NOT remove spread protection: the STATIC
# `--max-spread-open` cap (SUPERVISOR_MAX_SPREAD_OPEN=0.5) still applies and is
# the real protection here; exits/MODIFY/CLOSE were never gated either way.
# Accepted (case-insensitive): 1/true/yes/on to disable the adaptive gate,
# 0/false/no/off/empty to keep it. UNSET (default, None) appends NOTHING to the
# argv -- machine-1's argv, and therefore its behavior, stays byte-identical to
# before this option existed.
SUPERVISOR_NO_ADAPTIVE_SPREAD = os.environ.get("SUPERVISOR_NO_ADAPTIVE_SPREAD")

# Explicit truthy/falsy spellings for SUPERVISOR_NO_ADAPTIVE_SPREAD. Anything
# outside these two sets is a typo on a safety-adjacent setting and FAILS LOUD
# (see build_executor_argv) rather than being silently coerced to False.
_NO_ADAPTIVE_SPREAD_TRUE = frozenset({"1", "true", "yes", "on"})
_NO_ADAPTIVE_SPREAD_FALSE = frozenset({"0", "false", "no", "off", ""})


def build_executor_argv(configs: str = SUPERVISOR_CONFIGS,
                        max_spread_open: str | None = SUPERVISOR_MAX_SPREAD_OPEN,
                        blocked_open_window: str | None = SUPERVISOR_BLOCKED_OPEN_WINDOW,
                        no_adaptive_spread: str | None = SUPERVISOR_NO_ADAPTIVE_SPREAD,
                        ) -> list[str]:
    """Builds the argv used to launch the armed executor. `configs` is passed
    straight through to `--configs` (unchanged behavior). `max_spread_open`,
    if set (non-empty string), must parse as a FINITE positive float; it is
    then appended as `--max-spread-open <value>` -- a STATIC HARD cap on top
    of run_live_20's own adaptive gate (see module docstring / run_live_20.py
    for the combining rule and the exits-never-gated guarantee). Unset/empty
    means no cap is appended at all, so the argv (and therefore machine-1's
    behavior when the env var is unset) is byte-identical to before this
    option existed.

    `blocked_open_window`, if set (non-empty string), must be an exact
    'HH:MM-HH:MM' 24h local-time window; it is then appended as
    `--blocked-open-window <value>`, which makes the executor suppress NEW
    POSITION OPENINGS inside it (exits/MODIFY/CLOSE are never gated -- risk
    management always runs). Validation reuses
    `run_live_20.parse_blocked_open_window`, the SAME function the executor
    itself uses, so there is exactly one source of truth about the format.
    Unset/empty means the flag is not appended at all (byte-identical argv).

    `no_adaptive_spread`, if truthy (case-insensitive 1/true/yes/on), appends
    the bare flag `--no-adaptive-spread` LAST, which turns OFF the executor's
    ADAPTIVE running-min open-spread gate (run_live_20's `dest="adaptive_spread"`
    store_false). This is what machine-2 needs: its persistent all-time running
    min ratcheted to 0.20 and began binding tighter than the intended 0.5 hard
    cap, deferring every entry. The STATIC `--max-spread-open` cap still applies
    and remains the real protection. Falsy (0/false/no/off/empty) or unset
    appends nothing at all (byte-identical argv, machine-1 untouched).

    A malformed cap (doesn't parse, non-positive, infinite/NaN), a malformed
    window or an unrecognised `no_adaptive_spread` spelling is FAILED LOUD:
    these are safety settings, and arming the executor with a gate in a state
    the operator did not intend because of a typo would be worse than
    refusing to start at all. The error is logged to watchdog.log and the
    process exits via SystemExit(2) -- callers (e.g. `main()`) are expected to
    let this propagate rather than swallow it."""
    argv = [sys.executable, "-m", "scripts.live.run_live_20", "--arm",
            "--confirm-account", str(guard_cuenta.DEMO_LOGIN),
            "--configs", configs]
    if max_spread_open:
        try:
            value = float(max_spread_open)
            if not (value > 0.0) or value == float("inf"):
                raise ValueError(f"must be a finite positive float, got {value!r}")
        except (TypeError, ValueError) as exc:
            msg = (f"SUPERVISOR_MAX_SPREAD_OPEN={max_spread_open!r} is not a valid "
                   f"positive finite float ({exc}) -- refusing to arm the executor "
                   "without the intended spread-cap safety protection. Fix or unset "
                   "SUPERVISOR_MAX_SPREAD_OPEN and restart.")
            try:
                _log_watchdog(f"FATAL: {msg}")
            except NameError:
                print(msg, file=sys.stderr)
            raise SystemExit(2)
        argv += ["--max-spread-open", str(value)]
    if blocked_open_window:
        # Local import ON PURPOSE: run_live_20 pulls in the whole strategy
        # stack, and a machine with SUPERVISOR_BLOCKED_OPEN_WINDOW unset must
        # not pay (nor risk) that import just to build the argv.
        from scripts.live.run_live_20 import parse_blocked_open_window
        try:
            parse_blocked_open_window(blocked_open_window)
        except ValueError as exc:
            msg = (f"SUPERVISOR_BLOCKED_OPEN_WINDOW={blocked_open_window!r} is not a "
                   f"valid 'HH:MM-HH:MM' 24h local-time window ({exc}) -- refusing "
                   "to arm the executor WITHOUT the requested open-time protection. "
                   "Fix or unset SUPERVISOR_BLOCKED_OPEN_WINDOW and restart.")
            try:
                _log_watchdog(f"FATAL: {msg}")
            except NameError:
                print(msg, file=sys.stderr)
            raise SystemExit(2)
        argv += ["--blocked-open-window", blocked_open_window]
    if no_adaptive_spread is not None:
        token = str(no_adaptive_spread).strip().lower()
        if token not in _NO_ADAPTIVE_SPREAD_TRUE and token not in _NO_ADAPTIVE_SPREAD_FALSE:
            msg = (f"SUPERVISOR_NO_ADAPTIVE_SPREAD={no_adaptive_spread!r} is not a "
                   "recognised boolean -- accepted values are "
                   f"{sorted(_NO_ADAPTIVE_SPREAD_TRUE)} (disable the adaptive "
                   f"spread gate) or {sorted(_NO_ADAPTIVE_SPREAD_FALSE - {''})} / "
                   "empty (keep it), case-insensitive. Refusing to arm the executor "
                   "with a spread gate whose state the operator cannot have intended. "
                   "Fix or unset SUPERVISOR_NO_ADAPTIVE_SPREAD and restart.")
            try:
                _log_watchdog(f"FATAL: {msg}")
            except NameError:
                print(msg, file=sys.stderr)
            raise SystemExit(2)
        if token in _NO_ADAPTIVE_SPREAD_TRUE:
            argv += ["--no-adaptive-spread"]
    return argv


EXECUTOR_ARGV = build_executor_argv()
DEALS_WATCHER_MARKER = "run_deals_watcher"
# Argv the supervisor (re)launches the read-only deals watcher with. Poll 5s.
WATCHER_ARGV = [sys.executable, "-m", "scripts.live.run_deals_watcher", "--poll", "5"]
WATCHER_CONSOLE_LOG = REPO_ROOT / "scripts" / "live" / "watcher_console.log"
BARS_INGESTER_MARKER = "run_bars_ingester"
# Argv the supervisor (re)launches the read-only incremental bars ingester with.
# SYMBOL SCOPE (2026-07-22, machine "TOMACHINE"): the trader only needs the
# three TARGET symbols (XAUUSD, NQ100, USDCLP) -- the macro/context symbols
# (XAGUSD, EURUSD, SP, ...) are neither wanted nor traded. Restricting the
# ingester to just these three (via its existing --symbols filter) both honors
# that and shrinks the ingester's MT5 footprint from 16 symbols x 6 timeframes
# to 3 x 6, cutting the read-only IPC load on the shared terminal (defense in
# depth against the multi-client IPC contention that caused the freeze
# incidents). The executor itself does NOT depend on this lake -- it fetches
# its own bars straight from MT5 (run_live_20.fetch_bars) -- so this only
# scopes what the UI/lake keeps current. Override with SUPERVISOR_INGEST_SYMBOLS
# (comma-separated) if a machine needs a different set.
_INGEST_SYMBOLS = [s.strip() for s in os.environ.get(
    "SUPERVISOR_INGEST_SYMBOLS", "XAUUSD,NQ100,USDCLP").split(",") if s.strip()]
BARS_INGESTER_ARGV = [sys.executable, "-m", "scripts.live.run_bars_ingester"]
for _sym in _INGEST_SYMBOLS:
    BARS_INGESTER_ARGV += ["--symbols", _sym]
BARS_INGESTER_CONSOLE_LOG = REPO_ROOT / "scripts" / "live" / "bars_ingester_console.log"

BACKOFF_INITIAL_S = 30.0
BACKOFF_MAX_S = 600.0  # 10 minutes
BACKOFF_RESET_AFTER_S = 600.0  # a run that survives this long resets backoff
PREFLIGHT_RETRY_S = 60.0  # wait between preflight re-checks while it's failing
STALE_AFTER_S = 5 * 60.0
STALE_RECHECK_S = 30.0  # how often the running-executor loop polls
# SELF-HEAL (2026-07-22, machine "TOMACHINE"): after the audit log has been
# stale (age > STALE_AFTER_S) for this many CONSECUTIVE rechecks, kill the
# frozen executor so its existing relaunch path produces a clean one. With the
# defaults (alarm at 300s, recheck every 30s, kill after 3 consecutive stale
# rechecks) the executor is killed once it has been frozen for ~390s, i.e. we
# alarm first and only escalate to a kill if it stays frozen. Set to <= 0 to
# disable (pure alarm-only). Overridable via SUPERVISOR_STALE_KILL_AFTER (env).
STALE_KILL_AFTER_CONSECUTIVE = int(os.environ.get("SUPERVISOR_STALE_KILL_AFTER", "3"))

logger = logging.getLogger("supervisor_live")


def _log_watchdog(msg: str, *, log_path: Path = WATCHDOG_LOG) -> None:
    """Append one UTF-8 timestamped line to watchdog.log. File-only, on
    purpose: this used to also echo via `logger.info(msg)` (console,
    StreamHandler), but on 2026-07-15 a Windows console write blocked
    forever (QuickEdit selection / conhost stall) and froze this exact
    call inside `watch_while_running`'s staleness alarm, taking the whole
    supervisor down along with the executor it was supposed to be
    watchdogging. watchdog.log (file) is now the sole authoritative sink --
    it cannot block on a console. Never raises -- a logging failure must
    not take down the supervisor."""
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 -- logging must never crash the supervisor
        logger.exception("failed to append to watchdog.log")


@dataclass
class SupervisorConfig:
    executor_argv: list[str]
    watcher_argv: list[str] | None = None
    bars_ingester_argv: list[str] | None = None
    watchdog_log: Path = WATCHDOG_LOG
    audit_log: Path = AUDIT_LOG
    backoff_initial_s: float = BACKOFF_INITIAL_S
    backoff_max_s: float = BACKOFF_MAX_S
    backoff_reset_after_s: float = BACKOFF_RESET_AFTER_S
    preflight_retry_s: float = PREFLIGHT_RETRY_S
    stale_after_s: float = STALE_AFTER_S
    stale_recheck_s: float = STALE_RECHECK_S
    # SELF-HEAL (2026-07-22): number of CONSECUTIVE stale rechecks after which
    # the supervisor kills the frozen executor to force a clean relaunch. The
    # audit log first has to cross `stale_after_s` (alarm), then stay stale for
    # this many polls before the kill fires -- so a healthy executor (which
    # rewrites the audit log every ~15-20s) never trips it. <= 0 disables the
    # kill entirely (pure alarm-only, machine-1's original behavior).
    stale_kill_after_consecutive: int = STALE_KILL_AFTER_CONSECUTIVE
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
# Deals-watcher survivability: (re)launch it if it isn't running.
# --------------------------------------------------------------------------
def ensure_watcher_running(cfg: SupervisorConfig, *,
                           is_running_fn: Callable[[], bool],
                           launcher: Callable[[list[str]], Any]) -> bool:
    """(Re)launch the read-only deals watcher if it is not currently running.
    Idempotent: `is_running_fn` detects an existing watcher by cmdline marker,
    so an already-running one (including one started by hand) is never
    doubled. ATTACH-ONLY is preserved -- the watcher process re-checks the
    terminal before touching MT5; we only spawn the python process. Returns
    True iff a launch happened. No-op (returns False) when `watcher_argv` is
    None."""
    if cfg.watcher_argv is None:
        return False
    if is_running_fn():
        return False
    _log_watchdog("deals watcher: NOT running -- launching it (survivability, "
                  "so deals_raw is always being written).",
                  log_path=cfg.watchdog_log)
    launcher(cfg.watcher_argv)
    return True


# --------------------------------------------------------------------------
# Bars-ingester survivability: (re)launch it if it isn't running.
# --------------------------------------------------------------------------
def ensure_bars_ingester_running(cfg: SupervisorConfig, *,
                                 is_running_fn: Callable[[], bool],
                                 launcher: Callable[[list[str]], Any]) -> bool:
    """(Re)launch the read-only incremental bars ingester if it is not
    currently running. Idempotent: `is_running_fn` detects an existing
    ingester by cmdline marker, so an already-running one (including one
    started by hand) is never doubled. READ-ONLY is preserved -- the ingester
    process only reads price history; we only spawn the python process.
    Returns True iff a launch happened. No-op (returns False) when
    `bars_ingester_argv` is None."""
    if cfg.bars_ingester_argv is None:
        return False
    if is_running_fn():
        return False
    _log_watchdog("bars ingester: NOT running -- launching it (survivability, "
                  "so the OHLC lake is always kept current).",
                  log_path=cfg.watchdog_log)
    launcher(cfg.bars_ingester_argv)
    return True


# --------------------------------------------------------------------------
# Staleness watch: polls while the executor subprocess is alive.
# --------------------------------------------------------------------------
def watch_while_running(cfg: SupervisorConfig, proc: Any, *,
                        mtime_fn: Callable[[Path], float | None],
                        now_fn: Callable[[], float] = time.time,
                        sleep_fn: Callable[[float], None] = time.sleep,
                        watcher_keepalive: Callable[[], None] | None = None,
                        kill_fn: Callable[[Any], None] | None = None) -> int:
    """Polls `proc.poll()` every `stale_recheck_s` while the executor runs.
    Logs (repeatable) ALARM lines if the audit log hasn't been touched for
    more than `stale_after_s`. If `watcher_keepalive` is given, it is invoked
    on every poll cycle (so a dead deals watcher is revived within
    ~`stale_recheck_s`, not only between executor relaunches).

    SELF-HEAL (2026-07-22): if `kill_fn` is provided and staleness persists for
    `cfg.stale_kill_after_consecutive` CONSECUTIVE rechecks (> 0), the executor
    is killed via `kill_fn(proc)` so the caller's relaunch path produces a
    clean one -- this turns the old alarm-only watch into real self-healing.
    With `kill_fn=None` or `stale_kill_after_consecutive <= 0` the behavior is
    byte-identical to the previous alarm-only version (machine-1 immutability).

    Returns the process's exit code once it exits."""
    was_stale = False
    consecutive_stale = 0
    kill_enabled = kill_fn is not None and cfg.stale_kill_after_consecutive > 0
    while True:
        rc = proc.poll()
        if rc is not None:
            return rc

        if watcher_keepalive is not None:
            watcher_keepalive()

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
            consecutive_stale += 1
            _log_watchdog(
                f"ALARM: audit log stale (age={age_str}, limit={cfg.stale_after_s:.0f}s, "
                f"consecutive={consecutive_stale}) -- executor process is alive but may "
                "not be completing cycles.",
                log_path=cfg.watchdog_log)
            was_stale = True

            if kill_enabled and consecutive_stale >= cfg.stale_kill_after_consecutive:
                _log_watchdog(
                    f"SELF-HEAL: audit log stale for {consecutive_stale} consecutive "
                    f"rechecks (age={age_str}) -- KILLING the frozen executor to force a "
                    "clean relaunch (preflight + backoff + launch will follow).",
                    log_path=cfg.watchdog_log)
                try:
                    kill_fn(proc)
                except Exception as exc:  # noqa: BLE001 -- a kill failure must not crash the supervisor
                    _log_watchdog(f"SELF-HEAL: kill_fn raised {exc!r} -- will retry next "
                                  "threshold.", log_path=cfg.watchdog_log)
                # Reset so we don't immediately re-kill on the next iteration;
                # the kill should make the very next poll() return an exit code.
                consecutive_stale = 0
                sleep_fn(cfg.stale_recheck_s)
                continue
        else:
            consecutive_stale = 0
            if was_stale:
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
    watcher_keepalive: Callable[[], None] | None = None,
    kill_fn: Callable[[Any], None] | None = None,
) -> None:
    """The main supervisor loop. Runs until `cfg.max_iterations` relaunches
    have happened (production: None = forever / Ctrl-C). If `watcher_keepalive`
    is given, it is invoked at startup and on every executor poll cycle to
    keep the deals watcher alive. If `kill_fn` is given, the staleness watch
    self-heals by killing a frozen executor (see `watch_while_running`)."""
    if watcher_keepalive is not None:
        watcher_keepalive()  # start the watcher immediately (survivability)

    backoff = cfg.backoff_initial_s
    iterations = 0
    while cfg.max_iterations is None or iterations < cfg.max_iterations:
        iterations += 1

        ok = wait_for_preflight(cfg, preflight_fn=preflight_fn, sleep_fn=sleep_fn)
        if not ok:
            # Only reachable in tests (max_attempts set) -- production never
            # gives up. Treat as "stop the whole supervisor loop" for tests.
            return

        if watcher_keepalive is not None:
            watcher_keepalive()  # also revive it between executor relaunches

        _log_watchdog(f"launching executor: {' '.join(cfg.executor_argv)}",
                     log_path=cfg.watchdog_log)
        start_ts = now_fn()
        proc = launcher(cfg.executor_argv)

        rc = watch_while_running(cfg, proc, mtime_fn=mtime_fn, now_fn=now_fn,
                                 sleep_fn=sleep_fn, watcher_keepalive=watcher_keepalive,
                                 kill_fn=kill_fn)
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
    # stdout/stderr are redirected to an append-mode file, NEVER inherited
    # from this process's console. On 2026-07-15 the executor was launched
    # with inherited stdio, sharing one console with the supervisor; a
    # Windows console write-block (QuickEdit selection / conhost stall) hung
    # BOTH processes simultaneously (the executor's own `logger.info` emit,
    # and the supervisor's staleness-alarm `logger.info` emit into the same
    # console). run_live_20.py's audit-log FileHandler remains the primary
    # record and is unaffected by this -- this redirection only prevents the
    # executor's own console-bound handlers from ever blocking.
    EXECUTOR_CONSOLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(EXECUTOR_CONSOLE_LOG, "a", encoding="utf-8", buffering=1) as console_fh:
        # Popen dup()s the fd/handle for the child; safe to close our copy
        # (and let the `with` block do so) once the child owns its own.
        return subprocess.Popen(argv, cwd=str(REPO_ROOT), stdout=console_fh,
                                stderr=console_fh)


def _default_watcher_launcher(argv: list[str]) -> subprocess.Popen:
    """Launch the read-only deals watcher as a detached-stdio subprocess (its
    own console log, never inheriting this process's console -- same rationale
    as `_default_launcher`). The watcher re-checks ATTACH-ONLY itself."""
    WATCHER_CONSOLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHER_CONSOLE_LOG, "a", encoding="utf-8", buffering=1) as console_fh:
        return subprocess.Popen(argv, cwd=str(REPO_ROOT), stdout=console_fh,
                                stderr=console_fh)


def _default_bars_ingester_launcher(argv: list[str]) -> subprocess.Popen:
    """Launch the read-only incremental bars ingester as a detached-stdio
    subprocess (its own console log, never inheriting this process's console --
    same rationale as `_default_launcher`). The ingester only reads price
    history."""
    BARS_INGESTER_CONSOLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(BARS_INGESTER_CONSOLE_LOG, "a", encoding="utf-8", buffering=1) as console_fh:
        return subprocess.Popen(argv, cwd=str(REPO_ROOT), stdout=console_fh,
                                stderr=console_fh)


def _default_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _default_kill(proc: subprocess.Popen) -> None:
    """SELF-HEAL kill for a frozen executor. On Windows `terminate()` maps to
    TerminateProcess, which forcibly kills even a process blocked inside a
    native MT5 IPC call (the freeze signature) -- a graceful signal would not
    reach it. Best-effort: any failure is swallowed by the caller so the
    supervisor never crashes on a kill attempt."""
    proc.kill()


def _default_deals_watcher_check() -> bool:
    return preflight_live.process_running(DEALS_WATCHER_MARKER)


def _default_bars_ingester_check() -> bool:
    return preflight_live.process_running(BARS_INGESTER_MARKER)


def main(argv: list[str] | None = None) -> int:
    # No console StreamHandler here, deliberately: this process may be spawned
    # with a detached/minimized/inherited console (as it was on 2026-07-15),
    # and a Windows console write-block (QuickEdit selection / conhost stall)
    # can hang a console write forever. watchdog.log (via `_log_watchdog`,
    # file-only) is the sole authoritative log sink for this module -- it
    # cannot block on a console. `logging` is left at its default (silent)
    # config; nothing in this module calls `logger.info`/etc. for output that
    # matters, only `_log_watchdog`.
    cfg = SupervisorConfig(executor_argv=EXECUTOR_ARGV, watcher_argv=WATCHER_ARGV,
                           bars_ingester_argv=BARS_INGESTER_ARGV)
    _log_watchdog("=== supervisor_live starting ===", log_path=cfg.watchdog_log)

    def _watcher_keepalive() -> None:
        ensure_watcher_running(
            cfg,
            is_running_fn=_default_deals_watcher_check,
            launcher=_default_watcher_launcher,
        )
        ensure_bars_ingester_running(
            cfg,
            is_running_fn=_default_bars_ingester_check,
            launcher=_default_bars_ingester_launcher,
        )

    try:
        run_supervised(
            cfg,
            preflight_fn=preflight_live.run_all_checks,
            launcher=_default_launcher,
            mtime_fn=_default_mtime,
            watcher_keepalive=_watcher_keepalive,
            kill_fn=_default_kill,
        )
    except KeyboardInterrupt:
        _log_watchdog("Ctrl-C received -- supervisor stopping (executor subprocess, "
                     "if any, is left running; stop it separately if desired).",
                     log_path=cfg.watchdog_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
