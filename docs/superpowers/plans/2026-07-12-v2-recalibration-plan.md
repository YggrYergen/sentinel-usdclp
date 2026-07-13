# SENTINEL V2 Recalibration Implementation Plan (Waves 0–E)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Execution rules (Capa-4, OBLIGATORIAS): `docs/superpowers/specs/2026-07-12-agentic-workflow-rules.md`** — incl. task time budget (≤10 min target / 12 min problem / 20 min grave / 35 min discard), lane ownership, no-commit-by-implementers.

**Goal:** Implement the per-tab UI requirements (2026-07-12 brief) on the ALL-LOCAL v1 architecture: windowed/LOD data plane, unified chart, Positions (HUMANO/ESTRATEGIA/IA/TRAINING), Runs launcher, News, assistant v1, paper engine, AI-trader foundations.

**Architecture:** FastAPI service (routers split) + parquet lake with precomputed TF tiers + one chart component (3 adapters) in vanilla JS + lightweight-charts. LLM configures / code monitors (intent DSL). Design rationale: `docs/superpowers/specs/2026-07-12-v2-ui-recalibration-design.md`.

**Tech Stack:** Python 3.11, FastAPI, pyarrow/parquet, SQLite (registry2), MetaTrader5 pkg (attach-only), lightweight-charts (vendored), SSE, Anthropic API (opus-4-8 gated / sonnet-5 / haiku-4-5).

## Global Constraints (apply to EVERY task)

- Windows 10 AND 11; `pathlib` only; `encoding="utf-8"` explicit on every file open; no OS-version APIs.
- Fast gate (run subset relevant to your files; NEVER full suite): `PYTHONPATH=/d/FOREX python -m pytest -q tests/golden/test_parity.py tests/service tests/research tests/strategies`
- Golden parity (`tests/golden/test_parity.py`) must stay green in every task; scoring outputs byte-identical.
- No new pip/npm dependencies without ORC approval. No CDN; vendored libs only.
- Determinism: lake ONLY from broker history (`copy_rates_range`); forming bar never persisted; manifest content-hash recorded.
- Real accounts READ-ONLY; no `order_send` anywhere except gateway (E4 adds CI import test). MT5 attach-only: check `terminal64.exe` process exists BEFORE `MetaTrader5.initialize()`; never launch terminals.
- Perf budgets: /api/bars ≤5000 points per response (server-enforced); JS heap ≤60MB/chart tab; lists >200 rows virtualized; no pandas whole-file loads in request paths (pyarrow row-group reads, row_group_size=8192, monthly partitions).
- Implementers: only YOUR task's files; no commits; no writes to tracker/brain/memory; TDD (failing test → minimal impl → pass); report format per workflow rules.

---

## Progress Ledger (ORCHESTRATOR ticks; implementers never edit this file)

| Task | Lane | Ready when | Status | Commit |
|---|---|---|---|---|
| W0.1 routers split | A | — | [x] | 3833280+d1e202e |
| W0.2 asset versioning | B | — | [x] | 17aea47 |
| A1 lake TF tiers | C | — | [x] | b776ed0 |
| A2 /api/coverage | A | W0.1, A1 | [x] | 9363f9a |
| A3 /api/bars v2 (LOD+overlays) | A | W0.1, A1 | [x] | b3a3f3f |
| A4 chart data controller | B | A3 contract | [x] | 49128e9 |
| A5a adapters + windowed markers | B | A4 | [x] | 5ea9173 |
| A5b precise intrabar marker + connector re-anchor | B | A5a | [x] | bd43a80 (2 disp, ~6min) |
| A6a TV split-pane + TF dot | B | W0.2 | [x] | 3ba0f14 |
| A6b vlist util + TV lists virtualized | B | A6a | [x] | 1cda6d2 |
| A7 goto-date (Charts+TV) | B | A2, A4 | [x] | d5a2a4a (1 disp, ~2min) |
| A8 models/gate/cost endpoints | A | W0.1 | [x] | 1a6f9e5 |
| A9 chat UI catalog+unlock+meter | B | A8 | [x] | e2f5291 |
| A10 live tail service (tick→last bar) | A | W0.1 | [x] | 32a770a |
| A11 live-tail adapter (Charts) | B | A5a, A10 | [x] | 6462ad3 (1 disp, ~3min) — WAVE A COMPLETE |
| B1a deals watcher core | C | — | [x] | 850860b+ce2c36c |
| B1b position grouping (multi-lote/parciales) | C | B1a | [x] | 5da0947 |
| B2 metrics.py + scorecard endpoint | A | W0.1 | [x] | a4ca93e |
| B3-api positions list endpoint (gap found at B3 dispatch: routers/positions.py is stub, no /api/positions — UI has no data source) | A | B1b, B2 | [x] | e87ff10 (1 disp, ~2min) |
| B1c watcher captures account/symbol meta (leverage, contract_size) — gap found at B3-api: pct=profit/margin has no inputs; B3-api serves pct=null until this lands | C | B1a | [x] | 06606d6 (1 disp, ~1.5min) |
| B3 Positions HUMANO UI | B | A5a, B1b, B2, B3-api | [x] | bb9d155 (B3a) + 704b6f8 (B3b), 2 disp, ~5min |
| B4 ESTRATEGIA two-floor + sesiones label | B | B2 | [x] | 67c4914 (1 disp, ~2.5min) |
| B5 IA selector UI (empty-state) | B | B4 | [x] | 1061c55 (1 disp, ~2min; agregado client-side — endpoint ?origin=ia de B2 nunca existió) |
| B6 jobs queue + SSE | A | W0.1, A2 | [x] | a7de06d (2 disp equiv, 16min — §2 review OK) |
| B7 Runs launcher UI + detail dates | B | B6, A2 | [x] | efd0a92 (1 disp, ~3min) — WAVE B COMPLETE salvo B9 (ORC-3) |
| B8 /api/runs/{id}/equity | A | W0.1 | [x] | f0ebb35 (1 disp, ~4min) |
| B9 Lab tooltips render | B | ORC-3 content | [ ] | |
| REV-1 grouping.py StopIteration guard (wave-A review, CONFIRMED) | C | — | [x] | 0733e97 (1 disp, ~1min) |
| REV-2 web fixes: chart.js TF_SEC +H1/D · vlist-selected CSS · onTF live re-sync (review, CONFIRMED) | B | — | [x] | 8a00adb (1 disp, ~1.5min) |
| REV-4 service fixes wave-B review: SSE job_id (CT-4 enmendado) · equity JSON/ts hardening · pct computado · upsert COALESCE | A | — | [x] | 989e43c (2 disp c/ corte de sesión, ~5min) |
| REV-5 web fixes wave-B review: EventSource teardown · group-card VWAP | B | — | [x] | ac9b7e0 (2 disp c/ corte de sesión, ~4min) |
| REV-3 backlog (review): bars double-read w/ overlays · redraw/mousemove throttling · tuple-bar retirement · max_points≤0 · rangeless 404 · dual live-updaters · [wave-B] vwap con OUTs volume-0 · scorecard N-fetch sin caché · /api/positions full-scan (índice origin/symbol + time-bound antes de live) · fetchCoverage 3ª impl (runs.js) · re-fetch por tab-switch · guard IN-less duplicado router/grouping | — | — | [ ] | backlog, fix pass post-Wave-B |
| C1 news poller + API | A | W0.1 | [ ] | |
| C2 News tab UI | B | C1 | [ ] | |
| C3 dossier builders | A | B2 | [ ] | |
| C4 tool registry + manual loop | A | C3 | [ ] | |
| C5 Analizar wiring | B | C4, B3 | [ ] | |
| C6 mini-eval runner | A | C3 | [ ] | |
| C7 strategy-review chat v2 | A+B | C4, B4 | [ ] | |
| D1 paper engine | C | A10 | [ ] | |
| D2 TRAINING tab + Positions selector | B | D1, B3 | [ ] | |
| D3 coach v1 | A | C3, D1 | [ ] | |
| D4 paper-AI executor | C | D1 | [ ] | |
| E0 🗣️ DISCUSSION GATE (user+ORC) | ORC | — | [ ] | |
| E1 intent DSL + rules engine | C | E0 | [ ] | |
| E2 reviewer service (activators→Opus) | A | E0, E1, C3 | [ ] | |
| E3 monitor subagent runner | A | E2 | [ ] | |
| E4 gateway demo-only + CI import test | C | E1 | [ ] | |
| E5 chat propose_position tool | B | E1, C4 | [ ] | |
| ORC-1 R1–R36 map appendix | ORC | — | [x] | fb93b62 |
| ORC-2 Study frontend-design session | ORC+user | — | [ ] | |
| ORC-3 Lab tooltips content (+user review) | ORC+user | — | [ ] | |
| ORC-4 wave-boundary review+commit batches | ORC | continuous | [ ] | |
| ORC-5 e2e headless browser checklist | ORC | Wave A+B done | [x] | see below |

ORC-5 (2026-07-13, sesión #4): tooling `scripts/dev/e2e_service.py` (service :8611, historical feed,
registry COPY seeded with synthetic deals — real `data/research.db` untouched) + `scripts/dev/cdp_e2e_orc5.js`
(headless Chrome CDP driver). All steps PASS, zero console errors: charts (candles painted, TF switch,
EMA/BB chips, goto-date) · TV/review (run load, native-tf dot, replay ticking, split focus, trade rows;
equity endpoint 200 w/ points) · positions (3 tabs, multi-lot chevron expand, VWAP 3300.66667 verified,
detail panel + chart + replay btn, IA aggregate client-side) · launcher CT-4 happy-path in-browser
(H1 job → done → run link) · chat gate renders. Findings fixed: F1 backtest rejected H1/D tf offered by
launcher (`a9df394`) · F2 UI hang on terminal-before-subscribe SSE race (`bc562e8`). Grouping 90s
multi-lot window confirmed working as spec'd (initial seed 1h apart correctly split into 2 groups).

Concurrency: max 3 in flight, one per lane. Waves C/D/E: ORC expands each task to full TDD steps at wave start (contracts here are already frozen).

---

## Frozen Contracts (changes ONLY via ORC plan-amendment; implementers may not deviate)

### CT-1 `GET /api/coverage?symbol=XAUUSD`
```json
{"symbol":"XAUUSD","tfs":{"M1":{"first":1774396800,"last":1783382400},"M5":{"first":...,"last":...}}}
```
Epoch seconds UTC; TF absent from lake ⇒ key absent. 404 unknown symbol.

### CT-2 `GET /api/bars?symbol&tf&from&to&max_points=5000&overlays=ema8,ema20,sar,supertrend`
```json
{"symbol":"XAUUSD","tf_requested":"M1","served_tf":"M5","clipped":false,
 "bars":[{"t":1774396800,"o":4669.1,"h":4670.2,"l":4668.8,"c":4670.0,"v":123}],
 "overlays":{"ema8":[{"t":1774396800,"v":4669.4}]}}
```
Rules: `from`/`to` epoch-s or ISO (`_parse_flexible_ts`). Bars strictly ascending, unique `t`, CLOSED bars only, no rows for empty buckets. If span at `tf_requested` > max_points ⇒ serve next coarser tier (M1→M2→M5→M15→H1→D), set `served_tf`. Overlays computed SERVER-side with warmup: read 200 extra bars before `from`, compute, slice to window; overlay `t` values ⊆ bars `t` values (test-enforced). Numbers rounded to instrument dp (XAUUSD=2).

### CT-3 `GET /api/strategies/{id}/scorecard`
```json
{"strategy_id":"...","tf":"M5","metrics_contract":"v1","baseline_ref":"run_id|null",
 "floors":{"real":{"trades":12,"net":103.5,"pf":1.8,"wr":0.58,"payoff":1.4,
   "expectancy_r":0.31,"expectancy_r_flag":"ok|no_sl_fallback_ccy",
   "net_per_day":8.6,"trades_per_day":1.0,"maxdd_pct":4.2,"sharpe_d":1.1,
   "window":{"from":...,"to":...},"source":{"runs":[],"sessions":["fwd39"]}},
  "teorico":{...same fields, "source":{"runs":["run_id"]}}}}
```
`teorico` from `baseline_ref` run ONLY (never best-run). Fields null when insufficient data; never invented.

### CT-4 Jobs
`POST /api/jobs/backtest {"variant_id","symbol","tf","from","to","preregistro_id"?:str,"exploratory":bool}` → `{"job_id"}`; 422 if window outside CT-1 coverage. `GET /api/jobs/{id}` → `{"status":"queued|running|done|error","progress":0.0-1.0,"run_id":null|str,"error":null|str}`. `GET /api/jobs/stream` = SSE, events `job_update` with same body **+ `"job_id"` (AMENDED 2026-07-12, wave-B review REV-4: multi-job streams need event identity; without it clients cannot filter and cross-job progress/run_id bleed occurs)**. Worker pool size 1.

### CT-5 News
`GET /api/news?symbol=&impact=&kind=&limit=100` → `{"items":[{"id","ts","source","title","url","symbols":["XAUUSD"],"kind":"news|calendar","impact":"high|medium|low|null"}]}`; `GET /api/news/stream` SSE event `news_item`. id = sha1(canonical url) or sha1(calendar event key).

### CT-6 LLM
`GET /api/llm/models` → `[{"id":"claude-opus-4-8","label":"Opus 4.8","gated":true},{"id":"claude-sonnet-5","label":"Sonnet 5","gated":false,"default":true},{"id":"claude-haiku-4-5","label":"Haiku 4.5","gated":false}]`. `POST /api/llm/unlock {"code"}` → `{"ok":bool}`; code compared server-side vs env `SENTINEL_OPUS_GATE` (default "abc123"); on ok set server session flag. Gated model without unlocked session ⇒ 403. `GET /api/llm/usage` → `{"session_tokens_in","session_tokens_out","est_usd"}`.

### CT-7 Dossier builders (module `sentinel_engine/ai/dossier.py`)
`build_position_dossier(trade_id: str, tfs: list[str] = ["M5"]) -> Dossier` and `build_strategy_dossier(strategy_id: str) -> Dossier` where `Dossier = {"xml": str, "token_estimate": int, "sections": dict[str,int]}`. Format = LITERAL templates §3–§4 of `2026-07-12-llm-timeseries-context-research.md` (markdown tables, fixed dp, `<document><source>…<document_content>` wrappers, stats server-computed, question NOT included — caller appends it last). Budgets: position ≤8K tok, strategy ≤10K + tools.

### CT-8 Intent DSL — frozen at E1 from design spec §4.1 (fields as sketched; `fulfillment ∈ {first_of, two_of}`; states `pending→armed→active→closed|cancelled|expired`).

### CT-9 SSE convention: `text/event-stream`, named events, JSON data, retry 3000, heartbeat comment every 15s.

---

## Ownership Matrix

| Lane | Owns | Notes |
|---|---|---|
| A (service) | `sentinel_engine/service/**` (post W0.1 routers), `sentinel_engine/research/metrics.py`, `scorecard.py`, `sentinel_engine/ai/**`, their tests | `registry2.py` migrations: lane A, one task in flight |
| B (web) | `web/**` + `tests/service/test_web_*` | CHOKE: `web/index.html`, `web/style.css`, `web/app.js`, `web/lib/chart.js` — max ONE in-flight task may declare each |
| C (data/engines) | `sentinel_engine/lake/**`, `sentinel_engine/live/**`, `sentinel_engine/paper/**`, `sentinel_engine/exec/**`, `scripts/**`, their tests | |

---

## Wave 0 (SERIAL — nothing else runs until both done)

### Task W0.1: Split app.py into routers
**Files:** Create `sentinel_engine/service/routers/{__init__,bars,runs,strategies,positions,chat,jobs,news,system}.py`; Modify `sentinel_engine/service/app.py`; Test: existing `tests/service/**` unchanged must pass.
**Interfaces:** Produces `create_app()` unchanged externally; each router = `APIRouter` with current prefixes preserved EXACTLY (no URL changes).
**Steps:** (1) create empty routers + include in app factory; run fast gate (green, proves scaffold inert). (2) Move endpoint groups one router at a time — bars/ticks → `bars.py`; runs/registry → `runs.py`; strategies/variants/graduate → `strategies.py`; positions/forward → `positions.py`; chat/models → `chat.py`; leftovers (health, static, version) → `system.py`. Move code VERBATIM (imports adjusted only). (3) After each move: fast gate. (4) `app.py` ends ≤120 lines (factory + includes + middleware). No behavior change: assert route table equality — add `tests/service/test_router_parity.py`:
```python
def test_route_set_unchanged(client):
    paths = {r.path for r in client.app.routes}
    for p in ["/api/bars","/api/runs","/chat"]:  # extend with full current list at impl time from git show HEAD:app.py
        assert p in paths
```
**Budget:** 2 dispatches if needed (scaffold+2 routers / rest). Gate: fast gate green ×2.

### Task W0.2: Asset versioning (kill hand-bumped `?v=`)
**Files:** Modify `sentinel_engine/service/routers/system.py` (post W0.1 — serial anyway), `web/index.html`; Create `tests/service/test_asset_version.py`.
**Spec:** At startup compute `APP_ASSET_VERSION = sha1 of max(mtime of web/**/*.{js,css}))[:10]`. Service serves `index.html` replacing literal token `__ASSET_V__` in all `src=`/`href=` query strings (`app.js?v=__ASSET_V__` etc.). Replace ALL existing hardcoded `?v=2026…` with the token. Test: GET / contains no `__ASSET_V__` and same version on both assets; touching a file changes version (monkeypatch mtime).
**Budget:** 1 dispatch.

---

## Wave A — Data plane + chart core

### Task A1: Lake TF tiers builder
**Files:** Create `sentinel_engine/lake/tiers.py`, `scripts/build_tiers.py`, `tests/lake/test_tiers.py` (+`tests/lake/__init__.py`).
**Interfaces:** Produces `build_tiers(symbol: str, lake_root: Path) -> TierReport` and per-TF parquet at `data/lake/{SYMBOL}/{TF}/{YYYY-MM}.parquet` + updated `data/lake/manifest.json` entries `{symbol,tf,first,last,rows,content_sha}`.
**Spec:** Source of truth per TF: native file if present (M5 native exists), else derive from finest available native. Resample rules (deterministic): bucket = `t - (t % tf_seconds)`; o=first,h=max,l=min,c=last,v=sum; **skip empty buckets** (no rows emitted); input sorted+dedup by t; drop any bar with `t > now - tf_seconds` (forming-bar guard). Write parquet `row_group_size=8192`, monthly files, stable column order `t,o,h,l,c,v` (int64 epoch-s, float64, int64). `content_sha` = sha1 over concatenated per-file sha1s (stable order).
**Tests:** golden resample fixture (13 M1 bars incl. a 3-bucket gap → expected M5 rows exactly); forming-bar excluded; idempotent (run twice ⇒ identical shas); manifest updated.
**Gate:** `pytest -q tests/lake` + fast gate. **Budget:** 1 dispatch.

### Task A2: Coverage endpoint
**Files:** Modify `sentinel_engine/service/routers/bars.py`; Create `tests/service/test_coverage.py`.
**Spec:** Implement CT-1 reading `data/lake/manifest.json` (cached in-process, invalidated by mtime). 404 unknown symbol. Tests: known symbol shape, unknown 404, manifest reload on mtime change.
**Budget:** 1 dispatch.

### Task A3: /api/bars v2 (windowed + LOD + aligned overlays)
**Files:** Modify `sentinel_engine/service/routers/bars.py`; Create `sentinel_engine/service/bars_source.py`, `tests/service/test_bars_v2.py`.
**Interfaces:** Consumes A1 parquet layout + existing indicator functions (the code behind current `/indicators` — reuse, do not duplicate math). Produces CT-2 exactly.
**Spec:** `read_window(symbol, tf, from_, to_) -> list[Bar]` via pyarrow: prune monthly files by name, `parquet.read_table(path, filters=[("t",">=",from_),("t","<=",to_)], columns=[...])` — no pandas. LOD: `estimate = (to-from)/tf_seconds`; while estimate > max_points: step tf up the ladder; set served_tf. Overlays: fetch `from_ - 200*tf_s` extra, compute with existing catalog functions, slice, round to dp. Keep old `/indicators` endpoint intact (deprecation later).
**Tests:** ascending+unique t; ≤max_points enforced ⇒ served_tf set; overlay t-subset-of-bars invariant; warmup correctness (EMA at window edge equals EMA computed from full series — fixture); epoch and ISO both accepted; payload of 5000-bar response < 1.5MB (`len(resp.content)`).
**Budget:** 2 dispatches (A3a reader+LOD; A3b overlays+tests) if first exceeds 10 min.

### Task A4: Chart data controller (web)
**Files:** Create `web/lib/chartData.js`, `tests/service/test_web_chartdata.py` (serve-and-assert pattern used by existing web tests); Modify `web/lib/chart.js` (wire only).
**Interfaces:** Produces `createBarSource({symbol, tf, api}) → {ensureRange(fromT,toT):Promise, onData(cb), setTf(tf), coverage()}`.
**Spec:** chunked fetch (1500 bars/chunk aligned to chunk grid), in-flight dedupe, LRU cap 60000 bars (evict farthest-from-view chunk), merge strictly ascending (throw on duplicate t — surface as console.error not crash), `served_tf` propagated to a notice callback. chart.js: on `subscribeVisibleLogicalRangeChange` debounce 150ms → `ensureRange(view.from - 300*tf, view.to + 50*tf)`. Existing `loadSeq` token pattern preserved.
**Tests:** unit-style via existing headless harness: chunk math, LRU eviction, no duplicate t after overlapping fetches.
**Budget:** 2 dispatches (source module / wiring).

### Task A5a: Adapters + windowed markers
**Files:** Modify `web/lib/chart.js`; Create `web/lib/adapters.js`, test `tests/service/test_web_adapters.py`.
**Interfaces:** Produces `HistAdapter(chart, barSource)`, `ReplayAdapter(chart, barSource, {fromT,toT,speed,pauseAfterBars})` with `play/pause/seek(t)`; markers API `setSignals(signals)` renders ONLY signals within loaded window (re-filter on range change), preserving existing grouping/connector/halo behavior (`hoveredSignalId`, `findSignalNearConnector` untouched semantics).
**Spec:** Replay steps bars AND overlay points in lockstep from the already-fetched window (no per-step fetch). TF switch: `setTf` → re-fetch window around anchor timestamp (keep center bar time constant), re-anchor markers by `t` (position markers on the bar whose bucket contains signal t).
**Budget:** 2 dispatches.

### Task A5b: Precise intrabar marker + connector re-anchor
**Files:** Modify `web/lib/chart.js` (`web/lib/adapters.js` if cleaner); test `tests/service/test_web_precise_marker.py`.
**Spec:** Custom series-primitive drawing entry/exit ticks at fractional x: `x = barX + barWidth * ((signal_t - bucket_t)/tf_seconds)`, clamped [0,1]. Tooltip shows exact HH:MM:SS. FALLBACK (if primitive API blocks >2 attempts): bar-anchored marker + 1px vertical hairline at fractional x via overlay canvas + exact time in tooltip — this fallback is ACCEPTABLE, decided (design §6 ASSUMPTION). Connectors use same fractional x.
**Budget:** 1-2 dispatches.

### Task A6a: Trade View split-pane + native-TF dot
**Files:** Modify `web/sections/review.js`, `web/style.css` (CHOKE — exclusive), `web/index.html` if container change needed (CHOKE — exclusive).
**Spec:** Left column = CSS grid `grid-template-rows: 1fr 1fr; transition: grid-template-rows .25s ease`. Click a list header/card area toggles `.focused-top`/`.focused-bottom` → `3fr 1fr` / `1fr 3fr`; clicking focused one returns 1fr 1fr. Persist in localStorage key `tv.paneFocus`. Kill `.review-run-groups{max-height:240px}` → flex growth (W3-Stage3.1). TF dot: on selector buttons, when `btn.dataset.tf === run.tf` add class `native-tf` → CSS `::after` 5px dot top-left, accent cian, NO size/layout change to buttons.
**Tests:** extend `tests/service/test_web_layout.py`: focus classes toggle, localStorage persisted, dot present only on native TF.
**Budget:** 1 dispatch.

### Task A6b: Virtualized lists
**Files:** Create `web/lib/vlist.js`; Modify `web/sections/review.js`; test `tests/service/test_web_vlist.py`.
**Spec:** `createVList(container, {itemHeight, render(item)→node, items})` windowed rendering (viewport ±10 rows, absolute-positioned spacer). Apply to TV runs-list and positions-list. Keyboard/scroll intact; selection state survives re-render.
**Budget:** 1 dispatch.

### Task A7: Goto-date control
**Files:** Modify `web/sections/review.js`, `web/app.js` (CHOKE — exclusive) or charts section file; test `tests/service/test_web_goto.py`.
**Spec:** `datetime-local` input + "Ir" button in chart toolbar (Charts + TV). On go: clamp to coverage (CT-1, fetched once per symbol/tf; out-of-range ⇒ clamp + toast "Sin datos antes de {first} en {tf}"), `ensureRange(target−150*tf, target+150*tf)` then `setVisibleRange`.
**Budget:** 1 dispatch.

### Task A8: Models catalog + gate + usage
**Files:** Modify `sentinel_engine/service/routers/chat.py`, `models.yaml`; Create `tests/service/test_llm_gate.py`.
**Spec:** CT-6 exactly. models.yaml gains `gated: true` for opus. Session flag in existing session store (or module-level dict keyed by session cookie — match current chat session mechanism). 403 body `{"error":"gated_model_locked"}`. Usage counters accumulated per session from API responses' usage fields.
**Tests:** locked 403 → unlock wrong code → still 403 → right code → 200; usage accumulates.
**Budget:** 1 dispatch.

### Task A9: Chat UI catalog + unlock + meter
**Files:** Modify `web/sections/` chat section file (identify at impl; exclusive), `web/style.css` if needed (CHOKE).
**Spec:** Model dropdown from CT-6 (default=default flag). Selecting gated → inline passcode prompt → POST unlock → error shake on fail. Usage meter (tokens + est USD) polled after each message. NO passcode string in JS ever.
**Tests:** extend web tests: dropdown options, gated flow (mock 403→unlock→200), meter renders.
**Budget:** 1 dispatch.

### Task A10: Live tail service
**Files:** Modify `sentinel_engine/service/routers/bars.py` or create `sentinel_engine/service/live_tail.py`; test `tests/service/test_live_tail.py`.
**Spec:** Reuse existing WS/tick plumbing (P3): background task per subscribed symbol: on tick, update in-memory forming bar per TF (M1..M15) and broadcast SSE/WS event `bar_tail {"symbol","tf","bar":{t,o,h,l,c,v},"closed":false}`; on bucket rollover broadcast `closed:true` (client then treats as final; lake persistence stays with A1 backfill — forming bars NEVER written to lake). Degrade: if MT5 not attached, endpoint returns 503 `{"live":false}` and UI stays historical.
**Budget:** 2 dispatches.

### Task A11: Live-tail adapter (Charts)
**Files:** Modify `web/lib/adapters.js` + charts section wiring.
**Spec:** `LiveAdapter = HistAdapter + subscribe bar_tail` → `series.update(bar)` throttled to rAF; only when viewport at right edge auto-scroll; disconnect on tab hide (visibilitychange) to save laptop resources.
**Budget:** 1 dispatch.

---

## Wave B — Positions & Runs systems

### Task B1a: Deals watcher core
**Files:** Create `sentinel_engine/live/__init__.py`, `sentinel_engine/live/deals_watcher.py`, `tests/live/test_deals_watcher.py`.
**Interfaces:** Produces `class DealsWatcher(registry, mt5_client, poll_s=5)` with `poll_once() -> WatchReport`; service flag `--watch-deals` starts it.
**Spec:** ATTACH GUARD (mandatory, verbatim behavior): psutil-free check via `subprocess`-less: use `MetaTrader5.terminal_info()` — call `initialize()` ONLY if a prior `terminal_info()` on an existing connection… (MT5 pkg requires initialize first) ⇒ implement as: enumerate processes via `ctypes`/`tasklist` fallback: run guard `any('terminal64.exe' in line for line in os.popen('tasklist /FI "IMAGENAME eq terminal64.exe"'))`; if absent: log + skip cycle, NEVER initialize. Poll `history_deals_get(last_sync - 3600, now)`; map deal→row {ticket(pk), position_id, symbol, side, volume, price, profit, magic, time, entry_type}; attribution: magic in magic_allocation→strategy; 900000-900999→ia; else→human; upsert idempotent by ticket into registry (new table `deals_raw` + view into trades on close). Persist `last_sync` in registry meta.
**Tests:** synthetic mt5 stub client (fixtures list of deal dicts): attribution matrix, idempotency (poll twice ⇒ no dup), attach-guard skip path.
**Budget:** 2 dispatches (guard+poll / attribution+persist).

### Task B1b: Position grouping (multi-lote + parciales)
**Files:** Modify `sentinel_engine/live/deals_watcher.py`; Create `sentinel_engine/live/grouping.py`, tests.
**Spec:** `group_positions(deals) -> list[PositionGroup]`. Position = deals sharing `position_id` (IN + ≥1 OUT; partial closes = multiple OUT → position has fills list, aggregate exit = vwap, pnl=sum). GROUP (multi-lote, patrón 3-fichas): positions sharing symbol+direction+magic with entry times within 90s ⇒ `group_id = f"{magic}-{first_entry_t}"`; group row aggregates (net, lots, first-in, last-out) + children detail. Per-position MAE/MFE: computed later from bars (B2 helper `mae_mfe(bars, position)`) — here store nulls, flag `needs_excursions`.
**Tests:** fixtures: simple in/out; partial close 2 OUTs; 3-lote group ≤90s grouped, >90s not grouped.
**Budget:** 1-2 dispatches.

### Task B2: metrics.py + scorecard
**Files:** Create `sentinel_engine/research/metrics.py`, `sentinel_engine/research/scorecard.py`; Modify `sentinel_engine/service/routers/strategies.py`, `sentinel_engine/research/registry2.py` (migration: `ALTER TABLE strategy ADD COLUMN baseline_ref TEXT` guarded by pragma check); tests `tests/research/test_metrics.py`, `tests/service/test_scorecard.py`.
**Spec:** Pure functions, each with docstring formula: `pf(wins,losses)`, `wr`, `payoff`, `expectancy_r(trades)` (needs sl: r = pnl / (risk_per_unit*volume); if any trade lacks sl ⇒ return (value_ccy, flag="no_sl_fallback_ccy")), `net_per_day` (active days = distinct trade dates), `trades_per_day`, `maxdd_pct` (peak-to-trough on cumulative pnl over start equity or notional base param), `sharpe_d` (daily pnl mean/std*sqrt(252), None if <10 days), `mae_mfe(bars, entry_t, exit_t, side, entry_px)`. Scorecard endpoint per CT-3: real = deals origin=strategy(magic-matched) + forward sessions; teorico = baseline_ref run metrics from registry. Cache 60s in-process.
**Tests:** each formula against hand-computed fixture; endpoint shape; teorico=null when baseline_ref null.
**Budget:** 2 dispatches (metrics / endpoint).

### Task B3: Positions HUMANO UI
**Files:** Modify `web/sections/` positions file (exclusive), `web/index.html` (CHOKE: tooltip fix `title="Positions"`), styles via section-scoped CSS.
**Spec:** Card list (vlist) fields: asset, fecha/hora in→out, entry, exit, PnL, `pct = profit / margin` where `margin = volume*contract_size*open_price/leverage` (leverage+contract_size from account/symbol info captured by watcher), lot, MAE, MFE. Group cards: chevron expands children (per-lote SL/TP/exit). Click card → expanded panel: top = chart (HistAdapter, window entry−30/exit+30 bars, markers entry/exit precise) interactive zoom/pan; bottom = full detail table; buttons bottom-right: **Replay** (ReplayAdapter fromT=entry−4*tf, toT=exit+4*tf, pauseAfterBars=4) & **Analizar** (disabled hasta C5, tooltip "Análisis IA — próximamente").
**Tests:** extend web tests: card fields render from fixture API, group expand, replay invoked with correct window args (spy).
**Budget:** 2-3 dispatches (list/card / expanded+replay).

### Task B4: ESTRATEGIA two-floor + labels
**Files:** Modify positions section file (exclusive after B3 merged).
**Spec:** Strategy cards: two floors — top REAL (bold/nítido) bottom TEÓRICO (dimmed) from CT-3; TF badge; estado activa/pausada/graduada existing buttons kept. Second list header renamed **"Sesiones forward"**; click session → its positions right (existing M2.3 flow, labeled).
**Budget:** 1 dispatch.

### Task B5: IA selector UI
**Files:** positions section file (exclusive slot).
**Spec:** Top: big aggregate card = CT-3-style aggregate for origin=ia (endpoint param `?origin=ia` added in B2 scorecard aggregate mode `GET /api/positions/scorecard?origin=ia` — B2 produces it; if data empty ⇒ estado "Sin posiciones IA aún — se activa con el motor paper (Wave D)"). Bottom: HUMANO list component reused with origin=ia.
**Budget:** 1 dispatch.

### Task B6: Jobs queue
**Files:** Create `sentinel_engine/service/jobs.py`; Modify `sentinel_engine/service/routers/jobs.py`, registry migration `jobs` table (id TEXT pk, kind, params_json, status, progress REAL, run_id, error, created_at, updated_at); tests `tests/service/test_jobs.py`.
**Spec:** CT-4. Worker = single background thread consuming queue; backtest kind calls existing backtest-lite entry (M2.7 path) reporting progress callback → row update + SSE broadcast. 422 window-vs-coverage validation. Job survives restart as `error:"interrupted"` (mark on boot).
**Tests:** happy path with stub runner, 422 no-data window, SSE event emitted (test client).
**Budget:** 2 dispatches.

### Task B7: Runs launcher UI + detail dates
**Files:** Modify `web/sections/` runs file (exclusive).
**Spec:** Panel "Nueva corrida": variant select (existing endpoint), symbol select, TF select, period pickers **bounded by CT-1** (min/max attrs set from coverage; out-of-range impossible), exploratory toggle (default ON, label "Exploratoria (no cuenta para graduación)"), submit → CT-4 POST → progress bar via SSE → on done link to run. Detail pane: add rows "Ventana: {desde} → {hasta}" (from registry fields) + label existing date "Creada". Badges engine/fidelity/origin on list rows (fields exist).
**Budget:** 2 dispatches.

### Task B9: Lab tooltips render
**Files:** Modify `web/sections/` lab file (exclusive); Create `web/lib/tooltips.js` if no shared tooltip util exists.
**Spec:** Every Lab lever/control gains `data-help` attribute populated from `web/help/lab_tooltips.json` (file authored in ORC-3, reviewed by user; keys = control ids). Hover ≥400ms → rich tooltip (title + 2-4 line explanation + "afecta a:" line); keyboard-focus shows too; Esc closes. Missing key ⇒ no tooltip, console.warn (never broken UI). Tests: tooltip renders for known key, absent for missing, dismiss on Esc.
**Budget:** 1 dispatch (content JSON arrives from ORC-3; do not invent copy — placeholder keys get "(pendiente ORC-3)" only if JSON missing at impl time).

### Task B8: Equity endpoint
**Files:** Modify `sentinel_engine/service/routers/runs.py`; test.
**Spec:** `GET /api/runs/{id}/equity` → `{"points":[{"t","v"}]}` from equity artifact if exists else cumulative pnl over trades (sorted by ts_out). 404 unknown run.
**Budget:** 1 dispatch.

---

## Wave C — News + Assistant v1 (EXPANDED 2026-07-13 sesión #4, ORC per §6.5; contracts frozen)

Sequencing (one in flight per lane): lane A serial C1a→C1b→C3a→C3b→C4a→C4b→C7a ·
lane B C2 (after C1b), C5 (after C4b), C7b (after C7a) · lane C C6 (after C3b).
Current reality (verified): `routers/news.py` = empty 6-line stub; `routers/chat.py` has CT-6
endpoints (`/api/llm/models|unlock|usage`) + NON-streaming `POST /chat`; `sentinel_engine/ai/`
does not exist; nav button + `section-news` already in `index.html` (no CHOKE for C2 unless app.js glue needed).

### Task C1a: news core — parse + dedupe + table + GET /api/news
**Files:** Create `sentinel_engine/service/news.py`, `tests/service/test_news_core.py`; Modify `sentinel_engine/service/routers/news.py` (stub → build_router pattern like positions.py), `sentinel_engine/research/registry2.py` (additive `news_items` migration ONLY), `sentinel_engine/service/app.py` (swap `news_router.router` → `news_router.build_router(registry)`).
**Interfaces:** `parse_rss(raw: str, source: str) -> list[NewsItem]` (stdlib `xml.etree`), `parse_ff_calendar(raw: str) -> list[NewsItem]` (json), `dedupe_key(item) -> str` (sha1 canonical url / calendar event key), `is_dup_title(a, b) -> bool` (`difflib.SequenceMatcher(None,a,b).ratio()>0.9`, only inside 48h window), `upsert_items(registry, items)`, `query_items(registry, symbol, impact, kind, limit)`.
**Spec:** CT-5 response shape EXACT. `news_items` table additive migration (PRAGMA-guarded like B1c): `id TEXT PRIMARY KEY, ts INTEGER, source TEXT, title TEXT, url TEXT, symbols_json TEXT, kind TEXT, impact TEXT`. Symbol keyword map hardcoded default dict in news.py (XAUUSD: gold, oro, xau; DXY, VIX refs) — yaml override lands in C1b. No network code in this task (parsers take raw strings).
**Tests (TDD):** fixture RSS xml (2 items, 1 dup-title variant) + fixture ff-calendar json → parsed shapes; dedupe by id and by title-ratio window; endpoint filters symbol/impact/kind/limit over tmp registry; 200 empty `{"items":[]}`.
**Gate:** `python -m pytest tests/service/test_news_core.py tests/service/test_router_parity.py -q`. Budget: 1 dispatch.

### Task C1b: news poller loop + SSE + news.yaml
**Files:** Modify `sentinel_engine/service/news.py`, `sentinel_engine/service/routers/news.py`, `sentinel_engine/service/app.py` (start/stop task in lifespan, same pattern as compute loop); Create `news.yaml` (repo root), `tests/service/test_news_poller.py`.
**Interfaces:** `NewsPoller(registry, config, fetcher=None)` — `fetcher(url, etag, last_modified) -> (status, headers, body)` injectable (stdlib `urllib.request` default, run via `asyncio.to_thread`); 90s cadence; conditional GET honors ETag/Last-Modified (304 ⇒ skip). `GET /api/news/stream` SSE event `news_item` per CT-5/CT-9 (subscribe/broadcast pattern copied from jobs stream, heartbeat 15s, retry 3000).
**Spec:** `news.yaml`: `rss: [forexlive, fxstreet, investing urls]`, `ff_calendar: <faireconomy weekly json url>`, `symbol_keywords:` map (overrides C1a default). utf-8 explicit read, pathlib. Poller never raises out of its loop (log + continue). New items only ⇒ broadcast.
**Tests (TDD):** fake fetcher: first poll inserts+broadcasts, second poll 304 ⇒ no work; malformed feed ⇒ logged, loop alive; SSE endpoint emits `news_item` for a new insert (TestClient stream, same technique as test_jobs SSE); yaml load honors overrides.
**Gate:** `python -m pytest tests/service/test_news_poller.py tests/service/test_news_core.py -q`. Budget: 1 dispatch.

### Task C2: News tab UI
**Files:** Create `web/sections/news.js`, `tests/service/test_web_news.py`; Modify ONLY the include/glue the orchestrator confirms at dispatch (nav button + section already exist in index.html).
**Spec:** vlist (reuse `web/lib/vlist.js`) of CT-5 items; filters symbol/impact/kind (selects, client-side re-fetch `/api/news?...`); freshness label "hace N min" (computed from ts, re-render on a 60s timer); title = `<a target="_blank" rel="noopener">`; SSE `/api/news/stream` appends at top (EventSource with teardown on section switch — REV-5 pattern from runs.js).
**Tests (TDD):** serve-and-assert pattern of test_web_positions.py: source asserts for vlist reuse, target=_blank+rel, EventSource teardown registration, filter param building.
**Gate:** `python -m pytest tests/service/test_web_news.py -q`. Budget: 1 dispatch.

### Task C3a: position dossier builder (CT-7)
**Files:** Create `sentinel_engine/ai/__init__.py`, `sentinel_engine/ai/dossier.py`, `tests/ai/test_dossier_position.py` (+ `tests/ai/__init__.py`, fixture files under `tests/ai/fixtures/`).
**Spec:** `build_position_dossier(trade_id, tfs=["M5"]) -> {"xml","token_estimate","sections"}` per CT-7. Template = LITERAL §3 of `docs/superpowers/specs/2026-07-12-llm-timeseries-context-research.md` (markdown tables, fixed dp, `<document><source>…<document_content>` wrappers, stats server-computed, question NOT included). `token_estimate = ceil(len(chars)/3.5)` (heuristic, documented in docstring). Budget ≤8K tok enforced: trim bar tables (drop oldest rows) until under budget, record trim in `sections`. Data access: registry (trade row) + lake bars via existing `load_tf_frame`/bars_source — read-only.
**Tests (TDD):** golden snapshot: fixture trade + tiny fixture lake → exact expected xml (committed fixture file) compared by hash AND full string (diff on fail); token_estimate formula; budget trim kicks in on an oversized fixture; unknown trade_id raises clean error.
**Gate:** `python -m pytest tests/ai/test_dossier_position.py -q`. Budget: 1 dispatch.

### Task C3b: strategy dossier builder (CT-7)
**Files:** Modify `sentinel_engine/ai/dossier.py`; Create `tests/ai/test_dossier_strategy.py` (+ fixtures).
**Spec:** `build_strategy_dossier(strategy_id) -> Dossier`, LITERAL §4 of the research doc; ≤10K tok + tools note; sources: registry strategy/variant rows, CT-3 scorecard data (call the same internals the scorecard endpoint uses — no HTTP self-calls), recent runs table. Same trim/estimate rules as C3a.
**Tests (TDD):** golden snapshot vs committed fixture xml; budget trim; unknown strategy_id clean error.
**Gate:** `python -m pytest tests/ai/ -q`. Budget: 1 dispatch.

### Task C4a: tool registry (pure, no LLM)
**Files:** Create `sentinel_engine/ai/tools.py`, `tests/ai/test_tools.py`.
**Interfaces:** `TOOLS: list[dict]` (Anthropic tool-schema dicts) + `execute_tool(name, args, ctx) -> str` where `ctx = {"registry","lake_root"}`. Tools: `get_bars(symbol,tf,from,to)` → CT-2-shaped compact result, hard cap: serialized result ≤25K tokens by the chars/3.5 heuristic (truncate + note); `get_trade_detail(trade_id)`; `query_registry(filters)` (whitelisted filter keys → parameterized SQL ONLY); `get_scorecard(strategy_id)` (CT-3 internals reuse).
**Spec:** pure functions, deterministic, read-only; unknown tool/args ⇒ error string result (never raises to caller). No network, no LLM.
**Tests (TDD):** each tool happy path over tmp registry+lake; cap enforcement on get_bars; SQL-injection attempt in query_registry filters is neutralized; unknown tool name → error string.
**Gate:** `python -m pytest tests/ai/test_tools.py -q`. Budget: 1 dispatch.

### Task C4b: manual tool loop + SSE chat streaming + analyze endpoint
**Files:** Create `sentinel_engine/ai/loop.py`, `tests/ai/test_loop.py`; Modify `sentinel_engine/service/routers/chat.py` (add `POST /api/ai/analyze_position` + SSE upgrade), `tests/service/test_chat.py` (additive).
**Interfaces:** `run_tool_loop(client, model, system, messages, tools, ctx, on_text) -> final_text` — while `stop_reason=="tool_use"`: execute via C4a, append `tool_result`, re-call; max 8 iterations (then append "max iterations" note and stop); `on_text(chunk)` streams text deltas. `POST /api/ai/analyze_position {"trade_id"}` → SSE stream (CT-9, events `ai_text`/`ai_done`/`ai_error`): builds C3a dossier, system prompt STABLE-FIRST (fixed system → tools → dossier docs → question LAST, per research §5 caching order), model from session (CT-6 gate respected — gated model w/o unlock ⇒ 403 BEFORE any API call).
**Tests (TDD):** fake Anthropic client scripted with tool_use→end_turn sequences: loop executes tools, respects max-8, streams text; endpoint 403 on gated model; SSE event sequence on happy path; unknown trade_id → `ai_error`.
**Gate:** `python -m pytest tests/ai/test_loop.py tests/service/test_chat.py -q`. Budget: 1 dispatch (if >12min: split endpoint out).

### Task C5: Analizar wiring (web)
**Files:** Modify `web/sections/positions.js`; `tests/service/test_web_positions.py` (additive).
**Spec:** enable the B3b-disabled "Analizar" button → `POST /api/ai/analyze_position {trade_id}` → consume SSE into a text panel inside the expanded card panel (append `ai_text` chunks, close on `ai_done`, show `ai_error`); EventSource/reader teardown on panel close + section switch (REV-5 pattern); button disabled while a stream is active.
**Tests (TDD):** source asserts: endpoint URL, event names, teardown registration, re-entrancy guard.
**Gate:** `python -m pytest tests/service/test_web_positions.py -q`. Budget: 1 dispatch.

### Task C6: mini-eval runner (lane C — `scripts/**`)
**Files:** Create `scripts/llm_format_eval.py`, `tests/scripts/test_llm_format_eval.py` (+ `tests/scripts/__init__.py` if absent).
**Spec:** per research §6: 8 preguntas × 4 formatos × {sonnet, haiku}; formats built from C3 builders + §6 variants; `--dry-run` prints prompts w/o API calls (default when `ANTHROPIC_API_KEY` absent); real run writes `docs/superpowers/specs/2026-07-12-format-eval-results.md` (scores + per-question table). Cost guard: hard cap N calls = 8×4×2, abort if estimate > cap. ORC reviews the report → may flip dossier default via plan amendment (NOT the implementer).
**Tests (TDD):** dry-run builds 64 prompt specs with correct matrix; report writer renders md from canned results; no network in tests.
**Gate:** `python -m pytest tests/scripts/test_llm_format_eval.py -q`. Budget: 1 dispatch. NOTE: real API run is ORC/user-triggered, not part of the task.

### Task C7a: strategy-review endpoint (service)
**Files:** Modify `sentinel_engine/service/routers/chat.py`; `tests/service/test_chat.py` (additive).
**Spec:** `POST /api/ai/review_strategy {"strategy_id"}` → same SSE shape as analyze_position, dossier = C3b strategy dossier + C4a tools available in the loop; CT-6 gate respected.
**Tests (TDD):** fake client; 403 gated; SSE sequence; unknown strategy_id → `ai_error`.
**Gate:** `python -m pytest tests/service/test_chat.py -q`. Budget: 1 dispatch.

### Task C7b: strategy-review panel (web)
**Files:** Modify `web/sections/positions.js` (ESTRATEGIA card button "Revisar con IA" → SSE chat panel, reuse C5's stream-consumer helper); `tests/service/test_web_positions.py` (additive).
**Tests (TDD):** source asserts as C5.
**Gate:** `python -m pytest tests/service/test_web_positions.py -q`. Budget: 1 dispatch.

## Wave D — Paper engine + TRAINING (expand at wave start)

- **D1** `sentinel_engine/paper/engine.py`: subscribes live tail (A10) or M1-close fallback; market fills at current bid/ask ± slippage cfg (default 0.5 pip); virtual balance per profile (registry tables `paper_accounts`, `paper_positions` origin `practice|ia`); SL/TP static eval per tick; close writes position row (reuses B1b shapes).
- **D2** TRAINING tab: order ticket (symbol/side/lot/SL/TP), open-positions panel (live pnl via tail), close button; Positions tab gains 4th selector `TRAINING` = HUMANO component with origin=practice.
- **D3** coach v1: on paper position open/close → position dossier → sonnet commentary streamed to Training chat panel; throttle 1 comment/position/event.
- **D4** paper-AI executor: flag-gated listener on semáforo composite (existing signal panel state) → paper positions origin=ia with provenance (activator="semaforo_v1").

## Wave E — AI-trader (E0 GATE FIRST; expand after)

- **E0** 🗣️ user+ORC discussion: freeze activator strategy set + thresholds, Opus invocation budget/frequency, kill-switch UX, reviewer dossier contents, paper-vs-demo rollout criteria. OUTPUT: amendment to spec §4 + expanded E1-E5 tasks.
- **E1** intent DSL (CT-8) + `sentinel_engine/exec/intent_engine.py`: rule evaluators `pip_distance`, `indicator_cross`, `indicator_reversal`, `price_band` entry (tolerance+confirm_bars+expiry); m-of-n fulfillment; state machine + audit rows; evaluated on live tail events; executes v1 → paper engine.
- **E2** reviewer service: activator triggers (proximity % | fire) → dossier → Opus 4.8 `effort:medium` structured verdict `{decision: seconds|veto|modify, sl?, tp?, notes}` (output_config json_schema) → intent.
- **E3** monitor runner: per-active-intent optional Haiku check (single question, watch list from intent.monitor), cadence cfg, result → audit + optional intent cancel proposal (never auto-close without rule).
- **E4** gateway demo-only (design §4.4) + `guard_cuenta.assert_demo()` + CI test: grep-import test asserting `order_send` referenced ONLY in `sentinel_engine/exec/gateway.py`.
- **E5** chat tool `propose_position(intent_draft)` → draft card in chat UI → user confirm button → engine (paper v1).

## Deferred slots (not in these waves)
- Regime tab (post signal-history S2/S3 — placeholder honesto ya presente).
- Study tab UI (post ORC-2 design session).
- Deep P1 cutover review; P2 real exports; P4 real study (unchanged carryover).

## Appendix — R1–R36 map (ORC-1, 2026-07-12)

Source reqs: `D:\WebDev\TOKATA\docs\REQUISITOS_WEBAPP_ANALISIS_ESTRATEGIAS.md`. Strict count (one dominant state/R): **hecho 17 · planificado(task) 15 · backlog 2 · gap 2**.

| R | Requisito (resumen) | Estado | Ref |
|---|---|---|---|
| R1 | Gráfico velas profesional | hecho | M1.3 `a3feafd`; recalibrado A3-A5 |
| R2 | Cambio de TF en mismo gráfico | planificado | A3 (LOD ladder), A6a (TF dot) |
| R3 | Paneo histórico | planificado | A4 (ensureRange chunked), A7 |
| R4 | Zoom in/out | hecho | M1.3 `a3feafd` (librería nativa) |
| R5 | Hover por elemento (OHLC/indic/marker) | planificado | Base `e0d3c2b`; A5b marcador intrabar+HH:MM:SS |
| R6 | Indicadores propios por estrategia | planificado | EMA/SAR/SuperTrend `e0d3c2b`; A3 overlays server-side. **Ver GAP R6b** |
| R7 | Todas las estrategias en un lugar | hecho | M2.1 `981d575`, M2.4 `88c50cf` |
| R8 | Crear estrategias/variaciones desde UI | hecho | M2.7 `8435634` |
| R9 | Ver parámetros | hecho | M2.4/M2.7 |
| R10 | Modificar parámetros | hecho | M2.7 `8435634` |
| R11 | Informes de desempeño | planificado | RUNS `981d575`; B2 metrics+scorecard (CT-3) |
| R12 | Comparar estrategias/variantes | planificado | RUNS compare; B8 equity overlay |
| R13 | Recorrer cada trade sobre gráfico | hecho | M2.2 `c449526`, Trade-View `e0d3c2b` |
| R14 | Backtests personalizados desde UI | planificado | M2.5 `199d88d`; B6 jobs, B7 launcher |
| R15 | Forward walk configurable desde UI | **backlog** | Sin tarea; solo monitoreo de forward en curso (B3/B4) |
| R16 | Monitorear estrategias graduadas en vivo | planificado | M2.3 `2908047`; B3, B4 |
| R17 | Tomar trades por varias vías (manual/paper/estrat/IA) | planificado | D1, D4, E1/E5, B1a/b |
| R18 | Ejecución en vivo solo demo | hecho | CUENTAS.md/guard; E4 formaliza |
| R19 | Ingerir artefactos actuales | hecho | M0.2 `ce750e8`, M0.3 `319a650`, `b4c7fbe` |
| R20 | Importar estrategias afinadas + historial | hecho | M0.2/M0.3, `b4c7fbe` (EMASAR-V1) |
| R21 | Trazabilidad → variante/parámetros | hecho | params_hash/variant_id; CT-3 baseline_ref |
| R22 | Estrategia/variante entidades distintas | hecho | registry2.py + M2.4 |
| R23 | Params efectivos por corrida (params_hash) | hecho | ledger/registry |
| R24 | Parameter sweeps desde UI | **backlog** | Diferido explícitamente a ORC-2 (Study) |
| R25 | Ventana+modelo explícitos por corrida | planificado | registry M0/M2; B7 detail "Ventana:" |
| R26 | Multi-instrumento con escalas correctas | hecho (parcial) | CT-2 dp por instrumento; NQ100 sin datos reales en lake |
| R27 | Motivo de salida por trade | hecho | Trade-View Wave-1 (exit_reason 69/69) |
| R28 | Validez params según instrumento/bróker (stop mínimo) | **gap** | Sin mención de stop_level en plan ni specs |
| R29 | Curvas equity + drawdown superpuestas | planificado | B8 equity; **curva DD sin cobertura (parcial gap)** |
| R30 | Ranking/tabla ordenable+filtrable | hecho | M2.1 `981d575` |
| R31 | Distinguir screening/validación/forward en reportería | planificado | CT-3 real/teorico; B7 badges; CT-4 exploratory |
| R32 | Panel monitoreo forward/live | planificado | M2.3; B1a/b, B3, B4 |
| R33 | Marcar estrategia graduada | hecho | M2.7 `8435634` (criterio formal por confirmar) |
| R34 | Enforcement demo-only en toda ruta viva | planificado | E4 (gateway + CI grep-import test) |
| R35 | Pre-registro (hipótesis antes de correr) + audit | planificado | CT-4 preregistro_id **opcional** — ver riesgo abajo |
| R36 | Evidencia asociada a cada resultado | hecho | ledger report_path; CT-7 dossiers `<source>` |

**GAPS / riesgos para decisión del usuario (no bloquean Waves 0/A/B):**
- **R28 (gap duro):** validación de ejecutabilidad de parámetros vs bróker (distancia mínima de stop). Sin tarea. Candidato a tarea nueva o E-wave (relevante para AI-trader/gateway).
- **R6b (gap):** overlays limitados a EMA/SAR/SuperTrend; AO/AC/Momentum/patrones-vela/ORB/ADX/Choppiness (Sapitos/Pedro) no en catálogo A3. Ampliar catálogo = tarea nueva si esas estrategias se revisan en Trade-View.
- **R29 (parcial):** B8 cubre equity, no curva de drawdown superponible (solo escalar maxdd_pct).
- **R15 / R24 (backlog):** forward-walk y sweeps configurables desde UI — sin task-id; R24 depende de ORC-2.
- **R35 (riesgo de regresión):** `preregistro_id` es opcional en CT-4; el proceso Python actual lo exige. Decidir si B6/B7 deben hacerlo obligatorio para no relajar la disciplina.

Full working notes: `scratchpad/orc1-rmap.md` (session-local).
