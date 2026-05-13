"""Quick integration test for new DataFeed with MT5"""
import sys
sys.path.insert(0, r'd:\FOREX')

from sentinel.data_feed import DataFeed
from sentinel.config import SYMBOLS

feed = DataFeed(mode="auto")
print(f"Mode: {feed.mode}")
print(f"MT5 connected: {feed.mt5_connected}")
print(f"Status: {feed.get_status()}")
print()

print("Testing get_data for each symbol...")
for k, s in SYMBOLS.items():
    df = feed.get_data(s, 15, 50)
    bars = len(df)
    last = f"@ {df['close'].iloc[-1]:.2f}" if bars > 0 else "NO DATA"
    print(f"  {k:8s}: {s:15s} -> {bars:3d} bars {last}")

print()
p = feed.get_current_price(SYMBOLS["target"])
print(f"USDCLP price: bid={p['bid']}, ask={p['ask']}, spread={p['spread']}, source={p.get('source','?')}")

feed.shutdown()
print("\n✅ Test completado")
