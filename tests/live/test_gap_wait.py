"""tests/live/test_gap_wait.py -- B1's session/thin-spread state machine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel_engine.live import gap_wait
from sentinel_engine.live.gap_wait import GapWaitState, advance

T0 = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)


def test_first_thin_observation_starts_the_clock():
    s = advance(GapWaitState(None, None), now=T0, spread=0.5)
    assert s.spread_ok_since == T0
    assert s.last_seen == T0


def test_a_wide_spread_does_not_start_the_clock():
    s = advance(GapWaitState(None, None), now=T0, spread=0.6)
    assert s.spread_ok_since is None
    assert s.last_seen == T0


def test_a_missing_tick_does_not_start_the_clock():
    s = advance(GapWaitState(None, None), now=T0, spread=None)
    assert s.spread_ok_since is None


def test_the_clock_does_not_restart_when_the_spread_widens_again():
    s = advance(GapWaitState(None, None), now=T0, spread=0.5)
    s = advance(s, now=T0 + timedelta(minutes=5), spread=0.6)
    s = advance(s, now=T0 + timedelta(minutes=10), spread=0.5)
    assert s.spread_ok_since == T0, "the post-reopen clock runs once, continuously"


def test_a_session_gap_resets_the_clock():
    s = advance(GapWaitState(None, None), now=T0, spread=0.5)
    later = T0 + timedelta(minutes=90)          # >= SESSION_GAP_MINUTES
    s = advance(s, now=later, spread=0.6)
    assert s.spread_ok_since is None, "a 90-min gap is a new session"
    s = advance(s, now=later + timedelta(minutes=1), spread=0.5)
    assert s.spread_ok_since == later + timedelta(minutes=1)


def test_a_short_gap_is_not_a_session_boundary():
    s = advance(GapWaitState(None, None), now=T0, spread=0.5)
    s = advance(s, now=T0 + timedelta(minutes=59), spread=0.5)
    assert s.spread_ok_since == T0


def test_roundtrip_through_disk(tmp_path):
    p = tmp_path / "gap_wait_state.json"
    s = GapWaitState(last_seen=T0, spread_ok_since=T0 - timedelta(minutes=3))
    gap_wait.save(s, p)
    assert gap_wait.load(p) == s


def test_a_missing_state_file_loads_fresh(tmp_path):
    assert gap_wait.load(tmp_path / "nope.json") == GapWaitState(None, None)


def test_a_corrupt_state_file_loads_fresh_not_permissive(tmp_path):
    p = tmp_path / "gap_wait_state.json"
    p.write_text("{not json", encoding="utf-8")
    s = gap_wait.load(p)
    assert s.spread_ok_since is None, "corruption must deny, never admit"
