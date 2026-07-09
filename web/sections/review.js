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

  // ---- run selector (searchable, grouped by strategy w/ badge D.3) ----
  function runOptionLabel(row) {
    const fmt = window.SENTINEL.fmt;
    return `${row.run_id} · ${row.instrumento || "--"} · net ${fmt.signed(row.net)}`;
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

    function renderGroups(filterText) {
      const q = (filterText || "").trim().toLowerCase();
      listHost.innerHTML = "";
      Object.keys(runsByStrategy).forEach((strategyId) => {
        const rows = runsByStrategy[strategyId].filter((r) => {
          if (!q) return true;
          return (
            (r.run_id || "").toLowerCase().includes(q) ||
            (r.instrumento || "").toLowerCase().includes(q) ||
            (r.display_name || "").toLowerCase().includes(q)
          );
        });
        if (!rows.length) return;
        const strat = strategiesById[strategyId] || {};
        const group = el("div", { class: "review-run-group" });
        const header = el("div", { class: "review-run-group-header" });
        header.innerHTML = window.SENTINEL.badge.strategyBadge({
          familia: strat.familia,
          name: strat.familia && strat.familia.toLowerCase() === (strat.name || "").toLowerCase() ? "" : strat.name,
          color_idx: strat.color_idx,
          display_name: strat.name,
        });
        group.appendChild(header);
        rows.forEach((row) => {
          const item = el("button", {
            type: "button", class: "review-run-item", "data-run-id": row.run_id,
            title: row.display_name || row.run_id,
          });
          item.innerHTML = `<span class="mono">${escapeHtml(runOptionLabel(row))}</span>`;
          item.addEventListener("click", () => onPick(row));
          group.appendChild(item);
        });
        listHost.appendChild(group);
      });
      if (!listHost.children.length) {
        listHost.innerHTML = '<div class="review-run-empty">Sin corridas.</div>';
      }
    }

    searchInput.addEventListener("input", () => renderGroups(searchInput.value));
    renderGroups("");
    return { markActive: (runId) => {
      listHost.querySelectorAll(".review-run-item").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.runId === runId);
      });
    } };
  }

  // ---- trade list (virtualized, lib/vtable.js) ----
  function tradeRowColumns() {
    const fmt = window.SENTINEL.fmt;
    return [
      { key: "n", label: "#", width: "34px", render: (r) => `<span class="mono">${r.__n}</span>` },
      { key: "side", label: "Lado", width: "56px",
        render: (r) => `<span class="${(r.side || "").toUpperCase() === "LONG" ? "sentinel-sign-pos" : "sentinel-sign-neg"}">${escapeHtml(r.side || "--")}</span>` },
      { key: "ts_in", label: "Entrada", width: "1fr", render: (r) => `<span class="mono">${fmt.tsShort(epochOf(r.ts_in))}</span>` },
      { key: "pnl", label: "PnL", width: "80px", numeric: true,
        render: (r) => `<span class="${signClass(r.pnl)} mono">${fmt.signed(r.pnl)}</span>` },
      { key: "exit_reason", label: "Exit", width: "56px", render: (r) => `<span class="mono" title="${escapeHtml(r.exit_reason || "")}">${escapeHtml(exitReasonAbbrev(r.exit_reason))}</span>` },
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
    const tradeListHost = el("div", { class: "review-tradelist-host" });
    left.appendChild(selectorHost);
    left.appendChild(tradeListHost);

    const headerHost = el("div", { class: "review-header-host" });
    const chartHost = el("div", { class: "review-chart-host" });
    right.appendChild(headerHost);
    right.appendChild(chartHost);

    const appState = (window.SENTINEL.appState = window.SENTINEL.appState || {});

    let chartInst = null;
    let vt = null;
    let currentTrades = [];
    let currentRunId = null;
    let currentColor = "#00bfff";
    let selectedIndex = -1;
    let strategiesById = {};
    let runsById = {};
    let selectorApi = null;

    function keyHandler(evt) {
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
      if (!currentTrades.length) return;
      let next = selectedIndex + delta;
      if (next < 0) next = 0;
      if (next >= currentTrades.length) next = currentTrades.length - 1;
      selectTradeAt(next);
    }

    function highlightRow(idx) {
      if (!left.querySelectorAll) return;
      tradeListHost.querySelectorAll(".vtable-row").forEach((rowEl) => {
        rowEl.classList.remove("review-row-selected");
      });
      const trade = currentTrades[idx];
      if (!trade) return;
      const rowEl = tradeListHost.querySelector(`.vtable-row[data-key="${CSS.escape(String(trade.trade_id))}"]`);
      if (rowEl) rowEl.classList.add("review-row-selected");
    }

    function selectTradeAt(idx) {
      const trade = currentTrades[idx];
      if (!trade || !chartInst) return;
      selectedIndex = idx;
      chartInst.selectTrade(trade);
      highlightRow(idx);
    }

    async function loadRunTrades(row) {
      currentRunId = row.run_id;
      if (selectorApi) selectorApi.markActive(row.run_id);
      appState.selectedRun = row.run_id;
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
      const tf = appState.tf || "M1";
      appState.symbol = symbol;
      appState.tf = tf;

      if (!chartInst) {
        chartInst = window.SENTINEL.chart.create(chartHost, { symbol, tf });
      } else {
        chartInst.symbol = symbol;
        if (chartInst.tf !== tf) await chartInst.setTF(tf);
      }

      let tradesBody;
      try {
        tradesBody = await fetchTrades(row.run_id);
      } catch (e) {
        tradeListHost.innerHTML = '<div class="review-tradelist-error">Error cargando trades.</div>';
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/runs/{id}/trades", { type: "error" });
        return;
      }

      currentTrades = tradesBody.trades || [];
      selectedIndex = -1;

      if (!currentTrades.length) {
        tradeListHost.innerHTML = '<div class="review-tradelist-empty">Esta corrida no tiene trades.</div>';
        if (chartInst) chartInst.selectTrade(null);
        return;
      }

      // all trades as dim markers (40% alpha per D.4/D.7)
      chartInst.addTradeMarkers(currentTrades, currentColor, { dim: true });

      const tableEl = el("div", { class: "review-vtable" });
      tradeListHost.innerHTML = "";
      tradeListHost.appendChild(tableEl);
      const rowsForTable = currentTrades.map((t, i) => Object.assign({ __n: i + 1 }, t));
      vt = window.SENTINEL.vtable.createVTable(tableEl, {
        columns: tradeRowColumns(),
        rows: rowsForTable,
        rowKey: (r) => r.trade_id,
        onRowClick: (r) => {
          const idx = currentTrades.findIndex((t) => t.trade_id === r.trade_id);
          if (idx >= 0) selectTradeAt(idx);
        },
      });

      // select first trade by default so the chart isn't empty on run pick.
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
        if (chartInst) { try { chartInst.destroy(); } catch (e) { /* noop */ } }
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
