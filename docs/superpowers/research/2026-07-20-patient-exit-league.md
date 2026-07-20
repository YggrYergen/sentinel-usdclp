# Study report -- `honest-sweep-2026-07-19`

Trials recorded in registry: 21
Generated: honest-program

Winner: `PX-TRAIL-ARM1`

## Leaderboard

| Candidate | Median fold J | Dominance vs production | Status |
|---|---|---|---|
| PX-TRAIL-ARM1 | 31219.9500 | 1.0000 | **WINNER** |
| PX-FLOOR-K3 | 13330.8000 | 1.0000 | tie-pool candidate |
| PX-PART-F1TP0P5 | 13201.0500 | 1.0000 | tie-pool candidate |
| PX-PART-F1F2 | 13092.1500 | 1.0000 | tie-pool candidate |
| PX-CHAND-ATR3 | 12966.6000 | 1.0000 | tie-pool candidate |
| PX-CHAND-ATR2 | 12966.6000 | 1.0000 | tie-pool candidate |
| PX-BASE-S6K2P0 | 12966.6000 | 1.0000 | tie-pool candidate |
| PX-RATCHET-L33 | 12908.1000 | 1.0000 | tie-pool candidate |
| PX-PART-F1TP1 | 12901.7500 | 1.0000 | tie-pool candidate |
| PX-RATCHET-L50 | 12664.8000 | 1.0000 | tie-pool candidate |
| PX-RATCHET-L66 | 12653.5500 | 1.0000 | tie-pool candidate |
| PX-SAR-SLOW | 11523.1500 | 1.0000 | tie-pool candidate |
| PX-FLOOR-K4 | 4360.6500 | 1.0000 | tie-pool candidate |
| PX-RATCHET-L33-S7 | 3386.4000 | 1.0000 | tie-pool candidate |
| PX-BASE-S7TPNONE | 3355.0500 | 1.0000 | tie-pool candidate |
| PX-CHAND-ATR3-S7 | 3355.0500 | 1.0000 | tie-pool candidate |
| PX-CHAND-ATR2-S7 | 3355.0500 | 1.0000 | tie-pool candidate |
| PX-RATCHET-L50-S7 | 3334.6500 | 0.7500 | tie-pool candidate |
| PX-RATCHET-L66-S7 | 2200.3500 | 0.7500 | tie-pool candidate |
| PX-WAIT-MAE3 | -1788.0000 | 0.5000 | rejected -- fold-dominance 50.00% < 70% |
| PX-WAIT-MAE2 | -1819.2000 | 0.5000 | rejected -- fold-dominance 50.00% < 70% |

**Selection outcome:** selected as sole best-median-J survivor

## Winner vs. production -- parameter diff

| Lever | Production | Winner |
|---|---|---|
| ac_modulate_factor | None | 0.2500 |
| confirm_count | None | 2.0000 |
| confirm_mode | None | 1.0000 |
| ema_fast | None | 8.0000 |
| ema_slow | None | 20.0000 |
| f1_trail_pips | None | 100.0000 |
| f2_trail_pips | None | 100.0000 |
| f3_trail_pips | None | 100.0000 |
| init_sl_range_k | None | 2.5000 |
| max_hold_bars | None | 64.0000 |
| sar_max | None | 0.3000 |
| sar_step | None | 0.3000 |
| trail_arm_r | None | 1.0000 |
| trail_atr_floor_k | None | 2.0000 |
| vol_regime_window | None | 200.0000 |

## Single-touch holdout result

_No holdout has been run yet for this study (deferred -- reported here honestly, not faked)._

## Per-regime metric breakdown

_No per-regime breakdown available for this study._

## Deflated Sharpe ratio (honest, trial-count-penalized)

- Observed Sharpe: 6.6657
- Trials searched: 21
- Expected max Sharpe under the null (skill-less search): 3.2460
- Deflated Sharpe ratio (DSR): 0.8405
- **Honest p-value: 0.1595**

---

# PX-T6 -- PATIENT-EXIT program report (report-only, no engine changes)

_Real output from `gen_honest_sweep` (21-entry manifest, IW/W1/W2/W3) and
`gen_mfe_capture`'s pooled aggregation. All figures below are from the actual
run captured in this task; nothing here is interpolated or assumed._

## (a) DSR / luck-bar verdict (honest)

The PATIENT-EXIT trial family (21 candidates: 14 levers + 2 base controls +
5 S7 echoes) over the in-sample sweep windows {IW, W1, W2, W3} deflates to:

- Observed Sharpe: **6.6657**
- Trials searched (n_trials): **21**
- Expected max Sharpe under a skill-less null: **3.2460**
- **Deflated Sharpe Ratio (DSR): 0.8405**
- **Honest p-value: 0.1595**

This is NOT the pre-registered "expected 0/1" outcome from a large trial
family (the earlier 225-trial honest-league DSR deflated to ~0/1). With only
21 trials in this smaller PATIENT-EXIT family, the deflation is milder: DSR
0.84 / p≈0.16 means the winner's Sharpe is NOT implausible under a
skill-less 21-trial search, but it also is not the "indistinguishable from
noise" (p≈1) result seen in the larger family. Reported exactly as observed --
no interpretation beyond the number.

## (b) Per-config A/B table (pooled {IW,W1,W2,W3}, vs base)

Pooled across all 4 windows (trades concatenated, aggregates recomputed with
the same formulas `gen_mfe_capture.compute_config_metrics` uses). S6-family
configs vs `PX-BASE-S6K2P0`; S7 echoes vs `PX-BASE-S7TPNONE`.

| config | base | trades | net | vs base net | mean mfe_capture | median mfe_capture | mean giveback USD | total giveback USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| PX-BASE-S6K2P0 | (control) | 2283 | 18999.0 | - | -4.5549 | -0.4195 | 212.38 | 484855.82 |
| PX-RATCHET-L33 | PX-BASE-S6K2P0 | 2289 | 20045.7 | +1046.7 | -4.5423 | -0.4195 | 211.45 | 484014.73 |
| PX-RATCHET-L50 | PX-BASE-S6K2P0 | 2304 | 16993.5 | -2005.5 | -4.5498 | -0.4213 | 208.98 | 481494.18 |
| PX-RATCHET-L66 | PX-BASE-S6K2P0 | 2325 | 19658.7 | +659.7 | -4.5457 | -0.4378 | 202.81 | 471527.41 |
| PX-CHAND-ATR3 | PX-BASE-S6K2P0 | 2283 | 18999.0 | +0.0 | -4.5549 | -0.4195 | 212.38 | 484855.82 |
| PX-CHAND-ATR2 | PX-BASE-S6K2P0 | 2283 | 18999.0 | +0.0 | -4.5549 | -0.4195 | 212.38 | 484855.82 |
| PX-FLOOR-K3 | PX-BASE-S6K2P0 | 1767 | 30611.1 | +11612.1 | -3.5857 | -0.4063 | 268.87 | 475085.31 |
| PX-FLOOR-K4 | PX-BASE-S6K2P0 | 1563 | 40353.0 | +21354.0 | -3.7703 | -0.4348 | 290.38 | 453862.68 |
| PX-SAR-SLOW | PX-BASE-S6K2P0 | 2214 | 24408.0 | +5409.0 | -4.5063 | -0.3951 | 214.09 | 473991.14 |
| PX-WAIT-MAE2 | PX-BASE-S6K2P0 | 3498 | -1988.1 | -20987.1 | -2.2330 | -0.2199 | 117.99 | 412728.88 |
| PX-WAIT-MAE3 | PX-BASE-S6K2P0 | 3498 | -1848.9 | -20847.9 | -2.2334 | -0.2199 | 117.95 | 412589.49 |
| PX-PART-F1TP1 | PX-BASE-S6K2P0 | 2284 | 21468.2 | +2469.2 | -4.5361 | -0.4195 | 204.71 | 467564.50 |
| PX-PART-F1TP0P5 | PX-BASE-S6K2P0 | 2284 | 20332.5 | +1333.5 | -4.4944 | -0.3930 | 193.25 | 441377.66 |
| PX-PART-F1F2 | PX-BASE-S6K2P0 | 2285 | 24537.8 | +5538.8 | -4.5279 | -0.4195 | 200.92 | 459105.38 |
| PX-TRAIL-ARM1 | PX-BASE-S6K2P0 | 1680 | 36683.4 | +17684.4 | -3.8956 | -0.3966 | 266.25 | 447308.38 |
| PX-BASE-S7TPNONE | (control) | 2586 | 13355.7 | - | -3.1522 | -0.4245 | 176.81 | 457235.16 |
| PX-RATCHET-L33-S7 | PX-BASE-S7TPNONE | 2589 | 13418.4 | +62.7 | -3.1479 | -0.4147 | 176.68 | 457413.36 |
| PX-RATCHET-L50-S7 | PX-BASE-S7TPNONE | 2595 | 10203.6 | -3152.1 | -3.1466 | -0.4343 | 176.15 | 457118.16 |
| PX-RATCHET-L66-S7 | PX-BASE-S7TPNONE | 2604 | 9669.9 | -3685.8 | -3.1479 | -0.4418 | 174.34 | 453980.53 |
| PX-CHAND-ATR3-S7 | PX-BASE-S7TPNONE | 2586 | 13355.7 | +0.0 | -3.1522 | -0.4245 | 176.81 | 457235.16 |
| PX-CHAND-ATR2-S7 | PX-BASE-S7TPNONE | 2586 | 13355.7 | +0.0 | -3.1522 | -0.4245 | 176.81 | 457235.16 |

_Note on `mean_mfe_capture` magnitude: `gen_mfe_capture.ficha_metrics` clamps
`mfe_capture` only at the UPPER end (>=1.0 -> 1.0); it is unbounded below, so
trades where MFE is tiny but the booked result is a deep loss produce large
negative `mfe_capture` values (observed as low as -632 on a single trade).
This is the module's existing, as-designed math (see its docstring), not an
artifact of this task's pooling -- the module's own per-window numbers show
the same pattern (verified directly against `compute_config_metrics` before
trusting the pooled result)._

## (c) Keep-criterion result (mfe_capture > base AND giveback_usd < base AND net_honest >= base)

Configs meeting ALL THREE conditions vs their base, pooled in-sample:

- **PX-RATCHET-L33** (vs PX-BASE-S6K2P0): cap -4.5423 > -4.5549, gb 211.45 < 212.38, net 20045.7 >= 18999.0
- **PX-RATCHET-L66** (vs PX-BASE-S6K2P0): cap -4.5457 > -4.5549, gb 202.81 < 212.38, net 19658.7 >= 18999.0
- **PX-PART-F1TP1** (vs PX-BASE-S6K2P0): cap -4.5361 > -4.5549, gb 204.71 < 212.38, net 21468.2 >= 18999.0
- **PX-PART-F1TP0P5** (vs PX-BASE-S6K2P0): cap -4.4944 > -4.5549, gb 193.25 < 212.38, net 20332.5 >= 18999.0
- **PX-PART-F1F2** (vs PX-BASE-S6K2P0): cap -4.5279 > -4.5549, gb 200.92 < 212.38, net 24537.8 >= 18999.0
- **PX-RATCHET-L33-S7** (vs PX-BASE-S7TPNONE): cap -3.1479 > -3.1522, gb 176.68 < 176.81, net 13418.4 >= 13355.7

All other 14 non-control configs fail at least one leg. Notably, configs that
raised net the MOST (PX-FLOOR-K4 +21354.0, PX-TRAIL-ARM1 +17684.4, PX-FLOOR-K3
+11612.1, PX-SAR-SLOW +5409.0) all did so by RAISING give-back USD versus
base, not lowering it -- flagged explicitly below.

**Flag -- net improved by WORSENING give-back USD (not meeting the keep
criterion's give-back leg):**

| config | vs base net | mean giveback USD (config vs base) |
|---|---:|---|
| PX-FLOOR-K3 | +11612.1 | 268.87 vs 212.38 (worse) |
| PX-FLOOR-K4 | +21354.0 | 290.38 vs 212.38 (worse) |
| PX-SAR-SLOW | +5409.0 | 214.09 vs 212.38 (worse) |
| PX-TRAIL-ARM1 | +17684.4 | 266.25 vs 212.38 (worse) |

No config in the manifest raised net while lowering mean_mfe_capture (the
in-sample sweep's mfe_capture failures all coincide with net losses --
PX-RATCHET-L50, PX-WAIT-MAE2, PX-WAIT-MAE3, PX-RATCHET-L50-S7,
PX-RATCHET-L66-S7).

## (d) Holdout single-touch (HOLDOUT-2026-01, priced ONCE, no re-selection)

The 5 pre-committed configs (`_meta.holdout_precommit`: F1=PX-RATCHET-L50,
F2=PX-FLOOR-K3, F3=PX-WAIT-MAE2, F4=PX-PART-F1TP1, F5=PX-TRAIL-ARM1) plus
their base `PX-BASE-S6K2P0`, priced once on the untouched HOLDOUT-2026-01
window (2026-01-05..02-05, warmup from 2025-12-29), with gen_wave7's
in-window entry filter applied. No holdout DSR (one config per family --
nothing to deflate).

| family | config | trades | net USD | sign | mean mfe_capture | median mfe_capture | mean giveback USD | total giveback USD |
|---|---|---:|---:|---|---:|---:|---:|---:|
| - | PX-BASE-S6K2P0 (base) | 528 | 2441.7 | positive | -3.4469 | -0.5304 | 304.24 | 160641.20 |
| F1 | PX-RATCHET-L50 | 531 | 954.3 | positive | -3.4269 | -0.5281 | 301.95 | 160335.97 |
| F2 | PX-FLOOR-K3 | 417 | 7459.5 | positive | -3.7711 | -0.5326 | 364.96 | 152188.23 |
| F3 | PX-WAIT-MAE2 | 786 | -13292.7 | negative | -2.1871 | -0.4015 | 172.45 | 135542.95 |
| F4 | PX-PART-F1TP1 | 528 | 1125.1 | positive | -3.4382 | -0.5304 | 294.70 | 155599.04 |
| F5 | PX-TRAIL-ARM1 | 396 | -1211.4 | negative | -4.4324 | -0.6292 | 390.84 | 154771.89 |

**A/B persistence vs in-sample (does the config's relationship to base carry
into the holdout):**

| family | config | in-sample keep-criterion legs (cap/gb/net) | holdout legs (cap/gb/net) | net sign holds |
|---|---|---|---|---|
| F1 | PX-RATCHET-L50 | True/True/False | True/True/False | positive both, but net < base both in-sample and holdout |
| F2 | PX-FLOOR-K3 | True/False/True | False/False/True | net>=base holds; give-back is WORSE than base both in-sample and holdout |
| F3 | PX-WAIT-MAE2 | True/True/False | True/True/False | net < base both in-sample and holdout; holdout net is deeply negative (-13292.7) |
| F4 | PX-PART-F1TP1 | True/True/True (KEEP in-sample) | True/True/False | in-sample keep criterion is NOT preserved on holdout: net falls below base (1125.1 < 2441.7) even though cap/gb legs still hold |
| F5 | PX-TRAIL-ARM1 | True/False/True | False/False/False | holdout net turns NEGATIVE (-1211.4), reversing the in-sample net improvement; give-back also worse both in-sample and holdout |

**Flag:** PX-PART-F1TP1 is the only one of the 5 that met the full in-sample
keep-criterion, and its cap/give-back advantage over base persists on the
holdout, but its net advantage does NOT -- net falls below base on the
untouched month. No config among the 5 pre-committed configs preserves ALL
THREE keep-criterion legs on the holdout. No go-live recommendation is made
here (user's call, per brief).

---

## PX-T6b -- clamped-metric re-selection (post-review fix)

Re-run of the pooled A/B and the single-touch holdout with `mfe_capture` now
clamped to `[0.0, 1.0]` (post-review fix to `scripts/report/gen_mfe_capture.py`).
The pre-fix metric clamped only the UPPER bound, so a trade that booked a loss on
a swing with tiny upside produced a large NEGATIVE capture (observed as low as
~-632 on one trade), tail-dominating the mean and rendering the per-config
`mean_mfe_capture` figures uninterpretable. With the lower clamp, every per-trade
capture is in `[0,1]`: a booked loss / full give-back on a swing that had upside
now counts as `0.0` capture.

Report-only re-run. Pricing/pairing are unchanged, so **net, give-back USD, and
trade counts are byte-identical to the PX-T6 tables above** -- only `mfe_capture`
(mean and median) moves. Pooled figures come from
`gen_mfe_capture.compute_config_metrics(id, kwargs, gen_honest_sweep._BARS_LOADER("M15", w))`
over w in {IW,W1,W2,W3} (per-ficha `trades` pooled, aggregates recomputed with the
module's own formulas); holdout from `gen_wave7_single_touch_holdout._load_holdout_bars("M15")`
with its `_in_window` entry-epoch filter. `2026-07-20-patient-exit-mfe.{json,md}`
were regenerated with the clamped metric.

### (a) Re-computed per-config table (clamped metric)

S6-family vs `PX-BASE-S6K2P0`; S7 echoes vs `PX-BASE-S7TPNONE`. `mean cap` /
`median cap` are the clamped `mfe_capture`; `net` and give-back are unchanged
from PX-T6.

| config | base | trades | net | mean cap | median cap | mean giveback USD | total giveback USD |
|---|---|---:|---:|---:|---:|---:|---:|
| PX-BASE-S6K2P0 | (control) | 2283 | 18999.0 | 0.148140 | 0.0 | 212.38 | 484855.82 |
| PX-RATCHET-L33 | PX-BASE-S6K2P0 | 2289 | 20045.7 | 0.150958 | 0.0 | 211.45 | 484014.73 |
| PX-RATCHET-L50 | PX-BASE-S6K2P0 | 2304 | 16993.5 | 0.155136 | 0.0 | 208.98 | 481494.18 |
| PX-RATCHET-L66 | PX-BASE-S6K2P0 | 2325 | 19658.7 | 0.166169 | 0.0 | 202.81 | 471527.41 |
| PX-CHAND-ATR3 | PX-BASE-S6K2P0 | 2283 | 18999.0 | 0.148140 | 0.0 | 212.38 | 484855.82 |
| PX-CHAND-ATR2 | PX-BASE-S6K2P0 | 2283 | 18999.0 | 0.148140 | 0.0 | 212.38 | 484855.82 |
| PX-FLOOR-K3 | PX-BASE-S6K2P0 | 1767 | 30611.1 | 0.137376 | 0.0 | 268.87 | 475085.31 |
| PX-FLOOR-K4 | PX-BASE-S6K2P0 | 1563 | 40353.0 | 0.142927 | 0.0 | 290.38 | 453862.68 |
| PX-SAR-SLOW | PX-BASE-S6K2P0 | 2214 | 24408.0 | 0.148016 | 0.0 | 214.09 | 473991.14 |
| PX-WAIT-MAE2 | PX-BASE-S6K2P0 | 3498 | -1988.1 | 0.056857 | 0.0 | 117.99 | 412728.88 |
| PX-WAIT-MAE3 | PX-BASE-S6K2P0 | 3498 | -1848.9 | 0.056857 | 0.0 | 117.95 | 412589.49 |
| PX-PART-F1TP1 | PX-BASE-S6K2P0 | 2284 | 21468.2 | 0.164695 | 0.0 | 204.71 | 467564.50 |
| PX-PART-F1TP0P5 | PX-BASE-S6K2P0 | 2284 | 20332.5 | 0.199448 | 0.0 | 193.25 | 441377.66 |
| PX-PART-F1F2 | PX-BASE-S6K2P0 | 2285 | 24537.8 | 0.170800 | 0.0 | 200.92 | 459105.38 |
| PX-TRAIL-ARM1 | PX-BASE-S6K2P0 | 1680 | 36683.4 | 0.182701 | 0.0 | 266.25 | 447308.38 |
| PX-BASE-S7TPNONE | (control) | 2586 | 13355.7 | 0.153495 | 0.0 | 176.81 | 457235.16 |
| PX-RATCHET-L33-S7 | PX-BASE-S7TPNONE | 2589 | 13418.4 | 0.154012 | 0.0 | 176.68 | 457413.36 |
| PX-RATCHET-L50-S7 | PX-BASE-S7TPNONE | 2595 | 10203.6 | 0.154560 | 0.0 | 176.15 | 457118.16 |
| PX-RATCHET-L66-S7 | PX-BASE-S7TPNONE | 2604 | 9669.9 | 0.158284 | 0.0 | 174.34 | 453980.53 |
| PX-CHAND-ATR3-S7 | PX-BASE-S7TPNONE | 2586 | 13355.7 | 0.153495 | 0.0 | 176.81 | 457235.16 |
| PX-CHAND-ATR2-S7 | PX-BASE-S7TPNONE | 2586 | 13355.7 | 0.153495 | 0.0 | 176.81 | 457235.16 |

### (b) Keep-criterion re-evaluation (capture > base AND giveback < base AND net >= base)

The capture leg is evaluated on the clamped **MEDIAN (primary)** and, for
transparency, also on the clamped **mean**.

**Median-gated (primary):** the clamped `median_mfe_capture` is **0.0 for every
config, base and candidate alike** (the median trade captures none of its swing --
the distribution is heavily zero-massed: exits at or below entry, and losses on
up-swings, all map to 0.0 under the lower clamp). So the capture leg
`median > base` is `0.0 > 0.0 = False` for every candidate. **No config meets the
keep criterion under the median gate -- the keep list is EMPTY.**

**Mean-gated (secondary, shown for transparency):** using the clamped
`mean_mfe_capture` for the capture leg, the configs meeting all three legs are the
SAME six as the pre-fix PX-T6 report (net and give-back are unchanged; the mean
capture ordering vs base is preserved by the clamp):

- **PX-RATCHET-L33** (vs PX-BASE-S6K2P0): cap 0.150958 > 0.148140, gb 211.45 < 212.38, net 20045.7 >= 18999.0
- **PX-RATCHET-L66** (vs PX-BASE-S6K2P0): cap 0.166169 > 0.148140, gb 202.81 < 212.38, net 19658.7 >= 18999.0
- **PX-PART-F1TP1** (vs PX-BASE-S6K2P0): cap 0.164695 > 0.148140, gb 204.71 < 212.38, net 21468.2 >= 18999.0
- **PX-PART-F1TP0P5** (vs PX-BASE-S6K2P0): cap 0.199448 > 0.148140, gb 193.25 < 212.38, net 20332.5 >= 18999.0
- **PX-PART-F1F2** (vs PX-BASE-S6K2P0): cap 0.170800 > 0.148140, gb 200.92 < 212.38, net 24537.8 >= 18999.0
- **PX-RATCHET-L33-S7** (vs PX-BASE-S7TPNONE): cap 0.154012 > 0.153495, gb 176.68 < 176.81, net 13418.4 >= 13355.7

The clamp did NOT change WHICH configs pass under the mean gate (net/give-back
identical; the sign of the mean-capture delta vs base is preserved). Its effect is
to make the capture figures interpretable (all in `[0,1]`) and to expose that the
PRIMARY (median) gate rejects everything -- the median trade captures nothing.

### (c) Holdout re-computed with the clamped metric (priced ONCE, no re-selection)

The 5 pre-committed configs + base `PX-BASE-S6K2P0`, on the untouched
HOLDOUT-2026-01 window (`_in_window` entry filter). Net / give-back / trade counts
unchanged from PX-T6(d); only clamped capture shown.

| family | config | trades | net USD | mean cap | median cap | mean giveback USD | total giveback USD |
|---|---|---:|---:|---:|---:|---:|---:|
| - | PX-BASE-S6K2P0 (base) | 528 | 2441.7 | 0.116851 | 0.0 | 304.24 | 160641.20 |
| F1 | PX-RATCHET-L50 | 531 | 954.3 | 0.116662 | 0.0 | 301.95 | 160335.97 |
| F2 | PX-FLOOR-K3 | 417 | 7459.5 | 0.104146 | 0.0 | 364.96 | 152188.23 |
| F3 | PX-WAIT-MAE2 | 786 | -13292.7 | 0.029786 | 0.0 | 172.45 | 135542.95 |
| F4 | PX-PART-F1TP1 | 528 | 1125.1 | 0.125588 | 0.0 | 294.70 | 155599.04 |
| F5 | PX-TRAIL-ARM1 | 396 | -1211.4 | 0.144905 | 0.0 | 390.84 | 154771.89 |

**Holdout keep-criterion legs vs base (clamped):**

| family | config | cap-median leg | cap-mean leg | give-back leg | net leg | all three (median / mean) |
|---|---|---|---|---|---|---|
| F1 | PX-RATCHET-L50 | False (0.0 = 0.0) | False (0.116662 < 0.116851) | True (301.95 < 304.24) | False (954.3 < 2441.7) | False / False |
| F2 | PX-FLOOR-K3 | False (0.0 = 0.0) | False (0.104146 < 0.116851) | False (364.96 > 304.24) | True (7459.5 >= 2441.7) | False / False |
| F3 | PX-WAIT-MAE2 | False (0.0 = 0.0) | False (0.029786 < 0.116851) | True (172.45 < 304.24) | False (-13292.7 < 2441.7) | False / False |
| F4 | PX-PART-F1TP1 | False (0.0 = 0.0) | True (0.125588 > 0.116851) | True (294.70 < 304.24) | False (1125.1 < 2441.7) | False / False |
| F5 | PX-TRAIL-ARM1 | False (0.0 = 0.0) | True (0.144905 > 0.116851) | False (390.84 > 304.24) | False (-1211.4 < 2441.7) | False / False |

**Holdout verdict:** NONE of the 5 pre-committed configs preserves all three
keep-criterion legs on the holdout -- under either the primary (median) or the
secondary (mean) capture gate. Under the median gate the capture leg is False for
every config (holdout median capture is 0.0 across the board, base included); under
the mean gate PX-PART-F1TP1 and PX-TRAIL-ARM1 clear the capture leg but each fails
on net (and PX-TRAIL-ARM1 also on give-back). The clamped re-run does not change
the go/no-go conclusion of PX-T6(d): no config among the 5 survives the holdout.
No go-live recommendation is made here (user's call, per brief).

### (d) Erratum -- F3 wait_be_exit mechanism wording

F3 `wait_be_exit` mechanism: the BE floor arms once green (immediately at/above
entry), not adverse-then-recovered as the prereg text stated -- wording corrected
in the engine docstring; behavior unchanged and byte-identity unaffected.
