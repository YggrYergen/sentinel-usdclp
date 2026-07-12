// CDP: open :8611, go to CHARTS section, verify candles actually painted.
const { spawn } = require('child_process');
const http = require('http');
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 9334;
const TARGET = "http://127.0.0.1:8611/";
const udd = require('os').tmpdir() + "\\cdp-prof-" + Date.now();
const sleep = ms => new Promise(r => setTimeout(r, ms));
const getJSON = p => new Promise((res, rej) => { const t=setTimeout(()=>rej(new Error('to')),1500);
  http.get(`http://127.0.0.1:${PORT}${p}`, r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>{clearTimeout(t);try{res(JSON.parse(d))}catch(e){rej(e)}});}).on('error',e=>{clearTimeout(t);rej(e);}); });

const chrome = spawn(CHROME, ["--headless=new","--disable-gpu","--no-first-run","--no-default-browser-check",
  `--remote-debugging-port=${PORT}`,`--user-data-dir=${udd}`,"--window-size=1600,1000", TARGET], {stdio:'ignore'});

(async () => {
  let wsUrl=null;
  for (let i=0;i<40;i++){ try{ const l=await getJSON('/json'); const pg=l.find(t=>t.type==='page'); if(pg&&pg.webSocketDebuggerUrl){wsUrl=pg.webSocketDebuggerUrl;break;} }catch(e){} await sleep(250); }
  if(!wsUrl){ console.log(JSON.stringify({fatal:'no target'})); chrome.kill(); process.exit(1); }
  const ws = new WebSocket(wsUrl); const errors=[]; let id=0; const pend={};
  const send=(m,p={})=>new Promise(res=>{const i=++id;pend[i]=res;ws.send(JSON.stringify({id:i,method:m,params:p}));});
  ws.onmessage=ev=>{const m=JSON.parse(ev.data); if(m.id&&pend[m.id]){pend[m.id](m);delete pend[m.id];}
    if(m.method==='Runtime.exceptionThrown')errors.push('EXC: '+(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text).split('\n')[0]);
    if(m.method==='Runtime.consoleAPICalled'&&m.params.type==='error')errors.push('CONSOLE: '+m.params.args.map(a=>a.value||'').join(' ').slice(0,160));};
  await new Promise(r=>ws.onopen=r);
  await send('Runtime.enable'); await send('Page.enable');
  await send('Page.navigate',{url:TARGET}); await sleep(3500);
  const diag = `(async () => {
    const out = {href: location.href};
    const btn = document.querySelector('.nav-btn[data-section="charts"]');
    if (btn) btn.click();
    await new Promise(r => setTimeout(r, 4000));
    const sec = document.getElementById('section-charts');
    out.hidden = sec ? !!sec.hidden : 'NO_SECTION';
    const canvases = sec ? [...sec.querySelectorAll('canvas')] : [];
    out.canvases = canvases.map(c => ({w: c.width, h: c.height}));
    // pixel-sample the largest canvas: count non-transparent, non-uniform pixels
    let painted = 0, sampled = 0, colors = new Set();
    if (canvases.length) {
      const c = canvases.reduce((a,b)=> (b.width*b.height > a.width*a.height ? b : a));
      try {
        const ctx = c.getContext('2d');
        if (ctx) {
          const img = ctx.getImageData(0, 0, c.width, c.height).data;
          for (let i = 0; i < img.length; i += 400) { // sparse sample
            sampled++;
            const a = img[i+3];
            if (a > 0) { painted++; colors.add(img[i]+','+img[i+1]+','+img[i+2]); }
          }
        } else { out.ctx = '2d ctx unavailable (webgl?)'; }
      } catch (e) { out.pixelErr = String(e); }
    }
    out.paintedPct = sampled ? Math.round(100*painted/sampled) : 0;
    out.distinctColors = colors.size;
    out.overlayState = (()=>{ const o = sec && sec.querySelector('.chart-state-overlay'); return o ? {hidden: o.hidden, text:(o.textContent||'').trim().slice(0,60)} : 'none'; })();
    return out;
  })()`;
  const r = await send('Runtime.evaluate',{expression:diag,awaitPromise:true,returnByValue:true});
  console.log(JSON.stringify({result:r.result?.result?.value??r.result, errors:errors.slice(0,10)},null,2));
  ws.close(); chrome.kill(); process.exit(0);
})().catch(e=>{console.log(JSON.stringify({fatal:String(e)}));try{chrome.kill()}catch(_){}process.exit(1);});
setTimeout(()=>{console.log(JSON.stringify({fatal:'hard-timeout'}));try{chrome.kill()}catch(_){}process.exit(1);},30000);
