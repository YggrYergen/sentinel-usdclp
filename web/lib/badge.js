// SENTINEL lib/badge.js — strategy + fidelity badge components (spec D.3).
// Classic script (no ES modules), hangs off window.SENTINEL.badge.
(function () {
  "use strict";

  // Fixed 12-color palette; order = index; first 3 = celeste/verde/rojo
  // per user directive. color_idx = strategy_seq % 12 (assigned server-side).
  const PALETTE = [
    "#00bfff", "#26a69a", "#ef5350", "#ffb020", "#7c4dff", "#ff6e40",
    "#18ffff", "#f8ff4d", "#4dff91", "#4d9fff", "#ff9e4d", "#ff4d6d",
  ];

  const FIDELITY_COLORS = {
    research: "var(--text-2, #5c6a7d)",
    screening: "var(--accent-amber, #ffb020)",
    "real-tick": "var(--accent-celeste, #00bfff)",
    forward: "var(--long, #26a69a)",
    "live-demo": "var(--short, #ef5350)",
  };

  function colorForIdx(colorIdx) {
    if (colorIdx === null || colorIdx === undefined) return PALETTE[0];
    const i = ((Number(colorIdx) % PALETTE.length) + PALETTE.length) % PALETTE.length;
    return PALETTE[i];
  }

  function displayName(familia, nombre, variantSuffix) {
    const parts = [familia, nombre];
    if (variantSuffix) parts.push(variantSuffix);
    return parts.filter(Boolean).join(" · ");
  }

  // strategyBadge({familia, name, color_idx, variant_suffix, display_name})
  // → HTML string: chip [■ familia] nombre, title = display_name completo.
  function strategyBadge(opts) {
    opts = opts || {};
    const familia = opts.familia || "";
    const name = opts.name || opts.nombre || "";
    const colorIdx = opts.color_idx;
    const color = colorForIdx(colorIdx);
    const title = opts.display_name || displayName(familia, name, opts.variant_suffix);
    return (
      `<span class="sentinel-badge sentinel-badge-strategy" title="${escapeHtml(title)}">` +
      `<span class="sentinel-badge-swatch" style="background:${color}"></span>` +
      `<span class="sentinel-badge-familia mono">${escapeHtml(familia)}</span>` +
      `<span class="sentinel-badge-name">${escapeHtml(name)}</span>` +
      `</span>`
    );
  }

  // fidelityBadge("research"|"screening"|"real-tick"|"forward"|"live-demo")
  function fidelityBadge(fidelity) {
    const color = FIDELITY_COLORS[fidelity] || "var(--text-2, #5c6a7d)";
    const label = fidelity || "--";
    return (
      `<span class="sentinel-badge sentinel-badge-fidelity" ` +
      `style="color:${color};border-color:${color}" title="fidelity: ${escapeHtml(label)}">` +
      `${escapeHtml(label)}</span>`
    );
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.badge = {
    PALETTE, colorForIdx, displayName, strategyBadge, fidelityBadge,
  };
})();
