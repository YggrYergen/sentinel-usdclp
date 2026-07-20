"""scripts/report/gen_p34_supertrend_honest.py -- Wave 5, Task P34.

Honest port of the standalone SuperTrend *always-in* p14x3-M15 engine (the
"legacy legend"). Runs SuperTrend(atr_period=14, mult=3.0) always-in on M15
across the program's comparable contrast windows {IW, W1, W2, W3}, applying
the SAME flat-0.5 spread-at-fill and lot 0.10 cost model as every other honest
run, and reports the per-window net, a per-trade net-series Sharpe, and an
HONEST (undeflated, because only one config is evaluated) DSR accounting.

This is READ-ONLY vs data/research.db -- it writes NOTHING to the DB. The one
existing research.db row for this family (`sim-report-supertrend-p14x3-m15`,
screening net 447.8) is left untouched; this script only *compares* to it in
the report.

Engine reuse (ZERO new SuperTrend math):
    - sentinel_engine.strategies._supertrend_ref.supertrend / flips
      (vendored TOKATA reference)
    - sentinel_engine.strategies.emasar_ref._atr_wilder
The always-in flip loop is ported verbatim (same semantics) from
`gen_thu_fri_backtests.py::run_supertrend_always_in`, generalized so it takes
already-loaded window bars and an in-window predicate rather than closing over
that module's fixed ST_* globals.

Window bar loading reuses the EXISTING loaders:
    - gen_oow_validation._bars_for(tf, win_key) for W1/W2/W3
    - gen_variant_batch1._bars_for(tf) for the fixed IW window
Both read BID lake bars on the same integer-epoch convention; no new loader.

Run directly:  python scripts/report/gen_p34_supertrend_honest.py --report-md <path>
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.strategies._supertrend_ref import supertrend, flips  # noqa: E402
from sentinel_engine.strategies.emasar_ref import _atr_wilder  # noqa: E402
from sentinel_engine.opt.registry import deflated_sharpe_ratio  # noqa: E402

# --- Reuse existing loaders via the same importlib pattern the report scripts
#     use (they exec at import; gen_oow_validation itself imports batch1). ---
_OOW_SPEC = _ilu.spec_from_file_location(
    "gen_oow_validation", ROOT / "scripts" / "report" / "gen_oow_validation.py"
)
_OOW = _ilu.module_from_spec(_OOW_SPEC)
_OOW_SPEC.loader.exec_module(_OOW)  # type: ignore[union-attr]

_B1_SPEC = _ilu.spec_from_file_location(
    "gen_variant_batch1", ROOT / "scripts" / "report" / "gen_variant_batch1.py"
)
_B1 = _ilu.module_from_spec(_B1_SPEC)
_B1_SPEC.loader.exec_module(_B1)  # type: ignore[union-attr]

# --- Cost model constants: identical to every other honest run. ---
SPREAD = 0.5          # Capitaria/MT5 flat spread, applied at fill.
LOT = 0.10
CONTRACT_SIZE = 100.0  # XAUUSD: $100 / $1 move / 1.00 lot.

ATR_PERIOD = 14
MULT = 3.0
TF = "M15"

# n_trials for DSR = number of SuperTrend configs actually evaluated here.
# We evaluate exactly ONE config (p14x3). DSR deflation is undefined for a
# single trial (registry raises for n_trials < 2), so DSR is reported as
# "undeflated / not meaningful" -- see build_report / the report text.
N_CONFIGS_EVALUATED = 1

# Windows we run. IW uses batch1's fixed loader; W1/W2/W3 use gen_oow_validation.
WINDOW_ORDER = ["IW", "W1", "W2", "W3"]


# ---------------------------------------------------------------------------
# Spread-at-fill helpers (bars are BID; ask = bid + SPREAD). Same convention
# as gen_thu_fri_backtests / gen_variant_batch1.
# ---------------------------------------------------------------------------
def _entry_fill(side_l: str, bid_price: float) -> float:
    """Long entries buy at ASK; short entries sell at BID."""
    return bid_price + SPREAD if side_l == "L" else bid_price


def _exit_fill(side_l: str, bid_price: float) -> float:
    """Long exits SELL at BID (no adj); short exits BUY BACK at ASK."""
    return bid_price if side_l == "L" else bid_price + SPREAD


def _pnl(side_ui: str, px_in: float, px_out: float, volume: float = LOT) -> float:
    diff = (px_out - px_in) if side_ui == "LONG" else (px_in - px_out)
    return round(diff * volume * CONTRACT_SIZE, 2)


# ---------------------------------------------------------------------------
# Always-in SuperTrend flip engine (ported from
# gen_thu_fri_backtests.run_supertrend_always_in, generalized over bars).
# ---------------------------------------------------------------------------
def supertrend_always_in_trades(
    bars: list[dict[str, Any]],
    atr_period: int,
    mult: float,
    in_window: Callable[[int], bool] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Always-in SuperTrend: open at the first valid-ATR bar on the side of the
    trend; on every subsequent trend flip, close the open position and open the
    OPPOSITE side at the SAME bar's close. No SL/TP/session filter. The position
    still open at feed-end (never flipped again) is left OPEN by design (no exit
    event -> not emitted as a trade), matching the reference engine.

    `in_window(entry_epoch) -> bool` tags each trade with `entry_in_window`;
    defaults to always-True. Returns (trades, n_flips_total).
    """
    if in_window is None:
        in_window = lambda _e: True  # noqa: E731

    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    atr = _atr_wilder(highs, lows, closes, atr_period)
    atr_filled = [a if a is not None else 0.0 for a in atr]
    trend, _line = supertrend(highs, lows, closes, atr_filled, mult)

    flip_list = flips(trend)
    first_valid = next((i for i in range(len(atr)) if atr[i] is not None), None)
    if first_valid is None:
        return [], 0

    trades: list[dict[str, Any]] = []
    side_l = "L" if trend[first_valid] == 1 else "S"
    entry_bid = closes[first_valid]
    entry_t = bars[first_valid]["t"]
    signal_seq = 1

    for idx, new_trend in flip_list:
        if idx < first_valid:
            continue
        bar = bars[idx]
        exit_bid = closes[idx]
        exit_px = _exit_fill(side_l, exit_bid)
        entry_px = _entry_fill(side_l, entry_bid)
        trades.append({
            "signal_id": f"sig-{entry_t}-{signal_seq}",
            "side": "LONG" if side_l == "L" else "SHORT",
            "ts_in_epoch": entry_t,
            "ts_out_epoch": bar["t"],
            "px_in": round(entry_px, 2),
            "px_out": round(exit_px, 2),
            "exit_reason": "EXIT_STFLIP",
            "entry_in_window": in_window(entry_t),
        })
        side_l = "L" if new_trend == 1 else "S"
        entry_bid = exit_bid
        entry_t = bar["t"]
        signal_seq += 1

    return trades, len(flip_list)


# ---------------------------------------------------------------------------
# Window bar loading (reuse existing loaders).
# ---------------------------------------------------------------------------
def _load_window_bars(win_key: str, tf: str) -> list[dict[str, Any]]:
    if win_key == "IW":
        return _B1._bars_for(tf)
    return _OOW._bars_for(tf, win_key)


def _in_window_fn(win_key: str) -> Callable[[int], bool]:
    """Predicate: entry epoch inside the window's (non-warmup) bounds."""
    if win_key == "IW":
        start = int(_B1.WINDOW_START.timestamp())
        end = int(_B1.WINDOW_END_EXCL.timestamp())
    else:
        win = _OOW.WINDOWS[win_key]
        start = int(win["window_start"].timestamp())
        end = int(win["window_end_excl"].timestamp())
    return lambda e: start <= e < end


# ---------------------------------------------------------------------------
# Per-window metrics.
# ---------------------------------------------------------------------------
def compute_window_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-window net (in-window trades only), PF, WR, and the per-trade
    net PnL series (used for the pooled net-series Sharpe / DSR)."""
    in_trades = [t for t in trades if t["entry_in_window"]]
    pnls = [_pnl(t["side"], t["px_in"], t["px_out"]) for t in in_trades]
    n = len(pnls)
    net = round(sum(pnls), 2)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    pf = (round(gross_win / gross_loss, 4) if gross_loss > 0
          else (None if gross_win == 0 else float("inf")))
    wr = round(100.0 * len(wins) / n, 2) if n else None
    return {
        "trades": n,
        "net": net,
        "pf": pf,
        "wr": wr,
        "pnls": pnls,
        "n_flips": None,  # filled by caller
    }


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------
def run_all_windows(tf: str = TF) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for win_key in WINDOW_ORDER:
        try:
            bars = _load_window_bars(win_key, tf)
        except FileNotFoundError:
            results[win_key] = {"loaded": False, "reason": "lake month missing"}
            continue
        if not bars:
            results[win_key] = {"loaded": False, "reason": "no bars in window"}
            continue
        trades, n_flips = supertrend_always_in_trades(
            bars, ATR_PERIOD, MULT, _in_window_fn(win_key)
        )
        m = compute_window_metrics(trades)
        m["n_flips"] = n_flips
        m["loaded"] = True
        m["bars"] = len(bars)
        results[win_key] = m
    return results


def _sharpe(pnls: list[float]) -> float | None:
    if len(pnls) < 2:
        return None
    sd = statistics.stdev(pnls)
    if sd == 0.0:
        return None
    return statistics.mean(pnls) / sd


def build_report(results: dict[str, dict[str, Any]], tf: str = TF) -> str:
    """Render the honest markdown report."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []
    lines.append("# Wave 5 - P34: SuperTrend always-in p14x3-M15 (HONEST port)\n")
    lines.append(f"_Generated {generated} - read-only vs data/research.db._\n")
    lines.append(
        "SuperTrend(atr_period=14, mult=3.0) run **always-in** on "
        f"{tf} across the program's comparable contrast windows, with the same "
        "flat-0.5 spread-at-fill cost model and lot 0.10 as every other honest "
        "run. Because always-in carries NO stop-loss, `live_fill_mode`'s "
        "intrabar-SL honoring is moot; honesty here = flat-0.5 cost at fill + "
        "the comparable windows + DSR trial accounting.\n")

    # Per-window table.
    lines.append("## Per-window honest nets\n")
    lines.append("| Window | Bars | Flips | In-window trades | Net (USD) | PF | WR% |")
    lines.append("|--------|------|-------|------------------|-----------|----|-----|")
    pooled_pnls: list[float] = []
    for win_key in WINDOW_ORDER:
        r = results.get(win_key, {})
        if not r.get("loaded"):
            reason = r.get("reason", "not loaded")
            lines.append(f"| {win_key} | - | - | - | NOT LOADED ({reason}) | - | - |")
            continue
        pooled_pnls.extend(r["pnls"])
        pf = r["pf"]
        pf_s = "inf" if pf == float("inf") else ("-" if pf is None else f"{pf:.3f}")
        wr_s = "-" if r["wr"] is None else f"{r['wr']:.1f}"
        lines.append(
            f"| {win_key} | {r['bars']} | {r['n_flips']} | {r['trades']} | "
            f"{r['net']:+.2f} | {pf_s} | {wr_s} |")
    lines.append("")

    total_net = round(sum(pooled_pnls), 2)
    total_trades = len(pooled_pnls)
    lines.append(f"**Pooled across loaded windows:** {total_trades} in-window "
                 f"trades, net **{total_net:+.2f} USD**.\n")

    # Sharpe / DSR.
    lines.append("## Net-series Sharpe and DSR (honest trial accounting)\n")
    sh = _sharpe(pooled_pnls)
    if sh is None:
        lines.append("- Pooled per-trade net-series Sharpe: **N/A** "
                     "(fewer than 2 trades or zero variance).\n")
    else:
        lines.append(f"- Pooled per-trade net-series Sharpe (raw, per-trade): "
                     f"**{sh:.4f}**.\n")
    lines.append(
        f"- Configs evaluated (DSR `n_trials`): **{N_CONFIGS_EVALUATED}** "
        "(only p14x3). The Deflated Sharpe Ratio requires `n_trials >= 2` "
        "(it deflates for the number of configs *searched*); with a single, "
        "pre-specified config there is nothing to deflate. **DSR is therefore "
        "reported as UNDEFLATED / not meaningful here** -- we do NOT fabricate "
        "a trial family to manufacture a p-value. The raw per-trade Sharpe "
        "above is the observed statistic; treat it as such, not as a "
        "significance claim.\n")

    # Comparison to the screening row.
    lines.append("## Comparison to the existing screening row\n")
    lines.append(
        "The single research.db row for this family, "
        "`sim-report-supertrend-p14x3-m15` (mode=ro), reports net **447.8** "
        "over 51 trades on the IW-ish window 2026-06-08..07-07, "
        "fidelity=screening (flat-0.5 at fill, but NOT run through the honest "
        "windowed machinery). It is left UNTOUCHED by this script.\n")
    iw = results.get("IW", {})
    if iw.get("loaded"):
        lines.append(
            f"This honest IW run yields net **{iw['net']:+.2f}** over "
            f"{iw['trades']} in-window trades ({iw['n_flips']} flips on "
            f"{iw['bars']} bars). Differences vs the 447.8 screening figure "
            "arise from the exact window/warmup framing and the in-window "
            "trade filter, not from a different cost model.\n")

    # Evidence gap -- MANDATORY, load-bearing.
    lines.append("## EVIDENCE GAP (mandatory disclosure)\n")
    lines.append(
        "The legendary real-tick headline for this family -- **Net +$17,512, "
        "PF 1.49, 206 trades** (sometimes quoted as +$17,510) -- is **NOT "
        "reproducible in data/research.db and is NOT validated by this run.** "
        "That figure lives in a LEGACY TOKATA ledger (`mt5_ledger.csv`, real "
        "MT5 fills, window ~Jan-May 2026), which is OUTSIDE this program's data "
        "lake and comparable-window methodology. The lake does not cover that "
        "exact tick stream, so the $17.5k number cannot be independently "
        "reproduced or deflated here.\n")
    lines.append(
        "What IS honest and reproducible: the per-window nets above, run "
        "through the identical flat-0.5 / lot-0.10 / comparable-window pipeline "
        "used for every other honest strategy. Those -- not the legacy $17.5k "
        "headline -- are this family's honest, comparable evidence. Any use of "
        "the $17.5k figure MUST carry this caveat: it is an unverified legacy "
        "artifact, not a program-validated result.\n")

    lines.append("## Design notes / loose ends\n")
    lines.append(
        "- Position open at each window's feed-end (never flipped again) is "
        "left OPEN and not emitted as a trade -- matches the reference "
        "`run_supertrend_always_in` semantics (flip = only exit signal).\n"
        "- SuperTrend math is the vendored `_supertrend_ref`; ATR is "
        "`emasar_ref._atr_wilder`. No indicator code was re-implemented.\n"
        "- Windows loaded via the existing loaders "
        "(`gen_variant_batch1._bars_for` for IW, `gen_oow_validation._bars_for` "
        "for W1/W2/W3); no new bar loader was written.\n")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Honest SuperTrend p14x3-M15 port (P34).")
    ap.add_argument("--report-md", type=str, default=None,
                    help="Path to write the honest markdown report.")
    ap.add_argument("--tf", type=str, default=TF, help="Timeframe dir (default M15).")
    args = ap.parse_args(argv)

    results = run_all_windows(args.tf)
    report = build_report(results, args.tf)

    if args.report_md:
        out = Path(args.report_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"Wrote report -> {out}")
    else:
        print(report)

    for win_key in WINDOW_ORDER:
        r = results.get(win_key, {})
        if r.get("loaded"):
            print(f"{win_key}: net={r['net']:+.2f} trades={r['trades']} "
                  f"flips={r['n_flips']} bars={r['bars']}")
        else:
            print(f"{win_key}: NOT LOADED ({r.get('reason', '?')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
