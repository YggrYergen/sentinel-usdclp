// SENTINEL sections/positions.js — POSICIONES section (placeholder, M1.1).
// Real content (tabs HUMANO/ESTRATEGIA/IA, forward_session cards,
// re-import button) lands in M2.3.
(function () {
  "use strict";

  function render(el) {
    el.innerHTML =
      '<div class="section-placeholder">' +
      "<h2>Posiciones</h2>" +
      "<p>Próximamente (M1.3/M2.x)</p>" +
      "</div>";
  }

  function teardown() {
    // nothing to tear down yet (placeholder)
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.positions = { render, teardown };
})();
