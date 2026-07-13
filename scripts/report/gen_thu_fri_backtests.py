"""scripts/report/gen_thu_fri_backtests.py — Task 1 (Trade View backtests).

Generates 4 offline backtest runs for the nearest available Thu/Fri window
(2026-07-02/07-03, XAUUSD) and ingests them into `data/research.db` in the
SAME shape Trade View already loads (reference: run `mt5import-abc1043ef513`).

Reuses (does NOT modify) the vendored reference engines:
    - sentinel_engine/strategies/emasar_ref.py::simular
    - sentinel_engine/strategies/_supertrend_ref.py::supertrend
and writes ONLY via the public `ResearchRegistry` API (same API
`sentinel_engine/ingest_tokata/*` uses) — no schema/production-code edits.

Spread model (Capitaria/MT5, 0.5 flat): lake bars are BID. `ask = bid + 0.5`.
Long entries fill at ask, long exits/stops fill at bid. Short entries fill at
bid, short exits/stops fill at ask. Applied AT THE FILL (per-event), not as a
post-hoc PnL haircut, per the brief.

Window: bars are fed from the start of the July lake tier (2026-07-01, for
indicator warmup) through 2026-07-03 23:59:59 UTC, but only events whose
ENTRY bar falls within [2026-07-02 00:00, 2026-07-04 00:00) UTC are kept as
trades in the run (2026-07-02 and 2026-07-03 are the "nearest available
Thu/Fri", confirmed against the July lake tier which ends 2026-07-07).

Run this script directly: `python scripts/report/gen_thu_fri_backtests.py`.
Idempotent: re-running upserts the same 4 run_ids/trade_ids rather than
duplicating rows.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sentinel_engine.strategies.emasar_ref import simular  # noqa: E402
from sentinel_engine.strategies._supertrend_ref import supertrend, flips  # noqa: E402
from sentinel_engine.strategies.emasar_ref import _atr_wilder  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

LAKE_ROOT = ROOT / "data" / "lake"
DB_PATH = ROOT / "data" / "research.db"
SYMBOL = "XAUUSD"
SPREAD = 0.5  # Capitaria/MT5 real spread, flat, applied at fill.
LOT = 0.10
CONTRACT_SIZE = 100.0  # XAUUSD: $100 per $1 move per 1.00 lot (confirmed vs mt5import-abc1043ef513).

# --- EMASAR window (runs 1-3): nearest available Thu/Fri, per the brief. ---
WARMUP_START = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_START = datetime(2026, 7, 2, 0, 0, 0, tzinfo=timezone.utc)
WINDOW_END_EXCL = datetime(2026, 7, 4, 0, 0, 0, tzinfo=timezone.utc)  # entries in [07-02, 07-04)
FEED_END_EXCL = WINDOW_END_EXCL  # do not feed bars past 07-03 (no lake backfill per brief)

# --- SuperTrend window (run 4): WIDER recent span (correction #2). The 2-day
# Thu/Fri window gave 0 flips-in-window; SuperTrend M15 flips ~1.5x/week, so a
# ~4-week span is used to capture many complete flip-to-flip positions. Stays
# ENTIRELY within available lake data (M15 lake ends 2026-07-07 18:45Z); no
# backfill. Warmup starts 2026-06-01 so ATR(14) is fully seeded by 06-08. ---
ST_WARMUP_START = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
ST_WINDOW_START = datetime(2026, 6, 8, 0, 0, 0, tzinfo=timezone.utc)
ST_WINDOW_END_EXCL = datetime(2026, 7, 8, 0, 0, 0, tzinfo=timezone.utc)  # captures through 07-07
ST_FEED_END_EXCL = ST_WINDOW_END_EXCL
ST_LAKE_MONTHS = ("2026-06", "2026-07")

REPORT_JSON = Path(
    r"C:\Users\tomas\AppData\Local\Temp\claude\D--FOREX\7c8038c7-1a6a-499d-a8f8-398260d5dbb4"
    r"\scratchpad\task1_indicator_manifest.json"
)


def _load_bars(
    tf: str,
    months: tuple[str, ...] = ("2026-07",),
    warm_start: datetime = WARMUP_START,
    feed_end_excl: datetime = FEED_END_EXCL,
) -> list[dict[str, Any]]:
    """Load the lake tier(s) for XAUUSD/{tf} across `months`, bars in
    [warm_start, feed_end_excl). Defaults reproduce the original single-month
    (July) EMASAR feed; the SuperTrend run passes wider months/window."""
    warm_epoch = int(warm_start.timestamp())
    end_epoch = int(feed_end_excl.timestamp())
    bars = []
    for month in months:
        path = LAKE_ROOT / SYMBOL / tf / f"{month}.parquet"
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


def _ts_str(epoch: int) -> str:
    """MT5-dotted UTC string, matching mt5import-abc1043ef513's ts_in/ts_out
    format ("2026.01.11 20:00:00") -- the registry's _normalize_ts_iso_utc
    reformats this to ISO-8601Z on read (registry2.py L119-141), so this is
    the byte-identical convention the reference run already uses, not a
    workaround."""
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return dt.strftime("%Y.%m.%d %H:%M:%S")


def _in_window(epoch: int, start: datetime = WINDOW_START, end_excl: datetime = WINDOW_END_EXCL) -> bool:
    return int(start.timestamp()) <= epoch < int(end_excl.timestamp())


# ---------------------------------------------------------------------------
# Spread-at-fill helpers (bars are BID; ask = bid + SPREAD).
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
# EMASAR runs
# ---------------------------------------------------------------------------

def run_emasar_variant(tf: str, sim_kwargs: dict[str, Any], strategy_mode: int) -> tuple[list[dict], list[dict]]:
    """Runs emasar_ref.simular on the loaded `tf` bars, applies spread at
    fill, and returns (trades, eventos_raw). Pairs each EXIT_* event with the
    open position that owns its `ficha` tag -- correct for V1's
    3-simultaneous-fichas-per-entry-event shape (a single ENTRY_* event opens
    F1+F2+(F3) at once; each closes independently, later, with its own
    EXIT_* event carrying `ficha`). `strategy_mode` (1=V1 3 fichas, 2=V2 1
    ficha) determines the set of fichas a fresh entry opens; simular() never
    lets more than one signal group be open at a time (no reentry while
    fichas are open), so `last_signal_id` always resolves the right group."""
    bars = _load_bars(tf)
    eventos = simular(bars, **sim_kwargs)

    trades: list[dict[str, Any]] = []
    # open_positions: signal_id -> {entry info, fichas_remaining:set}
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
            fichas_remaining = {"F1", "F2", "F3"} if strategy_mode == 1 else {"F1"}
            open_positions[signal_id] = {
                "signal_id": signal_id, "t": bar["t"], "side": side_l,
                "side_ui": side_ui, "precio": ev["precio"],
                "fichas_remaining": fichas_remaining,
            }
            last_signal_id = signal_id
        elif motivo.startswith("EXIT"):
            ficha = ev.get("ficha") or "F1"
            # Find the open position that still owns this ficha (there is at
            # most one open signal at a time by construction of simular()'s
            # "no reentry while fichas open" rule -- so last_signal_id always
            # resolves correctly).
            pos = open_positions.get(last_signal_id)
            if pos is None or ficha not in pos["fichas_remaining"]:
                # defensive fallback: scan all open positions
                pos = None
                for sid, p in open_positions.items():
                    if ficha in p["fichas_remaining"]:
                        pos = p
                        last_signal_id = sid
                        break
                if pos is None:
                    continue

            entry_bid = pos["precio"]
            entry_side_l = pos["side"]
            entry_px = _entry_fill(entry_side_l, entry_bid)
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

    return trades, eventos


# ---------------------------------------------------------------------------
# SuperTrend always-in run
# ---------------------------------------------------------------------------

def run_supertrend_always_in(tf: str, atr_period: int, mult: float) -> tuple[list[dict], int]:
    """Always-in SuperTrend: on every trend flip, close the open position
    (if any) and open the opposite side at the SAME bar's close. First flip
    (or the first bar, per TOKATA's ST0 reference behaviour) opens the
    initial position with no prior exit. No SL/TP/session filter (matches
    'flip de tendencia = unica senal' from mt5_ledger_st0.csv /
    STR_XAU_LS_ORIG_p14x3_M15). Uses the WIDER SuperTrend window
    (ST_WINDOW_*, correction #2) so >=1 complete flip-to-flip position lands
    in-window. Returns (trades_all, n_flips_total)."""
    bars = _load_bars(tf, months=ST_LAKE_MONTHS,
                      warm_start=ST_WARMUP_START, feed_end_excl=ST_FEED_END_EXCL)
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    atr = _atr_wilder(highs, lows, closes, atr_period)
    atr_filled = [a if a is not None else 0.0 for a in atr]
    trend, _line = supertrend(highs, lows, closes, atr_filled, mult)

    flip_list = flips(trend)  # [(idx, new_trend), ...]
    # Position opens at the FIRST index where ATR is valid (i.e. trend is
    # meaningful), side = trend at that index; flips thereafter close+reopen.
    first_valid = next((i for i in range(len(atr)) if atr[i] is not None), None)
    if first_valid is None:
        return [], 0

    trades: list[dict[str, Any]] = []
    side_l = "L" if trend[first_valid] == 1 else "S"
    entry_bid = closes[first_valid]
    entry_t = bars[first_valid]["t"]
    signal_seq = 1

    for idx, new_trend in flip_list:
        if idx < first_valid:
            continue
        bar = bars[idx]
        exit_bid = closes[idx]
        exit_px = _exit_fill(side_l, exit_bid)
        entry_px = _entry_fill(side_l, entry_bid)
        trades.append({
            "signal_id": f"sig-{entry_t}-{signal_seq}",
            "ficha": "F1",
            "side": "LONG" if side_l == "L" else "SHORT",
            "ts_in_epoch": entry_t,
            "ts_out_epoch": bar["t"],
            "px_in": round(entry_px, 2),
            "px_out": round(exit_px, 2),
            "exit_reason": "EXIT_STFLIP",
            "entry_in_window": _in_window(entry_t, ST_WINDOW_START, ST_WINDOW_END_EXCL),
        })
        # reopen opposite side immediately at the same bar/price
        side_l = "L" if new_trend == 1 else "S"
        entry_bid = exit_bid
        entry_t = bar["t"]
        signal_seq += 1

    # NOTE: the position open at feed-end (never flipped again before the
    # feed cutoff) is left OPEN by design -- it has no exit event yet, so it
    # is not emitted as a trade (matches "no SL/TP/session, flip=only exit":
    # an unflipped position simply hasn't produced an EXIT signal within the
    # fed window). Documented as a loose end in the report.
    return trades, len(flip_list)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def _ingest_run(
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
    periodo_desde: str = "2026-07-02",
    periodo_hasta: str = "2026-07-03",
    warmup_from_iso: str = "2026-07-01T00:00:00Z",
    feed_to_excl_iso: str = "2026-07-04T00:00:00Z",
    window_note: str | None = None,
) -> dict[str, Any]:
    """Upserts strategy/variant/param_set + run + trade rows via the SAME
    public ResearchRegistry API sentinel_engine/ingest_tokata/{ledger,
    signals}.py use (insert_run/insert_trades/upsert_*), matching the shape
    of mt5import-abc1043ef513. Idempotent: re-running this script updates
    (not duplicates) the run row (ledger.py's own IntegrityError->UPDATE
    pattern) and re-inserts trades under STABLE deterministic trade_ids, so
    a second run first deletes this run_id's existing trades, matching the
    "re-correr no duplica" requirement in the brief."""
    strategy_id = registry.upsert_strategy(name=strategy_name, familia=familia, platform="python-sim")
    registry.upsert_variant(
        strategy_id=strategy_id, variant_id=variant_id,
        params_delta=params_delta, tf=tf, instrumento=SYMBOL,
        modo_salida=tf.lower(),
    )

    trades_in_window = [t for t in trades_all if t["entry_in_window"]]

    n = len(trades_in_window)
    net = round(sum(_pnl(t["side"], t["px_in"], t["px_out"]) for t in trades_in_window), 2)
    wins = [t for t in trades_in_window if _pnl(t["side"], t["px_in"], t["px_out"]) > 0]
    losses = [t for t in trades_in_window if _pnl(t["side"], t["px_in"], t["px_out"]) < 0]
    gross_win = sum(_pnl(t["side"], t["px_in"], t["px_out"]) for t in wins)
    gross_loss = -sum(_pnl(t["side"], t["px_in"], t["px_out"]) for t in losses)
    pf = round(gross_win / gross_loss, 4) if gross_loss > 0 else (None if gross_win == 0 else float("inf"))
    wr = round(100.0 * len(wins) / n, 2) if n else None
    avg_win = (gross_win / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    payoff = round(avg_win / avg_loss, 4) if avg_loss > 0 else None

    # maxdd: peak-to-trough on cumulative pnl ordered by ts_out.
    ordered = sorted(trades_in_window, key=lambda t: t["ts_out_epoch"])
    cum = 0.0
    peak = 0.0
    maxdd = 0.0
    for t in ordered:
        cum += _pnl(t["side"], t["px_in"], t["px_out"])
        peak = max(peak, cum)
        maxdd = max(maxdd, peak - cum)
    maxdd = round(maxdd, 2)

    run_row = {
        "run_id": run_id,
        "variant_id": variant_id,
        "params_hash": None,
        "engine": "sentinel-sim",
        "fidelity": "screening",
        "periodo_desde": periodo_desde,
        "periodo_hasta": periodo_hasta,
        "modelo_sim": "sim-report",
        "status": "OK",
        "trades": n,
        "net": net,
        "pf": pf if pf not in (None, float("inf")) else None,
        "wr": wr,
        "payoff": payoff,
        "maxdd": maxdd,
        "sharpe": None,
        "metrics_json": json.dumps({
            "display_name": display_name,
            "spread_model": "capitaria_0.5_at_fill",
            "warmup_from": warmup_from_iso,
            "feed_to_excl": feed_to_excl_iso,
            "total_events_all_dates": len(trades_all),
            "events_in_window": n,
            **({"window_note": window_note} if window_note else {}),
        }, ensure_ascii=False),
        "preregistro_id": None,
        "report_path": None,
        "trades_path": None,
        "equity_path": None,
        "signal_history_path": None,
        "fecha_corrida": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "seed": None,
        "config_hash": None,
        "source_file": "scripts/report/gen_thu_fri_backtests.py",
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
    for i, t in enumerate(trades_in_window):
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
        "scripts.report.gen_thu_fri_backtests", "sim_report_ingested",
        {"run_id": run_id, "variant_id": variant_id, "trades": n, "net": net},
    )

    return {
        "run_id": run_id, "variant_id": variant_id, "tf": tf,
        "trades": n, "net": net, "pf": pf, "wr": wr, "payoff": payoff, "maxdd": maxdd,
        "total_events_all_window_incl_warmup_dates": len(trades_all),
    }


def main() -> None:
    registry = ResearchRegistry(DB_PATH)
    results = []
    manifest: dict[str, Any] = {"generated": datetime.now(timezone.utc).isoformat(), "runs": []}

    # === CORRECTION 1 (2026-07-13): the trader's REAL, legal (broker-valid)
    # stop, NOT the Fase-0 3-pip init_sl_pips=3.0 (=0.03, below broker min /
    # eaten by the 0.5 spread -> instant stop-outs). Decoded from the ONLY
    # legal-stop config the TOKATA ledger records as VERIFIED (VERIF-OK): the
    # week-exploration winner "GANADOR C04" -- ledger row
    # `EMS_XAU_V1_M1_c2_fixSLrng_trail100` and its reproduced .ini
    # `mt5/configs/generated/ems_wk_repro/EMS_wk_C04_TRAIL100_REPRO.ini`, which
    # sets `InitSL_Mode=1 InitSL_RangeK=1.0` = SL at the signal candle's range
    # (init_sl_mode='range', init_sl_range_k=1.0 in emasar_ref.simular). This
    # range-SL is ALSO labelled "correccion trader 2026-07-09" directly in the
    # production emasar_ref.py::simular docstring -- i.e. it IS the trader's
    # own corrected stop, and it's legal (candle range >> broker min). Applied
    # to the 3 EMASAR runs; SAR/confirm_mode/TF per each variant unchanged.
    # NOTE: the C04 .ini ALSO bundled RequireEmaOrder=false + Trail_Pips=100 +
    # ConfirmMode=1; per the correction ("keep everything else the same") we
    # change ONLY the stop, leaving each variant's own gate/SAR/trail intact.
    # (C04 bundle flagged as a loose end in the report.)
    LEGAL_STOP = dict(init_sl_mode="range", init_sl_range_k=1.0)

    # ---- Run 1: EMASAR original SAR 0.3/0.3, V1, M2, confirm_mode=2 ----
    sim_kwargs_1 = dict(
        strategy_mode=1, confirm_mode=2, symbol=SYMBOL,
        sar_step=0.3, sar_max=0.3, **LEGAL_STOP,
        # rest: emasar_ref Fase-0 defaults (ema 8/20/5, st 10/3, mom 14,
        # trail_pips=170.0, confirm_count=2).
    )
    trades1, ev1 = run_emasar_variant("M2", sim_kwargs_1, strategy_mode=1)
    r1 = _ingest_run(
        registry, run_id="sim-report-emasar-orig-sar3m3-m2",
        variant_id="EMS_XAU_V1_M2_c2_sar3m3", strategy_name="EMASAR", familia="emasar",
        tf="M2", params_delta={
            "strategy_mode": 1, "confirm_mode": 2, "sar_step": 0.3, "sar_max": 0.3,
            "ema_fast": 8, "ema_slow": 20, "ema_pull": 5, "st_atr_period": 10, "st_mult": 3.0,
            "mom_period": 14, "trail_pips": 170.0, "confirm_count": 2,
            "init_sl_mode": "range", "init_sl_range_k": 1.0,
        },
        trades_all=trades1, display_name="EMASAR original (SAR 0.3/0.3), legal range-SL",
    )
    results.append(r1)

    # ---- Run 2: EMASAR most-PF sar005m05, V1, M5, confirm_mode=2 ----
    sim_kwargs_2 = dict(
        strategy_mode=1, confirm_mode=2, symbol=SYMBOL,
        sar_step=0.005, sar_max=0.05, **LEGAL_STOP,
    )
    trades2, ev2 = run_emasar_variant("M5", sim_kwargs_2, strategy_mode=1)
    r2 = _ingest_run(
        registry, run_id="sim-report-emasar-pf-sar005m05-m5",
        variant_id="EMS_XAU_V1_M5_c2_sar005m05", strategy_name="EMASAR", familia="emasar",
        tf="M5", params_delta={
            "strategy_mode": 1, "confirm_mode": 2, "sar_step": 0.005, "sar_max": 0.05,
            "ema_fast": 8, "ema_slow": 20, "ema_pull": 5, "st_atr_period": 10, "st_mult": 3.0,
            "mom_period": 14, "trail_pips": 170.0, "confirm_count": 2,
            "init_sl_mode": "range", "init_sl_range_k": 1.0,
        },
        trades_all=trades2, display_name="EMASAR mayor PF (sar005m05), legal range-SL",
    )
    results.append(r2)

    # ---- Run 3: EMASAR most-WR V2_M15_c1, V2, M15, confirm_mode=1 ----
    # V2 has NO init SL by default (v2_use_trail=False -> only engulfing exit),
    # so the legal-stop kwarg is a NO-OP here (documented): _sl_inicial is only
    # called for V2 when v2_use_trail AND init_sl_pips>0, neither of which we
    # set. Passing LEGAL_STOP keeps the call uniform; results are identical to
    # a V2 run without it (verified: same 7 engulfing exits).
    sim_kwargs_3 = dict(
        strategy_mode=2, confirm_mode=1, symbol=SYMBOL,
        sar_step=0.02, sar_max=0.20, **LEGAL_STOP,  # Fase 0 default SAR; range-SL is a no-op for V2
    )
    trades3, ev3 = run_emasar_variant("M15", sim_kwargs_3, strategy_mode=2)
    r3 = _ingest_run(
        registry, run_id="sim-report-emasar-wr-v2m15c1",
        variant_id="EMS_XAU_V2_M15_c1", strategy_name="EMASAR", familia="emasar",
        tf="M15", params_delta={
            "strategy_mode": 2, "confirm_mode": 1, "sar_step": 0.02, "sar_max": 0.20,
            "ema_fast": 8, "ema_slow": 20, "ema_pull": 5, "st_atr_period": 10, "st_mult": 3.0,
            "mom_period": 14, "trail_pips": 170.0, "confirm_count": 2,
            "init_sl_mode": "range", "init_sl_range_k": 1.0,
            "_note": "V2: no init SL by design (only engulfing exit); range-SL is a no-op here",
        },
        trades_all=trades3, display_name="EMASAR mayor WR (V2_M15_c1)",
    )
    results.append(r3)

    # ---- Run 4: SuperTrend p14x3, always-in, M15 -- WIDER window (corr #2) ----
    trades4, n_flips = run_supertrend_always_in("M15", atr_period=14, mult=3.0)
    r4 = _ingest_run(
        registry, run_id="sim-report-supertrend-p14x3-m15",
        variant_id="STR_XAU_LS_ORIG_p14x3_M15", strategy_name="SuperTrend", familia="supertrend",
        tf="M15", params_delta={"atr_period": 14, "mult": 3.0, "mode": "always_in"},
        trades_all=trades4, display_name="SuperTrend p14x3 (always-in), 4-week window",
        periodo_desde="2026-06-08", periodo_hasta="2026-07-07",
        warmup_from_iso="2026-06-01T00:00:00Z", feed_to_excl_iso="2026-07-08T00:00:00Z",
        window_note=("WIDER window than the EMASAR runs (07-02/03): the 2-day Thu/Fri window "
                     "yielded 0 SuperTrend flips-in-window. Widened to 2026-06-08..2026-07-07 "
                     "(entirely within the M15 lake, which ends 2026-07-07 18:45Z; no backfill) "
                     "to capture many complete flip-to-flip positions."),
    )
    results.append(r4)

    print(json.dumps(results, indent=2, ensure_ascii=False))

    # ---- Indicator manifest ----
    manifest["runs"] = [
        {
            "run_id": "sim-report-emasar-orig-sar3m3-m2",
            "display_name": "EMASAR original (SAR 0.3/0.3)",
            "engine": "EMASAR V1",
            "native_tf": "M2",
            "source_fn": "emasar_ref.py::simular",
            "indicators": [
                {"name": "EMA", "params": {"period": 8}, "panel": "price",
                 "math_fn": "emasar_ref.ema_series(closes, 8)"},
                {"name": "EMA", "params": {"period": 20}, "panel": "price",
                 "math_fn": "emasar_ref.ema_series(closes, 20)"},
                {"name": "Parabolic SAR", "params": {"step": 0.3, "max": 0.3}, "panel": "price",
                 "math_fn": "emasar_ref.sar_series(highs, lows, 0.3, 0.3)"},
                {"name": "SuperTrend", "params": {"atr_period": 10, "mult": 3.0}, "panel": "price",
                 "math_fn": "_supertrend_ref.supertrend(highs, lows, closes, atr(period=10), 3.0)",
                 "note": "V1-internal F2 exit signal (SuperTrend break), NOT the standalone run-4 strategy"},
                {"name": "Awesome Oscillator (AO)", "params": {}, "panel": "subpanel",
                 "math_fn": "emasar_ref.ao_series(highs, lows)"},
                {"name": "Accelerator (AC)", "params": {}, "panel": "subpanel",
                 "math_fn": "emasar_ref.ac_series(highs, lows)"},
                {"name": "Momentum", "params": {"period": 14}, "panel": "subpanel",
                 "math_fn": "emasar_ref.momentum_series(closes, 14)"},
            ],
            "render_other_tf_note": "Same params (EMA 8/20, SAR 0.3/0.3, ST 10/3, AO/AC/Mom(14)) "
                                     "apply unchanged if rendered on M1/M5/M15/etc -- only the input "
                                     "bars/closes/highs/lows change per TF, not the indicator params.",
        },
        {
            "run_id": "sim-report-emasar-pf-sar005m05-m5",
            "display_name": "EMASAR mayor PF (sar005m05)",
            "engine": "EMASAR V1",
            "native_tf": "M5",
            "source_fn": "emasar_ref.py::simular",
            "indicators": [
                {"name": "EMA", "params": {"period": 8}, "panel": "price",
                 "math_fn": "emasar_ref.ema_series(closes, 8)"},
                {"name": "EMA", "params": {"period": 20}, "panel": "price",
                 "math_fn": "emasar_ref.ema_series(closes, 20)"},
                {"name": "Parabolic SAR", "params": {"step": 0.005, "max": 0.05}, "panel": "price",
                 "math_fn": "emasar_ref.sar_series(highs, lows, 0.005, 0.05)"},
                {"name": "SuperTrend", "params": {"atr_period": 10, "mult": 3.0}, "panel": "price",
                 "math_fn": "_supertrend_ref.supertrend(highs, lows, closes, atr(period=10), 3.0)",
                 "note": "V1-internal F2 exit signal (SuperTrend break)"},
                {"name": "Awesome Oscillator (AO)", "params": {}, "panel": "subpanel",
                 "math_fn": "emasar_ref.ao_series(highs, lows)"},
                {"name": "Accelerator (AC)", "params": {}, "panel": "subpanel",
                 "math_fn": "emasar_ref.ac_series(highs, lows)"},
                {"name": "Momentum", "params": {"period": 14}, "panel": "subpanel",
                 "math_fn": "emasar_ref.momentum_series(closes, 14)"},
            ],
            "render_other_tf_note": "Same params apply unchanged on any TF.",
        },
        {
            "run_id": "sim-report-emasar-wr-v2m15c1",
            "display_name": "EMASAR mayor WR (V2_M15_c1)",
            "engine": "EMASAR V2",
            "native_tf": "M15",
            "source_fn": "emasar_ref.py::simular",
            "indicators": [
                {"name": "EMA", "params": {"period": 8}, "panel": "price",
                 "math_fn": "emasar_ref.ema_series(closes, 8)"},
                {"name": "EMA", "params": {"period": 20}, "panel": "price",
                 "math_fn": "emasar_ref.ema_series(closes, 20)"},
                {"name": "EMA (pullback, V2-only)", "params": {"period": 5}, "panel": "price",
                 "math_fn": "emasar_ref.ema_series(closes, 5)",
                 "note": "V2 uses EMA5 (not EMA8) as the G3 pullback reference"},
                {"name": "Parabolic SAR", "params": {"step": 0.02, "max": 0.20}, "panel": "price",
                 "math_fn": "emasar_ref.sar_series(highs, lows, 0.02, 0.20)",
                 "note": "Fase-0 default SAR, unchanged for this variant (see report §params)"},
                {"name": "Awesome Oscillator (AO)", "params": {}, "panel": "subpanel",
                 "math_fn": "emasar_ref.ao_series(highs, lows)"},
                {"name": "Accelerator (AC)", "params": {}, "panel": "subpanel",
                 "math_fn": "emasar_ref.ac_series(highs, lows)"},
                {"name": "Momentum", "params": {"period": 14}, "panel": "subpanel",
                 "math_fn": "emasar_ref.momentum_series(closes, 14)"},
            ],
            "render_other_tf_note": "V2 has NO SuperTrend (that is a V1-only F2 exit); do not draw ST "
                                     "for this run. Same params apply unchanged on any TF.",
        },
        {
            "run_id": "sim-report-supertrend-p14x3-m15",
            "display_name": "SuperTrend p14x3 (always-in)",
            "engine": "SuperTrend always-in",
            "native_tf": "M15",
            "source_fn": "_supertrend_ref.py::supertrend",
            "indicators": [
                {"name": "SuperTrend", "params": {"atr_period": 14, "mult": 3.0}, "panel": "price",
                 "math_fn": "_supertrend_ref.supertrend(highs, lows, closes, "
                             "emasar_ref._atr_wilder(highs, lows, closes, 14), 3.0)",
                 "note": "This IS the strategy's only signal (flip = entry+exit); no EMA/SAR/oscillators apply"},
            ],
            "render_other_tf_note": "Same ATR(14)/mult(3.0) params apply unchanged on any TF.",
        },
    ]

    manifest["notes"] = {
        "legal_stop_2026-07-13": (
            "EMASAR runs (1-3) use the trader's LEGAL stop: init_sl_mode='range', "
            "init_sl_range_k=1.0 (SL at the signal candle's range), NOT the Fase-0 3-pip stop. "
            "Source: verified week-winner C04 (.ini EMS_wk_C04_TRAIL100_REPRO.ini) + emasar_ref.py "
            "'correccion trader 2026-07-09' docstring. This is an EXECUTION param (position SL), not "
            "a drawable indicator -- the indicator params above are unchanged. The per-trade SL level "
            "is not persisted in `trade.sl` (kept None); EXIT_INITSL trades carry the stop-out price in "
            "px_out, and the SL rule (signal-candle range) is deterministic from the run params if needed."
        ),
        "supertrend_window_2026-07-13": (
            "Run 4 (SuperTrend) uses a WIDER window (2026-06-08..2026-07-07) than runs 1-3 "
            "(2026-07-02/03) because the 2-day window gave 0 flips. When rendering run 4 in Trade "
            "View, default its candle window to its own periodo (June 8 - July 7), not the Thu/Fri span."
        ),
    }

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    print(f"\nIndicator manifest written to {REPORT_JSON}")


if __name__ == "__main__":
    main()
