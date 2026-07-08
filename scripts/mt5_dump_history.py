"""
scripts/mt5_dump_history.py — pull real OHLC history from a running MT5 terminal
into the data lake (SENTINEL revamp, Step A).

READ-ONLY: only reads price history from the terminal; never selects an order,
never trades. Safe against the read-only real account.

Flow:
  1. Connect to the portable terminal (read-only).
  2. For every (lake_key, broker_symbol) x timeframe, page BACKWARD in chunked
     `copy_rates_from` calls (the terminal caps a single call ~20k-50k bars and
     rejects huge counts with "Invalid params"), until the start bound is reached
     or history runs out.
  3. Write each series to data/raw/<lake_key>/<tf_minutes>.csv in the exact MT5
     export shape the tested ingester expects (time,open,high,low,close,volume;
     ISO-8601 tz-aware UTC).
  4. Ingest every CSV into the Parquet lake via the repo's ingest_mt5_csv, then
     build the coverage manifest and print a summary.

The 3 config futures symbols rolled contracts; we source the current continuous
contract but STORE it under the config's original key so config_hash / parity is
untouched (USDX_Sep26 bars -> lake key 'USDX_Jun26', etc.).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import MetaTrader5 as mt5

REPO = Path(r"D:\FOREX")
sys.path.insert(0, str(REPO))
from sentinel_engine.lake.ingest_mt5 import ingest_mt5_csv  # noqa: E402
from sentinel_engine.lake.manifest import build_manifest, write_manifest  # noqa: E402

PORTABLE = REPO / "MT5_Portable" / "terminal64.exe"
RAW_ROOT = REPO / "data" / "raw"
LAKE_ROOT = REPO / "data" / "lake"

START_BOUND = datetime(2022, 1, 1, tzinfo=timezone.utc)
CHUNK = 20000  # bars per copy_rates_from call (100k errors; 20k-50k safe)

TIMEFRAMES = {
    1: mt5.TIMEFRAME_M1,
    2: mt5.TIMEFRAME_M2,
    5: mt5.TIMEFRAME_M5,
    15: mt5.TIMEFRAME_M15,
    60: mt5.TIMEFRAME_H1,
    1440: mt5.TIMEFRAME_D1,
}

# lake_key -> broker source symbol. Only the 3 rolled futures differ from identity.
SYMBOL_MAP = {
    # targets
    "XAUUSD": "XAUUSD",
    "NQ100": "NQ100",
    "USDCLP": "USDCLP",
    # macro (rolled contracts -> current continuous contract)
    "USDX_Jun26": "USDX_Sep26",
    "Cobre_Jul26": "Cobre_Sep26",
    "VIX_Jun26": "VIX_Jul26",
    # macro (identity)
    "XAGUSD": "XAGUSD",
    "EURUSD": "EURUSD",
    "SP": "SP",
    "USDJPY": "USDJPY",
    "WTI": "WTI",
    "USDMXN": "USDMXN",
    "USDBRL": "USDBRL",
    "AUDUSD": "AUDUSD",
    "USDCNH": "USDCNH",
    "BTCUSD": "BTCUSD",
}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_series(broker_sym: str, mt5_tf: int) -> pd.DataFrame:
    """Page backward until START_BOUND or history exhausted. Returns a
    tz-aware UTC DatetimeIndex frame with open/high/low/close/volume."""
    anchor = datetime.now(timezone.utc)
    prev_earliest: pd.Timestamp | None = None
    frames: list[pd.DataFrame] = []
    for _ in range(400):  # hard safety cap on iterations
        rates = mt5.copy_rates_from(broker_sym, mt5_tf, anchor, CHUNK)
        if rates is None or len(rates) == 0:
            break
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").sort_index()
        frames.append(df)
        earliest = df.index[0]
        if earliest <= START_BOUND:
            break
        if prev_earliest is not None and earliest >= prev_earliest:
            break  # no backward progress; history floor reached
        prev_earliest = earliest
        anchor = earliest.to_pydatetime() - timedelta(seconds=1)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out[out.index >= START_BOUND]
    res = pd.DataFrame({
        "open": out["open"],
        "high": out["high"],
        "low": out["low"],
        "close": out["close"],
        "volume": out["tick_volume"].astype("int64"),
    })
    return res


def write_csv(lake_key: str, tf_min: int, df: pd.DataFrame) -> Path:
    out_dir = RAW_ROOT / lake_key
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{tf_min}.csv"
    frame = df.copy()
    frame.index.name = "time"
    frame.reset_index().to_csv(path, index=False, encoding="utf-8")
    return path


def main() -> int:
    if not mt5.initialize(path=str(PORTABLE)):
        log(f"initialize FAILED: {mt5.last_error()}")
        return 1
    ai = mt5.account_info()
    log(f"connected: login={ai.login} server={ai.server} currency={ai.currency}")

    csv_paths: list[tuple[str, int, Path]] = []
    for lake_key, broker_sym in SYMBOL_MAP.items():
        if mt5.symbol_info(broker_sym) is None:
            log(f"!! {broker_sym} (for {lake_key}) MISSING on broker — skipped")
            continue
        mt5.symbol_select(broker_sym, True)
        for tf_min, mt5_tf in TIMEFRAMES.items():
            df = fetch_series(broker_sym, mt5_tf)
            if df.empty:
                log(f"   {lake_key:14s} tf={tf_min:>4d}  EMPTY")
                continue
            path = write_csv(lake_key, tf_min, df)
            log(f"   {lake_key:14s} tf={tf_min:>4d}  {len(df):>7d} bars  "
                f"{df.index[0].date()} .. {df.index[-1].date()}  <- {broker_sym}")
            csv_paths.append((lake_key, tf_min, path))

    mt5.shutdown()

    log(f"ingesting {len(csv_paths)} CSVs into lake {LAKE_ROOT} ...")
    for lake_key, tf_min, path in csv_paths:
        ingest_mt5_csv(path, lake_key, tf_min, LAKE_ROOT, update_manifest=False)
    write_manifest(LAKE_ROOT, gap_tolerance_factor=3.0)

    manifest = build_manifest(LAKE_ROOT, gap_tolerance_factor=3.0)
    log("=== COVERAGE MANIFEST ===")
    for sym in sorted(manifest):
        for tf in sorted(manifest[sym], key=int):
            e = manifest[sym][tf]
            ngaps = len(e["gaps"])
            log(f"   {sym:14s} tf={tf:>4s}  {e['bar_count']:>7d} bars  "
                f"{str(e['start'])[:10]} .. {str(e['end'])[:10]}  gaps={ngaps}")
    log("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
