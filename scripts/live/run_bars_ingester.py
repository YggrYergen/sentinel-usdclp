r"""scripts/live/run_bars_ingester.py -- durable, supervised, INCREMENTAL
OHLC bars ingester daemon (SENTINEL, 2026-07-21).

WHY THIS EXISTS: the lake's OHLC ingestion was a manual one-shot
(`scripts/mt5_dump_history.py`, run once on 2026-07-15 and never again),
so `/api/bars` tiers went stale for ~6 days and live-position charts showed
"Sin barras". The deals-watcher is kept alive by `supervisor_live.py`; bars
ingestion had no equivalent. This daemon mirrors that survivability with a
LIGHT INCREMENTAL approach: it fetches only the recent tail per cycle (never
re-pages full history to 2022), merges idempotently into the lake monolith
(`store.write_bars` dedupes on timestamp), and rebuilds TF tiers ONLY for
symbols that actually gained bars this cycle.

READ-ONLY toward MT5: only `copy_rates_from_pos` / `symbol_info` /
`symbol_select` (all read-only). NEVER sends an order -- there is no
order-sending call anywhere in this file.

ATTACH-ONLY / NEVER LAUNCH: mirrors `scripts/live/run_deals_watcher.py`'s
`_portable_running` pattern -- this daemon NEVER calls `mt5.initialize()`
unless the portable/standard terminal process is already confirmed running
via the injected `attach_checker`. Every loop iteration re-checks the
attach guard BEFORE touching MT5; if the terminal is not running we log and
skip the cycle (no connect, no crash, no exit) -- unlike the one-shot
deals-watcher runner, this is a durable daemon and must survive the
terminal being closed and self-attach again once the user reopens it. On a
transient MT5 hiccup (attach guard True but `initialize()` fails) it logs
and re-attempts on the next cycle rather than crashing.

MT5 is INJECTABLE: `run_cycle(mt5, lake_root, ...)` takes the client so tests
wire a fake and the CLI wires the real `MetaTrader5` module. This module
NEVER imports MetaTrader5 at top level -- it stays importable offline.

USAGE
    python -m scripts.live.run_bars_ingester [--interval 300] [--tail-bars 1500]
        [--lake-root data/lake] [--once] [--symbols XAUUSD --symbols NQ100]
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.lake.mt5_fetch import drop_forming_bar, rates_to_frame  # noqa: E402
from sentinel_engine.lake.store import read_bars, write_bars  # noqa: E402
from sentinel_engine.lake.tiers import build_tiers  # noqa: E402
from sentinel_engine.live.machine_profile import load_profile  # noqa: E402

# Reuse the one-shot dumper's authoritative lake_key -> broker-symbol map, so
# the daemon stays current on EXACTLY the same symbol set (the 3 rolled
# futures included) without a second, drift-prone copy.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from mt5_dump_history import SYMBOL_MAP  # noqa: E402

DEFAULT_LAKE_ROOT = REPO_ROOT / "data" / "lake"
DEFAULT_INTERVAL_S = 300
DEFAULT_TAIL_BARS = 1500
# MULTI-MACHINE (2026-07-15 pattern, applied here 2026-07-21): terminal
# path/marker/portable-flag come from the machine profile
# (sentinel_engine.live.machine_profile), same as run_deals_watcher.py and
# run_live_20.py, so this file serves both Machine 1 (portable
# D:\FOREX\MT5_Portable) and Machine "TOMACHINE" (standard Capitaria
# install) without either machine's hardcode clobbering the other's.
_PROFILE = load_profile()
PORTABLE_EXE = _PROFILE.terminal_path
PORTABLE_MARKER = _PROFILE.terminal_marker
PORTABLE_FLAG = _PROFILE.portable


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _build_timeframes(mt5: Any) -> dict[int, int]:
    """tf_minutes -> MT5 TIMEFRAME_* constant (built lazily, once mt5 exists)."""
    return {
        1: mt5.TIMEFRAME_M1,
        2: mt5.TIMEFRAME_M2,
        5: mt5.TIMEFRAME_M5,
        15: mt5.TIMEFRAME_M15,
        60: mt5.TIMEFRAME_H1,
        1440: mt5.TIMEFRAME_D1,
    }


def _max_epoch(df: pd.DataFrame) -> int | None:
    if df.empty:
        return None
    return int(df.index[-1].timestamp())


def run_cycle(mt5: Any, lake_root: Path, *, symbol_map: dict[str, str],
              timeframes: dict[int, int], tail_bars: int = DEFAULT_TAIL_BARS,
              now_epoch: int | None = None) -> list[str]:
    """Run ONE incremental ingestion cycle.

    For each (lake_key, broker_sym) x (tf_min, mt5_tf): fetch only the recent
    tail via `copy_rates_from_pos(broker_sym, mt5_tf, 0, tail_bars)`, shape it,
    drop the forming bar, and merge into the lake monolith (idempotent dedupe
    on timestamp). Track whether the symbol gained bars this cycle (max
    timestamp advanced or row count grew). Then rebuild TF tiers ONLY for
    symbols that gained bars.

    Returns the list of lake_keys whose tiers were rebuilt this cycle.
    """
    lake_root = Path(lake_root)
    if now_epoch is None:
        now_epoch = int(datetime.now(timezone.utc).timestamp())

    changed: list[str] = []
    for lake_key, broker_sym in symbol_map.items():
        if mt5.symbol_info(broker_sym) is None:
            log(f"!! {broker_sym} (for {lake_key}) MISSING on broker -- skipped")
            continue
        mt5.symbol_select(broker_sym, True)
        gained = False
        for tf_min, mt5_tf in timeframes.items():
            try:
                rates = mt5.copy_rates_from_pos(broker_sym, mt5_tf, 0, tail_bars)
            except Exception as exc:  # noqa: BLE001 -- transient hiccup, next cycle retries
                log(f"   {lake_key:14s} tf={tf_min:>4d}  copy_rates_from_pos FAILED: {exc}")
                continue
            df = rates_to_frame(rates)
            if df.empty:
                continue
            df = drop_forming_bar(df, tf_min, now_epoch)
            if df.empty:
                continue

            before = read_bars(lake_root, lake_key, tf_min)
            before_max = _max_epoch(before)
            before_n = len(before)

            write_bars(lake_root, lake_key, tf_min, df)

            after = read_bars(lake_root, lake_key, tf_min)
            after_max = _max_epoch(after)
            if (before_max is None
                    or (after_max is not None and after_max > before_max)
                    or len(after) > before_n):
                gained = True

        if gained:
            try:
                build_tiers(lake_key, lake_root)
                changed.append(lake_key)
                log(f"tiers rebuilt for {lake_key}")
            except Exception as exc:  # noqa: BLE001 -- monolith intact; skip this symbol
                log(f"!! build_tiers({lake_key}) FAILED: {exc} -- tiers stale, monolith intact")
    return changed


# --------------------------------------------------------------------------
# Attach guard (NEVER LAUNCH) -- copied verbatim from
# run_deals_watcher._portable_running.
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


def _connect(mt5: Any) -> bool:
    """Attach to the terminal ONLY (read-only). Caller has already confirmed
    the process is running (attach guard). Returns True on success."""
    # MULTI-MACHINE (2026-07-15 pattern): pass portable=True only when this
    # machine's profile says so (Machine 1's portable install needs it;
    # Machine "TOMACHINE"'s standard install must not get it, else MT5
    # would look for a nonexistent portable data dir and detach from the
    # logged-in session).
    ok = (mt5.initialize(path=str(PORTABLE_EXE), portable=True) if PORTABLE_FLAG
          else mt5.initialize(path=str(PORTABLE_EXE)))
    if not ok:
        log(f"initialize FAILED: {mt5.last_error()}")
        return False
    return True


def main(argv: list[str] | None = None, *, mt5_module: Any = None,
         attach_checker: Callable[[], bool] = _portable_running) -> int:
    ap = argparse.ArgumentParser(
        description="Durable incremental OHLC bars ingester (read-only).")
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_S,
                    help="seconds between cycles (default 300)")
    ap.add_argument("--tail-bars", type=int, default=DEFAULT_TAIL_BARS,
                    help="how many recent bars to fetch per (symbol, tf) (default 1500)")
    ap.add_argument("--lake-root", default=str(DEFAULT_LAKE_ROOT),
                    help="lake root directory (default data/lake)")
    ap.add_argument("--once", action="store_true",
                    help="run a single cycle then exit")
    ap.add_argument("--symbols", action="append", default=None,
                    help="repeatable filter; default = all of SYMBOL_MAP")
    args = ap.parse_args(argv)

    lake_root = Path(args.lake_root)
    if args.symbols:
        symbol_map = {k: v for k, v in SYMBOL_MAP.items() if k in set(args.symbols)}
        if not symbol_map:
            log(f"!! no known symbols in {args.symbols} -- nothing to do")
            return 2
    else:
        symbol_map = dict(SYMBOL_MAP)

    mt5 = mt5_module
    if mt5 is None:
        import MetaTrader5 as mt5  # noqa: N813 -- only imported when actually running

    connected = False
    timeframes: dict[int, int] = {}
    log(f"bars ingester up: interval={args.interval}s tail_bars={args.tail_bars} "
        f"symbols={len(symbol_map)} lake_root={lake_root}")

    try:
        while True:
            # ATTACH-ONLY / NEVER LAUNCH: re-check at the TOP of every loop
            # iteration, even on the very first one -- unlike the one-shot
            # deals-watcher runner, this daemon must SURVIVE the terminal
            # being closed (at startup or mid-run) and simply keep skipping
            # cycles until attach_checker() confirms it is running again.
            if not attach_checker():
                log("portable terminal not running -- skipping cycle "
                    "(ATTACH-ONLY: we never launch)")
                connected = False
            else:
                if not connected:
                    connected = _connect(mt5)
                    if connected:
                        timeframes = _build_timeframes(mt5)
                if connected:
                    try:
                        changed = run_cycle(mt5, lake_root, symbol_map=symbol_map,
                                            timeframes=timeframes, tail_bars=args.tail_bars)
                        log(f"cycle done: {len(changed)} symbol(s) re-tiered")
                    except Exception as exc:  # noqa: BLE001 -- never crash the daemon
                        log(f"!! cycle FAILED: {exc} -- will re-init and retry next cycle")
                        connected = False
                else:
                    log("MT5 not connected -- will retry next cycle")

            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log("Ctrl-C received -- bars ingester stopping.")
    finally:
        try:
            mt5.shutdown()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
