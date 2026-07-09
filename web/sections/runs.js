// SENTINEL sections/runs.js — RUNS section (placeholder, M1.1).
// Real content (filters, virtualized sortable table, drawer, uPlot compare)
// lands in M2.1.
(function () {
  "use strict";

  function render(el) {
    el.innerHTML =
      '<div class="section-placeholder">' +
      "<h2>Runs</h2>" +
      "<p>Próximamente (M1.3/M2.x)</p>" +
      "</div>";
  }

  function teardown() {
    // nothing to tear down yet (placeholder)
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.runs = { render, teardown };
})();
