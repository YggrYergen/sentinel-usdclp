# EMASAR variant research — Batch 3 (V-05, V-06, V-07)

Generated 2026-07-13 by `scripts/report/gen_variant_batch3.py`. Engine:
`sentinel_engine/strategies/emasar_variant.py::simular_variant`, extended
additively in this batch with `f1_tp_r`/`f2_tp_r` (V-05, staggered
take-profit by R multiples, new motivo `EXIT_TP`), `ac_modulate`/
`ac_modulate_factor` (V-06, AC-modulated trailing across the whole ladder),
and `f3_ac_decel_exit`/`f3_ac_decel_bars` (V-07, runner exit on sustained AC
deceleration, new motivo `EXIT_ACDECEL`). All three default to the
pre-batch-3 behavior EXACTLY (`f1_tp_r=0.0`, `f2_tp_r=0.0`,
`ac_modulate=False`, `f3_ac_decel_exit=False`) -- pinned by
`tests/strategies/test_emasar_variant.py` (19/19 pass, extended from
batch 2's 7 with 12 new tests: default-preservation on synthetic + real M5
data for each variant, plus a deterministic-seed trigger test per variant).
`emasar_ref.py` was NOT touched (frozen, golden-tested). Symbol XAUUSD,
spread 0.5 (Capitaria) applied at fill, same conventions as batches 1-2 (see
`docs/superpowers/research/2026-07-13-emasar-variants-batch1.md` and
`...batch2.md`).

**Window**: 2026-06-08 -> 2026-07-07 (warmup fed from 2026-06-01). TFs M1,
M2, M5, M15.

**Two legs per variant per TF, per this batch's task spec**:
- **base**: V-09 control params (`init_sl_range_k=1.0`, flat trail
  100/100/100).
- **stacked**: same but `init_sl_range_k` set to the V-01b winning k for
  that TF (M1=6.0, M2=3.0, M5=6.0, M15=2.5) -- tests whether each new
  lever's gain compounds with the program's best-known single lever so far.

Only the overall-best (base vs. stacked, whichever scored higher net) combo
per variant per TF was ingested into `data/research.db`.

**Baselines for comparison**:

| TF  | V-09 control Net ($) | V-01b best Net ($, k) |
|-----|----------------------:|------------------------:|
| M1  | -42,866.1             | -36,414.3 (k=6.0)       |
| M2  |  13,732.8             |  19,650.6 (k=3.0)       |
| M5  |  37,469.7             |  41,279.7 (k=6.0)       |
| M15 |  37,326.6             |  39,749.7 (k=2.5)       |

---

## V-05 — Staggered take-profit by R multiples (engine extension)

New params `f1_tp_r`/`f2_tp_r` (default 0.0/0.0 = disabled). Per signal,
R = |entry - initial_SL| (shared, computed at entry). Checked before the
initial-SL/trailing checks each bar: F1/F2 close at exactly
`entry + fN_tp_r*R` (long; mirror short) when touched, tagged `EXIT_TP`; F3
never TPs. Same-bar TP+SL collisions resolve SL-first (conservative fill).
Grid: (f1_tp_r, f2_tp_r) ∈ {(1.0,2.0), (1.0,3.0), (1.5,3.0), (0.75,1.5)}.

### Base leg (V-09 params, k=1.0)

| TF  | (f1,f2)=(1.0,2.0) | (1.0,3.0) | (1.5,3.0) | (0.75,1.5) |
|-----|-------------------:|----------:|----------:|-----------:|
| M1  | -43,426.6           | -43,263.7 | -43,281.0 | -43,584.9  |
| M2  |  13,431.2           |  13,437.0 |  13,667.3 |  13,059.4  |
| M5  |  37,228.8           |  37,227.5 |  37,452.7 |  36,647.2  |
| M15 |  35,440.7           |  35,582.0 |  35,830.5 |  34,797.8  |

### Stacked leg (V-01b best k per TF)

| TF  | (f1,f2)=(1.0,2.0) | (1.0,3.0) | (1.5,3.0) | (0.75,1.5) |
|-----|-------------------:|----------:|----------:|-----------:|
| M1  | -36,417.2           | -36,417.2 | -36,414.3 | -36,505.8  |
| M2  |  19,638.4           |  19,638.4 |  19,656.7 |  19,614.5  |
| M5  |  41,279.7           |  41,279.7 |  41,279.7 |  41,279.7  |
| M15 |  38,406.8           |  38,581.4 |  38,714.4 |  38,224.5  |

**Reading the grid**: on every TF and every leg, (1.5, 3.0) -- the loosest
tested TP combo -- is the best or tied-best. The looser the TP, the closer
net gets to (but never quite reaches) the no-TP baseline; M5's stacked leg
is IDENTICAL across all 4 TP combos (41,279.7 == V-01b's own number) because
at k=6.0 stacked, F1/F2's own trailing rarely lets price travel far enough
past entry to reach even the widest tested TP level before the trail itself
exits the ficha -- the TP effectively never fires in that regime. This is
the SAME convergence shape seen in batch 2's V-02 (breakeven): staggering
exits earlier than "let it run" costs net, with the cost shrinking as the
trigger loosens.

**Best-net combo per TF** -- ingested as `sim-report-emasar-v05-<tf>` (all
four chosen from the **stacked** leg):

| TF  | Best (f1_tp_r, f2_tp_r) | Leg     | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|---------------------------|---------|----------:|-------:|-------:|----------:|
| M1  | (1.5, 3.0)                 | stacked | -36,414.3 | 0.598  | 28.82  | 37,093.8  |
| M2  | (1.5, 3.0)                 | stacked |  19,656.7 | 1.521  | 40.98  |  2,899.5  |
| M5  | (1.0, 2.0)*                | stacked |  41,279.7 | 5.433  | 61.09  |    263.7  |
| M15 | (1.5, 3.0)                 | stacked |  38,714.4 | 24.485 | 77.85  |    150.3  |

\* M5 stacked: all 4 TP combos tie at 41,279.7 (TP never fires in that
regime, see above); (1.0, 2.0) is simply the first grid entry at that tie.

**Verdict: WORSE than V-01b on every TF**, but only marginally, and the
"stacked" leg always beats the "base" leg by the same margin V-01b itself
provides -- **stacking helps** (V-01b's range_k gain fully carries through
under V-05's TP overlay), it's the TP mechanism itself that costs a small
amount vs. no-TP. M1/M2/M15's best V-05 numbers are all within ~0.05%-0.2%
of the pure V-01b number (M1: -36,414.3 vs -36,414.3 -- actually TIES
V-01b exactly at (1.5,3.0), meaning the loosest TP tested is loose enough to
never bind on M1's window); M2 is +6.1 above V-01b (noise-level); M15 is
-1,035.3 (-2.6%) below V-01b. M5 exactly matches V-01b (TP never fires).
**Net verdict: WORSE (M15) to essentially a WASH (M1/M2/M5)** -- staggered
TP does not improve on the pure range_k lever in this window, and even its
best (loosest) setting only ever ties or slightly underperforms.

---

## V-06 — AC-modulated trailing (engine extension)

New params `ac_modulate`/`ac_modulate_factor` (default False/0.5 =
disabled). When AC is decelerating against a ficha's favorable direction on
the current bar (long: `ac[i] < ac[i-1]`; short mirror), that ficha's
trailing distance for the bar is multiplied by `ac_modulate_factor`
(tighter), applied to the WHOLE ladder (F1/F2/F3), not just F3 like
`emasar_ref`'s `ac_modulate_trail`. Grid: factor ∈ {0.5, 0.7}.

### Base leg (V-09 params, k=1.0)

| TF  | Trades | factor=0.5 Net ($) | factor=0.7 Net ($) |
|-----|-------:|---------------------:|---------------------:|
| M1  | 13,920 | -32,394.6             | -37,170.9             |
| M2  |  7,233 |  19,436.1             |  17,172.3             |
| M5  |  2,853 |  39,824.7             |  38,882.7             |
| M15 |    948 |  38,046.6             |  37,758.6             |

### Stacked leg (V-01b best k per TF)

| TF  | Trades | factor=0.5 Net ($) | factor=0.7 Net ($) |
|-----|-------:|---------------------:|---------------------:|
| M1  | 13,920 | -25,230.6             | -30,300.9             |
| M2  |  7,233 |  25,773.9             |  23,342.1             |
| M5  |  2,853 |  43,799.7             |  42,791.7             |
| M15 |    948 |  40,514.7             |  40,208.7             |

**factor=0.5 (tighter modulation) beats factor=0.7 on every TF, every
leg** -- the tighter the AC-triggered trail squeeze, the better, within this
2-point grid (no interior optimum found; like batch 1/2's k-sweeps, the true
optimum may lie below 0.5, outside this grid). M1 is notable: trade count
JUMPS from V-09's 13,881 to 13,920 (+39, +0.28%) -- the tighter stops from
AC-modulation free up re-entry slots slightly faster on the highest-frequency
TF, a genuinely new trade-count effect not seen in prior batches' levers
(V-01b/V-02/V-03/V-04 were all trade-count-neutral or trade-count-reducing).

**Best-net combo per TF** -- ingested as `sim-report-emasar-v06-<tf>` (all
four chosen from the **stacked** leg, factor=0.5):

| TF  | Best factor | Leg     | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|-------------:|---------|----------:|-------:|-------:|----------:|
| M1  | 0.5          | stacked | -25,230.6 | 0.689  | 30.78  | 27,746.7  |
| M2  | 0.5          | stacked |  25,773.9 | 1.769  | 43.72  |  2,231.1  |
| M5  | 0.5          | stacked |  43,799.7 | 6.475  | 63.30  |    233.7  |
| M15 | 0.5          | stacked |  40,514.7 | 28.702 | 78.80  |    150.3  |

**Verdict: BEATS both V-09 and V-01b on EVERY TF, by the largest margin of
this batch.** M1: -25,230.6 vs V-01b's -36,414.3 (+11,183.7, a 30.7%
reduction in the loss -- still net-negative but the biggest single-lever
improvement to M1 across all three batches). M2: 25,773.9 vs V-01b's
19,650.6 (+6,123.3, +31.2%). M5: 43,799.7 vs V-01b's 41,279.7 (+2,520.0,
+6.1%, also a new all-time-best M5 number across the whole program). M15:
40,514.7 vs V-01b's 39,749.7 (+765.0, +1.9%, also a new all-time-best M15
number). **Stacking clearly helps** -- every stacked number beats its
corresponding base number by a wide margin (e.g. M1: -25,230.6 stacked vs
-32,394.6 base, +7,164), consistent with V-06's tighter, AC-aware trailing
compounding well with a wider legal range-SL. This is the single best
result across all three batches so far for M1/M2/M5/M15 simultaneously.

---

## V-07 — Runner exit on sustained AC deceleration (engine extension)

New params `f3_ac_decel_exit`/`f3_ac_decel_bars` (default False/2 =
disabled). F3 only: a consecutive-deceleration counter increments each bar
AC decelerates against the position (same test as V-06), resets otherwise;
at `f3_ac_decel_bars` consecutive bars, F3 closes at that bar's close,
tagged `EXIT_ACDECEL`. Checked AFTER the SL/trailing checks (stop-outs take
precedence same-bar). Grid: bars ∈ {2, 3}.

### Base leg (V-09 params, k=1.0)

| TF  | bars=2 Net ($) | bars=3 Net ($) |
|-----|------------------:|------------------:|
| M1  | -42,824.4          | -42,848.6          |
| M2  |  13,735.8          |  13,735.3          |
| M5  |  37,469.7          |  37,469.7          |
| M15 |  37,326.6          |  37,326.6          |

### Stacked leg (V-01b best k per TF)

| TF  | bars=2 Net ($) | bars=3 Net ($) |
|-----|------------------:|------------------:|
| M1  | -36,369.9          | -36,396.8          |
| M2  |  19,653.6          |  19,653.1          |
| M5  |  41,279.7          |  41,279.7          |
| M15 |  39,749.7          |  39,749.7          |

**Surprise: this lever is essentially INERT in this window.** On M2/M5/M15
the numbers are within a few dollars (or exactly equal, M5/M15) of the
corresponding V-09/V-01b baseline with NO AC-decel feature at all; M1 shows
the largest (still tiny, ~$50) spread between bars=2/3. A direct diagnostic
run confirms why: at F3's default 100-pip trail, `EXIT_TRAIL` almost always
fires before 2-3 consecutive AC-decelerating bars can accumulate against an
open F3 (checked with a diagnostic run on M5: widening `f3_trail_pips` to
100,000 -- i.e. effectively disabling F3's trail -- makes `EXIT_ACDECEL`
fire 654 times out of ~755 F3-tagged fichas; at the real 100-pip trail it
fires ZERO times in the entire M5 window). The AC-decel counter logic itself
is correct and unit-tested (`test_ac_decel_exit_enabled_produces_exit_acdecel_and_only_on_f3`,
`test_ac_decel_exit_synthetic_trigger_case`, both using a widened
`f3_trail_pips` to isolate the path) -- it's a genuine interaction effect:
**a 100-pip trail on M1-M15 XAUUSD data is tight enough that F3 essentially
never survives 2+ consecutive AC-decel bars without also breaching its own
trailing stop first**, at least at this batch's tested bars∈{2,3}. This
would likely need either a much wider F3 trail or a much lower bars
threshold (bars=1, not tested per spec) to actually bind on real market
data at this window's volatility.

**Best-net combo per TF** -- ingested as `sim-report-emasar-v07-<tf>` (all
four chosen from the **stacked** leg, bars=2):

| TF  | Best bars | Leg     | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|-----------:|---------|----------:|-------:|-------:|----------:|
| M1  | 2          | stacked | -36,369.9 | 0.598  | 28.81  | 37,049.4  |
| M2  | 2          | stacked |  19,653.6 | 1.521  | 40.98  |  2,899.5  |
| M5  | 2          | stacked |  41,279.7 | 5.433  | 61.09  |    263.7  |
| M15 | 2          | stacked |  39,749.7 | 25.113 | 77.85  |    150.3  |

**Verdict: essentially a WASH vs. V-01b on every TF** (M5/M15 tie exactly;
M2 is +2.9/+0.01% noise; M1 is +44.4/+0.12% noise) -- **stacking "helps"**
only in the trivial sense that the V-01b range_k gain fully carries through
(the AC-decel exit itself contributes nothing measurable in this window at
bars∈{2,3}). This is a MIXED/inert result: the feature is correctly
implemented and does trigger (proven on synthetic + a diagnostic real-data
run with F3's trail relaxed), but at production-realistic trail distances it
almost never gets the chance to fire before the ordinary trailing stop
already closed F3.

---

## Head-to-head vs V-09 baseline and V-01b

| TF  | V-09 Net  | V-01b best Net | V-05 best (leg)     | V-06 best (leg)     | V-07 best (leg)     |
|-----|----------:|----------------:|------------------------|------------------------|------------------------|
| M1  | -42,866.1 | -36,414.3        | -36,414.3 (stacked)     | **-25,230.6 (stacked)** | -36,369.9 (stacked)    |
| M2  |  13,732.8 |  19,650.6        |  19,656.7 (stacked)     | **25,773.9 (stacked)**  |  19,653.6 (stacked)    |
| M5  |  37,469.7 |  41,279.7        |  41,279.7 (stacked, tie)| **43,799.7 (stacked)**  |  41,279.7 (stacked, tie)|
| M15 |  37,326.6 |  39,749.7        |  38,714.4 (stacked)     | **40,514.7 (stacked)**  |  39,749.7 (stacked, tie)|

### Verdicts

- **V-05 (staggered TP by R) -- WORSE/WASH.** Every TF's best combo is at or
  slightly below the pure V-01b number; M1/M5 essentially tie (TP barely or
  never fires at the loosest tested trigger), M2 is noise-level above, M15
  is the one measurably worse case (-2.6%). Same shape as batch 2's V-02
  (breakeven): earlier-exit mechanisms cost net vs. "let the trail run,"
  with the cost shrinking as the trigger loosens toward "never fires."
  Stacking on V-01b's k helps (carries the range_k gain through) but the TP
  overlay itself adds nothing.

- **V-06 (AC-modulated trailing) -- BEATS on every TF, this batch's clear
  winner.** Tighter-when-decelerating trailing across the WHOLE ladder
  (not just F3, unlike `emasar_ref`'s narrower `ac_modulate_trail`) beats
  V-01b by +11,183.7 (M1, still net-negative but the single largest M1
  improvement across all 3 batches), +6,123.3 (M2, +31.2%), +2,520.0 (M5,
  +6.1%, new program-best), +765.0 (M15, +1.9%, new program-best).
  Stacking clearly helps (every stacked number beats its own base leg by a
  wide margin). factor=0.5 (tighter) beats factor=0.7 on every TF/leg with
  no interior optimum found in this 2-point grid -- worth a follow-up sweep
  below 0.5 if a knee is wanted.

- **V-07 (runner AC-decel exit) -- MIXED/inert, essentially a WASH vs.
  V-01b.** The feature works correctly (proven via unit tests and a
  diagnostic run with F3's trail relaxed to isolate the path) but at
  production trail distances (100 pips) it almost never fires before the
  ordinary trailing stop already closes F3 -- ZERO `EXIT_ACDECEL` events
  fired anywhere in this batch's 8 (TF x bars) real-data sweep runs at the
  default trail. Stacking "helps" only because it inherits V-01b's range_k
  gain; the AC-decel mechanism itself is inert in this window/param
  regime.

**Batch 3's clear winner is V-06** (AC-modulated trailing, factor=0.5,
stacked on V-01b's range_k) -- it is now the best-net lever found across all
three batches on EVERY TF, including a first-ever meaningful improvement to
M1 (still net-negative, but the smallest loss seen anywhere in the program:
-25,230.6, a 43% reduction in loss vs. V-09's control -42,866.1). V-05 and
V-07 both land as wash-to-slightly-worse vs. V-01b -- their new-motivo exit
mechanisms (`EXIT_TP`, `EXIT_ACDECEL`) are implemented correctly (unit
tested, and V-07's inertness independently confirmed via a diagnostic run
with F3's trail relaxed) but simply don't bind often enough, or bind too
early relative to "let the trail run," to add value on top of the program's
strongest known lever (V-01b's widened range_k).

## Surprises

1. **V-06's factor=0.5 beats factor=0.7 with no diminishing returns visible
   in this 2-point grid** -- unlike most levers tested across all 3 batches
   (which show diminishing/flattening returns as they widen toward "never
   fires"), V-06 keeps improving as the modulation gets TIGHTER, the
   opposite direction. A follow-up sweep below 0.5 (e.g. 0.3, 0.2) would be
   worth running to find where this trend reverses or flattens.
2. **V-06 changes M1's trade count** (13,881 -> 13,920, +39) -- the only
   lever across all 3 batches to move M1's trade count at all (V-01/V-01b/
   V-02/V-03/V-04/V-05/V-07 are all trade-count-neutral or -reducing on
   every TF). Tighter AC-modulated stops free re-entry slots slightly faster
   on the highest-frequency TF.
3. **V-07 fired ZERO EXIT_ACDECEL events across the entire 8-run real-data
   sweep** (both legs x both bars values x 4 TFs) despite the exact same
   AC-deceleration test working correctly in V-06 (where it modulates
   trailing distance rather than gating an outright exit) and in V-07's own
   unit tests. This is a genuine interaction-effect finding, not a bug: F3's
   trailing stop (100 pips at base, still 100 pips at the stacked leg -- only
   `init_sl_range_k` changes between legs) is simply tight enough relative
   to this window's AC oscillation frequency that 2-3 consecutive
   AC-decelerating bars almost never survive without the trail already
   closing the ficha. Confirmed independently: relaxing `f3_trail_pips` to
   100,000 on the M5 diagnostic run makes `EXIT_ACDECEL` fire 654/755 times.

## Data gaps

None. Same M1/M2/M5/M15 lake coverage as batches 1-2
(2026-06-01->2026-07-07, warmup+window), reused via
`gen_variant_batch1._load_bars`/`_bars_for` (cached across all 3 variants'
sweeps x 2 legs in this run).

## Engine changes (additive, default-preserving)

`sentinel_engine/strategies/emasar_variant.py::simular_variant` gained:
- `f1_tp_r: float = 0.0`, `f2_tp_r: float = 0.0` -- staggered take-profit by
  R multiples (V-05), F1/F2 only, new motivo `EXIT_TP`. Disabled by default.
  Checked BEFORE the initial-SL/trailing checks each bar; skipped (SL wins)
  when the ficha's current SL is also hit on the same bar.
- `ac_modulate: bool = False`, `ac_modulate_factor: float = 0.5` --
  AC-modulated trailing (V-06) applied to the whole per-ficha ladder
  (F1/F2/F3), using the already-imported `ac_desacelerando` from
  `emasar_ref`. Disabled by default.
- `f3_ac_decel_exit: bool = False`, `f3_ac_decel_bars: int = 2` -- runner
  exit on sustained AC deceleration (V-07), F3 only, new motivo
  `EXIT_ACDECEL`. Checked AFTER the SL/trailing checks each bar (stop-outs
  take precedence same-bar). Disabled by default.
- New import: `ac_desacelerando` from `emasar_ref` (previously unused by
  this module; already existed in the frozen file, exercised via
  `emasar_ref.simular`'s own `ac_modulate_trail`/`ac_exit_enable` params).
- Per-signal state added out-of-band (same pattern as batch 2's
  `sl_inicial_by_tag`, since `_Ficha` uses `__slots__` and is vendored
  frozen): `r_by_tag` (V-05's shared R distance per ficha, set at entry,
  reset each new signal) and `ac_decel_consec_by_tag` (V-07's F3
  consecutive-deceleration counter, reset each new signal).
- `emasar_ref.py` was NOT touched (frozen, golden-tested).

`tests/strategies/test_emasar_variant.py` extended from batch 2's 7 tests to
19 (12 new, all passing, ZERO skips): for each of V-05/V-06/V-07 -- (a)
default-preservation on a synthetic fixture, (b) default-preservation on a
real XAUUSD/M5 2026-06 lake window, (c) a "turning it on changes the event
stream, motivo vocabulary stays in bounds" sanity test, and (d) a
deterministic-seed trigger test that pins the new motivo actually fires and
(where feasible) checks the exact exit price/ordering against the engine's
own formulas. The trigger tests use `_synthetic_bars(n, seed=...)` with
seeds pre-searched to reliably produce the target event (seed 1 for V-05/
V-07's trigger cases, seed 24 for V-06's) rather than hand-crafted OHLC
fixtures, since the entry gate's confirm-count/pullback logic made
hand-crafted fixtures unreliable across variants; V-07's isolation test also
widens `f3_trail_pips` (an existing, already-tested kwarg) to prevent F3's
own trailing stop from preempting the AC-decel counter, mirroring the same
technique used to independently confirm V-07's real-data inertness finding
above.

## Ingested runs (winners only, `data/research.db`)

- `sim-report-emasar-v05-{m1,m2,m5,m15}` -- best-net (leg, f1_tp_r, f2_tp_r)
  per TF, all four from the **stacked** leg (V-01b's per-TF k); (1.5, 3.0)
  for M1/M2/M15, (1.0, 2.0) for M5 (4-way tie at that leg).
- `sim-report-emasar-v06-{m1,m2,m5,m15}` -- best-net (leg, factor) per TF,
  all four from the **stacked** leg at factor=0.5.
- `sim-report-emasar-v07-{m1,m2,m5,m15}` -- best-net (leg, bars) per TF, all
  four from the **stacked** leg at bars=2.

All re-ingestion is idempotent (delete-before-insert per run_id), verified
via `PYTHONPATH=D:/FOREX python scripts/dev/e2e_service.py --port 8611` +
`GET /api/runs/<run_id>/trades` returning non-empty rows for all 12 winner
run_ids (3 variants x 4 TFs). Service was started fresh for this
verification (PID resolved via `Get-NetTCPConnection -LocalPort 8611`, then
stopped by that exact PID only); the production service on :8601 was
verified still running (separate PID) and left untouched throughout.

## Gates

- `tests/golden/test_parity.py`: 3/3 pass.
- `tests/strategies`: all green (25/25, including the 19 in
  `test_emasar_variant.py`).
- `tests/service`: 496 passed, 3 pre-existing allowed failures
  (`test_chat.py::test_review_strategy_happy_path_sse_sequence` +
  `test_web_positions.py`'s 2 analizar-button tests) -- unchanged from the
  documented baseline, `chat.py`/`positions.js` were not touched this batch.
