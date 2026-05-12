"""Smoke test para SENTINEL v3"""
import sys
sys.path.insert(0, 'd:/FOREX')

print("Importando módulos...")
from sentinel.config import SYMBOLS, RISK, WEIGHTS
print("  ✅ config OK")
from sentinel.data_feed import DataFeed
print("  ✅ data_feed OK")
from sentinel.indicators import calculate_all
print("  ✅ indicators OK")
from sentinel.correlation_engine import calculate_target_correlations
print("  ✅ correlation_engine OK")
from sentinel.technical_scorer import calculate_technical_score
print("  ✅ technical_scorer OK")
from sentinel.sentinel_core import SentinelCore
print("  ✅ sentinel_core OK")
from sentinel.risk_manager import calculate_position_size
print("  ✅ risk_manager OK")

print("\n=== TEST FUNCIONAL ===")
feed = DataFeed(mode="synthetic")
core = SentinelCore(feed)
result = core.calculate_composite()

score = result["composite_score"]
direction = result["direction"]
signal = result["signal"]

print(f"  Score Compuesto: {score}")
print(f"  Dirección: {direction}")
print(f"  Señal: {signal}")
print(f"  Bloqueado: {result['blocked']}")
print(f"  Alertas: {len(result['alerts'])}")

# Test position sizing
pos = calculate_position_size(1_500_000, 5.5, 950.0)
print(f"\n=== POSITION SIZING ===")
print(f"  Capital: ${pos['capital']:,.0f} CLP")
print(f"  Riesgo: ${pos['risk_amount_clp']:,.0f} CLP ({pos['risk_pct']}%)")
print(f"  SL: {pos['sl_distance']:.4f}")
print(f"  TP: {pos['tp_distance']:.4f}")
print(f"  R:R: 1:{pos['rr_ratio']}")
print(f"  Lots: {pos['lots']}")

print("\n✅✅✅ TODOS LOS TESTS PASARON ✅✅✅")
