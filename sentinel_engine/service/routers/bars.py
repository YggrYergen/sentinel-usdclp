"""sentinel_engine.service.routers.bars — /api/bars, /ws/ticks (W0.1a, A3a/A3b).

Moved verbatim out of `sentinel_engine.service.app` (plan recalibration V2,
W0.1 "split app.py into routers"). `build_router(lake_root, tick_hub)` is
called once from `create_app()` after those two dependencies exist; the
returned `APIRouter` is included via `app.include_router(...)` so the final
paths (`/api/bars`, `/ws/ticks`) stay stable.

A3a (windowed + LOD `/api/bars` v2, CT-2): `GET /api/bars` now serves the
CT-2 shape (`symbol`, `tf_requested`, `served_tf`, `clipped`, `bars`,
`overlays`) via `sentinel_engine.service.bars_source.read_window` +
`choose_served_tf`, reading pre-built lake tiers
(`sentinel_engine.lake.tiers.build_tiers` output) instead of the legacy
per-minute lake files. The old `/indicators`-style helpers in
`sentinel_engine.service.bars` (`bars_payload`, list-of-lists wire format)
are untouched and still used elsewhere; they are simply no longer wired to
this route.

A3b (server-side overlays): `overlays` query param (csv: `ema8,ema20,sar,
supertrend`) is now populated. Each requested overlay is computed with a
200-bar warmup window read via `read_window` (same served tier, extended
`from`), using the SAME indicator math as `/indicators`
(`sentinel_engine.strategies.emasar.ema_series`/`sar_series`,
`sentinel_engine.strategies._supertrend_ref.supertrend`,
`sentinel_engine.strategies.emasar_ref._atr_wilder`) — no duplicated math.
The warmup-extended series is then clipped back to `[from, to]` so every
overlay point's `t` is a member of the served `bars` window's `t` set.

`_parse_flexible_ts` and `_api_error` are imported lazily (inside
`build_router`, not at module import time) from `sentinel_engine.service.app`
to avoid a circular import — `app.py` imports this module at its own
top-level to register the router.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ..bars_source import BarsSourceError, choose_served_tf, read_window, tf_seconds
from ..stream import TickHub
from ...lake.tiers import TF_SECONDS as _VALID_TF_NAMES
from ...strategies._supertrend_ref import supertrend as _supertrend_series
from ...strategies.emasar import ema_series, sar_series
from ...strategies.emasar_ref import _atr_wilder

router = APIRouter()

# Display decimal places per symbol (A3a: no instrument-config field exists
# yet for this; documented default of 2 decimals, matching the CT-2 XAUUSD
# example, until a real per-instrument precision field lands).
_SYMBOL_DECIMALS: dict[str, int] = {"XAUUSD": 2}
_DEFAULT_DECIMALS = 2

# Overlay warmup: number of extra served-tier bars fetched before `from` so
# every indicator (largest period among ema8/ema20/supertrend's ATR(10)) is
# fully seeded by the time it reaches the visible window (CT-2 spec: 200).
_OVERLAY_WARMUP_BARS = 200

# Overlay params (A3b: match EmasarPolicy/V1 defaults used by /indicators —
# same "reuse, don't duplicate math" rule for the numbers, not just the code).
_EMA8_PERIOD = 8
_EMA20_PERIOD = 20
_SAR_STEP = 0.02
_SAR_MAX = 0.20
_ST_ATR_PERIOD = 10
_ST_MULT = 3.0

_SUPPORTED_OVERLAYS = ("ema8", "ema20", "sar", "supertrend")

# A2: valid tier-TF names (matches sentinel_engine.lake.tiers.TF_SECONDS keys,
# e.g. M1/M2/M5/M15/H1/D). Legacy manifest entries keyed by raw minute
# strings (e.g. "5") are NOT in this set and must be ignored by /api/coverage.
_VALID_TF_NAME_SET = frozenset(_VALID_TF_NAMES)

# In-process manifest cache, invalidated by source file mtime (A2). Keyed by
# the resolved manifest Path so multiple lake_roots (e.g. across tests) don't
# collide.
_manifest_cache: dict[Path, tuple[float, dict]] = {}


def _load_manifest(lake_root) -> dict:
    """Read `<lake_root>/manifest.json`, cached in-process and invalidated
    by the file's mtime (re-read only when mtime changes since last load)."""
    manifest_path = Path(lake_root) / "manifest.json"
    try:
        mtime = manifest_path.stat().st_mtime
    except OSError:
        _manifest_cache.pop(manifest_path, None)
        return {}

    cached = _manifest_cache.get(manifest_path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    _manifest_cache[manifest_path] = (mtime, manifest)
    return manifest


def _decimals_for(symbol: str) -> int:
    return _SYMBOL_DECIMALS.get(symbol.upper(), _DEFAULT_DECIMALS)


def _parse_overlays_param(overlays: str | None) -> list[str]:
    if not overlays:
        return []
    names = [name.strip() for name in overlays.split(",")]
    return [name for name in names if name in _SUPPORTED_OVERLAYS]


def _compute_overlays(
    requested: list[str],
    symbol: str,
    served_tf: str,
    from_epoch: int,
    to_epoch: int,
    lake_root,
    dp: int,
) -> dict[str, list[dict[str, Any]]]:
    """Compute each requested overlay server-side with a warmup window, then
    clip back to [from_epoch, to_epoch] so every overlay `t` is a subset of
    the served `bars` window's `t` set."""
    if not requested:
        return {}

    seconds = tf_seconds(served_tf)
    warmup_from = from_epoch - _OVERLAY_WARMUP_BARS * seconds
    warm_bars = read_window(symbol, served_tf, warmup_from, to_epoch, lake_root)

    result: dict[str, list[dict[str, Any]]] = {}
    if not warm_bars:
        return {name: [] for name in requested}

    times = [b["t"] for b in warm_bars]
    closes = [b["c"] for b in warm_bars]
    highs = [b["h"] for b in warm_bars]
    lows = [b["l"] for b in warm_bars]

    def _clip(vals: list[float | None]) -> list[dict[str, Any]]:
        out = []
        for t, v in zip(times, vals):
            if v is None:
                continue
            if t < from_epoch or t > to_epoch:
                continue
            out.append({"t": t, "v": round(v, dp)})
        return out

    for name in requested:
        if name == "ema8":
            result[name] = _clip(ema_series(closes, _EMA8_PERIOD))
        elif name == "ema20":
            result[name] = _clip(ema_series(closes, _EMA20_PERIOD))
        elif name == "sar":
            sar_vals, _trend = sar_series(highs, lows, _SAR_STEP, _SAR_MAX)
            result[name] = _clip(sar_vals)
        elif name == "supertrend":
            atr_vals = _atr_wilder(highs, lows, closes, _ST_ATR_PERIOD)
            if closes:
                _trend, line = _supertrend_series(
                    highs, lows, closes,
                    [a if a is not None else 0.0 for a in atr_vals], _ST_MULT,
                )
                st_vals = [None if atr_vals[i] is None else line[i] for i in range(len(atr_vals))]
            else:
                st_vals = []
            result[name] = _clip(st_vals)
        else:
            result[name] = []  # not reached: _parse_overlays_param already filters

    return result


def build_router(lake_root, tick_hub: TickHub) -> APIRouter:
    from ..app import _api_error, _parse_flexible_ts

    r = APIRouter()

    @r.get("/api/bars")
    def get_bars(
        symbol: str,
        tf: str = "M1",
        from_: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        max_points: int = 3000,
        overlays: str | None = None,
    ) -> Any:
        try:
            ts_from = _parse_flexible_ts(from_)
            ts_to = _parse_flexible_ts(to)
        except (ValueError, TypeError) as exc:
            return _api_error(400, "bad_range", f"invalid from/to: {exc}")

        try:
            tf_seconds(tf)
        except BarsSourceError as exc:
            return _api_error(400, "bad_tf", str(exc))

        from_epoch = int(ts_from.timestamp()) if ts_from is not None else 0
        to_epoch = int(ts_to.timestamp()) if ts_to is not None else from_epoch

        try:
            served_tf = choose_served_tf(tf, from_epoch, to_epoch, max_points)
            bars = read_window(symbol, served_tf, from_epoch, to_epoch, lake_root)
        except BarsSourceError as exc:
            return _api_error(400, "bad_tf", str(exc))
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the client
            return _api_error(500, "bars_failed", str(exc))

        clipped = len(bars) > max_points
        if clipped:
            bars = bars[-max_points:]

        dp = _decimals_for(symbol)
        rounded_bars = [
            {
                "t": b["t"],
                "o": round(b["o"], dp),
                "h": round(b["h"], dp),
                "l": round(b["l"], dp),
                "c": round(b["c"], dp),
                "v": b["v"],
            }
            for b in bars
        ]

        requested_overlays = _parse_overlays_param(overlays)
        overlays_payload = _compute_overlays(
            requested_overlays, symbol, served_tf, from_epoch, to_epoch, lake_root, dp,
        )

        return {
            "symbol": symbol,
            "tf_requested": tf,
            "served_tf": served_tf,
            "clipped": clipped,
            "bars": rounded_bars,
            "overlays": overlays_payload,
        }

    @r.get("/api/coverage")
    def get_coverage(symbol: str) -> Any:
        """CT-1 (frozen contract): lake coverage per timeframe for `symbol`.

        `{"symbol":..., "tfs":{"M1":{"first":..,"last":..}, ...}}` — only
        tier-named TFs (M1/M2/M5/M15/H1/D) are included; legacy per-minute
        manifest entries (e.g. key "5") are ignored. 404 if `symbol` is not
        in the manifest at all."""
        manifest = _load_manifest(lake_root)

        symbol_entries = manifest.get(symbol)
        if symbol_entries is None:
            return _api_error(404, "unknown_symbol", f"symbol not in lake manifest: {symbol}")

        tfs: dict[str, dict[str, int | None]] = {}
        for tf_name, entry in symbol_entries.items():
            if tf_name not in _VALID_TF_NAME_SET:
                continue
            tfs[tf_name] = {"first": entry.get("first"), "last": entry.get("last")}

        return {"symbol": symbol, "tfs": tfs}

    @r.websocket("/ws/ticks")
    async def ticks_ws(websocket: WebSocket) -> None:
        """`ticks:{SYMBOL}` channel (plan §D.6): client sends
        `{"sub":"ticks:XAUUSD"}` / `{"unsub":"ticks:XAUUSD"}`; server pushes
        `{"ch":"ticks:XAUUSD","t":epoch_ms,"bid","ask"}` on-change ~250ms,
        only while this socket (or another) is subscribed to that symbol.
        Subscribing to a second symbol on the same socket is additive."""
        await websocket.accept()
        subscribed: set[str] = set()
        try:
            while True:
                msg = await websocket.receive_json()
                sub = msg.get("sub")
                unsub = msg.get("unsub")
                if isinstance(sub, str) and sub.startswith("ticks:"):
                    symbol = sub[len("ticks:"):]
                    await tick_hub.subscribe(websocket, symbol)
                    subscribed.add(symbol)
                if isinstance(unsub, str) and unsub.startswith("ticks:"):
                    symbol = unsub[len("ticks:"):]
                    await tick_hub.unsubscribe(websocket, symbol)
                    subscribed.discard(symbol)
        except WebSocketDisconnect:
            pass
        finally:
            for symbol in list(subscribed):
                await tick_hub.unsubscribe(websocket, symbol)

    return r
