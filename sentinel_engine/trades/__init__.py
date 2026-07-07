"""
sentinel_engine.trades — normalized trade schema + broker ingesters (P2, Tasks 2.1-2.3).

Sub-modules:
    schema.py              — Trade schema v1 + validator.
    ingest_xtb.py           — XTB trade-history export -> schema v1 (synthetic fixture,
                              NEEDS REAL-SAMPLE VALIDATION).
    ingest_mt5_trades.py    — MT5 deals-history export -> schema v1 (synthetic fixture,
                              NEEDS REAL-SAMPLE VALIDATION).
"""
