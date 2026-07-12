"""
scripts/mt5_dump_xauusd_early2026.py — backfill XAUUSD Jan→late-Mar 2026 bars.

Why: the winner run `mt5import-abc1043ef513` has trades from 2026-01-11 onward, but
the lake's XAUUSD history only starts 2026-03-25 (the live broker feed doesn't serve
older M1). The Strategy Tester DID have Jan–May bars (they're cached in
MT5_Tester/Bases/Capitaria-All/history/XAUUSD). This script pulls the missing window
via copy_rates_range and ingests it into the Parquet lake so every trade gets candles.

READ-ONLY: only reads price history; never selects/places an order.

FEASIBILITY (spec docs/superpowers/specs/2026-07-10-xauusd-history-feasibility.md):
the Jan–Mar 2026 XAUUSD bars ALREADY exist on disk in the TESTER terminal's history
base — `MT5_Tester/Bases/Capitaria-All/history/XAUUSD/2026.hcc` (+ `ticks/202601..03.tkc`).
The live `MT5_Portable`/Capitaria feed does NOT serve them (its backward paging floored at
2026-03-25). So this script attaches to `MT5_Tester/terminal64.exe` (default TERMINAL below)
and reads its local cache via copy_rates_range.

PREREQUISITE / SAFETY:
  1. CLOSE any running MT5 terminal first (an already-open terminal blocks mt5.initialize
     on another install — user-known issue).
  2. BACK UP the cache before first run (read-only in theory, but a terminal may re-sync):
       Copy-Item MT5_Tester\Bases\Capitaria-All\history\XAUUSD  ..._backup -Recurse
     (You also already have a full duplicate at MT5_Tester_2, which is a natural backup.)
  3. Run the script. If M1 comes back EMPTY, retry once with --terminal pointing at
     MT5_Tester_2 (the duplicate), or fall back to the Dukascopy path in the spec.

Usage (PowerShell):
    python scripts/mt5_dump_xauusd_early2026.py
    python scripts/mt5_dump_xauusd_early2026.py --terminal "D:\FOREX\MT5_Tester_2\terminal64.exe"
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import MetaTrader5 as mt5

REPO = Path(r"D:\FOREX")
sys.path.insert(0, str(REPO))
from sentinel_engine.lake.ingest_mt5 import ingest_mt5_csv  # noqa: E402
from sentinel_engine.lake.manifest import build_manifest, write_manifest  # noqa: E402
from sentinel_engine.service.bars import load_tf_frame  # noqa: E402

# The TESTER terminal's history base holds the Jan–Mar 2026 XAUUSD cache (see docstring).
# Override with --terminal (e.g. the MT5_Tester_2 duplicate) if this one comes back empty.
TERMINAL = REPO / "MT5_Tester" / "terminal64.exe"
RAW_ROOT = REPO / "data" / "raw"
LAKE_ROOT = REPO / "data" / "lake"

SYMBOL = "XAUUSD"
# Backfill window: from before the earliest trade (2026-01-11) to just past the
# current lake start (2026-03-25); overlap is fine — ingest dedupes on time.
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 3, 26, tzinfo=timezone.utc)

TIMEFRAMES = {
    1: mt5.TIMEFRAME_M1,
    2: mt5.TIMEFRAME_M2,
    5: mt5.TIMEFRAME_M5,
    15: mt5.TIMEFRAME_M15,
    60: mt5.TIMEFRAME_H1,
}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Backfill XAUUSD Jan–Mar 2026 from the MT5 tester cache.")
    parser.add_argument("--terminal", default=str(TERMINAL),
                        help="Path to terminal64.exe whose history base holds the range "
                             "(default: MT5_Tester; try MT5_Tester_2 if empty).")
    args = parser.parse_args()

    log(f"attaching to terminal: {args.terminal}")
    if not mt5.initialize(path=args.terminal):
        log(f"initialize FAILED: {mt5.last_error()} — is another MT5 terminal already open? Close it and retry.")
        return 1
    ai = mt5.account_info()
    if ai is not None:
        log(f"connected: login={ai.login} server={ai.server}")
    mt5.symbol_select(SYMBOL, True)

    csv_paths: list[tuple[int, Path]] = []
    for tf_min, mt5_tf in TIMEFRAMES.items():
        rates = mt5.copy_rates_range(SYMBOL, mt5_tf, START, END)
        if rates is None or len(rates) == 0:
            log(f"   {SYMBOL} tf={tf_min:>4d}  EMPTY  (retry with --terminal MT5_Tester_2, else use the Dukascopy fallback)")
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").sort_index()
        res = pd.DataFrame({
            "open": df["open"], "high": df["high"], "low": df["low"],
            "close": df["close"], "volume": df["tick_volume"].astype("int64"),
        })
        out_dir = RAW_ROOT / SYMBOL
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{tf_min}_early2026.csv"
        res.index.name = "time"
        res.reset_index().to_csv(path, index=False, encoding="utf-8")
        log(f"   {SYMBOL} tf={tf_min:>4d}  {len(res):>7d} bars  "
            f"{res.index[0].date()} .. {res.index[-1].date()}")
        csv_paths.append((tf_min, path))

    mt5.shutdown()

    if not csv_paths:
        log("nothing fetched — terminal has no early-2026 XAUUSD history loaded. See PREREQUISITE.")
        return 2

    log(f"ingesting {len(csv_paths)} CSVs into lake {LAKE_ROOT} (idempotent, dedupes on time) ...")
    for tf_min, path in csv_paths:
        ingest_mt5_csv(path, SYMBOL, tf_min, LAKE_ROOT, update_manifest=False)
    write_manifest(LAKE_ROOT, gap_tolerance_factor=3.0)

    m1 = load_tf_frame(LAKE_ROOT, SYMBOL, "M1")
    log(f"lake XAUUSD M1 now covers {m1.index.min()} .. {m1.index.max()} ({len(m1)} bars)")
    if m1.index.min() <= pd.Timestamp("2026-01-11", tz="UTC"):
        log("OK — Jan-2026 trades are now inside the lake window.")
    else:
        log("still short of 2026-01-11 — the terminal history didn't reach that far back.")
    log("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
