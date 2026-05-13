import sys
sys.path.insert(0, r'd:\FOREX')
from sentinel.data_feed import DataFeed
from sentinel.sentinel_core import SentinelCore

feed = DataFeed(mode='auto')
core = SentinelCore(feed)
r = core.calculate_composite()
c = r['levels']['combined']

print("ABOVE (R):")
for l in c['above']:
    print(f"  {l['label']:20s} {l['price']:10.2f}  {l['pct']:+.3f}%")

print("BELOW (S):")
for l in c['below']:
    print(f"  {l['label']:20s} {l['price']:10.2f}  {l['pct']:+.3f}%")

print(f"\nPrice: {r['levels']['current_price']}")
feed.shutdown()
