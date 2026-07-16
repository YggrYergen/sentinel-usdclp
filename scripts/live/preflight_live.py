r"""scripts/live/preflight_live.py -- READ-ONLY preflight checklist for the
live executor (SENTINEL, 2026-07-15). NOT ORDER-CAPABLE.

WHY: the overnight incident on 2026-07-14 (executor died at 12:13:22 when the
MT5 IPC link broke -- guard-detected, exit code 2, by design) went silent
because nothing re-verified preconditions and relaunched. This module is the
single place that answers "is it currently safe/possible to (re)launch the
executor?" for both a human (`python -m scripts.live.preflight_live`) and the
supervisor daemon (`scripts/live/supervisor_live.py`, which imports and calls
`run_all_checks()` before every launch attempt).

CHECKS (all read-only, no state changes, no orders):
  1. portable-terminal-running -- same process-inspection technique as
     `run_live_20._portable_running` (ATTACH-ONLY: we only ever CHECK, never
     launch `terminal64.exe`).
  2. mt5-attach -- read-only `mt5.initialize(path=..., portable=True)` against
     the portable exe, immediately followed by `mt5.shutdown()`. We do not
     hold the connection open.
  3. account-guard -- delegates to `sentinel_engine.live.guard_cuenta.assert_demo`
     (imported, not duplicated) with `hard_exit=False` so a failure is a normal
     FAIL line here instead of killing the whole preflight run.
  4. fresh-bars -- `copy_rates_from_pos(XAUUSD, M2, 0, 100)` returns >= 100 bars
     and the newest CLOSED bar (second-to-last row; the last is the still
     forming bar, same convention as `run_live_20.fetch_bars`) is recent
     relative to the broker's OWN clock (`account_info().server_time` when
     available, else `datetime.now(timezone.utc)` as a fallback -- see
     MT5-clocks-are-server-time note: all timestamps in this repo are broker
     server time, so we compare bar time to server time, not to naive local
     wall clock).
  5. roster-resolves -- importing `sentinel_engine.strategies.live_configs_20`
     yields exactly the 4 `LIVE_ROSTER` ids, each present in `CONFIGS_20`.
  6. stop-file-absent -- `scripts/live/STOP` must NOT exist (if present:
     explicit FAIL "trading paused via kill-switch").
  7. audit-log-writable -- the directory containing
     `scripts/live/run_live_20.audit.log` is writable (append a zero-byte
     probe write is avoided; we just check `os.access(..., os.W_OK)` on the
     parent dir, and if the log file already exists, on the file itself too).

This module NEVER sends an order and NEVER calls `mt5.initialize()` unless
the attach check (1) already passed -- ATTACH-ONLY is preserved exactly like
`run_live_20.py` and `run_deals_watcher.py`.

USAGE
    python -m scripts.live.preflight_live
    python -m scripts.live.preflight_live --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.live import guard_cuenta  # noqa: E402

STOP_FILE = REPO_ROOT / "scripts" / "live" / "STOP"
AUDIT_LOG = REPO_ROOT / "scripts" / "live" / "run_live_20.audit.log"

# CUENTAS.md: the DEMO portable install. Mirrors run_live_20.PORTABLE_EXE.
PORTABLE_EXE = Path(r"D:\FOREX\MT5_Portable\terminal64.exe")
PORTABLE_MARKER = "mt5_portable"

SYMBOL = "XAUUSD"
MIN_BARS = 100
MAX_BAR_AGE_S = 15 * 60  # M2 bars close every 120s; 15 min is generously stale


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class PreflightReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append(CheckResult(name, ok, detail))

    def summary_lines(self) -> list[str]:
        lines = []
        for c in self.checks:
            tag = "PASS" if c.ok else "FAIL"
            lines.append(f"[{tag}] {c.name}: {c.detail}")
        lines.append(f"==> preflight {'PASS' if self.ok else 'FAIL'} "
                     f"({sum(c.ok for c in self.checks)}/{len(self.checks)} checks OK)")
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


# --------------------------------------------------------------------------
# Check 1: portable terminal running (ATTACH-ONLY -- read-only inspection).
# --------------------------------------------------------------------------
def portable_running(marker: str = PORTABLE_MARKER) -> bool:
    """True iff a running process' command line references the DEMO portable
    install path. Identical technique to `run_live_20._portable_running`
    (wmic primary, PowerShell CIM fallback) -- duplicated intentionally
    (not imported) so this module has zero import-time dependency on the
    order-capable executor module; the logic itself is copied verbatim."""
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='terminal64.exe'",
             "get", "CommandLine,ExecutablePath", "/format:list"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:  # noqa: BLE001
        out = ""
    if out:
        return any(marker in line.lower() for line in out.splitlines())
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"name='terminal64.exe'\" "
             "| Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=25,
        ).stdout
    except Exception:  # noqa: BLE001
        out = ""
    return any(marker in line.lower() for line in out.splitlines())


# --------------------------------------------------------------------------
# Process detection helper (also used to report the deals watcher status from
# the supervisor -- exposed here so both modules share one implementation).
# --------------------------------------------------------------------------
def process_running(cmdline_marker: str) -> bool:
    """True iff any running `python.exe`/`pythonw.exe` process' command line
    contains `cmdline_marker` (case-insensitive substring). Read-only, same
    wmic/PowerShell technique as `portable_running`."""
    try:
        out = subprocess.run(
            ["wmic", "process", "where",
             "(name='python.exe' or name='pythonw.exe')",
             "get", "CommandLine", "/format:list"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:  # noqa: BLE001
        out = ""
    if out:
        return any(cmdline_marker.lower() in line.lower() for line in out.splitlines())
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"name='python.exe' or "
             "name='pythonw.exe'\" | Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=25,
        ).stdout
    except Exception:  # noqa: BLE001
        out = ""
    return any(cmdline_marker.lower() in line.lower() for line in out.splitlines())


# --------------------------------------------------------------------------
# Individual checks. Each takes the shared `mt5` module (or None if the
# terminal-running check already failed) and appends to `report`.
# --------------------------------------------------------------------------
def check_portable_running(report: PreflightReport, *,
                           checker: Callable[[], bool] = portable_running) -> bool:
    ok = checker()
    detail = ("portable terminal64.exe (D:\\FOREX\\MT5_Portable) is running"
               if ok else
               "portable terminal NOT detected -- open it by hand via "
               "D:\\FOREX\\MT5_DEMO_TOMAS.bat (this script never launches it)")
    report.add("portable-terminal-running", ok, detail)
    return ok


def check_mt5_attach(report: PreflightReport, mt5: Any) -> bool:
    """Read-only attach + immediate shutdown. Returns True on success."""
    try:
        ok = bool(mt5.initialize(path=str(PORTABLE_EXE), portable=True))
    except Exception as exc:  # noqa: BLE001
        report.add("mt5-attach", False, f"initialize() raised {exc!r}")
        return False
    if not ok:
        err = None
        try:
            err = mt5.last_error()
        except Exception:  # noqa: BLE001
            pass
        report.add("mt5-attach", False, f"initialize() returned False (last_error={err})")
        return False
    report.add("mt5-attach", True, f"initialize(path={PORTABLE_EXE}, portable=True) OK")
    return True


def check_account_guard(report: PreflightReport, mt5: Any) -> bool:
    try:
        login = guard_cuenta.assert_demo(mt5, hard_exit=False)
    except guard_cuenta.GuardError as exc:
        report.add("account-guard", False, str(exc))
        return False
    except Exception as exc:  # noqa: BLE001
        report.add("account-guard", False, f"assert_demo raised {exc!r}")
        return False
    report.add("account-guard", True,
               f"account_info().login == {login} (DEMO, trade_mode OK)")
    return True


def check_fresh_bars(report: PreflightReport, mt5: Any, *,
                     symbol: str = SYMBOL, min_bars: int = MIN_BARS,
                     max_age_s: float = MAX_BAR_AGE_S,
                     now_server: datetime | None = None) -> bool:
    """>= min_bars M2 bars available and the newest CLOSED bar (index -2; the
    last row is the still-forming bar) is within max_age_s of the broker
    server clock. `now_server` lets callers/tests inject the broker's own
    clock instead of relying on `datetime.now()` (MT5 clocks are server
    time -- UTC-4, not local wall clock)."""
    try:
        timeframe = getattr(mt5, "TIMEFRAME_M2")
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, min_bars + 1)
    except Exception as exc:  # noqa: BLE001
        report.add("fresh-bars", False, f"copy_rates_from_pos raised {exc!r}")
        return False
    if rates is None or len(rates) < min_bars + 1:
        got = 0 if rates is None else len(rates)
        report.add("fresh-bars", False,
                   f"copy_rates_from_pos({symbol}, M2) returned {got} bars, "
                   f"need >= {min_bars + 1} (incl. forming bar)")
        return False

    closed_bar_t = int(rates[-2]["time"])
    if now_server is None:
        server_ts = _server_now_ts(mt5)
    else:
        server_ts = now_server.timestamp()
    age_s = server_ts - closed_bar_t
    if age_s < 0:
        # closed bar "in the future" relative to our clock estimate -- treat
        # as fresh (clock skew, not staleness) rather than failing spuriously.
        age_s = 0.0
    ok = age_s <= max_age_s
    bar_iso = datetime.fromtimestamp(closed_bar_t, tz=timezone.utc).isoformat()
    detail = (f"{len(rates)} M2 bars available; newest CLOSED bar {bar_iso} "
             f"is {age_s:.0f}s old (limit {max_age_s:.0f}s)")
    report.add("fresh-bars", ok, detail)
    return ok


def _server_now_ts(mt5: Any) -> float:
    """Best-effort broker server clock. `account_info()` doesn't carry a
    server timestamp in the MT5 API, so the most reliable read-only proxy is
    the last tick's time; falls back to naive UTC now if unavailable (only
    matters for the staleness margin, which is generous)."""
    try:
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick is not None:
            t = getattr(tick, "time", None)
            if t:
                return float(t)
    except Exception:  # noqa: BLE001
        pass
    return datetime.now(timezone.utc).timestamp()


def check_roster_resolves(report: PreflightReport) -> bool:
    try:
        from sentinel_engine.strategies.live_configs_20 import CONFIGS_20, LIVE_ROSTER
    except Exception as exc:  # noqa: BLE001
        report.add("roster-resolves", False, f"import failed: {exc!r}")
        return False
    ids_20 = {c["id"] for c in CONFIGS_20}
    missing = [cid for cid in LIVE_ROSTER if cid not in ids_20]
    ok = len(LIVE_ROSTER) == 4 and len(set(LIVE_ROSTER)) == 4 and not missing
    if ok:
        detail = f"LIVE_ROSTER resolves to 4 unique configs: {list(LIVE_ROSTER)}"
    else:
        detail = (f"LIVE_ROSTER={list(LIVE_ROSTER)} (len={len(LIVE_ROSTER)}, "
                 f"unique={len(set(LIVE_ROSTER))}, missing_from_CONFIGS_20={missing})")
    report.add("roster-resolves", ok, detail)
    return ok


def check_stop_file_absent(report: PreflightReport, *,
                           stop_file: Path = STOP_FILE) -> bool:
    present = stop_file.exists()
    if present:
        report.add("stop-file-absent", False,
                   f"trading PAUSED: kill-switch file present at {stop_file} "
                   "-- run REANUDAR_TRADING.bat to resume opens (existing "
                   "positions are still managed regardless).")
        return False
    report.add("stop-file-absent", True, f"{stop_file} absent (opens allowed)")
    return True


def check_audit_log_writable(report: PreflightReport, *,
                             audit_log: Path = AUDIT_LOG) -> bool:
    parent = audit_log.parent
    if not parent.exists():
        report.add("audit-log-writable", False, f"directory does not exist: {parent}")
        return False
    if audit_log.exists():
        ok = os.access(audit_log, os.W_OK)
        detail = f"{audit_log} exists and is {'writable' if ok else 'NOT writable'}"
    else:
        ok = os.access(parent, os.W_OK)
        detail = f"{audit_log} does not exist yet; parent dir is {'writable' if ok else 'NOT writable'}"
    report.add("audit-log-writable", ok, detail)
    return ok


# --------------------------------------------------------------------------
# Orchestration.
# --------------------------------------------------------------------------
def run_all_checks(*, mt5_module: Any = None,
                   attach_checker: Callable[[], bool] = portable_running,
                   now_server: datetime | None = None) -> PreflightReport:
    """Run every check in order, short-circuiting the MT5-dependent checks
    (attach/guard/fresh-bars) if the terminal isn't running -- we NEVER call
    `mt5.initialize()` otherwise (ATTACH-ONLY). Roster/STOP/audit-log checks
    always run regardless (they don't touch MT5). Always returns a full
    report; never raises for expected failure modes."""
    report = PreflightReport()

    terminal_ok = check_portable_running(report, checker=attach_checker)

    if terminal_ok:
        mt5 = mt5_module
        if mt5 is None:
            import MetaTrader5 as mt5  # noqa: N813 -- only imported once attach-confirmed
        attach_ok = check_mt5_attach(report, mt5)
        if attach_ok:
            check_account_guard(report, mt5)
            check_fresh_bars(report, mt5, now_server=now_server)
            try:
                mt5.shutdown()
            except Exception:  # noqa: BLE001
                pass
        else:
            report.add("account-guard", False, "skipped: mt5-attach failed")
            report.add("fresh-bars", False, "skipped: mt5-attach failed")
    else:
        report.add("mt5-attach", False, "skipped: portable terminal not running")
        report.add("account-guard", False, "skipped: portable terminal not running")
        report.add("fresh-bars", False, "skipped: portable terminal not running")

    check_roster_resolves(report)
    check_stop_file_absent(report)
    check_audit_log_writable(report)

    return report


def main(argv: list[str] | None = None, *, mt5_module: Any = None,
        attach_checker: Callable[[], bool] = portable_running) -> int:
    ap = argparse.ArgumentParser(
        description="Read-only preflight checklist for the live executor.")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON output")
    args = ap.parse_args(argv)

    report = run_all_checks(mt5_module=mt5_module, attach_checker=attach_checker)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for line in report.summary_lines():
            print(line)

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
