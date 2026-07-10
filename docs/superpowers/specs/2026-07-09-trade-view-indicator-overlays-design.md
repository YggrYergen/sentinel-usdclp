# Trade View — indicator overlays (EMA/SAR) — design

> Date: 2026-07-09 · Project: SENTINEL V2+TOKATA · Phase: REVIEW UI refinement
> Status: APPROVED (design) — pending spec review → writing-plans

## Context

The REVIEW "Trade View" (`web/sections/review.js`) lets a user open a strategy
run and step through its trades on a chart. Today the chart shows candles +
trade markers but **no strategy indicators**, so you cannot see *why* the
strategy entered/exited. The user wants the same **OVERLAYS** experience that
already exists in the `charts` section (toggle chips), but showing the
indicators the **emasar** strategy actually uses: **EMA-fast, EMA-slow, and
Parabolic SAR** — drawn with the *exact* parameters that run used, so the lines
match what drove the trades.

Two facts constrain the design:

- **Parity is required** (user decision): indicators must use each run's real
  params, not hardcoded values. For the current run
  `emasar_XAUUSD_M2_orig_sar3m3_repro` that is EMA-fast **8**, EMA-slow **20**,
  SAR step/max **0.3 / 0.3**. (The user says "EMA9" colloquially but approved
  respecting the real config = EMA8; chips self-label with the real period.)
- The strategy's canonical indicator math lives in
  `sentinel_engine/strategies/emasar.py` (`ema_series(closes, period)`,
  `sar_series(highs, lows, step, max_step) -> (sar, trend)`). Re-porting SAR to
  JS would risk divergence from the strategy, breaking parity.

**Out of scope for this spec** (explicitly deferred to a *separate* next spec):
entry↔exit dotted connectors, highlighting the selected trade, and hover
popups with per-leg P&L. The "three exits per entry" model those depend on does
not exist in current sim trades (single `ts_out`); it arrives with the improved
strategy from a separate session.

## Goal

Add a toggleable indicator-overlay layer to the REVIEW Trade View chart —
EMA-fast, EMA-slow, and SAR — computed on the backend with the run's exact
params for parity, rendered in the existing `charts` OVERLAYS chip style, and
**extensible** so more indicators can be added later by extending one endpoint.

## Architecture

Chosen approach: **backend indicator endpoint** (parity-safe, no duplicated
math). Rejected alternatives: client-side compute (duplicates SAR math →
divergence risk, conflicts with parity); persist-at-backtest-time (schema
change, doesn't help the 273 existing runs).

### 1. Backend — `GET /api/runs/{run_id}/indicators?tf=<tf>`

New endpoint in `sentinel_engine/service/app.py`.

- **Resolve params:** from `run.params_hash → param_set.params_json`; fall back
  to `variant.params_delta` merged over `EMASAR_DEFAULTS` (reuse the same
  merge `_build_policy`/`EmasarPolicy` uses so values are identical to the run).
- **Resolve tf:** query param `tf` (defaults to the run's native tf from the
  `variant.tf` record). Indicators are computed on the **bars for that tf**.
- **Load bars:** reuse the existing bar-loading path behind `GET /api/bars`
  (same lake/store, same symbol from the run's `instrumento`).
- **Compute:** call `emasar.py` directly —
  `ema_series(closes, params["ema_fast"])`,
  `ema_series(closes, params["ema_slow"])`,
  `sar_series(highs, lows, params["sar_step"], params["sar_max"])`.
- **Response shape** (params echoed so the UI self-labels and stays generic):

  ```json
  {
    "tf": "M2",
    "indicators": [
      {"id": "ema_fast", "kind": "line", "label": "EMA8",
       "period": 8, "points": [[ts, val], ...]},
      {"id": "ema_slow", "kind": "line", "label": "EMA20",
       "period": 20, "points": [[ts, val], ...]},
      {"id": "sar", "kind": "dots", "label": "SAR 0.3/0.3",
       "step": 0.3, "max": 0.3, "points": [[ts, val], ...]}
    ]
  }
  ```

  `null` indicator values (warm-up bars) are emitted as `null` and skipped by
  the renderer. Returning a **list of indicator descriptors** (not fixed keys)
  is what makes "add more later" a one-endpoint change.

### 2. Frontend chart lib — `web/lib/chart.js`

- EMA lines reuse the existing `addOverlay(id, points, color)` /
  `removeOverlay(id)` API (already `addLineSeries`-backed).
- **New `addSarDots(id, points, color)` / removed via `removeOverlay(id)`:** SAR
  is per-bar dots, not a continuous line (a line series would draw a misleading
  zig-zag). Implement as a lightweight-charts line series with `lineWidth: 0`
  and point markers visible (small radius), or an equivalent dot rendering.
  Registered in the same `overlays` map so `removeOverlay` and teardown work
  uniformly.

### 3. Frontend REVIEW — `web/sections/review.js`

- **OVERLAYS chip group** added to `reviewToolbar`, reusing the existing
  `.charts-overlay-chip` / `.charts-overlay-chips` CSS classes (no new styles).
  Chips are built from the endpoint's `indicators[].label`; toggling a chip
  calls `addOverlay`/`addSarDots` or `removeOverlay`.
- **Fetch trigger:** on run load and on TF change, fetch
  `/api/runs/{run_id}/indicators?tf=<currentTf>`; redraw currently-active chips
  against the new tf's series. Active chip set persists across tf switches.
- **Native-tf default (folded-in fix):** open the Trade View chart on the run's
  **native tf** (from the run/variant record) instead of the hardcoded
  `appState.tf || "M1"` (`review.js:345,423`). This also removes the
  *"Sin barras para XAUUSD M1"* empty state seen when an M2 run opened on M1.

## Data flow

```
run pick / tf change
  → GET /api/runs/{id}/indicators?tf=TF
      → resolve params (params_hash → param_set | variant.params_delta+defaults)
      → load bars(symbol, TF)  [reuse /api/bars path]
      → ema_series / sar_series  [emasar.py, same as the run]
      → [{id,kind,label,points,...}]
  → build/refresh OVERLAYS chips from indicators[]
  → per active chip: addOverlay (lines) | addSarDots (SAR)
```

## Testing

**Backend (pytest, `tests/service/`):**
- **Parity:** endpoint's `ema_fast`/`ema_slow`/`sar` points equal a direct
  `emasar.py` call (`ema_series`/`sar_series`) on the same bars — same params
  resolved from `params_hash`.
- **Params resolution:** a run whose variant overrides `sar_step`/`sar_max`
  (the `sar3m3` case → 0.3/0.3) yields those values in the response labels.
- **tf:** `?tf=` selects the bar set; default tf = the run's native tf.
- **Errors:** unknown `run_id` → 404-style `_api_error`; tf with no bars →
  empty `points`, not a crash.

**Frontend (`tests/service/test_web_*.py`, static asserts, existing pattern):**
- `review.js` contains the OVERLAYS chip group and fetches
  `/api/runs/{...}/indicators`.
- `chart.js` exposes `addSarDots` and registers it in the overlays map.
- Default tf is derived from the run (not the hardcoded `"M1"`).

**Browser verify (Playwright, as this session):** open REVIEW → pick the
`sar3m3` run → chart opens on M2 (no "Sin barras") → toggle EMA8/EMA20/SAR
chips → EMA lines and SAR dots render aligned to candles → switch tf → overlays
recompute → toggle off → series removed.

## Extensibility

Adding an indicator later = add one descriptor to the endpoint's `indicators[]`
(with `kind: "line"` or `"dots"`); the chip group and renderer are
data-driven, so no UI rewrite is needed.
