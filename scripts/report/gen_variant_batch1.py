"""scripts/report/gen_variant_batch1.py -- Batch 1 of the EMASAR variant
research program: V-09 (control baseline), V-14 (directional asymmetry),
V-01 (legal-stop range_k sweep).

Reuses (does NOT modify) `scripts/report/gen_thu_fri_backtests.py`'s
loading/fill/persistence conventions:
    - lake bars are BID; spread 0.5 (Capitaria/MT5) applied AT THE FILL
      (long entries buy ASK, long exits sell BID; short entries sell BID,
      short exits buy ASK) -- see `_entry_fill`/`_exit_fill` below, copied
      verbatim from that script.
    - trades/runs are persisted via the SAME public `ResearchRegistry` API
      (`upsert_strategy`/`upsert_variant`/`insert_run`/`insert_trades`), same
      row shapes, idempotent delete-before-insert per run_id.
    - `sentinel_engine.strategies.emasar_variant.simular_variant` is the ONLY
      strategy engine touched (frozen `emasar_ref.py` is never imported for
      mutation, only for its indicator/gate math via `emasar_variant`).

WINDOW: 2026-06-08 -> 2026-07-07 (bars from the lake; warmup starts
2026-06-01 so EMA/SAR/momentum are seeded well before the window opens).
TFs: M1, M2, M5, M15 (all 4 present in the lake for June+July -- verified,
no data gaps to note).

Run this script directly: `python scripts/report/gen_variant_batch1.py`.
Idempotent: re-running replaces the same run_ids (delete-before-insert).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

LAKE_ROOT = ROOT / "data" / "lake"
DB_PATH = ROOT / "data" / "research.db"
SYMBOL = "XAUUSD"
SPREAD = 0.5  # Capitaria/MT5 real spread, flat, applied at fill.
LOT = 0.10
CONTRACT_SIZE = 100.0  # XAUUSD: $100 per $1 move per 1.00 lot.

TFS = ["M1", "M2", "M5", "M15"]

WARMUP_START = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_START = datetime(2026, 6, 8, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_END_EXCL = datetime(2026, 7, 8, 0, 0, 0, tzinfo=timezone.utc)  # captures through 07-07
FEED_END_EXCL = WINDOW_END_EXCL
LAKE_MONTHS = ("2026-06", "2026-07")

# ---------------------------------------------------------------------------
# V-09 control-baseline params (exact spec).
# ---------------------------------------------------------------------------
V09_PARAMS: dict[str, Any] = dict(
    confirm_mode=1, confirm_count=2, require_ema_order=False,
    f1_trail_pips=100.0, f2_trail_pips=100.0, f3_trail_pips=100.0,
    init_sl_range_k=1.0, ema_fast=8, ema_slow=20,
    sar_step=0.3, sar_max=0.3,
)

# V-01 range_k sweep grid.
V01_RANGE_K_GRID = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)

# 3 existing EMASAR fixture runs for the V-14 diagnostic (step a).
V14_FIXTURE_RUN_IDS = (
    "sim-report-emasar-orig-sar3m3-m2",
    "sim-report-emasar-pf-sar005m05-m5",
    "sim-report-emasar-wr-v2m15c1",
)


def _load_bars(tf: str) -> list[dict[str, Any]]:
    """Load XAUUSD/{tf} lake bars in [WARMUP_START, FEED_END_EXCL), across
    the June+July tiers -- same pattern as gen_thu_fri_backtests._load_bars,
    generalized to the 2-month span this batch needs."""
    warm_epoch = int(WARMUP_START.timestamp())
    end_epoch = int(FEED_END_EXCL.timestamp())
    bars = []
    for month in LAKE_MONTHS:
        path = LAKE_ROOT / SYMBOL / tf / f"{month}.parquet"
        if not path.exists():
            continue
        table = pq.read_table(path)
        cols = {name: table.column(name).to_pylist() for name in table.schema.names}
        for i in range(len(cols["t"])):
            t = cols["t"][i]
            if t < warm_epoch or t >= end_epoch:
                continue
            bars.append({
                "t": t,
                "open": cols["o"][i], "high": cols["h"][i],
                "low": cols["l"][i], "close": cols["c"][i],
                "volume": cols["v"][i],
            })
    bars.sort(key=lambda b: b["t"])
    return bars


_BARS_CACHE: dict[str, list[dict[str, Any]]] = {}


def _bars_for(tf: str) -> list[dict[str, Any]]:
    if tf not in _BARS_CACHE:
        _BARS_CACHE[tf] = _load_bars(tf)
    return _BARS_CACHE[tf]


def _ts_str(epoch: int) -> str:
    """MT5-dotted UTC string convention (registry reformats to ISO on read)."""
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return dt.strftime("%Y.%m.%d %H:%M:%S")


def _in_window(epoch: int) -> bool:
    return int(WINDOW_START.timestamp()) <= epoch < int(WINDOW_END_EXCL.timestamp())


# ---------------------------------------------------------------------------
# Spread-at-fill helpers (bars are BID; ask = bid + SPREAD). Copied verbatim
# from gen_thu_fri_backtests.py.
# ---------------------------------------------------------------------------

def _entry_fill(side: str, bid_price: float) -> float:
    """Long entries buy at ASK; short entries sell at BID."""
    return bid_price + SPREAD if side == "L" else bid_price


def _exit_fill(side: str, bid_price: float) -> float:
    """Long exits SELL at BID (no adj); short exits BUY BACK at ASK."""
    return bid_price if side == "L" else bid_price + SPREAD


def _pnl(side: str, px_in: float, px_out: float, volume: float = LOT) -> float:
    diff = (px_out - px_in) if side == "LONG" else (px_in - px_out)
    return round(diff * volume * CONTRACT_SIZE, 2)


# ---------------------------------------------------------------------------
# Simulation runner: emasar_variant.simular_variant -> trades (spread applied)
# ---------------------------------------------------------------------------

def run_variant(tf: str, variant_kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    """Runs `simular_variant` on the loaded `tf` bars, applies spread at fill,
    and pairs each EXIT_* event with its ficha's open position -- same pairing
    shape as gen_thu_fri_backtests.run_emasar_trailing_variant (V1: one ENTRY
    opens F1+F2+F3; each closes independently)."""
    bars = _bars_for(tf)
    eventos = simular_variant(bars, symbol=SYMBOL, **variant_kwargs)

    trades: list[dict[str, Any]] = []
    open_positions: dict[str, dict[str, Any]] = {}
    signal_seq = 0
    last_signal_id: str | None = None

    for ev in eventos:
        motivo = ev["motivo"]
        idx = ev["idx"]
        bar = bars[idx]
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
            entry_px = _entry_fill(entry_side_l, pos["precio"])
            exit_px = _exit_fill(entry_side_l, ev["precio"])

            trades.append({
                "signal_id": pos["signal_id"],
                "ficha": ficha,
                "side": pos["side_ui"],
                "ts_in_epoch": pos["t"],
                "ts_out_epoch": bar["t"],
                "px_in": round(entry_px, 2),
                "px_out": round(exit_px, 2),
                "exit_reason": motivo,
                "entry_in_window": _in_window(pos["t"]),
            })

            pos["fichas_remaining"].discard(ficha)
            if not pos["fichas_remaining"]:
                open_positions.pop(pos["signal_id"], None)

    return trades


# ---------------------------------------------------------------------------
# Metrics computation (net, pf, wr, maxdd, %exit-by-motivo, trades/day)
# ---------------------------------------------------------------------------

def compute_metrics(trades_all: list[dict[str, Any]]) -> dict[str, Any]:
    trades_in = [t for t in trades_all if t["entry_in_window"]]
    n = len(trades_in)
    if n == 0:
        return {
            "trades": 0, "net": 0.0, "pf": None, "wr": None, "payoff": None,
            "maxdd": 0.0, "pct_initsl": None, "pct_trail": None,
            "trades_per_day": 0.0, "long_pnl": 0.0, "short_pnl": 0.0,
            "long_n": 0, "short_n": 0,
        }

    pnls = [(_pnl(t["side"], t["px_in"], t["px_out"]), t) for t in trades_in]
    net = round(sum(p for p, _ in pnls), 2)
    wins = [p for p, _ in pnls if p > 0]
    losses = [p for p, _ in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    pf = round(gross_win / gross_loss, 4) if gross_loss > 0 else (None if gross_win == 0 else float("inf"))
    wr = round(100.0 * len(wins) / n, 2) if n else None
    avg_win = (gross_win / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    payoff = round(avg_win / avg_loss, 4) if avg_loss > 0 else None

    ordered = sorted(trades_in, key=lambda t: t["ts_out_epoch"])
    cum = 0.0
    peak = 0.0
    maxdd = 0.0
    for t in ordered:
        cum += _pnl(t["side"], t["px_in"], t["px_out"])
        peak = max(peak, cum)
        maxdd = max(maxdd, peak - cum)
    maxdd = round(maxdd, 2)

    n_initsl = sum(1 for t in trades_in if t["exit_reason"] == "EXIT_INITSL")
    n_trail = sum(1 for t in trades_in if t["exit_reason"] == "EXIT_TRAIL")
    pct_initsl = round(100.0 * n_initsl / n, 2)
    pct_trail = round(100.0 * n_trail / n, 2)

    span_days = (WINDOW_END_EXCL - WINDOW_START).total_seconds() / 86400.0
    trades_per_day = round(n / span_days, 3)

    long_pnl = round(sum(p for p, t in pnls if t["side"] == "LONG"), 2)
    short_pnl = round(sum(p for p, t in pnls if t["side"] == "SHORT"), 2)
    long_n = sum(1 for _, t in pnls if t["side"] == "LONG")
    short_n = sum(1 for _, t in pnls if t["side"] == "SHORT")

    return {
        "trades": n, "net": net, "pf": pf, "wr": wr, "payoff": payoff,
        "maxdd": maxdd, "pct_initsl": pct_initsl, "pct_trail": pct_trail,
        "trades_per_day": trades_per_day,
        "long_pnl": long_pnl, "short_pnl": short_pnl,
        "long_n": long_n, "short_n": short_n,
    }


# ---------------------------------------------------------------------------
# Ingestion (mirrors gen_thu_fri_backtests._ingest_run exactly).
# ---------------------------------------------------------------------------

def ingest_run(
    registry: ResearchRegistry,
    *,
    run_id: str,
    variant_id: str,
    strategy_name: str,
    familia: str,
    tf: str,
    params_delta: dict[str, Any],
    trades_all: list[dict[str, Any]],
    display_name: str,
) -> dict[str, Any]:
    strategy_id = registry.upsert_strategy(name=strategy_name, familia=familia, platform="python-sim")
    registry.upsert_variant(
        strategy_id=strategy_id, variant_id=variant_id,
        params_delta=params_delta, tf=tf, instrumento=SYMBOL,
        modo_salida=tf.lower(),
    )

    trades_in_window = [t for t in trades_all if t["entry_in_window"]]
    m = compute_metrics(trades_all)

    run_row = {
        "run_id": run_id,
        "variant_id": variant_id,
        "params_hash": None,
        "engine": "sentinel-sim",
        "fidelity": "screening",
        "periodo_desde": "2026-06-08",
        "periodo_hasta": "2026-07-07",
        "modelo_sim": "sim-report",
        "status": "OK",
        "trades": m["trades"],
        "net": m["net"],
        "pf": m["pf"] if m["pf"] not in (None, float("inf")) else None,
        "wr": m["wr"],
        "payoff": m["payoff"],
        "maxdd": m["maxdd"],
        "sharpe": None,
        "metrics_json": json.dumps({
            "display_name": display_name,
            "spread_model": "capitaria_0.5_at_fill",
            "warmup_from": WARMUP_START.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "feed_to_excl": FEED_END_EXCL.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_events_all_dates": len(trades_all),
            "events_in_window": m["trades"],
            "pct_exit_initsl": m["pct_initsl"],
            "pct_exit_trail": m["pct_trail"],
            "trades_per_day": m["trades_per_day"],
            "long_pnl": m["long_pnl"], "short_pnl": m["short_pnl"],
            "long_n": m["long_n"], "short_n": m["short_n"],
            "params": params_delta,
        }, ensure_ascii=False),
        "preregistro_id": None,
        "report_path": None,
        "trades_path": None,
        "equity_path": None,
        "signal_history_path": None,
        "fecha_corrida": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "seed": None,
        "config_hash": None,
        "source_file": "scripts/report/gen_variant_batch1.py",
        "source_row": None,
        "fidelity_ref": None,
    }

    conn = registry._connect()  # noqa: SLF001 -- idempotent delete-before-insert, same DB the public API writes to
    try:
        conn.execute("DELETE FROM trade WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM run WHERE run_id=?", (run_id,))
        conn.commit()
    finally:
        conn.close()

    registry.insert_run(run_row)

    trade_rows = []
    for t in trades_in_window:
        pnl = _pnl(t["side"], t["px_in"], t["px_out"])
        trade_rows.append({
            "trade_id": f"{run_id}-{t['signal_id']}-{t['ficha']}",
            "run_id": run_id,
            "origin": "strategy",
            "origin_id": variant_id,
            "session_id": None,
            "ts_in": _ts_str(t["ts_in_epoch"]),
            "ts_out": _ts_str(t["ts_out_epoch"]),
            "px_in": t["px_in"],
            "px_out": t["px_out"],
            "side": t["side"],
            "volume": LOT,
            "sl": None,
            "tp": None,
            "exit_reason": t["exit_reason"],
            "exit_reason_source": "sim_report",
            "pnl": pnl,
            "mae": None,
            "mfe": None,
            "snapshot_ref": None,
            "decision_trace_ref": None,
            "signal_id": t["signal_id"],
            "ficha": t["ficha"],
        })
    registry.insert_trades(run_id, trade_rows)

    registry.audit(
        "scripts.report.gen_variant_batch1", "sim_report_ingested",
        {"run_id": run_id, "variant_id": variant_id, "trades": m["trades"], "net": m["net"]},
    )

    return {"run_id": run_id, "variant_id": variant_id, "tf": tf, **m}


# ---------------------------------------------------------------------------
# V-14 diagnostic step (a): query existing fixture runs' long/short split.
# ---------------------------------------------------------------------------

def v14_fixture_diagnostic(registry: ResearchRegistry) -> list[dict[str, Any]]:
    conn = registry._connect()  # noqa: SLF001 -- read-only diagnostic query
    out = []
    try:
        for run_id in V14_FIXTURE_RUN_IDS:
            cur = conn.execute(
                "SELECT side, SUM(pnl), COUNT(*) FROM trade WHERE run_id=? GROUP BY side",
                (run_id,),
            )
            rows = {side: (pnl, cnt) for side, pnl, cnt in cur.fetchall()}
            run_cur = conn.execute(
                "SELECT trades, net, pf, wr, maxdd FROM run WHERE run_id=?", (run_id,)
            ).fetchone()
            out.append({
                "run_id": run_id,
                "trades": run_cur[0] if run_cur else None,
                "net": run_cur[1] if run_cur else None,
                "pf": run_cur[2] if run_cur else None,
                "wr": run_cur[3] if run_cur else None,
                "maxdd": run_cur[4] if run_cur else None,
                "long_pnl": round(rows.get("LONG", (0.0, 0))[0] or 0.0, 2),
                "long_n": rows.get("LONG", (0.0, 0))[1],
                "short_pnl": round(rows.get("SHORT", (0.0, 0))[0] or 0.0, 2),
                "short_n": rows.get("SHORT", (0.0, 0))[1],
            })
    finally:
        conn.close()
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, default=None,
                         help="optional path to dump the full raw results as JSON")
    args = parser.parse_args()

    registry = ResearchRegistry(DB_PATH)
    all_results: dict[str, Any] = {"v09": {}, "v14": {}, "v01": {}}

    # ===== V-09: control baseline, one run per TF =====
    v09_results: dict[str, dict[str, Any]] = {}
    for tf in TFS:
        trades = run_variant(tf, dict(V09_PARAMS))
        m = compute_metrics(trades)
        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v09-{tf.lower()}",
            variant_id=f"EMS_XAU_V09_{tf}_c1_bundle", strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**V09_PARAMS, "variant": "V-09 control (C04 bundle replica)"},
            trades_all=trades, display_name=f"EMASAR V-09 control baseline {tf}",
        )
        v09_results[tf] = r
        print(f"[V-09] {tf}: trades={r['trades']} net={r['net']} pf={r['pf']} wr={r['wr']} "
              f"maxdd={r['maxdd']} initsl%={r['pct_initsl']} trail%={r['pct_trail']}")
    all_results["v09"] = v09_results

    # ===== V-14: directional asymmetry =====
    # Step (a): diagnostic -- V-09 params long/short split per TF (from the
    # trades just simulated above) + the 3 existing fixture runs.
    v14_diag_v09: dict[str, Any] = {}
    for tf in TFS:
        trades = run_variant(tf, dict(V09_PARAMS))
        m = compute_metrics(trades)
        v14_diag_v09[tf] = {
            "long_pnl": m["long_pnl"], "long_n": m["long_n"],
            "short_pnl": m["short_pnl"], "short_n": m["short_n"],
        }
        print(f"[V-14 diag V-09] {tf}: long_pnl={m['long_pnl']} (n={m['long_n']}) "
              f"short_pnl={m['short_pnl']} (n={m['short_n']})")

    v14_diag_fixtures = v14_fixture_diagnostic(registry)
    for f in v14_diag_fixtures:
        print(f"[V-14 diag fixture] {f['run_id']}: long_pnl={f['long_pnl']} (n={f['long_n']}) "
              f"short_pnl={f['short_pnl']} (n={f['short_n']}) net={f['net']}")

    # Step (b): long-only vs short-only runs per TF, compare to "both" (V-09).
    v14_results: dict[str, dict[str, Any]] = {}
    for tf in TFS:
        both_r = v09_results[tf]

        long_kwargs = {**V09_PARAMS, "allow_short": False}
        long_trades = run_variant(tf, long_kwargs)
        long_m = compute_metrics(long_trades)

        short_kwargs = {**V09_PARAMS, "allow_long": False}
        short_trades = run_variant(tf, short_kwargs)
        short_m = compute_metrics(short_trades)

        # winner = whichever single-side run has the higher net.
        if long_m["net"] >= short_m["net"]:
            winner_side, winner_kwargs, winner_trades, winner_m = "long", long_kwargs, long_trades, long_m
        else:
            winner_side, winner_kwargs, winner_trades, winner_m = "short", short_kwargs, short_trades, short_m

        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v14-{winner_side}-{tf.lower()}",
            variant_id=f"EMS_XAU_V14_{winner_side.upper()}_{tf}_c1", strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**winner_kwargs, "variant": f"V-14 {winner_side}-only (winner)"},
            trades_all=winner_trades,
            display_name=f"EMASAR V-14 {winner_side}-only (winner) {tf}",
        )

        v14_results[tf] = {
            "both": both_r, "long": long_m, "short": short_m,
            "winner_side": winner_side, "winner_run_id": r["run_id"],
        }
        print(f"[V-14] {tf}: both_net={both_r['net']} long_net={long_m['net']} "
              f"short_net={short_m['net']} winner={winner_side} ingested={r['run_id']}")

    all_results["v14"] = {"diag_v09": v14_diag_v09, "diag_fixtures": v14_diag_fixtures, "per_tf": v14_results}

    # ===== V-01: legal-stop range_k sweep =====
    v01_results: dict[str, dict[str, Any]] = {}
    for tf in TFS:
        sweep_metrics: list[dict[str, Any]] = []
        best_r = None
        best_net = None
        best_k = None
        for k in V01_RANGE_K_GRID:
            kwargs = {**V09_PARAMS, "init_sl_range_k": k}
            trades = run_variant(tf, kwargs)
            m = compute_metrics(trades)
            sweep_metrics.append({"k": k, **m})
            print(f"[V-01] {tf} k={k}: trades={m['trades']} net={m['net']} pf={m['pf']} "
                  f"wr={m['wr']} maxdd={m['maxdd']} initsl%={m['pct_initsl']}")
            if best_net is None or m["net"] > best_net:
                best_net = m["net"]
                best_k = k
                best_kwargs = kwargs
                best_trades = trades

        r = ingest_run(
            registry, run_id=f"sim-report-emasar-v01-{tf.lower()}",
            variant_id=f"EMS_XAU_V01_{tf}_c1_k{str(best_k).replace('.', 'p')}",
            strategy_name="EMASAR", familia="emasar",
            tf=tf, params_delta={**best_kwargs, "variant": f"V-01 range_k sweep, chosen k={best_k}"},
            trades_all=best_trades,
            display_name=f"EMASAR V-01 range_k sweep, best k={best_k} {tf}",
        )
        v01_results[tf] = {"sweep": sweep_metrics, "best_k": best_k, "ingested": r}
        print(f"[V-01] {tf}: BEST k={best_k} net={r['net']} ingested={r['run_id']}")

    all_results["v01"] = v01_results

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        with args.report_json.open("w", encoding="utf-8") as fh:
            json.dump(all_results, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nRaw results JSON written to {args.report_json}")

    print("\n==== DONE ====")


if __name__ == "__main__":
    main()
