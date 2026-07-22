r"""scripts/live/run_live_20.py -- GUARDED LIVE EXECUTOR for the curated 20
configs (SENTINEL, 2026-07-13). ORDER-CAPABLE. Read the safety block below in
full before running.

SAFETY MODEL (every rule -> where enforced)
-------------------------------------------
* SINGLE SOURCE OF TRUTH `D:/FOREX/CUENTAS.md`: one sanctioned DEMO login per
  machine (2883015767 portable on Machine 1, 2883016567 standard install on
  Machine "TOMACHINE" -- both in `guard_cuenta.SANCTIONED_DEMO_LOGINS`,
  selected per-machine by `sentinel_engine.live.machine_profile`) is the ONLY
  tradable account; REAL 2883011573 is read-only on every machine. Enforced
  by `guard_cuenta.assert_demo`, called after connect and EVERY cycle, before
  any order.
* ATTACH-ONLY / NEVER LAUNCH: we NEVER call `mt5.initialize()` unless a MT5
  terminal for THIS machine's configured install (`machine_profile.load_profile()`)
  is ALREADY running. `_portable_running` inspects process command lines for
  the configured `terminal64.exe` path/marker; if not found we print "open
  the terminal" and exit -- `initialize()` is never reached. We attach with
  `initialize(path=...)` to that exact exe, never a bare `initialize()`.
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
from sentinel_engine.live.machine_profile import load_profile  # noqa: E402
from sentinel_engine.live.magic_seed import ensure_magic_allocations  # noqa: E402
from sentinel_engine.live.reconciler import reconcile, ReconcileResult  # noqa: E402
from sentinel_engine.live.spread_store import SpreadStore  # noqa: E402
from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies.live_configs_20 import (  # noqa: E402
    CONFIGS_20, CONFIGS_GOLIVE, CONFIGS_GOLIVE_DEDUP, CONFIGS_LIVE,
    CONFIGS_SHADOW, CONFIGS_TK, CONFIGS_TOMACHINE, LIVE_ROSTER,
    supertrend_always_in_target)
from sentinel_engine.strategies.tk_bw2_live import (  # noqa: E402
    tk_bw2_fix2atr_target)
from sentinel_engine.strategies.tk_momentum import (  # noqa: E402
    tk_momentum_5_8_target)

TF_MT5_MINUTES = {"M1": 1, "M2": 2, "M5": 5, "M6": 6, "M10": 10, "M15": 15}
TF_SECONDS = {"M1": 60, "M2": 120, "M5": 300, "M6": 360, "M10": 600, "M15": 900}

STOP_FILE = REPO_ROOT / "scripts" / "live" / "STOP"
AUDIT_LOG = REPO_ROOT / "scripts" / "live" / "run_live_20.audit.log"
_MAGIC_ALLOCATION_DB_PATH = REPO_ROOT / "data" / "research.db"
DEFAULT_WINDOW = 10_000
MIN_WINDOW = 3_000
DEFAULT_VOLUME = 0.01

# TK-BW2-fix2atr LOCAL BAR CAP (2026-07-22) -----------------------------------
# `tk_bw2_fix2atr_target` replays bars through the REAL `tk_bw_v2_run` engine,
# whose `_Regime.__init__` recomputes every indicator series over the ENTIRE
# `closed` bar list on EVERY step -- O(n) work per step, O(n^2) total in bar
# count. Measured: 500 bars -> 1.6s, 2000 bars -> 17.7s replay time. Feeding
# it the full `--window` (default 10_000) would take minutes and hang the
# ~15s live poll cycle. We do NOT touch the shared engine (parity-gated,
# also used by the O(n^2)-tolerant batch backtest runner) -- instead we cap
# the bar TAIL fed to this one executor dispatch branch only.
#
# CORRECTNESS: capping to a tail window restarts the state machine from FLAT
# at the window start, so it would miss a position opened BEFORE the window
# that is still open. This is safe for TK-BW2-fix2atr specifically because
# its positions exit via ATR-frozen stops/BE/trail within hours -- never
# held for days. 750 M5 bars =~ 2.6 trading days of history: ample warmup
# plus full coverage of any realistically-open TK-BW2 position. Expected
# replay time at this size is ~3-4s, comfortably inside the 15s poll even on
# the slower machine-2.
TK_BW2_LIVE_BAR_CAP = 750

# HARD SPREAD-GATE (GL-T1, OPEN-only) -----------------------------------------
# An OPEN is SENT only when the current tick spread (ask-bid, PRICE units) is
# <= this threshold; otherwise it is SKIPPED (logged SPREAD_GATE_SKIP; the
# reconciler re-evaluates it next cycle). Exits, MODIFY and CLOSE are NEVER
# gated -- we never abandon risk management or a desired exit over spread.
#
# CALIBRATION (XAUUSD, Capitaria DEMO):
#   The tick_logger XAUUSD spread parquet was never captured on this repo
#   (`sentinel.config.LOG_TICKS` defaults False; `logs/` is gitignored; the
#   W8-T1 cycle-spread telemetry capture is queued, not yet run). The only
#   captured executor-level XAUUSD spread reading is the `spread_snapshot_now`
#   in `scripts/report/diag_h3h5_spread.json` (DEMO 2883015767, 2026-07-14):
#       symbol_info.spread = 60 points x point 0.01 = 0.60 USD/oz,
#       symbol_info_tick.ask - bid = 0.60, spread_float = False (FIXED spread).
#   A FIXED spread means the observed distribution is a point mass at 0.60 for
#   that regime (no p05/min variation to fit yet). Per the spec's fallback
#   rule ("if the captured data is insufficient, pick a conservative default
#   and say so"), the default is the observed session spread 0.60 + a 0.10
#   USD/oz margin = 0.70. This:
#     * ADMITS the observed thin/fixed 0.60 regime (0.60 <= 0.70), so the gate
#       does not starve the roster of entries under normal conditions, while
#     * HARD-SKIPPING any genuine widening above 0.70 (the overnight/illiquid
#       regimes the spread-minimum theory D115 flags as loss-making).
#   0.70 == "session-min + 0.10", matching the W8-T3 gate grid intent
#   {min, min+0.05, min+0.10}. RE-CALIBRATE once W8-T1 telemetry lands a real
#   per-cycle spread series.
DEFAULT_MAX_SPREAD_OPEN = 0.70

# ADAPTIVE RUNNING-MIN SPREAD-GATE (GL-T2) ------------------------------------
# Instead of the STATIC 0.70 above, the go-live roster LEARNS the thin-market
# floor online via `sentinel_engine.live.spread_store`: every cycle we record
# the current spread, ratchet an all-time running MINIMUM down, and admit an
# OPEN only when `current_spread <= running_min + eps`. This adapts to whatever
# regime the account actually shows (fixed 0.60 today; a real distribution once
# the broker turns on float spreads) with NO re-calibration.
#
# `--spread-eps` DEFAULT = 1e-6 USD/oz -- a TINY float-equality tolerance ONLY,
# NOT a margin band. Justification:
#   * The gate must admit entries ONLY at the observed MINIMUM spread. With the
#     fixed-0.60 regime running_min ratchets to 0.60 and threshold = 0.60 + 1e-6
#     ~= 0.60, so: spread 0.60 => OPERATE, spread 0.61 (and 0.70) => PAUSE. This
#     is deliberately STRICTER than GL-T1's static 0.70 (= min+0.10), which
#     wrongly admitted 0.61..0.70. We NEVER open above the running-min.
#   * 1e-6 is 1/10000 of a single 0.01 XAU tick -- it exists purely to absorb
#     float ask-bid rounding (e.g. ask-bid = 0.6000000000000455) so a spread
#     that IS the min is not spuriously skipped. It can never admit a spread one
#     real tick (0.01) above the floor.
# RATCHET-STARVATION (honest caveat): the running-min only ever goes DOWN. If
# the account ever prints an unusually thin spread (e.g. a 0.30 blip), the floor
# latches to 0.30 and the gate thereafter PAUSES the whole roster whenever
# spread sits at the normal 0.60 (0.60 > 0.30 + 1e-6). With eps this tight the
# gate is intentionally UNFORGIVING: it opens only at exactly the thinnest
# spread ever seen. Mitigations: (a) with today's FIXED 0.60 spread no thinner
# value can ever be printed, so the floor stays 0.60 and this cannot bite yet;
# (b) `--spread-eps` can be widened deliberately if the operator wants a band;
# (c) `--max-spread-open` remains an independent HARD cap; (d) a future task can
# add a decaying/percentile floor. Flagged, not silently ignored.
DEFAULT_SPREAD_EPS = 1e-6

# CUENTAS.md: the DEMO install. We attach to THIS exe only.
# MULTI-MACHINE (2026-07-15): terminal path/marker/portable-flag now come
# from the machine profile (sentinel_engine.live.machine_profile) so this
# same tracked file serves both Machine 1 (portable D:\FOREX\MT5_Portable)
# and Machine "TOMACHINE" (standard Capitaria install) without either
# machine's hardcode clobbering the other's on merge. See machine_profile.py
# and guard_cuenta.py (SANCTIONED_DEMO_LOGINS) for the rest of the picture.
_PROFILE = load_profile()
PORTABLE_EXE = _PROFILE.terminal_path
PORTABLE_MARKER = _PROFILE.terminal_marker  # lower-cased path fragment we look for
PORTABLE_FLAG = _PROFILE.portable

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
def fetch_bars(mt5: Any, symbol: str, tf: str, window: int,
               *, include_forming: bool = False) -> list[dict[str, Any]]:
    """Latest `window` bars in the sim's bar dict shape {t,open,high,low,close}.
    `copy_rates_from_pos(symbol, timeframe, 0, window+1)`.

    By default EXCLUDES the still-forming bar (close-driven engines act on the
    last CLOSED bar only). With `include_forming=True` the still-forming bar is
    KEPT as the last element (its OHLC reflect the elapsed part of the bar, its
    close = the current price) -- this is what the INTRABAR TK-Momentum path
    uses to evaluate the signal live, without waiting for the bar to close."""
    timeframe = getattr(mt5, f"TIMEFRAME_{tf}")
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, window + 1)
    if rates is None or len(rates) < 2:
        return []
    bars = [{"t": int(r["time"]), "open": float(r["open"]),
             "high": float(r["high"]), "low": float(r["low"]),
             "close": float(r["close"])} for r in rates]
    # last element is the forming bar: keep it only for the intrabar path.
    return bars if include_forming else bars[:-1]


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
    # INTRABAR (TK-Momentum, 2026-07-21 trader request): evaluate the signal on
    # the still-forming bar (current price) instead of waiting for the bar to
    # close, so a position is taken the moment the conditions are met live.
    intrabar = (cfg.get("engine") == "tk_momentum"
                and cfg["kwargs"].get("intrabar", False))
    bars = fetch_bars(mt5, symbol, cfg["tf"], window, include_forming=intrabar)
    if not bars:
        logger.warning("[%s] no bars available (market closed / no data)", cfg["id"])
        return None, None

    # ENGINE FLAVORS (GL-T3): the six ladder configs run simular_variant; the
    # 7th go-live strategy (SuperTrend-p14x3-M15) is ALWAYS-IN -- a single
    # flipping position whose desired target is built by
    # `supertrend_always_in_target`, NOT simular_variant. Both produce the
    # SAME `return_state` snapshot shape, so the reconciler below is identical
    # for either (single position vs 3-ficha ladder), and the OPEN spread-gate
    # applies to the SuperTrend entry exactly like any other.
    if cfg.get("engine") == "supertrend_always_in":
        desired = supertrend_always_in_target(bars)
    elif cfg.get("engine") == "tk_momentum":
        # TK-Momentum-5-8-short (2026-07-21): single-position SMA/MOM engine,
        # same return_state snapshot shape -> same reconciler path.
        desired = tk_momentum_5_8_target(
            bars, trail_usd=cfg["kwargs"].get("trail_usd", 0.5))
        # SINGLE-POSITION INVARIANT (trader 2026-07-21 "solo una posicion,
        # nunca mas de una"): the engine is single-slot by construction, but
        # guard it here too so a future engine change can NEVER open a 2nd
        # TK ficha in live. Fail closed rather than send extra orders.
        assert len(desired.get("open", {})) <= 1, (
            "TK-Momentum must never desire more than one open position "
            f"(got {list(desired.get('open', {}))})")
    elif cfg.get("engine") == "tk_bw2_fix2atr":
        # TK-BW2-fix2atr (2026-07-22): CLOSED-bars-only replay of the real
        # tk_bw_v2 engine (NOT intrabar -- `bars` above already excludes the
        # still-forming bar, since `intrabar` is False for this engine and
        # `include_forming` defaults False). Up to 3 fichas (F1/F2/F3), same
        # return_state snapshot shape -> same ladder reconciler as
        # simular_variant, no reconciler change.
        # Cap the replay tail LOCALLY (see TK_BW2_LIVE_BAR_CAP above) -- do
        # NOT change `window`/the MT5 fetch size, other tomachine configs
        # may still want the full window.
        engine_kwargs = {k: v for k, v in cfg["kwargs"].items() if k != "symbol"}
        desired = tk_bw2_fix2atr_target(
            bars[-TK_BW2_LIVE_BAR_CAP:], **engine_kwargs)
    else:
        kwargs = dict(cfg["kwargs"])
        if cfg.get("direction_filter"):
            kwargs["direction_mask"] = _direction_mask(bars)
        _events, desired = simular_variant(bars, return_state=True, **kwargs)

    live = fetch_live_positions(mt5, cfg["magic"])
    res = reconcile(cfg["id"], cfg["magic"], desired, live,
                    volume=volume, bar_t=bars[-1]["t"], kill_switch=kill_switch,
                    total_open_fichas=total_open_fichas)
    # SINGLE-POSITION EXECUTION GUARD (tk_momentum, trader 2026-07-21 "solo una
    # posicion"): NEVER send an OPEN while any live position already exists on
    # this magic. On a side-flip the reconciler emits CLOSE+OPEN in the same
    # cycle (it optimistically assumes the close lands); if that close
    # transiently fails the reopen would DOUBLE the book. Here we only allow an
    # OPEN from a genuinely FLAT book (len(live)==0) -- so a flip becomes
    # "close this cycle, open once the book is confirmed flat next cycle", and
    # the live count can never exceed 1 even if a close fails. Defense-in-depth
    # complementing the CLOSE retry in execute_action.
    if cfg.get("engine") == "tk_momentum" and res is not None and len(live) >= 1:
        dropped = [a for a in res.actions if a.kind == "OPEN"]
        if dropped:
            res.actions = [a for a in res.actions if a.kind != "OPEN"]
            logger.info("[%s] single-position guard: suppressed %d OPEN(s) while "
                        "%d live position(s) still on the book (open only when flat)",
                        cfg["id"], len(dropped), len(live))
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


def _current_spread(mt5: Any, symbol: str) -> float | None:
    """Current tick spread (ask - bid) in PRICE units, or None if the tick is
    unavailable (in which case the caller must NOT gate -- fail open on exits,
    fail closed only where explicitly decided). Read-only."""
    try:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        bid = getattr(tick, "bid", None)
        ask = getattr(tick, "ask", None)
        if bid is None or ask is None:
            return None
        return float(ask) - float(bid)
    except Exception:  # noqa: BLE001 - a tick read must never abort a fill/gate
        return None


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
                   modify_retries: int = 2, open_retries: int = 2,
                   close_retries: int = 2,
                   max_spread_open: float | None = None,
                   spread_threshold: float | None = None,
                   on_fill: Callable[[str, Any, float | None], None] | None = None) -> None:
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
      * SPREAD_GATE_SKIP -> (OPEN only) the current tick spread (ask-bid)
        exceeds `max_spread_open`; the OPEN is SKIPPED entirely (nothing sent)
        and the reconciler re-evaluates it next cycle. Exits / MODIFY / CLOSE
        are never gated. A None `max_spread_open` disables the gate.
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

    def _emit_fill(kind: str, position_id: Any, spread: float | None) -> None:
        """Best-effort spread recording (2026-07-21): persist the spread at
        fill so the UI/audit can show it. NEVER lets a recording error break
        or alter the order flow -- fail-safe, logged loudly on failure."""
        if on_fill is None:
            return
        try:
            on_fill(kind, position_id, spread)
        except Exception as exc:  # noqa: BLE001 - recording must never abort trading
            logger.error("  [SPREAD_RECORD_FAILED] kind=%s position_id=%s -> %s",
                         kind, position_id, exc)

    # SPREAD-GATE (OPEN only): skip a NEW entry when the current tick spread
    # exceeds the effective cap; the reconciler re-evaluates next cycle. Two
    # independent limits combine (the TIGHTER binds):
    #   * `spread_threshold` -- the ADAPTIVE running-min gate (running_min+eps,
    #     from spread_store); the DEFAULT gate for the go-live roster.
    #   * `max_spread_open`  -- an optional STATIC HARD cap (GL-T1 override).
    # Effective cap = min of whichever are set. Exits, MODIFY and CLOSE are
    # NEVER gated (they must always be free to run risk management), so this is
    # scoped strictly to a.kind == "OPEN" and runs in BOTH dry-run and armed
    # paths. A missing/None tick spread does NOT gate (fail-open: we only ever
    # SKIP on an affirmatively-too-wide read).
    if a.kind == "OPEN":
        caps = [c for c in (max_spread_open, spread_threshold) if c is not None]
        eff_cap = min(caps) if caps else None
        if eff_cap is not None:
            spread = _current_spread(mt5, symbol)
            # tiny epsilon so a spread that equals the cap (subject to float
            # ask-bid rounding, e.g. ask-bid = 0.6000000000000455 on ~4000 XAU
            # prices) is treated as AT-cap => admitted, not skipped. The gate is
            # `spread <= eff_cap`. 1e-6 USD/oz is 1/10000 of a 0.01 tick, far
            # below any real spread, so it never admits a genuinely wider one.
            _SPREAD_FLOAT_EPS = 1e-6
            if spread is not None and spread > eff_cap + _SPREAD_FLOAT_EPS:
                which = ("adaptive" if spread_threshold is not None
                         and eff_cap == spread_threshold else "hard")
                logger.warning("  [SPREAD_GATE_SKIP] config=%s ficha=%s spread=%.5f "
                               "> cap=%.5f (%s; running_min_thr=%s hard_max=%s; open "
                               "deferred, reconciler re-evaluates next cycle)",
                               a.config_id, a.ficha, spread, eff_cap, which,
                               spread_threshold, max_spread_open)
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
        # CLOSE is NOT fire-and-forget (2026-07-21 incident): mt5.order_send can
        # transiently return None (e.g. "trade context busy" when a close fires
        # right after another config's order in the same cycle). A dropped close
        # leaves the position open while the reconciler optimistically reopens
        # -> unbounded accumulation. Retry on None/non-DONE, log last_error
        # (previously a blind spot), refresh the price, then verify removal.
        done_rc = getattr(mt5, "TRADE_RETCODE_DONE", 10009)
        r = None
        for attempt in range(1, close_retries + 2):
            r = mt5.order_send(req)
            if r is not None and getattr(r, "retcode", None) == done_rc:
                break
            logger.error("  [CLOSE FAILED attempt %d/%d] ticket=%s -> retcode=%s "
                         "last_error=%s", attempt, close_retries + 1, a.ticket,
                         getattr(r, "retcode", r), mt5.last_error())
            rtick = mt5.symbol_info_tick(symbol)
            if rtick is not None:
                price = rtick.bid if is_long else rtick.ask
                req["price"] = price
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
        # Record the spread at close (best-effort). Keyed by the position
        # ticket, which is `deals_raw.position_id` for this position.
        if r is not None and getattr(r, "retcode", None) == done_rc:
            _emit_fill("CLOSE", a.ticket, _current_spread(mt5, symbol))
        # Verify removal: a position still on the book after all retries is an
        # ALARM (the single-position guard in reconcile_config will keep the
        # book from growing, but this surfaces the failed close loudly).
        if mt5.positions_get(ticket=a.ticket):
            logger.error("  [ALARM] CLOSE did not remove ticket=%s after %d attempts "
                         "-- still open (accumulation risk).", a.ticket, close_retries + 1)
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
            # Record the spread at open (best-effort). The opening order ticket
            # (`r.order`) is the MT5 position identifier == `deals_raw.position_id`.
            _emit_fill("OPEN", getattr(r, "order", None), _current_spread(mt5, symbol))
            return
        logger.error("  [ALARM] OPEN exhausted retries for config=%s ficha=%s -- "
                     "position may not be open (intra-bar risk).", a.config_id, a.ficha)


# --------------------------------------------------------------------------
# Cycle orchestration.
# --------------------------------------------------------------------------
def run_cycle(mt5: Any, configs: list[dict[str, Any]], *, window: int,
              volume: float, dry_run: bool, deviation: int,
              same_bar_cost: dict[str, float] | None = None,
              sl_clamp_cost: dict[str, float] | None = None,
              max_spread_open: float | None = None,
              spread_store: SpreadStore | None = None,
              spread_eps: float = DEFAULT_SPREAD_EPS,
              on_fill: Callable[[str, Any, float | None], None] | None = None) -> None:
    """One full reconcile pass over all configs. Re-asserts the guard FIRST,
    re-reads the STOP kill-switch, tracks the 60-total ficha cap.

    If a `spread_store` is given, BEFORE the OPEN decisions we record the
    current spread (per distinct symbol) so the all-time running-min ratchets,
    then gate OPENs with the ADAPTIVE threshold `running_min + spread_eps`
    (combined with the optional static `max_spread_open` hard cap -- tighter
    binds)."""
    guard_cuenta.assert_demo(mt5)  # re-check every cycle, before any order
    kill = STOP_FILE.exists()
    if kill:
        logger.warning("KILL-SWITCH ACTIVE (STOP file present): OPENs suppressed; "
                       "CLOSE/MODIFY still applied.")
    now = datetime.now(timezone.utc).isoformat()
    logger.info("=== cycle %s | guard OK | kill=%s | dry_run=%s ===", now, kill, dry_run)

    # ADAPTIVE SPREAD-GATE (GL-T2): record current spread(s) BEFORE any OPEN
    # decision so the running-min ratchets this cycle, then derive the per-symbol
    # threshold used to gate OPENs. Read-only: recording never sends an order.
    spread_threshold_by_symbol: dict[str, float | None] = {}
    if spread_store is not None:
        seen_symbols = {cfg["kwargs"]["symbol"] for cfg in configs}
        for sym in seen_symbols:
            sp = _current_spread(mt5, sym)
            if sp is not None:
                spread_store.record(sp, now)
            thr = spread_store.threshold(spread_eps)
            spread_threshold_by_symbol[sym] = thr
            logger.info("[spread] %s current=%s running_min=%s threshold(eps=%.4f)=%s",
                        sym, f"{sp:.5f}" if sp is not None else "None",
                        f"{spread_store.running_min:.5f}"
                        if spread_store.running_min is not None else "None",
                        spread_eps, f"{thr:.5f}" if thr is not None else "None")

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
        sym = cfg["kwargs"]["symbol"]
        for a in res.actions:
            execute_action(mt5, a, symbol=sym, dry_run=dry_run,
                           deviation=deviation, same_bar_cost=same_bar_cost,
                           sl_clamp_cost=sl_clamp_cost,
                           max_spread_open=max_spread_open,
                           spread_threshold=spread_threshold_by_symbol.get(sym),
                           on_fill=on_fill)
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
    # MULTI-MACHINE (2026-07-15): whether to pass portable=True depends on
    # the machine profile -- Machine 1's portable install needs it; Machine
    # "TOMACHINE"'s standard install must NOT pass it (portable=True there
    # would point MT5 at a nonexistent portable data dir and detach from the
    # logged-in session). We only pass the kwarg at all when the profile
    # says portable=True, matching the original non-portable call exactly.
    ok = (mt5.initialize(path=str(PORTABLE_EXE), portable=True) if PORTABLE_FLAG
          else mt5.initialize(path=str(PORTABLE_EXE)))
    if not ok:
        raise SystemExit(f"[FATAL] initialize(path={PORTABLE_EXE}) failed: "
                         f"{mt5.last_error()}")


def capture_spread_loop(mt5: Any, *, symbol: str, interval: float,
                        spread_store: SpreadStore,
                        stop_flag: dict[str, bool], once: bool = False) -> int:
    """STANDALONE always-on READ-ONLY spread capturer. Attaches (already done by
    the caller), asserts DEMO once, then loops: read `symbol_info_tick`, record
    the spread into `spread_store` (ratcheting the running-min), sleep. Sends NO
    orders EVER. The all-time running-min this learns is what the executor later
    picks up (persisted, atomic writes) for the adaptive gate.

    NOTE: do NOT run this AND an armed executor writing the same store file at
    the same instant (last-writer-wins race on the JSON). Run one at a time."""
    guard_cuenta.assert_demo(mt5)  # sanctioned DEMO only, once up front
    logger.info("[capture] read-only spread capture started: symbol=%s interval=%ss "
                "store=%s (NO orders will ever be sent)", symbol, interval,
                spread_store.store_path)
    while True:
        sp = _current_spread(mt5, symbol)
        now = datetime.now(timezone.utc).isoformat()
        if sp is not None:
            rm = spread_store.record(sp, now)
            logger.info("[capture] %s spread=%.5f running_min=%.5f samples=%d",
                        symbol, sp, rm if rm is not None else float("nan"),
                        spread_store.sample_count)
        else:
            logger.warning("[capture] %s tick unavailable (market closed?) -- skipped",
                           symbol)
        if once or stop_flag.get("flag"):
            break
        time.sleep(interval)
    logger.info("[capture] stopped cleanly (samples=%d, running_min=%s).",
                spread_store.sample_count, spread_store.running_min)
    return 0


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
         attach_checker: Callable[[], bool] = _portable_running,
         registry: Any = None,
         spread_recorder: Callable[[str, Any, float | None], None] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Guarded live executor for the 20 configs.")
    ap.add_argument("--configs", default="all",
                     help="'all', 'live' (the LIVE_ROSTER subset), 'shadow' "
                          "(the FIXED4 corrected roster only -- what machine-2 "
                          "runs), 'golive' (the GO-LIVE roster: M15 V-15 SAR "
                          "top-5 + V11-M2 + SuperTrend-p14x3-M15 always-in, "
                          "magics 7240x0), 'golive-dedup' (D121: the 5 SAR "
                          "clones collapsed to 2 best reps S6-K2P0+S7-TPNONE, "
                          "plus V11-M2 + SuperTrend; clone-concentration "
                          "removed), 'live+shadow' "
                          "(both, 8 configs), 'tk-momentum' (the trader's "
                          "isolated TK-Momentum-5-8-short live-forward test on "
                          "XAUUSD, magic 999999999), 'tomachine' (machine-2 "
                          "roster, trader selection 2026-07-22: FIXED4 shadow "
                          "+ S6-K2P0 + S7-TPNONE + SuperTrend-p14x3-M15 + "
                          "TK-BW2-fix2atr, 8 configs, NO V11-M2/TK-Momentum) "
                          "or comma ids e.g. SS-M5,V10-M15")
    ap.add_argument("--arm", action="store_true", help="SEND real orders (default: dry-run)")
    ap.add_argument("--once", action="store_true", help="one reconcile cycle then exit")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW, help="trailing bars for the sim")
    ap.add_argument("--volume", type=float, default=DEFAULT_VOLUME, help="per-ficha volume")
    ap.add_argument("--deviation", type=int, default=20, help="max slippage (points)")
    ap.add_argument("--interval", type=float, default=15.0, help="daemon poll seconds")
    ap.add_argument("--max-spread-open", type=float, default=None,
                     help="OPTIONAL static HARD spread-cap (OPEN only, price "
                          "units): an OPEN is sent only when the current tick "
                          "spread (ask-bid) <= this; else SKIP. Exits/MODIFY/"
                          "CLOSE are never gated. Default OFF (the ADAPTIVE "
                          "running-min gate is the default for --configs golive; "
                          "see --spread-eps). When BOTH are active the TIGHTER "
                          "binds. Pass a negative value to force-DISABLE.")
    ap.add_argument("--spread-eps", type=float, default=DEFAULT_SPREAD_EPS,
                     help="ADAPTIVE spread-gate epsilon (USD/oz): an OPEN is "
                          "sent only when current spread <= running_min + eps, "
                          "where running_min is the all-time minimum learned in "
                          f"the spread_store. Default {DEFAULT_SPREAD_EPS} -- a "
                          "TINY float-equality tolerance only (NOT a margin "
                          "band): admits entries ONLY at the observed minimum "
                          "spread (0.60 today), PAUSES at 0.61 and above.")
    ap.add_argument("--adaptive-spread", dest="adaptive_spread",
                     action="store_true", default=None,
                     help="force-ENABLE the adaptive running-min spread-gate "
                          "(default: ON for --configs golive, OFF otherwise).")
    ap.add_argument("--no-adaptive-spread", dest="adaptive_spread",
                     action="store_false",
                     help="force-DISABLE the adaptive running-min spread-gate.")
    ap.add_argument("--capture-spread", action="store_true",
                     help="STANDALONE read-only always-on spread capture: attach "
                          "to the DEMO terminal, loop symbol_info_tick + "
                          "spread_store.record every --interval seconds, sending "
                          "NO orders. Use to register spread even when the "
                          "executor is not armed. Ctrl-C to stop.")
    ap.add_argument("--capture-symbol", default="XAUUSD",
                     help="symbol for --capture-spread (default XAUUSD).")
    ap.add_argument("--confirm-account", type=int, default=None,
                     help="non-interactive arm confirmation: must equal the "
                          "sanctioned DEMO login; only effective with --arm")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(AUDIT_LOG, encoding="utf-8")])

    window = max(args.window, MIN_WINDOW)
    roster = args.configs.lower()
    if roster == "all":
        configs = list(CONFIGS_20)
    elif roster == "live":
        configs = list(CONFIGS_LIVE)
    elif roster == "shadow":
        # FIXED4 only -- the corrected roster machine-2 arms (D114: the
        # uncorrected live-4 never runs there).
        configs = list(CONFIGS_SHADOW)
    elif roster == "golive":
        # GL-T1 GO-LIVE roster: M15 V-15 SAR top-5 + V11-M2 (magics 7240x0).
        configs = list(CONFIGS_GOLIVE)
    elif roster == "golive-dedup":
        # DEDUP GO-LIVE (D121): the five M15 SAR clones collapsed to the two
        # best reps (S6-K2P0 + S7-TPNONE) + the distinct lines (V11-M2,
        # SuperTrend). Kills clone-concentration whipsaw; drops no distinct
        # signal. Same 7240x0 magics as golive (kept-rep positions re-sync).
        configs = list(CONFIGS_GOLIVE_DEDUP)
    elif roster == "live+shadow":
        configs = list(CONFIGS_LIVE) + list(CONFIGS_SHADOW)
    elif roster == "live+tk":
        # SUPERVISED roster (2026-07-21): the `live` classic roster PLUS the
        # trader's TK-Momentum-5-8-short, run together in ONE auto-healing
        # supervised executor (SUPERVISOR_CONFIGS=live+tk). TK keeps its own
        # engine (intrabar) + all-nines magic; per-config dispatch handles it.
        configs = list(CONFIGS_LIVE) + list(CONFIGS_TK)
    elif roster == "golive-dedup+tk":
        # SUPERVISED roster (2026-07-21 user decision): the DEDUP go-live roster
        # (S6-K2P0, S7-TPNONE, V11-M2, SuperTrend) PLUS TK-Momentum, in ONE
        # auto-healing supervised executor (SUPERVISOR_CONFIGS=golive-dedup+tk).
        # Adaptive spread-gate stays ON (see below) to preserve golive-dedup's
        # behavior; TK keeps its intrabar engine + all-nines magic.
        configs = list(CONFIGS_GOLIVE_DEDUP) + list(CONFIGS_TK)
    elif roster in ("tk-momentum", "tk"):
        # TK-Momentum-5-8-short (2026-07-21): the trader's isolated live-forward
        # roster, magic 999999999. Runs as its OWN process alongside the rest.
        configs = list(CONFIGS_TK)
    elif roster == "tomachine":
        # MACHINE-2 roster (trader selection 2026-07-22): the FIXED4 shadow
        # configs + the three named go-live configs (S6-K2P0, S7-TPNONE,
        # SuperTrend-p14x3-M15, magics unchanged from CONFIGS_GOLIVE) + the
        # new TK-BW2-fix2atr (magic 725010). Deliberately NO V11-M2 and NO
        # TK-Momentum here.
        configs = list(CONFIGS_TOMACHINE)
    else:
        want = {s.strip() for s in args.configs.split(",")}
        configs = [c for c in CONFIGS_20 if c["id"] in want]
        unknown = want - {c["id"] for c in configs}
        if unknown:
            print(f"unknown config id(s): {sorted(unknown)}", file=sys.stderr)
            return 2
    dry_run = not args.arm
    # --max-spread-open: None (default) => no static hard cap; a negative value
    # explicitly force-disables it too (both => None => the adaptive gate, if
    # enabled, is the only spread limit).
    max_spread_open = (None if args.max_spread_open is None or args.max_spread_open < 0
                       else args.max_spread_open)
    # ADAPTIVE running-min gate: default ON for the go-live roster, OFF else;
    # --adaptive-spread / --no-adaptive-spread override explicitly.
    if args.adaptive_spread is None:
        adaptive_spread = roster in ("golive", "golive-dedup", "golive-dedup+tk",
                                     "tomachine")
    else:
        adaptive_spread = args.adaptive_spread

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

    # MAGIC ALLOCATION SELF-HEAL (Task 3, 2026-07-22): idempotent, INSERT-OR-
    # IGNORE only -- never touches MT5, runs in dry-run too (it only writes
    # to data/research.db's magic_allocation table, not the broker), so a
    # config's magics are always attributable in the UI even if this is the
    # first cycle that ever evaluated it.
    try:
        seeded = ensure_magic_allocations(_MAGIC_ALLOCATION_DB_PATH, configs)
        logger.info("magic_allocation self-heal: %d row(s) inserted (idempotent).", seeded)
    except Exception:  # noqa: BLE001 -- seeding must never abort the executor
        logger.exception("magic_allocation self-heal failed (non-fatal, continuing).")

    stop = {"flag": False}

    def _sigint(_sig, _frm):
        logger.info("Ctrl-C received -- clean shutdown after current cycle.")
        stop["flag"] = True

    signal.signal(signal.SIGINT, _sigint)

    # STANDALONE READ-ONLY spread capture: never touches configs / orders / arm.
    if args.capture_spread:
        store = SpreadStore(symbol=args.capture_symbol)
        logger.info("connected + guard OK: DEMO login %s (CAPTURE-SPREAD mode, "
                    "read-only, symbol=%s)", login, args.capture_symbol)
        try:
            return capture_spread_loop(
                mt5, symbol=args.capture_symbol, interval=args.interval,
                spread_store=store, stop_flag=stop, once=args.once)
        finally:
            try:
                mt5.shutdown()
            except Exception:  # noqa: BLE001
                pass

    spread_store = SpreadStore() if adaptive_spread else None
    logger.info("connected + guard OK: DEMO login %s (dry_run=%s, %d configs, "
                "window=%d, max_spread_open=%s, adaptive_spread=%s eps=%s)",
                login, dry_run, len(configs), window,
                max_spread_open if max_spread_open is not None else "OFF",
                "ON" if adaptive_spread else "OFF",
                args.spread_eps if adaptive_spread else "n/a")

    if args.arm and args.confirm_account is None:
        _arm_confirm()

    # Per-position spread recorder (2026-07-21): persist spread at open/close
    # into `position_spread` so the UI/audit can show it. Only wired when we
    # actually send orders (dry-run never fills); injectable for tests.
    recorder = spread_recorder
    if recorder is None and not dry_run:
        from sentinel_engine.research.registry2 import ResearchRegistry
        _reg = registry if registry is not None else ResearchRegistry()

        def recorder(kind: str, position_id: Any, spread: float | None) -> None:
            if position_id is None:
                return
            ts = int(time.time())
            running_min = spread_store.running_min if spread_store is not None else None
            if kind == "OPEN":
                _reg.record_position_spread(
                    position_id, ticket_open=position_id, spread_open=spread,
                    spread_open_min=running_min, spread_open_ts=ts,
                )
            else:
                _reg.record_position_spread(
                    position_id, spread_close=spread, spread_close_ts=ts,
                )

    same_bar_cost: dict[str, float] = {}
    sl_clamp_cost: dict[str, float] = {}
    try:
        while True:
            run_cycle(mt5, configs, window=window, volume=args.volume,
                      dry_run=dry_run, deviation=args.deviation,
                      same_bar_cost=same_bar_cost, sl_clamp_cost=sl_clamp_cost,
                      max_spread_open=max_spread_open,
                      spread_store=spread_store, spread_eps=args.spread_eps,
                      on_fill=recorder)
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
