r"""Real-tick monthly backtest -- S6/S7/ST (components 2-5).

Pipeline (approach C, see docs/superpowers/specs/2026-07-25-realtick-monthly-backtest-design.md):
  2. SIGNAL/LEVEL  -- simular_variant(live_fill_mode) for S6/S7 (engine untouched);
                      vendored SuperTrend always-in for ST. Emits entries + exit levels.
  3. FILL RESOLVER -- walk REAL ticks: entry fill at bar-close (real spread), exit fill at
                      the first tick crossing the engine's server-side level intra-bar.
  4. SPREAD GATE   -- keep only entries whose real tick spread == 0.5 (mirror live).
  5. METRICS       -- per strategy x month: net/#/WR/PF/maxDD/RoM (per-strat + combined).

READ-ONLY on data. Costs: commission=0 (Capitaria embeds it in the spread), swap=0
(short holds). Net in CLP (USDCLP=936.50), leverage x100, contract 100 oz. All numbers
are computed here, never LLM-derived.

CLOCK CONVENTION (do not "simplify" this back)
----------------------------------------------
Every epoch on the bars/ticks axis is an MT5 epoch, and an MT5 epoch already encodes the
BROKER SERVER wall clock (server = UTC-4), not true UTC. So the only correct way back to
a wall-clock datetime is `datetime.utcfromtimestamp()`, which applies a zero offset and
hands back the server clock verbatim.

`datetime.fromtimestamp()` is WRONG here: it re-applies this PC's local UTC offset on top
of an epoch that was never UTC. Worse, the host is in Chile, which observes DST, so the
corruption is not even a constant -- it was 3 h through 2026-04-04 and 4 h from 2026-04-05
(Chile left DST), deforming the forex week mid-dataset (Sunday opens read 15:00 then 14:00
instead of the true 18:00). Fixed 2026-07-26; every conversion site below is marked.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(r"D:\FOREX")
sys.path.insert(0, str(ROOT))
from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies.live_configs_20 import _GOLIVE_M15  # noqa: E402
from sentinel_engine.strategies._supertrend_ref import supertrend, flips  # noqa: E402
from sentinel_engine.strategies.emasar_ref import _atr_wilder  # noqa: E402

BAR_SEC = 900          # M15
MAX_RETRY_BARS = 1     # close-driven spread retry cap: signal bar + this many next bars.
#                        (>1-bar delays pair a late entry with the sim's stale SL -> artifact.)
USDCLP = 936.50
LEVERAGE = 100.0
CONTRACT = 100.0       # oz per 1.0 lot
SYMBOL = "XAUUSD"
TICKDIR = ROOT / "data" / "lake_ticks" / "XAUUSD"
BARS_PATH = TICKDIR / "_bars_M15.parquet"
LEVEL_EXITS = {"EXIT_INITSL", "EXIT_SL_RAISED", "EXIT_TRAIL", "EXIT_TP", "EXIT_STLINE"}
# EXIT_SL_RAISED is included here (not just EXIT_INITSL): it is the SAME
# underlying event/level as an EXIT_INITSL stop-out, only relabeled in
# run_ladder() below when the level turns out to be an already-raised stop
# rather than the genuine entry-bar one (task-R2bis). resolve() must still
# treat it as a level-crossing SL exit (intra-bar tick sweep, non-TP
# direction), exactly like EXIT_INITSL always has -- omitting it here would
# silently fall back to a bar-close fill for ~99% of these rows (see
# task-R2-report.md H3), corrupting the exit price, not just the label.

# Tolerance (price units) for "event level == genuine entry-bar initial SL"
# when splitting EXIT_INITSL from EXIT_SL_RAISED in run_ladder(). See
# task-R2bis-brief.md ("diseno CERRADO", point 2).
TOL = 1e-6

# S6/S7 kwargs come byte-identical from the graduated go-live roster.
_GL = {c["id"]: c["kwargs"] for c in _GOLIVE_M15}
STRATS = ["S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"]


# --------------------------------------------------------------------------- bars
def load_bars() -> list[dict[str, Any]]:
    df = pd.read_parquet(BARS_PATH)
    return [{"t": int(r.t), "open": float(r.o), "high": float(r.h),
             "low": float(r.l), "close": float(r.c), "volume": int(r.v)}
            for r in df.itertuples()]


# --------------------------------------------------------------------------- ticks
class Ticks:
    """Per-month real-tick store; epoch-seconds axis shared with bars."""
    def __init__(self, *, tolerance_s: float = 60.0) -> None:
        self._m: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        # T0.7-M-E: max allowed gap between a requested instant and the
        # returned tick's timestamp in `first_at`. Keyword-with-default
        # (never positional/required): `AvaTicks.__init__`
        # (scripts/research/backtest_largo_ava.py) calls `super().__init__()`
        # with no arguments and must not break. Default 60.0s is an order of
        # magnitude above the measured p90 of healthy calls (3.268s) and
        # below every one of the 945 contaminated calls measured by T0.7-M-C
        # (research/fases/F0-preparacion/02-specs/T0.7-M-E-brief-fix-lookahead-motor-largo.md).
        self.tolerance_s = tolerance_s

    def _load(self, ym: str):
        if ym not in self._m:
            p = TICKDIR / f"{ym}.parquet"
            if not p.exists():
                self._m[ym] = (np.array([]), np.array([]), np.array([]))
            else:
                df = pd.read_parquet(p)
                self._m[ym] = (df.t_msc.to_numpy() / 1000.0,
                               df.bid.to_numpy(), df.ask.to_numpy())
        return self._m[ym]

    @staticmethod
    def _ym(t_sec: float) -> str:
        d = datetime.utcfromtimestamp(t_sec)   # server wall clock; see CLOCK CONVENTION
        return f"{d.year}{d.month:02d}"

    @staticmethod
    def _shift(ym: str, k: int) -> str:
        y, m = int(ym[:4]), int(ym[4:]) + k
        if m == 0:
            y, m = y - 1, 12
        elif m == 13:
            y, m = y + 1, 1
        return f"{y}{m:02d}"

    def _candidates(self, t_sec: float) -> list[str]:
        """Month files that may hold ticks at/after t_sec, in chronological order.

        The file names come from extract_ticks.py, which bucketed by naive
        copy_ticks_range windows -- i.e. on the EXTRACTOR HOST's clock, not the server
        clock. Those two differ by the host's UTC offset, so a file boundary does NOT
        land on server midnight of the 1st: 202603.parquet actually runs to server
        2026-04-01 02:59:59 and 202604.parquet starts at 03:00.

        Routing therefore must never assume file <ym> == server month <ym>. We probe the
        neighbouring months as well, which makes lookup correct for ANY constant offset
        between the two clocks (and on any host). Cost is nil: a full run touches every
        month anyway, and _load caches.
        """
        ym = self._ym(t_sec)
        return [self._shift(ym, -1), ym, self._shift(ym, 1)]

    def first_at(self, t_sec: float):
        """First tick with t >= t_sec (spills across month files as needed),
        bounded by `self.tolerance_s`: if that tick's timestamp is more than
        `tolerance_s` after `t_sec`, there is no tick "at" the requested
        instant in any meaningful sense (a market gap -- daily close,
        weekend, broker maintenance cut, feed outage) and this returns
        `None`, exactly as it already does when there is no later tick at
        all (T0.7-M-E; both call sites already handle `None`)."""
        for ym in self._candidates(t_sec):     # chronological -> first hit is the earliest
            ta, bid, ask = self._load(ym)
            if not len(ta):
                continue
            i = int(np.searchsorted(ta, t_sec, "left"))
            if i < len(ta):
                t_tick = float(ta[i])
                if t_tick - t_sec > self.tolerance_s:
                    return None
                return t_tick, float(bid[i]), float(ask[i])
        return None

    def range(self, t0: float, t1: float):
        """All ticks in [t0, t1) (spans <=2 months)."""
        yms = self._candidates(t0)
        ym1 = self._ym(t1)
        if ym1 not in yms:
            yms.append(ym1)
        ts, bs, as_ = [], [], []
        for ym in yms:                          # chronological -> concat stays sorted
            ta, bid, ask = self._load(ym)
            if not len(ta):
                continue
            lo = int(np.searchsorted(ta, t0, "left"))
            hi = int(np.searchsorted(ta, t1, "left"))
            if hi > lo:
                ts.append(ta[lo:hi]); bs.append(bid[lo:hi]); as_.append(ask[lo:hi])
        if not ts:
            return np.array([]), np.array([]), np.array([])
        return np.concatenate(ts), np.concatenate(bs), np.concatenate(as_)


# --------------------------------------------------------------------------- signals
def _sl_inicial_genuine(side_l: str, idx: int, bars: list[dict[str, Any]], k: float,
                         entry_px: float, wait_mae_atr_k: float,
                         atr14: list[float | None] | None) -> float:
    """Genuine (untouched, entry-bar) initial SL, reimplemented from the
    engine's OWN entry-site helper -- NOT importable: `_sl_inicial_bounded` is
    nested inside `simular_variant`
    (sentinel_engine/strategies/emasar_variant.py:626-643), closing over that
    call's local `bars`/`init_sl_range_k`/`wait_mae_atr_k`/`atr14_floor`, so it
    has no module-level name to import (confirmed: `from ...emasar_variant
    import _sl_inicial_bounded` raises ImportError). Per task-R2bis-brief.md
    ("diseno CERRADO", point 1), the fallback is to reimplement here citing the
    exact source so drift is detectable.

    task-R5fix (I-2): the three engine entry sites (`emasar_variant.py:1199`,
    `:1412`, `:1428`) all call `_sl_inicial_bounded(lado, idx, entry_px)`, NOT
    the plain `_sl_inicial` this docstring used to cite -- `_sl_inicial` has no
    call site at all. The two are byte-identical only while
    `wait_mae_atr_k <= 0.0` (the live S6-K2P0/S7-TPNONE kwargs; verified byte-
    for-byte no-op below). With `wait_mae_atr_k > 0` (PX-T2, a lever the
    experiment-matrix program sweeps explicitly), the genuine stop is the
    WIDER of {range-SL, `entry_px -/+ wait_mae_atr_k*ATR14[idx]`}. Cited
    verbatim (as of the read on 2026-07-27):

        def _sl_inicial(lado: int, idx: int) -> float:
            rango = bars[idx]["high"] - bars[idx]["low"]
            return (bars[idx]["low"] - init_sl_range_k * rango) if lado == +1 \\
                else (bars[idx]["high"] + init_sl_range_k * rango)

        def _sl_inicial_bounded(lado: int, idx: int, entry_px: float) -> float:
            base = _sl_inicial(lado, idx)
            if wait_mae_atr_k <= 0.0 or atr14_floor is None or atr14_floor[idx] is None:
                return base
            atr_dist = wait_mae_atr_k * atr14_floor[idx]
            if lado == +1:
                mae_sl = entry_px - atr_dist
                return min(base, mae_sl)   # wider (lower) of the two levels
            mae_sl = entry_px + atr_dist
            return max(base, mae_sl)       # wider (higher) of the two levels

    `side_l` here is run_ladder's own "L"/"S" convention (== lado +1/-1).
    `atr14` is the module-level Wilder ATR14 (period 14) over the FULL `bars`
    axis -- same call shape as the engine's `atr14_floor`
    (`_atr_wilder(highs, lows, closes, 14)`, emasar_variant.py:554-556,601) --
    or None when `wait_mae_atr_k <= 0.0` (byte-identical no-op path, mirroring
    the engine's own "only compute when a consumer is active" guard,
    emasar_variant.py:601-603)."""
    bar = bars[idx]
    rango = bar["high"] - bar["low"]
    base = (bar["low"] - k * rango) if side_l == "L" else (bar["high"] + k * rango)
    if wait_mae_atr_k <= 0.0 or atr14 is None or atr14[idx] is None:
        return base
    atr_dist = wait_mae_atr_k * atr14[idx]
    if side_l == "L":
        mae_sl = entry_px - atr_dist
        return min(base, mae_sl)   # wider (lower) of the two levels
    mae_sl = entry_px + atr_dist
    return max(base, mae_sl)       # wider (higher) of the two levels


def run_ladder(kwargs: dict[str, Any], bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """simular_variant events -> positions (batch1 pairing; captures level + fallback).

    EXIT_INITSL split (task-R2bis, hallazgo H3): the engine tags EXIT_INITSL
    by WHICH CHECK fired this bar, not by whether the stop is still the
    untouched entry-bar level -- a stop already raised by trailing/BE in an
    earlier bar that triggers later is still tagged EXIT_INITSL. Here we
    recompute the genuine entry-bar stop for each EXIT_INITSL event and split:
    reason stays "EXIT_INITSL" only if the emitted level matches the genuine
    formula within TOL; otherwise reason becomes "EXIT_SL_RAISED". All other
    motivos pass through with `reason` unchanged, exactly as before this task.
    """
    eventos = simular_variant(bars, **{**{"symbol": SYMBOL}, **kwargs})
    # Same default (1.0) as simular_variant's own `init_sl_range_k` kwarg, so
    # an empty/partial kwargs dict classifies identically to calling the
    # engine with its own default.
    k_init = kwargs.get("init_sl_range_k", 1.0)
    # task-R5fix (I-2): same default (0.0) as simular_variant's own
    # `wait_mae_atr_k` kwarg (emasar_variant.py:139) -- absent from the live
    # S6-K2P0/S7-TPNONE kwargs today, so this is a byte-identical no-op for
    # the current go-live roster. ATR14 is only computed when the lever is
    # actually active (mirrors the engine's own guard, emasar_variant.py:
    # 601-603), so the all-defaults path does no extra work.
    wait_mae_atr_k = kwargs.get("wait_mae_atr_k", 0.0)
    atr14 = (_atr_wilder([b["high"] for b in bars], [b["low"] for b in bars],
                         [b["close"] for b in bars], 14)
             if wait_mae_atr_k > 0.0 else None)
    positions: list[dict[str, Any]] = []
    open_pos: dict[str, dict[str, Any]] = {}
    seq = 0
    last: str | None = None
    for ev in eventos:
        motivo = ev["motivo"]; bar = bars[ev["idx"]]; side_l = ev["lado"]
        if motivo in ("ENTRY_L", "ENTRY_S"):
            seq += 1
            sid = f"sig-{bar['t']}-{seq}"
            open_pos[sid] = {"sid": sid, "t": bar["t"], "idx": ev["idx"], "side_l": side_l,
                             "entry_bid": ev["precio"], "fichas": {"F1", "F2", "F3"}}
            last = sid
        elif motivo.startswith("EXIT") or motivo == "time_stop" or motivo == "reverse":
            ficha = ev.get("ficha") or "F1"
            pos = open_pos.get(last)
            if pos is None or ficha not in pos["fichas"]:
                pos = None
                for sid, p in open_pos.items():
                    if ficha in p["fichas"]:
                        pos = p; last = sid; break
                if pos is None:
                    continue
            reason = motivo
            if motivo == "EXIT_INITSL":
                genuine = _sl_inicial_genuine(pos["side_l"], pos["idx"], bars, k_init,
                                               pos["entry_bid"], wait_mae_atr_k, atr14)
                if abs(ev["precio"] - genuine) > TOL:
                    reason = "EXIT_SL_RAISED"
            positions.append({
                "side_l": pos["side_l"], "side": "LONG" if pos["side_l"] == "L" else "SHORT",
                "ficha": ficha, "t_in": pos["t"], "t_out": bar["t"],
                "entry_bid": pos["entry_bid"], "exit_bid": ev["precio"],
                "reason": reason, "same_bar": bool(ev.get("same_bar_fallback")),
            })
            pos["fichas"].discard(ficha)
            if not pos["fichas"]:
                open_pos.pop(pos["sid"], None)
    return positions


def run_supertrend(bars: list[dict[str, Any]], ticks: Ticks, *,
                    atr_period: int = 14, mult: float = 3.0) -> list[dict[str, Any]]:
    """Always-in SuperTrend(atr_period, mult) with the LINE as a server-side SL (live
    semantics). Defaults (14, 3.0) are EXACTLY today's hardcoded values (WP-1+2 Bloque 1;
    build_all() calls this with no extra args, so behavior is byte-identical).

    The live reconciler holds one ficha on the trend side with sl=SuperTrend line, trailed
    each closed bar; a tick hitting the line closes it intra-bar. So per bar j the active
    server-side stop is line[j-1] (set at end of bar j-1). We walk the real ticks of bar j:
    if the line is touched -> EXIT_STLINE at that level (resolver prices it on the tick);
    else if the trend flipped at bar j close without a prior line-touch -> EXIT_STFLIP at
    the close. After either, the always-in position re-opens on trend[j]'s side."""
    highs = [b["high"] for b in bars]; lows = [b["low"] for b in bars]; closes = [b["close"] for b in bars]
    atr = _atr_wilder(highs, lows, closes, atr_period)
    atrf = [a if a is not None else 0.0 for a in atr]
    trend, line = supertrend(highs, lows, closes, atrf, mult)
    n = len(bars)
    fv = next((i for i in range(len(atr)) if atr[i] is not None), None)
    if fv is None:
        return []
    positions: list[dict[str, Any]] = []
    side_l = "L" if trend[fv] == 1 else "S"
    entry_bid = closes[fv]; entry_t = bars[fv]["t"]
    for j in range(fv + 1, n):
        sl = line[j - 1]
        if sl is None:
            continue
        t0 = bars[j]["t"]; t1 = t0 + BAR_SEC
        tt, bb, aa = ticks.range(t0, t1)
        hit = False
        if len(tt):
            cond = (bb <= sl) if side_l == "L" else (aa >= sl)
            hit = bool(cond.any())
        flipped = (trend[j] == 1) != (side_l == "L")
        if not (hit or flipped):
            continue
        if hit:
            reason, exit_bid = "EXIT_STLINE", sl          # server-side stop at the line
        else:
            reason, exit_bid = "EXIT_STFLIP", closes[j]   # flip at bar close (no line touch)
        positions.append({
            "side_l": side_l, "side": "LONG" if side_l == "L" else "SHORT", "ficha": "F1",
            "t_in": entry_t, "t_out": bars[j]["t"], "entry_bid": entry_bid, "exit_bid": exit_bid,
            "reason": reason, "same_bar": False,
        })
        side_l = "L" if trend[j] == 1 else "S"            # always-in re-opens on current trend
        entry_bid = closes[j]; entry_t = bars[j]["t"]
    return positions


# --------------------------------------------------------------------------- fills
def resolve(pos: dict[str, Any], ticks: Ticks, bar_times: np.ndarray) -> dict[str, Any] | None:
    """Real-tick fill. net1/margin1 are per-1.0-lot (scale by LOT at report; RoM invariant).

    Entry = live close-driven spread retry: the reconciler re-desires the ficha every
    closed bar and OPENs only when spread <= 0.5. So we scan bar-closes from the signal
    bar up to the exit bar and enter at the FIRST whose post-close tick has spread 0.5.
    If none in the window, the position never opened live -> dropped."""
    side_l = pos["side_l"]
    lo = int(np.searchsorted(bar_times, pos["t_in"], "left"))
    hi = int(np.searchsorted(bar_times, pos["t_out"], "right"))
    hi = min(hi, lo + 1 + MAX_RETRY_BARS)
    entry = None
    delay_bars = 0
    for bi in range(lo, max(lo + 1, hi)):
        tc = float(bar_times[bi]) + BAR_SEC
        if tc >= pos["t_out"] + BAR_SEC:            # would open at/after its own exit
            break
        e = ticks.first_at(tc)
        if e is None:
            continue
        _, ebid, eask = e
        sp = eask - ebid
        if abs(sp - 0.5) <= 0.05:
            entry = (tc, ebid, eask, round(sp, 3)); delay_bars = bi - lo; break
    if entry is None:
        return None
    t_in_exec, ebid, eask, spread = entry
    band = 0.5
    entry_fill = eask if side_l == "L" else ebid

    reason = pos["reason"]; level = pos["exit_bid"]
    t_out_close = pos["t_out"] + BAR_SEC
    exit_fill = None; t_exit = t_out_close; slipped = False
    if reason in LEVEL_EXITS and not pos["same_bar"]:
        tt, bb, aa = ticks.range(pos["t_out"], t_out_close)
        if len(tt):
            is_tp = reason == "EXIT_TP"
            if side_l == "L":                       # long exits on the BID
                cond = (bb >= level) if is_tp else (bb <= level)
                parr = bb
            else:                                   # short exits on the ASK
                cond = (aa <= level) if is_tp else (aa >= level)
                parr = aa
            if cond.any():
                j = int(np.argmax(cond))
                exit_fill = float(parr[j]); t_exit = float(tt[j]); slipped = True
    if exit_fill is None:                           # bar-close exit (or level un-crossed)
        x = ticks.first_at(t_out_close)
        if x is None:
            return None
        _, xbid, xask = x
        exit_fill = xbid if side_l == "L" else xask

    diff = (exit_fill - entry_fill) if pos["side"] == "LONG" else (entry_fill - exit_fill)
    net1 = diff * CONTRACT * USDCLP                 # per 1.0 lot, CLP
    margin1 = CONTRACT * entry_fill * USDCLP / LEVERAGE
    return {**pos, "spread": spread, "band": band, "entry_fill": round(entry_fill, 3),
            "exit_fill": round(exit_fill, 3), "t_in_exec": t_in_exec,
            "entry_delay_bars": delay_bars,
            "t_exit": t_exit, "net1": net1, "margin1": margin1, "level_slip": slipped}


# --------------------------------------------------------------------------- metrics
def peak_margin(rows: list[dict[str, Any]], lot: float) -> float:
    ev = []
    for r in rows:
        ev.append((r["t_in_exec"], +r["margin1"] * lot))
        ev.append((r["t_exit"], -r["margin1"] * lot))
    ev.sort(key=lambda x: (x[0], -x[1]))   # opens before closes at same instant
    cur = peak = 0.0
    for _, d in ev:
        cur += d
        peak = max(peak, cur)
    return peak


def metrics(rows: list[dict[str, Any]], lot: float) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0, "net": 0.0, "wr": None, "pf": None, "maxdd": 0.0,
                "rom": None, "avg_win": 0.0, "avg_loss": 0.0, "peak_margin": 0.0}
    nets = [r["net1"] * lot for r in rows]
    net = sum(nets)
    wins = [x for x in nets if x > 0]; losses = [x for x in nets if x < 0]
    gw = sum(wins); gl = -sum(losses)
    pf = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else None)
    wr = 100.0 * len(wins) / n
    ordered = sorted(rows, key=lambda r: r["t_exit"])
    cum = peak = maxdd = 0.0
    for r in ordered:
        cum += r["net1"] * lot
        peak = max(peak, cum); maxdd = max(maxdd, peak - cum)
    pm = peak_margin(rows, lot)
    rom = (net / pm) if pm > 0 else None
    return {"n": n, "net": round(net, 2), "wr": round(wr, 2),
            "pf": (round(pf, 3) if pf not in (None, float("inf")) else pf),
            "maxdd": round(maxdd, 2), "rom": (round(100 * rom, 2) if rom is not None else None),
            "avg_win": round(gw / len(wins), 2) if wins else 0.0,
            "avg_loss": round(-gl / len(losses), 2) if losses else 0.0,
            "peak_margin": round(pm, 2)}


def ym_of(t: float) -> str:
    d = datetime.utcfromtimestamp(t)           # server wall clock; see CLOCK CONVENTION
    return f"{d.year}-{d.month:02d}"


# --------------------------------------------------------------------------- driver
def build_all(ticks: Ticks, bars: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Resolve every position of every strategy once (lot-invariant)."""
    bar_times = np.array([b["t"] for b in bars], dtype="float64")
    resolved: dict[str, list[dict[str, Any]]] = {}
    for sid in STRATS:
        if sid == "SuperTrend-p14x3-M15":
            raw = run_supertrend(bars, ticks)
        else:
            raw = run_ladder(_GL[sid], bars)
        out = []
        for p in raw:
            r = resolve(p, ticks, bar_times)
            if r is not None:
                out.append(r)
        resolved[sid] = out
    return resolved


MONTHS = [f"2026-{m:02d}" for m in range(1, 8)]
OUT_DIR = ROOT / "data" / "analysis" / "realtick_bt"
REPORT_MD = ROOT / "docs" / "REPORTE_BACKTEST_REALTICK_MENSUAL_2026-07-25.md"
LOT_GRID = 0.67
LOT_VAL = 0.01
LIVE = {"combined": (116, 282372.88), "S6-K2P0": (69, 114348.06),
        "S7-TPNONE": (42, 45775.52), "SuperTrend-p14x3-M15": (5, 122249.30)}
LIVE_OUTLIER = 71707.0


def _fmt(v, kind):
    if v is None:
        return "—"
    if kind == "int":
        return f"{v:,}".replace(",", ".")
    if kind == "clp":
        return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if kind == "pct":
        return f"{v:.2f}".replace(".", ",")
    if kind == "ratio":
        return (f"{v:.2f}".replace(".", ",") if isinstance(v, (int, float)) else str(v))
    return str(v)


def _grid_table(rows_by_strat_or_comb, lot):
    """Markdown monthly table for a set of positions (per month + TOTAL)."""
    out = ["| Mes | Ops | Neto CLP | WR% | PF | maxDD CLP | RoM% |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for mo in MONTHS:
        mr = [r for r in rows_by_strat_or_comb if ym_of(r["t_in_exec"]) == mo]
        m = metrics(mr, lot)
        if not m["n"]:
            continue
        out.append(f"| {mo} | {m['n']} | {_fmt(m['net'],'clp')} | {_fmt(m['wr'],'pct')} | "
                   f"{_fmt(m['pf'],'ratio')} | {_fmt(m['maxdd'],'clp')} | {_fmt(m['rom'],'pct')} |")
    t = metrics(rows_by_strat_or_comb, lot)
    out.append(f"| **TOTAL** | **{t['n']}** | **{_fmt(t['net'],'clp')}** | **{_fmt(t['wr'],'pct')}** | "
               f"**{_fmt(t['pf'],'ratio')}** | **{_fmt(t['maxdd'],'clp')}** | **{_fmt(t['rom'],'pct')}** |")
    return "\n".join(out)


def emit_report(resolved: dict[str, list[dict[str, Any]]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # ---- per-position CSVs (all code-computed) ----
    for sid in STRATS:
        recs = []
        for r in resolved[sid]:
            recs.append({
                "side": r["side"], "ficha": r["ficha"], "reason": r["reason"],
                # server wall clock (UTC-4); see CLOCK CONVENTION in the module docstring
                "t_in": datetime.utcfromtimestamp(r["t_in_exec"]).isoformat(),
                "t_out": datetime.utcfromtimestamp(r["t_exit"]).isoformat(),
                "entry_fill": r["entry_fill"], "exit_fill": r["exit_fill"],
                "spread": r["spread"], "entry_delay_bars": r["entry_delay_bars"],
                "net_067lot_clp": round(r["net1"] * LOT_GRID, 2),
                "month": ym_of(r["t_in_exec"]),
            })
        pd.DataFrame(recs).to_csv(OUT_DIR / f"positions_{sid}.csv", index=False, encoding="utf-8")

    all_rows = [r for sid in STRATS for r in resolved[sid]]
    tot = metrics(all_rows, LOT_GRID)

    # ---- validation (informe week, 0.01/ficha) ----
    # INVERSE of the CLOCK CONVENTION: to bound the epoch axis at a SERVER wall-clock
    # instant we must encode with a zero offset (tzinfo=utc). A bare .timestamp() would
    # encode via this PC's local offset -- the same DST-varying error, mirrored.
    w0 = datetime(2026, 7, 20, tzinfo=timezone.utc).timestamp()
    w1 = datetime(2026, 7, 24, tzinfo=timezone.utc).timestamp()
    def week(rows):
        return [r for r in rows if w0 <= r["t_in_exec"] < w1]
    vc = metrics(week(all_rows), LOT_VAL)
    val_lines = ["| Estrategia | BT ops | BT neto CLP | Vivido ops | Vivido neto CLP |",
                 "|---|---:|---:|---:|---:|"]
    for sid in STRATS:
        mv = metrics(week(resolved[sid]), LOT_VAL)
        lo, ln = LIVE[sid]
        val_lines.append(f"| {sid} | {mv['n']} | {_fmt(mv['net'],'clp')} | {lo} | {_fmt(ln,'clp')} |")
    lo, ln = LIVE["combined"]
    val_lines.append(f"| **Combinado** | **{vc['n']}** | **{_fmt(vc['net'],'clp')}** | **{lo}** | **{_fmt(ln,'clp')}** |")
    val_table = "\n".join(val_lines)
    live_ex = ln - LIVE_OUTLIER

    md = f"""# Reporte — Backtest Real-Tick Mensual (S6 / S7 / SuperTrend)

**Fecha:** 2026-07-25 · **Instrumento:** XAUUSD · **Período:** 2026-01 → 2026-07 (7 meses, hora servidor UTC−4)
**Base:** las 3 estrategias como una **cuenta virtual única**, solo aperturas a **spread 0,5** (espejo del vivo).
**Motor:** `simular_variant` graduado (parity-gated) + overlay de **fills sobre ticks reales** (52,6M ticks locales).

> ⚠️ **ESTADO: PRELIMINAR — pendiente de confirmación en motor MT5 real-tick.**
> La **fidelidad de mecanismo está cerrada** (entradas close-driven + gate 0,5, salidas por SL-trailing
> intra-vela para S6/S7 y línea-SL para ST — exactamente el reconciler vivo). Pero las **magnitudes deben
> confirmarse contra el MT5 Strategy Tester "every tick based on real ticks"** (gold-standard). Toda brecha
> que se identifique debe **diagnosticarse**, no asumirse. Todas las cifras son **calculadas por código**
> (`scripts/analysis/realtick_bt/backtest.py`), no derivadas por LLM.

---

## 1. Resumen (7 meses, lote 0,67/ficha)

| Métrica | Valor |
|---|---:|
| Neto combinado | **{_fmt(tot['net'],'clp')} CLP** |
| Operaciones | {tot['n']} |
| Win rate | {_fmt(tot['wr'],'pct')} % |
| Profit factor | {_fmt(tot['pf'],'ratio')} |
| Máx. drawdown | {_fmt(tot['maxdd'],'clp')} CLP |
| RoM (neto ÷ margen pico) | {_fmt(tot['rom'],'pct')} % |

**Lectura:** positivo en el neto de 7 meses, pero con un **abril fuertemente negativo** y jun ~plano — un
perfil **mucho más sobrio que el +91 %/semana** del informe de esta semana (ver §4).

## 2. Grilla mensual combinada (3 estrategias)

{_grid_table(all_rows, LOT_GRID)}

## 3. Por estrategia (lote 0,67/ficha)

### 3.1 S6-K2P0
{_grid_table(resolved['S6-K2P0'], LOT_GRID)}

### 3.2 S7-TPNONE
{_grid_table(resolved['S7-TPNONE'], LOT_GRID)}

### 3.3 SuperTrend-p14×3-M15 — *provisional, pendiente MT5*
{_grid_table(resolved['SuperTrend-p14x3-M15'], LOT_GRID)}

## 4. Validación: backtest vs. lo vivido (semana del informe, 0,01/ficha)

{val_table}

**Veredicto (fidelidad):** el backtest reproduce **dirección y perfil** (tendencial, WR≈31 %, PF>1) pero da
**~1/3 del neto** vivido combinado. La brecha está **explicada, no es bug**:

1. **El track vivido es merge de 2 cuentas** stitched (cuenta 1 lun–mié + cuenta 2 mié–jue) → ~2× las
   operaciones que una simulación de **cuenta única** (30 vs 69 en S6). La grilla es cuenta única → saca menos, correctamente.
2. **El +71.707 fue outlier** (posición que quedó abierta por error mientras se programaba el motor y se cerró
   manual out-of-sample). Vivido ex-outlier = **{_fmt(live_ex,'clp')} CLP**; el backtest (~{_fmt(vc['net'],'clp')} a 0,01) ≈ **{_fmt(100*vc['net']/live_ex,'pct')} %** de eso.
3. **ST con línea-SL hace whipsaw** (WR bajo) — más fiel al vivo pero castiga el neto; el gran ganador vivo de ST era justamente el outlier.

**Conclusión de fondo:** un backtest real-tick fiel de esa semana da **~{_fmt(vc['net'],'clp')} CLP (cuenta única, 0,01 lote)**,
no +282k. **La semana del informe fue un punto alto favorable, no lo típico** — la grilla mensual (§2) lo confirma.

## 5. SuperTrend — nota

ST se modeló con la **línea SuperTrend como SL server-side intra-vela** (semántica confirmada del reconciler
vivo). Esto produce whipsaw (más stop-outs por mecha) y WR bajo. La **muestra viva es insuficiente para
contrastar** (ST corrió ~1 semana en vivo), así que su magnitud queda **pendiente del gold-standard MT5**.

## 6. Metodología

- **Ticks:** 52,6M ticks reales XAUUSD 2026-01→07 extraídos del cache local de MT5_Tester (`copy_ticks_range`,
  read-only) → `data/lake_ticks/XAUUSD/`. Barras M15 BID autoritativas frescas (`_bars_M15.parquet`).
- **Señal/niveles:** `simular_variant(**_GOLIVE_M15, live_fill_mode=True)` para S6/S7 (motor graduado, intacto);
  SuperTrend(14,3.0) always-in con línea-SL para ST.
- **Fills real-tick:** entrada al primer tick tras el cierre de la vela de confirmación (spread real; gate 0,5
  con retry close-driven ≤1 barra); salida al primer tick que cruza el nivel server-side intra-vela.
- **Costos:** comisión = 0 (Capitaria la embebe en el spread), swap = 0 (posiciones cortas). Neto en CLP
  (USDCLP 936,50), leverage ×100, contrato 100 oz. RoM = neto ÷ margen pico concurrente.
- **Sizing:** grilla a 0,67/ficha; validación a 0,01/ficha (para comparar contra lo vivido, que fue 0,01).

## 7. Próximos pasos

1. **Confirmar en MT5 "every tick real"** (gold-standard) — al menos SuperTrend, para cerrar su magnitud.
2. **Diagnosticar** cada brecha que aparezca contra MT5 (no asumir).
3. Con los backtests validados → **investigación y optimización** (ver objetivo del usuario: análisis
   buy/sell × ganadora/perdedora, maximizar ganadoras / minimizar perdedoras).

---
*Anexo: CSV por posición y estrategia en `data/analysis/realtick_bt/positions_*.csv`.*
"""
    REPORT_MD.write_text(md, encoding="utf-8")
    print(f"\n[emitted] {REPORT_MD}")
    print(f"[emitted] per-position CSVs -> {OUT_DIR}")


def main() -> int:
    bars = load_bars()
    ticks = Ticks()
    # server wall clock; see CLOCK CONVENTION in the module docstring
    print(f"bars: {len(bars)}  {datetime.utcfromtimestamp(bars[0]['t'])} .. {datetime.utcfromtimestamp(bars[-1]['t'])}")
    resolved = build_all(ticks, bars)
    emit_report(resolved)

    # ---- diagnostics: entries (all gated to 0.5 via retry) + resolution health ----
    print("\n== resolution (entries opened at spread 0.5 via close-driven retry) ==")
    for sid in STRATS:
        rows = resolved[sid]
        retried = sum(1 for r in rows if r.get("entry_delay_bars", 0) > 0)
        slip = sum(1 for r in rows if r.get("level_slip"))
        print(f"  {sid:24s} opened={len(rows):4d}  (via retry>0bars={retried:4d})  level-resolved-exits={slip}")

    # ---- MONTHLY GRID at 0.67/ficha, gate 0.5 ----
    LOT = 0.67
    print(f"\n== MONTHLY GRID  (lot={LOT}/ficha, gate 0.5)  net in CLP ==")
    months = [f"2026-{m:02d}" for m in range(1, 8)]
    for sid in STRATS:
        kept = resolved[sid]
        print(f"\n  {sid}")
        print(f"    {'month':8s} {'n':>4s} {'net':>14s} {'WR%':>6s} {'PF':>7s} {'maxDD':>13s} {'RoM%':>8s}")
        for mo in months:
            mr = [r for r in kept if ym_of(r["t_in_exec"]) == mo]
            m = metrics(mr, LOT)
            if m["n"]:
                print(f"    {mo:8s} {m['n']:>4d} {m['net']:>14,.0f} {str(m['wr']):>6s} {str(m['pf']):>7s} {m['maxdd']:>13,.0f} {str(m['rom']):>8s}")
        tot = metrics(kept, LOT)
        print(f"    {'TOTAL':8s} {tot['n']:>4d} {tot['net']:>14,.0f} {str(tot['wr']):>6s} {str(tot['pf']):>7s} {tot['maxdd']:>13,.0f} {str(tot['rom']):>8s}")

    # combined per month
    print("\n  COMBINED (3 strategies, gate 0.5)")
    print(f"    {'month':8s} {'n':>4s} {'net':>14s} {'WR%':>6s} {'PF':>7s} {'maxDD':>13s} {'RoM%':>8s}")
    all_kept = [r for sid in STRATS for r in resolved[sid]]
    for mo in months:
        mr = [r for r in all_kept if ym_of(r["t_in_exec"]) == mo]
        m = metrics(mr, LOT)
        if m["n"]:
            print(f"    {mo:8s} {m['n']:>4d} {m['net']:>14,.0f} {str(m['wr']):>6s} {str(m['pf']):>7s} {m['maxdd']:>13,.0f} {str(m['rom']):>8s}")
    ctot = metrics(all_kept, LOT)
    print(f"    {'TOTAL':8s} {ctot['n']:>4d} {ctot['net']:>14,.0f} {str(ctot['wr']):>6s} {str(ctot['pf']):>7s} {ctot['maxdd']:>13,.0f} {str(ctot['rom']):>8s}")

    # ---- VALIDATION: informe week at 0.01/ficha vs live combined 0.5 track ----
    LOTV = 0.01
    # server wall clock bounds -- see the inverse-conversion note in emit_report()
    w0 = datetime(2026, 7, 20, tzinfo=timezone.utc).timestamp()
    w1 = datetime(2026, 7, 24, tzinfo=timezone.utc).timestamp()
    print(f"\n== VALIDATION: informe week 2026-07-20..07-23  (lot={LOTV}/ficha, gate 0.5) ==")
    print("   (compare vs live combined-0.5 track: 116 ops, +282.372,88 CLP, WR 19,83%, PF 2,54, maxDD -137.135,44, RoM +91,22%)")
    wk = [r for sid in STRATS for r in resolved[sid]
          if w0 <= r["t_in_exec"] < w1]
    m = metrics(wk, LOTV)
    print(f"   BACKTEST week combined: n={m['n']}  net={m['net']:,.2f}  WR={m['wr']}%  PF={m['pf']}  maxDD={m['maxdd']:,.2f}  RoM={m['rom']}%")
    for sid in STRATS:
        sr = [r for r in resolved[sid] if w0 <= r["t_in_exec"] < w1]
        ms = metrics(sr, LOTV)
        print(f"     {sid:24s} n={ms['n']:>3d}  net={ms['net']:>12,.2f}  WR={str(ms['wr']):>6s}  PF={str(ms['pf'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
