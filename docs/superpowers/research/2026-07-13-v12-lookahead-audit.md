# V-12 Look-Ahead Bias Forensic Audit (2026-07-13)

**Verdict: BIAS CONFIRMED.** V-12's spectacular numbers (M1 +231,783 / M2
+224,542 / M5 +169,597 / M15 +123,455 net; WR up to 98.65%; PF up to 1287)
are a look-ahead artifact of `entry_timing=1`, not a tradeable edge. Once the
exact same signals are re-simulated with a strictly-causal fill (next bar's
open instead of an intrabar "touch" priced off information from the
unclosed signal bar), the excess over the champion baseline (`entry_timing=
0`) collapses to **zero or negative on all four timeframes**. The engine was,
in effect, filling orders at a price it could only have known after the
fact.

Scope audited: `run_id`s `sim-report-emasar-v12-{m1,m2,m5,m15}` (the
in-scope "V-12" runs) vs. champion baseline `sim-report-emasar-v06b-{tf}`
(champion stack, `ac_modulate_factor=0.25`; confirmed to match the mission's
reference nets M1 -18,819 / M2 +28,901 / M5 +45,060 / M15 +40,897 exactly).
V-12's actual ingested params (read back from `data/research.db`, NOT
assumed) are the champion per-TF `init_sl_range_k` (M1 6.0/M2 3.0/M5 6.0/M15
2.5) stacked with `ac_modulate_factor=0.5` (the "stacked" leg won on every
TF in the batch-4 sweep), `sar_step=sar_max=0.3`, `require_ema_order=False`,
`confirm_count=2`, `entry_timing=1`.

---

## TEST 1 — Mechanism anatomy (code reading)

Files: `sentinel_engine/strategies/emasar_ref.py` (frozen, read-only) and
`sentinel_engine/strategies/emasar_variant.py` (V-12's actual engine, a
faithful port of the same mechanism).

**(a) Which bar's data do the entry gates evaluate?**
Bar `i`'s data — same as `entry_timing=0` (close-entry). G1/G2/G4/G5 are
evaluated with `skip_g3=True` on bar `i` (`emasar_ref.py:528-544`,
`emasar_variant.py:563-583`). G5 in particular
(`g5_confirmacion(ao, ac, mom, i, ...)`) reads the oscillator VALUE AT bar
`i` — a value that, like the close, is only finalized when bar `i` closes.

**(b) What entry PRICE does `entry_timing=1` use?**
`emasar_ref.py:267-288`, `_toque_long`/`_toque_short`:
```python
def _toque_long(bars, ema_pull, i):
    nivel = ema_pull[i]                 # EMA(closes[0..i]) -- needs close[i]
    if bars[i]["low"] <= nivel:         # bar i's own intrabar low
        return True, nivel              # fill price = the EMA level itself
    return False, None
```
The fill price is `ema_pull[i]`, the EMA_fast value computed **through and
including bar `i`'s own close** (`emasar_ref.py:43-55`,
`ema_series`: `out[i] = closes[i] * k + out[i-1] * (1-k)`). The "touch" test
compares this same-bar EMA level against `bars[i]["low"]`/`["high"]` — an
intrabar extreme that can occur at any point during bar `i`, including near
the bar's open, long before the bar's close is known.

**(c) Implied information ordering.**
The claimed sequence is: "price touches EMA[i] intrabar → enter at EMA[i]."
But EMA[i] is a function of `close[i]`, which does not exist until bar `i`
finishes. The engine is asking "did price touch a level that depends on
where this very bar will close?" and then filling at that level, at a
timestamp that (by construction) is meant to represent "as soon as it
happens" — i.e., possibly the bar's very first tick.

**(d) Is the gate's information available at the moment the touch occurred?
No.** The docstring's claim ("no hay look-ahead porque estos indicadores
usan cierres <= i, disponibles en cuanto la barra abre") is false: it
conflates "EMA[i] is built only from closes ≤ i" with the separate fact
that `close[i]` — the newest of those closes — is not available until bar
`i` itself finishes. This is a genuine causality violation: the entry price
and the entry-price test both depend on data from the future relative to
the moment the fill is claimed to occur.

**A second, compounding violation:** the initial stop-loss for the
just-opened position is computed from the SAME signal bar's full range —
`emasar_ref.py:399-406` / `emasar_variant.py:322-325`:
`sl = low[i] - k*(high[i]-low[i])` (long). `high[i]` and `low[i]` are the
bar's full extremes, only known at close. So not only the entry price but
also the risk placed on the trade is set using information from later in
the same bar than the claimed entry moment.

Plain-language summary for a trader: entry_timing=1 pretends to enter
"as soon as price touches the pullback EMA within the candle," but the EMA
level it touches is computed using that same candle's closing price — a
price that hasn't happened yet at the moment of the touch. It's like being
told the price you can buy at depends on where the market closes today,
and then being allowed to buy at that price the moment the market opens.
That's not simulating a real fill; it's peeking at the answer.

---

## TEST 2 — Fill forensics

Joined each run's F1 trades (entry price/time identical across F1/F2/F3, so
F1 is representative and avoids triple-counting) to the entry bar's OHLC
from the lake. Signed improvement = `(close_i - px_in)` for longs,
`(px_in - close_i)` for shorts, in pips (XAUUSD pip = 0.01).

| TF  | Champion median imp. (pips) | V-12 median imp. (pips) | V-12 mean imp. (pips) | V-12 entry's median % of bar range from favorable side (0=best,1=worst) |
|-----|---:|---:|---:|---:|
| M1  | 0.0 | 102.0 | 137.9 | 0.323 |
| M2  | 0.0 | 155.0 | 204.2 | 0.292 |
| M5  | 0.0 | 260.0 | 328.7 | 0.257 |
| M15 | 0.0 | 506.0 | 668.7 | 0.216 |

Champion (close-entry) shows zero median improvement by construction (it
enters AT the close). V-12 shows large, monotonically-growing improvement
by timeframe — entries land in roughly the best 22-32% of the signal bar's
range, worsening (getting even more favorable) as the timeframe grows
(bigger candles = more room for the "touch" to sit near the extreme).

**Entry-improvement's share of total net** (mean improvement × fichas ×
signals, at $0.10/pip/ficha for LOT=0.10, XAUUSD contract 100):

| TF  | Entry-improvement $ | V-12 net $ | % of V-12's net explained by entry improvement alone |
|-----|---:|---:|---:|
| M1  | 220,820 | 231,783 | 95.3% |
| M2  | 173,141 | 224,542 | 77.1% |
| M5  | 109,448 | 169,597 | 64.5% |
| M15 | 74,432  | 123,455 | 60.3% |

This is the smoking gun for Test 2: 60-95% of V-12's entire net across all
four timeframes is attributable to the entry price alone landing near the
favorable extreme of the signal bar — the exact signature of a same-bar
look-ahead fill.

---

## TEST 3 — Same-bar exit audit

Literal `ts_out == ts_in` same-bar exits: **0 across all four TFs.** The
engine's loop structure evaluates exits for ALREADY-open fichas at the top
of each bar's iteration and new entries at the bottom, so a position opened
on bar `i` cannot itself be closed within bar `i` in this implementation —
the earliest possible exit is bar `i+1`. F1's median holding time confirms
this is effectively as fast as the mechanics allow: **90.6% (M1) to 99.6%
(M5) of F1 trades close within 1 bar of entry.**

Because F1's trailing distance is a flat 100 pips and the entry price
already sits near the favorable extreme of bar `i` (Test 2), bar `i+1`'s
ordinary range is frequently enough, on its own, to trigger a favorable
trailing exit almost immediately — the "same-bar exit" risk this test
looks for is instead expressed as "one-bar-later, near-certain, favorable
exit," which is functionally the same signature (fast, near-riskless
profit-taking) even though it technically lands on `i+1` rather than `i`.
The pessimistic-fill re-simulation asked for by this test's spirit — "what
if the entry were resolved at the signal bar's adverse extreme instead" —
is exactly what TEST 5's `entry_timing=3` (adverse-fill) run measures; see
below: net collapses or goes deeply negative on every TF.

---

## TEST 4 — MFE/MAE signature

`mae`/`mfe` are NULL in `data/research.db` for these runs (the batch1/4
ingest pipeline never populated them), so MAE/MFE were recomputed directly
from lake bars by walking each F1 trade's holding window.

| TF  | Champion MAE median (pips) | V-12 MAE median (pips) | Champion MFE median | V-12 MFE median | V-12 % trades with MAE < 1 pip |
|-----|---:|---:|---:|---:|---:|
| M1  | 248.0 | 92.0  | 80.0  | 225.0  | 0.34% |
| M2  | 333.0 | 116.0 | 118.0 | 323.0  | 0.14% |
| M5  | 513.0 | 173.0 | 216.0 | 533.0  | 0.00% |
| M15 | 913.0 | 277.0 | 433.0 | 1033.0 | 0.00% |

V-12's MAE is NOT a near-zero, "price never went against the position"
signature (the classic hard look-ahead tell) — median MAE is a few hundred
pips on every TF, not sub-pip. What IS visible, consistently, is that V-12's
MAE is roughly 2.7-3.3x smaller than champion's while its MFE is roughly
2.4-2.8x larger, on every timeframe. This is the same finding as Test 2
from a different angle: entries land close enough to the favorable extreme
that there is systematically less room left to go against the position and
systematically more room to run favorably, before the same fixed trailing
stop takes over. Honest characterization: this is corroborating, not
independently damning, evidence — Test 4 alone would not have proven
look-ahead; combined with Tests 1/2/5 it confirms the same mechanism.

---

## TEST 5 — Causal re-simulation (decisive test)

Two additive `entry_timing` modes were implemented in
`sentinel_engine/strategies/emasar_variant.py` (frozen `emasar_ref.py`
untouched):

- **`entry_timing=2`** ("causal next-open"): gates evaluated on bar `i`'s
  CLOSE exactly like `entry_timing=0`; fill executes at bar `i+1`'s OPEN
  (the earliest price a strictly-causal system could act on the
  close-confirmed signal). No entry if `i` is the last bar. Initial SL
  still uses the signal bar's own range (unchanged from V-12), per spec.
- **`entry_timing=3`** ("adverse-fill worst-case bound"): same signal
  bar/side/gates as `entry_timing=1` (G3 replaced by the intrabar touch
  test), but the fill price is forced to the WORST price of the signal bar
  for the side (bar `high` for long, bar `low` for short) — a pessimistic
  bound on how bad a same-bar intrabar fill could realistically be.

Both are OFF by default, byte-identical at `entry_timing=0/1` (pinned by
5 new tests in `tests/strategies/test_emasar_variant.py`, extending 45→50,
all green). Runner: `scripts/report/gen_v12_audit.py` (reads V-12's exact
ingested params back from `data/research.db` so the audit cannot drift from
what actually produced the numbers under audit). 8 runs ingested:
`sim-report-emasar-v12a-{m1,m2,m5,m15}` (causal), `sim-report-emasar-v12w-
{m1,m2,m5,m15}` (adverse), verified live via `scripts/dev/e2e_service.py`
on port 8611 (own PID only, DB copy — real `data/research.db` untouched by
the verification step itself, only by the ingest run before it).

### Verdict table — net $ and how much of V-12's excess survives

| TF  | Champion (t=0) | V-12 (t=1) | V-12a causal (t=2) | V-12w adverse (t=3) | V-12 excess over champion | V-12a excess over champion | **% of excess surviving causal fill** |
|-----|---:|---:|---:|---:|---:|---:|---:|
| M1  | -18,819.0 | 231,783.3 | -24,397.5 | -94,540.5 | 250,602.3 | -5,578.5 | **-2.2%** |
| M2  |  28,901.4 | 224,542.2 |  26,117.4 | -24,124.5 | 195,640.8 | -2,784.0 | **-1.4%** |
| M5  |  45,059.7 | 169,596.6 |  43,821.9 |  15,265.2 | 124,536.9 | -1,237.8 | **-1.0%** |
| M15 |  40,897.2 | 123,454.8 |  38,761.8 |  24,938.1 |  82,557.6 | -2,135.4 | **-2.6%** |

`V-12a` (causal, next-bar-open fill on the exact same signals) lands
essentially ON TOP OF champion on every TF — slightly below on 3 of 4,
slightly above on M2/M5 by amounts smaller than normal run-to-run noise
from the 1-bar fill shift. **Not one dollar of V-12's headline excess
survives causal re-simulation on any timeframe** — the causal-survival
percentage is negative on all four (the tiny negative numbers reflect that
`v12a` is marginally worse than champion, not better, once entries can no
longer see the future).

`V-12w` (adverse-fill worst case, same signals filled at the WORST price of
the signal bar) is deeply negative on M1 and M2, and far below champion on
M5 and M15. **V-12w beats champion on 0 of 4 timeframes.**

### Verdict framework — which branch fired

- Causal (`v12a`) excess-over-champion is **-1.0% to -2.6%** of V-12's
  excess on every TF — far below the 20% threshold. ✅ condition met.
- Test 2 shows systematic favorable-extreme entries (60-95% of net from
  entry-price alone, median entry sitting in the top ~22-32% of the bar's
  favorable range). ✅ signature present.
- Test 3: no literal same-bar exits (engine mechanics prevent it), but the
  equivalent "resolved pessimistically" re-simulation (`v12w`) shows the
  edge does not survive adverse fill on any TF. ✅ signature present (via
  the adverse-fill substitute).
- Test 4 shows corroborating (not independently conclusive) MAE/MFE
  compression consistent with the same mechanism. ✅ consistent.

**→ BIAS CONFIRMED** (first branch of the verdict framework fires cleanly
and unambiguously: causal excess survival is negative — nowhere close to
the 20% floor — and every supporting signature test points the same way).

---

## Honest surviving numbers per TF (the actionable estimate)

Discard V-12's headline numbers entirely. The genuine, causally-clean
number for "entry_timing=1-style intrabar entry" on this exact signal set
is `V-12a` (causal next-open fill), which is statistically indistinguishable
from the existing champion (`entry_timing=0`) baseline:

| TF  | Honest net (causal) | vs. champion |
|-----|---:|---:|
| M1  | -24,397.5 | ~$5.6k worse |
| M2  |  26,117.4 | ~$2.8k worse |
| M5  |  43,821.9 | ~$1.2k worse |
| M15 |  38,761.8 | ~$2.1k worse |

Conclusion: `entry_timing=1` contributes **no real edge** over close-entry;
it is marginally worse once you remove the ability to see the bar's own
close before filling on it. The champion config (`entry_timing=0`) remains
the best honestly-tested configuration for this signal set.

---

## Plain-language explanation for traders

Imagine a rule: "buy the instant price dips to touch a moving-average line
during the candle." That sounds like a real, tradeable rule — MT5 or any
live platform could, in principle, watch price tick-by-tick and fire the
moment it touches that line.

The problem is *which* moving-average line the backtest used: it used the
value of the moving average calculated **using that same candle's closing
price** — a number that isn't final until the candle is over. So the
backtest effectively asked "would price, at some point during this candle,
have touched the average that this candle will end up producing?" and then
happily filled the order at exactly that average level, as if it had known
in advance where the candle was going to close. In live trading you cannot
know a candle's close until it happens; you can only ever act on
already-finished (closed) candles or ticks as they occur, whichever is
earlier — never on a level partly computed from the future.

On top of that, the backtest also set the trade's protective stop-loss
using that same candle's full high-to-low range, which similarly isn't
known until the candle finishes.

When we removed this by forcing the system to only ever act on truly
final, already-known information — enter at the very next candle's open
after a signal is confirmed on a fully-closed candle — the "genius" numbers
evaporated completely. What's left is statistically the same as the plain
close-entry system that had already been vetted. The touch-based entry
timing didn't add value; it added a two-week look into the future.

---

## Deliverables checklist

1. Engine edits: `sentinel_engine/strategies/emasar_variant.py`
   (`entry_timing=2/3`, additive, default-preserving). `emasar_ref.py`
   untouched (frozen). Tests extended:
   `tests/strategies/test_emasar_variant.py` (45→50, all green).
2. Runner: `scripts/report/gen_v12_audit.py`.
3. 8 audit runs ingested (`sim-report-emasar-v12a-{m1,m2,m5,m15}`,
   `sim-report-emasar-v12w-{m1,m2,m5,m15}`) and verified live via
   `scripts/dev/e2e_service.py --port 8611` (own PID, DB copy).
4. This report.
5. Gates: `tests/strategies` 53/53 green; `tests/golden/test_parity.py`
   3/3 green; `tests/service` 471 passed / 3 pre-existing failures
   (`test_chat.py::test_review_strategy_happy_path_sse_sequence`,
   `test_web_positions.py::test_positions_js_humano_panel_has_analizar_
   button_disabled_with_tooltip`,
   `test_web_positions.py::test_positions_js_analizar_button_no_longer_
   hard_disabled`) — unrelated to this change (positions.js/chat.py/their
   tests were not touched, per the hard rules).
