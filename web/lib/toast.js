// SENTINEL lib/toast.js — bottom-right toast notifications.
// Classic script (no ES modules), hangs off window.SENTINEL.toast.
(function () {
  "use strict";

  let container = null;

  function ensureContainer() {
    if (container && document.body.contains(container)) return container;
    container = document.createElement("div");
    container.id = "sentinel-toast-container";
    document.body.appendChild(container);
    return container;
  }

  // show(message, {type: "info"|"success"|"error"|"warn", duration: ms})
  function show(message, opts) {
    opts = opts || {};
    const type = opts.type || "info";
    const duration = opts.duration || 4000;
    const el = document.createElement("div");
    el.className = `sentinel-toast sentinel-toast-${type}`;
    el.textContent = message;
    const root = ensureContainer();
    root.appendChild(el);
    requestAnimationFrame(() => el.classList.add("sentinel-toast-visible"));
    window.setTimeout(() => {
      el.classList.remove("sentinel-toast-visible");
      window.setTimeout(() => el.remove(), 300);
    }, duration);
    return el;
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.toast = { show };
})();
