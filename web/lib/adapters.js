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

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.adapters = { HistAdapter, ReplayAdapter, ct2ToCandle, ct2ToVolume, ct2OverlayToPoints, bucketOf };
})();
