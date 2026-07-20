# PATIENT-EXIT research program — executable plan

> Date: 2026-07-20 · Branch `alvaro` · Repo `D:\FOREX` · Author: DESIGN agent (Opus 4.8, design-only).
> Status: PLAN (design-only). No code written, no backtest run, no config armed by this document.
> Downstream: one Opus implementer executes the SDD tasks; one Sonnet backtester runs the final
> report-only league. This file is the single source of truth for the program's scope + gates.

This program designs and honestly evaluates **EXIT-POLICY variants** that refine the only surviving
strategy family — the **M15 V-15 SAR** configs (`S6-K2P0` / `S7-TPNONE`, the go-live reps in
`sentinel_engine/strategies/live_configs_20.py::CONFIGS_GOLIVE`). Goal: as profitable as possible with
minimal losses, attacking two articulated failure modes:

- **Problem A — give-back:** a position that IS in profit hands it back before exiting.
- **Problem B — premature exit:** a position that predicted direction CORRECTLY closes too early and
  misses the full favourable swing it was entitled to.

A and B pull in opposite directions. The program searches exit policies that trade this off well, under
hard constraints (never cap the runner; bounded waiting only; additive no-op-default levers; honest
WF+DSR evaluation + single-touch holdout; DEMO/read-only safety).

---

## 0. Findings that gate this design (closed facts, from the honest program)

These are load-bearing conclusions from prior research; the plan is built on them and does not re-litigate.

1. **No proven edge exists.** DSR 0.0 / p 1.0 across all 672 honest runs; the surviving family is
   net-positive in-sample and sign-stable on one untouched holdout month (`HOLDOUT-2026-01`) but
   sub-luck-bar. Every claim here is therefore about **improving a sub-luck-bar family**, not proving one.
   Any surviving PATIENT-EXIT variant is a **live-forward OOS candidate**, never a "validated edge."
   (`docs/superpowers/research/2026-07-20-PRELIMINARY-full-program-report.md` §1,§5.)
2. **`tp_min` (a ceiling on the winner) was DECISIVELY REFUTED** — the single most value-destroying lever
   in the program: champion +$13,355 → −$25k…−$28k at every grid value, because capping every winner at a
   few cents while the SL side takes full losses destroys the payoff distribution. **No ceiling on the
   runner is allowed in this program.** (`docs/superpowers/research/2026-07-20-wave6-tp-trailhalf-findings.md`.)
3. **On M15 the SAR / ATR-floor exit binds BEFORE the 100-pip trail.** `trail-half` (halving the trail
   distance 100→50) was **byte-identical** on the champion. This is the single most important mechanism
   fact for this program: on this family the *effective stop* is the max of {SAR-implied level, ATR-floor
   `trail_atr_floor_k × ATR14`, the pips trail}, and the ATR-floor/SAR term dominates. **Therefore
   give-back and premature-exit are governed by the SAR/ATR-floor geometry, not the pips trail** — the
   levers that will actually move the needle are ones that change the floor geometry (ATR-floor k, BE
   ratchet, partial-scale), not the pips trail. (Same wave-6 findings doc.)
4. **Clone concentration is the live-observed failure.** Live round-1 lost −58,445 CLP: the 5 near-clone
   M15 shorts (60–77% signal overlap) stopped out as a bloc into a whipsaw — a live illustration of
   Problem B (all exited at the worst point, then price reversed the way they were right about). Only the
   *different* line (V11-M2) won. This is exactly the whipsaw PATIENT-EXIT must cut. (PRELIMINARY report §8.)
5. **The base configs are frozen and honest-scored byte-for-byte.** `S6-K2P0` and `S7-TPNONE` in
   `CONFIGS_GOLIVE` are built VERBATIM from the honest-league manifest cells (`_golive_m15`), so a variant
   that modifies them via an additive no-op-default kwarg stays inside the same comparable-by-construction
   league. The champion base is: ema 8/20, sar 0.3/0.3 adaptive (`sar_adaptive`, fast (0.3,0.3), slow
   (0.005,0.05), window 200), `f{1,2,3}_trail_pips=100`, `init_sl_range_k=2.5`, `confirm_mode=1`,
   `confirm_count=2`, `ac_modulate_factor=0.25`, `stop_and_reverse=True`, `live_fill_mode=True`; per-rep
   deltas: `ac_modulate`, `trail_atr_floor_k`, `be_at_r`, `f1_tp_r`, `active_fichas`.

---

## 1. GATING VERDICT — backtestable vs tick-only vs live-only (answer FIRST)

**The question:** the engine acts on CLOSED M15 bars (OHLC only). Intrabar tick ORDERING within a single
bar is unknown. For each exit-mechanism class: is it (a) BACKTESTABLE on the current OHLC honest pipeline,
(b) BACKTESTABLE ONLY with tick/replay data, or (c) LIVE-ONLY?

### 1.1 Evidence the verdict rests on

- **Fill model is bar-OHLC with an explicit server-side-SL discipline.** `simular_variant`'s
  `live_fill_mode=True` (the honest-league mode) models the live executor's server-side SL: a bar-i
  intrabar stop check uses the SL level **as of the close of bar i−1** (`server_sl_by_tag` /
  `sl_check`), and trailing raises computed from bar i's own high only become active from bar i+1. A raise
  already violated by bar i's *own close* triggers a **same-bar fallback** exit at that close, flagged
  `same_bar_fallback: True`. (`sentinel_engine/strategies/emasar_variant.py` docstring pts 1–3, lines
  299–327; code lines 560–815.) **Consequence:** any exit whose *decision* is "did price reach level L?"
  where L is knowable at a bar boundary, and whose *fill* is a bar high/low touch or a bar close, is fully
  and honestly resolvable on OHLC — this is precisely how BE, TP-by-R, initial-SL, trailing, AC-decel, and
  time-stop already work in the engine.
- **Same-bar TP-vs-SL collisions are already resolved conservatively (SL-first).** The engine treats a bar
  that touches BOTH a TP and the active SL as an SL hit (V-05 / tp_min blocks, lines 577–638). This is the
  standard OHLC ambiguity, and it is already handled by a documented, pinned convention — so any *rising-
  floor* mechanism (which only ever tightens the stop) inherits the same honest treatment with no new
  ambiguity.
- **Bounded-adverse and bounded-hold are directly checkable on OHLC.** Max-adverse-excursion is
  `min(low)`/`max(high)` over the held bars vs entry — computable exactly from subsequent bar lows/highs.
  Max-hold is a bar count (`i - entry_bar_idx`), already implemented as `max_hold_bars` (P51, lines
  783–796). Both bounds are OHLC-native.
- **What OHLC CANNOT tell us: intrabar path ORDER.** Within one bar we know {open, high, low, close} but
  NOT whether the high or the low came first. Any mechanism whose outcome depends on *which extreme was
  touched first within the same bar* (e.g. "wait for a dip to level D and, if it then rallies to level U
  in the SAME bar, stay in") is not resolvable from OHLC. On a single bar this is a genuine unknown; the
  engine's only honest choices are the conservative one (assume the adverse extreme first) or refuse.
- **No tick lake exists for the honest windows.** `data/lake/XAUUSD/` is OHLCV bars only (M1/M2/M5/M15/H1/D);
  there is NO tick store. Real tick cache (`.tkc`) exists ONLY inside the MT5 tester
  (`D:/FOREX/MT5_Tester/Bases/Capitaria-All/ticks/XAUUSD/202601..202607.tkc`) for **2026-01 … 2026-07**,
  and **not for 2025-10** (W3). The honest league's windows are IW=2026-06, W1=2026-05, W2=2026-03,
  W3=2025-10 (+ holdout 2026-01). So even the *tick-replay* route cannot cover W3 without a fresh
  Capitaria download, and no Python tick-exit engine exists (only an *estimate* to build one, ~4.7 h + a
  4-task port). (`docs/superpowers/research/2026-07-13-realtick-estimate.md`.)
- **`fast_replay.py` is NOT a tick exit engine.** It vectorizes ENTRY-signal generation + triple-barrier
  LABELING for the opt search; it has no per-tick SL/trail path. It cannot resolve intrabar exit ordering.
  It is irrelevant to exit-mechanism gating (it is an entry/label speed layer).
- **Sub-M15 OHLC is a partial, honest refinement — not tick data.** The lake HAS M1/M2/M5 bars for the
  honest windows. Re-checking an M15 exit decision against the M1 bars *inside* that M15 bar narrows the
  intrabar-ordering unknown by ~15× (you learn the order of the fifteen M1 sub-bars' closes) without any
  tick data. This is BACKTESTABLE-with-more-bars (a "(a′)" refinement), not tick-only — but it is OUT OF
  SCOPE for the first league (it changes the fill model and would break byte-identity with the honest
  league); it is listed as a validation-section option, not a first-league lever.

### 1.2 Per-class verdict

| Mechanism class | Decision knowable at bar boundary? | Fill resolvable on OHLC? | Verdict | Why |
|---|---|---|---|---|
| **Profit-ratchet / chandelier** (rising floor at a fraction of peak-favourable) | Yes — peak = running `max(high)`/`min(low)`; floor = peak − k·(peak−entry) or peak − k·ATR | Yes — a monotone-tightening SL, touch-checked like today's trail | **(a) BACKTESTABLE** | Identical machinery to BE/trailing; SL only ever tightens → inherits SL-first collision convention; server-side-SL discipline already models the one-bar lag. |
| **Wider ATR-floor / slower SAR** (more room for correct calls) | Yes — `trail_atr_floor_k`, `sar_slow` are per-bar deterministic | Yes — just changes the effective stop level checked each bar | **(a) BACKTESTABLE** | Pure parameter changes on existing, honest-scored levers; no new fill route. |
| **BE / break-even ratchet** (`be_at_r`, `be_offset_pips`) | Yes — max_fav vs R threshold at bar close | Yes — raised SL touch-checked next bar (server-side) | **(a) BACKTESTABLE** | Already implemented + parity-pinned (lines 657–694); honest under live_fill_mode. |
| **Partial-scale / bank-a-fraction at +NR, run the rest** (`f1_tp_r`, `active_fichas` combos) | Yes — R-multiple TP at bar close; per-ficha | Yes — TP is a touch at a fixed level, SL-first on collision | **(a) BACKTESTABLE** | Exactly V-05 semantics (F1/F2-only R-multiple TP), already honest-scored; F3 runner never capped → constraint-1 safe. |
| **Time-stop / max-hold bound** (`max_hold_bars`) | Yes — bar count | Yes — exit at bar close | **(a) BACKTESTABLE** | P51, already implemented (lines 783–796). |
| **Bounded stop-and-wait through adverse noise** (hold through a bounded MAE, exit at BE-or-better) — the whipsaw/B core | Decision (widen initial stop to a bounded MAE, then require BE-or-better to exit) is knowable at bar boundary; **the exit-quality FILL depends on intrabar order** when the BE-recovery and the MAE-bound are touched in the SAME bar | Partly — the *bounded-loss* outcome (did the MAE bound get hit?) is OHLC-honest (conservative: adverse extreme first); the *upside "exit at breakeven-or-better when price recovers"* is only conservatively bounded on OHLC (same-bar recovery-then-give-back is unknowable) | **(a) BACKTESTABLE as a CONSERVATIVE LOWER BOUND; (b) for the exact same-bar recovery-vs-stop resolution** | The mechanism reduces to: (i) a wider initial-SL / MAE bound = pure OHLC param; (ii) a "don't exit until price returns to ≥ BE" rule = a floor that only tightens once BE is reached = OHLC-honest; (iii) the *within-bar* case where both the MAE bound and the BE-recovery would be touched in one bar is the only tick-ambiguous part, and the honest OHLC engine resolves it SL-first (conservative), which UNDER-states the mechanism's benefit. So it is backtestable as a pessimistic lower bound; the residual optimism gap is a tick-replay question. |
| **Trailing-stop start delay** ("don't start trailing until +NR", give the runner room early) | Yes — arm trailing only after max_fav ≥ entry+N·R at bar close | Yes — before arming, only the (wide) initial-SL is active | **(a) BACKTESTABLE** | A gate on when the existing trail turns on; initial-SL bound is OHLC-native. |
| **Intrabar "wait for the convenient dip then ride the swing" (path-dependent re-entry within a bar)** | No — depends on high-vs-low order within the signal bar | No | **(b) TICK-ONLY** | This is the literal "convenient price swing" as an *intrabar* object; OHLC cannot order the swing. Excluded from the first league. |
| **Slippage / partial-fill / spread-float sensitivity of the ratchet in real fills** | N/A | No — needs real forward fills | **(c) LIVE-ONLY** | The flat-0.5 model cannot price real slippage on a tightening stop; only the DEMO live-forward can. Goes to the live-forward section. |

### 1.3 Scope split (drives what goes in the backtest league)

- **(a) BACKTESTABLE now** on the OHLC honest pipeline: profit-ratchet/chandelier, wider ATR-floor/slower
  SAR, BE ratchet, partial-scale, time-stop, trail-start-delay, and the bounded stop-and-wait **as a
  conservative lower bound**. → **These are the ONLY configs that enter the honest WF+DSR league now.**
- **(b) TICK-ONLY** (or sub-M15-OHLC refinement): the *exact* same-bar resolution of bounded stop-and-wait's
  upside, and any intrabar "ride the convenient swing" mechanic. → **Live-forward / tick-replay validation
  section only**; NOT in the first league. A cheaper partial answer (M1-sub-bar cross-check) is offered
  there.
- **(c) LIVE-ONLY:** real-fill slippage/spread-float behaviour of a tightening ratchet. → **DEMO
  live-forward section only.**

**One-paragraph verdict:** Every give-back-protection and room-giving mechanism this program needs is a
RISING FLOOR, a WIDER INITIAL STOP, a BAR-COUNT BOUND, or a FIXED-LEVEL PARTIAL — all of which are decided
at bar boundaries and filled by a bar high/low touch or a bar close, so they are **(a) fully backtestable
on the current OHLC honest pipeline** with the engine's existing server-side-SL + SL-first-collision
discipline (no new fill route, no look-ahead). The ONLY genuinely tick-dependent thing is the *within-a-
single-bar ordering* of an adverse dip vs a favourable recovery — which affects ONLY the exact upside
resolution of the bounded stop-and-wait family and any literal "ride the intrabar swing" idea; those are
**(b) tick-only** and are validated separately (with an M1-sub-bar OHLC cross-check as a cheap partial),
while real-fill slippage of a tightening ratchet is **(c) live-only** on the DEMO. Net: the whole first
league is (a)-class; nothing is blocked on tick data.

---

## 2. Exit-policy taxonomy

Base = the champion M15 V-15 SAR (`S6-K2P0` primary, `S7-TPNONE` secondary). Every family below is a new
**additive kwarg with a no-op default** on `simular_variant`, or a re-parameterisation of an EXISTING
no-op-default lever. Constraint compliance is stated per family.

### F1 — Profit-ratchet / chandelier (rising floor at a fraction of peak) → **Problem A**
- **Mechanism:** maintain per-ficha `peak_fav` (running max favourable price). Once `peak_fav` has moved at
  least `ratchet_arm_r × R` in favour (R = |entry − initial_SL|), raise the SL to a FLOOR that locks a
  fraction of the peak gain: `floor = entry + ratchet_lock_frac × (peak_fav − entry)` (long; mirror short),
  OR a chandelier variant `floor = peak_fav − ratchet_atr_k × ATR14[i]`. SL only ever tightens (never
  loosens vs initial/trail/BE), exactly like the BE block. New kwargs:
  `ratchet_lock_frac: float = 0.0` (no-op), `ratchet_arm_r: float = 1.0`, `ratchet_atr_k: float = 0.0`
  (no-op; when >0 selects chandelier form; the two forms are mutually exclusive per config — raise if both
  >0).
- **Constraint 1 (never cap the runner):** the floor is BELOW the peak and rises WITH the peak; it never
  places a ceiling above price. As price runs, the locked floor runs up behind it. ✔
- **Constraint 2 (bounded waiting):** N/A — ratchet only ever tightens; it adds no holding.
- **Targets A** by converting give-back into a booked floor once a real move exists.

### F2 — Wider ATR-floor / slower SAR (more room for correct calls) → **Problem B**
- **Mechanism:** two sub-levers, both pure re-parameterisations of EXISTING no-op-default levers:
  (i) raise `trail_atr_floor_k` above the reps' 1.5–2.0 (grid to 3.0/4.0) so the effective stop sits
  further from price → correct calls get room; (ii) slow the adaptive SAR by widening `sar_slow` (e.g.
  (0.005,0.05)→(0.002,0.03)) so the SAR term flips less eagerly. No new kwargs (uses `trail_atr_floor_k`,
  `sar_slow`, `sar_adaptive`).
- **Constraint 1:** a wider floor is still a stop BELOW price; no ceiling. ✔
- **Constraint 2:** a wider stop increases per-trade risk (bigger R) but is HARD-BOUNDED by the initial-SL
  range (`init_sl_range_k`) and by `max_hold_bars` — both explicit parameters. Every F2 config MUST pin a
  finite `max_hold_bars` (see Global Constraints). ✔
- **Targets B** by not stopping correct calls out on ordinary noise.

### F3 — Bounded stop-and-wait (hold through bounded adverse excursion, exit at BE-or-better) → **B core / whipsaw**
- **Mechanism:** the whipsaw fix. Instead of dumping at the worst tick, tolerate a BOUNDED adverse
  excursion and prefer to exit at break-even-or-better. Composed ENTIRELY from OHLC-honest primitives:
  (i) `wait_mae_atr_k: float = 0.0` (no-op) — set the initial protective stop at
  `entry − wait_mae_atr_k × ATR14` (long; mirror short) i.e. a WIDER, explicitly bounded max-adverse
  excursion; (ii) `wait_be_exit: bool = False` — once armed (price returned to ≥ entry after being
  adverse), exit at the BE floor rather than chasing the trail down; (iii) MANDATORY `max_hold_bars` bound.
  This is `wait_mae_atr_k` (bounded MAE) + `be_at_r`/`wait_be_exit` (BE-or-better exit) + `max_hold_bars`
  (bounded hold) — three explicit bounds, no unbounded hold anywhere.
- **Constraint 1:** no ceiling; the runner side is untouched (only the stop side is widened+bounded). ✔
- **Constraint 2 (bounded waiting ONLY — the inviolable one):** BOTH bounds are hard kwargs:
  `wait_mae_atr_k` caps adverse price excursion; `max_hold_bars` caps time. An unbounded hold is REFUSED
  (`wait_mae_atr_k>0` requires `max_hold_bars` set — raise otherwise). ✔
- **Gating tag: (a) as a CONSERVATIVE LOWER BOUND** (the same-bar dip-then-recover case resolves SL-first,
  under-stating benefit); the exact same-bar upside is (b) tick-only. Reported honestly as a lower bound.
- **Targets B** (the live-observed clone-bloc whipsaw).

### F4 — Partial-scale (bank a fraction at +NR, run the rest — the tp_min-safe hybrid) → **A + B**
- **Mechanism:** bank a FRACTION of the position at a modest +N·R while letting the remainder run
  UNCAPPED. Uses EXISTING V-05 `f1_tp_r` (F1 R-multiple TP, F1 only; F2/F3 never TP) — optionally with
  `active_fichas` — so F1 books early profit (fixes A on the banked slice) while F2/F3 remain full runners
  (preserves B on the run slice). Grid `f1_tp_r ∈ {0.5,1.0,1.5}`, optionally `f2_tp_r` for a two-thirds
  bank. No new kwargs.
- **Constraint 1 (CRITICAL — this is the tp_min-safe design):** ONLY F1 (and optionally F2) is capped; F3
  (the runner) is NEVER capped. This is the exact opposite of the refuted `tp_min` (which capped ALL
  fichas). The refutation is respected by construction: the runner keeps its full uncapped payoff. ✔
- **Constraint 2:** N/A (no added holding).
- **Targets A+B**: A on the banked slice, B on the runner.

### F5 — Trail-start delay (give the runner early room, then trail) → **Problem B (secondary)**
- **Mechanism:** `trail_arm_r: float = 0.0` (no-op) — the per-ficha trailing stop does not begin tightening
  until `max_fav` reaches `entry + trail_arm_r × R`; before that only the (wide) initial-SL protects.
  Correct calls get uninterrupted early room; the trail engages only after a real move.
- **Constraint 1:** no ceiling. ✔
- **Constraint 2:** the pre-arm exposure is bounded by the initial-SL; pair with `max_hold_bars`. ✔
- **Targets B** (early premature-exit). NOTE per Finding-3 (ATR-floor binds before the pips trail on M15),
  this may be near-neutral on the champion; included as a principled probe + a diagnostic (if neutral, it
  confirms the floor-dominance mechanism). Kept to ≤2 configs.

**Additional principled family (justified):**

### F6 — Give-back cap as a RISING floor tied to realized MFE (not a ceiling) → **Problem A, sharper**
- **Mechanism:** a give-back GUARD expressed as a floor: exit only if the position gives back more than
  `giveback_frac` of its peak unrealized gain, implemented as a rising SL at
  `peak_fav − giveback_frac × (peak_fav − entry)` (equivalently F1 with `ratchet_lock_frac =
  1 − giveback_frac`). This is F1 re-parameterised to directly express "never give back more than X% of the
  best I saw" — the most literal statement of Problem A — WITHOUT any ceiling (it is a trailing floor).
  Shares F1's kwargs (`ratchet_lock_frac`), so no NEW kwarg; it is a grid slice of F1 chosen to sweep the
  give-back fraction explicitly (lock_frac ∈ {0.33,0.5,0.66}).
- Constraints: identical to F1 (rising floor, no ceiling, no added hold). ✔

---

## 3. Concrete config enumeration (14 configs; hard-max 30)

All modify base **`S6-K2P0`** (league rank 1, in-sample AND holdout profit leader) unless the row says
`S7-TPNONE` (rank 2, already carries `be_at_r=1.0` give-back protection — the natural base for A-family
comparisons). Each config = base kwargs + the listed delta ONLY. Every one is tagged (a)/(b)/(c) per §1.
Each is preregistered (hypothesis, mechanism, metric, threshold, discard_if) in the manifest per the
harness's P64 requirement.

| # | Config id | Family | Base | Delta kwargs (exact) | Problem | Tag |
|---|---|---|---|---|---|---|
| 1 | `PX-RATCHET-L33` | F1 | S6-K2P0 | `ratchet_lock_frac=0.33, ratchet_arm_r=1.0` | A | (a) |
| 2 | `PX-RATCHET-L50` | F1/F6 | S6-K2P0 | `ratchet_lock_frac=0.50, ratchet_arm_r=1.0` | A | (a) |
| 3 | `PX-RATCHET-L66` | F1/F6 | S6-K2P0 | `ratchet_lock_frac=0.66, ratchet_arm_r=1.0` | A | (a) |
| 4 | `PX-CHAND-ATR3` | F1 (chandelier) | S6-K2P0 | `ratchet_atr_k=3.0, ratchet_arm_r=1.0` | A | (a) |
| 5 | `PX-CHAND-ATR2` | F1 (chandelier) | S6-K2P0 | `ratchet_atr_k=2.0, ratchet_arm_r=1.0` | A | (a) |
| 6 | `PX-FLOOR-K3` | F2 | S6-K2P0 | `trail_atr_floor_k=3.0, max_hold_bars=64` | B | (a) |
| 7 | `PX-FLOOR-K4` | F2 | S6-K2P0 | `trail_atr_floor_k=4.0, max_hold_bars=64` | B | (a) |
| 8 | `PX-SAR-SLOW` | F2 | S6-K2P0 | `sar_slow=(0.002,0.03), max_hold_bars=64` | B | (a) |
| 9 | `PX-WAIT-MAE2` | F3 | S6-K2P0 | `wait_mae_atr_k=2.0, wait_be_exit=True, max_hold_bars=48` | B | (a) lower-bound |
| 10 | `PX-WAIT-MAE3` | F3 | S6-K2P0 | `wait_mae_atr_k=3.0, wait_be_exit=True, max_hold_bars=48` | B | (a) lower-bound |
| 11 | `PX-PART-F1TP1` | F4 | S6-K2P0 | `f1_tp_r=1.0` | A+B | (a) |
| 12 | `PX-PART-F1TP0P5` | F4 | S6-K2P0 | `f1_tp_r=0.5` | A+B | (a) |
| 13 | `PX-PART-F1F2` | F4 | S6-K2P0 | `f1_tp_r=1.0, f2_tp_r=1.5` | A+B | (a) |
| 14 | `PX-TRAIL-ARM1` | F5 | S6-K2P0 | `trail_arm_r=1.0, max_hold_bars=64` | B | (a) |

Notes: (i) `S7-TPNONE` is the A-family control (already has `be_at_r=1.0`); the F1/F6 ratchet rows should
ALSO be priced on `S7-TPNONE` in the manifest as a robustness echo IF the config budget allows (adds ≤5
rows, still ≤20). (ii) `max_hold_bars=48/64` M15 bars ≈ 12/16 h — a finite bound honoring Constraint 2;
its exact value is itself a pinned parameter, not a magic number, and can be swept in a follow-up wave.
(iii) ALL 14 are **(a)-class → all 14 enter the honest league.** 0 are (b)/(c) in the first league; the
(b) same-bar-upside refinement of #9/#10 goes to §6, and the (c) real-fill slippage question of the whole
set goes to §6.

**Config-count split:** 14 configs · **(a) = 14** (all in first league) · (b) = 0 in league (1 refinement
question deferred to validation) · (c) = 0 in league (1 real-fill question deferred to live-forward).

---

## 4. Honest-league integration

### 4.1 Additive kwargs + no-op defaults + byte-identity test (one per new lever)
New kwargs on `simular_variant` (all default to a byte-identical no-op; existing honest league stays
reproducible per Constraint 3 / P36 discipline):

| Kwarg | Default (no-op) | Family | Byte-identity test (must pass) |
|---|---|---|---|
| `ratchet_lock_frac: float` | `0.0` (block skipped) | F1/F6 | with default, event stream byte-identical to pre-change on S6-K2P0 over a fixed synthetic + one real month |
| `ratchet_arm_r: float` | `1.0` (inert while lock_frac/atr_k=0) | F1 | inert unless a ratchet form active |
| `ratchet_atr_k: float` | `0.0` (chandelier form off) | F1 | with default, byte-identical; raise if both lock_frac>0 AND atr_k>0 |
| `wait_mae_atr_k: float` | `0.0` (wider stop off) | F3 | with default, byte-identical; raise if >0 AND `max_hold_bars` is None |
| `wait_be_exit: bool` | `False` | F3 | inert unless `wait_mae_atr_k>0` |
| `trail_arm_r: float` | `0.0` (trail arms immediately, as today) | F5 | with default, byte-identical |

`trail_atr_floor_k`, `sar_slow`, `f1_tp_r`, `f2_tp_r`, `active_fichas`, `be_at_r`, `max_hold_bars` are
EXISTING no-op-default levers (already parity-pinned) — F2/F4/F5 reuse them with NO new kwarg. The
byte-identity gate for the new kwargs mirrors the existing pattern in
`tests/strategies/test_emasar_variant.py` and the P36 execution-parity suite: a
`simular_variant(bars, **base)` run must be event-for-event identical whether or not the new kwargs are
passed at their defaults, in BOTH `live_fill_mode` values, and with `return_state` on/off.

### 4.2 WF + DSR scoring (unchanged pipeline)
Each config is added as a manifest entry (same shape as
`scripts/report/honest_manifest_full_2026_07_20_v3.json`: `variant_id`, `tf:"M15"`, `kwargs`,
`windows:["IW","W1","W2","W3"]`, `prereg{…}`) and scored by
`scripts/report/gen_honest_sweep.py::run_sweep` VERBATIM — same `_price_cell`
(`simular_variant(live_fill_mode=True)` + `_B1` flat-0.5 fill/pnl primitives), `_metrics`, WF folds via
`anchored_walkforward`, and `deflated_sharpe_ratio` over the trial family (trial count = manifest size).
**The trial family for DSR is the PATIENT-EXIT manifest itself** (these 14 configs + their bases as
controls), so the DSR deflation is honest and self-contained; do NOT merge into the 225-cell league to
avoid changing that league's trial count (Constraint 3 reproducibility). Lot fixed 0.10 (`_B1.LOT`).

### 4.3 Holdout single-touch protocol (pre-committed, one price)
After the in-sample league ranks the 14, select **ONE pre-committed config per family** (declared in the
plan/manifest BEFORE holdout pricing — the pre-commitment: F1→`PX-RATCHET-L50`, F2→`PX-FLOOR-K3`,
F3→`PX-WAIT-MAE2`, F4→`PX-PART-F1TP1`, F5→`PX-TRAIL-ARM1`) and price each EXACTLY ONCE on the untouched
`HOLDOUT-2026-01` (2026-01-05→02-05, warmup 2025-12-29), using the identical
`gen_honest_sweep._price_cell`/`_metrics` path (per `docs/superpowers/research/2026-07-20-wave7-single-touch-holdout.md`).
No re-selection, no refit on holdout. No holdout DSR is computed (one config per family → nothing to
deflate; fabricating a trial family to manufacture a p-value is forbidden). The holdout tests DIRECTION/
sign persistence + the give-back/MFE metrics vs the base, NOT a powered significance claim.

### 4.4 MFE-capture % and give-back metrics (defined precisely; where computed)
Problems A and B are **max-favourable-excursion** problems that net PnL alone cannot separate. Two new
per-trade metrics, computed from OHLC in the SAME pairing pass as `_price_cell`:

- **MFE (max favourable excursion), price units, per ficha:** over the ficha's held bars [entry_bar,
  exit_bar], `MFE = max(high) − entry` (long) / `entry − min(low)` (short). Already available as the
  engine's per-ficha `f.max_fav` at exit; else recomputed from bar highs/lows. Populate the existing (but
  currently NULL) `trade.mfe` column (see `_persist_cell`, line 396: `"mfe": None`). Also populate
  `trade.mae = entry − min(low)` (long; mirror short) into the existing NULL `mae` column.
- **MFE-capture %** (the B metric): `booked / MFE` where `booked = (px_out − px_in)` in the favourable
  direction (0 if MFE ≤ 0; clamp to [−∞, 1], a value near 1.0 means the trade captured almost all the
  swing it was entitled to; a low value means premature exit). Report the **trade-count-weighted mean
  MFE-capture %** per config, and the **median**.
- **Give-back per trade** (the A metric): `giveback = MFE − booked` in price units (≥0 by construction for
  a trade that ever went favourable) → converted to USD via `_B1._pnl` scaling (lot 0.10, contract 100).
  Report **mean give-back USD/trade** and **total give-back USD** per config.
- **Where computed:** a new report-only module `scripts/report/gen_mfe_capture.py` (report-only, imports
  `simular_variant`, the `_B1` primitives, and the lake loader; NEVER mutates a run/score/DSR — same
  governance stance as `gen_residual_kpi.py`). It re-prices each config's trades with per-ficha MFE/MAE
  and emits a JSON + markdown table. The engine change to EXPOSE `max_fav`/MAE at exit (so the report need
  not re-derive) is a small optional `return_state`-style addition; if the engine is not extended, the
  report recomputes MFE/MAE from the paired trades' [entry,exit] bar span against lake highs/lows (fully
  OHLC-honest, no look-ahead — it uses only bars within the held span).

**Scoring rule (how A vs B is read):** a good PATIENT-EXIT config RAISES MFE-capture% (fixes B) AND LOWERS
give-back USD (fixes A) vs the base, WITHOUT reducing net. Report all three (net, MFE-capture%, give-back)
side-by-side vs `S6-K2P0`/`S7-TPNONE`; a config that improves net only by worsening one of A/B is flagged.

---

## 5. SDD task breakdown

Global Constraints block (task reviewers use verbatim) is in §5.0. Every task is one module + its tests,
sized ≤10 min of implementer (Sonnet) work, with its own acceptance gate (exact test command). Tasks with
overlapping file sets are SERIALISED (no parallel writers per the memory rule). The final backtest task is
report-only and objective (Sonnet).

### 5.0 GLOBAL CONSTRAINTS (reviewer checklist — applies to EVERY task)
1. **Never cap the runner.** No mechanism may place a ceiling ABOVE price on F3 (or the last active ficha).
   Only rising floors, wider stops, bar-count bounds, or F1/F2 partials. Any diff that caps the runner is
   REJECTED (echoes the tp_min refutation).
2. **Bounded waiting only.** Any waiting lever (F3) MUST hard-require BOTH a MAE bound (`wait_mae_atr_k`)
   AND a hold bound (`max_hold_bars`); the engine RAISES if a waiting lever is armed without both. F2 (wider
   stop) MUST ship with a finite `max_hold_bars` in every config.
3. **Additive, no-op default, byte-identity.** Every new kwarg defaults to a byte-identical no-op; a pinned
   byte-identity test (both `live_fill_mode` values, `return_state` on/off) accompanies each. The existing
   225-cell honest league must remain reproducible — do NOT touch its manifest or trial count.
4. **Honest evaluation only.** WF folds {IW,W1,W2,W3}, fixed lot 0.10, flat-0.5 cost, `live_fill_mode=True`,
   DSR over the PATIENT-EXIT trial family; single-touch holdout with one pre-committed config per family;
   report MFE-capture% and give-back, not just net.
5. **Safety (inviolable):** real broker accounts READ-ONLY; only the sanctioned DEMO (`2883015767`) trades;
   ATTACH-ONLY (never launch an MT5 terminal); golden/parity gate untouchable. Windows 10 AND 11 (pathlib,
   explicit utf-8, no WSL). Implementers never git commit; only the orchestrator commits, task by task.
6. **No sub-agents spawned by implementers.** Sonnet implementers do not spawn nested agents.

### PX-T1 — F1 profit-ratchet + chandelier lever (engine)
- **Files:** `sentinel_engine/strategies/emasar_variant.py` (+ tests in `tests/strategies/`).
- **Do:** add kwargs `ratchet_lock_frac=0.0`, `ratchet_arm_r=1.0`, `ratchet_atr_k=0.0`. In the per-ficha
  exit block, AFTER the BE block and BEFORE/alongside the trailing raise (as a floor that only tightens),
  compute the ratchet floor when armed (peak_fav moved ≥ `ratchet_arm_r×R`): frac form
  `entry + lock_frac×(peak_fav−entry)`; chandelier form `peak_fav − ratchet_atr_k×ATR14[i]`. Raise
  ValueError if both forms active. Honest under `live_fill_mode` (raised floor becomes active next bar via
  `server_sl_by_tag`; same-bar fallback path reused). Peak_fav = `f.max_fav` (already tracked).
- **Gate:** `python -m pytest tests/strategies/test_emasar_variant.py -k "ratchet or chandelier or noop" -q`
  — includes the byte-identity no-op test (default kwargs → identical events, both fill modes,
  return_state on/off) AND a behavioural test (a synthetic run-then-give-back bar sequence exits at the
  locked floor, not the give-back low).

### PX-T2 — F3 bounded stop-and-wait lever (engine)
- **Files:** `sentinel_engine/strategies/emasar_variant.py` (+ tests). **SERIALISED after PX-T1** (same file).
- **Do:** add `wait_mae_atr_k=0.0`, `wait_be_exit=False`. When `wait_mae_atr_k>0`, set the initial
  protective stop to `entry − wait_mae_atr_k×ATR14` (long; mirror short) — a WIDER, bounded MAE — instead
  of the range-SL (or as a max, whichever is wider/bounded; state the choice). When `wait_be_exit`, once
  the ficha has recovered to ≥ BE, prefer exiting at the BE floor. RAISE ValueError if `wait_mae_atr_k>0`
  and `max_hold_bars is None` (Constraint 2). Same-bar dip-vs-recovery resolves SL-first (conservative
  lower bound; document it).
- **Gate:** `python -m pytest tests/strategies/test_emasar_variant.py -k "wait or bounded or noop" -q` —
  byte-identity no-op test + a bounded-hold test (a config with `wait_mae_atr_k>0, max_hold_bars=N` never
  holds past N bars and never exceeds the MAE bound) + the raise-without-bound test.

### PX-T3 — F5 trail-start-delay lever (engine)
- **Files:** `sentinel_engine/strategies/emasar_variant.py` (+ tests). **SERIALISED after PX-T2** (same file).
- **Do:** add `trail_arm_r=0.0`. The per-ficha trailing raise is GATED: it only tightens once
  `max_fav ≥ entry + trail_arm_r×R`; before arming, only the initial-SL is active. Default 0.0 = arms
  immediately (today's behaviour) = byte-identical no-op.
- **Gate:** `python -m pytest tests/strategies/test_emasar_variant.py -k "trail_arm or noop" -q` —
  byte-identity no-op + a test that with `trail_arm_r=1.0` the trail does not tighten below the initial-SL
  until +1R is reached.

### PX-T4 — MFE-capture% + give-back report module (report-only)
- **Files:** `scripts/report/gen_mfe_capture.py` (new) + `tests/report/test_gen_mfe_capture.py` (new).
- **Do:** report-only module (governance stance of `gen_residual_kpi.py`): given a config id / kwargs +
  window, run `simular_variant(live_fill_mode=True)`, pair fichas (reuse `_price_cell`'s pairing shape or
  `sim_positions`), compute per-ficha MFE, MAE, booked, MFE-capture%, give-back (§4.4 definitions) from
  lake bar highs/lows within each ficha's [entry,exit] span, emit JSON + markdown. NEVER writes a
  run/score/DSR. Deterministic (no wall-clock/RNG).
- **Gate:** `python -m pytest tests/report/test_gen_mfe_capture.py -q` — a synthetic-bars test with a known
  MFE/give-back verifies the metrics exactly; a determinism test (same input → byte-identical JSON).

### PX-T5 — PATIENT-EXIT manifest + prereg (data, no engine)
- **Files:** `scripts/report/patient_exit_manifest_2026_07_20.json` (new) +
  `tests/report/test_patient_exit_manifest.py` (new).
- **Do:** author the 14-config manifest (+ optional S7-TPNONE echoes) in the
  `honest_manifest_full_*_v3.json` shape: each entry `{variant_id, tf:"M15", kwargs (base S6-K2P0/S7-TPNONE
  + delta), windows:["IW","W1","W2","W3"], prereg{hypothesis,mechanism,metric:"net_honest"+"mfe_capture",
  threshold, discard_if, date, author}}`. Include the pre-committed-holdout-config-per-family declaration
  in `_meta`. Every kwargs dict must be a VALID `simular_variant` call (levers from PX-T1..T3 + existing).
- **Gate:** `python -m pytest tests/report/test_patient_exit_manifest.py -q` — asserts 14(+echo) entries,
  unique ids, every `prereg.hypothesis` present (harness P64 requirement), every kwargs loads through
  `simular_variant` at its no-op defaults without error, tags recorded, holdout pre-commitment present.

### PX-T6 — FINAL BACKTEST-AND-REPORT (Sonnet, report-only, objective)
- **Files:** none modified — RUN + WRITE `docs/superpowers/research/2026-07-20-patient-exit-league.md`
  (+ `.json`) only.
- **Do (objective, no interpretation beyond the numbers):**
  1. Run `python -m scripts.report.gen_honest_sweep --manifest
     scripts/report/patient_exit_manifest_2026_07_20.json --windows IW,W1,W2,W3
     --league-json docs/superpowers/research/2026-07-20-patient-exit-league.json
     --report-md docs/superpowers/research/2026-07-20-patient-exit-league.md`.
  2. Run `gen_mfe_capture.py` for every config over {IW,W1,W2,W3} pooled; tabulate net, MFE-capture%
     (mean+median), give-back USD (mean+total) for each config vs the base `S6-K2P0`/`S7-TPNONE`.
  3. Price the 5 pre-committed holdout configs ONCE on `HOLDOUT-2026-01` via the same `_price_cell` path +
     `gen_mfe_capture` (single touch; no re-selection).
  4. Report: the DSR/luck-bar verdict (expected 0/1 — state it honestly), the per-config A/B table,
     which configs improved BOTH MFE-capture% AND give-back without hurting net, and the holdout sign +
     A/B persistence. Flag any config that improved net by worsening A or B. No go-live recommendation
     (that is the orchestrator+user's call at the assessment).
- **Gate:** the report exists with all four sections populated from real run output; the league JSON's
  `n_trials` == manifest size; MFE-capture% and give-back present for every config.

**Task dependency / ordering:** PX-T1 → PX-T2 → PX-T3 (serial, same engine file). PX-T4, PX-T5 may run in
parallel with the engine tasks (disjoint files) BUT PX-T5's manifest references PX-T1..T3 kwargs, so
PX-T5's *gate* (kwargs load through `simular_variant`) only passes once T1–T3 are merged — schedule PX-T5's
authoring in parallel, run its gate after T3. PX-T6 last (needs all).

---

## 6. Live-forward / tick-replay validation section (the (b)/(c) configs)

These are NOT in the first league (they cannot be honestly resolved on OHLC alone).

- **(b) Same-bar upside of the bounded stop-and-wait (F3).** The OHLC league scores F3 as a CONSERVATIVE
  LOWER BOUND (same-bar dip-then-recover resolved SL-first). To recover the residual optimism honestly:
  **(b-cheap) M1-sub-bar OHLC cross-check** — re-resolve each F3 exit decision against the M1 bars inside
  the signal M15 bar (the lake HAS M1 for IW/W1/W2/holdout; W3=2025-10 M1 coverage must be checked). This
  narrows intrabar ordering ~15× with zero tick data and is a report-only diff vs the M15 lower bound; it
  does NOT enter the byte-identical M15 league. **(b-full) tick-replay** — only if the M1 cross-check shows
  a material gap: real `.tkc` ticks exist for 2026-01..07 (covers IW, W1, holdout, NOT W2=2026-03? — 2026-03
  IS covered; W3=2025-10 is NOT and needs a download). Requires the unbuilt Python tick-exit engine
  (~4.7 h + 4-task port, per the realtick estimate) or an MT5 real-tick run (blocked on MQL5 lever ports).
  → deferred; only pursue if (b-cheap) flags a gap.
- **(c) Real-fill slippage/spread-float of a tightening ratchet.** The flat-0.5 model cannot price how a
  RISING floor (F1/F6) behaves under real slippage and a floating spread. This is DEMO-only: field the
  single best A-family config (e.g. `PX-RATCHET-L50`) and the best B-family config as spread-gated
  live-forward experiments on the sanctioned DEMO, reconciled via the existing `run_live_20` +
  `gen_residual_kpi.py` residual KPI (the by-design SAME_BAR/SL_CLAMP components are already broken out; a
  ratchet's real give-back vs sim shows up in the residual). ATTACH-ONLY, read-only broker, DEMO trades
  only. This is a live-forward OOS test, never a proven edge.
- **Clone-trim tie-in:** because the live loss was a clone bloc, the live-forward slots should field
  DISTINCT exit personalities (one A-ratchet, one B-wider-floor, one partial), not five near-clones — the
  PATIENT-EXIT families are a natural source of genuine exit-behaviour diversity for the roster's headroom.

---

## 7. Risks / open questions (for the orchestrator + user)

1. **Floor-dominance may flatten F2/F5.** Per Finding-3 (SAR/ATR-floor binds before the pips trail on
   M15), widening the pips-trail-adjacent levers can be near-neutral. MITIGATION: F2 targets the FLOOR
   itself (`trail_atr_floor_k`, `sar_slow`) not the pips trail; F5 is kept to 1 config as a diagnostic. If
   F2 is also neutral, that is itself an honest finding (the family's exit is SAR-geometry-bound and only
   partial-scale/ratchet-floor can move it). OPEN: is the champion's edge so floor-bound that ONLY F1/F4
   can help? The league answers this.
2. **DSR will almost certainly stay 0/p1.** With ~14–19 trials and a sub-luck-bar family, no config will
   clear the luck-bar. The program's honest deliverable is a BETTER give-back/MFE-capture profile at
   equal-or-better net, on a family already known to be sub-luck-bar — NOT a significance claim. The user
   should pre-agree that "improved A/B profile, sign-stable on holdout, DSR still 0" is the SUCCESS
   criterion here, not DSR>0.
3. **`max_hold_bars` value is a free parameter.** 48/64 M15 bars is a designer choice honoring Constraint 2;
   a wrong value could dominate results. OPEN: sweep `max_hold_bars ∈ {32,48,64,96}` in a follow-up wave if
   the first pass shows it binding often (report should flag `time_stop` exit frequency per config).
4. **(b) same-bar optimism gap size is unknown a priori.** The F3 lower bound could understate benefit
   materially or negligibly. The M1-sub-bar cross-check (§6 b-cheap) is the cheap way to size it before
   committing to a tick engine. OPEN: is M1 lake coverage complete for W3=2025-10? (must verify before
   promising the cross-check on all four windows).
5. **Holdout is one autocorrelated month.** Sign persistence on `HOLDOUT-2026-01` corroborates, never
   proves. No new holdout window should be "tried" — single touch, pre-committed, win or lose.
6. **Engine-file serialisation cost.** PX-T1..T3 all touch `emasar_variant.py` and must run serially,
   lengthening the critical path. If timeboxing bites, T1/T2/T3 can be authored as three disjoint blocks in
   one file and reviewed together — but they must still be committed separately with their own gates.

---

## Appendix — verified file references

- Engine + exit mechanics: `sentinel_engine/strategies/emasar_variant.py` (`simular_variant`; `be_at_r`
  657–694, trailing/ATR-floor 696–765, AC-decel 767–781, `max_hold_bars` 783–796, `live_fill_mode`/
  same-bar-fallback 299–327 & 560–815, V-05 TP + tp_min SL-first 577–638).
- Champion base + reps: `sentinel_engine/strategies/live_configs_20.py` (`_GOLIVE_BASE_M15`, `_golive_m15`,
  `CONFIGS_GOLIVE`, `CONFIGS_GOLIVE_DEDUP`; S6-K2P0 lines 255–256, S7-TPNONE 257–259).
- Honest sweep harness (scoring + persistence + WF/DSR): `scripts/report/gen_honest_sweep.py`
  (`_price_cell` 214–265, `_metrics` 268–297, `_persist_cell` NULL mfe/mae 396, `_build_league`+DSR
  424–513).
- Manifest shape: `scripts/report/honest_manifest_full_2026_07_20_v3.json` (`_meta`, cell fields, prereg).
- MFE/PnL infra: `scripts/report/gen_residual_kpi.py` (report-only governance stance);
  `scripts/live/check_live_sim_parity.py` (`load_bars`, `sim_positions`).
- Tick/replay (gating): `sentinel_engine/opt/fast_replay.py` (entry/label speed layer, NOT an exit engine);
  `docs/superpowers/research/2026-07-13-realtick-estimate.md` (no tick lake; `.tkc` 2026-01..07 only, no
  2025-10; ~4.7 h + 4-task port to a Python tick engine); `docs/superpowers/research/2026-07-15-signal-replay.md`.
- Prior findings: `docs/superpowers/research/2026-07-20-PRELIMINARY-full-program-report.md`;
  `docs/superpowers/research/2026-07-20-wave6-tp-trailhalf-findings.md`;
  `docs/superpowers/research/2026-07-20-wave7-single-touch-holdout.md`.
- Workflow rules (task sizing ≤10 min, one-file-one-owner, batched review):
  `docs/superpowers/specs/2026-07-12-agentic-workflow-rules.md`.
