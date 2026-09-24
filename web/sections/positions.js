// SENTINEL sections/positions.js — POSICIONES section (Task M2.3, plan
// §D.7-POSICIONES NORMATIVE). Tabs HUMANO · ESTRATEGIA · IA.
// ESTRATEGIA tab (2026-07-21) lists the strategies connected taking REAL
// positions in MT5 (GET /api/positions?origin=strategy): selectable strategy
// cards with their real scorecard (net / trades / PF / WR / DD), and for the
// selected strategy a table of its real positions (ABIERTA/CERRADA, spread at
// open/close, beneficio, %). Clicking a position opens the live chart+replay
// panel (buildHumanoDetailPanel) — trade-view, but for reals in vivo.
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

  // ---- ESTRATEGIA live positions CSS (2026-07-21), section-scoped. ----
  const ESTRATEGIA_LIVE_CSS_ID = "positions-estrategia-live-css";
  const ESTRATEGIA_LIVE_CSS = `
    /* Two-column ESTRATEGIA layout: left = cards + positions list, right = chart. */
    .estrategia-live-root { display: grid; grid-template-columns: minmax(360px, 42%) 1fr; gap: var(--sp-3, 12px); height: 100%; min-height: 0; }
    .estrategia-live-left { display: grid; grid-template-rows: auto 1fr; gap: var(--sp-3, 12px); min-height: 0; min-width: 0; }
    .estrategia-live-right { min-height: 0; min-width: 0; display: flex; flex-direction: column; border: var(--border, 1px solid #333); border-radius: var(--radius, 6px); background: var(--bg-1, #0d1117); overflow: hidden; }
    .estrategia-live-right .positions-humano-panel-host { flex: 1; min-height: 0; display: flex; }
    .estrategia-live-right .positions-humano-panel { flex: 1; border-top: none; }
    .estrategia-live-right .positions-humano-panel-chart { flex: 1; min-height: 260px; height: auto; }
    .estrategia-right-placeholder { flex: 1; display: flex; align-items: center; justify-content: center; text-align: center; padding: 24px; color: var(--text-2, #5c6a7d); font-size: 0.82rem; }
    .estrategia-cards-scroll { display: flex; flex-direction: column; gap: var(--sp-2, 8px); overflow-y: auto; max-height: 44vh; padding-right: 2px; }

    /* Strategy P&L card — net prominent + color-coded. */
    .estrategia-scard { cursor: pointer; display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; border: var(--border, 1px solid #333); border-radius: var(--radius, 6px); background: var(--bg-2, #131a24); border-left: 3px solid var(--strat-color, #00bfff); transition: border-color .12s, box-shadow .12s; }
    .estrategia-scard:hover { box-shadow: 0 0 0 1px var(--accent-celeste, #00bfff) inset; }
    .estrategia-scard.selected { box-shadow: 0 0 0 2px var(--accent-celeste, #00bfff) inset; background: rgba(0,191,255,0.06); }
    .estrategia-scard-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .estrategia-scard-head .manage-graduated-star { color: var(--accent-amber, #ffb020); }
    .estrategia-scard-live { margin-left: auto; font-size: 0.58rem; font-weight: 700; letter-spacing: 0.04em; color: var(--accent-green, #26a69a); display: inline-flex; align-items: center; gap: 4px; }
    .estrategia-scard-live::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--accent-green, #26a69a); box-shadow: 0 0 6px var(--accent-green, #26a69a); }
    .estrategia-scard-net { display: flex; align-items: baseline; gap: 8px; }
    .estrategia-scard-net-value { font-family: var(--mono, monospace); font-size: 1.5rem; font-weight: 800; line-height: 1.1; }
    .estrategia-scard-net-value.pos { color: var(--accent-green, #26a69a); }
    .estrategia-scard-net-value.neg { color: var(--accent-red, #ef5350); }
    .estrategia-scard-net-value.flat { color: var(--text-1, #8b98ab); }
    .estrategia-scard-net-label { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-2, #5c6a7d); }
    .estrategia-scard-stats { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 0.7rem; font-family: var(--mono, monospace); color: var(--text-1, #8b98ab); }
    .estrategia-scard-stats b { color: var(--text-0, #c9d4e3); font-weight: 700; }
    .estrategia-scard-counts { display: flex; gap: 6px; font-size: 0.62rem; }
    .estrategia-scard-count { display: inline-flex; align-items: center; gap: 4px; padding: 1px 7px; border-radius: 10px; border: 1px solid transparent; }
    .estrategia-scard-count.open { color: var(--accent-green, #26a69a); border-color: rgba(38,166,154,0.5); background: rgba(38,166,154,0.1); }
    .estrategia-scard-count.closed { color: var(--text-1, #8b98ab); border-color: rgba(139,152,171,0.3); }
    .estrategia-scard-controls { display: flex; gap: 4px; }
    .estrategia-scard-loading, .estrategia-scard-stats .muted { color: var(--text-2, #5c6a7d); }

    .positions-live-host { flex: 1; min-height: 0; display: flex; flex-direction: column; }
    .positions-estado-badge { display: inline-block; font-size: 0.6rem; font-weight: 700; padding: 1px 5px; border-radius: 3px; letter-spacing: 0.03em; }
    .positions-estado-abierta { background: rgba(38,166,154,0.18); color: var(--accent-green, #26a69a); border: 1px solid rgba(38,166,154,0.5); }
    .positions-estado-cerrada { background: rgba(139,152,171,0.12); color: var(--text-2, #5c6a7d); border: 1px solid rgba(139,152,171,0.3); }
    .positions-live-open { opacity: 0.6; font-style: italic; }
    .positions-spread-min { color: var(--accent-green, #26a69a); }
    .positions-live-empty { padding: 16px; opacity: 0.7; font-size: 0.82rem; }

    /* Compact positions vtable that fits the narrow left column (no overflow). */
    .estrategia-live-left .positions-live-host { min-height: 0; }
    .estrategia-live-left .positions-vtable { height: 100%; min-height: 0; display: flex; flex-direction: column; }
    .estrategia-live-left .positions-vtable .vtable-root { display: flex; flex-direction: column; min-height: 0; flex: 1; }
    .estrategia-live-left .positions-vtable .vtable-cell { font-size: 0.72rem; padding-left: 6px; padding-right: 6px; }
    .estrategia-live-left .positions-vtable .vtable-th { font-size: 0.62rem; }
    .estrategia-pos-io { display: flex; flex-direction: column; line-height: 1.25; }
    .estrategia-pos-io .io-out { color: var(--text-2, #5c6a7d); }
    .estrategia-pos-sym { display: flex; flex-direction: column; line-height: 1.2; }
    .estrategia-pos-sym .sym { font-weight: 700; }
    .estrategia-pos-spread { font-size: 0.7rem; }

    /* Task 1b: per-strategy chart toolbar (native TF switch + indicator
       selector popover), mounted above the chart in the ESTRATEGIA/HUMANO
       detail panel. Reuses the charts-tf-btn / charts-overlay-chip classes
       (already styled in style.css) so the TF buttons match CHARTS/REVIEW. */
    .estrategia-chart-toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 4px 2px 8px; }
    .estrategia-chart-toolbar-tf { display: flex; gap: 4px; }
    .estrategia-chart-native-note { font-size: 0.68rem; color: var(--text-2, #5c6a7d); font-style: italic; }
    .estrategia-ind-selector { position: relative; }
    .estrategia-ind-selector-btn { cursor: pointer; font-size: 0.72rem; padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border, #333); background: var(--bg-2, #131a24); color: var(--text-1, #8b98ab); }
    .estrategia-ind-selector-btn:hover { color: var(--accent-celeste, #00bfff); border-color: var(--accent-celeste, #00bfff); }
    .estrategia-ind-popover { position: absolute; z-index: 20; top: calc(100% + 4px); left: 0; min-width: 200px; display: flex; flex-direction: column; gap: 4px; padding: 8px; border: 1px solid var(--border, #333); border-radius: 6px; background: var(--bg-1, #0d1117); box-shadow: 0 6px 18px rgba(0,0,0,0.4); }
    .estrategia-ind-popover.hidden { display: none; }
    .estrategia-ind-popover label { display: flex; align-items: center; gap: 6px; font-size: 0.74rem; cursor: pointer; }
    .estrategia-ind-popover input[type="checkbox"] { margin: 0; }

    /* Task 2: contextual panel BELOW the chart -- strategy rules (card
       selected, no position) or position summary (row selected). Lives in
       the ESTRATEGIA right column, under panelHost/the chart. */
    .estrategia-context-panel { flex-shrink: 0; border-top: var(--border, 1px solid #333); padding: 10px 12px; max-height: 42vh; overflow-y: auto; }
    .estrategia-context-empty { padding: 8px 2px; color: var(--text-2, #5c6a7d); font-size: 0.78rem; font-style: italic; }

    /* STRATEGY view: rules grouped into Entrada / Salida / Meta. */
    .estrategia-rules-title { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
    .estrategia-rules-title b { font-size: 0.86rem; }
    .estrategia-rules-groups { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
    .estrategia-rules-group { display: flex; flex-direction: column; gap: 4px; padding: 8px 10px; border: 1px solid var(--border, #333); border-radius: 6px; background: var(--bg-2, #131a24); }
    .estrategia-rules-group-title { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent-celeste, #00bfff); font-weight: 700; margin-bottom: 2px; }
    .estrategia-rules-row { display: flex; justify-content: space-between; gap: 10px; font-size: 0.74rem; line-height: 1.4; }
    .estrategia-rules-row .k { color: var(--text-2, #5c6a7d); flex-shrink: 0; }
    .estrategia-rules-row .v { color: var(--text-0, #c9d4e3); text-align: right; font-family: var(--mono, monospace); }
    .estrategia-rules-note { font-size: 0.7rem; color: var(--text-2, #5c6a7d); font-style: italic; margin-top: 4px; }

    /* POSITION view: attractive summary card. */
    .estrategia-poscard { display: flex; flex-direction: column; gap: 10px; }
    .estrategia-poscard-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .estrategia-poscard-net { font-family: var(--mono, monospace); font-size: 1.6rem; font-weight: 800; line-height: 1.1; }
    .estrategia-poscard-net.pos { color: var(--accent-green, #26a69a); }
    .estrategia-poscard-net.neg { color: var(--accent-red, #ef5350); }
    .estrategia-poscard-net.flat { color: var(--text-1, #8b98ab); }
    .estrategia-poscard-pct { font-family: var(--mono, monospace); font-size: 0.9rem; opacity: 0.85; }
    .estrategia-poscard-side { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.04em; padding: 2px 7px; border-radius: 3px; }
    .estrategia-poscard-side.long { color: var(--accent-green, #26a69a); border: 1px solid rgba(38,166,154,0.5); background: rgba(38,166,154,0.1); }
    .estrategia-poscard-side.short { color: var(--accent-red, #ef5350); border: 1px solid rgba(239,83,80,0.5); background: rgba(239,83,80,0.1); }
    .estrategia-poscard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px 14px; }
    .estrategia-poscard-stat { display: flex; flex-direction: column; gap: 2px; }
    .estrategia-poscard-stat-label { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-2, #5c6a7d); }
    .estrategia-poscard-stat-value { font-family: var(--mono, monospace); font-size: 0.82rem; color: var(--text-0, #c9d4e3); }

    /* Task 3: per-position comment box, mounted below the POSITION card in
       the ESTRATEGIA context panel. Free-text notes on a real position,
       persisted via /api/positions/{id}/comments. */
    .estrategia-comments { display: flex; flex-direction: column; gap: 8px; margin-top: 4px; padding-top: 10px; border-top: 1px dashed var(--border, #333); }
    .estrategia-comments-title { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-2, #5c6a7d); font-weight: 700; }
    .estrategia-comments-list { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto; }
    .estrategia-comment-row { display: flex; align-items: flex-start; gap: 8px; padding: 6px 8px; border: 1px solid var(--border, #333); border-radius: 5px; background: var(--bg-2, #131a24); }
    .estrategia-comment-body { flex: 1; font-size: 0.78rem; line-height: 1.35; white-space: pre-wrap; word-break: break-word; color: var(--text-0, #c9d4e3); }
    .estrategia-comment-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
    .estrategia-comment-time { font-size: 0.62rem; color: var(--text-2, #5c6a7d); font-family: var(--mono, monospace); white-space: nowrap; }
    .estrategia-comment-del { cursor: pointer; background: none; border: none; color: var(--text-2, #5c6a7d); font-size: 0.9rem; line-height: 1; padding: 0; }
    .estrategia-comment-del:hover { color: var(--accent-red, #ef5350); }
    .estrategia-comment-del:disabled { opacity: 0.4; cursor: not-allowed; }
    .estrategia-comments-empty { font-size: 0.74rem; color: var(--text-2, #5c6a7d); font-style: italic; padding: 2px 0; }
    .estrategia-comments-error { font-size: 0.74rem; color: var(--accent-red, #ef5350); padding: 2px 0; }
    .estrategia-comments-form { display: flex; gap: 6px; align-items: flex-start; }
    .estrategia-comments-input { flex: 1; resize: vertical; min-height: 32px; max-height: 100px; font-size: 0.78rem; padding: 6px 8px; border-radius: 4px; border: 1px solid var(--border, #333); background: var(--bg-1, #0d1117); color: var(--text-0, #c9d4e3); font-family: inherit; }
    .estrategia-comments-add-btn { flex-shrink: 0; cursor: pointer; font-size: 0.76rem; padding: 6px 12px; border-radius: 4px; border: 1px solid var(--border, #333); background: var(--bg-2, #131a24); color: var(--text-1, #8b98ab); }
    .estrategia-comments-add-btn:hover:not(:disabled) { color: var(--accent-celeste, #00bfff); border-color: var(--accent-celeste, #00bfff); }
    .estrategia-comments-add-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  `;

  function injectEstrategiaLiveCss() {
    if (document.getElementById(ESTRATEGIA_LIVE_CSS_ID)) return;
    const style = document.createElement("style");
    style.id = ESTRATEGIA_LIVE_CSS_ID;
    style.textContent = ESTRATEGIA_LIVE_CSS;
    document.head.appendChild(style);
  }

  function scorecardFloorText(block) {
    if (!block) return "sin baseline";
    const fmt = window.SENTINEL.fmt;
    const net = block.net != null ? fmt.signed(block.net) : "--";
    const trades = block.trades != null ? block.trades : "--";
    const pf = block.pf != null ? fmt.num(block.pf) : "--";
    const wr = block.wr != null ? fmt.pct(block.wr) : "--";
    const dd = block.maxdd_pct != null ? fmt.pct(block.maxdd_pct) : "--";
    return `${net} · ${trades} trades · PF ${pf} · WR ${wr} · DD ${dd}`;
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

  function renderStrategyStateCard(strategy, onChanged, opts) {
    const options = opts || {};
    const badge = window.SENTINEL.badge;
    const estado = strategy.estado || "activa";
    const card = el("div", {
      class: `manage-strategy-card${options.selected ? " selected" : ""}${options.connected ? " connected" : ""}`,
      "data-strategy-id": strategy.strategy_id,
    });
    if (options.onSelect) {
      card.addEventListener("click", () => options.onSelect(strategy));
    }
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
      btn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
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

  // Aggregate open/closed position counts + net across a strategy's groups.
  function aggregateStrategyGroups(groups) {
    let net = 0;
    let open = 0;
    let closed = 0;
    let positions = 0;
    (groups || []).forEach((g) => {
      net += Number(g.net) || 0;
      (g.children || []).forEach((c) => {
        positions += 1;
        if (c.is_open) open += 1; else closed += 1;
      });
    });
    return { net, open, closed, positions };
  }

  // Wires the activa/pausada/graduada segmented control into `controls`,
  // shared by the P&L strategy card (extracted so both cards behave the same).
  function wireEstadoControls(controls, strategy, onChanged) {
    const estado = strategy.estado || "activa";
    ESTADOS.forEach((e) => {
      const btn = el("button", {
        type: "button",
        class: `manage-estado-btn${e === estado ? " active" : ""}`,
      });
      btn.textContent = e;
      btn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
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
  }

  function netValueClass(v) {
    const n = Number(v);
    if (!Number.isFinite(n) || n === 0) return "flat";
    return n > 0 ? "pos" : "neg";
  }

  // ESTRATEGIA P&L card (2026-07-21 redesign): net result is the headline,
  // color-coded green/red, with PF · WR · DD and open/closed counts, plus the
  // estado control and strategy badge/color identity. `agg` is the live
  // aggregate from this strategy's groups (net + counts); PF/WR/DD come from
  // the async real scorecard.
  function renderStrategyPnlCard(strategy, agg, onChanged, opts) {
    const options = opts || {};
    const badge = window.SENTINEL.badge;
    const fmt = window.SENTINEL.fmt;
    const color = badge.colorForIdx(strategy.color_idx);
    const card = el("div", {
      class: `estrategia-scard${options.selected ? " selected" : ""}`,
      "data-strategy-id": strategy.strategy_id,
      style: `--strat-color:${color}`,
    });
    if (options.onSelect) {
      card.addEventListener("click", () => options.onSelect(strategy));
    }
    const stratBadge = badge.strategyBadge({
      familia: strategy.familia,
      name: strategy.familia && strategy.familia.toLowerCase() === (strategy.name || "").toLowerCase() ? "" : strategy.name,
      color_idx: strategy.color_idx,
      display_name: strategy.name,
    });
    const starHtml = strategy.graduated ? '<span class="manage-graduated-star" title="Graduada">&#9733;</span>' : "";
    const estado = strategy.estado || "activa";
    const netCls = netValueClass(agg.net);
    card.innerHTML = `
      <div class="estrategia-scard-head">
        ${starHtml}${stratBadge}
        <span class="manage-estado-badge manage-estado-${escapeHtml(estado)}">${escapeHtml(estado)}</span>
        ${options.connected ? '<span class="estrategia-scard-live">EN VIVO</span>' : ""}
      </div>
      <div class="estrategia-scard-net">
        <span class="estrategia-scard-net-value ${netCls} mono">${fmt.signed(agg.net)}</span>
        <span class="estrategia-scard-net-label">Neto real</span>
      </div>
      <div class="estrategia-scard-stats" data-role="scorecard"><span class="muted">PF -- · WR -- · DD --</span></div>
      <div class="estrategia-scard-counts">
        <span class="estrategia-scard-count open" title="Posiciones abiertas">● ${agg.open} abiertas</span>
        <span class="estrategia-scard-count closed" title="Posiciones cerradas">${agg.closed} cerradas</span>
      </div>
      <div class="estrategia-scard-controls manage-estado-controls"></div>`;
    wireEstadoControls(card.querySelector(".manage-estado-controls"), strategy, onChanged);

    // Async real scorecard -> PF · WR · DD (net headline already from groups).
    const statsHost = card.querySelector('[data-role="scorecard"]');
    fetchScorecard(strategy.strategy_id).then((data) => {
      const real = (data.floors && data.floors.real) || null;
      if (!real) { statsHost.innerHTML = '<span class="muted">sin scorecard</span>'; return; }
      const pf = real.pf != null ? fmt.num(real.pf) : "--";
      const wr = real.wr != null ? fmt.pct(real.wr) : "--";
      const dd = real.maxdd_pct != null ? fmt.pct(real.maxdd_pct) : "--";
      const trades = real.trades != null ? real.trades : "--";
      statsHost.innerHTML =
        `<span>PF <b>${escapeHtml(pf)}</b></span>` +
        `<span>WR <b>${escapeHtml(wr)}</b></span>` +
        `<span>DD <b>${escapeHtml(dd)}</b></span>` +
        `<span>${escapeHtml(String(trades))} trades</span>`;
    }).catch(() => {
      statsHost.innerHTML = '<span class="muted">scorecard n/d</span>';
    });
    return card;
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

  // ---- ESTRATEGIA live positions (2026-07-21): real MT5 positions per
  // connected strategy. Each row is ONE position (a flattened group child),
  // marked ABIERTA/CERRADA, with the spread captured at open (★ when it was
  // the running-min the min-spread gate admits) and at close, plus beneficio
  // and %. Clicking a row opens the same live chart+replay panel the HUMANO
  // tab uses (buildHumanoDetailPanel) -- the "trade-view for reals". ----
  function sideOf(group) {
    return (group && group.side) || "--";
  }

  function sideClass(group) {
    const s = String(sideOf(group)).toUpperCase();
    if (s.startsWith("B") || s === "LONG" || s === "L") return "sentinel-sign-pos";
    if (s.startsWith("S") || s === "SHORT") return "sentinel-sign-neg";
    return "";
  }

  function estadoBadgeHtml(isOpen) {
    return isOpen
      ? '<span class="positions-estado-badge positions-estado-abierta">ABIERTA</span>'
      : '<span class="positions-estado-badge positions-estado-cerrada">CERRADA</span>';
  }

  // Spread-at-open cell: shows the value and a ★ when it was at/under the
  // learned running-min (spread_open <= spread_open_min + eps), i.e. admitted
  // by the min-spread OPEN gate. Null (historical position) -> "--".
  function spreadCellHtml(fmt, spread, spreadMin) {
    if (spread === null || spread === undefined || Number.isNaN(Number(spread))) {
      return '<span class="mono">--</span>';
    }
    const atMin = spreadMin != null && Number(spread) <= Number(spreadMin) + 1e-6;
    const star = atMin ? ' <span class="positions-spread-min" title="Spread mínimo (gate)">★</span>' : "";
    return `<span class="mono">${fmt.num(spread)}${star}</span>`;
  }

  // Compact columns so the list fits the narrow LEFT column of the two-column
  // ESTRATEGIA layout without horizontal overflow. Símbolo+Lado are stacked in
  // one cell, entrada→salida (ts @ px) stacked in one flexible cell, and the
  // two spreads (apertura ★ / cierre) share one cell. Only two fixed-width
  // columns + one 1fr → the vtable grid template can't overflow.
  function symCellHtml(r) {
    const sym = escapeHtml((r.__group && r.__group.symbol) || "--");
    const side = escapeHtml(sideOf(r.__group));
    return `<span class="estrategia-pos-sym mono"><span class="sym">${sym}</span><span class="${sideClass(r.__group)}">${side}</span></span>`;
  }

  function ioCellHtml(fmt, r) {
    const inLine = `${fmt.tsShort(epochOf(r.ts_in))} @ ${fmtOrDash(fmt, r.px_in, "price")}`;
    const outLine = r.is_open
      ? '<span class="positions-live-open">— abierta —</span>'
      : `${fmt.tsShort(epochOf(r.ts_out))} @ ${fmtOrDash(fmt, r.px_out, "price")}`;
    return `<span class="estrategia-pos-io mono"><span>${inLine}</span><span class="io-out">${outLine}</span></span>`;
  }

  function spreadPairCellHtml(fmt, r) {
    const open = spreadCellHtml(fmt, r.spread_open, r.spread_open_min);
    const close = `<span class="mono">${fmtOrDash(fmt, r.spread_close)}</span>`;
    return `<span class="estrategia-pos-spread">${open} / ${close}</span>`;
  }

  function livePositionColumns(fmt) {
    return [
      { key: "estado", label: "Estado", width: "72px", render: (r) => estadoBadgeHtml(r.is_open) },
      { key: "symbol", label: "Símbolo", width: "72px", render: (r) => symCellHtml(r) },
      { key: "io", label: "Entrada → Salida", width: "1fr", render: (r) => ioCellHtml(fmt, r) },
      { key: "spread", label: "Spread ap.★/ci.", width: "104px",
        render: (r) => spreadPairCellHtml(fmt, r) },
      { key: "pnl", label: "Beneficio", width: "82px", numeric: true,
        render: (r) => `<span class="mono ${signClass(r.pnl)}">${fmt.signed(r.pnl)}</span>` },
      { key: "pct", label: "%", width: "54px", numeric: true,
        render: (r) => `<span class="mono">${fmtOrDash(fmt, r.pct, "pct")}</span>` },
    ];
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

  // ---- Task 3: per-position comments (GET/POST/DELETE
  // /api/positions/{position_id}/comments). ----
  async function fetchPositionComments(positionId) {
    const resp = await fetch(`/api/positions/${encodeURIComponent(positionId)}/comments`);
    if (!resp.ok) throw new Error(`GET /api/positions/${positionId}/comments failed: ${resp.status}`);
    const body = await resp.json();
    return body.comments || [];
  }

  async function postPositionComment(positionId, bodyText, magic) {
    const payload = { body: bodyText };
    if (magic !== null && magic !== undefined) payload.magic = magic;
    const resp = await fetch(`/api/positions/${encodeURIComponent(positionId)}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      const msg = (err && err.error && err.error.message) || `POST comment failed: ${resp.status}`;
      throw new Error(msg);
    }
    return resp.json();
  }

  async function deletePositionComment(positionId, commentId) {
    const resp = await fetch(
      `/api/positions/${encodeURIComponent(positionId)}/comments/${encodeURIComponent(commentId)}`,
      { method: "DELETE" },
    );
    if (!resp.ok) throw new Error(`DELETE comment failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchPositions(origin, symbol, strategyId, limit) {
    const params = new URLSearchParams();
    if (origin) params.set("origin", origin);
    if (symbol) params.set("symbol", symbol);
    if (strategyId) params.set("strategy_id", strategyId);
    params.set("limit", String(limit || 200));
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

  // ---- Task 1b: per-strategy chart (native TF + TF switch + exact
  // indicators + selector). Data source: GET /api/strategies/chart-specs
  // (Task 1a) -> {specs: {config_id: {id, tf, engine, magic, indicators,
  // rules, notes}}}. MUST map by MAGIC (deals_raw.strategy_id is NOT a
  // config id) -- build magic -> spec once, cached module-level (specs are
  // static per deploy; a stale cache just means a new server-side roster
  // needs a page reload, same staleness class as every other static asset
  // here). ----
  // Servable TF set: the bars/lake/chart pipeline only serves these (see
  // sentinel_engine/service/routers/jobs.py::_VALID_TF_NAMES and chart.js's
  // own internal TF_LIST which additionally lacks H1/D -- every strategy
  // this task targets uses M2/M15, both already in chart.js's TF_LIST, so
  // that narrower intersection is what actually matters for setTF()).
  const SERVABLE_TF = new Set(["M1", "M2", "M5", "M15", "H1", "D"]);

  let _chartSpecsPromise = null;
  function fetchChartSpecs() {
    if (!_chartSpecsPromise) {
      _chartSpecsPromise = fetch("/api/strategies/chart-specs")
        .then((resp) => {
          if (!resp.ok) throw new Error(`GET /api/strategies/chart-specs failed: ${resp.status}`);
          return resp.json();
        })
        .then((body) => body.specs || {})
        .catch(() => ({})); // degrade clean -- no specs -> every position falls back to generic chart
    }
    return _chartSpecsPromise;
  }

  let _magicSpecIndexPromise = null;
  function fetchMagicSpecIndex() {
    if (!_magicSpecIndexPromise) {
      _magicSpecIndexPromise = fetchChartSpecs().then((specs) => {
        const byMagic = new Map();
        Object.keys(specs).forEach((cid) => {
          const spec = specs[cid];
          if (!spec || spec.magic == null) return;
          // chart-specs carry each config's BASE magic (e.g. 724020), but the
          // live positions carry the per-FICHA magic (base+1..+3 for F1/F2/F3,
          // e.g. 724021/22/23; TK base 999999998 -> position 999999999). The
          // reconciler puts fichas at base+1..+3, so index the base AND its
          // ficha band so a position/strategy magic resolves to its spec.
          for (let off = 0; off <= 3; off++) {
            if (!byMagic.has(spec.magic + off)) byMagic.set(spec.magic + off, spec);
          }
        });
        return byMagic;
      });
    }
    return _magicSpecIndexPromise;
  }

  // 🔴 SCOPE (2026-07-21): M6 (TK-Momentum's native tf) is NOT servable by
  // /api/bars yet (backlogged) -- any spec whose tf isn't in SERVABLE_TF is
  // treated as "no native TF available": never set it, never fetch /api/bars
  // with it, no TF button for it. Falls back to the panel's generic behavior
  // (current chart, no forced native TF, no indicators) -- never crash.
  function specHasServableTf(spec) {
    return !!(spec && spec.tf && SERVABLE_TF.has(spec.tf));
  }

  const IND_OVERLAY_ID = (ind, idx) => `strat-ind-${idx}-${ind.type}`;

  // Computes a single indicator's chart points against already-fetched bars
  // (bars: [[ts,o,h,l,c,v],...], see charts.js fetchLastBars/lib/chart.js
  // ct2BarsToTuples). Returns null for an indicator type/pane this client
  // can't render (caller skips it) rather than throwing.
  function computeIndicatorPoints(ind, bars) {
    const calc = window.SENTINEL.chartCalc;
    if (!calc || !bars.length) return null;
    const times = bars.map((b) => b[0]);
    const highs = bars.map((b) => b[2]);
    const lows = bars.map((b) => b[3]);
    const closes = bars.map((b) => b[4]);
    const params = ind.params || {};
    if (ind.type === "EMA") {
      const period = Number(params.period) || 20;
      return times.map((t, i) => [t, calc.computeEMA(closes, period)[i]]);
    }
    if (ind.type === "SMA") {
      const period = Number(params.period) || 20;
      const vals = calc.computeSMA(closes, period);
      return times.map((t, i) => [t, vals[i]]);
    }
    if (ind.type === "MOM") {
      const period = Number(params.period) || 2;
      const vals = calc.computeMomentum(closes, period);
      return times.map((t, i) => [t, vals[i]]);
    }
    if (ind.type === "SAR") {
      // Static SAR: params.step/params.max used verbatim (byte-for-byte port
      // of emasar.py sar_series, see charts.js computeSAR).
      // Adaptive SAR (params.adaptive=true, params.sar_fast/sar_slow tuples +
      // params.vol_regime_window): the ENGINE picks per-bar between a FAST
      // SAR series (sar_fast step/max) and a SLOW one (sar_slow step/max),
      // switching on whether ATR14[i] exceeds the rolling median of the
      // previous vol_regime_window bars' ATR14 (see emasar_variant.py
      // sar_adaptive block) -- a genuine regime switch, not just a
      // parameter choice. Exactly replicating that regime-detection
      // client-side is out of scope for this task (documented approximation,
      // per the task brief): we render the STANDARD parabolic SAR using
      // sar_fast as (step, max) -- i.e. the "fast" leg of the adaptive pair,
      // which in every current config is (0.3, 0.3), identical to the
      // static default. This is an APPROXIMATION for adaptive configs (it
      // never falls back to the "slow" leg) -- labeled "SAR (approx)" in the
      // indicator label so the operator knows it's not exact.
      let step;
      let maxStep;
      if (params.adaptive && Array.isArray(params.sar_fast)) {
        step = Number(params.sar_fast[0]);
        maxStep = Number(params.sar_fast[1]);
      } else {
        step = Number(params.step) || 0.02;
        maxStep = Number(params.max) || 0.2;
      }
      const { sar } = calc.computeSAR(highs, lows, step, maxStep);
      return times.map((t, i) => [t, sar[i]]);
    }
    if (ind.type === "SUPERTREND") {
      const atrPeriod = Number(params.atr_period) || 14;
      const mult = Number(params.mult) || 3.0;
      const { line } = calc.computeSuperTrend(highs, lows, closes, atrPeriod, mult);
      return times.map((t, i) => [t, line[i]]);
    }
    return null;
  }

  // Applies (or removes) one indicator's overlay on chartInst, using the
  // SAME overlay kinds review.js's applyIndicator() uses (price-pane
  // line/dots vs the "osc" sub-pane line for pane:"sub" indicators like
  // MOM). chart.js already exposes addOscLine/addOscHistogram (a dedicated
  // bottom price-scale, see lib/chart.js "oscillator SUBPANEL" block) --
  // MOM maps directly onto addOscLine, no chart.js change needed.
  function applyStratIndicator(chartInst, ind, id, points) {
    if (!points) { chartInst.removeOverlay(id); return; }
    if (ind.pane === "sub") {
      chartInst.addOscLine(id, points, ind.color || "#ffffff");
    } else if (ind.type === "SAR") {
      chartInst.addSarDots(id, points, ind.color || "#ab47bc");
    } else {
      chartInst.addOverlay(id, points, ind.color || "#00bfff");
    }
  }

  // Builds the toolbar (TF buttons + indicator selector popover) for a
  // resolved spec, mounted above the chart. Returns {el, destroy}. `getBars`
  // returns the chart's currently-loaded bars synchronously (chartInst has
  // no public bars getter, so the caller passes a small wrapper that
  // re-fetches /api/bars for the active tf -- see wireStrategyChart below).
  function buildStratChartToolbar(host, spec, activeIndicatorIds, callbacks) {
    const toolbar = el("div", { class: "estrategia-chart-toolbar" });

    if (specHasServableTf(spec)) {
      const tfWrap = el("div", { class: "estrategia-chart-toolbar-tf" });
      // Only the TF the strategy is native on, plus the other servable TFs
      // chart.js itself already supports (its internal TF_LIST) -- reusing
      // charts.js's own list would require exporting it; simplest safe
      // superset that never calls setTF with a value chart.js rejects.
      const CHART_JS_TF_LIST = ["M1", "M2", "M5", "M15"];
      CHART_JS_TF_LIST.forEach((tf) => {
        const btn = el("button", { type: "button", class: "charts-tf-btn", text: tf });
        if (tf === callbacks.getActiveTf()) btn.classList.add("active");
        btn.addEventListener("click", () => {
          tfWrap.querySelectorAll(".charts-tf-btn").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          callbacks.onTF(tf);
        });
        tfWrap.appendChild(btn);
      });
      toolbar.appendChild(tfWrap);
    } else {
      toolbar.appendChild(el("span", {
        class: "estrategia-chart-native-note",
        text: `TF nativo ${(spec && spec.tf) || "?"} — no disponible aún`,
      }));
    }

    // Indicator selector pop-up: button -> popover listing every one of the
    // strategy's spec indicators, pre-checked (the exact set the strategy
    // trades on). Unchecking removes it, re-checking re-adds it -- reuses
    // the overlay-chip TOGGLE semantics (charts.js onOverlayToggle), just
    // rendered as checkboxes in a popover instead of chips (a strategy can
    // have 3-4 indicators; chips would crowd the toolbar).
    const indicators = (spec && spec.indicators) || [];
    if (indicators.length) {
      const selectorWrap = el("div", { class: "estrategia-ind-selector" });
      const selBtn = el("button", { type: "button", class: "estrategia-ind-selector-btn", text: "Indicadores ▾" });
      const popover = el("div", { class: "estrategia-ind-popover hidden" });
      indicators.forEach((ind, idx) => {
        const id = IND_OVERLAY_ID(ind, idx);
        const label = el("label", {});
        const cb = el("input", { type: "checkbox" });
        cb.checked = activeIndicatorIds.has(id);
        cb.addEventListener("change", () => callbacks.onIndicatorToggle(ind, id, cb.checked));
        label.appendChild(cb);
        label.appendChild(el("span", { text: ind.label || ind.type }));
        popover.appendChild(label);
      });
      selBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        popover.classList.toggle("hidden");
      });
      document.addEventListener("click", (ev) => {
        if (!selectorWrap.contains(ev.target)) popover.classList.add("hidden");
      });
      selectorWrap.appendChild(selBtn);
      selectorWrap.appendChild(popover);
      toolbar.appendChild(selectorWrap);
    }

    host.appendChild(toolbar);
    return toolbar;
  }

  // Wires the native-TF/indicators/selector behavior onto an already-created
  // chartInst for the position's resolved `spec` (may be null/no-spec, or
  // non-servable-tf -- both degrade to "no toolbar, chart unchanged", per
  // the task's scope decision). Returns a teardown fn (no-op if no spec).
  function wireStrategyChart(toolbarHost, chartInst, spec, symbol) {
    if (!spec || !chartInst) return () => {};
    const indicators = spec.indicators || [];
    // Strategy's exact indicator set starts ACTIVE (pre-checked), per spec.
    const activeIds = new Set(indicators.map((ind, idx) => IND_OVERLAY_ID(ind, idx)));
    let activeTf = specHasServableTf(spec) ? spec.tf : chartInst.tf;
    let destroyed = false;

    async function applyAllActive() {
      if (destroyed) return;
      let bars;
      try {
        const usp = new URLSearchParams({ symbol, tf: activeTf, max_points: "3000" });
        const resp = await fetch(`/api/bars?${usp.toString()}`);
        if (!resp.ok) return;
        const body = await resp.json();
        bars = (body.bars || []).map((b) => (Array.isArray(b) ? b : [b.t, b.o, b.h, b.l, b.c, b.v]));
      } catch (e) {
        return;
      }
      if (destroyed || !bars.length) return;
      indicators.forEach((ind, idx) => {
        const id = IND_OVERLAY_ID(ind, idx);
        if (!activeIds.has(id)) { chartInst.removeOverlay(id); return; }
        const points = computeIndicatorPoints(ind, bars);
        applyStratIndicator(chartInst, ind, id, points);
      });
    }

    const toolbar = buildStratChartToolbar(toolbarHost, spec, activeIds, {
      getActiveTf: () => activeTf,
      onTF: (tf) => {
        activeTf = tf;
        Promise.resolve(chartInst.setTF(tf)).then(applyAllActive);
      },
      onIndicatorToggle: (ind, id, checked) => {
        if (checked) activeIds.add(id); else activeIds.delete(id);
        if (!checked) { chartInst.removeOverlay(id); return; }
        applyAllActive();
      },
    });

    // Native-TF default: if the strategy's tf is servable and differs from
    // the chart's current tf, switch to it before the first indicator apply
    // (requirement 1). If not servable (M6/TK) or no spec, chartInst keeps
    // whatever tf buildHumanoDetailPanel already opened it at.
    let initial;
    if (specHasServableTf(spec) && chartInst.tf !== spec.tf) {
      initial = Promise.resolve(chartInst.setTF(spec.tf)).then(applyAllActive);
    } else {
      initial = applyAllActive();
    }
    Promise.resolve(initial).catch(() => { /* noop -- best-effort */ });

    return () => {
      destroyed = true;
      indicators.forEach((ind, idx) => { try { chartInst.removeOverlay(IND_OVERLAY_ID(ind, idx)); } catch (e) { /* noop */ } });
      if (toolbar && toolbar.parentNode) toolbar.parentNode.removeChild(toolbar);
    };
  }

  // ---- Task 2: contextual panel BELOW the chart, ESTRATEGIA right column.
  // STRATEGY view (a card is selected, no position row yet) renders
  // spec.rules as readable labeled groups (Entrada/Salida/Meta) -- NOT raw
  // JSON. POSITION view (a row is clicked) renders an attractive summary
  // card for that one position. Both reuse fetchMagicSpecIndex (magic ->
  // spec, Task 1a/1b) and the fmt/signClass/estadoBadgeHtml/spreadCellHtml
  // helpers already used elsewhere in this file -- no duplicated formatting.

  function ruleRowHtml(label, value) {
    if (value === null || value === undefined || value === "") return "";
    return `<div class="estrategia-rules-row"><span class="k">${escapeHtml(label)}</span><span class="v">${escapeHtml(value)}</span></div>`;
  }

  // Renders a plain value (string/number/bool) or a small object of
  // sub-fields (e.g. exit.trailing = {f1_trail_pips, f2_trail_pips, ...}) as
  // one or more labeled rows -- never dumps raw JSON.
  function ruleValueRowsHtml(label, value) {
    if (value === null || value === undefined) return "";
    if (Array.isArray(value)) {
      if (!value.length) return "";
      return ruleRowHtml(label, value.join(", "));
    }
    if (typeof value === "object") {
      const rows = Object.keys(value)
        .map((k) => ruleRowHtml(`${label} · ${k}`, formatRuleScalar(value[k])))
        .join("");
      return rows;
    }
    return ruleRowHtml(label, formatRuleScalar(value));
  }

  function formatRuleScalar(v) {
    if (v === null || v === undefined) return "";
    if (typeof v === "boolean") return v ? "sí" : "no";
    return String(v);
  }

  // Builds the STRATEGY view: spec.rules (Task 1a shape -- entry/long/short/
  // exit{sl,tp,trailing,reentry,stop_and_reverse,blocked_hours,...}/tf/
  // engine/magic/notes) grouped into Entrada / Salida / Meta.
  function renderStrategyRulesPanel(host, strategyName, spec) {
    host.innerHTML = "";
    if (!spec || !spec.rules) {
      host.appendChild(el("div", {
        class: "estrategia-context-empty",
        text: `${strategyName || "Esta estrategia"}: sin ficha de estrategia.`,
      }));
      return;
    }
    const rules = spec.rules;
    const exit_ = rules.exit || {};

    const entradaRows = [
      ruleRowHtml("Entrada", rules.entry),
      ruleRowHtml("Largo", rules.long),
      ruleRowHtml("Corto", rules.short),
    ].join("");

    const salidaRows = [
      ruleRowHtml("Stop loss", exit_.sl),
      ruleRowHtml("Take profit", exit_.tp),
      ruleValueRowsHtml("Trailing", exit_.trailing),
      ruleValueRowsHtml("Reentrada", exit_.reentry),
      ruleRowHtml("Stop &amp; reverse", exit_.stop_and_reverse === true ? "sí" : (exit_.stop_and_reverse === false ? "no" : null)),
      ruleRowHtml("Horas bloqueadas", Array.isArray(exit_.blocked_hours) && exit_.blocked_hours.length ? exit_.blocked_hours.join(", ") : null),
      ruleRowHtml("Modulación AC", exit_.ac_modulate === true ? `sí (factor ${formatRuleScalar(exit_.ac_modulate_factor)})` : (exit_.ac_modulate === false ? "no" : null)),
      ruleRowHtml("Fichas activas", exit_.active_fichas),
    ].join("");

    const metaRows = [
      ruleRowHtml("Timeframe", spec.tf || rules.tf),
      ruleRowHtml("Engine", spec.engine || rules.engine),
      ruleRowHtml("Magic", spec.magic != null ? spec.magic : rules.magic),
    ].join("");

    const wrap = el("div", {});
    wrap.innerHTML = `
      <div class="estrategia-rules-title"><b>${escapeHtml(strategyName || spec.id || "Estrategia")}</b></div>
      <div class="estrategia-rules-groups">
        <div class="estrategia-rules-group"><div class="estrategia-rules-group-title">Entrada</div>${entradaRows || '<div class="estrategia-rules-note">Sin datos.</div>'}</div>
        <div class="estrategia-rules-group"><div class="estrategia-rules-group-title">Salida</div>${salidaRows || '<div class="estrategia-rules-note">Sin datos.</div>'}</div>
        <div class="estrategia-rules-group"><div class="estrategia-rules-group-title">Meta</div>${metaRows || '<div class="estrategia-rules-note">Sin datos.</div>'}</div>
      </div>
      ${rules.notes ? `<div class="estrategia-rules-note">${escapeHtml(rules.notes)}</div>` : ""}`;
    host.appendChild(wrap);
  }

  // Builds the POSITION view: net (color-coded, prominent), %, side, estado
  // badge, entrada/salida (px + hora), spread apertura/cierre, lotes,
  // duración. `row` is one flattened position row (group child + __group),
  // same shape livePositionColumns/ioCellHtml/spreadPairCellHtml consume.
  function positionDurationText(row) {
    const tIn = epochOf(row.ts_in);
    const tOut = row.is_open ? (Date.now() / 1000) : epochOf(row.ts_out);
    if (tIn == null || tOut == null || tOut < tIn) return "--";
    const secs = Math.round(tOut - tIn);
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  function renderPositionSummaryPanel(host, row) {
    const fmt = window.SENTINEL.fmt;
    host.innerHTML = "";
    if (!row) {
      host.appendChild(el("div", { class: "estrategia-context-empty", text: "Sin posición seleccionada." }));
      return;
    }
    const group = row.__group || {};
    const netCls = netValueClass(row.pnl);
    const side = String(sideOf(group)).toUpperCase();
    const isLong = side.startsWith("B") || side === "LONG" || side === "L";
    const sideLabel = isLong ? "LARGO" : (side.startsWith("S") || side === "SHORT" ? "CORTO" : side || "--");
    const sideCls = isLong ? "long" : "short";
    const tsIn = fmt.tsShort(epochOf(row.ts_in));
    const tsOut = row.is_open ? "—" : fmt.tsShort(epochOf(row.ts_out));
    const pxIn = fmtOrDash(fmt, row.px_in, "price");
    const pxOut = row.is_open ? "—" : fmtOrDash(fmt, row.px_out, "price");

    const wrap = el("div", { class: "estrategia-poscard" });
    wrap.innerHTML = `
      <div class="estrategia-poscard-head">
        <span class="estrategia-poscard-net ${netCls} mono">${fmt.signed(row.pnl)}</span>
        <span class="estrategia-poscard-pct mono">${fmtOrDash(fmt, row.pct, "pct")}</span>
        <span class="estrategia-poscard-side ${sideCls}">${escapeHtml(sideLabel)}</span>
        ${estadoBadgeHtml(row.is_open)}
      </div>
      <div class="estrategia-poscard-grid">
        <div class="estrategia-poscard-stat"><span class="estrategia-poscard-stat-label">Entrada</span><span class="estrategia-poscard-stat-value">${tsIn} @ ${pxIn}</span></div>
        <div class="estrategia-poscard-stat"><span class="estrategia-poscard-stat-label">Salida</span><span class="estrategia-poscard-stat-value">${tsOut} @ ${pxOut}</span></div>
        <div class="estrategia-poscard-stat"><span class="estrategia-poscard-stat-label">Spread apertura</span><span class="estrategia-poscard-stat-value">${spreadCellHtml(fmt, row.spread_open, row.spread_open_min)}</span></div>
        <div class="estrategia-poscard-stat"><span class="estrategia-poscard-stat-label">Spread cierre</span><span class="estrategia-poscard-stat-value">${fmtOrDash(fmt, row.spread_close)}</span></div>
        <div class="estrategia-poscard-stat"><span class="estrategia-poscard-stat-label">Lotes</span><span class="estrategia-poscard-stat-value">${fmtOrDash(fmt, row.volume != null ? row.volume : group.lots)}</span></div>
        <div class="estrategia-poscard-stat"><span class="estrategia-poscard-stat-label">Duración</span><span class="estrategia-poscard-stat-value">${escapeHtml(positionDurationText(row))}</span></div>
      </div>`;
    host.appendChild(wrap);
  }

  // ---- Task 3: per-position comment box. Mounted below the POSITION
  // summary card (renderPositionSummaryPanel) for the currently selected
  // position_id. Self-contained: loads/lists/adds/deletes comments for
  // exactly one position_id; callers rebuild it whenever the selected
  // position changes (no external state kept beyond this DOM subtree). ----
  function commentRowHtml(fmt, c) {
    const when = fmt.ts(epochOf(c.created_at));
    return `
      <span class="estrategia-comment-body">${escapeHtml(c.body)}</span>
      <span class="estrategia-comment-meta">
        <span class="estrategia-comment-time">${escapeHtml(when)}</span>
        <button type="button" class="estrategia-comment-del" data-comment-id="${escapeHtml(String(c.comment_id))}" title="Eliminar">×</button>
      </span>`;
  }

  function renderPositionCommentsBox(host, positionId, magic) {
    const fmt = window.SENTINEL.fmt;
    host.innerHTML = "";
    if (positionId === null || positionId === undefined) return;

    const wrap = el("div", { class: "estrategia-comments" });
    wrap.appendChild(el("div", { class: "estrategia-comments-title", text: "Comentarios" }));
    const listHost = el("div", { class: "estrategia-comments-list" });
    wrap.appendChild(listHost);

    const form = el("div", { class: "estrategia-comments-form" });
    const input = el("textarea", {
      class: "estrategia-comments-input",
      rows: "1",
      placeholder: "Añadir un comentario…",
    });
    const addBtn = el("button", { type: "button", class: "estrategia-comments-add-btn" });
    addBtn.textContent = "Añadir";
    form.appendChild(input);
    form.appendChild(addBtn);
    wrap.appendChild(form);
    host.appendChild(wrap);

    function buildCommentRow(c) {
      const row = el("div", { class: "estrategia-comment-row" });
      row.innerHTML = commentRowHtml(fmt, c);
      const delBtn = row.querySelector(".estrategia-comment-del");
      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          delBtn.disabled = true;
          try {
            await deletePositionComment(positionId, c.comment_id);
            row.remove();
            if (!listHost.querySelector(".estrategia-comment-row")) {
              listHost.innerHTML = "";
              listHost.appendChild(el("div", { class: "estrategia-comments-empty", text: "Sin comentarios todavía." }));
            }
          } catch (e) {
            delBtn.disabled = false;
            if (window.SENTINEL.toast) {
              window.SENTINEL.toast.show("Error eliminando comentario", { type: "error" });
            } else {
              listHost.appendChild(el("div", { class: "estrategia-comments-error", text: "Error eliminando comentario." }));
            }
          }
        });
      }
      return row;
    }

    function renderList(comments) {
      listHost.innerHTML = "";
      if (!comments.length) {
        listHost.appendChild(el("div", { class: "estrategia-comments-empty", text: "Sin comentarios todavía." }));
        return;
      }
      comments.forEach((c) => {
        listHost.appendChild(buildCommentRow(c));
      });
    }

    listHost.innerHTML = '<div class="estrategia-comments-empty">Cargando comentarios&hellip;</div>';
    fetchPositionComments(positionId).then((comments) => {
      renderList(comments);
    }).catch(() => {
      listHost.innerHTML = '';
      listHost.appendChild(el("div", { class: "estrategia-comments-error", text: "Error cargando comentarios." }));
    });

    async function submitComment() {
      const text = input.value.trim();
      if (!text) return; // mirrors backend's 400 guard -- never POST empty/whitespace
      addBtn.disabled = true;
      input.disabled = true;
      try {
        const added = await postPositionComment(positionId, text, magic);
        const emptyEl = listHost.querySelector(".estrategia-comments-empty");
        if (emptyEl) emptyEl.remove();
        listHost.appendChild(buildCommentRow(added));
        input.value = "";
      } catch (e) {
        if (window.SENTINEL.toast) {
          window.SENTINEL.toast.show(`Error añadiendo comentario: ${e.message}`, { type: "error" });
        } else {
          listHost.appendChild(el("div", { class: "estrategia-comments-error", text: "Error añadiendo comentario." }));
        }
      } finally {
        addBtn.disabled = false;
        input.disabled = false;
        input.focus();
      }
    }

    addBtn.addEventListener("click", submitComment);
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        submitComment();
      }
    });
  }

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

  function buildHumanoDetailPanel(container, selection, onClose, opts) {
    opts = opts || {};
    injectHumanoCss();
    const panel = el("div", { class: "positions-humano-panel" });
    const header = el("div", { class: "positions-humano-panel-header" });
    header.innerHTML = `<strong>Detalle posici&oacute;n</strong>`;
    const closeBtn = el("button", { type: "button", class: "positions-humano-panel-close", title: "Cerrar" });
    closeBtn.textContent = "×";
    header.appendChild(closeBtn);
    panel.appendChild(header);

    // Task 1b: per-strategy chart toolbar (native TF switch + indicator
    // selector) mounts here, ABOVE the chart itself. Populated async once the
    // position's magic resolves against /api/strategies/chart-specs (below);
    // stays empty (no toolbar) for HUMANO/legacy positions whose magic has no
    // spec, or while the specs fetch is in flight.
    const chartToolbarHost = el("div", { class: "estrategia-chart-toolbar-host" });
    panel.appendChild(chartToolbarHost);

    const chartHost = el("div", { class: "positions-humano-panel-chart" });
    panel.appendChild(chartHost);

    const detailHost = el("div", { class: "positions-humano-panel-detail" });
    panel.appendChild(detailHost);
    // ESTRATEGIA (summaryCard): show the attractive position summary card
    // directly under the chart instead of the raw key/value dump. HUMANO keeps
    // the raw detail table (it has no separate context card).
    if (opts.summaryCard) {
      const g = selection.group || {};
      const c = selection.kind === "child" ? selection.child : (g.children || [])[0] || {};
      renderPositionSummaryPanel(detailHost, Object.assign({ __group: g }, c));
    } else {
      renderDetailTable(detailHost, selection);
    }

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
    let panelBarSource = null;
    const symbol = (selection.group && selection.group.symbol) || "";
    if (window.SENTINEL.chart) {
      chartInst = window.SENTINEL.chart.create(chartHost, { symbol, tf });
      // Register + SELECT the position so the chart behaves EXACTLY like Trade
      // View: chart.selectTrade owns scale/glow/RECENTER (entry->exit span at
      // ~80% width, gap-immune) plus the entry/exit markers and the dotted
      // connector line between them. Works for OPEN positions too -- ts_out is
      // null, so selectTrade centers on the entry bar (no exit marker yet).
      if (chartInst && tIn != null) {
        const trade = {
          trade_id: child.position_id,
          signal_id: child.position_id,
          side: child.side,
          ts_in: tIn,
          px_in: child.px_in,
          ts_out: tOut,          // null while the position is still open
          px_out: child.px_out,
          sl: child.sl,
          tp: child.tp,
        };
        chartInst.addTradeMarkers([trade], null, { dim: false });
        Promise.resolve(chartInst.selectTrade(trade)).catch(() => { /* noop */ });
      }
      // Optional replay source (only when adapters + chartData are present):
      // the Replay button reveals this same window bar-by-bar.
      if (chartInst && window.SENTINEL.adapters && window.SENTINEL.chartData
          && window.SENTINEL.chartData.createBarSource) {
        panelBarSource = window.SENTINEL.chartData.createBarSource({ symbol, tf });
      }
    } else {
      chartHost.innerHTML = '<div class="positions-panel-chart-unavailable">Chart no disponible.</div>';
    }

    // Task 1b: resolve the position's magic -> chart-spec (async; the panel
    // above already opened at DEFAULT_TF/generic so there's no dead time).
    // MUST map by MAGIC, never strategy_id (deals_raw.strategy_id isn't a
    // config id) -- group.magic comes straight off /api/positions.
    // wireStrategyChart's own setTF (when the spec's tf is servable and
    // differs) reuses chart.js's setTF-then-reselect-trade path, so the
    // selection/centering above still holds after the native-tf switch.
    let stratChartTeardown = null;
    let panelClosed = false;
    if (chartInst) {
      const magic = selection.group && selection.group.magic;
      if (magic != null) {
        fetchMagicSpecIndex().then((byMagic) => {
          if (panelClosed) return;
          const spec = byMagic.get(magic) || null;
          if (!spec) return; // no spec for this magic (HUMANO/legacy) -> generic chart, unchanged
          stratChartTeardown = wireStrategyChart(chartToolbarHost, chartInst, spec, symbol);
        }).catch(() => { /* noop -- generic chart stays as-is */ });
      }
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
      panelClosed = true;
      document.removeEventListener("keydown", escHandler);
      if (aiStream) { try { aiStream.abort(); } catch (e) { /* noop */ } aiStream = null; }
      if (stratChartTeardown) { try { stratChartTeardown(); } catch (e) { /* noop */ } stratChartTeardown = null; }
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
    let selectedStrategyId = null;   // persists across re-renders (reimport/estado)
    let strategyGroups = {};         // strategy_id -> [position group]
    let vt = null;
    let posPanelHandle = null;       // live chart+replay panel teardown
    let humanoTabHandle = null;
    let estrategiaPollTimer = null;  // live refresh of the SELECTED strategy

    function clearEstrategiaPoll() {
      if (estrategiaPollTimer) { clearInterval(estrategiaPollTimer); estrategiaPollTimer = null; }
    }

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
      clearEstrategiaPoll();
      if (vt) { try { vt.destroy(); } catch (e) { /* noop */ } vt = null; }
      if (posPanelHandle) { try { posPanelHandle.teardown(); } catch (e) { /* noop */ } posPanelHandle = null; }
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

    // ESTRATEGIA tab (2026-07-21): live REAL MT5 positions per connected
    // strategy. Top = selectable strategy cards (scorecard real floor: net /
    // trades / PF / WR / DD). Selecting one lists its real positions
    // (ABIERTA/CERRADA, spread at open/close, beneficio, %); clicking a
    // position opens the live chart+replay panel (buildHumanoDetailPanel).
    function renderEstrategiaTab() {
      body.innerHTML = '<div class="positions-loading">Cargando estrategias en vivo&hellip;</div>';
      loadEstrategiaLive();
    }

    async function loadEstrategiaLive() {
      injectEstrategiaLiveCss();

      let strategies = [];
      try {
        const stratResp = await fetchStrategies();
        strategies = stratResp.strategies || [];
      } catch (e) {
        // Strategy panel is additive; positions can still render without it.
      }

      let groups = [];
      try {
        // High limit: show ALL real strategy positions (current + past), not
        // just the most recent 200 (the roster can accumulate hundreds).
        const posBody = await fetchPositions("strategy", "", "", 5000);
        groups = posBody.groups || [];
      } catch (e) {
        body.innerHTML =
          '<div class="positions-error">Error cargando posiciones en vivo.' +
          '<button type="button" class="positions-retry-btn">Reintentar</button></div>';
        const btn = body.querySelector(".positions-retry-btn");
        if (btn) btn.addEventListener("click", renderEstrategiaTab);
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/positions?origin=strategy", { type: "error" });
        return;
      }

      strategyGroups = {};
      groups.forEach((g) => {
        const sid = g.strategy_id;
        if (!sid) return;
        (strategyGroups[sid] = strategyGroups[sid] || []).push(g);
      });

      // ROBUST FILTER: only strategies that actually have live positions (are
      // present in strategyGroups). Everything else in /api/strategies is a
      // stale artifact (smoke/pedro/sapitos/stac/emasar/…) and must NOT show.
      const liveStrategies = sortStrategiesGraduatedFirst(strategies)
        .filter((s) => Array.isArray(strategyGroups[s.strategy_id]) && strategyGroups[s.strategy_id].length);

      body.innerHTML = "";

      if (!liveStrategies.length) {
        body.innerHTML =
          '<div class="positions-live-empty">Ninguna estrategia con posiciones reales en vivo por ahora.</div>';
        return;
      }

      // Two-column layout (mirrors REVIEW): LEFT = strategy P&L cards (top) +
      // positions list (below); RIGHT = live chart for the selected position.
      const root = el("div", { class: "estrategia-live-root" });
      const leftCol = el("div", { class: "estrategia-live-left" });
      const rightCol = el("div", { class: "estrategia-live-right" });
      root.appendChild(leftCol);
      root.appendChild(rightCol);
      body.appendChild(root);

      const cardsWrap = el("div", { class: "manage-strategy-panel" });
      cardsWrap.appendChild(el("div", { class: "manage-strategy-panel-title", text: "Estrategias en vivo" }));
      const cardsScroll = el("div", { class: "estrategia-cards-scroll" });
      cardsWrap.appendChild(cardsScroll);

      const posWrap = el("div", { class: "positions-live-host" });
      posWrap.appendChild(el("div", { class: "manage-strategy-panel-title", text: "Posiciones en vivo" }));
      const posHost = el("div", { class: "positions-live-host" });
      posWrap.appendChild(posHost);

      leftCol.appendChild(cardsWrap);
      leftCol.appendChild(posWrap);

      // RIGHT column: the live chart+replay panel host (buildHumanoDetailPanel
      // mounts here). Placeholder until a position is chosen.
      const panelHost = el("div", { class: "positions-humano-panel-host" });
      rightCol.appendChild(panelHost);
      function showRightPlaceholder() {
        panelHost.innerHTML =
          '<div class="estrategia-right-placeholder">Elegí una posición de la lista para ver su gráfico con la entrada y la salida marcadas.</div>';
      }
      showRightPlaceholder();

      // Task 2: contextual panel BELOW the chart -- STRATEGY view (selected
      // card, no position row yet) or POSITION view (row clicked). Mounted
      // once, content swapped via showStrategyContext/showPositionContext.
      const contextPanelHost = el("div", { class: "estrategia-context-panel" });
      rightCol.appendChild(contextPanelHost);

      // Task 3: comment box host, appended INSIDE the context panel so it
      // scrolls together with the POSITION card. Only populated in POSITION
      // view; showStrategyContext() clears it (no position selected).
      const commentsHost = el("div", {});

      function selectedStrategyMagic() {
        const gs = strategyGroups[selectedStrategyId] || [];
        return gs.length ? gs[0].magic : null;
      }

      function selectedStrategyName() {
        const s = liveStrategies.find((x) => x.strategy_id === selectedStrategyId);
        return s ? s.name : selectedStrategyId;
      }

      // Shows the STRATEGY view for whatever strategy is currently selected
      // (spec resolved async by magic; renders a neutral note if unresolved
      // or if the magic has no chart-spec).
      function showStrategyContext() {
        // STRATEGY view (no position selected): hide/clear the comment box.
        commentsHost.innerHTML = "";
        const name = selectedStrategyName();
        const magic = selectedStrategyMagic();
        if (magic == null) {
          renderStrategyRulesPanel(contextPanelHost, name, null);
          return;
        }
        contextPanelHost.innerHTML = '<div class="estrategia-context-empty">Cargando ficha de estrategia&hellip;</div>';
        fetchMagicSpecIndex().then((byMagic) => {
          renderStrategyRulesPanel(contextPanelHost, name, byMagic.get(magic) || null);
        }).catch(() => {
          renderStrategyRulesPanel(contextPanelHost, name, null);
        });
      }

      function showPositionContext(row) {
        // The attractive position card now renders directly under the chart
        // (buildHumanoDetailPanel summaryCard); the context panel below shows
        // this position's comments.
        contextPanelHost.innerHTML = "";
        const title = el("div", { class: "estrategia-rules-title" });
        title.innerHTML = "<b>Comentarios de la posición</b>";
        contextPanelHost.appendChild(title);
        contextPanelHost.appendChild(commentsHost);
        const magic = row && row.__group ? row.__group.magic : null;
        renderPositionCommentsBox(commentsHost, row ? row.position_id : null, magic);
      }

      // Flatten a strategy's groups into position rows (one row per group
      // child), each keeping a ref to its parent group for symbol/side + chart
      // context. Order: OPEN positions first, then most-recent entry first.
      function flattenPositionRows(gs) {
        const rows = [];
        (gs || []).forEach((g) => {
          (g.children || []).forEach((c) => {
            rows.push(Object.assign({ __group: g }, c));
          });
        });
        rows.sort((a, b) => {
          if (!!b.is_open - !!a.is_open) return (!!b.is_open) - (!!a.is_open);
          return (epochOf(b.ts_in) || 0) - (epochOf(a.ts_in) || 0);
        });
        return rows;
      }

      function renderPositionsArea() {
        if (vt) { try { vt.destroy(); } catch (e) { /* noop */ } vt = null; }
        if (posPanelHandle) { try { posPanelHandle.teardown(); } catch (e) { /* noop */ } posPanelHandle = null; }
        showRightPlaceholder();
        showStrategyContext();
        posHost.innerHTML = "";
        if (!selectedStrategyId) {
          posHost.innerHTML = '<div class="positions-live-empty">Elegí una estrategia arriba.</div>';
          return;
        }
        const gs = strategyGroups[selectedStrategyId] || [];
        if (!gs.length) {
          posHost.innerHTML = '<div class="positions-live-empty">Esta estrategia todavía no tomó posiciones reales.</div>';
          return;
        }
        const rows = flattenPositionRows(gs);
        const tableEl = el("div", { class: "positions-vtable" });
        posHost.appendChild(tableEl);
        vt = window.SENTINEL.vtable.createVTable(tableEl, {
          columns: livePositionColumns(window.SENTINEL.fmt),
          rows: rows,
          // vtable stores data-key as a STRING and compares it with === to
          // rowKey(row) on click; a numeric position_id would never match the
          // string dataset value, so onRowClick never fired (rows appeared
          // unselectable). Stringify to keep the comparison sound.
          rowKey: (r) => String(r.position_id),
          onRowClick: (r) => {
            const selection = { kind: "child", group: r.__group, child: r };
            window.SENTINEL.appState = window.SENTINEL.appState || {};
            window.SENTINEL.appState.selectedPosition = selection;
            if (posPanelHandle) { try { posPanelHandle.teardown(); } catch (e) { /* noop */ } posPanelHandle = null; }
            showPositionContext(r);
            // On close, restore the placeholder in the right column and go
            // back to the STRATEGY view (deselecting the position).
            posPanelHandle = buildHumanoDetailPanel(panelHost, selection, () => {
              posPanelHandle = null;
              showRightPlaceholder();
              showStrategyContext();
            }, { summaryCard: true });
          },
        });
      }

      function highlightSelected() {
        cardsScroll.querySelectorAll(".estrategia-scard").forEach((c) => {
          c.classList.toggle("selected", c.getAttribute("data-strategy-id") === selectedStrategyId);
        });
      }

      // Live VISUAL refresh (bug d): re-fetch ONLY the selected strategy's
      // positions and update the list + that card's counts/net in place, so
      // opens/closes appear without a manual reload. Does NOT touch the open
      // chart panel (buildHumanoDetailPanel) or any other strategy. The DB
      // itself is always real-time (deals watcher) independent of this poll;
      // this only drives what the operator currently sees. No selection -> the
      // caller never starts the timer, so nothing polls.
      async function refreshSelected() {
        if (!selectedStrategyId) return;
        let groups;
        try {
          const posBody = await fetchPositions("strategy", "", selectedStrategyId, 5000);
          groups = posBody.groups || [];
        } catch (e) {
          return; // transient; the next tick retries
        }
        if (!selectedStrategyId) return; // selection changed while fetching
        strategyGroups[selectedStrategyId] = groups;
        if (vt) vt.setRows(flattenPositionRows(groups));
        // Update the selected card's net + open/closed counts in place.
        const agg = aggregateStrategyGroups(groups);
        const card = cardsScroll.querySelector(
          `.estrategia-scard[data-strategy-id="${selectedStrategyId}"]`);
        if (card) {
          const netEl = card.querySelector(".estrategia-scard-net-value");
          if (netEl) {
            netEl.textContent = window.SENTINEL.fmt.signed(agg.net);
            netEl.className = `estrategia-scard-net-value ${netValueClass(agg.net)} mono`;
          }
          const openEl = card.querySelector(".estrategia-scard-count.open");
          const closedEl = card.querySelector(".estrategia-scard-count.closed");
          if (openEl) openEl.textContent = `● ${agg.open} abiertas`;
          if (closedEl) closedEl.textContent = `${agg.closed} cerradas`;
        }
      }

      function startEstrategiaPoll() {
        clearEstrategiaPoll();
        estrategiaPollTimer = setInterval(refreshSelected, 5000);
      }

      liveStrategies.forEach((s) => {
        const agg = aggregateStrategyGroups(strategyGroups[s.strategy_id]);
        const card = renderStrategyPnlCard(s, agg, renderEstrategiaTab, {
          selected: s.strategy_id === selectedStrategyId,
          connected: true,
          onSelect: () => {
            selectedStrategyId = s.strategy_id;
            highlightSelected();
            renderPositionsArea();
          },
        });
        cardsScroll.appendChild(card);
      });

      // Auto-select the first live strategy on first entry.
      if (!selectedStrategyId || !strategyGroups[selectedStrategyId]) {
        selectedStrategyId = liveStrategies[0].strategy_id;
      }
      highlightSelected();
      renderPositionsArea();
      // Start the live visual refresh now that a strategy is selected.
      startEstrategiaPoll();
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
        clearEstrategiaPoll();
        if (vt) { try { vt.destroy(); } catch (e) { /* noop */ } }
        if (posPanelHandle) { try { posPanelHandle.teardown(); } catch (e) { /* noop */ } }
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
