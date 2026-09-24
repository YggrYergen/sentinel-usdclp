"""sentinel_engine.ingest_tokata.signals — `mt5/reports/*_signals.csv`
importer (M0.2, plan §D.8).

Source format (real TOKATA file, `;`-separated, 4 columns):
    ts_server;lado;precio;motivo

`lado` in {LARGO, CORTO} (Spanish long/short); `motivo` is one of
`ENTRY_L`/`ENTRY_S` (position opened) or `EXIT_*` (position closed, the
literal suffix becomes `exit_reason`). The EA logs one row per fill, not one
row per trade, so this importer reconstructs trades by pairing each
`ENTRY_*` row with the next `EXIT_*` row for the *same side* (LIFO stack per
side — this file is a single-strategy, effectively single-position ledger so
FIFO/LIFO coincide in practice).

Mapping (§D.8): entradas/salidas del EA -> `trade` rows, `exit_reason` from
the CSV, `exit_reason_source='signals_csv'`. `run_id` is matched by the
caller via `variant_id` (+ optionally a period filename token); ambiguous
matches are the caller's responsibility (see `runner.py`) — this module
takes an explicit `run_id` (already resolved) to stay a pure mapper.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from . import ImportReport, read_text_resilient, sha256_of, to_float

_HEADER_COLS = ("ts_server", "lado", "precio", "motivo")

_SIDE_MAP = {"LARGO": "LONG", "CORTO": "SHORT"}


def _parse_ts(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y.%m.%d %H:%M:%S")
        return dt.isoformat()
    except ValueError:
        return raw  # keep raw string rather than dropping the row


def _split_rows(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return [], []
    header = lines[0].split(";")
    rows = [ln.split(";") for ln in lines[1:]]
    return header, rows


def import_signals(
    path: Path,
    registry: Any,
    variant_id: str | None = None,
    run_id: str | None = None,
) -> ImportReport:
    """Import one `*_signals.csv` file. `run_id`, if given, is attached to
    every emitted trade; otherwise trades are inserted with `run_id=None`
    (caller/runner is responsible for resolving ambiguity per §D.8)."""
    path = Path(path)
    report = ImportReport()
    sha = sha256_of(path)
    if registry.checksum_seen(str(path), sha):
        return report
    report.files = 1

    text = read_text_resilient(path)
    _header, raw_rows = _split_rows(text)

    open_by_side: dict[str, dict[str, Any]] = {}
    trades: list[dict[str, Any]] = []

    for i, row in enumerate(raw_rows, start=2):
        if len(row) < len(_HEADER_COLS):
            report.rows_skipped += 1
            report.errors.append(f"signals row unparseable (fields={len(row)}) at {path}:{i}")
            registry.audit(
                "ingest_tokata.signals", "import_skip",
                {"file": str(path), "row": i, "reason": "field_count_mismatch", "raw": row},
            )
            continue
        try:
            data = dict(zip(_HEADER_COLS, row[:len(_HEADER_COLS)]))
            lado_raw = (data["lado"] or "").strip().upper()
            side = _SIDE_MAP.get(lado_raw)
            if side is None:
                raise ValueError(f"unknown lado: {lado_raw!r}")
            motivo = (data["motivo"] or "").strip()
            ts = _parse_ts(data["ts_server"])
            px = to_float(data["precio"])
            if ts is None or px is None:
                raise ValueError("missing ts_server/precio")

            if motivo.startswith("ENTRY"):
                open_by_side[side] = {
                    "trade_id": f"SIG::{uuid.uuid4().hex}",
                    "run_id": run_id,
                    "origin": "strategy",
                    "origin_id": variant_id,
                    "session_id": None,
                    "ts_in": ts,
                    "ts_out": None,
                    "px_in": px,
                    "px_out": None,
                    "side": side,
                    "exit_reason_source": "signals_csv",
                }
            elif motivo.startswith("EXIT"):
                open_trade = open_by_side.pop(side, None)
                if open_trade is None:
                    # exit with no matching open entry -> unparseable pairing
                    raise ValueError(f"EXIT with no open {side} position")
                open_trade["ts_out"] = ts
                open_trade["px_out"] = px
                open_trade["exit_reason"] = motivo
                trades.append(open_trade)
            else:
                raise ValueError(f"unknown motivo: {motivo!r}")
        except Exception as exc:  # noqa: BLE001 - defensive: never abort import
            report.rows_skipped += 1
            report.errors.append(f"signals row error at {path}:{i}: {exc}")
            registry.audit(
                "ingest_tokata.signals", "import_skip",
                {"file": str(path), "row": i, "reason": str(exc)},
            )

    if trades:
        registry.insert_trades(run_id, trades)
        report.rows_new += len(trades)

    registry.mark_checksum(str(path), sha)
    return report
