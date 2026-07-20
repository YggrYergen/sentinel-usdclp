# Honest Program — Master Implementation Plan (overnight 2026-07-19 → 05:00 Chile 2026-07-20)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per house workflow (D85), the orchestrator authors a CLOSED, exact prompt per task at dispatch time using this plan as task-truth; implementers never improvise scope.

**Goal:** Re-found the strategy-research program on honest fills + honest statistics, re-run everything ever judged by the corrupted engine, audit the W2 giants, and prepare machine-2's FIXED4 deployment — offline work complete before **2026-07-20 05:00 América/Santiago (= 05:00 broker-server time)**.

**Architecture:** Two parallel tracks. Track A (machine-2 enablement): sim-honesty fix → minimal in-process shadow infra → FIXED4 → git pack for machine 2. Track B (research): registry validity marking → opt-integrated honest-sweep harness → overnight mega-sweep (Re-Run Manifest + new grids) → W2 forensic audit → morning league tables. Spec = `docs/SIM_VS_LIVE_GAP_ADAPTATION_CATALOG_2026-07-18.md` (Parts I–IV, 66 proposals) + its `-ADDENDUM.md` (§1 corrections are authoritative).

**Tech Stack:** Python 3.11 (repo embedded launcher), `simular_variant` (sentinel_engine/strategies/emasar_variant.py), `sentinel_engine/opt/` (walkforward/registry-DSR/selection), `ResearchRegistry` (registry2.py, data/research.db), pytest, git (branch `alvaro`).

## Global Constraints

- **Safety (Capa 4, unchanged):** DEMO 2883015767 only tradable; REAL read-only NEVER operate; ATTACH-ONLY; `guard_cuenta.assert_demo()` before any order. Machine-2 changes ship via git only.
- **Golden parity untouched:** `tests/golden/test_parity.py` must stay green; it does NOT cover `simular_variant` — Task A1 adds the hot path's own pinned tests (they are NEW, additive).
- **Registry policy: ADDITIVE-ONLY.** No run row deleted or mutated in original fields — ever. Marking via new column + audit_log. (User decision 2026-07-19: dups marked `DUPLICATE_INGEST`, not deleted.)
- **Model routing (USER OVERRIDE 2026-07-19, supersedes Sonnet-only rule for this program):** Fable 5 high = orchestrator (authors closed specs, verifies, proposes the high-value specifics). Sonnet 5 high = researchers/investigators, REPORT-ONLY (never ideas, never interpretation). **Opus 4.8 high = implementers**, given exact, specific, closed guidelines per task.
- **Agentic workflow rules** (`docs/superpowers/specs/2026-07-12-agentic-workflow-rules.md`): subagents timeboxed ≤10 min (>12 problem / >20 grave / >35 discard); ≤3 concurrent spawns; NEVER two agents on overlapping files; implementers get closed prompts in English.
- **Gate per task:** `python -m pytest -q tests/golden/test_parity.py tests/strategies tests/scripts tests/live` green (191+new; only the 3 known C5 `tests/service` failures tolerated repo-wide). Commit per task with descriptive message.
- **Assumed authorizations for the overnight run (user may veto at session start):** git tag + commits/pushes to `alvaro` of program code and docs; additive registry writes; file backups. NOT authorized: any deletion, any REAL-account touch, arming executors beyond what already runs — EXCEPT the local FIXED4 shadow verification explicitly authorized below (D114).
- **🔴 USER CORRECTION D114 (2026-07-19 session start — supersedes conflicting lines below):** machine-2 NEVER runs the uncorrected live-4. Machine-2 arms FIXED4 ONLY (`--configs shadow`). The A3 pack ships ONLY after the correction is confirmed working locally on machine-1: (a) **backtest** — A1 pinned tests green (classic byte-identical; live-fill honest SL); (b) **live** — FIXED4 running as in-process shadow alongside the local live-4 on DEMO 2883015767, ≥1 full cycle with the 7210xx magics active and no errors. Running `live+shadow` locally for this verification IS authorized. This local-verify step is Task A2b and is on the critical path.
- **Deadline:** Track B complete + morning report written before 05:00 Chile. Track A pack pushed same night.
- Windows 10 AND 11; pathlib; UTF-8 explicit.

---

## Phase 0 — Snapshot & rollback anchors (FIRST, ~10 min)

### Task 0.1: Git tag + data backup

**Files:** none created in repo (backup outside tree: `D:\FOREX_BACKUPS\2026-07-19-pre-honest-program\`)

- [ ] Step 1: `git -C D:\FOREX tag pre-honest-program-2026-07-19 && git push origin pre-honest-program-2026-07-19`
- [ ] Step 2: Create `D:\FOREX_BACKUPS\2026-07-19-pre-honest-program\` and copy: `data\research.db` (+ `-wal`/`-shm` if present), `data\lake\manifest.json`, `scripts\live\run_live_20.audit.log`, `scripts\live\watchdog.log`. Verify sizes non-zero; record a SHA256 of research.db in a `MANIFEST.txt` there.
- [ ] Step 3: Confirm live stack untouched (`git status -s` clean of unintended changes).

---

## Track A — Machine-2 enablement (wall-clock priority; catalog IV.H)

### Task A1: Sim honesty core (P1 fix + `trail_atr_floor_k` + pinned tests)

**Files:**
- Modify: `sentinel_engine/strategies/emasar_variant.py` (open_state snapshot ~line 812; new kwarg `trail_atr_floor_k: float = 0.0` applied where `trail_efectivo` is computed ~lines 504-513: `trail_efectivo = max(trail_efectivo, trail_atr_floor_k * atr14_current)` — ATR14 already computed in the sim for regime logic; if not exposed at that point, compute rolling ATR14 once per bar)
- Test: `tests/strategies/test_emasar_livefill_state.py` (NEW)

**Interfaces:**
- Produces: with `live_fill_mode=True, return_state=True`, `open_state[tag]["sl"]` == the SERVER-side SL (`server_sl_by_tag[tag]`), NOT the just-raised `f.sl`. With `live_fill_mode=False` behavior is byte-identical to today (pin it).
- Produces: `trail_atr_floor_k=0.0` default is a NO-OP (byte-identical outputs — pin with a regression test on a golden bar fixture).

- [ ] Step 1: Write failing tests: (a) classic-mode pin — run `simular_variant` on a small fixture (reuse an existing tests/strategies fixture) with and without the new kwarg default, assert identical events; (b) live-fill state — construct a bar sequence where the trail raises on bar i (bar high jump) and assert `open_state` sl == prior-bar server level, not the raised level; (c) same_bar_fallback event still emitted at bar close price.
- [ ] Step 2: Run → FAIL (b). 
- [ ] Step 3: Implement snapshot fix (`open_state` reads `server_sl_by_tag` when `live_fill_mode`) + the floor kwarg.
- [ ] Step 4: Full gate green. Commit: `feat(sim): honest open_state under live_fill_mode + ATR trail floor (P1/P8, catalog IV.H)`.

### Task A2: Minimal in-process shadow infra + FIXED4 (Addendum §1.2)

**Files:**
- Modify: `sentinel_engine/strategies/live_configs_20.py` (append `CONFIGS_SHADOW` + FIXED4 defs; magic base 721000)
- Modify: `scripts/live/run_live_20.py` (`--configs` accepts `live+shadow` AND `shadow` alone; resolution = CONFIGS_LIVE + CONFIGS_SHADOW, or CONFIGS_SHADOW only — machine-2 uses `shadow` per D114)
- Modify: `scripts/live/supervisor_live.py` (EXECUTOR_ARGV stays `live` by default; add `SUPERVISOR_CONFIGS` env/const so machine-1 can set `live+shadow` for A2b verification and machine-2 pack sets `shadow`)
- Test: `tests/strategies/test_configs_shadow.py`, extend `tests/scripts/test_run_live_20.py`

**Interfaces (exact FIXED4 spec):**
```python
# live_configs_20.py — FIXED4: the live roster with the obvious honesty fixes.
# Same signals; honest exits. Magics 721010/721020/721030/721040 (+1..+3 fichas).
def _fixed(cfg, new_magic):
    k = dict(cfg["kwargs"], ac_modulate=False, live_fill_mode=True,
             trail_atr_floor_k=1.5)
    return {**cfg, "id": cfg["id"] + "-F", "kwargs": k, "magic": new_magic}
CONFIGS_SHADOW = [_fixed(c, 721000 + 10*(i+1))
                  for i, c in enumerate(CONFIGS_LIVE)]
```
- Produces: `--configs live+shadow` → 8 configs, 24 ficha band, cap 60 respected; magic bands disjoint (assert in test).

- [ ] Steps: failing tests (roster resolution, magic disjointness, FIXED4 kwargs exact) → implement → gate → commit `feat(live): in-process CONFIGS_SHADOW + FIXED4 roster (catalog IV.H)`.
- [ ] Extra step: measure cycle time with 8 configs (one `--once` dry-run cycle, log timing) — record in commit message; if >12 s, flag for P37 priority (do NOT block).

### Task A2b: Local live confirmation of FIXED4 (D114 gate — blocks A3)

**Files:** none new (operational verification; evidence pasted into A3's doc)

- [ ] Step 1: Backtest confirmation = A1 test suite green (already gated) + one honest-vs-classic diff run of a live-4 config on recent lake bars showing the FIXED4 kwargs change exits (sanity print, no persistence needed).
- [ ] Step 2: With the local supervisor/watchdog stack running, start ONE verification executor cycle with `--configs live+shadow` (`guard_cuenta.assert_demo()` verified; DEMO 2883015767 only). Alternative if safer: set `SUPERVISOR_CONFIGS=live+shadow` and let the canonical supervisor restart the executor.
- [ ] Step 3: Verify in audit log: 8 configs resolved, 7210xx magics present in cycle output, no exceptions, cycle time recorded; if signals fire, `[SENT OPEN] ... magic=7210xx` with DEMO account. ≥1 clean full cycle required.
- [ ] Step 4: Record evidence block (log excerpts) for the A3 sheet. Revert local stack to `live` unless user says keep `live+shadow` running overnight.

### Task A3: Machine-2 pack (BLOCKED until A2b evidence recorded)

**Files:** Create `docs/MACHINE2_FIXED4_DEPLOY_2026-07-19.md` (instruction sheet)

- [ ] Step 1: Push Track-A commits to `origin/alvaro`.
- [ ] Step 2: Write the instruction sheet (D114 semantics): (1) pull; (2) run the evidence kit from `docs/DIAGNOSTIC_REPORT_MACHINE2_ZERO_POSITIONS_2026-07-18.md` §5 if not already done, apply its decision matrix — the platform-level causes (AutoTrading OFF, preflight, STOP file, machine_local.json) block FIXED4 exactly as they blocked live-4, so they must be cleared first; (3) set supervisor to `shadow` ONLY (never `live` nor `live+shadow` on machine-2 — the uncorrected live-4 must NOT run there); (4) verify FIXED4 magics 721010-40 appear and a `[SENT OPEN] retcode=10009` lands; (5) rollback = stop supervisor (there is no valid fallback roster on machine-2). Include the exact PowerShell/log greps + the A2b local-verification evidence block.
- [ ] Step 3: Commit + push doc. Final message to user includes the copy-paste block for machine-2's Claude session.

---

## Track B — Research pipeline (runs in parallel with Track A; B3 runs overnight)

### Task B1: Registry validity marking (P38, additive-only)

**Files:**
- Create: `scripts/report/mark_validity_2026_07_19.py` (idempotent migration)
- Modify: `sentinel_engine/research/registry2.py` (add nullable `validity TEXT` column via `ALTER TABLE` if absent — additive)
- Test: `tests/scripts/test_mark_validity.py` (against a temp copy of a mini DB fixture)

**Marking spec (exact):** 39 TOKATA dup pairs (group by variant_id+net+trades, keep FIRST run_id per group unmarked, mark the second `DUPLICATE_INGEST`); `sim-report-emasar-v12-{m1,m2,m5,m15}` → `LOOKAHEAD_CONFIRMED`; all `sim-report-emasar-oow2-*` → `REGIME_UNAUDITED` (Task B4 upgrades these); TOKATA rows whose variant used the 3-pip stop family (per `REPORTE_MEJORES_VERSIONES` §) → `INEXECUTABLE_STOP`. Every marking writes an `audit_log` row (actor='honest-program', action='validity-mark', payload=run_id+label+reason).

- [ ] Steps: failing test on fixture → implement → run against real DB (AFTER Phase-0 backup verified) → spot-check counts (39, 4, 17, …) → gate → commit.

### Task B2: Honest-sweep harness (P2+P35+P64): `scripts/report/gen_honest_sweep.py`

**Files:**
- Create: `scripts/report/gen_honest_sweep.py`
- Create: `scripts/report/honest_manifest_2026_07_19.json` (Task B3 authors content)
- Test: `tests/scripts/test_gen_honest_sweep.py` (tiny grid on fixture bars)

**Interfaces:**
- CLI: `python -m scripts.report.gen_honest_sweep --manifest <json> [--windows IW,W1,W2,W3] [--dry-list]`
- Manifest entry: `{"variant_id": str, "tf": "M1|M2|M5|M15", "kwargs": {…simular_variant kwargs, always live_fill_mode true…}, "windows": [...], "prereg": {"hypothesis": str, "metric": "net_honest", "threshold": …}}`
- Behavior: REFUSES to run any entry without prereg (writes `preregistration` row first, links run rows to it — P64). Reuses batch1's loader/spread/metrics helpers via importlib (pattern: `gen_livefill_bound.py`). Costs: flat SPREAD=0.5 until P3 data exists — stored in metrics_json as `cost_model: "flat0.5"`. Persists EVERY cell (run+trades) with `fidelity='honest-screen'`. After the grid: calls `sentinel_engine/opt` — walk-forward folds where window count permits, DSR over the trial family (trial registry = manifest size), the 4 selection guards — and writes a league table JSON + md report to `docs/superpowers/research/2026-07-20-honest-league.md`.

- [ ] Steps: failing test (tiny 2-entry manifest on fixture; assert prereg rows, run rows, league output exists) → implement → gate → commit.

### Task B3: The Mega-Sweep (manifest authoring + overnight run)

**Manifest content = catalog Part IV.G (Honest Re-Run Manifest) + Part II grids:** all batch-1..7 levers/extensions on all 4 TFs × all coverable windows (W3 only M5/M15 — lake fact); the 7 D90-uncovered configs; the 20 unpersisted batch-7 cells; V-07; honest twins of live-4 (reference row); Tier-A grids (trail_atr_floor_k ∈ {0,1.5,2,3} × ac_modulate {on,off} × close-confirmed exit if trivially expressible via existing kwargs — else defer); TP/BE grids (f1_tp_r ∈ {1,1.5}, be — sim-side kwargs EXIST); P51 time-stop if a max-hold kwarg exists (else defer to next wave — do NOT add sim levers beyond A1's floor tonight); P46 ficha-count via volume post-processing in metrics.
- [ ] Step 1: Orchestrator authors the manifest (Fable — this is the "propose the high-value specifics" duty), ~300–600 entries, each preregistered.
- [ ] Step 2: `--dry-list` review (entry count, window coverage matrix printed).
- [ ] Step 3: Launch full run in background; monitor; ETA check (~23k bars/s ⇒ hours).
- [ ] Step 4: League tables generated; commit results doc + manifest.

### Task B4: W2 forensic audit (P31): `scripts/report/gen_w2_audit.py`

**Files:** Create `scripts/report/gen_w2_audit.py` (modeled on `gen_v12_audit.py` — read it first); Create report `docs/superpowers/research/2026-07-20-w2-forensic-audit.md`

**Spec:** For each `sim-report-emasar-oow2-*` run: TEST-2-style entry-improvement forensics (join trades to entry-bar OHLC, measure signed improvement vs close; champion-baseline comparison); same-bar exit census; causal sanity (these configs enter at close — expected clean; VERIFY, don't assume); honest re-pricing via live_fill (some cells already exist from `gen_livefill_bound` — link, don't duplicate) + flat friction. Upgrade `validity`: `REGIME_UNAUDITED` → `W2_AUDIT_PASS` or `W2_AUDIT_FAIL(reason)`.
- [ ] Steps: implement → run → report (which W2 $ survives which fidelity level, per cell) → mark validity → gate → commit.

### Task B5: Morning report (before 05:00 Chile)

**Files:** Create `docs/REPORTE_HONEST_PROGRAM_2026-07-20.md`
- [ ] Contents: what ran (counts), DSR-surviving winners (the honest league top table + which old "winners" died), W2 audit verdict, FIXED4 expected-behavior notes for machine-2, registry marking summary, deviations from plan, next-wave recommendation. Spanish, user-facing, numbers first.
- [ ] Commit + push everything; leave breadcrumb-rich final message.

### Task C (only if time remains): P3 spread-capture telemetry in the executor cycle (log `symbol_info_tick` bid/ask/spread per cycle to audit log — 5-line change + test); P30 per-config daily loss budget for FIXED4.

---

## Timeline (wall-clock, Chile = server time)

| When | What |
|---|---|
| T0 (session start) | Phase 0 (15 min) → A1 (60–90 min) ∥ B1 (45 min) |
| T0+1.5h | A2 (60 min) ∥ B2 (90 min) |
| T0+3h | A3 pack pushed ∥ B3 manifest authored + dry-list |
| T0+4h | B3 overnight run launched; B4 built while it runs |
| B3 done | B4 executed on fresh results; league tables |
| ≤05:00 | B5 morning report committed + pushed |

## Self-review notes (spec-coverage)
- Catalog items NOT in tonight's scope (deliberately, deadline-driven): P4 tick loader, P6b ratchet, P37 state-carry, P21/P22/P25 pending orders, P39 Dukascopy download (start next session — user decision recorded), P42 archiver, UI badges (P38-UI half), P56–P62 builds. They remain queued in the catalog; tonight = honest foundation + mega-sweep + W2 + FIXED4.
- Vendor answers (Capitaria) arrive Monday — parameterize P59/P6b THEN.
- Machine-2 evidence may arrive mid-run: A3's sheet covers both orders (evidence-first, then FIXED4).
