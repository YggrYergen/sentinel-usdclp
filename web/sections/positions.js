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

  const EMPTY_FUTURE_COPY = "Disponible al activar live/IA (B4/B5)";

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
    card.innerHTML = `
      <div class="manage-strategy-card-top">${starHtml}${stratBadge}
        <span class="manage-estado-badge manage-estado-${escapeHtml(estado)}">${escapeHtml(estado)}</span>
      </div>
      <div class="manage-estado-controls"></div>`;
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

  function renderEmptyFutureTab(host) {
    host.innerHTML = `<div class="positions-empty-future">${escapeHtml(EMPTY_FUTURE_COPY)}</div>`;
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

  // no-op hook: B3b wires this up to open the expanded detail/replay panel.
  // Signature: onPositionSelect({ kind: "group"|"child", group, child }).
  function onPositionSelect(_selection) {
    // documented no-op for B3a; B3b (expanded panel + replay) replaces this.
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

  function renderHumanoGroupCard(item, fmt, expandedIds, onToggle, onSelect) {
    const group = item.group;
    const child = (group.children || [])[0] || {};
    const card = el("div", {
      class: "positions-humano-card",
      "data-group-id": group.group_id,
    });
    const chevronHtml = item.isMulti
      ? `<span class="positions-humano-chevron${item.expanded ? " open" : ""}" data-chevron="1">&#9656;</span>`
      : `<span></span>`;
    const tsIn = fmt.tsShort(epochOf(group.first_in));
    const tsOut = fmt.tsShort(epochOf(group.last_out));
    const pxIn = child.px_in != null ? fmtOrDash(fmt, child.px_in, "price") : "--";
    const pxOut = child.px_out != null ? fmtOrDash(fmt, child.px_out, "price") : "--";
    const pnl = group.net;
    const pct = fmtOrDash(fmt, child.pct, "pct");
    const mae = fmtOrDash(fmt, child.mae);
    const mfe = fmtOrDash(fmt, child.mfe);
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

  function renderHumanoTab(host) {
    injectHumanoCss();
    host.innerHTML = '<div class="positions-loading">Cargando posiciones&hellip;</div>';

    const expandedIds = new Set();
    let groups = [];
    let selectedKey = null;
    let humanoVlist = null;

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
      onPositionSelect(selection);
    }

    function handleToggle(groupId) {
      if (expandedIds.has(groupId)) expandedIds.delete(groupId);
      else expandedIds.add(groupId);
      refreshItems();
    }

    fetchPositions("human", "").then((body) => {
      groups = body.groups || [];
      host.innerHTML = "";
      if (!groups.length) {
        host.innerHTML = '<div class="positions-humano-empty">Sin posiciones HUMANO.</div>';
        return;
      }
      const listHost = el("div", { class: "positions-humano-list" });
      listHost.style.height = "100%";
      listHost.style.overflow = "auto";
      host.appendChild(listHost);

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
      teardown: () => { if (humanoVlist) { try { humanoVlist.destroy(); } catch (e) { /* noop */ } } },
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
        renderEmptyFutureTab(body);
        return;
      }
      if (activeTab === "humano") {
        humanoTabHandle = renderHumanoTab(body);
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
