// SENTINEL lib/vlist.js — generic windowed-rendering (virtualized) list.
// Task A6b (Wave A, lane B): long lists in review.js (run selector groups,
// trade/signal rows) only materialize the rows visible in the viewport
// +-10 rows, backed by a fixed-height spacer so native scrollbars/scroll
// math stay correct. Selection state is keyed by an item id (NOT by DOM
// node identity), so it survives rows scrolling out of and back into the
// viewport across re-renders.
// Classic script (no ES modules), hangs off window.SENTINEL.vlist — same
// export pattern as lib/vtable.js.
(function () {
  "use strict";

  const OVERSCAN = 10; // rows above/below the viewport, per spec ("±10 filas")

  // createVList(container, {
  //   itemHeight: number (px, fixed row height for viewport math),
  //   render: (item, index) -> HTMLElement,
  //   items: [...],
  //   itemKey: (item, index) -> string  (optional; defaults to index) --
  //     used to preserve the "selected" set across scroll/re-render.
  // }) -> { setItems(items), setSelected(keys), getSelected(), scrollToIndex(i), destroy() }
  function createVList(container, opts) {
    opts = opts || {};
    const itemHeight = opts.itemHeight || 30;
    const renderItem = opts.render || (() => document.createElement("div"));
    const itemKey = opts.itemKey || ((item, i) => String(i));
    let items = opts.items || [];
    const selected = new Set();

    container.classList.add("vlist-root");
    // container itself is the scrollable viewport; a spacer div gives it
    // the full scrollHeight (items.length * itemHeight) while a single
    // absolutely-positioned "rows" layer holds only the visible nodes.
    container.innerHTML =
      '<div class="vlist-spacer"></div><div class="vlist-rows"></div>';
    if (!container.style.position) container.style.position = "relative";

    const spacerEl = container.querySelector(".vlist-spacer");
    const rowsEl = container.querySelector(".vlist-rows");
    rowsEl.style.position = "absolute";
    rowsEl.style.top = "0";
    rowsEl.style.left = "0";
    rowsEl.style.right = "0";

    function totalHeight() {
      return items.length * itemHeight;
    }

    function windowBounds() {
      const viewportH = container.clientHeight || 400;
      const scrollTop = container.scrollTop;
      // windowed rendering: only the visible rows +- OVERSCAN rows are
      // materialized, never all N items.
      const firstVisible = Math.floor(scrollTop / itemHeight);
      const lastVisible = Math.ceil((scrollTop + viewportH) / itemHeight);
      const start = Math.max(0, firstVisible - OVERSCAN);
      const end = Math.min(items.length, lastVisible + OVERSCAN);
      return { start, end };
    }

    function renderWindow() {
      spacerEl.style.height = `${totalHeight()}px`;
      if (!items.length) {
        rowsEl.innerHTML = "";
        return;
      }
      const { start, end } = windowBounds();
      rowsEl.innerHTML = "";
      const frag = document.createDocumentFragment();
      for (let i = start; i < end; i++) {
        const item = items[i];
        const key = itemKey(item, i);
        const node = renderItem(item, i);
        if (!node) continue;
        node.style.position = "absolute";
        node.style.top = `${i * itemHeight}px`;
        node.style.left = "0";
        node.style.right = "0";
        node.style.height = `${itemHeight}px`;
        node.dataset.vlistKey = key;
        // selection survives entering/leaving the viewport: it is looked
        // up by `key` (stable per-item id), not by DOM node identity --
        // the node itself is destroyed/recreated every renderWindow().
        if (selected.has(key)) node.classList.add("vlist-selected");
        frag.appendChild(node);
      }
      rowsEl.appendChild(frag);
    }

    function onScroll() { renderWindow(); }
    container.addEventListener("scroll", onScroll);
    const resizeObs = typeof ResizeObserver !== "undefined"
      ? new ResizeObserver(() => renderWindow())
      : null;
    if (resizeObs) resizeObs.observe(container);

    function setItems(newItems) {
      items = newItems || [];
      renderWindow();
    }

    function setSelected(keys) {
      selected.clear();
      (keys || []).forEach((k) => selected.add(String(k)));
      renderWindow();
    }

    function scrollToIndex(i) {
      if (i < 0 || i >= items.length) return;
      container.scrollTop = i * itemHeight;
      renderWindow();
    }

    renderWindow();

    return {
      setItems,
      setSelected,
      getSelected: () => Array.from(selected),
      scrollToIndex,
      destroy: () => {
        container.removeEventListener("scroll", onScroll);
        if (resizeObs) resizeObs.disconnect();
        container.innerHTML = "";
      },
    };
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.vlist = { createVList };
})();
