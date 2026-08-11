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
the server wall clock. No `datetime.fromtimestamp()` / `.utcfromtimestamp()`
call exists anywhere in this module -- zero zone-conversion surface.

NO ORDERS. Guards, in order: terminal-running check, account guard
(login_prohibido / logins_sancionados), anti-order self-check (below), then
download.
"""
from __future__ import annotations

import subprocess
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

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

            if path.exists():
                existing = pd.read_parquet(path, columns=["t_msc"])
                n = len(existing)
                meses[key] = {
                    "ticks": n,
                    "t_msc_min": int(existing["t_msc"].min()) if n else None,
                    "t_msc_max": int(existing["t_msc"].max()) if n else None,
                    "escrito": False,
                }
                ticks_total += n
                continue

            start = datetime(y, mo, 1)
            end = datetime(y + (mo == 12), (mo % 12) + 1, 1)
            raw = provider.copy_ticks_range(symbol, start, end, provider.COPY_TICKS_ALL)
            n_raw = 0 if raw is None else len(raw)

            if n_raw == 0:
                meses[key] = {"ticks": 0, "t_msc_min": None, "t_msc_max": None, "escrito": False}
                continue

            df = pd.DataFrame({
                "t_msc": np.asarray(raw["time_msc"]).astype("int64"),
                "bid": np.asarray(raw["bid"]).astype("float64"),
                "ask": np.asarray(raw["ask"]).astype("float64"),
            })
            df.to_parquet(path, index=False)

            n = len(df)
            meses[key] = {
                "ticks": n,
                "t_msc_min": int(df["t_msc"].min()) if n else None,
                "t_msc_max": int(df["t_msc"].max()) if n else None,
                "escrito": True,
            }
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
