// SENTINEL lib/vtable.js — generic viewport-virtualized, client-side-sortable
// table (M2.1, spec §D.7-RUNS / plan line 214: "tabla virtualizada genérica:
// render por viewport, sort client-side de la página, columnas configurables").
// Classic script (no ES modules), hangs off window.SENTINEL.vtable.
(function () {
  "use strict";

  const ROW_H = 30; // px, fixed row height for viewport math
  const OVERSCAN = 6; // extra rows above/below viewport

  // createVTable(container, {
  //   columns: [{key, label, width, sortable, render(row)->htmlString, sortValue(row)->number|string}],
  //   rows: [...],
  //   rowKey(row) -> string,
  //   onRowClick(row, evt),
  //   selectable: bool,               // renders a leading checkbox column
  //   maxSelected: number,
  //   onSelectionChange(selectedKeys[]),
  //   initialSort: {key, dir},
  // }) -> { setRows(rows), destroy(), getSelected() }
  function createVTable(container, opts) {
    opts = opts || {};
    const columns = opts.columns || [];
    const rowKey = opts.rowKey || ((row, i) => String(i));
    const selectable = !!opts.selectable;
    const maxSelected = opts.maxSelected || 6;
    let rows = opts.rows || [];
    let sortKey = (opts.initialSort && opts.initialSort.key) || null;
    let sortDir = (opts.initialSort && opts.initialSort.dir) || "desc";
    const selected = new Set();

    container.classList.add("vtable-root");
    container.innerHTML =
      '<div class="vtable-head"></div>' +
      '<div class="vtable-viewport"><div class="vtable-spacer-top"></div>' +
      '<div class="vtable-rows"></div><div class="vtable-spacer-bottom"></div></div>';

    const headEl = container.querySelector(".vtable-head");
    const viewportEl = container.querySelector(".vtable-viewport");
    const rowsEl = container.querySelector(".vtable-rows");
    const spacerTop = container.querySelector(".vtable-spacer-top");
    const spacerBottom = container.querySelector(".vtable-spacer-bottom");

    function colTemplate() {
      return columns
        .map((c) => (c.width ? `${c.width}` : "1fr"))
        .join(" ");
    }
    const gridTemplate = (selectable ? "28px " : "") + colTemplate();

    function renderHead() {
      let html = "";
      if (selectable) html += '<div class="vtable-cell vtable-th vtable-th-check"></div>';
      for (const c of columns) {
        const active = c.key === sortKey;
        const arrow = active ? (sortDir === "asc" ? " ▲" : " ▼") : "";
        html += `<div class="vtable-cell vtable-th${c.sortable ? " vtable-th-sortable" : ""}${active ? " vtable-th-active" : ""}" data-key="${c.key}">${c.label}${arrow}</div>`;
      }
      headEl.style.gridTemplateColumns = gridTemplate;
      headEl.innerHTML = html;
      headEl.querySelectorAll(".vtable-th-sortable").forEach((th) => {
        th.addEventListener("click", () => {
          const key = th.dataset.key;
          if (sortKey === key) {
            sortDir = sortDir === "asc" ? "desc" : "asc";
          } else {
            sortKey = key;
            sortDir = "desc";
          }
          applySort();
          renderHead();
          renderViewport();
        });
      });
    }

    function applySort() {
      if (!sortKey) return;
      const col = columns.find((c) => c.key === sortKey);
      if (!col) return;
      const getVal = col.sortValue || ((row) => row[sortKey]);
      const dir = sortDir === "asc" ? 1 : -1;
      rows = rows.slice().sort((a, b) => {
        const va = getVal(a);
        const vb = getVal(b);
        if (va === null || va === undefined) return 1;
        if (vb === null || vb === undefined) return -1;
        if (va < vb) return -1 * dir;
        if (va > vb) return 1 * dir;
        return 0;
      });
    }

    function renderViewport() {
      const total = rows.length;
      const viewportH = viewportEl.clientHeight || 400;
      const scrollTop = viewportEl.scrollTop;
      let start = Math.max(0, Math.floor(scrollTop / ROW_H) - OVERSCAN);
      let visibleCount = Math.ceil(viewportH / ROW_H) + OVERSCAN * 2;
      let end = Math.min(total, start + visibleCount);
      if (total === 0) {
        spacerTop.style.height = "0px";
        spacerBottom.style.height = "0px";
        rowsEl.innerHTML = '<div class="vtable-empty">Sin corridas para los filtros</div>';
        return;
      }
      spacerTop.style.height = `${start * ROW_H}px`;
      spacerBottom.style.height = `${(total - end) * ROW_H}px`;

      let html = "";
      for (let i = start; i < end; i++) {
        const row = rows[i];
        const key = rowKey(row, i);
        const isSelected = selected.has(key);
        html += `<div class="vtable-row" style="grid-template-columns:${gridTemplate};height:${ROW_H}px" data-key="${escapeAttr(key)}">`;
        if (selectable) {
          html += `<div class="vtable-cell vtable-td-check"><input type="checkbox" data-key="${escapeAttr(key)}" ${isSelected ? "checked" : ""}/></div>`;
        }
        for (const c of columns) {
          const content = c.render ? c.render(row) : escapeHtml(row[c.key]);
          html += `<div class="vtable-cell${c.numeric ? " vtable-td-numeric mono" : ""}">${content}</div>`;
        }
        html += "</div>";
      }
      rowsEl.innerHTML = html;
      rowsEl.style.transform = "translateY(0)";

      rowsEl.querySelectorAll(".vtable-row").forEach((rowEl) => {
        rowEl.addEventListener("click", (evt) => {
          if (evt.target && evt.target.matches('input[type="checkbox"]')) return;
          const key = rowEl.dataset.key;
          const row = rows.find((r, i) => rowKey(r, i) === key);
          if (row && typeof opts.onRowClick === "function") opts.onRowClick(row, evt);
        });
      });
      if (selectable) {
        rowsEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
          cb.addEventListener("click", (evt) => evt.stopPropagation());
          cb.addEventListener("change", () => {
            const key = cb.dataset.key;
            if (cb.checked) {
              if (selected.size >= maxSelected) {
                cb.checked = false;
                return;
              }
              selected.add(key);
            } else {
              selected.delete(key);
            }
            if (typeof opts.onSelectionChange === "function") {
              opts.onSelectionChange(Array.from(selected));
            }
          });
        });
      }
    }

    function onScroll() { renderViewport(); }
    viewportEl.addEventListener("scroll", onScroll);
    const resizeObs = typeof ResizeObserver !== "undefined"
      ? new ResizeObserver(() => renderViewport())
      : null;
    if (resizeObs) resizeObs.observe(viewportEl);

    function setRows(newRows) {
      rows = newRows || [];
      applySort();
      viewportEl.scrollTop = 0;
      renderViewport();
    }

    applySort();
    renderHead();
    renderViewport();

    return {
      setRows,
      getSelected: () => Array.from(selected),
      clearSelection: () => { selected.clear(); renderViewport(); },
      destroy: () => {
        viewportEl.removeEventListener("scroll", onScroll);
        if (resizeObs) resizeObs.disconnect();
        container.innerHTML = "";
      },
    };
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function escapeAttr(s) { return escapeHtml(s); }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.vtable = { createVTable };
})();
