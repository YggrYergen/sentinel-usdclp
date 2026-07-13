"""sentinel_engine.strategies.emasar_variant -- EMASAR V1 with PER-FICHA
trailing (SENTINEL experiment 2026-07-13, trader request).

WHY THIS EXISTS
---------------
The frozen reference engine `emasar_ref.simular` can only trail F3; F1 exits
by bearish/bullish engulfing and F2 by SuperTrend flip. The trader asked for a
variant where EACH ficha (F1/F2/F3) trails with its OWN distance (a "trailing
ladder"), plus two entry tweaks (faster EMAs 5/8 and dropping the EMA-order
gate G1). To honour the "DO NOT EDIT the vendored frozen file" rule (see
`emasar_ref.py` header + golden test `tests/strategies/test_emasar_ref.py`),
this module does NOT touch `emasar_ref`; it IMPORTS its validated indicator +
gate math and only reimplements the position-management loop.

ENTRY PARITY: the entry decision calls the SAME `gate_long`/`gate_short` from
`emasar_ref` with the same parameters, so given identical params entries match
the reference engine exactly. Only the EXITS differ (all trailing, no
engulfing / no SuperTrend flip).

SCOPE: V1 only (3 fichas F1/F2/F3), close-entry (entry_timing=0), shared
initial range-SL (the "legal" stop). This is intentionally a focused
experiment simulator, not a general re-implementation of every Fase-1 branch.
"""
from __future__ import annotations

from typing import Any

from .emasar_ref import (
    ema_series,
    sar_series,
    ao_series,
    ac_series,
    momentum_series,
    gate_long,
    gate_short,
    pip_size,
    _Ficha,
)


def simular_variant(
    bars: list[dict[str, Any]],
    *,
    confirm_mode: int = 2,
    symbol: str = "XAUUSD",
    pipsize_input: float = 0.0,
    ema_fast: int = 5,
    ema_slow: int = 8,
    sar_step: float = 0.3,
    sar_max: float = 0.3,
    mom_period: int = 14,
    confirm_count: int = 2,
    require_ema_order: bool = False,
    init_sl_range_k: float = 1.0,
    f1_trail_pips: float = 289.0,
    f2_trail_pips: float = 230.0,
    f3_trail_pips: float = 170.0,
    allow_long: bool = True,
    allow_short: bool = True,
) -> list[dict[str, Any]]:
    """Simulate EMASAR V1 with a per-ficha trailing ladder.

    Returns the same event shape as `emasar_ref.simular`:
    [{'idx', 'lado':'L'|'S', 'precio', 'motivo', 'ficha':'F1'|'F2'|'F3'|None}].
    motivo in {ENTRY_L, ENTRY_S, EXIT_INITSL, EXIT_TRAIL}.

    Entry: identical to `emasar_ref` V1 close-entry (gate_long/gate_short with
    use_ema5=False). `require_ema_order=False` drops G1 (EMA-order) leaving G2
    (same-slope). `ema_fast`/`ema_slow` feed the two EMAs (the pullback gate G3
    references the FAST EMA in V1).

    Exit: all three fichas share the initial range-SL
    (LONG sl = low[i] - k*(high[i]-low[i]); SHORT mirror). Then each ficha
    trails with ITS OWN distance (`f1/f2/f3_trail_pips` * pip). An early
    stop-out at the untouched initial SL is tagged EXIT_INITSL; a stop-out
    after the trailing raised the stop is tagged EXIT_TRAIL. There is NO
    engulfing exit and NO SuperTrend flip exit in this variant.
    """
    n = len(bars)
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]

    ema_f = ema_series(closes, ema_fast)   # passed as the "ema8" gate arg
    ema_s = ema_series(closes, ema_slow)   # passed as the "ema20" gate arg
    ema5_unused = [None] * n               # V1 (use_ema5=False) ignores this
    _sar_val, sar_trend = sar_series(highs, lows, sar_step, sar_max)
    ao = ao_series(highs, lows)
    ac = ac_series(highs, lows)
    mom = momentum_series(closes, mom_period)

    pip = pip_size(symbol, pipsize_input)
    trail_by_tag = {
        "F1": f1_trail_pips * pip,
        "F2": f2_trail_pips * pip,
        "F3": f3_trail_pips * pip,
    }

    def _sl_inicial(lado: int, idx: int) -> float:
        rango = bars[idx]["high"] - bars[idx]["low"]
        return (bars[idx]["low"] - init_sl_range_k * rango) if lado == +1 \
            else (bars[idx]["high"] + init_sl_range_k * rango)

    eventos: list[dict[str, Any]] = []
    fichas: dict[str, _Ficha] = {}

    for i in range(n):
        bar = bars[i]
        px = bar["close"]

        # ---- 1) exits for open fichas (each trails with its own distance) ----
        for tag in list(fichas.keys()):
            f = fichas[tag]
            if not f.abierta:
                continue
            lado_txt = "L" if f.lado == +1 else "S"

            # Initial SL (still-untouched stop) -- checked before this bar's
            # trailing raise, so a same-bar hit here is tagged EXIT_INITSL.
            if f.lado == +1 and bar["low"] <= f.sl:
                f.abierta = False
                eventos.append({"idx": i, "lado": lado_txt, "precio": f.sl,
                                "motivo": "EXIT_INITSL", "ficha": tag})
                continue
            if f.lado == -1 and bar["high"] >= f.sl:
                f.abierta = False
                eventos.append({"idx": i, "lado": lado_txt, "precio": f.sl,
                                "motivo": "EXIT_INITSL", "ficha": tag})
                continue

            # Per-ficha trailing: SL only tightens toward price; the range-SL
            # is the floor until the trailing overtakes it.
            trail_efectivo = trail_by_tag[tag]
            if f.lado == +1:
                f.max_fav = max(f.max_fav, bar["high"])
                nuevo_sl = f.max_fav - trail_efectivo
                if f.sl is None or nuevo_sl > f.sl:
                    f.sl = nuevo_sl
                if bar["low"] <= f.sl:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": f.sl,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue
            else:
                f.max_fav = min(f.max_fav, bar["low"])
                nuevo_sl = f.max_fav + trail_efectivo
                if f.sl is None or nuevo_sl < f.sl:
                    f.sl = nuevo_sl
                if bar["high"] >= f.sl:
                    f.abierta = False
                    eventos.append({"idx": i, "lado": lado_txt, "precio": f.sl,
                                    "motivo": "EXIT_TRAIL", "ficha": tag})
                    continue

        fichas = {k: v for k, v in fichas.items() if v.abierta}

        # ---- 2) entry (no reentry while any ficha is open) ----
        if fichas:
            continue

        long_ok, _ = gate_long(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                               confirm_mode=confirm_mode, use_ema5=False,
                               confirm_count=confirm_count, require_ema_order=require_ema_order)
        short_ok, _ = gate_short(bars, ema_f, ema_s, ema5_unused, sar_trend, ao, ac, mom, i,
                                 confirm_mode=confirm_mode, use_ema5=False,
                                 confirm_count=confirm_count, require_ema_order=require_ema_order)

        if long_ok and allow_long:
            eventos.append({"idx": i, "lado": "L", "precio": px, "motivo": "ENTRY_L", "ficha": None})
            sl = _sl_inicial(+1, i)
            fichas = {
                "F1": _Ficha(+1, px, sl),
                "F2": _Ficha(+1, px, sl),
                "F3": _Ficha(+1, px, sl),
            }
        elif short_ok and allow_short:
            eventos.append({"idx": i, "lado": "S", "precio": px, "motivo": "ENTRY_S", "ficha": None})
            sl = _sl_inicial(-1, i)
            fichas = {
                "F1": _Ficha(-1, px, sl),
                "F2": _Ficha(-1, px, sl),
                "F3": _Ficha(-1, px, sl),
            }

    return eventos
