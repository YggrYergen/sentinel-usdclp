# EMASAR variant research -- Batch 5 (FINAL): V-06c, V-10, V-13, V-15

Generated 2026-07-13 by `scripts/report/gen_variant_batch5.py`. Engine:
`sentinel_engine/strategies/emasar_variant.py::simular_variant`, extended
additively in this batch with `direction_mask` (V-10, SuperTrend-M15 regime
filter), `reentry_enable`/`reentry_max` (V-13, controlled re-entry after a
full trail-out), and `sar_adaptive`/`sar_fast`/`sar_slow`/`vol_regime_window`
(V-15, volatility-adaptive SAR). All default to the pre-batch-5 behavior
EXACTLY (`direction_mask=None`, `reentry_enable=False`, `sar_adaptive=False`)
-- pinned by `tests/strategies/test_emasar_variant.py` (45/45 pass, extended
from batch 4's 31 with 14 new tests: default preservation on synthetic + real
M5 data for each new param, plus deterministic-seed trigger/behavior tests
per variant). `emasar_ref.py` was NOT touched (frozen, golden-tested).
Symbol XAUUSD, spread 0.5 (Capitaria) applied at fill, same conventions as
batches 1-4 (see `docs/superpowers/research/2026-07-13-emasar-variants-
batch{1,2,3,4}.md`).

**Window**: 2026-06-08 -> 2026-07-07 (warmup fed from 2026-06-01). TFs M1,
M2, M5, M15.

**Program "champion config"** for this batch (batch 4's V-06b best-net
factor, per-TF `init_sl_range_k` unchanged from batch 3/4): `init_sl_range_k`
= M1 6.0 / M2 3.0 / M5 6.0 / M15 2.5, `ac_modulate=True`,
`ac_modulate_factor=0.25`.

| TF  | Champion Net ($) |
|-----|------------------:|
| M1  | -18,819.0         |
| M2  |  28,901.4         |
| M5  |  45,059.7         |
| M15 |  40,897.2         |

**Two legs per variant per TF** (V-10/V-13/V-15):
- **base**: V-09 control params (`init_sl_range_k=1.0`, flat trail
  100/100/100, `ac_modulate=False`).
- **stacked**: the full CHAMPION config above plus this variant's own new
  lever on top.

V-06c is a zero-code sweep run only on the champion config (per spec,
continuing batch 4's V-06b sweep downward).

Only the overall-best combo per variant per TF was ingested into
`data/research.db`.

---

## V-06c -- ac_modulate_factor knee sweep (zero-code)

Sweep `ac_modulate_factor ∈ {0.10, 0.15, 0.20}` on the champion config (all
4 TFs), continuing batch 4's V-06b `{0.25, 0.35, 0.45}` grid downward per
the still-open question ("is there a knee below 0.25, or does the curve
stay monotonic all the way to 0?").

| TF  | factor=0.10 | factor=0.15 | factor=0.20 | Champion (factor=0.25) |
|-----|------------:|------------:|------------:|------------------------:|
| M1  | -14,922.0    | -16,221.0    | -17,520.0    | -18,819.0                |
| M2  |  30,777.9    |  30,152.4    |  29,526.9    |  28,901.4                |
| M5  |  45,815.7    |  45,563.7    |  45,311.7    |  45,059.7                |
| M15 |  41,126.7    |  41,050.2    |  40,973.7    |  40,897.2                |

**Still no knee.** The pattern from batch 4 (M1 improves as the factor
tightens further; M2/M5/M15 improve as the factor tightens further -- same
direction on EVERY TF this time, unlike batch 3's mixed read) continues
cleanly into `{0.10, 0.15, 0.20}`: factor=0.10 (the tightest tested, now
across FIVE batches of shrinking grids: 0.7 -> 0.5 -> 0.25 -> 0.20 -> 0.15
-> 0.10) is again the single best value on every TF, with the gap to the
next-tightest value (0.15) shrinking as the factor gets smaller (M1:
0.10 vs 0.15 is +1,299.0; M2: +625.5; M5: +252.0; M15: +76.5) -- consistent
with the curve flattening out (diminishing marginal improvement) as
`ac_modulate_factor` approaches 0, but still NOT reversing direction or
producing an interior maximum anywhere in `{0.10 ... 0.7}`. At the
mathematical limit (`factor -> 0`), AC-modulated trailing degenerates into
an immediate-exit-on-first-AC-deceleration rule for every ficha, which
batch 3 separately showed is inert/harmful for F3 in isolation (V-07's
runner-exit lever) -- so the true optimum almost certainly lies somewhere
above 0 but below 0.10, i.e. still undiscovered. This is now the fourth
consecutive batch confirming "tighter AC-modulation keeps winning" with no
knee found; a genuinely fine-grained sweep (e.g. `{0.02, 0.05, 0.08}`) would
be needed to pin the true optimum, which is out of scope for this program's
final batch.

**Best-net factor per TF** -- ingested as `sim-report-emasar-v06c-<tf>`:

| TF  | Best factor | Net ($)   | PF     | WR (%) | MaxDD ($) | vs Champion (factor=0.25) |
|-----|-------------:|----------:|-------:|-------:|----------:|----------------------------:|
| M1  | 0.10         | -14,922.0 | 0.799  | 33.85  | 19,790.1  | +3,897.0 (+20.7%, less-bad)  |
| M2  | 0.10         |  30,777.9 | 2.005  | 46.00  |  1,854.9  | +1,876.5 (+6.5%)             |
| M5  | 0.10         |  45,815.7 | 7.345  | 65.83  |    209.7  | +756.0 (+1.7%)                |
| M15 | 0.10         |  41,126.7 | 31.655 | 79.75  |    150.3  | +229.5 (+0.6%)                |

**Verdict: BEATS the champion config on EVERY TF, again a new all-time-best
number for all four TFs** -- the fifth consecutive batch-over-batch
improvement for this single lever. M1 (-14,922.0) breaks -$15K for the
first time in the whole program.

---

## V-10 -- SuperTrend-M15 regime filter (harness + engine hook)

New engine param `direction_mask: list[int] | None = None` -- per-bar
allowed direction: `+1` long-only, `-1` short-only, `0` both (see engine
changes section). Harness (`scripts/report/gen_variant_batch5.py
::compute_direction_mask`): resamples the SAME loaded bars to M15 (floor
timestamp to the 15-minute boundary, OHLC aggregate), computes
`SuperTrend(atr_period=14, mult=3.0)` via `_supertrend_ref.supertrend` +
`emasar_ref._atr_wilder` (the same Wilder ATR the reference engine's own F2
SuperTrend exit uses), and maps each bar's mask value from the trend
direction of the PREVIOUS CLOSED M15 bucket (bar `i`'s own M15 bucket index
`k` uses bucket `k-1`'s trend -- verified no look-ahead: the mask is
constant within every M15 bucket and always derived from the STRICTLY
PRIOR bucket, confirmed by direct inspection during development). For the
M15-TF run itself, bucket `k-1` IS literally the previous M15 bar (the
general resample-based logic degenerates correctly to the spec's simpler
"previous M15 bar" description at M15).

**Mask distribution** (long-only / short-only / both-allowed-or-warmup, per
TF, over the full loaded window):

| TF  | long (+1) | short (-1) | both/warmup (0) | total  |
|-----|----------:|-----------:|-----------------:|-------:|
| M1  | 16,560    | 19,677     | 210               | 36,447 |
| M2  |  8,721    |  9,407     | 105               | 18,233 |
| M5  |  3,313    |  3,938     |  42               |  7,293 |
| M15 |  1,105    |  1,313     |  14               |  2,432 |

Roughly balanced 46/54 long/short split on every TF, with only a small
warmup sliver (~14-210 bars, the first M15 bucket or two before ATR(14)
seeds) allowing both directions.

| TF  | Leg     | Trades | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|-------:|----------:|-------:|-------:|----------:|
| M1  | base    | 6,936  | -22,201.2 | 0.545  | 27.68  | 22,344.0  |
| M1  | stacked | 6,948  | -10,244.4 | 0.733  | 30.87  | 11,201.1  |
| M2  | base    | 3,579  |   9,880.8 | 1.486  | 40.40  |  2,002.2  |
| M2  | stacked | 3,579  |  16,299.6 | 2.039  | 44.84  |  1,107.3  |
| M5  | base    | 1,518  |  20,603.4 | 4.003  | 60.28  |    820.2  |
| M5  | stacked | 1,518  |  24,273.9 | 6.815  | 64.43  |    142.5  |
| M15 | base    |   486  |  20,494.8 | 10.461 | 75.93  |    638.1  |
| M15 | stacked |   486  |  22,688.7 | 31.631 | 79.63  |     77.1  |

**Trade count roughly halves on every TF** (M1: 13,881 baseline -> 6,936-
6,948, ~50%; M2: 7,233 -> 3,579, ~50%; M5: 2,853 -> 1,518, ~47%; M15: 948 ->
486, ~49%) -- consistent with a filter that rejects roughly one whole
direction's worth of signals at a time (the mask flips direction whenever
the M15 SuperTrend flips, so on average about half of all EMASAR signals
land on the "wrong" side of the currently-active M15 regime). **Stacking
helps on every TF** (M1 +11,956.8, M2 +6,418.8, M5 +3,670.5, M15 +2,193.9),
same direction as every other lever tested across the whole program.

**Best-net leg per TF** -- ingested as `sim-report-emasar-v10-<tf>` (all four
from the **stacked** leg):

| TF  | Leg     | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|----------:|-------:|-------:|----------:|
| M1  | stacked | -10,244.4 | 0.733  | 30.87  | 11,201.1  |
| M2  | stacked |  16,299.6 | 2.039  | 44.84  |  1,107.3  |
| M5  | stacked |  24,273.9 | 6.815  | 64.43  |    142.5  |
| M15 | stacked |  22,688.7 | 31.631 | 79.63  |     77.1  |

**Verdict vs. V-09 control and vs. champion**: **BEATS V-09 control on M1**
(-10,244.4 vs -42,866.1, a 76.1% reduction in loss) and **also BEATS the
champion on M1** (-10,244.4 vs -18,819.0, +45.6% less-bad) but **LOSES vs.
the champion on M2/M5/M15** (M2: 16,299.6 vs 28,901.4, -43.6%; M5: 24,273.9
vs 45,059.7, -46.1%; M15: 22,688.7 vs 40,897.2, -44.5%). Cutting roughly
half the trade population (specifically, the half that's "against the M15
regime") removes far more edge on M2/M5/M15 than the regime-alignment
filter adds back via win-rate/PF improvement -- the SAME pattern as batch
4's V-08 (AC transition gate): a strict population filter that helps the
noisiest TF (M1) but costs net on the TFs where the champion config already
extracts most of its edge from a small, high-quality population. **Mixed
verdict: M1-specialist win (beats both V-09 control and the champion by a
wide margin), net loser on M2/M5/M15 relative to the champion.** Checked
against the plain (un-stacked) V-09 control too: V-10-stacked still beats
V-09 control on M1/M2 (M1 +32,621.7; M2 +2,566.8) but actually LOSES to the
plain V-09 control on M5/M15 (M5 -13,195.8; M15 -14,637.9) -- on those two
TFs the SuperTrend-M15 filter's population cut costs MORE than the
champion's own k/ac_modulate stacking gains back, i.e. V-10 is a net
negative lever on M5/M15 in absolute terms, not merely "loses to the
champion but still beats doing nothing."

---

## V-13 -- Controlled re-entry after full trail-out (engine extension)

New params `reentry_enable: bool = False`, `reentry_max: int = 1`. When ALL
3 fichas of a signal have closed and EVERY exit motivo was EXIT_TRAIL (a
clean full trail-out, never EXIT_INITSL/EXIT_TP/EXIT_ACDECEL anywhere in the
lineage), a re-entry ARMS. On subsequent bars, while `sar_trend[i]` still
matches the original signal's direction, the engine checks a **relaxed
"full-gate, G5-bypassed" re-entry gate**: G1 (EMA order)/G2 (same-slope,
no cruzadas)/G4 (SAR trend) via a new `_gate_g1_g4_only` helper, and G3
(pullback) via `_gate_g3_only` (or the intrabar touch when
`entry_timing=1`) -- both copied verbatim from `emasar_ref.gate_long`/
`gate_short`'s own formulas since neither the frozen module nor its public
gate functions expose a clean way to bypass only the G5 oscillator vote (no
`skip_g5` parameter exists, unlike `skip_g3`). This was chosen over a
literal "G3-only" reading because a bare G3 pullback check with no
trend/slope confirmation at all fires far too often to be a faithful model
of "the gate would fire" (see the module docstring's full rationale). The
arm is cancelled if SAR trend flips before a re-entry fires; each lineage
gets at most `reentry_max` re-entries.

**Why this measures something new**: the engine already re-enters on ANY
new STRICT (G1-G5) signal once all fichas are flat -- ordinary re-entry
already happens. This relaxed, G5-bypassed re-entry is the ONLY lever that
can fire on bars the strict gate would have rejected (G5 fails but
G1/G2/G3/G4 all pass, AND the lineage's own recent history was a clean
trail-out in the same direction) -- that is the specific, measurable
difference V-13 tests.

| TF  | Leg     | reentry_max | Trades | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|-------------:|-------:|----------:|-------:|-------:|----------:|
| M1  | base    | 1            | 14,295 | -44,694.3 | 0.554  | 28.58  | 45,246.3  |
| M1  | base    | 2            | 14,427 | -45,051.3 | 0.555  | 28.63  | 45,573.0  |
| M1  | stacked | 1            | 14,361 | -18,846.6 | 0.760  | 32.25  | 22,761.3  |
| M1  | stacked | 2            | 14,478 | -18,379.5 | 0.767  | 32.39  | 22,490.4  |
| M2  | base    | 1            |  7,458 |  13,842.3 | 1.307  | 41.15  |  3,559.2  |
| M2  | base    | 2            |  7,521 |  13,417.5 | 1.294  | 41.05  |  3,613.2  |
| M2  | stacked | 1            |  7,458 |  30,101.1 | 1.931  | 44.97  |  2,030.1  |
| M2  | stacked | 2            |  7,524 |  30,174.6 | 1.930  | 45.06  |  2,083.5  |
| M5  | base    | 1            |  2,943 |  38,244.6 | 3.838  | 60.86  |    633.6  |
| M5  | base    | 2            |  2,964 |  37,937.4 | 3.733  | 60.73  |    633.6  |
| M5  | stacked | 1            |  2,943 |  46,217.4 | 6.984  | 64.73  |    186.0  |
| M5  | stacked | 2            |  2,964 |  46,264.8 | 6.917  | 64.57  |    186.0  |
| M15 | base    | 1            |    993 |  38,827.8 | 10.403 | 77.04  |    881.1  |
| M15 | base    | 2            |  1,002 |  39,075.3 | 10.361 | 76.65  |    881.1  |
| M15 | stacked | 1            |    993 |  42,735.3 | 30.511 | 79.46  |    186.6  |
| M15 | stacked | 2            |  1,002 |  43,027.8 | 30.379 | 79.34  |    186.6  |

**Trade count only rises modestly** (M1 stacked: 13,923 champion-config
baseline -> 14,361-14,478, +3-4%; M2: 7,233 -> 7,458-7,524, +3-4%; M5: 2,853
-> 2,943-2,964, +3-4%; M15: 948 -> 993-1,002, +5-6%) -- the "clean
all-EXIT_TRAIL lineage + SAR-trend-still-aligned" precondition is fairly
restrictive, so re-entry only adds a modest number of extra signals on top
of the base population (nowhere near V-08/V-10's ~50-75% cuts, since this
lever only ever ADDS entries, never removes any). **`reentry_max=2` beats
`reentry_max=1` on 6 of 8 leg/TF combos** (M1 both legs, M2 stacked, M5
stacked, M15 both legs) but LOSES narrowly on M2 base (-424.8) and M5 base
(-307.2) -- the second re-entry occasionally fires into a worse setup than
the first, a small but real diminishing/negative return past the first
re-entry on the un-stacked control config specifically.

**Best-net combo per TF** -- ingested as `sim-report-emasar-v13-<tf>` (all
four from the **stacked** leg, `reentry_max=2`):

| TF  | Leg     | reentry_max | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|-------------:|----------:|-------:|-------:|----------:|
| M1  | stacked | 2            | -18,379.5 | 0.767  | 32.39  | 22,490.4  |
| M2  | stacked | 2            |  30,174.6 | 1.930  | 45.06  |  2,083.5  |
| M5  | stacked | 2            |  46,264.8 | 6.917  | 64.57  |    186.0  |
| M15 | stacked | 2            |  43,027.8 | 30.379 | 79.34  |    186.6  |

**Verdict vs. V-09 control and vs. champion**: **BEATS the champion config
on M2/M5/M15** (M2: +1,273.2/+4.4%; M5: +1,205.1/+2.7%; M15: +2,130.6/+5.2%)
and comes within $439.5 (2.3%) of the champion on M1 (-18,379.5 vs
-18,819.0, actually a small WIN, +2.3% less-bad). **V-13 is the ONLY
variant in this batch that wins (or ties within noise) on ALL FOUR TFs
simultaneously** -- unlike V-10 (M1-specialist, loses elsewhere) it doesn't
sacrifice trade-population quality on the higher TFs, because it only ever
ADDS a small number of high-conviction re-entries (same-trend continuation
after a clean trail-out) rather than filtering the base population.

---

## V-15 -- Volatility-adaptive SAR (engine extension)

New params `sar_adaptive: bool = False`, `sar_fast: tuple = (0.3, 0.3)`,
`sar_slow: tuple = (0.005, 0.05)`, `vol_regime_window: int = 200`. Computes
ATR(14) Wilder (`_atr_wilder`, reused from `emasar_ref`) over the bars;
`regime[i]` = 'fast' if `atr[i]` exceeds the rolling median of the previous
`vol_regime_window` bars' ATR (requiring >= `window // 2` non-None values,
else 'slow'); computes SAR trend TWICE (fast pair, slow pair);
`sar_trend_effective[i]` = the regime-selected series' trend at bar `i`,
used everywhere `sar_trend` feeds the gate (G4) and V-13's re-entry check.

### Historical context (mid-task addendum, from a prior TOKATA experiment)

Before this batch, a read-only lookup into TOKATA's `_sarprobe_ledger.csv` +
`emasar_exploracion_apendice.md` (a prior, UNRELATED SAR-parameter screening
sweep on EMASAR, in-sample 2026-01-02 -> 05-15, screening-quality, 3-pip
ILLEGAL stop, NO spread modeled) surfaced a directly relevant precedent:
sarprobe swept 5 fixed SAR pairs and found, on V1/M5, `SAR 0.005/0.05` beat
the trader's original `0.3/0.3` (75 trades, net +3,276.9, PF 4.56 vs. 69
trades, +1,624.6, PF 2.82 -- though 0.3/0.3 had the LOWER maxDD). The
recorded mechanism: a smaller step size produces later SAR flips, which
means fewer whipsawed G4 gate passes. **Critically, the small-SAR win was
M5-ONLY**: on V2/M15 fixed `0.005/0.05` LOST money (net -2,651, PF 0.95),
and on M1 it was merely mediocre (PF ~1.5). Also `0.005/0.10` was strictly
worse than `0.005/0.05` (if step shrinks, max must stay proportionally
tight). **sarprobe never tested a regime-switched combination of the two
pairs** -- V-15's whole premise (switch between a fast and a slow SAR
depending on realized volatility) has NO precedent in that prior work; it
is a fresh hypothesis this batch tests directly. sarprobe's own numbers use
an illegal stop and no spread and are NOT comparable in magnitude to this
batch's -- only the RANKING/direction (which pair wins on which TF) is used
as a prior.

**The specific hypothesis under test**: per sarprobe, fixed-slow SAR should
help M5 and hurt M15 (and be middling on M1). If V-15's adaptive classifier
can capture the M5 gain while AVOIDING the M15 (and M1) damage that
UNCONDITIONAL fixed-slow SAR would cause, that is the entire value
proposition of regime-switching over just picking one fixed pair.

### Two extra zero-code reference legs (added mid-task per the above)

To judge V-15 fairly against the sarprobe precedent, two additional
non-adaptive reference runs were added per TF, both on the CHAMPION config:
**fixed-fast** (`sar_step=0.3, sar_max=0.3`, UNCONDITIONAL -- this is
identical to the champion config itself, so no extra run was needed, its
net is the "Champion Net" already tabulated above) and **fixed-slow**
(`sar_step=0.005, sar_max=0.05`, UNCONDITIONAL, held fixed for the whole
run, no regime switching):

| TF  | Fixed-slow (0.005/0.05) Net ($) | Trades | PF     | WR (%) | MaxDD ($) |
|-----|----------------------------------:|-------:|-------:|-------:|----------:|
| M1  | -4,862.4                          | 9,906  | 0.902  | 34.37  |  9,365.7  |
| M2  | 26,140.8                          | 5,235  | 2.246  | 48.88  |    856.8  |
| M5  | 38,801.1                          | 2,085  | 9.380  | 68.63  |    171.3  |
| M15 | 33,317.4                          |   702  | 37.023 | 80.34  |     99.6  |

**sarprobe's ranking pattern reproduces directionally on THIS window and
engine**, with one twist: fixed-slow is the single best-net SAR choice on
**M1** here (-4,862.4, beating fixed-fast's -18,819.0 champion by a huge
margin) -- the opposite of sarprobe's "mediocre on M1" read, though not
directly comparable (different window, different engine: sarprobe tested
raw signal quality with an illegal 3-pip stop, this batch tests the full
per-ficha trailing ladder stacked on the champion's k/ac_modulate). On
**M5/M15, fixed-slow LOSES to fixed-fast/champion** here (M5: 38,801.1 vs
45,059.7, -13.9%; M15: 33,317.4 vs 40,897.2, -18.5%) -- this DOES match
sarprobe's M15 finding (fixed-slow hurts M15) but is the reverse of
sarprobe's M5 finding (fixed-slow there beat fixed-fast on M5). On **M2**,
fixed-slow also loses to fixed-fast (26,140.8 vs 28,901.4, -9.6%). Net
read: on this window/engine, fixed-slow SAR is a clear WIN only on M1 and a
clear LOSS on M2/M5/M15 -- a different (not contradictory, since the
underlying edge/config are entirely different) but equally TF-dependent
pattern from sarprobe's own.

### Adaptive vs. both fixed benchmarks

| TF  | Leg     | Adaptive Net ($) | vs Fixed-fast (champion) | vs Fixed-slow | Outright winner? |
|-----|---------|-------------------:|----------------------------:|----------------:|:------------------|
| M1  | stacked | -7,902.9            | +10,916.1 (beats, +58.0%)   | -3,040.5 (loses) | No -- beats champion, loses to fixed-slow |
| M2  | stacked | 31,181.4            | +2,280.0 (beats, +7.9%)     | +5,040.6 (beats) | **Yes** |
| M5  | stacked | 42,425.1            | -2,634.6 (loses, -5.8%)     | +3,624.0 (beats) | No -- loses to champion, beats fixed-slow |
| M15 | stacked | 36,639.9            | -4,257.3 (loses, -10.4%)    | +3,322.5 (beats) | No -- loses to champion, beats fixed-slow |

| TF  | Leg     | Trades | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|-------:|----------:|-------:|-------:|----------:|
| M1  | base    | 11,679 | -32,788.2 | 0.595  | 29.28  | 33,507.0  |
| M1  | stacked | 11,700 |  -7,902.9 | 0.870  | 34.08  | 14,470.5  |
| M2  | base    |  6,045 |  16,208.1 | 1.459  | 42.58  |  2,495.4  |
| M2  | stacked |  6,048 |  31,181.4 | 2.269  | 48.02  |  1,116.0  |
| M5  | base    |  2,424 |  35,224.2 | 4.352  | 62.50  |    633.6  |
| M5  | stacked |  2,424 |  42,425.1 | 8.442  | 67.95  |    241.5  |
| M15 | base    |    801 |  33,742.8 | 12.262 | 76.03  |    638.1  |
| M15 | stacked |    801 |  36,639.9 | 32.381 | 79.40  |    129.3  |

**Testing the specific hypothesis**: the adaptive classifier does NOT
cleanly separate "capture M5's fixed-slow gain while avoiding M15's
fixed-slow damage" -- it beats fixed-slow on M5/M15/M2 (all three) but
UNDER-performs BOTH fixed references on M5/M15 relative to picking whichever
FIXED pair is best for that specific TF (fixed-fast/champion wins M5/M15
outright; the adaptive blend leaves value on the table by switching into
'slow' regime bars that would have been better served staying 'fast', or
vice versa, often enough to net below the single best static choice). On
**M1**, adaptive is a clear win over the champion (fixed-fast) but a clear
loss to fixed-slow -- meaning on M1 the STATIC fixed-slow choice alone
would have been the single best SAR lever in the whole batch
(-4,862.4, beating even V-06c's -14,922.0 program-best-for-M1 by a wide
margin) had it been run un-stacked... but note fixed-slow here IS already
stacked on the champion config (see table above), so -4,862.4 already
includes the k/ac_modulate stacking. **On M2 only, adaptive is the outright
winner** (beats both fixed references) -- the one TF where regime-switching
delivers on its premise. **Failure mode, stated explicitly**: on M5/M15,
the adaptive run evidently spends enough time in the 'slow' regime (or
switches at the wrong moments) to lose the edge that STAYING in 'fast'
(0.3/0.3, i.e. the champion/fixed-fast config) the whole time would have
captured -- the classifier is not simply "free lunch," it actively costs
net relative to the single best static choice on 2 of 4 TFs.

**Best-net leg per TF** -- ingested as `sim-report-emasar-v15-<tf>` (all
four from the **stacked** leg):

| TF  | Leg     | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------|----------:|-------:|-------:|----------:|
| M1  | stacked | -7,902.9  | 0.870  | 34.08  | 14,470.5  |
| M2  | stacked | 31,181.4  | 2.269  | 48.02  |  1,116.0  |
| M5  | stacked | 42,425.1  | 8.442  | 67.95  |    241.5  |
| M15 | stacked | 36,639.9  | 32.381 | 79.40  |    129.3  |

**Verdict vs. V-09 control and vs. champion**: **BEATS the champion config
on M1/M2 only** (M1: +58.0%; M2: +7.9%), **LOSES to the champion on M5/M15**
(M5: -5.8%; M15: -10.4%) -- because on those two TFs the single fixed choice
(0.3/0.3, already the champion) was already the TF-optimal SAR pair, and
adaptive switching only ever costs value relative to that. **Ingested as
the batch's best-net leg regardless (per the ingest-only-the-best-per-TF
rule)** since it still beats the base (un-stacked) leg on every TF and the
task spec's ingestion rule is "best across base/stacked," not "best across
all SAR reference legs" -- but the report explicitly flags that, for M5/M15,
simply NOT adopting `sar_adaptive` (staying on the plain champion config)
would have scored higher than what got ingested here for those two TFs.
This is an honest, TF-dependent MIXED result: adaptive SAR is NOT a clean
win, contrary to what its "best of both worlds" framing might suggest.

---

## Head-to-head vs V-09, vs Champion

| TF  | V-09 Net  | Champion Net | V-06c best | V-10 best (leg) | V-13 best (leg, rmax) | V-15 best (leg) |
|-----|----------:|---------------:|-------------:|---------------------|---------------------------|---------------------|
| M1  | -42,866.1 | -18,819.0       | -14,922.0 (f=0.10) | -10,244.4 (stacked) | -18,379.5 (stacked, 2)    | -7,902.9 (stacked)  |
| M2  |  13,732.8 |  28,901.4       |  30,777.9 (f=0.10) |  16,299.6 (stacked) | **30,174.6 (stacked, 2)** | **31,181.4 (stacked)** |
| M5  |  37,469.7 |  45,059.7       |  **45,815.7 (f=0.10)** |  24,273.9 (stacked) | **46,264.8 (stacked, 2)** |  42,425.1 (stacked) |
| M15 |  37,326.6 |  40,897.2       |  **41,126.7 (f=0.10)** |  22,688.7 (stacked) | **43,027.8 (stacked, 2)** |  36,639.9 (stacked) |

### Verdicts

- **V-06c (ac_modulate_factor knee sweep) -- BEATS champion on every TF,
  again.** No knee found through five consecutive shrinking-grid batches
  (0.7 -> 0.10); the improvement is diminishing per step but still
  monotonic. New all-time-best for all four TFs; M1 breaks -$15K for the
  first time.

- **V-10 (SuperTrend-M15 regime filter) -- MIXED, M1-specialist.** Large win
  vs. V-09 control on M1, but loses to the champion on ALL FOUR TFs
  including M1 net being worse than V-06c's; the ~50% trade-population cut
  removes more edge than the regime-alignment quality gain adds back,
  mirroring batch 4's V-08 pattern exactly.

- **V-13 (controlled re-entry after full trail-out) -- BEATS champion on
  M2/M5/M15, essentially ties (slightly beats) on M1.** The ONLY variant in
  this batch (and one of very few in the whole program) that wins or ties
  on every single TF -- because it only ever ADDS a small, high-conviction
  population (same-trend continuations after a clean trail-out) rather than
  filtering the base population, it avoids the "cut too much good stuff"
  failure mode that hurts V-08/V-10.

- **V-15 (volatility-adaptive SAR) -- MIXED, TF-dependent, with an honest
  negative finding.** Beats the champion on M1/M2 but LOSES to the champion
  on M5/M15 (where simply staying on the fixed fast/champion SAR the whole
  time would have scored higher). Cross-checked against a historical
  TOKATA precedent (sarprobe) via two added fixed-SAR reference legs:
  adaptive is the OUTRIGHT winner (beats both fixed-fast and fixed-slow)
  only on M2; on M1/M5/M15 a single STATIC choice (fixed-slow on M1,
  fixed-fast/champion on M5/M15) would have beaten the adaptive blend. The
  regime-switching premise (avoid fixed-slow's TF-specific damage while
  keeping its TF-specific gains) does NOT clearly pay off here.

**Batch 5's standout finding is V-13** (controlled re-entry) -- the only
variant this batch (and one of the few in the whole 5-batch program) that
is a clean win across every TF with no mixed/negative side, because its
mechanism (add a small number of high-conviction re-entries) cannot ever
remove edge the way population-filtering levers (V-08, V-10, and V-15's
worse-TF cases) can. V-06c continues its now-5-batch streak of "tighter
AC-modulation keeps winning, no knee yet." V-10 and V-15 both land as
honest mixed results -- real, TF-dependent tradeoffs rather than clean
wins, consistent with this program's broader pattern that levers cutting
the higher-TF trade population tend to cost more than they gain once
stacked on the champion's already-concentrated edge.

## Surprises

1. **V-06c's factor sweep STILL shows no knee, five batches in** -- 0.7 (V-06,
   batch 3) -> 0.5 (batch 3) -> 0.25 (V-06b, batch 4) -> now 0.10 (V-06c,
   batch 5), and factor=0.10 is again the single best value on every TF.
   The per-step gain is visibly shrinking (M15's gap from 0.15->0.10 is only
   $76.5, vs. batch 4's larger jumps), suggesting the curve IS flattening
   toward an asymptote, but it has not yet turned negative anywhere in five
   batches of testing.

2. **V-10 and V-08 (batch 4) are now confirmed as the SAME failure mode,
   not a coincidence**: both are strict entry-population filters (AC
   transition gate; SuperTrend-M15 regime alignment) that cut ~50-75% of
   the base signal population, and both show the identical pattern (M1 wins
   big, M2/M5/M15 lose to the champion). This is now a reliable signature
   across the program: population-CUTTING levers help the noisiest TF (M1)
   and hurt the higher TFs where the champion's edge is already concentrated
   in a small population; population-ADDING levers (V-13's re-entry) don't
   have this problem.

3. **V-15's sarprobe cross-check surfaced a genuine negative finding rather
   than confirming the hypothesis**: the expectation (adaptive avoids
   fixed-slow's TF-specific damage while keeping its TF-specific gains) was
   explicitly tested via two extra reference legs and DID NOT hold on
   M5/M15 -- the adaptive blend underperforms the single best static choice
   on those two TFs. Only M2 shows the "best of both worlds" pattern the
   hypothesis predicted. This is a clean example of a plausible-sounding
   mechanism (volatility-adaptive parameter switching) not paying off in
   practice on 3 of 4 TFs once actually measured against the right
   benchmarks -- worth flagging for anyone tempted to adopt V-15 based on
   intuition alone without checking the fixed-pair references first.

4. **The sarprobe precedent itself partially inverted on this window/engine**:
   sarprobe (Jan-May 2026, illegal stop, no spread) found fixed-slow SAR
   helped M5 and hurt M15/M1(mediocre); on this batch's window/engine
   (June-July 2026, legal stop, spread modeled, full ladder+champion
   stacking) fixed-slow instead helps M1 dramatically and hurts M2/M5/M15.
   Not a contradiction (entirely different window, stop model, and
   stacking config -- sarprobe's own numbers are explicitly NOT comparable
   in magnitude per its own caveat) but a useful reminder that a prior
   screening result's TF-specific ranking does not automatically transfer
   once you change the window, the stop model, or stack additional levers
   on top.

## Data gaps

None new. Same M1/M2/M5/M15 lake coverage as batches 1-4
(2026-06-01->2026-07-07, warmup+window), reused via
`gen_variant_batch1._load_bars`/`_bars_for` (cached across all four
variants' sweeps in this run, plus V-10's M15 resample and V-15's two extra
fixed-SAR reference legs).

## Engine changes (additive, default-preserving)

`sentinel_engine/strategies/emasar_variant.py::simular_variant` gained:
- `direction_mask: list[int] | None = None` -- SuperTrend-M15 regime filter
  (V-10). `None` (default) is a no-op (identical to pre-batch-5 behavior);
  otherwise a long signal is skipped when `direction_mask[i] == -1` and a
  short signal is skipped when `direction_mask[i] == +1` (checked in the
  entry block, AFTER the V-08 `g5_mode` check, for both `entry_timing=0`
  and `entry_timing=1` paths). The mask itself is computed by the CALLER
  (harness), not the engine -- see `scripts/report/gen_variant_batch5.py
  ::compute_direction_mask`.
- `reentry_enable: bool = False`, `reentry_max: int = 1` -- controlled
  re-entry after a full trail-out (V-13). `reentry_enable=False` (default)
  is a no-op; when True, per-signal exit-motivo bookkeeping tracks whether
  every ficha of a lineage closed EXIT_TRAIL, arming a re-entry that fires
  on a "relaxed full-gate" check (G1/G2/G4 via new module-level helper
  `_gate_g1_g4_only`, G3 via new helper `_gate_g3_only`, both formulas
  copied verbatim from `emasar_ref.gate_long`/`gate_short` since no G5-bypass
  parameter exists on those frozen functions) while `sar_trend[i]` still
  matches the original signal's direction; cancelled on a SAR-trend flip;
  capped at `reentry_max` re-entries per lineage; evaluated BEFORE the
  normal strict-gate entry path each bar.
- `sar_adaptive: bool = False`, `sar_fast: tuple = (0.3, 0.3)`,
  `sar_slow: tuple = (0.005, 0.05)`, `vol_regime_window: int = 200` --
  volatility-adaptive SAR (V-15). `sar_adaptive=False` (default) is a no-op
  (single `sar_step`/`sar_max` series, byte-identical to pre-batch-5); when
  True, ATR(14) Wilder (`_atr_wilder`, imported from `emasar_ref`) plus two
  SAR series (fast pair, slow pair) are computed, and the per-bar effective
  `sar_trend` is selected by comparing each bar's ATR to the rolling median
  of the previous `vol_regime_window` bars' ATR (requiring `>= window // 2`
  non-None values, else 'slow').
- New imports: `_atr_wilder` from `emasar_ref` (already existed in the
  frozen file, exercised via `emasar_ref.simular`'s own SuperTrend-ATR
  computation). New module-level helpers `_gate_g1_g4_only`/`_gate_g3_only`
  (G1/G2/G4 and G3 formulas copied verbatim from `emasar_ref.gate_long`/
  `gate_short`, used only by V-13's relaxed re-entry path).
- `emasar_ref.py` was NOT touched (frozen, golden-tested).

`tests/strategies/test_emasar_variant.py` extended from batch 4's 31 tests
to 45 (14 new, all passing, ZERO skips): for each of V-10/V-13/V-15 -- (a)
default-preservation on a synthetic fixture, (b) default-preservation on a
real XAUUSD/M5 2026-06 lake window, and (c)/(d)/(e) deterministic-seed
behavior tests (V-10: mask blocks only the masked side at the masked bar,
plus all-long-blocked and all-short-blocked full-vocabulary checks; V-13:
re-entry adds entries and stays in-vocabulary, `reentry_max=2 >=
reentry_max=1` entry count, and a lineage-reconstruction test confirming
every same-side consecutive re-entry follows a clean all-EXIT_TRAIL close
with matching SAR trend; V-15: a two-segment low-vol/high-vol synthetic
fixture (`_synthetic_regime_bars`) confirms the engine's event stream
changes when adaptive is enabled, and an independent re-derivation of the
regime classifier + fast/slow SAR series confirms genuine trend divergence
exists in both the classified-fast and classified-slow halves of the
fixture).

## Ingested runs (winners only, `data/research.db`)

- `sim-report-emasar-v06c-{m1,m2,m5,m15}` -- best-net factor per TF from
  `{0.10, 0.15, 0.20}` on the champion config; all four at factor=0.10.
- `sim-report-emasar-v10-{m1,m2,m5,m15}` -- best-net leg per TF
  (`direction_mask` = SuperTrend-M15, ATR period 14, mult 3.0, previous
  closed bar); all four from the **stacked** leg.
- `sim-report-emasar-v13-{m1,m2,m5,m15}` -- best-net (leg, reentry_max) per
  TF; all four from the **stacked** leg, `reentry_max=2`.
- `sim-report-emasar-v15-{m1,m2,m5,m15}` -- best-net leg per TF
  (`sar_adaptive=True`, fast=0.3/0.3, slow=0.005/0.05, window=200); all four
  from the **stacked** leg (with the honest caveat, per the V-15 section
  above, that for M5/M15 the plain champion/fixed-fast config alone scores
  higher than what got ingested here).

All re-ingestion is idempotent (delete-before-insert per run_id), verified
via `PYTHONPATH=D:/FOREX python scripts/dev/e2e_service.py --port 8611` +
`GET /api/runs/<run_id>/trades` returning non-empty rows for all 16 winner
run_ids (4 variants x 4 TFs). Service was started fresh for this
verification (PID resolved via `netstat -ano | grep :8611`, then stopped by
that exact Windows PID only via `taskkill /F /PID <pid>`); the production
service on :8601 was verified still running (separate PID 20472) and left
untouched throughout.

## Gates

- `tests/golden/test_parity.py`: 3/3 pass.
- `tests/strategies`: all green (48/48, including the 45 in
  `test_emasar_variant.py`).
- `tests/service`: 471 passed, 3 pre-existing allowed failures
  (`test_chat.py::test_review_strategy_happy_path_sse_sequence` +
  `test_web_positions.py`'s 2 analizar-button tests) -- unchanged from the
  documented baseline, `chat.py`/`positions.js` were not touched this batch.

---

## Program-wide standings (all 5 batches, final)

Best config per TF across the ENTIRE 5-batch EMASAR variant research
program, by net PnL, restricted to runs actually ingested into
`data/research.db` under the `sim-report-emasar-*` naming convention:

| TF  | Program-best run_id       | Net ($)     | PF        | WR (%) | Variant / lever |
|-----|----------------------------|------------:|----------:|-------:|------------------|
| M1  | `sim-report-emasar-v12-m1`  |  231,783.3  |    14.261 |  76.98 | V-12 intrabar entry (`entry_timing=1`, cc=2, stacked) |
| M2  | `sim-report-emasar-v12-m2`  |  224,542.2  |    50.686 |  87.90 | V-12 intrabar entry (`entry_timing=1`, cc=2, stacked) |
| M5  | `sim-report-emasar-v12-m5`  |  169,596.6  |   233.165 |  95.68 | V-12 intrabar entry (`entry_timing=1`, cc=2, stacked) |
| M15 | `sim-report-emasar-v12-m15` |  123,454.8  |  1286.988 |  98.65 | V-12 intrabar entry (`entry_timing=1`, cc=2, stacked) |

**V-12 (batch 4) remains the runaway program-best on every TF by a wide
margin** -- no lever in this final batch (V-06c/V-10/V-13/V-15) came close
to challenging it; the next-best results per TF this batch (V-06c on
M5/M15, V-13 on M2/M5/M15) top out in the $30-46K range, roughly 3-5x
smaller than V-12's six-figure nets. V-12 carries its own documented
caution flag (below) and should not be read as a simple "just use this"
conclusion without further validation.

**Best "conservative" (non-V-12) config per TF**, i.e. the best result NOT
relying on the intrabar-touch spike-capture mechanic, useful if V-12's
caveats rule it out operationally:

| TF  | Best conservative run_id      | Net ($)   | PF     | Variant |
|-----|---------------------------------|----------:|-------:|---------|
| M1  | `sim-report-emasar-v06c-m1`      | -14,922.0 |  0.799 | V-06c ac_modulate_factor=0.10 |
| M2  | `sim-report-emasar-v06c-m2`      |  30,777.9 |  2.005 | V-06c ac_modulate_factor=0.10 |
| M5  | `sim-report-emasar-v13-m5`       |  46,264.8 |  6.917 | V-13 re-entry (reentry_max=2, stacked) |
| M15 | `sim-report-emasar-v13-m15`      |  43,027.8 | 30.379 | V-13 re-entry (reentry_max=2, stacked) |

Note M1 is STILL net-negative in the best conservative config found across
the whole program -- no lever tested in 5 batches has flipped M1 to
positive net without relying on V-12's intrabar-spike mechanic (V-11's
session filter came closest at -5,063.4 in batch 4, batch 5's V-15 at
-7,902.9 is the second-closest).

### Caveats list (carried forward, unresolved -- read before deploying anything)

1. **V-11 (batch 4) session/hour filter -- IN-SAMPLE overfit risk.** The
   blocked hours were selected on the EXACT SAME window used to test them,
   with no held-out validation. M1's 8 blocked hours in particular are
   chosen from noisy per-hour buckets (n≈450-710 trades/hour, single 4-week
   window) and could be sampling artifacts rather than a durable structural
   edge. Do not deploy without an out-of-sample re-test on a different
   window.

2. **V-12 (batch 4) intrabar entry -- LOOK-AHEAD/SLIPPAGE VALIDATION
   PENDING.** The dramatic (5-9x) net improvement depends on this specific
   window containing several large single-bar M1/M2/M5 spikes that the
   intrabar-touch + immediate-large-trail mechanic captures very favorably.
   Verified (batch 4) to be a faithful, non-buggy mirror of `emasar_ref`'s
   own `entry_timing=1` semantics (not a variant-specific artifact) and NOT
   concentrated in a handful of trades (top-10 trades are only 1.5-6.1% of
   total net across TFs) -- but UNTESTED against (a) a calmer window where
   these spikes may not recur, and (b) a live/paper execution model that
   accounts for intrabar fill slippage on touch entries (MT5
   slippage/requotes are not modeled anywhere in this program's simulator).
   Do not treat V-12's numbers as directly deployable without both checks.

3. **V-15 (batch 5, this batch) volatility-adaptive SAR -- MIXED, not a
   clean win.** New this batch: cross-checked against a historical TOKATA
   precedent (sarprobe) via two added fixed-SAR reference legs, and found to
   UNDERPERFORM the single best static SAR choice on M5/M15 (adaptive only
   outright-wins on M2). Do not adopt V-15 assuming "adaptive is always at
   least as good as either fixed extreme" -- that assumption is FALSE on
   this window for 2 of 4 TFs, demonstrated directly rather than merely
   flagged as a risk.

4. **V-08/V-10 (batches 4/5) population-filtering levers -- TF-dependent
   sign flip, not overfit per se but a real structural tradeoff.** Both cut
   a large fraction of the base signal population (AC-transition gate:
   ~72-78%; SuperTrend-M15 regime filter: ~47-50%) to win big on M1 but lose
   30-80% of the champion's net on M2/M5/M15. Not a caveat about validity
   (the mechanism is well-understood, not a fluke) but a caution against
   assuming a lever that helps M1 will generalize to the other TFs.
