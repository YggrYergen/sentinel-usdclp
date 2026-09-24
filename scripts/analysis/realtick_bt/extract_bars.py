r"""Component 1b -- fresh authoritative M15 BID bars (READ-ONLY).

The main lake's M15 tail is stale (unsupervised bars ingester). For the backtest we
pull XAUUSD M15 bars 2026-01-01..2026-07-25 straight from the MT5_Tester local cache
(copy_rates_range, same BID/epoch convention as data/lake) into a dedicated file so the
backtest never depends on the stale lake tail. Columns t,o,h,l,c,v -- identical to the
lake bar schema the report harness reads.

NO ORDERS. Guard: sanctioned-demo login + anti-order self-check.

CLOCK CONVENTION: the `t` column holds MT5 epochs, which already encode the BROKER SERVER
wall clock (server = UTC-4), not true UTC. Decode with `datetime.utcfromtimestamp()` (zero
offset -> server clock verbatim). `datetime.fromtimestamp()` is wrong: it re-applies this
PC's local offset on top, and the host is in Chile, so that error even changes size at the
DST boundary (3 h before 2026-04-05, 4 h after). Same convention as backtest.py.
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import MetaTrader5 as mt5

_ORDER_CALL = "mt5." + "order_" + "send"
assert _ORDER_CALL not in open(__file__, encoding="utf-8").read(), "order call present in source"

SANCTIONED_DEMO = {2883015767, 2883016567}
REAL_LOGIN = 2883011573
EXE = r"D:\FOREX\MT5_Tester\terminal64.exe"
SYMBOL = "XAUUSD"
OUT = Path(r"D:\FOREX\data\lake_ticks\XAUUSD\_bars_M15.parquet")
START = datetime(2026, 1, 1)
END = datetime(2026, 7, 25)


def log(m: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)


def main() -> int:
    if not mt5.initialize(path=EXE):
        log(f"initialize FAILED: {mt5.last_error()}"); return 1
    ai = mt5.account_info()
    login = getattr(ai, "login", None)
    if login == REAL_LOGIN or login not in SANCTIONED_DEMO:
        log(f"REFUSE login={login}"); mt5.shutdown(); return 2
    log(f"attached login={login} server={ai.server}")
    mt5.symbol_select(SYMBOL, True)

    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M15, START, END)
    mt5.shutdown()
    if rates is None or len(rates) == 0:
        log(f"EMPTY: {mt5.last_error()}"); return 3
    df = pd.DataFrame(rates)
    out = pd.DataFrame({
        "t": df["time"].astype("int64"),
        "o": df["open"].astype("float64"), "h": df["high"].astype("float64"),
        "l": df["low"].astype("float64"), "c": df["close"].astype("float64"),
        "v": df["tick_volume"].astype("int64"),
    }).drop_duplicates("t").sort_values("t").reset_index(drop=True)
    out.to_parquet(OUT, index=False)
    log(f"-> {OUT.name}: {len(out)} M15 bars  "
        # server wall clock; see CLOCK CONVENTION in the module docstring
        f"{datetime.utcfromtimestamp(out.t.iloc[0])} .. {datetime.utcfromtimestamp(out.t.iloc[-1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
