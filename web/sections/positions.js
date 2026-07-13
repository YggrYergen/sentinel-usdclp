// SENTINEL sections/positions.js — POSICIONES section (Task M2.3, plan
// §D.7-POSICIONES NORMATIVE). Tabs HUMANO · ESTRATEGIA · IA (taxonomy is
// first-class: all 3 tabs exist even though HUMANO/IA have no data until
// B4/B5). ESTRATEGIA tab lists forward_session cards; click a card ->
// its trades table (same columns as REVIEW) + "Ver en chart -> REVIEW"
// button that hands off appState.selectedRun and switches section.
// "Re-importar TOKATA" button -> POST /api/ingest/tokata, refresh + toast.
// Classic script (no ES modules), hangs off window.SENTINEL.sections.positions.
(function () {
  "use strict";

  let state = null; // per-mount state, rebuilt on render()

  const TABS = [
    { id: "humano", label: "HUMANO" },
    { id: "estrategia", label: "ESTRATEGIA" },
    { id: "ia", label: "IA" },
  ];

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

  function exitReasonAbbrev(reason) {
    if (!reason) return "--";
    const s = String(reason).trim();
    if (s.length <= 4) return s.toUpperCase();
    return s.slice(0, 4).toUpperCase();
  }

  function epochOf(v) {
    if (v === null || v === undefined) return null;
    if (typeof v === "number") return v > 1e12 ? v / 1000 : v;
    const d = new Date(v);
    return d.getTime() / 1000;
  }

  const ESTADOS = ["activa", "pausada", "graduada"];

  // ---- data fetch (D.6 contracts) ----
  async function fetchSessions() {
    const resp = await fetch("/api/forward/sessions");
    if (!resp.ok) throw new Error(`GET /api/forward/sessions failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchStrategies() {
    const resp = await fetch("/api/strategies");
    if (!resp.ok) throw new Error(`GET /api/strategies failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchScorecard(strategyId) {
    const resp = await fetch(`/api/strategies/${encodeURIComponent(strategyId)}/scorecard`);
    if (!resp.ok) throw new Error(`GET /api/strategies/${strategyId}/scorecard failed: ${resp.status}`);
    return resp.json();
  }

  async function postEstado(strategyId, estado) {
    const resp = await fetch(`/api/strategies/${encodeURIComponent(strategyId)}/estado`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ estado }),
    });
    const json = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const msg = (json && json.error && json.error.message) || `POST estado failed: ${resp.status}`;
      throw new Error(msg);
    }
    return json;
  }

  // ---- Task B4: two-floor (real/teorico) scorecard CSS, section-scoped. ----
  const ESTRATEGIA_CSS_ID = "positions-estrategia-css";
  const ESTRATEGIA_CSS = `
    .estrategia-tf-badge { display: inline-block; font-size: 0.7rem; padding: 1px 6px; border: 1px solid var(--border, #333); border-radius: 3px; opacity: 0.85; margin-left: 6px; }
    .estrategia-scorecard { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
    .estrategia-floor { display: flex; justify-content: space-between; gap: 8px; padding: 2px 4px; font-size: 0.78rem; }
    .estrategia-floor-real { font-weight: 700; opacity: 1; }
    .estrategia-floor-teorico { font-weight: 400; opacity: 0.55; }
    .estrategia-floor-label { text-transform: uppercase; font-size: 0.62rem; opacity: 0.7; }
  `;

  function injectEstrategiaCss() {
    if (document.getElementById(ESTRATEGIA_CSS_ID)) return;
    const style = document.createElement("style");
    style.id = ESTRATEGIA_CSS_ID;
    style.textContent = ESTRATEGIA_CSS;
    document.head.appendChild(style);
  }

  function scorecardFloorText(block) {
    if (!block) return "sin baseline";
    const fmt = window.SENTINEL.fmt;
    const net = block.net != null ? fmt.signed(block.net) : "--";
    const trades = block.trades != null ? block.trades : "--";
    const pf = block.pf != null ? fmt.num(block.pf) : "--";
    return `${net} · ${trades} trades · PF ${pf}`;
  }

  function renderScorecardFloors(host, card) {
    injectEstrategiaCss();
    host.innerHTML = "";
    const wrap = el("div", { class: "estrategia-scorecard" });
    const real = el("div", { class: "estrategia-floor estrategia-floor-real" });
    real.innerHTML = `<span class="estrategia-floor-label">Real</span><span>Cargando&hellip;</span>`;
    const teorico = el("div", { class: "estrategia-floor estrategia-floor-teorico" });
    teorico.innerHTML = `<span class="estrategia-floor-label">Te&oacute;rico</span><span>Cargando&hellip;</span>`;
    wrap.appendChild(real);
    wrap.appendChild(teorico);
    host.appendChild(wrap);

    fetchScorecard(card.strategy_id).then((data) => {
      const floors = data.floors || {};
      real.innerHTML = `<span class="estrategia-floor-label">Real</span><span>${escapeHtml(scorecardFloorText(floors.real))}</span>`;
      teorico.innerHTML = `<span class="estrategia-floor-label">Te&oacute;rico</span><span>${escapeHtml(scorecardFloorText(floors.teorico))}</span>`;
    }).catch(() => {
      real.innerHTML = `<span class="estrategia-floor-label">Real</span><span>Error cargando scorecard.</span>`;
      teorico.innerHTML = `<span class="estrategia-floor-label">Te&oacute;rico</span><span>sin baseline</span>`;
    });
  }

  // ---- strategy state panel (M2.7): per-strategy activa/pausada/graduada
  // segmented control + state badge next to the strategy badge. Graduated
  // strategies list first, marked with a star (plan Task M2.7). ----
  function sortStrategiesGraduatedFirst(strategies) {
    return strategies.slice().sort((a, b) => {
      const ga = a.graduated ? 1 : 0;
      const gb = b.graduated ? 1 : 0;
      if (ga !== gb) return gb - ga;
      return (a.name || "").localeCompare(b.name || "");
    });
  }

  function renderStrategyStateCard(strategy, onChanged) {
    const badge = window.SENTINEL.badge;
    const estado = strategy.estado || "activa";
    const card = el("div", { class: "manage-strategy-card" });
    const stratBadge = badge.strategyBadge({
      familia: strategy.familia,
      name: strategy.familia && strategy.familia.toLowerCase() === (strategy.name || "").toLowerCase() ? "" : strategy.name,
      color_idx: strategy.color_idx,
      display_name: strategy.name,
    });
    const starHtml = strategy.graduated ? '<span class="manage-graduated-star" title="Graduada">&#9733;</span>' : "";
    const tfHtml = strategy.tf ? `<span class="estrategia-tf-badge">${escapeHtml(strategy.tf)}</span>` : "";
    card.innerHTML = `
      <div class="manage-strategy-card-top">${starHtml}${stratBadge}${tfHtml}
        <span class="manage-estado-badge manage-estado-${escapeHtml(estado)}">${escapeHtml(estado)}</span>
      </div>
      <div class="estrategia-scorecard-host"></div>
      <div class="manage-estado-controls"></div>`;
    const scorecardHost = card.querySelector(".estrategia-scorecard-host");
    renderScorecardFloors(scorecardHost, strategy);
    const controls = card.querySelector(".manage-estado-controls");
    ESTADOS.forEach((e) => {
      const btn = el("button", {
        type: "button",
        class: `manage-estado-btn${e === estado ? " active" : ""}`,
      });
      btn.textContent = e;
      btn.addEventListener("click", async () => {
        if (btn.disabled || e === estado) return;
        controls.querySelectorAll("button").forEach((b) => { b.disabled = true; });
        try {
          await postEstado(strategy.strategy_id, e);
          if (window.SENTINEL.toast) {
            window.SENTINEL.toast.show(`${strategy.name}: estado -> ${e}`, { type: "success" });
          }
          if (onChanged) onChanged();
        } catch (err) {
          if (window.SENTINEL.toast) {
            window.SENTINEL.toast.show(`Error cambiando estado: ${err.message}`, { type: "error" });
          }
          controls.querySelectorAll("button").forEach((b) => { b.disabled = false; });
        }
      });
      controls.appendChild(btn);
    });
    return card;
  }

  async function fetchSessionTrades(sessionId) {
    const resp = await fetch(`/api/forward/${encodeURIComponent(sessionId)}/trades`);
    if (!resp.ok) throw new Error(`GET /api/forward/${sessionId}/trades failed: ${resp.status}`);
    return resp.json();
  }

  async function postReimportTokata() {
    const resp = await fetch("/api/ingest/tokata", { method: "POST" });
    if (!resp.ok) throw new Error(`POST /api/ingest/tokata failed: ${resp.status}`);
    return resp.json();
  }

  // ---- C5: reusable SSE-over-fetch consumer (EventSource does not support
  // POST bodies, so the AI analysis stream is consumed manually via fetch +
  // ReadableStream reader). Parses `event:`/`data:` lines per the SSE wire
  // format (blank line terminates each event). Caller passes onEvent(name,
  // dataText) and gets back { abort } for REV-5-pattern teardown; caller may
  // also pass an external AbortController via opts.signal. C7b reuses this
  // helper verbatim for its own SSE endpoint. ----
  function consumeSseStream(url, body, opts) {
    const options = opts || {};
    const controller = new AbortController();
    const signal = controller.signal;
    const onEvent = options.onEvent || function () {};

    async function run() {
      let resp;
      try {
        resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body || {}),
          signal,
        });
      } catch (e) {
        if (signal.aborted) return;
        onEvent("ai_error", JSON.stringify({ message: e.message || String(e) }));
        return;
      }
      if (!resp.ok || !resp.body) {
        onEvent("ai_error", JSON.stringify({ message: `stream failed: ${resp.status}` }));
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buf = "";
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf("\n\n")) !== -1) {
            const rawEvent = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            let eventName = "message";
            let dataText = "";
            rawEvent.split("\n").forEach((line) => {
              if (line.startsWith("event:")) eventName = line.slice(6).trim();
              else if (line.startsWith("data:")) dataText += line.slice(5).trim();
            });
            onEvent(eventName, dataText);
          }
        }
      } catch (e) {
        if (!signal.aborted) onEvent("ai_error", JSON.stringify({ message: e.message || String(e) }));
      } finally {
        try { reader.releaseLock(); } catch (e) { /* noop */ }
      }
    }

    run();
    return { abort: () => controller.abort() };
  }

  // ---- trades table columns (same as REVIEW) ----
  function tradeRowColumns() {
    const fmt = window.SENTINEL.fmt;
    return [
      { key: "n", label: "#", width: "34px", render: (r) => `<span class="mono">${r.__n}</span>` },
      { key: "side", label: "Lado", width: "56px",
        render: (r) => `<span class="${(r.side || "").toUpperCase() === "LONG" ? "sentinel-sign-pos" : "sentinel-sign-neg"}">${escapeHtml(r.side || "--")}</span>` },
      { key: "ts_in", label: "Entrada", width: "1fr", render: (r) => `<span class="mono">${fmt.tsShort(epochOf(r.ts_in))}</span>` },
      { key: "pnl", label: "PnL", width: "80px", numeric: true,
        render: (r) => `<span class="${signClass(r.pnl)} mono">${fmt.signed(r.pnl)}</span>` },
      { key: "exit_reason", label: "Exit", width: "56px",
        render: (r) => `<span class="mono" title="${escapeHtml(r.exit_reason || "")}">${escapeHtml(exitReasonAbbrev(r.exit_reason))}</span>` },
    ];
  }

  // ---- session card ----
  function renderSessionCard(session) {
    const badge = window.SENTINEL.badge;
    const fmt = window.SENTINEL.fmt;
    const card = el("button", {
      type: "button",
      class: "positions-session-card",
      "data-session-id": session.session_id,
      title: session.display_name || session.session_id,
    });
    const stratBadge = badge.strategyBadge({
      familia: "", // display_name already carries familia · nombre
      name: session.display_name || session.session_id,
      color_idx: session.color_idx,
      display_name: session.display_name || session.session_id,
    });
    card.innerHTML = `
      <div class="positions-card-top">${stratBadge}</div>
      <div class="positions-card-row mono">
        <span class="positions-card-perfil">${escapeHtml(session.perfil || "--")}</span>
        <span class="positions-card-estado">${escapeHtml(session.estado || "--")}</span>
      </div>
      <div class="positions-card-row mono">
        <span class="positions-card-pnl ${signClass(session.pnl_total)}">${fmt.signed(session.pnl_total)}</span>
        <span class="positions-card-ntrades">${session.n_trades != null ? session.n_trades : "--"} trades</span>
      </div>`;
    return card;
  }

  // ---- IA tab (Task B5): TOP = client-side aggregated card over
  // GET /api/positions?origin=ia (net total, #posiciones, lots — no
  // dedicated scorecard endpoint exists for origin=ia; B2 only covers
  // strategy_id scorecards, so this aggregate is computed in the client).
  // BOTTOM = reuses renderHumanoTab(host, "ia") verbatim (no second
  // copy-pasted list builder). ----
  const IA_CSS_ID = "positions-ia-css";
  const IA_CSS = `
    .positions-ia-aggregate { display: flex; gap: 24px; align-items: center; padding: 14px 16px; margin-bottom: 10px; border: 1px solid var(--border, #333); border-radius: 6px; }
    .positions-ia-aggregate-stat { display: flex; flex-direction: column; gap: 2px; }
    .positions-ia-aggregate-label { font-size: 0.68rem; text-transform: uppercase; opacity: 0.65; }
    .positions-ia-aggregate-value { font-size: 1.25rem; font-weight: 700; }
    .positions-ia-list-host { flex: 1; min-height: 0; }
  `;

  function injectIaCss() {
    if (document.getElementById(IA_CSS_ID)) return;
    const style = document.createElement("style");
    style.id = IA_CSS_ID;
    style.textContent = IA_CSS;
    document.head.appendChild(style);
  }

  function aggregateIaGroups(groups) {
    let net = 0;
    let lots = 0;
    groups.forEach((g) => {
      net += Number(g.net) || 0;
      lots += Number(g.lots) || 0;
    });
    return { net, count: groups.length, lots };
  }

  function renderIaAggregateCard(host, groups) {
    injectIaCss();
    const fmt = window.SENTINEL.fmt;
    const agg = aggregateIaGroups(groups);
    const card = el("div", { class: "positions-ia-aggregate" });
    card.innerHTML = `
      <div class="positions-ia-aggregate-stat">
        <span class="positions-ia-aggregate-label">Net total</span>
        <span class="positions-ia-aggregate-value ${signClass(agg.net)} mono">${fmt.signed(agg.net)}</span>
      </div>
      <div class="positions-ia-aggregate-stat">
        <span class="positions-ia-aggregate-label">Posiciones</span>
        <span class="positions-ia-aggregate-value mono">${agg.count}</span>
      </div>
      <div class="positions-ia-aggregate-stat">
        <span class="positions-ia-aggregate-label">Lots</span>
        <span class="positions-ia-aggregate-value mono">${fmt.num(agg.lots)}</span>
      </div>`;
    host.innerHTML = "";
    host.appendChild(card);
  }

  function renderIaTab(host) {
    injectIaCss();
    host.innerHTML = '<div class="positions-loading">Cargando posiciones IA&hellip;</div>';
    let innerHandle = null;
    let torn = false;
    fetchPositions("ia", "").then((body) => {
      if (torn) return;
      const groups = body.groups || [];
      host.innerHTML = "";
      const aggHost = el("div", {});
      const listHost = el("div", { class: "positions-ia-list-host" });
      host.appendChild(aggHost);
      host.appendChild(listHost);
      renderIaAggregateCard(aggHost, groups);
      innerHandle = renderHumanoTab(listHost, "ia");
    }).catch(() => {
      if (torn) return;
      host.innerHTML = '<div class="positions-error">Error cargando /api/positions.</div>';
      if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/positions", { type: "error" });
    });
    return {
      teardown: () => {
        torn = true;
        if (innerHandle) { try { innerHandle.teardown(); } catch (e) { /* noop */ } innerHandle = null; }
      },
    };
  }

  // ---- HUMANO tab (Task B3a): card list of GET /api/positions?origin=human
  // groups, virtualized via window.SENTINEL.vlist. Multi-lote groups render
  // a group card with a chevron that expands/collapses its children inline
  // (flattened into the vlist items array on toggle -- vlist itemHeight is
  // fixed, so "expand" = insert child rows into the flat list, not a nested
  // sub-list). Part 2 (B3b: expanded detail panel + replay) is NOT built
  // here; onPositionSelect is a documented no-op hook for B3b to replace. ----

  const HUMANO_CSS_ID = "positions-humano-css";
  const HUMANO_CSS = `
    .positions-humano-card { display: grid; grid-template-columns: 20px 1fr 1fr 90px 70px 60px 60px 60px; gap: 8px; align-items: center; padding: 6px 10px; box-sizing: border-box; cursor: pointer; border-bottom: 1px solid var(--border, #333); }
    .positions-humano-card.vlist-selected { background: var(--accent-select-bg, rgba(80,140,255,0.15)); }
    .positions-humano-chevron { display: inline-block; transition: transform 0.1s ease; cursor: pointer; }
    .positions-humano-chevron.open { transform: rotate(90deg); }
    .positions-humano-child-row { display: grid; grid-template-columns: 20px 1fr 1fr 90px 70px; gap: 8px; padding: 4px 10px 4px 30px; opacity: 0.85; }
    .positions-humano-empty { padding: 16px; opacity: 0.7; }
    .positions-humano-panel { display: flex; flex-direction: column; border-top: 1px solid var(--border, #333); padding: 10px; box-sizing: border-box; gap: 10px; }
    .positions-humano-panel-header { display: flex; justify-content: space-between; align-items: center; }
    .positions-humano-panel-close { cursor: pointer; background: none; border: none; font-size: 18px; opacity: 0.7; }
    .positions-humano-panel-close:hover { opacity: 1; }
    .positions-humano-panel-chart { height: 320px; width: 100%; }
    .positions-humano-panel-detail { width: 100%; }
    .positions-humano-panel-detail table { width: 100%; border-collapse: collapse; }
    .positions-humano-panel-detail td, .positions-humano-panel-detail th { padding: 3px 8px; text-align: left; border-bottom: 1px solid var(--border, #333); }
    .positions-humano-panel-actions { display: flex; justify-content: flex-end; gap: 8px; }
    .positions-humano-panel-actions button { cursor: pointer; }
    .positions-humano-panel-actions button:disabled { cursor: not-allowed; opacity: 0.5; }
    .positions-humano-panel-ai { display: none; white-space: pre-wrap; padding: 8px; border: 1px solid var(--border, #333); border-radius: 4px; max-height: 220px; overflow: auto; font-size: 0.82rem; }
    .positions-humano-panel-ai.active { display: block; }
    .positions-humano-panel-ai.error { color: var(--sentinel-sign-neg, #e05555); }
  `;

  function injectHumanoCss() {
    if (document.getElementById(HUMANO_CSS_ID)) return;
    const style = document.createElement("style");
    style.id = HUMANO_CSS_ID;
    style.textContent = HUMANO_CSS;
    document.head.appendChild(style);
  }

  function fmtOrDash(fmt, value, kind) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
    if (kind === "pct") return fmt.pct(value);
    if (kind === "price") return fmt.price(value);
    return fmt.num(value);
  }

  async function fetchPositions(origin, symbol) {
    const params = new URLSearchParams();
    if (origin) params.set("origin", origin);
    if (symbol) params.set("symbol", symbol);
    params.set("limit", "200");
    const resp = await fetch(`/api/positions?${params.toString()}`);
    if (!resp.ok) throw new Error(`GET /api/positions failed: ${resp.status}`);
    return resp.json();
  }

  // Task B3b: expanded detail panel + replay. Replaces the B3a no-op hook.
  // fields covering all child/group columns + fills (Analizar is disabled
  // until C5). Degrades clean if adapters.js/chart.js are not on the page
  // (window.SENTINEL.adapters && / window.SENTINEL.chart && guards).
  const DEFAULT_TF = "M5";
  const PANEL_TF_SEC = { M1: 60, M2: 120, M5: 300, M10: 600, M15: 900, H1: 3600, D: 86400 };

  function positionEntryExit(selection) {
    const group = selection.group || {};
    const child = selection.kind === "child" ? selection.child : (group.children || [])[0] || {};
    const tIn = epochOf(child.ts_in != null ? child.ts_in : group.first_in);
    const tOut = epochOf(child.ts_out != null ? child.ts_out : group.last_out);
    return { child, tIn, tOut };
  }

  function renderDetailTable(host, selection) {
    const group = selection.group || {};
    const child = selection.kind === "child" ? selection.child : (group.children || [])[0] || {};
    const fills = child.fills || group.fills || [];
    const rows = [];
    Object.keys(group).forEach((k) => {
      if (k === "children") return;
      rows.push([`group.${k}`, group[k]]);
    });
    Object.keys(child).forEach((k) => {
      if (k === "fills") return;
      rows.push([k, child[k]]);
    });
    const fillsHtml = fills.length
      ? `<h4>Fills</h4><table>${fills.map((f, i) => `<tr><td>#${i + 1}</td><td>${escapeHtml(JSON.stringify(f))}</td></tr>`).join("")}</table>`
      : "";
    host.innerHTML = `<table>${rows.map(([k, v]) => `<tr><td class="mono">${escapeHtml(k)}</td><td class="mono">${escapeHtml(v === null || v === undefined ? "--" : String(v))}</td></tr>`).join("")}</table>${fillsHtml}`;
  }

  function buildHumanoDetailPanel(container, selection, onClose) {
    injectHumanoCss();
    const panel = el("div", { class: "positions-humano-panel" });
    const header = el("div", { class: "positions-humano-panel-header" });
    header.innerHTML = `<strong>Detalle posici&oacute;n</strong>`;
    const closeBtn = el("button", { type: "button", class: "positions-humano-panel-close", title: "Cerrar" });
    closeBtn.textContent = "×";
    header.appendChild(closeBtn);
    panel.appendChild(header);

    const chartHost = el("div", { class: "positions-humano-panel-chart" });
    panel.appendChild(chartHost);

    const detailHost = el("div", { class: "positions-humano-panel-detail" });
    panel.appendChild(detailHost);
    renderDetailTable(detailHost, selection);

    const actions = el("div", { class: "positions-humano-panel-actions" });
    const replayBtn = el("button", { type: "button", class: "positions-humano-replay-btn" });
    replayBtn.textContent = "Replay";
    const analizarBtn = el("button", {
      type: "button",
      class: "positions-humano-analizar-btn",
      title: "Análisis IA",
    });
    analizarBtn.textContent = "Analizar";
    actions.appendChild(replayBtn);
    actions.appendChild(analizarBtn);
    panel.appendChild(actions);

    const aiPanel = el("div", { class: "positions-humano-panel-ai" });
    panel.appendChild(aiPanel);

    let aiStream = null;

    function aiEventHandler(name, dataText) {
      if (name === "ai_text") {
        let chunk = "";
        try { chunk = JSON.parse(dataText).chunk || JSON.parse(dataText).text || ""; } catch (e) { chunk = dataText; }
        aiPanel.classList.remove("error");
        aiPanel.classList.add("active");
        aiPanel.textContent += chunk;
      } else if (name === "ai_done") {
        analizarBtn.disabled = false;
        aiStream = null;
      } else if (name === "ai_error") {
        let msg = dataText;
        try { msg = JSON.parse(dataText).message || dataText; } catch (e) { /* keep raw */ }
        aiPanel.classList.add("active", "error");
        aiPanel.textContent = `Error: ${msg}`;
        analizarBtn.disabled = false;
        aiStream = null;
      }
    }

    analizarBtn.addEventListener("click", () => {
      if (analizarBtn.disabled || aiStream) return;
      const { child: aiChild } = positionEntryExit(selection);
      const tradeId = aiChild.position_id != null ? aiChild.position_id : aiChild.trade_id;
      analizarBtn.disabled = true;
      aiPanel.classList.remove("error");
      aiPanel.classList.add("active");
      aiPanel.textContent = "";
      aiStream = consumeSseStream("/api/ai/analyze_position", { trade_id: tradeId }, { onEvent: aiEventHandler });
    });

    const { child, tIn, tOut } = positionEntryExit(selection);
    const tf = DEFAULT_TF;
    const tfSec = PANEL_TF_SEC[tf] || 300;

    let chartInst = null;
    let histAdapter = null;
    let panelBarSource = null;
    const symbol = (selection.group && selection.group.symbol) || "";
    if (window.SENTINEL.chart && window.SENTINEL.adapters) {
      chartInst = window.SENTINEL.chart.create(chartHost, { symbol, tf });
      if (chartInst && window.SENTINEL.chartData && window.SENTINEL.chartData.createBarSource && window.SENTINEL.adapters.HistAdapter) {
        panelBarSource = window.SENTINEL.chartData.createBarSource({ symbol, tf });
        histAdapter = window.SENTINEL.adapters.HistAdapter(chartInst, panelBarSource);
      }
      if (histAdapter && tIn != null && tOut != null) {
        histAdapter.ensureWindow(tIn - 30 * tfSec, tOut + 30 * tfSec).then(() => {
          histAdapter.setSignals([{
            signal_id: child.position_id,
            side: child.side,
            ts_in: tIn,
            px_in: child.px_in,
            ts_out: tOut,
            px_out: child.px_out,
          }]);
        }).catch(() => { /* noop: chart degrades to empty */ });
      }
    } else {
      chartHost.innerHTML = '<div class="positions-panel-chart-unavailable">Chart no disponible.</div>';
    }

    replayBtn.addEventListener("click", () => {
      if (!window.SENTINEL.adapters || !window.SENTINEL.adapters.ReplayAdapter || !chartInst || !panelBarSource) return;
      if (tIn == null || tOut == null) return;
      const replayArgs = {
        fromT: tIn - 4 * tfSec,
        toT: tOut + 4 * tfSec,
        pauseAfterBars: 4,
      };
      const replay = window.SENTINEL.adapters.ReplayAdapter(chartInst, panelBarSource, replayArgs);
      replay.prime().then(() => replay.play());
    });

    function escHandler(evt) {
      if (evt.key === "Escape") closePanel();
    }
    document.addEventListener("keydown", escHandler);

    function closePanel() {
      document.removeEventListener("keydown", escHandler);
      if (aiStream) { try { aiStream.abort(); } catch (e) { /* noop */ } aiStream = null; }
      if (chartInst) { try { chartInst.destroy(); } catch (e) { /* noop */ } }
      container.innerHTML = "";
      if (onClose) onClose();
    }

    closeBtn.addEventListener("click", closePanel);

    container.innerHTML = "";
    container.appendChild(panel);

    return { teardown: closePanel };
  }

  function buildHumanoFlatItems(groups, expandedIds) {
    const items = [];
    groups.forEach((group) => {
      const isMulti = (group.children || []).length > 1;
      items.push({ kind: "group", group, isMulti, expanded: isMulti && expandedIds.has(group.group_id) });
      if (isMulti && expandedIds.has(group.group_id)) {
        (group.children || []).forEach((child) => {
          items.push({ kind: "child", group, child });
        });
      }
    });
    return items;
  }

  // VWAP over a group's children for a given price field, ignoring children
  // whose value/volume is missing. Returns null if no valid children.
  function vwapOf(children, priceKey) {
    let sumPV = 0;
    let sumV = 0;
    (children || []).forEach((c) => {
      const price = c[priceKey];
      const volume = Number(c.volume);
      if (price === null || price === undefined || Number.isNaN(Number(price))) return;
      if (!volume || Number.isNaN(volume)) return;
      sumPV += Number(price) * volume;
      sumV += volume;
    });
    if (sumV === 0) return null;
    return sumPV / sumV;
  }

  function renderHumanoGroupCard(item, fmt, expandedIds, onToggle, onSelect) {
    const group = item.group;
    const children = group.children || [];
    const child = children[0] || {};
    const isMulti = children.length > 1;
    const card = el("div", {
      class: "positions-humano-card",
      "data-group-id": group.group_id,
    });
    const chevronHtml = item.isMulti
      ? `<span class="positions-humano-chevron${item.expanded ? " open" : ""}" data-chevron="1">&#9656;</span>`
      : `<span></span>`;
    const tsIn = fmt.tsShort(epochOf(group.first_in));
    const tsOut = fmt.tsShort(epochOf(group.last_out));
    // Multi-lote groups: px_in/px_out are VWAP across children (a single
    // child's fill is not representative of the group). pct/mae/mfe have no
    // defined group-level aggregation yet, so they show "--" rather than
    // borrowing one child's value.
    const pxInVal = isMulti ? vwapOf(children, "px_in") : child.px_in;
    const pxOutVal = isMulti ? vwapOf(children, "px_out") : child.px_out;
    const pxIn = pxInVal != null ? fmtOrDash(fmt, pxInVal, "price") : "--";
    const pxOut = pxOutVal != null ? fmtOrDash(fmt, pxOutVal, "price") : "--";
    const pnl = group.net;
    const pct = isMulti ? "--" : fmtOrDash(fmt, child.pct, "pct");
    const mae = isMulti ? "--" : fmtOrDash(fmt, child.mae);
    const mfe = isMulti ? "--" : fmtOrDash(fmt, child.mfe);
    card.innerHTML = `
      ${chevronHtml}
      <span class="mono">${escapeHtml(group.symbol || "--")}</span>
      <span class="mono">${tsIn} &rarr; ${tsOut}</span>
      <span class="mono">${pxIn} / ${pxOut}</span>
      <span class="mono ${signClass(pnl)}">${fmt.signed(pnl)}</span>
      <span class="mono">${pct}</span>
      <span class="mono">${mae}</span>
      <span class="mono">${mfe}</span>`;
    const chevronEl = card.querySelector("[data-chevron]");
    if (chevronEl) {
      chevronEl.addEventListener("click", (ev) => {
        ev.stopPropagation();
        onToggle(group.group_id);
      });
    }
    card.addEventListener("click", () => {
      onSelect({ kind: "group", group });
      if (item.isMulti) onToggle(group.group_id);
    });
    return card;
  }

  function renderHumanoChildRow(item, fmt, onSelect) {
    const c = item.child;
    const row = el("div", {
      class: "positions-humano-card positions-humano-child-row",
      "data-position-id": c.position_id,
    });
    const tsIn = fmt.tsShort(epochOf(c.ts_in));
    const tsOut = fmt.tsShort(epochOf(c.ts_out));
    const pxIn = fmtOrDash(fmt, c.px_in, "price");
    const pxOut = fmtOrDash(fmt, c.px_out, "price");
    row.innerHTML = `
      <span></span>
      <span class="mono">${escapeHtml(String(c.position_id != null ? c.position_id : "--"))}</span>
      <span class="mono">${tsIn} &rarr; ${tsOut}</span>
      <span class="mono">${pxIn} / ${pxOut}</span>
      <span class="mono ${signClass(c.pnl)}">${fmt.signed(c.pnl)}</span>`;
    row.addEventListener("click", (ev) => {
      ev.stopPropagation();
      onSelect({ kind: "child", group: item.group, child: c });
    });
    return row;
  }

  function renderHumanoTab(host, origin) {
    const originArg = origin || "human";
    injectHumanoCss();
    host.innerHTML = '<div class="positions-loading">Cargando posiciones&hellip;</div>';

    const expandedIds = new Set();
    let groups = [];
    let selectedKey = null;
    let humanoVlist = null;
    let panelHandle = null;
    const panelHost = el("div", { class: "positions-humano-panel-host" });

    function itemKeyOf(item) {
      return item.kind === "group" ? `g:${item.group.group_id}` : `c:${item.child.position_id}`;
    }

    function refreshItems() {
      const items = buildHumanoFlatItems(groups, expandedIds);
      if (humanoVlist) {
        humanoVlist.setItems(items);
        humanoVlist.setSelected(selectedKey ? [selectedKey] : []);
      }
      return items;
    }

    function handleSelect(selection) {
      selectedKey = selection.kind === "group" ? `g:${selection.group.group_id}` : `c:${selection.child.position_id}`;
      window.SENTINEL.appState = window.SENTINEL.appState || {};
      window.SENTINEL.appState.selectedPosition = selection;
      if (humanoVlist) humanoVlist.setSelected([selectedKey]);
      if (panelHandle) { try { panelHandle.teardown(); } catch (e) { /* noop */ } panelHandle = null; }
      panelHandle = buildHumanoDetailPanel(panelHost, selection, () => { panelHandle = null; });
    }

    function handleToggle(groupId) {
      if (expandedIds.has(groupId)) expandedIds.delete(groupId);
      else expandedIds.add(groupId);
      refreshItems();
    }

    fetchPositions(originArg, "").then((body) => {
      groups = body.groups || [];
      host.innerHTML = "";
      if (!groups.length) {
        const emptyText = originArg === "ia" ? "Sin posiciones IA aún — se activa con el motor paper (Wave D)" : "Sin posiciones HUMANO.";
        host.innerHTML = `<div class="positions-humano-empty">${escapeHtml(emptyText)}</div>`;
        return;
      }
      const listHost = el("div", { class: "positions-humano-list" });
      listHost.style.height = "100%";
      listHost.style.overflow = "auto";
      host.appendChild(listHost);
      host.appendChild(panelHost);

      const fmt = window.SENTINEL.fmt;
      humanoVlist = window.SENTINEL.vlist.createVList(listHost, {
        itemHeight: 34,
        items: buildHumanoFlatItems(groups, expandedIds),
        itemKey: (item) => itemKeyOf(item),
        render: (item) => {
          if (item.kind === "group") {
            return renderHumanoGroupCard(item, fmt, expandedIds, handleToggle, handleSelect);
          }
          return renderHumanoChildRow(item, fmt, handleSelect);
        },
      });
    }).catch((e) => {
      host.innerHTML = '<div class="positions-error">Error cargando /api/positions.</div>';
      if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/positions", { type: "error" });
    });

    return {
      teardown: () => {
        if (humanoVlist) { try { humanoVlist.destroy(); } catch (e) { /* noop */ } }
        if (panelHandle) { try { panelHandle.teardown(); } catch (e) { /* noop */ } panelHandle = null; }
      },
    };
  }

  function renderEmptySessions(host) {
    host.innerHTML = '<div class="positions-empty">Sin sesiones forward</div>';
  }

  // ---- main render ----
  function render(mountEl) {
    mountEl.innerHTML = "";
    const root = el("div", { class: "positions-section" });

    const toolbar = el("div", { class: "positions-toolbar" });
    const tabsHost = el("div", { class: "positions-tabs" });
    const reimportBtn = el("button", {
      type: "button", class: "positions-reimport-btn",
    }, []);
    reimportBtn.textContent = "↻ Re-importar TOKATA";
    toolbar.appendChild(tabsHost);
    toolbar.appendChild(reimportBtn);

    const body = el("div", { class: "positions-body" });

    root.appendChild(toolbar);
    root.appendChild(body);
    mountEl.appendChild(root);

    const appState = (window.SENTINEL.appState = window.SENTINEL.appState || {});

    let activeTab = "estrategia";
    let sessions = [];
    let sessionsById = {};
    let selectedSessionId = null;
    let vt = null;
    let humanoTabHandle = null;

    function renderTabs() {
      tabsHost.innerHTML = "";
      TABS.forEach((tab) => {
        const btn = el("button", {
          type: "button",
          class: `positions-tab${tab.id === activeTab ? " active" : ""}`,
          "data-tab": tab.id,
        });
        btn.textContent = tab.label;
        btn.addEventListener("click", () => {
          if (activeTab === tab.id) return;
          activeTab = tab.id;
          renderTabs();
          renderBody();
        });
        tabsHost.appendChild(btn);
      });
    }

    function renderBody() {
      if (vt) { try { vt.destroy(); } catch (e) { /* noop */ } vt = null; }
      if (humanoTabHandle) { try { humanoTabHandle.teardown(); } catch (e) { /* noop */ } humanoTabHandle = null; }
      body.innerHTML = "";
      if (activeTab === "ia") {
        humanoTabHandle = renderIaTab(body);
        return;
      }
      if (activeTab === "humano") {
        humanoTabHandle = renderHumanoTab(body, "human");
        return;
      }
      renderEstrategiaTab();
    }

    function renderEstrategiaTab() {
      body.innerHTML = '<div class="positions-loading">Cargando sesiones forward&hellip;</div>';
      loadSessions();
    }

    async function loadSessions() {
      let strategies = [];
      try {
        const stratResp = await fetchStrategies();
        strategies = stratResp.strategies || [];
      } catch (e) {
        // Strategy state panel is additive; sessions can still render if
        // /api/strategies is unavailable.
      }

      try {
        const resp = await fetchSessions();
        sessions = resp.sessions || [];
      } catch (e) {
        body.innerHTML =
          '<div class="positions-error">Error cargando sesiones forward.' +
          '<button type="button" class="positions-retry-btn">Reintentar</button></div>';
        const btn = body.querySelector(".positions-retry-btn");
        if (btn) btn.addEventListener("click", renderEstrategiaTab);
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/forward/sessions", { type: "error" });
        return;
      }

      sessionsById = {};
      sessions.forEach((s) => { sessionsById[s.session_id] = s; });

      body.innerHTML = "";
      const wrap = el("div", { class: "positions-estrategia-wrap" });

      if (strategies.length) {
        const stratPanel = el("div", { class: "manage-strategy-panel" });
        stratPanel.appendChild(el("div", { class: "manage-strategy-panel-title", text: "Estrategias" }));
        const stratCards = el("div", { class: "manage-strategy-cards" });
        sortStrategiesGraduatedFirst(strategies).forEach((s) => {
          stratCards.appendChild(renderStrategyStateCard(s, renderEstrategiaTab));
        });
        stratPanel.appendChild(stratCards);
        body.appendChild(stratPanel);
      }

      if (!sessions.length) {
        const sessionsHost = el("div", {});
        renderEmptySessions(sessionsHost);
        body.appendChild(sessionsHost);
        return;
      }

      const sessionsHeader = el("div", { class: "manage-strategy-panel-title", text: "Sesiones forward" });
      wrap.appendChild(sessionsHeader);
      const cardsHost = el("div", { class: "positions-cards" });
      const detailHost = el("div", { class: "positions-detail" });
      wrap.appendChild(cardsHost);
      wrap.appendChild(detailHost);
      body.appendChild(wrap);

      sessions.forEach((session) => {
        const card = renderSessionCard(session);
        card.addEventListener("click", () => {
          cardsHost.querySelectorAll(".positions-session-card").forEach((c) => c.classList.remove("active"));
          card.classList.add("active");
          selectedSessionId = session.session_id;
          loadSessionTrades(session, detailHost);
        });
        cardsHost.appendChild(card);
      });

      if (selectedSessionId && sessionsById[selectedSessionId]) {
        const activeCard = cardsHost.querySelector(`.positions-session-card[data-session-id="${CSS.escape(selectedSessionId)}"]`);
        if (activeCard) activeCard.classList.add("active");
        loadSessionTrades(sessionsById[selectedSessionId], detailHost);
      } else {
        detailHost.innerHTML = '<div class="positions-detail-empty">Elegí una sesión arriba.</div>';
      }
    }

    async function loadSessionTrades(session, detailHost) {
      detailHost.innerHTML = '<div class="positions-detail-loading">Cargando trades&hellip;</div>';
      let tradesBody;
      try {
        tradesBody = await fetchSessionTrades(session.session_id);
      } catch (e) {
        detailHost.innerHTML = '<div class="positions-detail-error">Error cargando trades de la sesión.</div>';
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/forward/{session_id}/trades", { type: "error" });
        return;
      }

      const trades = tradesBody.trades || [];
      detailHost.innerHTML = "";

      const header = el("div", { class: "positions-detail-header" });
      const stratBadge = window.SENTINEL.badge.strategyBadge({
        familia: "",
        name: session.display_name || session.session_id,
        color_idx: session.color_idx,
        display_name: session.display_name || session.session_id,
      });
      header.innerHTML = `${stratBadge}<button type="button" class="positions-view-review-btn">Ver en chart &rarr; REVIEW</button>`;
      header.querySelector(".positions-view-review-btn").addEventListener("click", () => {
        window.SENTINEL.appState = window.SENTINEL.appState || {};
        window.SENTINEL.appState.selectedRun = session.session_id;
        const reviewBtn = document.querySelector('.nav-btn[data-section="review"]');
        if (reviewBtn) reviewBtn.click();
      });
      detailHost.appendChild(header);

      if (!trades.length) {
        detailHost.appendChild(el("div", { class: "positions-detail-empty", text: "Esta sesión no tiene trades." }));
        return;
      }

      const tableEl = el("div", { class: "positions-vtable" });
      detailHost.appendChild(tableEl);
      const rowsForTable = trades.map((t, i) => Object.assign({ __n: i + 1 }, t));
      vt = window.SENTINEL.vtable.createVTable(tableEl, {
        columns: tradeRowColumns(),
        rows: rowsForTable,
        rowKey: (r) => r.trade_id,
      });
    }

    reimportBtn.addEventListener("click", async () => {
      reimportBtn.disabled = true;
      const originalText = reimportBtn.textContent;
      reimportBtn.textContent = "Importando…";
      try {
        const report = await postReimportTokata();
        const files = report.files != null ? report.files : "--";
        const rowsNew = report.rows_new != null ? report.rows_new : "--";
        if (window.SENTINEL.toast) {
          window.SENTINEL.toast.show(`TOKATA reimportado: ${files} archivos, ${rowsNew} filas nuevas`, { type: "success" });
        }
        if (activeTab === "estrategia") renderEstrategiaTab();
      } catch (e) {
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error en POST /api/ingest/tokata", { type: "error" });
      } finally {
        reimportBtn.disabled = false;
        reimportBtn.textContent = originalText;
      }
    });

    renderTabs();
    renderBody();

    state = {
      root,
      teardown: () => {
        if (vt) { try { vt.destroy(); } catch (e) { /* noop */ } }
        if (humanoTabHandle) { try { humanoTabHandle.teardown(); } catch (e) { /* noop */ } }
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
  window.SENTINEL.sections.positions = { render, teardown };
})();
