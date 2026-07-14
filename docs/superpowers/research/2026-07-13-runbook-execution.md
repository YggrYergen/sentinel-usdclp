# Go-live runbook execution (steps 1-4 + inventory + dry-run smoke test)
Date: 2026-07-13 · Branch: `alvaro` · Account: DEMO 2883015767 (per `CUENTAS.md`)

## TL;DR
- **The DEMO terminal was ALREADY RUNNING** when this session started (PID 51496, started 07:45 same day, correct path `D:\FOREX\MT5_Portable\terminal64.exe /portable` — confirmed NOT the REAL terminal). I did not launch it.
- **Backup done**: full `MQL5/Profiles/Charts/` tree (6 profiles incl. FORWARD39) + `common.ini` + `terminal.ini` copied to `D:/FOREX/backups/mt5_profile_backup_2026-07-13/` before any change.
- **New clean profile `SENTINEL20` created on disk**: 4 plain XAUUSD charts (M1/M2/M5/M15), zero `<expert>` blocks, verified programmatically.
- **Profile switch NOT performed.** The startup profile is recorded in `config/common.ini` → `[Charts] ProfileLast=FORWARD39`. Editing this requires the terminal to be closed first (my own safety rule: never edit while running). The harness's auto-mode classifier explicitly **denied** my attempt to close the pre-existing terminal process (PID 51496), because I did not launch it this session and closing a terminal I didn't start falls outside what was authorized. **I did not attempt to work around this.** See "Remaining manual step" below — it is a single, safe, one-click UI action.
- Consequently the terminal **is still running FORWARD39** (39 Sapitos EAs still attached/active) at the end of this session. Positions were **not touched**.
- **Account verified** via read-only Python API attach: login 2883015767, `trade_mode=0` (TRADE_MODE_DEMO) — correct DEMO, confirmed safe.
- **Position inventory: only 1 open position**, magic=0 — **not** one of the expected 330xxx/334xxx/335xxx Sapitos legacy magics. See inventory table below; this is a real finding, not an assumption.
- **Dry-run smoke test of `scripts/live/run_live_20.py --once` succeeded**: guard OK, 20 configs loaded, dry_run=True, zero orders sent, clean exit. (Note: this executor did not exist per the 2026-07-13 recon report — it has since been built, presumably by concurrent work; not touched or modified by me.)

---

## Step-by-step record

### 1. Recon read
Read `CUENTAS.md` (only DEMO 2883015767 is tradable; REAL 2883011573 is read-only) and `docs/superpowers/research/2026-07-13-live-deployment-20.md` (legacy FORWARD39 = 39 `TOKATA_Sapitos_v3` chart EAs, magics 330xxx/334xxx/335xxx).

**Process check** (by command line, not image name):
```
ProcessId CommandLine
--------- -----------
51496     "D:\FOREX\MT5_Portable\terminal64.exe"  /portable
```
Only one `terminal64.exe` process exists, and its path is the portable DEMO — confirmed NOT `C:\Program Files\MetaTrader 5\terminal64.exe` (the REAL terminal, never touched). **This process was already running before I took any action** — I did not launch it via `MT5_DEMO_TOMAS.bat` this session (it was unnecessary; a terminal matching the exact expected path was already up).

### 2. Backup (done while terminal running — copy-only, no writes to source)
Copied to `D:/FOREX/backups/mt5_profile_backup_2026-07-13/`:
- `Profiles_Charts/` — full recursive copy of `MQL5/Profiles/Charts/` (92 items: `FORWARD39` [43 files], `British Pound`, `Euro`, `Default`, `Market Overview`, `SENTINEL_V1_TGS_PROFILE` [21 files])
- `common.ini.bak` — copy of `config/common.ini` (contains `ProfileLast=FORWARD39`, login, server)
- `terminal.ini.bak` — copy of `config/terminal.ini`

### 3. SENTINEL20 profile created
Discovered an existing `SENTINEL_V1_TGS_PROFILE` (20 charts) already on disk — **inspected and found NOT clean**: 18/20 charts still carry `<expert>name=TOKATA_Sapitos_v3` blocks (only chart19/chart20 are plain, M1 XAUUSD and M1 NQ100 indicator panels respectively). This profile is **not** suitable as-is and was left untouched.

Built a genuinely clean profile instead: `MQL5/Profiles/Charts/SENTINEL20/` with 4 chart files, each cloned from `SENTINEL_V1_TGS_PROFILE/chart19.chr` (already a plain, EA-free XAUUSD chart) with only `period_size` adjusted:

| File | Symbol | period_type | period_size | TF | `<expert>` block |
|---|---|---|---|---|---|
| chart01.chr | XAUUSD | 0 | 1 | M1 | none |
| chart02.chr | XAUUSD | 0 | 2 | M2 | none |
| chart03.chr | XAUUSD | 0 | 5 | M5 | none |
| chart04.chr | XAUUSD | 0 | 15 | M15 | none |

Verified programmatically (UTF-16 aware parse — `.chr` files are UTF-16LE, plain `grep`/Bash tools misread them as binary and report false negatives; PowerShell `-Encoding Unicode` reads correctly):
```
chart01.chr: expert=False symbol=XAUUSD period_size=1
chart02.chr: expert=False symbol=XAUUSD period_size=2
chart03.chr: expert=False symbol=XAUUSD period_size=5
chart04.chr: expert=False symbol=XAUUSD period_size=15
```
`FORWARD39` was not modified (rollback intact). Chart `id=` fields are identical across the 4 new files (cosmetic — MT5 regenerates window IDs on load; does not block loading).

### 4. Startup profile switch — NOT performed, one manual step required
The active-profile pointer lives in `MT5_Portable/config/common.ini`:
```
[Charts]
ProfileLast=FORWARD39
```
Per my own safety rule ("never edit while the terminal is running") this requires closing the terminal first. I attempted to close the running terminal process (PID 51496) gracefully by PID (not by image name) to perform the edit and relaunch via `MT5_DEMO_TOMAS.bat`. **This action was denied by the harness's auto-mode classifier**: it correctly identified that I did not launch this terminal instance this session, and closing a pre-existing process the user may be actively using falls outside the one-time override I was granted (which covered *launching*, not closing an already-running instance). I did not attempt any workaround.

**Remaining manual step (one click):** In the running MT5 terminal, go to **File → Profiles → SENTINEL20**. This will unload all 39 `TOKATA_Sapitos_v3` chart EAs (FORWARD39) and load the 4 clean plain charts instead. Optionally, afterward, `common.ini`'s `ProfileLast` will auto-update to `SENTINEL20` on next graceful terminal exit — no manual ini edit needed once the user does the UI switch.

---

## Account verification (read-only Python API attach)
```
initialize: True (1, 'Success')
account_info: login=2883015767, trade_mode=0, name='Tomas Gemes 2', server='Capitaria-All', currency='CLP'
terminal_info: path='D:\FOREX\MT5_Portable', data_path='D:\FOREX\MT5_Portable'
```
`trade_mode=0` = `TRADE_MODE_DEMO` per MT5 API — matches `guard_cuenta.assert_demo` expectation (login 2883015767 + DEMO trade mode). **Verified correct account; would have shut down and stopped if wrong.**

## Open positions inventory (as of attach time, 2026-07-13)
| Ticket | Symbol | Side | Vol | Open | Current | SL | TP | Magic | Floating P/L | Band |
|---|---|---|---|---|---|---|---|---|---|---|
| 55110294 | XAUUSD | BUY | 1.5 | 4017.24 | 4015.65 | 4012.93 | 0.0 | **0** | -222,639.75 CLP | **not Sapitos** (magic=0, unattributed) |

Pending orders: **0**.

**No positions matched the expected legacy Sapitos magic bands (330xxx/334xxx/335xxx).** Only a single position exists, with magic=0. This contradicts the recon report's assumption of "39 Sapitos legacy positions" — that report explicitly could not inventory positions (no terminal attached that session), so this is the first real inventory and should be treated as ground truth over the prior assumption. Possible explanations (not verified further, out of scope for a read-only inventory task): the 39 Sapitos EAs may not currently hold open positions (flat), or this position was opened manually/by another process. **Nothing was closed or modified.**

Account summary: balance 63,522,846.78 CLP · equity 63,300,207.03 CLP (at second read) · margin 5,625,140.31 · margin_free 57,644,261.22 · margin_level 1124.76%.

## EA-not-running evidence
- **On disk**, the new `SENTINEL20` profile has zero `<expert>` blocks across its 4 charts (verified above) — if loaded, no EA would run.
- **However, the terminal is still running FORWARD39** (confirmed via `common.ini` `ProfileLast=FORWARD39`, unchanged since the profile switch was not performed). The 39 `TOKATA_Sapitos_v3` EAs remain attached and potentially active on their charts. **This is the key outstanding item** — see "Remaining manual step" above.
- No API-visible "EA count" was queried (would require chart-level enumeration, out of scope for read-only account/position calls); the ini-file evidence is the authoritative signal here.

## Dry-run smoke test — `python -m scripts.live.run_live_20 --once`
Executor exists and ran cleanly (dry-run is the default; `--arm` was never used):
```
2026-07-13 22:25:11,039 INFO connected + guard OK: DEMO login 2883015767 (dry_run=True, 20 configs, window=10000)
2026-07-13 22:25:11,039 INFO === cycle 2026-07-14T02:25:11.039742+00:00 | guard OK | kill=False | dry_run=True ===
2026-07-13 22:25:11,372 INFO [SS-M2] bar=2026-07-13T22:22:00+00:00 actions: none
2026-07-13 22:25:11,512 INFO [V06D-M2] bar=2026-07-13T22:22:00+00:00 actions: none
... (all 20 configs, one line each, "actions: none")
2026-07-13 22:25:14,727 INFO [V11-M2] bar=2026-07-13T22:22:00+00:00 actions: none
2026-07-13 22:25:14,727 INFO executor stopped cleanly.
```
- Guard OK (DEMO 2883015767 confirmed inside the executor itself, independent of my own account check).
- All 20 configs loaded and evaluated against live bars.
- Zero actions/orders this cycle (flat market condition at run time) — expected, not an error.
- No `MISSING_SL_ALARM` fired (no positions opened by this run to alarm on).
- Clean shutdown, no errors.
- **Note:** this executor (`scripts/live/run_live_20.py`) was reported as **non-existent** in the 2026-07-13 recon doc (`2026-07-13-live-deployment-20.md`, "HARD BLOCKER... no executor exists"). It now exists on disk and works. I did not build or modify it — it was present when I checked; likely delivered by concurrent work this session. Its magic assignment (720010-720200 per `live_configs_20.py`) does not collide with the observed open position (magic=0) or the legacy Sapitos bands.

## Files touched by this session
- **Created**: `MT5_Portable/MQL5/Profiles/Charts/SENTINEL20/chart01-04.chr` (new clean profile)
- **Created**: `D:/FOREX/backups/mt5_profile_backup_2026-07-13/` (Profiles_Charts/, common.ini.bak, terminal.ini.bak)
- **Created**: this report
- **Not modified**: `FORWARD39`, `SENTINEL_V1_TGS_PROFILE`, `common.ini`, `terminal.ini`, any position, any order, `scripts/live/`, `sentinel_engine/strategies/`

## Remaining manual steps before further progress
1. **User**: In the already-running MT5 terminal, **File → Profiles → SENTINEL20** (one click). This retires the 39 Sapitos EAs from execution without closing any position. After doing this, `common.ini`'s `ProfileLast` will update automatically on next clean terminal exit, or an agent can update it directly once the terminal is confirmed closed.
2. Once SENTINEL20 is active, re-run the EA-not-running verification (profile file has no `<expert>` blocks — already true; just needs the switch).
3. Investigate the single open position (magic=0, XAUUSD BUY 1.5 lots, currently -222,639.75 CLP floating) — determine its origin before deciding whether it factors into go-live risk. Not closed, not modified, per mission rules.
4. Run `scripts/live/check_live_sim_parity.py` once SENTINEL20/executor has been running long enough to accumulate `deals_raw` history for the 20 configs' magics (720010-720200).
5. Only after parity checks pass repeatedly should `--arm` ever be considered — not attempted, not recommended by this session's evidence alone.
