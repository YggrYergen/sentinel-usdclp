// SENTINEL lib/chartData.js — chart data controller (Task A4, plan §Wave A).
// Chunked bar loader for lib/chart.js: fetches /api/bars in fixed-size
// chunks aligned to a chunk grid, dedupes in-flight requests per chunk,
// caches bars with an LRU cap (evicting the chunk farthest from the current
// view), and merges strictly ascending with duplicate-t protection.
//
// API (plan §Wave A Task A4):
//   const src = window.SENTINEL.chartData.createBarSource({symbol, tf, api});
//   src.ensureRange(fromT, toT) -> Promise   // fetch missing chunks covering [from,to]
//   src.onData(cb)                            // cb(bars) on every merge-commit
//   src.setTf(tf)                             // switch timeframe, clears cache
//   src.coverage()                             // -> Promise<CT-1 coverage payload>
//   src.onNotice(cb)                           // cb({served_tf, tf_requested}) when
//                                               // backend served a coarser TF than requested
//
// Classic script (no ES modules), hangs off window.SENTINEL.chartData.
(function () {
  "use strict";

  const CHUNK_BARS = 1500; // bars per chunk (plan spec: 1500 bars/chunk)
  const MAX_CACHED_BARS = 60000; // LRU cap (plan spec: 60000 bars)

  const TF_SEC = { M1: 60, M2: 120, M5: 300, M10: 600, M15: 900, H1: 3600, D: 86400 };

  function tfSeconds(tf) {
    return TF_SEC[tf] || 60;
  }

  // chunkIndex = floor(t / (CHUNK_BARS * tf_seconds)) -- aligns every chunk
  // to a fixed grid so overlapping ensureRange() calls always resolve to the
  // SAME chunk boundaries (required for in-flight dedupe + cache reuse).
  function chunkIndexOf(t, tfSec) {
    return Math.floor(t / (CHUNK_BARS * tfSec));
  }

  function chunkSpan(tfSec) {
    return CHUNK_BARS * tfSec;
  }

  function chunkKey(tf, idx) {
    return `${tf}:${idx}`;
  }

  function chunkBounds(idx, tfSec) {
    const span = chunkSpan(tfSec);
    return { from: idx * span, to: idx * span + span - tfSec };
  }

  // Default fetch adapter: GET /api/bars?symbol&tf&from&to (epoch seconds).
  function defaultApi() {
    return {
      async getBars({ symbol, tf, from, to }) {
        const usp = new URLSearchParams();
        usp.set("symbol", symbol);
        usp.set("tf", tf);
        usp.set("from", String(from));
        usp.set("to", String(to));
        const resp = await fetch(`/api/bars?${usp.toString()}`);
        if (!resp.ok) throw new Error(`GET /api/bars failed: ${resp.status}`);
        return resp.json();
      },
      async getCoverage({ symbol }) {
        const usp = new URLSearchParams();
        usp.set("symbol", symbol);
        const resp = await fetch(`/api/coverage?${usp.toString()}`);
        if (!resp.ok) throw new Error(`GET /api/coverage failed: ${resp.status}`);
        return resp.json();
      },
    };
  }

  function createBarSource(opts) {
    opts = opts || {};
    let symbol = opts.symbol;
    let tf = opts.tf || "M1";
    const api = opts.api || defaultApi();

    // chunkCache: chunkKey -> { bars: [[t,o,h,l,c,v],...], lastAccessTime }
    // lastAccessTime is set to the view's [from,to] midpoint on every
    // ensureRange() that touches the chunk, so eviction can measure
    // "distance from current view" against it.
    const chunkCache = new Map();
    // in-flight fetch promises per chunkKey, so overlapping ensureRange()
    // calls for the same chunk share a single network request.
    const inFlight = new Map();

    let totalBarCount = 0;
    let mergedBars = []; // full ascending merged bar array across cached chunks
    let lastViewMid = 0; // most recent view midpoint (epoch seconds), for LRU distance

    const dataCallbacks = [];
    const noticeCallbacks = [];

    let coveragePromiseCache = null; // Promise, cached per (symbol,tf) -- coverage is symbol-scoped per CT-1
    let coverageCacheKey = null;

    function onData(cb) {
      if (typeof cb === "function") dataCallbacks.push(cb);
    }

    function onNotice(cb) {
      if (typeof cb === "function") noticeCallbacks.push(cb);
    }

    function emitData() {
      dataCallbacks.forEach((cb) => {
        try { cb(mergedBars.slice()); } catch (e) { /* noop */ }
      });
    }

    function emitNotice(servedTf, tfRequested) {
      noticeCallbacks.forEach((cb) => {
        try { cb({ served_tf: servedTf, tf_requested: tfRequested }); } catch (e) { /* noop */ }
      });
    }

    // Rebuilds the merged ascending bar array from ALL cached chunks
    // (sorted by chunk index), deduping any duplicate `t` that appears
    // across chunk boundaries (overlapping fetches can return an edge bar
    // twice). Strictly ascending; a duplicate t triggers console.error and
    // the duplicate is discarded (spec: never crash).
    function rebuildMerged() {
      const entries = Array.from(chunkCache.entries())
        .filter(([key]) => key.startsWith(`${tf}:`))
        .sort((a, b) => {
          const ia = Number(a[0].split(":")[1]);
          const ib = Number(b[0].split(":")[1]);
          return ia - ib;
        });

      const out = [];
      let lastT = null;
      let count = 0;
      entries.forEach(([, entry]) => {
        entry.bars.forEach((bar) => {
          const t = bar[0];
          if (lastT !== null && t === lastT) {
            console.error(`chartData: duplicate bar t=${t} discarded during merge`);
            return;
          }
          if (lastT !== null && t < lastT) {
            console.error(`chartData: out-of-order bar t=${t} (< lastT=${lastT}) discarded during merge`);
            return;
          }
          out.push(bar);
          lastT = t;
          count += 1;
        });
      });
      mergedBars = out;
      totalBarCount = count;
    }

    // Evicts chunks (of the CURRENT tf) until totalBarCount <= MAX_CACHED_BARS,
    // always evicting the chunk whose bounds are farthest (by distance from
    // its nearest edge) from `lastViewMid`.
    function evictIfNeeded() {
      while (totalBarCount > MAX_CACHED_BARS) {
        let farthestKey = null;
        let farthestDist = -Infinity;
        chunkCache.forEach((entry, key) => {
          if (!key.startsWith(`${tf}:`)) return;
          const idx = Number(key.split(":")[1]);
          const tfSec = tfSeconds(tf);
          const { from, to } = chunkBounds(idx, tfSec);
          const dist = lastViewMid < from ? from - lastViewMid
            : lastViewMid > to ? lastViewMid - to
              : 0;
          if (dist > farthestDist) {
            farthestDist = dist;
            farthestKey = key;
          }
        });
        if (farthestKey === null) break; // nothing left of this tf to evict
        const removed = chunkCache.get(farthestKey);
        chunkCache.delete(farthestKey);
        totalBarCount -= removed ? removed.bars.length : 0;
      }
    }

    async function fetchChunk(idx) {
      const tfSec = tfSeconds(tf);
      const { from, to } = chunkBounds(idx, tfSec);
      const key = chunkKey(tf, idx);

      if (chunkCache.has(key)) return; // already cached
      if (inFlight.has(key)) {
        await inFlight.get(key);
        return;
      }

      const myTf = tf; // guard against a setTf() race while this fetch is out
      const promise = (async () => {
        const body = await api.getBars({ symbol, tf, from, to });
        if (myTf !== tf) return; // superseded by a tf switch; discard
        const bars = (body && body.bars) || [];
        chunkCache.set(key, { bars });
        if (body && body.served_tf && body.tf_requested && body.served_tf !== body.tf_requested) {
          emitNotice(body.served_tf, body.tf_requested);
        }
      })();

      inFlight.set(key, promise);
      try {
        await promise;
      } finally {
        inFlight.delete(key);
      }
    }

    async function ensureRange(fromT, toT) {
      const tfSec = tfSeconds(tf);
      lastViewMid = (Number(fromT) + Number(toT)) / 2;

      const startIdx = chunkIndexOf(Number(fromT), tfSec);
      const endIdx = chunkIndexOf(Number(toT), tfSec);

      const wanted = [];
      for (let idx = startIdx; idx <= endIdx; idx += 1) {
        wanted.push(idx);
      }

      const missing = wanted.filter((idx) => !chunkCache.has(chunkKey(tf, idx)));
      await Promise.all(missing.map((idx) => fetchChunk(idx)));

      rebuildMerged();
      evictIfNeeded();
      rebuildMerged(); // reflect post-eviction state
      emitData();
    }

    function setTf(newTf) {
      if (newTf === tf) return;
      tf = newTf;
      // Cache is keyed by "tf:idx" so stale chunks from the old tf are
      // simply never matched again; clear outright to bound memory.
      chunkCache.clear();
      inFlight.clear();
      mergedBars = [];
      totalBarCount = 0;
      coveragePromiseCache = null;
      coverageCacheKey = null;
    }

    function coverage() {
      const key = `${symbol}:${tf}`;
      if (coveragePromiseCache && coverageCacheKey === key) return coveragePromiseCache;
      coverageCacheKey = key;
      coveragePromiseCache = api.getCoverage({ symbol, tf }).catch((e) => {
        coveragePromiseCache = null; // allow retry on failure
        throw e;
      });
      return coveragePromiseCache;
    }

    return {
      ensureRange,
      onData,
      onNotice,
      setTf,
      coverage,
      // escape hatches (tests/debug only)
      _chunkIndexOf: (t) => chunkIndexOf(t, tfSeconds(tf)),
      _chunkBounds: (idx) => chunkBounds(idx, tfSeconds(tf)),
      get _bars() { return mergedBars.slice(); },
      get _cacheSize() { return totalBarCount; },
      get _cachedChunkKeys() { return Array.from(chunkCache.keys()); },
    };
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.chartData = {
    createBarSource,
    CHUNK_BARS,
    MAX_CACHED_BARS,
    chunkIndexOf,
    chunkBounds,
    tfSeconds,
  };
})();
