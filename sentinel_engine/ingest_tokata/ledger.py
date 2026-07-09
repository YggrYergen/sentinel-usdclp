"""sentinel_engine.ingest_tokata.ledger — `backtest_results/mt5_ledger.csv`
importer (M0.2, plan §D.8).

Source format (real TOKATA file, `;`-separated, 21 columns):
    run_id;variant_id;familia;instrumento;lado;salida;params_hash;
    mecanismo_preregistro;periodo_desde;periodo_hasta;tipo_corrida;status;
    trades;net;pf;wr;payoff;maxdd;sharpe;report_path;fecha_corrida

`mecanismo_preregistro` is free text that sometimes contains unescaped `;`
(the file is not quote-escaped) — a naive `;`-split misaligns every column
after it. We realign: the first 7 fields (run_id..params_hash) and the last
13 fields (periodo_desde..fecha_corrida) are fixed-width; anything left in
the middle is rejoined with `;` back into `mecanismo_preregistro`. Rows with
fewer than 21 raw fields (after realignment attempt) are unparseable and are
skipped + audited.

Mapping (§D.8, normative):
    familia            -> strategy (upsert_strategy(name=familia, familia=familia, platform='mt5'))
    variant_id          -> variant (upsert_variant, params_delta={} — no preregistro joined here)
    params_hash         -> param_set (params_json='{}' if unknown, i.e. no matching preregistro row)
    tipo_corrida         -> fidelity: 'screening*' -> 'screening'; 'validacion'/'validación' -> 'real-tick';
                            'forward*' -> 'forward'; anything else -> 'research'
    engine = 'mt5-tester' (constant)
    trades,net,pf,wr,payoff,maxdd,sharpe,report_path,fecha_corrida,
    periodo_desde,periodo_hasta,status -> 1:1 onto `run`
    + source_file, source_row
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from . import ImportReport, read_text_resilient, sha256_of, to_float, to_int

_RUN_COLUMNS = (
    "run_id", "variant_id", "params_hash", "engine", "fidelity",
    "periodo_desde", "periodo_hasta", "modelo_sim", "status",
    "trades", "net", "pf", "wr", "payoff", "maxdd", "sharpe",
    "metrics_json", "preregistro_id", "report_path", "trades_path",
    "equity_path", "signal_history_path", "fecha_corrida", "seed",
    "config_hash", "source_file", "source_row",
)


def _upsert_run(registry: Any, run_row: dict[str, Any]) -> bool:
    """Insert `run_row` via `registry.insert_run`; if `run_id` already
    exists (the real TOKATA ledger is append-only and legitimately repeats
    run_id across sweep waves/re-registrations — not corruption), UPDATE the
    existing row in place instead of treating it as an error. Returns True
    if a NEW row was created (mirrors "rows_new" semantics), False if an
    existing row was updated."""
    try:
        registry.insert_run(run_row)
        return True
    except sqlite3.IntegrityError:
        conn = registry._connect()
        try:
            cols = [c for c in _RUN_COLUMNS if c != "run_id"]
            set_clause = ", ".join(f"{c}=?" for c in cols)
            payload = {c: run_row.get(c) for c in _RUN_COLUMNS}
            if payload.get("metrics_json") is None:
                payload["metrics_json"] = "{}"
            values = [payload[c] for c in cols] + [run_row["run_id"]]
            conn.execute(f"UPDATE run SET {set_clause} WHERE run_id=?", values)
            conn.commit()
            return False
        finally:
            conn.close()

_HEADER_COLS = (
    "run_id", "variant_id", "familia", "instrumento", "lado", "salida",
    "params_hash", "mecanismo_preregistro", "periodo_desde", "periodo_hasta",
    "tipo_corrida", "status", "trades", "net", "pf", "wr", "payoff",
    "maxdd", "sharpe", "report_path", "fecha_corrida",
)
_N_COLS = len(_HEADER_COLS)  # 21
_N_HEAD_FIXED = 8  # run_id .. mecanismo_preregistro (inclusive)
_N_TAIL_FIXED = _N_COLS - _N_HEAD_FIXED  # periodo_desde .. fecha_corrida (13)


def _fidelity_from_tipo_corrida(tipo_corrida: str) -> str:
    t = (tipo_corrida or "").strip().lower()
    if t.startswith("screening"):
        return "screening"
    if t in ("validacion", "validación") or t.startswith("validacion") or t.startswith("validación"):
        return "real-tick"
    if t.startswith("forward"):
        return "forward"
    return "research"


def _realign_row(raw_fields: list[str]) -> list[str] | None:
    """Realign a raw `;`-split row to exactly `_N_COLS` fields, folding any
    excess middle fields back into `mecanismo_preregistro`. Returns None if
    the row cannot be realigned (too few fields to have both fixed halves)."""
    n = len(raw_fields)
    if n == _N_COLS:
        return raw_fields
    if n < _N_COLS:
        return None
    head = raw_fields[: _N_HEAD_FIXED - 1]  # run_id..params_hash (7 fields)
    tail = raw_fields[n - _N_TAIL_FIXED:]   # periodo_desde..fecha_corrida (13 fields)
    middle = raw_fields[_N_HEAD_FIXED - 1: n - _N_TAIL_FIXED]
    mecanismo = ";".join(middle)
    return head + [mecanismo] + tail


def _split_rows(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return [], []
    header = lines[0].split(";")
    rows = [ln.split(";") for ln in lines[1:]]
    return header, rows


def import_ledger(path: Path, registry: Any) -> ImportReport:
    path = Path(path)
    report = ImportReport()
    sha = sha256_of(path)
    if registry.checksum_seen(str(path), sha):
        return report
    report.files = 1

    text = read_text_resilient(path)
    _header, raw_rows = _split_rows(text)

    for i, raw in enumerate(raw_rows, start=2):  # 1-based; header is line 1
        row = _realign_row(raw)
        if row is None:
            report.rows_skipped += 1
            msg = f"ledger row unparseable (fields={len(raw)}) at {path}:{i}"
            report.errors.append(msg)
            registry.audit(
                "ingest_tokata.ledger", "import_skip",
                {"file": str(path), "row": i, "reason": "field_count_mismatch", "raw": raw[:3]},
            )
            continue
        try:
            data = dict(zip(_HEADER_COLS, row))
            familia = data["familia"].strip()
            variant_id = data["variant_id"].strip()
            run_id = data["run_id"].strip()
            if not familia or not variant_id or not run_id:
                raise ValueError("missing familia/variant_id/run_id")

            strategy_id = registry.upsert_strategy(name=familia, familia=familia, platform="mt5")
            registry.upsert_variant(
                strategy_id=strategy_id,
                variant_id=variant_id,
                params_delta={},
                tf=None,
                instrumento=data.get("instrumento") or None,
                modo_salida=data.get("salida") or None,
            )
            params_hash = (data.get("params_hash") or "").strip() or None
            if params_hash:
                registry.upsert_param_set(params_hash, "{}")

            fidelity = _fidelity_from_tipo_corrida(data.get("tipo_corrida", ""))

            run_row = {
                "run_id": run_id,
                "variant_id": variant_id,
                "params_hash": params_hash,
                "engine": "mt5-tester",
                "fidelity": fidelity,
                "periodo_desde": data.get("periodo_desde") or None,
                "periodo_hasta": data.get("periodo_hasta") or None,
                "modelo_sim": None,
                "status": data.get("status") or None,
                "trades": to_int(data.get("trades")),
                "net": to_float(data.get("net")),
                "pf": to_float(data.get("pf")),
                "wr": to_float(data.get("wr")),
                "payoff": to_float(data.get("payoff")),
                "maxdd": to_float(data.get("maxdd")),
                "sharpe": to_float(data.get("sharpe")),
                "report_path": data.get("report_path") or None,
                "fecha_corrida": data.get("fecha_corrida") or None,
                "source_file": str(path),
                "source_row": i,
            }
            created = _upsert_run(registry, run_row)
            if created:
                report.rows_new += 1
        except Exception as exc:  # noqa: BLE001 - defensive: never abort import
            report.rows_skipped += 1
            report.errors.append(f"ledger row error at {path}:{i}: {exc}")
            registry.audit(
                "ingest_tokata.ledger", "import_skip",
                {"file": str(path), "row": i, "reason": str(exc)},
            )

    registry.mark_checksum(str(path), sha)
    return report
