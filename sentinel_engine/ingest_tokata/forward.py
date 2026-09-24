"""sentinel_engine.ingest_tokata.forward — `backtest_results/forward_*.csv`
+ `forward_daily/` importer (M0.2, plan §D.8).

Source format (real TOKATA file `forward_positions_ledger.csv`, `,`-separated,
17 columns):
    position_id,magic,variante,dir,volume,entry_price,entry_time,exit_price,
    exit_time,pnl_clp,commission,swap,atr_entrada,risk_clp,R_mult,
    motivo_inferido,duracion_min

Mapping (§D.8): -> `forward_session` (one session per distinct `variante`
token — the closest stable grouping key available in this ledger) +
`trade` rows with `origin='strategy'`, `run_id=NULL`, `session_id` set to
the synthesized session id. `dir` (BUY/SELL) -> side (LONG/SHORT).
`motivo_inferido` -> `exit_reason` (`exit_reason_source='forward_ledger'`).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from . import ImportReport, read_text_resilient, sha256_of, to_float

_HEADER_COLS = (
    "position_id", "magic", "variante", "dir", "volume", "entry_price",
    "entry_time", "exit_price", "exit_time", "pnl_clp", "commission",
    "swap", "atr_entrada", "risk_clp", "R_mult", "motivo_inferido",
    "duracion_min",
)
_N_COLS = len(_HEADER_COLS)  # 17

_SIDE_MAP = {"BUY": "LONG", "SELL": "SHORT"}


def _parse_ts(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        return dt.isoformat()
    except ValueError:
        return raw


def _split_rows(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return [], []
    header = lines[0].split(",")
    rows = [ln.split(",") for ln in lines[1:]]
    return header, rows


def import_forward(path: Path, registry: Any) -> ImportReport:
    path = Path(path)
    report = ImportReport()
    sha = sha256_of(path)
    if registry.checksum_seen(str(path), sha):
        return report
    report.files = 1

    text = read_text_resilient(path)
    _header, raw_rows = _split_rows(text)

    seen_sessions: set[str] = set()

    for i, row in enumerate(raw_rows, start=2):
        if len(row) < _N_COLS:
            report.rows_skipped += 1
            report.errors.append(f"forward row unparseable (fields={len(row)}) at {path}:{i}")
            registry.audit(
                "ingest_tokata.forward", "import_skip",
                {"file": str(path), "row": i, "reason": "field_count_mismatch", "raw": row},
            )
            continue
        try:
            data = dict(zip(_HEADER_COLS, row[:_N_COLS]))
            variante = (data["variante"] or "").strip() or "unknown"
            dir_raw = (data["dir"] or "").strip().upper()
            side = _SIDE_MAP.get(dir_raw)
            if side is None:
                raise ValueError(f"unknown dir: {dir_raw!r}")

            position_id = (data["position_id"] or "").strip()
            if not position_id:
                raise ValueError("missing position_id")

            session_id = f"FWD::{variante}"
            if session_id not in seen_sessions:
                registry.upsert_forward_session({
                    "session_id": session_id,
                    "strategy_id": None,
                    "variant_id": None,
                    "cuenta": None,
                    "perfil": variante,
                    "inicio": None,
                    "fin": None,
                    "estado": "forward",
                    "source_file": str(path),
                })
                seen_sessions.add(session_id)

            trade = {
                "trade_id": f"FWDTR::{position_id}",
                "run_id": None,
                "origin": "strategy",
                "origin_id": variante,
                "session_id": session_id,
                "ts_in": _parse_ts(data["entry_time"]),
                "ts_out": _parse_ts(data["exit_time"]),
                "px_in": to_float(data["entry_price"]),
                "px_out": to_float(data["exit_price"]),
                "side": side,
                "volume": to_float(data["volume"]),
                "sl": None,
                "tp": None,
                "exit_reason": (data.get("motivo_inferido") or None),
                "exit_reason_source": "forward_ledger",
                "pnl": to_float(data.get("pnl_clp")),
                "mae": None,
                "mfe": None,
            }
            if trade["ts_in"] is None or trade["px_in"] is None:
                raise ValueError("missing entry_time/entry_price")

            registry.insert_trades(None, [trade])
            report.rows_new += 1
        except Exception as exc:  # noqa: BLE001 - defensive: never abort import
            report.rows_skipped += 1
            report.errors.append(f"forward row error at {path}:{i}: {exc}")
            registry.audit(
                "ingest_tokata.forward", "import_skip",
                {"file": str(path), "row": i, "reason": str(exc)},
            )

    registry.mark_checksum(str(path), sha)
    return report
