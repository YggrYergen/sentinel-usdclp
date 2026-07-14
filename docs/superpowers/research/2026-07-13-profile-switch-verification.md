# Profile switch verification — SENTINEL20 (read-only)
Date: 2026-07-13 · Branch: `alvaro` · Account: DEMO 2883015767 (per `CUENTAS.md`) · Verifier: read-only, changed nothing.

## VERDICT: **CONFIRMED**
Profile `SENTINEL20` is demonstrably active, all 39 Sapitos EAs were removed on the switch with zero EA activity afterward, the attached account is the correct DEMO (2883015767, trade_mode=0), there are ZERO open positions and ZERO pending orders, and the executor dry-run ran clean with zero orders sent.

**Deviations from the pre-switch expectation (factual, not failures):** the terminal was **restarted** since the previous session (new PID), and the user **closed** the pre-existing XAUUSD BUY 1.5 magic=0 position and then did a few manual round-trip trades that netted flat. The account is currently **flat** (0 positions), not holding the BUY 1.5. This is a safer state, not a violation.

---

## Checklist → evidence

### 1. Terminal running + correct install — PASS
```
ProcessId : 51060
CreationDate : 13/07/2026 10:28:14 p. m.
CommandLine : "D:\FOREX\MT5_Portable\terminal64.exe"  /portable
```
Single `terminal64.exe`, portable DEMO path — NOT `C:\Program Files\MetaTrader 5\...` (the REAL terminal). PID is **51060**, created 22:28:14 — different from the previous session's PID 51496. The terminal was **restarted** since the runbook-execution session (it started 07:45 per that doc; the current instance started 22:28:14). API attach confirms path `D:\FOREX\MT5_Portable`, connected=True.

### 2. Profile switch happened — PASS (terminal journal is the authoritative evidence)
Journal `MT5_Portable/logs/20260713.log` (UTF-16), sequence:
- 22:28:16 — 39× `expert TOKATA_Sapitos_v3 (XAUUSD,M5) loaded successfully` (fresh terminal start loaded FORWARD39).
- 22:28:26 — 39× `expert TOKATA_Sapitos_v3 (XAUUSD,M5) removed`.
- 22:28:27.016 — **`automated trading is disabled because profile has been changed`** ← the profile switch.
- After 22:28:27: **zero** `Experts` lines of any kind for the rest of the log (verified by filtering all post-switch lines).

`common.ini` still literally reads `ProfileLast=FORWARD39` (mtime 22:30:54) — this key records the *startup/last-saved* profile written on graceful exit, NOT the live in-session profile; it does not reflect the live switch and is not authoritative here. The authoritative signal is the journal above. On-disk `SENTINEL20/` dir mtime 22:24:25 (created pre-switch, intact); FORWARD39 mtime unchanged (8/07) — MT5 did not re-save FORWARD39 on switch.

### 3. Sapitos EAs are OFF — PASS
- Journal: all 39 Sapitos experts `removed` at 22:28:26, immediately before the profile-changed line; no expert load/init/tick lines afterward.
- Expert log `MQL5/Logs/20260713.log`: last line is the same `automated trading is disabled because profile has been changed` at 22:28:27.016; file is now **0 bytes on subsequent writes / silent since the switch** — expert channel went quiet.
- SENTINEL20's 4 charts contain **zero `<expert>` blocks** (UTF-16-aware parse), all symbol=XAUUSD:
  `chart01..04.chr: expert_blocks=0 symbol=XAUUSD`.

### 4. Account + safety — PASS
Read-only Python API attach (initialize → account_info → shutdown):
```
initialize: True (1, 'Success')
account: login=2883015767 trade_mode=0 name='Tomas Gemes 2' server='Capitaria-All' currency=CLP
terminal path='D:\FOREX\MT5_Portable' connected=True trade_allowed=False
balance=63386851.53 equity=63386851.53 margin=0.0 margin_free=63386851.53 CLP
```
login==2883015767, trade_mode=0 = TRADE_MODE_DEMO. Correct DEMO account. (trade_allowed=False at terminal level is because AutoTrading was disabled by the profile change — an extra safety, not a problem.)

### 5. Positions unchanged — CHANGED BY USER, now flat (reported factually)
`positions_get()` → **0 positions**. `orders_get()` → **0 pending orders**.
The previously-known XAUUSD BUY 1.5 lots magic=0 (#55110294) is **gone** — journal shows the user closed it at 22:30:28 (`market sell 1.5 XAUUSD, close #55110294 ... at 4018.38`), followed by manual sells/buys at 22:30:47–22:32:10 that netted back to flat. Zero positions in Sapitos bands 330xxx/334xxx/335xxx and zero in executor band 720xxx (there are simply zero positions at all). margin=0.0 confirms flat.

### 6. Executor dry-run — PASS
`python -m scripts.live.run_live_20 --once`:
```
INFO connected + guard OK: DEMO login 2883015767 (dry_run=True, 20 configs, window=10000)
INFO === cycle ... | guard OK | kill=False | dry_run=True ===
[SS-M2] ... actions: none   ... (all 20 configs, one line each, "actions: none")
[V11-M2] ... actions: none
INFO executor stopped cleanly.
```
Guard OK (DEMO 2883015767 confirmed inside the executor), 20 configs loaded, dry_run=True, zero actions/orders, clean exit.

### 7. No stray automation — PASS
Python processes:
```
20472  run_service.py --force-historical --port 8601   (read-only service; no Python order path exists per recon docs)
77420  scripts/dev/e2e_service.py --port 8611           (e2e test harness)
```
`e2e_service.py` grep for `order_send|order_check|--arm|assert_demo` → no matches (not a trade path). No armed executor is running. No process attached that could place orders.

---

## What the user still needs to know / do
- Nothing is required for safety — the system is in the intended safe state (SENTINEL20 active, Sapitos off, DEMO, flat, dry-run clean).
- The account is **flat**: the old BUY 1.5 was closed by the user and manual trades netted to zero. If any of those manual trades were unintended, review deals #55814310–55814318 in the terminal history; all are magic=0 manual, none from an EA.
- Cosmetic: `common.ini` `ProfileLast=FORWARD39` will auto-update to SENTINEL20 only on the next graceful terminal exit; it does not affect the current live profile.
- `--arm` remains not attempted and not recommended until the parity protocol has been exercised.
