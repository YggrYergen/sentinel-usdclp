"""
SENTINEL v3 — Score Técnico Multi-Indicador (thin forwarder).

The technical scoring math now lives ONLY in `sentinel_engine.technical`. This
module is a backward-compat shim that re-exports the byte-identical pure
functions and delegates `calculate_multi_tf_score` to
`sentinel_engine.technical.TechnicalScorer`. The technical config
(timeframes / bars / tf-weights / indicators) is instrument-independent —
identical across every instrument YAML — so the USDCLP config reproduces the
legacy module-global behavior for any symbol (proven by
`tests/test_technical_engine.py` and `tests/test_engine.py`).

Reverting the P1 live-cutover commit restores this file's original standalone
implementation.
"""

# Re-export the byte-identical pure scoring helpers from the engine so the
# scoring math is defined in exactly ONE place.
from sentinel_engine.technical import (  # noqa: F401
    calculate_technical_score,
    detect_rsi_divergences,
    _score_ema,
    _score_rsi,
    _score_macd,
    _score_bb,
    _score_pa,
)

# Pesos por timeframe del score compuesto multi-TF.
# Fuente única de verdad — consumido tanto por el prompt de la IA
# (sentinel/ai_chat.py) como por tests/test_instrument_config.py, que valida
# que sentinel_engine/instruments/*.yaml coincidan con estos literales. Es
# config, no lógica de scoring (la lógica vive en sentinel_engine.technical).
TF_WEIGHTS = {"M15": 0.10, "M5": 0.20, "M2": 0.35, "M1": 0.35}

# Lazily-cached USDCLP InstrumentConfig — avoids re-parsing the YAML on every
# dashboard refresh. The technical config is instrument-independent, so this
# single config drives calculate_multi_tf_score for any symbol.
_USDCLP_CFG = None


def calculate_multi_tf_score(data_feed, symbol: str) -> dict:
    """Delegates to `sentinel_engine.technical.TechnicalScorer(cfg).score`.

    Byte-identical to the legacy multi-timeframe technical score — the math
    is sourced entirely from `sentinel_engine.technical`.
    """
    global _USDCLP_CFG
    if _USDCLP_CFG is None:
        from sentinel_engine.config import load_instrument
        _USDCLP_CFG = load_instrument("usdclp")
    from sentinel_engine.technical import TechnicalScorer
    return TechnicalScorer(_USDCLP_CFG).score(data_feed, symbol)
