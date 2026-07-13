// SENTINEL sections/review.js — TRADE REVIEW section (Task M2.2, plan
// §D.7-REVIEW NORMATIVE). Layout 2 columns (320px | 1fr):
//   LEFT  = searchable run selector (grouped by strategy, D.3 badges) +
//           virtualized trade list (lib/vtable.js).
//   RIGHT = shared chart (lib/chart.js) + run header (badges + summary).
// Interaction: selecting a run loads its trades, sets chart symbol/tf from
// the run's instrumento, draws ALL trades dim (40% alpha), and click/j/k
// select a trade -> chart.selectTrade() (full intensity, recenter, SL/TP)
// + highlights the list row. TF switch keeps the selected trade anchored.
// Classic script (no ES modules), hangs off window.SENTINEL.sections.review.
(function () {
  "use strict";

  let state = null; // per-mount state, rebuilt on render()

  const TF_LIST = ["M1", "M2", "M5", "M10", "M15"];
  const PLAYBACK_SPEEDS = [1, 5, 20, 60, "MAX"];

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

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function signClass(v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "";
    return Number(v) > 0 ? "sentinel-sign-pos" : Number(v) < 0 ? "sentinel-sign-neg" : "";
  }

  // instrumento (registry) already matches CHARTS symbol values (XAUUSD,
  // NQ100, USDCLP) 1:1 in the real TOKATA data — no remapping table needed,
  // just a safe default when a run has no instrumento.
  function instrumentoToSymbol(instrumento) {
    return instrumento || "XAUUSD";
  }

  function exitReasonAbbrev(reason) {
    if (!reason) return "--";
    const s = String(reason).trim();
    if (s.length <= 4) return s.toUpperCase();
    return s.slice(0, 4).toUpperCase();
  }

  // ---- data fetch (D.6 contracts) ----
  async function fetchStrategies() {
    const resp = await fetch("/api/strategies");
    if (!resp.ok) throw new Error(`GET /api/strategies failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchRuns() {
    const resp = await fetch("/api/runs?limit=500&order_by=fecha_corrida&dir=desc");
    if (!resp.ok) throw new Error(`GET /api/runs failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchRun(runId) {
    const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
    if (!resp.ok) throw new Error(`GET /api/runs/${runId} failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchTrades(runId) {
    const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/trades`);
    if (!resp.ok) throw new Error(`GET /api/runs/${runId}/trades failed: ${resp.status}`);
    return resp.json();
  }

  // ---- indicator overlays (EMA-fast/EMA-slow/SAR, backend-computed for
  // parity — spec 2026-07-09-trade-view-indicator-overlays) ----
  async function fetchIndicators(runId, tf, windowFrom, windowTo) {
    const usp = new URLSearchParams({ tf });
    // Defect B fix (Wave-2 plan 2026-07-10, candle-killer): bound the
    // request to the chart's CURRENT candle window so the overlay
    // time-range stays a subset of the candle time-range -- omitting
    // from/to (no window yet) falls back to the endpoint's full-frame
    // behavior.
    if (windowFrom !== undefined && windowFrom !== null) {
      usp.set("from", new Date(windowFrom * 1000).toISOString());
    }
    if (windowTo !== undefined && windowTo !== null) {
      usp.set("to", new Date(windowTo * 1000).toISOString());
    }
    const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}/indicators?${usp.toString()}`);
    if (!resp.ok) throw new Error(`GET /api/runs/${runId}/indicators failed: ${resp.status}`);
    return resp.json();
  }

  const OVERLAY_COLORS = {
    ema_fast: "#00bfff", ema_slow: "#ffb020", sar: "#ff6e40", supertrend: "#7e57c2",
    ema_pullback: "#26a69a",
    // extra fixed SAR(0.3/0.3) overlay -- distinct hue from the native SAR so
    // the two dot rows are visually separable when both are toggled on.
    sar_3_3: "#ffd54f",
    // oscillators (subpanel): white default per request; AC uses red/green
    // by sign (handled in chart.js addOscHistogram), AO neutral, Mom white.
    ao: "#c9d4e3", ac: "#c9d4e3", momentum: "#ffffff",
  };

  function renderOverlayChips(host, indicators, activeIds, onToggle) {
    host.innerHTML = "";
    const group = el("div", { class: "charts-overlay-chips review-overlay-chips" });
    indicators.forEach((ind) => {
      const chip = el("button", {
        type: "button", class: "charts-overlay-chip", text: ind.label, "data-indicator-id": ind.id,
      });
      if (activeIds.has(ind.id)) chip.classList.add("active");
      chip.addEventListener("click", () => {
        chip.classList.toggle("active");
        onToggle(ind, chip.classList.contains("active"));
      });
      group.appendChild(chip);
    });
    host.appendChild(group);
    return group;
  }

  function applyIndicator(chartInst, ind) {
    const color = OVERLAY_COLORS[ind.id] || "#00bfff";
    // Oscillators (AO/AC/Momentum) render in a dedicated bottom SUBPANEL
    // (separate price scale) so they don't distort the price axis. AO/AC are
    // histograms (red/green by sign like the reference terminal); Momentum is
    // a line. Everything else stays on the price scale (add-not-modify).
    if (ind.panel === "oscillator") {
      if (ind.kind === "histogram") {
        chartInst.addOscHistogram(ind.id, ind.points, color);
      } else {
        chartInst.addOscLine(ind.id, ind.points, color);
      }
    } else if (ind.kind === "dots") {
      chartInst.addSarDots(ind.id, ind.points, color);
    } else {
      chartInst.addOverlay(ind.id, ind.points, color);
    }
  }

  // ---- run selector (searchable, grouped by strategy w/ badge D.3) ----
  function runOptionLabel(row) {
    const fmt = window.SENTINEL.fmt;
    const label = row.variant_id || row.run_id;
    return `${label} · ${row.instrumento || "--"} · net ${fmt.signed(row.net)}`;
  }

  // Flattens the {strategyId: [rows]} map into a single list of rows, one
  // "group-header" row per strategy followed by its "run" rows -- same
  // header+child flattening technique used by buildSignalRows() below, so
  // the whole list (headers + runs, potentially hundreds of runs across
  // many strategies) can be windowed by a single lib/vlist.js instance
  // instead of rendering every row's DOM node up front.
  const RUN_ROW_HEIGHT = 22; // px, must match .review-run-item/.review-run-group-header row height

  function buildRunSelectorRows(runsByStrategy, strategiesById, filterText) {
    const q = (filterText || "").trim().toLowerCase();
    const flat = [];
    Object.keys(runsByStrategy).forEach((strategyId) => {
      const rows = runsByStrategy[strategyId].filter((r) => {
        if (!q) return true;
        return (
          (r.run_id || "").toLowerCase().includes(q) ||
          (r.variant_id || "").toLowerCase().includes(q) ||
          (r.instrumento || "").toLowerCase().includes(q) ||
          (r.display_name || "").toLowerCase().includes(q)
        );
      });
      if (!rows.length) return;
      const strat = strategiesById[strategyId] || {};
      flat.push({ __kind: "group-header", __rowKey: `hdr::${strategyId}`, strategyId, strat });
      rows.forEach((row) => {
        flat.push({ __kind: "run", __rowKey: `run::${row.run_id}`, row });
      });
    });
    return flat;
  }

  function renderRunSelectorRow(item, onPick) {
    if (item.__kind === "group-header") {
      const header = el("div", { class: "review-run-group-header" });
      const strat = item.strat;
      header.innerHTML = window.SENTINEL.badge.strategyBadge({
        familia: strat.familia,
        name: strat.familia && strat.familia.toLowerCase() === (strat.name || "").toLowerCase() ? "" : strat.name,
        color_idx: strat.color_idx,
        display_name: strat.name,
      });
      return header;
    }
    const row = item.row;
    const btn = el("button", {
      type: "button", class: "review-run-item", "data-run-id": row.run_id,
      title: row.display_name || row.run_id,
    });
    btn.innerHTML = `<span class="mono">${escapeHtml(runOptionLabel(row))}</span>`;
    btn.addEventListener("click", () => onPick(row));
    return btn;
  }

  function renderRunSelector(host, runsByStrategy, strategiesById, onPick) {
    host.innerHTML = "";
    const wrap = el("div", { class: "review-run-selector" });
    const searchInput = el("input", {
      type: "text", class: "review-run-search", placeholder: "Buscar corrida (run_id, instrumento)…",
    });
    const listHost = el("div", { class: "review-run-groups" });
    wrap.appendChild(searchInput);
    wrap.appendChild(listHost);
    host.appendChild(wrap);

    let activeRunId = null;
    let vlist = null;

    function currentRows(filterText) {
      return buildRunSelectorRows(runsByStrategy, strategiesById, filterText);
    }

    // windowed rendering (A6b, lib/vlist.js): only the rows visible in
    // listHost's viewport (+-10 rows) are materialized -- the run selector
    // can list hundreds of runs across many strategy groups.
    vlist = window.SENTINEL.vlist.createVList(listHost, {
      itemHeight: RUN_ROW_HEIGHT,
      items: currentRows(""),
      itemKey: (item) => item.__rowKey,
      render: (item) => renderRunSelectorRow(item, onPick),
    });
    // re-apply the .active class to whichever run row is currently
    // materialized -- selection is tracked by rowKey (vlist.setSelected),
    // so it survives a row scrolling out of/back into the viewport.
    function applyActiveClass() {
      listHost.querySelectorAll(".review-run-item").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.runId === activeRunId);
      });
    }
    const origSetItems = vlist.setItems;
    vlist.setItems = (items) => { origSetItems(items); applyActiveClass(); };

    function renderGroups(filterText) {
      vlist.setItems(currentRows(filterText));
    }

    searchInput.addEventListener("input", () => renderGroups(searchInput.value));
    return { markActive: (runId) => {
      activeRunId = runId;
      vlist.setSelected([`run::${runId}`]);
      applyActiveClass();
    } };
  }

  // ---- trade list (virtualized, lib/vtable.js) ----
  // Wave-2b req 7: group the 3 fichas (F1/F2/F3) under each SIGNAL. vtable
  // is a flat virtualized list, so the grouping is expressed as a flat row
  // model: one "header" row per signal (side, entry ts, px_in, signal total
  // pnl) followed by its 3 "ficha" sub-rows (ficha label, exit_reason,
  // px_out, per-ficha pnl), styled distinctly via a shared row-key so a
  // click on ANY row (header or ficha) selects the whole signal. Derived
  // purely from signal_id/ficha (req 8) -- no hardcoded run/signal ids.
  function groupBySignal(trades) {
    const order = [];
    const bySignal = new Map();
    (trades || []).forEach((t) => {
      const sid = t.signal_id || t.trade_id;
      let g = bySignal.get(sid);
      if (!g) {
        g = { signal_id: sid, side: t.side, ts_in: t.ts_in, px_in: t.px_in, fichas: [], pnl_total: 0 };
        bySignal.set(sid, g);
        order.push(g);
      }
      g.fichas.push(t);
      g.pnl_total += Number(t.pnl) || 0;
    });
    order.forEach((g) => g.fichas.sort((a, b) => (a.ficha || "").localeCompare(b.ficha || "")));
    return order;
  }

  // Flattens signals into vtable rows: 1 header row + N ficha rows/signal.
  // rowKey is the signal_id for EVERY row in the group (header + fichas) so
  // vtable's onRowClick can resolve straight back to the signal.
  function buildSignalRows(signals) {
    const rows = [];
    signals.forEach((sig, i) => {
      rows.push(Object.assign({ __kind: "header", __n: i + 1, __rowKey: `${sig.signal_id}::hdr` }, sig));
      sig.fichas.forEach((t) => {
        rows.push(Object.assign({ __kind: "ficha", __rowKey: `${sig.signal_id}::${t.ficha || t.trade_id}` }, t, { __signalId: sig.signal_id }));
      });
    });
    return rows;
  }

  function tradeRowColumns() {
    const fmt = window.SENTINEL.fmt;
    return [
      { key: "n", label: "#", width: "34px",
        render: (r) => (r.__kind === "header" ? `<span class="mono">${r.__n}</span>` : "") },
      { key: "side", label: "Lado", width: "56px",
        render: (r) => {
          if (r.__kind !== "header") return `<span class="review-ficha-label mono">${escapeHtml(r.ficha || "--")}</span>`;
          return `<span class="${(r.side || "").toUpperCase() === "LONG" ? "sentinel-sign-pos" : "sentinel-sign-neg"}">${escapeHtml(r.side || "--")}</span>`;
        } },
      { key: "ts_in", label: "Entrada", width: "1fr",
        render: (r) => {
          if (r.__kind === "header") return `<span class="mono">${fmt.tsShort(epochOf(r.ts_in))}</span>`;
          return `<span class="mono review-ficha-exit-reason" title="${escapeHtml(r.exit_reason || "")}">${escapeHtml(exitReasonAbbrev(r.exit_reason))} &middot; ${fmt.price(r.px_out, 2)}</span>`;
        } },
      { key: "pnl", label: "PnL", width: "80px", numeric: true,
        render: (r) => {
          const val = r.__kind === "header" ? r.pnl_total : r.pnl;
          return `<span class="${signClass(val)} mono">${fmt.signed(val)}</span>`;
        } },
      { key: "exit_reason", label: "Exit", width: "56px",
        render: (r) => (r.__kind === "header" ? "" : `<span class="mono" title="${escapeHtml(r.exit_reason || "")}">${escapeHtml(exitReasonAbbrev(r.exit_reason))}</span>`) },
    ];
  }

  function epochOf(v) {
    if (v === null || v === undefined) return null;
    if (typeof v === "number") return v > 1e12 ? v / 1000 : v;
    const d = new Date(v);
    return d.getTime() / 1000;
  }

  // ---- header (badge estrategia + badge fidelity + ventana + modelo_sim + summary) ----
  function renderHeader(host, runFull, strategy) {
    const fmt = window.SENTINEL.fmt;
    const badge = window.SENTINEL.badge;
    host.innerHTML = "";
    const stratBadge = strategy
      ? badge.strategyBadge({
          familia: strategy.familia,
          name: strategy.familia && strategy.familia.toLowerCase() === (strategy.name || "").toLowerCase() ? "" : strategy.name,
          color_idx: strategy.color_idx,
          display_name: strategy.name,
        })
      : "";
    const fidBadge = badge.fidelityBadge(runFull.fidelity);
    const win = `${runFull.periodo_desde || "--"} &rarr; ${runFull.periodo_hasta || "--"}`;
    host.innerHTML = `
      <div class="review-header-row">
        ${stratBadge} ${fidBadge}
        <span class="review-header-window mono">${win}</span>
        <span class="review-header-modelo mono">${escapeHtml(runFull.modelo_sim || "--")}</span>
      </div>
      <div class="review-header-summary mono">
        <span>net <span class="${signClass(runFull.net)}">${fmt.signed(runFull.net)}</span></span>
        <span>pf ${fmt.num(runFull.pf)}</span>
        <span>wr ${fmt.pct(runFull.wr)}</span>
        <span>maxdd ${fmt.num(runFull.maxdd)}</span>
      </div>`;
  }

  // ---- REVIEW TF-switcher (folded-in fix, closes M2.2 hito gap: recorrer
  // una corrida en M1 y M5) — exclusive M1/M2/M5/M10/M15 buttons, same
  // pattern as charts.js .charts-tf-btn. On switch: chartInst.setTF(tf)
  // then re-selectTrade(currentTrade) so the anchor trade stays centered
  // by timestamp across TFs. ----
  function renderTfButtons(host, initialTf, onTF) {
    const group = el("div", { class: "review-tf-buttons" });
    TF_LIST.forEach((tfName) => {
      const btn = el("button", { type: "button", class: "review-tf-btn", text: tfName, "data-tf": tfName });
      if (tfName === initialTf) btn.classList.add("active");
      btn.addEventListener("click", () => {
        group.querySelectorAll(".review-tf-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        onTF(tfName);
      });
      group.appendChild(btn);
    });
    host.appendChild(group);
    return group;
  }

  // TF dot: marks the button whose data-tf matches the loaded run's native
  // tf (run.tf) with .native-tf -- CSS ::after draws a small accent dot,
  // purely visual (no size/layout change to the button).
  function markNativeTfButton(group, run) {
    if (!group) return;
    const nativeTf = run && run.tf;
    group.querySelectorAll(".review-tf-btn").forEach((btn) => {
      btn.classList.toggle("native-tf", !!nativeTf && btn.dataset.tf === nativeTf);
    });
  }

  // ---- split-pane divider (left column: run-selector / trade-list) ----
  // BUG-L2 fix: the previous design toggled a 3fr/1fr "focus" on ANY CLICK in
  // either pane -- so simply selecting a run threw the split to 3:1 and it
  // never returned to 50/50 (the reported "not working"). Replaced with an
  // explicit DRAGGABLE divider between the two panes: default is a clean
  // 50/50 (grid-template-rows via --tv-split, 0.5), dragging the handle
  // re-proportions runs vs trades, persisted under "tv.splitFrac". Normal
  // clicks on run rows / trade rows no longer affect the split. The old
  // focused-top/bottom CSS classes are left in place (unused) for a possible
  // future preset-toggle (backlog).
  const SPLIT_FRAC_KEY = "tv.splitFrac";

  function applySplit(leftEl, frac) {
    // frac = fraction of the resizable area given to the TOP (runs) pane.
    const f = Math.max(0.15, Math.min(0.85, Number(frac) || 0.5));
    leftEl.style.gridTemplateRows = `${f}fr 6px ${1 - f}fr`;
  }

  function setupPaneDivider(leftEl, dividerEl) {
    let frac = 0.5;
    try {
      const stored = parseFloat(localStorage.getItem(SPLIT_FRAC_KEY));
      if (!Number.isNaN(stored)) frac = stored;
    } catch (e) { /* noop */ }
    applySplit(leftEl, frac);

    let dragging = false;
    function onMove(ev) {
      if (!dragging) return;
      const rect = leftEl.getBoundingClientRect();
      const y = (ev.touches ? ev.touches[0].clientY : ev.clientY) - rect.top;
      frac = y / rect.height;
      applySplit(leftEl, frac);
      ev.preventDefault();
    }
    function onUp() {
      if (!dragging) return;
      dragging = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onUp);
      try { localStorage.setItem(SPLIT_FRAC_KEY, String(Math.max(0.15, Math.min(0.85, frac)))); } catch (e) { /* noop */ }
    }
    function onDown(ev) {
      dragging = true;
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      document.addEventListener("touchmove", onMove, { passive: false });
      document.addEventListener("touchend", onUp);
      ev.preventDefault();
    }
    dividerEl.addEventListener("mousedown", onDown);
    dividerEl.addEventListener("touchstart", onDown, { passive: false });
  }

  // ---- playback UI bar (Task M2.6) — same pattern as charts.js:
  // ▶/⏸ + speed selector + scrub slider + ts label, polling
  // chartInst.getPlaybackState() on ONE interval. REVIEW plays back the
  // selected run's window WITH its trades appearing/closing (handled
  // inside lib/chart.js against the already-loaded trade markers).
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

  // ---- main render ----
  function render(mountEl) {
    mountEl.innerHTML = "";
    const root = el("div", { class: "review-section" });
    const left = el("div", { class: "review-left" });
    const right = el("div", { class: "review-right" });
    root.appendChild(left);
    root.appendChild(right);
    mountEl.appendChild(root);

    const selectorHost = el("div", { class: "review-selector-host" });
    const paneDivider = el("div", { class: "review-pane-divider", title: "Arrastrar para redimensionar" });
    const tradeListHost = el("div", { class: "review-tradelist-host" });
    left.appendChild(selectorHost);
    left.appendChild(paneDivider);
    left.appendChild(tradeListHost);
    // BUG-L2 fix: default 50/50 runs/trades split with an explicit draggable
    // divider between them (see setupPaneDivider). Replaces the old
    // click-anywhere-to-focus behavior that jammed the split at 3:1 on run
    // selection. The search bar stays where it is (inside the runs pane, per
    // the user's "search bar is correct, do not touch").
    setupPaneDivider(left, paneDivider);

    const reviewToolbar = el("div", { class: "review-toolbar" });
    const overlayChipsHost = el("div", { class: "review-overlay-chips-host" });
    const headerHost = el("div", { class: "review-header-host" });
    const chartHost = el("div", { class: "review-chart-host" });
    const posNavHost = el("div", { class: "review-posnav" });
    const playbackHost = el("div", { class: "playback-host" });
    right.appendChild(reviewToolbar);
    right.appendChild(overlayChipsHost);
    right.appendChild(headerHost);
    right.appendChild(chartHost);
    right.appendChild(posNavHost);
    right.appendChild(playbackHost);

    // Position nav bar (◀ / counter / ▶): step through trades in order, each
    // centered on the chart with its entry+exit visible. Mirrors the j/k keys.
    const posPrevBtn = el("button", { type: "button", class: "review-posnav-btn", title: "Posición anterior (k)", text: "◀ Anterior" });
    const posCounter = el("span", { class: "review-posnav-counter mono", text: "-- / --" });
    const posNextBtn = el("button", { type: "button", class: "review-posnav-btn", title: "Posición siguiente (j)", text: "Siguiente ▶" });
    posNavHost.appendChild(posPrevBtn);
    posNavHost.appendChild(posCounter);
    posNavHost.appendChild(posNextBtn);
    posPrevBtn.addEventListener("click", () => moveSelection(-1));
    posNextBtn.addEventListener("click", () => moveSelection(1));

    function updatePosCounter() {
      // Wave-2b req 3/7: j/k and the ◀/▶ nav bar step through SIGNALS (23),
      // not raw ficha trade rows (69).
      const total = currentSignals.length;
      const cur = selectedIndex >= 0 ? selectedIndex + 1 : 0;
      posCounter.textContent = total ? `${cur} / ${total}` : "-- / --";
      posPrevBtn.disabled = !total || selectedIndex <= 0;
      posNextBtn.disabled = !total || selectedIndex >= total - 1;
    }

    const appState = (window.SENTINEL.appState = window.SENTINEL.appState || {});

    let chartInst = null;
    let vt = null;
    let currentTrades = [];  // flat ficha trades (chart markers need every ficha)
    let currentSignals = []; // grouped {signal_id, side, ts_in, px_in, fichas:[...], pnl_total} -- req 7/3 nav unit
    let currentRunId = null;
    let currentColor = "#00bfff";
    let selectedIndex = -1;
    let strategiesById = {};
    let runsById = {};
    let selectorApi = null;
    let activeOverlayIds = new Set(); // persists across tf switches/runs
    // FIX 5 / D80: the backend now returns EVERY indicator for EVERY run with
    // a `default_on` flag (its own strategy's indicators start ON, the rest
    // are present but OFF, all toggleable). An indicator the user has NOT
    // explicitly toggled follows its `default_on`; once toggled, the user's
    // choice sticks (tracked in userTouchedIds) across tf switches. Switching
    // runs resets both so each run opens with ITS default-on set.
    let userTouchedIds = new Set();
    let tfButtonsGroup = null;
    let userPickedTf = false; // true once the user clicks a TF button explicitly

    // folded-in fix: TF switcher keeps the selected trade anchored by
    // timestamp across TFs (setTF then re-selectTrade(currentTrade)); also
    // refreshes indicator overlays for the new tf (native-tf default fix +
    // indicator-overlays spec). Initial highlight before any run is picked
    // has no "native tf" to fall back to yet, so it uses the last-known
    // appState.tf (from a previous section visit) or the DEFAULT_TF
    // constant — never a hardcoded "M1" literal (that literal is what
    // caused the "Sin barras para XAUUSD M1" bug for M2-native runs).
    const DEFAULT_TF = "M5";
    tfButtonsGroup = renderTfButtons(reviewToolbar, appState.tf || DEFAULT_TF, (tf) => {
      userPickedTf = true;
      appState.tf = tf;
      if (!chartInst) return;
      // Task 2.1 (Wave-3 Stage 2): chart.js setTF() now self-anchors to the
      // selected trade (re-runs selectTrade internally when one is
      // selected -- the anchorTrade is whichever ficha of currentSignals
      // is currently selected), so this handler no longer calls
      // selectTrade itself -- doing so here too would cause a redundant
      // double window fetch. setTF()'s returned promise already resolves
      // AFTER the anchored selectTrade's setWindow settles, so
      // refreshIndicators() below sees the NEW (post-selection) window.
      const anchorSignal = currentSignals[selectedIndex] || null;
      const anchorTrade = anchorSignal ? anchorSignal.fichas[0] : null; // eslint-disable-line no-unused-vars
      chartInst.setTF(tf).then(refreshIndicators);
    });
    // no run loaded yet at boot -- clears/no-ops the dot until loadRunTrades
    // marks it against the actual run.tf below.
    markNativeTfButton(tfButtonsGroup, null);

    // Task A7: goto-date control -- shared web/lib/goto.js helper, wired
    // here (same reviewToolbar as the TF buttons above).
    if (window.SENTINEL.goto) {
      window.SENTINEL.goto.createGotoControl(reviewToolbar, {
        getSymbol: () => appState.symbol,
        getTf: () => appState.tf || DEFAULT_TF,
        getChartInst: () => chartInst,
      });
    }

    function setActiveTfButton(tf) {
      if (!tfButtonsGroup) return;
      tfButtonsGroup.querySelectorAll(".review-tf-btn").forEach((b) => {
        b.classList.toggle("active", b.textContent === tf);
      });
    }

    async function refreshIndicators() {
      if (!chartInst || !currentRunId) return;
      let body;
      try {
        body = await fetchIndicators(
          currentRunId, appState.tf || DEFAULT_TF,
          chartInst.windowFrom, chartInst.windowTo,
        );
      } catch (e) {
        return;
      }
      const indicators = body.indicators || [];
      // FIX 5 / D80: for any indicator the user hasn't explicitly toggled this
      // run, honor its backend `default_on` -> seed activeOverlayIds so the
      // run opens with its own strategy's indicators ON and the rest OFF.
      indicators.forEach((ind) => {
        if (userTouchedIds.has(ind.id)) return;
        if (ind.default_on) activeOverlayIds.add(ind.id);
        else activeOverlayIds.delete(ind.id);
      });
      renderOverlayChips(overlayChipsHost, indicators, activeOverlayIds, (ind, active) => {
        userTouchedIds.add(ind.id);
        if (active) {
          activeOverlayIds.add(ind.id);
          applyIndicator(chartInst, ind);
        } else {
          activeOverlayIds.delete(ind.id);
          chartInst.removeOverlay(ind.id);
        }
      });
      indicators.forEach((ind) => {
        if (activeOverlayIds.has(ind.id)) applyIndicator(chartInst, ind);
        else chartInst.removeOverlay(ind.id);
      });
    }

    const playbackBar = renderPlaybackBar(playbackHost, () => chartInst);

    function keyHandler(evt) {
      if (evt.key === "Escape") {
        if (chartInst) chartInst.stopPlayback();
        return;
      }
      if (evt.target && /^(input|textarea|select)$/i.test(evt.target.tagName)) return;
      if (evt.key === "j" || evt.key === "J") {
        evt.preventDefault();
        moveSelection(1);
      } else if (evt.key === "k" || evt.key === "K") {
        evt.preventDefault();
        moveSelection(-1);
      }
    }
    document.addEventListener("keydown", keyHandler);

    function moveSelection(delta) {
      // Wave-2b req 3/7: step through SIGNALS in order (not raw ficha rows).
      if (!currentSignals.length) return;
      let next = selectedIndex + delta;
      if (next < 0) next = 0;
      if (next >= currentSignals.length) next = currentSignals.length - 1;
      selectTradeAt(next);
    }

    function highlightRow(idx) {
      // Highlights EVERY row (header + all 3 ficha sub-rows) belonging to
      // the selected signal -- req 3/7: the whole signal group is bright.
      if (!left.querySelectorAll) return;
      tradeListHost.querySelectorAll(".vtable-row").forEach((rowEl) => {
        rowEl.classList.remove("review-row-selected");
      });
      const signal = currentSignals[idx];
      if (!signal) return;
      tradeListHost.querySelectorAll(`.vtable-row[data-key^="${CSS.escape(String(signal.signal_id))}::"]`).forEach((rowEl) => {
        rowEl.classList.add("review-row-selected");
      });
    }

    function selectTradeAt(idx) {
      // Selects the SIGNAL at `idx` (any of its fichas may be passed to
      // chart.selectTrade -- lib/chart.js resolves the whole signal group
      // from signal_id internally, per Wave-2b req 3).
      const signal = currentSignals[idx];
      const trade = signal ? signal.fichas[0] : null;
      if (!trade || !chartInst) return;
      selectedIndex = idx;
      // Defect B fix: await selectTrade's returned setWindow promise
      // before refreshIndicators() so /indicators?from&to is requested
      // for the trade's SETTLED (recentered) window, never the stale one.
      Promise.resolve(chartInst.selectTrade(trade)).then(refreshIndicators);
      highlightRow(idx);
      updatePosCounter();
    }

    async function loadRunTrades(row) {
      currentRunId = row.run_id;
      // FIX 5 / D80: each run opens with ITS own default-on indicator set --
      // reset per-run selection state so a prior run's toggles don't leak
      // (e.g. SAR left ON from an EMASAR run onto the SuperTrend run).
      userTouchedIds = new Set();
      activeOverlayIds = new Set();
      if (selectorApi) selectorApi.markActive(row.run_id);
      appState.selectedRun = row.run_id;
      try {
        localStorage.setItem("sentinel.ui.review", JSON.stringify({ runId: row.run_id, tf: appState.tf, signalId: null }));
      } catch (e) {}
      headerHost.innerHTML = '<div class="review-header-loading">Cargando corrida&hellip;</div>';
      tradeListHost.innerHTML = '<div class="review-tradelist-loading">Cargando trades&hellip;</div>';

      let runFull;
      try {
        runFull = await fetchRun(row.run_id);
      } catch (e) {
        headerHost.innerHTML = '<div class="review-header-error">Error cargando la corrida.</div>';
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/runs/{id}", { type: "error" });
        return;
      }

      const strategy = strategiesById[runFull.strategy_id] || strategiesById[row.strategy_id];
      currentColor = window.SENTINEL.badge.colorForIdx(
        (strategy && strategy.color_idx) !== undefined ? strategy.color_idx : row.color_idx
      );
      renderHeader(headerHost, runFull, strategy);

      const symbol = instrumentoToSymbol(runFull.instrumento || row.instrumento);
      // Native-tf default fix: open on the RUN's own native tf (runFull.tf,
      // sourced from variant.tf) unless the user has already explicitly
      // picked a tf this session — a hardcoded "M1" fallback here produced
      // "Sin barras para XAUUSD M1" whenever an M2 (or other non-M1) run
      // opened, since M1 bars for that run's window may not exist.
      const tf = userPickedTf ? (appState.tf || runFull.tf || DEFAULT_TF) : (runFull.tf || appState.tf || DEFAULT_TF);
      appState.symbol = symbol;
      appState.tf = tf;
      setActiveTfButton(tf);
      // native-tf dot: mark the TF button matching this run's own native tf
      // (runFull.tf, sourced from variant.tf) -- separate from the
      // currently-ACTIVE tf button set just above.
      markNativeTfButton(tfButtonsGroup, runFull);

      if (!chartInst) {
        // windowMode: REVIEW pins an explicit per-trade window via
        // setWindow(); disables the chunked LOD prefetch that otherwise
        // clobbered the trade window (self-move) and thrashed redraws to
        // ~1fps on runs whose trades sit far from the data tail (BUG-C1/C3).
        chartInst = window.SENTINEL.chart.create(chartHost, { symbol, tf, windowMode: true });
      } else {
        // Set the symbol WITHOUT triggering the setter's TAIL loadInitial() --
        // selectTradeAt(0) below owns the single (trade-window) load. This
        // removes the loadInitial-vs-setWindow race that could leave the chart
        // with 0 committed bars (root cause, 2026-07-11b4).
        chartInst.setSymbolNoLoad(symbol);
        if (chartInst.tf !== tf) await chartInst.setTF(tf);
      }
      // Defect B fix: refreshIndicators() moved out of here -- it used to
      // fire immediately after chart creation/setTF, i.e. BEFORE any trade
      // is selected and the chart recenters its window around it. Fetching
      // /indicators against that pre-selection window could return a range
      // wider than (or disjoint from) the eventual trade-centered candle
      // window. selectTradeAt() now calls refreshIndicators() itself, after
      // its selectTrade() promise (setWindow) resolves. The empty-trades
      // early-return path below still needs a refresh since selectTradeAt
      // is never reached in that case.

      let tradesBody;
      try {
        tradesBody = await fetchTrades(row.run_id);
      } catch (e) {
        tradeListHost.innerHTML = '<div class="review-tradelist-error">Error cargando trades.</div>';
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/runs/{id}/trades", { type: "error" });
        return;
      }

      currentTrades = tradesBody.trades || [];
      // Wave-2b req 1/7: group the flat ficha trades by signal_id -- the
      // trade list and j/k navigation operate on SIGNALS (23), the chart
      // markers still need every individual ficha trade (69).
      currentSignals = groupBySignal(currentTrades);
      selectedIndex = -1;

      if (!currentTrades.length) {
        tradeListHost.innerHTML = '<div class="review-tradelist-empty">Esta corrida no tiene trades.</div>';
        if (chartInst) chartInst.selectTrade(null);
        refreshIndicators();
        updatePosCounter();
        return;
      }

      // all trades as dim markers; non-selected alpha is halved in chart.js
      // (FIX 3: markers 0.15, connectors 0.11, overlay hairlines 0.175 -- the
      // user wanted non-selected positions 50% MORE transparent).
      chartInst.addTradeMarkers(currentTrades, currentColor, { dim: true });

      const tableEl = el("div", { class: "review-vtable" });
      tradeListHost.innerHTML = "";
      tradeListHost.appendChild(tableEl);
      const rowsForTable = buildSignalRows(currentSignals);
      vt = window.SENTINEL.vtable.createVTable(tableEl, {
        columns: tradeRowColumns(),
        rows: rowsForTable,
        rowKey: (r) => r.__rowKey,
        onRowClick: (r) => {
          const sid = r.__kind === "header" ? r.signal_id : r.__signalId;
          const idx = currentSignals.findIndex((s) => s.signal_id === sid);
          if (idx >= 0) selectTradeAt(idx);
        },
      });

      // select first signal by default so the chart isn't empty on run pick.
      selectTradeAt(0);
    }

    async function boot() {
      let strategiesBody;
      let runsBody;
      try {
        [strategiesBody, runsBody] = await Promise.all([fetchStrategies(), fetchRuns()]);
      } catch (e) {
        selectorHost.innerHTML = '<div class="review-selector-error">Error cargando corridas/estrategias.<button type="button" class="review-retry-btn">Reintentar</button></div>';
        const btn = selectorHost.querySelector(".review-retry-btn");
        if (btn) btn.addEventListener("click", boot);
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/runs", { type: "error" });
        return;
      }

      strategiesById = {};
      (strategiesBody.strategies || []).forEach((s) => { strategiesById[s.strategy_id] = s; });

      try {
        const s = JSON.parse(localStorage.getItem("sentinel.ui.review") || "null");
        if (s && s.runId && !appState.selectedRun) {
          appState.selectedRun = s.runId;
          if (s.tf) appState.tf = s.tf;
        }
      } catch (e) {}

      const rows = runsBody.rows || [];
      runsById = {};
      rows.forEach((r) => { runsById[r.run_id] = r; });

      const runsByStrategy = {};
      rows.forEach((r) => {
        const key = r.strategy_id || "unknown";
        (runsByStrategy[key] = runsByStrategy[key] || []).push(r);
      });

      selectorApi = renderRunSelector(selectorHost, runsByStrategy, strategiesById, (row) => loadRunTrades(row));

      // honor appState.selectedRun if pre-set (RUNS "Ver trades -> REVIEW")
      const preselected = appState.selectedRun && runsById[appState.selectedRun];
      if (preselected) {
        loadRunTrades(preselected);
      } else {
        tradeListHost.innerHTML = '<div class="review-tradelist-empty">Elegí una corrida a la izquierda.</div>';
        headerHost.innerHTML = '<div class="review-header-empty">Sin corrida seleccionada.</div>';
      }
    }

    boot();

    state = {
      root,
      teardown: () => {
        document.removeEventListener("keydown", keyHandler);
        if (playbackBar) { try { playbackBar.destroy(); } catch (e) { /* noop */ } }
        if (chartInst) {
          try { chartInst.stopPlayback(); } catch (e) { /* noop */ }
          try { chartInst.destroy(); } catch (e) { /* noop */ }
        }
        if (vt) { try { vt.destroy(); } catch (e) { /* noop */ } }
      },
    };
  }

  function teardown() {
    if (state) {
      try { state.teardown(); } catch (e) { /* noop */ }
      if (state.root) state.root.innerHTML = "";
    }
    state = null;
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.review = { render, teardown };
})();
