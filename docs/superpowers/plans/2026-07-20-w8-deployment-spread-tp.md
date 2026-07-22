# W8 — Deployment Wave: Spread-Minimum Theory, Adaptive TP, NEW6 Rosters (plan amendment)

> Amendment to `2026-07-19-honest-program-master.md`. Authored 2026-07-20 from user directives (D115–D117).
> **Sequencing: W8 runs AFTER the current wave queue completes** (W5 continuation → W5 batched review → W6 governance → W7 holdout) — user: "after this plan and exploration is completed." The active SDD session continues W5–W7 unchanged; this doc queues W8.
> Routing D111 unchanged (Fable orchestrates, Sonnet investigates report-only, Opus 4.8 implements from closed specs). Registry additive-only (D113). Machine-2 shadow-only (D114).

## New user decisions (2026-07-20)

**D115 — SPREAD-MINIMUM THEORY (user, "strong observed evidence").** When the spread is NOT at its minimum, our strategies lose; only at minimum spread do they win consistently. Status: theory with user-observed evidence, HIGH prior consistency with measured facts (round-trip friction varies 26× by hour-of-day; worst hours 04/07 UTC ate $276 of the $509 toll on 2026-07-14; overnight sessions = widest spreads — note this theory *predicts* the 2026-07-20 overnight A/B loss on both bands). Mandate: build the capture, validate retroactively and live, implement the gate (elevates P3/P42/P23/P58 from queued to REQUIRED).

**D116 — NEW6 DEPLOYMENT TARGET.** After exploration completes: deploy the **top-5 honest-league strategies + V15-M15-F** (the FIXED4 M15 winner) = **NEW6**, live on Capitaria DEMO on BOTH machines (machine-1 2883015767; machine-2 2883016567, shadow-band-only per D114). Selection frozen at selection time with a preregistration row; ranking source = the honest league (672+ honest-screen runs incl. v2 comparable cells + W5+ additions: SAR-M15, vol-target, regime-gated variants) using the league's own J/dominance/DSR-aware ordering.

**D117 — ADAPTIVE TAKE-PROFIT.** User observation: strategies exit TOO LATE (especially machine-2's) and give back gains; wants a live version of the 6-winner suite with **adaptive TP** enabled — tested first, but tested REAL (live demo shadow). Note + reconcile (not dismiss) the evidence tension: the overnight machine-1 A/B measured both bands negative, while the user observes net-positive runs with late exits; D115's spread conditioning is the leading candidate reconciliation (win-at-min-spread, lose-otherwise) — W8-T2 tests exactly this slice.

## W8 task queue (closed specs authored at dispatch, house style)

**W8-T1 — Spread telemetry (P3/P42; FIRST — everything downstream needs it).**
Executor: log `symbol_info_tick(symbol)` bid/ask + `symbol_info(symbol).spread` once per cycle per symbol into the audit log (`[SPREAD] sym=… bid=… ask=… spread_pts=…`), plus a lightweight CSV/parquet appender (`data/spread_capture/YYYY-MM-DD.csv`) so the series survives log rotation. Zero behavior change to trading. Acceptance: one live cycle shows the line; file grows; gate green.

**W8-T2 — Theory validation (report-only).**
(a) Ingest Capitaria vendor answers (spread schedule, min spread) when they arrive — user has them on WhatsApp, expected Monday. (b) Retro: slice ALL recorded deals (2026-07-14 session, 15–16 Jul night, 2026-07-20 A/B) by hour-of-day as spread proxy; compute PnL/win-rate at proxy-min-spread hours vs elevated hours. (c) Live: once W8-T1 runs ≥2 sessions, re-slice by MEASURED spread. Deliverable: `docs/superpowers/research/…-spread-conditioning.md` — the empirical test of D115, including whether it explains the overnight A/B loss.

**W8-T3 — Spread-minimum gate lever (P23/P58 realized).**
Sim: new kwarg `entry_max_spread` (entry allowed iff current spread ≤ threshold; sim uses the captured/vendor spread series when replaying; flat-0.5 worlds mark the lever inert). Executor: pre-entry check via live tick spread. Grid: threshold ∈ {min, min+0.05, min+0.10} from W8-T2's measured minimum. Honest pipeline + prereg as always.

**W8-T4 — Executor TP support (Addendum Claim-2 build).**
`Action` gains `tp` field; OPEN request carries `tp`; TP-modify path via TRADE_ACTION_SLTP (sl AND tp); reconciler diffs TP like SL. Server-side TP = resting intra-bar capture (catalog §I.5 principle — the honest way to exit earlier). Tests: TP present in requests, TP-touch removes ficha without executor close.

**W8-T5 — Adaptive-TP lever + offline grid.**
Sim lever (additive): `tp_adaptive` → per-ficha TP = `max(tp_spread_k × current_spread, tp_atr_k × ATR14)` (floors TP above friction; scales with vol). Grid tp_atr_k ∈ {0.5, 1.0, 1.5, 2.0} × tp_spread_k ∈ {3, 5} × per-ficha enable (F1-only vs F1+F2, F3 keeps trail — P14 role-split). Honest pipeline, preregistered; league-ranked.

**W8-T6 — NEW6 selection freeze.**
After W7 holdout: take top-5 league (post-W5, DSR-aware, holdout-respecting) + V15-M15-F; write prereg rows; define magic bands: NEW6 = 7220x0 (722010…722060), NEW6-TP suite = 7230x0. Document per-config params verbatim in the pack.

**W8-T7 — Deployment packs (both machines).**
Machine-1: NEW6 as in-process shadow band alongside whatever control the user keeps. Machine-2: NEW6 shadow-ONLY pack (supersedes FIXED4-only pack; same evidence-kit-first protocol; 30M CLP account check; never classic live-4 there). Durable supervisor path (`SUPERVISOR_CONFIGS`), git-only delivery.

**W8-T8 — NEW6-TP live test suite.**
The 6 winners + adaptive TP (best cell from W8-T5) as an ADDITIONAL shadow band (7230x0) run in parallel with plain NEW6 — the live paired test of D117. Kill criteria + daily loss budget (P30) per band; verdict rules preregistered (min trades/days per TF before judgment).

## Ordering & gates
T1 → (T2 ∥ T4) → T3/T5 (offline, honest pipeline) → T6 (needs W7 done) → T7 → T8. T1 is safe to implement as soon as the active session reaches a wave boundary (small, no overlap with W5 research files). Nothing deploys anywhere without its pack task + prereg + user's go at deployment moment.

## Open inputs
- Capitaria vendor answers (spread schedule/min, rate limits) — user relays when received; feeds T2/T3 and P59/P6b parameterization.
- Machine-2 still hasn't pulled the FIXED4 pack; T7 supersedes it with NEW6 — coordinate with equipo-2 timing.
- Relaunch of machine-1 live stack (currently DOWN): user decision pending; if relaunched pre-W8, recommended roster = V15-M15-F + V15-M15 control only (the only honest-positive pair), which would also start generating W8-T2's live spread-conditioned sample the moment T1 lands.
