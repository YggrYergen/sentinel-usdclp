# Live deployment of the curated 20 — recon, design lock-in, and blockers
Date: 2026-07-13 · Branch: `alvaro` · Account of record: **DEMO 2883015767** (per `CUENTAS.md`)

## TL;DR
- **Legacy set identified:** 39 chart instances of the MQL5 EA **`TOKATA_Sapitos_v3`** (an ORB/London-breakout strategy — NOT EMASAR), all XAUUSD/M5, in the MT5 profile `FORWARD39`. Not Python forward sessions.
- **The 20 configs were validated, audited, and parity-tested** against `simular_variant` — the only in-repo engine with the required levers. Zero config drift; 6/6 new tests pass; full gates green (parity 3/3, strategies 62/62, service = the 3 known pre-existing failures only).
- **HARD BLOCKER to "going live":** the live path is MQL5-on-charts, and **no executor exists that supports the winning levers.** The shipped `TOKATA_EMASAR_v1.mq5` supports none of them (trails F3 only, fixed-pip SL, no ac_modulate factor / no reentry / no sar_adaptive / no range-SL / no direction mask). There is **no Python order path at all** (`run_service.py` and `deals_watcher` are strictly read-only; **there is no `guard_cuenta.assert_demo` in Python** — only the MQL5 mirror `Riesgo.mqh`). Deployment therefore cannot be completed on disk within the ATTACH-ONLY / NEVER-LAUNCH / no-chart-editing rules. See **Blockers & required user action**.

---

## Phase 0 — Recon

### Account verification
`CUENTAS.md` is the single source of truth. Only **DEMO 2883015767** (portable `D:\FOREX\MT5_Portable`) is tradable; REAL 2883011573 is read-only investor. **No MT5 terminal was launched or interacted with** (ATTACH-ONLY honored). I could not verify a *live* logged-in account because no terminal was attached during this session and launching is forbidden — the portable terminal's `Riesgo.mqh` guard hard-whitelists only `2883015767` and returns `INIT_FAILED` on any non-DEMO login, which is the enforced safety net at EA init.

### How live strategies actually run
- **Not** Python forward sessions. The `forward_session` + `trade` rows in `data/research.db` are an **ingest/audit artifact** — historical TOKATA CSV ledgers imported from `D:\WebDev\TOKATA\backtest_results\forward_positions_ledger.csv` (see `sentinel_engine/ingest_tokata/forward.py`; sessions keyed `FWD::<variante>`, `estado='forward'`, all timestamps NULL). They are backtest records, not live controllers.
- `magic_allocation` has only **2 rows** (a `smoke` test magic and one `emasar` repro magic) — it is a deals-attribution lookup for `deals_watcher`, **not** a live-strategy roster.
- **The live path is MQL5 EAs attached to charts** in the DEMO portable terminal, driven by whichever chart profile the user loads. The active legacy profile is **`FORWARD39`** (`MT5_Portable/MQL5/Profiles/Charts/FORWARD39`).

### Legacy inventory (retire target)
Enumerated by parsing the 43 `.chr` files in `FORWARD39`:

| Charts | EA | Symbol | TF | Magics | Vol |
|---|---|---|---|---|---|
| chart01–39 (39) | **`TOKATA_Sapitos_v3`** | XAUUSD | M5 (`period_type=0, period_size=5`) | bands 330xxx / 334xxx / 335xxx (per-instance `MagicOverride`, e.g. 330201–330212, 334002–334056, 335001–335013) | 0.10 (two at 0.20) |
| chart40–43 (4) | none (indicator/Market-Overview panels) | NQ100/XAUUSD | — | — | — |

So the "~36–39 legacy strategies" = **39 `Sapitos_v3` instances**. (Matches the user's own inventory doc: *"Sapitos — best in backtest, but red in live."*)

**Lever-support gap (as anticipated by the brief):** the winning configs' levers exist **only** in `sentinel_engine/strategies/emasar_variant.py::simular_variant`. The one EMASAR EA on disk (`TOKATA_EMASAR_v1.mq5`) implements a *different, older* exit model (F1 engulfing, F2 SuperTrend-flip, F3 single-distance trail, fixed-pip init SL) and exposes none of: per-ficha flat ladder 100/100/100, `ac_modulate_factor`, `reentry_*`, `sar_adaptive`, range-SL `k`, `require_ema_order=False`, direction mask, or blocked hours.

---

## Phase 1 — Retire the legacy set
**Not performed as a mutation, by design + safety.** The sanctioned retire mechanism for chart-attached EAs is *not touching a Python config or DB row* — it is the MT5 terminal removing the EAs from the charts (or loading a different profile). That requires driving the terminal, which is **forbidden** (ATTACH-ONLY / NEVER-LAUNCH), and the `.chr` files are binary MT5 session state that must not be hand-edited. **No history was deleted; nothing was disabled on disk.** Retirement is a user action (below).

**Open positions:** cannot be inventoried — no terminal was attachable this session (launching forbidden), and `deals_watcher` only reads history when `terminal64.exe` is already running. The user must read open positions from the DEMO terminal directly (see below). **No position was closed** (and none could be).

---

## Phase 2 — The 20, implemented as validated design specs
Because there is no lever-complete executor to deploy into, the 20 are implemented as the **single source of truth** in `sentinel_engine/strategies/live_configs_20.py` (`CONFIGS_20`): each config is the literal `simular_variant(**kwargs)` argument set — the only engine where every lever is real and golden-tested. This makes the 20 "implemented and tested against the backtested design" at the design layer, ready to drive whichever executor is built/wired next.

Mapping notes:
- Spec `init_sl_mode='range'` → `simular_variant` is **always** range-SL via `init_sl_range_k` (no separate mode flag); per-TF k = M1:6.0, M2:3.0, M5:6.0, M15:2.5.
- `#14/#15` direction filter → `direction_mask` (SuperTrend(14,3.0) on previous CLOSED M15 bar), computed by the caller at run time; flagged `direction_filter=True`.
- `#20` blocked server hours {0,6,16,18,23} → `blocked_hours` frozenset inside kwargs.
- **No fallback substitutions were needed** — the direction filter (#14/#15) and hour blocking (#20) are natively supported by `simular_variant`, so all 20 as specified are represented (fallback rule not triggered).

### Config audit dump (programmatic, zero drift vs. spec table)
```
ID             TF   k    ac  factor reent adapt dir blkhrs
SS-M2          M2   3.0  Y   0.01   Y     Y     -   -
V06D-M2        M2   3.0  Y   0.01   -     -     -   -
V15-M2         M2   3.0  Y   0.25   -     Y     -   -
SS-M5          M5   6.0  Y   0.01   Y     Y     -   -
V06D-M5        M5   6.0  Y   0.01   -     -     -   -
V13-M5         M5   6.0  Y   0.25   Y     -     -   -
SS-M15         M15  2.5  Y   0.01   Y     -     -   -
V13-M15        M15  2.5  Y   0.25   Y     -     -   -
V06D-M15       M15  2.5  Y   0.01   -     -     -   -
V06C-M5        M5   6.0  Y   0.10   -     -     -   -
V06C-M15       M15  2.5  Y   0.10   -     -     -   -
V06B-M15       M15  2.5  Y   0.25   -     -     -   -
V15-M15        M15  2.5  Y   0.25   -     Y     -   -
V10-M5         M5   6.0  Y   0.25   -     -     Y   -
V10-M15        M15  2.5  Y   0.25   -     -     Y   -
V13-M2         M2   3.0  Y   0.25   Y     -     -   -
V09-CTRL-M5    M5   1.0  N   -      -     -     -   -
V09-CTRL-M15   M15  1.0  N   -      -     -     -   -
SS-M1          M1   6.0  Y   0.01   Y     Y     -   -
V11-M2         M2   3.0  Y   0.25   -     -     -   [0, 6, 16, 18, 23]
```
Skeleton pinned for all (audit test): confirm_mode=1, confirm_count=2, require_ema_order=False, ema_fast=8, ema_slow=20, sar_step=0.3, sar_max=0.3, f1/f2/f3_trail_pips=100, symbol=XAUUSD. Adaptive pairs where enabled: sar_fast=(0.3,0.3), sar_slow=(0.005,0.05), vol_regime_window=200. Lot sizing: the live convention is **0.10 / ficha** (matches `Volumen=0.10` on the legacy Sapitos charts and `TOKATA_EMASAR_v1`'s `Volumen=0.10` default) — carried as an executor input, not a `simular_variant` param.

---

## Phase 3 — No-deviation verification
`tests/strategies/test_live_configs_20.py` (6 tests, all pass):
1. `test_exactly_20_unique` — exactly 20, unique ids, id set == spec set.
2. `test_config_audit_no_drift` — every field (TF, k, ac/factor, reentry, adaptive pairs+window, blocked_hours, direction flag, full skeleton) diffed against the spec table → zero mismatches.
3. `test_all_20_runnable_wellformed` — all 20 run on a deterministic synthetic series; every event has a valid motivo/side.
4. `test_parity_three_lever_configs_are_the_engine` — SS-M5 (adaptive+reentry+f0.01), V06D-M15 (plain f0.01), V13-M2 (reentry+f0.25): config-driven run == direct `simular_variant` call, **event-for-event**. (The "live decision path" *is* `simular_variant` here — no second engine exists in-repo, so parity is pinned at the config layer.)
5. `test_v11_blocked_hours_active` — V11-M2 fires zero entries in {0,6,16,18,23} and never more entries than the unblocked variant.
6. `test_v10_direction_mask_filters` — V10 configs are long-only under +1 mask, short-only under −1 mask.

**Dry-run:** the sanctioned dry-run (order routing to DEMO with a verified `assert_demo` guard) **could not be exercised — that Python path does not exist.** The runnability test above is the closest in-repo equivalent (all 20 load, compute signals, emit a well-formed event stream). No live orders fire (correct — there is no order path).

### Gates
- `tests/golden/test_parity.py` — **3/3 pass**.
- `tests/strategies` — **62/62 pass** (56 pre-existing + 6 new).
- `tests/service` — **471 pass, 3 fail**, and those 3 are the known pre-existing failures (`test_chat.py::test_review_strategy_happy_path_sse_sequence`, `test_web_positions.py::…analizar_button…` ×2) in files this task must not touch and did not touch.

---

## Phase 3.5 — LIVE shadow-parity checker (protocol addition, 2026-07-13)

### What it is
`scripts/live/check_live_sim_parity.py` — a **read-only** tool that verifies, post-deployment, that each live config took THE SAME POSITIONS `simular_variant` would have taken on the same market data:
(a) bars from the Parquet lake (`data/lake/XAUUSD/<TF>/YYYY-MM.parquet`, `t,o,h,l,c,v` schema — the same source the service consumes); (b) re-runs `simular_variant(**config.kwargs)` on those bars (V10 configs get their SuperTrend-M15 `direction_mask` computed via `scripts/report/gen_variant_batch5.compute_direction_mask`); (c) live deals from `deals_raw` in `data/research.db` (populated by `DealsWatcher` from DEMO 2883015767), matched by the config's **magic band**; (d) diffs entries (bar-level timestamp, side, price with tolerance = spread + 1 tick, ficha count) and exits (bars + prices).

**Magic assignment (new, in `live_configs_20.py`):** each config now carries `magic` = 720000 + 10×position → 720010 (SS-M2) … 720200 (V11-M2); fichas use the TOKATA offset convention (base+1/+2/+3 = F1/F2/F3), so the checker matches deals with `magic BETWEEN base+1 AND base+3`. Band collides with nothing (legacy Sapitos 330xxx/334xxx/335xxx, EMASAR EA 710000, IA 900000-999). **The deployed executor MUST use these magics** or attribution/parity is impossible.

### Divergence taxonomy
- **HARD (fail, exit code 1):** `MISSED_ENTRY` (sim entered, live didn't), `EXTRA_ENTRY` (live entered where sim didn't), `SIDE_MISMATCH`, `ENTRY_PRICE_OUT_OF_TOL` / `EXIT_PRICE_OUT_OF_TOL` (|live−sim| > spread+tick), `FICHA_COUNT`, `EXIT_BARS_MISMATCH`, `LIVE_ENTRY_OUTSIDE_BARS`.
- **Acceptable (classified, reported, never fail):** `ENTRY_PRICE_WITHIN_TOL` / `EXIT_PRICE_WITHIN_TOL` — live spread vs. the flat 0.5 model + slippage ≤ tolerance (default tol = 0.5 + 0.01 = 0.51 for XAUUSD; `--spread/--tick` configurable). Also by construction: same-bar timing jitter (matching is bar-level, live fills land inside the signal bar); weekend/holiday gaps (both sides read the same lake, missing bars vanish identically); partial fills (multiple IN deals of one position aggregate to a single volume-weighted entry).

### How to run (exact commands)
```
# one config, one day:
python -m scripts.live.check_live_sim_parity --config SS-M5 --start 2026-07-14 --end 2026-07-15

# all 20 at once (+ machine-readable dump):
python -m scripts.live.check_live_sim_parity --config all --start 2026-07-14 --end 2026-07-15 --json parity_2026-07-14.json
```
Exit codes: **0** = all MATCH (tolerated diffs OK) · **1** = ≥1 hard divergence (automatable gate) · **2** = usage/data error (unknown config, no bars in lake for the window). Smoke-verified end-to-end against the real June lake (correctly reports every sim entry as `MISSED_ENTRY` while nothing is deployed, exit 1) and `--config BOGUS` → exit 2.

### Acceptance protocol (post-deployment)
1. Deploy the 20 (with the assigned magics), let them run for a full session/day with the DEMO terminal open (DealsWatcher must be polling so `deals_raw` fills).
2. Run the all-20 command above for that day.
3. **Any config with verdict DIVERGENCE (any HARD item) is suspended immediately** (remove its EA from the chart) and investigated before it may resume. `*_WITHIN_TOL` items are acceptable and only reported.
4. Repeat daily for the first week; thereafter the non-zero exit code can drive an automated alarm.

### Checker self-test
`tests/scripts/test_check_live_sim_parity.py` (6 tests, all pass): builds a synthetic "recorded-live" deals dataset from the simulator's own event stream (perfect replay with half-spread fills) → MATCH with `WITHIN_TOL` classifications only; then **injects** (i) a dropped live entry → `MISSED_ENTRY` HARD caught, (ii) a rogue live position on a non-signal bar → `EXTRA_ENTRY` HARD caught, (iii) a fill 5.0 off → `ENTRY_PRICE_OUT_OF_TOL` HARD caught. Pure-core (`diff_config`) is injectable — no DB/lake/network in tests.

---

## Blockers & required user action (to actually go live)
The design is locked and verified; **execution is blocked on a missing lever-complete executor**, which cannot be built/deployed within this session's safety rules. To go live:

1. **Decide/build the executor.** The 20 need an EA (or a future *guarded* Python bridge) that implements `simular_variant`'s exact semantics: per-ficha flat ladder 100/100/100, `ac_modulate` × factor, controlled reentry (armed only when all 3 fichas exited via EXIT_TRAIL with SAR trend intact), volatility-adaptive SAR, range init-SL with per-TF k, `require_ema_order=False`, SuperTrend-M15 direction mask, blocked hours. `TOKATA_EMASAR_v1.mq5` does **not** qualify and must not be used as-is. Building/compiling a new EA is a separate, sizable workstream (and MQL5 compile/attach needs the terminal — a user step).
2. **Open the DEMO terminal** (`MT5_DEMO_TOMAS.bat` → portable, login 2883015767) and **inventory open positions** of magics 330xxx/334xxx/335xxx. Report them; do **not** close them unless you decide to.
3. **Retire the legacy Sapitos set** from *new* entries by removing `TOKATA_Sapitos_v3` from its 39 charts (or loading a fresh profile without them). This is a terminal action — I could not and did not do it on disk.
4. Attach the lever-complete EA (once it exists) to one chart per config on its own TF (M1/M2/M5/M15), XAUUSD, `Volumen=0.10`, with the per-config inputs from `live_configs_20.py`. The `Riesgo.mqh` guard will refuse to init on any non-DEMO account (safety net verified in source).
5. **No `:8601` restart is implied by my changes** (I added a Python module + tests only; nothing the running service imports at runtime changed). A restart is only relevant once an executor is wired.

## Files changed (all uncommitted)
- `sentinel_engine/strategies/live_configs_20.py` (new) — the 20 configs as `simular_variant` kwargs, single source of truth.
- `tests/strategies/test_live_configs_20.py` (new) — audit + parity + lever tests (6, all pass).
- `scripts/live/check_live_sim_parity.py` + `scripts/live/__init__.py` (new) — Phase 3.5 live shadow-parity checker (read-only, per-config or all-20, exit 1 on hard divergence).
- `tests/scripts/test_check_live_sim_parity.py` (new) — checker self-test with injected divergences (6, all pass).
- `sentinel_engine/strategies/live_configs_20.py` — added per-config magic assignment (720010…720200) + `MAGIC_BY_ID`.
- This report.
