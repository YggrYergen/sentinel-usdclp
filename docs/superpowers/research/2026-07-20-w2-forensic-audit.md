# W2 / OOW2 forensic audit (P31, honest program) — 2026-07-20

**Script:** `scripts/report/gen_w2_audit.py`
**Tests:** `tests/scripts/test_gen_w2_audit.py`
**Family under audit:** the 17 `sim-report-emasar-oow2-*` runs (W2 window
2026-03-02 → 2026-04-03), each carrying a $44–146k on-paper (classic) net.
B1 marked all 17 `REGIME_UNAUDITED` on 2026-07-19; this audit upgrades each to
`W2_AUDIT_PASS` or `W2_AUDIT_FAIL(<reason>)`.

Modeled on `gen_v12_audit.py` (the audit that killed the $123–232k V-12
family) and the atomic, additive-only validity-write pattern of
`mark_validity_2026_07_19.py` (single connection, single transaction,
`ResearchRegistry.audit_on`, actor=`honest-program`, accion=`validity-mark`).

---

## Protocol

Per oow2 run:

1. **TEST-1 — entry-improvement forensics.** Join each trade to its entry-bar
   lake OHLC and measure the mean SIGNED entry improvement vs bar *close*
   (spread stripped). A config that enters at close scores ≈ 0; a material
   favorable value would mean the fill beat any causal engine.
2. **TEST-2 — same-bar exit census.** Fraction of exits priced within the
   entry bar (`ts_out == ts_in`) — the intrabar same-bar trail-raise
   look-ahead signature.
3. **TEST-3 — causal sanity.** Verified per run from TEST-1, not assumed.
4. **TEST-4 — honest re-pricing.** The honest net under `live_fill_mode=True`
   + the flat 0.5 Capitaria spread at fill. Cells with an existing honest
   live-fill twin (D90 `gen_livefill_bound` + tonight's honest sweep) are
   **LINK**ed by full param signature (tf + engine params, ignoring only the
   free-text `variant` label and the `live_fill_mode` flag). Cells with no
   twin are re-simulated **FRESH** on the W2 window via
   `gen_oow_validation`'s machinery.
5. **TEST-5 — verdict.** `W2_AUDIT_PASS` iff the honest net clears the
   material profit floor ($1,000 over the W2 month at 0.10 lot); otherwise
   `W2_AUDIT_FAIL(reason)`. The on-paper net is reported for context but is
   **not** the pass criterion — a known-inflated figure cannot vouch for
   itself.

### Honest-twin matching (the key ambiguity, resolved)

oow2 variant_ids (`EMS_XAU_OOW_*`) do not string-match the honest sweep's
(`HON-S*-*`), and honest rows carry no `params.variant` label — so twins are
matched by **full engine-param signature + tf + W2 window**. Two subtleties
that would otherwise mis-link:

- The s6 sweep adds a `trail_atr_floor_k` lever absent from oow2. Including it
  in the signature keeps `k1p5/k2p0/k3p0` variants from collapsing onto the
  floor-0 config. The correct v15 twins are the `trail_atr_floor_k`-absent
  `HON-S1/S2-V15-*` rows.
- Only rows with `live_fill_mode=True` qualify as honest twins; classic
  screening rows on W2 are ignored.

All matched twin groups carry **identical nets** across ties, so the linked
$ figure is unambiguous (ties broken deterministically by lowest run_id).

---

## Per-cell result table (dry-run against `data/research.db`, read-only)

| run_id | tf | classic net | honest net | src | causal | verdict |
|---|---|---:|---:|---|---|---|
| oow2-ctrl-m15 | M15 | 83,581.5 | **+5,111.1** | LINK | clean | **PASS** |
| oow2-ctrl-m2 | M2 | 111,130.5 | −29,030.7 | FRESH | clean | FAIL |
| oow2-ctrl-m5 | M5 | 116,139.6 | −5,724.3 | LINK | clean | FAIL |
| oow2-ss-m15 | M15 | 92,148.6 | **+6,945.3** | LINK | clean | **PASS** |
| oow2-ss-m2 | M2 | 145,926.6 | −33,920.1 | LINK | clean | FAIL |
| oow2-ss-m5 | M5 | 122,599.5 | −5,589.9 | LINK | clean | FAIL |
| oow2-v06b-m15 | M15 | 89,583.0 | **+7,744.5** | LINK | clean | **PASS** |
| oow2-v06c-m15 | M15 | 89,826.0 | **+7,747.2** | LINK | clean | **PASS** |
| oow2-v06c-m5 | M5 | 125,933.1 | −6,038.7 | LINK | clean | FAIL |
| oow2-v06d-m15 | M15 | 89,971.8 | **+7,747.2** | LINK | clean | **PASS** |
| oow2-v06d-m5 | M5 | 126,467.7 | −6,033.0 | LINK | clean | FAIL |
| oow2-v10-m15 | M15 | 44,803.2 | **+6,092.7** | FRESH | clean | **PASS** |
| oow2-v10-m5 | M5 | 68,310.6 | −2,109.0 | FRESH | clean | FAIL |
| oow2-v13-m15 | M15 | 91,709.4 | **+6,961.2** | LINK | clean | **PASS** |
| oow2-v13-m5 | M5 | 129,489.0 | −4,602.6 | LINK | clean | FAIL |
| oow2-v15-m15 | M15 | 72,803.1 | **+3,879.6** | LINK | clean | **PASS** |
| oow2-v15-m2 | M2 | 120,754.8 | −27,635.4 | LINK | clean | FAIL |

**TOTAL: 17 cells — 8 PASS / 9 FAIL. 14 LINKed, 3 FRESH-simulated.**

### LINK vs FRESH ledger

- **FRESH (re-simulated, no honest twin):** `ctrl-m2`, `v10-m15`, `v10-m5`.
  The v10 cells store `direction_mask` as the descriptor string
  `supertrend_m15_atr14_mult3.0_prev_closed_bar`; the fresh sim rebuilds the
  per-bar mask array from the same `compute_direction_mask` helper the
  original run used.
- **LINK (existing honest twin):** the other 14 cells, each to its
  `honest-hon-*-w2` (or D90 live-fill) row of identical signature.

---

## Which $ survives which fidelity level

For every cell the money moves classic → honest-fill+friction in one step
(the honest twins already bundle live-fill semantics + 0.5 spread):

- **M15 family (all 8 PASS):** classic $44.8–92.1k → honest **+$3.9k to
  +$7.7k**. A small but *real, positive* edge survives honest fills on W2.
- **M5 family (all FAIL):** classic $116–129k → honest **−$4.6k to −$6.0k**.
  The entire six-figure on-paper net is a fill artifact; the honest edge is
  negative.
- **M2 family (all FAIL):** classic $111–146k → honest **−$27.6k to −$33.9k**.
  The most inflated cells in the registry; honest re-pricing turns them into
  the largest *losses*.

All 17 cells are **causal-clean** (mean signed entry improvement 0.0, same-bar
exit fraction 0.0): these configs enter exactly at bar close. The inflation is
**not** in entry timing — it is entirely in the classic engine's same-bar
trailing-SL raise (the D90 look-ahead the honest live-fill mode neutralizes).

---

## Family-level verdict: the W2-M15 ≈ +$9.3–9.6k, PF 1.24–1.26 region

**It holds under the full protocol — at a *deflated* magnitude.** Every M15
cell survives as genuinely profitable, but the honest W2-M15 nets land at
**+$3.9k–$7.7k**, not the +$9.3–9.6k on-paper-lite figure quoted for the
region. The +$9k headline is itself modestly optimistic; the honest, causal,
friction-included W2-M15 edge is real but sits nearer **+$6–8k** for the
strongest configs (`v06c/v06d/v13-m15` at +$7.7k/+$7.0k; `ss-m15` +$6.9k).
The M2/M5 side of the family is dead on honest fills.

**Bottom line:** 8 of 17 W2/OOW2 cells carry a real (if small) positive edge —
all on M15. The other 9 (every M2 and M5 cell) are look-ahead artifacts and
are killed with `W2_AUDIT_FAIL`. Of the ~$68–146k on-paper money in this
family, roughly **$0 of the M2/M5 block survives**; only the M15 block's
low-single-digit-thousands is real.

---

## Write pass / concurrency

- Reads open in `mode=ro` with `timeout=60`; the heavy read+re-sim work runs
  on the read-only connection so it never holds a write lock against the
  concurrent honest sweep.
- The validity upgrades + audit rows are written in **one short transaction at
  the end** (busy_timeout 60 s). A crash at any point rolls back the whole
  batch (no marked-but-unaudited row can exist). If the DB stays locked beyond
  60 s the CLI prints and exits nonzero rather than hang.
- **ADDITIVE-ONLY / idempotent:** the sole `UPDATE` touches `validity` and
  only while it is still `REGIME_UNAUDITED`; a second run marks nothing new
  and writes no duplicate audit rows.
- **ENV-ERROR guard (B4 review):** environment failures are never persisted as
  forensic verdicts. A cell whose honest re-pricing crashed (FRESH sim raised)
  or whose causal entry-bar join could not be verified (bars load raised, or
  `n_matched==0` on a run that has trades) resolves to `ENV-ERROR` with a null
  label; an UNVERIFIED causal status blocks a PASS. If ANY cell is `ENV-ERROR`,
  the apply pass raises `AuditEnvError` and aborts **before the first write**
  (zero rows written), naming the cell. `n_matched` (trades joined to entry
  bars) is printed per cell so a silent zero-join can never masquerade as
  "clean". All 17 cells currently join fully (`n_matched` = each run's trade
  count) — 0 ENV-ERROR.

> **Orchestrator note:** the real write pass is deferred to the orchestrator
> (run *after* the honest mega-sweep finishes) so LINK matching sees tonight's
> fresh honest cells. This document records the `--dry-run` verdicts; the
> applied run will reproduce them (LINK targets may shift to newer twins of
> identical signature/net without changing any verdict).

---

## APPLIED — 2026-07-20 (write pass executed)

The write pass ran against `data/research.db` after the mega-sweep finished and
**reproduced the dry-run verdicts byte-for-byte** (17 cells: 8 PASS / 9 FAIL,
all causal-clean, every cell fully joined — 0 ENV-ERROR). Registry state after:

- `run.validity`: **8 `W2_AUDIT_PASS`**, **9 `W2_AUDIT_FAIL(<reason>)`**,
  **0 `REGIME_UNAUDITED`** remaining (all 17 oow2 cells upgraded).
- `audit_log` (actor `honest-program`, action `validity-mark`): 60 → **77 rows**
  (+17, one per upgraded cell).
- **Idempotency confirmed:** a second apply marked nothing new (audit_log stayed
  at 77, verdict table unchanged).
- Gate green: `pytest tests/golden/test_parity.py tests/strategies tests/scripts
  tests/live` → **294 passed**.
