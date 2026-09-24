"""scripts/report/gen_w2_audit.py -- W2/OOW2 forensic audit (P31, honest
program, 2026-07-20).

The `sim-report-emasar-oow2-*` family (17 runs, W2 = 2026-03-02 -> 2026-04-03,
$68-146k on-paper each) is the registry's biggest never-audited block. B1
marked all 17 REGIME_UNAUDITED tonight. This script runs the V-12-style
forensic protocol against each run and upgrades its `run.validity` to
`W2_AUDIT_PASS` or `W2_AUDIT_FAIL(<reason>)`, using the SAME atomic,
additive-only write pattern as `scripts/report/mark_validity_2026_07_19.py`
(single connection, single transaction, `ResearchRegistry.audit_on`;
actor='honest-program', accion='validity-mark').

PROTOCOL (per oow2 run):
  TEST-1  Entry-improvement forensics -- join each trade to its entry-bar's
          lake OHLC and measure signed entry improvement vs bar CLOSE (spread
          stripped). These configs enter at close, so the expected signature
          is ~0; any material favorable improvement is a non-causal headline.
  TEST-2  Same-bar exit census -- fraction of exits priced within the entry
          bar (ts_out == ts_in). Same-bar trail raises are the look-ahead
          signature `gen_livefill_bound` (D90) neutralizes.
  TEST-3  Causal sanity -- verified per run from TEST-1, not assumed.
  TEST-4  Honest re-pricing -- the honest net for each cell under live_fill
          semantics + 0.5 spread. IMPORTANT: some (variant, tf, W2) cells
          already exist as honest-screen live-fill runs (D90 + tonight's
          honest sweep). We LINK to an existing honest twin by full param
          signature (tf + engine params, ignoring only the free-text
          `variant` label and the `live_fill_mode` flag) when one exists, and
          only re-simulate cells with NO honest twin ("FRESH"). Fresh sims
          reuse gen_oow_validation's W2 window machinery with
          live_fill_mode=True (the 0.5 Capitaria spread is already applied at
          fill by that machinery -- "flat $0.50 friction").
  TEST-5  Verdict -- W2_AUDIT_PASS if the honest net survives materially
          profitable; W2_AUDIT_FAIL(reason) if it collapses (to a loss, or to
          a token fraction of the on-paper figure).

CLI:
    python -m scripts.report.gen_w2_audit [--db PATH] [--dry-run]

`--dry-run` opens the DB READ-ONLY, computes and prints the full per-cell
verdict table, and writes NO validity/audit rows.

CONCURRENCY (the overnight honest sweep may run against data/research.db):
  read connections open in mode=ro; the sole write pass is one short
  transaction at the very end; every connection uses timeout=60; if the DB is
  locked beyond that, we print and exit nonzero rather than hang.

Windows-safe: pathlib + sqlite3 stdlib. Reuses (does NOT modify)
gen_oow_validation's W2 loaders/metrics for the FRESH cells via the same
importlib pattern every batch script in this program has used.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sentinel_engine.research.registry2 import (  # noqa: E402
    DEFAULT_DB_PATH,
    ResearchRegistry,
)

ACTOR = "honest-program"
ACCION = "validity-mark"

SPREAD = 0.5          # Capitaria/MT5 flat spread applied at fill.
BUSY_TIMEOUT_S = 60   # tolerate the concurrent honest sweep's locks.
OOW2_PREFIX = "sim-report-emasar-oow2-"
W2_DESDE = "2026-03-02"  # honest twins must share the W2 window.

# Verdict threshold. The on-paper (classic) net is KNOWN-inflated by
# look-ahead/same-bar fills -- so the verdict does NOT ask what fraction of
# that fake figure survives; it asks whether a REAL, materially-profitable
# edge remains once the cell is re-priced under honest live-fill semantics.
# A cell PASSES iff its honest net clears a material profit floor; anything at
# or below it (a loss, break-even, or a token profit) FAILS -- the on-paper
# money was a fill artifact. $1000 over a W2 month ≈ the smallest edge worth
# a live-demo slot at 0.10 lot.
PASS_MIN_HONEST_NET = 1000.0
CAUSAL_TOL = 0.01                # |mean signed entry improvement| <= this = clean.

# Keys that do NOT define the engine's behavior and must be excluded from the
# param signature: the free-text label and the fill-mode flag (a classic run
# and its live-fill twin share every OTHER param).
_SIG_DROP_KEYS = frozenset({"variant", "live_fill_mode"})

_TF_RE = re.compile(r"m(\d+)")


class AuditEnvError(RuntimeError):
    """A cell could not be resolved for ENVIRONMENT reasons (bars/lake load
    failure, fresh re-simulation crash, causal join unverifiable) -- never a
    forensic finding. The apply pass must ABORT with ZERO writes rather than
    persist a forensic-sounding verdict for an env problem (B4 review fix,
    2026-07-20)."""


# ---------------------------------------------------------------------------
# TEST-1 / TEST-2 / TEST-3: pure forensic maths on trades + entry-bar OHLC.
# ---------------------------------------------------------------------------

def entry_improvement(
    trades: list[dict[str, Any]],
    bars: list[dict[str, Any]],
    spread: float = SPREAD,
) -> dict[str, Any]:
    """Mean SIGNED entry improvement of each trade's fill vs its entry-bar
    CLOSE, spread stripped. Positive = the fill was more favorable than the
    bar close (LONG bought below close / SHORT sold above close) -- the
    look-ahead signature. Trades whose entry epoch has no matching bar are
    skipped (reported via n_matched)."""
    by_t = {b["t"]: b for b in bars}
    signed: list[float] = []
    for t in trades:
        bar = by_t.get(t["ts_in_epoch"])
        if bar is None:
            continue
        side = t["side"]
        # Strip the fill spread to recover the raw BID/close-comparable price.
        raw_entry = t["px_in"] - spread if side == "LONG" else t["px_in"]
        imp = (bar["close"] - raw_entry) if side == "LONG" else (raw_entry - bar["close"])
        signed.append(imp)
    n = len(signed)
    return {
        "n_matched": n,
        "mean_signed": round(sum(signed) / n, 6) if n else 0.0,
        "max_favorable": round(max(signed), 6) if n else 0.0,
    }


def same_bar_exit_census(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Fraction of trades whose exit is priced within the SAME bar as entry
    (ts_out_epoch == ts_in_epoch) -- the intrabar same-bar trail-raise
    look-ahead signature."""
    n = len(trades)
    n_same = sum(1 for t in trades if t["ts_out_epoch"] == t["ts_in_epoch"])
    return {
        "n": n,
        "n_same_bar": n_same,
        "fraction": round(n_same / n, 6) if n else 0.0,
    }


def causal_verdict(mean_signed_improvement: float, tol: float = CAUSAL_TOL) -> dict[str, Any]:
    """A config that enters at close has ~0 signed entry improvement. A
    material favorable value means the fill beat any causal engine -> a
    non-causal (look-ahead) entry signature."""
    clean = abs(mean_signed_improvement) <= tol
    note = ("entries clean (≈ bar close, causal)" if clean else
            f"NON-CAUSAL: mean favorable entry improvement {mean_signed_improvement} "
            f"exceeds tol {tol} -- headline finding")
    return {"clean": clean, "note": note}


# ---------------------------------------------------------------------------
# TEST-5: verdict from classic vs honest net.
# ---------------------------------------------------------------------------

def honest_verdict(classic_net: float, honest_net: float) -> dict[str, Any]:
    """W2_AUDIT_PASS iff the honest (live-fill + friction) net clears the
    material profit floor; otherwise W2_AUDIT_FAIL(reason). The on-paper net
    is reported for context (its inflation ratio vs honest) but is NOT the
    pass criterion -- a known-inflated figure cannot vouch for itself."""
    if honest_net < PASS_MIN_HONEST_NET:
        if honest_net <= 0:
            gist = f"honest live-fill net {honest_net:+.1f} is not profitable"
        else:
            gist = (f"honest live-fill net {honest_net:+.1f} is below the "
                    f"${PASS_MIN_HONEST_NET:.0f} material-edge floor")
        drop = ""
        if classic_net > 0:
            drop = (f" -- collapses from the on-paper {classic_net:+.1f} "
                    f"({honest_net/classic_net*100:.1f}% survives)")
        return {
            "verdict": "W2_AUDIT_FAIL",
            "reason": (f"{gist}{drop}; the on-paper edge is a look-ahead/"
                       f"same-bar fill artifact"),
        }
    survival = (f" ({honest_net/classic_net*100:.1f}% of on-paper "
                f"{classic_net:+.1f})" if classic_net > 0 else "")
    return {
        "verdict": "W2_AUDIT_PASS",
        "reason": f"honest live-fill net {honest_net:+.1f} clears the material "
                  f"profit floor{survival}",
    }


# ---------------------------------------------------------------------------
# TEST-4: honest-twin matching by full param signature.
# ---------------------------------------------------------------------------

def param_signature(params: dict[str, Any]) -> tuple:
    """A hashable signature of the ENGINE-relevant params: every key except
    the free-text `variant` label and the `live_fill_mode` flag, with lists
    (sar_fast/sar_slow) normalized to tuples. Two runs with the same signature
    are the same config regardless of fill mode or label. NOTE: an extra
    lever present on only one side (e.g. `trail_atr_floor_k` on the s6 sweep)
    changes the signature -> distinct configs never collapse into one twin."""
    items = []
    for k in sorted(params):
        if k in _SIG_DROP_KEYS:
            continue
        v = params[k]
        if isinstance(v, list):
            v = tuple(v)
        items.append((k, v))
    return tuple(items)


def _tf_from_run_id(run_id: str) -> str | None:
    """Last `m\\d+` token in a run_id (handles both `..._M5_M5_W2`-style
    variant suffixes and `...-ss-m5-m5-w2` honest run_ids)."""
    toks = _TF_RE.findall(run_id.lower())
    return "M" + toks[-1] if toks else None


def match_honest_twin(
    oow_params: dict[str, Any],
    oow_tf: str | None,
    honest_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find the existing honest live-fill twin for an oow2 config, or None.

    A candidate qualifies iff: it is a live-fill run
    (params.live_fill_mode is True), its tf matches, and its full param
    signature equals the oow2 config's. When several qualify (the same config
    re-run under different sweep labels -- verified to carry identical nets),
    pick deterministically by lowest run_id."""
    target = param_signature(oow_params)
    cands = [
        r for r in honest_rows
        if r.get("params", {}).get("live_fill_mode") is True
        and r.get("tf") == oow_tf
        and param_signature(r.get("params", {})) == target
    ]
    if not cands:
        return None
    return min(cands, key=lambda r: r["run_id"])


# ---------------------------------------------------------------------------
# DB reads (read-only / mode=ro).
# ---------------------------------------------------------------------------

def _ro_connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(
        f"file:{Path(db_path).as_posix()}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_S
    )
    return conn


def _load_oow2_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every oow2 run currently marked REGIME_UNAUDITED, with parsed params."""
    rows = conn.execute(
        "SELECT run_id, variant_id, net, pf, wr, trades, validity, metrics_json "
        "FROM run WHERE run_id LIKE ? ORDER BY run_id",
        (OOW2_PREFIX + "%",),
    ).fetchall()
    out = []
    for run_id, variant_id, net, pf, wr, trades, validity, mj in rows:
        params = json.loads(mj or "{}").get("params", {})
        out.append({
            "run_id": run_id, "variant_id": variant_id, "net": net, "pf": pf,
            "wr": wr, "trades": trades, "validity": validity, "params": params,
            "tf": _tf_from_run_id(run_id),
        })
    return out


def _load_honest_twins(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every W2 run that is NOT itself an oow2 row (candidate live-fill twins:
    honest-screen sweep rows + any D90 live-fill rows). The live_fill_mode
    filter is applied in `match_honest_twin`, so we deliberately do NOT filter
    on `fidelity` here -- a live-fill twin qualifies by its params, not its
    fidelity label."""
    rows = conn.execute(
        "SELECT run_id, variant_id, net, metrics_json FROM run "
        "WHERE periodo_desde=? AND run_id NOT LIKE ? ORDER BY run_id",
        (W2_DESDE, OOW2_PREFIX + "%"),
    ).fetchall()
    out = []
    for run_id, variant_id, net, mj in rows:
        params = json.loads(mj or "{}").get("params", {})
        out.append({
            "run_id": run_id, "variant_id": variant_id, "net": net,
            "params": params, "tf": _tf_from_run_id(run_id),
        })
    return out


def _load_trades(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    """oow2 trades reshaped for the forensic maths (epoch entry/exit, px, side)."""
    rows = conn.execute(
        "SELECT ts_in, ts_out, px_in, px_out, side, exit_reason "
        "FROM trade WHERE run_id=?",
        (run_id,),
    ).fetchall()
    out = []
    for ts_in, ts_out, px_in, px_out, side, exit_reason in rows:
        out.append({
            "ts_in_epoch": _epoch(ts_in), "ts_out_epoch": _epoch(ts_out),
            "px_in": px_in, "px_out": px_out, "side": side,
            "exit_reason": exit_reason,
        })
    return out


def _epoch(ts: str | None) -> int | None:
    """MT5-dotted UTC string ('2026.03.02 00:15:00') -> epoch seconds."""
    if not ts:
        return None
    return int(datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
               .replace(tzinfo=timezone.utc).timestamp())


# ---------------------------------------------------------------------------
# FRESH cells: live-fill re-simulation via gen_oow_validation's W2 machinery.
# (Lazy import so the fixture tests never need lake data or pyarrow.)
# ---------------------------------------------------------------------------

def _fresh_honest_net(tf: str, params: dict[str, Any]) -> float:
    """Re-simulate one cell on the W2 window with live_fill_mode=True (0.5
    spread already applied at fill by the window machinery) and return the
    honest net. Reuses gen_oow_validation exactly."""
    import importlib.util as ilu

    spec = ilu.spec_from_file_location(
        "gen_oow_validation", _REPO_ROOT / "scripts" / "report" / "gen_oow_validation.py"
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    kwargs = {k: v for k, v in params.items() if k != "variant"}
    kwargs["live_fill_mode"] = True
    # The registry stores `direction_mask` as a DESCRIPTOR STRING
    # ("supertrend_m15_atr14_mult3.0_prev_closed_bar") -- the JSON-safe stand-in
    # for the per-bar mask array the engine actually consumes (see
    # gen_oow_validation line ~645). Rebuild that array from the SAME
    # compute_direction_mask helper the original run used, so the fresh sim is
    # a faithful re-price, not a crash on a str index.
    if isinstance(kwargs.get("direction_mask"), str):
        kwargs["direction_mask"] = mod._mask_for(tf, "W2")
    trades = mod.run_variant_window(tf, "W2", kwargs)
    metrics = mod.compute_metrics_window(trades, "W2")
    return round(float(metrics["net"]), 2)


# ---------------------------------------------------------------------------
# Orchestration: compute per-cell verdicts.
# ---------------------------------------------------------------------------

def compute_verdicts(
    conn: sqlite3.Connection,
    simulate_fresh: bool = True,
) -> list[dict[str, Any]]:
    """For every oow2 run, run the forensic protocol and decide the verdict:
    W2_AUDIT_PASS / W2_AUDIT_FAIL / ENV-ERROR. Pure reads on `conn`.

    ENV-ERROR (B4 review fix): a cell whose honest re-pricing OR causal
    verification could not be completed for environment reasons gets verdict
    'ENV-ERROR' and label=None -- it can NEVER be persisted as a forensic
    finding; `audit_w2`'s apply pass aborts if any exists.

    Causal status (B4 review fix): a run WITH persisted trades whose entry-bar
    join did not happen (bars load raised, join skipped, or 0 bars matched) is
    'UNVERIFIED' -- never 'clean'. UNVERIFIED blocks a PASS label (the cell
    becomes ENV-ERROR); a FAIL-leaning cell still FAILs on the honest-net rule
    with the reason noting causal=UNVERIFIED."""
    oow_runs = _load_oow2_runs(conn)
    honest_twins = _load_honest_twins(conn)

    verdicts: list[dict[str, Any]] = []
    for run in oow_runs:
        classic_net = run["net"]
        trades = _load_trades(conn, run["run_id"])
        census = same_bar_exit_census(trades)

        # ---- TEST-4: honest re-pricing (LINK to twin, else FRESH sim). ----
        twin = match_honest_twin(run["params"], run["tf"], honest_twins)
        linked = twin is not None
        honest_net: float | None = None
        twin_run_id: str | None = None
        fresh = False
        fresh_error: str | None = None

        if twin is not None:
            honest_net = twin["net"]
            twin_run_id = twin["run_id"]
        elif simulate_fresh and run["tf"] is not None:
            fresh = True
            try:
                honest_net = _fresh_honest_net(run["tf"], run["params"])
            except Exception as exc:  # env problem -- NEVER a forensic FAIL
                fresh_error = f"{type(exc).__name__}: {exc}"
                print(f"[gen_w2_audit] ERROR {run['run_id']}: fresh live-fill "
                      f"re-simulation failed: {fresh_error}", file=sys.stderr)
        else:
            fresh_error = ("no honest twin and fresh re-simulation disabled "
                           "(simulate_fresh=False or tf unknown)")

        # ---- TEST-1: entry-improvement needs the entry-bar OHLC join. ----
        ei = {"n_matched": 0, "mean_signed": 0.0, "max_favorable": 0.0}
        join_error: str | None = None
        if trades:
            if run["tf"] is not None and simulate_fresh:
                try:
                    bars = _bars_for_cell(run["tf"])
                    ei = entry_improvement(trades, bars, SPREAD)
                except Exception as exc:
                    join_error = (f"entry-bar OHLC load failed: "
                                  f"{type(exc).__name__}: {exc}")
                    print(f"[gen_w2_audit] WARN {run['run_id']}: {join_error}",
                          file=sys.stderr)
            else:
                join_error = ("causal join not attempted "
                              "(tf unknown or fresh sims disabled)")

        # ---- TEST-3: causal status -- verified, UNVERIFIED, or NONCAUSAL. --
        if not trades:
            causal_status, causal_note = "clean", "no persisted trades (vacuously clean)"
        elif join_error is not None:
            causal_status, causal_note = "UNVERIFIED", join_error
        elif ei["n_matched"] == 0:
            causal_status = "UNVERIFIED"
            causal_note = "run has trades but 0 joined entry bars"
        else:
            c = causal_verdict(ei["mean_signed"])
            causal_status = "clean" if c["clean"] else "NONCAUSAL"
            causal_note = c["note"]

        # ---- TEST-5: verdict. ENV problems never become forensic labels. ---
        if honest_net is None:
            verdict_label = "ENV-ERROR"
            reason = f"honest re-pricing unavailable: {fresh_error}"
        else:
            hv = honest_verdict(classic_net, honest_net)
            verdict_label, reason = hv["verdict"], hv["reason"]
            if causal_status == "UNVERIFIED":
                if verdict_label == "W2_AUDIT_PASS":
                    # UNVERIFIED causal blocks a PASS: env condition, not verdict.
                    verdict_label = "ENV-ERROR"
                    reason = (f"PASS blocked: causal verification unavailable "
                              f"({causal_note})")
                else:
                    reason += f"; causal=UNVERIFIED({causal_note})"

        if verdict_label == "W2_AUDIT_PASS":
            full_label: str | None = "W2_AUDIT_PASS"
        elif verdict_label == "W2_AUDIT_FAIL":
            full_label = f"W2_AUDIT_FAIL({reason})"
        else:
            full_label = None  # ENV-ERROR is never persistable; apply aborts.

        upgraded = run["validity"] == "REGIME_UNAUDITED"

        verdicts.append({
            "run_id": run["run_id"], "tf": run["tf"], "classic_net": classic_net,
            "honest_net": honest_net, "linked": linked, "fresh": fresh,
            "twin_run_id": twin_run_id,
            "n_matched": ei["n_matched"],
            "entry_improvement": ei["mean_signed"],
            "causal_status": causal_status, "causal_note": causal_note,
            "causal_clean": causal_status == "clean",
            "same_bar_frac": census["fraction"],
            "verdict": verdict_label, "label": full_label, "reason": reason,
            "current_validity": run["validity"], "upgraded": upgraded,
        })
    return verdicts


_BARS_CACHE: dict[str, list[dict[str, Any]]] = {}


def _bars_for_cell(tf: str) -> list[dict[str, Any]]:
    """W2 lake bars for `tf` (cached), via gen_oow_validation's loader."""
    if tf not in _BARS_CACHE:
        import importlib.util as ilu

        spec = ilu.spec_from_file_location(
            "gen_oow_validation", _REPO_ROOT / "scripts" / "report" / "gen_oow_validation.py"
        )
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _BARS_CACHE[tf] = mod._bars_for(tf, "W2")
    return _BARS_CACHE[tf]


# ---------------------------------------------------------------------------
# Validity write pass (atomic, additive-only, idempotent).
# ---------------------------------------------------------------------------

def audit_w2(db_path: Path, dry_run: bool = False, simulate_fresh: bool = True) -> list[dict[str, Any]]:
    """Run the forensic audit and (unless dry_run) upgrade each still
    REGIME_UNAUDITED oow2 run's validity to its W2_AUDIT_* verdict in ONE
    short transaction. Returns the per-cell verdict list. Idempotent: a row no
    longer REGIME_UNAUDITED is never re-marked and writes no audit row.

    B4 review fix: if ANY cell resolved to ENV-ERROR (fresh sim crashed,
    causal join unverifiable on a PASS-leaning cell, ...), the apply pass
    raises `AuditEnvError` BEFORE opening the write connection -- zero rows
    are written for the whole batch. Dry-run returns the verdicts (the table
    shows the cell as ENV-ERROR) without raising."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"registry DB not found: {db_path}")

    if dry_run:
        conn = _ro_connect(db_path)
        try:
            return compute_verdicts(conn, simulate_fresh=simulate_fresh)
        finally:
            conn.close()

    # Compute on a read-only connection FIRST (so the heavy read/sim work does
    # NOT hold a write lock against the concurrent honest sweep), then open one
    # short write transaction at the end for the validity UPDATEs + audit rows.
    ro = _ro_connect(db_path)
    try:
        verdicts = compute_verdicts(ro, simulate_fresh=simulate_fresh)
    finally:
        ro.close()

    env_cells = [v for v in verdicts if v["verdict"] == "ENV-ERROR"]
    if env_cells:
        detail = "; ".join(f"{v['run_id']} -> {v['reason']}" for v in env_cells)
        raise AuditEnvError(
            f"apply ABORTED before any write -- {len(env_cells)} cell(s) "
            f"unresolvable (environment/verification failure, not a forensic "
            f"verdict): {detail}")

    registry = ResearchRegistry(db_path)  # additive migration (validity column).
    conn = registry._connect()  # noqa: SLF001
    try:
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_S * 1000}")
        for v in verdicts:
            # Idempotent + additive-only: the ONLY UPDATE touches validity and
            # only while it is still REGIME_UNAUDITED. A row a prior run already
            # upgraded, or one carrying a foreign label, is left untouched.
            cur = conn.execute(
                "UPDATE run SET validity=? WHERE run_id=? AND validity='REGIME_UNAUDITED'",
                (v["label"], v["run_id"]),
            )
            if cur.rowcount != 1:
                v["upgraded"] = False
                continue
            v["upgraded"] = True
            registry.audit_on(conn, ACTOR, ACCION, {
                "run_id": v["run_id"], "label": v["label"], "reason": v["reason"],
                "classic_net": v["classic_net"], "honest_net": v["honest_net"],
                "twin_run_id": v["twin_run_id"], "linked": v["linked"], "fresh": v["fresh"],
            })
        conn.commit()  # single atomic commit: all marks + all audits, or none.
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return verdicts


# ---------------------------------------------------------------------------
# CLI / report printing.
# ---------------------------------------------------------------------------

def _print_table(verdicts: list[dict[str, Any]], dry_run: bool) -> None:
    banner = "DRY-RUN (nothing written)" if dry_run else "APPLIED"
    print(f"gen_w2_audit -- {banner}")
    print(f"{'run_id':38} {'tf':4} {'classic_net':>12} {'honest_net':>12} "
          f"{'src':6} {'n_matched':>9} {'causal':>10} {'verdict'}")
    print("-" * 122)
    n_pass = n_fail = n_env = 0
    for v in sorted(verdicts, key=lambda x: x["run_id"]):
        src = "LINK" if v["linked"] else ("FRESH" if v["fresh"] else "-")
        hn = "n/a" if v["honest_net"] is None else f"{v['honest_net']:+.1f}"
        print(f"{v['run_id']:38} {v['tf'] or '?':4} {v['classic_net']:>12.1f} "
              f"{hn:>12} {src:6} {v['n_matched']:>9} {v['causal_status']:>10} "
              f"{v['verdict']}")
        if v["verdict"] == "W2_AUDIT_PASS":
            n_pass += 1
        elif v["verdict"] == "W2_AUDIT_FAIL":
            n_fail += 1
        else:
            n_env += 1
    print("-" * 122)
    tail = f" / {n_env} ENV-ERROR" if n_env else ""
    print(f"TOTAL: {len(verdicts)} cells -- {n_pass} PASS / {n_fail} FAIL{tail}")
    if n_env:
        print("  ENV-ERROR cells are NOT persistable; the apply pass would abort.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W2/OOW2 forensic audit + validity verdicts (P31). "
                    "See module docstring.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH,
                        help=f"registry DB path (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute + print the per-cell verdict table; write "
                             "NOTHING (opens the DB read-only)")
    args = parser.parse_args(argv)

    try:
        verdicts = audit_w2(args.db, dry_run=args.dry_run)
    except sqlite3.OperationalError as exc:
        print(f"gen_w2_audit: DB busy/locked beyond {BUSY_TIMEOUT_S}s "
              f"(honest sweep still running?): {exc}", file=sys.stderr)
        return 2
    except AuditEnvError as exc:
        print(f"gen_w2_audit: {exc}", file=sys.stderr)
        return 3

    _print_table(verdicts, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
