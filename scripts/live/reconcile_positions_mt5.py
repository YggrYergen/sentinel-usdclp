r"""scripts/live/reconcile_positions_mt5.py -- reconcile the `deals_raw` table
in `data/research.db` against the real MT5 deal history.

WHY: The DealsWatcher (`sentinel_engine.live.deals_watcher`) polls MT5 deals
into `deals_raw` continuously, but gaps happen -- a dead watcher, a missed
SL/TP close (magic=0, attributed human/NULL before position-inheritance
landed), or a position whose deals never got polled at all. The symptom is a
position the DB shows OPEN (an IN deal with no OUT) that MT5 actually CLOSED,
so it shows falsely ABIERTA under its strategy. This tool closes that gap by
BACKFILLING -- from the real MT5 history only -- the deals the DB is missing.

TWO backfill cases:
  1. MISSING OUT: DB has the IN, no OUT; MT5 history shows the position CLOSED
     (>=1 OUT). Insert the missing OUT(s), inheriting strategy_id/variant_id
     from the position's IN (SL/TP closes carry magic=0 and would otherwise be
     attributed human/NULL). Same inheritance rule DealsWatcher uses.
  2. ABSENT POSITION: MT5 history has a full position (IN+OUT) with NO deal at
     all in the DB. Insert both, attributing via magic (`lookup_magic`) exactly
     as DealsWatcher does, then inheriting the OUT from the IN by position_id.

NEVER fabricates deals: only rows that EXIST in the real MT5 history are
inserted. NEVER closes a position MT5 still reports open (no OUT in history ->
left untouched). NEVER sends an order -- MT5 is touched read-only
(`history_deals_get` / `account_info`), the same guard surface as
`run_deals_watcher.py`.

MODES:
  * DRY-RUN (default): reports the backfill plan (per strategy + position_id:
    which OUT tickets are missing, which positions are absent) WITHOUT writing.
  * `--apply`: persists the backfill, IDEMPOTENT -- dedup by the natural key
    `ticket` (an already-present ticket is skipped), so re-running is a no-op.

ATTACH-ONLY / NEVER LAUNCH + ACCOUNT GUARD: identical to run_deals_watcher --
we never `mt5.initialize()` unless the sanctioned DEMO portable terminal is
already running, and after connecting `account_info().login` MUST equal the
sanctioned DEMO login or we exit 2 without touching anything.

USAGE
    python -m scripts.live.reconcile_positions_mt5            # dry-run
    python -m scripts.live.reconcile_positions_mt5 --apply    # persist
    python -m scripts.live.reconcile_positions_mt5 --db data/research.db --apply
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from sentinel_engine.live import guard_cuenta  # noqa: E402
from sentinel_engine.live.deals_watcher import _DEAL_COLUMNS, _attribute_magic  # noqa: E402
from sentinel_engine.research.registry2 import ResearchRegistry  # noqa: E402

# Reuse run_deals_watcher's attach guard + real MT5 read-only adapter so we
# share ONE audited MT5 read surface (never order_send, WMIC path check, etc.).
from scripts.live.run_deals_watcher import (  # noqa: E402
    RealMt5DealsClient,
    _check_login,
    _connect,
    _portable_running,
)

logger = logging.getLogger("reconcile_positions_mt5")

DEFAULT_DB = REPO_ROOT / "data" / "research.db"

# History window: MT5 `history_deals_get(from_ts, to_ts)` epoch range.
#
# THE `from_ts` BUG (2026-07-21, verified live against DEMO 2883015767):
#   MT5's `history_deals_get` returns an EMPTY list when `from_ts` is epoch 0
#   (1970) -- the SAME far-past/far-future "empty return" family as the
#   `to_ts=year-2100` case. Concretely:
#     history_deals_get(0.0, now+86400)            -> 0 deals   (blind!)
#     history_deals_get(now-30d, now+1d)           -> 6561 deals
#   The earlier reconciler used `_FROM_TS = 0.0` "to pull all history", which
#   is exactly the poison value: it read an EMPTY history and then declared
#   "DB already consistent" -- a FALSE NEGATIVE while 8 positions were open.
#   DealsWatcher never hit this because it anchors `from_ts` to a RECENT
#   broker-clock `last_sync`, never 0.0.
#
# THE FIX: bound `from_ts` to a real, recent-ish epoch. We reach back from the
# EARLIEST deal time the DB already knows about (minus `_FROM_MARGIN_S`), so we
# cover every position the DB tracks; if the DB has no deal time to anchor on
# we fall back to `now - _DEFAULT_LOOKBACK_S`. `to_ts` is still padded past
# wall-clock `now` by `_FUTURE_PAD_S` so the window covers the newest deals
# regardless of the broker's UTC offset (a history query can't return
# nonexistent future deals, so the pad is free) -- same trick DealsWatcher uses.
_FUTURE_PAD_S = 86400
# Reach this far back before the earliest DB deal time (server-clock seconds).
_FROM_MARGIN_S = 7 * 86400
# When the DB has no deal to anchor `from_ts` on, look back this far from now.
_DEFAULT_LOOKBACK_S = 120 * 86400

# MT5 `entry` types that CLOSE (reduce/flatten) a position -- all treated as
# OUT for reconciliation. Besides plain OUT, a close-by (`OUT_BY`) and an
# in/out reversal (`INOUT`) also carry a realised close leg; dropping them
# would leave a genuinely-closed position looking open. RealMt5DealsClient maps
# MT5's numeric `entry` to "IN"/"OUT" already, but pass-through stubs / future
# mappings may surface these string forms, so bucket them defensively.
_OUT_ENTRY_TYPES = frozenset({"OUT", "OUT_BY", "INOUT"})


class ReconcileFetchError(RuntimeError):
    """The MT5 history fetch returned EMPTY while the DB still tracks OPEN
    positions -- a BROKEN fetch (the from_ts=0.0 empty-return bug or a dead IPC
    link), NOT a clean reconciliation. Raised so the caller aborts with a
    non-zero exit instead of falsely reporting "DB already consistent"."""


@dataclass
class ReconcileReport:
    applied: bool = False
    # counts
    missing_outs: int = 0          # positions that got OUT(s) backfilled
    absent_positions: int = 0      # positions inserted whole (IN+OUT)
    deals_inserted: int = 0        # total deal rows written (0 in dry-run)
    open_untouched: int = 0        # DB-open positions MT5 also shows open
    # plans (for the dry-run report / assertions)
    #   position_id -> [out_ticket, ...] that would be / were inserted
    plan_out_tickets: dict[Any, list[Any]] = field(default_factory=dict)
    #   position_id -> [ticket, ...] for whole absent positions
    plan_absent_tickets: dict[Any, list[Any]] = field(default_factory=dict)
    #   position_id -> strategy_id (for grouping the report by strategy)
    strategy_by_position: dict[Any, Any] = field(default_factory=dict)


@dataclass
class RepairReport:
    """Report for `repair_attribution` (Task 1, 2026-07-22): manual-close
    (magic=0) OUT rows already persisted as `origin='human',
    strategy_id IS NULL` whose position's IN row is `origin='strategy'`
    inherit that IN's `origin`/`strategy_id`/`variant_id`. Pure DB -- never
    touches MT5."""
    applied: bool = False
    repaired: int = 0
    # one dict per candidate: {"ticket", "position_id", "strategy_id"} --
    # populated in both dry-run and apply (dry-run: what WOULD be repaired).
    candidates: list[dict[str, Any]] = field(default_factory=list)


def repair_attribution(registry: ResearchRegistry, *, apply: bool = False) -> RepairReport:
    """Attribution-repair pass (Task 1): finds OUT rows with
    `entry_type='OUT' AND origin='human' AND strategy_id IS NULL` whose
    `position_id` has an IN row with `origin='strategy'` (matched by
    position_id ONLY -- no time bound on the IN, so a same-day manual close
    whose IN landed on an earlier day is still found), and updates those OUT
    rows to inherit `origin`, `strategy_id`, `variant_id` from that IN.

    Pure DB: works even if MT5 attach fails -- this pass never touches MT5.
    Dry-run (default) reports the candidates without writing; `--apply`
    persists the UPDATEs. Idempotent: a second run (after apply) finds 0
    candidates, since the just-repaired OUT rows no longer match the
    `origin='human' AND strategy_id IS NULL` predicate.
    """
    report = RepairReport(applied=apply)
    conn = registry._connect()
    try:
        rows = conn.execute(
            """
            SELECT o.ticket AS ticket, o.position_id AS position_id,
                   i.strategy_id AS strategy_id, i.variant_id AS variant_id
            FROM deals_raw o
            JOIN deals_raw i
              ON i.position_id = o.position_id AND i.entry_type = 'IN'
            WHERE o.entry_type = 'OUT'
              AND o.origin = 'human'
              AND o.strategy_id IS NULL
              AND i.origin = 'strategy'
            ORDER BY o.ticket
            """
        ).fetchall()

        for ticket, position_id, strategy_id, variant_id in rows:
            report.candidates.append({
                "ticket": ticket,
                "position_id": position_id,
                "strategy_id": strategy_id,
            })
            if apply:
                conn.execute(
                    "UPDATE deals_raw SET origin='strategy', strategy_id=?, "
                    "variant_id=? WHERE ticket=?",
                    (strategy_id, variant_id, ticket),
                )
                report.repaired += 1

        if apply and rows:
            conn.commit()
        return report
    finally:
        conn.close()


def _format_repair_report(report: RepairReport) -> str:
    """Human-readable dry-run/apply summary for `repair_attribution`."""
    lines: list[str] = []
    mode = "APPLIED" if report.applied else "DRY-RUN (no writes)"
    lines.append(f"=== attribution repair: {mode} ===")
    lines.append(f"candidates : {len(report.candidates)}")
    lines.append(f"repaired   : {report.repaired}")
    for c in report.candidates:
        lines.append(
            f"  ticket {c['ticket']} (position {c['position_id']}) "
            f"-> strategy_id={c['strategy_id']}"
        )
    if not report.candidates:
        lines.append("Nothing to repair: no human/NULL OUT with a strategy IN found.")
    return "\n".join(lines)


@dataclass
class EnrichReport:
    """Report for `enrich_comment_reason` (Task 2.3, 2026-07-22): backfills
    `comment`/`reason` from MT5 history for `deals_raw` tickets where either
    column is still NULL. REQUIRES MT5 (unlike `repair_attribution`, which
    is pure DB)."""
    applied: bool = False
    enriched: int = 0
    # tickets that are candidates (comment IS NULL OR reason IS NULL) AND
    # were found in the MT5 history window -- populated in both dry-run and
    # apply.
    candidates: list[Any] = field(default_factory=list)


def enrich_comment_reason(registry: ResearchRegistry, client: Any, *,
                           apply: bool = False) -> EnrichReport:
    """For tickets present in `deals_raw` where `comment IS NULL OR
    reason IS NULL`, look up the matching MT5 history deal (by ticket, over
    the same bounded window `reconcile` uses) and UPDATE ONLY the `comment`/
    `reason` columns from it. Never touches any other column. Idempotent:
    a ticket already carrying both values is not a candidate, so re-running
    finds nothing left to do.
    """
    report = EnrichReport(applied=apply)
    conn = registry._connect()
    try:
        null_tickets = {
            row[0] for row in conn.execute(
                "SELECT ticket FROM deals_raw "
                "WHERE comment IS NULL OR reason IS NULL"
            ).fetchall()
        }
        if not null_tickets:
            return report

        from_ts = _bounded_from_ts(conn)
        to_ts = time.time() + _FUTURE_PAD_S
        mt5_by_ticket = {
            deal.get("ticket"): deal
            for deal in client.history_deals_get(from_ts, to_ts)
        }

        for ticket in sorted(null_tickets):
            deal = mt5_by_ticket.get(ticket)
            if deal is None:
                continue
            report.candidates.append(ticket)
            if apply:
                conn.execute(
                    "UPDATE deals_raw SET comment=?, reason=? WHERE ticket=?",
                    (deal.get("comment"), deal.get("reason"), ticket),
                )
                report.enriched += 1

        if apply and report.candidates:
            conn.commit()
        return report
    finally:
        conn.close()


def _format_enrich_report(report: EnrichReport) -> str:
    """Human-readable dry-run/apply summary for `enrich_comment_reason`."""
    lines: list[str] = []
    mode = "APPLIED" if report.applied else "DRY-RUN (no writes)"
    lines.append(f"=== comment/reason enrichment: {mode} ===")
    lines.append(f"candidates : {len(report.candidates)}")
    lines.append(f"enriched   : {report.enriched}")
    if not report.candidates:
        lines.append("Nothing to enrich: every ticket already has comment+reason.")
    return "\n".join(lines)


def _load_db_positions(conn: Any) -> dict[Any, dict[str, Any]]:
    """position_id -> {in_deal_present, out_deal_present, tickets(set),
    strategy_id, variant_id} summarising what the DB already has, so we know
    which positions are open (IN, no OUT), which are absent, and which tickets
    already exist (idempotency)."""
    positions: dict[Any, dict[str, Any]] = {}
    rows = conn.execute(
        "SELECT ticket, position_id, entry_type, strategy_id, variant_id "
        "FROM deals_raw"
    ).fetchall()
    for ticket, position_id, entry_type, strategy_id, variant_id in rows:
        p = positions.setdefault(position_id, {
            "has_in": False, "has_out": False, "tickets": set(),
            "strategy_id": None, "variant_id": None,
        })
        p["tickets"].add(ticket)
        if entry_type == "IN":
            p["has_in"] = True
            # attribution lives on the IN row
            if strategy_id is not None:
                p["strategy_id"] = strategy_id
                p["variant_id"] = variant_id
        elif entry_type == "OUT":
            p["has_out"] = True
    return positions


def _mt5_open_position_count(client: Any) -> int:
    """Count of currently-open MT5 positions via `positions_get()` (read-only),
    used only to strengthen the empty-fetch safety-check. Defensive: a client
    without `positions_get` (e.g. RealMt5DealsClient today, or a test stub) or
    a call that raises/returns None yields 0, so this NEVER blocks a legitimate
    empty reconcile -- it only ADDS evidence that an empty history is a fetch
    failure."""
    positions_get = getattr(client, "positions_get", None)
    if positions_get is None:
        return 0
    try:
        result = positions_get()
    except Exception:  # noqa: BLE001 -- read-only probe, never fatal
        return 0
    return len(result) if result is not None else 0


def _open_db_positions(db_positions: dict[Any, dict[str, Any]]) -> list[Any]:
    """position_ids the DB tracks as OPEN: an IN with no OUT. Used by the
    safety-check -- if the MT5 history fetch is empty yet these exist, the
    fetch is broken (we'd never legitimately have an open position with zero
    corresponding MT5 history)."""
    return [pid for pid, p in db_positions.items()
            if p.get("has_in") and not p.get("has_out")]


def _earliest_db_deal_time(conn: Any) -> float | None:
    """Smallest `time` (broker/server epoch) across `deals_raw`, or None when
    the table is empty. Anchors a BOUNDED `from_ts` so the MT5 fetch reaches
    back far enough to cover every position the DB knows about -- without using
    the poison epoch-0 value that makes MT5 return an empty history."""
    row = conn.execute(
        "SELECT MIN(time) FROM deals_raw WHERE time IS NOT NULL"
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0])


def _bounded_from_ts(conn: Any) -> float:
    """A NON-ZERO `from_ts` for `history_deals_get`. Anchored to the earliest
    DB deal time minus `_FROM_MARGIN_S`; falls back to `now - _DEFAULT_LOOKBACK_S`
    when the DB has no deal time. NEVER returns 0.0 (the value that makes MT5
    return an empty history -- the bug this reconciler was blind to)."""
    earliest = _earliest_db_deal_time(conn)
    if earliest is not None:
        return max(0.0, earliest - _FROM_MARGIN_S) or 1.0
    return max(1.0, time.time() - _DEFAULT_LOOKBACK_S)


def _mt5_deals_by_position(client: Any, from_ts: float) -> dict[Any, dict[str, list]]:
    """position_id -> {"IN": [...deals], "OUT": [...deals]} from the MT5
    history (read-only), fetched over the BOUNDED window [from_ts, now+pad].
    Deals with no position_id are ignored (can't be reconciled to a position).
    Any closing entry (OUT, close-by, in/out reversal) is bucketed as OUT so a
    genuinely-closed position isn't left looking open."""
    by_pos: dict[Any, dict[str, list]] = {}
    to_ts = time.time() + _FUTURE_PAD_S
    for deal in client.history_deals_get(from_ts, to_ts):
        pid = deal.get("position_id")
        if pid is None:
            continue
        slot = by_pos.setdefault(pid, {"IN": [], "OUT": []})
        et = deal.get("entry_type")
        if et == "IN":
            slot["IN"].append(deal)
        elif et in _OUT_ENTRY_TYPES:
            slot["OUT"].append(deal)
    return by_pos


def _row_from_deal(registry: ResearchRegistry, deal: dict[str, Any],
                   inherit: dict[str, Any] | None) -> dict[str, Any]:
    """MT5 deal dict -> `deals_raw` row (only `_DEAL_COLUMNS`), attributing via
    magic then, if the deal isn't itself strategy-attributed, inheriting the
    position's strategy (by position_id) -- the exact rule DealsWatcher applies
    to magic=0 SL/TP-close OUTs."""
    row = {col: deal.get(col) for col in _DEAL_COLUMNS}
    attr = _attribute_magic(registry, deal.get("magic"))
    row["origin"] = attr["origin"]
    row["strategy_id"] = attr["strategy_id"]
    row["variant_id"] = attr["variant_id"]
    if row.get("origin") != "strategy" and inherit is not None \
            and inherit.get("strategy_id") is not None:
        row["origin"] = "strategy"
        row["strategy_id"] = inherit["strategy_id"]
        row["variant_id"] = inherit["variant_id"]
    return row


def _insert_rows(conn: Any, rows: list[dict[str, Any]]) -> int:
    """Insert deal rows, idempotent by `ticket` (ON CONFLICT DO NOTHING).
    Returns rows actually inserted."""
    if not rows:
        return 0
    cols = ", ".join(_DEAL_COLUMNS)
    placeholders = ", ".join("?" for _ in _DEAL_COLUMNS)
    inserted = 0
    for row in rows:
        cur = conn.execute(
            f"INSERT INTO deals_raw({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(ticket) DO NOTHING",
            tuple(row[c] for c in _DEAL_COLUMNS),
        )
        inserted += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    return inserted


def reconcile(registry: ResearchRegistry, client: Any, *,
              apply: bool = False) -> ReconcileReport:
    """Reconcile `deals_raw` against MT5 history. Read-only toward MT5. When
    `apply` is False (default) computes the plan and writes nothing; when True
    persists the backfill idempotently (dedup by ticket). See module docstring
    for the two backfill cases and the untouched-open rule."""
    report = ReconcileReport(applied=apply)
    conn = registry._connect()
    try:
        db_positions = _load_db_positions(conn)
        from_ts = _bounded_from_ts(conn)
        mt5_positions = _mt5_deals_by_position(client, from_ts)

        # SAFETY-CHECK: an EMPTY MT5 history while the DB still tracks OPEN
        # positions (or MT5 itself reports open positions) is a BROKEN FETCH,
        # not a clean reconcile -- refuse to declare "consistent". This is the
        # exact from_ts=0.0 empty-return failure mode that blinded the earlier
        # reconciler. We abort (raise) so the CLI exits non-zero.
        if not mt5_positions:
            open_pids = _open_db_positions(db_positions)
            live_open = _mt5_open_position_count(client)
            if open_pids or live_open > 0:
                raise ReconcileFetchError(
                    f"MT5 history fetch returned 0 deals but "
                    f"{len(open_pids)} DB-open position(s) and "
                    f"{live_open} live MT5 position(s) exist "
                    f"(from_ts={from_ts:.0f}). This is a BROKEN FETCH, not a "
                    f"clean reconciliation -- refusing to report 'consistent'."
                )

        rows_to_insert: list[dict[str, Any]] = []

        for pid, slots in mt5_positions.items():
            mt5_outs = slots["OUT"]
            mt5_ins = slots["IN"]
            db = db_positions.get(pid)

            if db is None:
                # ABSENT POSITION: only backfill when MT5 shows a CLOSED
                # position (both IN and OUT). A position MT5 shows still open
                # and that the DB has never seen is genuinely open -> skip
                # (the watcher will pick up its IN; we never invent a close).
                if not mt5_ins or not mt5_outs:
                    if mt5_ins and not mt5_outs:
                        report.open_untouched += 1
                    continue
                # Attribute the IN by magic; the OUT inherits from that IN.
                in_deal = mt5_ins[0]
                in_row = _row_from_deal(registry, in_deal, None)
                inherit = {
                    "strategy_id": in_row.get("strategy_id"),
                    "variant_id": in_row.get("variant_id"),
                } if in_row.get("origin") == "strategy" else None
                pos_rows = [in_row]
                for out in mt5_outs:
                    pos_rows.append(_row_from_deal(registry, out, inherit))
                rows_to_insert.extend(pos_rows)
                report.absent_positions += 1
                report.plan_absent_tickets[pid] = [r["ticket"] for r in pos_rows]
                report.strategy_by_position[pid] = in_row.get("strategy_id")
                continue

            # Position exists in DB.
            if db["has_out"]:
                continue  # already closed in DB, nothing to do.

            if not mt5_outs:
                # DB-open AND MT5 shows no close -> genuinely open, DON'T TOUCH.
                report.open_untouched += 1
                continue

            # MISSING OUT: DB has the IN (open), MT5 shows it CLOSED. Backfill
            # the OUT(s) the DB is missing, inheriting the position's strategy.
            inherit = {
                "strategy_id": db.get("strategy_id"),
                "variant_id": db.get("variant_id"),
            }
            missing = [out for out in mt5_outs
                       if out.get("ticket") not in db["tickets"]]
            if not missing:
                continue  # every OUT already present (shouldn't happen if !has_out)
            for out in missing:
                rows_to_insert.append(_row_from_deal(registry, out, inherit))
            report.missing_outs += 1
            report.plan_out_tickets[pid] = [out.get("ticket") for out in missing]
            report.strategy_by_position[pid] = db.get("strategy_id")

        if apply and rows_to_insert:
            report.deals_inserted = _insert_rows(conn, rows_to_insert)
            conn.commit()
        return report
    finally:
        conn.close()


def _format_report(report: ReconcileReport) -> str:
    """Human-readable dry-run/apply summary, grouped by strategy."""
    lines: list[str] = []
    mode = "APPLIED" if report.applied else "DRY-RUN (no writes)"
    lines.append(f"=== MT5<->DB reconcile: {mode} ===")
    lines.append(f"missing OUT backfills : {report.missing_outs}")
    lines.append(f"absent positions      : {report.absent_positions}")
    lines.append(f"deals inserted        : {report.deals_inserted}")
    lines.append(f"open (untouched)      : {report.open_untouched}")

    def _by_strategy(plan: dict[Any, list[Any]]) -> dict[Any, list[str]]:
        out: dict[Any, list[str]] = {}
        for pid, tickets in plan.items():
            strat = report.strategy_by_position.get(pid) or "(unattributed)"
            out.setdefault(strat, []).append(f"pos {pid}: tickets {tickets}")
        return out

    if report.plan_out_tickets:
        lines.append("--- missing OUT (position -> out tickets) ---")
        for strat, items in sorted(_by_strategy(report.plan_out_tickets).items()):
            lines.append(f"  [{strat}]")
            for it in items:
                lines.append(f"    {it}")
    if report.plan_absent_tickets:
        lines.append("--- absent positions (position -> IN+OUT tickets) ---")
        for strat, items in sorted(_by_strategy(report.plan_absent_tickets).items()):
            lines.append(f"  [{strat}]")
            for it in items:
                lines.append(f"    {it}")
    if not report.plan_out_tickets and not report.plan_absent_tickets:
        lines.append("Nothing to backfill: DB already consistent with MT5 history.")
    return "\n".join(lines)


def main(argv: list[str] | None = None, *, mt5_module: Any = None,
         attach_checker: Callable[[], bool] = _portable_running,
         registry_factory: Callable[[Path], ResearchRegistry] = ResearchRegistry,
         client_factory: Callable[[Any], Any] = RealMt5DealsClient) -> int:
    ap = argparse.ArgumentParser(
        description="Reconcile deals_raw against MT5 history (read-only; backfill only).")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="path to research.db")
    ap.add_argument("--apply", action="store_true",
                    help="persist the backfill (default: dry-run, no writes)")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)])

    # Attribution-repair pass (Task 1, 2026-07-22) runs FIRST and is pure DB
    # -- it must work even if MT5 attach fails below, so it's not gated by
    # the attach_checker() at all.
    registry = registry_factory(Path(args.db))
    repair_report = repair_attribution(registry, apply=args.apply)
    print(_format_repair_report(repair_report))
    if not args.apply and repair_report.candidates:
        print("\nRe-run with --apply to persist this attribution repair.")
    print()

    # ATTACH-ONLY / NEVER LAUNCH: confirm the DEMO portable terminal is running
    # BEFORE importing/initializing MetaTrader5.
    if not attach_checker():
        print("[STOP] The DEMO portable MT5 terminal is NOT running.\n"
              "       Open it first via  D:\\FOREX\\MT5_DEMO_TOMAS.bat  (login "
              f"{guard_cuenta.DEMO_LOGIN}), then re-run this reconciler.\n"
              "       (initialize() was NOT called -- we never launch a terminal.)\n"
              "       (the attribution-repair pass above still ran -- it needs no MT5.)",
              file=sys.stderr)
        return 3

    mt5 = mt5_module
    if mt5 is None:
        import MetaTrader5 as mt5  # noqa: N813 -- only imported once attach-confirmed
    _connect(mt5)
    try:
        login = _check_login(mt5)
    except SystemExit as exc:
        try:
            mt5.shutdown()
        except Exception:  # noqa: BLE001
            pass
        return exc.code if isinstance(exc.code, int) else 2
    logger.info("connected + account guard OK: DEMO login %s", login)

    try:
        client = client_factory(mt5)
        try:
            report = reconcile(registry, client, apply=args.apply)
        except ReconcileFetchError as exc:
            print(
                "\n[FETCH FAILURE] " + str(exc) + "\n"
                "                The MT5 history read came back EMPTY while "
                "positions are open.\n"
                "                NOT reporting 'consistent' -- this needs "
                "investigation (dead\n"
                "                MT5 IPC link, or the from_ts empty-return "
                "bug). Nothing was written.",
                file=sys.stderr,
            )
            return 4
        print(_format_report(report))
        if not args.apply and (report.missing_outs or report.absent_positions):
            print("\nRe-run with --apply to persist this backfill.")

        print()
        enrich_report = enrich_comment_reason(registry, client, apply=args.apply)
        print(_format_enrich_report(enrich_report))
        if not args.apply and enrich_report.candidates:
            print("\nRe-run with --apply to persist this enrichment.")
    finally:
        try:
            mt5.shutdown()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
