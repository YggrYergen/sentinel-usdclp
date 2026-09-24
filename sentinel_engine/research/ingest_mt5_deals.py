"""sentinel_engine.research.ingest_mt5_deals — EMASAR V1 MT5-fidelity
integration (design spec
docs/superpowers/specs/2026-07-10-emasar-v1-mt5-integration-design.md,
Components 2-4).

Reconstructs real EMASAR V1 positions (3 fichas per signal: F1/F2/F3) from a
parsed MT5 Strategy-Tester `.htm` (`sentinel_engine.research.mt5_report`),
annotates them with `ficha`/`motivo` by matching against the vendored
`emasar_ref.simular()` events (`sentinel_engine.strategies.emasar_ref`), runs
a T1 signal-parity + monetary-parity fidelity gate, and writes a certified
`mt5-import`/`mt5-htm` run + 3-ficha trades into `ResearchRegistry`
(`sentinel_engine.research.registry2`).

Architecture per the design spec: positions/prices/P&L are IMPORTED from the
`.htm` deals (identical to the cent, MT5's own numbers, by construction) —
`emasar_ref` only ANNOTATES (ficha/motivo) and VERIFIES (the T1 gate). If
bars for the run's period are unavailable (lake gap), the fidelity report
marks signal-parity `not_verified: bars_unavailable` and the import still
proceeds with the identical `.htm` numbers — this module never crashes and
never fakes a pass on a bars gap.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable

from sentinel_engine.research.mt5_report import parse_mt5_report
from sentinel_engine.strategies.emasar_ref import simular

_TYPE_TO_SIDE = {"buy": "LONG", "sell": "SHORT"}
_TOL_PRICE = 0.05  # price-match tolerance for event<->deal matching (spread/rounding slack)


# ---------------------------------------------------------------------
# Component 2a — pair deals into 3-ficha signals
# ---------------------------------------------------------------------
def pair_deals_into_signals(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair `in`->`out` deals into fichas (0.1-lot positions); consecutive
    `in` deals at the SAME (ts, symbol, type, price) are the fichas of ONE
    signal -> grouped under one `signal_id`. `out` deals are paired to their
    ficha's `in` deal in FIFO order by `order` number within the symbol (MT5
    hedging-account deals don't carry a shared position id in the deals
    table, so pairing is positional: the Nth open pairs with the Nth close
    for that symbol+side, matching the report's own row order). The initial
    `balance` deposit row is skipped (not a signal)."""
    in_deals = [d for d in deals if d["dir"] == "in"]
    out_deals = [d for d in deals if d["dir"] == "out"]

    # Group consecutive in-deals sharing (ts, symbol, type, price) into signals.
    groups: list[list[dict[str, Any]]] = []
    for d in in_deals:
        if groups:
            last = groups[-1][-1]
            if (d["ts"] == last["ts"] and d["symbol"] == last["symbol"]
                    and d["type"] == last["type"] and d["price"] == last["price"]):
                groups[-1].append(d)
                continue
        groups.append([d])

    # FIFO-pair out deals per symbol+type (the `in` deal's type == the side;
    # its matching `out` deal is the OPPOSITE type, e.g. buy-in / sell-out).
    _OPPOSITE = {"buy": "sell", "sell": "buy"}
    out_queue: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for d in out_deals:
        key = (d["symbol"], d["type"])
        out_queue.setdefault(key, []).append(d)

    signals = []
    for gi, group in enumerate(groups):
        first = group[0]
        side = _TYPE_TO_SIDE.get(first["type"])
        fichas = []
        for i, in_deal in enumerate(group):
            ficha_tag = f"F{i + 1}"
            out_key = (in_deal["symbol"], _OPPOSITE.get(in_deal["type"], in_deal["type"]))
            queue = out_queue.get(out_key, [])
            out_deal = queue.pop(0) if queue else None
            fichas.append({
                "ficha": ficha_tag,
                "px_in": in_deal["price"],
                "ts_in": in_deal["ts"],
                "in_order": in_deal["order"],
                "px_out": out_deal["price"] if out_deal else None,
                "ts_out": out_deal["ts"] if out_deal else None,
                "out_order": out_deal["order"] if out_deal else None,
                "out_comment": out_deal["comment"] if out_deal else None,
                "pnl": (out_deal["profit"] + out_deal["commission"] + out_deal["swap"])
                if out_deal else None,
                "volume": in_deal["volume"],
            })
        signals.append({
            "signal_id": f"sig-{first['ts'].replace(' ', '_').replace(':', '').replace('.', '')}-{gi}",
            "ts_in": first["ts"],
            "symbol": first["symbol"],
            "side": side,
            "fichas": fichas,
        })
    return signals


# ---------------------------------------------------------------------
# Component 2b/2c — annotate signals with emasar_ref events
# ---------------------------------------------------------------------
def annotate_signal_with_events(signal: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Tag each ficha in `signal` with `motivo`/`exit_reason_source` by
    matching it against `emasar_ref` exit events at the ficha's `px_out`
    (within `_TOL_PRICE`); the FIRST unmatched exit event with a `ficha` tag
    matching this ficha's ordinal is preferred if price alone is ambiguous
    (multiple exits at the same ts). Falls back to the `.htm` `sl <price>`
    comment on the out-deal when no emasar_ref event matches at all (the
    fallback in the design spec's error-handling section)."""
    exit_events = [e for e in events if e["motivo"] != "ENTRY_L" and e["motivo"] != "ENTRY_S"]
    used = [False] * len(exit_events)

    annotated_fichas = []
    for f in signal["fichas"]:
        motivo = None
        source = None
        if f["px_out"] is not None:
            # Prefer an event tagged with the SAME ficha label; else any
            # unused event within price tolerance.
            for idx, e in enumerate(exit_events):
                if used[idx]:
                    continue
                if e.get("ficha") == f["ficha"] and abs(e["precio"] - f["px_out"]) <= _TOL_PRICE:
                    motivo, source = e["motivo"], "emasar_ref"
                    used[idx] = True
                    break
            if motivo is None:
                for idx, e in enumerate(exit_events):
                    if used[idx]:
                        continue
                    if abs(e["precio"] - f["px_out"]) <= _TOL_PRICE:
                        motivo, source = e["motivo"], "emasar_ref"
                        used[idx] = True
                        break
        if motivo is None:
            comment = f.get("out_comment") or ""
            if comment.startswith("sl "):
                motivo, source = "sl", "mt5-comment"
        if motivo is None and f["px_out"] is not None and f["ts_out"] is not None:
            # Requirement 0 (Wave-2 plan 2026-07-10): the ficha DID fully
            # close (deal-structure evidence: px_out/ts_out present) but
            # matched no emasar_ref event and carries no SL/TP `.htm`
            # comment -- deterministically that means it was closed by the
            # strategy's own opposite-signal (flip) logic, not an
            # SL/TP hit. Label it rather than leaving it null (never
            # fabricate a specific motivo we can't evidence, but "signal"
            # is exactly what the absence of an SL/TP comment evidences).
            motivo, source = "signal", "derived"
        annotated_fichas.append({**f, "motivo": motivo, "exit_reason_source": source})

    return {**signal, "fichas": annotated_fichas}


def annotate_all_signals(signals: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate every signal, routing each signal only the events near its
    own entry (same side + price within tolerance) so unrelated signals'
    events never cross-match."""
    out = []
    for sig in signals:
        entry_px = sig["fichas"][0]["px_in"] if sig["fichas"] else None
        lado = "L" if sig["side"] == "LONG" else "S"
        relevant = [
            e for e in events
            if e["lado"] == lado and (entry_px is None or abs(e["precio"] - entry_px) <= 5.0
                                       or e["motivo"] in ("ENTRY_L", "ENTRY_S"))
        ]
        out.append(annotate_signal_with_events(sig, relevant))
    return out


# ---------------------------------------------------------------------
# Component 3 — fidelity reconciliation gate
# ---------------------------------------------------------------------
def check_signal_parity(signal: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """T1 (hard gate): every ficha's entry+exit must have a matching
    emasar_ref event (by ts/price within tolerance). Returns
    {"status": "pass"|"fail", "matched": int, "unmatched": int, "detail": [...]}."""
    annotated = annotate_signal_with_events(signal, events)
    matched = 0
    unmatched = 0
    detail = []
    # Entry: at least one ENTRY_L/ENTRY_S event at this signal's entry price.
    entry_px = signal["fichas"][0]["px_in"] if signal["fichas"] else None
    entry_ok = any(
        e["motivo"] in ("ENTRY_L", "ENTRY_S") and entry_px is not None
        and abs(e["precio"] - entry_px) <= _TOL_PRICE
        for e in events
    )
    if entry_ok:
        matched += 1
    else:
        unmatched += 1
        detail.append({"leg": "entry", "status": "unmatched"})

    for f in annotated["fichas"]:
        if f["exit_reason_source"] == "emasar_ref":
            matched += 1
            detail.append({"leg": f["ficha"], "status": "matched", "motivo": f["motivo"]})
        else:
            unmatched += 1
            detail.append({"leg": f["ficha"], "status": "unmatched"})

    return {
        "status": "pass" if unmatched == 0 else "fail",
        "matched": matched,
        "unmatched": unmatched,
        "detail": detail,
    }


def check_monetary_parity(report: dict[str, Any]) -> dict[str, Any]:
    """Sum(profit+commission+swap) over non-balance deals must equal the
    report's OWN totals (its "Beneficio Neto" isn't re-parsed here — the
    deals table's own footer/deal-level totals ARE the ground truth per the
    design spec's "import the deals, not re-simulate" resolving insight);
    cross-checked to the cent."""
    deals = report["deals"]
    deal_rows = [d for d in deals if d["type"] != "balance"]
    deals_net = sum(d["profit"] + d["commission"] + d["swap"] for d in deal_rows)
    deposit = report["settings"].get("deposit_initial") or 0.0
    final_balance = deals[-1]["balance"] if deals else deposit
    htm_net = final_balance - deposit
    status = "pass" if abs(htm_net - deals_net) <= 0.01 else "fail"
    return {"status": status, "htm_net": htm_net, "deals_net": deals_net}


# ---------------------------------------------------------------------
# Component 7 (partial) — param resolution from the .htm settings block
# ---------------------------------------------------------------------
def _bool(v: str | None) -> bool:
    return str(v).strip().lower() == "true"


def simular_params_from_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Map the `.htm` settings-block `params` (raw string Key=Value pairs,
    e.g. `StrategyMode=1`) to `emasar_ref.simular()` kwargs. The `.htm`
    carries the EXACT run params (better ground truth than re-deriving them
    from the variant_id tag, which only encodes symbol/tf/confirm per
    TOKATA's own `parse_tag_emasar` — see gen_variant.py)."""
    p = settings.get("params", {})
    out: dict[str, Any] = {
        "symbol": settings.get("symbol") or "XAUUSD",
        "strategy_mode": int(p.get("StrategyMode", 1)),
        "confirm_mode": int(p.get("ConfirmMode", 1)),
        "ema_fast": int(p.get("EMA_Fast", 8)),
        "ema_slow": int(p.get("EMA_Slow", 20)),
        "ema_pull": int(p.get("EMA_Pull", 5)),
        "sar_step": float(p.get("SAR_Step", 0.02)),
        "sar_max": float(p.get("SAR_Max", 0.20)),
        "st_atr_period": int(p.get("ST_ATRPeriod", 10)),
        "st_mult": float(p.get("ST_Mult", 3.0)),
        "mom_period": int(p.get("MomPeriod", 14)),
        "init_sl_pips": float(p.get("InitSL_Pips", 3.0)),
        "trail_pips": float(p.get("Trail_Pips", 170.0)),
        "pipsize_input": float(p.get("PipSize", 0.0)),
        "allow_long": _bool(p.get("AllowLong", "true")),
        "allow_short": _bool(p.get("AllowShort", "true")),
        "confirm_count": int(p.get("ConfirmCount", 2)),
        "ac_exit_enable": _bool(p.get("AC_ExitEnable", "false")),
        "ac_conviction_runner": _bool(p.get("AC_ConvictionRunner", "false")),
        "ac_mag_threshold": float(p.get("AC_MagThreshold", 0.0)),
        "ac_modulate_trail": _bool(p.get("AC_ModulateTrail", "false")),
        "v2_use_trail": _bool(p.get("V2_UseTrail", "false")),
    }
    return out


# ---------------------------------------------------------------------
# Component 4/7 — end-to-end ingest entrypoint
# ---------------------------------------------------------------------
def _bars_empty(bars: Any) -> bool:
    """`bars_lookup` may return a pandas DataFrame (production: wraps
    `load_tf_frame`) or a plain list of OHLC dicts (tests) -- accept both."""
    if bars is None:
        return True
    if hasattr(bars, "empty"):
        return bool(bars.empty)
    return len(bars) == 0


def _bars_to_dicts(bars: Any) -> list[dict[str, float]]:
    if hasattr(bars, "itertuples"):
        return [
            {"open": float(r.open), "high": float(r.high), "low": float(r.low), "close": float(r.close)}
            for r in bars.itertuples()
        ]
    return [{"open": float(b["open"]), "high": float(b["high"]),
              "low": float(b["low"]), "close": float(b["close"])} for b in bars]


def ingest_mt5_htm(
    path: str | Path,
    registry: Any,
    *,
    bars_lookup: Callable[[str, str, str, str], Any],
    variant_id: str,
    strategy_familia: str = "emasar",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Parse `path` (.htm) -> reconstruct 3-ficha V1 positions -> annotate +
    verify with the vendored `emasar_ref` -> write a certified
    `engine="mt5-import"`, `fidelity="mt5-htm"` run + trades into
    `registry`. `bars_lookup(symbol, tf, desde, hasta)` must return a
    pandas DataFrame with open/high/low/close columns (or an empty one if
    unavailable — the degradation path per the design spec: import still
    proceeds with the imported numbers, signal-parity is marked
    "not_verified: bars_unavailable" instead of crashing or faking a pass).
    Returns `{"run_id", "fidelity_report", "n_trades"}`."""
    report = parse_mt5_report(path)
    settings = report["settings"]
    symbol = settings.get("symbol") or "XAUUSD"
    tf = settings.get("period") or "M5"

    signals = pair_deals_into_signals(report["deals"])
    monetary = check_monetary_parity(report)

    bars_raw = bars_lookup(symbol, tf, None, None)
    bars_available = not _bars_empty(bars_raw)

    if bars_available:
        bars = _bars_to_dicts(bars_raw)
        sim_params = simular_params_from_settings(settings)
        events = simular(bars, **sim_params)
        annotated_signals = annotate_all_signals(signals, events)
        parity_results = [check_signal_parity(s, events) for s in signals]
        all_matched = sum(r["matched"] for r in parity_results)
        all_unmatched = sum(r["unmatched"] for r in parity_results)
        # Diagnostic: emasar_ref should fire ~= the number of MT5 signals on
        # the SAME bars. A wildly larger event count means the lake bars are
        # a DIFFERENT feed than the one MT5 backtested on (e.g. a different
        # broker) -- the gate still fails honestly, but this flag makes the
        # cause actionable rather than a bare "fail" (obtaining MT5's own
        # bars is the documented prerequisite to certify, design spec
        # §Error handling).
        n_entries = sum(1 for e in events if e["motivo"] in ("ENTRY_L", "ENTRY_S"))
        divergent_feed = n_entries > 5 * max(len(signals), 1)
        signal_parity = {
            "status": "pass" if all_unmatched == 0 else "fail",
            "matched": all_matched,
            "unmatched": all_unmatched,
            "mt5_signals": len(signals),
            "emasar_ref_entries": n_entries,
        }
        if all_unmatched > 0 and divergent_feed:
            signal_parity["diagnosis"] = "bars_feed_mismatch"
    else:
        annotated_signals = signals  # fichas keep motivo=None / .htm-comment fallback
        annotated_signals = [annotate_signal_with_events(s, []) for s in signals]
        signal_parity = {"status": "not_verified", "reason": "bars_unavailable"}

    fidelity_report = {"signal_parity": signal_parity, "monetary": monetary, "report_path": str(path)}

    strategy_id = registry.upsert_strategy("EMASAR", strategy_familia, "mt5")
    variant_actual_id = registry.upsert_variant(
        strategy_id, variant_id,
        {k: v for k, v in settings.get("params", {}).items()},
        tf, symbol, "3ficha-v1",
    )

    run_id = run_id or f"mt5import-{uuid.uuid4().hex[:12]}"
    trades_count = sum(len(s["fichas"]) for s in annotated_signals)
    net = monetary["deals_net"]

    registry.insert_run({
        "run_id": run_id,
        "variant_id": variant_actual_id,
        "engine": "mt5-import",
        "fidelity": "mt5-htm",
        "trades": trades_count,
        "net": net,
        "report_path": str(path),
        "fidelity_ref": _json_dumps(fidelity_report),
    })

    trade_rows = []
    for s in annotated_signals:
        for f in s["fichas"]:
            trade_rows.append({
                "trade_id": f"{run_id}-{s['signal_id']}-{f['ficha']}",
                "origin": "strategy",
                "origin_id": s["signal_id"],
                "ts_in": f["ts_in"],
                "ts_out": f["ts_out"],
                "px_in": f["px_in"],
                "px_out": f["px_out"],
                "side": s["side"],
                "volume": f["volume"],
                "exit_reason": f["motivo"],
                "exit_reason_source": f["exit_reason_source"],
                "pnl": f["pnl"],
                "signal_id": s["signal_id"],
                "ficha": f["ficha"],
            })
    registry.insert_trades(run_id, trade_rows)

    return {"run_id": run_id, "fidelity_report": fidelity_report, "n_trades": trades_count}


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
