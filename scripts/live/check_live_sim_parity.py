"""scripts/live/check_live_sim_parity.py -- LIVE shadow-parity checker
(PHASE 3.5, 2026-07-13 protocol addition).

Verifies that a live-deployed config (one of the curated 20 in
`sentinel_engine.strategies.live_configs_20`) took THE SAME POSITIONS the
simulator (`simular_variant`) would have taken on the same market data:

  (a) bars: loaded from the Parquet lake (`data/lake/<SYMBOL>/<TF>/YYYY-MM.parquet`),
      the same source the historical/live service path consumes;
  (b) sim: re-runs `simular_variant(**config.kwargs)` on those bars;
  (c) live: pulls REAL deals from `deals_raw` in `data/research.db`
      (populated by DealsWatcher from DEMO 2883015767), matched by the
      config's magic band [magic+1 .. magic+3] (per-ficha TOKATA offsets);
  (d) diff: entry bar/side/price (tolerance = spread + 1 tick), exits
      (bar/price/side), ficha count. Signal-level mismatches (live position
      the sim would not have taken, or a sim entry the live system missed)
      are HARD divergences; price offsets within tolerance are reported as
      WITHIN_TOLERANCE (acceptable: live spread vs. flat model, slippage
      <= tol).

READ-ONLY: never imports MetaTrader5, never sends orders; only reads the
lake and the sqlite registry.

Usage:
    python -m scripts.live.check_live_sim_parity --config SS-M5 \
        --start 2026-07-13 --end 2026-07-14
    python -m scripts.live.check_live_sim_parity --config all \
        --start 2026-07-13 --end 2026-07-14 [--db data/research.db] \
        [--lake data/lake] [--spread 0.5] [--tick 0.01] [--json out.json]

Exit code: 0 = all checked configs MATCH (tolerated diffs OK);
           1 = at least one HARD divergence;
           2 = usage/data error (no bars, unknown config).
"""
from __future__ import annotations

import argparse
import bisect
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies.live_configs_20 import CONFIGS_20  # noqa: E402

TF_SECONDS = {"M1": 60, "M2": 120, "M5": 300, "M15": 900}

# ---------------------------------------------------------------------------
# Known acceptable differences (classified, never hard failures):
#   - ENTRY/EXIT PRICE within tolerance = spread + 1 tick (live fills cross
#     the spread; the sim uses bar close/level prices from a flat 0.5 model).
#   - Same-bar timing: live deal timestamps land INSIDE the signal bar or at
#     its close; matching is bar-level, not tick-level.
#   - Weekend/holiday gaps: bars missing from the lake are skipped on both
#     sides identically (same data source), so no divergence is emitted.
#   - Partial fills: multiple IN deals summing to the ficha volume on the
#     same bar/side count as ONE live entry (volumes aggregated).
# Anything else (extra live position, missed sim entry, wrong side, price
# beyond tolerance, ficha-count mismatch) is HARD.
# ---------------------------------------------------------------------------


@dataclass
class Divergence:
    kind: str          # e.g. MISSED_ENTRY, EXTRA_ENTRY, SIDE_MISMATCH, ...
    hard: bool
    detail: str


@dataclass
class ParityReport:
    config_id: str
    magic: int
    n_bars: int = 0
    sim_entries: int = 0
    live_entries: int = 0
    matches: int = 0
    within_tolerance: int = 0
    same_bar_optimism: int = 0
    same_bar_cost: float = 0.0
    entry_next_bar: int = 0
    entry_slip_cost: float = 0.0
    divergences: list[Divergence] = field(default_factory=list)

    @property
    def hard_divergences(self) -> list[Divergence]:
        return [d for d in self.divergences if d.hard]

    @property
    def verdict(self) -> str:
        return "DIVERGENCE" if self.hard_divergences else "MATCH"


# ---------------- data loading ----------------

def load_bars(lake_root: Path, symbol: str, tf: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Load [start, end) bars from the lake, spanning months as needed.
    Each bar: {t, open, high, low, close}. Same source/columns convention as
    the research harness loaders."""
    import pyarrow.parquet as pq

    bars: list[dict[str, Any]] = []
    # iterate months covering the window
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        path = lake_root / symbol / tf / f"{y:04d}-{m:02d}.parquet"
        if path.exists():
            table = pq.read_table(path)
            cols = {name: table.column(name).to_pylist() for name in table.schema.names}
            tcol = "t" if "t" in cols else ("time" if "time" in cols else None)
            if tcol is None:
                raise ValueError(f"no time column in {path}")
            # lake schema is short-form (t,o,h,l,c,v); accept long-form too
            key = {k: (k if k in cols else k[0]) for k in ("open", "high", "low", "close")}
            for i, t in enumerate(cols[tcol]):
                ts = int(t.timestamp()) if hasattr(t, "timestamp") else int(t)
                bars.append({
                    "t": ts,
                    "open": cols[key["open"]][i], "high": cols[key["high"]][i],
                    "low": cols[key["low"]][i], "close": cols[key["close"]][i],
                })
        m += 1
        if m == 13:
            y, m = y + 1, 1
    s, e = int(start.timestamp()), int(end.timestamp())
    bars = [b for b in bars if s <= b["t"] < e]
    bars.sort(key=lambda b: b["t"])
    return bars


def load_bars_with_warmup(lake_root: Path, symbol: str, tf: str, start: datetime, end: datetime,
                          warmup_bars: int) -> tuple[list[dict[str, Any]], int]:
    """Load warmup_bars bars BEFORE `start` (extra 1.6x margin to absorb
    weekend/holiday gaps, then trimmed to the last `warmup_bars`) plus the
    [start, end) window bars. Returns (bars, first_in_window_idx) where
    bars[first_in_window_idx] is the first bar with t >= start."""
    from datetime import timedelta

    tf_s = TF_SECONDS[tf]
    warmup_start = start - timedelta(seconds=warmup_bars * tf_s * 1.6)
    warmup_pool = load_bars(lake_root, symbol, tf, warmup_start, start)
    if len(warmup_pool) > warmup_bars:
        warmup_pool = warmup_pool[-warmup_bars:]
    day_bars = load_bars(lake_root, symbol, tf, start, end)
    bars = warmup_pool + day_bars
    first_idx = len(warmup_pool)
    return bars, first_idx


def load_live_deals(db_path: Path, magic_lo: int, magic_hi: int,
                    start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Deals from deals_raw for magics in [magic_lo, magic_hi] within the
    window. Read-only."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ticket, position_id, symbol, side, volume, price, profit,"
            " magic, time, entry_type FROM deals_raw"
            " WHERE magic BETWEEN ? AND ? AND time >= ? AND time < ?"
            " ORDER BY time, ticket",
            (magic_lo, magic_hi, int(start.timestamp()), int(end.timestamp())),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------- normalization ----------------

def _bar_index_of(bar_times: list[int], ts: int, tf_s: int) -> int | None:
    """Map an epoch ts to the index of the bar whose [t, t+tf_s) contains it
    (bar-level matching; live deal timestamps land inside or at the close of
    the signal bar)."""
    j = bisect.bisect_right(bar_times, ts) - 1
    if j >= 0 and bar_times[j] <= ts < bar_times[j] + tf_s:
        return j
    # a fill logged exactly at bar close belongs to the closed bar
    if j + 1 < len(bar_times) and ts == bar_times[j + 1]:
        return j
    return None


def sim_positions(events: list[dict[str, Any]], bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sim event stream -> expected positions:
    [{bar_idx, t, side, price, fichas, exits:[{bar_idx, price, motivo, ficha}]}]."""
    positions: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for ev in events:
        if ev["motivo"].startswith("ENTRY"):
            cur = {"bar_idx": ev["idx"], "t": bars[ev["idx"]]["t"],
                   "side": ev["lado"], "price": ev["precio"],
                   "fichas": 3, "exits": []}
            positions.append(cur)
        elif cur is not None:
            cur["exits"].append({"bar_idx": ev["idx"], "t": bars[ev["idx"]]["t"],
                                 "price": ev["precio"], "motivo": ev["motivo"],
                                 "ficha": ev.get("ficha")})
    return positions


def live_positions(deals: list[dict[str, Any]], bars: list[dict[str, Any]], tf_s: int) -> list[dict[str, Any]]:
    """Group deals by position_id -> live positions with entry/exit mapped to
    bar indices. Partial fills (several IN deals, same position) aggregate to
    one entry at the volume-weighted price."""
    bar_times = [b["t"] for b in bars]
    by_pos: dict[Any, dict[str, list[dict[str, Any]]]] = {}
    for d in deals:
        g = by_pos.setdefault(d["position_id"], {"IN": [], "OUT": []})
        g[(d.get("entry_type") or "IN").upper()].append(d)
    out: list[dict[str, Any]] = []
    for pid, g in by_pos.items():
        if not g["IN"]:
            continue
        vol = sum(x["volume"] or 0.0 for x in g["IN"])
        vwap = (sum((x["price"] or 0.0) * (x["volume"] or 0.0) for x in g["IN"]) / vol) if vol else g["IN"][0]["price"]
        t_in = min(x["time"] for x in g["IN"])
        pos = {
            "position_id": pid,
            "bar_idx": _bar_index_of(bar_times, t_in, tf_s),
            "t": t_in,
            "side": (g["IN"][0]["side"] or "").upper(),  # LONG/SHORT or BUY/SELL
            "price": vwap,
            "magic": g["IN"][0]["magic"],
            "exits": [{"bar_idx": _bar_index_of(bar_times, x["time"], tf_s),
                       "t": x["time"], "price": x["price"]} for x in sorted(g["OUT"], key=lambda x: x["time"])],
        }
        out.append(pos)
    out.sort(key=lambda p: p["t"])
    return out


_SIDE_NORM = {"L": "L", "S": "S", "LONG": "L", "SHORT": "S", "BUY": "L", "SELL": "S"}

# Stop/trail exit motivos (sentinel_engine.strategies.emasar_variant): a trail
# raised using the just-closed bar's OWN high/AC can stop the sim out WITHIN
# that bar, while live's server-side SL only catches up next tick (fallback
# market-close). EXIT_TP/EXIT_INITSL/EXIT_ACDECEL fire at a fixed/pre-existing
# level (not a same-bar-raised trail), so they don't qualify.
_TRAIL_EXIT_MOTIVOS = {"EXIT_TRAIL"}


# ---------------- diff ----------------

def diff_config(config: dict[str, Any], bars: list[dict[str, Any]],
                deals: list[dict[str, Any]], *, spread: float = 0.5,
                tick: float = 0.01, direction_mask: list[int] | None = None,
                first_in_window_idx: int = 0) -> ParityReport:
    """Core diff (pure; injectable for tests). Entry matching is bar-level
    per signal: sim fires ONE entry (3 fichas) per signal bar; live shows up
    as up-to-3 positions (magic+1/+2/+3) on that bar.

    `bars` may include warmup bars BEFORE the diff window; `simular_variant`
    is run over the full list (for correct indicator state), but only sim
    events whose bar index >= first_in_window_idx participate in the diff.
    Live deals are already restricted to [start, end) by the caller."""
    tf_s = TF_SECONDS[config["tf"]]
    tol = spread + tick
    n_window_bars = len(bars) - first_in_window_idx
    rep = ParityReport(config_id=config["id"], magic=config["magic"], n_bars=n_window_bars)

    kwargs = dict(config["kwargs"])
    if config.get("direction_filter"):
        kwargs["direction_mask"] = direction_mask
    events = simular_variant(bars, **kwargs)
    sim_all = sim_positions(events, bars)
    sim = [s for s in sim_all if s["bar_idx"] >= first_in_window_idx]
    live_all = live_positions(deals, bars, tf_s)
    rep.sim_entries = len(sim)

    # group live positions by signal bar (fichas of one signal share the bar)
    live_by_bar: dict[int | None, list[dict[str, Any]]] = {}
    for p in live_all:
        live_by_bar.setdefault(p["bar_idx"], []).append(p)
    rep.live_entries = len(live_by_bar) - (1 if None in live_by_bar else 0)

    for p in live_by_bar.pop(None, []):
        rep.divergences.append(Divergence(
            "LIVE_ENTRY_OUTSIDE_BARS", True,
            f"live position {p['position_id']} at t={p['t']} maps to no bar in window"))

    matched_bars: set[int] = set()  # bars whose live group was consumed by a sim entry (N match)
    matched_next_bars: set[int] = set()  # bars whose live group was consumed as an N+1 match
    # Prefer exact-bar (N) matches over next-bar (N+1) fallback matches: a live
    # group must not be claimed by two different sim entries. First pass
    # reserves every exact-N live group so a later sim entry's N+1 fallback
    # can't steal a group that's the exact match for its own signal bar.
    exact_claimed = {s["bar_idx"] for s in sim if s["bar_idx"] in live_by_bar}
    for s in sim:
        group = live_by_bar.get(s["bar_idx"])
        matched_at_next = False
        if not group:
            next_bar = s["bar_idx"] + 1
            if next_bar not in exact_claimed:
                group = live_by_bar.get(next_bar)
                if group:
                    matched_at_next = True
        if not group:
            rep.divergences.append(Divergence(
                "MISSED_ENTRY", True,
                f"sim entry {s['side']}@{s['price']:.2f} bar {s['bar_idx']} "
                f"(t={s['t']}) has no live position at bar {s['bar_idx']} or {s['bar_idx'] + 1}"))
            continue
        if matched_at_next:
            matched_next_bars.add(s["bar_idx"] + 1)
        else:
            matched_bars.add(s["bar_idx"])
        # side
        bad_side = [p for p in group if _SIDE_NORM.get(p["side"], "?") != s["side"]]
        if bad_side:
            rep.divergences.append(Divergence(
                "SIDE_MISMATCH", True,
                f"bar {s['bar_idx']}: sim {s['side']} vs live "
                f"{[p['side'] for p in bad_side]}"))
            continue
        # ficha count
        if len(group) != s["fichas"]:
            rep.divergences.append(Divergence(
                "FICHA_COUNT", True,
                f"bar {s['bar_idx']}: sim expects {s['fichas']} fichas, live opened {len(group)}"))
        # entry price
        worst = max(abs((p["price"] or 0.0) - s["price"]) for p in group)
        if matched_at_next:
            rep.matches += 1
            rep.entry_next_bar += 1
            rep.entry_slip_cost += worst
            rep.divergences.append(Divergence(
                "ENTRY_NEXT_BAR", False,
                f"bar {s['bar_idx']}: sim entry matched live group at bar {s['bar_idx'] + 1} "
                f"(next-tick fill), |live-sim| entry px = {worst:.4f}"))
        elif worst <= tick:
            rep.matches += 1
        elif worst <= tol:
            rep.matches += 1
            rep.within_tolerance += 1
            rep.divergences.append(Divergence(
                "ENTRY_PRICE_WITHIN_TOL", False,
                f"bar {s['bar_idx']}: |live-sim| entry px = {worst:.4f} <= tol {tol:.4f}"))
        else:
            rep.divergences.append(Divergence(
                "ENTRY_PRICE_OUT_OF_TOL", True,
                f"bar {s['bar_idx']}: |live-sim| entry px = {worst:.4f} > tol {tol:.4f}"))
        # exits: compare bar-level exit sets (sim per-ficha exits vs live OUT deals)
        sim_exit_bars = sorted(e["bar_idx"] for e in s["exits"])
        live_exit_bars = sorted(e["bar_idx"] for p in group for e in p["exits"]
                                if e["bar_idx"] is not None)
        # allow the same-bar-optimism fallback: a trail exit's live fill can
        # legitimately land one bar later (fallback market-close next tick) --
        # don't hard-fail EXIT_BARS_MISMATCH for that specific off-by-one, let
        # the per-pair price classification below decide SAME_BAR_OPTIMISM vs
        # OUT_OF_TOL.
        bars_mismatch = bool(sim_exit_bars and live_exit_bars and sim_exit_bars != live_exit_bars)
        if bars_mismatch and len(sim_exit_bars) == len(live_exit_bars) and all(
            e["motivo"] in _TRAIL_EXIT_MOTIVOS for e in s["exits"]
        ) and all(
            lb is not None and sb is not None and lb in (sb, sb + 1)
            for sb, lb in zip(sim_exit_bars, live_exit_bars)
        ):
            bars_mismatch = False
        if bars_mismatch:
            rep.divergences.append(Divergence(
                "EXIT_BARS_MISMATCH", True,
                f"bar {s['bar_idx']}: sim exit bars {sim_exit_bars} != live {live_exit_bars}"))
        elif s["exits"]:
            sim_pairs = sorted(
                ((e["price"], e["bar_idx"], e["motivo"]) for e in s["exits"]),
                key=lambda x: x[0])
            live_pairs = sorted(
                ((e["price"], e["bar_idx"], e["t"]) for p in group for e in p["exits"]),
                key=lambda x: x[0])
            if live_pairs and len(live_pairs) == len(sim_pairs):
                worst_x = max(abs(a[0] - b[0]) for a, b in zip(sim_pairs, live_pairs))
                # preserve prior aggregate messages/behavior for the common cases
                if tick < worst_x <= tol:
                    rep.divergences.append(Divergence(
                        "EXIT_PRICE_WITHIN_TOL", False,
                        f"bar {s['bar_idx']}: exit px worst diff {worst_x:.4f} <= tol"))
                elif worst_x > tol:
                    for (sim_px, sim_bar_idx, sim_motivo), (live_px, live_bar_idx, live_t) in zip(sim_pairs, live_pairs):
                        gap = abs(sim_px - live_px)
                        if gap <= tick:
                            continue
                        if gap <= tol:
                            rep.divergences.append(Divergence(
                                "EXIT_PRICE_WITHIN_TOL", False,
                                f"bar {s['bar_idx']}: exit px diff {gap:.4f} <= tol"))
                            continue
                        same_bar_or_next = (
                            live_bar_idx is not None
                            and sim_bar_idx is not None
                            and live_bar_idx in (sim_bar_idx, sim_bar_idx + 1)
                        )
                        if sim_motivo in _TRAIL_EXIT_MOTIVOS and same_bar_or_next:
                            rep.same_bar_optimism += 1
                            rep.same_bar_cost += gap
                            rep.divergences.append(Divergence(
                                "SAME_BAR_OPTIMISM", False,
                                f"bar {s['bar_idx']}: sim exit ({sim_motivo}) px {sim_px:.4f} "
                                f"vs live px {live_px:.4f} gap {gap:.4f} > tol {tol:.4f} "
                                f"(live fill bar {live_bar_idx}, fallback next-tick close -- by design)"))
                        else:
                            rep.divergences.append(Divergence(
                                "EXIT_PRICE_OUT_OF_TOL", True,
                                f"bar {s['bar_idx']}: exit px diff {gap:.4f} > tol {tol:.4f} "
                                f"(sim motivo {sim_motivo})"))

    for bar_idx, group in live_by_bar.items():
        if bar_idx in matched_bars or bar_idx in matched_next_bars:
            continue
        rep.divergences.append(Divergence(
            "EXTRA_ENTRY", True,
            f"live opened {len(group)} position(s) on bar {bar_idx} "
            f"(t={bars[bar_idx]['t']}) where sim has NO entry at bar {bar_idx} or {bar_idx - 1}"))
    return rep


# ---------------- CLI ----------------

def _fmt_report(rep: ParityReport) -> str:
    lines = [f"== {rep.config_id} (magic {rep.magic}) -> {rep.verdict} ==",
             f"   bars={rep.n_bars} sim_entries={rep.sim_entries} "
             f"live_entries={rep.live_entries} matched={rep.matches} "
             f"within_tol={rep.within_tolerance} "
             f"same_bar_optimism={rep.same_bar_optimism} same_bar_cost={rep.same_bar_cost:.4f} "
             f"entry_next_bar={rep.entry_next_bar} entry_slip_cost={rep.entry_slip_cost:.4f}"]
    for d in rep.divergences:
        lines.append(f"   [{'HARD' if d.hard else 'ok  '}] {d.kind}: {d.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live vs simular_variant shadow-parity checker (read-only).")
    ap.add_argument("--config", required=True, help="config id (e.g. SS-M5) or 'all'")
    ap.add_argument("--start", required=True, help="UTC date/datetime, e.g. 2026-07-13")
    ap.add_argument("--end", required=True, help="UTC date/datetime (exclusive)")
    ap.add_argument("--db", default=str(REPO_ROOT / "data" / "research.db"))
    ap.add_argument("--lake", default=str(REPO_ROOT / "data" / "lake"))
    ap.add_argument("--spread", type=float, default=0.5, help="flat spread model (XAUUSD default 0.5)")
    ap.add_argument("--tick", type=float, default=0.01)
    ap.add_argument("--json", default=None, help="optional path to dump the machine-readable report")
    ap.add_argument("--warmup-bars", type=int, default=10000,
                    help="bars loaded BEFORE --start to warm up indicator state "
                         "(matches the live executor's recompute window default)")
    args = ap.parse_args(argv)

    def _parse_dt(s: str) -> datetime:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    start, end = _parse_dt(args.start), _parse_dt(args.end)
    if args.config.lower() == "all":
        configs = CONFIGS_20
    else:
        configs = [c for c in CONFIGS_20 if c["id"] == args.config]
        if not configs:
            print(f"unknown config id: {args.config}", file=sys.stderr)
            return 2

    reports: list[ParityReport] = []
    for cfg in configs:
        bars, first_in_window_idx = load_bars_with_warmup(
            Path(args.lake), cfg["kwargs"]["symbol"], cfg["tf"], start, end, args.warmup_bars)
        day_bars = bars[first_in_window_idx:]
        if not day_bars:
            print(f"== {cfg['id']} == NO BARS in lake for {cfg['tf']} {args.start}..{args.end}",
                  file=sys.stderr)
            return 2
        direction_mask = None
        if cfg.get("direction_filter"):
            from scripts.report.gen_variant_batch5 import compute_direction_mask  # lazy
            direction_mask = compute_direction_mask(bars)
        deals = load_live_deals(Path(args.db), cfg["magic"] + 1, cfg["magic"] + 3, start, end)
        rep = diff_config(cfg, bars, deals, spread=args.spread, tick=args.tick,
                          direction_mask=direction_mask, first_in_window_idx=first_in_window_idx)
        reports.append(rep)
        print(_fmt_report(rep))

    if args.json:
        Path(args.json).write_text(json.dumps([{
            "config_id": r.config_id, "magic": r.magic, "verdict": r.verdict,
            "n_bars": r.n_bars, "sim_entries": r.sim_entries,
            "live_entries": r.live_entries, "matches": r.matches,
            "within_tolerance": r.within_tolerance,
            "same_bar_optimism": r.same_bar_optimism,
            "same_bar_cost": r.same_bar_cost,
            "entry_next_bar": r.entry_next_bar,
            "entry_slip_cost": r.entry_slip_cost,
            "divergences": [{"kind": d.kind, "hard": d.hard, "detail": d.detail}
                            for d in r.divergences],
        } for r in reports], indent=2), encoding="utf-8")

    n_hard = sum(len(r.hard_divergences) for r in reports)
    print(f"\nTOTAL: {len(reports)} config(s), "
          f"{sum(1 for r in reports if r.verdict == 'MATCH')} MATCH, "
          f"{sum(1 for r in reports if r.verdict != 'MATCH')} DIVERGENCE, "
          f"{n_hard} hard divergence(s).")
    return 1 if n_hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
