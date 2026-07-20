r"""scripts/report/gen_mfe_capture.py -- PX-T4 (PATIENT-EXIT program):
MFE-capture% + give-back USD, a REPORT-ONLY per-trade metrics module.

WHAT IT COMPUTES
----------------
The PATIENT-EXIT success criterion (user-ratified) is: a config KEEPS iff it
RAISES MFE-capture% (fixes premature-exit / Problem B) AND LOWERS give-back USD
(fixes give-back / Problem A) WITHOUT reducing net. Net PnL alone cannot
separate Problem A from Problem B -- this module computes the two per-trade
metrics that can, for the PX-T6 backtest report to consume.

Given a config (id + `simular_variant` kwargs, tf) and market bars, for each
paired ficha over its held-bar span [entry_bar_idx, exit_bar_idx] (only bars
WITHIN the span -- no look-ahead), against the LAKE bars' highs/lows:

    entry          fill-in price (spread-at-fill via the _B1 primitives).
    booked         favourable-direction realized move in PRICE units:
                     (px_out - entry) for a long, (entry - px_out) for a short.
    MFE            max favourable excursion (price): max(span high) - entry
                     (long) / entry - min(span low) (short).
    MAE            max adverse excursion (price): entry - min(span low) (long) /
                     max(span high) - entry (short).
    mfe_capture    booked / MFE when MFE > 0 else 0.0; clamped to [0.0, 1.0]
                     (near 1.0 = captured almost the whole swing; low = premature
                     exit). A trade that booked a loss -- or gave back everything --
                     on a swing that had upside counts as 0.0 capture (the lower
                     clamp), not a large negative. Never divides by zero.
    giveback       max(MFE - booked, 0.0) in price units (>=0 for a trade that
                     ever went favourable), converted to USD via the _B1 pnl
                     scaling (lot 0.10, contract 100).

Aggregated per config: trade count; trade-count-weighted MEAN and MEDIAN
mfe_capture; MEAN give-back USD/trade and TOTAL give-back USD; and the pooled
honest `net` (the same _B1 pnl the league uses, so it matches exactly).

MFE/MAE SOURCE (brief 2): the engine's `simular_variant` does NOT expose a
per-ficha `f.max_fav` at each ficha's individual exit (its `return_state`
snapshot only carries `max_fav` for fichas STILL OPEN at the last bar). So MFE
and MAE are RECOMPUTED here from the span's bar highs/lows -- span-bounded, so
no look-ahead is possible by construction.

REPORT-ONLY / ISOLATION
-----------------------
This NEVER writes a run/score/DSR, never imports the registry, never opens
`data/research.db`, never trades. Same governance stance as
`scripts/report/gen_residual_kpi.py`. It writes ONLY its own output file (a NEW
patient-exit name, defaulting under docs/superpowers/research/), given as a CLI
flag / function argument. Deterministic: identical input -> byte-identical JSON
(sorted keys + stable float rounding; no wall-clock, RNG, or network).

REUSE
-----
* pairing: `sim_positions` from `scripts/live/check_live_sim_parity.py` (the
  ENTRY->EXIT-with-bar-index pairing shape), NOT a re-implementation of the
  engine.
* fill/pnl scaling: the verbatim `_entry_fill`/`_exit_fill`/`_pnl` primitives +
  `LOT`/`CONTRACT_SIZE`/`SPREAD`/`SYMBOL` from `gen_variant_batch1.py`, loaded
  the SAME importlib way `gen_honest_sweep.py` / `gen_livefill_bound.py` do -- so
  the give-back USD and net use the exact league scaling, never a hardcode.

USAGE
    python -m scripts.report.gen_mfe_capture --config SS-M15 \
        --start 2026-07-13 --end 2026-07-14 \
        [--lake data/lake] [--out-json ...] [--out-md ...]
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import sys
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.live.check_live_sim_parity import sim_positions  # noqa: E402
from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402

# Default output name: a NEW patient-exit file (never an existing research file).
DEFAULT_OUT_JSON = ROOT / "docs" / "superpowers" / "research" / "2026-07-20-patient-exit-mfe.json"
DEFAULT_OUT_MD = ROOT / "docs" / "superpowers" / "research" / "2026-07-20-patient-exit-mfe.md"

# Stable rounding for deterministic, byte-identical JSON output.
_PRICE_ND = 6
_USD_ND = 4
_CAP_ND = 6


# ---------------------------------------------------------------------------
# Reuse gen_variant_batch1's fill/pnl primitives via the SAME importlib pattern
# gen_honest_sweep / gen_livefill_bound use -- no spread/pnl math duplicated.
# ---------------------------------------------------------------------------
def _load_module(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_B1 = _load_module("gen_variant_batch1", "scripts/report/gen_variant_batch1.py")

SYMBOL = _B1.SYMBOL          # "XAUUSD"
SPREAD = _B1.SPREAD          # 0.5 flat, at fill
LOT = _B1.LOT                # 0.10
CONTRACT_SIZE = _B1.CONTRACT_SIZE  # 100.0

# UI side label the _B1._pnl primitive expects ("LONG"/"SHORT").
_SIDE_UI = {"L": "LONG", "S": "SHORT"}


# ---------------------------------------------------------------------------
# Pairing: engine events -> per-ficha paired trades (entry/exit bar indices).
# Reuses sim_positions' ENTRY->EXIT grouping; each exit becomes one ficha trade.
# ---------------------------------------------------------------------------
def paired_fichas(bars: list[dict[str, Any]], kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    """Run `simular_variant(live_fill_mode=True, **kwargs)` on `bars` and pair
    each ficha's ENTRY to its EXIT. Returns one dict per paired ficha:
        {side, ficha, entry_bar_idx, exit_bar_idx, entry_price, exit_price,
         exit_reason}
    entry_price / exit_price are the raw BID event prices; spread-at-fill is
    applied inside `ficha_metrics` (via the _B1 primitives)."""
    kw = {**kwargs, "live_fill_mode": True}
    events = simular_variant(bars, symbol=SYMBOL, **kw)
    positions = sim_positions(events, bars)

    fichas: list[dict[str, Any]] = []
    for p in positions:
        for e in p["exits"]:
            fichas.append({
                "side": p["side"],  # "L" / "S"
                # Assumption: exit events always carry a ficha tag; the "F1"
                # default is a defensive guard against a missing/empty tag, not
                # a semantic choice about which ficha this exit belongs to.
                "ficha": e.get("ficha") or "F1",
                "entry_bar_idx": p["bar_idx"],
                "exit_bar_idx": e["bar_idx"],
                "entry_price": p["price"],
                "exit_price": e["price"],
                "exit_reason": e["motivo"],
            })
    return fichas


# ---------------------------------------------------------------------------
# Per-ficha metric math (pure; no DB handle). Span-bounded highs/lows only.
# ---------------------------------------------------------------------------
def ficha_metrics(bars: list[dict[str, Any]], ficha: dict[str, Any]) -> dict[str, Any]:
    """Compute the per-trade metrics for one paired ficha over its held-bar
    span [entry_bar_idx, exit_bar_idx] (inclusive; ONLY bars within the span --
    no look-ahead). Returns entry/booked/mfe/mae/mfe_capture/giveback_price/
    giveback_usd plus pnl_usd (the league-scaled realized pnl)."""
    side = ficha["side"]
    lo_idx = ficha["entry_bar_idx"]
    hi_idx = ficha["exit_bar_idx"]
    # Defensive but deterministic span clamp (exit should be >= entry).
    if hi_idx < lo_idx:
        lo_idx, hi_idx = hi_idx, lo_idx
    span = bars[lo_idx:hi_idx + 1]

    # Spread-at-fill via the _B1 primitives (long buys ask / short sells bid on
    # entry; long sells bid / short buys ask on exit) -- identical to the league.
    entry = _B1._entry_fill(side, ficha["entry_price"])
    px_out = _B1._exit_fill(side, ficha["exit_price"])

    span_high = max(b["high"] for b in span)
    span_low = min(b["low"] for b in span)

    if side == "L":
        booked = px_out - entry
        mfe = span_high - entry
        mae = entry - span_low
    else:  # short mirror
        booked = entry - px_out
        mfe = entry - span_low
        mae = span_high - entry

    # An excursion is never negative: a span that never went favourable/adverse
    # relative to the fill has zero MFE/MAE, not a negative one.
    mfe = max(mfe, 0.0)
    mae = max(mae, 0.0)

    if mfe > 0.0:
        mfe_capture = booked / mfe
        if mfe_capture > 1.0:
            mfe_capture = 1.0  # clamp the UPPER end (booked can't beat the swing)
        elif mfe_capture < 0.0:
            mfe_capture = 0.0  # clamp the LOWER end: a booked loss on a swing that
            # had upside is 0.0 capture (not a large negative that tail-dominates
            # the mean)
    else:
        mfe_capture = 0.0  # MFE == 0 -> no swing to capture; never divide by zero

    giveback_price = max(mfe - booked, 0.0)
    giveback_usd = giveback_price * LOT * CONTRACT_SIZE
    # Two rounding regimes are INTENTIONAL: pnl_usd is scored on the league's
    # 2-dp-rounded fill prices so it matches _B1 (and thus the honest league net)
    # EXACTLY; booked/giveback use the UNROUNDED prices because they are
    # diagnostic excursion metrics, not league-net contributors.
    pnl_usd = _B1._pnl(_SIDE_UI[side], round(entry, 2), round(px_out, 2))

    return {
        "side": _SIDE_UI[side],
        "ficha": ficha["ficha"],
        "exit_reason": ficha["exit_reason"],
        "entry_bar_idx": lo_idx,
        "exit_bar_idx": hi_idx,
        "entry": round(entry, _PRICE_ND),
        "px_out": round(px_out, _PRICE_ND),
        "booked": round(booked, _PRICE_ND),
        "mfe": round(mfe, _PRICE_ND),
        "mae": round(mae, _PRICE_ND),
        "mfe_capture": round(mfe_capture, _CAP_ND),
        "giveback_price": round(giveback_price, _PRICE_ND),
        "giveback_usd": round(giveback_usd, _USD_ND),
        "pnl_usd": pnl_usd,
    }


# ---------------------------------------------------------------------------
# Per-config aggregation.
# ---------------------------------------------------------------------------
def compute_config_metrics(
    config_id: str,
    kwargs: dict[str, Any],
    bars: list[dict[str, Any]],
    *,
    tf: str = "M15",
) -> dict[str, Any]:
    """Full per-config report: per-ficha rows + aggregates (trade count;
    trade-count-weighted MEAN + MEDIAN mfe_capture; MEAN give-back USD/trade +
    TOTAL give-back USD; pooled honest `net`). Pure/report-only: takes bars +
    kwargs, returns a dict -- no DB handle."""
    fichas = paired_fichas(bars, kwargs)
    trades = [ficha_metrics(bars, f) for f in fichas]

    n = len(trades)
    caps = [t["mfe_capture"] for t in trades]
    gbs = [t["giveback_usd"] for t in trades]
    net = round(sum(t["pnl_usd"] for t in trades), _USD_ND)

    mean_cap = round(sum(caps) / n, _CAP_ND) if n else None
    median_cap = round(median(caps), _CAP_ND) if n else None
    total_gb = round(sum(gbs), _USD_ND)
    mean_gb = round(total_gb / n, _USD_ND) if n else 0.0

    return {
        "config_id": config_id,
        "tf": tf,
        "n_trades": n,
        "mean_mfe_capture": mean_cap,
        "median_mfe_capture": median_cap,
        "mean_giveback_usd": mean_gb,
        "total_giveback_usd": total_gb,
        "net": net,
        "trades": trades,
    }


# ---------------------------------------------------------------------------
# Output writers (only touch the given output path).
# ---------------------------------------------------------------------------
def _artifact(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "report": "patient_exit_mfe_capture",
        "report_only": True,
        "cost_model": "flat0.5",
        "lot": LOT,
        "contract_size": CONTRACT_SIZE,
        "symbol": SYMBOL,
        "configs": reports,
    }


def write_json(reports: list[dict[str, Any]], out_path: Path | str) -> Path:
    """Write the machine-readable JSON artifact (deterministic: sorted keys,
    stable float rounding). Touches ONLY `out_path`."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(_artifact(reports), indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return out


def _fmt(v: Any) -> str:
    return "-" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))


def write_markdown(reports: list[dict[str, Any]], out_path: Path | str) -> Path:
    """Write the human-readable markdown table. Touches ONLY `out_path`."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PATIENT-EXIT -- MFE-capture% + give-back report",
        "",
        "Report-only (PX-T4). MFE/MAE recomputed from span bar highs/lows "
        "(no look-ahead); give-back USD + net use the _B1 scaling "
        f"(lot {LOT}, contract {CONTRACT_SIZE}).",
        "",
        "| config | tf | trades | mean mfe_capture | median mfe_capture "
        "| mean giveback USD | total giveback USD | net USD |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(reports, key=lambda x: x["config_id"]):
        lines.append(
            f"| {r['config_id']} | {r['tf']} | {r['n_trades']} "
            f"| {_fmt(r['mean_mfe_capture'])} | {_fmt(r['median_mfe_capture'])} "
            f"| {_fmt(r['mean_giveback_usd'])} | {_fmt(r['total_giveback_usd'])} "
            f"| {_fmt(r['net'])} |"
        )
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# CLI (loads real lake bars for named live configs; report-only).
# ---------------------------------------------------------------------------
def _resolve_configs(config_id: str) -> list[dict[str, Any]]:
    from sentinel_engine.strategies.live_configs_20 import CONFIGS_20

    if config_id.lower() == "all":
        return list(CONFIGS_20)
    hits = [c for c in CONFIGS_20 if c["id"] == config_id]
    return hits


def main(argv: list[str] | None = None) -> int:
    from datetime import datetime, timezone

    from scripts.live.check_live_sim_parity import load_bars

    ap = argparse.ArgumentParser(description="PX-T4 MFE-capture% + give-back report (report-only).")
    ap.add_argument("--config", required=True, help="live config id (e.g. SS-M15) or 'all'")
    ap.add_argument("--start", required=True, help="ISO window start")
    ap.add_argument("--end", required=True, help="ISO window end (exclusive)")
    ap.add_argument("--lake", default=str(ROOT / "data" / "lake"))
    ap.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    ap.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    args = ap.parse_args(argv)

    def _dt(s: str) -> datetime:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    configs = _resolve_configs(args.config)
    if not configs:
        print(f"unknown config id: {args.config}", file=sys.stderr)
        return 2

    reports: list[dict[str, Any]] = []
    for cfg in configs:
        symbol = cfg["kwargs"].get("symbol", SYMBOL)
        bars = load_bars(Path(args.lake), symbol, cfg["tf"], _dt(args.start), _dt(args.end))
        if not bars:
            print(f"== {cfg['id']} == NO BARS in lake for {cfg['tf']} "
                  f"{args.start}..{args.end}", file=sys.stderr)
            continue
        rep = compute_config_metrics(cfg["id"], dict(cfg["kwargs"]), bars, tf=cfg["tf"])
        reports.append(rep)
        print(f"{rep['config_id']:12s} trades={rep['n_trades']:4d} "
              f"mean_cap={_fmt(rep['mean_mfe_capture'])} "
              f"median_cap={_fmt(rep['median_mfe_capture'])} "
              f"total_giveback=${_fmt(rep['total_giveback_usd'])} "
              f"net=${_fmt(rep['net'])}")

    write_json(reports, args.out_json)
    write_markdown(reports, args.out_md)
    print(f"\nJSON -> {args.out_json}\nMD   -> {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
