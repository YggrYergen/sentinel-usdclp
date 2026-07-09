// SENTINEL sections/charts.js — CHARTS section (placeholder, M1.1).
// Real content (lightweight-charts, toolbar, overlays) lands in M1.3.
(function () {
  "use strict";

  function render(el) {
    el.innerHTML =
      '<div class="section-placeholder">' +
      "<h2>Charts</h2>" +
      "<p>Próximamente (M1.3/M2.x)</p>" +
      "</div>";
  }

  function teardown() {
    // nothing to tear down yet (placeholder)
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.charts = { render, teardown };
})();
