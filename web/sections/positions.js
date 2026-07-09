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

  // ---- data fetch (D.6 contracts) ----
  async function fetchSessions() {
    const resp = await fetch("/api/forward/sessions");
    if (!resp.ok) throw new Error(`GET /api/forward/sessions failed: ${resp.status}`);
    return resp.json();
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
      body.innerHTML = "";
      if (activeTab === "humano" || activeTab === "ia") {
        renderEmptyFutureTab(body);
        return;
      }
      renderEstrategiaTab();
    }

    function renderEstrategiaTab() {
      body.innerHTML = '<div class="positions-loading">Cargando sesiones forward&hellip;</div>';
      loadSessions();
    }

    async function loadSessions() {
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

      if (!sessions.length) {
        renderEmptySessions(body);
        return;
      }

      const wrap = el("div", { class: "positions-estrategia-wrap" });
      const cardsHost = el("div", { class: "positions-cards" });
      const detailHost = el("div", { class: "positions-detail" });
      wrap.appendChild(cardsHost);
      wrap.appendChild(detailHost);
      body.innerHTML = "";
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
