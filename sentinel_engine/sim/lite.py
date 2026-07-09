"""sentinel_engine.sim.lite — backtest-lite engine (M2.5).

Minimal, deterministic bar-replay engine over the Parquet lake: one
position at a time, entries fill at the **next bar's open** (no look-ahead:
the policy only sees bars `[0..i]` when deciding at `i`, and the resulting
order fills at bar `i+1`'s open), a constant spread per instrument, zero
commission by default, and **SL-first conservative** intrabar resolution
(if a bar's range could hit both an exit signal and a hard stop, the stop
wins — conservative for backtest optimism). This is explicitly a lean
early slice of the future Tier-1 sim (plan §B1 has the full
OrderIntent/BarContext/broker-validity machinery) — no broker-validity
checks, no slippage model, no multi-position support here.

`run_backtest_lite(policy, symbol, tf, desde, hasta, costs) -> (run_dict, trades)`
is pure and deterministic: same inputs (policy params, symbol/tf/window,
costs, and the on-disk lake contents) always produce the same trade list —
there is no randomness, no wall-clock dependency in the simulation path
itself (only `run_dict["fecha_corrida"]` is wall-clock, and callers can
override it for reproducibility in tests).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from sentinel_engine.service.bars import load_tf_frame

# Constant spread per instrument, in price units (plan M2.5: "spread const
# por instrumento"). Additive registry, extend as new instruments are
# backtested; unknown instruments default to 0.0 (no spread modeled).
DEFAULT_SPREADS: dict[str, float] = {
    "XAUUSD": 0.30,
    "XAGUSD": 0.02,
    "EURUSD": 0.00010,
    "USDCLP": 2.0,
    "NQ100": 1.0,
}


def _default_spread(symbol: str) -> float:
    return DEFAULT_SPREADS.get(symbol.upper(), 0.0)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _frame_to_bars(df: pd.DataFrame) -> list[dict[str, Any]]:
    bars = []
    for ts, row in df.iterrows():
        bars.append({
            "ts": ts,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    return bars


def run_backtest_lite(
    policy: Any,
    symbol: str,
    tf: str,
    desde: str | pd.Timestamp | None,
    hasta: str | pd.Timestamp | None,
    costs: dict[str, Any] | None = None,
    lake_root: Path | str = Path("data/lake"),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run a minimal, deterministic backtest of `policy` over `symbol`/`tf`
    bars in `[desde, hasta]` (inclusive, causal — never reads a bar after
    `hasta`). `policy` must expose `signal_at(bars, i) -> "LONG"|"SHORT"|None`
    and `should_exit(bars, i, side) -> bool` (see
    `sentinel_engine.strategies.emasar.EmasarPolicy`).

    `costs`: `{"spread": float, "commission": float}` — `spread` defaults
    per-instrument (`DEFAULT_SPREADS`), `commission` defaults to 0.0 and is
    subtracted from `pnl` per round-trip trade.

    Returns `(run_dict, trades)`: `run_dict` is shaped for
    `ResearchRegistry.insert_run` (caller fills in `run_id`/`variant_id`/
    `engine`/`fidelity`), `trades` is a list of dicts shaped for
    `ResearchRegistry.insert_trades` (caller fills in `trade_id`).
    """
    costs = costs or {}
    spread = float(costs.get("spread", _default_spread(symbol)))
    commission = float(costs.get("commission", 0.0))

    lake_root = Path(lake_root)
    ts_from = pd.Timestamp(desde, tz="UTC") if desde else None
    ts_to = pd.Timestamp(hasta, tz="UTC") if hasta else None

    df = load_tf_frame(lake_root, symbol, tf)
    if not df.empty:
        if ts_from is not None:
            df = df[df.index >= ts_from]
        if ts_to is not None:
            df = df[df.index <= ts_to]

    bars = _frame_to_bars(df)
    n = len(bars)

    trades: list[dict[str, Any]] = []
    open_trade: dict[str, Any] | None = None  # side, ts_in, px_in, sl

    def _open(i: int, side: str) -> None:
        nonlocal open_trade
        fill_bar = bars[i]
        half_spread = spread / 2.0
        px_in = fill_bar["open"] + half_spread if side == "LONG" else fill_bar["open"] - half_spread
        open_trade = {"side": side, "ts_in": fill_bar["ts"], "px_in": px_in, "entry_idx": i}

    def _close(i: int, exit_reason: str) -> None:
        nonlocal open_trade
        assert open_trade is not None
        fill_bar = bars[i]
        half_spread = spread / 2.0
        side = open_trade["side"]
        px_out = fill_bar["open"] - half_spread if side == "LONG" else fill_bar["open"] + half_spread
        px_in = open_trade["px_in"]
        sign = 1.0 if side == "LONG" else -1.0
        pnl = sign * (px_out - px_in) - commission
        # MAE/MFE over the trade's held bars (entry bar .. exit-decision bar).
        held = bars[open_trade["entry_idx"]:i + 1]
        if side == "LONG":
            mfe = max((b["high"] - px_in) for b in held)
            mae = min((b["low"] - px_in) for b in held)
        else:
            mfe = max((px_in - b["low"]) for b in held)
            mae = min((px_in - b["high"]) for b in held)
        trades.append({
            "ts_in": open_trade["ts_in"].isoformat(),
            "ts_out": fill_bar["ts"].isoformat(),
            "px_in": px_in,
            "px_out": px_out,
            "side": side,
            "volume": 1.0,
            "sl": None,
            "tp": None,
            "exit_reason": exit_reason,
            "exit_reason_source": "sentinel-sim",
            "pnl": pnl,
            "mae": mae,
            "mfe": mfe,
        })
        open_trade = None

    # Causal replay: decisions at bar i (using history bars[0..i]) fill at
    # bar i+1's open — never uses information not yet available.
    for i in range(n):
        if open_trade is not None:
            # SL-first conservative: this lean slice has no explicit SL
            # price target (V2/engulfing-only exit, plan M2.5 minimal
            # slice), so the only exit path is the policy's engulfing
            # signal, decided on the CLOSE of bar i and filled at i+1's
            # open (no look-ahead).
            if policy.should_exit(bars, i, open_trade["side"]) and i + 1 < n:
                _close(i + 1, "EXIT_ENGULF")
                continue

        if open_trade is None and i + 1 < n:
            signal = policy.signal_at(bars, i)
            if signal is not None:
                _open(i + 1, signal)

    net = sum(t["pnl"] for t in trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    wr = (100.0 * len(wins) / len(trades)) if trades else 0.0
    payoff = ((gross_win / len(wins)) / (gross_loss / len(losses))) if wins and losses else 0.0

    equity = 0.0
    peak = 0.0
    maxdd = 0.0
    for t in trades:
        equity += t["pnl"]
        peak = max(peak, equity)
        maxdd = max(maxdd, peak - equity)

    periodo_desde = bars[0]["ts"].isoformat() if bars else None
    periodo_hasta = bars[-1]["ts"].isoformat() if bars else None

    run = {
        "engine": "sentinel-sim",
        "fidelity": "research",
        "periodo_desde": periodo_desde,
        "periodo_hasta": periodo_hasta,
        "modelo_sim": "lite-v1",
        "status": "done",
        "trades": len(trades),
        "net": net,
        "pf": None if pf == float("inf") else pf,
        "wr": wr,
        "payoff": payoff,
        "maxdd": maxdd,
        "sharpe": None,
        "fecha_corrida": _utcnow_iso(),
    }
    return run, trades


def new_run_id() -> str:
    return f"sim-{uuid.uuid4().hex[:16]}"


def new_trade_id() -> str:
    return f"simtr-{uuid.uuid4().hex[:16]}"
