# Diagnostic Report — Machine 2 (equipo 2) ran all day with ZERO positions

**Date:** 2026-07-18 (Saturday; market closed — live re-tests must wait for Sunday-evening/Monday open)
**Incident window:** 2026-07-17 (Friday), approx. 07:00–17:00 local, machine 2 powered on the whole time
**Symptom:** the 4 LIVE_ROSTER strategies (V11-M2, V15-M2, V13-M2, V15-M15) took **zero positions all day, with no crash**
**Reference (control):** Machine 1 — this machine — takes positions without problems on the same branch/code (evidence: nights of 2026-07-15/16, 301 tickets filled, retcode 10009)
**Method:** systematic differential diagnosis. Two independent read-only investigators (launch/order path; signal/data path) + orchestrator confirmation of every load-bearing claim against source, plus ground-truth extraction from machine 1's real audit log. **The failing machine was NOT accessible** — this report enumerates ranked candidates and gives the exact evidence to collect on machine 2 to confirm/refute each one.

---

## 1. Executive summary

The stack on machine 2 has **three nested gates**, each with its own log. "Ran all day with zero positions and no crash" is compatible with a failure at ANY of the three — and each failure lands its evidence in a **different file**:

```
[PS watchdog: watchdog_local.ps1]           → log: scripts/live/watchdog_local.log
   └─ gate: Wait-ForDemoAccount (bare mt5.initialize(), $DemoLogin literal)
      └─ [Supervisor: supervisor_live.py]    → log: scripts/live/watchdog.log
            └─ gate: preflight 7/7 (terminal marker, attach, account guard,
               FRESH BARS on XAUUSD, roster, STOP-file absent, audit writable)
            └─ [Executor: run_live_20.py]    → logs: run_live_20.audit.log
                                                    + executor_console.log
                  └─ per-cycle: fetch bars → sim → actions → order_send
```

**The single most important fact:** the code cleanly separates every failure world with distinct, greppable log signatures. One evidence-collection pass on machine 2 (Section 5) classifies the failure deterministically — no guessing needed. The top candidates, ranked:

| # | Candidate | Layer | Confidence |
|---|-----------|-------|------------|
| 1 | **AutoTrading (Algo Trading) OFF in the terminal** → orders sent, all rejected retcode 10027, logged at INFO (looks like success to a naive eye) | Executor/send | **HIGH** — proven failure mode: machine 1's own log shows 10027 streaks |
| 2 | **Supervisor never launched the executor: preflight FAIL all day** (terminal not logged in, marker mismatch, stale/absent `machine_local.json`, or no fresh bars) | Supervisor gate | **HIGH** |
| 3 | **Leftover `STOP` kill-switch file** (PAUSAR_TRADING without REANUDAR) → preflight refuses to arm / OPENs suppressed, by design | Supervisor gate + executor | **HIGH** (trivial to check) |
| 4 | **`machine_local.json` missing** (fresh clone / `git clean` deletes it — it is gitignored!) → profile silently defaults to Machine 1's values → attach check never matches → executor exits 3 in a supervised loop forever | Profile/attach | **MED-HIGH** |
| 5 | **XAUUSD not resolvable / not in Market Watch** in the attached terminal → "no bars available" every cycle (partially fenced by preflight's fresh-bars check, but the check and the loop can diverge over time) | Data feed | **MED** |
| 6 | **PS watchdog gate stuck**: `Test-DemoAccount`'s bare `mt5.initialize()` (no path) attaches to the wrong/none terminal, or terminal launched at boot without auto-login → supervisor never even started | PS watchdog gate | **MED** |
| 7 | Sim legitimately produced zero entries all day ("actions: none") | Strategy | **LOW-MED** — must be falsified by grep, not assumed; note machine 1 was OFF on 2026-07-17, so there is NO same-day control |
| 8 | Rogue dry-run process (started manually without `--arm`) instead of the supervised armed child | Operational | **LOW** |
| 9 | `blocked_hours` server-time miscalibration (V11-M2 only) | Strategy | **LOW as root cause** (affects 1 of 4 configs; real latent bug regardless) |

**Ruled out by direct code inspection:** data-lake/tiers dependency (live path is pure `copy_rates_from_pos`, no lake import); M2-timeframe resampling (native `mt5.TIMEFRAME_M2` constant); roster resolution failure (would FAIL preflight loudly); account-guard refusal (exits code 2 — contradicts "ran all day" only for the executor process, but see candidate 4: the *supervisor* keeps re-launching, so guard-exit loops are still compatible with "everything looks alive").

---

## 2. How the stack works (verified against source, branch `alvaro`)

### 2.1 Machine profile — the per-machine switch

- `sentinel_engine/live/machine_profile.py:92-105` — `load_profile()` reads the **gitignored** `scripts/live/machine_local.json`. **If the file is absent it silently returns Machine 1's defaults**: `D:\FOREX\MT5_Portable\terminal64.exe`, `portable=True`, login `2883015767`, marker `"mt5_portable"` (lines 50-55).
- Machine 2 requires the file to exist with: Capitaria path `C:\Program Files\Capitaria MT5 Terminal\terminal64.exe`, `portable=false`, `demo_login=2883016567` (module docstring lines 13-15; `scripts/live/machine_local.example.json`).
- Because the file is **untracked**, a fresh `git clone`, a `git clean -fdx`, or working from a second checkout silently loses it — and nothing warns: the defaults just quietly become Machine 1's.

### 2.2 The three gates

1. **PS watchdog** (`scripts/live/watchdog_local.ps1`, machine-2-only file):
   - Hardcodes its own identity **independently of `machine_local.json`**: `$Terminal` and `$DemoLogin = 2883016567` at lines 36-37. Two sources of truth that nothing cross-checks at runtime.
   - `Start-Terminal-IfNeeded` (lines 111-115) **launches** the terminal via `Start-Process` if no `terminal64` process exists. ⚠️ Note: this violates the Capa-4 ATTACH-ONLY rule; also, a terminal freshly launched at 07:00 may come up **not logged in** (no saved credentials) or with **AutoTrading OFF**.
   - `Test-DemoAccount` (lines 117-152) gates everything on a **bare `mt5.initialize()`** — no `path=`, no `portable=` — which attaches to whatever terminal the MetaTrader5 pip package resolves by default, not necessarily `$Terminal`. If the gate never passes, `Ensure-Supervisor` is **skipped forever** and the watchdog just logs `"Waiting for DEMO account confirmation..."` every cycle. All day. No crash.

2. **Supervisor** (`scripts/live/supervisor_live.py`):
   - Always launches the executor with `--arm --confirm-account <guard_cuenta.DEMO_LOGIN> --configs live` (lines 72-74). `DEMO_LOGIN` resolves **through the machine profile** — so an absent `machine_local.json` makes the supervisor pass Machine 1's login on machine 2.
   - **Preflight gate** (`wait_for_preflight`, lines 124-148): refuses to launch until `preflight_live.run_all_checks()` passes **7/7**: `portable-terminal-running` (marker match), `mt5-attach` (path+portable from profile), `account-guard` (`assert_demo`), `fresh-bars` (**real `copy_rates_from_pos` on XAUUSD with freshness threshold**), `roster-resolves`, `stop-file-absent`, `audit-log-writable` (preflight_live.py:183-328). Every FAIL is written with its named check and detail to `watchdog.log`, and preflight retries every 60 s forever.
   - When the executor exits, the supervisor logs `executor EXITED with code {rc} after {n}s uptime`, backs off (30 s → doubling → max), re-runs preflight, relaunches (lines 224-250). **A crash-looping executor therefore looks "alive" from the outside.**

3. **Executor** (`scripts/live/run_live_20.py`):
   - Attach check FIRST: `_portable_running(marker)` (lines 88-114) scans process command lines for the profile's marker substring. No match → prints `[STOP] The DEMO portable MT5 terminal is NOT running.` to **stderr** (→ `executor_console.log` since commit d360df4) → **exit code 3** (lines 579-585). MT5 is never touched.
   - `_connect` (lines 488-501): `mt5.initialize(path=…, portable=True)` only when profile says portable; standard installs must NOT pass `portable=True` (the code's own comment warns it "would detach from the logged-in session").
   - Per cycle (`run_cycle`, lines 445-486): re-assert guard → read STOP kill-switch (STOP present = **OPENs suppressed**, CLOSE/MODIFY still applied, loop continues) → for each config `reconcile_config` (lines 166-186): `fetch_bars` = `mt5.copy_rates_from_pos(symbol, TIMEFRAME_*, 0, window+1)` (line 126) → **empty/None ⇒ `logger.warning("[%s] no bars available (market closed / no data)")` and `continue`** — silent skip, forever (lines 173-175, 464-465) → else run sim → log `"[<ID>] bar=<ts> actions: <list|none>"` (467-468) → `execute_action` per action.
   - **Order send** (lines 403-439): only retcode **10016** (INVALID_STOPS) triggers retry+ERROR. **Every other retcode — including 10027 AutoTrading-disabled and 10018 market-closed — falls through to `logger.info("[SENT OPEN] … -> retcode=%s")` and returns.** A rejected order is logged at the same INFO level, same shape, as a filled one; only the number differs.
   - `symbol="XAUUSD"` is hardcoded once in `_SKELETON` (`sentinel_engine/strategies/live_configs_20.py:54`) and inherited by all 20 configs; **no `symbol_select()` and no symbol-existence check anywhere in the hot path** — a missing symbol degrades to "no bars available", never an error.
   - `dry_run = not args.arm` (line 566). The supervisor always passes `--arm`, so dry-run requires a rogue manually-started process.

### 2.3 Ground truth from machine 1's audit log (what "working" looks like)

From `scripts/live/run_live_20.audit.log` on this machine:

```
2026-07-14 01:03:36,125 INFO   [SENT OPEN] SS-M5 F1 magic=720041 -> retcode=10027   ← rejected: AutoTrading OFF (real precedent!)
2026-07-13 22:25:11,799 INFO [V15-M2] bar=2026-07-13T22:22:00+00:00 actions: none   ← sim ran, chose nothing
```
Marker frequency on a healthy multi-day log: `[NOOP]` 22 317 · `[SAME_BAR_EXIT_FALLBACK]` 1 728 · `[ALARM]` 33 · `[SL_CLAMPED]` 23. A healthy trading day contains hundreds of `[SENT …] -> retcode=10009` lines. **Machine 1 itself produced `retcode=10027` streaks on 2026-07-14 — AutoTrading-off is a demonstrated, real-world failure mode of this exact stack, not a hypothesis.**

Note: bar timestamps are printed `+00:00` but are **broker server time (UTC−4)**, per repo convention.

---

## 3. The failure worlds and their exact log signatures

| World | Meaning | Signature (grep target) | File |
|---|---|---|---|
| **W0a** | PS watchdog gate never passed → supervisor never started | `Waiting for DEMO account confirmation...` repeating; absence of `guard OK: DEMO login` | `watchdog_local.log` |
| **W0b** | Supervisor alive but preflight FAIL all day → executor never launched | `preflight FAIL -- refusing to (re)launch` + the named failing check (`portable-terminal-running`, `mt5-attach`, `account-guard`, `fresh-bars`, `stop-file-absent`…) | `watchdog.log` |
| **W0c** | Executor crash-looping (attach exit 3 / guard exit 2) under the supervisor | `executor EXITED with code 3` (or 2) repeating; `[STOP] The DEMO portable MT5 terminal is NOT running` | `watchdog.log` + `executor_console.log` |
| **WA** | Executor ran; **no data** → sim never executed | `no bars available (market closed / no data)` per config per cycle | `run_live_20.audit.log` |
| **WB** | Executor ran; sim ran; **zero intents** | 100% `actions: none`, zero `[SENT …]` all day | `run_live_20.audit.log` |
| **WC** | Intents generated; **sends rejected** | `[SENT OPEN] … -> retcode=` anything ≠ 10009/10010 (10027 = AutoTrading off; 10018 = market closed); or `OPEN FAILED`/`ALARM` | `run_live_20.audit.log` |
| **WD** | Dry-run process (not armed) | `DRY-RUN` anywhere; startup line `dry_run=True` | `run_live_20.audit.log` |

---

## 4. Ranked candidates (full detail)

### C1 — AutoTrading (Algo Trading) OFF in the attached terminal → every OPEN rejected 10027 — **HIGH**
- **Mechanism:** attach succeeds, guard passes (login+demo OK), bars fetch, sim generates OPENs, `order_send` returns `TRADE_RETCODE_CLIENT_DISABLES_AT` (10027). Only 10016 is retried/ERROR-logged (`run_live_20.py:430-434`); 10027 is logged `INFO [SENT OPEN] … -> retcode=10027` and dropped (435-437). **All 7 preflight checks pass with AutoTrading off** — preflight never touches `terminal_info().trade_allowed`. The system looks 100% healthy in every gate.
- **Why it fits perfectly:** runs all day, zero positions, zero crashes, zero ERROR lines (until/unless a MODIFY path trips), and the operator sees "everything green".
- **M1 vs M2:** AutoTrading is a per-terminal UI toggle a human must click; machine 1's long-lived portable terminal has it ON. Machine 2's terminal — *especially if `Start-Terminal-IfNeeded` relaunched it fresh at boot* — plausibly came up OFF. **Machine 1's own log shows 10027 happened there on 2026-07-14.**
- **Confirm:** on machine 2 — `Select-String '\[SENT OPEN\]' scripts\live\run_live_20.audit.log | Select-String -NotMatch 'retcode=1000[9|10]'`. Any `retcode=10027` = confirmed. Visual: is the "Algo Trading" toolbar button green in the terminal?

### C2 — Preflight FAIL all day: executor never launched — **HIGH** (umbrella; the log names the exact sub-cause)
- **Mechanism:** the supervisor loops `preflight → FAIL → sleep 60 s → retry` forever (`supervisor_live.py:124-148`). Sub-causes, each named in `watchdog.log`:
  - `portable-terminal-running` FAIL → marker mismatch (see C4) or terminal genuinely not running/not matching.
  - `mt5-attach` FAIL → wrong path / portable flag in profile.
  - `account-guard` FAIL → terminal open but **not logged in** (fresh launch, no saved credentials) or logged into an unexpected account.
  - `fresh-bars` FAIL → symbol missing / feed dead (see C5).
  - `stop-file-absent` FAIL → see C3.
- **Why it fits:** watchdog + supervisor stay alive; nothing crashes; nothing trades.
- **Confirm:** `Select-String 'preflight FAIL|preflight PASS|executor EXITED|launching executor' scripts\live\watchdog.log` — one command tells you if/when the executor ever launched on 2026-07-17 and, if not, exactly which named check failed.

### C3 — Leftover `STOP` kill-switch file — **HIGH** (trivial; check first)
- **Mechanism:** `PAUSAR_TRADING.bat` creates `scripts/live/STOP`. With STOP present: preflight `stop-file-absent` FAILs (blocks launch), and even a running executor suppresses all OPENs by design (`run_live_20.py:452-455`). The 2026-07-14 session also had an equity-floor mechanism that creates STOP automatically.
- **Why it fits:** everything runs, nothing opens, no errors — *by design*.
- **Confirm:** does `D:\FOREX\scripts\live\STOP` exist on machine 2? Also grep audit log for `KILL-SWITCH ACTIVE`.

### C4 — `machine_local.json` missing/stale → profile silently = Machine 1 → exit-3 loop — **MED-HIGH**
- **Mechanism:** file absent (fresh clone, `git clean`, new checkout — it's **gitignored**, git will never restore it) → marker defaults to `"mt5_portable"` → `_portable_running` never matches `…\Capitaria MT5 Terminal\…` → executor prints `[STOP] The DEMO portable MT5 terminal is NOT running.` and exits 3 → supervisor backs off and relaunches forever. Additionally `guard_cuenta.DEMO_LOGIN` becomes 2883015767, so even preflight's `account-guard` fails (terminal is logged into 2883016567). Variant: file present but `"portable": true` copied from the wrong example block → `initialize(path, portable=True)` on a standard install detaches from the logged-in session (warned in `run_live_20.py:491-496`) → `account_info()` None → guard exit 2 → same loop.
- **Why it fits:** the supervisor process is alive all day; each child dies instantly and quietly (stderr → `executor_console.log` only).
- **M1 vs M2:** machine 1 needs no file (defaults ARE machine 1); only machine 2 can break this way. Commit 1b43bb1 says the file existed on 2026-07-15 — but "el equipo actualizó vía Claude Code" on the 16th/17th; any re-clone/clean/worktree switch during that update deletes it.
- **Confirm:** does `scripts\live\machine_local.json` exist on machine 2, and does it contain exactly `"portable": false`, the Capitaria path, `"demo_login": 2883016567`? Then `Select-String 'EXITED with code' scripts\live\watchdog.log` and `Select-String 'NOT running' scripts\live\executor_console.log`.

### C5 — XAUUSD not resolvable / not in Market Watch → "no bars available" — **MED**
- **Mechanism:** `symbol="XAUUSD"` hardcoded (`live_configs_20.py:54`), no fallback, no `symbol_select()` anywhere in the executor. Symbol hidden/renamed ⇒ `copy_rates_from_pos` → None ⇒ `fetch_bars` → `[]` ⇒ WARNING + skip, per config, per cycle, forever. All 4 configs share the same symbol string, so all 4 die identically — matching the symptom exactly.
- **Downgraded from HIGH to MED** because preflight's `fresh-bars` check does a real `copy_rates_from_pos` on XAUUSD *before every executor launch* — a hard symbol failure should have blocked the launch and surfaced as C2/`fresh-bars` in `watchdog.log`. It remains possible if the feed passed at launch time and degraded later (Market Watch edit, symbol subscription lapse).
- **M1 vs M2:** both accounts are nominally on `Capitaria-All` (guard_cuenta.py:8-9, CUENTAS.md), lowering the odds of a ticker-suffix difference — but a fresh standard install's default Market Watch list can simply lack XAUUSD, while machine 1's veteran portable has it.
- **Confirm:** `Select-String 'no bars available' scripts\live\run_live_20.audit.log | Measure-Object`. Live check (Python on machine 2, read-only): `mt5.initialize(path=r"C:\Program Files\Capitaria MT5 Terminal\terminal64.exe"); mt5.symbol_info("XAUUSD")` → `None` or `.visible == False` confirms; also `[s.name for s in mt5.symbols_get() if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]`.

### C6 — PS watchdog gate stuck (bare `initialize()`, no-login terminal) — **MED**
- **Mechanism:** `Test-DemoAccount`'s inline python calls `mt5.initialize()` with **no arguments** (watchdog_local.ps1:125) — attaches to whatever the pip package's default terminal registration is, which may not be the Capitaria install; or the terminal launched at boot by `Start-Terminal-IfNeeded` never auto-logged-in → `account_info()` None / wrong login → gate returns not-ok → `Ensure-Supervisor` **skipped** every 20 s poll, all day.
- **Why it fits:** watchdog log fills quietly, no process ever crashes, nothing trades.
- **Confirm:** `Select-String 'Waiting for DEMO account|guard OK: DEMO login' scripts\live\watchdog_local.log` — if "Waiting…" dominates 07:00–17:00 and "guard OK" never appears, confirmed. Cross-check: `Get-Content scripts\live\watchdog.log -Tail 50` — if `watchdog.log` has no entries from 2026-07-17 at all, the supervisor never started.

### C7 — Sim legitimately generated zero entries (null hypothesis) — **LOW-MED**
- **Mechanism:** bars fine, sim runs, `actions: none` every bar (`run_live_20.py:467-468`). Legitimate if XAUUSD presented no entry conditions.
- **Why LOW:** on machine 1 the three M2 configs historically fire dozens of tickets within hours of arming (36 fichas in the first 50 minutes on 2026-07-15). Ten hours × 4 configs × zero signals is far outside that base rate. **Caveat:** machine 1 was OFF on 2026-07-17, so there is *no same-day control* — this must be falsified by log, then (if needed) by an offline replay of 2026-07-17 bars through the sim on machine 1.
- **Confirm:** count `actions: none` vs total `actions:` lines vs any `[SENT` lines for 2026-07-17 in machine 2's audit log. If WB is confirmed, run the bit-exact replay tooling on machine 1 over the same window to compute the *expected* entries.

### C8 — Rogue dry-run process — **LOW**
- **Mechanism:** a manually-started `python -m scripts.live.run_live_20` (no `--arm`) surviving instead of the supervised child ⇒ logs `[DRY-RUN would OPEN] …` instead of sending. The watchdog's orphan-reaping (`watchdog_local.ps1` `Ensure-Supervisor`) should prevent this *if* the watchdog was running.
- **Confirm:** `Select-String 'DRY-RUN|dry_run=True' scripts\live\run_live_20.audit.log` — any hit is a smoking gun. Startup lines `connected + guard OK: DEMO login … (dry_run=…)` list every process start with its arm state.

### C9 — `blocked_hours` server-time miscalibration — **LOW as root cause** (latent bug regardless)
- **Mechanism:** V11-M2 sets `blocked_hours=frozenset({0,6,16,18,23})` on **server hours** (`live_configs_20.py:131-133`); `emasar_variant.py` evaluates `datetime.fromtimestamp(bar["t"], tz=utc).hour` — which relabels the broker's server-time epoch as UTC (docstring wrongly says "UTC"). If machine 2's server offset differed, blocked hours shift.
- **Why LOW:** affects only V11-M2 (the other 3 configs don't set it), and 5 blocked hours cannot zero a 10-hour window. Both logins are on the same `Capitaria-All` server, so an offset difference is unlikely. Fix the mislabel regardless.
- **Confirm:** on machine 2 compare `mt5.symbol_info_tick("XAUUSD").time` (as naive UTC) with real UTC now → the offset should be −4 h, same as machine 1.

### Ruled out (code inspection)
- **Data-lake/tiers dependency:** the live executor imports no lake/parquet module; data source is `copy_rates_from_pos` only (`run_live_20.py:28,120-133`).
- **M2 timeframe resampling:** `mt5.TIMEFRAME_M2` is a native MT5 constant used directly (line 125); no resampling exists in the live path.
- **Roster mis-resolution:** `--configs live` filters `CONFIGS_20` by `LIVE_ROSTER` in a shared tracked file (`run_live_20.py:557-558`; `live_configs_20.py:157-159`), identical on both machines; import failure would crash at startup and `roster-resolves` would FAIL preflight loudly.

---

## 5. Evidence-collection kit for machine 2 (copy-paste, read-only)

Run in PowerShell from `D:\FOREX` (or wherever the repo lives) on machine 2, and send back the full output:

```powershell
# --- 0. Quick states -------------------------------------------------------
Test-Path scripts\live\STOP                                    # C3
Test-Path scripts\live\machine_local.json                      # C4
Get-Content scripts\live\machine_local.json -ErrorAction SilentlyContinue   # C4 (portable? login? path?)
git log --oneline -3; git status -s                            # same code as machine 1?

# --- 1. Did the supervisor ever launch the executor on 2026-07-17? ---------
Select-String 'preflight PASS|preflight FAIL|launching executor|EXITED with code' `
  scripts\live\watchdog.log | Select-Object -Last 60           # C2 / C4 (which check failed, exit codes)

# --- 2. Did the PS watchdog gate ever pass? --------------------------------
Select-String 'guard OK: DEMO login|Waiting for DEMO account' `
  scripts\live\watchdog_local.log | Select-Object -Last 40     # C6

# --- 3. Classify the executor's day (THE decisive query) -------------------
Select-String 'no bars available' scripts\live\run_live_20.audit.log | Measure-Object          # World A → C5
Select-String 'actions: none'    scripts\live\run_live_20.audit.log | Measure-Object          # World B → C7
Select-String '\[SENT (OPEN|CLOSE|MODIFY)\]|OPEN FAILED|ALARM' scripts\live\run_live_20.audit.log `
  | Select-Object -Last 40                                                                     # World C → C1 (read the retcodes!)
Select-String 'DRY-RUN|dry_run=True' scripts\live\run_live_20.audit.log | Select-Object -Last 10   # World D → C8
Select-String 'connected \+ guard OK|KILL-SWITCH' scripts\live\run_live_20.audit.log | Select-Object -Last 10
Select-String 'NOT running' scripts\live\executor_console.log -ErrorAction SilentlyContinue `
  | Select-Object -Last 5                                       # C4 exit-3 signature

# --- 4. Terminal-side live checks (only if 1-3 are inconclusive) -----------
python - <<'PY'
import MetaTrader5 as mt5, datetime
ok = mt5.initialize(path=r"C:\Program Files\Capitaria MT5 Terminal\terminal64.exe")
print("init:", ok, mt5.last_error())
ti = mt5.terminal_info();  ai = mt5.account_info()
print("trade_allowed(AutoTrading):", getattr(ti, "trade_allowed", None))    # C1 ← the big one
print("login:", getattr(ai, "login", None), "trade_mode:", getattr(ai, "trade_mode", None))
si = mt5.symbol_info("XAUUSD")
print("XAUUSD info:", None if si is None else f"visible={si.visible}")      # C5
r = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M2, 0, 5)
print("M2 bars:", None if r is None else len(r))
t = mt5.symbol_info_tick("XAUUSD")
if t: print("server-vs-UTC offset (h):",
            (datetime.datetime.utcfromtimestamp(t.time) - datetime.datetime.utcnow()).total_seconds()/3600)  # C9
mt5.shutdown()
PY
```

### Decision matrix (evidence → verdict → fix)

| Evidence found | Verdict | Fix |
|---|---|---|
| `[SENT OPEN] … retcode=10027` | **C1** | Click the **Algo Trading** button ON in the terminal; re-verify next fill = 10009 |
| `preflight FAIL … stop-file-absent` or `STOP` exists | **C3** | Run `REANUDAR_TRADING.bat` (deletes STOP) — after confirming pausing wasn't intentional |
| `preflight FAIL … account-guard` / `mt5-attach` / `portable-terminal-running` | **C2/C4** | Recreate `machine_local.json` from the example's TOMACHINE block (`portable:false`, Capitaria path, login 2883016567); log the terminal in by hand |
| `executor EXITED with code 3` loop + `[STOP] … NOT running` | **C4** | Same as above — the profile is resolving Machine 1 defaults |
| `no bars available` dominating | **C5** | Add XAUUSD to Market Watch by hand (right-click → Symbols); confirm `copy_rates` returns bars |
| `Waiting for DEMO account…` all day, `watchdog.log` empty on the 17th | **C6** | Log the terminal in by hand; then fix `Test-DemoAccount` to pass `path=$Terminal` |
| 100% `actions: none`, zero `[SENT`, no warnings | **C7** | Escalate: run the bit-exact replay of 2026-07-17 on machine 1 to compute expected entries before touching anything |
| Any `DRY-RUN` line | **C8** | Kill the rogue process; relaunch only via the watchdog/supervisor path |

---

## 6. Latent defects found during this investigation (worth fixing regardless of the root cause)

These are **not** authorized for implementation yet — listed for decision:

1. **Reject retcodes masquerade as success** (`run_live_20.py:428-437`): any retcode other than 10016 — including 10027/10018 — is logged `INFO [SENT OPEN] … -> retcode=N` and dropped. Should be: treat non-10009/10010 as ERROR + `[ALARM]`, and have the supervisor's stall-alarm (or the watcher) count consecutive rejects. This single fix would have converted yesterday's silent day into a loud one *if* C1 is the cause.
2. **No symbol validation**: one `symbol_info()/symbol_select()` assertion at executor startup (and in preflight, explicitly reporting `visible=False` as its own failure) would turn C5 from a per-cycle WARNING into a launch-blocking, named error.
3. **Two uncoordinated identity systems on machine 2**: `machine_local.json` (used by python) vs `watchdog_local.ps1`'s `$Terminal`/`$DemoLogin` literals and bare `mt5.initialize()`. The PS watchdog should read `machine_local.json` too (single source of truth) and pass `path=` on initialize.
4. **`machine_local.json` absence is silent**: on a machine whose hostname ≠ machine 1's, silently defaulting to Machine 1's profile is a trap. Cheap hardening: log the resolved profile at executor startup at WARNING when defaults are used (`profile: DEFAULTS (machine 1)` vs `profile: machine_local.json`), and make preflight print the resolved login/path/marker in its PASS line (it already prints path+portable in `mt5-attach`).
5. **`Start-Terminal-IfNeeded` launches MT5** (`watchdog_local.ps1:111-115`) — violates the ATTACH-ONLY Capa-4 rule that exists precisely to guarantee a human verified the right account/session. Recommend removal or an explicit user-authorized exception like D89.
6. **`blocked_hours` mislabeled "UTC"** in `emasar_variant.py` while actually operating on broker server-hours; the config comment (`live_configs_20.py:133`) is correct. Fix the docstring/comment to prevent future miscalibration.
7. **No AutoTrading check in preflight**: add `terminal_info().trade_allowed` as an 8th preflight check — it is the one terminal state that passes all current checks yet guarantees zero fills.

---

## 7. What we could NOT verify from here

- Anything on machine 2's disk: presence/contents of `machine_local.json`, `STOP`, its three logs, its git HEAD. The kit in §5 covers all of it.
- Whether machine 2's terminal was logged in, AutoTrading state, Market Watch contents on 2026-07-17.
- Machine 2's actual launch method that morning (`INICIAR_SENTINEL_LIVE_LOCAL.bat` → watchdog → supervisor, vs. anything manual).
- Same-day behavior of machine 1 (it was powered off on 2026-07-17) — so "the market simply gave no signals" (C7), while unlikely, cannot be excluded a priori; the §5 grep settles it.

---

*Report by: Claude orchestrator + 2 Sonnet 5 (high effort) read-only investigators (launch/order path; signal/data path). All file:line claims re-verified by the orchestrator against branch `alvaro` @ 7f5f8da. Ground truth extracted from machine 1's `run_live_20.audit.log`.*
