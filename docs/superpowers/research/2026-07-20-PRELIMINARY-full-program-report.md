# Honest Program "Complete the 66" — PRELIMINARY FULL REPORT

> Status: PRELIMINARY (issued while the belt-and-suspenders `tests/opt/` suite `bnmn8ngjk` runs; not a
> correctness gate). Date: 2026-07-20. Branch `alvaro`. Repo `D:\FOREX`. Author: honest-program orchestrator.
> This complies with the directive "continue — do not block on the background run." The FINAL professional
> assessment (reserved by the user for program completion) will supersede this once the whole-branch review
> and the patient-exit design land.

---

## 1. Executive summary

- **Research verdict (Waves 1–7, honest pipeline):** across everything run through the corruption-free
  pipeline (walk-forward + Deflated Sharpe Ratio + guards, `live_fill_mode`, flat-0.5 cost, fixed lot 0.10,
  windows {IW,W1,W2,W3}), **no DSR-significant, champion-beating strategy exists.** The program's real
  output is a *clean elimination* of a large search space down to one thin family.
- **The one surviving family:** the **M15 V-15 SAR** configs are the only pooled-net-positive cells
  (26 of 225), and they **hold their sign out-of-sample** on a genuinely untouched holdout month — but they
  remain **sub-luck-bar (DSR 0.0 / p 1.0)**. So: *corroborated direction, not a proven edge.*
- **The minimum-TP idea was decisively refuted** — it is the single most value-destroying lever tested.
- **Go-live:** the DEMO is armed with a **7-strategy roster** (5 M15 V-15 SAR + V11-M2 experiment +
  SuperTrend-p14x3-M15), entering **only at the thinnest spread** via an adaptive running-minimum gate.
- **First live round netted −58,445 CLP** — a textbook live confirmation of the *clone-concentration* risk:
  the 5 near-clone M15 shorts whipsawed out as a bloc; the only winner was the *different* line (V11-M2).
- **Primary improvement hypothesis:** a **bounded "stop-out-and-wait" / patient-exit** mechanism (not
  re-entry, which re-pays spread) to cut whipsaw losses. To be designed and validated in the honest pipeline.

---

## 2. Methodology (why these numbers are trustworthy)

Every result is produced by ONE comparable league:
- **One growing manifest** → **one DSR league** on fixed windows {IW,W1,W2,W3} (M5/M15/M2 as applicable),
  **fixed lot 0.10** (`_B1.LOT`), so all cells are comparable *by construction*.
- **`live_fill_mode` + flat-0.5 cost** — this is the whole point: it removes the *overly-optimistic close /
  same-bar look-ahead* behaviour that contaminated the legacy reports. Legacy un-validated sim reports are
  therefore **NON-comparable** and excluded from every go/no-go (comparability rule D17).
- **Deflated Sharpe Ratio** penalizes for the number of trials searched (the "luck-bar" = expected max
  Sharpe under a skill-less search). Beating raw Sharpe is not enough; you must beat the luck-bar.
- Every new sim lever is **additive with a no-op default + a pinned byte-identity test**, so the original
  league stays reproducible (D7). PROD stack untouched; DEMO-only.

---

## 3. Research results by wave

| Wave | Scope | Result |
|---|---|---|
| 1 | 151-cell comparable league (gap levers) | No significant winner; all new gap levers negative. DSR 0/p1. |
| 2 | 4 additive levers (time-stop, confirm-bar, SAR, ficha-count) + Sweep B (195 cells) | SAR is the best directional lever on M15; still sub-luck-bar (Sharpe 2.72 vs null-max 13.59). |
| 3 | Sizing | Vol-target = small real lift (Sharpe 2.72→3.10) but no rescue; Kelly/risk-parity provably Sharpe/DSR-invariant → portfolio-level only. |
| 4 | Portfolio | No real diversification: near-clone engine, 5.9% netting, meta-selector deploys nothing, M2 trio 60–77% signal overlap. |
| 5 | Legacy/regime | SuperTrend p14x3-M15 positive in every window but THIN (PF~1.05); regime no-lift; V-12 confirmed pure look-ahead; V-10 loses everywhere. |
| 6 | TP variants + governance | **tp_min REFUTED** (see §4); trail-half neutral; governance suite built (§6). |
| 7 | Single-touch holdout | The M15 SAR family + SuperTrend HOLD their sign out-of-sample (see §5) — corroborating, not decisive. |

**Headline:** through all waves, DSR = 0.0 / p = 1.0. The best observed Sharpe (2.72) sits far under the
null-max (14.05 over 225 trials). No strategy is statistically distinguishable from luck.

---

## 4. The tp_min refutation (Wave 6 A-track) — detailed

Hypothesis tested: pairing the winning levers with a **minimum-viable take-profit** (tightest broker-legal
TP, armed at entry) would keep positions net-positive. Result (225-cell league v3, commit `bfc1b64`):

- tp_min is the **most harmful lever in the entire program.** On the champion it turns **+$13,355 → −$25k…−$28k**
  (Sharpe **+2.56 → −5…−12**); on the FIXED4 M2 lines it worsens −$90/125k to **−$146k…−$190k**. Every grid
  value {5,10,20,40} pips, every base.
- **Mechanism:** capping every winner at a few cents while the stop side still takes full losses destroys the
  payoff distribution. This is the exact caveat flagged before running it.
- **trail-half** (halving the trail distance) is **neutral** on the champion (byte-identical net — on M15 the
  SAR/ATR-floor exits bind before the trail) and slightly worse on the plain FIXED4-M15 line.

Only **26 of 225** cells are pooled-net-positive; **all are M15 V-15 SAR** variants. Top-5 pooled net:
`S6-K2P0 +49,111 · S7-TPNONE +32,683 · S6-K1P5 +32,493 · S7-TP1P0 +30,642 · S7-TPNONE-F2 +21,789` (all
sub-luck-bar).

---

## 5. Wave 7 single-touch holdout (commit `239cdc6`)

An honest catch: the league's {IW,W1,W2,W3} were the *walk-forward folds* → all in-sample. A genuinely
untouched month **HOLDOUT-2026-01 (2026-01-05→02-05)** was fixed *before* seeing results and each candidate
priced exactly **once**:

| Candidate | Trades | Net (USD) | PF | WR% |
|---|---|---|---|---|
| HON-W2-S6-K2P0-M15-SAR (winner) | 414 | **+16,457** | 1.39 | 37.7 |
| HON-W2-S7-TPNONE-M15-SAR | 540 | +8,936 | 1.19 | 36.7 |
| HON-W2-S6-K1P5-M15-SAR | 540 | +8,936 | 1.19 | 36.7 |
| HON-W2-S7-TP1P0-M15-SAR | 540 | +7,072 | 1.15 | 36.7 |
| HON-W2-S7-TPNONE-M15-SAR-F2 | 360 | +5,957 | 1.19 | 36.7 |
| SuperTrend-p14x3-M15 | 55 | +2,814 | 1.19 | 32.7 |

**Verdict: the family's sign HOLDS out-of-sample — corroborating, NOT decisive.** It does not overturn
DSR 0/p1; it is one autocorrelated monthly regime; no holdout DSR was computed (one pre-specified config per
family → nothing to deflate; fabricating a trial family would be dishonest).

---

## 6. Wave 6 governance (make honesty structural)

- **P36 execution-parity suite** (`3cb3d06`, 249 tests): sim parity across both fill modes + `return_state`
  combos + carry≡window equivalence, byte-exact including with `tp_min` active. Carry≡window pins are the
  foundation for a future state-carry engine (P37).
- **P63 AUDIT_REQUIRED auto-flag** (`7a3c8af`, scoped 74 tests green; full suite `bnmn8ngjk` running):
  auto-flags "too-good-to-be-true" runs. Threshold `too_good_to_be_true` keys off the DSR null-max luck-bar
  in `opt/registry.py`; flag persistence reuses the P38 `validity` column + `audit_on` primitive in
  `research/registry2.py` (actor `honest-program`, idempotent, won't overwrite foreign labels). Governance
  only — never mutates DSR/scores.
- **P65 sim-vs-live residual KPI** (`adb55d0`, 31 tests): decomposes `live_net − sim_expected_net` per config
  with by-design components broken out. Honest coverage finding: the audit log carries telemetry + fill
  counts but **no realized per-config P&L**, so it reports `insufficient_live_sample` rather than fabricate.
  → realized P&L for the final assessment comes from **MT5 `history_deals_get`**, not the audit log.

---

## 7. Go-live: roster, spread reality, adaptive gate

- **Spread reality (verified live, read-only):** XAUUSD on the Capitaria DEMO is **0.60 USD/oz and FIXED**
  (`spread_float=False`); the "0.5" is the sim's flat *cost proxy*, never a measured spread. We have never
  recorded anything thinner, nor seen it float (tick logging was off). This means a static "≤0.70" gate would
  wrongly admit 0.61–0.70; the correct gate is the **adaptive running-minimum** below.
- **Adaptive spread-gate** (GL-T2, `ca2aee2`, 289 tests): continuously captures spread to a persistent store,
  keeps the all-time **running minimum**, and **operates only when spread ≤ running-min + 1e-6** (a tiny float
  tolerance, NOT a band); pauses otherwise. Verified: **0.60 → SENT, 0.61 → SKIP, 0.70 → SKIP.** Exits/MODIFY
  are never gated. Honest caveat: a strict all-time-min ratchet trades less over time; harmless while spread
  is fixed at 0.60.
- **Roster (GL-T1 `b9870ce` + GL-T3 `dec5640`):** 7 configs, magics `7240x0` + `724070/71`.
  - 5 M15 V-15 SAR winners (ladder engine): `S6-K2P0, S7-TPNONE, S6-K1P5, S7-TP1P0, S7-TPNONE-F2`.
  - `V11-M2` — least-negative M2 line, run as a **spread-gated experiment** (no offline evidence it flips
    positive; the gate bounds its loss).
  - `SuperTrend-p14x3-M15` — a **different always-in engine** (single position, flips on the SuperTrend line);
    integrated CLEAN-ADDITIVELY (a flip = close-wrong-side + reopen), spread-gated on entry.
- **Armed** (D21 authorization; guard `assert_demo` verified on sanctioned DEMO **2883015767**): daemon
  `b4ieuhn7g` (single executor), `dry_run=False, 7 configs, AutoTrading ON`. SuperTrend opened first
  (`SENT OPEN magic 724071 retcode 10009`).

---

## 8. Live results so far (MT5 deal history — round 1)

The first live round has closed (positions flat between signal waves):

| Strategy | Realized (CLP) | Note |
|---|---|---|
| **V11-M2** (long) | **+10,931** (+3,641/+3,641/+3,650) | rode the up-move, trailed out in profit |
| S6-K2P0 (short) | −15,844 (3 fichas ≈ −5,280 ea) | stopped out |
| S7-TPNONE (short) | −14,378 | stopped out |
| S6-K1P5 (short) | −14,508 | stopped out |
| S7-TP1P0 (short) | −14,788 | stopped out |
| S7-TPNONE-F2 (short) | −9,859 (2 fichas) | stopped out |
| **REALIZED TOTAL** | **−58,445 CLP** | demo/paper |

**Honest interpretation:** the 5 M15 strategies are **near-clones** (Wave-4 measured 60–77% signal overlap).
They entered short together, gold ticked up, and they **all stopped out as a bloc** — then price reversed
down (a whipsaw: they exited at the worst point and missed the move they were right about). The only winner
was **V11-M2**, precisely because it is the *different* line. This is a live illustration that **"5 near-clone
strategies ≠ 5 independent bets."** Nothing malfunctioned — trend-followers short into a rising market lose at
their trail, by design. It is one small demo sample, not a verdict.

---

## 9. The 7 strategies — how each works

**Shared "EMASAR" ladder engine (configs 1–6, minus SuperTrend):** compares a fast 8-EMA to a slow 20-EMA for
trend direction (confirmed over 2 bars); enters 3 staggered units (fichas) in the trend direction; each unit
gets an initial stop at 2.5× the entry-bar range, then trails behind price (100-pip trail, never tighter than
a volatility floor = `trail_atr_floor_k × ATR`), with a Parabolic SAR riding underneath; exits on the
trailing stop. Let-winners-run / cut-losers-at-the-trail.

| Config | Distinguishing levers | Personality |
|---|---|---|
| S6-K2P0 (rank 1) | AC-modulation ON, ATR floor 2.0 | most room; best in-sample |
| S7-TPNONE (rank 2) | no AC-mod, floor 1.5, break-even at +1R | can't turn a winner into a loss |
| S6-K1P5 (rank 3) | AC-mod ON, floor 1.5 | rank 1 on a shorter leash |
| S7-TP1P0 (rank 4) | +1R break-even AND partial TP on F1 at +1R | banks a little early |
| S7-TPNONE-F2 (rank 5) | like rank 2 but only 2 units | smaller exposure |
| **V11-M2** | same engine, **2-minute bars**, V-11 tuning | fast, many trades; gated experiment |
| **SuperTrend-p14x3-M15** | **always-in** (period 14 × mult 3), single position, flips on the line | genuinely different behaviour; diversifier |

---

## 10. Key hypotheses & open questions (for the final assessment)

1. **Patient-exit ("stop-out-and-wait") — the primary whipsaw fix (D25).** Instead of dumping at the worst
   tick, hold through *bounded* adverse noise and exit at breakeven/profit "when possible." **Re-entry is
   de-prioritized** (retries re-pay spread). GUARDRAIL: waiting = holding risk → must be bounded (max adverse /
   max hold) and validated in WF+DSR; an unbounded hold is martingale, not an edge.
2. **Clone concentration.** 5 near-clone M15 shorts multiply one whipsaw. Consider trimming clones in favour
   of genuine diversity (V11-M2, SuperTrend, and future distinct strategies). The roster has headroom to 10.
3. **7th slot.** SuperTrend (built, live) vs *repurposing/adapting a winner* (a wider-stop or patient-exit
   variant of the champion). Decide head-to-head at the assessment.
4. **Spread reality.** With a fixed 0.60 spread, the "thinnest-window" gate only bites if the broker ever
   floats the spread; keep capturing to detect it.

---

## 11. What this is / is NOT (honesty ledger)

- IS: a clean, corruption-free elimination of a large strategy space; one family that is net-positive
  in-sample and sign-stable out-of-sample; a governance layer that makes honesty structural; a live-forward
  DEMO test with 7 strategies gated to the thinnest spread.
- IS NOT: a proven edge. DSR = 0 everywhere. The live roster is a **live-forward out-of-sample test on paper**,
  not a deployment of validated winners. Round-1 lost money. No claim of profitability is made.

---

## 12. Remaining work

1. `bnmn8ngjk` full `tests/opt/` suite → green → finalize `/brain` handoff (per user).
2. **Final whole-branch review** (`git merge-base master HEAD..HEAD`) — batched, the program's closing gate.
3. **Final professional assessment** — realized P&L from MT5 `history_deals`, clone-trim decision,
   patient-exit (D25) design + honest-pipeline validation, SuperTrend-vs-adapt-winner, roster to 10.

---

## 13. Commit & artifact index

- Levers/manifest: `0f3e7c0` (tp_min lever) · `da8326c` (manifest v3, 225 cells) · `bfc1b64` (league v3 + findings).
- Governance: `3cb3d06` (P36) · `7a3c8af` (P63) · `adb55d0` (P65).
- Holdout: `239cdc6` (Wave 7).
- Go-live: `b9870ce` (roster) · `ca2aee2` (adaptive spread-gate) · `dec5640` (SuperTrend 7th).
- Docs: `docs/superpowers/specs/2026-07-20-tp-variants-spread-gate-design.md`;
  `docs/superpowers/research/2026-07-20-{wave6-tp-trailhalf-findings, wave7-single-touch-holdout,
  wave6-p65-residual-kpi, honest-league-v3.*}.md`; this report.
- Live: daemon `b4ieuhn7g`, login `2883015767`, magics `7240x0` + `724070/71`. Ledger
  `.superpowers/sdd/progress.md`; brain thread `20260720-073733-7mwm`.
