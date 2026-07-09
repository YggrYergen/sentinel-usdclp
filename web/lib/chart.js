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
//   inst.removeOverlay(id)
//   inst.destroy()
//
// Candle colors = long/short design tokens (D.2): --long #26a69a / --short #ef5350.
(function () {
  "use strict";

  const LONG_COLOR = "#26a69a";
  const SHORT_COLOR = "#ef5350";

  const TF_LIST = ["M1", "M2", "M5", "M10", "M15"];

  function tsSec(t) {
    // lightweight-charts wants seconds (UTCTimestamp) for time-based series.
    return Math.floor(Number(t));
  }

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
      rightPriceScale: { borderColor: "rgba(0,191,255,.18)" },
      timeScale: { borderColor: "rgba(0,191,255,.18)", timeVisible: true, secondsVisible: false },
      autoResize: true,
    });

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
    let selectedTradeId = null;
    let slTpLines = []; // price-line handles, cleared unless a trade is selected

    // Connector lines: one line-series per trade connecting entry->exit points.
    const connectorSeries = new Map(); // trade_id -> series

    const overlays = new Map(); // id -> series

    let bars = []; // current [[ts,o,h,l,c,v],...]
    let winFrom = null;
    let winTo = null;
    let fetchingPrev = false;
    let destroyed = false;

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
      candleSeries.setData(bars.map(barToCandle));
      volumeSeries.setData(bars.map((b) => barToVolume(b, b[4] >= b[1])));
      if (bars.length) {
        winFrom = bars[0][0];
        winTo = bars[bars.length - 1][0];
      }
      recomputeOverlays();
    }

    async function loadInitial() {
      showState("loading");
      try {
        const body = await fetchBars({ max_points: 3000 });
        if (destroyed) return;
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
      try {
        const oldestTs = bars[0][0];
        const body = await fetchBars({ to: oldestTs - 1, max_points: 1500 });
        if (destroyed) return;
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
    });

    // ---- crosshair hover tooltip (ts, OHLC, vol, overlay values) ----
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !param.point) {
        tooltip.hidden = true;
        return;
      }
      const bar = bars.find((b) => tsSec(b[0]) === param.time);
      if (!bar) {
        tooltip.hidden = true;
        return;
      }
      const fmt = window.SENTINEL.fmt;
      const [ts, o, h, l, c, v] = bar;
      let html = `<div class="chart-tooltip-row"><span class="chart-tooltip-ts mono">${fmt.ts(ts)}</span></div>` +
        `<div class="chart-tooltip-row mono">O ${fmt.price(o, 2)} H ${fmt.price(h, 2)} L ${fmt.price(l, 2)} C ${fmt.price(c, 2)}</div>` +
        `<div class="chart-tooltip-row mono">vol ${fmt.num(v, 0)}</div>`;
      overlays.forEach((series, id) => {
        const val = param.seriesData ? param.seriesData.get(series) : null;
        if (val && val.value !== undefined) {
          html += `<div class="chart-tooltip-row mono">${id}: ${fmt.price(val.value, 2)}</div>`;
        }
      });
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
        if (spec.points) {
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
      series.setData(points.map(([ts, val]) => ({ time: tsSec(ts), value: val })));
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

    // ---- trade markers (D.4 NORMATIVE) ----
    function tradeMarkerColor(colorHex) {
      return colorHex || "#00bfff";
    }

    function buildMarkers() {
      const markers = [];
      allTrades.forEach(({ trade, colorHex, dim }) => {
        const isSelected = selectedTradeId && trade.trade_id === selectedTradeId;
        const alpha = isSelected ? 1 : dim ? 0.4 : 1;
        const color = tradeMarkerColor(colorHex);
        const size = isSelected ? 2 : 1; // lightweight-charts marker "size" is relative; scale via shape/size below
        const long = (trade.side || "").toUpperCase() === "LONG";
        markers.push({
          time: tsSec(new Date(trade.ts_in).getTime() / 1000 || trade.ts_in),
          position: long ? "belowBar" : "aboveBar",
          color,
          shape: long ? "arrowUp" : "arrowDown",
          size: isSelected ? 2 : 1,
          text: "",
        });
        if (trade.ts_out) {
          markers.push({
            time: tsSec(new Date(trade.ts_out).getTime() / 1000 || trade.ts_out),
            position: "inBar",
            color,
            shape: "square",
            size: isSelected ? 1.6 : 1,
            text: "",
          });
        }
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
      connectorSeries.forEach((series) => chart.removeSeries(series));
      connectorSeries.clear();
    }

    function drawConnector(trade, colorHex, alpha) {
      const tsIn = epochOf(trade.ts_in);
      const tsOut = trade.ts_out ? epochOf(trade.ts_out) : null;
      if (!tsOut) return;
      const series = chart.addLineSeries({
        color: hexToRgba(colorHex, alpha),
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      series.setData([
        { time: tsSec(tsIn), value: trade.px_in },
        { time: tsSec(tsOut), value: trade.px_out },
      ]);
      connectorSeries.set(trade.trade_id, series);
    }

    function hexToRgba(hex, alpha) {
      const h = (hex || "#00bfff").replace("#", "");
      const bigint = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
      const r = (bigint >> 16) & 255, g = (bigint >> 8) & 255, b = bigint & 255;
      return `rgba(${r},${g},${b},${alpha})`;
    }

    function addTradeMarkers(trades, colorHex, options) {
      options = options || {};
      const dim = !!options.dim;
      (trades || []).forEach((trade) => {
        allTrades.push({ trade, colorHex, dim });
      });
      buildMarkers();
      clearConnectors();
      allTrades.forEach(({ trade, colorHex: c, dim: d }) => {
        const isSelected = selectedTradeId && trade.trade_id === selectedTradeId;
        const alpha = isSelected ? 0.9 : d ? 0.25 : 0.6;
        drawConnector(trade, c, alpha);
      });
    }

    function clearSlTpLines() {
      slTpLines.forEach(({ series, line }) => {
        try { series.removePriceLine(line); } catch (e) { /* noop */ }
      });
      slTpLines = [];
    }

    // Trade selected (D.4): scale 1.4x + glow (approximated via marker size),
    // recenter [ts_in-100bars, ts_out+30bars] of active TF, SL/TP dotted lines
    // only while selected.
    function selectTrade(trade) {
      clearSlTpLines();
      if (!trade) {
        selectedTradeId = null;
        buildMarkers();
        return;
      }
      selectedTradeId = trade.trade_id;
      buildMarkers();
      // rebuild connectors with the new selection's alpha
      clearConnectors();
      allTrades.forEach(({ trade: t, colorHex: c, dim: d }) => {
        const isSelected = selectedTradeId && t.trade_id === selectedTradeId;
        const alpha = isSelected ? 0.9 : d ? 0.25 : 0.6;
        drawConnector(t, c, alpha);
      });

      if (trade.sl) {
        const line = candleSeries.createPriceLine({
          price: trade.sl, color: "rgba(239,83,80,.4)", lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dotted, title: "SL",
        });
        slTpLines.push({ series: candleSeries, line });
      }
      if (trade.tp) {
        const line = candleSeries.createPriceLine({
          price: trade.tp, color: "rgba(38,166,154,.4)", lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dotted, title: "TP",
        });
        slTpLines.push({ series: candleSeries, line });
      }

      // recenter: [ts_in - 100 bars, ts_out + 30 bars] of active TF
      const tfMinutes = { M1: 1, M2: 2, M5: 5, M10: 10, M15: 15 }[tf] || 1;
      const secPerBar = tfMinutes * 60;
      const tsIn = epochOf(trade.ts_in);
      const tsOut = trade.ts_out ? epochOf(trade.ts_out) : tsIn;
      const from = tsIn - 100 * secPerBar;
      const to = tsOut + 30 * secPerBar;
      setWindow(from, to);
    }

    // ---- window / TF ----
    async function setWindow(from, to) {
      showState("loading");
      try {
        const body = await fetchBars({ from: new Date(from * 1000).toISOString(), to: new Date(to * 1000).toISOString(), max_points: 3000 });
        if (destroyed) return;
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
      tf = newTf;
      await loadInitial();
    }

    // ---- live ticks (WS /ws/ticks) ----
    let ws = null;
    let tickSymbol = null;

    function enableTicks(sym) {
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

    function destroy() {
      destroyed = true;
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
      removeOverlay,
      destroy,
      get symbol() { return symbol; },
      get tf() { return tf; },
      set symbol(v) { symbol = v; loadInitial(); },
      _chart: chart, // escape hatch for advanced callers (tests/debug only)
    };
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.chart = { create, TF_LIST };
})();
