# Sim-vs-Live Gap — Root-Cause Synthesis and Adaptation Catalog (30 proposals)

**Date:** 2026-07-18
**Problem:** the strategies earn in backtesting and lose in the live market. Measured gap (session 2026-07-14, 6h51m): classic backtest projected **+704 USD**, reality delivered **−763 USD**, decomposition closes with 0.16% residual.
**Purpose of this document:** (1) state the verified root causes; (2) catalog up to 30 adaptations/variants — each with mechanism and rationale — candidates for the shadow program (D103, magics 721000+) running alongside the 4 live configs.
**Method:** 2 read-only Sonnet investigators (gap measurements; sim/executor mechanics) compiled facts from the repo's research corpus and source; every load-bearing claim was re-verified against source by the orchestrator. Fact bases: `scratchpad/facts_A_gap_measurements.md`, `facts_B_mechanics_levers.md` (session artifacts); primary sources cited inline.

---

## Part I — The verified causal model

### 1. The gap decomposition (measured, residual 0.16%)

| Step | USD | Share |
|---|---:|---|
| Classic backtest projection (same bars, same window) | **+704.1** | — |
| − Same-bar exit optimism (classic → live-fill semantics) | **−956.8** | ≈ 2/3 of damage |
| = Executable theoretical bound | −252.7 | — |
| − Measured fill friction (spread + next-tick; ≈$0.50/round-trip × 1,011 positions) | **−509.0** | ≈ 1/3 of damage |
| = Expected with real fills | −761.7 | — |
| **Real** | **−762.9** | residual −1.2 (0.16%) |

Source: `docs/REPORTE_DIAGNOSTICO_LIVE_VS_TEORIA_2026-07-14.md` §1.

### 2. Root cause A — the sim's look-ahead exit, and how the optimizer weaponized it

Verified at `sentinel_engine/strategies/emasar_variant.py:512-518, 540-544` (classic mode):

1. On bar *i*, the trail is raised using **bar *i*'s own high**: `f.max_fav = max(f.max_fav, bar["high"]); nuevo_sl = f.max_fav − trail_efectivo`.
2. The **same bar's low** is then checked against the just-raised level, and the exit **fill price awarded is that raised level** — a price the server could never have honored, because the corresponding SL order did not exist during bar *i*.
3. With `ac_modulate=True`, on AC deceleration the trail is multiplied by `ac_modulate_factor`. At the "winning" factor **0.01**, effective trail = 100 pips × 0.01 = **$0.01/oz** — the sim exits at `bar_high − $0.01`, i.e. **essentially the top of every favorable bar**.

**Consequence:** the 7-batch variant program, whose objective was classic net PnL (`scripts/report/gen_variant_batch1.py:522` — `if m["net"] > best_net`), *monotonically rewarded smaller factors with no knee ever found* — because a smaller factor buys more look-ahead, not more edge. The D90 study then showed the tell: under live-fill semantics the entire factor axis **stops discriminating** (net bit-identical across f∈{0.01, 0.10, 0.25} on M15), and **100.0% of trail exits are same-bar fallbacks in all 51 config×window cells** (`2026-07-13-livefill-bound.md` §4-5). The champion selection is, to first order, a ranking of look-ahead exploitation.

### 3. Root cause B — the live executor chases the phantom

Verified at `scripts/live/run_live_20.py:177-180` + `live_configs_20.py:_SKELETON`: the executor's desired-state oracle calls `simular_variant(bars, return_state=True, **kwargs)` **without `live_fill_mode=True`** — the optimistic classic sim drives live trading. When the classic sim declares a same-bar exit the market never offered, the reconciler **market-closes at the next tick** (`SAME_BAR_EXIT_FALLBACK`, logged as "by design"): 954/1,011 positions (94.4%) exited this way, at an average by-design cost of **−$1.08/event**, plus the spread toll on every one of those round trips.

### 4. Root cause C — the objective never contained the costs that matter

Selection used: classic fills + flat 0.5 spread applied at fill (`gen_variant_batch1.py:46,126-137`) + **no slippage, no commission, no live-fill timing, net-PnL maximization**. Live reality adds: bar-close+latency market fills (cycle interval up to 15 s), bid/ask crossing both ways (measured median $0.495/oz round-trip; worst hours UTC 04 = $121 and 07 = $155), broker stops-level clamping (10016), and a short-side exit premium (median +0.71 vs +0.19 $/oz). None of these were selection pressures — so the selected population is systematically fragile against exactly them.

### 5. The unifying design principle

> **Server-side resting orders (SL, TP, pending stop/limit) are the only mechanism that can legitimately capture intra-bar prices.** Everything else the executor can do is a market order at bar-close-plus-latency. The classic sim assumed intra-bar fills everywhere; resting orders are the only honest way to actually obtain them — and where measured, the broker honored them perfectly (9/9 SL fills at exactly the installed level, gap 0.00).

Every exit-side proposal below is an application of this principle; every frequency proposal attacks the $0.50 × N toll; every selection proposal replaces the corrupted objective.

### 6. Sim assumption vs live reality (event map)

| Event | Classic sim assumes | Live reality |
|---|---|---|
| Entry | Fill at signal-bar close (bid+0.5 for longs) | Market order 0–15 s after bar close; ask-crossing; measured slip mean −0.25 $/oz |
| Trail update | Instantly active within the same bar, raised with current bar's high | MODIFY (SLTP) after bar close; active only from next bar; clamped by stops-level (10016) |
| Trail exit | Intra-bar touch fill at the just-raised level | Server SL touch at the *previous* bar's level, or executor market-close at bar close + latency |
| Same-bar entry+exit | Both fills honored intra-bar | Impossible: entry ~bar close, "exit" = immediate market close next tick (−$1.08 avg by-design + spread) |
| TP | Not used (0/20 configs) | Not used — no TP field exists in any order (verified H2) |
| Costs | Flat 0.5 spread at fill | ~$0.50/RT median but hour-dependent (up to 3×); short exits pay more; deviation 20 pt |

---

## Part II — The catalog (30 proposals)

Legend per item: **What** · **Why it should work** (tied to measured numbers) · **Validation path** · **Risk**.
Tiers: **T0** system honesty (prerequisites) · **TA** exit mechanics (attack −957) · **TB** churn/frequency (attack −509) · **TC** entry fills · **TE** trade-shape/regime redesigns.
Validation convention for ALL items (per the diagnostic's own rule, §6): *measured against `live_fill_mode=True` + realistic spread, never against the classic backtest*; survivors go to shadow demo (magics 721000+) paired against the 4 live configs.

### Tier 0 — Make the machine honest (system fixes; prerequisites, not shadow configs)

**P1. Switch the live executor's oracle to `live_fill_mode=True`.**
What: pass `live_fill_mode=True` into the executor's `simular_variant` call (one kwarg at `run_live_20.py:180` / `_SKELETON`).
Why: today live trading is steered by a sim that books impossible fills; the reconciler then "corrects" 94.4% of exits by market-closing at next tick. With the honest oracle, desired-state = executable state: fichas stay open until the *server's* SL level is genuinely touched or a close-of-bar violation occurs — same-bar market-closes stop being the norm. This is the single highest-leverage code change in the repo.
Validation: offline replay parity (honest oracle vs audit) over a recorded session; then A/B shadow of one config pair.
Risk: changes live behavior of the current 4 — deploy first on shadow twins, not on the live roster.

**P2. Re-run the entire lever program under the honest objective (D103 phase 1).**
What: re-execute batches 1–7 (all levers, all TFs) with `live_fill_mode=True` + hour-aware spread, objective = net *after friction*.
Why: every recorded verdict ("winner"/"loser") was rendered by a corrupted judge. Known example: ac_modulate factor's dominance evaporates under live-fill. Symmetrically, recorded *losers* (TP legs V-05, breakeven V-02, ladders V-04) were penalized for competing against perfect exits — their rankings may invert. The current winner set is not trustworthy; the honest re-ranking produces the true shadow candidates.
Validation: it *is* the validation instrument. Deliverable: honest league table per TF.
Risk: compute time only.

**P3. Capture real spread in the executor and the lake.**
What: log `symbol_info_tick` bid/ask (and `symbol_info().spread`) every cycle in the audit log; add a spread column to lake ingestion.
Why: the repo has **zero** recorded spread data (bars are BID-only; the 0.5 constant is folklore from one snapshot). Spread-by-hour was measured for ONE session and varies 26× by hour ($5.98 → $155.44 per hour of entries). Cost-aware objectives (P2), spread gates (P23) and honest friction models all starve without this feed.
Validation: one session of capture; compare distribution vs the flat 0.5 assumption.
Risk: none (read-only telemetry).

**P4. Build tick ingestion + a tick-level exit evaluator (Route A).**
What: `copy_ticks_range` dumper (tick cache exists locally for 2026-01→07), tick loader, and a tick-replay evaluator for exits/pending fills.
Why: no tick-level validation has ever been run; bar-level live_fill is itself an approximation (it can't see intra-bar sequence). Tick replay is the only way to honestly price server-side resting-order strategies (P6, P11, P22, P25) before risking even demo money.
Validation: reconcile tick-replay vs actual broker fills on a recorded live day (ground truth exists in deals history).
Risk: engineering effort; mitigate by validating only the shortlisted survivors of P2.

**P5. Pre-registered, cost-complete selection metric.**
What: adopt `net_honest = live_fill net − (round_trips × measured RT cost by hour) − slip model` with DD and trades/day reported; pre-register thresholds before each sweep (e.g. PF_honest > 1.3 across ≥2/3 OOW windows).
Why: D84 already forced audits for too-good results (WR>90% → audit); this generalizes the lesson: the objective *is* the strategy. Every historical mis-selection here traces to an objective that omitted a real cost.
Validation: applied inside P2.
Risk: none.

### Tier A — Exit mechanics: attack the −957 (same-bar optimism)

**P6. "Let the broker exit": server-SL-only trailing, no executor market-closes.**
What: the trail exists ONLY as the server-side SL, updated by MODIFY at each bar close; delete the same-bar market-close behavior (no `SAME_BAR_EXIT_FALLBACK` sends). Exits happen exclusively when price *actually touches* the resting level (plus the initial range-SL as disaster stop).
Why: broker SL fills measured perfect (9/9 at exactly the installed level). Resting orders capture intra-bar prices legitimately — the only honest version of what the classic sim pretended to do. Converts 94% of exits from spread-paying, latency-afflicted market orders into server-side stop fills, and mechanically lengthens holds (the position survives until a real touch).
Validation: tick replay (P4) → shadow twin of V15-M2 and one M15 config.
Risk: gaps/fast markets fill stops with slippage; stops-level (10016) bounds how tight the SL can trail — pair with wide-trail variants (P8).

**P7. Next-bar-activation trail as a strategy variant (honest live_fill twins of the 4 live configs).**
What: shadow-run the 4 live configs with `live_fill_mode=True` semantics end-to-end (P1 applied to their twins), unchanged parameters.
Why: isolates the pure effect of honest exit timing on the *current* roster — the cleanest possible A/B on the −957 component. The 2026-07-15 replay showed live-fill net-positive (+$145.77) on a real day for these 4 — evidence the roster isn't hopeless when the oracle is honest.
Validation: direct paired comparison vs the 4 live originals, same days, same market.
Risk: minimal — measurement variant.

**P8. Wide-trail floor: trail ≥ k × ATR(14), k ∈ {1.5, 2, 3}.**
What: floor `fN_trail_pips` at a multiple of current ATR so the trail is structurally wider than typical bar range.
Why: the same-bar condition fires when trail < bar range. M15 evidence: with trail wide relative to bar range, 94.7% of >1-bar trades exit at the *genuine* prior-bar server level. Wide trails make the honest mechanism (P6) actually reachable instead of degenerate.
Validation: P2 sweep (k grid) → shadow.
Risk: wider trail returns more open profit per exit; net effect must be measured, not assumed (this is the diagnostic's own §6-#2 caution).

**P9. Kill the modulated-tightening artifact: `ac_modulate=False` (and factor ∈ {0.5, 1.0}) twins.**
What: shadow variants of the live configs with AC modulation disabled or nearly disabled.
Why: factor 0.01–0.25 is the look-ahead harvester (§I.2): under live semantics it doesn't discriminate — but it DOES still shape the executor's oracle today, manufacturing same-bar exits (trail collapses to $0.01–0.25 on AC-deceleration bars, guaranteeing close-of-bar violation). Removing it removes a pure churn generator with zero proven live benefit.
Validation: P2 (expect ~no live-fill net change but large drop in same-bar event count and spread toll) → shadow.
Risk: low; the classic-engine "gain" it provided was the artifact itself.

**P10. Close-confirmed exits: exit only when bar CLOSE violates the trail.**
What: exit rule = close beyond trail level (not intra-bar touch); executed as a market close at the next cycle; sim and executor share this rule exactly.
Why: makes sim semantics *identical by construction* to what the executor can execute (bar-close information, bar-close action). Eliminates the sim-live divergence class entirely; close-confirmation also filters wick-noise stop-outs (a common cause of churn on M1/M2).
Validation: P2 → shadow.
Risk: gives back more adverse excursion per exit than touch-based stops; the disaster-stop (initial range SL) must remain server-side.

**P11. Take-profit legs (server-side limits) — re-judge V-05 under the honest engine.**
What: F1 TP at ~1–1.5R, F2 at ~2–3R (server-side TP field — currently NO config and NO order uses TP at all), F3 runner on trail.
Why: TP orders are resting intra-bar capture (the honest analogue of the sim's optimistic exits) and fill without executor latency. V-05's "inert/worse" verdict was rendered by the classic judge whose baseline exits were *already perfect* — against honest fills, locking gains at favorable extremes competes against a much worse baseline. The measured trade shape (median hold 132 s, avg same-bar cost −$1.08) shows winners are given back before they can be banked.
Validation: P2 re-sweep of TP grids → tick replay (P4) → shadow.
Risk: capping the right tail; measure PF vs tail loss trade-off per TF.

**P12. Breakeven-at-R ≥ 1.5R — re-judge V-02 under the honest engine.**
What: move SL to entry ± spread once ≥1.5R (grid up to 3R) of favorable excursion.
Why: V-02's loss under classic shrank monotonically as the threshold rose (−14,877 at 0.5R → −877 at 1.5R at top of grid — trend suggested a flip just beyond, never tested). Live loss shape is many small losses (WR 30% live vs 46–89% classic); a far breakeven converts a slice of full losses into scratches without touching winners' tails.
Validation: P2 with extended grid {1.5, 2, 3}R → shadow.
Risk: breakeven clustering at obvious levels invites stop-hunts; use entry±spread+buffer.

**P13. Signal-reversal exits (SAR/EMA flip), trail only as disaster stop.**
What: exit on the strategy's own reversal signal (bar-close information); server SL kept wide (initial range-SL) purely as catastrophe insurance.
Why: reversal exits are bar-close-executable with zero sim-live divergence, and decouple exit quality from trail-width tuning entirely. The entry logic already computes the SAR flip; the exit becomes symmetric with the entry rather than an intra-bar micro-mechanism the live market can't honor.
Validation: P2 → shadow.
Risk: reversal lag returns open profit in fast reversals — expected to pair best with M15/M5, not M1.

**P14. Role-split escalera: F1/F2 on TP legs, F3 on wide trail.**
What: restructure the 3-ficha ladder so F1/F2 bank via resting TPs (P11) and only the runner F3 trails (wide, P8).
Why: combines banked intra-bar captures (honest optimism) with preserved right tail; directly replaces the flat-100-pips×3 design whose entire exit population collapsed to same-bar fallbacks. Ladder *shape* variants lost under the classic judge (V-04) — but shape-of-exit-mechanism was never tested, only shape-of-distance.
Validation: P2 → tick replay → shadow.
Risk: complexity; needs clean per-ficha TP support in executor (TP field exists in MT5 request, currently unused).

### Tier B — Churn & frequency: attack the −509 (the $0.50 × N toll)

**P15. M15-first shadow roster.**
What: bias the shadow program toward M15 rebuilds (the 8 M15 configs + corrected-exit variants).
Why: M15 is the ONLY timeframe with any positive live-fill cells (W2: +$9.3–9.6k, PF 1.24–1.26; W3: +$1.6–2.9k) and has intrinsically lower churn (1.3–2.2 pos/h vs 12–25 on M2/M1). The structural math favors it: bigger bars ⇒ trail can exceed bar range ⇒ honest exits reachable; fewer round-trips ⇒ toll shrinks by an order of magnitude.
Validation: already live-fill-positive in D90 W2/W3; shadow to confirm on current regime.
Risk: thin real-money sample (9 positions) on M15 configs to date; W1-like regimes were negative — pair with P27.

**P16. Stronger entry confirmation: `confirm_count` 2→3, `require_ema_order=True`.**
What: raise the entry bar so marginal signals don't fire.
Why: every avoided round-trip banks ~$0.50 + avg same-bar cost ~$1.08. At 12–15 pos/h (M2 configs), even a 30% entry cut is worth ~$40–60/night per config at current volumes, while the classic-engine evidence says confirmation-strengthening cuts weakest-first.
Validation: P2 (watch net vs trades curve; stop where net_honest peaks) → shadow.
Risk: the V-08/V-10 lesson — population-cutting can remove more edge than it saves; that verdict too was classic-judged, so re-measure honestly.

**P17. Post-exit cooldown (N-bar re-entry lockout).**
What: after any exit, block same-config/side re-entry for N bars (grid N ∈ {1, 2, 3}).
Why: live churn shows immediate re-entry after same-bar exits (holds quantized to 1–2 bars; 75% of positions ≤5 min) — the same signal repeatedly pays entry+exit friction for the same move. A cooldown breaks the pay-per-bar cycle at minimal signal cost. Note the tension with V-13 (re-entry WON under classic): under the honest judge, re-entries must beat the friction they generate — test both directions (P2 decides).
Validation: P2 → shadow.
Risk: forfeits genuine continuation trades; N must stay small.

**P18. Economic-viability gate at entry.**
What: enter only when expected move scale (e.g., ATR(14) or the config's own initial-SL range) ≥ m × round-trip cost, m ∈ {5, 10}.
Why: a trade whose realistic target is ~$1/oz against a $0.50 toll needs 67% WR just to break even — the current median trade IS that trade (median RT friction $0.495, avg same-bar event −$1.08). This gate encodes "don't play when the pot is smaller than the rake" directly.
Validation: P2 with the gate as a boolean lever → shadow.
Risk: low-vol regimes go silent (that is the point); calibrate m per TF.

**P19. Friction-aware hour filter (held-out validated).**
What: block entries in the empirically worst friction hours (session data: UTC 04 = $120.5, 07 = $155.4 of RT cost vs 06 = $5.98), validated on *out-of-sample* sessions before adoption.
Why: friction varies ~26× by hour; avoiding two hours would have saved ~$276 of the $509 toll that session. Requires P3's spread feed to be regime-robust rather than one-night folklore.
Validation: ≥5 sessions of P3 spread capture (European/US sessions explicitly requested by the parity report) → then P2 → shadow.
Risk: V-11's in-sample-overfit warning applies verbatim — this is the one filter with a documented overfit precedent; held-out validation is mandatory.

**P20. De-duplicate the M2 trio.**
What: the 3 live M2 configs (V11/V15/V13-M2) share the same skeleton and fire near-identical signal streams (session counts 81/84/102, all ~92–100% same-bar). Run ONE representative + its corrected twin instead of three near-clones.
Why: three near-identical configs pay 3× friction for ~1× information. Live PnL confirms co-movement (all three bled together on 15–16 Jul: −50.7k/−65.2k/−73.7k CLP). Freed cap slots (6 fichas) fund two extra shadow variants.
Validation: signal-overlap matrix from audit logs (cheap, offline) before any roster change.
Risk: trader mandate (D104) chose these 4 — this proposal REQUIRES trader sign-off; it reallocates, not deletes.

### Tier C — Entry fills: attack entry slippage and spread-crossing

**P21. Limit-order entries at signal price.**
What: enter via limit at signal-bar close (or better), expiry at next bar close; unfilled ⇒ signal skipped.
Why: diagnostic §6-#6's own estimate: +$100–250/night if fill-rate holds. Limit fills also *earn* the queue instead of paying next-tick momentum (measured entry slip −0.25 $/oz mean, p10 tail −0.96).
Validation: tick replay for fill-rate honesty (P4) → shadow with paired market-entry twin.
Risk: adverse selection — you fill preferentially when price comes back (weaker continuation); the paired twin isolates exactly this.

**P22. Pending-stop entries at the confirmation level.**
What: place a server-side stop order at the breakout/confirmation level at bar close instead of market-ordering after the next cycle.
Why: converts up-to-15 s cycle latency into zero (server triggers the instant the level trades) and makes the fill *conditional on continuation* — entries only when the move is real. Honest implementation of "enter intra-bar," same principle as P6/P25.
Validation: tick replay → shadow.
Risk: stop-entry pays slippage in fast markets; stops-level constraints bound placement distance.

**P23. Spread gate at entry.**
What: skip any entry when live spread > threshold (baseline snapshot 0.60; threshold grid {0.55, 0.65, 0.80}).
Why: friction is the #2 gap component and is directly observable pre-trade (P3 feed). Refusing the worst quotes trims the toll's right tail (p90 RT cost = $2.33 — nearly 5× the median).
Validation: needs P3 capture first; then P2 replay with recorded spreads → shadow.
Risk: none structural; may correlate with the hour filter (P19) — measure jointly.

**P24. Cut executor latency: event-driven cycles.**
What: trigger the reconcile cycle on bar-close detection (poll 1–2 s around expected close) instead of a flat 15 s interval.
Why: every fill today happens 0–15 s late; measured entry slip (−$256 total/session) is partly pure latency. Cheap, strategy-neutral friction reduction that benefits ALL configs including the live 4.
Validation: A/B by interval setting on shadow twins; compare slip distributions from audit.
Risk: negligible; MT5 rate-limits are far above this cadence.

**P25. V-12 (intrabar entry), implemented honestly via resting stop orders, tick-validated.**
What: the program's runaway classic winner (net +$123k–232k, PF 14–1287 — flagged, not trusted) enters on intra-bar touches. Its only honest live form is P22-style pending stops resting at the trigger levels. Validate on ticks BEFORE any shadow deployment.
Why: if even a small fraction of V-12's classic edge survives honest tick-fill pricing, it dwarfs every other lever in this catalog; and if none survives, that closes the program's biggest open question. Either answer is worth one tick-replay run.
Validation: strictly P4 tick replay first (per D84's audit rule for too-good results); shadow only if it survives.
Risk: high prior that the edge is spike-capture look-ahead; treat as research, not a promise.

### Tier E — Trade-shape and regime redesigns

**P26. Retarget the trade shape: expected win ≥ 10× round-trip cost.**
What: redesign targets/trails so the median winner is ≥ $5/oz (vs. the current regime where median holds are 132 s and the same-bar event averages −$1.08): larger initial risk (k per V-01 knee), wider trails (P8), TP legs at multi-R (P11), holds of 30 min–hours.
Why: the toll is fixed per round-trip; the only structural escape is bigger numerators. Every measured fact says the current shape (scalper-frequency, sub-$1 excursions) sits exactly where friction is maximally destructive. This is the portfolio-level statement of which all Tier A/B items are components.
Validation: P2 defines the frontier (net_honest vs hold-time scatter); best cells → shadow.
Risk: fewer trades ⇒ slower statistical verdicts; pre-register sample sizes.

**P27. Regime gating for M15 (trade the windows that pay).**
What: enable M15 configs only when a regime classifier (the OOW doc's own TREND rule `|Δ|>0.5×range`, or ATR(14) percentile bands from D1: W2≈9.47 vs W1≈5.21) signals W2/W3-like conditions; stand down in W1-like.
Why: under live-fill, M15 is positive in W2 (trend-extreme) and W3 (range) but negative in IW/W1 — the edge is regime-conditional, and the regime is observable. Overlaps deliberately with the plan's genoma-v2/regime work (P6 of the original plan; tracker OPEN #5).
Validation: classify all historical windows, verify the gate would have selected the paying cells out-of-sample → shadow with the gate live.
Risk: regime classifiers lag transitions; use hysteresis.

**P28. Honest rebuild of the batch-7 best stack: S1 (V-13 re-entry, NO sar_adaptive) on M15 + wide trail.**
What: shadow config = M15 skeleton + `reentry_enable, reentry_max=2` + trail floor (P8) + honest oracle (P7), explicitly WITHOUT sar_adaptive.
Why: S1 was M15's best in batch 7 (+43,460 classic; and batch 7 recorded *interference* when sar_adaptive was stacked on M15 — S3 < S1); V-13 was the only lever that won/tied on all four TFs by ADDING population rather than filtering. Rebuilding the best-known combination under the honest judge is the shortest path to a deployable positive-expectancy config.
Validation: P2 → shadow (this is a flagship shadow candidate).
Risk: re-entry × friction tension (see P17) — the honest sweep arbitrates.

**P29. Short-side asymmetry handling.**
What: side-specific parameters: wider short trails or a short-only spread/hour gate.
Why: measured: shorts lost more (−$448 on 459 positions vs longs −$314 on 552) and pay a higher exit toll (median +0.71 vs +0.19 $/oz — market exits cross the ask). The sim is side-symmetric on bid-based bars; live is not. A cheap, measurable correction the sim can encode once P3's ask data exists.
Validation: P2 with side-split costs → shadow.
Risk: halving population per side slows verdicts; keep both sides, just asymmetric params.

**P30. Per-config daily loss budgets with auto-suspend (portfolio circuit breaker).**
What: executor-level rule: config exceeding −$X closed-PnL in a rolling day ⇒ suppress its OPENs until human review (kill-switch stays global; this is per-config).
Why: the 15–16 Jul night bled for 7 straight hours after a positive first hour (+11.3k → −196k CLP by morning, WR 30%) with no mechanism to stop an individually failing config. Whatever variants win, the shadow program *needs* bounded downside per candidate to run unattended; this also caps the cost of any future silent regression (cf. the machine-2 incident).
Validation: replay budget levels against historical nights (would it have saved the night without killing good days?).
Risk: budget too tight truncates recoverable days; calibrate on replay, pre-register X.

---

## Part III — Deployment frame for the shadow program (D103)

**Capacity math:** `MAX_FICHAS_TOTAL = 60`; live roster uses 12 (4 configs × 3 fichas) ⇒ **48 slots ≈ 16 shadow configs** per wave. The catalog intentionally exceeds one wave: P2's honest re-ranking selects each wave's 16.

**Recommended sequence:**
1. **Now (no market needed, it's the weekend):** P1 (oracle flag, on twins), P3 (spread capture, deploy Sunday), P5 (metric), then **P2 — the honest re-sweep** (pure compute).
2. **Wave 1 shadows (highest prior × lowest effort):** P7 (honest twins of the live 4 — the cleanest A/B), P9 (no-modulation twins), P8 (wide trail), P28 (S1-M15 rebuild), P15 (M15 roster), P30 (loss budgets protecting the whole experiment).
3. **Wave 2 (needs P3/P4 data):** P6 (server-SL-only), P11/P12/P14 (TP/BE/role-split), P18/P19/P23 (economic gates), P24 (latency).
4. **Research track (tick-gated):** P4 → P22/P25 (pending-order entries, V-12 verdict).

**Measurement discipline (pre-registered per variant):** paired vs live/shadow control on the same days; primary metric net_honest (P5); minimum sample before verdict (e.g. ≥30 round-trips or ≥10 trading days for M15); kill criteria = P30 budget; NO promotion to the live roster without trader sign-off (D104 holds) and the parity gate untouched.

**What this catalog does NOT change:** the 4 live configs keep running as-is (trader mandate D104); REAL account stays read-only; all shadow work is DEMO 2883015767, magics 721000+, guard-checked.

---

*Synthesis and proposals: orchestrator (this document's Part I §5 principle and all Part II rationales). Facts: 2 Sonnet 5 read-only investigators, re-verified against source at `emasar_variant.py:502-599`, `run_live_20.py:120-186,403-439`, `live_configs_20.py:42-159`, `gen_variant_batch1.py:46,126-137,513-537`. Primary research corpus: `docs/REPORTE_DIAGNOSTICO_LIVE_VS_TEORIA_2026-07-14.md`, `docs/superpowers/research/2026-07-13-livefill-bound.md`, `…-emasar-variants-batch{1..7}.md`, `…-2026-07-14-diag-h{1,2,3h5,4}*.md`, `…-candidates-top5.md`, `…-realtick-estimate.md`, `…-2026-07-15-signal-replay.md`.*

---
---

# PART IV — PROGRAM EXPANSION TO 66 PROPOSALS (2026-07-19)

**Authorized by user 2026-07-19.** Supersedence notes: (a) the Addendum's §1 corrections are authoritative over Part II where they conflict (P1 is a small tested change, not one-kwarg; shadow infra is new in-process code; TP is new executor code); (b) **P20 is RETRACTED as written** and replaced by P50 — similarity is a hypothesis to test, never a reason to drop configs (user directive: capacity shapes sequencing/waves, never scope); (c) **P6b (tick-trailing executor)** from the Addendum is a full member of the catalog. Count: P1–P30 + P6b + P31–P65 = **66**.

New evidence base for this expansion (session 2026-07-19, investigators E/F): the extreme-runs inventory (`scratchpad/inventory_E_extreme_runs.md`) and the methodology-flaws inventory (`inventory_F_method_flaws.md`). Headline findings driving Part IV: `sentinel_engine/opt/` (walk-forward + purged splits + DSR + 4 selection guards, 5,318 lines) exists and was never used by the variant program (0 imports; 150–250+ uncorrected evaluations); the V-12 giants are audit-DEAD (causal-fill survival −1.0…−2.6%, `2026-07-13-v12-lookahead-audit.md`) but the OOW2/W2 giants ($68k–146k) were NEVER bias-audited (regime-caveated only), and honest re-pricing already shows **W2-M15 survives at ≈+$9.3–9.6k (PF 1.24–1.26)** — the only positive honest region; SuperTrend p14x3-M15 is the one legacy family whose numbers survived real-tick validation ($17,512 ≈ $17,510).

### IV.A — Green-lit program items (user-approved 2026-07-19)

**P31. W2 forensic audit (the missing audit for the biggest unaudited family).** Run the V-12-style 5-test protocol on ALL OOW2/W2 extreme cells (§2 rows 4–20 of inventory E): entry-improvement forensics, same-bar exit census, MFE/MAE signature, causal re-fill, honest live-fill+friction re-pricing. Why: these runs carry the largest unexplained upside in the registry; the "not for averaging" caveat is an explanation, not a verification. Outcome either kills them or hands us P32's foundation. Validation: it IS validation (L0→L2 for the family).

**P32. W2-regime specialist strategy.** If P31 confirms the surviving honest edge (W2-M15 ≈ +$9.5k), build the strategy that *detects* W2-like conditions (ATR14 percentile bands: W2≈9.5 vs IW≈5.6; the OOW doc's trend rule `|Δ|>0.5×range`) and deploys M15 configs hard only then, standing down otherwise. Why: the registry's own giants say the edge is regime-conditional; conditional deployment converts "not for averaging" into "trade only the payable regime." Validation: regime-classifier hindcast across all windows → honest sweep gated → shadow.

**P33. V-12-pending (the honest cousin of the dead giant).** Resting LIMIT order at the *causally computed* pullback EMA level (from bar i−1, placed at close of i−1, next-bar expiry). Why: the V-12 audit killed `entry_timing=1` (fill priced off the unclosed bar) but never tested legitimate intra-bar capture at a causal level — the only untested door left on the program's biggest headline. Prior: modest. Validation: new sim entry mode (L1) → tick replay (L3) → shadow only if it survives.

**P34. SuperTrend p14x3-M15 revival.** Port the one legacy family that PASSED real-tick validation (screening $17,512 ≈ real-tick $17,510; explicitly "justo lo que mató a Pedro" — i.e., NOT a simulator artifact) into the honest ladder as its own family; also the trader line already names it (T1, D78). Why: a validated non-EMASAR edge, ignored while we mined EMASAR. Validation: honest sweep on our lake → shadow.

**P35. Rigor retrofit: `sentinel_engine/opt` becomes THE selection pipeline.** All sweeps run through anchored walk-forward + purged splits + DSR + the 4 selection guards + the `preregistration` table. Why: 150–250+ evaluations selected by `if net > best_net` on one month manufactures phantom winners even with honest fills; the cure is already written (5,318 lines, zero imports). This is the selection-side twin of the same-bar discovery. Validation: re-rank the entire program; report which "winners" survive DSR.

**P36. Execution-parity suite (new standing gate).** Pinned-behavior tests for `simular_variant` in BOTH fill modes (currently zero parity protection on the trading hot path); `return_state`+`live_fill_mode` combination tests (the open_state SL bug's class); state-carry ≡ sliding-window equivalence tests; `check_live_sim_parity.py` (D88) promoted to a scheduled nightly job with divergence KPIs tracked in the registry. Why: every fidelity claim in this program rests on the sim meaning what we think it means.

**P37. State-carry incremental engine.** Process only the newly closed bar per cycle instead of re-simulating 10,000 bars × N configs (~8–10 s/cycle today, ~1000× waste). Why: unlocks 1-s cadence (P24/P6b) AND large shadow rosters simultaneously; currently the compute wall caps both. Risk: documented sliding-vs-carry divergence on fast TFs — gated on P36. Validation: bit-equality vs full re-sim over recorded days.

**P38. Registry integrity & fidelity truth-in-labeling.** Additive-only migration: `validity` marking for the 39 TOKATA duplicate pairs (`DUPLICATE_INGEST` — user decision 2026-07-19: mark, never delete), V-12 family (`LOOKAHEAD_CONFIRMED`), OOW2 family (`REGIME_UNAUDITED` → post-P31 verdicts), legacy 3-pip stops (`INEXECUTABLE_STOP`); fidelity badges surfaced in the RUNS UI (the $231k rows must LOOK like screening-tier artifacts); fix the `engine` CHECK violation; backfill NULL mae/mfe. Why: the UI currently presents phantom money as treasure — the research system must tell the truth about its own history. All markings via new columns/audit_log rows; zero row deletions/mutations of original fields.

**P39. Dukascopy acquisition (user decision: full M1 bars + ticks ~2019→now).** Independent-feed history: M1 full available history + recent-years ticks; ingest to lake with `feed` provenance column. Why: unblocks the P4 walk-forward study (standing directive), provides multi-year honest windows (P40) and independent tick replay. Caveat carried explicitly: Dukascopy ≠ Capitaria feed — robustness tool, NOT broker-parity tool.

**P40. Multi-year honest window expansion.** Once P39 lands: extend the honest sweep from 4 windows/1 symbol-month-regime to N years of regime-labeled windows with walk-forward anchoring. Why: every current verdict rests on ≤4 windows, one of which (W2) dominates the upside; year-scale evidence is what "best possible strategies" actually requires.

**P41. Cross-feed robustness check.** Measure Capitaria-vs-Dukascopy bar divergence; re-run top honest configs on both feeds; flag any config whose edge is feed-specific. Why: an edge that dies across feeds is microstructure noise, not signal.

**P42. Own tick+spread archive (start immediately).** Daemon recording Capitaria tick stream + spread continuously (extends P3 from per-cycle to full stream). Why: every future month becomes fully replayable at L3 against OUR broker's real feed — the data we keep wishing we had for last month.

### IV.B — Sizing & risk family (an entirely untested axis — everything to date ran flat 0.01)

**P43. Volatility-targeted sizing.** Volume ∝ 1/ATR14 (constant $-risk per ficha). Why: fixed lots make PnL a hostage of the volatility regime; risk-normalizing is the cheapest known variance reducer and changes net WITHOUT touching signals. Validation: pure L1/L2 re-scoring of existing sweeps (sizing is orthogonal to signal replay).

**P44. Drawdown-responsive throttle (anti-martingale).** Per-config size multiplier stepping down after rolling-DD thresholds, restoring on recovery. Why: the 15–16 Jul night bled 7 straight hours at full size; a throttle converts tail nights into shallow ones at modest cost to winners. Validation: replay against recorded nights.

**P45. Fractional-Kelly per config.** Estimate edge/variance from honest sims, cap at ¼-Kelly, floor at broker min-lot. Why: principled aggression where honest edge is proven, principled timidity where thin — directly serves "maximize profit / minimize loss." Depends on P35's honest league table.

**P46. Escalera-value test (1 vs 2 vs 3 fichas).** Same signals, ficha-count grid, honest fills + friction. Why: 3 fichas triple ticket-count frictions and MODIFY load for the same signal; the ladder's value was never isolated under honest pricing.

**P47. Risk-parity portfolio allocation.** Allocate volume across the roster by inverse honest-risk contribution instead of equal lots. Why: the portfolio's realized risk today is an accident of per-config volatility; parity allocation is the standard fix. Validation: L2 portfolio backtest over recorded + honest-sim periods.

### IV.C — Portfolio & cross-config family

**P48. Correlation/netting study.** Measure the cross-config signal + PnL correlation matrix (never measured); simulate portfolio-level netting of opposing fichas (a long and a short open simultaneously cancel exposure but pay double spread today). Why: 20 configs were always run as 20 islands; the portfolio view may find free money (netting) and hidden concentration (all-M2 clustering). 

**P49. Meta-selector (rolling best-of).** Weekly/daily re-selection of the deployed subset by rolling honest performance with DSR-corrected thresholds. Why: regime adaptation WITHOUT parameter mutation — the roster becomes the adaptive layer. Validation: hindcast the selector across the honest multi-window table (P40).

**P50. Signal-overlap experiment (P20 rewritten per user directive).** Measure M2-trio (V11/V15/V13-M2) signal overlap and PnL co-movement from recorded live + honest sims; then test merged-vs-separate as a hypothesis. Nothing is dropped on similarity priors; if >95% redundancy is MEASURED, that's a finding for the trader to act on. 

### IV.D — Entry/exit additions & long-shots

**P51. Time-stop exits.** Max-hold N bars grid (close at bar-close after N). Why: honest-fill trade shape shows most excursion value realizes early; a time-stop caps the friction-bleeding tail of stale holds. Cheap L1 grid row.

**P52. Partial-close ladders.** Close fractional volume at TP1 (e.g. 1/3 at 1R), trail remainder — MT5 supports partial position close via DEAL with reduced volume. Why: banks intra-bar capture (resting TP, §I.5 principle) while keeping tail exposure with ZERO extra tickets (vs 3 separate fichas). Interacts with P46.

**P53. Re-entry v2 (honest re-judgment of V-13).** Reentry × cooldown (P17) interaction grid under honest fills + friction. Why: V-13 was the program's only all-TF winner under the corrupted judge; its friction-adjusted truth is unknown and it directly tensions with the anti-churn thesis — the grid arbitrates.

**P54. Confirmation-bar entry.** Enter only if bar i+1 confirms direction (close beyond signal-bar extreme). Why: trades fewer, later, better-confirmed entries — the anti-V-12: pays worse prices for higher win-rate; under honest friction the tradeoff was never priced.

**P55. Stop-and-reverse (SAR-true).** On opposite signal, reverse position (single net order) instead of exit-then-wait-then-enter. Why: halves round-trips per direction change → direct spread-toll reduction at identical signal content.

**P56. News/calendar gate.** Block new entries ±N min around high-impact events (the service already has a `news_items` feed table). Why: spread/slippage spikes concentrate around events (measured worst-hour friction 26× the best); the gate is a long-shot with a clean causal story. Held-out validation mandatory (V-11 lesson).

**P57. Weekend/rollover rules.** No new entries in the final pre-close window Friday; swap-time (rollover) avoidance; gap-risk study on Sunday opens. Why: never analyzed anywhere in the corpus (explicit gap); XAUUSD weekend gaps against 3-ficha exposure is an unpriced tail.

**P58. Spread-percentile adaptive gate.** Refine P23: entry allowed only when live spread < rolling percentile (e.g. p40) rather than a fixed threshold. Why: adapts to session structure automatically; needs P3/P42 feed. 

### IV.E — Microstructure & execution

**P59. MODIFY governor.** Batching + rate-limiting + improvement-threshold gating for SL updates, parameterized by the Capitaria vendor's official limits (answers pending). Why: prerequisite for P6b at any cadence; one bar-cadence night already produced 99 failed MODIFYs.

**P60. Deviation tuning.** Grid the `deviation` (slippage tolerance, today 20 points) against measured reject-rate/slippage tradeoff. Why: never tuned; wrong in either direction costs money (rejects vs bad fills).

**P61. Demo-vs-real microstructure dossier (design-only).** Compile vendor answers + literature on demo-fill optimism; design (NOT execute — REAL account stays read-only, hard rule) the eventual micro-lot real-validation protocol as a future user decision gate. Why: every live number we own is demo; the gap to real fills is our last unmeasured fidelity layer.

**P62. Full-path latency telemetry.** Timestamp every stage (bar close → signal → order_send → broker fill) into the audit log; nightly distribution report. Why: the dataset that prices P24/P37/P6b and detects degradation; currently we infer latency indirectly.

### IV.F — Governance & process (make the too-good rule and honesty structural)

**P63. Formalize the too-good trigger.** Registry rule: WR>90% ∨ PF>50 ∨ net>x → run auto-flags `AUDIT_REQUIRED`, blocked from any league table until the 5-test protocol passes. Why: today the rule is folklore (referenced as "D84", defined nowhere); the V-12 and Pedro episodes prove it earns its keep.

**P64. Preregistration enforcement.** Sweep harness refuses to run a grid without a `preregistration` row (hypothesis, metric, thresholds, sample plan); results link back to it. Why: the table exists (476 rows) and the batch scripts bypassed it — the discipline exists on paper only.

**P65. Nightly sim-vs-live residual KPI.** The D88 parity checker runs scheduled every session; residual (sim-expected vs realized, per config) stored and charted in the registry; alarm on drift. Why: "as close as possible to bit-identical" is a *maintained* property, not an achieved one — this is its instrument.

### IV.G — The Honest Re-Run Manifest (the re-dos and the forgotten, per user directive)

Everything ever judged by the corrupted engine gets re-judged at L1/L2 through the P35 pipeline. Explicit inventory:
1. **All 15 levers + 4 extensions, batches 1–7** (V-01…V-15, super-stacks S1/S2/S3) — full re-run honest, all 4 TFs, all available windows (verdicts like "V-04 loser / V-05 inert / V-02 loser" are untrustworthy: they competed against perfect exits).
2. **The 7 configs D90 never covered** (V10-M15, V15-M15, V09-CTRL-M15, V11-M2, V10-M5, V13-M2, V09-CTRL-M5) — zero live-fill evidence exists for them today.
3. **The 20/24 batch-7 grid cells never persisted** (docs-only) — re-run and persist ALL cells (P38 policy: every cell into the registry).
4. **V-07 (AC-decel runner exit)** — verdict never fully captured; re-run and record.
5. **The OOW2/W2 family** — via P31's full forensic protocol.
6. **V-12 family** — closed (audit-dead) EXCEPT the P33 pending-order cousin.
7. **SuperTrend p14x3** (P34) and any other credible legacy variant surfacing from the `REPORTE_MEJORES_VERSIONES` dossier — through the same ladder.
8. **The 4 live configs themselves** — honest twins (P7) as the baseline reference row of the entire table.

### IV.H — Machine-2 first deployment: the FIXED4 (user directive 2026-07-19)

Machine 2 (isolated replication control) runs, once its zero-positions issue closes: the **live-4 unchanged** PLUS **FIXED4** — the same 4 configs with the obvious fixes from this program, as in-process shadows (magics 721010/721020/721030/721040):
- `live_fill_mode=True` oracle (post-P1 sim fix) — exits the executor can actually execute;
- `ac_modulate=False` — removes the look-ahead-harvester trail collapse (P9);
- ATR trail floor — new additive kwarg `trail_atr_floor_k=1.5` (trail ≥ 1.5×ATR14) so the honest exit mechanism is structurally reachable (P8).
Same signals, honest exits, paired head-to-head against the originals on the same machine, same market — the cleanest possible A/B of the entire thesis. Requires: P1 sim fix + minimal in-process shadow infra (Addendum §1.2) shipped to `alvaro`.

### IV.I — Capacity & scheduling notes (updated)

66 proposals ≠ 66 shadow slots. Offline items (the majority) are compute-only and UNCAPPED — the mega-sweep + manifest run in hours at ~23k bars/s. Live-shadow items queue in waves of ≤16 configs (48 ficha slots); wave membership is decided by the P35 honest league table, never by prior exclusion. Program deadline (user): offline mega-sweep + re-runs + W2 audit complete before **2026-07-20 05:00 Chile** (= 05:00 server). Machine-2 FIXED4 pack prepared same night, deployed when their diagnosis closes.

---

*Part IV authored 2026-07-19 by the orchestrator after user green-light; evidence from investigators E (extreme runs) and F (methodology flaws), verified against `data/research.db` live queries, `2026-07-13-v12-lookahead-audit.md`, `REPORTE_VALIDACION_OOW_EMASAR_2026-07-13.md`, `REPORTE_MEJORES_VERSIONES_ESTRATEGIAS_2026-07-13.md`, and `sentinel_engine/opt/*`.*
