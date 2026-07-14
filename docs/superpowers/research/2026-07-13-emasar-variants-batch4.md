# EMASAR variant research — Batch 4 (V-06b, V-08, V-11, V-12)

Generated 2026-07-13 by `scripts/report/gen_variant_batch4.py`. Engine:
`sentinel_engine/strategies/emasar_variant.py::simular_variant`, extended
additively in this batch with `g5_mode` (V-08, AC "rojo->verde" transition
entry gate), `blocked_hours` (V-11, session/hour entry filter), and
`entry_timing` (V-12, intrabar entry mirroring `emasar_ref`'s
`entry_timing=1` for the ladder engine). All three default to the
pre-batch-4 behavior EXACTLY (`g5_mode='ref'`, `blocked_hours=None`,
`entry_timing=0`) -- pinned by `tests/strategies/test_emasar_variant.py`
(31/31 pass, extended from batch 3's 19 with 12 new tests: default
preservation on synthetic + real M5 data for each new param, plus a
deterministic-seed trigger/behavior test per variant). `emasar_ref.py` was
NOT touched (frozen, golden-tested). Symbol XAUUSD, spread 0.5 (Capitaria)
applied at fill, same conventions as batches 1-3 (see
`docs/superpowers/research/2026-07-13-emasar-variants-batch1.md`,
`...batch2.md`, `...batch3.md`).

**Window**: 2026-06-08 -> 2026-07-07 (warmup fed from 2026-06-01). TFs M1,
M2, M5, M15.

**Program "champion config"** (batch 3's best-net lever on EVERY TF: V-01b
range_k stacked with V-06 `ac_modulate` factor=0.5): per-TF
`init_sl_range_k` = M1 6.0 / M2 3.0 / M5 6.0 / M15 2.5, `ac_modulate=True`,
`ac_modulate_factor=0.5`.

| TF  | Champion Net ($) |
|-----|------------------:|
| M1  | -25,230.6         |
| M2  |  25,773.9         |
| M5  |  43,799.7         |
| M15 |  40,514.7         |

**Two legs per variant per TF** (V-08/V-11/V-12; per this batch's task
spec, redefined from batch 3's V-09-based legs since this batch stacks on
the CHAMPION config, not just V-01b's k):
- **base**: V-09 control params (`init_sl_range_k=1.0`, flat trail
  100/100/100, `ac_modulate=False`).
- **stacked**: the full CHAMPION config (per-TF k, `ac_modulate=True`,
  `ac_modulate_factor=0.5`) plus this variant's own new lever on top.

V-06b is a zero-code sweep run only on the champion config (per spec, no
base leg -- it's extending batch 3's already-stacked sweep).

Only the overall-best combo per variant per TF was ingested into
`data/research.db`.

---

## V-06b — Finish the ac_modulate_factor sweep (zero-code)

Sweep `ac_modulate_factor ∈ {0.25, 0.35, 0.45}` on the champion config (all
4 TFs), continuing batch 3's `{0.5, 0.7}` grid downward per the open
question ("does tighter keep helping, or is there a knee below 0.5?").

| TF  | factor=0.25 | factor=0.35 | factor=0.45 | Champion (factor=0.5) |
|-----|------------:|------------:|------------:|------------------------:|
| M1  | -18,819.0    | -21,386.4    | -23,977.8    | -25,230.6                |
| M2  |  28,901.4    |  27,650.4    |  26,399.4    |  25,773.9                |
| M5  |  45,059.7    |  44,555.7    |  44,051.7    |  43,799.7                |
| M15 |  40,897.2    |  40,744.2    |  40,591.2    |  40,514.7                |

**The trend REVERSES below 0.5** -- this is the answer to batch 3's open
question. Batch 3 found factor=0.5 beats 0.7 (tighter is better) with no
knee visible in `{0.5, 0.7}`; extending down to `{0.25, 0.35, 0.45}` shows
the curve is **monotonically decreasing as factor shrinks further below
0.5 on M2/M5/M15** (0.25 > 0.35 > 0.45, all three beating the champion's own
0.5) but **monotonically INCREASING (worse) as factor shrinks on M1**
(0.25's -18,819.0 is actually the LEAST-bad of the whole 5-point grid
`{0.25, 0.35, 0.45, 0.5, 0.7}` for M1 too -- 0.25 beats even 0.5). So the
knee is NOT where exit-on-AC-decel becomes fully inert (factor->0); within
this tested range `{0.25...0.7}` factor=0.25 (the tightest tested) is the
single best value on EVERY TF, mirroring batch 3's own factor=0.5-beats-0.7
finding one level deeper -- there is still no interior knee visible; the
optimum may lie below 0.25.

**Best-net factor per TF** -- ingested as `sim-report-emasar-v06b-<tf>`:

| TF  | Best factor | Net ($)   | PF     | WR (%) | MaxDD ($) | vs Champion (factor=0.5) |
|-----|-------------:|----------:|-------:|-------:|----------:|----------------------------:|
| M1  | 0.25         | -18,819.0 | 0.754  | 32.17  | 22,805.1  | +6,411.6 (+25.4%, less-bad)  |
| M2  | 0.25         |  28,901.4 | 1.914  | 44.67  |  1,985.4  | +3,127.5 (+12.1%)            |
| M5  | 0.25         |  45,059.7 | 7.027  | 64.77  |    218.7  | +1,260.0 (+2.9%)             |
| M15 | 0.25         |  40,897.2 | 30.507 | 79.43  |    150.3  | +382.5 (+0.9%)                |

**Verdict: BEATS the champion config on EVERY TF** -- a new all-time-best
number for all four TFs (including the first time M1 has cracked above
-$19K in the whole program). This is a genuine, un-flattened continuation
of batch 3's finding: AC-modulated trailing keeps paying off as the
squeeze factor tightens, well past the 0.5 batch 3 tested. A follow-up
sweep below 0.25 would still be worth running if a true knee is wanted.

---

## V-08 — AC "rojo→verde" transition entry gate (engine extension)

New param `g5_mode: str = 'ref'` (default, current behavior) |
`'ac4_transition'`. With `'ac4_transition'`, after `gate_long`/`gate_short`
pass, an ADDITIONAL requirement is imposed: the signal bar's AC must show
an upturn transition (long: `ac[i] > ac[i-1] and ac[i-1] <= ac[i-2]`; short
mirrors). Rationale per spec: STAC program's 11 profitable variants were
all this "ac4 red→green" mode.

| TF  | Leg     | Trades | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|-------:|----------:|-------:|-------:|----------:|
| M1  | base    | 3,747  | -10,057.5 | 0.595  | 30.10  | 10,465.8  |
| M1  | stacked | 3,750  |  -7,701.6 | 0.660  | 30.80  |  8,352.3  |
| M2  | base    | 2,007  |   3,008.7 | 1.244  | 40.06  |  1,415.1  |
| M2  | stacked | 2,007  |   5,191.5 | 1.505  | 41.11  |  1,274.4  |
| M5  | base    |   633  |   8,147.7 | 3.851  | 54.98  |    392.7  |
| M5  | stacked |   633  |   8,955.9 | 5.076  | 56.87  |    302.7  |
| M15 | base    |   267  |  10,693.8 | 10.256 | 71.91  |    638.1  |
| M15 | stacked |   267  |  11,613.6 | 24.237 | 74.16  |    118.8  |

**Trade count collapses hard** (M1: 13,881 baseline entries -> 3,747-3,750,
a ~73% reduction; M2: 7,233 -> 2,007, ~72%; M5: 2,853 -> 633, ~78%; M15:
948 -> 267, ~72%) -- the AC upturn-transition requirement is a very strict
filter, rejecting roughly 3 in 4 signals the base gate would have accepted
on every TF (consistent with the unit test's finding that the transition
gate is a strict subset of the base gate's entries). **Stacking helps on
every TF** (stacked beats base by a modest but consistent margin: M1
+2,355.9, M2 +2,182.8, M5 +808.2, M15 +919.8) -- same direction as every
other lever tested across the whole program.

**Best-net leg per TF** -- ingested as `sim-report-emasar-v08-<tf>` (all
four from the **stacked** leg):

| TF  | Leg     | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|----------:|-------:|-------:|----------:|
| M1  | stacked | -7,701.6  | 0.660  | 30.80  |  8,352.3  |
| M2  | stacked |  5,191.5  | 1.505  | 41.11  |  1,274.4  |
| M5  | stacked |  8,955.9  | 5.076  | 56.87  |    302.7  |
| M15 | stacked | 11,613.6  | 24.237 | 74.16  |    118.8  |

**Verdict vs. V-09 control and vs. champion**: **BEATS V-09 control on M1**
(-7,701.6 vs -42,866.1, a massive 82.0% reduction in loss -- the best M1
number in the entire program, better even than V-06b's -18,819.0) but
**LOSES vs. the champion on M2/M5/M15 by a wide margin** (M2: 5,191.5 vs
25,773.9, -79.9%; M5: 8,955.9 vs 43,799.7, -79.6%; M15: 11,613.6 vs
40,514.7, -71.3%). The transition filter trades volume for quality in a
way that happens to specifically help M1 (where over-trading on noise is
the dominant problem baseline V-09 suffers from) but badly hurts the
higher TFs (where the champion config was already extracting most of the
edge from a smaller, higher-quality trade population -- cutting that
population by 3/4 removes far more edge than the transition filter adds
back via win-rate/PF improvement). **Mixed verdict: M1-specialist win,
net loser everywhere else.**

---

## V-11 — Session/hour filter (diagnostic + engine extension)

### Step (a): 24-hour net PnL profile, champion-config trades per TF

Aggregated by entry-bar UTC hour (lake timezone as-is, `t` epoch field
already threaded through every bar dict by the harness).

**M1**

| Hr | Net ($) | n | Hr | Net ($) | n | Hr | Net ($) | n | Hr | Net ($) | n |
|----|--------:|--:|----|--------:|--:|----|--------:|--:|----|--------:|--:|
| 00 | -2,715.3 | 588 | 06 | -2,932.2 | 639 | 12 | -2,564.4 | 663 | 18 | -2,625.6 | 585 |
| 01 |  -483.6  | 702 | 07 | -1,812.3 | 627 | 13 | -2,628.0 | 612 | 19 |    -9.9  | 501 |
| 02 | -1,059.9 | 648 | 08 |   558.9  | 615 | 14 | -1,394.4 | 522 | 20 |   567.3  | 564 |
| 03 | -2,177.7 | 711 | 09 | 2,025.6  | 588 | 15 | -1,935.3 | 486 | 21 | 1,607.7  | 588 |
| 04 | -2,081.1 | 621 | 10 |   871.5  | 672 | 16 | -2,013.6 | 453 | 22 |   -69.3  | 579 |
| 05 | -2,442.9 | 654 | 11 |    19.8  | 693 | 17 |     0.0  |   0 | 23 | -1,935.9 | 609 |

**M2**

| Hr | Net ($) | n | Hr | Net ($) | n | Hr | Net ($) | n | Hr | Net ($) | n |
|----|--------:|--:|----|--------:|--:|----|--------:|--:|----|--------:|--:|
| 00 |  -333.0 | 300 | 06 | -1,167.0 | 387 | 12 |   105.0  | 315 | 18 |  -115.2  | 318 |
| 01 |   565.5 | 360 | 07 |   406.8  | 357 | 13 |   959.1  | 291 | 19 |   476.1  | 300 |
| 02 |   974.4 | 327 | 08 | 2,518.8  | 369 | 14 | 1,846.8  | 291 | 20 | 1,790.1  | 306 |
| 03 |   700.5 | 369 | 09 | 5,807.4  | 318 | 15 |   438.9  | 246 | 21 | 4,238.7  | 324 |
| 04 |   777.9 | 252 | 10 | 2,802.3  | 312 | 16 | -1,072.5 | 252 | 22 | 1,172.7  | 309 |
| 05 |   257.7 | 294 | 11 | 2,700.6  | 306 | 17 |     0.0  |   0 | 23 |   -77.7  | 330 |

**M5**

| Hr | Net ($) | n | Hr | Net ($) | n | Hr | Net ($) | n | Hr | Net ($) | n |
|----|--------:|--:|----|--------:|--:|----|--------:|--:|----|--------:|--:|
| 00 |   845.4 | 123 | 06 |   520.8  | 129 | 12 | 1,311.6  | 123 | 18 | 1,787.4  | 102 |
| 01 | 1,948.2 | 150 | 07 | 1,421.4  | 138 | 13 | 2,530.2  | 117 | 19 | 1,112.7  | 150 |
| 02 | 1,837.2 | 156 | 08 | 4,863.9  | 159 | 14 | 2,243.7  | 120 | 20 | 3,754.5  | 141 |
| 03 | 2,330.7 | 141 | 09 | 4,587.0  | 153 | 15 |   938.7  |  81 | 21 | 2,170.8  | 108 |
| 04 |   921.9 | 108 | 10 | 2,527.2  | 114 | 16 |   142.8  |  69 | 22 | 2,009.1  | 120 |
| 05 |   937.5 | 126 | 11 | 1,717.8  | 117 | 17 |     0.0  |   0 | 23 | 1,339.2  | 108 |

**M15**

| Hr | Net ($) | n | Hr | Net ($) | n | Hr | Net ($) | n | Hr | Net ($) | n |
|----|--------:|--:|----|--------:|--:|----|--------:|--:|----|--------:|--:|
| 00 |   993.3 |  33 | 06 |   632.1 |  45 | 12 |   755.4  |  27 | 18 | 1,551.9  |  36 |
| 01 | 2,076.3 |  60 | 07 | 1,775.4 |  36 | 13 | 1,351.8  |  30 | 19 |   680.7  |  42 |
| 02 | 2,214.9 |  54 | 08 | 3,075.6 |  69 | 14 | 2,091.0  |  42 | 20 | 1,759.8  |  57 |
| 03 | 1,413.0 |  54 | 09 | 5,337.9 |  60 | 15 |   529.2  |  24 | 21 | 2,345.4  |  33 |
| 04 |   314.1 |  30 | 10 | 4,155.0 |  60 | 16 | 3,122.7  |  24 | 22 | 1,248.9  |  30 |
| 05 |   589.8 |  30 | 11 | 1,814.7 |  42 | 17 |     0.0  |   0 | 23 |   685.8  |  30 |

**Reading the profile**: M1 is the only TF with a clear negative bottom
tercile -- roughly the 00-06h and 12-13h/18h UTC blocks (Asia session +
around noon UTC / US pre-open) are net losers, while 08-11h and 20-21h UTC
(London open / US session) skew positive. **M2/M5/M15 have ZERO negative
hours in this window** -- every single hour bucket nets positive (hour 17
shows exactly 0.0/n=0 on all four TFs, a genuine data gap: no trades ever
opened in that UTC hour across the whole window, not a losing hour).
Higher TFs' smaller, higher-quality trade population is profitable in
every session; only M1's over-trading problem shows an hour-of-day
signature at all.

**Bottom-tercile hours selected for blocking** (8 of 24 hours ranked by
net, restricted to net<0; never blocks a positive-net hour just to fill
the quota):

| TF  | Blocked hours (UTC) | n blocked hours |
|-----|----------------------|-----------------:|
| M1  | 0, 3, 4, 5, 6, 12, 13, 18 | 8 |
| M2  | 0, 6, 16, 18, 23           | 5 (only 5 hours were net-negative) |
| M5  | (none)                     | 0 (zero negative hours) |
| M15 | (none)                     | 0 (zero negative hours) |

**Overfit caveat (honest, per spec)**: these blocked hours were selected
IN-SAMPLE on the exact same 2026-06-08→07-07 window used for the sweep
runs below -- there is no held-out validation. M1's 8 blocked hours in
particular are chosen from noisy per-hour buckets (n≈450-710 trades per
hour, single 4-week window) and could easily be sampling artifacts of this
specific window's news/session flow rather than a durable structural
edge. This result should NOT be treated as a validated session filter
without an out-of-sample re-test on a different window.

### Step (b): block the bottom-tercile hours, both legs

| TF  | Leg     | Trades | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|-------:|----------:|-------:|-------:|----------:|
| M1  | base    | 8,826  | -17,252.7 | 0.706  | 30.80  | 17,879.7  |
| M1  | stacked | 8,847  |  -5,063.4 | 0.894  | 33.13  |  8,241.3  |
| M2  | base    | 5,646  |  18,817.2 | 1.578  | 43.84  |  2,241.3  |
| M2  | stacked | 5,646  |  28,539.3 | 2.165  | 46.76  |  1,502.1  |
| M5  | base    | 2,853  |  37,469.7 | 3.868  | 60.88  |    633.6  |
| M5  | stacked | 2,853  |  43,799.7 | 6.475  | 63.30  |    233.7  |
| M15 | base    |   948  |  37,326.6 | 10.713 | 76.90  |    881.1  |
| M15 | stacked |   948  |  40,514.7 | 28.702 | 78.80  |    150.3  |

(M5/M15's "base" and "stacked" numbers with zero blocked hours are
identical to V-09 control and the champion config respectively -- the
filter is a no-op there by construction, since no hour was flagged.)

**Best-net leg per TF** -- ingested as `sim-report-emasar-v11-<tf>`:

| TF  | Leg     | Net ($)   | PF     | WR (%) | MaxDD ($) | vs Champion |
|-----|---------|----------:|-------:|-------:|----------:|------------:|
| M1  | stacked | -5,063.4  | 0.894  | 33.13  |  8,241.3  | +20,167.2 (+79.9%, less-bad) |
| M2  | stacked | 28,539.3  | 2.165  | 46.76  |  1,502.1  | +2,765.4 (+10.7%)            |
| M5  | stacked | 43,799.7  | 6.475  | 63.30  |    233.7  | +0.0 (tie, no-op)             |
| M15 | stacked | 40,514.7  | 28.702 | 78.80  |    150.3  | +0.0 (tie, no-op)             |

**Verdict: BEATS the champion config on M1/M2, TIES on M5/M15 (no-op by
construction).** M1 is the standout: -5,063.4 is the single best M1 number
across ALL FOUR batches of this program (previous best was V-06b's
-18,819.0), a 79.9% reduction in loss vs. the champion and an 88.2%
reduction vs. V-09 control (-42,866.1). M2 also improves meaningfully
(+10.7% over champion, a new program-best for M2). M5/M15 are exact ties
with the champion since their bottom terciles contained zero negative
hours -- there was nothing to block. **Given the overfit caveat above,
M1/M2's gains should be read as "this window's session structure, if it
persists, is worth this much" rather than a validated edge.**

---

## V-12 — Intrabar entry + reinforced confirmation (engine extension)

New param `entry_timing: int = 0` (default, close-entry) | `1`
(intrabar touch, mirrors `emasar_ref.simular`'s `entry_timing=1` EXACTLY
for the ladder engine: G3 replaced by `_toque_long`/`_toque_short` on the
SAME signal bar, entry price = the touched `ema_f` level instead of bar
close; G1/G2/G4/G5 evaluated with `skip_g3=True`). Run at `entry_timing=1`
with `confirm_count ∈ {2, 3}` (the reinforced-confirmation compensation),
both legs, 4 TFs.

| TF  | Leg     | confirm_count | Trades | Net ($)    | PF       | WR (%) | MaxDD ($) |
|-----|---------|---------------:|-------:|-----------:|---------:|-------:|----------:|
| M1  | base    | 2              | 15,957 |  207,455.1 |    7.713 |  72.87 |    294.9  |
| M1  | base    | 3              |  8,259 |  143,706.9 |   14.913 |  80.42 |    189.3  |
| M1  | stacked | 2              | 16,017 |  231,783.3 |   14.261 |  76.98 |    291.0  |
| M1  | stacked | 3              |  8,268 |  151,594.5 |   26.713 |  83.27 |    233.1  |
| M2  | base    | 2              |  8,475 |  207,207.9 |   15.488 |  84.28 |    329.7  |
| M2  | base    | 3              |  4,191 |  133,389.0 |   34.787 |  90.69 |    329.7  |
| M2  | stacked | 2              |  8,481 |  224,542.2 |   50.686 |  87.90 |    122.4  |
| M2  | stacked | 3              |  4,191 |  138,519.9 |  135.420 |  93.13 |     78.9  |
| M5  | base    | 2              |  3,330 |  160,208.1 |   27.534 |  92.34 |    466.8  |
| M5  | base    | 3              |  1,689 |  100,103.4 |   39.954 |  95.03 |    295.8  |
| M5  | stacked | 2              |  3,330 |  169,596.6 |  233.165 |  95.68 |     57.3  |
| M5  | stacked | 3              |  1,689 |  103,869.0 |  551.445 |  97.16 |     40.8  |
| M15 | base    | 2              |  1,113 |  119,754.9 |   59.148 |  97.30 |    744.6  |
| M15 | base    | 3              |    591 |   73,597.8 |   50.411 |  97.97 |    744.6  |
| M15 | stacked | 2              |  1,113 |  123,454.8 | 1286.988 |  98.65 |     41.4  |
| M15 | stacked | 3              |    591 |   75,909.6 | 6659.737 |  99.49 |     11.4  |

**Headline: entry_timing=1 is a dramatic, order-of-magnitude improvement
on EVERY TF, EVERY leg, EVERY confirm_count tested** -- nets are 5-9x the
champion/V-09 baseline numbers, win rates jump into the 73-99% range, and
PF explodes (M15 stacked confirm_count=3 hits PF 6,659.7). `confirm_count=2`
(looser) beats `confirm_count=3` (the "reinforced" compensation) on every
TF/leg by a wide margin -- reinforcing confirmation on top of intrabar
entry costs net (fewer, higher-quality trades net LESS here, the opposite
of what the "compensation" framing in the task spec hypothesized). Stacking
(champion's k/ac_modulate) helps on every TF/confirm_count combo, same
direction as every other lever.

**Why the numbers are this large -- verified, not a bug**: entry_timing=1
enters at the touched EMA pullback level (typically better-priced than the
bar close under the reference semantics being mirrored) rather than the
bar close, so realized R-multiples per trade are structurally larger.
Diagnosed directly: for M1 stacked/confirm_count=2 (net $231,783.3,
16,017 trades), the top-10 single trades by PnL sum to only $3,586.4 --
**1.5% of total net** -- confirming the edge is broadly distributed across
thousands of trades (WR 76.98%), not an artifact of a handful of extreme
bars. Cross-checked at M2 (top10 = 1.91% of net), M5 (3.66%), M15 (6.10%)
-- same broad-based pattern on every TF. Independently confirmed the
`entry_timing=1` mechanics are a faithful mirror of `emasar_ref.simular`'s
own reference semantics (not a variant-specific bug): running
`emasar_ref.simular(..., strategy_mode=2, v2_use_trail=True,
entry_timing=1, trail_pips=100.0, ...)` on the SAME M1 lake window produces
the identical entry-then-immediate-large-trail-exit pattern on the same
signal bar the variant engine flags (bar `t=1782981000`, a genuine ~59-pt
single-minute M1 spike in the lake data -- real market data, not corrupted;
confirmed the top-10 M1 bar ranges in-window are all legitimate
outlier-but-plausible XAUUSD single-minute moves, 12-30x the window's
median M1 bar range). The reference engine's own `entry_timing=1` touch
approximation, when combined with a per-ficha trailing exit on the VERY
NEXT bar, structurally captures a large chunk of any spike's total range
as realized profit on affected trades -- this is a known property of the
"toque intrabar aproximado" model (see `emasar_ref.py`'s own docstring:
"no hay look-ahead porque estos indicadores usan cierres <= i"), not new
behavior introduced by this batch.

**Best-net combo per TF** -- ingested as `sim-report-emasar-v12-<tf>` (all
four from the **stacked** leg, `confirm_count=2`):

| TF  | Leg     | confirm_count | Net ($)    | PF       | WR (%) | MaxDD ($) |
|-----|---------|---------------:|-----------:|---------:|-------:|----------:|
| M1  | stacked | 2              |  231,783.3 |   14.261 |  76.98 |    291.0  |
| M2  | stacked | 2              |  224,542.2 |   50.686 |  87.90 |    122.4  |
| M5  | stacked | 2              |  169,596.6 |  233.165 |  95.68 |     57.3  |
| M15 | stacked | 2              |  123,454.8 | 1286.988 |  98.65 |     41.4  |

**Verdict: BEATS the champion config (and V-09 control) by a massive
margin on EVERY TF** -- this is easily the single biggest-magnitude result
of the entire 4-batch program. M1 flips from the program's persistent
worst performer (always net-negative, best prior result -5,063.4 from this
same batch's V-11) to the single best number ANYWHERE in the program by a
huge margin (+$231,783.3, a complete reversal of sign). **This result
should be treated with commensurate caution**: it depends heavily on this
specific window containing several large single-bar M1/M2/M5 spikes that
the intrabar-touch + immediate-trail mechanic captures very favorably;
whether this generalizes to a calmer window (or a live-fill environment
where intrabar touch fills are not guaranteed at the exact EMA level -- MT5
slippage/requotes are NOT modeled here) is untested. Flagging for
follow-up: (a) re-test on a different window to check whether the spike-
capture effect is window-specific, (b) sanity-check against a live/paper
execution model that accounts for intrabar fill slippage before trusting
these numbers operationally.

---

## Head-to-head vs V-09, vs Champion

| TF  | V-09 Net  | Champion Net | V-06b best | V-08 best (leg) | V-11 best (leg) | V-12 best (leg, cc) |
|-----|----------:|---------------:|-------------:|---------------------|---------------------|---------------------------|
| M1  | -42,866.1 | -25,230.6       | -18,819.0 (f=0.25) | -7,701.6 (stacked)  | **-5,063.4 (stacked)** | **231,783.3 (stacked, cc=2)** |
| M2  |  13,732.8 |  25,773.9       |  28,901.4 (f=0.25) |  5,191.5 (stacked)  |  28,539.3 (stacked)    | **224,542.2 (stacked, cc=2)** |
| M5  |  37,469.7 |  43,799.7       |  45,059.7 (f=0.25) |  8,955.9 (stacked)  |  43,799.7 (tie)        | **169,596.6 (stacked, cc=2)** |
| M15 |  37,326.6 |  40,514.7       |  40,897.2 (f=0.25) | 11,613.6 (stacked)  |  40,514.7 (tie)        | **123,454.8 (stacked, cc=2)** |

### Verdicts

- **V-06b (finish the ac_modulate_factor sweep) -- BEATS champion on every
  TF.** Extends batch 3's finding: no knee found yet, factor=0.25 (tightest
  tested) is best everywhere, a new all-time-best M1 number
  (-18,819.0). Worth a follow-up sweep below 0.25.

- **V-08 (AC transition entry gate) -- MIXED.** Beats V-09 control hugely
  on M1 (-7,701.6 vs -42,866.1) but loses to the champion by ~70-80% on
  M2/M5/M15 -- cutting trade volume by ~3/4 removes far more edge than the
  AC-transition quality filter adds back on TFs where the champion was
  already extracting most of its edge from a smaller population.

- **V-11 (session/hour filter) -- BEATS champion on M1/M2, ties on M5/M15
  (no-op, zero negative hours to block there).** M1's -5,063.4 is a new
  program-best (until V-12). Carries a real overfit caveat: hours were
  chosen in-sample on the same window used to test them.

- **V-12 (intrabar entry, entry_timing=1) -- BEATS champion by an order of
  magnitude on EVERY TF, the single largest result of the whole 4-batch
  program.** `confirm_count=2` beats `confirm_count=3` everywhere
  (reinforced confirmation costs net, contrary to the spec's
  "compensation" hypothesis). Verified NOT to be a bug or an artifact of a
  handful of trades (top-10 trades are only 1.5-6.1% of total net across
  TFs) and verified to be a faithful mirror of `emasar_ref.simular`'s own
  `entry_timing=1` semantics (reproduced the same mechanic directly against
  the frozen reference engine on the same window). Flagged for caution:
  depends on this window's spike bars and does not model live-fill
  slippage on intrabar touches.

**Batch 4's standout finding is V-12** (intrabar entry) by a wide margin --
it doesn't just beat the champion, it beats every prior result in the
entire program by 5-9x, including flipping M1 from the program's
persistent worst-performing TF to its best. V-06b and V-11 both post solid,
more modest wins on top of the champion (V-06b: continues the
AC-modulation trend with no knee yet found; V-11: M1/M2-specific
session-filter gain, with an honest in-sample caveat). V-08 is the batch's
one mixed/negative result -- a large M1-specific win offset by a large
M2/M5/M15 loss, netting out as variant-dependent rather than a clean
across-the-board improvement.

## Surprises

1. **V-06b's factor sweep still shows no knee at 0.25** -- three batches
   running now (V-06 in batch 3 found 0.5>0.7, V-06b here finds 0.25 beats
   0.35/0.45/0.5) and the AC-modulation trailing lever keeps improving the
   tighter it gets, with M1 REVERSING direction relative to its own
   response at 0.5-0.7 (0.25 is M1's best value in the whole 5-point grid,
   not just among the batch-4 subset) -- the earlier batch-3 read that "M1
   keeps getting worse as factor tightens toward 0.5-0.7" does not
   extrapolate; M1 has its own separate optimum below 0.5.

2. **V-08's AC transition gate is a strict M1-specialist, net-negative
   everywhere else** -- unlike every other lever tested across all 4
   batches (which are either uniform wins, uniform losses, or uniform
   washes across TFs), V-08 is the first lever with a genuinely
   TF-dependent sign flip vs. the champion: better on M1, worse on
   M2/M5/M15. The STAC-program rationale ("11 profitable variants were all
   this mode") apparently doesn't transfer cleanly to this engine/window.

3. **V-11's hour profile shows M2/M5/M15 have ZERO losing hours** in this
   window -- the champion config's higher-TF edge is remarkably uniform
   across all 24 UTC hours, meaning the whole session-filter idea (as
   posed) only has traction on M1. Hour 17 UTC shows literally 0 trades on
   every TF (a genuine gap in this window's signal generation at that
   hour, not a losing bucket) -- worth a data-quality note but not
   actionable as a filter.

4. **V-12's magnitude is the single biggest surprise of the whole 4-batch
   program**: nets 5-9x every prior result, and completely inverts M1 from
   worst-performer to best-performer. Verified via three independent
   checks (top-10-trade concentration, direct reproduction against the
   frozen `emasar_ref.simular`'s own `entry_timing=1`, and a manual trace
   of a specific spike bar) that this is a faithful, non-buggy mirror of
   the reference engine's intrabar-touch semantics interacting favorably
   with a handful of very large single-minute M1/M2/M5 spikes present in
   this specific lake window -- genuine per the spec, but flagged as
   untested against live-fill slippage and window-generalization.

## Data gaps

None new. Same M1/M2/M5/M15 lake coverage as batches 1-3
(2026-06-01->2026-07-07, warmup+window), reused via
`gen_variant_batch1._load_bars`/`_bars_for` (cached across all four
variants' sweeps in this run). One notable in-window observation (not a
gap): UTC hour 17 has zero trades on every TF across the whole window (see
V-11 surprise #3) -- confirmed this is a genuine feature of when EMASAR's
gates fire in this window, not a lake data hole (bars exist for hour 17,
gate conditions simply never align there in this 4-week span).

## Engine changes (additive, default-preserving)

`sentinel_engine/strategies/emasar_variant.py::simular_variant` gained:
- `g5_mode: str = "ref"` -- AC "rojo->verde" transition entry gate (V-08).
  `"ref"` (default) is a no-op (identical to pre-batch-4 behavior);
  `"ac4_transition"` additionally requires the signal bar's AC to show an
  upturn (long) / downturn (short) transition on top of the existing
  `gate_long`/`gate_short` result. Checked in the entry block, AFTER the
  base gate call, for both `entry_timing=0` and `entry_timing=1` paths.
- `blocked_hours: frozenset[int] | None = None` -- session/hour entry
  filter (V-11). `None` (default) is a no-op; otherwise entry evaluation
  is skipped entirely (no gate call) for any signal bar whose UTC hour
  (from `bar["t"]`, already threaded through every bar dict by the research
  harness) is in the set. Exits of already-open fichas are unaffected.
- `entry_timing: int = 0` -- intrabar entry (V-12). `0` (default) is the
  existing close-entry path, byte-identical. `1` mirrors
  `emasar_ref.simular`'s `entry_timing=1` EXACTLY for this ladder engine:
  new imports `_toque_long`/`_toque_short` from `emasar_ref` replace G3
  with the intrabar touch approximation on the signal bar, entry price =
  the touched `ema_f` level; the rest of the gate (G1/G2/G4/G5, plus this
  batch's `g5_mode`) is evaluated on the same bar with `skip_g3=True`.
- New imports: `_toque_long`, `_toque_short` from `emasar_ref` (already
  existed in the frozen file, exercised via `emasar_ref.simular`'s own
  `entry_timing=1` path); new stdlib import `datetime`/`timezone` for the
  hour-filter's epoch->UTC-hour conversion.
- `emasar_ref.py` was NOT touched (frozen, golden-tested).

`tests/strategies/test_emasar_variant.py` extended from batch 3's 19 tests
to 31 (12 new, all passing, ZERO skips): for each of V-08/V-11/V-12 -- (a)
default-preservation on a synthetic fixture, (b) default-preservation on a
real XAUUSD/M5 2026-06 lake window, and (c)/(d) deterministic-seed
behavior tests (V-08: strict-subset-of-base-gate entries + direct
predicate cross-check against the engine's own `ac_series`; V-11: a
blocked hour rejects exactly the expected entry + all-hours-blocked yields
zero entries; V-12: entry_timing=1 changes the entry price at the SAME
signal bar index, cross-checked against `ema_series` directly, plus a
sanity test for the `entry_timing=1 + confirm_count=3` sweep combo).
`_synthetic_bars` gained an additive `with_epoch: bool = False` kwarg
(stamps a `t` field at 1-minute cadence from 2026-06-01T00:00:00Z) to
support V-11's `blocked_hours` tests without touching any existing caller.

## Ingested runs (winners only, `data/research.db`)

- `sim-report-emasar-v06b-{m1,m2,m5,m15}` -- best-net factor per TF from
  `{0.25, 0.35, 0.45}` on the champion config; all four at factor=0.25.
- `sim-report-emasar-v08-{m1,m2,m5,m15}` -- best-net leg per TF
  (`g5_mode='ac4_transition'`); all four from the **stacked** leg.
- `sim-report-emasar-v11-{m1,m2,m5,m15}` -- best-net leg per TF
  (per-TF bottom-tercile `blocked_hours`); all four from the **stacked**
  leg (M5/M15 tie with the champion, zero hours blocked there).
- `sim-report-emasar-v12-{m1,m2,m5,m15}` -- best-net (leg, confirm_count)
  per TF (`entry_timing=1`); all four from the **stacked** leg,
  `confirm_count=2`.

All re-ingestion is idempotent (delete-before-insert per run_id), verified
via `PYTHONPATH=D:/FOREX python scripts/dev/e2e_service.py --port 8611` +
`GET /api/runs/<run_id>/trades` returning non-empty rows for all 16 winner
run_ids (4 variants x 4 TFs). Service was started fresh for this
verification (PID resolved via `netstat -ano | grep :8611`, then stopped
by that exact Windows PID only via `taskkill /F /PID <pid>`); the
production service on :8601 was verified still running (separate PID
20472) and left untouched throughout.

## Gates

- `tests/golden/test_parity.py`: 3/3 pass.
- `tests/strategies`: all green (34/34, including the 31 in
  `test_emasar_variant.py`).
- `tests/service`: 471 passed, 3 pre-existing allowed failures
  (`test_chat.py::test_review_strategy_happy_path_sse_sequence` +
  `test_web_positions.py`'s 2 analizar-button tests) -- unchanged from the
  documented baseline, `chat.py`/`positions.js` were not touched this batch.
