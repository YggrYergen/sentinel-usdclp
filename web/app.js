// SENTINEL thin frontend (P3 Task 3.4/3.5).
// Vanilla JS, no build step, no CDN — uPlot is vendored under /vendor/uplot.
// Renders the SAME fields the golden Snapshot.to_dict() schema exposes:
// composite_score, direction, signal, technical.tf_scores (per-TF), macro,
// levels, alerts, divergences, symbol/seq/config_hash/ts (see the
// SNAPSHOT_FIELDS set mirrored in tests/service/test_ui_parity.py).
(function () {
  "use strict";

  const statusEl = document.getElementById("conn-status");
  const metaEl = document.getElementById("meta-line");
  const select = document.getElementById("instrument-select");

  const MAX_POINTS = 120;
  const history = { seq: [], score: [] };

  let ws = null;
  let reconnectDelayMs = 500;
  const MAX_RECONNECT_DELAY_MS = 10000;

  let chart = null;

  function wsUrl(instrument) {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/stream?instrument=${encodeURIComponent(instrument)}`;
  }

  function setStatus(state, label) {
    statusEl.className = state;
    statusEl.textContent = label;
  }

  function connect() {
    const instrument = select.value;
    setStatus("connecting", "connecting…");
    ws = new WebSocket(wsUrl(instrument));

    ws.onopen = () => {
      reconnectDelayMs = 500;
      setStatus("connected", "connected");
    };

    ws.onmessage = (evt) => {
      let snapshot;
      try {
        snapshot = JSON.parse(evt.data);
      } catch (err) {
        return;
      }
      render(snapshot);
    };

    ws.onclose = () => {
      setStatus("disconnected", "disconnected — retrying…");
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function scheduleReconnect() {
    setTimeout(connect, reconnectDelayMs);
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, MAX_RECONNECT_DELAY_MS);
  }

  function reconnectNow() {
    history.seq.length = 0;
    history.score.length = 0;
    if (ws) {
      ws.onclose = null; // avoid double-reconnect
      ws.close();
    }
    connect();
  }

  select.addEventListener("change", reconnectNow);

  // ── rendering ─────────────────────────────────────────────────────
  function render(snap) {
    metaEl.textContent =
      `symbol=${snap.symbol} seq=${snap.seq} config_hash=${snap.config_hash}` +
      (snap.ts ? ` ts=${snap.ts}` : "");

    renderComposite(snap);
    renderTechnical(snap.technical);
    renderMacro(snap.macro);
    renderLevels(snap.levels);
    renderList("alerts-list", snap.alerts);
    renderList("divergences-list", snap.divergences, (d) =>
      typeof d === "string" ? d : d.description || JSON.stringify(d)
    );
  }

  function renderComposite(snap) {
    const scoreEl = document.getElementById("composite-score");
    const dirEl = document.getElementById("composite-direction");
    const sigEl = document.getElementById("composite-signal");

    scoreEl.textContent = snap.composite_score;
    dirEl.textContent = `direction: ${snap.direction}`;
    dirEl.className = `meta direction-${snap.direction}`;
    sigEl.textContent = `signal: ${snap.signal}` + (snap.blocked ? ` (blocked: ${snap.block_reason})` : "");

    history.seq.push(snap.seq);
    history.score.push(snap.composite_score);
    if (history.seq.length > MAX_POINTS) {
      history.seq.shift();
      history.score.shift();
    }
    updateChart();
  }

  function updateChart() {
    const el = document.getElementById("composite-chart");
    const noChartNote = document.getElementById("no-chart-note");

    if (typeof window.uPlot === "undefined") {
      // uPlot failed to load — degrade to the table-only view (already
      // rendered) and flag it, per the NO-CDN fallback contract.
      noChartNote.hidden = false;
      return;
    }

    const data = [history.seq, history.score];
    if (chart === null) {
      chart = new window.uPlot(
        {
          width: el.clientWidth || 260,
          height: 150,
          scales: { x: { time: false } },
          series: [
            { label: "seq" },
            { label: "composite_score", stroke: "#2ecc71", width: 2 },
          ],
        },
        data,
        el
      );
    } else {
      chart.setData(data);
    }
  }

  function renderTechnical(technical) {
    const tbody = document.querySelector("#tf-table tbody");
    tbody.innerHTML = "";
    if (!technical || !technical.tf_scores) return;
    for (const [tf, tfData] of Object.entries(technical.tf_scores)) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${tf}</td><td>${tfData.score}</td><td class="direction-${tfData.direction}">${tfData.direction}</td>`;
      tbody.appendChild(tr);
    }
  }

  function renderMacro(macro) {
    const tbody = document.querySelector("#macro-table tbody");
    tbody.innerHTML = "";
    if (!macro) return;
    const rows = [
      ["score", macro.score],
      ["direction", macro.direction],
      ["consensus_score", macro.consensus_score],
      ["confidence_avg", macro.confidence_avg],
      ["assets_warmed_up", `${macro.assets_warmed_up}/${macro.total_assets_tracked}`],
    ];
    for (const [k, v] of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<th>${k}</th><td>${v}</td>`;
      tbody.appendChild(tr);
    }
  }

  function renderLevels(levels) {
    const tbody = document.querySelector("#levels-table tbody");
    tbody.innerHTML = "";
    if (!levels || !levels.combined) return;
    const { above = [], below = [] } = levels.combined;
    for (const lvl of above) {
      appendLevelRow(tbody, "above", lvl);
    }
    for (const lvl of below) {
      appendLevelRow(tbody, "below", lvl);
    }
  }

  function appendLevelRow(tbody, side, lvl) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${side}</td><td>${lvl.label}</td><td>${lvl.price}</td><td>${lvl.pct}</td>`;
    tbody.appendChild(tr);
  }

  function renderList(elId, items, toText) {
    const ul = document.getElementById(elId);
    ul.innerHTML = "";
    if (!items) return;
    for (const item of items) {
      const li = document.createElement("li");
      li.textContent = toText ? toText(item) : item;
      ul.appendChild(li);
    }
  }

  // ── boot ──────────────────────────────────────────────────────────
  connect();
})();
