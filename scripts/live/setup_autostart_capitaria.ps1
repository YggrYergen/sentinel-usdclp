<#
  scripts\live\setup_autostart_capitaria.ps1

  AUTOARRANQUE DEL STACK CAPITARIA en el equipo 3 (SENTINEL, 2026-09-24).

  Registra la tarea SENTINEL_Watchdog_Capitaria, que corre
  scripts\live\watchdog_capitaria.ps1 oculta al iniciar sesion, con reinicio
  ante fallo y sin limite de tiempo de ejecucion.

  NO toca la configuracion de energia: de eso ya se encargo
  setup_autostart_equipo3.ps1 en el clon de AVA, y es una propiedad de la
  MAQUINA, no del stack. Hacerlo dos veces no aporta nada.

  NO hace `setx` de NADA. En esta maquina conviven dos stacks: una variable
  persistida se aplicaria a los dos. En particular
  SUPERVISOR_MAX_SPREAD_OPEN=0.5 (correcta aqui, para XAUUSD) bloquearia el
  100% de las aperturas del stack AVA EN SILENCIO. El watchdog inyecta el
  entorno por proceso.

  CERROJOS -- se niega a correr si:
    - no existe el venv propio (es lo que distingue estos procesos de los de AVA)
    - no existe scripts\live\machine_local.json en ESTE clon
    - el clon esta en la misma carpeta que el stack AVA
    - hay variables SUPERVISOR_* o SENTINEL_MACHINE_PROFILE persistidas

  NUNCA arma trading. Eso solo lo hace el supervisor tras pasar su preflight.

  Windows PowerShell 5.1. Rutas derivadas de $PSScriptRoot.

  USO (PowerShell ELEVADO):
      powershell -NoProfile -ExecutionPolicy Bypass -File scripts\live\setup_autostart_capitaria.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RepoRoot    = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$LiveDir     = Join-Path $RepoRoot "scripts\live"
$WatchdogPs1 = Join-Path $LiveDir "watchdog_capitaria.ps1"
$ProfileJson = Join-Path $LiveDir "machine_local.json"
$PythonExe   = Join-Path $RepoRoot ".venv\Scripts\python.exe"

$TaskName = "SENTINEL_Watchdog_Capitaria"
$AvaTask  = "SENTINEL_Watchdog_Equipo3"

function Write-Section { param([string]$m) Write-Output ""; Write-Output "==== $m ====" }

Write-Section "SENTINEL -- autoarranque del stack CAPITARIA (equipo 3)"
Write-Output "RepoRoot: $RepoRoot"

# --------------------------------------------------------------------------
Write-Section "Cerrojo 1: venv propio"
if (-not (Test-Path $PythonExe)) {
    Write-Output "ERROR: no existe $PythonExe"
    Write-Output "  Este stack DEBE correr en su propio venv. Es lo que permite al watchdog"
    Write-Output "  distinguir sus procesos de los del stack AVA -- sin el, la siega de"
    Write-Output "  ejecutores huerfanos mataria el ejecutor armado de AVA."
    Write-Output "  Crealo:"
    Write-Output "    py -3.11 -m venv `"$RepoRoot\.venv`""
    Write-Output "    & `"$PythonExe`" -m pip install -r scripts\live\requirements-capitaria.txt"
    exit 1
}
$pyv = (& $PythonExe -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>&1)
Write-Output "OK: venv en $PythonExe (Python $pyv)"

# --------------------------------------------------------------------------
Write-Section "Cerrojo 2: no compartir carpeta con el stack AVA"
$avaTaskObj = Get-ScheduledTask -TaskName $AvaTask -ErrorAction SilentlyContinue
if ($null -ne $avaTaskObj) {
    $avaDir = $avaTaskObj.Actions[0].WorkingDirectory
    if ($avaDir -and ((Resolve-Path $avaDir -ErrorAction SilentlyContinue).Path -eq $RepoRoot)) {
        Write-Output "ME NIEGO A CORRER: el stack AVA ('$AvaTask') usa ESTE MISMO directorio ($RepoRoot)."
        Write-Output "  Los dos stacks necesitan clones SEPARADOS: comparten STOP, audit log,"
        Write-Output "  spread store y research.db si viven en la misma carpeta."
        exit 1
    }
    Write-Output "OK: el stack AVA vive en '$avaDir', distinto de este clon."
} else {
    Write-Output "AVISO: no encuentro la tarea '$AvaTask'. Si el stack AVA no esta instalado en"
    Write-Output "  esta maquina, ignora este aviso."
}

# --------------------------------------------------------------------------
Write-Section "Cerrojo 3: perfil de maquina de ESTE clon"
if (-not (Test-Path $ProfileJson)) {
    Write-Output "ERROR: no existe $ProfileJson"
    Write-Output "  Sin el, load_profile() caeria a los valores por defecto de la maquina 1"
    Write-Output "  (terminal portable, login 2883015767) y el guard rechazaria todo."
    Write-Output "  Copia el bloque de machine_local.capitaria.example.json."
    exit 1
}
try { $cfg = (Get-Content -Raw -Path $ProfileJson -Encoding UTF8) | ConvertFrom-Json }
catch { Write-Output "ERROR: no pude interpretar $ProfileJson : $($_.Exception.Message)"; exit 1 }
Write-Output "OK: machine_local.json -> demo_login=$($cfg.demo_login) terminal=$($cfg.terminal_path)"

# --------------------------------------------------------------------------
Write-Section "Cerrojo 4: variables de entorno persistidas"
$fatal = $false
foreach ($name in @("SUPERVISOR_CONFIGS","SUPERVISOR_MAX_SPREAD_OPEN","SUPERVISOR_BLOCKED_OPEN_WINDOW",
                    "SUPERVISOR_NO_ADAPTIVE_SPREAD","SUPERVISOR_SYMBOL","SENTINEL_MACHINE_PROFILE")) {
    foreach ($scope in @("User","Machine")) {
        $v = [Environment]::GetEnvironmentVariable($name, $scope)
        if ($v) {
            Write-Output "FATAL: $name persistida en ambito $scope ('$v')."
            Write-Output "  En esta maquina conviven DOS stacks. Una variable persistida se aplica a"
            Write-Output "  los dos. Borrala:"
            Write-Output "    [Environment]::SetEnvironmentVariable('$name',`$null,'$scope')"
            $fatal = $true
        }
    }
}
if ($fatal) {
    Write-Output ""
    Write-Output "ME NIEGO A CONTINUAR. Tras borrarlas, ABRE UNA CONSOLA NUEVA."
    exit 1
}
Write-Output "OK: ninguna variable persistida."

# --------------------------------------------------------------------------
Write-Section "Programador de tareas: $TaskName"
if (-not (Test-Path $WatchdogPs1)) { Write-Output "ERROR: no encuentro $WatchdogPs1"; exit 1 }

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    Write-Output "La tarea ya existe -- la borro y la vuelvo a crear (idempotente)."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$psExe   = (Get-Command powershell.exe).Source
$argList = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WatchdogPs1`""
$action  = New-ScheduledTaskAction -Execute $psExe -Argument $argList -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "Tarea '$TaskName' registrada (oculta al iniciar sesion, reinicio ante fallo, sin caducidad)."

Write-Section "RESUMEN"
Write-Output "HECHO: tarea '$TaskName' registrada."
Write-Output "NO hecho (a proposito): setx de variables, y configuracion de energia"
Write-Output "  (ya la dejo setup_autostart_equipo3.ps1; es propiedad de la maquina)."
Write-Output ""
Write-Output "PENDIENTE A MANO:"
Write-Output "  1. Abre el terminal MT5 de Capitaria e inicia sesion en la cuenta UNA VEZ."
Write-Output "  2. Anade XAUUSD a Observacion de Mercado en ESE terminal."
Write-Output "     🔴 Imprescindible: si la instalacion se movio de carpeta, MT5 creo una"
Write-Output "        carpeta de datos nueva y vacia y la seleccion NO viajo. El sintoma es"
Write-Output "        'symbol-tradable: symbol=XAUUSD visible=False' repetido en el log."
Write-Output "  3. Arranca ya, sin reiniciar:"
Write-Output "         Start-ScheduledTask -TaskName $TaskName"
Write-Output "  4. Vigila:"
Write-Output "         Get-Content `"$LiveDir\watchdog_capitaria.log`" -Wait -Tail 40"
Write-Output "         Get-Content `"$LiveDir\watchdog.log`" -Wait -Tail 40   # preflight del supervisor"
Write-Output ""
Write-Output "OK."
