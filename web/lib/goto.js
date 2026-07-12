// SENTINEL lib/goto.js — Task A7: goto-date control shared helper.
// Pure clamp/format logic + a small DOM factory (datetime-local input + "Ir"
// button) reused by CHARTS (sections/charts.js) and REVIEW/TV
// (sections/review.js) toolbars. Classic script (no ES modules), hangs off
// window.SENTINEL.goto.
//
// Coverage (CT-1, GET /api/coverage?symbol=) is fetched ONCE per
// (symbol,tf) via a module-level cache keyed "symbol:tf" -- chart.js does
// not expose its internal barSource, so this module owns its own small
// cache rather than re-fetching on every "Ir" click.
(function () {
  "use strict";

  const TF_SEC = { M1: 60, M2: 120, M5: 300, M10: 600, M15: 900, H1: 3600, D: 86400 };

  function tfSeconds(tf) {
    return TF_SEC[tf] || 60;
  }

  // clampToCoverage(targetEpochSec, coverageForTf) -> {epoch, clamped, reason}
  // coverageForTf is CT-1's tfs[tf] shape {first,last} (epoch seconds), or
  // undefined/null if the tf is absent from the lake (CT-1: "TF ausente del
  // lake => key ausente").
  function clampToCoverage(targetEpochSec, coverageForTf) {
    if (!coverageForTf) {
      return { epoch: targetEpochSec, clamped: false, reason: null };
    }
    const { first, last } = coverageForTf;
    if (targetEpochSec < first) {
      return { epoch: first, clamped: true, reason: "before-first" };
    }
    if (targetEpochSec > last) {
      return { epoch: last, clamped: true, reason: "after-last" };
    }
    return { epoch: targetEpochSec, clamped: false, reason: null };
  }

  // windowAround(targetEpochSec, tf) -> {from, to} spanning +-150 bars, per
  // spec's `ensureRange(target-150*tf, target+150*tf)`.
  function windowAround(targetEpochSec, tf) {
    const span = 150 * tfSeconds(tf);
    return { from: targetEpochSec - span, to: targetEpochSec + span };
  }

  // datetimeLocalToEpoch("2026-07-12T10:30") -> epoch seconds (UTC). The
  // <input type="datetime-local"> value has no timezone; interpreted as UTC
  // to match CT-1's epoch-seconds-UTC contract.
  function datetimeLocalToEpoch(value) {
    if (!value) return null;
    const iso = value.length === 16 ? `${value}:00Z` : `${value}Z`;
    const ms = Date.parse(iso);
    if (Number.isNaN(ms)) return null;
    return Math.floor(ms / 1000);
  }

  function epochToDatetimeLocal(epochSec) {
    const d = new Date(epochSec * 1000);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  }

  function formatFirstTs(epochSec) {
    return epochToDatetimeLocal(epochSec).replace("T", " ");
  }

  // ---- coverage cache (fetched once per symbol,tf) ----
  const coverageCache = new Map(); // symbol -> Promise<CT-1 payload>

  function fetchCoverage(symbol) {
    if (!coverageCache.has(symbol)) {
      const usp = new URLSearchParams({ symbol });
      coverageCache.set(
        symbol,
        fetch(`/api/coverage?${usp.toString()}`).then((resp) => {
          if (!resp.ok) throw new Error(`GET /api/coverage failed: ${resp.status}`);
          return resp.json();
        }).catch((e) => {
          coverageCache.delete(symbol);
          throw e;
        }),
      );
    }
    return coverageCache.get(symbol);
  }

  // ---- DOM factory ----
  // createGotoControl(host, {getSymbol, getTf, getChartInst}) appends a
  // datetime-local input + "Ir" button to `host`, wired to clamp against
  // CT-1 coverage then call chartInst.setWindow(from, to) (chart.js's
  // setWindow already does the fetch/ensure + setVisibleRange in one call).
  function createGotoControl(host, callbacks) {
    callbacks = callbacks || {};
    const wrap = document.createElement("div");
    wrap.className = "charts-toolbar-group goto-control";

    const input = document.createElement("input");
    input.type = "datetime-local";
    input.className = "goto-datetime-input";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "goto-btn";
    btn.textContent = "Ir";

    async function onGo() {
      const target = datetimeLocalToEpoch(input.value);
      if (target === null) return;
      const symbol = callbacks.getSymbol ? callbacks.getSymbol() : null;
      const tf = callbacks.getTf ? callbacks.getTf() : "M1";
      const chartInst = callbacks.getChartInst ? callbacks.getChartInst() : null;
      if (!symbol || !chartInst) return;

      let coverage;
      try {
        coverage = await fetchCoverage(symbol);
      } catch (e) {
        coverage = null;
      }
      const covForTf = coverage && coverage.tfs ? coverage.tfs[tf] : null;
      const result = clampToCoverage(target, covForTf);
      if (result.clamped && covForTf) {
        const msg = result.reason === "before-first"
          ? `Sin datos antes de ${formatFirstTs(covForTf.first)} en ${tf}`
          : `Sin datos después de ${formatFirstTs(covForTf.last)} en ${tf}`;
        if (window.SENTINEL.toast) {
          window.SENTINEL.toast.show(msg, { type: "warn" });
        } else {
          wrap.title = msg;
        }
      }
      const win = windowAround(result.epoch, tf);
      chartInst.setWindow(win.from, win.to);
    }

    btn.addEventListener("click", onGo);

    wrap.appendChild(input);
    wrap.appendChild(btn);
    host.appendChild(wrap);

    return { el: wrap, input, btn };
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.goto = {
    clampToCoverage,
    windowAround,
    datetimeLocalToEpoch,
    epochToDatetimeLocal,
    fetchCoverage,
    createGotoControl,
  };
})();
