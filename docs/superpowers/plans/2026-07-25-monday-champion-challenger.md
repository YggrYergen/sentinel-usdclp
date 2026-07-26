# Monday Champion/Challenger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Tracker (state lives there, NOT here):** `docs/superpowers/plans/2026-07-25-monday-tracker.md` — update it at the end of every task.
> **Spec (authoritative source):** `docs/superpowers/specs/2026-07-25-monday-champion-challenger-design.md`

**Goal:** Ship, on machine-1 / DEMO 2883015767, a purely additive *challenger* sleeve — the same
S6/S7/SuperTrend signals byte-for-byte, plus an opt-in risk layer (B1–B4) — running alongside the
untouched *champion* sleeve, so Monday's live deployment generates paired A/B evidence without
re-tuning a single strategy parameter.

**Architecture:** One executor process, one account, two sleeves. Sleeve A = `CONFIGS_LOCAL`
exactly as it is today (zero changes). Sleeve B = `CONFIGS_CHALLENGER`, three deep-copied configs
in a fresh magic band (726010/726020/726070) at 0.02 lot, each carrying an **optional**
`cfg["risk_gates"]` dict. That key is the entire isolation mechanism: it is read only in the OPEN
path of `run_live_20.py`, exactly where `SPREAD_GATE_SKIP` already lives, and a config without the
key produces byte-identical decisions to today. The gate logic itself is a pure function in
`sentinel_engine/live/risk_gates.py` — no MT5, no clock, no filesystem — so it is fully unit-testable.

**Tech Stack:** Python 3.11+, stdlib only for the new live modules (`dataclasses`, `csv`, `json`,
`datetime`, `pathlib`). pytest for tests. numpy/pandas allowed **only** in `scripts/analysis/`
(Track A / Track C), never in the live path.

---

## Global Constraints

Every task's requirements implicitly include this section. Values are copied verbatim from the spec.

- **R1 — the S6/S7/ST signals are UNTOUCHABLE.** `CONFIGS_LOCAL` must be byte-identical after all
  work. No task may edit the shared go-live config dicts.
- **R1-bis — PRESERVATION IS ABSOLUTE (user ruling, 2026-07-25).** The S6, S7 and SuperTrend
  strategies that are running LIVE right now — their engines, their kwargs, their config dicts, and
  the code paths they execute — are preserved **byte-identical, as-is**. If any work in this or any
  later plan appears to require modifying them, the modification is made on an **independent copy**
  (deep-copied config, new module, new magic band) and **never** on the original. There is no
  exception, no "small edit", no "temporary" change. An implementer who believes the original must
  change is wrong about the task: STOP and escalate to the controller. This constraint binds every
  subagent dispatched under this plan and is repeated in every brief.
- **R2 — champion lot stays 0.1** (TK-Momentum 0.01). Challenger lot is **0.02**.
- **R3 — re-tuning ANY parameter is forbidden this weekend.** No grid, no sweep, no "best of".
- **R4 — the challenger is additive or it is nothing.** It may not mutate any shared object.
- **R5 — every number is computed by CODE, never by the LLM.** No hand-written metric anywhere.
- **Windows 10 AND 11 must both work:** `pathlib` only, explicit `encoding="utf-8"` on every file
  read/write, no OS-version APIs, no WSL assumptions.
- **Parity gate:** nothing in this plan may touch `simular_variant` or any scoring code. If a task
  seems to require it, STOP and escalate — the plan is wrong, not the parity gate.
- **ATTACH-ONLY:** no script launches an MT5 terminal. The user opens terminals by hand.
- **`guard_cuenta.assert_demo()`** already runs every cycle. Do not weaken or bypass it.
- **Retrospective masks VETO, they never SELECT.** A mask number may only ever justify *not*
  deploying a wrapper. Using it to choose between wrapper variants is re-tuning (violates R3).
- **Clock discipline:** `datetime.now(timezone.utc)` in this codebase is the **machine's real UTC**.
  MT5 bar timestamps are **broker server time**. The two are NOT the same clock. The gates use real
  UTC only; never mix a bar timestamp into a gate comparison.
- **Branch:** all work lands on `equipo1`. **Never commit to `alvaro`** (machine-2, Álvaro's repo).
- **Pre-existing red tests:** 2 failures in `tests/web/test_web_positions.py` ("Analizar" button) are
  NOT from this work and do not block it. Every other test must stay green.

---

## File Structure

**New files (all created by this plan):**

| Path | Responsibility |
|---|---|
| `sentinel_engine/live/risk_gates.py` | Pure gate logic: `GateInput`, `GateDecision`, `evaluate_open_gates`. No I/O. |
| `sentinel_engine/live/news_calendar.py` | Loads the committed static calendar into blackout windows; returns `None` on any problem (fail-closed signal). |
| `sentinel_engine/live/gap_wait.py` | B1 state machine + tiny JSON store: when did the thin-spread regime start after the last session reopen. |
| `data/live/news_calendar.csv` | The committed calendar (DATA, never generated at runtime). |
| `tests/live/test_risk_gates.py` | Unit tests for the four gates. |
| `tests/live/test_news_calendar.py` | Loader + fail-closed tests. |
| `tests/live/test_gap_wait.py` | State-machine + persistence tests. |
| `scripts/analysis/monday_audit/__init__.py` | Package marker for Track A. |
| `scripts/analysis/monday_audit/loader.py` | Loads the 3 positions CSVs into one merged, typed, chronologically sorted list. Shared by every Track-A task. |
| `scripts/analysis/monday_audit/a1_maxdd.py` … `a5_spread_gate.py` | One module per audit question. Each writes a JSON artifact. |
| `scripts/analysis/monday_audit/b6_masks.py` | The retrospective wrapper masks + verdict report. |
| `tests/analysis/test_monday_audit.py` | Unit tests for the audit maths on tiny synthetic fixtures. |

**Modified files:**

| Path | Change |
|---|---|
| `sentinel_engine/strategies/live_configs_20.py` | Append `CONFIGS_CHALLENGER` + its asserts, after `CONFIGS_LOCAL` (currently ends line 606). Nothing above is edited. |
| `scripts/live/run_live_20.py` | Add `risk_gates`/`gate_ctx` params to `execute_action`; add the gate block after `SPREAD_GATE_SKIP` (line 502); add `_build_gate_ctx` + the call in `run_cycle`; add the `local+challenger` roster branch. |
| `tests/scripts/test_run_live_20.py` | Append challenger roster, isolation and non-regression tests. |
| `docs/superpowers/plans/2026-07-25-monday-tracker.md` | Updated at the end of every task. |

---

## Dependency Graph & Dispatch Order

Doctrine D152 applies: **max 2 subagents in parallel**, implementers and investigators = **Sonnet 5
high**, only the hardest task = **Opus 5 medium**, briefs must be exhaustive, ~30 min / ~300k token
ceiling per subagent, tracker updated at the end of every task.

```
  Task 0 (safety tag)  ── must complete before ANY code change
        │
        ├── LANE A (read-only: scripts/analysis/**)   LANE B (live path: sentinel_engine + scripts/live)
        │     Task 6  audit loader                      Task 1  risk_gates.py
        │     Task 7  A1 maxDD                          Task 2  news_calendar.py + calendar data
        │     Task 8  A2 overlap ── B3 cap ──────┐      Task 3  gap_wait.py
        │     Task 9  A3+A4+A5 stats             └────► Task 4  CONFIGS_CHALLENGER  ◄ needs Task 8's number
        │                                               Task 5  executor plumbing   ◄ HARDEST (Opus 5 medium)
        │                                               Task 11 revert rehearsal
        └──────────────────────────────────────────────► Task 10 retrospective masks (needs 6, 8, 2)
                                                         Task 12 deploy (🙋 USER HANDS REQUIRED)
                                                         Task 13 document (needs 7, 8, 9, 10, 12)
                                                         Task 14 random-entry study (NON-BLOCKING)
```

**The two lanes touch disjoint files, so they are the 2 parallel subagents.** Within a lane, tasks
are strictly sequential. **Task 8 must land before Task 4 starts**; if lane B gets there first, it
waits rather than inventing the cap.

**Critical path to Monday:** 0 → (1,2,3 ‖ 6,8) → 4 → 5 → 10 → 11 → 12 → 13. Tasks 7, 9 and 14 are
off the critical path: 7 and 9 only feed the document, and 14 does not affect Monday at all.

---

## Task 0: Safety tag and revert point

**Files:**
- Create: none (git metadata only)

**Interfaces:**
- Produces: git tag `pre-challenger-2026-07-25` pointing at the currently-live commit. Task 7 (revert
  rehearsal) and any Monday rollback both depend on this tag existing.

- [ ] **Step 1: Confirm the working tree state and the live commit**

```bash
git -C D:/FOREX branch --show-current   # must print: equipo1
git -C D:/FOREX log -1 --format="%H %s"  # expect 496fecf... docs(spec): monday champion/challenger additive design
git -C D:/FOREX status --porcelain -uno  # must be EMPTY (untracked docs/*.pdf etc. are fine)
```

Expected: branch `equipo1`, HEAD `496fecf`, no tracked modifications. If tracked files are dirty,
STOP and report — do not stash, do not commit someone else's work.

- [ ] **Step 2: Create the annotated tag**

```bash
git -C D:/FOREX tag -a pre-challenger-2026-07-25 -m "Live machine-1 state before the challenger sleeve (rollback point for the 2026-07-27 delivery)"
```

- [ ] **Step 3: Verify the tag resolves to the live commit**

```bash
git -C D:/FOREX rev-parse pre-challenger-2026-07-25^{commit}
```

Expected: prints the same SHA as Step 1's HEAD.

- [ ] **Step 4: Record it in the tracker**

Set Task 0 to `[x]` in `docs/superpowers/plans/2026-07-25-monday-tracker.md` and write the resolved
SHA into the "Rollback point" line. Commit:

```bash
git -C D:/FOREX add docs/superpowers/plans/2026-07-25-monday-tracker.md
git -C D:/FOREX commit -m "chore(tracker): rollback tag pre-challenger-2026-07-25 recorded"
```

---

## Task 1: `risk_gates.py` â€” the four gates as pure logic

**Files:**
- Create: `sentinel_engine/live/risk_gates.py`
- Test: `tests/live/test_risk_gates.py`

**Interfaces:**
- Consumes: nothing (leaf module, stdlib only).
- Produces:
  - `GateInput(now: datetime, spread_ok_since: datetime | None, open_fichas: int, desired_sl: float | None, market_ref: float | None, news_windows: tuple[tuple[datetime, datetime], ...] | None)` â€” frozen dataclass.
  - `GateDecision(allow: bool, gate: str, reason: str)` â€” frozen dataclass.
  - `evaluate_open_gates(gates: dict[str, Any] | None, gi: GateInput) -> GateDecision`.
  - Gate keys, exact spelling: `gap_wait_minutes` (B1), `news_blackout_minutes` (B2),
    `max_open_fichas` (B3), `min_sl_distance` (B4). Tasks 4 and 5 use these names verbatim.

- [ ] **Step 1: Write the failing tests**

Create `tests/live/test_risk_gates.py`:

```python
"""tests/live/test_risk_gates.py -- the challenger sleeve's four OPEN gates.

Pure logic: no MT5, no clock, no filesystem. The champion sleeve never reaches
this module (it has no `risk_gates` key), which the empty-dict test pins down.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sentinel_engine.live.risk_gates import GateInput, evaluate_open_gates

T0 = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def _gi(**over):
    base = dict(now=T0, spread_ok_since=T0 - timedelta(minutes=90), open_fichas=0,
                desired_sl=3900.0, market_ref=4000.0, news_windows=())
    base.update(over)
    return GateInput(**base)


def test_no_gates_always_allows():
    # THE CHAMPION'S GUARANTEE: an absent/empty risk_gates dict is a no-op.
    for gates in ({}, None):
        d = evaluate_open_gates(gates, _gi(spread_ok_since=None, open_fichas=999,
                                           desired_sl=None, market_ref=None,
                                           news_windows=None))
        assert d.allow is True
        assert d.gate == ""


def test_b1_denies_before_the_wait_elapses():
    d = evaluate_open_gates({"gap_wait_minutes": 50},
                            _gi(spread_ok_since=T0 - timedelta(minutes=49)))
    assert d.allow is False and d.gate == "B1"
    assert "49.0 of 50" in d.reason


def test_b1_allows_once_the_wait_elapsed():
    d = evaluate_open_gates({"gap_wait_minutes": 50},
                            _gi(spread_ok_since=T0 - timedelta(minutes=50)))
    assert d.allow is True


def test_b1_denies_when_the_thin_regime_never_started():
    d = evaluate_open_gates({"gap_wait_minutes": 50}, _gi(spread_ok_since=None))
    assert d.allow is False and d.gate == "B1"


def test_b2_fails_closed_without_a_calendar():
    d = evaluate_open_gates({"news_blackout_minutes": 30}, _gi(news_windows=None))
    assert d.allow is False and d.gate == "B2"
    assert "fail-closed" in d.reason


def test_b2_denies_inside_a_window_and_allows_outside():
    win = ((T0 - timedelta(minutes=5), T0 + timedelta(minutes=25)),)
    assert evaluate_open_gates({"news_blackout_minutes": 30},
                               _gi(news_windows=win)).allow is False
    far = ((T0 + timedelta(hours=3), T0 + timedelta(hours=4)),)
    assert evaluate_open_gates({"news_blackout_minutes": 30},
                               _gi(news_windows=far)).allow is True


def test_b2_boundaries_are_inclusive():
    win = ((T0, T0 + timedelta(minutes=30)),)
    assert evaluate_open_gates({"news_blackout_minutes": 30},
                               _gi(now=T0, news_windows=win)).allow is False
    assert evaluate_open_gates({"news_blackout_minutes": 30},
                               _gi(now=T0 + timedelta(minutes=30),
                                   news_windows=win)).allow is False


def test_b3_denies_at_and_above_the_cap():
    assert evaluate_open_gates({"max_open_fichas": 3}, _gi(open_fichas=2)).allow is True
    d = evaluate_open_gates({"max_open_fichas": 3}, _gi(open_fichas=3))
    assert d.allow is False and d.gate == "B3"


def test_b4_flags_an_illegal_sl_as_a_bug():
    d = evaluate_open_gates({"min_sl_distance": 0.5},
                            _gi(desired_sl=3999.7, market_ref=4000.0))
    assert d.allow is False and d.gate == "B4"
    assert "THIS IS A BUG" in d.reason


def test_b4_allows_a_legal_sl_on_either_side():
    assert evaluate_open_gates({"min_sl_distance": 0.5},
                               _gi(desired_sl=3999.4, market_ref=4000.0)).allow is True
    assert evaluate_open_gates({"min_sl_distance": 0.5},
                               _gi(desired_sl=4000.6, market_ref=4000.0)).allow is True


def test_b4_fails_closed_when_it_cannot_verify():
    d = evaluate_open_gates({"min_sl_distance": 0.5}, _gi(desired_sl=None))
    assert d.allow is False and d.gate == "B4"


def test_gate_order_is_b1_b2_b3_b4():
    # All four would deny; the reported gate must be the FIRST in order, so the
    # audit log always names the outermost reason.
    gates = {"gap_wait_minutes": 50, "news_blackout_minutes": 30,
             "max_open_fichas": 1, "min_sl_distance": 0.5}
    d = evaluate_open_gates(gates, _gi(spread_ok_since=None, news_windows=None,
                                       open_fichas=5, desired_sl=None))
    assert d.gate == "B1"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/live/test_risk_gates.py -v`
Expected: collection error â€” `ModuleNotFoundError: No module named 'sentinel_engine.live.risk_gates'`.

- [ ] **Step 3: Write the implementation**

Create `sentinel_engine/live/risk_gates.py`:

```python
"""sentinel_engine/live/risk_gates.py -- OPT-IN opening gates for the
CHALLENGER sleeve (2026-07-25 Monday delivery, spec section 4.3).

THE ISOLATION CONTRACT: a config WITHOUT a `risk_gates` key never reaches this
module, so the champion sleeve's OPEN decisions stay byte-identical to what has
been running in production. Everything here is a PURE function of an immutable
`GateInput` -- no MT5, no clock, no filesystem -- so the whole risk layer is
unit-testable without a terminal.

The four gates, evaluated in this fixed order (the FIRST denial is the one
reported, so the audit log always names the outermost reason):

  B1 `gap_wait_minutes`      -- do not open until N minutes after the spread
                                first printed thin following a session reopen.
  B2 `news_blackout_minutes` -- do not open inside +/-N min of a calendar event.
                                FAIL-CLOSED: no calendar => no opens.
  B3 `max_open_fichas`       -- cap simultaneous fichas in the sleeve. Expressed
                                in FICHAS, so it is independent of lot size.
  B4 `min_sl_distance`       -- refuse an SL closer to market than the broker
                                minimum. A hit here is a BUG, not a filter.

A key that is absent is a gate that is not evaluated. NEVER add a gate key to a
shared config dict (that would leak into the champion) -- see live_configs_20.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GateInput:
    """Everything the gates need, captured once per OPEN decision.

    `now` is REAL UTC (the machine clock), never an MT5 bar timestamp -- the
    broker's server clock is a different clock and mixing them silently shifts
    every news window by hours.
    """
    now: datetime
    spread_ok_since: datetime | None
    open_fichas: int
    desired_sl: float | None
    market_ref: float | None
    news_windows: tuple[tuple[datetime, datetime], ...] | None


@dataclass(frozen=True)
class GateDecision:
    allow: bool
    gate: str
    reason: str


_ALLOW = GateDecision(True, "", "all gates passed")


def evaluate_open_gates(gates: dict[str, Any] | None, gi: GateInput) -> GateDecision:
    """Decide whether ONE new position may be opened. Never raises for ordinary
    inputs; callers still wrap it fail-closed (a bug in the challenger's risk
    layer must never abort the champion's cycle)."""
    if not gates:
        return _ALLOW

    wait_min = gates.get("gap_wait_minutes")
    if wait_min is not None:
        if gi.spread_ok_since is None:
            return GateDecision(
                False, "B1",
                f"gap-wait: the thin-spread regime has not started since the "
                f"session reopened (need {wait_min} min after it does)")
        waited = (gi.now - gi.spread_ok_since).total_seconds() / 60.0
        if waited < wait_min:
            return GateDecision(
                False, "B1",
                f"gap-wait: only {waited:.1f} of {wait_min} min elapsed since "
                f"spread went thin at {gi.spread_ok_since.isoformat()}")

    blackout_min = gates.get("news_blackout_minutes")
    if blackout_min is not None:
        if gi.news_windows is None:
            return GateDecision(
                False, "B2",
                "news calendar missing or unreadable -> fail-closed (the "
                "challenger does not open without a calendar)")
        for start, end in gi.news_windows:
            if start <= gi.now <= end:
                return GateDecision(
                    False, "B2",
                    f"inside news blackout {start.isoformat()}..{end.isoformat()} "
                    f"(+/-{blackout_min} min, by convention -- never tuned)")

    cap = gates.get("max_open_fichas")
    if cap is not None and gi.open_fichas >= cap:
        return GateDecision(
            False, "B3",
            f"exposure cap: {gi.open_fichas} fichas already open in the sleeve "
            f"(cap {cap})")

    min_dist = gates.get("min_sl_distance")
    if min_dist is not None:
        if gi.desired_sl is None or gi.market_ref is None:
            return GateDecision(
                False, "B4",
                "SL legality unverifiable (no desired SL or no market ref) "
                "-> fail-closed")
        dist = abs(gi.market_ref - gi.desired_sl)
        if dist < min_dist:
            return GateDecision(
                False, "B4",
                f"ILLEGAL SL: distance {dist:.5f} < broker minimum "
                f"{min_dist:.5f} (sl={gi.desired_sl} ref={gi.market_ref}) -- "
                f"THIS IS A BUG, investigate; do not 'compensate' with a filter")

    return _ALLOW
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/live/test_risk_gates.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git -C D:/FOREX add sentinel_engine/live/risk_gates.py tests/live/test_risk_gates.py
git -C D:/FOREX commit -m "feat(live): challenger risk gates B1-B4 as pure opt-in logic"
```

- [ ] **Step 6: Update the tracker** â€” set Task 1 to `[x]`, note "12 tests green", commit the tracker.

---

## Task 2: `news_calendar.py` + the committed calendar (B2's data)

**Files:**
- Create: `sentinel_engine/live/news_calendar.py`
- Create: `data/live/news_calendar.csv`
- Test: `tests/live/test_news_calendar.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_windows(path: str | Path = CALENDAR_PATH, *, minutes_before: int, minutes_after: int) -> tuple[tuple[datetime, datetime], ...] | None`.
  Task 5 calls it and hands the result straight to `GateInput.news_windows`. **`None` means
  "unreadable" and Task 1's B2 gate turns that into a denial.** An empty tuple means "readable,
  no events" and is NOT a denial.

**Read this before writing code â€” the two traps:**

1. **Clock.** The `utc_datetime` column is **real UTC**, the same clock as
   `datetime.now(timezone.utc)`. It is NOT MT5 broker server time. Do not convert anything.
2. **Fail-closed vs empty.** A missing file, an unreadable file, a wrong/missing header, or an
   unparseable timestamp all return `None` (the challenger then refuses to open â€” spec Â§6). A file
   with a valid header and zero data rows returns `()` and the challenger trades normally. This
   distinction is deliberate: corruption must stop trading, an genuinely quiet week must not.

- [ ] **Step 1: Write the failing tests**

Create `tests/live/test_news_calendar.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/live/test_news_calendar.py -v`
Expected: collection error â€” `ImportError: cannot import name 'news_calendar'`.

- [ ] **Step 3: Write the implementation**

Create `sentinel_engine/live/news_calendar.py`:

```python
"""sentinel_engine/live/news_calendar.py -- the STATIC, COMMITTED news
calendar behind the challenger's B2 blackout gate (spec section 4.3).

DATA, NOT A KNOB. The file is committed to the repo and read at runtime; it is
never generated, fetched or tuned. The +/-30 min window is a CONVENTION fixed by
the spec -- choosing it from a backtest sweep would be re-tuning (violates R3).

FAIL-CLOSED CONTRACT: a missing file, an unreadable file, a wrong header or an
unparseable timestamp all return None, and `risk_gates.evaluate_open_gates`
turns None into "do not open". A valid header with zero data rows returns an
empty tuple -- readable, simply no events -- and does NOT stop trading.

CLOCK: `utc_datetime` is REAL UTC (same clock as datetime.now(timezone.utc)),
NOT MT5 broker server time. A naive timestamp is read as UTC.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

CALENDAR_PATH = (Path(__file__).resolve().parents[2]
                 / "data" / "live" / "news_calendar.csv")

_REQUIRED_COLUMN = "utc_datetime"


def load_windows(path: str | Path = CALENDAR_PATH, *,
                 minutes_before: int,
                 minutes_after: int
                 ) -> tuple[tuple[datetime, datetime], ...] | None:
    """Blackout windows built from the committed calendar, sorted by start.
    Returns None on ANY read/parse problem (the fail-closed signal)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        reader = csv.DictReader(text.splitlines())
        if reader.fieldnames is None or _REQUIRED_COLUMN not in reader.fieldnames:
            return None
        windows: list[tuple[datetime, datetime]] = []
        for row in reader:
            raw = (row.get(_REQUIRED_COLUMN) or "").strip()
            if not raw:
                continue  # blank line
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts = ts.astimezone(timezone.utc)
            windows.append((ts - timedelta(minutes=minutes_before),
                            ts + timedelta(minutes=minutes_after)))
    except (ValueError, TypeError, csv.Error):
        return None
    return tuple(sorted(windows))
```

- [ ] **Step 4: Create the committed calendar**

Create `data/live/news_calendar.csv`. **Source of the rows, in priority order:**

1. If `data/live/news_calendar_source.md` exists (the user may drop an export there), transcribe
   its events into the CSV. Convert every timestamp to real UTC in the file itself.
2. Otherwise seed it with the **rule-defined, fixed-clock** US releases only â€” these are published
   conventions, not tuned choices: **US Non-Farm Payrolls, first Friday of each month, 12:30 UTC**
   (08:30 America/New_York; the release time is fixed, the date rule is fixed).

Write the file with this exact header and at minimum the NFP rows covering 2026-08 and 2026-09 so
the gate has coverage past Monday:

```csv
utc_datetime,label
2026-08-07T12:30:00Z,US Non-Farm Payrolls (first-Friday rule, 08:30 ET)
2026-09-04T12:30:00Z,US Non-Farm Payrolls (first-Friday rule, 08:30 ET)
```

Then add a sibling `data/live/news_calendar.README.md` stating, in one paragraph: the file is data;
the window is Â±30 min by convention; rows are real UTC; **missing events mean B2 under-protects,
never over-protects**; and the user should extend it with CPI/FOMC/PPI dates, which are irregular
and cannot be rule-generated.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/live/test_news_calendar.py -v`
Expected: 9 passed (including `test_the_committed_calendar_is_loadable`).

- [ ] **Step 6: Commit**

```bash
git -C D:/FOREX add sentinel_engine/live/news_calendar.py tests/live/test_news_calendar.py data/live/news_calendar.csv data/live/news_calendar.README.md
git -C D:/FOREX commit -m "feat(live): static news calendar loader for the B2 blackout gate (fail-closed)"
```

- [ ] **Step 7: Update the tracker** â€” set Task 2 to `[x]` and record, verbatim, which source was used
  (user file vs NFP rule) and the **date range the calendar covers**. Task 6 needs that range and the
  document (Task 11) must state it honestly.

---

## Task 3: `gap_wait.py` â€” B1's session state machine

**Files:**
- Create: `sentinel_engine/live/gap_wait.py`
- Test: `tests/live/test_gap_wait.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `GapWaitState(last_seen: datetime | None, spread_ok_since: datetime | None)` â€” frozen dataclass.
  - `advance(state, *, now, spread, thin_spread=THIN_SPREAD, session_gap_minutes=SESSION_GAP_MINUTES) -> GapWaitState`.
  - `load(path=STATE_PATH) -> GapWaitState` and `save(state, path=STATE_PATH) -> None`.
  - Constants `THIN_SPREAD = 0.5`, `SESSION_GAP_MINUTES = 60`, `STATE_PATH`.
  Task 5 calls `load` â†’ `advance` â†’ `save` once per cycle and passes `state.spread_ok_since`
  into `GateInput`.

**The semantics, precisely:**

- A **session boundary** is detected when the previous observation is `SESSION_GAP_MINUTES` or more
  in the past (the executor was down, or the broker disabled XAUUSD over the weekend). Crossing one
  resets `spread_ok_since` to `None` â€” the wait clock restarts.
- The clock **starts** at the first observation with `spread <= thin_spread`.
- The clock **does not restart** if the spread later widens again. The spec's rule is "â‰¥50 min after
  the spread comes down following the reopen", not "50 consecutive thin minutes".
- A corrupt or missing state file yields a fresh state (`spread_ok_since=None`), which denies opens
  until 50 min of post-reopen thin spread accumulate. That is the conservative direction.

- [ ] **Step 1: Write the failing tests**

Create `tests/live/test_gap_wait.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/live/test_gap_wait.py -v`
Expected: collection error â€” `ImportError: cannot import name 'gap_wait'`.

- [ ] **Step 3: Write the implementation**

Create `sentinel_engine/live/gap_wait.py`:

```python
"""sentinel_engine/live/gap_wait.py -- B1's state: how long the thin-spread
regime has held since the market last reopened (spec section 4.3, B1).

WHY IT EXISTS: XAUUSD is disabled by the broker around 05-06 server time and
over the weekend; the first candles after a reopen are tainted by the gap
(see the project's `xauusd-market-open-gap-wait` lesson). B1 refuses to open
until 50 minutes after the spread first comes back down to the thin regime.

The 50 comes from that earlier diagnosis, NOT from a sweep run this weekend.

SEMANTICS
  * A SESSION BOUNDARY is any gap of >= SESSION_GAP_MINUTES since the previous
    observation (executor down, or market closed). Crossing one resets the clock.
  * The clock STARTS at the first observation with spread <= THIN_SPREAD.
  * The clock DOES NOT restart if the spread later widens: the rule is "50 min
    after the spread comes down", not "50 consecutive thin minutes".
  * A missing/corrupt state file loads FRESH (spread_ok_since=None), which
    DENIES opens until the wait accumulates. Corruption must never admit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

THIN_SPREAD = 0.5
SESSION_GAP_MINUTES = 60

STATE_PATH = (Path(__file__).resolve().parents[2]
              / "data" / "live" / "gap_wait_state.json")


@dataclass(frozen=True)
class GapWaitState:
    last_seen: datetime | None = None
    spread_ok_since: datetime | None = None


def advance(state: GapWaitState, *, now: datetime, spread: float | None,
            thin_spread: float = THIN_SPREAD,
            session_gap_minutes: int = SESSION_GAP_MINUTES) -> GapWaitState:
    """Fold one cycle's observation into the state. Pure."""
    spread_ok_since = state.spread_ok_since
    if (state.last_seen is None
            or (now - state.last_seen) >= timedelta(minutes=session_gap_minutes)):
        spread_ok_since = None  # a new session started; restart the wait clock
    if spread_ok_since is None and spread is not None and spread <= thin_spread:
        spread_ok_since = now
    return GapWaitState(last_seen=now, spread_ok_since=spread_ok_since)


def _parse(raw: str | None) -> datetime | None:
    if not raw:
        return None
    ts = datetime.fromisoformat(raw)
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def load(path: str | Path = STATE_PATH) -> GapWaitState:
    """Read the persisted state. ANY problem -> a fresh (denying) state."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return GapWaitState(last_seen=_parse(data.get("last_seen")),
                            spread_ok_since=_parse(data.get("spread_ok_since")))
    except (OSError, ValueError, TypeError, AttributeError):
        return GapWaitState(None, None)


def save(state: GapWaitState, path: str | Path = STATE_PATH) -> None:
    """Best-effort persist. A write failure must NEVER abort a trading cycle:
    the next cycle simply reloads a fresh (conservative) state."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "last_seen": state.last_seen.isoformat() if state.last_seen else None,
            "spread_ok_since": (state.spread_ok_since.isoformat()
                                if state.spread_ok_since else None),
        }), encoding="utf-8")
    except OSError:
        pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/live/test_gap_wait.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git -C D:/FOREX add sentinel_engine/live/gap_wait.py tests/live/test_gap_wait.py
git -C D:/FOREX commit -m "feat(live): gap-wait session state machine behind the B1 gate"
```

- [ ] **Step 6: Update the tracker** â€” set Task 3 to `[x]`, note "9 tests green".

---

## Task 4: `CONFIGS_CHALLENGER` â€” the mirrored roster

**Depends on:** Task A2 (it supplies `max_open_fichas`). If A2 has not landed, STOP and wait â€” do
not invent the number.

**Files:**
- Modify: `sentinel_engine/strategies/live_configs_20.py` â€” **APPEND ONLY**, after the `CONFIGS_LOCAL`
  block that currently ends at line 606. Do not edit a single line above it.
- Test: `tests/scripts/test_run_live_20.py` â€” append tests at the end.

**Interfaces:**
- Consumes: `_LOCAL_GOLIVE_IDS`, `_golive_by_id_for_local`, `_live_band`, `_shadow_band`,
  `_golive_band`, `_tk_band`, `_tk_bw2_band` (all already defined in the module);
  `A2_MAX_SIMULTANEOUS_FICHAS` from `data/analysis/monday_audit/a2_overlap.json`.
- Produces: `CONFIGS_CHALLENGER: list[dict]`, `CHALLENGER_MAGIC_BASE = 726000`,
  `CHALLENGER_VOLUME = 0.02`, `CHALLENGER_RISK_GATES: dict`. Task 5 imports `CONFIGS_CHALLENGER`.

**The one thing that can go catastrophically wrong** (documented at `live_configs_20.py:548-559`):
if this roster mutates a **shared** go-live dict instead of a deep copy, machine-2's `tomachine` lot
silently becomes the challenger's. Use `copy.deepcopy`, and let the immutability asserts prove it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_run_live_20.py` (and add `CONFIGS_CHALLENGER` to the existing
`from sentinel_engine.strategies.live_configs_20 import (...)` block at line 17):

```python
# ------------------------- challenger sleeve (2026-07-25) ------------------
def test_challenger_roster_is_exactly_three_mirrored_configs():
    assert len(CONFIGS_CHALLENGER) == 3, "the challenger mirrors 3 configs, NOT 4 (no TK-Momentum)"
    assert [c["id"] for c in CONFIGS_CHALLENGER] == [
        "S6-K2P0-R", "S7-TPNONE-R", "SuperTrend-p14x3-M15-R"]
    assert [c["magic"] for c in CONFIGS_CHALLENGER] == [726010, 726020, 726070]
    assert all(c["volume"] == 0.02 for c in CONFIGS_CHALLENGER)
    assert "TK-Momentum-5-8-short-R" not in {c["id"] for c in CONFIGS_CHALLENGER}


def test_challenger_signals_are_byte_identical_to_the_champion():
    # THE WHOLE POINT: same signal, different risk wrapper. If kwargs ever
    # diverge, the A/B comparison stops being a controlled experiment.
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for c in CONFIGS_CHALLENGER:
        src = golive_by_id[c["id"][:-2]]
        assert c["kwargs"] == src["kwargs"]
        assert c.get("engine") == src.get("engine")
        assert c.get("direction_filter") == src.get("direction_filter")


def test_challenger_carries_all_four_gates():
    for c in CONFIGS_CHALLENGER:
        g = c["risk_gates"]
        assert g["gap_wait_minutes"] == 50
        assert g["news_blackout_minutes"] == 30
        assert g["min_sl_distance"] == 0.5
        assert isinstance(g["max_open_fichas"], int) and g["max_open_fichas"] >= 1


def test_challenger_gate_dicts_are_not_shared_between_configs():
    ids = {id(c["risk_gates"]) for c in CONFIGS_CHALLENGER}
    assert len(ids) == 3, "each config owns its own gate dict"


def test_challenger_did_not_leak_into_any_shared_config():
    # THE LEAK PROOF. The shared go-live dicts must have gained NEITHER key.
    golive_by_id = {c["id"]: c for c in CONFIGS_GOLIVE}
    for cid in ("S6-K2P0", "S7-TPNONE", "SuperTrend-p14x3-M15"):
        assert "risk_gates" not in golive_by_id[cid]
        assert "volume" not in golive_by_id[cid]
    for c in CONFIGS_TOMACHINE:
        assert c.get("risk_gates") is None
        assert c.get("volume") is None


def test_champion_roster_is_untouched_by_the_challenger():
    # R1 IN TEST FORM: CONFIGS_LOCAL must be exactly what shipped on 2026-07-22.
    assert [(c["id"], c["magic"], c["volume"]) for c in CONFIGS_LOCAL] == [
        ("S6-K2P0", 724010, 0.1),
        ("S7-TPNONE", 724020, 0.1),
        ("SuperTrend-p14x3-M15", 724070, 0.1),
        ("TK-Momentum-5-8-short", 999999998, 0.01)]
    for c in CONFIGS_LOCAL:
        assert "risk_gates" not in c, "the CHAMPION must carry no gates"


def test_challenger_magic_band_is_disjoint_from_everything():
    challenger_band = set()
    for c in CONFIGS_CHALLENGER:
        challenger_band |= {c["magic"] + off for off in range(4)}
    assert min(challenger_band) == 726010 and max(challenger_band) == 726073
    assert all(not (722000 <= m <= 723999) for m in challenger_band), \
        "722xxx/723xxx are reserved"
    for other in (CONFIGS_LIVE, CONFIGS_SHADOW, CONFIGS_GOLIVE, CONFIGS_TK,
                  CONFIGS_LOCAL, CONFIGS_TOMACHINE):
        other_band = set()
        for c in other:
            other_band |= {c["magic"] + off for off in range(4)}
        assert challenger_band.isdisjoint(other_band)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/scripts/test_run_live_20.py -k challenger -v`
Expected: collection error â€” `ImportError: cannot import name 'CONFIGS_CHALLENGER'`.

- [ ] **Step 3: Read A2's number**

```bash
python -c "import json,pathlib;print(json.loads(pathlib.Path('data/analysis/monday_audit/a2_overlap.json').read_text(encoding='utf-8'))['max_simultaneous_fichas'])"
```

Whatever integer this prints is the cap. **Do not adjust it, do not round it, do not pick a
'nicer' number** â€” the rule was fixed in advance (spec Â§4.3 B3): the cap is the observed peak of
simultaneous fichas across the 7 months, so it is a bound that would never have bitten, which is
what makes it conservative-by-construction rather than a tuned choice.

- [ ] **Step 4: Write the implementation**

Append to `sentinel_engine/strategies/live_configs_20.py` (after line 606, end of the `CONFIGS_LOCAL`
block). Replace `<A2>` with the integer from Step 3 and keep the provenance comment accurate:

```python
# --- MACHINE-1 CHALLENGER SLEEVE (2026-07-25 Monday delivery) -------------
# The CHALLENGER half of the champion/retador experiment. THE SAME THREE
# SIGNALS as the `local` champion roster, byte for byte (kwargs/engine copied,
# never re-tuned -- spec R1/R3), differing ONLY in:
#   * a fresh magic band 726010/726020/726070 (see the disjointness asserts),
#   * a pilot lot of 0.02 (the champion stays at 0.1 -- comparison is per-trade
#     and size-normalised, so lot parity is not required),
#   * an OPTIONAL `risk_gates` dict read exclusively by run_live_20's OPEN path.
#
# TK-Momentum is deliberately NOT mirrored: it is still in development at 0.01
# and is not part of the track being compared. THREE configs, not four.
#
# WHY THIS CANNOT BREAK THE CHAMPION: `risk_gates` is an OPTIONAL key on
# INDEPENDENT DEEP COPIES, exactly like `volume` above. A config without the key
# takes the identical code path it took before this sleeve existed. If the copy
# discipline were ever broken, the immutability asserts below fail at import
# time and the executor refuses to start -- see the 0.1-leak warning at the top
# of the CONFIGS_LOCAL block.
CHALLENGER_MAGIC_BASE = 726000
CHALLENGER_VOLUME = 0.02
# B1 50 min  -> from the earlier xauusd-market-open-gap-wait diagnosis, NOT a
#               sweep run this weekend.
# B2 30 min  -> BY CONVENTION (spec section 4.3). Choosing it from a backtest
#               would be re-tuning.
# B3 <A2>    -> the observed PEAK of simultaneous fichas across the 7-month
#               real-tick reconstruction (data/analysis/monday_audit/
#               a2_overlap.json). A cap that would never have bitten.
# B4 0.50    -> the broker's minimum stop distance. A breach is a BUG.
CHALLENGER_RISK_GATES: dict[str, Any] = {
    "gap_wait_minutes": 50,
    "news_blackout_minutes": 30,
    "max_open_fichas": <A2>,
    "min_sl_distance": 0.50,
}


def _challenger_copy(cid: str) -> dict[str, Any]:
    """Independent deep COPY of a shared go-live config, re-badged into the
    challenger band. NEVER mutates the source dict (the immutability invariant
    that keeps machine-2's tomachine lot and the champion's roster intact)."""
    c = copy.deepcopy(_golive_by_id_for_local[cid])
    c["id"] = f"{cid}-R"
    c["magic"] = CHALLENGER_MAGIC_BASE + (c["magic"] - 724000)
    c["volume"] = CHALLENGER_VOLUME
    c["risk_gates"] = dict(CHALLENGER_RISK_GATES)  # own dict per config
    return c


CONFIGS_CHALLENGER: list[dict[str, Any]] = [
    _challenger_copy(cid) for cid in _LOCAL_GOLIVE_IDS
]

assert len(CONFIGS_CHALLENGER) == 3, \
    "challenger roster must be exactly 3 configs (TK-Momentum is NOT mirrored)"
assert [c["id"] for c in CONFIGS_CHALLENGER] == [
    "S6-K2P0-R", "S7-TPNONE-R", "SuperTrend-p14x3-M15-R"], \
    "challenger ids must be the 3 champion ids suffixed -R, in order"
assert [c["magic"] for c in CONFIGS_CHALLENGER] == [726010, 726020, 726070], \
    "challenger magics must be 724xxx remapped into the fresh 726xxx band"
assert all(c["volume"] == CHALLENGER_VOLUME for c in CONFIGS_CHALLENGER), \
    "challenger pilot lot must be 0.02"
# SAME SIGNAL: the kwargs must be identical to the champion's, or the A/B
# comparison stops being controlled.
for _c in CONFIGS_CHALLENGER:
    _src = _golive_by_id_for_local[_c["id"][:-2]]
    assert _c["kwargs"] == _src["kwargs"], \
        f"challenger {_c['id']} must mirror the champion signal EXACTLY"
# IMMUTABILITY: the SHARED source objects must NOT have gained either key.
for _cid in _LOCAL_GOLIVE_IDS:
    assert "risk_gates" not in _golive_by_id_for_local[_cid], \
        f"challenger risk_gates leaked into the shared {_cid} dict"
    assert "volume" not in _golive_by_id_for_local[_cid], \
        f"challenger volume leaked into the shared {_cid} dict"
# BAND DISJOINTNESS: 726xxx vs every other band, and clear of the reserved
# 722xxx/723xxx blocks.
_challenger_band: set[int] = set()
for _c in CONFIGS_CHALLENGER:
    _band = {_c["magic"] + _o for _o in range(4)}
    assert _challenger_band.isdisjoint(_band), \
        f"challenger magic band overlap at {_c['id']}"
    _challenger_band |= _band
assert _challenger_band.isdisjoint(_live_band) \
    and _challenger_band.isdisjoint(_shadow_band) \
    and _challenger_band.isdisjoint(_golive_band) \
    and _challenger_band.isdisjoint(_tk_band) \
    and _challenger_band.isdisjoint(_tk_bw2_band), \
    "challenger magic band must be disjoint from live/shadow/go-live/TK/TK-BW2"
assert all(not (722000 <= m <= 723999) for m in _challenger_band), \
    "challenger band must stay clear of the reserved 722xxx/723xxx blocks"
assert min(_challenger_band) == 726010 and max(_challenger_band) == 726073, \
    "challenger band must be the fresh 726010..726073 block"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/scripts/test_run_live_20.py -v`
Expected: all pass â€” the 7 new challenger tests plus every pre-existing roster test (especially
`test_local_roster_volume_did_not_leak_into_tomachine` and
`test_armed_rosters_unchanged_by_tomachine_addition`, which now also guard against this sleeve).

- [ ] **Step 6: Commit**

```bash
git -C D:/FOREX add sentinel_engine/strategies/live_configs_20.py tests/scripts/test_run_live_20.py
git -C D:/FOREX commit -m "feat(live): CONFIGS_CHALLENGER -- 726xxx mirror of S6/S7/ST at 0.02 with opt-in risk gates"
```

- [ ] **Step 7: Update the tracker** â€” set Task 4 to `[x]` and record the `max_open_fichas` value used
  and the A2 artifact it came from.

---

## Task 5: Executor plumbing â€” wire the gates into the OPEN path

**HARDEST TASK. Dispatch to Opus 5, medium effort** (doctrine D152). Everything else in lane B is
Sonnet 5 high.

**Depends on:** Tasks 1, 2, 3, 4.

**Files:**
- Modify: `scripts/live/run_live_20.py` (imports; `execute_action` signature + gate block;
  `GateCycleContext` + `_build_gate_ctx`; `run_cycle`; the `local+challenger` roster branch)
- Modify: `scripts/live/supervisor_live.py` (docstring/comment only â€” the accepted
  `SUPERVISOR_CONFIGS` values list)
- Test: `tests/scripts/test_run_live_20.py` (append)

**Interfaces:**
- Consumes: `evaluate_open_gates`, `GateInput` (Task 1); `news_calendar.load_windows` (Task 2);
  `gap_wait.load/advance/save` (Task 3); `CONFIGS_CHALLENGER` (Task 4).
- Produces: roster keyword `local+challenger`; log tokens `[RISK_GATE_SKIP]`, `[RISK_GATE_ERROR]`,
  `[risk-gates]`. Task 8 (deploy) greps for these; Task 11 (document) explains them.

**The invariant this task must not break:** with a roster where no config has `risk_gates`,
`run_cycle` and `execute_action` must take **exactly** the code path they take today. The new block
is guarded by `if a.kind == "OPEN" and risk_gates:` and the context builder by
`if challenger_cfgs:`. A test pins this down.

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_run_live_20.py`:

```python
def test_local_plus_challenger_roster_selects_seven(caplog):
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        rc = run_live_20.main(["--once", "--configs", "local+challenger",
                               "--no-adaptive-spread"],
                              mt5_module=mt5, attach_checker=lambda: True)
    assert rc == 0
    assert mt5.sent == [], "dry-run must send ZERO orders"
    assert "7 configs" in caplog.text
    for c in CONFIGS_LOCAL:
        assert f"[{c['id']}]" in caplog.text
    for c in CONFIGS_CHALLENGER:
        assert f"[{c['id']}]" in caplog.text


def test_local_plus_challenger_keeps_adaptive_spread_off_like_local(caplog, monkeypatch, tmp_path):
    # `local` never enabled the adaptive gate; adding the challenger must not
    # silently switch it on for the champion.
    monkeypatch.setattr(run_live_20, "SPREAD_STORE_PATH", tmp_path / "s.json", raising=False)
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        run_live_20.main(["--once", "--configs", "local+challenger"],
                         mt5_module=mt5, attach_checker=lambda: True)
    assert "adaptive_spread=OFF" in caplog.text or "[spread]" not in caplog.text


def test_champion_only_roster_never_builds_a_gate_context(caplog):
    # THE BYTE-IDENTICAL GUARANTEE: no config carries risk_gates -> the gate
    # machinery is never touched and nothing new appears in the audit log.
    mt5 = MockMT5(_bars())
    with caplog.at_level("INFO"):
        run_live_20.main(["--once", "--configs", "local", "--no-adaptive-spread"],
                         mt5_module=mt5, attach_checker=lambda: True)
    assert "[risk-gates]" not in caplog.text
    assert "[RISK_GATE_SKIP]" not in caplog.text


def test_execute_action_without_risk_gates_is_unchanged(caplog):
    # An OPEN with risk_gates=None must reach the ordinary dry-run log line.
    mt5 = MockMT5(_bars())
    action = _open_action(config_id="S6-K2P0", magic=724010, side="L", sl=3900.0)
    with caplog.at_level("INFO"):
        run_live_20.execute_action(mt5, action, symbol="XAUUSD", dry_run=True)
    assert "[DRY-RUN would OPEN]" in caplog.text
    assert "[RISK_GATE_SKIP]" not in caplog.text


def test_execute_action_denies_when_a_gate_denies(caplog):
    mt5 = MockMT5(_bars())
    action = _open_action(config_id="S6-K2P0-R", magic=726010, side="L", sl=3900.0)
    ctx = run_live_20.GateCycleContext(
        now=datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
        spread_ok_since=None, news_windows=(), open_fichas=0)
    with caplog.at_level("INFO"):
        run_live_20.execute_action(mt5, action, symbol="XAUUSD", dry_run=True,
                                   risk_gates={"gap_wait_minutes": 50}, gate_ctx=ctx)
    assert "[RISK_GATE_SKIP] gate=B1" in caplog.text
    assert "[DRY-RUN would OPEN]" not in caplog.text


def test_missing_gate_ctx_fails_closed(caplog):
    # A wiring bug must DENY, never silently disable the gates.
    mt5 = MockMT5(_bars())
    action = _open_action(config_id="S6-K2P0-R", magic=726010, side="L", sl=3900.0)
    with caplog.at_level("INFO"):
        run_live_20.execute_action(mt5, action, symbol="XAUUSD", dry_run=True,
                                   risk_gates={"gap_wait_minutes": 50}, gate_ctx=None)
    assert "[RISK_GATE_ERROR]" in caplog.text
    assert "[DRY-RUN would OPEN]" not in caplog.text


def test_admitted_opens_increment_the_sleeve_ficha_count():
    mt5 = MockMT5(_bars())
    ctx = run_live_20.GateCycleContext(
        now=datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
        spread_ok_since=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
        news_windows=(), open_fichas=0)
    action = _open_action(config_id="S6-K2P0-R", magic=726010, side="L", sl=3900.0)
    run_live_20.execute_action(mt5, action, symbol="XAUUSD", dry_run=True,
                               risk_gates={"gap_wait_minutes": 50, "max_open_fichas": 2},
                               gate_ctx=ctx)
    assert ctx.open_fichas == 1, "an admitted OPEN consumes a slot in this cycle"
```

Add this helper next to `_bars()` near the top of the file:

```python
def _open_action(*, config_id, magic, side, sl):
    """Minimal sendable OPEN action for gate tests, built through the real
    reconciler types so the shape can never drift from production."""
    from sentinel_engine.live.reconciler import Action
    return Action(kind="OPEN", config_id=config_id, magic=magic, ficha="F1",
                  side=side, volume=0.02, sl=sl, reason="test")
```

**If `Action`'s constructor signature differs**, read `sentinel_engine/live/reconciler.py` and build
it the way the reconciler itself does â€” do not invent fields.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/scripts/test_run_live_20.py -k "challenger or gate" -v`
Expected: failures â€” `AttributeError: module 'run_live_20' has no attribute 'GateCycleContext'`
and `unknown config id(s)` for the `local+challenger` roster.

- [ ] **Step 3: Add the imports and the cycle-context type**

In `scripts/live/run_live_20.py`, extend the existing `live_configs_20` import to include
`CONFIGS_CHALLENGER`, and add near the other `sentinel_engine.live` imports (around line 57):

```python
from sentinel_engine.live import gap_wait, news_calendar  # noqa: E402
from sentinel_engine.live.risk_gates import GateInput, evaluate_open_gates  # noqa: E402
```

Then, just above `execute_action` (before line 409), add:

```python
@dataclass
class GateCycleContext:
    """Per-cycle inputs for the challenger's risk gates. Built ONCE per cycle by
    `_build_gate_ctx`, and ONLY when some config in the roster carries
    `risk_gates` -- a champion-only roster never constructs one.

    `open_fichas` is MUTABLE on purpose: every OPEN admitted during this cycle
    consumes a slot, so B3 also caps *within* a cycle and not just across
    cycles. It is incremented at admission (not at fill): a send that later
    fails has still consumed the slot until the next cycle re-reads the book.
    That is the conservative direction."""
    now: datetime
    spread_ok_since: datetime | None
    news_windows: tuple[tuple[datetime, datetime], ...] | None
    open_fichas: int
```

Add `from dataclasses import dataclass` to the imports if it is not already there.

- [ ] **Step 4: Add the gate block to `execute_action`**

Extend the signature (after `spread_threshold`, before `on_fill`):

```python
                   risk_gates: dict[str, Any] | None = None,
                   gate_ctx: "GateCycleContext | None" = None,
```

and insert this block **immediately after** the `SPREAD_GATE_SKIP` block closes (after the `return`
at line 502, before `if dry_run:`):

```python
    # CHALLENGER RISK GATES (2026-07-25, OPEN only, OPT-IN -- spec section 4.3).
    # A config WITHOUT `risk_gates` skips this entirely, so the champion's
    # decisions are byte-identical to before this sleeve existed. Sibling of
    # SPREAD_GATE_SKIP above: same place, same shape, same logging. Exits,
    # MODIFY and CLOSE are NEVER gated -- risk management must always run.
    #
    # FAIL-CLOSED BY CONSTRUCTION: any exception (including a missing gate_ctx,
    # i.e. a wiring bug) skips the OPEN and logs loudly. A bug in the
    # challenger's risk layer must never abort the cycle that also runs the
    # champion, and must never silently DISABLE the gates.
    if a.kind == "OPEN" and risk_gates:
        try:
            tick = mt5.symbol_info_tick(symbol)
            market_ref = None
            if tick is not None:
                market_ref = float(tick.bid) if a.side == "L" else float(tick.ask)
            decision = evaluate_open_gates(risk_gates, GateInput(
                now=gate_ctx.now,
                spread_ok_since=gate_ctx.spread_ok_since,
                open_fichas=gate_ctx.open_fichas,
                desired_sl=float(a.sl) if a.sl is not None else None,
                market_ref=market_ref,
                news_windows=gate_ctx.news_windows,
            ))
        except Exception as exc:  # noqa: BLE001 - fail closed, never abort
            logger.error("  [RISK_GATE_ERROR] config=%s ficha=%s -> %s "
                         "(fail-closed: open skipped)", a.config_id, a.ficha, exc)
            return
        if not decision.allow:
            logger.warning("  [RISK_GATE_SKIP] gate=%s config=%s ficha=%s -- %s",
                           decision.gate, a.config_id, a.ficha, decision.reason)
            return
        gate_ctx.open_fichas += 1
```

- [ ] **Step 5: Add `_build_gate_ctx` and wire it into `run_cycle`**

Add above `run_cycle` (before line 701):

```python
def _build_gate_ctx(mt5: Any, challenger_cfgs: list[dict[str, Any]]) -> GateCycleContext:
    """Gather this cycle's gate inputs ONCE: the gap-wait clock (persisted
    across restarts), the news blackout windows, and how many fichas the
    challenger sleeve already has on the book. Read-only w.r.t. trading."""
    now = datetime.now(timezone.utc)
    sym = challenger_cfgs[0]["kwargs"]["symbol"]
    spread = _current_spread(mt5, sym)
    state = gap_wait.advance(gap_wait.load(), now=now, spread=spread)
    gap_wait.save(state)

    blackout = None
    for c in challenger_cfgs:
        val = (c.get("risk_gates") or {}).get("news_blackout_minutes")
        if val is not None:
            blackout = val
            break
    windows = (news_calendar.load_windows(minutes_before=blackout,
                                          minutes_after=blackout)
               if blackout is not None else None)

    open_fichas = sum(len(fetch_live_positions(mt5, c["magic"]))
                      for c in challenger_cfgs)
    logger.info("[risk-gates] now=%s spread=%s spread_ok_since=%s open_fichas=%d "
                "news_windows=%s",
                now.isoformat(),
                f"{spread:.5f}" if spread is not None else "None",
                state.spread_ok_since.isoformat() if state.spread_ok_since else "None",
                open_fichas,
                "NONE(FAIL-CLOSED)" if windows is None else len(windows))
    return GateCycleContext(now=now, spread_ok_since=state.spread_ok_since,
                            news_windows=windows, open_fichas=open_fichas)
```

In `run_cycle`, immediately before `total_open = 0` (line 743), add:

```python
    # CHALLENGER GATE CONTEXT: built ONLY when some config in this roster
    # carries `risk_gates`. With a champion-only roster this stays None and
    # nothing below this line behaves differently than before.
    gate_ctx: GateCycleContext | None = None
    challenger_cfgs = [c for c in configs if c.get("risk_gates")]
    if challenger_cfgs:
        gate_ctx = _build_gate_ctx(mt5, challenger_cfgs)
```

and extend the `execute_action(...)` call (line 755) with:

```python
                           risk_gates=cfg.get("risk_gates"),
                           gate_ctx=gate_ctx,
```

- [ ] **Step 6: Add the roster branch**

In `main`, after the `elif roster == "local":` branch (ends line 979), add:

```python
    elif roster == "local+challenger":
        # MACHINE-1 CHAMPION + CHALLENGER (2026-07-25 Monday delivery): the
        # untouched `local` champion (S6/S7/ST @0.1 + TK-Momentum @0.01) PLUS
        # the three 726xxx challenger mirrors @0.02 carrying risk_gates B1-B4.
        # ONE process, ONE account, two sleeves; the challenger is purely
        # additive and cannot alter a single champion decision.
        configs = list(CONFIGS_LOCAL) + list(CONFIGS_CHALLENGER)
```

The adaptive-spread default list (line 996) is deliberately **not** extended: `local` runs with the
adaptive gate OFF and the static `--max-spread-open 0.5` cap, and `local+challenger` must inherit
exactly that.

Finally, in `scripts/live/supervisor_live.py`, add `local+challenger` to the comment listing the
accepted `SUPERVISOR_CONFIGS` values (around line 93). **No code change there.**

- [ ] **Step 7: Run the full live test suite**

Run: `python -m pytest tests/scripts/test_run_live_20.py tests/live/ -v`
Expected: all pass. If `test_champion_only_roster_never_builds_a_gate_context` fails, the guard is
wrong â€” fix the guard, never the test.

- [ ] **Step 8: Verify the champion path really is untouched**

```bash
git -C D:/FOREX stash
python -m pytest tests/scripts/test_run_live_20.py -k "local or tomachine or golive" -v > /tmp/before.txt
git -C D:/FOREX stash pop
python -m pytest tests/scripts/test_run_live_20.py -k "local or tomachine or golive" -v > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt
```

Use the scratchpad directory instead of `/tmp` on Windows. Expected: the only differences are the
NEW test names; every pre-existing test keeps its result.

- [ ] **Step 9: Commit**

```bash
git -C D:/FOREX add scripts/live/run_live_20.py scripts/live/supervisor_live.py tests/scripts/test_run_live_20.py
git -C D:/FOREX commit -m "feat(live): local+challenger roster -- opt-in risk gates in the OPEN path"
```

- [ ] **Step 10: Update the tracker** â€” set Task 5 to `[x]`, record the full test count and paste the
  `[risk-gates]` line the dry run emitted.

---

## Task 6: Track-A loader â€” one merged, typed view of the 2 347 positions

**Lane A. Read-only: this task and every Track-A task touch `scripts/analysis/**` and
`data/analysis/**` only. They never import from `scripts/live` or `sentinel_engine/live`.**

**Files:**
- Create: `scripts/analysis/monday_audit/__init__.py` (empty)
- Create: `scripts/analysis/monday_audit/loader.py`
- Test: `tests/analysis/test_monday_audit.py`

**Interfaces:**
- Consumes: `data/analysis/realtick_bt/positions_S6-K2P0.csv`,
  `positions_S7-TPNONE.csv`, `positions_SuperTrend-p14x3-M15.csv`.
  Header, verbatim: `side,ficha,reason,t_in,t_out,entry_fill,exit_fill,spread,entry_delay_bars,net_067lot_clp,month`
- Produces: `Position` (frozen dataclass) and `load_positions(root=REALTICK_DIR) -> list[Position]`,
  sorted by `t_in` then `strategy`. Tasks 7â€“10 all consume this.

**Facts about the data, verified â€” do not re-derive:** 2 347 rows total (S6 912 / S7 1167 / ST 268),
7 months (2026-01 â€¦ 2026-07), `net_067lot_clp` is the net CLP result **at 0.67 lot**, `spread` takes
only the values 0.5 and 0.6, timestamps are ISO-8601 **broker server time** (they are only ever
compared to each other here, never to a wall clock, so no conversion is needed or wanted).

- [ ] **Step 1: Write the failing test**

Create `tests/analysis/test_monday_audit.py`:

```python
"""tests/analysis/test_monday_audit.py -- Track-A audit maths on tiny synthetic
fixtures. The real 2 347-row run is a script invocation, not a test."""
from __future__ import annotations

from pathlib import Path

from scripts.analysis.monday_audit.loader import Position, load_positions

_HEADER = ("side,ficha,reason,t_in,t_out,entry_fill,exit_fill,spread,"
           "entry_delay_bars,net_067lot_clp,month\n")


def _fixture(tmp_path: Path) -> Path:
    (tmp_path / "positions_S6-K2P0.csv").write_text(
        _HEADER
        + "LONG,F1,EXIT_INITSL,2026-01-05T20:00:00,2026-01-05T23:47:08,4450.98,4458.94,0.5,0,499454.18,2026-01\n"
        + "SHORT,F2,EXIT_TRAIL,2026-01-06T10:00:00,2026-01-06T12:00:00,4460.00,4455.00,0.6,1,-120000.00,2026-01\n",
        encoding="utf-8")
    (tmp_path / "positions_S7-TPNONE.csv").write_text(
        _HEADER
        + "LONG,F1,EXIT_INITSL,2026-01-05T21:00:00,2026-01-06T01:00:00,4451.00,4449.00,0.5,0,-80000.00,2026-01\n",
        encoding="utf-8")
    (tmp_path / "positions_SuperTrend-p14x3-M15.csv").write_text(_HEADER, encoding="utf-8")
    return tmp_path


def test_loader_merges_all_three_files_and_tags_the_strategy(tmp_path):
    rows = load_positions(_fixture(tmp_path))
    assert len(rows) == 3
    assert {r.strategy for r in rows} == {"S6-K2P0", "S7-TPNONE"}
    assert all(isinstance(r, Position) for r in rows)


def test_loader_sorts_chronologically_by_entry(tmp_path):
    rows = load_positions(_fixture(tmp_path))
    assert [r.t_in.isoformat() for r in rows] == sorted(r.t_in.isoformat() for r in rows)


def test_loader_types_every_field(tmp_path):
    r = load_positions(_fixture(tmp_path))[0]
    assert r.side == "LONG" and r.ficha == "F1" and r.reason == "EXIT_INITSL"
    assert r.spread == 0.5 and r.entry_delay_bars == 0
    assert abs(r.net_067lot_clp - 499454.18) < 1e-6
    assert r.month == "2026-01"
    assert r.t_out > r.t_in


def test_loader_scales_net_to_an_arbitrary_lot(tmp_path):
    r = load_positions(_fixture(tmp_path))[0]
    assert abs(r.net_at_lot(0.1) - 499454.18 * (0.1 / 0.67)) < 1e-6
    assert abs(r.net_at_lot(0.67) - r.net_067lot_clp) < 1e-9
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/analysis/test_monday_audit.py -v`
Expected: `ModuleNotFoundError: No module named 'scripts.analysis.monday_audit'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/analysis/monday_audit/__init__.py` (empty file) and
`scripts/analysis/monday_audit/loader.py`:

```python
"""scripts/analysis/monday_audit/loader.py -- one merged, typed view of the
real-tick reconstruction that every Track-A audit question reads.

SUBSTRATE (spec section 5.1): data/analysis/realtick_bt/positions_*.csv, 2 347
positions across 7 months (S6 912 / S7 1167 / ST 268). NOTHING is re-simulated
here -- these are the positions the real-tick backtest already produced.

`net_067lot_clp` is the net CLP result AT 0.67 LOT. Lot scaling is exactly
linear (price PnL, commission and swap are all per-lot), so `net_at_lot`
rescales it; ratios (WR, PF, drawdown %) are lot-invariant.

Timestamps are broker SERVER time. They are only ever compared to each other in
Track A, so no timezone conversion is performed -- and none should be added.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REALTICK_DIR = Path(__file__).resolve().parents[3] / "data" / "analysis" / "realtick_bt"
OUT_DIR = Path(__file__).resolve().parents[3] / "data" / "analysis" / "monday_audit"

SOURCE_LOT = 0.67

STRATEGY_FILES = {
    "S6-K2P0": "positions_S6-K2P0.csv",
    "S7-TPNONE": "positions_S7-TPNONE.csv",
    "SuperTrend-p14x3-M15": "positions_SuperTrend-p14x3-M15.csv",
}


@dataclass(frozen=True)
class Position:
    strategy: str
    side: str
    ficha: str
    reason: str
    t_in: datetime
    t_out: datetime
    entry_fill: float
    exit_fill: float
    spread: float
    entry_delay_bars: int
    net_067lot_clp: float
    month: str

    def net_at_lot(self, lot: float) -> float:
        """Net CLP rescaled to `lot`. Linear by construction."""
        return self.net_067lot_clp * (lot / SOURCE_LOT)


def load_positions(root: str | Path = REALTICK_DIR) -> list[Position]:
    """Every position from the three CSVs, tagged with its strategy and sorted
    by entry time (ties broken by strategy name, so the order is total and the
    outputs are reproducible byte-for-byte)."""
    out: list[Position] = []
    for strategy, filename in STRATEGY_FILES.items():
        path = Path(root) / filename
        text = path.read_text(encoding="utf-8")
        for row in csv.DictReader(text.splitlines()):
            if not (row.get("t_in") or "").strip():
                continue
            out.append(Position(
                strategy=strategy,
                side=row["side"],
                ficha=row["ficha"],
                reason=row["reason"],
                t_in=datetime.fromisoformat(row["t_in"]),
                t_out=datetime.fromisoformat(row["t_out"]),
                entry_fill=float(row["entry_fill"]),
                exit_fill=float(row["exit_fill"]),
                spread=float(row["spread"]),
                entry_delay_bars=int(row["entry_delay_bars"]),
                net_067lot_clp=float(row["net_067lot_clp"]),
                month=row["month"],
            ))
    out.sort(key=lambda p: (p.t_in, p.strategy))
    return out


def write_artifact(name: str, payload: dict) -> Path:
    """Persist one audit answer as pretty JSON. Every Track-A module ends here,
    so every number in the Monday document is traceable to a file on disk."""
    import json
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str),
                    encoding="utf-8")
    return path
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/analysis/test_monday_audit.py -v`
Expected: 4 passed.

- [ ] **Step 5: Sanity-check against the real data**

```bash
python -c "from scripts.analysis.monday_audit.loader import load_positions; rows=load_positions(); import collections; print(len(rows), collections.Counter(r.strategy for r in rows))"
```

Expected: `2347 Counter({'S7-TPNONE': 1167, 'S6-K2P0': 912, 'SuperTrend-p14x3-M15': 268})`.
**If the counts differ, STOP and report** â€” the substrate is not what the spec assumed.

- [ ] **Step 6: Commit**

```bash
git -C D:/FOREX add scripts/analysis/monday_audit/ tests/analysis/test_monday_audit.py
git -C D:/FOREX commit -m "feat(analysis): monday audit loader over the real-tick position substrate"
```

- [ ] **Step 7: Update the tracker** â€” set Task 6 to `[x]` and paste the row counts from Step 5.

---

## Task 7: A1 â€” verify the âˆ’28,6 % max drawdown

**Files:**
- Create: `scripts/analysis/monday_audit/a1_maxdd.py`
- Test: append to `tests/analysis/test_monday_audit.py`

**Interfaces:**
- Consumes: `loader.load_positions`, `loader.write_artifact`.
- Produces: `data/analysis/monday_audit/a1_maxdd.json` with keys
  `max_dd_clp`, `max_dd_pct_of_initial`, `max_dd_pct_of_peak_equity`, `peak_equity_clp`,
  `trough_equity_clp`, `t_peak`, `t_trough`, `final_net_clp`, `lot`, `account_balance_clp`,
  `n_positions`. The document (Task 13) quotes these.

**What is being checked:** the âˆ’28,6 % in circulation is a rule of three
(114 092 025 CLP @0.67 â†’ â‰ˆâˆ’17,0 MM @0.1 â†’ â‰ˆâˆ’28,6 % of the 59,6 MM account), never verified against
the position stream. R2 already fixed the lot at 0.1 regardless of the answer, so this task
**cannot** change a deployment decision â€” it only makes the number in the document honest.

**Method, fixed in advance:** order all 2 347 positions by `t_out` (equity moves when a trade
closes), accumulate `net_at_lot(0.1)`, track the running peak, and take the largest peak-to-trough
drop. Report the drawdown both as a fraction of the initial balance (59 600 000 CLP) and of the
running-peak equity. Ties broken by `(t_out, strategy, t_in)` so the result is reproducible.

- [ ] **Step 1: Write the failing test**

Append to `tests/analysis/test_monday_audit.py`:

```python
from scripts.analysis.monday_audit.a1_maxdd import max_drawdown


def test_max_drawdown_finds_the_deepest_peak_to_trough():
    # equity: 0 -> 100 -> 60 -> 160 -> 10   (deepest drop is 160 -> 10 = 150)
    deltas = [100.0, -40.0, 100.0, -150.0]
    dd = max_drawdown(deltas)
    assert dd.max_dd == 150.0
    assert dd.peak_equity == 160.0
    assert dd.trough_equity == 10.0
    assert dd.peak_index == 2 and dd.trough_index == 3


def test_max_drawdown_of_a_monotonic_curve_is_zero():
    assert max_drawdown([10.0, 20.0, 5.0]).max_dd == 0.0


def test_max_drawdown_of_an_empty_series_is_zero():
    assert max_drawdown([]).max_dd == 0.0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/analysis/test_monday_audit.py -k drawdown -v`
Expected: `ModuleNotFoundError: ... a1_maxdd`.

- [ ] **Step 3: Write the implementation**

Create `scripts/analysis/monday_audit/a1_maxdd.py`:

```python
"""A1 -- verify the max drawdown of the S6+S7+SuperTrend track at 0.1 lot.

The -28,6 % figure in circulation is a rule of three from the 0.67-lot number,
never checked against the position stream. The trader has already fixed the lot
at 0.1 regardless (spec R2), so this cannot change a deployment decision: it
exists so the number that goes into the Monday document is a computed one.

Equity is stepped at t_out (a trade moves the balance when it CLOSES).
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.analysis.monday_audit.loader import load_positions, write_artifact

ACCOUNT_BALANCE_CLP = 59_600_000.0
CHAMPION_LOT = 0.1


@dataclass(frozen=True)
class Drawdown:
    max_dd: float
    peak_equity: float
    trough_equity: float
    peak_index: int
    trough_index: int


def max_drawdown(deltas: list[float]) -> Drawdown:
    """Largest peak-to-trough drop of the cumulative sum of `deltas`."""
    equity = 0.0
    peak = 0.0
    peak_i = -1
    best = Drawdown(0.0, 0.0, 0.0, -1, -1)
    for i, d in enumerate(deltas):
        equity += d
        if equity > peak:
            peak, peak_i = equity, i
        drop = peak - equity
        if drop > best.max_dd:
            best = Drawdown(drop, peak, equity, peak_i, i)
    return best


def main() -> int:
    rows = sorted(load_positions(), key=lambda p: (p.t_out, p.strategy, p.t_in))
    deltas = [p.net_at_lot(CHAMPION_LOT) for p in rows]
    dd = max_drawdown(deltas)
    payload = {
        "lot": CHAMPION_LOT,
        "account_balance_clp": ACCOUNT_BALANCE_CLP,
        "n_positions": len(rows),
        "final_net_clp": sum(deltas),
        "max_dd_clp": dd.max_dd,
        "max_dd_pct_of_initial": 100.0 * dd.max_dd / ACCOUNT_BALANCE_CLP,
        "max_dd_pct_of_peak_equity": (
            100.0 * dd.max_dd / (ACCOUNT_BALANCE_CLP + dd.peak_equity)),
        "peak_equity_clp": dd.peak_equity,
        "trough_equity_clp": dd.trough_equity,
        "t_peak": rows[dd.peak_index].t_out if dd.peak_index >= 0 else None,
        "t_trough": rows[dd.trough_index].t_out if dd.trough_index >= 0 else None,
    }
    path = write_artifact("a1_maxdd.json", payload)
    print(f"wrote {path}")
    print(f"max DD @{CHAMPION_LOT} lot: {dd.max_dd:,.0f} CLP = "
          f"{payload['max_dd_pct_of_initial']:.2f}% of the initial balance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/analysis/test_monday_audit.py -k drawdown -v`
Expected: 3 passed.

- [ ] **Step 5: Run it on the real data**

Run: `python -m scripts.analysis.monday_audit.a1_maxdd`
Expected: writes `data/analysis/monday_audit/a1_maxdd.json` and prints the DD.

- [ ] **Step 6: Commit and record**

```bash
git -C D:/FOREX add scripts/analysis/monday_audit/a1_maxdd.py tests/analysis/test_monday_audit.py data/analysis/monday_audit/a1_maxdd.json
git -C D:/FOREX commit -m "feat(analysis): A1 -- computed max drawdown of the champion track at 0.1 lot"
```

- [ ] **Step 7: Update the tracker** â€” set Task 7 to `[x]` and paste the computed DD **next to the
  âˆ’28,6 % estimate**, stating plainly whether the estimate is confirmed or corrected.

---

## Task 8: A2 â€” overlap, correlation, and the B3 exposure cap

**This task BLOCKS Task 4.** Its `max_simultaneous_fichas` is the challenger's B3 cap.

**Files:**
- Create: `scripts/analysis/monday_audit/a2_overlap.py`
- Test: append to `tests/analysis/test_monday_audit.py`

**Interfaces:**
- Consumes: `loader.load_positions`, `loader.write_artifact`.
- Produces: `data/analysis/monday_audit/a2_overlap.json` with keys
  `max_simultaneous_fichas` (**int â€” this is the B3 cap**), `simultaneous_histogram`,
  `p95_simultaneous`, `p99_simultaneous`, `pairwise_daily_net_correlation`,
  `pct_time_with_any_position`, `n_positions`.

**Two independent questions, one artifact:**

1. **Concurrency.** Sweep the merged position stream as an event series (+1 at `t_in`, âˆ’1 at
   `t_out`) and record the running count. The **maximum** is the B3 cap â€” a bound the 7 months would
   never have violated, hence conservative by construction and not a tuned choice (spec Â§4.3 B3).
   Ties matter: process **exits before entries** at an identical timestamp, so a close-then-open at
   the same instant does not inflate the peak.
2. **Correlation.** Daily net per strategy (at any lot â€” correlation is lot-invariant), then
   Pearson correlation for each of the three pairs. This tells the document whether the three
   "different" strategies are really one bet.

- [ ] **Step 1: Write the failing test**

Append to `tests/analysis/test_monday_audit.py`:

```python
from datetime import datetime

from scripts.analysis.monday_audit.a2_overlap import max_concurrency, pearson


def _iv(a, b):
    return (datetime.fromisoformat(a), datetime.fromisoformat(b))


def test_max_concurrency_counts_overlapping_intervals():
    ivs = [_iv("2026-01-01T00:00", "2026-01-01T03:00"),
           _iv("2026-01-01T01:00", "2026-01-01T02:00"),
           _iv("2026-01-01T01:30", "2026-01-01T04:00")]
    peak, hist = max_concurrency(ivs)
    assert peak == 3
    assert hist[3] >= 1


def test_concurrency_treats_a_touching_pair_as_sequential():
    # exits are processed BEFORE entries at the same timestamp
    ivs = [_iv("2026-01-01T00:00", "2026-01-01T01:00"),
           _iv("2026-01-01T01:00", "2026-01-01T02:00")]
    peak, _hist = max_concurrency(ivs)
    assert peak == 1


def test_max_concurrency_of_nothing_is_zero():
    assert max_concurrency([])[0] == 0


def test_pearson_matches_known_values():
    assert abs(pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) - 1.0) < 1e-9
    assert abs(pearson([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) + 1.0) < 1e-9
    assert pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0  # zero variance
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/analysis/test_monday_audit.py -k "concurrency or pearson" -v`
Expected: `ModuleNotFoundError: ... a2_overlap`.

- [ ] **Step 3: Write the implementation**

Create `scripts/analysis/monday_audit/a2_overlap.py`:

```python
"""A2 -- how much the three strategies overlap, and the exposure cap that
follows from it (spec section 5.1 item 2; feeds the challenger's B3 gate).

THE CAP RULE WAS FIXED IN ADVANCE: B3's cap is the OBSERVED MAXIMUM of
simultaneous fichas across the 7 months. It is therefore a bound that would
never have bitten -- conservative by construction -- and NOT a number chosen by
comparing outcomes. Choosing it by outcome would be re-tuning (spec R3).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations

from scripts.analysis.monday_audit.loader import load_positions, write_artifact


def max_concurrency(intervals: list[tuple[datetime, datetime]]
                    ) -> tuple[int, dict[int, int]]:
    """Peak simultaneous intervals, plus a histogram of how many distinct
    moments ran at each level. Exits are processed BEFORE entries at an equal
    timestamp, so a close-then-open at the same instant is sequential."""
    events: list[tuple[datetime, int]] = []
    for start, end in intervals:
        events.append((start, +1))
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], e[1]))  # -1 sorts before +1
    live = 0
    peak = 0
    hist: Counter[int] = Counter()
    for _t, delta in events:
        live += delta
        peak = max(peak, live)
        hist[live] += 1
    return peak, dict(hist)


def pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation; 0.0 when either series has zero variance."""
    n = len(xs)
    if n == 0 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0.0 or syy == 0.0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def _percentile_level(hist: dict[int, int], pct: float) -> int:
    """Highest concurrency level at or below the given percentile of moments."""
    total = sum(hist.values())
    if total == 0:
        return 0
    running = 0
    for level in sorted(hist):
        running += hist[level]
        if running / total >= pct:
            return level
    return max(hist)


def main() -> int:
    rows = load_positions()
    peak, hist = max_concurrency([(p.t_in, p.t_out) for p in rows])

    daily: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for p in rows:
        daily[p.strategy][p.t_out.date().isoformat()] += p.net_067lot_clp
    strategies = sorted(daily)
    all_days = sorted({d for s in strategies for d in daily[s]})
    corr = {}
    for a, b in combinations(strategies, 2):
        xs = [daily[a].get(d, 0.0) for d in all_days]
        ys = [daily[b].get(d, 0.0) for d in all_days]
        corr[f"{a}|{b}"] = pearson(xs, ys)

    moments = sum(hist.values())
    payload = {
        "n_positions": len(rows),
        "max_simultaneous_fichas": peak,
        "simultaneous_histogram": hist,
        "p95_simultaneous": _percentile_level(hist, 0.95),
        "p99_simultaneous": _percentile_level(hist, 0.99),
        "pct_time_with_any_position": (
            100.0 * sum(c for lvl, c in hist.items() if lvl > 0) / moments
            if moments else 0.0),
        "pairwise_daily_net_correlation": corr,
        "n_trading_days": len(all_days),
    }
    path = write_artifact("a2_overlap.json", payload)
    print(f"wrote {path}")
    print(f"B3 CAP (observed peak simultaneous fichas) = {peak}")
    for k, v in corr.items():
        print(f"  corr {k}: {v:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/analysis/test_monday_audit.py -k "concurrency or pearson" -v`
Expected: 4 passed.

- [ ] **Step 5: Run it on the real data**

Run: `python -m scripts.analysis.monday_audit.a2_overlap`
Expected: writes `a2_overlap.json` and prints `B3 CAP (observed peak simultaneous fichas) = N`.

**Sanity bound:** each of the three configs runs at most 3 fichas, so `N` must be between 1 and 9.
If it is outside that range, STOP and report â€” the substrate or the sweep is wrong.

- [ ] **Step 6: Commit and unblock Task 4**

```bash
git -C D:/FOREX add scripts/analysis/monday_audit/a2_overlap.py tests/analysis/test_monday_audit.py data/analysis/monday_audit/a2_overlap.json
git -C D:/FOREX commit -m "feat(analysis): A2 -- strategy overlap, correlation and the B3 exposure cap"
```

- [ ] **Step 7: Update the tracker** â€” set Task 8 to `[x]`, write `max_simultaneous_fichas = N` on the
  "B3 cap" line, and mark Task 4 as UNBLOCKED.

---

## Task 9: A3 + A4 + A5 â€” exit attribution, serial correlation, spread-gate validation

One task, three artifacts: each is a small independent read over the same substrate, and splitting
them would cost three review cycles for no benefit.

**Files:**
- Create: `scripts/analysis/monday_audit/a3_a4_a5_stats.py`
- Test: append to `tests/analysis/test_monday_audit.py`

**Interfaces:**
- Consumes: `loader.load_positions`, `loader.write_artifact`.
- Produces three artifacts:
  - `a3_exit_reason.json` â€” per `(strategy, reason)`: `n`, `net_clp`, `mean_clp`, `win_rate`.
  - `a4_serial.json` â€” per strategy: lag-1..5 autocorrelation of consecutive trade results,
    plus longest win/loss streak.
  - `a5_spread_gate.json` â€” per strategy and combined, split by `spread` (0.5 vs 0.6):
    `n`, `net_clp`, `win_rate`, `profit_factor`.
  Task 13 (the document) quotes all three.

**Why A5 matters most of the three:** the 0.5 spread filter is currently validated on **five live
sessions**. If the 7-month reconstruction shows the same sign, the filter stops being an anecdote.
Note the honest framing already established: 0.6 is a **worse regime**, not merely a higher cost.

- [ ] **Step 1: Write the failing tests**

Append to `tests/analysis/test_monday_audit.py`:

```python
from scripts.analysis.monday_audit.a3_a4_a5_stats import (
    autocorrelation, longest_streak, profit_factor, win_rate)


def test_win_rate_counts_strictly_positive_results():
    assert win_rate([1.0, -1.0, 0.0, 2.0]) == 50.0
    assert win_rate([]) == 0.0


def test_profit_factor_is_gross_win_over_gross_loss():
    assert profit_factor([3.0, -1.0, -0.5]) == 2.0
    assert profit_factor([1.0, 2.0]) == float("inf")   # no losses
    assert profit_factor([]) == 0.0


def test_autocorrelation_of_an_alternating_series_is_negative():
    assert autocorrelation([1.0, -1.0, 1.0, -1.0, 1.0], lag=1) < -0.9


def test_autocorrelation_with_too_few_points_is_zero():
    assert autocorrelation([1.0], lag=1) == 0.0


def test_longest_streak_finds_both_directions():
    assert longest_streak([1.0, 1.0, 1.0, -1.0]) == (3, 1)
    assert longest_streak([-1.0, -1.0, 2.0]) == (1, 2)
    assert longest_streak([]) == (0, 0)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/analysis/test_monday_audit.py -k "win_rate or profit_factor or autocorrelation or streak" -v`
Expected: `ModuleNotFoundError: ... a3_a4_a5_stats`.

- [ ] **Step 3: Write the implementation**

Create `scripts/analysis/monday_audit/a3_a4_a5_stats.py`:

```python
"""A3/A4/A5 -- three read-only questions over the real-tick substrate.

A3 exit attribution   -- where does the money actually come from, by exit reason.
A4 serial correlation -- do results cluster in streaks (regime) or not.
A5 spread-gate check  -- does the 0.5 filter hold across 7 months, or only over
                         the five live sessions it was validated on so far.

NONE of these selects a parameter. They describe the track that is already
deployed; the challenger's numbers come from the spec, not from here.
"""
from __future__ import annotations

import math
from collections import defaultdict

from scripts.analysis.monday_audit.loader import load_positions, write_artifact


def win_rate(nets: list[float]) -> float:
    return 100.0 * sum(1 for n in nets if n > 0) / len(nets) if nets else 0.0


def profit_factor(nets: list[float]) -> float:
    """Gross wins / gross losses. inf when there are wins and no losses."""
    if not nets:
        return 0.0
    wins = sum(n for n in nets if n > 0)
    losses = -sum(n for n in nets if n < 0)
    if losses == 0.0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def autocorrelation(series: list[float], *, lag: int) -> float:
    """Lag-k autocorrelation. 0.0 when the series is too short or flat."""
    n = len(series)
    if n <= lag:
        return 0.0
    mean = sum(series) / n
    denom = sum((x - mean) ** 2 for x in series)
    if denom == 0.0:
        return 0.0
    num = sum((series[i] - mean) * (series[i + lag] - mean) for i in range(n - lag))
    return num / denom


def longest_streak(nets: list[float]) -> tuple[int, int]:
    """(longest run of wins, longest run of losses). Zeros break both runs."""
    best_w = best_l = cur_w = cur_l = 0
    for n in nets:
        if n > 0:
            cur_w, cur_l = cur_w + 1, 0
        elif n < 0:
            cur_l, cur_w = cur_l + 1, 0
        else:
            cur_w = cur_l = 0
        best_w, best_l = max(best_w, cur_w), max(best_l, cur_l)
    return best_w, best_l


def _summary(nets: list[float]) -> dict:
    return {"n": len(nets), "net_clp": sum(nets), "win_rate": win_rate(nets),
            "profit_factor": profit_factor(nets),
            "mean_clp": (sum(nets) / len(nets)) if nets else 0.0}


def main() -> int:
    rows = load_positions()

    # --- A3: attribution by exit reason ---------------------------------
    by_reason: dict[str, list[float]] = defaultdict(list)
    for p in rows:
        by_reason[f"{p.strategy}|{p.reason}"].append(p.net_067lot_clp)
    a3 = {k: _summary(v) for k, v in sorted(by_reason.items())}
    write_artifact("a3_exit_reason.json", a3)

    # --- A4: serial correlation, per strategy, in trade order -----------
    a4 = {}
    for strat in sorted({p.strategy for p in rows}):
        series = [p.net_067lot_clp for p in sorted(
            (p for p in rows if p.strategy == strat), key=lambda p: p.t_out)]
        wins, losses = longest_streak(series)
        a4[strat] = {
            "n": len(series),
            "autocorr": {f"lag_{k}": autocorrelation(series, lag=k) for k in range(1, 6)},
            "longest_win_streak": wins,
            "longest_loss_streak": losses,
        }
    write_artifact("a4_serial.json", a4)

    # --- A5: the 0.5 spread gate across 7 months ------------------------
    a5: dict[str, dict] = {}
    for strat in sorted({p.strategy for p in rows}) + ["COMBINED"]:
        sel = rows if strat == "COMBINED" else [p for p in rows if p.strategy == strat]
        a5[strat] = {
            "at_0.5": _summary([p.net_067lot_clp for p in sel if p.spread <= 0.5]),
            "at_0.6": _summary([p.net_067lot_clp for p in sel if p.spread > 0.5]),
            "unfiltered": _summary([p.net_067lot_clp for p in sel]),
        }
    write_artifact("a5_spread_gate.json", a5)

    c = a5["COMBINED"]
    print(f"A5 COMBINED: @0.5 net={c['at_0.5']['net_clp']:,.0f} "
          f"(n={c['at_0.5']['n']}) | @0.6 net={c['at_0.6']['net_clp']:,.0f} "
          f"(n={c['at_0.6']['n']}) | unfiltered={c['unfiltered']['net_clp']:,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/analysis/test_monday_audit.py -v`
Expected: all pass (the loader, A1, A2 and A3/A4/A5 tests together).

- [ ] **Step 5: Run it on the real data**

Run: `python -m scripts.analysis.monday_audit.a3_a4_a5_stats`
Expected: three JSON artifacts written, and the A5 COMBINED line printed.

- [ ] **Step 6: Commit**

```bash
git -C D:/FOREX add scripts/analysis/monday_audit/a3_a4_a5_stats.py tests/analysis/test_monday_audit.py data/analysis/monday_audit/
git -C D:/FOREX commit -m "feat(analysis): A3/A4/A5 -- exit attribution, serial correlation, 7-month spread-gate check"
```

- [ ] **Step 7: Update the tracker** â€” set Task 9 to `[x]` and paste the A5 COMBINED line, since it is
  the headline the document needs.

---

## Task 10: The retrospective masks â€” veto verdicts for B1â€“B4

**Depends on:** Tasks 6, 8 (substrate + the cap), and Task 2 (the calendar's date coverage).

**Files:**
- Create: `scripts/analysis/monday_audit/b6_masks.py`
- Create: `docs/superpowers/research/2026-07-25-wrapper-mask-verdicts.md` (generated by the script)
- Test: append to `tests/analysis/test_monday_audit.py`

**Interfaces:**
- Consumes: `loader.load_positions`, `news_calendar.load_windows` (read-only import of the live
  module is fine here â€” this script never runs in the executor).
- Produces: `data/analysis/monday_audit/b6_mask_verdicts.json` + the markdown report.

### The rule that governs this task

> **The mask VETOES if the result is catastrophic; it NEVER selects.**

Concretely: you may write "B2 would have removed 4 % of trades and 3 % of net â†’ **NO VETO**", or
"B1 would have removed 60 % of the net â†’ **VETO, do not deploy B1**". You may **not** write "B1 at
35 min looks better than at 50 min". If you catch yourself comparing variants, stop â€” that is R3.

### What is and is not evaluable, decided in advance

| Gate | Maskable on this substrate? | How, or why not |
|---|---|---|
| **B1** gap-wait | **Yes, by proxy.** | The CSVs have no spread-regime history, so a *session boundary* is defined as a gap of â‰¥ 60 min between consecutive `t_in` values across the merged stream, and the mask drops positions entered within 50 min of one. Document it as a proxy: it approximates "50 min after the reopen" using the position stream alone, and it is the same conservative direction. |
| **B2** news blackout | **Only over the calendar's date range.** | Report the overlap between the calendar's coverage (Task 2, Step 7) and 2026-01â€¦2026-07. If coverage is zero, the honest verdict is **"NOT EVALUABLE â€” no veto by absence of evidence"**, stated as such. Do not invent events to make it evaluable. |
| **B3** exposure cap | **Yes, and trivially.** | The cap *is* the observed peak, so a chronological greedy replay must drop **zero** positions. That is the point: it proves the cap would never have bitten. If it drops any, the cap or the sweep is wrong â€” STOP and report. |
| **B4** SL legality | **No.** | The CSVs carry no SL column, and reconstructing it means re-simulating (out of scope, spec Â§8). B4 is a **bug detector in the live path**, not a filter. Verdict: **"NOT MASKABLE â€” by design"**. |

- [ ] **Step 1: Write the failing tests**

Append to `tests/analysis/test_monday_audit.py`:

```python
from datetime import datetime, timedelta

from scripts.analysis.monday_audit.b6_masks import (
    b1_session_starts, cap_replay_drops)


def test_b1_session_starts_finds_gaps_over_the_threshold():
    ts = [datetime(2026, 1, 1, 0, 0),
          datetime(2026, 1, 1, 0, 30),      # 30 min -> same session
          datetime(2026, 1, 1, 3, 0)]        # 150 min -> new session
    starts = b1_session_starts(ts, gap_minutes=60)
    assert starts == [datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 1, 3, 0)]


def test_b1_session_starts_of_an_empty_stream_is_empty():
    assert b1_session_starts([], gap_minutes=60) == []


def test_cap_replay_drops_nothing_when_the_cap_is_the_observed_peak():
    base = datetime(2026, 1, 1, 0, 0)
    ivs = [(base, base + timedelta(hours=3)),
           (base + timedelta(hours=1), base + timedelta(hours=2))]
    assert cap_replay_drops(ivs, cap=2) == []


def test_cap_replay_drops_the_later_entry_when_the_cap_binds():
    base = datetime(2026, 1, 1, 0, 0)
    ivs = [(base, base + timedelta(hours=3)),
           (base + timedelta(hours=1), base + timedelta(hours=2))]
    assert cap_replay_drops(ivs, cap=1) == [1]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/analysis/test_monday_audit.py -k "session_starts or cap_replay" -v`
Expected: `ModuleNotFoundError: ... b6_masks`.

- [ ] **Step 3: Write the implementation**

Create `scripts/analysis/monday_audit/b6_masks.py`:

```python
"""Retrospective wrapper masks (spec section 4.4).

THE RULE: each mask VETOES a wrapper if it would have been catastrophic. It
NEVER selects between wrapper variants -- selecting by this number is exactly
the overfitting the whole delivery is built to avoid (spec R3).

Honesty requirements baked in below: B2 is only evaluated over the range the
committed calendar actually covers, and B4 is reported as NOT MASKABLE rather
than quietly skipped.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from scripts.analysis.monday_audit.loader import load_positions, write_artifact
from sentinel_engine.live import news_calendar

REPORT_PATH = (Path(__file__).resolve().parents[3] / "docs" / "superpowers"
               / "research" / "2026-07-25-wrapper-mask-verdicts.md")

B1_WAIT_MINUTES = 50
B1_SESSION_GAP_MINUTES = 60
B2_BLACKOUT_MINUTES = 30


def b1_session_starts(entries: list[datetime], *, gap_minutes: int) -> list[datetime]:
    """Entry timestamps that open a new session: the first one, and any that
    follow a gap of >= `gap_minutes`. PROXY for a market reopen -- the position
    CSVs carry no spread-regime history."""
    starts: list[datetime] = []
    prev: datetime | None = None
    for t in sorted(entries):
        if prev is None or (t - prev) >= timedelta(minutes=gap_minutes):
            starts.append(t)
        prev = t
    return starts


def cap_replay_drops(intervals: list[tuple[datetime, datetime]], *, cap: int) -> list[int]:
    """Indices a chronological greedy replay would have refused because `cap`
    fichas were already open. Entries are considered in entry order."""
    order = sorted(range(len(intervals)), key=lambda i: intervals[i][0])
    open_ends: list[datetime] = []
    dropped: list[int] = []
    for i in order:
        start, end = intervals[i]
        open_ends = [e for e in open_ends if e > start]
        if len(open_ends) >= cap:
            dropped.append(i)
            continue
        open_ends.append(end)
    return sorted(dropped)


def _delta(kept_net: float, total_net: float, kept_n: int, total_n: int) -> dict:
    return {"kept_n": kept_n, "dropped_n": total_n - kept_n,
            "kept_net_clp": kept_net, "total_net_clp": total_net,
            "net_delta_clp": kept_net - total_net,
            "net_delta_pct": (100.0 * (kept_net - total_net) / abs(total_net)
                              if total_net else 0.0)}


def main() -> int:
    rows = load_positions()
    total_net = sum(p.net_067lot_clp for p in rows)
    verdicts: dict[str, dict] = {}

    # --- B1 (proxy) ------------------------------------------------------
    starts = b1_session_starts([p.t_in for p in rows], gap_minutes=B1_SESSION_GAP_MINUTES)
    start_set = set(starts)
    kept = []
    for p in rows:
        recent = [s for s in starts if s <= p.t_in]
        blocked = bool(recent) and (p.t_in - recent[-1]) < timedelta(minutes=B1_WAIT_MINUTES)
        if not blocked:
            kept.append(p)
    verdicts["B1"] = {
        "evaluable": True, "method": "PROXY: session start = gap >= 60 min in the merged entry stream",
        "n_sessions": len(start_set),
        **_delta(sum(p.net_067lot_clp for p in kept), total_net, len(kept), len(rows)),
    }

    # --- B2 (only over the calendar's coverage) --------------------------
    windows = news_calendar.load_windows(minutes_before=B2_BLACKOUT_MINUTES,
                                         minutes_after=B2_BLACKOUT_MINUTES)
    if not windows:
        verdicts["B2"] = {
            "evaluable": False,
            "method": "the committed calendar covers no date inside 2026-01..2026-07",
            "verdict": "NOT EVALUABLE -- no veto by absence of evidence"}
    else:
        lo = min(w[0] for w in windows).replace(tzinfo=None)
        hi = max(w[1] for w in windows).replace(tzinfo=None)
        in_range = [p for p in rows if lo <= p.t_in <= hi]
        if not in_range:
            verdicts["B2"] = {
                "evaluable": False,
                "calendar_range": [lo.isoformat(), hi.isoformat()],
                "method": "calendar range does not overlap the backtest period",
                "verdict": "NOT EVALUABLE -- no veto by absence of evidence"}
        else:
            naive = [(a.replace(tzinfo=None), b.replace(tzinfo=None)) for a, b in windows]
            kept = [p for p in in_range
                    if not any(a <= p.t_in <= b for a, b in naive)]
            verdicts["B2"] = {
                "evaluable": True,
                "calendar_range": [lo.isoformat(), hi.isoformat()],
                "method": "positions entered inside +/-30 min of a calendar event, over the covered range only",
                **_delta(sum(p.net_067lot_clp for p in kept),
                         sum(p.net_067lot_clp for p in in_range),
                         len(kept), len(in_range))}

    # --- B3 (must drop exactly nothing) ----------------------------------
    import json
    cap = json.loads((Path(__file__).resolve().parents[3] / "data" / "analysis"
                      / "monday_audit" / "a2_overlap.json").read_text(encoding="utf-8")
                     )["max_simultaneous_fichas"]
    drops = cap_replay_drops([(p.t_in, p.t_out) for p in rows], cap=cap)
    verdicts["B3"] = {
        "evaluable": True, "cap": cap, "dropped_n": len(drops),
        "method": "chronological greedy replay against the observed-peak cap",
        "expected": "ZERO drops -- the cap IS the observed peak, so it never bit"}

    # --- B4 (not maskable, by design) ------------------------------------
    verdicts["B4"] = {
        "evaluable": False,
        "method": "the position CSVs carry no SL column; reconstructing it means re-simulating (out of scope)",
        "verdict": "NOT MASKABLE -- B4 is a live BUG DETECTOR, not a filter"}

    write_artifact("b6_mask_verdicts.json", verdicts)

    lines = ["# Wrapper mask verdicts â€” 2026-07-25", "",
             "> Each mask VETOES a wrapper if it would have been catastrophic.",
             "> **It never selects between variants** â€” that would be re-tuning (spec R3).",
             f"> Substrate: {len(rows)} positions, net {total_net:,.0f} CLP @0.67 lot.", ""]
    for gate, v in verdicts.items():
        lines.append(f"## {gate}")
        for k, val in v.items():
            lines.append(f"- **{k}:** {val}")
        lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    for gate, v in verdicts.items():
        print(f"  {gate}: {v.get('verdict') or v.get('net_delta_pct')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/analysis/test_monday_audit.py -k "session_starts or cap_replay" -v`
Expected: 4 passed.

- [ ] **Step 5: Run it and read the verdicts**

Run: `python -m scripts.analysis.monday_audit.b6_masks`

**Then decide, per gate, using only the veto rule:**
- If a gate's `net_delta_pct` is catastrophic (the wrapper would have destroyed the track),
  **do not deploy that gate** â€” remove its key from `CHALLENGER_RISK_GATES` in Task 4's block,
  re-run Task 4's and Task 5's tests, and record the veto in the tracker with the number.
- Otherwise deploy it unchanged. **Do not adjust any threshold.**
- **B3 must show `dropped_n == 0`.** If not, STOP and report.

- [ ] **Step 6: Commit**

```bash
git -C D:/FOREX add scripts/analysis/monday_audit/b6_masks.py tests/analysis/test_monday_audit.py data/analysis/monday_audit/b6_mask_verdicts.json docs/superpowers/research/2026-07-25-wrapper-mask-verdicts.md
git -C D:/FOREX commit -m "feat(analysis): retrospective wrapper masks -- veto verdicts for B1-B4"
```

- [ ] **Step 7: Update the tracker** â€” set Task 10 to `[x]` and record all four verdicts verbatim,
  including the two "NOT EVALUABLE / NOT MASKABLE" ones. **Spec Â§9 requires the verdict to be on
  the record whether or not it is favourable.**

---

## Task 11: Revert rehearsal â€” prove the one-command rollback

**Depends on:** Tasks 0, 4, 5.

**Files:**
- Test: `tests/scripts/test_challenger_rollback.py` (create)

**Interfaces:**
- Consumes: tag `pre-challenger-2026-07-25` (Task 0).
- Produces: a rehearsed, documented rollback procedure recorded in the tracker.

**Why this exists:** the spec's backup guarantee (Â§3.2) is "if the challenger is a disaster, the
champion kept running and Monday's system is today's system". That is only true if reverting is a
one-command operation somebody can perform under pressure, not an improvisation.

- [ ] **Step 1: Write the guard test**

Create `tests/scripts/test_challenger_rollback.py`:

```python
"""tests/scripts/test_challenger_rollback.py -- the rollback guarantee.

The challenger must be removable by pointing the executor back at the `local`
roster, WITHOUT touching a line of champion code. This test pins that down: the
champion roster served under `--configs local` must be identical whether or not
the challenger module exists.
"""
from __future__ import annotations

from sentinel_engine.strategies.live_configs_20 import CONFIGS_CHALLENGER, CONFIGS_LOCAL

# The champion roster EXACTLY as it shipped on 2026-07-22 (commit f93e54a),
# written as literals so importing the challenger cannot influence it.
_CHAMPION_AS_SHIPPED = [
    ("S6-K2P0", 724010, 0.1),
    ("S7-TPNONE", 724020, 0.1),
    ("SuperTrend-p14x3-M15", 724070, 0.1),
    ("TK-Momentum-5-8-short", 999999998, 0.01),
]


def test_champion_roster_matches_what_shipped_before_the_challenger():
    assert [(c["id"], c["magic"], c["volume"]) for c in CONFIGS_LOCAL] == _CHAMPION_AS_SHIPPED


def test_rolling_back_is_a_roster_switch_not_a_code_change():
    # The two sleeves share NO object identity: dropping the challenger from
    # the roster removes it completely, with nothing left behind in champion
    # configs.
    champion_ids = {id(c) for c in CONFIGS_LOCAL}
    challenger_ids = {id(c) for c in CONFIGS_CHALLENGER}
    assert champion_ids.isdisjoint(challenger_ids)
    for c in CONFIGS_LOCAL:
        assert "risk_gates" not in c
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/scripts/test_challenger_rollback.py -v`
Expected: 2 passed.

- [ ] **Step 3: Rehearse the rollback in a scratch worktree (never in the live tree)**

```bash
git -C D:/FOREX worktree add C:/Users/tomas/AppData/Local/Temp/claude/D--FOREX/rollback-rehearsal pre-challenger-2026-07-25
cd C:/Users/tomas/AppData/Local/Temp/claude/D--FOREX/rollback-rehearsal
python -m pytest tests/scripts/test_run_live_20.py -k "local" -v
```

Expected: the pre-challenger tree is green on its own `local` tests â€” i.e. the tag is a genuinely
runnable rollback point, not just a label.

- [ ] **Step 4: Remove the rehearsal worktree**

```bash
git -C D:/FOREX worktree remove C:/Users/tomas/AppData/Local/Temp/claude/D--FOREX/rollback-rehearsal
```

- [ ] **Step 5: Write the rollback procedure into the tracker**

Under a `## Rollback` heading in the tracker, record these three levels verbatim:

1. **Level 1 (seconds, no code):** set `SUPERVISOR_CONFIGS=local` and restart the supervisor. The
   challenger stops opening; the champion is untouched. Any open 726xxx positions are managed to
   their exits by re-arming `local+challenger` briefly, or closed by hand.
2. **Level 2 (one command):** `git -C D:/FOREX revert --no-edit <challenger commits>` on `equipo1`.
3. **Level 3 (nuclear):** `git -C D:/FOREX checkout pre-challenger-2026-07-25 -- sentinel_engine scripts`
   then commit. Returns the code to the pre-challenger state exactly.

- [ ] **Step 6: Commit**

```bash
git -C D:/FOREX add tests/scripts/test_challenger_rollback.py docs/superpowers/plans/2026-07-25-monday-tracker.md
git -C D:/FOREX commit -m "test(live): rollback guarantee -- champion roster provably unchanged by the challenger"
```

---

## Task 12: Deploy â€” machine-1, DEMO 2883015767

**âš ï¸ REQUIRES THE USER'S HANDS.** ATTACH-ONLY is a hard rule: no script may launch an MT5 terminal.
A subagent executes Steps 1â€“4 and 7â€“8; **Steps 5 and 6 are for the user**, and the subagent must
stop and ask rather than improvise.

**Depends on:** every preceding task except 14.

**Files:**
- Modify: the machine-1 watchdog environment (`SUPERVISOR_CONFIGS`), via the Task Scheduler task
  `SENTINEL_Watchdog_Machine1` / `scripts/live/watchdog_local.ps1`.

- [ ] **Step 1: Full test sweep**

```bash
python -m pytest tests/ -q
```

Expected: green except the 2 known `test_web_positions.py` failures. **Any other red blocks the
deploy** â€” report it, do not deploy around it.

- [ ] **Step 2: Dry-run the combined roster against the live terminal**

```bash
python -m scripts.live.run_live_20 --once --configs local+challenger --no-adaptive-spread --max-spread-open 0.5
```

Expected in the output:
- `7 configs`
- one `[risk-gates] now=... spread=... spread_ok_since=... open_fichas=... news_windows=N` line
- **ZERO orders sent** (no `--arm`)
- If `news_windows=NONE(FAIL-CLOSED)` appears, the calendar is unreadable â†’ **fix Task 2 before
  deploying**, otherwise the challenger will never open.

- [ ] **Step 3: Confirm the account guard and the magic seeding**

```bash
python -c "from sentinel_engine.live import guard_cuenta; print(guard_cuenta.DEMO_LOGIN)"
```

Expected: `2883015767`. The executor calls `ensure_magic_allocations(...)` with the resolved roster
at startup (`run_live_20.py:1032`), so the 726xxx magics label themselves in the deals watcher with
no extra work. Verify after the first armed cycle:

```bash
python -c "import sqlite3;print(sqlite3.connect(r'<the magic-allocation db path from run_live_20>').execute('select magic,strategy_id from magic_allocation where magic between 726000 and 726999').fetchall())"
```

Expected: 12 rows (3 configs Ã— 4 ficha offsets).

- [ ] **Step 4: Point the watchdog at the combined roster**

Change `SUPERVISOR_CONFIGS` from `local` to `local+challenger` wherever the machine-1 watchdog sets
it (`scripts/live/watchdog_local.ps1` and/or the scheduled task's environment). Leave
`SUPERVISOR_MAX_SPREAD_OPEN=0.5` and `SUPERVISOR_STALE_AUTORESTART=1` exactly as they are.

**Do not change the `/portable` handling** â€” that fix (`bd28169`) is what stops a second MT5
terminal from spawning.

- [ ] **Step 5: ðŸ™‹ USER â€” open the MT5 terminal and confirm the account**

Ask the user to open the portable MT5 terminal logged into DEMO **2883015767** and confirm it is
the demo account, not the real one. Wait for their confirmation; do not proceed without it.

- [ ] **Step 6: ðŸ™‹ USER â€” restart the supervisor**

Ask the user to restart `SENTINEL_Watchdog_Machine1` (or run the launcher) so the executor picks up
the new `SUPERVISOR_CONFIGS`.

- [ ] **Step 7: Verify the live cycle**

```bash
python -c "import pathlib;p=pathlib.Path('scripts/live/run_live_20.audit.log');print(p.read_text(encoding='utf-8',errors='replace')[-6000:])"
```

Expected in the tail: `7 configs`, `guard OK`, a `[risk-gates]` line each cycle, and â€” because the
market is closed over the weekend â€” `[RISK_GATE_SKIP] gate=B1` on any challenger OPEN the sim wants.
That skip is **correct behaviour**, not a failure: the gap-wait clock has not started.

- [ ] **Step 8: Update the tracker**

Set Task 12 to `[x]`; paste the `[risk-gates]` line and the roster count from the live log; record
the exact time the combined roster went live.

---

## Task 13: The Monday document

**Depends on:** Tasks 7, 8, 9, 10, 12.

**Files:**
- Create: `docs/INFORME_ENTREGA_LUNES_2026-07-27.md`

**Hard rule:** every number in this document is **copied from a JSON artifact**, never typed from
memory or recomputed in prose (R5). Cite the artifact path next to each figure.

**Structure, fixed:**

1. **QuÃ© se entrega.** Champion + challenger running side by side on one account. Three mirrored
   signals at 0.02 with a risk layer; the champion untouched at 0.1.
2. **QuÃ© NO se tocÃ³, y por quÃ©.** The signals. Explain the reasoning honestly: re-optimising the
   parameters this weekend was the available temptation and it is the same mistake that produced
   DSRâ‰ˆ0 over 225 trials. The infrastructure that would make it legitimate â€” Phase 0, the MT5
   confirmation of the real-tick magnitudes (Task 2.2), the walk-forward/holdout of Phase 12 â€” does
   not exist yet. Say that plainly.
3. **La capa de riesgo (B1â€“B4).** One paragraph each: what it does, where its number comes from,
   and the mask verdict from `b6_mask_verdicts.json` â€” **including the two that are not evaluable**.
4. **La auditorÃ­a.** The A1 drawdown (confirmed or corrected against âˆ’28,6 %), A2's overlap and
   correlations, A3's exit attribution, A4's serial structure, A5's 7-month verdict on the 0.5
   spread gate.
5. **CÃ³mo se lee A vs B.** Comparison is **per trade and size-normalised**, so the 0.1 vs 0.02 lot
   difference does not distort it. State the minimum sample before the comparison means anything,
   and state that a week of data will not settle it.
6. **Rollback.** The three levels from Task 11, verbatim.
7. **QuÃ© sigue.** Task 2.2 (MT5 confirmation), Phase 0, walk-forward â€” the work that has to exist
   before any re-optimisation is honest.

- [ ] **Step 1: Collect every number**

```bash
python -c "import json,glob,pathlib;[print('==',p,'==\n',pathlib.Path(p).read_text(encoding='utf-8')) for p in sorted(glob.glob('data/analysis/monday_audit/*.json'))]"
```

- [ ] **Step 2: Write the document** following the structure above, citing artifact paths inline.

- [ ] **Step 3: Verify no number is unsourced**

Re-read the document and check every figure against the artifacts. Any number you cannot trace to a
file must be deleted or computed.

- [ ] **Step 4: Commit**

```bash
git -C D:/FOREX add docs/INFORME_ENTREGA_LUNES_2026-07-27.md
git -C D:/FOREX commit -m "docs: Monday delivery report -- champion/challenger, risk layer, audit"
```

- [ ] **Step 5: Update the tracker** â€” set Task 13 to `[x]`. **Nothing is "delivered" until the user
  has reviewed it**; mark it `EMITIDO, esperando revisiÃ³n`.

---

## Task 14: Track C â€” random-entry study (NON-BLOCKING)

**Runs only after Monday's deliverable is safe.** It changes nothing about the deployment; it
redirects the coming weeks by answering whether the edge lives in the entries or the exits.

**Files:**
- Create: `scripts/analysis/random_entry/study.py`
- Create: `docs/superpowers/research/2026-07-25-random-entry-study.md`

**Read first:** `scripts/analysis/realtick_bt/backtest.py` â€” it already provides `load_bars()`,
`Ticks`, `run_ladder(kwargs, bars)`, `run_supertrend(bars, ticks)`, `resolve(pos, ticks, bar_times)`
and `metrics(rows, lot)`. Reuse them; do not re-implement the engine and do not modify that file.

**The experimental design, fixed in advance:**

- **Null model:** keep each strategy's **exit machinery and position count** exactly as they are,
  but replace the **entry bar index** of every position with one drawn uniformly at random from the
  same month, preserving the side distribution (long/short proportions per strategy per month).
- **Runs:** 200 random seeds. Every run is resolved through the same `resolve()` used by the real
  backtest, so fills and costs are treated identically.
- **Statistic:** total net CLP at 0.67 lot per run â†’ an empirical null distribution. Report where
  the real track's net falls in it (percentile), per strategy and combined.
- **Reading, stated in advance so it cannot be rationalised afterwards:** if the real entries land
  **inside** the bulk of the random distribution, the edge is in the exits, and the entry-filter
  phases of the v2 plan should be cancelled. If they land **far in the right tail**, the entries
  carry real information.

- [ ] **Step 1** â€” Read `backtest.py` end to end. Write down the exact shape of a position dict
  returned by `run_ladder` / `run_supertrend` and what `resolve` needs.
- [ ] **Step 2** â€” Implement the randomiser as a pure function
  `randomise_entries(positions, bars, seed) -> list[dict]` and unit-test that it preserves the
  count, the side mix and the month of every position.
- [ ] **Step 3** â€” Run 200 seeds. This is CPU-bound (~4â€“6 h); launch it in the background and do not
  block the Monday work on it.
- [ ] **Step 4** â€” Write the report with the percentile of the real track in the null distribution,
  per strategy and combined, plus the explicit reading rule above.
- [ ] **Step 5** â€” Commit and update the tracker.

---

## Self-Review

Checked after writing, against `docs/superpowers/specs/2026-07-25-monday-champion-challenger-design.md`:

**Spec coverage.** Â§2.1 R1â€“R5 â†’ Global Constraints + the guard tests in Tasks 4/11. Â§4.1 champion
untouched â†’ Task 4 Step 1 (`test_champion_roster_is_untouched_by_the_challenger`) and Task 11.
Â§4.2 challenger roster, deep copies, 726xxx band â†’ Task 4. Â§4.3 B1 â†’ Tasks 1+3; B2 â†’ Tasks 1+2;
B3 â†’ Tasks 1+8 (the cap); B4 â†’ Task 1. Â§4.3 insertion point beside `SPREAD_GATE_SKIP` â†’ Task 5
Step 4. Â§4.4 masks veto-not-select â†’ Task 10, with the rule restated at the top of the task.
Â§5.1 Pista A items 1â€“5 â†’ Tasks 7 (maxDD), 8 (overlap/correlation, and the `CONFIGS_GOLIVE_DEDUP`
loose end which the spec itself already closed), 9 (exit attribution, serial correlation, spread
gate). Â§5.2 Pista B + git tag + rehearsed revert â†’ Tasks 4, 5, 11. Â§5.3 Pista C â†’ Task 14.
Â§5.4 document â†’ Task 13. Â§6 error handling: gate denials log and return like `SPREAD_GATE_SKIP`
(Task 5 Step 4); B2 fail-closed (Tasks 1+2); band violation â†’ `AssertionError` at import (Task 4);
B4 treated as a bug (Task 1's reason string and Task 10's "NOT MASKABLE" verdict). Â§7 the four
guards â†’ Task 4's tests (guards 1â€“3) and Task 5's
`test_champion_only_roster_never_builds_a_gate_context` (guard 4). Â§8 out of scope â†’ nothing in
this plan touches Task 2.2, the mean-reversion sleeve, pyramiding, meta-labeling or machine 2.
Â§9 acceptance â†’ Tasks 12 (both sleeves live), 10 (mask verdicts recorded), 11 (tag + rehearsed
revert), 7 (maxDD), 13 (document), 14 (Pista C, non-blocking).

**Known gap, stated rather than hidden:** B2's retrospective mask is only evaluable over the range
the committed calendar covers. If the user supplies no historical calendar, the verdict is
"NOT EVALUABLE â€” no veto by absence of evidence". That is a real limitation of this delivery and
Task 13 must say so in the document rather than let the wrapper look better-evidenced than it is.

**Placeholder scan.** No "TBD", no "add error handling", no "similar to Task N". The two
deliberately open values are (a) `<A2>` in Task 4, which Task 8 computes and Task 4 Step 3 reads
from disk, and (b) the calendar rows in Task 2 Step 4, which are data with a stated sourcing order.

**Type consistency.** Gate keys `gap_wait_minutes` / `news_blackout_minutes` / `max_open_fichas` /
`min_sl_distance` are spelled identically in Tasks 1, 4, 5 and 10. `GateInput` field names match
between Task 1's definition and Task 5's construction. `GateCycleContext` fields (`now`,
`spread_ok_since`, `news_windows`, `open_fichas`) match between Task 5's definition, its use in
`execute_action`, and the tests. `load_windows(path, *, minutes_before, minutes_after)` is called
with the same signature in Tasks 5 and 10. `Position.net_at_lot` is defined in Task 6 and used in
Task 7.
