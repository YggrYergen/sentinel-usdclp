// SENTINEL UI v2 — left-column v2 replica + WS client + top bar (UI rework).
// Vanilla JS, no build step, no CDN. Ports sentinel/instrument_panel.py's
// exact HTML/CSS/math (velocity, acceleration, fusion, tooltips) into JS,
// driven purely by Snapshot.to_dict() fields already served by app.py.
(function () {
  "use strict";

  const INSTRUMENTS = ["usdclp", "nasdaq", "gold"];
  const LABELS = { usdclp: "USD/CLP", nasdaq: "NQ100", gold: "XAUUSD" };
  const EMOJI = { usdclp: "⚡", nasdaq: "💻", gold: "🥇" };
  const CN = {
    dxy: "DXY", copper: "Cu", wti: "WTI", usdmxn: "MXN", usdbrl: "BRL",
    audusd: "AUD", usdcnh: "CNH", sp500: "S&P", silver: "Ag", vix: "VIX",
    eurusd: "EUR", usdjpy: "USD/JPY", bitcoin: "BTC", gold: "Au",
  };

  const tickBuffers = {}; // instrument -> {price:[], priceTs:[], macro:[], macroTs:[]}
  const configs = {};     // instrument -> /config response
  const sockets = {};

  function ensureBuffer(instrument) {
    if (!tickBuffers[instrument]) {
      tickBuffers[instrument] = { price: [], priceTs: [], macro: [], macroTs: [] };
    }
    return tickBuffers[instrument];
  }

  function pushCapped(arr, val, cap) {
    arr.push(val);
    if (arr.length > cap) arr.shift();
  }

  // ── derivative math (ported verbatim from instrument_panel.py) ──
  function accelWindow(b, tb, w) {
    if (b.length < w + 1) return 0.0;
    const n = b.length;
    const mid = Math.floor(w / 2);
    const last = b[n - 1], midV = b[n - 1 - mid], farV = b[n - 1 - w];
    const tLast = tb[n - 1], tMid = tb[n - 1 - mid], tFar = tb[n - 1 - w];
    const dt1 = tLast !== tMid ? tLast - tMid : 1;
    const dt2 = tMid !== tFar ? tMid - tFar : 1;
    const v1 = (last - midV) / dt1;
    const v2 = (midV - farV) / dt2;
    const dtA = (dt1 + dt2) / 2;
    return dtA > 0 ? (v1 - v2) / dtA : 0.0;
  }

  function velAt(b, tb, w) {
    const n = b.length;
    if (n < w + 1) return 0.0;
    const dt = tb[n - 1] - tb[n - 1 - w];
    return dt > 0 ? (b[n - 1] - b[n - 1 - w]) / dt : 0.0;
  }

  function velToBoost(v, scale = 0.05) { return Math.max(-25, Math.min(25, (v / scale) * 25)); }
  function accToBoost(a, scale = 0.01) { return Math.max(-10, Math.min(10, (a / scale) * 10)); }
  function macroVelToBoost(v, scale = 2.0) { return Math.max(-25, Math.min(25, (v / scale) * 25)); }
  function macroAccToBoost(a, scale = 0.5) { return Math.max(-10, Math.min(10, (a / scale) * 10)); }

  // ── fusion (ported from MacroScorer.calculate_fusion) ──
  function calculateFusion(techScore, techDir, macroScore, macroDir) {
    const aligned = techDir === macroDir && techDir !== "NEUTRAL";
    const opposed = techDir !== macroDir && techDir !== "NEUTRAL" && macroDir !== "NEUTRAL";
    let fusionScore, confluencePct;
    if (aligned) {
      fusionScore = (techScore + macroScore) / 2;
      const boost = Math.min(10, (Math.abs(techScore - 50) * Math.abs(macroScore - 50)) / 500);
      fusionScore += techDir === "LONG" ? boost : -boost;
      confluencePct = Math.round((techScore + macroScore) / 2 * 10) / 10;
    } else if (opposed) {
      fusionScore = 50 + (techScore - 50) * 0.3 + (macroScore - 50) * 0.3;
      confluencePct = Math.round((100 - Math.abs(techScore - macroScore)) * 10) / 10;
    } else {
      if (techDir !== "NEUTRAL") fusionScore = 50 + (techScore - 50) * 0.6;
      else if (macroDir !== "NEUTRAL") fusionScore = 50 + (macroScore - 50) * 0.6;
      else fusionScore = 50;
      confluencePct = Math.round((techScore + macroScore) / 2 * 10) / 10;
    }
    fusionScore = Math.round(Math.max(0, Math.min(100, fusionScore)) * 10) / 10;
    confluencePct = Math.max(0, Math.min(100, confluencePct));
    const fusionDir = fusionScore >= 60 ? "LONG" : fusionScore <= 40 ? "SHORT" : "NEUTRAL";
    let riskMode, riskEmoji;
    if (aligned && confluencePct >= 80) { riskMode = "AGGRESSIVE"; riskEmoji = "🟢"; }
    else if (opposed) { riskMode = "DEFENSIVE"; riskEmoji = "🔴"; }
    else { riskMode = "NORMAL"; riskEmoji = "🟡"; }
    return { score: fusionScore, direction: fusionDir, confluence_pct: confluencePct, aligned, opposed, risk_mode: riskMode, risk_emoji: riskEmoji };
  }

  function tt(content, title, body, direction = "up") {
    const cls = direction === "up" ? "tt-wrap" : "tt-wrap tt-down";
    return `<div class="${cls}">${content}<div class="tt-pop"><div class="tt-title">${title}</div>${body}</div></div>`;
  }

  function sliderBar(label, weightPct, score, msg) {
    const barClr = score >= 65 ? "#52b788" : score >= 45 ? "#ffd166" : "#ef476f";
    const pct = Math.max(0, Math.min(100, score));
    return `<div style="margin:3px 0;">
      <div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:1px;">
      <span style="color:#aaa;"><b>${label}</b> (${weightPct}%)</span>
      <span style="color:${barClr};font-weight:bold;">${score.toFixed(0)}</span></div>
      <div style="background:#2a2d35;border-radius:3px;height:6px;width:100%;overflow:hidden;">
      <div style="background:${barClr};height:100%;width:${pct}%;border-radius:3px;"></div></div>
      <div style="font-size:11px;color:#777;margin-top:1px;">${msg}</div></div>`;
  }

  // ── main panel renderer (mirrors instrument_panel.py::render_panel) ──
  function renderAssetPanel(el, snapshot, cfg) {
    if (!snapshot || !cfg) return;
    const instrument = cfg.instrument || (el.closest("[data-instrument]") || {}).dataset?.instrument;
    const buf = ensureBuffer(instrument || snapshot.symbol);

    const comp = snapshot.components || {};
    const tech = comp.technical || {};
    const techDetails = tech.details || {};
    const tfScores = techDetails.tf_scores || {};
    const techScore = tech.score ?? 50;
    const techDir = tech.direction ?? "NEUTRAL";
    const macro = comp._macro || {};
    const macroScore = macro.score ?? 50;
    const macroDir = macro.direction ?? "NEUTRAL";

    const levels = snapshot.levels || {};
    const combined = levels.combined || {};
    const currPrice = levels.current_price || 0;

    // price tick buffer (client-side derivatives, matches v2's session_state buffers)
    const now = Date.now() / 1000;
    if (currPrice > 0) {
      pushCapped(buf.price, currPrice, 200);
      pushCapped(buf.priceTs, now, 200);
    }
    pushCapped(buf.macro, macroScore, 200);
    pushCapped(buf.macroTs, now, 200);

    const n = buf.price.length;
    let vs = 0, vm = 0, vl = 0, v5 = 0, acs = 0, acm = 0, acl = 0, ac5 = 0;
    if (n >= 2) vs = velAt(buf.price, buf.priceTs, 1);
    if (n >= 3) acs = accelWindow(buf.price, buf.priceTs, 3);
    if (n >= 6) { vm = velAt(buf.price, buf.priceTs, 5); acm = accelWindow(buf.price, buf.priceTs, 6); }
    if (n >= 12) { vl = velAt(buf.price, buf.priceTs, 11); acl = accelWindow(buf.price, buf.priceTs, 12); }
    if (n >= 24) { v5 = velAt(buf.price, buf.priceTs, 23); ac5 = accelWindow(buf.price, buf.priceTs, 24); }

    const scMap = {}, dmMap = {};
    for (const t of ["M1", "M2", "M5", "M15"]) {
      scMap[t] = (tfScores[t] || {}).score ?? 50;
      dmMap[t] = (tfScores[t] || {}).direction ?? "NEUTRAL";
    }

    const fusedDefs = [
      ["⚡", "5s", { M1: 1.0 }, vs, acs, 0.50, 0.30],
      ["🔄", "30s", { M1: 0.6, M2: 0.4 }, vm, acm, 0.30, 0.15],
      ["📊", "1m", { M1: 0.4, M2: 0.3, M5: 0.3 }, vl, acl, 0.15, 0.05],
      ["📈", "5m", { M5: 0.6, M15: 0.4 }, v5, ac5, 0.10, 0.03],
    ];
    let cells = "", ttps = [];
    for (const [ic, sp, wt, v, a, vw, aw] of fusedDefs) {
      let vL = 0, vSh = 0;
      for (const [t, w] of Object.entries(wt)) {
        if (dmMap[t] === "LONG") vL += w;
        if (dmMap[t] === "SHORT") vSh += w;
      }
      const sd = vL > vSh && vL > 0.3 ? "LONG" : vSh > vL && vSh > 0.3 ? "SHORT" : "NEUTRAL";
      let bl = 0;
      for (const [t, w] of Object.entries(wt)) bl += (scMap[t] ?? 50) * w;
      const vb = velToBoost(v), ab = accToBoost(a);
      const enh = Math.max(0, Math.min(100, bl + vb * vw * 2 + ab * aw * 2));
      const sd2 = enh >= 55 ? "LONG" : enh <= 45 ? "SHORT" : "NEUTRAL";
      const disagree = sd !== sd2 && sd !== "NEUTRAL" && sd2 !== "NEUTRAL";
      const cv = Math.min(100, Math.abs(enh - 50) * 2);
      let r, g, b, arrow, action;
      if (sd === "LONG") { [r, g, b] = [82, 183, 136]; arrow = "▲"; action = "COMPRAR"; }
      else if (sd === "SHORT") { [r, g, b] = [239, 71, 111]; arrow = "▼"; action = "VENDER"; }
      else { [r, g, b] = [255, 209, 102]; arrow = "◆"; action = "ESPERAR"; }
      const op = 0.10 + (cv / 100) * 0.45;
      const tc = `rgb(${r},${g},${b})`, bg = `rgba(${r},${g},${b},${op.toFixed(2)})`;
      const dot = disagree ? `<span style="position:absolute;top:1px;right:2px;font-size:7px;color:#ff9f1c;" title="Tec!=Deriv">●</span>` : "";
      cells += `<td style="background:${bg};padding:4px 4px;text-align:center;border-right:1px solid #333;width:25%;position:relative;">${dot}
        <div style="font-size:18px;color:${tc};font-weight:900;line-height:1.2;">${arrow}</div>
        <div style="font-size:10px;color:${tc};font-weight:bold;line-height:1.2;">${action}</div>
        <div style="font-size:13px;color:#fff;font-weight:bold;line-height:1.2;">${cv.toFixed(0)}%</div></td>`;
    }
    const sigHtml = `<div style="background:#151820;border-radius:8px;overflow:hidden;">
      <table style="width:100%;border-collapse:collapse;table-layout:fixed;margin:0;"><tr>${cells}</tr></table>
      <div style="text-align:center;font-size:7px;color:#555;letter-spacing:2px;padding:1px 0;">TÉCNICO</div></div>`;

    // ── momentum bar ──
    let momTxt, momClr, momIc;
    if (vs > 0.01 && acs > 0.001) { momTxt = "📈 Subiendo y acelerando"; momClr = "#52b788"; momIc = "⏫"; }
    else if (vs > 0.01 && acs < -0.001) { momTxt = "📈 Subiendo pero frenando"; momClr = "#a8d5a2"; momIc = "🔼"; }
    else if (vs > 0) { momTxt = "↗️ Subiendo suave"; momClr = "#888"; momIc = "🔼"; }
    else if (vs < -0.01 && acs < -0.001) { momTxt = "📉 Bajando y acelerando"; momClr = "#ef476f"; momIc = "⏬"; }
    else if (vs < -0.01 && acs > 0.001) { momTxt = "📉 Bajando pero frenando"; momClr = "#f4a0b0"; momIc = "🔽"; }
    else if (vs < 0) { momTxt = "↘️ Bajando suave"; momClr = "#888"; momIc = "🔽"; }
    else { momTxt = "➡️ Sin movimiento"; momClr = "#555"; momIc = "⏸️"; }
    const momPct = Math.min(100, Math.abs(vs) / 0.05 * 100);
    const barClr = vs > 0 ? "#52b788" : "#ef476f";
    const fillDir = vs > 0 ? "right" : "left";
    const deriveInfo = `<div style="background:#1a1d23;border-radius:8px;padding:3px 8px;margin-top:2px;">
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;">
      <span style="color:${momClr};font-weight:bold;">${momIc} ${momTxt}</span>
      <span style="color:#555;font-size:9px;">${n} ticks</span></div>
      <div style="background:#111;border-radius:3px;height:4px;margin-top:2px;overflow:hidden;">
      <div style="width:${momPct.toFixed(0)}%;height:100%;background:${barClr};border-radius:3px;float:${fillDir};"></div></div></div>`;

    // ── macro derivative cards ──
    const mn = buf.macro.length;
    const mv2 = mn >= 3 ? velAt(buf.macro, buf.macroTs, 2) : 0;
    const mv6 = mn >= 7 ? velAt(buf.macro, buf.macroTs, 6) : 0;
    const mv12 = mn >= 13 ? velAt(buf.macro, buf.macroTs, 12) : 0;
    const mv24 = mn >= 25 ? velAt(buf.macro, buf.macroTs, 24) : 0;
    const ma3 = mn >= 4 ? accelWindow(buf.macro, buf.macroTs, 3) : 0;
    const ma6 = mn >= 7 ? accelWindow(buf.macro, buf.macroTs, 6) : 0;
    const ma12 = mn >= 13 ? accelWindow(buf.macro, buf.macroTs, 12) : 0;
    const ma24 = mn >= 25 ? accelWindow(buf.macro, buf.macroTs, 24) : 0;
    const macroDefs = [
      ["5s", mv2, ma3, 0.50, 0.30], ["30s", mv6, ma6, 0.30, 0.15],
      ["1m", mv12, ma12, 0.15, 0.05], ["5m", mv24, ma24, 0.10, 0.03],
    ];
    let mcCells = "";
    for (const [, v, a, vw, aw] of macroDefs) {
      const vb = macroVelToBoost(v), ab = macroAccToBoost(a);
      const enh = Math.max(0, Math.min(100, macroScore + vb * vw * 2 + ab * aw * 2));
      const sd = enh >= 55 ? "LONG" : enh <= 45 ? "SHORT" : "NEUTRAL";
      const cv = Math.min(100, Math.abs(enh - 50) * 2);
      let r, g, b, arrow, action;
      if (sd === "LONG") { [r, g, b] = [82, 183, 136]; arrow = "▲"; action = "COMPRAR"; }
      else if (sd === "SHORT") { [r, g, b] = [239, 71, 111]; arrow = "▼"; action = "VENDER"; }
      else { [r, g, b] = [255, 209, 102]; arrow = "◆"; action = "ESPERAR"; }
      const op = 0.10 + (cv / 100) * 0.45;
      const tc = `rgb(${r},${g},${b})`, bg = `rgba(${r},${g},${b},${op.toFixed(2)})`;
      mcCells += `<td style="background:${bg};padding:4px 4px;text-align:center;border-right:1px solid #333;width:25%;">
        <div style="font-size:18px;color:${tc};font-weight:900;line-height:1.2;">${arrow}</div>
        <div style="font-size:10px;color:${tc};font-weight:bold;line-height:1.2;">${action}</div>
        <div style="font-size:13px;color:#fff;font-weight:bold;line-height:1.2;">${cv.toFixed(0)}%</div></td>`;
    }
    const macroHtml = `<div style="background:#151820;border-radius:8px;overflow:hidden;margin-top:3px;">
      <table style="width:100%;border-collapse:collapse;table-layout:fixed;margin:0;"><tr>${mcCells}</tr></table>
      <div style="text-align:center;font-size:7px;color:#555;letter-spacing:2px;padding:1px 0;">MACRO</div></div>`;

    // ── triple signal + confluence ──
    const fusion = calculateFusion(techScore, techDir, macroScore, macroDir);
    function miniCard(label, sc, dr) {
      let clr, arrow, action;
      if (dr === "LONG") { clr = "#52b788"; arrow = "▲"; action = "COMPRAR"; }
      else if (dr === "SHORT") { clr = "#ef476f"; arrow = "▼"; action = "VENDER"; }
      else { clr = "#ffd166"; arrow = "◆"; action = "ESPERAR"; }
      const bp = Math.min(100, Math.abs(sc - 50) * 2);
      const bs = sc >= 50 ? "left" : "right";
      return `<td style="width:33.3%;padding:0 2px;vertical-align:top;">
        <div style="background:#1a1d23;border-radius:6px;padding:3px 4px;text-align:center;border:1px solid ${clr}22;">
        <div style="font-size:8px;color:#888;line-height:1;">${label}</div>
        <div style="font-size:16px;color:${clr};font-weight:900;line-height:1.1;">${arrow}</div>
        <div style="font-size:13px;color:${clr};font-weight:bold;line-height:1.1;">${sc.toFixed(0)}</div>
        <div style="font-size:8px;color:${clr};font-weight:bold;line-height:1.1;">${action}</div>
        <div style="background:#2a2d35;border-radius:2px;height:3px;margin-top:2px;overflow:hidden;">
        <div style="background:${clr};height:100%;width:${bp.toFixed(0)}%;border-radius:2px;float:${bs};"></div></div></div></td>`;
    }
    const t1 = miniCard("🔧 Técnico", techScore, techDir);
    const t2 = miniCard("🌍 Macro", macroScore, macroDir);
    const t3 = miniCard("⚡ Fusión", fusion.score, fusion.direction);
    const tripleHtml = `<table style="width:100%;border-collapse:collapse;table-layout:fixed;margin:3px 0 0 0;"><tr>${t1}${t3}${t2}</tr></table>`;
    const confClr = fusion.aligned ? "#52b788" : fusion.opposed ? "#ef476f" : "#ffd166";
    const confLabel = fusion.aligned ? "✅ CONFL" : fusion.opposed ? "⚠️ DIVER" : "➡️ PARCIAL";
    const conflHtml = `<div style="background:#1a1d23;border-radius:6px;padding:2px 6px;margin-top:2px;">
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:9px;">
      <span style="color:${confClr};font-weight:bold;">${confLabel} ${fusion.confluence_pct.toFixed(0)}%</span>
      <span style="color:#555;">${fusion.risk_emoji} ${fusion.risk_mode}</span></div>
      <div style="background:#2a2d35;border-radius:3px;height:4px;margin-top:2px;overflow:hidden;">
      <div style="background:${confClr};height:100%;width:${fusion.confluence_pct.toFixed(0)}%;border-radius:3px;"></div></div></div>`;

    // ── TF cards (M1/M2/M5/M15) ──
    const tfOrder = ["M1", "M2", "M5", "M15"];
    const tfW = { M1: "35%", M2: "35%", M5: "20%", M15: "10%" };
    const tfRoles = { M1: "Ejecución", M2: "Confirmación", M5: "Tendencia", M15: "Contexto" };
    let tfCardsHtml = "";
    for (const tfName of tfOrder) {
      const r = tfScores[tfName];
      if (!r) continue;
      const sc = r.score ?? 50, dr3 = r.direction ?? "NEUTRAL";
      const sigs = r.signals || {}, dets = r.details || {};
      const rsi = sigs.rsi ?? 0;
      const intensity = Math.min(1.0, Math.abs(sc - 50) / 40);
      let cr, cg, cb;
      if (sc >= 50) { cr = Math.round(136 - 54 * intensity); cg = Math.round(136 + 47 * intensity); cb = 136; }
      else { cr = Math.round(136 + 103 * intensity); cg = Math.round(136 - 65 * intensity); cb = Math.round(136 - 25 * intensity); }
      const clr = `rgb(${cr},${cg},${cb})`;
      const em = sc >= 65 ? "🟢" : sc >= 50 ? "🟡" : "🔴";
      const rc = rsi >= 70 ? "#ef476f" : rsi <= 30 ? "#52b788" : "#aaa";
      const rt = rsi >= 70 ? "OB" : rsi <= 30 ? "OS" : "";
      const action = dr3 === "LONG" ? "📈 COMPRAR" : dr3 === "SHORT" ? "📉 VENDER" : "🟡 ESPERAR";
      const rp = [];
      if (dr3 === "LONG") rp.push(`✅ <b>Señal COMPRAR</b> (${sc}/100).`);
      else if (dr3 === "SHORT") rp.push(`✅ <b>Señal VENDER</b> (${sc}/100).`);
      else rp.push(`🟡 <b>Sin dirección clara</b> (${sc}/100).`);
      if (rsi >= 70) rp.push(`<br>⚠️ RSI <b>${rsi.toFixed(0)}</b> SOBRECOMPRA.`);
      else if (rsi <= 30) rp.push(`<br>⚠️ RSI <b>${rsi.toFixed(0)}</b> SOBREVENTA.`);
      else if (rsi > 55) rp.push(`<br>RSI <b>${rsi.toFixed(0)}</b> — alcista.`);
      else if (rsi < 45) rp.push(`<br>RSI <b>${rsi.toFixed(0)}</b> — bajista.`);
      else rp.push(`<br>RSI <b>${rsi.toFixed(0)}</b> — neutral.`);
      rp.push(`<br><div style="border-top:1px solid #444;padding-top:4px;margin-top:4px;"><b>📋 Indicadores ${tfName}:</b></div>`);
      const emaD = dets.ema || {}, e9 = sigs.ema_9 ?? 0, e21 = sigs.ema_21 ?? 0, e50 = sigs.ema_50 ?? 0;
      const emaMsg = (e9 > e21 && e21 > e50 && e50 > 0) ? "<b>9&gt;21&gt;50 ✓</b> · Tendencia LONG"
        : (e9 < e21 && e21 < e50 && e50 > 0) ? "<b>9&lt;21&lt;50 ✓</b> · Tendencia SHORT"
        : "<b>Entrelazadas</b> · Sin tendencia clara";
      rp.push(sliderBar("EMA", 30, emaD.score ?? 50, emaMsg));
      rp.push(sliderBar("RSI", 20, (dets.rsi || {}).score ?? 50, `<b>RSI: ${rsi.toFixed(0)}</b>`));
      const macdH = sigs.macd_histogram ?? 0;
      rp.push(sliderBar("MACD", 25, (dets.macd || {}).score ?? 50, `<b>H: ${macdH >= 0 ? "+" : ""}${macdH.toFixed(4)}</b>`));
      const bbPct = sigs.bb_pct ?? 0.5;
      rp.push(sliderBar("BB", 15, (dets.bb || {}).score ?? 50, `<b>BB: ${(bbPct * 100).toFixed(0)}%</b>`));
      rp.push(sliderBar("PA", 10, (dets.pa || {}).score ?? 50, "Price Action"));
      const card = `<div style="text-align:center;background:#1a1d23;padding:2px 2px;border-radius:5px;">
        <div style="font-size:10px;color:#888;line-height:1.1;">${tfName} (${tfW[tfName]})</div>
        <div style="font-size:22px;color:${clr};font-weight:bold;line-height:1.1;">${em} ${sc}</div>
        <div style="font-size:11px;color:${clr};font-weight:bold;line-height:1.1;">${action}</div>
        <div style="font-size:11px;color:${rc};margin-top:1px;border-top:1px solid #333;padding-top:1px;line-height:1.2;">RSI: <b>${rsi.toFixed(0)}</b> ${rt}</div></div>`;
      tfCardsHtml += `<div style="width:25%;display:inline-block;vertical-align:top;">${tt(card, `${tfRoles[tfName]} — ${tfName} (${tfW[tfName]})`, rp.join(""), "down")}</div>`;
    }

    // ── S/R levels + macro votes ──
    const above = combined.above || [], below = combined.below || [];
    let levelsHtml = "";
    if ((above.length || below.length) && currPrice > 0) {
      above.slice().reverse().forEach((lv, i) => {
        const lb = `R${above.length - i}`;
        const rh = `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 3px;font-family:monospace;background:rgba(239,71,111,0.08);border-left:2px solid #ef476f;border-radius:2px;margin:0;line-height:1.3;">
          <span style="color:#ef476f;font-size:9px;">${lb}</span>
          <span style="font-weight:bold;font-size:16px;color:#ddd;">${lv.price.toFixed(1)}</span>
          <span style="color:#ef476f;font-size:9px;">${lv.pct >= 0 ? "+" : ""}${lv.pct.toFixed(1)}%</span></div>`;
        levelsHtml += tt(rh, `🔴 ${lb} — Resistencia (${lv.price.toFixed(2)})`, `Distancia: ${Math.abs(lv.pct).toFixed(2)}%`, "down");
      });
      levelsHtml += `<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 3px;font-family:monospace;background:rgba(76,201,240,0.12);border:1px solid #4cc9f0;border-radius:2px;margin:1px 0;line-height:1.3;">
        <span style="color:#4cc9f0;font-size:9px;font-weight:bold;">${(snapshot.symbol || "").slice(0, 3)}</span>
        <span style="font-size:17px;font-weight:bold;color:#4cc9f0;">${currPrice.toFixed(1)}</span></div>`;
      below.forEach((lv, i) => {
        const lb = `S${i + 1}`;
        const rh = `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 3px;font-family:monospace;background:rgba(82,183,136,0.08);border-left:2px solid #52b788;border-radius:2px;margin:0;line-height:1.3;">
          <span style="color:#52b788;font-size:9px;">${lb}</span>
          <span style="font-weight:bold;font-size:16px;color:#ddd;">${lv.price.toFixed(1)}</span>
          <span style="color:#52b788;font-size:9px;">${lv.pct >= 0 ? "+" : ""}${lv.pct.toFixed(1)}%</span></div>`;
        levelsHtml += tt(rh, `🟢 ${lb} — Soporte (${lv.price.toFixed(2)})`, `Distancia: ${Math.abs(lv.pct).toFixed(2)}%`, "down");
      });
    } else {
      levelsHtml = `<div style="color:#666;font-size:0.75rem;">Sin datos</div>`;
    }

    const votes = macro.votes || {};
    const corrData = ((comp.correlation || {}).details || {}).correlations || {};
    let voteRows = "";
    const fixedOrder = Object.keys(votes);
    for (const k of fixedOrder) {
      const v = votes[k];
      if (!v) continue;
      const name = CN[k] || k;
      const ret = v.return_bps ?? 0;
      const wv = v.weighted_vote ?? 0;
      const warm = v.warmup;
      const hvClr = wv > 0.05 ? "#52b788" : wv < -0.05 ? "#ef476f" : "#555";
      const hvDir = wv > 0.05 ? "LONG" : wv < -0.05 ? "SHORT" : "—";
      const wtTag = warm ? ` <span style="color:#ff6b6b;font-size:8px;">⏳</span>` : "";
      voteRows += `<tr style="border-bottom:1px solid #1a1d23;">
        <td style="padding:3px 3px;color:#ccc;font-size:12px;">${name}${wtTag}</td>
        <td style="padding:3px 3px;text-align:right;color:${ret > 0 ? "#52b788" : ret < 0 ? "#ef476f" : "#555"};font-size:12px;">${ret >= 0 ? "+" : ""}${ret.toFixed(1)}</td>
        <td style="padding:3px 3px;text-align:center;color:${hvClr};font-weight:bold;font-size:12px;">${hvDir}</td>
        </tr>`;
    }
    const hmClr = macroScore >= 65 ? "#52b788" : macroScore >= 50 ? "#ffd166" : "#ef476f";
    const macroVotesHtml = fixedOrder.length ? `<div class="macro-votes-wrap">
      <table style="width:100%;font-size:12px;font-family:monospace;border-collapse:collapse;line-height:1.5;">${voteRows}</table>
      <div style="text-align:center;margin-top:auto;padding:2px;border-top:1px solid #333;font-size:13px;">
      <span style="color:${hmClr};font-weight:bold;">Macro: ${macroScore.toFixed(0)}</span>
      <span style="color:${hmClr};font-size:11px;"> ${macroDir}</span></div></div>`
      : `<div style="color:#666;font-size:0.7rem;">⏳ Macro...</div>`;

    // ── alerts / divergences ──
    const alerts = snapshot.alerts || [];
    const divergences = snapshot.divergences || [];
    const alertsHtml = alerts.length
      ? `<ul style="margin:2px 0;padding-left:1rem;font-size:10px;color:#ffd166;">${alerts.map((a) => `<li>${a}</li>`).join("")}</ul>`
      : "";
    const divergHtml = divergences.length
      ? `<ul style="margin:2px 0;padding-left:1rem;font-size:10px;color:#4cc9f0;">${divergences.map((d) => `<li>${typeof d === "string" ? d : d.description || JSON.stringify(d)}</li>`).join("")}</ul>`
      : "";

    const hc = techScore >= 65 ? "#52b788" : techScore >= 50 ? "#ffd166" : "#ef476f";
    const label = LABELS[instrument] || snapshot.symbol;
    const emoji = EMOJI[instrument] || "";

    el.innerHTML = `
      <div style="text-align:center;padding:2px 0;border-bottom:2px solid ${hc};margin:6px 0 2px 0;">
        <span style="font-size:13px;color:${hc};font-weight:bold;">${emoji} ${label}</span></div>
      <div style="display:flex;gap:6px;">
        <div style="width:40%;">
          ${tt(sigHtml, "🎯 Señales Fusionadas", "Dirección + derivadas de precio", "down")}
          ${tt(deriveInfo, "📈 Momentum", `Vel: ${vs.toFixed(4)}/s | Buffer: ${n} ticks`, "down")}
          ${tt(macroHtml, "🌍 Señales Macro", `Buffer: ${mn} muestras`, "down")}
          ${tt(tripleHtml + conflHtml, "🧪 Triple Signal System", `Téc: ${techScore.toFixed(0)} | Macro: ${macroScore.toFixed(0)} | Fusión: ${fusion.score.toFixed(0)}`, "down")}
        </div>
        <div style="width:60%;">
          <div>${tfCardsHtml}</div>
          <div style="display:flex;gap:4px;margin-top:3px;">
            <div style="width:75%;">${macroVotesHtml}</div>
            <div style="width:25%;">${levelsHtml}</div>
          </div>
          ${alertsHtml}${divergHtml}
        </div>
      </div>`;
  }

  // ── top bar ──
  function updateTopBar(snapshot) {
    const cfgHashEl = document.getElementById("topbar-cfg-hash");
    const statusEl = document.getElementById("topbar-status");
    const staleEl = document.getElementById("topbar-stale");
    if (snapshot.config_hash) cfgHashEl.textContent = `cfg#${String(snapshot.config_hash).slice(0, 8)}`;
    const stale = snapshot.stale_seconds ?? 0;
    staleEl.textContent = `${snapshot.data_source || "?"} · stale: ${stale.toFixed(0)}s`;
    staleEl.className = "chip mono" + (stale > 30 ? " stale-crit" : stale > 10 ? " stale-warn" : "");
    statusEl.className = "chip connected";
    statusEl.textContent = "● REAL-TIME";
  }

  // ── WS client (one socket per left-column instrument) ──
  function wsUrl(instrument) {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/stream?instrument=${encodeURIComponent(instrument)}`;
  }

  function connect(instrument) {
    const ws = new WebSocket(wsUrl(instrument));
    sockets[instrument] = ws;
    ws.onmessage = (evt) => {
      let snap;
      try { snap = JSON.parse(evt.data); } catch (e) { return; }
      const elMount = document.querySelector(`#panel-${instrument} .v2-mount`);
      if (elMount) renderAssetPanel(elMount, snap, configs[instrument] || { instrument });
      updateTopBar(snap);
    };
    ws.onclose = () => setTimeout(() => connect(instrument), 1500);
    ws.onerror = () => ws.close();
  }

  async function probeEndpoint(path) {
    try {
      const resp = await fetch(path, { method: "GET" });
      return resp.status === 200;
    } catch (e) {
      return false;
    }
  }

  async function boot() {
    for (const instrument of INSTRUMENTS) {
      try {
        const resp = await fetch(`/config?instrument=${instrument}`);
        configs[instrument] = await resp.json();
      } catch (e) {
        configs[instrument] = { instrument };
      }
      connect(instrument);
    }

    // ── nav router ──
    const buttons = document.querySelectorAll(".nav-btn");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        buttons.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        document.querySelectorAll(".right-section").forEach((s) => (s.hidden = true));
        const target = document.getElementById(`section-${btn.dataset.section}`);
        if (target) target.hidden = false;
        window.dispatchEvent(new CustomEvent("sentinel:section", { detail: btn.dataset.section }));
      });
    });
  }

  window.SENTINEL = window.SENTINEL || {};
  window.SENTINEL.renderAssetPanel = renderAssetPanel;
  window.SENTINEL.probeEndpoint = probeEndpoint;
  window.SENTINEL.tickBuffers = tickBuffers;
  window.SENTINEL.configs = configs;

  boot();
})();
