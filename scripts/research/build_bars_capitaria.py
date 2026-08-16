"""Deriva velas M15 BID de Capitaria desde el lago de ticks (cierre de B12).

Por que. B12 bloqueaba A6 Pata A (paridad senal-vs-real): las unicas barras
M15 de Capitaria en disco (`data/lake_ticks/XAUUSD/_bars_M15.parquet`)
terminan el 2026-07-24 16:45 (hora de servidor), mientras que la ventana
operativa real de las estrategias vivas (S6 / SuperTrend, cuenta
2883016902) EMPIEZA el 2026-07-27 18:53:30 -- solape cero. S6 y SuperTrend
son estrategias M15: sin barras que cubran esa ventana no hay senal
reproducible y el motor no puede repetir ni una sola posicion real.

Los TICKS de Capitaria si cubren la ventana entera
(`data/lake_ticks/XAUUSD/202607.parquet`, recargado 2026-08-11, y
`202608.parquet`). Este script deriva barras M15 desde esos ticks, igual
que `scripts/research/build_bars_ava.py` hace para AVA.

Convencion, identica a scripts/analysis/realtick_bt/extract_bars.py y a
build_bars_ava.py:
  - barras BID -- columnas t,o,h,l,c,v -- `t` = epoch de APERTURA de la
    vela, int64
  - `v` = numero de ticks del bucket (equivalente a tick_volume)
  - los epochs YA codifican el reloj del SERVIDOR del broker; se decodifican
    con utcfromtimestamp(), NUNCA fromtimestamp() (que reaplicaria el
    offset local) -- todo timestamp del repo es hora de broker (UTC-4)

Esquema de los ticks de Capitaria: verificado igual al de AVA --
columnas `t_msc` (epoch ms, servidor) y `bid` (ademas de `ask`, no usado
aqui). No hace falta adaptacion de columnas.

Holdout: a diferencia del lago de AVA (que arranca en 2022 e incluye el
2023 sellado), el lago de ticks de Capitaria SOLO contiene 2026-01 ..
2026-08 -- no hay ningun ano sellado dentro de este rango, asi que no hay
nada que excluir por holdout. Se deja el gancho (`HOLDOUT_ANIOS`, vacio)
para que si algun dia se recarga historia con anos sellados dentro, la
exclusion por construccion siga aplicando automaticamente.

DESTINO fuera del lago de ticks, y excluyendo el propio `_bars_M15.parquet`
viejo de la entrada. El lago de Capitaria tiene ese `_bars_M15.parquet`
conviviendo con los parquet mensuales de ticks -- convivencia que rompe
cualquier `glob('*.parquet')` que espere la columna t_msc (defecto anotado
en BACKLOG). Este script filtra la entrada por nombre de mes (6 digitos
YYYYMM) para no tropezar con el, y escribe la salida en un directorio
nuevo (`data/lake_bars_capitaria/`), NUNCA dentro del lago de ticks. El
`_bars_M15.parquet` viejo no se toca -- se usa mas abajo solo como lectura,
para la sanidad cruzada del tramo comun.

Uso:  python -m scripts.research.build_bars_capitaria
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(r"D:\FOREX")
LAGO_TICKS = ROOT / "data" / "lake_ticks" / "XAUUSD"
OUT_DIR = ROOT / "data" / "lake_bars_capitaria"
OUT = OUT_DIR / "XAUUSD_M15.parquet"

BAR_SEC = 900
MES_RE = re.compile(r"^\d{6}$")  # YYYYMM -- excluye _bars_M15 y *.bak-*
HOLDOUT_ANIOS: tuple[str, ...] = ()  # nada sellado dentro de 2026-01..2026-08


def main() -> int:
    meses = sorted(p for p in LAGO_TICKS.glob("*.parquet") if MES_RE.match(p.stem))
    ignorados = sorted(p.name for p in LAGO_TICKS.glob("*.parquet*") if not MES_RE.match(p.stem))
    saltados = sorted(p.stem for p in meses if p.stem[:4] in HOLDOUT_ANIOS)
    meses = [p for p in meses if p.stem[:4] not in HOLDOUT_ANIOS]
    print(f"meses a procesar: {len(meses)}   excluidos por holdout: {len(saltados)}   "
          f"ignorados (no-mes, ej. _bars_M15/.bak): {ignorados}")

    partes = []
    for p in meses:
        t = pq.read_table(p, columns=["t_msc", "bid"])
        df = pd.DataFrame({
            "bucket": (t["t_msc"].to_numpy() // 1000 // BAR_SEC) * BAR_SEC,
            "bid": t["bid"].to_numpy(),
        })
        g = df.groupby("bucket", sort=True)["bid"]
        partes.append(pd.DataFrame({
            "t": g.first().index.astype("int64"),
            "o": g.first().to_numpy(),
            "h": g.max().to_numpy(),
            "l": g.min().to_numpy(),
            "c": g.last().to_numpy(),
            "v": g.count().to_numpy().astype("int64"),
        }))
        print(f"  {p.stem}: {len(t):>10,} ticks -> {len(partes[-1]):>6,} velas M15")
        del t, df, g

    out = (pd.concat(partes, ignore_index=True)
             .drop_duplicates("t").sort_values("t").reset_index(drop=True))

    # Guardas fail-loud: cualquier vela OHLC incoherente aborta el build.
    malas = out[(out.h < out.l) | (out.o > out.h) | (out.o < out.l) | (out.c > out.h) | (out.c < out.l)]
    if len(malas):
        raise SystemExit(f"ABORTADO: {len(malas)} velas con OHLC incoherente")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)

    f = lambda x: datetime.utcfromtimestamp(x).strftime("%Y-%m-%d %H:%M")  # server wall clock
    print(f"\n-> {OUT}")
    print(f"   {len(out):,} velas M15   {f(out.t.iloc[0])} .. {f(out.t.iloc[-1])}")
    print(f"   OHLC coherente en todas las velas: {len(malas) == 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
