"""tests/live/test_news_calendar.py -- the B2 static calendar loader.

Contract: any problem reading or parsing => None => the B2 gate fails closed.
A valid header with zero rows is NOT a problem: it means "no events".
"""
from __future__ import annotations

from datetime import datetime, timezone

from sentinel_engine.live import news_calendar

HEADER = "utc_datetime,label\n"


def _write(tmp_path, text):
    p = tmp_path / "cal.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_missing_file_is_fail_closed(tmp_path):
    assert news_calendar.load_windows(tmp_path / "nope.csv",
                                      minutes_before=30, minutes_after=30) is None


def test_missing_header_column_is_fail_closed(tmp_path):
    p = _write(tmp_path, "when,label\n2026-07-27T12:30:00Z,NFP\n")
    assert news_calendar.load_windows(p, minutes_before=30, minutes_after=30) is None


def test_unparseable_timestamp_is_fail_closed(tmp_path):
    p = _write(tmp_path, HEADER + "not-a-date,NFP\n")
    assert news_calendar.load_windows(p, minutes_before=30, minutes_after=30) is None


def test_valid_header_zero_rows_means_no_events(tmp_path):
    p = _write(tmp_path, HEADER)
    assert news_calendar.load_windows(p, minutes_before=30, minutes_after=30) == ()


def test_row_becomes_a_symmetric_window(tmp_path):
    p = _write(tmp_path, HEADER + "2026-07-27T12:30:00Z,US NFP\n")
    windows = news_calendar.load_windows(p, minutes_before=30, minutes_after=30)
    assert windows == ((datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
                        datetime(2026, 7, 27, 13, 0, tzinfo=timezone.utc)),)


def test_naive_timestamps_are_read_as_utc(tmp_path):
    p = _write(tmp_path, HEADER + "2026-07-27T12:30:00,US NFP\n")
    windows = news_calendar.load_windows(p, minutes_before=10, minutes_after=10)
    assert windows[0][0] == datetime(2026, 7, 27, 12, 20, tzinfo=timezone.utc)


def test_windows_come_back_sorted(tmp_path):
    p = _write(tmp_path, HEADER
               + "2026-07-29T18:00:00Z,FOMC\n"
               + "2026-07-27T12:30:00Z,NFP\n")
    windows = news_calendar.load_windows(p, minutes_before=30, minutes_after=30)
    assert [w[0] for w in windows] == sorted(w[0] for w in windows)


def test_blank_lines_are_ignored(tmp_path):
    p = _write(tmp_path, HEADER + "\n2026-07-27T12:30:00Z,NFP\n\n")
    assert len(news_calendar.load_windows(p, minutes_before=5, minutes_after=5)) == 1


def test_the_committed_calendar_is_loadable():
    # THE DEPLOYMENT GUARD: if this fails, the challenger will not open on
    # Monday (fail-closed), so it must be caught here and not in production.
    windows = news_calendar.load_windows(minutes_before=30, minutes_after=30)
    assert windows is not None, "the committed calendar must parse"
    for start, end in windows:
        assert start < end
        assert start.tzinfo is not None
