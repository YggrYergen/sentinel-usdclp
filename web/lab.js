// SENTINEL Lab — Zone A (lever console), Zone B (replay stage), Zone C
// (variant manager + study/fleet boards). Also builds the Regime/News/Study
// right-pane sections (thin gated-placeholder builders reusing the same
// helper — kept in this file to avoid a 4th script tag). Vanilla JS, no
// build step.
(function () {
  "use strict";

  const LAB_INSTRUMENT = "gold"; // default scope; a selector can widen this later

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "text") e.textContent = v;
      else e.setAttribute(k, v);
    }
    for (const child of children || []) e.appendChild(child);
    return e;
  }

  function renderGatedPlaceholder(container, capabilityLabel) {
    container.innerHTML = "";
    container.appendChild(
      el("div", { class: "gated-placeholder" }, [
        document.createTextNode(`${capabilityLabel}: `),
        el("b", { text: "not yet available" }),
        document.createTextNode(" — this surface lights up automatically when its backend is wired."),
      ])
    );
  }

  async function renderLeverConsole(container) {
    let resp;
    try {
      resp = await fetch(`/levers?instrument=${LAB_INSTRUMENT}`);
    } catch (e) {
      renderGatedPlaceholder(container, "Lever console (G1-G7)");
      return;
    }
    if (resp.status !== 200) {
      renderGatedPlaceholder(container, "Lever console (G1-G7)");
      return;
    }
    const body = await resp.json();
    container.innerHTML = "";
    container.appendChild(el("h3", { text: `Levers — ${body.instrument}` }));
    const overrides = {};
    for (const group of body.groups) {
      const groupEl = el("div", { class: "lever-group" });
      groupEl.appendChild(el("div", { style: "font-size:0.72rem;color:#4cc9f0;font-weight:bold;", text: group.name }));
      for (const p of group.params) {
        const row = el("div", { class: "lever-row" });
        const labelRow = el("label");
        const nameSpan = document.createElement("span");
        nameSpan.textContent = p.name;
        const valSpan = document.createElement("span");
        valSpan.className = "hash-chip";
        valSpan.textContent = p.production_value.toFixed(4);
        labelRow.appendChild(nameSpan);
        labelRow.appendChild(valSpan);
        const slider = el("input", {
          type: "range",
          min: String(p.lo),
          max: String(p.hi),
          step: p.is_int ? "1" : String((p.hi - p.lo) / 200),
          value: String(p.production_value),
        });
        slider.addEventListener("input", () => {
          overrides[p.name] = parseFloat(slider.value);
          valSpan.textContent = parseFloat(slider.value).toFixed(4);
          updateVariantHashChip(overrides);
        });
        row.appendChild(labelRow);
        row.appendChild(slider);
        groupEl.appendChild(row);
      }
      container.appendChild(groupEl);
    }
    const hashRow = el("div", { id: "lab-variant-hash", class: "hash-chip", style: "margin-top:0.6rem;" });
    hashRow.textContent = "variant: (unchanged)";
    container.appendChild(hashRow);
  }

  function updateVariantHashChip(overrides) {
    const hashEl = document.getElementById("lab-variant-hash");
    if (!hashEl) return;
    const n = Object.keys(overrides).length;
    hashEl.textContent = n === 0 ? "variant: (unchanged)" : `variant: ${n} override(s) pending (hash computed server-side on save)`;
  }

  async function renderReplayStage(container) {
    const ok = window.SENTINEL ? await window.SENTINEL.probeEndpoint("/replay/control") : false;
    if (!ok) {
      renderGatedPlaceholder(container, "Replay stage (HistoricalFeed)");
      return;
    }
    container.innerHTML = "<div>Replay stage active.</div>";
  }

  async function renderVariantManager(container) {
    const ok = await window.SENTINEL.probeEndpoint("/variants");
    if (!ok) {
      renderGatedPlaceholder(container, "Variant manager / Study / Fleet");
      return;
    }
    container.innerHTML = "<div>Variant manager active.</div>";
  }

  function buildLabSection() {
    const section = document.getElementById("section-lab");
    section.innerHTML = "";
    const grid = el("div", { class: "lab-grid" });
    const zoneA = el("div", { class: "lab-zone", id: "lab-zone-a" });
    const zoneB = el("div", { class: "lab-zone", id: "lab-zone-b" });
    const zoneC = el("div", { class: "lab-zone", id: "lab-zone-c" });
    grid.appendChild(zoneA);
    grid.appendChild(zoneB);
    grid.appendChild(zoneC);
    section.appendChild(grid);
    renderLeverConsole(zoneA);
    renderReplayStage(zoneB);
    renderVariantManager(zoneC);
  }

  window.addEventListener("sentinel:section", (evt) => {
    if (evt.detail === "lab") buildLabSection();
  });

  // Pre-build once on load too (in case Lab is the default tab in future).
  document.addEventListener("DOMContentLoaded", () => {
    const labSection = document.getElementById("section-lab");
    if (labSection && !labSection.hidden) buildLabSection();
  });

  // ── Regime / News / Study sections ──
  function renderGated(container, label) {
    container.innerHTML = "";
    const div = document.createElement("div");
    div.className = "gated-placeholder";
    div.innerHTML = `${label}: <b>not yet available</b> — lights up automatically when its backend is wired.`;
    container.appendChild(div);
  }

  function buildRegimeSection() {
    const section = document.getElementById("section-regime");
    section.innerHTML = "<h3>Regime</h3><div id='regime-body'>Waiting for a snapshot with a non-null `regime` field&hellip;</div>";
    // Regime is always PRESENT on the snapshot (Task 1: defaults to null),
    // so this is genuinely "gated on data" rather than "gated on endpoint" —
    // it renders live the moment any instrument's snapshot.regime is non-null.
    const body = document.getElementById("regime-body");
    const instruments = ["usdclp", "nasdaq", "gold"];
    let any = false;
    for (const inst of instruments) {
      const cfg = (window.SENTINEL && window.SENTINEL.configs) || {};
      if (cfg[inst] && cfg[inst].regime) any = true;
    }
    if (!any) {
      body.innerHTML = `<div class="gated-placeholder">Regime labeling: <b>not yet available</b> (P6) — shows "—" until wired; this section re-renders live once \`snapshot.regime\` is non-null.</div>`;
    }
  }

  async function buildNewsSection() {
    const section = document.getElementById("section-news");
    section.innerHTML = "<h3>News</h3><div id='news-body'></div>";
    const body = document.getElementById("news-body");
    const ok = window.SENTINEL ? await window.SENTINEL.probeEndpoint("/calendar") : false;
    if (!ok) { renderGated(body, "Economic calendar"); return; }
    body.textContent = "Calendar active.";
  }

  async function buildStudySection() {
    const section = document.getElementById("section-study");
    section.innerHTML = "<h3>Study</h3><div id='study-body'></div>";
    const body = document.getElementById("study-body");
    const ok = window.SENTINEL ? await window.SENTINEL.probeEndpoint("/study/latest") : false;
    if (!ok) { renderGated(body, "Study reports (walk-forward leaderboard)"); return; }
    body.textContent = "Study report active.";
  }

  window.addEventListener("sentinel:section", (evt) => {
    if (evt.detail === "regime") buildRegimeSection();
    if (evt.detail === "news") buildNewsSection();
    if (evt.detail === "study") buildStudySection();
  });
})();
