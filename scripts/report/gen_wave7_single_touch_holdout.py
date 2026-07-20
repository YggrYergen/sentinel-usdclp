"""scripts/report/gen_wave7_single_touch_holdout.py -- Wave 7, Task W7-T1.

The program's DECISIVE out-of-sample gate: a genuine SINGLE-TOUCH HOLDOUT.

Why this is a real holdout (honesty-critical):
    The in-sample honest league (`2026-07-20-honest-league-v3.{json,md}`,
    winner `HON-W2-S6-K2P0-M15-SAR`) scored EVERY candidate on the four
    windows {IW, W1, W2, W3} and used those four as the walk-forward "folds"
    that produced the leaderboard's median-fold-J -> selection. Concretely,
    in `gen_honest_sweep._build_league`, each window's honest net becomes one
    `FoldResult.candidate_J`, and `select_winner` chooses on the median of
    those. So IW/W1/W2/W3 were ALL touched during selection -- none of them is
    a valid holdout.

    But the XAUUSD lake has many months NEVER touched by that sweep. This
    driver evaluates each finalist EXACTLY ONCE on an untouched window that no
    sweep, selection, or refit ever saw:

        HOLDOUT = 2026-01-05 -> 2026-02-06 (thru 02-05), warmup from 2025-12-29.

    It is the most-recent contiguous month that sits OUTSIDE the touched span
    (IW=Jun, W1=May, W2=Mar, W3=Oct; Feb/Apr also untouched but Jan is the
    cleanest full untouched month adjacent to the touched cluster). Single
    touch: every candidate is priced ONCE here, win-or-lose, and NOTHING is
    refit or re-selected on it.

Same honest pipeline as the league: `simular_variant(live_fill_mode=True)`,
flat $0.50/round-trip spread applied at fill, lot 0.10 -- reusing verbatim
`gen_honest_sweep._price_cell` / `._metrics` (EMASAR SAR family) and the P34
`supertrend_always_in_trades` engine (SuperTrend p14x3-M15). ZERO new
strategy/fill/pnl math.

READ-ONLY vs data/research.db and the lake -- writes only the markdown report.

Run:  python scripts/report/gen_wave7_single_touch_holdout.py --report-md <path>
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _load_module(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# The honest-sweep harness gives us the EXACT same pricing/metrics used for the
# in-sample league (live_fill + flat-0.5 + lot-0.10). We call its private
# _price_cell/_metrics so there is zero risk of a divergent cost model.
_SWEEP = _load_module("gen_honest_sweep", "scripts/report/gen_honest_sweep.py")
# P34 SuperTrend always-in engine + its cost primitives.
_P34 = _load_module("gen_p34_supertrend_honest", "scripts/report/gen_p34_supertrend_honest.py")

SYMBOL = "XAUUSD"
LAKE_ROOT = ROOT / "data" / "lake"

# --- The untouched single-touch holdout window. ---
WARMUP_START = datetime(2025, 12, 29, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_START = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_END_EXCL = datetime(2026, 2, 6, 0, 0, 0, tzinfo=timezone.utc)  # thru 02-05
LAKE_MONTHS = ("2025-12", "2026-01", "2026-02")
HOLDOUT_LABEL = "HOLDOUT-2026-01"
PERIOD_STR = "2026-01-05 .. 2026-02-05"

# The five EMASAR V-15 SAR finalists (kwargs pulled from the v3 manifest).
MANIFEST = ROOT / "scripts" / "report" / "honest_manifest_full_2026_07_20_v3.json"
SAR_FINALISTS = [
    "HON-W2-S6-K2P0-M15-SAR",
    "HON-W2-S7-TPNONE-M15-SAR",
    "HON-W2-S6-K1P5-M15-SAR",
    "HON-W2-S7-TP1P0-M15-SAR",
    "HON-W2-S7-TPNONE-M15-SAR-F2",
]


def _load_holdout_bars(tf: str) -> list[dict[str, Any]]:
    """Load XAUUSD/{tf} BID lake bars in [WARMUP_START, WINDOW_END_EXCL).
    Same shape as gen_variant_batch1._load_bars, over the holdout months."""
    warm_epoch = int(WARMUP_START.timestamp())
    end_epoch = int(WINDOW_END_EXCL.timestamp())
    bars: list[dict[str, Any]] = []
    for month in LAKE_MONTHS:
        path = LAKE_ROOT / SYMBOL / tf / f"{month}.parquet"
        if not path.exists():
            continue
        table = pq.read_table(path)
        cols = {name: table.column(name).to_pylist() for name in table.schema.names}
        for i in range(len(cols["t"])):
            t = cols["t"][i]
            if t < warm_epoch or t >= end_epoch:
                continue
            bars.append({
                "t": t, "open": cols["o"][i], "high": cols["h"][i],
                "low": cols["l"][i], "close": cols["c"][i], "volume": cols["v"][i],
            })
    bars.sort(key=lambda b: b["t"])
    return bars


def _in_window(epoch: int) -> bool:
    return int(WINDOW_START.timestamp()) <= epoch < int(WINDOW_END_EXCL.timestamp())


def _load_sar_kwargs() -> dict[str, dict[str, Any]]:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {e["variant_id"]: e for e in m["entries"]}
    out: dict[str, dict[str, Any]] = {}
    for vid in SAR_FINALISTS:
        if vid not in by_id:
            raise KeyError(f"finalist {vid!r} not in manifest")
        out[vid] = dict(by_id[vid]["kwargs"])
    return out


def _sharpe(pnls: list[float]) -> float | None:
    if len(pnls) < 2:
        return None
    sd = statistics.stdev(pnls)
    return statistics.mean(pnls) / sd if sd else None


def run_sar_holdout() -> dict[str, dict[str, Any]]:
    """Price each SAR finalist ONCE on the holdout window, honest pipeline."""
    bars = _load_holdout_bars("M15")
    kwargs_by_id = _load_sar_kwargs()
    results: dict[str, dict[str, Any]] = {}
    for vid, kwargs in kwargs_by_id.items():
        # Identical honest pricing/metrics as the in-sample league.
        trades = _SWEEP._price_cell(bars, kwargs)
        # In-window filter: entry epoch inside the (non-warmup) holdout bounds.
        in_trades = [t for t in trades if _in_window(t["ts_in_epoch"])]
        metrics = _SWEEP._metrics(in_trades)
        metrics["sharpe"] = _sharpe(metrics["per_trade_pnl"])
        results[vid] = metrics
    return results


def run_supertrend_holdout() -> dict[str, Any]:
    """SuperTrend always-in p14x3-M15 on the holdout window (P34 engine)."""
    bars = _load_holdout_bars("M15")
    trades, n_flips = _P34.supertrend_always_in_trades(
        bars, _P34.ATR_PERIOD, _P34.MULT, _in_window,
    )
    in_trades = [t for t in trades if t["entry_in_window"]]
    pnls = [_P34._pnl(t["side"], t["px_in"], t["px_out"]) for t in in_trades]
    n = len(pnls)
    net = round(sum(pnls), 2)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_loss = -sum(losses)
    pf = round(sum(wins) / gross_loss, 4) if gross_loss > 0 else None
    wr = round(100.0 * len(wins) / n, 2) if n else None
    return {
        "trades": n, "net": net, "pf": pf, "wr": wr,
        "sharpe": _sharpe(pnls), "n_flips": n_flips, "bars": len(bars),
        "per_trade_pnl": pnls,
    }


def _fmt_pf(pf: Any) -> str:
    if pf is None:
        return "n/a"
    if pf == float("inf"):
        return "inf"
    return f"{pf:.3f}"


def build_report(sar: dict[str, dict[str, Any]], st: dict[str, Any]) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    L: list[str] = []
    L.append("# Wave 7 - Single-touch holdout (decisive OOS gate)\n")
    L.append(f"_Generated {generated} -- read-only vs data/research.db + lake. "
             "Offline; no MT5, no orders._\n")

    L.append("## Holdout window (disclosure)\n")
    L.append(
        f"**Holdout = `{HOLDOUT_LABEL}`, {PERIOD_STR}** (warmup from 2025-12-29), "
        "XAUUSD M15 BID lake bars.\n")
    L.append(
        "This window is a GENUINELY UNTOUCHED slice. The in-sample honest "
        "league (`2026-07-20-honest-league-v3`) scored every candidate on the "
        "four windows {IW=2026-06-08..07-07, W1=2026-05, W2=2026-03, "
        "W3=2025-10} and used those four AS the walk-forward folds feeding "
        "`select_winner` (see `gen_honest_sweep._build_league`: each window net "
        "-> one `FoldResult.candidate_J`; the median over folds picks the "
        "winner). Therefore IW/W1/W2/W3 are ALL in-sample and none is a valid "
        "holdout. The Jan-2026 month here was NEVER loaded by any sweep, "
        "selection, or refit -- it is the most-recent full month sitting "
        "outside the touched cluster. Each finalist is priced EXACTLY ONCE on "
        "it below (single touch), win or lose, with no re-selection.\n")
    L.append(
        "Cost model is identical to the league: `simular_variant("
        "live_fill_mode=True)` for the EMASAR family (via the verbatim "
        "`gen_honest_sweep._price_cell`/`._metrics`) and the P34 always-in "
        "engine for SuperTrend; flat $0.50/round-trip spread at fill; lot "
        "0.10; XAUUSD contract $100/$1.\n")

    L.append("## Per-candidate holdout (single-touch) results\n")
    L.append("| Candidate | Trades | Net (USD) | PF | WR% | Per-trade Sharpe |")
    L.append("|---|---|---|---|---|---|")
    order = SAR_FINALISTS
    for vid in order:
        r = sar[vid]
        sh = "n/a" if r["sharpe"] is None else f"{r['sharpe']:.4f}"
        wr = "n/a" if r["wr"] is None else f"{r['wr']:.1f}"
        L.append(f"| {vid} | {r['trades']} | {r['net']:+.2f} | "
                 f"{_fmt_pf(r['pf'])} | {wr} | {sh} |")
    sh = "n/a" if st["sharpe"] is None else f"{st['sharpe']:.4f}"
    wr = "n/a" if st["wr"] is None else f"{st['wr']:.1f}"
    L.append(f"| SuperTrend-p14x3-M15 (always-in) | {st['trades']} | "
             f"{st['net']:+.2f} | {_fmt_pf(st['pf'])} | {wr} | {sh} |")
    L.append("")
    L.append(f"_SuperTrend: {st['n_flips']} flips over {st['bars']} bars "
             "(warmup incl.); position open at feed-end left open, not a "
             "trade -- P34 reference semantics._\n")

    # Verdict.
    L.append("## Honest verdict\n")
    winner_vid = "HON-W2-S6-K2P0-M15-SAR"
    win_net = sar[winner_vid]["net"]
    n_pos = sum(1 for vid in order if sar[vid]["net"] > 0)
    st_pos = st["net"] > 0
    L.append(
        f"- The in-sample WINNER, `{winner_vid}`, posts net **{win_net:+.2f} "
        f"USD** on this untouched holdout ({sar[winner_vid]['trades']} trades).\n")
    L.append(
        f"- Of the 5 EMASAR SAR finalists, **{n_pos}/5** are net-positive on "
        "the holdout. SuperTrend-p14x3-M15 is "
        f"**{'net-positive' if st_pos else 'net-NEGATIVE'}** "
        f"({st['net']:+.2f}).\n")
    L.append(
        "- **Luck bar / DSR:** the in-sample league already deflated to "
        "**DSR 0.0000 / honest p-value 1.0000** over 225 trials -- i.e. the "
        "in-sample edge was statistically indistinguishable from the best of a "
        "skill-less search. A single untouched month is a small sample (a "
        "handful of trades per candidate), so it CANNOT by itself resurrect "
        "significance; it can only CONFIRM or REFUTE the direction. No DSR is "
        "computed on the holdout because there is exactly one pre-specified "
        "config per family here (nothing to deflate) -- fabricating a trial "
        "family to manufacture a holdout p-value would be dishonest. (Note: "
        "the SAR family fires often -- ~400-540 per-ficha trade rows in the "
        "month -- so per-candidate trade count is NOT the small-sample issue; "
        "the small sample is the ONE independent monthly regime tested.)\n")
    survives = win_net > 0 and n_pos >= 3
    if survives:
        L.append(
            "- **Direction:** the SAR family's sign HOLDS out of sample (winner "
            "positive, majority of finalists positive). This is corroborating, "
            "NOT decisive: it does not overturn the in-sample DSR verdict "
            "(p=1.0). The honest read is 'not falsified on one untouched "
            "month', not 'validated edge'.\n")
    else:
        L.append(
            "- **Direction:** the SAR family FAILS to carry its sign into this "
            "untouched month (winner and/or majority non-positive). Combined "
            "with the in-sample DSR of 0.0 (p=1.0), the honest conclusion is "
            "that NO candidate survives the out-of-sample gate: the apparent "
            "in-sample edge does not generalize and is consistent with "
            "search-luck.\n")

    L.append("## Caveats (mandatory)\n")
    L.append(
        "- Small-sample holdout: exactly ONE independent monthly regime is "
        "tested (trade COUNT per candidate is high, but they are highly "
        "autocorrelated within one month, not one independent draw). This gate "
        "tests DIRECTION/sign persistence, not a powered significance claim.\n"
        "- Single touch enforced: each candidate priced ONCE here; no lever "
        "was refit and no re-selection was done on holdout results.\n"
        "- The SuperTrend $17.5k legacy headline remains an unverified legacy "
        "TOKATA-ledger artifact (see P34), NOT reproduced here.\n"
        "- Window choice was fixed BEFORE seeing results (most-recent untouched "
        "full month); it was not cherry-picked from several tried windows.\n")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Wave-7 single-touch holdout (W7-T1).")
    ap.add_argument("--report-md", type=str, default=None)
    args = ap.parse_args(argv)

    sar = run_sar_holdout()
    st = run_supertrend_holdout()
    report = build_report(sar, st)

    if args.report_md:
        out = Path(args.report_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"Wrote report -> {out}")
    else:
        print(report)

    for vid in SAR_FINALISTS:
        r = sar[vid]
        print(f"{vid}: net={r['net']:+.2f} trades={r['trades']} "
              f"pf={_fmt_pf(r['pf'])} sharpe={r['sharpe']}")
    print(f"SuperTrend-p14x3-M15: net={st['net']:+.2f} trades={st['trades']} "
          f"pf={_fmt_pf(st['pf'])} flips={st['n_flips']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
