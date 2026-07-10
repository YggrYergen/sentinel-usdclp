# EMASAR V1 (3 fichas) — MT5-fidelity integration + Trade View rendering — design

> Date: 2026-07-10 · Project: SENTINEL V2+TOKATA · Phase: REVIEW — real V1 positions
> Status: APPROVED (approach) — pending spec review → writing-plans
> Supersedes the "connectors/highlight/popups" framing: those are Phase B here.

## Context

The REVIEW "Trade View" must show the **real EMASAR V1 positions** — the improved
strategy backtested in the sibling project **TOKATA** (`D:\WebDev\TOKATA`) — with
each entry connected to its **three exits**, highlighted, and annotated with why
each leg closed and how much it made.

Re-contextualization (the "descontextualización" that triggered this spec):

- **EMASAR has two modes.** **V1 (`strategy_mode=1`) opens THREE fichas per signal**
  (F1, F2, F3 at the same entry) that exit independently: F1→`EXIT_ENGULF`,
  F2→`EXIT_STFLIP` (SuperTrend flip), F3 (conviction runner)→`EXIT_TRAIL` /
  `EXIT_MOMSLOPE` / `EXIT_MOMSTALL`; any→`EXIT_INITSL` / `EXIT_ACDECEL`. **V2
  (`strategy_mode=2`) is a single ficha, engulfing-only exit.**
- **SENTINEL today only does V2.** `sentinel_engine/strategies/emasar.py` +
  `sim/lite.py` produce single-exit trades. That is why current trades have one
  exit — it is the V2 simplification, not the real V1.
- **The V1 positions are NOT in SENTINEL.** The two V1 runs in `research.db`
  (`EMS-ORIG-sar3m3` +1624.6, `EMS-ORIG-TF-sar3m3` −2064.5) hold **summary
  metrics only — the trades endpoint returns 0**. The real 3-ficha positions live
  in MT5 / TOKATA: the Strategy-Tester `.htm` reports (e.g.
  `D:\WebDev\TOKATA\mt5\reports\TOKATA_EMS_XAU_V1_M5_c2_sar3m3_m1.htm`) and were
  only ever visualized inside MT5's own visual tester ("Camino A").
- **No cross-engine parity exists for emasar.** SENTINEL's golden parity gate
  covers the scoring engine, not emasar; no SENTINEL test references
  `emasar_ref`. So SENTINEL emasar results are unvalidated vs MT5 — the user's
  core concern.

### Fidelity decision (user, normative)

- **Signal parity: exact (hard gate).** Same fichas, same entry/exit bars, same
  exit reasons.
- **Monetary parity: identical to the cent.**
- **Reconcile against the MT5 `.htm`.**

The resolving insight (verified in the `.htm` deals): the report **already
contains MT5's exact per-deal price, profit, commission, swap and balance**. At
`2026.01.11 20:00:00` three `buy in` deals at `4511.96` (F1/F2/F3) close as three
separate `sell out` deals (+154.10 / +280.30 / +551.70). Therefore **identical-to-
the-cent is achieved by IMPORTING the deals, not re-simulating** — the numbers are
MT5's own, by construction. No tick-level simulator and no tester tick-base
(absent on this machine) are needed.

## Goal

Integrate real EMASAR **V1** positions into SENTINEL with **MT5-identical**
numbers and render them in Trade View — generic across any winning cell in the
TOKATA ledger — with a **signal-parity fidelity gate** so every ingested run
carries a proof it reproduces the MT5 signals.

## Architecture — hybrid: import numbers, annotate + verify with `emasar_ref`

| Layer | Source | Guarantee |
|---|---|---|
| Positions / prices / P&L / balance | **Imported from MT5 `.htm` deals** | Identical to the cent (MT5's own output) |
| Ficha (F1/F2/F3) + exit reason (`motivo`) | **`emasar_ref.simular`** (match to deals) | Annotation for popups / grouping |
| Overlays EMA/SAR/**SuperTrend**/AO/AC/Mom | **`emasar_ref`** series (already computed) | Visual context |
| **Signal-parity gate (T1)** | `emasar_ref` events **vs** imported deals | Fails ingest if entries/exits diverge |

This dissolves the "two diverging engines" risk: displayed numbers do **not**
depend on any SENTINEL engine; `emasar_ref` only annotates and **verifies**.

### Component 1 — MT5 `.htm` deal parser (new)

`sentinel_engine/research/mt5_report.py`: parse the UTF-16 Strategy-Tester `.htm`
→ ordered deals `{ts, order, symbol, type(buy/sell), dir(in/out), volume, price,
commission, swap, profit, balance, comment}` + the settings block (symbol,
period, model, spread, initial deposit) for provenance. Pure parsing, no MT5
dependency, explicit utf-8/utf-16 handling (Win10/11 safe).

### Component 2 — position/ficha reconstruction + annotation (new)

`sentinel_engine/research/ingest_mt5_deals.py`:
1. **Pair deals into positions** (each `in`→its `out`; 0.1 lot fichas). Consecutive
   `in` deals at the same timestamp/price = the fichas of **one signal** → assign a
   `signal_id`.
2. **Run `emasar_ref.simular(bars, strategy_mode=1, …)`** on the run's bars (params
   parsed from the variant tag, same as `parse_tag_emasar`) → events carrying
   `ficha` + `motivo`.
3. **Match** emasar_ref entry/exit events to MT5 deals (by ts/price within a bar
   tolerance) → tag each imported position with `ficha` (F1/F2/F3) and `motivo`
   (ENGULF/STFLIP/TRAIL/MOMSLOPE/MOMSTALL/INITSL/ACDECEL). Fallback for exits: the
   `.htm` `sl <price>` comment marks stop hits.

### Component 3 — fidelity reconciliation gate (new)

For each ingested cell, emit a **fidelity report** artifact:
- **T1 signal parity (hard):** every MT5 entry/exit has a matching emasar_ref
  event (count + timestamps); fail loud + refuse to mark the run "certified" if not.
- **Monetary:** imported net/PF/DD is MT5's by construction; also cross-check it
  equals the ledger summary already in `research.db` and the `.htm` totals.
- Stored alongside the run (`run.fidelity_ref` → JSON) and asserted in tests.

### Component 4 — data model (extend `registry2`, additive/nullable)

Each ficha = one `trade` row (existing schema: `ts_in/ts_out/px_in/px_out/side/
pnl/exit_reason/...`). Add nullable columns:
- `signal_id TEXT` — groups the 3 fichas of one entry (NULL for legacy single-exit
  sim trades → fully backward compatible).
- `ficha TEXT` — `F1|F2|F3`.
- `exit_reason` = `motivo`; `exit_reason_source` = `emasar_ref` | `mt5-comment`.
Run row: `engine = "mt5-import"`, `fidelity = "mt5-htm"`, provenance = report path.

### Component 5 — vendored reference engine

`emasar_ref.py` lives in TOKATA and is the validated source of truth. Vendor a
**frozen copy** into `sentinel_engine/strategies/emasar_ref.py` with a provenance
header + a golden test pinning its output, so SENTINEL stays self-contained
(Win10/11, no cross-project import at runtime) while inheriting the validated
math. SENTINEL's existing V2 `emasar.py` is untouched (legacy sim path).

### Component 6 — Trade View rendering (Phase B, `web/`)

Extends the existing chart/overlay/connector code (`web/lib/chart.js`,
`web/sections/review.js`) — no rewrite:
- **Group by `signal_id`:** one entry marker + three exit markers, joined by
  **three dotted connectors** (entry→each ficha's exit). Generalizes today's
  entry→single-exit connector to entry→N-exits.
- **Highlight selected signal:** the whole signal (entry + 3 exits + connectors)
  brightened; others dimmed.
- **Hover popups** on entry/exit/connector: ficha, `motivo`, entry/exit price,
  per-ficha P&L, duration — reading the imported fields.
- **SuperTrend overlay** added to the indicators endpoint (Component 7) + a chip,
  since F2 exits on the SuperTrend flip. (AO/AC/Momentum subpanels: noted, deferred
  unless trivial.)
- Works for **any** imported V1 run (ledger winners), selected from the run list.

### Component 7 — indicators endpoint extension

Extend `GET /api/runs/{id}/indicators` (built for EMA/SAR) with **SuperTrend**
(and optionally AO/AC/Mom) computed via the vendored `emasar_ref`, same
list-of-descriptors shape, so the overlay chips pick it up with no UI rewrite.

## Data flow

```
ingest a ledger cell (e.g. EMS_XAU_V1_M5_c2_sar3m3):
  parse .htm deals ──► pair into positions ──► group fichas by signal_id
        │                                             │
        └── run emasar_ref.simular(V1) on same bars ──┤ match events↔deals
                                                      ▼
             assign ficha+motivo ; reconcile (T1 signal gate) ; fidelity report
                                                      ▼
             upsert run(engine=mt5-import) + insert 3-ficha trades + fidelity_ref
review UI:
  pick run ──► /trades (grouped by signal_id) + /indicators (EMA/SAR/SuperTrend)
          ──► entry + 3 connectors + 3 exits ; highlight ; hover popups
```

## Error handling / degradation

- **Bars unavailable for the period** (lake gap, e.g. pre-2026-03-25): positions +
  P&L still import (identical, from `.htm`); annotation/overlays/signal-gate that
  need `emasar_ref` are marked "not verified — bars unavailable" in the fidelity
  report instead of crashing. Certifying a winner therefore **requires** its bars;
  obtaining them (lake extension / MT5 export) is a documented prerequisite.
- **Deal↔event match ambiguity** (multiple exits same ts): resolve by price then
  order sequence; unmatched legs flagged in the report (do not silently guess).
- **Parse failure / malformed `.htm`:** hard error naming the file.

## Testing

**Parser/import (`tests/research/`):** parse the real
`TOKATA_EMS_XAU_V1_M5_c2_sar3m3_m1.htm` → deal count, the 01-11 3-ficha signal
(3 ins @4511.96, 3 outs +154.10/+280.30/+551.70), prices/P&L exact; UTF-16 handled.
**Reconstruction:** 3 `in`@same ts → one `signal_id`, three fichas; each paired to
an `out`.
**Fidelity gate:** emasar_ref events match imported deals on a known window → T1
pass; a deliberately corrupted deal set → T1 fail. Imported net == ledger summary
== `.htm` totals (to the cent).
**Data model:** `signal_id`/`ficha` populated; legacy sim trades (NULL) unaffected;
scoring golden parity (`tests/golden/test_parity.py`) stays green.
**Vendored engine:** golden test pins `emasar_ref` output.
**Frontend (`tests/service/test_web_*`):** signal grouping → 3 connectors; popup
wiring; SuperTrend chip + indicators endpoint returns it.
**Browser verify (Playwright):** load an imported V1 run → one entry + three
connected exits per signal, highlight on select, hover popups with motivo + per-
ficha P&L, SuperTrend overlay toggles.

## Implementation phases (single spec, phased build)

1. `.htm` parser + provenance (Component 1) + tests.
2. Vendored `emasar_ref` + golden (Component 5).
3. Reconstruction + annotation + reconciliation gate + data model (Components 2–4).
4. Ingest CLI for a ledger cell → certified V1 run in `research.db`.
5. Indicators endpoint: SuperTrend (Component 7).
6. Trade View rendering: grouping, 3 connectors, highlight, popups (Component 6).

## Non-goals

- No changes to the scoring engine or its parity gate.
- No live/forward execution; real accounts stay READ-ONLY.
- No re-port of V1 into SENTINEL's own sim engine (we import MT5 numbers + reuse
  the validated `emasar_ref` for annotation/verification).
- AO/AC/Momentum subpanels and non-EMASAR strategies: out of scope here.
