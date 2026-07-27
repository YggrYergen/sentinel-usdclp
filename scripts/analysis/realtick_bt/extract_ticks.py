r"""Component 1 -- Tick lake extractor (READ-ONLY).

Attach to MT5_Tester (saved demo login), read XAUUSD real ticks 2026-01..07 from the
LOCAL .tkc cache via copy_ticks_range, and persist per server-month to
data/lake_ticks/XAUUSD/<YYYYMM>.parquet with columns [t_msc, bid, ask].

Server/tz convention: copy_ticks_range interprets NAIVE datetimes on the HOST clock, and
the month windows below are naive, so each file is bucketed on the host clock -- NOT on
the server clock. Those coincide only while the host sits at UTC-4; this host is in Chile,
which observes DST, so from 2026-01-01 to 2026-04-04 (UTC-3) the boundaries are off by an
hour more than afterwards. Concretely 202603.parquet runs to server 2026-04-01 02:59:59
and 202604.parquet starts at 03:00 -- file <YYYYMM> is NOT exactly server-month <YYYYMM>.

Consumers must therefore not assume the bucketing: backtest.py's Ticks router probes the
neighbouring month files, which is correct for any host offset. Per-tick epochs are a
separate matter -- an MT5 epoch already encodes the SERVER wall clock, so decode it with
`datetime.utcfromtimestamp()` (zero offset). `datetime.fromtimestamp()` is wrong: it
re-applies the host offset on top, with the DST-varying error described above.

NO ORDERS. Guard: sanctioned-demo login check + anti-order self-check.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

# read-only self-check: this source must not reference the order API
_ORDER_CALL = "mt5." + "order_" + "send"
assert _ORDER_CALL not in open(__file__, encoding="utf-8").read(), "order call present in source"

SANCTIONED_DEMO = {2883015767, 2883016567}
REAL_LOGIN = 2883011573
EXE = r"D:\FOREX\MT5_Tester\terminal64.exe"
SYMBOL = "XAUUSD"
OUT = Path(r"D:\FOREX\data\lake_ticks\XAUUSD")
MONTHS = [(2026, m) for m in range(1, 8)]  # Jan..Jul 2026


def log(m: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not mt5.initialize(path=EXE):
        log(f"initialize FAILED: {mt5.last_error()}")
        return 1
    ai = mt5.account_info()
    login = getattr(ai, "login", None)
    if login == REAL_LOGIN:
        log("REFUSE: attached to REAL account"); mt5.shutdown(); return 2
    if login not in SANCTIONED_DEMO:
        log(f"REFUSE: login {login} not in sanctioned demo set"); mt5.shutdown(); return 2
    log(f"attached login={login} server={ai.server} trade_allowed={mt5.terminal_info().trade_allowed}")
    mt5.symbol_select(SYMBOL, True)

    grand = 0
    for (y, mo) in MONTHS:
        start = datetime(y, mo, 1)
        end = datetime(y + (mo == 12), (mo % 12) + 1, 1)
        parts = []
        w = start
        while w < end:
            we = min(w + timedelta(days=7), end)
            t = mt5.copy_ticks_range(SYMBOL, w, we, mt5.COPY_TICKS_ALL)
            n = 0 if t is None else len(t)
            if n:
                parts.append(t)
            log(f"  {y}-{mo:02d}  {w:%m-%d}..{we:%m-%d}: {n:>8} ticks"
                + ("" if n else f"  last_error={mt5.last_error()}"))
            w = we
        if not parts:
            log(f"  {y}-{mo:02d}: EMPTY -- no cached ticks"); continue
        arr = np.concatenate(parts)
        df = pd.DataFrame({
            "t_msc": arr["time_msc"].astype("int64"),
            "bid": arr["bid"].astype("float64"),
            "ask": arr["ask"].astype("float64"),
        }).drop_duplicates("t_msc").sort_values("t_msc").reset_index(drop=True)
        p = OUT / f"{y}{mo:02d}.parquet"
        df.to_parquet(p, index=False)
        # server wall clock; see the tz note in the module docstring
        span0 = datetime.utcfromtimestamp(df.t_msc.iloc[0] / 1000)
        span1 = datetime.utcfromtimestamp(df.t_msc.iloc[-1] / 1000)
        log(f"  -> {p.name}: {len(df):>8} ticks  {span0} .. {span1}")
        grand += len(df)
    mt5.shutdown()
    log(f"DONE -- total {grand} ticks across {len(MONTHS)} months")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
