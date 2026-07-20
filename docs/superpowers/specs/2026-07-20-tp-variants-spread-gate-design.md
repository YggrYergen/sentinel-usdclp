# Design — TP-min & trail-half variant families + live spread-gate + stops-level self-solve

> Date: 2026-07-20 | Branch: `alvaro` | Program: Honest Program — Complete the 66 (Wave 6+)
> Thread: `20260720-073733-7mwm` (key `C--Users-tomas`) | Ledger: `.superpowers/sdd/progress.md`

## 1. Motivation & honest framing

User directive (2026-07-20): add strategy variants that pair **all winning levers** (the carried
M15 V-15 **SAR + vol-target** champion base) with a **minimum-viable take-profit**, to "maximize net
positive / minimize losses." Root observation from the live demo stack (machine2): open positions
"never take profit despite plenty of room." **Load-bearing correction:** that is not a bug — the live
executor (`scripts/live/run_live_20.py`) is **SL/trail-only by design** and never installs a TP. So
this is a *feature to add*, mirrored in sim so parity holds.

**Honesty constraints (non-negotiable):**
- "Remain net positive on ALL positions" is NOT achievable as a guarantee. A min-TP raises hit-rate
  but caps upside; a large adverse move before TP still loses. We build it and run it through the
  **same honest pipeline** (P35 WF + DSR + guards, flat-0.5 cost, fixed lot 0.10, windows {IW,W1,W2,W3})
  and report whether it actually lifts net/DSR vs the luck-bar — not whether it "feels" safer.
- The offline sim has no per-bar spread; the "tightest legal TP" in sim is a **fixed pip proxy**. The
  live executor uses the true dynamic `max(stops_level, spread)`. The sim↔live gap is exactly the
  residual **P65** tracks. Disclose this in the report.

## 2. Family A — TP-MIN lever (sim)

New **additive, no-op-default** lever `tp_min_pips: float | None = None` on
`sentinel_engine/strategies/emasar_variant.py::simular_variant`.

- Semantics: at each ficha's fill, set a fixed TP target at `entry ± tp_min_pips * pip` (long: +, short: −).
  "Tightest legal distance" = the sim proxy for live `max(stops_level, spread)`; `tp_min_pips` is the
  configurable proxy value. Applies to **all fichas** (F1/F2/F3), distinct from the existing R-multiple
  `f1_tp_r`/`f2_tp_r` (F1/F2 only).
- Armed at entry, **fixed once armed** (does not move). Ordinary trailing continues on top; **whichever
  level a bar touches first exits the ficha**.
- **Conservative same-bar fill:** if a single bar would touch BOTH the TP and the initial/trailing SL,
  the **SL takes precedence** (ficha exits at the SL, not the TP) — mirrors the existing V-05 TP
  same-bar convention. No new fill route invented (close-of-bar / touch semantics as today).
- `tp_min_pips=None` (or ≤0) → disabled → **byte-identical** to current engine (pinned classic
  byte-identity test, per D7).

## 3. Family B — TRAIL-HALF (manifest only, no code)

Contrast set: champion base with the per-ficha trail distances **halved**
(`f{1,2,3}_trail_pips` → /2, i.e. 289/230/170 → 144.5/115/85; or `f{1,2,3}_trail_range_k` → /2 when
`trail_mode_ladder='range'`). Expressed purely as **new manifest grid cells** over existing params —
**no strategy-code change**. Byte-identity of the base engine is unaffected.

## 4. Live executor track (machine2 demo) — sequenced AFTER sim validation

Do **not** touch the live/demo stack until Family A is validated in the honest league. Then:
- **Mirror `tp_min` in `run_live_20`:** install a server-side TP alongside the SL (extend the
  `TRADE_ACTION_SLTP` request to carry `tp`), at the broker-legal distance via the existing
  `_stops_level_points()` / `_clamp_sl()` machinery (add a `_clamp_tp` sibling). Parity enforced by **P36**.
- **Spread-gate:** OPEN only when current spread ≤ threshold (`--max-spread-open`, default = observed
  XAUUSD minimum; configurable). Skips/defers OPENs when spread is above threshold; logged, reconciler
  re-evaluates next cycle. Exits/MODIFY are never gated. DEMO-only (D7: PROD `--arm` stack untouched).

## 5. Stops-level self-solve (empirical)

Capitaria has refused to provide min-distance / stops-level info. MT5 reports
`symbol_info.trade_stops_level = 0` for XAUUSD (dynamic/spread-based). We **discover the true minimum
empirically**: log rejected MODIFY/OPEN retcodes (10016 "invalid stops") vs the sent distance and the
tick spread at send time, over the live demo session; fit the effective floor as
`f(spread)` (likely `k * spread`). Feeds the live `_clamp_tp`/`_clamp_sl` floor and the sim proxy value.
This also **unblocks P59** (vendor MODIFY/stops-level limits were the parked blocker).

## 6. Honest pipeline & reporting

- Extend the growing manifest (`scripts/report/honest_manifest_full_2026_07_20_v2.json` → v3) with the
  Family-A `tp_min_pips` grid and the Family-B trail-half grid, on the M15 V-15 SAR (+vol-target) base,
  windows {IW,W1,W2,W3}, fixed lot 0.10.
- Run the honest sweep (`gen_honest_sweep.py`), score into ONE comparable DSR league.
- Report: net, PF, Sharpe, DSR/p, hit-rate, avg-win/avg-loss, vs champion and vs luck-bar (null-max).
  State the sim-proxy caveat and the sim↔live residual explicitly. Report **when results are in hand**.

## 7. Governance linkage

- **P36** parity suite must cover the new `tp` field across both fill modes + return_state combos.
- **P65** residual KPI is the tracking surface for the sim-proxy-TP vs live-dynamic-TP gap.
- **P63** AUDIT_REQUIRED auto-flag applies unchanged (a too-good min-TP result must auto-flag).

## 8. Sequencing (SDD, ≤2 parallel, Opus impl / Sonnet research report-only, TDD)

1. **A1 (Opus, TDD):** add `tp_min_pips` lever + byte-identity no-op test + behavior tests. [core]
2. **A2:** author manifest v3 (Family-A tp_min grid ∪ Family-B trail-half grid) on champion base.
3. **A3:** run honest sweep → consolidated DSR league → report (the deliverable to hand back).
4. **Wave-6 governance in parallel where files disjoint:** P36 parity (extend for `tp`), P63, P65.
5. **Live track (after A3 validates):** `run_live_20` TP + spread-gate + `_clamp_tp`; stops-level
   empirical self-solve; then deploy to machine2 with spread-gate.
6. **P4 live-replay track (parallel, separate files):** MT5 tick-export feasibility (Sonnet, report-only)
   + `.tkc` decoder (Sonnet→Opus-4.8-high escalation: 3 consecutive errors → Opus 2 retries → stop).

## 9a. Go-live selection & comparability (A4, after A3)

- **Comparability hard rule:** legacy/un-validated SIM reports are NON-comparable (optimistic close /
  same-bar look-ahead — the reason this pipeline exists). Rank ONLY on honest re-scores (live_fill +
  flat-0.5) and live DEMO FILLS (real broker fills = honest ground truth; the FIXED4 bleed counts).
- **Selection rule:** deploy the best **5** projected net-positive (even slight margin) + any marginal
  net-negative that flips positive under **thinnest-spread-only** trading.
- **Caveat 1:** net-positive-in-sample ≠ proven edge (nothing was DSR-significant). Frame the live run
  as a **live-forward OOS test** (demo/paper), not "proven winners."
- **Caveat 2:** the flat-0.5 offline league CANNOT model the spread-gate benefit. A4 must estimate the
  min-spread-only entry-cost delta from captured spread telemetry (P3 `tick_logger` data), per-config,
  and present it explicitly as an ESTIMATE.
- **Output:** a report ranking candidates, naming the top-5 + spread-rescued marginals, and specifying
  the EXACT live config (roster, `tp_min`, hard spread-gate per §4/D15, lot) → user decision.

## 9. Open defaults chosen (interrupt to change)
- `tp_min_pips` grid: proxy values spanning the plausible live min-distance (e.g. {5,10,20,40} pips of
  XAU) — A2 to finalize from the stops-level probe / observed spread.
- Spread-gate threshold default = observed XAUUSD session minimum (A5/live to calibrate).
- Trail-half applies to `_trail_pips` ladder (pips mode); `range_k` variant added if base uses range mode.
