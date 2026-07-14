# EMASAR variants -- Batch 6 (extension): AC-modulate factor sweep BELOW 0.10 ("V-06d")

Runner: `scripts/report/gen_variant_batch6.py`. Reuses batch1's load/fill/metrics/ingest
machinery (importlib pattern, same as batches 2-5). Zero new engine code -- the
`ac_modulate_factor` parameter already exists in
`sentinel_engine.strategies.emasar_variant.simular_variant`.

## Config (all 20 runs)

Champion stack, fixed:

```
confirm_mode=1, confirm_count=2, require_ema_order=False, ema_fast=8, ema_slow=20,
sar_step=0.3, sar_max=0.3, f1_trail_pips=100, f2_trail_pips=100, f3_trail_pips=100,
ac_modulate=True
```

Per-TF `init_sl_range_k`: M1=6.0, M2=3.0, M5=6.0, M15=2.5.

XAUUSD, window 2026-06-08 -> 2026-07-07 (warmup from 2026-06-01), BID lake bars,
spread 0.5 applied at fill, legal-range stop.

Grid: `ac_modulate_factor` in {0.01, 0.03, 0.05, 0.07, 0.09} x TF in {M1, M2, M5, M15}
= 20 simulations.

## Full results table (factor descending, including the 0.10 reference from batch 5's V-06c)

### M1

| factor | net | PF | WR | maxDD | n trades |
|---|---|---|---|---|---|
| 0.10 (ref) | -14,922.0 | 0.80 | -- | -- | -- |
| 0.09 | -14,662.2 | 0.8017 | 33.96 | 19,589.1 | 13,923 |
| 0.07 | -14,142.6 | 0.8079 | 34.20 | 19,187.1 | 13,923 |
| 0.05 | -13,623.0 | 0.8142 | 34.43 | 18,785.1 | 13,923 |
| 0.03 | -13,103.4 | 0.8206 | 34.63 | 18,383.1 | 13,923 |
| 0.01 | **-12,583.8** | 0.8270 | 34.82 | 17,981.1 | 13,923 |

### M2

| factor | net | PF | WR | maxDD | n trades |
|---|---|---|---|---|---|
| 0.10 (ref) | +30,777.9 | 2.00 | 46.0 | 1,854.9 | -- |
| 0.09 | +30,903.0 | 2.0109 | 46.00 | 1,846.2 | 7,233 |
| 0.07 | +31,153.2 | 2.0232 | 46.25 | 1,828.8 | 7,233 |
| 0.05 | +31,403.4 | 2.0354 | 46.50 | 1,811.4 | 7,233 |
| 0.03 | +31,653.6 | 2.0476 | 46.62 | 1,794.0 | 7,233 |
| 0.01 | **+31,903.8** | 2.0599 | 46.74 | 1,776.6 | 7,233 |

### M5

| factor | net | PF | WR | maxDD | n trades |
|---|---|---|---|---|---|
| 0.10 (ref) | +45,815.7 | 7.34 | 65.8 | 209.7 | -- |
| 0.09 | +45,866.1 | 7.3653 | 66.04 | 209.1 | 2,853 |
| 0.07 | +45,966.9 | 7.4054 | 66.25 | 207.9 | 2,853 |
| 0.05 | +46,067.7 | 7.4458 | 66.25 | 206.7 | 2,853 |
| 0.03 | +46,168.5 | 7.4866 | 66.25 | 205.5 | 2,853 |
| 0.01 | **+46,269.3** | 7.5269 | 66.46 | 204.3 | 2,853 |

### M15

| factor | net | PF | WR | maxDD | n trades |
|---|---|---|---|---|---|
| 0.10 (ref) | +41,126.7 | 31.66 | 79.8 | 150.3 | -- |
| 0.09 | +41,142.0 | 31.7282 | 79.75 | 150.3 | 948 |
| 0.07 | +41,172.6 | 31.8617 | 80.38 | 150.3 | 948 |
| 0.05 | +41,203.2 | 31.9822 | 80.38 | 150.3 | 948 |
| 0.03 | +41,233.8 | 32.1034 | 80.38 | 150.3 | 948 |
| 0.01 | **+41,264.4** | 32.2254 | 80.38 | 150.3 | 948 |

(Trade count, exit-motivo split, and trades/day are identical across the whole
factor sweep per TF -- factor only rescales the AC-modulated portion of the
initial-SL distance, it does not change which bars trigger entries/exits.
Exit-mix: M1 5.6% INITSL / 94.4% TRAIL; M2 1.24% / 98.76%; M5 0.11% / 99.89%;
M15 0.0% / 100.0%. Trades/day: M1 464.1, M2 241.1, M5 95.1, M15 31.6 -- constant
across the sweep.)

## Knee analysis (mechanical rule: first factor, ordered 0.10 -> 0.01 descending,
whose net is LOWER than the previous factor's net)

- **M1**: 0.10 -14,922.0 -> 0.09 -14,662.2 (better) -> 0.07 -14,142.6 (better) ->
  0.05 -13,623.0 (better) -> 0.03 -13,103.4 (better) -> 0.01 -12,583.8 (better).
  Net improves monotonically at every step. **Knee: monotonic to 0.01.** Best
  factor: **0.01** (net -12,583.8, still net-negative).
- **M2**: 0.10 +30,777.9 -> 0.09 +30,903.0 (better) -> 0.07 +31,153.2 (better) ->
  0.05 +31,403.4 (better) -> 0.03 +31,653.6 (better) -> 0.01 +31,903.8 (better).
  **Knee: monotonic to 0.01.** Best factor: **0.01** (net +31,903.8).
- **M5**: 0.10 +45,815.7 -> 0.09 +45,866.1 (better) -> 0.07 +45,966.9 (better) ->
  0.05 +46,067.7 (better) -> 0.03 +46,168.5 (better) -> 0.01 +46,269.3 (better).
  **Knee: monotonic to 0.01.** Best factor: **0.01** (net +46,269.3).
- **M15**: 0.10 +41,126.7 -> 0.09 +41,142.0 (better) -> 0.07 +41,172.6 (better) ->
  0.05 +41,203.2 (better) -> 0.03 +41,233.8 (better) -> 0.01 +41,264.4 (better).
  **Knee: monotonic to 0.01.** Best factor: **0.01** (net +41,264.4).

## Verdict per TF (vs. the 0.10 reference)

| TF | verdict | delta net vs 0.10 |
|---|---|---|
| M1 | IMPROVES (still net-negative) | +2,338.2 |
| M2 | IMPROVES | +1,125.9 |
| M5 | IMPROVES | +453.6 |
| M15 | IMPROVES | +137.7 |

All four TFs improve monotonically as `ac_modulate_factor` decreases from 0.10
down to 0.01, with no knee inside the tested sub-0.10 range. The grid did not
reach the point of diminishing/reversing returns; 0.01 (the smallest value
tested) is the best factor on every TF.

## Shape

`ac_modulate_factor` scales how much the AC (accelerator/oscillator) confirmation
signal widens the initial-SL distance beyond the base `init_sl_range_k` allowance
-- lower factor means less AC-driven widening, i.e. a tighter, more consistent
initial stop that tracks the base range_k more closely. Since exit-motivo mix and
trade count are IDENTICAL across the whole sweep on every TF (same bars trigger
entries/exits regardless of factor), the only thing changing is the SIZE of each
trade's initial-SL leg, and by extension the price distance covered before a
trailing exit locks in -- smaller AC widening tightens that distance uniformly,
which nets out to smaller per-trade losses on the losing tail (M1, still net-
negative but PF creeping toward parity) and larger locked-in gains on the winning
tail (M2/M5/M15, all already strongly profitable). The relationship in this
sub-0.10 band is linear/monotonic and shows no sign of turning over — the true
knee (if any) sits either below 0.01 or the true optimum is factor=0 (AC
modulation fully off), neither of which was tested this batch.

## Ingestion

Only the best-net factor (0.01, every TF) was ingested into `data/research.db`,
idempotent delete-before-insert:

| run_id | variant_id |
|---|---|
| sim-report-emasar-v06d-m1 | EMS_XAU_V06d_M1_c1_f0p01_champion |
| sim-report-emasar-v06d-m2 | EMS_XAU_V06d_M2_c1_f0p01_champion |
| sim-report-emasar-v06d-m5 | EMS_XAU_V06d_M5_c1_f0p01_champion |
| sim-report-emasar-v06d-m15 | EMS_XAU_V06d_M15_c1_f0p01_champion |

Verified via `python scripts/dev/e2e_service.py --port 8622` +
`GET /api/runs/<run_id>/trades` -- trade counts match exactly (M1 13,923;
M2 7,233; M5 2,853; M15 948).
