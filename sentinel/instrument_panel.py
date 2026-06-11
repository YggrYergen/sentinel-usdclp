"""
SENTINEL v2 — Reusable Instrument Panel (pixel-identical to USDCLP panel)
"""
import streamlit as st
import numpy as np
import time
from sentinel.technical_scorer import calculate_multi_tf_score
from sentinel.macro_scorer import MacroScorer


def _tt(content, title, body, direction="up"):
    cls = "tt-wrap" if direction == "up" else "tt-wrap tt-down"
    return (f'<div class="{cls}">{content}'
            f'<div class="tt-pop"><div class="tt-title">{title}</div>{body}</div></div>')


def _accel_w(b, tb, w):
    if len(b) < w + 1: return 0.0
    mid = w // 2
    dt1 = tb[-1] - tb[-mid] if tb[-1] != tb[-mid] else 1
    dt2 = tb[-mid] - tb[-w] if tb[-mid] != tb[-w] else 1
    v1 = (b[-1] - b[-mid]) / dt1; v2 = (b[-mid] - b[-w]) / dt2
    dt_a = (dt1 + dt2) / 2
    return (v1 - v2) / dt_a if dt_a > 0 else 0.0


def render_panel(feed, symbols_cfg, expected_corrs, asset_weights,
                 panel_key, label, emoji):
    target = symbols_cfg["target"]
    # MacroScorer per-instrument
    msk = f"_ms_{panel_key}"
    if msk not in st.session_state:
        st.session_state[msk] = MacroScorer()
    _ms = st.session_state[msk]
    # Technical scores
    tech = calculate_multi_tf_score(feed, target)
    tech_sc = tech["composite_score"]; tech_dir = tech["h4_direction"]
    # Macro tick update + score
    _update_macro(_ms, feed, symbols_cfg, asset_weights, expected_corrs)
    mr = _calc_macro(_ms, feed, symbols_cfg, expected_corrs, asset_weights)
    m_sc = mr["score"]; m_dir = mr["direction"]
    price_info = feed.get_current_price(target)
    CN = {}
    cn_map = {"dxy":"DXY","copper":"Cu","wti":"WTI","usdmxn":"MXN","usdbrl":"BRL",
              "audusd":"AUD","usdcnh":"CNH","sp500":"S&P","silver":"Ag","vix":"VIX",
              "eurusd":"EUR","usdjpy":"JPY","bitcoin":"BTC","gold":"Au"}
    for k in expected_corrs:
        CN[k] = cn_map.get(k, k.upper())
    # Header
    hc = "#52b788" if tech_sc >= 65 else ("#ffd166" if tech_sc >= 50 else "#ef476f")
    st.markdown(f"<div style='text-align:center;padding:2px 0;border-bottom:2px solid {hc};"
                f"margin:6px 0 2px 0;'><span style='font-size:13px;color:{hc};"
                f"font-weight:bold;'>{emoji} {label}</span></div>", unsafe_allow_html=True)
    col_s, col_r = st.columns([0.40, 0.60], gap="small")
    with col_s:
        _render_left(feed, price_info, tech, _ms, m_sc, m_dir, tech_sc, tech_dir, mr, panel_key)
    with col_r:
        _render_right(feed, tech, mr, expected_corrs, symbols_cfg, price_info, CN, panel_key)


def _update_macro(ms, feed, syms, weights, ecorrs):
    tp = feed.get_current_price(syms["target"])
    tb = tp.get("bid", 0)
    if tb <= 0: return
    pt = ms._prev_prices.get("target", tb)
    rt = (tb - pt) / pt * 10000 if pt > 0 else 0
    ms._prev_prices["target"] = tb
    for ak in weights:
        sym = syms.get(ak, "")
        if not sym: continue
        try:
            pi = feed.get_current_price(sym)
            cb = pi.get("bid", 0) if pi else 0
            if cb <= 0: continue
            pb = ms._prev_prices.get(ak, cb)
            ra = (cb - pb) / pb * 10000
            ms._prev_prices[ak] = cb
            es = np.sign(ecorrs.get(ak, 0))
            ms.tracker.update(ak, rt, ra, es)
        except Exception: pass


def _calc_macro(ms, feed, syms, ecorrs, weights):
    votes = {}; twv = 0.0; tmw = 0.0
    for ak, bw in weights.items():
        sym = syms.get(ak, "")
        if not sym: continue
        cd = ms.tracker.get_confidence(ak)
        conf = cd.get("confidence", 0.0); warm = cd.get("warmup", True)
        try:
            m1 = feed.get_data(sym, timeframe_minutes=1, bars=10)
            if m1 is not None and len(m1) >= 4:
                c = m1['close'].values; rb = (c[-1] - c[-4]) / c[-4] * 10000
            else: rb = 0.0
        except Exception: rb = 0.0
        es = np.sign(ecorrs.get(ak, 0))
        rv = np.tanh(rb / 5.0) * es; ew = conf * bw; wv = rv * ew
        twv += wv; tmw += ew
        votes[ak] = {"return_bps": round(rb, 2), "raw_vote": round(rv, 3),
                      "confidence": round(conf, 3), "weighted_vote": round(wv, 3), "warmup": warm}
    cons = twv / tmw if tmw > 0.01 else 0.0
    sc = round(max(0, min(100, 50 + cons * 50)), 1)
    dr = "LONG" if cons > 0.15 else ("SHORT" if cons < -0.15 else "NEUTRAL")
    ac = ms.tracker.get_all_confidence()
    cv = [v["confidence"] for v in ac.values() if not v.get("warmup")]
    avg = sum(cv) / len(cv) if cv else 0.0
    return {"score": sc, "direction": dr, "consensus_raw": round(cons, 4),
            "votes": votes, "confidence_avg": round(avg, 3),
            "total_assets_tracked": len(votes),
            "assets_warmed_up": sum(1 for v in votes.values() if not v["warmup"])}


def _render_left(feed, pi, tech_d, _ms, m_sc, m_dir, t_sc, t_dir, mr, pk):
    bk = f"pb_{pk}"; tk = f"pt_{pk}"
    if bk not in st.session_state:
        st.session_state[bk] = []; st.session_state[tk] = []
    cb = pi.get("bid", 0); nt = time.time()
    if cb > 0:
        st.session_state[bk].append(cb); st.session_state[tk].append(nt)
        if len(st.session_state[bk]) > 200:
            st.session_state[bk] = st.session_state[bk][-200:]
            st.session_state[tk] = st.session_state[tk][-200:]
    buf = st.session_state[bk]; tsb = st.session_state[tk]; n = len(buf)
    vs = vm = vl = v5 = 0.0; acs = acm = acl = ac5 = 0.0; vel = acc = 0.0
    if n >= 2:
        dt = tsb[-1] - tsb[-2]
        if dt > 0: vs = (buf[-1] - buf[-2]) / dt
        vel = vs
    if n >= 3: acs = _accel_w(buf, tsb, 3); acc = acs
    if n >= 6:
        dtm = tsb[-1] - tsb[-6]
        if dtm > 0: vm = (buf[-1] - buf[-6]) / dtm
        acm = _accel_w(buf, tsb, 6)
    if n >= 12:
        dtl = tsb[-1] - tsb[-12]
        if dtl > 0: vl = (buf[-1] - buf[-12]) / dtl
        acl = _accel_w(buf, tsb, 12)
    if n >= 24:
        dt5 = tsb[-1] - tsb[-24]
        if dt5 > 0: v5 = (buf[-1] - buf[-24]) / dt5
        ac5 = _accel_w(buf, tsb, 24)
    def vb(v, s=0.05): return max(-25, min(25, (v / s) * 25))
    def ab(a, s=0.01): return max(-10, min(10, (a / s) * 10))
    # ── Fused signal cards (TÉCNICO) ──
    tfs = tech_d.get("tf_scores", {})
    scm = {t: tfs.get(t, {}).get("score", 50) for t in ("M1","M2","M5","M15")}
    dm = {t: tfs.get(t, {}).get("direction", "NEUTRAL") for t in ("M1","M2","M5","M15")}
    fds = [("⚡","5s",{"M1":1.0},vs,acs,0.50,0.30),("🔄","30s",{"M1":0.6,"M2":0.4},vm,acm,0.30,0.15),
           ("📊","1m",{"M1":0.4,"M2":0.3,"M5":0.3},vl,acl,0.15,0.05),("📈","5m",{"M5":0.6,"M15":0.4},v5,ac5,0.10,0.03)]
    cells = ""
    for ic,sp,wt,_v,_a,vw,aw in fds:
        vL = sum(w for t,w in wt.items() if dm.get(t)=="LONG")
        vS = sum(w for t,w in wt.items() if dm.get(t)=="SHORT")
        sd = "LONG" if vL>vS and vL>0.3 else ("SHORT" if vS>vL and vS>0.3 else "NEUTRAL")
        bl = sum(scm.get(t,50)*w for t,w in wt.items())
        _vb = vb(_v); _ab = ab(_a)
        enh = max(0, min(100, bl + (_vb * vw * 2) + (_ab * aw * 2)))
        sd2 = "LONG" if enh >= 55 else ("SHORT" if enh <= 45 else "NEUTRAL")
        dis = (sd != sd2) and sd != "NEUTRAL" and sd2 != "NEUTRAL"
        cv = min(100, abs(enh - 50) * 2)
        if sd=="LONG": r,g,b=82,183,136; ar="▲"; ac2="COMPRAR"; ep=pi.get("ask",0)
        elif sd=="SHORT": r,g,b=239,71,111; ar="▼"; ac2="VENDER"; ep=pi.get("bid",0)
        else: r,g,b=255,209,102; ar="◆"; ac2="ESPERAR"; ep=0
        op = 0.10+(cv/100)*0.45
        tc = f"rgb({r},{g},{b})"; bg = f"rgba({r},{g},{b},{op:.2f})"
        dot = (f"<span style='position:absolute;top:1px;right:2px;font-size:7px;"
               f"color:#ff9f1c;' title='Téc≠Deriv'>●</span>") if dis else ""
        ept = f"<div style='font-size:9px;color:#666;'>{ep:.1f}</div>" if ep>0 else ""
        cells += (f"<td style='background:{bg};padding:4px 4px;text-align:center;"
                  f"border-right:1px solid #333;width:25%;position:relative;'>{dot}"
                  f"<div style='font-size:18px;color:{tc};font-weight:900;line-height:1.2;'>{ar}</div>"
                  f"<div style='font-size:10px;color:{tc};font-weight:bold;line-height:1.2;'>{ac2}</div>"
                  f"<div style='font-size:13px;color:#fff;font-weight:bold;line-height:1.2;'>{cv:.0f}%</div>"
                  f"{ept}</td>")
    sig = (f"<div style='background:#151820;border-radius:8px;overflow:hidden;'>"
           f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;margin:0;'><tr>{cells}</tr></table>"
           f"<div style='text-align:center;font-size:7px;color:#555;letter-spacing:2px;padding:1px 0;'"
           f">TÉCNICO</div></div>")
    st.markdown(_tt(sig, "🎯 Señales Fusionadas", "Dirección + derivadas de precio", "down"), unsafe_allow_html=True)
    # ── Momentum bar ──
    if vs > 0.01 and acc > 0.001: mt2 = "📈 Subiendo y acelerando"; mc = "#52b788"; mi = "⏫"
    elif vs > 0.01 and acc < -0.001: mt2 = "📈 Subiendo pero frenando"; mc = "#a8d5a2"; mi = "🔼"
    elif vs > 0: mt2 = "↗️ Subiendo suave"; mc = "#888"; mi = "🔼"
    elif vs < -0.01 and acc < -0.001: mt2 = "📉 Bajando y acelerando"; mc = "#ef476f"; mi = "⏬"
    elif vs < -0.01 and acc > 0.001: mt2 = "📉 Bajando pero frenando"; mc = "#f4a0b0"; mi = "🔽"
    elif vs < 0: mt2 = "↘️ Bajando suave"; mc = "#888"; mi = "🔽"
    else: mt2 = "➡️ Sin movimiento"; mc = "#555"; mi = "⏸️"
    mp = min(100, abs(vs) / 0.05 * 100)
    bc2 = "#52b788" if vs > 0 else "#ef476f"
    fd = "right" if vs > 0 else "left"
    di = (f"<div style='background:#1a1d23;border-radius:8px;padding:3px 8px;margin-top:2px;'>"
          f"<div style='display:flex;justify-content:space-between;align-items:center;font-size:11px;'>"
          f"<span style='color:{mc};font-weight:bold;'>{mi} {mt2}</span>"
          f"<span style='color:#555;font-size:9px;'>{n} ticks</span></div>"
          f"<div style='background:#111;border-radius:3px;height:4px;margin-top:2px;overflow:hidden;'>"
          f"<div style='width:{mp:.0f}%;height:100%;background:{bc2};"
          f"border-radius:3px;float:{fd};'></div></div></div>")
    st.markdown(_tt(di, "📈 Momentum", f"Vel: {vs:+.4f}/s | Buffer: {n} ticks", "down"), unsafe_allow_html=True)
    # ── Macro derivative cards ──
    mbk = f"mb_{pk}"; mtk = f"mt_{pk}"
    if mbk not in st.session_state:
        st.session_state[mbk] = []; st.session_state[mtk] = []
    st.session_state[mbk].append(m_sc); st.session_state[mtk].append(time.time())
    if len(st.session_state[mbk]) > 200:
        st.session_state[mbk] = st.session_state[mbk][-200:]
        st.session_state[mtk] = st.session_state[mtk][-200:]
    mb = st.session_state[mbk]; mts = st.session_state[mtk]; mn = len(mb)
    def mv(b2,t2,w):
        if len(b2)<w+1: return 0.0
        dt=t2[-1]-t2[-w]; return (b2[-1]-b2[-w])/dt if dt>0 else 0.0
    def ma(b2,t2,w):
        if len(b2)<w+1: return 0.0
        mid=w//2; d1=t2[-1]-t2[-mid] if t2[-1]!=t2[-mid] else 1
        d2=t2[-mid]-t2[-w] if t2[-mid]!=t2[-w] else 1
        v1=(b2[-1]-b2[-mid])/d1; v2=(b2[-mid]-b2[-w])/d2
        return (v1-v2)/((d1+d2)/2) if (d1+d2)>0 else 0.0
    def mvb2(v2,s=2.0): return max(-25,min(25,(v2/s)*25))
    def mab2(a2,s=0.5): return max(-10,min(10,(a2/s)*10))
    mcd = [("⚡","5s",mv(mb,mts,2) if mn>=3 else 0,ma(mb,mts,3) if mn>=4 else 0,0.50,0.30),
           ("🔄","30s",mv(mb,mts,6) if mn>=7 else 0,ma(mb,mts,6) if mn>=7 else 0,0.30,0.15),
           ("📊","1m",mv(mb,mts,12) if mn>=13 else 0,ma(mb,mts,12) if mn>=13 else 0,0.15,0.05),
           ("📈","5m",mv(mb,mts,24) if mn>=25 else 0,ma(mb,mts,24) if mn>=25 else 0,0.10,0.03)]
    mcc = ""
    for ic,sp,_v,_a,vw,aw in mcd:
        _vb2=mvb2(_v); _ab2=mab2(_a)
        enh2=max(0,min(100,m_sc+(_vb2*vw*2)+(_ab2*aw*2)))
        sd="LONG" if enh2>=55 else ("SHORT" if enh2<=45 else "NEUTRAL")
        cv2=min(100,abs(enh2-50)*2)
        if sd=="LONG": r,g,b=82,183,136; ar="▲"; ac3="COMPRAR"
        elif sd=="SHORT": r,g,b=239,71,111; ar="▼"; ac3="VENDER"
        else: r,g,b=255,209,102; ar="◆"; ac3="ESPERAR"
        op2=0.10+(cv2/100)*0.45
        tc2=f"rgb({r},{g},{b})"; bg2=f"rgba({r},{g},{b},{op2:.2f})"
        mcc += (f"<td style='background:{bg2};padding:4px 4px;text-align:center;"
                f"border-right:1px solid #333;width:25%;'>"
                f"<div style='font-size:18px;color:{tc2};font-weight:900;line-height:1.2;'>{ar}</div>"
                f"<div style='font-size:10px;color:{tc2};font-weight:bold;line-height:1.2;'>{ac3}</div>"
                f"<div style='font-size:13px;color:#fff;font-weight:bold;line-height:1.2;'>{cv2:.0f}%</div>"
                f"</td>")
    mch = (f"<div style='background:#151820;border-radius:8px;overflow:hidden;margin-top:3px;'>"
           f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;margin:0;'><tr>{mcc}</tr></table>"
           f"<div style='text-align:center;font-size:7px;color:#555;letter-spacing:2px;padding:1px 0;'"
           f">MACRO</div></div>")
    st.markdown(_tt(mch, "🌍 Señales Macro", f"Buffer: {mn} muestras", "down"), unsafe_allow_html=True)
    # ── Triple Signal + Confluence ──
    fu = _ms.calculate_fusion(t_sc, t_dir, m_sc, m_dir)
    def mc2(lb, sc2, dr2):
        if dr2=='LONG': clr='#52b788'; a='▲'; ac4='COMPRAR'
        elif dr2=='SHORT': clr='#ef476f'; a='▼'; ac4='VENDER'
        else: clr='#ffd166'; a='◆'; ac4='ESPERAR'
        bp=min(100,abs(sc2-50)*2); bs='left' if sc2>=50 else 'right'
        return (f"<td style='width:33.3%;padding:0 2px;vertical-align:top;'>"
                f"<div style='background:#1a1d23;border-radius:6px;padding:3px 4px;"
                f"text-align:center;border:1px solid {clr}22;'>"
                f"<div style='font-size:8px;color:#888;line-height:1;'>{lb}</div>"
                f"<div style='font-size:16px;color:{clr};font-weight:900;line-height:1.1;'>{a}</div>"
                f"<div style='font-size:13px;color:{clr};font-weight:bold;line-height:1.1;'>{sc2:.0f}</div>"
                f"<div style='font-size:8px;color:{clr};font-weight:bold;line-height:1.1;'>{ac4}</div>"
                f"<div style='background:#2a2d35;border-radius:2px;height:3px;margin-top:2px;overflow:hidden;'>"
                f"<div style='background:{clr};height:100%;width:{bp:.0f}%;border-radius:2px;"
                f"float:{bs};'></div></div></div></td>")
    t1=mc2('🔧 Técnico',t_sc,t_dir); t2=mc2('🌍 Macro',m_sc,m_dir)
    t3=mc2('⚡ Fusión',fu['score'],fu['direction'])
    cp=fu['confluence_pct']
    cc='#52b788' if fu['aligned'] else ('#ef476f' if fu['opposed'] else '#ffd166')
    cl='✅ CONFL' if fu['aligned'] else ('⚠️ DIVER' if fu['opposed'] else '➡️ PARCIAL')
    rk=fu['risk_mode']
    th = (f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;margin:3px 0 0 0;'>"
          f"<tr>{t1}{t3}{t2}</tr></table>")
    ch = (f"<div style='background:#1a1d23;border-radius:6px;padding:2px 6px;margin-top:2px;'>"
          f"<div style='display:flex;justify-content:space-between;align-items:center;font-size:9px;'>"
          f"<span style='color:{cc};font-weight:bold;'>{cl} {cp:.0f}%</span>"
          f"<span style='color:#555;'>{fu['risk_emoji']} {rk}</span></div>"
          f"<div style='background:#2a2d35;border-radius:3px;height:4px;margin-top:2px;overflow:hidden;'>"
          f"<div style='background:{cc};height:100%;width:{cp:.0f}%;border-radius:3px;'></div></div></div>")
    st.markdown(_tt(th+ch, '🧪 Triple Signal System',
        f"Téc: {t_sc:.0f} | Macro: {m_sc:.0f} | Fusión: {fu['score']:.0f}", 'down'), unsafe_allow_html=True)


def _slider_bar(label, wpct, score, msg):
    if score >= 65: bc = "#52b788"
    elif score >= 45: bc = "#ffd166"
    else: bc = "#ef476f"
    p = max(0, min(100, score))
    return (f"<div style='margin:3px 0;'>"
            f"<div style='display:flex;justify-content:space-between;font-size:10px;margin-bottom:1px;'>"
            f"<span style='color:#aaa;'><b>{label}</b> ({wpct}%)</span>"
            f"<span style='color:{bc};font-weight:bold;'>{score:.0f}</span></div>"
            f"<div style='background:#2a2d35;border-radius:3px;height:6px;width:100%;overflow:hidden;'>"
            f"<div style='background:{bc};height:100%;width:{p}%;border-radius:3px;'"
            f"transition:width 0.3s;'></div></div>"
            f"<div style='font-size:11px;color:#777;margin-top:1px;'>{msg}</div></div>")


def _render_right(feed, tech_d, mr, ecorrs, syms, pi, CN, pk):
    tfs = tech_d.get("tf_scores", {})
    if tfs:
        tfo = ["M1","M2","M5","M15"]
        atfs = [t for t in tfo if t in tfs]
        tcols = st.columns(len(atfs), gap="small")
        tw = {"M1":"35%","M2":"35%","M5":"20%","M15":"10%"}
        trl = {"M1":"Ejecución","M2":"Confirmación","M5":"Tendencia","M15":"Contexto"}
        for ci, tf in enumerate(atfs):
            r = tfs[tf]; sc = r.get("score",50); dr = r.get("direction","NEUTRAL")
            sigs = r.get("signals",{}); dets = r.get("details",{}); rsi = sigs.get("rsi",0)
            _i = min(1.0, abs(sc-50)/40)
            if sc >= 50:
                cr2=int(136-(136-82)*_i); cg2=int(136+(183-136)*_i); cb2=136
            else:
                cr2=int(136+(239-136)*_i); cg2=int(136-(136-71)*_i); cb2=int(136-(136-111)*_i)
            clr = f"rgb({cr2},{cg2},{cb2})"
            em = "🟢" if sc>=65 else ("🟡" if sc>=50 else "🔴")
            rc = "#ef476f" if rsi>=70 else ("#52b788" if rsi<=30 else "#aaa")
            rt = "OB" if rsi>=70 else ("OS" if rsi<=30 else "")
            if dr=="LONG": act="📈 COMPRAR"
            elif dr=="SHORT": act="📉 VENDER"
            else: act="🟡 ESPERAR"
            # Build tooltip content (identical to USDCLP)
            rp = []
            if dr=="LONG": rp.append(f"✅ <b>Señal COMPRAR</b> ({sc}/100).")
            elif dr=="SHORT": rp.append(f"✅ <b>Señal VENDER</b> ({sc}/100).")
            else: rp.append(f"🟡 <b>Sin dirección clara</b> ({sc}/100).")
            if rsi>=70: rp.append(f"<br>⚠️ RSI <b>{rsi:.0f}</b> SOBRECOMPRA.")
            elif rsi<=30: rp.append(f"<br>⚠️ RSI <b>{rsi:.0f}</b> SOBREVENTA.")
            elif rsi>55: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — alcista.")
            elif rsi<45: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — bajista.")
            else: rp.append(f"<br>RSI <b>{rsi:.0f}</b> — neutral.")
            rp.append(f"<br><div style='border-top:1px solid #444;padding-top:4px;margin-top:4px;'>"
                       f"<b>📋 Indicadores {tf}:</b></div>")
            ed = dets.get("ema",{}); esc = ed.get("score",50)
            e9=sigs.get("ema_9",0); e21=sigs.get("ema_21",0); e50=sigs.get("ema_50",0)
            if e9>e21>e50>0: emsg="<b>9>21>50 ✓</b> · Tendencia LONG"
            elif e9<e21<e50 and e50>0: emsg="<b>9<21<50 ✓</b> · Tendencia SHORT"
            else: emsg="<b>Entrelazadas</b> · Sin tendencia clara"
            rp.append(_slider_bar("EMA",30,esc,emsg))
            rd=dets.get("rsi",{}); rsc=rd.get("score",50)
            rp.append(_slider_bar("RSI",20,rsc,f"<b>RSI: {rsi:.0f}</b>"))
            md=dets.get("macd",{}); msc2=md.get("score",50); mh=sigs.get("macd_histogram",0)
            rp.append(_slider_bar("MACD",25,msc2,f"<b>H: {mh:+.4f}</b>"))
            bd=dets.get("bb",{}); bsc=bd.get("score",50); bp=sigs.get("bb_pct",0.5)
            rp.append(_slider_bar("BB",15,bsc,f"<b>BB: {bp:.0%}</b>"))
            pd2=dets.get("pa",{}); psc=pd2.get("score",50)
            rp.append(_slider_bar("PA",10,psc,"Price Action"))
            card = (f"<div style='text-align:center;background:#1a1d23;padding:2px 2px;border-radius:5px;'>"
                    f"<div style='font-size:10px;color:#888;line-height:1.1;'>{tf} ({tw.get(tf,'')})</div>"
                    f"<div style='font-size:22px;color:{clr};font-weight:bold;line-height:1.1;'>{em} {sc}</div>"
                    f"<div style='font-size:11px;color:{clr};font-weight:bold;line-height:1.1;'>{act}</div>"
                    f"<div style='font-size:11px;color:{rc};margin-top:1px;border-top:1px solid #333;"
                    f"padding-top:1px;line-height:1.2;'>RSI: <b>{rsi:.0f}</b> {rt}</div></div>")
            with tcols[ci]:
                st.markdown(_tt(card, f"{trl.get(tf,tf)} — {tf} ({tw.get(tf,'')})",
                            "".join(rp), "down"), unsafe_allow_html=True)
    st.markdown("<div style='margin-top:3px;'></div>", unsafe_allow_html=True)
    # ── S/R Levels + Macro Votes ──
    from sentinel.levels_engine import calculate_levels
    levels = calculate_levels(feed, syms["target"])
    combined = levels.get("combined", {}); curr_price = levels.get("current_price", 0)
    if curr_price == 0: curr_price = pi.get("bid", 0)
    col_macro_sub, col_levels_sub = st.columns([0.75, 0.25], gap="small")
    # ── Levels column ──
    with col_levels_sub:
        if combined and curr_price > 0:
            above = combined.get("above", []); below = combined.get("below", [])
            for i, lv in enumerate(reversed(above)):
                lb = f"R{len(above)-i}"
                rh = (f"<div style='display:flex;justify-content:space-between;align-items:center;padding:4px 3px;"
                      f"font-family:monospace;background:rgba(239,71,111,0.08);"
                      f"border-left:2px solid #ef476f;border-radius:2px;margin:0;line-height:1.3;'>"
                      f"<span style='color:#ef476f;font-size:9px;'>{lb}</span>"
                      f"<span style='font-weight:bold;font-size:16px;color:#ddd;'>{lv['price']:.1f}</span>"
                      f"<span style='color:#ef476f;font-size:9px;'>{lv['pct']:+.1f}%</span></div>")
                st.markdown(_tt(rh, f"🔴 {lb} — Resistencia ({lv['price']:.2f})",
                    f"Distancia: {abs(lv['pct']):.2f}%", "down"), unsafe_allow_html=True)
            sprd = pi.get('spread',0); src = 'MT5' if pi.get('source')=='mt5' else 'Yahoo'
            sym_lbl = syms['target'][:3]
            st.markdown(_tt(
                f"<div style='display:flex;justify-content:space-between;align-items:center;padding:5px 3px;"
                f"font-family:monospace;background:rgba(76,201,240,0.12);border:1px solid #4cc9f0;"
                f"border-radius:2px;margin:1px 0;line-height:1.3;'>"
                f"<span style='color:#4cc9f0;font-size:9px;font-weight:bold;'>{sym_lbl}</span>"
                f"<span style='font-size:17px;font-weight:bold;color:#4cc9f0;'>{curr_price:.1f}</span>"
                f"<span style='color:#4cc9f0;font-size:9px;'>±{sprd:.0f}</span></div>",
                "💲 Precio en Vivo",
                f"Bid: {pi['bid']:.2f} | Ask: {pi['ask']:.2f} | Spread: {sprd:.2f}<br>Fuente: <b>{src}</b>",
                "down"), unsafe_allow_html=True)
            for i, lv in enumerate(below):
                lb = f"S{i+1}"
                rh = (f"<div style='display:flex;justify-content:space-between;align-items:center;padding:4px 3px;"
                      f"font-family:monospace;background:rgba(82,183,136,0.08);"
                      f"border-left:2px solid #52b788;border-radius:2px;margin:0;line-height:1.3;'>"
                      f"<span style='color:#52b788;font-size:9px;'>{lb}</span>"
                      f"<span style='font-weight:bold;font-size:16px;color:#ddd;'>{lv['price']:.1f}</span>"
                      f"<span style='color:#52b788;font-size:9px;'>{lv['pct']:+.1f}%</span></div>")
                st.markdown(_tt(rh, f"🟢 {lb} — Soporte ({lv['price']:.2f})",
                    f"Distancia: {abs(lv['pct']):.2f}%", "down"), unsafe_allow_html=True)
        else:
            st.caption("Sin datos")
    # ── Macro Votes column ──
    with col_macro_sub:
        hvotes = mr.get("votes", {}); msc = mr["score"]; mdr = mr["direction"]
        if hvotes:
            tc2 = None
            try:
                tm1 = feed.get_data(syms["target"], timeframe_minutes=1, bars=30)
                if tm1 is not None and len(tm1) >= 10: tc2 = tm1['close'].values
            except Exception: pass
            cch = {}
            for hk in ecorrs:
                cas = syms.get(hk, "")
                if not cas or tc2 is None: continue
                try:
                    cm1 = feed.get_data(cas, timeframe_minutes=1, bars=30)
                    if cm1 is not None and len(cm1) >= 10:
                        cls = cm1['close'].values; ml = min(len(tc2), len(cls))
                        if ml >= 10:
                            tr2 = np.diff(np.log(tc2[-ml:])); ar2 = np.diff(np.log(cls[-ml:]))
                            rc2 = np.corrcoef(tr2, ar2)[0, 1]
                            if np.isfinite(rc2):
                                es = np.sign(ecorrs.get(hk, 0)); dc = rc2 * es
                                cch[hk] = round(min(100, max(0, (dc + 0.5) * 100)))
                except Exception: pass
            FO = list(ecorrs.keys())
            vrows = ""
            for hk in FO:
                hv = hvotes.get(hk)
                if not hv: continue
                nm = CN.get(hk, hk); ret = hv["return_bps"]; wv = hv["weighted_vote"]; wrm = hv["warmup"]
                if wv > 0.05: hc2="#52b788"; hd="LONG"
                elif wv < -0.05: hc2="#ef476f"; hd="SHORT"
                else: hc2="#555"; hd="—"
                wt2 = " <span style='color:#ff6b6b;font-size:8px;'>⏳</span>" if wrm else ""
                hoy = cch.get(hk, -1)
                if hoy < 0: hh = "<span style='color:#555;font-size:10px;'>--</span>"
                else:
                    hcc = "#52b788" if hoy>=65 else ("#ffd166" if hoy>=40 else "#ef476f")
                    hh = f"<span style='color:{hcc};font-size:11px;font-weight:bold;'>{hoy}%</span>"
                vrows += (f"<tr style='border-bottom:1px solid #1a1d23;'>"
                          f"<td style='padding:3px 3px;color:#ccc;font-size:12px;'>{nm}{wt2}</td>"
                          f"<td style='padding:3px 3px;text-align:right;color:{'#52b788' if ret>0 else '#ef476f' if ret<0 else '#555'};font-size:12px;'>"
                          f"{ret:+.1f}</td>"
                          f"<td style='padding:3px 3px;text-align:center;color:{hc2};font-weight:bold;font-size:12px;'>{hd}</td>"
                          f"<td style='padding:3px 3px;text-align:center;'>{hh}</td></tr>")
            hmc = "#52b788" if msc>=65 else ("#ffd166" if msc>=50 else "#ef476f")
            tbl = (f"<div class='macro-votes-wrap'>"
                   f"<table style='width:100%;font-size:12px;font-family:monospace;"
                   f"border-collapse:collapse;line-height:1.5;'>{vrows}</table>"
                   f"<div style='text-align:center;margin-top:auto;padding:2px;"
                   f"border-top:1px solid #333;font-size:13px;'>"
                   f"<span style='color:{hmc};font-weight:bold;'>Macro: {msc:.0f}</span>"
                   f" <span style='color:{hmc};font-size:11px;'>{mdr}</span></div></div>")
            st.markdown(_tt(tbl, "🌍 Votos Macro por Activo",
                f"Consenso: {mr['consensus_raw']:+.4f}", "down"), unsafe_allow_html=True)
        else:
            st.caption("⏳ Macro...")

