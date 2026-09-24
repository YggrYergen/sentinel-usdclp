"""scripts/report/gen_variant_batch5.py -- Batch 5 (FINAL) of the EMASAR
variant research program: V-06c (ac_modulate_factor knee sweep, zero-code),
V-10 (SuperTrend-M15 regime filter, harness + small engine hook), V-13
(controlled re-entry after full trail-out, engine extension), V-15
(volatility-adaptive SAR, engine extension).

V-10/V-13/V-15 add `direction_mask`, `reentry_enable`/`reentry_max`,
`sar_adaptive`/`sar_fast`/`sar_slow`/`vol_regime_window` to
`sentinel_engine.strategies.emasar_variant.simular_variant` (see that
module's docstring). All default to the pre-batch-5 behavior EXACTLY
(`direction_mask=None`, `reentry_enable=False`, `sar_adaptive=False`) --
pinned by `tests/strategies/test_emasar_variant.py` (45/45 pass, extended
from batch 4's 31 with 14 new tests).

Reuses (does NOT modify) `scripts/report/gen_variant_batch1.py`'s
load/fill/persistence conventions (BID lake bars, spread 0.5 applied at
fill, ResearchRegistry idempotent delete-before-insert per run_id). See that
module's docstring + `docs/superpowers/research/
2026-07-13-emasar-variants-batch{1,2,3,4}.md` for baselines and conventions.

WINDOW: 2026-06-08 -> 2026-07-07 (bars from the lake; warmup starts
2026-06-01). TFs: M1, M2, M5, M15.

PROGRAM "CHAMPION CONFIG" (batch 4's ac_modulate_factor=0.25 finding
subsumed into the config used for stacking legs THIS batch per the task
spec's literal instruction, which freezes the champion at factor=0.25 --
NOTE: the task brief's own CHAMPION block says factor=0.25 nets are
V-06b's, i.e. THIS is the champion baseline for batch 5): per-TF
`init_sl_range_k` = M1 6.0 / M2 3.0 / M5 6.0 / M15 2.5, `ac_modulate=True`,
`ac_modulate_factor=0.25`. Champion nets (batch 4's V-06b winners): M1
-18,819.0 * M2 28,901.4 * M5 45,059.7 * M15 40,897.2.

Each of V-10/V-13/V-15 is run in BOTH legs per the task spec:
  (a) "base" -- V-09 control params (init_sl_range_k=1.0, flat 100/100/100
      trail, no ac_modulate).
  (b) "stacked" -- the CHAMPION config (per-TF k, ac_modulate=True,
      factor=0.25) plus this variant's own new lever on top.

Only the overall-best combo PER VARIANT PER TF (across base+stacked,
whichever scored higher net) is ingested into data/research.db, as
sim-report-emasar-v06c-<tf> / v10 / v13 / v15.

Run this script directly: `python scripts/report/gen_variant_batch5.py`.
Idempotent: re-running replaces the same run_ids (delete-before-insert).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies.emasar_ref import _atr_wilder  # noqa: E402
from sentinel_engine.strategies._supertrend_ref import supertrend as _supertrend_batch  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

# Reuse batch1's loader/filler/metrics/ingest machinery directly (same
# importlib pattern batch2/batch3/batch4 used).
import importlib.util as _ilu  # noqa: E402

_b1_spec = _ilu.spec_from_file_location(
    "gen_variant_batch1", ROOT / "scripts" / "report" / "gen_variant_batch1.py"
)
_b1 = _ilu.module_from_spec(_b1_spec)
_b1_spec.loader.exec_module(_b1)  # type: ignore[union-attr]

DB_PATH = ROOT / "data" / "research.db"
TFS = _b1.TFS
V09_PARAMS = _b1.V09_PARAMS
run_variant = _b1.run_variant
compute_metrics = _b1.compute_metrics
ingest_run = _b1.ingest_run
_bars_for = _b1._bars_for

# ---------------------------------------------------------------------------
# Champion config, per TF -- V-01b k stacked with V-06b's factor=0.25 winner
# (batch 4's best-net lever on EVERY TF, per the task brief's CHAMPION block).
# ---------------------------------------------------------------------------
V01B_BEST_K = {"M1": 6.0, "M2": 3.0, "M5": 6.0, "M15": 2.5}
CHAMPION_FACTOR = 0.25


def champion_kwargs(tf: str) -> dict[str, Any]:
    return {
        **V09_PARAMS,
        "init_sl_range_k": V01B_BEST_K[tf],
        "ac_modulate": True,
        "ac_modulate_factor": CHAMPION_FACTOR,
    }


CHAMPION_NET = {"M1": -18819.0, "M2": 28901.4, "M5": 45059.7, "M15": 40897.2}

# ---------------------------------------------------------------------------
# V-09 control params (exact spec, "control leg" for V-10/V-13/V-15).
# ---------------------------------------------------------------------------
V09_CONTROL = dict(V09_PARAMS)


def _run_sweep_leg(
    tf: str,
    base_kwargs: dict[str, Any],
    grid: list[Any],
    kwargs_fn,
    label: str,
    leg: str,
) -> tuple[list[dict[str, Any]], Any, float, dict[str, Any], list[dict[str, Any]]]:
    """Runs one leg (base or stacked) of a sweep grid for one TF. Returns
    (sweep_metrics_rows, best_grid_value, best_net, best_kwargs, best_trades)."""
    sweep_metrics: list[dict[str, Any]] = []
    best_net = None
    best_val = None
    best_kwargs = None
    best_trades = None
    for val in grid:
        kwargs = kwargs_fn(base_kwargs, val)
        trades = run_variant(tf, kwargs)
        m = compute_metrics(trades)
        sweep_metrics.append({"leg": leg, "val": val, **m})
        print(f"[{label}] {tf} leg={leg} val={val}: trades={m['trades']} net={m['net']} "
              f"pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
        if best_net is None or m["net"] > best_net:
            best_net = m["net"]
            best_val = val
            best_kwargs = kwargs
            best_trades = trades
    return sweep_metrics, best_val, best_net, best_kwargs, best_trades


def _run_variant_both_legs(
    tf: str,
    grid: list[Any],
    kwargs_fn,
    label: str,
) -> dict[str, Any]:
    """Runs both the 'base' (V-09 control) and 'stacked' (CHAMPION config)
    legs of a sweep grid, returns combined results plus the single
    overall-best combo (by net) across both legs."""
    base_kwargs = dict(V09_CONTROL)
    stacked_kwargs = champion_kwargs(tf)

    base_sweep, base_best_val, base_best_net, base_best_kwargs, base_best_trades = _run_sweep_leg(
        tf, base_kwargs, grid, kwargs_fn, label, "base",
    )
    stacked_sweep, stacked_best_val, stacked_best_net, stacked_best_kwargs, stacked_best_trades = _run_sweep_leg(
        tf, stacked_kwargs, grid, kwargs_fn, label, "stacked",
    )

    if stacked_best_net > base_best_net:
        overall_leg = "stacked"
        overall_val = stacked_best_val
        overall_net = stacked_best_net
        overall_kwargs = stacked_best_kwargs
        overall_trades = stacked_best_trades
    else:
        overall_leg = "base"
        overall_val = base_best_val
        overall_net = base_best_net
        overall_kwargs = base_best_kwargs
        overall_trades = base_best_trades

    return {
        "base_sweep": base_sweep, "base_best_val": base_best_val, "base_best_net": base_best_net,
        "stacked_sweep": stacked_sweep, "stacked_best_val": stacked_best_val, "stacked_best_net": stacked_best_net,
        "stacking_helps": stacked_best_net > base_best_net,
        "overall_leg": overall_leg, "overall_val": overall_val, "overall_net": overall_net,
        "overall_kwargs": overall_kwargs, "overall_trades": overall_trades,
    }


# ---------------------------------------------------------------------------
# V-06c: ac_modulate_factor knee sweep, on the champion config, all 4 TFs.
# Continues batch 4's V-06b {0.25, 0.35, 0.45} grid downward: {0.10, 0.15, 0.20}.
# ---------------------------------------------------------------------------
V06C_FACTOR_GRID = (0.10, 0.15, 0.20)


# ---------------------------------------------------------------------------
# V-10: SuperTrend-M15 regime filter -- harness computes `direction_mask`.
# ---------------------------------------------------------------------------

def _resample_to_m15(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resample the given bars (any TF) to M15 OHLC buckets by flooring each
    bar's epoch timestamp to the nearest 15-minute boundary. Bars must
    already be sorted ascending by `t` (true of every `_bars_for(tf)` load).
    Returns one dict per M15 bucket: {'t': bucket_start_epoch, 'open',
    'high', 'low', 'close'} in ascending bucket order."""
    buckets: dict[int, dict[str, Any]] = {}
    for b in bars:
        bucket_t = (b["t"] // 900) * 900
        agg = buckets.get(bucket_t)
        if agg is None:
            buckets[bucket_t] = {
                "t": bucket_t, "open": b["open"], "high": b["high"],
                "low": b["low"], "close": b["close"],
            }
        else:
            agg["high"] = max(agg["high"], b["high"])
            agg["low"] = min(agg["low"], b["low"])
            agg["close"] = b["close"]  # bars are chronological -> last write wins
    return [buckets[t] for t in sorted(buckets)]


def compute_direction_mask(bars: list[dict[str, Any]], *, atr_period: int = 14,
                            st_mult: float = 3.0) -> list[int]:
    """V-10: resample `bars` to M15, compute SuperTrend(atr_period, st_mult)
    on the M15 series (Wilder ATR, same `_atr_wilder` helper `emasar_ref`'s
    own SuperTrend F2 exit uses), then map each bar in `bars` to the TREND
    DIRECTION of the PREVIOUS CLOSED M15 bar (no look-ahead: bar i's mask
    uses the last M15 bucket whose bucket START time is strictly before
    bar i's OWN M15 bucket start -- i.e. the previous bucket, since a bucket
    is only "closed" once its own 15 minutes have elapsed, which is
    guaranteed once we're looking at a LATER bucket than it). Returns a
    list the same length as `bars`, one mask value (+1/-1/0) per bar --
    0 for any bar before the first M15 bucket has closed (warmup)."""
    m15 = _resample_to_m15(bars)
    m15_highs = [b["high"] for b in m15]
    m15_lows = [b["low"] for b in m15]
    m15_closes = [b["close"] for b in m15]
    atr = _atr_wilder(m15_highs, m15_lows, m15_closes, atr_period)
    trend, _line = _supertrend_batch(m15_highs, m15_lows, m15_closes,
                                      [a if a is not None else 0.0 for a in atr], st_mult)
    st_valid = [atr[i] is not None for i in range(len(m15))]

    m15_bucket_start = [b["t"] for b in m15]
    # For a given bar's own bucket index k, the "previous CLOSED M15 bar" is
    # bucket k-1 (bucket k itself has not closed yet at any bar inside it --
    # even the LAST bar of bucket k is still inside that still-open bucket).
    mask: list[int] = [0] * len(bars)
    for i, b in enumerate(bars):
        own_bucket_t = (b["t"] // 900) * 900
        # Locate own_bucket_t's index via the sorted bucket-start list.
        k = _bisect_bucket_index(m15_bucket_start, own_bucket_t)
        prev_k = k - 1
        if prev_k < 0 or not st_valid[prev_k] or trend[prev_k] is None:
            mask[i] = 0
        else:
            mask[i] = trend[prev_k]
    return mask


def _bisect_bucket_index(bucket_starts: list[int], target_t: int) -> int:
    """Exact-match binary search: bucket_starts is sorted ascending, every
    bar's floored bucket_t is guaranteed to be a member of bucket_starts
    (the resample step created a bucket for every bar). Returns the index."""
    lo, hi = 0, len(bucket_starts) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if bucket_starts[mid] == target_t:
            return mid
        if bucket_starts[mid] < target_t:
            lo = mid + 1
        else:
            hi = mid - 1
    raise ValueError(f"bucket_t={target_t} not found in M15 bucket list (resample bug)")


_MASK_CACHE: dict[str, list[int]] = {}


def _mask_for(tf: str) -> list[int]:
    if tf not in _MASK_CACHE:
        _MASK_CACHE[tf] = compute_direction_mask(_bars_for(tf))
    return _MASK_CACHE[tf]


# ---------------------------------------------------------------------------
# V-13: controlled re-entry after full trail-out.
# ---------------------------------------------------------------------------
V13_REENTRY_MAX_GRID = (1, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {"v06c": {}, "v10": {}, "v13": {}, "v15": {}}

    # ===== V-06c: ac_modulate_factor knee sweep on the champion config =====
    v06c_results: dict[str, Any] = {}
    for tf in TFS:
        base_kwargs = champion_kwargs(tf)
        sweep_metrics: list[dict[str, Any]] = []
        best_net = None
        best_factor = None
        best_kwargs = None
        best_trades = None
        for factor in V06C_FACTOR_GRID:
            kwargs = {**base_kwargs, "ac_modulate_factor": factor}
            trades = run_variant(tf, kwargs)
            m = compute_metrics(trades)
            sweep_metrics.append({"factor": factor, **m})
            print(f"[V-06c] {tf} factor={factor}: trades={m['trades']} net={m['net']} "
                  f"pf={m['pf']} wr={m['wr']} maxdd={m['maxdd']}")
            if best_net is None or m["net"] > best_net:
                best_net = m["net"]
                best_factor = factor
                best_kwargs = kwargs
                best_trades = trades

        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v06c-{tf.lower()}",
            variant_id=f"EMS_XAU_V06c_{tf}_c1_f{str(best_factor).replace('.', 'p')}_champion",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs,
                                  "variant": f"V-06c ac_modulate_factor knee sweep on champion, chosen factor={best_factor}"},
            trades_all=best_trades,
            display_name=f"EMASAR V-06c ac_modulate_factor knee sweep, best factor={best_factor} (champion) {tf}",
        )
        v06c_results[tf] = {"sweep": sweep_metrics, "best_factor": best_factor,
                             "champion_net": CHAMPION_NET[tf], "ingested": r}
        print(f"[V-06c] {tf}: BEST factor={best_factor} net={r['net']} "
              f"(champion factor=0.25 net={CHAMPION_NET[tf]}) ingested={r['run_id']}")
    all_results["v06c"] = v06c_results

    # ===== V-10: SuperTrend-M15 regime filter =====
    def v10_kwargs_fn(base: dict[str, Any], val: str) -> dict[str, Any]:
        tf_local = val  # grid carries the TF string so kwargs_fn can look up the mask
        return {**base, "direction_mask": _mask_for(tf_local)}

    v10_results: dict[str, Any] = {}
    for tf in TFS:
        mask = _mask_for(tf)
        n_long = sum(1 for m in mask if m == 1)
        n_short = sum(1 for m in mask if m == -1)
        n_both = sum(1 for m in mask if m == 0)
        print(f"[V-10 diag] {tf}: mask distribution long={n_long} short={n_short} both/warmup={n_both} "
              f"(total={len(mask)})")
        res = _run_variant_both_legs(tf, [tf], v10_kwargs_fn, "V-10")
        json_safe_kwargs = {k: v for k, v in res["overall_kwargs"].items() if k != "direction_mask"}
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v10-{tf.lower()}",
            variant_id=f"EMS_XAU_V10_{tf}_c1_stmask_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**json_safe_kwargs,
                                  "direction_mask": "supertrend_m15_atr14_mult3.0_prev_closed_bar",
                                  "variant": f"V-10 SuperTrend-M15 regime filter, leg={res['overall_leg']}"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-10 SuperTrend-M15 regime filter ({res['overall_leg']}) {tf}",
        )
        v10_results[tf] = {**res, "mask_dist": {"long": n_long, "short": n_short, "both": n_both},
                            "ingested": r}
        print(f"[V-10] {tf}: BEST leg={res['overall_leg']} net={r['net']} "
              f"(base_net={res['base_best_net']}, stacked_net={res['stacked_best_net']}, "
              f"champion_net={CHAMPION_NET[tf]}) ingested={r['run_id']}")
    all_results["v10"] = v10_results

    # ===== V-13: controlled re-entry after full trail-out =====
    def v13_kwargs_fn(base: dict[str, Any], val: int) -> dict[str, Any]:
        return {**base, "reentry_enable": True, "reentry_max": val}

    v13_results: dict[str, Any] = {}
    for tf in TFS:
        res = _run_variant_both_legs(tf, list(V13_REENTRY_MAX_GRID), v13_kwargs_fn, "V-13")
        tag = f"rmax{res['overall_val']}"
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v13-{tf.lower()}",
            variant_id=f"EMS_XAU_V13_{tf}_c1_{tag}_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**res["overall_kwargs"],
                                  "variant": f"V-13 re-entry after full trail-out, reentry_max={res['overall_val']}, "
                                             f"leg={res['overall_leg']}"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-13 re-entry (reentry_max={res['overall_val']}) ({res['overall_leg']}) {tf}",
        )
        v13_results[tf] = {**res, "ingested": r}
        print(f"[V-13] {tf}: BEST reentry_max={res['overall_val']} leg={res['overall_leg']} net={r['net']} "
              f"(base_net={res['base_best_net']}, stacked_net={res['stacked_best_net']}, "
              f"champion_net={CHAMPION_NET[tf]}) ingested={r['run_id']}")
    all_results["v13"] = v13_results

    # ===== V-15: volatility-adaptive SAR =====
    # Mid-flight coordinator addendum (historical sarprobe context, see the
    # report's V-15 section): sarprobe (TOKATA IS screening, 2026-01-02 ->
    # 05-15, 3-pip illegal stop, no spread -- NOT comparable in magnitude to
    # this batch's numbers, only in RANKING/direction) found UNCONDITIONAL
    # fixed SAR 0.005/0.05 beat the trader's original 0.3/0.3 on V1/M5
    # (75tr/net+3276.9/PF4.56 vs 69tr/+1624.6/PF2.82) but LOST on V2/M15
    # (net -2651, PF 0.95) and was mediocre on M1 (PF~1.5). sarprobe never
    # tested a REGIME-SWITCHED combination of the two pairs -- V-15's
    # regime-switching premise has no historical precedent, it is a fresh
    # hypothesis this batch tests directly. To judge V-15 fairly against
    # that precedent, two extra zero-code reference legs are run per TF on
    # the CHAMPION config (fixed, non-adaptive `sar_step`/`sar_max`):
    #   - fixed-fast: sar_step=0.3, sar_max=0.3 (== the champion config
    #     itself, already known as CHAMPION_NET -- no extra run needed).
    #   - fixed-slow: sar_step=0.005, sar_max=0.05 (the sarprobe champion
    #     pair, held FIXED for the whole run, no regime switching).
    # Verdict logic per TF: adaptive must beat BOTH fixed-fast (champion)
    # AND fixed-slow to be declared an outright winner; if fixed-slow alone
    # wins on M5 (replicating sarprobe's M5 finding) that is itself reported
    # as a finding, and whether adaptive avoids fixed-slow's M15/M1 damage
    # while still capturing fixed-slow's M5 gain is the specific hypothesis
    # under test (the whole value proposition of switching vs. picking one
    # pair statically).
    fixed_slow_kwargs_by_tf: dict[str, dict[str, Any]] = {}
    fixed_slow_net_by_tf: dict[str, float] = {}
    for tf in TFS:
        fs_kwargs = {**champion_kwargs(tf), "sar_step": 0.005, "sar_max": 0.05}
        fs_trades = run_variant(tf, fs_kwargs)
        fs_m = compute_metrics(fs_trades)
        fixed_slow_kwargs_by_tf[tf] = fs_kwargs
        fixed_slow_net_by_tf[tf] = fs_m["net"]
        print(f"[V-15 fixed-slow ref] {tf} sar=0.005/0.05 (champion config, non-adaptive): "
              f"trades={fs_m['trades']} net={fs_m['net']} pf={fs_m['pf']} wr={fs_m['wr']} maxdd={fs_m['maxdd']}")

    def v15_kwargs_fn(base: dict[str, Any], val: Any) -> dict[str, Any]:
        return {**base, "sar_adaptive": True, "sar_fast": (0.3, 0.3),
                "sar_slow": (0.005, 0.05), "vol_regime_window": 200}

    v15_results: dict[str, Any] = {}
    for tf in TFS:
        res = _run_variant_both_legs(tf, [None], v15_kwargs_fn, "V-15")
        json_safe_kwargs = {k: (list(v) if isinstance(v, tuple) else v)
                             for k, v in res["overall_kwargs"].items()}
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v15-{tf.lower()}",
            variant_id=f"EMS_XAU_V15_{tf}_c1_adaptivesar_{res['overall_leg']}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**json_safe_kwargs,
                                  "variant": f"V-15 volatility-adaptive SAR (fast=0.3/0.3, slow=0.005/0.05, "
                                             f"window=200), leg={res['overall_leg']}"},
            trades_all=res["overall_trades"],
            display_name=f"EMASAR V-15 volatility-adaptive SAR ({res['overall_leg']}) {tf}",
        )
        fixed_fast_net = CHAMPION_NET[tf]  # fixed-fast IS the champion config itself
        fixed_slow_net = fixed_slow_net_by_tf[tf]
        beats_fixed_fast = r["net"] > fixed_fast_net
        beats_fixed_slow = r["net"] > fixed_slow_net
        v15_results[tf] = {**res, "ingested": r,
                            "fixed_fast_net": fixed_fast_net, "fixed_slow_net": fixed_slow_net,
                            "beats_fixed_fast": beats_fixed_fast, "beats_fixed_slow": beats_fixed_slow,
                            "outright_winner": beats_fixed_fast and beats_fixed_slow}
        print(f"[V-15] {tf}: BEST leg={res['overall_leg']} net={r['net']} "
              f"(base_net={res['base_best_net']}, stacked_net={res['stacked_best_net']}, "
              f"champion/fixed-fast_net={fixed_fast_net}, fixed-slow_net={fixed_slow_net}, "
              f"beats_fixed_fast={beats_fixed_fast}, beats_fixed_slow={beats_fixed_slow}) "
              f"ingested={r['run_id']}")
    all_results["v15"] = v15_results

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
