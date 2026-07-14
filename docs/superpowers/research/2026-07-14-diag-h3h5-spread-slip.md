# Diagnostic H3 + H5 — Effective spread by hour & full-night entry slip

**Date:** 2026-07-14 (analysis run ~13:20 UTC)
**Session under study:** 2026-07-14 01:06:02 → 07:57:05 (deal-epoch scale), XAUUSD, magics 720011..720203.
**Scope:** facts and numbers only.

## Data sources & reconciliation

- Deals: `mt5.history_deals_get` on DEMO login **2883015767** (verified via `account_info` before every MT5 read; read-only calls only). Raw dump kept in scratchpad `mt5_deals_full.json`.
- `data/research.db` table `deals_raw` contains only **330 rows**, max `time` = 1783991162..1783997658 (01:06:02 → **02:54:18**) — it does NOT cover the full night. Because the parity checker reads deals exclusively from a `deals_raw` table, a **new** sqlite DB (scratchpad `deals_full.db`, identical schema, populated from `history_deals_get`, 2,292 rows for magics 720011..720203, 00:00–09:00) was built and passed via `--db`. No existing file was modified.
- Session-window filter `1783991162 ≤ time ≤ 1784015825` yields exactly **2,022 deals = 1,011 IN + 1,011 OUT = 1,011 positions**, each 0.01 lot (1 oz), all closed in-window, every position exactly one IN + one OUT. Sum of `profit+commission+swap+fee` = **−712,141.89 CLP** (commission/swap/fee all 0). This reconciles exactly with the stated ~1,011 positions / −712,142 CLP.
- Bars: tier parquets `data/lake/XAUUSD/{M1,M2,M5,M15}/2026-07.parquet` covering through 07:53 / 07:52 / 07:50 / 07:45 respectively. Bars are BID-based. 6 deal legs (3 positions) fall in minutes after the last M1 bar (≥07:54) and are excluded where a bar is required (counts stated below).
- Audit log `scripts/live/run_live_20.audit.log`, armed region from line 2921. Log line clock is in the **same scale as deal epochs** (verified: `[SENT OPEN] SS-M2 F1` at log 01:06:01 → IN deal 720011 at 01:06:02).

---

## H3 — Effective spread vs the flat 0.5 USD/oz model

### H3.1 Per-deal signed distance to same-minute M1 close (bid proxy)

Formula: `delta = deal_price − bid_proxy`, where `bid_proxy` = close `c` of the M1 tier bar whose open-minute = `floor(deal_time/60)*60`. Units USD/oz, signed. Position side = side of the IN deal (BUY=long). 6 of 2,022 deal legs had no same-minute M1 bar (excluded). Hours are UTC hours of the deal time (deal-epoch scale).

**long-IN (BUY entries, fill at ask):**

| hour | count | median | p75 | p90 |
|---|---|---|---|---|
| all | 549 | +0.320 | +1.280 | +2.644 |
| 01 | 72 | +1.155 | +2.540 | +2.930 |
| 02 | 24 | +1.040 | +1.423 | +1.460 |
| 03 | 96 | +0.325 | +0.473 | +1.660 |
| 04 | 24 | +0.100 | +0.180 | +0.489 |
| 05 | 75 | +0.080 | +0.410 | +2.250 |
| 06 | 111 | −0.030 | +0.190 | +1.260 |
| 07 | 147 | +0.990 | +2.660 | +2.878 |

**short-IN (SELL entries, fill at bid):**

| hour | count | median | p75 | p90 |
|---|---|---|---|---|
| all | 459 | +0.120 | +0.560 | +1.160 |
| 01 | 18 | +0.525 | +0.580 | +0.813 |
| 02 | 63 | +0.130 | +0.885 | +1.110 |
| 03 | 57 | +0.440 | +0.760 | +0.924 |
| 04 | 153 | −0.010 | +0.310 | +0.810 |
| 05 | 90 | +0.110 | +1.820 | +1.911 |
| 06 | 42 | −0.060 | +0.482 | +0.540 |
| 07 | 36 | −0.565 | +0.385 | +2.190 |

**long-OUT (SELL exits, fill at bid):**

| hour | count | median | p75 | p90 |
|---|---|---|---|---|
| all | 549 | +0.190 | +0.640 | +1.120 |
| 01 | 72 | +0.410 | +0.857 | +1.213 |
| 02 | 24 | +0.650 | +0.780 | +0.924 |
| 03 | 96 | +0.190 | +0.390 | +0.550 |
| 04 | 24 | −0.240 | −0.028 | +0.690 |
| 05 | 75 | −0.080 | +0.495 | +0.670 |
| 06 | 96 | +0.345 | +0.460 | +1.030 |
| 07 | 162 | +0.170 | +1.118 | +1.325 |

**short-OUT (BUY exits, fill at ask):**

| hour | count | median | p75 | p90 |
|---|---|---|---|---|
| all | 459 | +0.710 | +1.075 | +1.834 |
| 01 | 18 | +0.325 | +0.830 | +0.830 |
| 02 | 60 | +1.400 | +1.692 | +1.741 |
| 03 | 60 | +0.920 | +1.318 | +1.902 |
| 04 | 153 | +0.980 | +1.580 | +2.100 |
| 05 | 90 | +0.545 | +0.880 | +0.982 |
| 06 | 42 | +0.695 | +0.830 | +1.240 |
| 07 | 36 | −0.330 | +0.602 | +0.980 |

(Hour bucket counts differ slightly between IN and OUT of the same side because a position's IN and OUT can fall in different hours.)

### H3.2 Per-position round-trip spread/cost estimate

Formula per position (proxy = same-minute M1 close for the respective deal minute):

- long: `est = (in_price − proxy_in) + (proxy_out − out_price)`
- short: `est = (proxy_in − in_price) + (out_price − proxy_out)`
- USD contribution = `est × volume × 100` = `est × 1 oz` (all positions 0.01 lot).

1,008 of 1,011 positions used; 3 skipped (a deal minute past the last M1 bar 07:53). Hour = UTC hour of the IN deal.

| hour of IN | count | median (USD/oz) | p90 (USD/oz) | total (USD) |
|---|---|---|---|---|
| 01 | 90 | +0.320 | +2.017 | +65.61 |
| 02 | 87 | +0.660 | +2.056 | +66.55 |
| 03 | 153 | −0.030 | +1.608 | +48.38 |
| 04 | 177 | +0.570 | +2.526 | +120.54 |
| 05 | 165 | +0.390 | +2.266 | +46.53 |
| 06 | 153 | +0.080 | +1.470 | +5.98 |
| 07 | 183 | +1.330 | +2.850 | +155.44 |
| **all** | **1,008** | **+0.495** | **+2.330** | **+509.03** |

### H3.3 Measured vs flat-model totals

| quantity | USD |
|---|---|
| Measured round-trip cost vs M1-close bid proxy (1,008 positions) | **509.03** |
| Flat model at 1.0 USD/oz round trip × 1,011 positions × 1 oz (0.5 charged per side) | **1,011.00** |
| Flat model at 0.5 USD/oz charged once per round trip × 1,011 positions × 1 oz | **505.50** |

### H3.4 Spread snapshot NOW (not the night)

Taken 2026-07-14T13:20:42 UTC on DEMO 2883015767: `symbol_info("XAUUSD").spread` = **60 points** × point 0.01 = **0.60 USD/oz**; `symbol_info_tick`: bid 4075.51 / ask 4076.11 → ask−bid = **0.60**; `spread_float` = False; `trade_contract_size` = 100.

---

## H5 — Entry slip, full night

### H5.5 Parity checker (full-night run)

Command: `python -m scripts.live.check_live_sim_parity --config all --start 2026-07-14T01:06:00 --end 2026-07-14T07:57:00 --db <scratchpad deals_full.db> --json scripts/report/diag_h5_parity_full.json` (spread model default 0.5). Result: 20 configs, 2 MATCH / 18 DIVERGENCE, 136 hard divergences. Costs are in the checker's price units (USD/oz per pair, summed).

| config | verdict | sim_entries | live_entries | matches | ENTRY_NEXT_BAR | entry_slip_cost | SAME_BAR_OPTIMISM | same_bar_cost |
|---|---|---|---|---|---|---|---|---|
| SS-M2 | DIVERGENCE | 33 | 31 | 28 | 27 | 12.71 | 60 | 78.85 |
| V06D-M2 | DIVERGENCE | 39 | 34 | 26 | 24 | 10.35 | 63 | 72.02 |
| V15-M2 | DIVERGENCE | 30 | 28 | 26 | 24 | 11.52 | 51 | 66.34 |
| SS-M5 | DIVERGENCE | 19 | 14 | 12 | 10 | 3.69 | 26 | 47.97 |
| V06D-M5 | DIVERGENCE | 21 | 17 | 15 | 13 | 5.25 | 39 | 83.88 |
| V13-M5 | DIVERGENCE | 22 | 18 | 15 | 13 | 5.55 | 36 | 82.24 |
| SS-M15 | DIVERGENCE | 7 | 4 | 3 | 2 | 0.53 | 9 | 39.62 |
| V13-M15 | DIVERGENCE | 7 | 4 | 3 | 2 | 0.42 | 9 | 38.56 |
| V06D-M15 | DIVERGENCE | 6 | 5 | 4 | 4 | 3.10 | 15 | 49.01 |
| V06C-M5 | DIVERGENCE | 21 | 17 | 15 | 13 | 5.59 | 36 | 85.89 |
| V06C-M15 | DIVERGENCE | 6 | 5 | 4 | 4 | 3.52 | 15 | 47.69 |
| V06B-M15 | DIVERGENCE | 6 | 5 | 4 | 4 | 3.27 | 15 | 47.13 |
| V15-M15 | MATCH | 3 | 3 | 3 | 3 | 2.91 | 9 | 19.78 |
| V10-M5 | DIVERGENCE | 13 | 9 | 8 | 6 | 2.37 | 21 | 49.39 |
| V10-M15 | MATCH | 3 | 3 | 3 | 3 | 2.73 | 9 | 19.93 |
| V13-M2 | DIVERGENCE | 39 | 34 | 26 | 24 | 10.31 | 57 | 65.39 |
| V09-CTRL-M5 | DIVERGENCE | 21 | 17 | 15 | 13 | 5.17 | 36 | 86.61 |
| V09-CTRL-M15 | DIVERGENCE | 6 | 5 | 4 | 4 | 2.73 | 15 | 43.30 |
| SS-M1 | DIVERGENCE | 61 | 56 | 50 | 46 | 23.12 | 60 | 72.68 |
| V11-M2 | DIVERGENCE | 30 | 27 | 20 | 20 | 9.17 | 50 | 51.00 |
| **TOTAL** | | **393** | **336** | **284** | **259** | **124.01** | **631** | **1,147.28** |

(Checker counts are per sim entry-group, not per ficha/deal, hence 336 live entry groups vs 1,011 fichas ≈ 3 fichas/group.)

### H5.6 Independent entry-slip cross-check (audit log × MT5 deals × tier bars)

Method: parsed armed region (line ≥ 2921) of `scripts/live/run_live_20.audit.log`. Each `[SENT OPEN] <cfg> <ficha> magic=… -> retcode=…` was tagged with the most recent `[<cfg>] bar=<iso>` cycle line for that config. Filter to session window and `retcode=10009`. Each SENT OPEN matched to an IN deal by magic + minimal `|deal_time − log_time|` ≤ 120 s, each deal used at most once. `signal_bar_close` = close of the config's TF tier parquet bar with open-time = cycle bar time. Slip sign: **negative = worse for the position side** — long: `close − in_price`; short: `in_price − close`. Per-position USD = slip × 1 oz.

**Match rates:** SENT OPEN lines in armed region at parse time: 1,218 (log still growing; executor remains armed past the session). In session window: 1,023 (retcode 10009: **1,011**, retcode 10016: 12, which produced no deals). Matched to IN deals: **1,011 / 1,011 (100%)**, i.e. every filled order and every IN deal paired 1:1. With a resolvable signal bar: **1,008 / 1,011** (3 excluded: cycle bar time beyond the tier parquet's last bar).

**Per config:**

| config | n | mean | median | p10 (worst tail) | p90 | total USD |
|---|---|---|---|---|---|---|
| SS-M2 | 93 | −0.295 | −0.190 | −0.900 | +0.480 | −27.45 |
| V06D-M2 | 102 | −0.281 | −0.150 | −0.740 | +0.389 | −28.67 |
| V15-M2 | 84 | −0.271 | −0.170 | −0.910 | +0.599 | −22.77 |
| SS-M5 | 42 | −0.141 | 0.000 | −0.865 | +0.279 | −5.93 |
| V06D-M5 | 51 | −0.091 | +0.020 | −0.680 | +0.550 | −4.66 |
| V13-M5 | 54 | −0.082 | −0.030 | −0.899 | +0.610 | −4.42 |
| SS-M15 | 12 | −0.227 | −0.150 | −1.172 | +0.559 | −2.72 |
| V13-M15 | 12 | −0.261 | −0.210 | −1.098 | +0.349 | −3.13 |
| V06D-M15 | 15 | −0.504 | −0.470 | −1.136 | +0.090 | −7.56 |
| V06C-M5 | 51 | −0.086 | −0.020 | −0.680 | +0.610 | −4.38 |
| V06C-M15 | 15 | −0.619 | −0.620 | −1.370 | +0.070 | −9.29 |
| V06B-M15 | 15 | −0.608 | −0.320 | −1.436 | +0.056 | −9.12 |
| V15-M15 | 9 | −0.921 | −1.130 | −1.372 | −0.238 | −8.29 |
| V10-M5 | 27 | −0.239 | −0.230 | −0.808 | +0.206 | −6.46 |
| V10-M15 | 9 | −0.730 | −1.040 | −1.330 | +0.198 | −6.57 |
| V13-M2 | 102 | −0.294 | −0.165 | −0.936 | +0.410 | −29.98 |
| V09-CTRL-M5 | 51 | +0.013 | +0.010 | −0.700 | +0.750 | +0.64 |
| V09-CTRL-M15 | 15 | −0.495 | −0.020 | −1.348 | +0.050 | −7.42 |
| SS-M1 | 168 | −0.268 | −0.310 | −0.926 | +0.430 | −45.09 |
| V11-M2 | 81 | −0.277 | −0.070 | −0.910 | +0.480 | −22.47 |
| **all** | **1,008** | **−0.254** | **−0.160** | **−0.963** | **+0.480** | **−255.74** |

**Per UTC hour (of deal time):**

| hour | n | mean | median | p10 (worst tail) | total USD |
|---|---|---|---|---|---|
| 01 | 90 | −0.849 | −0.185 | −4.436 | −76.39 |
| 02 | 87 | +0.080 | +0.140 | −0.652 | +6.98 |
| 03 | 153 | −0.269 | −0.380 | −0.610 | −41.17 |
| 04 | 177 | +0.033 | +0.080 | −1.074 | +5.89 |
| 05 | 165 | −0.106 | −0.020 | −0.910 | −17.55 |
| 06 | 153 | −0.342 | −0.320 | −0.680 | −52.30 |
| 07 | 183 | −0.444 | −0.560 | −1.308 | −81.20 |

Raw diff without sign convention: `in_price − signal_bar_close` per fill is stored in the JSON per-row source (scratchpad `h5_rows.json`); the sign-normalized totals above use the convention stated.

---

## Artifacts

- `scripts/report/diag_h5_parity_full.json` — checker output, full night, 20 configs.
- `scripts/report/diag_h3h5_spread.json` — H3 tables + formulas + spread snapshot.
- `scripts/report/diag_h3h5_entry_slip.json` — parity aggregation + independent slip tables + match rates.
- Scratchpad (session temp): `diag_h3h5.py` (analysis script), `mt5_deals_full.json` (raw deal dump), `deals_full.db` (deals_raw rebuild for the checker), `h5_rows.json` (per-fill slip rows), `parity_full.log`.
