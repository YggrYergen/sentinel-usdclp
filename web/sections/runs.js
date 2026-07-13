// SENTINEL sections/runs.js — RUNS section (M2.1, plan §D.7-RUNS NORMATIVE).
// Filter bar + virtualized sortable table (lib/vtable.js) + right drawer
// (full metrics + .htm evidence link + "Ver trades -> REVIEW") + compare
// modal (uPlot: overlaid equity curves or comparative bars, D.3 color/dash).
// Classic script (no ES modules), hangs off window.SENTINEL.sections.runs.
(function () {
  "use strict";

  const FIDELITIES = ["research", "screening", "real-tick", "forward", "live-demo"];
  const FIDELITY_TFS = ["M1", "M2", "M5", "M15", "H1", "D"];
  const DASH_PATTERNS = [[], [6, 4], [1, 3]]; // solid, dashed, dotted (uPlot dash arrays)

  let state = null; // per-mount state, rebuilt on render()

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "text") e.textContent = v;
      else if (k === "html") e.innerHTML = v;
      else e.setAttribute(k, v);
    }
    for (const child of children || []) e.appendChild(child);
    return e;
  }

  function qs(params) {
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === null || v === undefined || v === "") continue;
      if (Array.isArray(v)) { if (v.length) usp.set(k, v.join(",")); continue; }
      usp.set(k, v);
    }
    const s = usp.toString();
    return s ? `?${s}` : "";
  }

  // ---- badge helpers (D.3 R note: familia==name -> show once) ----
  function runBadgeHtml(row) {
    const familia = row.familia || "";
    const name = row.display_name || row.familia || "";
    // display_name is often "{familia} · {nombre} · {suffix}"; if familia
    // equals the bare strategy name (current data quirk), avoid duplicating.
    let nombre = name;
    if (familia && name && name.startsWith(`${familia} ·`)) {
      nombre = name.slice(familia.length + 2).trim();
    }
    if (familia && nombre && familia.toLowerCase() === nombre.toLowerCase()) {
      nombre = ""; // show familia once only
    }
    return window.SENTINEL.badge.strategyBadge({
      familia,
      name: nombre,
      color_idx: row.color_idx,
      display_name: row.display_name,
    });
  }

  // ---- data fetch ----
  async function fetchRuns(filters) {
    const query = qs({
      strategy_id: filters.strategy_ids && filters.strategy_ids.length ? filters.strategy_ids.join(",") : "",
      instrumento: filters.instrumento,
      engine: filters.engine,
      fidelity: filters.fidelity,
      desde: filters.desde,
      hasta: filters.hasta,
      order_by: filters.order_by || "fecha_corrida",
      dir: filters.dir || "desc",
      limit: 500,
      offset: 0,
    });
    const resp = await fetch(`/api/runs${query}`);
    if (!resp.ok) throw new Error(`GET /api/runs failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchStrategies() {
    const resp = await fetch("/api/strategies");
    if (!resp.ok) throw new Error(`GET /api/strategies failed: ${resp.status}`);
    return resp.json();
  }

  async function fetchRun(runId) {
    const resp = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
    if (!resp.ok) throw new Error(`GET /api/runs/${runId} failed: ${resp.status}`);
    return resp.json();
  }

  // ---- table columns (D.7-RUNS: badge estrategia · variant_id mono · instr ·
  // fidelity badge · trades · net · PF · WR% · payoff · maxDD · sharpe · fecha) ----
  function buildColumns(onBacktestClick) {
    const fmt = window.SENTINEL.fmt;
    const badge = window.SENTINEL.badge;
    return [
      { key: "strategy", label: "Estrategia", width: "180px", render: (r) => runBadgeHtml(r) },
      { key: "variant_id", label: "Variante", width: "170px", sortable: true,
        render: (r) => `<span class="mono">${escapeHtml(r.variant_id || "--")}</span>` },
      { key: "instrumento", label: "Instr", width: "80px", sortable: true, render: (r) => escapeHtml(r.instrumento || "--") },
      { key: "fidelity", label: "Fidelity", width: "90px", sortable: true, render: (r) => badge.fidelityBadge(r.fidelity) },
      { key: "trades", label: "Trades", width: "70px", sortable: true, numeric: true, render: (r) => fmt.num(r.trades, 0) },
      { key: "net", label: "Net", width: "90px", sortable: true, numeric: true,
        render: (r) => `<span class="${signClass(r.net)}">${fmt.signed(r.net)}</span>` },
      { key: "pf", label: "PF", width: "70px", sortable: true, numeric: true,
        render: (r) => `<span class="${signClass((r.pf ?? 1) - 1)}">${fmt.num(r.pf)}</span>` },
      { key: "wr", label: "WR%", width: "70px", sortable: true, numeric: true, render: (r) => fmt.pct(r.wr) },
      { key: "payoff", label: "Payoff", width: "80px", sortable: true, numeric: true, render: (r) => fmt.num(r.payoff) },
      { key: "maxdd", label: "MaxDD", width: "80px", sortable: true, numeric: true, render: (r) => fmt.num(r.maxdd) },
      { key: "sharpe", label: "Sharpe", width: "80px", sortable: true, numeric: true, render: (r) => fmt.num(r.sharpe) },
      { key: "fecha_corrida", label: "Fecha", width: "110px", sortable: true, render: (r) => escapeHtml(r.fecha_corrida || "--") },
      { key: "meta", label: "Meta", width: "150px",
        render: (r) => `${r.engine ? `<span class="sentinel-badge sentinel-badge-engine" title="engine">${escapeHtml(r.engine)}</span>` : ""}` +
          `${r.origin ? `<span class="sentinel-badge sentinel-badge-origin" title="origin">${escapeHtml(r.origin)}</span>` : ""}` },
      { key: "actions", label: "", width: "110px",
        render: (r) => `<button type="button" class="runs-backtest-btn" data-variant-id="${escapeHtml(r.variant_id || "")}">&#9654; Backtest</button>` },
    ];
  }

  function signClass(v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "";
    return Number(v) > 0 ? "sentinel-sign-pos" : Number(v) < 0 ? "sentinel-sign-neg" : "";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // ---- schema-driven "+ Variante" modal (M2.7) ----
  // Builds param_delta fields from the strategy's param_schema_json (a
  // {param_name: default_value} or {param_name: {type,default}} shaped
  // object as produced by the registry; we treat any JSON-serializable
  // shape leniently: object keys become text inputs, values pre-fill).
  function parseParamSchema(strategy) {
    const raw = strategy && (strategy.param_schema_json || strategy.param_schema);
    if (!raw) return {};
    if (typeof raw === "object") return raw;
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function openCreateVariantModal(strategies, onCreated) {
    const overlay = el("div", { class: "modal-overlay" });
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
    const modal = el("div", { class: "modal-box manage-variant-modal" });

    const stratOptions = strategies.map((s) =>
      `<option value="${escapeHtml(s.strategy_id)}">${escapeHtml(s.display_name || `${s.familia} · ${s.name}`)}</option>`
    ).join("");

    modal.innerHTML = `
      <div class="modal-header">
        <h3>&#65291; Variante</h3>
        <button type="button" class="modal-close" aria-label="Cerrar">&times;</button>
      </div>
      <form class="manage-form">
        <label class="manage-field">
          <span>Estrategia</span>
          <select class="manage-input" name="strategy_id" required>${stratOptions}</select>
        </label>
        <label class="manage-field">
          <span>Sufijo de variante</span>
          <input class="manage-input" name="variant_suffix" type="text" required placeholder="ej. M5_c2_sar3m3" />
        </label>
        <label class="manage-field">
          <span>TF</span>
          <input class="manage-input" name="tf" type="text" placeholder="M5" />
        </label>
        <label class="manage-field">
          <span>Instrumento</span>
          <input class="manage-input" name="instrumento" type="text" placeholder="XAUUSD" />
        </label>
        <label class="manage-field">
          <span>Modo salida</span>
          <input class="manage-input" name="modo_salida" type="text" placeholder="sl_tp" />
        </label>
        <div class="manage-params-editor"></div>
        <div class="manage-form-error" hidden></div>
        <div class="manage-form-actions">
          <button type="submit" class="manage-submit-btn">Crear</button>
        </div>
      </form>`;
    modal.querySelector(".modal-close").addEventListener("click", () => overlay.remove());
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const form = modal.querySelector(".manage-form");
    const stratSel = form.querySelector('[name="strategy_id"]');
    const paramsHost = form.querySelector(".manage-params-editor");
    const errBox = form.querySelector(".manage-form-error");

    function renderParamFields() {
      paramsHost.innerHTML = "";
      const strategy = strategies.find((s) => s.strategy_id === stratSel.value);
      const schema = parseParamSchema(strategy);
      const keys = Object.keys(schema);
      if (!keys.length) return;
      paramsHost.appendChild(el("div", { class: "manage-params-title", text: "params_delta" }));
      keys.forEach((k) => {
        const row = el("label", { class: "manage-field manage-param-field" });
        const defaultVal = schema[k] && typeof schema[k] === "object" && "default" in schema[k] ? schema[k].default : schema[k];
        row.innerHTML = `<span>${escapeHtml(k)}</span><input class="manage-input manage-param-input" data-param-key="${escapeHtml(k)}" type="text" placeholder="${escapeHtml(defaultVal == null ? "" : String(defaultVal))}" />`;
        paramsHost.appendChild(row);
      });
    }
    stratSel.addEventListener("change", renderParamFields);
    renderParamFields();

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errBox.hidden = true;
      const submitBtn = form.querySelector(".manage-submit-btn");
      submitBtn.disabled = true;
      submitBtn.textContent = "Creando…";
      const paramsDelta = {};
      paramsHost.querySelectorAll(".manage-param-input").forEach((input) => {
        if (input.value !== "") {
          const num = Number(input.value);
          paramsDelta[input.dataset.paramKey] = Number.isNaN(num) ? input.value : num;
        }
      });
      const body = {
        strategy_id: stratSel.value,
        variant_suffix: form.variant_suffix.value.trim(),
        params_delta: paramsDelta,
        tf: form.tf.value.trim() || null,
        instrumento: form.instrumento.value.trim() || null,
        modo_salida: form.modo_salida.value.trim() || null,
      };
      try {
        const resp = await fetch("/api/variants", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const json = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          const code = json && json.error && json.error.code;
          if (code === "variant_exists") {
            errBox.hidden = false;
            errBox.textContent = "Esta variante ya existe.";
          } else {
            errBox.hidden = false;
            errBox.textContent = (json && json.error && json.error.message) || `Error creando variante (${resp.status})`;
          }
          submitBtn.disabled = false;
          submitBtn.textContent = "Crear";
          return;
        }
        if (window.SENTINEL.toast) {
          window.SENTINEL.toast.show(`Variante creada: ${json.variant_id}`, { type: "success" });
        }
        overlay.remove();
        if (onCreated) onCreated();
      } catch (err) {
        errBox.hidden = false;
        errBox.textContent = "Error de red creando variante.";
        submitBtn.disabled = false;
        submitBtn.textContent = "Crear";
      }
    });
  }

  // ---- "▶ Backtest" modal + job polling (M2.7) ----
  function openBacktestModal(variantId, onDone) {
    const overlay = el("div", { class: "modal-overlay" });
    overlay.addEventListener("click", (e) => { if (e.target === overlay && !overlay.dataset.busy) overlay.remove(); });
    const modal = el("div", { class: "modal-box manage-backtest-modal" });
    modal.innerHTML = `
      <div class="modal-header">
        <h3>&#9654; Backtest &middot; <span class="mono">${escapeHtml(variantId)}</span></h3>
        <button type="button" class="modal-close" aria-label="Cerrar">&times;</button>
      </div>
      <form class="manage-form">
        <label class="manage-field">
          <span>Symbol</span>
          <input class="manage-input" name="symbol" type="text" required placeholder="XAUUSD" />
        </label>
        <label class="manage-field">
          <span>TF</span>
          <input class="manage-input" name="tf" type="text" required placeholder="M5" />
        </label>
        <label class="manage-field">
          <span>Desde</span>
          <input class="manage-input" name="desde" type="date" />
        </label>
        <label class="manage-field">
          <span>Hasta</span>
          <input class="manage-input" name="hasta" type="date" />
        </label>
        <div class="manage-form-error" hidden></div>
        <div class="manage-job-progress" hidden></div>
        <div class="manage-form-actions">
          <button type="submit" class="manage-submit-btn">Correr backtest</button>
        </div>
      </form>`;
    modal.querySelector(".modal-close").addEventListener("click", () => { if (!overlay.dataset.busy) overlay.remove(); });
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const form = modal.querySelector(".manage-form");
    const errBox = form.querySelector(".manage-form-error");
    const progressBox = form.querySelector(".manage-job-progress");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errBox.hidden = true;
      const submitBtn = form.querySelector(".manage-submit-btn");
      submitBtn.disabled = true;
      overlay.dataset.busy = "1";
      progressBox.hidden = false;
      progressBox.textContent = "Encolando job…";
      const body = {
        variant_id: variantId,
        symbol: form.symbol.value.trim(),
        tf: form.tf.value.trim(),
        desde: form.desde.value || null,
        hasta: form.hasta.value || null,
      };
      try {
        const resp = await fetch("/api/backtest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const json = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          errBox.hidden = false;
          errBox.textContent = (json && json.error && json.error.message) || `Error POST /api/backtest (${resp.status})`;
          submitBtn.disabled = false;
          delete overlay.dataset.busy;
          progressBox.hidden = true;
          return;
        }
        pollJob(json.job_id, progressBox, () => {
          delete overlay.dataset.busy;
          overlay.remove();
          if (onDone) onDone();
        }, (msg) => {
          errBox.hidden = false;
          errBox.textContent = msg;
          submitBtn.disabled = false;
          delete overlay.dataset.busy;
          progressBox.hidden = true;
        });
      } catch (err) {
        errBox.hidden = false;
        errBox.textContent = "Error de red en POST /api/backtest.";
        submitBtn.disabled = false;
        delete overlay.dataset.busy;
        progressBox.hidden = true;
      }
    });
  }

  function pollJob(jobId, progressBox, onDone, onError) {
    const started = Date.now();
    const timer = window.setInterval(async () => {
      let job;
      try {
        const resp = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
        job = await resp.json();
        if (!resp.ok) throw new Error((job && job.error && job.error.message) || `GET /api/jobs/${jobId} failed`);
      } catch (e) {
        window.clearInterval(timer);
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error consultando job de backtest", { type: "error" });
        onError("Error consultando el job.");
        return;
      }
      const elapsedS = Math.round((Date.now() - started) / 1000);
      if (job.status === "queued" || job.status === "running") {
        progressBox.textContent = `${job.status}… (${elapsedS}s)`;
        return;
      }
      window.clearInterval(timer);
      if (job.status === "done") {
        if (window.SENTINEL.toast) {
          window.SENTINEL.toast.show(`Backtest listo: run ${job.run_id}`, { type: "success" });
        }
        onDone();
      } else {
        if (window.SENTINEL.toast) {
          window.SENTINEL.toast.show(`Backtest falló: ${job.error || "error desconocido"}`, { type: "error" });
        }
        onError(job.error || "Backtest falló.");
      }
    }, 1000);
  }

  // ---- CT-1 coverage fetch (min/max bounds for period pickers) ----
  async function fetchCoverage(symbol) {
    const resp = await fetch(`/api/coverage?symbol=${encodeURIComponent(symbol)}`);
    if (!resp.ok) throw new Error(`GET /api/coverage failed: ${resp.status}`);
    return resp.json();
  }

  function epochToDateStr(epochSec) {
    if (epochSec === null || epochSec === undefined) return "";
    const d = new Date(epochSec * 1000);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
  }

  // ---- "Nueva corrida" launcher panel (B7, CT-4 first UI consumer) ----
  // variant select + symbol select + TF select + period pickers bounded by
  // CT-1 /api/coverage (min/max attrs on the date inputs => out-of-range is
  // impossible via the input itself) + exploratory toggle (default ON) +
  // submit -> POST /api/jobs/backtest -> progress via GET /api/jobs/stream
  // (SSE, job_update events, filtered by this job's job_id).
  function renderLauncherPanel(root, runRows, onRunCreated) {
    const panel = el("div", { class: "runs-launcher" });
    // variant/symbol options: no dedicated GET /api/variants endpoint exists
    // yet, so we derive them (deduped) from the runs already loaded in the
    // table -- same data source runs.js already consumes today.
    const seen = new Set();
    const variantOptions = [];
    (runRows || []).forEach((r) => {
      if (!r.variant_id || seen.has(r.variant_id)) return;
      seen.add(r.variant_id);
      variantOptions.push({ variant_id: r.variant_id, label: r.variant_id, instrumento: r.instrumento, tf: r.tf });
    });

    panel.innerHTML = `
      <h4>Nueva corrida</h4>
      <form class="runs-launcher-form">
        <label class="runs-launcher-field">
          <span>Variante</span>
          <select class="runs-launcher-input" name="variant_id" required>
            <option value="">-- seleccionar --</option>
            ${variantOptions.map((v) => `<option value="${escapeHtml(v.variant_id)}">${escapeHtml(v.label)}</option>`).join("")}
          </select>
        </label>
        <label class="runs-launcher-field">
          <span>Symbol</span>
          <select class="runs-launcher-input" name="symbol" required>
            <option value="">-- seleccionar --</option>
          </select>
        </label>
        <label class="runs-launcher-field">
          <span>TF</span>
          <select class="runs-launcher-input" name="tf" required>
            <option value="">-- seleccionar --</option>
            ${FIDELITY_TFS.map((tf) => `<option value="${tf}">${tf}</option>`).join("")}
          </select>
        </label>
        <label class="runs-launcher-field">
          <span>Desde</span>
          <input class="runs-launcher-input" name="from" type="date" disabled />
        </label>
        <label class="runs-launcher-field">
          <span>Hasta</span>
          <input class="runs-launcher-input" name="to" type="date" disabled />
        </label>
        <label class="runs-launcher-field runs-launcher-toggle">
          <input type="checkbox" name="exploratory" checked />
          <span>Exploratoria (no cuenta para graduación)</span>
        </label>
        <div class="runs-launcher-error" hidden></div>
        <div class="runs-launcher-progress" hidden></div>
        <div class="runs-launcher-actions">
          <button type="submit" class="runs-launcher-submit-btn">Lanzar backtest</button>
        </div>
      </form>`;
    root.appendChild(panel);

    const form = panel.querySelector(".runs-launcher-form");
    const symbolSel = form.querySelector('[name="symbol"]');
    const fromInput = form.querySelector('[name="from"]');
    const toInput = form.querySelector('[name="to"]');
    const errBox = form.querySelector(".runs-launcher-error");
    const progressBox = form.querySelector(".runs-launcher-progress");

    // symbol options: derive from known instrumentos on variants (fallback:
    // free-text-like small set is unavailable without a dedicated endpoint,
    // so we source it from the variants list actually offered above).
    const symbolSet = new Set(variantOptions.map((v) => v.instrumento).filter(Boolean));
    symbolSet.forEach((sym) => {
      symbolSel.appendChild(el("option", { value: sym, text: sym }));
    });

    async function applyCoverageBounds() {
      const symbol = symbolSel.value;
      const tf = form.tf.value;
      if (!symbol || !tf) {
        fromInput.disabled = true;
        toInput.disabled = true;
        return;
      }
      try {
        const cov = await fetchCoverage(symbol);
        const tfCov = cov.tfs && cov.tfs[tf];
        if (tfCov) {
          const minStr = epochToDateStr(tfCov.first);
          const maxStr = epochToDateStr(tfCov.last);
          fromInput.setAttribute("min", minStr);
          fromInput.setAttribute("max", maxStr);
          toInput.setAttribute("min", minStr);
          toInput.setAttribute("max", maxStr);
          fromInput.disabled = false;
          toInput.disabled = false;
        } else {
          fromInput.disabled = true;
          toInput.disabled = true;
        }
      } catch (e) {
        fromInput.disabled = true;
        toInput.disabled = true;
      }
    }
    symbolSel.addEventListener("change", applyCoverageBounds);
    form.tf.addEventListener("change", applyCoverageBounds);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errBox.hidden = true;
      const submitBtn = form.querySelector(".runs-launcher-submit-btn");
      submitBtn.disabled = true;
      progressBox.hidden = false;
      progressBox.textContent = "Encolando job…";
      const body = {
        variant_id: form.variant_id.value,
        symbol: symbolSel.value,
        tf: form.tf.value,
        from: fromInput.value || null,
        to: toInput.value || null,
        exploratory: form.exploratory.checked,
      };
      try {
        const resp = await fetch("/api/jobs/backtest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const json = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          errBox.hidden = false;
          errBox.textContent = (json && json.error && json.error.message) || `Error POST /api/jobs/backtest (${resp.status})`;
          submitBtn.disabled = false;
          progressBox.hidden = true;
          return;
        }
        streamJob(json.job_id, progressBox, (runId) => {
          submitBtn.disabled = false;
          progressBox.innerHTML = `Listo &rarr; <a href="#" class="runs-launcher-run-link" data-run-id="${escapeHtml(runId)}">ver run ${escapeHtml(runId)}</a>`;
          progressBox.querySelector(".runs-launcher-run-link").addEventListener("click", (ev) => {
            ev.preventDefault();
            openDrawer({ run_id: runId });
          });
          if (onRunCreated) onRunCreated();
        }, (msg) => {
          errBox.hidden = false;
          errBox.textContent = msg;
          submitBtn.disabled = false;
          progressBox.hidden = true;
        });
      } catch (err) {
        errBox.hidden = false;
        errBox.textContent = "Error de red en POST /api/jobs/backtest.";
        submitBtn.disabled = false;
        progressBox.hidden = true;
      }
    });

    return panel;
  }

  // ---- CT-9 SSE progress via GET /api/jobs/stream, filtered by job_id ----
  function streamJob(jobId, progressBox, onDone, onError) {
    let es;
    try {
      es = new EventSource("/api/jobs/stream");
    } catch (e) {
      onError("No se pudo abrir /api/jobs/stream.");
      return;
    }
    es.addEventListener("job_update", (evt) => {
      let data;
      try {
        data = JSON.parse(evt.data);
      } catch (e) {
        return;
      }
      if (data.job_id && data.job_id !== jobId) return;
      if (data.status === "queued" || data.status === "running") {
        const pct = data.progress !== undefined && data.progress !== null ? ` ${Math.round(data.progress * 100)}%` : "";
        progressBox.textContent = `${data.status}…${pct}`;
        return;
      }
      if (data.status === "done") {
        es.close();
        onDone(data.run_id);
      } else if (data.status === "error") {
        es.close();
        onError(data.error || "Backtest falló.");
      }
    });
    es.onerror = () => {
      // keep listening; EventSource auto-reconnects per spec (retry: 3000)
    };
  }

  // ---- filter bar ----
  function renderFilterBar(root, strategies, onChange) {
    const bar = el("div", { class: "runs-filterbar" });

    const stratWrap = el("div", { class: "runs-filter-group" }, [
      el("label", { text: "Estrategia" }),
    ]);
    const stratChips = el("div", { class: "runs-strategy-chips" });
    const selectedStrategies = new Set();
    strategies.forEach((s) => {
      const chip = el("button", { class: "runs-strategy-chip", type: "button" });
      chip.innerHTML = window.SENTINEL.badge.strategyBadge({
        familia: s.familia, name: s.familia && s.familia.toLowerCase() === (s.name || "").toLowerCase() ? "" : s.name,
        color_idx: s.color_idx, display_name: `${s.name} (${s.n_runs} runs)`,
      });
      chip.dataset.strategyId = s.strategy_id;
      chip.addEventListener("click", () => {
        if (selectedStrategies.has(s.strategy_id)) {
          selectedStrategies.delete(s.strategy_id);
          chip.classList.remove("active");
        } else {
          selectedStrategies.add(s.strategy_id);
          chip.classList.add("active");
        }
        onChange({ strategy_ids: Array.from(selectedStrategies) });
      });
      stratChips.appendChild(chip);
    });
    stratWrap.appendChild(stratChips);

    const instrInput = el("input", { type: "text", placeholder: "Instrumento", class: "runs-filter-input" });
    instrInput.addEventListener("change", () => onChange({ instrumento: instrInput.value.trim() }));

    const engineSel = el("select", { class: "runs-filter-input" }, [
      el("option", { value: "", text: "Engine: todos" }),
      ...["sentinel-replay", "sentinel-sim", "mt5-tester", "nt8-manual"].map((v) => el("option", { value: v, text: v })),
    ]);
    engineSel.addEventListener("change", () => onChange({ engine: engineSel.value }));

    const fidSel = el("select", { class: "runs-filter-input" }, [
      el("option", { value: "", text: "Fidelity: todas" }),
      ...FIDELITIES.map((v) => el("option", { value: v, text: v })),
    ]);
    fidSel.addEventListener("change", () => onChange({ fidelity: fidSel.value }));

    const desdeInput = el("input", { type: "date", class: "runs-filter-input" });
    desdeInput.addEventListener("change", () => onChange({ desde: desdeInput.value }));
    const hastaInput = el("input", { type: "date", class: "runs-filter-input" });
    hastaInput.addEventListener("change", () => onChange({ hasta: hastaInput.value }));

    bar.appendChild(stratWrap);
    bar.appendChild(el("div", { class: "runs-filter-group" }, [el("label", { text: "Instrumento" }), instrInput]));
    bar.appendChild(el("div", { class: "runs-filter-group" }, [engineSel]));
    bar.appendChild(el("div", { class: "runs-filter-group" }, [fidSel]));
    bar.appendChild(el("div", { class: "runs-filter-group" }, [
      el("label", { text: "Desde" }), desdeInput, el("label", { text: "Hasta" }), hastaInput,
    ]));

    root.appendChild(bar);
    return bar;
  }

  // ---- drawer ----
  function openDrawer(row) {
    closeDrawer();
    const overlay = el("div", { class: "runs-drawer-overlay" });
    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeDrawer(); });
    const drawer = el("div", { class: "runs-drawer" });

    const fmt = window.SENTINEL.fmt;
    drawer.innerHTML = `
      <div class="runs-drawer-header">
        ${runBadgeHtml(row)} ${window.SENTINEL.badge.fidelityBadge(row.fidelity)}
        <button type="button" class="runs-drawer-close" aria-label="Cerrar">&times;</button>
      </div>
      <div class="runs-drawer-body">
        <div class="runs-drawer-loading">Cargando métricas…</div>
      </div>`;
    drawer.querySelector(".runs-drawer-close").addEventListener("click", closeDrawer);
    overlay.appendChild(drawer);
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add("visible"));

    fetchRun(row.run_id).then((full) => {
      const body = drawer.querySelector(".runs-drawer-body");
      const metricsRows = [
        ["Run ID", full.run_id], ["Variant", full.variant_id],
        ["Instrumento", full.instrumento], ["Engine", full.engine],
        ["Ventana", `${full.periodo_desde || "--"} → ${full.periodo_hasta || "--"}`],
        ["Modelo sim", full.modelo_sim || "--"],
        ["Trades", fmt.num(full.trades, 0)], ["Net", fmt.signed(full.net)],
        ["PF", fmt.num(full.pf)], ["WR%", fmt.pct(full.wr)],
        ["Payoff", fmt.num(full.payoff)], ["MaxDD", fmt.num(full.maxdd)],
        ["Sharpe", fmt.num(full.sharpe)], ["Creada", full.fecha_corrida || "--"],
      ];
      const grid = metricsRows.map(([k, v]) => (
        `<div class="runs-drawer-metric"><span class="runs-drawer-metric-label">${escapeHtml(k)}</span>` +
        `<span class="runs-drawer-metric-value mono">${escapeHtml(String(v))}</span></div>`
      )).join("");

      const artifacts = full.artifacts || {};
      const reportPath = artifacts.report_path || full.report_path;
      let evidenceHtml = "";
      if (reportPath) {
        const normalized = String(reportPath).replace(/\\/g, "/");
        const href = /^[a-zA-Z]:\//.test(normalized) ? `file:///${normalized}` : `file:///${normalized}`;
        evidenceHtml = `<a class="runs-drawer-evidence" href="${escapeHtml(href)}" target="_blank" rel="noopener">Ver evidencia (.htm) &#8599;</a>`;
      }

      body.innerHTML = `
        <div class="runs-drawer-grid">${grid}</div>
        ${evidenceHtml}
        <button type="button" class="runs-drawer-review-btn">Ver trades &rarr; REVIEW</button>`;
      body.querySelector(".runs-drawer-review-btn").addEventListener("click", () => {
        window.SENTINEL.appState = window.SENTINEL.appState || {};
        window.SENTINEL.appState.selectedRun = full.run_id;
        const reviewBtn = document.querySelector('.nav-btn[data-section="review"]');
        if (reviewBtn) reviewBtn.click();
      });
    }).catch(() => {
      const body = drawer.querySelector(".runs-drawer-body");
      body.innerHTML = '<div class="runs-drawer-error">Error cargando el run.</div>';
    });
  }

  function closeDrawer() {
    const overlay = document.querySelector(".runs-drawer-overlay");
    if (overlay) overlay.remove();
  }

  // ---- compare modal (uPlot) ----
  function openCompareModal(selectedRows) {
    const overlay = el("div", { class: "runs-compare-overlay" });
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
    const modal = el("div", { class: "runs-compare-modal" });
    modal.innerHTML = `
      <div class="runs-compare-header">
        <h3>Comparar corridas</h3>
        <button type="button" class="runs-compare-close">&times;</button>
      </div>
      <div class="runs-compare-legend"></div>
      <div class="runs-compare-chart"></div>`;
    modal.querySelector(".runs-compare-close").addEventListener("click", () => overlay.remove());
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const legend = modal.querySelector(".runs-compare-legend");
    const chartEl = modal.querySelector(".runs-compare-chart");
    const badge = window.SENTINEL.badge;

    selectedRows.forEach((row, i) => {
      const dashLabel = i === 0 ? "solid" : i === 1 ? "dashed" : "dotted";
      const chip = el("div", { class: "runs-compare-legend-item" });
      chip.innerHTML = `${runBadgeHtml(row)} <span class="runs-compare-dash-label">(${dashLabel})</span>`;
      legend.appendChild(chip);
    });

    const hasEquity = selectedRows.some((r) => r.equity_path);
    if (hasEquity && typeof uPlot !== "undefined") {
      // Equity curves are not fetched from a dedicated endpoint in M2.1 (no
      // contract for it in D.6); fall back to comparative bars whenever we
      // cannot resolve series data client-side. This keeps the modal honest
      // rather than fabricating a curve.
      renderCompareBars(chartEl, selectedRows, badge);
    } else {
      renderCompareBars(chartEl, selectedRows, badge);
    }
  }

  function renderCompareBars(chartEl, rows, badge) {
    if (typeof uPlot === "undefined") {
      chartEl.textContent = "uPlot no disponible.";
      return;
    }
    const metrics = ["net", "pf", "wr", "maxdd"];
    const labels = ["Net", "PF", "WR%", "MaxDD"];
    const xs = metrics.map((_, i) => i);
    const series = [{}];
    const data = [xs];
    rows.forEach((row, idx) => {
      data.push(metrics.map((m) => Number(row[m]) || 0));
      series.push({
        label: row.display_name || row.variant_id,
        stroke: badge.colorForIdx(row.color_idx),
        width: 2,
        dash: DASH_PATTERNS[idx % DASH_PATTERNS.length],
        points: { show: true },
      });
    });
    const opts = {
      width: chartEl.clientWidth || 640,
      height: 320,
      series,
      axes: [{ values: (u, vals) => vals.map((v) => labels[v] || "") }, {}],
      scales: { x: { time: false } },
    };
    // eslint-disable-next-line no-undef
    new uPlot(opts, data, chartEl);
  }

  // ---- states ----
  function renderLoading(container) {
    container.innerHTML = '<div class="runs-skeleton">Cargando corridas&hellip;</div>';
  }
  function renderError(container, onRetry) {
    container.innerHTML = "";
    const box = el("div", { class: "runs-error" }, [
      el("p", { text: "Error cargando corridas." }),
      el("button", { type: "button", text: "Reintentar" }),
    ]);
    box.querySelector("button").addEventListener("click", onRetry);
    container.appendChild(box);
  }

  // ---- main render ----
  function render(el0) {
    el0.innerHTML = "";
    const root = el("div", { class: "runs-section" });
    el0.appendChild(root);

    const toolbarHost = el("div", { class: "runs-toolbar" });
    const addVariantBtn = el("button", { type: "button", class: "manage-add-variant-btn", text: "＋ Variante" });
    toolbarHost.appendChild(addVariantBtn);
    const launcherHost = el("div", { class: "runs-launcher-host" });
    const filterBarHost = el("div", { class: "runs-filterbar-host" });
    const tableHost = el("div", { class: "runs-table-host" });
    const compareBarHost = el("div", { class: "runs-compare-bar", hidden: "hidden" }, [
      el("span", { class: "runs-compare-count", text: "0 seleccionadas (max 6)" }),
      el("button", { type: "button", class: "runs-compare-btn", text: "Comparar" }),
    ]);

    root.appendChild(toolbarHost);
    root.appendChild(launcherHost);
    root.appendChild(filterBarHost);
    root.appendChild(compareBarHost);
    root.appendChild(tableHost);

    let vt = null;
    let currentFilters = { order_by: "fecha_corrida", dir: "desc" };
    let strategiesById = {};
    let allStrategies = [];

    addVariantBtn.addEventListener("click", () => {
      if (!allStrategies.length) {
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Sin estrategias disponibles todavía", { type: "warn" });
        return;
      }
      openCreateVariantModal(allStrategies, () => { loadRuns(); });
    });

    async function loadStrategiesAndBar() {
      try {
        const body = await fetchStrategies();
        strategiesById = {};
        allStrategies = body.strategies || [];
        allStrategies.forEach((s) => { strategiesById[s.strategy_id] = s; });
        renderFilterBar(filterBarHost, body.strategies || [], (patch) => {
          Object.assign(currentFilters, patch);
          loadRuns();
        });
      } catch (e) {
        // filters still usable without strategy chips; runs table load will
        // surface its own error/toast.
      }
    }

    async function loadRuns() {
      renderLoading(tableHost);
      let body;
      try {
        body = await fetchRuns(currentFilters);
      } catch (e) {
        if (window.SENTINEL.toast) window.SENTINEL.toast.show("Error cargando /api/runs", { type: "error" });
        renderError(tableHost, loadRuns);
        return;
      }
      const rows = body.rows || [];
      launcherHost.innerHTML = "";
      renderLauncherPanel(launcherHost, rows, () => loadRuns());
      tableHost.innerHTML = "";
      if (!rows.length) {
        tableHost.innerHTML = '<div class="runs-empty">Sin corridas para los filtros</div>';
        updateCompareBar([]);
        return;
      }
      const tableEl = el("div", { class: "runs-vtable" });
      tableHost.appendChild(tableEl);
      // Event delegation for the per-row "Backtest" button: vtable re-renders
      // row DOM on scroll/sort, so a single listener on the table root
      // (rather than per-render binding) survives those re-renders.
      // Capture phase: fires before the row's own click listener (added
      // directly on .vtable-row by vtable.js), so stopping propagation
      // here reliably prevents the drawer from also opening.
      tableEl.addEventListener("click", (e) => {
        const btn = e.target.closest(".runs-backtest-btn");
        if (!btn) return;
        e.stopPropagation();
        const variantId = btn.dataset.variantId;
        if (variantId) openBacktestModal(variantId, () => loadRuns());
      }, true);
      vt = window.SENTINEL.vtable.createVTable(tableEl, {
        columns: buildColumns(),
        rows,
        rowKey: (r) => r.run_id,
        selectable: true,
        maxSelected: 6,
        initialSort: { key: currentFilters.order_by || "fecha_corrida", dir: currentFilters.dir || "desc" },
        onRowClick: (row) => openDrawer(row),
        onSelectionChange: (keys) => updateCompareBar(keys, rows),
      });
    }

    function updateCompareBar(keys, rows) {
      const countEl = compareBarHost.querySelector(".runs-compare-count");
      countEl.textContent = `${keys.length} seleccionadas (max 6)`;
      compareBarHost.hidden = keys.length === 0;
      const btn = compareBarHost.querySelector(".runs-compare-btn");
      btn.onclick = () => {
        if (!rows) return;
        const selectedRows = rows.filter((r) => keys.includes(r.run_id));
        if (selectedRows.length) openCompareModal(selectedRows);
      };
    }

    loadStrategiesAndBar();
    loadRuns();

    state = { root, vt: () => vt };
  }

  function teardown() {
    closeDrawer();
    const compareOverlay = document.querySelector(".runs-compare-overlay");
    if (compareOverlay) compareOverlay.remove();
    if (state && state.root) state.root.innerHTML = "";
    state = null;
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.sections = window.SENTINEL.sections || {};
  window.SENTINEL.sections.runs = { render, teardown };
})();
