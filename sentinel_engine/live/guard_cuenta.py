"""sentinel_engine.live.guard_cuenta -- HARD account guard for the live
executor (SENTINEL, 2026-07-13). ORDER-CAPABLE SAFETY MODULE.

SINGLE SOURCE OF TRUTH: `D:/FOREX/CUENTAS.md`.
  DEMO 2883016567 (this machine's sanctioned 30M CLP demo, server Capitaria-All,
    standard install `C:\\Program Files\\Capitaria MT5 Terminal\\terminal64.exe`;
    adapted 2026-07-14 from the original teammate value 2883015767, which used
    a portable install on a different machine)
    -> the ONLY account where operating is permitted.
  REAL 2883011573 -> READ-ONLY, NEVER operate.

Every order-capable entry point MUST call `assert_demo(mt5)` AFTER connecting
and BEFORE any order, AND re-call it each reconcile cycle. On any mismatch the
guard raises `GuardError` and (via `assert_demo(..., hard_exit=True)`, the
default) hard-exits the process -- the executor must never proceed against an
account it cannot positively confirm is the demo.

This module imports NOTHING from MetaTrader5; the `mt5` module is injected so
the guard is fully unit-testable with a mock and cannot itself trigger a
terminal launch.
"""
from __future__ import annotations

import sys
from typing import Any

# CUENTAS.md single source of truth (2026-07-13). Hard-coded on purpose: the
# guard must not depend on any mutable config to know which login is tradable.
DEMO_LOGIN = 2883016567  # this machine's sanctioned 30M CLP demo (Capitaria-All),
# adapted 2026-07-14; original teammate value was 2883015767 (different machine).
REAL_LOGIN = 2883011573

# MetaTrader5 ACCOUNT_TRADE_MODE_* enum values (stable API constants):
#   0 = DEMO, 1 = CONTEST, 2 = REAL. We accept DEMO only.
TRADE_MODE_DEMO = 0
TRADE_MODE_CONTEST = 1
TRADE_MODE_REAL = 2


class GuardError(RuntimeError):
    """Raised when the connected account is NOT the sanctioned demo."""


def assert_demo(mt5_module: Any, *, hard_exit: bool = True) -> int:
    """Verify the account `mt5_module` is currently attached to is the
    sanctioned DEMO (login 2883016567, trade_mode DEMO). Returns the confirmed
    login on success. On ANY failure raises `GuardError`; if `hard_exit` is
    True (default) the process is terminated with `sys.exit(2)` after logging
    -- an order-capable caller must NEVER continue past a failed guard.

    Checks, in order:
      1. `account_info()` returns something (not None / not raising).
      2. `login == DEMO_LOGIN` (and, defensively, is NOT `REAL_LOGIN`).
      3. `trade_mode == TRADE_MODE_DEMO` (rejects CONTEST and REAL).
    """
    def _fail(msg: str) -> None:
        full = f"[GUARD] REFUSING TO OPERATE: {msg}"
        print(full, file=sys.stderr, flush=True)
        if hard_exit:
            # Hard stop: never let an order-capable path run on. exit code 2.
            sys.exit(2)
        raise GuardError(full)

    try:
        info = mt5_module.account_info()
    except Exception as exc:  # noqa: BLE001 -- any failure = do not operate
        _fail(f"account_info() raised {exc!r}")
        raise  # unreachable when hard_exit, keeps type-checkers happy

    if info is None:
        _fail("account_info() returned None (not connected / attach failed)")
        raise GuardError("unreachable")

    login = getattr(info, "login", None)
    trade_mode = getattr(info, "trade_mode", None)

    if login is None:
        _fail("account_info() has no 'login' field")
        raise GuardError("unreachable")

    if login == REAL_LOGIN:
        _fail(f"connected to the REAL account {login} -- HARD FORBIDDEN "
              "(CUENTAS.md rule: read-only, never operate)")
        raise GuardError("unreachable")

    if login != DEMO_LOGIN:
        _fail(f"login {login} is not the sanctioned DEMO {DEMO_LOGIN}")
        raise GuardError("unreachable")

    if trade_mode is None:
        _fail("account_info() has no 'trade_mode' field")
        raise GuardError("unreachable")

    if trade_mode != TRADE_MODE_DEMO:
        name = {TRADE_MODE_CONTEST: "CONTEST", TRADE_MODE_REAL: "REAL"}.get(
            trade_mode, f"code {trade_mode}")
        _fail(f"login {login} matches DEMO but trade_mode is {name}, not DEMO "
              "-- refusing (a real/contest account must never be operated)")
        raise GuardError("unreachable")

    return int(login)
