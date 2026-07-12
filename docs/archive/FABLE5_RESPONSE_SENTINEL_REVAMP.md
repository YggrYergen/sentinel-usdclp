# SENTINEL Revamp — Design Response (Fable 5)

> Response to `BRIEFING_SENTINEL_REVAMP.md` (v3.7.1, commit `6ee5310`). One deliverable, sections 1–7 per Part I. Central weight on the backtesting/optimization engine. All assumptions are explicitly labeled `ASSUMPTION`. Open questions collected at the end; nothing here blocks on them.

---

## 0. Executive orientation (read this first)

The single highest-leverage decision in this entire revamp is: **extract a headless, deterministic compute core (`sentinel_engine`) out of the current modules, driven by a pluggable feed abstraction (live MT5 / historical), producing immutable, timestamped, serializable `Snapshot` objects.** Every axis then becomes a consumer of that core:

- **Axis 1 (UI):** a background compute loop produces snapshots; a thin frontend renders them. Rendering cost and state inconsistency both die because compute is decoupled and the snapshot is the single source of displayed truth.
- **Axis 2 (backtesting):** the optimizer replays the *same* core over historical feeds with a *parameterized config variant*, guaranteeing replay==live fidelity by construction (killing the `normalize_macd` class of bug forever).
- **Axis 3 (AI):** the assistant's context is generated from the snapshot (plus MT5 positions), so it can never drift from the running code again (killing the 75/25-vs-50/50 prompt bug forever).
- **Axis 4 (replay/logging):** replay = the core over a historical feed with a cursor; logging = persisting every live snapshot.

Everything below is the concrete design of that core and its four consumers.

**Stack recommendation in one line:** keep Python; extract the core; run compute in a background process/thread exposing snapshots over a local FastAPI server (WebSocket push); replace Streamlit's full-rerun page with a single static HTML/JS page that paints snapshot diffs. Migrate incrementally with a golden-master parity harness proving bit-identical outputs. Backtesting: a **custom event-driven point-in-time replayer around the extracted core** (not vectorbt/backtrader — the scoring is bespoke and stateful), with **Optuna (TPE + pruning)** for search, **anchored walk-forward with purged folds** for validation, **triple-barrier synthetic labels + real-trade validation** as ground truth, and a **SQLite + Parquet run registry** for persisted comparable reports.

---

## 1. Stack recommendation (Part C)

### 1.1 Root-cause analysis of the two reported symptoms

**Heaviness.** The cost is not the math. The full scoring pipeline (4 TFs × ~200 bars of pandas indicator work + EWMA updates + one 200-bar H1 correlation matrix + S/R) is on the order of 100–300 ms on a 4-thread laptop. The dominant costs are: (a) Streamlit **re-executing a 1658-line script** every 1.5 s, re-serializing the whole DOM delta over its WebSocket, and the browser re-painting a large injected-CSS page; (b) **pandas/`ta` recomputation of full indicator columns over 200 bars × 4 TFs × N instruments per tick** when only the last bar changed; (c) Python + Streamlit runtime + Chromium tab + MT5 co-resident in 4–6 GB, causing paging. On v2 with three panels the script cost roughly triples. So the fix is architectural (stop re-running/re-rendering everything), not micro-optimization.

**Inconsistency ("different traders see different things").** With fully local per-trader instances and no shared state, *some* divergence is physically irreducible (different brokers' tick arrival, different refresh phases). But the current design amplifies it far beyond that floor:

1. **Path-dependent EWMA state**: `RealtimeCorrelationTracker` state depends on the exact sequence of ticks the instance happened to sample at its own 1.5 s phase. Two instances started 45 s apart have different warm-up states and different EWMA trajectories for minutes to hours.
2. **Cache-TTL phase**: the 5 s MT5 / 30 s Yahoo TTL means instance A may score bar *t* while B scores bar *t−1*.
3. **`session_state` tick buffers** (≤200-tick velocity/acceleration buffers) are per-browser-session; a page reload silently resets derivatives to zero while another instance shows large values.
4. **Frozen-at-start values** in some paths (the replay correlation defect is the extreme case; the "HOY" correlation and legacy H1 correlation also refresh on different effective cadences).
5. **Mixed data sources**: one instance on MT5, another silently degraded to Yahoo (0.1% synthetic spread, delayed closes) will show materially different numbers with no loud indication beyond the sidebar.

**Design consequence:** consistency must be redefined as a testable invariant — *"given the same input event stream, the displayed state is a pure function of that stream"* — and the architecture must make the input stream explicit (an ordered sequence of (timestamp, symbol, tick/bar) events) rather than implicit in rerun timing. That is exactly what the headless core does. Cross-instance, the residual divergence then reduces to genuine feed differences, which should be *surfaced* (data-source and staleness badges per panel) rather than hidden.

### 1.2 Candidate architectures evaluated

**(a) Keep Streamlit, use `st.fragment` + background compute.** Streamlit ≥1.37 supports `@st.fragment(run_every=…)` for partial reruns and background threads feeding `session_state`. Effort: low (days). Trade-offs: it fixes maybe half the render cost (fragments still rerun their own subtree; the heavy CSS/HTML string building remains), does **not** fix the state model (session_state still per-session, still browser-tab-coupled), keeps the full Streamlit+tornado runtime resident, and Streamlit's rerun semantics keep fighting a push-based data model. Verdict: acceptable as a **stopgap** (Phase 0 mitigation) but not the destination. **Discarded as final answer** because it leaves the consistency problem structurally unsolved and the memory footprint intact.

**(b) Native desktop GUI (PySide6/Qt, Tkinter, Dear PyGui).** Pros: lowest RAM (no browser), true event-driven rendering, single process. Cons: the existing UI is heavily HTML/CSS-idiomatic (tooltips, sparklines, cards) and would need a full visual rebuild in a widget toolkit; Qt licensing is fine (LGPL) but PySide6 wheels add ~200 MB; iteration speed with agent-driven development is slower than HTML; your team maintains it and HTML skills transfer better. Dear PyGui is fast but visually alien to the current design. Verdict: **discarded** — highest migration cost for a gain the web-service option also achieves.

**(c) Tauri/Electron shell + Python sidecar.** Electron: +150–300 MB RAM, exactly the wrong direction on 4–6 GB machines. Tauri: needs a Rust toolchain in the build pipeline and WebView2 (present on Win10 with Edge, usually fine) — but it is just a wrapper around option (d)'s frontend with extra build complexity. Verdict: **discarded**; if a "feels like an app" shell is ever wanted, `pywebview` (a 1-file Python wrapper over WebView2) gives the same result over option (d) for near-zero cost.

**(d) RECOMMENDED — Local compute service + thin web frontend.**
- **Compute core** (`sentinel_engine/`, pure Python, no UI imports): the existing scorers refactored per §1.4, running a **single background loop** (thread or dedicated process) at the configured cadence: pull ticks/bars → update trackers → compute composite → emit an immutable **`Snapshot`** (a frozen dataclass / dict, JSON-serializable, containing *everything* the UI shows: all scores, per-TF details, macro votes, levels, alerts, derivatives, data-source + staleness metadata, config-version hash, monotonic sequence number).
- **Service layer**: **FastAPI + uvicorn** (both lightweight, pure-Python-friendly, already installable by the existing launcher). Endpoints: `GET /snapshot` (latest), `WS /stream` (push each new snapshot), `GET /history?from=…` (from the logging store, Part F), `POST /chat` (AI, Part E), `GET /config`. One process serves all instruments/panels.
- **Frontend**: **one static HTML+CSS+vanilla-JS page** (no framework, or a micro-lib like `lit-html`/`preact` if desired; charts via **uPlot** — ~40 KB, MIT, canvas-based, dramatically lighter than plotly). It opens the WebSocket and **patches only changed DOM nodes** keyed by snapshot fields. The current dashboard is fundamentally a grid of value cards — this maps trivially. Sparklines: uPlot or inline `<canvas>`. The existing dark CSS ports almost verbatim.
- **Optional shell**: launch the default browser at `localhost:8501` exactly as today, or `pywebview` for a chromeless window. No packaging change beyond `requirements.txt` (fastapi, uvicorn, websockets ≈ 15 MB; Streamlit and its dependency tree can eventually be **removed**, a net footprint *reduction*). The launcher's step 8 changes from `streamlit run app.py` to `python -m sentinel.server`. 50 GB SSD constraint: trivially satisfied; total install shrinks.

**Why (d):** it is the only option that simultaneously (i) decouples compute from rendering (compute runs even if no browser is attached — which is also exactly what the native logger of Part F needs), (ii) makes displayed state a pure function of an explicit snapshot (consistency invariant testable), (iii) cuts render cost to DOM diffs of a few dozen text nodes per tick, (iv) reuses your team's existing HTML/CSS assets and agent-friendly iteration, and (v) yields the headless core Parts D/E/F all require. Estimated migration effort: **compute-core extraction 2–4 agent-days; server + frontend for v1 parity 4–7 agent-days; v2 panels 2–3 more** (they share the same panel component parameterized per instrument — which also *deletes* the `instrument_panel.py` duplication).

### 1.3 Guaranteeing output-identical behavior (the parity harness)

Non-negotiable #1 is enforced mechanically, not by care:

1. **Freeze a golden master first.** Before touching any scorer, write a capture script that (a) records a session of raw inputs — every `get_data` frame and `get_current_price` dict, pickled with timestamps — and (b) runs the *current* code over them, recording every output (`calculate_composite` dict, per-TF dicts, macro votes, levels, fusion). Store as `tests/golden/`.
2. **Parity tests**: after each refactor step, replay the recorded inputs through the new core and assert **exact equality** (`==` on rounded values exactly as the current code rounds; float-exact where no rounding exists). Any intentional bug fix that changes outputs (there are two known: replay `normalize_macd`, replay correlation) is quarantined behind an explicit flag and excluded from the live path until signed off.
3. **Determinism rules** in the core: no wall-clock reads inside scoring (timestamps come from the feed event), no dict-ordering dependence, seeds pinned anywhere randomness could appear (there is none today; keep it that way in the live path).
4. **Config hash in every snapshot**: `sha256` of the canonicalized active config, displayed in the footer. Two traders comparing screens can instantly verify they run the same parameters — this alone resolves a whole class of "we see different things" reports (stale git pulls, local edits).

### 1.4 The headless compute core — concrete shape

**Recommendation: yes, extract it.** Package `sentinel_engine/` with these boundaries:

- `feeds.py`: `Feed` protocol — `get_bars(symbol, tf, n, as_of=None)`, `get_tick(symbol, as_of=None)`, `now()`. Implementations: `MT5Feed` (wraps current `DataFeed`), `YahooFeed`, `HistoricalFeed` (Part D/F: backed by Parquet, honors `as_of` strictly — the leak-free contract lives *here*, in one place). The `as_of` parameter is the single mechanism that makes live and replay share code.
- `instrument.py`: **`InstrumentConfig`** dataclass — *the* single source of truth per asset: symbols map, expected correlations, asset weights, TF set + weights, indicator params, sub-score weights, composite weights, thresholds, EWMA lambdas, warm-up, fusion params, risk params, session hours. Serializable to/from YAML/JSON. The current `config.py` constants become the three default instances (`USDCLP`, `XAUUSD`, `NQ100`). **This object is also the optimizer's genome (Part D)** — a "variant" is literally an `InstrumentConfig` file, its hash the variant ID. This kills the triplicated weight tables (config / macro_scorer module-global / correlation_engine hardcoded) in one move.
- `technical.py`, `macro.py`, `levels.py`, `fusion.py`: current logic, ported verbatim, but **every function takes an `InstrumentConfig`** instead of reading module globals. `MacroScorer(cfg)` replaces both the hardwired class and the `instrument_panel._calc_macro` inline copy (parity tests prove the inline copy and the class produce identical numbers before deletion — per the brief they already should, since the panel copy is "identical but parameterized").
- `core.py`: `Engine(cfg, feed)` with `step(event) -> Snapshot`. Owns all mutable state (trackers, tick buffers, velocity/accel windows) so that state is *inspectable and serializable* — needed for replay checkpointing and for the consistency invariant.
- `snapshot.py`: the `Snapshot` schema + JSON codec + the flat "AI context" renderer (Part E) generated **from the snapshot fields**, with weights/formulas interpolated from `cfg` (never hardcoded prose again).
- `logging_store.py`: append-only snapshot persistence (Part F).

Threading model on the trader laptop: **one process**; a compute thread per instrument family (or one thread round-robining all three — at 1.5 s cadence and ~100–300 ms compute, one thread suffices; ASSUMPTION: measured compute confirms this, else split), FastAPI on the main asyncio loop, snapshots handed over via a thread-safe "latest value" slot + broadcast queue. MT5's Python API is not thread-safe across processes sharing one terminal; keep all MT5 calls on one thread (as today, effectively).

### 1.5 Performance expectations & remaining risks

Expected on target hardware: steady-state CPU for compute unchanged (~5–15% of one core); render cost drops from "full page per 1.5 s" to sub-millisecond DOM patches; RAM drops by the Streamlit runtime (~150–250 MB) and by not holding Streamlit's element tree; the browser tab becomes a static page with small live text updates. Risks: (i) WebSocket disconnects on sleep/resume — auto-reconnect with `GET /snapshot` resync; (ii) uvicorn on Windows: use `asyncio` loop (default), well-supported; (iii) the incremental-indicator temptation — **do not** rewrite indicators incrementally in v1 (recompute the 200-bar window per bar as today; it is cheap and parity-safe; incremental EMA/RSI is a later optimization with its own parity tests).

---

## 2. Backtesting & optimization engine (Part D) — CORE

### 2.1 Architecture overview

```
                         ┌────────────────────────────────────────────┐
  Dukascopy / MT5 export │  DATA LAYER (Parquet lake, per symbol/tf)  │
  XTB export / MT5 deals │  ingest → validate → align → label regimes │
                         └───────────────┬────────────────────────────┘
                                         ▼
                         ┌────────────────────────────────────────────┐
                         │  POINT-IN-TIME REPLAYER                    │
                         │  HistoricalFeed(as_of) + Engine(cfg)       │
                         │  → Snapshot stream (leak-free, warm-up-    │
                         │    honest, identical code to live)         │
                         └───────────────┬────────────────────────────┘
                                         ▼
        ┌────────────────┬───────────────┴──────────────┬─────────────────────┐
        ▼                ▼                              ▼                     ▼
  TRADE SIMULATOR   TRADE-MATCHER                REGIME LABELER        SL/TP STUDY
  (rules → fills,   (real XTB/MT5 trades vs      (bull/bear/high-vol/  (MAE/MFE per
  costs, sessions)  snapshot at entry)            news/war flags)      trade cluster)
        └────────────────┴──────────────┬───────────────┴─────────────────────┘
                                        ▼
                         ┌────────────────────────────────────────────┐
                         │  OBJECTIVE EVALUATOR  → metrics per fold   │
                         └───────────────┬────────────────────────────┘
                                         ▼
                         ┌────────────────────────────────────────────┐
                         │  OPTIMIZER (Optuna TPE / grid per group)   │
                         │  anchored walk-forward, purged folds       │
                         └───────────────┬────────────────────────────┘
                                         ▼
                         ┌────────────────────────────────────────────┐
                         │  RUN REGISTRY (SQLite + Parquet + HTML)    │
                         │  variant × asset × fold × regime × tf      │
                         └────────────────────────────────────────────┘
```

Everything is a plain Python package (`sentinel_lab/`) run by a CLI (`python -m sentinel_lab.run study.yaml`) on the developer machine, unattended end-to-end. Output of a study: a set of winning `InstrumentConfig` YAML files + a full report. Shipping to traders = committing those YAMLs to the repo (the launcher's existing git-pull update channel already distributes them).

**Why a custom replayer instead of vectorbt / backtrader / backtesting.py / Nautilus:** the thing being optimized is not a standard indicator strategy — it is SENTINEL's bespoke, *stateful* pipeline (dual-lambda EWMA tick trackers with warm-up, sign-concordance windows, multi-TF blending, fusion logic). Off-the-shelf vectorized frameworks (vectorbt) require expressing the signal as array operations — a full reimplementation that would *guarantee* live/replay divergence, the exact disease we are curing. Event-driven frameworks (backtrader, Nautilus Trader) would wrap our engine in their abstractions for little gain and real integration cost (Nautilus is excellent but heavyweight, Rust-cored, and its value is order-management realism we barely need for a signal system). **Decision: the replayer is ~500 lines around the already-extracted `Engine`; the trade simulator is ours; we borrow libraries only where they are commodities** — `optuna` (search), `pandas/pyarrow` (data), `scipy/statsmodels` (stats), optionally `quantstats` (tearsheet metrics). All free/OSS, satisfying Part H. Discarded alternative: writing the optimizer loop by hand (random+grid) — Optuna's TPE, pruning, storage, and resume-ability are too valuable for zero cost.

### 2.2 Data layer

**Price history.**
- **Primary source: Dukascopy** via `dukascopy-node` (free, Node CLI; ASSUMPTION: installing Node on the dev machine is acceptable — alternative pure-Python: `duka` or `findatapy`, less maintained). Pull **tick data** where the macro layer needs it and **M1 bars** otherwise, for: targets `XAUUSD`, `NQ100` (Dukascopy: `usatechidxusd`), `USDCLP` (⚠ not on Dukascopy — see below); macro basket: DXY (`usdollarindexusd` or synthesize from EUR/JPY/GBP/CAD/SEK/CHF legs), silver `XAGUSD`, EURUSD, USDJPY, S&P (`usa500idxusd`), copper (`copperusd`... **verify availability**; fallback COMEX HG via other source), Brent/WTI (`brentcmdusd`/`lightcmdusd`), BTC (`btcusd`), VIX (⚠ Dukascopy has no VIX — source daily/intraday VIX from CBOE's free CSVs or Yahoo `^VIX`; intraday VIX at 1-min is available from CBOE with delay; ASSUMPTION: 1-min VIX from Yahoo's 60-day window forward-collected + daily VIX backfilled is acceptable for macro replay, with the limitation flagged in reports).
- **Secondary: MT5/Capitaria** `copy_rates_range` from the `MT5_Tester` instances — this is the *only* deep source for `USDCLP` and for broker-exact prices/spreads on all Capitaria symbols. Depth is broker-dependent (typically months of M1). Pull it all now; it also gives **real spread** if tick data (`copy_ticks_range`) is available.
- **Storage:** Parquet lake `data_lake/{symbol}/{tf}/year=YYYY/…`, columns `time(UTC), open, high, low, close, volume, spread?` + a `source` column. Ingest jobs are idempotent (re-run = upsert). A `manifest.json` per symbol records coverage gaps.
- **Alignment:** all series normalized to UTC; a single `TimelineAligner` produces, for any `as_of`, each symbol's last-completed bar per TF — replicating live semantics (live scores use the in-progress bar's latest state for M1; ASSUMPTION: for replay we evaluate at M1-bar close, i.e., signals are computed on completed M1 bars — this is slightly conservative vs. live intra-bar updates and is the correct leak-safe default; intra-bar tick replay is available where tick data exists, used for the macro tracker, see §2.3).
- **Cross-source calibration:** Dukascopy vs Capitaria prices differ (different liquidity pools; NQ100 CFDs differ in absolute level). Before mixing, compute per-symbol return-correlation and level offsets over the overlapping window; **rule: optimize *shapes* (returns/indicators) on Dukascopy, validate on Capitaria overlap, and always simulate costs with Capitaria spreads.**

**Real trades.**
- Ingest **XTB export** (xStation CSV/xlsx) and **MT5 `history_deals_get` / MT5 CSV** into one normalized schema: `trader_id, account, symbol, direction, volume, entry_time, entry_price, exit_time, exit_price, sl, tp, pnl, commission, swap, source, raw_ref`. The MT5 deal-pairing logic from `compare_with_trades` (IN/OUT on `position_id`) is reused and hardened (partial closes → multiple exits per position; ASSUMPTION: aggregate partials into one position with volume-weighted exit).
- **Schema is unconfirmed (D.3)** — the ingester is therefore written as per-source adapter classes with a validation step that *reports* unmapped/missing fields rather than crashing; first real files will finalize mappings (see Open Questions).
- Remove the current `"USDCLP|CLP"` regex filter; filter by a per-study symbol list instead.

### 2.3 Point-in-time (leak-free) evaluation

The replayer walks the M1 timeline of the target asset. At each step `t`:

1. `HistoricalFeed.as_of = t`. Every `get_bars` call returns only bars with `close_time ≤ t`. Every `get_tick` returns the last known tick ≤ t (from tick data where present, else bar close). **There is no other data path** — leak-freedom is enforced by the feed, not by discipline in scoring code.
2. **Macro tracker with honest warm-up:** the EWMA tracker is `update()`-ed along the timeline exactly as live (per M1 step, or per tick where tick data exists — configurable; default M1 steps with the tanh sensitivity as the live `calculate_score_at_window` path uses, since live `update_tick` cadence ≈ dashboard refresh which M1 stepping approximates; the difference is measured once in a fidelity experiment and documented). Warm-up (≥30 updates) is respected: early snapshots carry `confidence=0` exactly as live. **This fixes the frozen-correlation defect by construction** — there is no "compute correlation once" anywhere.
3. `Engine.step()` emits the Snapshot. Identical code to live — the `normalize_macd` divergence disappears because there is only one code path (`normalize_macd=True` per the live contract).
4. Snapshots stream to Parquet (same format as the native logger, Part F — one format, three producers: live, replay, backtest).

Cost: ~1 year of M1 ≈ 370k steps × (multi-TF score + macro) — with the pre-slicing trick the current backtester already uses, plus caching indicator columns per TF frame and only recomputing the tail, expect **1–5 k steps/s single-core → a year per asset in minutes**. Optuna parallelizes trials across the dev machine's cores (`n_jobs`) since each trial is an independent replay.

**Known replayer defects fixed at birth:** the `CorrelationEngine` ImportError (the class never existed — the legacy correlation table is recomputed rolling per step from the aligned H1 lake, or simply excluded from replay since it is UI-only and not in the composite; **decision: excluded from the optimization objective, included optionally in snapshots for completeness**); `normalize_macd` fidelity; single-asset hardwiring (the replayer takes any `InstrumentConfig`).

### 2.4 Ground truth & objective functions

**Reconciling "signal endorsement" vs "realized PnL" (D.3):** these are two evaluation layers, not competitors.

- **Layer 1 — dense synthetic labels (primary optimization signal).** Real trades are far too sparse (a few hundred at best across regimes) to fit dozens of levers. Label *every* M1 timestamp with a **triple-barrier outcome**: from `t`, does price hit `+k·ATR` before `−k·ATR` within horizon `H` (per the 1–30 min scalping mandate: `H ∈ {15, 30, 60}` min, `k` tied to the live SL/TP multipliers, e.g. TP barrier `1.5·ATR`, SL barrier `1.0·ATR`, ratio matching min R:R 1.5)? Labels: LONG-good / SHORT-good / neutral (timeout). Costs (spread) are subtracted from the barrier distances so a "good" label already clears real friction.
- **Layer 2 — simulated strategy PnL (the operative truth).** Convert snapshots into simulated trades with a fixed, simple execution policy (the "reference policy"): enter when composite ≥ threshold with direction ≠ NEUTRAL (+ optional fusion-confluence gate + session filter), SL/TP = ATR multipliers from the active risk mode, exit on opposite strong signal or hard close 15:30 CLT; one position at a time; costs per §2.7. This is what "if followed, maximizes profit and minimizes losses" *means* operationally. The reference policy itself is held **fixed during indicator/weight optimization** (so we optimize the signal, not an entangled strategy), then optimized separately in the SL/TP study.
- **Layer 3 — real-trade cross-check (validation, never fitting).** For each candidate config, recompute `accuracy_pct` and `filter_rate_pct` against each trader's actual trades (the existing `compare_with_trades` semantics, fixed and generalized). A config that wins Layers 1–2 but *worsens* the filter-rate on real losing trades is flagged, not shipped.

**Objective function (D.5 "objective metric" — resolution):** a **constrained scalar** for the optimizer plus a **Pareto report** for humans.

- Scalar (per fold, then aggregated per §2.6):
  `J = ProfitFactor_capped(3.0) × sqrt(n_trades / n_ref)` subject to constraints: `maxDD ≤ 1.25 × baseline_maxDD`, `n_trades ≥ n_min` (statistical floor, e.g. 30/fold), `win_rate ≥ 0.35`. Constraint violations → heavily penalized (Optuna pruning). Profit factor is capped to stop the optimizer chasing 3-trade flukes; the `sqrt(n)` term rewards signal frequency (a scalper's edge must recur). Expressed in **R-multiples** (PnL / initial risk) so it is volume- and capital-independent and comparable across assets.
- Reported alongside (not optimized directly): net PnL (R), win rate, max drawdown (R), average R, Sharpe on daily R-series, **deflated Sharpe ratio** (Bailey–López de Prado, penalizing the number of trials tried — computed at study level), label-accuracy vs Layer 1, real-trade `accuracy/filter_rate` per trader, per-regime breakdown.
- Multi-objective handling: **weighted/constrained scalar for search** (TPE behaves better than NSGA-II at our trial budgets and the constraints encode the real business asks: "fewest losses" → maxDD/win-rate constraints; "most income" → PF/expectancy). The registry stores all metrics, so any Pareto view can be rendered after the fact. Discarded: pure NSGA-II multi-objective — slower convergence, and the team ultimately must pick one config per asset anyway.

### 2.5 The lever inventory — treatment per group & search methods

Full enumeration (from D.2) with dimensionality, prior, and method. Guiding principle: **staged, grouped optimization (coordinate-block descent over lever groups) rather than one 40-dimensional search** — the groups are weakly coupled, sample efficiency demands it, and it mirrors how the system composes.

| Group | Levers (dims) | Search method | Notes |
|---|---|---|---|
| **G1 Indicator params** | EMA lengths (9/21/50/200→ keep 200 fixed; 3 dims, small integer grids), RSI period + OB/OS (3), MACD 12/26/9 (3, constrained fast<slow), BB period/σ (2), ATR period (1) | **Optuna TPE**, integer/log-uniform priors centered on current values, ±60% ranges | Highest overfit risk (classic data-snooping territory); heaviest regularization (§2.6): prefer parameter-stable plateaus, penalize distance from canonical defaults with a mild prior term. |
| **G2 Technical sub-weights** | EMA/RSI/MACD/BB/PA weights (4 free dims on simplex) | **Dirichlet-sampled TPE** or coarse simplex grid (steps of 0.05) | Cheap; also test *removing* PA (weight 0). |
| **G3 TF blend** | which TFs + weights (M1/M2/M5/M15; 3 free dims + subset choice) | Exhaustive over TF subsets (≤15) × simplex grid | Resolves the 35/35/20/10 vs 40/30/20/10 inconsistency empirically; also test adding M30. |
| **G4 Composite & thresholds** | tech/macro weight (1), direction-vote weights (1 ratio), alert/strong thresholds (2), NEUTRAL band (±0.15) (1) | **Full grid** (small, smooth space) — grid is preferable here for exhaustive comparability across assets | Thresholds interact with the reference policy → optimized jointly with it. |
| **G5 Macro engine** | per-asset expected-corr signs/magnitudes (use signs only as levers; magnitudes are gates, 7–8 dims but mostly frozen to empirical rolling estimates — see below), asset weights (7–8 dims simplex), λ_var/λ_cov (2, log-scale near 0.85/0.97), concordance window (1), z-break window/threshold (2), warm-up (1), tanh sensitivity (1) | **TPE**, two passes: first weights+sensitivity with dynamics frozen, then dynamics | **Key insight:** `EXPECTED_CORRELATIONS` should largely stop being hand-set constants — replace magnitudes with **rolling empirical correlations** (e.g. 60-day daily-return corr, refreshed by the retuning pipeline) and keep only the *sign* and a *min-|corr| gate* as config. This converts a fragile lever into measured data and shrinks the search space. Signs that flip empirically per regime feed D.4 regime conditioning. |
| **G6 Fusion & risk** | fusion boost cap, opposed-pull 0.3, neutral-lean 0.6, confluence bands (4–5), ATR SL/TP multipliers per risk mode (6), R:R min, pause/session rules | Fusion: small grid. **SL/TP: the dedicated MAE/MFE study (§2.8), not blind search** | SL/TP search through replay alone is expensive; MAE/MFE analytics give near-closed-form answers first, then a confirmation grid. |
| **G7 Regime levers (new)** | regime definitions' thresholds + per-regime overrides of G4/G6 | Fit *after* G1–G6 global fit; per-regime deltas only (§2.9) | Keeps config sprawl bounded: a regime is a *delta* on the base config, not a full config. |

**Stage order:** G4 (with reference policy) → G2/G3 → G5 → G1 → G6 → G7, then **one final joint TPE polish** over the top-3 candidates per group with narrow ranges (≤ 300 trials). Each stage re-freezes previous winners. Total budget: ~2–5 k replays per asset per study — hours on the dev machine. Discarded: evolutionary/CMA-ES (fine but no advantage over TPE at this budget); pure random (baseline only — we do run 200 random trials per stage as a sanity floor: if TPE doesn't beat random, the lever group has no signal and we say so in the report).

### 2.6 Overfitting & validation strategy (D.5 resolution)

- **Anchored walk-forward** as the outer loop: e.g., for 2024-01→2026-06 data, folds = train `[start, T_i]` → test `[T_i, T_i+2 months]`, stepping 2 months, with a **1-day embargo** between train and test (purging: any triple-barrier label whose horizon crosses the boundary is dropped from train — López de Prado purged K-fold adapted to walk-forward).
- **Selection rule:** a config's score = **median test-fold J** (not mean — robust to one lucky fold), and it must beat the current-production config in **≥ 70% of folds**. Parameter-stability preference: among configs within 1 SE of the best, choose the one closest to current production values (an explicit "minimum-change prior" — cheap regularization, eases trader trust, and reduces snooping).
- **Final holdout:** the most recent 2 months are touched **once**, by the single chosen config per asset, after all selection. Result goes in the report verbatim, win or lose.
- **Deflated Sharpe / trial accounting:** the registry records total trials per study; DSR computed for the winner; the report shows the p-value honestly.
- **Plateau check:** for the winner, perturb each lever ±10% and require J degradation < 25% — cliff-edge optima are rejected as noise fits.
- **Regime-balance check:** the winner's per-regime metrics must not be catastrophic in any regime that covers >15% of test time (guard against "bull-only" configs) — see §2.9.

### 2.7 Transaction realism (D.5 resolution)

- **Spread:** per-symbol spread model from data: where Capitaria tick data exists, use recorded bid/ask; else a **time-of-day spread curve** (median spread per 15-min bucket, estimated from a few weeks of live tick logging — the Part F logger doubles as the collector) with a stress multiplier (×2) around news windows. The replay UI's "variable controllable spread" (Part F) uses the same model with a user override.
- **Slippage:** fixed per-asset baseline (ASSUMPTION: 0.5 × median spread per side for XAUUSD/NQ100 CFDs at retail size) + news-window multiplier. Refined later from real-trade fill analysis (entry price vs bar range at entry timestamp).
- **Commission/swap:** taken from the real-trade exports (they carry actuals); defaults per Capitaria's published schedule otherwise. Swap irrelevant for intraday scalps but included since real exports show occasional held positions.
- **Sessions & news:** trades only inside configured session (09:30–14:00 primary, hard flat 15:30 CLT for USDCLP; **XAUUSD/NQ100 get their own session configs** — ASSUMPTION: traders keep CLT day hours; confirm); `NEWS_BUFFER_MINUTES` blocks entries ±30 min around high-impact events from the calendar feed (§5/Part E share it).

### 2.8 Per-trader clustering & the optimal SL/TP study (D.4)

**Trade enrichment.** For every real trade, join the replayed snapshot at entry (leak-free: snapshot at-or-before entry time) → each trade gains: composite score/direction, tech & macro scores, per-TF directions, confluence, regime label, distance to nearest S/R, ATR at entry, session bucket, day-of-week, spread at entry. Then compute the trade's **MAE/MFE path** (max adverse/favorable excursion, in ATR units and in R) from the price lake between entry and exit — the single most informative dataset for SL/TP design.

**Clustering.** Two complementary groupings:
1. **Rule-based (primary, interpretable):** regime at entry (§2.9) × direction × signal-endorsement class (both-endorse / tech-only / macro-only / counter-signal) × session bucket. This matches the traders' own mental model ("group by trade type / where the market was heading").
2. **Statistical (exploratory):** k-means / HDBSCAN on standardized entry features (score, confluence, ATR-normalized S/R distance, velocity, regime one-hots) with silhouette-guided k; used to *discover* groupings rule-based misses, reported but not used for shipping parameters unless a cluster is stable across traders and time.

**Per-group trend review:** win rate, expectancy (R), PF, hold time, MAE/MFE distributions, per trader and pooled, with binomial confidence intervals (sample sizes will be small — always shown).

**Optimal SL:** per group, sweep SL ∈ {0.5…3.0 ATR, step 0.25} against the recorded MFE/MAE paths (this is analytic — no replay needed: a trade survives SL `s` iff MAE < s; its outcome then = min(TP, realized path)); choose the SL maximizing group expectancy subject to win-rate floor. Repeat for **TP** ∈ {1.0…5.0 ATR} given the chosen SL, then a small joint grid around the marginals. Then evaluate **trailing variants** on the paths: (a) ATR chandelier (trail = k·ATR from peak), (b) breakeven-at-1R then trail, (c) structure trail (last swing per `levels_engine`), (d) time stop (flat after N minutes if < x R). Output: per-group table `SL*, TP*, trailing*, expectancy delta vs actual` — the direct input to section 5 (EAs) and to the live UI's regime-aware SL/TP suggestion.

### 2.9 Macro regime conditioning (D.4, high priority)

**Regime taxonomy (per asset, per day, with intraday overrides):**
- **Trend regime:** BULL / BEAR / RANGE from daily anchor rules (e.g., close vs EMA50/EMA200 daily + ADX(14) > / < 20 on H4). Deliberately simple and point-in-time computable.
- **Volatility regime:** LOW / NORMAL / HIGH / EXTREME from ATR percentile (rolling 1-year) and, for NQ100/XAUUSD, VIX bands (<15 / 15–20 / 20–30 / >30).
- **Event regime (per symbol):** NEWS-DAY flags from an economic-calendar feed (free sources: ForexFactory calendar scrape or `investpy`-style alternatives; ASSUMPTION: a weekly-refreshed local calendar file is acceptable), mapped per symbol (NFP/CPI/FOMC → XAUUSD+NQ100+USDCLP; Chile IPoM/copper data → USDCLP; etc.).
- **Stress/"war" regime:** a composite risk-off flag: VIX > threshold AND gold+dxy co-rising AND equity drawdown > x% over 5 days — i.e., detectable from market data, not headlines (headline-driven classification is Part E's assistant, advisory only).

Labels are computed by a `RegimeLabeler` over the lake (point-in-time: only data ≤ t), stored as a per-day/per-symbol Parquet table shared by optimizer, replay UI (regime shown on the timeline), and live engine (today's regime in the snapshot).

**How regimes interact with optimization (D.5 resolution):** fit **global-first, regime-delta-second**. The base config is fit across all regimes (walk-forward as §2.6). Then, per regime with sufficient test coverage (≥ ~15 sessions and ≥ 30 simulated trades), fit a small **override set** (thresholds, macro/tech blend, SL/TP multipliers — G4/G6 only, never G1 indicator params) as deltas, validated on that regime's out-of-sample slices. Ship as `regime_overrides:` blocks inside the same `InstrumentConfig` YAML. This bounds config sprawl (one file per asset, small override maps), avoids per-regime overfit on thin samples, and gives the live engine a trivial switch: `cfg.effective(regime_today)`.

### 2.10 Statistical model comparison & the run registry (reporting)

**Registry:** one SQLite DB (`lab_registry.db`) + Parquet artifacts:
- `studies(study_id, created, git_commit, data_manifest_hash, seed, notes)`
- `variants(variant_id = cfg_sha256, asset, cfg_yaml, parent_variant, stage)`
- `runs(run_id, study_id, variant_id, fold, regime_slice, tf_profile, seed, started, dur_s)`
- `metrics(run_id, metric, value)` — long format: pnl_R, PF, winrate, maxDD_R, sharpe, DSR, n_trades, label_acc, real_accuracy_pct, real_filter_rate_pct, …
- Artifacts per run: equity curve Parquet, trade list Parquet, snapshot-stream sample.
- `reports/` : an auto-generated static **HTML report per study** (tables + uPlot/matplotlib charts): leaderboard, per-fold stability, per-regime heatmap, winner-vs-production diff of every changed parameter with before/after metrics, holdout verdict, DSR, and the reproduction command line. Deterministic: study YAML pins seeds, data manifest hash, and git commit; `python -m sentinel_lab.run study.yaml` reproduces bit-identically.

**Statistical comparison of two configs:** paired comparison on aligned fold returns — Wilcoxon signed-rank on per-fold J; bootstrap CI (block bootstrap on daily R-series, 10k resamples) on the PF/expectancy difference; report p-values and CIs, with the standing rule that **no config ships without: median-fold superiority, plateau check, holdout non-failure, and real-trade filter-rate non-regression.** White's Reality Check / SPA test is available in the backlog if variant counts grow large; at our scale, DSR + holdout + the honesty rules above are proportionate.

**Lifecycle (D.6):** the whole thing is a **repeatable retune**: `study.yaml` declares asset, date range, lever groups, budgets; a scheduled monthly run refreshes data (ingest jobs), re-fits, and emits the report; a human approves; the winning YAMLs are committed; traders receive them via the existing launcher git-pull. Adding a new lever = adding a field to `InstrumentConfig` + a prior in the study file — no engine rewrite. Adding a new asset = writing one `InstrumentConfig` + data-lake ingestion for its basket.

---

## 3. AI assistant (Part E) & Replay + Logging (Part F)

### 3.1 AI assistant — design

**Context assembly (cheap, per turn, never stale).** The system prompt is generated by `snapshot.render_ai_context(snapshot, cfg, positions, regime, calendar)` — a pure function of live objects. All weights/formulas are interpolated from `cfg` (the 75/25 and 40/30/20/10 hardcoded-prose defects become impossible). Added blocks vs today: **open MT5 positions** (from `positions_get`/`history_deals_get` — still read-only), today's **regime label**, the **active config hash + any regime overrides in force**, upcoming **calendar events with countdowns**, and the last N logged snapshots' score trajectory (from the Part F store — giving the assistant *time context*, which the current single-snapshot prompt lacks). Token budget: the snapshot context is ~2–4 k tokens; per-turn cost is dominated by model choice, not context.

**Model/effort roster — made trivially updatable.** Replace hardcoded `MODELS` with `sentinel/models.yaml`: entries `{key, model_id, display, max_tokens, in_price, out_price, supports_thinking, efforts[]}`. On startup, optionally validate/refresh against the Anthropic **models list API** (`GET /v1/models`) so new families appear without a code change; prices stay in the YAML (the API doesn't serve pricing). Mid-conversation switching: the conversation is a plain message list; each turn simply sends it to the currently selected model/effort — no migration needed; the UI (new stack) puts model + effort selectors in the chat header, and the **web-search vs extended-thinking mutual exclusivity** is enforced in the request builder exactly as today (UI disables the effort selector when search is on, and vice versa), isolated in one function so an API change lifts the restriction in one place.

**Auto per-trade chat (toggle, high priority).** The compute core already polls MT5; add a `PositionWatcher` that diffs `positions_get()` per cycle. On new position && toggle on: create a conversation seeded with a **trade brief** (symbol, direction, volume, entry, SL/TP, snapshot at entry, regime, distance to S/R, calendar next 4 h) and a fixed instruction: *assess merit, verify via web search if enabled, recommend SL/TP/levels/watch-items, flag excessive risk (position risk vs `RiskConfig`)*. Default model for auto-chats: the cheap tier (Haiku-class) with an "escalate" button; the first message is generated once (bounded cost), then the trader converses at will. On position close, append the outcome to the conversation and persist it — these transcripts become a per-trade journal that feeds Part D's trade enrichment (qualitative labels).

**News countdown, non-intrusively.** The calendar feed (shared with §2.9/§2.7) drives a small fixed **status strip** (top-right): `⏳ CPI US in 12:41` turning amber < 30 min, red < 5 min, with an optional native toast (browser Notification API) — no layout shift, no modal, indicators untouched. The same events drive the engine's `NEWS_BUFFER` flag already shown in alerts.

**Governance:** `UsageTracker` persists to SQLite (per day/model/trader), with a soft daily USD budget and a visible meter; API key from env or an encrypted local file (DPAPI on Windows), never in git. The assistant lives behind `POST /chat` on the same FastAPI service (streaming via SSE/WebSocket), so it works identically in the live UI and the replay UI (where its context is the replay-cursor snapshot — "ask the AI what SENTINEL saw at 2025-11-14 10:32" falls out for free).

### 3.2 Replay + logging — design

**Native logging (start immediately — it is the cheapest, highest-value item in the whole program).** The compute loop appends every snapshot (or every Nth; default: every snapshot, ~57 k/day/asset at 1.5 s) to hourly-rotated **Parquet** files under `data/snapshots/{asset}/{date}/`, plus a lightweight SQLite index (time → file/rowgroup). Size: a flattened snapshot ≈ 200–400 numeric fields → ~2–5 MB/day/asset compressed — trivially within 50 GB with a 90-day retention default. Also log raw ticks per symbol (time, bid, ask) — this doubles as the **spread-model collector** (§2.7). Same schema whether produced by live, replay, or backtest (`producer` column) — one reader serves all consumers.

**Replay tab.** A page on the same frontend: instrument selector, date/time picker, a **cursor slider + play/pause/speed (1×–60×) + step buttons**. Backend: a `ReplaySession` (per browser session, on the FastAPI service) = `Engine(cfg_variant, HistoricalFeed(lake))` stepped under cursor control, streaming snapshots over the same WebSocket protocol as live — **the frontend literally cannot tell replay from live**, so the entire panel UI is reused unmodified. Controls extra to live: **spread override** (slider or "recorded/model/custom"), **config-variant selector** (pick any `InstrumentConfig` YAML/registry variant — this is the "test different weights and see" requirement), and a mini trade-sim ticket (buy/sell at cursor with the chosen spread; the session tracks simulated PnL using the §2.7 cost model). Performance: seek = re-run the engine from the nearest **state checkpoint** (engine state serialized every 30 min of replayed time) — sub-second seeks. Statistical evaluation of variants "which is more convenient" routes to the same evaluator + registry as Part D (a replay session can be promoted to a registered run), so replay experimentation and formal backtesting share one metrics vocabulary.

**Data prerequisite** (shared with Part D): the lake must hold targets + full macro baskets. Coverage plan: Dukascopy backfill (NQ100 to ≥2024-01 as stated, XAUUSD same or deeper), MT5/Capitaria backfill for USDCLP + broker-exact series, VIX per §2.2, and from day one the native tick/snapshot logger closes all future gaps.

---

## 4. Resolution of every D.5 edge

1. **Objective metric.** Constrained scalar for search: capped Profit Factor × √(trade-count ratio), in R-multiples, s.t. maxDD / win-rate / min-trades constraints; full metric set persisted; Pareto views rendered post-hoc; deflated Sharpe reported at study level. Rationale in §2.4: it operationalizes "most income, fewest losses" while blocking the two classic degeneracies (fluke-chasing and trade-starvation). Score-accuracy and `filter_rate_pct` are validation gates, not optimization targets (optimizing filter-rate directly teaches the system to say "wait" always).
2. **Overfitting/data-snooping.** Anchored walk-forward + 1-day embargo + purged labels; median-fold selection with ≥70%-fold dominance over production; minimum-change prior among statistical ties; plateau (±10%) rejection of cliff optima; single-touch 2-month holdout; DSR with honest trial counts; random-search floor per stage to detect no-signal lever groups; staged block-wise search to keep effective dimensionality per fit at 3–8. (§2.5–2.6.)
3. **Look-ahead/leakage.** Enforced structurally: the only data access is `HistoricalFeed(as_of=t)`; EWMA/macro state is evolved along the timeline with live-identical warm-up; labels are purged at fold boundaries; regime labels are point-in-time; no per-replay frozen quantities exist. The broken/frozen legacy-correlation path is removed from replay scoring entirely (it was never in the composite). Fidelity experiments (M1-step vs tick-step tracker updates; bar-close vs intra-bar evaluation) are run once, quantified, and documented as the replay's stated approximation error. (§2.3.)
4. **Regime dependence.** Global-first fit, then per-regime **deltas** on G4/G6 only, only for regimes with adequate out-of-sample coverage; a regime-balance gate rejects configs catastrophic in any ≥15%-coverage regime; live engine applies `cfg.effective(regime)`. This prevents both failure modes: one-regime overfit and regime-blind averaging. (§2.9.)
5. **Ground-truth definition.** Three layers (§2.4): triple-barrier synthetic labels (dense, cost-aware, ATR-scaled, horizons matched to the 1–30 min mandate) drive optimization; simulated reference-policy PnL is the operative business truth; real trades are a per-trader validation set (accuracy & filter-rate non-regression), never a fitting target while samples are sparse. Trader idiosyncrasy: fit at **asset level** (pooled), report per-trader diagnostics; per-trader parameter forks only if a trader's validation persistently diverges *and* their sample crosses a significance floor (≥ ~100 trades) — otherwise idiosyncrasy is handled by the SL/TP-per-cluster study, not by forking signal configs.
6. **Sample size / pooling / significance.** Synthetic labels: ~10⁵–10⁶ per asset — ample. Simulated trades: enforce ≥30/fold or the fold is inconclusive. Real trades: pooled across traders per asset with per-trader breakdown and binomial CIs always displayed; cluster-level SL/TP findings require n≥25 per cluster to ship, else the cluster inherits its parent regime's values. Cross-config significance: Wilcoxon on paired folds + block-bootstrap CIs (§2.10).
7. **Transaction realism.** Time-of-day spread curves from recorded ticks (Capitaria where available; logger collects going forward), ×2 news stress; slippage = 0.5×median spread/side baseline refined from real fills; commissions/swap from real exports; session gates per asset; news buffers from the shared calendar. All costs inside the label barriers *and* the trade simulator, so nothing wins on friction it wouldn't survive. (§2.7.)
8. **Multi-asset generalization.** One `InstrumentConfig` per asset is mandatory and sufficient. **Shared:** engine code, indicator formulas, scoring semantics, fusion logic, regime taxonomy, objective, validation protocol, report format. **Per-asset:** symbol basket, expected-corr signs/gates (magnitudes empirical, §2.5-G5), asset weights, TF weights, thresholds, session hours, SL/TP multipliers, regime overrides. Sprawl control: single YAML per asset, regime handling as deltas, empirical (not hand-set) correlation magnitudes, and the registry diffing any variant against production so drift is always visible.
9. **Search method.** Per lever group (§2.5 table): TPE (Optuna) for continuous/mixed medium-dimensional groups (indicators, macro dynamics, sub-weights); exhaustive small grids where the space is tiny and cross-asset comparability matters (composite weights, thresholds, TF subsets); analytic MAE/MFE sweep (not search) for SL/TP; coordinate-block staging across groups; a final narrow joint TPE polish; 200-trial random floors as no-signal detectors. Evolutionary methods discarded (no advantage at 10³-trial budgets); Bayesian-GP discarded in favor of TPE (categorical/integer levers, Optuna's pruning + storage + parallelism are free wins).
10. **Reproducibility & reporting.** Study YAML pins seed, git commit, data-manifest hash; variant ID = config sha256; SQLite registry (studies/variants/runs/metrics) + Parquet artifacts + auto-generated HTML report per study with leaderboard, fold stability, regime heatmap, winner-vs-production parameter diff, holdout verdict, and the exact reproduction command. One command reruns any study bit-identically. (§2.10.)

---

## 5. Strategies / EAs from optimal SL/TP (brief, no code)

All are **exit-management EAs** layered on trades the human (or SENTINEL signal) opens — consistent with SENTINEL's read-only ethos; the EA is a separate, opt-in MT5 component. Ordered by evidence-strength expected from §2.8:

1. **ATR-anchored bracket EA.** On position open, set SL/TP to the per-regime optimal multipliers (e.g., SL 1.25×ATR(14,M5), TP 2.5×ATR) from the study's cluster table, keyed by symbol + regime + direction. The simplest, most robust productization of the SL/TP study; zero discretion.
2. **Breakeven-then-chandelier trailer.** At +1R, move SL to entry ± spread; thereafter trail at k×ATR below/above the favorable extreme (chandelier). Directly testable on recorded MAE/MFE paths; typically the best expectancy-preserver for scalps that run.
3. **Structure-trail EA.** Trail SL to the most recent confirmed swing (the `levels_engine` swing detector) or the nearest Camarilla level beyond price; TP at next opposing level. Marries exits to the S/R logic traders already watch; slightly more parameters (level tolerance).
4. **Time-stop scalper guard.** Flat any position that hasn't reached +x R within N minutes (per-cluster optimal N from hold-time analysis), and hard-flat at session close. Targets the study's likely finding that stale scalps are net losers.
5. **Regime-switched risk EA.** One EA that reads the day's regime file (published by the engine) and applies the matching bracket/trailing profile — the productized form of §2.9's regime deltas; the natural end-state that subsumes 1–2.
6. **Signal-degradation exit (later).** Close/half-close when the live composite crosses back through neutral against the position — requires the EA to read SENTINEL's snapshot (local file/socket); highest coupling, prototype last.

---

## 6. Phased implementation plan (agent-driven, startable now)

**Phase 0 — Foundations & quick wins (days 1–3).** (a) Golden-master capture + parity test harness (§1.3). (b) Fix the two code defects behind flags: guard/remove the `CorrelationEngine` import; set replay `normalize_macd=True`. (c) Regenerate the AI context numbers from config (kills the 75/25 prompt lie even before the full refactor). (d) Stopgap UI relief: move the compute into a background thread + `st.fragment` partial rerun on the existing Streamlit app (buys breathing room on trader laptops while the real stack lands). (e) Start the **native tick + snapshot logger** immediately inside the current app — every day it runs is data for spreads and replay. *Milestone: parity harness green; loggers writing; traders feel a first improvement.*

**Phase 1 — Headless core extraction (days 3–8).** `sentinel_engine/` per §1.4: `InstrumentConfig` (three YAMLs generated from current `config.py`), parameterized `MacroScorer`, `Feed` protocol, `Engine.step() → Snapshot`, snapshot schema + AI-context renderer. Parity tests pass on golden masters for all three instruments; `instrument_panel`'s inline macro copy deleted. *Dependency: Phase 0a. Milestone: one code path per computation, config-hash in output.*

**Phase 2 — Data lake + point-in-time replayer (days 6–12, overlaps P1).** Dukascopy + MT5 ingestion, Parquet lake + manifests, `HistoricalFeed(as_of)`, `TimelineAligner`, trade ingesters (XTB/MT5 adapters with schema-validation reports), replayer streaming snapshots, fidelity experiments documented. *Milestone: one command replays any asset over any range, leak-free, at ≥1k steps/s.*

**Phase 3 — Optimization engine, first study (days 10–18). THE CENTER.** Trade simulator + cost models; triple-barrier labeler; objective evaluator; Optuna integration; walk-forward driver; run registry + HTML reports; regime labeler v1. Run **Study #1: XAUUSD** (current main instrument) through stages G4→G2/G3→G5→G1, then **Study #2: NQ100**. *Milestone: persisted comparable reports; candidate configs beating production out-of-sample or an honest null result.*

**Phase 4 — New UI stack (days 14–22, overlaps P3; different agent lane).** FastAPI service + WebSocket snapshot stream + static frontend reproducing v1/v2 panels via one parameterized panel component; source/staleness badges; side-by-side visual+numeric parity sign-off vs Streamlit; launcher step-8 switch; Streamlit retired after a 1–2 week dual-run. *Dependency: P1. Milestone: traders on the light UI, identical numbers, config hash visible.*

**Phase 5 — Replay tab + SL/TP study (days 20–28).** ReplaySession + cursor UI + spread override + variant selector + checkpointed seeks; trade enrichment + MAE/MFE clustering study; per-cluster SL/TP + trailing tables; regime deltas (G7) fitted and shipped as YAML overrides; regime-aware SL/TP surfaced in the live UI. *Dependencies: P2 (lake), P4 (frontend). Milestone: traders can scrub history and see exactly what SENTINEL showed; SL/TP recommendations regime-aware.*

**Phase 6 — AI assistant revamp (days 24–30).** `models.yaml` + models-API refresh; chat endpoint on the service; snapshot-based context with positions/regime/calendar/trajectory; PositionWatcher auto per-trade chat (toggle); news countdown strip; usage governance. *Dependency: P4 (service), calendar feed. Milestone: assistant live with key, per-trade auto-briefs working.*

**Phase 7 — Retune lifecycle (day 30+, recurring).** Monthly scheduled study runs; approval workflow; YAML shipping via existing launcher updates; backlog: intra-bar tick replay, incremental indicators, SPA tests, EA prototypes (section 5, order 1→2→4), per-trader forks if warranted.

Critical path: P0a → P1 → P2 → P3. UI (P4) parallelizes after P1. Nothing waits on the XTB schema except trade-validation parts of P3 — everything else proceeds on synthetic labels.

---

## 7. Strengths, blind spots, and improvement map (Part G)

**Strengths (confirmed and exploited by this design).** Genuinely modular scoring layers whose semantics port cleanly into a headless core; the per-instrument macro parameterization already proven (the panel's inline copy demonstrates the math generalizes — it just lives in the wrong place); strict read-only broker posture (keeps every extension low-risk and lets EAs be a separate opt-in component); the launcher's git-update channel is a ready-made **parameter-distribution mechanism** for optimized configs; the existing replay+compare backtester, though broken in one path, encodes the correct *intent* (score-vs-real-trade comparison) that survives as validation Layer 3; the AI context builder is a near-complete inventory of "what the assistant needs" and only its *generation mechanism* is wrong.

**Blind spots / fragilities (beyond the brief's list, with disposition).**
- The **EWMA tracker's path-dependence** is an unacknowledged consistency and replay-fidelity issue even after the stack fix: its state depends on sampling cadence. Disposition: cadence pinned in the engine loop, state serialized (checkpointing), fidelity experiment quantifies tick-vs-M1 stepping (§2.3).
- **`h4_direction` = M15 direction** and other legacy naming will mislead future optimization work; renamed in the snapshot schema with a compat alias.
- **RSI momentum-zone always votes** (never 0 between 30–70) biases the direction tally toward whatever side of 50 RSI sits — flagged as a lever-adjacent semantic to examine in the *separate* tuning one-shot, not changed here (behavioral contract).
- **Synthetic Yahoo spread (0.1%)** and silent MT5→Yahoo degradation can materially distort what a trader sees; the new UI badges source and staleness loudly. BUT since yahoo finance will be dropped due to its ~10m delay with reltime. 
- **VIX and copper history sourcing** are the weakest data-lake links (§2.2); mitigated by daily backfill + forward tick logging, and by reporting macro-input coverage per study so no optimization silently runs on thin cross-asset data.
- **CRLF/LF churn** across the repo pollutes diffs and the launcher's MD5-change self-relaunch logic; fix with `.gitattributes` (`* text=auto eol=lf`, `.bat eol=crlf`) early in Phase 0.
- **Secrets hygiene:** plaintext demo password in `CUENTAS.md` (untracked but on-disk) and API keys typed into the UI; move to env/DPAPI-encrypted store in Phase 6.
- **No tests exist today** for any scoring semantics — the golden-master harness is the first and pays for itself immediately.
- **Sparse real-trade samples** are the program's fundamental statistical constraint; the design leans on synthetic labels deliberately, and every report must keep saying so where it binds.

**Where the biggest gains live, ranked by value/effort:** (1) native snapshot+tick logging — near-zero effort, compounds daily, unblocks spreads/replay/validation; (2) core extraction + parity harness — unlocks every axis and permanently kills the replay-vs-live and prompt-vs-code drift classes; (3) the staged optimizer with honest validation — the traders' #1 ask, and the registry makes every future retune cheap; (4) the stack swap — largest perceived improvement for traders; (5) regime deltas + MAE/MFE SL/TP tables — the most likely source of realized-PnL improvement given that exits, not entries, are where retail scalping PnL is usually lost; (6) the assistant revamp — high delight, modest engineering, fully decoupled.

---

## Open questions for the team (would sharpen a second pass)

None of these block the design; assumptions above cover them. Answers would tighten Phases 2–3.

1. **XTB export schema:** one sample file (anonymized) — exact columns, timezone of timestamps, partial-close representation, and whether SL/TP *as set* (not just fills) are included.
2. **MT5/Capitaria history depth:** how far back `copy_rates_range` M1 (and `copy_ticks_range`) actually returns for XAUUSD, NQ100, USDCLP, and the macro basket on your account — determines how much of the lake can be broker-exact.
3. **Trading sessions for XAUUSD/NQ100:** do traders keep CLT day-session hours (assumed), or trade other windows? Session gates and spread curves depend on it.
4. **Trade volume/frequency reality:** rough count of real trades per trader per asset (last 6–12 months) — calibrates how much weight real-trade validation can bear and whether per-trader forks are ever in play.
5. **Dev-machine spec** (cores/RAM) and tolerance for installing Node (dukascopy-node) — affects study wall-times and the ingestion tool choice.
6. **Calendar source preference:** is a weekly-refreshed scraped ForexFactory calendar acceptable, or do you have a preferred free feed for the news buffers/countdowns?
7. **Anthropic budget ceiling** per trader/month for the assistant — sets the default model tier and the auto per-trade-chat default model.
