# Wave 5 - P34: SuperTrend always-in p14x3-M15 (HONEST port)

_Generated 2026-07-20T13:13:05Z - read-only vs data/research.db._

SuperTrend(atr_period=14, mult=3.0) run **always-in** on M15 across the program's comparable contrast windows, with the same flat-0.5 spread-at-fill cost model and lot 0.10 as every other honest run. Because always-in carries NO stop-loss, `live_fill_mode`'s intrabar-SL honoring is moot; honesty here = flat-0.5 cost at fill + the comparable windows + DSR trial accounting.

## Per-window honest nets

| Window | Bars | Flips | In-window trades | Net (USD) | PF | WR% |
|--------|------|-------|------------------|-----------|----|-----|
| IW | 2452 | 71 | 52 | +600.10 | 1.076 | 34.6 |
| W1 | 2726 | 69 | 47 | +2248.30 | 1.393 | 44.7 |
| W2 | 2644 | 75 | 54 | +352.30 | 1.023 | 33.3 |
| W3 | 2535 | 61 | 48 | +1423.50 | 1.181 | 35.4 |

**Pooled across loaded windows:** 201 in-window trades, net **+4624.20 USD**.

## Net-series Sharpe and DSR (honest trial accounting)

- Pooled per-trade net-series Sharpe (raw, per-trade): **0.0394**.

- Configs evaluated (DSR `n_trials`): **1** (only p14x3). The Deflated Sharpe Ratio requires `n_trials >= 2` (it deflates for the number of configs *searched*); with a single, pre-specified config there is nothing to deflate. **DSR is therefore reported as UNDEFLATED / not meaningful here** -- we do NOT fabricate a trial family to manufacture a p-value. The raw per-trade Sharpe above is the observed statistic; treat it as such, not as a significance claim.

## Comparison to the existing screening row

The single research.db row for this family, `sim-report-supertrend-p14x3-m15` (mode=ro), reports net **447.8** over 51 trades on the IW-ish window 2026-06-08..07-07, fidelity=screening (flat-0.5 at fill, but NOT run through the honest windowed machinery). It is left UNTOUCHED by this script.

This honest IW run yields net **+600.10** over 52 in-window trades (71 flips on 2452 bars). Differences vs the 447.8 screening figure arise from the exact window/warmup framing and the in-window trade filter, not from a different cost model.

## EVIDENCE GAP (mandatory disclosure)

The legendary real-tick headline for this family -- **Net +$17,512, PF 1.49, 206 trades** (sometimes quoted as +$17,510) -- is **NOT reproducible in data/research.db and is NOT validated by this run.** That figure lives in a LEGACY TOKATA ledger (`mt5_ledger.csv`, real MT5 fills, window ~Jan-May 2026), which is OUTSIDE this program's data lake and comparable-window methodology. The lake does not cover that exact tick stream, so the $17.5k number cannot be independently reproduced or deflated here.

What IS honest and reproducible: the per-window nets above, run through the identical flat-0.5 / lot-0.10 / comparable-window pipeline used for every other honest strategy. Those -- not the legacy $17.5k headline -- are this family's honest, comparable evidence. Any use of the $17.5k figure MUST carry this caveat: it is an unverified legacy artifact, not a program-validated result.

## Design notes / loose ends

- Position open at each window's feed-end (never flipped again) is left OPEN and not emitted as a trade -- matches the reference `run_supertrend_always_in` semantics (flip = only exit signal).
- SuperTrend math is the vendored `_supertrend_ref`; ATR is `emasar_ref._atr_wilder`. No indicator code was re-implemented.
- Windows loaded via the existing loaders (`gen_variant_batch1._bars_for` for IW, `gen_oow_validation._bars_for` for W1/W2/W3); no new bar loader was written.

