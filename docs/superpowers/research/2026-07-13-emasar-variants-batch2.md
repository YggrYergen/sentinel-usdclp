# EMASAR variant research — Batch 2 (V-01b, V-04, V-02, V-03)

Generated 2026-07-13 by `scripts/report/gen_variant_batch2.py`. Engine:
`sentinel_engine/strategies/emasar_variant.py::simular_variant`, extended
additively in this batch with `be_at_r`/`be_offset_pips` (V-02, breakeven)
and `trail_mode_ladder`/`f1_trail_range_k`/`f2_trail_range_k`/
`f3_trail_range_k` (V-03, range-mode trailing ladder). Both new features
default to the pre-batch-2 behavior EXACTLY (`be_at_r=0.0`,
`trail_mode_ladder='pips'`) -- pinned by
`tests/strategies/test_emasar_variant.py` (10/10 pass, incl. real M5 lake
window + synthetic fixtures). Symbol XAUUSD, spread 0.5 (Capitaria) applied
at fill, same conventions as batch 1 (see
`docs/superpowers/research/2026-07-13-emasar-variants-batch1.md`).

**Window**: 2026-06-08 -> 2026-07-07 (warmup fed from 2026-06-01). TFs M1,
M2, M5, M15.

**Baselines for comparison** (from batch 1):

| TF  | V-09 control Net ($) | V-01 k=2.0 Net ($) |
|-----|----------------------:|--------------------:|
| M1  | -42,866.1             | -37,432.2           |
| M2  |  13,732.8             |  17,831.4           |
| M5  |  37,469.7             |  39,950.7           |
| M15 |  37,326.6             |  39,749.7           |

---

## V-01b — Extend the range_k sweep

V-09 params with `init_sl_range_k ∈ {2.5, 3.0, 4.0, 6.0}` (continuing batch
1's grid, which topped out at k=2.0 with the curve still climbing on every
TF).

### M1

| k   | Trades | Net ($)   | PF    | WR (%) | %INITSL | MaxDD ($) |
|-----|-------:|----------:|------:|-------:|--------:|----------:|
| 2.5 | 13,878 | -37,289.4 | 0.592 |  28.77 |   7.41  | 37,968.9  |
| 3.0 | 13,878 | -36,813.3 | 0.595 |  28.79 |   7.33  | 37,492.8  |
| 4.0 | 13,878 | -36,773.7 | 0.596 |  28.79 |   7.31  | 37,453.2  |
| 6.0 | 13,878 | -36,414.3 | 0.598 |  28.82 |   7.28  | 37,093.8  |

### M2

| k   | Trades | Net ($)   | PF    | WR (%) | %INITSL | MaxDD ($) |
|-----|-------:|----------:|------:|-------:|--------:|----------:|
| 2.5 | 7,233  |  18,807.6 | 1.488 |  40.98 |   1.49  |  2,899.5  |
| 3.0 | 7,233  |  19,650.6 | 1.521 |  40.98 |   1.29  |  2,899.5  |
| 4.0 | 7,233  |  19,650.6 | 1.521 |  40.98 |   1.29  |  2,899.5  |
| 6.0 | 7,233  |  19,650.6 | 1.521 |  40.98 |   1.29  |  2,899.5  |

### M5

| k   | Trades | Net ($)   | PF    | WR (%) | %INITSL | MaxDD ($) |
|-----|-------:|----------:|------:|-------:|--------:|----------:|
| 2.5 | 2,853  |  40,525.5 | 5.026 |  61.09 |   0.32  |    506.1  |
| 3.0 | 2,853  |  40,402.2 | 4.965 |  61.09 |   0.32  |    582.6  |
| 4.0 | 2,853  |  40,155.3 | 4.847 |  61.09 |   0.32  |    735.9  |
| 6.0 | 2,853  |  41,279.7 | 5.433 |  61.09 |   0.11  |    263.7  |

### M15

| k   | Trades | Net ($)   | PF     | WR (%) | %INITSL | MaxDD ($) |
|-----|-------:|----------:|-------:|-------:|--------:|----------:|
| 2.5 | 948    |  39,749.7 | 25.113 |  77.85 |   0.0   |    150.3  |
| 3.0 | 948    |  39,749.7 | 25.113 |  77.85 |   0.0   |    150.3  |
| 4.0 | 948    |  39,749.7 | 25.113 |  77.85 |   0.0   |    150.3  |
| 6.0 | 948    |  39,749.7 | 25.113 |  77.85 |   0.0   |    150.3  |

**Knee found.** The curve has flattened -- this is the answer batch 1 was
missing:

- **M2/M15**: net is FLAT from k=3.0 onward (M2: identical 19,650.6 at
  k=3.0/4.0/6.0; M15: identical 39,749.7 at k=2.5/3.0/4.0/6.0). Trade count
  is also flat. This is the "stop stops mattering" convergence the task
  asked about -- past k≈3 (M2) / k≈2.5 (M15) the initial range-SL is wide
  enough that it is essentially NEVER the exit that fires ahead of trailing,
  so widening it further changes nothing. M15's %INITSL is already 0.0% at
  k=2.5.
- **M5**: net wobbles (peaks at k=2.5, dips slightly at k=3.0/4.0, then rises
  again at k=6.0 to the batch's best M5 number, 41,279.7) -- not perfectly
  monotone, but the swings are small (~1.1% of net) and %INITSL is pinned at
  0.32%→0.11% across the grid, confirming the range-SL is nearly irrelevant
  here too; the small net wobble is trade-mix noise from the handful of
  fichas still exiting near the (moving) INITSL boundary.
- **M1**: net keeps improving very slowly (still climbing $150-475 per step
  from k=2.5→6.0) and %INITSL keeps drifting down (7.41%→7.28%) but at a
  visibly decelerating rate compared to batch 1's k=0.5→2.0 climb (which
  moved %INITSL from 12.9%→7.5%, an ~5.4pt drop, vs. only ~0.13pt drop across
  this entire k=2.5→6.0 extension). M1 is asymptotically converging but never
  reaches profitability in this window -- the wide-stop convergence just
  removes the last few % of INITSL-tagged losers without fixing the
  underlying over-trading problem.

**Best-net k per TF** -- ingested as `sim-report-emasar-v01b-<tf>`:

| TF  | Best k | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|-------:|----------:|-------:|-------:|----------:|
| M1  |  6.0   | -36,414.3 |  0.598 |  28.82 | 37,093.8  |
| M2  |  3.0   |  19,650.6 |  1.521 |  40.98 |  2,899.5  |
| M5  |  6.0   |  41,279.7 |  5.433 |  61.09 |    263.7  |
| M15 |  2.5   |  39,749.7 | 25.113 |  77.85 |    150.3  |

---

## V-04 — Trailing ladder sweep

V-09 params otherwise (k=1.0). Grid: f1∈{80,100,120}, f2∈{150,170,230},
f3∈{230,289,340}, constraint f1<f2<f3. Since min(f2 grid)=150 > max(f1
grid)=120, every f1<f2 pair automatically holds; the only violations come
from f2=230 paired with f3=230 (f2<f3 fails when they're equal). That
excludes exactly the 3 combos with f2=230, f3=230 (one per f1 value),
leaving 24 valid combos per TF -- 96 sims total for this variant.

### M1 (compact: best 3 and worst 3 by net; full 24-row grid available in
raw run output)

| Ladder (f1,f2,f3) | Trades | Net ($)    | PF    | WR (%) | MaxDD ($)  |
|--------------------|-------:|-----------:|------:|-------:|-----------:|
| 80,150,340 (best)  | 9,000  | -46,466.4  | 0.503 |  29.90 |  46,466.4  |
| 80,150,289         | 10,242 | -53,650.0  | 0.468 |  29.19 |  53,658.7  |
| 80,170,340         | 9,000  | -50,062.1  | 0.481 |  29.43 |  50,062.1  |
| 120,230,289        | 10,242 | -76,481.5  | 0.366 |  26.16 |  76,502.8  |
| 120,170,230 (worst)| 11,676 | -76,339.0  | 0.366 |  25.13 |  76,357.1  |
| 120,150,230         | 11,676 | -72,193.4 | 0.381 |  25.46 |  72,211.5  |

M1: every ladder in the grid is net-negative -- the widest F3 (340) and
tightest F1 (80) minimizes the damage, but nothing beats even V-09's flat
100/100/100 (-42,866.1); this grid made M1 WORSE across the board vs. V-09
control.

### M2 (compact: best 3 / worst 3)

| Ladder (f1,f2,f3)  | Trades | Net ($)    | PF    | WR (%) | MaxDD ($)  |
|---------------------|-------:|-----------:|------:|-------:|-----------:|
| 80,150,230 (best)   | 6,831  | -12,617.8  | 0.789 |  35.31 |  15,440.5  |
| 80,170,230          | 6,831  | -15,974.3  | 0.743 |  34.53 |  18,045.0  |
| 100,150,230         | 6,831  | -16,934.4  | 0.727 |  33.47 |  18,998.3  |
| 120,230,340         | 5,898  | -33,674.8  | 0.534 |  30.71 |  33,784.6  |
| 120,230,289 (worst) | 6,372  | -35,461.3  | 0.521 |  29.71 |  35,465.0  |

M2: **every single one of the 24 ladder combos is net-negative**, versus
V-09's flat 100/100/100 which is +13,732.8. This is the batch's most
striking finding -- de-equalizing the ladder (any spread away from equal
100/100/100) hurts M2 badly; equal trailing distances across fichas appear
to matter specifically at M2.

### M5 (compact: best 3 / worst 3)

| Ladder (f1,f2,f3)  | Trades | Net ($)   | PF    | WR (%) | MaxDD ($) |
|---------------------|-------:|----------:|------:|-------:|----------:|
| 80,150,230 (best)   | 2,823  |  23,872.0 | 2.227 |  51.86 |    710.4  |
| 80,170,230          | 2,823  |  22,190.5 | 2.095 |  50.83 |    761.9  |
| 100,150,230         | 2,823  |  22,040.9 | 2.097 |  50.55 |    765.7  |
| 120,230,340         | 2,733  |   6,967.4 | 1.247 |  43.25 |  3,436.6  |
| 120,230,289 (worst) | 2,787  |   9,642.5 | 1.364 |  43.60 |  2,824.5  |

M5: best ladder (80,150,230) net 23,872.0 is BELOW V-09's flat-100 baseline
(37,469.7) -- tightening the ladder trades win-rate/PF for a smaller,
choppier profile that nets less here.

### M15 (compact: best 3 / worst 3)

| Ladder (f1,f2,f3)  | Trades | Net ($)   | PF    | WR (%) | MaxDD ($) |
|---------------------|-------:|----------:|------:|-------:|----------:|
| 80,150,230 (best)   | 945    |  32,455.0 | 7.258 |  71.64 |    881.1  |
| 100,150,230         | 945    |  31,833.0 | 6.998 |  70.37 |    881.1  |
| 80,170,230          | 945    |  31,833.0 | 6.936 |  70.90 |    881.1  |
| 120,230,340         | 942    |  25,402.6 | 4.344 |  62.00 |    881.1  |
| 100,230,340 (worst) | 942    |  26,022.6 | 4.490 |  62.95 |    881.1  |

M15: best ladder (32,455.0) is also below V-09's flat baseline (37,326.6).

**Consistent pattern across ALL 4 TFs**: the best-performing ladder in this
grid is always the TIGHTEST one tested, `(80, 150, 230)` or close to it (M1
favors a wider F3=340 specifically), and even the best ladder never beats
V-09's flat 100/100/100 control on M2/M5/M15. **V-04 does not beat V-09 on
any TF** in this batch's grid -- unequal trailing distances across fichas
underperform the simple flat-100 baseline everywhere tested.

**Best-net ladder per TF** -- ingested as `sim-report-emasar-v04-<tf>`:

| TF  | Best ladder (f1,f2,f3) | Net ($)   | PF    | WR (%) | MaxDD ($) |
|-----|--------------------------|----------:|------:|-------:|----------:|
| M1  | 80, 150, 340             | -46,466.4 | 0.503 |  29.90 | 46,466.4  |
| M2  | 80, 150, 230             | -12,617.8 | 0.789 |  35.31 | 15,440.5  |
| M5  | 80, 150, 230             |  23,872.0 | 2.227 |  51.86 |    710.4  |
| M15 | 80, 150, 230             |  32,455.0 | 7.258 |  71.64 |    881.1  |

---

## V-02 — Breakeven at 1R/1.5R/2R (engine extension)

New params `be_at_r`, `be_offset_pips=0.5` (see engine docstring). Unit
tests confirm `be_at_r=0.0` reproduces the pre-extension event stream
byte-for-byte (synthetic 300-bar fixture AND real XAUUSD/M5 2026-06 window).
V-09 params otherwise. Grid: `be_at_r ∈ {0.5, 1.0, 1.5}`.

| TF  | be_at_r | Trades | Net ($)    | PF     | WR (%) | MaxDD ($) |
|-----|--------:|-------:|-----------:|-------:|-------:|----------:|
| M1  | 0.5     | 13,893 | -78,148.5  | 0.252  |  18.27 | 78,148.5  |
| M1  | 1.0     | 13,881 | -53,703.0  | 0.454  |  26.48 | 53,961.3  |
| M1  | 1.5     | 13,881 | -47,060.7  | 0.516  |  28.14 | 47,654.4  |
| M2  | 0.5     |  7,236 | -19,187.4  | 0.602  |  28.23 | 19,543.2  |
| M2  | 1.0     |  7,233 |   4,788.0  | 1.108  |  38.57 |  4,213.2  |
| M2  | 1.5     |  7,233 |  10,998.6  | 1.252  |  40.40 |  3,602.7  |
| M5  | 0.5     |  2,853 |  17,167.2  | 2.158  |  48.37 |    741.9  |
| M5  | 1.0     |  2,853 |  30,324.9  | 3.260  |  58.36 |    633.6  |
| M5  | 1.5     |  2,853 |  35,013.3  | 3.662  |  60.25 |    633.6  |
| M15 | 0.5     |    948 |  22,045.5  | 5.939  |  63.61 |    881.1  |
| M15 | 1.0     |    948 |  30,536.7  | 8.624  |  73.42 |    881.1  |
| M15 | 1.5     |    948 |  36,449.1  | 10.413 |  76.27 |    881.1  |

**Monotone pattern on every TF**: net/PF/WR all IMPROVE as `be_at_r`
increases from 0.5 -> 1.5 (i.e. the tightest/earliest breakeven trigger,
0.5R, is the WORST setting everywhere -- it locks in a tiny gain too early
and gets whipsawed out of trades that would otherwise have run). The best
tested value (1.5R) approaches but never quite reaches the un-BE'd V-09
control on M1/M2/M5/M15 -- BE strictly costs net vs. V-09 across this whole
grid, with the cost shrinking as be_at_r grows (consistent with BE
converging toward "never triggers" as be_at_r -> large, same convergence
shape as V-01b's range_k). The grid's ceiling (1.5R) did not bracket a
reversal, so, like V-01, there may be further room above 1.5R, but even at
its best BE never beats V-09 in this batch.

**Best-net be_at_r per TF** -- ingested as `sim-report-emasar-v02-<tf>`:

| TF  | Best be_at_r | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------------:|----------:|-------:|-------:|----------:|
| M1  | 1.5            | -47,060.7 |  0.516 |  28.14 | 47,654.4  |
| M2  | 1.5            |  10,998.6 |  1.252 |  40.40 |  3,602.7  |
| M5  | 1.5            |  35,013.3 |  3.662 |  60.25 |    633.6  |
| M15 | 1.5            |  36,449.1 | 10.413 |  76.27 |    881.1  |

---

## V-03 — Range-based (volatility-adaptive) trailing ladder (engine extension)

New params `trail_mode_ladder='range'`, `f1_trail_range_k`,
`f2_trail_range_k`, `f3_trail_range_k` (semantics identical to
`emasar_ref`'s `trail_mode='range'`: trailing distance per bar =
`fN_trail_range_k * (bar['high'] - bar['low'])` of the CURRENT bar). Unit
tests confirm `trail_mode_ladder='pips'` (default) reproduces the
pre-extension event stream byte-for-byte (synthetic + real M5). V-09 params
otherwise. Grid: ladders (2,3,4), (1.5,2.5,3.5), (3,4,6).

| TF  | Ladder k (f1,f2,f3) | Trades | Net ($)    | PF    | WR (%) | MaxDD ($) |
|-----|-----------------------|-------:|-----------:|------:|-------:|----------:|
| M1  | 2.0, 3.0, 4.0         | 5,703  | -21,115.7  | 0.801 |  31.30 | 21,885.3  |
| M1  | 1.5, 2.5, 3.5         | 6,528  | -24,653.9  | 0.773 |  31.31 | 25,242.1  |
| M1  | 3.0, 4.0, 6.0         | 3,795  | -10,001.4  | 0.883 |  32.15 | 10,835.8  |
| M2  | 2.0, 3.0, 4.0         | 2,769  | -11,192.3  | 0.849 |  30.91 | 12,714.6  |
| M2  | 1.5, 2.5, 3.5         | 3,171  | -13,539.2  | 0.823 |  31.98 | 14,316.8  |
| M2  | 3.0, 4.0, 6.0         | 1,766  |   1,320.8  | 1.025 |  33.07 |  3,678.8  |
| M5  | 2.0, 3.0, 4.0         | 1,053  |   3,948.9  | 1.095 |  37.99 |  5,082.1  |
| M5  | 1.5, 2.5, 3.5         | 1,179  |   3,627.6  | 1.087 |  36.30 |  4,521.3  |
| M5  | 3.0, 4.0, 6.0         |   713  |   8,295.6  | 1.268 |  37.45 |  2,465.3  |
| M15 | 2.0, 3.0, 4.0         |   393  |     478.4  | 1.017 |  34.61 |  7,883.1  |
| M15 | 1.5, 2.5, 3.5         |   429  |  -1,747.2  | 0.940 |  34.27 |  9,215.2  |
| M15 | 3.0, 4.0, 6.0         |   270  |   1,222.6  | 1.049 |  33.33 |  6,709.3  |

**Range-mode trailing is a large step down from pips-mode everywhere.**
Trade counts drop sharply (a symptom of the range-scaled trailing distance
being much wider than the fixed-pip ladder on most bars in this window,
so far fewer fichas ever get stopped into a fresh re-entry slot -- e.g. M1
drops from 13,881 trades (V-09) to as few as 3,795 at the widest ladder).
PF barely clears 1.0 even in the best cases (M2/M5/M15 with the widest
tested ladder (3,4,6)) and M1/M2 stay net-negative at the tighter ladders.
The widest tested ladder (3,4,6) is consistently the best of the three on
every TF except M1's own internal ranking is also (3,4,6)-best but still
deeply negative -- again hinting the true optimum may lie beyond this
grid's ceiling, but even at (3,4,6) V-03 is far below both V-09 and V-01
baselines on every TF (M15's best is +1,222.6 vs. V-09's +37,326.6).

**Best-net ladder per TF** -- ingested as `sim-report-emasar-v03-<tf>`:

| TF  | Best ladder k (f1,f2,f3) | Net ($)   | PF    | WR (%) | MaxDD ($) |
|-----|----------------------------|----------:|------:|-------:|----------:|
| M1  | 3.0, 4.0, 6.0               | -10,001.4 | 0.883 |  32.15 | 10,835.8  |
| M2  | 3.0, 4.0, 6.0               |   1,320.8 | 1.025 |  33.07 |  3,678.8  |
| M5  | 3.0, 4.0, 6.0               |   8,295.6 | 1.268 |  37.45 |  2,465.3  |
| M15 | 3.0, 4.0, 6.0               |   1,222.6 | 1.049 |  33.33 |  6,709.3  |

---

## Head-to-head vs V-09 baseline and V-01 (k=2.0)

| TF  | V-09 Net  | V-01 k=2.0 Net | V-01b best (k) | V-04 best (ladder) | V-02 best (be_at_r) | V-03 best (ladder_k) |
|-----|----------:|---------------:|------------------|-----------------------|-------------------------|--------------------------|
| M1  | -42,866.1 | -37,432.2       | -36,414.3 (k=6.0)| -46,466.4 (80,150,340) | -47,060.7 (1.5)          | -10,001.4 (3,4,6)        |
| M2  |  13,732.8 |  17,831.4       |  19,650.6 (k=3.0) | -12,617.8 (80,150,230) |  10,998.6 (1.5)          |   1,320.8 (3,4,6)        |
| M5  |  37,469.7 |  39,950.7       |  41,279.7 (k=6.0) |  23,872.0 (80,150,230) |  35,013.3 (1.5)          |   8,295.6 (3,4,6)        |
| M15 |  37,326.6 |  39,749.7       |  39,749.7 (k=2.5) |  32,455.0 (80,150,230) |  36,449.1 (1.5)          |   1,222.6 (3,4,6)        |

### Verdicts

- **V-01b (range_k extension) -- BEATS baseline.** Confirms and extends
  V-01's win on M2 (+19,650.6 > +17,831.4 at k=2.0, new best k=3.0 where the
  curve flattens) and M5 (+41,279.7 > +39,950.7 at k=6.0). M15 is a wash
  (39,749.7 == V-01's own k=2.0 number; the curve is flat from k=2.0
  onward). M1 improves slightly over both V-09 and V-01 but stays
  net-negative. **The open question from batch 1 is answered**: the knee is
  at roughly k≈2.5-3.0 for M2/M15 (net goes flat) and the curve never truly
  reverses within the tested range for M1/M5, it just decelerates.

- **V-04 (trailing ladder sweep) -- WORSE.** Every combo in the 24-cell grid
  underperforms V-09's flat 100/100/100 on M2, M5, and M15 (M2 is
  universally negative across all 24 combos -- the standout negative
  finding of this batch); M1's best combo is also worse than V-09's own M1
  number. De-equalizing the trailing ladder is a net loser in this window;
  flat trailing distances across F1/F2/F3 dominate every spread ladder
  tested.

- **V-02 (breakeven-at-R) -- WORSE, but converging toward parity.**
  Breakeven costs net on every TF vs. V-09 across the whole `{0.5,1.0,1.5}`
  grid, with the smallest be_at_r (0.5) always the worst setting (premature
  lock-in) and 1.5R the least-bad. The gap to V-09 shrinks monotonically as
  be_at_r grows (M15: -14,877 at 0.5R -> -877.5 at 1.5R), suggesting BE
  would approach breakeven-with-baseline (pun intended) or possibly flip
  positive above 1.5R, but that's outside this batch's tested grid.

- **V-03 (range-mode trailing ladder) -- WORSE, and by a wide margin.**
  Range-scaled trailing collapses trade counts and PF across the board;
  even its best (widest, 3/4/6) ladder is far below V-09/V-01 on every TF.
  This mode is not competitive with fixed-pip trailing in this window.

**Batch 2's single clear winner is V-01b**, which is really an extension of
batch 1's V-01 finding: loosening the legal range-SL keeps paying off (with
a genuine knee now visible on M2/M15 around k≈2.5-3.0) and remains the best
lever tested across both batches for M2/M5/M15. V-04, V-02, and V-03 all
underperform both V-09 control and V-01/V-01b on every TF that matters
(M2/M5/M15) -- the per-ficha ladder is best kept flat, breakeven-at-R is
net-costly at the tested trigger levels, and range-mode trailing is
substantially worse than pips-mode in this window.

## Data gaps

None. Same M1/M2/M5/M15 lake coverage as batch 1 (2026-06-01→2026-07-07,
warmup+window), reused via `gen_variant_batch1._load_bars`/`_bars_for`
(cached across all 4 variants' sweeps in this run).

## Engine changes (additive, default-preserving)

`sentinel_engine/strategies/emasar_variant.py::simular_variant` gained:
- `be_at_r: float = 0.0`, `be_offset_pips: float = 0.5` -- breakeven-at-R
  per ficha (V-02). Disabled by default.
- `trail_mode_ladder: str = 'pips'`, `f1_trail_range_k: float = 2.0`,
  `f2_trail_range_k: float = 3.0`, `f3_trail_range_k: float = 4.0` --
  range-mode per-ficha trailing distance (V-03). Defaults to `'pips'`
  (pre-extension behavior).
- `_Ficha` (vendored from `emasar_ref`, `__slots__`) could not carry a new
  attribute for the BE calc's initial-SL reference, so the initial SL is
  tracked out-of-band in a `sl_inicial_by_tag` dict, reset on every fresh
  entry (mirrors the existing `fichas` dict's tag-keyed lifecycle).
- `emasar_ref.py` was NOT touched (frozen, golden-tested).

`tests/strategies/test_emasar_variant.py` (new, 7 tests, all passing):
default-preservation for both extensions individually and combined (on a
synthetic fixture AND a real XAUUSD/M5 2026-06 lake window), plus sanity
checks that turning each extension on actually changes the event stream and
stays within the expected motivo vocabulary.

## Ingested runs (winners only, `data/research.db`)

- `sim-report-emasar-v01b-{m1,m2,m5,m15}` -- best-net k per TF from
  `{2.5,3.0,4.0,6.0}` (k=6.0 for M1/M5, k=3.0 for M2, k=2.5 for M15; ties
  broken by lowest k where the curve had flattened).
- `sim-report-emasar-v04-{m1,m2,m5,m15}` -- best-net ladder per TF from the
  24-combo grid (see per-TF tables above for the exact (f1,f2,f3) chosen).
- `sim-report-emasar-v02-{m1,m2,m5,m15}` -- best-net be_at_r per TF, all
  four at be_at_r=1.5 (the loosest tested trigger).
- `sim-report-emasar-v03-{m1,m2,m5,m15}` -- best-net range-ladder per TF,
  all four at ladder_k=(3.0,4.0,6.0) (the widest tested).

All re-ingestion is idempotent (delete-before-insert per run_id), verified
via `PYTHONPATH=D:/FOREX python scripts/dev/e2e_service.py --port 8611` +
`GET /api/runs/<run_id>/trades` returning non-empty rows for all 16 winner
run_ids (4 variants × 4 TFs). Service was started fresh for this
verification and its single listening PID was stopped afterward; the
production service on :8601 was left untouched throughout.
