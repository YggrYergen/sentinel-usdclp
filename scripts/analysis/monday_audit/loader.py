"""scripts/analysis/monday_audit/loader.py -- one merged, typed view of the
real-tick reconstruction that every Track-A audit question reads.

SUBSTRATE (spec section 5.1): data/analysis/realtick_bt/positions_*.csv, 2 347
positions across 7 months (S6 912 / S7 1167 / ST 268). NOTHING is re-simulated
here -- these are the positions the real-tick backtest already produced.

`net_067lot_clp` is the net CLP result AT 0.67 LOT. Lot scaling is exactly
linear (price PnL, commission and swap are all per-lot), so `net_at_lot`
rescales it; ratios (WR, PF, drawdown %) are lot-invariant.

Timestamps are broker SERVER time. They are only ever compared to each other in
Track A, so no timezone conversion is performed -- and none should be added.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REALTICK_DIR = Path(__file__).resolve().parents[3] / "data" / "analysis" / "realtick_bt"
OUT_DIR = Path(__file__).resolve().parents[3] / "data" / "analysis" / "monday_audit"

SOURCE_LOT = 0.67

STRATEGY_FILES = {
    "S6-K2P0": "positions_S6-K2P0.csv",
    "S7-TPNONE": "positions_S7-TPNONE.csv",
    "SuperTrend-p14x3-M15": "positions_SuperTrend-p14x3-M15.csv",
}


@dataclass(frozen=True)
class Position:
    strategy: str
    side: str
    ficha: str
    reason: str
    t_in: datetime
    t_out: datetime
    entry_fill: float
    exit_fill: float
    spread: float
    entry_delay_bars: int
    net_067lot_clp: float
    month: str

    def net_at_lot(self, lot: float) -> float:
        """Net CLP rescaled to `lot`. Linear by construction."""
        return self.net_067lot_clp * (lot / SOURCE_LOT)


def load_positions(root: str | Path = REALTICK_DIR) -> list[Position]:
    """Every position from the three CSVs, tagged with its strategy and sorted
    by entry time (ties broken by strategy name, so the order is total and the
    outputs are reproducible byte-for-byte)."""
    out: list[Position] = []
    for strategy, filename in STRATEGY_FILES.items():
        path = Path(root) / filename
        text = path.read_text(encoding="utf-8")
        for row in csv.DictReader(text.splitlines()):
            if not (row.get("t_in") or "").strip():
                continue
            out.append(Position(
                strategy=strategy,
                side=row["side"],
                ficha=row["ficha"],
                reason=row["reason"],
                t_in=datetime.fromisoformat(row["t_in"]),
                t_out=datetime.fromisoformat(row["t_out"]),
                entry_fill=float(row["entry_fill"]),
                exit_fill=float(row["exit_fill"]),
                spread=float(row["spread"]),
                entry_delay_bars=int(row["entry_delay_bars"]),
                net_067lot_clp=float(row["net_067lot_clp"]),
                month=row["month"],
            ))
    out.sort(key=lambda p: (p.t_in, p.strategy))
    return out


def write_artifact(name: str, payload: dict) -> Path:
    """Persist one audit answer as pretty JSON. Every Track-A module ends here,
    so every number in the Monday document is traceable to a file on disk."""
    import json
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str),
                    encoding="utf-8")
    return path
