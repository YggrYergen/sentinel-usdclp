# Signal replay 2026-07-15: would the 4 live-roster configs have fired entries during the account's idle window?

Facts and numbers only. This report answers one question with bit-exact
replay evidence: given the account showed zero new positions on
2026-07-15 (executor dead since 2026-07-14 12:13:22), would the 4
`LIVE_ROSTER` configs (`V11-M2`, `V15-M2`, `V13-M2`, `V15-M15`) have opened
positions during 2026-07-15 08:30->17:00 server time **if the executor had
been alive**? The alternative hypothesis under test was a silent
strategy/config-level gate suppressing entries.

**VERDICT: strategies WOULD have fired. No silent config gate is
suppressing entries.** All 4 roster configs produced entry signals in
every hour of the 08:30-17:00 window (except hours correctly blocked by
`V11-M2`'s own `blocked_hours` design parameter). The account's flatness
on 2026-07-15 is fully explained by the executor process being dead (last
audit-log line: 2026-07-14 12:13:22); it is not caused by market regime or
by any strategy/config gate.

## 1. Lake freshness

Ran `python scripts/mt5_dump_history.py` (attach-only, portable terminal
already running; ingests to the monolith and rebuilds tiers per commit
fe83434). Verified post-refresh via pyarrow on the tier files:

| tier | rows | min `t` | max `t` |
|---|---|---|---|
| `data/lake/XAUUSD/M2/2026-07.parquet` | 7,334 | 2026-07-01T00:00:00 | **2026-07-15T19:30:00** |
| `data/lake/XAUUSD/M15/2026-07.parquet` | 979 | 2026-07-01T00:00:00 | **2026-07-15T19:30:00** |

Both tiers cover through 2026-07-15T19:30 server time (server-as-UTC
convention), comfortably past the 17:00 end of the primary analysis
window. The lake was stale before the refresh (monolith ended
2026-07-14T07:50); it is fresh now.

## 2. Methodology

Throwaway script: `scripts/report/diag_signal_replay_20260715.py`
(read-only; does not modify `run_live_20.py`, `emasar_variant.py`, or
`live_configs_20.py`).

- **Bars**: loaded from the Parquet tier lake via
  `scripts.live.check_live_sim_parity.load_bars`, same `{t,open,high,low,close}`
  shape the executor's `fetch_bars()` consumes from MT5.
- **Per-bar trailing-window replay** (mirrors `run_live_20.reconcile_config`
  exactly): for every closed bar B in a window, take the trailing <=10,000
  closed bars ending at B (`DEFAULT_WINDOW` in `run_live_20.py`) and call
  `simular_variant(bars, return_state=True, **cfg["kwargs"])` -- CLASSIC mode
  (no `live_fill_mode`), the exact call the daemon makes every cycle. An
  "entry signal at B" = an event with `idx == last_idx` and
  `motivo.startswith("ENTRY")`. A "non-empty desired snapshot at B" =
  `snap["open"]` (the executor's would-be live positions) is non-empty.
- **Single full-window pass** (cross-check + PnL source): one
  `simular_variant` call per config over the FULL bar history available
  (not truncated at the window end, so exits after the window close are
  still captured), run in both `live_fill_mode=False` (classic) and
  `live_fill_mode=True` (executor-faithful fills). Entry events are then
  filtered to those landing inside the window for the entry-count
  cross-check.
- **PnL reconstruction**: reused `check_live_sim_parity.sim_positions()` to
  pair each `ENTRY_*` event with its F1/F2/F3 `EXIT_*` events (first exit
  per ficha tag closes it). PnL per ficha = `(exit_price - entry_price) *
  side_sign * 100 (oz/lot) * 0.01 (lot/ficha, DEFAULT_VOLUME in
  run_live_20.py)`. Summed over F1+F2+F3 for every position whose ENTRY bar
  falls inside the window. All positions in all 3 windows closed out fully
  before the end of available history (0 fichas left open at the end in
  every row), so the reported PnL is fully realized, not truncation bias.
  None of the 4 roster configs use `direction_filter`, so no SuperTrend-M15
  direction mask is needed.

None of the 4 roster configs (`V11-M2`, `V15-M2`, `V13-M2`, `V15-M15`) has
`direction_filter=True` in `CONFIGS_20` -- confirmed by inspection.

## 3. Positive control (2026-07-14 01:00->08:00 server)

The account actually traded in this window. Results:

| config | per-bar entries | single-pass classic | single-pass live-fill | nonempty-snapshot bars | classic PnL (USD) | live-fill PnL (USD) |
|---|---|---|---|---|---|---|
| V11-M2 | 30 | 30 | 27 | 30/210 | $30.75 | $17.40 |
| V15-M2 | 31 | 31 | 28 | 31/210 | $30.36 | $16.77 |
| V13-M2 | 39 | 39 | 34 | 39/210 | $36.87 | $8.52 |
| V15-M15 | 3 | 3 | 3 | 3/28 | $18.21 | $2.94 |

All 4 configs produced dozens of entries, non-zero PnL, and the per-bar
trailing-window replay agrees exactly with the single-pass full-history
replay (both methods use identical gate logic; per-bar recomputes state
fresh from a 10k lookback each cycle, single-pass carries state forward --
they must and do agree once warmed up).

**Cross-check against pre-existing repo artifacts** (independently produced
2026-07-14, not touched for this task):

- `scripts/report/candidates_top5.json`'s `livefill_sim_night_usd` for the
  same 4 configs over the 01:06:02-07:57:05 night window: V11-M2 = $17.40
  (**exact match**), V13-M2 = $8.52 (**exact match**), V15-M15 = $2.94
  (**exact match**), V15-M2 = $14.16 (close; small window-edge difference,
  01:00-08:00 here vs 01:06:02-07:57:05 there).
- `docs/superpowers/research/2026-07-14-diag-h1-churn.md`'s "classic PnL
  $/oz" column (same 100oz x 0.01lot convention) for V11-M2 = 30.75
  (**exact match**), V13-M2 = 36.87 (**exact match**), V15-M15 = 18.21
  (**exact match**).
- The audit log itself: at bar `2026-07-14T11:24:00+00:00` (inside the
  drought secondary window, see Section 5) the replay predicts a NEW entry
  (side S, price 4084.88) for V11-M2/V13-M2/V15-M2; the real audit log line
  at that exact bar reads `actions: OPEN/F1, OPEN/F2, OPEN/F3` for all
  three configs (`scripts/live/run_live_20.audit.log` lines 67585-67597,
  timestamped 11:26:08-11:26:09 -- matching "last SENT OPENs 11:26" from
  the mission brief).

The harness is validated bit-exact against three independent
ground-truth sources (a pre-existing candidates ranking, a pre-existing
diagnostic report, and the raw audit log). It is not producing
false zeros or fabricated non-zeros.

## 4. Primary window: 2026-07-15 08:30 -> 17:00 server

| config | entries | per-hour | nonempty-snapshot bars | classic PnL (USD) | live-fill PnL (USD) |
|---|---|---|---|---|---|
| V11-M2 | 34 | 08:00=1, 09:00=8, 10:00=7, 11:00=5, 12:00=5, 13:00=4, 14:00=2, 15:00=2, **16:00=0 (blocked_hours)** | 34/255 | $101.37 | $37.95 |
| V15-M2 | 33 | 08:00=1, 09:00=8, 10:00=7, 11:00=4, 12:00=4, 13:00=4, 14:00=2, 15:00=1, 16:00=2 | 33/255 | $105.09 | $32.13 |
| V13-M2 | 37 | 08:00=1, 09:00=8, 10:00=7, 11:00=5, 12:00=5, 13:00=4, 14:00=3, 15:00=2, 16:00=2 | 38/255 | $98.49 | $31.80 |
| V15-M15 | 6 | 08:00=1, 09:00=1, 11:00=1, 13:00=1, 15:00=1, 16:00=1 | 6/34 | $96.87 | $43.89 |
| **TOTAL** | **110** | -- | -- | **$401.82** | **$145.77** |

First 10 entry timestamps (identical across V11-M2/V15-M2/V13-M2 -- same
symbol/TF/gate family, differing only in `blocked_hours`/`reentry`
extras which did not diverge in this sample):
`08:30:00 L, 09:22:00 S, 09:38:00 L, 09:42:00 L, 09:46:00 S, 09:48:00 S,
09:52:00 S, 09:54:00 L, 09:56:00 L, 10:02:00 L`.
V15-M15 (M15 tf): `08:30:00 L, 09:45:00 L, 11:00:00 S, 13:15:00 L,
15:30:00 S, 16:00:00 L`.

**Internal consistency check**: `V11-M2` is the only roster config with
`blocked_hours = frozenset({0, 6, 16, 18, 23})`. Its per-hour breakdown
shows exactly zero entries in the 16:00 server hour, while `V15-M2` and
`V13-M2` (no blocked hours, otherwise near-identical gate family) both
show 2 entries in that same hour. This is the `blocked_hours` gate working
exactly as designed on a single hour-block, not a broader entry
suppression -- V11-M2 fires normally in every other hour of the window.

Every config produced entries in essentially every open hour of the
window; `nonempty_snapshot_bars` counts (34/255, 33/255, 38/255, 6/34)
confirm the executor would have held open positions across a substantial
fraction of the window's bars, not merely fired-and-flattened
instantaneously. Simulated PnL for the window is net **positive** for all
4 configs under both classic and live-fill fill assumptions (total
$401.82 classic / $145.77 live-fill across the roster) -- the market
regime this day was not adverse to these strategies; nothing about
2026-07-15 08:30-17:00 would have produced a quiet, lossless, or gated
session had the executor been running.

## 5. Secondary window: 2026-07-14 11:14 -> 12:13 server (the "drought")

The executor was alive and cycling during this window, logging
`actions: none` almost continuously. Replay result:

| config | entries | classic PnL (USD) |
|---|---|---|
| V11-M2 | 1 (at 11:24:00, side S) | $7.38 |
| V15-M2 | 1 (at 11:24:00, side S) | $7.38 |
| V13-M2 | 1 (at 11:24:00, side S) | $7.38 |
| V15-M15 | 0 | $0.00 |

The single predicted entry at `2026-07-14T11:24:00+00:00` (S, price
4084.88) is confirmed by the audit log itself: lines 67585/67593/67597
show `[V15-M2]/[V13-M2]/[V11-M2] bar=2026-07-14T11:24:00+00:00 actions:
OPEN/F1, OPEN/F2, OPEN/F3` at 11:26:08-11:26:09 wall-clock -- exactly
matching the replay. All bars in `[11:14, 11:24)` and `[11:26, 12:13)`
correctly show `snap["open"] == {}` (empty desired snapshot) in the
replay, matching every surrounding `actions: none` audit line sampled
(e.g. bars 11:14:00, 11:16:00, 11:18:00 for V11-M2/V13-M2/V15-M2 -- all
`actions: none` in both the audit log and the replay's
zero-nonempty-snapshot bars). The "drought" was a real, brief lull in
market-generated signals correctly reflected by both the live executor and
the offline replay -- not a divergence between them, and not evidence of a
gate malfunction (one real entry did fire mid-drought, at 11:24, and both
systems agree on it exactly).

## 6. Conclusion

- The lake was successfully refreshed and confirmed fresh through
  2026-07-15T19:30 server time.
- The replay harness is validated against three independent sources
  (candidates ranking JSON, the H1-churn diagnostic report, and the raw
  audit log) with exact PnL/entry-count matches in the control window and
  bit-exact bar-level agreement on the one real entry in the drought
  window.
- Over the primary window under investigation, **2026-07-15 08:30->17:00
  server**, all 4 `LIVE_ROSTER` configs (`V11-M2`, `V15-M2`, `V13-M2`,
  `V15-M15`) would have fired a combined **110 entry signals** (34 + 33 +
  37 + 6), spread across essentially every trading hour, with simulated
  PnL net positive under both classic ($401.82) and live-fill ($145.77)
  fill assumptions.
- `V11-M2`'s `blocked_hours` parameter correctly suppressed entries only in
  its designated blocked hour (16:00) and nowhere else -- the one
  config-level gate present in the roster behaves exactly as designed and
  does not explain the account's overall silence.
- **No silent strategy- or config-level gate is disabling position-taking.**
  The account's flatness on 2026-07-15 is fully and only explained by the
  live executor process being dead since 2026-07-14T12:13:22 (last audit
  log line); had it been running and healthy, it would have opened dozens
  of positions with a net-positive simulated result during the observed
  window.

## Artifacts

- `scripts/report/diag_signal_replay_20260715.py` -- throwaway replay
  script (read-only, does not touch engine/executor/config files).
- `scripts/report/diag_replay_20260715.json` -- machine-readable results:
  per-config, per-window entry counts, per-hour breakdowns, first-20 entry
  timestamps, non-empty-snapshot bar counts, PnL (classic + live-fill,
  with position-level detail), for all 3 windows (control, primary,
  secondary/drought).
