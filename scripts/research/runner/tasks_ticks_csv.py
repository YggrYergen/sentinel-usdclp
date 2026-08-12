"""scripts.research.runner.tasks_ticks_csv -- task-type `ticks_csv_mt5`.

Ingests a tick history CSV that was manually exported by hand, from the MT5
terminal UI, for the broker AVA -- symbol `GOLD` (not `XAUUSD`). This is a
*static file* ingest, not a live MT5 API download: this module never
imports the MT5 python package, never touches a terminal, never places an
order. There is nothing here for `guard_cuenta.assert_demo()` to guard,
because nothing here can trade.

CSV format (confirmed against the real file's first lines, PASO 0 of the
brief -- only the header + a handful of rows were read, never the full
8.65 GB): TAB-separated, header literally
`<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>`, e.g.
`2022.01.02\t23:01:00.106\t1829.55\t1829.89\t\t\t6`. `<LAST>`/`<VOLUME>`
empty is normal for a spot/CFD feed (not a defect) and is not validated or
filled in -- those two columns are read and discarded; they do not appear
in the output schema (see below).

Output schema (replicated, not invented): inspected the real
`data/lake_ticks/XAUUSD/*.parquet` files -- columns are exactly
`[t_msc: int64, bid: float64, ask: float64]`, one file per calendar month
named `<YYYYMM>.parquet` (e.g. `202607.parquet`). This module produces the
identical schema and naming convention, but into a SEPARATE lake (below).

Server/tz convention (the trap documented at extract_ticks.py:7-18 and at
the top of tasks_ticks.py): an MT5 tick epoch already encodes the SERVER
wall clock in zero-offset form -- decoded with `datetime.utcfromtimestamp()`,
never `.fromtimestamp()`. `<DATE>`/`<TIME>` in this CSV are already on the
broker's (AVA's) server clock, written by hand from the terminal, with no
zone information at all. `parse_naive_timestamp()` below combines them into
a naive `datetime` that is EXACTLY what the file says (no shift of any
kind), and re-encodes it into `t_msc` using `calendar.timegm()` -- the same
zero-offset function `tasks_ticks.py:_month_end_epoch_ms` already uses --
which never consults the host OS timezone. This is a pure re-encode of the
clock reading already in the CSV into the lake's existing int64 convention,
not a timezone conversion: no `utcnow()`, no `tz_localize()`, no DST/offset
math appears anywhere in this module. The AVA/Capitaria clock offset is
UNMEASURED and is never applied to the data; if it is ever computed, it
belongs in a sidecar metadata file, never mixed into `t_msc`.

Lake separation (charter mandate, non-negotiable): the SAME physical
terminal on this machine serves Capitaria some sessions and AVA others, so
mixing the two substrates would silently contaminate `data/lake_ticks/XAUUSD/`
-- the substrate that feeds A6, the gate for the whole program.
`assert_destino_seguro()` aborts hard if the manifest's `destino` resolves
anywhere inside `data/lake_ticks/`. `destino` has NO default anywhere in
this module -- it is a required manifest field (missing it is a `KeyError`,
same convention as `ticks_mt5`'s required fields).

Streaming (8.65 GB is never loaded into memory): the CSV is read row by row
via the stdlib `csv` module (full control over per-row field-count
validation and exact line numbers for error messages -- pandas' C parser
can silently pad short rows with NaN instead of raising). Valid rows are
buffered per calendar month in batches of `BATCH_SIZE` and flushed to a
per-month `pyarrow.parquet.ParquetWriter` as they fill, so memory use is
bounded by one batch at a time, never a whole month or the whole file.

Forward-fill of bid/ask (correction round, 2026-08-11 -- the original spec's
claim that every row carries both bid and ask was false: `<FLAGS>` is a bit
field -- 2 = only BID changed this tick, 4 = only ASK changed, 6 = both --
and the exporter writes the side that did NOT change as an EMPTY string.
The real ingest aborted on line 6 of the real CSV for exactly this reason).
When `<BID>` or `<ASK>` is empty, it is filled with the last non-empty value
already seen for that same column in this run. This is NOT data cleaning:
`copy_ticks_range` (the live MT5 API path `ticks_mt5` uses, and the path the
existing `data/lake_ticks/XAUUSD/` lake was built from) already returns both
sides populated with the last known value on every tick -- forward-filling
here reconstructs exactly that behavior, so the AVA lake stays comparable to
the Capitaria one. The decision to fill is made from the EMPTY FIELD alone,
never from the `<FLAGS>` bit -- if the two ever disagreed, the data (the
empty/non-empty field) must win over the label (the flags bit). `<FLAGS>`
is recorded only as an audit metric (`flags_distribucion`, a value->count
dict over every row scanned), never consulted for control flow.
`<LAST>`/`<VOLUME>` are unaffected by any of this: still read and
discarded, no forward-fill applied to them.

Metrics returned (and appended to the LEDGER by the runner): besides
`csv_path`/`csv_checksum_sha256`/`filas_leidas`/`filas_escritas`/
`meses_generados`/`t_msc_min`/`t_msc_max`/`bytes_salida`/`ficheros_escritos`,
this module also reports `ticks_bid_arrastrado` and `ticks_ask_arrastrado`
(counts of forward-filled cells) and `flags_distribucion` (the observed
`<FLAGS>` value->count dict), because the fill changes what is actually
written to parquet and must stay auditable.

Cold start: if a column is still empty the first time it is ever needed for
fill (no non-empty value of that column has been seen yet in this run),
there is nothing to carry forward -- this raises `TicksCsvValidationError`
the same as any other validation failure (source line number + offending
row), never a fill with zero, the other side, or an interpolation.

Validation (hard abort, never a silent skip/clean -- charter SS A.13):
before a row is ever buffered for writing, this module checks, in order:
field count == 7, forward-fill (or cold-start abort) of empty bid/ask,
non-empty bid/ask parse as numbers, bid > 0 and ask > 0 (evaluated on the
ALREADY-FILLED values), ask >= bid (likewise on filled values), and t_msc
non-decreasing versus the previous row (ties are fine -- multiple ticks can
share a millisecond; only a value that goes backwards aborts, same
convention `integridad_ticks.py` already uses for `n_no_monotonicos`). Fill
happens before these four checks specifically so a value that only becomes
invalid after being carried forward (e.g. a stale ask that ends up below a
fresh bid) is still caught. Any failure raises `TicksCsvValidationError`
naming the source line number and the offending raw row, and -- because
validation happens BEFORE a row ever reaches a parquet writer -- also
closes and deletes every `.tmp` parquet writer opened during this run
before re-raising, so no half-written output file survives an abort. A
`.tmp` left over from a PRIOR, separately interrupted run is likewise never
treated as data: it is silently overwritten (never appended to) the next
time that month is (re)processed, which is what makes resumption
non-duplicating.

Idempotency (`destino/<YYYYMM>.parquet` already exists -> month skipped
entirely, not re-read into a writer -- but every row is still scanned and
validated, because the CSV must be read start to end regardless and the
monotonic-timestamp invariant is a whole-file property, not a per-month
one). This is simpler than `ticks_mt5`'s tolerance-window completeness
check because there is no "still downloading" concept for a static,
already-fully-exported file: a month's final parquet either exists (done)
or it doesn't (redo it, from scratch, safely).

Safe overwrite (`atomic_finalize_month`): write to `<key>.parquet.tmp`,
validate it with `integridad_ticks.validar_ticks` (belt-and-suspenders --
the per-row checks above already forbid the anomalies it looks for), then
if `<key>.parquet` already exists, rename it (never delete) to
`<key>.parquet.bak-<YYYYmmddHHMMSS>`, and finally rename the `.tmp` into
place. In the normal flow a month only reaches this function when its final
file did NOT already exist (see idempotency above), so the `.bak` branch is
a defensive path, exercised directly by its own unit tests.
"""
from __future__ import annotations

import calendar
import csv
import hashlib
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.research.runner import integridad_ticks
from scripts.research.runner.tasks import register

# read-only self-check: this source must never depend on the MT5 python
# package. Built via concatenation so the literal forbidden token never
# appears verbatim anywhere in this file (a plain literal would make the
# check always "fail", since the check line -- or this docstring -- would
# itself contain it).
_FORBIDDEN_IMPORT = "Meta" + "Trader5"
assert _FORBIDDEN_IMPORT not in open(__file__, encoding="utf-8").read(), (
    "forbidden MT5-package reference present in tasks_ticks_csv.py -- this "
    "task-type ingests a hand-exported CSV, never the MT5 API"
)

EXPECTED_FIELDS = 7
BATCH_SIZE = 500_000
LAKE_TICKS_PARTS = ("data", "lake_ticks")

PARQUET_SCHEMA = pa.schema([
    ("t_msc", pa.int64()),
    ("bid", pa.float64()),
    ("ask", pa.float64()),
])


class TicksCsvError(Exception):
    """Base error for ticks_csv_mt5 aborts."""


class TicksCsvValidationError(TicksCsvError):
    """Raised when a CSV row fails validation: field count, bid/ask parse,
    bid<=0/ask<=0, ask<bid, or a non-monotonic timestamp. Hard abort --
    never a warning, never a skipped row, never a silent fix."""


class TicksCsvDestinoError(TicksCsvError):
    """Raised when the resolved destino falls inside data/lake_ticks/ --
    the Capitaria lake that feeds A6. Mixing AVA ticks into it would
    silently contaminate the program's gate substrate."""


def assert_destino_seguro(destino: Path) -> None:
    """Abort if `destino` resolves anywhere inside data/lake_ticks/.

    Checks the resolved path's components for a consecutive
    ("data", "lake_ticks") pair so it works for any anchor (real repo path
    or a tmp_path fixture) and does not false-positive on a sibling name
    like "lake_ticks_ava" (a distinct path component, never equal to
    "lake_ticks").
    """
    parts = Path(destino).resolve().parts
    for i in range(len(parts) - 1):
        if parts[i] == LAKE_TICKS_PARTS[0] and parts[i + 1] == LAKE_TICKS_PARTS[1]:
            raise TicksCsvDestinoError(
                f"destino {destino} cae dentro de data/lake_ticks/ -- PROHIBIDO: "
                "mezclaria ticks AVA con el lago Capitaria que alimenta A6. "
                "usa un lago separado, p.ej. data/lake_ticks_ava/GOLD/"
            )


def parse_naive_timestamp(date_str: str, time_str: str) -> tuple[datetime, int]:
    """Combine <DATE> (YYYY.MM.DD) + <TIME> (HH:MM:SS.mmm) into a naive
    datetime EXACTLY as written (broker server clock, no zone applied), and
    encode it as a zero-offset epoch-ms int64 (t_msc) via calendar.timegm --
    never .timestamp()/mktime(), which would consult the host OS timezone.
    This mirrors the exact convention already used for t_msc in the
    existing lake (decoded with datetime.utcfromtimestamp(), zero offset --
    see extract_ticks.py:7-18) -- a re-encode of the same clock reading,
    not a timezone conversion.
    """
    y, mo, d = date_str.split(".")
    hh, mm, rest = time_str.split(":")
    ss, ms = rest.split(".")
    ms = int(ms)
    dt = datetime(int(y), int(mo), int(d), int(hh), int(mm), int(ss), ms * 1000)
    t_msc = calendar.timegm(dt.timetuple()) * 1000 + ms
    return dt, t_msc


def atomic_finalize_month(tmp_path: Path, final_path: Path, report_dir: Path) -> Path | None:
    """Validate `tmp_path` (integridad_ticks.validar_ticks -- raises
    IntegrityError and leaves both files untouched on anomaly), then swap it
    into `final_path`. If `final_path` already existed, it is renamed (never
    deleted) to `<name>.bak-<YYYYmmddHHMMSS>` and that path is returned;
    otherwise returns None.
    """
    tmp_path = Path(tmp_path)
    final_path = Path(final_path)

    integridad_ticks.validar_ticks(tmp_path, report_dir)  # raises -> abort, tmp stays

    bak_path = None
    if final_path.exists():
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        bak_path = final_path.with_name(final_path.name + f".bak-{ts}")
        final_path.rename(bak_path)

    tmp_path.rename(final_path)
    return bak_path


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _month_key(dt: datetime) -> str:
    return f"{dt.year:04d}{dt.month:02d}"


def ticks_csv_mt5(params: dict, out_dir: Path) -> dict:
    """Stream-ingest an AVA GOLD tick-history CSV into monthly parquet files.

    params: csv_path (ruta al CSV origen), destino (dir, SIN default --
    debe caer fuera de data/lake_ticks/, ver assert_destino_seguro).
    `out_dir` (the corrida's results dir, injected by the runner) receives
    the per-month integridad_ticks reports.
    """
    csv_path = Path(params["csv_path"])
    destino = Path(params["destino"])
    out_dir = Path(out_dir)

    assert_destino_seguro(destino)

    destino.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    checksum = _sha256_file(csv_path)

    meses: dict[str, dict] = {}
    batch_by_key: dict[str, list[tuple[int, float, float]]] = {}
    open_writers: dict[str, tuple[pq.ParquetWriter, Path]] = {}
    ficheros_escritos: list[str] = []
    meses_generados: list[str] = []

    filas_leidas = 0
    filas_escritas = 0
    t_msc_min_global: int | None = None
    t_msc_max_global: int | None = None
    prev_t_msc: int | None = None
    ticks_bid_arrastrado = 0
    ticks_ask_arrastrado = 0
    flags_distribucion: dict[str, int] = {}
    last_bid: float | None = None
    last_ask: float | None = None

    def _tmp_path_for(key: str) -> Path:
        return destino / f"{key}.parquet.tmp"

    def _get_writer(key: str) -> pq.ParquetWriter:
        if key not in open_writers:
            tmp_path = _tmp_path_for(key)
            writer = pq.ParquetWriter(tmp_path, PARQUET_SCHEMA)
            open_writers[key] = (writer, tmp_path)
        return open_writers[key][0]

    def _flush(key: str) -> None:
        rows = batch_by_key.get(key)
        if not rows:
            return
        table = pa.table({
            "t_msc": [r[0] for r in rows],
            "bid": [r[1] for r in rows],
            "ask": [r[2] for r in rows],
        }, schema=PARQUET_SCHEMA)
        _get_writer(key).write_table(table)
        batch_by_key[key] = []

    def _cleanup_and_abort(msg: str) -> None:
        for _key, (writer, tmp_path) in list(open_writers.items()):
            writer.close()
            if tmp_path.exists():
                tmp_path.unlink()
        raise TicksCsvValidationError(msg)

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader, None)
        if header is None:
            raise TicksCsvValidationError(f"{csv_path}: fichero vacio, sin cabecera")

        line_no = 1
        for row in reader:
            line_no += 1

            if len(row) != EXPECTED_FIELDS:
                _cleanup_and_abort(
                    f"{csv_path}:{line_no}: se esperaban {EXPECTED_FIELDS} campos "
                    f"(<DATE> <TIME> <BID> <ASK> <LAST> <VOLUME> <FLAGS>), se "
                    f"encontraron {len(row)}: {row!r}"
                )

            date_str, time_str, bid_str, ask_str, _last_str, _vol_str, flags_str = row
            filas_leidas += 1
            flags_distribucion[flags_str] = flags_distribucion.get(flags_str, 0) + 1

            # arrastre del ultimo valor conocido: <FLAGS> es un bitfield
            # (2=solo cambio bid, 4=solo cambio ask, 6=ambos) y el exportador
            # de MT5 deja vacio el lado que no cambio en ese tick. La
            # decision de arrastrar se toma del campo vacio, NUNCA de
            # <FLAGS> (auditado arriba, jamas consultado para control de
            # flujo). Corre ANTES de las 4 validaciones de mas abajo.
            if bid_str == "":
                if last_bid is None:
                    _cleanup_and_abort(
                        f"{csv_path}:{line_no}: bid vacio y aun no hay ningun valor "
                        f"previo de bid para arrastrar (arranque en frio): {row!r}"
                    )
                bid = last_bid
                ticks_bid_arrastrado += 1
            else:
                try:
                    bid = float(bid_str)
                except ValueError as exc:
                    _cleanup_and_abort(f"{csv_path}:{line_no}: bid no numerico: {row!r} ({exc})")

            if ask_str == "":
                if last_ask is None:
                    _cleanup_and_abort(
                        f"{csv_path}:{line_no}: ask vacio y aun no hay ningun valor "
                        f"previo de ask para arrastrar (arranque en frio): {row!r}"
                    )
                ask = last_ask
                ticks_ask_arrastrado += 1
            else:
                try:
                    ask = float(ask_str)
                except ValueError as exc:
                    _cleanup_and_abort(f"{csv_path}:{line_no}: ask no numerico: {row!r} ({exc})")

            last_bid = bid
            last_ask = ask

            if bid <= 0 or ask <= 0:
                _cleanup_and_abort(
                    f"{csv_path}:{line_no}: bid<=0 o ask<=0 (bid={bid}, ask={ask}): {row!r}"
                )
            if ask < bid:
                _cleanup_and_abort(
                    f"{csv_path}:{line_no}: ask < bid (bid={bid}, ask={ask}): {row!r}"
                )

            dt, t_msc = parse_naive_timestamp(date_str, time_str)

            if prev_t_msc is not None and t_msc < prev_t_msc:
                _cleanup_and_abort(
                    f"{csv_path}:{line_no}: timestamps no monotonos crecientes "
                    f"(t_msc={t_msc} < anterior={prev_t_msc}): {row!r}"
                )
            prev_t_msc = t_msc

            if t_msc_min_global is None:
                t_msc_min_global = t_msc
            t_msc_max_global = t_msc

            key = _month_key(dt)
            final_path = destino / f"{key}.parquet"

            if key not in meses:
                meses[key] = {
                    "ya_completo": final_path.exists(),
                    "filas_leidas": 0,
                    "filas_escritas": 0,
                    "escrito": False,
                    "bak": None,
                }

            meses[key]["filas_leidas"] += 1

            if meses[key]["ya_completo"]:
                continue

            meses[key]["filas_escritas"] += 1
            filas_escritas += 1
            batch_by_key.setdefault(key, []).append((t_msc, bid, ask))

            if len(batch_by_key[key]) >= BATCH_SIZE:
                _flush(key)

    # EOF: flush remaining batches and finalize every month that was (re)written
    bytes_salida = 0
    for key, rows in list(batch_by_key.items()):
        if rows:
            _flush(key)

    for key, (writer, tmp_path) in list(open_writers.items()):
        writer.close()
        final_path = destino / f"{key}.parquet"
        bak_path = atomic_finalize_month(tmp_path, final_path, out_dir)
        meses[key]["escrito"] = True
        meses[key]["bak"] = str(bak_path) if bak_path is not None else None
        ficheros_escritos.append(str(final_path))
        meses_generados.append(key)
        bytes_salida += final_path.stat().st_size

    return {
        "csv_path": str(csv_path),
        "csv_checksum_sha256": checksum,
        "filas_leidas": filas_leidas,
        "filas_escritas": filas_escritas,
        "meses_generados": sorted(meses_generados),
        "t_msc_min": t_msc_min_global,
        "t_msc_max": t_msc_max_global,
        "bytes_salida": bytes_salida,
        "ficheros_escritos": sorted(ficheros_escritos),
        "meses": meses,
        "ticks_bid_arrastrado": ticks_bid_arrastrado,
        "ticks_ask_arrastrado": ticks_ask_arrastrado,
        "flags_distribucion": flags_distribucion,
    }


register("ticks_csv_mt5", ticks_csv_mt5)
