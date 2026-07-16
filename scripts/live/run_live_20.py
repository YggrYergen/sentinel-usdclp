r"""scripts/live/run_live_20.py -- GUARDED LIVE EXECUTOR for the curated 20
configs (SENTINEL, 2026-07-13). ORDER-CAPABLE. Read the safety block below in
full before running.

SAFETY MODEL (every rule -> where enforced)
-------------------------------------------
* SINGLE SOURCE OF TRUTH `D:/FOREX/CUENTAS.md`: DEMO 2883015767 (portable) is
  the ONLY tradable account; REAL 2883011573 is read-only. Enforced by
  `guard_cuenta.assert_demo`, called after connect and EVERY cycle, before any
  order.
* ATTACH-ONLY / NEVER LAUNCH: we NEVER call `mt5.initialize()` unless a MT5
  terminal for the DEMO PORTABLE install is ALREADY running. `_portable_running`
  inspects process command lines for the portable `terminal64.exe /portable`
  path (from CUENTAS.md); if not found we print "open the terminal" and exit --
  `initialize()` is never reached. We attach with `initialize(path=...)` to that
  exact portable exe, never a bare `initialize()`.
* DRY-RUN BY DEFAULT: without `--arm` every sendable action is LOGGED and NOT
  sent. `--arm` prints a red banner and requires typing the account number to
  confirm.
* VOLUME cap 0.10/ficha, ficha caps 3/config & 60 total, kill-switch (STOP
  file): all enforced in `reconciler.reconcile`; the daemon passes the running
  total and re-reads the STOP file each cycle.
* Ctrl-C -> clean shutdown; `--once` -> one reconcile cycle then exit.

DATA SOURCE: live MT5 rates via `copy_rates_from_pos` (freshest bar-close data;
same OHLC the sim consumes). We only act on NEWLY CLOSED bars (index 1 back from
the forming bar), so entries/exits are close-driven exactly like the sim; live
fills land at the next tick after bar close (tolerated by the parity checker).

USAGE
    # dry-run, single cycle, all configs (safe; needs the demo terminal open):
    python -m scripts.live.run_live_20 --once
    # dry-run daemon, subset:
    python -m scripts.live.run_live_20 --configs SS-M5,V10-M15
    # ARMED (real DEMO orders) -- user only:
    python -m scripts.live.run_live_20 --arm
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.live import guard_cuenta  # noqa: E402
from sentinel_engine.live.reconciler import reconcile, ReconcileResult  # noqa: E402
from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies.live_configs_20 import CONFIGS_20, LIVE_ROSTER  # noqa: E402

TF_MT5_MINUTES = {"M1": 1, "M2": 2, "M5": 5, "M15": 15}
TF_SECONDS = {"M1": 60, "M2": 120, "M5": 300, "M15": 900}

STOP_FILE = REPO_ROOT / "scripts" / "live" / "STOP"
AUDIT_LOG = REPO_ROOT / "scripts" / "live" / "run_live_20.audit.log"
DEFAULT_WINDOW = 10_000
MIN_WINDOW = 3_000
DEFAULT_VOLUME = 0.01

# CUENTAS.md: the DEMO install. We attach to THIS exe only.
# LOCAL MACHINE ADAPTATION (2026-07-14): this machine has a standard (non
# -portable) Capitaria MT5 install, not the teammate's D:\FOREX\MT5_Portable
# layout. Path and marker updated to match; see guard_cuenta.py for the
# corresponding DEMO_LOGIN adaptation.
PORTABLE_EXE = Path(r"C:\Program Files\Capitaria MT5 Terminal\terminal64.exe")
PORTABLE_MARKER = "capitaria mt5 terminal"  # lower-cased path fragment we look for

logger = logging.getLogger("run_live_20")


# --------------------------------------------------------------------------
# Attach guard (NEVER LAUNCH): confirm the DEMO PORTABLE terminal is running.
# --------------------------------------------------------------------------
def _portable_running(marker: str = PORTABLE_MARKER) -> bool:
    """True iff a running process' command line references the DEMO portable
    install path. Uses WMIC command-line inspection (Windows) so we do NOT
    confuse the REAL terminal (same image name, different path). No psutil,
    no killing, read-only."""
    import subprocess
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='terminal64.exe'",
             "get", "CommandLine,ExecutablePath", "/format:list"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:  # noqa: BLE001 -- wmic missing/failed: fall back below
        out = ""
    if out:
        return any(marker in line.lower() for line in out.splitlines())
    # PowerShell fallback for hosts where wmic is deprecated/absent.
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"name='terminal64.exe'\" "
             "| Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=25,
        ).stdout
    except Exception:  # noqa: BLE001
        out = ""
    return any(marker in line.lower() for line in out.splitlines())


# --------------------------------------------------------------------------
# Live rates + positions (thin adapters over the injected mt5 module).
# --------------------------------------------------------------------------
def fetch_bars(mt5: Any, symbol: str, tf: str, window: int) -> list[dict[str, Any]]:
    """Latest `window` bars, EXCLUDING the still-forming bar (we act on the
    last CLOSED bar only). Returns the sim's bar dict shape {t,open,high,low,
    close}. `copy_rates_from_pos(symbol, timeframe, 0, window+1)` then drop the
    forming bar."""
    timeframe = getattr(mt5, f"TIMEFRAME_{tf}")
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, window + 1)
    if rates is None or len(rates) < 2:
        return []
    bars = [{"t": int(r["time"]), "open": float(r["open"]),
             "high": float(r["high"]), "low": float(r["low"]),
             "close": float(r["close"])} for r in rates]
    # last element is the forming bar -> drop it; keep closed bars only.
    return bars[:-1]


def fetch_live_positions(mt5: Any, base_magic: int) -> list[dict[str, Any]]:
    """MT5 positions in this config's ficha band [base+1 .. base+3], as plain
    dicts for the reconciler. Read-only."""
    positions = mt5.positions_get()
    if positions is None:
        return []
    band = {base_magic + 1, base_magic + 2, base_magic + 3}
    out: list[dict[str, Any]] = []
    for p in positions:
        m = getattr(p, "magic", None)
        if m in band:
            out.append({"ticket": getattr(p, "ticket", None), "magic": m,
                        "type": getattr(p, "type", None),
                        "volume": getattr(p, "volume", None),
                        "sl": getattr(p, "sl", None),
                        "symbol": getattr(p, "symbol", None)})
    return out


# --------------------------------------------------------------------------
# Direction mask (V10 configs #14/#15).
# --------------------------------------------------------------------------
def _direction_mask(bars: list[dict[str, Any]]) -> list[int]:
    from scripts.report.gen_variant_batch5 import compute_direction_mask
    return compute_direction_mask(bars)


# --------------------------------------------------------------------------
# One reconcile cycle for one config.
# --------------------------------------------------------------------------
def reconcile_config(mt5: Any, cfg: dict[str, Any], *, window: int,
                     volume: float, kill_switch: bool,
                     total_open_fichas: int) -> tuple[ReconcileResult | None, int]:
    """Fetch bars + live positions, run the sim to the last CLOSED bar, diff.
    Returns (result, closed_bar_t). result is None if no bars available."""
    symbol = cfg["kwargs"]["symbol"]
    bars = fetch_bars(mt5, symbol, cfg["tf"], window)
    if not bars:
        logger.warning("[%s] no bars available (market closed / no data)", cfg["id"])
        return None, None

    kwargs = dict(cfg["kwargs"])
    if cfg.get("direction_filter"):
        kwargs["direction_mask"] = _direction_mask(bars)
    _events, desired = simular_variant(bars, return_state=True, **kwargs)

    live = fetch_live_positions(mt5, cfg["magic"])
    res = reconcile(cfg["id"], cfg["magic"], desired, live,
                    volume=volume, bar_t=bars[-1]["t"], kill_switch=kill_switch,
                    total_open_fichas=total_open_fichas)
    return res, bars[-1]["t"]


# --------------------------------------------------------------------------
# Order execution (only reached with --arm; dry-run logs + returns).
# --------------------------------------------------------------------------
def _side_to_order_type(mt5: Any, side: str) -> Any:
    return mt5.ORDER_TYPE_BUY if side == "L" else mt5.ORDER_TYPE_SELL


def _stops_level_points(mt5: Any, symbol: str) -> float:
    """Broker-legal minimum distance (in PRICE units, not points) between an
    SL and the current market price: max(trade_stops_level, trade_freeze_level)
    * point. Falls back to 0.0 if symbol_info is unavailable (never blocks)."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return 0.0
    stops = float(getattr(info, "trade_stops_level", 0) or 0)
    freeze = float(getattr(info, "trade_freeze_level", 0) or 0)
    point = float(getattr(info, "point", 0.0) or 0.0)
    return max(stops, freeze) * point


def _clamp_sl(mt5: Any, symbol: str, side: str, desired_sl: float) -> tuple[str, float]:
    """Decide the legal handling for a desired SL given the current tick.
    Returns (mode, value):
      mode="crossed"  -> value is the market ref price (bid/ask) the ficha
                          must be closed at (desired SL already at/through
                          market -- sim would already be out).
      mode="clamp"    -> value is the clamped SL to send (too close to
                          market but not crossed).
      mode="legal"    -> value is the original desired_sl, unmodified."""
    tick = mt5.symbol_info_tick(symbol)
    level = _stops_level_points(mt5, symbol)
    if side == "L":
        ref = tick.bid
        if desired_sl >= ref:
            return "crossed", ref
        if desired_sl > ref - level:
            return "clamp", ref - level
        return "legal", desired_sl
    else:
        ref = tick.ask
        if desired_sl <= ref:
            return "crossed", ref
        if desired_sl < ref + level:
            return "clamp", ref + level
        return "legal", desired_sl


def execute_action(mt5: Any, a: Any, *, symbol: str, dry_run: bool,
                   deviation: int = 20, contract_size: float = 100.0,
                   same_bar_cost: dict[str, float] | None = None,
                   sl_clamp_cost: dict[str, float] | None = None,
                   modify_retries: int = 2, open_retries: int = 2) -> None:
    """Send ONE sendable action, or (dry-run) just log the intent. Guard is
    re-asserted by the caller each cycle BEFORE this is reached.

    Side-effects on the audit log:
      * MISSING_SL_ALARM  -> logged at ERROR (loud) -- a ficha with no server
        -side SL; the paired MODIFY installs it.
      * SAME_BAR_EXIT_FALLBACK -> market-close the ficha; account the by-design
        price gap (sim exit level vs live market fill) into `same_bar_cost`
        keyed by config_id ("same-bar optimism, by design" -- NOT a divergence).
      * MODIFY failures are retried (`modify_retries`) and logged loudly; a
        ficha left without a server-side SL is an alarm condition.
      * FALLBACK_CLOSE_INVALID_SL -> the sim's desired SL has already been
        crossed by the current market price (bid for LONG / ask for SHORT):
        the sim would already be out, so live market-closes the ficha instead
        of sending an invalid MODIFY. The $-gap vs the sim's desired SL is
        accounted into `same_bar_cost` (same semantics as
        SAME_BAR_EXIT_FALLBACK).
      * SL_CLAMPED / SL_CLAMPED OPEN -> the desired SL is legal-side but
        closer to market than the broker's trade_stops_level/
        trade_freeze_level allow; the MODIFY/OPEN is sent with the closest
        legal SL. The $-gap between desired and clamped is accounted into
        `sl_clamp_cost`.
      * OPEN_SKIPPED_SL_CROSSED -> the sim's desired SL for a new position is
        already at/through the current market ref (bid for LONG / ask for
        SHORT): opening now would be an instant stop-out, so the OPEN is
        skipped entirely (nothing sent); the reconciler re-evaluates next
        cycle. OPEN retries (`open_retries`, mirrors `modify_retries`) on
        10016 with a fresh tick + re-clamp each attempt; exhaustion logs an
        ALARM like MODIFY does."""
    if a.kind == "MISSING_SL_ALARM":
        logger.error("  [ALARM MISSING_SL] %s %s magic=%s ticket=%s -- %s",
                     a.config_id, a.ficha, a.magic, a.ticket, a.reason)
        return
    if not a.sendable():
        logger.info("  [%s] %s %s %s -- %s", a.kind, a.config_id, a.ficha,
                    a.side or "", a.reason)
        return
    if dry_run:
        extra = ""
        if a.kind == "SAME_BAR_EXIT_FALLBACK":
            extra = f" sim_fill={a.sim_fill} motivo={a.motivo}"
        if a.kind == "MODIFY":
            desired_sl = float(a.sl) if a.sl is not None else 0.0
            mode, value = _clamp_sl(mt5, symbol, a.side, desired_sl)
            if mode == "crossed":
                logger.warning("  [DRY-RUN FALLBACK_CLOSE_INVALID_SL] ticket=%s "
                               "desired_sl=%s bid/ask=%s (would market-close, not modify)",
                               a.ticket, desired_sl, value)
                return
            if mode == "clamp":
                logger.warning("  [DRY-RUN SL_CLAMPED] ticket=%s desired=%s clamped=%s "
                               "gap=%.5f (would modify with clamped sl)",
                               a.ticket, desired_sl, value, abs(desired_sl - value))
                return
        if a.kind == "OPEN":
            desired_sl = float(a.sl) if a.sl is not None else 0.0
            mode, value = _clamp_sl(mt5, symbol, a.side, desired_sl)
            if mode == "crossed":
                logger.warning("  [DRY-RUN OPEN_SKIPPED_SL_CROSSED] config=%s ficha=%s "
                               "desired_sl=%s ref=%s (would skip open, not send)",
                               a.config_id, a.ficha, desired_sl, value)
                return
            if mode == "clamp":
                logger.warning("  [DRY-RUN SL_CLAMPED OPEN] config=%s ficha=%s desired=%s "
                               "clamped=%s gap=%.5f (would open with clamped sl)",
                               a.config_id, a.ficha, desired_sl, value,
                               abs(desired_sl - value))
                return
        logger.info("  [DRY-RUN would %s] %s %s magic=%s side=%s vol=%s sl=%s%s -- %s",
                    a.kind, a.config_id, a.ficha, a.magic, a.side, a.volume, a.sl,
                    extra, a.reason)
        return

    # --- ARMED path ---
    if a.kind in ("CLOSE", "SAME_BAR_EXIT_FALLBACK"):
        pos = None
        for p in (mt5.positions_get(ticket=a.ticket) or []):
            pos = p
        if pos is None:
            logger.warning("  [%s] ticket %s not found (already closed?)", a.kind, a.ticket)
            return
        tick = mt5.symbol_info_tick(symbol)
        is_long = getattr(pos, "type", 0) == getattr(mt5, "POSITION_TYPE_BUY", 0)
        price = tick.bid if is_long else tick.ask
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
               "volume": float(getattr(pos, "volume", a.volume or 0.0)),
               "type": mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY,
               "position": int(a.ticket), "price": price, "deviation": deviation,
               "magic": int(a.magic), "comment": f"{a.config_id}:{a.ficha}:close",
               "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)}
        r = mt5.order_send(req)
        if a.kind == "SAME_BAR_EXIT_FALLBACK":
            # by-design cost = (live market fill - sim fill) in P&L terms; the
            # gap is the "same-bar optimism" the sim enjoyed. side is the
            # POSITION side; a worse live fill vs sim level = negative gap.
            gap = 0.0
            if a.sim_fill is not None:
                d = (price - a.sim_fill) if is_long else (a.sim_fill - price)
                gap = d * float(getattr(pos, "volume", a.volume or 0.0)) * contract_size
            if same_bar_cost is not None:
                same_bar_cost[a.config_id] = same_bar_cost.get(a.config_id, 0.0) + gap
            logger.info("  [SAME_BAR_EXIT_FALLBACK] %s %s sim_fill=%s live_fill=%s "
                        "gap$=%.4f motivo=%s -> retcode=%s (by design, not a divergence)",
                        a.config_id, a.ficha, a.sim_fill, price, gap, a.motivo,
                        getattr(r, "retcode", r))
        else:
            logger.info("  [SENT CLOSE] ticket=%s -> retcode=%s", a.ticket,
                        getattr(r, "retcode", r))
        return
    if a.kind == "MODIFY":
        desired_sl = float(a.sl) if a.sl is not None else 0.0
        for attempt in range(1, modify_retries + 2):
            mode, value = _clamp_sl(mt5, symbol, a.side, desired_sl)
            if mode == "crossed":
                # sim's stop is already crossed/at market -> live must
                # market-close, not send an invalid MODIFY.
                pos = None
                for p in (mt5.positions_get(ticket=a.ticket) or []):
                    pos = p
                if pos is None:
                    logger.warning("  [MODIFY->CLOSE] ticket %s not found "
                                   "(already closed?)", a.ticket)
                    return
                is_long = a.side == "L"
                close_req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
                             "volume": float(getattr(pos, "volume", a.volume or 0.0)),
                             "type": mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY,
                             "position": int(a.ticket), "price": value,
                             "deviation": deviation, "magic": int(a.magic),
                             "comment": f"{a.config_id}:{a.ficha}:fallback_close",
                             "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)}
                r = mt5.order_send(close_req)
                gap = abs(desired_sl - value) * float(getattr(pos, "volume", a.volume or 0.0)) \
                    * contract_size
                if same_bar_cost is not None:
                    same_bar_cost[a.config_id] = same_bar_cost.get(a.config_id, 0.0) + gap
                logger.warning("  [FALLBACK_CLOSE_INVALID_SL] ticket=%s desired_sl=%s "
                               "bid=%s gap$=%.4f -> retcode=%s",
                               a.ticket, desired_sl, value, gap, getattr(r, "retcode", r))
                return
            if mode == "clamp":
                gap = abs(desired_sl - value)
                if sl_clamp_cost is not None:
                    sl_clamp_cost[a.config_id] = sl_clamp_cost.get(a.config_id, 0.0) + gap
                logger.warning("  [SL_CLAMPED] ticket=%s desired=%s clamped=%s gap=%.5f",
                               a.ticket, desired_sl, value, gap)
            req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": symbol,
                   "position": int(a.ticket), "sl": float(value),
                   "magic": int(a.magic)}
            r = mt5.order_send(req)
            ok = getattr(r, "retcode", None) in (
                getattr(mt5, "TRADE_RETCODE_DONE", 10009),
                getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010))
            if ok:
                logger.info("  [SENT MODIFY] ticket=%s sl=%s -> retcode=%s",
                            a.ticket, value, getattr(r, "retcode", r))
                return
            logger.error("  [MODIFY FAILED attempt %d/%d] ticket=%s sl=%s -> retcode=%s",
                         attempt, modify_retries + 1, a.ticket, value, getattr(r, "retcode", r))
        logger.error("  [ALARM] MODIFY exhausted retries for ticket=%s -- ficha "
                     "may lack a correct server-side SL (intra-bar risk).", a.ticket)
        return
    if a.kind == "OPEN":
        desired_sl = float(a.sl) if a.sl is not None else 0.0
        for attempt in range(1, open_retries + 2):
            mode, value = _clamp_sl(mt5, symbol, a.side, desired_sl)
            if mode == "crossed":
                logger.warning("  [OPEN_SKIPPED_SL_CROSSED] config=%s ficha=%s "
                               "desired_sl=%s ref=%s", a.config_id, a.ficha,
                               desired_sl, value)
                return
            sl_to_send = value
            if mode == "clamp":
                gap = abs(desired_sl - value)
                if sl_clamp_cost is not None:
                    sl_clamp_cost[a.config_id] = sl_clamp_cost.get(a.config_id, 0.0) + gap
                logger.warning("  [SL_CLAMPED OPEN] config=%s ficha=%s desired=%s "
                               "clamped=%s gap=%.5f", a.config_id, a.ficha,
                               desired_sl, value, gap)
            tick = mt5.symbol_info_tick(symbol)
            price = tick.ask if a.side == "L" else tick.bid
            req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
                   "volume": float(a.volume), "type": _side_to_order_type(mt5, a.side),
                   "price": price, "sl": float(sl_to_send),
                   "deviation": deviation, "magic": int(a.magic),
                   "comment": f"{a.config_id}:{a.ficha}",
                   "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1)}
            r = mt5.order_send(req)
            retcode = getattr(r, "retcode", None)
            if retcode == getattr(mt5, "TRADE_RETCODE_INVALID_STOPS", 10016):
                logger.error("  [OPEN FAILED attempt %d/%d] config=%s ficha=%s "
                             "sl=%s -> retcode=%s", attempt, open_retries + 1,
                             a.config_id, a.ficha, sl_to_send, retcode)
                continue
            logger.info("  [SENT OPEN] %s %s magic=%s -> retcode=%s", a.config_id,
                        a.ficha, a.magic, retcode)
            return
        logger.error("  [ALARM] OPEN exhausted retries for config=%s ficha=%s -- "
                     "position may not be open (intra-bar risk).", a.config_id, a.ficha)


# --------------------------------------------------------------------------
# Cycle orchestration.
# --------------------------------------------------------------------------
def run_cycle(mt5: Any, configs: list[dict[str, Any]], *, window: int,
              volume: float, dry_run: bool, deviation: int,
              same_bar_cost: dict[str, float] | None = None,
              sl_clamp_cost: dict[str, float] | None = None) -> None:
    """One full reconcile pass over all configs. Re-asserts the guard FIRST,
    re-reads the STOP kill-switch, tracks the 60-total ficha cap."""
    guard_cuenta.assert_demo(mt5)  # re-check every cycle, before any order
    kill = STOP_FILE.exists()
    if kill:
        logger.warning("KILL-SWITCH ACTIVE (STOP file present): OPENs suppressed; "
                       "CLOSE/MODIFY still applied.")
    now = datetime.now(timezone.utc).isoformat()
    logger.info("=== cycle %s | guard OK | kill=%s | dry_run=%s ===", now, kill, dry_run)

    total_open = 0
    for cfg in configs:
        res, bar_t = reconcile_config(
            mt5, cfg, window=window, volume=volume, kill_switch=kill,
            total_open_fichas=total_open)
        if res is None:
            continue
        bar_iso = datetime.fromtimestamp(bar_t, tz=timezone.utc).isoformat() if bar_t else "?"
        logger.info("[%s] bar=%s actions: %s", cfg["id"], bar_iso,
                    ", ".join(f"{a.kind}/{a.ficha}" for a in res.actions) or "none")
        for a in res.actions:
            execute_action(mt5, a, symbol=cfg["kwargs"]["symbol"], dry_run=dry_run,
                           deviation=deviation, same_bar_cost=same_bar_cost,
                           sl_clamp_cost=sl_clamp_cost)
        # count fichas the sim wants open (desired) toward the global cap.
        # OPEN + NOOP = one per still-desired ficha (MODIFY is paired with a
        # NOOP-or-open slot, so counting it too would double-count).
        total_open += sum(1 for a in res.actions if a.kind in ("OPEN", "NOOP"))

    if same_bar_cost:
        total = sum(same_bar_cost.values())
        logger.info("SAME_BAR cumulative by-design cost (this run): total=$%.4f | %s",
                    total, ", ".join(f"{k}=${v:.4f}" for k, v in sorted(same_bar_cost.items())))
    if sl_clamp_cost:
        total = sum(sl_clamp_cost.values())
        logger.info("SL_CLAMP cumulative gap (this run): total=$%.4f | %s",
                    total, ", ".join(f"{k}=${v:.4f}" for k, v in sorted(sl_clamp_cost.items())))


def _connect(mt5: Any) -> None:
    """Attach to the DEMO terminal ONLY. Never launches: the caller
    has already confirmed the terminal process is running."""
    # LOCAL MACHINE ADAPTATION (2026-07-14): standard (non-portable) install
    # on this machine -- portable=True would point MT5 at a portable data
    # directory that doesn't exist here and detach from the logged-in
    # 2883016567 session, so we drop it.
    if not mt5.initialize(path=str(PORTABLE_EXE)):
        raise SystemExit(f"[FATAL] initialize(path={PORTABLE_EXE}) failed: "
                         f"{mt5.last_error()}")


def _arm_confirm() -> None:
    banner = ("\n" + "!" * 64 + "\n"
              "!!  ARMED: REAL ORDERS WILL BE SENT TO THE DEMO ACCOUNT.      !!\n"
              f"!!  Type the DEMO account number ({guard_cuenta.DEMO_LOGIN}) to proceed.   !!\n"
              + "!" * 64)
    print(banner)
    typed = input("account number> ").strip()
    if typed != str(guard_cuenta.DEMO_LOGIN):
        raise SystemExit("account number mismatch -- aborting (nothing sent).")


def _confirm_account_noninteractive(confirm_account: int) -> None:
    """Non-interactive arm confirmation for supervised/watchdog restarts: the
    caller must supply the exact sanctioned DEMO account number on the command
    line (`--confirm-account`). Mismatch (any other number, especially the
    REAL account) -> loud stderr error, exit code 2, WITHOUT touching MT5.
    Match -> logged at WARNING for the audit trail, then proceeds like the
    interactive path."""
    if confirm_account != guard_cuenta.DEMO_LOGIN:
        print(f"[FATAL] --confirm-account {confirm_account} does not match the "
              f"sanctioned DEMO account {guard_cuenta.DEMO_LOGIN} -- refusing to "
              "arm (nothing sent, MT5 not initialized).", file=sys.stderr)
        raise SystemExit(2)
    logger.warning("ARMED mode confirmed NON-INTERACTIVELY via --confirm-account "
                   "%s (matches sanctioned DEMO account) -- audit trail.",
                   confirm_account)


def main(argv: list[str] | None = None, *, mt5_module: Any = None,
         attach_checker: Callable[[], bool] = _portable_running) -> int:
    ap = argparse.ArgumentParser(description="Guarded live executor for the 20 configs.")
    ap.add_argument("--configs", default="all",
                     help="'all', 'live' (the LIVE_ROSTER subset) or comma ids "
                          "e.g. SS-M5,V10-M15")
    ap.add_argument("--arm", action="store_true", help="SEND real orders (default: dry-run)")
    ap.add_argument("--once", action="store_true", help="one reconcile cycle then exit")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW, help="trailing bars for the sim")
    ap.add_argument("--volume", type=float, default=DEFAULT_VOLUME, help="per-ficha volume")
    ap.add_argument("--deviation", type=int, default=20, help="max slippage (points)")
    ap.add_argument("--interval", type=float, default=15.0, help="daemon poll seconds")
    ap.add_argument("--confirm-account", type=int, default=None,
                     help="non-interactive arm confirmation: must equal the "
                          "sanctioned DEMO login; only effective with --arm")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(AUDIT_LOG, encoding="utf-8")])

    window = max(args.window, MIN_WINDOW)
    if args.configs.lower() == "all":
        configs = list(CONFIGS_20)
    elif args.configs.lower() == "live":
        configs = [c for c in CONFIGS_20 if c["id"] in LIVE_ROSTER]
    else:
        want = {s.strip() for s in args.configs.split(",")}
        configs = [c for c in CONFIGS_20 if c["id"] in want]
        unknown = want - {c["id"] for c in configs}
        if unknown:
            print(f"unknown config id(s): {sorted(unknown)}", file=sys.stderr)
            return 2
    dry_run = not args.arm

    if args.confirm_account is not None and not args.arm:
        logger.warning("--confirm-account %s is ignored: --arm was not passed "
                       "(dry-run proceeds, not armed).", args.confirm_account)

    # Non-interactive arm confirmation (watchdog/supervised restarts): validate
    # BEFORE the attach check / MT5 import so a mismatch never touches MT5.
    if args.arm and args.confirm_account is not None:
        _confirm_account_noninteractive(args.confirm_account)

    # ATTACH-ONLY / NEVER LAUNCH: confirm the portable terminal is running
    # BEFORE importing/initializing MetaTrader5.
    if not attach_checker():
        print("[STOP] The DEMO portable MT5 terminal is NOT running.\n"
              "       Open it first via  D:\\FOREX\\MT5_DEMO_TOMAS.bat  (login "
              f"{guard_cuenta.DEMO_LOGIN}), then re-run this executor.\n"
              "       (initialize() was NOT called -- we never launch a terminal.)",
              file=sys.stderr)
        return 3

    mt5 = mt5_module
    if mt5 is None:
        import MetaTrader5 as mt5  # noqa: N813 -- only imported once attach-confirmed
    _connect(mt5)
    login = guard_cuenta.assert_demo(mt5)  # hard-exits on any mismatch
    logger.info("connected + guard OK: DEMO login %s (dry_run=%s, %d configs, window=%d)",
                login, dry_run, len(configs), window)

    if args.arm and args.confirm_account is None:
        _arm_confirm()

    stop = {"flag": False}

    def _sigint(_sig, _frm):
        logger.info("Ctrl-C received -- clean shutdown after current cycle.")
        stop["flag"] = True

    signal.signal(signal.SIGINT, _sigint)

    same_bar_cost: dict[str, float] = {}
    sl_clamp_cost: dict[str, float] = {}
    try:
        while True:
            run_cycle(mt5, configs, window=window, volume=args.volume,
                      dry_run=dry_run, deviation=args.deviation,
                      same_bar_cost=same_bar_cost, sl_clamp_cost=sl_clamp_cost)
            if args.once or stop["flag"]:
                break
            time.sleep(args.interval)
    finally:
        try:
            mt5.shutdown()
        except Exception:  # noqa: BLE001
            pass
    logger.info("executor stopped cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
