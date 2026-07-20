"""sentinel_engine.research.registry2 — ResearchRegistry (M0.1).

SQLite/WAL-backed registry for research data: strategies, variants,
param sets, runs, trades, preregistrations, forward sessions, magic-number
allocation, audit log, and import-checksum bookkeeping.

DDL is copied EXACTLY from
`docs/superpowers/plans/2026-07-09-sentinel-v2-tokata.md` §D.5 — do not
redesign the schema here. Default db path is `data/research.db`, always
injectable via the constructor.

Windows-safe: `pathlib.Path` throughout, `encoding="utf-8"` on every text
`open()` (registry itself uses `sqlite3`, which has no encoding param, but
any helper here that opens text files must specify it).
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

_TF_FROM_VARIANT_ID_RE = re.compile(r"_(M\d+)_")

DEFAULT_DB_PATH = Path("data/research.db")

# 12-color fixed palette (D.3), index = strategy_seq % 12.
STRATEGY_PALETTE: tuple[str, ...] = (
    "#00bfff", "#26a69a", "#ef5350", "#ffb020", "#7c4dff", "#ff6e40",
    "#18ffff", "#f8ff4d", "#4dff91", "#4d9fff", "#ff9e4d", "#ff4d6d",
)

_DDL = """
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
  trade_id TEXT PRIMARY KEY, run_id TEXT REFERENCES run,       -- NULL => vivo (B4)
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
CREATE TABLE IF NOT EXISTS deals_raw(
  ticket INTEGER PRIMARY KEY, position_id INTEGER, symbol TEXT, side TEXT,
  volume REAL, price REAL, profit REAL, magic INTEGER, time INTEGER, entry_type TEXT);
"""

_META_DDL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""

# B6: `jobs` table (CT-4 backtest job queue). Additive, own CREATE TABLE IF
# NOT EXISTS since it didn't exist before B6 -- same pattern as `_META_DDL`.
_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, params_json TEXT NOT NULL,
  status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0.0,
  run_id TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
"""

# C1a: `news_items` table (CT-5 news feed cache). Additive, own CREATE
# TABLE IF NOT EXISTS -- same pattern as `_JOBS_DDL`.
_NEWS_ITEMS_DDL = """
CREATE TABLE IF NOT EXISTS news_items(
  id TEXT PRIMARY KEY, ts INTEGER, source TEXT, title TEXT, url TEXT,
  symbols_json TEXT, kind TEXT, impact TEXT);
"""

_RUN_COLUMNS = (
    "run_id", "variant_id", "params_hash", "engine", "fidelity",
    "periodo_desde", "periodo_hasta", "modelo_sim", "status",
    "trades", "net", "pf", "wr", "payoff", "maxdd", "sharpe",
    "metrics_json", "preregistro_id", "report_path", "trades_path",
    "equity_path", "signal_history_path", "fecha_corrida", "seed",
    "config_hash", "source_file", "source_row", "fidelity_ref",
)

_TRADE_COLUMNS = (
    "trade_id", "run_id", "origin", "origin_id", "session_id", "ts_in",
    "ts_out", "px_in", "px_out", "side", "volume", "sl", "tp",
    "exit_reason", "exit_reason_source", "pnl", "mae", "mfe",
    "snapshot_ref", "decision_trace_ref", "signal_id", "ficha",
)

def _normalize_ts_iso_utc(ts: str | None) -> str | None:
    """Defect D (Wave-2 plan 2026-07-10): `/trades` must emit ts_in/ts_out
    as unambiguous ISO-8601 UTC (`2026-01-11T20:00:00Z`), never an MT5
    dotted string (`2026.01.11 20:00:00`) nor a bare ISO string with no
    zone -- `new Date('2026.01.11 20:00:00')` parses as browser-LOCAL time
    in JS, offsetting markers from the UTC candle axis. The MT5 tester
    times matched lake bars byte-identically (Wave-1 fidelity work) -> the
    source is effectively UTC already; this REFORMATS ONLY, never shifts
    the clock (no tz conversion, just dotted/bare -> `...Z` string ops)."""
    if not ts:
        return ts
    s = str(ts).strip()
    if "." in s and ":" in s and "T" not in s:
        # MT5 dotted: "2026.01.11 20:00:00" -> "2026-01-11T20:00:00"
        date_part, _, time_part = s.partition(" ")
        s = date_part.replace(".", "-") + "T" + time_part
    if s.endswith("Z"):
        return s
    if "+" in s[10:] or s.count("-") > 2:
        # already carries an explicit offset -- leave it alone (not
        # expected in this codebase's data, but don't mangle it).
        return s
    return s + "Z"


_PREREG_COLUMNS = (
    "preregistro_id", "variant_id", "hipotesis", "mecanismo",
    "metrica_primaria", "umbral_exito", "condicion_descarte", "fecha",
    "autor", "raw_json",
)

_FORWARD_SESSION_COLUMNS = (
    "session_id", "strategy_id", "variant_id", "cuenta", "perfil",
    "inicio", "fin", "estado", "source_file",
)

_RUN_ORDER_COLUMNS = {"net", "pf", "wr", "maxdd", "sharpe", "fecha_corrida"}


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class ResearchRegistry:
    """SQLite/WAL registry for SENTINEL research data (strategies, variants,
    runs, trades, ...). See module docstring / plan §D.5 for schema."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(_DDL)
            conn.commit()
            self._migrate_additive(conn)
        finally:
            conn.close()

    def _migrate_additive(self, conn: sqlite3.Connection) -> None:
        """Additive-only schema evolution (never rewrites D.5's DDL): adds
        `strategy.estado` (M2.4 — activa|pausada|graduada, alongside the
        pre-existing `graduated` bool) if the column isn't there yet. Also
        adds `trade.signal_id`/`trade.ficha` (EMASAR V1 MT5-fidelity
        integration, design spec 2026-07-10, Component 4 — nullable, NULL
        for pre-existing single-exit sim trades) and widens the `run.engine`
        / `run.fidelity` CHECK constraints to admit 'mt5-import' /
        'mt5-htm' (SQLite has no ALTER for CHECK constraints, so this one
        rebuilds the `run` table: rename -> recreate with the D.5 DDL plus
        the two new enum members -> copy rows -> drop the renamed table)."""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(strategy)").fetchall()}
        if "estado" not in cols:
            conn.execute("ALTER TABLE strategy ADD COLUMN estado TEXT NOT NULL DEFAULT 'activa'")
            conn.commit()

        trade_cols = {row[1] for row in conn.execute("PRAGMA table_info(trade)").fetchall()}
        if "signal_id" not in trade_cols:
            conn.execute("ALTER TABLE trade ADD COLUMN signal_id TEXT")
            conn.commit()
        if "ficha" not in trade_cols:
            conn.execute("ALTER TABLE trade ADD COLUMN ficha TEXT")
            conn.commit()

        run_engine_check = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='run'"
        ).fetchone()[0]
        if "mt5-import" not in run_engine_check:
            # SQLite rewrites OTHER tables' FK-reference text (e.g.
            # `trade.run_id REFERENCES run`) when `run` is renamed below --
            # `trade`'s FK ends up pointing at the transient
            # `run_pre_mt5import` name. Rebuild `trade` too (verbatim DDL,
            # just re-pointed at `run`) right after so its FK is correct.
            trade_sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='trade'"
            ).fetchone()[0]
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.executescript(
                f"""
                ALTER TABLE run RENAME TO run_pre_mt5import;
                CREATE TABLE run(
                  run_id TEXT PRIMARY KEY, variant_id TEXT REFERENCES variant, params_hash TEXT REFERENCES param_set,
                  engine TEXT NOT NULL CHECK(engine IN('sentinel-replay','sentinel-sim','mt5-tester','nt8-manual','mt5-import')),
                  fidelity TEXT NOT NULL CHECK(fidelity IN('research','screening','real-tick','forward','live-demo','mt5-htm')),
                  periodo_desde TEXT, periodo_hasta TEXT, modelo_sim TEXT, status TEXT,
                  trades INTEGER, net REAL, pf REAL, wr REAL, payoff REAL, maxdd REAL, sharpe REAL,
                  metrics_json TEXT NOT NULL DEFAULT '{{}}', preregistro_id TEXT,
                  report_path TEXT, trades_path TEXT, equity_path TEXT, signal_history_path TEXT,
                  fecha_corrida TEXT, seed INTEGER, config_hash TEXT, source_file TEXT, source_row INTEGER,
                  fidelity_ref TEXT);
                INSERT INTO run SELECT *, NULL FROM run_pre_mt5import;
                ALTER TABLE trade RENAME TO trade_pre_mt5import;
                {trade_sql.replace('"run_pre_mt5import"', "run").replace("run_pre_mt5import", "run")};
                INSERT INTO trade SELECT * FROM trade_pre_mt5import;
                DROP TABLE trade_pre_mt5import;
                DROP TABLE run_pre_mt5import;
                CREATE INDEX IF NOT EXISTS ix_run_variant ON run(variant_id);
                CREATE INDEX IF NOT EXISTS ix_trade_run ON trade(run_id);
                """
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")

        run_cols = {row[1] for row in conn.execute("PRAGMA table_info(run)").fetchall()}
        if "fidelity_ref" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN fidelity_ref TEXT")
            conn.commit()

        # P38 (honest program, 2026-07-19): `run.validity` -- nullable TEXT
        # validity label ('DUPLICATE_INGEST'|'LOOKAHEAD_CONFIRMED'|
        # 'REGIME_UNAUDITED'|...). ADDITIVE-ONLY by user directive: the
        # registry is append-only history -- NULL means valid/unreviewed;
        # marking NEVER deletes a row nor mutates any original field. Set
        # exclusively by scripts/report/mark_validity_2026_07_19.py, which
        # also writes an `audit_log` row per marking.
        if "validity" not in run_cols:
            conn.execute("ALTER TABLE run ADD COLUMN validity TEXT")
            conn.commit()

        # B1a-2: `meta` kv table (persisted DealsWatcher.last_sync + any
        # other single-row settings) -- additive, own CREATE TABLE IF NOT
        # EXISTS since it didn't exist in D.5's DDL.
        conn.executescript(_META_DDL)
        conn.commit()

        # B1a-2: `deals_raw` attribution columns (magic -> strategy/ia/human).
        # Nullable so pre-existing rows (inserted before this migration, or
        # deals with no attribution) are untouched.
        deals_cols = {row[1] for row in conn.execute("PRAGMA table_info(deals_raw)").fetchall()}
        if "origin" not in deals_cols:
            conn.execute("ALTER TABLE deals_raw ADD COLUMN origin TEXT")
            conn.commit()
        if "strategy_id" not in deals_cols:
            conn.execute("ALTER TABLE deals_raw ADD COLUMN strategy_id TEXT")
            conn.commit()
        if "variant_id" not in deals_cols:
            conn.execute("ALTER TABLE deals_raw ADD COLUMN variant_id TEXT")
            conn.commit()

        # B2: `strategy.baseline_ref` (nullable run_id) -- the CT-3 scorecard
        # endpoint's `teorico` block reads metrics from this run ONLY, never
        # from a best-run search. Additive, guarded by the same
        # PRAGMA-table_info check pattern as every other migration above.
        strategy_cols = {row[1] for row in conn.execute("PRAGMA table_info(strategy)").fetchall()}
        if "baseline_ref" not in strategy_cols:
            conn.execute("ALTER TABLE strategy ADD COLUMN baseline_ref TEXT")
            conn.commit()

        # B6: `jobs` table (CT-4). Additive, own CREATE TABLE IF NOT EXISTS.
        conn.executescript(_JOBS_DDL)
        conn.commit()

        # B1c: `deals_raw` leverage/contract_size (pct = profit/margin inputs,
        # margin = volume*contract_size*open_price/leverage for B3 UI).
        # Nullable -- pre-existing rows and clients without account_info()/
        # symbol_info() stay null, no crash.
        deals_cols = {row[1] for row in conn.execute("PRAGMA table_info(deals_raw)").fetchall()}
        if "leverage" not in deals_cols:
            conn.execute("ALTER TABLE deals_raw ADD COLUMN leverage REAL")
            conn.commit()
        if "contract_size" not in deals_cols:
            conn.execute("ALTER TABLE deals_raw ADD COLUMN contract_size REAL")
            conn.commit()

        # C1a: `news_items` table (CT-5). Additive, own CREATE TABLE IF NOT
        # EXISTS.
        conn.executescript(_NEWS_ITEMS_DDL)
        conn.commit()

        # B6: any job left `queued`/`running` from a prior process (crash or
        # restart) can never be resumed -- mark it `error:"interrupted"` on
        # boot so `GET /api/jobs/{id}` never reports a job as perpetually
        # in-flight when nothing is actually running it.
        conn.execute(
            "UPDATE jobs SET status='error', error='interrupted', updated_at=? "
            "WHERE status IN ('queued','running')",
            (_utcnow_iso(),),
        )
        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ------------------------------------------------------------------
    # strategy / variant / param_set
    # ------------------------------------------------------------------
    def upsert_strategy(self, name: str, familia: str, platform: str) -> str:
        """Idempotent on (name, familia): returns existing strategy_id if a
        row with the same name+familia already exists, else creates one with
        the next `strategy_seq` and `color_idx = seq % 12`."""
        strategy_id = f"{familia}::{name}"
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT strategy_id FROM strategy WHERE strategy_id=?", (strategy_id,)
            ).fetchone()
            if row is not None:
                return row[0]
            seq_row = conn.execute("SELECT COALESCE(MAX(strategy_seq), -1) FROM strategy").fetchone()
            next_seq = seq_row[0] + 1
            color_idx = next_seq % len(STRATEGY_PALETTE)
            conn.execute(
                """INSERT INTO strategy(strategy_id, strategy_seq, name, familia, platform, color_idx)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (strategy_id, next_seq, name, familia, platform, color_idx),
            )
            conn.commit()
            return strategy_id
        finally:
            conn.close()

    def upsert_variant(
        self,
        strategy_id: str,
        variant_id: str,
        params_delta: dict[str, Any] | None,
        tf: str | None,
        instrumento: str | None,
        modo_salida: str | None,
    ) -> str:
        params_delta_json = json.dumps(params_delta or {}, ensure_ascii=False)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT variant_id FROM variant WHERE variant_id=?", (variant_id,)
            ).fetchone()
            if row is not None:
                return row[0]
            seq_row = conn.execute(
                "SELECT COALESCE(MAX(variant_seq), -1) FROM variant WHERE strategy_id=?",
                (strategy_id,),
            ).fetchone()
            next_seq = seq_row[0] + 1
            conn.execute(
                """INSERT INTO variant(variant_id, strategy_id, variant_seq, params_delta_json, tf, instrumento, modo_salida)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (variant_id, strategy_id, next_seq, params_delta_json, tf, instrumento, modo_salida),
            )
            conn.commit()
            return variant_id
        finally:
            conn.close()

    def upsert_param_set(self, params_hash: str, params_json: str) -> str:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO param_set(params_hash, params_json) VALUES (?, ?)
                   ON CONFLICT(params_hash) DO NOTHING""",
                (params_hash, params_json),
            )
            conn.commit()
            return params_hash
        finally:
            conn.close()

    def get_param_set(self, params_hash: str) -> dict[str, Any] | None:
        """`params_json` (parsed) for a given `params_hash`, or `None` if no
        such param_set row exists — used to resolve a run's EXACT params for
        parity (`GET /api/runs/{id}/indicators`), falling back to
        `variant.params_delta` merged over strategy defaults when a run has
        no `params_hash` (the common case today: `_run_backtest_job` doesn't
        yet persist one per run)."""
        if not params_hash:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT params_json FROM param_set WHERE params_hash=?", (params_hash,)
            ).fetchone()
            if row is None:
                return None
            return json.loads(row[0])
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # run / trade / preregistration / forward_session
    # ------------------------------------------------------------------
    def insert_run(self, data: dict[str, Any]) -> str:
        payload = {col: data.get(col) for col in _RUN_COLUMNS}
        if payload.get("metrics_json") is None:
            payload["metrics_json"] = "{}"
        placeholders = ", ".join("?" for _ in _RUN_COLUMNS)
        cols = ", ".join(_RUN_COLUMNS)
        conn = self._connect()
        try:
            conn.execute(
                f"INSERT INTO run({cols}) VALUES ({placeholders})",
                tuple(payload[c] for c in _RUN_COLUMNS),
            )
            conn.commit()
            return payload["run_id"]
        finally:
            conn.close()

    def insert_trades(self, run_id: str, trades: list[dict[str, Any]]) -> None:
        if not trades:
            return
        cols = ", ".join(_TRADE_COLUMNS)
        placeholders = ", ".join("?" for _ in _TRADE_COLUMNS)
        conn = self._connect()
        try:
            for t in trades:
                payload = dict(t)
                payload.setdefault("run_id", run_id)
                payload.setdefault("origin", "strategy")
                row = tuple(payload.get(c) for c in _TRADE_COLUMNS)
                conn.execute(f"INSERT INTO trade({cols}) VALUES ({placeholders})", row)
            conn.commit()
        finally:
            conn.close()

    def insert_preregistration(self, data: dict[str, Any]) -> str:
        payload = {col: data.get(col) for col in _PREREG_COLUMNS}
        cols = ", ".join(_PREREG_COLUMNS)
        placeholders = ", ".join("?" for _ in _PREREG_COLUMNS)
        conn = self._connect()
        try:
            conn.execute(
                f"""INSERT INTO preregistration({cols}) VALUES ({placeholders})
                    ON CONFLICT(preregistro_id) DO NOTHING""",
                tuple(payload[c] for c in _PREREG_COLUMNS),
            )
            conn.commit()
            return payload["preregistro_id"]
        finally:
            conn.close()

    def upsert_forward_session(self, data: dict[str, Any]) -> str:
        payload = {col: data.get(col) for col in _FORWARD_SESSION_COLUMNS}
        cols = ", ".join(_FORWARD_SESSION_COLUMNS)
        placeholders = ", ".join("?" for _ in _FORWARD_SESSION_COLUMNS)
        update_cols = [c for c in _FORWARD_SESSION_COLUMNS if c != "session_id"]
        update_clause = ", ".join(f"{c}=excluded.{c}" for c in update_cols)
        conn = self._connect()
        try:
            conn.execute(
                f"""INSERT INTO forward_session({cols}) VALUES ({placeholders})
                    ON CONFLICT(session_id) DO UPDATE SET {update_clause}""",
                tuple(payload[c] for c in _FORWARD_SESSION_COLUMNS),
            )
            conn.commit()
            return payload["session_id"]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def query_strategies(self) -> list[dict[str, Any]]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT s.*,
                          (SELECT COUNT(*) FROM variant v WHERE v.strategy_id = s.strategy_id) AS n_variants,
                          (SELECT COUNT(*) FROM run r JOIN variant v ON r.variant_id = v.variant_id
                             WHERE v.strategy_id = s.strategy_id) AS n_runs
                   FROM strategy s ORDER BY s.strategy_seq"""
            ).fetchall()
            out = []
            for row in rows:
                d = dict(row)
                d["display_color"] = STRATEGY_PALETTE[d["color_idx"] % len(STRATEGY_PALETTE)]
                d["sweepable"] = bool(d["sweepable"])
                d["graduated"] = bool(d["graduated"])
                d.setdefault("estado", "activa")
                out.append(d)
            return out
        finally:
            conn.close()

    def query_runs(
        self,
        strategy_id: str | None = None,
        variant_id: str | None = None,
        instrumento: str | None = None,
        engine: str | None = None,
        fidelity: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        order_by: str = "fecha_corrida",
        dir: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        if order_by not in _RUN_ORDER_COLUMNS:
            order_by = "fecha_corrida"
        direction = "ASC" if str(dir).lower() == "asc" else "DESC"

        where = []
        params: list[Any] = []
        if strategy_id is not None:
            where.append("v.strategy_id = ?")
            params.append(strategy_id)
        if variant_id is not None:
            where.append("r.variant_id = ?")
            params.append(variant_id)
        if instrumento is not None:
            where.append("v.instrumento = ?")
            params.append(instrumento)
        if engine is not None:
            where.append("r.engine = ?")
            params.append(engine)
        if fidelity is not None:
            where.append("r.fidelity = ?")
            params.append(fidelity)
        if desde is not None:
            where.append("r.fecha_corrida >= ?")
            params.append(desde)
        if hasta is not None:
            where.append("r.fecha_corrida <= ?")
            params.append(hasta)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute(
                f"""SELECT COUNT(*) FROM run r
                    LEFT JOIN variant v ON r.variant_id = v.variant_id
                    {where_clause}""",
                params,
            ).fetchone()[0]

            rows = conn.execute(
                f"""SELECT r.run_id, r.variant_id, r.engine, r.fidelity,
                           r.periodo_desde, r.periodo_hasta, r.modelo_sim,
                           r.trades, r.net, r.pf, r.wr, r.payoff, r.maxdd, r.sharpe,
                           r.fecha_corrida, r.report_path,
                           v.instrumento AS instrumento, v.strategy_id AS strategy_id,
                           s.name AS strategy_name, s.familia AS familia,
                           s.color_idx AS color_idx, v.params_delta_json AS params_delta_json
                    FROM run r
                    LEFT JOIN variant v ON r.variant_id = v.variant_id
                    LEFT JOIN strategy s ON v.strategy_id = s.strategy_id
                    {where_clause}
                    ORDER BY r.{order_by} {direction}
                    LIMIT ? OFFSET ?""",
                params + [limit, offset],
            ).fetchall()

            out_rows = []
            for row in rows:
                d = dict(row)
                strategy_name = d.get("strategy_name")
                familia = d.get("familia")
                color_idx = d.get("color_idx")
                variant_suffix = d.get("variant_id") or ""
                display_name = f"{familia} · {strategy_name} · {variant_suffix}" if familia else None
                out_rows.append({
                    "run_id": d["run_id"],
                    "variant_id": d["variant_id"],
                    "display_name": display_name,
                    "color_idx": color_idx,
                    "familia": familia,
                    "instrumento": d.get("instrumento"),
                    "engine": d["engine"],
                    "fidelity": d["fidelity"],
                    "periodo_desde": d.get("periodo_desde"),
                    "periodo_hasta": d.get("periodo_hasta"),
                    "modelo_sim": d.get("modelo_sim"),
                    "trades": d.get("trades"),
                    "net": d.get("net"),
                    "pf": d.get("pf"),
                    "wr": d.get("wr"),
                    "payoff": d.get("payoff"),
                    "maxdd": d.get("maxdd"),
                    "sharpe": d.get("sharpe"),
                    "fecha_corrida": d.get("fecha_corrida"),
                    "report_path": d.get("report_path"),
                })
            return {"total": total, "rows": out_rows}
        finally:
            conn.close()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Full `run` row joined with variant/strategy display info, plus
        `preregistration` (or None) — shape for `GET /api/runs/{id}` (D.6)."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT r.*, v.instrumento AS instrumento, v.strategy_id AS strategy_id,
                          v.tf AS tf, v.modo_salida AS modo_salida,
                          s.name AS strategy_name, s.familia AS familia, s.color_idx AS color_idx
                   FROM run r
                   LEFT JOIN variant v ON r.variant_id = v.variant_id
                   LEFT JOIN strategy s ON v.strategy_id = s.strategy_id
                   WHERE r.run_id = ?""",
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            familia = d.get("familia")
            strategy_name = d.get("strategy_name")
            variant_suffix = d.get("variant_id") or ""
            d["display_name"] = (
                f"{familia} · {strategy_name} · {variant_suffix}" if familia else None
            )
            # Task 1.2 (Wave-3 Stage 1): self-heal pre-existing rows ingested
            # before `variant.tf` was populated -- fall back to the
            # `_(M\d+)_` suffix on variant_id (e.g.
            # "EMS_XAU_V1_M5_c2_sar3m3" -> "M5") so /api/runs/{id} never
            # returns a null tf for these rows without needing a re-ingest.
            if not d.get("tf"):
                m = _TF_FROM_VARIANT_ID_RE.search(variant_suffix)
                if m:
                    d["tf"] = m.group(1)

            prereg = None
            preregistro_id = d.get("preregistro_id")
            if preregistro_id:
                prow = conn.execute(
                    "SELECT * FROM preregistration WHERE preregistro_id=?", (preregistro_id,)
                ).fetchone()
                if prow is not None:
                    prereg = dict(prow)
            if prereg is None:
                prow = conn.execute(
                    "SELECT * FROM preregistration WHERE variant_id=?", (d.get("variant_id"),)
                ).fetchone()
                if prow is not None:
                    prereg = dict(prow)
            d["preregistration"] = prereg
            d["artifacts"] = {
                "report_path": d.get("report_path"),
                "trades_path": d.get("trades_path"),
                "equity_path": d.get("equity_path"),
                "signal_history_path": d.get("signal_history_path"),
            }
            return d
        finally:
            conn.close()

    def get_trades_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """`trade` rows for one run, ordered `ts_in` asc — shape for
        `GET /api/runs/{id}/trades` (D.6)."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM trade WHERE run_id=? ORDER BY ts_in ASC", (run_id,)
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["ts_in"] = _normalize_ts_iso_utc(d.get("ts_in"))
                d["ts_out"] = _normalize_ts_iso_utc(d.get("ts_out"))
                out.append(d)
            return out
        finally:
            conn.close()

    def query_forward_sessions(self) -> list[dict[str, Any]]:
        """`forward_session` rows + n_trades/pnl_total + display info —
        shape for `GET /api/forward/sessions` (D.6)."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT fs.*, s.name AS strategy_name, s.familia AS familia,
                          s.color_idx AS color_idx,
                          (SELECT COUNT(*) FROM trade t WHERE t.session_id = fs.session_id) AS n_trades,
                          (SELECT COALESCE(SUM(t.pnl), 0) FROM trade t WHERE t.session_id = fs.session_id) AS pnl_total
                   FROM forward_session fs
                   LEFT JOIN strategy s ON fs.strategy_id = s.strategy_id
                   ORDER BY fs.inicio DESC"""
            ).fetchall()
            out = []
            for row in rows:
                d = dict(row)
                familia = d.get("familia")
                strategy_name = d.get("strategy_name")
                display_name = (
                    f"{familia} · {strategy_name}" if familia else (d.get("perfil") or d["session_id"])
                )
                out.append({
                    "session_id": d["session_id"],
                    "display_name": display_name,
                    "color_idx": d.get("color_idx"),
                    "cuenta": d.get("cuenta"),
                    "perfil": d.get("perfil"),
                    "inicio": d.get("inicio"),
                    "fin": d.get("fin"),
                    "estado": d.get("estado"),
                    "n_trades": d.get("n_trades", 0),
                    "pnl_total": d.get("pnl_total", 0),
                })
            return out
        finally:
            conn.close()

    def get_trades_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """`trade` rows for one forward session, ordered `ts_in` asc, incl.
        `origin` — shape for `GET /api/forward/{id}/trades` (D.6)."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM trade WHERE session_id=? ORDER BY ts_in ASC", (session_id,)
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["ts_in"] = _normalize_ts_iso_utc(d.get("ts_in"))
                d["ts_out"] = _normalize_ts_iso_utc(d.get("ts_out"))
                out.append(d)
            return out
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # magic allocation
    # ------------------------------------------------------------------
    def allocate_magic(self, strategy_id: str, variant_id: str) -> int:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            srow = conn.execute(
                "SELECT strategy_seq FROM strategy WHERE strategy_id=?", (strategy_id,)
            ).fetchone()
            if srow is None:
                raise ValueError(f"unknown strategy_id: {strategy_id}")
            vrow = conn.execute(
                "SELECT variant_seq FROM variant WHERE variant_id=?", (variant_id,)
            ).fetchone()
            if vrow is None:
                raise ValueError(f"unknown variant_id: {variant_id}")
            strategy_seq = srow["strategy_seq"]
            variant_seq = vrow["variant_seq"]
            if strategy_seq >= 900:
                raise ValueError(f"strategy_seq out of range (<900 required): {strategy_seq}")
            if variant_seq >= 1000:
                raise ValueError(f"variant_seq out of range (<1000 required): {variant_seq}")
            magic = 100000 + strategy_seq * 1000 + variant_seq
            conn.execute(
                """INSERT INTO magic_allocation(magic, strategy_id, variant_id, asignado)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(magic) DO UPDATE SET strategy_id=excluded.strategy_id, variant_id=excluded.variant_id""",
                (magic, strategy_id, variant_id, _utcnow_iso()),
            )
            conn.commit()
            return magic
        finally:
            conn.close()

    def lookup_magic(self, magic: int) -> dict[str, Any] | None:
        """`magic_allocation` row for a given `magic` (int), or `None` if
        that magic hasn't been assigned to any strategy/variant — used by
        `DealsWatcher` (B1a-2) to attribute a deal's `origin`."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM magic_allocation WHERE magic=?", (magic,)
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # meta (kv) — single-row settings, e.g. DealsWatcher.last_sync (B1a-2)
    # ------------------------------------------------------------------
    def get_meta(self, key: str) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return row[0] if row is not None else None
        finally:
            conn.close()

    def set_meta(self, key: str, value: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO meta(key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, str(value)),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # audit / import checksum
    # ------------------------------------------------------------------
    def audit(self, actor: str | None, accion: str, detalle: dict[str, Any] | None = None) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO audit_log(ts, actor, accion, detalle_json) VALUES (?, ?, ?, ?)",
                (_utcnow_iso(), actor, accion, json.dumps(detalle or {}, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # M2.4 — variant/strategy management helpers
    # ------------------------------------------------------------------
    def get_strategy(self, strategy_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM strategy WHERE strategy_id=?", (strategy_id,)
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            d["sweepable"] = bool(d["sweepable"])
            d["graduated"] = bool(d["graduated"])
            return d
        finally:
            conn.close()

    def get_variant(self, variant_id: str) -> dict[str, Any] | None:
        """`variant` row joined with its parent `strategy` (familia, name,
        platform) — used by `POST /api/backtest` (M2.5) to pick a policy
        and pull `params_delta_json`."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT v.*, s.name AS strategy_name, s.familia AS familia,
                          s.platform AS platform
                   FROM variant v LEFT JOIN strategy s ON v.strategy_id = s.strategy_id
                   WHERE v.variant_id=?""",
                (variant_id,),
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            d["params_delta"] = json.loads(d.get("params_delta_json") or "{}")
            return d
        finally:
            conn.close()

    def variant_exists(self, variant_id: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM variant WHERE variant_id=?", (variant_id,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def insert_variant(
        self,
        strategy_id: str,
        variant_id: str,
        params_delta: dict[str, Any] | None,
        tf: str | None,
        instrumento: str | None,
        modo_salida: str | None,
    ) -> str:
        """Strict create (M2.4 `POST /api/variants`): raises `ValueError` if
        `variant_id` already exists — unlike `upsert_variant`, which is
        idempotent for the importer's use case."""
        if self.variant_exists(variant_id):
            raise ValueError(f"variant already exists: {variant_id}")
        return self.upsert_variant(strategy_id, variant_id, params_delta, tf, instrumento, modo_salida)

    def set_strategy_estado(self, strategy_id: str, estado: str) -> None:
        """`estado` in {'activa','pausada','graduada'} (M2.4). Keeps the
        pre-existing `graduated` bool column in sync (`graduated=1` iff
        `estado='graduada'`) so older readers of that flag stay correct."""
        if self.get_strategy(strategy_id) is None:
            raise ValueError(f"unknown strategy_id: {strategy_id}")
        graduated = 1 if estado == "graduada" else 0
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE strategy SET estado=?, graduated=? WHERE strategy_id=?",
                (estado, graduated, strategy_id),
            )
            conn.commit()
        finally:
            conn.close()

    def checksum_seen(self, path: str, sha: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT sha256 FROM import_checksum WHERE path=?", (str(path),)
            ).fetchone()
            return row is not None and row[0] == sha
        finally:
            conn.close()

    def mark_checksum(self, path: str, sha: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO import_checksum(path, sha256, imported_at) VALUES (?, ?, ?)
                   ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256, imported_at=excluded.imported_at""",
                (str(path), sha, _utcnow_iso()),
            )
            conn.commit()
        finally:
            conn.close()
