# B1 wait-curve robustness: does the +32.67% at N3 survive scrutiny?

**Status: backtest only. Nothing here is deployed, and nothing here changes
the B1 mask verdict.** Every number below is read back from
`data/analysis/monday_audit/b1_robustness.json`, produced by
`scripts/analysis/monday_audit/b1_robustness.py` (tests:
`tests/analysis/test_b1_robustness.py`, 14 green).

## The question this answers

Task 16 (`b1_wait_curve.py`, `docs/superpowers/research/2026-07-27-b1-wait-curve.md`)
found a hump-shaped COMBINED curve over the 7-month real-tick substrate
(2347 positions: S6-K2P0 912, S7-TPNONE 1167, SuperTrend-p14x3-M15 268):

| N | wait | blocked | Δ net % | WR % |
|---|---|---|---|---|
| N2 | 30 min | 92 | +13.27% | 34.41 |
| N3 | 45 min | 159 | **+32.67%** | 34.78 |
| N4 | 60 min | 209 | +20.01% | 34.89 |
| N5 | 75 min | 293 | +9.72% | 35.35 |
| N6 | 90 min | 362 | −15.24% | 34.56 |

Win rate moves less than 1 point across the whole grid while net swings 48
points and changes sign at N6. That is compatible with two different
stories the curve alone cannot distinguish: the gate **selects** (blocked
entries are systematically worse) or the gate **shuffles** (blocked entries
are statistically unremarkable and the swing is a few large trades landing
on one side of an arbitrary N). The metric the user fixed for this track is
"net decides, but only if the improvement survives a robustness check" —
this module is that check, built three ways. It answers the question. **It
does not decide anything and it does not move the B1 mask verdict**, which
is pre-committed at 50 minutes in `b6_masks.py`.

"Blocked" here is defined exactly as Task 16 defined it —
`is_blocked(bars_since_reopen(t_in, reopens), n)`, imported, not
reimplemented — so every number below is directly comparable to the curve
above.

## M1 — sign consistency, month by month

For each rung, each of the 7 months (`2026-01`..`2026-07`, the substrate's
own `month` label, not re-derived from `t_in`) gets its own baseline net,
kept net, and delta. A month counts as positive/negative by the sign of
**delta_clp**, never `delta_pct` — see the caveat below on why.

**COMBINED**, months positive/negative out of 7:

| Rung | Positive | Negative | Zero |
|---|---|---|---|
| N2 | 3 | 4 | 0 |
| N3 | **5** | 2 | 0 |
| N4 | 4 | 3 | 0 |
| N5 | 3 | 4 | 0 |
| N6 | 4 | 3 | 0 |

N3 is the only rung that wins outright (5/7 months), and it is the one the
raw curve also ranked first. But 5/7 is not the near-unanimous result the
+32.67% headline number might suggest on its own — 2 of 7 months move the
wrong way even at the best rung, and every other rung is a near coin-flip
(3-4 or 4-3) across the same 7 months.

**COMBINED, N3, month by month** (the full detail — this is what "5/7"
is built from):

| Month | Baseline CLP | Kept CLP | Δ CLP | Δ % | Blocked |
|---|---|---|---|---|---|
| 2026-01 | 87,475,384 | 72,694,427 | −14,780,957 | −16.90% | 17 |
| 2026-02 | 12,048,391 | 76,988,101 | **+64,939,710** | +538.99% | 39 |
| 2026-03 | 30,131,017 | 38,582,835 | +8,451,819 | +28.05% | 43 |
| 2026-04 | −52,022,294 | −40,489,671 | +11,532,623 | −22.17% | 28 |
| 2026-05 | 60,795,997 | 63,588,799 | +2,792,802 | +4.59% | 5 |
| 2026-06 | −3,590,925 | −30,050,702 | **−26,459,777** | +736.85% | 20 |
| 2026-07 | 12,942,514 | 14,738,918 | +1,796,404 | +13.88% | 7 |

🔴 **This table is why sign counting uses `delta_clp`, never `delta_pct`.**
2026-04's baseline is a *loss* of −52.0M; N3 improves it to −40.5M
(`delta_clp` = +11.5M, unambiguously an improvement) but `delta_pct` prints
**−22.17%** because dividing a positive delta by a negative baseline flips
the sign. 2026-06 is the mirror case: baseline is a small −3.6M loss, N3
makes it a much bigger −30.1M loss (`delta_clp` = −26.5M, unambiguously
worse) but `delta_pct` prints **+736.85%**. Anyone reading `delta_pct` alone
off this table would count both months backwards. Also visible here: the
combined +32.67% headline is **not evenly spread** — February alone
contributes +64.9M of the +48.3M combined-year delta, i.e. more than 100% of
the total; several other months are pulling the total down and February is
carrying the average by itself.

**Per-strategy sign counts** (same 7 months, out of 7):

| Rung | S6-K2P0 (pos/neg/zero) | S7-TPNONE (pos/neg/zero) | SuperTrend (pos/neg/zero) |
|---|---|---|---|
| N2 | 2 / 3 / 2 | 2 / 3 / 2 | 6 / 1 / 0 |
| N3 | 3 / 2 / 2 | 4 / 2 / 1 | **6 / 1 / 0** |
| N4 | 3 / 4 / 0 | 4 / 3 / 0 | 6 / 1 / 0 |
| N5 | 5 / 2 / 0 | 3 / 4 / 0 | 4 / 3 / 0 |
| N6 | 5 / 2 / 0 | 4 / 3 / 0 | 4 / 3 / 0 |

SuperTrend is 6/7 positive at every rung through N4 — the strongest, most
consistent per-strategy signal in this whole study, on the smallest sample
(n=268). S6 and S7 are both closer to a coin-flip at every rung, including
N3: S6 is 3/2 (with 2 zero months — months where nothing landed inside the
wait window), S7 is 4/2 (1 zero month). Neither S6 nor S7 individually
shows the kind of month-to-month consistency the COMBINED 5/7 at N3
suggests; SuperTrend does, but it is 27% of the position count.

## M2 — sensitivity to removing the largest trades

Two trims, for K in {1, 3, 5, 10}, tie-broken deterministically by
`(-abs(net), t_in, strategy, ficha)`:

- **GLOBAL**: remove the K positions with the largest `|net|` out of all
  2347, wherever they fall, then recompute COMBINED and each strategy on
  what's left.
- **BY_GROUP**: remove the K positions with the largest `|net|` **within
  each strategy separately** (so 3×K removed total, K per strategy), then
  recompute.

**GLOBAL trim, COMBINED, ranking of rungs by net (best → worst):**

| K | removed | ranking | N3 Δ% |
|---|---|---|---|
| 0 (none) | 0 | N3, N4, N2, N5, N6 | +32.67% |
| 1 | 1 | N3, N4, N2, N5, N6 | +38.90% |
| 3 | 3 | N3, N4, N2, N5, N6 | +47.93% |
| 5 | 5 | N3, N4, N2, N5, N6 | +58.69% |
| 10 | 10 | N3, N5, N4, N2, N6 | +115.65% |

N3 stays **#1 at every K tested, global trim**, including K=10. The ranking
order N3 > N4 > N2 > N5 > N6 is unchanged through K=5; at K=10, N5 swaps
past N4 into 2nd place but N3 keeps the top spot. N3's `delta_pct` actually
*grows* as K increases — expected, since removing the largest winners
shrinks the (positive) baseline denominator faster than it shrinks N3's own
kept-net, and this is exactly the kind of denominator effect M1 already
flagged: **the growing percentage at K=10 is partly an artifact of a
shrinking baseline, not proof the effect is getting stronger.** The COMBINED
baseline net itself drops from 147.8M (K=0) to 41.7M (K=10) — removing 10
of 2347 trades (0.4%) cuts baseline net by 72%, which is its own separate
finding about how concentrated this substrate's profit is in a small number
of large trades.

**BY_GROUP trim, COMBINED, ranking of rungs by net (best → worst):**

| K (per strategy) | removed (total) | ranking | N3 Δ% |
|---|---|---|---|
| 1 | 3 | N3, N4, N2, N5, N6 | +44.16% |
| 3 | 9 | N3, N4, N2, N5, N6 | +85.59% |
| 5 | 15 | N3, N5, N4, N2, N6 | +138.81% |
| 10 | 30 | **N5, N3**, N4, N2, N6 | −97.24% |

🔴 **N3 loses the #1 spot at K=10 per-strategy (30 trades removed out of
2347, 1.3%).** N5 edges ahead with a net of +3.6M vs N3's −1.37M — and by
this point the baseline itself has flipped negative (−49.6M): stripping the
10 largest-|net| trades from *each* of the three strategies pushes the
whole 7-month substrate into a loss before any gate is applied at all. The
ranking at K=10 by-group is between two near-zero, sign-unstable numbers,
not a decisive win for N5; the honest read is that by K=10-per-strategy the
comparison has left the range where these rungs are reliably ordered at
all. At K≤5, both trims agree: N3 is first or tied for first.

## M3 — profile of blocked vs. kept ("selects or shuffles?")

**COMBINED**, full distribution profile per rung:

| Rung | Set | n | mean CLP | median CLP | WR % | PF | max win | max loss |
|---|---|---|---|---|---|---|---|---|
| N2 | blocked | 92 | −213,185 | −406,277 | 34.78 | 0.762 | 4,594,853 | −5,632,664 |
| N2 | kept | 2255 | 74,232 | −267,923 | 34.41 | 1.170 | 23,691,446 | −6,314,080 |
| N3 | blocked | 159 | −303,601 | −454,905 | **29.56** | **0.620** | 5,018,385 | −5,632,664 |
| N3 | kept | 2188 | 89,604 | −262,276 | 34.78 | 1.208 | 23,691,446 | −6,314,080 |
| N4 | blocked | 209 | −141,520 | −428,552 | 29.67 | 0.798 | 5,018,385 | −5,632,664 |
| N4 | kept | 2138 | 82,955 | −260,708 | 34.89 | 1.192 | 23,691,446 | −6,314,080 |
| N5 | blocked | 293 | −49,049 | −454,905 | 27.99 | 0.925 | 8,013,228 | −5,632,664 |
| N5 | kept | 2054 | 78,944 | −257,257 | 35.35 | 1.185 | 23,691,446 | −6,314,080 |
| N6 | blocked | 362 | **+62,208** | −328,159 | 33.70 | **1.104** | 8,013,228 | −5,632,664 |
| N6 | kept | 1985 | 63,104 | −263,531 | 34.56 | 1.147 | 23,691,446 | −6,314,080 |

This is the sharpest signal in the whole study, and it lines up with the
sign flip Task 16 already reported: **at N2–N5, the blocked set is a
consistently worse population than the kept set** — win rate 3-7 points
lower, profit factor below 1.0 (a losing set on its own) vs. kept's
1.17-1.21, and a negative mean where kept is positive. At N3 specifically —
the peak of the curve — the gap is largest: blocked WR 29.56% vs. kept
34.78%, blocked PF 0.620 vs. kept 1.208. **At N6, this flips**: the blocked
set's mean turns positive (+62,208) and its profit factor crosses above 1.0
(1.104), nearly matching the kept set's 1.147. Per-strategy at N3 (the star
rung) the same "selects" pattern holds in all three strategies
independently, not just in the aggregate:

| Strategy | blocked n / mean / WR / PF | kept n / mean / WR / PF |
|---|---|---|
| S6-K2P0 | 60 / −530,356 / 30.00% / 0.486 | 852 / +147,244 / 36.97% / 1.321 |
| S7-TPNONE | 72 / −72,732 / 33.33% / 0.880 | 1095 / +35,070 / 35.62% / 1.090 |
| SuperTrend-p14x3-M15 | 27 / −415,352 / 18.52% / 0.478 | 241 / +133,604 / 23.24% / 1.256 |

**Concentration.** Because the blocked set at each rung is a strict superset
of the previous rung's (`bars_since_reopen < N` only grows with N), the 5
most-negative blocked trades are the *same* 5 trades at N2 through N5 (they
already qualify as blocked at N2), and likewise the 5 most-positive blocked
trades are the same set at N5 and N6:

| Rung | Δ CLP | top-5-most-negative sum | as % of Δ | top-5-most-positive sum | as % of Δ |
|---|---|---|---|---|---|
| N2 | +19,612,988 | −24,509,647 | −125.0% | 22,385,712 | +114.1% |
| N3 | +48,272,623 | −24,509,647 | −50.8% | 23,103,521 | +47.9% |
| N4 | +29,577,601 | −24,509,647 | −82.9% | 23,103,521 | +78.1% |
| N5 | +14,371,229 | −24,509,647 | −170.5% | **38,871,465** | +270.5% |
| N6 | −22,519,360 | −24,509,647 | +108.8% | 38,871,465 | −172.6% |

At every rung, the same fixed 5 worst trades (−24.5M) outweigh Δ by
themselves — meaning the *rest* of the blocked set (87 to 357 other trades,
depending on rung) nets out positive, compensating for those 5. That
compensation is smallest, relatively, at N3 (the 5 worst trades are only
51% of Δ, so the rest of the blocked set is doing comparatively more work
pulling the net down) and largest at N5 (170%, so the rest of the blocked
set at N5 is net strongly positive, offsetting most of those 5 losses).
The most-positive-5 jump from ~22-23M (N2-N4, stable — the same 5 trades)
to **38.9M at N5 and N6**: a new large winner enters the blocked set
between N4 and N5, and it is the single largest visible driver of both N5's
Δ retreating from N4's and N6's Δ going negative — past 75 minutes the
gate starts vetoing trades that were big winners, not just the losers it
was catching at N2-N4. At N6, Δ itself is negative, so both fractions
invert sign relative to the earlier rungs (+108.8% and −172.6%) — a
mechanical consequence of the denominator crossing zero, the same effect
flagged for `delta_pct` in M1, here applied to a fraction instead of a
percentage.

## What this does and does not show

- **N3 is not an artifact of one or two outsized trades.** It survives
  removing the 1, 3, 5, and (for the global trim) 10 largest `|net|` trades
  in the substrate, keeping the #1 rank throughout M2's global variant, and
  through K=5 in the per-strategy variant.
- **N3 does not survive being pushed to an extreme.** Stripping the 10
  largest trades from *each* strategy separately (30 of 2347, 1.3%) is
  enough to both flip the underlying baseline negative and swap N3 out of
  first place. This was not tested at any smaller K, and nothing here
  identifies a boundary between K=5 (N3 first) and K=10 (N3 second) more
  precisely than "somewhere in that range, on this trim style."
  **Not measured**, and left unmeasured deliberately: K=6..9 per-group.
- **The blocked population at N2-N5 is measurably worse than the kept
  population** by every distributional statistic computed (WR, PF, mean,
  and the per-strategy breakdown), not just a headline net figure. This is
  evidence *for* "the gate selects" over "the gate shuffles" in that
  specific range.
- **At N6 the blocked population's own profile flips toward profitable**
  (PF 1.104, positive mean), which is the same mechanism, read from the
  other side, that produces the sign flip in the original curve — waiting
  past 75 minutes starts vetoing large winners along with the losers it was
  catching before.
- **Month-to-month, N3 wins 5 of 7 months** — a majority, not a landslide,
  and the combined-year total is not evenly spread across those 5 winning
  months (February alone is larger than the full-year net delta).
  Per-strategy, only SuperTrend shows a consistent 6/7-month pattern at N3;
  S6 and S7 are both closer to even splits.
- **None of this establishes an out-of-sample claim.** Every number in this
  document, like every number in the original wait-curve, is computed over
  the same 7 months of positions. Surviving a trimmed-population check or a
  month-by-month check inside one sample is a different thing from holding
  up on new data; this document does not claim the latter.
- **This document issues no recommendation.** It does not say N3 should be
  deployed, and the B1 mask verdict (pre-committed at 50 minutes,
  `b6_masks.py`) is unaffected by anything above.

## Deviations from the brief

- None. All three measurements (M1, M2 both trim variants, M3 with
  concentration) were implemented and run exactly as specified. `pandas`/
  `numpy` were not needed and were not used — the percentile function is
  pure `math`/stdlib, tested against a hand-computed vector.

## Verification

- `python -m pytest tests/analysis/test_b1_robustness.py -q` — 14 passed.
- `python -m pytest tests/analysis -q` — 57 passed (43 pre-existing +
  14 new), foreground, ~2.4s.
- Every figure in this document was read back from
  `data/analysis/monday_audit/b1_robustness.json` after it was written by
  `python -m scripts.analysis.monday_audit.b1_robustness`; none were
  hand-computed.
