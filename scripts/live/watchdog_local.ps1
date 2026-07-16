<#
  scripts\live\watchdog_local.ps1

  Self-healing process watchdog for THIS machine (login 2883016567,
  Capitaria-All DEMO). Modeled on the teammate's INICIAR_TRADING_LIVE.bat
  (D:\FOREX, login 2883015767) but adapted fully:
    - detects components by full command-line match (Win32_Process),
      not just PID files -- PID files are refreshed on relaunch for
      operator convenience/inspection, never trusted alone;
    - pre-checks the standard (non-portable) Capitaria MT5 terminal is
      running AND that mt5.account_info() confirms login 2883016567 +
      trade_mode DEMO (0) before relaunching anything;
    - may itself START terminal64.exe if not running (this is the user's
      own watchdog, not an unrelated tool -- attach-only rule is preserved
      for the python scripts, which never start until the account check
      passes);
    - keeps the CANONICAL supervisor (scripts.live.supervisor_live) alive,
      NOT run_live_20 directly -- the supervisor owns the armed executor
      (preflight gate + backoff + staleness alarm). This avoids duplicate
      armed executors / double orders;
    - honors scripts\live\STOP indirectly: the supervisor's own preflight
      refuses to arm while STOP exists, so the watchdog keeps the supervisor
      process alive regardless and lets it manage the pause;
    - refuses to run twice (lockfile + cmdline self-check).

  Log: scripts\live\watchdog_local.log (append-only, ~5MB rotation cap).
#>

$ErrorActionPreference = "Stop"

$RepoRoot   = (Resolve-Path "$PSScriptRoot\..\..").Path
$LiveDir    = Join-Path $RepoRoot "scripts\live"
$LogFile    = Join-Path $LiveDir "watchdog_local.log"
$LockFile   = Join-Path $LiveDir "watchdog_local.lock"
$StopFile   = Join-Path $LiveDir "STOP"
$Terminal   = "C:\Program Files\Capitaria MT5 Terminal\terminal64.exe"
$DemoLogin  = [int64]2883016567
$PollSec    = 20
$MaxLogBytes = 5MB

$WatcherPidFile  = Join-Path $LiveDir "deals_watcher.pid"
$SupervisorPidFile = Join-Path $LiveDir "supervisor.pid"
$DashboardPidFile = Join-Path $LiveDir "run_service.pid"

$WatcherLog  = Join-Path $LiveDir "deals_watcher_local.log"
$SupervisorLog = Join-Path $LiveDir "supervisor_local.log"
$DashboardLog = Join-Path $LiveDir "run_service_local.log"

function Write-Log {
    param([string]$Msg)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Msg"
    if (Test-Path $LogFile) {
        $len = (Get-Item $LogFile).Length
        if ($len -gt $MaxLogBytes) {
            $bak = "$LogFile.1"
            if (Test-Path $bak) { Remove-Item $bak -Force }
            Rename-Item $LogFile $bak -Force
        }
    }
    Add-Content -Path $LogFile -Value $line
    Write-Output $line
}

function Acquire-Singleton {
    # Cmdline self-check: any OTHER powershell process already running
    # this same script (besides us) means refuse to start.
    $myPid = $PID
    $others = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match 'powershell' -and $_.CommandLine -match 'watchdog_local\.ps1' -and $_.ProcessId -ne $myPid
    }
    if ($others) {
        Write-Log "REFUSING TO START: another watchdog_local.ps1 instance already running (PID $($others[0].ProcessId))."
        exit 1
    }
    # Lockfile as a second guard (covers races / stale cmdline matches).
    if (Test-Path $LockFile) {
        $lockPid = (Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        $alive = $false
        if ($lockPid) {
            $alive = [bool](Get-Process -Id $lockPid -ErrorAction SilentlyContinue)
        }
        if ($alive) {
            Write-Log "REFUSING TO START: lockfile $LockFile points at live PID $lockPid."
            exit 1
        } else {
            Write-Log "Stale lockfile found (PID $lockPid not alive) -- taking over."
        }
    }
    Set-Content -Path $LockFile -Value $myPid
}

function Release-Singleton {
    if (Test-Path $LockFile) {
        $lockPid = (Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($lockPid -eq $PID) { Remove-Item $LockFile -Force -ErrorAction SilentlyContinue }
    }
}

function Find-ProcByCmdline {
    param([string]$Pattern)
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(\.exe)?$' -and $_.CommandLine -match $Pattern
    } | Select-Object -First 1
}

function Test-Terminal-Running {
    [bool](Get-Process -Name "terminal64" -ErrorAction SilentlyContinue)
}

function Start-Terminal-IfNeeded {
    if (Test-Terminal-Running) { return }
    Write-Log "terminal64 not running -- starting it: $Terminal"
    Start-Process -FilePath $Terminal | Out-Null
}

function Test-DemoAccount {
    # Returns @{ ok = $true/$false; login = <int or $null>; detail = <string> }
    $py = @"
import sys
try:
    import MetaTrader5 as mt5
except Exception as e:
    print('IMPORT_FAIL:' + str(e)); sys.exit(3)
if not mt5.initialize():
    print('INIT_FAIL:' + str(mt5.last_error())); sys.exit(2)
info = mt5.account_info()
mt5.shutdown()
if info is None:
    print('NO_ACCOUNT_INFO'); sys.exit(2)
print(f'LOGIN={info.login} TRADE_MODE={info.trade_mode}')
sys.exit(0)
"@
    $tmp = Join-Path $env:TEMP "sentinel_acct_check_$PID.py"
    Set-Content -Path $tmp -Value $py -Encoding UTF8
    try {
        $out = & python $tmp 2>&1
        $code = $LASTEXITCODE
    } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
    $result = @{ ok = $false; login = $null; detail = ($out -join ' | ') }
    if ($code -eq 0 -and $out -match 'LOGIN=(\d+)\s+TRADE_MODE=(\d+)') {
        $login = [int64]$Matches[1]
        $tradeMode = [int]$Matches[2]
        $result.login = $login
        if ($login -eq $DemoLogin -and $tradeMode -eq 0) {
            $result.ok = $true
        }
    }
    return $result
}

function Wait-ForDemoAccount {
    param([int]$TimeoutSec = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $chk = Test-DemoAccount
        if ($chk.ok) {
            Write-Log "guard OK: DEMO login $($chk.login) confirmed."
            return $chk
        }
        Write-Log "Waiting for DEMO account confirmation... ($($chk.detail))"
        Start-Sleep -Seconds 5
    }
    return @{ ok = $false; login = $null; detail = "timeout" }
}

function Ensure-Watcher {
    param($AcctCheck)
    $proc = Find-ProcByCmdline 'run_deals_watcher'
    if ($proc) { return }
    if (-not $AcctCheck.ok) {
        Write-Log "SKIP watcher relaunch: account guard not OK ($($AcctCheck.detail))."
        return
    }
    Write-Log "Watcher DOWN -- relaunching."
    $env:PYTHONPATH = $RepoRoot
    $cmdLine = "python -m scripts.live.run_deals_watcher --db data/research.db --poll 5 >> `"$WatcherLog`" 2>> `"$WatcherLog.err`""
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c",$cmdLine -WorkingDirectory $RepoRoot -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
    $newProc = Find-ProcByCmdline 'run_deals_watcher'
    if ($newProc) {
        Set-Content -Path $WatcherPidFile -Value $newProc.ProcessId
        Write-Log "Watcher relaunched: new PID $($newProc.ProcessId)."
    } else {
        Write-Log "Watcher relaunch attempted but process not yet visible (will re-check next cycle)."
    }
}

function Ensure-Supervisor {
    param($AcctCheck)
    # We supervise the CANONICAL supervisor (scripts.live.supervisor_live),
    # NOT run_live_20 directly. The supervisor owns the armed executor: it
    # runs preflight before every (re)arm, relaunches the executor with
    # backoff, and alarms if the audit log goes stale. Arming run_live_20
    # here too would create DUPLICATE armed executors -> double orders.
    # The supervisor honors the STOP kill-switch internally (its preflight
    # refuses to arm while STOP exists), so we keep it alive regardless of
    # STOP and let it manage the pause.
    $proc = Find-ProcByCmdline 'supervisor_live'
    if ($proc) { return }
    if (-not $AcctCheck.ok) {
        Write-Log "SKIP supervisor relaunch: account guard not OK ($($AcctCheck.detail))."
        return
    }
    # ANTI-DUPLICATE: if the supervisor is down, any run_live_20 executor is
    # ORPHANED (a live supervisor owns its own child). Killing the parent
    # supervisor on Windows does NOT kill the child, so we must reap orphans
    # here before relaunching -- otherwise the new supervisor would arm a
    # SECOND executor -> double orders.
    $orphans = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(\.exe)?$' -and $_.CommandLine -match 'run_live_20'
    }
    foreach ($o in $orphans) {
        Write-Log "Reaping ORPHANED executor PID $($o.ProcessId) before supervisor relaunch (no live supervisor owns it)."
        try { Stop-Process -Id $o.ProcessId -Force -ErrorAction Stop } catch { Write-Log "  could not kill $($o.ProcessId): $($_.Exception.Message)" }
    }
    Write-Log "Supervisor DOWN -- relaunching (canonical: preflight-gate + armed executor + backoff + staleness alarm)."
    $env:PYTHONPATH = $RepoRoot
    $cmdLine = "python -m scripts.live.supervisor_live >> `"$SupervisorLog`" 2>> `"$SupervisorLog.err`""
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c",$cmdLine -WorkingDirectory $RepoRoot -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
    $newProc = Find-ProcByCmdline 'supervisor_live'
    if ($newProc) {
        Set-Content -Path $SupervisorPidFile -Value $newProc.ProcessId
        Write-Log "Supervisor relaunched: new PID $($newProc.ProcessId)."
    } else {
        Write-Log "Supervisor relaunch attempted but process not yet visible (will re-check next cycle)."
    }
}

function Ensure-Dashboard {
    $proc = Find-ProcByCmdline 'run_service\.py'
    if ($proc) { return }
    $listening = $false
    try {
        $conn = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
        if ($conn) { $listening = $true }
    } catch {}
    if ($listening) { return }
    Write-Log "Dashboard DOWN (nothing on 8501) -- relaunching."
    $env:PYTHONPATH = $RepoRoot
    $cmdLine = "python scripts\run_service.py --host 127.0.0.1 --port 8501 >> `"$DashboardLog`" 2>> `"$DashboardLog.err`""
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c",$cmdLine -WorkingDirectory $RepoRoot -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 3
    $newProc = Find-ProcByCmdline 'run_service\.py'
    if ($newProc) {
        Set-Content -Path $DashboardPidFile -Value $newProc.ProcessId
        Write-Log "Dashboard relaunched: new PID $($newProc.ProcessId)."
    } else {
        Write-Log "Dashboard relaunch attempted but process not yet visible (will re-check next cycle)."
    }
}

# ---------------------------------------------------------------------
Acquire-Singleton
Write-Log "watchdog_local.ps1 started (PID $PID). Poll interval ${PollSec}s."

try {
    while ($true) {
        try {
            $watcherUp   = [bool](Find-ProcByCmdline 'run_deals_watcher')
            $supervisorUp = [bool](Find-ProcByCmdline 'supervisor_live')
            $dashListening = $false
            try {
                if (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue) { $dashListening = $true }
            } catch {}
            $dashboardUp = $dashListening -or [bool](Find-ProcByCmdline 'run_service\.py')

            # Supervisor is kept alive even under STOP: it correctly refuses to
            # arm while STOP exists (preflight gate) and resumes when removed.
            $needsRelaunch = (-not $watcherUp) -or (-not $supervisorUp) -or (-not $dashboardUp)

            if ($needsRelaunch) {
                if (-not (Test-Terminal-Running)) {
                    Start-Terminal-IfNeeded
                }
                $acct = Wait-ForDemoAccount -TimeoutSec 90
                if (-not $acct.ok) {
                    Write-Log "ACCOUNT GUARD FAILED -- will NOT relaunch watcher/supervisor this cycle. ($($acct.detail))"
                }
                Ensure-Watcher -AcctCheck $acct
                Ensure-Supervisor -AcctCheck $acct
            } else {
                # cheap account check just for the log heartbeat is skipped to
                # avoid needless MT5 IPC churn when everything is healthy.
                Write-Log "OK: watcher up=$watcherUp supervisor up=$supervisorUp dashboard up=$dashboardUp (STOP=$(Test-Path $StopFile))"
            }

            Ensure-Dashboard
        } catch {
            Write-Log "ERROR in watchdog loop: $($_.Exception.Message)"
        }
        Start-Sleep -Seconds $PollSec
    }
} finally {
    Release-Singleton
}
