// SENTINEL sections/news.js -- NEWS tab (Task C2, consumes CT-5 frozen
// contract). Filters (symbol/impact/kind selects, client-side re-fetch) +
// vlist (lib/vlist.js) of items + freshness label ("hace N min", recomputed
// on a 60s timer) + SSE /api/news/stream appends new items at top (teardown
// pattern copied from sections/runs.js's streamJob: EventSource stored on
// section state, closed in teardown()).
// Classic script (no ES modules), hangs off window.SENTINEL.sections.news.
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

  function qs(params) {
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === null || v === undefined || v === "") continue;
      usp.set(k, v);
    }
    const s = usp.toString();
    return s ? `?${s}` : "";
  }

  // ---- data fetch (CT-5) ----
  async function fetchNews(filters) {
    const query = qs({
      symbol: filters.symbol,
      impact: filters.impact,
      kind: filters.kind,
      limit: 100,
    });
    const resp = await fetch(`/api/news${query}`);
    if (!resp.ok) throw new Error(`GET /api/news failed: ${resp.status}`);
    return resp.json();
  }

  // ---- freshness ("hace N min") ----
  function epochOf(ts) {
    if (ts === null || ts === undefined) return null;
    if (typeof ts === "number") return ts > 1e12 ? ts / 1000 : ts;
    const d = new Date(ts);
    const t = d.getTime();
    return Number.isNaN(t) ? null : t / 1000;
  }

  function freshnessLabel(ts) {
    const epoch = epochOf(ts);
    if (epoch === null) return "--";
    const nowS = Date.now() / 1000;
    let mins = Math.floor((nowS - epoch) / 60);
    if (mins < 0) mins = 0;
    return `hace ${mins} min`;
  }

  // ---- item row ----
  function renderNewsItem(item) {
    const row = el("div", { class: "news-item-row", "data-news-id": item.id });
    const impactHtml = item.impact
      ? `<span class="news-impact-badge news-impact-${escapeHtml(item.impact)}">${escapeHtml(item.impact)}</span>`
      : "";
    const symbolsHtml = (item.symbols || [])
      .map((s) => `<span class="news-symbol-badge">${escapeHtml(s)}</span>`)
      .join("");
    const titleHtml = item.url
      ? `<a class="news-item-title" href="${escapeHtml(item.url)}" target="_blank" rel="noopener">${escapeHtml(item.title || "")}</a>`
      : `<span class="news-item-title">${escapeHtml(item.title || "")}</span>`;
    row.innerHTML = `
      <div class="news-item-top">
        ${titleHtml}
        <span class="news-item-freshness" data-ts="${escapeHtml(String(item.ts))}">${freshnessLabel(item.ts)}</span>
      </div>
      <div class="news-item-meta">
        <span class="news-item-source">${escapeHtml(item.source || "")}</span>
        <span class="news-item-kind">${escapeHtml(item.kind || "")}</span>
        ${impactHtml}
        ${symbolsHtml}
      </div>`;
    return row;
  }

  // ---- section-scoped CSS ----
  const NEWS_CSS_ID = "news-section-css";
  const NEWS_CSS = `
    .news-section { display: flex; flex-direction: column; height: 100%; }
    .news-filterbar { display: flex; gap: 8px; padding: 8px; }
    .news-filterbar select { padding: 2px 6px; }
    .news-list-host { flex: 1; min-height: 0; }
    .news-item-row { display: flex; flex-direction: column; gap: 2px; padding: 6px 10px; box-sizing: border-box; border-bottom: 1px solid var(--border, #333); }
    .news-item-top { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
    .news-item-title { text-decoration: none; }
    .news-item-freshness { font-size: 0.7rem; opacity: 0.65; white-space: nowrap; }
    .news-item-meta { display: flex; gap: 6px; font-size: 0.7rem; opacity: 0.8; }
    .news-empty { padding: 16px; opacity: 0.7; }
  `;

  function injectNewsCss() {
    if (document.getElementById(NEWS_CSS_ID)) return;
    const style = document.createElement("style");
    style.id = NEWS_CSS_ID;
    style.textContent = NEWS_CSS;
    document.head.appendChild(style);
  }

  // ---- filter bar ----
  function renderFilterBar(root, onChange) {
    const bar = el("div", { class: "news-filterbar" });

    const symbolSel = el("select", { class: "news-filter-symbol" }, [
      el("option", { value: "", text: "Symbol: todos" }),
      ...["XAUUSD", "USDCLP", "NASDAQ"].map((v) => el("option", { value: v, text: v })),
    ]);
    symbolSel.addEventListener("change", () => onChange({ symbol: symbolSel.value }));

    const impactSel = el("select", { class: "news-filter-impact" }, [
      el("option", { value: "", text: "Impact: todos" }),
      ...["high", "medium", "low"].map((v) => el("option", { value: v, text: v })),
    ]);
    impactSel.addEventListener("change", () => onChange({ impact: impactSel.value }));

    const kindSel = el("select", { class: "news-filter-kind" }, [
      el("option", { value: "", text: "Kind: todos" }),
      ...["news", "calendar"].map((v) => el("option", { value: v, text: v })),
    ]);
    kindSel.addEventListener("change", () => onChange({ kind: kindSel.value }));

    bar.appendChild(symbolSel);
    bar.appendChild(impactSel);
    bar.appendChild(kindSel);
    root.appendChild(bar);
    return bar;
  }

  // ---- SSE stream (REV-5 teardown pattern from sections/runs.js) ----
  function openStream(onItem) {
    let es;
    try {
      es = new EventSource("/api/news/stream");
    } catch (e) {
      return null;
    }
    es.addEventListener("news_item", (evt) => {
      let data;
      try {
        data = JSON.parse(evt.data);
      } catch (e) {
        return;
      }
      onItem(data);
    });
    es.onerror = () => {
      // keep listening; EventSource auto-reconnects per spec (retry: 3000)
    };
    return es;
  }

  // ---- main render ----
  function render(mountEl) {
    injectNewsCss();
    mountEl.innerHTML = "";
    const root = el("div", { class: "news-section" });
    mountEl.appendChild(root);

    const filterBarHost = el("div", {});
    const listHost = el("div", { class: "news-list-host" });
    root.appendChild(filterBarHost);
    root.appendChild(listHost);

    let items = [];
    let currentFilters = {};
    let nvlist = null;

    function itemKey(item) {
      return String(item.id);
    }

    async function loadNews() {
      let body;
      try {
        body = await fetchNews(currentFilters);
      } catch (e) {
        listHost.innerHTML = '<div class="news-empty">Error cargando /api/news.</div>';
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/news", { type: "error" });
        return;
      }
      items = body.items || [];
      if (!items.length) {
        listHost.innerHTML = '<div class="news-empty">Sin noticias para los filtros</div>';
        nvlist = null;
        return;
      }
      listHost.innerHTML = "";
      nvlist = window.SENTINEL.vlist.createVList(listHost, {
        itemHeight: 56,
        items,
        itemKey,
        render: renderNewsItem,
      });
    }

    renderFilterBar(filterBarHost, (patch) => {
      Object.assign(currentFilters, patch);
      loadNews();
    });

    loadNews();

    // SSE: new items append at top of the current in-memory list (client
    // side only; does not re-fetch/re-apply filters).
    const es = openStream((item) => {
      items = [item, ...items];
      if (nvlist) {
        nvlist.setItems(items);
      } else {
        listHost.innerHTML = "";
        nvlist = window.SENTINEL.vlist.createVList(listHost, {
          itemHeight: 56,
          items,
          itemKey,
          render: renderNewsItem,
        });
      }
    });

    // freshness re-render timer: recompute "hace N min" labels every 60s
    // without a full re-fetch/re-render of the list.
    const freshnessTimer = window.setInterval(() => {
      listHost.querySelectorAll(".news-item-freshness").forEach((elx) => {
        const ts = elx.getAttribute("data-ts");
        elx.textContent = freshnessLabel(ts === "null" ? null : Number(ts) || ts);
      });
    }, 60000);

    state = { root, activeEventSource: es, freshnessTimer };
  }

  function teardown() {
    if (state) {
      if (state.activeEventSource) {
        try { state.activeEventSource.close(); } catch (e) { /* noop */ }
        state.activeEventSource = null;
      }
      if (state.freshnessTimer) {
        window.clearInterval(state.freshnessTimer);
        state.freshnessTimer = null;
      }
      if (state.root) state.root.innerHTML = "";
    }
    state = null;
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.news = { render, teardown };
})();
