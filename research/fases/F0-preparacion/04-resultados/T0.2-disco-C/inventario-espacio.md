# T0.2 — Inventario de espacio en disco C:

```
run_id: F0-INFRA-T0.2
etapa: F0
area: INFRA
substrate_id: n/a
generador: agent:sonnet5-investigador
git_sha: b042f5c
timestamp: 2026-08-10 19:42:18 -04:00 (hora local del host = hora de servidor, UTC-4; no convertida)
```

Rol: INVESTIGADOR REPORT-ONLY. Este documento es un inventario de hechos (rutas, tamaños,
fechas, identificación factual de qué es cada ruta). No contiene recomendaciones ni juicios sobre
qué borrar. Ningún comando de borrado fue ejecutado (D-04).

---

## 1. Estado de los discos

Comando: `Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:' OR DeviceID='D:'"`

| Disco | Tamaño total | Usado | Libre | % libre |
|---|---|---|---|---|
| C: | 451,37 GB | 429,18 GB | 22,19 GB | 4,92 % |
| D: | 465,75 GB | 311,87 GB | 153,87 GB | 33,04 % |

D: se reporta solo como referencia (fuera de alcance de la medición detallada, por instrucción del
brief).

---

## 2. Tabla principal — candidatos de tamaño relevante, ordenados por tamaño descendente

Metodología: medición por directorio (no recursiva sobre todo el perfil), de arriba hacia abajo,
en llamadas cortas. Tamaños de directorios grandes obtenidos con
`Get-ChildItem -Recurse -File | Measure-Object -Sum Length`; para las ramas de `C:\Windows` con
volumen de ficheros muy alto se usó `robocopy <ruta> NULL /L /S /NJH /NDL /NFL /BYTES` (recorrido
en seco, sin copiar nada, más rápido que el cmdlet para árboles de cientos de miles de ficheros).

**Nota sobre "Último acceso":** el propio acto de medir (`Get-ChildItem -Recurse`, `robocopy /L`)
actualiza el `LastAccessTime` de la carpeta contenedora porque NTFS tiene las actualizaciones de
hora de acceso habilitadas en esta máquina (`fsutil behavior query disablelastaccess` → valor 2,
habilitadas). Es decir: la columna "Último acceso" de las carpetas medidas en esta sesión refleja
**el instante de esta medición, no un uso real anterior**, y por tanto no es fiable como señal de
"hace cuánto no se usa esto". Se reporta igualmente (dato factual), marcada con la nota.

Umbral de inclusión en la tabla: ≥ 0,5 GB. Ítems menores se agregan en la sección de categorías
(§3) sin fila individual.

| Ruta | Tamaño | Última modificación | Último acceso | Qué es | ⚠️ No borrar |
|---|---|---|---|---|---|
| `C:\Users\tomas\Downloads` | 56,26 GB | 08/07/2026 14:50 | *(ver nota — refleja esta medición)* | Carpeta de descargas del usuario: vídeos/torrents (varias películas .mkv y carpetas de release, ~50 GB), un par de .zip, un instalador NinjaTrader.msi, PDFs sueltos | |
| `C:\Windows\Installer` | 38,12 GB (40.933.513.481 bytes) | 09/08/2026 22:40 | *(ver nota)* | Caché de Windows Installer: `$PatchCache$` + 532 carpetas GUID de paquetes MSI/MSP instalados; incluye 2 carpetas `MSI####.tmp-` (patrón de carpeta temporal de instalador sin limpiar) | ⚠️ sistema — desinstalar programas puede depender de estos ficheros para reparar/desinstalar |
| `C:\Program Files\Adobe` | 25,59 GB | 24/03/2026 16:31 | *(ver nota)* | Programas instalados: Acrobat DC, Creative Cloud + Experience, Illustrator 2026, InDesign 2025/2026, Media Encoder 2025, Photoshop 2026, Premiere Pro 2025, carpeta `Common` | ⚠️ software instalado en uso |
| `C:\Windows\WinSxS` | 22,42 GB (24.077.054.862 bytes) | 08/08/2026 17:59 | *(ver nota)* | Windows Component Store (almacén de componentes del sistema operativo, versiones side-by-side) | ⚠️ sistema operativo |
| `C:\Users\tomas\AppData\Local\Docker` | 22,01 GB | 11/08/2025 21:36 | *(ver nota)* | Datos de Docker Desktop; dominado por `wsl\disk\docker_data.vhdx` (22.384 MB, disco virtual WSL2 de Docker) y `wsl\main\ext4.vhdx` (115 MB) | ⚠️ datos de programa activo (contenedores/imágenes Docker) |
| `C:\Users\tomas\AppData\Local\Packages` | 21,49 GB | 04/08/2026 03:42 | *(ver nota)* | Datos de aplicaciones UWP/Store (sandboxed por paquete) | |
| `C:\Program Files (x86)\Steam` | 12,19 GB | 04/08/2026 03:59 | *(ver nota)* | Cliente Steam + datos de juegos instalados | |
| `C:\Users\tomas\.android` | 12,06 GB | 12/03/2025 20:32 | *(ver nota)* | Datos de Android SDK / emulador (carpeta de usuario `~/.android`) | |
| `C:\Windows\System32` | 11,44 GB (12.277.773.294 bytes) | 09/08/2026 22:47 | *(ver nota)* | Binarios y componentes centrales del sistema operativo | ⚠️ sistema operativo |
| `C:\Users\tomas\AppData\Local\wsl` | 11,12 GB | 11/08/2025 21:14 | *(ver nota)* | Datos de distribución(es) WSL (distinta de la carpeta `wsl` dentro de Docker) | ⚠️ datos de programa (WSL) si hay distros activas |
| `C:\Users\tomas\AppData\Local\npm-cache` | 9,25 GB | 12/03/2025 20:23 | *(ver nota)* | Caché de paquetes npm | |
| `C:\Users\tomas\AppData\Local\Android` | 8,83 GB | 20/03/2025 18:59 | *(ver nota)* | Caché/datos de Android Studio / SDK Manager (AppData\Local, distinto de `.android`) | |
| `C:\Users\tomas\AppData\Local\Google` | 8,04 GB | 18/04/2026 09:18 | *(ver nota)* | Datos/caché de navegador Google Chrome | |
| `C:\adobeTemp` | 6,85 GB | 08/03/2026 21:32 | *(ver nota)* | Carpetas temporales de Adobe (5 carpetas `ETR*.tmp`) en la raíz de C: | |
| `C:\Program Files\Common Files` | 6,06 GB | 07/07/2026 16:42 | *(ver nota)* | Ficheros compartidos entre programas instalados (Program Files) | ⚠️ compartido entre programas instalados |
| `C:\Users\tomas\.gemini` | 5,73 GB | 12/07/2025 23:05 | *(ver nota)* | Datos/caché de la herramienta CLI Gemini (carpeta de usuario `~/.gemini`) | |
| `C:\Program Files\Microsoft Office` | 5,14 GB | 09/08/2026 19:25 | *(ver nota)* | Programa instalado: Microsoft Office | ⚠️ software instalado en uso |
| `C:\Program Files\Microsoft Visual Studio` | 5,24 GB | 21/03/2025 12:58 | *(ver nota)* | Programa instalado: Visual Studio | ⚠️ software instalado |
| `C:\eSupport` | 5,03 GB | 21/07/2024 02:06 | *(ver nota)* | Carpeta `eDriver` — paquete de diagnóstico/drivers de fabricante (eSupport) | |
| `C:\Users\tomas\AppData\Local\Temp` | 4,76 GB | 10/08/2026 19:41 | *(ver nota)* | Carpeta Temp de usuario de Windows (`%LOCALAPPDATA%\Temp`) | |
| `C:\Windows\assembly` | 3,33 GB (3.571.342.146 bytes) | 04/08/2026 22:55 | *(ver nota)* | Global Assembly Cache de .NET Framework | ⚠️ sistema / .NET Framework |
| `C:\Program Files\Docker` | 3,18 GB | 11/08/2025 21:27 | *(ver nota)* | Programa instalado: Docker Desktop (binarios, no los datos/imágenes) | ⚠️ software instalado en uso |
| `C:\Users\tomas\userteemp` | 2,97 GB | 10/03/2026 13:51 | *(ver nota)* | Carpeta de nombre no estándar en el perfil del usuario; contenido no auditado en detalle (fuera de alcance de identificación exhaustiva) | |
| `C:\Users\tomas\AppData\LocalLow` | 2,73 GB | 04/08/2026 03:44 | *(ver nota)* | Datos de aplicaciones de baja integridad (AppData\LocalLow) | |
| `C:\ProgramData\Microsoft` | 2,69 GB | 04/08/2026 03:41 | *(ver nota)* | Datos compartidos de componentes Microsoft en ProgramData | ⚠️ datos de programa del sistema |
| `C:\Program Files\Android` | 2,85 GB | 20/03/2025 18:58 | *(ver nota)* | Programa instalado: Android Studio / herramientas Android | ⚠️ software instalado |
| `C:\Users\tomas\curseforge` | 2,48 GB | 04/08/2026 04:05 | *(ver nota)* | Datos de CurseForge (gestor de mods de Minecraft) | |
| `C:\Users\tomas\userteemp - backup` | 2,39 GB | 27/01/2026 12:00 | *(ver nota)* | Copia/backup de la carpeta anterior, nombre no estándar | |
| `C:\Users\tomas\.gradle` | 2,43 GB | 21/03/2025 17:39 | *(ver nota)* | Caché de build de Gradle | |
| `C:\Users\tomas\AppData\Local\uv` | 2,42 GB | 11/08/2025 20:56 | *(ver nota)* | Caché del gestor de paquetes Python `uv` | |
| `C:\Program Files (x86)\Windows Kits` | 2,25 GB | 21/03/2025 13:03 | *(ver nota)* | Windows SDK (Windows Kits) | ⚠️ software/SDK instalado |
| `C:\Users\tomas\.cache` | 2,12 GB | 01/08/2026 05:33 | *(ver nota)* | Caché genérica de herramientas de usuario (convención `~/.cache`) | |
| `C:\Users\tomas\AppData\Local\star citizen` | 2,68 GB | (no capturada individualmente) | — | Datos/caché del juego Star Citizen | |
| `C:\Users\tomas\Documents` | 0,79 GB | (ver §Users\tomas) | — | Documentos de usuario; incluye proyecto `porta` con `node_modules` (0,19 GB) | |
| `C:\Users\tomas\.vscode` | 0,82 GB | 21/07/2024 01:24 | *(ver nota)* | Extensiones/caché de Visual Studio Code | |
| `C:\Users\tomas\Python Scripts` | 0,88 GB | — | — | Carpeta de proyecto de usuario (scripts Python) | |
| `C:\Users\tomas\MedicIA` | 0,97 GB | — | — | Carpeta de proyecto de usuario `MedicIA/synapse`; incluye `node_modules` (0,67 GB) y subcarpetas de build `.next`/`.open-next` | |
| `C:\ProgramData\Package Cache` | 0,98 GB | — | — | Caché de instaladores/bootstrappers (Visual Studio / .NET / etc.) | |
| `C:\Users\tomas\AppData\Local\ms-playwright` | 1,19 GB | — | — | Navegadores descargados por Playwright (testing) | |
| `C:\Users\tomas\AppData\Local\Discord` | 1,12 GB | — | — | Datos/actualizaciones de la app Discord | |
| `C:\Users\tomas\AppData\Local\Programs` | 5,19 GB | — | — | Programas instalados a nivel de usuario (Electron apps, VS Code, etc. — no desglosado por app) | |
| `C:\Users\tomas\AppData\Roaming` | 18,14 GB (total, no desglosado por subcarpeta) | 04/08/2026 03:59 | *(ver nota)* | Datos de aplicaciones en `%APPDATA%` (perfiles de programas: navegadores, clientes de chat, editores, etc.) | |

**Ficheros de sistema en raíz de C:** (no son directorios, tamaño fijo reportado por el propio SO):

| Ruta | Tamaño | Última modificación | Qué es | ⚠️ No borrar |
|---|---|---|---|---|
| `C:\hiberfil.sys` | 6,29 GB (6442,38 MB) | 09/08/2026 22:39 | Fichero de hibernación de Windows | ⚠️ sistema |
| `C:\pagefile.sys` | 3,69 GB (3773,40 MB) | 10/08/2026 19:18 | Fichero de paginación / memoria virtual | ⚠️ sistema |
| `C:\swapfile.sys` | 0,016 GB (16 MB) | 09/08/2026 22:40 | Fichero de intercambio de apps UWP | ⚠️ sistema |

---

## 3. Agrupación por categoría (con subtotal)

Los subtotales usan las cifras medidas arriba; los ítems por debajo del umbral de 0,5 GB de la
tabla principal se incluyen aquí agregados cuando se identificaron en el barrido, bajo "(+ menores
no listados individualmente)".

### Sistema — subtotal ≈ 79,4 GB
- `C:\Windows\WinSxS` 22,42 GB
- `C:\Windows\System32` 11,44 GB
- `C:\Windows\assembly` 3,33 GB
- `C:\Windows\servicing` 0,58 GB
- `C:\Windows\Logs` 0,24 GB
- `C:\Windows\SoftwareDistribution` 0,24 GB
- `C:\Windows\Panther` 0,0004 GB
- `C:\hiberfil.sys` 6,29 GB
- `C:\pagefile.sys` 3,69 GB
- `C:\swapfile.sys` 0,016 GB
- `C:\ProgramData\Microsoft` 2,69 GB
- `C:\$SysReset` 0,03 GB
- `C:\Windows\Installer` 38,12 GB *(clasificado también como "instaladores", ver abajo; no se suma dos veces al total del programa — se lista en ambas categorías porque es simultáneamente caché de instalador y dependencia del sistema de gestión de paquetes de Windows)*

### Instaladores — subtotal ≈ 39,1 GB
- `C:\Windows\Installer` 38,12 GB (incl. `$PatchCache$` y 2 carpetas `MSI*.tmp-` de aspecto huérfano)
- `C:\ProgramData\Package Cache` 0,98 GB

### Software instalado (Program Files / Program Files x86) — subtotal ≈ 77,05 GB (total de ambas carpetas, ver §4)
- `C:\Program Files\Adobe` 25,59 GB
- `C:\Program Files\Common Files` 6,06 GB
- `C:\Program Files\Microsoft Visual Studio` 5,24 GB
- `C:\Program Files\Microsoft Office` 5,14 GB
- `C:\Program Files\Docker` 3,18 GB
- `C:\Program Files\Android` 2,85 GB
- `C:\Program Files (x86)\Steam` 12,19 GB
- `C:\Program Files (x86)\Windows Kits` 2,25 GB
- (+ resto de subcarpetas menores no listadas individualmente — ver §4 para el desglose completo medido)

### Cachés (gestores de paquetes / build / navegador) — subtotal ≈ 41,4 GB
- `C:\Users\tomas\AppData\Local\npm-cache` 9,25 GB
- `C:\Users\tomas\AppData\Local\Google` (Chrome) 8,04 GB
- `C:\Users\tomas\.gemini` 5,73 GB
- `C:\Users\tomas\.gradle` 2,43 GB
- `C:\Users\tomas\AppData\Local\uv` 2,42 GB
- `C:\Users\tomas\.cache` 2,12 GB
- `C:\Users\tomas\AppData\Local\Android` 8,83 GB
- `C:\Users\tomas\AppData\Local\ms-playwright` 1,19 GB
- `C:\Users\tomas\AppData\Local\pip` 0,74 GB
- `C:\Users\tomas\AppData\Local\pnpm` 0,56 GB
- `C:\Users\tomas\AppData\Local\pnpm-cache` 0,15 GB
- `C:\Users\tomas\AppData\Local\ms-playwright-go` 0,18 GB
- `C:\Users\tomas\AppData\Local\Package Cache` 0,07 GB

### `node_modules` (encontrados, no confirmados como huérfanos) — subtotal ≈ 1,16 GB
*(ya incluidos dentro de sus carpetas de proyecto en "datos de usuario"; no se suman aparte al
total general)*
- `C:\Users\tomas\MedicIA\synapse\node_modules` 0,67 GB (mod. 03/09/2026)
- `C:\Users\tomas\MedicIA\synapse\.next\standalone\node_modules` 0,034 GB
- `C:\Users\tomas\MedicIA\synapse\.open-next\server-functions\default\node_modules` 0,015 GB
- `C:\Users\tomas\flash-crm\node_modules` 0,236 GB (mod. 19/04/2026)
- `C:\Users\tomas\Documents\porta\node_modules` 0,191 GB (mod. 31/03/2026)
- `C:\Users\tomas\Documents\porta\packages\web\node_modules` 0,004 GB
- `C:\Users\tomas\Documents\porta\packages\proxy\node_modules` ~0 GB
Ninguno de los proyectos padre muestra fecha de modificación anterior a 2026; no hay base factual
en las fechas para calificar alguno como "huérfano" sin más contexto del usuario.

### Logs — subtotal ≈ 0,41 GB
- `C:\Windows\Logs` 0,24 GB (ya contado en "sistema", no se duplica en el total)
- `C:\Users\tomas\AppData\Local\CrashDumps` 0,16 GB
- `C:\Users\tomas\AppData\Local\D3DSCache` 0,01 GB (caché de shaders, no log puro)

### Temporales — subtotal ≈ 14,58 GB
- `C:\adobeTemp` 6,85 GB
- `C:\Users\tomas\AppData\Local\Temp` 4,76 GB
- `C:\Users\tomas\userteemp` 2,97 GB (nombre sugiere temporal; no confirmado sin auditoría de
  contenido, fuera de alcance)
- `C:\tmp` 0,69 GB
- `C:\Windows\Temp` — no medido (acceso denegado, ver §5)
- `C:\Users\tomas\temp-cc`, `temp-daily`, `temp-trailstop-papa`, `temp-viewing` — 0 GB cada una
  (vacías o negligibles)

### Datos de usuario — subtotal ≈ 118,9 GB
- `C:\Users\tomas\Downloads` 56,26 GB
- `C:\Users\tomas\AppData\Roaming` 18,14 GB
- `C:\Users\tomas\AppData\Local\Packages` 21,49 GB
- `C:\Users\tomas\.android` 12,06 GB
- `C:\Users\tomas\AppData\Local\wsl` 11,12 GB
- `C:\Users\tomas\AppData\LocalLow` 2,73 GB
- `C:\Users\tomas\curseforge` 2,48 GB
- `C:\Users\tomas\AppData\Local\star citizen` 2,68 GB
- `C:\Users\tomas\userteemp - backup` 2,39 GB
- `C:\Users\tomas\.vscode` 0,82 GB
- `C:\Users\tomas\Documents` 0,79 GB
- `C:\Users\tomas\MedicIA` 0,97 GB
- `C:\Users\tomas\Python Scripts` 0,88 GB
- `C:\Users\tomas\AppData\Local\Discord` 1,12 GB
- `C:\Users\tomas\AppData\Local\Programs` 5,19 GB
- (+ ~30 carpetas de proyecto menores del perfil, cada una < 0,5 GB — ver §Anexo/comandos)

### Datos de programa activo (Docker/WSL) — subtotal ≈ 22,01 GB
- `C:\Users\tomas\AppData\Local\Docker` 22,01 GB (dominado por `docker_data.vhdx`, 21,86 GB)

---

## 4. Rutas peligrosas de borrar — resumen explícito

Marcadas con ⚠️ en la tabla principal. Resumen:

- **Sistema operativo, no tocar bajo ninguna circunstancia:** `C:\Windows\WinSxS`,
  `C:\Windows\System32`, `C:\Windows\assembly`, `C:\hiberfil.sys`, `C:\pagefile.sys`,
  `C:\swapfile.sys`, `C:\Windows\Installer` (soporta reparación/desinstalación de programas
  instalados).
- **Software instalado en uso activo:** todo `C:\Program Files\*` y `C:\Program Files (x86)\*`
  listado (Adobe, Office, Visual Studio, Docker Desktop, Steam, Android Studio, Windows Kits,
  Common Files).
- **Datos de programa activo, no cachés desechables sin más:** `C:\Users\tomas\AppData\Local\Docker`
  (imágenes/contenedores Docker — borrarlo sin más implica perder contenedores/imágenes locales),
  `C:\Users\tomas\AppData\Local\wsl` (si hay distros WSL activas con datos).
- **Datos de usuario, no identificables como descartables sin la lectura del usuario:**
  `C:\Users\tomas\Downloads` (contiene documentos personales además de vídeos), `Documents`, y
  todos los subdirectorios de proyecto (`MedicIA`, `flash-crm`, `AgenciaRM`, `CRECE`, etc.).

---

## 5. No medido — ruta y motivo exacto

| Ruta | Motivo |
|---|---|
| `C:\System Volume Information` | Acceso denegado (`Get-ChildItem` → "Acceso denegado a la ruta de acceso"). Requiere privilegios de sistema/administrador elevado para enumerar. Contiene, entre otras cosas, los puntos de restauración / almacenamiento de instantáneas de volumen (VSS); no se pudo confirmar su tamaño. |
| Tamaño de shadow storage (VSS) vía `vssadmin list shadowstorage` | Comando ejecutado, rechazado: "No tiene los permisos adecuados para ejecutar este comando. Ejecute esta utilidad desde una ventana de comandos que tenga privilegios elevados de administrador." Esta sesión no tiene consola elevada. |
| `C:\Program Files\WindowsApps` | `Get-ChildItem` devolvió "Acceso denegado a la ruta de acceso". La cifra "0 GB" obtenida en la primera pasada (`Measure-Object` sobre un `Get-ChildItem -Recurse` que traga el error) es un **artefacto de la supresión de errores, no un tamaño real** — se descarta explícitamente esa cifra y se reporta como no medido. |
| `C:\Windows\Temp` | `robocopy ... /L` devolvió `ERROR 5 (0x00000005) Obteniendo acceso al directorio de origen ... Acceso denegado.` Requiere permisos elevados. |
| `C:\Windows` (tamaño total como conjunto) | No se ejecutó una medición recursiva de la carpeta completa (el brief advierte explícitamente que un recorrido total del perfil/artefactos grandes del sistema excede el timeout). Se midieron solo las subramas identificadas como pesadas en el listado de primer nivel (`WinSxS`, `Installer`, `System32`, `assembly`, `servicing`, `Logs`, `SoftwareDistribution`, `Panther`); quedan sin medir subcarpetas menores (`Fonts`, `SysWOW64`, `System`, `ServiceProfiles`, `SystemApps`, paquetes de idioma `es-ES`/`es-MX`/`en-US`/etc., `Speech`, `Microsoft.NET`, entre otras) por tratarse de ramas de segundo orden bajo el umbral de relevancia dado el tiempo disponible. |
| `C:\Users\tomas\AppData\Roaming` (desglose por subcarpeta) | Se midió el total (18,14 GB) pero no se descendió a desglosar cada subcarpeta individual por límite de tiempo de la sesión; el total sí es una medición real (no estimada). |
| ~30 carpetas de proyecto de menor tamaño bajo `C:\Users\tomas\` (p. ej. `Ads`, `nuevacasa`, `octopus-limb`, `hailmary`, `CRECE`, `rtk-test`, `AgenciaRM`, etc.) | Medidas individualmente (ver Anexo §6) pero no desglosadas por fecha de último acceso real, dado que la propia medición altera esa marca de tiempo (ver nota en §2). |
| Fecha de "último acceso" real (uso genuino, no inducido por esta medición) para toda la tabla | El acto de medir con `Get-ChildItem -Recurse` / `robocopy /L` actualiza `LastAccessTime` de la carpeta contenedora (NTFS con actualización de acceso habilitada, confirmado con `fsutil behavior query disablelastaccess` = 2). No existe forma de obtener el último acceso genuino previo a esta sesión sin herramientas forenses fuera de alcance. |

**Cuadre de totales (transparencia, no interpretación):** la suma de todas las cifras medidas en
este documento es de aproximadamente 410–411 GB, frente a los 429,18 GB que reporta el sistema
operativo como usados en C:. La diferencia (~18 GB) es consistente con la suma de las ramas no
medidas de esta tabla (`WindowsApps`, `Windows\Temp`, `System Volume Information`, subcarpetas
menores de `C:\Windows` y de `AppData\Roaming` no desglosadas) más el redondeo acumulado de
reportar cada cifra a 2 decimales de GB.

---

## 6. Anexo de evidencia — comandos ejecutados y salida real

### Disco: totales C: y D:
```
PS> Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:' OR DeviceID='D:'" | Select-Object DeviceID, @{N='SizeGB';E={[math]::Round($_.Size/1GB,2)}}, @{N='FreeGB';E={[math]::Round($_.FreeSpace/1GB,2)}}, @{N='UsedGB';E={[math]::Round(($_.Size-$_.FreeSpace)/1GB,2)}}, @{N='PctFree';E={[math]::Round(($_.FreeSpace/$_.Size)*100,2)}} | Format-Table -AutoSize

DeviceID SizeGB FreeGB UsedGB PctFree
-------- ------ ------ ------ -------
C:       451,37  22,19 429,18    4,92
D:       465,75 153,87 311,87   33,04
```

### Git SHA y timestamp
```
PS> git -C D:\FOREX rev-parse --short HEAD
b042f5c

PS> Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
2026-08-10 19:21:21 -04:00   (inicio de sesión de medición)
2026-08-10 19:42:18 -04:00   (cierre, usado en cabecera)
```

### Primer nivel de C:\
```
PS> Get-ChildItem -Path C:\ -Directory -Force | Select-Object Name, LastWriteTime | Format-Table -AutoSize
[listado completo — 25 carpetas: $Recycle.Bin, $SysReset, adobeTemp, Archivos de programa,
Cloudflared, Config, Config.Msi, Documents and Settings, eSupport, flutter, inetpub, Intel,
NewsTrader, PerfLogs, Program Files, Program Files (x86), ProgramData, projects, Recovery,
SapitosLogs, System Volume Information, tmp, Users, Windows, XboxGames]

PS> Get-ChildItem -Path C:\ -File -Force | Select-Object Name, @{SizeMB},LastWriteTime | Format-Table -AutoSize
Name                 SizeMB LastWriteTime
----                 ------ -------------
.GamingRoot               0 4/08/2026 3:41:15 a. m.
appverifUI.dll         0,11 22/02/2024 1:33:48 a. m.
DumpStack.log          0,01 18/07/2026 6:42:03 a. m.
DumpStack.log.tmp      0,01 9/08/2026 10:40:05 p. m.
GetDeviceStatus.xml       0 21/07/2024 2:10:53 a. m.
hiberfil.sys        6442,38 9/08/2026 10:39:58 p. m.
pagefile.sys         3773,4 10/08/2026 7:18:00 p. m.
swapfile.sys             16 9/08/2026 10:40:05 p. m.
vfcompat.dll           0,06 22/02/2024 1:34:14 a. m.
```

### Medición de carpetas de primer nivel de C:\ (Get-ChildItem -Recurse -File | Measure-Object)
```
C:\XboxGames => 0.01 GB
C:\NewsTrader => 0 GB
C:\projects => 1.32 GB
C:\inetpub => 0 GB
C:\flutter => 2.2 GB
C:\Intel => 0 GB
C:\tmp => 0.69 GB
C:\SapitosLogs => 0 GB
C:\adobeTemp => 6.85 GB
C:\Config.Msi => 0 GB
C:\Recovery => 0 GB
C:\eSupport => 5.03 GB
C:\Cloudflared => 0 GB
C:\Config => 0 GB
C:\PerfLogs => 0 GB
C:\$Recycle.Bin => 0.18 GB
C:\$SysReset => 0.03 GB
```

### System Volume Information — acceso denegado
```
PS> try { Get-ChildItem -LiteralPath 'C:\System Volume Information' -Force -ErrorAction Stop } catch { $_ }
SVI: ERROR Acceso denegado a la ruta de acceso 'C:\System Volume Information'.
```

### vssadmin — requiere elevación
```
PS> vssadmin list shadowstorage
vssadmin 1.1 - Herramienta administrativa de línea de comandos del Servicio de instantáneas de volumen.
Error: No tiene los permisos adecuados para ejecutar este comando. Ejecute esta utilidad desde una
ventana de comandos que tenga privilegios elevados de administrador.
```

### Program Files / Program Files (x86) — totales y subcarpetas
```
C:\Program Files => 53.75 GB (elapsed 49.33s)
C:\Program Files (x86) => 23.3 GB (elapsed 5.93s)

C:\Program Files\WSL => 0.63 GB
C:\Program Files\NinjaTrader 8 => 0.17 GB
C:\Program Files\MetaTrader 5 => 0.36 GB
C:\Program Files\Microsoft Visual Studio => 5.24 GB
C:\Program Files\Adobe => 25.59 GB
C:\Program Files\WindowsApps => 0 GB  [DESCARTADO: acceso denegado real, ver Get-ChildItem directo abajo]
C:\Program Files\Android => 2.85 GB
C:\Program Files\Docker => 3.18 GB
C:\Program Files\Microsoft Office => 5.14 GB
C:\Program Files\Microsoft SQL Server => 0 GB
C:\Program Files\Tesseract-OCR => 0.23 GB
C:\Program Files\nodejs => 0.1 GB
C:\Program Files\obs-studio => 0.44 GB
C:\Program Files\GitHub CLI => 0.04 GB
C:\Program Files\Git => 0.39 GB
C:\Program Files\Common Files => 6.06 GB
C:\Program Files\Application Verifier => 0 GB

PS> Get-ChildItem -LiteralPath 'C:\Program Files\WindowsApps' -Force -ErrorAction Stop
ERROR: Acceso denegado a la ruta de acceso 'C:\Program Files\WindowsApps'.

C:\Program Files (x86)\Steam => 12.19 GB
C:\Program Files (x86)\Microsoft Visual Studio => 0.1 GB
C:\Program Files (x86)\Windows Kits => 2.25 GB
C:\Program Files (x86)\Traktor => 0.08 GB
C:\Program Files (x86)\Microsoft SDKs => 0.03 GB
C:\Program Files (x86)\Common Files => 0.47 GB
C:\Program Files (x86)\Microsoft.NET => 0.01 GB
C:\Program Files (x86)\Adobe => 0.06 GB
```

### ProgramData — subcarpetas
```
C:\ProgramData\SoftwareDistribution => 0 GB
C:\ProgramData\Package Cache => 0.98 GB
C:\ProgramData\DockerDesktop => 0 GB
C:\ProgramData\MetaQuotes => 0.45 GB
C:\ProgramData\NVIDIA => 0.22 GB
C:\ProgramData\NVIDIA Corporation => 0.74 GB
C:\ProgramData\Microsoft => 2.69 GB
C:\ProgramData\Packages => 0 GB
C:\ProgramData\chocolatey => 0.3 GB
C:\ProgramData\ChocolateyHttpCache => 0 GB
C:\ProgramData\Adobe => 2.25 GB
C:\ProgramData\ASUS => 0.16 GB
C:\ProgramData\boost_interprocess => 0 GB
C:\ProgramData\CanonBJ => 0.02 GB
C:\ProgramData\Epson => 0 GB
C:\ProgramData\Cloudflare => 0 GB
C:\ProgramData\Intel => 0.01 GB
C:\ProgramData\McAfee => 0 GB
C:\ProgramData\Jagex Launcher => 0 GB
C:\ProgramData\obs-studio => 0 GB
C:\ProgramData\obs-studio-hook => 0 GB
C:\ProgramData\Tailscale => 0 GB
C:\ProgramData\Microsoft DevDiv => 0 GB
C:\ProgramData\Microsoft OneDrive => 0 GB
```

### C:\Users\tomas — AppData
```
AppData\LocalLow => 2.73 GB (elapsed 0.47s)
AppData\Roaming => 18.14 GB (elapsed 18.50s)
AppData\Local => 108.48 GB (elapsed 107.28s)

C:\Users\tomas\AppData\Local\Packages => 21.49 GB
C:\Users\tomas\AppData\Local\Programs => 5.19 GB
C:\Users\tomas\AppData\Local\Google => 8.04 GB
C:\Users\tomas\AppData\Local\Microsoft => 2.83 GB
C:\Users\tomas\AppData\Local\Docker => 22.01 GB
C:\Users\tomas\AppData\Local\pip => 0.74 GB
C:\Users\tomas\AppData\Local\npm-cache => 9.25 GB
C:\Users\tomas\AppData\Local\uv => 2.42 GB
C:\Users\tomas\AppData\Local\pnpm-cache => 0.15 GB
C:\Users\tomas\AppData\Local\pnpm => 0.56 GB
C:\Users\tomas\AppData\Local\pnpm-state => 0 GB
C:\Users\tomas\AppData\Local\ms-playwright => 1.19 GB
C:\Users\tomas\AppData\Local\ms-playwright-go => 0.18 GB
C:\Users\tomas\AppData\Local\Temp => 4.76 GB
C:\Users\tomas\AppData\Local\VirtualStore => 0 GB
C:\Users\tomas\AppData\Local\Package Cache => 0.07 GB
C:\Users\tomas\AppData\Local\star citizen => 2.68 GB
C:\Users\tomas\AppData\Local\UnrealEngine => 0 GB
C:\Users\tomas\AppData\Local\Riot Games => 0.02 GB
C:\Users\tomas\AppData\Local\Overwolf => 0 GB
C:\Users\tomas\AppData\Local\wsl => 11.12 GB
C:\Users\tomas\AppData\Local\Steam => 0.29 GB
C:\Users\tomas\AppData\Local\Discord => 1.12 GB
C:\Users\tomas\AppData\Local\Adobe => 0.17 GB
C:\Users\tomas\AppData\Local\Android => 8.83 GB
C:\Users\tomas\AppData\Local\NVIDIA => 0.26 GB
C:\Users\tomas\AppData\Local\NVIDIA Corporation => 0.01 GB
C:\Users\tomas\AppData\Local\CrashDumps => 0.16 GB
C:\Users\tomas\AppData\Local\D3DSCache => 0.01 GB
C:\Users\tomas\AppData\Local\SolidDocuments => 0 GB
C:\Users\tomas\AppData\Local\MinecraftInstaller => 0 GB

PS> (Docker, top 15 files by size, depth 2)
C:\Users\tomas\AppData\Local\Docker\wsl\disk\docker_data.vhdx  22384 MB
C:\Users\tomas\AppData\Local\Docker\wsl\main\ext4.vhdx           115 MB
[resto: logs de 1 MB]
```

### C:\Users\tomas — carpetas de perfil (dotfiles y proyectos)
```
C:\Users\tomas\.antigravity => 0.69 GB
C:\Users\tomas\.aws => 0 GB
C:\Users\tomas\.azure => 0 GB
C:\Users\tomas\.chocolatey => 0 GB
C:\Users\tomas\.claude => 0.51 GB
C:\Users\tomas\.cloud-run-mcp => 0 GB
C:\Users\tomas\.cloudflared => 0 GB
C:\Users\tomas\.config => 0 GB
C:\Users\tomas\.crossnote => 0 GB
C:\Users\tomas\.docker => 0.4 GB
C:\Users\tomas\.gemini => 5.73 GB
C:\Users\tomas\.javacpp => 0.04 GB
C:\Users\tomas\.local => 0.06 GB
C:\Users\tomas\.ms-ad => 0 GB
C:\Users\tomas\.skiko => 0.03 GB
C:\Users\tomas\.ssh => 0 GB
C:\Users\tomas\.streamlit => 0 GB
C:\Users\tomas\.supabase => 0 GB
C:\Users\tomas\.VirtualBox => 0 GB
C:\Users\tomas\.vscode => 0.82 GB
C:\Users\tomas\Ads => 0.04 GB
C:\Users\tomas\AgenciaRM => 0.12 GB
C:\Users\tomas\AndroidStudioProjects => 0.55 GB
C:\Users\tomas\ansel => 0 GB
C:\Users\tomas\Book Knowledge Extraction => 0 GB
C:\Users\tomas\claude-backup-20260630-165027 => 0.07 GB
C:\Users\tomas\claude-brain-pre-P7-20260701-104423 => 0 GB
C:\Users\tomas\Creative Cloud Files ...AdobeID => 0 GB
C:\Users\tomas\CRECE => 0 GB
C:\Users\tomas\ffx_extensions => 0 GB
C:\Users\tomas\hailmary => 0 GB
C:\Users\tomas\MedicIA => 0.97 GB
C:\Users\tomas\NanoBanana_Product_Studio => 0.07 GB
C:\Users\tomas\nuevacasa => 0.02 GB
C:\Users\tomas\octopus-limb => 0 GB
C:\Users\tomas\Python Scripts => 0.88 GB
C:\Users\tomas\rtk-test => 0 GB
C:\Users\tomas\temp-cc => 0 GB
C:\Users\tomas\temp-daily => 0 GB
C:\Users\tomas\temp-trailstop-papa => 0 GB
C:\Users\tomas\temp-viewing => 0 GB
C:\Users\tomas\test_assistants => 0.06 GB
C:\Users\tomas\userteemp => 2.97 GB
C:\Users\tomas\userteemp - backup => 2.39 GB
C:\Users\tomas\VS_code_custom => 0 GB
C:\Users\tomas\Downloads => 56.26 GB
C:\Users\tomas\node_modules => 0.01 GB
C:\Users\tomas\OneDrive => 0.51 GB
C:\Users\tomas\google-cloud-sdk => 0.38 GB
C:\Users\tomas\.cache => 2.12 GB
C:\Users\tomas\.android => 12.06 GB
C:\Users\tomas\.gradle => 2.43 GB
C:\Users\tomas\pipx => 0.38 GB
C:\Users\tomas\VirtualBox VMs => 0 GB
C:\Users\tomas\curseforge => 2.48 GB
C:\Users\tomas\Muse Hub => 0 GB
C:\Users\tomas\Documents => 0.79 GB
C:\Users\tomas\Videos => 0 GB
C:\Users\tomas\flash-crm => 0.26 GB
C:\Users\tomas\flash-crm-backup-20251207 => 0.03 GB
C:\Users\Public => 0.19 GB
```

### Downloads — top 25 ítems por tamaño
```
Name                                                                GB  LastWrite
Project.Hail.Mary.2026.2160p.WEB-DL.DDP5.1.Atmos.H.265-RDNYB.mkv  23,335 13/05/2026
Project Hail Mary [2026] WEBrip YG                                10,694 13/05/2026
www.UIndex.org - Citizen.Vigilante.2026...GOREHOUNDS               5,575 28/06/2026
www.UIndex.org - The Fantastic Four...x265-DH                      2,375 02/07/2026
hogar magico 2                                                     2,102 11/01/2026
hogar magico 2.zip                                                     2 11/01/2026
Muebles_Nagu                                                       1,844 18/05/2026
www.UIndex.org - The Fantastic Four...x265-NeoNoir                  1,71 02/07/2026
Good Fortune 2025 1080p WEB-DL HEVC x265 5.1 BONE.mkv               1,475 04/07/2026
www.UIndex.org - Good Fortune (2025)...LAMA                        1,299 04/07/2026
Citizen.Vigilante.2026.1080p.10bit.DDP5.1.x265.FaS.mkv              1,212 29/06/2026
hogar magico 2 p2.zip                                              0,779 11/01/2026
inicio_hero_hunter.mp4                                              0,312 26/03/2026
[...resto de la lista completa capturada, ver tabla §2 para resumen]
NinjaTrader.Install.msi                                               0,08 01/07/2026
```

### Windows — robocopy dry-run (`/L`) por rama
```
PS> robocopy 'C:\Windows\WinSxS' NULL /L /S /NJH /NDL /NFL /BYTES /R:0 /W:0
Director.:      154314      154314         0         0         0         0
 Archivos:      168893      168893         0         0         0         0
    Bytes: 24077054862 24077054862         0         0         0         0
   Tiempo:     0:00:24

PS> (batch) robocopy sobre SoftwareDistribution / Installer / Temp / Panther / Logs / servicing / assembly
=== C:\Windows\SoftwareDistribution ===
    Bytes: 252407754
=== C:\Windows\Installer ===
    Bytes: 40933513481
=== C:\Windows\Temp ===
    [sin línea Bytes — ver error de acceso abajo]
=== C:\Windows\Panther ===
    Bytes: 407790
=== C:\Windows\Logs ===
    Bytes: 255747116
=== C:\Windows\servicing ===
    Bytes: 622155222
=== C:\Windows\assembly ===
    Bytes: 3571342146

PS> robocopy 'C:\Windows\System32' NULL /L /S /NJH /NDL /NFL /BYTES /R:0 /W:0
    Bytes: 12277773294

PS> robocopy 'C:\Windows\Temp' NULL /L /S /NJH /NDL /NFL /BYTES /R:0 /W:0
2026/08/10 19:38:51 ERROR 5 (0x00000005) Obteniendo acceso al directorio de origen C:\Windows\Temp\
Acceso denegado.

PS> Get-ChildItem -Path 'C:\Windows\Installer' -Force | Measure-Object → Count: 532
PS> Get-ChildItem -Path 'C:\Windows\Installer' -Directory | Select Name
$PatchCache$, MSI1CC3.tmp-, MSI9266.tmp-, {GUID}... (530 carpetas GUID adicionales)
```

### NTFS last-access
```
PS> fsutil behavior query disablelastaccess
DisableLastAccess = 2   (administradas por el sistema, actualizaciones de la hora de último acceso HABILITADAS)
```

### node_modules — búsqueda dirigida (no exhaustiva sobre todo el perfil)
```
PS> (por cada raíz de proyecto conocida) Get-ChildItem -Recurse -Directory -Filter node_modules | Where no-anidado
C:\Users\tomas\MedicIA\synapse\node_modules => 0.67 GB, LastWrite: 03/09/2026 21:31:51
C:\Users\tomas\MedicIA\synapse\.next\standalone\node_modules => 0.034 GB, LastWrite: 03/09/2026 23:05:57
C:\Users\tomas\MedicIA\synapse\.open-next\server-functions\default\node_modules => 0.015 GB, LastWrite: 03/09/2026 23:06:01
C:\Users\tomas\flash-crm\node_modules => 0.236 GB, LastWrite: 04/19/2026 15:24:17
C:\Users\tomas\Documents\porta\node_modules => 0.191 GB, LastWrite: 03/31/2026 03:57:38
C:\Users\tomas\Documents\porta\packages\proxy\node_modules => 0 GB, LastWrite: 03/31/2026 03:57:38
C:\Users\tomas\Documents\porta\packages\web\node_modules => 0.004 GB, LastWrite: 03/31/2026 03:57:49
```
