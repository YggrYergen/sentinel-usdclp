# Trade View — Wave-2 (V1 signal grouping) + overlay/foundation bug fixes

> Created 2026-07-10 · track: SENTINEL Revamp UI · test run: `mt5import-abc1043ef513`
> Prereq specs: `docs/superpowers/specs/2026-07-09-trade-view-indicator-overlays-design.md`,
> `docs/superpowers/specs/2026-07-10-emasar-v1-mt5-integration-design.md`

## Context

The REVIEW Trade View must plot EMASAR **V1** positions: each signal has **3 fichas
(F1/F2/F3)** — one entry, three exits. The winner MT5 backtest was ingested as run
`mt5import-abc1043ef513` (23 signals × 3 fichas = 69 trades, net 1624.60). Wave-1
delivered the backend model (signal_id/ficha/exit_reason on `/trades`), the indicator
endpoint (EMA/SAR/SuperTrend), and playback. Wave-2 must draw the V1 grouping
(1 entry + 3 connected exits per signal, highlight, hover P&L) and fix the overlay
rendering, which currently **hides all candles**.

Empirical diagnosis (payloads from `:8601`, 2026-07-10) found **4 defects**, two of
which are foundation-breaking and must be fixed before the grouping UX is meaningful.

## Defects (fix in this wave)

### 🔴 B — overlay candle-killer (PRIMARY)
`GET /api/runs/{id}/indicators` returns the **entire lake history** (100,044 points,
2026-03-25→2026-07-07) regardless of the loaded candle window (~3000-bar tail). All
lightweight-charts series share ONE time scale, so injecting ~100k bars of history to
the *left* of the loaded candles pushes the candles off the right edge of the visible
logical range → "no candles visible; only SAR dots."
- **Invariant to enforce:** overlay time-range ⊆ candle time-range (never wider).
- **Backend** (`sentinel_engine/service/app.py::get_run_indicators`, ~L462): accept
  optional `from`/`to` (ISO-8601, same as `/api/bars`). Compute EMA/SAR/SuperTrend on
  a frame that includes a **warmup lookback** before `from` (slice
  `df[from - lookback : to]`, `lookback = max(periods)*4` bars is ample), then return
  ONLY points with `from <= t <= to`. If `from`/`to` omitted → keep current full-frame
  behavior (charts.js callers unaffected; but see frontend change).
- **Frontend** (`web/sections/review.js::fetchIndicators` ~L82,
  `refreshIndicators` ~L413): pass the chart's current window to the endpoint. Expose
  `winFrom`/`winTo` from `web/lib/chart.js` (new getters `get windowFrom()/windowTo()`,
  returning `winFrom`/`winTo` epoch secs). Call `refreshIndicators()` AFTER the window
  is set (i.e. after `selectTrade`/`setTF` resolve — `selectTrade` calls `setWindow`
  which updates `winFrom/winTo`). Overlays therefore always match the selected trade's
  window. Panning left (which extends candles but not overlays) is safe under the
  subset invariant.

### 🟠 A — line overlays throw on null warmup values
EMA-fast (7 leading nulls), EMA-slow (19), SuperTrend (9) carry `null` warmup values.
`web/lib/chart.js::setOverlaySeries` (~L321) maps them to `{time, value: null}`, which
is invalid line data in lightweight-charts (warmup gaps must be **whitespace** points,
`{time}` with NO `value` key) → `setData` throws → EMA/SuperTrend never render.
- **Fix:** in `setOverlaySeries`, map `null`/`undefined` values to `{ time }` only:
  ```js
  series.setData(points.map(([ts, val]) =>
    (val === null || val === undefined) ? { time: tsSec(ts) } : { time: tsSec(ts), value: val }));
  ```
  SAR (`setSarDotsSeries`) already filters nulls — leave as is.

### 🟠 D — MT5 timestamps parsed as browser-local time
`/trades` returns `ts_in`/`ts_out` as MT5 dotted strings (`2026.01.11 20:00:00`).
`new Date('2026.01.11 20:00:00')` parses as **browser-LOCAL** time (verified: −3h in
Chile), not UTC → markers/connectors land offset from the UTC candle axis.
- **Fix (backend, authoritative):** normalize `/trades` `ts_in`/`ts_out` to ISO-8601
  UTC (`2026-01-11T20:00:00Z`) in `registry2` trade serialization (or in the app
  endpoint). The MT5 tester times matched lake bars byte-identically in Wave-1 fidelity
  work → source is effectively UTC; reformat only, do not shift. **Verify in browser**
  that an in-window entry (e.g. F1 @ 4511.96, 2026-05-08 area) sits on its candle.
- Frontend `epochOf`/`buildMarkers` then parse ISO-UTC unambiguously (already use
  `new Date(...)` — ISO-`Z` removes the local-time ambiguity). If a server-time vs UTC
  offset surfaces during browser verification, handle it in the ingester, not the UI.

### 🔴 C — lake coverage (USER-IN-THE-LOOP, parallel track)
The 69 trades span 2026-01-11→2026-05-08 but the XAUUSD lake only covers late-Mar→Jul
→ only **21/69** trades currently have candles. **User decision: extend the lake.**
The Jan–May bars exist in the tester cache `MT5_Tester/Bases/Capitaria-All/history/XAUUSD`
(binary `.hcc`) — the live broker feed does NOT serve XAUUSD M1 before late March.
See "Lake extension" below. This track is independent of the code wave; the code fixes
verify on the 21 in-window trades now and cover all 69 once the lake is extended.

## Wave-2 UX requirements (build on the fixed foundation)

Data is READY: `/trades` already returns `signal_id`, `ficha`, `exit_reason`, `px_in`,
`px_out`, `pnl` per trade (verified). Only 7 `exit_reason` are `None`.

0. **Fill 7 null exit_reasons** deterministically from deal structure (V1: last ficha
   closed by opposite signal → `signal`/`flip`; SL/TP hits already labeled). Do it in
   the ingester/registry, not the UI.
1. **Group by `signal_id`:** ONE entry marker + THREE exit marks (F1/F2/F3) per signal.
2. **Dotted connectors:** entry→F1, entry→F2, entry→F3 (three dashed segments/signal).
   Reuse the connector machinery in `web/lib/chart.js` (`buildAllConnectorData`,
   `drawSelectedConnector`) — generalize from 1-exit to 3-exit per entry.
3. **Highlight selected signal:** entry + its 3 exits + 3 connectors bright; everything
   else dimmed (the current single-trade selection must select the whole SIGNAL group).
4. **Correct prices/times** from MT5 (no garbage): entry 4511.96; exits 4527.37 /
   4539.99 / 4567.13 for the sample signal.
5. **Hover popups** on entry/exit/connector: ficha (F1/F2/F3), exit_reason, px_in,
   px_out, **P&L per ficha**, duration. Extend the crosshair tooltip in `chart.js`.
6. **SuperTrend chip:** endpoint already returns it; once A is fixed the line renders —
   ensure the chip appears in `renderOverlayChips`.
7. **Trade list groups the 3 fichas under each signal** (`web/sections/review.js`
   vtable): signal header row + 3 ficha sub-rows, or grouped rendering.
8. **Generic** for any future V1 run (no hardcoded run/signal ids).

## Lake extension (Track C — scripted, user runs it)

Write `scripts/mt5_dump_tester_history.py` (variant of `scripts/mt5_dump_history.py`):
- `mt5.initialize(path=...)` against a terminal whose history base holds Jan–May
  (`MT5_Portable/terminal64.exe`; if it lacks the range, the user must point it at the
  tester install or scroll XAUUSD M1 back to Jan in the GUI first).
- `copy_rates_range('XAUUSD', tf, 2026-01-01, 2026-03-26)` for tf in {M1,M2,M5,M15,H1}.
- Write `data/raw/XAUUSD/<min>.csv`, ingest via
  `sentinel_engine.lake.ingest_mt5.ingest_mt5_csv(csv, 'XAUUSD', min, LAKE_ROOT)`
  (idempotent, dedupes on time — safe to overlap the existing March data).
- Verify: `load_tf_frame(lake,'XAUUSD','M1').index.min()` <= 2026-01-11.
**READ-ONLY**: history reads only; never select/place orders.

## Verification

- **Backend tests** (pytest): `/indicators` with `from`/`to` returns only in-window
  points, warmup-correct (EMA seeded from lookback); `/trades` emits ISO-UTC ts and no
  null exit_reason. Extend `tests/service/test_web_indicators.py`,
  `tests/service/test_web_review_overlays.py`, `tests/research/test_ingest_mt5_deals.py`.
- **Parity gate:** `python -m pytest tests/golden/test_parity.py` stays green.
- **Full suite:** `python -m pytest` (was 229 green in Wave-1).
- **Browser (user-in-the-loop)** on `:8601`, run `mt5import-abc1043ef513`:
  1. Toggle SAR/EMA/SuperTrend → candles STAY visible, overlays sit ON the candles.
  2. Select a signal → 1 entry + 3 dashed connectors to 3 exits, bright; others dim.
  3. Hover entry/exit → popup with ficha, exit_reason, px_in/px_out, P&L, duration.
  4. After lake extension: an early (Jan/Feb) signal also shows candles.
  Capture the symptom before/after for defect B specifically.
