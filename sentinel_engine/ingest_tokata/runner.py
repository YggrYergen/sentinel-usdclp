"""sentinel_engine.ingest_tokata.runner — `import_all(tokata_root, registry)`
orchestrator (M0.2, plan §D.8).

Walks the READ-ONLY TOKATA tree and drives the four importers in order:
    1. backtest_results/mt5_ledger.csv        -> ledger.import_ledger
    2. backtest_results/preregistro.csv       -> preregistro.import_preregistro
    3. mt5/reports/*_signals.csv               -> signals.import_signals (per file)
    4. backtest_results/forward_*.csv          -> forward.import_forward (per file)

`.htm` reports are NOT parsed here (report_path already comes from the
ledger; `.htm` metric parsing is backlog B3, §D.8).

Signals-file -> run_id resolution (§D.8: "run_id matcheado por variant_id +
periodo del nombre de archivo; si ambiguo, registrar en audit_log y
saltar"): a signals filename is matched against every known `variant_id` in
the registry by substring/token overlap; if exactly one run exists for the
matched variant we attach that run_id, if zero or more-than-one runs match
we log an `import_skip` audit entry and still import the trades with
`run_id=None` (never aborting the import) rather than silently guessing.

`D:/WebDev/TOKATA/**` is read-only: this module only ever opens files here
for reading; it never writes/moves/renames anything under `tokata_root`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import ImportReport
from . import forward as forward_mod
from . import ledger as ledger_mod
from . import preregistro as preregistro_mod
from . import signals as signals_mod

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokens(s: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(s)}


def _resolve_run_id_for_signals(path: Path, registry: Any) -> tuple[str | None, str | None]:
    """Best-effort match of a `*_signals.csv` filename to a single run's
    variant_id. Returns (run_id, variant_id) — run_id is None if no
    unambiguous match was found (variant_id may still be set for origin_id)."""
    stem_tokens = _tokens(path.stem)

    result = registry.query_runs(limit=100000, offset=0)
    rows = result["rows"]

    variant_ids = {r["variant_id"] for r in rows if r.get("variant_id")}
    matched_variants = [
        vid for vid in variant_ids if _tokens(vid) and _tokens(vid) <= stem_tokens
    ]

    if len(matched_variants) != 1:
        return None, (matched_variants[0] if matched_variants else None)

    variant_id = matched_variants[0]
    matching_runs = [r for r in rows if r.get("variant_id") == variant_id]
    if len(matching_runs) == 1:
        return matching_runs[0]["run_id"], variant_id
    return None, variant_id


def import_all(tokata_root: Path, registry: Any) -> ImportReport:
    root = Path(tokata_root)
    report = ImportReport()

    ledger_path = root / "backtest_results" / "mt5_ledger.csv"
    if ledger_path.exists():
        report.merge(ledger_mod.import_ledger(ledger_path, registry))

    preregistro_path = root / "backtest_results" / "preregistro.csv"
    if preregistro_path.exists():
        report.merge(preregistro_mod.import_preregistro(preregistro_path, registry))

    reports_dir = root / "mt5" / "reports"
    if reports_dir.exists():
        for signals_path in sorted(reports_dir.glob("*_signals.csv")):
            run_id, variant_id = _resolve_run_id_for_signals(signals_path, registry)
            if run_id is None:
                registry.audit(
                    "ingest_tokata.runner", "import_skip",
                    {
                        "file": str(signals_path),
                        "reason": "ambiguous_or_no_run_match",
                        "variant_id": variant_id,
                    },
                )
            report.merge(
                signals_mod.import_signals(
                    signals_path, registry, variant_id=variant_id, run_id=run_id,
                )
            )

    backtest_results_dir = root / "backtest_results"
    if backtest_results_dir.exists():
        for forward_path in sorted(backtest_results_dir.glob("forward_*.csv")):
            report.merge(forward_mod.import_forward(forward_path, registry))

    forward_daily_dir = backtest_results_dir / "forward_daily"
    if forward_daily_dir.exists():
        for forward_path in sorted(forward_daily_dir.glob("*.csv")):
            report.merge(forward_mod.import_forward(forward_path, registry))

    return report


def _main() -> None:
    import argparse

    from sentinel_engine.research.registry2 import ResearchRegistry

    parser = argparse.ArgumentParser(description="Import TOKATA artifacts into the research registry")
    parser.add_argument("--root", required=True, help="TOKATA root directory (read-only)")
    parser.add_argument("--db", default="data/research.db", help="Registry SQLite db path")
    args = parser.parse_args()

    registry = ResearchRegistry(Path(args.db))
    report = import_all(Path(args.root), registry)
    print(
        f"files={report.files} rows_new={report.rows_new} "
        f"rows_skipped={report.rows_skipped} errors={len(report.errors)}"
    )
    for err in report.errors[:50]:
        print(f"  - {err}")


if __name__ == "__main__":
    _main()
