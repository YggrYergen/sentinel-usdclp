"""
sentinel_engine.opt.levers -- the lever-group map: Fable Sec 2.5's G1-G7
coordinate-descent groups, wired onto REAL `InstrumentConfig` fields (P4
wiring layer, complements `sentinel_engine.opt.search.staged_search`).

Fable Sec 2.5's lever-group table (FABLE5_RESPONSE_SENTINEL_REVAMP.md,
lines 167-181) enumerates levers by INTENT, not by concrete Python field.
Mapping that intent onto the actual `InstrumentConfig` dataclass (which is
considerably smaller than the full "fusion/risk/regime" surface Fable
envisions for the eventual system) requires the judgment calls logged below.
Stage order per Fable Sec 2.5: G4 -> G2/G3 -> G5 -> G1 -> G6 -> G7, then a
final joint polish (not implemented here -- a caller of `search.staged_search`
can re-run a narrow final stage over the union of winning params if desired).

Ambiguity log (this module):
  1. G1 "Indicator params" (Fable: 12 raw levers -- EMA x3, RSI x3, MACD x3,
     BB x2, ATR x1) exceeds the 3-8 dim/fit cap by itself. Split: 6
     highest-signal, SCORE-AFFECTING dims (EMA fast/mid/slow, RSI period,
     MACD fast/slow) go into G1 proper; the remainder (MACD signal, BB
     period/std, ATR period) are folded into "G6" below. `ema_trend` (200)
     is held fixed per Fable's own note ("keep 200 fixed").

     `rsi_overbought`/`rsi_oversold` are DROPPED entirely (not a lever
     anywhere, not just moved out of G1) -- traced (2026-07-08, indicator-
     levers wiring task) and found PROVABLY INERT on the composite technical
     score in BOTH scorer implementations: `calculate_all` writes them only
     into the derived `rsi_signal` column (`sentinel/indicators.py`), which
     is exposed via `get_latest_signals` purely for reporting/telemetry.
     Neither `sentinel_engine.technical._score_rsi` (reads raw `s["rsi"]`
     against hardcoded 70/30/50 thresholds) nor the vectorized fast-path
     `sentinel_engine.opt.fast_replay._vec_score_rsi` (same hardcoded
     70/30/50) ever reads `rsi_signal`/`rsi_overbought`/`rsi_oversold`. A
     study varying these two would burn trials with zero score movement --
     an honest empty lever beats a fake one. `rsi_period` (which DOES change
     the raw RSI value feeding `_score_rsi`) is kept.

     All 6 remaining G1 dims, plus G6's 4 (macd_signal, bb_period, bb_std,
     atr_period), were traced and CONFIRMED score-affecting on both paths:
     `macd_signal` changes the MACD signal line -> `macd_histogram`
     (`macd.macd_diff()`) -> `_score_macd`/`_vec_score_macd`; `bb_period`/
     `bb_std` change `bb_pct` -> `_score_bb`/`_vec_score_bb`; `atr_period`
     changes `atr`, which normalizes `_score_macd`/`_vec_score_macd` (both
     paths call with `normalize_macd=True`/the ATR-aware branch always
     active in the fast path). See `tests/opt/test_indicator_levers.py` for
     the executable proof (per-param score-movement assertions) and the
     mission report's param -> affects-score -> action table.
  2. G6 (this module): Fable's actual G6 ("Fusion & risk": fusion boost cap,
     opposed-pull, neutral-lean, confluence bands, ATR SL/TP multipliers,
     R:R min) has NO matching field anywhere in `InstrumentConfig` -- this
     engine's Phase-1 port never modeled a fusion/risk layer distinct from
     scoring. G6 here is repurposed as "secondary indicator params" (the
     G1 overflow from #1). A real fusion/risk G6 needs new fields added to
     `sentinel_engine/config.py` -- flagged for the file owner; NOT changed
     here per this task's file-ownership rule.
  3. G7 "Regime levers": `InstrumentConfig` has no `regime_overrides` block
     (that's Phase 6 future work). Repurposed here as the `asset_weights`
     simplex (7 dims -- Fable's own G5 sub-item "asset weights (7-8 dims
     simplex)"), split out of G5 to keep G5 within the 3-8 dim cap. Once
     Phase 6 lands real regime deltas, G7 should be rewired to those fields
     directly -- flagged for the file owner.
  4. G2/G3 merged into one stage ("G2_G3_technical_blend"): Fable's G3
     ("which TFs + weights", i.e. TF subset selection) has no toggle field
     in `InstrumentConfig` -- only `technical.tf_weights` (a weight per TF)
     exists. A weight near 0 emulates "removing" a TF, so G3's subset-choice
     intent is folded into G2's simplex search rather than added as a
     separate boolean-toggle group.
  5. `expected_correlations` (7 floats) is intentionally NEVER exposed as a
     lever here -- Fable Sec 2.5 (G5 row) explicitly recommends these
     magnitudes stop being hand-set constants and instead come from a
     rolling empirical estimate (a future ingestion pipeline); treating
     them as search dims here would fight that recommendation.
  6. `data.bars_to_fetch` / `data.timeframes` are left untouched: these are
     structural (which physical Parquet timeframe series get read / how
     many bars), not scoring "levers" -- retuning them risks feed-alignment
     and leakage-adjacent semantics out of scope for a config lever sweep.
  7. Search ranges: G1 uses roughly the Fable-suggested "+-60% of current
     production value" (FABLE5_RESPONSE_SENTINEL_REVAMP.md line 173),
     rounded to clean integers/bounds. G4/G5/G6/G7 ranges are centered on
     the `gold.yaml` production values with generous (2-4x) but sane bounds
     (e.g. thresholds kept within [0, 100], simplex weights kept positive).
     These are starting points for a real study, not tuned/validated here.
  8. Weight renormalization: `composite.weights` (technical + correlation)
     and `technical.tf_weights` (M15/M5/M2/M1) are each constrained to sum
     to 1 in the live scoring math (`engine.py`'s composite formula and
     `technical.py`'s `wscore` sum both assume this). `apply_overrides`
     treats only ONE weight per composite pair as the free search dim (the
     other is `1 - x`, clamped) and renormalizes the 4 TF weights to sum to
     1 after overrides are applied (falls back to an equal 0.25 split in
     the degenerate all-zero-or-negative case).
  9. G7's `asset_weights.*` ParamSpec names are keyed to GOLD's specific
     macro basket (dxy/silver/vix/eurusd/sp500/usdjpy/copper). `usdclp.yaml`
     and `nasdaq.yaml` use entirely different `asset_weights` keys (e.g.
     usdmxn/usdbrl/wti/audusd/usdcnh for usdclp; bitcoin/gold for nasdaq),
     so `LEVER_GROUPS`/`priors_for` as written are GOLD-instrument-scoped
     (matching this task's acceptance test, which only exercises gold).
     `apply_overrides` itself is structurally instrument-agnostic (every
     other param path is generic across `InstrumentConfig`); only G7's
     param names would need a per-instrument variant. Building a per-
     instrument `LEVER_GROUPS` factory is flagged as follow-up work, not
     done here to keep this module's public shape matching the task's
     locked contract (`LEVER_GROUPS: list[LeverGroup]`).
"""
from __future__ import annotations

from typing import Callable, Dict

from sentinel_engine.config import (
    CompositeConfig,
    DataConfig,
    IndicatorConfig,
    InstrumentConfig,
    MacroConfig,
    TechnicalConfig,
    TrackerConfig,
)
from sentinel_engine.opt.search import LeverGroup, ParamSpec

# --- G4: Composite & thresholds (stage order position 1) ------------------
_G4 = LeverGroup(
    name="G4_composite_thresholds",
    params=[
        ParamSpec("composite.weights.technical", 0.20, 0.80),
        ParamSpec("composite.direction_vote_weights.technical", 1, 5, is_int=True),
        ParamSpec("composite.score_alert_threshold", 50.0, 80.0),
        ParamSpec("composite.score_strong_threshold", 60.0, 90.0),
    ],
)

# --- G2/G3: Technical TF blend (stage order position 2) --------------------
_G2_G3 = LeverGroup(
    name="G2_G3_technical_blend",
    params=[
        ParamSpec("technical.tf_weights.M15", 0.05, 0.50),
        ParamSpec("technical.tf_weights.M5", 0.05, 0.50),
        ParamSpec("technical.tf_weights.M2", 0.05, 0.60),
        ParamSpec("technical.tf_weights.M1", 0.05, 0.60),
    ],
)

# --- G5: Macro engine dynamics (stage order position 3) --------------------
_G5 = LeverGroup(
    name="G5_macro_dynamics",
    params=[
        ParamSpec("macro.tanh_sensitivity", 2.0, 10.0),
        ParamSpec("macro.tracker.lambda_var", 0.50, 0.99, log=True),
        ParamSpec("macro.tracker.lambda_cov", 0.80, 0.999, log=True),
        ParamSpec("macro.tracker.concordance_window", 20, 120, is_int=True),
        ParamSpec("macro.warmup_threshold", 10, 60, is_int=True),
        ParamSpec("macro.direction_threshold", 0.05, 0.40),
    ],
)

# --- G1: Indicator params, core (stage order position 4) -------------------
# NOTE: `rsi_overbought`/`rsi_oversold` were DROPPED (see ambiguity #1) --
# provably inert on the composite score in both scorer paths, not merely
# moved to another group. MACD fast<slow is a HARD constraint the real MACD
# math requires (a slow period <= fast period inverts/degenerates the
# indicator); `ParamSpec`/`staged_search` sample each dim independently with
# no cross-param constraint mechanism, so this is enforced downstream in
# `apply_overrides` (swap-if-inverted, see below) rather than by changing
# `search.py`'s sampling -- flagged as the simplest correct fix within this
# module's ownership; a "proper" fix (rejection sampling / a joint
# MACD-pair ParamSpec) would need `search.py`, out of scope here.
_G1 = LeverGroup(
    name="G1_indicator_params",
    params=[
        ParamSpec("technical.indicators.ema_fast", 4, 15, is_int=True),
        ParamSpec("technical.indicators.ema_mid", 8, 34, is_int=True),
        ParamSpec("technical.indicators.ema_slow", 20, 80, is_int=True),
        ParamSpec("technical.indicators.rsi_period", 6, 22, is_int=True),
        ParamSpec("technical.indicators.macd_fast", 5, 19, is_int=True),
        ParamSpec("technical.indicators.macd_slow", 11, 42, is_int=True),
    ],
)

# --- G6: secondary indicator params (fusion/risk substitute, ambiguity #2),
# stage order position 5 -----------------------------------------------------
_G6 = LeverGroup(
    name="G6_indicator_secondary",
    params=[
        ParamSpec("technical.indicators.macd_signal", 4, 14, is_int=True),
        ParamSpec("technical.indicators.bb_period", 8, 32, is_int=True),
        ParamSpec("technical.indicators.bb_std", 1.0, 3.2),
        ParamSpec("technical.indicators.atr_period", 6, 22, is_int=True),
    ],
)

# --- G7: asset weights (regime substitute, ambiguity #3), stage order
# position 6 ------------------------------------------------------------------
_G7 = LeverGroup(
    name="G7_asset_weights",
    params=[
        ParamSpec("asset_weights.dxy", 0.5, 6.0),
        ParamSpec("asset_weights.silver", 0.5, 6.0),
        ParamSpec("asset_weights.vix", 0.2, 4.0),
        ParamSpec("asset_weights.eurusd", 0.3, 4.0),
        ParamSpec("asset_weights.sp500", 0.2, 4.0),
        ParamSpec("asset_weights.usdjpy", 0.3, 4.0),
        ParamSpec("asset_weights.copper", 0.2, 4.0),
    ],
)

#: ordered per Fable Sec 2.5 stage order: G4 -> G2/G3 -> G5 -> G1 -> G6 -> G7
LEVER_GROUPS: list = [_G4, _G2_G3, _G5, _G1, _G6, _G7]

#: flat param-name -> ParamSpec, used for int-rounding + priors lookups.
_ALL_PARAMS: Dict[str, ParamSpec] = {p.name: p for g in LEVER_GROUPS for p in g.params}

#: name -> getter(cfg) -> current value, one entry per `_ALL_PARAMS` key.
_GETTERS: Dict[str, Callable[[InstrumentConfig], float]] = {
    "composite.weights.technical": lambda c: c.composite.weights["technical"],
    "composite.direction_vote_weights.technical": (
        lambda c: c.composite.direction_vote_weights["technical"]
    ),
    "composite.score_alert_threshold": lambda c: c.composite.score_alert_threshold,
    "composite.score_strong_threshold": lambda c: c.composite.score_strong_threshold,
    "technical.tf_weights.M15": lambda c: c.technical.tf_weights["M15"],
    "technical.tf_weights.M5": lambda c: c.technical.tf_weights["M5"],
    "technical.tf_weights.M2": lambda c: c.technical.tf_weights["M2"],
    "technical.tf_weights.M1": lambda c: c.technical.tf_weights["M1"],
    "macro.tanh_sensitivity": lambda c: c.macro.tanh_sensitivity,
    "macro.tracker.lambda_var": lambda c: c.macro.tracker.lambda_var,
    "macro.tracker.lambda_cov": lambda c: c.macro.tracker.lambda_cov,
    "macro.tracker.concordance_window": lambda c: c.macro.tracker.concordance_window,
    "macro.warmup_threshold": lambda c: c.macro.warmup_threshold,
    "macro.direction_threshold": lambda c: c.macro.direction_threshold,
    "technical.indicators.ema_fast": lambda c: c.technical.indicators.ema_fast,
    "technical.indicators.ema_mid": lambda c: c.technical.indicators.ema_mid,
    "technical.indicators.ema_slow": lambda c: c.technical.indicators.ema_slow,
    "technical.indicators.rsi_period": lambda c: c.technical.indicators.rsi_period,
    "technical.indicators.macd_fast": lambda c: c.technical.indicators.macd_fast,
    "technical.indicators.macd_slow": lambda c: c.technical.indicators.macd_slow,
    "technical.indicators.macd_signal": lambda c: c.technical.indicators.macd_signal,
    "technical.indicators.bb_period": lambda c: c.technical.indicators.bb_period,
    "technical.indicators.bb_std": lambda c: c.technical.indicators.bb_std,
    "technical.indicators.atr_period": lambda c: c.technical.indicators.atr_period,
    "asset_weights.dxy": lambda c: c.asset_weights.get("dxy", 0.0),
    "asset_weights.silver": lambda c: c.asset_weights.get("silver", 0.0),
    "asset_weights.vix": lambda c: c.asset_weights.get("vix", 0.0),
    "asset_weights.eurusd": lambda c: c.asset_weights.get("eurusd", 0.0),
    "asset_weights.sp500": lambda c: c.asset_weights.get("sp500", 0.0),
    "asset_weights.usdjpy": lambda c: c.asset_weights.get("usdjpy", 0.0),
    "asset_weights.copper": lambda c: c.asset_weights.get("copper", 0.0),
}

assert set(_GETTERS) == set(_ALL_PARAMS), "levers.py: _GETTERS must cover every ParamSpec exactly"


def _resolve(name: str, params: Dict[str, float], cfg: InstrumentConfig) -> float:
    """Look up `name`'s effective value: the override from `params` if
    present (rounded for int-typed specs), else the current value read
    from `cfg`."""
    if name in params:
        value = float(params[name])
        spec = _ALL_PARAMS[name]
        if spec.is_int:
            value = float(round(value))
        return value
    return float(_GETTERS[name](cfg))


def apply_overrides(cfg: InstrumentConfig, params: Dict[str, float]) -> InstrumentConfig:
    """Return a NEW `InstrumentConfig` (`cfg` is never mutated) with every
    recognized param in `params` applied to its target field. Unrecognized
    param names raise `ValueError` (fail loudly rather than silently
    ignoring a typo'd lever name).

    See the module docstring's ambiguity log (#8) for the renormalization
    rules applied to `composite.weights` and `technical.tf_weights`.
    """
    unknown = sorted(set(params) - set(_ALL_PARAMS))
    if unknown:
        raise ValueError(f"apply_overrides: unknown param name(s): {unknown}")

    def r(name: str) -> float:
        return _resolve(name, params, cfg)

    # --- composite ---
    tech_w = min(max(r("composite.weights.technical"), 0.0), 1.0)
    corr_w = 1.0 - tech_w
    new_composite = CompositeConfig(
        weights={"technical": tech_w, "correlation": corr_w},
        direction_vote_weights={
            "technical": int(round(r("composite.direction_vote_weights.technical"))),
            "macro": cfg.composite.direction_vote_weights["macro"],
        },
        score_alert_threshold=r("composite.score_alert_threshold"),
        score_strong_threshold=r("composite.score_strong_threshold"),
    )

    # --- technical.tf_weights (renormalized simplex) ---
    raw_tf = {
        "M15": r("technical.tf_weights.M15"),
        "M5": r("technical.tf_weights.M5"),
        "M2": r("technical.tf_weights.M2"),
        "M1": r("technical.tf_weights.M1"),
    }
    tf_sum = sum(raw_tf.values())
    if tf_sum <= 0:
        new_tf_weights = {k: 0.25 for k in raw_tf}
    else:
        new_tf_weights = {k: v / tf_sum for k, v in raw_tf.items()}

    # --- technical.indicators ---
    ind = cfg.technical.indicators

    # MACD fast<slow is a hard constraint the indicator math requires (see
    # ambiguity #1 note above _G1): `ParamSpec`/`staged_search` sample
    # macd_fast/macd_slow independently, so an inverted/tied draw is
    # possible. Swap-if-inverted (rather than clamp/reject) keeps both
    # sampled magnitudes in play (just assigned to the correct slot) instead
    # of silently narrowing the search or raising mid-study.
    macd_fast_raw = int(round(r("technical.indicators.macd_fast")))
    macd_slow_raw = int(round(r("technical.indicators.macd_slow")))
    if macd_fast_raw >= macd_slow_raw:
        macd_fast_val, macd_slow_val = macd_slow_raw, macd_fast_raw
        if macd_fast_val == macd_slow_val:
            macd_slow_val = macd_fast_val + 1  # break the tie, still fast < slow
    else:
        macd_fast_val, macd_slow_val = macd_fast_raw, macd_slow_raw

    new_indicators = IndicatorConfig(
        ema_fast=int(round(r("technical.indicators.ema_fast"))),
        ema_mid=int(round(r("technical.indicators.ema_mid"))),
        ema_slow=int(round(r("technical.indicators.ema_slow"))),
        ema_trend=ind.ema_trend,  # held fixed -- Fable: "keep 200 fixed"
        rsi_period=int(round(r("technical.indicators.rsi_period"))),
        rsi_overbought=ind.rsi_overbought,  # dropped as a lever -- provably inert (see ambiguity #1)
        rsi_oversold=ind.rsi_oversold,      # dropped as a lever -- provably inert (see ambiguity #1)
        macd_fast=macd_fast_val,
        macd_slow=macd_slow_val,
        macd_signal=int(round(r("technical.indicators.macd_signal"))),
        bb_period=int(round(r("technical.indicators.bb_period"))),
        bb_std=r("technical.indicators.bb_std"),
        atr_period=int(round(r("technical.indicators.atr_period"))),
    )
    new_technical = TechnicalConfig(tf_weights=new_tf_weights, indicators=new_indicators)

    # --- macro ---
    new_tracker = TrackerConfig(
        lambda_var=r("macro.tracker.lambda_var"),
        lambda_cov=r("macro.tracker.lambda_cov"),
        concordance_window=int(round(r("macro.tracker.concordance_window"))),
    )
    new_macro = MacroConfig(
        tanh_sensitivity=r("macro.tanh_sensitivity"),
        tracker=new_tracker,
        warmup_threshold=int(round(r("macro.warmup_threshold"))),
        direction_threshold=r("macro.direction_threshold"),
    )

    # --- asset_weights (only keys already present in cfg are refreshed;
    # G7's ParamSpec names are gold-specific, see ambiguity #9) ---
    new_asset_weights = dict(cfg.asset_weights)
    for key in list(new_asset_weights):
        name = f"asset_weights.{key}"
        if name in _ALL_PARAMS:
            new_asset_weights[key] = r(name)

    # --- untouched, structural fields -- rebuilt (not reused) so the
    # returned object shares no mutable state with `cfg` ---
    new_data = DataConfig(
        bars_to_fetch=cfg.data.bars_to_fetch,
        timeframes=dict(cfg.data.timeframes),
    )

    return InstrumentConfig(
        instrument=cfg.instrument,
        target=cfg.target,
        symbols=dict(cfg.symbols),
        expected_correlations=dict(cfg.expected_correlations),
        asset_weights=new_asset_weights,
        macro=new_macro,
        technical=new_technical,
        composite=new_composite,
        data=new_data,
    )


def priors_for(cfg: InstrumentConfig) -> Dict[str, Dict[str, float]]:
    """`{group_name: {param_name: current_value}}` read from `cfg` -- one
    entry per `LEVER_GROUPS` group -- used to seed `search.staged_search`'s
    per-stage priors (Fable Sec 2.5: "priors centered on current values")."""
    return {
        group.name: {p.name: float(_GETTERS[p.name](cfg)) for p in group.params}
        for group in LEVER_GROUPS
    }
