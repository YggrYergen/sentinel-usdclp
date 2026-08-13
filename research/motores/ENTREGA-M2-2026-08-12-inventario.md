# Entrega de máquina 2 (TOMACHINE) — inventario y estado de explotación

Recibida 2026-08-12. Generada en la máquina que operó la DEMO **2883016902**, en modo
estrictamente de solo lectura (ningún fichero de su repo fue modificado).

**Ubicación:** `D:\FOREX\data\entregas\2026-08-12-maquina2-tomachine-902\` · **468 MB**
(1.271 ficheros). Fuera de git por la regla `data/*` del `.gitignore`, que es lo correcto: son
datos, no código.

Copiada desde `C:\Users\tomas\Downloads\M2_ENTREGA\M2_ENTREGA\` el 2026-08-13 y **verificada por
MD5** en las tres piezas críticas (`repo-completo.bundle`, `repo/data/research.db`,
`logs_ejecutor/audit_ventana_*.log`). El original de `Downloads` **no se ha borrado** — esa decisión
es del user.

Junto a los datos quedan las tres versiones vigentes del análisis, para que la carpeta se explique
sola sin depender del repo: `ANALISIS-DE-CONTENIDOS.md` (copia de este fichero),
`DIVERGENCIAS-harness-vs-faulty.md` y `MOTOR-FAULTY-descriptor.md`.

---

## 1 · Qué llegó

| Artefacto | Tamaño | Estado |
|---|---:|---|
| `RESUMEN.md` | 15 KB | ✅ leído íntegro |
| `repo-completo.bundle` | 4,6 MB | ✅ **importado y verificado** → `refs/m2/*`, tag `engine-faulty-tomachine-902` |
| `repo/` (copia íntegra con `.git` y sin trackear) | 355 MB | 🟡 explotado en parte (ver §3) |
| `logs_ejecutor/` | 70 MB | ⏳ **sin explotar** — es la verdad de terreno de A6 |
| `mt5_logs_capitaria/` | 629 KB | ⏳ sin explotar |
| `config_efectiva/` (10 ficheros) | 297 KB | ✅ verificados byte-idénticos a `b113eb7` |
| `diff_vs_origin-alvaro.patch` | 164 KB | ✅ redundante con el bundle |
| `commits_sin_pushear.txt` | 15 KB | ✅ redundante con el bundle |
| `M2_COMPLETO.zip` / `M2_ESENCIAL.zip` | 37,5 / 4,8 MB | — copias comprimidas de lo anterior |

## 2 · Logs

### `logs_ejecutor/` — el de mayor valor sin explotar

| Fichero | Tamaño | Cobertura |
|---|---:|---|
| `audit_ventana_2026-07-27_2026-08-12.log` | 69,7 MB | 2026-07-27 18:52:29 → 2026-08-12 09:37:02 · **561.988 líneas** |
| `audit_ventana_SOLO_ORDENES.log` | 204 KB | mismas fechas, sólo SENT/ALARM/CLAMP/CROSSED/arranques · 1.710 líneas |

Permite comparar **decisión a decisión** en vez de inferir desde el resultado. Es el insumo
declarado de A6 Pata A. Reparto de acciones ya extraído por máquina 2:
`OPEN/F1` 98.365 · `NOOP/F1` 50.484 · `none` 19.038 · `MODIFY/F1` 441 · `SAME` 11 ·
`CLOSE/F1+OPEN/F1` 3. Warnings: `SPREAD_GATE_SKIP` 92.461 · `TIME_GATE_SKIP` 4.790 ·
`OPEN_SKIPPED_SL_CROSSED` 943 · `SL_CLAMPED` 35 · `SAME_BAR_EXIT_FALLBACK` 11 ·
`FALLBACK_CLOSE_INVALID_SL` 9 · `ALARM` 4.

⚠️ **Todos esos contadores son por CICLO de reconciliación (~15 s), no por señal.** Con ~89.900
ciclos en la ventana, `SPREAD_GATE_SKIP` ≈ 1/ciclo. Contra 49 + 42 barras-señal hay tres órdenes de
magnitud. Leerlos como censo de oportunidades es el error que ya se cometió una vez.

### Otros logs, dentro de `repo/scripts/live/`

| Fichero | Tamaño | Qué es |
|---|---:|---|
| `run_live_20.audit.log` | 119,9 MB | audit **completo** 2026-07-15 → 2026-08-12 (superset del anterior) |
| `executor_console.log` | 119,8 MB | consola del ejecutor; su última línea es la muerte del proceso |
| `deals_watcher_local.log` | 37,6 MB | **422.208 líneas**, arranca 2026-07-15 21:12:59 sobre la cuenta **2883016567** (la retirada) |
| `run_service_local.log.err` | 9,4 MB | stderr del servicio |
| `watchdog_local.log.1` | 5,2 MB | watchdog rotado |

### `mt5_logs_capitaria/`

- `terminal/` — **18 logs**, `20260726.log` → `20260812.log`, del terminal sancionado.
- `mql5/` — **0 ficheros**. Negativo real, no un fallo: **ningún EA MQL5 corrió jamás** en esa
  máquina. Descarta la hipótesis de un gestor de SL alternativo (§5 del descriptor del motor).

## 3 · `repo/data/research.db` — la pieza que nadie había mirado

393 KB. **Es la fuente que refutó el «7 %» de los cierres manuales (D-43).** Tablas con contenido:

| Tabla | Filas | Para qué sirve |
|---|---:|---|
| `deals_raw` | **483** | deals con `profit`, `magic`, `reason`, `entry_type`, `position_id`, `strategy_id`, `comment` — **verdad de terreno del PnL** |
| `news_items` | 495 | sin explotar; posible insumo de filtro de régimen |
| `position_spread` | **237** | `spread_open` / `spread_open_min` / `spread_close` **por posición** |
| `magic_allocation` | 132 | reparto de magics |
| `meta` | 1 | — |

Vacías: `audit_log`, `forward_session`, `import_checksum`, `jobs`, `param_set`, `position_comment`,
`preregistration`, `run`, `strategy`, `trade`, `variant`.

### Dos hallazgos de esta tabla

**(a) El PnL real de las estrategias — ver D-43.** Sin cierres manuales la cuenta pierde
13,2 M CLP; `SuperTrend` hace −16,22 M. Las cifras de la LEDGER incluyen los manuales.

**(b) El spread por posición SÍ está registrado.** `position_spread` tiene 237 filas y
**236 tienen `spread_open = 0,50`, una sola 0,60**. Coherente con el cap duro de 0,50: el ejecutor
sólo abría cuando el spread estaba en el mínimo. Corrige la creencia registrada de que el spread
por operación no se logueaba — se loguea, en otra tabla.

### Atribución de deals: funciona, con residuo

Los cierres manuales llegan con `magic=0` (el problema conocido), pero la re-atribución por
`position_id` ya está hecha: en la ventana operativa, de 16 cierres manuales **12 quedan atribuidos**
a su estrategia (`origin='strategy'`) y **4 permanecen sin atribuir** (`origin='human'`,
`strategy_id=NULL`, −1.147.788 CLP). Ese residuo hay que resolverlo o declararlo antes de usar la
tabla como verdad de neto.

## 4 · Discrepancias abiertas

1. ✅ **RESUELTA (2026-08-13) — son 152 aperturas, y el error era del controlador.** La cifra de 150
   que apareció en la primera versión de este inventario venía de un filtro de ventana construido
   con `datetime(...).timestamp()`, que aplica el offset **local** (−4 h) al pasar de calendario a
   epoch. Como los epochs de `deals_raw` codifican el reloj de **servidor verbatim**, la ventana
   quedaba desplazada 4 horas y perdía 2 aperturas del borde. Con la conversión correcta
   (`calendar.timegm`): **152 `IN` / 151 `OUT`**, neto idéntico (+15.203.111,33). Confirmado
   independientemente por T0.6-B.

   > **Gotcha, en las dos direcciones.** La regla conocida cubre epoch → datetime
   > (`utcfromtimestamp`, nunca `fromtimestamp`). Falta su simétrica: **datetime → epoch se hace
   > con `calendar.timegm`, nunca con `.timestamp()`**. El controlador cometió exactamente el error
   > que había escrito como gotcha en los briefs, en el sentido inverso.

2. ✅ **RESUELTA — convención de reloj declarada.** `deals_raw.time` es un epoch que codifica el
   reloj del **servidor (UTC−4)** verbatim, y el reloj del servidor **coincide con la hora local de
   Chile**. Conversiones válidas: `datetime.utcfromtimestamp()` para leer, `calendar.timegm()` para
   escribir. Ninguna otra.

3. ✅ **RESUELTA — concurrencia máxima = 1 posición por estrategia.** Medido sobre la línea temporal
   real de aperturas y cierres: S6-K2P0 máximo **1** bajo cualquier convención de desempate;
   SuperTrend máximo **1** si en un empate de segundo el cierre precede a la apertura, que es la
   lectura físicamente correcta (el reconciliador abre porque ve la posición ya desaparecida). El
   único candidato a «2» es un par cierre→apertura en el **mismo segundo**, es decir una
   re-entrada. **Las re-entradas son secuenciales, nunca concurrentes.** Reparto: 84 posiciones de
   S6 + 68 de SuperTrend = 152.
3. **`deals_watcher_local.log` arranca sobre la cuenta 2883016567**, retirada en el commit
   `17258cd`. Cubre desde 2026-07-15, antes de la ventana. Sin explotar.

## 5 · Lo que no se pudo obtener, y por qué

1. **`account_info()` completo** (`server`, `company`, `balance`) — el único terminal abierto en esa
   máquina era el genérico, no el sancionado, y el ejecutor ya obtuvo `None` contra él. Attachear
   habría arriesgado lanzar un segundo terminal y congelar el IPC. **No lo necesitamos.**
2. **`git diff` con contenido** — vacío porque el working tree estaba limpio. No es un fallo: es el
   hallazgo que corrigió nuestra premisa.
3. **Logs MQL5** — no existen (ningún EA corrió). Negativo real.
4. **argv literal del proceso vivo** — no había proceso vivo. El argv del descriptor está
   reconstruido desde `build_executor_argv` + env persistidas + la línea que el propio ejecutor
   registró al arrancar; **las tres fuentes coinciden**.
5. **Más ticks de Capitaria** — no es una carencia de la entrega. Capitaria no compartió (D-42).

## 6 · Anomalía operativa reportada, no tocada

El stack de máquina 2 **no está operando**. El ejecutor murió el 2026-08-12 09:37:02 con
`[GUARD] REFUSING TO OPERATE: account_info() returned None`, y el watchdog no lo vigila (reporta
`watcher/supervisor/dashboard up` cada 20 s). Se documenta como fallo **F-3** del motor faulty.
Por instrucción del user **no se interviene**: ese equipo está en cambio de bróker.
