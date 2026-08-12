# BRIEF PARA CLAUDE CODE DE LA MÁQUINA 2 — extracción de la config viva de la 902

> **Cómo usar esto:** pegar TODO el bloque de abajo (desde «INICIO DEL MENSAJE») en Claude Code
> abierto en el repo de la máquina 2. Está escrito para un agente **sin ningún contexto previo**.
> Redactado 2026-08-12 desde la máquina 1 (equipo local, rama `equipo1`, HEAD `ee47fe3`).

---

## INICIO DEL MENSAJE

Hola. Vengo de otra máquina que trabaja en el mismo proyecto y necesito que me extraigas
información **en modo estrictamente de solo lectura**. Lee las reglas antes de ejecutar nada.

# 🔴 REGLAS DURAS — LÉELAS PRIMERO

**Este equipo corre operativa EN VIVO sobre la cuenta MT5 `2883016902` (la "902").** Cualquier cosa
que la interrumpa tiene coste real.

1. **NO detengas, reinicies ni mates ningún proceso.** Ni Python, ni `terminal64.exe`, ni servicios,
   ni tareas programadas.
2. **NO envíes ninguna orden a ningún mercado. NO ejecutes el ejecutor.** No lances backtests ni
   scripts que abran conexiones de trading.
3. **NO modifiques ningún fichero del repo.** Nada de `git add`, `commit`, `push`, `pull`, `merge`,
   `rebase`, `checkout`, `switch`, `restore`, `reset`, `clean`, ni **`git stash`**.
   🔴 **El working tree sin commitear ES el artefacto que vengo a buscar.** Es, con toda
   probabilidad, el **único ejemplar** del código que generó dos semanas de operativa real.
   Cualquier comando que lo mueva o lo limpie destruye evidencia irrecuperable.
4. **No instales nada.** No `pip install`, no `npm`, no actualizaciones.
5. Si algo te parece que «habría que arreglar», **NO lo arregles**: anótalo y repórtalo.
6. Si un comando pudiera escribir en el repo y no estás seguro, **no lo corras** y dilo.

Todo lo que sigue se puede hacer leyendo ficheros y consultando estado. Si algo no se puede
obtener sin violar una regla, **repórtalo como no obtenible** en vez de forzarlo.

# CONTEXTO: qué estamos resolviendo

En la otra máquina intentamos reproducir con el motor de backtest las **152 posiciones reales** que
esta máquina ejecutó entre `2026-07-27 18:53:30` y `2026-08-11 01:15:04` (84 de `S6-K2P0`,
68 de `SuperTrend-p14x3-M15`). El motor **no las reproduce**, y ya descartamos con medición: el
feed, el servidor de datos, la construcción de barras, el gate de spread y la granularidad
tick-vs-barra.

Lo que queda son **dos divergencias de configuración** entre lo que corre aquí y lo que hay
commiteado en el repo:

- **Fichas.** El repo abre **3 fichas por señal**; la realidad abrió **exactamente 1** (magics de
  apertura `724011` y `724071`, comentario `S6-K2P0:F1`; los magics `724012`/`724013` **nunca**
  aparecen).
- **Trailing.** En el repo, `trail_atr_floor_k=2.0` eleva el trail efectivo a
  `max(1,00 ; 2,0×ATR14)` ≈ **15,6 USD**, y con un SL inicial de ≈17,5 USD el trail **nunca llega a
  disparar** (192 de 192 salidas simuladas son por SL inicial). Pero las salidas **reales** se
  agrupan en **−1,00 USD**, que es exactamente el ancho del trail plano
  (`f1_trail_pips=100.0 × pip 0,01`). Es decir: **aquí el sistema se comporta como si el floor ATR
  no estuviera aplicado.**

Nuestra hipótesis: **este equipo no corre la config del repo**, sino una variante con **1 ficha** y
**sin floor ATR sobre el trail**. Sabemos que los últimos cambios de esta máquina **nunca se
commitearon**. Tu trabajo es darme el estado real, no confirmar mi hipótesis — **si los datos la
contradicen, dilo.**

# LO QUE NECESITO, POR ORDEN DE VALOR

## 1 · El working tree sin commitear (LO MÁS IMPORTANTE)

Sin escribir nada en el repo:

```
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git log --oneline -5
git remote -v
git status --porcelain=v1 --untracked-files=all
git diff                 # cambios sin stagear, COMPLETO
git diff --stat
git diff --cached        # cambios stageados, si hay
git stash list           # SOLO listar. NO crear, NO aplicar, NO borrar.
```

Luego haz una **copia portable** del repo completo a una carpeta **FUERA** del repo (por ejemplo
`%USERPROFILE%\Desktop\M2_ENTREGA\`), incluyendo el directorio `.git` y los ficheros sin trackear.
Copiar es lectura del origen: no toca el working tree. Si el repo es enorme, prioriza en este orden:
el `.git` completo, los ficheros modificados y sin trackear, y los directorios de configuración de
estrategias y del ejecutor.

Si puedes, añade también `git bundle create <destino>\repo-completo.bundle --all` — es de solo
lectura sobre el repo y empaqueta toda la historia en un fichero.

## 2 · Con qué línea de comandos corre el ejecutor

Consulta el proceso vivo (solo lectura):

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'python|run_live|supervisor' } |
  Select-Object ProcessId, CreationDate, CommandLine | Format-List
```

Y busca de dónde se lanza: tareas programadas (`Get-ScheduledTask | Where-Object TaskName -match
'live|sentinel|mt5'`), servicios, ficheros `.bat`/`.ps1`/`.cmd` de arranque, accesos directos, o
entradas de inicio automático. **Solo leer y reportar**, no ejecutar ni deshabilitar.

Quiero literalmente los flags: `--window`, `--roster`, `--interval`, `--max-spread-open`, y
cualquiera que module SL, trailing, nº de fichas o volumen.

## 3 · La config efectiva de las dos estrategias

Localiza el módulo de configuraciones de estrategias vivas (en el otro repo se llama
`sentinel_engine/strategies/live_configs_20.py`, aquí puede diferir) y **dame su contenido íntegro**,
más el del ejecutor (`run_live_20.py` o su equivalente aquí).

Y respóndeme estos valores **tal como los usa esta máquina**, citando `fichero:línea` para cada uno.
Si un parámetro no existe aquí, **dilo explícitamente** — su ausencia es justo lo que sospecho:

| Parámetro | Qué necesito saber | Lo que predecimos |
|---|---|---|
| `active_fichas` (o el equivalente) | valor efectivo para S6 y para SuperTrend | **1** |
| `trail_atr_floor_k` | ¿existe? ¿con qué valor? ¿se aplica al trail? | **ausente o sin aplicar** |
| `f1_trail_pips` | valor | 100.0 |
| `init_sl_range_k` | valor para M15 | 2.5 |
| `be_at_r` | ¿lo tiene S6? | ausente en S6 |
| volumen / lote | de dónde sale el **0.67** por posición | fijo en config de aquí |
| `MAX_VOLUME` | si existe un tope y cuánto vale | en el otro repo es 0.10 y rechazaría 0.67 |
| `stop_and_reverse` | valor para S6 | True |
| gate de spread | mecanismo y umbral | adaptativo running-min |

⚠️ Prefiero que **leas los ficheros** a que importes módulos. Si necesitas importar para resolver un
valor calculado, asegúrate primero de que el módulo no abre conexiones ni arranca nada al importarse,
y dilo en el reporte.

## 4 · Los logs del ejecutor de la ventana

Localiza los logs de decisiones del ejecutor que cubran **2026-07-27 → 2026-08-11** y **cópialos** a
la carpeta de entrega. Son de altísimo valor: permiten comparar decisión a decisión en vez de
inferirlas desde el resultado. Reporta sus rutas, tamaños y el rango temporal real que cubren.

Incluye también, si existen, los logs del terminal MT5 (`MQL5/Logs/`, `logs/`) del mismo periodo.

## 5 · ¿Hay algún gestor de SL aparte del ejecutor Python?

En la otra máquina hay un EA MQL5 llamado `SENTINEL_TrailGuard` que **no compila** (10 errores) y
está desactivado. Aquí puede ser distinto y sería una explicación alternativa del trailing observado.
Comprueba y reporta:

- Qué EAs hay en `MQL5/Experts/` y cuáles están compilados (`.ex5`) vs desactivados.
- Si algún EA está **adjunto a un gráfico** y activo (mira los perfiles de gráficos y el estado del
  terminal), y con qué parámetros de entrada.
- Ruta del terminal MT5 que usa esta máquina y si corre en modo `/portable`.

## 6 · Identidad de la cuenta (sin loguear nada)

Si —y solo si— hay un terminal MT5 **ya abierto y ya logueado**, attachea en solo lectura y dame
`account_info()`: `login`, `server`, `company`, `balance`, `trade_mode`. **No introduzcas
credenciales, no cambies de cuenta, no abras sesión.** Si no hay terminal abierto, **no lo abras**:
reporta «no obtenible sin abrir sesión».

# CÓMO ENTREGARME EL RESULTADO

1. Deja todo en **una sola carpeta** fuera del repo y dime su **ruta absoluta** y su tamaño total.
2. Comprímela en un zip si cabe en un pendrive.
3. **Además**, escribe en el chat un **resumen en texto** con: rama, HEAD, `git status` resumido, la
   línea de comandos del ejecutor, y la **tabla de la sección 3 rellena con los valores reales y sus
   `fichero:línea`**. Lo quiero también en texto porque puede que el zip no llegue a viajar y ese
   resumen ya me desbloquea.
4. Termina con una lista explícita de **lo que NO pudiste obtener y por qué**.

# CRITERIO DE HONESTIDAD

No adivines ningún valor. Si algo no está en el código, di «no está». Si un valor se calcula en
tiempo de ejecución, dime dónde se calcula y de qué depende, en vez de estimarlo. Si encuentras algo
que contradice la hipótesis de las dos divergencias, **dilo con la misma claridad** — un negativo
bien medido me sirve igual que un positivo.

## FIN DEL MENSAJE
