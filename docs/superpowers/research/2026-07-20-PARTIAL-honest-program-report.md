# Honest Program — "Complete the 66": PARTIAL results report (Waves 1–3)

Branch `alvaro` · 2026-07-20 · execution = subagent-driven-development.
Scope of this report: the ~40% of the program executed so far (Waves 1–3 of 7). Waves 4–7
(portfolio, legacy/regime revivals, governance, holdout) are in progress after this snapshot.

> **Bottom line so far:** across **195 honestly-priced, prereg'd, walk-forward + DSR-gated
> configurations** on one comparable timeframe {IW,W1,W2,W3}, **no strategy shows a
> statistically significant edge** (DSR 0.0 / honest p 1.0). The M15 V-15 family remains the
> only thing with a small real-looking net, **stop-and-reverse (SAR) on M15** is the best
> *directional* lever, and **vol-target sizing** adds a small further lift — but none clears the
> multiple-testing luck bar. The honest verdict is not yet "we found a winner"; it is "we have
> ruled out a large space cleanly, and isolated one stacked candidate to test out-of-sample."

---

## 1. What the honest pipeline is (why these results are trustworthy)

Every backtest in this program runs through the *designed* honest procedure, not the old
corrupted engine:

- **`live_fill_mode=True`** — server-side SL honored intrabar (no ghost same-bar exits).
- **flat-0.5 spread cost at fill**, fixed lot **0.10**, one instrument (XAUUSD).
- **Anchored walk-forward + purged splits**, **4 selection guards**, and a **Deflated Sharpe
  Ratio** whose trial family = the full manifest size (so searching more configs *raises* the
  bar you must beat).
- **Pre-registration enforced** — the harness refuses an un-preregistered grid.
- **One comparable window set {IW,W1,W2,W3}** across all waves → every strategy sits in one
  league and re-runs reproduce identical nets.

This is why a naive "median-net winner" can still be reported honestly as **not significant**:
the DSR asks whether the winner's Sharpe beats what the *best of N random tries* would produce.

## 2. Wave 1 — the full honest re-run (the "full picture")

Closed the gap between the overnight subset and the full lever set: **151-cell comparable league**
(102 overnight ∪ 49 previously-un-run gap cells; V-01…V-14 across 4 TFs).

- **Result: DSR 0.0 / p 1.0.** No significant winner even on the full comparable league.
- The tie-pool is the **same 9 M15 V-15 configs**; every newly-run gap lever (V-01…V-14) came
  back **negative** (e.g. `GAP-V13-M1` net −79,810).
- **Finding:** the un-run levers were un-run because they don't work honestly, not because they
  were promising-but-skipped. The M15 V-15 family is the only real edge carrier.
- Artifact: `2026-07-20-honest-league-full.{json,md}` (commit 7f1b4c1).

## 3. Wave 2 — four new additive sim levers + expanded sweep

Four levers added to `simular_variant`, each an **additive kwarg with a no-op default**
(classic byte-identity confirmed per lever), TDD, full parity gate (318) green:

| Lever | Proposal | Commit | Sweep-B outcome |
|---|---|---|---|
| `max_hold_bars` (time-stop) | P51 | 43a8a7d | TS40 marginal, TS20 negative |
| `confirm_bar` (confirmation entry) | P54 | a3f34ed | **dead — strongly negative everywhere** |
| `stop_and_reverse` (SAR) | P55 | 6e56581 | **best lever — fills the top tie-pool on M15** |
| `active_fichas` (escalera count) | P46 | 3afa4a1 | F2 mildly positive, tie-pool-neutral |

- **P52 (partial-close ladder) DEFERRED** — the engine has no fractional volume (fichas are unit
  1.0); cannot be honestly simulated without a stake-fraction model. Reported, not skipped.
- Expanded manifest → **195-cell v2 league** (151 ∪ 44 Wave-2 lever grids; commit 8e23797).

**Sweep B result (`2026-07-20-honest-league-v2.md`, commit 04a725e):**
- Naive median-J winner **`HON-W2-S6-K2P0-M15-SAR`** (stop-and-reverse, M15 V-15); SAR variants
  occupy the entire top of the tie-pool.
- **Still DSR 0.0 / p 1.0:** observed Sharpe 2.72 vs null-max 13.59 over 195 trials.
- CONF dead-negative; all M1/M2/M5 deeply negative (churn). SAR is the one lever that
  *directionally* lifts M15 — worth carrying forward, presumed noise until holdout says otherwise.

## 4. Wave 3 — sizing & risk (P43/P45/P46/P47), re-scored offline

Re-scored existing honest trade rows (no fresh sim except P46, which Wave-2 covered):

- **P43 vol-target (`vol ∝ 1/ATR14`) — a real small improvement.** Reweighting each trade by
  1/ATR14 (causal, from the lake) lifts the best M15 net-series Sharpe **2.72 → 3.10** and the
  whole tie-pool median **−0.064 → +0.022** (it down-weights noisy high-ATR entries). Pipeline
  validated against stored Sharpe to 6 decimals. **But still DSR 0.0 / p 1.0** — 3.10 falls short
  of both the full null-max 13.59 and even the narrower M15-only null-max 4.03.
- **P45 fractional-Kelly & P47 risk-parity — provably Sharpe/DSR-invariant** as per-config
  constant multipliers (verified against `deflated_sharpe_ratio`: mean/std + scale-invariant
  skew/kurt). They are capital-allocation, not edge → their real test is **portfolio composition
  (Wave 4)**.
- **P46 escalera — needs fresh sim**, partially covered by Wave-2 `active_fichas` grids
  (tie-pool-neutral-to-negative). No escalera lift.
- Artifact: `2026-07-20-wave3-sizing.md` (commit 594a9af).

**The "small improvements add up" tension, stated honestly:** SAR (+directional) and vol-target
(+0.38 Sharpe) *do* stack into the best config seen — but in-sample stacking also raises the
luck bar as fast as it raises Sharpe. Small edges only bank if each **survives out-of-sample**.
The best stacked candidate — **SAR + vol-target on M15** — is therefore the **#1 holdout
candidate** for Wave 7.

## 5. Coverage ledger (which of the 66 are done / deferred / parked)

- **Done & honest:** all V-lever re-runs (V01–V15 family), P43, P45, P46, P47, P51, P54, P55.
- **Deferred (technical):** P52 (no fractional volume model).
- **In progress (this session):** Wave 4 P48/P49/P50 (portfolio); Wave 5 P34/P32/P33 (legacy/
  regime); Wave 6 P36/P63/P65 (governance); Wave 7 holdout + consolidated league.
- **PARKED — blocked by external factors (honestly out of scope this session):**
  - **P39–P42** — Dukascopy tick acquisition / multi-year windows / cross-feed: external data,
    credentials, long-running download.
  - **P59–P62** — MODIFY governor, deviation tuning, demo-vs-real dossier, latency telemetry:
    Capitaria vendor limits / live-execution (REAL stays read-only).
  - **P6b** — tick-trailing executor: live executor, gated on P59.
  - **P37** — state-carry incremental engine: large rewrite, gated on P36; only if time remains.

## 6. Honest headline for the user

We have not (yet) found a strategy that beats the honest luck bar. What we *have* produced is
rare and valuable: a **clean, comparable, corruption-free elimination** of a 195-config space,
with the surviving signal narrowed to **one family (M15 V-15) + two stacking levers (SAR,
vol-target)**. That single stacked candidate is what Wave 7's out-of-sample holdout will
adjudicate. Everything negative here is a real "this doesn't work under honest pricing" — which
is exactly the picture the program was built to deliver.
