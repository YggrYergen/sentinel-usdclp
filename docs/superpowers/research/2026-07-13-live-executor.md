# Guarded Python live executor — the 20 validated configs (2026-07-13)

Order-capable daemon that runs the 20 curated EMASAR-variant configs against the
**MT5 DEMO 2883015767** by **recompute-and-reconcile per closed bar**, reusing
`simular_variant` so live == sim by construction. Delivered UNCOMMITTED. The
user arms it; this session placed **zero** live orders.

## Files delivered
- `sentinel_engine/live/guard_cuenta.py` — hard account guard (`assert_demo`).
- `sentinel_engine/live/reconciler.py` — pure diff core (no MT5, unit-testable).
- `scripts/live/run_live_20.py` — the executor daemon (attach-only, dry-run default).
- `sentinel_engine/strategies/emasar_variant.py` — **one additive, default-OFF**
  kwarg `return_state=False`. When True, `simular_variant` returns
  `(events, {"open":…, "last_bar_exits":…, "last_idx":…})` — the still-open
  fichas (side/entry/current-SL) plus exits that fired on the last closed bar.
  Default path (`return_state` omitted) is **byte-for-byte** unchanged; proven
  by the 56 pre-existing strategy tests + a back-compat pin
  (`test_return_state_default_off_is_backcompat`).
- Tests: `tests/live/test_guard_cuenta.py`, `test_reconciler.py`,
  `test_executor_dryrun.py`.

## Architecture as built
**Per config, each cycle** (`run_live_20.run_cycle`):
1. `guard_cuenta.assert_demo(mt5)` — re-checked EVERY cycle before any order.
2. Read STOP kill-switch file.
3. `fetch_bars` → `mt5.copy_rates_from_pos(sym, TF, 0, window+1)`, **drop the
   forming bar** → act on closed bars only. Live MT5 rates chosen over the lake
   for freshness; same OHLC the sim consumes.
4. `simular_variant(bars, return_state=True, **kwargs)` → desired open-ficha
   state at the last closed bar (V10 #14/#15 get a `direction_mask` computed
   live via `scripts.report.gen_variant_batch5.compute_direction_mask` on the
   same rates — previous CLOSED M15 bucket; V11 #20 `blocked_hours` uses the bar
   timestamps' server hours inside the sim). Identical bars → identical
   decisions = the parity property.
5. `fetch_live_positions` → MT5 positions filtered to this config's ficha band
   `[base+1 .. base+3]` (F1/F2/F3 per TOKATA magic convention).
6. `reconciler.reconcile(desired, live)` → ordered actions: CLOSE orphans /
   SAME_BAR_EXIT_FALLBACK, then MODIFY (trail SL), then OPEN, plus NOOP /
   REJECT_* / SUPPRESSED_OPEN / MISSING_SL_ALARM.
7. `execute_action` — dry-run logs the intent; `--arm` sends `order_send`.

Fills happen at the **next tick after bar close** (the sim is close-driven);
the shadow-parity checker already tolerates spread + 1 tick, so this is
expected, not a divergence.

### Intra-bar stop semantics (design addendum, mandatory)
- **Server-side SLs are mandatory.** Every open ficha carries a real MT5 SL at
  the sim's current stop, so the broker executes mid-bar exactly like the sim's
  `low <= sl` check. `reconcile` emits MODIFY whenever the sim's trail moved; a
  live position with SL None/0 emits **MISSING_SL_ALARM** (logged at ERROR) and
  a paired MODIFY installs it. MODIFY failures are retried (`modify_retries`,
  default 2) and, if still failing, logged as an ALARM (ficha may lack intra-bar
  protection).
- **Same-bar exit fallback.** The sim can raise a trail using the just-closed
  bar's OWN high/AC and stop out WITHIN that bar; live's server SL sat at the
  prior bar's level, so it did not. Detected via `last_bar_exits`: an open live
  ficha that is flat in the new desired state AND appears in `last_bar_exits`
  becomes **SAME_BAR_EXIT_FALLBACK** → market-close next tick. The by-design
  price gap (sim exit level vs live market fill) is accumulated in `$` per
  config (`same_bar_cost`) and logged each cycle as *"same-bar optimism, by
  design"* — **NOT** a hard divergence.
- **Parity-checker taxonomy note (no code change made).** `check_live_sim_parity.py`
  currently classes exit-price gaps only as `EXIT_PRICE_WITHIN_TOL` /
  `EXIT_PRICE_OUT_OF_TOL`. A same-bar-exit market fill can legitimately land
  **beyond** spread+tick tolerance and would today be flagged HARD. Rather than
  edit the read-only checker, the **executor side owns the `$` quantification**
  (`same_bar_cost` in the audit log). RECOMMENDATION for a follow-up: add a
  `SAME_BAR_OPTIMISM` non-hard class to the checker keyed off the sim exit motivo
  + same-bar timing, and sum its `$` cost — noted here, deliberately not done.

### Exposure asymmetry (must drive week-1 review)
Configs with `ac_modulate_factor=0.01` — **SS-\*** (#1,4,7,19) and **V06D-\***
(#2,5,9) — collapse the trail to ~1% of distance on AC-decel bars (effective
~1-pip trail), so they same-bar-exit **frequently** → **highest** exposure to
the sim-vs-live gap. The `0.10`/`0.25` configs (V06C, V13, V15, V10, V11,
V09-CTRL) are far less exposed. Week-1 parity review must look at the
accumulated **SAME_BAR cost per config**, concentrating on the 0.01 group.

## Safety rails → where enforced
| Rule | Enforcement |
|---|---|
| DEMO 2883015767 only; REAL 2883011573 never | `guard_cuenta.assert_demo`: login must == DEMO, must != REAL, `trade_mode` == DEMO; else `GuardError` + `sys.exit(2)`. Called after connect AND every cycle before any order. |
| ATTACH-ONLY / NEVER LAUNCH | `run_live_20._portable_running` inspects process command lines (wmic → PowerShell fallback) for the portable path *before* importing/initializing MT5; if absent → prints "open MT5_DEMO_TOMAS.bat", returns exit 3, `initialize()` never reached. Connect uses `initialize(path=<portable exe>, portable=True)`, never a bare `initialize()`. |
| Dry-run by default | `--arm` required to send; otherwise every sendable action is logged only. |
| `--arm` confirmation | Red banner + must type the account number (`_arm_confirm`). |
| Volume cap 0.10/ficha | `reconciler`: `volume > MAX_VOLUME` → REJECT_VOLUME (rejected, never clamped). |
| Fichas cap 3/config, 60 total | 3/config is structural (3 slots); 60-total → REJECT_CAP via `total_open_fichas` threaded across configs. |
| Kill-switch | `scripts/live/STOP` file checked each cycle → OPENs become SUPPRESSED_OPEN; CLOSE/MODIFY still applied; logging continues. Ctrl-C → clean shutdown. |
| Audit log | All actions logged structured+timestamped to console + `scripts/live/run_live_20.audit.log`, per magic, with guard/kill status each cycle. |

## Test / gate results
- `tests/live` — **47 passed** (guard: correct/wrong/real/trade-mode/None/hard-exit;
  reconciler: open/close/SL-update/noop/same-bar-fallback/missing-SL-alarm/vol-cap/
  total-cap/kill-switch/wrong-side/magic-isolation; executor: never-launch,
  dry-run-sends-nothing, guard-blocks-real, unknown-config, **parity smoke
  SS-M5 & V10-M15**, back-compat).
- `tests/strategies` + `tests/scripts` + `tests/live` — **129 passed**.
- Parity/golden (`test_emasar_ref`, variant parity pins) — pass; `simular_variant`
  default behavior byte-for-byte preserved.
- `tests/service` — **3 failed** (the known pre-existing set: `test_chat.py`
  review-SSE, two `test_web_positions.py` analizar-button), 471 passed. Untouched
  files (`chat.py`, `positions.js`) as required.

## How to run (acceptance protocol)
```
# 0. Open the demo terminal (user):  D:\FOREX\MT5_DEMO_TOMAS.bat
# 1. DRY-RUN, single cycle, all 20 (safe; sends nothing):
python -m scripts.live.run_live_20 --once
# subset / daemon dry-run:
python -m scripts.live.run_live_20 --configs SS-M5,V10-M15
# 2. Run one live DEMO session dry-run for a while, then check parity:
python -m scripts.live.check_live_sim_parity --config all --start 2026-07-14 --end 2026-07-15
# 3. ARM (user only — banner + type 2883015767):
python -m scripts.live.run_live_20 --arm
```
Kill-switch: `type NUL > scripts\live\STOP` to freeze new opens; delete to resume.

## Go-live runbook (user, 5 steps)
1. **Open the demo terminal** via `D:\FOREX\MT5_DEMO_TOMAS.bat` (login
   2883015767, portable). Do NOT open the REAL terminal alongside for this.
2. **Inventory / retire the ~39 legacy Sapitos charts** — remove their EAs
   manually (or start from a clean MT5 profile) so only the executor's magics
   (720011–720203) trade. Sapitos magics (330xxx/334xxx/335xxx) are outside the
   executor's bands, but leaving them running mixes exposure.
3. **Dry-run one full session:** `python -m scripts.live.run_live_20` (no
   `--arm`). Watch `run_live_20.audit.log`: guard OK each cycle, intended
   OPEN/MODIFY/CLOSE make sense, MISSING_SL_ALARM count is 0.
4. **Run the parity checker** over that session
   (`check_live_sim_parity --config all …`) → expect MATCH (tolerated diffs OK).
   Review the executor's **SAME_BAR cost** line, especially the 0.01 configs.
5. **Arm:** `python -m scripts.live.run_live_20 --arm`, type `2883015767`. Keep
   the STOP file handy; keep MT5 open (attach-only — the daemon never launches it).

## Limitations
- **Bar-close granularity:** decisions fire at bar close; live fills at the next
  tick (spread + 1 tick, tolerated). Same-bar trail exits can't be replicated
  mid-bar → handled via SAME_BAR_EXIT_FALLBACK + `$` accounting (see above); the
  0.01-factor configs carry the residual optimism bias.
- **Restart / reconcile-on-boot:** stateless by design — on boot the first cycle
  recomputes desired state from the trailing window and reconciles against
  whatever positions exist in each magic band, self-healing (opens missing,
  closes orphans, re-installs SLs). No persisted per-ficha state to corrupt.
- **Weekend/market-closed:** `copy_rates_from_pos` returns no fresh closed bar →
  `fetch_bars` empty → cycle logs "no bars" and idles; no action. Positions are
  left as-is; SL modifies resume when bars return.
- **Window:** default 10 000 bars (≥ vol_regime_window=200 warmup + AO 34);
  floored at 3 000. Larger windows = more warmup fidelity at more compute.
- **`compute_direction_mask` / batch5 import** is a lazy dependency for V10 only;
  if `scripts/report` moves, those two configs need the import path updated.
```
