"""Deriva velas M15 BID de AVA desde el lago de ticks (T0.6 mod #10, parte 1).

Por que. El harness real-tick necesita barras M15 para la SENAL (S6 y SuperTrend
son estrategias M15) y ticks reales para los FILLS. Los ticks de AVA ya estan
completos (B9 cerrado, 246,4 M ticks, 2022-01-02 -> 2026-08-12) pero no existen
barras M15 de AVA: sin ellas no hay backtest largo.

Convencion, identica a scripts/analysis/realtick_bt/extract_bars.py:
  - barras BID (extract_bars tira copy_rates_range, que en MT5 son barras BID)
  - columnas t,o,h,l,c,v -- `t` = epoch de APERTURA de la vela, int64
  - `v` = numero de ticks del bucket (equivalente a tick_volume)
  - los epochs YA codifican el reloj del SERVIDOR del broker; se decodifican con
    utcfromtimestamp(), nunca fromtimestamp() (que reaplicaria el offset local)

🔴 HOLDOUT (SS A.14 + D-31 acto 2): el ano 2023 completo esta sellado. Se EXCLUYE
del fichero de salida, no solo del uso. Asi el sello queda garantizado por
construccion y no por la disciplina de quien luego corra un backtest.

🔴 DESTINO fuera del lago de ticks. El lago de Capitaria tiene un
`_bars_M15.parquet` conviviendo con los parquet mensuales de ticks, y eso rompe
cualquier `glob('*.parquet')` que espere la columna t_msc (anotado en BACKLOG).
No se repite: estas barras van a data/lake_bars_ava/.

Uso:  python -m scripts.research.build_bars_ava
"""
from __future__ import annotations

import calendar
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(r"D:\FOREX")
LAGO_TICKS = ROOT / "data" / "lake_ticks_ava" / "GOLD"
OUT_DIR = ROOT / "data" / "lake_bars_ava"
OUT = OUT_DIR / "GOLD_M15.parquet"

BAR_SEC = 900
HOLDOUT_ANIO = "2023"


def main() -> int:
    meses = sorted(p for p in LAGO_TICKS.glob("*.parquet") if p.stem[:4] != HOLDOUT_ANIO)
    saltados = sorted(p.stem for p in LAGO_TICKS.glob("*.parquet") if p.stem[:4] == HOLDOUT_ANIO)
    print(f"meses a procesar: {len(meses)}   excluidos por holdout ({HOLDOUT_ANIO}): {len(saltados)}")

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

    # Guardas fail-loud: el holdout no puede estar, y la vela ha de ser coherente.
    a = calendar.timegm(datetime(2023, 1, 1).timetuple())
    b = calendar.timegm(datetime(2024, 1, 1).timetuple())
    intrusas = out[(out.t >= a) & (out.t < b)]
    if len(intrusas):
        raise SystemExit(f"ABORTADO: {len(intrusas)} velas caen dentro del holdout {HOLDOUT_ANIO}")
    malas = out[(out.h < out.l) | (out.o > out.h) | (out.o < out.l) | (out.c > out.h) | (out.c < out.l)]
    if len(malas):
        raise SystemExit(f"ABORTADO: {len(malas)} velas con OHLC incoherente")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)

    f = lambda x: datetime.utcfromtimestamp(x).strftime("%Y-%m-%d %H:%M")  # server wall clock
    print(f"\n-> {OUT}")
    print(f"   {len(out):,} velas M15   {f(out.t.iloc[0])} .. {f(out.t.iloc[-1])}")
    print(f"   holdout {HOLDOUT_ANIO} ausente por construccion: {len(intrusas) == 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
