<#
  scripts\live\setup_autostart_machine1.ps1

  MACHINE-1 ONLY always-on setup (SENTINEL, 2026-07-22). Idempotently brings
  machine 1's live stack up as a durable, self-healing service so the deals
  watcher / bars ingester / supervisor / dashboard survive reboots and logons
  without a human babysitting a console window. It does this by:

    1. Registering a Task Scheduler task (SENTINEL_Watchdog_Machine1) that runs
       scripts\live\watchdog_local.ps1 hidden at user logon, restarting on
       failure. The watchdog is the self-healer: it keeps terminal + watcher +
       bars ingester + supervisor + dashboard alive.
    2. Setting never-sleep AC power settings (a sleeping machine stops trading).
    3. Persistently setting machine-1's env vars via setx:
         SUPERVISOR_CONFIGS       = local   (S6/S7/SuperTrend @0.1 + TK-Momentum @0.01)
         SUPERVISOR_MAX_SPREAD_OPEN = 0.5   (open only at XAUUSD's 0.5 min spread)
       (Machine-1 may additionally opt into SUPERVISOR_STALE_AUTORESTART=1 to
        auto-recycle a stale executor -- left OUT here by default; add it by
        hand if desired. It is OFF unless explicitly set, so this script's
        omission keeps the byte-identical alarm-only default.)

  SAFETY -- MACHINE-1 LOCKOUT: this script REFUSES to run on any other machine.
  If scripts\live\machine_local.json exists and its demo_login is not machine
  1's sanctioned login 2883015767, the script exits 1 with a clear message. It
  NEVER arms trading, NEVER places an order, and NEVER launches an MT5 terminal
  itself (see the summary -- the WATCHDOG may start the terminal; this setup
  script does not).

  Windows PowerShell 5.1 compatible: NO '&&'/'||', no ternary, no null-
  coalescing. Paths are derived from this script's own location -- NO hardcoded
  D:\FOREX, so it cannot accidentally point machine 2 at the wrong tree (and
  the login guard above stops it running there at all anyway).

  USAGE (run from an ELEVATED PowerShell for power settings + machine-scope
  scheduled task):
      powershell -NoProfile -ExecutionPolicy Bypass -File scripts\live\setup_autostart_machine1.ps1
  Switches:
      -SkipEnv     : do NOT set the SUPERVISOR_* env vars (leave as-is).
      -EnvOnly     : ONLY set the env vars; skip task registration + power.
      -WhatIf-ish  : this script has no destructive side effects beyond
                     Register-ScheduledTask / setx / powercfg; review before running.
#>
[CmdletBinding()]
param(
    [switch]$SkipEnv,
    [switch]$EnvOnly
)

$ErrorActionPreference = "Stop"

# --------------------------------------------------------------------------
# Derive repo root from THIS script's location (never hardcode D:\FOREX).
# scripts\live\setup_autostart_machine1.ps1 -> repo root is two levels up.
# --------------------------------------------------------------------------
$ScriptDir = $PSScriptRoot
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$LiveDir   = Join-Path $RepoRoot "scripts\live"
$WatchdogPs1 = Join-Path $LiveDir "watchdog_local.ps1"
$MachineLocalJson = Join-Path $LiveDir "machine_local.json"

$MACHINE1_LOGIN = 2883015767
$TaskName = "SENTINEL_Watchdog_Machine1"
$PortableTerminal = Join-Path $RepoRoot "MT5_Portable\terminal64.exe"

function Write-Section {
    param([string]$Msg)
    Write-Output ""
    Write-Output "==== $Msg ===="
}

# --------------------------------------------------------------------------
# MACHINE-1 LOCKOUT GUARD: refuse to run anywhere but machine 1.
# If machine_local.json is present and names a login other than 2883015767,
# this is NOT machine 1 -- exit 1 loudly. (Absent file = machine-1 defaults,
# which is allowed.)
# --------------------------------------------------------------------------
function Assert-Machine1 {
    if (-not (Test-Path $MachineLocalJson)) {
        Write-Output "machine_local.json absent -> machine-1 defaults (login $MACHINE1_LOGIN). OK."
        return
    }
    try {
        $raw = Get-Content -Raw -Path $MachineLocalJson -Encoding UTF8
        $cfg = $raw | ConvertFrom-Json
    } catch {
        Write-Output "ERROR: could not parse $MachineLocalJson : $($_.Exception.Message)"
        exit 1
    }
    $login = $cfg.demo_login
    if ($null -eq $login) {
        Write-Output "ERROR: $MachineLocalJson has no demo_login -- refusing to run (cannot confirm this is machine 1)."
        exit 1
    }
    if ([int64]$login -ne $MACHINE1_LOGIN) {
        Write-Output "REFUSING TO RUN: machine_local.json demo_login=$login is NOT machine-1's login $MACHINE1_LOGIN."
        Write-Output "This setup script is MACHINE-1 ONLY. Do not run it on machine 2 (login 2883016567)."
        exit 1
    }
    Write-Output "machine_local.json demo_login=$login == machine-1 login $MACHINE1_LOGIN. OK."
}

# --------------------------------------------------------------------------
# Env vars (machine-1 roster + static spread cap). Persistent via setx (USER
# scope so no elevation strictly required for this part).
# --------------------------------------------------------------------------
function Set-Machine1Env {
    Write-Section "Persistent env vars (setx, USER scope)"
    # SUPERVISOR_CONFIGS=local : the machine-1 LOCAL roster.
    # SUPERVISOR_MAX_SPREAD_OPEN=0.5 : open only at XAUUSD's observed 0.5 min spread.
    setx SUPERVISOR_CONFIGS "local"
    setx SUPERVISOR_MAX_SPREAD_OPEN "0.5"
    Write-Output "set SUPERVISOR_CONFIGS=local"
    Write-Output "set SUPERVISOR_MAX_SPREAD_OPEN=0.5"
    Write-Output "NOTE: setx affects NEW processes only. Restart the watchdog/"
    Write-Output "      supervisor (or log off/on) for these to take effect."
    Write-Output "NOTE: SUPERVISOR_STALE_AUTORESTART is intentionally NOT set here."
    Write-Output "      Set it to 1 by hand if you want stale-executor auto-recycle."
}

# --------------------------------------------------------------------------
# Never-sleep AC power settings (a sleeping box stops trading). AC only;
# battery settings untouched. monitor-timeout left ALONE deliberately -- the
# screen turning off is harmless and saves the panel; only standby/hibernate
# would halt the CPU and must be disabled.
# --------------------------------------------------------------------------
function Set-NeverSleep {
    Write-Section "Never-sleep AC power settings (powercfg)"
    powercfg /change standby-timeout-ac 0
    powercfg /change hibernate-timeout-ac 0
    # monitor-timeout-ac left alone on purpose (screen off is fine; comment above).
    Write-Output "standby-timeout-ac=0, hibernate-timeout-ac=0 (monitor left alone)."
}

# --------------------------------------------------------------------------
# Register (idempotently) the logon watchdog task. Unregister-then-register so
# a re-run always reflects the current action/paths. Hidden window, working dir
# = repo root, restart on failure.
# --------------------------------------------------------------------------
function Register-WatchdogTask {
    Write-Section "Task Scheduler: $TaskName"
    if (-not (Test-Path $WatchdogPs1)) {
        Write-Output "ERROR: watchdog not found at $WatchdogPs1 -- cannot register task."
        exit 1
    }

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
        Write-Output "existing task found -- unregistering before re-registering (idempotent)."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $psExe = (Get-Command powershell.exe).Source
    $argList = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WatchdogPs1`""
    $action = New-ScheduledTaskAction -Execute $psExe -Argument $argList -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
    # Run as the current interactive user (the watchdog needs the desktop
    # session to see/start terminal64.exe). Highest privileges for powercfg-like
    # needs the watchdog may have.
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Output "registered task '$TaskName' (runs $WatchdogPs1 hidden at logon, restart-on-failure)."
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
Write-Section "SENTINEL machine-1 autostart setup"
Write-Output "RepoRoot: $RepoRoot"

Assert-Machine1

if ($EnvOnly) {
    if ($SkipEnv) {
        Write-Output "ERROR: -EnvOnly and -SkipEnv are mutually exclusive."
        exit 1
    }
    Set-Machine1Env
} else {
    if (-not $SkipEnv) {
        Set-Machine1Env
    } else {
        Write-Output "-SkipEnv: leaving SUPERVISOR_* env vars unchanged."
    }
    Set-NeverSleep
    Register-WatchdogTask
}

# --------------------------------------------------------------------------
# Final summary: what was done + what the OPERATOR must still do by hand.
# --------------------------------------------------------------------------
Write-Section "SUMMARY"
Write-Output "DONE (this run):"
if (-not $SkipEnv) {
    Write-Output "  - env: SUPERVISOR_CONFIGS=local, SUPERVISOR_MAX_SPREAD_OPEN=0.5 (setx, USER scope)."
}
if (-not $EnvOnly) {
    Write-Output "  - power: standby/hibernate on AC disabled (powercfg)."
    Write-Output "  - task: '$TaskName' registered (watchdog runs hidden at logon)."
}
Write-Output ""
Write-Output "STILL TO DO BY HAND (operator):"
Write-Output "  1. Open the portable MT5 terminal ONCE and log into DEMO ${MACHINE1_LOGIN}:"
Write-Output "         $PortableTerminal"
Write-Output "     ACCURACY NOTE: watchdog_local.ps1's Start-Terminal-IfNeeded (~line 157-161)"
Write-Output "     WILL itself Start-Process the terminal if it is not running -- so strictly"
Write-Output "     the watchdog can launch it. But you should open+log-in ONCE by hand first so"
Write-Output "     the DEMO account/session is established; the python stack stays attach-only"
Write-Output "     and refuses to arm until account_info() confirms DEMO $MACHINE1_LOGIN."
Write-Output "  2. If env vars were set this run, RESTART the watchdog task (or log off/on) so"
Write-Output "     new processes inherit SUPERVISOR_CONFIGS/SUPERVISOR_MAX_SPREAD_OPEN:"
Write-Output "         Stop-ScheduledTask -TaskName $TaskName ; Start-ScheduledTask -TaskName $TaskName"
Write-Output "  3. (Optional) To arm stale-executor auto-recycle on machine 1:"
Write-Output "         setx SUPERVISOR_STALE_AUTORESTART 1   (then restart the task)"
Write-Output "  4. Verify: the dashboard should come up on http://127.0.0.1:8501 (watchdog's"
Write-Output "     Ensure-Dashboard relaunches run_service.py when nothing listens on 8501)."
Write-Output "  5. Confirm nothing is armed unexpectedly: this script NEVER arms trading; the"
Write-Output "     supervisor only arms the DEMO login via its own preflight gate."
Write-Output ""
Write-Output "OK."
