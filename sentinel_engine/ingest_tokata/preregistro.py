"""sentinel_engine.ingest_tokata.preregistro — `backtest_results/preregistro.csv`
importer (M0.2, plan §D.8).

Source format (real TOKATA file, `;`-separated, 11 columns):
    variant_id;wave;tipo;params_delta_vs_default;mecanismo;efecto_esperado;
    metrica_primaria;umbral_exito;condicion_descarte;autor;fecha

Mapping (§D.8): 1:1 into `preregistration`, plus `raw_json` = the full row.
`preregistro_id` is not a native column in this file; we synthesize one
deterministically from `variant_id` (stable across re-imports so the
INSERT...ON CONFLICT DO NOTHING idempotency in the registry works).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import ImportReport, read_text_resilient, sha256_of

_HEADER_COLS = (
    "variant_id", "wave", "tipo", "params_delta_vs_default", "mecanismo",
    "efecto_esperado", "metrica_primaria", "umbral_exito",
    "condicion_descarte", "autor", "fecha",
)
_N_COLS = len(_HEADER_COLS)  # 11


def _split_rows(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return [], []
    header = lines[0].split(";")
    rows = [ln.split(";") for ln in lines[1:]]
    return header, rows


def import_preregistro(path: Path, registry: Any) -> ImportReport:
    path = Path(path)
    report = ImportReport()
    sha = sha256_of(path)
    if registry.checksum_seen(str(path), sha):
        return report
    report.files = 1

    text = read_text_resilient(path)
    _header, raw_rows = _split_rows(text)

    for i, row in enumerate(raw_rows, start=2):
        if len(row) < _N_COLS:
            report.rows_skipped += 1
            report.errors.append(f"preregistro row unparseable (fields={len(row)}) at {path}:{i}")
            registry.audit(
                "ingest_tokata.preregistro", "import_skip",
                {"file": str(path), "row": i, "reason": "field_count_mismatch", "raw": row},
            )
            continue
        try:
            data = dict(zip(_HEADER_COLS, row[:_N_COLS]))
            variant_id = data["variant_id"].strip()
            if not variant_id:
                raise ValueError("missing variant_id")
            preregistro_id = f"PREG::{variant_id}"
            payload = {
                "preregistro_id": preregistro_id,
                "variant_id": variant_id,
                "hipotesis": data.get("mecanismo") or None,
                "mecanismo": data.get("mecanismo") or None,
                "metrica_primaria": data.get("metrica_primaria") or None,
                "umbral_exito": data.get("umbral_exito") or None,
                "condicion_descarte": data.get("condicion_descarte") or None,
                "fecha": data.get("fecha") or None,
                "autor": data.get("autor") or None,
                "raw_json": json.dumps(data, ensure_ascii=False),
            }
            registry.insert_preregistration(payload)
            report.rows_new += 1
        except Exception as exc:  # noqa: BLE001 - defensive: never abort import
            report.rows_skipped += 1
            report.errors.append(f"preregistro row error at {path}:{i}: {exc}")
            registry.audit(
                "ingest_tokata.preregistro", "import_skip",
                {"file": str(path), "row": i, "reason": str(exc)},
            )

    registry.mark_checksum(str(path), sha)
    return report
