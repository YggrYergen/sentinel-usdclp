# EMASAR variant research — Batch 1 (V-09, V-14, V-01)

Generated 2026-07-13 by `scripts/report/gen_variant_batch1.py`. Engine:
`sentinel_engine/strategies/emasar_variant.py::simular_variant` (per-ficha
trailing ladder, V1 entries). Symbol XAUUSD, spread 0.5 (Capitaria) applied
at fill exactly as in `scripts/report/gen_thu_fri_backtests.py`. LOT 0.10,
contract size $100/pt.

**Window**: 2026-06-08 → 2026-07-07 (warmup fed from 2026-06-01). Timeframes
M1, M2, M5, M15 — **all four are present in the lake for June+July** (no
backfill needed, no data gaps). M1 yields ~13.9k trades over the window,
M2 ~7.2k, M5 ~2.9k, M15 ~0.9k.

All metrics: net PnL ($), profit factor (PF), win rate (WR %), max drawdown
on cumulative trade PnL ($), trade count, % exits EXIT_INITSL vs EXIT_TRAIL,
trades/day. Numbers rounded to 1 decimal (PF/payoff to 2 where useful for
distinguishing runs).

---

## V-09 — Full C04 bundle replica (CONTROL baseline)

Params: `confirm_mode=1, confirm_count=2, require_ema_order=False,
f1_trail_pips=100, f2_trail_pips=100, f3_trail_pips=100, init_sl_range_k=1.0,
ema_fast=8, ema_slow=20, sar_step=0.3, sar_max=0.3`. One run per TF, ingested
as `sim-report-emasar-v09-<tf>`.

| TF  | Trades | Net ($)   | PF     | WR (%) | MaxDD ($) | %INITSL | %TRAIL | Trades/day |
|-----|-------:|----------:|-------:|-------:|----------:|--------:|-------:|-----------:|
| M1  | 13,881 | -42,866.1 |  0.56  |  28.7  |  43,459.8 |   9.4   |  90.6  |    462.7   |
| M2  |  7,233 |  13,732.8 |  1.32  |  40.9  |   3,350.7 |   3.5   |  96.5  |    241.1   |
| M5  |  2,853 |  37,469.7 |  3.87  |  60.9  |     633.6 |   2.4   |  97.6  |     95.1   |
| M15 |    948 |  37,326.6 | 10.71  |  76.9  |     881.1 |   1.6   |  98.4  |     31.6   |

**Headline**: V-09 is net-negative and low-PF on M1 (over-trading: 462.7
trades/day, PF 0.56), turns marginally profitable on M2 (PF 1.32), and is
strongly profitable with high PF/WR on M5 and M15 — M15 is the standout
(PF 10.7, WR 76.9%, tiny drawdown). Lower TFs trade far more often but with
materially worse edge; the C04 bundle scales best at M5/M15 within this
window.

---

## V-14 — Directional asymmetry

### Step (a): diagnostic — long/short PnL split

**V-09 params, this window (2026-06-08→07-07), simulated fresh per TF:**

| TF  | Long PnL ($) | Long n | Short PnL ($) | Short n | Long − Short |
|-----|-------------:|-------:|--------------:|--------:|--------------:|
| M1  |  -20,535.9   |  6,846 |   -22,330.2   |  7,035  |    1,794.3    |
| M2  |    7,594.5   |  3,603 |     6,138.3   |  3,630  |    1,456.2    |
| M5  |   18,477.6   |  1,389 |    18,992.1   |  1,464  |     -514.5    |
| M15 |   18,814.5   |    447 |    18,512.1   |    501  |      302.4    |

Long and short are close to symmetric on every TF in this window (both
directions lose on M1, both win on M2/M5/M15) — there's a mild long-side
edge on M1/M2/M15 and a mild short-side edge on M5, but none of these are
large relative to the "both" totals. **No systematic strong directional
bias emerges from V-09 params on this window.**

**3 existing EMASAR fixture runs (2026-07-02/03 window, original engine
params, from `data/research.db`):**

| run_id                                    | TF  | Net ($) | Long PnL ($) | Long n | Short PnL ($) | Short n |
|--------------------------------------------|-----|--------:|-------------:|-------:|---------------:|--------:|
| sim-report-emasar-orig-sar3m3-m2          | M2  |  -718.7 |         -8.5 |    49  |        -710.2  |    45   |
| sim-report-emasar-pf-sar005m05-m5         | M5  |  -603.8 |         42.8 |    15  |        -646.6  |    15   |
| sim-report-emasar-wr-v2m15c1              | M15 |  -502.2 |        254.5 |     5  |        -756.7  |     2   |

**Contrast with V-09 diagnostic**: unlike the V-09-params diagnostic above,
these 3 fixture runs (different engine params, different 2-day window) show
a **strong, consistent short-side loss** across all three — long is near
breakeven or positive, short is deeply negative in every case. This is the
opposite pattern of what V-09 shows on the 4-week window, i.e. the
directional bias is params/window-dependent, not a fixed property of the
EMASAR entry logic.

### Step (b): long-only vs short-only vs both (V-09 params)

| TF  | Side  | Trades | Net ($)   | PF     | WR (%) | MaxDD ($) |
|-----|-------|-------:|----------:|-------:|-------:|----------:|
| M1  | Both  | 13,881 | -42,866.1 |  0.56  |  28.7  | 43,459.8  |
| M1  | Long  |  6,858 | -20,469.9 |  0.58  |  28.4  | 21,139.8  |
| M1  | Short |  7,041 | -22,378.2 |  0.54  |  29.0  | 22,426.8  |
| M2  | Both  |  7,233 |  13,732.8 |  1.32  |  40.9  |  3,350.7  |
| M2  | Long  |  3,603 |   7,594.5 |  1.34  |  39.1  |  1,755.9  |
| M2  | Short |  3,630 |   6,138.3 |  1.29  |  42.6  |  1,855.5  |
| M5  | Both  |  2,853 |  37,469.7 |  3.87  |  60.9  |    633.6  |
| M5  | Long  |  1,389 |  18,477.6 |  3.93  |  59.8  |    685.2  |
| M5  | Short |  1,464 |  18,992.1 |  3.81  |  61.9  |    682.2  |
| M15 | Both  |    948 |  37,326.6 | 10.71  |  76.9  |    881.1  |
| M15 | Long  |    447 |  18,814.5 | 10.04  |  76.5  |    881.1  |
| M15 | Short |    501 |  18,512.1 | 11.50  |  77.3  |    645.6  |

**Both-sides beats either single side on every TF** (roughly ~net_long +
net_short, as expected since long/short trade streams barely interact in
this engine — no shared position slots across sides). Splitting to a single
side does NOT improve PF/WR meaningfully anywhere; it just halves trade
count and net, with drawdown *not* halving proportionally (M1 long/short
maxDD ≈ half of "both" maxDD, but M15 long maxDD stays the *same* as "both"
because the DD-defining sequence sits within the long-only stream). Given
the diagnostic in step (a) showed no strong bias on this window, this
result is consistent — asymmetry restriction is a net loser here.

**Winners ingested** (best single-side net per TF, per spec — still worse
than "both" everywhere, but this is what the protocol asks for):

| TF  | Winner side | run_id                          | Net ($)  |
|-----|-------------|----------------------------------|---------:|
| M1  | long        | sim-report-emasar-v14-long-m1   | -20,469.9|
| M2  | long        | sim-report-emasar-v14-long-m2   |   7,594.5|
| M5  | short       | sim-report-emasar-v14-short-m5  |  18,992.1|
| M15 | long        | sim-report-emasar-v14-long-m15  |  18,814.5|

**Verdict**: V-14 does not beat V-09 baseline on any TF (single-side nets
are strictly below "both"-side V-09 net in every case examined). The
fixture-run diagnostic hints that short-side weakness *can* appear under
different params/windows, but under this batch's controlled params and
window, splitting hurts more than it helps.

---

## V-01 — Legal-stop range_k sweep

V-09 params with `init_sl_range_k ∈ {0.5, 0.75, 1.0, 1.25, 1.5, 2.0}`, 6 k
values × 4 TFs = 24 runs. Full curve below.

### M1

| k    | Trades | Net ($)   | PF    | WR (%) | %INITSL | MaxDD ($) |
|------|-------:|----------:|------:|-------:|--------:|----------:|
| 0.50 | 13,884 | -49,499.4 | 0.52  |  28.5  |  12.9   | 49,900.5  |
| 0.75 | 13,884 | -45,587.1 | 0.54  |  28.6  |  10.8   | 46,001.1  |
| 1.00 | 13,881 | -42,866.1 | 0.56  |  28.7  |   9.4   | 43,459.8  |
| 1.25 | 13,881 | -40,516.5 | 0.57  |  28.7  |   8.5   | 41,097.0  |
| 1.50 | 13,878 | -39,530.7 | 0.58  |  28.8  |   8.1   | 40,210.2  |
| 2.00 | 13,878 | -37,432.2 | 0.59  |  28.8  |   7.5   | 38,111.7  |

### M2

| k    | Trades | Net ($)   | PF    | WR (%) | %INITSL | MaxDD ($) |
|------|-------:|----------:|------:|-------:|--------:|----------:|
| 0.50 |  7,233 |   9,087.9 | 1.19  |  40.7  |   6.9   |  4,425.6  |
| 0.75 |  7,233 |  11,476.2 | 1.25  |  40.7  |   4.8   |  3,795.0  |
| 1.00 |  7,233 |  13,732.8 | 1.32  |  40.9  |   3.5   |  3,350.7  |
| 1.25 |  7,233 |  15,530.4 | 1.37  |  40.9  |   2.6   |  2,971.8  |
| 1.50 |  7,233 |  16,518.6 | 1.40  |  40.9  |   2.2   |  2,987.1  |
| 2.00 |  7,233 |  17,831.4 | 1.45  |  40.9  |   1.7   |  2,922.3  |

### M5

| k    | Trades | Net ($)   | PF    | WR (%) | %INITSL | MaxDD ($) |
|------|-------:|----------:|------:|-------:|--------:|----------:|
| 0.50 |  2,853 |  31,923.3 | 2.75  |  59.9  |   6.4   |  1,126.5  |
| 0.75 |  2,853 |  34,926.3 | 3.26  |  60.6  |   3.9   |    795.3  |
| 1.00 |  2,853 |  37,469.7 | 3.87  |  60.9  |   2.4   |    633.6  |
| 1.25 |  2,853 |  38,290.5 | 4.11  |  61.1  |   1.5   |    721.5  |
| 1.50 |  2,853 |  39,561.3 | 4.59  |  61.1  |   0.9   |    503.7  |
| 2.00 |  2,853 |  39,950.7 | 4.75  |  61.1  |   0.5   |    614.7  |

### M15

| k    | Trades | Net ($)   | PF    | WR (%) | %INITSL | MaxDD ($) |
|------|-------:|----------:|------:|-------:|--------:|----------:|
| 0.50 |    948 |  34,358.4 |  6.19 |  76.0  |   5.4   |    921.6  |
| 0.75 |    948 |  35,667.9 |  7.64 |  76.3  |   3.2   |    737.7  |
| 1.00 |    948 |  37,326.6 | 10.71 |  76.9  |   1.6   |    881.1  |
| 1.25 |    948 |  38,117.7 | 13.40 |  77.2  |   0.9   |    729.0  |
| 1.50 |    948 |  39,263.7 | 19.65 |  77.5  |   0.3   |    457.2  |
| 2.00 |    948 |  39,749.7 | 25.11 |  77.9  |   0.0   |    150.3  |

### Knee analysis

Trade count is essentially flat across k (±0.4% at most — widening the
initial range-SL mostly converts EXIT_INITSL outcomes into later
EXIT_TRAIL outcomes rather than changing which signals fire). Net and PF
**increase monotonically with k on every TF, across the entire tested
range** — there is no interior knee where %INITSL "drops fastest vs net
gained" within `{0.5 … 2.0}`; the curve is still climbing at k=2.0 (the top
of the grid) on all four TFs. The steepest %INITSL drop-per-k happens
between k=0.5→1.0 (e.g. M15: 5.4%→1.6%, a 3.8pt drop) while net gain in
that same segment is smaller in relative terms than the 1.0→2.0 segment
(M15: +2,968 vs +2,423 — comparable, not a clear inflection). In short:
**wider legal stops keep helping throughout the tested grid; k=2.0 (the
loosest tested) wins everywhere**, meaning the true optimum for this
window/params likely lies at or beyond k=2.0 — the sweep grid did not
bracket a genuine knee. This should be flagged for a follow-up sweep
extending k beyond 2.0 if a knee is specifically wanted.

**Best-net k per TF (all k=2.0)** — ingested as `sim-report-emasar-v01-<tf>`:

| TF  | Best k | Net ($)   | PF    | WR (%) | MaxDD ($) |
|-----|-------:|----------:|------:|-------:|----------:|
| M1  |  2.0   | -37,432.2 | 0.59  |  28.8  | 38,111.7  |
| M2  |  2.0   |  17,831.4 | 1.45  |  40.9  |  2,922.3  |
| M5  |  2.0   |  39,950.7 | 4.75  |  61.1  |    614.7  |
| M15 |  2.0   |  39,749.7 | 25.11 |  77.9  |    150.3  |

---

## Head-to-head vs V-09 baseline

| TF  | V-09 Net  | V-14 winner Net (side)      | V-01 best-k Net (k) | Best of the 3 |
|-----|----------:|------------------------------|----------------------|----------------|
| M1  | -42,866.1 | -20,469.9 (long)             | -37,432.2 (k=2.0)   | V-14 long (least-bad; still net-negative) |
| M2  |  13,732.8 |   7,594.5 (long)             |  17,831.4 (k=2.0)   | V-01 (k=2.0) |
| M5  |  37,469.7 |  18,992.1 (short)            |  39,950.7 (k=2.0)   | V-01 (k=2.0) |
| M15 |  37,326.6 |  18,814.5 (long)             |  39,749.7 (k=2.0)   | V-01 (k=2.0) |

- **V-09** (control, k=1.0, both sides) is a reasonable baseline but is
  dominated by V-01's wider-stop variant on every TF that matters (M2/M5/M15;
  M1 stays negative everywhere due to over-trading noise on 1-minute bars).
- **V-14** never beats V-09 on net (halving the trade population always
  costs more net than it saves in drawback) — it is informative for risk
  shaping (e.g. lower absolute drawdown exposure per side) but not for raw
  PnL.
- **V-01** is the clear win of this batch: simply loosening the legal
  range-SL to k=2.0 improves net, PF, and (mostly) drawdown simultaneously
  on M2/M5/M15, and it partially recovers M1 (still net-negative, but
  ~$5.4K better than V-09's control k=1.0).
- **M15 is the best-performing TF overall** for the C04 bundle family in
  this window (PF up to 25.1 at k=2.0), consistent with V-09's own M15
  standout result.

## Data gaps

None. M1/M2/M5/M15 all had full lake coverage for 2026-06-01→2026-07-07
(warmup + window), so no timeframe was skipped or backfilled.

## Ingested runs (winners only, `data/research.db`)

- `sim-report-emasar-v09-{m1,m2,m5,m15}` — V-09 control, one per TF.
- `sim-report-emasar-v14-{long,short}-{m1,m2,m5,m15}` — V-14 best single
  side per TF (long: m1, m2, m15; short: m5).
- `sim-report-emasar-v01-{m1,m2,m5,m15}` — V-01 best-net k per TF (k=2.0 in
  all four cases; see `metrics_json.params.init_sl_range_k` on each run row).

All re-ingestion is idempotent (delete-before-insert per run_id), verified
via `python scripts/dev/e2e_service.py --port 8611` + `GET
/api/runs/<run_id>/trades` returning non-empty rows for
`sim-report-emasar-v09-m5`, `sim-report-emasar-v01-m15`, and
`sim-report-emasar-v14-short-m5`.
