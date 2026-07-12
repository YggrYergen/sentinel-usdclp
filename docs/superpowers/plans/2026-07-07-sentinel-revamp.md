# SENTINEL Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Governance:** `docs/superpowers/specs/2026-07-07-sentinel-revamp-workflow-design.md` (model routing, 2-strikes rule, Fable gate, brain protocol). Read it before executing.
> **Technical design source of truth:** `FABLE5_RESPONSE_SENTINEL_REVAMP.md` (sections referenced inline as §n). When a task says "per §2.6", open that section for the exact algorithm.

**Goal:** Turn SENTINEL into a headless-core-driven system with a real backtesting/optimization engine, a lightweight UI, restored AI, and replay/logging — without changing what/how it recommends and without getting slower.

**Architecture:** Extract a deterministic headless compute core (`sentinel_engine/`) producing immutable `Snapshot` objects; every axis (UI, backtesting, AI, replay/logging) is a consumer of that one core. Compute runs in a background process exposing snapshots over a local FastAPI + WebSocket service; a thin static HTML/JS page renders them. Backtesting replays the same core over historical feeds with parameterized config variants, guaranteeing replay==live fidelity by construction.

**Tech Stack:** Python 3.11 (existing embedded launcher), FastAPI + uvicorn, vanilla JS + uPlot, Parquet (pyarrow), SQLite, Optuna, pandas/numpy. Free/OSS only (Anthropic API exempt as a runtime feature).

## Global Constraints

- **OS:** Every deliverable MUST run on **Windows 10 AND Windows 11**. `pathlib` only; no hardcoded path separators; explicit `encoding="utf-8"` on all file I/O; no OS-version-specific APIs; reuse the existing embedded-Python launcher; no WSL-only assumptions; no reliance on a system Python.
- **Target HW:** ~4–6 GB RAM, 4 threads, SSD ~50 GB free, MT5 running alongside. Nothing may make the UI slower than today.
- **Read-only accounts:** Real broker accounts are strictly read-only. No order placement anywhere in this system.
- **Determinism:** The core MUST be deterministic — same feed + same config ⇒ byte-identical snapshot (config-version hash + monotonic sequence number in every snapshot).
- **Parity gate:** No refactor of a computation may change its output vs the captured golden master. Parity tests are the acceptance gate for P0–P1 and any change touching scoring.
- **Tooling:** Free/OSS only; Anthropic API allowed solely as a runtime product feature.
- **Model routing (see governance §3):** Opus 4.8 only on P1 + P4; Sonnet 5 default elsewhere; Haiku only on tasks tagged `[haiku-ok]`; 2-strikes escalation per governance §4.

---

## Phase 0 — Foundations & quick wins  ·  Model: Sonnet 5  ·  Dep: none

**Exit gate:** parity harness green on NASDAQ+Gold+USDCLP; both loggers writing dated files; the two defects fixed and covered by a regression test; AI-context numbers sourced from config; Streamlit stopgap measurably reduces rerun cost. Runs on Win10 + Win11.

**Files:**
- Create: `tests/golden/capture_golden.py`, `tests/golden/test_parity.py`, `tests/golden/fixtures/` (captured snapshots)
- Create: `sentinel/logging/tick_logger.py`, `sentinel/logging/snapshot_logger.py`
- Modify: `sentinel/backtester.py` (defect 1 + 2), `sentinel/ai_chat.py` (defect 3), `sentinel/dashboard*.py` (stopgap)

### Task 0.1: Golden-master capture harness
**Interfaces — Produces:** `capture_golden(instrument, feed_fixture) -> dict` writing a canonical JSON snapshot per instrument to `tests/golden/fixtures/<instrument>.json`.
- [ ] Read `sentinel/sentinel_core.py`, `technical_scorer.py`, `macro_scorer.py`, `correlation_engine.py`, `config.py` to enumerate every scored output field.
- [ ] Write `capture_golden.py`: feed a **fixed recorded input** (a small committed CSV fixture per instrument) through the current scoring path and serialize the full result (composite, per-TF scores, macro, technical, levels) to canonical JSON (sorted keys, fixed float format).
- [ ] Run it once to produce `fixtures/nasdaq.json`, `fixtures/gold.json`, `fixtures/usdclp.json`. Commit fixtures.
- [ ] **Acceptance:** re-running capture produces byte-identical JSON (determinism check).
- [ ] Commit.

### Task 0.2: Parity test
**Interfaces — Consumes:** fixtures from 0.1.
- [ ] Write `test_parity.py`: for each instrument, run the current scoring path over the same fixture and assert the result equals the committed golden JSON (exact for ints/enums; abs tol 1e-9 for floats).
- [ ] Run: `pytest tests/golden/test_parity.py -v` → expect PASS (this is the baseline lock).
- [ ] Commit.

### Task 0.3: Defect 1 — guard the broken CorrelationEngine import (§A.14)
- [ ] In `sentinel/backtester.py`, locate the `replay_scoring` import of the nonexistent `CorrelationEngine` class (currently raises `ImportError`, unguarded).
- [ ] Write a failing test `tests/test_backtester_import.py` that imports `replay_scoring` and asserts it does not raise.
- [ ] Fix: remove/guard the import so the legacy correlation path is excluded from replay scoring (it was never in the composite — confirm against §A.7/§A.14 before deleting).
- [ ] Run test → PASS. Run parity (0.2) → still PASS.
- [ ] Commit.

### Task 0.4: Defect 2 — replay ≠ live fidelity (`normalize_macd`) (§A.14 vs §A.7)
- [ ] Confirm the live scorer uses `normalize_macd=True` and `replay_scoring` uses `False` (read both call sites; cite line numbers in the commit).
- [ ] Write a failing test: replay-scoring a fixture equals live-scoring the same fixture on the MACD-derived fields.
- [ ] Fix: set replay `normalize_macd=True`. Run test → PASS. Run parity → PASS.
- [ ] Commit.

### Task 0.5: Defect 3 — stale AI context numbers (§A.15)
- [ ] In `sentinel/ai_chat.py`, find the hardcoded 75/25 composite and 40/30/20/10 TF weights in the system prompt.
- [ ] Write a failing test asserting the AI-context builder emits the *current* weights (50/50 composite, 35/35/20/10 TF) **read from `config.py`**, not literals.
- [ ] Fix: source the numbers from config at render time. Run test → PASS.
- [ ] Commit.

### Task 0.6: Native tick logger (start collecting NOW)
**Interfaces — Produces:** `TickLogger(symbol, out_dir).on_tick(ts, bid, ask)` appending to `logs/ticks/<symbol>/<YYYY-MM-DD>.parquet`.
- [ ] Write test: feeding N ticks yields a Parquet file with N rows and columns `[ts, bid, ask, spread]`, UTF-8, pathlib paths.
- [ ] Implement `tick_logger.py` (append-batched to keep laptop I/O low). Wire it into the live data path behind a config flag `LOG_TICKS=True`.
- [ ] Run test → PASS. Verify a file appears on a short live run.
- [ ] Commit.

### Task 0.7: Native snapshot logger
**Interfaces — Produces:** `SnapshotLogger(out_dir).log(snapshot_dict)` appending one row per computed snapshot to `logs/snapshots/<symbol>/<YYYY-MM-DD>.parquet`.
- [ ] Write test: logging K snapshots yields K rows with the full scored schema + `config_hash` + `seq`.
- [ ] Implement; wire behind `LOG_SNAPSHOTS=True`. Run test → PASS.
- [ ] Commit.

### Task 0.8: Streamlit stopgap relief
- [ ] Move the per-cycle compute into a background thread; publish the latest result to a thread-safe holder.
- [ ] Convert the heavy render blocks to `st.fragment` partial reruns reading the holder (no full-page rerun per tick).
- [ ] **Acceptance:** parity (0.2) still PASS (no change to *what* is shown); manual check that rerun cost drops (fewer full reruns per second). Runs on Win10 + Win11.
- [ ] Commit. **→ Run `brain close-impl --analyze` then `--apply` when the exit gate is green; `/brain handoff`.**

---

## Phase 1 — Headless core extraction  ·  Model: **Opus 4.8**  ·  Dep: P0.1–0.2

> Opus implementer authors per-task TDD code. This plan locks the file map, the interface contracts, and the acceptance gate. Design detail: Fable §1.4.

**Exit gate:** parity tests (P0.2) pass on all 3 instruments **through the new core** (byte-identical to golden masters); one code path per computation; `config_hash` in every snapshot; `instrument_panel`'s inline macro copy deleted; determinism check green.

**Files:**
- Create: `sentinel_engine/__init__.py`, `config.py` (`InstrumentConfig`), `feed.py` (`Feed` protocol), `macro.py` (parameterized `MacroScorer`), `technical.py`, `engine.py` (`Engine`, `Snapshot`), `ai_context.py`, `schemas.py`
- Create: `sentinel_engine/instruments/{nasdaq,gold,usdclp}.yaml`
- Delete: inline macro reimplementation in `sentinel/instrument_panel.py`

**Interface contracts (locked — implementer matches these exactly):**
- `class InstrumentConfig` — loaded from YAML; fields cover every number currently in `config.py` per instrument (composite weights, TF weights, macro weights, thresholds, ATR/level params). One YAML per instrument generated from current `config.py` values (must reproduce them exactly).
- `class Feed(Protocol)`: `def bars(self, tf: str) -> pd.DataFrame`, `def now(self) -> datetime`, `def positions(self) -> list`. Implementations: `LiveMT5Feed`, `HistoricalFeed(as_of)` (P2).
- `class MacroScorer(cfg: InstrumentConfig)` — parameterized; unifies the USD/CLP-hardwired `sentinel/macro_scorer.py` and the duplicated Gold/NASDAQ inline copy into ONE engine (§A.9/§A.13).
- `@dataclass(frozen=True) class Snapshot` — immutable; fields: `ts`, `symbol`, `seq: int`, `config_hash: str`, composite, per-TF scores, macro, technical, levels, plus an `ai_context: str`. Serializable to the canonical JSON of P0.1.
- `class Engine(cfg, feed)`: `def step(self) -> Snapshot`.
- `render_ai_context(snapshot) -> str` — the ONLY producer of AI context (kills prompt drift; consumes config, never literals).

**Tasks (each: write parity/equivalence test first, implement, keep golden parity green, commit):**
- [ ] **1.1** Generate the three instrument YAMLs from `config.py`; test: loading YAML reproduces every current constant exactly.
- [ ] **1.2** `InstrumentConfig` loader + `config_hash` (stable hash of normalized config).
- [ ] **1.3** `Feed` protocol + `LiveMT5Feed` adapter wrapping the current data path.
- [ ] **1.4** Parameterized `MacroScorer`; equivalence test: matches current per-instrument macro output on fixtures; then delete the inline copy.
- [ ] **1.5** `technical.py` extracted from `technical_scorer.py`; equivalence test on fixtures.
- [ ] **1.6** `Snapshot` schema + `Engine.step()`; parity test: `Engine.step()` over each fixture == golden JSON (byte-identical).
- [ ] **1.7** `render_ai_context`; test: output derives all weights from config (regression for defect 3, now structural).
- [ ] **1.8** Determinism test: same fixture ⇒ identical `config_hash` + identical snapshot across 100 runs.
- [ ] **Exit:** all parity green on Win10 + Win11 → `brain close-impl` → `/brain handoff`.

---

## Phase 2 — Data lake + point-in-time replayer  ·  Model: Sonnet 5 (+2-strikes gate)  ·  Dep: P1

> **2-strikes proving ground (governance §4):** look-ahead leakage bugs are subtle. Any task here that fails acceptance twice in a row → `/brain update` → Opus orchestrator. Design detail: Fable §2 intro + §2.6/§2.7 leakage rules.

**Exit gate:** `HistoricalFeed(as_of=t)` exposes ONLY data ≤ t (leakage test green); Parquet lake built from Dukascopy NQ100 + XAUUSD + MT5 with manifests; trade ingesters produce schema-validated normalized trades; replayer reproduces a live snapshot when fed the same point-in-time window. Win10 + Win11.

**Files:** `sentinel_engine/lake/ingest_dukascopy.py`, `ingest_mt5.py`, `manifest.py`, `sentinel_engine/feed_historical.py` (`HistoricalFeed`), `sentinel_engine/timeline.py` (`TimelineAligner`), `sentinel_engine/trades/ingest_xtb.py`, `ingest_mt5_trades.py`, `schema.py`.

**Interface contracts:**
- `HistoricalFeed(lake, as_of)` implements `Feed`; every accessor filters to `ts <= as_of`.
- `TimelineAligner(feeds).events()` — yields aligned point-in-time cursors across symbols/TFs.
- Trade schema (v1): `[account, symbol, side, open_ts, close_ts, open_px, close_px, size, pnl, r_multiple]`; ingesters validate and reject on mismatch (schema unverified today — §Part D).

**Tasks:**
- [ ] **2.1** Trade schema + validator; test rejects malformed rows, accepts a known-good fixture.
- [ ] **2.2** XTB trade ingester (adapter → schema v1); test on a real export sample.
- [ ] **2.3** MT5 trade ingester; test on a local CSV sample.
- [ ] **2.4** Dukascopy ingester → Parquet lake + manifest (coverage ranges, gaps); test manifest correctness.
- [ ] **2.5** MT5 price ingester → lake.
- [ ] **2.6** `HistoricalFeed(as_of)` + **leakage test** (asserts no field derived from data > `as_of`).
- [ ] **2.7** `TimelineAligner`; test alignment across two symbols with different bar cadences.
- [ ] **2.8** Replayer equivalence: `Engine` over `HistoricalFeed(as_of=t)` == the live snapshot captured at `t` (uses P0.7 snapshot logs as truth).
- [ ] **Exit** → `brain close-impl` → `/brain handoff`.

---

## Phase 3 — FastAPI service + thin frontend  ·  Model: Sonnet 5 (Fable one-shot candidate, see governance §5)  ·  Dep: P1

**Exit gate:** one uvicorn process serves all instruments; frontend renders snapshots via WS with no per-tick full reload; UI golden-master parity (shows the SAME thing to every trader — fixes the state-inconsistency correctness bug); not slower than today on target HW. Win10 + Win11.

**Files:** `sentinel_engine/service/app.py` (FastAPI), `service/stream.py` (WS broadcaster), `web/index.html`, `web/app.js`, `web/style.css` (uPlot vendored locally — no CDN).

**Interface contracts:** `GET /snapshot`, `WS /stream` (push each new snapshot), `GET /history?from=…` (P2 store), `POST /chat` (P5), `GET /config`.

**Tasks:**
- [ ] **3.1** FastAPI app + `/snapshot` + `/config`; test endpoints return the live snapshot schema.
- [ ] **3.2** WS broadcaster pushing each `Engine.step()` snapshot; test a client receives monotonic `seq`.
- [ ] **3.3** Background compute loop → snapshot holder → broadcast; test one loop feeds N clients identically (state-consistency fix).
- [ ] **3.4** Static frontend: render composite + per-TF + macro + levels; uPlot charts; reconnecting WS client. Vendored assets only.
- [ ] **3.5** UI parity check vs golden snapshot fields; performance sanity on target HW.
- [ ] **Exit** → `brain close-impl` → `/brain handoff`.

---

## Phase 4 — Optimization + validation engine  ·  Model: **Opus 4.8** (+ gated Fable one-shot)  ·  Dep: P1, P2

> **Decision gate BEFORE starting (governance §5):** re-evaluate whether to spend the reserved Fable one-shot on a P4 design pass or redirect it. Record decision + rationale in tracker. Opus implementer authors per-task TDD code. Design source of truth: Fable §2.4–2.9 + §4 (read verbatim — the objective metric, walk-forward, purging, DSR, plateau, regime-balance are specified there exactly).

**Exit gate:** optimizer runs a full study per asset on the lake; produces a chosen config per asset with honest deflated-Sharpe reporting; walk-forward + embargo + purged labels enforced; single-touch holdout report generated win-or-lose; all trials persisted to SQLite+Parquet registry; selection obeys ≥70%-fold dominance + minimum-change prior + plateau + regime-balance guards. Win10 + Win11.

**Files:** `sentinel_engine/opt/objective.py`, `labels.py` (triple-barrier), `walkforward.py`, `search.py` (Optuna TPE + staged grids), `selection.py`, `registry.py` (SQLite+Parquet), `report.py`.

**Interface contracts (from Fable §4):**
- Objective = capped Profit Factor × √(trade-count ratio) in R-multiples, s.t. maxDD / win-rate / min-trades constraints; full metric set persisted; score-accuracy & `filter_rate_pct` are **gates, not targets**.
- `triple_barrier(prices, tp, sl, horizon) -> labels`; reference-policy PnL from optimal SL/TP; real trades used only as validation.
- Anchored walk-forward: train `[start,T_i]` → test `[T_i,T_i+2mo]`, 2-mo step, 1-day embargo, purged labels at boundaries (§2.6).
- Selection: median test-fold J; must beat production in ≥70% folds; minimum-change prior among 1-SE ties; plateau ±10% (reject if J degrades >25%); regime-balance guard for any regime >15% of test time.

**Tasks (Opus authors the TDD; acceptance gates are fixed here):**
- [ ] **4.1** Triple-barrier labeler + purging-at-boundary; test labels never cross a fold boundary into train.
- [ ] **4.2** Objective metric + constraint gates; test the two degeneracies (fluke-chasing, trade-starvation) are blocked.
- [ ] **4.3** Anchored walk-forward splitter + 1-day embargo; test no train label horizon crosses into test.
- [ ] **4.4** Optuna TPE + staged block-wise search (3–8 dims/fit) + per-stage random-search floor; test reproducible study with fixed seed.
- [ ] **4.5** Selection rule (median-fold, ≥70% dominance, min-change prior, plateau, regime-balance); test each guard rejects a crafted bad config.
- [ ] **4.6** SQLite+Parquet registry (all trials, trial counts for DSR); test round-trip + DSR computed for winner.
- [ ] **4.7** Report generator (single-touch holdout, per-regime metrics, honest DSR p-value); test a full study end-to-end on a small lake slice.
- [ ] **Exit** → `brain close-impl` → `/brain handoff`.

---

## Phase 5 — AI assistant re-enable  ·  Model: Sonnet 5  ·  Dep: P1, P3

**Exit gate:** `/chat` answers using context from `render_ai_context(snapshot)` + MT5 positions (never literals — prompt drift impossible by construction). Win10 + Win11.

**Files:** `sentinel_engine/service/chat.py`; modify `sentinel/ai_chat.py` to consume the P1 renderer.
- [ ] **5.1** Wire `POST /chat` to build context solely from the current snapshot + positions; test the context contains config-derived weights.
- [ ] **5.2** Restore the assistant behavior on top of that context; test a canned Q returns a grounded answer.
- [ ] **Exit** → `brain close-impl` → `/brain handoff`.

---

## Phase 6 — Regime conditioning + per-asset tuning  ·  Model: Sonnet 5  ·  Dep: P2, P4

**Exit gate:** `RegimeLabeler` writes a point-in-time per-day/per-symbol regime table; optimizer fits global-first then regime-delta-second; snapshot carries today's regime. Design: Fable §2.9. Win10 + Win11.

**Files:** `sentinel_engine/regime/labeler.py`, `regime/calendar.py`.
- [ ] **6.1** `RegimeLabeler` (trend/vol/event/stress per §2.9), point-in-time only; test labels use only data ≤ t.
- [ ] **6.2** Regime table Parquet shared by optimizer + UI + live engine; test the live snapshot exposes today's regime.
- [ ] **6.3** Optimizer regime-delta pass (≥~15 sessions coverage); test deltas only fit where coverage sufficient.
- [ ] **Exit** → `brain close-impl` → `/brain handoff`.

---

## Phase 7 — Monthly retune runbook  ·  Model: Sonnet 5  ·  Dep: P4, P6

**Exit gate:** a documented, one-command monthly retune that ingests the latest month, reruns the study, and produces the report + a proposed config diff (never auto-applied). Win10 + Win11.

**Files:** `docs/runbooks/monthly-retune.md`, `sentinel_engine/opt/retune.py`.
- [ ] **7.1** `retune.py` orchestrating ingest → study → report → config diff; test on a small slice.
- [ ] **7.2** Runbook doc with exact PowerShell commands for Win10 + Win11.
- [ ] **Exit** → `brain close-impl` → `/brain handoff`.

---

## Self-review notes (author)
- **Spec coverage:** all 4 axes + 8 phases from governance §2 mapped to tasks. ✔
- **Delegation boundaries (P1, P4):** intentional per governance §3/§5 — Opus authors per-task TDD; acceptance gates are fixed here, so they are contracts, not placeholders. ✔
- **Windows 10+11:** in Global Constraints + every phase exit gate. ✔
- **Determinism/parity:** locked in P0.1–0.2, inherited by every scoring change. ✔
