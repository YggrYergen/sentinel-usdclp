"""sentinel_engine.live.guard_cuenta -- HARD account guard for the live
executor (SENTINEL, 2026-07-13). ORDER-CAPABLE SAFETY MODULE.

SINGLE SOURCE OF TRUTH: `D:/FOREX/CUENTAS.md`.
  Two machines share this branch, each with its OWN sanctioned DEMO login:
    - 2883015767 (Machine 1, portable install
      `D:\\FOREX\\MT5_Portable\\terminal64.exe`)
    - 2883016567 (Machine "TOMACHINE", 30M CLP demo, server Capitaria-All,
      standard install `C:\\Program Files\\Capitaria MT5 Terminal\\terminal64.exe`)
  Both are permitted logins; which ONE is expected on a given machine is
  selected by `sentinel_engine.live.machine_profile` (see that module) --
  but the profile can only SELECT within this hard-coded set, never EXTEND
  it. A malicious or corrupted `machine_local.json` cannot make an
  unsanctioned login tradable.
  REAL 2883011573 -> READ-ONLY, NEVER operate, on either machine.

Every order-capable entry point MUST call `assert_demo(mt5)` AFTER connecting
and BEFORE any order, AND re-call it each reconcile cycle. On any mismatch the
guard raises `GuardError` and (via `assert_demo(..., hard_exit=True)`, the
default) hard-exits the process -- the executor must never proceed against an
account it cannot positively confirm is the demo.

This module imports NOTHING from MetaTrader5; the `mt5` module is injected so
the guard is fully unit-testable with a mock and cannot itself trigger a
terminal launch.

PRINCIPLE (unchanged since 2026-07-13, restated 2026-07-15 for two machines):
the guard must not depend on any MUTABLE config to know which logins are
tradable AT ALL -- `SANCTIONED_DEMO_LOGINS` below is a hard-coded frozenset,
never read from JSON/env/CLI. Mutable config (the machine profile) may only
pick one member of this fixed set as "expected on this machine"; it can never
add a login that isn't already baked into this file.
"""
from __future__ import annotations

import sys
from typing import Any

# CUENTAS.md single source of truth (2026-07-13, extended 2026-07-15 for the
# second machine). Hard-coded on purpose: the guard must not depend on any
# mutable config to know which logins are tradable -- see module docstring.
SANCTIONED_DEMO_LOGINS = frozenset({
    2883015767,  # Machine 1 -- portable install D:\FOREX\MT5_Portable
    2883016567,  # Machine "TOMACHINE" -- standard Capitaria install, 30M CLP demo
})
REAL_LOGIN = 2883011573

# Backward-compatible alias: historically this module exposed a single
# mutable-looking DEMO_LOGIN constant that many call sites (run_live_20.py,
# supervisor_live.py, tests) reference directly. It now resolves through the
# machine profile so each machine sees ITS OWN expected login, while
# `assert_demo` below still validates against the hard-coded
# SANCTIONED_DEMO_LOGINS frozenset regardless of what this alias says.
def _resolve_demo_login() -> int:
    try:
        from sentinel_engine.live.machine_profile import load_profile
        return load_profile().demo_login
    except Exception:  # noqa: BLE001 -- never let alias resolution crash import
        # Fallback to Machine 1's value (zero-config default) if the profile
        # module/file is unavailable for any reason at import time.
        return 2883015767


DEMO_LOGIN = _resolve_demo_login()

# MetaTrader5 ACCOUNT_TRADE_MODE_* enum values (stable API constants):
#   0 = DEMO, 1 = CONTEST, 2 = REAL. We accept DEMO only.
TRADE_MODE_DEMO = 0
TRADE_MODE_CONTEST = 1
TRADE_MODE_REAL = 2


class GuardError(RuntimeError):
    """Raised when the connected account is NOT the sanctioned demo."""


def assert_demo(mt5_module: Any, *, hard_exit: bool = True,
                expected_login: int | None = None) -> int:
    """Verify the account `mt5_module` is currently attached to is a
    sanctioned DEMO, trade_mode DEMO, AND (if `expected_login` is given or
    resolvable from the machine profile) matches THIS machine's expected
    login. Returns the confirmed login on success. On ANY failure raises
    `GuardError`; if `hard_exit` is True (default) the process is terminated
    with `sys.exit(2)` after logging -- an order-capable caller must NEVER
    continue past a failed guard.

    Checks, in order:
      1. `account_info()` returns something (not None / not raising).
      2. `login` is NOT `REAL_LOGIN` (defensive, checked first).
      3. `login in SANCTIONED_DEMO_LOGINS` (the hard-coded set -- a
         machine_local.json can NEVER get a login into this check that
         isn't already baked into this file).
      4. `login == expected_login` -- the machine profile's SELECTION within
         the sanctioned set (defaults to `DEMO_LOGIN`, i.e.
         `machine_profile.load_profile().demo_login`, when not passed
         explicitly). This is the only role mutable config plays: picking
         which already-sanctioned login this machine should see.
      5. `trade_mode == TRADE_MODE_DEMO` (rejects CONTEST and REAL).
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

    if login not in SANCTIONED_DEMO_LOGINS:
        _fail(f"login {login} is not in the hard-coded sanctioned set "
              f"{sorted(SANCTIONED_DEMO_LOGINS)}")
        raise GuardError("unreachable")

    want_login = DEMO_LOGIN if expected_login is None else expected_login
    if login != want_login:
        _fail(f"login {login} is sanctioned but does not match THIS "
              f"machine's expected DEMO {want_login} (machine profile "
              "selection) -- refusing (wrong machine/account pairing)")
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
