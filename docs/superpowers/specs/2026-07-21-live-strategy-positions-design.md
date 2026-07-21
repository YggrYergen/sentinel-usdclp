# Posiciones reales en vivo por estrategia — Design

- **Fecha:** 2026-07-21
- **Rama:** `alvaro`
- **Sección UI:** POSICIONES → pestaña ESTRATEGIA
- **Estado:** aprobado (brainstorming), pendiente plan de implementación

## Objetivo

La pestaña **POSICIONES → ESTRATEGIA** hoy muestra sesiones *forward-test*
(`/api/forward/sessions`) y su gráfico va a REVIEW (backtests). Los traders
piden que en su lugar quede el registro de las **estrategias conectadas
tomando posiciones reales en MT5**:

- cada estrategia listada con su agregado real (net, PF, WR, maxDD), seleccionable;
- cada posición con su estado **ABIERTA / CERRADA**, info completa, **spread al
  abrir y al cerrar**, profit y %;
- al clickear una posición, un **gráfico en vivo con replay** (equivalente al de
  trade-view, pero sobre datos reales en vivo en lugar de backtest).

Requisito adicional del usuario: mientras el sistema corre, cada posición que
las estrategias toman en MT5 debe quedar guardada en la base de datos con todo
el detalle **incluyendo el spread al que se abrió/cerró**, para poder auditar la
regla de "operar solo con spread mínimo" (en XAUUSD ≈ 0.5).

## Contexto existente (reutilizado, no reimplementado)

- `deals_raw` ya captura los deals de MT5 atribuidos por `magic` →
  `origin='strategy'` + `strategy_id`/`variant_id`
  (`sentinel_engine/live/deals_watcher.py`). Las posiciones reales de cada
  estrategia **ya se registran**.
- `GET /api/positions?origin=strategy` agrupa los deals en `PositionGroup`s vía
  `sentinel_engine/live/grouping.py` (`sentinel_engine/service/routers/positions.py`).
  Una posición está **abierta** cuando su `last_out`/`exit_time` es null.
- `GET /api/strategies/{id}/scorecard` ya calcula el bloque `real` con **net,
  pf, wr, payoff, net_per_day, maxdd_pct** desde los deals reales de la
  estrategia (`sentinel_engine/research/scorecard.py`).
- El panel de detalle por posición con **gráfico en vivo + replay** ya existe en
  la pestaña HUMANO (`buildHumanoDetailPanel` en `web/sections/positions.js`) y
  es reutilizable para reales.
- El ejecutor real `scripts/live/run_live_20.py` coloca las órdenes
  (`order_send` en OPEN/CLOSE) y **ya calcula `_current_spread(mt5, symbol)`**
  para el gate de spread mínimo. Es el único punto donde se conoce el spread
  exacto al momento del fill (el historial de deals de MT5 no trae spread).

## Brecha

- **El spread por posición no se persiste hoy.** `deals_raw` no tiene columna
  de spread; solo existe un store global de mínimo de XAUUSD
  (`sentinel_engine/live/spread_store.py`). Hay que capturarlo **de ahora en
  adelante** desde el ejecutor (las posiciones históricas mostrarán `--`).

## Diseño

### Componente 1 — Persistencia del spread por posición (backend nuevo)

- **Tabla nueva** en el registry (migración aditiva en
  `sentinel_engine/research/registry2.py`, patrón `_migrate_additive`):

  ```sql
  CREATE TABLE IF NOT EXISTS position_spread(
    position_id INTEGER PRIMARY KEY,
    ticket_open INTEGER,
    spread_open REAL,
    spread_open_min REAL,       -- running_min del spread_store al abrir
    spread_open_ts INTEGER,
    spread_close REAL,
    spread_close_ts INTEGER
  );
  ```

- **Helper** `record_position_spread(registry, position_id, *, ...)` (upsert
  idempotente por `position_id`): una escritura para el OPEN (setea
  `spread_open`, `spread_open_min`, `spread_open_ts`, `ticket_open`) y otra para
  el CLOSE (setea `spread_close`, `spread_close_ts`). El CLOSE hace UPDATE del
  registro existente sin pisar los campos de OPEN. Ubicación: junto a la lógica
  de spread live (p. ej. `sentinel_engine/live/spread_store.py` o un módulo
  hermano). Error path con las 3 vías de observabilidad (log + canal + estado),
  fail-safe: un error al registrar spread **nunca** aborta ni altera la orden.

- **`run_live_20.py`**: en cada OPEN confirmado (tras obtener `position_id` del
  resultado de `order_send`), llamar a `record_position_spread(...)` con el
  `_current_spread()` ya calculado para el gate y el `running_min` del
  `spread_store`. En cada CLOSE confirmado, registrar `spread_close` + ts. Se
  mantiene el modo **solo-lectura** de MT5 (no cambia qué/cómo se opera; el
  spread ya se lee hoy).

### Componente 2 — Endpoint (backend)

- `GET /api/positions` (`routers/positions.py`):
  - aceptar filtro opcional **`strategy_id`** (además de `origin`/`symbol`);
  - incluir `strategy_id` en cada grupo devuelto;
  - **LEFT JOIN** `position_spread` por `position_id` para exponer, por hijo:
    `spread_open`, `spread_open_min`, `spread_close`;
  - exponer `is_open` derivado (`last_out is null`) a nivel grupo/hijo.
  - Los campos de spread son null cuando no hay registro (posiciones históricas).
- El agregado por estrategia reutiliza el bloque `real` de
  `GET /api/strategies/{id}/scorecard` (net/PF/WR/maxDD). No se crea endpoint
  nuevo de agregación.

### Componente 3 — Frontend (pestaña ESTRATEGIA reescrita)

En `web/sections/positions.js`, `renderEstrategiaTab` / `loadSessions` se
reemplaza por un flujo de reales en vivo:

1. Listar estrategias conectadas (`GET /api/strategies`, las que tienen
   actividad `origin=strategy`) como tarjetas seleccionables, cada una con su
   scorecard real (net, PF, WR, maxDD) vía el scorecard existente.
2. Al seleccionar una estrategia → `GET /api/positions?origin=strategy&strategy_id=<id>`
   y renderizar sus posiciones (reutilizando la maquinaria de la pestaña HUMANO:
   vlist + grupos/hijos). Cada posición muestra:
   badge **ABIERTA/CERRADA**, lado, volumen, entrada/salida (ts + precio),
   **spread@open** (marcando visualmente si fue el mínimo:
   `spread_open <= spread_open_min + eps`), **spread@close**, profit y %.
3. Click en una posición → `buildHumanoDetailPanel(...)` (gráfico en vivo +
   replay), reutilizado tal cual.
4. Se retira de esta pestaña el botón "Ver en chart → REVIEW" (handoff a
   backtest) y el uso de `/api/forward/*`.

Se conservan las pestañas HUMANO e IA sin cambios.

### Componente 4 — Tests

- Registry: migración `position_spread` idempotente + `record_position_spread`
  (OPEN luego CLOSE, no pisa campos de OPEN; upsert idempotente).
- API: `/api/positions?strategy_id=...` filtra correctamente e incluye los
  campos de spread joinados; `strategy_id` presente en los grupos; posiciones
  sin registro de spread devuelven null.
- Ejecutor (dry-run): al abrir y cerrar registra el spread esperado en
  `position_spread` (extiende `tests/live/test_executor_dryrun.py` /
  `tests/scripts/test_run_live_20.py`).

## Restricciones

- Rama `alvaro`. Ediciones ≤500 LOC por cambio; observabilidad de 3 canales en
  cada error path.
- Cuentas reales **solo-lectura** en MT5: el ejecutor solo lee el spread; la
  captura no introduce ninguna llamada de trading nueva.
- Un fallo al registrar el spread nunca debe impedir ni alterar una orden
  (fail-safe, best-effort).

## No incluido (YAGNI)

- Backfill de spread para posiciones históricas (imposible: MT5 no lo guarda).
- Endpoint de agregación por estrategia dedicado (se reutiliza el scorecard).
- Cambios en las pestañas HUMANO / IA.
