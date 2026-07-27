"""B1 robustness -- does the wait-curve's +32.67% at N3 survive scrutiny?

THE PROBLEM THIS ANSWERS. Task 16 (b1_wait_curve.py) found a hump-shaped
COMBINED curve: N2 +13.27%, N3 +32.67% (peak), N4 +20.01%, N5 +9.72%, N6
-15.24%. Win rate barely moves across that whole range (34.41%..35.35%)
while net swings 48 points. That pattern is compatible with two very
different stories that the curve alone cannot distinguish:

  (a) the gate SELECTS -- the blocked entries were systematically worse, so
      the net improvement reflects a real edge in avoiding post-reopen bars;
  (b) the gate SHUFFLES -- the blocked entries are statistically
      indistinguishable from the rest, and the swing is driven by a handful
      of large trades landing on one side of an arbitrary N.

This module builds three independent checks against that question. It does
NOT decide it -- see the caveat in the artifact and the module-level notes
on each function.

  M1 sign_consistency  -- does each rung's net improvement hold up month by
                           month, or is it one or two good months carrying
                           the whole 7-month average?
  M2 topk_sensitivity   -- does the ranking of rungs survive removing the
                           K largest |net| trades (globally, and per
                           strategy)?
  M3 blocked_vs_kept    -- is the distribution of blocked trades actually
                           worse than the distribution of kept trades, or
                           just different (e.g. same center, fatter tails)?

REUSE, NOT REDERIVATION. "Blocked" is defined exactly as Task 16 defined it:
`is_blocked(bars_since_reopen(t_in, reopens), n)`, imported from
b1_wait_curve.py, never reimplemented. Divergence here would make the
numbers incomparable to the wait-curve document and defeat the point.

REPORT-ONLY. Nothing in this module or its artifact recommends a rung to
deploy. The B1 mask verdict is pre-committed at 50 minutes in
b6_masks.py and does not move because of anything found here. See
docs/superpowers/research/2026-07-27-b1-robustness.md.

Timestamps are broker server time throughout. No timezone correction is
applied anywhere in this file (none should be -- the substrate is already
fixed at the source).
"""
from __future__ import annotations

import datetime as dt
import math

from scripts.analysis.monday_audit.a3_a4_a5_stats import profit_factor, win_rate
from scripts.analysis.monday_audit.b1_wait_curve import (
    BAR_MINUTES, RUNGS, bars_since_reopen, is_blocked)
from scripts.analysis.monday_audit.loader import Position, load_positions, write_artifact
from scripts.analysis.monday_audit.session_clock import load_bar_times, market_reopens

TOPK_VALUES = (1, 3, 5, 10)


def _groups(rows: list[Position]) -> dict[str, list[Position]]:
    """Same 4-key breakdown b1_wait_curve.wait_curve uses: one entry per
    strategy present in `rows`, plus COMBINED."""
    strategies = sorted({p.strategy for p in rows})
    groups: dict[str, list[Position]] = {s: [p for p in rows if p.strategy == s]
                                          for s in strategies}
    groups["COMBINED"] = rows
    return groups


def _bars_of(rows: list[Position], reopens: list[dt.datetime]) -> dict[Position, int | None]:
    return {p: bars_since_reopen(p.t_in, reopens) for p in rows}


# =========================================================================
# M1 -- sign consistency, month by month
# =========================================================================
def sign_consistency(rows: list[Position], reopens: list[dt.datetime],
                      rungs: list[int] = RUNGS) -> dict:
    """For each group (per-strategy + COMBINED) and each rung, the
    month-by-month baseline/kept/delta using the position's own `month`
    field (never re-derived from t_in), plus how many months the rung's
    delta was positive/negative/exactly zero.

    Pure function over `rows`/`reopens` -- testable on synthetic data."""
    groups = _groups(rows)
    bars_of = _bars_of(rows, reopens)

    out: dict = {}
    for key, positions in groups.items():
        months = sorted({p.month for p in positions})
        by_month = {m: [p for p in positions if p.month == m] for m in months}

        rung_out: dict = {}
        for n in rungs:
            month_rows = []
            n_pos = n_neg = n_zero = 0
            for m in months:
                pm = by_month[m]
                baseline_net = sum(p.net_067lot_clp for p in pm)
                kept = [p for p in pm if not is_blocked(bars_of[p], n)]
                kept_net = sum(p.net_067lot_clp for p in kept)
                delta = kept_net - baseline_net
                delta_pct = (100.0 * delta / baseline_net) if baseline_net else 0.0
                month_rows.append({
                    "month": m,
                    "baseline_net_clp": baseline_net,
                    "kept_net_clp": kept_net,
                    "delta_clp": delta,
                    "delta_pct": delta_pct,
                    "n_blocked": len(pm) - len(kept),
                })
                if delta > 0:
                    n_pos += 1
                elif delta < 0:
                    n_neg += 1
                else:
                    n_zero += 1
            rung_out[f"N{n}"] = {
                "months": month_rows,
                "n_months_positive": n_pos,
                "n_months_negative": n_neg,
                "n_months_zero": n_zero,
                "n_months_total": len(months),
            }
        out[key] = rung_out
    return out


# =========================================================================
# M2 -- sensitivity to removing the K largest |net| trades
# =========================================================================
def _trim_key(p: Position) -> tuple:
    """Deterministic ordering for "biggest |net| first": descending |net|,
    then ascending (t_in, strategy, ficha) to break exact ties reproducibly
    (same value can recur, e.g. round-number stop-outs)."""
    return (-abs(p.net_067lot_clp), p.t_in, p.strategy, p.ficha)


def trim_top_k_global(rows: list[Position], k: int) -> tuple[list[Position], list[Position]]:
    """Remove the K positions with the largest |net| from the WHOLE
    population (may span multiple strategies). Returns (remaining, removed),
    both preserving `rows`' relative order. Uses list index, not dataclass
    equality, so it is safe even if two positions were ever field-identical."""
    order = sorted(range(len(rows)), key=lambda i: _trim_key(rows[i]))
    removed_idx = set(order[:k])
    removed = [rows[i] for i in range(len(rows)) if i in removed_idx]
    remaining = [rows[i] for i in range(len(rows)) if i not in removed_idx]
    return remaining, removed


def trim_top_k_by_group(rows: list[Position], k: int) -> tuple[list[Position], list[Position]]:
    """Remove the K positions with the largest |net| WITHIN EACH STRATEGY
    separately (so K per strategy, not K total). Returns (remaining, removed)
    across all strategies combined."""
    remaining: list[Position] = []
    removed: list[Position] = []
    for strat in sorted({p.strategy for p in rows}):
        group_rows = [p for p in rows if p.strategy == strat]
        rem, rmv = trim_top_k_global(group_rows, k)
        remaining.extend(rem)
        removed.extend(rmv)
    return remaining, removed


def _pos_ref(p: Position) -> dict:
    """Minimal JSON-safe identifier for a removed position, for audit."""
    return {"strategy": p.strategy, "ficha": p.ficha, "t_in": p.t_in.isoformat(),
            "net_clp": p.net_067lot_clp}


def _rung_nets(rows: list[Position], reopens: list[dt.datetime],
                rungs: list[int]) -> dict:
    """baseline + per-rung net/delta_pct, per group. Deliberately smaller
    than b1_wait_curve.wait_curve's output (no win_rate/PF) -- M2 only needs
    net and delta_pct to answer "does the ranking survive the trim"."""
    groups = _groups(rows)
    bars_of = _bars_of(rows, reopens)
    out: dict = {}
    for key, positions in groups.items():
        baseline_net = sum(p.net_067lot_clp for p in positions)
        rung_out: dict = {"baseline": {"net_clp": baseline_net, "n": len(positions)}}
        for n in rungs:
            kept = [p for p in positions if not is_blocked(bars_of[p], n)]
            kept_net = sum(p.net_067lot_clp for p in kept)
            delta = kept_net - baseline_net
            delta_pct = (100.0 * delta / baseline_net) if baseline_net else 0.0
            rung_out[f"N{n}"] = {
                "net_clp": kept_net,
                "n_kept": len(kept),
                "n_blocked": len(positions) - len(kept),
                "delta_clp": delta,
                "delta_pct": delta_pct,
            }
        out[key] = rung_out
    return out


def _rank_rungs_by_group(rung_nets: dict, rungs: list[int]) -> dict:
    out: dict = {}
    for key, data in rung_nets.items():
        ranked = sorted(
            ({"rung": f"N{n}", "net_clp": data[f"N{n}"]["net_clp"],
              "delta_pct": data[f"N{n}"]["delta_pct"]} for n in rungs),
            key=lambda r: r["net_clp"], reverse=True)
        out[key] = ranked
    return out


def topk_sensitivity(rows: list[Position], reopens: list[dt.datetime],
                      ks: tuple[int, ...] = TOPK_VALUES,
                      rungs: list[int] = RUNGS) -> dict:
    """For each K in `ks`, two trims -- GLOBAL (K biggest |net| out of the
    whole population, carried through to whichever strategies they belonged
    to) and BY_GROUP (K biggest |net| removed independently within each
    strategy) -- each recomputing baseline/delta_pct/ranking on the trimmed
    population. Pure over `rows`/`reopens`."""
    out: dict = {"global": {}, "by_group": {}}
    for k in ks:
        remaining, removed = trim_top_k_global(rows, k)
        rung_nets = _rung_nets(remaining, reopens, rungs)
        out["global"][f"K{k}"] = {
            "n_removed": len(removed),
            "removed": [_pos_ref(p) for p in removed],
            "curve": rung_nets,
            "ranking": _rank_rungs_by_group(rung_nets, rungs),
        }
    for k in ks:
        remaining, removed = trim_top_k_by_group(rows, k)
        rung_nets = _rung_nets(remaining, reopens, rungs)
        out["by_group"][f"K{k}"] = {
            "n_removed": len(removed),
            "removed": [_pos_ref(p) for p in removed],
            "curve": rung_nets,
            "ranking": _rank_rungs_by_group(rung_nets, rungs),
        }
    return out


# =========================================================================
# percentile (shared by M3)
# =========================================================================
def percentile(values: list[float], q: float) -> float:
    """Linear-interpolation percentile, inclusive of both endpoints -- the
    same convention as `numpy.percentile`'s default ("linear") and R's
    type 7. For a sorted vector of n values, position = q/100 * (n-1),
    interpolated between the two neighboring order statistics.

    0.0 for an empty vector (there is nothing to describe -- callers that
    care should check `n` first)."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    pos = (q / 100.0) * (n - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[int(pos)]
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _profile(nets: list[float]) -> dict:
    """Shape of a set of trade outcomes: center, spread, and tails."""
    if not nets:
        return {"n": 0, "sum_clp": 0.0, "mean_clp": 0.0, "median_clp": 0.0,
                "p10": 0.0, "p25": 0.0, "p75": 0.0, "p90": 0.0,
                "win_rate": 0.0, "profit_factor": 0.0,
                "max_win": 0.0, "max_loss": 0.0}
    return {
        "n": len(nets),
        "sum_clp": sum(nets),
        "mean_clp": sum(nets) / len(nets),
        "median_clp": percentile(nets, 50),
        "p10": percentile(nets, 10),
        "p25": percentile(nets, 25),
        "p75": percentile(nets, 75),
        "p90": percentile(nets, 90),
        "win_rate": win_rate(nets),
        "profit_factor": profit_factor(nets),
        "max_win": max(nets),
        "max_loss": min(nets),
    }


def _concentration(blocked_nets: list[float], delta_clp: float) -> dict:
    """How much of a rung's delta_clp is explained by just its 5 most
    negative and 5 most positive BLOCKED trades. delta_clp = -sum(blocked)
    by construction (blocking removes exactly those trades from the net), so
    these fractions are a direct readout of concentration."""
    most_negative = sorted(blocked_nets)[:5]
    most_positive = sorted(blocked_nets, reverse=True)[:5]
    sum_neg = sum(most_negative)
    sum_pos = sum(most_positive)
    return {
        "n_available": len(blocked_nets),
        "top5_most_negative_sum": sum_neg,
        "top5_most_positive_sum": sum_pos,
        "top5_most_negative_frac_of_delta": (sum_neg / delta_clp) if delta_clp else None,
        "top5_most_positive_frac_of_delta": (sum_pos / delta_clp) if delta_clp else None,
    }


# =========================================================================
# M3 -- blocked vs kept distribution profile
# =========================================================================
def blocked_vs_kept(rows: list[Position], reopens: list[dt.datetime],
                     rungs: list[int] = RUNGS) -> dict:
    """For each group and rung: the full distribution profile of the
    BLOCKED set and the KEPT set separately, plus a concentration readout
    of the blocked set. "Blocked" is exactly is_blocked(bars_since_reopen(
    t_in, reopens), n) -- identical to Task 16, never redefined."""
    groups = _groups(rows)
    bars_of = _bars_of(rows, reopens)

    out: dict = {}
    for key, positions in groups.items():
        baseline_net = sum(p.net_067lot_clp for p in positions)
        rung_out: dict = {}
        for n in rungs:
            blocked = [p for p in positions if is_blocked(bars_of[p], n)]
            kept = [p for p in positions if not is_blocked(bars_of[p], n)]
            blocked_nets = [p.net_067lot_clp for p in blocked]
            kept_nets = [p.net_067lot_clp for p in kept]
            delta_clp = sum(kept_nets) - baseline_net
            rung_out[f"N{n}"] = {
                "blocked": _profile(blocked_nets),
                "kept": _profile(kept_nets),
                "concentration": _concentration(blocked_nets, delta_clp),
            }
        out[key] = rung_out
    return out


# =========================================================================
# main
# =========================================================================
def main() -> int:
    rows = load_positions()
    reopens = market_reopens(load_bar_times())

    m1 = sign_consistency(rows, reopens)
    m2 = topk_sensitivity(rows, reopens)
    m3 = blocked_vs_kept(rows, reopens)

    payload = {
        "n_positions": len(rows),
        "n_reopens": len(reopens),
        "bar_minutes": BAR_MINUTES,
        "rungs_bars": RUNGS,
        "topk_values": list(TOPK_VALUES),
        "m1_sign_consistency_by_month": m1,
        "m2_topk_sensitivity": m2,
        "m3_blocked_vs_kept_profile": m3,
        "caveat": (
            "All three checks are IN-SAMPLE over the same 7 months used to "
            "build the original b1_wait_window.json curve (Task 16). "
            "Surviving these checks means the curve's shape is not an "
            "artifact of a few large trades or of a single lucky month "
            "within this substrate -- it does NOT mean the curve, or any "
            "rung on it, will hold out of sample. This module does not "
            "recommend a rung to deploy; the B1 mask verdict is "
            "pre-committed at 50 minutes in b6_masks.py and does not move "
            "because of anything here."
        ),
    }
    path = write_artifact("b1_robustness.json", payload)
    print(f"wrote {path}")

    print("\nM1 sign consistency (COMBINED):")
    for n in RUNGS:
        r = m1["COMBINED"][f"N{n}"]
        print(f"  N{n}: {r['n_months_positive']}/{r['n_months_total']} months positive, "
              f"{r['n_months_negative']} negative, {r['n_months_zero']} zero")

    print("\nM2 top-K sensitivity, GLOBAL trim, COMBINED ranking:")
    for k in TOPK_VALUES:
        ranking = m2["global"][f"K{k}"]["ranking"]["COMBINED"]
        best = ranking[0]
        print(f"  K={k}: best={best['rung']} ({best['delta_pct']:+.2f}%), "
              f"full order={[r['rung'] for r in ranking]}")

    print("\nM3 blocked vs kept, COMBINED, N3:")
    n3 = m3["COMBINED"]["N3"]
    print(f"  blocked: n={n3['blocked']['n']} mean={n3['blocked']['mean_clp']:,.0f} "
          f"median={n3['blocked']['median_clp']:,.0f} WR={n3['blocked']['win_rate']:.2f}")
    print(f"  kept:    n={n3['kept']['n']} mean={n3['kept']['mean_clp']:,.0f} "
          f"median={n3['kept']['median_clp']:,.0f} WR={n3['kept']['win_rate']:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
