// SENTINEL lib/adapters.js — CT-2 adapters (Task A5a, plan Wave A lane B).
// Bridges window.SENTINEL.chartData's barSource (CT-2 bars/overlays) to the
// lib/chart.js candle/overlay/marker rendering surface. Classic script (no
// ES modules), hangs off window.SENTINEL.adapters = {HistAdapter, ReplayAdapter}
// (vlist/vtable-style factory pattern -- plain functions returning an
// instance object, no class syntax required elsewhere in this codebase).
//
// barSource (lib/chartData.js) caches CT-2 bar OBJECTS verbatim per chunk
// (`body.bars` -- `{t,o,h,l,c,v}`, see chartData.js fetchChunk/rebuildMerged),
// so `barSource._bars` is already an ascending array of CT-2 objects; no
// tuple<->object re-hydration is needed here.
//
// HistAdapter(chart, barSource):
//   ensureWindow(fromT, toT) -> Promise<bars>   // barSource.ensureRange + apply
//   Applies the barSource's merged CT-2 bars (clipped to [fromT,toT]) to the
//   chart's candle/volume series (mapped to lightweight-charts
//   {time,open,high,low,close}). Uses ONLY barSource.ensureRange() -- never
//   fetches /api/bars directly. Preserves the loadSeq pattern: every call
//   captures a sequence token and is a no-op if superseded by a later call.
//   applyOverlays(overlaysPayload) maps CT-2 `overlays` ({name:[{t,v}]}) onto
//   chart.addOverlay/addSarDots (SAR by name convention, matching chart.js's
//   own overlaysSpecs registry).
//
// ReplayAdapter(chart, barSource, {fromT, toT, speed, pauseAfterBars}):
//   prime() fetches the window ONCE via barSource.ensureRange; play()/
//   pause()/seek(t) then reveal bars AND overlays in LOCKSTEP (same reveal
//   index into both arrays) off one setInterval, with NO fetch per step.
//
// Markers: setSignals(signals) on a HistAdapter instance renders only
// signals whose entry/exit bar falls inside the CURRENT loaded window,
// re-filtering whenever the window changes, and delegates the actual
// marker/connector/hover-halo drawing to chart.addTradeMarkers (lib/chart.js
// owns hoveredSignalId/findSignalNearConnector/grouping -- this file never
// touches that logic, only decides which trades reach it).
(function () {
  "use strict";

  const TF_SEC = { M1: 60, M2: 120, M5: 300, M10: 600, M15: 900, H1: 3600, D: 86400 };

  function tfSeconds(tf) {
    return TF_SEC[tf] || 60;
  }

  function tsSec(t) {
    return Math.floor(Number(t));
  }

  // Normalizes a bar to the CT-2 OBJECT shape {t,o,h,l,c,v} regardless of
  // whether it arrived as a tuple [t,o,h,l,c,v] or already as an object.
  // Defensive: lib/chartData.js's barSource caches whatever `body.bars`
  // shape a given `api.getBars` implementation returns (real backend and
  // this repo's own chartData tests use different shapes), so this adapter
  // never assumes one or the other.
  function normBar(bar) {
    if (Array.isArray(bar)) {
      return { t: bar[0], o: bar[1], h: bar[2], l: bar[3], c: bar[4], v: bar[5] };
    }
    return bar;
  }

  // CT-2 bar {t,o,h,l,c,v} -> lightweight-charts candlestick point.
  function ct2ToCandle(bar) {
    const b = normBar(bar);
    return { time: tsSec(b.t), open: b.o, high: b.h, low: b.l, close: b.c };
  }

  // CT-2 bar -> lightweight-charts volume point (color derives from up/down).
  function ct2ToVolume(bar, upColor, downColor) {
    const b = normBar(bar);
    return { time: tsSec(b.t), value: b.v || 0, color: b.c >= b.o ? upColor : downColor };
  }

  // CT-2 overlay array [{t,v}] -> lib/chart.js addOverlay/addSarDots point
  // tuples [[t, v], ...] (v may be null/undefined for warmup gaps).
  function ct2OverlayToPoints(points) {
    return (points || []).map((p) => [p.t, p.v === undefined ? null : p.v]);
  }

  function epochOfTradeTs(v) {
    if (typeof v === "number") return v > 1e12 ? v / 1000 : v;
    const d = new Date(v);
    return d.getTime() / 1000;
  }

  // Bucket a raw timestamp to the TF's bar boundary (same snapping rule
  // chart.js's barTimeOf uses internally) so re-anchored markers always
  // land on a bar that exists in the loaded window.
  function bucketOf(epochSec, tfSec) {
    return Math.floor(epochSec / tfSec) * tfSec;
  }

  // True if the trade (V1 shape: side, ts_in, px_in, trade_id/signal_id,
  // optional ts_out) has ANY event (entry or exit) bar time inside
  // [fromT, toT] inclusive -- the definition of "in the loaded window".
  function signalTouchesWindow(trade, fromT, toT, tfSec) {
    const tIn = bucketOf(epochOfTradeTs(trade.ts_in), tfSec);
    if (tIn >= fromT && tIn <= toT) return true;
    if (trade.ts_out) {
      const tOut = bucketOf(epochOfTradeTs(trade.ts_out), tfSec);
      if (tOut >= fromT && tOut <= toT) return true;
    }
    return false;
  }

  // ---- HistAdapter ----
  function HistAdapter(chart, barSource) {
    let seq = 0;
    let windowFrom = null;
    let windowTo = null;
    let allSignals = [];
    let currentTf = (chart && chart.tf) || "M1";

    function clippedBars(fromT, toT) {
      return (barSource._bars || [])
        .map(normBar)
        .filter((b) => b.t >= fromT && b.t <= toT);
    }

    function paintBars(ct2Bars) {
      if (chart._candleSeries) {
        chart._candleSeries.setData(ct2Bars.map(ct2ToCandle));
      }
    }

    function applyOverlays(overlaysPayload) {
      if (!overlaysPayload) return;
      Object.keys(overlaysPayload).forEach((name) => {
        const pts = ct2OverlayToPoints(overlaysPayload[name]);
        if (name === "sar") {
          chart.addSarDots(name, pts);
        } else {
          chart.addOverlay(name, pts);
        }
      });
    }

    // ensureWindow: the PRIMARY paint path -- fetches via barSource
    // (chunked, cached, in-flight-deduped) then commits the clipped bars to
    // the chart's own candle series. Guarded by a local seq token so a
    // superseded call (a newer ensureWindow/setTf started after this one)
    // never clobbers a later window's bars.
    async function ensureWindow(fromT, toT) {
      const mySeq = ++seq;
      await barSource.ensureRange(fromT, toT);
      if (mySeq !== seq) return null; // superseded
      windowFrom = fromT;
      windowTo = toT;
      const ct2Bars = clippedBars(fromT, toT);
      paintBars(ct2Bars);
      refilterSignals();
      return ct2Bars;
    }

    function refilterSignals() {
      if (windowFrom === null) return;
      const tfSec = tfSeconds(currentTf);
      const windowed = allSignals.filter((t) => signalTouchesWindow(t, windowFrom, windowTo, tfSec));
      chart.addTradeMarkers(windowed, null, { dim: false });
    }

    // setSignals: renders ONLY signals inside the currently loaded window,
    // re-filtered whenever the window changes (ensureWindow/setTf). Delegates
    // to chart.addTradeMarkers so lib/chart.js's own
    // grouping/connectors/hoveredSignalId/findSignalNearConnector are
    // untouched.
    function setSignals(signals) {
      allSignals = signals || [];
      refilterSignals();
    }

    // TF switch: re-fetch the window centered on `anchorT` (bar time held
    // constant), re-anchoring by bucketing anchorT to the NEW tf's bar grid.
    // Keeps the same total span (toT - fromT) around the anchor.
    async function setTf(newTf, anchorT) {
      currentTf = newTf;
      const tfSec = tfSeconds(newTf);
      const anchorBucket = bucketOf(anchorT !== undefined && anchorT !== null ? anchorT : (windowFrom || 0), tfSec);
      const span = windowFrom !== null && windowTo !== null ? (windowTo - windowFrom) : 100 * tfSec;
      const half = span / 2;
      return ensureWindow(anchorBucket - half, anchorBucket + half);
    }

    return {
      ensureWindow,
      applyOverlays,
      setSignals,
      setTf,
      get windowFrom() { return windowFrom; },
      get windowTo() { return windowTo; },
    };
  }

  // ---- ReplayAdapter ----
  // Plays back an ALREADY-FETCHED window (barSource.ensureRange, done once
  // in prime()) bar-by-bar, advancing candles AND every active overlay's
  // points in LOCKSTEP (same reveal index) -- no per-step fetch.
  function ReplayAdapter(chart, barSource, options) {
    options = options || {};
    const fromT = options.fromT;
    const toT = options.toT;
    let speed = options.speed || 1;
    const pauseAfterBars = options.pauseAfterBars || null;

    let bars = []; // CT-2 objects, ascending, snapshot of the fetched window
    let overlaysSnapshot = {}; // name -> [{t,v}] filtered to the window
    let idx = 0;
    let timerId = null;
    let playing = false;
    const TICK_MS = 200;

    async function prime() {
      await barSource.ensureRange(fromT, toT);
      bars = (barSource._bars || [])
        .map(normBar)
        .filter((b) => b.t >= fromT && b.t <= toT);
      idx = 0;
    }

    // Reveals bars[0..revealIdx) on the candle series and, in lockstep,
    // overlaysSnapshot[name][0..revealIdx) on each overlay series -- both
    // advance from the SAME index so candles and overlays never drift.
    function revealTo(revealIdx) {
      idx = Math.max(0, Math.min(bars.length, revealIdx));
      const visible = bars.slice(0, idx);
      if (chart._candleSeries) chart._candleSeries.setData(visible.map(ct2ToCandle));
      Object.keys(overlaysSnapshot).forEach((name) => {
        const visiblePts = overlaysSnapshot[name].slice(0, idx);
        const tuples = ct2OverlayToPoints(visiblePts);
        if (name === "sar") chart.addSarDots(name, tuples);
        else chart.addOverlay(name, tuples);
      });
      if (pauseAfterBars && idx > 0 && idx % pauseAfterBars === 0) {
        pause();
      }
    }

    // setOverlays: supplies the (already-fetched, e.g. from CT-2 `overlays`)
    // full-window overlay payload up front; prime() must be called first (or
    // concurrently) so [fromT,toT] clipping matches the primed bars window.
    function setOverlays(overlaysPayload) {
      const filtered = {};
      Object.keys(overlaysPayload || {}).forEach((name) => {
        filtered[name] = (overlaysPayload[name] || []).filter((p) => p.t >= fromT && p.t <= toT);
      });
      overlaysSnapshot = filtered;
    }

    function tick() {
      if (idx >= bars.length) {
        pause();
        return;
      }
      const step = speed === "MAX" ? bars.length : Math.max(1, Math.round(Number(speed) || 1));
      revealTo(Math.min(bars.length, idx + step));
    }

    function clearTimer() {
      if (timerId !== null) {
        clearInterval(timerId);
        timerId = null;
      }
    }

    function play() {
      playing = true;
      clearTimer();
      timerId = setInterval(tick, TICK_MS);
    }

    function pause() {
      playing = false;
      clearTimer();
    }

    function seek(t) {
      const target = tsSec(t);
      let targetIdx = 0;
      while (targetIdx < bars.length && bars[targetIdx].t <= target) targetIdx++;
      revealTo(targetIdx);
    }

    return {
      prime,
      setOverlays,
      play,
      pause,
      seek,
      get isPlaying() { return playing; },
      get index() { return idx; },
      get bars() { return bars.slice(); },
    };
  }

  // ---- LiveAdapter ----
  // LiveAdapter = HistAdapter + a `bar_tail` SSE subscription (CT-9,
  // GET /api/bars/tail?symbol=...). Wraps a HistAdapter instance (same
  // ensureWindow/applyOverlays/setSignals/setTf API, delegated straight
  // through) and layers connect()/disconnect() on top:
  //   - connect() opens an EventSource to /api/bars/tail and listens for the
  //     named `bar_tail` event. Each event's `{symbol,tf,bar,closed}` is
  //     filtered to this chart's symbol + CURRENT tf (the underlying
  //     HistAdapter's tracked tf, which setTf() keeps in sync) -- events for
  //     any other tf are ignored (a TF switch just naturally stops matching
  //     until the user switches back).
  //   - Updates are coalesced onto requestAnimationFrame: at most one
  //     series.update() per animation frame, using the LATEST bar_tail event
  //     received since the last frame (rAF throttle).
  //   - Auto-scroll: series.update() is only allowed to move the viewport
  //     when the chart's timeScale is already at (or very near) the right
  //     edge (scrollPosition() ~ 0, lightweight-charts convention -- 0 is
  //     "no bars scrolled past the latest"). If the user has panned left,
  //     the update is SKIPPED entirely (no partial candle flicker, no
  //     viewport yank while inspecting history) -- matches HistAdapter's
  //     "never surprise the user's current view" ethos.
  //   - Tab-hide: subscribes to `document.visibilitychange` and calls
  //     disconnect() when `document.hidden` becomes true (laptop battery /
  //     backgrounded-tab hygiene) -- does NOT auto-reconnect on visible
  //     again; the caller (chart.js/charts.js wiring) decides whether to
  //     call connect() again, matching the CT-9 contract of "the client
  //     manages its own subscription lifecycle".
  //   - 503 degrade: if the server has no live tick source attached (MT5 not
  //     attached), GET /api/bars/tail responds 503 JSON {"live":false}
  //     instead of opening an SSE stream. LiveAdapter treats this as an
  //     expected, silent degrade to pure HistAdapter behaviour: logs via
  //     console.info and returns without throwing or opening an
  //     EventSource (EventSource itself is only constructed after a
  //     successful liveness probe).
  function LiveAdapter(chart, barSource, options) {
    options = options || {};
    const symbol = options.symbol || (chart && chart.symbol);
    const hist = HistAdapter(chart, barSource);

    let es = null;
    let pendingBar = null;
    let pendingTf = null;
    let rafScheduled = false;
    let currentTf = (chart && chart.tf) || "M1";

    function isAtRightEdge() {
      if (!chart || typeof chart.timeScale !== "function") return true;
      const ts = chart.timeScale();
      if (!ts || typeof ts.scrollPosition !== "function") return true;
      const pos = ts.scrollPosition();
      return Math.abs(pos) < 1e-6;
    }

    function flush() {
      rafScheduled = false;
      if (!pendingBar) return;
      const bar = pendingBar;
      pendingBar = null;
      if (!isAtRightEdge()) return;
      if (chart._candleSeries && typeof chart._candleSeries.update === "function") {
        chart._candleSeries.update(ct2ToCandle(bar));
      }
    }

    function scheduleFlush() {
      if (rafScheduled) return;
      rafScheduled = true;
      requestAnimationFrame(flush);
    }

    function onBarTail(evt) {
      let payload;
      try {
        payload = JSON.parse(evt.data);
      } catch (e) {
        return;
      }
      if (symbol && payload.symbol && payload.symbol !== symbol) return;
      if (payload.tf && payload.tf !== currentTf) return;
      pendingBar = normBar(payload.bar);
      pendingTf = payload.tf;
      scheduleFlush();
    }

    function onVisibilityChange() {
      if (typeof document !== "undefined" && document.hidden) {
        disconnect();
      }
    }

    function connect() {
      if (es) return; // already connected
      const url = `/api/bars/tail?symbol=${encodeURIComponent(symbol || "")}`;
      es = new EventSource(url);
      es.addEventListener("bar_tail", onBarTail);
      if (typeof document !== "undefined" && typeof document.addEventListener === "function") {
        document.addEventListener("visibilitychange", onVisibilityChange);
      }
    }

    function disconnect() {
      if (es) {
        try { es.close(); } catch (e) { /* noop */ }
        es = null;
      }
      if (typeof document !== "undefined" && typeof document.removeEventListener === "function") {
        document.removeEventListener("visibilitychange", onVisibilityChange);
      }
    }

    async function ensureWindow(fromT, toT) {
      return hist.ensureWindow(fromT, toT);
    }

    async function setTf(newTf, anchorT) {
      currentTf = newTf;
      return hist.setTf(newTf, anchorT);
    }

    return {
      ensureWindow,
      applyOverlays: hist.applyOverlays,
      setSignals: hist.setSignals,
      setTf,
      connect,
      disconnect,
      get windowFrom() { return hist.windowFrom; },
      get windowTo() { return hist.windowTo; },
    };
  }

  // probeLiveTail: fire-and-forget liveness probe for /api/bars/tail --
  // GET returns 503 JSON {"live":false} when no tick source is attached
  // (e.g. MT5 not attached). Callers (chart.js/charts.js wiring) should
  // check this BEFORE calling LiveAdapter.connect() so the 503 case never
  // opens (and immediately fails) an EventSource; degrades silently via
  // console.info, per CT-9 ("no error visible").
  async function probeLiveTailAvailable(symbol) {
    try {
      const resp = await fetch(`/api/bars/tail?symbol=${encodeURIComponent(symbol)}`, { method: "HEAD" });
      if (resp.status === 503) {
        console.info("[LiveAdapter] live tail unavailable (503) -- degrading to HistAdapter-only", symbol);
        return false;
      }
      return true;
    } catch (e) {
      console.info("[LiveAdapter] live tail probe failed -- degrading to HistAdapter-only", symbol, e);
      return false;
    }
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.adapters = {
    HistAdapter, ReplayAdapter, LiveAdapter, ct2ToCandle, ct2ToVolume, ct2OverlayToPoints, bucketOf,
    probeLiveTailAvailable,
  };
})();
