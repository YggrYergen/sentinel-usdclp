# Honest Program — Complete the 66 (Wave-2 master plan) — 2026-07-20

> **Continuation of** `2026-07-19-honest-program-master.md` (which executed only the
> overnight subset). Goal (user, 2026-07-20): run EVERYTHING not-yet-run through the
> designed honest pipeline and finish the un-done proposals, to get the full picture and
> surface the **best working strategies** — following the designed system/procedure.
> Execution: superpowers:subagent-driven-development.

## Model routing (USER OVERRIDE 2026-07-20 — supersedes the Fable-5 routing)

- **Orchestrator = Opus 4.8, high effort** (this controller). Authors closed task briefs,
  reviews, sequences, launches sweeps.
- **Implementers = Opus 4.8** (medium effort intent). Given exact, closed briefs per task.
- **Researchers = Sonnet 5, high effort, REPORT-ONLY** (objective facts, never ideas/interpretation).
- **Concurrency: ≤2 subagents in flight at any time** (user, 2026-07-20). Never two agents on
  overlapping files. Implementers run one-at-a-time (SDD rule); the 2nd slot is for an
  independent read-only researcher only.

## Global constraints (inherited — binding)

- **PROD read-only:** the live stack (`run_live_20 --arm`, running) is untouched. DEMO 2883015767
  only; REAL never operated; ATTACH-ONLY.
- **Registry ADDITIVE-ONLY:** no run row deleted or mutated in original fields. Marking via
  columns + `audit_log` (actor `honest-program`). Phase-0 backup exists (`D:\FOREX_BACKUPS\...`).
- **Concurrency-safe DB:** heavy work opens `research.db` `mode=ro`; writes in one short
  transaction with `busy_timeout`. The live stack + sweeps coexist (proven overnight).
- **Designed procedure (P35/P64) is mandatory for every backtest:** anchored walk-forward +
  purged splits + DSR (trial family = manifest size) + the 4 selection guards + a
  `preregistration` row per entry (harness refuses un-preregistered grids). Cost model: flat
  0.5 spread at fill (`cost_model: flat0.5`), `live_fill_mode=True` always. Persist EVERY cell
  (`fidelity='honest-screen'`).
- **Idempotent, comparable timeframe (user, 2026-07-20):** ALL backtests across ALL waves run on
  the SAME window set — **IW, W1, W2, W3** (W3 M5/M15 only, lake fact) — so every strategy is
  comparable in one league, and a re-run reproduces identical nets/hashes. Any new sim lever
  ships with a NO-OP default so classic byte-identity is preserved (pinned test per lever).
- **Gate per task:** `pytest -q tests/golden/test_parity.py tests/strategies tests/scripts
  tests/live` green (currently 294) + the task's own new tests. Commit per task, ≤~500 LOC/edit.
- **Subagents timeboxed ≤10 min**; closed English briefs; TDD (test-first) for every code task.
- Branch `alvaro` (where all honest-program work lives). Artifacts under `docs/superpowers/`.

## Definition of done (the single final report)

Report to the user ONLY when: every offline proposal below is implemented + gated; every
un-run backtest has run through the designed pipeline on {IW,W1,W2,W3}; the single-touch
holdout has run on all DSR survivors; ONE consolidated honest league ranks every strategy on
the comparable timeframe; and a final whole-branch code review is clean. Then `/brain update`.

---

## Wave sequence (dependency-ordered)

### Wave 1 — Finish the honest re-run (IV.G completeness) — the "full picture"
Close the gap between what the manifest ran (V06/07/09/11/13/15 + super-stacks + trail/TP/BE
grids) and the full lever set. Un-run: **V01,V02,V03,V04,V05,V08,V10,V14** (+ V01b extension),
all 4 TFs × {IW,W1,W2,W3}; persist any batch-7 grid cells still docs-only; V-12 stays
audit-DEAD (excluded except its P33 cousin, Wave 5).
- **W1-T1 (researcher, Sonnet 5):** definitive gap inventory — every lever/extension/grid-cell
  ever defined (batch1–7 docs + `REPORTE_MEJORES_VERSIONES`) vs what exists in `research.db`
  honest-screen + the current manifest. Output: exact un-run cell list (variant_id, tf, kwargs).
- **W1-T2 (implementer):** extend `honest_manifest_2026_07_19.json` → the gap entries,
  preregistered; `--dry-list` count + window-coverage matrix.
- **W1-T3 (orchestrator):** launch the extended sweep in background; monitor; regenerate the
  league; commit results + manifest.

### Wave 2 — New sim levers (additive kwargs, then sweep)
Each: TDD, additive kwarg with NO-OP default, pinned classic byte-identity + honest tests,
gate, commit; then add its grid to the manifest and sweep on {IW,W1,W2,W3}.
- **W2-T1:** P51 time-stop (`max_hold_bars`, close at bar-close after N).
- **W2-T2:** P52 partial-close ladder (fractional close at TP1, trail remainder).
- **W2-T3:** P54 confirmation-bar entry (enter only if i+1 confirms beyond signal-bar extreme).
- **W2-T4:** P55 stop-and-reverse (single net order on opposite signal).
- **W2-T5:** sweep all Wave-2 levers (grids) through the pipeline; league refresh.

### Wave 3 — Sizing & risk re-scoring (orthogonal, mostly metric post-processing)
Re-score existing honest sweeps; sizing is orthogonal to signal replay (L1/L2 re-score).
- P43 vol-targeted sizing (vol ∝ 1/ATR14); P44 drawdown-responsive throttle; P45 fractional-Kelly
  (from the honest league); P46 escalera 1-vs-2-vs-3 fichas; P47 risk-parity portfolio alloc.

### Wave 4 — Portfolio & cross-config
- P48 correlation/netting study; P49 meta-selector (rolling best-of, DSR-gated); P50 signal-overlap
  M2-trio (measure redundancy — finding, not a drop).

### Wave 5 — Legacy revivals & regime specialists (new strategy code)
- P34 SuperTrend p14x3-M15 revival (port the one real-tick-validated legacy family into the ladder).
- P32 W2-regime specialist (ATR14 percentile bands; deploy M15 only in W2-like regime).
- P33 V-12 causal cousin (resting LIMIT at causally-computed pullback EMA, next-bar expiry).

### Wave 6 — Governance & parity (make honesty structural)
- P36 execution-parity suite (both fill modes, return_state combos, carry≡window). P63 formalize
  the too-good trigger (`AUDIT_REQUIRED` auto-flag). P65 nightly sim-vs-live residual KPI.

### Wave 7 — Holdout & final selection — the "best working strategies"
- Single-touch holdout on ALL DSR survivors across waves; final consolidated honest league on
  {IW,W1,W2,W3}; name the best working strategies with survival evidence; final whole-branch review.

---

## PARKED — cannot run autonomously this session (needs user/external input)
Listed so the final report is honest about coverage; NOT silently skipped.
- **P39–P42** — Dukascopy acquisition + multi-year windows + cross-feed + tick archive: external
  data download / credentials / long-running daemon.
- **P59–P62** — MODIFY governor, deviation tuning, demo-vs-real dossier, latency telemetry: need
  Capitaria vendor limits / are live-execution or design-only (REAL stays read-only).
- **P6b** — tick-trailing executor: live executor work, gated on P59.
- **P37** — state-carry incremental engine: large engine rewrite, gated on P36; deferred unless
  time remains after Wave 6.

## Trackers
- **SDD ledger:** `.superpowers/sdd/progress.md` (per-task completion + commit range).
- **Brain thread:** `20260720-073733-7mwm` ("Honest Program — complete the 66"). `/brain update`
  at program end with plan path, artifacts, league, holdout verdict.
