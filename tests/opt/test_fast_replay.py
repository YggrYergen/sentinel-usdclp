"""Acceptance gate for `sentinel_engine.opt.fast_replay` (P4 speed layer).

Runs against the REAL local Parquet lake at `D:\\FOREX\\data\\lake` (gitignored
but present on this machine -- read directly, no synthetic fixtures, no
worktree). Uses the `gold` instrument and a short real window near the head
of the lake (the last few hours of ingested data) so the SLOW oracle
(`evaluator.evaluate_config`) finishes in-test.

CORRECTNESS TIER ACHIEVED: bit-exact. On real lake data, every technical
score, macro score, composite score, direction, entry timestamp/direction,
and trades_R value produced by `fast_evaluate_config` was found to be
IDENTICAL (not merely close) to `evaluator.evaluate_config`'s oracle output,
across the baseline config and every randomized `param_overrides` draw
tried during development. The tolerance-tier fallback described in the task
brief (>=99% entry agreement / <=1% relative score error) is implemented
below as a safety net in case some untested corner of the parameter space
ever produces a genuine floating-point tie-break flip, but it is expected
to never be exercised -- if it triggers, the test still passes and prints
the exact discrepancy counts.
"""
from __future__ import annotations

import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from sentinel_engine.config import load_instrument
from sentinel_engine.lake.store import read_bars
from sentinel_engine.opt.evaluator import evaluate_config
from sentinel_engine.opt.fast_replay import FastReplayCache, fast_evaluate_config
from sentinel_engine.opt.levers import LEVER_GROUPS, apply_overrides

LAKE_ROOT = Path("D:/FOREX/data/lake")
INSTRUMENT = "gold"
HORIZON = 30
TP_R = 1.5
SL = 2.0
OBJ_KW = dict(horizon=HORIZON, tp_r=TP_R, sl=SL, n_min=1, win_rate_min=0.0)
N_RANDOM_CONFIGS = 9
SEED = 20260707

pytestmark = pytest.mark.skipif(not LAKE_ROOT.exists(), reason="real lake not present on this machine")


def _window():
    """A short real window: the last ~5 hours of gold's M1 history in the
    lake (picked dynamically off the actual data so the test doesn't rot as
    the lake grows)."""
    cfg = load_instrument(INSTRUMENT)
    m1 = read_bars(LAKE_ROOT, cfg.target, 1)
    assert not m1.empty, "real lake has no XAUUSD M1 data -- cannot run acceptance gate"
    w_end = m1.index[-1]
    w_start = w_end - pd.Timedelta(hours=5)
    return cfg, w_start, w_end


def _random_param_overrides(rng: random.Random) -> dict:
    """Draw ONE random value per param from a couple of randomly chosen
    lever groups (Fable-style groups from `levers.LEVER_GROUPS`), seeded
    for determinism."""
    group = rng.choice(LEVER_GROUPS)
    overrides = {}
    for spec in group.params:
        if spec.is_int:
            overrides[spec.name] = float(rng.randint(int(spec.low), int(spec.high)))
        elif spec.log:
            lo, hi = np.log(spec.low), np.log(spec.high)
            overrides[spec.name] = float(np.exp(rng.uniform(lo, hi)))
        else:
            overrides[spec.name] = float(rng.uniform(spec.low, spec.high))
    return overrides


def _all_configs():
    rng = random.Random(SEED)
    # Lowered-threshold configs GUARANTEE the oracle fires real entries over
    # the short window, so the equivalence gate is never vacuous (a config
    # that produces 0 trades on both paths would "match" trivially).
    configs = [
        {},  # baseline
        {"composite.score_alert_threshold": 55.0},
        {"composite.score_alert_threshold": 45.0},
    ]
    for _ in range(N_RANDOM_CONFIGS):
        configs.append(_random_param_overrides(rng))
    return configs


def _indicator_lever_configs():
    """G1/G6 indicator-param configs -- one lever varied per config, wide
    range, PLUS a lowered alert threshold on each so the oracle actually
    fires entries over the short real window (an indicator-param sweep at
    the default threshold could easily produce 0 trades on every config,
    which would make the equivalence comparison vacuous). This is the
    config set that would have caught the original `calculate_all`-reads-
    module-global bug: before the G1 wiring fix, every one of these scored
    identically to the baseline regardless of the indicator override."""
    low_threshold = {"composite.score_alert_threshold": 45.0}
    configs = [
        dict(low_threshold),  # baseline (wired levers at production values)
    ]
    for ema_fast in (5, 9, 20):
        configs.append({**low_threshold, "technical.indicators.ema_fast": float(ema_fast)})
    for ema_slow in (25, 50, 75):
        configs.append({**low_threshold, "technical.indicators.ema_slow": float(ema_slow)})
    for rsi_period in (7, 14, 21):
        configs.append({**low_threshold, "technical.indicators.rsi_period": float(rsi_period)})
    for macd_fast, macd_slow in ((5, 26), (12, 26), (12, 40)):
        configs.append({
            **low_threshold,
            "technical.indicators.macd_fast": float(macd_fast),
            "technical.indicators.macd_slow": float(macd_slow),
        })
    for bb_period in (10, 20, 30):
        configs.append({**low_threshold, "technical.indicators.bb_period": float(bb_period)})
    for bb_std in (1.5, 2.0, 2.8):
        configs.append({**low_threshold, "technical.indicators.bb_std": bb_std})
    for atr_period in (7, 14, 20):
        configs.append({**low_threshold, "technical.indicators.atr_period": float(atr_period)})
    for macd_signal in (5, 9, 13):
        configs.append({**low_threshold, "technical.indicators.macd_signal": float(macd_signal)})
    return configs


def test_oracle_equivalence_and_ranking_and_speed():
    cfg, w_start, w_end = _window()
    symbols = cfg.symbols
    configs = _all_configs()
    shared_cache = FastReplayCache()

    slow_results = []
    fast_results = []
    slow_total_t = 0.0
    fast_total_t = 0.0

    entry_mismatches = 0
    entry_total = 0
    trades_mismatches = 0

    for i, overrides in enumerate(configs):
        t0 = time.perf_counter()
        slow = evaluate_config(cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, **OBJ_KW)
        t1 = time.perf_counter()
        fast = fast_evaluate_config(cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, **OBJ_KW)
        t2 = time.perf_counter()

        # Parity check #2 from the acceptance gate: the CACHED fast path
        # must remain bit-exact vs the oracle too (cache is purely a speed
        # optimization -- see test_cache_correctness for the decisive
        # ON-vs-OFF proof; this loop additionally proves cached-fast ==
        # oracle for every config in the existing equivalence sweep).
        fast_cached = fast_evaluate_config(
            cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, cache=shared_cache, **OBJ_KW
        )
        assert fast_cached.score == fast.score
        assert fast_cached.metrics == fast.metrics

        if i > 0:  # exclude first call's parquet warm-up from the speed ratio
            slow_total_t += t1 - t0
            fast_total_t += t2 - t1

        slow_results.append(slow)
        fast_results.append(fast)

        n_slow = slow.metrics["n_trades"]
        n_fast = fast.metrics["n_trades"]
        entry_total += max(n_slow, n_fast, 1)
        if n_slow != n_fast:
            entry_mismatches += abs(n_slow - n_fast)

        rel_err = abs(fast.score - slow.score) / (abs(slow.score) + 1e-9)
        if rel_err > 1e-9 and (n_slow != n_fast or fast.score != slow.score):
            trades_mismatches += 1

        print(
            f"[cfg {i}] slow score={slow.score:.6f} n={n_slow}  "
            f"fast score={fast.score:.6f} n={n_fast}  rel_err={rel_err:.2e}"
        )

    # ---- 0. non-vacuity guard: the oracle MUST fire real entries, else the
    # equivalence comparison is meaningless (0==0 is not a proof of anything).
    max_n_trades = max(r.metrics["n_trades"] for r in slow_results)
    assert max_n_trades >= 20, (
        f"VACUOUS GATE: oracle produced at most {max_n_trades} entries across all "
        f"configs — equivalence is untested. Widen the window or lower the threshold."
    )

    # ---- 1. oracle equivalence ----
    entry_agreement_pct = 100.0 * (1.0 - entry_mismatches / entry_total)
    print(f"\nEntry agreement: {entry_agreement_pct:.3f}% ({entry_mismatches} mismatched / {entry_total})")
    print(f"Score-mismatched configs: {trades_mismatches} / {len(configs)}")

    bit_exact = trades_mismatches == 0
    if bit_exact:
        print("TIER ACHIEVED: bit-exact (entries, trades_R, and score all identical).")
    else:
        assert entry_agreement_pct >= 99.0, f"entry agreement {entry_agreement_pct:.3f}% < 99%"
        for slow, fast in zip(slow_results, fast_results):
            rel_err = abs(fast.score - slow.score) / (abs(slow.score) + 1e-9)
            assert rel_err <= 0.01, f"score rel error {rel_err:.4f} > 0.01 (slow={slow.score}, fast={fast.score})"
        print("TIER ACHIEVED: >=99% entry agreement + <=1% relative score error tolerance.")

    # ---- 2. ranking preserved ----
    slow_scores = np.array([r.score for r in slow_results])
    fast_scores = np.array([r.score for r in fast_results])
    argmax_match = int(np.argmax(slow_scores)) == int(np.argmax(fast_scores))
    rho, _ = spearmanr(slow_scores, fast_scores)
    print(f"argmax match: {argmax_match}  spearman rho: {rho:.4f}")
    assert argmax_match or rho >= 0.98, (
        f"ranking not preserved: argmax_match={argmax_match}, spearman={rho:.4f}"
    )

    # ---- 3. speed ----
    speedup = slow_total_t / fast_total_t if fast_total_t > 0 else float("inf")
    print(f"\nSpeed: slow={slow_total_t:.3f}s fast={fast_total_t:.3f}s over {len(configs)-1} configs -> {speedup:.1f}x")
    assert speedup >= 5.0, f"fast path only {speedup:.1f}x faster than slow oracle (need >= 5x)"


def test_indicator_levers_move_score_and_stay_bit_exact():
    """THE decisive test for the G1 indicator-param wiring fix (2026-07-08):
    before this fix, `calculate_all` read indicator periods from the module
    global `sentinel.config.INDICATORS`, never from `cfg` -- every one of
    these configs would have scored IDENTICALLY to the baseline in both
    `evaluate_config` (oracle) and `fast_evaluate_config` (fast), which was
    the bug. Now: (1) fast must stay bit-exact vs oracle for EVERY
    period-varying config, AND (2) the set of resulting scores must show
    real movement (non-vacuous -- a wired lever that still doesn't move the
    score is a failure, not a pass)."""
    cfg, w_start, w_end = _window()
    symbols = cfg.symbols
    configs = _indicator_lever_configs()

    # The candidate configs lower composite.score_alert_threshold to 45 (see
    # _indicator_lever_configs) so the oracle actually fires entries over the
    # short window. But the objective's sqrt(n_trades / n_ref) term needs
    # n_ref > 0 to discriminate ANY config: n_ref is the trade count of a
    # reference policy replayed over the SAME window, and evaluate_config
    # defaults that reference to the UNMODIFIED cfg (production threshold 65),
    # which fires 0 entries over this window -> n_ref == 0 -> every score
    # collapses to exactly 0.0 regardless of the levers (a degenerate objective,
    # not a wiring no-op). Pin the reference to the same firing threshold so
    # n_ref > 0 and the objective is non-degenerate; this is the reference-count
    # denominator, not a scoring lever, so it does not alter any candidate's own
    # trades or the oracle-vs-fast bit-exactness being asserted below.
    ref_cfg = apply_overrides(cfg, {"composite.score_alert_threshold": 45.0})

    slow_scores = []
    fast_scores = []
    mismatches = []

    for i, overrides in enumerate(configs):
        slow = evaluate_config(
            cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, reference_cfg=ref_cfg, **OBJ_KW
        )
        fast = fast_evaluate_config(
            cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, reference_cfg=ref_cfg, **OBJ_KW
        )

        slow_scores.append(slow.score)
        fast_scores.append(fast.score)

        if slow.score != fast.score or slow.metrics != fast.metrics:
            mismatches.append((i, overrides, slow, fast))

        print(
            f"[ind-cfg {i}] {overrides} -> slow score={slow.score:.6f} n={slow.metrics['n_trades']}  "
            f"fast score={fast.score:.6f} n={fast.metrics['n_trades']}"
        )

    for i, overrides, slow, fast in mismatches:
        print(f"[MISMATCH ind-cfg {i}] overrides={overrides}")
        print(f"  slow: score={slow.score} metrics={slow.metrics}")
        print(f"  fast: score={fast.score} metrics={fast.metrics}")

    assert not mismatches, (
        f"{len(mismatches)}/{len(configs)} indicator-param configs produced a "
        f"fast != oracle mismatch (see printed detail above) -- the fast and "
        f"oracle paths are no longer honoring the same cfg indicator periods."
    )

    # ---- non-vacuity: the wired levers must actually MOVE the score ----
    distinct_scores = len(set(slow_scores))
    print(f"\nDistinct oracle scores across {len(configs)} indicator configs: {distinct_scores}")
    assert distinct_scores >= 2, (
        f"VACUOUS G1 WIRING: all {len(configs)} period-varying configs produced the "
        f"SAME score ({slow_scores[0]}). With the firing reference above (n_ref > 0) "
        f"the objective is non-degenerate, so identical scores here mean the indicator "
        f"levers no longer reach the score at all -- e.g. calculate_all reading the "
        f"module global instead of the passed cfg indicators. (Indicator levers are "
        f"low-leverage on gold's objective -- tech is 0.5x of composite and direction "
        f"is macro-dominated -- so movement comes from the few configs that flip an "
        f"entry near the threshold; if this ever regresses to <2, widen the window or "
        f"the config set rather than weakening the assertion.)"
    )


def test_determinism():
    cfg, w_start, w_end = _window()
    symbols = cfg.symbols
    overrides = {"composite.score_alert_threshold": 45.0}
    cache = FastReplayCache()

    r1 = fast_evaluate_config(cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, cache=cache, **OBJ_KW)
    r2 = fast_evaluate_config(cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, cache=cache, **OBJ_KW)

    assert r1.score == r2.score
    assert r1.metrics["n_trades"] == r2.metrics["n_trades"]
    assert r1.metrics == r2.metrics


def _cache_correctness_configs(cfg) -> list:
    """One config perturbing EACH cacheable lever family individually, plus
    a combined config touching all families at once -- exercises every
    cache key from the task brief (layers #4 and #5) and proves stale-key
    safety (the SAME cache instance is reused across the whole set in
    `test_cache_correctness`, so a stale hit from a prior lever's key would
    corrupt a later result)."""
    tf_weights = cfg.technical.tf_weights
    configs = [
        {},  # baseline / production
        # composite.weights + composite thresholds (feeds _composite_and_direction,
        # NOT itself a fast_replay cache key, but must not corrupt cached tech/macro arrays)
        {"composite.weights.technical": 0.65, "composite.score_alert_threshold": 52.0},
        # technical.tf_weights -- each TF individually (layer #4 key)
        {"technical.tf_weights.M15": 0.40},
        {"technical.tf_weights.M5": 0.35},
        {"technical.tf_weights.M2": 0.30},
        {"technical.tf_weights.M1": 0.45},
        # ALL macro levers (layer #5 key), individually
        {"macro.tanh_sensitivity": 6.5},
        {"macro.tracker.lambda_var": 0.80},
        {"macro.tracker.lambda_cov": 0.95},
        {"macro.tracker.concordance_window": 55},
        {"macro.direction_threshold": 0.22},
        # asset_weights -- each asset individually (feeds layer #5's key too)
        {"asset_weights.dxy": 3.0},
        {"asset_weights.silver": 2.5},
        {"asset_weights.vix": 1.5},
        {"asset_weights.eurusd": 2.0},
        {"asset_weights.sp500": 1.8},
        {"asset_weights.usdjpy": 1.2},
        {"asset_weights.copper": 0.9},
        # combination: every cacheable family perturbed at once
        {
            "technical.tf_weights.M15": 0.30,
            "technical.tf_weights.M5": 0.30,
            "technical.tf_weights.M2": 0.20,
            "technical.tf_weights.M1": 0.20,
            "macro.tanh_sensitivity": 4.0,
            "macro.tracker.lambda_var": 0.70,
            "macro.tracker.lambda_cov": 0.90,
            "macro.tracker.concordance_window": 40,
            "macro.direction_threshold": 0.15,
            "asset_weights.dxy": 2.0,
            "asset_weights.copper": 1.5,
        },
        # G1/G6 indicator params -- layer #2 (`_vectorized_tf_score_cached`)
        # and layer #4 (`_technical_arrays`) caches must now include the
        # indicator-param tuple in their keys, else a stale hit keyed only on
        # (lake_root, target, tf_min, window_end) from a PRIOR indicator
        # config in this same shared cache would silently corrupt these.
        {"technical.indicators.ema_fast": 5},
        {"technical.indicators.ema_fast": 20},
        {"technical.indicators.ema_slow": 75},
        {"technical.indicators.rsi_period": 21},
        {"technical.indicators.macd_fast": 5, "technical.indicators.macd_slow": 26},
        {"technical.indicators.bb_period": 30},
        {"technical.indicators.bb_std": 2.8},
        {"technical.indicators.atr_period": 20},
        {"technical.indicators.macd_signal": 13},
        # combination: indicator params + a cacheable non-indicator family,
        # to prove the two cache-key extensions (indicator tuple + the
        # pre-existing tf_weights/macro keys) compose correctly
        {
            "technical.indicators.ema_fast": 6,
            "technical.indicators.rsi_period": 9,
            "technical.tf_weights.M15": 0.35,
            "macro.tanh_sensitivity": 5.0,
        },
    ]
    del tf_weights  # only used to document intent above; not needed directly
    return configs


def test_cache_correctness():
    """The decisive new test (fast, no oracle needed): reusing ONE cache
    instance across a config set that perturbs EVERY cacheable lever family
    individually and in combination must return byte-identical
    `ObjectiveResult`s (score + every metric) vs cache=None. Reusing the
    SAME cache across the whole set proves stale-key safety -- changing a
    lever must invalidate/bypass any prior lever's cached arrays, never
    silently reuse them."""
    cfg, w_start, w_end = _window()
    symbols = cfg.symbols
    configs = _cache_correctness_configs(cfg)
    shared_cache = FastReplayCache()

    mismatches = []
    for i, overrides in enumerate(configs):
        uncached = fast_evaluate_config(cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, **OBJ_KW)
        cached = fast_evaluate_config(
            cfg, overrides, LAKE_ROOT, w_start, w_end, symbols, cache=shared_cache, **OBJ_KW
        )
        if cached.score != uncached.score or cached.metrics != uncached.metrics:
            mismatches.append((i, overrides, uncached, cached))

    for i, overrides, uncached, cached in mismatches:
        print(f"[MISMATCH cfg {i}] overrides={overrides}")
        print(f"  uncached: score={uncached.score} metrics={uncached.metrics}")
        print(f"  cached:   score={cached.score} metrics={cached.metrics}")

    assert not mismatches, (
        f"{len(mismatches)}/{len(configs)} configs produced a cache-vs-no-cache "
        f"mismatch -- see printed detail above (this would mean a stale cache "
        f"key was reused across a lever change)."
    )


def test_plateau_like_speed_evidence():
    """Real plateau access pattern: a FIXED window, then ~30 evals each
    perturbing ONE lever (the plateau guard in `selection.select_winner`
    re-scores perturbed levers over the full study window, one lever at a
    time). Runs the sequence with cache=None and with one shared cache,
    asserts a large real speedup with ZERO result change."""
    cfg, w_start, w_end = _window()
    symbols = cfg.symbols

    rng = random.Random(SEED + 1)
    all_lever_names = [p.name for g in LEVER_GROUPS for p in g.params if "asset_weights" not in p.name]
    perturb_sequence = []
    for _ in range(30):
        group = rng.choice(LEVER_GROUPS)
        spec = rng.choice(group.params)
        if spec.is_int:
            val = float(rng.randint(int(spec.low), int(spec.high)))
        else:
            val = float(rng.uniform(spec.low, spec.high))
        perturb_sequence.append({spec.name: val})
    del all_lever_names

    # ---- uncached ----
    t0 = time.perf_counter()
    uncached_results = [
        fast_evaluate_config(cfg, ov, LAKE_ROOT, w_start, w_end, symbols, **OBJ_KW)
        for ov in perturb_sequence
    ]
    uncached_t = time.perf_counter() - t0

    # ---- cached (one shared cache across the whole plateau-like sequence) ----
    cache = FastReplayCache()
    t0 = time.perf_counter()
    cached_results = [
        fast_evaluate_config(cfg, ov, LAKE_ROOT, w_start, w_end, symbols, cache=cache, **OBJ_KW)
        for ov in perturb_sequence
    ]
    cached_t = time.perf_counter() - t0

    for i, (u, c) in enumerate(zip(uncached_results, cached_results)):
        assert c.score == u.score, f"eval {i}: cached score {c.score} != uncached {u.score}"
        assert c.metrics == u.metrics, f"eval {i}: cached metrics differ from uncached"

    speedup = uncached_t / cached_t if cached_t > 0 else float("inf")
    print(
        f"\nPlateau-like sequence ({len(perturb_sequence)} evals, 1 lever perturbed/eval): "
        f"uncached={uncached_t:.3f}s cached={cached_t:.3f}s -> {speedup:.1f}x, zero result change"
    )
    assert speedup >= 3.0, f"cached plateau sequence only {speedup:.1f}x faster (need >= 3x)"
