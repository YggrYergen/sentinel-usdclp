# B1 wait-window curve: how long should the post-reopen gate hold?

**Status: backtest only. Nothing here is deployed.** Every number below is read
back from `data/analysis/monday_audit/b1_wait_window.json`, produced by
`scripts/analysis/monday_audit/b1_wait_curve.py` (tests:
`tests/analysis/test_b1_wait_curve.py`, 11 green).

## This is a separate experiment from the B1 mask verdicts

A different agent is producing the wrapper-mask verdicts in
`docs/superpowers/research/2026-07-25-wrapper-mask-verdicts.md`
(`scripts/analysis/monday_audit/b6_masks.py`). That document's B1 verdict is
**pre-committed at 50 minutes** and does not move because of anything in this
file. This document instead asks a different question: *if* you were to pick
the wait length by looking at the 7-month curve, what would the curve show,
and is there a principled point to pick (an elbow or plateau) or not?

**Searching this curve for a "best" point is tuning.** It is declared,
in writing, as tuning — not as a recommendation. See the caveat repeated at
the end.

## The grid is in bars, not minutes

The user originally proposed a 40/50/60/70-minute grid. That grid is
degenerate: positions enter only on M15 bar boundaries relative to a reopen,
so the *measured* delay from reopen to entry is always exactly one of
{15, 30, 45, 60, 75, 90, …} minutes — never anything in between, and never 0.
A "50-minute wait" and a "60-minute wait" both block exactly the delay set
{15, 30, 45} and are the same experiment wearing two different labels.

The non-degenerate grid is **N = 2, 3, 4, 5, 6 M15 bars**, i.e. waits of
**30 / 45 / 60 / 75 / 90 minutes**. N=1 (a 15-minute wait) is **excluded by
explicit user instruction**, not by this module's choice.

Framed physically: each rung means "wait N M15 bars after reopen for
SAR/EMA/ATR/SuperTrend to clean up before allowing an entry."

## Method

- Reopens are measured off the M15 bar stream via
  `session_clock.market_reopens()` — **145** reopens over the substrate, never
  inferred from the sparse entry stream (an earlier attempt that did that
  invented 415 sessions and produced numbers that measured nothing).
- For each position, `bars_since_reopen(t_in, reopens)` gives the whole number
  of M15 bars between the most recent reopen and that position's entry. Every
  one of the 2347 positions landed on an exact 15-minute multiple after some
  reopen (0 positions were unclassifiable / before the first reopen).
- A wait of N bars **blocks** a position when `bars_since_reopen < N`, and
  **keeps** it otherwise. Blocked positions are simply removed from the net/WR/PF
  computation for that rung — this models "the gate refused to open," not "the
  trade happened later."
- Timestamps are broker server time throughout. No timezone correction was
  applied anywhere in this analysis (none should be — the substrate is already
  fixed at the source).

Baseline (no gate) reproduces the substrate total exactly:
**147,780,084.05 CLP**, n=2347 (S6=912, S7=1167, ST=268).

## The curve — COMBINED

| Rung | Wait | Kept | Blocked | Net CLP | Δ CLP | Δ % | WR % | PF |
|---|---|---|---|---|---|---|---|---|
| baseline | — | 2347 | 0 | 147,780,084 | — | — | 34.43 | 1.138 |
| N2 | 30 min | 2255 | 92 | 167,393,073 | +19,612,988 | **+13.27%** | 34.41 | 1.170 |
| N3 | 45 min | 2188 | 159 | 196,052,707 | +48,272,623 | **+32.67%** | 34.78 | 1.208 |
| N4 | 60 min | 2138 | 209 | 177,357,685 | +29,577,601 | **+20.01%** | 34.89 | 1.192 |
| N5 | 75 min | 2054 | 293 | 162,151,313 | +14,371,229 | **+9.72%** | 35.35 | 1.185 |
| N6 | 90 min | 1985 | 362 | 125,260,724 | −22,519,360 | **−15.24%** | 34.56 | 1.147 |

## The curve — per strategy

**S6-K2P0** (baseline net 93,630,717, n=912) — positive at every rung, peaks at N3, decays afterward, never flips sign:

| Rung | Kept | Blocked | Net CLP | Δ % | WR % | PF |
|---|---|---|---|---|---|---|
| N2 | 876 | 36 | 101,965,830 | +8.90% | 36.30 | 1.246 |
| N3 | 852 | 60 | 125,452,098 | +33.99% | 36.97 | 1.321 |
| N4 | 831 | 81 | 114,622,852 | +22.42% | 36.82 | 1.300 |
| N5 | 798 | 114 | 109,032,228 | +16.45% | 37.59 | 1.301 |
| N6 | 768 | 144 | 96,586,030 | +3.16% | 36.72 | 1.276 |

**S7-TPNONE** (baseline net 33,165,389, n=1167) — flips sign three times and drives almost all of the combined curve's instability:

| Rung | Kept | Blocked | Net CLP | Δ % | WR % | PF |
|---|---|---|---|---|---|---|
| N2 | 1128 | 39 | 27,138,056 | −18.17% | 35.37 | 1.061 |
| N3 | 1095 | 72 | 38,402,129 | +15.79% | 35.62 | 1.090 |
| N4 | 1068 | 99 | 30,059,487 | −9.36% | 35.96 | 1.072 |
| N5 | 1026 | 141 | 30,718,315 | −7.38% | 36.26 | 1.078 |
| N6 | 993 | 174 | 2,228,720 | **−93.28%** | 35.35 | 1.006 |

**SuperTrend-p14x3-M15** (baseline net 20,983,978, n=268) — small n, positive at every rung, but noisy in magnitude:

| Rung | Kept | Blocked | Net CLP | Δ % | WR % | PF |
|---|---|---|---|---|---|---|
| N2 | 251 | 17 | 38,289,186 | +82.47% | 23.51 | 1.295 |
| N3 | 241 | 27 | 32,198,481 | +53.44% | 23.24 | 1.256 |
| N4 | 239 | 29 | 32,675,347 | +55.72% | 23.43 | 1.261 |
| N5 | 230 | 38 | 22,400,771 | +6.75% | 23.48 | 1.186 |
| N6 | 224 | 44 | 26,445,973 | +26.03% | 23.66 | 1.227 |

## Ranking, best to worst (COMBINED, from the artifact's `ranking_best_to_worst`)

1. **N3 (45 min)** — net 196,052,707 CLP, **+32.67%** vs baseline
2. **N4 (60 min)** — net 177,357,685 CLP, +20.01%
3. **N2 (30 min)** — net 167,393,073 CLP, +13.27%
4. **N5 (75 min)** — net 162,151,313 CLP, +9.72%
5. **N6 (90 min)** — net 125,260,724 CLP, **−15.24%** (worse than doing nothing)

🔴 **Caveat, attached to this ranking in the same breath**: this ordering is
computed in-sample, on the same 7 months of positions used to build the curve
itself. It is documentation of what the gate would have done historically —
not a deployment recommendation, and not a claim that N3 will hold out of
sample. It is recorded anyway, in writing, because the alternative is someone
re-deriving this same curve in three months, landing on N=90min or N=15min by
guesswork, getting a materially worse or even sign-flipped number, and having
no record of why.

## Is there an elbow or a plateau? No — it is a hump, and the sign flips.

There is no clean elbow (a point after which returns flatten) and no plateau
(a stable region of similar performance). The combined curve rises from N2 to
a peak at N3, falls at N4 and N5, and goes **negative** at N6:

```
N2 +13.3%  ->  N3 +32.7% (peak)  ->  N4 +20.0%  ->  N5 +9.7%  ->  N6 -15.2%
```

This is a hump/inverted-V shape with the sign flipping at the far end, not a
monotone curve you can read an elbow off of. Waiting *longer is not
monotonically better* — past 45 minutes the marginal minutes give back what
was gained, and past ~75 minutes the combined result is worse than not gating
at all.

**This confirms, on real data, the instability flagged in the task brief from
an earlier minute-threshold prototype** (+13.3% at 30 min, +20.0% at 50/60
min, −15.2% at 90 min). The bar-grid rungs N2/N4/N6 reproduce those exact
figures (+13.27%, +20.01%, −15.24%) almost to the decimal, which is a useful
cross-check that the two independent constructions (minute-threshold vs.
bar-count) agree — and that the sign flip at the long end is real, not an
artifact of how the earlier prototype binned its thresholds.

The per-strategy tables show *why* the combined curve is unstable: S6 and
SuperTrend are positive at every single rung tested (S6 decaying smoothly
after its own peak at N3, SuperTrend noisy but never negative), while
S7-TPNONE is the one that flips sign three times and single-handedly produces
most of the combined swing — its net collapses from 33.2M baseline to 2.2M at
N6 (−93.3%), i.e. blocking the first 75 minutes after every reopen removes
almost all of S7's edge for that day. Whatever is driving S7's profit is
concentrated disproportionately in the bars this gate would block at the long
end of the grid; S6 and ST show no such concentration.

**Bottom line: no clean elbow or plateau. The curve is genuinely noisy, hump-shaped, and sign-flips at long waits — treat any single point on it as in-sample, not as a stable target.**

## Verification

- `python -m pytest tests/analysis/test_b1_wait_curve.py -q` — 11 passed.
- `python -m pytest tests/analysis -q` — 43 passed (full Track-A suite,
  foreground, ~0.6s).
- Every figure in this document was read back from
  `data/analysis/monday_audit/b1_wait_window.json` after it was written by
  `python -m scripts.analysis.monday_audit.b1_wait_curve`; none were
  hand-computed.
