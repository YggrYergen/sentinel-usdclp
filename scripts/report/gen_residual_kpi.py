r"""scripts/report/gen_residual_kpi.py -- P65 (Wave 6 governance, the last of
the wave): the sim-expected-vs-live-actual NET RESIDUAL as a TRACKED KPI.

WHAT IT COMPUTES
----------------
Per live config (and total), over a period:

    residual = live_net - sim_expected_net

with the BY-DESIGN components broken out so any residual is ATTRIBUTABLE, not
mysterious:

    same_bar_cost   -- the SAME_BAR "same-bar optimism" by-design cost the sim
                       enjoyed (sim exit at a same-bar-raised trail level the
                       live executor's server-side SL cannot replicate until the
                       next tick). Read straight from run_live_20's own audit-log
                       telemetry ("SAME_BAR cumulative by-design cost").
    sl_clamp_gap    -- the SL_CLAMP gap (desired SL closer to market than the
                       broker's trade_stops_level allows; the clamped level costs
                       a small, accountable gap). Read from the audit-log
                       "SL_CLAMP cumulative gap" telemetry.
    by_design_total = same_bar_cost + sl_clamp_gap
    unexplained     = residual - by_design_total

HONEST COVERAGE
---------------
The running live GOLIVE audit log records the BY-DESIGN telemetry
(SAME_BAR / SL_CLAMP) and realized-FILL COUNTS (SENT OPEN/CLOSE), but it does
NOT record realized per-config P&L. So the live-net side of the residual is
only fully observable when a realized-net series is supplied AND the live
sample is large enough to be meaningful. When either is missing the KPI reports
`status == "insufficient_live_sample"` for that config (and, if every config is
short, for the total) rather than fabricating a residual -- but it STILL reports
the by-design components, which ARE observable from telemetry. Live history is
currently thin; this KPI is designed to SAY SO.

GOVERNANCE ONLY
---------------
This is a REPORT ARTIFACT + a queryable value. It NEVER writes a run, a score,
or a DSR; it never imports the scoring/DSR mutators; it never touches the live
executor. It is deterministic: identical inputs -> byte-identical JSON.

REUSE
-----
* run_live_20's audit-log telemetry line formats (SAME_BAR / SL_CLAMP cumulative,
  SENT OPEN/CLOSE) -- parsed READ-ONLY here, never re-derived.
* the honest sim pipeline: the sim-expected net per config is produced by
  `_sim_expected_net`, which runs `simular_variant(**cfg["kwargs"],
  live_fill_mode=True)` over the window and pairs fills the same way the
  gen_livefill_bound / gen_variant_batch loaders do (the honest-fills bound).
* `sentinel_engine.strategies.live_configs_20` for the config kwargs (base ids
  and their `-F` fixed siblings), so the sim side aligns 1:1 with the audit-log
  config keys.

USAGE
    # design report from the live audit log (current residual or "insufficient"):
    python scripts/report/gen_residual_kpi.py --report-json out.json
    # queryable value for one config:
    python scripts/report/gen_residual_kpi.py --config V13-M2
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

AUDIT_LOG = ROOT / "scripts" / "live" / "run_live_20.audit.log"

# Governance-honesty default: require MORE than one live fill before a residual
# is considered a meaningful sample. A single fill is not evidence.
DEFAULT_MIN_LIVE_FILLS = 10

INSUFFICIENT_SAMPLE = "insufficient_live_sample"

# --------------------------------------------------------------------------
# Audit-log line patterns (run_live_20's own formats; parsed READ-ONLY).
# --------------------------------------------------------------------------
# "SAME_BAR cumulative by-design cost (this run): total=$-205.79 | A=$-73.65, B=$13.36"
_SAME_BAR_RE = re.compile(r"SAME_BAR cumulative by-design cost \(this run\): total=\$[-0-9.]+ \| (.+)$")
# "SL_CLAMP cumulative gap (this run): total=$69.85 | A=$16.85, B=$1.42"
_SL_CLAMP_RE = re.compile(r"SL_CLAMP cumulative gap \(this run\): total=\$[-0-9.]+ \| (.+)$")
# "config=$value" pairs inside the "|" tail
_PAIR_RE = re.compile(r"([A-Za-z0-9_-]+)=\$(-?[0-9.]+)")
# "[SENT OPEN] V11-M2 F1 magic=... -> retcode=..."
_SENT_OPEN_RE = re.compile(r"\[SENT OPEN\]\s+(\S+)\s+F\d")
# "[SENT CLOSE] ticket=... -> retcode=..."  (no config id -> total only)
_SENT_CLOSE_RE = re.compile(r"\[SENT CLOSE\]")


def parse_audit_telemetry(log_path: str | Path) -> dict[str, Any]:
    """Parse per-config by-design telemetry + fill counts from a run_live_20
    audit log. READ-ONLY.

    Returns a dict keyed by config id (e.g. "V13-M2", "V13-M2-F") with:
        {same_bar_cost, sl_clamp_gap, n_opens}
    plus a "_total" key {n_opens, n_closes}.

    The cumulative lines are running totals; the LAST occurrence of each is
    authoritative (the value at run-end). SENT OPEN fills are tallied per
    config; SENT CLOSE lines carry no config id and are tallied at the total
    level only.
    """
    path = Path(log_path)
    same_bar: dict[str, float] = {}
    sl_clamp: dict[str, float] = {}
    n_opens: dict[str, int] = {}
    total = {"n_opens": 0, "n_closes": 0}

    if path.exists():
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = _SAME_BAR_RE.search(line)
                if m:
                    # last-wins: overwrite the whole per-config map from this line
                    for cid, val in _PAIR_RE.findall(m.group(1)):
                        same_bar[cid] = float(val)
                    continue
                m = _SL_CLAMP_RE.search(line)
                if m:
                    for cid, val in _PAIR_RE.findall(m.group(1)):
                        sl_clamp[cid] = float(val)
                    continue
                m = _SENT_OPEN_RE.search(line)
                if m:
                    cid = m.group(1)
                    n_opens[cid] = n_opens.get(cid, 0) + 1
                    total["n_opens"] += 1
                    continue
                if _SENT_CLOSE_RE.search(line):
                    total["n_closes"] += 1

    tel: dict[str, Any] = {"_total": total}
    for cid in set(same_bar) | set(sl_clamp) | set(n_opens):
        tel[cid] = {
            "same_bar_cost": same_bar.get(cid, 0.0),
            "sl_clamp_gap": sl_clamp.get(cid, 0.0),
            "n_opens": n_opens.get(cid, 0),
        }
    return tel


def build_residual_row(
    config_id: str,
    tel_row: dict[str, Any] | None,
    *,
    sim_expected_net: float | None,
    live_realized_net: float | None,
    min_live_fills: int = DEFAULT_MIN_LIVE_FILLS,
) -> dict[str, Any]:
    """One per-config residual row. By-design components are ALWAYS reported
    (they are observable from telemetry); the residual itself is gated on a
    meaningful live sample.

    status == "OK"                        -> residual/unexplained computed.
    status == "insufficient_live_sample"  -> residual/unexplained are None and
                                             `reason` explains why (no realized
                                             net, or too few live fills).
    """
    tel_row = tel_row or {}
    same_bar = float(tel_row.get("same_bar_cost", 0.0))
    sl_clamp = float(tel_row.get("sl_clamp_gap", 0.0))
    n_opens = int(tel_row.get("n_opens", 0))
    by_design_total = same_bar + sl_clamp

    row: dict[str, Any] = {
        "config_id": config_id,
        "sim_expected_net": sim_expected_net,
        "live_realized_net": live_realized_net,
        "n_live_opens": n_opens,
        "same_bar_cost": same_bar,
        "sl_clamp_gap": sl_clamp,
        "by_design_total": by_design_total,
        "residual": None,
        "unexplained": None,
        "status": "OK",
        "reason": None,
    }

    if live_realized_net is None or sim_expected_net is None:
        row["status"] = INSUFFICIENT_SAMPLE
        row["reason"] = "no realized live net available (audit log carries no per-config P&L)"
        return row
    if n_opens < min_live_fills:
        row["status"] = INSUFFICIENT_SAMPLE
        row["reason"] = f"only {n_opens} live fills < min_live_fills={min_live_fills}"
        return row

    residual = float(live_realized_net) - float(sim_expected_net)
    row["residual"] = residual
    row["unexplained"] = residual - by_design_total
    return row


def residual_report(
    telemetry: dict[str, Any],
    sim_expected_nets: dict[str, float],
    live_realized_nets: dict[str, float] | None = None,
    *,
    min_live_fills: int = DEFAULT_MIN_LIVE_FILLS,
) -> dict[str, Any]:
    """Assemble the full KPI artifact: per-config residual rows + a total.

    `sim_expected_nets` maps config id -> honest sim-expected net.
    `live_realized_nets` maps config id -> realized live net, or None if no
    realized-net series is available (the current thin-history case), in which
    case every row is `insufficient_live_sample` (but by-design components still
    surface). Deterministic: config ids are processed in sorted order.
    """
    live_realized_nets = live_realized_nets or {}
    rows: list[dict[str, Any]] = []
    for cid in sorted(sim_expected_nets):
        rows.append(build_residual_row(
            cid, telemetry.get(cid),
            sim_expected_net=sim_expected_nets.get(cid),
            live_realized_net=live_realized_nets.get(cid),
            min_live_fills=min_live_fills,
        ))

    ok_rows = [r for r in rows if r["status"] == "OK"]
    # The total's by-design components sum over the SAME rows the residual total
    # covers. When there is a meaningful sample (>=1 OK row) that is the OK rows,
    # so the by-design breakout stays consistent with the residual it explains.
    # When NO row is OK (thin history), we still surface the by-design components
    # observed across ALL telemetry-carrying rows -- the residual is None but the
    # observable costs are reported honestly.
    breakout_rows = ok_rows if ok_rows else rows
    total: dict[str, Any] = {
        "n_configs": len(rows),
        "n_ok": len(ok_rows),
        "same_bar_cost": round(sum(r["same_bar_cost"] for r in breakout_rows), 4),
        "sl_clamp_gap": round(sum(r["sl_clamp_gap"] for r in breakout_rows), 4),
        "by_design_total": round(sum(r["by_design_total"] for r in breakout_rows), 4),
    }
    if ok_rows:
        total["status"] = "OK"
        total["residual"] = round(sum(r["residual"] for r in ok_rows), 4)
        total["unexplained"] = round(sum(r["unexplained"] for r in ok_rows), 4)
    else:
        total["status"] = INSUFFICIENT_SAMPLE
        total["residual"] = None
        total["unexplained"] = None
        total["reason"] = ("no config has a meaningful live sample yet "
                           "(thin live history / no realized-net series)")

    return {
        "kpi": "sim_vs_live_net_residual",
        "governance_only": True,
        "min_live_fills": min_live_fills,
        "configs": rows,
        "total": total,
    }


# --------------------------------------------------------------------------
# Sim-expected side (honest pipeline). Reused, not reinvented: runs
# `simular_variant(..., live_fill_mode=True)` over the window and pairs fills
# the same way the batch loaders do (the honest-fills bound).
# --------------------------------------------------------------------------

def _resolve_config_kwargs(config_id: str) -> dict[str, Any] | None:
    """Map an audit-log config id (e.g. "V13-M2" or its "-F" fixed sibling) to
    its `simular_variant` kwargs from live_configs_20. Returns None if the id is
    not a known live config (so the sim side stays cleanly aligned -- unknown
    ids are reported, never guessed)."""
    from sentinel_engine.strategies.live_configs_20 import CONFIGS_20, _fixed

    base_id = config_id[:-2] if config_id.endswith("-F") else config_id
    base = next((c for c in CONFIGS_20 if c["id"] == base_id), None)
    if base is None:
        return None
    if config_id.endswith("-F"):
        return dict(_fixed(base, base["magic"])["kwargs"])
    return dict(base["kwargs"])


def _sim_expected_net(config_id: str, start: str, end: str,
                      lake_root: Path) -> float | None:
    """Honest sim-expected net for one config over [start, end). Reuses the
    parity checker's lake loader + `simular_variant(live_fill_mode=True)` and a
    minimal flat-spread fill pairing (0.5 XAU, entry crosses the spread), mirror
    of gen_variant_batch's convention. Returns None if the lake has no bars for
    the window (reported as insufficient, never a fabricated 0)."""
    from datetime import datetime, timezone

    from scripts.live.check_live_sim_parity import load_bars, sim_positions
    from sentinel_engine.strategies.emasar_variant import simular_variant

    kwargs = _resolve_config_kwargs(config_id)
    if kwargs is None:
        return None
    from sentinel_engine.strategies.live_configs_20 import CONFIGS_20
    base_id = config_id[:-2] if config_id.endswith("-F") else config_id
    base = next((c for c in CONFIGS_20 if c["id"] == base_id), None)
    if base is None:
        return None

    def _dt(s: str) -> datetime:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    symbol = kwargs.get("symbol", "XAUUSD")
    tf = base["tf"]
    bars = load_bars(lake_root, symbol, tf, _dt(start), _dt(end))
    if not bars:
        return None
    # direction-mask configs are not in the golive roster; skip if present.
    if base.get("direction_filter"):
        return None
    events = simular_variant(bars, **kwargs)
    positions = sim_positions(events, bars)
    spread = 0.5
    contract = 100.0
    lot = 0.10
    net = 0.0
    for p in positions:
        if not p["exits"]:
            continue
        # entry crosses the spread; exits at sim level (half-spread each side)
        px_in = p["price"] + (spread / 2 if p["side"] == "L" else -spread / 2)
        for e in p["exits"]:
            px_out = e["price"] - (spread / 2 if p["side"] == "L" else -spread / 2)
            d = (px_out - px_in) if p["side"] == "L" else (px_in - px_out)
            net += d * lot * contract
    return round(net, 4)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit-log", default=str(AUDIT_LOG),
                    help="run_live_20 audit log to parse (READ-ONLY)")
    ap.add_argument("--lake", default=str(ROOT / "data" / "lake"))
    ap.add_argument("--start", default=None, help="sim-expected window start (ISO)")
    ap.add_argument("--end", default=None, help="sim-expected window end (ISO, exclusive)")
    ap.add_argument("--config", default=None, help="print the residual row for one config")
    ap.add_argument("--min-live-fills", type=int, default=DEFAULT_MIN_LIVE_FILLS)
    ap.add_argument("--report-json", default=None, help="dump the full KPI artifact")
    args = ap.parse_args(argv)

    tel = parse_audit_telemetry(args.audit_log)
    config_ids = sorted(k for k in tel if k != "_total")

    sim_nets: dict[str, float] = {}
    if args.start and args.end:
        for cid in config_ids:
            net = _sim_expected_net(cid, args.start, args.end, Path(args.lake))
            if net is not None:
                sim_nets[cid] = net
    else:
        # no window -> sim-expected unavailable; still report by-design telemetry.
        for cid in config_ids:
            sim_nets[cid] = None  # type: ignore[assignment]

    # The audit log carries NO realized per-config P&L -> live_realized_nets is
    # None (the honest thin-history case): the KPI reports insufficient_live_sample
    # for the residual while still surfacing the by-design components.
    rep = residual_report(tel, sim_nets, live_realized_nets=None,
                          min_live_fills=args.min_live_fills)
    rep["_audit_log"] = str(args.audit_log)
    rep["_window"] = {"start": args.start, "end": args.end}

    if args.config:
        row = next((r for r in rep["configs"] if r["config_id"] == args.config), None)
        print(json.dumps(row, indent=2, sort_keys=True))
    else:
        print(json.dumps(rep["total"], indent=2, sort_keys=True))
        for r in rep["configs"]:
            print(f"  {r['config_id']:12s} status={r['status']:24s} "
                  f"same_bar={r['same_bar_cost']:+.4f} sl_clamp={r['sl_clamp_gap']:+.4f} "
                  f"residual={r['residual']}")

    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(rep, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nKPI artifact written to {args.report_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
