"""scripts/report/diag_signal_replay_20260715.py -- THROWAWAY diagnostic
replay (2026-07-15 investigation). Bit-exact reconstruction of what the live
executor (`scripts/live/run_live_20.py::reconcile_config`) would have decided
per closed bar over the 4 LIVE_ROSTER configs, for:
  (1) a positive control window (2026-07-14 01:00-08:00 server) where the
      account actually traded, to validate the harness is not itself broken;
  (2) the primary window under investigation (2026-07-15 08:30-17:00 server);
  (3) the secondary "drought" window (2026-07-14 11:14-12:13 server) while
      the executor was alive logging `actions: none`.

Methodology (mirrors the executor EXACTLY -- read scripts/live/run_live_20.py
reconcile_config() and scripts/live/check_dryrun_intent_parity.py diff_cycle()):
  - bars are loaded from the Parquet tier lake via
    scripts.live.check_live_sim_parity.load_bars (same source/shape the
    executor's fetch_bars() reads from MT5: {"t","open","high","low","close"}).
  - For each closed bar B in a window, take the trailing <=10,000 closed bars
    ending at and including B (DEFAULT_WINDOW in run_live_20.py), and call
    simular_variant(bars, return_state=True, **cfg["kwargs"]). This is
    CLASSIC mode (live_fill_mode not passed / False), exactly what the daemon
    runs each cycle.
  - "entry signal at B" = an event in the returned `events` list with
    ev["idx"] == last_idx (the index of B in the trailing window) and
    ev["motivo"].startswith("ENTRY").
  - "non-empty desired snapshot at B" = snap["open"] (the {tag: {...}} dict)
    is non-empty, i.e. the executor would want >=1 ficha open after
    processing B.
  - Additionally, a single full-window forward pass (bars = ALL bars in
    [window_start - warmup, window_end), i.e. one simular_variant call, not
    one per closed bar) is run in both live_fill_mode=False and
    live_fill_mode=True to count total ENTRY_L/ENTRY_S events independent of
    the per-bar trailing-window framing. This is a cross-check: the
    per-bar-trailing-window replay and the single-pass replay should agree on
    which bars carry NEW entries (both use identical gate logic; the
    per-bar version just re-derives state fresh each time from a 10k-bar
    lookback instead of carrying it forward, but EMASAR's state is bar-local
    Markovian modulo warmup so results must match once both are warmed up).

READ-ONLY. Does not import MetaTrader5. Does not modify run_live_20.py,
emasar_variant.py, or live_configs_20.py.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies.live_configs_20 import CONFIGS_20, LIVE_ROSTER  # noqa: E402
from scripts.live.check_live_sim_parity import load_bars, sim_positions  # noqa: E402

LAKE_ROOT = REPO_ROOT / "data" / "lake"
TF_SECONDS = {"M1": 60, "M2": 120, "M5": 300, "M15": 900}
DEFAULT_WINDOW = 10_000  # matches run_live_20.DEFAULT_WINDOW

# PnL model (matches the executor's ACTUAL run parameters, not a guess):
# scripts/live/run_live_20.py DEFAULT_VOLUME = 0.01 lot/ficha (no --volume
# override is documented as used for this roster), 3 fichas opened per
# ENTRY event (F1/F2/F3, per emasar_variant.simular_variant's fichas dict),
# XAUUSD standard MT5 contract size = 100 oz/lot. A ficha that never exits
# by the end of the analysis bars is left OPEN (unrealized, excluded from
# realized PnL, reported separately as `n_still_open`).
FICHAS_PER_ENTRY = 3
VOLUME_PER_FICHA = 0.01
CONTRACT_SIZE_OZ = 100.0


def positions_pnl_usd(events: list[dict[str, Any]], bars: list[dict[str, Any]],
                       win_start_t: int, win_end_t: int) -> dict[str, Any]:
    """Realized USD PnL for positions whose ENTRY bar lands inside
    [win_start_t, win_end_t), using sim_positions() (entry price + per-ficha
    exit price reconstruction from the event stream, reused from
    check_live_sim_parity.py). Each ficha: pnl = (exit - entry) * side_sign *
    CONTRACT_SIZE_OZ * VOLUME_PER_FICHA. Fichas with no exit event before the
    end of `bars` are still open at the end of the simulated history and are
    excluded from realized PnL (counted in n_still_open)."""
    positions = sim_positions(events, bars)
    realized_usd = 0.0
    n_positions_in_window = 0
    n_fichas_closed = 0
    n_fichas_still_open = 0
    per_position: list[dict[str, Any]] = []
    for pos in positions:
        if not (win_start_t <= pos["t"] < win_end_t):
            continue
        n_positions_in_window += 1
        side_sign = 1.0 if pos["side"] == "L" else -1.0
        entry_price = pos["price"]
        exits_by_ficha: dict[str, dict[str, Any]] = {}
        for ex in pos["exits"]:
            tag = ex.get("ficha")
            if tag is not None and tag not in exits_by_ficha:
                exits_by_ficha[tag] = ex  # first exit per ficha tag closes it
        pos_pnl = 0.0
        for tag in ("F1", "F2", "F3"):
            ex = exits_by_ficha.get(tag)
            if ex is None:
                n_fichas_still_open += 1
                continue
            n_fichas_closed += 1
            ficha_pnl = (ex["price"] - entry_price) * side_sign * CONTRACT_SIZE_OZ * VOLUME_PER_FICHA
            pos_pnl += ficha_pnl
        realized_usd += pos_pnl
        per_position.append({
            "entry_t": pos["t"], "entry_iso": datetime.fromtimestamp(pos["t"], tz=timezone.utc).isoformat(),
            "side": pos["side"], "entry_price": entry_price,
            "n_fichas_closed": sum(1 for t in ("F1", "F2", "F3") if t in exits_by_ficha),
            "n_fichas_open_at_end": sum(1 for t in ("F1", "F2", "F3") if t not in exits_by_ficha),
            "pnl_usd": round(pos_pnl, 4),
        })
    return {
        "n_positions_in_window": n_positions_in_window,
        "n_fichas_closed": n_fichas_closed,
        "n_fichas_still_open_at_end_of_history": n_fichas_still_open,
        "realized_pnl_usd": round(realized_usd, 4),
        "positions": per_position,
    }

CONFIGS_LIVE = [c for c in CONFIGS_20 if c["id"] in LIVE_ROSTER]
assert len(CONFIGS_LIVE) == 4


def _utc(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def load_all_bars_for_tf(symbol: str, tf: str, upto: datetime, lookback_days: int = 260) -> list[dict[str, Any]]:
    """Load a generous history window ending at `upto` (exclusive), enough to
    cover DEFAULT_WINDOW trailing bars even for M15 (10_000 * 900s = ~104
    days) with slack for weekend/holiday gaps."""
    start = upto - timedelta(days=lookback_days)
    return load_bars(LAKE_ROOT, symbol, tf, start, upto)


def replay_window(cfg: dict[str, Any], all_bars: list[dict[str, Any]],
                   win_start_t: int, win_end_t: int) -> dict[str, Any]:
    """Per-closed-bar trailing-window replay, exactly mirroring
    run_live_20.reconcile_config: for every closed bar B with
    win_start_t <= B.t < win_end_t, take the trailing <=DEFAULT_WINDOW bars
    ending at B (inclusive) and call simular_variant(return_state=True).
    Records desired-open snapshot and any NEW entry at B."""
    bar_times = [b["t"] for b in all_bars]
    # indices of bars within the window
    win_idxs = [i for i, t in enumerate(bar_times) if win_start_t <= t < win_end_t]

    per_bar: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    nonempty_snapshot_bars = 0

    for i in win_idxs:
        lo = max(0, i - DEFAULT_WINDOW + 1)
        trailing = all_bars[lo:i + 1]
        if len(trailing) < 2:
            continue
        kwargs = dict(cfg["kwargs"])
        events, snap = simular_variant(trailing, return_state=True, **kwargs)
        last_idx = len(trailing) - 1
        open_state = snap.get("open") or {}
        new_entries = [ev for ev in events if ev["idx"] == last_idx and ev["motivo"].startswith("ENTRY")]
        if open_state:
            nonempty_snapshot_bars += 1
        rec = {
            "t": all_bars[i]["t"],
            "iso": datetime.fromtimestamp(all_bars[i]["t"], tz=timezone.utc).isoformat(),
            "n_open": len(open_state),
            "new_entries": [{"side": ev["lado"], "price": ev["precio"], "motivo": ev["motivo"]} for ev in new_entries],
        }
        per_bar.append(rec)
        for ev in new_entries:
            entries.append({
                "t": all_bars[i]["t"],
                "iso": rec["iso"],
                "side": ev["lado"],
                "price": ev["precio"],
                "motivo": ev["motivo"],
            })

    return {
        "n_closed_bars_in_window": len(win_idxs),
        "n_nonempty_snapshot_bars": nonempty_snapshot_bars,
        "n_entries": len(entries),
        "entries": entries,
        "per_bar": per_bar,
    }


def single_pass_counts(cfg: dict[str, Any], all_bars: list[dict[str, Any]],
                        win_start_t: int, win_end_t: int) -> dict[str, Any]:
    """One simular_variant call over ALL bars available in `all_bars` (full
    history through the lake's freshest bar, NOT truncated at win_end_t --
    this lets exits that occur AFTER the window close still be captured for
    PnL reconstruction), for both live_fill_mode False/True. Entry events are
    filtered to those landing inside [win_start_t, win_end_t) for the entry
    count/cross-check; PnL is computed separately via positions_pnl_usd()
    over the SAME full-history event stream so exits past win_end_t are
    matched to their entry."""
    out = {}
    for mode_name, live_fill_mode in (("classic", False), ("live_fill", True)):
        kwargs = dict(cfg["kwargs"])
        events = simular_variant(all_bars, return_state=False, live_fill_mode=live_fill_mode, **kwargs)
        entries = []
        for ev in events:
            if not ev["motivo"].startswith("ENTRY"):
                continue
            t = all_bars[ev["idx"]]["t"]
            if win_start_t <= t < win_end_t:
                entries.append({
                    "t": t, "iso": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                    "side": ev["lado"], "price": ev["precio"], "motivo": ev["motivo"],
                })
        pnl = positions_pnl_usd(events, all_bars, win_start_t, win_end_t)
        out[mode_name] = {"n_entries": len(entries), "entries": entries, "pnl": pnl}
    return out


def per_hour_breakdown(entries: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in entries:
        hour_key = datetime.fromtimestamp(e["t"], tz=timezone.utc).strftime("%Y-%m-%dT%H:00")
        out[hour_key] = out.get(hour_key, 0) + 1
    return dict(sorted(out.items()))


def run_all_windows() -> dict[str, Any]:
    windows = {
        "control_2026-07-14_01-08": (_utc("2026-07-14T01:00:00"), _utc("2026-07-14T08:00:00")),
        "primary_2026-07-15_0830-1700": (_utc("2026-07-15T08:30:00"), _utc("2026-07-15T17:00:00")),
        "secondary_drought_2026-07-14_1114-1213": (_utc("2026-07-14T11:14:00"), _utc("2026-07-14T12:13:00")),
    }
    # latest possible upto for bar loading = max window end + slack
    max_end = max(e for _, e in windows.values())

    results: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(), "windows": {}}

    # cache bars per tf
    bars_cache: dict[str, list[dict[str, Any]]] = {}

    for cfg in CONFIGS_LIVE:
        tf = cfg["tf"]
        symbol = cfg["kwargs"]["symbol"]
        cache_key = f"{symbol}:{tf}"
        if cache_key not in bars_cache:
            t0 = time.time()
            bars_cache[cache_key] = load_all_bars_for_tf(symbol, tf, max_end + timedelta(days=1))
            print(f"[load] {cache_key}: {len(bars_cache[cache_key])} bars "
                  f"({time.time()-t0:.1f}s), "
                  f"range {datetime.fromtimestamp(bars_cache[cache_key][0]['t'], tz=timezone.utc).isoformat()} "
                  f".. {datetime.fromtimestamp(bars_cache[cache_key][-1]['t'], tz=timezone.utc).isoformat()}")

    for win_name, (wstart, wend) in windows.items():
        win_start_t, win_end_t = int(wstart.timestamp()), int(wend.timestamp())
        results["windows"][win_name] = {"start": wstart.isoformat(), "end": wend.isoformat(), "configs": {}}
        for cfg in CONFIGS_LIVE:
            tf = cfg["tf"]
            symbol = cfg["kwargs"]["symbol"]
            all_bars = bars_cache[f"{symbol}:{tf}"]
            t0 = time.time()
            rep = replay_window(cfg, all_bars, win_start_t, win_end_t)
            sp = single_pass_counts(cfg, all_bars, win_start_t, win_end_t)
            dt_s = time.time() - t0
            entry_ts = rep["entries"]
            first20 = entry_ts[:20]
            classic_pnl = sp["classic"]["pnl"]
            livefill_pnl = sp["live_fill"]["pnl"]
            results["windows"][win_name]["configs"][cfg["id"]] = {
                "tf": tf,
                "n_closed_bars_in_window": rep["n_closed_bars_in_window"],
                "n_nonempty_snapshot_bars": rep["n_nonempty_snapshot_bars"],
                "per_bar_trailing_window_n_entries": rep["n_entries"],
                "per_hour": per_hour_breakdown(entry_ts),
                "first_20_entries": first20,
                "single_pass_classic_n_entries": sp["classic"]["n_entries"],
                "single_pass_live_fill_n_entries": sp["live_fill"]["n_entries"],
                "single_pass_classic_entries": sp["classic"]["entries"][:50],
                "single_pass_live_fill_entries": sp["live_fill"]["entries"][:50],
                "pnl_model": {"volume_per_ficha_lot": VOLUME_PER_FICHA,
                              "fichas_per_entry": FICHAS_PER_ENTRY,
                              "contract_size_oz": CONTRACT_SIZE_OZ},
                "classic_pnl_usd": classic_pnl["realized_pnl_usd"],
                "classic_pnl_n_positions": classic_pnl["n_positions_in_window"],
                "classic_pnl_n_fichas_closed": classic_pnl["n_fichas_closed"],
                "classic_pnl_n_fichas_still_open": classic_pnl["n_fichas_still_open_at_end_of_history"],
                "classic_pnl_positions": classic_pnl["positions"],
                "livefill_pnl_usd": livefill_pnl["realized_pnl_usd"],
                "livefill_pnl_n_positions": livefill_pnl["n_positions_in_window"],
                "livefill_pnl_n_fichas_closed": livefill_pnl["n_fichas_closed"],
                "livefill_pnl_n_fichas_still_open": livefill_pnl["n_fichas_still_open_at_end_of_history"],
                "livefill_pnl_positions": livefill_pnl["positions"],
                "elapsed_s": round(dt_s, 2),
            }
            print(f"[{win_name}] {cfg['id']}: per-bar entries={rep['n_entries']} "
                  f"single-pass classic={sp['classic']['n_entries']} live_fill={sp['live_fill']['n_entries']} "
                  f"nonempty-snapshot-bars={rep['n_nonempty_snapshot_bars']}/{rep['n_closed_bars_in_window']} "
                  f"classic_pnl=${classic_pnl['realized_pnl_usd']:.2f} "
                  f"livefill_pnl=${livefill_pnl['realized_pnl_usd']:.2f} "
                  f"({dt_s:.1f}s)")

    return results


if __name__ == "__main__":
    results = run_all_windows()
    out_path = REPO_ROOT / "scripts" / "report" / "diag_replay_20260715.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {out_path}")
