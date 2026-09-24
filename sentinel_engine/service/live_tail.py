"""sentinel_engine.service.live_tail — in-formation bar tail (Wave A, A10).

Maintains the CURRENTLY-FORMING bar per (symbol, tf) for TFs M1/M2/M5/M15,
built purely from ticks (never written to the lake — memory only). On each
tick `(symbol, price, volume, ts_epoch_seconds)`:

  bucket = ts - (ts % tf_seconds)

- if `bucket` matches the currently-open bar's bucket: update h/l/c (+v),
  emit `closed: false`.
- if `bucket` is a NEW bucket (advanced past the open bar's bucket): emit
  the previous bar as CLOSED (`closed: true`), then open a new bar with
  `o = h = l = c = price` at the new bucket, emit `closed: false`.

This module owns only the bar-maintenance state machine + a minimal
broadcaster (`LiveTailHub`) that fans out `bar_tail` events to SSE
subscribers. It does NOT own a tick source — the caller (the `/api/bars/tail`
route in `sentinel_engine.service.routers.bars`) feeds it ticks pulled from
the EXISTING `TickHub` (`sentinel_engine.service.stream.TickHub`), the same
hub already powering `/ws/ticks`. See `routers/bars.py` for the subscription
wiring; this module has no MT5 import and never calls `mt5.initialize()`.

Throttle note: the SPEC permits at most 1 in-progress (`closed:false`)
emission per second per (symbol, tf) as an acceptable throttle. This module
itself emits on every tick update (no internal timer) — the throttle is
applied by the caller (the SSE route), which drops non-closed emissions
that arrive within 1s of the last one it forwarded for that (symbol, tf).
Closed-bar emissions are NEVER throttled/dropped.
"""
from __future__ import annotations

from typing import Any, Callable

TF_SECONDS: dict[str, int] = {"M1": 60, "M2": 120, "M5": 300, "M15": 900}

BarEvent = dict[str, Any]


class _FormingBar:
    __slots__ = ("t", "o", "h", "l", "c", "v")

    def __init__(self, bucket: int, price: float, volume: float) -> None:
        self.t = bucket
        self.o = price
        self.h = price
        self.l = price
        self.c = price
        self.v = volume

    def to_dict(self) -> dict[str, Any]:
        return {"t": self.t, "o": self.o, "h": self.h, "l": self.l, "c": self.c, "v": self.v}


class LiveTailMaintainer:
    """Per-(symbol, tf) forming-bar state machine, memory-only (never
    persisted to the lake). `on_tick` returns the list of `bar_tail` events
    produced by this tick, one per maintained TF (usually 1 unless the tick
    also closes a bar, which still yields exactly 1 event per tf per call —
    the closed-bar emission happens on the FOLLOWING tick that rolls into a
    new bucket, per spec: "emit the previous bar as CLOSED ... and open a
    new one" happens together, as a single closed:true event for the just-
    finished bar, immediately followed conceptually by the new bar's first
    closed:false event)."""

    def __init__(self, tfs: tuple[str, ...] = ("M1", "M2", "M5", "M15")) -> None:
        self._tfs = tfs
        # (symbol, tf) -> _FormingBar
        self._bars: dict[tuple[str, str], _FormingBar] = {}

    def on_tick(self, symbol: str, price: float, volume: float, ts: int) -> list[BarEvent]:
        """Feed one tick to every maintained TF for `symbol`. Returns the
        ordered list of `bar_tail` events produced (closed event for the
        rolled-over bar, if any, followed by the new/updated open bar's
        event)."""
        events: list[BarEvent] = []
        for tf in self._tfs:
            tf_s = TF_SECONDS[tf]
            bucket = ts - (ts % tf_s)
            key = (symbol, tf)
            bar = self._bars.get(key)

            if bar is None:
                bar = _FormingBar(bucket, price, volume)
                self._bars[key] = bar
                events.append(self._event(symbol, tf, bar, closed=False))
                continue

            if bucket == bar.t:
                bar.h = max(bar.h, price)
                bar.l = min(bar.l, price)
                bar.c = price
                bar.v += volume
                events.append(self._event(symbol, tf, bar, closed=False))
            elif bucket > bar.t:
                # Rollover: emit the finished bar as closed, then open new.
                events.append(self._event(symbol, tf, bar, closed=True))
                new_bar = _FormingBar(bucket, price, volume)
                self._bars[key] = new_bar
                events.append(self._event(symbol, tf, new_bar, closed=False))
            # bucket < bar.t: out-of-order/late tick — ignored (never
            # rewrites a bar backwards in time).

        return events

    def forming_bar(self, symbol: str, tf: str) -> dict[str, Any] | None:
        bar = self._bars.get((symbol, tf))
        return None if bar is None else bar.to_dict()

    @staticmethod
    def _event(symbol: str, tf: str, bar: _FormingBar, closed: bool) -> BarEvent:
        return {"symbol": symbol, "tf": tf, "bar": bar.to_dict(), "closed": closed}


class LiveTailHub:
    """Bridges tick delivery -> `LiveTailMaintainer` -> per-symbol async
    subscriber queues, for the `/api/bars/tail` SSE route.

    This hub does NOT poll a tick source itself; the caller pushes ticks in
    via `push_tick` (typically driven by piggy-backing on the existing
    `TickHub` poll loop for the same symbol — see `routers/bars.py`). This
    keeps a single source of truth for ticks (no duplicate MT5/tick-source
    polling) per the task's "reuse the same tick plumbing" requirement.
    """

    def __init__(self, tfs: tuple[str, ...] = ("M1", "M2", "M5", "M15"), throttle_seconds: float = 1.0) -> None:
        self._maintainer = LiveTailMaintainer(tfs=tfs)
        self._throttle_seconds = throttle_seconds
        # symbol -> list of async queues (subscribers)
        self._subscribers: dict[str, list[Any]] = {}
        # (symbol, tf) -> last forwarded closed:false wall-clock time (monotonic)
        self._last_forwarded: dict[tuple[str, str], float] = {}

    def push_tick(self, symbol: str, price: float, volume: float, ts: int, *, now: Callable[[], float] | None = None) -> list[BarEvent]:
        """Feed a tick and return the events that pass the throttle (to be
        forwarded to subscribers). Closed events are never throttled."""
        import time as _time

        clock = now or _time.monotonic
        raw_events = self._maintainer.on_tick(symbol, price, volume, ts)
        forwarded: list[BarEvent] = []
        for ev in raw_events:
            key = (ev["symbol"], ev["tf"])
            if ev["closed"]:
                forwarded.append(ev)
                self._last_forwarded[key] = clock()
                continue
            last = self._last_forwarded.get(key)
            t = clock()
            if last is None or (t - last) >= self._throttle_seconds:
                self._last_forwarded[key] = t
                forwarded.append(ev)
        return forwarded

    def forming_bar(self, symbol: str, tf: str) -> dict[str, Any] | None:
        return self._maintainer.forming_bar(symbol, tf)
