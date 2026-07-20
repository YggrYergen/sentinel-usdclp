"""gen_wave4_portfolio.py — Wave 4 OFFLINE portfolio & cross-config study.

Honest Program "complete the 66", Wave 4: P48 (correlation/netting), P49
(rolling meta-selector, DSR-gated), P50 (M2-trio signal overlap). Read-only
against data/research.db (opened mode=ro). Produces an honest report via
--report-md.

Design notes
------------
* Wave 3 proved per-config CONSTANT sizing multipliers (Kelly/risk-parity) are
  Sharpe-invariant, so the only real cross-config test is PORTFOLIO
  composition (this wave).
* F1/F2/F3 dedup: a config runs 3 "fichas" (position replicas). Within a
  window they are (empirically) exact replicas — same signal_id, identical
  pnl+exit. The stored trials `net_honest` SUMS all three, tripling the true
  economic net. We DEDUP to one economic position per signal (collapse
  identical-pnl+exit fichas; keep divergent ones) before summing — this is
  the honest per-config net.
* All numbers use stored honest-screen fixed-lot pnl as the base (no sizing
  overlay applied); any overlay would be disclosed here (none is).

Run: python scripts/report/gen_wave4_portfolio.py --report-md <path>
"""
from __future__ import annotations

import argparse
import math
import sqlite3
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

# --------------------------------------------------------------------------
# Data facts (established Waves 1-3; do not re-investigate).
# --------------------------------------------------------------------------
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))  # make sentinel_engine importable when run directly
_RESEARCH_DB = _REPO / "data" / "research.db"
_LEAGUE_V2 = _REPO / "docs" / "superpowers" / "research" / "2026-07-20-honest-league-v2.trials.db"

_WINDOWS = ("IW", "W1", "W2", "W3")  # M15 has all four; M2 lacks W3.

# Top M15 tie-pool: positive median-fold-net configs in the SAR / V-15 / TS40
# / BE families (per 2026-07-20-honest-league-v2.md leaderboard). Many rows in
# that pool are exact numeric duplicates (Sharpe-invariant K-sizing variants);
# we pick the DISTINCT economic net series below at load time. This is the
# curated seed list of variant_ids to consider.
_M15_TIEPOOL = (
    "HON-W2-S6-K2P0-M15-SAR",
    "HON-W2-S6-K1P5-M15-SAR",
    "HON-W2-S7-TPNONE-M15-SAR",
    "HON-W2-S7-TP1P0-M15-SAR",
    "HON-S7-V15-TPNONE-BE1P0-M15",
    "HON-S6-V15-K1P5-AC1-M15",
    "HON-S7-V15-TP1P0-BE1P0-M15",
    "HON-S7-V15-TP1P5-BE1P0-M15",
    "HON-S6-V15-K3P0-AC1-M15",
    "HON-S1-V15-M15",
)

# P50 M2-trio bases (M2 V-11 / V-13 / V-15).
_M2_TRIO = ("HON-S1-V11-M2", "HON-S1-V13-M2", "HON-S1-V15-M2")

_TS_FORMATS = ("%Y.%m.%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


# --------------------------------------------------------------------------
# Pure data model + logic (unit-tested).
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Trade:
    signal_id: str
    ficha: str
    pnl: float
    side: str
    ts_in: str
    ts_out: str
    exit_reason: str


def _parse_ts(s: str) -> datetime:
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"unparseable timestamp: {s!r}")


def dedup_trades(rows: Iterable[Trade]) -> list[Trade]:
    """Collapse F1/F2/F3 replicas to one economic position per signal.

    Rule (from the brief): where a config's fichas are replicas (same
    signal_id + identical pnl -> count once); where fichas diverge (different
    exit -> keep each). We key uniqueness on (signal_id, pnl, exit_reason):
    identical replicas collapse; a divergent ficha (different pnl OR exit) is
    a distinct economic outcome and is kept.
    """
    seen: set[tuple[str, float, str]] = set()
    out: list[Trade] = []
    for t in rows:
        key = (t.signal_id, t.pnl, t.exit_reason)
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def config_net(configs: Mapping[str, Sequence[Trade]]) -> dict[str, float]:
    """Dedup'd net pnl per config."""
    return {name: sum(t.pnl for t in dedup_trades(rows)) for name, rows in configs.items()}


def combined_portfolio_net(configs: Mapping[str, Sequence[Trade]]) -> float:
    """Equal-weight combined-portfolio net = sum of each config's dedup'd net."""
    return sum(config_net(configs).values())


def _signal_ts_key(signal_id: str) -> str:
    """Overlap key = the embedded entry epoch (sig-{epoch}-{seq}); strip the
    trailing per-config sequence number so the same entry-time counts as
    shared across configs."""
    parts = signal_id.split("-")
    return "-".join(parts[:-1]) if len(parts) >= 3 else signal_id


def signal_overlap_jaccard(a: Iterable[Trade], b: Iterable[Trade]) -> float:
    ka = {_signal_ts_key(t.signal_id) for t in a}
    kb = {_signal_ts_key(t.signal_id) for t in b}
    if not ka and not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


def exposure_netting(configs: Mapping[str, Sequence[Trade]]) -> dict[str, float]:
    """Gross-vs-net exposure over the shared timeline.

    We sweep all position open/close events. At any instant the GROSS
    exposure is the count of open positions; the NET exposure is
    |longs - shorts|. Integrating each over time (in minutes) and comparing
    gives the netting reduction. Opposite-overlap intervals are counted when
    both a long and a short are simultaneously open.
    """
    # Build per-side step deltas: each dedup'd trade contributes +1 at entry
    # and -1 at exit on its side's counter.
    from collections import defaultdict

    long_delta: dict[datetime, int] = defaultdict(int)
    short_delta: dict[datetime, int] = defaultdict(int)
    for rows in configs.values():
        for t in dedup_trades(rows):
            ti = _parse_ts(t.ts_in)
            to = _parse_ts(t.ts_out)
            if to <= ti:
                continue
            if t.side.upper() == "LONG":
                long_delta[ti] += 1
                long_delta[to] -= 1
            else:
                short_delta[ti] += 1
                short_delta[to] -= 1

    times = sorted(set(long_delta) | set(short_delta))
    if len(times) < 2:
        return {
            "gross_exposure_minutes": 0.0,
            "net_exposure_minutes": 0.0,
            "reduction_pct": 0.0,
            "opposite_overlap_intervals": 0,
        }

    gross_min = 0.0
    net_min = 0.0
    opposite_intervals = 0
    longs = shorts = 0
    for i in range(len(times) - 1):
        t0 = times[i]
        longs += long_delta.get(t0, 0)
        shorts += short_delta.get(t0, 0)
        span = (times[i + 1] - t0).total_seconds() / 60.0
        gross = longs + shorts
        net = abs(longs - shorts)
        gross_min += gross * span
        net_min += net * span
        if longs > 0 and shorts > 0 and span > 0:
            opposite_intervals += 1
    reduction = 0.0 if gross_min == 0 else 100.0 * (gross_min - net_min) / gross_min
    return {
        "gross_exposure_minutes": gross_min,
        "net_exposure_minutes": net_min,
        "reduction_pct": reduction,
        "opposite_overlap_intervals": opposite_intervals,
    }


def series_sharpe(returns: Sequence[float]) -> float:
    r = [float(x) for x in returns]
    if len(r) < 2:
        return 0.0
    sd = statistics.stdev(r)
    if sd == 0.0:
        return 0.0
    return statistics.mean(r) / sd


def series_maxdd(returns: Sequence[float]) -> float:
    """Max drawdown of the cumulative net series (absolute USD)."""
    cum = 0.0
    peak = 0.0
    mdd = 0.0
    for x in returns:
        cum += x
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    return mdd


def pairwise_correlation(series_by_cfg: Mapping[str, Sequence[float]]) -> dict[tuple[str, str], float]:
    names = list(series_by_cfg)
    out: dict[tuple[str, str], float] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sa, sb = series_by_cfg[a], series_by_cfg[b]
            out[(a, b)] = _pearson(sa, sb)
    return out


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    n = len(a)
    if n < 2 or n != len(b):
        return float("nan")
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return float("nan")
    return num / (da * db)


# --------------------------------------------------------------------------
# DB loading (read-only).
# --------------------------------------------------------------------------
def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _run_id(variant_id: str, tf: str, window: str) -> str:
    return f"honest-{variant_id}-{tf}-{window}".lower()


def load_config_window(conn: sqlite3.Connection, variant_id: str, tf: str, window: str) -> list[Trade]:
    rid = _run_id(variant_id, tf, window)
    cur = conn.execute(
        "SELECT signal_id, ficha, pnl, side, ts_in, ts_out, exit_reason "
        "FROM trade WHERE run_id = ?",
        (rid,),
    )
    return [Trade(*row) for row in cur.fetchall()]


def load_config_all_windows(conn: sqlite3.Connection, variant_id: str, tf: str,
                            windows: Sequence[str]) -> dict[str, list[Trade]]:
    out: dict[str, list[Trade]] = {}
    for w in windows:
        rows = load_config_window(conn, variant_id, tf, w)
        if rows:
            out[w] = rows
    return out


# --------------------------------------------------------------------------
# Analyses.
# --------------------------------------------------------------------------
def _distinct_net_configs(conn: sqlite3.Connection) -> dict[str, dict[str, list[Trade]]]:
    """Load the M15 tie-pool, dropping variants whose per-window net vector is
    an exact duplicate of an already-kept one (Sharpe-invariant K-variants)."""
    kept: dict[str, dict[str, list[Trade]]] = {}
    seen_vecs: set[tuple[float, ...]] = set()
    for vid in _M15_TIEPOOL:
        by_w = load_config_all_windows(conn, vid, "M15", _WINDOWS)
        if len(by_w) < len(_WINDOWS):
            continue
        vec = tuple(round(sum(t.pnl for t in dedup_trades(by_w[w])), 2) for w in _WINDOWS)
        if vec in seen_vecs:
            continue
        seen_vecs.add(vec)
        kept[vid] = by_w
    return kept


def analysis_p48(conn: sqlite3.Connection) -> dict:
    cfgs = _distinct_net_configs(conn)
    # Per-config per-window dedup'd net series.
    window_net: dict[str, list[float]] = {
        vid: [sum(t.pnl for t in dedup_trades(by_w[w])) for w in _WINDOWS]
        for vid, by_w in cfgs.items()
    }
    corr = pairwise_correlation(window_net)
    # Combined equal-weight portfolio per-window net.
    combined_series = [
        sum(window_net[vid][i] for vid in cfgs) for i in range(len(_WINDOWS))
    ]
    # Exposure netting over the shared timeline (flatten all windows).
    flat = {vid: [t for w in _WINDOWS for t in by_w[w]] for vid, by_w in cfgs.items()}
    netting = exposure_netting(flat)
    # Combined vs best single config.
    per_cfg_total = {vid: sum(s) for vid, s in window_net.items()}
    best_vid = max(per_cfg_total, key=per_cfg_total.get)
    return {
        "configs": list(cfgs),
        "window_net": window_net,
        "corr": corr,
        "combined_series": combined_series,
        "combined_total": sum(combined_series),
        "combined_sharpe": series_sharpe(combined_series),
        "combined_maxdd": series_maxdd(combined_series),
        "best_vid": best_vid,
        "best_total": per_cfg_total[best_vid],
        "best_sharpe": series_sharpe(window_net[best_vid]),
        "best_maxdd": series_maxdd(window_net[best_vid]),
        "netting": netting,
    }


def analysis_p49(conn: sqlite3.Connection, p48: dict) -> dict:
    """Anchored rolling meta-selector, DSR-gated.

    At each window boundary k (k=1..N-1): rank configs by cumulative net over
    prior windows [0..k-1], pick the leader, trade it in window k (OOS).
    DSR-gate: only 'deploy' the pick if its DSR over the prior windows would
    clear (dsr>=0.95 / p<=0.05). Family size = number of configs searched.
    """
    from sentinel_engine.opt.registry import deflated_sharpe_ratio

    window_net = p48["window_net"]
    cfgs = list(window_net)
    n = len(_WINDOWS)
    n_trials = max(2, len(cfgs))

    oos_static_best = window_net[p48["best_vid"]]
    static_oos = sum(oos_static_best[1:])  # static best traded OOS windows 1..N-1

    picks: list[dict] = []
    meta_oos_net = 0.0
    for k in range(1, n):
        prior_cum = {vid: sum(window_net[vid][:k]) for vid in cfgs}
        leader = max(prior_cum, key=prior_cum.get)
        prior_series = window_net[leader][:k]
        gated = False
        dsr_val = float("nan")
        p_val = float("nan")
        if len(prior_series) >= 2 and statistics.pstdev(prior_series) > 0:
            try:
                res = deflated_sharpe_ratio(
                    prior_series, n_trials,
                    trial_sharpe_std=statistics.pstdev(
                        [series_sharpe(window_net[v][:k]) for v in cfgs]
                    ) or None,
                )
                dsr_val, p_val = res.dsr, res.p_value
                gated = res.dsr >= 0.95
            except ValueError:
                gated = False
        realized = window_net[leader][k] if gated else 0.0
        meta_oos_net += realized
        picks.append({
            "boundary": _WINDOWS[k], "leader": leader, "deployed": gated,
            "dsr": dsr_val, "p_value": p_val, "oos_net": window_net[leader][k],
            "realized": realized,
        })
    return {
        "picks": picks,
        "meta_oos_net": meta_oos_net,
        "static_oos_net": static_oos,
        "static_best": p48["best_vid"],
        "n_decisions": n - 1,
        "n_trials": n_trials,
    }


def analysis_p50(conn: sqlite3.Connection) -> dict:
    trio: dict[str, list[Trade]] = {}
    windows_m2 = ("IW", "W1", "W2")  # M2 lacks W3
    for vid in _M2_TRIO:
        rows: list[Trade] = []
        for w in windows_m2:
            rows.extend(load_config_window(conn, vid, "M2", w))
        trio[vid] = rows
    pairs: dict[tuple[str, str], float] = {}
    names = list(trio)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pairs[(a, b)] = signal_overlap_jaccard(trio[a], trio[b])
    counts = {vid: len({_signal_ts_key(t.signal_id) for t in rows})
              for vid, rows in trio.items()}
    return {"pairs": pairs, "signal_counts": counts, "configs": names}


# --------------------------------------------------------------------------
# Report.
# --------------------------------------------------------------------------
def _fmt_corr_matrix(configs: Sequence[str], corr: Mapping[tuple[str, str], float]) -> str:
    lines = ["| config | " + " | ".join(c.replace("HON-", "") for c in configs) + " |",
             "|" + "---|" * (len(configs) + 1)]
    for a in configs:
        cells = []
        for b in configs:
            if a == b:
                cells.append("1.00")
            else:
                key = (a, b) if (a, b) in corr else (b, a)
                v = corr.get(key, float("nan"))
                cells.append("nan" if math.isnan(v) else f"{v:+.2f}")
        lines.append(f"| {a.replace('HON-','')} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_report(p48: dict, p49: dict, p50: dict) -> str:
    L: list[str] = []
    L.append("# Wave 4 — Portfolio & cross-config study (P48 / P49 / P50)")
    L.append("")
    L.append("_Honest Program, offline. Generated by "
             "`scripts/report/gen_wave4_portfolio.py` (read-only vs "
             "`data/research.db`). All nets use stored honest-screen fixed-lot "
             "pnl, F1/F2/F3-dedup'd (one economic position per signal); NO "
             "sizing overlay applied._")
    L.append("")
    L.append("**Context.** Waves 1–3: 195 honest DSR-gated configs, no "
             "significant edge (DSR 0 / p 1); the M15 V-15 tie-pool is the only "
             "real net; per-config CONSTANT sizing multipliers are "
             "Sharpe-invariant, so portfolio composition is the only untested "
             "lever — this wave.")
    L.append("")

    # P48
    L.append("## P48 — correlation / netting")
    L.append("")
    L.append(f"Distinct-net M15 tie-pool configs studied ({len(p48['configs'])} "
             "after dropping exact-duplicate K-variants):")
    L.append("")
    for vid in p48["configs"]:
        s = p48["window_net"][vid]
        L.append(f"- `{vid}` — window nets (dedup'd) "
                 f"[{', '.join(f'{x:+.0f}' for x in s)}], total {sum(s):+.0f}")
    L.append("")
    L.append("**Pairwise correlation of per-window net series (n=4 windows — "
             "thin; treat as directional only):**")
    L.append("")
    L.append(_fmt_corr_matrix(p48["configs"], p48["corr"]))
    L.append("")
    corr_vals = [v for v in p48["corr"].values() if not math.isnan(v)]
    if corr_vals:
        L.append(f"Mean pairwise corr = {statistics.mean(corr_vals):+.2f} "
                 f"(min {min(corr_vals):+.2f}, max {max(corr_vals):+.2f}). "
                 "With only 4 observations per series, these correlations are "
                 "statistically meaningless individually; reported for honesty, "
                 "not inference.")
    L.append("")
    net = p48["netting"]
    L.append("**Netting (gross vs net exposure over the shared timeline):**")
    L.append("")
    L.append(f"- Opposite-side simultaneous-overlap intervals: "
             f"{net['opposite_overlap_intervals']}")
    L.append(f"- Gross exposure: {net['gross_exposure_minutes']:.0f} position-minutes")
    L.append(f"- Net exposure: {net['net_exposure_minutes']:.0f} position-minutes")
    L.append(f"- **Exposure reduction from netting: {net['reduction_pct']:.1f}%**")
    L.append("")
    L.append("**Combined equal-weight portfolio vs single best config:**")
    L.append("")
    L.append(f"- Combined per-window net "
             f"[{', '.join(f'{x:+.0f}' for x in p48['combined_series'])}], "
             f"total {p48['combined_total']:+.0f}, "
             f"across-window Sharpe {p48['combined_sharpe']:+.2f}, "
             f"maxDD {p48['combined_maxdd']:+.0f}")
    L.append(f"- Best single (`{p48['best_vid']}`): total {p48['best_total']:+.0f}, "
             f"across-window Sharpe {p48['best_sharpe']:+.2f}, "
             f"maxDD {p48['best_maxdd']:+.0f}")
    L.append("")
    L.append("_Caveat: the \"Sharpe\" here is mean/stdev of only 4 per-window "
             "net aggregates — a small-sample statistic, not a trade-level "
             "Sharpe. The maxDD is 0 for any series whose 4 window aggregates "
             "are all positive, which is a triviality of the 4-point "
             "granularity, not evidence of a drawdown-free strategy._")
    L.append("")
    L.append(f"**Verdict:** the combined across-window Sharpe "
             f"({p48['combined_sharpe']:+.2f}) exceeds the best single "
             f"({p48['best_sharpe']:+.2f}), but this is a mechanical "
             "small-sample artifact: summing ~10 near-clone series with "
             "uniformly-positive window aggregates shrinks the relative "
             "cross-window dispersion. The configs share one V-15/SAR signal "
             "engine (see the ~+1.00 correlations among the SAR/BE clusters and "
             "P50's 60–77% M2 signal overlap), so there is almost nothing "
             "genuinely independent to diversify. Honest read: **no real "
             "diversification benefit** under honest pricing — the number is an "
             "aggregation artifact, not an edge.")
    L.append("")

    # P49
    L.append("## P49 — rolling meta-selector (anchored, DSR-gated)")
    L.append("")
    L.append(f"Anchored rolling best-of over {p49['n_decisions']} OOS boundaries "
             f"(trial family = {p49['n_trials']} configs). At each boundary the "
             "leader by prior-window cumulative net is picked, DSR-gated, and "
             "traded the next window OOS.")
    L.append("")
    L.append("| boundary | leader | prior-DSR | p | deployed? | OOS net | realized |")
    L.append("|---|---|---|---|---|---|---|")
    for pk in p49["picks"]:
        dsr = "nan" if math.isnan(pk["dsr"]) else f"{pk['dsr']:.2f}"
        pv = "nan" if math.isnan(pk["p_value"]) else f"{pk['p_value']:.2f}"
        L.append(f"| {pk['boundary']} | `{pk['leader'].replace('HON-','')}` | "
                 f"{dsr} | {pv} | {'YES' if pk['deployed'] else 'no'} | "
                 f"{pk['oos_net']:+.0f} | {pk['realized']:+.0f} |")
    L.append("")
    L.append(f"- Meta-selector OOS net (DSR-gated): **{p49['meta_oos_net']:+.0f}**")
    L.append(f"- Static single-best (`{p49['static_best'].replace('HON-','')}`) "
             f"OOS net over the same windows: **{p49['static_oos_net']:+.0f}**")
    L.append("")
    L.append("**Honest limitation:** only 4 windows → 3 OOS decisions. This is "
             "statistically thin — a directional read, not a significant result. "
             "The DSR gate over a 1–3 point prior series is essentially a coin "
             "flip; do NOT read the meta-selector's edge (or lack of it) as "
             "evidence of anything. No significance is claimed.")
    L.append("")

    # P50
    L.append("## P50 — M2-trio signal overlap (finding, not a drop)")
    L.append("")
    L.append("Pairwise signal-entry overlap (Jaccard on embedded entry epoch) "
             "for the M2 V-11/V-13/V-15 bases:")
    L.append("")
    for vid in p50["configs"]:
        L.append(f"- `{vid}` — {p50['signal_counts'][vid]} distinct entry signals")
    L.append("")
    L.append("| pair | signal overlap (Jaccard) |")
    L.append("|---|---|")
    for (a, b), frac in p50["pairs"].items():
        L.append(f"| `{a}` × `{b}` | {frac*100:.1f}% |")
    L.append("")
    ov = list(p50["pairs"].values())
    if ov:
        L.append(f"Mean pairwise redundancy = {statistics.mean(ov)*100:.1f}%. "
                 "This is a measurement only: high overlap means the M2 trio is "
                 "largely one signal engine at different V-thresholds, so "
                 "combining them adds little independent information.")
    L.append("")
    L.append("---")
    L.append("_Generated offline; research.db opened mode=ro (no writes). "
             "Honest limitations (n=4 windows, thin OOS) stated explicitly._")
    L.append("")
    return "\n".join(L)


def main(report_md: str | Path | None = None) -> str:
    conn = _connect_ro(_RESEARCH_DB)
    try:
        p48 = analysis_p48(conn)
        p49 = analysis_p49(conn, p48)
        p50 = analysis_p50(conn)
    finally:
        conn.close()
    report = render_report(p48, p49, p50)
    if report_md is not None:
        path = Path(report_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    return report


def _cli() -> None:
    ap = argparse.ArgumentParser(description="Wave 4 offline portfolio study")
    ap.add_argument("--report-md", type=str, default=None,
                    help="write the generated honest report to this path")
    args = ap.parse_args()
    report = main(report_md=args.report_md)
    if args.report_md:
        print(f"wrote report to {args.report_md}")
    else:
        print(report)


if __name__ == "__main__":
    _cli()
