"""scripts/report/gen_honest_sweep.py -- Honest-sweep harness (P2/P35/P64).

The engine for the honest-program re-run: a manifest-driven sweep runner that
re-prices the whole research corpus under HONEST fill semantics
(`live_fill_mode=True`) + a flat $0.50/round-trip friction, and feeds the grid
through the (previously unused) `sentinel_engine.opt` statistical machinery
(anchored walk-forward, Deflated Sharpe Ratio, and the four selection guards)
to produce an honest league table.

Five stages, per manifest entry / whole grid:

  1. PREREGISTRATION (P64): every manifest entry MUST carry a `prereg` block.
     The harness REFUSES to run any entry lacking one -- it writes a
     `preregistration` row FIRST (via `ResearchRegistry.insert_preregistration`)
     and links every run row it produces for that entry to it
     (`run.preregistro_id`). No prereg -> `PreregistrationRequired`, nothing
     persisted for that entry.
  2. PRICING: `simular_variant(..., live_fill_mode=True)` for honest,
     non-look-ahead fills; BID lake bars, spread applied at fill via the
     verbatim `_entry_fill`/`_exit_fill`/`_pnl` primitives reused from
     `gen_variant_batch1.py` (imported the same importlib way
     `gen_livefill_bound.py` uses -- no logic duplicated). Cost model:
     flat SPREAD=0.5 USD/round-trip, stamped as `cost_model: "flat0.5"` in
     every run's metrics_json.
  3. PERSISTENCE (ADDITIVE-ONLY): every grid cell -> one run row with
     `fidelity='honest-screen'` + its trades. Never mutates/deletes existing
     rows; the nullable `validity` column stays NULL for new runs. Resumable:
     a cell whose (variant_id, tf, window) already has a persisted
     honest-screen run is SKIPPED (logged), so the overnight run survives
     restarts without duplicating rows.
  4. OPT LEAGUE: after the grid, the honest per-cell metrics feed
     `sentinel_engine.opt` -- anchored walk-forward folds (where the window
     count permits), Deflated Sharpe over the trial family (trial count ==
     manifest size), and the four selection guards -- via their PUBLIC APIs
     (nothing reimplemented). Emits a league-table JSON + a markdown report.
  5. `--dry-list`: prints the entry count + a window-coverage matrix and exits
     WITHOUT running or writing anything.

Determinism: same manifest + same bars => identical run outputs. No
wall-clock/random enters the metrics; run timestamps use bar data.

Windows-safe: pathlib throughout, explicit utf-8, stdlib + repo deps only.

CLI:
    python -m scripts.report.gen_honest_sweep --manifest <json> \
        [--db data/research.db] [--windows IW,W1,W2,W3] \
        [--league-json ...] [--report-md ...] [--dry-list]

Task B3 authors the real ~300-600-entry manifest and launches the overnight
run on the real DB; this file is the harness + tests only.
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402
from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402

from sentinel_engine.opt.registry import (  # noqa: E402
    TrialRegistry,
    deflated_sharpe_ratio,
)
from sentinel_engine.opt.selection import (  # noqa: E402
    CandidateResult,
    FoldResult,
    select_winner,
)
from sentinel_engine.opt import report as opt_report  # noqa: E402
from sentinel_engine.opt.walkforward import anchored_walkforward  # noqa: E402


# ---------------------------------------------------------------------------
# Reuse gen_livefill_bound's loader + gen_variant_batch1's fill/pnl primitives
# via the SAME importlib pattern the live-fill runner uses. We import the
# live-fill runner (which itself loads batch1 as `_b1` and oow as `_oow`) so we
# get its window->bars + window->period mapping for the REAL overnight path,
# without duplicating that logic. Tests override `_BARS_LOADER` to inject
# synthetic bars so they never touch the lake.
# ---------------------------------------------------------------------------
def _load_module(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_LF = _load_module("gen_livefill_bound", "scripts/report/gen_livefill_bound.py")
_B1 = _LF._b1  # gen_variant_batch1 (fill/pnl/spread primitives)

SYMBOL = _B1.SYMBOL
SPREAD = _B1.SPREAD  # 0.5 flat, at fill
COST_MODEL = "flat0.5"
FIDELITY = "honest-screen"
DEFAULT_WINDOWS = ("IW", "W1", "W2", "W3")


class PreregistrationRequired(RuntimeError):
    """Raised when a manifest entry lacks a `prereg` block (P64)."""


def _ensure_honest_fidelity(registry: ResearchRegistry) -> None:
    """Additive schema evolution: widen `run.fidelity`'s CHECK to admit
    'honest-screen'. Stated adaptation (Task B2): the schema's fidelity enum
    predates the honest program and `registry2.py` is outside this task's
    file set, so the harness performs the SAME precedented migration pattern
    `registry2._migrate_additive` uses for 'mt5-import'/'mt5-htm' -- rename ->
    recreate (DDL string-patched from sqlite_master, so every column and enum
    member present at migration time is preserved verbatim) -> copy rows ->
    drop. No row is mutated or deleted; only the enum widens. Idempotent:
    no-op once 'honest-screen' is already in the CHECK."""
    conn = registry._connect()  # noqa: SLF001 -- schema migration, mirrors registry2
    try:
        run_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='run'"
        ).fetchone()[0]
        if "honest-screen" in run_sql:
            return
        patched = run_sql.replace("'live-demo'", "'live-demo','honest-screen'", 1)
        if patched == run_sql:
            raise RuntimeError(
                "cannot widen run.fidelity CHECK: 'live-demo' anchor not found "
                "in the run table DDL -- schema drifted, refusing to guess"
            )
        # SQLite rewrites trade's FK-reference text when `run` is renamed --
        # rebuild `trade` too (verbatim DDL re-pointed at `run`), exactly as
        # registry2._migrate_additive does for the mt5-import widening.
        trade_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='trade'"
        ).fetchone()[0]
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            f"""
            ALTER TABLE run RENAME TO run_pre_honest;
            {patched};
            INSERT INTO run SELECT * FROM run_pre_honest;
            ALTER TABLE trade RENAME TO trade_pre_honest;
            {trade_sql.replace('"run_pre_honest"', "run").replace("run_pre_honest", "run")};
            INSERT INTO trade SELECT * FROM trade_pre_honest;
            DROP TABLE trade_pre_honest;
            DROP TABLE run_pre_honest;
            CREATE INDEX IF NOT EXISTS ix_run_variant ON run(variant_id);
            CREATE INDEX IF NOT EXISTS ix_trade_run ON trade(run_id);
            """
        )
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Bar loading seam. Real path delegates to gen_livefill_bound's window->bars
# map; tests monkeypatch this to return synthetic bars.
# ---------------------------------------------------------------------------
def _default_bars_loader(tf: str, window: str) -> list[dict[str, Any]]:
    return _LF._bars_for_window(tf, window)


_BARS_LOADER: Callable[[str, str], list[dict[str, Any]]] = _default_bars_loader


def _window_period(window: str) -> tuple[str, str]:
    """(periodo_desde, periodo_hasta) for a named window, reusing the
    live-fill runner's mapping when known; otherwise a stable placeholder so
    tests with arbitrary window labels still persist a well-formed row."""
    try:
        return _LF._periodo(window)
    except Exception:
        return window, window


# ---------------------------------------------------------------------------
# Stage 2: honest pricing (simular_variant live_fill + spread-at-fill pairing).
# The pairing loop mirrors gen_variant_batch1.run_variant's shape but operates
# on caller-supplied bars (so it is bar-source-agnostic and testable) and reuses
# batch1's verbatim `_entry_fill`/`_exit_fill`/`_pnl` primitives -- no spread or
# pnl math is duplicated here.
# ---------------------------------------------------------------------------
def _price_cell(bars: list[dict[str, Any]], kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    kw = {**kwargs, "live_fill_mode": True}
    eventos = simular_variant(bars, symbol=SYMBOL, **kw)

    trades: list[dict[str, Any]] = []
    open_positions: dict[str, dict[str, Any]] = {}
    signal_seq = 0
    last_signal_id: str | None = None

    for ev in eventos:
        motivo = ev["motivo"]
        bar = bars[ev["idx"]]
        side_l = ev["lado"]
        side_ui = "LONG" if side_l == "L" else "SHORT"

        if motivo in ("ENTRY_L", "ENTRY_S"):
            signal_seq += 1
            signal_id = f"sig-{bar['t']}-{signal_seq}"
            open_positions[signal_id] = {
                "signal_id": signal_id, "t": bar["t"], "side": side_l,
                "side_ui": side_ui, "precio": ev["precio"],
                "fichas_remaining": {"F1", "F2", "F3"},
            }
            last_signal_id = signal_id
        elif motivo.startswith("EXIT"):
            ficha = ev.get("ficha") or "F1"
            pos = open_positions.get(last_signal_id)
            if pos is None or ficha not in pos["fichas_remaining"]:
                pos = None
                for sid, p in open_positions.items():
                    if ficha in p["fichas_remaining"]:
                        pos = p
                        last_signal_id = sid
                        break
                if pos is None:
                    continue

            entry_side_l = pos["side"]
            entry_px = _B1._entry_fill(entry_side_l, pos["precio"])
            exit_px = _B1._exit_fill(entry_side_l, ev["precio"])
            trades.append({
                "signal_id": pos["signal_id"], "ficha": ficha,
                "side": pos["side_ui"],
                "ts_in_epoch": pos["t"], "ts_out_epoch": bar["t"],
                "px_in": round(entry_px, 2), "px_out": round(exit_px, 2),
                "exit_reason": motivo,
            })
            pos["fichas_remaining"].discard(ficha)
            if not pos["fichas_remaining"]:
                open_positions.pop(pos["signal_id"], None)

    return trades


def _metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Honest per-cell metrics: net/pf/wr/payoff/maxdd on the paired trades,
    computed via batch1's `_pnl` primitive (deterministic, no wall-clock)."""
    n = len(trades)
    pnls = [(_B1._pnl(t["side"], t["px_in"], t["px_out"]), t) for t in trades]
    net = round(sum(p for p, _ in pnls), 2)
    wins = [p for p, _ in pnls if p > 0]
    losses = [p for p, _ in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    pf = (round(gross_win / gross_loss, 4) if gross_loss > 0
          else (None if gross_win == 0 else None))  # inf -> None (registry REAL)
    wr = round(100.0 * len(wins) / n, 2) if n else None
    avg_win = (gross_win / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    payoff = round(avg_win / avg_loss, 4) if avg_loss > 0 else None

    ordered = sorted(trades, key=lambda t: t["ts_out_epoch"])
    cum = peak = maxdd = 0.0
    per_trade_pnl: list[float] = []
    for t in ordered:
        p = _B1._pnl(t["side"], t["px_in"], t["px_out"])
        per_trade_pnl.append(p)
        cum += p
        peak = max(peak, cum)
        maxdd = max(maxdd, peak - cum)
    return {
        "trades": n, "net": net, "pf": pf, "wr": wr, "payoff": payoff,
        "maxdd": round(maxdd, 2), "per_trade_pnl": per_trade_pnl,
    }


# ---------------------------------------------------------------------------
# Stage 1+3: prereg + additive persistence.
# ---------------------------------------------------------------------------
def _prereg_id(variant_id: str) -> str:
    return f"prereg-honest-{variant_id}"


def _write_prereg(registry: ResearchRegistry, entry: dict[str, Any]) -> str:
    prereg = entry.get("prereg")
    if not prereg or not isinstance(prereg, dict) or not prereg.get("hypothesis"):
        raise PreregistrationRequired(
            f"manifest entry {entry.get('variant_id')!r} has no valid `prereg` "
            "block -- honest sweep refuses to run un-preregistered cells (P64)"
        )
    preregistro_id = _prereg_id(entry["variant_id"])
    registry.insert_preregistration({
        "preregistro_id": preregistro_id,
        "variant_id": entry["variant_id"],
        "hipotesis": prereg.get("hypothesis"),
        "mecanismo": prereg.get("mechanism"),
        "metrica_primaria": prereg.get("metric", "net_honest"),
        "umbral_exito": json.dumps(prereg.get("threshold"), ensure_ascii=False),
        "condicion_descarte": prereg.get("discard_if"),
        "fecha": prereg.get("date"),
        "autor": prereg.get("author", "honest-program"),
        "raw_json": json.dumps(prereg, ensure_ascii=False),
    })
    return preregistro_id


def _run_id(variant_id: str, tf: str, window: str) -> str:
    return f"honest-{variant_id}-{tf}-{window}".lower()


def _already_persisted(registry: ResearchRegistry, run_id: str) -> bool:
    conn = registry._connect()  # noqa: SLF001 -- read-only resume probe
    try:
        row = conn.execute(
            "SELECT 1 FROM run WHERE run_id=? AND fidelity=?",
            (run_id, FIDELITY),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _persist_cell(
    registry: ResearchRegistry, *, run_id: str, variant_id: str, tf: str,
    window: str, kwargs: dict[str, Any], preregistro_id: str,
    trades: list[dict[str, Any]], metrics: dict[str, Any],
) -> None:
    periodo_desde, periodo_hasta = _window_period(window)
    strategy_id = registry.upsert_strategy(name="EMASAR", familia="emasar", platform="py")
    json_kwargs = {k: (list(v) if isinstance(v, tuple) else v) for k, v in kwargs.items()}
    registry.upsert_variant(
        strategy_id=strategy_id, variant_id=variant_id, params_delta=json_kwargs,
        tf=tf, instrumento=SYMBOL, modo_salida=tf.lower(),
    )

    # Deterministic fecha_corrida from bar data (never now()): last exit bar.
    last_epoch = max((t["ts_out_epoch"] for t in trades), default=None)
    fecha = _B1._ts_str(last_epoch).split(" ")[0].replace(".", "-") if last_epoch else periodo_hasta

    run_row = {
        "run_id": run_id, "variant_id": variant_id, "params_hash": None,
        "engine": "sentinel-sim", "fidelity": FIDELITY,
        "periodo_desde": periodo_desde, "periodo_hasta": periodo_hasta,
        "modelo_sim": "honest-screen", "status": "OK",
        "trades": metrics["trades"], "net": metrics["net"], "pf": metrics["pf"],
        "wr": metrics["wr"], "payoff": metrics["payoff"], "maxdd": metrics["maxdd"],
        "sharpe": None,
        "metrics_json": json.dumps({
            "cost_model": COST_MODEL, "spread_usd_round_trip": SPREAD,
            "live_fill_mode": True, "window_key": window, "fidelity": FIDELITY,
            "per_trade_pnl": metrics["per_trade_pnl"], "params": json_kwargs,
        }, ensure_ascii=False),
        "preregistro_id": preregistro_id, "report_path": None, "trades_path": None,
        "equity_path": None, "signal_history_path": None,
        "fecha_corrida": fecha, "seed": None, "config_hash": None,
        "source_file": "scripts/report/gen_honest_sweep.py", "source_row": None,
        "fidelity_ref": None,
        # validity intentionally omitted -> NULL for new honest runs.
    }
    registry.insert_run(run_row)

    trade_rows = []
    for t in trades:
        trade_rows.append({
            "trade_id": f"{run_id}-{t['signal_id']}-{t['ficha']}", "run_id": run_id,
            "origin": "strategy", "origin_id": variant_id, "session_id": None,
            "ts_in": _B1._ts_str(t["ts_in_epoch"]), "ts_out": _B1._ts_str(t["ts_out_epoch"]),
            "px_in": t["px_in"], "px_out": t["px_out"], "side": t["side"],
            "volume": _B1.LOT, "sl": None, "tp": None, "exit_reason": t["exit_reason"],
            "exit_reason_source": "honest_screen",
            "pnl": _B1._pnl(t["side"], t["px_in"], t["px_out"]),
            "mae": None, "mfe": None, "snapshot_ref": None, "decision_trace_ref": None,
            "signal_id": t["signal_id"], "ficha": t["ficha"],
        })
    registry.insert_trades(run_id, trade_rows)
    registry.audit(
        "scripts.report.gen_honest_sweep", "honest_cell_persisted",
        {"run_id": run_id, "variant_id": variant_id, "tf": tf, "window": window,
         "net": metrics["net"], "trades": metrics["trades"]},
    )


# ---------------------------------------------------------------------------
# Stage 5: opt-integrated league table.
# ---------------------------------------------------------------------------
def _bar_datetimes(windows: list[str]) -> list:
    """A coarse per-window timeline (one datetime per window's start) so
    anchored_walkforward can emit folds when >=3 windows are present."""
    from datetime import datetime, timezone
    out = []
    for w in windows:
        desde, _ = _window_period(w)
        try:
            out.append(datetime.fromisoformat(desde).replace(tzinfo=timezone.utc))
        except Exception:
            out.append(datetime(2026, 1, 1, tzinfo=timezone.utc) +
                       __import__("datetime").timedelta(days=30 * len(out)))
    return out


def _build_league(
    registry_opt: TrialRegistry, study_id: str, per_entry: dict[str, dict[str, Any]],
    windows_ordered: list[str], league_json: Path, report_md: Path,
) -> dict[str, Any]:
    from datetime import timedelta

    # Walk-forward folds over the ordered window timeline (empty if <2 windows
    # of coverage fit a full test span -- reported honestly, not faked).
    timeline = _bar_datetimes(windows_ordered)
    folds = []
    if len(timeline) >= 2:
        span = timedelta(days=30)
        try:
            folds = anchored_walkforward(timeline, test_span=span, step=span,
                                         embargo=timedelta(days=1))
        except ValueError:
            folds = []

    # Candidate pool: one per manifest entry; per-window honest net is the
    # per-"fold" J. Production baseline = zero net (honest go/no-go: beat flat).
    candidates: list[CandidateResult] = []
    for variant_id, info in per_entry.items():
        window_nets = info["window_nets"]
        fold_results = [
            FoldResult(fold_index=i, candidate_J=window_nets[w], production_J=0.0)
            for i, w in enumerate(windows_ordered) if w in window_nets
        ]
        if not fold_results:
            continue
        candidates.append(CandidateResult(
            name=variant_id,
            config={k: float(v) for k, v in info["kwargs"].items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)},
            fold_results=fold_results,
        ))

    outcome = select_winner(candidates, production_config={})

    # DSR over the trial family (trial registry size == manifest size). Use the
    # winner's per-window net series as its return series when available.
    n_trials = registry_opt.trial_count(study_id)
    dsr = None
    winner = outcome.winner
    if winner is not None:
        returns = [fr.candidate_J for fr in winner.fold_results]
        trial_sharpes = [
            info["sharpe"] for info in per_entry.values() if info.get("sharpe") is not None
        ]
        trial_sharpe_std = None
        if len(trial_sharpes) >= 2:
            mean = sum(trial_sharpes) / len(trial_sharpes)
            var = sum((s - mean) ** 2 for s in trial_sharpes) / (len(trial_sharpes) - 1)
            trial_sharpe_std = var ** 0.5
        if n_trials >= 2 and len(returns) >= 2:
            try:
                dsr = deflated_sharpe_ratio(returns, n_trials, trial_sharpe_std=trial_sharpe_std)
            except ValueError:
                dsr = None

    league = {
        "study_id": study_id,
        "n_trials": n_trials,
        "windows": windows_ordered,
        "n_folds": len(folds),
        "winner": winner.name if winner is not None else None,
        "selection_reason": outcome.reason,
        "median_J_by_name": outcome.median_J_by_name,
        "dominance_by_name": outcome.dominance_by_name,
        "rejected": outcome.rejected,
        "tie_pool": outcome.tie_pool,
        "dsr": None if dsr is None else {
            "sharpe": dsr.sharpe, "n_trials": dsr.n_trials,
            "expected_max_sharpe_null": dsr.expected_max_sharpe_null,
            "dsr": dsr.dsr, "p_value": dsr.p_value,
        },
        "entries": {
            vid: {"window_nets": info["window_nets"], "sharpe": info.get("sharpe")}
            for vid, info in per_entry.items()
        },
    }
    league_json = Path(league_json)
    league_json.parent.mkdir(parents=True, exist_ok=True)
    league_json.write_text(json.dumps(league, indent=2, ensure_ascii=False), encoding="utf-8")

    opt_report.generate_report(
        study_id=study_id, registry=registry_opt, selection_outcome=outcome,
        production_config={}, dsr=dsr, out_path=report_md,
        generated_at="honest-program",
    )
    return league


# ---------------------------------------------------------------------------
# Orchestrator.
# ---------------------------------------------------------------------------
def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"entries": data}
    return data


def _coverage_matrix(entries: list[dict[str, Any]], windows: tuple[str, ...]) -> str:
    lines = ["Entry / window coverage matrix:", "  " + "  ".join(f"{w:>4}" for w in windows)]
    for e in entries:
        ews = set(e.get("windows") or windows)
        marks = "  ".join(f"{'X' if w in ews else '.':>4}" for w in windows)
        lines.append(f"{e.get('variant_id', '?')}: {marks}")
    return "\n".join(lines)


def run_sweep(
    *,
    manifest_path: Path,
    db_path: Path,
    league_json: Path,
    report_md: Path,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
    dry_list: bool = False,
) -> dict[str, Any]:
    """Run the honest sweep described by `manifest_path` into `db_path`.

    Returns a summary dict: {persisted, skipped, refused, league}. Raises
    `PreregistrationRequired` if any entry lacks a valid `prereg` block --
    that entry (and only that entry) contributes nothing to the DB.
    """
    manifest = _load_manifest(manifest_path)
    entries = manifest.get("entries", [])

    if dry_list:
        print(f"Honest sweep: {len(entries)} manifest entries.")
        print(_coverage_matrix(entries, windows))
        return {"persisted": 0, "skipped": 0, "refused": 0, "entries": len(entries),
                "dry_list": True}

    registry = ResearchRegistry(db_path)
    _ensure_honest_fidelity(registry)

    # opt trial registry lives beside the league output (temp/real both work).
    opt_db = Path(league_json).with_suffix(".trials.db")
    opt_parquet = Path(league_json).parent / "honest_trials_parquet"
    study_id = "honest-sweep-2026-07-19"
    registry_opt = TrialRegistry(opt_db, opt_parquet)
    registry_opt.ensure_study(study_id, notes="honest-program re-run")

    persisted = skipped = 0
    per_entry: dict[str, dict[str, Any]] = {}
    windows_seen: list[str] = []

    for entry in entries:
        variant_id = entry["variant_id"]
        tf = entry["tf"]
        kwargs = dict(entry.get("kwargs", {}))
        entry_windows = entry.get("windows") or list(windows)

        # P64: prereg FIRST (refuse if missing -> nothing persisted for it).
        preregistro_id = _write_prereg(registry, entry)

        window_nets: dict[str, float] = {}
        for window in entry_windows:
            if window not in windows_seen:
                windows_seen.append(window)
            run_id = _run_id(variant_id, tf, window)
            if _already_persisted(registry, run_id):
                skipped += 1
                print(f"[SKIP] {run_id} already persisted (fidelity={FIDELITY})")
                _accum_net(registry, run_id, window, window_nets)
                continue

            bars = _BARS_LOADER(tf, window)
            trades = _price_cell(bars, kwargs)
            metrics = _metrics(trades)
            _persist_cell(
                registry, run_id=run_id, variant_id=variant_id, tf=tf, window=window,
                kwargs=kwargs, preregistro_id=preregistro_id, trades=trades, metrics=metrics,
            )
            persisted += 1
            window_nets[window] = metrics["net"]
            print(f"[HON] {run_id}: net={metrics['net']} trades={metrics['trades']}")

        # One opt trial per manifest entry (trial family size == manifest size).
        sharpe = _entry_sharpe(window_nets)
        registry_opt.record_trial(
            study_id,
            params={"variant_id": variant_id, "tf": tf},
            metrics={"net_honest": sum(window_nets.values()), "sharpe": sharpe,
                     "window_nets": window_nets},
        )
        per_entry[variant_id] = {"kwargs": kwargs, "window_nets": window_nets, "sharpe": sharpe}

    windows_ordered = [w for w in windows if w in windows_seen] + \
        [w for w in windows_seen if w not in windows]
    league = _build_league(
        registry_opt, study_id, per_entry, windows_ordered, league_json, report_md,
    )
    registry_opt.close()

    return {"persisted": persisted, "skipped": skipped, "refused": 0, "league": league}


def _accum_net(registry: ResearchRegistry, run_id: str, window: str,
               window_nets: dict[str, float]) -> None:
    """On resume, pull an already-persisted cell's net so the league still
    sees the full grid (deterministic re-read, no re-simulation)."""
    conn = registry._connect()  # noqa: SLF001
    try:
        row = conn.execute("SELECT net FROM run WHERE run_id=?", (run_id,)).fetchone()
        if row is not None and row[0] is not None:
            window_nets[window] = row[0]
    finally:
        conn.close()


def _entry_sharpe(window_nets: dict[str, float]) -> float | None:
    vals = list(window_nets.values())
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    std = var ** 0.5
    return round(mean / std, 6) if std > 0 else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Honest-sweep harness (P2/P35/P64).")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "research.db")
    parser.add_argument("--windows", type=str, default=",".join(DEFAULT_WINDOWS),
                         help="comma-separated window keys (default IW,W1,W2,W3)")
    parser.add_argument("--league-json", type=Path,
                         default=ROOT / "docs" / "superpowers" / "research" /
                         "2026-07-20-honest-league.json")
    parser.add_argument("--report-md", type=Path,
                         default=ROOT / "docs" / "superpowers" / "research" /
                         "2026-07-20-honest-league.md")
    parser.add_argument("--dry-list", action="store_true")
    args = parser.parse_args()

    windows = tuple(w.strip() for w in args.windows.split(",") if w.strip())
    summary = run_sweep(
        manifest_path=args.manifest, db_path=args.db,
        league_json=args.league_json, report_md=args.report_md,
        windows=windows, dry_list=args.dry_list,
    )
    if not args.dry_list:
        print(f"\n==== HONEST SWEEP DONE: persisted={summary['persisted']} "
              f"skipped={summary['skipped']} ====")


if __name__ == "__main__":
    main()
