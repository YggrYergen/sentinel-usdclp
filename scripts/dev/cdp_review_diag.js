// Minimal CDP driver: render Trade View on :8611 and inspect list DOM + console.
const { spawn } = require('child_process');
const http = require('http');
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 9333;
const TARGET = "http://127.0.0.1:8611/";
const udd = require('os').tmpdir() + "\\cdp-prof-" + Date.now();
const sleep = ms => new Promise(r => setTimeout(r, ms));
const getJSON = path => new Promise((res, rej) => {
  const t = setTimeout(() => rej(new Error('to')), 1500);
  http.get(`http://127.0.0.1:${PORT}${path}`, r => { let d=''; r.on('data',c=>d+=c); r.on('end',()=>{clearTimeout(t); try{res(JSON.parse(d))}catch(e){rej(e)}}); }).on('error', e => { clearTimeout(t); rej(e); });
});

const chrome = spawn(CHROME, ["--headless=new","--disable-gpu","--no-first-run","--no-default-browser-check",
  `--remote-debugging-port=${PORT}`,`--user-data-dir=${udd}`,"--window-size=1600,1000", TARGET], {stdio:'ignore'});

(async () => {
  let pageWsUrl = null;
  for (let i=0;i<40;i++){ try { const list = await getJSON('/json'); const pg = list.find(t=>t.type==='page'); if (pg && pg.webSocketDebuggerUrl){ pageWsUrl = pg.webSocketDebuggerUrl; break; } } catch(e){} await sleep(250); }
  if (!pageWsUrl){ console.log(JSON.stringify({fatal:'no page target'})); chrome.kill(); process.exit(1); }
  const ws = new WebSocket(pageWsUrl);
  const errors = []; let id = 0; const pending = {};
  const send = (method, params={}) => new Promise(res => { const mid = ++id; pending[mid]=res; ws.send(JSON.stringify({id:mid, method, params})); });
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending[m.id]) { pending[m.id](m); delete pending[m.id]; }
    if (m.method === 'Runtime.exceptionThrown') errors.push('EXC: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push('CONSOLE.error: ' + m.params.args.map(a=>a.value||a.description||'').join(' '));
  };
  await new Promise(r => ws.onopen = r);
  await send('Runtime.enable'); await send('Page.enable');
  await send('Page.navigate', {url: TARGET});
  await sleep(3500);
  const diag = `(async () => {
    const out = {href: location.href};
    const btn = document.querySelector('.nav-btn[data-section="review"]');
    out.reviewBtn = !!btn;
    if (btn) btn.click();
    await new Promise(r => setTimeout(r, 1800));
    const sec = document.getElementById('section-review');
    out.sectionHidden = sec ? !!sec.hidden : 'NO_SECTION';
    const left = document.querySelector('.review-left');
    out.leftH = left ? left.clientHeight : 'NO_LEFT';
    const groups = document.querySelector('.review-run-groups');
    out.groups = groups ? { clientH: groups.clientHeight, scrollH: groups.scrollHeight, children: groups.children.length, text: (groups.textContent||'').trim().slice(0,80) } : 'NO_GROUPS_EL';
    out.anyRunRows = document.querySelectorAll('#section-review [class*="run"]').length;
    out.tradeList = (()=>{ const t = document.querySelector('.review-trade-list, [class*="trade-list"], .review-signals'); return t ? {clientH:t.clientHeight, children:t.children.length} : 'NO_TRADE_LIST'; })();
    return out;
  })()`;
  const r = await send('Runtime.evaluate', {expression: diag, awaitPromise:true, returnByValue:true});
  console.log(JSON.stringify({ result: r.result?.result?.value ?? r.result, consoleErrors: errors.slice(0,15) }, null, 2));
  ws.close(); chrome.kill(); process.exit(0);
})().catch(e => { console.log(JSON.stringify({fatal:String(e)})); try{chrome.kill()}catch(_){} process.exit(1); });
setTimeout(() => { console.log(JSON.stringify({fatal:'hard-timeout'})); try{chrome.kill()}catch(_){} process.exit(1); }, 25000);
