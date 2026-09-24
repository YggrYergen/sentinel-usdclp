r"""scripts/live/check_dryrun_intent_parity.py -- DRY-RUN intent parity
checker (SENTINEL, 2026-07-14 addendum).

`scripts/live/run_live_20.py` runs in DRY-RUN against MT5 DEMO: each cycle,
per config, it recomputes desired state via `simular_variant` on LIVE MT5
rates and LOGS intended actions (never sends anything). Because dry-run sends
nothing, deal-level parity (like `check_live_sim_parity.py`) is impossible.
This module instead checks INTENT-level parity: do the intents logged from
LIVE MT5 rates match what the sim would decide on the Parquet LAKE bars for
the same bar timestamps? Any mismatch flags a data-feed or timing gap between
MT5 rates and the lake ingester.

READ-ONLY: never imports MetaTrader5, never sends orders; only reads the
audit log (text) and the lake (parquet).

Usage:
    python -m scripts.live.check_dryrun_intent_parity \
        --log scripts/live/run_live_20.audit.log [--configs all|ID,ID] \
        [--lake data/lake] [--json out.json]

Exit code: 0 = no HARD findings; 1 = at least one HARD finding;
           2 = usage/data error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.live.check_live_sim_parity import load_bars  # noqa: E402 -- reuse the lake loader
from sentinel_engine.strategies.emasar_variant import simular_variant  # noqa: E402
from sentinel_engine.strategies.live_configs_20 import CONFIGS_20  # noqa: E402

TF_SECONDS = {"M1": 60, "M2": 120, "M5": 300, "M15": 900}
DEFAULT_WINDOW = 10_000  # mirrors run_live_20.DEFAULT_WINDOW

CONFIG_BY_ID: dict[str, dict[str, Any]] = {c["id"]: c for c in CONFIGS_20}

# --------------------------------------------------------------------------
# Log line formats we parse:
#   "2026-07-13 22:25:11,372 INFO [SS-M2] bar=2026-07-13T22:22:00+00:00 actions: none"
#   "2026-07-13 22:25:11,372 INFO [SS-M2] bar=2026-07-13T22:22:00+00:00 actions: OPEN/F1, MODIFY/F2"
#   "2026-07-13 22:25:11,039 INFO === cycle 2026-07-14T02:25:11.039742+00:00 | guard OK | kill=False | dry_run=True ==="
# Per-action detail lines (kept only for context; not required to derive the
# intent, which is already summarized on the "actions:" line as kind/ficha
# pairs) look like:
#   "  [DRY-RUN would OPEN] SS-M2 F1 magic=720011 side=L vol=0.01 sl=1234.5 -- reason"
# --------------------------------------------------------------------------

_CYCLE_RE = re.compile(
    r"^(?P<ts>\S+ \S+),\d+ \S+ === cycle (?P<iso>\S+) \|")
_ACTIONS_RE = re.compile(
    r"^(?P<ts>\S+ \S+),\d+ \S+ \[(?P<cfg>[^\]]+)\] bar=(?P<bar_iso>\S+) "
    r"actions: (?P<actions>.*)$")


@dataclass
class ParsedIntent:
    kind: str          # OPEN | CLOSE | MODIFY | NOOP | ... | "none" marker skipped
    ficha: str          # F1/F2/F3


@dataclass
class ParsedCycle:
    line_no: int
    log_ts: str          # raw log timestamp string (wall clock)
    config_id: str
    bar_t: int            # epoch seconds of the last-closed bar the executor saw
    intents: list[ParsedIntent] = field(default_factory=list)

    @property
    def has_actions(self) -> bool:
        return bool(self.intents)


@dataclass
class ParseStats:
    total_lines: int = 0
    cycles_parsed: int = 0
    parse_skipped: int = 0


def _parse_bar_iso(bar_iso: str) -> int | None:
    try:
        dt = datetime.fromisoformat(bar_iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def parse_action_list(actions_str: str) -> list[ParsedIntent]:
    """Parse the 'actions: KIND/FICHA, KIND/FICHA' (or 'none') tail of an
    executor summary line into ParsedIntent objects. Tolerant: any token that
    doesn't match 'KIND/FICHA' is skipped (never raises)."""
    actions_str = actions_str.strip()
    if not actions_str or actions_str == "none":
        return []
    out: list[ParsedIntent] = []
    for tok in actions_str.split(","):
        tok = tok.strip()
        if not tok or "/" not in tok:
            continue
        kind, _, ficha = tok.partition("/")
        kind, ficha = kind.strip(), ficha.strip()
        if not kind or not ficha:
            continue
        out.append(ParsedIntent(kind=kind, ficha=ficha))
    return out


def parse_audit_log(text: str) -> tuple[list[ParsedCycle], ParseStats]:
    """Parse the audit log text into a list of ParsedCycle (one per
    '[CONFIG-ID] bar=... actions: ...' line) plus stats. Never raises;
    unparseable lines are counted in `parse_skipped`."""
    stats = ParseStats()
    cycles: list[ParsedCycle] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        stats.total_lines += 1
        if _CYCLE_RE.match(line):
            continue  # cycle-header lines carry no per-config intent info
        m = _ACTIONS_RE.match(line)
        if not m:
            # any other line (DRY-RUN detail lines, warnings, connect banner,
            # etc.) is not a parse target for this parser; only count as
            # skipped if it looks like it SHOULD have matched (has "actions:"
            # in it) -- otherwise it's just log noise we intentionally ignore.
            if "actions:" in line:
                stats.parse_skipped += 1
            continue
        bar_t = _parse_bar_iso(m.group("bar_iso"))
        if bar_t is None:
            stats.parse_skipped += 1
            continue
        intents = parse_action_list(m.group("actions"))
        cycles.append(ParsedCycle(
            line_no=i, log_ts=m.group("ts"), config_id=m.group("cfg"),
            bar_t=bar_t, intents=intents))
        stats.cycles_parsed += 1
    return cycles, stats


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

HARD_KINDS = {"SIGNAL_MISMATCH", "MISSED_SIGNAL", "STATE_MISMATCH"}
NON_HARD_KINDS = {"BAR_MISSING_IN_LAKE", "BAR_LAG", "BAR_EDGE_LAG"}


@dataclass
class Finding:
    kind: str
    hard: bool
    config_id: str
    cycle_line_no: int
    bar_t: int
    detail: str


@dataclass
class ConfigResult:
    config_id: str
    cycles: int = 0
    bars_checked: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def hard_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.hard]

    def count_by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.kind] = out.get(f.kind, 0) + 1
        return out


def _direction_mask_for(bars: list[dict[str, Any]]) -> list[int]:
    from scripts.report.gen_variant_batch5 import compute_direction_mask
    return compute_direction_mask(bars)


def diff_cycle(cycle: ParsedCycle, lake_bars: list[dict[str, Any]],
               cfg: dict[str, Any], tf_s: int) -> list[Finding]:
    """Compare one parsed cycle's logged intents against the lake-recomputed
    desired state at the same bar time. Pure function -- no I/O."""
    findings: list[Finding] = []

    bar_times = [b["t"] for b in lake_bars]
    # (a) BAR_MISSING_IN_LAKE / BAR_EDGE_LAG / BAR_LAG: does the lake have a
    # bar at exactly cycle.bar_t? If not, find the last lake bar <= cycle.bar_t
    # and report the gap (non-hard in all cases).
    exact = cycle.bar_t in bar_times
    if not exact:
        earlier = [t for t in bar_times if t <= cycle.bar_t]
        if not earlier:
            findings.append(Finding(
                "BAR_MISSING_IN_LAKE", False, cycle.config_id, cycle.line_no,
                cycle.bar_t,
                f"executor bar t={cycle.bar_t} absent from lake; no earlier "
                "lake bar available either"))
            return findings
        last_lake_t = max(earlier)
        lake_tail_t = max(bar_times) if bar_times else None
        if lake_tail_t is not None and cycle.bar_t > lake_tail_t:
            # Executor's cycle bar is strictly newer than the last available
            # lake bar for this config/TF: this is lake-freshness edge lag,
            # not a signal divergence. Do NOT recompute/emit SIGNAL_MISMATCH,
            # MISSED_SIGNAL, or STATE_MISMATCH for this cycle.
            lag = cycle.bar_t - lake_tail_t
            findings.append(Finding(
                "BAR_EDGE_LAG", False, cycle.config_id, cycle.line_no,
                cycle.bar_t,
                f"executor bar t={cycle.bar_t} is newer than lake last bar "
                f"t={lake_tail_t} (lag={lag}s, {lag / tf_s:.2f} bars); "
                "skipping recompute (lake-freshness edge lag)"))
            return findings
        gap = cycle.bar_t - last_lake_t
        findings.append(Finding(
            "BAR_LAG", False, cycle.config_id, cycle.line_no, cycle.bar_t,
            f"lake last bar <= cycle time is t={last_lake_t}, executor bar "
            f"t={cycle.bar_t} (gap={gap}s, {gap / tf_s:.2f} bars)"))
        # still attempt the recompute against the last available lake bar so
        # we can surface any additional STATE/SIGNAL mismatches.
        truncate_t = last_lake_t
    else:
        truncate_t = cycle.bar_t

    bars_upto = [b for b in lake_bars if b["t"] <= truncate_t]
    if not bars_upto:
        return findings

    # A "NEW entry on the last closed bar" is detected via simular_variant's
    # own event stream: an ENTRY_* event at the last bar index.
    last_idx = len(bars_upto) - 1
    kwargs = dict(cfg["kwargs"])
    if cfg.get("direction_filter"):
        kwargs["direction_mask"] = _direction_mask_for(bars_upto)
    events, snap = simular_variant(bars_upto, return_state=True, **kwargs)
    open_state, last_bar_exits = snap.get("open") or {}, snap.get("last_bar_exits") or {}
    new_entry_this_bar = any(
        ev["idx"] == last_idx and ev["motivo"].startswith("ENTRY")
        for ev in events)

    if not cycle.has_actions:
        if new_entry_this_bar:
            sides = sorted({ev["lado"] for ev in events
                            if ev["idx"] == last_idx and ev["motivo"].startswith("ENTRY")})
            findings.append(Finding(
                "MISSED_SIGNAL", True, cycle.config_id, cycle.line_no,
                cycle.bar_t,
                f"executor logged 'actions: none' but lake-recomputed state "
                f"shows a NEW entry on bar t={truncate_t} (side(s)={sides})"))
        return findings

    # non-"none" action set: check each intent against lake-recomputed state.
    for intent in cycle.intents:
        tag = intent.ficha
        if intent.kind == "OPEN":
            d = open_state.get(tag)
            if d is None:
                findings.append(Finding(
                    "SIGNAL_MISMATCH", True, cycle.config_id, cycle.line_no,
                    cycle.bar_t,
                    f"executor logged OPEN/{tag} but lake-recomputed desired "
                    f"state has no open ficha {tag} at bar t={truncate_t}"))
        elif intent.kind == "MODIFY":
            d = open_state.get(tag)
            if d is None:
                findings.append(Finding(
                    "STATE_MISMATCH", True, cycle.config_id, cycle.line_no,
                    cycle.bar_t,
                    f"executor logged MODIFY/{tag} but lake-recomputed state "
                    f"has ficha {tag} flat at bar t={truncate_t}"))
        elif intent.kind in ("CLOSE", "SAME_BAR_EXIT_FALLBACK"):
            d = open_state.get(tag)
            exited = tag in last_bar_exits
            if d is not None and not exited:
                findings.append(Finding(
                    "STATE_MISMATCH", True, cycle.config_id, cycle.line_no,
                    cycle.bar_t,
                    f"executor logged {intent.kind}/{tag} but lake-recomputed "
                    f"state still has ficha {tag} open (not absent/exited) at "
                    f"bar t={truncate_t}"))
        # NOOP / REJECT_* / SUPPRESSED_OPEN / MISSING_SL_ALARM: no lake-state
        # assertion defined by spec; skip.
    return findings


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def _lake_symbol_tf(cfg: dict[str, Any]) -> tuple[str, str]:
    return cfg["kwargs"]["symbol"], cfg["tf"]


def run_check(cycles: list[ParsedCycle], lake_root: Path,
              config_ids: list[str] | None = None,
              window: int = DEFAULT_WINDOW) -> dict[str, ConfigResult]:
    """Group parsed cycles by config, load lake bars once per config, diff
    every cycle. Pure aside from the lake read."""
    by_cfg: dict[str, list[ParsedCycle]] = {}
    for c in cycles:
        if config_ids is not None and c.config_id not in config_ids:
            continue
        by_cfg.setdefault(c.config_id, []).append(c)

    results: dict[str, ConfigResult] = {}
    for cfg_id, cyc_list in by_cfg.items():
        cfg = CONFIG_BY_ID.get(cfg_id)
        res = ConfigResult(config_id=cfg_id)
        if cfg is None:
            res.findings.append(Finding(
                "STATE_MISMATCH", True, cfg_id, cyc_list[0].line_no,
                cyc_list[0].bar_t, f"unknown config id '{cfg_id}' (not in CONFIGS_20)"))
            results[cfg_id] = res
            continue

        tf_s = TF_SECONDS[cfg["tf"]]
        symbol, tf = _lake_symbol_tf(cfg)
        first_bar_t = min(c.bar_t for c in cyc_list)
        last_bar_t = max(c.bar_t for c in cyc_list)
        start = datetime.fromtimestamp(
            first_bar_t - window * tf_s, tz=timezone.utc)
        end = datetime.fromtimestamp(last_bar_t + tf_s, tz=timezone.utc)
        lake_bars = load_bars(lake_root, symbol, tf, start, end)

        res.bars_checked = len(lake_bars)
        for cyc in cyc_list:
            res.cycles += 1
            res.findings.extend(diff_cycle(cyc, lake_bars, cfg, tf_s))
        results[cfg_id] = res
    return results


def _fmt_summary(res: ConfigResult) -> str:
    counts = res.count_by_kind()
    hard_n = len(res.hard_findings)
    non_hard_parts = ", ".join(
        f"{k}={counts[k]}" for k in sorted(NON_HARD_KINDS) if k in counts)
    hard_parts = ", ".join(
        f"{k}={counts[k]}" for k in sorted(HARD_KINDS) if k in counts)
    return (f"== {res.config_id} == cycles={res.cycles} bars_checked={res.bars_checked} "
            f"hard={hard_n}"
            + (f" [{hard_parts}]" if hard_parts else "")
            + (f" non_hard=[{non_hard_parts}]" if non_hard_parts else ""))


def _fmt_finding(f: Finding) -> str:
    return (f"   [{'HARD' if f.hard else 'ok  '}] {f.kind} line={f.cycle_line_no} "
            f"bar_t={f.bar_t}: {f.detail}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Dry-run intent parity checker (LIVE MT5 vs lake, read-only).")
    ap.add_argument("--log", required=True, help="path to run_live_20.audit.log")
    ap.add_argument("--configs", default="all", help="'all' or comma ids e.g. SS-M5,V10-M15")
    ap.add_argument("--lake", default=str(REPO_ROOT / "data" / "lake"))
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                    help="warmup bars to load before the first cycle bar (mirrors executor)")
    ap.add_argument("--json", default=None, help="optional path to dump the machine-readable report")
    args = ap.parse_args(argv)

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"[ERROR] log file not found: {log_path}", file=sys.stderr)
        return 2

    text = log_path.read_text(encoding="utf-8", errors="replace")
    cycles, stats = parse_audit_log(text)

    if args.configs.lower() == "all":
        config_ids = None
    else:
        want = {s.strip() for s in args.configs.split(",")}
        unknown = want - {c["id"] for c in CONFIGS_20}
        if unknown:
            print(f"unknown config id(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        config_ids = sorted(want)

    results = run_check(cycles, Path(args.lake), config_ids=config_ids, window=args.window)

    for cfg_id in sorted(results):
        res = results[cfg_id]
        print(_fmt_summary(res))
        for f in res.hard_findings:
            print(_fmt_finding(f))

    n_hard = sum(len(r.hard_findings) for r in results.values())
    print(f"\nPARSE: total_lines={stats.total_lines} cycles_parsed={stats.cycles_parsed} "
          f"parse_skipped={stats.parse_skipped}")
    print(f"TOTAL: {len(results)} config(s) checked, {n_hard} hard finding(s).")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "parse_stats": {"total_lines": stats.total_lines,
                            "cycles_parsed": stats.cycles_parsed,
                            "parse_skipped": stats.parse_skipped},
            "configs": {
                cfg_id: {
                    "cycles": r.cycles, "bars_checked": r.bars_checked,
                    "hard": len(r.hard_findings),
                    "counts_by_kind": r.count_by_kind(),
                    "findings": [{"kind": f.kind, "hard": f.hard,
                                 "line_no": f.cycle_line_no, "bar_t": f.bar_t,
                                 "detail": f.detail} for f in r.findings],
                } for cfg_id, r in results.items()
            },
        }, indent=2), encoding="utf-8")

    return 1 if n_hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
