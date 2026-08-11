"""scripts.research.runner.tasks_ticks -- task-type `ticks_mt5` (T0.4-impl).

Spec: research/fases/F0-preparacion/02-specs/T0.4-brief-task-type-ticks.md.
Reference (read-only, NOT modified): scripts/analysis/realtick_bt/extract_ticks.py.

Attach-only MT5 tick downloader task-type for the runner (protocolo 06).
Registers `ticks_mt5` in scripts.research.runner.tasks so a manifest can
reference it via `tipo: ticks_mt5`.

Attach-only (charter SS A.12): this module never launches a terminal. Before
calling MT5 it verifies a terminal64.exe process is already running
(tasklist); if not, it fails loud and tells the user to open the terminal by
hand. `provider.initialize()` is always called WITHOUT `path=` -- passing
`path=` would make MT5 launch a terminal itself if none is found, which is
exactly what attach-only forbids (and already caused a two-terminal
incident on this machine).

Server/tz convention (same trap as extract_ticks.py:7-18): copy_ticks_range
interprets NAIVE datetimes on the HOST clock, so the naive month-boundary
datetimes passed to it below are on the host clock, not the server clock --
this module does not correct for that (same as the reference) and does not
need to, because it never decodes a t_msc into a datetime: t_msc is stored
and reported as the raw int64 the provider returns, which already encodes
the server wall clock. No `datetime.fromtimestamp()` call exists anywhere in
this module. The one datetime<->epoch arithmetic this module DOES do
(month-end, for the completeness check below) uses `calendar.timegm()`,
never `.timestamp()`: `timegm` never consults the host's actual OS timezone
setting -- it is the zero-offset mirror of the sanctioned
`datetime.utcfromtimestamp()` decode, so no host/server offset is ever
applied in either direction.

NO ORDERS. Guards, in order: terminal-running check, account guard
(login_prohibido / logins_sancionados), anti-order self-check (below), then
download.

Completeness (ronda 1 correction): a month file counts as complete only if
it exists AND its max(t_msc) is within `tolerancia_horas` (manifest
parameter, default 72h -- covers a weekend market closure) of the end of
the requested month. Otherwise the whole month is re-downloaded. Overwrite
is always safe: write `<key>.parquet.tmp`, run integridad_ticks.validar_ticks
on it (raises IntegrityError -- and aborts, leaving the .tmp on disk and the
original untouched -- on any bid/ask anomaly), then rename the previous file
(if any) to `<key>.parquet.bak-<YYYYmmddHHMMSS>` and the .tmp into place.
The previous file is never deleted.
"""
from __future__ import annotations

import calendar
import subprocess
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from scripts.research.runner import integridad_ticks
from scripts.research.runner.tasks import register

# read-only self-check: this source must not reference the order API
_ORDER_CALL = "mt5." + "order_" + "send"
assert _ORDER_CALL not in open(__file__, encoding="utf-8").read(), "order call present in source"


class TicksMT5Error(Exception):
    """Raised when ticks_mt5 aborts: attach-only guard, account guard, or MT5 error."""


def terminal64_running() -> bool:
    """Real detector: True iff a terminal64.exe process is already running.

    Uses `tasklist` (no MT5 call, no terminal launch) so the attach-only
    check can run before touching the MetaTrader5 package at all.
    """
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, check=True,
    )
    return "terminal64.exe" in result.stdout


def _month_range(desde: str, hasta: str) -> list[tuple[int, int]]:
    """(year, month) tuples spanning desde..hasta inclusive (both ISO YYYY-MM-DD)."""
    d0 = date.fromisoformat(desde)
    d1 = date.fromisoformat(hasta)
    if d1 < d0:
        raise TicksMT5Error(f"hasta ({hasta}) es anterior a desde ({desde})")

    months = []
    y, m = d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        months.append((y, m))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return months


def _month_end_epoch_ms(y: int, mo: int) -> int:
    """Zero-offset epoch ms for the first instant of the month after (y, mo).

    Uses calendar.timegm, never .timestamp() / time.mktime() -- those
    consult the host's actual OS timezone; timegm does not. This is the
    exact inverse of the sanctioned `datetime.utcfromtimestamp()` decode.
    """
    end = datetime(y + (mo == 12), (mo % 12) + 1, 1)
    return calendar.timegm(end.timetuple()) * 1000


def _atomic_write_validated(df: pd.DataFrame, final_path: Path, report_dir: Path) -> Path | None:
    """Write df to <final_path>.tmp, validate it, then swap it in atomically.

    On success: if final_path already existed, it is renamed (never deleted)
    to <name>.bak-<YYYYmmddHHMMSS> and the returned Path points to it;
    otherwise returns None. On integrity failure, IntegrityError propagates,
    the .tmp is left on disk for inspection, and final_path (if it existed)
    is untouched.
    """
    tmp_path = final_path.with_name(final_path.name + ".tmp")
    df.to_parquet(tmp_path, index=False)

    integridad_ticks.validar_ticks(tmp_path, report_dir)  # raises IntegrityError -> abort, .tmp stays

    bak_path = None
    if final_path.exists():
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        bak_path = final_path.with_name(final_path.name + f".bak-{ts}")
        final_path.rename(bak_path)

    tmp_path.rename(final_path)
    return bak_path


def ticks_mt5(
    params: dict,
    out_dir: Path,
    *,
    provider=mt5,
    terminal_check=terminal64_running,
) -> dict:
    """Download XAUUSD ticks month by month and persist one parquet per month.

    params: symbol, desde (ISO date), hasta (ISO date), destino (dir),
    logins_sancionados (list[int]), login_prohibido (int).
    `out_dir` (the corrida's results dir, injected by the runner) is unused
    here -- parquets go to `params['destino']` per the manifest.
    `provider` / `terminal_check` are injectable; the defaults above are the
    real ones (the MetaTrader5 module, and a live tasklist check).
    """
    symbol = params["symbol"]
    desde = params["desde"]
    hasta = params["hasta"]
    destino = Path(params["destino"])
    logins_sancionados = set(params["logins_sancionados"])
    login_prohibido = params["login_prohibido"]
    tolerancia_horas = params.get("tolerancia_horas", 72)
    tolerancia_ms = tolerancia_horas * 3_600_000
    out_dir = Path(out_dir)

    if not terminal_check():
        raise TicksMT5Error(
            "ningun terminal64.exe corriendo -- attach-only (charter SS A.12): "
            "el user debe abrir el terminal MT5 a mano antes de correr esta tarea"
        )

    if not provider.initialize():
        raise TicksMT5Error(f"provider.initialize() fallo: {provider.last_error()}")

    try:
        account = provider.account_info()
        login = getattr(account, "login", None)

        if login == login_prohibido:
            raise TicksMT5Error(
                f"login {login} es la cuenta REAL prohibida (login_prohibido) -- "
                "abortando antes de leer ticks"
            )
        if login not in logins_sancionados:
            raise TicksMT5Error(
                f"login {login} no esta en logins_sancionados {sorted(logins_sancionados)} -- "
                "abortando antes de leer ticks"
            )

        destino.mkdir(parents=True, exist_ok=True)

        meses: dict = {}
        ficheros_escritos: list[str] = []
        ticks_total = 0

        for (y, mo) in _month_range(desde, hasta):
            key = f"{y}{mo:02d}"
            path = destino / f"{key}.parquet"
            tramo_fin_ms = _month_end_epoch_ms(y, mo)

            existe = path.exists()
            ticks_antes = None
            rango_antes = None
            completo = False

            if existe:
                existing = pd.read_parquet(path, columns=["t_msc"])
                n_existente = len(existing)
                if n_existente:
                    min_existente = int(existing["t_msc"].min())
                    max_existente = int(existing["t_msc"].max())
                    ticks_antes = n_existente
                    rango_antes = [min_existente, max_existente]
                    completo = (tramo_fin_ms - max_existente) <= tolerancia_ms

            if completo:
                meses[key] = {
                    "ticks": ticks_antes,
                    "t_msc_min": rango_antes[0],
                    "t_msc_max": rango_antes[1],
                    "escrito": False,
                    "redescargado": False,
                }
                ticks_total += ticks_antes
                continue

            start = datetime(y, mo, 1)
            end = datetime(y + (mo == 12), (mo % 12) + 1, 1)
            raw = provider.copy_ticks_range(symbol, start, end, provider.COPY_TICKS_ALL)
            n_raw = 0 if raw is None else len(raw)

            if n_raw == 0:
                meses[key] = {
                    "ticks": ticks_antes or 0,
                    "t_msc_min": rango_antes[0] if rango_antes else None,
                    "t_msc_max": rango_antes[1] if rango_antes else None,
                    "escrito": False,
                    "redescargado": False,
                }
                if ticks_antes:
                    ticks_total += ticks_antes
                continue

            df = pd.DataFrame({
                "t_msc": np.asarray(raw["time_msc"]).astype("int64"),
                "bid": np.asarray(raw["bid"]).astype("float64"),
                "ask": np.asarray(raw["ask"]).astype("float64"),
            })
            bak_path = _atomic_write_validated(df, path, out_dir)

            n = len(df)
            t_msc_min = int(df["t_msc"].min()) if n else None
            t_msc_max = int(df["t_msc"].max()) if n else None
            entry = {
                "ticks": n,
                "t_msc_min": t_msc_min,
                "t_msc_max": t_msc_max,
                "escrito": True,
                "redescargado": existe,
            }
            if existe:
                entry["ticks_antes"] = ticks_antes
                entry["ticks_despues"] = n
                entry["rango_antes"] = rango_antes
                entry["rango_despues"] = [t_msc_min, t_msc_max]
                entry["bak"] = str(bak_path) if bak_path is not None else None
            meses[key] = entry
            ficheros_escritos.append(str(path))
            ticks_total += n

        return {
            "meses": meses,
            "ticks_total": ticks_total,
            "ficheros_escritos": ficheros_escritos,
        }
    finally:
        provider.shutdown()


register("ticks_mt5", ticks_mt5)
