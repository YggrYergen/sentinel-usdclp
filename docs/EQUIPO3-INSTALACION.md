# Equipo 3 — instalación y puesta en marcha del runner oficial

> Windows 10 · rama `equipo3-runner` · 2026-09-24
> Sigue los pasos **en orden**. Cada uno termina con una comprobación; si esa
> comprobación no da lo que dice, para ahí y no sigas — casi todos los modos de
> fallo de este stack son silenciosos, y un paso mal dado no se nota hasta que
> llevas días sin abrir una sola posición.

---

## 0 · Qué vas a montar

El equipo 3 pasa a ser el **runner oficial**: el que opera de forma continua,
respetando los horarios y las reglas de cada estrategia. El equipo 1 (este,
`D:\FOREX`) queda **solo para desarrollo** y deja de operar.

Dos terminales MT5 conviviendo en la misma máquina, con un solo clon del repo:

| | **STACK #1** | **STACK #2** |
|---|---|---|
| Cuenta | AVA **101744074** (migrada del equipo 1) | Segunda demo AVA (login que aportas tú) |
| Terminal | `C:\MT5_AVA1\terminal64.exe` | `C:\MT5_AVA2\terminal64.exe` |
| Estrategias | `S6-K2P0-AVA` (magic 727010) + `SuperTrend-p14x3-M15-AVA` (magic 727020) | **ninguna, por ahora** |
| ¿Manda órdenes? | **Sí** — supervisor + ejecutor armado | **No** — ni supervisor ni ejecutor |
| Procesos | terminal + deals watcher + supervisor | terminal + deals watcher |
| Base de datos | `data/research.db` | `data/research_ava2.db` |
| Perfil | `scripts/live/machine_local.json` | `scripts/live/machine_local.ava2.json` |

La configuración de las estrategias del stack #1 es **idéntica** a la que corría
en el equipo 1: símbolo GOLD, lote 0.01, una posición por estrategia, ventana
R1/R2, sin cap estático de spread. No se ha tocado ni un parámetro. Lo único
nuevo es la infraestructura que las mantiene vivas.

El stack #2 es **solo infraestructura**: terminal conectado y su historial
capturándose a disco, listo para recibir estrategias cuando existan candidatos.
Hasta entonces no arma nada. Si su perfil no existe, el watchdog trabaja con el
stack #1 y ni se queja.

---

## 1 · Requisitos de la máquina

- Windows 10 **1809 o posterior** (requisito de Claude Code, paso 13).
  Compruébalo: `winver` → debe decir versión 1809 o superior.
- 8 GB de RAM o más recomendado (dos terminales MT5 + Python + dashboard).
  Claude Code por su parte pide 4 GB+.
- Conexión a internet estable. Esta máquina va a estar encendida siempre.
- Una cuenta de usuario Windows con permisos de administrador (hará falta para
  la configuración de energía y la tarea programada).

---

## 2 · Python 3.11

El equipo 1 corre **Python 3.11.9** y las dependencias están fijadas a las
versiones verificadas ahí. Usa 3.11, no 3.12 ni 3.13.

1. Descarga el instalador de Python 3.11 para Windows x64 desde
   <https://www.python.org/downloads/windows/>.
2. En el instalador **marca «Add python.exe to PATH»**.
3. Comprueba:

```powershell
python --version
```

Debe imprimir `Python 3.11.x`.

---

## 3 · Git for Windows

Necesario para clonar el repo, y además es lo que le da a Claude Code su
herramienta Bash (paso 13).

1. Descarga desde <https://git-scm.com/downloads/win> e instala con las
   opciones por defecto.
2. Comprueba:

```powershell
git --version
```

---

## 4 · Los DOS terminales MT5 🔴

**Este es el paso que más se tuerce.** MT5 **no abre dos instancias de la misma
instalación**: si instalas una sola vez y haces doble clic dos veces, la segunda
te trae al frente la primera. Hacen falta **dos instalaciones en carpetas
distintas**.

1. Descarga el instalador de MT5 de **Ava Trade** (el mismo de siempre).
2. Instálalo eligiendo como carpeta de destino:

   ```
   C:\MT5_AVA1
   ```

3. **Vuelve a lanzar el mismo instalador** y elige ahora:

   ```
   C:\MT5_AVA2
   ```

   Si el instalador no te deja elegir carpeta la segunda vez, la alternativa es
   copiar la carpeta entera:
   `Copy-Item -Recurse C:\MT5_AVA1 C:\MT5_AVA2`

4. Abre **`C:\MT5_AVA1\terminal64.exe`** e inicia sesión en la cuenta
   **101744074**, servidor `Ava-Demo 1-MT5`.
5. Abre **`C:\MT5_AVA2\terminal64.exe`** e inicia sesión en la **segunda demo
   AVA**.
6. En **cada** terminal: `Herramientas → Opciones → Asesores Expertos` →
   marca **«Permitir trading algorítmico»**. Sin esto el ejecutor no puede
   mandar órdenes.
7. En **cada** terminal, abre el símbolo **`GOLD`** en Observación de Mercado
   (AVA no tiene `XAUUSD`, se llama `GOLD`).

> **Por qué carpetas distintas y no `/portable`:** una instalación MT5 normal
> guarda sus datos en `%APPDATA%\MetaQuotes\Terminal\<hash>`, y ese hash se
> deriva de la **ruta de instalación**. Dos carpetas distintas ⇒ dos carpetas de
> datos independientes, automáticamente. El paso 9 te imprime el `data path` de
> cada terminal para que lo confirmes con tus propios ojos.

**Comprobación:** los dos terminales abiertos a la vez, cada uno con su cuenta
distinta en la esquina, y `GOLD` visible en ambos.

---

## 5 · Clonar el repo, rama `equipo3-runner`

```powershell
cd C:\
git clone --branch equipo3-runner --single-branch --depth 1 https://github.com/YggrYergen/sentinel-usdclp.git FOREX
cd C:\FOREX
git branch --show-current
```

Debe imprimir `equipo3-runner`.

> **Por qué así y no un `git clone` normal.** `equipo3-runner` es una rama
> **ligera y sin historia**: contiene todo el código, las pruebas y los datos de
> runtime necesarios para operar, pero no arrastra los 55 MB de
> `research/fases/`, los 24 MB de `docs/superpowers/` ni los 8 MB de
> `backups/`, que son artefactos de investigación y no hacen falta para correr.
> Son **~8 MB en vez de ~96 MB**.
>
> Los tres modificadores importan: `--single-branch` evita traerse las demás
> ramas, y `--depth 1` evita traerse la historia. Sin ellos, `git clone`
> descargaría los 96 MB de todos modos aunque la rama sea pequeña.
>
> Esta máquina **opera**, no investiga. Si algún día necesitas el historial
> completo aquí, `git remote set-branches origin '*'` y `git fetch --unshallow`
> lo traen todo.

> Puedes clonarlo en `D:\FOREX` si esa máquina tiene disco D — da igual. Nada
> del código de arranque tiene `D:\FOREX` incrustado: el watchdog y el script de
> autoarranque derivan todas sus rutas de su propia ubicación. Lo único con
> rutas absolutas son los perfiles del paso 6, que escribes tú.

---

## 6 · Dependencias y perfiles de máquina

### 6.1 Dependencias

```powershell
cd C:\FOREX
python -m pip install --upgrade pip
python -m pip install -r scripts\live\requirements-equipo3.txt
```

Comprueba lo único imprescindible:

```powershell
python -c "import MetaTrader5; print(MetaTrader5.__version__)"
```

Debe imprimir `5.0.5735`.

### 6.2 Perfil del STACK #1

Crea `scripts\live\machine_local.json` con exactamente esto (ajusta la ruta si
instalaste MT5 en otro sitio):

```json
{
  "terminal_path": "C:\\MT5_AVA1\\terminal64.exe",
  "portable": false,
  "demo_login": 101744074,
  "terminal_marker": "mt5_ava1"
}
```

### 6.3 Perfil del STACK #2 — **espera al paso 7**

Todavía no lo crees. El login de la segunda demo tiene que estar sancionado
primero, o el cargador lo rechazará (por diseño). Si creas este fichero antes de
tiempo, el watchdog registrará `perfil INVÁLIDO -> DESACTIVADO` y seguirá con el
stack #1 — molesto, pero inofensivo.

> 🔴 Las dos plantillas, con todas sus notas, están en
> `scripts\live\machine_local.equipo3.example.json`. Los perfiles reales están
> gitignoreados: son locales de esta máquina y no se suben nunca.

**Comprobación:**

```powershell
python -c "from sentinel_engine.live.machine_profile import load_profile; p=load_profile(); print(p)"
```

Debe imprimir el terminal `C:\MT5_AVA1\terminal64.exe` y `demo_login=101744074`.

---

## 7 · Sancionar el login de la segunda demo AVA 🔴

`guard_cuenta.SANCTIONED_DEMO_LOGINS` es un `frozenset` **escrito a mano en el
código a propósito**: el guard no debe depender de ninguna configuración mutable
para saber qué cuentas son operables. Un `machine_local.json` solo puede
*elegir* dentro de ese conjunto, nunca *ampliarlo*. Por eso añadir la segunda
cuenta es un cambio de código, no de configuración — igual que lo fue D-62 para
la 101744074.

**Esto requiere tu autorización explícita, exactamente como en D-62.** Cuando
tengas el login:

1. Edita `sentinel_engine/live/guard_cuenta.py` y añade la entrada al conjunto:

```python
SANCTIONED_DEMO_LOGINS = frozenset({
    2883015767,  # Machine 1 -- portable install D:\FOREX\MT5_Portable
    2883016567,  # Machine "TOMACHINE" -- standard Capitaria install, 30M CLP demo
    101744074,   # AVA demo ... (D-62)
    XXXXXXXXX,   # <-- 2ª demo AVA (equipo 3, MT5 #2). Campo de pruebas: HOY solo
                 # monitorización (terminal + deals watcher), sin ejecutor y sin
                 # supervisor. Autorizada por el usuario el <FECHA>.
})
```

2. Añade la fila correspondiente a `CUENTAS.md` (la única fuente de verdad de
   cuentas). Ese fichero está gitignoreado: se edita a mano en cada máquina.
3. **Ahora sí**, crea `scripts\live\machine_local.ava2.json`:

```json
{
  "terminal_path": "C:\\MT5_AVA2\\terminal64.exe",
  "portable": false,
  "demo_login": XXXXXXXXX,
  "terminal_marker": "mt5_ava2"
}
```

4. Comprueba que el cargador lo acepta:

```powershell
$env:SENTINEL_MACHINE_PROFILE = "scripts\live\machine_local.ava2.json"
python -c "from sentinel_engine.live.machine_profile import load_profile; print(load_profile())"
Remove-Item Env:\SENTINEL_MACHINE_PROFILE
```

> 🔴 **Nunca hagas `setx` de `SENTINEL_MACHINE_PROFILE`.** Es una variable
> **por proceso**. Persistida, apuntaría *todos* los procesos de la máquina —
> incluido el ejecutor armado del stack #1 — al terminal y la cuenta
> equivocados. El watchdog la inyecta solo en el watcher del stack #2, y tanto
> él como el script de autoarranque **se niegan a correr** si la encuentran
> persistida. La línea de arriba la define solo para esa consola; el
> `Remove-Item` la retira.

**Si todavía no tienes el login:** salta este paso. Todo lo demás funciona; el
watchdog registrará `stack #2: sin perfil -- DESACTIVADO` y cuidará del stack #1
con normalidad. Vuelve aquí cuando la tengas.

---

## 8 · Verificar que los dos terminales se distinguen 🔴

Este es el riesgo técnico que había que despejar antes que ningún otro: todo el
diseño de un solo clon depende de que `mt5.initialize(path=...)` se enganche
**a ese terminal y no al otro**. Con un solo terminal abierto eso nunca se había
puesto a prueba, y ya hubo un incidente (2026-07-24) en que un desajuste del
flag `/portable` hizo que `initialize()` levantara un terminal fantasma.

Con **los dos terminales abiertos y logueados**:

```powershell
cd C:\FOREX
python -m scripts.live.verify_two_terminals
```

El script es **estrictamente de solo lectura**: no manda órdenes, no escribe en
ninguna base, no arranca ni cierra terminales. Comprueba cinco cosas:

1. que cada exe existe y tiene un proceso corriendo **desde esa ruta exacta**;
2. que `initialize(path=...)` devuelve, en cada caso, **el login que dice su
   perfil**;
3. que el símbolo `GOLD` existe en ambos, con su spread y sus dígitos;
4. que **no apareció ningún terminal nuevo** durante la prueba (el fantasma);
5. que los dos perfiles dan **logins distintos** — si dan el mismo,
   `initialize()` está ignorando `path=` y el diseño de un solo clon no sirve.

**Debe terminar con `RESULTADO: OK` y salir con código 0.**

Si dice `RESULTADO: NO OK`:
- *«login aún no está sancionado» para el stack #2* → es lo esperado si te
  saltaste el paso 7. Todo lo demás debe estar OK.
- *«los DOS perfiles devolvieron el mismo login»* → **para**. Avísame: hay que
  pasar al plan B del spec (dos clones del repo, uno por stack).
- *«initialize() levantó terminal(es) nuevo(s)»* → casi siempre es el flag
  `portable` mal puesto en un perfil. Si arrancas el terminal sin `/portable`,
  el perfil debe decir `"portable": false`.

---

## 9 · Pasar las pruebas

```powershell
cd C:\FOREX
python -m pytest tests\live\ -q
```

Deben pasar todas. Dos avisos sobre el resultado esperado:

- En el equipo 1, `tests/live/test_news_calendar.py` falla **porque allí se
  borró `data/live/news_calendar.csv` del árbol de trabajo**. En un clon nuevo
  ese fichero llega intacto desde git, así que aquí **debe pasar**. Si falla,
  comprueba que existe `data\live\news_calendar.csv`.
- Si ves fallos en pruebas del supervisor, revisa el paso 12.1: casi siempre son
  variables `SUPERVISOR_*` persistidas contaminando el entorno de pytest.

No corras la suite completa (`python -m pytest`) sin necesidad: hay pruebas
marcadas `slow` que reproducen datos reales y tardan.

---

## 10 · 🔴 CORTE DE MIGRACIÓN — parar el equipo 1

**No hagas esto hasta que los pasos 1–9 estén verdes.** Y hazlo **con el mercado
cerrado** (fin de semana), para no cortar por la mitad una posición abierta.

La cuenta 101744074 es **una sola cuenta en el bróker**. Si los dos equipos
corren armados a la vez, sus dos reconciliadores se pisan: cada uno ve las
posiciones del otro como sobrantes e intenta cerrarlas. **Nunca los dos a la
vez.**

### En el EQUIPO 1 (`D:\FOREX`), por este orden:

1. **Cierra o deja cerrar las posiciones abiertas.** Comprueba que no queda
   ninguna con magic 727010 / 727020.
2. Activa el kill-switch:
   ```powershell
   cd D:\FOREX
   .\PAUSAR_TRADING.bat
   ```
3. Para el watchdog y sus hijos:
   ```powershell
   Stop-ScheduledTask -TaskName SENTINEL_Watchdog_Machine1 -ErrorAction SilentlyContinue
   Disable-ScheduledTask -TaskName SENTINEL_Watchdog_Machine1 -ErrorAction SilentlyContinue
   Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'supervisor_live|run_live_20|run_deals_watcher' } |
       ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
   ```
4. Confirma que no queda nada vivo:
   ```powershell
   Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'supervisor_live|run_live_20' } | Measure-Object
   ```
   Debe dar `Count: 0`.
5. **Cierra la sesión de la cuenta 101744074 en el MT5 del equipo 1**
   (`D:\FOREX\MT5_Tester`), o cierra ese terminal. Así, si algo se reanimara,
   el guard de cuenta lo detendría en seco.

### Guarda el historial anterior

El historial de la cuenta en el equipo 1 vive en `D:\FOREX\data\research.db`.
Cópialo a una unidad externa o a la nube antes de nada: es la serie histórica de
la comparación Capitaria↔AVA. El equipo 3 empieza una base nueva; los deals
viejos siguen en el bróker y el watcher los recuperará al arrancar, pero no
dependas de eso.

### Solo entonces, en el EQUIPO 3

Sigue al paso 11.

---

## 11 · Autoarranque, energía y auto-sanado

Desde un **PowerShell como Administrador**:

```powershell
cd C:\FOREX
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\live\setup_autostart_equipo3.ps1
```

Esto hace tres cosas y **ninguna de ellas arma trading**:

1. Registra la tarea `SENTINEL_Watchdog_Equipo3`, que corre
   `scripts\live\watchdog_equipo3.ps1` oculta al iniciar sesión, con reinicio
   ante fallo y sin límite de tiempo de ejecución.
2. Desactiva suspensión e hibernación con corriente alterna (una máquina dormida
   deja de operar). El apagado de pantalla se deja como esté: es inofensivo.
3. **Se niega a continuar** si encuentra variables de entorno persistidas que
   sabotearían el stack en silencio — ver 11.1.

El script **no hace `setx` de nada**, a diferencia del de la máquina 1. Es
deliberado: aquí conviven dos stacks y el entorno va inyectado por proceso desde
el watchdog.

### 11.1 · Las variables que matan en silencio

El script se niega a correr si encuentra persistida cualquiera de estas:

- **`SENTINEL_MACHINE_PROFILE`** → apuntaría el ejecutor armado al terminal y la
  cuenta del stack #2.
- **`SUPERVISOR_MAX_SPREAD_OPEN`** → ese cap (0.5) es de la máquina Capitaria,
  donde el spread mínimo de XAUUSD es 0.50. En AVA el spread de GOLD es
  **0.73–0.80**: un cap de 0.5 **bloquea el 100 % de las aperturas sin un solo
  error en los logs**. El sistema parece perfectamente sano y no abre nada
  nunca. Es el fallo más caro de diagnosticar de todo el stack.

Para borrarlas:

```powershell
[Environment]::SetEnvironmentVariable('SENTINEL_MACHINE_PROFILE',$null,'User')
[Environment]::SetEnvironmentVariable('SUPERVISOR_MAX_SPREAD_OPEN',$null,'User')
```

Y **abre una consola nueva** — los cambios no afectan a la que ya está abierta.

### 11.2 · Arrancar ya, sin reiniciar

```powershell
Start-ScheduledTask -TaskName SENTINEL_Watchdog_Equipo3
Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log -Wait -Tail 40
```

En el log debes ver, en este orden:

```
watchdog_equipo3.ps1 ARRANCADO (PID ...)
stack #1: terminal=C:\MT5_AVA1\terminal64.exe portable=False login=101744074
stack #2: terminal=C:\MT5_AVA2\terminal64.exe portable=False login=...
stack #1 : guard OK -- DEMO 101744074 confirmada.
stack #1 : watcher relanzado, PID ...
stack #1 : supervisor relanzado, PID ...
stack #2 : guard OK -- DEMO ... confirmada.
stack #2 : watcher relanzado, PID ...
OK: watcher1=True supervisor=True watcher2=True stack2=True STOP=False
```

(Si te saltaste el paso 7 verás `stack #2: sin perfil -- DESACTIVADO` y
`watcher2=False stack2=False`. Es correcto.)

Y quita el kill-switch si quedó puesto:

```powershell
cd C:\FOREX
.\REANUDAR_TRADING.bat
```

### 11.3 · Qué sana el watchdog, y qué no

| Cae… | ¿Se recupera solo? | Cómo |
|---|---|---|
| Un terminal MT5 | **Sí** | Detección **por ruta** (no por nombre de proceso) y `Start-Process`. Este es el arreglo clave frente al watchdog de la máquina 1, que con dos terminales nunca habría relanzado el caído. |
| El deals watcher (cualquiera) | Sí | Relanzado en ≤20 s |
| El supervisor | Sí | Relanzado, previa **siega de ejecutores huérfanos** (en Windows matar al padre no mata al hijo, así que sin esto habría dos ejecutores armados → órdenes dobles) |
| El ejecutor armado | Sí | Es hijo del supervisor: preflight + backoff exponencial |
| El ejecutor se queda «rancio» | Sí | `SUPERVISOR_STALE_AUTORESTART=1`: si el audit log lleva >5 min sin tocarse y lo confirma una segunda comprobación, lo recicla |
| El dashboard (8501) | Sí | Relanzado si nadie escucha en el puerto |
| El propio watchdog | Sí | La tarea programada lo reinicia (hasta 999 veces, cada minuto) |
| Cierre de sesión de Windows | Sí | La tarea se dispara al iniciar sesión |
| **La máquina apagada** | **No, sin BIOS** | Ningún software enciende una máquina apagada → paso 12 |
| La ingesta de barras | **No está vigilada** | Ver «Puntos abiertos» al final |

---

## 12 · Recuperarse de un apagón

La tarea se dispara **al iniciar sesión**, no al arrancar la máquina. Tiene que
ser así: MT5 es una aplicación gráfica y necesita una sesión de escritorio; una
tarea «corre esté o no el usuario conectado» no puede mostrarla.

Así que hacen falta dos piezas **fuera de Windows y fuera de este repo**:

1. **BIOS/UEFI → «Restore on AC Power Loss» = Power On.**
   Reinicia, entra en la BIOS (normalmente `Supr` o `F2`), busca esa opción en
   la sección de gestión de energía y ponla en *Power On*. Así, al volver la
   corriente, la máquina arranca sola. Algunas placas lo llaman *AC Back*, *After
   Power Loss* o *Power On After Power Failure*.

2. **Inicio de sesión automático de Windows**, para que la tarea se dispare sin
   que nadie escriba la contraseña:

   ```powershell
   netplwiz
   ```

   Desmarca «Los usuarios deben escribir su nombre y contraseña…», acepta, y
   escribe la contraseña cuando la pida.

   > **Considera el coste de seguridad antes de hacerlo:** cualquiera con acceso
   > físico a la máquina entra directo al escritorio. Es tu decisión, y depende
   > de dónde vaya a estar el equipo. Si está en un sitio no controlado, es mejor
   > renunciar al arranque automático y levantar la sesión a mano tras un
   > apagón.

3. **Comprobación:** reinicia la máquina y no toques nada. A los pocos minutos:

   ```powershell
   Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log -Tail 20
   ```

   Deben aparecer líneas nuevas con la hora del arranque.

---

## 13 · Instalar Claude Code en Windows 10

**Claude Code sí corre en Windows 10** — no hace falta Codex ni WSL. Los
requisitos oficiales son, literalmente:

> - **Operating system**: macOS 13.0+ · **Windows 10 1809+ or Windows Server
>   2019+** · Ubuntu 20.04+ · Debian 10+ · Alpine Linux 3.19+
> - **Hardware**: 4 GB+ RAM, x64 or ARM64 processor
> - **Network**: internet connection required
> - **Shell**: Bash, Zsh, PowerShell, or CMD

*(fuente: <https://code.claude.com/docs/en/setup>, consultada el 2026-09-24)*

### 13.1 · Instalar

**No hace falta ejecutar como Administrador.** Abre **PowerShell** y:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Si prefieres CMD, el comando equivalente es:

```batch
curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
```

> Cómo saber en cuál estás: el prompt pone `PS C:\...` en PowerShell y `C:\...`
> sin el `PS` en CMD. Si ves `The token '&&' is not a valid statement separator`
> estás en PowerShell ejecutando el comando de CMD; si ves
> `'irm' is not recognized` estás en CMD ejecutando el de PowerShell.

La instalación nativa **se actualiza sola en segundo plano**.

*Alternativa con WinGet* (`winget install Anthropic.ClaudeCode`): funciona, pero
**no se autoactualiza** — tendrías que correr `winget upgrade
Anthropic.ClaudeCode` de vez en cuando. En una máquina desatendida prefiere el
instalador nativo.

### 13.2 · Git Bash (recomendado)

Ya lo instalaste en el paso 3. Con Git for Windows presente, Claude Code usa
**Git Bash** para su herramienta Bash; sin él, usa la herramienta PowerShell.
Como este repo tiene scripts de ambos tipos, conviene tenerlo.

Si Claude Code no encuentra Git Bash, indícale la ruta en tu `settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"
  }
}
```

### 13.3 · Comprobar la instalación

```powershell
claude --version
```

Una instalación correcta imprime un número de versión, del estilo
`2.1.211 (Claude Code)`.

Y para un diagnóstico más completo, que **no arranca ninguna sesión**:

```powershell
claude doctor
```

Imprime el estado de la instalación, errores de validación de los ficheros de
configuración y avisos con sus arreglos sugeridos.

### 13.4 · Autenticarse

> Claude Code requiere una cuenta **Pro, Max, Team, Enterprise o Console**.
> **El plan gratuito de claude.ai no incluye Claude Code.**

Ejecuta `claude` y sigue las indicaciones del navegador.

### 13.5 · Abrirlo en el repo

```powershell
cd C:\FOREX
claude
```

**Comprobación final:** dentro de la sesión, pide algo trivial y verificable —
por ejemplo «lee `scripts\live\watchdog_equipo3.ps1` y dime cuántos stacks
vigila» (la respuesta es dos). Si contesta con el contenido real del fichero, la
instalación está operativa.

---

## 14 · Qué mirar a diario

```powershell
# el watchdog, en vivo
Get-Content C:\FOREX\scripts\live\watchdog_equipo3.log -Wait -Tail 40

# las decisiones del ejecutor armado
Get-Content C:\FOREX\scripts\live\run_live_20.audit.log -Wait -Tail 40

# los deals que se están capturando
Get-Content C:\FOREX\scripts\live\deals_watcher_local.log -Tail 20   # stack #1
Get-Content C:\FOREX\scripts\live\deals_watcher_ava2.log  -Tail 20   # stack #2

# dashboard
start http://127.0.0.1:8501
```

Tres señales de alarma que conviene reconocer:

- **`run_live_20.audit.log` sin líneas nuevas en más de 5 minutos** con el
  mercado abierto. El supervisor debería reciclarlo solo; si no lo hace, mira el
  log del watchdog.
- **`deals_seen=0` sostenido** en el log del watcher mientras hay operaciones.
  Es un incidente de pérdida de datos: el historial vivo tiene que estar
  cayendo a disco siempre.
- **Cero aperturas durante todo un día** con el mercado abierto. Revisa primero
  el paso 11.1 (el cap de spread heredado) y después los
  `SPREAD_GATE_SKIP` / `TIME_GATE_SKIP` / `window-gate` del audit log.

---

## 15 · Cómo parar

```powershell
# pausar el trading dejando todo vivo (kill-switch por fichero STOP;
# el supervisor sigue en pie y se niega a armar mientras exista)
cd C:\FOREX ; .\PAUSAR_TRADING.bat

# reanudar
cd C:\FOREX ; .\REANUDAR_TRADING.bat

# parar el stack entero
Stop-ScheduledTask -TaskName SENTINEL_Watchdog_Equipo3
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'supervisor_live|run_live_20|run_deals_watcher' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

---

## Puntos abiertos — conocidos, no resueltos

Para que no aparezcan como sorpresas más adelante:

1. **La ingesta de barras no está vigilada.** `run_bars_ingester.py` tiene un
   `SYMBOL_MAP` de Capitaria (`XAUUSD`, `NQ100`, `USDCLP`…) que **no contiene
   `GOLD`**, así que en AVA no ingestaría nada. Meterlo en el watchdog solo
   conseguiría que lo relanzara en bucle. Queda fuera a propósito, hasta decidir
   qué símbolos debe seguir en AVA.

2. **D-39 sigue vigente y viajará al equipo 3.** El ejecutor abre a precio de
   mercado pero hereda el stop ya arrastrado del simulador; el 21-09-2026 eso
   produjo 1.016 `OPEN_SKIPPED_SL_CROSSED` en la cuenta AVA, y los
   `SL_CLAMPED OPEN` que sí salen nacen con el stop a la distancia mínima legal
   del bróker. No se arregla aquí porque este despliegue es una **migración a
   configuración idéntica**: cambiarlo rompería la comparabilidad de la serie.
   Está diagnosticado y pendiente de decisión aparte.

3. **El calendario de ventanas R2 extrapola sin marcarlo.** Pasado el
   2026-08-11 sigue generando ventanas indefinidamente sin ninguna señal de que
   está extrapolando.

4. **Esta rama no trae el material de investigación.** `equipo3-runner` excluye
   `research/`, `docs/superpowers/` (salvo el spec de este despliegue),
   `backups/` y `data/analysis/`. **Una excepción deliberada:**
   `research/fases/F0-preparacion/04-resultados/T0.13-ventana-ny/` sí viaja,
   porque `sentinel_engine/live/ava_window_gate.py` lee de ahí
   `calendario-ventana.json` en cada decisión de apertura, y ese gate **falla
   duro**: sin el fichero, las dos estrategias AVA dejarían de abrir. Si algún
   día mueves o regeneras ese calendario, acuérdate de esta dependencia.

5. **El stack #2 no tiene estrategias.** Cuando haya candidatos habrá que
   decidir cómo armarlo: hoy no hay ejecutor ni supervisor para él, y darle uno
   exige el aislamiento por instancia que el spec describe como plan B
   (`docs/superpowers/specs/2026-09-24-equipo3-runner-oficial-design.md`).
