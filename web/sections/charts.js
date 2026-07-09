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

    const toolbar = renderToolbar(root, initial, {
      onSymbol: (sym) => {
        appState.symbol = sym;
        if (chartInst) {
          if (liveOn) chartInst.disableTicks();
          chartInst.symbol = sym;
          applyOverlays(chartInst, sym, appState.tf || "M1", activeOverlays);
          if (liveOn) chartInst.enableTicks(sym);
        }
      },
      onTF: (tf) => {
        appState.tf = tf;
        if (chartInst) {
          chartInst.setTF(tf).then(() => applyOverlays(chartInst, appState.symbol, tf, activeOverlays));
        }
      },
      onLiveToggle: (checked) => {
        liveOn = checked;
        if (!chartInst) return;
        if (checked) chartInst.enableTicks(appState.symbol || initial.symbol);
        else chartInst.disableTicks();
      },
      onOverlayToggle: (name, active) => {
        if (active) activeOverlays.add(name);
        else activeOverlays.delete(name);
        if (chartInst) applyOverlays(chartInst, appState.symbol || initial.symbol, appState.tf || initial.tf, activeOverlays);
      },
    });

    root.appendChild(chartHost);

    chartInst = window.SENTINEL.chart.create(chartHost, { symbol: initial.symbol, tf: initial.tf });

    state = { root, chartInst, teardownFns: [] };
  }

  function teardown() {
    if (state && state.chartInst) {
      try { state.chartInst.destroy(); } catch (e) { /* noop */ }
    }
    if (state && state.root) state.root.innerHTML = "";
    state = null;
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.charts = { render, teardown };
})();
