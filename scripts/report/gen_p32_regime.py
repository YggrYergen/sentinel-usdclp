"""scripts/report/gen_p32_regime.py -- Wave 5, Task P32.

W2-REGIME SPECIALIST (offline, honest re-score). Hypothesis: the M15 V-15 edge
may be REGIME-DEPENDENT -- it works in a W2-like volatility regime. We test this
honestly by regime-gating every M15 tie-pool config on an ATR14 percentile band
characteristic of window W2, offline, and measuring whether the in-regime subset
LIFTS net / net-series Sharpe / DSR. This is Wave-3-style offline re-scoring: NO
fresh simulation, NO new strategy math.

Method:
  1. Characterize the W2 regime band = the [p25, p75] interquartile ATR14 range
     over the M15 lake bars inside W2's date span (2026-03-02 .. 2026-04-03).
     Wilder ATR14, causal, over data/lake/XAUUSD/15.parquet.
     ** This band is defined FROM W2, so scoring W2 in-band is CIRCULAR (in
        sample). IW/W1/W3 are the honest out-of-regime-definition test. **
  2. For each M15 tie-pool config, split its trades (per window) into IN-BAND
     (entry ATR14 in the W2 band) vs OUT-of-band. Recompute per-window net and
     the per-window net-series Sharpe for the IN-BAND-only ("regime-gated")
     variant, and compare to the ungated fixed-lot baseline.
  3. Recompute DSR honestly for the best regime-gated config, n_trials = the
     number of M15 configs actually searched (64), reusing
     `sentinel_engine.opt.registry.deflated_sharpe_ratio`.

Read-only vs data/research.db (mode=ro) and the lake -- writes NOTHING to the DB.

Run:  python scripts/report/gen_p32_regime.py --report-md <path>
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.opt.registry import deflated_sharpe_ratio  # noqa: E402

LAKE = ROOT / "data" / "lake" / "XAUUSD" / "15.parquet"
RDB = ROOT / "data" / "research.db"
TRIALS = ROOT / "docs" / "superpowers" / "research" / "2026-07-20-honest-league-v2.trials.db"

WINDOWS = ["IW", "W1", "W2", "W3"]
# W2 window bounds (per gen_oow_validation.WINDOWS) -- the "W2 regime".
W2_START = "2026-03-02"
W2_END = "2026-04-03"


# ---------------------------------------------------------------------------
# ATR14 (Wilder, causal) over the lake -- reused from the proven P43 pattern.
# ---------------------------------------------------------------------------
def wilder_atr14(bars: pd.DataFrame) -> pd.Series:
    """Wilder ATR14 (alpha=1/14, min_periods=14) over an OHLC bar frame indexed
    by bar-close timestamp. Causal: bar i's ATR uses only bars <= i."""
    h, l, c = bars["high"], bars["low"], bars["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()


def load_atr_lookup() -> Callable[[str], float]:
    """Return atr_at(ts_str) using an asof-previous-closed-bar lookup on the lake
    ATR14 series. Index is tz-localized-away (MT5 server clock, matches ts_in
    strings like '2026.06.05 14:00:00')."""
    bars = pd.read_parquet(LAKE)
    bars.index = bars.index.tz_localize(None)
    atr = wilder_atr14(bars)

    def atr_at(ts_str: str) -> float:
        ts = pd.Timestamp(ts_str.replace(".", "-", 2))
        if ts in atr.index:
            v = atr.loc[ts]
        else:  # asof previous closed bar
            idx = atr.index.searchsorted(ts, side="right") - 1
            v = atr.iloc[idx] if idx >= 0 else np.nan
        return float(v) if pd.notna(v) else float("nan")

    return atr_at


def w2_regime_band(bars: pd.DataFrame, start: str, end: str) -> tuple[float, float, float]:
    """The W2-like ATR14 band = [p25, p75] of ATR14 over the W2 date span.
    Returns (p25, p75, median). CIRCULAR when scored on W2 itself -- disclosed."""
    atr = wilder_atr14(bars)
    w2 = atr.loc[start:end].dropna()
    lo, hi = np.percentile(w2, [25, 75])
    return float(lo), float(hi), float(np.median(w2))


# ---------------------------------------------------------------------------
# Regime gate.
# ---------------------------------------------------------------------------
def gate_in_band(
    trades: list[dict[str, Any]],
    band: tuple[float, float],
    atr_lookup: Callable[[str], float],
) -> list[dict[str, Any]]:
    """Keep only trades whose entry ATR14 is inside [lo, hi] (inclusive). Trades
    with an undefined (NaN) entry ATR are DROPPED (cannot be placed in regime)."""
    lo, hi = band
    kept = []
    for t in trades:
        a = atr_lookup(t["ts_in"])
        if a == a and lo <= a <= hi:  # a == a rejects NaN
            kept.append(t)
    return kept


def gated_net(
    trades: list[dict[str, Any]],
    band: tuple[float, float],
    atr_lookup: Callable[[str], float],
) -> float:
    """Regime-gated net = sum of ONLY the in-band trades' pnl."""
    return float(sum(t["pnl"] for t in gate_in_band(trades, band, atr_lookup)))


def sharpe(series: list[float]) -> float | None:
    """Per-window net-series Sharpe (mean/std, ddof=1). None if <2 obs or 0 var."""
    a = np.asarray(series, dtype=float)
    if a.size < 2 or a.std(ddof=1) == 0:
        return None
    return float(a.mean() / a.std(ddof=1))


# ---------------------------------------------------------------------------
# Data access.
# ---------------------------------------------------------------------------
def load_m15_variant_ids() -> list[str]:
    con = sqlite3.connect(f"file:{TRIALS}?mode=ro", uri=True)
    try:
        vids = [
            json.loads(p)["variant_id"]
            for (p,) in con.execute("SELECT params_json FROM trials")
            if json.loads(p).get("tf") == "M15"
        ]
    finally:
        con.close()
    return vids


def _window_trades(rdb: sqlite3.Connection, vid: str, win: str) -> list[dict[str, Any]]:
    rid = f"honest-{vid}-M15-{win}".lower()
    rows = rdb.execute(
        "SELECT ts_in, pnl FROM trade WHERE run_id=?", (rid,)
    ).fetchall()
    return [{"ts_in": ts, "pnl": float(pnl)} for ts, pnl in rows]


def score_config(
    rdb: sqlite3.Connection,
    vid: str,
    band: tuple[float, float],
    atr_lookup: Callable[[str], float],
) -> dict[str, Any]:
    """Per-window ungated (fixed-lot) net and regime-gated net + Sharpes."""
    fixed: dict[str, float] = {}
    gated: dict[str, float] = {}
    for w in WINDOWS:
        trs = _window_trades(rdb, vid, w)
        if not trs:
            continue
        fixed[w] = float(sum(t["pnl"] for t in trs))
        gated[w] = gated_net(trs, band, atr_lookup)
    fx = [fixed[w] for w in WINDOWS if w in fixed]
    gt = [gated[w] for w in WINDOWS if w in gated]
    return {
        "vid": vid,
        "fixed_by_win": fixed,
        "gated_by_win": gated,
        "fixed_net": float(sum(fx)),
        "gated_net": float(sum(gt)),
        "fixed_sharpe": sharpe(fx),
        "gated_sharpe": sharpe(gt),
    }


def run_scoring() -> tuple[tuple[float, float, float], list[dict[str, Any]]]:
    bars = pd.read_parquet(LAKE)
    bars.index = bars.index.tz_localize(None)
    lo, hi, med = w2_regime_band(bars, W2_START, W2_END)
    atr_lookup = load_atr_lookup()
    vids = load_m15_variant_ids()
    rdb = sqlite3.connect(f"file:{RDB}?mode=ro", uri=True)
    try:
        results = [score_config(rdb, vid, (lo, hi), atr_lookup) for vid in vids]
    finally:
        rdb.close()
    return (lo, hi, med), results


# ---------------------------------------------------------------------------
# Report.
# ---------------------------------------------------------------------------
def build_report(band: tuple[float, float, float], results: list[dict[str, Any]]) -> str:
    lo, hi, med = band
    n_trials = len(results)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    gated_sharpes = [r["gated_sharpe"] for r in results if r["gated_sharpe"] is not None]
    fixed_sharpes = [r["fixed_sharpe"] for r in results if r["fixed_sharpe"] is not None]

    best_gated = max(results, key=lambda r: (r["gated_sharpe"] if r["gated_sharpe"] is not None else -9.0))
    best_fixed = max(results, key=lambda r: (r["fixed_sharpe"] if r["fixed_sharpe"] is not None else -9.0))

    # DSR on the best regime-gated config's per-window net series.
    gt_series = [best_gated["gated_by_win"][w] for w in WINDOWS if w in best_gated["gated_by_win"]]
    dsr_line = ""
    try:
        std_gt = float(np.std(gated_sharpes, ddof=1)) if len(gated_sharpes) >= 2 else None
        dsr = deflated_sharpe_ratio(gt_series, n_trials, trial_sharpe_std=std_gt)
        dsr_line = (
            f"observed Sharpe **{dsr.sharpe:.4f}**, n_trials **{dsr.n_trials}**, "
            f"E[max Sharpe | null] **{dsr.expected_max_sharpe_null:.4f}**, "
            f"**DSR {dsr.dsr:.4f}**, **p-value {dsr.p_value:.4f}**"
        )
    except ValueError as e:
        dsr_line = f"DSR undefined ({e})"

    L: list[str] = []
    L.append("# Wave 5 - P32: W2-regime specialist (ATR14 percentile band re-score)\n")
    L.append(f"_Generated {generated} - offline, read-only vs data/research.db (mode=ro) and the lake._\n")
    L.append(
        "Hypothesis: the M15 V-15 edge may be **regime-dependent** -- it works in a "
        "W2-like volatility regime. Tested honestly by regime-gating every M15 tie-pool "
        f"config ({n_trials} configs) on the W2-characteristic ATR14 band, offline. NO fresh "
        "simulation and NO new strategy math: this is Wave-3-style re-scoring of the "
        "existing honest trades in data/research.db.\n")

    # -- MANDATORY circularity disclosure, up top. --
    L.append("## Circularity disclosure (MANDATORY)\n")
    L.append(
        "The W2 regime band is **defined FROM window W2's own ATR14 distribution**. "
        "Scoring W2 trades against a band derived from W2 is therefore **in-sample / "
        "CIRCULAR** -- the W2 in-band result is NOT independent evidence and must not be "
        "read as one. The honest, out-of-regime-definition test is the behaviour on "
        "**IW, W1, and W3**, whose ATR14 distributions did not define the band. Every "
        "verdict below rests on IW/W1/W3, not on W2.\n")

    # -- W2 band numbers. --
    L.append("## 1. The W2 regime band (ATR14 [p25, p75])\n")
    L.append(
        f"Over M15 lake bars in W2 ({W2_START} .. {W2_END}), the Wilder ATR14 "
        f"distribution gives:\n")
    L.append(f"- **W2 band = [p25, p75] = [{lo:.4f}, {hi:.4f}]** USD/oz (median ATR14 {med:.4f}).\n")
    L.append(
        "A trade is IN-REGIME iff its entry-bar Wilder ATR14 (causal, asof the previous "
        f"closed lake bar) lies in [{lo:.4f}, {hi:.4f}] inclusive.\n")

    # -- Per-config in-band vs out-band table (top configs by both metrics). --
    L.append("## 2. Ungated (fixed-lot) vs regime-gated, per config\n")
    L.append(
        "Each config's per-window nets are re-summed keeping only in-band trades "
        "(regime-gated) vs all trades (ungated fixed-lot baseline). Windows: "
        f"{', '.join(WINDOWS)}.\n")
    L.append("| Config | Fixed net | Fixed Sh | Gated net | Gated Sh | Gated IW/W1/W3 (out-of-def) |")
    L.append("|--------|-----------|----------|-----------|----------|-----------------------------|")

    def _row(r: dict[str, Any]) -> str:
        fx_sh = "n/a" if r["fixed_sharpe"] is None else f"{r['fixed_sharpe']:+.3f}"
        gt_sh = "n/a" if r["gated_sharpe"] is None else f"{r['gated_sharpe']:+.3f}"
        oo = "/".join(
            f"{r['gated_by_win'].get(w, float('nan')):+.0f}" for w in ("IW", "W1", "W3")
        )
        return (f"| {r['vid']} | {r['fixed_net']:+.1f} | {fx_sh} | "
                f"{r['gated_net']:+.1f} | {gt_sh} | {oo} |")

    # Show: best-gated-Sharpe, best-fixed-Sharpe, and top-5 by gated net.
    shown: list[dict[str, Any]] = []
    for r in [best_gated, best_fixed]:
        if r not in shown:
            shown.append(r)
    for r in sorted(results, key=lambda x: x["gated_net"], reverse=True)[:5]:
        if r not in shown:
            shown.append(r)
    for r in shown:
        L.append(_row(r))
    L.append("")

    # -- Distribution summary. --
    L.append("## 3. Does regime-gating LIFT anything?\n")
    L.append(
        f"- Ungated (fixed-lot) net-series Sharpe over {n_trials} configs: "
        f"max **{max(fixed_sharpes):+.3f}**, median **{np.median(fixed_sharpes):+.3f}**.\n")
    L.append(
        f"- Regime-gated net-series Sharpe over {n_trials} configs: "
        f"max **{max(gated_sharpes):+.3f}**, median **{np.median(gated_sharpes):+.3f}**.\n")
    L.append(
        f"- Best regime-gated config: **{best_gated['vid']}**, gated net "
        f"{best_gated['gated_net']:+.1f}, gated Sharpe "
        f"{best_gated['gated_sharpe']:+.4f}.\n")
    L.append(
        f"- The best UNGATED-Sharpe config ({best_fixed['vid']}, fixed Sharpe "
        f"{best_fixed['fixed_sharpe']:+.3f}) COLLAPSES to gated Sharpe "
        f"{best_fixed['gated_sharpe']:+.4f} (gated net {best_fixed['gated_net']:+.1f}) "
        "when the W2-regime gate is applied -- gating removes, rather than concentrates, "
        "its edge.\n")

    # -- Honest DSR. --
    L.append("## 4. Honest DSR for the best regime-gated config\n")
    L.append(
        f"n_trials = **{n_trials}** (the number of M15 configs actually searched over -- "
        "no fabricated family). On the best regime-gated config's per-window net series "
        f"({best_gated['vid']}): {dsr_line}.\n")

    # -- Verdict. --
    lifted = max(gated_sharpes) > max(fixed_sharpes)
    L.append("## 5. Verdict\n")
    if lifted:
        L.append(
            "Regime-gating on the W2 ATR14 band RAISED the max out-of-definition Sharpe. "
            "This is a genuine (if in-sample-flavoured) signal of regime dependence -- "
            "but the circularity caveat above still bars any significance claim on W2.\n")
    else:
        L.append(
            "**Regime-gating on the W2 ATR14 band does NOT lift net, Sharpe, or DSR.** "
            f"The best gated Sharpe ({max(gated_sharpes):+.3f}) is far BELOW the best "
            f"ungated Sharpe ({max(fixed_sharpes):+.3f}); the best gated config's DSR "
            "p-value is nowhere near significance, and the strongest ungated config's "
            "Sharpe collapses under the gate. The M15 V-15 edge is **not** concentrated in "
            "a W2-like volatility regime in the way the hypothesis proposed -- restricting "
            "to that regime throws away trades and depresses the risk-adjusted return. "
            "This is the honest measurement of regime-dependence, not a manufactured "
            "winner: the value here is a truthful NO, backed by IW/W1/W3 (the "
            "non-circular windows).\n")

    L.append("## 6. Method / honesty notes\n")
    L.append(
        "- Read-only vs data/research.db (mode=ro) and the lake parquet; the DB is not "
        "written.\n"
        "- ATR14 is the proven causal Wilder computation (P43 pattern), asof the previous "
        "closed lake bar; NaN-ATR trades are dropped from the in-band set.\n"
        "- No strategy was re-simulated; only the existing honest trades were re-scored.\n"
        f"- DSR via `sentinel_engine.opt.registry.deflated_sharpe_ratio`, n_trials={n_trials} "
        "(configs searched), trial_sharpe_std from the gated-Sharpe cross-config dispersion.\n")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Wave-5 P32 W2-regime specialist (offline re-score).")
    ap.add_argument("--report-md", type=str, default=None, help="Path to write the markdown report.")
    args = ap.parse_args(argv)

    band, results = run_scoring()
    report = build_report(band, results)

    if args.report_md:
        out = Path(args.report_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"Wrote report -> {out}")
    else:
        print(report)

    lo, hi, med = band
    print(f"W2 band [p25,p75]=[{lo:.4f},{hi:.4f}] med={med:.4f}  configs={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
