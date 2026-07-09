// SENTINEL lib/fmt.js — number/timestamp formatters (tabular mono, D.2/D.7).
// Classic script (no ES modules), hangs off window.SENTINEL.fmt.
(function () {
  "use strict";

  function num(value, decimals) {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    const d = decimals === undefined ? 2 : decimals;
    return Number(value).toFixed(d);
  }

  function pct(value, decimals) {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    const d = decimals === undefined ? 1 : decimals;
    return `${Number(value).toFixed(d)}%`;
  }

  function signed(value, decimals) {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    const n = Number(value);
    const d = decimals === undefined ? 2 : decimals;
    const sign = n > 0 ? "+" : "";
    return `${sign}${n.toFixed(d)}`;
  }

  function price(value, decimals) {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    const d = decimals === undefined ? 5 : decimals;
    return Number(value).toFixed(d);
  }

  // epoch seconds or ms → short local timestamp "HH:MM:SS" / "YYYY-MM-DD HH:MM"
  function ts(epoch, opts) {
    if (epoch === null || epoch === undefined) return "--";
    const ms = epoch > 1e12 ? epoch : epoch * 1000;
    const d = new Date(ms);
    if (Number.isNaN(d.getTime())) return "--";
    const short = opts && opts.short;
    const pad = (n) => String(n).padStart(2, "0");
    const hms = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    if (short) return hms;
    const ymd = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    return `${ymd} ${hms}`;
  }

  function tsShort(epoch) {
    return ts(epoch, { short: true });
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.fmt = { num, pct, signed, price, ts, tsShort };
})();
