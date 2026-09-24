"""scripts.research.runner.integridad_ticks -- integrity report for a ticks parquet.

Spec: research/fases/F0-preparacion/02-specs/T0.4-brief-task-type-ticks.md, deliverable 2.

Computes facts, not judgments, about a `[t_msc, bid, ask]` ticks parquet: tick
count, min/max t_msc, exact duplicate rows, non-monotonic t_msc, gaps above a
threshold (minutes, default 60) with their (inicio, fin, duracion) list, and
rows with bid<=0, ask<=0 or ask<bid. The report is always written as JSON to
out_dir before returning or raising.

Fail-loud (charter SS A.13): a bid<=0 / ask<=0 / ask<bid row is a data
anomaly. The report is still written (audit trail) and then IntegrityError
is raised -- callers must not continue past this.

No datetime conversion anywhere in this module: t_msc stays a raw int64
(server-clock epoch milliseconds), including in the gap entries. This avoids
the host/server timezone trap documented in
scripts/analysis/realtick_bt/extract_ticks.py:7-18 -- there is nothing to
get wrong if no datetime object is ever constructed from t_msc.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class IntegrityError(Exception):
    """Raised when a tick parquet has a bid/ask data anomaly (charter SS A.13)."""


def validar_ticks(parquet_path: Path, out_dir: Path, *, gap_threshold_min: int = 60) -> dict:
    parquet_path = Path(parquet_path)
    out_dir = Path(out_dir)

    df = pd.read_parquet(parquet_path, columns=["t_msc", "bid", "ask"])
    n = len(df)

    t_msc = df["t_msc"].to_numpy()
    bid = df["bid"].to_numpy()
    ask = df["ask"].to_numpy()

    n_duplicados_exactos = int(df.duplicated().sum())
    n_no_monotonicos = int((t_msc[1:] < t_msc[:-1]).sum()) if n > 1 else 0

    bad_mask = (bid <= 0) | (ask <= 0) | (ask < bid)
    n_bid_ask_invalidos = int(bad_mask.sum())

    huecos = []
    if n > 1:
        umbral_ms = gap_threshold_min * 60_000
        deltas = t_msc[1:] - t_msc[:-1]
        for i, d in enumerate(deltas):
            if d > umbral_ms:
                huecos.append({
                    "inicio_t_msc": int(t_msc[i]),
                    "fin_t_msc": int(t_msc[i + 1]),
                    "duracion_min": float(d) / 60_000.0,
                })

    report = {
        "parquet": str(parquet_path),
        "n_ticks": n,
        "t_msc_min": int(t_msc.min()) if n else None,
        "t_msc_max": int(t_msc.max()) if n else None,
        "n_duplicados_exactos": n_duplicados_exactos,
        "n_no_monotonicos": n_no_monotonicos,
        "gap_threshold_min": gap_threshold_min,
        "huecos": huecos,
        "n_bid_ask_invalidos": n_bid_ask_invalidos,
        "anomalia": n_bid_ask_invalidos > 0,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"integridad_{parquet_path.stem}.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True, indent=2, ensure_ascii=False)

    if report["anomalia"]:
        raise IntegrityError(
            f"anomalia de datos en {parquet_path}: {n_bid_ask_invalidos} fila(s) con "
            f"bid<=0, ask<=0 o ask<bid (charter SS A.13) -- STOP, no continuar"
        )

    return report
