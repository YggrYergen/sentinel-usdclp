<#
  scripts\live\watchdog_equipo3.ps1

  WATCHDOG DEL EQUIPO 3 -- runner oficial de dos stacks (SENTINEL, 2026-09-24).

  Derivado de watchdog_local.ps1, del que conserva la estructura y las
  salvaguardas (singleton por lockfile + cmdline, deteccion por linea de
  comandos, reaping de ejecutores huerfanos, guard de cuenta antes de
  relanzar nada). Se separa de el en tres cosas, todas obligadas por el
  hecho de que aqui conviven DOS terminales MT5:

  1. DETECCION DE TERMINAL POR RUTA, NO POR NOMBRE. watchdog_local.ps1 usa
     `Get-Process -Name "terminal64"`, que es global a la maquina: con dos
     terminales abiertos devuelve verdadero aunque el caido sea el otro, y
     el terminal muerto no se relanzaria JAMAS. Aqui se consulta
     Win32_Process filtrando por ExecutablePath exacto.

  2. DOS STACKS ASIMETRICOS.
       STACK #1 (AVA 101744074) -- ARMADO. terminal + deals watcher +
         supervisor (que es quien posee el ejecutor armado). Roster `ava`:
         S6-K2P0-AVA + SuperTrend-p14x3-M15-AVA, con la configuracion
         EXACTA que corria en el equipo 1. Este script no elige roster ni
         parametros: solo levanta supervisor_live con las mismas variables
         de entorno que INICIAR_AVA_LIVE.bat.
       STACK #2 (segunda demo AVA) -- SOLO MONITORIZACION. terminal +
         deals watcher a una base separada. SIN supervisor y SIN ejecutor:
         hoy no tiene estrategias. Es OPCIONAL: si no existe su perfil
         (machine_local.ava2.json) el watchdog lo salta y sigue cuidando
         del #1 con normalidad.

  3. ENTORNO POR PROCESO, NUNCA setx. Las variables SUPERVISOR_* y
     SENTINEL_MACHINE_PROFILE se inyectan en la linea de comandos de cada
     hijo. Un setx de SUPERVISOR_MAX_SPREAD_OPEN=0.5 (el valor de la
     maquina Capitaria) bloquearia EN SILENCIO el 100% de las aperturas en
     AVA, cuyo spread en GOLD es 0.73-0.80; por eso el stack #1 la limpia
     explicitamente con `set SUPERVISOR_MAX_SPREAD_OPEN=` aunque estuviera
     heredada. Y un setx de SENTINEL_MACHINE_PROFILE apuntaria el ejecutor
     armado al terminal equivocado.

  ATTACH-ONLY: el stack de Python nunca arranca un terminal; este watchdog
  SI puede arrancarlo (igual que watchdog_local.ps1 y con la misma
  justificacion: es la herramienta del propio operador). El guard de cuenta
  sigue intacto -- nada de Python se relanza hasta que account_info()
  confirma el login DEMO esperado de ESE stack.

  NO gestiona run_bars_ingester: su SYMBOL_MAP es de Capitaria (XAUUSD,
  NQ100, ...) y no contiene GOLD, asi que en AVA no ingestaria nada y este
  watchdog lo estaria relanzando en bucle. Queda como punto abierto del
  spec, no como demonio vigilado.

  Compatible con Windows PowerShell 5.1: sin '&&'/'||', sin ternario, sin
  null-coalescing. Todas las rutas derivan de $PSScriptRoot -- ningun
  D:\FOREX hardcodeado.

  Log: scripts\live\watchdog_equipo3.log (rotacion a los 5MB).
#>

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$LiveDir  = Join-Path $RepoRoot "scripts\live"
$LogFile  = Join-Path $LiveDir "watchdog_equipo3.log"
$LockFile = Join-Path $LiveDir "watchdog_equipo3.lock"
$StopFile = Join-Path $LiveDir "STOP"

$Profile1 = Join-Path $LiveDir "machine_local.json"
$Profile2 = Join-Path $LiveDir "machine_local.ava2.json"
# Ruta RELATIVA al repo para el hijo: machine_profile la resuelve contra
# REPO_ROOT, asi la linea de comandos no lleva espacios ni unidad.
$Profile2Rel = "scripts\live\machine_local.ava2.json"

$Db1 = "data/research.db"
$Db2 = "data/research_ava2.db"

$WatcherLog1    = Join-Path $LiveDir "deals_watcher_local.log"
$WatcherLog2    = Join-Path $LiveDir "deals_watcher_ava2.log"
$SupervisorLog  = Join-Path $LiveDir "supervisor_local.log"
$DashboardLog   = Join-Path $LiveDir "run_service_local.log"

$WatcherPid1    = Join-Path $LiveDir "deals_watcher.pid"
$WatcherPid2    = Join-Path $LiveDir "deals_watcher_ava2.pid"
$SupervisorPid  = Join-Path $LiveDir "supervisor.pid"
$DashboardPid   = Join-Path $LiveDir "run_service.pid"

$PollSec     = 20
$MaxLogBytes = 5MB

# Resueltos al arrancar desde los perfiles.
$Term1 = $null; $Login1 = $null; $Portable1 = $false
$Term2 = $null; $Login2 = $null; $Portable2 = $false
$Stack2Enabled = $false

# ---------------------------------------------------------------------
function Write-Log {
    param([string]$Msg)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Msg"
    if (Test-Path $LogFile) {
        if ((Get-Item $LogFile).Length -gt $MaxLogBytes) {
            $bak = "$LogFile.1"
            if (Test-Path $bak) { Remove-Item $bak -Force }
            Rename-Item $LogFile $bak -Force
        }
    }
    Add-Content -Path $LogFile -Value $line
    Write-Output $line
}

function Assert-NoPersistedProfileVar {
    # 🔴 SENTINEL_MACHINE_PROFILE es POR PROCESO. Persistida, repuntaria
    # TODOS los procesos -- incluido el ejecutor armado del stack #1 -- al
    # terminal y la cuenta del stack #2. Preferimos no arrancar a arrancar
    # apuntando a la cuenta equivocada.
    $u = [Environment]::GetEnvironmentVariable("SENTINEL_MACHINE_PROFILE", "User")
    $m = [Environment]::GetEnvironmentVariable("SENTINEL_MACHINE_PROFILE", "Machine")
    if ($u -or $m) {
        Write-Log "ME NIEGO A ARRANCAR: SENTINEL_MACHINE_PROFILE esta persistida (User='$u' Machine='$m')."
        Write-Log "  Es una variable POR PROCESO. Borrala y vuelve a intentarlo:"
        Write-Log "    [Environment]::SetEnvironmentVariable('SENTINEL_MACHINE_PROFILE',`$null,'User')"
        Write-Log "    [Environment]::SetEnvironmentVariable('SENTINEL_MACHINE_PROFILE',`$null,'Machine')"
        exit 1
    }
}

function Resolve-Profiles {
    $env:PYTHONPATH = $RepoRoot
    $py = @"
import json, os, sys
from sentinel_engine.live.machine_profile import load_profile
from pathlib import Path
out = {}
for key, p in (("p1", r"$Profile1"), ("p2", r"$Profile2")):
    if not Path(p).exists():
        out[key] = None
        continue
    try:
        pr = load_profile(path=Path(p))
        out[key] = {"terminal_path": str(pr.terminal_path), "portable": bool(pr.portable), "demo_login": int(pr.demo_login)}
    except Exception as exc:
        out[key] = {"error": str(exc)}
print("PROFILES=" + json.dumps(out))
"@
    $tmp = Join-Path $env:TEMP "sentinel_eq3_profiles_$PID.py"
    Set-Content -Path $tmp -Value $py -Encoding UTF8
    try {
        $out = & python $tmp 2>&1
        $code = $LASTEXITCODE
    } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
    $line = ($out | Where-Object { $_ -match '^PROFILES=' } | Select-Object -First 1)
    if ($code -ne 0 -or -not $line) {
        Write-Log "ME NIEGO A ARRANCAR: no pude resolver los perfiles. ($($out -join ' | '))"
        exit 1
    }
    $prof = ($line -replace '^PROFILES=', '') | ConvertFrom-Json

    if ($null -eq $prof.p1) {
        Write-Log "ME NIEGO A ARRANCAR: falta $Profile1 (perfil del stack #1)."
        Write-Log "  Copia el bloque _stack_1 de machine_local.equipo3.example.json. Runbook paso 6."
        exit 1
    }
    if ($prof.p1.error) {
        Write-Log "ME NIEGO A ARRANCAR: perfil del stack #1 invalido: $($prof.p1.error)"
        exit 1
    }
    $script:Term1     = [string]$prof.p1.terminal_path
    $script:Login1    = [int64]$prof.p1.demo_login
    $script:Portable1 = [bool]$prof.p1.portable
    Write-Log "stack #1: terminal=$Term1 portable=$Portable1 login=$Login1"

    if ($null -eq $prof.p2) {
        Write-Log "stack #2: sin perfil ($Profile2 no existe) -- DESACTIVADO. Solo se vigila el stack #1."
        $script:Stack2Enabled = $false
        return
    }
    if ($prof.p2.error) {
        Write-Log "stack #2: perfil INVALIDO -> DESACTIVADO: $($prof.p2.error)"
        Write-Log "  (si dice 'not a member of SANCTIONED_DEMO_LOGINS', falta el paso 7 del runbook)"
        $script:Stack2Enabled = $false
        return
    }
    $script:Term2     = [string]$prof.p2.terminal_path
    $script:Login2    = [int64]$prof.p2.demo_login
    $script:Portable2 = [bool]$prof.p2.portable
    $script:Stack2Enabled = $true
    Write-Log "stack #2: terminal=$Term2 portable=$Portable2 login=$Login2"

    if ($script:Term1 -eq $script:Term2) {
        Write-Log "ME NIEGO A ARRANCAR: los dos perfiles apuntan al MISMO terminal ($Term1)."
        Write-Log "  MT5 no abre dos instancias de una misma instalacion. Runbook paso 4."
        exit 1
    }
    if ($script:Login1 -eq $script:Login2) {
        Write-Log "ME NIEGO A ARRANCAR: los dos perfiles usan el MISMO login ($Login1)."
        exit 1
    }
}

function Acquire-Singleton {
    $myPid = $PID
    $others = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match 'powershell' -and $_.CommandLine -match 'watchdog_equipo3\.ps1' -and $_.ProcessId -ne $myPid
    }
    if ($others) {
        Write-Log "ME NIEGO A ARRANCAR: ya hay otro watchdog_equipo3.ps1 (PID $($others[0].ProcessId))."
        exit 1
    }
    if (Test-Path $LockFile) {
        $lockPid = (Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        $alive = $false
        if ($lockPid) { $alive = [bool](Get-Process -Id $lockPid -ErrorAction SilentlyContinue) }
        if ($alive) {
            Write-Log "ME NIEGO A ARRANCAR: lockfile $LockFile apunta al PID vivo $lockPid."
            exit 1
        }
        Write-Log "Lockfile rancio (PID $lockPid muerto) -- tomo el relevo."
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

function Test-TerminalRunning {
    # POR RUTA, no por nombre: con dos terminales abiertos, -Name "terminal64"
    # daria verdadero para el que sigue vivo y el caido no se relanzaria nunca.
    param([string]$ExePath)
    $want = $ExePath.ToLower()
    $procs = Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'"
    foreach ($p in $procs) {
        $exe = $p.ExecutablePath
        if ($exe -and $exe.ToLower() -eq $want) { return $true }
    }
    return $false
}

function Start-TerminalIfNeeded {
    param([string]$ExePath, [bool]$Portable, [string]$Label)
    if (Test-TerminalRunning -ExePath $ExePath) { return }
    if (-not (Test-Path $ExePath)) {
        Write-Log "$Label : el exe NO existe en disco ($ExePath) -- no puedo arrancarlo."
        return
    }
    # Arrancar en el MISMO modo de datos con que se enganchara initialize()
    # (path=..., portable=$Portable). Si arrancamos SIN /portable en una
    # maquina portable, initialize(portable=True) no logra engancharse y
    # levanta su PROPIO terminal -> dos terminal64.exe (diagnosticado el
    # 2026-07-24).
    if ($Portable) {
        Write-Log "$Label : terminal caido -- arrancandolo (portable): $ExePath /portable"
        Start-Process -FilePath $ExePath -ArgumentList "/portable" | Out-Null
    } else {
        Write-Log "$Label : terminal caido -- arrancandolo: $ExePath"
        Start-Process -FilePath $ExePath | Out-Null
    }
}

function Test-Account {
    # Engancha SOLO LECTURA al terminal indicado y comprueba login+trade_mode.
    param([string]$ExePath, [bool]$Portable, [int64]$ExpectedLogin)
    $portablePy = "False"
    if ($Portable) { $portablePy = "True" }
    $py = @"
import sys
try:
    import MetaTrader5 as mt5
except Exception as e:
    print('IMPORT_FAIL:' + str(e)); sys.exit(3)
if not mt5.initialize(path=r"$ExePath", portable=$portablePy):
    print('INIT_FAIL:' + str(mt5.last_error())); sys.exit(2)
info = mt5.account_info()
mt5.shutdown()
if info is None:
    print('NO_ACCOUNT_INFO'); sys.exit(2)
print(f'LOGIN={info.login} TRADE_MODE={info.trade_mode}')
sys.exit(0)
"@
    $tmp = Join-Path $env:TEMP "sentinel_eq3_acct_$($ExpectedLogin)_$PID.py"
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
        if ($login -eq $ExpectedLogin -and $tradeMode -eq 0) { $result.ok = $true }
    }
    return $result
}

function Wait-ForAccount {
    param([string]$ExePath, [bool]$Portable, [int64]$ExpectedLogin,
          [string]$Label, [int]$TimeoutSec = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $chk = Test-Account -ExePath $ExePath -Portable $Portable -ExpectedLogin $ExpectedLogin
        if ($chk.ok) {
            Write-Log "$Label : guard OK -- DEMO $($chk.login) confirmada."
            return $chk
        }
        Write-Log "$Label : esperando confirmacion de cuenta... ($($chk.detail))"
        Start-Sleep -Seconds 5
    }
    return @{ ok = $false; login = $null; detail = "timeout" }
}

function Start-Hidden {
    # Lanza una linea de cmd oculta con el cwd en la raiz del repo.
    param([string]$CmdLine)
    $env:PYTHONPATH = $RepoRoot
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $CmdLine `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden | Out-Null
}

function Ensure-Watcher1 {
    param($AcctCheck)
    # El watcher #1 se distingue del #2 por su --db: 'research.db' no es
    # subcadena de 'research_ava2.db', asi que los patrones no colisionan.
    if (Find-ProcByCmdline 'run_deals_watcher.*research\.db') { return }
    if (-not $AcctCheck.ok) {
        Write-Log "stack #1 : NO relanzo el watcher -- guard de cuenta KO ($($AcctCheck.detail))."
        return
    }
    Write-Log "stack #1 : watcher CAIDO -- relanzando."
    Start-Hidden "python -m scripts.live.run_deals_watcher --db $Db1 --poll 5 >> `"$WatcherLog1`" 2>> `"$WatcherLog1.err`""
    Start-Sleep -Seconds 2
    $p = Find-ProcByCmdline 'run_deals_watcher.*research\.db'
    if ($p) {
        Set-Content -Path $WatcherPid1 -Value $p.ProcessId
        Write-Log "stack #1 : watcher relanzado, PID $($p.ProcessId)."
    } else {
        Write-Log "stack #1 : watcher relanzado pero aun no visible (se revisa el proximo ciclo)."
    }
}

function Ensure-Watcher2 {
    param($AcctCheck)
    if (Find-ProcByCmdline 'run_deals_watcher.*research_ava2\.db') { return }
    if (-not $AcctCheck.ok) {
        Write-Log "stack #2 : NO relanzo el watcher -- guard de cuenta KO ($($AcctCheck.detail))."
        return
    }
    Write-Log "stack #2 : watcher CAIDO -- relanzando."
    # SENTINEL_MACHINE_PROFILE va inline y SOLO aqui: es lo que hace que ESTE
    # proceso vea el terminal y el login del stack #2 en vez de los del #1.
    # OJO cmd: 'set VAR=valor&& ...' SIN espacio antes de && (un espacio ahi
    # quedaria DENTRO del valor de la variable).
    Start-Hidden "set SENTINEL_MACHINE_PROFILE=$Profile2Rel&& python -m scripts.live.run_deals_watcher --db $Db2 --poll 5 >> `"$WatcherLog2`" 2>> `"$WatcherLog2.err`""
    Start-Sleep -Seconds 2
    $p = Find-ProcByCmdline 'run_deals_watcher.*research_ava2\.db'
    if ($p) {
        Set-Content -Path $WatcherPid2 -Value $p.ProcessId
        Write-Log "stack #2 : watcher relanzado, PID $($p.ProcessId)."
    } else {
        Write-Log "stack #2 : watcher relanzado pero aun no visible (se revisa el proximo ciclo)."
    }
}

function Ensure-Supervisor {
    param($AcctCheck)
    # Vigilamos el supervisor CANONICO, no run_live_20 directamente: el
    # supervisor es el dueno del ejecutor armado (preflight + backoff +
    # alarma de log rancio). Armar run_live_20 aqui tambien crearia
    # ejecutores armados DUPLICADOS -> ordenes dobles.
    if (Find-ProcByCmdline 'supervisor_live') { return }
    if (-not $AcctCheck.ok) {
        Write-Log "stack #1 : NO relanzo el supervisor -- guard de cuenta KO ($($AcctCheck.detail))."
        return
    }
    # ANTI-DUPLICADO: si el supervisor esta caido, cualquier run_live_20 vivo
    # es HUERFANO (matar al padre en Windows no mata al hijo). Hay que segarlo
    # antes de relanzar o el nuevo supervisor armaria un SEGUNDO ejecutor.
    $orphans = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(\.exe)?$' -and $_.CommandLine -match 'run_live_20'
    }
    foreach ($o in $orphans) {
        Write-Log "stack #1 : segando ejecutor HUERFANO PID $($o.ProcessId) antes de relanzar."
        try { Stop-Process -Id $o.ProcessId -Force -ErrorAction Stop }
        catch { Write-Log "  no pude matar $($o.ProcessId): $($_.Exception.Message)" }
    }
    Write-Log "stack #1 : supervisor CAIDO -- relanzando (roster ava, GOLD, sin cap de spread)."
    # Entorno IDENTICO al de INICIAR_AVA_LIVE.bat, inyectado por proceso:
    #   SUPERVISOR_CONFIGS=ava        -> S6-K2P0-AVA + SuperTrend-p14x3-M15-AVA
    #   SUPERVISOR_SYMBOL=GOLD        -> AVA no tiene XAUUSD; sin esto el
    #                                    preflight falla y nunca se arma.
    #   SUPERVISOR_MAX_SPREAD_OPEN=   -> VACIO A PROPOSITO. El cap 0.5 de
    #                                    Capitaria no es transferible (R2): el
    #                                    spread de GOLD en AVA es 0.73-0.80 y
    #                                    un cap de 0.5 bloquearia el 100% de
    #                                    las aperturas EN SILENCIO. Se limpia
    #                                    aqui aunque viniera heredado.
    #   SUPERVISOR_STALE_AUTORESTART=1-> recicla el ejecutor si el audit log
    #                                    se queda rancio.
    $envPrefix = "set SUPERVISOR_CONFIGS=ava&& set SUPERVISOR_SYMBOL=GOLD&& set SUPERVISOR_MAX_SPREAD_OPEN=&& set SUPERVISOR_STALE_AUTORESTART=1&& "
    Start-Hidden ($envPrefix + "python -m scripts.live.supervisor_live >> `"$SupervisorLog`" 2>> `"$SupervisorLog.err`"")
    Start-Sleep -Seconds 2
    $p = Find-ProcByCmdline 'supervisor_live'
    if ($p) {
        Set-Content -Path $SupervisorPid -Value $p.ProcessId
        Write-Log "stack #1 : supervisor relanzado, PID $($p.ProcessId)."
    } else {
        Write-Log "stack #1 : supervisor relanzado pero aun no visible (se revisa el proximo ciclo)."
    }
}

function Ensure-Dashboard {
    if (Find-ProcByCmdline 'run_service\.py') { return }
    try {
        if (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue) { return }
    } catch {}
    Write-Log "dashboard CAIDO (nadie escucha en 8501) -- relanzando."
    Start-Hidden "python scripts\run_service.py --host 127.0.0.1 --port 8501 >> `"$DashboardLog`" 2>> `"$DashboardLog.err`""
    Start-Sleep -Seconds 3
    $p = Find-ProcByCmdline 'run_service\.py'
    if ($p) {
        Set-Content -Path $DashboardPid -Value $p.ProcessId
        Write-Log "dashboard relanzado, PID $($p.ProcessId)."
    }
}

# ---------------------------------------------------------------------
Assert-NoPersistedProfileVar
Acquire-Singleton
Write-Log "watchdog_equipo3.ps1 ARRANCADO (PID $PID). Sondeo cada ${PollSec}s. Repo: $RepoRoot"
Resolve-Profiles

try {
    while ($true) {
        try {
            # ---------------- STACK #1 (armado) ----------------
            $w1Up  = [bool](Find-ProcByCmdline 'run_deals_watcher.*research\.db')
            $supUp = [bool](Find-ProcByCmdline 'supervisor_live')
            if ((-not $w1Up) -or (-not $supUp)) {
                Start-TerminalIfNeeded -ExePath $Term1 -Portable $Portable1 -Label "stack #1"
                $acct1 = Wait-ForAccount -ExePath $Term1 -Portable $Portable1 `
                                         -ExpectedLogin $Login1 -Label "stack #1"
                if (-not $acct1.ok) {
                    Write-Log "stack #1 : GUARD DE CUENTA KO -- no relanzo nada este ciclo. ($($acct1.detail))"
                }
                Ensure-Watcher1 -AcctCheck $acct1
                # El supervisor se mantiene vivo incluso con STOP presente: su
                # propio preflight se niega a armar mientras STOP exista y
                # reanuda al quitarlo. El es quien gestiona la pausa.
                Ensure-Supervisor -AcctCheck $acct1
            }

            # ---------------- STACK #2 (solo monitorizacion) ----------------
            $w2Up = $false
            if ($Stack2Enabled) {
                $w2Up = [bool](Find-ProcByCmdline 'run_deals_watcher.*research_ava2\.db')
                if (-not $w2Up) {
                    Start-TerminalIfNeeded -ExePath $Term2 -Portable $Portable2 -Label "stack #2"
                    $acct2 = Wait-ForAccount -ExePath $Term2 -Portable $Portable2 `
                                             -ExpectedLogin $Login2 -Label "stack #2"
                    if (-not $acct2.ok) {
                        Write-Log "stack #2 : GUARD DE CUENTA KO -- no relanzo el watcher. ($($acct2.detail))"
                    }
                    Ensure-Watcher2 -AcctCheck $acct2
                }
            }

            if ($w1Up -and $supUp -and (($Stack2Enabled -eq $false) -or $w2Up)) {
                Write-Log "OK: watcher1=$w1Up supervisor=$supUp watcher2=$w2Up stack2=$Stack2Enabled STOP=$(Test-Path $StopFile)"
            }

            Ensure-Dashboard
        } catch {
            Write-Log "ERROR en el bucle del watchdog: $($_.Exception.Message)"
        }
        Start-Sleep -Seconds $PollSec
    }
} finally {
    Release-Singleton
}
