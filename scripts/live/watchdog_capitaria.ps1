<#
  scripts\live\watchdog_capitaria.ps1

  WATCHDOG DEL STACK CAPITARIA en el equipo 3 (SENTINEL, 2026-09-24).

  Derivado de watchdog_local.ps1 (el que corrio en la maquina 2 / W11), del que
  conserva TODA la logica de decision y las salvaguardas. No cambia ni un
  parametro de estrategia: el roster, el lote 0.67, el cap de spread 0.50, la
  ventana bloqueada 18:00-18:45 y el gate adaptativo apagado son EXACTAMENTE los
  de b113eb7 / M2_ENTREGA.

  Se separa de el SOLO en lo que obliga el hecho de que en esta maquina conviven
  TRES terminales MT5 y DOS clones del repo operando a la vez:

    C:\FOREX      rama equipo3-runner     -> 2 cuentas AVA (GOLD)
    C:\FOREX_CAP  rama equipo3-capitaria  -> 1 cuenta Capitaria (XAUUSD)  <- este

  LAS CUATRO COLISIONES QUE ESTE FICHERO ARREGLA. Sin ellas, los dos stacks se
  destruyen mutuamente; ninguna da un error visible:

  1. `Get-Process -Name "terminal64"` (original linea 156) es GLOBAL a la
     maquina. Con tres terminales abiertos devuelve verdadero SIEMPRE, asi que
     el terminal de Capitaria, si se cae, NO SE RELANZA JAMAS. Aqui se filtra
     por ExecutablePath exacto.

  2. `Find-ProcByCmdline 'supervisor_live'` (original 253) encontraria el
     SUPERVISOR DE AVA y concluiria que el suyo ya esta vivo -> el stack
     Capitaria no arrancaria nunca, en silencio.

  3. `Find-ProcByCmdline 'run_deals_watcher'` (original 223) encontraria
     cualquiera de los DOS watchers de AVA. Mismo efecto.

  4. 🔴 EL PEOR: la siega de huerfanos (original 265) mata TODO proceso cuya
     linea de comandos contenga `run_live_20`, sin filtrar por carpeta. Cada vez
     que este watchdog relanzara su supervisor, MATARIA EL EJECUTOR ARMADO DE
     AVA, dejando posiciones abiertas sin nadie que las gestione.

  COMO SE ARREGLAN LAS TRES ULTIMAS (REVISADO 2026-10-06). El primer diseno
  filtraba solo por ExecutablePath == venv, y era INSUFICIENTE: en Windows
  `<venv>\Scripts\python.exe` es un REDIRECTOR que lanza como HIJO al Python
  base (`...\Python311\python.exe`). El hijo es el que trabaja de verdad y su
  ExecutablePath es el del sistema -- el MISMO que usa el stack AVA --, con los
  mismos modulos en la linea de comandos. Resultado: el watchdog de AVA tomaba
  los trabajadores de Capitaria por suyos (y viceversa se veia solo al
  redirector; matar el redirector no mata al hijo).

  Ahora la propiedad se decide por DOS rasgos, cualquiera basta:
    a) la linea de comandos contiene `sentinel_stack=capitaria`. Todo python que
       lanza ESTE watchdog lleva `-X sentinel_stack=capitaria` justo tras el
       exe; CPython guarda los -X desconocidos en sys._xoptions sin efecto, y el
       redirector pasa los args tal cual, asi que lo llevan redirector E hijo.
    b) ExecutablePath == el venv de este clon (el redirector). Hace falta
       porque el supervisor lanza el ejecutor y el watcher con
       `[sys.executable, "-m", ...]` SIN el -X (los -X no se heredan): ese
       redirector no lleva marca, pero su exe es exacto. Su hijo base no se
       identifica solo -> por eso toda muerte se hace con `taskkill /T /F`.
  Un servicio logico se cuenta UNA vez (el redirector tiene preferencia).
  El interprete clavado tambien resuelve el riesgo D1 del acta del equipo 3:
  `python` a secas resolvia a 3.14.5 en consola interactiva y a 3.11 bajo la
  tarea programada, dependiendo del PATH.

  El dashboard va al puerto 8502: el 8501 es de AVA.

  ATTACH-ONLY: el stack de Python nunca arranca un terminal; este watchdog SI
  puede (misma justificacion que su original). El guard de cuenta sigue intacto:
  nada de Python se relanza hasta que account_info() confirma el login esperado.

  Compatible con Windows PowerShell 5.1: sin '&&'/'||', sin ternario, sin
  null-coalescing. Rutas derivadas de $PSScriptRoot -- nada hardcodeado.

  Log: scripts\live\watchdog_capitaria.log
#>

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$LiveDir  = Join-Path $RepoRoot "scripts\live"
$LogFile  = Join-Path $LiveDir "watchdog_capitaria.log"
$LockFile = Join-Path $LiveDir "watchdog_capitaria.lock"
$StopFile = Join-Path $LiveDir "STOP"

# 🔴 INTERPRETE CLAVADO. Es a la vez el fix del riesgo D1 y el mecanismo por el
# que este watchdog distingue SUS procesos de los del stack AVA.
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"

# MARCA DE PROPIEDAD. `-X sentinel_stack=capitaria` va justo tras el exe en
# CADA python que lanza este watchdog. Sin efecto en ejecucion (sys._xoptions);
# visible en Win32_Process.CommandLine tanto del redirector como de su hijo.
$StackMarker = "sentinel_stack=capitaria"
$PyOpt       = "-X $StackMarker"

$WatcherLog    = Join-Path $LiveDir "deals_watcher_local.log"
$SupervisorLog = Join-Path $LiveDir "supervisor_local.log"
$DashboardLog  = Join-Path $LiveDir "run_service_local.log"

$WatcherPidFile    = Join-Path $LiveDir "deals_watcher.pid"
$SupervisorPidFile = Join-Path $LiveDir "supervisor.pid"
$DashboardPidFile  = Join-Path $LiveDir "run_service.pid"

$DashboardPort = 8502          # 8501 es de AVA

$Terminal  = $null
$DemoLogin = $null
$Portable  = $false
$PollSec   = 20
$MaxLogBytes = 5MB

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

function Assert-Venv {
    if (-not (Test-Path $PythonExe)) {
        Write-Log "ME NIEGO A ARRANCAR: no existe el interprete del venv en $PythonExe"
        Write-Log "  Este stack DEBE correr en su propio venv: es lo que lo distingue de los"
        Write-Log "  procesos del stack AVA. Crealo (paso 4 de las instrucciones):"
        Write-Log "    py -3.11 -m venv `"$RepoRoot\.venv`""
        Write-Log "    & `"$PythonExe`" -m pip install -r scripts\live\requirements-capitaria.txt"
        exit 1
    }
    $v = & $PythonExe -X $StackMarker -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1
    Write-Log "interprete: $PythonExe (Python $v)"
    if ("$v".Trim() -ne "3.11") {
        Write-Log "AVISO: el venv no es Python 3.11 sino $v. Las dependencias estan fijadas a 3.11."
    }
}

function Resolve-MachineProfile {
    $env:PYTHONPATH = $RepoRoot
    $py = @"
import json
from sentinel_engine.live.machine_profile import load_profile
p = load_profile()
print("PROFILE=" + json.dumps({"terminal_path": str(p.terminal_path), "portable": bool(p.portable), "demo_login": int(p.demo_login)}))
"@
    $tmp = Join-Path $env:TEMP "sentinel_cap_profile_$PID.py"
    Set-Content -Path $tmp -Value $py -Encoding UTF8
    try {
        $out = & $PythonExe -X $StackMarker $tmp 2>&1
        $code = $LASTEXITCODE
    } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
    $line = ($out | Where-Object { $_ -match '^PROFILE=' } | Select-Object -First 1)
    if ($code -ne 0 -or -not $line) {
        # NUNCA caer a los valores por defecto (maquina 1, terminal portable de
        # Capitaria, login 2883015767): este stack apunta a una cuenta distinta y
        # un default silencioso lo ataria a la cuenta equivocada.
        Write-Log "ME NIEGO A ARRANCAR: no pude resolver el perfil de maquina. ($($out -join ' | '))"
        Write-Log "  Comprueba que existe scripts\live\machine_local.json en ESTE clon."
        exit 1
    }
    $prof = ($line -replace '^PROFILE=', '') | ConvertFrom-Json
    $script:Terminal  = [string]$prof.terminal_path
    $script:DemoLogin = [int64]$prof.demo_login
    $script:Portable  = [bool]$prof.portable
    Write-Log "perfil: terminal=$Terminal portable=$Portable demo_login=$DemoLogin"
}

function Acquire-Singleton {
    $myPid = $PID
    $others = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match 'powershell' -and $_.CommandLine -match 'watchdog_capitaria\.ps1' -and $_.ProcessId -ne $myPid
    }
    if ($others) {
        Write-Log "ME NIEGO A ARRANCAR: ya hay otro watchdog_capitaria.ps1 (PID $($others[0].ProcessId))."
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

function Test-IsRedirector {
    # El redirector del venv: su ExecutablePath ES el interprete del venv.
    param($Proc)
    return [bool]($Proc.ExecutablePath -and $Proc.ExecutablePath.ToLower() -eq $PythonExe.ToLower())
}

function Test-IsMine {
    # Propiedad (ver cabecera): marca -X en la linea de comandos (redirector e
    # hijo) O exe == venv (redirector, incluido el del ejecutor que lanza el
    # supervisor sin marca). Nunca basta el ExecutablePath del Python base: es
    # el mismo que usa AVA.
    param($Proc)
    if ($Proc.Name -notmatch '^python(\.exe)?$') { return $false }
    if (Test-IsRedirector $Proc) { return $true }
    return [bool]($Proc.CommandLine -and $Proc.CommandLine.Contains($StackMarker))
}

function Get-MyProcs {
    # Procesos python de ESTE stack cuya linea de comandos casa con $Pattern.
    param([string]$Pattern)
    Get-CimInstance Win32_Process | Where-Object {
        (Test-IsMine $_) -and $_.CommandLine -match $Pattern
    }
}

function Find-MyProc {
    # COLISIONES 2 y 3. Cuenta cada servicio logico UNA vez: devuelve el
    # redirector si existe (su hijo con marca es el mismo servicio); solo si no
    # hay redirector devuelve un proceso con marca (hijo huerfano de un
    # redirector muerto).
    param([string]$Pattern)
    $all = @(Get-MyProcs $Pattern)
    foreach ($p in $all) { if (Test-IsRedirector $p) { return $p } }
    if ($all.Count -gt 0) { return $all[0] }
    return $null
}

function Stop-ProcTree {
    # Matar SOLO el redirector deja vivo a su hijo (el trabajador real).
    # `taskkill /T /F` mata el arbol entero. Start-Process en vez de `&` para
    # que el stderr de taskkill no se convierta en excepcion con
    # $ErrorActionPreference = Stop (PowerShell 5.1).
    param([int]$ProcId)
    if (-not (Get-Process -Id $ProcId -ErrorAction SilentlyContinue)) { return $true }
    $k = Start-Process -FilePath "taskkill.exe" -ArgumentList "/PID", $ProcId, "/T", "/F" `
            -Wait -PassThru -WindowStyle Hidden
    return ($k.ExitCode -eq 0)
}

function Test-TerminalRunning {
    # COLISION 1: por ruta, no por nombre.
    param([string]$ExePath)
    $want = $ExePath.ToLower()
    $procs = Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'"
    foreach ($p in $procs) {
        if ($p.ExecutablePath -and $p.ExecutablePath.ToLower() -eq $want) { return $true }
    }
    return $false
}

function Start-TerminalIfNeeded {
    if (Test-TerminalRunning -ExePath $Terminal) { return }
    if (-not (Test-Path $Terminal)) {
        Write-Log "el terminal NO existe en disco ($Terminal) -- no puedo arrancarlo."
        return
    }
    if ($Portable) {
        Write-Log "terminal caido -- arrancandolo (portable): $Terminal /portable"
        Start-Process -FilePath $Terminal -ArgumentList "/portable" | Out-Null
    } else {
        Write-Log "terminal caido -- arrancandolo: $Terminal"
        Start-Process -FilePath $Terminal | Out-Null
    }
}

function Test-DemoAccount {
    $portablePy = "False"
    if ($Portable) { $portablePy = "True" }
    $py = @"
import sys
try:
    import MetaTrader5 as mt5
except Exception as e:
    print('IMPORT_FAIL:' + str(e)); sys.exit(3)
if not mt5.initialize(path=r"$Terminal", portable=$portablePy):
    print('INIT_FAIL:' + str(mt5.last_error())); sys.exit(2)
info = mt5.account_info()
mt5.shutdown()
if info is None:
    print('NO_ACCOUNT_INFO'); sys.exit(2)
print(f'LOGIN={info.login} TRADE_MODE={info.trade_mode}')
sys.exit(0)
"@
    $tmp = Join-Path $env:TEMP "sentinel_cap_acct_$PID.py"
    Set-Content -Path $tmp -Value $py -Encoding UTF8
    try {
        $out = & $PythonExe -X $StackMarker $tmp 2>&1
        $code = $LASTEXITCODE
    } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
    $result = @{ ok = $false; login = $null; detail = ($out -join ' | ') }
    if ($code -eq 0 -and $out -match 'LOGIN=(\d+)\s+TRADE_MODE=(\d+)') {
        $login = [int64]$Matches[1]
        $tradeMode = [int]$Matches[2]
        $result.login = $login
        if ($login -eq $DemoLogin -and $tradeMode -eq 0) { $result.ok = $true }
    }
    return $result
}

function Wait-ForDemoAccount {
    param([int]$TimeoutSec = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $chk = Test-DemoAccount
        if ($chk.ok) {
            Write-Log "guard OK: DEMO $($chk.login) confirmada."
            return $chk
        }
        Write-Log "esperando confirmacion de cuenta... ($($chk.detail))"
        Start-Sleep -Seconds 5
    }
    return @{ ok = $false; login = $null; detail = "timeout" }
}

function Start-Hidden {
    param([string]$CmdLine)
    $env:PYTHONPATH = $RepoRoot
    # OJO cmd /c: si la linea EMPIEZA por comillas y lleva mas de dos, cmd
    # quita la primera y la ultima comilla y la linea queda rota ("El nombre de
    # archivo... no son correctos"; medido 2026-10-06). Las lineas de watcher y
    # dashboard empiezan por `"<python>"`, asi que se envuelve TODA la linea en
    # un par extra de comillas, que es lo que cmd retira.
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$CmdLine`"" `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden | Out-Null
}

function Ensure-Watcher {
    param($AcctCheck)
    if (Find-MyProc 'run_deals_watcher') { return }
    if (-not $AcctCheck.ok) {
        Write-Log "NO relanzo el watcher -- guard de cuenta KO ($($AcctCheck.detail))."
        return
    }
    Write-Log "watcher CAIDO -- relanzando."
    Start-Hidden "`"$PythonExe`" $PyOpt -m scripts.live.run_deals_watcher --db data/research.db --poll 5 >> `"$WatcherLog`" 2>> `"$WatcherLog.err`""
    Start-Sleep -Seconds 2
    $p = Find-MyProc 'run_deals_watcher'
    if ($p) {
        Set-Content -Path $WatcherPidFile -Value $p.ProcessId
        Write-Log "watcher relanzado, PID $($p.ProcessId)."
    } else {
        Write-Log "watcher relanzado pero aun no visible (se revisa el proximo ciclo)."
    }
}

function Ensure-Supervisor {
    param($AcctCheck)
    if (Find-MyProc 'supervisor_live') { return }
    if (-not $AcctCheck.ok) {
        Write-Log "NO relanzo el supervisor -- guard de cuenta KO ($($AcctCheck.detail))."
        return
    }
    # 🔴 COLISION 4, LA PEOR. El original sega TODO `run_live_20` de la maquina.
    # Aqui la siega se limita a procesos de ESTE stack (marca -X o exe == venv):
    # el ejecutor armado de AVA queda intocado. Se mata el ARBOL (/T): el
    # redirector del ejecutor tiene un hijo base que de otro modo seguiria
    # operando sin supervisor.
    $orphans = @(Get-MyProcs 'run_live_20')
    foreach ($o in $orphans) {
        Write-Log "segando ejecutor HUERFANO de ESTE stack, PID $($o.ProcessId) y su arbol (ningun supervisor vivo lo posee)."
        try {
            if (-not (Stop-ProcTree -ProcId ([int]$o.ProcessId))) {
                Write-Log "  taskkill /T /F fallo para $($o.ProcessId)."
            }
        } catch { Write-Log "  no pude matar $($o.ProcessId): $($_.Exception.Message)" }
    }
    Write-Log "supervisor CAIDO -- relanzando (roster tomachine, XAUUSD, cap 0.50, ventana 18:00-18:45, gate adaptativo OFF)."
    # Entorno EXACTO de M2_ENTREGA (RESUMEN.md, 'Env efectivas'), inyectado por
    # proceso. NUNCA con setx: en esta maquina conviven dos stacks y una variable
    # persistida se aplicaria tambien al de AVA -- donde SUPERVISOR_MAX_SPREAD_OPEN=0.5
    # bloquearia el 100% de las aperturas en silencio.
    # OJO cmd: 'set VAR=valor&&' SIN espacio antes de && (el espacio entraria en el valor).
    $envPrefix = "set SUPERVISOR_CONFIGS=tomachine&& set SUPERVISOR_MAX_SPREAD_OPEN=0.5&& set SUPERVISOR_BLOCKED_OPEN_WINDOW=18:00-18:45&& set SUPERVISOR_NO_ADAPTIVE_SPREAD=1&& "
    Start-Hidden ($envPrefix + "`"$PythonExe`" $PyOpt -m scripts.live.supervisor_live >> `"$SupervisorLog`" 2>> `"$SupervisorLog.err`"")
    Start-Sleep -Seconds 2
    $p = Find-MyProc 'supervisor_live'
    if ($p) {
        Set-Content -Path $SupervisorPidFile -Value $p.ProcessId
        Write-Log "supervisor relanzado, PID $($p.ProcessId)."
    } else {
        Write-Log "supervisor relanzado pero aun no visible (se revisa el proximo ciclo)."
    }
}

function Ensure-Dashboard {
    if (Find-MyProc 'run_service\.py') { return }
    try {
        if (Get-NetTCPConnection -LocalPort $DashboardPort -State Listen -ErrorAction SilentlyContinue) { return }
    } catch {}
    Write-Log "dashboard CAIDO (nadie escucha en $DashboardPort) -- relanzando."
    Start-Hidden "`"$PythonExe`" $PyOpt scripts\run_service.py --host 127.0.0.1 --port $DashboardPort --force-historical >> `"$DashboardLog`" 2>> `"$DashboardLog.err`""
    Start-Sleep -Seconds 3
    $p = Find-MyProc 'run_service\.py'
    if ($p) {
        Set-Content -Path $DashboardPidFile -Value $p.ProcessId
        Write-Log "dashboard relanzado, PID $($p.ProcessId)."
    }
}

# ---------------------------------------------------------------------
Acquire-Singleton
Write-Log "watchdog_capitaria.ps1 ARRANCADO (PID $PID). Sondeo cada ${PollSec}s. Repo: $RepoRoot"
Assert-Venv
Resolve-MachineProfile

try {
    while ($true) {
        try {
            $watcherUp    = [bool](Find-MyProc 'run_deals_watcher')
            $supervisorUp = [bool](Find-MyProc 'supervisor_live')
            $dashUp = $false
            try {
                if (Get-NetTCPConnection -LocalPort $DashboardPort -State Listen -ErrorAction SilentlyContinue) { $dashUp = $true }
            } catch {}
            if (-not $dashUp) { $dashUp = [bool](Find-MyProc 'run_service\.py') }

            if ((-not $watcherUp) -or (-not $supervisorUp)) {
                Start-TerminalIfNeeded
                $acct = Wait-ForDemoAccount -TimeoutSec 90
                if (-not $acct.ok) {
                    Write-Log "GUARD DE CUENTA KO -- no relanzo nada este ciclo. ($($acct.detail))"
                }
                Ensure-Watcher -AcctCheck $acct
                # El supervisor se mantiene vivo incluso con STOP: su propio
                # preflight se niega a armar mientras exista y reanuda al quitarlo.
                Ensure-Supervisor -AcctCheck $acct
            } else {
                Write-Log "OK: watcher=$watcherUp supervisor=$supervisorUp dashboard=$dashUp STOP=$(Test-Path $StopFile)"
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
