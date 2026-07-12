// SENTINEL lib/chart.js — shared chart module (Task M1.3, plan §D.4/D.6/D.7).
// Wraps TradingView lightweight-charts v4.2.0 (vendored, Apache-2.0) behind
// a single API reused by CHARTS (M1.3) and TRADE REVIEW (M2.2). Classic
// script (no ES modules), hangs off window.SENTINEL.chart.create(el, opts).
//
// API (plan §D.7 / Task M1.3):
//   const inst = window.SENTINEL.chart.create(el, {symbol, tf});
//   inst.setWindow(fromEpochSec, toEpochSec)   -> refetch /api/bars for [from,to]
//   inst.setTF(tf)                              -> refetch /api/bars for new TF
//   inst.addTradeMarkers(trades, colorHex, {dim})
//   inst.selectTrade(trade)                     -> D.4 selection (scale/glow/recenter/SL-TP)
//   inst.enableTicks(symbol)                    -> WS subscribe, live candle.update()
//   inst.disableTicks()
//   inst.addOverlay(id, points)                 -> points: [[ts, value], ...] line series
//   inst.addSarDots(id, points, colorHex)       -> points: [[ts, value], ...] per-bar dots (SAR)
//   inst.removeOverlay(id)                      -> removes either kind (same overlays map)
//   inst.destroy()
//
// Playback API (Task M2.6, plan §D.7/§D.4 forward-walk variable-speed):
//   inst.startPlayback({speed})  -> speed in PLAYBACK_SPEEDS (1,5,20,60,"MAX")
//   inst.pausePlayback()
//   inst.seekPlayback(tsEpochSec)
//   inst.stopPlayback()          -> restores full view (all bars + all trades)
//   inst.isPlaying()             -> bool
//   inst.PLAYBACK_SPEEDS         -> [1,5,20,60,"MAX"]
// Playback reveals the already-fetched `bars` sequentially via ONE timer
// (setInterval), cleared on pause/stop/destroy. As the cursor advances,
// trade markers appear at ts_in and gain their exit+connector once
// ts_out <= cursor (reusing addTradeMarkers/buildMarkers/drawConnector).
// Mutually exclusive with live-ticks: starting one disables the other.
//
// Candle colors = long/short design tokens (D.2): --long #26a69a / --short #ef5350.
(function () {
  "use strict";

  const LONG_COLOR = "#26a69a";
  const SHORT_COLOR = "#ef5350";
  // Hover-halo color (electric sky-blue / "celeste eléctrico"). Single knob
  // for the user to fine-tune the shade/intensity of the whole-group hover
  // highlight (markers + connectors) — see buildMarkers()/redrawConnectors().
  const HOVER_HALO_COLOR = "#29e0ff";

  const TF_LIST = ["M1", "M2", "M5", "M10", "M15"];

  function tsSec(t) {
    // lightweight-charts wants seconds (UTCTimestamp) for time-based series.
    return Math.floor(Number(t));
  }

  const TF_SEC = { M1: 60, M2: 120, M5: 300, M10: 600, M15: 900 };

  function barToCandle(bar) {
    const [ts, o, h, l, c] = bar;
    return { time: tsSec(ts), open: o, high: h, low: l, close: c };
  }

  function barToVolume(bar, up) {
    const [ts, , , , , v] = bar;
    return { time: tsSec(ts), value: v || 0, color: up ? LONG_COLOR : SHORT_COLOR };
  }

  function wsUrl() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/ws/ticks`;
  }

  function create(el, opts) {
    opts = opts || {};
    if (typeof LightweightCharts === "undefined") {
      el.innerHTML = '<div class="chart-error">lightweight-charts no disponible (vendor no cargado).</div>';
      return null;
    }

    let symbol = opts.symbol || "XAUUSD";
    let tf = opts.tf || "M1";

    // Wave-2b gap/wavy-line fix: lightweight-charts merges ALL series' time
    // points into one shared time scale. Trade event times (ts_out often at
    // :40s) don't align to bar boundaries (M1 bars at :00s), so handing raw
    // event times to any series injects a phantom off-bar column -> visible
    // gaps between real candles. Snap EVERY trade-derived time to the TF's
    // bar boundary before it ever reaches a series/marker.
    function secPerBar() { return TF_SEC[tf] || 60; }
    function barTimeOf(epochSec) {
      const s = secPerBar();
      return Math.floor(Number(epochSec) / s) * s;
    }

    // ---- DOM scaffold ----
    el.innerHTML = "";
    const root = document.createElement("div");
    root.className = "chart-root";
    const canvasHost = document.createElement("div");
    canvasHost.className = "chart-canvas-host";
    const tooltip = document.createElement("div");
    tooltip.className = "chart-tooltip";
    tooltip.hidden = true;
    const stateOverlay = document.createElement("div");
    stateOverlay.className = "chart-state-overlay";
    stateOverlay.hidden = true;
    root.appendChild(canvasHost);
    root.appendChild(tooltip);
    root.appendChild(stateOverlay);
    el.appendChild(root);

    const chart = LightweightCharts.createChart(canvasHost, {
      layout: {
        background: { color: "transparent" },
        textColor: "#8b98ab",
      },
      grid: {
        vertLines: { color: "rgba(0,191,255,.06)" },
        horzLines: { color: "rgba(0,191,255,.06)" },
      },
      crosshair: { mode: LightweightCharts.CrosshairMode.Magnet },
      // Free navigation (pan L/R, wheel zoom, drag the price axis for up/down):
      // all enabled explicitly so the chart is fully interactive in REVIEW.
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: { time: true, price: true },
        axisDoubleClickReset: { time: true, price: true },
      },
      rightPriceScale: { borderColor: "rgba(0,191,255,.18)" },
      timeScale: { borderColor: "rgba(0,191,255,.18)", timeVisible: true, secondsVisible: false },
      // ROOT-CAUSE FIX (2026-07-11b6): the correct lightweight-charts v4 option
      // is `autoSize` (verified: the vendored v4.2.0 bundle contains `autoSize`
      // and NO `autoResize`). We had `autoResize: true`, an UNKNOWN option that
      // v4 silently ignores, so the chart was created at a stale/creation-time
      // size and never tracked its container. Candles still painted (the canvas
      // bitmap is CSS-scaled), but lightweight-charts' pointer hit-test and
      // crosshair use its INTERNAL size, which no longer matched the on-screen
      // canvas -> the crosshair/tooltip never appeared and mouse interaction was
      // dead. `autoSize` engages the bundle's ResizeObserver to keep the chart's
      // internal dimensions matched to the container.
      autoSize: true,
    });

    // Belt-and-suspenders (2026-07-11b6): explicitly size the chart to its
    // container immediately after creation, in case the container's layout
    // height settles a frame after createChart (flex/min-height). autoSize's
    // ResizeObserver then keeps it in sync on every later resize. Without a
    // correct initial size, the very first crosshair hit-test can be dead.
    function syncChartSize() {
      const w = canvasHost.clientWidth;
      const h = canvasHost.clientHeight;
      if (w > 0 && h > 0) {
        try { chart.resize(w, h); } catch (e) { /* noop */ }
      }
    }
    syncChartSize();
    requestAnimationFrame(syncChartSize);

    const candleSeries = chart.addCandlestickSeries({
      upColor: LONG_COLOR,
      downColor: SHORT_COLOR,
      borderUpColor: LONG_COLOR,
      borderDownColor: SHORT_COLOR,
      wickUpColor: LONG_COLOR,
      wickDownColor: SHORT_COLOR,
    });
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
      color: LONG_COLOR,
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

    // Entry/exit marker series (lightweight-charts v4 setMarkers on a series).
    const markerSeries = candleSeries;
    let allTrades = []; // {trade, colorHex, dim}
    let selectedTradeId = null;    // last trade object passed to selectTrade()
    let selectedSignalId = null;   // Wave-2b: selection is by SIGNAL, not ficha
    let hoveredSignalId = null;    // transient hover halo (crosshair-driven), distinct from selection
    let slTpLines = []; // price-line handles, cleared unless a trade is selected

    // Connector lines: entry->exit segments, ONE 2-point line series PER
    // FICHA (Wave-2b gap/wavy-line fix). The old design merged every trade
    // into a single ascending-time series with whitespace breaks; because
    // all 3 fichas of a signal SHARE the same entry time, that forced a
    // fake "clamp to last+1" time for repeated entries -> a zigzag line.
    // Per-ficha series sidestep that entirely (each series has its own
    // independent 2-point time axis) and naturally support V1's
    // multi-day-hold fichas (F2/F3 exit days after F1 -- still just 2
    // points). GUARD (see redrawConnectors): only draw the dim layer when
    // allTrades.length <= 300, to protect huge runs from a series-per-ficha
    // explosion; V1 imports are small (~69 trades / ~23 signals).
    let connectorSeriesList = []; // array of series handles, cleared as a group

    // ---- Wave-2b signal grouping (V1: entry + 3 ficha exits share signal_id) ----
    // Derives the SIGNAL model from allTrades on demand -- no hardcoded run
    // or signal ids anywhere (req 8), works for any future V1 import.
    function groupBySignal() {
      const bySignal = new Map(); // signal_id -> {signal_id, side, ts_in, px_in, trades:[...], colorHex}
      allTrades.forEach(({ trade, colorHex }) => {
        const sid = trade.signal_id || trade.trade_id;
        let g = bySignal.get(sid);
        if (!g) {
          g = { signal_id: sid, side: trade.side, ts_in: trade.ts_in, px_in: trade.px_in, trades: [], colorHex };
          bySignal.set(sid, g);
        }
        g.trades.push(trade);
      });
      return bySignal;
    }

    function signalIdOf(trade) {
      return trade ? (trade.signal_id || trade.trade_id) : null;
    }

    const overlays = new Map(); // id -> series

    let bars = []; // current [[ts,o,h,l,c,v],...]
    let winFrom = null;
    let winTo = null;
    let fetchingPrev = false;
    let destroyed = false;

    // ---- barSource (Task A4 wiring): chunked/LRU data controller feeding
    // ensureRange() calls off the visible-range-change debounce below. This
    // is ADDITIVE wiring only -- existing loadInitial/setWindow/fetchPreviousBlock
    // paths (and the loadSeq token) are untouched.
    const barSource = (window.SENTINEL.chartData && window.SENTINEL.chartData.createBarSource)
      ? window.SENTINEL.chartData.createBarSource({ symbol, tf })
      : null;
    let rangeDebounceTimer = null;
    // Load-sequence token (Wave-3 race fix): the chart constructor kicks off
    // loadInitial() (the TAIL) while review.js immediately calls
    // selectTrade()->setWindow() (the selected trade's window). Both fetch
    // /api/bars concurrently; whichever RESOLVES last used to win applyBars,
    // so a slow tail load would clobber the trade window -> markers land
    // off-screen (no glow, nothing to hover). Every loader captures the seq
    // at START and only applies its result if it is still the latest.
    let loadSeq = 0;

    // ---- playback (Task M2.6) ----
    const PLAYBACK_SPEEDS = [1, 5, 20, 60, "MAX"];
    let playbackCursor = null; // epoch seconds; null = not in playback (full view)
    let playbackTimerId = null;
    let playbackBars = null; // full bar set captured at playback start
    let playbackIdx = 0; // index into playbackBars of next bar to reveal
    let playbackSpeed = 1;
    let playbackPlaying = false;
    const TICK_MS = 200; // one timer tick every 200ms; speed scales bars-per-tick

    // ---- data loading ----
    function barsUrl(params) {
      const usp = new URLSearchParams();
      usp.set("symbol", symbol);
      usp.set("tf", tf);
      if (params.from !== undefined && params.from !== null) usp.set("from", params.from);
      if (params.to !== undefined && params.to !== null) usp.set("to", params.to);
      if (params.max_points) usp.set("max_points", params.max_points);
      return `/api/bars?${usp.toString()}`;
    }

    function showState(kind, message) {
      if (kind === null) {
        stateOverlay.hidden = true;
        stateOverlay.innerHTML = "";
        return;
      }
      stateOverlay.hidden = false;
      if (kind === "loading") {
        stateOverlay.innerHTML = '<div class="chart-skeleton">Cargando barras&hellip;</div>';
      } else if (kind === "error") {
        stateOverlay.innerHTML =
          `<div class="chart-error-box"><p>${message || "Error cargando barras."}</p>` +
          '<button type="button" class="chart-retry-btn">Reintentar</button></div>';
        const btn = stateOverlay.querySelector(".chart-retry-btn");
        if (btn) btn.addEventListener("click", () => loadInitial());
      } else if (kind === "empty") {
        stateOverlay.innerHTML = `<div class="chart-empty">Sin barras para ${symbol} ${tf}</div>`;
      }
    }

    async function fetchBars(params) {
      const resp = await fetch(barsUrl(params));
      if (!resp.ok) throw new Error(`GET /api/bars failed: ${resp.status}`);
      return resp.json();
    }

    function applyBars(newBars) {
      bars = newBars;
      // ROOT-CAUSE FIX (2026-07-11b4): applyBars is the single point where real
      // bars are committed, so clear the "loading" overlay HERE. Previously a
      // load superseded by the loadSeq guard returned early WITHOUT calling
      // showState(null); if such a superseded loader was the last to resolve,
      // the semi-opaque .chart-state-overlay (inset:0; z-index:10) stayed up as
      // an "invisible layer" over the canvas -- swallowing every pointer event
      // and hiding the crosshair (exactly the reported symptom). Clearing on
      // successful commit guarantees the overlay is down whenever candles exist.
      showState(null);
      candleSeries.setData(bars.map(barToCandle));
      volumeSeries.setData(bars.map((b) => barToVolume(b, b[4] >= b[1])));
      if (bars.length) {
        winFrom = bars[0][0];
        winTo = bars[bars.length - 1][0];
      }
      recomputeOverlays();
      // ROOT-CAUSE FIX (2026-07-11b4): markers/connectors set BEFORE bars land
      // (selectTrade calls buildMarkers/redrawConnectors, THEN setWindow ->
      // applyBars) were computed against an empty bar set (barsLoaded=0) and
      // never rebuilt, so the selection glow + entry/exit markers rendered
      // against no candles (invisible). Rebuild them here whenever new bars are
      // committed, so markers always anchor to the freshly-loaded window and
      // the selected signal's glow appears. Guarded on allTrades to avoid work
      // on the plain CHARTS view (no trades loaded there).
      if (allTrades.length) {
        buildMarkers();
        redrawConnectors();
      }
    }

    async function loadInitial() {
      const mySeq = ++loadSeq;
      showState("loading");
      try {
        const body = await fetchBars({ max_points: 3000 });
        if (destroyed || mySeq !== loadSeq) return; // superseded by a newer load
        if (!body.bars || !body.bars.length) {
          showState("empty");
          bars = [];
          candleSeries.setData([]);
          volumeSeries.setData([]);
          return;
        }
        showState(null);
        applyBars(body.bars);
      } catch (e) {
        if (destroyed) return;
        showState("error", "Error cargando barras.");
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/bars", { type: "error" });
      }
    }

    async function fetchPreviousBlock() {
      if (fetchingPrev || bars.length === 0) return;
      fetchingPrev = true;
      const mySeq = loadSeq; // prepend is valid only for the current window
      try {
        const oldestTs = bars[0][0];
        // Send ISO (matches setWindow); a bare epoch used to 400 the endpoint.
        const body = await fetchBars({ to: new Date((tsSec(oldestTs) - 1) * 1000).toISOString(), max_points: 1500 });
        if (destroyed || mySeq !== loadSeq) return; // window changed under us
        if (body.bars && body.bars.length) {
          // merge: dedupe by ts, prepend
          const seen = new Set(bars.map((b) => b[0]));
          const merged = body.bars.filter((b) => !seen.has(b[0])).concat(bars);
          merged.sort((a, b) => a[0] - b[0]);
          bars = merged;
          candleSeries.setData(bars.map(barToCandle));
          volumeSeries.setData(bars.map((b) => barToVolume(b, b[4] >= b[1])));
          winFrom = bars[0][0];
          recomputeOverlays();
        }
      } catch (e) {
        // pan-fetch failure is non-fatal; leave existing data as-is.
      } finally {
        fetchingPrev = false;
      }
    }

    // pan-left near edge -> fetch previous block and merge (D.7 CHARTS).
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (!range || destroyed) return;
      if (range.from !== null && range.from < 5) {
        fetchPreviousBlock();
      }
      // Task A4 wiring: debounce 150ms -> ensureRange(view.from - 300*tf,
      // view.to + 50*tf) via the chunked barSource controller. Independent
      // of fetchPreviousBlock/loadSeq above -- purely additive prefetch.
      if (barSource) {
        if (rangeDebounceTimer !== null) clearTimeout(rangeDebounceTimer);
        rangeDebounceTimer = setTimeout(() => {
          rangeDebounceTimer = null;
          if (destroyed) return;
          const visible = chart.timeScale().getVisibleRange();
          if (!visible) return;
          const barSec = secPerBar();
          barSource.ensureRange(visible.from - 300 * barSec, visible.to + 50 * barSec);
        }, 150);
      }
    });

    // Wave-2b req 5: human-readable duration (ts_out - ts_in), e.g. "10m",
    // "1h 5m", "4h 55m". lightweight-charts markers have no native hover, so
    // signal hover is detected by matching param.time to a signal's
    // entry/exit bar time (see findSignalAtBarTime below).
    function humanizeDuration(seconds) {
      if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "--";
      let s = Math.max(0, Math.round(seconds));
      const days = Math.floor(s / 86400); s -= days * 86400;
      const hours = Math.floor(s / 3600); s -= hours * 3600;
      const mins = Math.floor(s / 60);
      const parts = [];
      if (days) parts.push(`${days}d`);
      if (hours) parts.push(`${hours}h`);
      if (mins || !parts.length) parts.push(`${mins}m`);
      return parts.slice(0, 2).join(" ");
    }

    // Finds the SIGNAL (group) whose entry bar OR any ficha's exit bar falls
    // on the given lightweight-charts bar time (epoch seconds already
    // rounded via tsSec). Returns null if the bar time isn't a signal
    // entry/exit for any currently-loaded trade.
    function findSignalAtBarTime(barTime) {
      const bySignal = groupBySignal();
      let found = null;
      bySignal.forEach((group) => {
        if (found) return;
        if (barTimeOf(epochOf(group.ts_in)) === barTime) { found = group; return; }
        group.trades.forEach((t) => {
          if (t.ts_out && barTimeOf(epochOf(t.ts_out)) === barTime) found = group;
        });
      });
      return found;
    }

    // Finds the SIGNAL whose CONNECTOR SPAN (entry->any ficha exit) passes
    // near the given bar time + crosshair price. Unlike findSignalAtBarTime
    // (exact entry/exit bar match), this covers hover ANYWHERE along a
    // connector line, not just its endpoints. For each ficha segment whose
    // bar-time range [tInBar, tOutBar] contains barTime, linearly interpolate
    // the connector's price at barTime and compare to the crosshair price;
    // pick the candidate with the smallest price distance (disambiguates
    // overlapping signals). Tolerance is scaled to the visible price range so
    // it feels consistent across symbols/zoom levels.
    function findSignalNearConnector(barTime, price) {
      if (price === null || price === undefined) return null;
      const bySignal = groupBySignal();
      const priceRange = visiblePriceRange();
      const tol = priceRange ? priceRange * 0.02 : Math.abs(price) * 0.001 || 0.5;
      let best = null;
      let bestDist = Infinity;
      bySignal.forEach((group) => {
        const tInBar = barTimeOf(epochOf(group.ts_in));
        group.trades.forEach((trade) => {
          if (!trade.ts_out) return;
          let tOutBar = barTimeOf(epochOf(trade.ts_out));
          if (tOutBar <= tInBar) tOutBar = tInBar + secPerBar();
          if (barTime < tInBar || barTime > tOutBar) return;
          const frac = tOutBar === tInBar ? 0 : (barTime - tInBar) / (tOutBar - tInBar);
          const interpPrice = group.px_in + (trade.px_out - group.px_in) * frac;
          const dist = Math.abs(interpPrice - price);
          if (dist <= tol && dist < bestDist) {
            bestDist = dist;
            best = group;
          }
        });
      });
      return best;
    }

    // Approximate visible price range (top-bottom of the right price scale)
    // for scaling the connector-hover tolerance. Falls back to null if the
    // chart can't report coordinates yet (e.g. before first paint).
    function visiblePriceRange() {
      try {
        const height = canvasHost.clientHeight || 0;
        if (!height) return null;
        const top = candleSeries.coordinateToPrice(0);
        const bottom = candleSeries.coordinateToPrice(height);
        if (top === null || bottom === null) return null;
        return Math.abs(bottom - top);
      } catch (e) {
        return null;
      }
    }

    function signalTooltipHtml(group) {
      const fmt = window.SENTINEL.fmt;
      const tsIn = epochOf(group.ts_in);
      let html = `<div class="chart-tooltip-row chart-tooltip-signal-header mono">${escapeHtmlLite(group.side || "")} entry ${fmt.price(group.px_in, 2)} @ ${fmt.ts(tsIn)}</div>`;
      let total = 0;
      const sorted = group.trades.slice().sort((a, b) => (a.ficha || "").localeCompare(b.ficha || ""));
      sorted.forEach((t) => {
        const pnl = Number(t.pnl) || 0;
        total += pnl;
        const dur = t.ts_out ? humanizeDuration(epochOf(t.ts_out) - tsIn) : "--";
        const pnlClass = pnl > 0 ? "chart-tooltip-pos" : pnl < 0 ? "chart-tooltip-neg" : "";
        html += `<div class="chart-tooltip-row mono">${escapeHtmlLite(t.ficha || "?")} ${escapeHtmlLite(t.exit_reason || "--")} `
          + `${fmt.price(t.px_in, 2)}&rarr;${fmt.price(t.px_out, 2)} `
          + `<span class="${pnlClass}">${fmt.signed(pnl)}</span> ${dur}</div>`;
      });
      html += `<div class="chart-tooltip-row chart-tooltip-signal-total mono">total <span class="${total > 0 ? "chart-tooltip-pos" : total < 0 ? "chart-tooltip-neg" : ""}">${fmt.signed(total)}</span></div>`;
      return html;
    }

    function escapeHtmlLite(s) {
      return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
      }[c]));
    }

    // Updates the transient hover-halo target and rebuilds markers/connectors
    // ONLY when the hovered signal actually changes (mousemove fires every
    // frame; rebuilding on every tick would be wasteful and can cause
    // flicker). Distinct from selectedSignalId (click-driven, persistent) --
    // both can be active at once; buildMarkers/redrawConnectors give the
    // hover halo precedence so it reads clearly even over a selected signal.
    function setHoveredSignal(signalId) {
      if (signalId === hoveredSignalId) return;
      hoveredSignalId = signalId;
      buildMarkers();
      redrawConnectors();
    }

    // ---- crosshair hover tooltip (ts, OHLC, vol, overlay values; or, when
    // hovering a signal's entry/exit bar, a per-ficha P&L mini-table) ----
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !param.point) {
        tooltip.hidden = true;
        setHoveredSignal(null);
        return;
      }
      const bar = bars.find((b) => tsSec(b[0]) === param.time);
      if (!bar) {
        tooltip.hidden = true;
        setHoveredSignal(null);
        return;
      }
      const fmt = window.SENTINEL.fmt;
      let html;
      // Hover-halo detection (whole-group highlight): first try an exact
      // entry/exit bar match (findSignalAtBarTime), then fall back to a
      // connector-span match (hovering anywhere along the entry->exit line),
      // using the crosshair's price coordinate to disambiguate overlaps.
      let signalGroup = allTrades.length ? findSignalAtBarTime(param.time) : null;
      if (!signalGroup && allTrades.length) {
        const crosshairPrice = candleSeries.coordinateToPrice(param.point.y);
        signalGroup = findSignalNearConnector(param.time, crosshairPrice);
      }
      setHoveredSignal(signalGroup ? signalGroup.signal_id : null);
      if (signalGroup) {
        html = signalTooltipHtml(signalGroup);
      } else {
        const [ts, o, h, l, c, v] = bar;
        html = `<div class="chart-tooltip-row"><span class="chart-tooltip-ts mono">${fmt.ts(ts)}</span></div>` +
          `<div class="chart-tooltip-row mono">O ${fmt.price(o, 2)} H ${fmt.price(h, 2)} L ${fmt.price(l, 2)} C ${fmt.price(c, 2)}</div>` +
          `<div class="chart-tooltip-row mono">vol ${fmt.num(v, 0)}</div>`;
        overlays.forEach((series, id) => {
          const val = param.seriesData ? param.seriesData.get(series) : null;
          if (val && val.value !== undefined) {
            html += `<div class="chart-tooltip-row mono">${id}: ${fmt.price(val.value, 2)}</div>`;
          }
        });
      }
      tooltip.innerHTML = html;
      tooltip.hidden = false;
      const box = el.getBoundingClientRect();
      const x = Math.min(param.point.x + 12, box.width - 220);
      const y = Math.max(param.point.y - 12, 4);
      tooltip.style.left = `${Math.max(4, x)}px`;
      tooltip.style.top = `${y}px`;
    });

    // ---- overlays (EMA9/21/50, BB, etc.) ----
    function computeEMA(values, period) {
      const k = 2 / (period + 1);
      let ema = null;
      const out = [];
      for (const v of values) {
        ema = ema === null ? v : v * k + ema * (1 - k);
        out.push(ema);
      }
      return out;
    }

    const overlaySpecs = new Map(); // id -> {kind, points|params}

    function recomputeOverlays() {
      overlaySpecs.forEach((spec, id) => {
        if (!spec.points) return;
        if (spec.dots) {
          setSarDotsSeries(id, spec.points, spec.color);
        } else {
          setOverlaySeries(id, spec.points, spec.color);
        }
      });
    }

    function setOverlaySeries(id, points, color) {
      let series = overlays.get(id);
      if (!series) {
        series = chart.addLineSeries({
          color: color || "#00bfff",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        overlays.set(id, series);
      }
      // Defect A fix: EMA/SuperTrend warmup bars carry `null` values.
      // lightweight-charts line series reject `{time, value: null}` --
      // `setData` throws and the WHOLE series never renders. Warmup gaps
      // must instead be WHITESPACE points (`{time}`, no `value` key).
      series.setData(points.map(([ts, val]) =>
        (val === null || val === undefined) ? { time: tsSec(ts) } : { time: tsSec(ts), value: val }));
    }

    function addOverlay(id, points, colorHex) {
      overlaySpecs.set(id, { points, color: colorHex });
      setOverlaySeries(id, points, colorHex);
    }

    function removeOverlay(id) {
      const series = overlays.get(id);
      if (series) {
        chart.removeSeries(series);
        overlays.delete(id);
      }
      overlaySpecs.delete(id);
    }

    // SAR is per-bar DOTS, not a continuous line (a line series would draw a
    // misleading zig-zag as trend flips). Rendered as a lightweight-charts
    // line series with lineWidth 0 + circle crosshair-style markers via
    // pointMarkersVisible, so each bar's SAR value shows as an isolated dot.
    // Registered in the SAME `overlays`/`overlaySpecs` maps as addOverlay so
    // removeOverlay/teardown work uniformly across line and dot overlays.
    function setSarDotsSeries(id, points, color) {
      let series = overlays.get(id);
      if (!series) {
        series = chart.addLineSeries({
          color: color || "#ffb020",
          lineWidth: 0,
          lineVisible: false,
          pointMarkersVisible: true,
          pointMarkersRadius: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        overlays.set(id, series);
      }
      series.setData(
        points
          .filter(([, val]) => val !== null && val !== undefined)
          .map(([ts, val]) => ({ time: tsSec(ts), value: val }))
      );
    }

    function addSarDots(id, points, colorHex) {
      overlaySpecs.set(id, { points, color: colorHex, dots: true });
      setSarDotsSeries(id, points, colorHex);
    }

    // ---- trade markers (D.4 NORMATIVE) ----
    function tradeMarkerColor(colorHex) {
      return colorHex || "#00bfff";
    }

    function buildMarkers() {
      const markers = [];
      const cursor = playbackCursor; // null when not in playback -> show everything
      const bySignal = groupBySignal();
      // Wave-2b req 1: ONE entry marker per SIGNAL (dedupe -- the 3 fichas
      // share ts_in/px_in/side), THREE exit markers per signal (one per
      // ficha, distinct "square" shape from the arrowUp/arrowDown entries).
      bySignal.forEach((group) => {
        const isSelected = selectedSignalId && group.signal_id === selectedSignalId;
        const isHovered = hoveredSignalId && group.signal_id === hoveredSignalId;
        // Wave-2b highlight fix: when a signal IS selected, everything else
        // must visibly dim (rgba fade + smaller size); when nothing is
        // selected, everyone gets full color/size (unchanged look).
        const dimOthers = !!selectedSignalId && !isHovered;
        const colorHex = group.colorHex;
        const baseColor = tradeMarkerColor(colorHex);
        // Hover halo takes visual precedence over selection dim/bright so the
        // hovered group reads clearly even when a DIFFERENT signal is
        // selected (or when this same signal is both selected and hovered).
        const color = isHovered ? HOVER_HALO_COLOR : (isSelected ? baseColor : (dimOthers ? hexToRgba(colorHex, 0.30) : baseColor));
        const long = (group.side || "").toUpperCase() === "LONG";
        const tIn = barTimeOf(epochOf(group.ts_in));
        if (cursor !== null && tIn > cursor) return; // not revealed yet
        markers.push({
          time: tIn,
          position: long ? "belowBar" : "aboveBar",
          color,
          shape: long ? "arrowUp" : "arrowDown",
          size: isHovered ? 2.4 : (isSelected ? 2 : 1),
          text: "",
        });
        group.trades.forEach((trade) => {
          if (!trade.ts_out) return;
          const tOut = barTimeOf(epochOf(trade.ts_out));
          if (cursor !== null && tOut > cursor) return;
          markers.push({
            time: tOut,
            position: "inBar",
            color,
            shape: "square",
            size: isHovered ? 2 : (isSelected ? 1.6 : 1),
            text: "",
          });
        });
      });
      markers.sort((a, b) => a.time - b.time);
      markerSeries.setMarkers(markers);
    }

    function epochOf(v) {
      if (typeof v === "number") return v > 1e12 ? v / 1000 : v;
      const d = new Date(v);
      return d.getTime() / 1000;
    }

    function clearConnectors() {
      connectorSeriesList.forEach((series) => {
        try { chart.removeSeries(series); } catch (e) { /* noop */ }
      });
      connectorSeriesList = [];
    }

    // Draws ONE 2-point line series for a single ficha's entry->exit,
    // bar-snapped (Wave-2b gap fix). If entry and exit snap to the SAME bar
    // (e.g. a sub-bar-duration ficha), bump the exit time forward by one
    // real bar (secPerBar()), NOT +1s -- a synthetic +1s time isn't a real
    // bar and would reintroduce a phantom column.
    function drawFichaConnector(tIn, pIn, tOut, pOut, colorHex, bright, hovered) {
      let tInBar = barTimeOf(tIn);
      let tOutBar = barTimeOf(tOut);
      if (tOutBar <= tInBar) tOutBar = tInBar + secPerBar();
      const points = [
        { time: tInBar, value: pIn },
        { time: tOutBar, value: pOut },
      ];
      // Hover halo approximation: lightweight-charts markers/lines are
      // canvas-drawn (no CSS box-shadow), so the "soft glow" is faked with a
      // wide, low-opacity underlay line in the halo color PLUS a slim bright
      // core line on top -- the wide layer reads as a tenuous halo around the
      // thin connector without a real blur filter.
      if (hovered) {
        const glow = chart.addLineSeries({
          color: hexToRgba(HOVER_HALO_COLOR, 0.22),
          lineWidth: 6,
          lineStyle: LightweightCharts.LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        glow.setData(points);
        connectorSeriesList.push(glow);
      }
      const series = chart.addLineSeries({
        color: hovered ? HOVER_HALO_COLOR : (bright ? hexToRgba(colorHex, 0.95) : hexToRgba(colorHex, 0.22)),
        lineWidth: hovered ? 2.5 : (bright ? 2 : 1),
        lineStyle: (bright || hovered) ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      series.setData(points);
      connectorSeriesList.push(series);
      return series;
    }

    function hexToRgba(hex, alpha) {
      const h = (hex || "#00bfff").replace("#", "");
      const bigint = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
      const r = (bigint >> 16) & 255, g = (bigint >> 8) & 255, b = bigint & 255;
      return `rgba(${r},${g},${b},${alpha})`;
    }

    // Draws every ficha's entry->exit connector as its own 2-point series:
    // non-selected signals dim+dashed (skipped entirely above the 300-trade
    // GUARD to protect huge runs), the selected signal's fichas bright+solid
    // and drawn LAST so they sit on top of the dim layer.
    function redrawConnectors() {
      clearConnectors();
      if (!allTrades.length) return;
      const cursor = playbackCursor;
      const bySignal = groupBySignal();
      const withinCursor = (tOut) => cursor === null || epochOf(tOut) <= cursor;
      const drawSignalDim = allTrades.length <= 300;

      if (drawSignalDim) {
        bySignal.forEach((group) => {
          if (selectedSignalId && group.signal_id === selectedSignalId) return; // drawn bright below
          if (hoveredSignalId && group.signal_id === hoveredSignalId) return; // drawn as halo below
          const tIn = epochOf(group.ts_in);
          group.trades.forEach((trade) => {
            if (!trade.ts_out || !withinCursor(trade.ts_out)) return;
            drawFichaConnector(tIn, trade.px_in, epochOf(trade.ts_out), trade.px_out, group.colorHex, false);
          });
        });
      }

      if (selectedSignalId && selectedSignalId !== hoveredSignalId) {
        const group = bySignal.get(selectedSignalId);
        if (group) {
          const tIn = epochOf(group.ts_in);
          group.trades.forEach((trade) => {
            if (!trade.ts_out || !withinCursor(trade.ts_out)) return;
            drawFichaConnector(tIn, trade.px_in, epochOf(trade.ts_out), trade.px_out, group.colorHex, true);
          });
        }
      }

      // Hovered signal drawn LAST (on top of everything, including a
      // different selected signal) with the electric-blue halo treatment.
      if (hoveredSignalId) {
        const group = bySignal.get(hoveredSignalId);
        if (group) {
          const tIn = epochOf(group.ts_in);
          group.trades.forEach((trade) => {
            if (!trade.ts_out || !withinCursor(trade.ts_out)) return;
            drawFichaConnector(tIn, trade.px_in, epochOf(trade.ts_out), trade.px_out, group.colorHex, true, true);
          });
        }
      }
    }

    function addTradeMarkers(trades, colorHex, options) {
      options = options || {};
      const dim = !!options.dim;
      (trades || []).forEach((trade) => {
        allTrades.push({ trade, colorHex, dim });
      });
      buildMarkers();
      redrawConnectors();
    }

    function clearSlTpLines() {
      slTpLines.forEach(({ series, line }) => {
        try { series.removePriceLine(line); } catch (e) { /* noop */ }
      });
      slTpLines = [];
    }

    // Signal selected (Wave-2b req 3, generalizes D.4 single-trade select):
    // selecting ANY ficha of a signal selects the WHOLE SIGNAL -- its entry
    // + 3 exits + 3 connectors go bright, everything else dims. Recenters
    // the window to show the entry AND all 3 ficha exits:
    // from = min(ts_in) - pad, to = max(ts_out over the 3 fichas) + pad.
    // SL/TP dotted lines kept per selected signal if present on any ficha.
    function selectTrade(trade) {
      clearSlTpLines();
      if (!trade) {
        selectedTradeId = null;
        selectedSignalId = null;
        buildMarkers();
        redrawConnectors();
        return;
      }
      selectedTradeId = trade.trade_id;
      selectedSignalId = signalIdOf(trade);
      const bySignal = groupBySignal();
      const group = bySignal.get(selectedSignalId) || { trades: [trade], ts_in: trade.ts_in };
      const fichas = group.trades;

      buildMarkers();
      // rebuild connectors with the new selection's alpha
      redrawConnectors();

      fichas.forEach((t) => {
        if (t.sl) {
          const line = candleSeries.createPriceLine({
            price: t.sl, color: "rgba(239,83,80,.4)", lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted, title: "SL",
          });
          slTpLines.push({ series: candleSeries, line });
        }
        if (t.tp) {
          const line = candleSeries.createPriceLine({
            price: t.tp, color: "rgba(38,166,154,.4)", lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted, title: "TP",
          });
          slTpLines.push({ series: candleSeries, line });
        }
      });

      // recenter so entry + ALL 3 ficha exits sit in view with symmetric
      // context: pad = max(40 bars, 1.5x the signal's total duration).
      const barSec = secPerBar();
      const tsIn = epochOf(group.ts_in || trade.ts_in);
      let tsOutMax = tsIn;
      fichas.forEach((t) => {
        if (t.ts_out) tsOutMax = Math.max(tsOutMax, epochOf(t.ts_out));
      });
      const dur = Math.max(tsOutMax - tsIn, barSec);
      const pad = Math.max(40 * barSec, dur * 1.5);
      const from = tsIn - pad;
      const to = tsOutMax + pad;
      // Defect B (frontend half, Wave-2 plan 2026-07-10): return the
      // setWindow promise so callers (review.js) can await window-settle
      // before requesting indicator overlays for the NEW window -- without
      // this, a caller's `selectTrade(t); refreshIndicators();` fired the
      // indicators fetch against the STALE (pre-selection) window.
      return setWindow(from, to);
    }

    // ---- window / TF ----
    async function setWindow(from, to) {
      const mySeq = ++loadSeq;
      showState("loading");
      try {
        const body = await fetchBars({ from: new Date(from * 1000).toISOString(), to: new Date(to * 1000).toISOString(), max_points: 3000 });
        if (destroyed || mySeq !== loadSeq) return; // superseded by a newer load
        if (!body.bars || !body.bars.length) {
          showState("empty");
          return;
        }
        showState(null);
        applyBars(body.bars);
        chart.timeScale().setVisibleRange({ from: tsSec(from), to: tsSec(to) });
      } catch (e) {
        if (destroyed) return;
        showState("error", "Error cargando barras.");
      }
    }

    async function setTF(newTf) {
      if (!TF_LIST.includes(newTf)) return;
      pausePlayback();
      playbackBars = null;
      playbackIdx = 0;
      playbackCursor = null;
      tf = newTf;
      if (barSource) barSource.setTf(newTf);
      await loadInitial();
      // Task 2.1 (Wave-3 Stage 2): loadInitial() only fetches the TAIL of
      // the new tf, which may be months away from the currently-selected
      // trade -- markers/connectors would stay built against the OLD tf's
      // bar times. If a trade is selected, re-run the selection path so the
      // chart reloads THAT trade's window on the new tf and rebuilds
      // markers/connectors against the new bar boundaries (selectTrade ->
      // setWindow -> applyBars -> buildMarkers/redrawConnectors already
      // wired below via selectTrade itself).
      if (selectedTradeId) {
        const bySignal = groupBySignal();
        const group = selectedSignalId ? bySignal.get(selectedSignalId) : null;
        const trade = group ? group.trades.find((t) => t.trade_id === selectedTradeId) || group.trades[0] : null;
        if (trade) {
          await selectTrade(trade);
          return;
        }
      }
      buildMarkers();
      redrawConnectors();
    }

    // ---- live ticks (WS /ws/ticks) ----
    let ws = null;
    let tickSymbol = null;

    function enableTicks(sym) {
      stopPlayback(); // mutually exclusive with playback
      disableTicks();
      tickSymbol = sym || symbol;
      ws = new WebSocket(wsUrl());
      ws.onopen = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ sub: `ticks:${tickSymbol}` }));
        }
      };
      ws.onmessage = (evt) => {
        let msg;
        try { msg = JSON.parse(evt.data); } catch (e) { return; }
        if (msg.ch !== `ticks:${tickSymbol}`) return;
        updateFormingCandle(msg);
      };
      ws.onclose = () => { ws = null; };
      ws.onerror = () => { if (ws) ws.close(); };
    }

    function disableTicks() {
      if (ws) {
        try { ws.send(JSON.stringify({ unsub: `ticks:${tickSymbol}` })); } catch (e) { /* noop */ }
        ws.close();
        ws = null;
      }
    }

    function updateFormingCandle(msg) {
      if (!bars.length) return;
      const tfMinutes = { M1: 1, M2: 2, M5: 5, M10: 10, M15: 15 }[tf] || 1;
      const secPerBar = tfMinutes * 60;
      const bid = msg.bid;
      const tSec = Math.floor(msg.t / 1000);
      const bucketStart = Math.floor(tSec / secPerBar) * secPerBar;
      const last = bars[bars.length - 1];
      if (bucketStart > last[0]) {
        // new forming bar
        const newBar = [bucketStart, bid, bid, bid, bid, 0];
        bars.push(newBar);
        candleSeries.update(barToCandle(newBar));
        volumeSeries.update(barToVolume(newBar, true));
      } else if (bucketStart === last[0]) {
        last[2] = Math.max(last[2], bid); // high
        last[3] = Math.min(last[3], bid); // low
        last[4] = bid; // close = bid
        candleSeries.update(barToCandle(last));
        volumeSeries.update(barToVolume(last, last[4] >= last[1]));
      }
      // bucketStart < last[0]: stale tick, ignore.
    }

    // ---- playback engine (Task M2.6, plan §D.7/§D.4) ----
    // Reveals the already-fetched `bars` sequentially over ONE timer.
    // Speeds 1x/5x/20x/60x scale bars-per-tick; MAX reveals all remaining
    // bars on the next tick (fast-forward). Trade markers/connectors are
    // recomputed via buildMarkers()/redrawConnectors() against the cursor.
    function barsPerTick(speed) {
      if (speed === "MAX") return Infinity;
      const n = Number(speed) || 1;
      return Math.max(1, Math.round(n));
    }

    function clearPlaybackTimer() {
      if (playbackTimerId !== null) {
        clearInterval(playbackTimerId);
        playbackTimerId = null;
      }
    }

    function playbackTick() {
      if (!playbackBars || !playbackBars.length) {
        pausePlayback();
        return;
      }
      const step = barsPerTick(playbackSpeed);
      const nextIdx = step === Infinity ? playbackBars.length : Math.min(playbackBars.length, playbackIdx + step);
      revealTo(nextIdx);
      if (playbackIdx >= playbackBars.length) {
        pausePlayback(); // reached the end; stay paused at full reveal
      }
    }

    function revealTo(idx) {
      if (!playbackBars) return;
      playbackIdx = Math.max(0, Math.min(playbackBars.length, idx));
      const visible = playbackBars.slice(0, playbackIdx);
      bars = visible.slice();
      candleSeries.setData(visible.map(barToCandle));
      volumeSeries.setData(visible.map((b) => barToVolume(b, b[4] >= b[1])));
      recomputeOverlays();
      playbackCursor = visible.length ? visible[visible.length - 1][0] : (playbackBars[0] ? playbackBars[0][0] : null);
      buildMarkers();
      redrawConnectors();
    }

    function startPlayback(options) {
      options = options || {};
      disableTicks(); // mutually exclusive with live-ticks
      const speed = options.speed !== undefined ? options.speed : playbackSpeed;
      playbackSpeed = PLAYBACK_SPEEDS.includes(speed) ? speed : 1;
      if (!playbackBars) {
        playbackBars = bars.slice(); // snapshot of already-fetched bars
        playbackIdx = 0;
      }
      clearPlaybackTimer();
      playbackPlaying = true;
      playbackTimerId = setInterval(playbackTick, TICK_MS);
    }

    function pausePlayback() {
      playbackPlaying = false;
      clearPlaybackTimer();
    }

    function seekPlayback(ts) {
      if (!playbackBars) {
        playbackBars = bars.slice();
        playbackIdx = 0;
      }
      const target = tsSec(ts);
      let idx = 0;
      while (idx < playbackBars.length && playbackBars[idx][0] <= target) idx++;
      revealTo(idx);
    }

    function stopPlayback() {
      pausePlayback();
      const hadPlayback = playbackBars !== null;
      const fullBars = playbackBars;
      playbackBars = null;
      playbackIdx = 0;
      playbackCursor = null;
      if (hadPlayback && fullBars) {
        // restore full view: re-apply the full bar set + full markers.
        applyBars(fullBars);
        buildMarkers();
        redrawConnectors();
      }
    }

    function isPlaying() {
      return playbackPlaying;
    }

    // UI polling helper (playback bar in charts.js/review.js): current
    // cursor ts, progress pct within the snapshot, and playing flag.
    function getPlaybackState() {
      if (!playbackBars || !playbackBars.length) {
        return { active: false, playing: false, cursor: null, pct: 0, from: null, to: null };
      }
      const from = playbackBars[0][0];
      const to = playbackBars[playbackBars.length - 1][0];
      const pct = to > from ? Math.max(0, Math.min(1, ((playbackCursor || from) - from) / (to - from))) : 0;
      return { active: true, playing: playbackPlaying, cursor: playbackCursor, pct, from, to };
    }

    function destroy() {
      destroyed = true;
      if (rangeDebounceTimer !== null) {
        clearTimeout(rangeDebounceTimer);
        rangeDebounceTimer = null;
      }
      stopPlayback();
      disableTicks();
      try { chart.remove(); } catch (e) { /* noop */ }
      el.innerHTML = "";
    }

    // initial load
    loadInitial();

    return {
      setWindow,
      setTF,
      addTradeMarkers,
      selectTrade,
      enableTicks,
      disableTicks,
      addOverlay,
      addSarDots,
      removeOverlay,
      startPlayback,
      pausePlayback,
      seekPlayback,
      stopPlayback,
      isPlaying,
      getPlaybackState,
      PLAYBACK_SPEEDS,
      destroy,
      get symbol() { return symbol; },
      get tf() { return tf; },
      set symbol(v) { symbol = v; loadInitial(); },
      // ROOT-CAUSE FIX (2026-07-11b4): set the symbol WITHOUT kicking off a
      // TAIL loadInitial(). REVIEW opens a run then immediately calls
      // selectTradeAt(0) -> selectTrade -> setWindow (the trade's window). The
      // `set symbol` setter's loadInitial() raced that setWindow through the
      // shared loadSeq token: whichever resolved last won, and on repeat opens
      // a stale TAIL load could supersede the trade window -> chart committed 0
      // relevant bars (barsLoaded=0). REVIEW must set the symbol quietly and
      // let selectTrade own the single load.
      setSymbolNoLoad(v) { symbol = v; },
      // Defect B (frontend half): current candle window in epoch seconds,
      // so callers (review.js refreshIndicators) can request overlays
      // bounded to the SAME range as the loaded candles (overlay range must
      // be a subset of candle range, never wider).
      get windowFrom() { return winFrom === null ? null : tsSec(winFrom); },
      get windowTo() { return winTo === null ? null : tsSec(winTo); },
      _chart: chart, // escape hatch for advanced callers (tests/debug only)
      _candleSeries: candleSeries, // escape hatch (tests/debug only)
      get _hoveredSignalId() { return hoveredSignalId; }, // escape hatch (tests/debug only)
    };
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.chart = { create, TF_LIST };
})();
