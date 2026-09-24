import sys; sys.path.insert(0, 'd:/FOREX')
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore
from sentinel.config import SYMBOLS, EXPECTED_CORRELATIONS

feed = DataFeed()
core = SentinelCore(feed)
result = core.calculate_composite()
comp = result['components']
tf = comp['technical'].get('details', {}).get('tf_scores', {})
price = feed.get_current_price(SYMBOLS['target'])

print('=== PRECIO ===')
print(f"Bid: {price['bid']:.2f} | Ask: {price['ask']:.2f} | Spread: {price['spread']:.2f}")
print()
print('=== SCORE COMPUESTO ===')
print(f"Final: {result['composite_score']} | Dir: {result['direction']}")
print(f"Tecnico: {comp['technical']['score']:.1f} ({comp['technical']['direction']})")
print(f"Correlacion: {comp['correlation']['score']:.1f} ({comp['correlation']['direction']})")
print()
print('=== TIMEFRAMES ===')
for t in ['M1','M2','M5','M15']:
    d = tf.get(t, {})
    sigs = d.get('signals', {})
    dets = d.get('details', {})
    print(f"{t}: score={d.get('score',0):.1f} dir={d.get('direction','?')} rsi={sigs.get('rsi',0):.1f}")
    print(f"   EMA={dets.get('ema',{}).get('score',0):.0f} RSI={dets.get('rsi',{}).get('score',0):.0f} MACD={dets.get('macd',{}).get('score',0):.0f} BB={dets.get('bb',{}).get('score',0):.0f} PA={dets.get('pa',{}).get('score',0):.0f}")
    print(f"   ema9={sigs.get('ema_9',0):.2f} ema21={sigs.get('ema_21',0):.2f} ema50={sigs.get('ema_50',0):.2f}")
    print(f"   macd_h={sigs.get('macd_histogram',0):.5f} bb_pct={sigs.get('bb_pct',0):.2f}")
print()
print('=== CORRELACIONES ===')
corr = comp['correlation'].get('details', {}).get('correlations', {})
for k, v in corr.items():
    if v is None: continue
    exp = EXPECTED_CORRELATIONS.get(k, 0)
    delta = v - exp
    status = 'OK' if abs(delta) < 0.2 else ('WARN' if abs(delta) < 0.4 else 'BREAK')
    print(f"  {k:8s}: real={v:+.2f} exp={exp:+.2f} d={delta:+.2f} [{status}]")
print()
print('=== NIVELES ===')
levels = result.get('levels', {})
cp = levels.get('current_price', 0)
combined = levels.get('combined', {})
print(f"Precio actual: {cp:.2f}")
for lv in combined.get('above', []):
    print(f"  R: {lv['price']:.2f} ({lv['pct']:+.2f}%)")
for lv in combined.get('below', []):
    print(f"  S: {lv['price']:.2f} ({lv['pct']:+.2f}%)")
print()
print('=== ALERTAS ===')
for a in result.get('alerts', [])[:5]:
    print(f"  {a}")
