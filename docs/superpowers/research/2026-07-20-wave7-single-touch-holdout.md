# Wave 7 - Single-touch holdout (decisive OOS gate)

_Generated 2026-07-20T14:43:29Z -- read-only vs data/research.db + lake. Offline; no MT5, no orders._

## Holdout window (disclosure)

**Holdout = `HOLDOUT-2026-01`, 2026-01-05 .. 2026-02-05** (warmup from 2025-12-29), XAUUSD M15 BID lake bars.

This window is a GENUINELY UNTOUCHED slice. The in-sample honest league (`2026-07-20-honest-league-v3`) scored every candidate on the four windows {IW=2026-06-08..07-07, W1=2026-05, W2=2026-03, W3=2025-10} and used those four AS the walk-forward folds feeding `select_winner` (see `gen_honest_sweep._build_league`: each window net -> one `FoldResult.candidate_J`; the median over folds picks the winner). Therefore IW/W1/W2/W3 are ALL in-sample and none is a valid holdout. The Jan-2026 month here was NEVER loaded by any sweep, selection, or refit -- it is the most-recent full month sitting outside the touched cluster. Each finalist is priced EXACTLY ONCE on it below (single touch), win or lose, with no re-selection.

Cost model is identical to the league: `simular_variant(live_fill_mode=True)` for the EMASAR family (via the verbatim `gen_honest_sweep._price_cell`/`._metrics`) and the P34 always-in engine for SuperTrend; flat $0.50/round-trip spread at fill; lot 0.10; XAUUSD contract $100/$1.

## Per-candidate holdout (single-touch) results

| Candidate | Trades | Net (USD) | PF | WR% | Per-trade Sharpe |
|---|---|---|---|---|---|
| HON-W2-S6-K2P0-M15-SAR | 414 | +16457.10 | 1.392 | 37.7 | 0.0969 |
| HON-W2-S7-TPNONE-M15-SAR | 540 | +8935.80 | 1.187 | 36.7 | 0.0485 |
| HON-W2-S6-K1P5-M15-SAR | 540 | +8935.80 | 1.187 | 36.7 | 0.0485 |
| HON-W2-S7-TP1P0-M15-SAR | 540 | +7072.00 | 1.148 | 36.7 | 0.0390 |
| HON-W2-S7-TPNONE-M15-SAR-F2 | 360 | +5957.20 | 1.187 | 36.7 | 0.0484 |
| SuperTrend-p14x3-M15 (always-in) | 55 | +2813.90 | 1.194 | 32.7 | 0.0556 |

_SuperTrend: 76 flips over 2540 bars (warmup incl.); position open at feed-end left open, not a trade -- P34 reference semantics._

## Honest verdict

- The in-sample WINNER, `HON-W2-S6-K2P0-M15-SAR`, posts net **+16457.10 USD** on this untouched holdout (414 trades).

- Of the 5 EMASAR SAR finalists, **5/5** are net-positive on the holdout. SuperTrend-p14x3-M15 is **net-positive** (+2813.90).

- **Luck bar / DSR:** the in-sample league already deflated to **DSR 0.0000 / honest p-value 1.0000** over 225 trials -- i.e. the in-sample edge was statistically indistinguishable from the best of a skill-less search. A single untouched month is a small sample (a handful of trades per candidate), so it CANNOT by itself resurrect significance; it can only CONFIRM or REFUTE the direction. No DSR is computed on the holdout because there is exactly one pre-specified config per family here (nothing to deflate) -- fabricating a trial family to manufacture a holdout p-value would be dishonest. (Note: the SAR family fires often -- ~400-540 per-ficha trade rows in the month -- so per-candidate trade count is NOT the small-sample issue; the small sample is the ONE independent monthly regime tested.)

- **Direction:** the SAR family's sign HOLDS out of sample (winner positive, majority of finalists positive). This is corroborating, NOT decisive: it does not overturn the in-sample DSR verdict (p=1.0). The honest read is 'not falsified on one untouched month', not 'validated edge'.

## Caveats (mandatory)

- Small-sample holdout: exactly ONE independent monthly regime is tested (trade COUNT per candidate is high, but they are highly autocorrelated within one month, not one independent draw). This gate tests DIRECTION/sign persistence, not a powered significance claim.
- Single touch enforced: each candidate priced ONCE here; no lever was refit and no re-selection was done on holdout results.
- The SuperTrend $17.5k legacy headline remains an unverified legacy TOKATA-ledger artifact (see P34), NOT reproduced here.
- Window choice was fixed BEFORE seeing results (most-recent untouched full month); it was not cherry-picked from several tried windows.

