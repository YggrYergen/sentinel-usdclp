<#
  scripts\live\setup_autostart_equipo3.ps1

  AUTOARRANQUE DEL EQUIPO 3 (runner oficial, SENTINEL 2026-09-24). Deja el
  stack como un servicio duradero y auto-sanable, para que los dos terminales
  MT5, los dos deals watchers, el supervisor y el dashboard sobrevivan a
  reinicios y cierres de sesion sin que nadie cuide una consola.

  Hermano de setup_autostart_machine1.ps1, del que copia la estructura. Lo que
  hace:
    1. Registra una tarea programada (SENTINEL_Watchdog_Equipo3) que corre
       scripts\live\watchdog_equipo3.ps1 oculta al iniciar sesion, con
       reinicio ante fallo. El watchdog es el auto-sanador.
    2. Desactiva suspension e hibernacion con corriente alterna (una maquina
       dormida deja de operar).
    3. Comprueba -- y se NIEGA a continuar -- si hay variables de entorno
       persistidas que sabotearian el stack en silencio.

  NO hace setx de NINGUNA variable, a diferencia del script de la maquina 1.
  Es deliberado: en el equipo 3 conviven dos stacks y las variables van
  inyectadas POR PROCESO desde el watchdog. Una variable persistida se
  aplicaria a los dos y a cualquier otra cosa que corra en la maquina
  (incluido pytest, que ya se rompio asi en la maquina 1).

  NUNCA arma trading ni manda una orden. Puede, eso si, registrar el watchdog,
  que a su vez SI puede arrancar los terminales MT5 (ver la cabecera de
  watchdog_equipo3.ps1: el stack de Python sigue siendo attach-only y se niega
  a armar hasta que account_info() confirma la cuenta DEMO esperada).

  CERROJO DEL EQUIPO 3: se niega a correr si machine_local.json no nombra el
  login 101744074. Asi no puede ejecutarse por error en el equipo 1 o en la
  maquina Capitaria.

  Compatible con Windows PowerShell 5.1: sin '&&'/'||', sin ternario, sin
  null-coalescing. Rutas derivadas de $PSScriptRoot -- ningun D:\FOREX
  hardcodeado.

  USO (desde un PowerShell ELEVADO, para powercfg y la tarea):
      powershell -NoProfile -ExecutionPolicy Bypass -File scripts\live\setup_autostart_equipo3.ps1
  Modificadores:
      -TaskOnly   : solo registra la tarea; no toca la configuracion de energia.
      -PowerOnly  : solo configura la energia; no registra la tarea.
#>
[CmdletBinding()]
param(
    [switch]$TaskOnly,
    [switch]$PowerOnly
)

$ErrorActionPreference = "Stop"

$ScriptDir   = $PSScriptRoot
$RepoRoot    = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$LiveDir     = Join-Path $RepoRoot "scripts\live"
$WatchdogPs1 = Join-Path $LiveDir "watchdog_equipo3.ps1"
$Profile1    = Join-Path $LiveDir "machine_local.json"
$Profile2    = Join-Path $LiveDir "machine_local.ava2.json"

$EQUIPO3_LOGIN = 101744074
$TaskName = "SENTINEL_Watchdog_Equipo3"

function Write-Section {
    param([string]$Msg)
    Write-Output ""
    Write-Output "==== $Msg ===="
}

# --------------------------------------------------------------------------
# CERROJO: solo el equipo 3. El perfil del stack #1 tiene que nombrar la
# cuenta AVA 101744074. A diferencia del script de la maquina 1, aqui la
# AUSENCIA del fichero tambien es un fallo: sin perfil, load_profile() caeria
# a los valores por defecto de la maquina 1 (terminal portable de Capitaria,
# login 2883015767), que no existen en esta maquina.
# --------------------------------------------------------------------------
function Assert-Equipo3 {
    Write-Section "Cerrojo del equipo 3"
    if (-not (Test-Path $Profile1)) {
        Write-Output "ERROR: no existe $Profile1."
        Write-Output "  Copia el bloque _stack_1 de machine_local.equipo3.example.json primero."
        Write-Output "  (Sin el, el stack caeria a los valores por defecto de la maquina 1.)"
        exit 1
    }
    try {
        $cfg = (Get-Content -Raw -Path $Profile1 -Encoding UTF8) | ConvertFrom-Json
    } catch {
        Write-Output "ERROR: no pude interpretar $Profile1 : $($_.Exception.Message)"
        exit 1
    }
    $login = $cfg.demo_login
    if ($null -eq $login) {
        Write-Output "ERROR: $Profile1 no tiene demo_login."
        exit 1
    }
    if ([int64]$login -ne $EQUIPO3_LOGIN) {
        Write-Output "ME NIEGO A CORRER: machine_local.json dice demo_login=$login, no $EQUIPO3_LOGIN."
        Write-Output "Este script es SOLO del equipo 3. No lo corras en el equipo 1 ni en la maquina Capitaria."
        exit 1
    }
    Write-Output "OK: machine_local.json -> demo_login=$login (AVA, equipo 3)."

    if (Test-Path $Profile2) {
        Write-Output "OK: perfil del stack #2 presente ($Profile2) -- el watchdog lo vigilara."
    } else {
        Write-Output "AVISO: no hay perfil del stack #2 ($Profile2)."
        Write-Output "  El watchdog arrancara igual y cuidara solo del stack #1."
        Write-Output "  Anadelo cuando tengas el login de la segunda demo AVA (runbook paso 7)."
    }
}

# --------------------------------------------------------------------------
# Variables persistidas que sabotean el stack EN SILENCIO.
# --------------------------------------------------------------------------
function Assert-NoToxicEnv {
    Write-Section "Variables de entorno persistidas"
    $fatal = $false

    foreach ($scope in @("User", "Machine")) {
        $v = [Environment]::GetEnvironmentVariable("SENTINEL_MACHINE_PROFILE", $scope)
        if ($v) {
            Write-Output "FATAL: SENTINEL_MACHINE_PROFILE esta persistida en ambito $scope ('$v')."
            Write-Output "  Es una variable POR PROCESO. Persistida, apunta TODOS los procesos"
            Write-Output "  -- incluido el ejecutor armado del stack #1 -- al terminal y la"
            Write-Output "  cuenta del stack #2. Borrala:"
            Write-Output "    [Environment]::SetEnvironmentVariable('SENTINEL_MACHINE_PROFILE',`$null,'$scope')"
            $fatal = $true
        }
    }

    foreach ($scope in @("User", "Machine")) {
        $v = [Environment]::GetEnvironmentVariable("SUPERVISOR_MAX_SPREAD_OPEN", $scope)
        if ($v) {
            Write-Output "FATAL: SUPERVISOR_MAX_SPREAD_OPEN esta persistida en ambito $scope ('$v')."
            Write-Output "  Ese cap es de la maquina Capitaria (XAUUSD, spread minimo 0.50). En AVA"
            Write-Output "  el spread de GOLD es 0.73-0.80: un cap de 0.5 bloquea el 100% de las"
            Write-Output "  aperturas SIN UN SOLO ERROR EN LOS LOGS -- el sistema parece sano y no"
            Write-Output "  abre nada. El watchdog la limpia por proceso, pero persistida seguiria"
            Write-Output "  envenenando pytest y cualquier arranque manual. Borrala:"
            Write-Output "    [Environment]::SetEnvironmentVariable('SUPERVISOR_MAX_SPREAD_OPEN',`$null,'$scope')"
            $fatal = $true
        }
    }

    foreach ($name in @("SUPERVISOR_CONFIGS", "SUPERVISOR_SYMBOL", "SUPERVISOR_STALE_AUTORESTART")) {
        foreach ($scope in @("User", "Machine")) {
            $v = [Environment]::GetEnvironmentVariable($name, $scope)
            if ($v) {
                Write-Output "AVISO: $name persistida en ambito $scope ('$v')."
                Write-Output "  El watchdog la sobrescribe por proceso, asi que el stack no se ve"
                Write-Output "  afectado, pero puede falsear pytest. Mejor borrarla."
            }
        }
    }

    if ($fatal) {
        Write-Output ""
        Write-Output "ME NIEGO A CONTINUAR hasta que se borren las variables marcadas FATAL."
        Write-Output "Tras borrarlas, ABRE UNA CONSOLA NUEVA (los cambios no afectan a la actual)."
        exit 1
    }
    Write-Output "OK: ninguna variable toxica persistida."
}

# --------------------------------------------------------------------------
# Nunca dormir con corriente alterna. La pantalla puede apagarse (inofensivo);
# suspension e hibernacion PARAN la CPU y con ella el trading.
# --------------------------------------------------------------------------
function Set-NeverSleep {
    Write-Section "Energia: no dormir nunca con CA (powercfg)"
    powercfg /change standby-timeout-ac 0
    powercfg /change hibernate-timeout-ac 0
    Write-Output "standby-timeout-ac=0, hibernate-timeout-ac=0 (el apagado de pantalla se deja como este)."
}

# --------------------------------------------------------------------------
# Tarea programada del watchdog (idempotente: se borra y se vuelve a crear,
# asi un re-lanzamiento siempre refleja las rutas actuales).
# --------------------------------------------------------------------------
function Register-WatchdogTask {
    Write-Section "Programador de tareas: $TaskName"
    if (-not (Test-Path $WatchdogPs1)) {
        Write-Output "ERROR: no encuentro el watchdog en $WatchdogPs1."
        exit 1
    }

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
        Write-Output "La tarea ya existe -- la borro y la vuelvo a crear (idempotente)."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $psExe = (Get-Command powershell.exe).Source
    $argList = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WatchdogPs1`""
    $action = New-ScheduledTaskAction -Execute $psExe -Argument $argList -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
    # Como usuario interactivo: el watchdog necesita la sesion de escritorio
    # para ver y arrancar los terminal64.exe (MT5 tiene interfaz grafica; una
    # tarea sin sesion no puede mostrarla).
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
        -LogonType Interactive -RunLevel Highest

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Write-Output "Tarea '$TaskName' registrada (corre $WatchdogPs1 oculta al iniciar sesion, con reinicio ante fallo)."
    Write-Output "ExecutionTimeLimit=0 (sin limite): el watchdog es un bucle infinito y no debe caducar."
}

# --------------------------------------------------------------------------
Write-Section "SENTINEL -- autoarranque del equipo 3"
Write-Output "RepoRoot: $RepoRoot"

if ($TaskOnly -and $PowerOnly) {
    Write-Output "ERROR: -TaskOnly y -PowerOnly son mutuamente excluyentes."
    exit 1
}

Assert-Equipo3
Assert-NoToxicEnv

if ($PowerOnly) {
    Set-NeverSleep
} elseif ($TaskOnly) {
    Register-WatchdogTask
} else {
    Set-NeverSleep
    Register-WatchdogTask
}

Write-Section "RESUMEN"
Write-Output "HECHO en esta pasada:"
if (-not $TaskOnly)  { Write-Output "  - energia: suspension/hibernacion con CA desactivadas." }
if (-not $PowerOnly) { Write-Output "  - tarea:  '$TaskName' registrada (watchdog oculto al iniciar sesion)." }
Write-Output "  - NO se ha hecho setx de nada (a proposito: aqui el entorno va por proceso)."
Write-Output "  - NO se ha armado trading. Eso solo lo hace el supervisor tras pasar su preflight."
Write-Output ""
Write-Output "PENDIENTE A MANO (operador) -- ver docs\EQUIPO3-INSTALACION.md:"
Write-Output "  1. Abre los DOS terminales MT5 una vez a mano e inicia sesion en cada cuenta,"
Write-Output "     para que quede establecida la sesion. El watchdog sabe relanzarlos, pero el"
Write-Output "     primer login lo haces tu."
Write-Output "  2. Corre la verificacion de dos terminales antes de armar nada:"
Write-Output "         python -m scripts.live.verify_two_terminals"
Write-Output "  3. Para que la maquina se recupere sola de un apagon hace falta, fuera de"
Write-Output "     Windows: BIOS/UEFI -> 'Restore on AC Power Loss' = Power On, y un inicio de"
Write-Output "     sesion automatico (la tarea se dispara al iniciar sesion, no al arrancar,"
Write-Output "     porque MT5 necesita escritorio). Runbook paso 11."
Write-Output "  4. Arranca ya, sin reiniciar:"
Write-Output "         Start-ScheduledTask -TaskName $TaskName"
Write-Output "  5. Vigila:  Get-Content scripts\live\watchdog_equipo3.log -Wait -Tail 40"
Write-Output ""
Write-Output "OK."
