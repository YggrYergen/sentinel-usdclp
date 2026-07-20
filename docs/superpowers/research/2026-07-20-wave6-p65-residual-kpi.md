# P65 (Wave 6 governance) — sim-vs-live NET RESIDUAL tracked KPI

**Date:** 2026-07-20 · **Branch:** `alvaro` · **Task:** P65 (last of Wave 6 governance)
**Script:** `scripts/report/gen_residual_kpi.py` · **Tests:** `tests/scripts/test_gen_residual_kpi.py`
**Artifact:** `docs/superpowers/research/2026-07-20-wave6-p65-residual-kpi.json`

## What this KPI is

A **governance-only tracked KPI**: the sim-expected-vs-live-actual **NET RESIDUAL**
per config (and total), over a period, with the by-design cost components broken
out so any residual is **attributable, not mysterious**:

```
residual        = live_net − sim_expected_net
same_bar_cost   = SAME_BAR "same-bar optimism" by-design cost (from audit telemetry)
sl_clamp_gap    = SL_CLAMP gap (desired SL closer to market than trade_stops_level)
by_design_total = same_bar_cost + sl_clamp_gap
unexplained     = residual − by_design_total
```

It is a **report artifact + a queryable value**. It NEVER writes a run, a score,
or a DSR; it never imports the scoring/DSR mutators; it never touches the running
live executor. Deterministic: identical inputs → byte-identical JSON.

## What was reused (not reinvented)

- **`scripts/live/run_live_20.py` audit-log telemetry** — the live side is parsed
  READ-ONLY from `scripts/live/run_live_20.audit.log`: the per-config
  `SAME_BAR cumulative by-design cost (this run)` and `SL_CLAMP cumulative gap
  (this run)` lines, plus `SENT OPEN`/`SENT CLOSE` fills. The running GOLIVE
  daemon writes this log; it is treated strictly as read-only.
- **`sentinel_engine.strategies.live_configs_20`** (`CONFIGS_20`, `_fixed`) — to
  resolve each audit-log config id (base ids and their `-F` fixed siblings) to
  the exact `simular_variant` kwargs, so the sim side aligns 1:1 with the audit
  keys.
- **`scripts/live/check_live_sim_parity.py`** (`load_bars`, `sim_positions`) — the
  existing lake loader and sim event→position mapping, reused verbatim for the
  sim-expected net (`simular_variant(..., live_fill_mode=True)` over the window,
  honest-fills bound, flat-0.5 spread crossed at fill — the same model as
  `gen_livefill_bound.py`).

## Honest coverage — current residual is "insufficient live sample"

The audit log records the **by-design telemetry** (SAME_BAR / SL_CLAMP cumulative)
and realized **fill counts** (SENT OPEN/CLOSE), but it records **no realized
per-config P&L**. Verified: `grep -in "profit|pnl|realized|net=|equity"` over the
120,996-line audit log returns nothing but the connect banners.

Therefore the **live-net side of the residual is not observable from telemetry
alone**. There ARE substantial fills (e.g. V13-M2: 438 opens, V15-M2: 346,
SS-M1: 315 — well above any reasonable sample floor), so the binding constraint
is **not** sample size — it is the **absence of a realized per-config net series**.
The KPI reports `status = "insufficient_live_sample"` for the residual accordingly,
rather than fabricating a number.

Crucially, the KPI **still reports the by-design components**, which ARE observable.
Current parse of the real audit log (`--min-live-fills 10`, no `--start/--end` so the
sim side is deliberately absent → residual honestly `None`):

```
total: status = insufficient_live_sample
  same_bar_cost   = -1335.5764   (sum of the by-design SAME_BAR optimism)
  sl_clamp_gap    =   +75.0499
  by_design_total = -1260.5265
  residual        = null
  n_configs = 29,  n_ok = 0
```

Per-config highlights (same_bar_cost, USD): V13-M2 −80.73, V11-M2 −73.65,
V15-M2 −72.53, V15-M15 −45.43; `-F` siblings are net-positive same_bar
(e.g. V15-M2-F +24.11) because their `live_fill_mode=True` exits already remove
most of the optimism. SL_CLAMP gaps concentrate in the `-F` siblings
(V13-M2-F +29.65, V15-M2-F +21.53).

### Caveat on the cumulative aggregation (flagged, not hidden)

The `... cumulative ... (this run)` lines are **per-daemon-run running totals** that
reset each time the executor restarts. The parser takes **last-value-wins per
config across the whole concatenated log**, so the figure above is the last
observed running total for each config, NOT a strict sum across all runs (different
runs traded different rosters). This is adequate for a design-level KPI and is
honest about what it is; a future refinement could segment by daemon-run boundary
(`connected + guard OK` markers) and sum per-run finals if a precise lifetime total
is wanted. It changes nothing about the residual verdict (still insufficient).

## How to get a real residual once realized net lands

When a realized per-config net series exists (e.g. from `deals_raw` P&L in
`data/research.db`, or a future audit-log P&L field), pass it as
`live_realized_nets` to `residual_report(...)` and supply `--start/--end` so the
sim-expected side runs. Rows with ≥ `min_live_fills` fills and a realized net then
flip to `status="OK"` with a computed `residual` and `unexplained` (= residual −
by_design_total). The by-design breakout makes it immediately clear how much of any
residual is the known SAME_BAR/SL_CLAMP tax versus a genuine unexplained gap.

## Tests (TDD — written first, then implemented)

`tests/scripts/test_gen_residual_kpi.py` (11 tests, all pass):

- `test_parse_same_bar_and_sl_clamp_per_config` — per-config by-design parse, `-F` siblings independent, missing SL_CLAMP → 0.0
- `test_parse_fill_counts` — per-config SENT OPEN tally; SENT CLOSE at total level
- `test_parse_last_cumulative_wins` — later running-total line supersedes earlier
- `test_parse_empty_log` — empty log → `{"_total": {...}}`
- `test_residual_math_and_breakout_sums` — residual = live − sim; by_design_total = same_bar + sl_clamp; unexplained sums correctly
- `test_insufficient_live_sample_when_realized_net_absent` — None realized net → insufficient, but by-design still reported
- `test_insufficient_live_sample_when_fills_below_threshold` — fills < min → insufficient
- `test_residual_report_totals_and_determinism` — total = Σ OK-row residuals; byte-identical JSON on repeat
- `test_residual_report_insufficient_when_no_live_net` — no realized series → total insufficient, by-design still surfaces
- `test_default_min_live_fills_is_conservative` — default > 1
- `test_no_scoring_or_dsr_mutation` — no registry constant mutation; module never references `insert_run`/`deflated_sharpe_ratio`

Regression gate `tests/golden/test_parity.py` stays green (3 passed), and the
existing `tests/scripts/test_check_live_sim_parity.py` (17) stays green.
**Combined: 31 passed.**

## Verdict

The KPI is wired and honest. It attributes the observable by-design cost
(SAME_BAR + SL_CLAMP, currently ≈ −$1,260 aggregate last-run tax) and, per the
task's honesty requirement, **reports `insufficient_live_sample` for the net
residual** because the live daemon's audit log carries no realized per-config P&L
— not because history is thin (it isn't). The moment a realized-net series is
available, the same code computes and decomposes the true residual with no change.
