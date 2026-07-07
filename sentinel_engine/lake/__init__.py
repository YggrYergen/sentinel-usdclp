"""
sentinel_engine.lake — Parquet price data lake (P2, Tasks 2.4/2.5).

Sub-modules:
    store.py             — low-level parquet read/write for OHLCV bars.
    manifest.py           — coverage manifest (ranges, gap detection) over a lake root.
    ingest_dukascopy.py   — Dukascopy CSV export -> lake (adapter + synthetic fixture only,
                             NEEDS REAL-SAMPLE VALIDATION).
    ingest_mt5.py          — MT5 OHLC CSV export -> lake (validated against real fixtures
                             under tests/golden/fixtures/csv/**).
"""
