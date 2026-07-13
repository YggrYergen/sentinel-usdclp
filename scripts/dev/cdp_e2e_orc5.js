// ORC-5 e2e headless checklist driver. Target: scripts/dev/e2e_service.py on :8611
// (seeded registry copy). Drives the real UI over CDP and prints a JSON summary:
// charts (paint/TF/indicator/goto) · TV-review (run load/dot/replay/split) ·
// positions (tabs/groups/VWAP/panel) · runs launcher (CT-4 happy path) · chat gate.
const { spawn } = require('child_process');
const http = require('http');
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 9335;
const TARGET = "http://127.0.0.1:8611/";
const udd = require('os').tmpdir() + "\\cdp-orc5-" + Date.now();
const sleep = ms => new Promise(r => setTimeout(r, ms));
const getJSON = p => new Promise((res, rej) => { const t = setTimeout(() => rej(new Error('to')), 1500);
  http.get(`http://127.0.0.1:${PORT}${p}`, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => { clearTimeout(t); try { res(JSON.parse(d)) } catch (e) { rej(e) } }); }).on('error', e => { clearTimeout(t); rej(e); }); });

const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${udd}`, "--window-size=1600,1000", TARGET], { stdio: 'ignore' });

const results = {};
const errors = [];

(async () => {
  let wsUrl = null;
  for (let i = 0; i < 40; i++) { try { const l = await getJSON('/json'); const pg = l.find(t => t.type === 'page'); if (pg && pg.webSocketDebuggerUrl) { wsUrl = pg.webSocketDebuggerUrl; break; } } catch (e) { } await sleep(250); }
  if (!wsUrl) { console.log(JSON.stringify({ fatal: 'no target' })); chrome.kill(); process.exit(1); }
  const ws = new WebSocket(wsUrl); let id = 0; const pend = {};
  const send = (m, p = {}) => new Promise(res => { const i = ++id; pend[i] = res; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pend[m.id]) { pend[m.id](m); delete pend[m.id]; }
    if (m.method === 'Runtime.exceptionThrown') errors.push('EXC: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text).split('\n')[0]);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push('CONSOLE: ' + m.params.args.map(a => a.value || a.description || '').join(' ').slice(0, 200)); };
  await new Promise(r => ws.onopen = r);
  await send('Runtime.enable'); await send('Page.enable');
  await send('Page.navigate', { url: TARGET }); await sleep(3500);

  // evaluate an async expression in-page, return its resolved value
  const run = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: `(async () => { ${expr} })()`, awaitPromise: true, returnByValue: true, timeout: 130000 });
    if (r.result?.exceptionDetails) return { evalError: r.result.exceptionDetails.exception?.description || 'eval exception' };
    return r.result?.result?.value;
  };
  // in-page helpers injected once
  await run(`
    window.__e2e = {
      sleep: ms => new Promise(r => setTimeout(r, ms)),
      waitFor: async (fn, timeout, step) => { const t0 = Date.now(); while (Date.now() - t0 < timeout) { try { const v = fn(); if (v) return v; } catch (e) {} await new Promise(r => setTimeout(r, step || 200)); } return null; },
      paint: (host) => {
        // sample EVERY canvas (top canvas is often a transparent overlay); report the best
        const canvases = [...host.querySelectorAll('canvas')];
        if (!canvases.length) return { canvases: 0 };
        let best = { paintedPct: 0, colors: 0 }; const perCanvas = [];
        for (const c of canvases) {
          let painted = 0, sampled = 0; const colors = new Set();
          try { const ctx = c.getContext('2d'); if (!ctx) { perCanvas.push('no2d'); continue; }
            const img = ctx.getImageData(0, 0, c.width, c.height).data;
            for (let i = 0; i < img.length; i += 400) { sampled++; const a = img[i + 3]; if (a > 0) { painted++; colors.add(img[i] + ',' + img[i + 1] + ',' + img[i + 2]); } }
          } catch (e) { perCanvas.push('err'); continue; }
          const pct = sampled ? Math.round(100 * painted / sampled) : 0;
          perCanvas.push(pct + '%/' + colors.size + 'c@' + c.width + 'x' + c.height);
          if (pct > best.paintedPct || (pct === best.paintedPct && colors.size > best.colors))
            best = { paintedPct: pct, colors: colors.size, w: c.width, h: c.height };
        }
        return { canvases: canvases.length, ...best, perCanvas };
      },
      nav: async (name) => { document.querySelector('.nav-btn[data-section="' + name + '"]').click(); await window.__e2e.sleep(600); return !document.getElementById('section-' + name).hidden; }
    }; return true;`);

  // ---------- 1. CHARTS ----------
  results.charts = await run(`
    const E = window.__e2e; const out = {};
    out.navOk = await E.nav('charts');
    const sec = document.getElementById('section-charts');
    await E.waitFor(() => { const p = E.paint(sec.querySelector('.charts-chart-host') || sec); return p.paintedPct > 3 && p.colors > 3; }, 12000);
    out.initialPaint = E.paint(sec.querySelector('.charts-chart-host') || sec);
    // TF switch: click a non-active TF button
    const tfBtns = [...sec.querySelectorAll('.charts-tf-btn')];
    out.tfButtons = tfBtns.map(b => b.textContent);
    const target = tfBtns.find(b => !b.classList.contains('active'));
    if (target) { out.tfClicked = target.textContent; target.click(); await E.sleep(3000);
      out.tfActiveAfter = (tfBtns.find(b => b.classList.contains('active')) || {}).textContent;
      out.tfPaint = E.paint(sec.querySelector('.charts-chart-host') || sec); }
    // indicator chip toggle
    const chips = [...sec.querySelectorAll('.charts-overlay-chip')];
    out.chips = chips.map(c => c.textContent);
    if (chips.length) { chips[0].click(); await E.sleep(2500);
      out.chipActive = chips[0].className; out.chipPaint = E.paint(sec.querySelector('.charts-chart-host') || sec); }
    // goto-date
    const gi = sec.querySelector('.goto-datetime-input'); const gb = sec.querySelector('.goto-btn');
    out.gotoPresent = !!(gi && gb);
    if (gi && gb) { gi.value = '2026-07-03T12:00'; gi.dispatchEvent(new Event('input', { bubbles: true })); gb.click(); await E.sleep(3000);
      out.gotoPaint = E.paint(sec.querySelector('.charts-chart-host') || sec); }
    return out;`);

  // ---------- 2. TV / REVIEW ----------
  results.review = await run(`
    const E = window.__e2e; const out = {};
    out.navOk = await E.nav('review');
    const sec = document.getElementById('section-review');
    const item = await E.waitFor(() => sec.querySelector('.review-run-item'), 10000);
    out.runList = !!item;
    if (item) { out.runClicked = item.getAttribute('data-run-id'); item.click();
      await E.waitFor(() => { const p = E.paint(sec.querySelector('.review-chart-host') || sec); return p.paintedPct > 3 && p.colors > 3; }, 15000);
      out.chartPaint = E.paint(sec.querySelector('.review-chart-host') || sec);
      // native-tf dot
      out.nativeTfDot = (sec.querySelector('.review-tf-btn.native-tf') || {}).textContent || null;
      // replay: playback bar play -> ts label changes
      const play = sec.querySelector('.playback-play-btn'); const ts = sec.querySelector('.playback-ts-label');
      out.playback = !!(play && ts);
      if (play && ts) { const before = ts.textContent; play.click();
        await E.waitFor(() => ts.textContent !== before && ts.textContent !== '--', 8000);
        out.replayTsChanged = ts.textContent !== before && ts.textContent !== '--'; out.replayTs = ts.textContent; play.click(); }
      // split-pane focus: click trade-list host, check persisted focus
      const tl = sec.querySelector('.review-tradelist-host'); if (tl) { tl.click(); await E.sleep(300); }
      out.paneFocus = localStorage.getItem('tv.paneFocus');
      // trade rows loaded?
      out.tradeRows = sec.querySelectorAll('.review-vtable [data-run-id], .review-vtable .vtable-row, .review-vtable div').length > 0;
    }
    return out;`);

  // ---------- 3. POSITIONS ----------
  results.positions = await run(`
    const E = window.__e2e; const out = {};
    out.navOk = await E.nav('positions');
    const sec = document.getElementById('section-positions');
    await E.waitFor(() => sec.querySelectorAll('.positions-tab').length >= 3, 8000);
    out.tabs = [...sec.querySelectorAll('.positions-tab')].map(t => t.textContent);
    // HUMANO tab (default): cards from seeded deals
    const humano = [...sec.querySelectorAll('.positions-tab')].find(t => t.textContent === 'HUMANO');
    if (humano) humano.click(); await E.sleep(1200);
    await E.waitFor(() => sec.querySelectorAll('.positions-humano-card').length > 0, 8000);
    out.humanoCards = sec.querySelectorAll('.positions-humano-card').length;
    // multi-lot group: chevron expand + VWAP px_in (0.2@3300 + 0.1@3302 -> 3300.67)
    const chev = sec.querySelector('.positions-humano-chevron');
    out.chevron = !!chev;
    if (chev) { const groupCard = chev.closest('.positions-humano-card'); out.groupCardText = (groupCard.textContent || '').slice(0, 260);
      chev.click(); await E.sleep(600);
      out.childRows = sec.querySelectorAll('.positions-humano-child-row').length;
      out.vwapShown = /3[.,]?300[.,]6|3300\\.6/.test(groupCard.textContent); }
    // select a card -> detail panel with chart + replay button
    const card = sec.querySelector('.positions-humano-card:not(.positions-humano-child-row)');
    if (card) { card.click(); await E.sleep(1500);
      const panel = sec.querySelector('.positions-humano-panel'); out.panel = !!panel;
      if (panel) { await E.waitFor(() => { const p = E.paint(panel.querySelector('.positions-humano-panel-chart') || panel); return p.paintedPct > 2; }, 10000);
        out.panelPaint = E.paint(panel.querySelector('.positions-humano-panel-chart') || panel);
        out.replayBtn = !!panel.querySelector('.positions-humano-replay-btn');
        out.panelDetail = (panel.querySelector('.positions-humano-panel-detail') || {}).textContent?.slice(0, 200); } }
    // IA tab: aggregate card + list
    const ia = [...sec.querySelectorAll('.positions-tab')].find(t => t.textContent === 'IA');
    if (ia) { ia.click(); await E.sleep(1500);
      out.iaAggregate = !!(await E.waitFor(() => sec.querySelector('.positions-ia-aggregate'), 6000));
      out.iaAggText = (sec.querySelector('.positions-ia-aggregate') || {}).textContent?.slice(0, 200);
      out.iaCards = sec.querySelectorAll('.positions-humano-card').length; }
    // ESTRATEGIA tab renders
    const est = [...sec.querySelectorAll('.positions-tab')].find(t => t.textContent === 'ESTRATEGIA');
    if (est) { est.click(); await E.sleep(1500); out.estrategiaRendered = !!sec.querySelector('.positions-estrategia-wrap, .manage-strategy-panel, .positions-cards'); }
    return out;`);

  // ---------- 4. RUNS LAUNCHER (CT-4 happy path) ----------
  results.launcher = await run(`
    const E = window.__e2e; const out = {};
    out.navOk = await E.nav('runs');
    const sec = document.getElementById('section-runs');
    const form = await E.waitFor(() => sec.querySelector('.runs-launcher-form'), 10000);
    out.form = !!form;
    if (form) {
      await E.waitFor(() => form.querySelector('select[name="variant_id"]').options.length > 0, 8000);
      const vs = form.querySelector('select[name="variant_id"]'); const ss = form.querySelector('select[name="symbol"]'); const ts = form.querySelector('select[name="tf"]');
      out.variants = vs.options.length; out.symbols = [...ss.options].map(o => o.value); out.tfs = [...ts.options].map(o => o.value);
      // pick a real variant (first option is an empty placeholder), XAUUSD + coarse tf for a fast job
      const vOpt = [...vs.options].find(o => o.value); if (vOpt) vs.value = vOpt.value;
      const sym = [...ss.options].find(o => /XAU/i.test(o.value)); if (sym) ss.value = sym.value;
      const tfOpt = [...ts.options].find(o => /^(D|H4|H1)$/i.test(o.value)) || ts.options[ts.options.length - 1]; ts.value = tfOpt.value;
      [vs, ss, ts].forEach(el => el.dispatchEvent(new Event('change', { bubbles: true })));
      out.chose = { variant: vs.value, symbol: ss.value, tf: ts.value };
      form.querySelector('.runs-launcher-submit-btn').click();
      const progress = form.querySelector('.runs-launcher-progress'); const err = form.querySelector('.runs-launcher-error');
      await E.waitFor(() => !progress.hidden || !err.hidden, 10000);
      out.errShown = !err.hidden ? err.textContent.slice(0, 200) : null;
      // wait for completion (run link) up to 110s
      const done = await E.waitFor(() => progress.querySelector('.runs-launcher-run-link'), 110000, 1000);
      out.progressText = (progress.textContent || '').slice(0, 200);
      out.completed = !!done;
      if (done) out.runId = done.getAttribute('data-run-id');
    }
    return out;`);

  // ---------- 5. CHAT GATE ----------
  results.chat = await run(`
    const E = window.__e2e; const out = {};
    out.navOk = await E.nav('chat');
    const sec = document.getElementById('section-chat');
    await E.sleep(1000);
    out.text = (sec.textContent || '').trim().slice(0, 300);
    out.hasContent = (sec.textContent || '').trim().length > 0;
    return out;`);

  console.log(JSON.stringify({ results, consoleErrors: errors.slice(0, 20) }, null, 2));
  ws.close(); chrome.kill(); process.exit(0);
})().catch(e => { console.log(JSON.stringify({ fatal: String(e), results, consoleErrors: errors.slice(0, 20) })); try { chrome.kill() } catch (_) { } process.exit(1); });
setTimeout(() => { console.log(JSON.stringify({ fatal: 'hard-timeout', results, consoleErrors: errors.slice(0, 20) })); try { chrome.kill() } catch (_) { } process.exit(1); }, 240000);
