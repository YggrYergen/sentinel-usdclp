#!/usr/bin/env python3
"""gen_v10_completion.py -- Wave 5, Task V-10 honest completion (direction_mask).

Brings the V-10 SuperTrend-M15 `direction_mask` regime filter into the comparable
honest frame {IW, W1, W2, W3} as far as existing machinery cleanly allows, and
reports its standing under HONEST live-fill pricing vs the champion baseline.

What it does (offline; reuses `gen_oow_validation` primitives verbatim):
  * FRESH honest live-fill nets for V-10 on M5/M15 (W1/W2/W3) and, additively,
    M1/M2 -- via the SAME path `gen_w2_audit._fresh_honest_net` uses:
        config_kwargs(cfg, win) with direction_mask rebuilt by _mask_for(tf,win)
        -> live_fill_mode=True -> run_variant_window -> compute_metrics_window.
  * Lake-feasibility gating (`lake_feasible`): M1 lake starts 2026-03, M2 2025-12,
    so M1 on W2/W3 and M2 on W3 have no bars -> SKIPPED + documented, NEVER faked.
  * IW: reuses the persisted batch5 screening rows (sim-report-emasar-v10-m*) with
    an explicit fidelity caveat (screening, not the live-fill honest path).
  * A per-(TF,window) honest coverage table vs the champion (ss-*) baseline,
    DSR-aware (honest trial count stated; no faked significance).

ADDITIVE-ONLY: mutates no existing CONFIGS entry and no research.db run row. Reads
research.db read-only (mode=ro). This script writes only its --report-md markdown.

Usage:
    python scripts/report/gen_v10_completion.py --report-md docs/superpowers/research/2026-07-20-wave5-v10-completion.md
    python scripts/report/gen_v10_completion.py --report-md - --skip-fresh   # table only, no sim
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.report import gen_oow_validation as ov  # noqa: E402

DB_PATH = _REPO_ROOT / "data" / "research.db"

# V-10 cells to bring honest, per TF. M5/M15 exist as screening OOW rows already;
# M1/M2 are the additive extension. IW is reused from screening (batch5).
V10_TFS = ["M1", "M2", "M5", "M15"]
V10_WINDOWS = ["W1", "W2", "W3"]

# Champion baseline = the ss-* family (leads the comparable league on every
# window). Persisted OOW champion nets are SCREENING fidelity -- so the V-10
# honest-net-vs-champion comparison is directional, with a fidelity caveat.
_CHAMPION_CFG = "ss"  # ss-m5 / ss-m15 / ss-m2


# ---------------------------------------------------------------------------
# Lake feasibility: a (TF, window) is feasible only if EVERY lake month the
# window needs is present on disk (strict -- a missing warmup month means the
# SuperTrend/ATR seed is incomplete, so we do not run a contaminated sim).
# ---------------------------------------------------------------------------
def lake_feasible(tf: str, win_key: str) -> bool:
    win = ov.WINDOWS[win_key]
    for month in win["lake_months"]:
        path = ov.LAKE_ROOT / ov.SYMBOL / tf / f"{month}.parquet"
        if not path.exists():
            return False
    return True


# ---------------------------------------------------------------------------
# Fresh honest live-fill net for one V-10 (TF, window) cell. Reuses the exact
# gen_oow_validation machinery (identical to gen_w2_audit._fresh_honest_net).
# ---------------------------------------------------------------------------
def fresh_honest_net(cfg_id: str, tf: str, win_key: str) -> dict[str, Any]:
    kwargs = ov.config_kwargs(cfg_id, win_key)   # rebuilds direction_mask array
    kwargs["live_fill_mode"] = True              # 0.5 spread applied at fill
    trades = ov.run_variant_window(tf, win_key, kwargs)
    m = ov.compute_metrics_window(trades, win_key)
    return {"net": round(float(m["net"]), 2), "trades": m["trades"],
            "pf": m["pf"], "wr": m["wr"], "maxdd": m["maxdd"]}


# ---------------------------------------------------------------------------
# Persisted reads (research.db, read-only).
# ---------------------------------------------------------------------------
def _ro_conn() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def persisted_nets() -> dict[str, dict[str, Any]]:
    """run_id -> {net, trades, fidelity} for all V-10 and champion OOW/IW rows."""
    out: dict[str, dict[str, Any]] = {}
    if not DB_PATH.exists():
        return out
    conn = _ro_conn()
    try:
        for rid, net, trades, fidelity in conn.execute(
            "SELECT run_id, net, trades, fidelity FROM run "
            "WHERE run_id LIKE 'sim-report-emasar-%'"
        ):
            out[rid] = {"net": net, "trades": trades, "fidelity": fidelity}
    finally:
        conn.close()
    return out


def _tf_suffix(tf: str) -> str:
    return tf.lower()


def _oow_runid(cfg: str, win_key: str, tf: str) -> str:
    tag = ov.WINDOWS[win_key]["run_tag"]  # oow1/oow2/oow3
    return f"sim-report-emasar-{tag}-{cfg}-{_tf_suffix(tf)}"


def _iw_runid(cfg: str, tf: str) -> str:
    return f"sim-report-emasar-{cfg}-{_tf_suffix(tf)}"


# ---------------------------------------------------------------------------
# Coverage matrix build.
# ---------------------------------------------------------------------------
def build_matrix(run_fresh: bool = True) -> dict[str, Any]:
    persisted = persisted_nets()
    cells: list[dict[str, Any]] = []
    ran, reused, skipped = 0, 0, 0

    for tf in V10_TFS:
        cfg_id = f"v10-{_tf_suffix(tf)}"
        # --- IW (screening, reused) ---
        iw_rid = _iw_runid("v10", tf)
        iw = persisted.get(iw_rid)
        champ_iw = ov.IW_NET.get(f"ss-{_tf_suffix(tf)}")
        cells.append({
            "tf": tf, "window": "IW", "cfg": cfg_id,
            "net": iw["net"] if iw else None,
            "fidelity": "screening (reused)" if iw else "MISSING",
            "source": "reused" if iw else "gap",
            "champion": champ_iw,
            "beats_champion": (iw["net"] > champ_iw) if (iw and champ_iw is not None) else None,
            "note": "IW rows are screening-fidelity, not the live-fill honest path.",
        })
        if iw:
            reused += 1

        # --- W1/W2/W3 ---
        for win_key in V10_WINDOWS:
            champ_rid = _oow_runid(_CHAMPION_CFG, win_key, tf)
            champ = persisted.get(champ_rid)
            champ_net = champ["net"] if champ else None

            if not lake_feasible(tf, win_key):
                missing = [mo for mo in ov.WINDOWS[win_key]["lake_months"]
                           if not (ov.LAKE_ROOT / ov.SYMBOL / tf / f"{mo}.parquet").exists()]
                cells.append({
                    "tf": tf, "window": win_key, "cfg": cfg_id,
                    "net": None, "fidelity": "n/a", "source": "skipped-no-lake",
                    "champion": champ_net, "beats_champion": None,
                    "note": f"{tf} lake missing month(s) {'/'.join(missing)} needed for "
                            f"{win_key} (warmup+window) -- incomplete SuperTrend/ATR seed, "
                            "SKIPPED, not fabricated.",
                })
                skipped += 1
                continue

            if run_fresh:
                r = fresh_honest_net(cfg_id, tf, win_key)
                net = r["net"]
                fidelity = "honest live-fill (ran)"
                source = "ran"
                ran += 1
            else:
                # Fall back to persisted screening OOW row if present (M5/M15 only).
                p = persisted.get(_oow_runid("v10", win_key, tf))
                net = p["net"] if p else None
                fidelity = "screening (reused)" if p else "MISSING"
                source = "reused" if p else "gap"
                if p:
                    reused += 1

            cells.append({
                "tf": tf, "window": win_key, "cfg": cfg_id,
                "net": net, "fidelity": fidelity, "source": source,
                "champion": champ_net,
                "beats_champion": (net > champ_net) if (net is not None and champ_net is not None) else None,
                "note": "champion (ss-*) net is screening -- comparison is directional.",
            })

    return {"cells": cells, "ran": ran, "reused": reused, "skipped": skipped}


# ---------------------------------------------------------------------------
# DSR: honest trial count over the V-10 honest-net family.
#
# The Bailey-Lopez de Prado deflated Sharpe (`deflated_sharpe_ratio(returns,
# n_trials)`) deflates a WINNING trial's return series by the number of trials
# searched. V-10 produces NO champion-beating winner (see verdict) -- so there
# is no winner series to deflate. We therefore report the honest trial count and
# state plainly that DSR does not apply (no selection to correct for), rather
# than manufacture a Sharpe from net-dispersion. This is the honest read.
# ---------------------------------------------------------------------------
def dsr_summary(cells: list[dict[str, Any]]) -> dict[str, Any]:
    honest = [c for c in cells if c["source"] == "ran" and c["net"] is not None]
    n_trials = len(honest)
    beaters = [c for c in cells if c["beats_champion"]]
    if not beaters:
        return {
            "n_trials": n_trials, "dsr": None, "applicable": False,
            "note": "DSR not applicable: V-10 selects NO champion-beating cell, so "
                    "there is no winning trial series to deflate. Honest live-fill "
                    f"trial count = {n_trials} (M1/M2/M5/M15 x feasible windows).",
        }
    # If a beater ever emerges, DSR needs its per-trade return series (not stored
    # in this matrix) -- flag it rather than fake a number.
    return {
        "n_trials": n_trials, "dsr": None, "applicable": True,
        "note": f"{len(beaters)} champion-beating cell(s) exist; a proper DSR needs "
                "each winner's per-trade return series (re-run with trade retention). "
                f"Honest trial count = {n_trials}.",
    }


# ---------------------------------------------------------------------------
# Markdown report.
# ---------------------------------------------------------------------------
def render_md(matrix: dict[str, Any]) -> str:
    cells = matrix["cells"]
    lines: list[str] = []
    lines.append("# Wave-5 · V-10 direction_mask honest completion\n")
    lines.append("_Generated by `scripts/report/gen_v10_completion.py`. "
                 "Additive-only; research.db read `mode=ro`._\n")
    lines.append(f"- ran (honest live-fill): **{matrix['ran']}** cells  ")
    lines.append(f"- reused (persisted): **{matrix['reused']}** cells  ")
    lines.append(f"- skipped (no lake, documented): **{matrix['skipped']}** cells\n")

    lines.append("## Per-(TF, window) coverage vs champion (ss-*)\n")
    lines.append("| TF | Window | V-10 net | fidelity | src | champion net | V-10 beats champ? | note |")
    lines.append("|----|--------|---------:|----------|-----|-------------:|:-----------------:|------|")
    for c in cells:
        net = "—" if c["net"] is None else f"{c['net']:,.1f}"
        champ = "—" if c["champion"] is None else f"{c['champion']:,.1f}"
        beats = {True: "YES", False: "no", None: "—"}[c["beats_champion"]]
        lines.append(
            f"| {c['tf']} | {c['window']} | {net} | {c['fidelity']} | {c['source']} "
            f"| {champ} | {beats} | {c['note']} |")
    lines.append("")

    dsr = dsr_summary(cells)
    lines.append("## DSR (honest trial count)\n")
    lines.append(f"- honest live-fill trials (n): **{dsr['n_trials']}**")
    lines.append(f"- DSR applicable: {dsr['applicable']}")
    lines.append(f"- {dsr['note']}\n")

    # Verdict.
    beat_any = any(c["beats_champion"] for c in cells if c["beats_champion"])
    lines.append("## Verdict\n")
    if beat_any:
        winners = [f"{c['tf']}/{c['window']}" for c in cells if c["beats_champion"]]
        lines.append(f"V-10 beats the champion on: {', '.join(winners)} "
                     "(directional -- champion nets are screening).\n")
    else:
        lines.append("**V-10 does NOT beat the champion (ss-*) on any comparable cell** "
                     "under honest live-fill pricing. It loses on every (TF, window) where "
                     "both nets exist -- consistent with the batch5 screening finding "
                     "(\"MIXED, M1-specialist; loses to champion on all 4 TFs\"). The "
                     "direction_mask regime filter suppresses too much of the ladder's edge "
                     "to overtake the always-on champion.\n")

    lines.append("## Honest gaps (no fabrication)\n")
    for c in cells:
        if c["source"].startswith("skipped"):
            lines.append(f"- **{c['tf']}/{c['window']}**: {c['note']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-md", default="-",
                    help="output markdown path, or '-' for stdout")
    ap.add_argument("--skip-fresh", action="store_true",
                    help="do not run live-fill sims; reuse persisted screening nets only")
    args = ap.parse_args(argv)

    matrix = build_matrix(run_fresh=not args.skip_fresh)
    md = render_md(matrix)

    if args.report_md == "-":
        sys.stdout.write(md)
    else:
        out = Path(args.report_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"wrote {out}  (ran={matrix['ran']} reused={matrix['reused']} "
              f"skipped={matrix['skipped']})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
