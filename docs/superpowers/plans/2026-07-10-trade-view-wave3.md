# Trade View — Wave-3 (usability + fidelity) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development to implement task-by-task. Steps use `- [ ]` checkboxes. Implement EXACTLY as written — do not re-analyze or re-design; every decision is already made here.

**Goal:** Make the SENTINEL REVIEW ("Trade View") + RUNS sections actually usable for traders: remember the open tab on refresh, focus RUNS on the one ready run, and fix the Trade-View chart (layout, live search, native-TF default, TF-switching without breakage, selection glow, pointer tooltip) with MT5-identical position fidelity across every timeframe.

**Architecture:** Pure frontend (top-level `web/`, classic scripts hanging off `window.SENTINEL`) plus two small backend touches (set `run.tf` at ingest; a read-only source-audit script). The chart is TradingView lightweight-charts v4.2.0 wrapped by `web/lib/chart.js`. All trade event times are snapped to the timeframe's bar boundary so markers/connectors/tooltips align to candles on ANY tf.

**Tech Stack:** Vanilla JS (no framework, no build), lightweight-charts v4.2.0 (vendored), FastAPI (`sentinel_engine/service/app.py`), SQLite registry (`sentinel_engine/research/registry2.py`), pytest source-assertion frontend tests.

## Global Constraints

- Windows 10 AND 11: `pathlib` only, utf-8 explicit, no OS-version APIs. No new runtime deps; no CDN (vendor stays local).
- Real broker accounts READ-ONLY — never place orders. The source-audit script only READS.
- Parity gate stays green: `python -m pytest tests/golden/test_parity.py`. Determinism preserved.
- Test gate for ALL tasks (fast ~32s — NEVER run the full suite; `tests/opt` is an unrelated ~30-min P4 track that gets killed): `PYTHONPATH=/d/FOREX python -m pytest -q tests/golden/test_parity.py tests/service tests/research tests/strategies`.
- Frontend served from disk (no restart needed for JS/CSS/HTML). Bump the `?v=` cache-bust in `web/index.html` (currently `20260710d`) once per stage: Stage1→`20260711a`, Stage2→`20260711b`, Stage3→`20260711c`.
- Do NOT commit. Leave the tree dirty; the orchestrator verifies and commits.
- Verification service is `:8601` (`PYTHONPATH=/d/FOREX python scripts/run_service.py --force-historical --port 8601`). Target run `mt5import-abc1043ef513` (XAUUSD, native tf M5).
- FIXED DATA FACTS (use as acceptance oracles — these are MT5's own imported numbers):
  - Signal `sig-20260402_165000-16`: entry `2026-04-02T16:50:00Z` @ **4669.88**; F1 exit `16:55:40Z` @ **4673.68** (+38.0); F2 & F3 exit `2026-04-05T18:00:40Z` @ **4668.63** (−25.5 each).
  - Signal `sig-20260111_200000-0`: entry `2026-01-11T20:00:00Z` @ **4511.96**; F1 @ 4527.37 (+154.10); F2 @ 4539.99; F3 @ 4567.13.
  - Lake coverage now: M5 →2025-02, M2 →2025-12, M15 →2022; **M1 only from 2026-03-25** (Jan–Mar M1 does NOT exist — those trades must be viewed on M5/M2/M15).
  - `/api/runs/{id}/trades` already returns per trade: `signal_id, ficha, side, ts_in, ts_out` (ISO-8601 `...Z`), `px_in, px_out, pnl, exit_reason, sl, tp`.

---

## BACKLOG (register only — DO NOT implement)
- **B8 — Chat-IA para diseñar/implementar/versionar estrategias:** the traders' #1 ask is a chat assistant that designs new strategies and implements them (or modifies/creates new versions of existing ones). This is OUT OF CURRENT SCOPE. Register in `brains/D--FOREX/project/tracker.md` §B backlog and stop. (Relates to §B B3 MT5 adapter + AI compilation and B5 AI multi-role.)

---

## STAGE 1 — State persistence + native-TF default (unblocks everything)

### Task 1.1: Persist & restore the active navbar section + review selection

**Files:**
- Modify: `web/app.js` (nav router ~L511-537; and add a restore call at end of the init function ~L537)
- Test: `tests/service/test_web_layout.py` (source-assertion)

**Interfaces — Produces:** a `localStorage` key `sentinel.ui.section` (string section name) and `sentinel.ui.review` (JSON `{runId, tf, signalId}`); a `window.SENTINEL.restoreSection()` helper.

- [ ] **Step 1 (test, fails):** in `tests/service/test_web_layout.py` add `test_app_js_persists_and_restores_section` asserting the served `web/app.js` source contains `localStorage.setItem("sentinel.ui.section"` and `localStorage.getItem("sentinel.ui.section"` and a `restoreSection`. Run: `PYTHONPATH=/d/FOREX python -m pytest tests/service/test_web_layout.py::test_app_js_persists_and_restores_section -v` → FAIL.
- [ ] **Step 2 (impl):** in `web/app.js` nav-button click handler (after `const name = btn.dataset.section;`), add `try { localStorage.setItem("sentinel.ui.section", name); } catch(e){}`. Then add a function near the router:
  ```js
  function restoreSection() {
    let name = null;
    try { name = localStorage.getItem("sentinel.ui.section"); } catch (e) {}
    const btn = name && document.querySelector(`.nav-btn[data-section="${name}"]`);
    if (btn) btn.click(); // replays the full teardown/render router path
  }
  window.SENTINEL.restoreSection = restoreSection;
  ```
  Call `restoreSection();` at the very end of the init function (after the buttons.forEach wiring, ~L537). Because the review section already honors `appState.selectedRun` on boot, also persist it: in `web/sections/review.js` `loadRunTrades` (after `appState.selectedRun = row.run_id;`), add `try { localStorage.setItem("sentinel.ui.review", JSON.stringify({ runId: row.run_id, tf: appState.tf, signalId: null })); } catch(e){}`, and in review.js `boot()` before the `appState.selectedRun && runsById[...]` check, hydrate: `try { const s = JSON.parse(localStorage.getItem("sentinel.ui.review")||"null"); if (s && s.runId && !appState.selectedRun) { appState.selectedRun = s.runId; if (s.tf) appState.tf = s.tf; } } catch(e){}`.
- [ ] **Step 3:** Run the test → PASS. Bump `web/index.html` `?v=` to `20260711a`.
- [ ] **Step 4 (browser, orchestrator+user):** navigate to REVIEW, pick the run, refresh (F5) → lands back on REVIEW with the same run loaded (not on chat).

### Task 1.2: Set `run.tf` at MT5 import so REVIEW opens on the run's native TF

**Files:**
- Modify: `sentinel_engine/research/ingest_mt5_deals.py` (where the run row is built — search `tf` / `variant` / the run dict) and/or `sentinel_engine/research/registry2.py` (run serialization in `get_run`)
- Modify: `web/sections/review.js` (`loadRunTrades` ~L511 default-tf line) — make the fallback robust
- Test: `tests/research/test_ingest_mt5_deals.py`, `tests/service/test_web_runs.py`

**Interfaces — Produces:** `/api/runs/{id}` returns non-null `tf` (e.g. `"M5"`) for mt5import runs.

- [ ] **Step 1 (test, fails):** in `tests/research/test_ingest_mt5_deals.py` add `test_mt5_import_sets_native_tf` asserting the ingested run's `tf` equals the timeframe parsed from the report/variant (M5 for the sample). Run → FAIL (currently None).
- [ ] **Step 2 (impl):** in the ingester, derive the timeframe: FIRST from the parsed MT5 report settings (the `.htm` "Period"/"Timeframe" field via `mt5_report.py` — check what it exposes), ELSE from the variant name suffix (regex `_(M\d+)_` on `variant_id`, e.g. `EMS_XAU_V1_M5_c2_sar3m3` → `M5`), ELSE `"M5"`. Persist it on the run row (`tf` column). If the run already exists without tf, a serialization-time fallback in `registry2.get_run` may also apply the same variant-name regex so existing rows self-heal.
- [ ] **Step 3:** run `scripts/ingest_mt5_htm.py` is NOT needed if the serialization fallback covers it; otherwise re-ingest is idempotent (same run_id). Verify: `curl -s :8601/api/runs/mt5import-abc1043ef513 | python -c "import sys,json;print(json.load(sys.stdin)['tf'])"` → `M5`.
- [ ] **Step 4 (impl, frontend guard):** `web/sections/review.js` L511 — keep native-tf-first, but if the run's tf has NO bars in the lake for the run's earliest trade, that's fine (user pans); do NOT hardcode M1. Leave logic as `userPickedTf ? (appState.tf||runFull.tf||"M5") : (runFull.tf||appState.tf||"M5")` — change the two `DEFAULT_TF` literals from `M1` to a constant `DEFAULT_TF="M5"` for mt5import (safer default than M1 which lacks early history).
- [ ] **Step 5:** Test → PASS. Gate (Global Constraints) → green.
- [ ] **Step 6 (browser):** open the run → chart opens on **M5** by default; a January trade (`sig-20260111_200000-0`) shows candles + markers.

---

## STAGE 2 — Trade-View chart: TF-switch fidelity + selection glow + pointer tooltip

Wave-2b already added `groupBySignal`, `barTimeOf`/`secPerBar`, per-ficha connector series (`drawFichaConnector`/`connectorSeriesList`), selection dimming in `buildMarkers`, and the signal tooltip (`findSignalAtBarTime`/`signalTooltipHtml`) in `web/lib/chart.js`. This stage makes them work across TF switches and verifies fidelity + the glow/tooltip actually fire on-chart.

### Task 2.1: TF switch must re-anchor to the selected trade and rebuild markers/overlays (no breakage)

**Files:**
- Modify: `web/lib/chart.js` `setTF` (~L595-603) and `web/sections/review.js` TF handler (~L395-404)
- Test: `tests/service/test_web_trade_grouping.py`

**Root cause (already diagnosed):** `chart.js::setTF` calls `loadInitial()` which loads the TAIL (`max_points:3000`, recent bars) of the new TF — NOT the selected trade's window. Markers/connectors are NOT rebuilt for the new bar times until `selectTrade` runs, and the tail window may be months away from the trade → "breaks absolutely".

**Interfaces — Consumes:** `selectedTradeId`/`selectedSignalId`, `barTimeOf`. **Produces:** `setTF` that, when a trade is selected, reloads THAT trade's window on the new TF and rebuilds markers/connectors.

- [ ] **Step 1 (test, fails):** in `tests/service/test_web_trade_grouping.py` add `test_settf_reanchors_to_selected_trade` asserting `web/lib/chart.js` `setTF` source calls `selectTrade` (or `setWindow` with the selected trade) rather than only `loadInitial`, and that `buildMarkers()`+`redrawConnectors()` run after a tf change. Run → FAIL.
- [ ] **Step 2 (impl, chart.js):** change `setTF(newTf)` so that after `tf = newTf;`: if a trade is currently selected (`selectedTradeId`), re-run the selection path for the new tf — capture the selected trade object, call `await loadInitial()` (keeps a valid fallback), then `if (selectedTradeId) { const t = allTrades.find(x=>x.trade.trade_id===selectedTradeId); if (t) selectTrade(t.trade); }` (selectTrade already calls setWindow → loads the trade window on the new tf, then buildMarkers/redrawConnectors). If no selection, keep `loadInitial()`. Ensure `buildMarkers()` and `redrawConnectors()` are invoked after bars load in BOTH paths.
- [ ] **Step 3 (impl, review.js):** the TF handler (L395) already does `chartInst.setTF(tf).then(()=>{ if(anchorTrade) chartInst.selectTrade(anchorTrade); refreshIndicators(); })`. Keep it, but guard `refreshIndicators` to run only AFTER `windowFrom/windowTo` are set (they are, post-selectTrade). No change if Step 2 makes setTF self-anchor; remove the now-redundant double selectTrade to avoid a double window fetch (call selectTrade in EITHER setTF OR the handler, not both — prefer the handler; make chart.js setTF NOT auto-selphere-select if the caller will; simplest: chart.js setTF re-selects, review.js handler drops its own selectTrade and only calls refreshIndicators()).
- [ ] **Step 4:** test → PASS; gate → green; bump `?v=` to `20260711b`.
- [ ] **Step 5 (browser, FIDELITY — orchestrator+user):** open the run (M5), select signal `sig-20260402_165000-16`. Confirm entry marker on the **16:50** bar @ ~4669.88, F1 exit on **16:55** bar @ 4673.68. Switch M5→M15→M2→M5: candles render each time, markers stay ON their bars at the same prices, no gaps, no wavy lines. Repeat for the January signal on M5. This is the fidelity acceptance: positions graph at the correct time/price identical to the imported MT5 numbers, on every TF.

### Task 2.2: Selection glow on the chart (entry + exits + connectors) and list row

**Files:**
- Modify: `web/lib/chart.js` (`buildMarkers` selected sizing ~L488-516; connector brightness in `redrawConnectors`/`drawFichaConnector` ~L563-635) and `web/style.css`
- Test: `tests/service/test_web_trade_grouping.py`

**Note:** dimming of non-selected + brighten-selected already exists (Wave-2b fix). The user reports "no pasa nada" because they tested on M1 (no candles). This task makes the glow unmistakable and verifies it fires.

- [ ] **Step 1 (test, fails):** add `test_selected_markers_use_glow` asserting `buildMarkers` sizes the selected signal's markers larger (size 2 / 1.6) AND non-selected use a dimmed rgba (`hexToRgba(colorHex, 0.30)`), and that `drawFichaConnector` for the selected signal uses alpha ≥ 0.9 while non-selected ≤ 0.25. Run → FAIL if any missing.
- [ ] **Step 2 (impl):** verify/keep the Wave-2b logic; ADD a visible glow: give the selected signal's markers a distinct bright color (full `colorHex`) plus size 2, and set the selected connectors `lineWidth: 3` (from 2) for a clear glow vs the dim dashed 1px others. In `web/style.css` add a `.review-row-selected` rule (bright left-border + subtle background) if not present, and ensure it applies to the signal header row AND its 3 ficha sub-rows (the row key prefix `<signal_id>::` — see `highlightRow` in review.js).
- [ ] **Step 3:** test → PASS; gate → green.
- [ ] **Step 4 (browser):** click a signal (list) and click its entry/exit/connector (chart) — the whole signal (entry + 3 exits + 3 connectors) glows bright, everything else dims, and the list header+3 fichas highlight. Confirm clicking the CONNECTOR or an EXIT marker also selects (not just the entry).

### Task 2.3: Pointer tooltip card on hover/click of a position

**Files:**
- Modify: `web/lib/chart.js` crosshair handler (~L349-383) + `findSignalAtBarTime` (~L309) + `signalTooltipHtml` (~L322); `web/style.css` tooltip card styles
- Test: `tests/service/test_web_trade_grouping.py`

**Note:** `signalTooltipHtml` + `findSignalAtBarTime` exist (Wave-2b). After Stage-1 default-TF + Task 2.1 the markers land on bars, so `findSignalAtBarTime` matches. This task guarantees the card shows entry/exit TIMES and NET per ficha and follows the pointer.

- [ ] **Step 1 (test, fails):** add `test_signal_tooltip_has_times_and_net` asserting `signalTooltipHtml` renders, per ficha: `ts_in`/`ts_out` (via `fmt.ts`), `px_in→px_out`, signed `pnl`, and a signal `total`. Run → FAIL if the current version omits entry/exit TIMES (it currently shows duration but confirm both ts). If missing, add `entry`/`exit` timestamps per row.
- [ ] **Step 2 (impl):** ensure `signalTooltipHtml(group)` shows for each ficha: `Fx exit_reason  entryTs→exitTs  px_in→px_out  ±pnl` and a `total` line; the card is positioned at the pointer (`param.point.x/y`, already implemented ~L378-382 — keep). Add `.chart-tooltip-signal-header`, `.chart-tooltip-signal-total`, `.chart-tooltip-pos/neg` CSS if missing (glow border, mono, small).
- [ ] **Step 3:** test → PASS; gate → green; bump `?v=` to `20260711b` (same stage).
- [ ] **Step 4 (browser):** hover the entry bar and each exit bar of the selected signal → a card appears at the pointer with the 3 fichas' exit_reason, entry/exit times, px_in→px_out, per-ficha net, and total. Values match the FIXED DATA FACTS.

---

## STAGE 3 — Trade-View layout + live search + RUNS focused on the one ready run

### Task 3.1: Trade-View left column — runs-list box fills the space (kill the gap)

**Files:**
- Modify: `web/style.css` (`.review-run-selector` L703-708, `.review-run-groups` L718-724, `.review-selector-host` L702, `.review-tradelist-host` L893)
- Test: `tests/service/test_web_layout.py`

- [ ] **Step 1 (test, fails):** add `test_review_run_groups_flex_fills` asserting `.review-run-groups` no longer hard-caps at `max-height: 240px` and `.review-selector-host` participates in flex growth. Run → FAIL.
- [ ] **Step 2 (impl):** change `.review-selector-host` to `{ flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; }`; `.review-run-selector` remove `max-height: 40%` → `{ display:flex; flex-direction:column; gap:var(--sp-2); min-height:0; flex:1 1 auto; }`; `.review-run-groups` change `max-height:240px` → `{ overflow-y:auto; flex:1 1 auto; min-height:80px; ... }`. Keep `.review-tradelist-host` with its own `flex` share (give it `flex: 1 1 auto; min-height:0; overflow-y:auto` if not already) so the runs-groups bottom nearly meets the tradelist top with no dead gap.
- [ ] **Step 3:** test → PASS; gate → green; bump `?v=` to `20260711c`.
- [ ] **Step 4 (browser):** the "runs disponibles" box expands so its bottom border nearly touches the positions-list box; no empty gap.

### Task 3.2: Trade-View run search filters live as you type

**Files:**
- Modify: `web/sections/review.js` `renderRunSelector` (~L125-183; the search `input` listener is at ~L176)
- Test: `tests/service/test_web_review_overlays.py` or `test_web_trade_grouping.py`

- [ ] **Step 1 (test, fails):** add `test_review_search_filters_live` asserting `renderRunSelector` wires an `input` event (not just `change`/`click`) on `.review-run-search` that calls `renderGroups(value)`, and there is NO reliance on a separate search button. Run → verify current state; if the listener exists but the box was collapsed (Task 3.1) the fix is 3.1 — but STILL add the test to lock it.
- [ ] **Step 2 (impl):** confirm the `input` listener exists and `renderGroups(q)` filters by `run_id/variant_id/instrumento/display_name` (it does). Add a small debounce-free immediate filter is fine. If Task 3.1 already made results visible, this task may be test-only + a one-line confirm. Ensure the search input has a placeholder and clearing it restores all rows.
- [ ] **Step 3:** test → PASS; gate → green.
- [ ] **Step 4 (browser):** type in the search box → the runs list filters immediately, no button needed; clearing shows all.

### Task 3.3: RUNS section shows ONLY ready runs (+ read-only source audit; safe, reversible)

**Files:**
- Create: `scripts/audit_run_sources.py` (READ-ONLY audit)
- Modify: `web/sections/runs.js` (`fetchRuns`/render — add a "ready-only" filter default) and/or `sentinel_engine/service/app.py` `/api/runs` (add optional `ready=true`)
- Test: `tests/service/test_web_runs.py`, `tests/research/test_registry2.py`

**Decision (safe default):** do NOT hard-delete rows. Instead (a) AUDIT that every non-target run's source exists elsewhere, (b) FILTER the UI to show only "ready" runs (default = the mt5import run(s), i.e. runs whose `engine='mt5-import'` OR a `ready` flag), reversible via a toggle. Provide the audited hard-delete as a SEPARATE script the user runs manually once satisfied.

- [ ] **Step 1 (audit script):** create `scripts/audit_run_sources.py` — for every run in `data/research.db`, print run_id, engine, origin/origin_id, and whether its source is reachable: mt5-import → the `.htm` under `D:/WebDev/TOKATA/mt5/reports` or the recorded `fidelity_ref`; tokata-import → the TOKATA ledger path; sim → regenerable (mark SAFE). READ-ONLY (no writes, no MT5). Output a table + a summary "N runs, all sources present: YES/NO".
- [ ] **Step 2 (test, fails):** add `test_runs_ready_filter` asserting `/api/runs?ready=true` (or the runs.js default) returns only runs with `engine='mt5-import'` (the ready class) for now. Run → FAIL.
- [ ] **Step 3 (impl):** add optional `ready: bool=False` to `/api/runs` in `app.py` → when true, filter to `engine IN ('mt5-import')`. In `web/sections/runs.js`, default the RUNS table fetch to `ready=true` and add a small "mostrar todas" toggle (unchecked by default) that refetches without the filter. This shows only the target run now; flipping the toggle reveals the rest (reversible, non-destructive).
- [ ] **Step 4:** test → PASS; gate → green; bump `?v=` (already `20260711c`).
- [ ] **Step 5 (browser + user decision):** RUNS shows only `mt5import-abc1043ef513`. Run `python scripts/audit_run_sources.py`; if it reports all sources present, the user may later run an audited hard-delete (separate, not in this plan) — but the UI is already focused without deleting anything.

---

## Self-Review coverage map (plan ↔ user feedback)
- Backlog chat-IA → B8 (registered, not implemented). ✅
- (1) tab remembered on refresh → Task 1.1. ✅
- (Runs) show only the one ready run, safely → Task 3.3 (+ audit script). ✅
- (2.1) runs-list box fills space → Task 3.1. ✅
- (2.2) live search, no button → Task 3.2. ✅
- (2.3) default to run's native TF → Task 1.2. ✅
- (2.4) TF switch renders correctly + fidelity on every TF → Task 2.1 (+ fidelity browser acceptance). ✅
- (2.5) selection glow on chart + list → Task 2.2. ✅
- (2.6) pointer tooltip card with entry/exit times + net → Task 2.3. ✅

## Verification (end-to-end, orchestrator + user on :8601, run mt5import-abc1043ef513)
1. Refresh on REVIEW → stays on REVIEW with the run loaded.
2. Chart opens on M5; Jan and Apr signals both show candles + markers on correct bars/prices.
3. Switch M5↔M15↔M2 → renders cleanly each time; markers stay on bars at MT5-identical prices; no gaps/wavy.
4. Click a signal (chart or list) → whole signal glows, rest dims, list header+3 fichas highlight.
5. Hover entry/exit → pointer card with 3 fichas (exit_reason, entry/exit times, px_in→px_out, net) + total, matching the FIXED DATA FACTS.
6. Left column: runs box fills to nearly touch the positions box; search filters live.
7. RUNS section shows only the ready run; audit script confirms all other sources present.
