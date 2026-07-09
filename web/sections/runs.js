// SENTINEL sections/runs.js — RUNS section (M2.1, plan §D.7-RUNS NORMATIVE).
// Filter bar + virtualized sortable table (lib/vtable.js) + right drawer
// (full metrics + .htm evidence link + "Ver trades -> REVIEW") + compare
// modal (uPlot: overlaid equity curves or comparative bars, D.3 color/dash).
// Classic script (no ES modules), hangs off window.SENTINEL.sections.runs.
(function () {
  "use strict";

  const FIDELITIES = ["research", "screening", "real-tick", "forward", "live-demo"];
  const DASH_PATTERNS = [[], [6, 4], [1, 3]]; // solid, dashed, dotted (uPlot dash arrays)

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

  function qs(params) {
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === null || v === undefined || v === "") continue;
      if (Array.isArray(v)) { if (v.length) usp.set(k, v.join(",")); continue; }
      usp.set(k, v);
    }
    const s = usp.toString();
    return s ? `?${s}` : "";
  }

  // ---- badge helpers (D.3 R note: familia==name -> show once) ----
  function runBadgeHtml(row) {
    const familia = row.familia || "";
    const name = row.display_name || row.familia || "";
    // display_name is often "{familia} · {nombre} · {suffix}"; if familia
    // equals the bare strategy name (current data quirk), avoid duplicating.
    let nombre = name;
    if (familia && name && name.startsWith(`${familia} ·`)) {
      nombre = name.slice(familia.length + 2).trim();
    }
    if (familia && nombre && familia.toLowerCase() === nombre.toLowerCase()) {
      nombre = ""; // show familia once only
    }
    return window.SENTINEL.badge.strategyBadge({
      familia,
      name: nombre,
      color_idx: row.color_idx,
      display_name: row.display_name,
    });
  }

  // ---- data fetch ----
  async function fetchRuns(filters) {
    const query = qs({
      strategy_id: filters.strategy_ids && filters.strategy_ids.length ? filters.strategy_ids.join(",") : "",
      instrumento: filters.instrumento,
      engine: filters.engine,
      fidelity: filters.fidelity,
      desde: filters.desde,
      hasta: filters.hasta,
      order_by: filters.order_by || "fecha_corrida",
      dir: filters.dir || "desc",
      limit: 500,
      offset: 0,
    });
    const resp = await fetch(`/api/runs${query}`);
    if (!resp.ok) throw new Error(`GET /api/runs failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchStrategies() {
    const resp = await fetch("/api/strategies");
    if (!resp.ok) throw new Error(`GET /api/strategies failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchRun(runId) {
    const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
    if (!resp.ok) throw new Error(`GET /api/runs/${runId} failed: ${resp.status}`);
    return resp.json();
  }

  // ---- table columns (D.7-RUNS: badge estrategia · variant_id mono · instr ·
  // fidelity badge · trades · net · PF · WR% · payoff · maxDD · sharpe · fecha) ----
  function buildColumns() {
    const fmt = window.SENTINEL.fmt;
    const badge = window.SENTINEL.badge;
    return [
      { key: "strategy", label: "Estrategia", width: "180px", render: (r) => runBadgeHtml(r) },
      { key: "variant_id", label: "Variante", width: "170px", sortable: true,
        render: (r) => `<span class="mono">${escapeHtml(r.variant_id || "--")}</span>` },
      { key: "instrumento", label: "Instr", width: "80px", sortable: true, render: (r) => escapeHtml(r.instrumento || "--") },
      { key: "fidelity", label: "Fidelity", width: "90px", sortable: true, render: (r) => badge.fidelityBadge(r.fidelity) },
      { key: "trades", label: "Trades", width: "70px", sortable: true, numeric: true, render: (r) => fmt.num(r.trades, 0) },
      { key: "net", label: "Net", width: "90px", sortable: true, numeric: true,
        render: (r) => `<span class="${signClass(r.net)}">${fmt.signed(r.net)}</span>` },
      { key: "pf", label: "PF", width: "70px", sortable: true, numeric: true,
        render: (r) => `<span class="${signClass((r.pf ?? 1) - 1)}">${fmt.num(r.pf)}</span>` },
      { key: "wr", label: "WR%", width: "70px", sortable: true, numeric: true, render: (r) => fmt.pct(r.wr) },
      { key: "payoff", label: "Payoff", width: "80px", sortable: true, numeric: true, render: (r) => fmt.num(r.payoff) },
      { key: "maxdd", label: "MaxDD", width: "80px", sortable: true, numeric: true, render: (r) => fmt.num(r.maxdd) },
      { key: "sharpe", label: "Sharpe", width: "80px", sortable: true, numeric: true, render: (r) => fmt.num(r.sharpe) },
      { key: "fecha_corrida", label: "Fecha", width: "110px", sortable: true, render: (r) => escapeHtml(r.fecha_corrida || "--") },
    ];
  }

  function signClass(v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "";
    return Number(v) > 0 ? "sentinel-sign-pos" : Number(v) < 0 ? "sentinel-sign-neg" : "";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // ---- filter bar ----
  function renderFilterBar(root, strategies, onChange) {
    const bar = el("div", { class: "runs-filterbar" });

    const stratWrap = el("div", { class: "runs-filter-group" }, [
      el("label", { text: "Estrategia" }),
    ]);
    const stratChips = el("div", { class: "runs-strategy-chips" });
    const selectedStrategies = new Set();
    strategies.forEach((s) => {
      const chip = el("button", { class: "runs-strategy-chip", type: "button" });
      chip.innerHTML = window.SENTINEL.badge.strategyBadge({
        familia: s.familia, name: s.familia && s.familia.toLowerCase() === (s.name || "").toLowerCase() ? "" : s.name,
        color_idx: s.color_idx, display_name: `${s.name} (${s.n_runs} runs)`,
      });
      chip.dataset.strategyId = s.strategy_id;
      chip.addEventListener("click", () => {
        if (selectedStrategies.has(s.strategy_id)) {
          selectedStrategies.delete(s.strategy_id);
          chip.classList.remove("active");
        } else {
          selectedStrategies.add(s.strategy_id);
          chip.classList.add("active");
        }
        onChange({ strategy_ids: Array.from(selectedStrategies) });
      });
      stratChips.appendChild(chip);
    });
    stratWrap.appendChild(stratChips);

    const instrInput = el("input", { type: "text", placeholder: "Instrumento", class: "runs-filter-input" });
    instrInput.addEventListener("change", () => onChange({ instrumento: instrInput.value.trim() }));

    const engineSel = el("select", { class: "runs-filter-input" }, [
      el("option", { value: "", text: "Engine: todos" }),
      ...["sentinel-replay", "sentinel-sim", "mt5-tester", "nt8-manual"].map((v) => el("option", { value: v, text: v })),
    ]);
    engineSel.addEventListener("change", () => onChange({ engine: engineSel.value }));

    const fidSel = el("select", { class: "runs-filter-input" }, [
      el("option", { value: "", text: "Fidelity: todas" }),
      ...FIDELITIES.map((v) => el("option", { value: v, text: v })),
    ]);
    fidSel.addEventListener("change", () => onChange({ fidelity: fidSel.value }));

    const desdeInput = el("input", { type: "date", class: "runs-filter-input" });
    desdeInput.addEventListener("change", () => onChange({ desde: desdeInput.value }));
    const hastaInput = el("input", { type: "date", class: "runs-filter-input" });
    hastaInput.addEventListener("change", () => onChange({ hasta: hastaInput.value }));

    bar.appendChild(stratWrap);
    bar.appendChild(el("div", { class: "runs-filter-group" }, [el("label", { text: "Instrumento" }), instrInput]));
    bar.appendChild(el("div", { class: "runs-filter-group" }, [engineSel]));
    bar.appendChild(el("div", { class: "runs-filter-group" }, [fidSel]));
    bar.appendChild(el("div", { class: "runs-filter-group" }, [
      el("label", { text: "Desde" }), desdeInput, el("label", { text: "Hasta" }), hastaInput,
    ]));

    root.appendChild(bar);
    return bar;
  }

  // ---- drawer ----
  function openDrawer(row) {
    closeDrawer();
    const overlay = el("div", { class: "runs-drawer-overlay" });
    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeDrawer(); });
    const drawer = el("div", { class: "runs-drawer" });

    const fmt = window.SENTINEL.fmt;
    drawer.innerHTML = `
      <div class="runs-drawer-header">
        ${runBadgeHtml(row)} ${window.SENTINEL.badge.fidelityBadge(row.fidelity)}
        <button type="button" class="runs-drawer-close" aria-label="Cerrar">&times;</button>
      </div>
      <div class="runs-drawer-body">
        <div class="runs-drawer-loading">Cargando métricas…</div>
      </div>`;
    drawer.querySelector(".runs-drawer-close").addEventListener("click", closeDrawer);
    overlay.appendChild(drawer);
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add("visible"));

    fetchRun(row.run_id).then((full) => {
      const body = drawer.querySelector(".runs-drawer-body");
      const metricsRows = [
        ["Run ID", full.run_id], ["Variant", full.variant_id],
        ["Instrumento", full.instrumento], ["Engine", full.engine],
        ["Periodo", `${full.periodo_desde || "--"} → ${full.periodo_hasta || "--"}`],
        ["Modelo sim", full.modelo_sim || "--"],
        ["Trades", fmt.num(full.trades, 0)], ["Net", fmt.signed(full.net)],
        ["PF", fmt.num(full.pf)], ["WR%", fmt.pct(full.wr)],
        ["Payoff", fmt.num(full.payoff)], ["MaxDD", fmt.num(full.maxdd)],
        ["Sharpe", fmt.num(full.sharpe)], ["Fecha", full.fecha_corrida || "--"],
      ];
      const grid = metricsRows.map(([k, v]) => (
        `<div class="runs-drawer-metric"><span class="runs-drawer-metric-label">${escapeHtml(k)}</span>` +
        `<span class="runs-drawer-metric-value mono">${escapeHtml(String(v))}</span></div>`
      )).join("");

      const artifacts = full.artifacts || {};
      const reportPath = artifacts.report_path || full.report_path;
      let evidenceHtml = "";
      if (reportPath) {
        const normalized = String(reportPath).replace(/\\/g, "/");
        const href = /^[a-zA-Z]:\//.test(normalized) ? `file:///${normalized}` : `file:///${normalized}`;
        evidenceHtml = `<a class="runs-drawer-evidence" href="${escapeHtml(href)}" target="_blank" rel="noopener">Ver evidencia (.htm) &#8599;</a>`;
      }

      body.innerHTML = `
        <div class="runs-drawer-grid">${grid}</div>
        ${evidenceHtml}
        <button type="button" class="runs-drawer-review-btn">Ver trades &rarr; REVIEW</button>`;
      body.querySelector(".runs-drawer-review-btn").addEventListener("click", () => {
        window.SENTINEL.appState = window.SENTINEL.appState || {};
        window.SENTINEL.appState.selectedRun = full.run_id;
        const reviewBtn = document.querySelector('.nav-btn[data-section="review"]');
        if (reviewBtn) reviewBtn.click();
      });
    }).catch(() => {
      const body = drawer.querySelector(".runs-drawer-body");
      body.innerHTML = '<div class="runs-drawer-error">Error cargando el run.</div>';
    });
  }

  function closeDrawer() {
    const overlay = document.querySelector(".runs-drawer-overlay");
    if (overlay) overlay.remove();
  }

  // ---- compare modal (uPlot) ----
  function openCompareModal(selectedRows) {
    const overlay = el("div", { class: "runs-compare-overlay" });
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
    const modal = el("div", { class: "runs-compare-modal" });
    modal.innerHTML = `
      <div class="runs-compare-header">
        <h3>Comparar corridas</h3>
        <button type="button" class="runs-compare-close">&times;</button>
      </div>
      <div class="runs-compare-legend"></div>
      <div class="runs-compare-chart"></div>`;
    modal.querySelector(".runs-compare-close").addEventListener("click", () => overlay.remove());
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const legend = modal.querySelector(".runs-compare-legend");
    const chartEl = modal.querySelector(".runs-compare-chart");
    const badge = window.SENTINEL.badge;

    selectedRows.forEach((row, i) => {
      const dashLabel = i === 0 ? "solid" : i === 1 ? "dashed" : "dotted";
      const chip = el("div", { class: "runs-compare-legend-item" });
      chip.innerHTML = `${runBadgeHtml(row)} <span class="runs-compare-dash-label">(${dashLabel})</span>`;
      legend.appendChild(chip);
    });

    const hasEquity = selectedRows.some((r) => r.equity_path);
    if (hasEquity && typeof uPlot !== "undefined") {
      // Equity curves are not fetched from a dedicated endpoint in M2.1 (no
      // contract for it in D.6); fall back to comparative bars whenever we
      // cannot resolve series data client-side. This keeps the modal honest
      // rather than fabricating a curve.
      renderCompareBars(chartEl, selectedRows, badge);
    } else {
      renderCompareBars(chartEl, selectedRows, badge);
    }
  }

  function renderCompareBars(chartEl, rows, badge) {
    if (typeof uPlot === "undefined") {
      chartEl.textContent = "uPlot no disponible.";
      return;
    }
    const metrics = ["net", "pf", "wr", "maxdd"];
    const labels = ["Net", "PF", "WR%", "MaxDD"];
    const xs = metrics.map((_, i) => i);
    const series = [{}];
    const data = [xs];
    rows.forEach((row, idx) => {
      data.push(metrics.map((m) => Number(row[m]) || 0));
      series.push({
        label: row.display_name || row.variant_id,
        stroke: badge.colorForIdx(row.color_idx),
        width: 2,
        dash: DASH_PATTERNS[idx % DASH_PATTERNS.length],
        points: { show: true },
      });
    });
    const opts = {
      width: chartEl.clientWidth || 640,
      height: 320,
      series,
      axes: [{ values: (u, vals) => vals.map((v) => labels[v] || "") }, {}],
      scales: { x: { time: false } },
    };
    // eslint-disable-next-line no-undef
    new uPlot(opts, data, chartEl);
  }

  // ---- states ----
  function renderLoading(container) {
    container.innerHTML = '<div class="runs-skeleton">Cargando corridas&hellip;</div>';
  }
  function renderError(container, onRetry) {
    container.innerHTML = "";
    const box = el("div", { class: "runs-error" }, [
      el("p", { text: "Error cargando corridas." }),
      el("button", { type: "button", text: "Reintentar" }),
    ]);
    box.querySelector("button").addEventListener("click", onRetry);
    container.appendChild(box);
  }

  // ---- main render ----
  function render(el0) {
    el0.innerHTML = "";
    const root = el("div", { class: "runs-section" });
    el0.appendChild(root);

    const filterBarHost = el("div", { class: "runs-filterbar-host" });
    const tableHost = el("div", { class: "runs-table-host" });
    const compareBarHost = el("div", { class: "runs-compare-bar", hidden: "hidden" }, [
      el("span", { class: "runs-compare-count", text: "0 seleccionadas (max 6)" }),
      el("button", { type: "button", class: "runs-compare-btn", text: "Comparar" }),
    ]);

    root.appendChild(filterBarHost);
    root.appendChild(compareBarHost);
    root.appendChild(tableHost);

    let vt = null;
    let currentFilters = { order_by: "fecha_corrida", dir: "desc" };
    let strategiesById = {};

    async function loadStrategiesAndBar() {
      try {
        const body = await fetchStrategies();
        strategiesById = {};
        (body.strategies || []).forEach((s) => { strategiesById[s.strategy_id] = s; });
        renderFilterBar(filterBarHost, body.strategies || [], (patch) => {
          Object.assign(currentFilters, patch);
          loadRuns();
        });
      } catch (e) {
        // filters still usable without strategy chips; runs table load will
        // surface its own error/toast.
      }
    }

    async function loadRuns() {
      renderLoading(tableHost);
      let body;
      try {
        body = await fetchRuns(currentFilters);
      } catch (e) {
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/runs", { type: "error" });
        renderError(tableHost, loadRuns);
        return;
      }
      const rows = body.rows || [];
      tableHost.innerHTML = "";
      if (!rows.length) {
        tableHost.innerHTML = '<div class="runs-empty">Sin corridas para los filtros</div>';
        updateCompareBar([]);
        return;
      }
      const tableEl = el("div", { class: "runs-vtable" });
      tableHost.appendChild(tableEl);
      vt = window.SENTINEL.vtable.createVTable(tableEl, {
        columns: buildColumns(),
        rows,
        rowKey: (r) => r.run_id,
        selectable: true,
        maxSelected: 6,
        initialSort: { key: currentFilters.order_by || "fecha_corrida", dir: currentFilters.dir || "desc" },
        onRowClick: (row) => openDrawer(row),
        onSelectionChange: (keys) => updateCompareBar(keys, rows),
      });
    }

    function updateCompareBar(keys, rows) {
      const countEl = compareBarHost.querySelector(".runs-compare-count");
      countEl.textContent = `${keys.length} seleccionadas (max 6)`;
      compareBarHost.hidden = keys.length === 0;
      const btn = compareBarHost.querySelector(".runs-compare-btn");
      btn.onclick = () => {
        if (!rows) return;
        const selectedRows = rows.filter((r) => keys.includes(r.run_id));
        if (selectedRows.length) openCompareModal(selectedRows);
      };
    }

    loadStrategiesAndBar();
    loadRuns();

    state = { root, vt: () => vt };
  }

  function teardown() {
    closeDrawer();
    const compareOverlay = document.querySelector(".runs-compare-overlay");
    if (compareOverlay) compareOverlay.remove();
    if (state && state.root) state.root.innerHTML = "";
    state = null;
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.runs = { render, teardown };
})();
