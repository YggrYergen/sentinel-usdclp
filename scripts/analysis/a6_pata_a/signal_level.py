r"""A6 Pata A -- paridad de entradas a NIVEL DE SEÑAL (barra M15), no de posición.

Por qué. La medición previa comparó 1 señal del motor contra ~1.7 posiciones
reales (S6: 84 posiciones -> 49 barras M15 distintas; ST: 68 -> 42), porque
las 27 barras multi-posición son re-entradas/escalado intra-barra de UNA
sola señal (dirección mixta = 0 en todas ellas). Ese denominador imponía un
techo estructural al recall. Este script recalcula todo al nivel correcto:
barra-señal (epoch M15 + dirección), reutilizando el harness validado de
`scripts/analysis/realtick_bt/backtest.py` (Ticks, run_supertrend, resolve,
run_ladder) y `sentinel_engine.strategies.emasar_variant.simular_variant`
vía la config viva `live_configs_20._GOLIVE_M15` (S6-K2P0 magic 724010,
SuperTrend-p14x3-M15 magic 724070).

Ventana: 2026-07-27 18:53:30 .. 2026-08-11 01:15:04 (hora de servidor).

CLOCK CONVENTION (idéntica a backtest.py): todo epoch de barras/ticks del
repo YA codifica el reloj de SERVIDOR (UTC-4). Se decodifica SIEMPRE con
datetime.utcfromtimestamp() y se codifica con calendar.timegm() (nunca
.timestamp()/.fromtimestamp(), que reaplicarían el offset local del host).

Salida: data/analysis/a6_pata_a/a6_pata_a_signal_level.json -- incluye,
por estrategia y por pata, la lista completa de barras-señal reales y de
motor (epoch + dirección) y la lista de emparejamientos, para que se pueda
auditar sin re-ejecutar.
"""
from __future__ import annotations

import calendar
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(r"D:\FOREX")
sys.path.insert(0, str(ROOT))

from scripts.analysis.realtick_bt.backtest import (  # noqa: E402
    Ticks, run_ladder, run_supertrend, resolve, _GL,
)

BAR_SEC = 900
POS_CSV = ROOT / "data" / "analysis" / "2883016902" / "2883016902_positions.csv"
CAPITARIA_BARS = ROOT / "data" / "lake_bars_capitaria" / "XAUUSD_M15.parquet"
AVA_BARS = ROOT / "data" / "lake_bars_ava" / "GOLD_M15.parquet"
AVA_TICKDIR = ROOT / "data" / "lake_ticks_ava" / "GOLD"
OUT_JSON = ROOT / "data" / "analysis" / "a6_pata_a" / "a6_pata_a_signal_level.json"

WINDOW_START = "2026-07-27 18:53:30"
WINDOW_END = "2026-08-11 01:15:04"

STRATS = ["S6-K2P0", "SuperTrend-p14x3-M15"]


def to_epoch(s: str) -> float:
    """Server-wall-clock string -> epoch, WITHOUT reapplying host-local offset."""
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    return float(calendar.timegm(dt.timetuple()))


WIN0 = to_epoch(WINDOW_START)
WIN1 = to_epoch(WINDOW_END)


def fmt(t: float) -> str:
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- AVA ticks
class TicksAva:
    """Same logic as backtest.Ticks but pointed at the AVA tick lake."""
    def __init__(self, *, tolerance_s: float = 60.0) -> None:
        self._m: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        # T0.7-M-F: mirrors bt.Ticks.tolerance_s (T0.7-M-E, backtest.py) --
        # same default, same semantics, so the AVA side of the feed
        # comparison is bounded identically to the Capitaria side (Ticks()
        # at signal_level.py:298). Keyword-with-default: TicksAva() at
        # signal_level.py:299 calls with no arguments and must not break.
        self.tolerance_s = tolerance_s

    def _load(self, ym: str):
        if ym not in self._m:
            p = AVA_TICKDIR / f"{ym}.parquet"
            if not p.exists():
                self._m[ym] = (np.array([]), np.array([]), np.array([]))
            else:
                df = pd.read_parquet(p)
                self._m[ym] = (df.t_msc.to_numpy() / 1000.0,
                               df.bid.to_numpy(), df.ask.to_numpy())
        return self._m[ym]

    @staticmethod
    def _ym(t_sec: float) -> str:
        d = datetime.utcfromtimestamp(t_sec)
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
        ym = self._ym(t_sec)
        return [self._shift(ym, -1), ym, self._shift(ym, 1)]

    def range(self, t0: float, t1: float):
        yms = self._candidates(t0)
        ym1 = self._ym(t1)
        if ym1 not in yms:
            yms.append(ym1)
        ts, bs, as_ = [], [], []
        for ym in yms:
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

    def first_at(self, t_sec: float):
        """First tick with t >= t_sec (spills across month files as needed),
        bounded by `self.tolerance_s` (T0.7-M-F, mirrors bt.Ticks.first_at
        T0.7-M-E): if that tick's timestamp is more than `tolerance_s` after
        `t_sec`, returns `None`, exactly as it already does when there is no
        later tick at all."""
        for ym in self._candidates(t_sec):
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


# --------------------------------------------------------------------------- bars
def load_bars(path: Path) -> list[dict[str, Any]]:
    df = pd.read_parquet(path)
    return [{"t": int(r.t), "open": float(r.o), "high": float(r.h),
              "low": float(r.l), "close": float(r.c), "volume": int(r.v)}
             for r in df.itertuples()]


# --------------------------------------------------------------------------- real signals (ground truth)
def load_real_signals() -> dict[str, list[dict[str, Any]]]:
    df = pd.read_csv(POS_CSV)
    df["epoch"] = df["open_srv"].map(to_epoch)
    df = df[(df["epoch"] >= WIN0) & (df["epoch"] <= WIN1)].copy()
    df["bucket"] = (df["epoch"] // BAR_SEC * BAR_SEC).astype(int)
    df["dir"] = df["side"].map({"BUY": "L", "SELL": "S"})

    out: dict[str, list[dict[str, Any]]] = {}
    for strat in STRATS:
        sub = df[df["strategy"] == strat]
        g = sub.groupby(["bucket", "dir"])
        n_pos_per_bar = g.size()
        mixed = 0
        sigs = []
        for (bucket, d), cnt in n_pos_per_bar.items():
            sigs.append({"t": int(bucket), "dir": d, "n_positions": int(cnt)})
        # sanity: any bucket with >1 direction? (should be 0 per user's brief)
        dirs_per_bucket = sub.groupby("bucket")["dir"].nunique()
        mixed = int((dirs_per_bucket > 1).sum())
        sigs.sort(key=lambda x: x["t"])
        out[strat] = {"signals": sigs, "n_positions_total": int(len(sub)),
                       "n_signal_bars": len(sigs), "mixed_direction_bars": mixed}
    return out


# --------------------------------------------------------------------------- motor signals
def s6_signals_capitaria(bars: list[dict[str, Any]], ticks: Ticks, gated: bool) -> list[dict[str, Any]]:
    """gated=True: motor "t" is the FILL bucket (t_in_exec from resolve(), i.e. the
    close-driven-retry spread=0.5 fill), matching what open_srv means for the real
    positions (also a fill timestamp, not the raw signal bar). "t_signal" (raw ENTRY
    bar, pre-retry) is kept alongside for audit. gated=False: no fill concept exists
    (no gate applied), so "t" IS the raw entry bar (t == t_signal).
    """
    raw = run_ladder(_GL["S6-K2P0"], bars)  # 1 row per (entry, ficha-exit); shares t_in per entry
    bar_times = np.array([b["t"] for b in bars], dtype="float64")
    best: dict[tuple[int, str], dict[str, Any]] = {}
    for p in raw:
        key = (int(p["t_in"]), p["side_l"])
        if gated:
            r = resolve(p, ticks, bar_times)
            if r is None:
                continue
            cand = {"t": int(round(r["t_in_exec"])), "dir": p["side_l"], "t_signal": int(p["t_in"])}
            # keep the earliest fill among fichas of the same entry signal
            if key not in best or cand["t"] < best[key]["t"]:
                best[key] = cand
        else:
            best.setdefault(key, {"t": int(p["t_in"]), "dir": p["side_l"], "t_signal": int(p["t_in"])})
    sigs = [v for v in best.values() if WIN0 <= v["t"] <= WIN1]
    sigs.sort(key=lambda x: x["t"])
    return sigs


def s6_signals_ava(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = run_ladder(_GL["S6-K2P0"], bars)
    seen: dict[tuple[int, str], dict[str, Any]] = {}
    for p in raw:
        key = (int(p["t_in"]), p["side_l"])
        seen.setdefault(key, {"t": int(p["t_in"]), "dir": p["side_l"], "t_signal": int(p["t_in"])})
    sigs = [v for v in seen.values() if WIN0 <= v["t"] <= WIN1]
    sigs.sort(key=lambda x: x["t"])
    return sigs


def st_signals(bars: list[dict[str, Any]], ticks, gated: bool) -> list[dict[str, Any]]:
    """Same t/t_signal convention as s6_signals_capitaria (see docstring there)."""
    raw = run_supertrend(bars, ticks)  # 1 row per leg already (always-in, ficha F1 only)
    bar_times = np.array([b["t"] for b in bars], dtype="float64")
    sigs = []
    for p in raw:
        t_in = int(p["t_in"]); d = p["side_l"]
        if gated:
            r = resolve(p, ticks, bar_times)
            if r is None:
                continue
            t_match = int(round(r["t_in_exec"]))
        else:
            t_match = t_in
        if not (WIN0 <= t_match <= WIN1):
            continue
        sigs.append({"t": t_match, "dir": d, "t_signal": t_in})
    # dedupe (defensive; keeps earliest if duplicates)
    uniq: dict[tuple[int, str], dict[str, Any]] = {}
    for s in sigs:
        key = (s["t"], s["dir"])
        if key not in uniq:
            uniq[key] = s
    out = list(uniq.values())
    out.sort(key=lambda x: x["t"])
    return out


# --------------------------------------------------------------------------- matching
def match_signals(real: list[dict[str, Any]], motor: list[dict[str, Any]], tol_bars: int):
    """Greedy nearest-offset, one-to-one, same-direction match within tol_bars*900s."""
    remaining = list(range(len(motor)))
    pairs = []
    unmatched_real = []
    for i, rs in enumerate(sorted(range(len(real)), key=lambda k: real[k]["t"])):
        r = real[rs]
        cands = [j for j in remaining if motor[j]["dir"] == r["dir"]
                 and abs(motor[j]["t"] - r["t"]) <= tol_bars * BAR_SEC]
        if not cands:
            unmatched_real.append(rs)
            continue
        j = min(cands, key=lambda j: abs(motor[j]["t"] - r["t"]))
        offset_bars = (motor[j]["t"] - r["t"]) / BAR_SEC
        pairs.append({"real_t": r["t"], "real_dir": r["dir"],
                      "motor_t": motor[j]["t"], "motor_dir": motor[j]["dir"],
                      "offset_bars": offset_bars})
        remaining.remove(j)
    matched_motor_idx = {p["motor_t"] for p in pairs}  # note: (t) alone ok, dedupe by t+dir below
    matched_motor_keys = {(p["motor_t"], p["motor_dir"]) for p in pairs}
    unmatched_motor = [motor[j] for j in range(len(motor))
                        if (motor[j]["t"], motor[j]["dir"]) not in matched_motor_keys]
    n_real = len(real); n_motor = len(motor); n_matched = len(pairs)
    recall = round(100.0 * n_matched / n_real, 2) if n_real else None
    precision = round(100.0 * n_matched / n_motor, 2) if n_motor else None
    return {
        "tol_bars": tol_bars, "n_real": n_real, "n_motor": n_motor, "n_matched": n_matched,
        "recall_pct": recall, "precision_pct": precision,
        "pairs": pairs,
        "unmatched_real": [{"t": real[i]["t"], "dir": real[i]["dir"]} for i in unmatched_real],
        "unmatched_motor": unmatched_motor,
    }


def summarize_leg(real_sigs: list[dict[str, Any]], motor_sigs: list[dict[str, Any]], label: str):
    return {
        "label": label,
        "n_real": len(real_sigs),
        "n_motor": len(motor_sigs),
        "real_signals": real_sigs,
        "motor_signals": motor_sigs,
        "match_tol0": match_signals(real_sigs, motor_sigs, 0),
        "match_tol1": match_signals(real_sigs, motor_sigs, 1),
        "match_tol2_labeled": match_signals(real_sigs, motor_sigs, 2),
    }


def main() -> int:
    print(f"window: {WINDOW_START} .. {WINDOW_END}  epoch [{WIN0},{WIN1}]")
    real = load_real_signals()
    for strat in STRATS:
        r = real[strat]
        print(f"  REAL {strat}: {r['n_positions_total']} posiciones -> {r['n_signal_bars']} barras-señal "
              f"(mixed_direction_bars={r['mixed_direction_bars']})")

    cap_bars = load_bars(CAPITARIA_BARS)
    ava_bars_full = load_bars(AVA_BARS)
    print(f"capitaria bars: {len(cap_bars)}  {fmt(cap_bars[0]['t'])} .. {fmt(cap_bars[-1]['t'])}")
    print(f"ava bars (full): {len(ava_bars_full)}  {fmt(ava_bars_full[0]['t'])} .. {fmt(ava_bars_full[-1]['t'])}")

    cap_ticks = Ticks()
    ava_ticks = TicksAva()

    # AVA ST needs tick-informed intrabar line-touch mechanics; restrict to the
    # tick-covered span (2026-02 onward) so early untouched bars don't silently
    # fall back to close-only flip logic. S6 signal generation (bars-only, no
    # ticks) keeps the FULL ava_bars history for indicator warm-up.
    ava_tick_start = to_epoch("2026-02-01 00:00:00")
    ava_bars_st = [b for b in ava_bars_full if b["t"] >= ava_tick_start]
    print(f"ava bars (ST, tick-covered): {len(ava_bars_st)}  {fmt(ava_bars_st[0]['t'])} .. {fmt(ava_bars_st[-1]['t'])}")

    result: dict[str, Any] = {
        "window": {"start": WINDOW_START, "end": WINDOW_END, "epoch": [WIN0, WIN1]},
        "unit": "barra-señal M15 (epoch open + dirección), NO posición",
        "real_ground_truth": real,
        "legs": {},
        "limitaciones_conocidas": [
            "Servidor de barras = Capitaria-All; cuenta 2883016902 opera en Capitaria Latam Spa "
            "(servidores hermanos, no el mismo).",
            "El ejecutor real usa gate de spread ADAPTATIVO (running-min, run_live_20.py:159,1105-1109); "
            "el harness usa un gate FIJO 0.5 (resolve()), no lo replica.",
            "En vivo solo se observó la ficha F1 (magics 724011/724071); F2/F3 nunca se vieron.",
        ],
    }

    # ---- S6-K2P0 ----
    s6_real = real["S6-K2P0"]["signals"]
    s6_cap_gated = s6_signals_capitaria(cap_bars, cap_ticks, gated=True)
    s6_cap_raw = s6_signals_capitaria(cap_bars, cap_ticks, gated=False)
    s6_ava_raw = s6_signals_ava(ava_bars_full)
    result["legs"]["S6-K2P0"] = {
        "1_capitaria_gated": summarize_leg(s6_real, s6_cap_gated, "Capitaria + gate spread harness vs real"),
        "2_capitaria_ungated": summarize_leg(s6_real, s6_cap_raw, "Capitaria señal cruda (sin gate) vs real"),
        "3_ava_ungated": summarize_leg(s6_real, s6_ava_raw, "AVA señal cruda (sin gate) vs real"),
        "capitaria_vs_ava_ungated": summarize_leg(s6_cap_raw, s6_ava_raw, "Capitaria cruda vs AVA cruda (motor-motor)"),
    }

    # ---- SuperTrend ----
    st_real = real["SuperTrend-p14x3-M15"]["signals"]
    st_cap_gated = st_signals(cap_bars, cap_ticks, gated=True)
    st_cap_raw = st_signals(cap_bars, cap_ticks, gated=False)
    st_ava_raw = st_signals(ava_bars_st, ava_ticks, gated=False)
    result["legs"]["SuperTrend-p14x3-M15"] = {
        "1_capitaria_gated": summarize_leg(st_real, st_cap_gated, "Capitaria + gate spread harness vs real"),
        "2_capitaria_ungated": summarize_leg(st_real, st_cap_raw, "Capitaria señal cruda (sin gate) vs real"),
        "3_ava_ungated": summarize_leg(st_real, st_ava_raw, "AVA señal cruda (sin gate) vs real"),
        "capitaria_vs_ava_ungated": summarize_leg(st_cap_raw, st_ava_raw, "Capitaria cruda vs AVA cruda (motor-motor)"),
    }

    # ---- interpretive check: are the gated-24 (or whatever count) a clean subset of the 49/42? ----
    for strat, gated_sigs, real_sigs in [
        ("S6-K2P0", s6_cap_gated, s6_real),
        ("SuperTrend-p14x3-M15", st_cap_gated, st_real),
    ]:
        m0 = match_signals(real_sigs, gated_sigs, 0)
        m1 = match_signals(real_sigs, gated_sigs, 1)
        result["legs"][strat]["subset_check_gated_vs_real"] = {
            "n_gated_motor": len(gated_sigs),
            "n_real": len(real_sigs),
            "tol0_matched": m0["n_matched"], "tol0_unmatched_motor": len(m0["unmatched_motor"]),
            "tol1_matched": m1["n_matched"], "tol1_unmatched_motor": len(m1["unmatched_motor"]),
            "clean_subset_tol0": len(m0["unmatched_motor"]) == 0,
            "clean_subset_tol1": len(m1["unmatched_motor"]) == 0,
        }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {OUT_JSON}")

    # ---- console summary table ----
    print("\n== RESUMEN (barra-señal) ==")
    for strat in STRATS:
        print(f"\n-- {strat} --")
        for legname in ["1_capitaria_gated", "2_capitaria_ungated", "3_ava_ungated"]:
            leg = result["legs"][strat][legname]
            t0 = leg["match_tol0"]; t1 = leg["match_tol1"]
            print(f"  {legname:24s} n_real={leg['n_real']:3d} n_motor={leg['n_motor']:3d}  "
                  f"tol0: matched={t0['n_matched']:3d} recall={t0['recall_pct']:>6}% prec={t0['precision_pct']:>6}%  "
                  f"tol1: matched={t1['n_matched']:3d} recall={t1['recall_pct']:>6}% prec={t1['precision_pct']:>6}%")
        cva = result["legs"][strat]["capitaria_vs_ava_ungated"]
        t0 = cva["match_tol0"]; t1 = cva["match_tol1"]
        print(f"  {'capitaria_vs_ava':24s} n_cap={cva['n_real']:3d} n_ava={cva['n_motor']:3d}  "
              f"tol0: matched={t0['n_matched']:3d}  tol1: matched={t1['n_matched']:3d}")
        sc = result["legs"][strat]["subset_check_gated_vs_real"]
        print(f"  subset-check: gated({sc['n_gated_motor']}) clean subset of real({sc['n_real']})? "
              f"tol0={sc['clean_subset_tol0']} (unmatched_motor={sc['tol0_unmatched_motor']})  "
              f"tol1={sc['clean_subset_tol1']} (unmatched_motor={sc['tol1_unmatched_motor']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
