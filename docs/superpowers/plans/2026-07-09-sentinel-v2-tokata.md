# SENTINEL V2 + TOKATA — Plan de implementación (rev. 2, 2026-07-09)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Spec fuente (vinculante):** `FABLE5_RESPONSE_V2_SENTINEL_TOKATA.md` (correcciones 2026-07-09 integradas).
> **Alcance de esta revisión (orden del usuario):** el requisito INMEDIATO a validar es **la UI madura + la interacción con posiciones/trades de las estrategias** (fases **M0–M3**, especificadas aquí a nivel de contrato para que los implementadores NO tengan que razonar sobre lo crítico). Todo lo demás (sim Tier-1, genoma v2, adaptador MT5, live, IA, gateway) queda en **BACKLOG REGISTRADO** (§B) — no urgente, NO implementar sin orden explícita, pero documentado con punteros para retomar sin pérdida de contexto ni drift.
> **Tracker (fuente de verdad de estado):** `~/.claude/brains/D--FOREX/project/tracker.md`, sección "SENTINEL V2+TOKATA — M/B" ("tracker is law"). Briefs/reports por tarea: `.superpowers/sdd/task-M*.md`.

**Goal:** Una UI madura dentro de la app existente: tercio izquierdo v2 pixel-exact intacto · navbar vertical cyberpunk central · 2/3 derecho con secciones Charts / Trade Review / Runs / Posiciones, donde los trades de distintas estrategias se distinguen por **nombre, color e identidad visual consistente**, sobre los datos TOKATA reales importados.

**Architecture:** `sentinel_engine/research/` (registry v2 SQLite WAL) + `sentinel_engine/ingest_tokata/` (importadores read-only) + endpoints FastAPI en `service/app.py` + secciones vanilla-JS lazy en `web/sections/` + lightweight-charts vendorizado. CERO cambios a scoring (`technical/macro/engine`) en M-phases — golden ni se acerca.

**Tech Stack:** Python 3.12 embebido · FastAPI+WS · SQLite(WAL) · pandas · TradingView lightweight-charts v4 (vendor, Apache-2.0) · uPlot (existente) · vanilla JS scripts clásicos (patrón app.js/lab.js/chat.js, NO ES modules) + CSS tokens.

## Global Constraints (cada tarea las hereda; el brief SDD las copia)
- Windows 10 Y 11; `pathlib` siempre; `encoding="utf-8"` explícito en TODO open(); sin APIs de versión de OS; sin WSL.
- `pytest tests/golden/test_parity.py -q` = 6/6 tras cada fase (M-phases no tocan scoring; el gate igual se corre).
- Cuentas reales READ-ONLY; **en M-phases NO existe ninguna ruta de ejecución de órdenes** (eso es B5).
- `D:/WebDev/TOKATA/**` es **SOLO LECTURA absoluta** — jamás escribir/mover/renombrar allí.
- OSS-only, sin CDNs (todo vendorizado), sin telemetría.
- Implementadores: **Sonnet 5 only**; máx 2 en paralelo, lanes A/B disjuntos (ver §W); prohibido tocar archivos fuera de la lista "Files owned" del brief.
- Commit por tarea: `feat(M<id>): <resumen>` + `Co-Authored-By` de la casa.
- UI: liviandad nunca a costa de frescura (ticks/sub-1 s cuando aplique, §M2.2); presupuesto perf: heap ≤60 MB con chart abierto, 1 sola rAF loop, tablas >200 filas virtualizadas, WS sólo diffs.

---

## §D — Contratos de diseño (NORMATIVOS — los implementadores copian, no deciden)

### D.1 Layout maestro (M1.1) — RECONCILIADO CON REPO REAL (verificado 2026-07-09)
**La estructura de 3 bandas YA EXISTE** en `web/index.html` (ui-rework; golden 6/6 + service 37/37, D38). NO se reconstruye — se EXTIENDE.
```
#app-body:  #left-column(~1/3) | #navbar(vertical .nav-btn) | #right-pane(~2/3, .right-section)
#left-column = 3× section.asset-panel (#panel-usdclp/nasdaq/gold, .v2-mount) = réplica v2 YA HECHA, INTACTA
```
- **`#left-column`** = la réplica v2 (paneles de los 3 assets con `.v2-mount`) = "el tercio izquierdo pixel-exact". NO se toca su rendering/HTML; sólo debe seguir vivo igual que hoy.
- **`#navbar`** (ya existe, vertical): hoy tiene 5 `.nav-btn[data-section]` = `chat·lab·regime·news·study` — **NO se eliminan** (los bloquea `tests/service/test_frontend.py::test_index_has_navbar_and_three_asset_panels`). M1.1 **AÑADE** al mismo navbar, mismo patrón: `charts·review·runs·positions` (después de los existentes). Estado activo reskin a `--accent-celeste` (barra 2 px + glow ≤8 px).
- **Patrón de sección (EXISTENTE — seguirlo, NO ES modules):** `app.js` ya hace click `.nav-btn` → `hidden=true` a todas `.right-section` → muestra `#section-${data-section}`. Cada sección nueva = `<section class="right-section" id="section-<name>" hidden>` en index.html + `<script src="/sections/<name>.js">` (script CLÁSICO, como app.js/lab.js/chat.js). Cada script expone `window.SENTINEL.sections["<name>"]={render(el),teardown()}`; M1.1 extiende el handler de `app.js` para llamar `render` al mostrar (lazy: 1er render al 1er show) y `teardown` al ocultar. Helpers en `web/lib/{badge,toast,fmt}.js` (scripts clásicos colgando de `window.SENTINEL`).

### D.2 Design tokens (`style.css` `:root` — valores EXACTOS)
```css
--bg-0:#0a0e14; --bg-1:#0d1117; --bg-2:#131a24; --bg-3:#1a2332;
--text-0:#c9d4e3; --text-1:#8b98ab; --text-2:#5c6a7d;
--accent-celeste:#00bfff; --accent-green:#26a69a; --accent-red:#ef5350; --accent-amber:#ffb020;
--long:#26a69a; --short:#ef5350; --neutral:#8b98ab;
--border:1px solid rgba(0,191,255,.18); --radius:6px;
--glow-sm:0 0 6px; /* SOLO interactivo/activo; blur máx 8px */
--font-mono:'Cascadia Mono',Consolas,monospace; --font-ui:'Segoe UI',system-ui,sans-serif;
--sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-6:24px;
```
Reglas duras (paleta CORREGIDA por usuario 2026-07-09): los realces cyberpunk usan **celeste eléctrico** (`--accent-celeste`) como acento dominante en TODAS las secciones (navbar, activos, focus, bordes); **verde/rojo clásicos de plataforma de trading** (`#26a69a`/`#ef5350`) EXCLUSIVAMENTE para semántica direccional (LONG/SHORT, PnL±, velas up/down); ámbar sólo warnings. Números/ids/precios SIEMPRE `--font-mono` con `font-variant-numeric:tabular-nums`; contraste ≥ 4.5:1; animaciones sólo `opacity/transform`, respetar `prefers-reduced-motion`; sin imágenes raster; scanline opcional = `background-image` estático.

### D.3 Identidad visual por estrategia (NORMATIVO — R distinguibilidad)
- **Paleta fija de 12 colores** (orden = índice; primeros 3 = celeste/verde/rojo por directiva de usuario): `#00bfff, #26a69a, #ef5350, #ffb020, #7c4dff, #ff6e40, #18ffff, #f8ff4d, #4dff91, #4d9fff, #ff9e4d, #ff4d6d`.
- **Asignación determinista** en registry: `color_idx = strategy_seq % 12` guardado en tabla `strategy` al registrar (estable para siempre; colisión >12 estrategias acepta repetición — el badge de familia desambigua). **Variantes** de una estrategia usan el MISMO color base; se distinguen por sufijo de nombre y, en overlays comparativos, por dash-pattern (`solid | dashed | dotted`, asignado por orden de selección).
- **display_name**: `"{familia} · {nombre} · {variant_suffix}"` — ej. `EMS · EMASAR v1 · M5_c2_sar3m3` (familia = código ledger EMS/SAP/PED/STR/STA). El nombre SIEMPRE visible junto al color (nunca color solo).
- **Badge de estrategia** (componente único `lib/badge.js`, reusado en TODAS las secciones): chip `[■ familia] nombre` — cuadrado 8 px del color + familia en mono 10 px + nombre; title = display_name completo.
- **Badge de fidelity** (colores fijos): `research`=gris `--text-2` · `screening`=ámbar · `real-tick`=celeste · `forward`=verde `--long` · `live-demo`=rojo `--short`. SIEMPRE visible junto a cualquier métrica (regla R25/R31: nunca un número sin su fidelity).

### D.4 Marcadores de trade sobre el chart (NORMATIVO)
- Entrada: triángulo (▲ LONG apunta arriba bajo la vela / ▼ SHORT apunta abajo sobre la vela), **relleno sólido del color de la estrategia**, 10 px.
- Salida: cuadrado hueco (borde 1.5 px color estrategia), 8 px, en la vela/precio de salida.
- Conexión entrada→salida: línea discontinua 1 px color estrategia al 60 % alpha (`lightweight-charts` series de línea con 2 puntos, o primitive custom).
- SL/TP del trade (si existen): líneas horizontales punteadas rojo/verde al 40 % alpha SOLO mientras el trade está seleccionado.
- Tooltip de marcador (hover): `display_name · LADO · vol · in: {ts} @ {px} · out: {ts} @ {px} · PnL: {±x.xx} · exit: {motivo} · MAE/MFE: {x}/{x}` — PnL coloreado long/short tokens.
- Trade **seleccionado**: marcadores escalan 1.4× + glow; el chart centra el rango `[ts_in − 100 barras, ts_out + 30 barras]` del TF activo.

### D.5 DDL registry v2 (EXACTO — M0.1 lo crea tal cual; `db = data/research.db`)
```sql
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS strategy(
  strategy_id TEXT PRIMARY KEY, strategy_seq INTEGER UNIQUE NOT NULL,
  name TEXT NOT NULL, familia TEXT NOT NULL, platform TEXT NOT NULL,        -- 'mt5'|'nt8'|'py'
  color_idx INTEGER NOT NULL, indicators_json TEXT NOT NULL DEFAULT '[]',
  param_schema_json TEXT NOT NULL DEFAULT '{}', defaults_json TEXT NOT NULL DEFAULT '{}',
  sweepable INTEGER NOT NULL DEFAULT 0, graduated INTEGER NOT NULL DEFAULT 0, notes TEXT);
CREATE TABLE IF NOT EXISTS variant(
  variant_id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL REFERENCES strategy,
  variant_seq INTEGER NOT NULL, params_delta_json TEXT NOT NULL,
  tf TEXT, instrumento TEXT, modo_salida TEXT,
  UNIQUE(strategy_id, variant_seq));
CREATE TABLE IF NOT EXISTS param_set(params_hash TEXT PRIMARY KEY, params_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS run(
  run_id TEXT PRIMARY KEY, variant_id TEXT REFERENCES variant, params_hash TEXT REFERENCES param_set,
  engine TEXT NOT NULL CHECK(engine IN('sentinel-replay','sentinel-sim','mt5-tester','nt8-manual')),
  fidelity TEXT NOT NULL CHECK(fidelity IN('research','screening','real-tick','forward','live-demo')),
  periodo_desde TEXT, periodo_hasta TEXT, modelo_sim TEXT, status TEXT,
  trades INTEGER, net REAL, pf REAL, wr REAL, payoff REAL, maxdd REAL, sharpe REAL,
  metrics_json TEXT NOT NULL DEFAULT '{}', preregistro_id TEXT,
  report_path TEXT, trades_path TEXT, equity_path TEXT, signal_history_path TEXT,
  fecha_corrida TEXT, seed INTEGER, config_hash TEXT, source_file TEXT, source_row INTEGER);
CREATE INDEX IF NOT EXISTS ix_run_variant ON run(variant_id);
CREATE TABLE IF NOT EXISTS trade(
  trade_id TEXT PRIMARY KEY, run_id TEXT REFERENCES run,       -- NULL ⇒ vivo (B4)
  origin TEXT NOT NULL DEFAULT 'strategy' CHECK(origin IN('human','strategy','ai')),
  origin_id TEXT, session_id TEXT, ts_in TEXT NOT NULL, ts_out TEXT,
  px_in REAL NOT NULL, px_out REAL, side TEXT CHECK(side IN('LONG','SHORT')),
  volume REAL, sl REAL, tp REAL, exit_reason TEXT, exit_reason_source TEXT,
  pnl REAL, mae REAL, mfe REAL, snapshot_ref TEXT, decision_trace_ref TEXT);
CREATE INDEX IF NOT EXISTS ix_trade_run ON trade(run_id);
CREATE TABLE IF NOT EXISTS preregistration(
  preregistro_id TEXT PRIMARY KEY, variant_id TEXT, hipotesis TEXT, mecanismo TEXT,
  metrica_primaria TEXT, umbral_exito TEXT, condicion_descarte TEXT, fecha TEXT, autor TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS forward_session(
  session_id TEXT PRIMARY KEY, strategy_id TEXT, variant_id TEXT, cuenta TEXT, perfil TEXT,
  inicio TEXT, fin TEXT, estado TEXT, source_file TEXT);
CREATE TABLE IF NOT EXISTS magic_allocation(
  magic INTEGER PRIMARY KEY, strategy_id TEXT NOT NULL, variant_id TEXT, asignado TEXT);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT, accion TEXT, detalle_json TEXT);
CREATE TABLE IF NOT EXISTS import_checksum(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, imported_at TEXT);
```
Magic: `magic = 100000 + strategy_seq*1000 + variant_seq` (validar `strategy_seq<900`, `variant_seq<1000`); rango 900000–999999 reservado IA (B5); sin match ⇒ human.

### D.6 Contratos de endpoints (EXACTOS — JSON de respuesta; prefijo `/api`)
Errores: siempre `{"error":{"code":str,"message":str}}` con HTTP 4xx/5xx; nunca traceback al cliente.
```
GET /api/strategies
  → {"strategies":[{"strategy_id","name","familia","platform","color_idx","display_color":"#hex",
     "n_variants":int,"n_runs":int,"sweepable":bool,"graduated":bool}]}
GET /api/runs?strategy_id&variant_id&instrumento&engine&fidelity&desde&hasta&order_by=net|pf|wr|maxdd|sharpe|fecha_corrida&dir=asc|desc&limit=100&offset=0
  → {"total":int,"rows":[{"run_id","variant_id","display_name","color_idx","familia","instrumento",
     "engine","fidelity","periodo_desde","periodo_hasta","modelo_sim","trades","net","pf","wr",
     "payoff","maxdd","sharpe","fecha_corrida","report_path"}]}
GET /api/runs/{run_id} → fila completa + {"preregistration":{...}|null,"artifacts":{"report_path",...}}
GET /api/runs/{run_id}/trades → {"trades":[{"trade_id","ts_in","ts_out","px_in","px_out","side",
     "volume","sl","tp","pnl","mae","mfe","exit_reason","exit_reason_source"}]}   // orden ts_in asc
GET /api/bars?symbol&tf=M1|M2|M5|M10|M15&from=iso&to=iso&max_points=3000
  → {"symbol","tf","decimated":bool,"bars":[[ts_epoch_s,o,h,l,c,v],...]}          // lake, causal
GET /api/forward/sessions → {"sessions":[{"session_id","display_name","color_idx","cuenta","perfil",
     "inicio","fin","estado","n_trades","pnl_total"}]}
GET /api/forward/{session_id}/trades → mismo shape que /runs/{id}/trades + "origin"
WS  canal "ticks:{SYMBOL}" (suscripción por mensaje {"sub":"ticks:XAUUSD"})
  → {"ch":"ticks:XAUUSD","t":epoch_ms,"bid":float,"ask":float}   // loop on-change ~250 ms, sólo con ≥1 suscriptor
```
Implementación `/api/bars`: leer del lake (`lake/store.read_bars`), resample M2/M10 desde M1 si el TF no existe nativo; si `len>max_points` decimar LOD (agregación OHLC por buckets, `decimated:true`). Timestamps SIEMPRE epoch UTC.

### D.7 Especificación por sección (comportamiento EXACTO)
**CHARTS (`sections/charts.js`, acento celeste):** toolbar superior: select símbolo (USDCLP/NQ100/XAUUSD), botones TF `M1 M2 M5 M10 M15` (grupo exclusivo), toggle "ticks en vivo", multiselect de overlays de indicador (v1: EMA9/21/50, BB, sin osciladores — subpanes llegan en B2). Chart lightweight-charts: velas `--long`/`--short`, crosshair magnet, pan/zoom rueda+drag, hover tooltip flotante (`--bg-3`, borde token) con `ts · O H L C · vol` + valores de overlays. "Ticks en vivo" ON ⇒ suscribe WS y `candleSeries.update()` la vela en curso (close=bid; high/low=max/min). Carga por ventanas: al pan-izquierda cerca del borde, fetch del bloque anterior y `setData` merge. Estados: loading=skeleton pulse; error=toast + retry; sin datos="Sin barras para {symbol} {tf}".
**TRADE REVIEW (`sections/review.js`, acento celeste):** layout 2 columnas (`320px | 1fr`). Izquierda: select de run (buscable, agrupado por estrategia con badge D.3) + lista **virtualizada** de trades (fila: `#n · side coloreado · ts_in corto · PnL coloreado · exit_reason abreviado`). Derecha: el mismo componente chart de CHARTS (módulo compartido `lib/chart.js` — UNA implementación) + header del run (badge estrategia + badge fidelity + ventana + modelo_sim + métricas resumen net/pf/wr/maxdd). Interacción: click o teclas `j/k` navegan trades → selección según D.4 (centrado, SL/TP, glow); TF conmutable manteniendo el trade ancla (recentra por timestamps); TODOS los trades del run se muestran como marcadores tenues (40 % alpha) y el seleccionado a plena intensidad.
**RUNS (`sections/runs.js`, acento celeste):** barra de filtros (estrategia multiselect con badges, instrumento, engine, fidelity, rango fechas) + tabla virtualizada ordenable (columnas: badge estrategia · variant_id mono · instr · fidelity badge · trades · net · PF · WR% · payoff · maxDD · sharpe · fecha; números mono tabular, net/PF coloreados por signo). Click fila ⇒ drawer lateral derecho (grid de métricas completo + link a `.htm` evidencia `file:///` + botón "Ver trades → REVIEW" que navega con el run preseleccionado). Checkbox por fila (máx 6) + botón "Comparar" ⇒ modal con **uPlot**: equity curves superpuestas si existe `equity_path`, si no barras comparativas de net/PF/WR/maxDD; color = estrategia, dash = orden de selección (D.3).
**POSICIONES (`sections/positions.js`, acento celeste):** tabs `HUMANO · ESTRATEGIA · IA` (v1: HUMANO e IA muestran empty-state "Disponible al activar live/IA (B4/B5)" — el tab EXISTE ya, la taxonomía es de primer nivel). Tab ESTRATEGIA: lista de `forward_session` (card por sesión: badge estrategia, perfil, estado, PnL total coloreado, n trades) → click ⇒ tabla de trades de la sesión (mismas columnas que REVIEW) + botón "Ver en chart → REVIEW". Botón "Re-importar TOKATA" (POST `/api/ingest/tokata`, corre importadores idempotentes y refresca).
**Transversal:** navegación entre secciones con estado (`app.js` mantiene `appState={selectedRun, selectedTrade, symbol, tf}` y las secciones lo leen de `ctx`); toasts (`lib/toast.js`) esquina inferior derecha; NUNCA fetch de histórico completo; sin frameworks.

### D.8 Mapeo de ingesta TOKATA (columna→columna, M0.2)
Fuentes (READ-ONLY, rutas por config `tokata_root=D:/WebDev/TOKATA`):
- `backtest_results/mt5_ledger.csv` (sep `;`) → `run`: run_id→run_id; variant_id→variant_id (creando `strategy` por `familia` con los códigos vistos EMS/STR/STA/SAP/PED y `variant` con delta vacío si no hay preregistro); params_hash→param_set(params_json='{}' si desconocido); tipo_corrida→fidelity (`screening`→screening, `validacion|validación`→real-tick, `forward`→forward, otro→research); engine='mt5-tester'; resto de columnas 1:1 (trades,net,pf,wr,payoff,maxdd,sharpe,report_path,fecha_corrida,periodo_desde/hasta,status) + source_file/source_row.
- `backtest_results/preregistro.csv` (sep `;`) → `preregistration` 1:1 + raw_json con la fila completa.
- `mt5/reports/*_signals.csv` → `trade` (run_id matcheado por variant_id+periodo del nombre de archivo; si ambiguo, registrar en audit_log y saltar): entradas/salidas del EA, exit_reason del CSV, `exit_reason_source='signals_csv'`.
- `backtest_results/forward_*.csv` + `forward_daily/` → `forward_session` + `trade` (origin='strategy', run_id NULL, session_id set).
- `.htm`: NO parsear en M0 (report_path ya viene del ledger); parsing de métricas faltantes = backlog B3.
Reglas: idempotencia por `import_checksum` (sha256; si igual ⇒ skip); encoding `utf-8-sig` con fallback `latin-1`; separador `;`; decimales con coma → punto si aparece; TODA fila inparseable se registra en audit_log (accion='import_skip') y NO aborta el import; `ImportReport{files, rows_new, rows_skipped, errors[]}` retornado y logueado.

### D.9 Preservación del tercio izquierdo (M1.1 gate) — CORREGIDO 2026-07-09
El tercio izquierdo = `#left-column` (3 `section.asset-panel`/`.v2-mount`), YA construido y verificado (golden 6/6, service 37/37, D38). NO hay re-implementación pendiente. "Pixel-exact" = estado ACTUAL de `#left-column` en HEAD (NO `baseline-pre-revamp`, que precede al stack `sentinel_engine/service`). Gate: (1) `test_frontend.py` verde (3 asset-panels + 5 sections originales intactos); (2) `#left-column` renderiza y actualiza en vivo idéntico a antes; (3) el implementador NO modifica HTML/CSS/JS de rendering de `#left-column` ni de los asset-panels; sólo añade tokens que no alteren su apariencia.

---

## §W — Flujo agéntico dinámico (el orquestador ejecuta esto)
1. Leer tracker → elegir siguiente(s) tarea(s) OPEN con `deps` satisfechas.
2. **Máx 2 subagentes simultáneos, SOLO lanes distintos (A≠B), archivos disjuntos garantizados por las listas "Files" de cada tarea.** Pares pre-aprobados: M0.1∥M1.1 · M0.2∥M1.1 · M0.3(A)∥M1.2(B) · M2.1(A)∥M1.2(B) · M3.x(B)∥(nada de A pendiente ⇒ solo). Cualquier otro par: verificar disyunción antes de despachar.
3. Brief SDD por tarea (`.superpowers/sdd/task-M<id>-brief.md`): copia Global Constraints + los §D relevantes COMPLETOS (el implementador no abre el spec) + Files owned + tests + gate + prohibiciones. Despachar **Sonnet 5** (effort high para M0/M2.1, medium para UI).
4. Retorno ⇒ correr gate de tarea + suite tocada + golden si adyacente. Verde ⇒ commit + `[x]` en tracker + report SDD. Rojo ⇒ strike (2º: re-brief esfuerzo↑; 3º: BLOCKED, seguir con otra).
5. Reviews **batched en frontera de fase** (memoria: review-cadence-batched): gate de fase + code-review batch + handoff brain.
6. **Brain:** crumb por turno; handoff completo del thread en cada frontera de fase y ante threshold; si contexto se agota ⇒ handoff + spawn-continue.
7. Fin de M3 (o bloqueo): reporte final — avance, faltantes (=§B intacto), evidencia, tracker/brain al día. **NO iniciar §B sin orden explícita del usuario.**

**Lanes:** **A (backend)** = `sentinel_engine/research/**`, `sentinel_engine/ingest_tokata/**`, `sentinel_engine/service/app.py`, `sentinel_engine/service/stream.py`, `scripts/**`, `tests/{research,service}/test_*.py` (backend). **B (frontend)** = `web/**`, `tests/service/test_web_*.py` (y `test_frontend`/`test_ui_coverage` deben seguir verdes). `app.py`/`stream.py` son SIEMPRE de A; B consume contratos D.6 tal cual (por eso son normativos).

---

## FASE M0 — Datos (Lane A)
**Pre-req de fase (orquestador, antes de despachar):** cerrar el pendiente D35 — matar python huérfanos; `python -m pytest tests/opt/test_fast_replay.py -rA -q > temp/ff.log 2>&1` y `python -m pytest tests/opt/test_study.py -m "not slow" -rA -q > temp/st.log 2>&1` (SIN pipes); leer colas de logs; SOLO si ambos verdes ⇒ commit G1 (5 archivos) y commit PAR (4 archivos) como estaba definido; si G1 rojo ⇒ commitear SOLO PAR y registrar G1 como BLOCKED en tracker.

### Task M0.1: Registry v2
**Files:** Create `sentinel_engine/research/__init__.py`, `sentinel_engine/research/registry2.py`, `tests/research/__init__.py`, `tests/research/test_registry2.py`.
**Produces:** `ResearchRegistry(db_path: Path)` — crea el DDL D.5 EXACTO en `__init__`; métodos: `upsert_strategy(name,familia,platform)->strategy_id` (asigna `strategy_seq` autoincremental y `color_idx=seq%12`), `upsert_variant(strategy_id,variant_id,params_delta,tf,instrumento,modo_salida)`, `upsert_param_set(params_hash,params_json)`, `insert_run(dict)->run_id`, `insert_trades(run_id,list[dict])`, `insert_preregistration(dict)`, `upsert_forward_session(dict)`, `query_runs(**filtros de D.6)->list[dict]` (+total), `query_strategies()->list[dict]`, `allocate_magic(strategy_id,variant_id)->int` (fórmula D.5 + validaciones), `audit(actor,accion,detalle)`, `checksum_seen(path,sha)->bool`.
- [ ] Escribir tests fallando: roundtrip por tabla; `allocate_magic` determinista y validado; `query_runs` con filtros/orden/paginación; WAL activo; UNIQUE respetados.
- [ ] Implementar mínimo → `pytest tests/research/test_registry2.py -q` PASS → commit `feat(M0.1): registry v2`.
**Gate:** suite research verde; golden 6/6 (no toca scoring).

### Task M0.2: Importadores TOKATA
**Files:** Create `sentinel_engine/ingest_tokata/{__init__.py,ledger.py,preregistro.py,signals.py,forward.py,runner.py}`, `tests/research/test_ingest_tokata.py`, `tests/research/fixtures/` (muestras COPIADAS pequeñas de los CSV reales, ≤20 filas c/u).
**Consumes:** M0.1. **Produces:** `import_all(tokata_root: Path, registry) -> ImportReport` según mapeo **D.8 completo** (el brief lo copia literal).
- [ ] Tests fallando: mapeo ledger→run correcto (fila real de fixture); fidelity mapping; idempotencia (2ª corrida ⇒ rows_new=0); fila corrupta ⇒ skip+audit, no abort; separador `;` + coma decimal.
- [ ] Implementar → verde → correr `python -m sentinel_engine.ingest_tokata.runner --root D:/WebDev/TOKATA` REAL → commit.
**Gate:** import real completo sin excepción; `query_strategies()` muestra familias EMS/STR/STA/SAP/PED con colores asignados; `query_runs()` pobladas; TOKATA intacto (0 escrituras).

### Task M0.3: Endpoints de datos (D.6 sin /bars ni ticks)
**Files:** Modify `sentinel_engine/service/app.py`; Create `tests/service/test_api_research.py`.
**Produces:** `/api/strategies`, `/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/trades`, `/api/forward/sessions`, `/api/forward/{id}/trades`, `POST /api/ingest/tokata` — shapes EXACTOS D.6; `display_color` resuelto desde la paleta D.3; errores en formato normativo.
- [ ] Tests fallando por endpoint (shape, filtros, orden, paginación, error 404 formato) → implementar → verde → commit.
**Gate:** `pytest tests/service -q` verde (incluye suite existente 37/37); golden 6/6. **Frontera M0:** review batch + handoff brain.

## FASE M1 — Shell UI + datos de mercado
### Task M1.1: Layout 3 bandas + navbar (Lane B)
**Files:** Modify `web/{index.html,app.js,style.css}`; Create `web/lib/{badge.js,toast.js,fmt.js}`, `web/sections/.gitkeep`, `tests/service/test_web_layout.py`.
**Produces:** D.1 + D.2 + D.3(badges) EXACTOS: grid 3 bandas, `#v2-pane` intacto (D.9), navbar con los 6 ítems y estados, loader lazy de secciones (`mount/unmount`), tokens en `:root`, `appState` compartido.
- [ ] Test DOM servido (grid presente, navbar ítems, #v2-pane contiene la réplica) → implementar → verde → commit.
**Gate:** checklist D.9 (visual, con el usuario o capturas) + navegación entre placeholders funciona + panel izquierdo sigue actualizando en vivo.

### Task M1.2: `/api/bars` + WS ticks (Lane A)
**Files:** Modify `sentinel_engine/service/app.py`, `sentinel_engine/service/stream.py`; Create `tests/service/test_bars_ticks.py`.
**Produces:** D.6 `/api/bars` (lake, resample M2/M10 desde M1, LOD, epoch UTC) + canal `ticks:{SYMBOL}` (loop 250 ms on-change, sólo con suscriptores, read-only `symbol_info_tick`, apagado limpio).
- [ ] Tests: shape bars; decimación >max_points; resample M10 correcto (suma vol, OHLC agregado); suscripción/dessuscripción WS; sin suscriptores ⇒ sin polling.
**Gate:** tests verdes; tick→WS <500 ms en test de integración local (si MT5 no disponible en CI, mock con marca `requires_mt5` y verificación manual).

### Task M1.3: Componente chart compartido (Lane B)
**Files:** Create `web/vendor/lightweight-charts/lightweight-charts.standalone.production.js` (vendorizar v4.x + LICENSE), `web/lib/chart.js`, `web/sections/charts.js`; Modify `style.css` (bloque charts).
**Produces:** `lib/chart.js` exporta `createChart(el,{symbol,tf})` con API: `setWindow(from,to)`, `setTF(tf)`, `addTradeMarkers(trades, colorHex, {dim})`, `selectTrade(trade)` (D.4 completo), `enableTicks(ws)`, `addOverlay(id, series)`, `destroy()`. Sección CHARTS = spec D.7 completo (toolbar, hover, pan-fetch incremental, estados vacío/carga/error, toggle ticks).
- [ ] Implementar → verificación manual con checklist R1–R5 (velas, TF switch, pan histórico, zoom, hover completo) → commit.
**Gate:** checklist R1–R5 + vela viva con ticks ON + heap ≤60 MB (DevTools) + panel izquierdo no se degrada. **Frontera M1:** review + handoff.

## FASE M2 — Las secciones de estrategia (Lane B; A libre)
### Task M2.1: Sección RUNS
**Files:** Create `web/sections/runs.js`, `web/lib/vtable.js` (tabla virtualizada genérica: render por viewport, sort client-side de la página, columnas configurables); Modify `style.css`.
**Produces:** spec D.7-RUNS completo (filtros, tabla, drawer, comparación uPlot con colores/dash D.3, badges fidelity SIEMPRE).
**Gate:** con los datos TOKATA reales importados: filtrar por familia, ordenar por PF, abrir drawer con link a `.htm`, comparar 3 variantes visualmente distinguibles por color+dash+nombre.

### Task M2.2: Sección TRADE REVIEW
**Files:** Create `web/sections/review.js`; Modify `style.css`.
**Consumes:** `lib/chart.js` (M1.3), `/api/runs/*` (M0.3), `/api/bars` (M1.2). **Produces:** spec D.7-REVIEW completo (lista virtualizada, j/k, selección D.4, TF conmutable con ancla, todos-los-trades tenues + seleccionado intenso, header con badges).
**Gate (el hito del requisito inmediato):** recorrer trade-a-trade una corrida EMASAR real importada sobre el chart, con identidad visual de estrategia correcta, motivo de salida y PnL visibles, en M1 y M5.

### Task M2.3: Sección POSICIONES
**Files:** Create `web/sections/positions.js`; Modify `style.css`.
**Produces:** spec D.7-POSICIONES completo (tabs taxonomía con empty-states honestos, cards forward_session, trades por sesión, re-importar).
**Gate:** sesiones forward TOKATA reales visibles con badge/color; navegación a REVIEW funciona. **Frontera M2:** review + handoff.

## FASE M2+ — Capacidades prioritarias (orden usuario 2026-07-09: backtest por variante, forward-walk velocidad variable, gestión de estrategias, crear variantes — versión mínima-costo)

### Task M2.4: Endpoints de gestión (Lane A)
**Files:** Modify `sentinel_engine/service/app.py`; Create `tests/service/test_manage_api.py`.
**Produces:** `POST /api/variants {strategy_id, variant_suffix, params_delta, tf, instrumento, modo_salida}` → crea variante en registry (variant_id = `{familia}_{instr}_{suffix}`, valida contra param_schema si existe, audit) → `{"variant_id"}`; `POST /api/strategies/{id}/estado {estado: activa|pausada|graduada}` → flag en registry + audit_log; errores formato D.6.
**Gate:** tests verdes; crear variante duplicada ⇒ 409.

### Task M2.5: Backtest-lite por variante (Lane A) — adelanto mínimo de B1
**Files:** Create `sentinel_engine/sim/__init__.py`, `sentinel_engine/sim/lite.py`, `sentinel_engine/strategies/__init__.py`, `sentinel_engine/strategies/emasar.py`, `tests/sim/test_lite.py`; Modify `sentinel_engine/service/app.py` (`POST /api/backtest`, `GET /api/jobs/{id}`).
**Produces:** `run_backtest_lite(policy, symbol, tf, desde, hasta, costs) -> (run_dict, trades)` — motor de barras mínimo sobre el lake (fill next-open, spread const por instrumento, comisión 0 default, **SL-first conservador** intrabar, sin apalancamiento de validación de bróker aún); `EmasarPolicy(params)` portada de `D:/WebDev/TOKATA/mt5/scripts/emasar_ref.py` (LEER solamente); `POST /api/backtest {variant_id, symbol, tf, desde, hasta}` → job en `BackgroundTasks` (cola de 1, secuencial) → al terminar inserta run (engine=`sentinel-sim`, fidelity=`research`) + trades en registry; `GET /api/jobs/{id}` → `{status: queued|running|done|error, run_id?}`. Determinismo: mismo input ⇒ mismos trades.
**Gate:** backtest real de una variante EMASAR sobre lake XAUUSD (ventana corta) produce run+trades consultables por `/api/runs`; determinismo verificado en test.

### Task M2.6: Forward-walk playback velocidad variable (Lane B)
**Files:** Modify `web/lib/chart.js`, `web/sections/{charts.js,review.js}`, `style.css`.
**Produces:** modo playback client-side sobre los datos ya fetcheados: controles `▶/⏸ · velocidad 1×/5×/20×/60×/MAX · scrub-slider · ts actual`; las velas se van formando secuencialmente (setData incremental por timer, 1 vela por tick de reloj × velocidad) y los **marcadores de trades aparecen/cierran en su timestamp** (entrada al llegar ts_in, conexión+salida al llegar ts_out); disponible en CHARTS (sin trades) y REVIEW (con los trades del run seleccionado); ESC o cambio de sección detiene y restaura vista completa.
**Gate:** reproducir una corrida EMASAR a 5× y a MAX viendo posiciones abrirse/cerrarse conectadas sobre el gráfico.

### Task M2.7: UI de gestión de estrategias/variantes (Lane B)
**Files:** Modify `web/sections/{runs.js,positions.js}`, `style.css`.
**Consumes:** M2.4/M2.5. **Produces:** botón "＋ Variante" (form schema-driven desde param_schema; POST /api/variants; toast éxito con variant_id); botón "▶ Backtest" por variante (modal símbolo/tf/ventana → POST /api/backtest → polling job → al terminar toast + refresh RUNS); controles de estado por estrategia en POSICIONES (activa/pausada/graduada, badge de estado junto al badge de estrategia, cambio → POST estado + audit); las graduadas se listan primero con marca `★`.
**Gate (hito usuario):** flujo completo desde la UI: crear variante → correrle backtest → verla en RUNS → recorrer sus trades en REVIEW → reproducirla en playback → marcar la estrategia como graduada.

## FASE M3 — Madurez y cierre
### Task M3.1: Pulido transversal UI (Lane B)
**Files:** Modify `web/**` (los suyos), Create `docs/superpowers/specs/2026-07-09-ui-style-guide.md` (captura D.2–D.4 + capturas de pantalla como guía viva).
**Produces:** pasada de consistencia contra D.2/D.3 (un acento por sección, mono tabular en todo número, contraste, focus-visible en todo interactivo, tooltips title en todo elemento truncado, empty/loading/error en TODA sección), atajos documentados en un `?` overlay.
**Gate:** checklist de estilo (en el brief) 100 %; revisión visual del usuario.

### Task M3.2: Cierre de fase inmediata (orquestador, no subagente)
- [ ] Suite completa: `pytest tests/ --ignore=tests/opt -q` + `pytest tests/golden -q` + `pytest tests/research tests/service -q` — todo verde.
- [ ] Verificación en navegador con el usuario (D.9 + R1–R5 + gates M2.x).
- [ ] Tracker: M-phases `[x]`, §B intacto como faltante registrado; handoff brain completo; reporte final con evidencia.

---

## §B — BACKLOG REGISTRADO (diferido — NO implementar sin orden explícita)
> Cada ítem conserva su diseño completo en el spec (§ referenciada). Al activarse, se expande a fase M-style con briefs SDD. Este registro ES el mecanismo anti-drift para retomar.
- **B1 · Tier-1 sim + EMASAR + sweeps + signal_history** — spec §2.3–2.5: `sim/{policy,broker_sim,costs}.py` (OrderIntent/BarContext/StrategyPolicy/ExitPolicy; fills next-open±slip, SL-first, R28), port `emasar_ref.py`, `fidelity_audit` (±1 barra/±%PnL/conteo; testear 2–3 sets), `sweep.py` sobre study/fleet con pre-registro obligatorio, `record_snapshots`→`signal_history/{run}.parquet`, `SignalPanelPolicy`. Dep: M0. Baseline study (spec D-V2-12) entra aquí como B1.0.
- **B2 · Genoma v2 + regime** — spec §3: `features/` + harness PIT, `graph_v1` ancla BYTE-EXACTA (regla P1 de cutover), catálogo (supertrend/sar/ao/ac/adx/chop/orb/sr_zones/...), search-space desde grafo + screening IC + sparsity cap, macro v2 `lagged_beta`+gate coherencia (metadata-first), regime labeler P6, estudio comparativo XAUUSD 5 lentes (§3.5) + diff PROPUESTO. Dep: B1 (signal_history).
- **B3 · Adaptador MT5 + funnel** — spec §2.4: wrapper `gen_variant/batch_runner` in-situ (secuencial, TOKATA intacto), compilación asistida IA/MetaEditor-CLI (manual NO aceptable — decisión §9.4), promote-to-validation, fidelity ladder en UI, parse `.htm` métricas faltantes. Dep: M0, B1.
- **B4 · Live demo + procedencia viva** — spec §4.3: poller read-only demo, clasificación por `magic_allocation`, tabs HUMANO/IA se pueblan, `forward_session` en vivo, graduación R33 con criterio pre-registrado. Dep: M0.
- **B5 · Gateway + IA multi-rol** — spec §4.4+§7: gateway demo-only (allowlist+trade_mode+guardarraíles+kill-switch+**test CI de imports de orden**), tools IA (lectura→run_backtest→propose_order), calendario económico precedido por **subagente de investigación de fuentes gratis** (decisión §9.2). Dep: B4.
- **B6 · Charts avanzado** — subpanes de osciladores (AO/AC/Momentum), overlays de features B2 con params efectivos (R6 completo), replay con cursor temporal + scrubbing de signal_history. Dep: B1/B2.

## Self-review (rev. 2, hecho)
- Requisito inmediato cubierto de punta a punta: datos (M0) → shell+chart (M1) → distinguir/recorrer/comparar trades por estrategia con identidad visual normada (M2, D.3/D.4/D.7) → madurez (M3). AI/sim/live correctamente FUERA y registrados (§B) con deps y § del spec.
- Nada crítico queda a criterio del implementador: DDL, JSON, tokens, paleta, marcadores, mapeo de ingesta y comportamiento por sección son normativos (§D) y se copian al brief.
- Consistencia de nombres verificada: `ResearchRegistry`, `import_all`, `lib/chart.js` API, `appState`, rutas `/api/*` usadas idénticas en M0.3/M1.3/M2.x.
