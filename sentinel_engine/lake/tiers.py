"""
sentinel_engine.lake.tiers — Lake timeframe ("tier") builder for LOD bar serving.

Produces, per symbol, one Parquet file per (timeframe, calendar month) under:
    <lake_root>/<SYMBOL>/<TF>/<YYYY-MM>.parquet

with stable columns `t, o, h, l, c, v` (t: int64 epoch-seconds, o/h/l/c:
float64, v: int64), and updates `<lake_root>/manifest.json` with one entry
per (symbol, tf):
    {"symbol": ..., "tf": ..., "first": ..., "last": ..., "rows": ...,
     "content_sha": ...}

Design notes / reuse:
    - Source-of-truth bars are read via `sentinel_engine.lake.store.read_bars`,
      which already knows the existing on-disk native format
      (`<lake_root>/<symbol>/<timeframe_minutes>.parquet`, DatetimeIndex
      "time", columns open/high/low/close/volume). This module does NOT
      duplicate that read/write path for native minute-indexed files — it
      only *reads* through it to source raw bars, then resamples into the
      new epoch-second tier format described above.
    - Resample math (bucketing, OHLCV aggregation, empty-bucket skipping,
      forming-bar guard) is new: the existing `store.py`/`manifest.py` only
      do 1:1 read/write + gap detection, no resampling exists elsewhere in
      the lake package.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from sentinel_engine.lake.store import read_bars

# Timeframe name -> seconds. Spec: at least M1, M2, M5, M15, H1, D.
TF_SECONDS: dict[str, int] = {
    "M1": 60,
    "M2": 120,
    "M5": 300,
    "M15": 900,
    "H1": 3600,
    "D": 86400,
}

# Timeframe name -> native minute-file key understood by store.read_bars,
# used when a tier's own native file exists in the legacy per-minute layout.
_TF_NATIVE_MINUTES: dict[str, int] = {
    "M1": 1,
    "M2": 2,
    "M5": 5,
    "M15": 15,
    "H1": 60,
    "D": 1440,
}

OUT_COLUMNS = ["t", "o", "h", "l", "c", "v"]

ROW_GROUP_SIZE = 8192


@dataclass
class TierReport:
    symbol: str
    tiers: dict[str, dict] = field(default_factory=dict)


def _resample(df: pd.DataFrame, tf_seconds: int, now_epoch: int) -> pd.DataFrame:
    """Resample a native OHLCV frame (DatetimeIndex "time", UTC, columns
    open/high/low/close/volume) into `tf_seconds`-wide buckets.

    Rules (deterministic):
      - bucket = t - (t % tf_seconds)
      - o=first, h=max, l=min, c=last, v=sum
      - empty buckets are omitted (no emitted row)
      - input is sorted + de-duplicated by t before bucketing
      - any bar whose bucket start t > now_epoch - tf_seconds is dropped
        (forming-bar guard: the bucket may still be accumulating data)
    """
    if df.empty:
        return pd.DataFrame(columns=OUT_COLUMNS)

    t = (df.index.view("int64") // 1_000_000_000).astype("int64")
    work = pd.DataFrame({
        "t": t,
        "o": df["open"].to_numpy(dtype="float64"),
        "h": df["high"].to_numpy(dtype="float64"),
        "l": df["low"].to_numpy(dtype="float64"),
        "c": df["close"].to_numpy(dtype="float64"),
        "v": df["volume"].to_numpy(dtype="int64"),
    })
    work = work.sort_values("t").drop_duplicates(subset="t", keep="last")

    bucket = work["t"] - (work["t"] % tf_seconds)
    work = work.assign(bucket=bucket)

    grouped = work.groupby("bucket", sort=True)
    out = grouped.agg(o=("o", "first"), h=("h", "max"), l=("l", "min"),
                      c=("c", "last"), v=("v", "sum"))
    out.index.name = "t"
    out = out.reset_index()

    forming_cutoff = now_epoch - tf_seconds
    out = out[out["t"] <= forming_cutoff]

    out["t"] = out["t"].astype("int64")
    out["v"] = out["v"].astype("int64")
    out["o"] = out["o"].astype("float64")
    out["h"] = out["h"].astype("float64")
    out["l"] = out["l"].astype("float64")
    out["c"] = out["c"].astype("float64")

    return out[OUT_COLUMNS].reset_index(drop=True)


def _month_key(epoch_seconds: int) -> str:
    ts = pd.Timestamp(epoch_seconds, unit="s", tz="UTC")
    return f"{ts.year:04d}-{ts.month:02d}"


def _sha1_of_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_monthly_parquet(tier_dir: Path, month_df: pd.DataFrame) -> Path:
    """Write one month's worth of bars to `<tier_dir>/<YYYY-MM>.parquet`."""
    month_key = _month_key(int(month_df["t"].iloc[0]))
    path = tier_dir / f"{month_key}.parquet"
    table = pa.table({
        "t": pa.array(month_df["t"].to_numpy(), type=pa.int64()),
        "o": pa.array(month_df["o"].to_numpy(), type=pa.float64()),
        "h": pa.array(month_df["h"].to_numpy(), type=pa.float64()),
        "l": pa.array(month_df["l"].to_numpy(), type=pa.float64()),
        "c": pa.array(month_df["c"].to_numpy(), type=pa.float64()),
        "v": pa.array(month_df["v"].to_numpy(), type=pa.int64()),
    })
    pq.write_table(table, path, row_group_size=ROW_GROUP_SIZE)
    return path


def _source_frame_for_tf(symbol: str, lake_root: Path, tf_name: str) -> pd.DataFrame:
    """Locate the source-of-truth native frame for `tf_name`, falling back to
    the finest available native timeframe when no native file exists for it."""
    native_minutes = sorted(_TF_NATIVE_MINUTES.values())
    tf_minutes = _TF_NATIVE_MINUTES[tf_name]

    df = read_bars(lake_root, symbol, tf_minutes)
    if not df.empty:
        return df, tf_minutes

    # Fall back to the finest native timeframe available that is <= tf_minutes,
    # else the finest available at all (still coarser data cannot produce a
    # finer tier correctly, but there is nothing better to derive from).
    candidates = [m for m in native_minutes if m <= tf_minutes]
    candidates = sorted(candidates, reverse=True) + sorted(
        [m for m in native_minutes if m > tf_minutes])
    for m in candidates:
        if m == tf_minutes:
            continue
        cand = read_bars(lake_root, symbol, m)
        if not cand.empty:
            return cand, m
    return df, tf_minutes


def build_tiers(symbol: str, lake_root: Path,
                 now_epoch: int | None = None) -> TierReport:
    """Build all lake TF tiers for `symbol` under `lake_root`.

    Writes monthly Parquet files to `<lake_root>/<symbol>/<TF>/<YYYY-MM>.parquet`
    and updates `<lake_root>/manifest.json` with one entry per (symbol, tf).
    """
    lake_root = Path(lake_root)
    if now_epoch is None:
        now_epoch = int(pd.Timestamp.utcnow().timestamp())

    report = TierReport(symbol=symbol)

    manifest_path = lake_root / "manifest.json"
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {}

    for tf_name, tf_seconds in TF_SECONDS.items():
        source_df, _source_minutes = _source_frame_for_tf(symbol, lake_root, tf_name)
        resampled = _resample(source_df, tf_seconds, now_epoch)

        tier_dir = lake_root / symbol / tf_name
        tier_dir.mkdir(parents=True, exist_ok=True)
        # Clear any pre-existing monthly files for a clean, deterministic rebuild.
        for existing in tier_dir.glob("*.parquet"):
            existing.unlink()

        file_shas: list[str] = []
        if not resampled.empty:
            month_of = resampled["t"].apply(_month_key)
            for month_key in sorted(month_of.unique()):
                month_df = resampled[month_of == month_key]
                path = _write_monthly_parquet(tier_dir, month_df)
                file_shas.append(_sha1_of_file(path))

        content_sha = hashlib.sha1("".join(file_shas).encode("utf-8")).hexdigest()

        entry = {
            "symbol": symbol,
            "tf": tf_name,
            "first": int(resampled["t"].iloc[0]) if not resampled.empty else None,
            "last": int(resampled["t"].iloc[-1]) if not resampled.empty else None,
            "rows": int(len(resampled)),
            "content_sha": content_sha,
        }
        report.tiers[tf_name] = entry

        manifest.setdefault(symbol, {})[tf_name] = entry

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8"
    )

    return report
