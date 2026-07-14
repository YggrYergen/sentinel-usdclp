r"""scripts/live/run_deals_watcher.py -- standalone runner daemon for
`sentinel_engine.live.deals_watcher.DealsWatcher`.

WHY: `scripts/live/check_live_sim_parity.py` reads real deals from the
`deals_raw` table in `data/research.db`, which is populated by
`DealsWatcher.poll_once()` -- but nothing runs the watcher in production, so
`deals_raw` stays empty. This script is the daemon that runs it.

READ-ONLY toward MT5: this watcher only ever calls history-read methods
(`history_deals_get`, `account_info`, `symbol_info`) via the injected mt5
client -- it NEVER sends orders (no `order_send` anywhere in this file).

ATTACH-ONLY / NEVER LAUNCH: mirrors `scripts/live/run_live_20.py`'s
`_portable_running` pattern -- we NEVER call `mt5.initialize()` unless the
DEMO portable `terminal64.exe` process is already running.

ACCOUNT GUARD: after connecting, `account_info().login` MUST equal
`sentinel_engine.live.guard_cuenta.DEMO_LOGIN` (2883015767) -- this watcher
must only ever record deals for the sanctioned DEMO account. A mismatch
exits 2 without recording anything.

SELF-HEAL: at the top of every loop iteration we call `_connection_healthy()`
to detect a dead MT5 IPC link (e.g. `account_info()` returning None after a
silent disconnect). An unhealthy-but-attributable connection triggers
`_reconnect()`, which re-attaches via `mt5.shutdown()` + `mt5.initialize()`
-- but ONLY after re-confirming the portable terminal is still running
(ATTACH-ONLY is never violated by the self-heal path). A reconnect that
surfaces a different account login exits 2 immediately (account guard is
never bypassed); a reconnect that merely fails to attach is logged and
retried on the next poll interval -- the daemon never exits for that reason.

USAGE
    python -m scripts.live.run_deals_watcher [--db data/research.db] [--poll 5] [--once]
    python -m scripts.live.run_deals_watcher --once --since 2026-07-14T00:00:00+00:00
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.live import guard_cuenta  # noqa: E402
from sentinel_engine.live.deals_watcher import DealsWatcher  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

# Same documented meta key DealsWatcher itself persists last_sync under
# (sentinel_engine/live/deals_watcher.py: `_LAST_SYNC_META_KEY`). We only
# ever WRITE it here, and only to seed an initial watermark before the
# watcher's own constructor reads it -- never touching deals_watcher.py.
_LAST_SYNC_META_KEY = "deals_watcher.last_sync"

DEFAULT_DB = REPO_ROOT / "data" / "research.db"
PORTABLE_EXE = Path(r"D:\FOREX\MT5_Portable\terminal64.exe")
PORTABLE_MARKER = "mt5_portable"

logger = logging.getLogger("run_deals_watcher")


# --------------------------------------------------------------------------
# Attach guard (NEVER LAUNCH) -- copied pattern from run_live_20._portable_running.
# --------------------------------------------------------------------------
def _portable_running(marker: str = PORTABLE_MARKER) -> bool:
    """True iff a running process' command line references the DEMO portable
    install path. Uses WMIC (fallback: PowerShell CIM) so we don't confuse
    the REAL terminal (same image name, different path)."""
    import subprocess
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
# Thin real-MT5 client adapter satisfying the DealsWatcher.mt5_client interface
# (history_deals_get(from_ts, to_ts) -> list[dict], plus optional
# account_info()/symbol_info(sym) for B1c leverage/contract_size).
# --------------------------------------------------------------------------
_DEAL_FIELDS = (
    "ticket", "position_id", "symbol", "side", "volume",
    "price", "profit", "magic", "time", "entry_type",
)


def _deal_to_dict(mt5: Any, d: Any) -> dict[str, Any]:
    """Real MT5 `TradeDeal` namedtuple -> the dict shape DealsWatcher expects
    (mirrors `tests/live/test_deals_watcher.py`'s stub deal dicts)."""
    entry = getattr(d, "entry", None)
    entry_type = "IN" if entry == 0 else ("OUT" if entry == 1 else str(entry))
    dtype = getattr(d, "type", None)
    side = "BUY" if dtype == getattr(mt5, "DEAL_TYPE_BUY", 0) else (
        "SELL" if dtype == getattr(mt5, "DEAL_TYPE_SELL", 1) else str(dtype))
    return {
        "ticket": getattr(d, "ticket", None),
        "position_id": getattr(d, "position_id", None),
        "symbol": getattr(d, "symbol", None),
        "side": side,
        "volume": getattr(d, "volume", None),
        "price": getattr(d, "price", None),
        "profit": getattr(d, "profit", None),
        "magic": getattr(d, "magic", None),
        "time": getattr(d, "time", None),
        "entry_type": entry_type,
    }


class RealMt5DealsClient:
    """Real, read-only adapter over the `MetaTrader5` module satisfying the
    interface `DealsWatcher` expects. Never calls `order_send` or any other
    trading function -- only `history_deals_get`, `account_info`,
    `symbol_info` (all read-only queries)."""

    def __init__(self, mt5_module: Any):
        self._mt5 = mt5_module

    def history_deals_get(self, from_ts: float, to_ts: float) -> list[dict[str, Any]]:
        deals = self._mt5.history_deals_get(from_ts, to_ts)
        if deals is None:
            return []
        return [_deal_to_dict(self._mt5, d) for d in deals]

    def account_info(self) -> Any:
        return self._mt5.account_info()

    def symbol_info(self, symbol: str) -> Any:
        return self._mt5.symbol_info(symbol)


# --------------------------------------------------------------------------
# Connect (attach-only) + account guard.
# --------------------------------------------------------------------------
def _connect(mt5: Any) -> None:
    """Attach to the DEMO portable terminal ONLY. Caller has already
    confirmed the portable process is running (attach guard)."""
    if not mt5.initialize(path=str(PORTABLE_EXE), portable=True):
        raise SystemExit(f"[FATAL] initialize(path={PORTABLE_EXE}) failed: "
                         f"{mt5.last_error()}")


def _connection_healthy(mt5: Any) -> tuple[bool, str]:
    """Cheap health probe for the live MT5 IPC connection. Never raises --
    any exception from `account_info()` is treated as "no_info" (unhealthy).
    Returns `(True, "ok")` only when we get an `account_info()` result AND
    its `login` matches the sanctioned DEMO account; `(False, "wrong_login")`
    signals the account-guard case specifically (caller must exit, never
    just retry) and `(False, "no_info")` signals a plain dead/absent
    connection (caller should attempt `_reconnect()`)."""
    try:
        info = mt5.account_info()
    except Exception:  # noqa: BLE001
        return False, "no_info"
    if info is None:
        return False, "no_info"
    if getattr(info, "login", None) != guard_cuenta.DEMO_LOGIN:
        return False, "wrong_login"
    return True, "ok"


def _reconnect(mt5: Any, attach_checker: Callable[[], bool], *,
               max_attempts: int = 3,
               sleep_fn: Callable[[float], None] = time.sleep) -> bool:
    """Attempt to re-attach to the DEMO portable MT5 terminal, self-healing a
    silently-dead IPC connection. ATTACH-ONLY is preserved: `mt5.initialize()`
    is NEVER called unless `attach_checker()` confirms the portable terminal
    process is still running -- if it isn't, we log and give up immediately
    rather than launching anything. The account guard is also preserved: a
    reconnect that resolves to a different login aborts immediately (returns
    False) instead of continuing to retry on the wrong account."""
    for attempt in range(1, max_attempts + 1):
        try:
            mt5.shutdown()
        except Exception:  # noqa: BLE001
            pass

        if not attach_checker():
            logger.error(
                "portable terminal not running -- cannot re-attach "
                "(ATTACH-ONLY: we never launch)")
            return False

        try:
            ok = mt5.initialize(path=str(PORTABLE_EXE), portable=True)
        except Exception:  # noqa: BLE001
            ok = False

        if ok:
            healthy, why = _connection_healthy(mt5)
            if healthy:
                logger.info("reconnected to MT5 (attempt %d)", attempt)
                return True
            if why == "wrong_login":
                logger.error(
                    "reconnect attempt %d succeeded but account login does "
                    "not match the sanctioned DEMO account -- aborting "
                    "reconnect (account guard).", attempt)
                return False

        logger.warning("reconnect attempt %d/%d failed", attempt, max_attempts)
        sleep_fn(5.0 * attempt)

    return False


def _check_login(mt5: Any) -> int:
    """Verify `account_info().login == guard_cuenta.DEMO_LOGIN`. Returns the
    login on success; caller exits 2 on mismatch/missing info."""
    info = mt5.account_info()
    login = getattr(info, "login", None) if info is not None else None
    if login != guard_cuenta.DEMO_LOGIN:
        print(f"[FATAL] connected account login={login!r} does not match the "
              f"sanctioned DEMO account {guard_cuenta.DEMO_LOGIN} -- refusing to "
              "record deals for any other account.", file=sys.stderr)
        raise SystemExit(2)
    return login


# --------------------------------------------------------------------------
# Optional --since seeding: only when no watermark exists yet.
# --------------------------------------------------------------------------
def _seed_since_watermark(registry: ResearchRegistry, since_iso: str) -> None:
    """If `--since` was given AND the registry has no persisted last_sync
    yet, seed it so DealsWatcher's constructor (which reads
    `registry.get_meta(_LAST_SYNC_META_KEY)`) resumes from that timestamp
    instead of 0.0 (which would pull ALL history). No-op if a watermark
    already exists (never rewinds an established watermark) or if
    `since_iso` is None. Achieved purely via `registry.set_meta` BEFORE
    constructing DealsWatcher -- no changes to deals_watcher.py needed,
    since its constructor already reads this exact meta key on init."""
    if since_iso is None:
        return
    if registry.get_meta(_LAST_SYNC_META_KEY) is not None:
        logger.info("--since %s ignored: a watermark already exists.", since_iso)
        return
    dt = datetime.fromisoformat(since_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = dt.timestamp()
    registry.set_meta(_LAST_SYNC_META_KEY, str(ts))
    logger.info("seeded initial watermark from --since %s (epoch=%.3f)", since_iso, ts)


# --------------------------------------------------------------------------
# Main.
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None, *, mt5_module: Any = None,
         attach_checker: Callable[[], bool] = _portable_running,
         registry_factory: Callable[[Path], ResearchRegistry] = ResearchRegistry,
         client_factory: Callable[[Any], Any] = RealMt5DealsClient,
         watcher_factory: Callable[..., DealsWatcher] = DealsWatcher) -> int:
    ap = argparse.ArgumentParser(description="Standalone DealsWatcher runner (read-only).")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="path to research.db")
    ap.add_argument("--poll", type=float, default=5.0, help="poll interval seconds")
    ap.add_argument("--once", action="store_true", help="single poll then exit")
    ap.add_argument("--since", default=None,
                     help="ISO-8601 UTC timestamp: seed the initial watermark "
                          "from this time IF no watermark exists yet (ignored "
                          "otherwise)")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)])

    # ATTACH-ONLY / NEVER LAUNCH: confirm the portable terminal is running
    # BEFORE importing/initializing MetaTrader5.
    if not attach_checker():
        print("[STOP] The DEMO portable MT5 terminal is NOT running.\n"
              "       Open it first via  D:\\FOREX\\MT5_DEMO_TOMAS.bat  (login "
              f"{guard_cuenta.DEMO_LOGIN}), then re-run this watcher.\n"
              "       (initialize() was NOT called -- we never launch a terminal.)",
              file=sys.stderr)
        return 3

    mt5 = mt5_module
    if mt5 is None:
        import MetaTrader5 as mt5  # noqa: N813 -- only imported once attach-confirmed
    _connect(mt5)
    try:
        login = _check_login(mt5)
    except SystemExit as exc:
        try:
            mt5.shutdown()
        except Exception:  # noqa: BLE001
            pass
        return exc.code if isinstance(exc.code, int) else 2
    logger.info("connected + account guard OK: DEMO login %s", login)

    registry = registry_factory(Path(args.db))
    _seed_since_watermark(registry, args.since)

    client = client_factory(mt5)
    watcher = watcher_factory(registry, client, poll_s=int(args.poll),
                              attach_checker=attach_checker)

    stop = {"flag": False}

    def _sigint(_sig, _frm):
        logger.info("Ctrl-C received -- clean shutdown after current poll.")
        stop["flag"] = True

    import signal
    signal.signal(signal.SIGINT, _sigint)

    consecutive_errors = 0
    try:
        while True:
            healthy, why = _connection_healthy(mt5)
            if why == "wrong_login":
                logger.error(
                    "MT5 connection now reports a different account login -- "
                    "refusing to continue polling (account guard).")
                return 2

            skip_poll = False
            if not healthy:
                logger.warning(
                    "MT5 connection unhealthy -- attempting self-heal reconnect")
                if not _reconnect(mt5, attach_checker):
                    logger.error(
                        "reconnect failed -- will retry next poll interval")
                    skip_poll = True

            if not skip_poll:
                try:
                    report = watcher.poll_once()
                    consecutive_errors = 0
                    logger.info(
                        "poll: attached=%s deals_seen=%d upserted=%d skipped=%s",
                        report.attached, report.deals_seen, report.upserted, report.skipped)
                except Exception:  # noqa: BLE001 -- never crash-loop silently
                    consecutive_errors += 1
                    logger.exception("poll_once() failed (consecutive=%d)", consecutive_errors)
                    if consecutive_errors >= 5:
                        logger.error(
                            "5 consecutive poll failures -- continuing to retry, "
                            "but this needs investigation.")
                        reconnected = _reconnect(mt5, attach_checker)
                        logger.error("self-heal reconnect after 5 failures: %s",
                                     "succeeded" if reconnected else "failed")
                        if reconnected:
                            consecutive_errors = 0

            if args.once or stop["flag"]:
                break
            time.sleep(args.poll)
    finally:
        try:
            mt5.shutdown()
        except Exception:  # noqa: BLE001
            pass
    logger.info("watcher stopped cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
