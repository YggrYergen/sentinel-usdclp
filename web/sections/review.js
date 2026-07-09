// SENTINEL sections/review.js — TRADE REVIEW section (placeholder, M1.1).
// Real content (run picker, virtualized trade list, shared chart, j/k nav)
// lands in M2.2.
(function () {
  "use strict";

  function render(el) {
    el.innerHTML =
      '<div class="section-placeholder">' +
      "<h2>Trade Review</h2>" +
      "<p>Próximamente (M1.3/M2.x)</p>" +
      "</div>";
  }

  function teardown() {
    // nothing to tear down yet (placeholder)
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.review = { render, teardown };
})();
