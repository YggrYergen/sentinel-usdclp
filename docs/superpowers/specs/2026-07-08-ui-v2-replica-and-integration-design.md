# SENTINEL UI Rework — v2 Replica (left) + Full-Capability Integration (right)

**Date:** 2026-07-08
**Status:** Design approved — ready for implementation planning
**Implementer target:** Sonnet 5 (high)
**Depends on:** P1 core (`sentinel_engine/`), P3 service (`sentinel_engine/service/app.py`), P4 opt (`levers.py`, `study.py`, `run_fleet.py`), P2 `feed_historical.py`. P5 (chat), P6 (regime), Part F (calendar/registry) surfaces are **gated** — the UI ships and degrades gracefully when they are absent.

---

## 1. Goal & governing invariant

Rebuild the SENTINEL web UI so that:

1. The **left third** is a pixel-faithful replica of the Streamlit **v2** dashboard (`sentinel/dashboard_v2.py` + `sentinel/instrument_panel.py` in the baseline worktree `D:/FOREX_baseline_2026-06-11`), for **three** instruments stacked and independently scrollable: USDCLP, NQ100, XAUUSD.
2. The **right two-thirds** is a modern / futuristic / minimalist / lightweight workspace exposing the **new** features (Chat, Lab, Regime, News, Study), switched by a **vertical navbar** that sits as the divider column between the two halves.
3. **Governing invariant — Capability Coverage:** every capability the engine and the rest of the suite expose MUST be visible and interactive in this UI. Nothing built stays unreachable. Section 8 is the coverage matrix; any capability without a UI home is a spec defect to fix before dispatch.

**Consistency invariant (inherited from P3):** displayed state is a pure function of the snapshot stream. The frontend patches DOM text nodes from each snapshot; it never recomputes scores. Cross-instance divergence reduces to genuine feed differences, which are **surfaced** via data-source + staleness badges, never hidden.

**Non-negotiables:** vanilla JS, no build step, no CDN, no framework; vendored assets only (uPlot already under `web/vendor/uplot`). Runs on Win10 + Win11. Must not be slower than the current thin frontend.

---

## 2. Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│ TOP BAR: ⚡SENTINEL  ·  cfg#a1b2c3  ·  ●REAL-TIME / staleness  ·  ⏳CPI 12:41 │
├──────────────────────────────┬───┬───────────────────────────────────────────┤
│ LEFT 1/3  (scrollable)       │ N │ RIGHT 2/3  (active section)               │
│  ┌ USDCLP ─ v2 stack ──────┐ │ A │  Chat (default) | Lab | Regime | News |   │
│  ├ NQ100  ─ v2 stack ──────┤ │ V │  Study                                     │
│  └ XAUUSD ─ v2 stack ──────┘ │ ↕ │                                            │
└──────────────────────────────┴───┴───────────────────────────────────────────┘
```

- **Vertical navbar** (~48–56px): icon buttons; the active one gets the cyan accent. It is BOTH the section switcher for the right pane AND the visual divider between halves (per coordinator correction 2026-07-08).
- **Left column** scrolls independently; all three asset stacks always rendered at full v2 fidelity.
- **Top bar** is thin, non-intrusive; carries config-hash chip, data-source/staleness badge, and the news countdown strip (amber <30 min, red <5 min).

---

## 3. Left-side v2 replica — component inventory (source of truth)

Each instrument stack reproduces, in order, the v2 `render_panel` layout. Every widget maps to a field already in `Snapshot.to_dict()` (§7). Fidelity target: same palette, same tooltip content/behavior, same numbers.

Per asset, left sub-column (`0.40` width):
1. **Fused-Signal cards (TÉCNICO)** — 4 cells (5s/30s/1m/5m) — direction from TF voting, confidence% from TF score + client-side price derivatives, disagreement dot, acceleration icon. Source: `technical.tf_scores[tf].{score,direction}` + client tick buffer.
2. **Momentum bar** — velocity/accel text + fill bar. Source: client tick buffer.
3. **Macro-derivative cards (MACRO)** — 4 cells, base = macro score, boosted by macro-score velocity/accel buffered client-side. Source: `components._macro.score` over time.
4. **Triple-Signal + Confluence** — Técnico / Fusión / Macro mini-cards + confluence slider + risk mode. Source: `components.technical`, `components._macro`, fusion (`MacroScorer.calculate_fusion`, computed client-side from the two scores/dirs to match v2 exactly).

Per asset, right sub-column (`0.60` width):
5. **TF cards M1/M2/M5/M15** — score, emoji, action, RSI, OB/OS; tooltip has the full indicator slider set (EMA 30% / RSI 20% / MACD 25% / BB 15% / PA 10%) with per-indicator scores + messages. Source: `technical.tf_scores[tf].{score,direction,signals,details}`.
6. **Macro-Votes table** — per-asset rows (return_bps, LONG/SHORT vote, ✅/⚠️/🔴 corr status, HOY% rolling M1 corr) + Macro footer. Source: `components._macro.votes`, `components.correlation.details.correlations`, `expected_correlations` (from `/config`), HOY computed client-side from M1 closes.
7. **S/R levels** — R3..R1 / live price / S1..S3 with % distance + tooltips. Source: `levels.combined.{above,below}`, live price from snapshot/tick.
8. **Alerts / divergences** — from `alerts`, `divergences`.

**Reusable panel component:** ONE parameterized JS component `renderAssetPanel(el, snapshot, cfg)` renders any instrument (kills the v2 duplication). The **same** component renders the Lab replay stage (replay snapshots are indistinguishable from live).

---

## 4. Right-side sections

### 4.1 Chat (default)
- **Full live context, per asset, per timeframe.** Context = the complete `render_ai_context` payload for **all three instruments** (every TF M1/M2/M5/M15 with EMA/RSI/MACD/BB/PA sub-scores + signals, macro votes/consensus/confidence, levels, divergences, alerts, derivatives, regime, config-hash, positions, calendar, and score trajectory). The chat must "see live all the different timeframes per asset — the whole stuff."
- Header controls: model + effort selectors (from `models.yaml`), web-search toggle, extended-thinking toggle. **Web-search vs thinking mutual exclusivity** enforced in ONE request-builder function (toggling one disables the other).
- Streaming replies (SSE or WS). Auto-per-trade chat toggle (PositionWatcher-seeded brief) shown when P5 present; gated otherwise.
- Endpoint: `POST /chat` (extended for streaming + `{model,effort,web_search,thinking}`); `GET /models`. Gated: without a key, mock-answers offline (existing behavior).

### 4.2 Lab (elevated — the primary new workspace)
A minimal-futuristic control surface to manage levers, switch/save/compare/branch configs, and run replay + walk-forward + fast-walk-forward. Three zones in a 3-column grid (collapses to stacked panels under a width threshold).

**Zone A — Lever console (left rail):**
- G1–G7 groups from `LEVER_GROUPS` (`sentinel_engine/opt/levers.py`) as collapsible sections; each `ParamSpec` = labeled slider + numeric field clamped to `lo/hi`, with the production value as a ghost tick.
- Moving any lever recomputes the **variant config hash** live via `apply_overrides(cfg, params)`; production hash + variant hash shown as monospace chips.
- Instrument selector scopes the lever set.
- Endpoint: `GET /levers?instrument=` → serialized groups (group, param, lo, hi, production_value).

**Zone B — Replay stage (center):**
- Reuses `renderAssetPanel` unmodified on the replay snapshot stream.
- Transport: date/time picker, cursor slider, play/pause, speed 1×–60×, step ±1. Spread: recorded / model / custom.
- Active variant (Zone A) drives `ReplaySession = Engine(variant_cfg, HistoricalFeed(lake))`. Seek uses engine-state checkpoints (every 30 min replayed) for sub-second seeks.
- Endpoints: `WS /replay`, `POST /replay/control` (cursor/play/speed/spread/variant). Gated on P2 lake presence.

**Zone C — Variant manager (right rail):**
- **Save** current lever set as a named variant → registry (config sha256 = ID).
- **Compare** 2+ variants → changed-only param diff (before/after) + study metrics (PF, DSR, per-fold, per-regime).
- **Branch** any variant into a new editable set; lineage parent-hash → child-hash rendered as git-commit-style chips (experiments form a tree).
- **Run study** (`run_study`, anchored walk-forward) on the active variant → progress + `StudyResult` proposed diff + verdict + DSR.
- **Run fleet** (`run_fleet`, K studies at once) = **fast walk-forward** — compact fleet board with per-study live status → leaderboard.
- Endpoints: `POST /variant`, `GET /variants`, `POST /variant/branch`, `GET /variant/diff?a=&b=`, `POST /study`, `POST /fleet`, `GET /study/{id}`. Persistence = existing SQLite/Parquet registry (`registry.py`). Gated on P4.

**Lab aesthetic:** near-black `#0a0d12`; hairline `1px` borders `#1e2330`; single cyan accent `#4cc9f0` for active/interactive; monospace (`ui-monospace`) for all numerics + hashes; thin slider tracks with a glowing thumb on the active lever; motion ≤150ms opacity/transform only; no layout-shifting animation.

### 4.3 Regime
- Today's regime label per asset (trend / vol / event / stress) + history strip. Source: `snapshot.regime` (added field, §7). Gated on P6; shows "—" until then.

### 4.4 News
- Calendar strip + expanded event table with countdowns; drives the top-bar countdown and mirrors the engine `NEWS_BUFFER` flag. Endpoint: `GET /calendar?within=`. Gated.

### 4.5 Study
- Latest study report per asset: leaderboard, per-fold stability, per-regime heatmap, winner-vs-production param diff, holdout verdict, DSR, reproduction command. Endpoint: `GET /study/latest?instrument=`. Gated on P4; reuses Zone C metric renderers.

---

## 5. Aesthetic system

- **Left panels** keep v2's exact dark palette for fidelity: bg `#0e1117`; card `#151820`/`#1a1d23`; semantics green `#52b788`, red `#ef476f`, amber `#ffd166`, cyan `#4cc9f0`; existing tooltip styling.
- **Chrome + right pane** get the refined futuristic layer: base `#0a0d12`, hairline borders `#1e2330`, one cyan accent, `system-ui` + one monospace for numerics.
- **Motion:** opacity/transform transitions ≤150ms; WS-diff DOM patching (never full re-render); no animation that shifts layout.
- **Assets:** vendored only. A tiny (~30-line) reactive helper for text-node binding; no framework.

---

## 6. Backend endpoint surface

Existing (P3): `GET /snapshot`, `GET /config`, `WS /stream`, `POST /chat`.

Additive (this rework designs the contracts; implementation of gated ones may land with their phase):
- `GET /snapshot` **extended** with `data_source`, `stale_seconds`, and (when P6) `regime`.
- `GET /levers?instrument=` — serialized `LEVER_GROUPS`.
- `WS /replay`, `POST /replay/control`.
- `POST /variant`, `GET /variants`, `POST /variant/branch`, `GET /variant/diff`.
- `POST /study`, `POST /fleet`, `GET /study/{id}`, `GET /study/latest`.
- `GET /calendar?within=`.
- `GET /models`; `POST /chat` extended (stream + model/effort/search/thinking).

**Gating contract:** the frontend probes each optional endpoint; a 404/501 renders that surface in a labeled "not yet available" state and never blocks the rest of the UI.

---

## 7. Data contract — `Snapshot.to_dict()` field map

Fields present today (`sentinel_engine/engine.py`):
`ts, symbol, seq, config_hash, composite_score, direction, signal, blocked, block_reason, components{technical{score,weight,direction,details{tf_scores{M1..M15{score,direction,signals{rsi,ema_9,ema_21,ema_50,macd_histogram,bb_pct,...},details{ema,rsi,macd,bb,pa{score}}}}}}, correlation{score,weight,direction,details{correlations}}, _macro{score,direction,consensus_raw,consensus_score,votes{asset{return_bps,weighted_vote,confidence,warmup,...}},confidence_avg,total_assets_tracked,assets_warmed_up}}, levels{combined{above[],below[]},current_price,position}, divergences[], alerts[], technical{...}, macro{...}, ai_context`.

**Fields to ADD (additive, do not alter existing scoring output):**
- `data_source: str` (e.g. "mt5" | "yahoo"), `stale_seconds: number` — per Fable §1.2 badges.
- `regime: {trend,vol,event,stress} | null` — P6; null until then.

Derivatives (velocity/accel/momentum) are **client-side** from the WS tick buffer (matches v2, which buffered client-side); no snapshot change.

---

## 8. Capability Coverage Matrix (the governing invariant, made testable)

| Capability (engine / suite) | UI surface | Endpoint | Status |
|---|---|---|---|
| composite score / direction / signal | Left triple-signal + top | `/snapshot`,`/stream` | available |
| per-TF scores + indicator breakdown (M1/M2/M5/M15) | Left TF cards + Chat context | `/snapshot` | available |
| macro votes / consensus / confidence / warmup | Left macro-votes + Chat | `/snapshot` | available |
| correlations + HOY | Left macro-votes status | `/snapshot`,`/config` | available |
| levels S/R + position | Left levels | `/snapshot` | available |
| alerts / divergences | Left alerts + Chat | `/snapshot` | available |
| price derivatives (vel/accel) | Left fused/momentum cards | client tick buffer | available |
| config hash + full config | top chip + Lab | `/config` | available |
| data-source / staleness | badges | `/snapshot`(ext) | to-add |
| AI context (full, all assets/TFs) | Chat | `/chat`,`/models` | gated P5 |
| lever groups G1–G7 | Lab Zone A | `/levers` | gated P4 |
| apply_overrides → variant hash | Lab Zone A live hash | client + `/levers` | gated P4 |
| HistoricalFeed replay | Lab Zone B stage | `/replay`,`/replay/control` | gated P2 |
| run_study (walk-forward) | Lab Zone C + Study | `/study` | gated P4 |
| run_fleet (fast walk-forward) | Lab Zone C fleet board | `/fleet` | gated P4 |
| variant save/compare/branch + registry | Lab Zone C | `/variant*` | gated P4 |
| study report (folds/regime/DSR/diff) | Study section | `/study/latest` | gated P4 |
| regime label | Regime section + badge | `/snapshot`(ext) | gated P6 |
| calendar / news buffer | News + top strip | `/calendar` | gated P6 |
| MT5 positions (read-only) | Chat context / auto-brief | `/chat` | gated P5 |

Acceptance for the invariant: every row has a UI surface. Gated rows ship as labeled placeholders that light up when their backend arrives.

---

## 9. Files

- `web/index.html` — top bar, left column, vertical navbar, right sections.
- `web/app.js` — WS client, `renderAssetPanel`, section router, tick buffer + derivatives, gating probes.
- `web/lab.js` — lever console, replay transport, variant manager, study/fleet boards.
- `web/chat.js` — chat UI, model/effort/search/thinking controls + mutual-exclusivity.
- `web/style.css` — dark v2 palette (left) + futuristic layer (chrome/right/Lab).
- `web/vendor/uplot/*` — existing, unchanged.
- `sentinel_engine/service/app.py` — extend snapshot fields (data_source/staleness), add gated endpoint stubs where owned by this rework.

## 10. Acceptance gates

1. **Left parity:** side-by-side visual + numeric parity vs baseline v2 for all three instruments (same scores, same tooltips, same palette).
2. **Coverage:** every §8 row has a rendered surface (available = live; gated = labeled placeholder). No capability unreachable.
3. **Consistency:** two browser tabs on the same instrument show identical snapshots for a given `seq`.
4. **No-CDN / no-build:** loads fully offline from vendored assets; uPlot-missing degrades to table view.
5. **Performance:** not slower than the current thin frontend on target HW (4–6 GB RAM, 4 threads).
6. **Gating:** every optional endpoint absent → labeled placeholder, never a blocked UI.
7. Win10 + Win11.
