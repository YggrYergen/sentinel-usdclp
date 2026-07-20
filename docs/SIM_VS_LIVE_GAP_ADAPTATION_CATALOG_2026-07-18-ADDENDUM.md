# Addendum — Verification Corrections, P6b, and Implementation-Readiness Annex

**Date:** 2026-07-18 · **Amends:** `docs/SIM_VS_LIVE_GAP_ADAPTATION_CATALOG_2026-07-18.md`
**Method:** 2 additional Sonnet 5 read-only investigators — (C) adversarial verification of the catalog's feasibility claims against source; (D) data + tooling readiness audit for the honest re-sweep. Fact bases: `scratchpad/verify_C_feasibility.md`, `audit_D_resweep_readiness.md`.

---

## 1. Corrections to the catalog (verification results)

### 1.1 P1 is NOT a one-kwarg change — it is a small, testable code change ⚠️

Verified: `simular_variant` accepts `live_fill_mode=True` + `return_state=True` together without crashing, **but** the returned `open_state["sl"]` (`emasar_variant.py:812`) always reports the classic look-ahead `f.sl`, never `server_sl_by_tag` — so an executor flipped to the honest oracle would still emit MODIFYs targeting **one-bar-ahead SL levels**. The honest oracle requires:
- the `return_state` snapshot to report the server-side SL when `live_fill_mode=True` (a few lines), and
- **new tests**: no test in the repo covers `return_state=True` + `live_fill_mode=True` (the exact executor combination); `tests/live/test_reconciler.py` has zero `live_fill_mode` references.

**Safety-net finding (cuts both ways):** golden parity (`tests/golden/test_parity.py`) covers `Engine`/`emasar_ref`, NOT `simular_variant` — the trading hot path has no parity protection. Changes here can't break the sacred gate, but nothing catches regressions either. Any P1 work must ship with its own pinned-behavior tests.

### 1.2 Shadow infrastructure: "near-supported" is REFUTED — it is new code (as D103's own row anticipated)

- `--configs` resolves only within `CONFIGS_20` (unknown IDs → exit 2); magics hardcoded 720010–720200.
- **A second executor process is impossible by design**: `watchdog_local.ps1:207-218` force-kills any second `run_live_20` by command-line substring match (deliberately — "DUPLICATE armed executors → double orders"), and `MAX_FICHAS_TOTAL=60` is per-process.
- Therefore shadows MUST run **in-process**: a `CONFIGS_SHADOW` list (magics 721000+), `--configs live+shadow` resolution, and cap management. Real, bounded work — but work.

### 1.3 TP legs (P11/P14): sim-side exists and is tested; executor-side is new code (not dormant code)

`f1_tp_r/f2_tp_r/f3_tp_r` are implemented and tested in the sim (R = distance to the initial range-SL). But **no `tp` key exists in any MT5 request dict** and the reconciler `Action` has no `tp` field — executor TP support must be written, not enabled.

### 1.4 The +$145.77 replay figure is friction-free

The 2026-07-15 signal-replay's live-fill PnL subtracts no spread/slippage. At ~110 round-trips × ~$0.50 measured toll ≈ −$55 ⇒ realistically **≈ +$90** for that window. Still positive — the honest-oracle direction survives friction on that day — but the catalog's P7 rationale should quote ≈ +$90, not +$146.

### 1.5 Confirmed exactly (no correction needed)

- The `$0.01/oz` modulated-trail arithmetic (pip_size 0.01 × 100 pips × factor 0.01). The look-ahead-harvest interpretation stands.
- REJECT_CAP: logged, never silent; cap shared correctly across configs in one process.
- No pending-order support anywhere (`TRADE_ACTION_DEAL` + `TRADE_ACTION_SLTP` only; no `orders_get()`): P21/P22/P25 are built-from-scratch items.
- Cycle loop is a bare `time.sleep(interval)`; no bar-close scheduling exists anywhere (P24 is small but from scratch).

### 1.6 New landmines (for any implementation plan)

1. **Compute budget per cycle:** each config re-simulates a `DEFAULT_WINDOW=10,000`-bar window every 15 s. 4 live + 16 shadow configs in one process multiplies this ×5 — needs measurement (throughput benchmark says ~23k bars/sec ⇒ ~20×10k bars ≈ 8-10 s/cycle single-threaded: **near the 15 s budget; must be profiled before Wave 1 sizing**).
2. `sl_tol=0.05` (MODIFY-thrash tolerance) must be revisited by any proposal that changes SL movement granularity (P6b especially).
3. The watchdog's orphan-reaper matches the substring `'run_live_20'` with no argument discrimination — relevant to any tooling that runs the module ad hoc on a machine with the watchdog active.

---

## 2. NEW PROPOSAL — P6b: Tick-trailing executor (per-second server-SL ratchet)

*Origin: user insight 2026-07-18 ("maybe the calculations of when to close a position might be useful to do every second"). Formalizes and supersedes the latency-only reading; already foreshadowed by D90 ("modo trailing-por-ticks si los ticks validan").*

**What:** a per-second (or tick-event) loop that, for each open ficha: tracks live `max_fav` from the tick stream → computes `new_sl = max_fav − trail` → sends MODIFY **only when** the improvement exceeds a threshold (≥ broker stops-level, or ≥ $0.10). Entries stay bar-based; the *exit level* becomes intra-bar.

**Why it should work (mechanism):** the classic sim's "optimism" is precisely a zero-latency intra-bar trail — and a continuously-ratcheted **server-side SL is the honest implementation of that exact behavior**. Price makes a high → SL ratchets behind it → retrace fills the resting stop (broker fill fidelity measured perfect, 9/9 at the installed level). This converts part of the −957 same-bar component from fantasy into legitimately capturable PnL. Reality is bounded by the two curves already computed: live-fill floor (−253) and classic ceiling (+704).

**Hard constraints (built into the design):**
- `trade_stops_level`: trails tighter than the broker minimum cannot exist server-side (also the second independent proof that factor-0.01 trails were unimplementable). The base trail must sit above this floor → pair with P8 (wide-trail floor).
- MODIFY throughput: per-second × up to 60 fichas = untenable naive rates; the improvement-threshold gate + per-ficha rate cap are mandatory. One night at *bar* cadence already produced 99 failed MODIFYs (10016).
- Path ambiguity: OHLC cannot reveal how much classic edge came from favorable intra-bar ordering. **Validation gate: P4 tick replay sizes the recoverable fraction BEFORE build** (available for 2026-01→07; see §3).
- `sl_tol=0.05` re-tune (see §1.6.2).

**Validation path:** P4 tick replay of recorded live days (ground truth = actual deals) → paired shadow twin vs a P6 (bar-cadence) twin, same config, same days.
**Risk:** medium-high engineering; broker/IPC rate limits; fast-market slippage on stop fills (measured so far: zero, but sample = 9).

---

## 3. Implementation-Readiness Annex (what exists vs what must be built)

### 3.1 Data readiness (verified on disk)

**Bar lake (`data/lake/manifest.json` + tier files):**

| Window | M1 | M2 | M5 | M15 |
|---|---|---|---|---|
| IW 2026-06-08→07-07 | ✓ | ✓ | ✓ | ✓ |
| W1 2026-05-04→06-05 | ✓ | ✓ | ✓ | ✓ |
| W2 2026-03-02→04-03 | ✓ | ✓ | ✓ | ✓ |
| W3 2025-10-01→11-01 | ✗ | ✗ | ✓ | ✓ |

(Lake starts: M1 2026-03-25 · M2 2025-12-10 · M5 2025-02-04 · M15 2022-03-31.)

**Ticks:** real `.tkc` cache for XAUUSD **2026-01→2026-07 only** (16–58 MB/month, under `MT5_Portable/Bases/Capitaria-All/ticks/` + two tester dirs). No W3 ticks (fresh Capitaria download needed if ever required). **No repo-friendly tick format exists** — P4 requires a `.tkc` loader (or an MT5-side export) before any tick replay.

**Spread:** confirmed zero historical spread data; the only "spread" anywhere is the flat `SPREAD = 0.5` constant. P3 (live capture) is the only path to a real distribution.

### 3.2 Tooling readiness — the P2 harness ALREADY EXISTS ✅

`scripts/report/gen_livefill_bound.py` (418 lines) already drives `simular_variant` with `live_fill_mode=True` across all 4 windows — it produced the D90 study (13 configs × 4 windows = 51 cells, raw JSON at `scripts/report/livefill_bound_raw.json`). It reuses the batch scripts' mode-agnostic helpers (bar loader, spread-at-fill, metrics) via importlib **without modifying them**.

**What P2 actually needs (much less than "re-write the program"):**
1. Replace the hardcoded 13-config `CONFIGS` dict with a lever-grid generator (the catalog's Tier A/B grids: trail floors, ac_modulate on/off, TP/BE grids, confirmation, cooldowns, gates).
2. Adopt the P5 metric (net_honest with per-hour friction once P3 data exists; flat 0.5 until then, stated as such).
3. Persist all cells to `data/research.db` (the first run persisted only 4/51 — rest live in raw JSON).
4. Compute is cheap: ~23,000 bars/sec measured ⇒ a 4-window grid of hundreds of variants is minutes-to-hours, not days.

### 3.3 Per-proposal readiness table

| Proposal cluster | Sim side | Executor side | Data needed | Verdict |
|---|---|---|---|---|
| P1/P7 honest oracle | small change (`open_state` server-SL) + NEW tests | one kwarg after sim fix | none | **small, must be tested — hot path has no parity net** |
| P2 honest re-sweep | harness EXISTS (extend grid) | n/a | lake ✓ (W3: M5/M15 only) | **ready to start** |
| P3 spread capture | n/a | small (log tick bid/ask per cycle) + lake column | produces the data | **small, start Sunday** |
| P4 tick replay | NEW (.tkc loader + tick evaluator) | n/a | ticks ✓ 2026-01→07 | **medium build; gates P6b/P22/P25** |
| P6 server-SL-only / P6b tick-ratchet | P6: config; P6b: NEW loop | P6: remove same-bar close; P6b: NEW ratchet + threshold gate | P4 first | **P6 small / P6b medium-high** |
| P8/P9/P10/P13 trail & exit variants | config/kwargs (exist) | none (flow through oracle) | P2 ranks them | **cheap — pure P2 grid rows** |
| P11/P12/P14 TP & BE | sim EXISTS+tested | NEW: `tp` in Action + requests, TP MODIFY path | P2 first | **executor work is real but bounded** |
| P15–P20 churn/gates | mostly config/new small levers | in-process CONFIGS_SHADOW required | P19/P23 need P3 | **blocked on shadow infra** |
| P21/P22/P25 pending orders | n/a | NEW order types + `orders_get` tracking + reconciler states | P4 first | **largest executor build in catalog** |
| P24 event-driven cycle | n/a | small, from scratch | none | small |
| P30 loss budgets | n/a | small executor rule | replay calibration | small |
| Shadow infra itself | `CONFIGS_SHADOW` + magics 721000+ | `--configs` extension + cap mgmt + **cycle-time profiling** (§1.6.1) | n/a | **prerequisite for every live shadow; new code** |

### 3.4 Revised recommended sequence (effort-honest)

1. **This weekend (no market):** P2 grid extension on the existing harness (**the real Wave 0** — compute only) · P5 metric · P1 sim-side fix + tests (small).
2. **Sunday pre-open:** P3 spread capture deployed (telemetry only, zero risk) · P24 if trivial.
3. **Week 1:** shadow infra (in-process CONFIGS_SHADOW — the gating build) + cycle-time profiling → Wave 1 shadows from P2's league table (P7, P9, P8, P28, P15 twins) + P30 budgets.
4. **Week 2+:** P4 tick loader → P6b verdict (sized before built) → TP executor support (P11/P14) if P2 ranks them → pending-order research track (P22/P25).

---

*All §1 verdicts and §3 inventories verified by investigators C and D and spot-confirmed by the orchestrator; primary evidence in the two scratchpad fact files. Corrections stand as the authoritative reading where they conflict with the main catalog.*
