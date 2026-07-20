# Wave 3 — Sizing / risk re-scoring (P43 / P45 / P46 / P47), honest

Program: *Honest Program — complete the 66*. Branch `alvaro`. Date 2026-07-20.
Scope: the four sizing/risk proposals of the 66-catalog, evaluated **offline** against the
already-persisted honest-screen trade rows (no fresh simulation except where noted). Fidelity
`honest-screen`: `live_fill_mode`, flat-0.5 cost, fixed lot 0.10, comparable windows {IW,W1,W2,W3}.

Base league for comparison: `2026-07-20-honest-league-v2.md` (195 cells, DSR 0.0 / p 1.0; naive
median-J winner the SAR-on-M15 family). Prep facts: `scratchpad/honest66/w3-sizing-feasibility.md`,
`w-align.md`. Re-scoring code: `scratchpad/p43_voltarget.py` (read-only vs `data/research.db` and
`data/lake/XAUUSD/15.parquet`).

---

## Headline

- **P45 (fractional-Kelly) and P47 (risk-parity weights)**, applied as a per-config **constant**
  volume multiplier, are **provably Sharpe- and DSR-invariant** — they cannot change the significance
  verdict of any single config. They are capital-allocation choices, not edge. Their only place where
  they can matter is **portfolio composition** (cross-config netting), which is Wave 4.
- **P43 (vol-target, `volume ∝ 1/ATR14`)** is *trade-varying*, so it genuinely reshapes each config's
  net series and **does** move Sharpe. It is a **real, small improvement**: best M15 net-series Sharpe
  **2.72 → 3.10**, and the whole tie-pool median shifts **−0.064 → +0.022**. **But it does not clear the
  luck bar**: DSR 0.0 / p 1.0 against both the full-family null-max (13.59) and even the narrower
  M15-only null-max (4.03; 3.10 < 4.03). No significance rescue.
- **P46 (escalera, 1 vs 2 vs 3 fichas)** needs fresh simulation; it was partially covered by the
  `active_fichas` F1/F2 grids already in league-v2 (Sweep B) — those were tie-pool-neutral-to-negative.

**Net Wave-3 conclusion:** sizing does not manufacture a statistically significant edge on this data.
It does produce the single best *stacked* candidate so far — **SAR + vol-target on M15** — which is the
#1 config to carry into the Wave-7 single-touch holdout, where out-of-sample survival (not further
in-sample stacking) is the only honest way small improvements "add up".

---

## P43 — vol-targeted sizing (RE-SCORABLE, computed)

**Method.** Because the DSR Sharpe is scale-invariant (`sharpe = mean/std`, verified in
`sentinel_engine/opt/registry.py:deflated_sharpe_ratio`), the sizing constant `k` is irrelevant to the
significance verdict — the entire effect of vol-target on Sharpe is the per-trade **1/ATR14**
reweighting. For each of the 64 M15 tie-pool configs, for each window, every trade's price-diff
`(px_out−px_in)` was reweighted by `1/ATR14(entry)` and summed to a per-window net; the net series
`[IW,W1,W2,W3]` gives the config's vol-target Sharpe.

**ATR14** = Wilder causal ATR over `data/lake/XAUUSD/15.parquet`, joined to each trade by `ts_in`
(same MT5 server clock as the lake). **Disclosed honestly:** this ATR14 is an *independent sizing
definition*, NOT the engine's internal `vol_regime_window=200` warmup — it is a legitimate sizing
overlay, not a reproduction of engine state.

**Validation.** The re-score pipeline reproduces the persisted fixed-lot `sharpe` in the trials DB to
6 decimals for all top configs (e.g. `HON-S1-V15-M15` −0.0596573 both) — the px/side/pnl handling is
correct.

**Results (64 M15 tie-pool configs).**

| | Fixed-lot | Vol-target (P43) |
|---|---|---|
| Best net-series Sharpe | 2.721 (`HON-W2-S6-K2P0-M15-SAR`) | **3.102 (`HON-W2-S7-TP1P0-M15-SAR`)** |
| Median Sharpe (pool) | −0.064 | +0.022 |
| Trial-Sharpe std (pool) | 1.325 | 1.463 |

Vol-target helps by down-weighting high-ATR (noisy) entries. Best config's vol-target window nets:
`[8856, 7951, 4900, 4665]` → Sharpe 3.102.

**Deflated Sharpe under vol-target (best config, n_trials=195):**

| Null family | null-max Sharpe | Observed Sharpe | DSR | honest p |
|---|---|---|---|---|
| Full 195-trial family | 13.587 | 3.102 | 0.000 | 1.000 |
| M15-only sub-family (64) | 4.034 | 3.102 | 0.000 | 1.000 |

Even under the most favourable honest framing (narrowing the family to M15, which *lowers* the bar),
3.10 < 4.03 → still not significant. **Caveat:** post-hoc narrowing of the family to where the winner
lives is itself a mild form of p-hacking; the pre-registered family is the full 195, so 13.59 is the
honest bar. Both are reported for transparency.

## P45 — fractional-Kelly per config (RE-SCORABLE → provably invariant)

Kelly assigns each config a **constant** volume multiplier `c` (from its win-rate / payoff / edge).
A constant `c` scales every trade's pnl → every window-net scales by `c` → the net-series
Sharpe `mean(c·x)/std(c·x) = mean(x)/std(x)` is **unchanged**; skewness and kurtosis are likewise
scale-invariant; and the expected-max-null depends only on the (unchanged) per-trial Sharpe spread.
**Therefore Kelly cannot change any DSR term for a single config** — verified directly against the
`deflated_sharpe_ratio` implementation. Kelly is a capital-allocation / bet-sizing overlay; it changes
absolute net and drawdown proportionally but discovers no edge. Deferred to Wave-4 portfolio sizing.

## P47 — risk-parity allocation (RE-SCORABLE → invariant per config; real only at portfolio level)

Same argument: risk-parity is a per-config **constant** inverse-risk weight → Sharpe/DSR-invariant per
config. It only becomes meaningful as a **portfolio composition** across configs (cross-config netting
of simultaneously-open positions), which consumes stored `ts_in/ts_out/pnl/side` per config and is
offline-computable. → **Wave 4** (P47/P48/P49/P50 portfolio), aligned via `trade.ts_in` per `w-align.md`.

## P46 — escalera 1/2/3 fichas (NEEDS-FRESH-SIM; partially done)

Stored honest trades always open all 3 fichas at fixed 0.10; ficha divergence is exit-management
tiering, not stake count — so a true 1-/2-ficha run cannot be re-scored from existing rows. The
`active_fichas` lever (P46, commit 3afa4a1) added this capability; league-v2 already ran F1/F2 grids
(Sweep B). Outcome: tie-pool-neutral-to-negative (e.g. `HON-W2-S7-TPNONE-M15-F2` median-J 2236 stays
in the tie-pool but below the SAR variants; M2 F1/F2 deeply negative). No escalera lift.

---

## Carry-forward

1. **#1 holdout candidate:** `HON-W2-S7-TP1P0-M15-SAR` **+ vol-target overlay** (best stacked Sharpe
   3.10), alongside the SAR-K2P0 naive-net winner. Decide at Wave-7 single-touch holdout.
2. Wave 4 portfolio composition is where P45/P47 sizing can legitimately act (cross-config netting).
3. Honest discipline reminder: in-sample stacking raises the null-max; only out-of-sample survival
   banks a small edge.
