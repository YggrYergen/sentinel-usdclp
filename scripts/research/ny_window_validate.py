r"""Validacion empirica de la ventana NY (T0.13 -> codigo, Artefacto 3).

Por que existe. T0.13 (cerrado) establecio que el gate de spread 0.5 del
sistema vivo de Capitaria es, en realidad, un reloj: 18:00 -> 02:00 hora de
Nueva York. `scripts/research/ny_window.py` implementa esa regla como codigo.
Este script MIDE, sobre ticks reales de Capitaria, si la regla de reloj
reproduce el comportamiento del gate de spread que ya se observo en vivo. No
interpreta ni concluye (charter SS B: REPORT-ONLY) -- solo calcula numeros y
los escribe a disco.

R1-bis (charter SS A.11): NO modifica `scripts/analysis/realtick_bt/backtest.py`.
Reutiliza `bt.TICKDIR` (backtest.py:52) para localizar los parquet de ticks y
copia VERBATIM la condicion de "estado estrecho" de `backtest.py:358`
(`abs(spread - 0.5) <= 0.05`) -- no se reescribe ni se redondea.

Sustrato: mismo tramo pre-holdout que T0.6 (2026-01-01 -> 2026-05-11), que
cubre ambos cruces DST relevantes (2026-03-08 EEUU, 2026-04-05 Chile) con
semanas de margen a ambos lados. HOLDOUT SELLADO (charter SS A.14 + D-31):
Capitaria 2026-05-12 -> 2026-07-26 es intocable; este script lleva una guarda
dura que aborta si el rango pedido tocara ese tramo.

Que reporta (verbatim, sin interpretar):
  - Agregado sobre todo el tramo: % de ticks en estado estrecho, dentro y
    fuera de la ventana NY.
  - Desglose semana a semana alrededor de cada cruce DST (>=3 semanas antes y
    >=3 despues de cada uno), que es donde T0.13 pide mirar -- el promedio
    puede esconder semanas enteras mal desplazadas justo en la transicion.

Uso:  python -m scripts.research.ny_window_validate
"""
from __future__ import annotations

import calendar
import json
import subprocess
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(r"D:\FOREX")
OUT_DIR = (
    ROOT / "research" / "fases" / "F0-preparacion" / "04-resultados"
    / "T0.13-ventana-ny"
)

# D-31 acto 1: Capitaria 2026-05-12 -> 2026-07-26, intocable (charter SS A.14).
HOLDOUT_INI = calendar.timegm(datetime(2026, 5, 12).timetuple())
HOLDOUT_FIN = calendar.timegm(datetime(2026, 7, 27).timetuple())  # exclusivo

# Mismo tramo pre-holdout que T0.6 (scripts/research/baseline_golden.py):
# cubre ambos cruces DST con semanas de margen y no toca el sello.
RANGE_INI = calendar.timegm(datetime(2026, 1, 1).timetuple())
RANGE_FIN = calendar.timegm(datetime(2026, 5, 12).timetuple())  # exclusivo

DST_EEUU_2026 = date(2026, 3, 8)
DST_CHILE_2026 = date(2026, 4, 5)
BROKER = "capitaria"

from scripts.analysis.realtick_bt import backtest as bt  # noqa: E402
from scripts.research.ny_window import in_ny_window, server_epoch_to_ny  # noqa: E402


def _assert_no_holdout_overlap(ini: float, fin: float) -> None:
    """Guarda dura (charter SS A.14): aborta si [ini, fin) tocara el holdout
    sellado. `fin` es exclusivo, igual que HOLDOUT_FIN."""
    if ini < HOLDOUT_FIN and fin > HOLDOUT_INI:
        raise SystemExit(
            f"ABORTADO: el rango solicitado [{ini}, {fin}) toca el holdout "
            f"sellado [{HOLDOUT_INI}, {HOLDOUT_FIN}) (charter SS A.14 + D-31). "
            "No se leyo ningun tick."
        )


def _months_in_range(ini: float, fin: float) -> list[str]:
    """Nombres YYYYMM de los parquet de bt.TICKDIR que cubren [ini, fin)."""
    d0 = datetime.utcfromtimestamp(ini)
    d1 = datetime.utcfromtimestamp(fin)
    out = []
    y, m = d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _load_ticks(ini: float, fin: float) -> pd.DataFrame:
    """Carga ticks crudos (t_msc, bid, ask) de bt.TICKDIR para [ini, fin),
    recorta por t exacto. Nunca toca ficheros fuera de los meses pedidos."""
    frames = []
    for ym in _months_in_range(ini, fin):
        p = bt.TICKDIR / f"{ym}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p, columns=["t_msc", "bid", "ask"])
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["t_msc", "bid", "ask"])
    df = pd.concat(frames, ignore_index=True)
    t = df["t_msc"].to_numpy() / 1000.0
    mask = (t >= ini) & (t < fin)
    df = df.loc[mask].copy()
    df["t"] = t[mask]
    return df.sort_values("t").reset_index(drop=True)


def _narrow_mask(df: pd.DataFrame) -> pd.Series:
    """Estado 'estrecho' VERBATIM de backtest.py:358 -- abs(spread-0.5)<=0.05.
    No se reescribe ni se redondea."""
    spread = df["ask"] - df["bid"]
    return (spread - 0.5).abs() <= 0.05


def _dentro_mask(df: pd.DataFrame) -> pd.Series:
    return df["t"].map(lambda t: in_ny_window(server_epoch_to_ny(t, BROKER)))


def _pct(numer: int, denom: int) -> float | None:
    return round(100.0 * numer / denom, 4) if denom else None


def _agregado(df: pd.DataFrame) -> dict:
    narrow = _narrow_mask(df)
    dentro = _dentro_mask(df)
    n_dentro = int(dentro.sum())
    n_fuera = int((~dentro).sum())
    narrow_dentro = int((narrow & dentro).sum())
    narrow_fuera = int((narrow & ~dentro).sum())
    return {
        "n_ticks": int(len(df)),
        "n_dentro_ventana": n_dentro,
        "n_fuera_ventana": n_fuera,
        "pct_estrecho_dentro_ventana": _pct(narrow_dentro, n_dentro),
        "pct_estrecho_fuera_ventana": _pct(narrow_fuera, n_fuera),
    }


def _semana(df: pd.DataFrame, anchor: date, offset_dias: int) -> dict:
    """Ticks cuya fecha de reloj de servidor cae en [anchor+offset, anchor+offset+7)."""
    fechas = df["t"].map(lambda t: datetime.utcfromtimestamp(t).date())
    ini = pd.Timestamp(anchor) + pd.Timedelta(days=offset_dias)
    fin = ini + pd.Timedelta(days=7)
    mask = (pd.to_datetime(fechas) >= ini) & (pd.to_datetime(fechas) < fin)
    sub = df.loc[mask]
    d = _agregado(sub)
    d["semana_offset"] = offset_dias // 7  # -3..2
    d["fecha_ini"] = str(ini.date())
    d["fecha_fin"] = str((fin - pd.Timedelta(days=1)).date())
    return d


def _desglose_dst(df: pd.DataFrame, anchor: date) -> list[dict]:
    """>=3 semanas antes y >=3 despues del cruce DST `anchor` (server-wall-clock)."""
    return [_semana(df, anchor, off) for off in range(-21, 21, 7)]


def _git_sha() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def main() -> int:
    _assert_no_holdout_overlap(RANGE_INI, RANGE_FIN)

    df = _load_ticks(RANGE_INI, RANGE_FIN)
    if df.empty:
        raise SystemExit("ningun tick en el rango solicitado -- abortando")

    # Guarda dura post-lectura: ningun tick cargado puede caer dentro del sello.
    intrusos = df[(df["t"] >= HOLDOUT_INI) & (df["t"] < HOLDOUT_FIN)]
    if len(intrusos):
        raise SystemExit(
            f"ABORTADO: {len(intrusos)} ticks cargados caen dentro del holdout "
            "sellado. No se escribio ningun artefacto."
        )

    agregado = _agregado(df)
    desglose_eeuu = _desglose_dst(df, DST_EEUU_2026)
    desglose_chile = _desglose_dst(df, DST_CHILE_2026)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resultado = {
        "generado": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_sha": _git_sha(),
        "broker": BROKER,
        "substrate_id": "capitaria-ticks-2026-preholdout",
        "sustrato": "data/lake_ticks/XAUUSD/ (ticks reales Capitaria)",
        "rango_medido": [
            datetime.utcfromtimestamp(RANGE_INI).strftime("%Y-%m-%d"),
            datetime.utcfromtimestamp(RANGE_FIN).strftime("%Y-%m-%d"),
        ],
        "holdout_excluido": [
            datetime.utcfromtimestamp(HOLDOUT_INI).strftime("%Y-%m-%d"),
            datetime.utcfromtimestamp(HOLDOUT_FIN).strftime("%Y-%m-%d"),
        ],
        "condicion_estrecho": "abs((ask-bid) - 0.5) <= 0.05  (backtest.py:358, verbatim)",
        "ventana_ny": "18:00 -> 02:00 hora America/New_York (T0.13)",
        "agregado": agregado,
        "desglose_dst_eeuu_2026-03-08": desglose_eeuu,
        "desglose_dst_chile_2026-04-05": desglose_chile,
    }
    out_path = OUT_DIR / "validacion.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, sort_keys=False, indent=2, ensure_ascii=False, allow_nan=False)

    print(f"agregado: n={agregado['n_ticks']:,} "
          f"dentro%estrecho={agregado['pct_estrecho_dentro_ventana']} "
          f"fuera%estrecho={agregado['pct_estrecho_fuera_ventana']}")
    print("\n-- DST EEUU 2026-03-08 --")
    for s in desglose_eeuu:
        print(f"  semana {s['semana_offset']:+d} [{s['fecha_ini']}..{s['fecha_fin']}] "
              f"n={s['n_ticks']:5d} dentro%={s['pct_estrecho_dentro_ventana']} "
              f"fuera%={s['pct_estrecho_fuera_ventana']}")
    print("\n-- DST Chile 2026-04-05 --")
    for s in desglose_chile:
        print(f"  semana {s['semana_offset']:+d} [{s['fecha_ini']}..{s['fecha_fin']}] "
              f"n={s['n_ticks']:5d} dentro%={s['pct_estrecho_dentro_ventana']} "
              f"fuera%={s['pct_estrecho_fuera_ventana']}")

    print(f"\nartefacto: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
