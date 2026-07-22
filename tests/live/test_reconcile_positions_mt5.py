"""tests/live/test_reconcile_positions_mt5.py — TDD for the MT5<->DB
position reconciler (`scripts/live/reconcile_positions_mt5.py`).

The reconciler is READ-ONLY toward MT5 (only `history_deals_get`-shaped
reads) and only ever BACKFILLS deals that actually exist in the MT5 history
into `deals_raw`. It never fabricates deals and never closes a position that
MT5 still reports open. Two backfill cases:

  1. MISSING OUT: a position the DB has as an IN with no OUT, but which MT5
     history shows CLOSED (>=1 OUT deal). The reconciler inserts the missing
     OUT deal(s), inheriting strategy_id/variant_id from the position's IN
     (SL/TP closes arrive with magic=0 -> would otherwise be human/NULL).

  2. ABSENT POSITION: a position present in MT5 history (IN+OUT) with NO deal
     at all in the DB. The reconciler inserts both, attributing via magic
     (`ResearchRegistry.lookup_magic`) exactly like DealsWatcher.

Genuinely-open positions (IN in DB, no OUT in MT5 either) are left untouched.
`--apply` is idempotent: running twice yields the same rows, no duplicates
(dedup by the natural key, `ticket`).

Everything here runs offline against a tmp DB + a stub MT5 client; no real
`MetaTrader5` import.
"""
from __future__ import annotations

import sqlite3

import pytest

from scripts.live import reconcile_positions_mt5 as rec
from sentinel_engine.research.registry2 import ResearchRegistry


class _StubMt5Client:
    """`history_deals_get(from_ts, to_ts)` returning a fixed list of deal
    dicts (same shape DealsWatcher consumes). Records call count + the
    `from_ts` of the last call so tests can assert reads happened / didn't
    and that the fetch window was bounded (never epoch-0)."""

    def __init__(self, deals):
        self._deals = deals
        self.calls = 0
        self.last_from_ts = None

    def history_deals_get(self, from_ts, to_ts):
        self.calls += 1
        self.last_from_ts = from_ts
        return list(self._deals)


def _deal(ticket, position_id, entry_type, *, magic, strategy_id=None,
          symbol="XAUUSD", side="BUY", volume=0.1, price=2400.0,
          profit=0.0, time=1784660000, origin=None, variant_id=None,
          comment=None, reason=None):
    return {
        "ticket": ticket, "position_id": position_id, "symbol": symbol,
        "side": side, "volume": volume, "price": price, "profit": profit,
        "magic": magic, "time": time, "entry_type": entry_type,
        "origin": origin, "strategy_id": strategy_id, "variant_id": variant_id,
        "leverage": None, "contract_size": None,
        "comment": comment, "reason": reason,
    }


@pytest.fixture
def reg(tmp_path):
    r = ResearchRegistry(tmp_path / "research.db")
    # Register a magic->strategy allocation so absent-position attribution
    # resolves like DealsWatcher does. Insert directly to control the exact
    # magic value (allocate_magic derives magic from strategy/variant seq).
    conn = r._connect()
    try:
        conn.execute(
            "INSERT INTO magic_allocation(magic, strategy_id, variant_id, asignado) "
            "VALUES (?, ?, ?, ?)",
            (724011, "SAR::S6-K2P0", "v1", "2026-07-21T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()
    return r


def _insert_deal(reg, d):
    cols = ("ticket", "position_id", "symbol", "side", "volume", "price",
            "profit", "magic", "time", "entry_type", "origin", "strategy_id",
            "variant_id")
    conn = reg._connect()
    try:
        conn.execute(
            f"INSERT INTO deals_raw({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})",
            tuple(d[c] for c in cols),
        )
        conn.commit()
    finally:
        conn.close()


def _rows(reg):
    conn = sqlite3.connect(str(reg.db_path))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM deals_raw ORDER BY ticket").fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Case 1: missing OUT is backfilled, inheriting strategy_id by position_id.
# ---------------------------------------------------------------------------
def test_missing_out_backfilled_inherits_strategy(reg):
    # DB has the IN (strategy-attributed), no OUT.
    _insert_deal(reg, _deal(9001, 55167593, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy"))
    # MT5 history shows the IN AND a magic=0 SL/TP-close OUT.
    client = _StubMt5Client([
        _deal(9001, 55167593, "IN", magic=724011),
        _deal(9002, 55167593, "OUT", magic=0, profit=-5.0, time=1784665000),
    ])

    report = rec.reconcile(reg, client, apply=True)

    rows = _rows(reg)
    assert len(rows) == 2
    out = next(r for r in rows if r["ticket"] == 9002)
    assert out["entry_type"] == "OUT"
    # Inherited strategy attribution from the position's IN (not human/NULL).
    assert out["strategy_id"] == "SAR::S6-K2P0"
    assert out["origin"] == "strategy"
    assert report.missing_outs == 1


# ---------------------------------------------------------------------------
# Case 2: a position absent from the DB is inserted with IN+OUT + attribution.
# ---------------------------------------------------------------------------
def test_absent_position_backfilled_in_and_out(reg):
    # DB empty. MT5 shows a full position (IN 724011 -> strategy, OUT magic=0).
    client = _StubMt5Client([
        _deal(8001, 55160000, "IN", magic=724011, time=1784660000),
        _deal(8002, 55160000, "OUT", magic=0, profit=3.0, time=1784661000),
    ])

    report = rec.reconcile(reg, client, apply=True)

    rows = _rows(reg)
    assert len(rows) == 2
    in_row = next(r for r in rows if r["ticket"] == 8001)
    out_row = next(r for r in rows if r["ticket"] == 8002)
    assert in_row["strategy_id"] == "SAR::S6-K2P0"
    assert in_row["origin"] == "strategy"
    # OUT inherits from the position's IN by position_id.
    assert out_row["strategy_id"] == "SAR::S6-K2P0"
    assert out_row["origin"] == "strategy"
    assert report.absent_positions == 1


# ---------------------------------------------------------------------------
# Case 3: a genuinely-open position (no OUT in MT5) is NOT touched.
# ---------------------------------------------------------------------------
def test_genuinely_open_position_not_touched(reg):
    _insert_deal(reg, _deal(7001, 55167616, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy"))
    # MT5 shows only the IN -- still open.
    client = _StubMt5Client([_deal(7001, 55167616, "IN", magic=724011)])

    before = _rows(reg)
    report = rec.reconcile(reg, client, apply=True)
    after = _rows(reg)

    assert before == after  # nothing invented
    assert report.missing_outs == 0
    assert report.absent_positions == 0
    # No OUT fabricated for the open position.
    assert all(r["entry_type"] != "OUT" for r in after)


# ---------------------------------------------------------------------------
# Case 4: --apply twice is idempotent (dedup by ticket, no duplicates).
# ---------------------------------------------------------------------------
def test_apply_is_idempotent(reg):
    _insert_deal(reg, _deal(9001, 55167593, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy"))
    client = _StubMt5Client([
        _deal(9001, 55167593, "IN", magic=724011),
        _deal(9002, 55167593, "OUT", magic=0, profit=-5.0, time=1784665000),
    ])

    rec.reconcile(reg, client, apply=True)
    first = _rows(reg)
    rec.reconcile(reg, client, apply=True)
    second = _rows(reg)

    assert first == second
    assert len(second) == 2  # no duplicate OUT
    assert sum(1 for r in second if r["ticket"] == 9002) == 1


# ---------------------------------------------------------------------------
# Case 5: dry-run (apply=False) writes nothing but reports the backfill plan.
# ---------------------------------------------------------------------------
def test_dry_run_writes_nothing(reg):
    _insert_deal(reg, _deal(9001, 55167593, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy"))
    client = _StubMt5Client([
        _deal(9001, 55167593, "IN", magic=724011),
        _deal(9002, 55167593, "OUT", magic=0, profit=-5.0, time=1784665000),
    ])

    report = rec.reconcile(reg, client, apply=False)

    rows = _rows(reg)
    assert len(rows) == 1  # still just the IN; nothing written
    assert report.missing_outs == 1
    assert report.applied is False
    # The plan lists the position + which OUT ticket(s) would be inserted.
    assert 55167593 in report.plan_out_tickets
    assert 9002 in report.plan_out_tickets[55167593]


# ---------------------------------------------------------------------------
# Case 6 (SAFETY): an empty history fetch WITH open positions in the DB is a
# BROKEN FETCH, not "consistent". The reconciler must NOT report clean -- it
# raises so `main()` can exit non-zero instead of printing "DB consistent".
# ---------------------------------------------------------------------------
def test_empty_history_with_open_positions_is_fetch_failure(reg):
    # DB has an OPEN position (IN, no OUT) -- genuinely tracked.
    _insert_deal(reg, _deal(9001, 55167593, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy"))
    # MT5 history returns EMPTY (the from_ts=0.0 far-past empty-return bug).
    client = _StubMt5Client([])

    with pytest.raises(rec.ReconcileFetchError):
        rec.reconcile(reg, client, apply=True)

    # Nothing was written / closed despite the empty history.
    assert len(_rows(reg)) == 1


# ---------------------------------------------------------------------------
# Case 7 (SAFETY): an empty history fetch with NO open positions in the DB is
# genuinely nothing-to-do -- must NOT raise (empty DB, empty MT5 = consistent).
# ---------------------------------------------------------------------------
def test_empty_history_no_open_positions_is_ok(reg):
    client = _StubMt5Client([])
    report = rec.reconcile(reg, client, apply=True)  # no raise
    assert report.missing_outs == 0
    assert report.absent_positions == 0


# ---------------------------------------------------------------------------
# Case 8: the fetch window is BOUNDED (never epoch-0). With a DB deal present
# the reconciler bounds `from_ts` to the earliest DB deal time minus margin,
# so MT5's far-past empty-return can't blind it.
# ---------------------------------------------------------------------------
def test_fetch_from_ts_is_bounded_not_epoch_zero(reg):
    _insert_deal(reg, _deal(9001, 55167593, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy",
                            time=1784660000))
    client = _StubMt5Client([
        _deal(9001, 55167593, "IN", magic=724011, time=1784660000),
        _deal(9002, 55167593, "OUT", magic=0, profit=-5.0, time=1784665000),
    ])

    rec.reconcile(reg, client, apply=True)

    assert client.last_from_ts is not None
    assert client.last_from_ts > 0.0
    # Bounded to (earliest DB deal time - margin), i.e. below the IN time.
    assert client.last_from_ts < 1784660000


# ---------------------------------------------------------------------------
# Attribution-repair pass (Task 1, 2026-07-22): manual OUT closes (magic=0)
# already persisted as origin='human'/strategy_id=NULL, whose position's IN
# row is origin='strategy', must inherit strategy_id/variant_id/origin from
# that IN. Pure DB -- never touches MT5. Idempotent (second run finds 0).
# ---------------------------------------------------------------------------

def test_repair_attributes_human_out_when_in_is_strategy(reg):
    # IN is strategy-attributed; OUT is a manual close (magic=0), wrongly
    # persisted as origin='human'/strategy_id=NULL (the exact 2026-07-21 bug).
    _insert_deal(reg, _deal(55164867, 55164867, "IN", magic=724071,
                            strategy_id="SAR::SuperTrend-p14x3-M15",
                            variant_id="v1", origin="strategy"))
    _insert_deal(reg, _deal(55869675, 55164867, "OUT", magic=0,
                            profit=-100.0, time=1784692000,
                            origin="human", strategy_id=None, variant_id=None))

    report = rec.repair_attribution(reg, apply=True)

    row = next(r for r in _rows(reg) if r["ticket"] == 55869675)
    assert row["origin"] == "strategy"
    assert row["strategy_id"] == "SAR::SuperTrend-p14x3-M15"
    assert row["variant_id"] == "v1"
    assert report.repaired == 1
    assert report.candidates == [
        {"ticket": 55869675, "position_id": 55164867,
         "strategy_id": "SAR::SuperTrend-p14x3-M15"}
    ]


def test_repair_leaves_fully_manual_position_untouched(reg):
    # IN is ALSO magic=0/origin=human (a fully-manual position) -- must stay
    # untouched: there's no strategy IN to inherit from.
    _insert_deal(reg, _deal(55164773, 55164773, "IN", magic=0,
                            origin="human", strategy_id=None, variant_id=None))
    _insert_deal(reg, _deal(55869670, 55164773, "OUT", magic=0,
                            profit=50.0, time=1784692100,
                            origin="human", strategy_id=None, variant_id=None))

    before = _rows(reg)
    report = rec.repair_attribution(reg, apply=True)
    after = _rows(reg)

    assert before == after
    assert report.repaired == 0
    assert report.candidates == []


def test_repair_leaves_unallocated_human_in_positions_untouched(reg):
    # IN carries an unallocated 720xxx magic but origin='human' (not a
    # strategy magic) -- the manual OUT must NOT be repaired since the IN
    # itself is origin='human', not 'strategy'.
    _insert_deal(reg, _deal(55164999, 55164999, "IN", magic=720123,
                            origin="human", strategy_id=None, variant_id=None))
    _insert_deal(reg, _deal(55869671, 55164999, "OUT", magic=0,
                            profit=-20.0, time=1784692200,
                            origin="human", strategy_id=None, variant_id=None))

    before = _rows(reg)
    report = rec.repair_attribution(reg, apply=True)
    after = _rows(reg)

    assert before == after
    assert report.repaired == 0


def test_repair_dry_run_writes_nothing(reg):
    _insert_deal(reg, _deal(55165646, 55165646, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", variant_id="v1",
                            origin="strategy"))
    _insert_deal(reg, _deal(55869674, 55165646, "OUT", magic=0,
                            profit=30.0, time=1784692300,
                            origin="human", strategy_id=None, variant_id=None))

    report = rec.repair_attribution(reg, apply=False)

    row = next(r for r in _rows(reg) if r["ticket"] == 55869674)
    assert row["origin"] == "human"
    assert row["strategy_id"] is None
    assert report.applied is False
    assert report.repaired == 0  # nothing written
    assert report.candidates == [
        {"ticket": 55869674, "position_id": 55165646,
         "strategy_id": "SAR::S6-K2P0"}
    ]


def test_repair_apply_is_idempotent(reg):
    _insert_deal(reg, _deal(55165647, 55165647, "IN", magic=724012,
                            strategy_id="SAR::S7-TPNONE", variant_id="v1",
                            origin="strategy"))
    _insert_deal(reg, _deal(55869673, 55165647, "OUT", magic=0,
                            profit=15.0, time=1784692400,
                            origin="human", strategy_id=None, variant_id=None))

    rec.repair_attribution(reg, apply=True)
    first = _rows(reg)
    second_report = rec.repair_attribution(reg, apply=True)
    second = _rows(reg)

    assert first == second
    assert second_report.repaired == 0
    assert second_report.candidates == []


def test_repair_in_can_be_outside_time_window_no_time_bound_on_join(reg):
    # The IN row is far in the past (e.g. yesterday) -- the repair JOIN must
    # not be time-bounded on the IN side, only matched by position_id.
    _insert_deal(reg, _deal(55160001, 55160001, "IN", magic=724013,
                            strategy_id="SAR::V11-M2", variant_id="v1",
                            origin="strategy", time=1784500000))
    _insert_deal(reg, _deal(55869660, 55160001, "OUT", magic=0,
                            profit=-40.0, time=1784692500,
                            origin="human", strategy_id=None, variant_id=None))

    report = rec.repair_attribution(reg, apply=True)

    row = next(r for r in _rows(reg) if r["ticket"] == 55869660)
    assert row["origin"] == "strategy"
    assert row["strategy_id"] == "SAR::V11-M2"
    assert report.repaired == 1


# ---------------------------------------------------------------------------
# Enrichment pass (Task 2.3, 2026-07-22): backfills `comment`/`reason` from
# MT5 history for tickets already present in `deals_raw` where either column
# is still NULL. Requires MT5 (unlike `repair_attribution`). Idempotent:
# updates ONLY the NULL columns, never clobbers an already-filled value.
# ---------------------------------------------------------------------------

def test_enrich_fills_null_comment_and_reason_from_mt5(reg):
    _insert_deal(reg, _deal(9001, 55167593, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy"))
    client = _StubMt5Client([
        _deal(9001, 55167593, "IN", magic=724011,
              comment="[sl 2400.00]", reason=4),
    ])

    report = rec.enrich_comment_reason(reg, client, apply=True)

    row = next(r for r in _rows(reg) if r["ticket"] == 9001)
    assert row["comment"] == "[sl 2400.00]"
    assert row["reason"] == 4
    assert report.enriched == 1


def test_enrich_only_touches_rows_missing_comment_or_reason(reg):
    # Ticket already has BOTH comment and reason set -- must not be touched
    # (not even re-written with the same value) or counted as a candidate.
    conn = reg._connect()
    try:
        conn.execute(
            "INSERT INTO deals_raw(ticket, position_id, symbol, side, volume, "
            "price, profit, magic, time, entry_type, origin, strategy_id, "
            "variant_id, comment, reason) VALUES "
            "(9002, 55167594, 'XAUUSD', 'BUY', 0.1, 2400.0, 0.0, 724011, "
            "1784660000, 'IN', 'strategy', 'SAR::S6-K2P0', 'v1', "
            "'already-set', 3)"
        )
        conn.commit()
    finally:
        conn.close()
    client = _StubMt5Client([
        _deal(9002, 55167594, "IN", magic=724011,
              comment="[different]", reason=99),
    ])

    report = rec.enrich_comment_reason(reg, client, apply=True)

    row = next(r for r in _rows(reg) if r["ticket"] == 9002)
    assert row["comment"] == "already-set"
    assert row["reason"] == 3
    assert report.enriched == 0


def test_enrich_dry_run_writes_nothing(reg):
    _insert_deal(reg, _deal(9003, 55167595, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy"))
    client = _StubMt5Client([
        _deal(9003, 55167595, "IN", magic=724011,
              comment="[tp 2410.00]", reason=5),
    ])

    report = rec.enrich_comment_reason(reg, client, apply=False)

    row = next(r for r in _rows(reg) if r["ticket"] == 9003)
    assert row["comment"] is None
    assert row["reason"] is None
    assert report.applied is False
    assert report.enriched == 0
    assert report.candidates == [9003]


def test_enrich_is_idempotent(reg):
    _insert_deal(reg, _deal(9004, 55167596, "IN", magic=724011,
                            strategy_id="SAR::S6-K2P0", origin="strategy"))
    client = _StubMt5Client([
        _deal(9004, 55167596, "IN", magic=724011,
              comment="[sl 2400.00]", reason=4),
    ])

    rec.enrich_comment_reason(reg, client, apply=True)
    first = _rows(reg)
    second_report = rec.enrich_comment_reason(reg, client, apply=True)
    second = _rows(reg)

    assert first == second
    assert second_report.enriched == 0
