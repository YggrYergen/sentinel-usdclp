// SENTINEL sections/charts.js — CHARTS section (Task M1.3, plan §D.7 NORMATIVE).
// Toolbar: symbol select (USDCLP/NQ100/XAUUSD), exclusive TF buttons
// M1/M2/M5/M10/M15, live-ticks toggle, overlay multiselect (EMA9/21/50, BB v1).
// Chart = shared lib/chart.js module. Classic script (no ES modules), hangs
// off window.SENTINEL.sections.charts.
(function () {
  "use strict";

  const SYMBOLS = [
    { value: "USDCLP", label: "USD/CLP" },
    { value: "NQ100", label: "NQ100" },
    { value: "XAUUSD", label: "XAUUSD" },
  ];
  const TF_LIST = ["M1", "M2", "M5", "M10", "M15"];
  const OVERLAYS = ["EMA9", "EMA21", "EMA50", "BB"];
  const OVERLAY_COLORS = { EMA9: "#00bfff", EMA21: "#ffb020", EMA50: "#7c4dff", BB: "#4d9fff" };
  const PLAYBACK_SPEEDS = [1, 5, 20, 60, "MAX"];

  // ---- playback UI bar (Task M2.6, plan §D.7/§D.4) — shared pattern used
  // by both CHARTS (no trades) and REVIEW (with the run's trades). Renders
  // ▶/⏸ + speed selector 1x/5x/20x/60x/MAX + scrub slider + current-ts label.
  // Polls chartInst.getPlaybackState() on ONE interval to drive the ts
  // label + slider. ESC or leaving the section stops playback (caller wires
  // stopPlayback() + this.destroy() on teardown).
  function renderPlaybackBar(host, getChartInst) {
    const bar = el("div", { class: "playback-bar" });
    const playBtn = el("button", { type: "button", class: "playback-play-btn", text: "▶" });
    const speedSel = el("select", { class: "playback-speed-select" },
      PLAYBACK_SPEEDS.map((s) => el("option", { value: String(s), text: `${s}${s === "MAX" ? "" : "x"}` })));
    const slider = el("input", { type: "range", class: "playback-scrub", min: "0", max: "1000", value: "0" });
    const tsLabel = el("span", { class: "playback-ts-label mono", text: "--" });

    let scrubbing = false;

    playBtn.addEventListener("click", () => {
      const inst = getChartInst();
      if (!inst) return;
      const st = inst.getPlaybackState();
      if (st.active && st.playing) {
        inst.pausePlayback();
      } else {
        const speed = speedSel.value === "MAX" ? "MAX" : Number(speedSel.value);
        inst.startPlayback({ speed });
      }
    });

    speedSel.addEventListener("change", () => {
      const inst = getChartInst();
      if (!inst) return;
      const st = inst.getPlaybackState();
      const speed = speedSel.value === "MAX" ? "MAX" : Number(speedSel.value);
      if (st.active && st.playing) inst.startPlayback({ speed });
    });

    slider.addEventListener("input", () => { scrubbing = true; });
    slider.addEventListener("change", () => {
      const inst = getChartInst();
      scrubbing = false;
      if (!inst) return;
      const st = inst.getPlaybackState();
      if (!st.active || st.from === null) return;
      const pct = Number(slider.value) / 1000;
      inst.seekPlayback(st.from + pct * (st.to - st.from));
    });

    bar.appendChild(playBtn);
    bar.appendChild(speedSel);
    bar.appendChild(slider);
    bar.appendChild(tsLabel);
    host.appendChild(bar);

    const fmt = window.SENTINEL.fmt;
    const pollId = setInterval(() => {
      const inst = getChartInst();
      if (!inst) return;
      const st = inst.getPlaybackState();
      playBtn.textContent = st.active && st.playing ? "⏸" : "▶";
      tsLabel.textContent = st.cursor ? fmt.ts(st.cursor) : "--";
      if (!scrubbing) slider.value = String(Math.round((st.pct || 0) * 1000));
    }, 250);

    return {
      el: bar,
      destroy: () => clearInterval(pollId),
    };
  }

  let state = null;

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "text") e.textContent = v;
      else if (k === "html") e.innerHTML = v;
      else e.setAttribute(k, v);
    }
    for (const child of children || []) e.appendChild(child);
    return e;
  }

  function computeEMA(closes, period) {
    const k = 2 / (period + 1);
    let ema = null;
    return closes.map((c) => {
      ema = ema === null ? c : c * k + ema * (1 - k);
      return ema;
    });
  }

  function computeBBUpper(closes, period, mult) {
    const out = [];
    for (let i = 0; i < closes.length; i++) {
      if (i < period - 1) { out.push(null); continue; }
      const win = closes.slice(i - period + 1, i + 1);
      const mean = win.reduce((a, b) => a + b, 0) / period;
      const variance = win.reduce((a, b) => a + (b - mean) * (b - mean), 0) / period;
      out.push(mean + mult * Math.sqrt(variance));
    }
    return out;
  }

  // ---- Task 1b shared indicator calculators -------------------------------
  // Client-side reproductions of the strategy-chart indicators
  // (`/api/strategies/chart-specs`). Exported on window.SENTINEL.chartCalc so
  // positions.js (ESTRATEGIA per-strategy chart) reuses the SAME functions
  // instead of duplicating them; computeEMA/computeBBUpper above stay local
  // (charts.js's own overlay set) but are also exposed for reuse.

  function computeSMA(closes, period) {
    const out = new Array(closes.length).fill(null);
    if (period <= 0) return out;
    let run = 0;
    for (let i = 0; i < closes.length; i++) {
      run += closes[i];
      if (i >= period) run -= closes[i - period];
      if (i >= period - 1) out[i] = run / period;
    }
    return out;
  }

  // MT5-style momentum oscillator: close[i] / close[i-period] * 100 (matches
  // sentinel_engine/strategies/tk_momentum.py `momentum()`). Entries before
  // `period` (or where the reference close is 0) are null.
  function computeMomentum(closes, period) {
    const out = new Array(closes.length).fill(null);
    for (let i = period; i < closes.length; i++) {
      const ref = closes[i - period];
      out[i] = ref ? (closes[i] / ref) * 100 : null;
    }
    return out;
  }

  // Standard parabolic SAR (Wilder), a line-by-line port of
  // sentinel_engine/strategies/emasar.py::sar_series (STATIC case, fixed
  // step/max — read there for the exact reference). Returns {sar, trend}
  // arrays (trend: +1 bullish / -1 bearish), same shape as the Python
  // reference (sar[0] is never null: seeded from bar 0).
  function computeSAR(highs, lows, step, maxStep) {
    const n = highs.length;
    const sar = new Array(n).fill(null);
    const trend = new Array(n).fill(0);
    if (n === 0) return { sar, trend };
    let up = n < 2 ? true : highs[1] >= highs[0];
    let ep = up ? highs[0] : lows[0];
    let af = step;
    sar[0] = up ? lows[0] : highs[0];
    trend[0] = up ? 1 : -1;
    for (let i = 1; i < n; i++) {
      let cur = sar[i - 1] + af * (ep - sar[i - 1]);
      if (up) {
        const ceiling = i >= 2 ? Math.min(lows[i - 1], lows[i - 2]) : lows[i - 1];
        cur = Math.min(cur, ceiling);
        if (lows[i] < cur) {
          up = false;
          cur = ep;
          ep = lows[i];
          af = step;
        } else if (highs[i] > ep) {
          ep = highs[i];
          af = Math.min(af + step, maxStep);
        }
      } else {
        const floor = i >= 2 ? Math.max(highs[i - 1], highs[i - 2]) : highs[i - 1];
        cur = Math.max(cur, floor);
        if (highs[i] > cur) {
          up = true;
          cur = ep;
          ep = highs[i];
          af = step;
        } else if (lows[i] < ep) {
          ep = lows[i];
          af = Math.min(af + step, maxStep);
        }
      }
      sar[i] = cur;
      trend[i] = up ? 1 : -1;
    }
    return { sar, trend };
  }

  // Wilder ATR(period) -- warmup (first `period` bars) is null, matching the
  // engine's _atr_wilder semantics (first true value is the SMA of the first
  // `period` true ranges, then Wilder-smoothed).
  function computeAtrWilder(highs, lows, closes, period) {
    const n = highs.length;
    const out = new Array(n).fill(null);
    if (n === 0 || period <= 0) return out;
    const tr = new Array(n).fill(0);
    for (let i = 0; i < n; i++) {
      if (i === 0) { tr[i] = highs[i] - lows[i]; continue; }
      tr[i] = Math.max(
        highs[i] - lows[i],
        Math.abs(highs[i] - closes[i - 1]),
        Math.abs(lows[i] - closes[i - 1]),
      );
    }
    if (n < period) return out;
    let sum = 0;
    for (let i = 0; i < period; i++) sum += tr[i];
    let atr = sum / period;
    out[period - 1] = atr;
    for (let i = period; i < n; i++) {
      atr = (atr * (period - 1) + tr[i]) / period;
      out[i] = atr;
    }
    return out;
  }

  // SuperTrend(atr_period, mult): Wilder ATR + the standard recursion, a
  // line-by-line port of sentinel_engine/strategies/_supertrend_ref.py::
  // supertrend (read for the exact formula). Matches the engine's OWN call
  // convention (`live_configs_20.py supertrend_always_in_target`): ATR's
  // None warmup values are filled with 0.0 BEFORE running the recursion
  // (not skipped) -- so `line`/`trend` are defined from bar 0, same as what
  // the live engine actually computes/trades on. Returns {line, trend}.
  function computeSuperTrend(highs, lows, closes, atrPeriod, mult) {
    const n = closes.length;
    const atrRaw = computeAtrWilder(highs, lows, closes, atrPeriod);
    const atr = atrRaw.map((v) => (v === null ? 0.0 : v));
    const finUp = new Array(n).fill(0);
    const finLo = new Array(n).fill(0);
    const trend = new Array(n).fill(0);
    const line = new Array(n).fill(null);
    for (let i = 0; i < n; i++) {
      const hl2 = (highs[i] + lows[i]) / 2;
      const bUp = hl2 + mult * atr[i];
      const bLo = hl2 - mult * atr[i];
      if (i === 0) {
        finUp[i] = bUp;
        finLo[i] = bLo;
        trend[i] = closes[i] >= hl2 ? 1 : -1;
      } else {
        finUp[i] = (bUp < finUp[i - 1] || closes[i - 1] > finUp[i - 1]) ? bUp : finUp[i - 1];
        finLo[i] = (bLo > finLo[i - 1] || closes[i - 1] < finLo[i - 1]) ? bLo : finLo[i - 1];
        if (trend[i - 1] === 1 && closes[i] < finLo[i]) trend[i] = -1;
        else if (trend[i - 1] === -1 && closes[i] > finUp[i]) trend[i] = 1;
        else trend[i] = trend[i - 1];
      }
      line[i] = trend[i] === 1 ? finLo[i] : finUp[i];
    }
    return { line, trend };
  }

  async function fetchLastBars(symbol, tf) {
    const usp = new URLSearchParams({ symbol, tf, max_points: "3000" });
    const resp = await fetch(`/api/bars?${usp.toString()}`);
    if (!resp.ok) throw new Error(`GET /api/bars failed: ${resp.status}`);
    return resp.json();
  }

  async function applyOverlays(chartInst, symbol, tf, activeOverlays) {
    if (!activeOverlays.size) {
      ["EMA9", "EMA21", "EMA50", "BB"].forEach((id) => chartInst.removeOverlay(id));
      return;
    }
    let body;
    try {
      body = await fetchLastBars(symbol, tf);
    } catch (e) {
      return;
    }
    const bars = body.bars || [];
    if (!bars.length) return;
    const closes = bars.map((b) => b[4]);
    const times = bars.map((b) => b[0]);

    if (activeOverlays.has("EMA9")) {
      const vals = computeEMA(closes, 9);
      chartInst.addOverlay("EMA9", times.map((t, i) => [t, vals[i]]), OVERLAY_COLORS.EMA9);
    } else {
      chartInst.removeOverlay("EMA9");
    }
    if (activeOverlays.has("EMA21")) {
      const vals = computeEMA(closes, 21);
      chartInst.addOverlay("EMA21", times.map((t, i) => [t, vals[i]]), OVERLAY_COLORS.EMA21);
    } else {
      chartInst.removeOverlay("EMA21");
    }
    if (activeOverlays.has("EMA50")) {
      const vals = computeEMA(closes, 50);
      chartInst.addOverlay("EMA50", times.map((t, i) => [t, vals[i]]), OVERLAY_COLORS.EMA50);
    } else {
      chartInst.removeOverlay("EMA50");
    }
    if (activeOverlays.has("BB")) {
      const vals = computeBBUpper(closes, 20, 2);
      const pts = times.map((t, i) => [t, vals[i]]).filter(([, v]) => v !== null);
      chartInst.addOverlay("BB", pts, OVERLAY_COLORS.BB);
    } else {
      chartInst.removeOverlay("BB");
    }
  }

  function renderToolbar(root, initial, callbacks) {
    const bar = el("div", { class: "charts-toolbar" });

    // symbol select
    const symGroup = el("div", { class: "charts-toolbar-group" }, [
      el("label", { text: "Símbolo" }),
    ]);
    const symSel = el("select", { class: "charts-symbol-select" },
      SYMBOLS.map((s) => el("option", { value: s.value, text: s.label })));
    symSel.value = initial.symbol;
    symSel.addEventListener("change", () => callbacks.onSymbol(symSel.value));
    symGroup.appendChild(symSel);

    // TF buttons (exclusive group)
    const tfGroup = el("div", { class: "charts-toolbar-group" }, [
      el("label", { text: "TF" }),
    ]);
    const tfBtns = el("div", { class: "charts-tf-buttons" });
    TF_LIST.forEach((tfName) => {
      const btn = el("button", { type: "button", class: "charts-tf-btn", text: tfName });
      if (tfName === initial.tf) btn.classList.add("active");
      btn.addEventListener("click", () => {
        tfBtns.querySelectorAll(".charts-tf-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        callbacks.onTF(tfName);
      });
      tfBtns.appendChild(btn);
    });
    tfGroup.appendChild(tfBtns);

    // live ticks toggle
    const liveGroup = el("div", { class: "charts-toolbar-group" });
    const liveLabel = el("label", { class: "charts-live-toggle" });
    const liveCheckbox = el("input", { type: "checkbox" });
    liveCheckbox.addEventListener("change", () => callbacks.onLiveToggle(liveCheckbox.checked));
    liveLabel.appendChild(liveCheckbox);
    liveLabel.appendChild(el("span", { text: "Ticks en vivo" }));
    liveGroup.appendChild(liveLabel);

    // overlay multiselect
    const overlayGroup = el("div", { class: "charts-toolbar-group" }, [
      el("label", { text: "Overlays" }),
    ]);
    const overlayChips = el("div", { class: "charts-overlay-chips" });
    OVERLAYS.forEach((name) => {
      const chip = el("button", { type: "button", class: "charts-overlay-chip", text: name });
      chip.addEventListener("click", () => {
        chip.classList.toggle("active");
        callbacks.onOverlayToggle(name, chip.classList.contains("active"));
      });
      overlayChips.appendChild(chip);
    });
    overlayGroup.appendChild(overlayChips);

    bar.appendChild(symGroup);
    bar.appendChild(tfGroup);
    bar.appendChild(liveGroup);
    bar.appendChild(overlayGroup);
    if (window.SENTINEL.goto && callbacks.getChartInst) {
      window.SENTINEL.goto.createGotoControl(bar, {
        getSymbol: callbacks.getSymbol,
        getTf: callbacks.getTf,
        getChartInst: callbacks.getChartInst,
      });
    }
    root.appendChild(bar);
    return bar;
  }

  function render(mountEl) {
    mountEl.innerHTML = "";
    const root = el("div", { class: "charts-section" });
    mountEl.appendChild(root);

    const appState = (window.SENTINEL.appState = window.SENTINEL.appState || {});
    const initial = {
      symbol: appState.symbol || "XAUUSD",
      tf: appState.tf || "M1",
    };

    const chartHost = el("div", { class: "charts-chart-host" });
    const activeOverlays = new Set();
    let liveOn = false;
    let chartInst = null;
    // A11: liveAdapter wraps chartInst's own candle series/timeScale for the
    // `bar_tail` SSE tail (CT-9). Independent from chartInst.enableTicks()
    // (WS raw-tick live candle -- pre-existing), guarded behind
    // window.SENTINEL.adapters.LiveAdapter so charts.js never crashes if
    // adapters.js isn't loaded (same degrade pattern lib/chart.js uses for
    // HistAdapter).
    let liveAdapter = null;

    function teardownLiveAdapter() {
      if (liveAdapter) {
        try { liveAdapter.disconnect(); } catch (e) { /* noop */ }
        liveAdapter = null;
      }
    }

    function setupLiveAdapter(sym) {
      teardownLiveAdapter();
      if (!chartInst || !window.SENTINEL.adapters || !window.SENTINEL.adapters.LiveAdapter) return;
      const liveChart = {
        _candleSeries: chartInst._candleSeries,
        get tf() { return chartInst.tf; },
        timeScale: () => chartInst._chart.timeScale(),
      };
      liveAdapter = window.SENTINEL.adapters.LiveAdapter(liveChart, null, { symbol: sym });
      liveAdapter.connect();
    }

    const toolbar = renderToolbar(root, initial, {
      onSymbol: (sym) => {
        appState.symbol = sym;
        if (chartInst) {
          if (liveOn) chartInst.disableTicks();
          chartInst.symbol = sym;
          applyOverlays(chartInst, sym, appState.tf || "M1", activeOverlays);
          if (liveOn) chartInst.enableTicks(sym);
          if (liveAdapter) setupLiveAdapter(sym);
        }
      },
      onTF: (tf) => {
        appState.tf = tf;
        if (chartInst) {
          chartInst.setTF(tf).then(() => applyOverlays(chartInst, appState.symbol, tf, activeOverlays));
          if (liveAdapter) {
            if (typeof liveAdapter.setTf === "function") liveAdapter.setTf(tf);
            else setupLiveAdapter(appState.symbol || initial.symbol);
          }
        }
      },
      onLiveToggle: (checked) => {
        liveOn = checked;
        if (!chartInst) return;
        if (checked) {
          chartInst.enableTicks(appState.symbol || initial.symbol);
          setupLiveAdapter(appState.symbol || initial.symbol);
        } else {
          chartInst.disableTicks();
          teardownLiveAdapter();
        }
      },
      onOverlayToggle: (name, active) => {
        if (active) activeOverlays.add(name);
        else activeOverlays.delete(name);
        if (chartInst) applyOverlays(chartInst, appState.symbol || initial.symbol, appState.tf || initial.tf, activeOverlays);
      },
      getSymbol: () => appState.symbol || initial.symbol,
      getTf: () => appState.tf || initial.tf,
      getChartInst: () => chartInst,
    });

    root.appendChild(chartHost);

    chartInst = window.SENTINEL.chart.create(chartHost, { symbol: initial.symbol, tf: initial.tf });

    const playbackHost = el("div", { class: "playback-host" });
    root.appendChild(playbackHost);
    const playbackBar = renderPlaybackBar(playbackHost, () => chartInst);

    function escHandler(evt) {
      if (evt.key === "Escape" && chartInst) chartInst.stopPlayback();
    }
    document.addEventListener("keydown", escHandler);

    state = { root, chartInst, playbackBar, escHandler, teardownLiveAdapter };
  }

  function teardown() {
    if (state && state.escHandler) document.removeEventListener("keydown", state.escHandler);
    if (state && state.playbackBar) { try { state.playbackBar.destroy(); } catch (e) { /* noop */ } }
    if (state && state.teardownLiveAdapter) { try { state.teardownLiveAdapter(); } catch (e) { /* noop */ } }
    if (state && state.chartInst) {
      try { state.chartInst.stopPlayback(); } catch (e) { /* noop */ }
      try { state.chartInst.destroy(); } catch (e) { /* noop */ }
    }
    if (state && state.root) state.root.innerHTML = "";
    state = null;
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.charts = { render, teardown };
  // Task 1b: shared indicator calculators, reused by positions.js (ESTRATEGIA
  // per-strategy chart) so charts.js/positions.js don't duplicate the math.
  window.SENTINEL.chartCalc = {
    computeEMA,
    computeSMA,
    computeMomentum,
    computeSAR,
    computeAtrWilder,
    computeSuperTrend,
  };
})();
