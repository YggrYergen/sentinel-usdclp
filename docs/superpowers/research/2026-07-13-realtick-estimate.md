# Real-Tick Validation Time Estimate — 10 Winning EMASAR Configs

Estimation-only research spec. **No real-tick backtest, no MT5 terminal launch, no
orders were executed to produce this estimate.** All numbers below are derived from
(a) reading existing lake parquet files, (b) timing the existing bar-level
`simular_variant` engine on real historical bars (a normal, seconds-long Python
run — not a tick-level or MT5 execution), and (c) reading pre-existing `.htm`
Strategy Tester reports and `.mq5` sources already on disk from prior sessions.

## Scope

- **10 winners** (SS-M5, V13-M5, V06d-M5, V06c-M5, SS-M15, V13-M15, V06d-M15,
  V06c-M15, V06b-M15, V15-M15), all on the champion skeleton.
- **Standard 4-month scope**: 2026-06-08→07-07, 2026-05-04→06-05,
  2026-03-02→04-03, 2025-10-01→11-01 (XAUUSD).
- Also reported: 1-month (representative, the Jun–Jul IW) and 6-continuous-months
  (2026-01-08→2026-07-07, the longest continuous span the lake supports ending
  at its latest date).

---

## 1. Tick volume table

No tick-level store exists in `data/lake/XAUUSD/` (checked `data/lake/manifest.json`
and every subfolder — `1/2/5/15/60/1440.parquet` at symbol root plus
`M1/M2/M5/M15/H1/D` month-sharded dirs; all are OHLCV **bar** parquets, no tick
files). Tick volume is therefore estimated from bar `volume`, per the standard
MT5 convention that `volume` = tick count observed while building that bar.

**Verification performed**: summed `volume` (`v` column) over the same span
(2026-06-08 → 2026-06-20) independently from the M2, M5, M15, and root-M1
parquets. All four returned the **identical total: 4,088,971**. This confirms
the lake's `volume` field is tick-count-per-bar, additive and timeframe-invariant
— summing any one timeframe's volume over a span gives the true tick count for
that span, so M15 (the only timeframe with full coverage back to 2025-10) is a
safe proxy for all four windows.

| Window | Days | Ticks (Σ volume) | Ticks/day |
|---|---|---|---|
| 2026-06-08 → 07-07 | 29 | 8,467,419 | 291,980 |
| 2026-05-04 → 06-05 | 32 | 8,782,481 | 274,453 |
| 2026-03-02 → 04-03 | 32 | 8,528,522 | 266,516 |
| 2025-10-01 → 11-01 | 31 | 4,908,249 | 158,331 |
| **4-window standard scope, total** | 124 | **30,686,671** | — |
| 1-month reference (Jun–Jul IW alone) | 29 | 8,467,419 | — |
| 6-continuous-months (2026-01-08→07-07) | 180 | 43,173,271 | — |

Note: 2025-10 tick density (~158K/day) is notably lower than the 2026 windows
(~270-290K/day) — plausibly lower liquidity/volatility regime in Oct 2025 XAUUSD;
worth flagging if per-window Route A/B times are compared apples-to-apples.

---

## 2. Throughput benchmark (existing bar-level engine)

Benchmarked `sentinel_engine.strategies.emasar_variant.simular_variant` directly
via `scripts/report/gen_variant_batch1.py`'s loader (`_bars_for`) and champion
skeleton kwargs, on the IW window (2026-06-08→07-07, warmup from 2026-06-01),
for M5 and M1. 3 timed runs each, data load timed separately from the sim loop.

| TF | Bars | Load time | Sim times (3 runs) | Avg sim time | Bars/sec | Events emitted |
|---|---|---|---|---|---|---|
| M5 | 7,293 | 1.48s | 0.325 / 0.319 / 0.345 s | 0.330s | **22,135** | 4,736 |
| M1 | 36,447 | 0.34s | 1.567 / 1.538 / 1.489 s | 1.531s | **23,801** | 22,945 |

Average measured throughput: **~23,000 bars/sec**. Data-load time is small and
not the bottleneck (M1's faster load reflects OS disk-cache warmth from the
M5 run moments earlier — treat both as noise-level, <2s, per config-month at
this scale).

---

## Route A — Python tick-level simulation (would require porting the engine)

**Assumptions (each stated explicitly):**
- Effective tick-processing rate = bar-throughput ÷ slowdown factor.
- Slowdown factor = **1.25×** (midpoint of the stated 1.0–1.5× range) — the
  per-tick loop body (indicator update, gate check, exit eval) is structurally
  the same work as the per-bar loop body; ticks are simply a finer time-grid so
  no algorithmic blowup is expected, just more iterations of similar-cost code.
- Effective rate = 22,968 (avg of M5/M1 bars/sec) ÷ 1.25 = **~18,374 ticks/sec**.
- Data-load overhead: assumed ~3s/config-month for a tick-level loader (CSV/parquet
  read, an order of magnitude more rows than bar loading but still I/O-bound and
  small next to compute) → negligible at this scale (≤3 min total across all scopes).
- No port has been written or run — this is throughput extrapolated from the bar
  engine's measured cost, not a tick engine's measured cost.

**Estimate table** (10 configs, effective rate 18,374 ticks/sec):

| Scope | Ticks/config | Total ticks (×10) | Time |
|---|---|---|---|
| 1-month (Jun–Jul IW) | 8,467,419 | 84,674,190 | **76.8 min (1.28 hr)** |
| **4-month standard scope** | 30,686,671/4mo | 306,866,710 | **278.3 min (4.64 hr)** |
| 6-continuous-months | 43,173,271 | 431,732,710 | **391.6 min (6.53 hr)** |

(4-month row: 30,686,671 is the sum across the 4 non-contiguous windows, ×10 configs.)

**Port effort (task count, not hours):**
1. Tick loader — read/decode tick source (format TBD: MT5 `.tkc` export or CSV) into
   the same in-memory row structure `simular_variant` expects, generalized from
   the existing `_load_bars` bar loader.
2. Tick-level exit evaluation — SL/TP/trail/reentry checks currently run once per
   closed bar must run per tick (intrabar price path), replacing the current
   bar-OHLC-implied "worst case" exit approximation with true sequential tick
   exposure.
3. Tick-level entry-signal timing — confirm_mode/confirm_count logic currently
   keyed to bar closes needs a tick-vs-bar-boundary reconciliation (do signals
   still evaluate at bar close, or does entry timing become tick-precise too —
   a design decision, not just a mechanical port).
4. AC-modulate / reentry / SAR-adaptive levers — verify each is timeframe-input-based
   (should port unchanged, since they operate on the underlying EMA/SAR/AC state,
   not directly on OHLC) vs. re-derive per-tick.
5. Golden/parity test — compare tick-mode output against the existing bar-mode
   output on a known window to confirm no silent behavior drift before trusting
   tick-mode numbers for a demo greenlight decision.

---

## Route B — MT5 Strategy Tester "Every tick based on real ticks"

**1. Evidence search results:**

- `D:/FOREX/MT5_Tester/Bases/Capitaria-All/ticks/XAUUSD/` contains real tick
  cache files `202601.tkc` … `202607.tkc` (26–58 MB each) — i.e. **real tick
  data physically exists locally for 2026-01 through 2026-07**, but **not for
  2025-10** (no `202510.tkc`; that month would need a fresh Capitaria download).
- Searched `D:/WebDev/TOKATA/mt5/reports/*.htm` and `D:/FOREX/MT5_Tester/*.htm`
  for tester timing/tick-count headers. Found tick-count fields (`Ticks:`) but
  **no elapsed-time/duration field** — MT5's HTML tester report does not emit
  wall-clock run time by default. Example real numbers found:
  - `EMS_orig_SL60_trail170_d08.htm`: XAUUSD M1, period 2026.07.06–2026.07.08
    (2 days), **11,032 ticks**.
  - `EMS_wk_C04_TRAIL100.htm`: XAUUSD M1, period 2026.07.06–2026.07.10 (4 days),
    **16,548 ticks**.
  - `TOKATA_SAP_XAU_LS_ORIG_W4_001_m1.htm`: XAUUSD M5, period 2026.01.02–2026.05.15
    (~4.5 months), reports **515,126 Ticks** against only **25,762 Bars** and
    **"Calidad del historial: 100%"** — the ~20:1 tick:bar ratio is the signature
    of MT5's **"Open prices only"/generated-tick M1 mode**, not genuine
    "Every tick based on real ticks" mode (a true real-tick run over 4.5 months
    of XAUUSD would show tens of millions of ticks, consistent with the ~8.5M/mo
    figure measured in §1, not ~515K). **No genuine real-tick timing evidence
    was found in the historical reports or logs** (checked `MT5_Tester/logs/*.log`
    — these only show terminal startup/login events, no run-duration or
    ticks-processed-per-second telemetry).
  - Conclusion: **no empirical MT5 real-tick throughput number exists on this
    machine from prior runs.** The estimate below is assumption-based, not
    evidence-calibrated.

**2. Tick counts:** same as Route A's §1 table (volume-sum method).

**3. Estimate** (assumption: 1–5M ticks/min for a simple EA on this machine
class — wide range because no local calibration point was found; cites
industry-typical MT5 "Every tick" throughput folklore, not a measured number):

| Scope | Total ticks (×10 configs) | Time @ 5M/min (upper) | Time @ 1M/min (lower bound of range) |
|---|---|---|---|
| 1-month (Jun–Jul IW) | 84,674,190 | 16.9 min | 84.7 min |
| **4-month standard scope** | 306,866,710 | **61.4 min** | **306.9 min (5.1 hr)** |
| 6-continuous-months | 431,732,710 | 86.3 min | 431.7 min (7.2 hr) |

Plus **one-time tick-download overhead**: Capitaria server history download for
the 4 distinct months not fully covered by existing local cache. `.tkc` cache
exists for 2026-01→07 (covers 3 of the 4 standard-scope windows: Jun, May, Mar);
**2025-10 has no local tick cache and would need a fresh server-side download**
— assume 15–45 min for a single month's tick history over a live broker
connection (bandwidth/server-throttling dependent, no local evidence to calibrate
this either). Call it **+30 min** (midpoint) one-time, only for the 2025-10 window.

**4. CRITICAL CAVEAT — MQL5 port blocker (verified by direct grep of TOKATA sources):**

Searched every `.mq5` in `D:/WebDev/TOKATA/mt5/experts/` for `AC_Modulate`,
`Reentry`/`Re_Entry`, `SarAdaptive`/`Sar_Adaptive`, `VolRegime`/`Vol_Regime`.

- **`D:/WebDev/TOKATA/mt5/experts/TOKATA_EMASAR_v1.mq5`** is the only EA with
  anything matching: it has `AC_ExitEnable`, `AC_ConvictionRunner`,
  `AC_MagThreshold`, `AC_ModulateTrail` (bool) inputs — a **partial, unverified
  match** to Python's `ac_modulate` (bool) + `ac_modulate_factor` (0.01/0.10)
  pair; semantic equivalence between `AC_ModulateTrail` and `ac_modulate_factor`
  has **not** been confirmed and would need code-level comparison before trusting
  it as a drop-in.
- **`reentry_enable`/`reentry_max`** (the V-13 lever, used by SS-M5, V13-M5,
  SS-M15, V13-M15 — 4 of the 10 winners): **does not exist anywhere** in the
  TOKATA MQL5 sources.
- **`sar_adaptive`/`sar_fast`/`sar_slow`/`vol_regime_window`** (the V-15 lever,
  used by SS-M5, SS-M15, V15-M15 — 3 of the 10 winners): **does not exist
  anywhere** in the TOKATA MQL5 sources.

**Port scope (feature count, not hours):**
1. Verify/complete `AC_ModulateTrail` ↔ `ac_modulate`+`ac_modulate_factor`
   semantic parity in `TOKATA_EMASAR_v1.mq5` (may be a partial match already,
   needs a side-by-side param audit).
2. Implement reentry logic (`reentry_enable`, `reentry_max`) from scratch in MQL5.
3. Implement adaptive-SAR-by-volatility-regime logic (`sar_adaptive`, dual
   fast/slow SAR step pairs, `vol_regime_window` lookback) from scratch in MQL5.
4. Re-validate parity between the ported MQL5 EA and the Python reference engine
   on a known window (the project already has a "parity gate" pattern used
   elsewhere in this codebase — same discipline would apply here) before trusting
   any MT5 real-tick number for a greenlight decision.

**7 of the 10 winning configs use at least one of the two missing levers**
(reentry and/or sar_adaptive) — only V06d-M5, V06c-M5, V06d-M15, V06c-M15,
V06b-M15 (5 configs, and even some of those overlap the ac_modulate uncertainty)
are close to the skeleton-only params the current EA already exposes.

---

## Side-by-side: 4-month standard scope

| Route | Compute time | One-time overhead | Total | Confidence |
|---|---|---|---|---|
| **A — Python tick sim (extended engine)** | 278.3 min (4.64 hr) | ~2 min data-load | **~4.7 hr** | Compute number is a throughput extrapolation from a real benchmark (measured 22–24K bars/sec, 1.25× slowdown assumption); engine does not exist yet — port effort (4 tasks, §Route A) is unscheduled work on top of this number. |
| **B — MT5 "Every tick" real-tick tester** | 61–307 min (1.0–5.1 hr) | +30 min tick download (2025-10 only) | **~1.5–5.6 hr** | Compute number has **no local calibration evidence** (wide 5× assumption range); and is **blocked** — 7 of 10 winning configs cannot run at all until reentry + sar_adaptive (and possibly ac_modulate parity) are ported to MQL5 (unscheduled work, §Route B pt.4). |

**Recommendation:** Route A is faster to *trustworthy* numbers, not because its
compute time is shorter (it's comparable to or slower than Route B's midpoint),
but because **Route A's blocker is "extend Python code we already understand and
can unit-test against the existing bar engine,"** while **Route B's blocker is
"port three levers into MQL5 blind, with zero local real-tick throughput
evidence to sanity-check the estimate against."** Route A's port items (tick
loader, tick-level exit eval, signal-timing reconciliation) are mechanical
extensions of code already in this repo, immediately parity-testable against
the bar-mode engine that's the source of truth for the current 10-winner
selection. Route B's port items require writing genuinely new MQL5 logic for
levers that don't exist in any EA today, then trusting an MT5 tester throughput
number this session found no evidence for — meaning the real risk in Route B
isn't the ~1–5 hour compute estimate, it's the unbounded time to first-correct
MQL5 port of reentry/sar_adaptive plus the parity-gate work to trust it. If the
trader's priority is "cheapest path to a demo-account greenlight number I can
trust," start Route A's tick loader now; treat Route B as the eventual
production-EA path (it has to happen before live trading regardless) but not
the fast path to a trustworthy real-tick validation number this week.
